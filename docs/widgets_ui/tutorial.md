# `tutorial.py`

---

## Classes

### `UserGuideDialog` *(extends `QDialog`)*

User guide dialog — content mirrors the IsotopeTrack README.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
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

### `get_resource_path`

```python
def get_resource_path(relative_path)
```


**Args:**

- `relative_path (Any): The relative path.`

**Returns:**

- `object: Result of the operation.`

### `_section`

```python
def _section(html: str) → QLabel
```

Rich-text section label with consistent styling.

**Args:**

- `html (str): The html.`

**Returns:**

- `QLabel: Result of the operation.`

### `_gif_widget`

```python
def _gif_widget(filename: str, width: int = 680) → QWidget
```

Return a widget displaying an animated GIF from the images/ folder.
Falls back to a styled placeholder if the file is not found.

**Args:**

- `filename (str): The filename.`
- `width (int): Width in pixels.`

**Returns:**

- `QWidget: Result of the operation.`

### `_scroll_tab`

```python
def _scroll_tab(*widgets) → QScrollArea
```

Wrap a list of widgets in a scrollable tab.

**Args:**

- `*widgets (Any): Additional positional arguments.`

**Returns:**

- `QScrollArea: Result of the operation.`

### `_hr`

```python
def _hr() → QLabel
```


**Returns:**

- `QLabel: Result of the operation.`
