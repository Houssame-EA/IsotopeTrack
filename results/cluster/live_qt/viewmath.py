"""View framing, rotation and tick selection.

Pure functions of the view state plus the pane size, deliberately free of any
Qt import so they can be unit-tested without a running application.

The 2-D screen mapping is kept even though pyqtgraph's ``ViewBox`` has its own
transform, because focusing a cluster has to reproduce an exact framing and
clamp rule that the ViewBox does not express directly.
"""

from __future__ import annotations

import math
import time

import numpy as np


def now_ms():
    """Return a monotonic timestamp in milliseconds.

    Returns:
        float: Milliseconds from an arbitrary origin.
    """
    return time.perf_counter() * 1000.0


def ease(k):
    """Apply an ease-in-out cubic curve.

    Args:
        k (float): Progress in [0, 1].

    Returns:
        float: Eased progress in [0, 1].
    """
    return 4 * k * k * k if k < 0.5 else 1 - ((-2 * k + 2) ** 3) / 2


def data_bounds2(xy):
    """Return the bounding box of the 2-D point cloud.

    Args:
        xy (array-like | None): Point coordinates.

    Returns:
        list[float] | None: ``[x0, y0, x1, y1]``, or None when empty.
    """
    if xy is None or len(xy) == 0:
        return None
    a = np.asarray(xy)
    return [float(a[:, 0].min()), float(a[:, 1].min()),
            float(a[:, 0].max()), float(a[:, 1].max())]


def ux(S, px):
    """Convert a screen x back to a data x in the 2-D view.

    Args:
        S (LiveState): The view state.
        px (float): Screen coordinate.

    Returns:
        float: Data coordinate.
    """
    return (px - S.view.ox) / S.view.scale


def uy(S, py):
    """Convert a screen y back to a data y in the 2-D view.

    Args:
        S (LiveState): The view state.
        py (float): Screen coordinate.

    Returns:
        float: Data coordinate.
    """
    return (S.view.oy - py) / S.view.scale


def data_bounds3(S, mask=None):
    """Return the per-axis minimum and maximum of the 3-D embedding.

    Args:
        S (LiveState): The view state.
        mask (array-like | None): Optional boolean row selector. Used to narrow
            the range to a focused cluster, so its axes read at the resolution
            of that cluster rather than of the whole cloud. Ignored when it does
            not match the data or leaves fewer than two points.

    Returns:
        tuple | None: ``(lo, hi)``, each a length-3 array in data units, or
        None when there is no usable data.
    """
    P = np.asarray((S.data or {}).get('xy'), dtype=float)
    if P.ndim != 2 or P.size == 0:
        return None
    if P.shape[1] < 3:
        P = np.column_stack([P[:, :2], np.zeros(len(P))])
    P = P[:, :3]
    if mask is not None:
        mask = np.asarray(mask)
        if mask.shape == (len(P),) and int(mask.sum()) >= 2:
            P = P[mask]
    P = P[np.isfinite(P).all(axis=1)]
    if not len(P):
        return None
    return P.min(axis=0), P.max(axis=0)


def cloud_center(S):
    """Centre of the 3-D data range, used as the pivot for rotation.

    Args:
        S (LiveState): The view state.

    Returns:
        numpy.ndarray: An ``(x, y, z)`` point, the origin when there is no data.
    """
    b = data_bounds3(S)
    if b is None:
        return np.zeros(3)
    lo, hi = b
    return (np.asarray(lo, float) + np.asarray(hi, float)) / 2.0


def rot_matrix(S):
    """Build the rotation matrix for the current azimuth and elevation.

    Args:
        S (LiveState): The view state, read for ``rot['az']`` and ``rot['el']``.

    Returns:
        numpy.ndarray: A ``(3, 3)`` rotation matrix.
    """
    az = float(S.rot.get('az', 0.0))
    el = float(S.rot.get('el', 0.0))
    ca, sa = math.cos(az), math.sin(az)
    ce, se = math.cos(el), math.sin(el)
    ry = np.array([[ca, 0.0, sa], [0.0, 1.0, 0.0], [-sa, 0.0, ca]])
    rx = np.array([[1.0, 0.0, 0.0], [0.0, ce, -se], [0.0, se, ce]])
    return rx @ ry


def rotate3(S, P, center=True):
    """Rotate points into the plane the scatter draws.

    The result stays in *data* coordinates rather than screen coordinates: the
    ViewBox owns pan and zoom, so the rotation only has to orient the cloud.
    Rotating about :func:`cloud_center` and putting the centre back leaves the
    cloud spinning in place instead of swinging away from the framed range.

    Args:
        S (LiveState): The view state.
        P (array-like): An ``(n, 2+)`` array of points.
        center (bool): Rotate about the cloud centre. Pass False for direction
            vectors such as the biplot loadings, which carry no position.

    Returns:
        numpy.ndarray: An ``(n, 3)`` array of ``[x, y, depth]``. In 2-D the
        first two columns are unchanged and depth is 0.
    """
    P = np.asarray(P, dtype=float)
    if P.ndim != 2 or P.size == 0:
        return np.zeros((0, 3))
    Q = P[:, :3] if P.shape[1] >= 3 else np.column_stack(
        [P[:, :2], np.zeros(len(P))])
    if S.cur_dims() != 3:
        return np.column_stack([Q[:, 0], Q[:, 1], np.zeros(len(Q))])
    c = cloud_center(S) if center else np.zeros(3)
    out = (Q - c) @ rot_matrix(S).T
    if center:
        out[:, 0] += c[0]
        out[:, 1] += c[1]
    return out


def nice_ticks(lo, hi, target):
    """Choose round tick values spanning a range.

    Steps are the usual 1, 2 or 5 times a power of ten.

    Args:
        lo (float): Lower bound in data units.
        hi (float): Upper bound in data units.
        target (int): Roughly how many ticks are wanted.

    Returns:
        tuple[list[float], float]: The tick values and the step between them.
        Empty when the range is degenerate or non-finite, which callers treat
        as "draw no ticks" rather than as an error.
    """
    if not (hi > lo) or not math.isfinite(lo) or not math.isfinite(hi):
        return [], 1.0
    raw = (hi - lo) / max(1, target)
    mag = 10 ** math.floor(math.log10(raw))
    n = raw / mag
    step = (1 if n < 1.5 else 2 if n < 3 else 5 if n < 7 else 10) * mag
    values = []
    v = math.ceil(lo / step) * step
    while v <= hi + step * 1e-6:
        values.append(0.0 if abs(v) < step * 1e-6 else v)
        if len(values) > 200:
            break
        v += step
    return values, step


def exp_str(v, digits=1):
    """Format a value in exponential form without a padded exponent.

    Python's ``%e`` writes ``1.2e-04``; this writes ``1.2e-4``, which is what
    the axis labels want.

    Args:
        v (float): The value.
        digits (int): Digits after the decimal point in the mantissa.

    Returns:
        str: The formatted value.
    """
    s = '%.*e' % (digits, v)
    mant, _, exp = s.partition('e')
    sign = '-' if exp[0] == '-' else ''
    return '%se%s%s' % (mant, sign, exp[1:].lstrip('0') or '0')


def fmt_tick(v, step):
    """Format a tick value at a precision suited to the step between ticks.

    Args:
        v (float): The value.
        step (float): Spacing between ticks.

    Returns:
        str: Display text.
    """
    if v == 0:
        return '0'
    a = abs(step)
    if a >= 1e4 or a < 1e-3:
        return exp_str(v)
    return '%.*f' % (max(0, math.ceil(-math.log10(a))), v)
