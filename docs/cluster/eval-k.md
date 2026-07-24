# `eval_k.py`

Interactive 'Evaluate K' web tab for the Clustering Analysis dialog.

Replaces the matplotlib evaluation view with a live web view: it sweeps k for
the selected algorithm (``live_engine.evaluate_k``) on the same 2-D
projection the Cluster tab uses, streams the silhouette / Calinski-Harabasz /
Davies-Bouldin scores per k, and draws them as interactive curves. Hovering a k
shows the values; clicking a k applies it to the toolbar K selector so the next
``② Cluster`` uses it.

Reuses the ``live`` helpers (``build_view``, theme, ``_safe_dumps``,
QtWebEngine availability) so it stays consistent with the Cluster tab.

---

## Classes

### `_EvalWorker` *(extends `QThread`)*

Sweep k off the UI thread, emitting one JSON result per k.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, xy, algo, params, k_min, k_max, parent=None)` | Store the sweep configuration. |
| `cancel` | `(self)` | Request cancellation of the sweep. |
| `run` | `(self)` | Run the k-sweep and emit each k's scores, then emit done. |

### `ClusterEvalBridge` *(extends `QObject`)*

QWebChannel object exposed to the evaluation web page.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, dialog, parent=None)` | Initialise bridge state. |
| `attach_page` | `(self, page)` | Give the bridge the page for runJavaScript pushes. |
| `_push_js` | `(self, code)` | Run JavaScript on the page if attached. |
| `_proj_dims` | `(self)` | Return (projection, n_dims) from the shared node config. |
| `get_theme` | `(self)` | Return theme CSS variables as JSON. |
| `get_config` | `(self)` | Return the current algorithm, k-range and projection as JSON. |
| `_algo_params` | `(self, algo)` | Non-k params for ``algo`` from the shared config (same as Cluster). |
| `set_algorithm` | `(self, algo)` | Persist the selected algorithm to the shared config (syncs Cluster). |
| `set_krange` | `(self, k_min, k_max)` | Persist the K sweep range to the shared config. |
| `run_evaluation` | `(self, algo, k_min, k_max)` | Build the projection and stream validity scores for k in range. |
| `_on_k` | `(self, payload)` | Push one k's scores to the page. |
| `_on_done` | `(self, summary)` | Tell the page the sweep finished. |
| `stop` | `(self)` | Cancel the running sweep. |
| `apply_k` | `(self, k)` | Apply the chosen k to the toolbar selector and shared config. |

### `ClusterEvalTab` *(extends `QWidget`)*

QWidget hosting the interactive evaluation web view.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, dialog)` | Build the web view, bridge and channel. |
| `_inject_qwebchannel` | `(self)` | Inject qwebchannel.js from the Qt resource before page scripts run. |
| `_on_load_finished` | `(self, ok)` | Apply the theme once the page has loaded. |
| `apply_theme` | `(self)` | Push the current palette into the page. |
| `trigger_eval` | `(self)` | Start a K-sweep from Python (toolbar '① Evaluate K' button). |
| `refresh_config` | `(self)` | Re-sync the page controls with the shared config (no run). |
