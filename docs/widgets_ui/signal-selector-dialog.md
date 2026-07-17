# `signal_selector_dialog.py`

---

## Constants

| Name | Value |
|------|-------|
| `DEFAULT_SAMPLE_COLORS` | `['#1f77b4', '#d62728', '#2ca02c', '#ff7f0e', '#9467bd', '…` |
| `DEFAULT_ELEMENT_COLORS` | `['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '…` |

## Classes

### `ColorButton` *(extends `QPushButton`)*

Custom color picker button widget.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, color='#1f77b4')` | Initialize the color button. |
| `_apply_style` | `(self)` | Apply stylesheet to reflect the current color. |
| `pick_color` | `(self)` | Open the color picker dialog and emit colorChanged if a new color is chosen. |
| `get_color` | `(self)` | Return the current color. |
| `set_color` | `(self, color)` | Set a new color and update appearance. |

### `SignalSelectorDialog` *(extends `QDialog`)*

Dialog for selecting and configuring multiple signals for simultaneous display.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, main_window, parent=None)` | Initialize the signal selector dialog. |
| `apply_theme` | `(self)` | Re-apply all theme-aware styling. |
| `showEvent` | `(self, event)` |  |
| `_apply_element_scroll_style` | `(self)` |  |
| `_apply_sample_scroll_style` | `(self)` |  |
| `_apply_button_bar_style` | `(self)` |  |
| `_row_label_style` | `(self) → str` |  |
| `_setup_ui` | `(self)` | Build and assemble the dialog layout. |
| `_build_sample_group` | `(self)` | Build the sample selection group box. |
| `_build_element_group` | `(self)` | Build the element/signal selection group box. |
| `_build_button_bar` | `(self)` | Bottom row with Cancel and Plot Signals buttons. |
| `_utility_btn` | `(self, text, slot)` | Create a small utility button (Select All / Deselect All). |
| `_build_row` | `(self, label_text, color, checked=True, on_check_changed=None)` | Build a single checkbox + label + color-picker row widget. |
| `populate_samples` | `(self)` | Populate the sample list from loaded data. Current sample is checked by default. |
| `populate_signals` | `(self)` | Populate the signals list ordered by isotope mass. |
| `select_all` | `(self)` | Select all element checkboxes that are currently visible. |
| `deselect_all` | `(self)` | Clear element checkboxes that are currently visible. |
| `select_all_samples` | `(self)` | Select all sample checkboxes. |
| `deselect_all_samples` | `(self)` | Clear all sample checkboxes. |
| `_update_sample_count` | `(self)` | Refresh the sample count shown in the group title. |
| `_update_element_count` | `(self)` | Refresh the element count shown in the group title. |
| `_filter_elements` | `(self)` | Show/hide element rows based on the filter input's text. |
| `_get_selected_samples` | `(self)` | Return selected samples with their visual configuration. |
| `_get_selected_elements` | `(self)` | Return selected element configurations. |
| `_find_closest_mass` | `(self, sample_data, target_mass)` | Find the key in sample_data closest to target_mass. |
| `_get_detected_peaks` | `(self, sample_name, element, isotope)` | Retrieve detected peaks for a given sample and element. |
| `plot_signals` | `(self)` | Plot all selected signals with optimized performance. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_style_group_box` | `() → str` |  |
| `_style_scroll_area` | `() → str` |  |
| `_style_checkbox` | `() → str` |  |
| `_style_row_widget` | `() → str` |  |
| `_style_utility_btn` | `() → str` |  |
| `_style_plot_btn` | `() → str` |  |
| `_style_cancel_btn` | `() → str` |  |
