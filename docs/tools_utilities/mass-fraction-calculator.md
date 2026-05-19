# `mass_fraction_calculator.py`

---

## Constants

| Name | Value |
|------|-------|
| `_TOKEN_RE` | `re.compile('([A-Z][a-z]?|\\(|\\))(\\d*(?:\\.\\d...` |
| `_ELEMENT_ORDER_RE` | `re.compile('([A-Z][a-z]?)')` |

## Classes

### `CSVCompoundDatabase`

Database loader for materials from CSV with signature-based lookup.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` |  |
| `auto_load_csv` | `(self) → bool` | Try to load CSV from standard locations, preferring trimmed/compressed versions. |
| `load_csv` | `(self, csv_path: str | Path) → bool` | Load CSV and build signature-based indices. |
| `_signature_for_formula` | `(self, formula: str) → str` | Args: |
| `get_data_by_formula_or_signature` | `(self, formula: str) → list[dict]` | Args: |
| `best_density_for_formula` | `(self, formula: str) → float` | Args: |
| `best_url_for_formula` | `(self, formula: str) → str` | Args: |
| `get_compounds_for_element` | `(self, element: str) → list[dict]` | Get one entry per canonical formula for initial browsing. |
| `get_variants_for_formula` | `(self, formula: str) → list[dict]` | Get ALL polymorphs/structures for a given formula. |
| `get_material_data` | `(self, formula: str) → list[dict]` | Args: |

### `FormulaComboBox` *(extends `QComboBox`)*

Editable combobox for chemical formulas with debounced filtering.

Key design decisions that prevent the old recursion crash:
1. Both the combobox AND lineEdit signals are blocked during rebuilds
2. Filtering is debounced (300 ms) so rapid typing doesn't queue rebuilds
3. Only the top MAX_DROPDOWN_ITEMS matches are shown, not thousands
4. Minimum 2 characters before filtering starts (avoids huge result sets)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, element: str, csv_database: CSVCompoundDatabase, tracked_elemen` | Args: |
| `_setup_compounds` | `(self)` | Build the full item list but only load a capped subset into the widget. |
| `_rebuild_items` | `(self, items: list[dict])` | Replace dropdown items, blocking ALL signals to prevent recursion. |
| `_do_filter` | `(self)` | Actually perform the filter (called by debounce timer). |
| `filter_to_formula` | `(self, user_canon_formula: str)` | Show all polymorphs/structures for the confirmed formula. |
| `reset_items` | `(self)` | Restore the capped default list. |
| `_set_editor_text` | `(self, text: str)` | Set the lineEdit text without triggering any slots. |
| `current_formula` | `(self) → str` | Returns: |
| `_on_text_changed` | `(self, text: str)` | Debounce: restart timer on every keystroke, filter when typing pauses. |
| `_on_item_activated` | `(self, index: int)` | Args: |
| `_on_editing_finished` | `(self)` |  |

### `CheckableListItem` *(extends `QWidget`)*

Compact widget with checkbox + label for sample list.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, sample_name: str, parent = None)` | Args: |
| `is_checked` | `(self) → bool` | Returns: |
| `set_checked` | `(self, checked: bool)` | Args: |

### `_PositiveDoubleDelegate` *(extends `QStyledItemDelegate`)*

Only accept positive floats when editing density cells.

| Method | Signature | Description |
|--------|-----------|-------------|
| `createEditor` | `(self, parent, option, index)` | Args: |
| `setEditorData` | `(self, editor, index)` | Args: |
| `setModelData` | `(self, editor, model, index)` | Args: |

### `MassFractionCalculator` *(extends `QDialog`)*

Mass fraction calculator with sample selection and molecular weight calculations.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, selected_isotopes: dict, periodic_table_widget, parent = None)` | Args: |
| `apply_theme` | `(self)` | Apply the currently active theme palette to this dialog. |
| `closeEvent` | `(self, event)` | Disconnect theme signal so we don't leak slots on closed dialogs. |
| `_build_stylesheet` | `(self) → str` | Dark/light aware stylesheet for the whole dialog. |
| `_refresh_db_status_style` | `(self)` |  |
| `_refresh_apply_button_style` | `(self)` |  |
| `_setup_ui` | `(self)` |  |
| `_build_sample_panel` | `(self) → QGroupBox` | Returns: |
| `_build_header` | `(self) → QHBoxLayout` | Returns: |
| `_build_table` | `(self)` |  |
| `_build_buttons` | `(self) → QHBoxLayout` | Returns: |
| `_populate_table` | `(self)` |  |
| `_make_readonly_item` | `(text: str) → QTableWidgetItem` | Args: |
| `_element_data` | `(self, symbol: str) → dict | None` | Args: |
| `_current_formula` | `(self, row: int) → str` | Args: |
| `_calc_mass_fraction` | `(self, row: int, formula: str)` | Args: |
| `_calc_molecular_weight` | `(self, row: int, formula: str)` | Args: |
| `_on_compound_selected` | `(self, row: int, formula: str, density_csv: float)` | Args: |
| `_highlight_tracked` | `(self, row: int, formula: str)` | Set a tooltip showing which elements in the compound are being tracked. |
| `_calculate_all` | `(self)` |  |
| `_reset_to_default` | `(self)` |  |
| `_select_all_samples` | `(self)` |  |
| `_select_no_samples` | `(self)` |  |
| `_get_selected_samples` | `(self) → list[str]` | Returns: |
| `_save_state` | `(self)` |  |
| `_restore_previous_state` | `(self)` |  |
| `_manual_load_csv` | `(self)` |  |
| `_open_structure` | `(self, row: int)` | Args: |
| `_apply_mass_fractions` | `(self)` |  |
| `closeEvent` | `(self, event)` | Args: |
| `reject` | `(self)` |  |

## Functions

### `_parse_formula_to_counts`

```python
def _parse_formula_to_counts(formula: str) → dict
```

Parse a chemical formula string into {element: integer_count}.

Handles parenthesised groups such as Ca(OH)2 → {'Ca': 1, 'O': 2, 'H': 2}.
Nested parentheses are supported.


**Args:**

- `formula: Chemical formula string.`


**Returns:**

- `dict mapping element symbols to positive integer counts.`

### `_safe_int`

```python
def _safe_int(s: str, default: int = 1) → int
```

Convert a numeric string to a positive int, rounding floats.

**Args:**

- `s (str): The s.`
- `default (int): The default.`

**Returns:**

- `int: Result of the operation.`

### `_element_order_in_formula`

```python
def _element_order_in_formula(formula: str) → list[str]
```

Return elements in the order they first appear in *formula*.

**Args:**

- `formula (str): The formula.`

**Returns:**

- `list[str]: Result of the operation.`

### `_reduce_counts`

```python
def _reduce_counts(counts: dict) → dict
```

Divide all counts by their GCD to get the empirical formula.

**Args:**

- `counts (dict): The counts.`

**Returns:**

- `dict: Result of the operation.`

### `_signature_from_counts`

```python
def _signature_from_counts(counts: dict) → str
```

Order-independent canonical key for matching equivalent formulas.

**Args:**

- `counts (dict): The counts.`

**Returns:**

- `str: Result of the operation.`

### `_join_formula_from_counts`

```python
def _join_formula_from_counts(counts: dict, prefer_order: list[str] | None = None) → str
```

Build a human-readable formula string from counts.

**Args:**

- `counts (dict): The counts.`
- `prefer_order (list[str] | None): The prefer order.`

**Returns:**

- `str: Result of the operation.`

### `canonicalize_preserve_user_order`

```python
def canonicalize_preserve_user_order(formula: str) → str
```

Reduce stoichiometry but preserve the user's element order.

**Args:**

- `formula (str): The formula.`

**Returns:**

- `str: Result of the operation.`
