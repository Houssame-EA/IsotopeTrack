# `numeric_format.py`

Defensive numeric formatting for text output (CSV exports, tables, logs).

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

---

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `as_scalar` | `(value)` | Collapse a numpy value to something an f-string can format. |
| `fmt` | `(value, spec, fallback='N/A')` | Format ``value`` with ``spec`` without ever raising. |
