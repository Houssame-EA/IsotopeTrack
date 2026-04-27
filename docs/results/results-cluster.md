# `results_cluster.py`

---

## Constants

| Name | Value |
|------|-------|
| `ALGORITHMS` | `['K-Means', 'Hierarchical', 'DBSCAN', 'Spectral...` |
| `METRICS` | `['Silhouette', 'Calinski-Harabasz', 'Davies-Bou...` |
| `METRIC_KEYS` | `{'Silhouette': ('Silhouette Score', 'silhouette...` |
| `SCALING_OPTIONS` | `['StandardScaler', 'MinMaxScaler', 'None']` |
| `DIM_REDUCTION_OPTIONS` | `['None', 'PCA', 't-SNE']` |
| `DATA_TYPE_OPTIONS` | `['Counts', 'Element Mass (fg)', 'Particle Mass ...` |
| `DATA_KEY_MAP` | `{'Counts': 'elements', 'Element Mass (fg)': 'el...` |
| `CLUSTER_COLORS` | `['#2563EB', '#DC2626', '#16A34A', '#D97706', '#...` |
| `ALGO_LINE_STYLES` | `{'K-Means': dict(color='#2563EB', ls='-', marke...` |

## Classes

### `ClusteringSettingsDialog` *(extends `QDialog`)*

Full settings dialog opened from right-click → Configure.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config, parent = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `collect` | `(self) → dict` | Returns: |

### `ClusteringDisplayDialog` *(extends `QDialog`)*

Main clustering dialog with toolbar, tabs, and right-click menus.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window = None)` | Args: |
| `_is_multi` | `(self)` | Returns: |
| `_build_ui` | `(self)` |  |
| `_make_btn` | `(self, text, color, slot)` | Args: |
| `_build_eval_tab` | `(self)` |  |
| `_build_cluster_tab` | `(self)` |  |
| `_build_char_tab` | `(self)` |  |
| `_ctx_menu` | `(self, pos, tab)` | Args: |
| `_make_popout_btn` | `(self, slot)` | Args: |
| `_pop_out_figure` | `(self, tab: str)` | Redraw the requested figure into a standalone resizable window. |
| `_edit_figure` | `(self, tab: str)` | Open a lightweight per-figure settings dialog. |
| `_redraw_figure` | `(self, tab: str)` | Args: |
| `_cl_drag_press` | `(self, event)` | Args: |
| `_cl_drag_motion` | `(self, event)` | Args: |
| `_cl_drag_release` | `(self, _event)` | Args: |
| `_set` | `(self, key, value)` | Args: |
| `_build_overview_tab` | `(self)` |  |
| `_build_dendrogram_tab` | `(self)` |  |
| `_build_3d_tab` | `(self)` |  |
| `_set_3d_view` | `(self, elev, azim)` | Snap all 3D axes to a preset view angle. |
| `_draw_3d` | `(self)` |  |
| `_draw_3d_into` | `(self, target_fig)` | Args: |
| `_draw_dendrogram` | `(self)` |  |
| `_draw_dendrogram_into` | `(self, target_fig)` | Args: |
| `_draw_overview` | `(self)` | Heatmap (elements × clusters) + cluster size bar chart. |
| `_draw_overview_into` | `(self, target_fig)` | Draw the overview content into an arbitrary Figure (used for pop-out). |
| `_on_eval_pick` | `(self, event)` | Click a point on an evaluation curve to set K directly. |
| `_on_cluster_hover` | `(self, event)` | Show a floating tooltip with element values when hovering scatter points. |
| `_draw_radar` | `(self, algo)` | Spider/radar chart: detection frequency per element per cluster. |
| `_open_settings` | `(self)` |  |
| `_on_node_changed` | `(self)` |  |
| `_get_elements` | `(self)` | Returns: |
| `_prepare_data` | `(self, elements)` | Prepare data matrix — identical logic to original. |
| `_run_algo` | `(self, name, k, data)` | Args: |
| `_run_evaluation` | `(self)` |  |
| `_determine_optimal_k` | `(self)` | Robust optimal-K selection via per-metric voting: |
| `_elbow_k` | `(k_vals: list, scores: list) → int` | Kneedle algorithm: find the K at the elbow of a monotone curve. |
| `_update_optimal_label` | `(self)` |  |
| `_refresh_eval_plot` | `(self)` |  |
| `_run_clustering` | `(self)` |  |
| `_characterise` | `(self, elements, data)` | Generate cluster characterisation with real element-% composition labels. |
| `_populate_char_combos` | `(self, elements)` | Args: |
| `_refresh_char` | `(self)` |  |
| `_export_results` | `(self)` |  |

### `ClusteringPlotNode` *(extends `QObject`)*

Clustering analysis node with matplotlib figures.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |
| `process_data` | `(self, input_data)` | Args: |

## Functions

### `_style_ax`

```python
def _style_ax(ax, cfg, xlabel = '', ylabel = '', title = '')
```

Apply consistent styling to a matplotlib axes.

**Args:**

- `ax (Any): The ax.`
- `cfg (Any): The cfg.`
- `xlabel (Any): The xlabel.`
- `ylabel (Any): The ylabel.`
- `title (Any): Window or dialog title.`

### `_draw_evaluation`

```python
def _draw_evaluation(fig, eval_results, cfg, optimal_k = None, view_algo = 'All Algorithms')
```

Draw evaluation metric curves on a matplotlib Figure.

**Args:**

- `fig (Any): The fig.`
- `eval_results (Any): The eval results.`
- `cfg (Any): The cfg.`
- `optimal_k (Any): The optimal k.`
- `view_algo (Any): The view algo.`

### `_draw_clustering`

```python
def _draw_clustering(fig, clustering_results, data_matrix, characterisation, cfg)
```

Draw cluster scatter plots on a matplotlib Figure.

**Args:**

- `fig (Any): The fig.`
- `clustering_results (Any): The clustering results.`
- `data_matrix (Any): The data matrix.`
- `characterisation (Any): The characterisation.`
- `cfg (Any): The cfg.`

### `_draw_characterisation`

```python
def _draw_characterisation(fig, algo_name, element, characterisation, cfg)
```

Draw cluster characterisation bar chart on a matplotlib Figure.

**Args:**

- `fig (Any): The fig.`
- `algo_name (Any): The algo name.`
- `element (Any): The element.`
- `characterisation (Any): The characterisation.`
- `cfg (Any): The cfg.`
