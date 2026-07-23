"""Compositional data transforms shared by the clustering modules.

Single home for the zero-replacement, log-ratio and robust scaling helpers
used by both ``results_cluster.py`` and ``results_cluster_tools.py``, so the
statistical behaviour of every pipeline is defined exactly once. The module
depends only on NumPy and is importable without Qt, matplotlib or scikit-learn.
"""

from __future__ import annotations

import numpy as np


def multiplicative_replacement(matrix, frac=0.65, threshold=None):
    """Replace zeros in a non-negative composition matrix without distorting ratios.

    Log-ratio transforms are undefined at zero, and substituting a fixed tiny
    constant such as ``1e-10`` is statistically poor for sparse, zero-inflated
    data: every zero maps to an almost identical, very large negative log value,
    so the transformed coordinates end up encoding presence/absence at enormous
    magnitude and overwhelm genuine compositional differences. This is acute for
    single-particle ICP-ToF-MS matrices, where most particles carry signal in
    only one or a few element channels.

    Multiplicative (simple) replacement substitutes a small positive ``delta``
    for each zero and rescales the non-zero parts of the same row so the row
    total is preserved, leaving the ratios among the observed parts unchanged —
    the coherence property required for compositional data. ``delta`` is a
    fraction of a per-column detection floor (by default the smallest strictly
    positive value in each column), tying the imputed value to the instrument's
    effective detection limit rather than to an arbitrary constant.

    References:
        J. A. Martín-Fernández, C. Barceló-Vidal and V. Pawlowsky-Glahn,
        "Dealing with zeros and missing values in compositional data sets using
        nonparametric imputation," *Math. Geol.* 35(3), 2003, 253-278,
        doi:10.1023/A:1023866030544.
        J. Aitchison, *The Statistical Analysis of Compositional Data*, Chapman &
        Hall, 1986.

    Args:
        matrix (np.ndarray): Non-negative matrix ``(n_samples, n_parts)``; each
            row is one composition.
        frac (float): Fraction of the per-column detection floor used as the
            imputed value; ``0.65`` follows Martín-Fernández et al. (2003).
        threshold (np.ndarray or float or None): Explicit per-column (or scalar)
            detection floor; when ``None`` the smallest strictly positive entry
            of each column is used, with ``1.0`` for all-zero columns.

    Returns:
        np.ndarray: A float64 copy with zeros replaced and row totals preserved;
            all-zero rows are filled with the per-column floor ``delta`` so
            log-ratios stay finite.
    """
    X = np.array(matrix, dtype=np.float64, copy=True)
    if X.size == 0:
        return X
    n_parts = X.shape[1]
    if threshold is None:
        floor = np.full(n_parts, np.nan)
        for j in range(n_parts):
            col = X[:, j]
            pos = col[col > 0]
            floor[j] = pos.min() if pos.size else 1.0
    else:
        floor = np.asarray(threshold, dtype=np.float64)
        if floor.ndim == 0:
            floor = np.full(n_parts, float(floor))
    floor = np.where(np.isfinite(floor) & (floor > 0), floor, 1.0)
    delta = np.clip(float(frac), 1e-9, 1.0 - 1e-9) * floor

    totals = X.sum(axis=1)
    out = X.copy()
    for i in range(X.shape[0]):
        row = X[i]
        zero = row <= 0
        if not zero.any():
            continue
        if totals[i] <= 0:
            out[i] = delta
            continue
        removed = delta[zero].sum()
        scale = 1.0 - removed / totals[i]
        if scale <= 0:
            out[i, zero] = delta[zero]
            continue
        out[i, ~zero] = row[~zero] * scale
        out[i, zero] = delta[zero]
    return out


def _apply_clr(matrix, zero_replacement='additive'):
    """Centred-log-ratio transform of a non-negative composition matrix.

    The CLR maps a composition to log values centred on the per-row geometric
    mean, giving coordinates suitable for Euclidean-distance clustering of
    compositional data. Because the logarithm is undefined at zero, zeros must
    be handled first; the strategy is selectable.

    References:
        J. Aitchison, *The Statistical Analysis of Compositional Data*, Chapman &
        Hall, 1986.
        J. A. Martín-Fernández, C. Barceló-Vidal and V. Pawlowsky-Glahn,
        "Dealing with zeros and missing values in compositional data sets using
        nonparametric imputation," *Math. Geol.* 35(3), 2003, 253-278,
        doi:10.1023/A:1023866030544.

    Args:
        matrix (np.ndarray): Data matrix ``(n_samples, n_features)``, values >= 0.
        zero_replacement (str): ``'additive'`` adds a fixed ``1e-10`` floor
            (legacy behaviour, retained as the default for reproducibility);
            ``'multiplicative'`` uses ratio-preserving, detection-limit-aware
            replacement via :func:`multiplicative_replacement`, which is the
            statistically preferred treatment for the sparse single-particle case.

    Returns:
        np.ndarray: CLR-transformed matrix.
    """
    if zero_replacement == 'multiplicative':
        X = multiplicative_replacement(matrix)
    else:
        eps = 1e-10
        X = np.where(matrix <= 0, eps, matrix.astype(np.float64))
    log_X = np.log(X)
    return log_X - log_X.mean(axis=1, keepdims=True)


def _apply_ilr(matrix, zero_replacement='additive'):
    """Isometric-log-ratio transform yielding ``p - 1`` orthonormal coordinates.

    The ILR expresses a composition in an orthonormal basis of the Aitchison
    simplex, removing the singular covariance the CLR leaves behind while
    preserving Aitchison distances. It is built on the CLR and inherits its zero
    handling.

    References:
        J. J. Egozcue, V. Pawlowsky-Glahn, G. Mateu-Figueras and C.
        Barceló-Vidal, "Isometric logratio transformations for compositional data
        analysis," *Math. Geol.* 35(3), 2003, 279-300,
        doi:10.1023/A:1023818214614.

    Args:
        matrix (np.ndarray): Data matrix ``(n_samples, n_features)``, values >= 0.
        zero_replacement (str): Passed through to :func:`_apply_clr`.

    Returns:
        np.ndarray: ILR-transformed matrix with ``p - 1`` coordinates.
    """
    clr = _apply_clr(matrix, zero_replacement=zero_replacement)
    p = clr.shape[1]
    if p < 2:
        return clr
    V = np.zeros((p, p - 1), dtype=np.float64)
    for j in range(p - 1):
        k = j + 1
        scale = np.sqrt(k / (k + 1.0))
        V[:k, j] = scale / k
        V[k, j] = -scale
    return clr @ V


def _apply_robust_zscore(matrix):
    """Robust per-column z-score using a consistent scale estimate.

    Each column is centred on its median and divided by a robust estimate of its
    standard deviation. The estimate is ``1.4826 * MAD``, where ``1.4826`` is the
    consistency constant that makes the scaled MAD an unbiased estimator of the
    standard deviation for Gaussian data. When the MAD vanishes the column
    standard deviation is used instead, and a unit scale is used only when the
    column is genuinely constant, so no sparse column can be inflated by a
    near-zero denominator.

    References:
        P. J. Rousseeuw and C. Croux, "Alternatives to the median absolute
        deviation," *J. Am. Stat. Assoc.* 88(424), 1993, 1273-1283,
        doi:10.1080/01621459.1993.10476408.

    Args:
        matrix (np.ndarray): Data matrix ``(n_samples, n_features)``.

    Returns:
        np.ndarray: Robust z-score normalised matrix with no column inflated by a
            near-zero scale.
    """
    X = matrix.astype(np.float64)
    med = np.median(X, axis=0)
    mad = np.median(np.abs(X - med), axis=0)
    scale = 1.4826 * mad
    std = np.std(X, axis=0)
    scale = np.where(scale > 1e-10, scale, std)
    scale = np.where(scale > 1e-10, scale, 1.0)
    return (X - med) / scale
