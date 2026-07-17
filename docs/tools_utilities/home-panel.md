# `home_panel.py`

Home panel for IsotopeTrack.

---

## Classes

### `HomePanel` *(extends `QWidget`)*

Resume-focused landing panel that overlays the empty plot area.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, overlay_target=None, on_open_project=None, on_recover=None, par` |  |
| `refresh` | `(self)` | Re-read recovery sessions + recent projects and rebuild the panel. |
| `_do_recover` | `(self)` |  |
| `_open_recent` | `(self, item)` |  |
| `_restyle` | `(self)` |  |
| `paintEvent` | `(self, event)` |  |
| `eventFilter` | `(self, obj, event)` |  |
| `_disconnect` | `(self)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_recovery_sessions` | `()` | Return [(Path, datetime)] for recoverable crashed sessions, newest first. |
