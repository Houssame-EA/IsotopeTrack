# `mass_fraction_table_model.py`

Model and calculation state for the mass-fraction table.

---

## Constants

| Name | Value |
|------|-------|
| `HEADERS` | `('Element', 'Compound Formula', 'Mass Fraction', 'Molecul…` |

## Classes

### `MassFractionColumn` *(extends `IntEnum`)*

Enum of the columns in the mass fraction with their index.

### `MassFractionRow`

Dataclass that contains the data related to one row of the mass
fraction table.

### `MassFractionTableModel` *(extends `QAbstractTableModel`)*

Owns editable mass-fraction data, validation, and derived values.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, selected_isotopes: dict, periodic_table_info: PeriodicTableInfo` |  |
| `_initial_rows` | `(self, selected_isotopes: dict) → list[MassFractionRow]` |  |
| `rowCount` | `(self, parent: QModelIndex \| QPersistentModelIndex=QModelIndex())` |  |
| `columnCount` | `(self, parent: QModelIndex \| QPersistentModelIndex=QModelIndex())` |  |
| `headerData` | `(self, section: int, orientation: Qt.Orientation, role: int=Qt.ItemDat` |  |
| `data` | `(self, index: QModelIndex \| QPersistentModelIndex, role: int=Qt.ItemDa` |  |
| `flags` | `(self, index: QModelIndex \| QPersistentModelIndex)` |  |
| `setData` | `(self, index: QModelIndex \| QPersistentModelIndex, value: Any, role: i` |  |
| `set_compound` | `(self, row_number: int, compound: Compound) → None` | Sets compound for a certain row and updates all |
| `reset_to_pure_elements` | `(self) → None` | Resets the model to the pure element state. |
| `recalculate_all` | `(self) → None` | Recalculate all mass fractions and molecular weights. |
| `export_values` | `(self) → dict` | Data for the `MassFractionService`. |
| `save_state` | `(self) → dict` | Saves the state of the model by returning a `dict` |
| `restore_state` | `(self, state: dict) → None` | Restores the previous state of the model by formulas and densities. |
| `_mass_fraction` | `(self, target_element: str, formula: str) → float` |  |
| `_molecular_weight` | `(self, fallback_element: str, formula: str) → float` |  |
| `_formula_tooltip` | `(self, formula: str, base_element: str) → str` |  |
| `_emit_row_changed` | `(self, row: int) → None` |  |
| `_emit_all_changed` | `(self) → None` |  |
| `_formula_has_unknown_elements` | `(self, formula)` |  |
| `_formula_has_base_element` | `(self, formula, element)` |  |
