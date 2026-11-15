"""One number with its uncertainty for a group of particles.

A ratio of two signals is best estimated as the ratio of their sums over the
particles, not as the mean or median of the particles' own ratios: a small
particle's ratio is noisy and skewed, and many small particles pull an
average of ratios away from the truth. The ratio of sums weighs each
particle by its signal, so the large, well-counted particles decide.

The uncertainty is the standard error of that ratio estimator, from how each
particle's numerator departs from the pooled ratio times its denominator. For
raw ion counts of one isotopic population it equals the counting-statistics
error ``R·√(1/ΣA + 1/ΣB)``; when the particles truly differ it is wider, as it
should be. Nothing here assumes the values are counts.

A value that is not a ratio is estimated by its mean and the standard error
of the mean. Nothing here depends on Qt or matplotlib.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

Z95 = 1.959964
"""Normal quantile of a two-sided 95% interval."""

CHI2_95_2DF = 5.991465
"""Chi-square quantile of a 95% region in two dimensions."""

MIN_PARTICLES = 3
"""Particles a group needs before it is estimated."""


@dataclass
class Estimate:
    """A group's value and what it rests on.

    Attributes:
        value: The ratio of sums, or the mean.
        se: Its standard error.
        n: Particles used.
        influence: How much each of those particles moves the value; the
            squares sum to the variance and the products of two estimates'
            influences to their covariance.
    """

    value: float
    se: float
    n: int
    influence: np.ndarray

    @property
    def half(self) -> float:
        """Half-width of the 95% interval."""
        return Z95 * self.se


def denominator(expr: str) -> str | None:
    """The denominator of an expression written as one thing divided by another.

    ``"206Pb / 207Pb"`` → ``"207Pb"``; a mass-bias factor is allowed, so
    ``"(206Pb / 207Pb) * 1.01"`` and ``"(206Pb / 207Pb) * mb_x"`` give
    ``"207Pb"`` too. ``None`` for anything else, such as a sum, a product or
    a ratio of ratios.
    """
    from results.figure_builder.core.isotopes import split_factor
    text = split_factor(expr or '')[0].strip()
    depth = 0
    cut = None
    for i, ch in enumerate(text):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0 and ch == '/':
            if cut is not None:
                return None
            cut = i
        elif depth == 0 and ch in '+*' or (depth == 0 and ch == '-' and i > 0):
            return None
    if cut is None:
        return None
    den = text[cut + 1:].strip()
    return den or None


def estimate(values, weights=None) -> Estimate | None:
    """Estimate a group's value from its particles.

    Args:
        values: One value per particle; for a ratio, each particle's own ratio.
        weights: For a ratio, each particle's denominator. The estimate is
            then the ratio of sums, written as the denominator-weighted mean
            of the particles' ratios, which carries any correction factor
            already applied to them. ``None`` for a plain mean.

    Returns:
        The :class:`Estimate`, or ``None`` with fewer than
        :data:`MIN_PARTICLES` usable particles.
    """
    v = np.asarray(values, dtype=float)
    if weights is None:
        ok = np.isfinite(v)
        v = v[ok]
        n = int(v.size)
        if n < MIN_PARTICLES:
            return None
        centre = float(v.mean())
        infl = (v - centre) / n
    else:
        w = np.asarray(weights, dtype=float)
        ok = np.isfinite(v) & np.isfinite(w) & (w > 0)
        v, w = v[ok], w[ok]
        n = int(v.size)
        if n < MIN_PARTICLES:
            return None
        total = float(w.sum())
        centre = float(np.sum(v * w) / total)
        infl = w * (v - centre) / total
    se = float(np.sqrt(n / (n - 1) * np.sum(infl ** 2)))
    return Estimate(centre, se, n, infl)


def covariance(a: Estimate, b: Estimate) -> np.ndarray:
    """Covariance matrix of two estimates made on the same particles, in the same order."""
    n = a.n
    if n != b.n or n < MIN_PARTICLES:
        raise ValueError('The two estimates must come from the same particles')
    k = n / (n - 1)
    ab = k * float(np.sum(a.influence * b.influence))
    return np.array([[a.se ** 2, ab], [ab, b.se ** 2]])


def ellipse(a: Estimate, b: Estimate, points: int = 200) -> tuple[np.ndarray, np.ndarray] | None:
    """Outline of the 95% region of two estimates' joint value.

    Returns:
        ``(x, y)`` of the outline, or ``None`` when the region has no area.
    """
    cov = covariance(a, b)
    if not np.all(np.isfinite(cov)) or np.linalg.det(cov) <= 0:
        return None
    vals, vecs = np.linalg.eigh(cov)
    t = np.linspace(0, 2 * np.pi, points)
    ring = vecs @ (np.sqrt(np.maximum(vals, 0) * CHI2_95_2DF)[:, None] * np.vstack([np.cos(t), np.sin(t)]))
    return ring[0] + a.value, ring[1] + b.value


def difference(a: Estimate, b: Estimate) -> tuple[float, float]:
    """Compare two independent groups' estimates.

    Returns:
        ``(z, p)``: the difference in units of its standard error and its
        two-sided p-value.
    """
    from scipy import stats
    se = float(np.hypot(a.se, b.se))
    if not se > 0:
        return float('nan'), float('nan')
    z = (a.value - b.value) / se
    return float(z), float(2 * stats.norm.sf(abs(z)))


def fmt_pm(value: float, half: float) -> str:
    """``1.163 ± 0.016``: the value written to the digits its interval supports."""
    if not (np.isfinite(value) and np.isfinite(half)) or half <= 0:
        return f'{value:.4g}'
    digits = max(0, min(8, 1 - int(np.floor(np.log10(half)))))
    return f'{value:.{digits}f} ± {half:.{digits}f}'
