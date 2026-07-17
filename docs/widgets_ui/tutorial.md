# `tutorial.py`

---

## Classes

### `UserGuideDialog` *(extends `QDialog`)*

User guide dialog — content mirrors the IsotopeTrack README.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Build the user-guide dialog and all its tabs. |
| `apply_theme` | `(self)` | Apply the currently active theme palette. |
| `_refresh_section_styles` | `(self)` | Restyle all _section() labels to use the current palette. |
| `closeEvent` | `(self, event)` | Disconnect theme signals when the dialog closes. |
| `_tab_overview` | `(self)` | Build the Overview tab. |
| `_build_search_index` | `(self)` | Index every hotspot of every interactive page for search. |
| `_on_search_changed` | `(self, text)` | Filter the search index and show matching regions. |
| `_on_result_clicked` | `(self, item)` | Navigate to the clicked search result. |
| `_interactive_sections` | `(self)` | Build the interactive guide sections from guide_content. |
| `_tab_workflow` | `(self)` | Build the Workflow tab. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_section` | `(html: str) → QLabel` | Rich-text section label with consistent styling. |
| `_scroll_tab` | `(*widgets) → QScrollArea` | Wrap a list of widgets in a scrollable tab. |
| `_hr` | `() → QLabel` | Return a horizontal-rule label for separating sections. |
