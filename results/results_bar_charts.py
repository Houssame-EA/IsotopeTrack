import os
import sys

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QPushButton,
    QLineEdit, QFrame, QScrollArea, QWidget, QMenu, QSlider,
    QDialogButtonBox, QMessageBox, QListWidget, QListWidgetItem,
    QAbstractItemView, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QCursor, QFont
import pyqtgraph as pg
import numpy as np
import math
from scipy import stats
from scipy.stats import gaussian_kde
import logging
_itk_log = logging.getLogger("IsotopeTrack.results.results_bar_charts")


def _ensure_project_root_on_sys_path():
    """Ensure package-style imports work when this file is run directly.

    Returns:
        None

    Preserved behavior:
        Normal application startup through ``Run.py`` already has the correct
        import context. This helper only adds the parent ``IsotopeTrack``
        source directory when the current module is executed from inside the
        ``results`` directory, which keeps absolute imports like ``results.*``
        and ``widget.*`` resolvable without changing runtime behavior.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


_ensure_project_root_on_sys_path()

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS,
    get_font_config, apply_font_to_pyqtgraph, set_axis_labels,
    apply_plot_item_text_styling, apply_plot_title_style,
    FontSettingsGroup,
    get_sample_color, get_display_name,
    download_pyqtgraph_figure,
    format_element_label, LABEL_MODES, Renderer, HtmlAxisItem,
    SHADE_TYPES, _QT_LINE, _apply_box,
    _add_shaded_region_hist, _add_stat_lines_hist, _add_det_limit_v, _add_det_limit_h,
    format_per_ml as _shared_format_per_ml, apply_sci_y_axis as _shared_apply_sci_y_axis,
)
try:
    from widget.custom_plot_widget import (
        PlotSettingsDialog as _PlotSettingsDialog,
        get_system_font_families as _get_system_font_families,
    )
    _CUSTOM_PLOT_AVAILABLE = True
except Exception:
    _itk_log.exception("Handled exception in <module>")
    _PlotSettingsDialog = None
    _get_system_font_families = lambda: FONT_FAMILIES[:]
    _CUSTOM_PLOT_AVAILABLE = False
from results.utils_sort import (
    sort_elements_by_mass, sort_element_dict_by_mass, element_alphabetical_key,
)


HIST_DATA_TYPES = [
    'Counts', 'Element Mass (fg)', 'Particle Mass (fg)',
    'Element Moles (fmol)', 'Particle Moles (fmol)',
    'Element Diameter (nm)', 'Particle Diameter (nm)',
]

SUMMABLE_DATA_TYPES = [
    'Counts', 'Element Mass (fg)', 'Particle Mass (fg)',
    'Element Moles (fmol)', 'Particle Moles (fmol)',
]

HIST_DATA_KEY_MAP = {
    'Counts': 'elements',
    'Element Mass (fg)': 'element_mass_fg',
    'Particle Mass (fg)': 'particle_mass_fg',
    'Element Moles (fmol)': 'element_moles_fmol',
    'Particle Moles (fmol)': 'particle_moles_fmol',
    'Element Diameter (nm)': 'element_diameter_nm',
    'Particle Diameter (nm)': 'particle_diameter_nm',
}

HIST_LABEL_MAP = {
    'Counts': 'Intensity (counts)',
    'Element Mass (fg)': 'Element Mass (fg)',
    'Particle Mass (fg)': 'Particle Mass (fg)',
    'Element Moles (fmol)': 'Element Moles (fmol)',
    'Particle Moles (fmol)': 'Particle Moles (fmol)',
    'Element Diameter (nm)': 'Element Diameter (nm)',
    'Particle Diameter (nm)': 'Particle Diameter (nm)',
}

HIST_DISPLAY_MODES = [
    'Overlaid (Different Colors)',
    'Side by Side Subplots',
    'Individual Subplots',
]

BAR_DISPLAY_MODES = [
    'Grouped Bars (Side by Side)',
    'By Sample (Element Colors)',
    'Individual Subplots',
    'Side by Side Subplots',
    'Stacked Bars',
]

SORT_OPTIONS = [
    'No Sorting',
    'Ascending',
    'Descending',
    'Alphabetical',
]

CURVE_TYPES = [ 'Log-Normal Fit', 'Normal Fit']

DEFAULT_ELEMENT_COLORS = [
    '#663399', '#2E86AB', '#A23B72', '#F18F01', '#C73E1D',
    '#7209B7', '#F72585', '#4361EE', '#277DA1', '#F8961E',
    '#2563EB', '#DC2626', '#16A34A', '#D97706', '#7C3AED',
]


def _normalize_hist_display_mode(mode: str) -> str:
    """Normalize legacy histogram display-mode aliases to active modes.

    Args:
        mode (str): Display mode from config or UI.

    Returns:
        str: Supported histogram display mode.

    Preserved behavior:
        Existing configs that stored ``Combined with Legend`` are supported by
        aliasing that value to ``Overlaid (Different Colors)``.
    """
    if mode == 'Combined with Legend':
        return 'Overlaid (Different Colors)'
    if mode in HIST_DISPLAY_MODES:
        return mode
    return HIST_DISPLAY_MODES[0]


def _fmt_elem(elem: str, cfg: dict) -> str:
    """Format an element key using the configured label_mode.

    'Symbol'        → strip leading mass number  (e.g. '107Ag' → 'Ag')
    'Mass + Symbol' → keep as-is                 (e.g. '107Ag')
    Args:
        elem (str): The elem.
        cfg (dict): The cfg.
    Returns:
        str: Result of the operation.
    """
    return format_element_label(elem, cfg.get('label_mode', 'Symbol'), Renderer.HTML)


def _meta_te_available(input_data):
    """
    Report whether any sample in the input carries a usable transport rate.

    Args:
        input_data (dict): Node input data dictionary.

    Returns:
        bool: True when at least one concentration metadata entry reports
            te_available, otherwise False.
    """
    meta = (input_data or {}).get('concentration_meta', {})
    if not isinstance(meta, dict):
        return False
    return any(bool(m and m.get('te_available')) for m in meta.values())


def _per_ml_active(cfg, input_data):
    """
    Report whether the particles per millilitre y-axis unit should be used.

    Args:
        cfg (dict): Plot configuration.
        input_data (dict): Node input data dictionary.

    Returns:
        bool: True when the unit is selected and a transport rate is available.
    """
    return cfg.get('y_axis_unit', 'count') == 'per_ml' and _meta_te_available(input_data)


def _pml_factor(input_data, sample_name):
    """
    Return the multiplier that converts a particle count to particles per mL.

    Args:
        input_data (dict): Node input data dictionary.
        sample_name (str): Output sample name to look up.

    Returns:
        float: dilution_factor divided by volume_ml, or 0.0 when unavailable.
    """
    meta = (input_data or {}).get('concentration_meta', {})
    entry = meta.get(sample_name) if isinstance(meta, dict) else None
    if not entry:
        return 0.0
    volume = entry.get('volume_ml', 0.0)
    if not volume or volume <= 0:
        return 0.0
    return entry.get('dilution_factor', 1.0) / volume


def _fmt_bar_value(value, per_ml, cfg=None):
    """
    Format a bar value label as an integer count or ten-to-a-power.

    Args:
        value (float): Bar height in count or particles per mL units.
        per_ml (bool): Whether the value represents a concentration.
        cfg (dict): Optional font config applied to the per mL label.

    Returns:
        str: Formatted label text.
    """
    if per_ml:
        return _shared_format_per_ml(value, Renderer.HTML, cfg)
    return str(int(round(value)))


def _bar_value_textitem(value, per_ml, anchor=(0.5, 1), color='#374151', cfg=None):
    """
    Build a bar value-label TextItem, using HTML so a ten-to-a-power exponent
    is raised by Qt in the configured font when particles-per-mL is active.

    Args:
        value (float): Bar height value.
        per_ml (bool): Whether the value is a concentration.
        anchor (tuple): TextItem anchor.
        color (str): Text colour.
        cfg (dict): Optional font config applied to the label.

    Returns:
        pg.TextItem: Configured text item.
    """
    if per_ml:
        ti = pg.TextItem(anchor=anchor, color=color)
        ti.setHtml(f'<span style="color:{color};">{_fmt_bar_value(value, True, cfg)}</span>')
        return ti
    return pg.TextItem(_fmt_bar_value(value, False), anchor=anchor, color=color)


def _apply_sci_y_axis(plot_item, cfg=None):
    """
    Render the left axis tick labels of a plot as ten-to-a-power.

    Args:
        plot_item (Any): Target pyqtgraph PlotItem.
        cfg (dict): Optional font config applied to the tick labels.

    Returns:
        None
    """
    _shared_apply_sci_y_axis(plot_item, cfg)


class _PlotWidgetAdapter:
    """Wraps a (GraphicsLayoutWidget, PlotItem) pair so that all editor
    dialogs from custom_plot_widget.py treat it like a pg.PlotWidget.

    ``custom_axis_labels`` and ``persistent_dialog_settings`` are stored
    directly on the PlotItem (prefixed with '_') so they survive across
    multiple double-click events even though the adapter is re-created
    each time.
    """

    def __init__(self, glw, plot_item):
        """
        Args:
            glw (Any): The glw.
            plot_item (Any): The plot item.
        """
        self._glw = glw
        self._pi = plot_item
        self.legend = getattr(plot_item, 'legend', None)

    # ── State that must survive re-creation ──────────────────────────

    @property
    def custom_axis_labels(self):
        """
        Returns:
            object: Result of the operation.
        """
        if not hasattr(self._pi, '_custom_axis_labels'):
            self._pi._custom_axis_labels = {}
        return self._pi._custom_axis_labels

    @custom_axis_labels.setter
    def custom_axis_labels(self, val):
        """
        Args:
            val (Any): The val.
        """
        self._pi._custom_axis_labels = val

    @property
    def persistent_dialog_settings(self):
        """
        Returns:
            object: Result of the operation.
        """
        if not hasattr(self._pi, '_persistent_dialog_settings'):
            self._pi._persistent_dialog_settings = {}
        return self._pi._persistent_dialog_settings

    @persistent_dialog_settings.setter
    def persistent_dialog_settings(self, val):
        """
        Args:
            val (Any): The val.
        """
        self._pi._persistent_dialog_settings = val

    # ── PlotWidget interface ─────────────────────────────────────────

    def getPlotItem(self):
        """
        Returns:
            object: Result of the operation.
        """
        return self._pi

    def backgroundBrush(self):
        """
        Returns:
            object: Result of the operation.
        """
        return self._glw.backgroundBrush()

    def setBackground(self, color):
        """
        Args:
            color (Any): Colour value.
        """
        try:
            self._glw.setBackground(color)
        except Exception:
            _itk_log.exception("Handled exception in setBackground")
            pass

    def repaint(self):
        try:
            self._glw.repaint()
        except Exception:
            _itk_log.exception("Handled exception in repaint")
            pass

    def notify_bar_group_color_changed(self, items, color_hex):
        """Forward shared bar-color edits to a plot-specific sync callback.

        Args:
            items (list[pg.BarGraphItem]): Edited bar items from the Plot
                Settings dialog.
            color_hex (str): Selected bar color in ``#RRGGBB`` form.

        Returns:
            None
        """
        callback = getattr(self._pi, '_bar_group_color_sync_callback', None)
        if callable(callback):
            try:
                callback(items, color_hex)
            except Exception:
                _itk_log.exception("Handled exception in notify_bar_group_color_changed")
                pass

    def parent(self):
        """
        Returns:
            object: Result of the operation.
        """
        try:
            return self._glw.parent()
        except Exception:
            _itk_log.exception("Handled exception in parent")
            return None


class EnhancedGraphicsLayoutWidget(pg.GraphicsLayoutWidget):
    """GraphicsLayoutWidget with double-click inline editing.

    Double-clicking on any subplot opens the same editor dialogs that
    EnhancedPlotWidget uses in the main signal window:
      • Title label      → TitleEditorDialog
      • Left axis        → AxisLabelEditorDialog('left')
      • Bottom axis      → AxisLabelEditorDialog('bottom')
      • Legend           → LegendEditorDialog
      • Background area  → BackgroundEditorDialog

    Works correctly across all multi-subplot display modes.
    """

    def __init__(self, parent=None):
        """
        Args:
            parent (Any): Parent widget or object.
        """
        super().__init__(parent=parent)

    # ── Helpers ──────────────────────────────────────────────────────

    def _plot_item_at(self, scene_pos):
        """Return the PlotItem whose bounding rect contains scene_pos.
        Args:
            scene_pos (Any): The scene pos.
        Returns:
            None
        """
        for item in self.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    rect = item.mapRectToScene(item.boundingRect())
                    if rect.contains(scene_pos):
                        return item
                except Exception:
                    _itk_log.exception("Handled exception in _plot_item_at")
                    pass
        return None

    def _adapter_for(self, plot_item):
        """Build an adapter for plot_item, syncing legend from it.
        Args:
            plot_item (Any): The plot item.
        Returns:
            object: Result of the operation.
        """
        adapter = _PlotWidgetAdapter(self, plot_item)
        adapter.legend = getattr(plot_item, 'legend', None)
        return adapter

    def _closest_scatter(self, pi, scene_pos, threshold_px=20):
        """
        Args:
            pi (Any): The pi.
            scene_pos (Any): The scene pos.
            threshold_px (Any): The threshold px.
        Returns:
            object: Result of the operation.
        """
        try:
            vb = pi.getViewBox()
            dp = vb.mapSceneToView(scene_pos)
            mx, my = dp.x(), dp.y()
            vr = vb.viewRange()
            xr = vr[0][1] - vr[0][0]
            yr = vr[1][1] - vr[1][0]
            if xr == 0 or yr == 0:
                return None
            best, best_d = None, float('inf')
            for item in pi.items:
                if not isinstance(item, pg.ScatterPlotItem):
                    continue
                pts = item.data
                if pts is None or len(pts) == 0:
                    continue
                try:
                    xd = np.array([p[0] for p in pts])
                    yd = np.array([p[1] for p in pts])
                except (IndexError, TypeError):
                    _itk_log.exception("Handled exception in _closest_scatter")
                    try:
                        xd = pts['x']; yd = pts['y']
                    except Exception:
                        _itk_log.exception("Handled exception in _closest_scatter")
                        continue
                dx = (xd - mx) / xr; dy = (yd - my) / yr
                dists = np.sqrt(dx**2 + dy**2)
                md = dists[np.argmin(dists)]
                if md * self.width() < threshold_px and md < best_d:
                    best_d = md; best = item
            return best
        except Exception:
            _itk_log.exception("Handled exception in _closest_scatter")
            return None

    def _closest_curve(self, pi, scene_pos, threshold_px=15):
        """
        Args:
            pi (Any): The pi.
            scene_pos (Any): The scene pos.
            threshold_px (Any): The threshold px.
        Returns:
            object: Result of the operation.
        """
        try:
            vb = pi.getViewBox()
            dp = vb.mapSceneToView(scene_pos)
            mx, my = dp.x(), dp.y()
            vr = vb.viewRange()
            xr = vr[0][1] - vr[0][0]
            yr = vr[1][1] - vr[1][0]
            if xr == 0 or yr == 0:
                return None
            best, best_d = None, float('inf')
            for item in pi.listDataItems():
                if isinstance(item, pg.ScatterPlotItem):
                    continue
                if not isinstance(item, (pg.PlotCurveItem, pg.PlotDataItem)):
                    continue
                xd = item.getData()[0] if isinstance(item, pg.PlotDataItem) \
                    else item.xData
                yd = item.getData()[1] if isinstance(item, pg.PlotDataItem) \
                    else item.yData
                if xd is None or yd is None or len(xd) == 0:
                    continue
                dx = (xd - mx) / xr; dy = (yd - my) / yr
                dists = np.sqrt(dx**2 + dy**2)
                md = dists[np.argmin(dists)]
                if md * self.width() < threshold_px and md < best_d:
                    best_d = md; best = item
            return best
        except Exception:
            _itk_log.exception("Handled exception in _closest_curve")
            return None

    def _bar_at(self, pi, scene_pos):
        """Return the BarGraphItem the cursor is inside (data-space test).
        Skips legend swatches (width == 0).
        Args:
            pi (Any): The pi.
            scene_pos (Any): The scene pos.
        Returns:
            None
        """
        try:
            vb = pi.getViewBox()
            dp = vb.mapSceneToView(scene_pos)
            cx, cy = dp.x(), dp.y()
            for item in pi.items:
                if not isinstance(item, pg.BarGraphItem):
                    continue
                w = item.opts.get('width', 0)
                if (not hasattr(w, '__len__') and w == 0):
                    continue
                x_arr = item.opts.get('x', [])
                h_arr = item.opts.get('height', [])
                if not hasattr(x_arr, '__len__'):
                    x_arr = [x_arr]
                if not hasattr(h_arr, '__len__'):
                    h_arr = [h_arr]
                half_w = (w / 2) if not hasattr(w, '__len__') else \
                         (w[0] / 2 if len(w) else 0.35)
                for xi, hi in zip(x_arr, h_arr):
                    y_lo, y_hi = min(0.0, float(hi)), max(0.0, float(hi))
                    if (float(xi) - half_w <= cx <= float(xi) + half_w
                            and y_lo <= cy <= y_hi):
                        return item
        except Exception:
            _itk_log.exception("Handled exception in _bar_at")
            pass
        return None

    # ── Double-click ─────────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event):
        """Route double-click editing to the most specific plot item hit.

        Args:
            event (Any): Qt event object.

        Returns:
            None

        Preserved behavior:
            Existing shared editor dialogs remain available. Individual
            ``PlotItem`` objects may opt into alternate title-editor options
            through ``_title_editor_options`` without affecting other plots.
        """
        if not _CUSTOM_PLOT_AVAILABLE:
            super().mouseDoubleClickEvent(event)
            return
        try:
            from widget.custom_plot_widget import (
                TitleEditorDialog, AxisLabelEditorDialog,
                LegendEditorDialog, BackgroundEditorDialog,
                ScatterEditorDialog, TraceEditorDialog,
            )

            pos = (event.position() if hasattr(event, 'position')
                   else event.pos())
            scene_pos = self.mapToScene(pos.toPoint())

            pi = self._plot_item_at(scene_pos)
            if pi is None:
                event.accept()
                return

            adapter = self._adapter_for(pi)
            dlg_parent = self.parent()

            tl = pi.titleLabel
            if tl and tl.isVisible():
                if tl.mapRectToScene(
                        tl.boundingRect()).contains(scene_pos):
                    title_editor_options = getattr(
                        pi, '_title_editor_options', {})
                    TitleEditorDialog(
                        adapter, dlg_parent, **title_editor_options).exec()
                    event.accept(); return

            la = pi.getAxis('left')
            if la.mapRectToScene(
                    la.boundingRect()).contains(scene_pos):
                AxisLabelEditorDialog(
                    adapter, 'left', dlg_parent).exec()
                event.accept(); return

            ba = pi.getAxis('bottom')
            if ba.mapRectToScene(
                    ba.boundingRect()).contains(scene_pos):
                AxisLabelEditorDialog(
                    adapter, 'bottom', dlg_parent).exec()
                event.accept(); return

            legend = getattr(pi, 'legend', None)
            if legend and legend.isVisible():
                try:
                    if legend.mapRectToScene(
                            legend.boundingRect()).contains(scene_pos):
                        adapter.legend = legend
                        LegendEditorDialog(adapter, dlg_parent).exec()
                        event.accept(); return
                except Exception:
                    _itk_log.exception("Handled exception in mouseDoubleClickEvent")
                    pass

            scat = self._closest_scatter(pi, scene_pos)
            if scat is not None:
                ScatterEditorDialog(scat, adapter, dlg_parent).exec()
                event.accept(); return

            curve = self._closest_curve(pi, scene_pos)
            if curve is not None:
                TraceEditorDialog(curve, adapter, dlg_parent).exec()
                event.accept(); return

            bar_item = self._bar_at(pi, scene_pos)
            if bar_item is not None:
                from PySide6.QtWidgets import QColorDialog
                try:
                    cur = pg.mkBrush(
                        bar_item.opts.get('brush', 'b')).color()
                except Exception:
                    _itk_log.exception("Handled exception in mouseDoubleClickEvent")
                    cur = QColor(100, 120, 220)
                new_c = QColorDialog.getColor(cur, self, "Bar Color")
                if new_c.isValid():
                    alpha = new_c.alpha() if new_c.alpha() < 255 else 215
                    bar_item.setOpts(
                        brush=pg.mkBrush(
                            new_c.red(), new_c.green(),
                            new_c.blue(), alpha),
                        pen=pg.mkPen('w', width=0.5))
                event.accept(); return

            BackgroundEditorDialog(adapter, dlg_parent).exec()
            event.accept()

        except Exception as e:
            _itk_log.exception("Handled exception in mouseDoubleClickEvent")
            print(f"EnhancedGraphicsLayoutWidget double-click error: {e}")
            import traceback; traceback.print_exc()
            super().mouseDoubleClickEvent(event)


class _ClickableLegendSwatch(pg.BarGraphItem):
    """Legend swatch item that forwards click events to a visibility callback.

    The swatch stores a raw histogram element/isotope key and emits that key
    through ``toggle_callback`` when clicked. This keeps histogram visibility
    state keyed by raw identifiers instead of formatted legend labels.
    """

    def __init__(self, *args, raw_key=None, toggle_callback=None, **kwargs):
        """
        Args:
            *args: Forwarded positional args for ``pg.BarGraphItem``.
            raw_key (str | None): Raw isotope/element key represented by this
                legend swatch.
            toggle_callback (Callable[[str], None] | None): Callback invoked on
                left-click to toggle raw-key visibility.
            **kwargs: Forwarded keyword args for ``pg.BarGraphItem``.
        """
        super().__init__(*args, **kwargs)
        self._raw_key = raw_key
        self._toggle_callback = toggle_callback

    def mouseClickEvent(self, ev):
        """Toggle the associated raw-key visibility on left-click.

        Preserved behavior:
            This only affects render-layer element visibility in the parent
            histogram dialog and does not mutate scientific data.
        """
        if ev.button() == Qt.LeftButton and self._raw_key and self._toggle_callback:
            try:
                self._toggle_callback(self._raw_key)
                ev.accept()
                return
            except Exception:
                _itk_log.exception("Handled exception in mouseClickEvent")
                pass
        super().mouseClickEvent(ev)


def _attach_histogram_legend_toggle(legend, raw_key, toggle_callback):
    """Wire histogram legend-row clicks to a raw-key visibility toggle callback.

    Args:
        legend: ``pg.LegendItem`` that already received ``addItem(...)``.
        raw_key (str): Raw isotope/element key represented by the legend row.
        toggle_callback (Callable[[str], None] | None): Parent histogram
            callback that toggles hidden-state and triggers refresh.

    Returns:
        bool: ``True`` when at least one legend row object was hooked.

    Preserved behavior:
        This attaches only Histogram-local click behavior and does not alter
        PyQtGraph globally. Raw keys are used instead of formatted labels so
        label-mode changes cannot break visibility identity.
    """
    if legend is None or not raw_key or toggle_callback is None:
        return False
    try:
        if not getattr(legend, 'items', None):
            return False
        sample_item, label_item = legend.items[-1]
    except Exception:
        _itk_log.exception("Handled exception in _attach_histogram_legend_toggle")
        return False

    def _bind_click(target):
        """Bind one legend-row graphics object to the histogram toggle path."""
        if target is None:
            return False
        try:
            target._hist_raw_key = raw_key
            target._hist_toggle_callback = toggle_callback
            if getattr(target, '_hist_toggle_bound', False):
                return True
            orig_handler = getattr(target, 'mouseClickEvent', None)

            def _wrapped_click(ev, _target=target, _orig=orig_handler):
                if ev.button() == Qt.LeftButton:
                    cb = getattr(_target, '_hist_toggle_callback', None)
                    rk = getattr(_target, '_hist_raw_key', None)
                    if cb is not None and rk:
                        try:
                            cb(rk)
                            ev.accept()
                            return
                        except Exception:
                            _itk_log.exception("Handled exception in _wrapped_click")
                            pass
                if callable(_orig):
                    _orig(ev)

            target.mouseClickEvent = _wrapped_click
            target._hist_toggle_bound = True
            return True
        except Exception:
            _itk_log.exception("Handled exception in _bind_click")
            return False

    hooked = _bind_click(sample_item)
    hooked = _bind_click(label_item) or hooked
    return hooked


def _attach_bar_chart_legend_toggle(legend, raw_key, toggle_callback):
    """Wire one Element Bar Chart legend row to a sample-visibility callback.

    Args:
        legend: ``pg.LegendItem`` that already received ``addItem(...)``.
        raw_key (str): Canonical raw sample key represented by the legend row.
        toggle_callback (Callable[[str], None] | None): Element-Bar-Chart-local
            callback that toggles sample visibility and redraws.

    Returns:
        bool: ``True`` when at least one legend row object was hooked.

    Preserved behavior:
        This attaches only Element-Bar-Chart-local click behavior and keeps
        visibility keyed by raw sample identifiers instead of display labels.
    """
    if legend is None or not raw_key or toggle_callback is None:
        return False
    try:
        if not getattr(legend, 'items', None):
            return False
        sample_item, label_item = legend.items[-1]
    except Exception:
        _itk_log.exception("Handled exception in _attach_bar_chart_legend_toggle")
        return False

    def _bind_click(target):
        """Bind one legend-row graphics object to the sample toggle path."""
        if target is None:
            return False
        try:
            target._bar_raw_key = raw_key
            target._bar_toggle_callback = toggle_callback
            if getattr(target, '_bar_toggle_bound', False):
                return True
            orig_handler = getattr(target, 'mouseClickEvent', None)

            def _wrapped_click(ev, _target=target, _orig=orig_handler):
                if ev.button() == Qt.LeftButton:
                    cb = getattr(_target, '_bar_toggle_callback', None)
                    rk = getattr(_target, '_bar_raw_key', None)
                    if cb is not None and rk:
                        try:
                            cb(rk)
                            ev.accept()
                            return
                        except Exception:
                            _itk_log.exception("Handled exception in _wrapped_click")
                            pass
                if callable(_orig):
                    _orig(ev)

            target.mouseClickEvent = _wrapped_click
            target._bar_toggle_bound = True
            return True
        except Exception:
            _itk_log.exception("Handled exception in _bind_click")
            return False

    hooked = _bind_click(sample_item)
    hooked = _bind_click(label_item) or hooked
    return hooked


def _get_element_color(element, index, cfg):
    """Get color for an element from config or defaults.
    Args:
        element (Any): The element.
        index (Any): Row or item index.
        cfg (Any): The cfg.
    Returns:
        object: Result of the operation.
    """
    colors = cfg.get('element_colors', {})
    if element in colors:
        return colors[element]
    return DEFAULT_ELEMENT_COLORS[index % len(DEFAULT_ELEMENT_COLORS)]


def _get_element_display_name(element, cfg):
    """Get display name for an element (renamed or original).
    Args:
        element (Any): The element.
        cfg (Any): The cfg.
    Returns:
        object: Result of the operation.
    """
    mappings = cfg.get('element_name_mappings', {})
    return mappings.get(element, element)


def _tag_element_color_item(item, raw_element_key, trace_name):
    """Attach canonical raw-element identity metadata to a graphics item.

    Args:
        item (Any): Bar or legend-swatch graphics item to annotate.
        raw_element_key (str): Canonical raw element key such as ``Fe``.
        trace_name (str): Display-only trace label shown to users.

    Returns:
        None
    """
    if item is None or not raw_element_key:
        return
    setattr(item, '_color_identity_role', 'element')
    setattr(item, '_raw_element_key', raw_element_key)
    setattr(item, '_trace_name', trace_name)


def _get_legend_sample_graphics_item(legend_sample_item):
    """Resolve the live swatch graphics item stored in a legend row.

    Args:
        legend_sample_item (Any): Sample-side entry from ``legend.items``.

    Returns:
        Any: Underlying swatch graphics item when exposed by PyQtGraph,
            otherwise ``legend_sample_item`` itself.
    """
    return getattr(legend_sample_item, 'item', legend_sample_item)


def _get_xy_labels(cfg):
    """Build x/y label strings.
    Args:
        cfg (Any): The cfg.
    Returns:
        tuple: Result of the operation.
    """
    dt = cfg.get('data_type_display', 'Counts')
    x_base = HIST_LABEL_MAP.get(dt, 'Value')
    y_base = 'Number of Particles'
    return x_base, y_base


def _is_multi(input_data):
    """
    Args:
        input_data (Any): The input data.
    Returns:
        object: Result of the operation.
    """
    return input_data and input_data.get('type') == 'multiple_sample_data'


def _sample_names(input_data):
    """
    Args:
        input_data (Any): The input data.
    Returns:
        list: Result of the operation.
    """
    if input_data and input_data.get('type') == 'multiple_sample_data':
        return input_data.get('sample_names', [])
    return []


def _can_sum(cfg):
    """Check if current data type supports per-particle summation.
    Args:
        cfg (Any): The cfg.
    Returns:
        object: Result of the operation.
    """
    return cfg.get('data_type_display', 'Counts') in SUMMABLE_DATA_TYPES


def _apply_element_groups(particles, dk, groups):
    """Apply element groups to particle data by summing per particle.

    Args:
        particles: list of particle dicts
        dk: data key (e.g. 'elements', 'element_mass_fg', ...)
        groups: list of group dicts

    Returns:
        dict {display_label: [values]}  where grouped elements are summed
        per particle, ungrouped elements kept as-is.
    """
    if not particles:
        return {}

    elem_to_group = {}
    for grp in groups:
        for el in grp.get('elements', []):
            elem_to_group[el] = grp['name']

    out = {}
    for p in particles:
        d = p.get(dk, {})
        if not d:
            continue

        group_sums = {}
        for el, val in d.items():
            if val <= 0:
                continue
            if dk != 'elements' and np.isnan(val):
                continue

            grp_name = elem_to_group.get(el)
            if grp_name:
                group_sums[grp_name] = group_sums.get(grp_name, 0.0) + val
            else:
                out.setdefault(el, []).append(val)

        for grp_name, total in group_sums.items():
            if total > 0:
                out.setdefault(grp_name, []).append(total)

    return out


def _apply_element_groups_multi(particles, sample_names, dk, groups):
    """Apply element groups to multi-sample particle data.

    Returns:
        dict {sample_name: {display_label: [values]}}
    Args:
        particles (Any): The particles.
        sample_names (Any): The sample names.
        dk (Any): The dk.
        groups (Any): The groups.
    """
    if not particles:
        return {}

    elem_to_group = {}
    for grp in groups:
        for el in grp.get('elements', []):
            elem_to_group[el] = grp['name']

    result = {sn: {} for sn in sample_names}

    for p in particles:
        src = p.get('source_sample')
        if src not in result:
            continue
        d = p.get(dk, {})
        if not d:
            continue

        group_sums = {}
        for el, val in d.items():
            if val <= 0:
                continue
            if dk != 'elements' and np.isnan(val):
                continue

            grp_name = elem_to_group.get(el)
            if grp_name:
                group_sums[grp_name] = group_sums.get(grp_name, 0.0) + val
            else:
                result[src].setdefault(el, []).append(val)

        for grp_name, total in group_sums.items():
            if total > 0:
                result[src].setdefault(grp_name, []).append(total)

    return {k: v for k, v in result.items() if v}


class ElementGroupEditor(QGroupBox):
    """Widget for defining element groups (sum per particle)."""

    def __init__(self, groups, available_elements, parent=None):
        """
        Args:
            groups (Any): The groups.
            available_elements (Any): The available elements.
            parent (Any): Parent widget or object.
        """
        super().__init__("Element Groups (Sum per Particle)", parent)
        self._groups = [dict(g) for g in groups]
        self._available = available_elements or []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "Group elements to SUM their values within each particle.\n"
            "e.g. group Fe + Si + Ti → each particle's Fe+Si+Ti mass "
            "is summed into one value.\n"
            "Only applies to Counts, Mass, Moles (not Diameter).")
        info.setStyleSheet("color: #6B7280; font-size: 10px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        self._group_list = QListWidget()
        self._group_list.setMaximumHeight(120)
        self._group_list.currentRowChanged.connect(self._on_group_selected)
        layout.addWidget(self._group_list)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("+ Add Group")
        self._add_btn.clicked.connect(self._add_group)
        btn_row.addWidget(self._add_btn)
        self._remove_btn = QPushButton("− Remove")
        self._remove_btn.clicked.connect(self._remove_group)
        self._remove_btn.setEnabled(False)
        btn_row.addWidget(self._remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._detail_frame = QFrame()
        self._detail_frame.setFrameShape(QFrame.StyledPanel)
        dl = QVBoxLayout(self._detail_frame)
        dl.setContentsMargins(6, 6, 6, 6)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Group Name:"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. HgSe, Total Metal, ...")
        self._name_edit.textChanged.connect(self._on_name_changed)
        name_row.addWidget(self._name_edit)
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(30, 22)
        self._color_btn.clicked.connect(self._pick_color)
        name_row.addWidget(self._color_btn)
        dl.addLayout(name_row)

        dl.addWidget(QLabel("Select elements to include in this group:"))
        self._elem_list = QListWidget()
        self._elem_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self._elem_list.setMaximumHeight(150)
        self._elem_list.itemSelectionChanged.connect(
            self._on_elements_changed)
        dl.addWidget(self._elem_list)

        layout.addWidget(self._detail_frame)
        self._detail_frame.setVisible(False)

        self._refresh_group_list()

    def _refresh_group_list(self):
        self._group_list.clear()
        for g in self._groups:
            name = g.get('name', 'Unnamed')
            elems = ', '.join(g.get('elements', []))
            self._group_list.addItem(f"{name}  [{elems}]")

    def _on_group_selected(self, row):
        """
        Args:
            row (Any): Row index.
        """
        has = 0 <= row < len(self._groups)
        self._remove_btn.setEnabled(has)
        self._detail_frame.setVisible(has)
        if has:
            g = self._groups[row]
            self._name_edit.blockSignals(True)
            self._name_edit.setText(g.get('name', ''))
            self._name_edit.blockSignals(False)

            c = g.get('color',
                       DEFAULT_ELEMENT_COLORS[
                           row % len(DEFAULT_ELEMENT_COLORS)])
            self._color_btn.setStyleSheet(
                f"background-color: {c}; border: 1px solid black;")

            self._elem_list.blockSignals(True)
            self._elem_list.clear()
            selected_elems = set(g.get('elements', []))

            used_elsewhere = set()
            for i, og in enumerate(self._groups):
                if i != row:
                    used_elsewhere.update(og.get('elements', []))

            for el in self._available:
                item = QListWidgetItem(el)
                if el in used_elsewhere:
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    item.setToolTip(f"{el} already in another group")
                self._elem_list.addItem(item)
                if el in selected_elems:
                    item.setSelected(True)
            self._elem_list.blockSignals(False)

    def _add_group(self):
        idx = len(self._groups)
        self._groups.append({
            'name': f'Group {idx + 1}',
            'elements': [],
            'color': DEFAULT_ELEMENT_COLORS[
                idx % len(DEFAULT_ELEMENT_COLORS)],
        })
        self._refresh_group_list()
        self._group_list.setCurrentRow(len(self._groups) - 1)

    def _remove_group(self):
        row = self._group_list.currentRow()
        if 0 <= row < len(self._groups):
            self._groups.pop(row)
            self._refresh_group_list()
            if self._groups:
                self._group_list.setCurrentRow(
                    min(row, len(self._groups) - 1))

    def _on_name_changed(self, text):
        """
        Args:
            text (Any): Text string.
        """
        row = self._group_list.currentRow()
        if 0 <= row < len(self._groups):
            self._groups[row]['name'] = text.strip() or f'Group {row + 1}'
            self._refresh_group_list()
            self._group_list.setCurrentRow(row)

    def _on_elements_changed(self):
        row = self._group_list.currentRow()
        if 0 <= row < len(self._groups):
            selected = []
            for i in range(self._elem_list.count()):
                item = self._elem_list.item(i)
                if item.isSelected() and (item.flags() & Qt.ItemIsEnabled):
                    selected.append(item.text())
            self._groups[row]['elements'] = selected
            self._refresh_group_list()
            self._group_list.setCurrentRow(row)

    def _pick_color(self):
        from PySide6.QtWidgets import QColorDialog
        row = self._group_list.currentRow()
        if 0 <= row < len(self._groups):
            cur = QColor(self._groups[row].get('color', '#663399'))
            c = QColorDialog.getColor(cur, self, "Group Color")
            if c.isValid():
                self._groups[row]['color'] = c.name()
                self._color_btn.setStyleSheet(
                    f"background-color: {c.name()}; "
                    f"border: 1px solid black;")

    def collect(self):
        """Return list of valid groups (with ≥1 element and a name).
        Returns:
            list: Result of the operation.
        """
        return [g for g in self._groups
                if g.get('elements') and g.get('name')]


class HistogramSettingsDialog(QDialog):
    """Full settings dialog for histogram node."""

    def __init__(self, config, is_multi, sample_names, parent=None,
                 available_elements=None, lock_data_type=False,
                 data_type_lock_message="", te_available=False):
        """
        Args:
            config (Any): Configuration dictionary.
            is_multi (Any): The is multi.
            sample_names (Any): The sample names.
            parent (Any): Parent widget or object.
            available_elements (Any): The available elements.
            lock_data_type (bool): When True, keep data-type selection
                read-only in this dialog.
            data_type_lock_message (str): Optional explanatory text shown near
                the data-type control when locked.

        Preserved behavior:
            Parent histogram can still fully change data type. The lock is used
            by decomposition child views that redraw from already-extracted
            snapshots and therefore must not relabel values as another type.
        """
        super().__init__(parent)
        self.setWindowTitle("Histogram Settings")
        self.setMinimumWidth(520)
        self._cfg = dict(config)
        self._multi = is_multi
        self._samples = sample_names
        self._available_elements = available_elements or []
        self._lock_data_type = bool(lock_data_type)
        self._data_type_lock_message = data_type_lock_message or ""
        self._te_available = bool(te_available)
        self._build_ui()

    def _build_ui(self):
        """
        Returns:
            tuple: Result of the operation.
        """
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        if self._multi:
            g = QGroupBox("Multiple Sample Display")
            fl = QFormLayout(g)
            self.display_mode = QComboBox()
            self.display_mode.addItems(HIST_DISPLAY_MODES)
            self.display_mode.setCurrentText(
                _normalize_hist_display_mode(
                    self._cfg.get('display_mode', HIST_DISPLAY_MODES[0])))
            fl.addRow("Display Mode:", self.display_mode)
            layout.addWidget(g)

        g = QGroupBox("Data Type")
        fl = QFormLayout(g)
        self.data_type = QComboBox()
        self.data_type.addItems(HIST_DATA_TYPES)
        self.data_type.setCurrentText(
            self._cfg.get('data_type_display', 'Counts'))
        fl.addRow("Data:", self.data_type)
        if self._lock_data_type:
            self.data_type.setEnabled(False)
            self.data_type.setToolTip(self._data_type_lock_message)
            self.data_type.setStatusTip(self._data_type_lock_message)
            if self._data_type_lock_message:
                lock_note = QLabel(self._data_type_lock_message)
                lock_note.setWordWrap(True)
                lock_note.setStyleSheet("color: #6B7280; font-size: 10px;")
                fl.addRow("", lock_note)
        self.y_axis_unit = QComboBox()
        self.y_axis_unit.addItem("Particle", "count")
        self.y_axis_unit.addItem("Particle per mL", "per_ml")
        cur_unit = self._cfg.get('y_axis_unit', 'count')
        self.y_axis_unit.setCurrentIndex(1 if cur_unit == 'per_ml' else 0)
        fl.addRow("Y Axis:", self.y_axis_unit)
        if not self._te_available:
            idx = self.y_axis_unit.findData('per_ml')
            model = self.y_axis_unit.model()
            item = model.item(idx)
            if item is not None:
                item.setEnabled(False)
            if cur_unit == 'per_ml':
                self.y_axis_unit.setCurrentIndex(0)
            note = QLabel("Particle per mL requires Transport Rate calibration")
            note.setWordWrap(True)
            note.setStyleSheet("color: #6B7280; font-size: 10px;")
            fl.addRow("", note)
        layout.addWidget(g)

        self._group_editor = ElementGroupEditor(
            self._cfg.get('element_groups', []),
            self._available_elements)
        layout.addWidget(self._group_editor)

        g = QGroupBox("Element Display Names")
        el_vl = QVBoxLayout(g)
        el_vl.addWidget(QLabel(
            "Rename individual elements in legend and stats:"))
        self._elem_name_edits = {}

        existing_names = self._cfg.get('element_name_mappings', {})
        all_elements = list(self._available_elements)

        for el in all_elements:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(el)
            lbl.setFixedWidth(80)
            row.addWidget(lbl)
            ne = QLineEdit(existing_names.get(el, el))
            ne.setFixedWidth(180)
            ne.setPlaceholderText(el)
            row.addWidget(ne)
            self._elem_name_edits[el] = ne
            rst = QPushButton("\u21ba")
            rst.setFixedSize(22, 22)
            rst.setToolTip(f"Reset to: {el}")
            rst.clicked.connect(
                lambda _, e=el: self._elem_name_edits[e].setText(e))
            row.addWidget(rst)
            row.addStretch()
            w_row = QWidget()
            w_row.setLayout(row)
            el_vl.addWidget(w_row)

        if not all_elements:
            el_vl.addWidget(QLabel("(No elements detected yet)"))
        layout.addWidget(g)

        g = QGroupBox("Curve && Median")
        fl = QFormLayout(g)
        self.show_curve = QCheckBox()
        self.show_curve.setChecked(self._cfg.get('show_curve', True))
        fl.addRow("Show Density Curve:", self.show_curve)
        self.curve_type = QComboBox()
        self.curve_type.addItems(CURVE_TYPES)
        self.curve_type.setCurrentText(
            self._cfg.get('curve_type', 'Kernel Density'))
        fl.addRow("Curve Type:", self.curve_type)
        self.show_median = QCheckBox()
        self.show_median.setChecked(self._cfg.get('show_median', True))
        fl.addRow("Show Median Line (legacy):", self.show_median)
        self._curve_color = QColor(self._cfg.get('curve_color', '#2C3E50'))
        self.curve_color_btn = QPushButton()
        self.curve_color_btn.setFixedSize(60, 25)
        self.curve_color_btn.setStyleSheet(
            f"background-color: {self._curve_color.name()}; "
            f"border: 1px solid black;")
        self.curve_color_btn.clicked.connect(self._pick_curve_color)
        fl.addRow("Curve Color:", self.curve_color_btn)
        layout.addWidget(g)

        g = QGroupBox("Statistical Overlays")
        fl = QFormLayout(g)

        def _color_row(cfg_key, label, default_color):
            """Return (row_widget, color_holder, style_combo, width_spin).
            Args:
                cfg_key (Any): The cfg key.
                label (Any): Label text.
                default_color (Any): The default color.
            Returns:
                tuple: Result of the operation.
            """
            rw = QWidget(); rh = QHBoxLayout(rw); rh.setContentsMargins(0,0,0,0)
            holder = [self._cfg.get(cfg_key, default_color)]
            btn = QPushButton(); btn.setFixedSize(26, 22)
            btn.setStyleSheet(f"background:{holder[0]};")
            def _pick(h=holder, b=btn):
                """
                Args:
                    h (Any): The h.
                    b (Any): The b.
                """
                from PySide6.QtWidgets import QColorDialog as _CD
                c = _CD.getColor(QColor(h[0]), self)
                if c.isValid():
                    h[0] = c.name(); b.setStyleSheet(f"background:{h[0]};")
            btn.clicked.connect(_pick)
            rh.addWidget(btn); rh.addStretch()
            return rw, holder

        self.show_median_line = QCheckBox()
        self.show_median_line.setChecked(self._cfg.get('show_median_line', False))
        med_w, self._med_color = _color_row('median_line_color', 'med', '#0F6E56')
        med_row = QHBoxLayout()
        med_row.addWidget(self.show_median_line); med_row.addWidget(med_w)
        med_container = QWidget(); med_container.setLayout(med_row)
        fl.addRow("Median Line:", med_container)

        self.show_mean_line = QCheckBox()
        self.show_mean_line.setChecked(self._cfg.get('show_mean_line', False))
        mean_w, self._mean_color = _color_row('mean_line_color', 'mean', '#B45309')
        mean_row = QHBoxLayout()
        mean_row.addWidget(self.show_mean_line); mean_row.addWidget(mean_w)
        mean_container = QWidget(); mean_container.setLayout(mean_row)
        fl.addRow("Mean Line:", mean_container)

        self.show_mode_marker = QCheckBox()
        self.show_mode_marker.setChecked(self._cfg.get('show_mode_marker', False))
        mode_w, self._mode_color = _color_row('mode_line_color', 'mode', '#7C3AED')
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.show_mode_marker); mode_row.addWidget(mode_w)
        mode_container = QWidget(); mode_container.setLayout(mode_row)
        fl.addRow("Mode Marker:", mode_container)

        self.shade_combo = QComboBox()
        self.shade_combo.addItems(SHADE_TYPES)
        self.shade_combo.setCurrentText(self._cfg.get('shade_type', 'None'))
        fl.addRow("Shaded Region:", self.shade_combo)

        shade_row_w = QWidget(); shade_rh = QHBoxLayout(shade_row_w)
        shade_rh.setContentsMargins(0,0,0,0)
        self._shade_color_val = self._cfg.get('shade_color', '#534AB7')
        self._shade_clr_btn = QPushButton(); self._shade_clr_btn.setFixedSize(26, 22)
        self._shade_clr_btn.setStyleSheet(f"background:{self._shade_color_val};")
        self._shade_clr_btn.clicked.connect(self._pick_shade_color_hist)
        self._shade_alpha_spin = QDoubleSpinBox()
        self._shade_alpha_spin.setRange(0.01, 1.0); self._shade_alpha_spin.setDecimals(2)
        self._shade_alpha_spin.setValue(self._cfg.get('shade_alpha', 0.18))
        shade_rh.addWidget(self._shade_clr_btn)
        shade_rh.addWidget(QLabel("alpha:")); shade_rh.addWidget(self._shade_alpha_spin)
        shade_rh.addStretch()
        fl.addRow("Shade Color / alpha:", shade_row_w)

        self.show_det_cb = QCheckBox()
        self.show_det_cb.setChecked(self._cfg.get('show_det_limit', False))
        fl.addRow("Detection Limit Line:", self.show_det_cb)
        self.det_val_spin = QDoubleSpinBox()
        self.det_val_spin.setRange(0.0, 999999999); self.det_val_spin.setDecimals(4)
        self.det_val_spin.setValue(self._cfg.get('det_limit_value', 1.0))
        fl.addRow("DL Value:", self.det_val_spin)
        self.det_label_edit = QLineEdit(self._cfg.get('det_limit_label', ''))
        self.det_label_edit.setPlaceholderText("Auto  (e.g.  DL: 1.0)")
        fl.addRow("DL Label:", self.det_label_edit)
        self.show_box_cb = QCheckBox()
        self.show_box_cb.setChecked(self._cfg.get('show_box', True))
        fl.addRow("Figure Box (frame):", self.show_box_cb)
        layout.addWidget(g)

        g = QGroupBox("Plot Options")
        fl = QFormLayout(g)
        self.bins = QSpinBox()
        self.bins.setRange(5, 200)
        self.bins.setValue(self._cfg.get('bins', 20))
        fl.addRow("Bins:", self.bins)
        self.alpha = QSlider(Qt.Horizontal)
        self.alpha.setRange(10, 100)
        self.alpha.setValue(int(self._cfg.get('alpha', 0.7) * 100))
        fl.addRow("Transparency:", self.alpha)
        self.log_x = QCheckBox()
        self.log_x.setChecked(self._cfg.get('log_x', False))
        fl.addRow("Log X-axis:", self.log_x)
        self.log_y = QCheckBox()
        self.log_y.setChecked(self._cfg.get('log_y', False))
        fl.addRow("Log Y-axis:", self.log_y)
        self.show_stats = QCheckBox()
        self.show_stats.setChecked(self._cfg.get('show_stats', True))
        fl.addRow("Show Statistics:", self.show_stats)
        self.label_mode = QComboBox()
        self.label_mode.addItems(LABEL_MODES)
        self.label_mode.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
        fl.addRow("Isotope Label:", self.label_mode)
        layout.addWidget(g)

        g = QGroupBox("Axis Limits")
        fl = QFormLayout(g)
        self.auto_x = QCheckBox("Auto X")
        self.auto_x.setChecked(self._cfg.get('auto_x', True))
        fl.addRow(self.auto_x)
        w = QWidget()
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        self.x_min = QDoubleSpinBox()
        self.x_min.setRange(-999999, 999999)
        self.x_min.setValue(self._cfg.get('x_min', 0))
        self.x_max = QDoubleSpinBox()
        self.x_max.setRange(-999999, 999999)
        self.x_max.setValue(self._cfg.get('x_max', 1000))
        hl.addWidget(self.x_min)
        hl.addWidget(QLabel("to"))
        hl.addWidget(self.x_max)
        fl.addRow("X Range:", w)
        self.auto_y = QCheckBox("Auto Y")
        self.auto_y.setChecked(self._cfg.get('auto_y', True))
        fl.addRow(self.auto_y)
        w2 = QWidget()
        hl2 = QHBoxLayout(w2)
        hl2.setContentsMargins(0, 0, 0, 0)
        self.y_min = QDoubleSpinBox()
        self.y_min.setRange(0, 999999)
        self.y_min.setValue(self._cfg.get('y_min', 0))
        self.y_max = QDoubleSpinBox()
        self.y_max.setRange(0, 999999)
        self.y_max.setValue(self._cfg.get('y_max', 100))
        hl2.addWidget(self.y_min)
        hl2.addWidget(QLabel("to"))
        hl2.addWidget(self.y_max)
        fl.addRow("Y Range:", w2)
        layout.addWidget(g)

        if self._multi:
            g = QGroupBox("Sample Names")
            vl = QVBoxLayout(g)
            self._name_edits = {}
            mappings = self._cfg.get('sample_name_mappings', {})
            for sn in self._samples:
                row = QHBoxLayout()
                ne = QLineEdit(mappings.get(sn, sn))
                ne.setFixedWidth(220)
                row.addWidget(QLabel(sn[:20]))
                row.addWidget(ne)
                self._name_edits[sn] = ne
                rst = QPushButton("\u21ba")
                rst.setFixedSize(22, 22)
                rst.clicked.connect(
                    lambda _, o=sn: self._name_edits[o].setText(o))
                row.addWidget(rst)
                row.addStretch()
                w3 = QWidget()
                w3.setLayout(row)
                vl.addWidget(w3)
            layout.addWidget(g)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def _pick_curve_color(self):
        from PySide6.QtWidgets import QColorDialog
        c = QColorDialog.getColor(self._curve_color, self, "Curve Color")
        if c.isValid():
            self._curve_color = c
            self.curve_color_btn.setStyleSheet(
                f"background-color: {c.name()}; border: 1px solid black;")

    def _pick_shade_color_hist(self):
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor
        c = QColorDialog.getColor(QColor(self._shade_color_val), self)
        if c.isValid():
            self._shade_color_val = c.name()
            self._shade_clr_btn.setStyleSheet(f"background:{self._shade_color_val};")

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.

        Preserved behavior:
            When data type is locked (decomposition child safety mode), this
            method preserves inherited ``data_type_display`` and collects other
            quantity/format controls normally.
        """
        out = dict(self._cfg)
        if self._lock_data_type:
            out['data_type_display'] = self._cfg.get('data_type_display', 'Counts')
        else:
            out['data_type_display'] = self.data_type.currentText()
        out['element_groups'] = self._group_editor.collect()
        out['y_axis_unit'] = self.y_axis_unit.currentData()
        out['show_curve'] = self.show_curve.isChecked()
        out['curve_type'] = self.curve_type.currentText()
        out['show_median'] = self.show_median.isChecked()
        out['curve_color'] = self._curve_color.name()
        out['show_median_line'] = self.show_median_line.isChecked()
        out['median_line_color'] = self._med_color[0]
        out['show_mean_line'] = self.show_mean_line.isChecked()
        out['mean_line_color'] = self._mean_color[0]
        out['show_mode_marker'] = self.show_mode_marker.isChecked()
        out['mode_line_color'] = self._mode_color[0]
        out['shade_type'] = self.shade_combo.currentText()
        out['shade_color'] = self._shade_color_val
        out['shade_alpha'] = self._shade_alpha_spin.value()
        out['show_det_limit'] = self.show_det_cb.isChecked()
        out['det_limit_value'] = self.det_val_spin.value()
        out['det_limit_label'] = self.det_label_edit.text().strip()
        out['show_box'] = self.show_box_cb.isChecked()
        out['bins'] = self.bins.value()
        out['alpha'] = self.alpha.value() / 100.0
        out['log_x'] = self.log_x.isChecked()
        out['log_y'] = self.log_y.isChecked()
        out['show_stats'] = self.show_stats.isChecked()
        out['auto_x'] = self.auto_x.isChecked()
        out['x_min'] = self.x_min.value()
        out['x_max'] = self.x_max.value()
        out['auto_y'] = self.auto_y.isChecked()
        out['y_min'] = self.y_min.value()
        out['y_max'] = self.y_max.value()
        out['element_name_mappings'] = {
            e: ne.text().strip() or e
            for e, ne in self._elem_name_edits.items()}
        if self._multi:
            out['display_mode'] = _normalize_hist_display_mode(
                self.display_mode.currentText())
            out['sample_name_mappings'] = {
                sn: ne.text() for sn, ne in self._name_edits.items()}
        out['label_mode'] = self.label_mode.currentText()
        return out


class HistogramFormatSettingsDialog(QDialog):
    """Global visual-format settings dialog for Histogram plots.

    This dialog is intentionally config-driven and plot-global: it collects
    only presentation settings (fonts, labels, visual toggles, and element
    colors) and relies on Histogram redraw to apply those settings uniformly
    across all subplot PlotItems.
    """

    def __init__(self, config, is_multi, sample_names, parent=None,
                 available_elements=None):
        """
        Initialize the histogram format-only settings dialog.

        Args:
            config (dict): Current histogram config snapshot.
            is_multi (bool): Whether current histogram data is multi-sample.
            sample_names (list[str]): Source sample names for display-name edits.
            parent (QWidget | None): Parent dialog.
            available_elements (list[str] | None): Element keys available for
                global element-color and display-name edits.

        Preserved behavior:
            Scientific quantity controls (bins/data type/curve type/shade type/
            element groups/log axes/display mode) are intentionally excluded and
            remain in the quantities configuration workflow.
        """
        super().__init__(parent)
        self.setWindowTitle("Histogram plot format settings")
        self.setMinimumWidth(520)
        self._cfg = dict(config)
        self._multi = is_multi
        self._samples = sample_names
        self._available_elements = available_elements or []
        self._font_color = QColor(self._cfg.get('font_color', '#000000'))
        self._elem_color_btns = {}
        self._build_ui()

    def _build_ui(self):
        """Build visual-only controls used by the histogram format route."""
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        g = QGroupBox("Font && Text")
        fl = QFormLayout(g)
        self.font_family = QComboBox()
        self.font_family.addItems(_get_system_font_families())
        self.font_family.setCurrentText(self._cfg.get('font_family', 'Times New Roman'))
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 72)
        self.font_size.setValue(self._cfg.get('font_size', 18))
        self.font_bold = QCheckBox()
        self.font_bold.setChecked(self._cfg.get('font_bold', False))
        self.font_italic = QCheckBox()
        self.font_italic.setChecked(self._cfg.get('font_italic', False))
        self.font_color_btn = QPushButton()
        self.font_color_btn.setFixedSize(70, 24)
        self._refresh_font_color_btn()
        self.font_color_btn.clicked.connect(self._pick_font_color)
        self.label_mode = QComboBox()
        self.label_mode.addItems(LABEL_MODES)
        self.label_mode.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
        fl.addRow("Font Family:", self.font_family)
        fl.addRow("Font Size:", self.font_size)
        fl.addRow("Bold:", self.font_bold)
        fl.addRow("Italic:", self.font_italic)
        fl.addRow("Font Color:", self.font_color_btn)
        fl.addRow("Isotope Label:", self.label_mode)
        layout.addWidget(g)

        g = QGroupBox("Visual Toggles")
        fl = QFormLayout(g)
        self.show_curve = QCheckBox()
        self.show_curve.setChecked(self._cfg.get('show_curve', True))
        self.show_stats = QCheckBox()
        self.show_stats.setChecked(self._cfg.get('show_stats', True))
        self.show_box = QCheckBox()
        self.show_box.setChecked(self._cfg.get('show_box', True))
        self.show_median_line = QCheckBox()
        self.show_median_line.setChecked(self._cfg.get('show_median_line', False))
        self.show_mean_line = QCheckBox()
        self.show_mean_line.setChecked(self._cfg.get('show_mean_line', False))
        self.show_mode_marker = QCheckBox()
        self.show_mode_marker.setChecked(self._cfg.get('show_mode_marker', False))
        self.show_det_limit = QCheckBox()
        self.show_det_limit.setChecked(self._cfg.get('show_det_limit', False))
        fl.addRow("Show Density Curve:", self.show_curve)
        fl.addRow("Show Statistics:", self.show_stats)
        fl.addRow("Figure Box (frame):", self.show_box)
        fl.addRow("Median Line:", self.show_median_line)
        fl.addRow("Mean Line:", self.show_mean_line)
        fl.addRow("Mode Marker:", self.show_mode_marker)
        fl.addRow("Detection Limit Line:", self.show_det_limit)
        layout.addWidget(g)

        g = QGroupBox("Grid")
        fl = QFormLayout(g)
        self.show_x_grid = QCheckBox()
        self.show_x_grid.setChecked(self._cfg.get('show_x_grid', False))
        self.show_y_grid = QCheckBox()
        self.show_y_grid.setChecked(self._cfg.get('show_y_grid', False))
        self.grid_alpha = QDoubleSpinBox()
        self.grid_alpha.setRange(0.05, 1.0)
        self.grid_alpha.setDecimals(2)
        self.grid_alpha.setSingleStep(0.05)
        self.grid_alpha.setValue(float(self._cfg.get('grid_alpha', 0.2)))
        fl.addRow("Show X Grid:", self.show_x_grid)
        fl.addRow("Show Y Grid:", self.show_y_grid)
        fl.addRow("Grid Alpha:", self.grid_alpha)
        layout.addWidget(g)

        g = QGroupBox("Element Colors")
        vl = QVBoxLayout(g)
        existing_colors = self._cfg.get('element_colors', {})
        for i, el in enumerate(self._available_elements):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(QLabel(el))
            btn = QPushButton()
            btn.setFixedSize(70, 24)
            col = existing_colors.get(
                el, DEFAULT_ELEMENT_COLORS[i % len(DEFAULT_ELEMENT_COLORS)])
            btn._color = QColor(col)
            btn.setStyleSheet(
                f"background-color: {btn._color.name()}; border: 1px solid black;")
            btn.clicked.connect(lambda _, e=el: self._pick_element_color(e))
            row.addWidget(btn)
            row.addStretch()
            vl.addLayout(row)
            self._elem_color_btns[el] = btn
        if not self._available_elements:
            vl.addWidget(QLabel("(No elements detected yet)"))
        layout.addWidget(g)

        g = QGroupBox("Element Display Names")
        el_vl = QVBoxLayout(g)
        self._elem_name_edits = {}
        existing_names = self._cfg.get('element_name_mappings', {})
        for el in self._available_elements:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(el)
            lbl.setFixedWidth(90)
            row.addWidget(lbl)
            ne = QLineEdit(existing_names.get(el, el))
            ne.setFixedWidth(180)
            ne.setPlaceholderText(el)
            row.addWidget(ne)
            self._elem_name_edits[el] = ne
            rst = QPushButton("\u21ba")
            rst.setFixedSize(22, 22)
            rst.clicked.connect(lambda _, e=el: self._elem_name_edits[e].setText(e))
            row.addWidget(rst)
            row.addStretch()
            el_vl.addLayout(row)
        if not self._available_elements:
            el_vl.addWidget(QLabel("(No elements detected yet)"))
        layout.addWidget(g)

        if self._multi:
            g = QGroupBox("Sample Names")
            vl = QVBoxLayout(g)
            self._name_edits = {}
            mappings = self._cfg.get('sample_name_mappings', {})
            for sn in self._samples:
                row = QHBoxLayout()
                ne = QLineEdit(mappings.get(sn, sn))
                ne.setFixedWidth(220)
                row.addWidget(QLabel(sn[:20]))
                row.addWidget(ne)
                self._name_edits[sn] = ne
                rst = QPushButton("\u21ba")
                rst.setFixedSize(22, 22)
                rst.clicked.connect(lambda _, o=sn: self._name_edits[o].setText(o))
                row.addWidget(rst)
                row.addStretch()
                vl.addLayout(row)
            layout.addWidget(g)
        else:
            self._name_edits = None

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def _refresh_font_color_btn(self):
        """Refresh the font-color swatch preview."""
        self.font_color_btn.setStyleSheet(
            f"background-color: {self._font_color.name()}; border: 1px solid black;")

    def _pick_font_color(self):
        """Select and store a global histogram font color."""
        from PySide6.QtWidgets import QColorDialog
        c = QColorDialog.getColor(self._font_color, self, "Font Color")
        if c.isValid():
            self._font_color = c
            self._refresh_font_color_btn()

    def _pick_element_color(self, element):
        """Select an element color used globally across histogram subplots."""
        from PySide6.QtWidgets import QColorDialog
        btn = self._elem_color_btns.get(element)
        if btn is None:
            return
        c = QColorDialog.getColor(btn._color, self, f"{element} Color")
        if c.isValid():
            btn._color = c
            btn.setStyleSheet(
                f"background-color: {c.name()}; border: 1px solid black;")

    def collect(self) -> dict:
        """Collect only histogram visual-format settings.

        Returns:
            dict: Format-only config updates that are safe to merge via
            ``node.config.update(...)`` without overwriting quantity settings.
        """
        out = {}
        out['font_family'] = self.font_family.currentText()
        out['font_size'] = self.font_size.value()
        out['font_bold'] = self.font_bold.isChecked()
        out['font_italic'] = self.font_italic.isChecked()
        out['font_color'] = self._font_color.name()
        out['label_mode'] = self.label_mode.currentText()
        out['show_curve'] = self.show_curve.isChecked()
        out['show_stats'] = self.show_stats.isChecked()
        out['show_box'] = self.show_box.isChecked()
        out['show_median_line'] = self.show_median_line.isChecked()
        out['show_mean_line'] = self.show_mean_line.isChecked()
        out['show_mode_marker'] = self.show_mode_marker.isChecked()
        out['show_det_limit'] = self.show_det_limit.isChecked()
        out['show_x_grid'] = self.show_x_grid.isChecked()
        out['show_y_grid'] = self.show_y_grid.isChecked()
        out['grid_alpha'] = self.grid_alpha.value()
        out['element_name_mappings'] = {
            e: ne.text().strip() or e
            for e, ne in self._elem_name_edits.items()
        }
        out['element_colors'] = {
            e: btn._color.name()
            for e, btn in self._elem_color_btns.items()
        }
        if self._multi and self._name_edits is not None:
            out['sample_name_mappings'] = {
                sn: ne.text() for sn, ne in self._name_edits.items()}
        return out


def _get_label_color(label, idx, cfg):
    """Get color for a label: check element_colors → group color → default.
    Args:
        label (Any): Label text.
        idx (Any): The idx.
        cfg (Any): The cfg.
    Returns:
        object: Result of the operation.
    """
    ec = cfg.get('element_colors', {})
    if label in ec:
        return ec[label]
    for i, g in enumerate(cfg.get('element_groups', [])):
        if g.get('name') == label:
            return g.get('color',
                         DEFAULT_ELEMENT_COLORS[
                             i % len(DEFAULT_ELEMENT_COLORS)])
    return DEFAULT_ELEMENT_COLORS[idx % len(DEFAULT_ELEMENT_COLORS)]


class HistogramDisplayDialog(QDialog):
    """Full-figure histogram dialog with PyQtGraph and right-click menu.

    This dialog owns parent-level histogram visibility state for legend-click
    hiding/showing of both raw isotope/element keys and raw sample keys.
    Visibility state is UI-local and render-only; scientific calculations and
    extracted data remain unchanged.
    """

    def __init__(self, histogram_node, parent_window=None):
        """
        Args:
            histogram_node (Any): The histogram node.
            parent_window (Any): The parent window.
        """
        super().__init__(parent_window)
        self.node = histogram_node
        self.parent_window = parent_window
        self._histogram_panel_contexts = {}
        self._decomposition_windows = []
        self._hidden_histogram_elements = set()
        self._hidden_histogram_samples = set()
        self.setWindowTitle("Particle Data Histogram Analysis")
        self.setMinimumSize(1000, 700)

        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _build_ui(self):
        """
        Build histogram canvas, stats footer, and standardized bottom buttons.

        Preserved behavior:
            Plot calculations are unchanged; this only adds consistent UI entry
            points for formatting, quantity configuration, layout reset, and
            figure export.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.pw = EnhancedGraphicsLayoutWidget()
        self.pw.setBackground('w')
        self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pw.customContextMenuRequested.connect(self._ctx_menu)
        layout.addWidget(self.pw, stretch=1)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            "color: #6B7280; font-size: 11px; padding: 2px 8px; "
            "background: #F8FAFC; border-top: 1px solid #E2E8F0;")
        layout.addWidget(self.stats_label)

        bb = QHBoxLayout()
        bb.setContentsMargins(0, 0, 0, 0)
        btn_fmt = QPushButton("Plot format settings")
        btn_fmt.clicked.connect(self._open_plot_format_settings)
        btn_qty = QPushButton("Configure plot quantities")
        btn_qty.clicked.connect(self._open_configure_plot_quantities)
        btn_reset = QPushButton("Reset layout")
        btn_reset.setToolTip("Reset plot ranges to automatic view.")
        btn_reset.clicked.connect(self._reset_layout)
        btn_export = QPushButton("Export figure")
        btn_export.clicked.connect(self._export_figure)
        bb.addWidget(btn_fmt)
        bb.addWidget(btn_qty)
        bb.addWidget(btn_reset)
        bb.addWidget(btn_export)
        layout.addLayout(bb)


    def _ctx_menu(self, pos):
        """
        Show lightweight histogram quick actions.

        Args:
            pos (Any): Position point.

        Preserved behavior:
            Keeps right-click focused on visual quick toggles and isotope label
            mode while full quantity/format/reset/export workflows are handled by
            bottom buttons. Unsupported overlay toggles are disabled per display
            mode and marked with explicit unavailable suffix text. Unavailable
            actions are also forced unchecked to avoid misleading checked-but-
            disabled states. A panel-specific decomposition action is offered
            only when clicked-panel context is eligible.
        """
        cfg = self.node.config
        clicked_plot = self._plot_item_at(pos)
        panel_ctx = self._histogram_panel_contexts.get(clicked_plot)
        menu = QMenu(self)
        plot_data = self.node.extract_plot_data()
        mode = self._get_hist_display_mode()
        support = self._get_quick_toggle_support(mode, plot_data)

        tg = menu.addMenu("Quick Toggles")
        for key, label, default in [
            ('show_curve',  'Density Curve',       True),
            ('show_stats',  'Statistics',          True),
            ('show_box',    'Figure Box (frame)',   True),
        ]:
            a = tg.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, default))
            entry = support.get(key, {})
            if not entry.get('enabled', True):
                a.setChecked(False)
                disabled_label = entry.get(
                    'label_suffix', f"{label} (unavailable in Overlaid mode)")
                a.setText(disabled_label)
                a.setEnabled(False)
                msg = entry.get(
                    'reason', 'Unavailable in multi-sample Overlaid mode.')
                a.setStatusTip(msg)
                a.setToolTip(msg)
            else:
                a.triggered.connect(lambda _, k=key: self._toggle_key(k))

        tg.addSeparator()
        sep1 = tg.addAction("-- Stat Lines --"); sep1.setEnabled(False)
        for key, label in [
            ('show_median_line',  'Median Line'),
            ('show_mean_line',    'Mean Line'),
            ('show_mode_marker',  'Mode Marker'),
            ('show_det_limit',    'Detection Limit'),
        ]:
            a = tg.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            entry = support.get(key, {})
            if not entry.get('enabled', True):
                a.setChecked(False)
                disabled_label = entry.get(
                    'label_suffix', f"{label} (unavailable in Overlaid mode)")
                a.setText(disabled_label)
                a.setEnabled(False)
                msg = entry.get(
                    'reason', 'Unavailable in multi-sample Overlaid mode.')
                a.setStatusTip(msg)
                a.setToolTip(msg)
            else:
                a.triggered.connect(lambda _, k=key: self._toggle_key(k))

        lm = menu.addMenu("Isotope Label")
        for mode in LABEL_MODES:
            a = lm.addAction(mode); a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set('label_mode', v))

        decompose_action = menu.addAction("Decompose by isotope...")
        eligible, reason = self._decomposition_eligibility(panel_ctx)
        if eligible:
            decompose_action.triggered.connect(
                lambda _, ctx=panel_ctx: self._open_decomposition_window(ctx))
        else:
            decompose_action.setText("Decompose by isotope... (unavailable)")
            decompose_action.setEnabled(False)
            decompose_action.setStatusTip(reason)
            decompose_action.setToolTip(reason)
        if self._hidden_histogram_elements:
            menu.addSeparator()
            show_all = menu.addAction("Show all isotopes")
            show_all.setToolTip(
                "Restore all legend-hidden isotopes/elements in this histogram view.")
            show_all.triggered.connect(self._show_all_histogram_elements)
        if self._hidden_histogram_samples:
            if not self._hidden_histogram_elements:
                menu.addSeparator()
            show_all_samples = menu.addAction("Show all samples")
            show_all_samples.setToolTip(
                "Restore all legend-hidden samples in Overlaid mode.")
            show_all_samples.triggered.connect(self._show_all_histogram_samples)
        menu.exec(self.pw.mapToGlobal(pos))

    def _toggle_histogram_element_visibility(self, raw_element_key: str):
        """Toggle parent histogram element visibility by raw isotope key.

        Args:
            raw_element_key (str): Raw isotope/element identifier used by
                extracted histogram data keys.

        Preserved behavior:
            This is render-layer filtering only. It does not delete data, alter
            histogram calculations, or persist to project save/load state.
            The method is invoked by legend-row click bindings attached at the
            PyQtGraph legend sample/label level, then triggers ``_refresh()``.
        """
        if not raw_element_key:
            return
        if raw_element_key in self._hidden_histogram_elements:
            self._hidden_histogram_elements.remove(raw_element_key)
        else:
            self._hidden_histogram_elements.add(raw_element_key)
        self._refresh()

    def _show_all_histogram_elements(self):
        """Clear all legend-hidden isotopes/elements and redraw.

        Preserved behavior:
            Resets only this dialog's UI visibility filter state. Scientific
            data extraction and histogram math remain unchanged.
        """
        if not self._hidden_histogram_elements:
            return
        self._hidden_histogram_elements.clear()
        self._refresh()

    def _toggle_histogram_sample_visibility(self, raw_sample_key: str):
        """Toggle parent histogram sample visibility by raw sample key.

        Args:
            raw_sample_key (str): Raw source sample key from multi-sample
                histogram data.

        Preserved behavior:
            This is render-layer filtering only for sample series (primarily
            Overlaid mode). It does not mutate scientific values or extraction
            semantics.
        """
        if not raw_sample_key:
            return
        if raw_sample_key in self._hidden_histogram_samples:
            self._hidden_histogram_samples.remove(raw_sample_key)
        else:
            self._hidden_histogram_samples.add(raw_sample_key)
        self._refresh()

    def _show_all_histogram_samples(self):
        """Clear legend-hidden samples and redraw the parent histogram.

        Preserved behavior:
            Only resets UI visibility filtering for raw sample keys; it does
            not change scientific configuration or persisted project state.
        """
        if not self._hidden_histogram_samples:
            return
        self._hidden_histogram_samples.clear()
        self._refresh()

    def _plot_item_at(self, pos):
        """Resolve the clicked histogram PlotItem from a context-menu position.

        Args:
            pos: Position in ``self.pw`` widget coordinates from
                ``customContextMenuRequested``.

        Returns:
            pg.PlotItem | None: Plot item under cursor, if any.

        Preserved behavior:
            This is a UI-only context resolver and does not alter data or
            rendering semantics.
        """
        try:
            scene_pos = self.pw.mapToScene(pos)
            for item in self.pw.scene().items():
                if isinstance(item, pg.PlotItem):
                    try:
                        rect = item.mapRectToScene(item.boundingRect())
                        if rect.contains(scene_pos):
                            return item
                    except Exception:
                        _itk_log.exception("Handled exception in _plot_item_at")
                        pass
        except Exception:
            _itk_log.exception("Handled exception in _plot_item_at")
            pass
        return None

    def _get_hist_display_mode(self):
        """Return the active histogram display mode for current input type.

        Returns:
            str: Normalized display-mode name.

        Preserved behavior:
            Uses the existing mode normalization and does not change scientific
            display-mode semantics.
        """
        if _is_multi(self.node.input_data):
            return _normalize_hist_display_mode(
                self.node.config.get('display_mode', HIST_DISPLAY_MODES[0]))
        return 'single'

    def _density_curve_supported(self, mode, plot_data):
        """Determine whether density curve toggle can render in current view.

        Args:
            mode (str): Active histogram display mode.
            plot_data (dict | None): Data returned by histogram extraction.

        Returns:
            bool: True when existing draw paths can visibly render density.

        Preserved behavior:
            Reflects current implementation limits (single plottable series per
            panel) without changing density calculations.
        """
        if mode == 'Overlaid (Different Colors)':
            return False
        if not plot_data:
            return False
        cfg = self.node.config
        if mode == 'single':
            return self._count_plottable_series(plot_data, cfg) == 1
        if isinstance(plot_data, dict):
            return all(
                self._count_plottable_series(sd or {}, cfg) == 1
                for sd in plot_data.values()
            )
        return False

    def _count_plottable_series(self, element_data, cfg):
        """Count series that can actually be plotted in a histogram panel.

        Args:
            element_data (dict): Element/isotope -> raw values for one panel.
            cfg (dict): Active histogram config used by value preparation.

        Returns:
            int: Number of non-empty plottable element series in this panel.

        Preserved behavior:
            Uses existing `_prepare_values(...)` filtering rules only to gate UI
            availability for density toggles; no density/stat math is changed.
        """
        dt = cfg.get('data_type_display', 'Counts')
        log_x = cfg.get('log_x', False)
        count = 0
        for raw_vals in (element_data or {}).values():
            vals = _prepare_values(raw_vals, dt, log_x)
            if vals is not None and len(vals) > 0:
                count += 1
        return count

    def _snapshot_panel_element_data(self, element_data):
        """Copy per-element value arrays for a child decomposition snapshot.

        Args:
            element_data (dict): Element/isotope mapping for one histogram panel.

        Returns:
            dict: Deep-ish copy ``element -> list(values)`` suitable for
            independent child-window rendering.

        Preserved behavior:
            Data values are copied for decoupling only; scientific semantics and
            extraction logic remain unchanged.
        """
        out = {}
        for elem, vals in (element_data or {}).items():
            out[elem] = list(vals) if vals is not None else []
        return out

    def _register_panel_context(self, plot_item, mode, panel_label, element_data,
                                sample_name=None):
        """Store per-panel context for right-click decomposition eligibility.

        Args:
            plot_item: PlotItem representing one rendered histogram panel.
            mode (str): Display mode used for this panel.
            panel_label (str): Human-readable sample/panel label.
            element_data (dict): Per-element arrays for this panel.
            sample_name (str | None): Raw output sample name backing this panel,
                used to resolve the particles-per-mL conversion factor for the
                decomposition child view.

        Preserved behavior:
            Context is rebuilt every refresh and never persisted into project
            state, keeping parent/child window lifetimes decoupled.
        """
        self._histogram_panel_contexts[plot_item] = {
            'mode': mode,
            'panel_label': panel_label,
            'sample_name': sample_name,
            'element_data': self._snapshot_panel_element_data(element_data),
        }

    def _decomposition_eligibility(self, panel_ctx):
        """Return whether isotope decomposition can open for clicked panel.

        Args:
            panel_ctx (dict | None): Stored panel context from right-click
                lookup.

        Returns:
            tuple[bool, str]: ``(eligible, reason_if_not)``.

        Preserved behavior:
            Uses existing plottable-series filtering and display-mode semantics
            only to gate this UI action; no scientific calculations are changed.
        """
        if not panel_ctx:
            return False, (
                "Available when right-clicking a specific histogram panel with "
                "at least two isotope/element series.")
        mode = panel_ctx.get('mode')
        if mode == 'Overlaid (Different Colors)':
            return False, "Unavailable in Overlaid multi-sample mode."
        plottable = self._count_plottable_series(
            panel_ctx.get('element_data', {}), self.node.config)
        if plottable < 2:
            return False, (
                "Available when a histogram panel contains at least two "
                "isotope/element series.")
        return True, ""

    def _open_decomposition_window(self, panel_ctx):
        """Open a decoupled child histogram window split by isotope/element.

        Args:
            panel_ctx (dict): Context snapshot for the clicked histogram panel.

        Preserved behavior:
            Child receives copied panel data and copied config so parent and
            child can be used independently without shared mutable state.
        """
        cfg_snapshot = dict(self.node.config)
        per_ml = _per_ml_active(cfg_snapshot, self.node.input_data)
        y_scale = (_pml_factor(self.node.input_data, panel_ctx.get('sample_name'))
                   if per_ml else 1.0)
        child = HistogramDecompositionDialog(
            config_snapshot=cfg_snapshot,
            panel_label=panel_ctx.get('panel_label', 'Current panel'),
            panel_element_data=panel_ctx.get('element_data', {}),
            per_ml=per_ml,
            y_scale=y_scale,
            parent=self,
        )
        child.destroyed.connect(
            lambda *_: self._decomposition_windows.remove(child)
            if child in self._decomposition_windows else None)
        self._decomposition_windows.append(child)
        child.show()

    def _get_quick_toggle_support(self, mode, plot_data):
        """Return per-toggle enabled/disabled support for current histogram mode.

        Args:
            mode (str): Active histogram display mode.
            plot_data (dict | None): Extracted histogram data for support checks.

        Returns:
            dict: Mapping ``config_key -> {enabled: bool, reason: str}``.

        Preserved behavior:
            This only gates UI availability so users are not shown inert
            toggles; it does not alter calculations or overlay math. In
            multi-sample Overlaid mode, unsupported statistical overlays are
            disabled while ``Figure Box`` remains enabled because it still
            affects presentation in that mode.
        """
        unsupported_overlaid = {
            'show_curve', 'show_stats',
            'show_median_line', 'show_mean_line',
            'show_mode_marker', 'show_det_limit',
        }
        labels = {
            'show_curve': 'Density Curve',
            'show_stats': 'Statistics',
            'show_box': 'Figure Box (frame)',
            'show_median_line': 'Median Line',
            'show_mean_line': 'Mean Line',
            'show_mode_marker': 'Mode Marker',
            'show_det_limit': 'Detection Limit',
        }
        support = {}
        for key in [
            'show_curve', 'show_stats', 'show_box',
            'show_median_line', 'show_mean_line',
            'show_mode_marker', 'show_det_limit',
        ]:
            support[key] = {'enabled': True, 'reason': ''}
            if mode == 'Overlaid (Different Colors)' and key in unsupported_overlaid:
                support[key] = {
                    'enabled': False,
                    'reason': 'Unavailable in multi-sample Overlaid mode.',
                    'label_suffix': f"{labels[key]} (unavailable in Overlaid mode)",
                }
        if not self._density_curve_supported(mode, plot_data):
            support['show_curve'] = {
                'enabled': False,
                'reason': 'Unavailable in multi-sample Overlaid mode.'
                if mode == 'Overlaid (Different Colors)'
                else 'Density curve requires a single series per panel',
                'label_suffix': 'Density Curve (unavailable in Overlaid mode)'
                if mode == 'Overlaid (Different Colors)'
                else 'Density Curve (requires single series per panel)',
            }
        return support

    def _toggle_key(self, key):
        """Toggle a visual overlay key and redraw histogram.

        Args:
            key (str): Histogram visual-toggle config key.

        Preserved behavior:
            Only updates UI/overlay visibility state; scientific data extraction
            and quantity settings are unchanged.
        """
        self.node.config[key] = not self.node.config.get(key, False)
        self._refresh()

    def _set(self, key, value):
        """
        Args:
            key (Any): Dictionary or storage key.
            value (Any): Value to set or process.
        """
        self.node.config[key] = value
        self._refresh()

    def _get_available_elements(self):
        """Get raw element names from input (before grouping).
        Returns:
            object: Result of the operation.
        """
        try:
            data = self.node.input_data
            if not data:
                return []
            dt = self.node.config.get('data_type_display', 'Counts')
            dk = HIST_DATA_KEY_MAP.get(dt, 'elements')
            elems = set()
            for p in data.get('particle_data', []):
                elems.update(p.get(dk, {}).keys())
            return sorted(elems)
        except Exception:
            _itk_log.exception("Handled exception in _get_available_elements")
            return []

    def _open_settings(self, title_override=None):
        """Open histogram quantity/configuration controls.

        Args:
            title_override (str | None): Optional explicit window title used by
                standardized bottom-button routes.

        Preserved behavior:
            Reuses the existing combined Histogram settings schema for this
            migration pass, keeping scientific quantity semantics unchanged.
        """
        dlg = HistogramSettingsDialog(
            self.node.config, _is_multi(self.node.input_data),
            _sample_names(self.node.input_data), self,
            available_elements=self._get_available_elements(),
            te_available=_meta_te_available(self.node.input_data))
        if title_override:
            dlg.setWindowTitle(title_override)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_plot_format_settings(self):
        """
        Open histogram format-only settings with global multi-subplot scope.

        Preserved behavior:
            Avoids single-PlotItem mutation paths so accepted changes are stored
            in canonical config and then redrawn consistently across all
            histogram subplots and legends.
        """
        dlg = HistogramFormatSettingsDialog(
            self.node.config,
            _is_multi(self.node.input_data),
            _sample_names(self.node.input_data),
            self,
            available_elements=self._get_available_elements(),
        )
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_configure_plot_quantities(self):
        """
        Open histogram quantity/configuration controls.

        Preserved behavior:
            Keeps quantity/scientific options in the dedicated bottom-button
            route and applies the standardized title.
        """
        self._open_settings(
            title_override="Histogram plot quantities configuration")

    def _open_plot_settings(self, title_override=None, show_apply=True):
        """Compatibility wrapper for the legacy single-plot settings editor.

        Args:
            title_override (str | None): Optional window-title override.
            show_apply (bool): Whether live Apply is visible in the dialog.

        Preserved behavior:
            Left available for non-primary legacy entry points, but Histogram's
            standardized format workflow uses ``HistogramFormatSettingsDialog``
            so settings apply globally across multi-subplot layouts.
        """
        if not _CUSTOM_PLOT_AVAILABLE or _PlotSettingsDialog is None:
            return
        pi = next(
            (item for item in self.pw.scene().items()
             if isinstance(item, pg.PlotItem)),
            None,
        )
        if pi is not None:
            dlg = _PlotSettingsDialog(
                _PlotWidgetAdapter(self.pw, pi), self, show_apply=show_apply)
            if title_override:
                try:
                    dlg.setWindowTitle(title_override)
                except Exception:
                    _itk_log.exception("Handled exception in _open_plot_settings")
                    pass
            dlg.exec()

    def _download_figure(self):
        """Export histogram figure and CSV via existing PyQtGraph helper."""
        import pandas as pd
        csv_df = None
        try:
            plot_data = self.node.extract_plot_data()
            cfg = self.node.config
            dt = cfg.get('data_type_display', 'Counts')
            if plot_data:
                rows = []
                if _is_multi(self.node.input_data):
                    for sn, sd in plot_data.items():
                        dname = get_display_name(sn, cfg)
                        for elem, vals in sd.items():
                            disp = _get_element_display_name(elem, cfg)
                            for v in vals:
                                rows.append({
                                    'Sample': dname,
                                    'Element/Group': elem,
                                    'Display Name': disp,
                                    dt: v})
                else:
                    for elem, vals in plot_data.items():
                        disp = _get_element_display_name(elem, cfg)
                        for v in vals:
                            rows.append({
                                'Element/Group': elem,
                                'Display Name': disp,
                                dt: v})
                if rows:
                    csv_df = pd.DataFrame(rows)
        except Exception as e:
            _itk_log.exception("Handled exception in _download_figure")
            print(f"Warning: could not build CSV data: {e}")

        download_pyqtgraph_figure(
            self.pw, self, default_name='histogram', csv_data=csv_df)

    def _export_figure(self):
        """Route standardized bottom export action to histogram export path."""
        self._download_figure()

    def _disable_native_pyqtgraph_context_menu(self):
        """
        Disable native PyQtGraph menus locally for Histogram.

        Preserved behavior:
            Prevents stacked native menus for this dialog only; global
            PyQtGraph behavior remains unchanged.
        """
        for item in self.pw.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    item.setMenuEnabled(False)
                except Exception:
                    _itk_log.exception("Handled exception in _disable_native_pyqtgraph_context_menu")
                    pass
                try:
                    vb = item.getViewBox()
                    if vb is not None:
                        vb.setMenuEnabled(False)
                except Exception:
                    _itk_log.exception("Handled exception in _disable_native_pyqtgraph_context_menu")
                    pass

    def _reset_layout(self):
        """
        Reset histogram layout/ranges without changing scientific settings.

        Preserved behavior:
            Data type, bins, curve/shade options, grouping, and log-axis
            semantics remain unchanged; only auto-range layout state is reset.
        """
        self.node.config['auto_x'] = True
        self.node.config['auto_y'] = True
        for item in self.pw.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    item.enableAutoRange(axis='xy', enable=True)
                    vb = item.getViewBox()
                    if vb is not None:
                        vb.autoRange()
                except Exception:
                    _itk_log.exception("Handled exception in _reset_layout")
                    pass
        self._refresh()


    def _refresh(self):
        """
        Rebuild and redraw the histogram canvas from current configuration.

        Preserved behavior:
            Scientific calculations and data extraction are unchanged. This
            method now normalizes legacy display-mode aliases and reapplies
            local native-menu suppression after redraw so the custom histogram
            context menu remains authoritative. Panel context mappings used for
            decomposition are rebuilt fresh on every redraw.
        """
        try:
            parent_layout = self.pw.parent().layout()
            idx = parent_layout.indexOf(self.pw)
            parent_layout.removeWidget(self.pw)
            self.pw.deleteLater()
            self.pw = EnhancedGraphicsLayoutWidget()
            self.pw.setBackground('w')
            self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
            self.pw.customContextMenuRequested.connect(self._ctx_menu)
            parent_layout.insertWidget(idx, self.pw, stretch=1)
            self._histogram_panel_contexts = {}

            plot_data = self.node.extract_plot_data()
            cfg = self.node.config

            if not plot_data:
                pi = self.pw.addPlot(axisItems={'left': HtmlAxisItem('left')})
                t = pg.TextItem(
                    "No particle data available\n"
                    "Connect to Sample Selector\n"
                    "and run particle detection",
                    anchor=(0.5, 0.5), color='gray')
                pi.addItem(t, ignoreBounds=True)
                t.setPos(0.5, 0.5)
                pi.hideAxis('left')
                pi.hideAxis('bottom')
                self.stats_label.setText("")
                return

            if _is_multi(self.node.input_data):
                mode = _normalize_hist_display_mode(
                    cfg.get('display_mode', HIST_DISPLAY_MODES[0]))
                if mode == 'Individual Subplots':
                    self._draw_subplots(plot_data, cfg)
                elif mode == 'Side by Side Subplots':
                    self._draw_side_by_side(plot_data, cfg)
                else:
                    self._draw_overlaid(plot_data, cfg)
            else:
                pi = self.pw.addPlot(axisItems={'left': HtmlAxisItem('left')})
                per_ml = _per_ml_active(cfg, self.node.input_data)
                sn = self.node.input_data.get('sample_name') if self.node.input_data else None
                y_scale = _pml_factor(self.node.input_data, sn) if per_ml else 1.0
                _draw_single_histogram(
                    pi,
                    plot_data,
                    cfg,
                    hidden_elements=self._hidden_histogram_elements,
                    legend_click_callback=self._toggle_histogram_element_visibility,
                    y_scale=y_scale,
                    y_label='Particles/mL' if per_ml else None,
                )
                self._register_panel_context(
                    pi, 'single', 'Current sample', plot_data, sample_name=sn)
                if cfg.get('show_stats', True):
                    _add_stats_text(pi, plot_data, cfg)

            self._disable_native_pyqtgraph_context_menu()
            self._update_stats(plot_data)

        except Exception as e:
            _itk_log.exception("Handled exception in _refresh")
            print(f"Error updating histogram: {e}")
            import traceback
            traceback.print_exc()

    def _draw_subplots(self, plot_data, cfg):
        """
        Draw one subplot per sample using per-element color encoding.

        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.

        Preserved behavior:
            Histogram calculations are unchanged. When enabled, statistics text
            is now rendered per-sample subplot using that subplot's data. Each
            subplot also registers per-panel context for decomposition actions.
        """
        samples = list(plot_data.keys())
        cols = min(2, len(samples))
        per_ml = _per_ml_active(cfg, self.node.input_data)
        for idx, sn in enumerate(samples):
            if idx > 0 and idx % cols == 0:
                self.pw.nextRow()
            pi = self.pw.addPlot(title=get_display_name(sn, cfg),
                                 axisItems={'left': HtmlAxisItem('left')})
            sd = plot_data[sn]
            if sd:
                y_scale = _pml_factor(self.node.input_data, sn) if per_ml else 1.0
                _draw_single_histogram(
                    pi,
                    sd,
                    cfg,
                    hidden_elements=self._hidden_histogram_elements,
                    legend_click_callback=self._toggle_histogram_element_visibility,
                    y_scale=y_scale,
                    y_label='Particles/mL' if per_ml else None,
                )
                self._register_panel_context(
                    pi, 'Individual Subplots', get_display_name(sn, cfg), sd,
                    sample_name=sn)
                if cfg.get('show_stats', True):
                    _add_stats_text(pi, sd, cfg)

    def _draw_side_by_side(self, plot_data, cfg):
        """
        Draw side-by-side sample subplots using per-element color encoding.

        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.

        Preserved behavior:
            Statistical overlays keep existing semantics; stats text is added
            per subplot when enabled so each sample panel reports its own data.
            Panel contexts are captured per sample for right-click decomposition.
        """
        first_pi = None
        xl, yl = _get_xy_labels(cfg)
        per_ml = _per_ml_active(cfg, self.node.input_data)
        for idx, (sn, sd) in enumerate(plot_data.items()):
            pi = self.pw.addPlot(row=0, col=idx, title=get_display_name(sn, cfg),
                                 axisItems={'left': HtmlAxisItem('left')})
            if sd:
                y_scale = _pml_factor(self.node.input_data, sn) if per_ml else 1.0
                _draw_single_histogram(
                    pi,
                    sd,
                    cfg,
                    hidden_elements=self._hidden_histogram_elements,
                    legend_click_callback=self._toggle_histogram_element_visibility,
                    y_scale=y_scale,
                    y_label='Particles/mL' if per_ml else None,
                )
                self._register_panel_context(
                    pi, 'Side by Side Subplots', get_display_name(sn, cfg), sd,
                    sample_name=sn)
                if cfg.get('show_stats', True):
                    _add_stats_text(pi, sd, cfg)
            if first_pi is None:
                first_pi = pi
            else:
                pi.setYLink(first_pi)
                pi.getAxis('left').setLabel('')
                pi.getAxis('left').setStyle(showValues=False)
            if cfg.get('log_x', False):
                pi.getAxis('bottom').setLogMode(True)
            if cfg.get('log_y', False):
                pi.getAxis('left').setLogMode(True)
            if not cfg.get('auto_x', True):
                xn, xx = cfg.get('x_min', 0), cfg.get('x_max', 1000)
                if cfg.get('log_x', False) and xn > 0 and xx > 0:
                    xn, xx = float(np.log10(xn)), float(np.log10(xx))
                pi.setXRange(xn, xx, padding=0)
            apply_font_to_pyqtgraph(pi, cfg)

    def _draw_overlaid(self, plot_data, cfg):
        """Draw multi-sample overlaid histogram view.

        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.

        Preserved behavior:
            Scientific aggregation and sample-color encoding are unchanged.
            The plot frame/box toggle is applied in this mode for consistency
            with other histogram layouts. Overlaid context is marked ineligible
            for decomposition because it does not represent one sample panel.
            Sample-level legend clicks can hide/show whole sample series using
            raw sample keys, while hidden isotope keys are still filtered before
            per-sample aggregation.
        """
        pi = self.pw.addPlot(axisItems={'left': HtmlAxisItem('left')})
        self._register_panel_context(
            pi, 'Overlaid (Different Colors)', 'Overlaid', {})
        dt = cfg.get('data_type_display', 'Counts')
        log_x = cfg.get('log_x', False)
        bins_n = cfg.get('bins', 20)
        per_ml = _per_ml_active(cfg, self.node.input_data)

        legend = pg.LegendItem(offset=(60, 10))
        legend.setParentItem(pi.graphicsItem())
        pi.legend = legend

        drew_any = False
        hidden = self._hidden_histogram_elements
        hidden_samples = self._hidden_histogram_samples
        plottable_samples = [sn for sn, sd in plot_data.items() if sd]
        all_plottable_samples_hidden = (
            len(plottable_samples) > 0
            and all(sn in hidden_samples for sn in plottable_samples)
        )
        for idx, (sn, sd) in enumerate(plot_data.items()):
            if not sd:
                continue
            color = get_sample_color(sn, idx, cfg)
            dname = get_display_name(sn, cfg)
            sample_hidden = sn in hidden_samples
            combined = []
            for elem, vals in sd.items():
                if elem in hidden:
                    continue
                combined.extend(vals)
            co = QColor(color)
            s_alpha = 55 if sample_hidden else 180
            swatch = _ClickableLegendSwatch(
                x=[0], height=[0], width=0,
                brush=pg.mkBrush(co.red(), co.green(), co.blue(), s_alpha),
                raw_key=sn,
                toggle_callback=self._toggle_histogram_sample_visibility,
            )
            lbl = dname + (" (hidden)" if sample_hidden else "")
            legend.addItem(swatch, lbl)
            _attach_histogram_legend_toggle(
                legend,
                raw_key=sn,
                toggle_callback=self._toggle_histogram_sample_visibility,
            )
            if sample_hidden:
                continue
            v = _prepare_values(combined, dt, log_x)
            if v is None:
                continue
            drew_any = True
            y_scale = _pml_factor(self.node.input_data, sn) if per_ml else 1.0
            _draw_histogram_bars(pi, v, cfg, color, bins_n, y_scale=y_scale)

        if not drew_any:
            msg = (
                "No visible samples"
                if all_plottable_samples_hidden
                else "No visible isotopes"
            )
            ti = pg.TextItem(msg, anchor=(0.5, 0.5), color='#9CA3AF')
            pi.addItem(ti, ignoreBounds=True)
            try:
                vb = pi.getViewBox()
                xr, yr = vb.viewRange()
                ti.setPos((xr[0] + xr[1]) * 0.5, (yr[0] + yr[1]) * 0.5)
            except Exception:
                _itk_log.exception("Handled exception in _draw_overlaid")
                ti.setPos(0, 0)

        xl, yl = _get_xy_labels(cfg)
        if per_ml:
            yl = 'Particles/mL'
        set_axis_labels(pi, xl, yl, cfg)
        if cfg.get('log_x', False):
            pi.getAxis('bottom').setLogMode(True)
        if cfg.get('log_y', False):
            pi.getAxis('left').setLogMode(True)
        if not cfg.get('auto_x', True):
            xn, xx = cfg.get('x_min', 0), cfg.get('x_max', 1000)
            if cfg.get('log_x', False) and xn > 0 and xx > 0:
                xn, xx = float(np.log10(xn)), float(np.log10(xx))
            pi.setXRange(xn, xx, padding=0)
        if not cfg.get('auto_y', True):
            pi.setYRange(cfg.get('y_min', 0), cfg.get('y_max', 100), padding=0)
        _apply_box(pi, cfg)
        _apply_histogram_grid(pi, cfg)
        apply_font_to_pyqtgraph(pi, cfg)
        if per_ml and not cfg.get('log_y', False):
            _apply_sci_y_axis(pi, cfg)

    def _draw_combined(self, plot_data, cfg):
        """
        Legacy wrapper for historical ``Combined with Legend`` mode values.

        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        self._draw_overlaid(plot_data, cfg)

    def _update_stats(self, plot_data):
        """
        Args:
            plot_data (Any): The plot data.
        """
        cfg = self.node.config
        groups = cfg.get('element_groups', [])
        group_info = ""
        if groups and _can_sum(cfg):
            names = [g['name'] for g in groups if g.get('name')]
            if names:
                group_info = f"  \u00b7  Groups: {', '.join(names)}"

        if _is_multi(self.node.input_data):
            total = sum(
                sum(len(v) for v in sd.values())
                for sd in plot_data.values())
            self.stats_label.setText(
                f"{len(plot_data)} samples  \u00b7  "
                f"{total:,} values{group_info}")
        else:
            total = sum(len(v) for v in plot_data.values())
            self.stats_label.setText(
                f"{len(plot_data)} elements/groups  \u00b7  "
                f"{total:,} values{group_info}")


class HistogramDecompositionDialog(QDialog):
    """Independent child dialog that decomposes one histogram panel by isotope.

    This window renders one single-series histogram panel per element/isotope
    using a snapshot of parent panel data, with no write-back to parent node
    or project lifecycle state.
    """

    def __init__(self, config_snapshot, panel_label, panel_element_data, parent=None,
                 per_ml=False, y_scale=1.0):
        """
        Args:
            config_snapshot (dict): Copied parent histogram config.
            panel_label (str): Human-readable source sample/panel label.
            panel_element_data (dict): Copied per-element arrays for one panel.
            parent (QWidget | None): Qt parent for window ownership only.
            per_ml (bool): Whether the parent panel is rendering the
                particles-per-mL y-axis unit. Inherited so the decomposition
                view respects the same y-axis selection.
            y_scale (float): Multiplier converting raw bin counts to particles
                per mL for this panel's sample. Defaults to 1.0 (raw counts).

        Preserved behavior:
            Child owns local rendering/config and reuses existing histogram
            drawing helpers without changing scientific extraction semantics.
            Data type is inherited from parent and intentionally locked because
            this child redraws from frozen parent snapshot arrays rather than
            re-extracting alternate data-type values.
        """
        super().__init__(parent)
        self._cfg = dict(config_snapshot or {})
        self._per_ml = bool(per_ml)
        self._y_scale = float(y_scale) if y_scale else 1.0
        self._inherited_data_type = self._cfg.get('data_type_display', 'Counts')
        self._cfg['data_type_display'] = self._inherited_data_type
        self._cfg['show_median'] = False
        self._panel_label = panel_label or "Current panel"
        self._element_data = {
            k: list(v) for k, v in (panel_element_data or {}).items()
        }
        self.setWindowTitle(f"Histogram decomposition — {self._panel_label}")
        self.setMinimumSize(1000, 700)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        """Build decomposition plot area and standardized bottom buttons.

        Preserved behavior:
            Uses the same four-button contract as parent histogram while
            keeping child controls local to this decomposed view only.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.pw = EnhancedGraphicsLayoutWidget()
        self.pw.setBackground('w')
        self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pw.customContextMenuRequested.connect(self._ctx_menu)
        layout.addWidget(self.pw, stretch=1)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            "color: #6B7280; font-size: 11px; padding: 2px 8px; "
            "background: #F8FAFC; border-top: 1px solid #E2E8F0;")
        layout.addWidget(self.stats_label)

        bb = QHBoxLayout()
        bb.setContentsMargins(0, 0, 0, 0)
        btn_fmt = QPushButton("Plot format settings")
        btn_fmt.clicked.connect(self._open_plot_format_settings)
        btn_qty = QPushButton("Configure plot quantities")
        btn_qty.clicked.connect(self._open_configure_plot_quantities)
        btn_reset = QPushButton("Reset layout")
        btn_reset.clicked.connect(self._reset_layout)
        btn_export = QPushButton("Export figure")
        btn_export.clicked.connect(self._export_figure)
        bb.addWidget(btn_fmt)
        bb.addWidget(btn_qty)
        bb.addWidget(btn_reset)
        bb.addWidget(btn_export)
        layout.addLayout(bb)

    def _plot_item_at(self, pos):
        """Resolve which decomposed histogram subplot was right-clicked.

        Args:
            pos: Position in ``self.pw`` widget coordinates from
                ``customContextMenuRequested``.

        Returns:
            pg.PlotItem | None: Clicked subplot plot item when resolvable.
        """
        try:
            scene_pos = self.pw.mapToScene(pos)
            for item in self.pw.scene().items():
                if isinstance(item, pg.PlotItem):
                    try:
                        rect = item.mapRectToScene(item.boundingRect())
                        if rect.contains(scene_pos):
                            return item
                    except Exception:
                        _itk_log.exception("Handled exception in _plot_item_at")
                        pass
        except Exception:
            _itk_log.exception("Handled exception in _plot_item_at")
            pass
        return None

    @staticmethod
    def _sanitize_filename_part(value):
        """Return a filesystem-safe token for subplot export filenames."""
        text = str(value or "").strip().replace(" ", "_")
        cleaned = ''.join(ch if ch.isalnum() or ch in ('_', '-', '.') else '_'
                          for ch in text)
        return cleaned.strip('_') or "subplot"

    def _ctx_menu(self, pos):
        """Show child quick toggles, isotope label, and subplot export action.

        Args:
            pos: Right-click location in widget coordinates.

        Preserved behavior:
            Child keeps the same minimal right-click contract and does not
            offer recursive decomposition actions.
        """
        menu = QMenu(self)
        clicked_plot = self._plot_item_at(pos)
        subplot_ctx = self._subplot_context_by_plotitem.get(clicked_plot)
        tg = menu.addMenu("Quick Toggles")
        for key, label, default in [
            ('show_curve',  'Density Curve',       True),
            ('show_stats',  'Statistics',          True),
            ('show_box',    'Figure Box (frame)',  True),
            ('show_median_line', 'Median Line',    False),
            ('show_mean_line',   'Mean Line',      False),
            ('show_mode_marker', 'Mode Marker',    False),
            ('show_det_limit',   'Detection Limit', False),
        ]:
            a = tg.addAction(label)
            a.setCheckable(True)
            a.setChecked(self._cfg.get(key, default))
            a.triggered.connect(lambda _, k=key: self._toggle_key(k))

        lm = menu.addMenu("Isotope Label")
        for mode in LABEL_MODES:
            a = lm.addAction(mode)
            a.setCheckable(True)
            a.setChecked(self._cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set_key('label_mode', v))

        if clicked_plot is not None and subplot_ctx is not None:
            exp_act = menu.addAction("Export this subplot...")
            exp_act.triggered.connect(
                lambda *_: self._export_subplot(clicked_plot, subplot_ctx))
        else:
            exp_act = menu.addAction("Export this subplot... (unavailable here)")
            exp_act.setEnabled(False)
            exp_act.setStatusTip("Right-click a subplot panel to export only that panel.")
            exp_act.setToolTip("Right-click a subplot panel to export only that panel.")

        menu.exec(self.pw.mapToGlobal(pos))

    def _toggle_key(self, key):
        """Toggle one local child visual setting and redraw."""
        self._cfg[key] = not self._cfg.get(key, False)
        self._refresh()

    def _set_key(self, key, value):
        """Set one local child config key and redraw."""
        self._cfg[key] = value
        self._refresh()

    def _open_plot_format_settings(self):
        """Open local format settings for decomposed histogram panels.

        Preserved behavior:
            Applies format updates to child-local config only; parent histogram
            settings and project state are unchanged.
        """
        dlg = HistogramFormatSettingsDialog(
            self._cfg, False, [], self,
            available_elements=sorted(self._element_data.keys()))
        dlg.setWindowTitle("Histogram plot format settings")
        if dlg.exec() == QDialog.Accepted:
            self._cfg.update(dlg.collect())
            self._refresh()

    def _open_configure_plot_quantities(self):
        """Open local quantity settings for decomposed histogram panels.

        Preserved behavior:
            Reuses histogram quantity dialog behavior but keeps all updates in
            child-local config only. Data type is inherited from parent and
            read-only here to avoid scientifically misleading relabeling of the
            frozen decomposition snapshot values.
        """
        dlg = HistogramSettingsDialog(
            self._cfg, False, [], self,
            available_elements=sorted(self._element_data.keys()),
            lock_data_type=True,
            data_type_lock_message=(
                "Data type inherited from parent for decomposed histograms. "
                "Re-extraction for other data types is not available in this view yet."
            ),
        )
        dlg.setWindowTitle("Histogram plot quantities configuration")
        if dlg.exec() == QDialog.Accepted:
            self._cfg.update(dlg.collect())
            self._cfg['data_type_display'] = self._inherited_data_type
            self._refresh()

    def _reset_layout(self):
        """Reset child view ranges without modifying plotted values."""
        self._cfg['auto_x'] = True
        self._cfg['auto_y'] = True
        for item in self.pw.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    item.enableAutoRange(axis='xy', enable=True)
                    vb = item.getViewBox()
                    if vb is not None:
                        vb.autoRange()
                except Exception:
                    _itk_log.exception("Handled exception in _reset_layout")
                    pass
        self._refresh()

    def _download_figure(self):
        """Export the child decomposition figure and per-element CSV rows."""
        import pandas as pd
        rows = []
        dt = self._cfg.get('data_type_display', 'Counts')
        for elem, vals in self._element_data.items():
            disp = _get_element_display_name(elem, self._cfg)
            for v in vals or []:
                rows.append({
                    'Panel': self._panel_label,
                    'Element/Group': elem,
                    'Display Name': disp,
                    dt: v,
                })
        csv_df = pd.DataFrame(rows) if rows else None
        download_pyqtgraph_figure(
            self.pw, self, default_name='histogram_decomposition', csv_data=csv_df)

    def _export_subplot(self, plot_item, subplot_ctx):
        """Export only one clicked decomposed histogram subplot.

        Reuses the shared export dialog/options path while targeting a specific
        rendered ``PlotItem`` instead of the full child scene.
        """
        import pandas as pd
        raw_elem = subplot_ctx.get('element') if subplot_ctx else None
        vals = list(self._element_data.get(raw_elem, []))
        dt = self._cfg.get('data_type_display', 'Counts')
        disp = _get_element_display_name(raw_elem, self._cfg) if raw_elem else "subplot"
        rows = [{
            'Panel': self._panel_label,
            'Element/Group': raw_elem,
            'Display Name': disp,
            dt: v,
        } for v in vals]
        csv_df = pd.DataFrame(rows) if rows else None
        default_name = (
            f"histogram_{self._sanitize_filename_part(self._panel_label)}_"
            f"{self._sanitize_filename_part(raw_elem or disp)}"
        )
        download_pyqtgraph_figure(
            self.pw,
            self,
            default_name=default_name or "subplot_export",
            csv_data=csv_df,
            export_item=plot_item,
        )

    def _export_figure(self):
        """Route standardized export action to child export helper."""
        self._download_figure()

    def _disable_native_pyqtgraph_context_menu(self):
        """Disable native PyQtGraph context menus for all child panels."""
        for item in self.pw.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    item.setMenuEnabled(False)
                except Exception:
                    _itk_log.exception("Handled exception in _disable_native_pyqtgraph_context_menu")
                    pass
                try:
                    vb = item.getViewBox()
                    if vb is not None:
                        vb.setMenuEnabled(False)
                except Exception:
                    _itk_log.exception("Handled exception in _disable_native_pyqtgraph_context_menu")
                    pass

    def _get_custom_title_map(self):
        """Return the child-local custom title mapping for decomposed subplots.

        Returns:
            dict: Mutable mapping of raw isotope keys to custom display titles.

        Preserved behavior:
            Custom title text remains local to this child dialog and uses raw
            isotope keys as canonical identifiers. Scientific labels and data
            extraction semantics are unchanged.
        """
        custom_titles = self._cfg.get('custom_titles')
        if not isinstance(custom_titles, dict):
            custom_titles = {}
            self._cfg['custom_titles'] = custom_titles
        return custom_titles

    def _default_title_for_element(self, raw_element_key):
        """Return the default rendered title for one decomposed subplot.

        Args:
            raw_element_key (str): Canonical raw isotope/element key.

        Returns:
            str: Default subplot title generated from current label settings.
        """
        return _fmt_elem(raw_element_key, self._cfg)

    def _effective_title_for_element(self, raw_element_key):
        """Resolve the visible title text for one decomposed subplot.

        Args:
            raw_element_key (str): Canonical raw isotope/element key.

        Returns:
            str: Custom title text when stored, otherwise the default title.
        """
        custom_title = self._get_custom_title_map().get(raw_element_key)
        if isinstance(custom_title, str) and custom_title.strip():
            return custom_title.strip()
        return self._default_title_for_element(raw_element_key)

    def _store_custom_title_text(self, raw_element_key, title_text):
        """Persist one custom decomposed-subplot title in child-local config.

        Args:
            raw_element_key (str): Canonical raw isotope/element key.
            title_text (str): User-entered title text for the subplot.

        Returns:
            None

        Preserved behavior:
            Blank text removes the override so the subplot falls back to the
            normal isotope display name on future redraws.
        """
        clean_text = (title_text or '').strip()
        custom_titles = self._get_custom_title_map()
        if clean_text:
            custom_titles[raw_element_key] = clean_text
        else:
            custom_titles.pop(raw_element_key, None)

    def _apply_custom_title_edit(self, plot_item, raw_element_key, title_text):
        """Persist one edited title and update the live decomposed subplot.

        Args:
            plot_item (Any): Target ``pg.PlotItem`` receiving the title edit.
            raw_element_key (str): Canonical raw isotope/element key.
            title_text (str): User-entered title text from the editor dialog.

        Returns:
            None

        Preserved behavior:
            This updates only display text. Title styling continues to be owned
            by the existing live editor and histogram format settings.
        """
        self._store_custom_title_text(raw_element_key, title_text)
        plot_item.setTitle(self._effective_title_for_element(raw_element_key))

    def _configure_plot_title(self, plot_item, raw_element_key):
        """Attach persistent title-edit behavior to one decomposed subplot.

        Args:
            plot_item (Any): Target ``pg.PlotItem`` for the isotope subplot.
            raw_element_key (str): Canonical raw isotope/element key.

        Returns:
            None

        Preserved behavior:
            Double-click title editing remains available through the shared
            title editor, while custom title content now survives child redraws.
        """
        plot_item._title_editor_options = {
            'title_apply_callback': (
                lambda text, _plot_item=plot_item, _key=raw_element_key:
                self._apply_custom_title_edit(_plot_item, _key, text)
            ),
        }

    def _refresh(self):
        """Rebuild and redraw one single-series subplot per isotope/element.

        Preserved behavior:
            Child uses parent snapshot data only. Each subplot receives exactly
            one element series, preserving existing single-series density support
            rules without introducing new scientific calculations. When density
            is requested but unavailable for a panel, a small in-panel note is
            shown instead of modal warnings.
        """
        parent_layout = self.pw.parent().layout()
        idx = parent_layout.indexOf(self.pw)
        parent_layout.removeWidget(self.pw)
        self.pw.deleteLater()
        self.pw = EnhancedGraphicsLayoutWidget()
        self.pw.setBackground('w')
        self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pw.customContextMenuRequested.connect(self._ctx_menu)
        parent_layout.insertWidget(idx, self.pw, stretch=1)
        self._subplot_context_by_plotitem = {}

        sorted_items = sort_element_dict_by_mass(self._element_data)
        valid = []
        dt = self._cfg.get('data_type_display', 'Counts')
        log_x = self._cfg.get('log_x', False)
        for elem, vals in sorted_items.items():
            pv = _prepare_values(vals, dt, log_x)
            if pv is not None and len(pv) > 0:
                valid.append((elem, vals))

        if not valid:
            pi = self.pw.addPlot(axisItems={'left': HtmlAxisItem('left')})
            t = pg.TextItem(
                "No plottable isotope data available",
                anchor=(0.5, 0.5), color='gray')
            pi.addItem(t, ignoreBounds=True)
            t.setPos(0.5, 0.5)
            pi.hideAxis('left')
            pi.hideAxis('bottom')
            self.stats_label.setText("")
            return

        cols = min(2, len(valid))
        for idx_plot, (elem, vals) in enumerate(valid):
            if idx_plot > 0 and idx_plot % cols == 0:
                self.pw.nextRow()
            effective_title = self._effective_title_for_element(elem)
            pi = self.pw.addPlot(title=effective_title,
                                 axisItems={'left': HtmlAxisItem('left')})
            self._configure_plot_title(pi, elem)
            self._subplot_context_by_plotitem[pi] = {
                'element': elem,
                'title': _get_element_display_name(elem, self._cfg),
            }
            density_status = {}
            _draw_single_histogram(
                pi, {elem: vals}, self._cfg, density_status_out=density_status,
                y_scale=self._y_scale if self._per_ml else 1.0,
                y_label='Particles/mL' if self._per_ml else None)
            if self._cfg.get('show_curve', True):
                st = density_status.get(elem, {})
                if st and not st.get('success'):
                    self._add_density_unavailable_note(pi)
            if self._cfg.get('show_stats', True):
                _add_stats_text(pi, {elem: vals}, self._cfg)

        self._disable_native_pyqtgraph_context_menu()
        total_values = sum(len(v or []) for _, v in valid)
        self.stats_label.setText(
            f"{len(valid)} isotope panels  \u00b7  {total_values:,} values")

    def _add_density_unavailable_note(self, plot_item):
        """Add a minimal per-panel note when density curve cannot be rendered.

        Args:
            plot_item: The child subplot PlotItem.

        Preserved behavior:
            This is non-modal UI feedback only. It does not alter density
            calculations, value preparation, or histogram semantics. Note
            position is centered at x=0 when visible, otherwise centered at the
            visible x-range midpoint, and near the top of the visible y-range.
            The note is excluded from autorange bounds so it cannot distort
            decomposed histogram axes when rendered.
        """
        ti = pg.TextItem(
            "Density curve unavailable",
            anchor=(0.5, 0),
            color='#9CA3AF')
        ti.setZValue(50)
        plot_item.addItem(ti, ignoreBounds=True)
        try:
            vb = plot_item.getViewBox()
            rng = vb.viewRange()
            x_min, x_max = rng[0]
            y_min, y_max = rng[1]
            if x_min <= 0 <= x_max:
                x_pos = 0.0
            else:
                x_pos = x_min + (x_max - x_min) * 0.5
            y_pos = y_min + (y_max - y_min) * 0.88
            ti.setPos(
                x_pos,
                y_pos,
            )
        except Exception:
            _itk_log.exception("Handled exception in _add_density_unavailable_note")
            ti.setPos(0, 0)


class HistogramPlotNode(QObject):
    """Histogram visualization node with element grouping support.

    Element groups sum selected element values PER PARTICLE into a
    single combined value, then plot the histogram of those sums.
    """

    position_changed = Signal(object)
    configuration_changed = Signal()

    DEFAULT_CONFIG = {
        'data_type_display': 'Counts',
        'y_axis_unit': 'count',
        'element_groups': [],
        'element_name_mappings': {},
        'show_curve': True,
        'curve_type': 'Kernel Density',
        'show_median': True,
        'show_median_line': False,
        'show_mean_line': False,
        'show_mode_marker': False,
        'median_line_color': '#0F6E56',
        'median_line_style': 'dash',
        'median_line_width': 2,
        'mean_line_color': '#B45309',
        'mean_line_style': 'solid',
        'mean_line_width': 2,
        'mode_line_color': '#7C3AED',
        'mode_line_style': 'dot',
        'mode_line_width': 2,
        'curve_color': '#2C3E50',
        'bins': 20,
        'alpha': 0.7,
        'log_x': False,
        'log_y': False,
        'show_stats': True,
        'shade_type': 'None',
        'shade_color': '#534AB7',
        'shade_alpha': 0.18,
        'show_det_limit': False,
        'det_limit_value': 1.0,
        'det_limit_color': '#DC2626',
        'det_limit_style': 'dash',
        'det_limit_width': 2,
        'det_limit_label': '',
        'show_box': True,
        'x_min': 0, 'x_max': 1000, 'auto_x': True,
        'y_min': 0, 'y_max': 100, 'auto_y': True,
        'element_colors': {},
        'display_mode': 'Overlaid (Different Colors)',
        'sample_colors': {},
        'sample_name_mappings': {},
        'font_family': 'Times New Roman',
        'font_size': 18,
        'font_bold': False,
        'font_italic': False,
        'font_color': '#000000',
        'label_mode': 'Symbol',
    }

    def __init__(self, parent_window=None):
        """
        Args:
            parent_window (Any): The parent window.
        """
        super().__init__()
        self.title = "Histogram"
        self.node_type = "histogram_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        self.config = dict(self.DEFAULT_CONFIG)
        self.input_data = None
        self.plot_widget = None

    def set_position(self, pos):
        """
        Args:
            pos (Any): Position point.
        """
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        """
        Args:
            parent_window (Any): The parent window.
        Returns:
            bool: Result of the operation.
        """
        dlg = HistogramDisplayDialog(self, parent_window)
        dlg.exec()
        return True

    def process_data(self, input_data):
        """
        Args:
            input_data (Any): The input data.
        """
        if not input_data:
            return
        self.input_data = input_data
        self.configuration_changed.emit()

    def extract_plot_data(self):
        """Extract plottable data, applying element groups when active.

        Groups SUM element values per particle. For example if a
        particle has Fe=10fg, Si=5fg, Ti=3fg and group "FeSiTi"
        includes [Fe, Si, Ti], that particle contributes 18fg to
        the "FeSiTi" histogram. Ungrouped elements stay separate.
        Returns:
            None
        """
        if not self.input_data:
            return None

        dt = self.config.get('data_type_display', 'Counts')
        dk = HIST_DATA_KEY_MAP.get(dt, 'elements')
        itype = self.input_data.get('type')

        groups = self.config.get('element_groups', [])
        use_groups = bool(groups) and _can_sum(self.config)

        if itype == 'sample_data':
            if use_groups:
                particles = self.input_data.get('particle_data', [])
                out = _apply_element_groups(particles, dk, groups)
                return out or None
            return self._extract_single(dk)

        elif itype == 'multiple_sample_data':
            if use_groups:
                particles = self.input_data.get('particle_data', [])
                names = self.input_data.get('sample_names', [])
                out = _apply_element_groups_multi(
                    particles, names, dk, groups)
                return out or None
            return self._extract_multi(dk)

        return None

    def _extract_single(self, dk):
        """
        Args:
            dk (Any): The dk.
        Returns:
            object: Result of the operation.
        """
        particles = self.input_data.get('particle_data')
        if not particles:
            return None
        out = {}
        for p in particles:
            d = p.get(dk, {})
            for el, val in d.items():
                if dk == 'elements':
                    if val > 0:
                        out.setdefault(el, []).append(val)
                else:
                    if val > 0 and not np.isnan(val):
                        out.setdefault(el, []).append(val)
        return out or None

    def _extract_multi(self, dk):
        """
        Args:
            dk (Any): The dk.
        Returns:
            object: Result of the operation.
        """
        particles = self.input_data.get('particle_data', [])
        names = self.input_data.get('sample_names', [])
        if not particles:
            return None
        result = {sn: {} for sn in names}
        for p in particles:
            src = p.get('source_sample')
            if src not in result:
                continue
            d = p.get(dk, {})
            for el, val in d.items():
                if dk == 'elements':
                    if val > 0:
                        result[src].setdefault(el, []).append(val)
                else:
                    if val > 0 and not np.isnan(val):
                        result[src].setdefault(el, []).append(val)
        return {k: v for k, v in result.items() if v} or None

class BarChartSettingsDialog(QDialog):
    """Scope-aware settings dialog for the element bar chart."""

    def __init__(self, config, is_multi, sample_names, parent=None, scope='all',
                 te_available=False, available_elements=None):
        """
        Initialize bar-chart settings dialog with optional scope filtering.

        Args:
            config (dict): Current plot configuration.
            is_multi (bool): Whether data contains multiple samples.
            sample_names (list[str]): Source sample names used for display controls.
            parent (Any): Parent widget.
            scope (str): ``'format'``, ``'quantities'``, or ``'all'``.
            available_elements (list[str] | None): Canonical raw element keys
                currently available for Element Bar Chart color configuration.

        Preserved behavior:
            Existing config key semantics and rendering behavior are unchanged; this
            only controls which settings groups are shown by each bottom-button route.
        """
        super().__init__(parent)
        if scope == 'format':
            self.setWindowTitle("Element bar chart plot format settings")
        elif scope == 'quantities':
            self.setWindowTitle("Element bar chart plot quantities configuration")
        else:
            self.setWindowTitle("Element Bar Chart Settings")
        self.setMinimumWidth(460)
        self._cfg = dict(config)
        self._multi = is_multi
        self._samples = sample_names
        self._scope = scope
        self._te_available = bool(te_available)
        self._available_elements = list(available_elements or [])

        self.display_mode = None
        self.show_values = None
        self.sort_bars = None
        self.y_axis_unit = None
        self.log_y = None
        self.label_mode = None
        self.min_count = None
        self._name_edits = None
        self._order_list = None
        self.font_family = None
        self.axis_font_size = None
        self.title_font_size = None
        self.legend_font_size = None
        self.font_bold = None
        self.font_italic = None
        self.show_x_grid = None
        self.show_y_grid = None
        self.grid_alpha = None
        self.font_color_btn = None
        self.bg_color_btn = None
        self._font_color = QColor("#000000")
        self._bg_color = QColor("#FFFFFF")
        self._elem_color_btns = {}
        self._sample_color_btns = {}

        self._build_ui()

    def _build_ui(self):
        """
        Build settings controls for the selected scope.

        Scope behavior:
            - ``format``: visual/presentation controls.
            - ``quantities``: scientific/view arrangement controls.
            - ``all``: legacy combined dialog.
        """
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        if self._multi and self._scope in ('all', 'quantities'):
            g = QGroupBox("Multiple Sample Display")
            fl = QFormLayout(g)
            self.display_mode = QComboBox()
            self.display_mode.addItems(BAR_DISPLAY_MODES)
            self.display_mode.setCurrentText(
                self._cfg.get('display_mode', BAR_DISPLAY_MODES[0]))
            fl.addRow("Display Mode:", self.display_mode)
            layout.addWidget(g)

        if self._scope in ('all', 'format'):
            self._build_format_groups(layout)

        if self._scope in ('all', 'quantities'):
            g = QGroupBox("Plot Quantities")
            fl = QFormLayout(g)
            self.sort_bars = QComboBox()
            self.sort_bars.addItems(SORT_OPTIONS)
            self.sort_bars.setCurrentText(self._cfg.get('sort_bars', 'No Sorting'))
            fl.addRow("Sort Bars:", self.sort_bars)
            self.y_axis_unit = QComboBox()
            self.y_axis_unit.addItem("Particle", "count")
            self.y_axis_unit.addItem("Particle per mL", "per_ml")
            cur_unit = self._cfg.get('y_axis_unit', 'count')
            self.y_axis_unit.setCurrentIndex(1 if cur_unit == 'per_ml' else 0)
            fl.addRow("Y Axis:", self.y_axis_unit)
            if not self._te_available:
                idx = self.y_axis_unit.findData('per_ml')
                item = self.y_axis_unit.model().item(idx)
                if item is not None:
                    item.setEnabled(False)
                if cur_unit == 'per_ml':
                    self.y_axis_unit.setCurrentIndex(0)
                note = QLabel("Particle per mL requires Transport Rate calibration")
                note.setWordWrap(True)
                note.setStyleSheet("color: #6B7280; font-size: 10px;")
                fl.addRow("", note)
            self.log_y = QCheckBox()
            self.log_y.setChecked(self._cfg.get('log_y', False))
            fl.addRow("Log Y-axis:", self.log_y)
            self.min_count = QSpinBox()
            self.min_count.setRange(0, 100000)
            self.min_count.setValue(self._cfg.get('min_particle_count', 10))
            self.min_count.setSuffix(" particles")
            self.min_count.setToolTip(
                "Hide elements with fewer particles than this threshold.\n"
                "Set to 0 to show all elements.")
            fl.addRow("Min Particle Count:", self.min_count)
            layout.addWidget(g)

        if self._multi and self._scope in ('all', 'format'):
            g = QGroupBox("Sample Names")
            vl = QVBoxLayout(g)
            self._name_edits = {}
            mappings = self._cfg.get('sample_name_mappings', {})
            for sn in self._samples:
                row = QHBoxLayout()
                ne = QLineEdit(mappings.get(sn, sn))
                ne.setFixedWidth(220)
                row.addWidget(QLabel(sn[:20]))
                row.addWidget(ne)
                self._name_edits[sn] = ne
                rst = QPushButton("Reset")
                rst.setFixedWidth(50)
                rst.clicked.connect(lambda _, o=sn: self._name_edits[o].setText(o))
                row.addWidget(rst)
                row.addStretch()
                w = QWidget()
                w.setLayout(row)
                vl.addWidget(w)
            layout.addWidget(g)

        if self._multi and self._scope in ('all', 'quantities'):
            g2 = QGroupBox("Sample Display Order")
            vl2 = QVBoxLayout(g2)
            hint = QLabel("Drag or use Up/Down to set order; useful for time series.")
            hint.setStyleSheet("color: #6B7280; font-size: 10px;")
            hint.setWordWrap(True)
            vl2.addWidget(hint)
            from PySide6.QtWidgets import QAbstractItemView as _AIV
            self._order_list = QListWidget()
            self._order_list.setMaximumHeight(130)
            self._order_list.setDragDropMode(_AIV.InternalMove)
            cur_order = self._cfg.get('sample_order', [])
            ordered = [s for s in cur_order if s in self._samples]
            ordered += [s for s in self._samples if s not in ordered]
            for s in ordered:
                self._order_list.addItem(s)
            vl2.addWidget(self._order_list)
            btn_row = QHBoxLayout()
            up_btn = QPushButton("Up")
            up_btn.setFixedWidth(72)
            up_btn.clicked.connect(self._move_up)
            dn_btn = QPushButton("Down")
            dn_btn.setFixedWidth(72)
            dn_btn.clicked.connect(self._move_down)
            btn_row.addWidget(up_btn)
            btn_row.addWidget(dn_btn)
            btn_row.addStretch()
            vl2.addLayout(btn_row)
            layout.addWidget(g2)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def _build_format_groups(self, layout):
        """Build the flat Element Bar Chart format controls.

        Args:
            layout (QVBoxLayout): Target vertical layout inside the dialog's
                scroll container.

        Returns:
            None

        Preserved behavior:
            This dialog remains Element-Bar-Chart-specific and writes only
            canonical bar-chart config keys instead of mutating live first-plot
            traces through the shared tabbed Plot Settings dialog.
        """
        fmt = self._format_settings_seed()

        g = QGroupBox("Text & Labels")
        fl = QFormLayout(g)
        self.font_family = QComboBox()
        self.font_family.addItems(_get_system_font_families())
        self.font_family.setCurrentText(
            fmt.get('global_font_family', self._cfg.get('font_family', 'Times New Roman')))
        self.font_family.setMaxVisibleItems(20)
        self.axis_font_size = QSpinBox()
        self.axis_font_size.setRange(6, 72)
        self.axis_font_size.setValue(int(fmt.get('axis_font_size', self._cfg.get('font_size', 18))))
        self.title_font_size = QSpinBox()
        self.title_font_size.setRange(6, 72)
        self.title_font_size.setValue(int(fmt.get('title_font_size', self._cfg.get('font_size', 18))))
        self.legend_font_size = QSpinBox()
        self.legend_font_size.setRange(6, 72)
        self.legend_font_size.setValue(int(fmt.get('legend_font_size', self._cfg.get('font_size', 18))))
        style_row = QHBoxLayout()
        self.font_bold = QCheckBox("Bold")
        self.font_bold.setChecked(bool(fmt.get('global_bold', self._cfg.get('font_bold', False))))
        self.font_italic = QCheckBox("Italic")
        self.font_italic.setChecked(bool(fmt.get('global_italic', self._cfg.get('font_italic', False))))
        style_row.addWidget(self.font_bold)
        style_row.addWidget(self.font_italic)
        style_row.addStretch()
        self._font_color = QColor(fmt.get('font_color', self._cfg.get('font_color', '#000000')))
        self.font_color_btn = QPushButton()
        self.font_color_btn.setFixedSize(70, 24)
        self._style_swatch_button(self.font_color_btn, self._font_color)
        self.font_color_btn.clicked.connect(self._pick_font_color)
        self.show_values = QCheckBox()
        self.show_values.setChecked(self._cfg.get('show_values', True))
        self.label_mode = QComboBox()
        self.label_mode.addItems(LABEL_MODES)
        self.label_mode.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
        fl.addRow("Font Family:", self.font_family)
        fl.addRow("Axis Font Size:", self.axis_font_size)
        fl.addRow("Title Font Size:", self.title_font_size)
        fl.addRow("Legend Font Size:", self.legend_font_size)
        fl.addRow("Font Style:", style_row)
        fl.addRow("Font Color:", self.font_color_btn)
        fl.addRow("Isotope Label:", self.label_mode)
        fl.addRow("Show Values on Bars:", self.show_values)
        layout.addWidget(g)

        g = QGroupBox("Grid & Background")
        fl = QFormLayout(g)
        self._bg_color = QColor(fmt.get('bg_color', '#FFFFFF'))
        self.bg_color_btn = QPushButton()
        self.bg_color_btn.setFixedSize(70, 24)
        self._style_swatch_button(self.bg_color_btn, self._bg_color)
        self.bg_color_btn.clicked.connect(self._pick_background_color)
        self.show_x_grid = QCheckBox()
        self.show_x_grid.setChecked(bool(fmt.get('show_x_grid', self._cfg.get('show_x_grid', False))))
        self.show_y_grid = QCheckBox()
        self.show_y_grid.setChecked(bool(fmt.get('show_y_grid', self._cfg.get('show_y_grid', False))))
        self.grid_alpha = QDoubleSpinBox()
        self.grid_alpha.setRange(0.05, 1.0)
        self.grid_alpha.setDecimals(2)
        self.grid_alpha.setSingleStep(0.05)
        grid_alpha = float(fmt.get('grid_alpha', self._cfg.get('grid_alpha', 0.2)))
        if grid_alpha > 1.0:
            grid_alpha = grid_alpha / 255.0
        self.grid_alpha.setValue(max(0.05, min(1.0, grid_alpha)))
        fl.addRow("Background Color:", self.bg_color_btn)
        fl.addRow("Show X Grid:", self.show_x_grid)
        fl.addRow("Show Y Grid:", self.show_y_grid)
        fl.addRow("Grid Alpha:", self.grid_alpha)
        layout.addWidget(g)

        if self._uses_element_colors_in_format_dialog():
            g = QGroupBox("Element Colors")
            vl = QVBoxLayout(g)
            existing_colors = self._cfg.get('element_colors', {})
            for i, element in enumerate(self._available_elements):
                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                row.addWidget(QLabel(element))
                btn = QPushButton()
                btn.setFixedSize(70, 24)
                color_hex = existing_colors.get(
                    element, DEFAULT_ELEMENT_COLORS[i % len(DEFAULT_ELEMENT_COLORS)])
                btn._color = QColor(color_hex)
                self._style_swatch_button(btn, btn._color)
                btn.clicked.connect(lambda _, e=element: self._pick_element_color(e))
                row.addWidget(btn)
                row.addStretch()
                self._elem_color_btns[element] = btn
                vl.addLayout(row)
            if not self._available_elements:
                vl.addWidget(QLabel("(No elements detected yet)"))
            layout.addWidget(g)

        if self._uses_sample_colors_in_format_dialog():
            g = QGroupBox("Sample Colors")
            vl = QVBoxLayout(g)
            existing_sample_colors = self._cfg.get('sample_colors', {})
            for i, sample_name in enumerate(self._samples):
                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                row.addWidget(QLabel(sample_name[:24]))
                btn = QPushButton()
                btn.setFixedSize(70, 24)
                color_hex = existing_sample_colors.get(
                    sample_name, DEFAULT_SAMPLE_COLORS[i % len(DEFAULT_SAMPLE_COLORS)])
                btn._color = QColor(color_hex)
                self._style_swatch_button(btn, btn._color)
                btn.clicked.connect(lambda _, sn=sample_name: self._pick_sample_color(sn))
                row.addWidget(btn)
                row.addStretch()
                self._sample_color_btns[sample_name] = btn
                vl.addLayout(row)
            layout.addWidget(g)

    def _uses_element_colors_in_format_dialog(self):
        """Return whether the active bar-chart mode visibly uses element colors.

        Returns:
            bool: ``True`` when the flat format dialog should expose canonical
                ``element_colors`` because the current bar mode renders bars
                from that mapping.
        """
        if not self._multi:
            return True
        return self._cfg.get('display_mode', BAR_DISPLAY_MODES[0]) == \
            'By Sample (Element Colors)'

    def _uses_sample_colors_in_format_dialog(self):
        """Return whether the active bar-chart mode visibly uses sample colors.

        Returns:
            bool: ``True`` when the flat format dialog should expose canonical
                ``sample_colors`` because the current bar mode renders bars
                from that mapping.
        """
        return bool(self._multi) and not self._uses_element_colors_in_format_dialog()

    def _format_settings_seed(self):
        """Return the current Element Bar Chart format-settings state.

        Returns:
            dict: Normalized mapping of text/grid/background settings.

        Preserved behavior:
            Existing shared-format state stored in ``plot_format_settings`` is
            reused when present so prior title-format fixes continue to work.
        """
        settings = self._cfg.get('plot_format_settings')
        if not isinstance(settings, dict):
            settings = {}
        return settings

    @staticmethod
    def _style_swatch_button(button, color):
        """Apply a simple color-preview stylesheet to one swatch button.

        Args:
            button (QPushButton): Target swatch button.
            color (QColor): Current selected color.

        Returns:
            None
        """
        button.setStyleSheet(
            f"background-color: {color.name()}; border: 1px solid black;")

    def _pick_font_color(self):
        """Select a canonical font color for Element Bar Chart text styling."""
        from PySide6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(self._font_color, self, "Font Color")
        if color.isValid():
            self._font_color = color
            self._style_swatch_button(self.font_color_btn, color)

    def _pick_background_color(self):
        """Select the Element Bar Chart plot background color."""
        from PySide6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(self._bg_color, self, "Background Color")
        if color.isValid():
            self._bg_color = color
            self._style_swatch_button(self.bg_color_btn, color)

    def _pick_element_color(self, element):
        """Select one canonical per-element bar color.

        Args:
            element (str): Canonical raw element key to recolor.

        Returns:
            None
        """
        from PySide6.QtWidgets import QColorDialog
        button = self._elem_color_btns.get(element)
        if button is None:
            return
        color = QColorDialog.getColor(button._color, self, f"{element} Color")
        if color.isValid():
            button._color = color
            self._style_swatch_button(button, color)

    def _pick_sample_color(self, sample_name):
        """Select one canonical per-sample bar color.

        Args:
            sample_name (str): Canonical raw sample key to recolor.

        Returns:
            None
        """
        from PySide6.QtWidgets import QColorDialog
        button = self._sample_color_btns.get(sample_name)
        if button is None:
            return
        color = QColorDialog.getColor(button._color, self, f"{sample_name} Color")
        if color.isValid():
            button._color = color
            self._style_swatch_button(button, color)

    @staticmethod
    def _normalized_display_name(raw_name, edited_text):
        """Normalize one display-name edit against its canonical raw key.

        Args:
            raw_name (str): Canonical raw sample key.
            edited_text (str): User-entered visible label text.

        Returns:
            str | None: Clean display override, or ``None`` when the edit
            should fall back to the raw default display name.
        """
        clean_text = (edited_text or '').strip()
        if not clean_text or clean_text == raw_name:
            return None
        return clean_text

    def _move_up(self):
        """Move selected sample-order row up in quantities scope."""
        if self._order_list is None:
            return
        row = self._order_list.currentRow()
        if row > 0:
            item = self._order_list.takeItem(row)
            self._order_list.insertItem(row - 1, item)
            self._order_list.setCurrentRow(row - 1)

    def _move_down(self):
        """Move selected sample-order row down in quantities scope."""
        if self._order_list is None:
            return
        row = self._order_list.currentRow()
        if row < self._order_list.count() - 1:
            item = self._order_list.takeItem(row)
            self._order_list.insertItem(row + 1, item)
            self._order_list.setCurrentRow(row + 1)

    def collect(self) -> dict:
        """
        Collect settings values only for controls present in the active scope.

        Returns:
            dict: Updated config dictionary to merge into node config.

        Preserved behavior:
            Prevents scope-related missing-widget errors and preserves untouched keys.
        """
        out = dict(self._cfg)
        if self.show_values is not None:
            out['show_values'] = self.show_values.isChecked()
        if self.sort_bars is not None:
            out['sort_bars'] = self.sort_bars.currentText()
        if self.y_axis_unit is not None:
            out['y_axis_unit'] = self.y_axis_unit.currentData()
        if self.log_y is not None:
            out['log_y'] = self.log_y.isChecked()
        if self.label_mode is not None:
            out['label_mode'] = self.label_mode.currentText()
        if self.font_family is not None:
            out['font_family'] = self.font_family.currentText()
        if self.axis_font_size is not None:
            out['font_size'] = self.axis_font_size.value()
        if self.font_bold is not None:
            out['font_bold'] = self.font_bold.isChecked()
        if self.font_italic is not None:
            out['font_italic'] = self.font_italic.isChecked()
        if self.font_color_btn is not None:
            out['font_color'] = self._font_color.name()
        if self.show_x_grid is not None:
            out['show_x_grid'] = self.show_x_grid.isChecked()
        if self.show_y_grid is not None:
            out['show_y_grid'] = self.show_y_grid.isChecked()
        if self.grid_alpha is not None:
            out['grid_alpha'] = self.grid_alpha.value()
        if self.min_count is not None:
            out['min_particle_count'] = self.min_count.value()
        if self._multi and self.display_mode is not None:
            out['display_mode'] = self.display_mode.currentText()
        if self._multi and self._name_edits is not None:
            sample_name_mappings = {}
            for sample_name, name_edit in self._name_edits.items():
                normalized = self._normalized_display_name(
                    sample_name, name_edit.text())
                if normalized is not None:
                    sample_name_mappings[sample_name] = normalized
            out['sample_name_mappings'] = sample_name_mappings
        if self._multi and self._order_list is not None:
            out['sample_order'] = [
                self._order_list.item(i).text()
                for i in range(self._order_list.count())]
        if self._elem_color_btns:
            out['element_colors'] = {
                element: button._color.name()
                for element, button in self._elem_color_btns.items()}
        if self._sample_color_btns:
            out['sample_colors'] = {
                sample_name: button._color.name()
                for sample_name, button in self._sample_color_btns.items()}
        if self.font_family is not None:
            out['plot_format_settings'] = {
                'global_font_family': self.font_family.currentText(),
                'axis_font_size': self.axis_font_size.value(),
                'title_font_size': self.title_font_size.value(),
                'legend_font_size': self.legend_font_size.value(),
                'global_bold': self.font_bold.isChecked(),
                'global_italic': self.font_italic.isChecked(),
                'font_color': self._font_color.name(),
                'bg_color': self._bg_color.name(),
                'show_x_grid': self.show_x_grid.isChecked(),
                'show_y_grid': self.show_y_grid.isChecked(),
                'grid_alpha': self.grid_alpha.value(),
            }
        return out

def _prepare_values(values, data_type, log_x):
    """Filter and optionally log-transform histogram values.
    Args:
        values (Any): Array or sequence of values.
        data_type (Any): The data type.
        log_x (Any): The log x.
    Returns:
        object: Result of the operation.
    """
    if not values:
        return None
    v = np.array(values, dtype=float)
    if data_type != 'Counts':
        v = v[(v > 0) & ~np.isnan(v)]
    if len(v) == 0:
        return None
    if log_x:
        v = v[v > 0]
        if len(v) == 0:
            return None
        v = np.log10(v)
    return v


def _draw_histogram_bars(plot_item, values, cfg, color_hex, bins_n=None,
                         name='', y_scale=1.0):
    """Draw histogram bars using PyQtGraph BarGraphItem.

    Returns: (processed_values, bin_edges, counts)
    Args:
        plot_item (Any): The plot item.
        values (Any): Array or sequence of values.
        cfg (Any): The cfg.
        color_hex (Any): The color hex.
        bins_n (Any): The bins n.
        name (Any): Name string.
        y_scale (float): Multiplier applied to bin counts, used to convert raw
            counts to particles per millilitre. Defaults to 1.0.
    """
    if bins_n is None:
        bins_n = cfg.get('bins', 20)
    alpha = int(cfg.get('alpha', 0.7) * 255)
    log_y = cfg.get('log_y', False)

    counts, bin_edges = np.histogram(values, bins=bins_n)
    scaled = counts.astype(float) * y_scale
    y_plot = np.log10(scaled + 1) if log_y else scaled

    centres = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    bw = bin_edges[1] - bin_edges[0] if len(bin_edges) > 1 else 1.0

    co = QColor(color_hex)
    bar = pg.BarGraphItem(
        x=centres, height=y_plot, width=bw * 0.95,
        brush=pg.mkBrush(co.red(), co.green(), co.blue(), alpha),
        pen=pg.mkPen(color='w', width=0.5))
    if name:
        bar.opts['_trace_name'] = name
    plot_item.addItem(bar)

    return values, bin_edges, counts


def _apply_histogram_grid(plot_item, cfg):
    """Apply histogram grid visibility/alpha settings to a PlotItem.

    Args:
        plot_item: Target ``pg.PlotItem``.
        cfg (dict): Histogram config containing ``show_x_grid``,
            ``show_y_grid``, and ``grid_alpha``.

    Preserved behavior:
        Affects only plot presentation and does not alter histogram data or
        quantity semantics.
    """
    show_x = cfg.get('show_x_grid', False)
    show_y = cfg.get('show_y_grid', False)
    alpha = float(cfg.get('grid_alpha', 0.2))
    alpha = max(0.0, min(1.0, alpha))
    plot_item.showGrid(x=show_x, y=show_y, alpha=alpha)


def _add_density_curve(plot_item, values, cfg, bin_edges, total_count):
    """Add density curve overlay scaled to match count histogram.
    Args:
        plot_item (Any): The plot item.
        values (Any): Array or sequence of values.
        cfg (Any): The cfg.
        bin_edges (Any): The bin edges.
        total_count (Any): The total count.
    Returns:
        bool: ``True`` when a density curve item was added, otherwise ``False``.

    Preserved behavior:
        Curve calculations and fit choices are unchanged. The return value
        provides non-disruptive status for callers that want to surface
        availability notes.
    """
    curve_type = cfg.get('curve_type', 'Kernel Density')
    curve_color = cfg.get('curve_color', '#2C3E50')
    log_y = cfg.get('log_y', False)

    try:
        bin_width = bin_edges[1] - bin_edges[0] if len(bin_edges) > 1 else 1.0
        x_min, x_max = values.min(), values.max()
        x_range = x_max - x_min
        if x_range <= 0:
            return False
        x_curve = np.linspace(x_min - 0.1 * x_range, x_max + 0.1 * x_range, 300)

        if curve_type == 'Log-Normal Fit' and np.all(values > 0):
            shape, loc, scale = stats.lognorm.fit(values, floc=0)
            y_curve = stats.lognorm.pdf(x_curve, shape, loc, scale)
        elif curve_type == 'Normal Fit':
            mu, sigma = stats.norm.fit(values)
            y_curve = stats.norm.pdf(x_curve, mu, sigma)
        else:
            y_curve = gaussian_kde(values)(x_curve)

        y_scaled = y_curve * total_count * bin_width
        if log_y:
            y_scaled = np.log10(y_scaled + 1)
        if len(x_curve) == 0 or len(y_scaled) == 0:
            return False
        if not np.all(np.isfinite(x_curve)) or not np.all(np.isfinite(y_scaled)):
            return False

        plot_item.addItem(pg.PlotDataItem(
            x=x_curve, y=y_scaled,
            pen=pg.mkPen(color=curve_color, width=2.5)))
        return True
    except Exception as e:
        _itk_log.exception("Handled exception in _add_density_curve")
        print(f"Density curve error: {e}")
        return False


def _density_curve_status(values, cfg):
    """Classify whether density can be attempted for one histogram series.

    Args:
        values (np.ndarray | list[float]): Plot-space values for a single
            histogram series after `_prepare_values(...)` filtering.
        cfg (dict): Histogram configuration containing `show_curve`.

    Returns:
        tuple[bool, str | None]: `(can_attempt, reason)` where `reason` is
            set only for unavailable cases.

    Preserved behavior:
        This helper does not change density math; it only reports eligibility
        conditions so callers can provide truthful UI feedback.
    """
    if not cfg.get('show_curve', True):
        return False, None
    if values is None:
        return False, 'no_values'
    arr = np.asarray(values, dtype=float)
    if arr.size <= 5:
        return False, 'too_few_points'
    if not np.all(np.isfinite(arr)):
        return False, 'non_finite_values'
    if np.unique(arr).size < 2:
        return False, 'insufficient_unique_values'
    x_min, x_max = float(np.min(arr)), float(np.max(arr))
    if not np.isfinite(x_min) or not np.isfinite(x_max) or (x_max - x_min) <= 0:
        return False, 'zero_or_invalid_span'
    return True, None


def _add_median_line(plot_item, values, cfg):
    """Add median vertical line with annotation.
    Args:
        plot_item (Any): The plot item.
        values (Any): Array or sequence of values.
        cfg (Any): The cfg.
    """
    fc = get_font_config(cfg)
    median = np.median(values)

    plot_item.addItem(pg.InfiniteLine(
        pos=median, angle=90,
        pen=pg.mkPen(color='#1F2937', style=pg.QtCore.Qt.DashLine, width=1.8)))

    txt = f"median: {median:.2f}"
    ti = pg.TextItem(txt, anchor=(0, 1), color='#1F2937')
    ti.setFont(QFont(fc.get('family', 'Times New Roman'),
                      max(fc.get('size', 18) - 4, 7)))
    plot_item.addItem(ti)
    try:
        vb = plot_item.getViewBox()
        rng = vb.viewRange()
        y_top = rng[1][1] if rng[1][1] > 0 else 10
        ti.setPos(median + (rng[0][1] - rng[0][0]) * 0.01, y_top * 0.92)
    except Exception:
        _itk_log.exception("Handled exception in _add_median_line")
        ti.setPos(median, 0)


def _add_stats_text(plot_item, plot_data, cfg):
    """Add statistics text box to histogram plot.

    Args:
        plot_item (Any): The plot item.
        plot_data (Any): The plot data.
        cfg (Any): The cfg.

    Preserved behavior:
        This is informational UI only. The visible statistics box remains
        available when enabled, but it is excluded from autorange bounds so it
        cannot influence histogram data scaling.
    """
    fc = get_font_config(cfg)
    dt = cfg.get('data_type_display', 'Counts')
    sorted_data = sort_element_dict_by_mass(plot_data)

    lines = []
    for el, vals in sorted_data.items():
        if not vals:
            continue
        if dt != 'Counts':
            v = [x for x in vals if x > 0 and not np.isnan(x)]
        else:
            v = vals
        if not v:
            continue
        n = len(v)
        m = np.mean(v)
        md = np.median(v)
        if 'Mass' in dt:
            lines.append(f"{el}: n={n}, \u03bc={m:.2f} fg, med={md:.2f} fg")
        elif 'Moles' in dt:
            lines.append(f"{el}: n={n}, \u03bc={m:.4f} fmol, med={md:.4f} fmol")
        elif 'Diameter' in dt:
            lines.append(f"{el}: n={n}, \u03bc={m:.1f} nm, med={md:.1f} nm")
        else:
            lines.append(f"{el}: n={n}, \u03bc={m:.1f}, med={md:.1f}")

    if lines:
        ti = pg.TextItem(
            '\n'.join(lines), anchor=(0, 1),
            border=pg.mkPen(color='#CBD5E1', width=1),
            fill=pg.mkBrush(255, 255, 255, 220),
            color='#374151')
        ti.setFont(QFont(fc.get('family', 'Times New Roman'),
                          max(fc.get('size', 18) - 4, 7)))
        plot_item.addItem(ti, ignoreBounds=True)
        try:
            vb = plot_item.getViewBox()
            rng = vb.viewRange()
            ti.setPos(rng[0][0] + (rng[0][1] - rng[0][0]) * 0.02,
                      rng[1][1] * 0.98)
        except Exception:
            _itk_log.exception("Handled exception in _add_stats_text")
            ti.setPos(0, 0)


def _draw_single_histogram(
        plot_item, element_data, cfg, single_color=None, density_status_out=None,
        hidden_elements=None, legend_click_callback=None, y_scale=1.0, y_label=None):
    """Draw histogram for one set of element data onto a PyQtGraph PlotItem.
    Args:
        plot_item (Any): The plot item.
        element_data (Any): The element data.
        cfg (Any): The cfg.
        single_color (Any): The single color.
        density_status_out (dict | None): Optional output mapping used by child
            decomposition views to record density attempt/success per element.
        hidden_elements (set[str] | None): Raw element/isotope keys to skip at
            render time for parent histogram visibility filtering.
        legend_click_callback (Callable[[str], None] | None): Optional callback
            used to make element legend swatches clickable for visibility
            toggling in parent histogram views.
    Returns:
        object: Result of the operation.

    Preserved behavior:
        Histogram/stat calculations are unchanged. Optional density status is
        observational metadata only and does not affect rendering logic.
        When ``legend_click_callback`` is provided, legend-row clicks are bound
        to raw-key visibility toggles so parent histogram views can hide/show
        isotopes via redraw filtering.
    """
    dt = cfg.get('data_type_display', 'Counts')
    log_x = cfg.get('log_x', False)
    bins_n = cfg.get('bins', 20)
    hidden = set(hidden_elements or set())

    sorted_data = sort_element_dict_by_mass(element_data)
    is_single = len(sorted_data) == 1
    visible_count = 0

    all_vals = []
    for idx, (elem, raw_vals) in enumerate(sorted_data.items()):
        if elem in hidden:
            continue
        vals = _prepare_values(raw_vals, dt, log_x)
        if vals is None:
            continue

        visible_count += 1
        color = single_color or _get_element_color(elem, idx, cfg)
        _draw_histogram_bars(plot_item, vals, cfg, color, bins_n,
                             name=_fmt_elem(elem, cfg), y_scale=y_scale)
        all_vals.append(vals)

        if is_single:
            _, bin_edges = np.histogram(vals, bins=bins_n)
            can_attempt_density, density_reason = _density_curve_status(vals, cfg)
            density_attempted = cfg.get('show_curve', True)
            density_success = False
            if can_attempt_density:
                density_success = _add_density_curve(
                    plot_item, vals, cfg, bin_edges, len(vals) * y_scale)
                if not density_success and density_reason is None:
                    density_reason = 'curve_fit_or_kde_failure'
            if density_status_out is not None:
                density_status_out[elem] = {
                    'attempted': density_attempted,
                    'success': density_success,
                    'reason': density_reason,
                }
            if cfg.get('show_median', True):
                _add_median_line(plot_item, vals, cfg)

    if all_vals:
        pooled = np.concatenate(all_vals) if len(all_vals) > 1 else all_vals[0]
        _add_shaded_region_hist(plot_item, pooled, cfg)
        _add_stat_lines_hist(plot_item, pooled, cfg)
        _add_det_limit_v(plot_item, cfg)
    _apply_box(plot_item, cfg)

    xl, yl = _get_xy_labels(cfg)
    if y_label is not None:
        yl = y_label
    set_axis_labels(plot_item, xl, yl, cfg)

    if cfg.get('log_x', False):
        plot_item.getAxis('bottom').setLogMode(True)
    if cfg.get('log_y', False):
        plot_item.getAxis('left').setLogMode(True)

    if not cfg.get('auto_x', True):
        xn, xx = cfg.get('x_min', 0), cfg.get('x_max', 1000)
        if cfg.get('log_x', False) and xn > 0 and xx > 0:
            xn, xx = float(np.log10(xn)), float(np.log10(xx))
        plot_item.setXRange(xn, xx, padding=0)
    if not cfg.get('auto_y', True):
        plot_item.setYRange(cfg.get('y_min', 0), cfg.get('y_max', 100), padding=0)

    _apply_histogram_grid(plot_item, cfg)
    if not is_single and len(sorted_data) > 1:
        legend = pg.LegendItem(offset=(60, 10))
        legend.setParentItem(plot_item.graphicsItem())
        plot_item.legend = legend
        for idx, elem in enumerate(sorted_data.keys()):
            color = single_color or _get_element_color(elem, idx, cfg)
            co = QColor(color)
            is_hidden = elem in hidden
            alpha = 55 if is_hidden else 180
            swatch = _ClickableLegendSwatch(
                x=[0], height=[0], width=0,
                brush=pg.mkBrush(co.red(), co.green(), co.blue(), alpha),
                raw_key=elem,
                toggle_callback=legend_click_callback,
            )
            lbl = _fmt_elem(elem, cfg) + (" (hidden)" if is_hidden else "")
            legend.addItem(swatch, lbl)
            _attach_histogram_legend_toggle(
                legend,
                raw_key=elem,
                toggle_callback=legend_click_callback,
            )

    apply_font_to_pyqtgraph(plot_item, cfg)
    if y_label is not None and not cfg.get('log_y', False):
        _apply_sci_y_axis(plot_item, cfg)
    if visible_count == 0 and len(sorted_data) > 0:
        ti = pg.TextItem("No visible isotopes", anchor=(0.5, 0.5), color='#9CA3AF')
        plot_item.addItem(ti, ignoreBounds=True)
        try:
            vb = plot_item.getViewBox()
            xr, yr = vb.viewRange()
            ti.setPos((xr[0] + xr[1]) * 0.5, (yr[0] + yr[1]) * 0.5)
        except Exception:
            _itk_log.exception("Handled exception in _draw_single_histogram")
            ti.setPos(0, 0)
    return sorted_data


def _sort_elements_for_display(elements, counts, sort_option):
    """Sort elements by user preference.
    Args:
        elements (Any): The elements.
        counts (Any): The counts.
        sort_option (Any): The sort option.
    Returns:
        tuple: Result of the operation.
    """
    mass_sorted = sort_elements_by_mass(elements)
    if sort_option == 'No Sorting':
        ec = dict(zip(elements, counts))
        return mass_sorted, [ec[e] for e in mass_sorted]
    elif sort_option == 'Ascending':
        pairs = sorted(zip(elements, counts), key=lambda x: x[1])
    elif sort_option == 'Descending':
        pairs = sorted(zip(elements, counts), key=lambda x: x[1], reverse=True)
    elif sort_option == 'Alphabetical':
        pairs = sorted(zip(elements, counts), key=lambda x: element_alphabetical_key(x[0]))
    else:
        ec = dict(zip(elements, counts))
        return mass_sorted, [ec[e] for e in mass_sorted]
    el, ct = zip(*pairs) if pairs else ([], [])
    return list(el), list(ct)


def _draw_single_bar_chart(plot_item, element_counts, cfg, single_color=None,
                            show_y_label=True, y_scale=1.0, per_ml=False):
    """Draw one element bar chart and tag element-colored bars for sync hooks.
    Args:
        plot_item (Any): The plot item.
        element_counts (Any): The element counts.
        cfg (Any): The cfg.
        single_color (Any): The single color.
        show_y_label (Any): The show y label.
        y_scale (float): Multiplier converting counts to particles per mL.
        per_ml (bool): Whether values are rendered as a concentration.

    Preserved behavior:
        Scientific counts, ordering rules, and value scaling are unchanged.
        Canonical raw element metadata is attached only when element colors are
        active so shared format edits can update config and legend swatches.
    """
    log_y = cfg.get('log_y', False)
    sort_opt = cfg.get('sort_bars', 'No Sorting')
    show_vals = cfg.get('show_values', True)
    fc = get_font_config(cfg)
    min_count = cfg.get('min_particle_count', 0)

    if min_count > 0:
        element_counts = {e: c for e, c in element_counts.items()
                          if c >= min_count}

    elems = list(element_counts.keys())
    counts = [element_counts[e] * y_scale for e in elems]
    elems, counts = _sort_elements_for_display(elems, counts, sort_opt)

    original_counts = list(counts)
    if log_y:
        counts = [np.log10(c + 1) for c in counts]

    x = np.arange(len(elems), dtype=float)

    for i, (xi, elem, c) in enumerate(zip(x, elems, counts)):
        color = single_color or _get_element_color(elem, i, cfg)
        co = QColor(color)
        bar = pg.BarGraphItem(
            x=[xi], height=[c], width=0.7,
            brush=pg.mkBrush(co.red(), co.green(), co.blue(), 215),
            pen=pg.mkPen(color='w', width=0.5))
        bar.opts['_trace_name'] = _fmt_elem(elem, cfg)
        if single_color is None:
            _tag_element_color_item(bar, elem, bar.opts['_trace_name'])
        plot_item.addItem(bar)

    if show_vals:
        max_c = max(counts) if counts else 1
        for i, (xi, c, oc) in enumerate(zip(x, counts, original_counts)):
            if oc > 0:
                ti = _bar_value_textitem(oc, per_ml, anchor=(0.5, 1), color="#374151", cfg=cfg)
                ti.setFont(QFont(fc.get('family', 'Times New Roman'),
                                  max(fc.get('size', 18) - 4, 7)))
                plot_item.addItem(ti)
                ti.setPos(xi, c + max_c * 0.02)

    ax_bottom = plot_item.getAxis('bottom')
    ticks = [(float(i), _fmt_elem(e, cfg)) for i, e in enumerate(elems)]
    ax_bottom.setTicks([ticks])

    yl = 'Particles/mL' if per_ml else 'Particle Count'
    xl = 'Isotope Elements'
    set_axis_labels(plot_item, xl, yl if show_y_label else '', cfg)
    
    if log_y:
        plot_item.getAxis('left').setLogMode(True)
    _add_det_limit_h(plot_item, cfg)
    _apply_box(plot_item, cfg)
    apply_font_to_pyqtgraph(plot_item, cfg)
    if per_ml and not log_y:
        _apply_sci_y_axis(plot_item, cfg)


class ElementBarChartDisplayDialog(QDialog):
    """Full-figure bar chart dialog with controlled custom context menu."""

    def __init__(self, bar_node, parent_window=None):
        """
        Initialize the element bar chart display dialog.

        Args:
            bar_node (Any): Plot node providing config and extracted plot data.
            parent_window (Any): Parent window reference.
        """
        super().__init__(parent_window)
        self.node = bar_node
        self.parent_window = parent_window
        self._hidden_bar_samples = set()
        self.setWindowTitle("Element Particle Count Bar Chart")
        self.setMinimumSize(1000, 700)

        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _build_ui(self):
        """
        Build the PyQtGraph canvas plus standardized bottom action buttons.

        Preserved behavior:
            Plot rendering/data logic is unchanged. This only routes UI entry points
            for format settings, quantity settings, reset, and export.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.pw = EnhancedGraphicsLayoutWidget()
        self.pw.setBackground('w')
        self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pw.customContextMenuRequested.connect(self._ctx_menu)
        layout.addWidget(self.pw, stretch=1)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            "color: #6B7280; font-size: 11px; padding: 2px 8px; "
            "background: #F8FAFC; border-top: 1px solid #E2E8F0;")
        layout.addWidget(self.stats_label)

        bb = QHBoxLayout()
        bb.setContentsMargins(0, 0, 0, 0)
        btn_fmt = QPushButton("Plot format settings")
        btn_fmt.clicked.connect(self._open_plot_format_settings)
        btn_qty = QPushButton("Configure plot quantities")
        btn_qty.clicked.connect(self._open_configure_plot_quantities)
        btn_reset = QPushButton("Reset layout")
        btn_reset.setToolTip("Reset plot view ranges to default auto-range.")
        btn_reset.clicked.connect(self._reset_layout)
        btn_export = QPushButton("Export figure")
        btn_export.clicked.connect(self._export_figure)
        bb.addWidget(btn_fmt)
        bb.addWidget(btn_qty)
        bb.addWidget(btn_reset)
        bb.addWidget(btn_export)
        layout.addLayout(bb)

    def _ctx_menu(self, pos):
        """
        Show the custom bar-chart right-click menu.

        Args:
            pos (Any): Local click position within the graphics widget.

        Preserved behavior:
            Keeps lightweight visual toggles plus plot-specific quick sorting while
            delegating full configuration/export/reset to bottom buttons.
        """
        cfg = self.node.config
        menu = QMenu(self)

        tg = menu.addMenu("Quick Toggles")
        for key, label, default in [
            ('show_values', 'Show Values on Bars', True),
            ('show_box', 'Figure Box (frame)', True),
            ('show_det_limit', 'Detection Limit Line', False),
        ]:
            a = tg.addAction(label)
            a.setCheckable(True)
            a.setChecked(cfg.get(key, default))
            a.triggered.connect(lambda _, k=key: self._toggle_key(k))

        lm = menu.addMenu("Isotope Label")
        for mode in LABEL_MODES:
            a = lm.addAction(mode)
            a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set('label_mode', v))

        sort_menu = menu.addMenu("Sort Bars")
        cur_sort = cfg.get('sort_bars', 'No Sorting')
        for s in SORT_OPTIONS:
            a = sort_menu.addAction(s)
            a.setCheckable(True)
            a.setChecked(s == cur_sort)
            a.triggered.connect(lambda _, v=s: self._set('sort_bars', v))

        menu.exec(self.pw.mapToGlobal(pos))

    def _toggle_key(self, key):
        """
        Toggle a lightweight visual option from the custom context menu.

        Args:
            key (str): Config key to toggle.
        """
        self.node.config[key] = not self.node.config.get(key, False)
        self._refresh()

    def _set(self, key, value):
        """
        Set a config value from right-click quick actions.

        Args:
            key (str): Config key to update.
            value (Any): New value to set.
        """
        self.node.config[key] = value
        self._refresh()

    def _toggle_bar_sample_visibility(self, raw_sample_key):
        """Toggle one raw sample's visibility in supported multi-sample modes.

        Args:
            raw_sample_key (str): Canonical raw sample key represented by the
                clicked legend row.

        Returns:
            None

        Preserved behavior:
            This updates only render-layer visibility state for the current
            Element Bar Chart dialog. Scientific data extraction, counts, and
            grouping semantics remain unchanged.
        """
        if not raw_sample_key:
            return
        if raw_sample_key in self._hidden_bar_samples:
            self._hidden_bar_samples.remove(raw_sample_key)
        else:
            self._hidden_bar_samples.add(raw_sample_key)
        self._refresh()

    @staticmethod
    def _no_visible_samples_message():
        """Return the standard empty-state message for fully hidden samples.

        Returns:
            str: User-visible guidance shown when no samples remain visible in
                a mode that supports legend-based sample hiding.
        """
        return "No visible samples. Use the legend to show at least one sample."

    def _add_no_visible_samples_message(self, plot_item):
        """Render the standard no-visible-samples message on one plot item.

        Args:
            plot_item (Any): Target ``pg.PlotItem`` receiving the empty-state
                message.

        Returns:
            None

        Preserved behavior:
            This is informational UI only and does not change scientific data,
            bar heights, or extraction behavior.
        """
        ti = pg.TextItem(
            self._no_visible_samples_message(),
            anchor=(0.5, 0.5),
            color='#9CA3AF')
        plot_item.addItem(ti, ignoreBounds=True)
        try:
            vb = plot_item.getViewBox()
            xr, yr = vb.viewRange()
            ti.setPos((xr[0] + xr[1]) * 0.5, (yr[0] + yr[1]) * 0.5)
        except Exception:
            _itk_log.exception("Handled exception in _add_no_visible_samples_message")
            ti.setPos(0, 0)

    def _open_settings(self):
        """
        Open the legacy all-in-one settings dialog for compatibility.

        Preserved behavior:
            Existing combined route remains available internally; bottom buttons now
            use scoped settings dialogs.
        """
        dlg = BarChartSettingsDialog(
            self.node.config, _is_multi(self.node.input_data),
            _sample_names(self.node.input_data), self,
            te_available=_meta_te_available(self.node.input_data),
            available_elements=self._get_available_bar_elements())
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_plot_format_settings(self):
        """
        Open the Element-Bar-Chart-specific flat format settings dialog.

        Preserved behavior:
            Quantity/data-selection controls remain in the separate
            ``Configure plot quantities`` route. This format route writes only
            canonical Element Bar Chart appearance config and redraws the full
            chart so bars, legends, labels, and titles stay synchronized.
        """
        dlg = BarChartSettingsDialog(
            self.node.config, _is_multi(self.node.input_data),
            _sample_names(self.node.input_data), self, scope='format',
            te_available=_meta_te_available(self.node.input_data),
            available_elements=self._get_available_bar_elements())
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_configure_plot_quantities(self):
        """Open quantities-scoped bar chart settings dialog."""
        dlg = BarChartSettingsDialog(
            self.node.config, _is_multi(self.node.input_data),
            _sample_names(self.node.input_data), self, scope='quantities',
            te_available=_meta_te_available(self.node.input_data),
            available_elements=self._get_available_bar_elements())
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _get_available_bar_elements(self):
        """Return canonical raw element keys currently available to the chart.

        Returns:
            list[str]: Sorted raw element keys present in current extracted bar
            data across single-sample or multi-sample modes.

        Preserved behavior:
            This inspects already extracted plot data only. It does not change
            selection, grouping, sorting semantics, or scientific extraction.
        """
        plot_data = self.node.extract_plot_data()
        if not plot_data:
            return []
        if _is_multi(self.node.input_data):
            keys = set()
            for sample_data in plot_data.values():
                keys.update(sample_data.keys())
            return sort_elements_by_mass(list(keys))
        return sort_elements_by_mass(list(plot_data.keys()))

    def _open_plot_settings(self, title_override=None, show_apply=True):
        """
        Open the existing PlotSettingsDialog on the first available PlotItem.

        Args:
            title_override (str | None): Optional window-title override used by
                the standardized bottom ``Plot format settings`` route.
            show_apply (bool): Whether the shared PlotSettings dialog should
                expose live ``Apply``. Element bar chart format workflow passes
                ``False`` to enforce one-shot confirmation via ``OK``.

        Preserved behavior:
            Uses the same PyQtGraph formatting editor path that existed before
            right-click cleanup, but keeps it accessible via bottom buttons
            instead of context-menu entries.
        """
        if not _CUSTOM_PLOT_AVAILABLE or _PlotSettingsDialog is None:
            return
        pi = next(
            (item for item in self.pw.scene().items()
             if isinstance(item, pg.PlotItem)),
            None,
        )
        if pi is not None:
            pi._bar_group_color_sync_callback = self._sync_element_bar_group_color
            dlg = _PlotSettingsDialog(
                _PlotWidgetAdapter(self.pw, pi), self, show_apply=show_apply,
                allow_title_text=False)
            if title_override:
                try:
                    dlg.setWindowTitle(title_override)
                except Exception:
                    _itk_log.exception("Handled exception in _open_plot_settings")
                    pass
            try:
                result = dlg.exec()
                if result == QDialog.Accepted:
                    self._propagate_plot_format_text_settings(pi)
            finally:
                try:
                    delattr(pi, '_bar_group_color_sync_callback')
                except Exception:
                    _itk_log.exception("Handled exception in _open_plot_settings")
                    pass

    def _plot_items(self):
        """Return all current PyQtGraph plot items in the dialog canvas.

        Returns:
            list: Current ``pg.PlotItem`` instances in draw order.
        """
        return [
            item for item in self.pw.scene().items()
            if isinstance(item, pg.PlotItem)
        ]

    def _get_custom_title_map(self):
        """Return the mutable Element Bar Chart custom-title mapping.

        Returns:
            dict: Node-config mapping from stable plot identifiers to custom
            title text strings.
        """
        custom_titles = self.node.config.get('custom_titles')
        if not isinstance(custom_titles, dict):
            custom_titles = {}
            self.node.config['custom_titles'] = custom_titles
        return custom_titles

    def _title_key_for_combined_plot(self, mode_key):
        """Build the stable custom-title key for a combined bar-chart view.

        Args:
            mode_key (str): Stable internal mode identifier for one combined
                Element Bar Chart plot.

        Returns:
            str: Canonical config key used for custom title lookup.
        """
        return f"combined:{mode_key}"

    def _title_key_for_sample_plot(self, sample_name):
        """Build the stable custom-title key for one sample subplot.

        Args:
            sample_name (str): Canonical raw sample name represented by the
                subplot.

        Returns:
            str: Canonical config key used for custom title lookup.
        """
        return f"sample:{sample_name}"

    def _default_title_for_key(self, plot_key):
        """Return the default rendered title for one custom-title key.

        Args:
            plot_key (str): Stable custom-title identifier for a plot or
                subplot.

        Returns:
            str: Default title text when no custom override is stored.
        """
        if plot_key.startswith('sample:'):
            raw_sample_name = plot_key.split(':', 1)[1]
            return get_display_name(raw_sample_name, self.node.config)
        return ''

    def _effective_title_for_key(self, plot_key, default_title):
        """Resolve the visible title text for one plot from config state.

        Args:
            plot_key (str): Stable custom-title identifier for a plot.
            default_title (str): Fallback title when no custom text exists.

        Returns:
            str: Title text that should be rendered on the plot.
        """
        custom_title = self._get_custom_title_map().get(plot_key)
        if isinstance(custom_title, str) and custom_title.strip():
            return custom_title.strip()
        return default_title

    def _apply_title_text_to_plot(self, plot_item, title_text):
        """Apply title text while preserving current global title formatting.

        Args:
            plot_item (Any): Target ``pg.PlotItem``.
            title_text (str): Title text that should be rendered.

        Returns:
            None

        Preserved behavior:
            This does not create a second title-style system. When shared plot
            settings are active on the live plot, their current title font
            settings are reused. Otherwise the Element Bar Chart font config is
            used as the default title styling.
        """
        title_text = (title_text or '').strip()
        if not title_text:
            plot_item.setTitle('')
            return

        settings = getattr(plot_item, '_persistent_dialog_settings', {}) or {}
        apply_plot_title_style(
            plot_item,
            title_text,
            family=settings.get(
                'global_font_family',
                self.node.config.get('font_family', 'Times New Roman')),
            size=settings.get(
                'title_font_size',
                self.node.config.get('font_size', 18)),
            bold=settings.get(
                'global_bold',
                self.node.config.get('font_bold', False)),
            italic=settings.get(
                'global_italic',
                self.node.config.get('font_italic', False)),
            color=settings.get(
                'font_color',
                self.node.config.get('font_color', '#000000')),
        )

    def _propagate_plot_format_text_settings(self, source_plot_item):
        """Apply accepted plot-format text settings to every current subplot.

        Args:
            source_plot_item (Any): Plot item whose shared dialog just stored
                the accepted persistent text-format settings.

        Returns:
            None

        Preserved behavior:
            This propagates formatting only. Custom title content remains owned
            by ``custom_titles`` and each subplot keeps its own title text.
        """
        settings = getattr(source_plot_item, '_persistent_dialog_settings', None)
        if not settings:
            return
        self.node.config['plot_format_settings'] = dict(settings)
        for plot_item in self._plot_items():
            plot_item._persistent_dialog_settings = dict(settings)
            self._apply_plot_text_settings_to_plot_item(plot_item, settings)

    def _reapply_saved_plot_format_settings(self):
        """Reapply saved Element Bar Chart plot-format settings after redraw.

        Returns:
            None
        """
        settings = self.node.config.get('plot_format_settings')
        if not isinstance(settings, dict) or not settings:
            return
        bg_color = settings.get('bg_color')
        if bg_color:
            try:
                self.pw.setBackground(bg_color)
            except Exception:
                _itk_log.exception("Handled exception in _reapply_saved_plot_format_settings")
                pass
        for plot_item in self._plot_items():
            plot_item._persistent_dialog_settings = dict(settings)
            self._apply_plot_text_settings_to_plot_item(plot_item, settings)

    def _apply_plot_text_settings_to_plot_item(self, plot_item, settings):
        """Apply explicit saved-format styling to one plot item.

        Args:
            plot_item (Any): Target ``pg.PlotItem``.
            settings (dict): Saved Element Bar Chart format state from
                ``plot_format_settings`` / ``persistent_dialog_settings``.

        Returns:
            None

        Preserved behavior:
            Custom title text remains independent. This applies only appearance
            settings such as text styling and grid visibility/alpha.
        """
        axis_labels = {}
        custom_axis_labels = getattr(plot_item, '_custom_axis_labels', {}) or {}
        for axis_name in ('bottom', 'left'):
            axis = plot_item.getAxis(axis_name)
            info = custom_axis_labels.get(axis_name, {})
            axis_labels[axis_name] = {
                'text': info.get('text', getattr(axis, 'labelText', '') or ''),
                'units': info.get(
                    'units', getattr(axis, 'labelUnits', None) or None),
            }

        title_label = getattr(plot_item, 'titleLabel', None)
        title_text = (
            title_label.text.strip()
            if title_label and getattr(title_label, 'text', '')
            else ''
        )
        apply_plot_item_text_styling(
            plot_item,
            family=settings.get(
                'global_font_family',
                self.node.config.get('font_family', 'Times New Roman')),
            title_size=settings.get(
                'title_font_size',
                self.node.config.get('font_size', 18)),
            axis_size=settings.get(
                'axis_font_size',
                self.node.config.get('font_size', 18)),
            legend_size=settings.get(
                'legend_font_size',
                self.node.config.get('font_size', 18)),
            bold=settings.get(
                'global_bold',
                self.node.config.get('font_bold', False)),
            italic=settings.get(
                'global_italic',
                self.node.config.get('font_italic', False)),
            color=settings.get(
                'font_color',
                self.node.config.get('font_color', '#000000')),
            title_text=title_text,
            axis_labels=axis_labels,
        )
        show_x_grid = bool(settings.get('show_x_grid', False))
        show_y_grid = bool(settings.get('show_y_grid', False))
        grid_alpha = float(settings.get('grid_alpha', self.node.config.get('grid_alpha', 0.2)))
        if grid_alpha > 1.0:
            grid_alpha = grid_alpha / 255.0
        grid_alpha = max(0.0, min(1.0, grid_alpha))
        plot_item.showGrid(x=show_x_grid, y=show_y_grid, alpha=grid_alpha)

    def _store_custom_title_text(self, plot_key, title_text):
        """Persist one custom title text value into Element Bar Chart config.

        Args:
            plot_key (str): Stable custom-title identifier for a plot.
            title_text (str): User-entered title text. Blank text removes the
                custom override and restores default title behavior.

        Returns:
            None
        """
        custom_titles = dict(self._get_custom_title_map())
        clean_text = (title_text or '').strip()
        if clean_text:
            custom_titles[plot_key] = clean_text
        else:
            custom_titles.pop(plot_key, None)
        self.node.config['custom_titles'] = custom_titles

    def _apply_custom_title_edit(self, plot_item, plot_key, title_text):
        """Update live plot title text and persist it in node config.

        Args:
            plot_item (Any): Target ``pg.PlotItem`` being edited.
            plot_key (str): Stable custom-title identifier for that plot.
            title_text (str): User-entered title text.

        Returns:
            None
        """
        self._store_custom_title_text(plot_key, title_text)
        effective_title = self._effective_title_for_key(
            plot_key, self._default_title_for_key(plot_key))
        self._apply_title_text_to_plot(plot_item, effective_title)

    def _configure_plot_title(self, plot_item, plot_key, default_title=''):
        """Bind Element Bar Chart title behavior to one freshly drawn plot.

        Args:
            plot_item (Any): Freshly created ``pg.PlotItem``.
            plot_key (str): Stable custom-title identifier for that plot.
            default_title (str): Default title text for the plot when no custom
                override exists.

        Returns:
            None
        """
        plot_item._title_editor_options = {
            'text_only': True,
            'title_apply_callback': (
                lambda text, _plot_item=plot_item, _plot_key=plot_key:
                self._apply_custom_title_edit(_plot_item, _plot_key, text)
            ),
        }
        self._apply_title_text_to_plot(
            plot_item, self._effective_title_for_key(plot_key, default_title))

    def _sync_element_bar_group_color(self, items, color_hex):
        """Persist shared bar-color edits into canonical element config state.

        Args:
            items (list[pg.BarGraphItem]): Edited bar items from the Plot
                Settings dialog.
            color_hex (str): Selected color for the edited element group.

        Returns:
            None

        Preserved behavior:
            Only presentation-layer color config is updated. Element keys remain
            canonical raw identifiers and no scientific data is recalculated.
        """
        if not items:
            return
        raw_keys = {
            getattr(item, '_raw_element_key', None)
            for item in items
            if getattr(item, '_color_identity_role', None) == 'element'
        }
        raw_keys.discard(None)
        if not raw_keys:
            return

        element_colors = dict(self.node.config.get('element_colors', {}))
        for raw_key in raw_keys:
            element_colors[raw_key] = color_hex
        self.node.config['element_colors'] = element_colors
        self._update_element_legend_swatches(raw_keys, color_hex)

    def _update_element_legend_swatches(self, raw_keys, color_hex):
        """Refresh live legend swatches for element-colored bar-chart entries.

        Args:
            raw_keys (set[str]): Canonical raw element keys whose legend
                swatches should be recolored.
            color_hex (str): Selected color for those legend entries.

        Returns:
            None
        """
        plot_item = next(
            (item for item in self.pw.scene().items() if isinstance(item, pg.PlotItem)),
            None,
        )
        if plot_item is None:
            return
        legend = getattr(plot_item, 'legend', None)
        if legend is None:
            return

        color = QColor(color_hex)
        brush = pg.mkBrush(color.red(), color.green(), color.blue(), 215)
        for sample_item, _label_item in getattr(legend, 'items', []):
            swatch_item = _get_legend_sample_graphics_item(sample_item)
            if getattr(swatch_item, '_color_identity_role', None) != 'element':
                continue
            if getattr(swatch_item, '_raw_element_key', None) not in raw_keys:
                continue
            try:
                swatch_item.setOpts(brush=brush)
                swatch_item.update()
            except Exception:
                _itk_log.exception("Handled exception in _update_element_legend_swatches")
                pass

    def _download_figure(self):
        """Export bar chart as image or CSV via existing PyQtGraph export path."""
        import pandas as pd
        csv_df = None
        try:
            plot_data = self.node.extract_plot_data()
            cfg = self.node.config
            active_mode = cfg.get('display_mode', BAR_DISPLAY_MODES[0])
            hidden_samples = (
                set(self._hidden_bar_samples)
                if active_mode in ('Grouped Bars', 'Stacked Bars')
                else set()
            )

            if plot_data:
                rows = []
                if _is_multi(self.node.input_data):
                    for sn, sd in plot_data.items():
                        if sn in hidden_samples:
                            continue
                        dname = get_display_name(sn, cfg)
                        for elem, count in sd.items():
                            rows.append({'Sample': dname, 'Element': elem, 'Particle Count': count})
                else:
                    for elem, count in plot_data.items():
                        rows.append({'Element': elem, 'Particle Count': count})
                if rows:
                    csv_df = pd.DataFrame(rows)
        except Exception as e:
            _itk_log.exception("Handled exception in _download_figure")
            print(f"Warning: could not build CSV data: {e}")

        download_pyqtgraph_figure(
            self.pw, self,
            default_name='bar_chart',
            csv_data=csv_df,
        )

    def _export_figure(self):
        """Route standardized export button to existing bar-chart export path."""
        self._download_figure()

    def _disable_native_pyqtgraph_context_menu(self):
        """
        Disable native PyQtGraph plot/view menus for this dialog only.

        Preserved behavior:
            This does not alter PyQtGraph globally or in other plots; it only
            suppresses stacked native menus in this bar-chart dialog.
        """
        for item in self.pw.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    item.setMenuEnabled(False)
                except Exception:
                    _itk_log.exception("Handled exception in _disable_native_pyqtgraph_context_menu")
                    pass
                try:
                    vb = item.getViewBox()
                    if vb is not None:
                        vb.setMenuEnabled(False)
                except Exception:
                    _itk_log.exception("Handled exception in _disable_native_pyqtgraph_context_menu")
                    pass

    def _reset_layout(self):
        """
        Reset current PyQtGraph view ranges to auto-range without changing data.

        Preserved behavior:
            Sorting and quantity configuration are left unchanged.
        """
        for item in self.pw.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    item.enableAutoRange(axis='xy', enable=True)
                    vb = item.getViewBox()
                    if vb is not None:
                        vb.autoRange()
                except Exception:
                    _itk_log.exception("Handled exception in _reset_layout")
                    pass
    # ── Refresh ─────────────────────────────

    def _refresh(self):
        """Rebuild the Element Bar Chart canvas from node config and data.

        Returns:
            None

        Preserved behavior:
            Scientific/data extraction and display-mode logic remain unchanged.
            Custom title text is reapplied during every rebuild using stable
            plot identifiers stored in node config.
        """
        try:
            parent_layout = self.pw.parent().layout()
            idx = parent_layout.indexOf(self.pw)
            parent_layout.removeWidget(self.pw)
            self.pw.deleteLater()
            self.pw = EnhancedGraphicsLayoutWidget()
            self.pw.setBackground('w')
            self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
            self.pw.customContextMenuRequested.connect(self._ctx_menu)
            parent_layout.insertWidget(idx, self.pw, stretch=1)

            plot_data = self.node.extract_plot_data()
            cfg = self.node.config

            if not plot_data:
                pi = self.pw.addPlot(axisItems={'left': HtmlAxisItem('left')})
                t = pg.TextItem(
                    "No particle data available\n"
                    "Connect to Sample Selector\nand run particle detection",
                    anchor=(0.5, 0.5), color='gray')
                pi.addItem(t)
                t.setPos(0.5, 0.5)
                pi.hideAxis('left')
                pi.hideAxis('bottom')
                self.stats_label.setText("")
                return

            if _is_multi(self.node.input_data):
                mode = cfg.get('display_mode', BAR_DISPLAY_MODES[0])
                if mode == 'Individual Subplots':
                    self._draw_subplots(plot_data, cfg)
                elif mode == 'Side by Side Subplots':
                    self._draw_side_by_side(plot_data, cfg)
                elif mode == 'Stacked Bars':
                    self._draw_stacked(plot_data, cfg)
                elif mode == 'By Sample (Element Colors)':
                    self._draw_by_sample(plot_data, cfg)
                else:
                    self._draw_grouped(plot_data, cfg)
            else:
                pi = self.pw.addPlot(axisItems={'bottom': HtmlAxisItem('bottom'), 'left': HtmlAxisItem('left')})
                per_ml = _per_ml_active(cfg, self.node.input_data)
                sn = self.node.input_data.get('sample_name') if self.node.input_data else None
                y_scale = _pml_factor(self.node.input_data, sn) if per_ml else 1.0
                _draw_single_bar_chart(pi, plot_data, cfg, y_scale=y_scale, per_ml=per_ml)
                self._configure_plot_title(
                    pi, self._title_key_for_combined_plot('single'))

            self._reapply_saved_plot_format_settings()
            self._disable_native_pyqtgraph_context_menu()
            self._update_stats(plot_data)

        except Exception as e:
            _itk_log.exception("Handled exception in _refresh")
            print(f"Error updating bar chart: {e}")
            import traceback
            traceback.print_exc()

    def _draw_subplots(self, plot_data, cfg):
        """Draw one titled subplot per sample and reapply custom title text.

        Args:
            plot_data (Any): Multi-sample element-count data keyed by raw
                sample name.
            cfg (Any): Element Bar Chart config snapshot.
        """
        samples = list(plot_data.keys())
        n = len(samples)
        cols = min(2, n)
        per_ml = _per_ml_active(cfg, self.node.input_data)
        for idx, sn in enumerate(samples):
            if idx > 0 and idx % cols == 0:
                self.pw.nextRow()
            pi = self.pw.addPlot(title=get_display_name(sn, cfg),
                                  axisItems={'bottom': HtmlAxisItem('bottom'), 'left': HtmlAxisItem('left')})
            sd = plot_data[sn]
            if sd:
                color = get_sample_color(sn, idx, cfg)
                y_scale = _pml_factor(self.node.input_data, sn) if per_ml else 1.0
                _draw_single_bar_chart(pi, sd, cfg, single_color=color,
                                        y_scale=y_scale, per_ml=per_ml)
            self._configure_plot_title(
                pi, self._title_key_for_sample_plot(sn),
                default_title=get_display_name(sn, cfg))

    def _draw_side_by_side(self, plot_data, cfg):
        """Draw horizontal sample subplots and reapply custom title text.

        Args:
            plot_data (Any): Multi-sample element-count data keyed by raw
                sample name.
            cfg (Any): Element Bar Chart config snapshot.
        """
        samples = list(plot_data.keys())
        per_ml = _per_ml_active(cfg, self.node.input_data)
        for idx, sn in enumerate(samples):
            pi = self.pw.addPlot(title=get_display_name(sn, cfg),
                                  axisItems={'bottom': HtmlAxisItem('bottom'), 'left': HtmlAxisItem('left')})
            sd = plot_data[sn]
            if sd:
                color = get_sample_color(sn, idx, cfg)
                y_scale = _pml_factor(self.node.input_data, sn) if per_ml else 1.0
                _draw_single_bar_chart(pi, sd, cfg, single_color=color,
                                        show_y_label=(idx == 0),
                                        y_scale=y_scale, per_ml=per_ml)
            self._configure_plot_title(
                pi, self._title_key_for_sample_plot(sn),
                default_title=get_display_name(sn, cfg))

    def _draw_grouped(self, plot_data, cfg):
        """Draw the combined grouped-bars multi-sample view.

        Args:
            plot_data (Any): Multi-sample element-count data.
            cfg (Any): Element Bar Chart config snapshot.
        """
        pi = self.pw.addPlot(axisItems={'bottom': HtmlAxisItem('bottom'), 'left': HtmlAxisItem('left')})
        fc = get_font_config(cfg)
        log_y = cfg.get('log_y', False)
        show_vals = cfg.get('show_values', True)
        sort_opt = cfg.get('sort_bars', 'No Sorting')
        per_ml = _per_ml_active(cfg, self.node.input_data)

        all_elems = set()
        for sd in plot_data.values():
            all_elems.update(sd.keys())
        all_elems = sort_elements_by_mass(list(all_elems))

        min_count = cfg.get('min_particle_count', 0)
        if min_count > 0:
            all_elems = [e for e in all_elems
                        if sum(sd.get(e, 0) for sd in plot_data.values()) >= min_count]

        if sort_opt != 'No Sorting':
            totals = [(e, sum(plot_data[s].get(e, 0) for s in plot_data))
                      for e in all_elems]
            if sort_opt == 'Ascending':
                totals.sort(key=lambda x: x[1])
            elif sort_opt == 'Descending':
                totals.sort(key=lambda x: x[1], reverse=True)
            elif sort_opt == 'Alphabetical':
                totals.sort(key=lambda x: element_alphabetical_key(x[0]))
            all_elems = [e for e, _ in totals]

        x = np.arange(len(all_elems), dtype=float)
        visible_samples = [
            sample_name for sample_name in plot_data
            if sample_name not in self._hidden_bar_samples
        ]
        n_visible_samples = len(visible_samples)
        bar_w = 0.8 / max(n_visible_samples, 1)

        legend = pg.LegendItem(offset=(60, 10))
        legend.setParentItem(pi.graphicsItem())
        pi.legend = legend

        global_max = 0
        visible_index = 0
        for i, (sn, sd) in enumerate(plot_data.items()):
            sample_hidden = sn in self._hidden_bar_samples
            color = get_sample_color(sn, i, cfg)
            dname = get_display_name(sn, cfg)
            co = QColor(color)
            alpha = 55 if sample_hidden else 215
            swatch = _ClickableLegendSwatch(
                x=[0], height=[0], width=0,
                brush=pg.mkBrush(co.red(), co.green(), co.blue(), alpha),
                raw_key=sn,
                toggle_callback=self._toggle_bar_sample_visibility,
            )
            legend_label = dname + (" (hidden)" if sample_hidden else "")
            legend.addItem(swatch, legend_label)
            _attach_bar_chart_legend_toggle(
                legend,
                raw_key=sn,
                toggle_callback=self._toggle_bar_sample_visibility,
            )

            if sample_hidden:
                continue

            y_scale = _pml_factor(self.node.input_data, sn) if per_ml else 1.0
            heights = [sd.get(e, 0) * y_scale for e in all_elems]
            orig = list(heights)
            if log_y:
                heights = [np.log10(h + 1) for h in heights]
            cur_max = max(heights) if heights else 0
            if cur_max > global_max:
                global_max = cur_max

            offsets = x + (visible_index - n_visible_samples / 2 + 0.5) * bar_w
            visible_index += 1
            bar = pg.BarGraphItem(
                x=offsets, height=heights, width=bar_w,
                brush=pg.mkBrush(co.red(), co.green(), co.blue(), 215),
                pen=pg.mkPen(color='w', width=0.5))
            bar.opts['_trace_name'] = dname
            pi.addItem(bar)

            if show_vals:
                for j, (xp, h, o) in enumerate(zip(offsets, heights, orig)):
                    if o > 0:
                        ti = _bar_value_textitem(o, per_ml, anchor=(0.5, 1), color="#374151", cfg=cfg)
                        ti.setFont(QFont(fc.get('family', 'Times New Roman'),
                                          max(fc.get('size', 18) - 5, 6)))
                        pi.addItem(ti)
                        ti.setPos(xp, h + global_max * 0.02)

        ax_bottom = pi.getAxis('bottom')
        ticks = [(float(i), _fmt_elem(e, cfg)) for i, e in enumerate(all_elems)]
        ax_bottom.setTicks([ticks])

        yl = 'Particles/mL' if per_ml else 'Particle Count'
        set_axis_labels(pi, 'Isotope Elements', yl, cfg)
        if not visible_samples:
            self._add_no_visible_samples_message(pi)
        
        if log_y:
            pi.getAxis('left').setLogMode(True)        
        apply_font_to_pyqtgraph(pi, cfg)
        if per_ml and not log_y:
            _apply_sci_y_axis(pi, cfg)
        self._configure_plot_title(
            pi, self._title_key_for_combined_plot('grouped'))

    def _draw_stacked(self, plot_data, cfg):
        """Draw the combined stacked-bars multi-sample view.

        Args:
            plot_data (Any): Multi-sample element-count data.
            cfg (Any): Element Bar Chart config snapshot.
        """
        pi = self.pw.addPlot(axisItems={'bottom': HtmlAxisItem('bottom'), 'left': HtmlAxisItem('left')})
        fc = get_font_config(cfg)
        log_y = cfg.get('log_y', False)
        sort_opt = cfg.get('sort_bars', 'No Sorting')

        all_elems = set()
        for sd in plot_data.values():
            all_elems.update(sd.keys())
        all_elems = sort_elements_by_mass(list(all_elems))

        min_count = cfg.get('min_particle_count', 0)
        if min_count > 0:
            all_elems = [e for e in all_elems
                        if sum(sd.get(e, 0) for sd in plot_data.values()) >= min_count]

        if sort_opt != 'No Sorting':
            totals = [(e, sum(plot_data[s].get(e, 0) for s in plot_data))
                      for e in all_elems]
            if sort_opt == 'Ascending':
                totals.sort(key=lambda x: x[1])
            elif sort_opt == 'Descending':
                totals.sort(key=lambda x: x[1], reverse=True)
            elif sort_opt == 'Alphabetical':
                totals.sort(key=lambda x: element_alphabetical_key(x[0]))
            all_elems = [e for e, _ in totals]

        x = np.arange(len(all_elems), dtype=float)
        bottom = np.zeros(len(all_elems))
        per_ml = _per_ml_active(cfg, self.node.input_data)
        visible_samples = [
            sample_name for sample_name in plot_data
            if sample_name not in self._hidden_bar_samples
        ]

        legend = pg.LegendItem(offset=(60, 10))
        legend.setParentItem(pi.graphicsItem())
        pi.legend = legend

        for i, (sn, sd) in enumerate(plot_data.items()):
            sample_hidden = sn in self._hidden_bar_samples
            color = get_sample_color(sn, i, cfg)
            dname = get_display_name(sn, cfg)
            co = QColor(color)
            alpha = 55 if sample_hidden else 215
            swatch = _ClickableLegendSwatch(
                x=[0], height=[0], width=0,
                brush=pg.mkBrush(co.red(), co.green(), co.blue(), alpha),
                raw_key=sn,
                toggle_callback=self._toggle_bar_sample_visibility,
            )
            legend_label = dname + (" (hidden)" if sample_hidden else "")
            legend.addItem(swatch, legend_label)
            _attach_bar_chart_legend_toggle(
                legend,
                raw_key=sn,
                toggle_callback=self._toggle_bar_sample_visibility,
            )

            if sample_hidden:
                continue

            y_scale = _pml_factor(self.node.input_data, sn) if per_ml else 1.0
            heights = np.array([sd.get(e, 0) * y_scale for e in all_elems], dtype=float)

            if log_y:
                top = bottom + heights
                h_plot = np.log10(top + 1) - np.log10(bottom + 1)
                b_plot = np.log10(bottom + 1)
            else:
                h_plot = heights
                b_plot = bottom

            for j in range(len(x)):
                bar = pg.BarGraphItem(
                    x=[x[j]], height=[h_plot[j]], width=0.7,
                    brush=pg.mkBrush(co.red(), co.green(), co.blue(), 215),
                    pen=pg.mkPen(color='w', width=0.5))
                bar.opts['_trace_name'] = dname
                bar.setPos(0, b_plot[j])
                pi.addItem(bar)

            bottom += heights

        ax_bottom = pi.getAxis('bottom')
        ticks = [(float(i), _fmt_elem(e, cfg)) for i, e in enumerate(all_elems)]
        ax_bottom.setTicks([ticks])

        yl = 'Particles/mL' if per_ml else 'Particle Count'
        set_axis_labels(pi, 'Isotope Elements', yl, cfg)
        if not visible_samples:
            self._add_no_visible_samples_message(pi)
        
        if log_y:
            pi.getAxis('left').setLogMode(True)        
        apply_font_to_pyqtgraph(pi, cfg)
        if per_ml and not log_y:
            _apply_sci_y_axis(pi, cfg)
        self._configure_plot_title(
            pi, self._title_key_for_combined_plot('stacked'))

    def _draw_by_sample(self, plot_data, cfg):
        """Draw the multi-sample element-colored grouped bar chart view.

        X-axis = samples, one bar per element per sample, colors = elements.
        Respects sample_order for time-series use.
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.

        Preserved behavior:
            Element ordering, counts, particles-per-mL scaling, and label
            rendering are unchanged. Live bars and draggable legend swatches are
            tagged with the same raw element key so color edits stay synced.
        """
        pi = self.pw.addPlot(axisItems={'bottom': HtmlAxisItem('bottom'), 'left': HtmlAxisItem('left')})
        fc = get_font_config(cfg)
        log_y = cfg.get('log_y', False)
        show_vals = cfg.get('show_values', True)
        sort_opt = cfg.get('sort_bars', 'No Sorting')
        min_count = cfg.get('min_particle_count', 0)

        sample_order = cfg.get('sample_order', [])
        if sample_order:
            samples = [s for s in sample_order if s in plot_data]
            samples += [s for s in plot_data if s not in samples]
        else:
            samples = list(plot_data.keys())

        all_elems_set = set()
        for sd in plot_data.values():
            all_elems_set.update(sd.keys())
        if min_count > 0:
            all_elems_set = {
                e for e in all_elems_set
                if sum(plot_data[s].get(e, 0) for s in samples) >= min_count}
        all_elems = sort_elements_by_mass(list(all_elems_set))

        if sort_opt != 'No Sorting' and samples:
            totals = [(e, sum(plot_data[s].get(e, 0) for s in samples))
                      for e in all_elems]
            if sort_opt == 'Ascending':
                totals.sort(key=lambda x: x[1])
            elif sort_opt == 'Descending':
                totals.sort(key=lambda x: x[1], reverse=True)
            elif sort_opt == 'Alphabetical':
                totals.sort(key=lambda x: element_alphabetical_key(x[0]))
            all_elems = [e for e, _ in totals]

        x = np.arange(len(samples), dtype=float)
        n_elems = max(len(all_elems), 1)
        bar_w = 0.8 / n_elems

        legend = pg.LegendItem(offset=(60, 10))
        legend.setParentItem(pi.graphicsItem())
        pi.legend = legend

        global_max = 0.0
        per_ml = _per_ml_active(cfg, self.node.input_data)
        for j, elem in enumerate(all_elems):
            color = _get_element_color(elem, j, cfg)
            label = _fmt_elem(elem, cfg)
            heights = [plot_data[s].get(elem, 0) *
                       (_pml_factor(self.node.input_data, s) if per_ml else 1.0)
                       for s in samples]
            orig = list(heights)
            if log_y:
                heights = [np.log10(h + 1) for h in heights]
            cur_max = max(heights) if heights else 0.0
            if cur_max > global_max:
                global_max = cur_max

            offsets = x + (j - n_elems / 2 + 0.5) * bar_w
            co = QColor(color)
            bar = pg.BarGraphItem(
                x=offsets, height=heights, width=bar_w,
                brush=pg.mkBrush(co.red(), co.green(), co.blue(), 215),
                pen=pg.mkPen(color='w', width=0.5))
            bar.opts['_trace_name'] = label
            _tag_element_color_item(bar, elem, label)
            pi.addItem(bar)

            swatch = pg.BarGraphItem(x=[0], height=[0], width=0,
                                     brush=pg.mkBrush(co.red(), co.green(), co.blue(), 215))
            _tag_element_color_item(swatch, elem, label)
            legend.addItem(swatch, label)

            if show_vals:
                for xp, h, o in zip(offsets, heights, orig):
                    if o > 0:
                        ti = _bar_value_textitem(o, per_ml, anchor=(0.5, 1),
                                                 color='#374151', cfg=cfg)
                        ti.setFont(QFont(fc.get('family', 'Times New Roman'),
                                         max(fc.get('size', 18) - 5, 6)))
                        pi.addItem(ti)
                        ti.setPos(xp, h + global_max * 0.02)

        ax_bottom = pi.getAxis('bottom')
        ticks = [(float(i), get_display_name(s, cfg))
                 for i, s in enumerate(samples)]
        ax_bottom.setTicks([ticks])

        set_axis_labels(pi, 'Sample', 'Particles/mL' if per_ml else 'Particle Count', cfg)
        if log_y:
            pi.getAxis('left').setLogMode(True)
        apply_font_to_pyqtgraph(pi, cfg)
        if per_ml and not log_y:
            _apply_sci_y_axis(pi, cfg)
        self._configure_plot_title(
            pi, self._title_key_for_combined_plot('by_sample'))

    def _update_stats(self, plot_data):
        """
        Args:
            plot_data (Any): The plot data.
        """
        if _is_multi(self.node.input_data):
            total = sum(sum(v for v in sd.values()) for sd in plot_data.values())
            self.stats_label.setText(
                f"{len(plot_data)} samples  \u00b7  {total:,} total particles")
        else:
            total = sum(plot_data.values())
            self.stats_label.setText(
                f"{len(plot_data)} elements  \u00b7  {total:,} total particles")


class ElementBarChartPlotNode(QObject):
    """Element particle-count bar chart node with right-click context menu."""

    position_changed = Signal(object)
    configuration_changed = Signal()

    DEFAULT_CONFIG = {
        'show_values': True,
        'sort_bars': 'No Sorting',
        'y_axis_unit': 'count',
        'log_x': False,
        'log_y': False,
        'show_box': True,
        'show_det_limit': False,
        'det_limit_value': 1.0,
        'det_limit_color': '#DC2626',
        'det_limit_style': 'dash',
        'det_limit_width': 2,
        'det_limit_label': '',
        'element_colors': {},
        'display_mode': 'Grouped Bars (Side by Side)',
        'sample_colors': {},
        'sample_name_mappings': {},
        'sample_order': [],
        'custom_titles': {},
        'plot_format_settings': {},
        'font_family': 'Times New Roman',
        'font_size': 18,
        'font_bold': False,
        'font_italic': False,
        'font_color': '#000000',
        'label_mode': 'Symbol',
        'min_particle_count': 10,
    }

    def __init__(self, parent_window=None):
        """
        Args:
            parent_window (Any): The parent window.
        """
        super().__init__()
        self.title = "Element Bar Chart"
        self.node_type = "element_bar_chart_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        self.config = dict(self.DEFAULT_CONFIG)
        self.input_data = None
        self.plot_widget = None

    def set_position(self, pos):
        """
        Args:
            pos (Any): Position point.
        """
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        """
        Args:
            parent_window (Any): The parent window.
        Returns:
            bool: Result of the operation.
        """
        dlg = ElementBarChartDisplayDialog(self, parent_window)
        dlg.exec()
        return True

    def process_data(self, input_data):
        """
        Args:
            input_data (Any): The input data.
        """
        if not input_data:
            return
        self.input_data = input_data
        self.configuration_changed.emit()

    def extract_plot_data(self):
        """Extract element particle counts from input.
        Returns:
            None
        """
        if not self.input_data:
            return None

        itype = self.input_data.get('type')

        if itype == 'sample_data':
            particles = self.input_data.get('particle_data')
            if not particles:
                return None
            counts = {}
            for p in particles:
                for el, val in p.get('elements', {}).items():
                    if val > 0:
                        counts[el] = counts.get(el, 0) + 1
            return counts or None

        elif itype == 'multiple_sample_data':
            particles = self.input_data.get('particle_data', [])
            names = self.input_data.get('sample_names', [])
            if not particles:
                return None
            result = {sn: {} for sn in names}
            for p in particles:
                src = p.get('source_sample')
                if src not in result:
                    continue
                for el, val in p.get('elements', {}).items():
                    if val > 0:
                        result[src][el] = result[src].get(el, 0) + 1
            return {k: v for k, v in result.items() if v} or None

        return None
