"""Find one, two or three straight-line trends in a scatter of particles.

Particles from different sources often fall on separate lines: two Fe/Mn
ratios, a pure phase and a mixed one. A single regression through them
describes neither. This module fits a mixture of linear regressions
(DeSarbo & Cron 1988), each line with its own slope, intercept and scatter,
by expectation–maximisation, and gives every particle to its most likely
line.

The number of lines can be fixed or chosen from the data. When chosen, a
line is only added if:

* the Bayesian information criterion improves by at least 10 (strong
  evidence on the scale of Kass & Raftery 1995),
* every line holds at least 5 % of the particles, and
* every pair of lines is separated, at the middle of the data, by at least
  twice their pooled scatter, so two lines are not drawn through what is
  really one cloud.

Fits are made on the coordinates as plotted, so on log axes the lines are
power laws, and lines of slope one are fixed ratios.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

MIN_SHARE = 0.05
"""Smallest share of the particles a line may hold."""

MIN_BIC_GAIN = 10.0
"""BIC improvement needed before another line is accepted."""

MIN_SEPARATION = 2.0
"""Least distance between two lines, in units of their pooled scatter."""

MAX_FIT_POINTS = 6000
"""Points used for fitting; larger sets are subsampled and then all assigned."""


@dataclass
class TrendLine:
    """One fitted line.

    Attributes:
        slope: Slope on the plotted axes.
        intercept: Intercept on the plotted axes.
        sigma: Scatter of its particles around the line.
        n: Particles given to the line.
        share: Fraction of all particles.
        r2: Coefficient of determination of its own particles.
        r: Pearson r of its own particles.
    """

    slope: float
    intercept: float
    sigma: float
    n: int = 0
    share: float = 0.0
    r2: float = float("nan")
    r: float = float("nan")


@dataclass
class TrendFit:
    """The chosen fit.

    Attributes:
        lines: The lines, steepest-intercept first (ordered by their value at
            the middle of the data, highest first).
        labels: Index of each particle's line.
        bic: BIC of every number of lines tried, by count.
        chosen_by: ``"data"`` when the count was chosen, ``"user"`` when fixed.
    """

    lines: list[TrendLine]
    labels: np.ndarray
    bic: dict = field(default_factory=dict)
    chosen_by: str = "data"


def _ols(x, y, w):
    """Weighted least-squares slope and intercept."""
    sw = w.sum()
    if sw <= 0:
        return 0.0, float(np.mean(y)) if y.size else 0.0
    mx, my = (w * x).sum() / sw, (w * y).sum() / sw
    sxx = (w * (x - mx) ** 2).sum()
    if sxx <= 0:
        return 0.0, my
    slope = (w * (x - mx) * (y - my)).sum() / sxx
    return float(slope), float(my - slope * mx)


def _em(x, y, init_labels, k, max_iter=200, tol=1e-7):
    """Fit a k-line mixture from starting labels; returns (params, resp, loglik)."""
    n = x.size
    span = float(np.ptp(y)) or 1.0
    floor = 1e-4 * span
    resp = np.zeros((n, k))
    resp[np.arange(n), init_labels] = 1.0
    prev = -np.inf
    params = []
    loglik = -np.inf
    for _ in range(max_iter):
        params = []
        for j in range(k):
            w = resp[:, j]
            slope, icpt = _ols(x, y, w)
            res = y - (slope * x + icpt)
            sw = w.sum()
            sigma = np.sqrt((w * res ** 2).sum() / sw) if sw > 0 else span
            params.append((slope, icpt, max(float(sigma), floor), max(sw / n, 1e-12)))
        dens = np.empty((n, k))
        for j, (slope, icpt, sigma, pi) in enumerate(params):
            res = y - (slope * x + icpt)
            dens[:, j] = np.log(pi) - np.log(sigma * np.sqrt(2 * np.pi)) - 0.5 * (res / sigma) ** 2
        top = dens.max(axis=1, keepdims=True)
        total = top[:, 0] + np.log(np.exp(dens - top).sum(axis=1))
        loglik = float(total.sum())
        resp = np.exp(dens - total[:, None])
        if abs(loglik - prev) < tol * max(1.0, abs(loglik)):
            break
        prev = loglik
    return params, resp, loglik


def _starts(x, y, k, rng):
    """Starting labels: by residual from one line, and by angle about the centre."""
    from sklearn.cluster import KMeans
    slope, icpt = _ols(x, y, np.ones_like(x))
    res = (y - (slope * x + icpt)).reshape(-1, 1)
    starts = [KMeans(n_clusters=k, n_init=4, random_state=int(rng.integers(1 << 30))).fit(res).labels_]
    angle = np.arctan2(y - np.median(y), x - np.median(x)).reshape(-1, 1)
    starts.append(KMeans(n_clusters=k, n_init=4, random_state=int(rng.integers(1 << 30))).fit(angle).labels_)
    order = np.argsort(res[:, 0])
    starts.append(np.minimum((np.arange(x.size) * k) // x.size, k - 1)[np.argsort(order)])
    return starts


def _separated(params, x) -> bool:
    """Whether every pair of lines is apart by MIN_SEPARATION pooled scatters mid-data."""
    lo, mid, hi = np.percentile(x, [10, 50, 90])
    for i in range(len(params)):
        for j in range(i + 1, len(params)):
            si, ii, sgi, _ = params[i]
            sj, ij, sgj, _ = params[j]
            pooled = np.sqrt((sgi ** 2 + sgj ** 2) / 2)
            gap = max(abs((si * at + ii) - (sj * at + ij)) for at in (lo, mid, hi))
            if gap < MIN_SEPARATION * pooled:
                return False
    return True


def fit_trends(x, y, lines="auto", max_lines: int = 3, seed: int = 0) -> TrendFit | None:
    """Fit one or more straight lines through a scatter.

    Args:
        x: Values on the horizontal axis, as plotted (log10 already applied
            for a log axis).
        y: Values on the vertical axis, as plotted.
        lines: ``"auto"`` to choose 1 to *max_lines* from the data, or the
            number of lines to fit.
        max_lines: Most lines tried when choosing.
        seed: Seed for the starting points and subsampling.

    Returns:
        The :class:`TrendFit`, or ``None`` with fewer than ten finite points.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    if int(ok.sum()) < 10:
        return None
    xa, ya = x[ok], y[ok]
    rng = np.random.default_rng(seed)
    if xa.size > MAX_FIT_POINTS:
        pick = rng.choice(xa.size, MAX_FIT_POINTS, replace=False)
        xf, yf = xa[pick], ya[pick]
    else:
        xf, yf = xa, ya
    fixed = None if lines == "auto" else max(1, int(lines))
    counts = [fixed] if fixed else list(range(1, max(1, int(max_lines)) + 1))
    fits = {}
    for k in counts:
        if k == 1:
            labels0 = np.zeros(xf.size, dtype=int)
            fits[k] = _em(xf, yf, labels0, 1)
            continue
        if xf.size < 10 * k:
            continue
        best = None
        for start in _starts(xf, yf, k, rng):
            fit = _em(xf, yf, np.asarray(start), k)
            if best is None or fit[2] > best[2]:
                best = fit
        fits[k] = best
    bic = {k: -2 * f[2] + (4 * k - 1) * np.log(xf.size) for k, f in fits.items()}
    if fixed:
        chosen = fixed if fixed in fits else max(fits)
    else:
        chosen = 1
        for k in sorted(fits):
            if k == 1:
                continue
            params, resp, _ll = fits[k]
            shares = np.bincount(resp.argmax(axis=1), minlength=k) / xf.size
            if (bic[chosen] - bic[k] >= MIN_BIC_GAIN and shares.min() >= MIN_SHARE
                    and _separated(params, xf)):
                chosen = k
    params = fits[chosen][0]
    mid = float(np.median(xa))
    order = sorted(range(len(params)), key=lambda j: -(params[j][0] * mid + params[j][1]))
    params = [params[j] for j in order]
    dens = np.empty((xa.size, len(params)))
    for j, (slope, icpt, sigma, pi) in enumerate(params):
        res = ya - (slope * xa + icpt)
        dens[:, j] = np.log(pi) - np.log(sigma) - 0.5 * (res / sigma) ** 2
    hard = dens.argmax(axis=1)
    labels = np.full(x.size, -1, dtype=int)
    labels[np.flatnonzero(ok)] = hard
    out = []
    for j, (slope, icpt, sigma, _pi) in enumerate(params):
        m = hard == j
        n_j = int(m.sum())
        r2 = r = float("nan")
        if n_j >= 3:
            pred = slope * xa[m] + icpt
            ss_res = float(((ya[m] - pred) ** 2).sum())
            ss_tot = float(((ya[m] - ya[m].mean()) ** 2).sum())
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
            if np.ptp(xa[m]) > 0 and np.ptp(ya[m]) > 0:
                r = float(np.corrcoef(xa[m], ya[m])[0, 1])
        out.append(TrendLine(slope=float(slope), intercept=float(icpt), sigma=float(sigma),
                             n=n_j, share=n_j / xa.size, r2=r2, r=r))
    return TrendFit(lines=out, labels=labels, bic=bic, chosen_by="user" if fixed else "data")


def describe(line: TrendLine, log_x: bool, log_y: bool, x_name: str = "x",
             y_name: str = "y") -> str:
    """One readable sentence for a line: its equation, or its ratio on log–log axes.

    On log–log axes a line of slope near one is a fixed ratio, ``y/x =
    10**intercept``; otherwise it is a power law ``y = a x^b``.
    """
    if log_x and log_y:
        if abs(line.slope - 1) <= 0.1:
            return (f"{y_name}/{x_name} ≈ {10 ** line.intercept:.3g} (slope {line.slope:.2f}), "
                    f"{line.n:,} particles ({100 * line.share:.0f}%), R² = {line.r2:.2f}")
        return (f"{y_name} = {10 ** line.intercept:.3g}·{x_name}^{line.slope:.2f}, "
                f"{line.n:,} particles ({100 * line.share:.0f}%), R² = {line.r2:.2f}")
    sign = "+" if line.intercept >= 0 else "−"
    return (f"{y_name} = {line.slope:.3g}·{x_name} {sign} {abs(line.intercept):.3g}, "
            f"{line.n:,} particles ({100 * line.share:.0f}%), R² = {line.r2:.2f}")
