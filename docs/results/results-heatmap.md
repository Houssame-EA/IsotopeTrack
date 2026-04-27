# `results_heatmap.py`

---

## Constants

| Name | Value |
|------|-------|
| `HEATMAP_DATA_TYPES` | `['Counts', 'Element Mass (fg)', 'Particle Mass ...` |

## Classes

### `HeatmapSettingsDialog` *(extends `QDialog`)*

Full settings dialog opened from right-click → Configure…

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config: dict, is_multi: bool, sample_names: list, parent = None` | Args: |
| `_build` | `(self)` |  |
| `_pick_color` | `(self, name, btn)` | Args: |
| `collect` | `(self) → dict` | Returns: |

### `HeatmapDisplayDialog` *(extends `QDialog`)*

Full-figure heatmap dialog with right-click context menu.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, heatmap_node, parent_window = None)` | Args: |
| `_is_multi` | `(self) → bool` | Returns: |
| `_sample_names` | `(self) → list` | Returns: |
| `_setup_ui` | `(self)` |  |
| `_show_context_menu` | `(self, pos)` | Args: |
| `_add_toggle` | `(self, menu, label, key)` | Args: |
| `_toggle` | `(self, key, value)` | Args: |
| `_set_and_refresh` | `(self, key, value)` | Args: |
| `_search_dialog` | `(self)` |  |
| `_range_dialog` | `(self)` | Quick range adjustment via two input dialogs. |
| `_open_settings` | `(self)` |  |
| `_reset_layout` | `(self)` |  |
| `_export_figure` | `(self)` |  |
| `_refresh` | `(self)` |  |
| `_draw_multi` | `(self, data, cfg, display_mode)` | Args: |
| `_combine_data` | `(data)` | Args: |
| `_draw_heatmap` | `(self, ax, sample_data, cfg, title)` | Args: |

### `HeatmapPlotNode` *(extends `QObject`)*

Heatmap plot node with multiple sample support.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `extract_combinations_data` | `(self)` | Returns: |
| `_extract_single` | `(self, data_key)` | Args: |
| `_extract_multi` | `(self, data_key)` | Args: |

## Functions

### `_combo_matches`

```python
def _combo_matches(combination: str, search_elements: list) → bool
```

Check if a combination string contains all search elements (order-independent).

**Args:**

- `combination (str): The combination.`
- `search_elements (list): The search elements.`

**Returns:**

- `bool: Result of the operation.`

### `_build_combinations`

```python
def _build_combinations(particles, data_key)
```

Build combination dict from a list of particle dicts.

**Args:**

- `particles (Any): The particles.`
- `data_key (Any): The data key.`

**Returns:**

- `object: Result of the operation.`
