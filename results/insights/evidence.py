"""Numbers behind a finding's figure, measured on the particles the figure draws.

The explained figure's legend should report what its panels show, not what
they are expected to show. Every function here reads the same particle table
the Figure Builder node will draw from, with the same expressions and
filters, so a number in the legend is the number in the panel.

:class:`Checks` collects the verdict line closing the legend: each check is
passed (✓), failed (✗) or undecided (–) with a short reason.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

BOOTSTRAP = 400
"""Resamples for bootstrap confidence intervals."""

BAND_K = 2.0
"""Width of the counting-statistics band, in standard deviations."""

EXCESS_OK = 1.3
"""Excess scatter up to which a ratio's spread is read as counting noise alone."""

EXCESS_LOW = 0.6
"""Excess scatter below which the counts cannot be raw ion counts.

Counting statistics set a floor on the scatter of a ratio; a spread well
below it means the signal was scaled before it reached the table.
"""

DRIFT_RHO = 0.15
"""Rank correlation above which a ratio is said to drift with signal."""

COINCIDENCE_SHARE = 0.10
"""Largest share of co-detections that may be chance coincidence for a pairing to count."""


@dataclass
class Checks:
    """The checks a figure ran, written as the legend's closing line."""

    items: list = field(default_factory=list)

    def add(self, ok: bool | None, text: str) -> None:
        """Record a check: ``True`` passed, ``False`` failed, ``None`` undecided."""
        self.items.append((ok, text))

    def line(self) -> str:
        """The verdict line, or an empty string when nothing was checked."""
        if not self.items:
            return ""
        marks = {True: "✓", False: "✗", None: "–"}
        return "Checks: " + "; ".join(f"{marks[ok]} {text}" for ok, text in self.items) + "."


def table_from(units, pool) -> object | None:
    """The particle table a figure's selector will produce.

    Args:
        units: ``(label, members)`` pairs from
            :func:`results.insights.panel.selection_units`; a label shared by
            several members is a pooled replicate group.
        pool: Sample name to its particle dicts.

    Returns:
        A Figure Builder :class:`ParticleTable`, or ``None`` without particles.
    """
    from results.figure_builder.core.expressions import ParticleTable
    particles = []
    names = []
    for label, members in units:
        names.append(label)
        for member in members:
            for p in pool.get(member, ()):
                q = dict(p)
                q["source_sample"] = label
                q["original_sample"] = member
                particles.append(q)
    if not particles:
        return None
    return ParticleTable.from_input({"type": "multiple_sample_data", "sample_names": names,
                                     "particle_data": particles}, "Counts")


def _eval(table, expr: str) -> np.ndarray:
    """Evaluate an expression on the table as floats."""
    from results.figure_builder.core.expressions import evaluate
    return np.asarray(evaluate(expr, table), dtype=float)


def mask(table, rule: str = "") -> np.ndarray:
    """Particles passing a filter expression; every particle for an empty rule."""
    from results.figure_builder.core.expressions import evaluate
    if not (rule or "").strip():
        return np.ones(len(table), dtype=bool)
    return np.asarray(evaluate(rule, table, as_mask=True), dtype=bool)


def values(table, expr: str, rule: str = "") -> np.ndarray:
    """Finite positive values of *expr* among the particles passing *rule*."""
    v = _eval(table, expr)[mask(table, rule)]
    return v[np.isfinite(v) & (v > 0)]


def by_sample(table, expr: str, rule: str = "") -> list[tuple[str, np.ndarray]]:
    """``(sample, values)`` for every sample of the table, in its order."""
    v = _eval(table, expr)
    m = mask(table, rule) & np.isfinite(v) & (v > 0)
    col = table.column("sample")
    return [(s, v[m & (col == s)]) for s in table.samples()]


def fmt(x: float, digits: int = 3) -> str:
    """A number for a legend."""
    if x is None or not np.isfinite(x):
        return "n/a"
    return f"{x:.{digits}g}"


def pct(x: float) -> str:
    """A share as a percentage for a legend."""
    return "n/a" if x is None or not np.isfinite(x) else f"{100 * x:.0f}%"


def p_text(p: float) -> str:
    """A p-value for a legend."""
    if p is None or not np.isfinite(p):
        return "p n/a"
    return "p < 0.001" if p < 0.001 else f"p = {p:.2g}"


def median_ci(v: np.ndarray, seed: int = 0) -> tuple[float, float, float]:
    """Median and its bootstrap 95% interval."""
    v = np.asarray(v, dtype=float)
    if v.size == 0:
        return math.nan, math.nan, math.nan
    if v.size < 5:
        m = float(np.median(v))
        return m, math.nan, math.nan
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, v.size, size=(BOOTSTRAP, v.size))
    meds = np.median(v[idx], axis=1)
    return float(np.median(v)), float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))


def fold_ci(a: np.ndarray, b: np.ndarray, seed: int = 0) -> tuple[float, float, float]:
    """Ratio of the medians of *a* to *b* with a bootstrap 95% interval."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.size < 5 or b.size < 5:
        return math.nan, math.nan, math.nan
    rng = np.random.default_rng(seed)
    ma = np.median(a[rng.integers(0, a.size, size=(BOOTSTRAP, a.size))], axis=1)
    mb = np.median(b[rng.integers(0, b.size, size=(BOOTSTRAP, b.size))], axis=1)
    folds = ma / np.where(mb > 0, mb, np.nan)
    folds = folds[np.isfinite(folds)]
    point = float(np.median(a) / np.median(b)) if np.median(b) > 0 else math.nan
    if folds.size < 10:
        return point, math.nan, math.nan
    return point, float(np.percentile(folds, 2.5)), float(np.percentile(folds, 97.5))


def spearman(x: np.ndarray, y: np.ndarray) -> tuple[float, float, int]:
    """Spearman's rho, its p-value and the number of pairs used."""
    from scipy import stats
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 10 or np.ptp(x[ok]) == 0 or np.ptp(y[ok]) == 0:
        return math.nan, math.nan, int(ok.sum())
    res = stats.spearmanr(x[ok], y[ok])
    rho = float(getattr(res, "statistic", getattr(res, "correlation", np.nan)))
    return rho, float(res.pvalue), int(ok.sum())


def ratio_spread(table, num: str, den: str, rule: str = "", factor: float = 1.0,
                 group: np.ndarray | None = None) -> dict | None:
    """How the ratio of two isotopes scatters compared with counting statistics.

    Each particle's expected standard deviation from counting statistics is
    ``σ = √(R(1 + R)/N)`` with N its denominator counts. The excess scatter
    is the root mean square of ``(R_i − R̄)/σ_i``: about 1 when counting
    noise explains the spread, well above 1 when the particles differ.

    Args:
        table: Particle table.
        num: Numerator isotope.
        den: Denominator isotope.
        rule: Filter expression for the particles to use.
        factor: Mass-bias factor applied to the reported median.
        group: Optional extra mask, such as one sample.

    Returns:
        ``n``, ``median`` (corrected), ``inside`` (share within ±2σ) and
        ``excess``, or ``None`` with fewer than ten particles.
    """
    a, b = _eval(table, num), _eval(table, den)
    m = mask(table, rule) & (a > 0) & (b > 0)
    if group is not None:
        m &= group
    if int(m.sum()) < 10:
        return None
    r = a[m] / b[m]
    mean = float(np.mean(r))
    sigma = np.sqrt(mean * (1 + mean) / np.maximum(b[m], 1.0))
    z = (r - mean) / sigma
    return {"n": int(m.sum()), "median": float(np.median(r)) * factor,
            "inside": float(np.mean(np.abs(z) <= BAND_K)),
            "excess": float(np.sqrt(np.mean(z ** 2)))}


def ratio_drift(table, num: str, den: str, rule: str = "") -> tuple[float, float, int]:
    """Rank correlation of a particle's isotope ratio with its denominator counts."""
    a, b = _eval(table, num), _eval(table, den)
    m = mask(table, rule) & (a > 0) & (b > 0)
    return spearman(b[m], a[m] / b[m])


def replicate_medians(table, expr: str, rule: str = "") -> dict[str, list[float]]:
    """Each sample's replicate medians of *expr*: sample → one median per replicate."""
    v = _eval(table, expr)
    m = mask(table, rule) & np.isfinite(v) & (v > 0)
    samples = table.column("sample")
    reps = table.column("replicate")
    out: dict[str, list[float]] = {}
    for s in table.samples():
        sm = m & (samples == s)
        meds = []
        for r in dict.fromkeys(reps[sm].tolist()):
            vals = v[sm & (reps == r)]
            if vals.size >= 5:
                meds.append(float(np.median(vals)))
        out[s] = meds
    return out


def replicate_test(meds: dict[str, list[float]], log: bool = True) -> tuple[float | None, str]:
    """Test between samples on replicate medians, when every sample has two or more.

    Returns:
        ``(p, method)``; ``p`` is ``None`` when the samples are not replicated.
    """
    from scipy import stats
    groups = [np.log10(np.array(m)) if log else np.array(m) for m in meds.values()]
    if len(groups) < 2 or any(g.size < 2 for g in groups):
        return None, ""
    try:
        if len(groups) == 2:
            res = stats.ttest_ind(groups[0], groups[1], equal_var=False)
            return float(res.pvalue), "Welch's t-test on replicate medians"
        return float(stats.f_oneway(*groups).pvalue), "ANOVA on replicate medians"
    except Exception:
        return None, ""


def amount(table) -> tuple[np.ndarray, str]:
    """Each particle's total amount, in fg when calibrated, otherwise in counts."""
    from results.figure_builder.core.common import particle_amount
    return particle_amount(table)


def size_classes(table, rule: str = "") -> list[tuple[str, np.ndarray]]:
    """Small, medium and large particles (thirds of total amount) among those passing *rule*."""
    from results.figure_builder.core.common import size_groups
    return [(g.label.split(" (")[0].lower(), g.mask) for g in size_groups(table, mask(table, rule))
            if g.key != "__all__"]


def by_size(table, expr: str, rule: str = "") -> list[tuple[str, float, int]]:
    """Median of *expr* in small, medium and large particles: ``(class, median, n)``."""
    v = _eval(table, expr)
    out = []
    for name, m in size_classes(table, rule):
        vals = v[m & np.isfinite(v) & (v > 0)]
        out.append((name, float(np.median(vals)) if vals.size else math.nan, int(vals.size)))
    return out


def size_holds(table, x_expr: str, y_expr: str, rule: str = "") -> list[tuple[str, float, int]]:
    """Rank correlation of two expressions within each size class: ``(class, rho, n)``."""
    x, y = _eval(table, x_expr), _eval(table, y_expr)
    out = []
    for name, m in size_classes(table, rule):
        ok = m & (x > 0) & (y > 0)
        rho, _p, n = spearman(np.log10(x[ok]), np.log10(y[ok])) if ok.sum() else (math.nan, 0, 0)
        out.append((name, rho, n))
    return out


def detected_share_by_size(table, element: str, rule: str = "") -> list[tuple[str, float, int]]:
    """Share of particles carrying *element* in each size class: ``(class, share, n)``."""
    v = _eval(table, element)
    return [(name, float(np.mean(v[m] > 0)) if m.any() else math.nan, int(m.sum()))
            for name, m in size_classes(table, rule)]


def coincidence(table, a: str, b: str) -> dict | None:
    """Co-detections of two elements against those expected from chance coincidence.

    Two particles arriving within one event's duration are read as one
    particle. With particles arriving at random, an *a* particle meets a
    *b* particle by chance with probability ``1 − exp(−λ_b (τ_a + τ_b))``,
    where λ_b is the rate of *b* particles and τ the median event duration.
    Summed over samples this gives the co-detections chance alone would make.

    Returns:
        ``observed``, ``expected``, ``n_a``, ``n_b``, or ``None`` when the
        particles carry no arrival times.
    """
    va, vb = _eval(table, a), _eval(table, b)
    starts = np.array([_num(p.get("start_time")) for p in table.particles])
    ends = np.array([_num(p.get("end_time")) for p in table.particles])
    if not np.isfinite(starts).any():
        return None
    duration = np.where(np.isfinite(ends) & (ends >= starts), ends - starts, np.nan)
    col = table.column("replicate")
    observed = int(np.sum((va > 0) & (vb > 0)))
    expected = 0.0
    n_a = n_b = 0
    for r in dict.fromkeys(col.tolist()):
        m = col == r
        t = starts[m]
        t = t[np.isfinite(t)]
        if t.size < 2:
            continue
        span = float(t.max() - t.min())
        if span <= 0:
            continue
        has_a, has_b = m & (va > 0), m & (vb > 0)
        tau_a = np.nanmedian(duration[has_a]) if has_a.any() else np.nan
        tau_b = np.nanmedian(duration[has_b]) if has_b.any() else np.nan
        if not (np.isfinite(tau_a) and np.isfinite(tau_b)):
            continue
        rate_b = float(has_b.sum()) / span
        expected += float(has_a.sum()) * (1 - math.exp(-rate_b * (tau_a + tau_b)))
        n_a += int(has_a.sum())
        n_b += int(has_b.sum())
    if n_a == 0:
        return None
    return {"observed": observed, "expected": expected, "n_a": n_a, "n_b": n_b}


def independence(table, a: str, b: str, rule: str = "") -> dict | None:
    """Co-detections of two elements against those expected if they were independent."""
    m = mask(table, rule)
    va, vb = _eval(table, a)[m] > 0, _eval(table, b)[m] > 0
    n = int(m.sum())
    if n < 20:
        return None
    expected = float(va.sum()) * float(vb.sum()) / n
    return {"observed": int((va & vb).sum()), "expected": expected, "n": n}


def near_limit(v: np.ndarray, limit: float | None, factor: float = 2.0) -> float | None:
    """Share of values within *factor* of the detection limit."""
    v = np.asarray(v, dtype=float)
    if limit is None or not limit or v.size == 0:
        return None
    return float(np.mean(v < factor * float(limit)))


def _num(x) -> float:
    """A float, or NaN when *x* is not a number."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return math.nan
