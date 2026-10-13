# `frozen_column.py`

Keep the first columns of a table in place while it scrolls sideways.

---

## Classes

### `FrozenColumns` *(extends `QTableView`)*

An overlay that keeps the first *count* columns of a table visible.

It is a second view of the same model and selection model, drawn over
the left edge of the table and showing only the frozen columns, so
editing, selection, copy/paste, the context menu and cell clicks act on
the table exactly as before. Column widths, row heights and vertical
scrolling follow the table.

Args:
    table: The QTableView or QTableWidget to freeze columns of.
    count: Number of leading columns to keep in place.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, table, count=1)` |  |
| `_sync` | `(self, *_)` | Show only the frozen columns, at the table's widths and heights. |
| `_sync_now` | `(self)` |  |
| `_on_column_resized` | `(self, column, _old, new)` |  |
| `_on_row_resized` | `(self, row, _old, new)` |  |
| `_update_geometry` | `(self)` | Place the overlay over the frozen columns of the table. |
| `_place` | `(self)` |  |
| `_forward_click` | `(self, index)` | Report clicks as clicks on the table, and give it the keyboard. |
| `_forward_context_menu` | `(self, pos)` | Open the table's own context menu at the same place. |

### `_ResizeWatcher` *(extends `QObject`)*

Calls *callback* whenever a watched widget is resized or shown.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, callback)` |  |
| `eventFilter` | `(self, obj, event)` |  |
