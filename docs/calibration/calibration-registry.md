# `calibration_registry.py`

Single source of truth for IsotopeTrack's calibration methods.

---

## Constants

| Name | Value |
|------|-------|
| `_TRANSPORT` | `[]` |
| `IONIC` | `'Ionic Calibration'` |

## Classes

### `TransportMethod`

One transport-rate calibration method.

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
