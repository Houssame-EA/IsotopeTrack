from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QPushButton,
    QLineEdit, QFrame, QScrollArea, QWidget, QMenu, QWidgetAction,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QColorDialog, QListWidget,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QAction, QCursor
import pyqtgraph as pg
import numpy as np
import math

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS, DATA_TYPE_OPTIONS, DATA_KEY_MAPPING,
    get_font_config, make_qfont, apply_font_to_pyqtgraph, set_axis_labels,
    FontSettingsGroup, build_axis_labels,
    apply_saturation_filter, apply_zero_filter, apply_log_transform,
    evaluate_equation, evaluate_equation_array, build_element_matrix,
    compute_correlation_matrix, find_top_correlations,
    create_single_color_scatter, create_color_mapped_scatter,
    add_trend_line, add_correlation_text, CustomColorBar,
    get_sample_color, get_display_name,
    download_pyqtgraph_figure,
    SHADE_TYPES, _QT_LINE, apply_outlier_filter, _apply_box,
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


class CorrelationSettingsDialog(QDialog):
    """Full settings dialog opened from the right-click → Configure… action."""

    def __init__(self, config: dict, available_elements: list,
                 is_multi: bool, sample_names: list, parent=None):
        """
        Args:
            config (dict): Configuration dictionary.
            available_elements (list): The available elements.
            is_multi (bool): The is multi.
            sample_names (list): The sample names.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("Correlation Plot Settings")
        self.setMinimumWidth(460)
        self._config = dict(config)
        self._elements = available_elements
        self._is_multi = is_multi
        self._sample_names = sample_names
        self._build_ui()

    # ── UI construction ──────────────────────

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

        if self._is_multi:
            g = QGroupBox("Multiple Sample Display")
            fl = QFormLayout(g)
            self.display_mode = QComboBox()
            self.display_mode.addItems([
                'Overlaid (Different Colors)', 'Side by Side Subplots',
                'Individual Subplots', 'Combined with Legend'
            ])
            self.display_mode.setCurrentText(self._config.get('display_mode', 'Overlaid (Different Colors)'))
            fl.addRow("Display Mode:", self.display_mode)
            layout.addWidget(g)

        g = QGroupBox("Analysis Mode")
        vl = QVBoxLayout(g)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(['Simple Element Correlation', 'Custom Mathematical Expressions'])
        self.mode_combo.setCurrentText(self._config.get('mode', 'Simple Element Correlation'))
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        vl.addWidget(self.mode_combo)
        layout.addWidget(g)

        self.simple_group = QGroupBox("Element Selection")
        fl = QFormLayout(self.simple_group)
        self.x_elem = QComboBox(); self.x_elem.addItems(self._elements)
        self.x_elem.setCurrentText(self._config.get('x_element', self._elements[0] if self._elements else ''))
        fl.addRow("X-axis:", self.x_elem)
        self.y_elem = QComboBox(); self.y_elem.addItems(self._elements)
        y_def = self._config.get('y_element', self._elements[1] if len(self._elements) > 1 else '')
        if y_def in self._elements:
            self.y_elem.setCurrentText(y_def)
        fl.addRow("Y-axis:", self.y_elem)
        self.color_elem = QComboBox(); self.color_elem.addItems(["None"] + self._elements)
        self.color_elem.setCurrentText(self._config.get('color_element', 'None'))
        fl.addRow("Color by:", self.color_elem)
        layout.addWidget(self.simple_group)

        self.custom_group = QGroupBox("Custom Equations")
        cl = QFormLayout(self.custom_group)

        eq_hint = QLabel(
            "Write equations using element names as variables.\n"
            "Operators: + - * /   Parentheses allowed.\n"
            "Examples:   Fe/Ti     Ca + Mg     (Fe+Al)/Si\n"
            "Axis label is set from the equation text automatically.")
        eq_hint.setWordWrap(True)
        eq_hint.setStyleSheet(
            "color:#1D4ED8; font-size:10px; padding:5px 6px;"
            "background:#DBEAFE; border-radius:4px;")
        cl.addRow(eq_hint)

        self.x_eq = QLineEdit(self._config.get('x_equation', ''))
        self.x_eq.setPlaceholderText("e.g. Fe/Ti")
        self.x_eq.setToolTip(
            "Element names as variables. Examples:\n"
            "  Fe/Ti    Ca + Mg    (Fe+Al)/Si\n"
            "The X-axis label is auto-set from this text.")
        self.x_eq.textChanged.connect(self._on_eq_changed)
        cl.addRow("X equation:", self.x_eq)

        self.x_lbl = QLineEdit(self._config.get('x_label', 'X-axis'))
        self.x_lbl.setPlaceholderText("Auto-filled from equation")
        cl.addRow("X label:", self.x_lbl)

        self.y_eq = QLineEdit(self._config.get('y_equation', ''))
        self.y_eq.setPlaceholderText("e.g. Ca + Mg")
        self.y_eq.setToolTip(
            "Element names as variables. Examples:\n"
            "  Ca+Mg    Pb/Al    (Ce+La)/Nd\n"
            "The Y-axis label is auto-set from this text.")
        self.y_eq.textChanged.connect(self._on_eq_changed)
        cl.addRow("Y equation:", self.y_eq)

        self.y_lbl = QLineEdit(self._config.get('y_label', 'Y-axis'))
        self.y_lbl.setPlaceholderText("Auto-filled from equation")
        cl.addRow("Y label:", self.y_lbl)

        if self._elements:
            info = QLabel(f"Available elements: {', '.join(self._elements)}")
            info.setWordWrap(True)
            info.setStyleSheet("color:#3B82F6; font-size:10px; padding:4px; "
                               "background:#DBEAFE; border-radius:4px;")
            cl.addRow(info)
        layout.addWidget(self.custom_group)

        g = QGroupBox("Data Type")
        vl = QVBoxLayout(g)
        self.data_type = QComboBox(); self.data_type.addItems(DATA_TYPE_OPTIONS)
        self.data_type.setCurrentText(self._config.get('data_type_display', 'Counts'))
        vl.addWidget(self.data_type)
        layout.addWidget(g)

        g = QGroupBox("Plot Options")
        fl = QFormLayout(g)
        self.filter_zeros = QCheckBox(); self.filter_zeros.setChecked(self._config.get('filter_zeros', True))
        fl.addRow("Filter zeros:", self.filter_zeros)
        self.filter_sat = QCheckBox(); self.filter_sat.setChecked(self._config.get('filter_saturated', True))
        fl.addRow("Filter saturated:", self.filter_sat)
        self.sat_thresh = QSpinBox(); self.sat_thresh.setRange(1, 1_000_000)
        self.sat_thresh.setValue(self._config.get('saturation_threshold', 10000))
        fl.addRow("Saturation threshold:", self.sat_thresh)
        self.filter_outliers_cb = QCheckBox()
        self.filter_outliers_cb.setChecked(self._config.get('filter_outliers', False))
        fl.addRow("Filter outliers:", self.filter_outliers_cb)
        self.outlier_pct = QDoubleSpinBox(); self.outlier_pct.setRange(90.0, 99.9)
        self.outlier_pct.setDecimals(1)
        self.outlier_pct.setValue(self._config.get('outlier_percentile', 99.0))
        fl.addRow("Keep below percentile:", self.outlier_pct)
        self.show_corr = QCheckBox(); self.show_corr.setChecked(self._config.get('show_correlation', True))
        fl.addRow("Show r:", self.show_corr)
        self.show_trend = QCheckBox(); self.show_trend.setChecked(self._config.get('show_trendline', True))
        fl.addRow("Trend line:", self.show_trend)
        self.show_box_cb = QCheckBox(); self.show_box_cb.setChecked(self._config.get('show_box', True))
        fl.addRow("Figure box (frame):", self.show_box_cb)
        self.log_x = QCheckBox(); self.log_x.setChecked(self._config.get('log_x', False))
        fl.addRow("Log X:", self.log_x)
        self.log_y = QCheckBox(); self.log_y.setChecked(self._config.get('log_y', False))
        fl.addRow("Log Y:", self.log_y)
        layout.addWidget(g)

        g = QGroupBox("SD Envelope (around trend line)")
        fl = QFormLayout(g)
        self.show_sd_band = QCheckBox()
        self.show_sd_band.setChecked(self._config.get('show_sd_band', False))
        fl.addRow("Show SD band:", self.show_sd_band)
        sd_row = QHBoxLayout()
        self._sd_color = self._config.get('sd_band_color', '#3B82F6')
        self._sd_color_btn = QPushButton(); self._sd_color_btn.setFixedSize(26, 22)
        self._sd_color_btn.setStyleSheet(f"background:{self._sd_color};")
        self._sd_color_btn.clicked.connect(self._pick_sd_color)
        self._sd_alpha = QDoubleSpinBox(); self._sd_alpha.setRange(0.01, 1.0)
        self._sd_alpha.setDecimals(2); self._sd_alpha.setValue(self._config.get('sd_band_alpha', 0.18))
        sd_row.addWidget(self._sd_color_btn); sd_row.addWidget(QLabel("alpha:"))
        sd_row.addWidget(self._sd_alpha); sd_row.addStretch()
        fl.addRow("Color / alpha:", sd_row)
        layout.addWidget(g)

        g = QGroupBox("Reference Diagonal Line")
        fl = QFormLayout(g)
        self.show_ref_cb = QCheckBox()
        self.show_ref_cb.setChecked(self._config.get('show_ref_line', False))
        fl.addRow("Show reference line:", self.show_ref_cb)
        self.ref_slope = QDoubleSpinBox(); self.ref_slope.setRange(-1e6, 1e6)
        self.ref_slope.setDecimals(4); self.ref_slope.setValue(self._config.get('ref_line_slope', 1.0))
        fl.addRow("Slope:", self.ref_slope)
        self.ref_intercept = QDoubleSpinBox(); self.ref_intercept.setRange(-1e9, 1e9)
        self.ref_intercept.setDecimals(4); self.ref_intercept.setValue(self._config.get('ref_line_intercept', 0.0))
        fl.addRow("Intercept:", self.ref_intercept)
        self.ref_label_edit = QLineEdit(self._config.get('ref_line_label', ''))
        self.ref_label_edit.setPlaceholderText("Auto  (e.g.  y = x)")
        fl.addRow("Label:", self.ref_label_edit)
        ref_style_row = QHBoxLayout()
        self._ref_color = self._config.get('ref_line_color', '#A32D2D')
        self._ref_color_btn = QPushButton(); self._ref_color_btn.setFixedSize(26, 22)
        self._ref_color_btn.setStyleSheet(f"background:{self._ref_color};")
        self._ref_color_btn.clicked.connect(self._pick_ref_color)
        self._ref_style = QComboBox(); self._ref_style.addItems(['solid', 'dash', 'dot'])
        self._ref_style.setCurrentText(self._config.get('ref_line_style', 'dash'))
        self._ref_style.setFixedWidth(70)
        self._ref_width = QSpinBox(); self._ref_width.setRange(1, 5)
        self._ref_width.setValue(self._config.get('ref_line_width', 2)); self._ref_width.setFixedWidth(44)
        ref_style_row.addWidget(self._ref_color_btn); ref_style_row.addWidget(self._ref_style)
        ref_style_row.addWidget(QLabel("w:")); ref_style_row.addWidget(self._ref_width)
        ref_style_row.addStretch()
        fl.addRow("Style:", ref_style_row)
        layout.addWidget(g)

        g = QGroupBox("Marker")
        fl = QFormLayout(g)
        self.m_size = QSpinBox(); self.m_size.setRange(1, 20)
        self.m_size.setValue(self._config.get('marker_size', 6))
        fl.addRow("Size:", self.m_size)
        self.m_alpha = QDoubleSpinBox(); self.m_alpha.setRange(0.1, 1.0)
        self.m_alpha.setSingleStep(0.1); self.m_alpha.setDecimals(1)
        self.m_alpha.setValue(self._config.get('marker_alpha', 0.7))
        fl.addRow("Alpha:", self.m_alpha)
        layout.addWidget(g)


        if self._is_multi:
            g = QGroupBox("Sample Names")
            sl = QVBoxLayout(g)
            self._sample_name_edits = {}
            nm = self._config.get('sample_name_mappings', {})
            for sn in self._sample_names:
                row = QHBoxLayout()
                row.addWidget(QLabel(sn[:20]))
                ne = QLineEdit(nm.get(sn, sn))
                ne.setFixedWidth(200)
                row.addWidget(ne)
                self._sample_name_edits[sn] = ne
                rst = QPushButton("\u21ba")
                rst.setFixedSize(22, 22)
                rst.clicked.connect(
                    lambda _, o=sn: self._sample_name_edits[o].setText(o))
                row.addWidget(rst)
                row.addStretch()
                w = QWidget(); w.setLayout(row)
                sl.addWidget(w)
            layout.addWidget(g)

            g2 = QGroupBox("Sample Display Order")
            v2 = QVBoxLayout(g2)
            hint = QLabel(
                "Drag or use \u2191\u2193 to reorder \u2014 useful for time series.")
            hint.setStyleSheet("color:#6B7280; font-size:10px;")
            hint.setWordWrap(True)
            v2.addWidget(hint)
            from PySide6.QtWidgets import QAbstractItemView as _AIV
            self._order_list = QListWidget()
            self._order_list.setMaximumHeight(130)
            self._order_list.setDragDropMode(_AIV.InternalMove)
            cur_order = self._config.get('sample_order', [])
            ordered = [s for s in cur_order if s in self._sample_names]
            ordered += [s for s in self._sample_names if s not in ordered]
            for s in ordered:
                self._order_list.addItem(s)
            v2.addWidget(self._order_list)
            btn_row = QHBoxLayout()
            up_btn = QPushButton("\u2191  Up"); up_btn.setFixedWidth(72)
            up_btn.clicked.connect(self._move_up)
            dn_btn = QPushButton("\u2193  Down"); dn_btn.setFixedWidth(72)
            dn_btn.clicked.connect(self._move_down)
            btn_row.addWidget(up_btn); btn_row.addWidget(dn_btn)
            btn_row.addStretch()
            v2.addLayout(btn_row)
            layout.addWidget(g2)

        g = QGroupBox("Axis Ranges")
        fl = QFormLayout(g)

        def _range_row(min_key, max_key, auto_key, min_def, max_def):
            """
            Args:
                min_key (Any): The min key.
                max_key (Any): The max key.
                auto_key (Any): The auto key.
                min_def (Any): The min def.
                max_def (Any): The max def.
            Returns:
                tuple: Result of the operation.
            """
            rw = QWidget(); rh = QHBoxLayout(rw); rh.setContentsMargins(0,0,0,0)
            auto_cb = QCheckBox("Auto"); auto_cb.setChecked(self._config.get(auto_key, True))
            mn = QDoubleSpinBox(); mn.setRange(-1e9, 1e9); mn.setDecimals(4)
            mn.setValue(self._config.get(min_key, min_def))
            mx = QDoubleSpinBox(); mx.setRange(-1e9, 1e9); mx.setDecimals(4)
            mx.setValue(self._config.get(max_key, max_def))
            mn.setEnabled(not auto_cb.isChecked())
            mx.setEnabled(not auto_cb.isChecked())
            auto_cb.stateChanged.connect(lambda s, a=mn, b=mx: (
                a.setEnabled(not auto_cb.isChecked()),
                b.setEnabled(not auto_cb.isChecked())))
            rh.addWidget(auto_cb); rh.addWidget(mn)
            rh.addWidget(QLabel("to")); rh.addWidget(mx)
            rh.addStretch()
            return rw, auto_cb, mn, mx

        xr, self._x_auto, self._x_min, self._x_max = _range_row(
            'x_min', 'x_max', 'auto_x', 0.0, 1000.0)
        fl.addRow("X Range:", xr)
        yr, self._y_auto, self._y_min, self._y_max = _range_row(
            'y_min', 'y_max', 'auto_y', 0.0, 1000.0)
        fl.addRow("Y Range:", yr)
        layout.addWidget(g)

        layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

        self._on_mode_changed()

    def _on_mode_changed(self):
        simple = self.mode_combo.currentText() == 'Simple Element Correlation'
        self.simple_group.setVisible(simple)
        self.custom_group.setVisible(not simple)

    def _on_eq_changed(self):
        """Auto-populate axis labels from equation text when label is blank or was auto."""
        x_eq = self.x_eq.text().strip()
        y_eq = self.y_eq.text().strip()
        if x_eq:
            self.x_lbl.setPlaceholderText(x_eq)
        if y_eq:
            self.y_lbl.setPlaceholderText(y_eq)

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

    def _pick_sd_color(self):
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor
        c = QColorDialog.getColor(QColor(self._sd_color), self)
        if c.isValid():
            self._sd_color = c.name()
            self._sd_color_btn.setStyleSheet(f"background:{self._sd_color};")

    def _pick_ref_color(self):
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor
        c = QColorDialog.getColor(QColor(self._ref_color), self)
        if c.isValid():
            self._ref_color = c.name()
            self._ref_color_btn.setStyleSheet(f"background:{self._ref_color};")

    def collect(self) -> dict:
        """Return the updated config dict.
        Returns:
            dict: Result of the operation.
        """
        cfg = dict(self._config)
        cfg['mode'] = self.mode_combo.currentText()
        cfg['x_element'] = self.x_elem.currentText()
        cfg['y_element'] = self.y_elem.currentText()
        cfg['color_element'] = self.color_elem.currentText()
        cfg['x_equation'] = self.x_eq.text()
        cfg['y_equation'] = self.y_eq.text()
        x_lbl = self.x_lbl.text().strip()
        y_lbl = self.y_lbl.text().strip()
        cfg['x_label'] = x_lbl or self.x_eq.text().strip() or 'X-axis'
        cfg['y_label'] = y_lbl or self.y_eq.text().strip() or 'Y-axis'
        cfg['auto_x'] = self._x_auto.isChecked()
        cfg['x_min'] = self._x_min.value()
        cfg['x_max'] = self._x_max.value()
        cfg['auto_y'] = self._y_auto.isChecked()
        cfg['y_min'] = self._y_min.value()
        cfg['y_max'] = self._y_max.value()
        cfg['data_type_display'] = self.data_type.currentText()
        cfg['filter_zeros'] = self.filter_zeros.isChecked()
        cfg['filter_saturated'] = self.filter_sat.isChecked()
        cfg['saturation_threshold'] = self.sat_thresh.value()
        cfg['filter_outliers'] = self.filter_outliers_cb.isChecked()
        cfg['outlier_percentile'] = self.outlier_pct.value()
        cfg['show_correlation'] = self.show_corr.isChecked()
        cfg['show_trendline'] = self.show_trend.isChecked()
        cfg['show_box'] = self.show_box_cb.isChecked()
        cfg['log_x'] = self.log_x.isChecked()
        cfg['log_y'] = self.log_y.isChecked()
        cfg['show_sd_band'] = self.show_sd_band.isChecked()
        cfg['sd_band_color'] = self._sd_color
        cfg['sd_band_alpha'] = self._sd_alpha.value()
        cfg['show_ref_line'] = self.show_ref_cb.isChecked()
        cfg['ref_line_slope'] = self.ref_slope.value()
        cfg['ref_line_intercept'] = self.ref_intercept.value()
        cfg['ref_line_label'] = self.ref_label_edit.text().strip()
        cfg['ref_line_color'] = self._ref_color
        cfg['ref_line_style'] = self._ref_style.currentText()
        cfg['ref_line_width'] = self._ref_width.value()
        cfg['marker_size'] = self.m_size.value()
        cfg['marker_alpha'] = self.m_alpha.value()

        if self._is_multi:
            cfg['display_mode'] = self.display_mode.currentText()
            if hasattr(self, '_sample_name_edits'):
                nm = {}
                for sn, ne in self._sample_name_edits.items():
                    if ne.text() != sn:
                        nm[sn] = ne.text()
                cfg['sample_name_mappings'] = nm
            if hasattr(self, '_order_list'):
                cfg['sample_order'] = [
                    self._order_list.item(i).text()
                    for i in range(self._order_list.count())]
        return cfg


class AutoCorrelationDialog(QDialog):
    """Table of top correlations — double-click to jump to that pair."""

    pair_selected = Signal(str, str)

    def __init__(self, top_pairs: list, parent=None):
        """
        Args:
            top_pairs (list): The top pairs.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("Automated Correlation Detection")
        self.setMinimumSize(520, 400)
        self._pairs = top_pairs
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        lbl = QLabel("Top element-pair correlations (by |r|). Double-click to plot.")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.table = QTableWidget(len(self._pairs), 4)
        self.table.setHorizontalHeaderLabels(["X Element", "Y Element", "r", "N points"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        for i, p in enumerate(self._pairs):
            self.table.setItem(i, 0, QTableWidgetItem(p['x']))
            self.table.setItem(i, 1, QTableWidgetItem(p['y']))
            ri = QTableWidgetItem(f"{p['r']:.4f}")
            ri.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 2, ri)
            ni = QTableWidgetItem(str(p['n']))
            ni.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 3, ni)

            abs_r = abs(p['r'])
            if abs_r > 0.7:
                color = QColor(209, 250, 229) if p['r'] > 0 else QColor(254, 226, 226)
            elif abs_r > 0.4:
                color = QColor(236, 253, 245) if p['r'] > 0 else QColor(254, 242, 242)
            else:
                color = QColor(255, 255, 255)
            for c in range(4):
                self.table.item(i, c).setBackground(color)

        self.table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

        btn = QDialogButtonBox(QDialogButtonBox.Close)
        btn.rejected.connect(self.reject)
        layout.addWidget(btn)

    def _on_double_click(self, index):
        """
        Args:
            index (Any): Row or item index.
        """
        row = index.row()
        if 0 <= row < len(self._pairs):
            p = self._pairs[row]
            self.pair_selected.emit(p['x'], p['y'])
            self.accept()


class CorrelationPlotDisplayDialog(QDialog):
    """
    Full-figure correlation dialog.

    Right-click anywhere on the plot to access:
    - Quick toggles (log axes, trend line, correlation coeff)
    - Data type switching
    - Auto-detect correlations
    - Full settings dialog
    - Download
    """

    def __init__(self, correlation_node, parent_window=None):
        """
        Args:
            correlation_node (Any): The correlation node.
            parent_window (Any): The parent window.
        """
        super().__init__(parent_window)
        self.node = correlation_node
        self.parent_window = parent_window
        self.setWindowTitle("Element Correlation Analysis")
        self.setMinimumSize(1000, 700)

        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        self.active_color_bars: list[CustomColorBar] = []
        self._setup_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    # ── helpers ─────────────────────────────

    def _is_multi(self) -> bool:
        """
        Returns:
            bool: Result of the operation.
        """
        return (self.node.input_data and
                self.node.input_data.get('type') == 'multiple_sample_data')

    def _sample_names(self) -> list:
        """
        Returns:
            list: Result of the operation.
        """
        if self._is_multi():
            return self.node.input_data.get('sample_names', [])
        return []

    def _available_elements(self) -> list:
        """
        Returns:
            list: Result of the operation.
        """
        try:
            pd = self.node.extract_plot_data()
            if pd:
                if self._is_multi():
                    elems = set()
                    for sd in pd.values():
                        if isinstance(sd, dict) and 'element_data' in sd:
                            elems.update(sd['element_data'].columns)
                    return sorted(elems)
                elif 'element_data' in pd:
                    return list(pd['element_data'].columns)
        except Exception:
            pass
        sel = (self.node.input_data or {}).get('selected_isotopes', [])
        return [iso['label'] for iso in sel]

    # ── UI ──────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.node.config.setdefault('annotations', [])

        self.ann_mgr = AnnotationManager(self.node.config, parent=self)

        self._plot_container = QWidget()
        self._plot_container_layout = QVBoxLayout(self._plot_container)
        self._plot_container_layout.setContentsMargins(0, 0, 0, 0)
        self._plot_container_layout.setSpacing(0)

        self.plot_widget = EnhancedGraphicsLayoutWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.plot_widget.customContextMenuRequested.connect(self._show_context_menu)
        self._plot_container_layout.addWidget(self.plot_widget)

        self._primary_plot_item = None

        self.ann_inspector = FloatingInspector(self.ann_mgr, parent=self._plot_container)
        self.ann_inspector.set_plot_accessor(
            lambda: (self.plot_widget, self._primary_plot_item))

        layout.addWidget(self._plot_container, stretch=1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(6, 0, 6, 0)

        self._hint_lbl = QLabel("Right-click the plot to add annotations")
        self._hint_lbl.setStyleSheet(
            "color: #999; font-size: 11px; font-style: italic;")
        bottom.addWidget(self._hint_lbl)
        bottom.addStretch(1)

        self.ann_shelf = AnnotationShelfButton(self.ann_mgr)
        bottom.addWidget(self.ann_shelf)

        layout.addLayout(bottom)

        self.ann_mgr.sig_annotations_changed.connect(self._refresh_hint)
        self._refresh_hint()

        install_annotation_shortcuts(self, self.ann_mgr)

    def _refresh_hint(self):
        self._hint_lbl.setVisible(len(self.node.config.get('annotations', [])) == 0)

    # ── Context menu ────────────────────────

    def _show_context_menu(self, pos):
        """
        Args:
            pos (Any): Position point.
        """
        cfg = self.node.config
        menu = QMenu(self)

        tm = menu.addMenu("Quick Toggles")
        for key, label, default in [
            ('log_x',           'Log X-axis',         False),
            ('log_y',           'Log Y-axis',         False),
            ('show_trendline',  'Trend Line',         True),
            ('show_correlation','Correlation r',      True),
            ('show_sd_band',    'SD Envelope',        False),
            ('show_ref_line',   'Reference Line',     False),
            ('filter_zeros',    'Filter Zeros',       True),
            ('filter_outliers', 'Filter Outliers',    False),
            ('filter_saturated','Filter Saturated',   True),
            ('show_box',        'Figure Box (frame)', True),
        ]:
            a = tm.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, default))
            a.triggered.connect(lambda checked, k=key: self._toggle(k, checked))

        dt_menu = menu.addMenu("Data Type")
        current_dt = cfg.get('data_type_display', 'Counts')
        for dt in DATA_TYPE_OPTIONS:
            a = dt_menu.addAction(dt); a.setCheckable(True)
            a.setChecked(dt == current_dt)
            a.triggered.connect(lambda checked, d=dt: self._set_data_type(d))

        if cfg.get('mode') == 'Simple Element Correlation':
            elems = self._available_elements()
            if elems:
                xe_menu = menu.addMenu("X Element")
                for e in elems:
                    a = xe_menu.addAction(e); a.setCheckable(True)
                    a.setChecked(e == cfg.get('x_element'))
                    a.triggered.connect(lambda _, el=e: self._set_elem('x_element', el))
                ye_menu = menu.addMenu("Y Element")
                for e in elems:
                    a = ye_menu.addAction(e); a.setCheckable(True)
                    a.setChecked(e == cfg.get('y_element'))
                    a.triggered.connect(lambda _, el=e: self._set_elem('y_element', el))

                ce_menu = menu.addMenu("Color By Element")
                cur_ce = cfg.get('color_element', 'None')
                a_none = ce_menu.addAction("(None - single color)"); a_none.setCheckable(True)
                a_none.setChecked(cur_ce == 'None' or not cur_ce)
                a_none.triggered.connect(lambda _: self._set_elem('color_element', 'None'))
                for e in elems:
                    a = ce_menu.addAction(e); a.setCheckable(True)
                    a.setChecked(e == cur_ce)
                    a.triggered.connect(lambda _, el=e: self._set_elem('color_element', el))

        if self._is_multi():
            dm_menu = menu.addMenu("Display Mode")
            modes = ['Overlaid (Different Colors)', 'Side by Side Subplots',
                     'Individual Subplots', 'Combined with Legend']
            cur = cfg.get('display_mode', modes[0])
            for m in modes:
                a = dm_menu.addAction(m); a.setCheckable(True)
                a.setChecked(m == cur)
                a.triggered.connect(lambda _, mode=m: self._set_display_mode(mode))

        menu.addSeparator()
        menu.addAction("Auto-Detect Correlations...").triggered.connect(
            self._auto_detect_correlations)
        menu.addSeparator()
        menu.addAction("Configure...").triggered.connect(self._open_settings)
        menu.addAction("Download Figure...").triggered.connect(
            lambda: download_pyqtgraph_figure(self.plot_widget, self, "correlation_plot.png"))
        if _CUSTOM_PLOT_AVAILABLE:
            menu.addAction("Plot Settings...").triggered.connect(self._open_plot_settings)

        menu.exec(QCursor.pos())

    def _add_toggle(self, menu, label, key):
        """
        Args:
            menu (Any): QMenu object.
            label (Any): Label text.
            key (Any): Dictionary or storage key.
        """
        a = menu.addAction(label)
        a.setCheckable(True)
        a.setChecked(self.node.config.get(key, False))
        a.triggered.connect(lambda checked, k=key: self._toggle(k, checked))

    def _toggle(self, key, value):
        """
        Args:
            key (Any): Dictionary or storage key.
            value (Any): Value to set or process.
        """
        self.node.config[key] = value
        self._refresh()

    def _set_data_type(self, dt):
        """
        Args:
            dt (Any): The dt.
        """
        self.node.config['data_type_display'] = dt
        self._refresh()

    def _set_elem(self, key, elem):
        """
        Args:
            key (Any): Dictionary or storage key.
            elem (Any): The elem.
        """
        self.node.config[key] = elem
        self._refresh()

    def _set_display_mode(self, mode):
        """
        Args:
            mode (Any): Operating mode string.
        """
        self.node.config['display_mode'] = mode
        self._refresh()

    def _open_settings(self):
        dlg = CorrelationSettingsDialog(
            self.node.config, self._available_elements(),
            self._is_multi(), self._sample_names(), self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_plot_settings(self):
        """Open PlotSettingsDialog via the adapter bridge."""
        if not _CUSTOM_PLOT_AVAILABLE or _PlotSettingsDialog is None \
                or _PlotWidgetAdapter is None:
            return
        pi = next(
            (item for item in self.plot_widget.scene().items()
             if isinstance(item, pg.PlotItem)),
            None,
        )
        if pi is not None:
            _PlotSettingsDialog(
                _PlotWidgetAdapter(self.plot_widget, pi), self).exec()

    # ── Annotation helpers ──────────────────────

    def _click_to_data_coords(self, widget_pos) -> tuple:
        """Convert a right-click position in plot_widget coords to data coords
        on the primary plot item. Returns (x, y) as floats.
        Args:
            widget_pos (Any): The widget pos.
        """
        pi = getattr(self, '_primary_plot_item', None)
        if pi is None:
            return 0.0, 0.0
        vb = pi.getViewBox()
        if vb is None:
            return 0.0, 0.0
        try:
            scene_pt = self.plot_widget.mapToScene(widget_pos)
            data_pt = vb.mapSceneToView(scene_pt)
            return float(data_pt.x()), float(data_pt.y())
        except Exception:
            return 0.0, 0.0

    def _current_xy_arrays(self):
        """Return (x_array, y_array) pooled across samples in the plot's
        rendered coordinate space (i.e. the same values the scatter points use).
        Returns (None, None) if unavailable."""
        cfg = self.node.config
        try:
            plot_data = self.node.extract_plot_data()
        except Exception:
            return None, None
        if not plot_data:
            return None, None

        xs, ys = [], []
        if self._is_multi():
            for sd in plot_data.values():
                if not (sd and 'element_data' in sd):
                    continue
                x, y, _ = self._prepare_data(sd['element_data'], cfg)
                if len(x):
                    xs.append(np.asarray(x)); ys.append(np.asarray(y))
        else:
            if 'element_data' in plot_data:
                x, y, _ = self._prepare_data(plot_data['element_data'], cfg)
                if len(x):
                    xs.append(np.asarray(x)); ys.append(np.asarray(y))

        if not xs:
            return None, None
        return np.concatenate(xs), np.concatenate(ys)

    def _build_smart_actions(self) -> list:
        """Data-aware smart actions for correlation plots.

        All annotation coordinates are placed in the SAME coordinate system
        the scatter points use (i.e. what `_prepare_data` returns). Placements
        are additionally clamped to the data's (min, max) bounds so they never
        blow out pyqtgraph's autoRange — annotation items are also added with
        ignoreBounds=True for belt-and-suspenders.
        Returns:
            list: Result of the operation.
        """
        actions = []
        cfg = self.node.config
        mgr = self.ann_mgr

        x, y = self._current_xy_arrays()

        if x is not None and len(x) >= 3:
            x_lo, x_hi = float(np.min(x)), float(np.max(x))
            y_lo, y_hi = float(np.min(y)), float(np.max(y))
            x_span = max(x_hi - x_lo, 1e-9)
            y_span = max(y_hi - y_lo, 1e-9)

            both_linear = not cfg.get('log_x') and not cfg.get('log_y')
            both_log = cfg.get('log_x') and cfg.get('log_y')
            ranges_overlap = not (x_hi < y_lo or y_hi < x_lo)
            if (both_linear or both_log) and ranges_overlap:
                lo = max(x_lo, y_lo)
                hi = min(x_hi, y_hi)
                if hi > lo:
                    def _one_to_one(a=lo, b=hi):
                        """
                        Args:
                            a (Any): The a.
                            b (Any): The b.
                        """
                        mgr.add_new('text', b, b)
                        last = self.node.config['annotations'][-1]
                        last['text'] = 'y = x'
                        last['color'] = '#444441'
                        last['box'] = False
                        last['arrow_to'] = [a, a]
                        mgr._raw_update(last['id'], last)
                    actions.append(('Reference line  y = x', _one_to_one))

            try:
                mx = float(np.mean(x))
                my = float(np.mean(y))

                def _mean_x(val=mx):
                    """
                    Args:
                        val (Any): The val.
                    """
                    mgr.add_new('vline', val, 0)
                    last = self.node.config['annotations'][-1]
                    last['label'] = f"mean x: {val:.3g}"
                    last['color'] = '#0F6E56'
                    mgr._raw_update(last['id'], last)
                actions.append(('Mark mean x', _mean_x))

                def _mean_y(val=my):
                    """
                    Args:
                        val (Any): The val.
                    """
                    mgr.add_new('hline', 0, val)
                    last = self.node.config['annotations'][-1]
                    last['label'] = f"mean y: {val:.3g}"
                    last['color'] = '#0F6E56'
                    mgr._raw_update(last['id'], last)
                actions.append(('Mark mean y', _mean_y))
            except Exception as e:
                print(f"[smart] mark means failed: {e}")

            try:
                sx = float(np.std(x)); sy = float(np.std(y))
                mx = float(np.mean(x)); my = float(np.mean(y))
                if sx > 0 and sy > 0:
                    cx1 = max(mx - sx, x_lo)
                    cx2 = min(mx + sx, x_hi)
                    cy1 = max(my - sy, y_lo)
                    cy2 = min(my + sy, y_hi)
                    if cx2 > cx1 and cy2 > cy1:
                        def _core_box(x1=cx1, x2=cx2, y1=cy1, y2=cy2):
                            """
                            Args:
                                x1 (Any): The x1.
                                x2 (Any): The x2.
                                y1 (Any): The y1.
                                y2 (Any): The y2.
                            """
                            mgr.add_new('rect', (x1 + x2) / 2, (y1 + y2) / 2)
                            last = self.node.config['annotations'][-1]
                            last['x1'] = x1; last['x2'] = x2
                            last['y1'] = y1; last['y2'] = y2
                            last['label'] = '1σ core'
                            last['color'] = '#534AB7'
                            last['filled'] = False
                            mgr._raw_update(last['id'], last)
                        actions.append(('Highlight 1σ core region', _core_box))
            except Exception as e:
                print(f"[smart] core box failed: {e}")

            try:
                r = float(np.corrcoef(x, y)[0, 1])
                if np.isfinite(r):
                    tx = x_lo + 0.05 * x_span
                    ty = y_lo + 0.92 * y_span

                    def _r_label(xx=tx, yy=ty, rv=r):
                        """
                        Args:
                            xx (Any): The xx.
                            yy (Any): The yy.
                            rv (Any): The rv.
                        """
                        mgr.add_new('text', xx, yy)
                        last = self.node.config['annotations'][-1]
                        last['text'] = f"r = {rv:.3f}"
                        last['color'] = '#185FA5'
                        mgr._raw_update(last['id'], last)
                    actions.append(('Label Pearson r', _r_label))
            except Exception as e:
                print(f"[smart] r label failed: {e}")

            try:
                if len(x) >= 3:
                    slope, intercept = np.polyfit(x, y, 1)
                    y_pred = slope * x + intercept
                    residual_sd = float(np.std(y - y_pred))
                    if np.isfinite(residual_sd) and residual_sd > 0:
                        x_end_lo = x_lo
                        x_end_hi = x_hi
                        y_line_lo = slope * x_end_lo + intercept
                        y_line_hi = slope * x_end_hi + intercept

                        def _sd_band(xe1=x_end_lo, xe2=x_end_hi,
                                      yl1=y_line_lo, yl2=y_line_hi,
                                      sd=residual_sd, sl=slope):
                            """
                            Args:
                                xe1 (Any): The xe1.
                                xe2 (Any): The xe2.
                                yl1 (Any): The yl1.
                                yl2 (Any): The yl2.
                                sd (Any): The sd.
                                sl (Any): The sl.
                            """
                            x_mid = (xe1 + xe2) / 2
                            y_mid = sl * x_mid + (yl1 - sl * xe1)
                            mgr.add_new('rect', x_mid, y_mid)
                            last = self.node.config['annotations'][-1]
                            last['x1'] = xe1
                            last['x2'] = xe2
                            last['y1'] = y_mid - sd
                            last['y2'] = y_mid + sd
                            last['label'] = f'trend ± SD ({sd:.3g})'
                            last['color'] = '#BA7517'
                            last['filled'] = True
                            last['alpha'] = 0.18
                            last['width'] = 1
                            mgr._raw_update(last['id'], last)
                        actions.append(('Shade ±SD around trend', _sd_band))
            except Exception as e:
                print(f"[smart] trend band failed: {e}")

        return actions

    # ── Auto-detect ─────────────────────────

    def _auto_detect_correlations(self):
        pd_data = self.node.extract_plot_data()
        if not pd_data:
            QMessageBox.warning(self, "No Data", "No data available for correlation analysis.")
            return

        if self._is_multi():
            import pandas
            frames = []
            for sd in pd_data.values():
                if isinstance(sd, dict) and 'element_data' in sd:
                    frames.append(sd['element_data'])
            if not frames:
                return
            df = pandas.concat(frames, ignore_index=True)
        else:
            df = pd_data.get('element_data')

        if df is None or df.empty:
            QMessageBox.warning(self, "No Data", "Element data is empty.")
            return

        df = apply_saturation_filter(df, self.node.config)

        top = find_top_correlations(df, n_top=20, min_nonzero=10)
        if not top:
            QMessageBox.information(self, "No Correlations",
                                    "No significant correlations found.")
            return

        dlg = AutoCorrelationDialog(top, self)
        dlg.pair_selected.connect(self._apply_auto_pair)
        dlg.exec()

    def _apply_auto_pair(self, x_elem, y_elem):
        """
        Args:
            x_elem (Any): The x elem.
            y_elem (Any): The y elem.
        """
        self.node.config['mode'] = 'Simple Element Correlation'
        self.node.config['x_element'] = x_elem
        self.node.config['y_element'] = y_elem
        self._refresh()

    # ── Refresh / draw ──────────────────────

    def _cleanup_color_bars(self):
        for cb in self.active_color_bars:
            try:
                cb.remove()
            except Exception:
                pass
        self.active_color_bars.clear()

    def _refresh(self):
        try:
            if hasattr(self, 'ann_mgr'):
                self.ann_mgr._detach_all()

            self._cleanup_color_bars()

            self._plot_container_layout.removeWidget(self.plot_widget)
            self.plot_widget.deleteLater()
            self.plot_widget = EnhancedGraphicsLayoutWidget()
            self.plot_widget.setBackground('w')
            self.plot_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            self.plot_widget.customContextMenuRequested.connect(self._show_context_menu)
            self._plot_container_layout.addWidget(self.plot_widget)

            plot_data = self.node.extract_plot_data()

            primary_plot = None

            if not plot_data:
                pi = self.plot_widget.addPlot()
                ti = pg.TextItem(
                    "No data available\nRight-click for options",
                    anchor=(0.5, 0.5), color='gray')
                pi.addItem(ti); ti.setPos(0.5, 0.5)
                pi.hideAxis('left'); pi.hideAxis('bottom')
                primary_plot = pi
            else:
                cfg = self.node.config

                if self._is_multi():
                    dm = cfg.get('display_mode', 'Overlaid (Different Colors)')
                    if dm == 'Individual Subplots':
                        self._draw_subplots(plot_data, cfg)
                        primary_plot = self.plot_widget.getItem(0, 0)
                    elif dm == 'Side by Side Subplots':
                        self._draw_side_by_side(plot_data, cfg)
                        primary_plot = self.plot_widget.getItem(0, 0)
                    else:
                        pi = self.plot_widget.addPlot()
                        self._draw_combined(pi, plot_data, cfg)
                        apply_font_to_pyqtgraph(pi, cfg)
                        primary_plot = pi
                else:
                    pi = self.plot_widget.addPlot()
                    self._draw_single(pi, plot_data, cfg)
                    apply_font_to_pyqtgraph(pi, cfg)
                    primary_plot = pi

            self._primary_plot_item = primary_plot

            if hasattr(self, 'ann_mgr') and primary_plot is not None:
                self.ann_mgr.attach_plot(primary_plot)
            if hasattr(self, 'ann_inspector'):
                self.ann_inspector.attach(primary_plot)

        except Exception as e:
            print(f"Error refreshing correlation display: {e}")
            import traceback; traceback.print_exc()

    # ── Drawing helpers ─────────────────────

    def _extract_xy_color(self, df, cfg):
        """Extract (x, y, color_or_None) arrays from a DataFrame and config.
        Args:
            df (Any): Pandas DataFrame.
            cfg (Any): The cfg.
        Returns:
            tuple: Result of the operation.
        """
        mode = cfg.get('mode', 'Simple Element Correlation')

        if mode == 'Simple Element Correlation':
            xn = cfg.get('x_element', '')
            yn = cfg.get('y_element', '')
            if not (xn and yn and xn in df.columns and yn in df.columns):
                return np.array([]), np.array([]), None
            x = df[xn].values
            y = df[yn].values
            cn = cfg.get('color_element', 'None')
            c = df[cn].values if (cn != 'None' and cn in df.columns) else None
            return x, y, c
        else:
            xeq = cfg.get('x_equation', '').strip()
            yeq = cfg.get('y_equation', '').strip()
            if not (xeq and yeq):
                return np.array([]), np.array([]), None
            xa = evaluate_equation_array(xeq, df)
            ya = evaluate_equation_array(yeq, df)
            mask = ~(np.isnan(xa) | np.isnan(ya) | np.isinf(xa) | np.isinf(ya))
            return xa[mask], ya[mask], None

    def _prepare_data(self, df, cfg):
        """Filter + log-transform + outlier removal. Returns (x, y, color) ready for plotting.
        Args:
            df (Any): Pandas DataFrame.
            cfg (Any): The cfg.
        """
        df = apply_saturation_filter(df, cfg)
        if df.empty:
            return np.array([]), np.array([]), None

        x, y, c = self._extract_xy_color(df, cfg)
        if len(x) == 0:
            return x, y, c

        if cfg.get('filter_zeros', True):
            x, y, c = apply_zero_filter(x, y, c)

        if cfg.get('log_x') and len(x):
            others = [y] + ([c] if c is not None else [])
            x, others = apply_log_transform(x, others)
            y = others[0]
            c = others[1] if len(others) > 1 else None

        if cfg.get('log_y') and len(y):
            others = [x] + ([c] if c is not None else [])
            y, others = apply_log_transform(y, others)
            x = others[0]
            c = others[1] if len(others) > 1 else None

        if cfg.get('filter_outliers', False) and len(y) > 3:
            y_arr = np.asarray(y)
            pct = float(cfg.get('outlier_percentile', 99.0))
            lo, hi = np.percentile(y_arr, [100.0 - pct, pct])
            mask = (y_arr >= lo) & (y_arr <= hi)
            x = np.asarray(x)[mask]
            y = y_arr[mask]
            if c is not None:
                c = np.asarray(c)[mask]

        return x, y, c

    def _plot_scatter(self, pi, x, y, c, cfg, color):
        """Add scatter + optional trend + SD envelope + ref line + box to a PlotItem.
        Args:
            pi (Any): The pi.
            x (Any): Input array or value.
            y (Any): Input array or value.
            c (Any): The c.
            cfg (Any): The cfg.
            color (Any): Colour value.
        Returns:
            object: Result of the operation.
        """
        from PySide6.QtGui import QColor as _QC
        mode = cfg.get('mode', 'Simple Element Correlation')
        if (mode == 'Simple Element Correlation' and c is not None
                and cfg.get('color_element', 'None') != 'None'):
            scatter = create_color_mapped_scatter(
                pi, x, y, c, cfg, color,
                element_name=cfg.get('color_element'),
                active_color_bars=self.active_color_bars)
        else:
            scatter = create_single_color_scatter(pi, x, y, cfg, color)

        if cfg.get('show_trendline', True) and len(x) > 1:
            add_trend_line(pi, x, y, color)

            if cfg.get('show_sd_band', False) and len(x) > 2:
                try:
                    coeffs = np.polyfit(x, y, 1)
                    y_hat = np.polyval(coeffs, x)
                    residuals = y - y_hat
                    sd_r = float(np.std(residuals))
                    x_sorted = np.sort(x)
                    y_fit = np.polyval(coeffs, x_sorted)
                    band_color = cfg.get('sd_band_color', '#3B82F6')
                    band_alpha = int(cfg.get('sd_band_alpha', 0.18) * 255)
                    qc = _QC(band_color); qc.setAlpha(band_alpha)
                    upper = y_fit + sd_r
                    lower = y_fit - sd_r
                    fill = pg.FillBetweenItem(
                        pg.PlotDataItem(x=x_sorted, y=upper),
                        pg.PlotDataItem(x=x_sorted, y=lower),
                        brush=pg.mkBrush(qc),
                    )
                    fill.setZValue(-5)
                    pi.addItem(fill)
                except Exception as e:
                    print(f'[SD envelope] {e}')

        if cfg.get('show_correlation', True) and len(x) > 1:
            add_correlation_text(pi, x, y, cfg)

        if cfg.get('show_ref_line', False) and len(x) > 0:
            try:
                slope = float(cfg.get('ref_line_slope', 1.0))
                intercept = float(cfg.get('ref_line_intercept', 0.0))
                x_min, x_max = float(np.min(x)), float(np.max(x))
                xr = np.array([x_min - 0.05*(x_max - x_min),
                                x_max + 0.05*(x_max - x_min)])
                yr = slope * xr + intercept
                ref_color = cfg.get('ref_line_color', '#A32D2D')
                ref_style = _QT_LINE.get(cfg.get('ref_line_style', 'dash'),
                                         pg.QtCore.Qt.DashLine)
                ref_width = int(cfg.get('ref_line_width', 2))
                pi.addItem(pg.PlotDataItem(
                    x=xr, y=yr,
                    pen=pg.mkPen(color=ref_color, style=ref_style, width=ref_width)))
                custom_lbl = cfg.get('ref_line_label', '').strip()
                label = custom_lbl if custom_lbl else (
                    f'y = {slope:g}x' + (f' + {intercept:g}' if intercept else ''))
                lbl_item = pg.TextItem(label, color=ref_color, anchor=(0, 1))
                lbl_item.setPos(float(xr[-1]), float(yr[-1]))
                pi.addItem(lbl_item)
            except Exception as e:
                print(f'[ref line] {e}')

        _apply_box(pi, cfg)
        return scatter

    def _apply_labels(self, pi, cfg):
        """
        Args:
            pi (Any): The pi.
            cfg (Any): The cfg.
        """
        if cfg.get('mode') != 'Simple Element Correlation':
            x_lbl = cfg.get('x_label', '') or cfg.get('x_equation', 'X-axis')
            y_lbl = cfg.get('y_label', '') or cfg.get('y_equation', 'Y-axis')
            dt = cfg.get('data_type_display', 'Counts')
            xl = f"log({x_lbl})" if cfg.get('log_x') else x_lbl
            yl = f"log({y_lbl})" if cfg.get('log_y') else y_lbl
        else:
            xl, yl = build_axis_labels(cfg)
        set_axis_labels(pi, xl, yl, cfg)

        if cfg.get('log_x'):
            pi.getAxis('bottom').setLogMode(True)
        if cfg.get('log_y'):
            pi.getAxis('left').setLogMode(True)

        if not cfg.get('auto_x', True):
            pi.setXRange(cfg.get('x_min', 0), cfg.get('x_max', 1000), padding=0)
        if not cfg.get('auto_y', True):
            pi.setYRange(cfg.get('y_min', 0), cfg.get('y_max', 1000), padding=0)

    # ── Single sample ───────────────────────

    def _draw_single(self, pi, plot_data, cfg):
        """
        Args:
            pi (Any): The pi.
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        df = plot_data.get('element_data')
        if df is None or df.empty:
            return
        x, y, c = self._prepare_data(df, cfg)
        if len(x) == 0:
            pi.addItem(pg.TextItem("No valid data", anchor=(0.5, 0.5), color='red'))
            return
        color = cfg.get('single_sample_color', '#3B82F6')
        self._plot_scatter(pi, x, y, c, cfg, color)
        self._apply_labels(pi, cfg)

    # ── Multiple samples ────────────────────

    def _draw_subplots(self, plot_data, cfg):
        """
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        names = list(plot_data.keys())
        cols = min(3, len(names))
        for i, sn in enumerate(names):
            pi = self.plot_widget.addPlot(row=i // cols, col=i % cols)
            sd = plot_data[sn]
            if sd and 'element_data' in sd:
                x, y, c = self._prepare_data(sd['element_data'], cfg)
                if len(x):
                    color = get_sample_color(sn, i, cfg)
                    self._plot_scatter(pi, x, y, c, cfg, color)
                pi.setTitle(get_display_name(sn, cfg))
                self._apply_labels(pi, cfg)
                apply_font_to_pyqtgraph(pi, cfg)

    def _draw_side_by_side(self, plot_data, cfg):
        """
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        first_pi = None
        for i, (sn, sd) in enumerate(plot_data.items()):
            pi = self.plot_widget.addPlot(row=0, col=i)
            if sd and 'element_data' in sd:
                x, y, c = self._prepare_data(sd['element_data'], cfg)
                if len(x):
                    color = get_sample_color(sn, i, cfg)
                    self._plot_scatter(pi, x, y, c, cfg, color)
            pi.setTitle(get_display_name(sn, cfg))
            if first_pi is None:
                first_pi = pi
                self._apply_labels(pi, cfg)
            else:
                pi.setYLink(first_pi)
                pi.getAxis('left').setLabel('')
                pi.getAxis('left').setStyle(showValues=False)
                if cfg.get('log_x'):
                    pi.getAxis('bottom').setLogMode(True)
                if not cfg.get('auto_x', True):
                    pi.setXRange(cfg.get('x_min', 0), cfg.get('x_max', 1000), padding=0)
            apply_font_to_pyqtgraph(pi, cfg)

    def _draw_combined(self, pi, plot_data, cfg):
        """
        Args:
            pi (Any): The pi.
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        legend_items = []
        for i, (sn, sd) in enumerate(plot_data.items()):
            if not (sd and 'element_data' in sd):
                continue
            x, y, c = self._prepare_data(sd['element_data'], cfg)
            if len(x) == 0:
                continue
            color = get_sample_color(sn, i, cfg)
            scatter = self._plot_scatter(pi, x, y, c, cfg, color)
            legend_items.append((scatter, get_display_name(sn, cfg)))

        self._apply_labels(pi, cfg)
        if legend_items:
            leg = pi.addLegend()
            for item, name in legend_items:
                leg.addItem(item, name)


class CorrelationPlotNode(QObject):
    """
    Correlation plot node with multiple sample support and auto-detection.
    """

    position_changed = Signal(object)
    configuration_changed = Signal()

    DEFAULT_CONFIG = {
        'mode': 'Simple Element Correlation',
        'x_element': '', 'y_element': '', 'color_element': 'None',
        'x_equation': '', 'y_equation': '',
        'x_label': 'X-axis', 'y_label': 'Y-axis',
        'data_type_display': 'Counts',
        'filter_zeros': True, 'filter_saturated': True,
        'filter_outliers': False,
        'outlier_percentile': 99.0,
        'saturation_threshold': 10000,
        'show_correlation': True, 'show_trendline': True,
        'show_sd_band': False,
        'sd_band_color': '#3B82F6',
        'sd_band_alpha': 0.18,
        'show_ref_line': False,
        'ref_line_slope': 1.0,
        'ref_line_intercept': 0.0,
        'ref_line_color': '#A32D2D',
        'ref_line_style': 'dash',
        'ref_line_width': 2,
        'ref_line_label': '',
        'log_x': False, 'log_y': False,
        'auto_x': True, 'x_min': 0.0, 'x_max': 1000.0,
        'auto_y': True, 'y_min': 0.0, 'y_max': 1000.0,
        'marker_size': 6, 'marker_alpha': 0.7,
        'single_sample_color': '#3B82F6',
        'display_mode': 'Overlaid (Different Colors)',
        'show_box': True,
        'sample_colors': {}, 'sample_name_mappings': {},
        'sample_order': [],
        'font_family': 'Times New Roman', 'font_size': 18,
        'font_bold': False, 'font_italic': False, 'font_color': '#000000',
        'annotations': [],
    }

    def __init__(self, parent_window=None):
        """
        Args:
            parent_window (Any): The parent window.
        """
        super().__init__()
        self.title = "Element Correlation"
        self.node_type = "correlation_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        self.config = dict(self.DEFAULT_CONFIG)
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
        dlg = CorrelationPlotDisplayDialog(self, parent_window)
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
        if not self.config.get('x_element') or not self.config.get('y_element'):
            self._auto_configure_elements()
        self.configuration_changed.emit()

    def _auto_configure_elements(self):
        elems = self._get_elements()
        if len(elems) >= 2:
            self.config['x_element'] = elems[0]
            self.config['y_element'] = elems[1]

    def _get_elements(self) -> list:
        """
        Returns:
            list: Result of the operation.
        """
        if not self.input_data:
            return []
        sel = self.input_data.get('selected_isotopes', [])
        return [iso['label'] for iso in sel]

    def extract_plot_data(self):
        """
        Returns:
            None
        """
        if not self.input_data:
            return None
        dk = DATA_KEY_MAPPING.get(
            self.config.get('data_type_display', 'Counts'), 'elements')
        itype = self.input_data.get('type')

        if itype == 'sample_data':
            particles = self.input_data.get('particle_data')
            df = build_element_matrix(particles, dk) if particles else None
            return {'element_data': df} if df is not None else None

        elif itype == 'multiple_sample_data':
            particles = self.input_data.get('particle_data', [])
            names = self.input_data.get('sample_names', [])
            if not particles:
                return None
            grouped = {n: [] for n in names}
            for p in particles:
                src = p.get('source_sample')
                if src in grouped:
                    grouped[src].append(p)
            result = {}
            for sn, plist in grouped.items():
                df = build_element_matrix(plist, dk)
                if df is not None:
                    result[sn] = {'element_data': df}
            return result or None

        return None