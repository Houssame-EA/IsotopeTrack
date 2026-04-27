# `info_file.py`

File information display dialogs and menus for viewing method and run information.

---

## Classes

### `InfoPalette`

Colour tokens used by the file-info dialog and its sub-widgets.
All fields are hex strings.

### `Divider` *(extends `QFrame`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |

### `SectionHeader` *(extends `QWidget`)*

Compact section title with accent bar on the left.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, title, parent = None)` | Args: |

### `ParamRow` *(extends `QWidget`)*

Single label/value row with optional unit.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, label, value, unit = '', alternate = False, parent = None)` | Args: |

### `StatusRow` *(extends `QWidget`)*

Label/value row where value is coloured by enabled/disabled state.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, label, enabled, alternate = False, parent = None)` | Args: |

### `Card` *(extends `QWidget`)*

White card with border and title, containing stacked rows.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, title, parent = None)` | Args: |
| `add_row` | `(self, label, value, unit = '')` | Args: |
| `add_status_row` | `(self, label, enabled)` | Args: |
| `add_divider` | `(self, sub_title)` | Add a visual sub-group divider with a label. |

### `SummaryBar` *(extends `QWidget`)*

Dark top bar showing key stats at a glance.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, stats, parent = None)` | Args: |

### `FileInfoDialog` *(extends `QDialog`)*

Dialog for displaying detailed file information.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, sample_name, run_info, method_info, time_array, masses, parent ` | Args: |
| `_rebuild` | `(self, *_)` | Re-create the entire UI so every sub-widget picks up the new |
| `setup_ui` | `(self)` |  |
| `_insert_card` | `(self, card)` | Insert card before the trailing stretch. |
| `_build_content` | `(self)` |  |
| `_build_method_card` | `(self, segment)` | Args: |
| `_build_run_info_card` | `(self)` |  |

### `FileInfoMenu`

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_menu` | `(sample_name, run_info, method_info, time_array, masses, parent = None` | Args: |
| `show_file_info` | `(sample_name, run_info, method_info, time_array, masses, parent = None` | Args: |

## Functions

### `info_palette`

```python
def info_palette() → InfoPalette
```

Build the card-UI palette from the current global theme.

Keeps the distinctive "dark navy header + light body" identity in
light mode, and switches to an all-dark variant that still separates
the header from the body via contrasting brightness.

**Returns:**

- `InfoPalette: Result of the operation.`
