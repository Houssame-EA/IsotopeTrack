

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QColorDialog,
    QPushButton, QLineEdit, QFrame, QWidget, QMenu, QScrollArea,
    QDialogButtonBox, QMessageBox, QFileDialog,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QPen, QFont
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

# ── Constants ──────────────────────────────────────────────────────────

MOLAR_DATA_TYPES = ['Element Moles (fmol)', 'Particle Moles (fmol)']

MOLAR_DATA_KEY_MAP = {
    'Element Moles (fmol)': 'element_moles_fmol',
    'Particle Moles (fmol)': 'particle_moles_fmol',
}

MR_DISPLAY_MODES = [
    'Overlaid (Different Colors)',
    'Side by Side Subplots',
    'Individual Subplots',
    'Combined with Legend',
]

ZERO_HANDLING = [
    'Skip particles with zero values',
    'Replace zeros with threshold',
    'Use log10 safe calculation',
]

DEFAULT_CONFIG = {
    'data_type_display': 'Element Moles (fmol)',
    'numerator_element': '',
    'denominator_element': '',
    'min_threshold': 0.001,
    'zero_handling': ZERO_HANDLING[0],
    'filter_outliers': True,
    'outlier_percentile': 99.0,
    'bins': 50,
    'alpha': 0.7,
    'bin_borders': True,
    'log_x': True,
    'log_y': False,
    'show_stats': True,
    'show_curve': True,
    'show_median': True,
    'show_mean': True,
    'x_min': 0.01, 'x_max': 100.0, 'auto_x': True,
    'y_min': 0, 'y_max': 100, 'auto_y': True,
    'display_mode': MR_DISPLAY_MODES[0],
    'normalize_samples': False,
    'sample_colors': {},
    'sample_name_mappings': {},
    'font_family': 'Times New Roman',
    'font_size': 18,
    'font_bold': False,
    'font_italic': False,
    'font_color': '#000000',
}


# ── Helpers ────────────────────────────────────────────────────────────

def _is_multi(input_data):
    return input_data and input_data.get('type') == 'multiple_sample_data'


def _xy_labels(cfg):
    num = cfg.get('numerator_element', 'Element1')
    den = cfg.get('denominator_element', 'Element2')
    
    xl = f"{num}/{den}"
    yl = "Number of Particles"
    
    return xl, yl


# ── Settings Dialog ────────────────────────────────────────────────────

class MolarRatioSettingsDialog(QDialog):
    """Full settings dialog opened from context menu."""

    def __init__(self, cfg, input_data, available_elements, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Molar Ratio Analysis Settings")
        self.setMinimumWidth(480)
        self._cfg = dict(cfg)
        self._input_data = input_data
        self._elements = available_elements or []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); lay = QVBoxLayout(inner)
        scroll.setWidget(inner); root.addWidget(scroll)

        # ── Element selection ──
        g1 = QGroupBox("Element Selection for Ratio")
        f1 = QFormLayout(g1)
        self.num_combo = QComboBox(); self.den_combo = QComboBox()
        if self._elements:
            self.num_combo.addItems(self._elements)
            self.den_combo.addItems(self._elements)
            nc = self._cfg.get('numerator_element', '')
            dc = self._cfg.get('denominator_element', '')
            if nc in self._elements: self.num_combo.setCurrentText(nc)
            if dc in self._elements: self.den_combo.setCurrentText(dc)
            elif len(self._elements) > 1: self.den_combo.setCurrentIndex(1)
        f1.addRow("Numerator:", self.num_combo)
        f1.addRow("Denominator:", self.den_combo)
        lay.addWidget(g1)

        # ── Molar data type ──
        g2 = QGroupBox("Molar Data Type")
        f2 = QFormLayout(g2)
        self.dtype_combo = QComboBox(); self.dtype_combo.addItems(MOLAR_DATA_TYPES)
        self.dtype_combo.setCurrentText(self._cfg.get('data_type_display', MOLAR_DATA_TYPES[0]))
        f2.addRow("Type:", self.dtype_combo)
        lay.addWidget(g2)

        # ── Ratio calculation ──
        g3 = QGroupBox("Ratio Calculation")
        f3 = QFormLayout(g3)
        self.thresh_spin = QDoubleSpinBox(); self.thresh_spin.setRange(0.0, 1000.0)
        self.thresh_spin.setDecimals(3); self.thresh_spin.setValue(self._cfg.get('min_threshold', 0.001))
        f3.addRow("Min Threshold (fmol):", self.thresh_spin)
        self.zero_combo = QComboBox(); self.zero_combo.addItems(ZERO_HANDLING)
        self.zero_combo.setCurrentText(self._cfg.get('zero_handling', ZERO_HANDLING[0]))
        f3.addRow("Zero Handling:", self.zero_combo)
        self.outlier_cb = QCheckBox(); self.outlier_cb.setChecked(self._cfg.get('filter_outliers', True))
        f3.addRow("Filter Outliers:", self.outlier_cb)
        self.pct_spin = QDoubleSpinBox(); self.pct_spin.setRange(90.0, 99.9)
        self.pct_spin.setDecimals(1); self.pct_spin.setValue(self._cfg.get('outlier_percentile', 99.0))
        f3.addRow("Keep Below Percentile:", self.pct_spin)
        lay.addWidget(g3)

        # ── Display mode (multi) ──
        if _is_multi(self._input_data):
            gm = QGroupBox("Multiple Sample Display")
            fm = QFormLayout(gm)
            self.mode_combo = QComboBox(); self.mode_combo.addItems(MR_DISPLAY_MODES)
            self.mode_combo.setCurrentText(self._cfg.get('display_mode', MR_DISPLAY_MODES[0]))
            fm.addRow("Display Mode:", self.mode_combo)
            self.norm_cb = QCheckBox(); self.norm_cb.setChecked(self._cfg.get('normalize_samples', False))
            fm.addRow("Normalize Samples:", self.norm_cb)
            lay.addWidget(gm)

        # ── Plot options ──
        g4 = QGroupBox("Plot Options")
        f4 = QFormLayout(g4)
        self.bins_spin = QSpinBox(); self.bins_spin.setRange(10, 200)
        self.bins_spin.setValue(self._cfg.get('bins', 50))
        f4.addRow("Bins:", self.bins_spin)
        self.alpha_spin = QDoubleSpinBox(); self.alpha_spin.setRange(0.1, 1.0)
        self.alpha_spin.setDecimals(1); self.alpha_spin.setValue(self._cfg.get('alpha', 0.7))
        f4.addRow("Transparency:", self.alpha_spin)
        self.borders_cb = QCheckBox(); self.borders_cb.setChecked(self._cfg.get('bin_borders', True))
        f4.addRow("Bin Borders:", self.borders_cb)
        self.curve_cb = QCheckBox(); self.curve_cb.setChecked(self._cfg.get('show_curve', True))
        f4.addRow("Density Curve:", self.curve_cb)
        self.median_cb = QCheckBox(); self.median_cb.setChecked(self._cfg.get('show_median', True))
        f4.addRow("Median Line:", self.median_cb)
        self.mean_cb = QCheckBox(); self.mean_cb.setChecked(self._cfg.get('show_mean', True))
        f4.addRow("Mean ± SD:", self.mean_cb)
        self.stats_cb = QCheckBox(); self.stats_cb.setChecked(self._cfg.get('show_stats', True))
        f4.addRow("Statistics:", self.stats_cb)
        self.lx_cb = QCheckBox(); self.lx_cb.setChecked(self._cfg.get('log_x', True))
        f4.addRow("Log X:", self.lx_cb)
        self.ly_cb = QCheckBox(); self.ly_cb.setChecked(self._cfg.get('log_y', False))
        f4.addRow("Log Y:", self.ly_cb)
        lay.addWidget(g4)

        # ── Axis limits ──
        g5 = QGroupBox("Axis Limits")
        f5 = QFormLayout(g5)
        xr = QHBoxLayout()
        self.x_min = QDoubleSpinBox(); self.x_min.setRange(0.0001, 999999); self.x_min.setDecimals(4)
        self.x_min.setValue(self._cfg.get('x_min', 0.01))
        self.x_max = QDoubleSpinBox(); self.x_max.setRange(0.0001, 999999); self.x_max.setDecimals(4)
        self.x_max.setValue(self._cfg.get('x_max', 100.0))
        self.auto_x = QCheckBox("Auto"); self.auto_x.setChecked(self._cfg.get('auto_x', True))
        self.auto_x.stateChanged.connect(lambda: (
            self.x_min.setEnabled(not self.auto_x.isChecked()),
            self.x_max.setEnabled(not self.auto_x.isChecked())))
        self.x_min.setEnabled(not self.auto_x.isChecked())
        self.x_max.setEnabled(not self.auto_x.isChecked())
        xr.addWidget(self.x_min); xr.addWidget(QLabel("to")); xr.addWidget(self.x_max); xr.addWidget(self.auto_x)
        f5.addRow("X Range:", xr)

        yr = QHBoxLayout()
        self.y_min = QDoubleSpinBox(); self.y_min.setRange(0, 999999)
        self.y_min.setValue(self._cfg.get('y_min', 0))
        self.y_max = QDoubleSpinBox(); self.y_max.setRange(0, 999999)
        self.y_max.setValue(self._cfg.get('y_max', 100))
        self.auto_y = QCheckBox("Auto"); self.auto_y.setChecked(self._cfg.get('auto_y', True))
        self.auto_y.stateChanged.connect(lambda: (
            self.y_min.setEnabled(not self.auto_y.isChecked()),
            self.y_max.setEnabled(not self.auto_y.isChecked())))
        self.y_min.setEnabled(not self.auto_y.isChecked())
        self.y_max.setEnabled(not self.auto_y.isChecked())
        yr.addWidget(self.y_min); yr.addWidget(QLabel("to")); yr.addWidget(self.y_max); yr.addWidget(self.auto_y)
        f5.addRow("Y Range:", yr)
        lay.addWidget(g5)

        # ── Sample colors (multi or single) ──
        if _is_multi(self._input_data):
            names = self._input_data.get('sample_names', [])
            if names:
                g6 = QGroupBox("Sample Colors & Names")
                v6 = QVBoxLayout(g6)
                self._sample_btns = {}; self._sample_edits = {}
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
                self._sc = sc; self._nm = nm
                lay.addWidget(g6)
        else:
            g6 = QGroupBox("Histogram Color")
            v6 = QHBoxLayout(g6)
            sc = dict(self._cfg.get('sample_colors', {}))
            c = sc.get('single_sample', '#663399')
            self._single_btn = QPushButton(); self._single_btn.setFixedSize(40, 25)
            self._single_btn.setStyleSheet(f"background-color: {c}; border:1px solid black;")
            self._single_btn.clicked.connect(self._pick_single_color)
            self._single_color = c
            v6.addWidget(QLabel("Color:")); v6.addWidget(self._single_btn); v6.addStretch()
            lay.addWidget(g6)

        # ── Font ──
        self._font_grp = FontSettingsGroup(self._cfg)
        lay.addWidget(self._font_grp.build())

        # ── Buttons ──
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _pick_sample_color(self, sn, btn):
        c = QColorDialog.getColor(QColor(self._sc.get(sn, '#3B82F6')), self)
        if c.isValid():
            self._sc[sn] = c.name()
            btn.setStyleSheet(f"background-color: {c.name()}; border:1px solid black;")

    def _pick_single_color(self):
        c = QColorDialog.getColor(QColor(self._single_color), self)
        if c.isValid():
            self._single_color = c.name()
            self._single_btn.setStyleSheet(f"background-color: {c.name()}; border:1px solid black;")

    def collect(self):
        d = {
            'numerator_element': self.num_combo.currentText(),
            'denominator_element': self.den_combo.currentText(),
            'data_type_display': self.dtype_combo.currentText(),
            'min_threshold': self.thresh_spin.value(),
            'zero_handling': self.zero_combo.currentText(),
            'filter_outliers': self.outlier_cb.isChecked(),
            'outlier_percentile': self.pct_spin.value(),
            'bins': self.bins_spin.value(),
            'alpha': self.alpha_spin.value(),
            'bin_borders': self.borders_cb.isChecked(),
            'show_curve': self.curve_cb.isChecked(),
            'show_median': self.median_cb.isChecked(),
            'show_mean': self.mean_cb.isChecked(),
            'show_stats': self.stats_cb.isChecked(),
            'log_x': self.lx_cb.isChecked(),
            'log_y': self.ly_cb.isChecked(),
            'x_min': self.x_min.value(), 'x_max': self.x_max.value(), 'auto_x': self.auto_x.isChecked(),
            'y_min': self.y_min.value(), 'y_max': self.y_max.value(), 'auto_y': self.auto_y.isChecked(),
        }
        d.update(self._font_grp.collect())
        if hasattr(self, 'mode_combo'):
            d['display_mode'] = self.mode_combo.currentText()
            d['normalize_samples'] = self.norm_cb.isChecked()
        if hasattr(self, '_sc'):
            d['sample_colors'] = dict(self._sc)
        if hasattr(self, '_sample_edits'):
            d['sample_name_mappings'] = {k: v.text() for k, v in self._sample_edits.items()}
        if hasattr(self, '_single_color'):
            d.setdefault('sample_colors', {})['single_sample'] = self._single_color
        return d


# ── Drawing helpers (PyQtGraph) ────────────────────────────────────────

def _draw_histogram_bars(plot_item, ratios, cfg, color):
    """Draw histogram bars for ratio values."""
    bins = cfg.get('bins', 50)
    log_x = cfg.get('log_x', True)
    log_y = cfg.get('log_y', False)

    pr = np.log10(ratios) if log_x else ratios.copy()
    y, edges = np.histogram(pr, bins=bins)
    if log_y:
        y = np.log10(y + 1)

    co = QColor(color)
    alpha = int(cfg.get('alpha', 0.7) * 255)
    bb = cfg.get('bin_borders', True)
    pw = 1 if bb else 0
    pc = 'k' if bb else color

    centres = (edges[:-1] + edges[1:]) / 2
    bw = edges[1] - edges[0]
    bar = pg.BarGraphItem(x=centres, height=y, width=bw,
                          brush=pg.mkBrush(co.red(), co.green(), co.blue(), alpha),
                          pen=pg.mkPen(color=pc, width=pw))
    plot_item.addItem(bar)
    return pr, edges, y


def _add_density_curve(plot_item, values, cfg, edges, total):
    """KDE density curve scaled to histogram counts."""
    try:
        bw = edges[1] - edges[0] if len(edges) > 1 else 1.0
        xmin, xmax = min(values), max(values)
        xr = xmax - xmin
        xc = np.linspace(xmin - 0.1*xr, xmax + 0.1*xr, 200)
        kde = gaussian_kde(values)
        yc = kde(xc) * total * bw
        if cfg.get('log_y', False):
            yc = np.log10(yc + 1)
        plot_item.addItem(pg.PlotDataItem(x=xc, y=yc, pen=pg.mkPen('#2C3E50', width=2.5)))
    except Exception as e:
        print(f"Density curve error: {e}")


def _add_median_line(plot_item, values, cfg):
    """Add median vertical dashed line with annotation."""
    med = np.median(values)
    fc = cfg.get('font_color', '#000000')
    plot_item.addItem(pg.InfiniteLine(pos=med, angle=90,
        pen=pg.mkPen(color=fc, style=pg.QtCore.Qt.DashLine, width=2)))

    if cfg.get('log_x', True):
        txt = f'median: {10**med:.3f}'
    else:
        txt = f'median: {med:.3f}'

    ti = pg.TextItem(txt, anchor=(0, 1), color=fc)
    try:
        font = make_qfont(cfg)
        font.setPointSize(max(8, int(cfg.get('font_size', 18) * 0.8)))
        ti.setFont(font)
    except Exception:
        pass
    plot_item.addItem(ti)
    try:
        vr = plot_item.getViewBox().state['viewRange']
        ti.setPos(med, vr[1][0] + 0.9*(vr[1][1]-vr[1][0]))
    except Exception:
        ti.setPos(med, 1)


def _add_mean_line(plot_item, transformed, original, cfg):
    """Add mean ± SD vertical lines."""
    mu = np.mean(original)
    sd = np.std(original)
    fc = cfg.get('font_color', '#000000')
    lx = cfg.get('log_x', True)

    if lx:
        md = np.log10(mu)
        pd = np.log10(mu + sd)
        nd = np.log10(max(mu - sd, 0.001))
    else:
        md, pd, nd = mu, mu + sd, mu - sd

    plot_item.addItem(pg.InfiniteLine(pos=md, angle=90,
        pen=pg.mkPen(color=fc, style=pg.QtCore.Qt.SolidLine, width=2)))

    sc = QColor(fc); sc.setAlpha(100)
    plot_item.addItem(pg.InfiniteLine(pos=pd, angle=90,
        pen=pg.mkPen(color=sc, style=pg.QtCore.Qt.DotLine, width=1)))
    plot_item.addItem(pg.InfiniteLine(pos=nd, angle=90,
        pen=pg.mkPen(color=sc, style=pg.QtCore.Qt.DotLine, width=1)))

    txt = f'mean ± SD: {mu:.1f} ± {sd:.1f}'
    ti = pg.TextItem(txt, anchor=(0, 0), color=fc)
    try:
        font = make_qfont(cfg)
        font.setPointSize(max(8, int(cfg.get('font_size', 18) * 0.8)))
        ti.setFont(font)
    except Exception:
        pass
    plot_item.addItem(ti)
    try:
        vr = plot_item.getViewBox().state['viewRange']
        ti.setPos(md, vr[1][0] + 0.1*(vr[1][1]-vr[1][0]))
    except Exception:
        ti.setPos(md, 0.1)


def _add_stats_text(plot_item, ratios, cfg):
    """Add statistics text box."""
    num = cfg.get('numerator_element', '?')
    den = cfg.get('denominator_element', '?')
    lx = cfg.get('log_x', True)
    fc = cfg.get('font_color', '#000000')

    vals = 10**ratios if lx else ratios
    n = len(vals)
    mu, med, sd = np.mean(vals), np.median(vals), np.std(vals)
    q1, q3 = np.percentile(vals, [25, 75])

    lines = [
        f"Molar Ratio Statistics:",
        f"Ratio: {num}/{den}",
        f"Particles: {n}",
        f"Mean: {mu:.3f} ± {sd:.3f}",
        f"Median: {med:.3f}",
        f"Q1: {q1:.3f}, Q3: {q3:.3f}",
    ]
    ti = pg.TextItem('\n'.join(lines), anchor=(0, 1),
        border=pg.mkPen(color=fc, width=1),
        fill=pg.mkBrush(255, 255, 255, 200), color=fc)
    try:
        font = make_qfont(cfg)
        font.setPointSize(max(8, int(cfg.get('font_size', 18) * 0.8)))
        ti.setFont(font)
    except Exception:
        pass
    plot_item.addItem(ti)
    try:
        vr = plot_item.getViewBox().state['viewRange']
        ti.setPos(vr[0][0] + 0.02*(vr[0][1]-vr[0][0]),
                  vr[1][0] + 0.98*(vr[1][1]-vr[1][0]))
    except Exception:
        ti.setPos(0.02, 0.98)


def _draw_ratio_plot(plot_item, ratios, cfg, color):
    """Draw a complete ratio histogram with overlays."""
    if ratios is None or len(ratios) == 0:
        return
    pr, edges, _ = _draw_histogram_bars(plot_item, ratios, cfg, color)

    if cfg.get('show_curve', True) and len(ratios) > 5:
        _add_density_curve(plot_item, pr, cfg, edges, len(ratios))
    if cfg.get('show_median', True):
        _add_median_line(plot_item, pr, cfg)
    if cfg.get('show_mean', True):
        _add_mean_line(plot_item, pr, ratios, cfg)

    lx = cfg.get('log_x', True)
    ly = cfg.get('log_y', False)
    if not cfg.get('auto_x', True):
        xn, xx = cfg['x_min'], cfg['x_max']
        if lx: xn, xx = np.log10(xn), np.log10(xx)
        plot_item.setXRange(xn, xx)
    if not cfg.get('auto_y', True):
        yn, yx = cfg['y_min'], cfg['y_max']
        if ly: yn, yx = np.log10(yn + 1), np.log10(yx + 1)
        plot_item.setYRange(yn, yx)


# ── Display Dialog ─────────────────────────────────────────────────────

class MolarRatioDisplayDialog(QDialog):
    """Main dialog with PyQtGraph plot and right-click context menu."""

    def __init__(self, node, parent_window=None):
        super().__init__(parent_window)
        self.node = node
        self.setWindowTitle("Particle Data Molar Ratio Analysis")
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

        # Ratio label
        self._ratio_lbl = QLabel("")
        self._ratio_lbl.setStyleSheet(
            "color:#3B82F6; font-weight:bold; font-size:12px; padding:4px 8px; "
            "background:rgba(59,130,246,0.1); border-radius:4px; border:1px solid #3B82F6;")
        lay.addWidget(self._ratio_lbl)

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

        # Data type
        dm = menu.addMenu("Molar Data Type")
        for dt in MOLAR_DATA_TYPES:
            a = dm.addAction(dt); a.setCheckable(True)
            a.setChecked(cfg.get('data_type_display') == dt)
            a.triggered.connect(lambda _, v=dt: self._set('data_type_display', v))

        # Quick toggles
        tm = menu.addMenu("Quick Toggles")
        for key, label in [('show_curve', 'Density Curve'), ('show_median', 'Median Line'),
                           ('show_mean', 'Mean ± SD'), ('show_stats', 'Statistics'),
                           ('log_x', 'Log X-axis'), ('log_y', 'Log Y-axis'),
                           ('bin_borders', 'Bin Borders')]:
            a = tm.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        # Zero handling
        zm = menu.addMenu("Zero Handling")
        for z in ZERO_HANDLING:
            a = zm.addAction(z); a.setCheckable(True)
            a.setChecked(cfg.get('zero_handling') == z)
            a.triggered.connect(lambda _, v=z: self._set('zero_handling', v))

        # Display mode (multi)
        if _is_multi(self.node.input_data):
            mm = menu.addMenu("Display Mode")
            for m in MR_DISPLAY_MODES:
                a = mm.addAction(m); a.setCheckable(True)
                a.setChecked(cfg.get('display_mode') == m)
                a.triggered.connect(lambda _, v=m: self._set('display_mode', v))

        menu.addSeparator()
        menu.addAction("Configure…").triggered.connect(self._open_settings)
        menu.addAction("Download Figure…").triggered.connect(
            lambda: download_pyqtgraph_figure(self.pw, self, "molar_ratio_plot.png"))

        menu.exec(self.pw.mapToGlobal(pos))

    def _toggle(self, key):
        self.node.config[key] = not self.node.config.get(key, False)
        self._refresh()

    def _set(self, key, value):
        self.node.config[key] = value
        self._refresh()

    def _open_settings(self):
        elems = self.node.extract_available_elements()
        dlg = MolarRatioSettingsDialog(self.node.config, self.node.input_data, elems, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    # ── Refresh ──

    def _refresh(self):
        try:
            # Recreate plot widget to avoid PyQtGraph stale state
            parent_layout = self.pw.parent().layout()
            parent_layout.removeWidget(self.pw)
            self.pw.deleteLater()
            self.pw = pg.GraphicsLayoutWidget()
            self.pw.setBackground('w')
            self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
            self.pw.customContextMenuRequested.connect(self._ctx_menu)
            parent_layout.addWidget(self.pw)

            cfg = self.node.config
            num = cfg.get('numerator_element', '')
            den = cfg.get('denominator_element', '')
            self._ratio_lbl.setText(f"Ratio: {num} / {den}" if num and den else "Ratio: Select elements")

            plot_data = self.node.extract_plot_data()

            is_empty = (plot_data is None or
                        (isinstance(plot_data, dict) and
                         all(v is None or (hasattr(v, '__len__') and len(v) == 0) for v in plot_data.values())) or
                        (hasattr(plot_data, '__len__') and len(plot_data) == 0))

            if is_empty:
                pi = self.pw.addPlot()
                t = pg.TextItem("No molar ratio data available\nSelect two elements and connect data",
                                anchor=(0.5, 0.5), color='gray')
                pi.addItem(t); t.setPos(0.5, 0.5)
                pi.hideAxis('left'); pi.hideAxis('bottom')
                self._stats.setText("")
                return

            multi = _is_multi(self.node.input_data)
            if multi:
                mode = cfg.get('display_mode', MR_DISPLAY_MODES[0])
                if mode == 'Individual Subplots':
                    self._draw_subplots(plot_data, cfg)
                elif mode == 'Side by Side Subplots':
                    self._draw_side_by_side(plot_data, cfg)
                else:
                    pi = self.pw.addPlot()
                    self._draw_overlaid(pi, plot_data, cfg)
                    apply_font_to_pyqtgraph(pi, cfg)
            else:
                pi = self.pw.addPlot()
                self._draw_single(pi, plot_data, cfg)
                apply_font_to_pyqtgraph(pi, cfg)

            self._update_stats(plot_data, multi)
        except Exception as e:
            print(f"Error updating molar ratio: {e}")
            import traceback; traceback.print_exc()

    def _draw_single(self, pi, ratios, cfg):
        sc = cfg.get('sample_colors', {})
        color = sc.get('single_sample', '#663399')
        _draw_ratio_plot(pi, ratios, cfg, color)
        xl, yl = _xy_labels(cfg)
        set_axis_labels(pi, xl, yl, cfg)
        
        if cfg.get('log_x', True):
            pi.getAxis('bottom').setLogMode(True)
        if cfg.get('log_y', False):
            pi.getAxis('left').setLogMode(True)        
        if cfg.get('show_stats', True):
            pr = np.log10(ratios) if cfg.get('log_x', True) else ratios.copy()
            _add_stats_text(pi, pr, cfg)

    def _draw_overlaid(self, pi, plot_data, cfg):
        sc = cfg.get('sample_colors', {})
        legend_items = []
        for i, (sn, ratios) in enumerate(plot_data.items()):
            if ratios is not None and len(ratios) > 0:
                c = sc.get(sn, DEFAULT_SAMPLE_COLORS[i % len(DEFAULT_SAMPLE_COLORS)])
                pr, edges, y = _draw_histogram_bars(pi, ratios, cfg, c)
                legend_items.append((sn, c))
        xl, yl = _xy_labels(cfg)
        set_axis_labels(pi, xl, yl, cfg)
        
        if cfg.get('log_x', True):
            pi.getAxis('bottom').setLogMode(True)
        if cfg.get('log_y', False):
            pi.getAxis('left').setLogMode(True)        
        if legend_items:
            legend = pi.addLegend()
            for sn, c in legend_items:
                dn = get_display_name(sn, cfg)
                item = pg.PlotDataItem(pen=pg.mkPen(c, width=4))
                legend.addItem(item, dn)

    def _draw_subplots(self, plot_data, cfg):
        names = list(plot_data.keys())
        cols = min(3, len(names))
        rows = math.ceil(len(names) / cols)
        sc = cfg.get('sample_colors', {})
        for i, sn in enumerate(names):
            r, c = divmod(i, cols)
            pi = self.pw.addPlot(row=r, col=c)
            ratios = plot_data[sn]
            if ratios is not None and len(ratios) > 0:
                color = sc.get(sn, DEFAULT_SAMPLE_COLORS[i % len(DEFAULT_SAMPLE_COLORS)])
                _draw_ratio_plot(pi, ratios, cfg, color)
                pi.setTitle(get_display_name(sn, cfg))
                xl, yl = _xy_labels(cfg)
                set_axis_labels(pi, xl, yl, cfg)
                
                if cfg.get('log_x', True):
                    pi.getAxis('bottom').setLogMode(True)
                if cfg.get('log_y', False):
                    pi.getAxis('left').setLogMode(True)                
            apply_font_to_pyqtgraph(pi, cfg)

    def _draw_side_by_side(self, plot_data, cfg):
        names = list(plot_data.keys())
        sc = cfg.get('sample_colors', {})
        for i, sn in enumerate(names):
            pi = self.pw.addPlot(row=0, col=i)
            ratios = plot_data[sn]
            if ratios is not None and len(ratios) > 0:
                color = sc.get(sn, DEFAULT_SAMPLE_COLORS[i % len(DEFAULT_SAMPLE_COLORS)])
                _draw_ratio_plot(pi, ratios, cfg, color)
                pi.setTitle(get_display_name(sn, cfg))
                xl, yl = _xy_labels(cfg)
                set_axis_labels(pi, xl, yl if i == 0 else "", cfg)
                
                if cfg.get('log_x', True):
                    pi.getAxis('bottom').setLogMode(True)
                if cfg.get('log_y', False):
                    pi.getAxis('left').setLogMode(True)                
            apply_font_to_pyqtgraph(pi, cfg)

    def _update_stats(self, plot_data, multi):
        if multi:
            total = sum(len(v) for v in plot_data.values() if v is not None and hasattr(v, '__len__'))
            self._stats.setText(f"{len(plot_data)} samples  |  {total} total ratio values")
        else:
            self._stats.setText(f"{len(plot_data)} ratio values")


# ── Node ───────────────────────────────────────────────────────────────

class MolarRatioPlotNode(QObject):
    position_changed = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        super().__init__()
        self.title = "Molar Ratio"
        self.node_type = "molar_ratio_plot"
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
        dlg = MolarRatioDisplayDialog(self, parent_window)
        dlg.exec()
        return True

    def process_data(self, input_data):
        if not input_data:
            return
        self.input_data = input_data
        self.configuration_changed.emit()

    def extract_available_elements(self):
        if not self.input_data:
            return []
        sel = self.input_data.get('selected_isotopes', [])
        return [i['label'] for i in sel] if sel else []

    def extract_plot_data(self):
        if not self.input_data:
            return None
        num = self.config.get('numerator_element', '')
        den = self.config.get('denominator_element', '')
        if not num or not den or num == den:
            return None
        dk = MOLAR_DATA_KEY_MAP.get(self.config.get('data_type_display', MOLAR_DATA_TYPES[0]), 'element_moles_fmol')
        itype = self.input_data.get('type')
        if itype == 'sample_data':
            return self._extract_single(dk, num, den)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(dk, num, den)
        return None

    def _compute_ratios(self, particles, dk, num, den):
        mt = self.config.get('min_threshold', 0.001)
        zh = self.config.get('zero_handling', ZERO_HANDLING[0])
        ratios = []
        for p in particles:
            pd = p.get(dk, {})
            nv = pd.get(num, 0)
            dv = pd.get(den, 0)
            if zh == ZERO_HANDLING[0]:
                if nv <= 0 or dv <= 0 or np.isnan(nv) or np.isnan(dv):
                    continue
            else:
                if nv <= 0 or np.isnan(nv): nv = mt
                if dv <= 0 or np.isnan(dv): dv = mt
            if dv > 0:
                r = nv / dv
                if r > 0 and np.isfinite(r):
                    ratios.append(r)
        if not ratios:
            return None
        if self.config.get('filter_outliers', True):
            pct = self.config.get('outlier_percentile', 99.0)
            lo, hi = np.percentile(ratios, [100 - pct, pct])
            ratios = [r for r in ratios if lo <= r <= hi]
        return np.array(ratios) if ratios else None

    def _extract_single(self, dk, num, den):
        particles = self.input_data.get('particle_data')
        if not particles:
            return None
        return self._compute_ratios(particles, dk, num, den)

    def _extract_multi(self, dk, num, den):
        particles = self.input_data.get('particle_data', [])
        names = self.input_data.get('sample_names', [])
        if not particles:
            return None
        buckets = {n: [] for n in names}
        for p in particles:
            src = p.get('source_sample')
            if src and src in buckets:
                buckets[src].append(p)
        result = {}
        for sn, plist in buckets.items():
            r = self._compute_ratios(plist, dk, num, den)
            if r is not None and len(r) > 0:
                result[sn] = r
        return result if result else None