# `element_picker.py`

tools/element_picker.py

---

## Classes

### `ElementGridPopup` *(extends `QWidget`)*

Pop-up grid of every element, shown only while the user is choosing.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, items, current_index, columns, chip_qss, palette, parent=None)` |  |
| `_choose` | `(self, idx)` |  |

### `ElementPicker` *(extends `QWidget`)*

Compact element navigator for the plot header.

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
