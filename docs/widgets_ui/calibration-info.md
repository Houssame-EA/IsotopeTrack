# `calibration_info.py`

---

## Classes

### `CalibrationInfoDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, calibration_results, selected_methods, method_preferences = Non` | Initialize the calibration information dialog. |
| `apply_theme` | `(self)` | Apply the currently active theme palette to this dialog. |
| `closeEvent` | `(self, event)` | Args: |
| `get_modern_stylesheet` | `(self)` | Stylesheet parameterized on the active theme palette. |
| `_quality_row_color` | `(self, r_squared, method_name)` | Pick a row tint color for the ionic table based on R² + method. |
| `_tier_text_color` | `(self)` | Text color to use on top of tier-colored row backgrounds. |
| `_muted_color` | `(self)` | Color for 'Not available' / em-dash placeholder text. |
| `format_isotope_label` | `(self, element_key)` | Args: |
| `get_mass_number_for_sorting` | `(self, formatted_label)` | Args: |
| `find_matching_threshold_key` | `(self, formatted_isotope, element_thresholds)` | Args: |
| `find_matching_limit_key` | `(self, formatted_isotope, element_limits)` | Args: |
| `init_ui` | `(self)` | Initialize the user interface layout and components. |
| `create_transport_rate_tab` | `(self)` | Create transport rate calibration tab. |
| `setup_transport_rate_table` | `(self)` |  |
| `create_ionic_calibration_tab` | `(self)` | Create ionic calibration tab. |
| `setup_ionic_table` | `(self)` |  |
| `create_bottom_buttons` | `(self, layout)` | Args: |
| `populate_data` | `(self)` |  |
| `populate_transport_rate_table` | `(self)` |  |
| `populate_ionic_calibration_table` | `(self)` |  |
| `_apply_ionic_row_tints` | `(self)` | Apply theme-aware row tints to the ionic calibration table. |
| `_repaint_rows_for_theme` | `(self)` | Re-apply row tints after a theme change. |
| `create_item` | `(self, value, editable = True)` | Args: |
| `create_scientific_item` | `(self, value)` | Args: |
| `create_decimal_item` | `(self, value, decimals = 2)` | Args: |
| `create_quality_item` | `(self, r_squared)` | Args: |
| `create_status_item` | `(self, r_squared, method_data, limit_data)` | Args: |
| `filter_ionic_table` | `(self)` |  |
| `update_average_transport_rate` | `(self)` |  |
| `_refresh_avg_rate_style` | `(self)` | Update the inline avg-rate text + its color, from the current palette. |
| `_refresh_summary_line` | `(self)` | Compact text summary shown at the top of the dialog. |
| `export_calibration_data` | `(self)` |  |
| `refresh_data` | `(self)` | Refresh all calibration data without showing notification. |
