"""The Insights engine: what to search, and the detectors that search it.

The pipeline has four stages:

``resolve_scope``
    Collects every loaded sample and works out its replicate groups (see
    :mod:`results.insights.replicates`). Canvas selection and element choices
    are never consulted, so a finding can surface anywhere.

``gather_scope_data``
    Collects the raw particle dicts for that scope. Cheap enough for the GUI
    thread, which keeps the scene off the worker thread entirely.

``build_context_from``
    Turns those particles into an :class:`AnalysisContext`: the element
    matrix, detection masks and per-sample index every detector shares.
    Results are cached by scope fingerprint.

``_AnalysisWorker``
    Runs the detectors on a background thread, per replicate group where a
    detector looks inside one material, and emits :class:`Suggestion` objects.

The panel that shows the suggestions lives in :mod:`results.insights.panel`;
the extra detectors in :mod:`results.insights.discovery`.
"""

from __future__ import annotations
import copy
import math
import warnings
import re
import threading
from dataclasses import dataclass, field
import numpy as np
from scipy import stats as _stats
from PySide6.QtCore import QThread, Signal

from results.insights import discovery as _disc
from results.insights.replicates import (
    ReplicateGroup, describe_grouping, resolve_groups, user_group_map,
)
import logging
_itk_log = logging.getLogger("IsotopeTrack.results.insights")

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
    "signature":    {"icon": "⌘", "label": "Signature"},
    "outlier":      {"icon": "↑", "label": "Outlier"},
    "interference": {"icon": "⚡", "label": "Interference"},
    "stoichiometry": {"icon": "⚖", "label": "Stoichiometry"},
    "cooccurrence": {"icon": "⊕", "label": "Co-occurrence"},
    "rare":         {"icon": "✧", "label": "Rare find"},
    "quality":      {"icon": "⚠", "label": "Data quality"},
    "time":         {"icon": "⏱", "label": "Time"},
    "replicate":    {"icon": "≡", "label": "Replicates"},
    "network":      {"icon": "⋈", "label": "Network"},
    "ternary":      {"icon": "△", "label": "Ternary"},
    "single_multi": {"icon": "◐", "label": "Single vs multiple"},
    "size":         {"icon": "⤢", "label": "Size trend"},
    "isotope_groups": {"icon": "⚛", "label": "Isotope ratio between groups"},
    "types":        {"icon": "◈", "label": "Particle types"},
}

NODE_TYPE_META: dict[str, str] = {
    "correlation_plot": "Correlation",
    "correlation_matrix": "Correlation matrix",
    "network_diagram": "Network",
    "isotopic_ratio_plot": "Isotopic ratio",
    "molar_ratio_plot": "Molar ratio",
    "histogram_plot": "Histogram",
    "box_plot": "Box plot",
    "concentration_comparison": "Concentration",
    "heatmap_plot": "Heatmap",
    "element_bar_chart_plot": "Element bar chart",
    "pie_chart_plot": "Pie chart",
    "element_composition_plot": "Element composition",
    "triangle_plot": "Ternary",
    "single_multiple_element_plot": "Single vs multiple",
    "figure_builder": "Figure Builder",
}
"""Plot nodes Insights can propose, in the order the panel lists them.

The Clustering node is not proposed. Particle types are found inside Insights
with strict checks (see :func:`results.insights.discovery.find_particle_types`)
and shown in a Figure Builder figure; exploring them further is the
Clustering node's job.
"""

MIN_CORR_OVERLAP = 25
"""Co-detected particles a pair needs before its correlation is reported."""

FDR_Q = 0.05
"""Target false discovery rate for the pairwise correlation family."""

MIN_ABS_CORRELATION = 0.50
"""Effect-size floor, applied on top of significance, for a correlation card."""

MAX_CORRELATION_CARDS = 4
"""Most correlation pairs to surface from one scan."""

_DATA_KEY_LABELS: dict[str, str] = {
    "elements": "Counts",
    "element_mass_fg": "Element Mass (fg)",
    "particle_mass_fg": "Particle Mass (fg)",
    "element_moles_fmol": "Element Moles (fmol)",
    "particle_moles_fmol": "Particle Moles (fmol)",
    "element_diameter_nm": "Element Diameter (nm)",
    "particle_diameter_nm": "Particle Diameter (nm)",
}
"""Measurement keys mapped to the display names the plot nodes expect."""

_DATA_KEY_UNITS: dict[str, str] = {
    "elements": "counts",
    "element_mass_fg": "fg",
    "particle_mass_fg": "fg",
    "element_moles_fmol": "fmol",
    "particle_moles_fmol": "fmol",
    "element_diameter_nm": "nm",
    "particle_diameter_nm": "nm",
}
"""Short unit suffixes for writing measured values into card text."""

_DATA_KEY_NOUNS: dict[str, str] = {
    "elements": "intensity",
    "element_mass_fg": "mass",
    "particle_mass_fg": "particle mass",
    "element_moles_fmol": "molar",
    "particle_moles_fmol": "particle molar",
    "element_diameter_nm": "size",
    "particle_diameter_nm": "particle size",
}
"""How to name each measurement in a sentence."""

BIMODALITY_SCAN_ORDER = (
    "element_diameter_nm",
    "particle_diameter_nm",
    "element_mass_fg",
    "particle_mass_fg",
    "elements",
)
"""Units searched for split distributions, most physically meaningful first.

Size leads because two size populations is the clearest result to act on, then
mass, then raw counts as a fallback when nothing has been calibrated.
"""

MIN_BIMODALITY_PARTICLES = 60
"""Particles an element needs before its distribution shape is worth testing."""

BIMODALITY_KDE_SAMPLE = 4000
"""Most values the density curve is fitted to; larger sets are subsampled.

Locating two modes needs a few thousand values at most, and fitting the curve
to every particle of a large run costs seconds for no change in the answer.
The subsample is drawn with a fixed seed, so a scan always gives the same
result.
"""

MIN_MODE_SEPARATION = 0.30
"""Minimum gap between two modes, in log10 units, so about a factor of two."""

MIN_MINOR_MODE_SHARE = 0.10
"""Smallest share of particles the lesser mode must hold to count as real."""

MIN_VALLEY_DEPTH = 0.40
"""How far the dip between two modes must fall below the lower peak."""

MAX_BIMODALITY_CARDS = 3
"""Most split-distribution cards to surface from one scan."""

SIGNATURE_ABSENCE_RATIO = 0.30
"""How rare a feature must be elsewhere before it counts as a fingerprint.

Present in 40% of one sample and 30% of another is a difference in degree, not
a signature. The lesser sample has to hold well under a third of the leader's
rate before a finding is worded as belonging to one sample.
"""

SIGNATURE_MIN_COMBO_GAP = 0.12
"""Smallest share difference for an element combination to be worth reporting."""

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
        samples: The samples where the finding holds. Adding the card builds a
            selector over these samples only. Empty means every sample in scope.
        sample_groups: Sample to replicate group label for *samples*. A label
            makes the new selector pool that sample with the rest of its group;
            an empty label keeps it separate, as replicate checks need.
        explain_key: Which explanation in :mod:`results.insights.explain`
            describes this finding; the category when empty.
        details: ``(label, value)`` pairs with the numbers behind the finding,
            shown in the card's details section.
    """

    title: str
    reasoning: str
    category: str
    confidence: float
    node_type: str
    config: dict = field(default_factory=dict)
    elements: tuple[str, ...] = ()
    samples: tuple[str, ...] = ()
    sample_groups: dict = field(default_factory=dict)
    explain_key: str = ""
    details: list = field(default_factory=list)

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
    particles: list[dict], data_key: str = "elements",
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Build the element matrix in a single sparse pass.

    Only the elements each particle actually carries are visited, rather than
    every element for every particle, which matters because most particles
    carry a small fraction of the elements present across a sample. Numeric
    values are converted on a fast path, with anything exotic (strings,
    ``Decimal``, ``None``) falling back to :func:`_safe_float`.

    Args:
        particles: Particle dicts, each optionally holding a mapping of element
            label to measured value under *data_key*.
        data_key: Which measurement to read, such as ``"elements"`` for raw
            counts or ``"element_diameter_nm"`` for size.

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
        for el, raw in (p.get(data_key) or {}).items():
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


def _fmt_q(q: float) -> str:
    """Write a corrected p-value for a card, without printing a bare zero.

    Args:
        q: The adjusted p-value.

    Returns:
        Text such as ``"q = 0.003"`` or ``"q < 1e-300"``.
    """
    if not np.isfinite(q) or q <= 0:
        return "q < 1e-300"
    return f"q = {q:.2g}"


def correlated_pairs(ctx, elements) -> list[tuple[str, str, dict]]:
    """Correlate every pair of *elements*, reusing results already computed.

    The correlation and network detectors both need every pairwise
    correlation; caching them on the context means the work is done once.

    Args:
        ctx: Analysis context.
        elements: Element labels, in the order pairs should be listed.

    Returns:
        ``(a, b, stats)`` for every pair with enough co-detections, in the
        order the elements were given.
    """
    cache = ctx.cache.setdefault("pair_stats", {})
    out = []
    for i in range(len(elements)):
        for j in range(i + 1, len(elements)):
            a, b = elements[i], elements[j]
            key = (a, b)
            if key not in cache:
                cache[key] = _correlate_pair(ctx.matrix[a], ctx.matrix[b])
            if cache[key] is not None:
                out.append((a, b, cache[key]))
    return out


def _proportionality(a: np.ndarray, b: np.ndarray) -> float | None:
    """Measure how close two elements are to a fixed ratio.

    Uses the proportionality coefficient of Lovell et al. (2015) on log values
    of particles carrying both elements: one minus the variance of the log
    ratio over the summed variances of the two logs. It is 1 for a perfectly
    fixed ratio and falls towards 0, or below, when the elements merely rise
    together, as any two elements do in particles of varying size.

    Args:
        a: Concentration array for the first element.
        b: Concentration array for the second element, aligned to *a*.

    Returns:
        The coefficient, or ``None`` with fewer than ten co-detections or no
        variation.
    """
    both = (a > 0) & (b > 0)
    if int(both.sum()) < 10:
        return None
    la, lb = np.log10(a[both]), np.log10(b[both])
    denominator = float(la.var() + lb.var())
    if denominator <= 1e-12:
        return None
    return float(1.0 - (la - lb).var() / denominator)


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


def _bimodality_coefficient(values: np.ndarray) -> float:
    """Score how two-humped a distribution looks, from skewness and kurtosis.

    Values above about 0.555, the figure for a uniform distribution, suggest
    two populations rather than one. This is only a prefilter: it is cheap
    enough to run on every element, but a heavy tail can push it up on its own,
    so anything it flags is confirmed by :func:`_detect_bimodality`.

    The kurtosis term is *excess* kurtosis. Using the raw fourth moment inflates
    the denominator and drives the score below the threshold almost regardless
    of the data, which is a common way to get this formula wrong.

    Args:
        values: Positive measurements for a single element.

    Returns:
        The sample-corrected coefficient, or ``0.0`` when there are too few
        values or no variation at all.
    """
    values = values[values > 0]
    n = len(values)
    if n < 8:
        return 0.0
    std = values.std()
    if std == 0:
        return 0.0

    centred = values - values.mean()
    skew = float(np.mean(centred ** 3)) / (std ** 3 + 1e-30)
    kurtosis = float(np.mean(centred ** 4)) / (std ** 4 + 1e-30) - 3.0
    correction = 3.0 * ((n - 1) ** 2) / ((n - 2) * (n - 3) + 1e-9)
    return (skew ** 2 + 1.0) / (kurtosis + correction)


def _detect_bimodality(values: np.ndarray, min_separation: float = MIN_MODE_SEPARATION
                       ) -> dict | None:
    """Look for two separated populations in one element's measurements.

    The test runs on log10 values, because particle measurements span orders of
    magnitude and a split that is obvious on a log axis is invisible on a
    linear one. A kernel density estimate is evaluated across the range, its
    local maxima are found, and the two tallest are kept.

    Three conditions must all hold before this reports a split, which together
    rule out the long right tail that is normal in this data:

    * the modes sit at least :data:`MIN_MODE_SEPARATION` apart in log10,
    * the dip between them falls at least :data:`MIN_VALLEY_DEPTH` below the
      lower of the two peaks,
    * the smaller population holds at least :data:`MIN_MINOR_MODE_SHARE` of the
      particles.

    Args:
        values: Positive measurements for a single element.
        min_separation: Smallest gap between the modes, in log10 units.
            Isotope ratios use a much smaller gap than sizes or masses.

    Returns:
        A dict describing the split, with ``modes`` in the original units,
        ``split`` at the dividing value, ``minor_share``, ``separation``,
        ``valley_depth`` and the prefilter ``bc``. ``None`` when the data is
        too small, too flat, or better described by a single population.
    """
    values = values[values > 0]
    if len(values) < MIN_BIMODALITY_PARTICLES:
        return None

    logged = np.log10(values)
    if logged.std() < 1e-9:
        return None

    bc = _bimodality_coefficient(logged)
    if bc < 0.555:
        return None

    fit_on = logged
    if len(logged) > BIMODALITY_KDE_SAMPLE:
        fit_on = np.random.default_rng(0).choice(logged, BIMODALITY_KDE_SAMPLE, replace=False)
    try:
        density = _stats.gaussian_kde(fit_on)
    except Exception:
        _itk_log.exception("[Insights] KDE failed")
        return None

    grid = np.linspace(logged.min(), logged.max(), 256)
    curve = density(grid)

    peaks = [i for i in range(1, len(curve) - 1)
             if curve[i] > curve[i - 1] and curve[i] >= curve[i + 1]]
    if len(peaks) < 2:
        return None

    peaks.sort(key=lambda i: -curve[i])
    first, second = sorted(peaks[:2])
    lower_peak = min(curve[first], curve[second])
    if lower_peak <= 0:
        return None

    separation = float(grid[second] - grid[first])
    if separation < min_separation:
        return None

    valley_index = first + int(np.argmin(curve[first:second + 1]))
    valley_depth = float(1.0 - curve[valley_index] / lower_peak)
    if valley_depth < MIN_VALLEY_DEPTH:
        return None

    split = float(grid[valley_index])
    below = float(np.mean(logged < split))
    minor_share = min(below, 1.0 - below)
    if minor_share < MIN_MINOR_MODE_SHARE:
        return None

    return {
        "modes": (float(10 ** grid[first]), float(10 ** grid[second])),
        "split": float(10 ** split),
        "minor_share": minor_share,
        "separation": separation,
        "valley_depth": valley_depth,
        "bc": bc,
        "n": int(len(values)),
    }


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
    """Which samples the Insights engine looks at, and how they group.

    Insights always searches every loaded sample and every element, whatever
    is selected on the canvas, so that a finding can surface anywhere. Each
    card then narrows the node it builds to the samples and elements the
    finding is about.

    Attributes:
        sample_names: The samples to analyse, in load order.
        origin: Where the samples came from. ``"all"`` for the loaded pool;
            ``"batch"`` when a batch node supplies them.
        counts: Particle count per entry in *sample_names*, index aligned.
        pool_ids: Identity of each sample's particle list, index aligned. Two
            different datasets can share a name and a particle count, so the
            counts alone are not enough to tell cached contexts apart.
        groups: Replicate groups covering *sample_names*, see
            :mod:`results.insights.replicates`.
    """

    sample_names: tuple[str, ...]
    origin: str
    counts: tuple[int, ...]
    pool_ids: tuple[int, ...] = ()
    groups: tuple[ReplicateGroup, ...] = ()

    @property
    def key(self) -> str:
        """Return the cache fingerprint for this scope.

        Covers the samples, their particle counts, the identity of the
        underlying lists and the replicate grouping, so reloading data or
        regrouping replicates invalidates any context cached against the same
        sample names.
        """
        ids = ",".join(str(i) for i in self.pool_ids)
        grouping = ";".join(f"{g.name}={','.join(g.members)}" for g in self.groups)
        return (f"{self.origin}|{'|'.join(self.sample_names)}|{sum(self.counts)}|{ids}"
                f"|{grouping}")

    @property
    def total_particles(self) -> int:
        """Return the number of particles across every sample in scope."""
        return sum(self.counts)

    @property
    def is_multi(self) -> bool:
        """Return whether the scope spans more than one sample."""
        return len(self.sample_names) > 1

    @property
    def has_several_groups(self) -> bool:
        """Return whether there is more than one group to compare."""
        return len(self.groups) > 1

    @property
    def origin_label(self) -> str:
        """Return a human-readable form of :attr:`origin` for the panel."""
        return {
            "all": "all loaded samples",
            "batch": "batch samples",
        }.get(self.origin, self.origin)

    @property
    def grouping_label(self) -> str:
        """Return a short description of the replicate grouping."""
        return describe_grouping(self.groups)

    def group_of(self, sample: str) -> ReplicateGroup | None:
        """Return the replicate group holding *sample*, if any."""
        for group in self.groups:
            if sample in group.members:
                return group
        return None


def resolve_scope(scene, parent_window) -> AnalysisScope:
    """Collect every loaded sample and work out its replicate groups.

    Canvas selection and the element choices of selector nodes are never
    consulted, so the search always covers everything. Replicate groups come
    from the user's own grouping on the canvas when there is any, and are
    otherwise guessed from sample names.

    Args:
        scene: The canvas scene, read for a batch node and for the user's
            replicate groups.
        parent_window: Main window holding the loaded particle data.

    Returns:
        The resolved scope, with empty ``sample_names`` when nothing is loaded.
    """
    pool = _raw_pool(scene, parent_window)
    origin = "batch" if _find_batch_node(scene) is not None and pool else "all"
    names = [n for n in _dedupe(pool.keys()) if pool.get(n)]
    counts = tuple(len(pool.get(n, ())) for n in names)
    pool_ids = tuple(id(pool.get(n)) for n in names)
    try:
        user_map = user_group_map(scene, names)
    except Exception:
        _itk_log.exception("[Insights] could not read replicate groups")
        user_map = {}
    groups = tuple(resolve_groups(names, user_map))
    return AnalysisScope(tuple(names), origin, counts, pool_ids, groups)


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
        unit_matrices: Matrices for measurements other than raw counts, built
            on first use and keyed by data key. Scanning sizes costs nothing
            until something actually asks for them.
        cache: Scratch space detectors use to share derived arrays, such as
            the number of elements per particle.
        label: Which part of the scope this context covers: empty for the
            whole scope, or a replicate group's name for a group subset.
    """

    scope: AnalysisScope
    particles: list[dict]
    matrix: dict[str, np.ndarray]
    det_mask: dict[str, np.ndarray]
    det_counts: dict[str, int]
    sample_idx: np.ndarray
    unit_matrices: dict = field(default_factory=dict)
    cache: dict = field(default_factory=dict)
    label: str = ""

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

    def matrix_for(self, data_key: str) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
        """Return the matrix and detection mask for one measurement.

        Anything other than raw counts is built the first time it is asked for
        and kept for the life of the context, so a scan that walks several
        units pays for each only once.

        Args:
            data_key: Measurement to read, e.g. ``"element_diameter_nm"``.

        Returns:
            The ``(matrix, det_mask)`` pair for *data_key*.
        """
        if data_key == "elements":
            return self.matrix, self.det_mask
        cached = self.unit_matrices.get(data_key)
        if cached is None:
            cached = _build_matrix(self.particles, data_key)
            self.unit_matrices[data_key] = cached
        return cached

    def available_data_keys(self, sample_size: int = 400) -> list[str]:
        """List the measurements these particles actually carry.

        Which units exist depends on how far the data was calibrated, so this
        looks rather than assumes. Only the first *sample_size* particles are
        inspected, since a key present at all is almost always present broadly.

        Args:
            sample_size: How many particles to inspect.

        Returns:
            Data keys found, in :data:`_DATA_KEY_LABELS` order.
        """
        seen: set[str] = set()
        for p in self.particles[:sample_size]:
            for key in _DATA_KEY_LABELS:
                if key not in seen and p.get(key):
                    seen.add(key)
            if len(seen) == len(_DATA_KEY_LABELS):
                break
        return [k for k in _DATA_KEY_LABELS if k in seen]

    def subset(self, mask: np.ndarray, label: str = "") -> "AnalysisContext":
        """Return a context over the particles where *mask* is true.

        Columns are sliced rather than rebuilt from the particle dicts, and
        elements with no detection left in the subset are dropped.

        Args:
            mask: Boolean array of length ``n``.
            label: Name for the subset, such as a replicate group.

        Returns:
            A new context sharing this one's scope.
        """
        idx = np.flatnonzero(mask)
        matrix, det_mask, det_counts = {}, {}, {}
        for el, column in self.matrix.items():
            detected = self.det_mask[el][idx]
            hits = int(detected.sum())
            if hits:
                matrix[el] = column[idx]
                det_mask[el] = detected
                det_counts[el] = hits
        units = {
            key: ({el: col[idx] for el, col in mat.items()},
                  {el: m[idx] for el, m in msk.items()})
            for key, (mat, msk) in self.unit_matrices.items()
        }
        return AnalysisContext(
            scope=self.scope,
            particles=[self.particles[i] for i in idx],
            matrix=matrix,
            det_mask=det_mask,
            det_counts=det_counts,
            sample_idx=self.sample_idx[idx],
            unit_matrices=units,
            label=label,
        )

    def group_mask(self, group: ReplicateGroup) -> np.ndarray:
        """Mark the particles belonging to the samples of *group*."""
        names = self.sample_names
        indices = [names.index(m) for m in group.members if m in names]
        return np.isin(self.sample_idx, indices)

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

    Every pair of different, sufficiently detected elements is tested, then the
    whole
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
    pairs = [(a, b, res) for a, b, res in correlated_pairs(ctx, els)
             if not _disc.same_element(a, b) and not _disc.interference_pair(ctx, a, b)]

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
            rho_p = _proportionality(ctx.matrix[ea], ctx.matrix[eb]) if rho > 0 else None
            note, penalty = "", 0.0
            if rho_p is not None and rho_p >= 0.75:
                note = (f" Their ratio is nearly constant (proportionality ρp = {rho_p:.2f}), "
                        "consistent with one phase.")
            elif rho_p is not None and rho_p < 0.4:
                note = (f" They are not proportional (ρp = {rho_p:.2f}): the ratio shifts "
                        "with particle size, so the link may be shared size rather than a "
                        "fixed composition.")
                penalty = 0.10
            out.append(Suggestion(
                title=f"{ea} vs {eb}",
                reasoning=(
                    f"{strength} {direction} rank correlation "
                    f"(ρ = {rho:+.2f}, log Pearson r = {res['pearson']:+.2f}). "
                    f"{res['overlap']:,} of {ctx.n:,} particles carry both. "
                    f"{_fmt_q(q_value)} after correcting {len(pairs)} tests.{note}"
                ),
                category="correlation",
                confidence=max(min(abs(rho), 1.0) - penalty, 0.05),
                explain_key="correlation",
                details=[("Rank correlation (ρ)", f"{rho:+.2f}"),
                         ("Pearson on log values (r)", f"{res['pearson']:+.2f}"),
                         ("Proportionality (ρp)", "n/a" if rho_p is None else f"{rho_p:.2f}"),
                         ("Particles with both", f"{res['overlap']:,} of {ctx.n:,}"),
                         ("Pairs tested", str(len(pairs))), ("False discovery", _fmt_q(q_value))],
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
            explain_key="correlation",
            details=[("Elements", ", ".join(els))],
            node_type="correlation_matrix",
            config={},
        ))
    return out


def _analyse_isotope(ctx: AnalysisContext, progress=None) -> list[Suggestion]:
    """Examine isotope ratios within one material.

    Kept under its old name for callers of the earlier engine; the work is
    done by :func:`results.insights.discovery.analyse_isotope_ratios`.
    """
    return _disc.analyse_isotope_ratios(ctx, progress)


def _scan_bimodality(ctx: AnalysisContext, progress=None) -> list[Suggestion]:
    """Look for elements whose measurements fall into two separate populations.

    Units are searched in :data:`BIMODALITY_SCAN_ORDER`, so a split in particle
    size is reported ahead of the same split expressed as mass or raw counts.
    Once an element has been reported in one unit it is not reported again in
    another, since that would be the same finding worded differently.

    Args:
        ctx: The shared analysis context.
        progress: Optional callable receiving status strings.

    Returns:
        Up to :data:`MAX_BIMODALITY_CARDS` histogram suggestions, each
        configured to open on the unit the split was found in.
    """
    out: list[Suggestion] = []
    available = set(ctx.available_data_keys())
    if not available:
        return out

    reported: set[str] = set()
    for data_key in BIMODALITY_SCAN_ORDER:
        if data_key not in available or len(out) >= MAX_BIMODALITY_CARDS:
            continue

        noun = _DATA_KEY_NOUNS.get(data_key, "value")
        _say(progress, f"Checking {noun} distributions…")
        matrix, det_mask = ctx.matrix_for(data_key)
        if not matrix:
            continue

        findings = []
        for el in sorted(matrix, key=lambda e: -int(det_mask[e].sum())):
            if el in reported:
                continue
            split = _detect_bimodality(matrix[el][det_mask[el]])
            if split is not None:
                findings.append((el, split))

        findings.sort(key=lambda f: -(f[1]["valley_depth"] * f[1]["minor_share"]))
        unit = _DATA_KEY_UNITS.get(data_key, "")
        label = _DATA_KEY_LABELS.get(data_key, "Counts")

        for el, split in findings:
            if len(out) >= MAX_BIMODALITY_CARDS:
                break
            reported.add(el)
            low, high = split["modes"]
            out.append(Suggestion(
                title=f"Two {noun} populations: {el}",
                reasoning=(
                    f"{el} splits at about {split['split']:.3g} {unit} into groups "
                    f"near {low:.3g} and {high:.3g} {unit}. The smaller holds "
                    f"{split['minor_share'] * 100:.0f}% of "
                    f"{split['n']:,} particles."
                ),
                category="distribution",
                confidence=min(0.55 + split["valley_depth"] * 0.4, 0.94),
                explain_key="distribution_two",
                details=[("Measured as", noun), ("Lower group near", f"{low:.3g} {unit}"),
                         ("Upper group near", f"{high:.3g} {unit}"),
                         ("Split at", f"{split['split']:.3g} {unit}"),
                         ("Smaller group", f"{split['minor_share']:.0%}"),
                         ("Particles", f"{split['n']:,}")],
                node_type="histogram_plot",
                config={"element": el, "data_type_display": label},
                elements=(el,),
            ))
    return out


def _analyse_distribution(ctx: AnalysisContext, progress=None) -> list[Suggestion]:
    """Describe the shape and spread of individual element distributions.

    Two things are looked for: elements that split into two populations, which
    is the more interesting finding and is searched across size, mass and count
    units, and elements whose values simply vary very widely, which is worth
    seeing as a distribution rather than read as an average.

    Args:
        ctx: The shared analysis context.
        progress: Optional callable receiving status strings.

    Returns:
        Any split-distribution suggestions, plus a box plot across the most
        variable elements and a histogram for the single most variable one.
    """
    out: list[Suggestion] = _scan_bimodality(ctx, progress)
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
        explain_key="distribution_spread",
        details=[(el, f"CV {v:.1f}×") for v, el in spreads[:4]],
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
        explain_key="distribution_spread",
        details=[("Element", top[0]), ("Coefficient of variation", f"{cv:.1f}×")],
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
        explain_key="composition",
        details=[("Most common combination", " + ".join(top_combo[:6])),
                 ("Its particles", f"{top_count:,} of {ctx.n:,}"),
                 ("Distinct combinations", f"{len(combos):,}")],
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
        explain_key="composition",
        details=[("Distinct combinations", f"{len(combos):,}")],
        node_type="pie_chart_plot",
        config={},
    ))
    return out


MIN_GROUP_FOLD = 1.5
"""Smallest fold difference between groups worth a comparison card."""


def _comparison_groups(ctx: AnalysisContext) -> list[tuple[ReplicateGroup, list[int]]]:
    """List the replicate groups available for a between-group comparison.

    Args:
        ctx: Context over the whole scope.

    Returns:
        ``(group, sample_indices)`` pairs, keeping only samples with enough
        particles to summarise. Groups left with no sample are dropped.
    """
    names = ctx.sample_names
    groups = ctx.scope.groups or tuple(ReplicateGroup(n, (n,)) for n in names)
    out = []
    for group in groups:
        indices = [names.index(m) for m in group.members if m in names]
        indices = [i for i in indices
                   if int((ctx.sample_idx == i).sum()) >= _disc.MIN_GROUP_PARTICLES]
        if indices:
            out.append((group, indices))
    return out


def _group_selection(groups) -> dict:
    """Samples and selector grouping for a card about some replicate groups.

    Args:
        groups: The :class:`ReplicateGroup` objects the card is about.

    Returns:
        Keyword arguments for :class:`Suggestion`: ``samples`` and
        ``sample_groups``.
    """
    samples: list[str] = []
    sample_groups: dict[str, str] = {}
    for g in groups:
        for m in g.members:
            if m not in sample_groups:
                samples.append(m)
                sample_groups[m] = g.name if g.is_replicated else ""
    return {"samples": tuple(samples), "sample_groups": sample_groups}


def _analyse_comparison(ctx: AnalysisContext, progress=None) -> list[Suggestion]:
    """Find elements whose signal differs between replicate groups.

    Groups are compared, never the replicates inside one group. When every
    compared group has at least two replicates, each replicate's median is one
    observation and the groups are compared with a one-way ANOVA on log
    medians, which is the honest test: the replicate, not the particle, is the
    unit that was repeated. Otherwise the particles of each group are pooled
    and compared with a Kruskal-Wallis test.

    Either way a difference must also be at least :data:`MIN_GROUP_FOLD` and,
    where replicates exist, more than :data:`~results.insights.discovery.REPLICATE_MARGIN`
    times the spread between replicates. The family of tests is corrected for
    false discovery, and survivors are ranked by fold difference.

    Args:
        ctx: The shared analysis context.
        progress: Optional callable receiving status strings.

    Returns:
        Up to two comparison suggestions, or nothing with fewer than two groups.
    """
    out: list[Suggestion] = []
    groups = _comparison_groups(ctx)
    if len(groups) < 2:
        return out

    _say(progress, "Comparing sample groups…")
    tests = []
    for el in ctx.frequent_elements():
        column, detected = ctx.matrix[el], ctx.det_mask[el]
        summaries = []
        for group, indices in groups:
            rep_medians, pooled = [], []
            for i in indices:
                values = column[detected & (ctx.sample_idx == i)]
                if len(values) >= 5:
                    rep_medians.append(float(np.log10(np.median(values))))
                    pooled.append(np.log10(values))
            if pooled:
                summaries.append((group, rep_medians, np.concatenate(pooled)))
        if len(summaries) < 2:
            continue

        replicated = all(len(r) >= 2 for _g, r, _p in summaries)
        try:
            if replicated:
                _stat, p_value = _stats.f_oneway(*[r for _g, r, _p in summaries])
                method = "ANOVA on replicate medians"
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    _stat, p_value = _stats.kruskal(*[pooled for _g, _r, pooled in summaries])
                method = "Kruskal-Wallis on particles"
        except Exception:
            continue
        if not np.isfinite(p_value):
            continue

        centres = [(float(np.median(r)) if r else float(np.median(pooled)), g)
                   for g, r, pooled in summaries]
        centres.sort(key=lambda c: c[0])
        (lo_c, lo_g), (hi_c, hi_g) = centres[0], centres[-1]
        gap = hi_c - lo_c
        spreads = [max(r) - min(r) for _g, r, _p in summaries if len(r) >= 2]
        spread = max(spreads) if spreads else 0.0
        tests.append((el, float(p_value), gap, spread, hi_g, lo_g, method, len(summaries)))

    if not tests:
        return out

    significant, adjusted = _benjamini_hochberg([t[1] for t in tests])
    kept = [
        (t, float(adjusted[k])) for k, t in enumerate(tests)
        if significant[k]
        and 10 ** t[2] >= MIN_GROUP_FOLD
        and t[2] > _disc.REPLICATE_MARGIN * t[3]
    ]
    kept.sort(key=lambda x: -x[0][2])

    for (el, _p, gap, spread, hi_g, lo_g, method, n_groups), q_value in kept[:2]:
        fold = 10 ** gap
        if spread > 0:
            rep_text = f", well beyond the ×{10 ** spread:.2f} spread between replicates"
        else:
            rep_text = " (no replicates, so particle-level only)"
        title = (f"{el}: {hi_g.name} vs {lo_g.name}" if n_groups == 2
                 else f"{el} highest in {hi_g.name}, lowest in {lo_g.name}")
        out.append(Suggestion(
            title=title,
            reasoning=(
                f"Median {el} is {fold:.1f}× higher in {hi_g.name} than in {lo_g.name}"
                f"{rep_text}. {method}, {_fmt_q(q_value)} across {len(tests)} elements."
            ),
            category="comparison",
            confidence=min(0.5 + math.log10(fold) * 0.4, 0.92),
            explain_key="comparison",
            details=[("Element", el), ("Higher group", hi_g.name), ("Lower group", lo_g.name),
                     ("Fold difference in median", f"{fold:.2f}×"),
                     ("Spread between replicates", f"×{10 ** spread:.2f}" if spread else "no replicates"),
                     ("Test", method), ("Elements tested", str(len(tests))),
                     ("False discovery", _fmt_q(q_value))],
            node_type="concentration_comparison",
            config={"element": el},
            elements=(el,),
            **_group_selection([hi_g, lo_g]),
        ))
    return out


def _group_rates(ctx: AnalysisContext, mask: np.ndarray, indices: list[int]) -> tuple[float, float, int, int]:
    """Summarise how often *mask* is true across one group's replicates.

    Args:
        ctx: Context over the whole scope.
        mask: Per-particle boolean, such as a detection mask.
        indices: Sample indices of the group's replicates.

    Returns:
        ``(mean_rate, rate_spread, hits, size)``: the mean of the per-replicate
        rates, the gap between the highest and lowest replicate, and the pooled
        hit and particle counts for an exact test.
    """
    rates, hits, size = [], 0, 0
    for i in indices:
        in_sample = ctx.sample_idx == i
        n = int(in_sample.sum())
        h = int((mask & in_sample).sum())
        rates.append(h / n if n else 0.0)
        hits += h
        size += n
    spread = (max(rates) - min(rates)) if len(rates) >= 2 else 0.0
    return float(np.mean(rates)), spread, hits, size


def _analyse_signature(ctx: AnalysisContext, progress=None) -> list[Suggestion]:
    """Find what one group of samples contains that another does not.

    This asks a different question from the comparison analysis. Comparison
    asks how *much* of an element a group carries; signature asks whether the
    element is there at all. An element found in a third of one group's
    particles and in none of another's is a fingerprint, however similar the
    concentrations happen to be where both are present.

    Presence rates are averaged over each group's replicates and compared with
    Fisher's exact test between the groups holding the most and least of each
    element; the family of tests is corrected for false discovery. Where
    replicates exist, the gap must also exceed the spread between them. The
    same is then done for whole element combinations, which is what makes a
    card like "Al+Fe+Si+Pb is 18% of S1 and absent from S2" possible.

    Args:
        ctx: The shared analysis context.
        progress: Optional callable receiving status strings.

    Returns:
        Up to two element suggestions and one combination suggestion, or
        nothing with fewer than two groups.
    """
    out: list[Suggestion] = []
    groups = _comparison_groups(ctx)
    if len(groups) < 2:
        return out

    _say(progress, "Comparing group signatures…")
    tests: list[tuple] = []
    for el, mask in ctx.det_mask.items():
        rates = []
        for group, indices in groups:
            mean_rate, spread, hits, size = _group_rates(ctx, mask, indices)
            rates.append((mean_rate, hits, size, group, spread))
        rates.sort(key=lambda r: -r[0])
        top, bottom = rates[0], rates[-1]
        gap = top[0] - bottom[0]
        if top[0] < 0.05 or gap < 0.15:
            continue
        if gap <= _disc.REPLICATE_MARGIN * max(top[4], bottom[4]):
            continue
        try:
            _odds, p_value = _stats.fisher_exact([
                [top[1], top[2] - top[1]],
                [bottom[1], bottom[2] - bottom[1]],
            ])
        except Exception:
            continue
        tests.append((el, float(p_value), top, bottom))

    if tests:
        significant, adjusted = _benjamini_hochberg([t[1] for t in tests])
        kept = [(t, float(adjusted[k])) for k, t in enumerate(tests) if significant[k]]
        kept.sort(key=lambda x: -(x[0][2][0] - x[0][3][0]))

        for (el, _p, top, bottom), q_value in kept[:2]:
            absent = bottom[1] == 0
            distinctive = bottom[0] <= top[0] * SIGNATURE_ABSENCE_RATIO
            top_name, bottom_name = top[3].name, bottom[3].name
            out.append(Suggestion(
                title=(f"{el} marks {top_name}" if distinctive
                       else f"{el} is enriched in {top_name}"),
                reasoning=(
                    f"{el} appears in {top[0] * 100:.0f}% of {top_name} particles "
                    + (f"and in none of {bottom_name}." if absent
                       else f"but only {bottom[0] * 100:.1f}% of {bottom_name}.")
                    + f" Fisher {_fmt_q(q_value)}."
                ),
                category="signature",
                confidence=min(0.5 + (top[0] - bottom[0]) * 0.5, 0.95),
                explain_key="signature",
                details=[(f"Share in {top_name}", f"{top[0]:.1%}"),
                         (f"Share in {bottom_name}", f"{bottom[0]:.1%}"),
                         ("Spread between replicates", f"{max(top[4], bottom[4]):.1%}"),
                         ("Fisher", _fmt_q(q_value))],
                node_type="element_composition_plot",
                config={},
                elements=(el,),
                **_group_selection([top[3], bottom[3]]),
            ))

    combo_card = _signature_combination(ctx, groups)
    if combo_card is not None:
        out.append(combo_card)
    return out


def _signature_combination(ctx: AnalysisContext, groups) -> Suggestion | None:
    """Find an element combination that belongs to one group alone.

    Args:
        ctx: The shared analysis context.
        groups: ``(group, sample_indices)`` pairs from :func:`_comparison_groups`.

    Returns:
        A suggestion naming the most distinctive combination, or ``None`` when
        no combination is common in one group and rare in the rest.
    """
    combo_ids = np.full(ctx.n, -1, dtype=np.int64)
    ids: dict[tuple, int] = {}
    for position, p in enumerate(ctx.particles):
        detected = tuple(sorted(
            el for el, v in (p.get("elements") or {}).items()
            if _safe_float(v) is not None
        ))
        if len(detected) >= 2:
            combo_ids[position] = ids.setdefault(detected, len(ids))
    counts = np.bincount(combo_ids[combo_ids >= 0], minlength=len(ids))

    floor = max(5, int(0.01 * ctx.n))
    best = None
    for combo, combo_id in ids.items():
        if counts[combo_id] < floor:
            continue
        mask = combo_ids == combo_id
        shares = []
        for group, indices in groups:
            mean_rate, spread, _hits, _size = _group_rates(ctx, mask, indices)
            shares.append((mean_rate, group, spread))
        shares.sort(key=lambda s: -s[0])
        top, bottom = shares[0], shares[-1]
        if top[0] < 0.05:
            continue
        gap = top[0] - bottom[0]
        if gap < SIGNATURE_MIN_COMBO_GAP:
            continue
        if bottom[0] > top[0] * SIGNATURE_ABSENCE_RATIO:
            continue
        if gap <= _disc.REPLICATE_MARGIN * max(top[2], bottom[2]):
            continue
        if best is None or gap > best[0]:
            best = (gap, combo, top, bottom)

    if best is None:
        return None

    gap, combo, top, bottom = best
    absent = bottom[0] == 0
    shown = " + ".join(combo[:5])
    top_name, bottom_name = top[1].name, bottom[1].name
    return Suggestion(
        title=f"{top_name} signature: {shown}",
        reasoning=(
            f"Particles carrying {shown} make up {top[0] * 100:.0f}% of "
            f"{top_name} "
            + (f"and are absent from {bottom_name}."
               if absent else
               f"against {bottom[0] * 100:.1f}% of {bottom_name}.")
        ),
        category="signature",
        confidence=min(0.5 + gap * 0.5, 0.92),
        explain_key="signature",
        details=[("Combination", shown), (f"Share in {top_name}", f"{top[0]:.1%}"),
                 (f"Share in {bottom_name}", f"{bottom[0]:.1%}")],
        node_type="pie_chart_plot",
        config={},
        elements=tuple(combo[:5]),
        **_group_selection([top[1], bottom[1]]),
    )


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
        explain_key="outlier",
        details=[("Element", el), ("Outlying particles", f"{count:,} ({fraction:.1%})")],
        node_type="heatmap_plot",
        config={"highlight_element": el},
    ))
    return out


def _analyse_joint_outlier(ctx: AnalysisContext, progress=None) -> list[Suggestion]:
    """Find particles that are extreme in more than one element at once.

    A particle high in a single element is unremarkable in a heavy-tailed
    dataset. A particle high in two elements simultaneously is a much stronger
    signal, and usually means a genuinely different kind of particle rather
    than the tail of the usual one.

    Extremes are measured with the median and the median absolute deviation on
    log values, so a few very large particles cannot inflate the threshold and
    hide the rest, as the mean and standard deviation would allow.

    Args:
        ctx: The shared analysis context.
        progress: Optional callable receiving status strings.

    Returns:
        At most one suggestion, proposing the scatter of the two elements that
        most often go extreme together.
    """
    out: list[Suggestion] = []
    els = ctx.frequent_elements()
    if len(els) < 2:
        return out

    _say(progress, "Looking for joint outliers…")
    extreme: dict[str, np.ndarray] = {}
    for el in els:
        detected = ctx.det_mask[el]
        values = ctx.matrix[el][detected]
        if len(values) < 30:
            continue
        logged = np.log10(values)
        median = float(np.median(logged))
        deviation = float(np.median(np.abs(logged - median)))
        if deviation <= 0:
            continue
        scores = 0.6745 * (logged - median) / deviation
        flags = np.zeros(ctx.n, dtype=bool)
        flags[detected] = scores > 3.5
        if flags.any():
            extreme[el] = flags

    if len(extreme) < 2:
        return out

    stacked = np.vstack(list(extreme.values()))
    hits = stacked.sum(axis=0)
    joint = int(np.sum(hits >= 2))
    if joint < 5:
        return out

    joint_mask = hits >= 2
    pairs: dict[tuple[str, str], int] = {}
    labels = list(extreme)
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            both = int(np.sum(extreme[labels[i]] & extreme[labels[j]] & joint_mask))
            if both:
                pairs[(labels[i], labels[j])] = both
    if not pairs:
        return out

    (first, second), together = max(pairs.items(), key=lambda kv: kv[1])
    out.append(Suggestion(
        title=f"Joint outliers: {first} + {second}",
        reasoning=(
            f"{joint:,} particles are extreme in two or more elements at once, "
            f"{together:,} of them in {first} and {second} together. Being "
            "unusual twice over is far less likely than a single long tail."
        ),
        category="outlier",
        confidence=min(0.55 + joint / ctx.n * 4, 0.88),
        explain_key="outlier",
        details=[("Extreme in two or more elements", f"{joint:,}"),
                 (f"Extreme in {first} and {second}", f"{together:,}")],
        node_type="correlation_plot",
        config={"x_element": first, "y_element": second},
        elements=(first, second),
    ))
    return out


@dataclass(frozen=True)
class InsightCategory:
    """One detector in the discovery engine.

    Attributes:
        key: Identifier, and the default ``category`` of its suggestions.
        label: Human-readable name.
        icon: Glyph shown on cards of this kind.
        run: Callable taking ``(ctx, progress)`` and returning suggestions.
        kind: ``"within"`` for detectors that look inside one material and are
            run once per replicate group; ``"across"`` for detectors that
            compare samples or groups and see the whole scope.
        node_types: Plot nodes the detector can propose. Ticking a node type
            in the panel runs every detector that can feed it.
    """

    key: str
    label: str
    icon: str
    run: object
    kind: str = "within"
    node_types: frozenset = frozenset()


def _analyse_anomaly(ctx: AnalysisContext, progress=None) -> list[Suggestion]:
    """Run every anomaly test the outlier category covers.

    Args:
        ctx: The shared analysis context.
        progress: Optional callable receiving status strings.

    Returns:
        Single-element outlier suggestions followed by joint ones.
    """
    return _analyse_outlier(ctx, progress) + _analyse_joint_outlier(ctx, progress)


_REGISTRY = (
    ("interference", _disc.analyse_interference, "within", {"correlation_plot"}),
    ("isotope", _analyse_isotope, "within", {"isotopic_ratio_plot"}),
    ("isotope_groups", _disc.analyse_isotope_groups, "across", {"isotopic_ratio_plot"}),
    ("comparison", _analyse_comparison, "across", {"concentration_comparison"}),
    ("signature", _analyse_signature, "across",
     {"element_composition_plot", "pie_chart_plot"}),
    ("replicate", _disc.analyse_replicates, "across",
     {"concentration_comparison", "box_plot", "figure_builder"}),
    ("time", _disc.analyse_time, "across", {"figure_builder"}),
    ("stoichiometry", _disc.analyse_stoichiometry, "within",
     {"molar_ratio_plot", "correlation_plot"}),
    ("cooccurrence", _disc.analyse_cooccurrence, "within", {"heatmap_plot"}),
    ("rare", _disc.analyse_rare, "within", {"heatmap_plot"}),
    ("quality", _disc.analyse_detection_limit, "within", {"histogram_plot"}),
    ("ternary", _disc.analyse_ternary, "within", {"triangle_plot"}),
    ("single_multi", _disc.analyse_single_multi, "within", {"single_multiple_element_plot"}),
    ("composition", _analyse_composition, "within",
     {"element_bar_chart_plot", "pie_chart_plot"}),
    ("size", _disc.analyse_size_composition, "within", {"figure_builder"}),
    ("outlier", _analyse_anomaly, "within", {"heatmap_plot", "correlation_plot"}),
    ("correlation", _analyse_correlation, "within", {"correlation_plot", "correlation_matrix"}),
    ("network", _disc.analyse_network, "within", {"network_diagram"}),
    ("distribution", _analyse_distribution, "within", {"histogram_plot", "box_plot"}),
    ("types", _disc.analyse_particle_types, "across", {"figure_builder"}),
)
"""Detectors in run order, fastest and most specific first, so the panel fills
with interference, isotope and group findings before the slower passes finish."""

_ANALYSERS: dict[str, InsightCategory] = {
    key: InsightCategory(key, _CAT_META[key]["label"], _CAT_META[key]["icon"], fn,
                         kind, frozenset(types))
    for key, fn, kind, types in _REGISTRY
}


def category_keys() -> list[str]:
    """List the detectors in the order they run.

    Returns:
        Detector keys, suitable for indexing :data:`_ANALYSERS`.
    """
    return list(_ANALYSERS)


def node_type_keys() -> list[str]:
    """List the plot nodes Insights can propose, in panel order."""
    return list(NODE_TYPE_META)


def analysers_for(node_types) -> list[str]:
    """Return the detectors needed to fill the given node types.

    Args:
        node_types: Node type keys, or ``None`` for all of them.

    Returns:
        Detector keys, in run order.
    """
    if node_types is None:
        return category_keys()
    wanted = set(node_types)
    return [k for k, a in _ANALYSERS.items() if a.node_types & wanted]


_NODE_TYPE_CARD_LIMITS: dict[str, int] = {
    "correlation_plot": 4,
    "histogram_plot": 3,
    "heatmap_plot": 3,
    "concentration_comparison": 4,
    "figure_builder": 4,
    "isotopic_ratio_plot": 3,
    "molar_ratio_plot": 3,
    "box_plot": 2,
    "element_composition_plot": 2,
    "pie_chart_plot": 2,
}
"""Node types allowed more than one card, because each says something new.

A second correlation plot is a different element pair, and a second histogram
is a different element or a different unit. Everything else repeats itself.
"""

_DEFAULT_CARD_LIMIT = 1

FOCUSED_CARD_LIMIT = 12
"""Cards allowed per node type when the panel shows a single node type."""

_MULTI_SAMPLE_CATEGORIES = ("comparison", "signature")
"""Detectors that need at least two groups in scope to say anything."""


def _dedupe_suggestions(suggestions: list[Suggestion], per_type_limit: int | None = None
                        ) -> list[Suggestion]:
    """Rank suggestions and drop the ones that repeat each other.

    Two cards are treated as the same idea when they would build the same node
    over the same elements, samples and unit. Beyond that, each node type is
    capped so that one prolific analysis cannot crowd out the rest.

    Args:
        suggestions: Suggestions from one or more analysers.
        per_type_limit: Cap applied to every node type instead of the defaults,
            used when the panel focuses on a single node type.

    Returns:
        The surviving suggestions, most confident first.
    """
    seen: set[tuple] = set()
    counts: dict[str, int] = {}
    out: list[Suggestion] = []

    for s in sorted(suggestions, key=lambda x: -x.confidence):
        signature = (s.node_type, tuple(sorted(s.elements)), tuple(s.samples),
                     s.config.get("data_type_display", ""), s.category,
                     "" if s.elements else s.title)
        loose = (s.node_type, tuple(sorted(s.elements)), tuple(s.samples),
                 s.config.get("data_type_display", ""))
        if signature in seen or (s.elements and loose in seen):
            continue
        limit = (per_type_limit if per_type_limit is not None
                 else _NODE_TYPE_CARD_LIMITS.get(s.node_type, _DEFAULT_CARD_LIMIT))
        if counts.get(s.node_type, 0) >= limit:
            continue
        seen.add(signature)
        seen.add(loose)
        counts[s.node_type] = counts.get(s.node_type, 0) + 1
        out.append(s)
    return out


MIN_WITHIN_GROUP_PARTICLES = 20
"""Particles a replicate group needs before within-group detectors search it."""


def _within_units(ctx: AnalysisContext) -> list[tuple[AnalysisContext, ReplicateGroup | None]]:
    """Split the scope into the per-group contexts within-group detectors search.

    Searching each group on its own keeps a pattern that exists in one
    material from being diluted by the others, and keeps a difference between
    materials from masquerading as a pattern inside one. With a single group
    the whole context is searched as it is.

    The split is cached on the context, so every detector reuses it.

    Args:
        ctx: Context over the whole scope.

    Returns:
        ``(context, group)`` pairs; *group* is ``None`` when the scope has no
        grouping at all.
    """
    cached = ctx.cache.get("within_units")
    if cached is not None:
        return cached
    groups = list(ctx.scope.groups)
    if len(groups) <= 1:
        units = [(ctx, groups[0] if groups else None)]
    else:
        units = []
        for group in groups:
            mask = ctx.group_mask(group)
            if int(mask.sum()) >= MIN_WITHIN_GROUP_PARTICLES:
                units.append((ctx.subset(mask, group.name), group))
    ctx.cache["within_units"] = units
    return units


def _run_detector(ctx: AnalysisContext, analyser: InsightCategory, progress=None,
                  should_stop=None) -> list[Suggestion]:
    """Run one detector the way its kind requires.

    Within-group detectors run once per replicate group and their findings are
    merged, so a card records every sample where it held. Across-group
    detectors run once over the whole scope.

    Args:
        ctx: Context over the whole scope.
        analyser: The detector to run.
        progress: Optional callable receiving status strings.
        should_stop: Optional callable returning ``True`` to abandon the run.

    Returns:
        The detector's suggestions, each carrying its samples.
    """
    if analyser.kind != "within":
        return list(analyser.run(ctx, progress))
    units = _within_units(ctx)
    items = []
    for sub, group in units:
        if should_stop is not None and should_stop():
            return []
        for s in analyser.run(sub, progress):
            items.append((s, group))
    if all(group is None for _s, group in items):
        return [s for s, _g in items]
    return _disc.merge_group_findings(items, ctx.sample_names, len(units))


def analyse(ctx: AnalysisContext, categories=None, progress=None,
            should_stop=None, node_types=None, dedupe: bool = True,
            per_type_limit: int | None = None) -> list[Suggestion]:
    """Run detectors over *ctx* and collect their suggestions.

    Args:
        ctx: The shared analysis context.
        categories: Detector keys to run. All of them when omitted.
        progress: Optional callable receiving status strings.
        should_stop: Optional callable returning ``True`` to abandon the run
            between detectors.
        node_types: Only keep suggestions for these plot nodes, and only run
            the detectors able to produce them. Every node type when omitted.
        dedupe: Rank and de-duplicate the result. The panel turns this off and
            de-duplicates itself, because its limits depend on the view.
        per_type_limit: Passed to :func:`_dedupe_suggestions`.

    Returns:
        The suggestions, most confident first when deduplicated. Empty if the
        context is too small to analyse or the run was stopped.
    """
    if ctx.n < 5 or not ctx.matrix:
        return []

    keys = list(categories) if categories else category_keys()
    if node_types is not None:
        allowed = set(analysers_for(node_types))
        keys = [k for k in keys if k in allowed]
    found: list[Suggestion] = []
    for key in keys:
        if should_stop is not None and should_stop():
            return []
        analyser = _ANALYSERS.get(key)
        if analyser is None:
            _itk_log.debug(f"[Insights] unknown category: {key}")
            continue
        try:
            found.extend(_run_detector(ctx, analyser, progress, should_stop))
        except Exception:
            _itk_log.exception(f"[Insights] {key} analysis failed")
    if should_stop is not None and should_stop():
        return []
    if node_types is not None:
        wanted = set(node_types)
        found = [s for s in found if s.node_type in wanted]
    return _dedupe_suggestions(found, per_type_limit) if dedupe else found


def context_for_stream(data: dict | None) -> AnalysisContext | None:
    """Build an analysis context from a canvas data stream.

    Used by nodes that receive particles over a link, such as the AI
    assistant, rather than reading the loaded pool. Particles are grouped by
    their ``source_sample``, and replicate groups are guessed from the sample
    names.

    Args:
        data: A ``sample_data`` or ``multiple_sample_data`` stream.

    Returns:
        The context, or ``None`` when the stream holds too few particles.
    """
    if not isinstance(data, dict):
        return None
    particles = list(data.get("particle_data") or [])
    if len(particles) < 5:
        return None
    fallback = data.get("sample_name") or "Sample"
    by_sample: dict[str, list[dict]] = {}
    for p in particles:
        by_sample.setdefault(p.get("source_sample") or fallback, []).append(p)
    listed = list(data.get("sample_names") or [])
    names = [n for n in listed if n in by_sample] + [n for n in by_sample if n not in listed]
    flat: list[dict] = []
    index: list[int] = []
    for i, name in enumerate(names):
        flat.extend(by_sample[name])
        index.extend([i] * len(by_sample[name]))
    scope = AnalysisScope(
        tuple(names), "stream", tuple(len(by_sample[n]) for n in names),
        tuple(id(by_sample[n]) for n in names), tuple(resolve_groups(names)),
    )
    matrix, det_mask = _build_matrix(flat)
    return AnalysisContext(
        scope=scope, particles=flat, matrix=matrix, det_mask=det_mask,
        det_counts={el: int(m.sum()) for el, m in det_mask.items()},
        sample_idx=np.asarray(index, dtype=np.int32),
    )


def findings_for_stream(data: dict | None, limit: int = 12, should_stop=None) -> list[Suggestion]:
    """Run every Insights detector over a canvas data stream.

    Args:
        data: A ``sample_data`` or ``multiple_sample_data`` stream.
        limit: Most findings to return.
        should_stop: Optional callable returning ``True`` to abandon the run.

    Returns:
        The strongest findings, most confident first.
    """
    ctx = context_for_stream(data)
    if ctx is None:
        return []
    return analyse(ctx, should_stop=should_stop)[:limit]


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
        partial: Emitted after each detector with its suggestions and its
            key, so the panel can show findings as soon as they exist.
        progress: Emitted with a short status string as each stage begins.
    """

    results_ready = Signal(list)
    partial = Signal(list, str)
    progress = Signal(str)

    def __init__(self, scope: AnalysisScope, particles: list[dict],
                 sample_idx: np.ndarray, categories=None, node_types=None,
                 dedupe: bool = True):
        """Prepare an analysis run.

        Args:
            scope: The resolved scope these particles were gathered for.
            particles: Particle dicts to analyse.
            sample_idx: Index into ``scope.sample_names`` for each particle.
            categories: Detector keys to run. All of them when omitted.
            node_types: Plot nodes to search for. All of them when omitted.
            dedupe: De-duplicate before emitting. The panel passes ``False``
                and de-duplicates for whichever view is showing.
        """
        super().__init__()
        self._scope = scope
        self._particles = particles
        self._sample_idx = sample_idx
        self._categories = tuple(categories) if categories else None
        self._node_types = tuple(node_types) if node_types is not None else None
        self._dedupe = dedupe
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

        if ctx.n < 5 or not ctx.matrix:
            self.results_ready.emit([])
            return

        keys = list(self._categories) if self._categories else category_keys()
        wanted = set(self._node_types) if self._node_types is not None else None
        if wanted is not None:
            allowed = set(analysers_for(wanted))
            keys = [k for k in keys if k in allowed]

        found: list[Suggestion] = []
        for key in keys:
            if self._stop():
                return
            analyser = _ANALYSERS.get(key)
            if analyser is None:
                continue
            try:
                result = _run_detector(ctx, analyser, self.progress.emit, self._stop)
            except Exception:
                _itk_log.exception(f"[Insights] {key} analysis failed")
                result = []
            if wanted is not None:
                result = [s for s in result if s.node_type in wanted]
            found.extend(result)
            if self._stop():
                return
            self.partial.emit(result, key)

        if self._stop():
            return
        self.results_ready.emit(_dedupe_suggestions(found) if self._dedupe else found)
