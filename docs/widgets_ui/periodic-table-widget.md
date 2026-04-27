# `periodic_table_widget.py`

---

## Constants

| Name | Value |
|------|-------|
| `PRESET_LISTS` | `{'71A': ['Ag', 'Al', 'As', 'B', 'Ba', 'Be', 'Ca...` |

## Classes

### `AnimatedButton` *(extends `QPushButton`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Initialize the animated button for periodic table elements. |
| `set_element_data` | `(self, element_data)` | Cache element data to avoid repeated lookups. |
| `set_isotope_display` | `(self, display)` | Set the isotope display widget for this button. |
| `paintEvent` | `(self, event)` | Paint the button with highlight gradient overlay. |
| `set_highlight` | `(self, percentage, accumulate = True)` | Set or accumulate highlight percentage for the button. |
| `remove_highlight` | `(self, percentage)` | Remove a specific highlight percentage value. |
| `clear_highlights` | `(self)` | Clear all highlight values from the button. |
| `mousePressEvent` | `(self, event)` | Handle mouse press events for isotope selection. |

### `SelectableIsotopeLabel` *(extends `QLabel`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, text, isotope_mass, is_preferred = False, parent = None)` | Initialize selectable isotope label. |
| `setSelected` | `(self, selected)` | Set the selection state of the label. |
| `updateStyle` | `(self)` | Update the visual style based on selection and preference state. |
| `mousePressEvent` | `(self, event)` | Handle mouse press events on the label. |
| `enterEvent` | `(self, event)` | Handle mouse enter events for hover effect. |
| `leaveEvent` | `(self, event)` | Handle mouse leave events to restore normal style. |

### `IsotopeDisplay` *(extends `QFrame`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Initialize the isotope display panel. |
| `get_selected_isotopes_data` | `(self)` | Return selected isotopes in a serializable format. |
| `load_selected_isotopes` | `(self, isotopes_data)` | Load selected isotopes from saved data. |
| `set_available_masses` | `(self, available_masses)` | Set the available masses from loaded data. |
| `is_isotope_available` | `(self, isotope_mass, tolerance = 0.5)` | Check if an isotope mass is available in the loaded data. |
| `set_isotopes` | `(self, element)` | Set the isotopes to display for an element. |
| `set_parent_button` | `(self, button)` | Set the parent button for this isotope display. |
| `toggle_at_position` | `(self, pos)` | Toggle visibility of the display at a specific position. |
| `hide_with_animation` | `(self)` | Hide the display with animation effect. |
| `_on_hide_finished` | `(self)` | Handle animation finished event for hiding. |
| `show_at_position` | `(self, pos)` | Show the display at a specific position with animation. |
| `mousePressEvent` | `(self, event)` | Handle mouse press events on the display. |
| `get_selected_isotopes` | `(self)` | Get list of selected isotopes. |
| `select_preferred_isotope` | `(self, mass)` | Select the preferred isotope with given mass. |
| `on_isotope_clicked` | `(self, label, isotope_mass)` | Handle isotope label click events. |
| `clear_selection` | `(self)` | Clear all selections and update button state. |

### `PeriodicTableWidget` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Initialize the periodic table widget. |
| `apply_theme` | `(self, *_)` | Re-apply the theme-driven chrome of the periodic table. |
| `_refresh_all_element_buttons` | `(self)` | Re-apply the correct style to every element button based on |
| `_refresh_element_button_labels` | `(self, btn, enabled)` | Update the four internal labels (atomic number, symbol, name, |
| `_toolbar_btn_style` | `(p) → str` | Style for the small control-panel buttons (Clear/Save/Load/Confirm). |
| `_big_btn_style` | `(p, kind) → str` | Style for the big Save/Load Selections buttons. |
| `_disabled_element_style` | `(self) → str` | Style for an element button whose isotopes aren't in the |
| `_create_elements_data` | `(self)` | Returns: |
| `add_control_panel` | `(self)` | Add control panel with preset lists and save/load buttons. |
| `confirm_selections` | `(self)` | Gather all selected elements and isotopes and emit signal. |
| `add_save_load_buttons` | `(self)` | Add save and load buttons to the dialog. |
| `save_selections` | `(self)` | Save selected isotopes to a simple text file. |
| `load_selections` | `(self)` | Load selected isotopes from a simple text file. |
| `initUI` | `(self)` | Initialize the user interface and periodic table grid. |
| `create_element_button` | `(self, element)` | Create a button for a periodic table element. |
| `on_preset_selected` | `(self, preset_name)` | Handle preset list selection events. |
| `on_element_button_clicked` | `(self, element)` | Handle element button click events. |
| `on_isotope_selected` | `(self, element, mass, abundance)` | Handle isotope selection with abundance. |
| `get_element_style` | `(self, element, highlighted = False)` | Get the style for an element button. |
| `update_element_states` | `(self, available_masses, low_count_elements)` | Update element button states based on available masses. |
| `validate_selections_against_new_range` | `(self)` | Validate and clear selections that are no longer available in the new mass range. |
| `update_available_masses` | `(self, available_masses)` | Update which elements are available based on detected masses. |
| `get_element_by_symbol` | `(self, symbol)` | Get element data by symbol using O(1) lookup. |
| `close_all_isotope_displays_except` | `(self, current_button)` | Close all isotope displays except for the specified button. |
| `clear_all_highlights` | `(self)` | Clear all element highlights. |
| `clear_all_selections` | `(self)` | Clear all selected isotopes and highlights, respecting available mass range. |
| `clear_selections_in_range_only` | `(self)` | Clear only selections for elements within the available mass range. |
| `get_elements` | `(self)` | Return cached elements list using O(1) operation. |
