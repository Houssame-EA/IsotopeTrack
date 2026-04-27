# `batch_parameters.py`

---

## Classes

### `CollapsibleSection` *(extends `QWidget`)*

A lightweight collapsible container with a toggle header.

Used to hide 'Advanced' parameters that most users don't need to touch,
keeping the default dialog view short and focused.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, title: str, parent = None)` | Args: |
| `_on_toggled` | `(self, checked: bool)` | Args: |
| `content_layout` | `(self) → QGridLayout` | Returns: |

### `BatchElementParametersDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None, elements = None, current_parameters = None, all_` | Initialize the batch element parameters dialog. |
| `apply_theme` | `(self)` | Apply the currently active theme palette to this dialog. |
| `closeEvent` | `(self, event)` | Disconnect theme signal so we don't leak slots on closed dialogs. |
| `setup_ui` | `(self)` | Build the dialog layout. |
| `_build_samples_group` | `(self) → QGroupBox` | Returns: |
| `_build_elements_group` | `(self) → QGroupBox` | Returns: |
| `_build_params_group` | `(self) → QGroupBox` | Returns: |
| `_build_advanced_section` | `(self) → CollapsibleSection` | Returns: |
| `toggle_manual_threshold` | `(self, method)` | Show/hide the manual threshold input based on the detection method. |
| `toggle_window_size` | `(self, state)` | Show/hide the window size input based on the Enable checkbox. |
| `_toggle_valley_ratio` | `(self, method: str)` | Show/hide the valley ratio input depending on the split method. |
| `filter_elements` | `(self)` | Filter element checkboxes based on search text input. |
| `select_all` | `(self)` |  |
| `deselect_all` | `(self)` |  |
| `select_all_samples` | `(self)` |  |
| `deselect_all_samples` | `(self)` |  |
| `_on_element_toggled` | `(self)` |  |
| `update_selected_elements` | `(self)` | Back-compat alias in case external code referenced this name. |
| `_update_element_count` | `(self)` |  |
| `_update_sample_count` | `(self)` |  |
| `initialize_controls_from_parameters` | `(self)` | Initialize UI controls with current parameter values from existing settings. |
| `get_parameters` | `(self)` | Return the parameter values to apply to selected elements. |
| `get_selected_samples` | `(self)` | Return names of all selected samples. |
