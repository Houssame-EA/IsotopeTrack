"""
Distribution Plot Node – Box / Violin / Strip / Bar-with-errors.

Keeps **PyQtGraph** for interactive zoom/pan.
Sidebar replaced by **right-click context menu** + settings dialog.
Uses shared_plot_utils for fonts, colors, sample helpers, and download.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QColorDialog,
    QPushButton, QLineEdit, QFrame, QScrollArea, QWidget, QMenu,
    QDialogButtonBox, QMessageBox, QFileDialog,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QPen, QFont, QAction
import pyqtgraph as pg
import numpy as np
import math
from scipy.stats import gaussian_kde

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS,
    get_font_config, make_qfont, apply_font_to_pyqtgraph, set_axis_labels,
    FontSettingsGroup, get_sample_color, get_display_name,
    download_pyqtgraph_figure,
)
from results.utils_sort import sort_elements_by_mass, sort_element_dict_by_mass

# ── Constants ──────────────────────────────────────────────────────────

PLOT_SHAPES = [
    'Box Plot (Traditional)',
    'Violin Plot',
    'Box + Violin (Overlay)',
    'Strip Plot (Dots)',
    'Half Violin + Half Box',
    'Notched Box Plot',
    'Bar Plot with Error Bars',
]

BOX_DATA_TYPES = [
    'Counts',
    'Element Mass (fg)',
    'Particle Mass (fg)',
    'Element Moles (fmol)',
    'Particle Moles (fmol)',
    'Element Diameter (nm)',
    'Particle Diameter (nm)',
]

BOX_DATA_KEY_MAP = {
    'Counts': 'elements',
    'Element Mass (fg)': 'element_mass_fg',
    'Particle Mass (fg)': 'particle_mass_fg',
    'Element Moles (fmol)': 'element_moles_fmol',
    'Particle Moles (fmol)': 'particle_moles_fmol',
    'Element Diameter (nm)': 'element_diameter_nm',
    'Particle Diameter (nm)': 'particle_diameter_nm',
}

BOX_LABEL_MAP = {
    'Counts': 'Intensity (counts)',
    'Element Mass (fg)': 'Element Mass (fg)',
    'Particle Mass (fg)': 'Particle Mass (fg)',
    'Element Moles (fmol)': 'Element Moles (fmol)',
    'Particle Moles (fmol)': 'Particle Moles (fmol)',
    'Element Diameter (nm)': 'Element Diameter (nm)',
    'Particle Diameter (nm)': 'Particle Diameter (nm)',
}

BOX_DISPLAY_MODES = ['Side by Side', 'Individual Subplots', 'Grouped by Element']

DEFAULT_ELEMENT_COLORS = [
    '#663399', '#2E86AB', '#A23B72', '#F18F01', '#C73E1D',
    '#7209B7', '#F72585', '#4361EE', '#277DA1', '#F8961E',
]

DEFAULT_CONFIG = {
    'data_type_display': 'Counts',
    'plot_shape': 'Box Plot (Traditional)',
    'violin_bandwidth': 0.2,
    'strip_jitter': 0.2,
    'show_outliers': True,
    'show_mean': True,
    'show_median': True,
    'alpha': 0.7,
    'log_y': False,
    'show_stats': True,
    'plot_width': 0.8,
    'y_min': 0,
    'y_max': 100,
    'auto_y': True,
    'element_colors': {},
    'display_mode': 'Side by Side',
    'sample_colors': {},
    'sample_name_mappings': {},
    'font_family': 'Times New Roman',
    'font_size': 18,
    'font_bold': False,
    'font_italic': False,
    'font_color': '#000000',
}


# ── Helpers ────────────────────────────────────────────────────────────

def _y_label(cfg):
    base = BOX_LABEL_MAP.get(cfg.get('data_type_display', 'Counts'), 'Values')
    return BOX_LABEL_MAP.get(cfg.get('data_type_display', 'Counts'), 'Values')


def _element_color(element, index, cfg):
    return cfg.get('element_colors', {}).get(
        element, DEFAULT_ELEMENT_COLORS[index % len(DEFAULT_ELEMENT_COLORS)])


def _is_multi(input_data):
    return (input_data and input_data.get('type') == 'multiple_sample_data')


def _available_elements(input_data):
    if not input_data:
        return []
    sel = input_data.get('selected_isotopes', [])
    if sel:
        return sort_elements_by_mass([i['label'] for i in sel])
    return []


def _filter_values(values, data_type, log_y):
    if data_type != 'Counts':
        vals = [v for v in values if v > 0 and not np.isnan(v)]
    else:
        vals = list(values)
    if not vals:
        return None
    if log_y:
        vals = list(np.log10(np.array(vals)))
    return vals


# ── Settings Dialog ────────────────────────────────────────────────────

class BoxPlotSettingsDialog(QDialog):
    """Full settings dialog opened from context menu."""

    def __init__(self, cfg, input_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Distribution Plot Settings")
        self.setMinimumWidth(460)
        self._cfg = dict(cfg)
        self._input_data = input_data
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        scroll.setWidget(inner)
        root.addWidget(scroll)

        # ── Shape ──
        g1 = QGroupBox("Plot Shape")
        f1 = QFormLayout(g1)
        self.shape_combo = QComboBox()
        self.shape_combo.addItems(PLOT_SHAPES)
        self.shape_combo.setCurrentText(self._cfg.get('plot_shape', PLOT_SHAPES[0]))
        f1.addRow("Shape:", self.shape_combo)
        self.bw_spin = QDoubleSpinBox(); self.bw_spin.setRange(0.01, 2.0)
        self.bw_spin.setDecimals(2); self.bw_spin.setValue(self._cfg.get('violin_bandwidth', 0.2))
        f1.addRow("Violin Bandwidth:", self.bw_spin)
        self.jitter_spin = QDoubleSpinBox(); self.jitter_spin.setRange(0.0, 0.5)
        self.jitter_spin.setDecimals(2); self.jitter_spin.setValue(self._cfg.get('strip_jitter', 0.2))
        f1.addRow("Strip Jitter:", self.jitter_spin)
        lay.addWidget(g1)

        # ── Data type ──
        g2 = QGroupBox("Data Type")
        f2 = QFormLayout(g2)
        self.dtype_combo = QComboBox(); self.dtype_combo.addItems(BOX_DATA_TYPES)
        self.dtype_combo.setCurrentText(self._cfg.get('data_type_display', BOX_DATA_TYPES[0]))
        f2.addRow("Type:", self.dtype_combo)
        lay.addWidget(g2)

        # ── Display mode (multi-sample) ──
        if _is_multi(self._input_data):
            g_dm = QGroupBox("Multiple Sample Display")
            f_dm = QFormLayout(g_dm)
            self.mode_combo = QComboBox(); self.mode_combo.addItems(BOX_DISPLAY_MODES)
            self.mode_combo.setCurrentText(self._cfg.get('display_mode', BOX_DISPLAY_MODES[0]))
            f_dm.addRow("Display Mode:", self.mode_combo)
            lay.addWidget(g_dm)

        # ── Plot options ──
        g3 = QGroupBox("Plot Options")
        f3 = QFormLayout(g3)
        self.outliers_cb = QCheckBox(); self.outliers_cb.setChecked(self._cfg.get('show_outliers', True))
        f3.addRow("Show Outliers:", self.outliers_cb)
        self.mean_cb = QCheckBox(); self.mean_cb.setChecked(self._cfg.get('show_mean', True))
        f3.addRow("Show Mean:", self.mean_cb)
        self.median_cb = QCheckBox(); self.median_cb.setChecked(self._cfg.get('show_median', True))
        f3.addRow("Show Median:", self.median_cb)
        self.stats_cb = QCheckBox(); self.stats_cb.setChecked(self._cfg.get('show_stats', True))
        f3.addRow("Show Statistics:", self.stats_cb)
        self.alpha_spin = QDoubleSpinBox(); self.alpha_spin.setRange(0.1, 1.0)
        self.alpha_spin.setDecimals(1); self.alpha_spin.setValue(self._cfg.get('alpha', 0.7))
        f3.addRow("Transparency:", self.alpha_spin)
        self.width_spin = QDoubleSpinBox(); self.width_spin.setRange(0.1, 2.0)
        self.width_spin.setDecimals(1); self.width_spin.setValue(self._cfg.get('plot_width', 0.8))
        f3.addRow("Plot Width:", self.width_spin)
        self.log_y_cb = QCheckBox(); self.log_y_cb.setChecked(self._cfg.get('log_y', False))
        f3.addRow("Log Y-axis:", self.log_y_cb)
        lay.addWidget(g3)

        # ── Y limits ──
        g4 = QGroupBox("Y-Axis Limits")
        f4 = QFormLayout(g4)
        row = QHBoxLayout()
        self.y_min = QDoubleSpinBox(); self.y_min.setRange(-999999, 999999)
        self.y_min.setValue(self._cfg.get('y_min', 0))
        self.y_max = QDoubleSpinBox(); self.y_max.setRange(-999999, 999999)
        self.y_max.setValue(self._cfg.get('y_max', 100))
        self.auto_y = QCheckBox("Auto"); self.auto_y.setChecked(self._cfg.get('auto_y', True))
        self.auto_y.stateChanged.connect(lambda: (
            self.y_min.setEnabled(not self.auto_y.isChecked()),
            self.y_max.setEnabled(not self.auto_y.isChecked())))
        self.y_min.setEnabled(not self.auto_y.isChecked())
        self.y_max.setEnabled(not self.auto_y.isChecked())
        row.addWidget(self.y_min); row.addWidget(QLabel("to")); row.addWidget(self.y_max)
        row.addWidget(self.auto_y)
        f4.addRow("Y Range:", row)
        lay.addWidget(g4)

        # ── Element colors ──
        elems = _available_elements(self._input_data)
        if elems:
            g5 = QGroupBox("Element Colors")
            v5 = QVBoxLayout(g5)
            self._elem_btns = {}
            ec = dict(self._cfg.get('element_colors', {}))
            for i, el in enumerate(elems):
                h = QHBoxLayout()
                h.addWidget(QLabel(el))
                btn = QPushButton(); btn.setFixedSize(30, 20)
                c = ec.get(el, DEFAULT_ELEMENT_COLORS[i % len(DEFAULT_ELEMENT_COLORS)])
                ec[el] = c
                btn.setStyleSheet(f"background-color: {c}; border:1px solid black;")
                btn.clicked.connect(lambda _, e=el, b=btn: self._pick_elem_color(e, b))
                h.addWidget(btn); h.addStretch()
                w = QWidget(); w.setLayout(h); v5.addWidget(w)
                self._elem_btns[el] = (btn, c)
            self._elem_colors = ec
            lay.addWidget(g5)
        else:
            self._elem_colors = dict(self._cfg.get('element_colors', {}))

        # ── Sample colors & names (multi) ──
        if _is_multi(self._input_data):
            names = self._input_data.get('sample_names', [])
            if names:
                g6 = QGroupBox("Sample Colors & Names")
                v6 = QVBoxLayout(g6)
                self._sample_btns = {}
                self._sample_edits = {}
                sc = dict(self._cfg.get('sample_colors', {}))
                nm = dict(self._cfg.get('sample_name_mappings', {}))
                for i, sn in enumerate(names):
                    h = QHBoxLayout()
                    ed = QLineEdit(nm.get(sn, sn)); ed.setFixedWidth(180)
                    h.addWidget(ed); self._sample_edits[sn] = ed
                    btn = QPushButton(); btn.setFixedSize(25, 18)
                    c = sc.get(sn, DEFAULT_SAMPLE_COLORS[i % len(DEFAULT_SAMPLE_COLORS)])
                    sc[sn] = c
                    btn.setStyleSheet(f"background-color: {c}; border:1px solid black;")
                    btn.clicked.connect(lambda _, s=sn, b=btn: self._pick_sample_color(s, b))
                    h.addWidget(btn); h.addStretch()
                    w = QWidget(); w.setLayout(h); v6.addWidget(w)
                    self._sample_btns[sn] = (btn, c)
                self._sample_colors = sc
                self._sample_names = nm
                lay.addWidget(g6)

        # ── Font ──
        self._font_grp = FontSettingsGroup(self._cfg)
        lay.addWidget(self._font_grp.build())

        # ── Buttons ──
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _pick_elem_color(self, el, btn):
        c = QColorDialog.getColor(QColor(self._elem_colors.get(el, '#663399')), self)
        if c.isValid():
            self._elem_colors[el] = c.name()
            btn.setStyleSheet(f"background-color: {c.name()}; border:1px solid black;")

    def _pick_sample_color(self, sn, btn):
        c = QColorDialog.getColor(QColor(self._sample_colors.get(sn, '#3B82F6')), self)
        if c.isValid():
            self._sample_colors[sn] = c.name()
            btn.setStyleSheet(f"background-color: {c.name()}; border:1px solid black;")

    def collect(self):
        d = {
            'plot_shape': self.shape_combo.currentText(),
            'violin_bandwidth': self.bw_spin.value(),
            'strip_jitter': self.jitter_spin.value(),
            'data_type_display': self.dtype_combo.currentText(),
            'show_outliers': self.outliers_cb.isChecked(),
            'show_mean': self.mean_cb.isChecked(),
            'show_median': self.median_cb.isChecked(),
            'show_stats': self.stats_cb.isChecked(),
            'alpha': self.alpha_spin.value(),
            'plot_width': self.width_spin.value(),
            'log_y': self.log_y_cb.isChecked(),
            'y_min': self.y_min.value(),
            'y_max': self.y_max.value(),
            'auto_y': self.auto_y.isChecked(),
            'element_colors': dict(self._elem_colors),
        }
        d.update(self._font_grp.collect())
        if hasattr(self, 'mode_combo'):
            d['display_mode'] = self.mode_combo.currentText()
        if hasattr(self, '_sample_colors'):
            d['sample_colors'] = dict(self._sample_colors)
        if hasattr(self, '_sample_edits'):
            d['sample_name_mappings'] = {k: v.text() for k, v in self._sample_edits.items()}
        return d


# ── Drawing helpers (PyQtGraph) ────────────────────────────────────────

def _draw_box(plot_item, x, values, color, alpha, width, cfg):
    if len(values) < 2:
        return
    q1, median, q3 = np.percentile(values, [25, 50, 75])
    iqr = q3 - q1
    co = QColor(color)

    box = pg.QtWidgets.QGraphicsRectItem(x - width/2, q1, width, q3 - q1)
    box.setBrush(pg.mkBrush(co.red(), co.green(), co.blue(), alpha))
    box.setPen(pg.mkPen(color, width=2))
    plot_item.addItem(box)

    if cfg.get('show_median', True):
        plot_item.addItem(pg.PlotDataItem(
            [x - width/2, x + width/2], [median, median], pen=pg.mkPen('black', width=3)))

    lo = max(q1 - 1.5*iqr, min(values))
    hi = min(q3 + 1.5*iqr, max(values))
    wp = pg.mkPen('black', width=2)
    plot_item.addItem(pg.PlotDataItem([x, x], [q1, lo], pen=wp))
    plot_item.addItem(pg.PlotDataItem([x, x], [q3, hi], pen=wp))
    cw = width * 0.3
    plot_item.addItem(pg.PlotDataItem([x-cw/2, x+cw/2], [lo, lo], pen=wp))
    plot_item.addItem(pg.PlotDataItem([x-cw/2, x+cw/2], [hi, hi], pen=wp))

    if cfg.get('show_outliers', True):
        outliers = [v for v in values if v < q1 - 1.5*iqr or v > q3 + 1.5*iqr]
        if outliers:
            plot_item.addItem(pg.ScatterPlotItem(
                x=[x]*len(outliers), y=outliers, pen=pg.mkPen('black'),
                brush=pg.mkBrush('red'), size=6, symbol='o'))

    if cfg.get('show_mean', True):
        plot_item.addItem(pg.ScatterPlotItem(
            x=[x], y=[np.mean(values)], pen=pg.mkPen('white', width=2),
            brush=pg.mkBrush('blue'), size=8, symbol='s'))


def _draw_violin(plot_item, x, values, color, alpha, width, cfg):
    if len(values) < 2:
        return
    try:
        bw = cfg.get('violin_bandwidth', 0.2)
        kde = gaussian_kde(values, bw_method=bw)
        ymin, ymax = min(values), max(values)
        yr = ymax - ymin
        yv = np.linspace(ymin - 0.1*yr, ymax + 0.1*yr, 100)
        d = kde(yv)
        mx = np.max(d)
        nd = (d / mx * width/2) if mx > 0 else np.zeros_like(d)
        co = QColor(color)
        ha = alpha // 2

        plot_item.addItem(pg.PlotDataItem(x=x - nd, y=yv, pen=pg.mkPen(color, width=2),
            fillLevel=x, brush=pg.mkBrush(co.red(), co.green(), co.blue(), ha)))
        plot_item.addItem(pg.PlotDataItem(x=x + nd, y=yv, pen=pg.mkPen(color, width=2),
            fillLevel=x, brush=pg.mkBrush(co.red(), co.green(), co.blue(), ha)))

        q1, med, q3 = np.percentile(values, [25, 50, 75])
        if cfg.get('show_median', True):
            plot_item.addItem(pg.PlotDataItem(
                [x - width/4, x + width/4], [med, med], pen=pg.mkPen('white', width=4)))
        plot_item.addItem(pg.PlotDataItem(
            [x - width/6, x + width/6], [q1, q1], pen=pg.mkPen('white', width=2)))
        plot_item.addItem(pg.PlotDataItem(
            [x - width/6, x + width/6], [q3, q3], pen=pg.mkPen('white', width=2)))

        if cfg.get('show_mean', True):
            plot_item.addItem(pg.ScatterPlotItem(
                x=[x], y=[np.mean(values)], pen=pg.mkPen('white', width=2),
                brush=pg.mkBrush('red'), size=8, symbol='d'))
    except Exception:
        _draw_box(plot_item, x, values, color, alpha, width, cfg)


def _draw_box_violin(plot_item, x, values, color, alpha, width, cfg):
    _draw_violin(plot_item, x, values, color, alpha // 2, width, cfg)
    box_cfg = dict(cfg); box_cfg['show_median'] = True; box_cfg['show_mean'] = False
    _draw_box(plot_item, x, values, color, alpha, width * 0.3, box_cfg)


def _draw_strip(plot_item, x, values, color, alpha, width, cfg):
    jitter = cfg.get('strip_jitter', 0.2)
    np.random.seed(42)
    xj = x + np.random.uniform(-jitter, jitter, len(values))
    co = QColor(color)
    plot_item.addItem(pg.ScatterPlotItem(
        x=xj, y=values, pen=pg.mkPen(color),
        brush=pg.mkBrush(co.red(), co.green(), co.blue(), alpha), size=6, symbol='o'))
    if cfg.get('show_mean', True):
        plot_item.addItem(pg.PlotDataItem(
            [x - width/2, x + width/2], [np.mean(values)]*2, pen=pg.mkPen('red', width=3)))
    if cfg.get('show_median', True):
        plot_item.addItem(pg.PlotDataItem(
            [x - width/2, x + width/2], [np.median(values)]*2, pen=pg.mkPen('blue', width=2)))


def _draw_half_violin_box(plot_item, x, values, color, alpha, width, cfg):
    co = QColor(color)
    try:
        bw = cfg.get('violin_bandwidth', 0.2)
        kde = gaussian_kde(values, bw_method=bw)
        ymin, ymax = min(values), max(values)
        yr = ymax - ymin
        yv = np.linspace(ymin - 0.1*yr, ymax + 0.1*yr, 100)
        d = kde(yv)
        mx = np.max(d)
        nd = (d / mx * width/2) if mx > 0 else np.zeros_like(d)
        plot_item.addItem(pg.PlotDataItem(x=x - nd, y=yv, pen=pg.mkPen(color, width=2),
            fillLevel=x, brush=pg.mkBrush(co.red(), co.green(), co.blue(), alpha // 2)))
    except Exception:
        pass

    q1, med, q3 = np.percentile(values, [25, 50, 75])
    box = pg.QtWidgets.QGraphicsRectItem(x, q1, width/2, q3 - q1)
    box.setBrush(pg.mkBrush(co.red(), co.green(), co.blue(), alpha))
    box.setPen(pg.mkPen(color, width=2))
    plot_item.addItem(box)
    if cfg.get('show_median', True):
        plot_item.addItem(pg.PlotDataItem(
            [x, x + width/2], [med, med], pen=pg.mkPen('black', width=3)))


def _draw_notched_box(plot_item, x, values, color, alpha, width, cfg):
    q1, med, q3 = np.percentile(values, [25, 50, 75])
    iqr = q3 - q1
    n = len(values)
    ne = 1.57 * iqr / np.sqrt(n) if n > 0 else 0
    nl, nu = med - ne, med + ne
    nw = width * 0.3
    co = QColor(color)

    pts = [(x - width/2, q1), (x + width/2, q1), (x + width/2, nl),
           (x + nw/2, med), (x + width/2, nu), (x + width/2, q3),
           (x - width/2, q3), (x - width/2, nu), (x - nw/2, med), (x - width/2, nl)]
    xc = [p[0] for p in pts] + [pts[0][0]]
    yc = [p[1] for p in pts] + [pts[0][1]]
    plot_item.addItem(pg.PlotDataItem(x=xc, y=yc, pen=pg.mkPen(color, width=2),
        brush=pg.mkBrush(co.red(), co.green(), co.blue(), alpha)))

    if cfg.get('show_median', True):
        plot_item.addItem(pg.PlotDataItem(
            [x - nw/2, x + nw/2], [med, med], pen=pg.mkPen('black', width=3)))

    lo = max(q1 - 1.5*iqr, min(values))
    hi = min(q3 + 1.5*iqr, max(values))
    wp = pg.mkPen('black', width=2)
    plot_item.addItem(pg.PlotDataItem([x, x], [q1, lo], pen=wp))
    plot_item.addItem(pg.PlotDataItem([x, x], [q3, hi], pen=wp))


def _draw_bar_errors(plot_item, x, values, color, alpha, width, cfg):
    mean_v = np.mean(values)
    sem = np.std(values) / np.sqrt(len(values))
    co = QColor(color)

    bar = pg.QtWidgets.QGraphicsRectItem(x - width/2, 0, width, mean_v)
    bar.setBrush(pg.mkBrush(co.red(), co.green(), co.blue(), alpha))
    bar.setPen(pg.mkPen(color, width=2))
    plot_item.addItem(bar)

    ep = pg.mkPen('black', width=2)
    cw = width * 0.3
    for sign in [1, -1]:
        ev = mean_v + sign * sem
        if sign == -1:
            ev = max(0, ev)
        plot_item.addItem(pg.PlotDataItem([x, x], [mean_v, ev], pen=ep))
        plot_item.addItem(pg.PlotDataItem([x - cw/2, x + cw/2], [ev, ev], pen=ep))


_SHAPE_DRAWERS = {
    'Box Plot (Traditional)': _draw_box,
    'Violin Plot': _draw_violin,
    'Box + Violin (Overlay)': _draw_box_violin,
    'Strip Plot (Dots)': _draw_strip,
    'Half Violin + Half Box': _draw_half_violin_box,
    'Notched Box Plot': _draw_notched_box,
    'Bar Plot with Error Bars': _draw_bar_errors,
}


def _draw_single_element(plot_item, x, values, sample_name, element, cfg, is_multi):
    """Dispatch to the correct shape drawer."""
    if len(values) < 2:
        return
    sc = cfg.get('sample_colors', {})
    ec = cfg.get('element_colors', {})
    if is_multi:
        color = sc.get(sample_name, DEFAULT_SAMPLE_COLORS[0])
    else:
        color = ec.get(element, DEFAULT_ELEMENT_COLORS[0])
    alpha = int(cfg.get('alpha', 0.7) * 255)
    width = cfg.get('plot_width', 0.8)
    shape = cfg.get('plot_shape', PLOT_SHAPES[0])
    drawer = _SHAPE_DRAWERS.get(shape, _draw_box)
    drawer(plot_item, x, values, color, alpha, width, cfg)


def _add_stats_text(plot_item, plot_data, cfg):
    """Add statistics text box."""
    dt = cfg.get('data_type_display', 'Counts')
    shape = cfg.get('plot_shape', PLOT_SHAPES[0])
    lines = [f"Statistics ({dt}):", f"Plot: {shape}"]
    for el, vals in plot_data.items():
        if not vals:
            continue
        fv = [v for v in vals if v > 0 and not np.isnan(v)] if dt != 'Counts' else vals
        if not fv:
            continue
        n = len(fv)
        mu, med = np.mean(fv), np.median(fv)
        q1, q3 = np.percentile(fv, [25, 75])
        sd = np.std(fv)
        if 'Mass' in dt:
            lines.append(f"{el}: {n} particles")
            lines.append(f"  Mean: {mu:.2f}±{sd:.2f} fg, Median: {med:.2f} (Q1:{q1:.2f}, Q3:{q3:.2f})")
        elif 'Moles' in dt:
            lines.append(f"{el}: {n} particles")
            lines.append(f"  Mean: {mu:.4f}±{sd:.4f} fmol, Median: {med:.4f} (Q1:{q1:.4f}, Q3:{q3:.4f})")
        elif 'Diameter' in dt:
            lines.append(f"{el}: {n} particles")
            lines.append(f"  Mean: {mu:.1f}±{sd:.1f} nm, Median: {med:.1f} (Q1:{q1:.1f}, Q3:{q3:.1f})")
        else:
            lines.append(f"{el}: {n} particles")
            lines.append(f"  Mean: {mu:.1f}±{sd:.1f}, Median: {med:.1f} (Q1:{q1:.1f}, Q3:{q3:.1f})")

    txt = pg.TextItem('\n'.join(lines), anchor=(0, 1),
                      border=pg.mkPen('black', width=1),
                      fill=pg.mkBrush(255, 255, 255, 200))
    plot_item.addItem(txt)
    try:
        vb = plot_item.getViewBox().state['viewRange']
        txt.setPos(vb[0][0] + 0.02*(vb[0][1]-vb[0][0]),
                   vb[1][0] + 0.98*(vb[1][1]-vb[1][0]))
    except Exception:
        txt.setPos(0.02, 0.98)


# ── Display Dialog ─────────────────────────────────────────────────────

class BoxPlotDisplayDialog(QDialog):
    """Main dialog with PyQtGraph plot and right-click context menu."""

    def __init__(self, node, parent_window=None):
        super().__init__(parent_window)
        self.node = node
        self.setWindowTitle("Particle Data Distribution Plot Analysis")
        self.setMinimumSize(1100, 750)

        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        # Stats label
        self._stats = QLabel("")
        self._stats.setStyleSheet("color:#6B7280; font-size:11px; padding:2px 6px;")
        lay.addWidget(self._stats)

        # PyQtGraph widget
        self.pw = pg.GraphicsLayoutWidget()
        self.pw.setBackground('w')
        self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pw.customContextMenuRequested.connect(self._ctx_menu)
        lay.addWidget(self.pw, stretch=1)

    # ── Context menu ──

    def _ctx_menu(self, pos):
        cfg = self.node.config
        menu = QMenu(self)

        # Plot shape
        sm = menu.addMenu("Plot Shape")
        for s in PLOT_SHAPES:
            a = sm.addAction(s)
            a.setCheckable(True)
            a.setChecked(cfg.get('plot_shape') == s)
            a.triggered.connect(lambda _, v=s: self._set('plot_shape', v))

        # Data type
        dm = menu.addMenu("Data Type")
        for dt in BOX_DATA_TYPES:
            a = dm.addAction(dt)
            a.setCheckable(True)
            a.setChecked(cfg.get('data_type_display') == dt)
            a.triggered.connect(lambda _, v=dt: self._set('data_type_display', v))

        # Quick toggles
        tm = menu.addMenu("Quick Toggles")
        for key, label in [('show_outliers', 'Show Outliers'), ('show_mean', 'Show Mean'),
                           ('show_median', 'Show Median'), ('show_stats', 'Show Statistics'),
                           ('log_y', 'Log Y-axis')]:
            a = tm.addAction(label)
            a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        # Display mode (multi-sample)
        if _is_multi(self.node.input_data):
            mm = menu.addMenu("Display Mode")
            for m in BOX_DISPLAY_MODES:
                a = mm.addAction(m)
                a.setCheckable(True)
                a.setChecked(cfg.get('display_mode') == m)
                a.triggered.connect(lambda _, v=m: self._set('display_mode', v))

        menu.addSeparator()
        menu.addAction("Configure…").triggered.connect(self._open_settings)
        menu.addAction("Download Figure…").triggered.connect(
            lambda: download_pyqtgraph_figure(self.pw, self, "distribution_plot.png"))

        menu.exec(self.pw.mapToGlobal(pos))

    def _toggle(self, key):
        self.node.config[key] = not self.node.config.get(key, False)
        self._refresh()

    def _set(self, key, value):
        self.node.config[key] = value
        self._refresh()

    def _open_settings(self):
        dlg = BoxPlotSettingsDialog(self.node.config, self.node.input_data, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    # ── Refresh ──

    def _refresh(self):
        try:
            self.pw.clear()
            plot_data = self.node.extract_plot_data()
            if not plot_data:
                pi = self.pw.addPlot()
                t = pg.TextItem("No particle data available\nConnect to Sample Selector",
                                anchor=(0.5, 0.5), color='gray')
                pi.addItem(t); t.setPos(0.5, 0.5)
                pi.hideAxis('left'); pi.hideAxis('bottom')
                self._stats.setText("")
                return

            cfg = self.node.config
            multi = _is_multi(self.node.input_data)

            if multi:
                mode = cfg.get('display_mode', 'Side by Side')
                if mode == 'Individual Subplots':
                    self._draw_subplots(plot_data, cfg)
                elif mode == 'Grouped by Element':
                    self._draw_grouped(plot_data, cfg)
                else:
                    pi = self.pw.addPlot()
                    self._draw_combined(pi, plot_data, cfg)
                    apply_font_to_pyqtgraph(pi, cfg)
            else:
                pi = self.pw.addPlot()
                self._draw_single_sample(pi, plot_data, cfg)
                apply_font_to_pyqtgraph(pi, cfg)

            self._update_stats(plot_data, multi)
        except Exception as e:
            print(f"Error updating distribution plot: {e}")
            import traceback; traceback.print_exc()

    def _draw_single_sample(self, pi, data, cfg):
        """Single sample – one shape per element."""
        sorted_data = sort_element_dict_by_mass(data)
        xp, xl = [], []
        x = 0
        for el, vals in sorted_data.items():
            fv = _filter_values(vals, cfg.get('data_type_display', 'Counts'), cfg.get('log_y'))
            if fv and len(fv) >= 2:
                _draw_single_element(pi, x, fv, None, el, cfg, False)
                xp.append(x); xl.append(el)
                x += 1
        if xp:
            pi.getAxis('bottom').setTicks([list(zip(xp, xl))])
        set_axis_labels(pi, "Elements", _y_label(cfg), cfg)
        
        if cfg.get('log_y'):
            pi.getAxis('left').setLogMode(True)        
        if not cfg.get('auto_y', True):
            pi.setYRange(cfg['y_min'], cfg['y_max'])
        if cfg.get('show_stats', True):
            _add_stats_text(pi, sorted_data, cfg)

    def _draw_combined(self, pi, plot_data, cfg):
        """Multi-sample Side by Side."""
        xp, xl = [], []
        x = 0
        for sn, sdata in plot_data.items():
            if not sdata:
                continue
            for el, vals in sort_element_dict_by_mass(sdata).items():
                fv = _filter_values(vals, cfg.get('data_type_display'), cfg.get('log_y'))
                if fv and len(fv) >= 2:
                    _draw_single_element(pi, x, fv, sn, el, cfg, True)
                    dn = get_display_name(sn, cfg)
                    xp.append(x); xl.append(f"{el}\n({dn})")
                    x += 1
        if xp:
            pi.getAxis('bottom').setTicks([list(zip(xp, xl))])
        set_axis_labels(pi, "Elements", _y_label(cfg), cfg)
        
        if cfg.get('log_y'):
            pi.getAxis('left').setLogMode(True)        
        if not cfg.get('auto_y', True):
            pi.setYRange(cfg['y_min'], cfg['y_max'])

    def _draw_subplots(self, plot_data, cfg):
        names = list(plot_data.keys())
        cols = min(3, len(names))
        rows = math.ceil(len(names) / cols)
        for i, sn in enumerate(names):
            r, c = divmod(i, cols)
            pi = self.pw.addPlot(row=r, col=c)
            sd = plot_data[sn]
            if sd:
                self._draw_single_sample(pi, sort_element_dict_by_mass(sd), cfg)
                pi.setTitle(get_display_name(sn, cfg))
            apply_font_to_pyqtgraph(pi, cfg)

    def _draw_grouped(self, plot_data, cfg):
        all_elems = set()
        for sd in plot_data.values():
            all_elems.update(sd.keys())
        all_elems = sort_elements_by_mass(list(all_elems))
        cols = min(3, len(all_elems))
        rows = math.ceil(len(all_elems) / cols)
        for i, el in enumerate(all_elems):
            r, c = divmod(i, cols)
            pi = self.pw.addPlot(row=r, col=c)
            xp, xl = [], []
            x = 0
            for sn, sd in plot_data.items():
                if el in sd:
                    fv = _filter_values(sd[el], cfg.get('data_type_display'), cfg.get('log_y'))
                    if fv and len(fv) >= 2:
                        _draw_single_element(pi, x, fv, sn, el, cfg, True)
                        xp.append(x); xl.append(get_display_name(sn, cfg))
                        x += 1
            if xp:
                pi.getAxis('bottom').setTicks([list(zip(xp, xl))])
            pi.setTitle(el)
            set_axis_labels(pi, "Samples", _y_label(cfg), cfg)
            
            if cfg.get('log_y'):
                pi.getAxis('left').setLogMode(True)            
            apply_font_to_pyqtgraph(pi, cfg)

    def _update_stats(self, plot_data, multi):
        if multi:
            total = sum(sum(len(v) for v in sd.values()) for sd in plot_data.values() if sd)
            ns = len(plot_data)
            self._stats.setText(f"{ns} samples  |  {total} total data points")
        else:
            total = sum(len(v) for v in plot_data.values())
            ne = len(plot_data)
            self._stats.setText(f"{ne} elements  |  {total} total data points")


# ── Node ───────────────────────────────────────────────────────────────

class BoxPlotNode(QObject):
    position_changed = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        super().__init__()
        self.title = "Distribution Plot"
        self.node_type = "box_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        self.config = dict(DEFAULT_CONFIG)
        self.input_data = None

    def set_position(self, pos):
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        dlg = BoxPlotDisplayDialog(self, parent_window)
        dlg.exec()
        return True

    def process_data(self, input_data):
        if not input_data:
            return
        self.input_data = input_data
        self.configuration_changed.emit()

    def extract_plot_data(self):
        if not self.input_data:
            return None
        data_key = BOX_DATA_KEY_MAP.get(
            self.config.get('data_type_display', 'Counts'), 'elements')
        itype = self.input_data.get('type')
        if itype == 'sample_data':
            return self._extract_single(data_key)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(data_key)
        return None

    def _extract_single(self, data_key):
        particles = self.input_data.get('particle_data')
        if not particles:
            return None
        result = {}
        for p in particles:
            for el, val in p.get(data_key, {}).items():
                if data_key == 'elements':
                    if val > 0:
                        result.setdefault(el, []).append(val)
                else:
                    if val > 0 and not np.isnan(val):
                        result.setdefault(el, []).append(val)
        return sort_element_dict_by_mass(result) if result else None

    def _extract_multi(self, data_key):
        particles = self.input_data.get('particle_data', [])
        names = self.input_data.get('sample_names', [])
        if not particles:
            return None
        sd = {n: {} for n in names}
        for p in particles:
            src = p.get('source_sample')
            if src and src in sd:
                for el, val in p.get(data_key, {}).items():
                    if data_key == 'elements':
                        if val > 0:
                            sd[src].setdefault(el, []).append(val)
                    else:
                        if val > 0 and not np.isnan(val):
                            sd[src].setdefault(el, []).append(val)
        result = {}
        for sn, d in sd.items():
            if d:
                result[sn] = sort_element_dict_by_mass(d)
        return result if result else None