from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QColorDialog,
    QPushButton, QLineEdit, QFrame, QWidget, QMenu, QScrollArea,
    QDialogButtonBox, QMessageBox, QFileDialog, QListWidget,
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
    format_element_label, LABEL_MODES,
)
from results.shared_annotation import (
    AnnotationManager, FloatingInspector, AnnotationShelfButton,
    install_annotation_shortcuts,
)

try:
    from results.results_bar_charts import (
        EnhancedGraphicsLayoutWidget, _PlotWidgetAdapter,
    )
    try:
        from widget.custom_plot_widget import PlotSettingsDialog as _PlotSettingsDialog
        _CUSTOM_PLOT_AVAILABLE = True
    except Exception:
        _PlotSettingsDialog = None
        _CUSTOM_PLOT_AVAILABLE = False
except Exception:
    EnhancedGraphicsLayoutWidget = pg.GraphicsLayoutWidget
    _PlotWidgetAdapter = None
    _CUSTOM_PLOT_AVAILABLE = False

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

SHADE_TYPES = [
    'None',
    'Mean ± 1 SD',
    'Mean ± 2 SD',
    'Median ± IQR  (Q1–Q3)',
    'P5 – P95',
    'P1 – P99',
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
    'show_median_line': False,
    'median_line_color': '#0F6E56',
    'median_line_style': 'dash',
    'median_line_width': 2,
    'show_mean_line': False,
    'mean_line_color': '#B45309',
    'mean_line_style': 'solid',
    'mean_line_width': 2,
    'show_mode_marker': False,
    'mode_line_color': '#7C3AED',
    'mode_line_style': 'dot',
    'mode_line_width': 2,
    'shade_type': 'None',
    'shade_color': '#534AB7',
    'shade_alpha': 0.18,
    'show_ref_line': False,
    'ref_line_value': 1.0,
    'ref_line_label': '',
    'ref_line_color': '#A32D2D',
    'ref_line_style': 'dash',
    'ref_line_width': 2,
    'show_box': True,
    'x_min': 0.01, 'x_max': 100.0, 'auto_x': True,
    'y_min': 0, 'y_max': 100, 'auto_y': True,
    'display_mode': MR_DISPLAY_MODES[0],
    'sample_colors': {},
    'sample_name_mappings': {},
    'sample_order': [],
    'label_mode': 'Symbol',
    'font_family': 'Times New Roman',
    'font_size': 18,
    'font_bold': False,
    'font_italic': False,
    'font_color': '#000000',
    'annotations': [],
}


# ── Helpers ────────────────────────────────────────────────────────────

def _is_multi(input_data):
    """
    Args:
        input_data (Any): The input data.
    Returns:
        object: Result of the operation.
    """
    return input_data and input_data.get('type') == 'multiple_sample_data'


def _xy_labels(cfg):
    """
    Args:
        cfg (Any): The cfg.
    Returns:
        tuple: Result of the operation.
    """
    num = cfg.get('numerator_element', 'Element1')
    den = cfg.get('denominator_element', 'Element2')
    lm = cfg.get('label_mode', 'Symbol')
    num = format_element_label(num, lm)
    den = format_element_label(den, lm)
    xl = f"{num}/{den}"
    yl = "Number of Particles"
    return xl, yl


# ── Settings Dialog ────────────────────────────────────────────────────

class MolarRatioSettingsDialog(QDialog):
    """Full settings dialog opened from context menu."""

    def __init__(self, cfg, input_data, available_elements, parent=None):
        """
        Args:
            cfg (Any): The cfg.
            input_data (Any): The input data.
            available_elements (Any): The available elements.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("Molar Ratio Analysis Settings")
        self.setMinimumWidth(480)
        self._cfg = dict(cfg)
        self._input_data = input_data
        self._elements = available_elements or []
        self._build_ui()

    def _build_ui(self):
        """
        Returns:
            tuple: Result of the operation.
        """
        root = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); lay = QVBoxLayout(inner)
        scroll.setWidget(inner); root.addWidget(scroll)

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
        self.label_mode = QComboBox()
        self.label_mode.addItems(LABEL_MODES)
        self.label_mode.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
        f1.addRow("Element Label:", self.label_mode)
        lay.addWidget(g1)

        g2 = QGroupBox("Molar Data Type")
        f2 = QFormLayout(g2)
        self.dtype_combo = QComboBox(); self.dtype_combo.addItems(MOLAR_DATA_TYPES)
        self.dtype_combo.setCurrentText(self._cfg.get('data_type_display', MOLAR_DATA_TYPES[0]))
        f2.addRow("Type:", self.dtype_combo)
        lay.addWidget(g2)

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

        if _is_multi(self._input_data):
            gm = QGroupBox("Multiple Sample Display")
            fm = QFormLayout(gm)
            self.mode_combo = QComboBox()
            self.mode_combo.addItems(MR_DISPLAY_MODES)
            self.mode_combo.setCurrentText(
                self._cfg.get('display_mode', MR_DISPLAY_MODES[0]))
            fm.addRow("Display Mode:", self.mode_combo)
            lay.addWidget(gm)

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
        self.stats_cb = QCheckBox(); self.stats_cb.setChecked(self._cfg.get('show_stats', True))
        f4.addRow("Statistics Box:", self.stats_cb)
        self.box_cb = QCheckBox(); self.box_cb.setChecked(self._cfg.get('show_box', True))
        f4.addRow("Figure Box (frame):", self.box_cb)
        self.lx_cb = QCheckBox(); self.lx_cb.setChecked(self._cfg.get('log_x', True))
        f4.addRow("Log X:", self.lx_cb)
        self.ly_cb = QCheckBox(); self.ly_cb.setChecked(self._cfg.get('log_y', False))
        f4.addRow("Log Y:", self.ly_cb)
        lay.addWidget(g4)

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

        gs = QGroupBox("Statistical Overlays  (applied to all subplots)")
        fs = QFormLayout(gs)

        def _line_row(color_key, style_key, width_key, defaults):
            """
            Args:
                color_key (Any): The color key.
                style_key (Any): The style key.
                width_key (Any): The width key.
                defaults (Any): The defaults.
            Returns:
                tuple: Result of the operation.
            """
            row = QHBoxLayout()
            color_holder = [self._cfg.get(color_key, defaults[0])]
            btn = QPushButton(); btn.setFixedSize(26, 22)
            btn.setStyleSheet(f"background:{color_holder[0]};")
            def _pick(h=color_holder, b=btn):
                """
                Args:
                    h (Any): The h.
                    b (Any): The b.
                """
                c = QColorDialog.getColor(QColor(h[0]), self)
                if c.isValid():
                    h[0] = c.name(); b.setStyleSheet(f"background:{h[0]};")
            btn.clicked.connect(_pick)
            sc = QComboBox(); sc.addItems(['solid', 'dash', 'dot'])
            sc.setCurrentText(self._cfg.get(style_key, defaults[1]))
            sc.setFixedWidth(64)
            ws = QSpinBox(); ws.setRange(1, 5)
            ws.setValue(self._cfg.get(width_key, defaults[2]))
            ws.setFixedWidth(44)
            row.addWidget(btn); row.addWidget(sc)
            row.addWidget(QLabel("w:")); row.addWidget(ws)
            row.addStretch()
            return row, color_holder, sc, ws

        r, self._med_color, self._med_style, self._med_width = \
            _line_row('median_line_color', 'median_line_style', 'median_line_width',
                      ['#0F6E56', 'dash', 2])
        med_row = QHBoxLayout()
        self.median_line_cb = QCheckBox()
        self.median_line_cb.setChecked(self._cfg.get('show_median_line', False))
        med_row.addWidget(self.median_line_cb); med_row.addLayout(r)
        fs.addRow("Median Line:", med_row)

        r, self._mean_color, self._mean_style, self._mean_width = \
            _line_row('mean_line_color', 'mean_line_style', 'mean_line_width',
                      ['#B45309', 'solid', 2])
        mean_row = QHBoxLayout()
        self.mean_line_cb = QCheckBox()
        self.mean_line_cb.setChecked(self._cfg.get('show_mean_line', False))
        mean_row.addWidget(self.mean_line_cb); mean_row.addLayout(r)
        fs.addRow("Mean Line:", mean_row)

        r, self._mode_color, self._mode_style, self._mode_width = \
            _line_row('mode_line_color', 'mode_line_style', 'mode_line_width',
                      ['#7C3AED', 'dot', 2])
        mode_row = QHBoxLayout()
        self.mode_marker_cb = QCheckBox()
        self.mode_marker_cb.setChecked(self._cfg.get('show_mode_marker', False))
        mode_row.addWidget(self.mode_marker_cb); mode_row.addLayout(r)
        fs.addRow("Mode Marker:", mode_row)

        self.shade_combo = QComboBox()
        self.shade_combo.addItems(SHADE_TYPES)
        self.shade_combo.setCurrentText(self._cfg.get('shade_type', 'None'))
        fs.addRow("Shaded Region:", self.shade_combo)
        shade_row = QHBoxLayout()
        self._shade_color = self._cfg.get('shade_color', '#534AB7')
        self.shade_color_btn = QPushButton()
        self.shade_color_btn.setFixedSize(26, 22)
        self.shade_color_btn.setStyleSheet(f"background:{self._shade_color};")
        self.shade_color_btn.setToolTip("Pick shade color")
        self.shade_color_btn.clicked.connect(self._pick_shade_color)
        self.shade_alpha_spin = QDoubleSpinBox()
        self.shade_alpha_spin.setRange(0.01, 1.0)
        self.shade_alpha_spin.setDecimals(2)
        self.shade_alpha_spin.setValue(self._cfg.get('shade_alpha', 0.18))
        shade_row.addWidget(self.shade_color_btn)
        shade_row.addWidget(QLabel("α:"))
        shade_row.addWidget(self.shade_alpha_spin)
        shade_row.addStretch()
        fs.addRow("Shade Color / α:", shade_row)
        lay.addWidget(gs)

        gr = QGroupBox("Reference Line")
        fr = QFormLayout(gr)
        ref_top = QHBoxLayout()
        self.ref_line_cb = QCheckBox("Show")
        self.ref_line_cb.setChecked(self._cfg.get('show_ref_line', False))
        self.ref_val_spin = QDoubleSpinBox()
        self.ref_val_spin.setRange(0.0001, 999999); self.ref_val_spin.setDecimals(4)
        self.ref_val_spin.setValue(self._cfg.get('ref_line_value', 1.0))
        ref_top.addWidget(self.ref_line_cb)
        ref_top.addWidget(QLabel("Value:")); ref_top.addWidget(self.ref_val_spin)
        ref_top.addStretch()
        fr.addRow("", ref_top)

        self.ref_label_edit = QLineEdit(self._cfg.get('ref_line_label', ''))
        self.ref_label_edit.setPlaceholderText("Auto  (e.g.  Mg:Al = 1)")
        fr.addRow("Label:", self.ref_label_edit)

        r, self._ref_color, self._ref_style, self._ref_width = \
            _line_row('ref_line_color', 'ref_line_style', 'ref_line_width',
                      ['#A32D2D', 'dash', 2])
        fr.addRow("Style:", r)
        lay.addWidget(gr)

        if _is_multi(self._input_data):
            names = self._input_data.get('sample_names', [])
            if names:
                g6 = QGroupBox("Sample Names")
                v6 = QVBoxLayout(g6)
                self._sample_edits = {}
                nm = dict(self._cfg.get('sample_name_mappings', {}))
                for sn in names:
                    h = QHBoxLayout()
                    h.addWidget(QLabel(sn[:20]))
                    ed = QLineEdit(nm.get(sn, sn))
                    ed.setFixedWidth(200)
                    h.addWidget(ed)
                    self._sample_edits[sn] = ed
                    rst = QPushButton("\u21ba")
                    rst.setFixedSize(22, 22)
                    rst.clicked.connect(
                        lambda _, o=sn: self._sample_edits[o].setText(o))
                    h.addWidget(rst)
                    h.addStretch()
                    w = QWidget(); w.setLayout(h); v6.addWidget(w)
                lay.addWidget(g6)

                g7 = QGroupBox("Sample Display Order")
                v7 = QVBoxLayout(g7)
                hint = QLabel(
                    "Drag or use \u2191\u2193 to reorder \u2014 useful for time series.")
                hint.setStyleSheet("color:#6B7280; font-size:10px;")
                hint.setWordWrap(True)
                v7.addWidget(hint)
                from PySide6.QtWidgets import QAbstractItemView as _AIV
                self._order_list = QListWidget()
                self._order_list.setMaximumHeight(130)
                self._order_list.setDragDropMode(_AIV.InternalMove)
                cur_order = self._cfg.get('sample_order', [])
                ordered = [s for s in cur_order if s in names]
                ordered += [s for s in names if s not in ordered]
                for s in ordered:
                    self._order_list.addItem(s)
                v7.addWidget(self._order_list)
                btn_row = QHBoxLayout()
                up_btn = QPushButton("\u2191  Up")
                up_btn.setFixedWidth(72)
                up_btn.clicked.connect(self._move_up)
                dn_btn = QPushButton("\u2193  Down")
                dn_btn.setFixedWidth(72)
                dn_btn.clicked.connect(self._move_down)
                btn_row.addWidget(up_btn); btn_row.addWidget(dn_btn)
                btn_row.addStretch()
                v7.addLayout(btn_row)
                lay.addWidget(g7)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _move_up(self):
        row = self._order_list.currentRow()
        if row > 0:
            item = self._order_list.takeItem(row)
            self._order_list.insertItem(row - 1, item)
            self._order_list.setCurrentRow(row - 1)

    def _move_down(self):
        row = self._order_list.currentRow()
        if row < self._order_list.count() - 1:
            item = self._order_list.takeItem(row)
            self._order_list.insertItem(row + 1, item)
            self._order_list.setCurrentRow(row + 1)

    def _pick_shade_color(self):
        c = QColorDialog.getColor(QColor(self._shade_color), self, "Shade Color")
        if c.isValid():
            self._shade_color = c.name()
            self.shade_color_btn.setStyleSheet(f"background:{self._shade_color};")

    def collect(self):
        """
        Returns:
            object: Result of the operation.
        """
        d = {
            'numerator_element': self.num_combo.currentText(),
            'denominator_element': self.den_combo.currentText(),
            'data_type_display': self.dtype_combo.currentText(),
            'label_mode': self.label_mode.currentText(),
            'min_threshold': self.thresh_spin.value(),
            'zero_handling': self.zero_combo.currentText(),
            'filter_outliers': self.outlier_cb.isChecked(),
            'outlier_percentile': self.pct_spin.value(),
            'bins': self.bins_spin.value(),
            'alpha': self.alpha_spin.value(),
            'bin_borders': self.borders_cb.isChecked(),
            'show_curve': self.curve_cb.isChecked(),
            'show_stats': self.stats_cb.isChecked(),
            'show_box': self.box_cb.isChecked(),
            'show_median_line': self.median_line_cb.isChecked(),
            'median_line_color': self._med_color[0],
            'median_line_style': self._med_style.currentText(),
            'median_line_width': self._med_width.value(),
            'show_mean_line': self.mean_line_cb.isChecked(),
            'mean_line_color': self._mean_color[0],
            'mean_line_style': self._mean_style.currentText(),
            'mean_line_width': self._mean_width.value(),
            'show_mode_marker': self.mode_marker_cb.isChecked(),
            'mode_line_color': self._mode_color[0],
            'mode_line_style': self._mode_style.currentText(),
            'mode_line_width': self._mode_width.value(),
            'shade_type': self.shade_combo.currentText(),
            'shade_color': self._shade_color,
            'shade_alpha': self.shade_alpha_spin.value(),
            'show_ref_line': self.ref_line_cb.isChecked(),
            'ref_line_value': self.ref_val_spin.value(),
            'ref_line_label': self.ref_label_edit.text().strip(),
            'ref_line_color': self._ref_color[0],
            'ref_line_style': self._ref_style.currentText(),
            'ref_line_width': self._ref_width.value(),
            'log_x': self.lx_cb.isChecked(),
            'log_y': self.ly_cb.isChecked(),
            'x_min': self.x_min.value(), 'x_max': self.x_max.value(),
            'auto_x': self.auto_x.isChecked(),
            'y_min': self.y_min.value(), 'y_max': self.y_max.value(),
            'auto_y': self.auto_y.isChecked(),
        }
        if hasattr(self, 'mode_combo'):
            d['display_mode'] = self.mode_combo.currentText()
        if hasattr(self, '_sample_edits'):
            d['sample_name_mappings'] = {
                k: v.text() for k, v in self._sample_edits.items()}
        if hasattr(self, '_order_list'):
            d['sample_order'] = [
                self._order_list.item(i).text()
                for i in range(self._order_list.count())]
        return d


# ── Drawing helpers (PyQtGraph) ────────────────────────────────────────

def _draw_histogram_bars(plot_item, ratios, cfg, color):
    """Draw histogram bars for ratio values.
    Args:
        plot_item (Any): The plot item.
        ratios (Any): The ratios.
        cfg (Any): The cfg.
        color (Any): Colour value.
    Returns:
        tuple: Result of the operation.
    """
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
    pc = cfg.get('font_color', '#000000') if bb else color

    centres = (edges[:-1] + edges[1:]) / 2
    bw = edges[1] - edges[0]
    bar = pg.BarGraphItem(x=centres, height=y, width=bw,
                          brush=pg.mkBrush(co.red(), co.green(), co.blue(), alpha),
                          pen=pg.mkPen(color=pc, width=pw))
    plot_item.addItem(bar)
    return pr, edges, y


def _add_density_curve(plot_item, values, cfg, edges, total):
    """KDE density curve scaled to histogram counts.
    Args:
        plot_item (Any): The plot item.
        values (Any): Array or sequence of values.
        cfg (Any): The cfg.
        edges (Any): The edges.
        total (Any): The total.
    """
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


def _apply_box(plot_item, cfg):
    """Show or hide the figure frame (top + right axes = closed box).
    Args:
        plot_item (Any): The plot item.
        cfg (Any): The cfg.
    """
    show = cfg.get('show_box', True)
    plot_item.showAxis('top', show)
    plot_item.showAxis('right', show)
    if show:
        plot_item.getAxis('top').setStyle(showValues=False)
        plot_item.getAxis('right').setStyle(showValues=False)


_QT_LINE = {
    'solid': pg.QtCore.Qt.SolidLine,
    'dash':  pg.QtCore.Qt.DashLine,
    'dot':   pg.QtCore.Qt.DotLine,
}


def _add_ref_line(plot_item, cfg):
    """Draw a customisable reference vertical line (e.g. ratio = 1).
    Args:
        plot_item (Any): The plot item.
        cfg (Any): The cfg.
    """
    if not cfg.get('show_ref_line', False):
        return
    log_x = cfg.get('log_x', True)
    val = float(cfg.get('ref_line_value', 1.0))
    if val <= 0:
        return
    pos = float(np.log10(val)) if log_x else val
    color = cfg.get('ref_line_color', '#A32D2D')
    style = _QT_LINE.get(cfg.get('ref_line_style', 'dash'), pg.QtCore.Qt.DashLine)
    width = int(cfg.get('ref_line_width', 2))
    lm = cfg.get('label_mode', 'Symbol')
    num = format_element_label(cfg.get('numerator_element') or 'X', lm)
    den = format_element_label(cfg.get('denominator_element') or 'Y', lm)
    custom_lbl = cfg.get('ref_line_label', '').strip()
    label = custom_lbl if custom_lbl else f"{num}:{den} = {val:g}"
    line = pg.InfiniteLine(
        pos=pos, angle=90,
        pen=pg.mkPen(color=color, style=style, width=width),
        label=label,
        labelOpts={'color': color, 'movable': False, 'position': 0.55,
                   'anchors': [(0, 1), (0, 1)]},
    )
    line.setZValue(5)
    plot_item.addItem(line)


def _add_stat_lines(plot_item, values, cfg):
    """Draw median / mean / mode marker lines.

    ``values`` must already be in plot-space (log10 if log_x is True).
    Lines are drawn as pg.InfiniteLine with built-in labels — no floating
    TextItem so they can't be mispositioned by view-range race conditions.
    Colors, styles and widths are all customisable via cfg.
    Args:
        plot_item (Any): The plot item.
        values (Any): Array or sequence of values.
        cfg (Any): The cfg.
    """
    if len(values) == 0:
        return
    log_x = cfg.get('log_x', True)

    # ── Median line ───────────────────────────────────────────────────
    if cfg.get('show_median_line', False):
        med = float(np.median(values))
        med_real = 10**med if log_x else med
        color = cfg.get('median_line_color', '#0F6E56')
        style = _QT_LINE.get(cfg.get('median_line_style', 'dash'), pg.QtCore.Qt.DashLine)
        width = int(cfg.get('median_line_width', 2))
        plot_item.addItem(pg.InfiniteLine(
            pos=med, angle=90,
            pen=pg.mkPen(color=color, style=style, width=width),
            label=f'median: {med_real:.3g}',
            labelOpts={'color': color, 'movable': False, 'position': 0.92,
                       'anchors': [(0, 1), (0, 1)]},
        ))

    # ── Mean line ─────────────────────────────────────────────────────
    if cfg.get('show_mean_line', False):
        real_vals = 10**values if log_x else values
        mu = float(np.mean(real_vals))
        mu_plot = float(np.log10(max(mu, 1e-12))) if log_x else mu
        color = cfg.get('mean_line_color', '#B45309')
        style = _QT_LINE.get(cfg.get('mean_line_style', 'solid'), pg.QtCore.Qt.SolidLine)
        width = int(cfg.get('mean_line_width', 2))
        plot_item.addItem(pg.InfiniteLine(
            pos=mu_plot, angle=90,
            pen=pg.mkPen(color=color, style=style, width=width),
            label=f'mean: {mu:.3g}',
            labelOpts={'color': color, 'movable': False, 'position': 0.80,
                       'anchors': [(0, 1), (0, 1)]},
        ))

    # ── Mode marker ───────────────────────────────────────────────────
    if cfg.get('show_mode_marker', False) and len(values) > 3:
        try:
            bins = max(10, int(cfg.get('bins', 50)))
            counts, edges = np.histogram(values, bins=bins)
            peak_idx = int(np.argmax(counts))
            peak_x = float((edges[peak_idx] + edges[peak_idx + 1]) / 2)
            peak_real = 10**peak_x if log_x else peak_x
            color = cfg.get('mode_line_color', '#7C3AED')
            style = _QT_LINE.get(cfg.get('mode_line_style', 'dot'), pg.QtCore.Qt.DotLine)
            width = int(cfg.get('mode_line_width', 2))
            plot_item.addItem(pg.InfiniteLine(
                pos=peak_x, angle=90,
                pen=pg.mkPen(color=color, style=style, width=width),
                label=f'mode: {peak_real:.3g}',
                labelOpts={'color': color, 'movable': False, 'position': 0.68,
                           'anchors': [(0, 1), (0, 1)]},
            ))
        except Exception as e:
            print(f"[mode marker] {e}")


def _add_shaded_region(plot_item, values, cfg):
    """Draw a statistical shaded band — applied to every subplot.

    ``values`` must already be in plot-space (log10 if log_x is True).
    Args:
        plot_item (Any): The plot item.
        values (Any): Array or sequence of values.
        cfg (Any): The cfg.
    Returns:
        object: Result of the operation.
    """
    shade_type = cfg.get('shade_type', 'None')
    if shade_type == 'None' or len(values) < 3:
        return

    log_x = cfg.get('log_x', True)
    color = cfg.get('shade_color', '#534AB7')
    alpha = int(cfg.get('shade_alpha', 0.18) * 255)
    real_vals = 10**values if log_x else values

    def _to_plot(v):
        """
        Args:
            v (Any): The v.
        Returns:
            object: Result of the operation.
        """
        if log_x:
            return float(np.log10(max(float(v), 1e-12)))
        return float(v)

    lo = hi = None

    if shade_type == 'Mean ± 1 SD':
        mu, sd = float(np.mean(real_vals)), float(np.std(real_vals))
        lo = _to_plot(mu - sd) if not log_x else _to_plot(max(mu - sd, 1e-12))
        hi = _to_plot(mu + sd)

    elif shade_type == 'Mean ± 2 SD':
        mu, sd = float(np.mean(real_vals)), float(np.std(real_vals))
        lo = _to_plot(mu - 2*sd) if not log_x else _to_plot(max(mu - 2*sd, 1e-12))
        hi = _to_plot(mu + 2*sd)

    elif shade_type == 'Median ± IQR  (Q1–Q3)':
        q1, q3 = np.percentile(real_vals, [25, 75])
        lo = _to_plot(q1)
        hi = _to_plot(q3)

    elif shade_type == 'P5 – P95':
        p5, p95 = np.percentile(real_vals, [5, 95])
        lo = _to_plot(p5)
        hi = _to_plot(p95)

    elif shade_type == 'P1 – P99':
        p1, p99 = np.percentile(real_vals, [1, 99])
        lo = _to_plot(p1)
        hi = _to_plot(p99)

    if lo is None or hi is None or not np.isfinite(lo) or not np.isfinite(hi):
        return

    qc = QColor(color)
    qc.setAlpha(alpha)
    band = pg.LinearRegionItem(
        values=(min(lo, hi), max(lo, hi)),
        orientation='vertical',
        brush=pg.mkBrush(qc),
        pen=pg.mkPen(color, width=0.8, style=pg.QtCore.Qt.DashLine),
        movable=False,
    )
    band.setZValue(-10)
    plot_item.addItem(band)


def _add_stats_text(plot_item, ratios, cfg):
    """Add statistics text box.
    Args:
        plot_item (Any): The plot item.
        ratios (Any): The ratios.
        cfg (Any): The cfg.
    """
    lm = cfg.get('label_mode', 'Symbol')
    num = format_element_label(cfg.get('numerator_element', '?'), lm)
    den = format_element_label(cfg.get('denominator_element', '?'), lm)
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
    """Draw a complete ratio histogram with overlays (applied to every subplot).
    Args:
        plot_item (Any): The plot item.
        ratios (Any): The ratios.
        cfg (Any): The cfg.
        color (Any): Colour value.
    """
    if ratios is None or len(ratios) == 0:
        return
    pr, edges, _ = _draw_histogram_bars(plot_item, ratios, cfg, color)

    if cfg.get('show_curve', True) and len(ratios) > 5:
        _add_density_curve(plot_item, pr, cfg, edges, len(ratios))

    _add_shaded_region(plot_item, pr, cfg)
    _add_stat_lines(plot_item, pr, cfg)
    _add_ref_line(plot_item, cfg)

    _apply_box(plot_item, cfg)

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
        """
        Args:
            node (Any): Tree or graph node.
            parent_window (Any): The parent window.
        """
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

        self._ratio_lbl = QLabel("")
        self._ratio_lbl.setStyleSheet(
            "color:#3B82F6; font-weight:bold; font-size:12px; padding:4px 8px; "
            "background:rgba(59,130,246,0.1); border-radius:4px; border:1px solid #3B82F6;")
        lay.addWidget(self._ratio_lbl)

        self._stats = QLabel("")
        self._stats.setStyleSheet("color:#6B7280; font-size:11px; padding:2px 6px;")
        lay.addWidget(self._stats)

        self.node.config.setdefault('annotations', [])

        self.ann_mgr = AnnotationManager(self.node.config, parent=self)

        self._plot_container = QWidget()
        self._plot_container_layout = QVBoxLayout(self._plot_container)
        self._plot_container_layout.setContentsMargins(0, 0, 0, 0)
        self._plot_container_layout.setSpacing(0)

        self.pw = EnhancedGraphicsLayoutWidget()
        self.pw.setBackground('w')
        self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pw.customContextMenuRequested.connect(self._ctx_menu)
        self._plot_container_layout.addWidget(self.pw)

        self._primary_plot_item = None

        self.ann_inspector = FloatingInspector(self.ann_mgr, parent=self._plot_container)
        self.ann_inspector.set_plot_accessor(
            lambda: (self.pw, self._primary_plot_item))

        lay.addWidget(self._plot_container, stretch=1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(6, 0, 6, 0)

        self._hint_lbl = QLabel("Use the annotation shelf (bottom-right) to add figure annotations")
        self._hint_lbl.setStyleSheet(
            "color: #999; font-size: 11px; font-style: italic;")
        bottom.addWidget(self._hint_lbl)
        bottom.addStretch(1)

        self.ann_shelf = AnnotationShelfButton(self.ann_mgr)
        bottom.addWidget(self.ann_shelf)

        lay.addLayout(bottom)

        self.ann_mgr.sig_annotations_changed.connect(self._refresh_hint)
        self._refresh_hint()

        install_annotation_shortcuts(self, self.ann_mgr)

    def _refresh_hint(self):
        """Show hint only when the plot has zero annotations."""
        self._hint_lbl.setVisible(len(self.node.config.get('annotations', [])) == 0)


    def _ctx_menu(self, pos):
        """
        Args:
            pos (Any): Position point.
        """
        cfg = self.node.config
        menu = QMenu(self)

        dm = menu.addMenu("Molar Data Type")
        for dt in MOLAR_DATA_TYPES:
            a = dm.addAction(dt); a.setCheckable(True)
            a.setChecked(cfg.get('data_type_display') == dt)
            a.triggered.connect(lambda _, v=dt: self._set('data_type_display', v))

        elems = self.node.extract_available_elements()
        if elems:
            nm = menu.addMenu("Numerator Element")
            for e in elems:
                a = nm.addAction(e); a.setCheckable(True)
                a.setChecked(e == cfg.get('numerator_element', ''))
                a.triggered.connect(lambda _, el=e: self._set('numerator_element', el))
            dm2 = menu.addMenu("Denominator Element")
            for e in elems:
                a = dm2.addAction(e); a.setCheckable(True)
                a.setChecked(e == cfg.get('denominator_element', ''))
                a.triggered.connect(lambda _, el=e: self._set('denominator_element', el))

        tm = menu.addMenu("Quick Toggles")

        for key, label in [
            ('show_curve',  'Density Curve'),
            ('show_stats',  'Statistics Box'),
            ('log_x',       'Log X-axis'),
            ('log_y',       'Log Y-axis'),
            ('bin_borders', 'Bin Borders'),
            ('show_box',    'Figure Box (frame)'),
        ]:
            a = tm.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        tm.addSeparator()
        sep1 = tm.addAction("── Stat Lines ──"); sep1.setEnabled(False)

        for key, label in [
            ('show_ref_line',    'Reference Line'),
            ('show_median_line', 'Median Line'),
            ('show_mean_line',   'Mean Line'),
            ('show_mode_marker', 'Mode Marker'),
        ]:
            a = tm.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        tm.addSeparator()
        sep2 = tm.addAction("── Shaded Region ──"); sep2.setEnabled(False)

        shm = tm.addMenu("Shade Type")
        for st in SHADE_TYPES:
            a = shm.addAction(st); a.setCheckable(True)
            a.setChecked(cfg.get('shade_type', 'None') == st)
            a.triggered.connect(lambda _, v=st: self._set('shade_type', v))

        zm = menu.addMenu("Zero Handling")
        for z in ZERO_HANDLING:
            a = zm.addAction(z); a.setCheckable(True)
            a.setChecked(cfg.get('zero_handling') == z)
            a.triggered.connect(lambda _, v=z: self._set('zero_handling', v))

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
        if _CUSTOM_PLOT_AVAILABLE:
            menu.addAction("\U0001f5bc  Plot Settings\u2026").triggered.connect(
                self._open_plot_settings)
        menu.exec(self.pw.mapToGlobal(pos))

    # ── Helpers ──────────────────────────

    def _current_ratios(self):
        """Return a 1-D numpy array of all current ratio values (pooled across
        samples if multi). Returns None if unavailable."""
        try:
            plot_data = self.node.extract_plot_data()
        except Exception:
            return None
        if plot_data is None:
            return None
        if _is_multi(self.node.input_data):
            if not isinstance(plot_data, dict):
                return None
            parts = [v for v in plot_data.values()
                     if v is not None and hasattr(v, '__len__') and len(v) > 0]
            if not parts:
                return None
            return np.concatenate([np.asarray(p).ravel() for p in parts])
        if hasattr(plot_data, '__len__') and len(plot_data) > 0:
            return np.asarray(plot_data).ravel()
        return None

    def _toggle(self, key):
        """
        Args:
            key (Any): Dictionary or storage key.
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

    def _open_settings(self):
        elems = self.node.extract_available_elements()
        dlg = MolarRatioSettingsDialog(self.node.config, self.node.input_data, elems, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_plot_settings(self):
        if not _CUSTOM_PLOT_AVAILABLE or _PlotSettingsDialog is None \
                or _PlotWidgetAdapter is None:
            return
        pi = next(
            (item for item in self.pw.scene().items()
             if isinstance(item, pg.PlotItem)),
            None,
        )
        if pi is not None:
            _PlotSettingsDialog(_PlotWidgetAdapter(self.pw, pi), self).exec()


    def _refresh(self):
        try:
            if hasattr(self, 'ann_mgr'):
                self.ann_mgr._detach_all()

            self._plot_container_layout.removeWidget(self.pw)
            self.pw.deleteLater()
            self.pw = EnhancedGraphicsLayoutWidget()
            self.pw.setBackground('w')
            self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
            self.pw.customContextMenuRequested.connect(self._ctx_menu)
            self._plot_container_layout.addWidget(self.pw)

            cfg = self.node.config
            lm = cfg.get('label_mode', 'Symbol')
            num = format_element_label(cfg.get('numerator_element', ''), lm)
            den = format_element_label(cfg.get('denominator_element', ''), lm)
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
                self._primary_plot_item = pi
                if hasattr(self, 'ann_mgr'):
                    self.ann_mgr.attach_plot(pi)
                if hasattr(self, 'ann_inspector'):
                    self.ann_inspector.attach(pi)
                return

            multi = _is_multi(self.node.input_data)
            primary_plot = None
            if multi:
                mode = cfg.get('display_mode', MR_DISPLAY_MODES[0])
                if mode == 'Individual Subplots':
                    self._draw_subplots(plot_data, cfg)
                    primary_plot = self.pw.getItem(0, 0)
                elif mode == 'Side by Side Subplots':
                    self._draw_side_by_side(plot_data, cfg)
                    primary_plot = self.pw.getItem(0, 0)
                else:
                    pi = self.pw.addPlot()
                    self._draw_overlaid(pi, plot_data, cfg)
                    apply_font_to_pyqtgraph(pi, cfg)
                    primary_plot = pi
            else:
                pi = self.pw.addPlot()
                self._draw_single(pi, plot_data, cfg)
                apply_font_to_pyqtgraph(pi, cfg)
                primary_plot = pi

            self._update_stats(plot_data, multi)

            self._primary_plot_item = primary_plot

            if hasattr(self, 'ann_mgr') and primary_plot is not None:
                self.ann_mgr.attach_plot(primary_plot)
            if hasattr(self, 'ann_inspector'):
                self.ann_inspector.attach(primary_plot)
        except Exception as e:
            print(f"Error updating molar ratio: {e}")
            import traceback; traceback.print_exc()

    def _draw_single(self, pi, ratios, cfg):
        """
        Args:
            pi (Any): The pi.
            ratios (Any): The ratios.
            cfg (Any): The cfg.
        """
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
        """
        Args:
            pi (Any): The pi.
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        sc = cfg.get('sample_colors', {})
        legend_items = []
        all_pr = []
        for i, (sn, ratios) in enumerate(plot_data.items()):
            if ratios is not None and len(ratios) > 0:
                c = sc.get(sn, DEFAULT_SAMPLE_COLORS[i % len(DEFAULT_SAMPLE_COLORS)])
                pr, edges, y = _draw_histogram_bars(pi, ratios, cfg, c)
                legend_items.append((sn, c))
                if cfg.get('show_curve', True) and len(ratios) > 5:
                    _add_density_curve(pi, pr, cfg, edges, len(ratios))
                all_pr.append(pr)
        if all_pr:
            pooled = np.concatenate(all_pr)
            _add_shaded_region(pi, pooled, cfg)
            _add_stat_lines(pi, pooled, cfg)
        _add_ref_line(pi, cfg)
        xl, yl = _xy_labels(cfg)
        set_axis_labels(pi, xl, yl, cfg)
        if cfg.get('log_x', True):
            pi.getAxis('bottom').setLogMode(True)
        if cfg.get('log_y', False):
            pi.getAxis('left').setLogMode(True)
        _apply_box(pi, cfg)
        if legend_items:
            legend = pi.addLegend()
            for sn, c in legend_items:
                dn = get_display_name(sn, cfg)
                item = pg.PlotDataItem(pen=pg.mkPen(c, width=4))
                legend.addItem(item, dn)

    def _draw_subplots(self, plot_data, cfg):
        """
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
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
        """
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
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
        """
        Args:
            plot_data (Any): The plot data.
            multi (Any): The multi.
        """
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
        """
        Args:
            parent_window (Any): The parent window.
        """
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
        dlg = MolarRatioDisplayDialog(self, parent_window)
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

    def extract_available_elements(self):
        """
        Returns:
            object: Result of the operation.
        """
        if not self.input_data:
            return []
        sel = self.input_data.get('selected_isotopes', [])
        return [i['label'] for i in sel] if sel else []

    def extract_plot_data(self):
        """
        Returns:
            None
        """
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
        """
        Args:
            particles (Any): The particles.
            dk (Any): The dk.
            num (Any): The num.
            den (Any): The den.
        Returns:
            object: Result of the operation.
        """
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
        """
        Args:
            dk (Any): The dk.
            num (Any): The num.
            den (Any): The den.
        Returns:
            object: Result of the operation.
        """
        particles = self.input_data.get('particle_data')
        if not particles:
            return None
        return self._compute_ratios(particles, dk, num, den)

    def _extract_multi(self, dk, num, den):
        """
        Args:
            dk (Any): The dk.
            num (Any): The num.
            den (Any): The den.
        Returns:
            object: Result of the operation.
        """
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