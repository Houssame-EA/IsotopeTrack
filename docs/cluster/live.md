# `live.py`

Interactive *live* clustering tab for the Clustering Analysis dialog.

Adds a QWebEngineView-backed tab that animates *how each clustering algorithm
builds its answer* — centroids sliding, densities flooding, neuron grids
unfolding — on the same particle data the rest of the dialog uses. Python does
the maths (``live_engine`` — pure NumPy steppers); a small JS/Canvas
frontend renders it and talks back over ``QWebChannel``.

The tab is **read-only** with respect to the dialog: it builds its own 2-D PCA
view of the data and never mutates the dialog's caches, so it can't interfere
with the real evaluate/cluster pipeline or the strips/heatmap figures. It
follows the application's dark/light palette live.

If QtWebEngine is unavailable the tab degrades to a short message and the rest
of the dialog is unaffected.

---

## Constants

| Name | Value |
|------|-------|
| `SCALING_OPTIONS` | `['CLR', 'ILR', 'Robust Z-score', 'None']` |
| `DATA_TYPE_OPTIONS` | `['Counts', 'Element Mass (fg)', 'Particle Mass (fg)', 'El…` |
| `PROJECTION_ORDER` | `['PCA', 't-SNE', 'UMAP', 'None']` |
| `DATA_KEY_MAP` | `{'Counts': 'elements', 'Element Mass (fg)': 'element_mass…` |
| `ALGO_PARAM_MAP` | `{'K-Means': {'max_iter': 'kmeans_max_iter', 'n_init': 'km…` |
| `PROJECTION_TO_DIMRED` | `{'PCA': 'PCA', 't-SNE': 't-SNE', 'UMAP': 'UMAP', 'None': …` |
| `SHAPE_OVERRIDE_KEY` | `'cluster_sample_shapes'` |
| `EMBED_FIT_MAX` | `3000` |

## Classes

### `_FrameWorker` *(extends `QThread`)*

QThread that streams one clustering run's frames as JSON.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, xy, algo, params, seed=42, parent=None)` | Store the run configuration. |
| `cancel` | `(self)` | Request cancellation of the running stream. |
| `run` | `(self)` | Iterate the engine and emit each frame as JSON, then emit done. |

### `_SkWorker` *(extends `QThread`)*

QThread that computes the authoritative scikit-learn labels.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, Xs, xy, cfg, k, seq=0, settle=False, parent=None)` | Store the matrices and config for one comparison run. |
| `run` | `(self)` | Fit with scikit-learn and emit one frame in the page's frame shape. |

### `_ProjWorker` *(extends `QThread`)*

Compute a projection off the UI thread (t-SNE/UMAP can take seconds).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, input_data, cfg, elements, projection, dims, parent=None)` | Store the projection arguments. |
| `run` | `(self)` | Build the projection view off the UI thread and emit it. |

### `ClusterLiveBridge` *(extends `QObject`)*

QWebChannel object bridging the NumPy engine to the web page.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, dialog, parent=None)` | Initialise the bridge's state from the shared node config. |
| `attach_page` | `(self, page)` | Give the bridge direct access to the page for runJavaScript pushes. |
| `_push_js` | `(self, code)` | Run a snippet of JavaScript on the page if one is attached. |
| `rebuild` | `(self)` | Synchronous rebuild (used for the fast PCA path / fallbacks). |
| `rebuild_async` | `(self, animate=False)` | Compute the projection on a worker thread, then push state to JS. |
| `_on_projected` | `(self, view)` | Store the finished view and push the new state to the page. |
| `_current_k` | `(self)` | Return the cluster count K shared with the app (toolbar / config). |
| `_param_values` | `(self)` | Config-derived value for every algorithm's parameters. |
| `_cfg_snapshot` | `(self)` | Return the current preprocessing/algorithm config as a plain dict. |
| `_state_payload` | `(self)` | Assemble the full state dict that is sent to the page. |
| `get_schema` | `(self)` | Return algorithms, scalings, data types and projections as JSON. |
| `get_theme` | `(self)` | Return the current theme CSS variables as JSON. |
| `get_state` | `(self)` | Return the current view state as JSON, building it if needed. |
| `set_label_mode` | `(self, mode)` | Persist the element label style and repaint the other views. |
| `set_cluster_color` | `(self, cid, color)` | Persist one cluster's colour and repaint the other views. |
| `reset_cluster_colors` | `(self)` | Drop every colour override and repaint the other views. |
| `set_sample_shape` | `(self, sample, shape)` | Persist the marker shape used for one sample. |
| `reset_sample_shapes` | `(self)` | Drop every marker-shape assignment, restoring the default cycle. |
| `_redraw_host_figures` | `(self)` | Redraw the dialog's figures after a shared appearance change. |
| `_do_redraw_host` | `(self)` | Repaint the dialog's figures without re-running the clustering. |
| `pick_color` | `(self, initial)` | Open the native colour dialog and return the chosen ``#RRGGBB``. |
| `set_projection` | `(self, projection, dims)` | Change projection / dimensionality, persist to config, re-project. |
| `set_config` | `(self, payload_json)` | Update the shared node config from the panel, then re-project. |
| `_invalidate_host_matrix` | `(self)` | Drop the dialog's cached matrix so the next run re-prepares it. |
| `set_param` | `(self, algo, key, value_json)` | Persist one algorithm parameter to the shared node config. |
| `run` | `(self, algo, params_json)` | Start a clustering run and stream its frames to the page. |
| `run_sklearn` | `(self, settle=False)` | Compute the authoritative scikit-learn labels for the shown particles. |
| `_sk_finished` | `(self, payload)` | Adopt the settled labels, then re-run if a request was queued. |
| `_push_compare` | `(self, s)` | Main-thread relay: deliver the comparison result to the page. |
| `_relay_frame` | `(self, s)` | Main-thread relay: deliver a frame to the page. |
| `_flush_frames` | `(self)` | Push any buffered frames to the page in a single batch. |
| `stop` | `(self)` | Cancel and dispose of the running frame worker. |
| `_on_done` | `(self, summary)` | Flush remaining frames, then settle the view on the real result. |
| `_apply_to_overview` | `(self)` | Feed the Cluster tab's result into the Overview strips/heatmap. |

### `ClusterLiveTab` *(extends `QWidget`)*

QWidget hosting the interactive clustering web view.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, dialog)` | Build the web view, bridge and channel that make up the tab. |
| `_connect_downloads` | `(self)` | Accept image exports from the page and let the user choose where. |
| `_on_download` | `(self, item)` | Prompt for a destination and accept or cancel the download. |
| `_on_download_done` | `(self, item)` | Report the saved path (or the failure) on the page's status line. |
| `_inject_qwebchannel` | `(self)` | Load qwebchannel.js from the Qt resource and inject at doc creation. |
| `_on_load_finished` | `(self, ok)` | Apply the theme and push data once the page has loaded. |
| `mark_dirty` | `(self)` | Flag that the data/config changed, so the next show rebuilds. |
| `refresh_data` | `(self, force=False)` | Rebuild the view only when the data changed since last time. |
| `apply_theme` | `(self)` | Push the current app palette into the page (dark/light switch). |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_safe_dumps` | `(obj)` | json.dumps that never emits bare NaN/Infinity (invalid JSON for JS). |
| `_projection_options` | `()` | Return every projection method, each flagged with its availability. |
| `_last_dir` | `()` | Folder that file dialogs should open in, via the app's shared memory. |
| `_remember_dir` | `(path)` | Persist *path* as the folder future file dialogs should start in. |
| `_theme_vars` | `()` | Map the active app Palette to the CSS variables the page consumes. |
| `sample_shape_overrides` | `(cfg)` | Return the per-sample marker shapes stored on the node config. |
| `_rare_filter` | `(matrix, samples, min_count)` | Drop particles whose non-zero element signature is rarer than min_count. |
| `_propagate_labels` | `(sub_raw, sub_labels, raw_full)` | Give every particle the label of its nearest labelled sample particle. |
| `_embed_fit_index` | `(n)` | Row indices used to fit an embedding. |
| `_place_rest` | `(Xs, fit_idx, Pf)` | Give every particle a position in an embedding fitted on a subset. |
| `_embed` | `(Xs, projection, n_dims)` | Project the scaled matrix to ``n_dims`` (2 or 3) with the chosen method. |
| `_raw_axes` | `(Xs, elements, n_dims)` | Select raw feature axes for the 'None' (no-reduction) projection. |
| `build_view` | `(input_data, cfg, elements, projection='PCA', n_dims=2, max_points=Non` | Build an N-D projection view + aligned raw matrix from the dialog's data. |
| `sklearn_cluster` | `(Xs, cfg, k)` | Cluster ``Xs`` exactly the way the ② Cluster tab would. |
| `_sklearn_params` | `(algo, cfg, k)` | Translate ``node.config`` into the parameter names run_algorithm expects. |
