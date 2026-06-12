from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QPushButton,
    QLineEdit, QScrollArea, QWidget, QMenu, QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QColorDialog,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QCursor
import pyqtgraph as pg
import numpy as np
import re

from results.shared_plot_utils import (
    FONT_FAMILIES, DATA_TYPE_OPTIONS, DATA_KEY_MAPPING, get_font_config,
    apply_font_to_pyqtgraph, set_axis_labels, LABEL_MODES, format_label_text_tokens,
    Renderer, build_axis_labels, apply_saturation_filter,
    apply_zero_filter, apply_log_transform,
    evaluate_equation_array, build_element_matrix, find_top_correlations,
    create_single_color_scatter, create_color_mapped_scatter, add_trend_line,
    add_correlation_text, CustomColorBar,
    get_sample_color, get_display_name,
    download_pyqtgraph_figure, pick_color_hex, _QT_LINE,
    _apply_box,
)
import logging
_itk_log = logging.getLogger("IsotopeTrack.results.results_correlation")

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


class CorrelationSettingsDialog(QDialog):
    """Full settings dialog opened from the right-click → Configure… action."""

    def __init__(self, config: dict, available_elements: list,
                 is_multi: bool, sample_names: list,
                 scope: str = "all", parent=None):
        """
        Args:
            config (dict): Configuration dictionary.
            available_elements (list): The available elements.
            is_multi (bool): The is multi.
            sample_names (list): The sample names.
            scope (str): Which settings scope to expose and collect:
                ``format``, ``quantities``, or ``all``.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self._scope = scope if scope in {"format", "quantities", "all"} else "all"
        if self._scope == "format":
            self.setWindowTitle("Correlation plot format settings")
        elif self._scope == "quantities":
            self.setWindowTitle("Correlation quantities configuration")
        else:
            self.setWindowTitle("Correlation Plot Settings")
        self.setMinimumWidth(460)
        self._config = dict(config)
        self._elements = available_elements
        self._is_multi = is_multi
        self._sample_names = sample_names
        self.display_mode = None
        self._sample_name_edits = None
        self._sample_color_buttons = None
        self._sample_colors = dict(self._config.get('sample_colors', {}))
        self._single_sample_color = self._config.get('single_sample_color', '#3B82F6')
        self._single_sample_color_btn = None
        self._format_groups = []
        self._quantity_groups = []
        self._build_ui()

    # ── UI construction ──────────────────────

    def _sample_point_colors_available(self) -> bool:
        """Return whether sample-owned colors currently drive scatter points.

        Returns:
            bool: ``True`` when Correlation is not using element-based
                color-mapped points through the active ``Color by`` selection.

        Preserved behavior:
            This only gates format-settings controls. It does not change
            plotted values, correlation math, or the existing color-mapped
            scatter rendering path.
        """
        if self._config.get('mode', 'Simple Element Correlation') != 'Simple Element Correlation':
            return True
        return self._config.get('color_element', 'None') == 'None'

    def _sample_point_color_unavailable_text(self) -> str:
        """Return the explanatory note for disabled sample point colors.

        Returns:
            str: Short user-facing explanation shown when ``Color by`` owns
                point appearance instead of per-sample colors.
        """
        color_element = self._config.get('color_element', 'None')
        if color_element and color_element != 'None':
            return (
                "Sample point colors are unavailable because points are "
                f"colored by the selected Color By element: {color_element}."
            )
        return "Sample point colors are unavailable for the current plot mode."

    def _style_color_button(self, button: QPushButton, color: str) -> None:
        """Apply a compact swatch preview to a Correlation color button.

        Args:
            button (QPushButton): Swatch button to update.
            color (str): Hex color string to preview.
        """
        button.setStyleSheet(f"background:{color};")

    def _sample_display_label(self, sample_name: str) -> str:
        """Return the visible display label for one raw sample key.

        Args:
            sample_name (str): Raw canonical sample key.

        Returns:
            str: Current display label, falling back to the raw sample key.
        """
        return get_display_name(sample_name, self._config)

    def _pick_single_sample_color(self) -> None:
        """Pick the actual single-sample scatter point color."""
        picked = pick_color_hex(
            self._single_sample_color,
            owner=self,
            title="Point Color",
        )
        if picked:
            self._single_sample_color = picked
            if self._single_sample_color_btn is not None:
                self._style_color_button(self._single_sample_color_btn, picked)

    def _pick_sample_color(self, sample_name: str, button: QPushButton) -> None:
        """Pick one canonical scatter color for a raw multi-sample key.

        Args:
            sample_name (str): Raw canonical sample key whose point color is
                being edited.
            button (QPushButton): Swatch button previewing the current color.
        """
        initial = self._sample_colors.get(sample_name, '#3B82F6')
        picked = pick_color_hex(initial, owner=self, title="Sample Point Color")
        if picked:
            self._sample_colors[sample_name] = picked
            self._style_color_button(button, picked)

    def _reset_sample_color(self, sample_name: str, sample_index: int,
                            button: QPushButton) -> None:
        """Reset one sample color override back to palette fallback.

        Args:
            sample_name (str): Raw canonical sample key to clear.
            sample_index (int): Stable palette index for this sample.
            button (QPushButton): Swatch button to refresh after clearing.
        """
        self._sample_colors.pop(sample_name, None)
        fallback = get_sample_color(sample_name, sample_index, {'sample_colors': {}})
        self._style_color_button(button, fallback)

    def _build_ui(self):
        """
        Build settings UI sections and mark each section as format or quantities.

        A single dialog class is reused for both bottom-button routes. Scope
        visibility and scope-aware collection prevent duplicated/no-op controls.
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
                'Individual Subplots'
            ])
            self.display_mode.setCurrentText(
                CorrelationPlotDisplayDialog.normalize_display_mode(
                    self._config.get('display_mode', 'Overlaid (Different Colors)')
                )
            )
            fl.addRow("Display Mode:", self.display_mode)
            layout.addWidget(g)
            self._quantity_groups.append(g)

        g = QGroupBox("Analysis Mode")
        vl = QVBoxLayout(g)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(['Simple Element Correlation', 'Custom Mathematical Expressions'])
        self.mode_combo.setCurrentText(self._config.get('mode', 'Simple Element Correlation'))
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        vl.addWidget(self.mode_combo)
        layout.addWidget(g)
        self._quantity_groups.append(g)

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
        self._quantity_groups.append(self.simple_group)

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
        self._quantity_groups.append(self.custom_group)

        g = QGroupBox("Data Type")
        fl = QFormLayout(g)
        self.data_type = QComboBox(); self.data_type.addItems(DATA_TYPE_OPTIONS)
        self.data_type.setCurrentText(self._config.get('data_type_display', 'Counts'))
        fl.addRow("Data Type:", self.data_type)
        layout.addWidget(g)
        self._quantity_groups.append(g)

        g = QGroupBox("Plot Options")
        fl = QFormLayout(g)
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
        self.log_x = QCheckBox(); self.log_x.setChecked(self._config.get('log_x', False))
        fl.addRow("Log X:", self.log_x)
        self.log_y = QCheckBox(); self.log_y.setChecked(self._config.get('log_y', False))
        fl.addRow("Log Y:", self.log_y)
        layout.addWidget(g)
        self._quantity_groups.append(g)

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
        self._format_groups.append(g)

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
        self._format_groups.append(g)

        g = QGroupBox("Marker")
        fl = QFormLayout(g)
        self.m_size = QSpinBox(); self.m_size.setRange(1, 20)
        self.m_size.setValue(self._config.get('marker_size', 6))
        fl.addRow("Size:", self.m_size)
        self.m_alpha = QDoubleSpinBox(); self.m_alpha.setRange(0.1, 1.0)
        self.m_alpha.setSingleStep(0.1); self.m_alpha.setDecimals(1)
        self.m_alpha.setValue(self._config.get('marker_alpha', 0.7))
        fl.addRow("Alpha:", self.m_alpha)
        self.show_box_cb = QCheckBox(); self.show_box_cb.setChecked(self._config.get('show_box', True))
        fl.addRow("Figure box (frame):", self.show_box_cb)
        layout.addWidget(g)
        self._format_groups.append(g)

        if self._is_multi:
            g = QGroupBox("Sample Point Colors")
            sl = QVBoxLayout(g)
            if self._sample_point_colors_available():
                self._sample_color_buttons = {}
                for index, sn in enumerate(self._sample_names):
                    row = QHBoxLayout()
                    label = QLabel(self._sample_display_label(sn)[:28])
                    label.setToolTip(f"Raw key: {sn}")
                    row.addWidget(label)
                    btn = QPushButton()
                    btn.setFixedSize(26, 22)
                    color = get_sample_color(sn, index, self._config)
                    self._style_color_button(btn, color)
                    btn.clicked.connect(
                        lambda _, sample_name=sn, swatch=btn: self._pick_sample_color(sample_name, swatch))
                    row.addWidget(btn)
                    rst = QPushButton("Reset")
                    rst.setFixedHeight(22)
                    rst.clicked.connect(
                        lambda _, sample_name=sn, sample_index=index, swatch=btn:
                            self._reset_sample_color(sample_name, sample_index, swatch))
                    row.addWidget(rst)
                    row.addStretch()
                    w = QWidget(); w.setLayout(row)
                    sl.addWidget(w)
                    self._sample_color_buttons[sn] = btn
            else:
                note = QLabel(self._sample_point_color_unavailable_text())
                note.setWordWrap(True)
                note.setStyleSheet("color:#6B7280;")
                sl.addWidget(note)
            layout.addWidget(g)
            self._format_groups.append(g)
        else:
            g = QGroupBox("Point Color")
            fl = QFormLayout(g)
            if self._sample_point_colors_available():
                row = QHBoxLayout()
                self._single_sample_color_btn = QPushButton()
                self._single_sample_color_btn.setFixedSize(26, 22)
                self._style_color_button(self._single_sample_color_btn, self._single_sample_color)
                self._single_sample_color_btn.clicked.connect(self._pick_single_sample_color)
                row.addWidget(self._single_sample_color_btn)
                row.addStretch()
                fl.addRow("Scatter points:", row)
            else:
                note = QLabel(self._sample_point_color_unavailable_text())
                note.setWordWrap(True)
                note.setStyleSheet("color:#6B7280;")
                fl.addRow(note)
            layout.addWidget(g)
            self._format_groups.append(g)

        g = QGroupBox("Font")
        fl = QFormLayout(g)
        self.font_family_combo = QComboBox()
        self.font_family_combo.addItems(FONT_FAMILIES)
        self.font_family_combo.setCurrentText(self._config.get('font_family', 'Times New Roman'))
        fl.addRow("Family:", self.font_family_combo)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 48)
        self.font_size_spin.setValue(int(self._config.get('font_size', 18)))
        fl.addRow("Size:", self.font_size_spin)
        self.font_color_btn = QPushButton()
        self._font_color = self._config.get('font_color', '#000000')
        self.font_color_btn.setFixedWidth(40)
        self.font_color_btn.setStyleSheet(f"background:{self._font_color};")
        self.font_color_btn.clicked.connect(self._pick_font_color)
        fl.addRow("Color:", self.font_color_btn)
        layout.addWidget(g)
        self._format_groups.append(g)


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
            self._format_groups.append(g)

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
        self._quantity_groups.append(g)

        layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

        self._apply_scope_visibility()
        self._on_mode_changed()

    def _apply_scope_visibility(self):
        """Show only relevant setting groups for the current route scope.

        Format routes show visual controls; quantities routes show scientific
        controls. This avoids duplicated/no-op controls while preserving one
        dialog implementation.
        """
        show_format = self._scope in {"format", "all"}
        show_quantities = self._scope in {"quantities", "all"}
        for grp in self._format_groups:
            if grp is not None:
                grp.setVisible(show_format)
        for grp in self._quantity_groups:
            if grp is not None:
                grp.setVisible(show_quantities)

    def _on_mode_changed(self):
        """Toggle simple/custom selector groups for quantity-editing routes."""
        if self._scope == "format":
            return
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
        if not hasattr(self, '_order_list') or self._order_list is None:
            return
        row = self._order_list.currentRow()
        if row > 0:
            item = self._order_list.takeItem(row)
            self._order_list.insertItem(row - 1, item)
            self._order_list.setCurrentRow(row - 1)

    def _move_down(self):
        if not hasattr(self, '_order_list') or self._order_list is None:
            return
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

    def _pick_font_color(self):
        """Pick the font/text color used for axis labels and overlay text."""
        c = QColorDialog.getColor(QColor(self._font_color), self)
        if c.isValid():
            self._font_color = c.name()
            self.font_color_btn.setStyleSheet(f"background:{self._font_color};")

    def collect(self) -> dict:
        """Return scope-safe config updates for format/quantities routes.

        The active scope controls which keys are collected so the dialog never
        reads missing/deleted widgets from sections not created for that route.
        """
        cfg = dict(self._config)
        if self._scope in {"quantities", "all"}:
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
            cfg['filter_saturated'] = self.filter_sat.isChecked()
            cfg['saturation_threshold'] = self.sat_thresh.value()
            cfg['filter_outliers'] = self.filter_outliers_cb.isChecked()
            cfg['outlier_percentile'] = self.outlier_pct.value()
            cfg['log_x'] = self.log_x.isChecked()
            cfg['log_y'] = self.log_y.isChecked()
            if self._is_multi and self.display_mode is not None:
                cfg['display_mode'] = CorrelationPlotDisplayDialog.normalize_display_mode(
                    self.display_mode.currentText()
                )

        if self._scope in {"format", "all"}:
            cfg['show_box'] = self.show_box_cb.isChecked()
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
            if self._is_multi and self._sample_color_buttons is not None:
                cfg['sample_colors'] = dict(self._sample_colors)
            if (not self._is_multi and self._single_sample_color_btn is not None
                    and self._sample_point_colors_available()):
                cfg['single_sample_color'] = self._single_sample_color
            cfg['font_family'] = self.font_family_combo.currentText()
            cfg['font_size'] = self.font_size_spin.value()
            cfg['font_color'] = self._font_color
            if self._is_multi and self._sample_name_edits is not None:
                nm = {}
                for sn, ne in self._sample_name_edits.items():
                    if ne.text() != sn:
                        nm[sn] = ne.text()
                cfg['sample_name_mappings'] = nm
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

    The dialog follows the four-button Results contract for settings, reset, and
    export. Right-click stays minimal with quick visual toggles, isotope-label
    rendering modes, and the correlation-specific auto-detect action.
    """

    DISPLAY_MODE_OVERLAID = 'Overlaid (Different Colors)'
    DISPLAY_MODE_SIDE = 'Side by Side Subplots'
    DISPLAY_MODE_SUBPLOTS = 'Individual Subplots'
    DISPLAY_MODE_LEGACY_COMBINED = 'Combined with Legend'

    @staticmethod
    def normalize_display_mode(mode: str) -> str:
        """Normalize legacy Correlation display modes to active UI modes.

        The old ``Combined with Legend`` mode is treated as overlaid because both
        routes share the same combined draw path in current Correlation behavior.
        """
        if mode == CorrelationPlotDisplayDialog.DISPLAY_MODE_LEGACY_COMBINED:
            return CorrelationPlotDisplayDialog.DISPLAY_MODE_OVERLAID
        if mode in {
            CorrelationPlotDisplayDialog.DISPLAY_MODE_OVERLAID,
            CorrelationPlotDisplayDialog.DISPLAY_MODE_SIDE,
            CorrelationPlotDisplayDialog.DISPLAY_MODE_SUBPLOTS,
        }:
            return mode
        return CorrelationPlotDisplayDialog.DISPLAY_MODE_OVERLAID

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
        self._subplot_context_by_plotitem = {}
        self._current_display_mode = self.DISPLAY_MODE_OVERLAID
        self._setup_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    # ── helpers ─────────────────────────────

    def _is_multi(self) -> bool:
        """
        Returns:
            bool: Result of the operation.
        """
        return bool(self.node.input_data and
                    self.node.input_data.get('type') == 'multiple_sample_data')

    def _sample_names(self) -> list:
        """
        Returns:
            list: Result of the operation.
        """
        if self._is_multi():
            return self.node.input_data.get('sample_names', [])
        return []

    def _ordered_plot_data_items(self, plot_data):
        """Return plot_data items in configured sample order when available.

        This preserves backward compatibility with existing ``sample_order``
        config while avoiding a no-op sample-order editor in Phase 1 UI.
        """
        if not isinstance(plot_data, dict):
            return []
        keys = list(plot_data.keys())
        order = self.node.config.get('sample_order', [])
        if not order:
            return list(plot_data.items())
        ordered_keys = [k for k in order if k in plot_data]
        ordered_keys += [k for k in keys if k not in ordered_keys]
        return [(k, plot_data[k]) for k in ordered_keys]

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
            _itk_log.exception("Handled exception in _available_elements")
        sel = (self.node.input_data or {}).get('selected_isotopes', [])
        return [iso['label'] for iso in sel]

    # ── UI ──────────────────────────────────

    def _setup_ui(self):
        """Build the Correlation dialog with a full-width four-button action row.

        The bottom actions are kept in the standardized Results order and each
        button is given equal layout stretch so the row spans the dialog width
        consistently with other migrated result plots.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._plot_container = QWidget()
        self._plot_container_layout = QVBoxLayout(self._plot_container)
        self._plot_container_layout.setContentsMargins(0, 0, 0, 0)
        self._plot_container_layout.setSpacing(0)

        self.plot_widget = CorrelationGraphicsLayoutWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.plot_widget.customContextMenuRequested.connect(self._show_context_menu)
        self._plot_container_layout.addWidget(self.plot_widget)
        self._primary_plot_item = None
        layout.addWidget(self._plot_container, stretch=1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(6, 0, 6, 0)
        bottom.setSpacing(8)
        self.format_btn = QPushButton("Plot format settings")
        self.format_btn.clicked.connect(self._open_plot_format_settings)
        bottom.addWidget(self.format_btn, 1)
        self.quantities_btn = QPushButton("Configure plot quantities")
        self.quantities_btn.clicked.connect(self._open_configure_plot_quantities)
        bottom.addWidget(self.quantities_btn, 1)
        self.reset_btn = QPushButton("Reset layout")
        self.reset_btn.clicked.connect(self._reset_layout)
        bottom.addWidget(self.reset_btn, 1)
        self.export_btn = QPushButton("Export figure")
        self.export_btn.clicked.connect(self._export_figure)
        bottom.addWidget(self.export_btn, 1)
        layout.addLayout(bottom)

    # ── Context menu ────────────────────────

    def _show_context_menu(self, pos):
        """Show Correlation right-click actions with mode-aware subplot export.

        ``Export this subplot...`` is intentionally enabled only in
        ``Individual Subplots`` mode. Other modes keep a disabled action with
        an explanatory tooltip.
        """
        cfg = self.node.config
        menu = QMenu(self)

        tm = menu.addMenu("Quick Toggles")
        for key, label, default in [
            ('show_trendline',  'Trend Line',         True),
            ('show_correlation','Correlation r',      True),
            ('show_sd_band',    'SD Envelope',        False),
            ('show_ref_line',   'Reference Line',     False),
            ('show_box',        'Figure Box (frame)', True),
        ]:
            a = tm.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, default))
            a.triggered.connect(lambda checked, k=key: self._toggle(k, checked))

        lm_menu = menu.addMenu("Isotope Label")
        cur_lm = cfg.get('label_mode', 'Symbol')
        for mode in LABEL_MODES:
            a = lm_menu.addAction(mode); a.setCheckable(True)
            a.setChecked(mode == cur_lm)
            a.triggered.connect(lambda _, m=mode: self._set_elem('label_mode', m))
        menu.addAction("Auto-Detect Correlations...").triggered.connect(
            self._auto_detect_correlations)

        clicked_plot = self._plot_item_at(pos)
        subplot_ctx = self._subplot_context_by_plotitem.get(clicked_plot)
        can_export_subplot = (
            self._current_display_mode == self.DISPLAY_MODE_SUBPLOTS
            and clicked_plot is not None
            and subplot_ctx is not None
        )
        if can_export_subplot:
            action = menu.addAction("Export this subplot...")
            action.triggered.connect(
                lambda: self._export_subplot(clicked_plot, subplot_ctx)
            )
        else:
            disabled = menu.addAction("Export this subplot... (unavailable here)")
            disabled.setEnabled(False)
            if self._current_display_mode == self.DISPLAY_MODE_SIDE:
                reason = (
                    "Individual subplot export is only available in "
                    "Individual Subplots mode."
                )
            else:
                reason = "Right-click an individual subplot panel to export only that panel."
            disabled.setToolTip(reason)
            disabled.setStatusTip(reason)

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
        """Set display mode using alias-normalized values and refresh."""
        self.node.config['display_mode'] = self.normalize_display_mode(mode)
        self._refresh()

    def _open_plot_format_settings(self):
        """Open scoped visual formatting controls and refresh on apply."""
        dlg = CorrelationSettingsDialog(
            self.node.config, self._available_elements(),
            self._is_multi(), self._sample_names(), scope="format", parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_configure_plot_quantities(self):
        """Open scoped quantity controls and refresh on apply."""
        dlg = CorrelationSettingsDialog(
            self.node.config, self._available_elements(),
            self._is_multi(), self._sample_names(), scope="quantities", parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _reset_layout(self):
        """Reset current view layout by re-enabling axis autorange and redrawing."""
        self.node.config['auto_x'] = True
        self.node.config['auto_y'] = True
        self._refresh()

    def _export_figure(self):
        """Export the full Correlation figure with the shared export workflow."""
        download_pyqtgraph_figure(self.plot_widget, self, "correlation_plot.png")

    def _plot_item_at(self, pos):
        """Resolve the clicked PlotItem using scene-space hit testing.

        This mirrors the reliable subplot hit-testing pattern used in other
        migrated result plots for item-targeted export actions.
        """
        scene_pos = self.plot_widget.mapToScene(pos)
        for item in self.plot_widget.scene().items():
            if isinstance(item, pg.PlotItem):
                rect = item.mapRectToScene(item.boundingRect())
                if rect.contains(scene_pos):
                    return item
        return None

    def _sanitize_filename_token(self, text: str) -> str:
        """Sanitize subplot names for use in export filename stems."""
        cleaned = re.sub(r'[^A-Za-z0-9._-]+', '_', (text or '').strip())
        return cleaned.strip('_') or "subplot"

    def _export_subplot(self, plot_item, subplot_ctx: dict):
        """Export only the clicked subplot while reusing full export options."""
        name_hint = subplot_ctx.get("title") or subplot_ctx.get("sample") or "subplot"
        token = self._sanitize_filename_token(name_hint)
        default_name = f"correlation_{token}" if token else "correlation_subplot"
        download_pyqtgraph_figure(
            self.plot_widget,
            self,
            default_name,
            export_item=plot_item,
        )

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
            _itk_log.exception("Handled exception in _click_to_data_coords")
            return 0.0, 0.0

    def _current_xy_arrays(self):
        """Return (x_array, y_array) pooled across samples in the plot's
        rendered coordinate space (i.e. the same values the scatter points use).
        Returns (None, None) if unavailable."""
        cfg = self.node.config
        try:
            plot_data = self.node.extract_plot_data()
        except Exception:
            _itk_log.exception("Handled exception in _current_xy_arrays")
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
        # Annotation actions were intentionally removed in Correlation Phase 1.
        return []

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
        """Remove any existing per-plot color bars before a redraw."""
        for cb in self.active_color_bars:
            try:
                cb.remove()
            except Exception:
                _itk_log.exception("Handled exception in _cleanup_color_bars")
        self.active_color_bars.clear()

    def _suppress_native_plot_menus(self):
        """Disable native PyQtGraph right-click menus for Correlation plot items."""
        for item in self.plot_widget.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    item.setMenuEnabled(False)
                except Exception:
                    _itk_log.exception("Handled exception in _suppress_native_plot_menus")
                vb = item.getViewBox()
                if vb is not None:
                    try:
                        vb.setMenuEnabled(False)
                    except Exception:
                        _itk_log.exception("Handled exception in _suppress_native_plot_menus")

    def _refresh(self):
        """Redraw Correlation plots from current config without changing math semantics."""
        try:
            self._cleanup_color_bars()
            self._subplot_context_by_plotitem = {}

            self._plot_container_layout.removeWidget(self.plot_widget)
            self.plot_widget.deleteLater()
            self.plot_widget = CorrelationGraphicsLayoutWidget()
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
                self._current_display_mode = self.normalize_display_mode(
                    cfg.get('display_mode', self.DISPLAY_MODE_OVERLAID)
                )
                cfg['display_mode'] = self._current_display_mode

                if self._is_multi():
                    dm = self._current_display_mode
                    if dm == self.DISPLAY_MODE_SUBPLOTS:
                        self._draw_subplots(plot_data, cfg)
                        primary_plot = self.plot_widget.getItem(0, 0)
                    elif dm == self.DISPLAY_MODE_SIDE:
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
            self._suppress_native_plot_menus()

        except Exception as e:
            _itk_log.exception("Handled exception in _refresh")
            _itk_log.error(f"Error refreshing correlation display: {e}")
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

    def _plot_scatter(
        self, pi, x, y, c, cfg, color,
        correlation_label: str | None = None,
        correlation_index: int = 0,
        correlation_count: int = 1,
    ):
        """Add scatter + overlays to a PlotItem using already-prepared sample data.

        Trendline and correlation text visibility are owned by quick-toggle config
        keys. In overlaid multi-sample mode, optional ``correlation_label`` and
        index parameters place one visible r label per sample with capped lines
        to avoid dense label clutter.
        Args:
            pi (Any): The pi.
            x (Any): Input array or value.
            y (Any): Input array or value.
            c (Any): The c.
            cfg (Any): The cfg.
            color (Any): Colour value.
            correlation_label (str | None): Optional series label prefix for r
                text (e.g. sample display name).
            correlation_index (int): Series index used for r label vertical
                offset in overlaid plots.
            correlation_count (int): Number of series in the overlaid panel.
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
                    _itk_log.exception("Handled exception in _plot_scatter")
                    _itk_log.error(f'[SD envelope] {e}')

        if cfg.get('show_correlation', True) and len(x) > 1:
            if correlation_label:
                try:
                    r = float(np.corrcoef(x, y)[0, 1])
                    if np.isfinite(r):
                        fc = get_font_config(cfg)
                        vr = pi.getViewBox().state['viewRange']
                        x_pos = vr[0][0] + 0.05 * (vr[0][1] - vr[0][0])
                        base_y = vr[1][0] + 0.95 * (vr[1][1] - vr[1][0])
                        step = 0.055 * (vr[1][1] - vr[1][0])
                        max_lines = 6
                        if correlation_index < max_lines:
                            y_pos = base_y - (correlation_index * step)
                            txt = pg.TextItem(
                                f"{correlation_label}: r = {r:.3f}",
                                anchor=(0, 1),
                                color=color if color else fc['color'],
                            )
                            pi.addItem(txt)
                            txt.setPos(x_pos, y_pos)
                        elif correlation_index == max_lines:
                            hidden_count = max(correlation_count - max_lines, 0)
                            if hidden_count > 0:
                                y_pos = base_y - (max_lines * step)
                                txt = pg.TextItem(
                                    f"+{hidden_count} more",
                                    anchor=(0, 1),
                                    color=fc['color'],
                                )
                                pi.addItem(txt)
                                txt.setPos(x_pos, y_pos)
                except Exception:
                    _itk_log.exception("Handled exception in _plot_scatter")
            else:
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
                _itk_log.exception("Handled exception in _plot_scatter")
                _itk_log.error(f'[ref line] {e}')

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
            xl = f"log({x_lbl})" if cfg.get('log_x') else x_lbl
            yl = f"log({y_lbl})" if cfg.get('log_y') else y_lbl
        else:
            xl, yl = build_axis_labels(cfg)
            lm = cfg.get('label_mode', 'Symbol')
            xl = format_label_text_tokens(xl, lm, Renderer.HTML)
            yl = format_label_text_tokens(yl, lm, Renderer.HTML)
        set_axis_labels(pi, xl, yl, cfg)

        pi.getAxis('bottom').setLogMode(bool(cfg.get('log_x', False)))
        pi.getAxis('left').setLogMode(bool(cfg.get('log_y', False)))

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
        """Draw one subplot per sample and register subplot-export context.

        Empty panels after filtering show a clear message so users can
        distinguish filtered-out samples from rendering failures.
        """
        items = self._ordered_plot_data_items(plot_data)
        names = [sn for sn, _ in items]
        cols = min(3, len(names))
        for i, (sn, sd) in enumerate(items):
            pi = self.plot_widget.addPlot(row=i // cols, col=i % cols)
            if sd and 'element_data' in sd:
                x, y, c = self._prepare_data(sd['element_data'], cfg)
                if len(x):
                    color = get_sample_color(sn, i, cfg)
                    self._plot_scatter(pi, x, y, c, cfg, color)
                else:
                    self._add_no_valid_data_message(pi)
                title = get_display_name(sn, cfg)
                pi.setTitle(title)
                self._apply_labels(pi, cfg)
                apply_font_to_pyqtgraph(pi, cfg)
                self._subplot_context_by_plotitem[pi] = {
                    "sample": sn,
                    "title": title,
                    "mode": self.DISPLAY_MODE_SUBPLOTS,
                }

    def _draw_side_by_side(self, plot_data, cfg):
        """Draw one panel per sample in one row and register export context.

        Panels with no valid paired data after filtering display an explicit
        message instead of remaining unexplained blank plots.
        """
        first_pi = None
        for i, (sn, sd) in enumerate(self._ordered_plot_data_items(plot_data)):
            pi = self.plot_widget.addPlot(row=0, col=i)
            if sd and 'element_data' in sd:
                x, y, c = self._prepare_data(sd['element_data'], cfg)
                if len(x):
                    color = get_sample_color(sn, i, cfg)
                    self._plot_scatter(pi, x, y, c, cfg, color)
                else:
                    self._add_no_valid_data_message(pi)
            title = get_display_name(sn, cfg)
            pi.setTitle(title)
            if first_pi is None:
                first_pi = pi
                self._apply_labels(pi, cfg)
            else:
                pi.setYLink(first_pi)
                pi.getAxis('left').setLabel('')
                pi.getAxis('left').setStyle(showValues=False)
                pi.getAxis('bottom').setLogMode(bool(cfg.get('log_x', False)))
                pi.getAxis('left').setLogMode(bool(cfg.get('log_y', False)))
                if not cfg.get('auto_x', True):
                    pi.setXRange(cfg.get('x_min', 0), cfg.get('x_max', 1000), padding=0)
            apply_font_to_pyqtgraph(pi, cfg)
            self._subplot_context_by_plotitem[pi] = {
                "sample": sn,
                "title": title,
                "mode": self.DISPLAY_MODE_SIDE,
            }

    def _draw_combined(self, pi, plot_data, cfg):
        """Draw all samples overlaid in one panel with capped per-sample r labels."""
        legend_items = []
        valid_series = []
        for i, (sn, sd) in enumerate(self._ordered_plot_data_items(plot_data)):
            if not (sd and 'element_data' in sd):
                continue
            x, y, c = self._prepare_data(sd['element_data'], cfg)
            if len(x) == 0:
                continue
            valid_series.append((i, sn, x, y, c))

        if not valid_series:
            self._add_no_valid_data_message(pi)
            self._apply_labels(pi, cfg)
            return

        for idx, (i, sn, x, y, c) in enumerate(valid_series):
            color = get_sample_color(sn, i, cfg)
            sample_label = get_display_name(sn, cfg)
            scatter = self._plot_scatter(
                pi, x, y, c, cfg, color,
                correlation_label=sample_label,
                correlation_index=idx,
                correlation_count=len(valid_series),
            )
            legend_items.append((scatter, sample_label))

        self._apply_labels(pi, cfg)
        if legend_items:
            leg = pi.addLegend()
            for item, name in legend_items:
                leg.addItem(item, name)

    def _add_no_valid_data_message(self, pi, text: str = "No valid paired data after filtering."):
        """Show a centered non-modal empty-data message in the given PlotItem."""
        ti = pg.TextItem(text, anchor=(0.5, 0.5), color='gray')
        pi.addItem(ti)
        try:
            vr = pi.getViewBox().state['viewRange']
            x_mid = vr[0][0] + 0.5 * (vr[0][1] - vr[0][0])
            y_mid = vr[1][0] + 0.5 * (vr[1][1] - vr[1][0])
            ti.setPos(x_mid, y_mid)
        except Exception:
            _itk_log.exception("Handled exception in _add_no_valid_data_message")
            ti.setPos(0.5, 0.5)


class CorrelationGraphicsLayoutWidget(EnhancedGraphicsLayoutWidget):
    """Correlation-local GraphicsLayout widget with double-click editor suppression.

    Correlation scatter points use per-spot brush/pen styling. The generic
    double-click editor changes item-level style and can produce misleading
    legend-only updates. This local override disables those editors for
    Correlation without affecting other result plot types.
    """

    def mouseDoubleClickEvent(self, event):
        """Consume double-click events to suppress incompatible style editors."""
        event.accept()


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
        'label_mode': 'Symbol',
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
