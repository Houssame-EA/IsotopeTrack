# `parameters_table.py`

Drop-in replacement for the QTableWidget used as the parameters table in
IsotopeTrack.

---

## Constants

| Name | Value |
|------|-------|
| `COL_ELEMENT` | `0` |
| `COL_INCLUDE` | `1` |
| `COL_METHOD` | `2` |
| `COL_SIGMA` | `3` |
| `COL_THRESHOLD` | `4` |
| `COL_MIN_CONT` | `5` |
| `COL_ALPHA` | `6` |
| `COL_ITERATIVE` | `7` |
| `COL_WINDOW` | `8` |
| `COL_INTEG` | `9` |
| `COL_SPLIT` | `10` |
| `COL_VALLEY` | `11` |
| `NUM_COLUMNS` | `12` |
| `_HEADERS` | `['Element', 'Include', 'Detection Method', 'Sigma', 'Manu…` |
| `_TOOLTIPS` | `['element', 'include in analysis', 'detection method', 'p…` |
| `METHOD_OPTIONS` | `['Manual', 'Compound Poisson LogNormal', 'CPLN table']` |
| `INTEG_OPTIONS` | `['Background', 'Threshold', 'Midpoint']` |
| `SPLIT_OPTIONS` | `['No Splitting', '1D Watershed']` |
| `_SIGMA_HIGHLIGHT_LIGHT` | `'#FFF3CD'` |
| `_SIGMA_HIGHLIGHT_DARK` | `'#3a3a1f'` |
| `_SUP` | `str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')` |
| `_FIELD_TO_COL` | `{'include': COL_INCLUDE, 'method': COL_METHOD, 'sigma': C…` |
| `_DEFAULT_COL_WIDTHS` | `{0: 80, 1: 50, 2: 155, 3: 130, 4: 130, 5: 100, 6: 130, 7:…` |

## Classes

### `ParametersModel` *(extends `QAbstractTableModel`)*

Stores all parameter data as a list of plain Python dicts.
No Qt widgets are ever created here.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `rowCount` | `(self, parent=QModelIndex())` |  |
| `columnCount` | `(self, parent=QModelIndex())` |  |
| `headerData` | `(self, section, orientation, role=Qt.DisplayRole)` |  |
| `flags` | `(self, index)` |  |
| `data` | `(self, index, role=Qt.DisplayRole)` |  |
| `setData` | `(self, index, value, role=Qt.EditRole)` |  |
| `_emit_row` | `(self, row, roles)` |  |
| `populate` | `(self, rows)` |  |
| `clear` | `(self)` |  |
| `row_data` | `(self, row)` |  |
| `set_field` | `(self, row, field, value, emit_changed=False)` |  |
| `set_row_colors` | `(self, row, bg=None, fg=None)` |  |
| `bulk_update` | `(self)` |  |

### `ParametersDelegate` *(extends `QStyledItemDelegate`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `paint` | `(self, painter, option, index)` |  |
| `_paint_check` | `(painter, rect, checked, option)` |  |
| `editorEvent` | `(self, event, model, option, index)` |  |
| `createEditor` | `(self, parent, option, index)` |  |
| `setEditorData` | `(self, editor, index)` |  |
| `setModelData` | `(self, editor, model, index)` |  |
| `updateEditorGeometry` | `(self, editor, option, index)` |  |

### `ParametersTableView` *(extends `QTableView`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `populate` | `(self, rows)` |  |
| `get_row_params` | `(self, row)` |  |
| `set_row_field` | `(self, row, field, value, emit_changed=False)` |  |
| `set_row_colors` | `(self, row, bg=None, fg=None)` |  |
| `rowCount` | `(self)` |  |
| `columnCount` | `(self)` |  |
| `currentRow` | `(self)` |  |
| `setCurrentCell` | `(self, row, col)` |  |
| `item` | `(self, row, col)` |  |
| `setRowCount` | `(self, n)` |  |
| `setColumnCount` | `(self, n)` |  |
| `setHorizontalHeaderLabels` | `(self, labels)` |  |
| `horizontalHeaderItem` | `(self, col)` |  |
| `insertRow` | `(self, row)` |  |
| `setItem` | `(self, row, col, item)` |  |
| `setCellWidget` | `(self, row, col, widget)` |  |
| `cellWidget` | `(self, row, col)` |  |
| `setSelectionBehavior` | `(self, behavior)` |  |
| `setEditTriggers` | `(self, triggers)` |  |

### `_ItemProxy`

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, model, row, col)` |  |
| `text` | `(self)` |  |
| `setBackground` | `(self, brush)` |  |
| `setForeground` | `(self, brush)` |  |
| `setFlags` | `(self, flags)` |  |
| `__bool__` | `(self)` |  |

### `_CellProxy`

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, model, row, col)` |  |
| `_d` | `(self)` |  |
| `isChecked` | `(self)` |  |
| `currentText` | `(self)` |  |
| `value` | `(self)` |  |
| `setValue` | `(self, v)` |  |
| `blockSignals` | `(self, block)` |  |
| `setEnabled` | `(self, enabled)` |  |
| `setStyleSheet` | `(self, qss)` |  |
| `findChild` | `(self, type_, name='')` |  |
| `__bool__` | `(self)` |  |

### `_WindowChildProxy`

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, model, row, *, is_checkbox)` |  |
| `isChecked` | `(self)` |  |
| `value` | `(self)` |  |
| `setEnabled` | `(self, enabled)` |  |
| `__bool__` | `(self)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_fmt_alpha` | `(v)` | Return alpha as compact scientific notation, e.g. 1x10^-6. |
| `_display` | `(d, col)` |  |
| `_edit_value` | `(d, col)` |  |
| `_apply_edit` | `(d, col, value)` |  |
| `_is_cell_disabled` | `(d, col)` |  |
