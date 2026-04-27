"""
Single vs Multiple Element Analysis Node – Pie charts & heatmaps.

Uses **Matplotlib** for publication-quality figures (pie/heatmap).
Sidebar replaced by **right-click context menu** + settings dialog.
Uses shared_plot_utils for fonts, colors, sample helpers, and download.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QColorDialog,
    QPushButton, QLineEdit, QFrame, QWidget, QMenu, QScrollArea,
    QDialogButtonBox, QMessageBox, QFileDialog, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd
from collections import defaultdict
import math
import re

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS,
    get_font_config, make_font_properties, apply_font_to_matplotlib,
    FontSettingsGroup, LegendGroup, ExportSettingsGroup, MplDraggableCanvas,
    get_sample_color, get_display_name,
    download_matplotlib_figure,
)
from widget.colors import default_colors, colorheatmap

# ── Constants ──────────────────────────────────────────────────────────

VIZ_TYPES = ['Pie Charts', 'Heatmaps']
SM_DISPLAY_MODES = ['Individual Subplots', 'Side by Side Subplots', 'Combined View']

DEFAULT_CONFIG = {
    'custom_title': 'Single vs Multiple Element Analysis',
    'visualization_type': 'Pie Charts',
    'display_mode': 'Individual Subplots',
    'use_particles_per_ml': False,
    'dilution_factor': 1.0,
    'single_threshold': 0.5,
    'multiple_threshold': 0.5,
    'show_percentages': True,
    'explode_slices': False,
    'label_color': '#000000',
    'single_pie_colors': {},
    'multiple_pie_colors': {},
    'use_log_scale': True,
    'show_values': True,
    'colormap': 'YlGn',
    'sample_colors': {},
    'sample_name_mappings': {},
    'font_family': 'Times New Roman',
    'font_size': 12,
    'font_bold': False,
    'font_italic': False,
    'font_color': '#000000',
    # ── Pie style ────────────────────────────
    'label_mode':        'Symbol',
    'donut':             False,
    'donut_hole_size':   0.4,
    'donut_center_text': '',
    'start_angle':       90,
    'shadow':            False,
    'edge_color':        '#FFFFFF',
    'edge_width':        1.5,
    'label_distance':    1.15,
    # ── Legend ──────────────────────────────
    'legend_show':       False,
    'legend_position':   'best',
    'legend_outside':    False,
    # ── Labels & connection lines ────────────
    'show_connection_lines':  True,
    'connection_line_color':  '#888888',
    'connection_line_style':  '-',
    'label_bbox':             True,
    'label_positions':        {},
    # ── Export / appearance ──────────────────
    'bg_color':             '#FFFFFF',
    'export_format':        'svg',
    'export_dpi':           300,
    'use_custom_figsize':   False,
    'figsize_w':            16.0,
    'figsize_h':            10.0,
}


# ── Helper class (logic only, no UI) ──────────────────────────────────

class SingleMultipleElementHelper:
    """Analysis helper for single vs multiple element particle classification."""

    @staticmethod
    def analyze_particles(particle_data, pct_single=0.5, pct_multiple=0.5):
        """
        Args:
            particle_data (Any): The particle data.
            pct_single (Any): The pct single.
            pct_multiple (Any): The pct multiple.
        Returns:
            dict: Result of the operation.
        """
        if not particle_data:
            return None
        combo_data = defaultdict(list)
        for i, p in enumerate(particle_data):
            elems = [e for e, c in p.get('elements', {}).items() if c > 0]
            if elems:
                combo_data[', '.join(sorted(elems))].append(i)

        combos = {}
        for key, idx in combo_data.items():
            combos[key] = {'count': len(idx), 'indices': idx, 'is_single': len(key.split(', ')) == 1}

        total = len(particle_data)
        single, multi = [], []
        for combo, det in sorted(combos.items(), key=lambda x: x[1]['count'], reverse=True):
            pct = det['count'] / total * 100
            if det['is_single']:
                if pct >= pct_single:
                    single.append((combo, det, pct))
            else:
                if pct >= pct_multiple:
                    multi.append((combo, det, pct))

        return {'single_combinations': single, 'multiple_combinations': multi,
                'total_particles': total, 'all_combinations': sorted(combos.items(), key=lambda x: x[1]['count'], reverse=True)}

    @staticmethod
    def format_clean(combo_str):
        """
        Args:
            combo_str (Any): The combo str.
        Returns:
            object: Result of the operation.
        """
        return ', '.join(re.sub(r'^\d+', '', e.strip()) for e in combo_str.split(','))

    @staticmethod
    def calc_per_ml(count, parent_window, dilution=1.0, sample_info=None):
        """
        Args:
            count (Any): The count.
            parent_window (Any): The parent window.
            dilution (Any): The dilution.
            sample_info (Any): The sample info.
        Returns:
            object: Result of the operation.
        """
        if not parent_window:
            return count
        try:
            tr = getattr(parent_window, 'average_transport_rate', None)
            if sample_info and sample_info.get('is_summed', False):
                total_time = 0
                for sn in sample_info.get('original_samples', []):
                    if hasattr(parent_window, 'sample_time_data'):
                        std = parent_window.sample_time_data.get(sn)
                        if std and len(std) > 0:
                            total_time += std[-1] - std[0]
                    elif hasattr(parent_window, 'time_array'):
                        ta = parent_window.time_array
                        if ta and len(ta) > 0:
                            total_time += ta[-1] - ta[0]
            else:
                ta = getattr(parent_window, 'time_array', None)
                total_time = (ta[-1] - ta[0]) if ta is not None and len(ta) > 0 else 0

            if tr and tr > 0 and total_time > 0:
                vol = (tr * total_time) / 1000
                return (count / vol * dilution) if vol > 0 else count
            return count
        except Exception:
            return count

    @staticmethod
    def pie_data(results, combo_type, custom_colors=None, per_ml=False,
                 parent_window=None, dilution=1.0, sample_info=None):
        """
        Args:
            results (Any): The results.
            combo_type (Any): The combo type.
            custom_colors (Any): The custom colors.
            per_ml (Any): The per ml.
            parent_window (Any): The parent window.
            dilution (Any): The dilution.
            sample_info (Any): The sample info.
        Returns:
            dict: Result of the operation.
        """
        combos = results['single_combinations'] if combo_type == 'single' else results['multiple_combinations']
        if not combos:
            return None
        palette = default_colors if combo_type == 'single' else list(reversed(default_colors))
        unit = "Particles/mL" if per_ml else "Particles"
        labels, values, colors, keys = [], [], [], []
        for i, (combo, det, pct) in enumerate(combos):
            val = SingleMultipleElementHelper.calc_per_ml(det['count'], parent_window, dilution, sample_info) if per_ml else det['count']
            clean = SingleMultipleElementHelper.format_clean(combo)
            labels.append(f"{clean}\n({val:.0f} {unit})")
            values.append(val)
            colors.append((custom_colors or {}).get(combo, palette[i % len(palette)]))
            keys.append(combo)
        return {'labels': labels, 'values': values, 'colors': colors, 'combinations': keys}

    @staticmethod
    def heatmap_data(results_dict, per_ml=False, parent_window=None, dilution=1.0):
        """
        Args:
            results_dict (Any): The results dict.
            per_ml (Any): The per ml.
            parent_window (Any): The parent window.
            dilution (Any): The dilution.
        Returns:
            dict: Result of the operation.
        """
        if not results_dict:
            return None
        all_single, all_multi = set(), set()
        for sr in results_dict.values():
            for c, _, _ in sr['single_combinations']:
                all_single.add(SingleMultipleElementHelper.format_clean(c))
            for c, _, _ in sr['multiple_combinations']:
                all_multi.add(SingleMultipleElementHelper.format_clean(c))

        names = list(results_dict.keys())
        s_part = pd.DataFrame(0.0, index=sorted(all_single), columns=names)
        s_pct = pd.DataFrame(0.0, index=sorted(all_single), columns=names)

        top_multi = sorted(all_multi, key=lambda x: sum(
            next((d['count'] for c, d, _ in sr['multiple_combinations']
                  if SingleMultipleElementHelper.format_clean(c) == x), 0)
            for sr in results_dict.values()), reverse=True)[:30]
        m_part = pd.DataFrame(0.0, index=top_multi, columns=names)
        m_pct = pd.DataFrame(0.0, index=top_multi, columns=names)

        for sn, sr in results_dict.items():
            si = {'is_summed': False}
            for combo, det, pct in sr['single_combinations']:
                clean = SingleMultipleElementHelper.format_clean(combo)
                if clean in s_part.index:
                    v = SingleMultipleElementHelper.calc_per_ml(det['count'], parent_window, dilution, si) if per_ml else det['count']
                    s_part.loc[clean, sn] = v
                    s_pct.loc[clean, sn] = pct
            for combo, det, pct in sr['multiple_combinations']:
                clean = SingleMultipleElementHelper.format_clean(combo)
                if clean in m_part.index:
                    v = SingleMultipleElementHelper.calc_per_ml(det['count'], parent_window, dilution, si) if per_ml else det['count']
                    m_part.loc[clean, sn] = v
                    m_pct.loc[clean, sn] = pct

        return {'single_particles': s_part, 'single_percentage': s_pct,
                'multiple_particles': m_part, 'multiple_percentage': m_pct}

    @staticmethod
    def statistics_table(analysis_data, is_multi=False, per_ml=False, parent_window=None, dilution=1.0):
        """
        Args:
            analysis_data (Any): The analysis data.
            is_multi (Any): The is multi.
            per_ml (Any): The per ml.
            parent_window (Any): The parent window.
            dilution (Any): The dilution.
        Returns:
            object: Result of the operation.
        """
        unit = 'Particles/mL' if per_ml else 'Particles'
        si = {'is_summed': False}
        calc = lambda c: SingleMultipleElementHelper.calc_per_ml(c, parent_window, dilution, si) if per_ml else c
        rows = []
        if is_multi:
            for sn, sr in analysis_data.items():
                t = sr['total_particles']
                sc = sum(d['count'] for _, d, _ in sr['single_combinations'])
                mc = sum(d['count'] for _, d, _ in sr['multiple_combinations'])
                sp = sc/t*100 if t else 0
                mp = mc/t*100 if t else 0
                rows.append([sn, 'SUMMARY', 'Total', f'{calc(t):.1f}', '100.0%', f'All {unit}'])
                rows.append([sn, 'SUMMARY', 'Single Total', f'{calc(sc):.1f}', f'{sp:.1f}%', f'sNPs {unit}'])
                rows.append([sn, 'SUMMARY', 'Multiple Total', f'{calc(mc):.1f}', f'{mp:.1f}%', f'mNPs {unit}'])
                for combo, det, pct in sr['single_combinations']:
                    rows.append([sn, 'SINGLE', SingleMultipleElementHelper.format_clean(combo),
                                 f'{calc(det["count"]):.1f}', f'{pct:.1f}%', f'sNP {unit}'])
                for combo, det, pct in sr['multiple_combinations']:
                    ne = len(combo.split(', '))
                    rows.append([sn, 'MULTIPLE', SingleMultipleElementHelper.format_clean(combo),
                                 f'{calc(det["count"]):.1f}', f'{pct:.1f}%', f'mNP ({ne} elem) {unit}'])
            return pd.DataFrame(rows, columns=['Sample', 'Type', 'Combination', 'Count', '%', 'Description'])
        else:
            t = analysis_data['total_particles']
            sc = sum(d['count'] for _, d, _ in analysis_data['single_combinations'])
            mc = sum(d['count'] for _, d, _ in analysis_data['multiple_combinations'])
            sp = sc/t*100 if t else 0
            mp = mc/t*100 if t else 0
            rows.append(['SUMMARY', 'Total', f'{calc(t):.1f}', '100.0%', f'All {unit}'])
            rows.append(['SUMMARY', 'Single Total', f'{calc(sc):.1f}', f'{sp:.1f}%', f'sNPs {unit}'])
            rows.append(['SUMMARY', 'Multiple Total', f'{calc(mc):.1f}', f'{mp:.1f}%', f'mNPs {unit}'])
            for combo, det, pct in analysis_data['single_combinations']:
                rows.append(['SINGLE', SingleMultipleElementHelper.format_clean(combo),
                             f'{calc(det["count"]):.1f}', f'{pct:.1f}%', f'sNP {unit}'])
            for combo, det, pct in analysis_data['multiple_combinations']:
                ne = len(combo.split(', '))
                rows.append(['MULTIPLE', SingleMultipleElementHelper.format_clean(combo),
                             f'{calc(det["count"]):.1f}', f'{pct:.1f}%', f'mNP ({ne} elem) {unit}'])
            return pd.DataFrame(rows, columns=['Type', 'Combination', 'Count', '%', 'Description'])


# ── Small colour-swatch button ─────────────────────────────────────────

class _ColorBtn(QPushButton):
    """Compact colour-picker button."""
    def __init__(self, color: str = '#FFFFFF', parent=None):
        """
        Args:
            color (str): Colour value.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setFixedSize(34, 22)
        self._color = color
        self._apply()

    def _apply(self):
        self.setStyleSheet(
            f'background-color:{self._color};border:1px solid #666;border-radius:2px;')

    def color(self) -> str:
        """
        Returns:
            str: Result of the operation.
        """
        return self._color

    def set_color(self, c: str):
        """
        Args:
            c (str): The c.
        """
        self._color = c; self._apply()

    def mousePressEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        if event.button() == Qt.LeftButton:
            picked = QColorDialog.getColor(QColor(self._color), self)
            if picked.isValid():
                self.set_color(picked.name())
        super().mousePressEvent(event)


class PieStyleGroup:
    """Pie / donut style settings reusable group for Single/Multiple dialog."""

    _LINE_STYLES = ['-', '--', '-.', ':']
    _LINE_NAMES  = ['Solid', 'Dashed', 'Dash-dot', 'Dotted']

    def __init__(self, cfg: dict):
        """
        Args:
            cfg (dict): The cfg.
        """
        self._cfg = cfg

    def build(self) -> QGroupBox:
        """
        Returns:
            QGroupBox: Result of the operation.
        """
        cfg = self._cfg
        g = QGroupBox("Pie / Donut Style")
        f = QFormLayout(g)

        self._label_mode = QComboBox()
        self._label_mode.addItems(['Symbol', 'Mass + Symbol'])
        self._label_mode.setCurrentText(cfg.get('label_mode', 'Symbol'))
        f.addRow("Label Mode:", self._label_mode)

        self._donut = QCheckBox("Donut Mode")
        self._donut.setChecked(cfg.get('donut', False))
        f.addRow("", self._donut)

        self._hole = QDoubleSpinBox()
        self._hole.setRange(0.10, 0.85); self._hole.setSingleStep(0.05)
        self._hole.setValue(cfg.get('donut_hole_size', 0.4))
        f.addRow("Hole Size:", self._hole)

        self._center_text = QLineEdit(cfg.get('donut_center_text', ''))
        self._center_text.setPlaceholderText("e.g.  n = 250")
        f.addRow("Centre Label:", self._center_text)

        self._start = QSpinBox()
        self._start.setRange(0, 360); self._start.setSuffix("°")
        self._start.setValue(cfg.get('start_angle', 90))
        f.addRow("Start Angle:", self._start)

        self._shadow = QCheckBox("Shadow")
        self._shadow.setChecked(cfg.get('shadow', False))
        f.addRow("", self._shadow)

        self._edge_btn = _ColorBtn(cfg.get('edge_color', '#FFFFFF'))
        f.addRow("Edge Colour:", self._edge_btn)

        self._edge_w = QDoubleSpinBox()
        self._edge_w.setRange(0.0, 5.0); self._edge_w.setSingleStep(0.5)
        self._edge_w.setValue(cfg.get('edge_width', 1.5))
        f.addRow("Edge Width:", self._edge_w)

        self._ldist = QDoubleSpinBox()
        self._ldist.setRange(0.50, 2.00); self._ldist.setSingleStep(0.05)
        self._ldist.setDecimals(2)
        self._ldist.setValue(cfg.get('label_distance', 1.15))
        f.addRow("Label Distance:", self._ldist)

        self._show_lines = QCheckBox("Show Connection Lines")
        self._show_lines.setChecked(cfg.get('show_connection_lines', True))
        f.addRow("", self._show_lines)

        self._line_style = QComboBox()
        self._line_style.addItems(self._LINE_NAMES)
        cur_ls = cfg.get('connection_line_style', '-')
        self._line_style.setCurrentIndex(
            self._LINE_STYLES.index(cur_ls) if cur_ls in self._LINE_STYLES else 0)
        f.addRow("Line Style:", self._line_style)

        self._line_color = _ColorBtn(cfg.get('connection_line_color', '#888888'))
        f.addRow("Line Colour:", self._line_color)

        self._bbox = QCheckBox("Label Background Box")
        self._bbox.setChecked(cfg.get('label_bbox', True))
        f.addRow("", self._bbox)

        return g

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        return {
            'label_mode':             self._label_mode.currentText(),
            'donut':                  self._donut.isChecked(),
            'donut_hole_size':        self._hole.value(),
            'donut_center_text':      self._center_text.text().strip(),
            'start_angle':            self._start.value(),
            'shadow':                 self._shadow.isChecked(),
            'edge_color':             self._edge_btn.color(),
            'edge_width':             self._edge_w.value(),
            'label_distance':         self._ldist.value(),
            'show_connection_lines':  self._show_lines.isChecked(),
            'connection_line_style':  self._LINE_STYLES[self._line_style.currentIndex()],
            'connection_line_color':  self._line_color.color(),
            'label_bbox':             self._bbox.isChecked(),
        }


# ── Settings Dialog ────────────────────────────────────────────────────

class SingleMultipleSettingsDialog(QDialog):

    def __init__(self, cfg, input_data, analysis_data, parent=None):
        """
        Args:
            cfg (Any): The cfg.
            input_data (Any): The input data.
            analysis_data (Any): The analysis data.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("Single vs Multiple Element Settings")
        self.setMinimumWidth(500)
        self._cfg = dict(cfg)
        self._input_data = input_data
        self._analysis = analysis_data
        self._multi = (input_data and input_data.get('type') == 'multiple_sample_data')
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); lay = QVBoxLayout(inner)
        scroll.setWidget(inner); root.addWidget(scroll)

        g1 = QGroupBox("Visualization")
        f1 = QFormLayout(g1)
        self.viz_combo = QComboBox(); self.viz_combo.addItems(VIZ_TYPES)
        self.viz_combo.setCurrentText(self._cfg.get('visualization_type', 'Pie Charts'))
        f1.addRow("Type:", self.viz_combo)
        lay.addWidget(g1)

        g2 = QGroupBox("Units & Dilution")
        f2 = QFormLayout(g2)
        self.pml_cb = QCheckBox(); self.pml_cb.setChecked(self._cfg.get('use_particles_per_ml', False))
        f2.addRow("Use Particles/mL:", self.pml_cb)
        self.dil_spin = QDoubleSpinBox(); self.dil_spin.setRange(0.001, 100000)
        self.dil_spin.setDecimals(3); self.dil_spin.setValue(self._cfg.get('dilution_factor', 1.0))
        f2.addRow("Dilution Factor:", self.dil_spin)
        lay.addWidget(g2)

        if self._multi:
            gm = QGroupBox("Multiple Sample Display")
            fm = QFormLayout(gm)
            self.mode_combo = QComboBox(); self.mode_combo.addItems(SM_DISPLAY_MODES)
            self.mode_combo.setCurrentText(self._cfg.get('display_mode', SM_DISPLAY_MODES[0]))
            fm.addRow("Mode:", self.mode_combo)
            lay.addWidget(gm)

        g3 = QGroupBox("Thresholds")
        f3 = QFormLayout(g3)
        self.st_spin = QDoubleSpinBox(); self.st_spin.setRange(0, 10); self.st_spin.setDecimals(2)
        self.st_spin.setSuffix('%'); self.st_spin.setValue(self._cfg.get('single_threshold', 0.5))
        f3.addRow("Single Threshold:", self.st_spin)
        self.mt_spin = QDoubleSpinBox(); self.mt_spin.setRange(0, 10); self.mt_spin.setDecimals(2)
        self.mt_spin.setSuffix('%'); self.mt_spin.setValue(self._cfg.get('multiple_threshold', 0.5))
        f3.addRow("Multiple Threshold:", self.mt_spin)
        lay.addWidget(g3)

        g4 = QGroupBox("Pie Chart Settings")
        f4 = QFormLayout(g4)
        self.pct_cb = QCheckBox(); self.pct_cb.setChecked(self._cfg.get('show_percentages', True))
        f4.addRow("Show %:", self.pct_cb)
        self.explode_cb = QCheckBox(); self.explode_cb.setChecked(self._cfg.get('explode_slices', False))
        f4.addRow("Explode Slices:", self.explode_cb)
        self.lbl_btn = QPushButton(); self._lbl_color = QColor(self._cfg.get('label_color', '#000000'))
        self.lbl_btn.setStyleSheet(f"background-color:{self._lbl_color.name()}; min-height:25px;")
        self.lbl_btn.clicked.connect(self._pick_lbl_color)
        f4.addRow("Label Color:", self.lbl_btn)
        lay.addWidget(g4)

        g5 = QGroupBox("Heatmap Settings")
        f5 = QFormLayout(g5)
        self.log_cb = QCheckBox(); self.log_cb.setChecked(self._cfg.get('use_log_scale', True))
        f5.addRow("Log Scale:", self.log_cb)
        self.val_cb = QCheckBox(); self.val_cb.setChecked(self._cfg.get('show_values', True))
        f5.addRow("Show % on Cells:", self.val_cb)
        self.cmap_combo = QComboBox(); self.cmap_combo.addItems(colorheatmap)
        self.cmap_combo.setCurrentText(self._cfg.get('colormap', 'YlGn'))
        f5.addRow("Colormap:", self.cmap_combo)
        lay.addWidget(g5)

        if self._multi:
            names = self._input_data.get('sample_names', [])
            if names:
                g6 = QGroupBox("Sample Colors & Names")
                v6 = QVBoxLayout(g6)
                self._sample_btns = {}; self._sample_edits = {}
                sc = dict(self._cfg.get('sample_colors', {}))
                nm = dict(self._cfg.get('sample_name_mappings', {}))
                for i, sn in enumerate(names):
                    h = QHBoxLayout()
                    ed = QLineEdit(nm.get(sn, sn)); ed.setFixedWidth(200)
                    h.addWidget(ed); self._sample_edits[sn] = ed
                    btn = QPushButton(); btn.setFixedSize(30, 20)
                    c = sc.get(sn, default_colors[i % len(default_colors)])
                    sc[sn] = c
                    btn.setStyleSheet(f"background-color: {c}; border:1px solid black;")
                    btn.clicked.connect(lambda _, s=sn, b=btn: self._pick_sc(s, b))
                    h.addWidget(btn); h.addStretch()
                    w = QWidget(); w.setLayout(h); v6.addWidget(w)
                    self._sample_btns[sn] = (btn, c)
                self._sc = sc; self._nm = nm
                lay.addWidget(g6)

        self._font_grp = FontSettingsGroup(self._cfg)
        lay.addWidget(self._font_grp.build())

        self._pie_style = PieStyleGroup(self._cfg)
        lay.addWidget(self._pie_style.build())

        self._legend_grp = LegendGroup(self._cfg)
        lay.addWidget(self._legend_grp.build())

        self._export_grp = ExportSettingsGroup(self._cfg)
        lay.addWidget(self._export_grp.build())

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _pick_lbl_color(self):
        c = QColorDialog.getColor(self._lbl_color, self)
        if c.isValid():
            self._lbl_color = c
            self.lbl_btn.setStyleSheet(f"background-color:{c.name()}; min-height:25px;")

    def _pick_sc(self, sn, btn):
        """
        Args:
            sn (Any): The sn.
            btn (Any): The btn.
        """
        c = QColorDialog.getColor(QColor(self._sc.get(sn, '#3B82F6')), self)
        if c.isValid():
            self._sc[sn] = c.name()
            btn.setStyleSheet(f"background-color:{c.name()}; border:1px solid black;")

    def collect(self):
        """
        Returns:
            object: Result of the operation.
        """
        d = {
            'visualization_type': self.viz_combo.currentText(),
            'use_particles_per_ml': self.pml_cb.isChecked(),
            'dilution_factor': self.dil_spin.value(),
            'single_threshold': self.st_spin.value(),
            'multiple_threshold': self.mt_spin.value(),
            'show_percentages': self.pct_cb.isChecked(),
            'explode_slices': self.explode_cb.isChecked(),
            'label_color': self._lbl_color.name(),
            'use_log_scale': self.log_cb.isChecked(),
            'show_values': self.val_cb.isChecked(),
            'colormap': self.cmap_combo.currentText(),
        }
        d.update(self._font_grp.collect())
        d.update(self._pie_style.collect())
        d.update(self._legend_grp.collect())
        d.update(self._export_grp.collect())
        if hasattr(self, 'mode_combo'):
            d['display_mode'] = self.mode_combo.currentText()
        if hasattr(self, '_sc'):
            d['sample_colors'] = dict(self._sc)
        if hasattr(self, '_sample_edits'):
            d['sample_name_mappings'] = {k: v.text() for k, v in self._sample_edits.items()}
        return d


# ── Display Dialog ─────────────────────────────────────────────────────

class SingleMultipleElementDisplayDialog(QDialog):
    """Main dialog with matplotlib figure and right-click context menu."""

    def __init__(self, node, parent_window=None):
        """
        Args:
            node (Any): Tree or graph node.
            parent_window (Any): The parent window.
        """
        super().__init__(parent_window)
        self.node = node
        self.parent_window = parent_window
        self.setWindowTitle("Single vs Multiple Element Analysis")
        self.setMinimumSize(1400, 900)
        self._anns: dict = {}
        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    @property
    def _multi(self):
        """
        Returns:
            object: Result of the operation.
        """
        return (self.node.input_data and self.node.input_data.get('type') == 'multiple_sample_data')

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        self._stats = QLabel("")
        self._stats.setStyleSheet("color:#6B7280; font-size:11px; padding:2px 6px;")
        lay.addWidget(self._stats)

        self.tabs = QTabWidget()

        # ── Viz tab ───────────────────────────────────────────────────
        viz_widget = QWidget()
        viz_lay = QVBoxLayout(viz_widget)
        viz_lay.setContentsMargins(0, 0, 0, 0)
        viz_lay.setSpacing(2)

        self.fig = Figure(figsize=(16, 10), dpi=100, tight_layout=True)
        self.canvas = MplDraggableCanvas(self.fig)
        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._ctx_menu)
        try:
            self.canvas.mpl_connect('button_release_event', self._persist_positions)
        except AttributeError:
            pass
        viz_lay.addWidget(self.canvas, stretch=1)

        tb = QHBoxLayout()
        tb.setContentsMargins(0, 2, 0, 0)
        btn_s = QPushButton("⚙  Settings")
        btn_s.clicked.connect(self._open_settings)
        btn_r = QPushButton("↺  Reset Layout")
        btn_r.setToolTip("Reset all subplot positions to auto layout\n(or middle-click on the figure)")
        btn_r.clicked.connect(self._reset_layout)
        btn_e = QPushButton("⬆  Export…")
        btn_e.clicked.connect(self._export_figure)
        tb.addWidget(btn_s); tb.addWidget(btn_r)
        tb.addStretch(); tb.addWidget(btn_e)
        viz_lay.addLayout(tb)

        self.tabs.addTab(viz_widget, "Visualization")

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.table, "Statistics Table")

        lay.addWidget(self.tabs, stretch=1)


    def _ctx_menu(self, pos):
        """
        Args:
            pos (Any): Position point.
        """
        cfg = self.node.config
        menu = QMenu(self)

        vm = menu.addMenu("Visualization Type")
        for vt in VIZ_TYPES:
            a = vm.addAction(vt); a.setCheckable(True)
            a.setChecked(cfg.get('visualization_type') == vt)
            a.triggered.connect(lambda _, v=vt: self._set('visualization_type', v))

        tm = menu.addMenu("Quick Toggles")
        for key, label in [('show_percentages', 'Show Percentages'), ('explode_slices', 'Explode Slices'),
                           ('use_log_scale', 'Log Scale (Heatmap)'), ('show_values', 'Values on Cells'),
                           ('use_particles_per_ml', 'Particles/mL'),
                           ('donut',                'Donut Mode'),
                           ('shadow',               'Shadow'),
                           ('legend_show',          'Show Legend'),
                           ]:
            a = tm.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        lm = menu.addMenu("Label Mode")
        for mode in ['Symbol', 'Mass + Symbol']:
            a = lm.addAction(mode); a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set('label_mode', v))

        if self._multi:
            mm = menu.addMenu("Display Mode")
            for m in SM_DISPLAY_MODES:
                a = mm.addAction(m); a.setCheckable(True)
                a.setChecked(cfg.get('display_mode') == m)
                a.triggered.connect(lambda _, v=m: self._set('display_mode', v))

        menu.addSeparator()
        menu.addAction("↺  Reset Layout").triggered.connect(self._reset_layout)
        menu.addAction("Configure…").triggered.connect(self._open_settings)
        menu.addAction("Download Figure…").triggered.connect(self._export_figure)
        menu.addAction("Download Statistics Table…").triggered.connect(self._download_table)

        menu.exec(self.canvas.mapToGlobal(pos))

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
        ad = self.node.extract_analysis_data()
        dlg = SingleMultipleSettingsDialog(self.node.config, self.node.input_data, ad, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _reset_layout(self):
        self.node.config['label_positions'] = {}
        self._anns = {}
        self.canvas.reset_layout()

    def _export_figure(self):
        download_matplotlib_figure(self.fig, self, "single_multiple_analysis")

    def _download_table(self):
        ad = self.node.extract_analysis_data()
        if not ad:
            QMessageBox.warning(self, "Warning", "No data available"); return
        cfg = self.node.config
        df = SingleMultipleElementHelper.statistics_table(
            ad, self._multi, cfg.get('use_particles_per_ml'), self.parent_window, cfg.get('dilution_factor', 1.0))
        path, _ = QFileDialog.getSaveFileName(self, "Save Table", "statistics.csv", "CSV (*.csv);;All (*)")
        if path:
            try:
                df.to_csv(path, index=False)
                QMessageBox.information(self, "Success", f"Saved to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _persist_positions(self, _event):
        """Save current annotation positions into config so they survive redraws.
        Args:
            _event (Any): The  event.
        """
        for sp_key, anns in self._anns.items():
            bucket = (self.node.config
                      .setdefault('label_positions', {})
                      .setdefault(sp_key, {}))
            for combo_key, ann in anns.items():
                p = ann.get_position()
                bucket[combo_key] = (float(p[0]), float(p[1]))


    def _refresh(self):
        try:
            cfg = self.node.config

            if cfg.get('use_custom_figsize', False):
                self.fig.set_size_inches(cfg.get('figsize_w', 16.0),
                                         cfg.get('figsize_h', 10.0))

            self.fig.clear()
            bg = cfg.get('bg_color', '#FFFFFF')
            self.fig.patch.set_facecolor(bg)

            ad = self.node.extract_analysis_data()

            if not ad:
                ax = self.fig.add_subplot(111)
                ax.text(0.5, 0.5, 'No particle data available\nConnect to Sample Selector',
                        ha='center', va='center', transform=ax.transAxes, fontsize=12, color='gray')
                ax.set_xticks([]); ax.set_yticks([])
            else:
                vt = cfg.get('visualization_type', 'Pie Charts')
                if vt == 'Pie Charts':
                    self._draw_pies(ad, cfg)
                else:
                    self._draw_heatmaps(ad, cfg)
                self._update_stats(ad)
                self._update_table(ad)

            self.fig.tight_layout()
            self.canvas.draw()
            self.canvas.snapshot_positions()
        except Exception as e:
            print(f"Error updating SM display: {e}")
            import traceback; traceback.print_exc()


    def _draw_pies(self, ad, cfg):
        """
        Args:
            ad (Any): The ad.
            cfg (Any): The cfg.
        """
        fp = make_font_properties(cfg)
        fc = cfg.get('font_color', '#000000')
        lc = cfg.get('label_color', '#000000')
        pml = cfg.get('use_particles_per_ml', False)
        dil = cfg.get('dilution_factor', 1.0)
        s_colors = cfg.get('single_pie_colors', {})
        m_colors = cfg.get('multiple_pie_colors', {})

        self._anns = {}

        if self._multi:
            names = list(ad.keys())
            n = len(names)
            for i, sn in enumerate(names):
                sr = ad[sn]
                dn = get_display_name(sn, cfg)
                si = {'is_summed': False}

                ax1 = self.fig.add_subplot(n, 2, i*2 + 1)
                self._pie_one(ax1, sr, 'single', s_colors, pml, dil, si, cfg, fp, lc,
                              sp_key=f'{sn}_single')
                ax1.set_title(f'{dn} – Single', fontproperties=fp, color=fc)

                ax2 = self.fig.add_subplot(n, 2, i*2 + 2)
                self._pie_one(ax2, sr, 'multiple', m_colors, pml, dil, si, cfg, fp, lc,
                              sp_key=f'{sn}_multiple')
                ax2.set_title(f'{dn} – Multiple', fontproperties=fp, color=fc)
        else:
            ax1 = self.fig.add_subplot(1, 2, 1)
            self._pie_one(ax1, ad, 'single', s_colors, pml, dil, None, cfg, fp, lc,
                          sp_key='single')
            ax1.set_title('Single Element Particles', fontproperties=fp, color=fc)

            ax2 = self.fig.add_subplot(1, 2, 2)
            self._pie_one(ax2, ad, 'multiple', m_colors, pml, dil, None, cfg, fp, lc,
                          sp_key='multiple')
            ax2.set_title('Multiple Element Particles', fontproperties=fp, color=fc)

    def _pie_one(self, ax, results, ctype, custom_colors, pml, dil, si, cfg, fp, lc, sp_key=''):
        """
        Args:
            ax (Any): The ax.
            results (Any): The results.
            ctype (Any): The ctype.
            custom_colors (Any): The custom colors.
            pml (Any): The pml.
            dil (Any): The dil.
            si (Any): The si.
            cfg (Any): The cfg.
            fp (Any): The fp.
            lc (Any): The lc.
            sp_key (Any): The sp key.
        Returns:
            object: Result of the operation.
        """
        pd_data = SingleMultipleElementHelper.pie_data(
            results, ctype, custom_colors, pml, self.parent_window, dil, si)
        if not pd_data:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                    transform=ax.transAxes, color='gray')
            ax.axis('off')
            return

        raw_labels   = pd_data['labels']
        values       = pd_data['values']
        colors       = pd_data['colors']
        combo_keys   = pd_data['combinations']

        # ── Apply label mode (strip mass numbers for 'Symbol') ────────
        mode = cfg.get('label_mode', 'Symbol')
        def _fmt(lbl: str) -> str:
            """
            Args:
                lbl (str): The lbl.
            Returns:
                str: Result of the operation.
            """
            if mode == 'Symbol':
                lines = lbl.split('\n')
                lines[0] = ', '.join(
                    re.sub(r'^\d+', '', tok.strip()) for tok in lines[0].split(',')
                )
                return '\n'.join(lines)
            return lbl

        # ── Optionally append percentage line ────────────────────────
        total_val = sum(values) or 1.0
        def _build_text(lbl: str, val: float) -> str:
            """
            Args:
                lbl (str): The lbl.
                val (float): The val.
            Returns:
                str: Result of the operation.
            """
            text = _fmt(lbl)
            if cfg.get('show_percentages', True):
                text += f'\n{val / total_val * 100:.1f}%'
            return text

        texts = [_build_text(l, v) for l, v in zip(raw_labels, values)]

        # ── Pie / donut geometry ──────────────────────────────────────
        donut     = cfg.get('donut', False)
        hole      = cfg.get('donut_hole_size', 0.4)
        start_ang = cfg.get('start_angle', 90)
        shadow    = cfg.get('shadow', False)
        edge_c    = cfg.get('edge_color', '#FFFFFF')
        edge_w    = cfg.get('edge_width', 1.5)
        label_d   = cfg.get('label_distance', 1.15)

        wp = {'linewidth': edge_w, 'edgecolor': edge_c}
        if donut:
            wp['width'] = max(0.05, 1.0 - hole)

        exp_amt = 0.05 if cfg.get('explode_slices', False) else 0.0
        explode = tuple([exp_amt] * len(values))

        result  = ax.pie(
            values,
            colors=colors,
            startangle=start_ang,
            explode=explode,
            shadow=shadow,
            wedgeprops=wp,
            labels=None,
            autopct=None,
            counterclock=False,
        )
        wedges = result[0]

        # ── Draggable annotations with connection lines ───────────────
        show_lines = cfg.get('show_connection_lines', True)
        line_color = cfg.get('connection_line_color', '#888888')
        line_style = cfg.get('connection_line_style', '-')
        use_bbox   = cfg.get('label_bbox', True)
        saved      = cfg.get('label_positions', {}).get(sp_key, {})

        fc = cfg.get('font_color', '#000000')

        anns: dict = {}
        for wedge, text, combo_key in zip(wedges, texts, combo_keys):
            theta = np.radians((wedge.theta1 + wedge.theta2) / 2)

            tip_x = (1.0 + exp_amt) * np.cos(theta)
            tip_y = (1.0 + exp_amt) * np.sin(theta)

            if combo_key in saved:
                lx, ly = saved[combo_key]
            else:
                lx = label_d * (1.0 + exp_amt) * np.cos(theta)
                ly = label_d * (1.0 + exp_amt) * np.sin(theta)

            ann = ax.annotate(
                text,
                xy=(tip_x, tip_y),
                xytext=(lx, ly),
                ha='center', va='center',
                fontproperties=fp, color=fc,
                arrowprops=dict(
                    arrowstyle='-',
                    color=line_color,
                    lw=0.8,
                    linestyle=line_style,
                ) if show_lines else None,
                bbox=dict(
                    boxstyle='round,pad=0.25',
                    fc='white', alpha=0.75, ec='none',
                ) if use_bbox else None,
                zorder=10,
            )
            try:
                ann.draggable(True)
            except AttributeError:
                pass
            anns[combo_key] = ann

        if sp_key:
            self._anns[sp_key] = anns

        # ── Donut centre label ────────────────────────────────────────
        centre = cfg.get('donut_center_text', '')
        if donut and centre:
            ax.text(0, 0, centre, ha='center', va='center',
                    fontproperties=fp, color=fc, zorder=11)

        # ── Legend ───────────────────────────────────────────────────
        if cfg.get('legend_show', False):
            import matplotlib.patches as mpatches
            display_labels = [_fmt(l).split('\n')[0] for l in raw_labels]
            handles = [mpatches.Patch(facecolor=c, label=dl)
                       for c, dl in zip(colors, display_labels)]
            kw = dict(handles=handles, prop=fp, framealpha=0.8)
            if cfg.get('legend_outside', False):
                ax.legend(loc='upper left', bbox_to_anchor=(1.0, 1.0), **kw)
            else:
                ax.legend(loc=cfg.get('legend_position', 'best'), **kw)

        ax.set_aspect('equal')
        ax.axis('off')


    def _draw_heatmaps(self, ad, cfg):
        """
        Args:
            ad (Any): The ad.
            cfg (Any): The cfg.
        """
        if not self._multi:
            ax = self.fig.add_subplot(111)
            ax.text(0.5, 0.5, 'Heatmaps require multiple samples',
                    ha='center', va='center', transform=ax.transAxes, color='gray')
            ax.set_xticks([]); ax.set_yticks([])
            return

        fp = make_font_properties(cfg)
        fc = cfg.get('font_color', '#000000')
        pml = cfg.get('use_particles_per_ml', False)
        dil = cfg.get('dilution_factor', 1.0)
        hd = SingleMultipleElementHelper.heatmap_data(ad, pml, self.parent_window, dil)
        if not hd:
            return
        cmap_name = cfg.get('colormap', 'YlGn')
        cmap = plt.cm.get_cmap(cmap_name)
        unit = 'Particles/mL' if pml else 'Particles'
        log = cfg.get('use_log_scale', True)

        for idx, (title, df_p, df_pct) in enumerate([
            ('Single Element Distribution', hd['single_particles'], hd['single_percentage']),
            ('Multiple Element Distribution', hd['multiple_particles'], hd['multiple_percentage']),
        ]):
            ax = self.fig.add_subplot(1, 2, idx + 1)
            if df_p.empty:
                ax.set_title(title, fontproperties=fp, color=fc)
                continue
            plot_d = df_p.copy()
            if log:
                plot_d = plot_d.replace(0, np.nan)
                plot_d = np.log10(plot_d + 1)
            im = ax.imshow(plot_d.values, cmap=cmap_name, aspect='auto')
            ax.set_xticks(range(len(df_p.columns)))
            ax.set_xticklabels([get_display_name(n, cfg) for n in df_p.columns], rotation=0, ha='right')
            ax.set_yticks(range(len(df_p.index)))
            ax.set_yticklabels(df_p.index)

            if cfg.get('show_values', True):
                dmin = np.nanmin(plot_d.values)
                dmax = np.nanmax(plot_d.values)
                norm = plt.Normalize(vmin=dmin, vmax=dmax)
                for r in range(len(df_pct.index)):
                    for c in range(len(df_pct.columns)):
                        pct = df_pct.iloc[r, c]
                        if not np.isnan(pct) and pct > 0:
                            dv = plot_d.iloc[r, c]
                            if not np.isnan(dv):
                                rgba = cmap(norm(dv))
                                lum = 0.299*rgba[0] + 0.587*rgba[1] + 0.114*rgba[2]
                                tc = 'white' if lum < 0.5 else 'black'
                            else:
                                tc = 'black'
                            ax.text(c, r, f'{pct:.2f}%', ha='center', va='center',
                                    color=tc, fontweight='bold')

            cbar = self.fig.colorbar(im, ax=ax, shrink=0.8)
            cl = f'{unit}' if not log else f'Log({unit} + 1)'
            cbar.set_label(cl, fontproperties=fp, color=fc)
            ax.set_title(title, fontproperties=fp, color=fc)
            apply_font_to_matplotlib(ax, cfg)


    def _update_stats(self, ad):
        """
        Args:
            ad (Any): The ad.
        """
        cfg = self.node.config
        pml = cfg.get('use_particles_per_ml', False)
        dil = cfg.get('dilution_factor', 1.0)
        unit = "Particles/mL" if pml else "Particles"
        calc = lambda c: SingleMultipleElementHelper.calc_per_ml(c, self.parent_window, dil) if pml else c

        if self._multi:
            tp = sum(sr['total_particles'] for sr in ad.values())
            sc = sum(sum(d['count'] for _, d, _ in sr['single_combinations']) for sr in ad.values())
            mc = sum(sum(d['count'] for _, d, _ in sr['multiple_combinations']) for sr in ad.values())
        else:
            tp = ad['total_particles']
            sc = sum(d['count'] for _, d, _ in ad['single_combinations'])
            mc = sum(d['count'] for _, d, _ in ad['multiple_combinations'])

        self._stats.setText(
            f"Total: {calc(tp):.1f} {unit}  |  Single: {calc(sc):.1f}  |  Multiple: {calc(mc):.1f}")

    def _update_table(self, ad):
        """
        Args:
            ad (Any): The ad.
        """
        try:
            cfg = self.node.config
            df = SingleMultipleElementHelper.statistics_table(
                ad, self._multi, cfg.get('use_particles_per_ml'),
                self.parent_window, cfg.get('dilution_factor', 1.0))
            self.table.setRowCount(len(df))
            self.table.setColumnCount(len(df.columns))
            self.table.setHorizontalHeaderLabels(df.columns.tolist())
            for i, row in df.iterrows():
                for j, val in enumerate(row):
                    item = QTableWidgetItem(str(val))
                    if j == 0 and str(val) == 'SUMMARY':
                        item.setBackground(QColor('#E6F3FF'))
                    self.table.setItem(i, j, item)
            self.table.resizeColumnsToContents()
        except Exception as e:
            print(f"Table update error: {e}")


# ── Node ───────────────────────────────────────────────────────────────

class SingleMultipleElementPlotNode(QObject):
    position_changed = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        """
        Args:
            parent_window (Any): The parent window.
        """
        super().__init__()
        self.title = "Single/Multiple"
        self.node_type = "single_multiple_element_plot"
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
        dlg = SingleMultipleElementDisplayDialog(self, parent_window)
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

    def extract_analysis_data(self):
        """
        Returns:
            None
        """
        if not self.input_data:
            return None
        st = self.config.get('single_threshold', 0.5)
        mt = self.config.get('multiple_threshold', 0.5)
        itype = self.input_data.get('type')
        if itype == 'sample_data':
            return SingleMultipleElementHelper.analyze_particles(
                self.input_data.get('particle_data', []), st, mt)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(st, mt)
        return None

    def _extract_multi(self, st, mt):
        """
        Args:
            st (Any): The st.
            mt (Any): The mt.
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
            if plist:
                r = SingleMultipleElementHelper.analyze_particles(plist, st, mt)
                if r:
                    result[sn] = r
        return result if result else None