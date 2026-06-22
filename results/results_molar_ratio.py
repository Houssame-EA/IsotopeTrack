from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QColorDialog,
    QPushButton, QLineEdit, QWidget, QMenu, QScrollArea, QDialogButtonBox,
    QListWidget,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor
import pyqtgraph as pg
import numpy as np
import math
from scipy.stats import gaussian_kde

from results.shared_plot_utils import (
    DEFAULT_SAMPLE_COLORS, make_qfont,
    apply_font_to_pyqtgraph, set_axis_labels, FontSettingsGroup, get_display_name,
    download_pyqtgraph_figure, format_element_label, LABEL_MODES,
    Renderer,
    per_ml_active, per_ml_factor, conc_meta_available,
    single_sample_name, apply_sci_y_axis, HtmlAxisItem, pick_color_hex,
)
import logging
_itk_log = logging.getLogger("IsotopeTrack.results.results_molar_ratio")

try:
    from results.results_bar_charts import (
        EnhancedGraphicsLayoutWidget, _PlotWidgetAdapter,
    )
    try:
        from widget.custom_plot_widget import PlotSettingsDialog as _PlotSettingsDialog
        _CUSTOM_PLOT_AVAILABLE = True
    except Exception:
        _itk_log.exception("Handled exception in <module>")
        _PlotSettingsDialog = None
        _CUSTOM_PLOT_AVAILABLE = False
except Exception:
    _itk_log.exception("Handled exception in <module>")
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
    'Individual Subplots',
]

_MR_DISPLAY_MODE_ALIASES = {
    'Side by Side Subplots': 'Individual Subplots',
    'Combined with Legend': 'Overlaid (Different Colors)',
}

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
    'y_axis_unit': 'count',
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
    return input_data and input_data.get('type') == 'multiple_sample_data'


def _xy_labels(cfg):
    num = cfg.get('numerator_element', 'Element1')
    den = cfg.get('denominator_element', 'Element2')
    lm = cfg.get('label_mode', 'Symbol')
    num = format_element_label(num, lm)
    den = format_element_label(den, lm)
    xl = f"{num}/{den}"
    yl = "Particles/mL" if cfg.get('y_axis_unit', 'count') == 'per_ml' else "Number of Particles"
    return xl, yl


def _normalize_mr_display_mode(mode):
    """Normalize legacy/redundant display-mode values for Molar Ratio.

    Preserved behavior:
        Older configs that stored ``Side by Side Subplots`` or
        ``Combined with Legend`` remain loadable. They are mapped to the
        supported user-facing modes without changing ratio calculations.
    """
    return _MR_DISPLAY_MODE_ALIASES.get(mode, mode)


# ── Settings Dialog ────────────────────────────────────────────────────

class MolarRatioSettingsDialog(QDialog):
    """Scope-aware settings dialog for Molar Ratio format or quantities."""

    preview_requested = Signal(dict)

    def __init__(self, cfg, input_data, available_elements, parent=None, scope='all'):
        """
        Preserved behavior:
            ``all`` keeps legacy combined settings support. Scoped routes are
            used by the four-button UI so quantity and format edits are routed
            predictably without changing ratio science.
        """
        super().__init__(parent)
        if scope == 'format':
            self.setWindowTitle("Molar ratio plot format settings")
        elif scope == 'quantities':
            self.setWindowTitle("Molar ratio quantities configuration")
        else:
            self.setWindowTitle("Molar Ratio Analysis Settings")
        self.setMinimumWidth(480)
        self._cfg = dict(cfg)
        self._input_data = input_data
        self._elements = available_elements or []
        self._scope = scope

        self.num_combo = None
        self.den_combo = None
        self.label_mode = None
        self.dtype_combo = None
        self.mode_combo = None
        self.y_unit_combo = None
        self.bins_spin = None
        self.outlier_cb = None
        self.pct_spin = None
        self.alpha_spin = None
        self.borders_cb = None
        self.curve_cb = None
        self.stats_cb = None
        self.box_cb = None
        self.lx_cb = None
        self.ly_cb = None
        self.x_min = None
        self.x_max = None
        self.auto_x = None
        self.y_min = None
        self.y_max = None
        self.auto_y = None
        self._sample_edits = None
        self._order_list = None
        self._font_group = None
        self.median_line_cb = None
        self.mean_line_cb = None
        self.mode_marker_cb = None
        self._med_color = None
        self._med_style = None
        self._med_width = None
        self._mean_color = None
        self._mean_style = None
        self._mean_width = None
        self._mode_color = None
        self._mode_style = None
        self._mode_width = None
        self.shade_combo = None
        self._shade_color = None
        self.shade_alpha_spin = None
        self.ref_line_cb = None
        self.ref_val_spin = None
        self.ref_label_edit = None
        self._ref_color = None
        self._ref_style = None
        self._ref_width = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); lay = QVBoxLayout(inner)
        scroll.setWidget(inner); root.addWidget(scroll)

        if self._scope in ('all', 'quantities'):
            g1 = QGroupBox("Element Selection for Ratio")
            f1 = QFormLayout(g1)
            self.num_combo = QComboBox(); self.den_combo = QComboBox()
            if self._elements:
                self.num_combo.addItems(self._elements)
                self.den_combo.addItems(self._elements)
                nc = self._cfg.get('numerator_element', '')
                dc = self._cfg.get('denominator_element', '')
                if nc in self._elements:
                    self.num_combo.setCurrentText(nc)
                if dc in self._elements:
                    self.den_combo.setCurrentText(dc)
                elif len(self._elements) > 1:
                    self.den_combo.setCurrentIndex(1)
            f1.addRow("Numerator:", self.num_combo)
            f1.addRow("Denominator:", self.den_combo)
            lay.addWidget(g1)

        if self._scope in ('all', 'format'):
            g1f = QGroupBox("Label Display")
            f1f = QFormLayout(g1f)
            self.label_mode = QComboBox()
            self.label_mode.addItems(LABEL_MODES)
            self.label_mode.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
            f1f.addRow("Isotope Label:", self.label_mode)
            lay.addWidget(g1f)

            self._font_group = FontSettingsGroup(self._cfg)
            lay.addWidget(self._font_group.build())

        if self._scope in ('all', 'quantities'):
            g2 = QGroupBox("Molar Data Type")
            f2 = QFormLayout(g2)
            self.dtype_combo = QComboBox(); self.dtype_combo.addItems(MOLAR_DATA_TYPES)
            self.dtype_combo.setCurrentText(self._cfg.get('data_type_display', MOLAR_DATA_TYPES[0]))
            f2.addRow("Type:", self.dtype_combo)
            lay.addWidget(g2)

        if self._scope in ('all', 'quantities'):
            g3 = QGroupBox("Ratio Calculation")
            f3 = QFormLayout(g3)
            note = QLabel("Zero/nonpositive/missing/invalid values are skipped by design.")
            note.setWordWrap(True)
            note.setStyleSheet("color:#6B7280; font-size:11px;")
            f3.addRow(note)
            self.outlier_cb = QCheckBox(); self.outlier_cb.setChecked(self._cfg.get('filter_outliers', True))
            f3.addRow("Filter Outliers:", self.outlier_cb)
            self.pct_spin = QDoubleSpinBox(); self.pct_spin.setRange(90.0, 99.9)
            self.pct_spin.setDecimals(1); self.pct_spin.setValue(self._cfg.get('outlier_percentile', 99.0))
            f3.addRow("Keep Below Percentile:", self.pct_spin)
            lay.addWidget(g3)

        if _is_multi(self._input_data) and self._scope in ('all', 'quantities'):
            gm = QGroupBox("Multiple Sample Display")
            fm = QFormLayout(gm)
            self.mode_combo = QComboBox()
            self.mode_combo.addItems(MR_DISPLAY_MODES)
            cur_mode = _normalize_mr_display_mode(
                self._cfg.get('display_mode', MR_DISPLAY_MODES[0]))
            if cur_mode not in MR_DISPLAY_MODES:
                cur_mode = MR_DISPLAY_MODES[0]
            self.mode_combo.setCurrentText(cur_mode)
            fm.addRow("Display Mode:", self.mode_combo)
            lay.addWidget(gm)

        g4 = QGroupBox("Plot Options")
        f4 = QFormLayout(g4)
        self.bins_spin = QSpinBox(); self.bins_spin.setRange(10, 200)
        self.bins_spin.setValue(self._cfg.get('bins', 50))
        if self._scope in ('all', 'quantities'):
            f4.addRow("Bins:", self.bins_spin)
        self.y_unit_combo = QComboBox()
        self.y_unit_combo.addItem("Particle", "count")
        self.y_unit_combo.addItem("Particle per mL", "per_ml")
        _cur_u = self._cfg.get('y_axis_unit', 'count')
        self.y_unit_combo.setCurrentIndex(1 if _cur_u == 'per_ml' else 0)
        if self._scope in ('all', 'quantities'):
            if not conc_meta_available(self._input_data):
                _i = self.y_unit_combo.findData('per_ml')
                _it = self.y_unit_combo.model().item(_i)
                if _it is not None:
                    _it.setEnabled(False)
                if _cur_u == 'per_ml':
                    self.y_unit_combo.setCurrentIndex(0)
            f4.addRow("Y Axis:", self.y_unit_combo)
        self.alpha_spin = QDoubleSpinBox(); self.alpha_spin.setRange(0.1, 1.0)
        self.alpha_spin.setDecimals(1); self.alpha_spin.setValue(self._cfg.get('alpha', 0.7))
        if self._scope in ('all', 'format'):
            f4.addRow("Transparency:", self.alpha_spin)
        self.borders_cb = QCheckBox(); self.borders_cb.setChecked(self._cfg.get('bin_borders', True))
        if self._scope in ('all', 'format'):
            f4.addRow("Bin Borders:", self.borders_cb)
        self.curve_cb = QCheckBox(); self.curve_cb.setChecked(self._cfg.get('show_curve', True))
        self.stats_cb = QCheckBox(); self.stats_cb.setChecked(self._cfg.get('show_stats', True))
        self.box_cb = QCheckBox(); self.box_cb.setChecked(self._cfg.get('show_box', True))
        if self._scope in ('all', 'quantities'):
            # Quantity scope owns data-view toggles that are consumed by draw paths.
            f4.addRow("Density Curve:", self.curve_cb)
            f4.addRow("Statistics Box:", self.stats_cb)
        if self._scope in ('all', 'format'):
            # Format scope owns visual frame presentation controls.
            f4.addRow("Figure Box (frame):", self.box_cb)
        self.lx_cb = QCheckBox(); self.lx_cb.setChecked(self._cfg.get('log_x', True))
        self.ly_cb = QCheckBox(); self.ly_cb.setChecked(self._cfg.get('log_y', False))
        if self._scope in ('all', 'quantities'):
            f4.addRow("Log X:", self.lx_cb)
            f4.addRow("Log Y:", self.ly_cb)
        if f4.rowCount() > 0:
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
        if self._scope in ('all', 'quantities'):
            lay.addWidget(g5)

        gs = QGroupBox("Statistical Overlays  (applied to all subplots)")
        fs = QFormLayout(gs)

        def _normalize_overlay_color(color_value, fallback):
            """Return a valid overlay color string or the supplied fallback.

            Args:
                color_value (Any): Config value intended to represent a color.
                fallback (str): Safe default color for this overlay row.

            Returns:
                str: Valid hex/color string for the overlay preview and config.
            """
            if isinstance(color_value, str) and QColor(color_value).isValid():
                return color_value
            return fallback

        def _line_row(color_key, style_key, width_key, defaults):
            """Build one statistical-overlay row with isolated color/style/width state.

            Returns:
                tuple: Row layout, mutable color holder, style combo, and width
                spinbox for the overlay.
            """
            row = QHBoxLayout()
            color_holder = [_normalize_overlay_color(
                self._cfg.get(color_key, defaults[0]), defaults[0])]
            btn = QPushButton(); btn.setFixedSize(26, 22)
            btn.setStyleSheet(f"background:{color_holder[0]};")
            def _pick(*_args, holder=color_holder, button=btn):
                """Pick one overlay color without letting button state replace it."""
                picked = pick_color_hex(holder[0], owner=self,
                                        title="Overlay Color")
                if picked:
                    holder[0] = picked
                    button.setStyleSheet(f"background:{holder[0]};")
            btn.clicked.connect(_pick)
            sc = QComboBox(); sc.addItems(['solid', 'dash', 'dot'])
            sc.setCurrentText(self._cfg.get(style_key, defaults[1]))
            sc.setFixedWidth(64)
            ws = QSpinBox(); ws.setRange(1, 5)
            ws.setValue(self._cfg.get(width_key, defaults[2]))
            ws.setFixedWidth(68)
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
        if self._scope in ('all', 'format'):
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
        if self._scope in ('all', 'format'):
            lay.addWidget(gr)

        if _is_multi(self._input_data):
            names = self._input_data.get('sample_names', [])
            if names:
                if self._scope in ('all', 'format'):
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

                if self._scope in ('all', 'quantities'):
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

        _btn_row = QHBoxLayout()
        _btn_row.addStretch()
        _apply_btn = QPushButton("Apply")
        _done_btn = QPushButton("Done")
        _cancel_btn = QPushButton("Cancel")
        _apply_btn.clicked.connect(lambda: self.preview_requested.emit(self.collect()))
        _done_btn.clicked.connect(self.accept)
        _cancel_btn.clicked.connect(self.reject)
        _btn_row.addWidget(_apply_btn)
        _btn_row.addWidget(_done_btn)
        _btn_row.addWidget(_cancel_btn)
        root.addLayout(_btn_row)

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
        """Collect config updates using strict scope-aware key groups.

        Preserved behavior:
            ``scope='quantities'`` only reads scientific/quantity controls and
            never touches visual/quick-toggle widgets (e.g. median/mean/mode
            line checkboxes), preventing deleted-Qt-object access in quantity
            workflows. ``scope='format'`` collects presentation-only settings.
            ``scope='all'`` remains supported for compatibility.
        """
        d = {}
        in_quantities = self._scope in ('all', 'quantities')
        in_format = self._scope in ('all', 'format')

        if in_quantities:
            if self.num_combo is not None:
                d['numerator_element'] = self.num_combo.currentText()
                d['denominator_element'] = self.den_combo.currentText()
            if self.dtype_combo is not None:
                d['data_type_display'] = self.dtype_combo.currentText()
            if self.outlier_cb is not None:
                d['filter_outliers'] = self.outlier_cb.isChecked()
                d['outlier_percentile'] = self.pct_spin.value()
            if self.bins_spin is not None:
                d['bins'] = self.bins_spin.value()
            if getattr(self, 'y_unit_combo', None) is not None:
                d['y_axis_unit'] = self.y_unit_combo.currentData()
            if self.curve_cb is not None:
                d['show_curve'] = self.curve_cb.isChecked()
                d['show_stats'] = self.stats_cb.isChecked()
            if self.lx_cb is not None:
                d['log_x'] = self.lx_cb.isChecked()
                d['log_y'] = self.ly_cb.isChecked()
            if self.x_min is not None:
                d['x_min'] = self.x_min.value()
                d['x_max'] = self.x_max.value()
                d['auto_x'] = self.auto_x.isChecked()
                d['y_min'] = self.y_min.value()
                d['y_max'] = self.y_max.value()
                d['auto_y'] = self.auto_y.isChecked()
            if self.mode_combo is not None:
                d['display_mode'] = _normalize_mr_display_mode(
                    self.mode_combo.currentText())
            if self._order_list is not None:
                d['sample_order'] = [
                    self._order_list.item(i).text()
                    for i in range(self._order_list.count())]

        if in_format:
            if self.label_mode is not None:
                d['label_mode'] = self.label_mode.currentText()
            if self.alpha_spin is not None:
                d['alpha'] = self.alpha_spin.value()
            if self.borders_cb is not None:
                d['bin_borders'] = self.borders_cb.isChecked()
            if self.box_cb is not None:
                d['show_box'] = self.box_cb.isChecked()
            if self.median_line_cb is not None:
                d['show_median_line'] = self.median_line_cb.isChecked()
                d['median_line_color'] = self._med_color[0]
                d['median_line_style'] = self._med_style.currentText()
                d['median_line_width'] = self._med_width.value()
                d['show_mean_line'] = self.mean_line_cb.isChecked()
                d['mean_line_color'] = self._mean_color[0]
                d['mean_line_style'] = self._mean_style.currentText()
                d['mean_line_width'] = self._mean_width.value()
                d['show_mode_marker'] = self.mode_marker_cb.isChecked()
                d['mode_line_color'] = self._mode_color[0]
                d['mode_line_style'] = self._mode_style.currentText()
                d['mode_line_width'] = self._mode_width.value()
                d['shade_type'] = self.shade_combo.currentText()
                d['shade_color'] = self._shade_color
                d['shade_alpha'] = self.shade_alpha_spin.value()
                d['show_ref_line'] = self.ref_line_cb.isChecked()
                d['ref_line_value'] = self.ref_val_spin.value()
                d['ref_line_label'] = self.ref_label_edit.text().strip()
                d['ref_line_color'] = self._ref_color[0]
                d['ref_line_style'] = self._ref_style.currentText()
                d['ref_line_width'] = self._ref_width.value()
            if self._sample_edits is not None:
                d['sample_name_mappings'] = {
                    k: v.text() for k, v in self._sample_edits.items()}
            if self._font_group is not None:
                d.update(self._font_group.collect())
        return d


# ── Drawing helpers (PyQtGraph) ────────────────────────────────────────

def _draw_histogram_bars(plot_item, ratios, cfg, color, y_scale=1.0):
    """Draw histogram bars for ratio values.
    Args:
        plot_item (Any): The plot item.
        ratios (Any): The ratios.
        cfg (Any): The cfg.
        color (Any): Colour value.
        y_scale (float): Multiplier converting bin counts to particles per mL.
    """
    bins = cfg.get('bins', 50)
    log_x = cfg.get('log_x', True)
    log_y = cfg.get('log_y', False)

    pr = np.log10(ratios) if log_x else ratios.copy()
    y, edges = np.histogram(pr, bins=bins)
    y = y.astype(float) * y_scale
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
        _itk_log.exception("Handled exception in _add_density_curve")
        _itk_log.error(f"Density curve error: {e}")


def _apply_box(plot_item, cfg):
    """Show or hide the figure frame (top + right axes = closed box).

    The frame state is forced on every redraw so toggling ``show_box`` is
    responsive in single and multi-sample views.
    """
    show = bool(cfg.get('show_box', True))
    plot_item.showAxis('top', show)
    plot_item.showAxis('right', show)
    if show:
        plot_item.getAxis('top').setStyle(showValues=False)
        plot_item.getAxis('right').setStyle(showValues=False)
    else:
        # Ensure hidden-frame state is explicit after any prior enabled state.
        plot_item.getAxis('top').setStyle(showValues=False)
        plot_item.getAxis('right').setStyle(showValues=False)


_QT_LINE = {
    'solid': pg.QtCore.Qt.SolidLine,
    'dash':  pg.QtCore.Qt.DashLine,
    'dot':   pg.QtCore.Qt.DotLine,
}


def _add_ref_line(plot_item, cfg):
    """Draw a customisable reference vertical line (e.g. ratio = 1)."""
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
    num = format_element_label(cfg.get('numerator_element') or 'X', lm, Renderer.HTML)
    den = format_element_label(cfg.get('denominator_element') or 'Y', lm, Renderer.HTML)
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
            _itk_log.exception("Handled exception in _add_stat_lines")
            _itk_log.error(f"[mode marker] {e}")


def _add_shaded_region(plot_item, values, cfg):
    """Draw a statistical shaded band — applied to every subplot.

    ``values`` must already be in plot-space (log10 if log_x is True).
    """
    shade_type = cfg.get('shade_type', 'None')
    if shade_type == 'None' or len(values) < 3:
        return

    log_x = cfg.get('log_x', True)
    color = cfg.get('shade_color', '#534AB7')
    alpha = int(cfg.get('shade_alpha', 0.18) * 255)
    real_vals = 10**values if log_x else values

    def _to_plot(v):
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
    """Add statistics text box."""
    lm = cfg.get('label_mode', 'Symbol')
    num = format_element_label(cfg.get('numerator_element', '?'), lm, Renderer.HTML)
    den = format_element_label(cfg.get('denominator_element', '?'), lm, Renderer.HTML)
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
        _itk_log.exception("Handled exception in _add_stats_text")
    plot_item.addItem(ti)
    try:
        vr = plot_item.getViewBox().state['viewRange']
        ti.setPos(vr[0][0] + 0.02*(vr[0][1]-vr[0][0]),
                  vr[1][0] + 0.98*(vr[1][1]-vr[1][0]))
    except Exception:
        _itk_log.exception("Handled exception in _add_stats_text")
        ti.setPos(0.02, 0.98)


def _draw_ratio_plot(plot_item, ratios, cfg, color, y_scale=1.0):
    """Draw a complete ratio histogram with overlays (applied to every subplot).
    Args:
        plot_item (Any): The plot item.
        ratios (Any): The ratios.
        cfg (Any): The cfg.
        color (Any): Colour value.
        y_scale (float): Multiplier converting bin counts to particles per mL.
    """
    if ratios is None or len(ratios) == 0:
        return
    pr, edges, _ = _draw_histogram_bars(plot_item, ratios, cfg, color, y_scale)

    if cfg.get('show_curve', True) and len(ratios) > 5:
        _add_density_curve(plot_item, pr, cfg, edges, len(ratios) * y_scale)

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
        """Build plot area and standardized four-button action row.

        Preserved behavior:
            Annotation shelf/counter/hint UI is intentionally removed from
            Molar Ratio so the dialog follows the same results-plot workflow
            as other homogenized views.
        """
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

        self._plot_container = QWidget()
        self._plot_container_layout = QVBoxLayout(self._plot_container)
        self._plot_container_layout.setContentsMargins(0, 0, 0, 0)
        self._plot_container_layout.setSpacing(0)

        self.pw = EnhancedGraphicsLayoutWidget()
        self.pw.setBackground('w')
        self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pw.customContextMenuRequested.connect(self._ctx_menu)
        self._plot_container_layout.addWidget(self.pw)

        lay.addWidget(self._plot_container, stretch=1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        btn_fmt = QPushButton("Plot format settings")
        btn_fmt.clicked.connect(self._open_plot_format_settings)
        btn_qty = QPushButton("Configure plot quantities")
        btn_qty.clicked.connect(self._open_configure_plot_quantities)
        btn_reset = QPushButton("Reset layout")
        btn_reset.clicked.connect(self._reset_layout)
        btn_export = QPushButton("Export figure")
        btn_export.clicked.connect(self._export_figure)
        actions.addWidget(btn_fmt)
        actions.addWidget(btn_qty)
        actions.addWidget(btn_reset)
        actions.addWidget(btn_export)
        lay.addLayout(actions)

        
    def _ctx_menu(self, pos):
        """Show the minimal Molar Ratio right-click menu.

        Preserved behavior:
            Right-click contains only lightweight visual quick toggles and
            isotope-label display mode. Quantity/edit/export actions are
            intentionally routed through bottom buttons.
        """
        cfg = self.node.config
        multi = _is_multi(self.node.input_data)
        mode = _normalize_mr_display_mode(
            cfg.get('display_mode', MR_DISPLAY_MODES[0])) if multi else None
        stats_available = not (
            multi and mode != 'Individual Subplots'
        )
        menu = QMenu(self)

        tm = menu.addMenu("Quick Toggles")
        for key, label in [
            ('show_curve',  'Density Curve'),
            ('show_box',    'Figure Box (frame)'),
            ('show_ref_line',    'Reference Line'),
            ('show_median_line', 'Median Line'),
            ('show_mean_line',   'Mean Line'),
            ('show_mode_marker', 'Mode Marker'),
        ]:
            a = tm.addAction(label)
            a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        if stats_available:
            stats_act = tm.addAction('Statistics Box')
            stats_act.setCheckable(True)
            stats_act.setChecked(cfg.get('show_stats', False))
            stats_act.triggered.connect(lambda _, k='show_stats': self._toggle(k))
        else:
            stats_act = tm.addAction('Statistics Box (unavailable in overlaid mode)')
            stats_act.setEnabled(False)
            hint = "Statistics are available in individual subplot mode."
            stats_act.setToolTip(hint)
            stats_act.setStatusTip(hint)

        lm = menu.addMenu("Isotope Label")
        for label_mode in LABEL_MODES:
            a = lm.addAction(label_mode)
            a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == label_mode)
            a.triggered.connect(lambda _, v=label_mode: self._set('label_mode', v))

        menu.exec(self.pw.mapToGlobal(pos))

    # ── Helpers ──────────────────────────

    def _current_ratios(self):
        """Return a 1-D numpy array of all current ratio values (pooled across
        samples if multi). Returns None if unavailable."""
        try:
            plot_data = self.node.extract_plot_data()
        except Exception:
            _itk_log.exception("Handled exception in _current_ratios")
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
        self.node.config[key] = not self.node.config.get(key, False)
        self._refresh()

    def _set(self, key, value):
        self.node.config[key] = value
        self._refresh()

    def _open_settings(self, scope='all', title_override=None):
        """Open scoped Molar Ratio settings and apply on accept."""
        elems = self.node.extract_available_elements()
        _snap = dict(self.node.config)
        dlg = MolarRatioSettingsDialog(
            self.node.config,
            self.node.input_data,
            elems,
            self,
            scope=scope,
        )
        if title_override:
            dlg.setWindowTitle(title_override)
        dlg.preview_requested.connect(lambda cfg: (self.node.config.update(cfg), self._refresh()))
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()
        else:
            self.node.config.clear()
            self.node.config.update(_snap)
            self._refresh()

    def _open_plot_format_settings(self):
        """Open visual format settings for Molar Ratio presentation."""
        self._open_settings(
            scope='format',
            title_override="Molar ratio plot format settings",
        )

    def _open_configure_plot_quantities(self):
        """Open scientific quantity settings for ratio selection and filters."""
        self._open_settings(
            scope='quantities',
            title_override="Molar ratio quantities configuration",
        )

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

    def _export_figure(self):
        """Export the full Molar Ratio figure using existing helper options."""
        download_pyqtgraph_figure(self.pw, self, "molar_ratio_plot.png")

    def _disable_native_pyqtgraph_context_menu(self):
        """Suppress native PyQtGraph menus only for this Molar Ratio dialog."""
        for item in self.pw.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    item.setMenuEnabled(False)
                except Exception:
                    _itk_log.exception("Handled exception in _disable_native_pyqtgraph_context_menu")
                try:
                    vb = item.getViewBox()
                    if vb is not None:
                        vb.setMenuEnabled(False)
                except Exception:
                    _itk_log.exception("Handled exception in _disable_native_pyqtgraph_context_menu")

    def _reset_layout(self):
        """Reset view ranges only, preserving all ratio scientific settings."""
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
        self._refresh()


    def _refresh(self):
        """Rebuild the ratio plot and show non-modal invalid-data explanations.

        Preserved behavior:
            Refresh always redraws from current node config and explicitly
            suppresses native PyQtGraph menus for the newly created plot items.
            Annotation shelf/attach behavior is intentionally removed.
        """
        try:
            self._plot_container_layout.removeWidget(self.pw)
            self.pw.deleteLater()
            self.pw = EnhancedGraphicsLayoutWidget()
            self.pw.setBackground('w')
            self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
            self.pw.customContextMenuRequested.connect(self._ctx_menu)
            self._plot_container_layout.addWidget(self.pw)

            cfg = self.node.config
            lm = cfg.get('label_mode', 'Symbol')
            num = format_element_label(cfg.get('numerator_element', ''), lm, Renderer.HTML)
            den = format_element_label(cfg.get('denominator_element', ''), lm, Renderer.HTML)
            self._ratio_lbl.setText(f"Ratio: {num} / {den}" if num and den else "Ratio: Select elements")

            plot_data = self.node.extract_plot_data()
            reason = getattr(self.node, '_last_extract_reason', None)

            is_empty = (plot_data is None or
                        (isinstance(plot_data, dict) and
                         all(v is None or (hasattr(v, '__len__') and len(v) == 0) for v in plot_data.values())) or
                        (hasattr(plot_data, '__len__') and len(plot_data) == 0))

            if is_empty:
                pi = self.pw.addPlot(axisItems={'left': HtmlAxisItem('left')})
                if reason == 'same_elements':
                    msg = "Choose different numerator and denominator elements."
                elif reason == 'no_valid_ratios':
                    msg = "No valid ratios after skipping zero or invalid values."
                else:
                    msg = "No molar ratio data available\nSelect two elements and connect data"
                t = pg.TextItem(msg,
                                anchor=(0.5, 0.5), color='gray')
                pi.addItem(t); t.setPos(0.5, 0.5)
                pi.hideAxis('left'); pi.hideAxis('bottom')
                self._stats.setText("")
                self._disable_native_pyqtgraph_context_menu()
                return

            multi = _is_multi(self.node.input_data)
            if multi:
                mode = _normalize_mr_display_mode(
                    cfg.get('display_mode', MR_DISPLAY_MODES[0]))
                cfg['display_mode'] = mode
                if mode == 'Individual Subplots':
                    self._draw_subplots(plot_data, cfg)
                else:
                    pi = self.pw.addPlot(axisItems={'left': HtmlAxisItem('left')})
                    self._draw_overlaid(pi, plot_data, cfg)
                    apply_font_to_pyqtgraph(pi, cfg)
            else:
                pi = self.pw.addPlot(axisItems={'left': HtmlAxisItem('left')})
                self._draw_single(pi, plot_data, cfg)
                apply_font_to_pyqtgraph(pi, cfg)

            # Enforce figure-frame visibility across every subplot regardless
            # of draw branch or panel data availability.
            for item in self.pw.scene().items():
                if isinstance(item, pg.PlotItem):
                    _apply_box(item, cfg)

            self._update_stats(plot_data, multi)
            self._disable_native_pyqtgraph_context_menu()
        except Exception as e:
            _itk_log.exception("Handled exception in _refresh")
            _itk_log.error(f"Error updating molar ratio: {e}")
            import traceback; traceback.print_exc()

    def _draw_single(self, pi, ratios, cfg):
        """Draw single-sample ratio histogram and apply explicit axis log states."""
        sc = cfg.get('sample_colors', {})
        color = sc.get('single_sample', '#663399')
        per_ml = per_ml_active(cfg, self.node.input_data)
        sn = single_sample_name(self.node.input_data)
        y_scale = per_ml_factor(self.node.input_data, sn) if per_ml else 1.0
        _draw_ratio_plot(pi, ratios, cfg, color, y_scale)
        xl, yl = _xy_labels(cfg)
        set_axis_labels(pi, xl, yl, cfg)
        
        pi.getAxis('bottom').setLogMode(bool(cfg.get('log_x', True)))
        pi.getAxis('left').setLogMode(bool(cfg.get('log_y', False)))
        if per_ml and not cfg.get('log_y', False):
            apply_sci_y_axis(pi, cfg)
        if cfg.get('show_stats', True):
            pr = np.log10(ratios) if cfg.get('log_x', True) else ratios.copy()
            _add_stats_text(pi, pr, cfg)

    def _draw_overlaid(self, pi, plot_data, cfg):
        """Draw multi-sample overlaid ratios in one panel with explicit log states."""
        sc = cfg.get('sample_colors', {})
        legend_items = []
        all_pr = []
        per_ml = per_ml_active(cfg, self.node.input_data)
        for i, (sn, ratios) in enumerate(plot_data.items()):
            if ratios is not None and len(ratios) > 0:
                c = sc.get(sn, DEFAULT_SAMPLE_COLORS[i % len(DEFAULT_SAMPLE_COLORS)])
                y_scale = per_ml_factor(self.node.input_data, sn) if per_ml else 1.0
                pr, edges, y = _draw_histogram_bars(pi, ratios, cfg, c, y_scale)
                legend_items.append((sn, c))
                if cfg.get('show_curve', True) and len(ratios) > 5:
                    _add_density_curve(pi, pr, cfg, edges, len(ratios) * y_scale)
                all_pr.append(pr)
        if all_pr:
            pooled = np.concatenate(all_pr)
            _add_shaded_region(pi, pooled, cfg)
            _add_stat_lines(pi, pooled, cfg)
        _add_ref_line(pi, cfg)
        xl, yl = _xy_labels(cfg)
        set_axis_labels(pi, xl, yl, cfg)
        pi.getAxis('bottom').setLogMode(bool(cfg.get('log_x', True)))
        pi.getAxis('left').setLogMode(bool(cfg.get('log_y', False)))
        if per_ml and not cfg.get('log_y', False):
            apply_sci_y_axis(pi, cfg)
        _apply_box(pi, cfg)
        if legend_items:
            legend = pi.addLegend()
            for sn, c in legend_items:
                dn = get_display_name(sn, cfg)
                item = pg.PlotDataItem(pen=pg.mkPen(c, width=4))
                legend.addItem(item, dn)

    def _draw_subplots(self, plot_data, cfg):
        """Draw one subplot per sample and apply explicit log + stats behavior."""
        names = list(plot_data.keys())
        cols = min(3, len(names))
        rows = math.ceil(len(names) / cols)
        sc = cfg.get('sample_colors', {})
        per_ml = per_ml_active(cfg, self.node.input_data)
        for i, sn in enumerate(names):
            r, c = divmod(i, cols)
            pi = self.pw.addPlot(row=r, col=c,
                                 axisItems={'left': HtmlAxisItem('left')})
            ratios = plot_data[sn]
            if ratios is not None and len(ratios) > 0:
                color = sc.get(sn, DEFAULT_SAMPLE_COLORS[i % len(DEFAULT_SAMPLE_COLORS)])
                y_scale = per_ml_factor(self.node.input_data, sn) if per_ml else 1.0
                _draw_ratio_plot(pi, ratios, cfg, color, y_scale)
                pi.setTitle(get_display_name(sn, cfg))
                xl, yl = _xy_labels(cfg)
                set_axis_labels(pi, xl, yl, cfg)
                
                pi.getAxis('bottom').setLogMode(bool(cfg.get('log_x', True)))
                pi.getAxis('left').setLogMode(bool(cfg.get('log_y', False)))
                if per_ml and not cfg.get('log_y', False):
                    apply_sci_y_axis(pi, cfg)
                if cfg.get('show_stats', True):
                    pr = np.log10(ratios) if cfg.get('log_x', True) else ratios.copy()
                    _add_stats_text(pi, pr, cfg)
            apply_font_to_pyqtgraph(pi, cfg)

    def _draw_side_by_side(self, plot_data, cfg):
        """Draw side-by-side sample subplots with explicit log + stats behavior."""
        names = list(plot_data.keys())
        sc = cfg.get('sample_colors', {})
        per_ml = per_ml_active(cfg, self.node.input_data)
        for i, sn in enumerate(names):
            pi = self.pw.addPlot(row=0, col=i,
                                 axisItems={'left': HtmlAxisItem('left')})
            ratios = plot_data[sn]
            if ratios is not None and len(ratios) > 0:
                color = sc.get(sn, DEFAULT_SAMPLE_COLORS[i % len(DEFAULT_SAMPLE_COLORS)])
                y_scale = per_ml_factor(self.node.input_data, sn) if per_ml else 1.0
                _draw_ratio_plot(pi, ratios, cfg, color, y_scale)
                pi.setTitle(get_display_name(sn, cfg))
                xl, yl = _xy_labels(cfg)
                set_axis_labels(pi, xl, yl if i == 0 else "", cfg)
                
                pi.getAxis('bottom').setLogMode(bool(cfg.get('log_x', True)))
                pi.getAxis('left').setLogMode(bool(cfg.get('log_y', False)))
                if per_ml and not cfg.get('log_y', False):
                    apply_sci_y_axis(pi, cfg)
                if cfg.get('show_stats', True):
                    pr = np.log10(ratios) if cfg.get('log_x', True) else ratios.copy()
                    _add_stats_text(pi, pr, cfg)
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
        self._last_extract_reason = None

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
        """Compute ratio arrays for current numerator/denominator/data-type config.

        Preserved behavior:
            Old configs may still carry obsolete zero-handling keys; they are
            ignored. Ratio extraction now uses one fixed scientific behavior:
            skip zero/nonpositive/missing/NaN/non-finite components.
        """
        self._last_extract_reason = None
        if not self.input_data:
            self._last_extract_reason = 'no_input'
            return None
        num = self.config.get('numerator_element', '')
        den = self.config.get('denominator_element', '')
        if not num or not den or num == den:
            self._last_extract_reason = 'same_elements' if num == den else 'missing_elements'
            return None
        dk = MOLAR_DATA_KEY_MAP.get(self.config.get('data_type_display', MOLAR_DATA_TYPES[0]), 'element_moles_fmol')
        itype = self.input_data.get('type')
        if itype == 'sample_data':
            return self._extract_single(dk, num, den)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(dk, num, den)
        return None

    def _compute_ratios(self, particles, dk, num, den):
        """Compute positive finite ratios with fixed skip-invalid behavior.

        Preserved behavior:
            Legacy ``zero_handling`` / ``min_threshold`` config keys are
            ignored for backward compatibility. This method now always skips
            particles where numerator or denominator is missing, non-finite,
            or nonpositive.
        """
        # Obsolete zero-handling config keys are intentionally ignored.
        # Fixed behavior: skip zero/nonpositive/missing/invalid components.
        ratios = []
        for p in particles:
            pd = p.get(dk, {})
            nv = pd.get(num)
            dv = pd.get(den)
            if nv is None or dv is None:
                continue
            if not np.isfinite(nv) or not np.isfinite(dv):
                continue
            if nv <= 0 or dv <= 0:
                continue
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
        ratios = self._compute_ratios(particles, dk, num, den)
        if ratios is None or len(ratios) == 0:
            self._last_extract_reason = 'no_valid_ratios'
            return None
        return ratios

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
        if not result:
            self._last_extract_reason = 'no_valid_ratios'
        return result if result else None
