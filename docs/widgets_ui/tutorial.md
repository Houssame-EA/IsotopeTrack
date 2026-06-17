# `tutorial.py`

---

## Classes

### `UserGuideDialog` *(extends `QDialog`)*

User guide dialog — content mirrors the IsotopeTrack README.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Args: |
| `apply_theme` | `(self)` | Apply the currently active theme palette. |
| `_refresh_section_styles` | `(self)` | Restyle all _section() labels to use the current palette. |
| `closeEvent` | `(self, event)` | Args: |
| `_tab_overview` | `(self)` | Returns: |
| `_tab_workflow` | `(self)` | Returns: |
| `_tab_data` | `(self)` | Returns: |
| `_tab_calibration` | `(self)` | Returns: |
| `_tab_parameters` | `(self)` | Returns: |
| `_tab_results` | `(self)` | Returns: |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_resource_path` | `(relative_path)` | Args: |
| `_section` | `(html: str) → QLabel` | Rich-text section label with consistent styling. |
| `_gif_widget` | `(filename: str, width: int=680) → QWidget` | Return a widget displaying an animated GIF from the images/ folder. |
| `_scroll_tab` | `(*widgets) → QScrollArea` | Wrap a list of widgets in a scrollable tab. |
| `_hr` | `() → QLabel` | Returns: |
