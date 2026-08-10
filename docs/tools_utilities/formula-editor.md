# `formula_editor.py`

This module contains the formula editor, a `QLineEdit` that can have
compound prediction that dispatches known compound information through a
signal.

---

## Classes

### `DirectQCompleter` *(extends `QCompleter`)*

Enables a `QCompleter` to show all model results regardless of the input

| Method | Signature | Description |
|--------|-----------|-------------|
| `splitPath` | `(self, _, /)` |  |

### `FormulaEditor` *(extends `QLineEdit`)*

Formula editor with compound completion. When editing, the changes can
be observed by other component.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, compound_db: CompoundDatabase, default_formula: str='', parent:` |  |
| `_setup_completion` | `(self)` |  |
| `_formula_selected` | `(self, index: QModelIndex)` |  |
| `set_formula` | `(self, formula: str)` | Sets the formula and notifies. |
| `reset_formula` | `(self)` | Resets the formula to what it originally was. |
| `formula` | `(self) → str` |  |
| `formula` | `(self, value: str)` |  |
| `_set_formula_no_notify` | `(self, formula: str)` |  |
