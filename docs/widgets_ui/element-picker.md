# `element_picker.py`

tools/element_picker.py
=======================
ElementGridPopup and ElementPicker widgets — extracted from mainwindow.py to
keep that file smaller.

---

## Classes

### `ElementGridPopup` *(extends `QWidget`)*

Pop-up grid of every element, shown only while the user is choosing.

Built fresh each time it opens. The currently selected element is
highlighted. Clicking any chip emits ``selected(index)`` and closes the
pop-up. Clicking outside (or pressing Esc) just closes it.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, items, current_index, columns, chip_qss, palette, parent=None)` |  |
| `_choose` | `(self, idx)` |  |

### `ElementPicker` *(extends `QWidget`)*

Compact element navigator for the plot header.

Three small controls: a left arrow (previous element), a grid button that
opens :class:`ElementGridPopup`, and a right arrow (next element). No
element name is shown. Activating any of them emits
``elementActivated(element_key)``; the host commits the change and calls
:meth:`set_current_key` to keep this widget in sync.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, columns=7, parent=None)` |  |
| `set_chip_style` | `(self, qss)` |  |
| `apply_button_style` | `(self, p)` |  |
| `set_elements` | `(self, items)` | ``items``: list of ``(element_key, label)`` in display order. |
| `current_key` | `(self)` |  |
| `set_current_key` | `(self, key, emit=False)` |  |
| `_update_enabled` | `(self)` |  |
| `_emit_index` | `(self, i)` |  |
| `_step` | `(self, delta)` |  |
| `_on_popup_selected` | `(self, idx)` |  |
| `_open_popup` | `(self)` |  |
| `_on_popup_destroyed` | `(self)` |  |
| `eventFilter` | `(self, obj, event)` |  |
