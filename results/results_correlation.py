
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QPushButton,
    QLineEdit, QFrame, QScrollArea, QWidget, QMenu, QWidgetAction,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QColorDialog
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
)


# ═══════════════════════════════════════════════
# Settings Dialog (opened from right-click menu)
# ═══════════════════════════════════════════════

class CorrelationSettingsDialog(QDialog):
    """Full settings dialog opened from the right-click → Configure… action."""

    def __init__(self, config: dict, available_elements: list,
                 is_multi: bool, sample_names: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Correlation Plot Settings")
        self.setMinimumWidth(460)
        self._config = dict(config)  # work on a copy
        self._elements = available_elements
        self._is_multi = is_multi
        self._sample_names = sample_names
        self._build_ui()

    # ── UI construction ──────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        # Multiple-sample display mode
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

        # Analysis mode
        g = QGroupBox("Analysis Mode")
        vl = QVBoxLayout(g)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(['Simple Element Correlation', 'Custom Mathematical Expressions'])
        self.mode_combo.setCurrentText(self._config.get('mode', 'Simple Element Correlation'))
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        vl.addWidget(self.mode_combo)
        layout.addWidget(g)

        # Simple panel
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

        # Custom panel
        self.custom_group = QGroupBox("Custom Equations")
        cl = QFormLayout(self.custom_group)
        self.x_eq = QLineEdit(self._config.get('x_equation', ''))
        self.x_eq.setPlaceholderText("e.g. Fe/Ti")
        cl.addRow("X equation:", self.x_eq)
        self.x_lbl = QLineEdit(self._config.get('x_label', 'X-axis'))
        cl.addRow("X label:", self.x_lbl)
        self.y_eq = QLineEdit(self._config.get('y_equation', ''))
        self.y_eq.setPlaceholderText("e.g. Ca + Mg")
        cl.addRow("Y equation:", self.y_eq)
        self.y_lbl = QLineEdit(self._config.get('y_label', 'Y-axis'))
        cl.addRow("Y label:", self.y_lbl)
        if self._elements:
            info = QLabel(f"Elements: {', '.join(self._elements)}")
            info.setWordWrap(True)
            info.setStyleSheet("color:#3B82F6; font-size:10px; padding:4px; "
                               "background:#DBEAFE; border-radius:4px;")
            cl.addRow(info)
        layout.addWidget(self.custom_group)

        # Data type
        g = QGroupBox("Data Type")
        vl = QVBoxLayout(g)
        self.data_type = QComboBox(); self.data_type.addItems(DATA_TYPE_OPTIONS)
        self.data_type.setCurrentText(self._config.get('data_type_display', 'Counts'))
        vl.addWidget(self.data_type)
        layout.addWidget(g)

        # Plot options
        g = QGroupBox("Plot Options")
        fl = QFormLayout(g)
        self.filter_zeros = QCheckBox(); self.filter_zeros.setChecked(self._config.get('filter_zeros', True))
        fl.addRow("Filter zeros:", self.filter_zeros)
        self.filter_sat = QCheckBox(); self.filter_sat.setChecked(self._config.get('filter_saturated', True))
        fl.addRow("Filter saturated:", self.filter_sat)
        self.sat_thresh = QSpinBox(); self.sat_thresh.setRange(1, 1_000_000)
        self.sat_thresh.setValue(self._config.get('saturation_threshold', 10000))
        fl.addRow("Saturation threshold:", self.sat_thresh)
        self.show_corr = QCheckBox(); self.show_corr.setChecked(self._config.get('show_correlation', True))
        fl.addRow("Show r:", self.show_corr)
        self.show_trend = QCheckBox(); self.show_trend.setChecked(self._config.get('show_trendline', True))
        fl.addRow("Trend line:", self.show_trend)
        self.log_x = QCheckBox(); self.log_x.setChecked(self._config.get('log_x', False))
        fl.addRow("Log X:", self.log_x)
        self.log_y = QCheckBox(); self.log_y.setChecked(self._config.get('log_y', False))
        fl.addRow("Log Y:", self.log_y)
        layout.addWidget(g)

        # Marker
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

        # Font
        self._font_group = FontSettingsGroup(self._config)
        layout.addWidget(self._font_group.build())

        # Sample colors (multi)
        if self._is_multi:
            g = QGroupBox("Sample Colors")
            sl = QVBoxLayout(g)
            self._sample_btns = {}
            colors = self._config.get('sample_colors', {})
            for i, sn in enumerate(self._sample_names):
                row = QHBoxLayout()
                name_edit = QLineEdit(get_display_name(sn, self._config))
                name_edit.setFixedWidth(180)
                row.addWidget(name_edit)
                btn = QPushButton()
                btn.setFixedSize(30, 20)
                c = colors.get(sn, DEFAULT_SAMPLE_COLORS[i % len(DEFAULT_SAMPLE_COLORS)])
                btn.setStyleSheet(f"background-color:{c}; border:1px solid black;")
                btn.clicked.connect(lambda _, s=sn, b=btn: self._pick_sample_color(s, b))
                row.addWidget(btn)
                row.addStretch()
                w = QWidget(); w.setLayout(row)
                sl.addWidget(w)
                self._sample_btns[sn] = (name_edit, btn, c)
            layout.addWidget(g)

        layout.addStretch()

        # Dialog buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

        self._on_mode_changed()

    def _on_mode_changed(self):
        simple = self.mode_combo.currentText() == 'Simple Element Correlation'
        self.simple_group.setVisible(simple)
        self.custom_group.setVisible(not simple)

    def _pick_sample_color(self, name, btn):
        c = QColorDialog.getColor(QColor(self._sample_btns[name][2]), self)
        if c.isValid():
            btn.setStyleSheet(f"background-color:{c.name()}; border:1px solid black;")
            ne, b, _ = self._sample_btns[name]
            self._sample_btns[name] = (ne, b, c.name())

    def collect(self) -> dict:
        """Return the updated config dict."""
        cfg = dict(self._config)
        cfg['mode'] = self.mode_combo.currentText()
        cfg['x_element'] = self.x_elem.currentText()
        cfg['y_element'] = self.y_elem.currentText()
        cfg['color_element'] = self.color_elem.currentText()
        cfg['x_equation'] = self.x_eq.text()
        cfg['y_equation'] = self.y_eq.text()
        cfg['x_label'] = self.x_lbl.text()
        cfg['y_label'] = self.y_lbl.text()
        cfg['data_type_display'] = self.data_type.currentText()
        cfg['filter_zeros'] = self.filter_zeros.isChecked()
        cfg['filter_saturated'] = self.filter_sat.isChecked()
        cfg['saturation_threshold'] = self.sat_thresh.value()
        cfg['show_correlation'] = self.show_corr.isChecked()
        cfg['show_trendline'] = self.show_trend.isChecked()
        cfg['log_x'] = self.log_x.isChecked()
        cfg['log_y'] = self.log_y.isChecked()
        cfg['marker_size'] = self.m_size.value()
        cfg['marker_alpha'] = self.m_alpha.value()
        cfg.update(self._font_group.collect())

        if self._is_multi:
            cfg['display_mode'] = self.display_mode.currentText()
            sc = {}; nm = {}
            for sn, (ne, btn, c) in self._sample_btns.items():
                sc[sn] = c
                if ne.text() != sn:
                    nm[sn] = ne.text()
            cfg['sample_colors'] = sc
            cfg['sample_name_mappings'] = nm
        return cfg


# ═══════════════════════════════════════════════
# Auto-Correlation Dialog
# ═══════════════════════════════════════════════

class AutoCorrelationDialog(QDialog):
    """Table of top correlations — double-click to jump to that pair."""

    pair_selected = Signal(str, str)  # x_element, y_element

    def __init__(self, top_pairs: list, parent=None):
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

            # Color code: green for strong positive, red for strong negative
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
        row = index.row()
        if 0 <= row < len(self._pairs):
            p = self._pairs[row]
            self.pair_selected.emit(p['x'], p['y'])
            self.accept()


# ═══════════════════════════════════════════════
# Display Dialog (figure-only with right-click)
# ═══════════════════════════════════════════════

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
        return (self.node.input_data and
                self.node.input_data.get('type') == 'multiple_sample_data')

    def _sample_names(self) -> list:
        if self._is_multi():
            return self.node.input_data.get('sample_names', [])
        return []

    def _available_elements(self) -> list:
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

        self.plot_widget = pg.GraphicsLayoutWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.plot_widget.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.plot_widget)

    # ── Context menu ────────────────────────

    def _show_context_menu(self, pos):
        cfg = self.node.config
        menu = QMenu(self)

        # Quick toggles
        toggle_menu = menu.addMenu("Quick Toggles")
        self._add_toggle(toggle_menu, "Log X-axis", 'log_x')
        self._add_toggle(toggle_menu, "Log Y-axis", 'log_y')
        self._add_toggle(toggle_menu, "Trend Line", 'show_trendline')
        self._add_toggle(toggle_menu, "Correlation r", 'show_correlation')
        self._add_toggle(toggle_menu, "Filter Zeros", 'filter_zeros')
        self._add_toggle(toggle_menu, "Filter Saturated", 'filter_saturated')

        # Data type submenu
        dt_menu = menu.addMenu("Data Type")
        current_dt = cfg.get('data_type_display', 'Counts')
        for dt in DATA_TYPE_OPTIONS:
            a = dt_menu.addAction(dt)
            a.setCheckable(True)
            a.setChecked(dt == current_dt)
            a.triggered.connect(lambda checked, d=dt: self._set_data_type(d))

        # Element quick-switch (simple mode)
        if cfg.get('mode') == 'Simple Element Correlation':
            elems = self._available_elements()
            if elems:
                xe_menu = menu.addMenu("X Element")
                for e in elems:
                    a = xe_menu.addAction(e)
                    a.setCheckable(True)
                    a.setChecked(e == cfg.get('x_element'))
                    a.triggered.connect(lambda _, el=e: self._set_elem('x_element', el))
                ye_menu = menu.addMenu("Y Element")
                for e in elems:
                    a = ye_menu.addAction(e)
                    a.setCheckable(True)
                    a.setChecked(e == cfg.get('y_element'))
                    a.triggered.connect(lambda _, el=e: self._set_elem('y_element', el))

        # Display mode (multi)
        if self._is_multi():
            dm_menu = menu.addMenu("Display Mode")
            modes = ['Overlaid (Different Colors)', 'Side by Side Subplots',
                     'Individual Subplots', 'Combined with Legend']
            cur = cfg.get('display_mode', modes[0])
            for m in modes:
                a = dm_menu.addAction(m)
                a.setCheckable(True)
                a.setChecked(m == cur)
                a.triggered.connect(lambda _, mode=m: self._set_display_mode(mode))

        menu.addSeparator()

        # Auto-detect correlations
        auto_action = menu.addAction("🔍 Auto-Detect Correlations…")
        auto_action.triggered.connect(self._auto_detect_correlations)

        menu.addSeparator()

        # Full settings
        settings_action = menu.addAction("⚙  Configure…")
        settings_action.triggered.connect(self._open_settings)

        # Download
        dl_action = menu.addAction("💾 Download Figure…")
        dl_action.triggered.connect(
            lambda: download_pyqtgraph_figure(self.plot_widget, self, "correlation_plot.png"))

        menu.exec(QCursor.pos())

    def _add_toggle(self, menu, label, key):
        a = menu.addAction(label)
        a.setCheckable(True)
        a.setChecked(self.node.config.get(key, False))
        a.triggered.connect(lambda checked, k=key: self._toggle(k, checked))

    def _toggle(self, key, value):
        self.node.config[key] = value
        self._refresh()

    def _set_data_type(self, dt):
        self.node.config['data_type_display'] = dt
        self._refresh()

    def _set_elem(self, key, elem):
        self.node.config[key] = elem
        self._refresh()

    def _set_display_mode(self, mode):
        self.node.config['display_mode'] = mode
        self._refresh()

    def _open_settings(self):
        dlg = CorrelationSettingsDialog(
            self.node.config, self._available_elements(),
            self._is_multi(), self._sample_names(), self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    # ── Auto-detect ─────────────────────────

    def _auto_detect_correlations(self):
        pd_data = self.node.extract_plot_data()
        if not pd_data:
            QMessageBox.warning(self, "No Data", "No data available for correlation analysis.")
            return

        # Build combined matrix
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

        # Apply saturation filter
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
            self._cleanup_color_bars()
            self.plot_widget.clear()

            plot_data = self.node.extract_plot_data()
            if not plot_data:
                pi = self.plot_widget.addPlot()
                ti = pg.TextItem(
                    "No data available\nRight-click for options",
                    anchor=(0.5, 0.5), color='gray')
                pi.addItem(ti); ti.setPos(0.5, 0.5)
                pi.hideAxis('left'); pi.hideAxis('bottom')
                return

            cfg = self.node.config

            if self._is_multi():
                dm = cfg.get('display_mode', 'Overlaid (Different Colors)')
                if dm == 'Individual Subplots':
                    self._draw_subplots(plot_data, cfg)
                elif dm == 'Side by Side Subplots':
                    self._draw_side_by_side(plot_data, cfg)
                else:
                    pi = self.plot_widget.addPlot()
                    self._draw_combined(pi, plot_data, cfg)
                    apply_font_to_pyqtgraph(pi, cfg)
            else:
                pi = self.plot_widget.addPlot()
                self._draw_single(pi, plot_data, cfg)
                apply_font_to_pyqtgraph(pi, cfg)

        except Exception as e:
            print(f"Error refreshing correlation display: {e}")
            import traceback; traceback.print_exc()

    # ── Drawing helpers ─────────────────────

    def _extract_xy_color(self, df, cfg):
        """Extract (x, y, color_or_None) arrays from a DataFrame and config."""
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
        """Filter + log-transform. Returns (x, y, color) ready for plotting."""
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

        return x, y, c

    def _plot_scatter(self, pi, x, y, c, cfg, color):
        """Add scatter + optional trend + r text to a PlotItem."""
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
        if cfg.get('show_correlation', True) and len(x) > 1:
            add_correlation_text(pi, x, y, cfg)

        return scatter

    def _apply_labels(self, pi, cfg):
        xl, yl = build_axis_labels(cfg)
        set_axis_labels(pi, xl, yl, cfg)
        
        if cfg.get('log_x'):
            pi.getAxis('bottom').setLogMode(True)
        if cfg.get('log_y'):
            pi.getAxis('left').setLogMode(True)

    # ── Single sample ───────────────────────

    def _draw_single(self, pi, plot_data, cfg):
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
        for i, (sn, sd) in enumerate(plot_data.items()):
            pi = self.plot_widget.addPlot(row=0, col=i)
            if sd and 'element_data' in sd:
                x, y, c = self._prepare_data(sd['element_data'], cfg)
                if len(x):
                    color = get_sample_color(sn, i, cfg)
                    self._plot_scatter(pi, x, y, c, cfg, color)
                pi.setTitle(get_display_name(sn, cfg))
                self._apply_labels(pi, cfg)
                apply_font_to_pyqtgraph(pi, cfg)

    def _draw_combined(self, pi, plot_data, cfg):
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


# ═══════════════════════════════════════════════
# Node (logic + data extraction)
# ═══════════════════════════════════════════════

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
        'saturation_threshold': 10000,
        'show_correlation': True, 'show_trendline': True,
        'log_x': False, 'log_y': False,
        'marker_size': 6, 'marker_alpha': 0.7,
        'single_sample_color': '#3B82F6',
        'display_mode': 'Overlaid (Different Colors)',
        'sample_colors': {}, 'sample_name_mappings': {},
        'font_family': 'Times New Roman', 'font_size': 18,
        'font_bold': False, 'font_italic': False, 'font_color': '#000000',
    }

    def __init__(self, parent_window=None):
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
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        dlg = CorrelationPlotDisplayDialog(self, parent_window)
        dlg.exec()
        return True

    def process_data(self, input_data):
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
        if not self.input_data:
            return []
        sel = self.input_data.get('selected_isotopes', [])
        return [iso['label'] for iso in sel]

    def extract_plot_data(self):
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
            # Group by source_sample
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