"""Interactive 'Evaluate K' web tab for the Clustering Analysis dialog.

Replaces the matplotlib evaluation view with a live web view: it sweeps k for
the selected algorithm (``live_engine.evaluate_k``) on the same 2-D
projection the Cluster tab uses, streams the silhouette / Calinski-Harabasz /
Davies-Bouldin scores per k, and draws them as interactive curves. Hovering a k
shows the values; clicking a k applies it to the toolbar K selector so the next
``② Cluster`` uses it.

Reuses the ``live`` helpers (``build_view``, theme, ``_safe_dumps``,
QtWebEngine availability) so it stays consistent with the Cluster tab.
"""

from __future__ import annotations

import json
import os
import logging

import numpy as np

from PySide6.QtCore import QObject, Signal, Slot, QThread, QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from results.cluster.live import (
    WEBENGINE_OK, build_view, _theme_vars, _safe_dumps, ALGO_PARAM_MAP,
)
import results.cluster.live_engine as engine

if WEBENGINE_OK:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings
    from PySide6.QtWebChannel import QWebChannel

_log = logging.getLogger("IsotopeTrack.results.cluster.eval_k")


class _EvalWorker(QThread):
    """Sweep k off the UI thread, emitting one JSON result per k."""

    result = Signal(str)
    done = Signal(str)

    def __init__(self, xy, algo, params, k_min, k_max, parent=None):
        """Store the sweep configuration."""
        super().__init__(parent)
        self._xy = xy
        self._algo = algo
        self._params = params
        self._k_min = k_min
        self._k_max = k_max
        self._cancel = False

    def cancel(self):
        """Request cancellation of the sweep."""
        self._cancel = True

    def run(self):
        """Run the k-sweep and emit each k's scores, then emit done."""
        n = 0
        try:
            for r in engine.evaluate_k(self._xy, self._algo, self._params,
                                       self._k_min, self._k_max):
                if self._cancel:
                    break
                self.result.emit(_safe_dumps(r))
                n += 1
        except Exception as exc:
            _log.exception("evaluation sweep failed")
            self.done.emit(json.dumps({"error": str(exc), "count": n}))
            return
        self.done.emit(json.dumps({"error": None, "count": n}))


class ClusterEvalBridge(QObject):
    """QWebChannel object exposed to the evaluation web page."""

    def __init__(self, dialog, parent=None):
        """Initialise bridge state."""
        super().__init__(parent)
        self._dialog = dialog
        self._page = None
        self._worker = None

    def attach_page(self, page):
        """Give the bridge the page for runJavaScript pushes."""
        self._page = page

    def _push_js(self, code):
        """Run JavaScript on the page if attached."""
        if self._page is not None:
            try:
                self._page.runJavaScript(code)
            except Exception:
                _log.exception("eval runJavaScript push failed")

    def _proj_dims(self):
        """Return (projection, n_dims) from the shared node config."""
        cfg = self._dialog.node.config
        dr = cfg.get("dim_reduction", "PCA")
        proj = dr if dr in ("PCA", "t-SNE", "UMAP", "None") else "PCA"
        dims = 3 if int(cfg.get("n_components", 2)) == 3 else 2
        return proj, dims

    @Slot(result=str)
    def get_theme(self):
        """Return theme CSS variables as JSON."""
        return json.dumps(_theme_vars())

    @Slot(result=str)
    def get_config(self):
        """Return the current algorithm, k-range and projection as JSON."""
        cfg = self._dialog.node.config
        proj, dims = self._proj_dims()
        algos = [name for name, spec in engine.ALGORITHMS.items()
                 if any(p["key"] == "k" for p in spec["params"])]
        sel = cfg.get("selected_algorithm", "K-Means")
        if sel not in algos:
            sel = "K-Means"
        return json.dumps({
            "algorithm": sel, "algorithms": algos,
            "k_min": int(cfg.get("min_clusters", 2)),
            "k_max": int(cfg.get("max_clusters", 10)),
            "projection": proj, "dims": dims,
            "theme": _theme_vars(),
        })

    def _algo_params(self, algo):
        """Non-k params for ``algo`` from the shared config (same as Cluster)."""
        cfg = self._dialog.node.config
        spec = engine.ALGORITHMS.get(algo)
        params = {}
        if spec:
            for p in spec["params"]:
                if p["key"] == "k":
                    continue
                cfgkey = ALGO_PARAM_MAP.get(algo, {}).get(p["key"])
                params[p["key"]] = (cfg.get(cfgkey, p["default"]) if cfgkey
                                    else p["default"])
        return params

    @Slot(str)
    def set_algorithm(self, algo):
        """Persist the selected algorithm to the shared config (syncs Cluster)."""
        cfg = self._dialog.node.config
        cfg["selected_algorithm"] = algo
        cfg["enabled_algorithms"] = [algo]

    @Slot(int, int)
    def set_krange(self, k_min, k_max):
        """Persist the K sweep range to the shared config."""
        cfg = self._dialog.node.config
        cfg["min_clusters"] = int(k_min)
        cfg["max_clusters"] = int(k_max)

    @Slot(str, int, int)
    def run_evaluation(self, algo, k_min, k_max):
        """Build the projection and stream validity scores for k in range.

        Uses the same algorithm parameters as the Cluster tab (from the shared
        config) and persists the algorithm + K range so everything stays in step.
        """
        self.stop()
        try:
            elements = self._dialog._get_elements()
            proj, dims = self._proj_dims()
            view = build_view(self._dialog.node.input_data,
                              self._dialog.node.config, elements,
                              projection=proj, n_dims=dims)
        except Exception:
            _log.exception("eval view build failed")
            view = None
        if view is None:
            self._push_js("window.__clusterEval && window.__clusterEval.done("
                          "{\"error\":\"no data\"});")
            return
        cfg = self._dialog.node.config
        cfg["selected_algorithm"] = algo
        cfg["enabled_algorithms"] = [algo]
        cfg["min_clusters"] = int(k_min)
        cfg["max_clusters"] = int(k_max)
        params = self._algo_params(algo)
        w = _EvalWorker(np.asarray(view["xy"]), algo, params,
                        int(k_min), int(k_max))
        w.result.connect(self._on_k)
        w.done.connect(self._on_done)
        self._worker = w
        w.start()

    def _on_k(self, payload):
        """Push one k's scores to the page."""
        self._push_js("window.__clusterEval && "
                      "window.__clusterEval.pushK(%s);" % payload)

    def _on_done(self, summary):
        """Tell the page the sweep finished."""
        self._push_js("window.__clusterEval && "
                      "window.__clusterEval.done(%s);" % summary)

    @Slot()
    def stop(self):
        """Cancel the running sweep."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)
        self._worker = None

    @Slot(int)
    def apply_k(self, k):
        """Apply the chosen k to the toolbar selector and shared config."""
        dlg = self._dialog
        try:
            dlg.node.config["live_k"] = int(k)
            kc = dlg.k_combo
            if kc.findText(str(k)) < 0:
                kc.addItem(str(k))
            kc.setEnabled(True)
            kc.setCurrentText(str(k))
        except Exception:
            _log.exception("apply_k failed")


class ClusterEvalTab(QWidget):
    """QWidget hosting the interactive evaluation web view."""

    def __init__(self, dialog):
        """Build the web view, bridge and channel."""
        super().__init__()
        self._dialog = dialog
        self._loaded = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if not WEBENGINE_OK:
            layout.addWidget(QLabel("The interactive Evaluate-K view needs "
                                    "QtWebEngine, which isn't available here."))
            self.view = None
            return
        self.view = QWebEngineView(self)
        st = self.view.settings()
        st.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        st.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        self._inject_qwebchannel()
        self.backend = ClusterEvalBridge(dialog, self)
        self.backend.attach_page(self.view.page())
        self.channel = QWebChannel(self.view.page())
        self.channel.registerObject("backend", self.backend)
        self.view.page().setWebChannel(self.channel)
        self.view.loadFinished.connect(self._on_load_finished)
        index = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "eval_ui", "index.html")
        self.view.load(QUrl.fromLocalFile(index))
        layout.addWidget(self.view)

    def _inject_qwebchannel(self):
        """Inject qwebchannel.js from the Qt resource before page scripts run."""
        try:
            from PySide6.QtWebEngineCore import QWebEngineScript
            from PySide6.QtCore import QFile, QIODevice
            f = QFile(":/qtwebchannel/qwebchannel.js")
            if not f.open(QIODevice.ReadOnly):
                return
            try:
                src = bytes(f.readAll().data()).decode("utf-8")
            finally:
                f.close()
            s = QWebEngineScript()
            s.setName("qwebchannel.js")
            s.setSourceCode(src)
            ip = getattr(QWebEngineScript, "InjectionPoint", QWebEngineScript)
            wid = getattr(QWebEngineScript, "ScriptWorldId", QWebEngineScript)
            s.setInjectionPoint(getattr(ip, "DocumentCreation"))
            s.setWorldId(getattr(wid, "MainWorld"))
            s.setRunsOnSubFrames(False)
            self.view.page().scripts().insert(s)
        except Exception:
            _log.exception("eval qwebchannel injection failed")

    def _on_load_finished(self, ok):
        """Apply the theme once the page has loaded."""
        self._loaded = bool(ok)
        if ok:
            self.apply_theme()

    def apply_theme(self):
        """Push the current palette into the page."""
        if self.view is None or not self._loaded:
            return
        try:
            self.view.page().runJavaScript(
                "window.applyTheme && window.applyTheme(%s);"
                % json.dumps(_theme_vars()))
        except Exception:
            _log.exception("eval apply_theme failed")

    def trigger_eval(self):
        """Start a K-sweep from Python (toolbar '① Evaluate K' button).

        Re-syncs the page controls with the shared config first, then runs.
        """
        if self.view is None or not self._loaded:
            return
        try:
            cfg = json.dumps(self.backend.get_config())
            self.view.page().runJavaScript(
                "window.__evalSyncAndRun && window.__evalSyncAndRun(%s);" % cfg)
        except Exception:
            _log.exception("trigger_eval failed")

    def refresh_config(self):
        """Re-sync the page controls with the shared config (no run)."""
        if self.view is None or not self._loaded:
            return
        try:
            cfg = json.dumps(self.backend.get_config())
            self.view.page().runJavaScript(
                "window.__evalSync && window.__evalSync(%s);" % cfg)
        except Exception:
            _log.exception("refresh_config failed")
