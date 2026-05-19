# `results_periodic.py`

---

## Constants

| Name | Value |
|------|-------|
| `ELEMENT_CATEGORY_COLORS` | `{'alkali': '#FF7043', 'alkaline': '#BA68C8', 't...` |

## Classes

### `CompactAnimatedButton` *(extends `QPushButton`)*

Custom animated button for periodic table elements with isotope selection support.

This button displays element symbols and handles mouse interactions for isotope selection.
It supports visual highlighting based on isotope abundance and progressive selection modes.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Initialize the compact animated button. |
| `set_isotope_display` | `(self, display)` | Set the isotope display panel for this button. |
| `paintEvent` | `(self, event)` | Custom paint event to draw gradient highlight overlay. |
| `set_highlight` | `(self, percentage, accumulate = True)` | Set or accumulate highlight percentage for isotope abundance visualization. |
| `remove_highlight` | `(self, percentage)` | Remove a specific abundance percentage from the highlight. |
| `clear_highlights` | `(self)` | Clear all highlight percentages and reset visual state. |
| `mousePressEvent` | `(self, event)` | Handle mouse press events for isotope selection. |

### `CompactSelectableIsotopeLabel` *(extends `QLabel`)*

Selectable label widget for individual isotopes with visual feedback.

Displays isotope information and handles click events for selection.
Visual styling changes based on selection state and availability.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, text, isotope_mass, is_available = False, parent = None)` | Initialize the selectable isotope label. |
| `setSelected` | `(self, selected)` | Set the selection state of this isotope label. |
| `updateStyle` | `(self)` |  |
| `mousePressEvent` | `(self, event)` | Handle mouse press events to emit clicked signal. |
| `enterEvent` | `(self, event)` | Args: |
| `leaveEvent` | `(self, event)` | Handle mouse leave event to restore normal styling. |

### `CompactIsotopeDisplay` *(extends `QFrame`)*

Popup panel displaying available isotopes for an element with selection capability.

This widget appears next to element buttons and shows a list of isotopes with
their abundances. It supports progressive selection, individual selection,
and animated show/hide transitions.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Initialize the isotope display panel. |
| `_disconnect_theme` | `(self)` |  |
| `_safe_apply_theme` | `(self)` |  |
| `_apply_theme_style` | `(self)` |  |
| `get_selected_isotopes_data` | `(self)` | Get list of selected isotopes as tuples. |
| `load_selected_isotopes` | `(self, isotopes_data)` | Args: |
| `set_isotopes` | `(self, element, available_element_masses = None)` | Populate the display with isotopes for the given element. |
| `set_parent_button` | `(self, button)` | Set the parent button that owns this isotope display. |
| `toggle_at_position` | `(self, pos)` | Toggle display visibility at the specified position. |
| `hide_with_animation` | `(self)` | Hide the display with a collapsing animation. |
| `_on_hide_finished` | `(self)` | Callback when hide animation completes. |
| `show_at_position` | `(self, pos)` | Show the display at the specified position with an expanding animation. |
| `mousePressEvent` | `(self, event)` | Handle mouse press events to close display when clicking outside. |
| `get_selected_isotopes` | `(self)` | Get list of currently selected isotopes. |
| `select_next_available_isotope` | `(self)` | Progressive isotope selection - add the next available isotope. |
| `select_all_available_isotopes` | `(self)` | Select all available isotopes for this element at once. |
| `select_preferred_isotope` | `(self, mass)` | Select a specific isotope by mass, clearing other selections. |
| `on_isotope_clicked` | `(self, label, isotope_mass)` | Handle isotope label click events to toggle selection. |
| `clear_selection` | `(self)` | Clear all isotope selections for this element. |

### `CompactPeriodicTableWidget` *(extends `QWidget`)*

Interactive periodic table widget with isotope selection capabilities.

Displays a compact periodic table where elements can be clicked to select specific
isotopes. Elements are color-coded by category and can be enabled/disabled based
on available isotopes in the data.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Initialize the periodic table widget. |
| `initUI` | `(self)` |  |
| `_pt_disconnect_theme` | `(self)` |  |
| `_safe_apply_theme_bg` | `(self)` |  |
| `_apply_theme_bg` | `(self)` |  |
| `create_element_button` | `(self, element)` | Create an element button with isotope display and styling. |
| `on_element_button_clicked` | `(self, element)` | Handle element button click event. |
| `on_isotope_selected` | `(self, element, mass, abundance)` | Handle isotope selection event. |
| `get_element_style` | `(self, element, highlighted = False)` | Get CSS stylesheet for element button based on category and state. |
| `update_available_masses` | `(self, available_element_masses)` | Update which elements are available based on detected element-mass pairs. |
| `_update_by_element_mass_pairs` | `(self, element_mass_pairs)` | Update availability based on exact element-mass pairs. |
| `_update_by_mass_tolerance` | `(self, available_masses)` | Update availability based on mass tolerance for backward compatibility. |
| `get_element_by_symbol` | `(self, symbol)` | Get element data dictionary by symbol. |
| `close_all_isotope_displays_except` | `(self, current_button)` | Close all isotope display panels except the one for the current button. |
| `clear_all_highlights` | `(self)` | Clear highlighting from all element buttons. |
| `clear_all_selections` | `(self)` | Clear all isotope selections from all elements. |
| `get_selected_isotopes` | `(self)` | Get all currently selected isotopes from all elements. |
| `get_elements` | `(self)` | Get the periodic table elements data. |

### `IsotopeChipSelector` *(extends `QWidget`)*

Compact chip-based isotope selector.
Shows available isotopes grouped by element as clickable toggle chips.
Much simpler UX than the full periodic table for quick sample configuration.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `_chip_disconnect_theme` | `(self)` |  |
| `_safe_restyle` | `(self)` |  |
| `_setup` | `(self)` |  |
| `_restyle_all` | `(self)` |  |
| `_style_chip` | `(self, sym, mass)` | Args: |
| `set_available_isotopes` | `(self, element_data_list, isotope_pairs)` | isotope_pairs: list of (symbol, mass) tuples |
| `_rebuild_chips` | `(self)` |  |
| `_toggle` | `(self, sym, mass)` | Args: |
| `set_selected` | `(self, isotope_list)` | isotope_list: list of {'symbol':..., 'mass':...} dicts |
| `get_selected` | `(self)` | Returns list of (symbol, mass) tuples |
| `select_all` | `(self)` |  |
| `clear_selection` | `(self)` |  |
