"""
Pie Chart & Element Composition Node.

Replaces the sidebar with a right-click context menu + modal settings dialog.
Uses shared_plot_utils for fonts, download, and unified color handling.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QColorDialog,
    QPushButton, QLineEdit, QFrame, QScrollArea, QWidget, QMenu,
    QDialogButtonBox, QMessageBox, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QPen, QFont
import pyqtgraph as pg
import numpy as np
import math
import pandas as pd

from results.shared_plot_utils import (
    DEFAULT_SAMPLE_COLORS,
    get_font_config, make_qfont, FontSettingsGroup, get_display_name,
    download_pyqtgraph_figure
)
from results.utils_sort import sort_element_dict_by_mass, sort_elements_by_mass

# ── Constants ──────────────────────────────────────────────────────────

PIE_CHART_TYPES = ['Element Distribution', 'Particle Count Distribution']
PIE_DATA_TYPES = [
    'Counts', 'Element Mass (fg)', 'Particle Mass (fg)',
    'Element Moles (fmol)', 'Particle Moles (fmol)'
]
PIE_DISPLAY_MODES = [
    'Individual Subplots', 'Side by Side Subplots',
    'Combined Distribution', 'Overlaid Comparison'
]

COMP_ANALYSIS_TYPES = [
    'Single vs Multiple Elements', 
    'Specific Element Combinations', 
    'Element Distribution by Data Type'
]

DEFAULT_PIE_COLORS = [
    '#FF6347', '#FFD700', '#FFA500', '#20B2AA', '#00BFFF',
    '#F0E68C', '#E0FFFF', '#AFEEEE', '#DDA0DD', '#FFE4E1',
    '#FAEBD7', '#D3D3D3', '#90EE90', '#FFB6C1', '#FFA07A'
]

DEFAULT_COMBO_COLORS = [
    '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
    '#FF6B35', '#FFD700', '#20B2AA', '#FF69B4', '#32CD32',
    '#FF4500', '#9370DB', '#00CED1', '#FF1493', '#00FF7F'
]

# ── Helpers ────────────────────────────────────────────────────────────

def _is_multi(input_data):
    return (input_data and input_data.get('type') == 'multiple_sample_data')

def _draw_pie_chart(plot_item, labels, sizes, texts, colors, cfg):
    """Generic drawing function for pie chart wedges and labels."""
    if not sizes:
        return
    
    angles = [(size / 100.0) * 360 for size in sizes]
    start_angle = 90
    
    # Text rendering config
    fc = get_font_config(cfg)
    text_font = make_qfont(cfg)
    font_color = fc['color']
    
    smart_labels = cfg.get('smart_labels', True)
    show_lines = cfg.get('show_connection_lines', True)
    
    for i, (label, angle, size, color, display_text) in enumerate(zip(labels, angles, sizes, colors, texts)):
        end_angle = start_angle + angle
        start_rad = math.radians(start_angle)
        end_rad = math.radians(end_angle)
        
        radius = 1.0
        segments = max(16, int(angle / 3))
        
        wedge_x, wedge_y = [0], [0]
        for j in range(segments + 1):
            t = j / segments if segments > 0 else 0
            current_angle = start_rad + t * (end_rad - start_rad)
            wedge_x.append(radius * math.cos(current_angle))
            wedge_y.append(radius * math.sin(current_angle))
        wedge_x.append(0)
        wedge_y.append(0)
        
        wedge_item = pg.PlotDataItem(
            wedge_x, wedge_y, 
            pen=pg.mkPen('white', width=2),
            brush=pg.mkBrush(color),
            fillLevel=0
        )
        plot_item.addItem(wedge_item)
        
        mid_angle_rad = math.radians(start_angle + angle / 2)
        
        if smart_labels and size > 10:
            label_radius = 0.6
            label_x = label_radius * math.cos(mid_angle_rad)
            label_y = label_radius * math.sin(mid_angle_rad)
            
            text_item = pg.TextItem(display_text, anchor=(0.5, 0.5), color=font_color)
            text_item.setFont(text_font)
            text_item.setPos(label_x, label_y)
            plot_item.addItem(text_item)
            
        else:
            inside_radius = 1.05
            outside_radius = 1.3
            
            inside_x = inside_radius * math.cos(mid_angle_rad)
            inside_y = inside_radius * math.sin(mid_angle_rad)
            outside_x = outside_radius * math.cos(mid_angle_rad)
            outside_y = outside_radius * math.sin(mid_angle_rad)
            
            if show_lines:
                line_data = pg.PlotDataItem([inside_x, outside_x], [inside_y, outside_y], 
                                           pen=pg.mkPen('gray', width=1))
                plot_item.addItem(line_data)
            
            anchor = (0, 0.5) if outside_x > 0 else (1, 0.5)
            text_item = pg.TextItem(display_text, anchor=anchor, color=font_color)
            text_item.setFont(text_font)
            text_item.setPos(outside_x, outside_y)
            plot_item.addItem(text_item)
        
        start_angle = end_angle

# ═══════════════════════════════════════════════════════════════════════
# PIE CHART (ELEMENT DISTRIBUTION)
# ═══════════════════════════════════════════════════════════════════════

class PieChartSettingsDialog(QDialog):
    def __init__(self, cfg, input_data, available_elements, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pie Chart Settings")
        self.setMinimumWidth(460)
        self._cfg = dict(cfg)
        self._input_data = input_data
        self._available_elements = available_elements
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        scroll.setWidget(inner)
        root.addWidget(scroll)

        # ── Data & Chart Type ──
        g1 = QGroupBox("Data & Chart Type")
        f1 = QFormLayout(g1)
        
        self.chart_type = QComboBox()
        self.chart_type.addItems(PIE_CHART_TYPES)
        self.chart_type.setCurrentText(self._cfg.get('chart_type', PIE_CHART_TYPES[0]))
        f1.addRow("Chart Type:", self.chart_type)
        
        self.data_type = QComboBox()
        self.data_type.addItems(PIE_DATA_TYPES)
        self.data_type.setCurrentText(self._cfg.get('data_type_display', PIE_DATA_TYPES[0]))
        f1.addRow("Data Type:", self.data_type)
        lay.addWidget(g1)

        # ── Display Mode ──
        if _is_multi(self._input_data):
            g2 = QGroupBox("Multiple Sample Display")
            f2 = QFormLayout(g2)
            self.display_mode = QComboBox()
            self.display_mode.addItems(PIE_DISPLAY_MODES)
            self.display_mode.setCurrentText(self._cfg.get('display_mode', PIE_DISPLAY_MODES[0]))
            f2.addRow("Mode:", self.display_mode)
            lay.addWidget(g2)

        # ── Labels & Options ──
        g3 = QGroupBox("Labels & Thresholds")
        f3 = QFormLayout(g3)
        
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.0, 50.0)
        self.threshold.setSuffix(" %")
        self.threshold.setValue(self._cfg.get('threshold', 1.0))
        f3.addRow("Threshold ('Others'):", self.threshold)
        
        self.filter_zeros = QCheckBox("Filter Zero Values")
        self.filter_zeros.setChecked(self._cfg.get('filter_zeros', True))
        f3.addRow("", self.filter_zeros)
        
        self.show_counts = QCheckBox("Show Particle Counts")
        self.show_counts.setChecked(self._cfg.get('show_counts', True))
        f3.addRow("", self.show_counts)
        
        self.show_pct = QCheckBox("Show Percentages")
        self.show_pct.setChecked(self._cfg.get('show_percentages', True))
        f3.addRow("", self.show_pct)

        self.smart_labels = QCheckBox("Smart Label Positioning")
        self.smart_labels.setChecked(self._cfg.get('smart_labels', True))
        f3.addRow("", self.smart_labels)
        
        self.show_lines = QCheckBox("Show Connection Lines")
        self.show_lines.setChecked(self._cfg.get('show_connection_lines', True))
        f3.addRow("", self.show_lines)
        lay.addWidget(g3)

        # ── Element Colors ──
        if self._available_elements:
            g4 = QGroupBox("Element Colors")
            v4 = QVBoxLayout(g4)
            self._elem_colors = dict(self._cfg.get('element_colors', {}))
            for i, el in enumerate(self._available_elements):
                h = QHBoxLayout()
                h.addWidget(QLabel(el))
                btn = QPushButton()
                btn.setFixedSize(30, 20)
                c = self._elem_colors.get(el, DEFAULT_PIE_COLORS[i % len(DEFAULT_PIE_COLORS)])
                self._elem_colors[el] = c
                btn.setStyleSheet(f"background-color: {c}; border:1px solid black;")
                btn.clicked.connect(lambda _, e=el, b=btn: self._pick_color(self._elem_colors, e, b))
                h.addWidget(btn)
                h.addStretch()
                w = QWidget(); w.setLayout(h); v4.addWidget(w)
            lay.addWidget(g4)
        else:
            self._elem_colors = dict(self._cfg.get('element_colors', {}))

        # ── Sample Names ──
        if _is_multi(self._input_data):
            names = self._input_data.get('sample_names', [])
            if names:
                g5 = QGroupBox("Sample Names")
                v5 = QVBoxLayout(g5)
                self._sample_edits = {}
                nm = dict(self._cfg.get('sample_name_mappings', {}))
                for sn in names:
                    h = QHBoxLayout()
                    h.addWidget(QLabel(sn))
                    ed = QLineEdit(nm.get(sn, sn))
                    h.addWidget(ed)
                    self._sample_edits[sn] = ed
                    w = QWidget(); w.setLayout(h); v5.addWidget(w)
                lay.addWidget(g5)

        # ── Font Settings ──
        self._font_grp = FontSettingsGroup(self._cfg)
        lay.addWidget(self._font_grp.build())

        # ── Buttons ──
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _pick_color(self, color_dict, key, btn):
        c = QColorDialog.getColor(QColor(color_dict.get(key, '#FFFFFF')), self)
        if c.isValid():
            color_dict[key] = c.name()
            btn.setStyleSheet(f"background-color: {c.name()}; border:1px solid black;")

    def collect(self):
        d = {
            'chart_type': self.chart_type.currentText(),
            'data_type_display': self.data_type.currentText(),
            'threshold': self.threshold.value(),
            'filter_zeros': self.filter_zeros.isChecked(),
            'show_counts': self.show_counts.isChecked(),
            'show_percentages': self.show_pct.isChecked(),
            'smart_labels': self.smart_labels.isChecked(),
            'show_connection_lines': self.show_lines.isChecked(),
            'element_colors': dict(self._elem_colors),
        }
        if hasattr(self, 'display_mode'):
            d['display_mode'] = self.display_mode.currentText()
        if hasattr(self, '_sample_edits'):
            d['sample_name_mappings'] = {k: v.text() for k, v in self._sample_edits.items()}
        d.update(self._font_grp.collect())
        return d


class PieChartDisplayDialog(QDialog):
    def __init__(self, node, parent_window=None):
        super().__init__(parent_window)
        self.node = node
        self.setWindowTitle("Element Distribution Pie Charts")
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

        self.pw = pg.GraphicsLayoutWidget()
        self.pw.setBackground('w')
        self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pw.customContextMenuRequested.connect(self._ctx_menu)
        lay.addWidget(self.pw)

    def _ctx_menu(self, pos):
        cfg = self.node.config
        menu = QMenu(self)

        cm = menu.addMenu("Chart Type")
        for ct in PIE_CHART_TYPES:
            a = cm.addAction(ct)
            a.setCheckable(True)
            a.setChecked(cfg.get('chart_type') == ct)
            a.triggered.connect(lambda _, v=ct: self._set('chart_type', v))
            
        dm = menu.addMenu("Data Type")
        for dt in PIE_DATA_TYPES:
            a = dm.addAction(dt)
            a.setCheckable(True)
            a.setChecked(cfg.get('data_type_display') == dt)
            a.triggered.connect(lambda _, v=dt: self._set('data_type_display', v))

        tm = menu.addMenu("Quick Toggles")
        for key, lbl in [('show_counts', 'Show Counts'), ('show_percentages', 'Show Percentages')]:
            a = tm.addAction(lbl)
            a.setCheckable(True)
            a.setChecked(cfg.get(key, True))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        if _is_multi(self.node.input_data):
            mm = menu.addMenu("Display Mode")
            for m in PIE_DISPLAY_MODES:
                a = mm.addAction(m)
                a.setCheckable(True)
                a.setChecked(cfg.get('display_mode') == m)
                a.triggered.connect(lambda _, v=m: self._set('display_mode', v))

        menu.addSeparator()
        menu.addAction("Configure…").triggered.connect(self._open_settings)
        menu.addAction("Download Figure…").triggered.connect(
            lambda: download_pyqtgraph_figure(self.pw, self, "pie_chart.png"))

        menu.exec(self.pw.mapToGlobal(pos))

    def _toggle(self, key):
        self.node.config[key] = not self.node.config.get(key, True)
        self._refresh()

    def _set(self, key, value):
        self.node.config[key] = value
        self._refresh()

    def _open_settings(self):
        elems = self._get_available_elements()
        dlg = PieChartSettingsDialog(self.node.config, self.node.input_data, elems, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _get_available_elements(self):
        pd_data = self.node.extract_plot_data()
        elems = set()
        if pd_data:
            if _is_multi(self.node.input_data):
                for sd in pd_data.values():
                    if 'element_data' in sd:
                        elems.update(sd['element_data'].columns)
            else:
                if 'element_data' in pd_data:
                    elems.update(pd_data['element_data'].columns)
        return sort_elements_by_mass(list(elems))

    def _refresh(self):
        try:
            self.pw.clear()
            plot_data = self.node.extract_plot_data()
            if not plot_data:
                pi = self.pw.addPlot()
                pi.addItem(pg.TextItem("No data available", anchor=(0.5, 0.5), color='gray'))
                pi.hideAxis('left'); pi.hideAxis('bottom')
                return

            cfg = self.node.config
            if _is_multi(self.node.input_data):
                self._draw_multi(plot_data, cfg)
            else:
                pi = self.pw.addPlot()
                data, counts = self._calc_single(plot_data, cfg)
                self._draw_pie(pi, data, counts, cfg, f"Element Distribution")
        except Exception as e:
            print(f"Error updating pie chart: {e}")
            import traceback; traceback.print_exc()

    def _calc_single(self, sample_data, cfg):
        ed = sample_data.get('element_data')
        if ed is None: return {}, {}
        
        filtered = ed[ed > 0] if cfg.get('filter_zeros', True) else ed
        chart_type = cfg.get('chart_type', PIE_CHART_TYPES[0])
        
        data_totals = {}
        particle_counts = {}
        
        for col in ed.columns:
            pc = (ed[col] > 0).sum()
            if pc > 0:
                particle_counts[col] = pc
                if chart_type == 'Particle Count Distribution':
                    data_totals[col] = pc
                else:
                    data_totals[col] = filtered[col].sum()
        return data_totals, particle_counts

    def _draw_pie(self, pi, data, orig_counts, cfg, title):
        if not data: return
        
        total = sum(data.values())
        if total == 0: return
        pcts = {k: (v/total)*100 for k, v in data.items()}
        
        threshold = cfg.get('threshold', 1.0)
        main_elems = {k: v for k, v in pcts.items() if v >= threshold}
        others = {k: v for k, v in pcts.items() if v < threshold}
        
        if others: main_elems['Others'] = sum(others.values())
        
        sorted_elems = sorted(main_elems.items(), key=lambda x: x[1], reverse=True)
        labels = [x[0] for x in sorted_elems]
        sizes = [x[1] for x in sorted_elems]
        
        colors = []
        texts = []
        ec = cfg.get('element_colors', {})
        
        for i, lbl in enumerate(labels):
            # Resolve color
            if lbl == 'Others': colors.append('#808080')
            elif lbl in ec: colors.append(ec[lbl])
            else: colors.append(DEFAULT_PIE_COLORS[i % len(DEFAULT_PIE_COLORS)])
            
            # Resolve text
            sz = sizes[i]
            if lbl == 'Others':
                count = sum(orig_counts.get(k, 0) for k in others.keys())
            else:
                count = orig_counts.get(lbl, 0)
                
            parts = [lbl]
            if cfg.get('show_counts', True): parts.append(f"({count:,})")
            if cfg.get('show_percentages', True): parts.append(f"{sz:.1f}%")
            texts.append('\n'.join(parts))

        _draw_pie_chart(pi, labels, sizes, texts, colors, cfg)
        
        pi.setTitle(title, **{'color': get_font_config(cfg)['color']})
        pi.hideAxis('left'); pi.hideAxis('bottom')
        pi.setAspectLocked(True)
        pi.setRange(xRange=[-1.5, 1.5], yRange=[-1.5, 1.5])

    def _draw_multi(self, plot_data, cfg):
        mode = cfg.get('display_mode', PIE_DISPLAY_MODES[0])
        names = list(plot_data.keys())
        
        if mode == 'Combined Distribution':
            pi = self.pw.addPlot()
            comb_data, comb_counts = {}, {}
            for sd in plot_data.values():
                d, c = self._calc_single(sd, cfg)
                for k, v in d.items(): comb_data[k] = comb_data.get(k, 0) + v
                for k, v in c.items(): comb_counts[k] = comb_counts.get(k, 0) + v
            self._draw_pie(pi, comb_data, comb_counts, cfg, "Combined")
            
        elif mode in ['Individual Subplots', 'Side by Side Subplots']:
            cols = min(3, len(names)) if mode == 'Individual Subplots' else len(names)
            for i, sn in enumerate(names):
                r, c = divmod(i, cols)
                pi = self.pw.addPlot(row=r, col=c)
                d, cnt = self._calc_single(plot_data[sn], cfg)
                self._draw_pie(pi, d, cnt, cfg, get_display_name(sn, cfg))
                
        elif mode == 'Overlaid Comparison':
            for i, sn in enumerate(names[:2]):
                pi = self.pw.addPlot(row=0, col=i)
                d, cnt = self._calc_single(plot_data[sn], cfg)
                self._draw_pie(pi, d, cnt, cfg, get_display_name(sn, cfg))

class PieChartPlotNode(QObject):
    position_changed = Signal(object)
    configuration_changed = Signal()
    
    def __init__(self, parent_window=None):
        super().__init__()
        self.title = "Element Distribution"
        self.node_type = "pie_chart_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        
        self.config = {
            'chart_type': 'Element Distribution',
            'data_type_display': 'Counts',
            'threshold': 1.0,
            'filter_zeros': True,
            'element_colors': {},
            'display_mode': 'Individual Subplots',
            'sample_name_mappings': {},
            'font_family': 'Times New Roman',
            'font_size': 18,
            'show_counts': True,
            'show_percentages': True,
            'smart_labels': True,
            'show_connection_lines': True
        }
        self.input_data = None
        
    def set_position(self, pos):
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)
            
    def configure(self, parent_window):
        dlg = PieChartDisplayDialog(self, parent_window)
        dlg.exec()
        return True
        
    def process_data(self, input_data):
        if not input_data: return
        self.input_data = input_data
        self.configuration_changed.emit()
    
    def extract_plot_data(self):
        if not self.input_data: return None
        dt = self.config.get('data_type_display', 'Counts')
        dk = {'Counts': 'elements', 'Element Mass (fg)': 'element_mass_fg',
              'Particle Mass (fg)': 'particle_mass_fg', 'Element Moles (fmol)': 'element_moles_fmol',
              'Particle Moles (fmol)': 'particle_moles_fmol'}.get(dt, 'elements')
              
        if self.input_data.get('type') == 'sample_data':
            return self._extract_single(dk)
        elif self.input_data.get('type') == 'multiple_sample_data':
            return self._extract_multi(dk)
        return None
        
    def _extract_single(self, data_key):
        particles = self.input_data.get('particle_data')
        if not particles: return None
        
        all_elems = set()
        for p in particles: all_elems.update(p.get(data_key, {}).keys())
        if not all_elems: return None
        all_elems = sorted(list(all_elems))
        
        mat = []
        for p in particles:
            row = []
            for e in all_elems:
                v = p.get(data_key, {}).get(e, 0)
                if data_key == 'elements': row.append(v if v > 0 else 0)
                else: row.append(v if (v > 0 and not np.isnan(v)) else 0)
            mat.append(row)
            
        return {'element_data': pd.DataFrame(mat, columns=all_elems)} if mat else None
        
    def _extract_multi(self, data_key):
        particles = self.input_data.get('particle_data', [])
        names = self.input_data.get('sample_names', [])
        if not particles: return None
        
        all_elems = set()
        for p in particles: all_elems.update(p.get(data_key, {}).keys())
        if not all_elems: return None
        all_elems = sorted(list(all_elems))
        
        sd = {n: [] for n in names}
        for p in particles:
            src = p.get('source_sample')
            if src in sd:
                row = []
                for e in all_elems:
                    v = p.get(data_key, {}).get(e, 0)
                    if data_key == 'elements': row.append(v if v > 0 else 0)
                    else: row.append(v if (v > 0 and not np.isnan(v)) else 0)
                sd[src].append(row)
                
        res = {}
        for sn, mat in sd.items():
            if mat: res[sn] = {'element_data': pd.DataFrame(mat, columns=all_elems)}
        return res if res else None


# ═══════════════════════════════════════════════════════════════════════
# ELEMENT COMPOSITION
# ═══════════════════════════════════════════════════════════════════════

class ElementCompositionSettingsDialog(QDialog):
    def __init__(self, cfg, input_data, available_combos, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Element Composition Settings")
        self.setMinimumWidth(500)
        self._cfg = dict(cfg)
        self._input_data = input_data
        self._available_combos = available_combos
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        scroll.setWidget(inner)
        root.addWidget(scroll)

        # ── Analysis & Data Type ──
        g1 = QGroupBox("Analysis & Data Type")
        f1 = QFormLayout(g1)
        self.analysis_type = QComboBox()
        self.analysis_type.addItems(COMP_ANALYSIS_TYPES)
        self.analysis_type.setCurrentText(self._cfg.get('analysis_type', COMP_ANALYSIS_TYPES[0]))
        f1.addRow("Analysis:", self.analysis_type)
        
        self.data_type = QComboBox()
        self.data_type.addItems(PIE_DATA_TYPES)
        self.data_type.setCurrentText(self._cfg.get('data_type_display', PIE_DATA_TYPES[0]))
        f1.addRow("Data Type:", self.data_type)
        lay.addWidget(g1)

        # ── Display Mode ──
        if _is_multi(self._input_data):
            g2 = QGroupBox("Multiple Sample Display")
            f2 = QFormLayout(g2)
            self.display_mode = QComboBox()
            self.display_mode.addItems(['Individual Subplots', 'Side by Side Subplots', 'Combined Analysis', 'Comparative View'])
            self.display_mode.setCurrentText(self._cfg.get('display_mode', 'Individual Subplots'))
            f2.addRow("Mode:", self.display_mode)
            lay.addWidget(g2)

        # ── Thresholds & Labels ──
        g3 = QGroupBox("Thresholds & Labels")
        f3 = QFormLayout(g3)
        self.p_thresh = QSpinBox()
        self.p_thresh.setRange(1, 10000)
        self.p_thresh.setValue(self._cfg.get('particle_threshold', 10))
        f3.addRow("Min Particles:", self.p_thresh)
        
        self.pct_thresh = QDoubleSpinBox()
        self.pct_thresh.setRange(0.0, 50.0)
        self.pct_thresh.setSuffix(" %")
        self.pct_thresh.setValue(self._cfg.get('percentage_threshold', 1.0))
        f3.addRow("Min Percentage:", self.pct_thresh)
        
        self.show_vals = QCheckBox("Show Data Values"); self.show_vals.setChecked(self._cfg.get('show_data_values', True))
        self.show_counts = QCheckBox("Show Counts"); self.show_counts.setChecked(self._cfg.get('show_counts', True))
        self.show_pct = QCheckBox("Show Percentages"); self.show_pct.setChecked(self._cfg.get('show_percentages', True))
        self.show_epct = QCheckBox("Show Element % in Combos"); self.show_epct.setChecked(self._cfg.get('show_element_percentages', False))
        
        f3.addRow("", self.show_vals)
        f3.addRow("", self.show_counts)
        f3.addRow("", self.show_pct)
        f3.addRow("", self.show_epct)
        lay.addWidget(g3)

        # ── Combination Colors ──
        if self._available_combos:
            g4 = QGroupBox("Combination Colors (Top 15)")
            v4 = QVBoxLayout(g4)
            self._combo_colors = dict(self._cfg.get('combination_colors', {}))
            for i, combo in enumerate(self._available_combos[:15]):
                h = QHBoxLayout()
                lbl = combo if len(combo) <= 30 else combo[:27] + "..."
                h.addWidget(QLabel(lbl))
                btn = QPushButton(); btn.setFixedSize(30, 20)
                c = self._combo_colors.get(combo, DEFAULT_COMBO_COLORS[i % len(DEFAULT_COMBO_COLORS)])
                self._combo_colors[combo] = c
                btn.setStyleSheet(f"background-color: {c}; border:1px solid black;")
                btn.clicked.connect(lambda _, k=combo, b=btn: self._pick_color(self._combo_colors, k, b))
                h.addWidget(btn); h.addStretch()
                w = QWidget(); w.setLayout(h); v4.addWidget(w)
            lay.addWidget(g4)
        else:
            self._combo_colors = dict(self._cfg.get('combination_colors', {}))

        # ── Font Settings ──
        self._font_grp = FontSettingsGroup(self._cfg)
        lay.addWidget(self._font_grp.build())

        # ── Buttons ──
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _pick_color(self, color_dict, key, btn):
        c = QColorDialog.getColor(QColor(color_dict.get(key, '#FFFFFF')), self)
        if c.isValid():
            color_dict[key] = c.name()
            btn.setStyleSheet(f"background-color: {c.name()}; border:1px solid black;")

    def collect(self):
        d = {
            'analysis_type': self.analysis_type.currentText(),
            'data_type_display': self.data_type.currentText(),
            'particle_threshold': self.p_thresh.value(),
            'percentage_threshold': self.pct_thresh.value(),
            'show_data_values': self.show_vals.isChecked(),
            'show_counts': self.show_counts.isChecked(),
            'show_percentages': self.show_pct.isChecked(),
            'show_element_percentages': self.show_epct.isChecked(),
            'combination_colors': dict(self._combo_colors),
        }
        if hasattr(self, 'display_mode'):
            d['display_mode'] = self.display_mode.currentText()
        d.update(self._font_grp.collect())
        return d


class ElementCompositionDisplayDialog(QDialog):
    def __init__(self, node, parent_window=None):
        super().__init__(parent_window)
        self.node = node
        self.setWindowTitle("Element Combination Analysis")
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

        self.pw = pg.GraphicsLayoutWidget()
        self.pw.setBackground('w')
        self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pw.customContextMenuRequested.connect(self._ctx_menu)
        lay.addWidget(self.pw)

    def _ctx_menu(self, pos):
        cfg = self.node.config
        menu = QMenu(self)

        am = menu.addMenu("Analysis Type")
        for ct in COMP_ANALYSIS_TYPES:
            a = am.addAction(ct)
            a.setCheckable(True)
            a.setChecked(cfg.get('analysis_type') == ct)
            a.triggered.connect(lambda _, v=ct: self._set('analysis_type', v))
            
        dm = menu.addMenu("Data Type")
        for dt in PIE_DATA_TYPES:
            a = dm.addAction(dt)
            a.setCheckable(True)
            a.setChecked(cfg.get('data_type_display') == dt)
            a.triggered.connect(lambda _, v=dt: self._set('data_type_display', v))

        tm = menu.addMenu("Quick Toggles")
        for key, lbl in [('show_data_values', 'Show Data Values'), ('show_counts', 'Show Counts'), ('show_percentages', 'Show Percentages')]:
            a = tm.addAction(lbl)
            a.setCheckable(True)
            a.setChecked(cfg.get(key, True))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        if _is_multi(self.node.input_data):
            mm = menu.addMenu("Display Mode")
            for m in ['Individual Subplots', 'Side by Side Subplots', 'Combined Analysis', 'Comparative View']:
                a = mm.addAction(m)
                a.setCheckable(True)
                a.setChecked(cfg.get('display_mode') == m)
                a.triggered.connect(lambda _, v=m: self._set('display_mode', v))

        menu.addSeparator()
        menu.addAction("Configure…").triggered.connect(self._open_settings)
        menu.addAction("Download Figure…").triggered.connect(
            lambda: download_pyqtgraph_figure(self.pw, self, "composition_plot.png"))

        menu.exec(self.pw.mapToGlobal(pos))

    def _toggle(self, key):
        self.node.config[key] = not self.node.config.get(key, True)
        self._refresh()

    def _set(self, key, value):
        self.node.config[key] = value
        self._refresh()

    def _get_actual_combos(self):
        plot_data = self.node.extract_plot_data()
        if not plot_data: return []
        all_c = {}
        if _is_multi(self.node.input_data):
            for sd in plot_data.values():
                for c, info in sd.items():
                    all_c[c] = all_c.get(c, 0) + info.get('particle_count', 0)
        else:
            for c, info in plot_data.items():
                all_c[c] = info.get('particle_count', 0)
        return [k for k, v in sorted(all_c.items(), key=lambda x: x[1], reverse=True)]

    def _open_settings(self):
        combos = self._get_actual_combos()
        dlg = ElementCompositionSettingsDialog(self.node.config, self.node.input_data, combos, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _refresh(self):
        try:
            self.pw.clear()
            plot_data = self.node.extract_plot_data()
            if not plot_data:
                pi = self.pw.addPlot()
                pi.addItem(pg.TextItem("No data available", anchor=(0.5, 0.5), color='gray'))
                pi.hideAxis('left'); pi.hideAxis('bottom')
                return

            cfg = self.node.config
            if _is_multi(self.node.input_data):
                self._draw_multi(plot_data, cfg)
            else:
                pi = self.pw.addPlot()
                data = self._calc_data(plot_data, cfg)
                self._draw_comp_pie(pi, data, cfg, "Element Combinations")
        except Exception as e:
            print(f"Error updating composition plot: {e}")
            import traceback; traceback.print_exc()

    def _calc_data(self, plot_data, cfg):
        at = cfg.get('analysis_type', COMP_ANALYSIS_TYPES[0])
        pt = cfg.get('particle_threshold', 10)
        
        filtered = {k: v for k, v in plot_data.items() if v.get('particle_count', 0) >= pt}
        
        if at == 'Single vs Multiple Elements':
            res = {'Single Elements': {'particle_count': 0, 'data_value': 0, 'elements': {}},
                   'Multiple Elements': {'particle_count': 0, 'data_value': 0, 'elements': {}}}
            for k, v in filtered.items():
                target = 'Single Elements' if len(k.split(',')) == 1 else 'Multiple Elements'
                res[target]['particle_count'] += v.get('particle_count', 0)
                res[target]['data_value'] += v.get('data_value', 0)
            return {k: v for k, v in res.items() if v['particle_count'] > 0}
        
        return filtered

    def _draw_comp_pie(self, pi, data, cfg, title):
        if not data: return
        dt = cfg.get('data_type_display', 'Counts')
        
        val_key = 'particle_count' if dt == 'Counts' else 'data_value'
        total = sum(v.get(val_key, 0) for v in data.values())
        if total == 0: return
        
        pcts = {k: (v.get(val_key, 0)/total)*100 for k, v in data.items()}
        thresh = cfg.get('percentage_threshold', 1.0)
        
        main_c = {k: v for k, v in pcts.items() if v >= thresh}
        others = {k: v for k, v in pcts.items() if v < thresh}
        
        if others: main_c['Others'] = sum(others.values())
        
        sorted_c = sorted(main_c.items(), key=lambda x: x[1], reverse=True)
        labels = [x[0] for x in sorted_c]
        sizes = [x[1] for x in sorted_c]
        
        colors = []
        texts = []
        cc = cfg.get('combination_colors', {})
        
        for i, lbl in enumerate(labels):
            # Resolve color
            if lbl == 'Others': colors.append('#808080')
            elif lbl in cc: colors.append(cc[lbl])
            else: colors.append(DEFAULT_COMBO_COLORS[i % len(DEFAULT_COMBO_COLORS)])
            
            # Resolve text
            if lbl == 'Others':
                pc = sum(data[k].get('particle_count', 0) for k in others.keys())
                dv = sum(data[k].get('data_value', 0) for k in others.keys())
                elems = {}
            else:
                pc = data[lbl].get('particle_count', 0)
                dv = data[lbl].get('data_value', 0)
                elems = data[lbl].get('elements', {})
                
            parts = [lbl]
            if cfg.get('show_counts', True): parts.append(f"({pc:,} particles)")
            if cfg.get('show_data_values', True) and dt != 'Counts':
                unit = 'fg' if 'Mass' in dt else 'fmol' if 'Moles' in dt else ''
                parts.append(f"[{dv:.2f} {unit}]".strip())
            if cfg.get('show_percentages', True): parts.append(f"{sizes[i]:.1f}%")
            if cfg.get('show_element_percentages', False) and elems and len(elems) > 1:
                etot = sum(elems.values())
                if etot > 0:
                    eparts = [f"{e}: {(v/etot)*100:.1f}%" for e, v in elems.items()]
                    parts.append(f"({', '.join(eparts)})")
                    
            texts.append('\n'.join(parts))

        _draw_pie_chart(pi, labels, sizes, texts, colors, cfg)
        
        pi.setTitle(title, **{'color': get_font_config(cfg)['color']})
        pi.hideAxis('left'); pi.hideAxis('bottom')
        pi.setAspectLocked(True)
        pi.setRange(xRange=[-1.5, 1.5], yRange=[-1.5, 1.5])

    def _draw_multi(self, plot_data, cfg):
        mode = cfg.get('display_mode', 'Individual Subplots')
        names = list(plot_data.keys())
        
        if mode == 'Combined Analysis':
            pi = self.pw.addPlot()
            comb = {}
            for sd in plot_data.values():
                for k, v in sd.items():
                    if k not in comb: comb[k] = {'particle_count':0, 'data_value':0, 'elements':{}}
                    comb[k]['particle_count'] += v.get('particle_count',0)
                    comb[k]['data_value'] += v.get('data_value',0)
            data = self._calc_data(comb, cfg)
            self._draw_comp_pie(pi, data, cfg, "Combined")
            
        elif mode in ['Individual Subplots', 'Side by Side Subplots']:
            cols = min(3, len(names)) if mode == 'Individual Subplots' else len(names)
            for i, sn in enumerate(names):
                r, c = divmod(i, cols)
                pi = self.pw.addPlot(row=r, col=c)
                data = self._calc_data(plot_data[sn], cfg)
                self._draw_comp_pie(pi, data, cfg, get_display_name(sn, cfg))
                
        elif mode == 'Comparative View':
            for i, sn in enumerate(names[:2]):
                pi = self.pw.addPlot(row=0, col=i)
                data = self._calc_data(plot_data[sn], cfg)
                self._draw_comp_pie(pi, data, cfg, get_display_name(sn, cfg))

class ElementCompositionPlotNode(QObject):
    position_changed = Signal(object)
    configuration_changed = Signal()
    
    def __init__(self, parent_window=None):
        super().__init__()
        self.title = "Element Composition"
        self.node_type = "element_composition_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        
        self.config = {
            'analysis_type': 'Single vs Multiple Elements',
            'data_type_display': 'Counts',
            'particle_threshold': 10,
            'percentage_threshold': 1.0,
            'filter_zeros': True,
            'show_data_values': True,
            'show_counts': True,
            'show_percentages': True,
            'show_element_percentages': False,
            'combination_colors': {},
            'display_mode': 'Individual Subplots',
            'font_family': 'Times New Roman',
            'font_size': 18,
            'smart_labels': True,
            'show_connection_lines': True
        }
        self.input_data = None
        
    def set_position(self, pos):
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)
            
    def configure(self, parent_window):
        dlg = ElementCompositionDisplayDialog(self, parent_window)
        dlg.exec()
        return True
        
    def process_data(self, input_data):
        if not input_data: return
        self.input_data = input_data
        self.configuration_changed.emit()
    
    def extract_plot_data(self):
        if not self.input_data: return None
        dt = self.config.get('data_type_display', 'Counts')
        dk = {'Counts': 'elements', 'Element Mass (fg)': 'element_mass_fg',
              'Particle Mass (fg)': 'particle_mass_fg', 'Element Moles (fmol)': 'element_moles_fmol',
              'Particle Moles (fmol)': 'particle_moles_fmol'}.get(dt, 'elements')
              
        if self.input_data.get('type') == 'sample_data':
            return self._extract_single_enhanced(dk)
        elif self.input_data.get('type') == 'multiple_sample_data':
            return self._extract_multi_enhanced(dk)
        return None
        
    def _extract_single_enhanced(self, data_key):
        particles = self.input_data.get('particle_data')
        if not particles: return None
        
        combos = {}
        for p in particles:
            elems = {}
            for e, v in p.get(data_key, {}).items():
                if data_key == 'elements' and v > 0: elems[e] = v
                elif v > 0 and not np.isnan(v): elems[e] = v
            
            if elems:
                c_name = ', '.join(sorted(elems.keys()))
                if c_name not in combos:
                    combos[c_name] = {'particle_count': 0, 'data_value': 0, 'elements': {}}
                combos[c_name]['particle_count'] += 1
                combos[c_name]['data_value'] += sum(elems.values())
                for e, v in elems.items():
                    combos[c_name]['elements'][e] = combos[c_name]['elements'].get(e, 0) + v
        return combos
        
    def _extract_multi_enhanced(self, data_key):
        particles = self.input_data.get('particle_data', [])
        names = self.input_data.get('sample_names', [])
        if not particles: return None
        
        sd = {n: {} for n in names}
        for p in particles:
            src = p.get('source_sample')
            if src in sd:
                elems = {}
                for e, v in p.get(data_key, {}).items():
                    if data_key == 'elements' and v > 0: elems[e] = v
                    elif v > 0 and not np.isnan(v): elems[e] = v
                
                if elems:
                    c_name = ', '.join(sorted(elems.keys()))
                    if c_name not in sd[src]:
                        sd[src][c_name] = {'particle_count': 0, 'data_value': 0, 'elements': {}}
                    sd[src][c_name]['particle_count'] += 1
                    sd[src][c_name]['data_value'] += sum(elems.values())
                    for e, v in elems.items():
                        sd[src][c_name]['elements'][e] = sd[src][c_name]['elements'].get(e, 0) + v
        return {k: v for k, v in sd.items() if v}