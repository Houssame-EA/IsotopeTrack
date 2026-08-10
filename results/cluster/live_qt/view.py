"""The live view widget: assembles the figure and the panels.

This is the piece the controller in :mod:`results.cluster.live` talks to. It
owns the scatter, both legends, the control panel, the detail box and the
worked-example box, and exposes two entry points the controller calls:

* :meth:`LiveView.set_state` — a new dataset and projection
* :meth:`LiveView.result_ready` — the clustering result arrived

Requests travel the other way as Qt signals, so the widget never reaches into
the controller.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMenu,
                               QProgressBar, QPushButton, QVBoxLayout,
                               QWidget)

from . import export as export_mod
from .equation import EquationBox
from .floatbox import FloatBox
from .insets import InsetBox
from .legend import ColorPicker, LegendPanel
from .panel import ControlPanel, SettingsDialog
from .scatter import ClusterScatter, rebuild_overlay
from .state import PALETTE, SHAPES, THEME, LiveState



class MetricChip(QFrame):
    """A metric box: a small muted caption over a large value."""

    def __init__(self, caption, parent=None):
        """Build the chip.

        Args:
            caption (str): The static label, such as 'Clusters'.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(9, 3, 9, 4)
        lay.setSpacing(0)
        self.caption = QLabel(caption)
        self.caption.setObjectName('chipKey')
        self.caption.setAlignment(Qt.AlignHCenter)
        lay.addWidget(self.caption)
        self.value = QLabel('–')
        self.value.setObjectName('chipValue')
        self.value.setAlignment(Qt.AlignHCenter)
        lay.addWidget(self.value)

    def set_value(self, v):
        """Set the displayed value.

        Args:
            v: Anything printable; ``None`` shows an en dash.
        """
        self.value.setText('–' if v is None else str(v))

    def apply_theme(self):
        """Restyle for the active palette."""
        self.setStyleSheet(
            'MetricChip{background:%(chip)s;border:1px solid %(stroke)s;'
            'border-radius:6px;}'
            'QLabel#chipKey{color:%(muted)s;font-size:9px;'
            'letter-spacing:.05em;background:transparent;}'
            'QLabel#chipValue{color:%(text)s;font-size:14px;font-weight:600;'
            'background:transparent;}'
            % {'chip': THEME.chip, 'muted': THEME.muted, 'text': THEME.text,
               'stroke': THEME.stroke2})


class LiveView(QWidget):
    """The whole live tab below the controller."""

    request_run = Signal(str, dict)
    request_config = Signal(dict)
    request_projection = Signal(str, int)
    request_param = Signal(str, str, object)
    request_cluster_color = Signal(int, str)
    request_reset_colors = Signal()
    request_sample_shape = Signal(str, str)
    request_reset_shapes = Signal()
    request_label_mode = Signal(str)
    request_overlay_colormap = Signal(str)

    def __init__(self, parent=None):
        """Build the view.

        Args:
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self.S = LiveState()
        self._state_seq = None
        self._run_timer = QTimer(self)
        self._run_timer.setSingleShot(True)
        self._run_timer.timeout.connect(self._do_run)
        self._build_ui()

    def _build_ui(self):
        """Assemble the top bar, the plot, the floating boxes and the panel.

        The parameters panel overlays the left edge of the plot rather than
        sharing width with it, so hiding it gives the whole width back to the
        scatter.
        """
        S = self.S
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QWidget()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(10, 6, 10, 6)
        bl.setSpacing(10)

        self.menu_btn = QPushButton('☰')
        self.menu_btn.setObjectName('menuBtn')
        self.menu_btn.setToolTip('Show or hide the parameters panel')
        self.menu_btn.setCheckable(True)
        self.menu_btn.setChecked(True)
        self.menu_btn.setFixedSize(30, 26)
        self.menu_btn.toggled.connect(self._toggle_panel)
        bl.addWidget(self.menu_btn)
        bl.addSpacing(6)

        self.algo_title = QLabel('K-Means')
        self.algo_title.setObjectName('algoTitle')
        bl.addWidget(self.algo_title)

        self.note = QLabel('')
        self.note.setObjectName('note')
        bl.addWidget(self.note)

        self.busy = QProgressBar()
        self.busy.setObjectName('busy')
        self.busy.setRange(0, 0)
        self.busy.setTextVisible(False)
        self.busy.setFixedSize(110, 4)
        self.busy.setVisible(False)
        bl.addWidget(self.busy)
        bl.addStretch(1)

        self.show_inset_btn = QPushButton('◱  Detail view')
        self.show_inset_btn.setObjectName('showBtn')
        self.show_inset_btn.setToolTip('Show the detail view')
        self.show_inset_btn.clicked.connect(self._show_inset)
        self.show_inset_btn.setVisible(False)
        bl.addWidget(self.show_inset_btn)

        self.show_eq_btn = QPushButton('∑  Example')
        self.show_eq_btn.setObjectName('showBtn')
        self.show_eq_btn.setToolTip('Show the worked example')
        self.show_eq_btn.clicked.connect(self._show_equation)
        self.show_eq_btn.setVisible(False)
        bl.addWidget(self.show_eq_btn)

        bl.addSpacing(6)
        self.chip_k = MetricChip('Clusters')
        self.chip_noise = MetricChip('Noise')
        bl.addWidget(self.chip_k)
        bl.addWidget(self.chip_noise)
        outer.addWidget(bar)

        centre = QWidget()
        cl = QVBoxLayout(centre)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        self._centre = centre

        self.scatter = ClusterScatter(S)
        self.scatter.hovered.connect(self._on_hover)
        self.scatter.rotated.connect(self._redraw)
        self.scatter.setContextMenuPolicy(Qt.CustomContextMenu)
        self.scatter.customContextMenuRequested.connect(self._context_menu)
        cl.addWidget(self.scatter, 1)

        self.legend = LegendPanel(S)
        self.legend.focus_cluster.connect(self.set_focus)
        self.legend.toggle_cluster.connect(self._toggle_cluster)
        self.legend.recolor_cluster.connect(self._pick_cluster_color)
        self.legend.focus_sample.connect(self.set_sample_focus)
        self.legend.toggle_sample.connect(self._toggle_sample)
        self.legend.cycle_sample_shape.connect(self._cycle_sample_shape)
        self.legend_box = FloatBox('Clusters', self.legend, centre)

        self.inset = InsetBox(S)
        self.inset_box = FloatBox('Detail', self.inset, centre, subtitle=True)
        self.inset.title_changed.connect(self._on_inset_title)
        self.inset.availability_changed.connect(self.inset_box.setVisible)
        self.inset_box.setVisible(False)

        self.equation = EquationBox(S)
        self.equation_box = FloatBox('Worked example', self.equation, centre)
        self.equation.title_changed.connect(
            lambda t, _s: self.equation_box.set_title(t))
        self.equation.availability_changed.connect(self.equation_box.setVisible)
        self.equation_box.setVisible(False)

        self._boxes = [self.legend_box, self.inset_box, self.equation_box]
        self._boxes_placed = False
        outer.addWidget(centre, 1)

        self.panel = ControlPanel(S)
        self.panel.config_changed.connect(self.request_config)
        self.panel.projection_changed.connect(self.request_projection)
        self.panel.algorithm_changed.connect(self._on_algorithm)
        self.panel.param_changed.connect(self._on_param)
        self.panel.run_clicked.connect(self.run)
        self.panel.overlay_changed.connect(self._on_overlay)
        self.panel.colormap_changed.connect(self.request_overlay_colormap)
        self.panel.biplot_changed.connect(lambda: self.scatter.biplot.update())
        self.panel.setParent(centre)
        self.panel.setFixedWidth(290)
        self.panel.raise_()

        self.settings = SettingsDialog(S, self)
        self.settings.appearance_changed.connect(self._on_appearance)
        self.settings.reset_colors.connect(self._reset_colors)
        self.settings.reset_shapes.connect(self._reset_shapes)
        self.settings.reset_boxes.connect(self.reset_boxes)
        self.settings.sample_shape_changed.connect(self._set_sample_shape)
        self.settings.label_mode_changed.connect(self._on_label_mode)
        self.settings.boxes_toggled.connect(self._on_boxes)
        self.settings.export_plot.connect(
            lambda: export_mod.export_plot(self.S, self.scatter, self))
        self.settings.export_inset.connect(
            lambda: export_mod.export_inset(self.S, self.inset, self))

        self.empty = QLabel(
            'No data to explore yet.\n\nConnect particle data and run '
            '① Evaluate K or pick isotopes, then come back to this tab.')
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setObjectName('empty')
        outer.addWidget(self.empty)
        self.empty.setVisible(False)

        self.apply_theme()

    def set_state(self, state):
        """Adopt a new dataset and schedule a run.

        Exact re-deliveries are ignored so an unchanged projection does not
        trigger a second fit.

        Args:
            state (dict | None): The state payload from the controller.
        """
        if state is None:
            return
        seq = state.get('seq')
        if seq is not None and seq == self._state_seq:
            return
        self._state_seq = seq if seq is not None else (self._state_seq or 0) + 1
        self.set_busy(False)
        self._on_state(state)
        if not state.get('empty'):
            self.schedule_run()

    def result_ready(self, res):
        """Adopt the clustering result and draw it.

        Args:
            res (dict | None): The result payload, or an error.
        """
        S = self.S
        if (res and res.get('seq') is not None and self._state_seq is not None
                and res['seq'] != self._state_seq):
            return
        S.running = False
        self.set_busy(False)
        if not res or res.get('error') or res.get('labels') is None:
            S.result = None
            self.note.setText(
                (res or {}).get('error') or 'clustering result unavailable')
        else:
            S.result = res
            self.note.setText(res.get('note') or '')
        self.scatter.fit()
        self._redraw()



    def projecting(self, proj, dims):
        """Show that a projection is being computed.

        Args:
            proj (str): Projection method name.
            dims (int): 2 or 3.
        """
        self.set_busy(True, 'Computing %s %dD projection…' % (proj, dims))


    def _on_state(self, state):
        """Store the dataset, refit the view and update the header.

        Args:
            state (dict): The state payload from the controller.
        """
        S = self.S
        S.data = state
        S.dims = state.get('dims') or 2
        if state.get('projection'):
            S.proj = state['projection']
        if state.get('palette'):
            S.palette = list(state['palette'])
        if state.get('noise_color'):
            THEME['noise'] = state['noise_color']
            THEME.noise_locked = True
        if state.get('cluster_colors'):
            S.ui.colors = {int(k): v
                           for k, v in state['cluster_colors'].items() if v}
        if state.get('theme'):
            THEME.apply(state['theme'])
            self.apply_theme()
        S.param_values = state.get('param_values') or S.param_values
        if state.get('algorithm'):
            S.algo = state['algorithm']
        if state.get('sample_shapes'):
            S.ui.shapes = {k: v for k, v in state['sample_shapes'].items() if v}
        if state.get('overlay_colormap'):
            S.ui.overlay_cmap = state['overlay_colormap']

        S.hidden.clear()
        S.sample_hidden.clear()
        S.sample_focus = None
        S.focus = None
        S.result = None

        self.panel.reflect_config(state)
        if S.schema:
            self.panel.algo.setCurrentText(S.algo)
            self.panel.params.build()
        self.panel.update_biplot_availability()
        self.panel.build_overlay_picker()
        rebuild_overlay(S)
        self.legend.rebuild(None)

        empty = bool(state.get('empty'))
        self.empty.setVisible(empty)
        self.scatter.setVisible(not empty)
        if empty:
            return

        self.scatter.fit()
        v = state.get('var_ratio') or [0, 0]
        proj = state.get('projection') or 'PCA'
        n, n_total = state.get('n'), state.get('n_total')
        nlbl = ('%s of %s particles' % (n, n_total)
                if n_total and n_total > n else '%s particles' % n)
        vtxt = ''
        if proj == 'PCA':
            vtxt = 'var %s · ' % ' / '.join('%d%%' % round(x * 100) for x in v)
        self.panel.set_var_info('%s · %sD · %s%s · %d elements'
                                % (proj, S.dims, vtxt, nlbl,
                                   len(state.get('elements') or [])))

    def set_schema(self, schema):
        """Adopt the algorithm schema and build the panel.

        Args:
            schema (dict): Algorithms, scalings, projections and colormaps.
        """
        self.S.schema = schema
        self.panel.build_from_schema()



    def schedule_run(self):
        """Debounce a clustering run."""
        self._run_timer.start(160)

    def run(self):
        """Ask for a clustering result immediately."""
        self._run_timer.stop()
        self._do_run()


    def _do_run(self):
        """Ask the controller for the clustering result."""
        S = self.S
        if not S.data or S.data.get('empty'):
            return
        S.result = None
        S.running = True
        self.algo_title.setText(S.algo)
        self.set_busy(True, 'Running %s…' % S.algo)
        self.request_run.emit(S.algo, dict(S.params))

    def _redraw(self):
        """Push the current result into every widget."""
        S = self.S
        if not S.data or S.data.get('empty'):
            return
        xy = S.data.get('xy')
        if xy is None or len(xy) == 0:
            return
        P = np.asarray(xy, dtype=float)
        res = S.result
        if res is None or res.get('labels') is None \
                or len(res['labels']) != S.data.get('n'):
            self.scatter.set_frame(P, np.full(len(P), -1))
            return
        extra = res.get('extra') or {}
        som = None
        if extra.get('som_nodes') is not None:
            som = {'nodes': np.asarray(extra['som_nodes'], float),
                   'edges': extra.get('som_edges') or []}
        self.scatter.set_frame(P, np.asarray(res['labels']),
                               res.get('centroids'), som)
        self._update_hud(res)
        self.inset.set_frame(res)
        self.equation.set_frame(res)

    def _update_hud(self, fr):
        """Update the metric chips, the show buttons and the legends.

        The per-frame step description is not repeated here; it appears as the
        detail view's subtitle, and the top bar stays reserved for transient
        status.

        Args:
            fr (dict): The frame currently on screen.
        """
        m = fr.get('metrics') or {}
        self.chip_k.set_value(m.get('n_clusters'))
        self.chip_noise.set_value(m.get('n_noise'))
        self.legend.rebuild(fr.get('labels'))
        self._sync_show_buttons(fr)

    def _sync_show_buttons(self, fr):
        """Offer a button for each hidden box the current frame could fill.

        A box that is switched off but has content to show gets a chip in the
        top bar; clicking it turns the box back on.

        Args:
            fr (dict | None): The frame currently on screen.
        """
        extra = (fr or {}).get('extra') or {}
        self.show_inset_btn.setVisible(
            bool(extra.get('inset')) and not self.S.inset_on)
        self.show_eq_btn.setVisible(
            bool(extra.get('equation')) and not self.S.eq_on)

    def _show_inset(self):
        """Turn the detail view on from its top-bar button."""
        self.S.inset_on = True
        self.settings.sync()
        self._redraw()

    def _show_equation(self):
        """Turn the worked example on from its top-bar button."""
        self.S.eq_on = True
        self.settings.sync()
        self._redraw()

    def set_focus(self, c):
        """Focus a cluster, zooming to it, or clear the focus.

        Args:
            c (int | None): Cluster id, or None to clear.
        """
        S = self.S
        S.focus = None if (c is None or S.focus == c) else c
        self.scatter.focus(S.focus)
        self._redraw()

    def set_sample_focus(self, name):
        """Isolate one sample, fading the others, or clear the isolation.

        Args:
            name (str | None): Sample name, or None to show every sample.
        """
        S = self.S
        S.sample_focus = None if (name is None or S.sample_focus == name) else name
        self._redraw()

    def _toggle_cluster(self, c):
        """Hide or show one cluster, clearing the focus if it was focused.

        Args:
            c (int): Cluster id.
        """
        S = self.S
        if c in S.hidden:
            S.hidden.discard(c)
        else:
            S.hidden.add(c)
            if S.focus == c:
                S.focus = None
                self.scatter.focus(None)
        self._redraw()

    def _toggle_sample(self, name):
        """Hide or show one sample, clearing the focus if it was focused.

        Args:
            name (str): Sample name.
        """
        S = self.S
        if name in S.sample_hidden:
            S.sample_hidden.discard(name)
        else:
            S.sample_hidden.add(name)
            if S.sample_focus == name:
                S.sample_focus = None
        self._redraw()

    def _cycle_sample_shape(self, name):
        """Advance one sample to the next marker shape.

        Args:
            name (str): Sample name.
        """
        cur = self.S.shape_for(name)
        nxt = SHAPES[(SHAPES.index(cur) + 1) % len(SHAPES)] \
            if cur in SHAPES else SHAPES[0]
        self._set_sample_shape(name, nxt)

    def _set_sample_shape(self, name, shape):
        """Assign a marker shape to a sample and announce it for persisting.

        Args:
            name (str): Sample name.
            shape (str): A key from
                :data:`~results.cluster.live_qt.state.SHAPES`.
        """
        self.S.ui.shapes[name] = shape
        self.request_sample_shape.emit(name, shape)
        self.settings.build_shape_rows()
        self._redraw()

    def _reset_shapes(self):
        """Drop every marker-shape override, restoring the default cycle."""
        self.S.ui.shapes = {}
        self.request_reset_shapes.emit()
        self.settings.build_shape_rows()
        self._redraw()

    def _pick_cluster_color(self, c):
        """Open the colour picker for a cluster and persist the choice.

        Args:
            c (int): Cluster id; noise is not recolourable.
        """
        if c < 0:
            return
        S = self.S
        dlg = ColorPicker(S.cluster_color(c), S.palette or PALETTE, self)
        if dlg.exec() != ColorPicker.Accepted:
            return
        if dlg.reverted or dlg.chosen is None:
            S.ui.colors.pop(int(c), None)
            self.request_cluster_color.emit(int(c), '')
        else:
            S.ui.colors[int(c)] = dlg.chosen
            self.request_cluster_color.emit(int(c), dlg.chosen)
        self.settings.build_swatches(self._pick_cluster_color)
        self._redraw()

    def _reset_colors(self):
        """Drop every per-cluster colour override."""
        self.S.ui.colors = {}
        self.request_reset_colors.emit()
        self.settings.build_swatches(self._pick_cluster_color)
        self._redraw()

    def _on_algorithm(self, name):
        """Persist the chosen algorithm and schedule a run.

        Args:
            name (str): Algorithm name.
        """
        self.request_config.emit({'algorithm': name})
        self.schedule_run()

    def _on_param(self, key, value):
        """Persist one algorithm parameter and schedule a run.

        Args:
            key (str): Engine parameter key.
            value: The new value.
        """
        self.request_param.emit(self.S.algo, key, value)
        self.schedule_run()

    def _on_overlay(self, _key):
        """Recompute the colour-by-element overlay and repaint.

        Args:
            _key (str): Unused; the element is read from the state.
        """
        rebuild_overlay(self.S)
        self.legend.rebuild((self.S.current_frame() or {}).get('labels'))
        self._redraw()

    def _on_appearance(self):
        """Apply a font, size or label change everywhere, immediately.

        Several widgets cache derived values — the legend caches cluster names
        built from the element label style, the equation caches its typeset
        pixmaps, the sample glyphs cache the text colour. An appearance change
        has to clear all of them and force a repaint, or the change appears
        only after something else happens to invalidate the cache.
        """
        S = self.S
        self.legend.invalidate()
        self.equation.invalidate()
        self.settings.build_shape_rows()
        self.scatter.axes.update()
        self.scatter.biplot.update()
        self.scatter.centroids.update()
        self._redraw()
        self.legend.rebuild((S.current_frame() or {}).get('labels'))
        self.scatter.viewport().update()

    def _on_label_mode(self, mode):
        """Adopt an element label style and refresh everything showing labels.

        Args:
            mode (str): One of Symbol, Mass + Symbol or Atomic Notation.
        """
        self.request_label_mode.emit(mode)
        self.panel.build_overlay_picker()
        self._on_appearance()

    def _on_boxes(self):
        """Show or hide the legend box after a settings change."""
        self.legend_box.setVisible(self.S.legend_on)
        self._redraw()


    def _on_inset_title(self, title, subtitle):
        """Copy the detail payload's title into its floating box header.

        Args:
            title (str): Detail view title.
            subtitle (str): Detail view subtitle.
        """
        self.inset_box.set_title(title)
        self.inset_box.set_subtitle(subtitle)

    def _toggle_panel(self, shown):
        """Show or hide the parameters panel.

        Args:
            shown (bool): Whether the panel is visible.
        """
        self.panel.setVisible(bool(shown))
        if shown:
            self._place_panel()
            self.panel.raise_()

    def _place_panel(self):
        """Pin the panel down the left edge of the plot area."""
        c = self._centre
        self.panel.setGeometry(0, 0, self.panel.width(), c.height())

    def _place_boxes(self):
        """Lay the floating boxes out along the right edge of the plot.

        Called once the plot has a real size, since the positions are relative
        to it.
        """
        c = self._centre
        w, h = c.width(), c.height()
        if w < 60 or h < 60:
            return
        bw = 236
        x = max(4, w - bw - 8)
        legend_h = min(250, h * 0.42)
        inset_h = min(200, h * 0.30)
        self.legend_box.set_default_geometry(x, 8, bw, legend_h)
        self.inset_box.set_default_geometry(x, 8 + legend_h + 8, bw, inset_h)
        self.equation_box.set_default_geometry(
            x, 8 + legend_h + inset_h + 16, bw, min(210, h * 0.28))
        for b in self._boxes:
            b.clamp()
            b.raise_()
        self._boxes_placed = True

    def reset_boxes(self):
        """Restore every floating box to its default size and position."""
        self._place_boxes()
        for b in self._boxes:
            b.reset()

    def resizeEvent(self, ev):
        """Place the panel and boxes on first show, then keep them in bounds.

        Args:
            ev (QResizeEvent): The resize event.
        """
        super().resizeEvent(ev)
        self._place_panel()
        if not self._boxes_placed:
            self._place_boxes()
        else:
            for b in self._boxes:
                b.clamp()

    def _on_hover(self, i):
        """Show the particle tooltip at the cursor.

        Args:
            i (int): Particle index, or -1 when the cursor is over nothing.
        """
        if i < 0:
            return
        from PySide6.QtGui import QCursor
        from PySide6.QtWidgets import QToolTip
        html = self.scatter.hover_html(i)
        if html:
            QToolTip.showText(QCursor.pos(), html, self.scatter)

    def _context_menu(self, pos):
        """Show the right-click menu on the plot.

        Args:
            pos (QPoint): Cursor position within the scatter widget.
        """
        S = self.S
        m = QMenu(self)
        a_set = m.addAction('Plot settings…')
        a_exp = m.addAction('Export image…')
        m.addSeparator()
        a_det = m.addAction('Show / hide detail view')
        a_eq = m.addAction('Show / hide worked example')
        m.addSeparator()
        a_fit = m.addAction('Reset view')
        a_col = m.addAction('Reset cluster colours')
        act = m.exec(self.scatter.mapToGlobal(pos))
        if act is None:
            return
        if act is a_set:
            self.open_settings()
        elif act is a_exp:
            self.open_settings(2)
        elif act is a_det:
            S.inset_on = not S.inset_on
            self.settings.sync()
            self._redraw()
        elif act is a_eq:
            S.eq_on = not S.eq_on
            self.settings.sync()
            self._redraw()
        elif act is a_fit:
            S.v3.zoom = 1.0
            S.focus = None
            S.sample_focus = None
            S.sample_hidden.clear()
            self.scatter.fit()
            self._redraw()
        elif act is a_col:
            self._reset_colors()

    def open_settings(self, tab=None):
        """Open the settings dialog, optionally on a given tab.

        Args:
            tab (int | None): Tab index to select.
        """
        self.settings.sync()
        self.settings.build_swatches(self._pick_cluster_color)
        self.settings.build_shape_rows()
        self.settings.build_info()
        if tab is not None:
            self.settings.tabs.setCurrentIndex(tab)
        self.settings.show()
        self.settings.raise_()

    def keyPressEvent(self, ev):
        """Clear the focus on Escape.

        Args:
            ev (QKeyEvent): The key event.
        """
        if ev.key() == Qt.Key_Escape:
            if self.S.focus is not None:
                self.set_focus(None)
                return
            if self.S.sample_focus is not None:
                self.set_sample_focus(None)
                return
        super().keyPressEvent(ev)

    def apply_theme(self, theme_vars=None):
        """Adopt a palette change across every widget.

        Every widget that hard-codes a colour has to be restyled here, because
        a Qt stylesheet is a snapshot taken when it was set rather than a live
        reference. Missing one shows up as a panel stuck in the previous mode,
        so the walk below is deliberately blunt: anything exposing
        ``apply_theme`` gets called.

        Args:
            theme_vars (dict | None): Colours to merge before restyling.
        """
        if theme_vars:
            THEME.apply(theme_vars)

        self.setStyleSheet(
            'QWidget{background:%(bg2)s;}'
            'QLabel#algoTitle{color:%(text)s;font-weight:600;}'
            'QLabel#note{color:%(muted)s;font-size:11px;}'
            'QLabel#empty{color:%(muted)s;}'
            'QPushButton#menuBtn{background:%(chip)s;color:%(text)s;'
            'border:1px solid %(stroke2)s;border-radius:6px;'
            'font-size:14px;}'
            'QPushButton#menuBtn:checked{background:%(accent)s;color:#fff;'
            'border:1px solid %(accent)s;}'
            'QPushButton#showBtn{background:%(chip)s;color:%(text)s;'
            'border:1px solid %(stroke)s;border-radius:6px;'
            'padding:4px 10px;font-size:11px;}'
            'QPushButton#showBtn:hover{border:1px solid %(accent)s;}'
            'QProgressBar#busy{background:%(chip)s;border:none;'
            'border-radius:2px;}'
            'QProgressBar#busy::chunk{background:%(accent)s;'
            'border-radius:2px;}'
            % {'bg2': THEME.bg2, 'text': THEME.text, 'muted': THEME.muted,
               'chip': THEME.chip, 'stroke': THEME.stroke,
               'stroke2': THEME.stroke2, 'accent': THEME.accent})

        for w in (self.scatter, self.legend, self.inset, self.equation,
                  self.legend_box, self.inset_box, self.equation_box,
                  self.panel, self.chip_k, self.chip_noise):
            fn = getattr(w, 'apply_theme', None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
        self._redraw()

    def set_status(self, text):
        """Show a short status message in the top bar.

        Args:
            text (str): The message.
        """
        self.note.setText(text)

    def set_busy(self, on, text=''):
        """Show or hide the indeterminate progress bar.

        Projections and the scikit-learn fit run on worker threads with no
        progress to report, so an indeterminate bar says "working" without
        pretending to know how far along it is.

        Args:
            on (bool): Whether work is in progress.
            text (str): Optional message to show beside the bar.
        """
        self.busy.setVisible(bool(on))
        if text:
            self.note.setText(text)
        elif not on:
            self.note.setText('')
