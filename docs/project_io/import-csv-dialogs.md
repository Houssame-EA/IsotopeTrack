# `import_csv_dialogs.py`

---

## Constants

| Name | Value |
|------|-------|
| `DELIMITED_EXTS` | `{'.csv', '.txt'}` |
| `EXCEL_EXTS` | `{'.xls', '.xlsx', '.xlsm', '.xlsb'}` |
| `PREVIEW_MAX_ROWS` | `20` |
| `LOAD_SAMPLE_ROWS` | `100` |
| `_ISOTOPE_RE` | `re.compile('(?:Mass[_\\s]*|M(?=\\d))?(?:(\\d{1,...` |

## Classes

### `CSVPreviewTableWidget` *(extends `QTableWidget`)*

Themed preview table; column selection enabled for mapping.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `_apply_theme` | `(self, *_)` | Args: |
| `highlight_column` | `(self, column: int, color: QColor | None = None)` | Tint every cell in ``column`` with ``color`` (default = accent_soft). |
| `clear_column_highlight` | `(self, column: int)` | Reset column cells to the default (alternating) background. |

### `IsotopeBadgeBar` *(extends `QWidget`)*

Horizontal strip of one clickable badge per data column, positioned
directly above the preview table. Each badge shows the current isotope
mapping (or a faint '+ assign' placeholder) and opens an isotope picker
popover on click.

We use a widget strip (rather than custom-painted header labels) because
QHeaderView does not natively host arbitrary widgets, and this approach
gives us full theming/hover/popover control with minimal fuss.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `sync_with_columns` | `(self, column_widths: list[int])` | Create one badge per column, with widths matching the preview table. |
| `set_mapping` | `(self, column_index: int, isotope: dict | None)` | Update the badge for one column (None = unmapped). |
| `update_widths` | `(self, column_widths: list[int])` | Re-apply widths after the preview table resizes its columns. |
| `_refresh_badge` | `(self, column_index: int)` | Args: |
| `_show_context_menu` | `(self, column_index: int)` | Args: |

### `IsotopePickerDialog` *(extends `QDialog`)*

Modal popover for selecting an isotope. Opened from a column badge.
Pre-filters the list with the column name so the user lands on the
most likely match when an auto-detection was ambiguous.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, periodic_table_data: list, initial_filter: str = '', parent = N` | Args: |
| `_populate` | `(self)` |  |
| `_filter` | `(self, text: str)` | Args: |
| `_accept_current` | `(self, *_)` | Args: |
| `selected_isotope` | `(self) → dict | None` | Returns: |

### `DataProcessThread` *(extends `QThread`)*

Worker thread that loads CSV/TXT/Excel files per the import config.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config, parent = None)` | Args: |
| `run` | `(self)` |  |
| `process_file` | `(self, file_config, file_index)` | Args: |
| `_load_delimited` | `(self, file_path, settings)` | Args: |
| `_load_excel` | `(self, file_path, settings)` | Args: |
| `_process_time` | `(self, df, settings)` | Args: |
| `_process_isotopes` | `(self, df, mappings, settings, dwell_s)` | Args: |
| `_run_info` | `(self, df, settings, file_path, dwell_s, ext)` | Args: |

### `FileStructureDialog` *(extends `QDialog`)*

Configure and preview import of one or more CSV/TXT/Excel files.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, file_paths, parent = None)` | Args: |
| `_load_periodic_table` | `(parent) → list` | Args: |
| `_build_ui` | `(self)` |  |
| `_build_file_header` | `(self) → QFrame` | Returns: |
| `_build_left_panel` | `(self) → QWidget` | Returns: |
| `_build_right_panel` | `(self) → QWidget` | Returns: |
| `_build_button_row` | `(self) → QHBoxLayout` | Returns: |
| `_apply_theme` | `(self, *_)` | Args: |
| `_toggle_advanced` | `(self)` |  |
| `_switch_file` | `(self, index: int)` | Args: |
| `_load_file` | `(self, file_path: str)` | Load a file with the current settings; degrade gracefully on error. |
| `_update_settings_visibility` | `(self, ftype: str)` | Enable the settings relevant to the current file type. |
| `_populate_sheet_list` | `(self, file_path: str)` | Args: |
| `_load_delimited_preview` | `(self, file_path: str) → pd.DataFrame` | Args: |
| `_load_excel_preview` | `(self, file_path: str) → pd.DataFrame` | Args: |
| `_refresh_preview` | `(self)` |  |
| `_sync_badge_widths` | `(self, rebuild: bool = False)` | Args: |
| `_refresh_file_info` | `(self)` |  |
| `_refresh_time_column_options` | `(self)` |  |
| `_refresh_current_file_indicator` | `(self)` |  |
| `_on_column_selected` | `(self)` |  |
| `_on_time_column_changed` | `(self, text: str)` | Args: |
| `_refresh_time_column_options_if_needed` | `(self, selected_time_col: str)` | If the time column was previously mapped, remove that mapping. |
| `_on_dwell_method_changed` | `(self)` |  |
| `_open_picker_for_column` | `(self, column_index: int)` | Open the isotope picker for ``column_index`` and commit the result. |
| `_commit_mapping` | `(self, column_index: int, column_name: str, isotope: dict)` | Args: |
| `_unmap_column` | `(self, column_index: int)` | Args: |
| `_remove_mapping` | `(self)` |  |
| `_refresh_mappings_list` | `(self)` |  |
| `_refresh_mapped_columns_highlight` | `(self)` |  |
| `_auto_detect_isotopes` | `(self, silent: bool = False)` | Scan column names for isotope patterns and create mappings. |
| `_detect_isotope_from_name` | `(self, col_name: str) → dict | None` | Match a column name against the isotope regex and the periodic table. |
| `_apply_to_all_files` | `(self)` |  |
| `_perform_apply_to_all` | `(self, source_mappings: list[dict]) → int` | For each other file, map columns by matching name (case-insensitive). |
| `_match_column` | `(name: str, columns: list[str]) → int | None` | Find the index of a column matching ``name`` (exact → ci → substring). |
| `_read_columns_only` | `(self, file_path: str) → list[str]` | Return the column names of ``file_path`` without loading data. |
| `_debounced_reload` | `(self, *_)` | Coalesce rapid settings changes into a single reload. |
| `_do_reload` | `(self)` |  |
| `_validate_configuration` | `(self)` |  |
| `_build_import_config` | `(self) → dict` | Returns: |
| `_accept_import` | `(self)` |  |

## Functions

### `file_type_of`

```python
def file_type_of(path: str | Path) → str
```

Return 'delimited', 'excel', or 'unknown' for a given file path.

**Args:**

- `path (str | Path): File or directory path.`

**Returns:**

- `str: Result of the operation.`

### `find_first_stopping_row`

```python
def find_first_stopping_row(df: pd.DataFrame) → int
```

Return the index of the first row that is empty or contains text-heavy
cells (2+ consecutive letters).

Dtype-aware fast path: numeric columns are checked with ``isna()`` (fast),
and only object columns are subjected to the regex scan. On a 100k × 30
all-numeric frame this runs in ~5 ms versus ~7 s for a naive per-cell scan.

**Args:**

- `df (pd.DataFrame): Pandas DataFrame.`

**Returns:**

- `int: Result of the operation.`

### `show_csv_structure_dialog`

```python
def show_csv_structure_dialog(file_paths, parent = None) → dict | None
```

Open the import dialog; return the config dict or None if cancelled.

**Args:**

- `file_paths (Any): The file paths.`
- `parent (Any): Parent widget or object.`

**Returns:**

- `dict | None: Result of the operation.`
