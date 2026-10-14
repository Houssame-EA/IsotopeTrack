# `theme_switch.py`

Sliding light/dark switch for window headers.

A rounded track with a sun on the left and a moon on the right; a knob
slides over the active side. It is a checkable button: checked means dark.
Colours come from the application palette and are refreshed with
:meth:`ThemeSwitch.set_palette`.

---

## Constants

| Name | Value |
|------|-------|
| `_SUN_ON` | `'#f39c12'` |
| `_MOON_ON` | `'#f5d76e'` |

## Classes

### `ThemeSwitch` *(extends `QAbstractButton`)*

Sliding sun / moon switch; checked means dark mode.

Args:
    parent: Parent widget.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `sizeHint` | `(self)` |  |
| `_get_offset` | `(self)` |  |
| `_set_offset` | `(self, value)` |  |
| `_slide` | `(self, checked)` |  |
| `set_dark` | `(self, dark)` | Show the given mode without emitting signals. |
| `set_palette` | `(self, p)` | Take the track, knob and icon colours from an application palette. |
| `paintEvent` | `(self, _event)` |  |
