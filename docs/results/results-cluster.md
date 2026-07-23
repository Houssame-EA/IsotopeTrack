# `results_cluster.py`

---

## Constants

| Name | Value |
|------|-------|
| `ALGORITHMS` | `['K-Means', 'Hierarchical', 'DBSCAN', 'HDBSCAN', 'Spectra…` |
| `CVI_FUNCS` | `{'silhouette_scores': lambda d, l: float(silhouette_score…` |
| `METRIC_REGISTRY` | `{'Silhouette': {'display': 'Silhouette Score', 'key': 'si…` |
| `METRICS` | `list(METRIC_REGISTRY.keys())` |
| `METRIC_KEYS` | `{name: (spec['display'], spec['key']) for name, spec in M…` |
| `DEFAULT_METRICS` | `['Silhouette', 'Calinski-Harabasz', 'Davies-Bouldin']` |
| `METRIC_COLORS` | `{name: spec['color'] for name, spec in METRIC_REGISTRY.it…` |
| `DENSITY_BASED_ALGOS` | `{'DBSCAN', 'HDBSCAN', 'OPTICS', 'Mean Shift'}` |
| `PROGRESS_RESOLUTION` | `1000` |
| `SCALING_OPTIONS` | `['CLR', 'ILR', 'Robust Z-score', 'None']` |
| `DIM_REDUCTION_OPTIONS` | `['None', 'PCA', 't-SNE'] + (['UMAP'] if _UMAP_OK else [])` |
| `DATA_TYPE_OPTIONS` | `['Counts', 'Element Mass (fg)', 'Particle Mass (fg)', 'El…` |
| `DATA_KEY_MAP` | `{'Counts': 'elements', 'Element Mass (fg)': 'element_mass…` |
| `CLUSTER_COLORS` | `['#2563EB', '#DC2626', '#16A34A', '#D97706', '#7C3AED', '…` |
| `ALGO_LINE_STYLES` | `{'K-Means': dict(color='#2563EB', ls='-', marker='o'), 'H…` |
| `_ELEMENT_PALETTE` | `['#2563EB', '#DC2626', '#16A34A', '#D97706', '#7C3AED', '…` |
| `SAMPLE_MARKERS` | `['o', 's', '^', 'D', 'v', 'P', 'X', '*', 'h', '<', '>', 'p']` |
| `SAMPLE_PALETTE` | `['#2563EB', '#DC2626', '#16A34A', '#D97706', '#7C3AED', '…` |

## Classes

### `_SafeFigureCanvas` *(extends `FigureCanvas`)*

FigureCanvas subclass that suppresses the PySide6 installEventFilter crash.

| Method | Signature | Description |
|--------|-----------|-------------|
| `showEvent` | `(self, event)` |  |
| `resizeEvent` | `(self, event)` |  |

### `_SOM`

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, rows, cols, n_features, sigma=1.0, lr=0.5, n_iter=2000, random_` |  |
| `fit` | `(self, X, progress_cb=None, snapshot_every=0)` | Train the SOM, optionally reporting live convergence snapshots. |
| `predict` | `(self, X)` |  |
| `get_weights` | `(self)` |  |
| `get_grid_labels` | `(self, neuron_cluster_labels)` |  |
| `get_u_matrix` | `(self)` | Compute the U-matrix: mean Euclidean distance from each neuron to |
| `get_hit_count` | `(self, X)` | Count how many input samples have each neuron as their BMU |
| `get_quantization_error` | `(self, X)` | Mean Euclidean distance from each input to its BMU. |

### `ClusteringSettingsDialog` *(extends `QDialog`)*

Full settings dialog opened from right-click → Configure.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, config, parent=None, input_data=None)` | Initialise the dialog and build the UI from the supplied config. |
| `_build_ui` | `(self)` |  |
| `collect` | `(self) → dict` | Collect all widget values into a configuration dictionary. |

### `_ClusterWorker` *(extends `QThread`)*

Background worker that runs the clustering pipeline off the UI thread.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, dialog, sel_k, elements, data, enabled, parent=None)` |  |
| `run` | `(self)` | Execute the pipeline on the worker thread and emit results. |

### `_EvalWorker` *(extends `QThread`)*

Background worker that runs K-evaluation off the UI thread.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, dialog, elements, parent=None)` |  |
| `run` | `(self)` | Run preparation and K-evaluation, emitting progress and results. |

### `_BootstrapWorker` *(extends `QThread`)*

Background worker that runs the K-stability bootstrap off the UI thread.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, dialog, data, enabled_algos, bootstrap_metrics, n_boot, seed, p` |  |
| `cancel` | `(self)` | Request cancellation; the loop stops after the current resample. |
| `run` | `(self)` | Execute the bootstrap loop on the worker thread and emit results. |

### `_StabilityWorker` *(extends `QThread`)*

Background worker computing bootstrap assignment stability.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, dialog, data, algo, sel_k, ref_labels, n_boot, seed, parent=Non` |  |
| `cancel` | `(self)` | Request cancellation; the loop stops after the current resample. |
| `run` | `(self)` | Execute the stability bootstrap loop and emit aggregated results. |

### `ClusteringDisplayDialog` *(extends `QDialog`)*

Main clustering dialog with toolbar, tabs, and right-click menus.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, node, parent_window=None)` |  |
| `_on_app_theme_changed` | `(self, _name=None)` | Re-theme the dialog and redraw figures when the app theme changes. |
| `_apply_theme` | `(self)` | Apply the active palette to the whole dialog as one stylesheet. |
| `_is_multi` | `(self)` |  |
| `_update_color_by_visibility` | `(self)` | Hide the Color-by picker for single-sample input. |
| `_update_eval_scope_visibility` | `(self)` | Hide the Pooled/Per-sample scope toggle for single-sample input. |
| `_on_color_by_changed` | `(self, text)` | Redraw the cluster scatter when the user changes the Color-by selection. |
| `_build_ui` | `(self)` |  |
| `_btn_style` | `(self, color)` | Return the stylesheet for a flat coloured action button. |
| `_make_btn` | `(self, text, color, slot)` |  |
| `_build_eval_tab` | `(self)` |  |
| `_build_summary_tab` | `(self)` | Build the Summary tab holding the consensus decision matrix. |
| `_refresh_summary` | `(self)` | Redraw the consensus summary table from the latest evaluation state. |
| `_build_cluster_tab` | `(self)` | Build the Clusters tab containing both 2-D and 3-D scatter views, |
| `_switch_cluster_view` | `(self, mode)` | Toggle between 2-D scatter and 3-D scatter within the Clusters tab. |
| `_ctx_menu` | `(self, pos, tab)` |  |
| `_make_popout_btn` | `(self, slot)` |  |
| `_pop_out_figure` | `(self, tab: str)` | Redraw the requested figure into a standalone resizable window. |
| `_edit_figure` | `(self, tab: str)` | Open the per-figure display settings dialog. |
| `_redraw_figure` | `(self, tab: str)` |  |
| `_cl_drag_press` | `(self, event)` |  |
| `_cl_drag_motion` | `(self, event)` |  |
| `_cl_drag_release` | `(self, _event)` |  |
| `_set` | `(self, key, value)` |  |
| `_build_overview_tab` | `(self)` |  |
| `_on_overview_view_changed` | `(self, text)` | Handle a change to the Strips/Heatmap toggle in the Overview toolbar. |
| `_open_overview_element_picker` | `(self)` | Pop a small multi-select menu of available elements. |
| `_clear_overview_elements` | `(self)` | Empty the selected-elements list and redraw. |
| `_refresh_overview_elem_btn` | `(self)` | Sync the picker button's label with the current selection. |
| `_build_dendrogram_tab` | `(self)` |  |
| `_open_3d_sample_picker` | `(self)` | Checkable menu to show/hide samples in the 3D scatter. |
| `_show_all_3d_samples` | `(self)` | Clear the hidden-sample set and redraw the 3D scatter. |
| `_on_3d_scroll` | `(self, event)` | Zoom the 3D axes under the cursor in/out on mouse-wheel scroll. |
| `_set_3d_view` | `(self, elev, azim)` | Snap all 3D axes to a preset view angle. |
| `_draw_3d` | `(self)` |  |
| `_on_3d_hover` | `(self, event)` | Show a tooltip with cluster and element information on 3D hover. |
| `_draw_3d_into` | `(self, target_fig)` |  |
| `_draw_dendrogram` | `(self)` |  |
| `_draw_dendrogram_into` | `(self, target_fig)` |  |
| `_draw_overview` | `(self)` | Render the Overview tab: composition strips (or heatmap) on the |
| `_draw_overview_into` | `(self, target_fig)` | Draw the Overview content into an arbitrary Figure. |
| `_restyle_heatmap_axes` | `(self, ax, fig, cfg)` | Re-apply font and theme to an externally-drawn heatmap axes. |
| `_on_eval_pick` | `(self, event)` | Click a point on an evaluation curve to set K directly. |
| `_on_cluster_hover` | `(self, event)` | Show a floating tooltip with element values when hovering scatter points. |
| `_open_settings` | `(self)` |  |
| `_on_node_changed` | `(self)` |  |
| `_get_elements` | `(self)` |  |
| `_prepare_data` | `(self, elements)` | Prepare data matrix — identical logic to original. |
| `_run_algo` | `(self, name, k, data)` |  |
| `_run_som` | `(self, k, data, cfg, progress_cb=None)` | Train a SOM and cluster the resulting neuron weight vectors. |
| `_evaluate_data` | `(self, data, *, enabled_algos=None, enabled_metrics=None, min_k=None, ` | Run the full algorithm × K × metric sweep on ``data`` once. |
| `_pick_optimal_per_metric` | `(self, eval_results)` | Reduce an eval-results dict to ``{metric: K}`` using vote+tiebreak. |
| `_evaluate_per_sample` | `(self, data)` | Run the evaluation sweep independently on each sample's particles. |
| `_run_evaluation` | `(self)` | Launch K-evaluation on a background worker thread. |
| `_on_eval_done` | `(self, payload)` | Apply evaluation results on the main thread and refresh the UI. |
| `_on_eval_failed` | `(self, message)` | Report an evaluation-worker failure to the user. |
| `_on_eval_thread_finished` | `(self)` | Clean up after the evaluation worker terminates. |
| `_run_bootstrap` | `(self)` | Launch the K-stability bootstrap on a background worker thread. |
| `_on_bootstrap_done` | `(self, payload)` | Apply bootstrap stability results on the main thread. |
| `_on_bootstrap_failed` | `(self, message)` | Report a bootstrap-worker failure to the user. |
| `_on_bootstrap_thread_finished` | `(self)` | Restore the toolbar and progress state after the worker terminates. |
| `_cancel_bootstrap` | `(self)` | Request the running bootstrap worker to stop after the current pass. |
| `_determine_optimal_k` | `(self)` | Compute the optimal K independently for each enabled metric. |
| `_elbow_k` | `(k_vals: list, scores: list) → int` | Kneedle algorithm: find the K at the elbow of a monotone curve. |
| `_update_optimal_label` | `(self)` |  |
| `_update_metric_picks_ui` | `(self)` | Rebuild the per-metric K-pick chips in the toolbar. |
| `_select_metric_pick` | `(self, metric, k)` | Switch the active K selection to the given metric's suggestion. |
| `_refresh_eval_plot` | `(self)` |  |
| `_run_clustering` | `(self)` | Launch the clustering pipeline on a background worker thread. |
| `_set_progress` | `(self, pct)` | Set the toolbar progress bar from a 0-100 percentage. |
| `_on_cluster_progress` | `(self, pct, message)` | Update the progress bar and status text from worker signals. |
| `_on_som_snapshot` | `(self, weights, t, total)` | Render a live SOM convergence frame during training. |
| `_persist_results_to_node` | `(self, sel_k=None)` | Store the full clustering state on the workflow node so it is |
| `_restore_saved_results` | `(self)` | Restore a previously saved clustering state from the workflow |
| `_on_cluster_done` | `(self, payload)` | Finalise clustering results on the main thread and draw all figures. |
| `_on_cluster_failed` | `(self, message)` | Report a worker-thread failure to the user. |
| `_on_cluster_thread_finished` | `(self)` | Clean up after the worker thread terminates (success or failure). |
| `closeEvent` | `(self, event)` | Ensure a running clustering worker finishes before teardown. |
| `_live_k_supported` | `(self)` | Return whether the current algorithm supports live K dragging. |
| `_update_live_k_availability` | `(self)` | Enable or disable the Live checkbox based on the current algorithm. |
| `_on_k_combo_changed` | `(self, text)` | Sync the slider to the combo when the combo changes. |
| `_on_k_slider_changed` | `(self, k)` | Sync the combo to the slider and, if live mode is on, schedule a recut. |
| `_do_live_k` | `(self)` | Recompute clustering for the current slider K on the main thread. |
| `_hier_recut` | `(self, data, k, cfg)` | Cut a cached hierarchical linkage tree at K clusters. |
| `_build_som_tab` | `(self)` |  |
| `_characterise` | `(self, elements, data)` | Generate cluster characterisation with real element-% composition labels. |
| `_rebuild_display_labels` | `(self)` | Recompute cluster_type_short and cluster_type from stored composition. |
| `_apply_display_settings` | `(self)` | Rebuild display labels and redraw all figures without re-clustering. |
| `_run_stability` | `(self)` | Launch the assignment-stability bootstrap on a worker thread. |
| `_cancel_stability` | `(self)` | Request cooperative cancellation of the stability worker. |
| `_on_stability_done` | `(self, payload)` | Store stability results, persist them, and show the result window. |
| `_on_stability_failed` | `(self, message)` | Report a stability-worker failure to the user. |
| `_on_stability_thread_finished` | `(self)` | Restore the toolbar and progress state after the worker exits. |
| `_show_stability_dialog` | `(self)` | Open a window with the stability figure (Jaccard bars + histogram). |
| `_export_results` | `(self)` | Serialise clustering results and characterisation to a JSON file. |
| `_export_methods` | `(self)` | Preview and export an auto-generated methods paragraph. |

### `ClusteringPlotNode` *(extends `QObject`)*

Clustering analysis node with matplotlib figures.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` |  |
| `process_data` | `(self, input_data)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_cluster_centroids` | `(data, labels, valid_labels)` | Compute per-cluster centroids as the arithmetic mean of member points. |
| `_xie_beni_score` | `(data, labels)` | Xie-Beni cluster validity index (lower is better). |
| `_pbm_score` | `(data, labels)` | PBM (I-index) cluster validity index (higher is better). |
| `_sdbw_score` | `(data, labels)` | S_Dbw cluster validity index (lower is better). |
| `_dunn_sym_score` | `(data, labels, max_points=2000, random_state=0)` | Dunn-Symmetric (Sym-Dunn) cluster validity index (higher is better). |
| `_c_index_score` | `(data, labels, max_points=2000, random_state=0)` | C-index cluster validity index (lower is better, bounded in ``[0, 1]``). |
| `_vote_optimal_per_metric` | `(eval_results, elbow_fn, enabled_metrics=None)` | Select an optimal K per metric by voting across algorithms. |
| `_palette_to_plot` | `(pal)` | Map an app ``Palette`` (or None) to the plot/theme keys used here. |
| `_current_plot_palette` | `()` | Return the active plot/theme dict from the app ThemeManager. |
| `_filter_rare_particle_types` | `(matrix, sample_labels, original_indices, min_count)` | Remove particles whose elemental signature occurs fewer than min_count times. |
| `_som_cluster_cmap` | `(name, n_clusters)` | Build a discrete categorical colormap for the SOM cluster grid. |
| `_contrast_text_for` | `(cmap_name, norm_value)` | Pick black or white text for legibility over a colormap cell. |
| `_draw_som_grid` | `(fig, som_obj, neuron_cluster_labels, data_labels, cfg, sample_labels=` | Draw the SOM diagnostic panels: cluster grid, U-matrix, hit-count, |
| `_font_scale` | `(cfg, role='label')` | Return a (FontProperties, color) pair scaled for a given text role. |
| `_text_color` | `(cfg)` | Resolve the colour for figure text in a theme-consistent way. |
| `_muted_color` | `(cfg)` | Theme-aware muted colour for placeholder / empty-state text. |
| `_empty_message` | `(ax, cfg, text)` | Draw a centered, theme- and font-consistent placeholder message. |
| `_plot_theme` | `(cfg)` | Return plot colours (face, grid, text) for the active theme. |
| `_style_ax` | `(ax, cfg, xlabel='', ylabel='', title='')` | Apply consistent visual styling to a matplotlib Axes. |
| `_element_color` | `(element, all_elements_sorted)` | Return a deterministic colour for an element symbol. |
| `_cluster_label_short` | `(cid)` | Return a user-facing display tag for a cluster ID. |
| `_cluster_per_ml_value` | `(cd, input_data)` | Convert a cluster's particle count to particles per mL. |
| `_cluster_size_str` | `(cd, cfg, input_data, renderer=Renderer.MATHTEXT)` | Return the size annotation for a cluster honouring the y-axis unit. |
| `_build_cluster_label` | `(cd, threshold_pct=0.1, max_elems=5, include_count=True, label_mode='S` | Build a "Fe, O, Si (1,234)" style row label from a cluster's |
| `_cluster_primary` | `(cd)` | Return the primary dominant element of a cluster. |
| `_order_clusters` | `(char_for_algo, group_by_dominant=True)` | Return cluster IDs in display order. |
| `_build_sample_data_from_characterisation` | `(char_for_algo, elements, threshold_pct=0.1, max_elems=5, group_by_dom` | Synthesise a ``sample_data`` dict from per-cluster characterisation data. |
| `_draw_composition_strips` | `(ax, char_for_algo, elements, cfg, algo_name='', input_data=None)` | Draw one horizontal stacked bar per cluster showing mass composition. |
| `_draw_sample_share_strip` | `(ax, char_for_algo, sample_names, cfg, group_by_dominant=True)` | Draw a per-cluster sample-fraction strip for multi-sample input. |
| `_draw_detection_panel` | `(ax, char_for_algo, selected_elements, cfg, group_by_dominant=True, in` | Draw per-cluster real detection counts for selected elements. |
| `_draw_evaluation` | `(fig, eval_results, cfg, optimal_k=None, view_algo='All Algorithms', o` | Draw evaluation metric curves on a matplotlib Figure. |
| `_draw_evaluation_per_sample` | `(fig, per_sample_eval, cfg, per_sample_optk=None, view_algo='All Algor` | Draw per-sample evaluation curves as a single metric × sample grid. |
| `_consensus_k` | `(per_metric_k)` | Return the consensus K and its agreement fraction from per-metric picks. |
| `_draw_consensus_summary` | `(fig, eval_results, per_sample_eval, cfg, elbow_fn, optimal_per_metric` | Draw a metric × scope consensus decision table for choosing K. |
| `_draw_clustering` | `(fig, clustering_results, data_matrix, characterisation, cfg, input_da` | Draw cluster scatter plots on a matplotlib Figure. |
| `_draw_stability` | `(fig, stab, cfg)` | Draw bootstrap stability results: cluster Jaccard bars + particle histogram. |
| `_algo_params_str` | `(cfg, algo)` | Return a human-readable parameter summary for one algorithm. |
| `build_methods_paragraph` | `(cfg, optimal_k=None, algorithm=None, n_particles=None, n_elements=Non` | Generate a publication-ready methods paragraph from the node settings. |
