# `results_reader.py`

---

## Constants

| Name | Value |
|------|-------|
| `_FONT` | `'Segoe UI'` |

## Classes

### `Suggestion`

| Method | Signature | Description |
|--------|-----------|-------------|
| `confidence_label` | `(self) → str` |  |

### `_AnalysisWorker` *(extends `QThread`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, data_context: dict)` |  |
| `run` | `(self)` |  |

### `_Card` *(extends `QFrame`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, s: Suggestion, on_add, parent=None)` |  |
| `_build` | `(self)` |  |
| `_clicked` | `(self)` |  |

### `SmartInsightsPanel` *(extends `QWidget`)*

Resizable QWidget embedded as the rightmost pane of the canvas QSplitter.
Call refresh() to rerun analysis; it runs automatically when the panel
becomes visible.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, scene, parent_window, parent=None)` |  |
| `_build_ui` | `(self)` |  |
| `_apply_theme` | `(self)` |  |
| `refresh` | `(self)` | Re-run analysis. Auto-called when the panel becomes visible. |
| `_update_sample_strip` | `(self)` |  |
| `_on_done` | `(self, suggestions: list[Suggestion])` |  |
| `_rebuild_cards` | `(self)` |  |
| `_show_empty` | `(self)` |  |
| `_clear_cards` | `(self)` |  |
| `_add_suggestion` | `(self, s: Suggestion)` |  |
| `showEvent` | `(self, event)` |  |
| `closeEvent` | `(self, event)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_safe_float` | `(v) → float \| None` |  |
| `_element_matrix` | `(particles: list[dict]) → dict[str, np.ndarray]` |  |
| `_det_counts` | `(mat: dict[str, np.ndarray]) → dict[str, int]` |  |
| `_pearson_log` | `(a: np.ndarray, b: np.ndarray) → float \| None` |  |
| `_bimodality_bc` | `(arr: np.ndarray) → float` |  |
| `_isotope_symbol` | `(name: str) → str \| None` |  |
| `_group_isotopes` | `(elements: list[str]) → dict[str, list[str]]` |  |
| `_find_source_node` | `(scene) → object \| None` | Return the configured sample node with the most particles. |
| `_get_open_sample_names` | `(scene) → list[str]` |  |
| `_get_data_context` | `(scene) → dict` |  |
| `integrate_insights_panel` | `(canvas_dialog, splitter: QSplitter) → SmartInsightsPanel` | Append SmartInsightsPanel as the rightmost pane of *splitter*. |
| `make_insights_toggle_button` | `(canvas_dialog, splitter: QSplitter) → QPushButton` | Create the header toggle button that shows/hides the insights panel. |
