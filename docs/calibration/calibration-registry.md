# `calibration_registry.py`

Single source of truth for IsotopeTrack's calibration methods.

There are two families:

* **Transport-rate methods.** Each has a *display label* — shown in the UI and
  stored in saved projects (e.g. ``"Liquid weight"``) — and a *signal name* —
  the string the calibration window emits to
  ``MainWindow.handle_calibration_result`` (e.g. ``"Weight Method"``). These two
  naming schemes were previously duplicated, by hand, across ~13 modules.
* **Ionic calibration.** A single method, :data:`IONIC`.

Centralising the names, their mapping, and their order here means adding a
transport-rate method is a single :func:`register_transport` call (plus wiring
the method's widget in ``calibration_methods/TE.py``), instead of editing string
literals in many files.

The module imports nothing heavy (no PySide6), so the name data is unit-testable
without a display server — see ``tests/test_calibration_registry.py``.

---

## Constants

| Name | Value |
|------|-------|
| `_TRANSPORT` | `[]` |
| `IONIC` | `'Ionic Calibration'` |

## Classes

### `TransportMethod`

One transport-rate calibration method.

Args:
    label: Display name, also the value stored in saved projects
        (e.g. ``"Liquid weight"``).
    signal_name: Name emitted to ``handle_calibration_result``
        (e.g. ``"Weight Method"``).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, label, signal_name)` |  |
| `__repr__` | `(self)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `register_transport` | `(method)` | Register a :class:`TransportMethod` (returns it). |
| `transport_methods` | `()` | All transport methods in registration order. |
| `default_transport_labels` | `()` | Ordered display labels, e.g. ``['Liquid weight', 'Number based', 'Mass based']``. |
| `transport_signal_names` | `()` | Signal names the calibration window emits, e.g. ``['Weight Method', ...]``. |
| `label_to_signal_map` | `()` | Display label -> signal name (the old ``_METHOD_SIGNAL_MAP``). |
| `is_ionic` | `(name)` | True if ``name`` is the ionic calibration method. |
| `is_transport_signal` | `(name)` | True if ``name`` is one of the transport-rate *signal* names. |
