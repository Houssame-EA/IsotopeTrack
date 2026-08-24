"""Defensive numeric formatting for text output (CSV exports, tables, logs).

Only numpy is imported, so this module is safe to import and unit-test without
PySide6.

Why this exists
---------------
Python's f-string format specs are applied by ``__format__``. ``np.ndarray``
implements that only for 0-d arrays; anything with ``ndim >= 1`` raises::

    TypeError: unsupported format string passed to numpy.ndarray.__format__

Several quantities in IsotopeTrack are scalars in the ordinary case and arrays
in others — ``threshold`` and ``background`` become full-length arrays when a
moving-window background is enabled, and values reloaded from third-party or
older project files can arrive as size-1 arrays. Formatting those directly
aborts the file being written, so every value is unwrapped first.
"""
from __future__ import annotations

import logging

import numpy as np

_itk_log = logging.getLogger("IsotopeTrack.utils.numeric_format")


def as_scalar(value):
    """Collapse a numpy value to something an f-string can format.

    Empty arrays become ``0.0``. Arrays of size 1 collapse to their single
    element, whatever their shape. Larger arrays collapse to their mean — the
    same summary the detection engine already applies to window-mode
    thresholds — and log a warning, since receiving one here means an upstream
    value kept a shape it was not expected to have.

    Args:
        value: Any value bound for a format spec.

    Returns:
        A plain Python float for numpy inputs, otherwise ``value`` unchanged.
    """
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return 0.0
        if value.size == 1:
            return float(value.reshape(-1)[0])
        _itk_log.warning(
            "Received an array of size %d where a scalar was expected; "
            "using its mean", value.size)
        return float(np.mean(value))
    if isinstance(value, np.generic):
        return value.item()
    return value


def fmt(value, spec, fallback="N/A"):
    """Format ``value`` with ``spec`` without ever raising.

    A single unformattable cell used to abort a whole export file, losing every
    particle already written. The cell now degrades to ``fallback`` and the
    export completes.

    Args:
        value: Value to render. Passed through :func:`as_scalar` first.
        spec (str): Format spec without the colon, e.g. ``".4f"`` or ``".2e"``.
        fallback (str): Text used when the value cannot be formatted, which
            covers ``None``, strings, and any type the spec does not accept.

    Returns:
        str: The formatted value, or ``fallback``.
    """
    try:
        return format(as_scalar(value), spec)
    except (TypeError, ValueError):
        _itk_log.warning("Could not format %r with %r; wrote %s",
                         value, spec, fallback)
        return fallback
