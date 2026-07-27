"""Smart Insights for the Workflow Builder canvas.

This module analyses the particle data behind the canvas and proposes plot
nodes worth adding, presented as cards in a dockable side panel.

The pipeline has four stages:

``resolve_scope``
    Decides *which samples* to analyse. Priority runs from the currently
    selected sample node, to the union of every sample node on the canvas, to
    every loaded sample. Element selection is deliberately never consulted, so
    insights can surface patterns in elements the user has not picked.

``gather_scope_data``
    Collects the raw particle dicts for that scope. Cheap enough for the GUI
    thread, which keeps the scene off the worker thread entirely.

``build_context_from``
    Turns those particles into an :class:`AnalysisContext` — the element
    matrix, detection masks and per-sample index that every analysis shares.
    Results are cached by scope fingerprint.

``_AnalysisWorker``
    Runs the statistical tests on a background thread and emits a list of
    :class:`Suggestion` objects for the panel to render.

Public entry points for the canvas dialog are :func:`integrate_insights_panel`
and :func:`make_insights_toggle_button`.
"""

from __future__ import annotations
import math
import re
import threading
from dataclasses import dataclass, field
import numpy as np
from scipy import stats as _stats
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPointF
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QScrollArea, QVBoxLayout, QWidget, QSplitter,
)

from tools.theme import theme as _theme
import logging
_itk_log = logging.getLogger("IsotopeTrack.results.results_reader")

# ──────────────────────────────────────────────────────────────────────────────
# Category metadata — icon + label only; colour comes from palette
# ──────────────────────────────────────────────────────────────────────────────

_FONT = "Segoe UI"

_CAT_META: dict[str, dict] = {
    "correlation":  {"icon": "⬡", "label": "Correlation"},
    "isotope":      {"icon": "⚛", "label": "Isotope Ratio"},
    "distribution": {"icon": "▦", "label": "Distribution"},
    "composition":  {"icon": "◔", "label": "Composition"},
    "comparison":   {"icon": "⇄", "label": "Comparison"},
    "outlier":      {"icon": "↑", "label": "Outlier"},
}

MIN_CORR_OVERLAP = 25
"""Co-detected particles a pair needs before its correlation is reported."""

FDR_Q = 0.05
"""Target false discovery rate for the pairwise correlation family."""

MIN_ABS_CORRELATION = 0.50
"""Effect-size floor, applied on top of significance, for a correlation card."""

MAX_CORRELATION_CARDS = 4
"""Most correlation pairs to surface from one scan."""

@dataclass
class Suggestion:
    """One proposed plot node, rendered as a card in the panel.

    Attributes:
        title: Short headline shown on the card, e.g. ``"56Fe vs 55Mn"``.
        reasoning: Sentence explaining why this was surfaced, including the
            statistics behind it.
        category: Key into :data:`_CAT_META`, controlling the card's icon and
            label.
        confidence: Ranking weight in ``0.0`` to ``1.0``. This is a heuristic
            priority score used for sorting and deduplication, not a
            statistical confidence level.
        node_type: Key into ``widget.canvas_widgets._NODE_FACTORIES``, naming
            the node to create when the card's Add button is pressed.
        config: Pre-set configuration merged into the new node, such as the
            elements to plot on each axis.
        elements: The elements this insight is actually about. Adding the card
            builds a sample selector narrowed to these, so the new branch
            carries only the relevant data. Left empty for insights that need
            the full element set to mean anything, such as the composition
            breakdown or the full correlation matrix.
    """

    title: str
    reasoning: str
    category: str
    confidence: float
    node_type: str
    config: dict = field(default_factory=dict)
    elements: tuple[str, ...] = ()

    @property
    def confidence_label(self) -> str:
        """Bucket the confidence score as ``"high"``, ``"medium"`` or ``"low"``."""
        if self.confidence >= 0.75:
            return "high"
        if self.confidence >= 0.45:
            return "medium"
        return "low"


# ──────────────────────────────────────────────────────────────────────────────
# Statistical helpers
# ──────────────────────────────────────────────────────────────────────────────

def _safe_float(v) -> float | None:
    """Coerce *v* to a positive float, or ``None`` if it is not usable.

    Zero, negatives and NaN all return ``None``: in this dataset they mean the
    element was not detected rather than measured at that value.

    Args:
        v: Any value read from a particle's ``elements`` mapping.

    Returns:
        The value as a float when it is finite and greater than zero,
        otherwise ``None``.
    """
    try:
        f = float(v)
        return f if (f > 0 and not math.isnan(f)) else None
    except Exception:
        _itk_log.exception("Handled exception in _safe_float")
        return None


def _build_matrix(
    particles: list[dict],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Build the element matrix in a single sparse pass.

    Only the elements each particle actually carries are visited, rather than
    every element for every particle, which matters because most particles
    carry a small fraction of the elements present across a sample. Numeric
    values are converted on a fast path, with anything exotic (strings,
    ``Decimal``, ``None``) falling back to :func:`_safe_float`.

    Args:
        particles: Particle dicts, each optionally holding an ``elements``
            mapping of element label to concentration.

    Returns:
        A ``(matrix, det_mask)`` pair. Both are keyed by element label and
        every array has length ``len(particles)``. ``matrix[el][i]`` holds the
        concentration of *el* in particle *i*, or ``0.0`` where the element was
        not detected. ``det_mask[el][i]`` records whether the element was
        detected at all, which is what separates a genuine non-detect from a
        measured zero — callers sensitive to censoring should mask on
        ``det_mask`` rather than testing ``> 0``. Elements with no positive
        reading anywhere are omitted entirely.
    """
    n = len(particles)
    if not n:
        return {}, {}

    rows: dict[str, list[int]] = {}
    vals: dict[str, list[float]] = {}
    isnan = math.isnan
    for i, p in enumerate(particles):
        for el, raw in (p.get("elements") or {}).items():
            if type(raw) is float:
                if not (raw > 0.0) or isnan(raw):
                    continue
                v = raw
            elif type(raw) is int:
                if raw <= 0:
                    continue
                v = float(raw)
            else:
                v = _safe_float(raw)
                if v is None:
                    continue
            r = rows.get(el)
            if r is None:
                rows[el] = [i]
                vals[el] = [v]
            else:
                r.append(i)
                vals[el].append(v)

    matrix: dict[str, np.ndarray] = {}
    det_mask: dict[str, np.ndarray] = {}
    for el, idx_list in rows.items():
        arr = np.zeros(n, dtype=np.float64)
        msk = np.zeros(n, dtype=bool)
        idx = np.asarray(idx_list, dtype=np.int64)
        arr[idx] = np.asarray(vals[el], dtype=np.float64)
        msk[idx] = True
        matrix[el] = arr
        det_mask[el] = msk
    return matrix, det_mask


def _correlate_pair(a: np.ndarray, b: np.ndarray,
                    min_overlap: int = MIN_CORR_OVERLAP) -> dict | None:
    """Correlate two element columns both parametrically and by rank.

    Pearson's r is taken on ``log1p`` values, since concentrations span orders
    of magnitude and are roughly log-normal. Spearman's rho is taken on the raw
    values, needs no distributional assumption, and is the coefficient used for
    ranking because it is far less swayed by a handful of extreme particles.

    Only particles detecting both elements contribute, which makes this a
    statement about the co-detected subset rather than the sample as a whole.
    The overlap count is returned so the caller can say so on the card.

    Args:
        a: Concentration array for the first element.
        b: Concentration array for the second element, aligned to *a*.
        min_overlap: Minimum co-detected particles required to report anything.

    Returns:
        A dict with ``pearson``, ``pearson_p``, ``spearman``, ``spearman_p``
        and ``overlap``, or ``None`` when the overlap is too small or either
        column is constant across it.
    """
    mask = (a > 0) & (b > 0)
    overlap = int(mask.sum())
    if overlap < min_overlap:
        return None

    xa, xb = a[mask], b[mask]
    if xa.std() == 0 or xb.std() == 0:
        return None

    try:
        pear = _stats.pearsonr(np.log1p(xa), np.log1p(xb))
        spear = _stats.spearmanr(xa, xb)
    except Exception:
        _itk_log.exception("[Insights] correlation failed")
        return None

    spearman = float(getattr(spear, "statistic", getattr(spear, "correlation", np.nan)))
    if not np.isfinite(spearman):
        return None

    return {
        "pearson": float(pear[0]),
        "pearson_p": float(pear[1]),
        "spearman": spearman,
        "spearman_p": float(spear[1]),
        "overlap": overlap,
    }


def _benjamini_hochberg(pvalues: list[float], q: float = FDR_Q) -> tuple[np.ndarray, np.ndarray]:
    """Control the false discovery rate across a family of tests.

    Testing every element pair means running hundreds of tests at once, where
    a handful will clear any fixed threshold through chance alone. The
    Benjamini-Hochberg procedure raises the bar in proportion to how many tests
    were run, so what survives is worth showing.

    Args:
        pvalues: One raw p-value per test.
        q: Target false discovery rate.

    Returns:
        A ``(significant, adjusted)`` pair of arrays aligned to *pvalues*, where
        *significant* flags the tests that pass and *adjusted* holds the
        corrected p-values suitable for display.
    """
    n = len(pvalues)
    if n == 0:
        return np.zeros(0, dtype=bool), np.zeros(0)

    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    ranked = p[order]
    ranks = np.arange(1, n + 1)

    adjusted_sorted = np.minimum.accumulate((ranked * n / ranks)[::-1])[::-1]
    adjusted_sorted = np.clip(adjusted_sorted, 0.0, 1.0)

    adjusted = np.empty(n)
    adjusted[order] = adjusted_sorted

    significant = np.zeros(n, dtype=bool)
    passing = np.nonzero(ranked <= q * ranks / n)[0]
    if passing.size:
        significant[order[: passing.max() + 1]] = True

    return significant, adjusted


def _isotope_symbol(name: str) -> str | None:
    """Extract the element symbol from an isotope label.

    Args:
        name: Isotope label such as ``"56Fe"``.

    Returns:
        The symbol (``"Fe"``), or ``None`` if *name* is not mass-number
        prefixed.
    """
    m = re.match(r"^\d+([A-Za-z]+)$", name.strip())
    return m.group(1) if m else None


def _group_isotopes(elements: list[str]) -> dict[str, list[str]]:
    """Group isotope labels by their shared element symbol.

    Only elements measured at two or more masses are returned, since a single
    isotope offers no ratio to compute.

    Args:
        elements: Isotope labels, e.g. ``["206Pb", "208Pb", "56Fe"]``.

    Returns:
        Element symbol to its isotope labels, e.g. ``{"Pb": ["206Pb", "208Pb"]}``.
    """
    groups: dict[str, list] = {}
    for el in elements:
        sym = _isotope_symbol(el)
        if sym:
            groups.setdefault(sym, []).append(el)
    return {sym: iso for sym, iso in groups.items() if len(iso) >= 2}




# ──────────────────────────────────────────────────────────────────────────────
# Canvas helpers
# ──────────────────────────────────────────────────────────────────────────────

def _find_source_node(scene) -> object | None:
    """Find the node a newly added plot node should be wired to.

    Picks the configured node carrying the most particles, on the assumption
    that it is the one the user is actually working from.

    Args:
        scene: The canvas scene.

    Returns:
        The chosen workflow node, or ``None`` if nothing on the canvas has
        output data yet.
    """
    best, best_n = None, 0
    for node in scene.workflow_nodes:
        if not getattr(node, "_has_output", False):
            continue
        for d in [
            *(
                [node.get_output_data()]
                if hasattr(node, "get_output_data")
                else []
            ),
            getattr(node, "input_data", None),
        ]:
            if not isinstance(d, dict):
                continue
            cnt = len(d.get("particle_data", []))
            if cnt > best_n:
                best, best_n = node, cnt
    return best


_SAMPLE_NODE_TYPES = ("sample_selector", "multiple_sample_selector")


def _find_batch_node(scene):
    """Find the batch node feeding the canvas, if there is one.

    Args:
        scene: The canvas scene.

    Returns:
        The batch sample selector node, or ``None``.
    """
    for node in getattr(scene, "workflow_nodes", []):
        if getattr(node, "node_type", "") == "batch_sample_selector":
            return node
    return None


def _isotope_entries(parent_window, scene, labels) -> list[dict]:
    """Resolve element labels into the isotope records a selector expects.

    A selector node stores isotopes as dicts carrying ``symbol``, ``mass``,
    ``key`` and ``label``. Particle data only ever names the label, so the
    remaining fields are recovered from the isotopes the app has loaded. They
    matter because the configuration dialog matches on symbol and mass, and a
    record missing them would open blank.

    Args:
        parent_window: Main window exposing ``selected_isotopes`` and
            ``get_formatted_label``.
        scene: The canvas scene, checked for a batch node whose isotope list
            takes precedence.
        labels: Element labels to resolve, e.g. ``("56Fe", "55Mn")``.

    Returns:
        One record per resolved label, in the order given. Labels that cannot
        be matched are skipped, so an empty list means none resolved.
    """
    available = None
    for node in getattr(scene, "workflow_nodes", []):
        batch = getattr(node, "batch_available_isotopes", None)
        if batch:
            available = batch
            break
    if not available:
        available = getattr(parent_window, "selected_isotopes", None)
    if not isinstance(available, dict) or not available:
        return []

    formatter = getattr(parent_window, "get_formatted_label", None)
    by_label: dict[str, dict] = {}
    for symbol, masses in available.items():
        for mass in masses or ():
            try:
                key = f"{symbol}-{float(mass):.4f}"
            except (TypeError, ValueError):
                continue
            label = key
            if callable(formatter):
                try:
                    label = formatter(key) or key
                except Exception:
                    _itk_log.exception("[Insights] label lookup failed")
            by_label.setdefault(
                label,
                {"symbol": symbol, "mass": mass, "key": key, "label": label},
            )

    return [by_label[l] for l in labels if l in by_label]


def _samples_of_node(node) -> list[str]:
    """List the samples a selector node refers to.

    Covers single selection, summed replicates, and multi-sample nodes with or
    without a per-sample config. The node's isotope filter is ignored, since
    insights are always computed across every element.

    Args:
        node: A ``sample_selector`` or ``multiple_sample_selector`` node.

    Returns:
        Sample names, possibly with duplicates, in the order found.
    """
    names: list[str] = []
    if getattr(node, "sum_replicates", False) and getattr(node, "replicate_samples", None):
        names.extend(node.replicate_samples)
    elif getattr(node, "selected_sample", None):
        names.append(node.selected_sample)

    cfg = getattr(node, "sample_config", None)
    if cfg:
        names.extend(s for s, c in cfg.items() if c.get("included"))
    elif getattr(node, "selected_samples", None):
        names.extend(node.selected_samples)

    return [n for n in names if n]


def _dedupe(seq) -> list[str]:
    """Drop duplicates and falsy entries while preserving order.

    Args:
        seq: Any iterable of strings.

    Returns:
        The distinct truthy items, first occurrence order preserved.
    """
    seen: set = set()
    return [x for x in seq if x and not (x in seen or seen.add(x))]


def _raw_pool(scene, parent_window) -> dict[str, list[dict]]:
    """Collect every loaded particle, grouped by sample, with all elements intact.

    This is the unfiltered source the whole panel reads from, deliberately
    bypassing the selector nodes so that no element selection can narrow it.

    A batch node's particle pool takes precedence when one is on the canvas,
    because in that workflow the main window holds no per-sample data.

    Args:
        scene: The canvas scene, searched for a batch node.
        parent_window: Main window exposing ``sample_particle_data``.

    Returns:
        Sample name to its particle dicts. Empty if nothing is loaded.
    """
    for node in getattr(scene, "workflow_nodes", []):
        batch = getattr(node, "batch_particle_data", None)
        if batch:
            pool: dict[str, list[dict]] = {}
            for p in batch:
                pool.setdefault(p.get("source_sample", ""), []).append(p)
            pool.pop("", None)
            if pool:
                return pool

    pool = getattr(parent_window, "sample_particle_data", None)
    return pool if isinstance(pool, dict) else {}


@dataclass(frozen=True)
class AnalysisScope:
    """Which samples the Insights engine should look at, and why.

    Attributes:
        sample_names: The samples to analyse, in display order.
        origin: How the scope was arrived at. ``"selection"`` means it came
            from the sample node the user has selected, ``"canvas"`` from the
            union of every sample node present, and ``"all"`` from everything
            loaded because the canvas offered no sample nodes.
        counts: Particle count per entry in *sample_names*, index aligned.
        pool_ids: Identity of each sample's particle list, index aligned. Two
            different datasets can share a name and a particle count, so the
            counts alone are not enough to tell cached contexts apart.
    """

    sample_names: tuple[str, ...]
    origin: str
    counts: tuple[int, ...]
    pool_ids: tuple[int, ...] = ()

    @property
    def key(self) -> str:
        """Return the cache fingerprint for this scope.

        Covers the samples, their particle counts and the identity of the
        underlying lists, so reloading or replacing data invalidates any
        context cached against the same sample names.
        """
        ids = ",".join(str(i) for i in self.pool_ids)
        return f"{self.origin}|{'|'.join(self.sample_names)}|{sum(self.counts)}|{ids}"

    @property
    def total_particles(self) -> int:
        """Return the number of particles across every sample in scope."""
        return sum(self.counts)

    @property
    def is_multi(self) -> bool:
        """Return whether the scope spans more than one sample."""
        return len(self.sample_names) > 1

    @property
    def origin_label(self) -> str:
        """Return a human-readable form of :attr:`origin` for the panel."""
        return {
            "selection": "selected node",
            "canvas": "canvas",
            "all": "all loaded samples",
        }.get(self.origin, self.origin)


def resolve_scope(scene, parent_window) -> AnalysisScope:
    """Decide which samples to analyse.

    Three levels are tried in order: the samples of whichever sample node the
    user has selected, then the union of every sample node on the canvas, then
    every loaded sample. Samples with no particle data are dropped at the end,
    so a node pointing at something unloaded cannot skew the result.

    Element selection is never consulted at any level. That is what allows a
    card to surface a pattern in an element the user has not picked.

    Args:
        scene: The canvas scene, read for both selection and node list.
        parent_window: Main window holding the loaded particle data.

    Returns:
        The resolved scope, with empty ``sample_names`` when nothing is loaded.
    """
    pool = _raw_pool(scene, parent_window)

    selected: list[str] = []
    try:
        for item in scene.selectedItems():
            node = getattr(item, "workflow_node", None)
            if node is not None and getattr(node, "node_type", "") in _SAMPLE_NODE_TYPES:
                selected.extend(_samples_of_node(node))
    except Exception:
        _itk_log.exception("[Insights] Could not read canvas selection")

    origin = "selection"
    names = _dedupe(selected)

    if not names:
        origin = "canvas"
        on_canvas: list[str] = []
        for node in getattr(scene, "workflow_nodes", []):
            if getattr(node, "node_type", "") in _SAMPLE_NODE_TYPES:
                on_canvas.extend(_samples_of_node(node))
        names = _dedupe(on_canvas)

    if not names:
        origin = "all"
        names = _dedupe(pool.keys())

    names = [n for n in names if pool.get(n)]
    counts = tuple(len(pool.get(n, ())) for n in names)
    pool_ids = tuple(id(pool.get(n)) for n in names)
    return AnalysisScope(tuple(names), origin, counts, pool_ids)


# ──────────────────────────────────────────────────────────────────────────────
# Analysis context — built once per scope, shared by every category analyser
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class AnalysisContext:
    """Precomputed data shared by every analysis run against one scope.

    Building this is the expensive part of the panel, so it happens once per
    scope and is reused across insight categories.

    Attributes:
        scope: The scope this context was built for.
        particles: The particle dicts in scope, concatenated sample by sample.
        matrix: Element label to concentration array, zero-filled at
            non-detects. Every array is ``n`` long.
        det_mask: Element label to boolean detection array, distinguishing a
            non-detect from a measured zero.
        det_counts: Element label to the number of particles detecting it.
        sample_idx: For each particle, the index of its sample within
            ``scope.sample_names``. This is what lets between-sample analyses
            group particles that carry no ``source_sample`` key of their own.
    """

    scope: AnalysisScope
    particles: list[dict]
    matrix: dict[str, np.ndarray]
    det_mask: dict[str, np.ndarray]
    det_counts: dict[str, int]
    sample_idx: np.ndarray

    @property
    def n(self) -> int:
        """Return the number of particles in the context."""
        return len(self.particles)

    @property
    def sample_names(self) -> list[str]:
        """Return the scope's sample names as a list."""
        return list(self.scope.sample_names)

    @property
    def is_multi(self) -> bool:
        """Return whether the context spans more than one sample."""
        return self.scope.is_multi

    def elements_by_abundance(self) -> list[str]:
        """Rank every element by how many particles detected it.

        Returns:
            Element labels, most frequently detected first.
        """
        return [el for el, _ in sorted(self.det_counts.items(), key=lambda x: -x[1])]

    def frequent_elements(self, min_frac: float = 0.04, min_abs: int = 5) -> list[str]:
        """Select the elements detected often enough to be worth testing.

        Filtering these out early keeps rare elements from producing
        statistics that rest on a handful of particles.

        Args:
            min_frac: Minimum share of particles that must detect the element.
            min_abs: Absolute floor applied when the dataset is small.

        Returns:
            Element labels passing the threshold, most abundant first.
        """
        floor = max(min_abs, self.n * min_frac)
        return [el for el in self.elements_by_abundance() if self.det_counts[el] >= floor]

    def particle_mask_for(self, elements) -> np.ndarray:
        """Mark the particles carrying at least one of *elements*.

        This is the rule used when scoping a newly added node: a particle is
        kept if any of the elements of interest was detected in it, rather than
        requiring all of them.

        Args:
            elements: Element labels. Unknown labels contribute nothing.

        Returns:
            Boolean array of length ``n``, true where the particle qualifies.
        """
        out = np.zeros(self.n, dtype=bool)
        for el in elements:
            m = self.det_mask.get(el)
            if m is not None:
                out |= m
        return out


_CTX_CACHE: dict[str, AnalysisContext] = {}
_CTX_CACHE_MAX = 3
_CTX_LOCK = threading.Lock()


def gather_scope_data(
    scene, parent_window, scope: AnalysisScope
) -> tuple[list[dict], np.ndarray]:
    """Collect the particle list for *scope*.

    Only references to dicts that already exist are concatenated, so this is
    cheap enough to run on the GUI thread. Doing so lets the caller hand plain
    data to a worker and keep the scene off the background thread entirely.

    Args:
        scene: The canvas scene, used to locate the particle pool.
        parent_window: Main window holding the loaded particle data.
        scope: The resolved scope to gather for.

    Returns:
        A ``(particles, sample_idx)`` pair, where *sample_idx* gives each
        particle's index into ``scope.sample_names``.
    """
    pool = _raw_pool(scene, parent_window)
    particles: list[dict] = []
    idx_parts: list[np.ndarray] = []
    for i, name in enumerate(scope.sample_names):
        chunk = pool.get(name) or []
        particles.extend(chunk)
        idx_parts.append(np.full(len(chunk), i, dtype=np.int32))

    sample_idx = (
        np.concatenate(idx_parts) if idx_parts else np.zeros(0, dtype=np.int32)
    )
    return particles, sample_idx


def build_context_from(
    scope: AnalysisScope, particles: list[dict], sample_idx: np.ndarray
) -> AnalysisContext:
    """Build an :class:`AnalysisContext`, reusing a cached one when possible.

    Contexts are cached by scope fingerprint, so switching between insight
    categories reuses the matrix instead of rebuilding it. The cache holds a
    few entries and evicts the oldest.

    Safe to call from a worker thread: it touches no Qt objects and guards the
    cache with a lock.

    Args:
        scope: The scope the particles were gathered for.
        particles: Particle dicts from :func:`gather_scope_data`.
        sample_idx: Per-particle sample index from :func:`gather_scope_data`.

    Returns:
        The context for *scope*, freshly built or from cache.
    """
    with _CTX_LOCK:
        cached = _CTX_CACHE.get(scope.key)
    if cached is not None:
        _itk_log.debug(f"[Insights] context cache hit ({scope.key})")
        return cached

    matrix, det_mask = _build_matrix(particles)
    ctx = AnalysisContext(
        scope=scope,
        particles=particles,
        matrix=matrix,
        det_mask=det_mask,
        det_counts={el: int(m.sum()) for el, m in det_mask.items()},
        sample_idx=sample_idx,
    )

    _itk_log.debug(
        f"[Insights] built context: {ctx.n:,} particles, {len(matrix)} elements, "
        f"{len(scope.sample_names)} sample(s) from {scope.origin}"
    )

    with _CTX_LOCK:
        if len(_CTX_CACHE) >= _CTX_CACHE_MAX:
            _CTX_CACHE.pop(next(iter(_CTX_CACHE)))
        _CTX_CACHE[scope.key] = ctx
    return ctx


def build_context(scene, parent_window, scope: AnalysisScope | None = None) -> AnalysisContext:
    """Resolve, gather and build a context in one call.

    A convenience wrapper for callers with no reason to keep the stages apart,
    such as tests. The panel calls the stages separately so that only the
    matrix build happens off the GUI thread.

    Args:
        scene: The canvas scene.
        parent_window: Main window holding the loaded particle data.
        scope: Scope to use. Resolved from the scene when omitted.

    Returns:
        The analysis context for the resolved scope.
    """
    if scope is None:
        scope = resolve_scope(scene, parent_window)
    particles, sample_idx = gather_scope_data(scene, parent_window, scope)
    return build_context_from(scope, particles, sample_idx)


def invalidate_context_cache() -> None:
    """Drop every cached context.

    Scope fingerprints already cover sample and particle-count changes, so this
    is only needed when the underlying values change without the counts moving.
    """
    with _CTX_LOCK:
        _CTX_CACHE.clear()


# ──────────────────────────────────────────────────────────────────────────────
# Category analysers — one family of tests each, over a shared context
# ──────────────────────────────────────────────────────────────────────────────

def _say(progress, message: str) -> None:
    """Report progress if the caller supplied a callback.

    Args:
        progress: Callable taking a status string, or ``None``.
        message: Status to report.
    """
    if progress is not None:
        progress(message)


def _analyse_correlation(ctx: AnalysisContext, progress=None) -> list[Suggestion]:
    """Find element pairs that vary together.

    Every pair of sufficiently detected elements is tested, then the whole
    family is put through a false discovery rate correction. Running hundreds
    of tests guarantees some will clear a fixed threshold by chance, so a pair
    has to survive correction *and* clear an effect-size floor before it earns
    a card.

    Args:
        ctx: The shared analysis context.
        progress: Optional callable receiving status strings.

    Returns:
        Up to :data:`MAX_CORRELATION_CARDS` pair suggestions, plus a full
        correlation matrix suggestion when there are enough elements to make
        one worth looking at.
    """
    out: list[Suggestion] = []
    els = ctx.frequent_elements()
    if len(els) < 2:
        return out

    _say(progress, "Correlating element pairs…")
    pairs: list[tuple[str, str, dict]] = []
    for i in range(len(els)):
        for j in range(i + 1, len(els)):
            stats_ = _correlate_pair(ctx.matrix[els[i]], ctx.matrix[els[j]])
            if stats_ is not None:
                pairs.append((els[i], els[j], stats_))

    if pairs:
        _say(progress, f"Correcting {len(pairs)} pairwise tests…")
        significant, adjusted = _benjamini_hochberg([p[2]["pearson_p"] for p in pairs])

        kept = [
            (ea, eb, res, float(adjusted[k]))
            for k, (ea, eb, res) in enumerate(pairs)
            if significant[k] and abs(res["spearman"]) >= MIN_ABS_CORRELATION
        ]
        kept.sort(key=lambda t: -abs(t[2]["spearman"]))

        for ea, eb, res, q_value in kept[:MAX_CORRELATION_CARDS]:
            rho = res["spearman"]
            direction = "positive" if rho > 0 else "negative"
            strength = "Strong" if abs(rho) >= 0.80 else "Moderate"
            out.append(Suggestion(
                title=f"{ea} vs {eb}",
                reasoning=(
                    f"{strength} {direction} rank correlation "
                    f"(ρ = {rho:+.2f}, log Pearson r = {res['pearson']:+.2f}). "
                    f"{res['overlap']:,} of {ctx.n:,} particles carry both. "
                    f"q = {q_value:.2g} after correcting {len(pairs)} tests."
                ),
                category="correlation",
                confidence=min(abs(rho), 1.0),
                node_type="correlation_plot",
                config={"x_element": ea, "y_element": eb},
                elements=(ea, eb),
            ))

    if len(els) >= 4:
        out.append(Suggestion(
            title=f"Full matrix: {len(els)} elements",
            reasoning=(
                "Every pairwise correlation in one heatmap. Blocks of "
                "correlated elements point to a shared source."
            ),
            category="correlation",
            confidence=0.68,
            node_type="correlation_matrix",
            config={},
        ))
    return out


def _analyse_isotope(ctx: AnalysisContext, progress=None) -> list[Suggestion]:
    """Find isotope pairs worth plotting as a ratio.

    For each element measured at two or more masses, the lightest and heaviest
    are paired. Every other element is then tested against that ratio, and the
    strongest association becomes the suggested x-axis, since a ratio that
    tracks another element usually indicates mixing between two sources.

    Args:
        ctx: The shared analysis context.
        progress: Optional callable receiving status strings.

    Returns:
        One suggestion per isotope group, for at most four groups.
    """
    out: list[Suggestion] = []
    mat = ctx.matrix
    all_els = ctx.elements_by_abundance()
    frequent = ctx.frequent_elements()

    groups = _group_isotopes(all_els)
    if not groups:
        return out

    _say(progress, "Pairing isotopes…")
    non_isotopic = [e for e in frequent if _isotope_symbol(e) is None]

    for _symbol, isotopes in list(groups.items())[:4]:
        ordered = sorted(isotopes, key=lambda x: int(re.match(r"^(\d+)", x).group(1)))
        num, den = ordered[0], ordered[-1]
        if num not in mat or den not in mat:
            continue

        joint = ctx.det_mask[num] & ctx.det_mask[den]
        joint_n = int(joint.sum())
        if joint_n < 5:
            continue

        ratio = np.where(joint, mat[num] / (mat[den] + 1e-30), np.nan)

        best_element: str | None = None
        best_r = 0.0
        for other in non_isotopic:
            if other in (num, den):
                continue
            mask = joint & ctx.det_mask[other]
            if mask.sum() < MIN_CORR_OVERLAP:
                continue
            ratio_values, other_values = ratio[mask], mat[other][mask]
            if ratio_values.std() < 1e-10 or other_values.std() < 1e-10:
                continue
            try:
                r = float(np.corrcoef(np.log1p(ratio_values),
                                      np.log1p(other_values))[0, 1])
            except Exception:
                _itk_log.exception("[Insights] isotope ratio correlation failed")
                continue
            if abs(r) > abs(best_r):
                best_r, best_element = r, other

        config = {"element1": num, "element2": den, "x_axis_element": den}
        elements = [num, den]
        extra = ""
        if best_element and abs(best_r) >= 0.40:
            config["x_axis_element"] = best_element
            elements.append(best_element)
            extra = (
                f" The ratio tracks {best_element} "
                f"({'positively' if best_r > 0 else 'negatively'}, "
                f"r = {best_r:+.2f}), so it is set as the x-axis."
            )

        out.append(Suggestion(
            title=f"{num} / {den} ratio",
            reasoning=f"{joint_n:,} particles carry both isotopes.{extra}",
            category="isotope",
            confidence=min(joint_n / ctx.n * 2, 0.93),
            node_type="isotopic_ratio_plot",
            config=config,
            elements=tuple(elements),
        ))
    return out


def _analyse_distribution(ctx: AnalysisContext, progress=None) -> list[Suggestion]:
    """Rank elements by how widely their concentrations vary.

    A high coefficient of variation means particles carry wildly different
    amounts of that element, which is worth seeing as a distribution rather
    than reading as a single average.

    Args:
        ctx: The shared analysis context.
        progress: Optional callable receiving status strings.

    Returns:
        A box plot suggestion across the most variable elements and a histogram
        suggestion for the single most variable one.
    """
    out: list[Suggestion] = []
    els = ctx.frequent_elements()
    if not els:
        return out

    _say(progress, "Ranking element variability…")
    spreads: list[tuple[float, str]] = []
    for el in els:
        values = ctx.matrix[el][ctx.det_mask[el]]
        if len(values) >= 5:
            spreads.append((float(values.std() / (values.mean() + 1e-30)), el))
    if not spreads:
        return out

    spreads.sort(key=lambda x: -x[0])
    top = [el for _, el in spreads[:4]]
    cv = spreads[0][0]
    confidence = min(cv / 3.0, 0.85)

    out.append(Suggestion(
        title=f"Wide spread: {', '.join(top[:3])}",
        reasoning=(
            f"Coefficient of variation up to {cv:.1f}×, so concentrations "
            "differ enormously from particle to particle."
        ),
        category="distribution",
        confidence=confidence,
        node_type="box_plot",
        config={"elements": top},
        elements=tuple(top),
    ))
    out.append(Suggestion(
        title=f"Histogram: {top[0]}",
        reasoning=(
            f"{top[0]} varies most (CV = {cv:.1f}×). A histogram shows whether "
            "that is one broad population or several."
        ),
        category="distribution",
        confidence=confidence * 0.85,
        node_type="histogram_plot",
        config={"element": top[0]},
        elements=(top[0],),
    ))
    return out


def _analyse_composition(ctx: AnalysisContext, progress=None) -> list[Suggestion]:
    """Summarise which element combinations particles actually contain.

    Args:
        ctx: The shared analysis context.
        progress: Optional callable receiving status strings.

    Returns:
        A bar chart and a pie chart suggestion, both left unscoped because the
        point of each is the spread across every element.
    """
    out: list[Suggestion] = []
    _say(progress, "Counting element combinations…")

    combos: dict[tuple, int] = {}
    for p in ctx.particles:
        detected = tuple(sorted(
            el for el, v in (p.get("elements") or {}).items()
            if _safe_float(v) is not None
        ))
        if detected:
            combos[detected] = combos.get(detected, 0) + 1
    if not combos:
        return out

    top_combo, top_count = max(combos.items(), key=lambda x: x[1])
    confidence = min(top_count / ctx.n + 0.3, 0.88)

    out.append(Suggestion(
        title="Element composition",
        reasoning=(
            f"Most common combination is {' + '.join(top_combo[:4])}, in "
            f"{top_count:,} of {ctx.n:,} particles ({top_count / ctx.n * 100:.0f}%)."
        ),
        category="composition",
        confidence=confidence,
        node_type="element_bar_chart_plot",
        config={},
    ))
    out.append(Suggestion(
        title="Particle type breakdown",
        reasoning=(
            f"{len(combos):,} distinct element combinations were measured. "
            "A pie chart shows which particle types dominate."
        ),
        category="composition",
        confidence=confidence * 0.80,
        node_type="pie_chart_plot",
        config={},
    ))
    return out


def _analyse_comparison(ctx: AnalysisContext, progress=None) -> list[Suggestion]:
    """Find elements whose concentrations differ between samples.

    Each element is compared across samples with a Kruskal-Wallis test, which
    assumes nothing about the shape of the distributions, and the family of
    tests is corrected for false discovery. Surviving elements are ranked by
    how far apart the sample means actually sit, so the card leads with size of
    difference rather than significance alone.

    Args:
        ctx: The shared analysis context.
        progress: Optional callable receiving status strings.

    Returns:
        Up to two comparison suggestions, or nothing for a single-sample scope.
    """
    out: list[Suggestion] = []
    if not ctx.is_multi:
        return out

    _say(progress, "Comparing samples…")
    tests: list[tuple[str, float, float, int]] = []
    for el in ctx.frequent_elements():
        column, detected = ctx.matrix[el], ctx.det_mask[el]
        groups = []
        for i in range(len(ctx.sample_names)):
            selected = detected & (ctx.sample_idx == i)
            if int(selected.sum()) >= 5:
                groups.append(column[selected])
        if len(groups) < 2:
            continue
        try:
            _stat, p_value = _stats.kruskal(*groups)
        except Exception:
            continue
        if not np.isfinite(p_value):
            continue
        means = [float(g.mean()) for g in groups]
        spread = (max(means) - min(means)) / (max(means) + 1e-30)
        tests.append((el, float(p_value), spread, len(groups)))

    if not tests:
        return out

    significant, adjusted = _benjamini_hochberg([t[1] for t in tests])
    kept = [(t, float(adjusted[k])) for k, t in enumerate(tests) if significant[k]]
    kept.sort(key=lambda x: -x[0][2])

    for (el, _p, spread, group_count), q_value in kept[:2]:
        out.append(Suggestion(
            title=f"{el} differs across {group_count} samples",
            reasoning=(
                f"Mean {el} varies {spread * 100:.0f}% between samples "
                f"(Kruskal-Wallis q = {q_value:.2g} across {len(tests)} elements)."
            ),
            category="comparison",
            confidence=min(spread + 0.3, 0.90),
            node_type="concentration_comparison",
            config={"element": el},
            elements=(el,),
        ))
    return out


def _analyse_outlier(ctx: AnalysisContext, progress=None) -> list[Suggestion]:
    """Find elements with a detached population of unusually high particles.

    The interquartile test runs on log-transformed concentrations. On the raw
    scale it would flag essentially every element, because single-particle
    concentrations are heavy-tailed by nature and a long right tail is the norm
    rather than the exception.

    Args:
        ctx: The shared analysis context.
        progress: Optional callable receiving status strings.

    Returns:
        At most one suggestion, for the element with the largest outlying
        fraction.
    """
    out: list[Suggestion] = []
    _say(progress, "Scanning for outliers…")

    flagged: list[tuple[float, str, int]] = []
    for el in ctx.frequent_elements():
        values = ctx.matrix[el][ctx.det_mask[el]]
        if len(values) < 20:
            continue
        logged = np.log10(values)
        q1, q3 = np.percentile(logged, 25), np.percentile(logged, 75)
        iqr = q3 - q1
        if iqr <= 0:
            continue
        count = int(np.sum(logged > q3 + 3 * iqr))
        fraction = count / len(values)
        if fraction > 0.01:
            flagged.append((fraction, el, count))

    if not flagged:
        return out

    flagged.sort(key=lambda x: -x[0])
    fraction, el, count = flagged[0]
    out.append(Suggestion(
        title=f"Outliers: {el}",
        reasoning=(
            f"{count:,} particles ({fraction * 100:.1f}%) sit more than 3 IQR "
            f"above the {el} log-concentration range, suggesting a separate "
            "high-concentration population."
        ),
        category="outlier",
        confidence=min(fraction * 5 + 0.4, 0.80),
        node_type="heatmap_plot",
        config={"highlight_element": el},
    ))
    return out


@dataclass(frozen=True)
class InsightCategory:
    """One family of tests the user can run from the panel.

    Attributes:
        key: Identifier, also the ``category`` on suggestions it produces.
        label: Text for the chip.
        icon: Glyph shown beside the label.
        run: Callable taking ``(ctx, progress)`` and returning suggestions.
    """

    key: str
    label: str
    icon: str
    run: object


_ANALYSERS: dict[str, InsightCategory] = {
    key: InsightCategory(key, meta["label"], meta["icon"], fn)
    for key, meta, fn in (
        ("correlation", _CAT_META["correlation"], _analyse_correlation),
        ("isotope", _CAT_META["isotope"], _analyse_isotope),
        ("distribution", _CAT_META["distribution"], _analyse_distribution),
        ("composition", _CAT_META["composition"], _analyse_composition),
        ("comparison", _CAT_META["comparison"], _analyse_comparison),
        ("outlier", _CAT_META["outlier"], _analyse_outlier),
    )
}


def category_keys() -> list[str]:
    """List the analysis categories in the order the panel shows them.

    Returns:
        Category keys, suitable for indexing :data:`_ANALYSERS`.
    """
    return list(_ANALYSERS)


def _dedupe_suggestions(suggestions: list[Suggestion]) -> list[Suggestion]:
    """Rank suggestions and drop near-duplicates.

    Two cards proposing the same node type are usually the same idea twice, so
    only the strongest survives. Correlation plots are allowed a second entry,
    since a different element pair is a genuinely different plot.

    Args:
        suggestions: Suggestions from one or more analysers.

    Returns:
        The surviving suggestions, most confident first.
    """
    seen: dict[str, int] = {}
    out: list[Suggestion] = []
    for s in sorted(suggestions, key=lambda x: -x.confidence):
        limit = 2 if s.node_type == "correlation_plot" else 1
        if seen.get(s.node_type, 0) < limit:
            out.append(s)
            seen[s.node_type] = seen.get(s.node_type, 0) + 1
    return out


def analyse(ctx: AnalysisContext, categories=None, progress=None,
            should_stop=None) -> list[Suggestion]:
    """Run one or more categories of analysis over *ctx*.

    Args:
        ctx: The shared analysis context.
        categories: Category keys to run. All of them when omitted.
        progress: Optional callable receiving status strings.
        should_stop: Optional callable returning ``True`` to abandon the run
            between categories.

    Returns:
        The deduplicated suggestions, most confident first. Empty if the
        context is too small to analyse or the run was stopped.
    """
    if ctx.n < 5 or not ctx.matrix:
        return []

    keys = list(categories) if categories else category_keys()
    found: list[Suggestion] = []
    for key in keys:
        if should_stop is not None and should_stop():
            return []
        analyser = _ANALYSERS.get(key)
        if analyser is None:
            _itk_log.debug(f"[Insights] unknown category: {key}")
            continue
        try:
            found.extend(analyser.run(ctx, progress))
        except Exception:
            _itk_log.exception(f"[Insights] {key} analysis failed")
    return _dedupe_suggestions(found)


# ──────────────────────────────────────────────────────────────────────────────
# Analysis worker (runs in a QThread)
# ──────────────────────────────────────────────────────────────────────────────

class _AnalysisWorker(QThread):
    """Background thread that turns particle data into :class:`Suggestion` cards.

    The worker is handed plain data rather than the scene, so it never touches
    Qt objects owned by the GUI thread. It is single-use: construct one per
    analysis and discard it when finished.

    Signals:
        results_ready: Emitted once with the final list of suggestions. Named
            to avoid shadowing ``QThread.finished``, which the panel relies on
            to know when a cancelled thread has actually exited.
        progress: Emitted with a short status string as each stage begins.
    """

    results_ready = Signal(list)
    progress = Signal(str)

    def __init__(self, scope: AnalysisScope, particles: list[dict],
                 sample_idx: np.ndarray, categories=None):
        """Prepare an analysis run.

        Args:
            scope: The resolved scope these particles were gathered for.
            particles: Particle dicts to analyse.
            sample_idx: Index into ``scope.sample_names`` for each particle.
            categories: Category keys to run. All of them when omitted.
        """
        super().__init__()
        self._scope = scope
        self._particles = particles
        self._sample_idx = sample_idx
        self._categories = tuple(categories) if categories else None
        self._abort = False

    def cancel(self) -> None:
        """Ask the run to stop at the next stage boundary.

        ``QThread.quit()`` only ends a thread running an event loop, and
        :meth:`run` here is a plain blocking method, so cancellation has to be
        a flag the analysis checks as it goes. A cancelled run emits nothing.
        """
        self._abort = True

    def _stop(self) -> bool:
        """Return whether :meth:`cancel` has been called."""
        return self._abort

    def run(self):
        """Analyse the particles and emit the resulting suggestions.

        Builds the shared context, which is cached so that running a second
        category over the same scope reuses the element matrix, then runs the
        requested analysers.

        Emits an empty list when there is too little data to say anything.
        Returns without emitting if cancelled part way.
        """
        if len(self._particles) < 5:
            self.results_ready.emit([])
            return

        self.progress.emit("Building element matrix…")
        ctx = build_context_from(self._scope, self._particles, self._sample_idx)

        if self._stop():
            return

        found = analyse(
            ctx,
            categories=self._categories,
            progress=self.progress.emit,
            should_stop=self._stop,
        )

        if self._stop():
            return
        self.results_ready.emit(found)


# ──────────────────────────────────────────────────────────────────────────────
# Suggestion card  — muted, theme-aware, no vivid category colours
# ──────────────────────────────────────────────────────────────────────────────

class _Card(QFrame):
    """One suggestion rendered as a card in the panel.

    Shows the category tag, title, reasoning and a confidence bar, with an Add
    button that hands the suggestion back to the panel. Colours come from the
    active theme palette rather than per-category accents, so a list of cards
    reads as one surface.
    """

    def __init__(self, s: Suggestion, on_add, parent=None):
        """Build a card for one suggestion.

        Args:
            s: The suggestion to display.
            on_add: Callback invoked with *s* when Add is pressed.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._s = s
        self._on_add = on_add
        self._build()

    def _build(self):
        """Lay out and style the card's contents."""
        p = _theme.palette
        meta = _CAT_META.get(self._s.category, _CAT_META["correlation"])
        conf_col = {
            "high": p.success, "medium": p.warning, "low": p.disabled
        }[self._s.confidence_label]

        self.setObjectName("insightCard")
        self.setStyleSheet(f"""
            QFrame#insightCard {{
                background: {p.bg_secondary};
                border: 1px solid {p.border_subtle};
                border-left: 3px solid {p.accent};
                border-radius: 6px;
            }}
            QFrame#insightCard:hover {{
                background: {p.bg_hover};
                border-color: {p.border};
                border-left: 3px solid {p.accent_hover};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(4)

        tag = QLabel(f"{meta['icon']}  {meta['label'].upper()}")
        tag.setStyleSheet(f"""
            color: {p.text_muted}; font-size: 9px; font-weight: 700;
            font-family: '{_FONT}'; background: transparent; letter-spacing: 0.5px;
        """)
        root.addWidget(tag)

        title = QLabel(self._s.title)
        title.setWordWrap(True)
        title.setStyleSheet(f"""
            color: {p.text_primary}; font-size: 12px; font-weight: 600;
            font-family: '{_FONT}'; background: transparent;
        """)
        root.addWidget(title)

        reason = QLabel(self._s.reasoning)
        reason.setWordWrap(True)
        reason.setStyleSheet(f"""
            color: {p.text_secondary}; font-size: 11px;
            font-family: '{_FONT}'; background: transparent;
        """)
        root.addWidget(reason)

        footer = QHBoxLayout()
        footer.setSpacing(8)

        cf_w = QWidget()
        cf_w.setStyleSheet("background: transparent;")
        cf_vl = QVBoxLayout(cf_w)
        cf_vl.setContentsMargins(0, 0, 0, 0)
        cf_vl.setSpacing(2)

        cf_lbl = QLabel(
            f"{self._s.confidence_label.upper()}  {int(self._s.confidence * 100)}%"
        )
        cf_lbl.setStyleSheet(
            f"color: {conf_col}; font-size: 9px; font-family: '{_FONT}';"
            " background: transparent;"
        )

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(self._s.confidence * 100))
        bar.setFixedHeight(3)
        bar.setTextVisible(False)
        bar.setStyleSheet(f"""
            QProgressBar {{ background: {p.border_subtle}; border: none; border-radius: 1px; }}
            QProgressBar::chunk {{ background: {conf_col}; border-radius: 1px; }}
        """)

        cf_vl.addWidget(cf_lbl)
        cf_vl.addWidget(bar)
        footer.addWidget(cf_w, 1)

        btn = QPushButton("+ Add")
        btn.setFixedSize(52, 24)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {p.accent}; color: {p.text_inverse};
                border: none; border-radius: 4px;
                font-size: 10px; font-weight: 600; font-family: '{_FONT}';
            }}
            QPushButton:hover  {{ background: {p.accent_hover}; }}
            QPushButton:pressed {{ background: {p.accent_pressed}; }}
        """)
        btn.clicked.connect(self._clicked)
        footer.addWidget(btn)
        root.addLayout(footer)

    def _clicked(self):
        """Hand the suggestion to the panel and flash the card as feedback."""
        self._on_add(self._s)
        p = _theme.palette
        orig = self.styleSheet()
        self.setStyleSheet(
            orig.replace(
                f"background: {p.bg_secondary}",
                f"background: {p.bg_selected}",
            )
        )
        QTimer.singleShot(450, lambda: self.setStyleSheet(orig))


# ──────────────────────────────────────────────────────────────────────────────
# The integrated panel
# ──────────────────────────────────────────────────────────────────────────────

class SmartInsightsPanel(QWidget):
    """Resizable pane holding the suggestion cards.

    Embedded as the rightmost pane of the canvas splitter and hidden by default,
    toggled by the button from :func:`make_insights_toggle_button`.

    Analysis runs on a background worker and refreshes when the panel becomes
    visible or when the user presses the re-analyse button. Because the scope
    follows the canvas selection, selecting a different sample node updates the
    header strip immediately, though it does not re-run the analysis on its own.

    Use :func:`integrate_insights_panel` to construct and attach one rather than
    instantiating this directly.
    """

    def __init__(self, scene, parent_window, parent=None):
        """Build the panel and subscribe it to theme and selection changes.

        Args:
            scene: The canvas scene to analyse and watch for selection changes.
            parent_window: Main window holding the loaded particle data.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._scene = scene
        self._pw = parent_window
        self._worker: _AnalysisWorker | None = None
        self._suggestions: list[Suggestion] = []
        self._scope: AnalysisScope | None = None
        self._retired: list[_AnalysisWorker] = []
        self._active_category: str | None = None
        self._results: dict[tuple[str, str], list[Suggestion]] = {}
        self.setMinimumWidth(250)

        self._build_ui()
        self._apply_theme()
        self._theme_dc = _theme.connect_theme(lambda _: self._apply_theme())

        try:
            scene.node_selection_changed.connect(self._on_scene_selection)
        except Exception:
            _itk_log.debug("[Insights] scene has no node_selection_changed signal")


    def _build_ui(self):
        """Assemble the header, sample strip, card scroll area and footer."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._hdr = QFrame()
        self._hdr.setObjectName("iHdr")
        self._hdr.setFixedHeight(52)
        hl = QHBoxLayout(self._hdr)
        hl.setContentsMargins(12, 0, 8, 0)
        hl.setSpacing(6)

        self._title_lbl = QLabel("✦  Insights")
        self._title_lbl.setObjectName("iTitleLbl")

        self._count_lbl = QLabel("")
        self._count_lbl.setObjectName("iCountLbl")

        tleft = QVBoxLayout()
        tleft.setSpacing(1)
        tleft.addWidget(self._title_lbl)
        tleft.addWidget(self._count_lbl)

        self._refresh_btn = QPushButton("↺")
        self._refresh_btn.setObjectName("iRefreshBtn")
        self._refresh_btn.setFixedSize(26, 26)
        self._refresh_btn.setToolTip("Re-analyse")
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.clicked.connect(self.refresh)

        hl.addLayout(tleft)
        hl.addStretch()
        hl.addWidget(self._refresh_btn)
        root.addWidget(self._hdr)

        self._strip = QFrame()
        self._strip.setObjectName("iStrip")
        self._strip.setFixedHeight(26)
        sl = QHBoxLayout(self._strip)
        sl.setContentsMargins(12, 0, 12, 0)
        self._sample_lbl = QLabel("")
        self._sample_lbl.setObjectName("iSampleLbl")
        sl.addWidget(self._sample_lbl)
        root.addWidget(self._strip)

        self._chips_frame = QFrame()
        self._chips_frame.setObjectName("iChips")
        chip_grid = QGridLayout(self._chips_frame)
        chip_grid.setContentsMargins(8, 8, 8, 8)
        chip_grid.setHorizontalSpacing(6)
        chip_grid.setVerticalSpacing(6)

        self._chips: dict[str, QPushButton] = {}
        for i, key in enumerate(category_keys()):
            meta = _CAT_META[key]
            chip = QPushButton(f"{meta['icon']}  {meta['label']}")
            chip.setObjectName("iChip")
            chip.setCheckable(True)
            chip.setCursor(Qt.PointingHandCursor)
            chip.setFixedHeight(26)
            chip.setToolTip(f"Scan for {meta['label'].lower()} insights")
            chip.clicked.connect(lambda _checked=False, k=key: self.run_category(k))
            chip_grid.addWidget(chip, i // 2, i % 2)
            self._chips[key] = chip
        root.addWidget(self._chips_frame)

        self._bar = QProgressBar()
        self._bar.setObjectName("iBar")
        self._bar.setRange(0, 0)
        self._bar.setFixedHeight(2)
        self._bar.setTextVisible(False)
        self._bar.setVisible(False)
        root.addWidget(self._bar)

        self._status = QLabel("")
        self._status.setObjectName("iStatus")
        self._status.setAlignment(Qt.AlignCenter)
        root.addWidget(self._status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._card_w = QWidget()
        self._card_w.setObjectName("iCardW")
        self._card_layout = QVBoxLayout(self._card_w)
        self._card_layout.setContentsMargins(8, 8, 8, 8)
        self._card_layout.setSpacing(6)
        self._card_layout.addStretch()
        scroll.setWidget(self._card_w)
        root.addWidget(scroll, 1)

        self._ftr = QFrame()
        self._ftr.setObjectName("iFtr")
        self._ftr.setFixedHeight(24)
        fl = QHBoxLayout(self._ftr)
        fl.setContentsMargins(12, 0, 12, 0)
        self._hint_lbl = QLabel("+ Add auto-connects and pre-configures the node")
        self._hint_lbl.setObjectName("iHintLbl")
        fl.addStretch()
        fl.addWidget(self._hint_lbl)
        root.addWidget(self._ftr)

    def _apply_theme(self):
        """Restyle the panel chrome from the current theme palette."""
        p = _theme.palette
        self.setStyleSheet(f"""
            SmartInsightsPanel {{
                background: {p.bg_primary};
                border-left: 1px solid {p.border};
            }}
            QFrame#iHdr {{
                background: {p.bg_secondary};
                border-bottom: 1px solid {p.border};
            }}
            QFrame#iChips {{
                background: {p.bg_secondary};
                border-bottom: 1px solid {p.border};
            }}
            QPushButton#iChip {{
                background: {p.bg_primary}; color: {p.text_secondary};
                border: 1px solid {p.border_subtle}; border-radius: 13px;
                padding: 0 10px; font-size: 10px; font-weight: 600;
                font-family: '{_FONT}'; text-align: left;
            }}
            QPushButton#iChip:hover {{
                background: {p.bg_hover}; color: {p.text_primary};
                border-color: {p.border};
            }}
            QPushButton#iChip:checked {{
                background: {p.accent_soft}; color: {p.accent};
                border: 1px solid {p.accent};
            }}
            QPushButton#iChip:disabled {{
                color: {p.disabled}; border-color: {p.border_subtle};
                background: transparent;
            }}
            QFrame#iStrip {{
                background: {p.bg_tertiary};
                border-bottom: 1px solid {p.border_subtle};
            }}
            QFrame#iFtr {{
                background: {p.bg_secondary};
                border-top: 1px solid {p.border};
            }}
            QLabel#iTitleLbl {{
                color: {p.text_primary}; font-size: 13px; font-weight: 700;
                font-family: '{_FONT}'; background: transparent;
            }}
            QLabel#iCountLbl {{
                color: {p.text_muted}; font-size: 10px;
                font-family: '{_FONT}'; background: transparent;
            }}
            QLabel#iSampleLbl {{
                color: {p.text_secondary}; font-size: 10px;
                font-family: '{_FONT}'; background: transparent;
            }}
            QLabel#iStatus {{
                color: {p.text_muted}; font-size: 10px;
                font-family: '{_FONT}'; background: transparent; padding: 2px;
            }}
            QLabel#iHintLbl {{
                color: {p.text_muted}; font-size: 9px;
                font-family: '{_FONT}'; background: transparent;
            }}
            QPushButton#iRefreshBtn {{
                background: transparent; color: {p.text_muted};
                border: 1px solid {p.border}; border-radius: 4px;
                font-size: 13px;
            }}
            QPushButton#iRefreshBtn:hover {{
                color: {p.text_primary}; border-color: {p.accent};
            }}
            QProgressBar#iBar {{
                background: {p.bg_secondary}; border: none;
            }}
            QProgressBar#iBar::chunk {{ background: {p.accent}; }}
            QWidget#iCardW {{ background: transparent; }}
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                background: {p.bg_secondary}; width: 5px; border-radius: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {p.border}; border-radius: 2px; min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {p.text_muted}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        if self._suggestions:
            self._rebuild_cards()

    def run_category(self, key: str, force: bool = False):
        """Scan one category of insights and show the result.

        Nothing is computed until this is called, which is what keeps opening
        the panel free. Results are remembered per scope and category, so
        returning to a category already scanned is instant. Any run still in
        flight is cancelled first, so clicking through several chips quickly
        cannot leave an older worker delivering into the panel.

        Args:
            key: Category to run, from :func:`category_keys`.
            force: Discard any remembered result and rescan.
        """
        scope = resolve_scope(self._scene, self._pw)
        if self._scope is None or scope.key != self._scope.key:
            self._forget_results()
        self._scope = scope
        self._active_category = key

        self._update_sample_strip(scope)
        self._sync_chips(scope)
        self._stop_worker()
        self._clear_cards()

        if not scope.sample_names:
            self._bar.setVisible(False)
            self._status.setText("")
            self._count_lbl.setText("")
            self._show_empty()
            return

        remembered = self._results.get((scope.key, key))
        if remembered is not None and not force:
            self._on_done(remembered, remember=False)
            return

        self._bar.setVisible(True)
        self._bar.setRange(0, 0)
        self._refresh_btn.setEnabled(False)
        self._count_lbl.setText("")

        particles, sample_idx = gather_scope_data(self._scene, self._pw, scope)
        self._worker = _AnalysisWorker(scope, particles, sample_idx, categories=[key])
        self._worker.progress.connect(self._status.setText)
        self._worker.results_ready.connect(self._on_done)
        self._worker.start()

    def refresh(self):
        """Rescan the active category, discarding anything remembered.

        With no category active there is nothing to rescan, so this just brings
        the scope display up to date.
        """
        active = self._active_category
        self._forget_results()
        invalidate_context_cache()
        self._scope = resolve_scope(self._scene, self._pw)
        self._update_sample_strip(self._scope)
        self._sync_chips(self._scope)

        if active:
            self.run_category(active, force=True)
        else:
            self._clear_cards()
            self._show_idle()

    def _forget_results(self):
        """Drop remembered results and reset the chips to their idle labels."""
        self._results.clear()
        self._active_category = None
        for key, chip in self._chips.items():
            meta = _CAT_META[key]
            chip.setText(f"{meta['icon']}  {meta['label']}")
            chip.setChecked(False)

    def _sync_chips(self, scope: AnalysisScope | None = None):
        """Update which chip reads as active and which are worth offering.

        Comparison is disabled for a single-sample scope, where it has nothing
        to compare.

        Args:
            scope: Scope the chips describe. Resolved when omitted.
        """
        if scope is None:
            scope = resolve_scope(self._scene, self._pw)
        for key, chip in self._chips.items():
            chip.setChecked(key == self._active_category)
            if key == "comparison":
                chip.setEnabled(scope.is_multi)
                chip.setToolTip(
                    "Compare samples" if scope.is_multi
                    else "Needs more than one sample in scope"
                )

    def _on_scene_selection(self, *_):
        """React to the canvas selection changing the scope.

        The strip and chips update immediately; the cards do not, since nothing
        rescans until a category is clicked. When the scope has genuinely moved
        the remembered results are dropped, because they describe other samples.
        """
        if not self.isVisible():
            return
        scope = resolve_scope(self._scene, self._pw)
        if self._scope is not None and scope.key != self._scope.key:
            self._stop_worker()
            self._forget_results()
            self._clear_cards()
            self._count_lbl.setText("")
            self._show_idle()
        self._scope = scope
        self._update_sample_strip(scope)
        self._sync_chips(scope)

    def _stop_worker(self):
        """Cancel any in-flight analysis and stop listening to it.

        Disconnecting matters as much as cancelling: a worker that has already
        passed its last abort check will still emit, and without this it would
        deliver results for the previous scope into the current panel.

        A cancelled worker is held in ``_retired`` until its thread actually
        exits, because letting a running ``QThread`` be garbage collected
        crashes the interpreter.
        """
        w = self._worker
        if w is None:
            return
        try:
            w.progress.disconnect()
            w.results_ready.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._worker = None
        if w.isRunning():
            w.cancel()
            self._retired.append(w)
            w.finished.connect(lambda: self._retired.remove(w)
                               if w in self._retired else None)

    def _update_sample_strip(self, scope: AnalysisScope | None = None):
        """Show which samples will be analysed, and why those.

        Naming the origin matters because the scope is implicit: without it
        there is no way to tell a deliberate single-sample scope from an
        accidental one.

        Args:
            scope: Scope to describe. Resolved from the scene when omitted.
        """
        if scope is None:
            scope = resolve_scope(self._scene, self._pw)
        names = list(scope.sample_names)
        if not names:
            self._sample_lbl.setText("No samples loaded")
            return
        text = "  ·  ".join(names[:4])
        if len(names) > 4:
            text += f"  +{len(names)-4} more"
        self._sample_lbl.setText(
            f"📂  {text}   ({scope.total_particles:,} particles · {scope.origin_label})"
        )

    def _on_done(self, suggestions: list[Suggestion], remember: bool = True):
        """Render a finished scan and record its result on the chip.

        Args:
            suggestions: Cards to display, or an empty list if the scan found
                nothing worth surfacing.
            remember: Store the result against the current scope and category.
                False when replaying something already remembered.
        """
        self._bar.setVisible(False)
        self._status.setText("")
        self._refresh_btn.setEnabled(True)
        self._suggestions = suggestions

        key = self._active_category
        if remember and key and self._scope is not None:
            self._results[(self._scope.key, key)] = suggestions

        if key and key in self._chips:
            meta = _CAT_META[key]
            count = len(suggestions)
            self._chips[key].setText(
                f"{meta['icon']}  {meta['label']}   {count}" if count
                else f"{meta['icon']}  {meta['label']}   –"
            )

        n = len(suggestions)
        self._count_lbl.setText(
            f"{n} insight{'s' if n != 1 else ''}" if n else "Nothing found"
        )
        self._rebuild_cards() if suggestions else self._show_empty()

    def _rebuild_cards(self):
        """Replace the card list with one card per current suggestion."""
        self._clear_cards()
        for s in self._suggestions:
            card = _Card(s, on_add=self._add_suggestion)
            self._card_layout.insertWidget(self._card_layout.count() - 1, card)

    def _empty_message(self) -> str:
        """Explain why a scan produced no cards.

        Distinguishes the three cases that would otherwise look identical: no
        data loaded at all, data too sparse to analyse, and a scan that ran
        properly but found nothing strong enough to report.

        Returns:
            A two-line message for the empty-state label.
        """
        scope = self._scope
        if scope is None or not scope.sample_names:
            return "No sample data loaded.\nLoad a sample to generate insights."
        if scope.total_particles < 5:
            return (
                f"Only {scope.total_particles} particle(s) in "
                f"{scope.origin_label}.\nToo few to analyse."
            )
        label = (_CAT_META.get(self._active_category or "", {})
                 .get("label", "This scan").lower())
        return (
            f"Scanned {scope.total_particles:,} particles across "
            f"{len(scope.sample_names)} sample(s).\n"
            f"Nothing stood out under {label}."
        )

    def _idle_message(self) -> str:
        """Describe what a scan would cover, before any category is picked.

        Returns:
            A two-line prompt for the idle-state label.
        """
        scope = self._scope
        if scope is None or not scope.sample_names:
            return "No sample data loaded.\nLoad a sample to generate insights."
        return (
            f"{scope.total_particles:,} particles across "
            f"{len(scope.sample_names)} sample(s) in scope.\n"
            "Pick a category above to scan them."
        )

    def _show_empty(self):
        """Display the empty-state message in place of the cards."""
        self._show_placeholder(self._empty_message())

    def _show_idle(self):
        """Display the idle prompt shown before anything has been scanned."""
        self._show_placeholder(self._idle_message())

    def _show_placeholder(self, text: str):
        """Put a centred muted message where the cards would go.

        Args:
            text: Message to display.
        """
        p = _theme.palette
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color: {p.text_muted}; font-size: 11px; font-family: '{_FONT}';"
            " padding: 24px; background: transparent;"
        )
        self._card_layout.insertWidget(self._card_layout.count() - 1, lbl)

    def _clear_cards(self):
        """Remove every card, leaving the trailing stretch in place."""
        while self._card_layout.count() > 1:
            item = self._card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_suggestion(self, s: Suggestion):
        """Build the branch a suggestion describes and wire it into the canvas.

        Where the insight names the elements it is about, a fresh sample
        selector is created for the same samples but narrowed to just those
        elements, and the plot node hangs off that. This is what lets a card
        for an element the user never selected still produce a working branch,
        and it keeps the new branch carrying only the relevant data.

        Insights that need the full element set to mean anything, such as the
        composition breakdown, name no elements and simply attach to the
        existing source node instead.

        Args:
            s: The suggestion whose Add button was pressed.
        """
        try:
            from widget.canvas_widgets import _NODE_FACTORIES
        except ImportError:
            _itk_log.exception("[Insights] Could not import _NODE_FACTORIES")
            self._flash_status("Could not reach the node factory")
            return

        factory = _NODE_FACTORIES.get(s.node_type)
        if factory is None:
            _itk_log.error(f"[Insights] Unknown node_type: {s.node_type}")
            self._flash_status(f"No node type '{s.node_type}'")
            return

        scene = self._scene
        plot_node = factory(self._pw)
        if s.config and isinstance(getattr(plot_node, "config", None), dict):
            plot_node.config.update(s.config)

        selector = self._build_scoped_selector(s, _NODE_FACTORIES)
        source = selector or _find_source_node(scene)

        existing = len(scene.workflow_nodes)
        base = QPointF(300 + existing * 12, 200 + existing * 12)
        if selector is None and source is not None:
            item = scene.node_items.get(source)
            if item is not None:
                base = QPointF(item.pos().x() + 220 + (existing % 3) * 8,
                               item.pos().y() + (existing // 3) * 130)

        if selector is not None:
            scene.add_node(selector, base)
            upstream = _find_batch_node(scene)
            if upstream is not None:
                scene.add_link(upstream, "output", selector, "input")
            base = QPointF(base.x() + 220, base.y())

        scene.add_node(plot_node, base)
        if source is not None and getattr(source, "_has_output", False):
            scene.add_link(source, "output", plot_node, "input")

        if selector is not None:
            self._flash_status(
                f"Added {len(s.elements)}-element selector + plot"
            )

    def _build_scoped_selector(self, s: Suggestion, factories: dict):
        """Create a sample selector holding the insight's elements only.

        The selector covers the same samples the insight was computed over, so
        the new branch says the same thing the card does. Its type follows the
        scope: a single-sample scope gets a single selector, several samples get
        a multi-sample one with every sample included.

        Args:
            s: The suggestion being added.
            factories: The canvas node factory mapping.

        Returns:
            The configured selector node, or ``None`` when the suggestion names
            no elements, no scope is known, or the elements cannot be resolved
            to isotopes the selector would understand.
        """
        scope = self._scope
        if not s.elements or scope is None or not scope.sample_names:
            return None

        entries = _isotope_entries(self._pw, self._scene, s.elements)
        if not entries:
            _itk_log.warning(
                f"[Insights] could not resolve isotopes for {list(s.elements)}; "
                "falling back to the existing source node"
            )
            self._flash_status("Could not scope elements — using existing node")
            return None

        node_type = ("multiple_sample_selector" if scope.is_multi
                     else "sample_selector")
        factory = factories.get(node_type)
        if factory is None:
            return None

        selector = factory(self._pw)
        selector.selected_isotopes = entries

        if scope.is_multi:
            selector.selected_samples = list(scope.sample_names)
            selector.sample_config = {
                name: {"included": True, "sum_group": "", "custom_name": name}
                for name in scope.sample_names
            }
        else:
            selector.selected_sample = scope.sample_names[0]

        title = getattr(selector, "title", None)
        if isinstance(title, str):
            selector.title = f"{', '.join(s.elements[:3])}"
        return selector

    def _flash_status(self, message: str, msec: int = 2600):
        """Show a transient message in the status line.

        Args:
            message: Text to show.
            msec: How long to leave it up.
        """
        self._status.setText(message)
        QTimer.singleShot(msec, lambda: (
            self._status.setText("") if self._status.text() == message else None
        ))


    def showEvent(self, event):
        """Show what is in scope without analysing anything.

        Opening the panel costs nothing: the scope strip and chips update, and
        the first scan waits for the user to choose a category.
        """
        super().showEvent(event)
        QTimer.singleShot(0, self._show_scope_only)

    def _show_scope_only(self):
        """Refresh the scope display and prompt for a category."""
        self._scope = resolve_scope(self._scene, self._pw)
        self._update_sample_strip(self._scope)
        self._sync_chips(self._scope)
        if self._active_category is None:
            self._clear_cards()
            self._show_idle()

    def closeEvent(self, event):
        """Release resources if the panel is ever closed directly."""
        self._teardown()
        super().closeEvent(event)

    def _teardown(self):
        """Drop the theme subscription and stop any running analysis.

        Safe to call more than once, since it may arrive from either the panel
        closing or the parent dialog finishing.
        """
        if getattr(self, "_torn_down", False):
            return
        self._torn_down = True
        try:
            self._theme_dc()
        except Exception:
            _itk_log.exception("[Insights] theme disconnect failed")
        self._stop_worker()


# ──────────────────────────────────────────────────────────────────────────────
# Integration helpers — call from CanvasResultsDialog._build()
# ──────────────────────────────────────────────────────────────────────────────

def integrate_insights_panel(canvas_dialog, splitter: QSplitter) -> SmartInsightsPanel:
    """Append a :class:`SmartInsightsPanel` as the rightmost pane of *splitter*.

    The panel starts hidden. Teardown is hung off the dialog's ``finished``
    signal, because a widget inside a splitter never receives ``closeEvent``
    and the theme subscription would otherwise outlive the panel.

    Call from ``CanvasResultsDialog._build()`` after the splitter has its
    palette and canvas panes::

        self.insights_panel = integrate_insights_panel(self, splitter)
        splitter.setSizes([240, 820, 0])

        self._insights_btn = make_insights_toggle_button(self, splitter)
        hl.addWidget(self._insights_btn)

    Args:
        canvas_dialog: The dialog owning the canvas and splitter.
        splitter: Splitter to append the panel to.

    Returns:
        The panel, also assign it to ``canvas_dialog.insights_panel`` so the
        toggle button can find it.
    """
    panel = SmartInsightsPanel(
        scene=canvas_dialog.canvas.scene,
        parent_window=canvas_dialog.parent,
        parent=canvas_dialog,
    )
    panel.setVisible(False)
    splitter.addWidget(panel)

    if hasattr(canvas_dialog, "finished"):
        canvas_dialog.finished.connect(lambda *_: panel._teardown())
    return panel


def make_insights_toggle_button(canvas_dialog, splitter: QSplitter) -> QPushButton:
    """Create the header button that shows and hides the insights panel.

    The button label reflects the current state, and the panel's last width is
    remembered so reopening restores it rather than snapping to a default.

    Args:
        canvas_dialog: The dialog holding ``insights_panel``.
        splitter: The splitter the panel lives in.

    Returns:
        The toggle button, ready to add to the header layout.
    """

    def _toggle():
        """Show or hide the panel, resizing the splitter to match."""
        panel = canvas_dialog.insights_panel
        sizes = splitter.sizes()
        if panel.isVisible():
            canvas_dialog._insights_prev_w = sizes[-1] or 300
            panel.setVisible(False)
            btn.setText("✦  Insights")
            btn.setToolTip("Open Insights")
        else:
            panel.setVisible(True)
            w = getattr(canvas_dialog, "_insights_prev_w", 300)
            new_sizes = list(sizes)
            new_sizes[-1] = w
            new_sizes[-2] = max(100, new_sizes[-2] - w)
            splitter.setSizes(new_sizes)
            btn.setText("✦  Insights  ‹")
            btn.setToolTip("Close Insights")

    def _style():
        """Apply the current theme palette to the button."""
        p = _theme.palette
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {p.accent_soft}; color: {p.accent};
                border: 1px solid {p.accent}; border-radius: 6px;
                padding: 0 14px; font-size: 11px; font-weight: 700;
                font-family: '{_FONT}';
            }}
            QPushButton:hover {{
                background: {p.accent_hover}; color: {p.text_inverse};
            }}
            QPushButton:pressed {{
                background: {p.accent_pressed}; color: {p.text_inverse};
            }}
        """)

    btn = QPushButton("✦  Insights")
    btn.setFixedHeight(30)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setToolTip("Open Insights")
    _style()
    _theme.connect_theme(lambda _: _style())
    btn.clicked.connect(_toggle)
    return btn