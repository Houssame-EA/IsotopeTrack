# `theme.py`

---

## Constants

| Name | Value |
|------|-------|
| `LIGHT` | `Palette(name='light', bg_primary='#f0f4f8', bg_...` |
| `DARK` | `Palette(name='dark', bg_primary='#1e1e1e', bg_s...` |

## Classes

### `Palette`

A complete color palette. All fields are hex strings '#rrggbb'.

### `ThemeManager` *(extends `QObject`)*

Singleton theme manager. Emits themeChanged(palette_name) whenever
the active theme changes. Widgets should connect to themeChanged
and reapply their stylesheets.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__new__` | `(cls)` | Returns: |
| `__init__` | `(self)` |  |
| `palette` | `(self) → Palette` | Returns: |
| `is_dark` | `(self) → bool` | Returns: |
| `set_theme` | `(self, name: str)` | Args: |
| `connect_theme` | `(self, slot) → callable` | Connect a slot to themeChanged and return a cleanup callable. |
| `toggle` | `(self)` |  |

## Functions

### `main_window_qss`

```python
def main_window_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `sidebar_qss`

```python
def sidebar_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `edge_strip_qss`

```python
def edge_strip_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `sidebar_logo_qss`

```python
def sidebar_logo_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `sidebar_list_label_qss`

```python
def sidebar_list_label_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `calibration_panel_qss`

```python
def calibration_panel_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `sample_table_qss`

```python
def sample_table_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `parameters_table_qss`

```python
def parameters_table_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `info_button_qss`

```python
def info_button_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `theme_toggle_button_qss`

```python
def theme_toggle_button_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `sidebar_toggle_button_qss`

```python
def sidebar_toggle_button_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `primary_button_qss`

```python
def primary_button_qss(p: Palette) → str
```

Used by batch_edit_button, show_all_signals_button, detect_button.

**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `progress_bar_qss`

```python
def progress_bar_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `groupbox_qss`

```python
def groupbox_qss(p: Palette) → str
```

Used by plot, control panel, summary group boxes.

**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `summary_label_qss`

```python
def summary_label_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `results_container_qss`

```python
def results_container_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `results_header_qss`

```python
def results_header_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `results_title_qss`

```python
def results_title_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `perf_tip_qss`

```python
def perf_tip_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `enhanced_checkbox_qss`

```python
def enhanced_checkbox_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `table_header_label_qss`

```python
def table_header_label_qss(p: Palette, bg_color: str, text_color: str) → str
```

The create_table_header helper takes explicit colors; this keeps that API
but funnels through the theme-aware border.

**Args:**

- `p (Palette): The p.`
- `bg_color (str): The bg color.`
- `text_color (str): The text color.`

**Returns:**

- `str: Result of the operation.`

### `context_menu_qss`

```python
def context_menu_qss(p: Palette) → str
```


**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `results_table_qss`

```python
def results_table_qss(p: Palette) → str
```

Styling for results_table and multi_element_table (data tables under
the Results Display section).

**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `dialog_qss`

```python
def dialog_qss(p: Palette) → str
```

Generic QDialog styling — covers background, labels, group boxes,
and radio buttons inside popup dialogs. Use for dialogs you don't have
direct control over creating.

**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`

### `tier_colors`

```python
def tier_colors(p: Palette) → dict
```

Returns a dict mapping tier name -> QColor-compatible hex string.
Replacement for hardcoded (255,200,200) style row backgrounds.

**Args:**

- `p (Palette): The p.`

### `html_table_css`

```python
def html_table_css(p: Palette) → str
```

CSS block for HTML tables rendered inside QLabel/QTextEdit via RichText.
Qt's rich-text engine supports a subset of CSS; we stick to attributes
that are known to work (border, background-color, color, padding).

Usage:
html = f"<style>{html_table_css(theme.palette)}</style><table>...</table>"
label.setText(html)

**Args:**

- `p (Palette): The p.`

**Returns:**

- `str: Result of the operation.`
