# `flow_layout.py`

A layout that places widgets left to right and wraps onto new lines.

---

## Classes

### `FlowLayout` *(extends `QLayout`)*

Lays widgets out left to right and starts a new line when the row is full.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None, spacing=2)` |  |
| `addItem` | `(self, item)` |  |
| `count` | `(self)` |  |
| `itemAt` | `(self, index)` |  |
| `takeAt` | `(self, index)` |  |
| `expandingDirections` | `(self)` |  |
| `hasHeightForWidth` | `(self)` |  |
| `heightForWidth` | `(self, width)` |  |
| `setGeometry` | `(self, rect)` |  |
| `sizeHint` | `(self)` |  |
| `minimumSize` | `(self)` |  |
| `_arrange` | `(self, rect, apply)` | Place the visible items in rows; return the total height used. |
