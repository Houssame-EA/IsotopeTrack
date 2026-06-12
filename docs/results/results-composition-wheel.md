# `results_composition_wheel.py`

Composition Wheel (2D / 3D) — single & multi-sample particle-signature plot.

---

## Constants

| Name | Value |
|------|-------|
| `WHEEL_MODES` | `['Single sample', 'Stacked discs (Z = sample)', 'Overlaid…` |
| `ANGLE_MODES` | `['Element (categorical)', 'Ratio A/(A+B) (continuous)']` |
| `RADIUS_MODES` | `['Mass', 'Counts']` |
| `DATA_KEY_MAP` | `{'Counts': 'elements', 'Element Mass (fg)': 'element_mass…` |

## Classes

### `CompositionWheelCanvas` *(extends `QWidget`)*

Renders the composition wheel. Holds either a GLViewWidget (3D, GPU) or

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict, parent=None)` |  |
| `set_context_menu_callback` | `(self, fn)` |  |
| `_fwd_ctx` | `(self, pos)` |  |
| `render` | `(self, samples: dict, cfg: dict)` | samples: {sample_name: {'x':, 'y':, 'elem':, 'r_raw':}}  (wheel coords) |
| `export_figure` | `(self, parent=None)` | Reuse the standard download dialog (matplotlib path). |
| `_show_for_mode` | `(self, mode: str)` |  |
| `_qcolor` | `(hexstr)` |  |
| `_elem_palette` | `(self, elements)` |  |
| `_render_mpl_2d` | `(self, samples, cfg, mode)` |  |
| `_draw_disc` | `(self, ax, samples, cfg, by_sample, title)` |  |
| `_render_mpl_3d` | `(self, samples, cfg, mode)` |  |
| `_render_gl` | `(self, samples, cfg, mode)` |  |

### `CompositionWheelSettingsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg, input_data, available_elements, parent=None)` |  |
| `_build` | `(self)` |  |
| `_sync_ratio` | `(self, mode)` |  |
| `collect` | `(self) → dict` |  |

### `CompositionWheelDisplayDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window=None)` |  |
| `_build_ui` | `(self)` |  |
| `_on_sample` | `(self, name)` |  |
| `_settings` | `(self)` |  |
| `_ctx_menu` | `(self, global_pos)` |  |
| `_set` | `(self, k, v)` |  |
| `_export` | `(self)` |  |
| `_refresh` | `(self, repopulate=True)` |  |

### `CompositionWheelPlotNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` |  |
| `process_data` | `(self, input_data)` |  |
| `_data_key` | `(self)` |  |
| `available_elements` | `(self) → list` |  |
| `_matrices` | `(self) → dict` | Return {sample_name: particles×elements DataFrame}. |
| `extract_plot_data` | `(self)` | Return {sample_name: wheel-coord dict} or None. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_dominant_element` | `(row: pd.Series) → str \| None` | Element with the largest value in a particle row (None if all zero). |
| `compute_wheel_xy` | `(df: pd.DataFrame, cfg: dict) → dict` | Map a particles × elements matrix into wheel coordinates. |
| `polar_histogram` | `(x: np.ndarray, y: np.ndarray, n_ang: int=24, n_rad: int=6) → np.ndarr` | Bin wheel points into an (n_ang × n_rad) count grid for the Z surface. |
| `fp_or_none` | `(cfg)` |  |
| `_viridis` | `(t: float)` |  |
| `_gl_bar` | `(cx, cy, w, h, rgba)` | A coloured vertical box mesh for the density surface. |
