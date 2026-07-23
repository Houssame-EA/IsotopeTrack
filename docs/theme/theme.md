# `theme.py`

---

## Constants

| Name | Value |
|------|-------|
| `LIGHT` | `Palette(name='light', bg_primary='#e8edf3', bg_secondary=…` |
| `DARK` | `Palette(name='dark', bg_primary='#1e1e1e', bg_secondary='…` |

## Classes

### `Palette`

A complete color palette. All fields are hex strings '#rrggbb'.

### `ThemeManager` *(extends `QObject`)*

Singleton theme manager.

Emits ``themeChanged(palette_name)`` whenever the active theme changes.
Widgets should connect to ``themeChanged`` and reapply their stylesheets.

System-theme integration
------------------------
On first run (no saved preference) the OS dark/light setting is used
automatically.  Call ``sync_with_system()`` once after ``QApplication``
is created to:
  • Apply the detected OS preference if follow-system is enabled.
  • Hook into ``QStyleHints.colorSchemeChanged`` for live OS changes
    (Qt 6.5 / PySide6 ≥ 6.5, macOS 13+, Windows 10+).

The saved setting can be ``'light'``, ``'dark'``, or ``'system'``
(follow OS automatically).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__new__` | `(cls)` |  |
| `__init__` | `(self)` |  |
| `sync_with_system` | `(self) → None` | Call **once** right after ``QApplication`` is created (before the |
| `_on_system_scheme_changed` | `(self) → None` | Qt slot: called automatically when the OS changes dark/light mode. |
| `palette` | `(self) → Palette` |  |
| `is_dark` | `(self) → bool` |  |
| `follow_system` | `(self) → bool` | True when the theme automatically tracks the OS preference. |
| `set_follow_system` | `(self, follow: bool) → None` | Enable or disable automatic OS-theme following. |
| `set_theme` | `(self, name: str) → None` | Manually set 'dark' or 'light'.  Disables follow-system automatically |
| `toggle` | `(self) → None` | Toggle between dark and light, disabling follow-system. |
| `connect_theme` | `(self, slot) → callable` | Connect *slot* to ``themeChanged`` and return a zero-argument |
| `_apply_palette` | `(self, new_palette: 'Palette') → None` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_detect_system_theme` | `() → str` | Detect the OS dark/light mode preference. |
| `main_window_qss` | `(p: Palette) → str` |  |
| `sidebar_qss` | `(p: Palette) → str` |  |
| `edge_strip_qss` | `(p: Palette) → str` |  |
| `sidebar_logo_qss` | `(p: Palette) → str` |  |
| `sidebar_list_label_qss` | `(p: Palette) → str` |  |
| `calibration_panel_qss` | `(p: Palette) → str` |  |
| `sample_table_qss` | `(p: Palette) → str` |  |
| `parameters_table_qss` | `(p: Palette) → str` |  |
| `info_button_qss` | `(p: Palette) → str` |  |
| `theme_toggle_button_qss` | `(p: Palette) → str` |  |
| `sidebar_toggle_button_qss` | `(p: Palette) → str` |  |
| `primary_button_qss` | `(p: Palette) → str` | Used by batch_edit_button, show_all_signals_button, detect_button. |
| `progress_bar_qss` | `(p: Palette) → str` |  |
| `groupbox_qss` | `(p: Palette) → str` | Used by plot, control panel, summary group boxes. |
| `summary_label_qss` | `(p: Palette) → str` |  |
| `results_container_qss` | `(p: Palette) → str` |  |
| `results_header_qss` | `(p: Palette) → str` |  |
| `results_title_qss` | `(p: Palette) → str` |  |
| `perf_tip_qss` | `(p: Palette) → str` |  |
| `enhanced_checkbox_qss` | `(p: Palette) → str` |  |
| `table_header_label_qss` | `(p: Palette, bg_color: str, text_color: str) → str` | The create_table_header helper takes explicit colors; this keeps that API |
| `context_menu_qss` | `(p: Palette) → str` |  |
| `results_table_qss` | `(p: Palette) → str` | Styling for results_table and multi_element_table (data tables under |
| `dialog_qss` | `(p: Palette) → str` | Generic QDialog styling — covers background, labels, group boxes, |
| `export_dialog_qss` | `(p: Palette) → str` | Styling for pyqtgraph's plot-export dialogs (item picker and Save As). |
| `tier_colors` | `(p: Palette) → dict` | Returns a dict mapping tier name -> QColor-compatible hex string. |
| `html_table_css` | `(p: Palette) → str` | CSS block for HTML tables rendered inside QLabel/QTextEdit via RichText. |
