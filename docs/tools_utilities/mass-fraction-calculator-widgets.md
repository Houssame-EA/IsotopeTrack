# `mass_fraction_calculator_widgets.py`

Focused UI widgets used by the mass-fraction calculator dialog.

---

## Classes

### `_CheckableSampleItem` *(extends `QWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, sample_name: str, parent=None)` |  |

### `SampleSelectionWidget` *(extends `QGroupBox`)*

Selects which samples receive values when the dialog is applied.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, sample_names: list[str], parent=None)` |  |
| `selected_samples` | `(self) → list[str]` | List of the selected samples names. |
| `apply_to_all` | `(self) → bool` | Is "apply to all" selected or not. |
| `restore_state` | `(self, state: dict) → None` | Restores the state of the widget at the last opening. |
| `_set_all_checked` | `(self, checked: bool) → None` |  |

### `_FormulaDelegate` *(extends `QStyledItemDelegate`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, compound_db: CompoundDatabase, parent=None)` |  |
| `createEditor` | `(self, parent, option, index)` |  |
| `setEditorData` | `(self, editor, index)` |  |
| `setModelData` | `(self, editor, model, index)` |  |
| `_set_compound` | `(self, row: int, compound: Compound) → None` |  |

### `_DensityDelegate` *(extends `QStyledItemDelegate`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `createEditor` | `(self, parent, option, index)` |  |
| `setModelData` | `(self, editor, model, index)` |  |

### `_StructureDelegate` *(extends `QStyledItemDelegate`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `paint` | `(self, painter, option: QStyleOptionViewItem, index)` |  |
| `editorEvent` | `(self, event, model, option, index)` |  |

### `MassFractionTableWidget` *(extends `QTableView`)*

View layer for a `MassFractionTableModel`.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, model: MassFractionTableModel, compound_db: CompoundDatabase, p` |  |

### `CalculationActionsWidget` *(extends `QWidget`)*

Buttons that are related to mass fraction data.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |

### `DialogActionsWidget` *(extends `QWidget`)*

Buttons that are related to modal window management.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
