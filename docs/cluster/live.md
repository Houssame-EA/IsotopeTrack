# `live.py`

Interactive clustering tab for the Clustering Analysis dialog.

Shows the clustering the rest of the dialog computed, in a 2-D or 3-D view of
the same particles, alongside a detail figure and a worked example describing
that fit. :mod:`results.cluster.detail` derives both from the fit;
:mod:`results.cluster.live_qt` draws everything.

**The clustering is computed once.** When ② Cluster has already fitted this
configuration over these particles, its labels are adopted as they are — see
:meth:`ClusterLiveController._reusable_labels`. Only a configuration ② Cluster
has not fitted causes this tab to fit, and then only once, off the UI thread.
That is also why the two tabs cannot show different answers.

The tab builds its own display projection and does not mutate the dialog's
caches while an authoritative run is active. It follows the application's
dark/light palette live.

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
| `FIT_CONFIG_KEYS` | `('scaling', 'data_type_display', 'filter_zeros', 'min_par…` |
| `SHAPE_OVERRIDE_KEY` | `'cluster_sample_shapes'` |
| `OVERLAY_CMAP_KEY` | `'cluster_overlay_colormap'` |
| `DEFAULT_OVERLAY_CMAP` | `OVERLAY_COLORMAPS[0] if OVERLAY_COLORMAPS else 'viridis'` |
| `_CMAP_STOPS` | `None` |
| `EMBED_FIT_MAX` | `3000` |

## Classes

### `_ProjWorker` *(extends `QThread`)*

Compute a projection off the UI thread (t-SNE/UMAP can take seconds).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, input_data, cfg, elements, projection, dims, parent=None)` | Store the projection arguments. |
| `run` | `(self)` | Build the projection view off the UI thread and emit it. |

### `ClusterLiveController` *(extends `QObject`)*

Drives the live view: owns the projection, the fit and the config.

Holds the built view for the current projection, produces the tab's one
clustering result off the UI thread, and is the single place where the
shared ``node.config`` is written.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, dialog, parent=None)` | Initialise the bridge's state from the shared node config. |
| `attach_view` | `(self, view)` | Adopt the :class:`~results.cluster.live_qt.view.LiveView` to drive. |
| `rebuild` | `(self)` | Synchronous rebuild (used for the fast PCA path / fallbacks). |
| `rebuild_async` | `(self)` | Compute the projection on a worker thread, then push state to the view. |
| `_retire_proj_worker` | `(self, worker)` | Park a superseded projection worker until its thread has stopped. |
| `_on_retired_proj_finished` | `(self)` | Release a retired worker once its thread has fully stopped. |
| `_on_projected` | `(self, view)` | Store the finished view and hand the new state to the widget. |
| `_current_k` | `(self)` | Return the cluster count K shared with the app (toolbar / config). |
| `_param_values` | `(self)` | Config-derived value for every algorithm's parameters. |
| `_cfg_snapshot` | `(self)` | Return the current preprocessing/algorithm config as a plain dict. |
| `_state_payload` | `(self)` | Assemble the full state dict that is sent to the page. |
| `get_schema` | `(self)` | Return algorithms, scalings, data types and projections. |
| `get_theme` | `(self)` | Return the current theme colours. |
| `get_state` | `(self)` | Return the current view state, building it if needed. |
| `set_label_mode` | `(self, mode)` | Persist the element label style and repaint the other views. |
| `set_cluster_color` | `(self, cid, color)` | Persist one cluster's colour and repaint the other views. |
| `reset_cluster_colors` | `(self)` | Drop every colour override and repaint the other views. |
| `set_sample_shape` | `(self, sample, shape)` | Persist the marker shape used for one sample. |
| `reset_sample_shapes` | `(self)` | Drop every marker-shape assignment, restoring the default cycle. |
| `set_overlay_colormap` | `(self, name)` | Persist the colormap used by the colour-by-element overlay. |
| `_redraw_host_figures` | `(self)` | Redraw the dialog's figures after a shared appearance change. |
| `_do_redraw_host` | `(self)` | Repaint the dialog's figures without re-running the clustering. |
| `set_projection` | `(self, projection, dims)` | Change projection / dimensionality, persist to config, re-project. |
| `set_config` | `(self, patch)` | Update the shared node config from the panel, then re-project. |
| `_invalidate_host_matrix` | `(self)` | Drop the dialog's cached matrix so the next run re-prepares it. |
| `set_param` | `(self, algo, key, value)` | Persist one algorithm parameter to the shared node config. |
| `run` | `(self, algo, params=None)` | Produce the tab's clustering result for ``algo``. |
| `_cache_fit` | `(self, res)` | Remember a completed fit so an identical request need not redo it. |
| `_reusable_labels` | `(self, algo, k)` | Return an existing fit for ``algo`` that this run can adopt as-is. |
| `_host_matrix` | `(self)` | Return the matrix ② Cluster clustered, when it is still cached. |
| `_host_estimator` | `(self, algo)` | Return the estimator ② Cluster fitted for ``algo``, if it kept one. |
| `_host_som` | `(self)` | Return the host's trained self-organising map, if there is one. |
| `fit` | `(self)` | Show the clustering for the current configuration. |
| `_request_host_run` | `(self, algo, k)` | Ask ② Cluster to compute the configuration the tab is showing. |
| `_adopt` | `(self, payload)` | Take on a result and report it. |
| `_push_result` | `(self, res)` | Main-thread relay: deliver the clustering result to the view. |
| `stop` | `(self)` | No-op: the tab owns no worker of its own. |

### `ClusterLiveTab` *(extends `QWidget`)*

QWidget hosting the interactive clustering view.

``dialog.py`` constructs this with the dialog, then calls :meth:`arm`,
:meth:`mark_dirty`, :meth:`refresh_data` and :meth:`apply_theme`.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, dialog)` | Set up the tab shell without building the view. |
| `ensure_view` | `(self)` | Create the view the first time this tab is actually shown. |
| `showEvent` | `(self, event)` | Build the view on first display, then behave normally. |
| `arm` | `(self)` | Allow the view to draw, once a clustering run has produced results. |
| `mark_dirty` | `(self)` | Flag that the data/config changed, so the next show rebuilds. |
| `refresh_data` | `(self, force=False)` | Rebuild the view only when the data changed since last time. |
| `apply_theme` | `(self)` | Push the current app palette into the view (dark/light switch). |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_projection_options` | `()` | Return every projection method, each flagged with its availability. |
| `fit_fingerprint` | `(cfg, algo, k)` | Identify a clustering fit by everything that can change its answer. |
| `index_signature` | `(idx)` | Return an exact, cheap identity for a particle index array. |
| `_compare_payload` | `(labels, xy, info, seq)` | Build the result payload the view expects from a fit. |
| `_theme_vars` | `()` | Map the active app Palette to the CSS variables the page consumes. |
| `colormap_stops` | `(n_stops=32)` | Sample every offered colormap into plain hex stops for the web view. |
| `overlay_colormap` | `(cfg)` | Return the colour-by-element colormap saved on the node config. |
| `sample_shape_overrides` | `(cfg)` | Return the per-sample marker shapes stored on the node config. |
| `_rare_filter` | `(matrix, samples, min_count)` | Drop particles whose non-zero element signature is rarer than min_count. |
| `_embed_fit_index` | `(n)` | Row indices used to fit an embedding. |
| `_place_rest` | `(Xs, fit_idx, Pf)` | Give every particle a position in an embedding fitted on a subset. |
| `_embed` | `(Xs, projection, n_dims, params=None)` | Project the scaled matrix to ``n_dims`` (2 or 3) with the chosen method. |
| `_raw_axes` | `(Xs, elements, n_dims)` | Select raw feature axes for the 'None' (no-reduction) projection. |
| `build_view` | `(input_data, cfg, elements, projection='PCA', n_dims=2, max_points=Non` | Build an N-D projection view + aligned raw matrix from the dialog's data. |
| `_sklearn_params` | `(algo, cfg, k)` | Translate ``node.config`` into an algorithm's own parameter names. |
| `describe_fit` | `(cfg, k, labels, info, xy=None, som=None)` | Derive the detail view and worked example from a finished fit. |
