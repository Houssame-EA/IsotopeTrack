# `results_table_view.py`

Fast model/view table for the Single Element and Multi-Element results.

``QTableWidget`` creates one item object per cell, so refilling a table with
thousands of particles and dozens of element columns is slow. This view keeps
the rows as plain Python values in a ``QAbstractTableModel`` and only formats
the cells Qt actually paints, the same approach as the detection parameters
table.

---

## Classes

### `ResultsTableModel` *(extends `QAbstractTableModel`)*

Rows of raw values with per-column display formats.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `rowCount` | `(self, parent=QModelIndex())` |  |
| `columnCount` | `(self, parent=QModelIndex())` |  |
| `data` | `(self, index, role=Qt.ItemDataRole.DisplayRole)` |  |
| `set_display_options` | `(self, align_numbers=False, tooltips=False)` | Right-align numeric cells and/or show each cell's text as its tooltip. |
| `set_row_brush` | `(self, func)` | Set a callable ``row -> QBrush \| None`` that tints whole rows. |
| `headerData` | `(self, section, orientation, role=Qt.ItemDataRole.DisplayRole)` |  |
| `set_table` | `(self, headers, rows, formats=None)` | Replace the whole table in one reset. |
| `clear_rows` | `(self)` | Remove every row but keep the columns. |
| `raw` | `(self, row, col)` | Return the raw value of a cell, or None when out of range. |
| `sort` | `(self, column, order=Qt.SortOrder.AscendingOrder)` | Sort the rows by one column, keeping selections on the same rows. |

### `ResultsTableView` *(extends `QTableView`)*

Read-only, sortable results table backed by :class:`ResultsTableModel`.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `set_table` | `(self, headers, rows, formats=None)` | Fill the table, keeping the current sort column and selected row numbers. |
| `clear_rows` | `(self)` | Remove every row but keep the columns. |
| `set_row_brush` | `(self, func)` | Tint whole rows; see :meth:`ResultsTableModel.set_row_brush`. |
| `set_display_options` | `(self, align_numbers=False, tooltips=False)` | See :meth:`ResultsTableModel.set_display_options`. |
| `rowCount` | `(self)` | Number of rows currently shown. |
| `columnCount` | `(self)` | Number of columns currently shown. |
| `header_text` | `(self, col)` | Return the title of column ``col``. |
| `cell_text` | `(self, row, col)` | Return the displayed text of a cell. |
| `cell_value` | `(self, row, col)` | Return the raw value of a cell. |
| `selected_row` | `(self)` | Return the first selected row, or None. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_format` | `(value, fmt)` | Return the display text for one cell. |
| `_sort_key` | `(value)` | Sort numbers numerically, then text alphabetically, blanks last. |
| `_as_number` | `(value)` | Read a cell as a number, allowing thousands separators and a percent sign. |
