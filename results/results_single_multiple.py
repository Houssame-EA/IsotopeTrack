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

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS,
    get_font_config, make_font_properties, apply_font_to_matplotlib,
    FontSettingsGroup, LegendGroup, ExportSettingsGroup, MplDraggableCanvas,
    get_sample_color, get_display_name,
    download_matplotlib_figure, LABEL_MODES, format_combination_label, Renderer,
    pick_color_hex,
)
from widget.colors import default_colors, colorheatmap
import logging
_itk_log = logging.getLogger("IsotopeTrack.results.results_single_multiple")

# ── Constants ──────────────────────────────────────────────────────────

VIZ_TYPES = ['Pie Charts', 'Heatmaps']
SM_DISPLAY_MODES = ['Individual Subplots', 'Side by Side Subplots', 'Combined View']
DEGREE_SIGN = "\N{DEGREE SIGN}"

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
    def format_clean(combo_str, label_mode='Symbol', cfg=None):
        """
        Format a raw combination label for display using the selected isotope label mode.

        Args:
            combo_str (str): Raw combination key (for example ``"56Fe, 197Au"``).
            label_mode (str): Isotope label mode (``Symbol``, ``Mass + Symbol``,
                or ``Atomic Notation``).
            cfg (dict | None): Optional plot config used by the formatter for
                renderer/font-aware atomic notation. When omitted, formatting falls
                back safely without config-specific font tuning.

        Returns:
            str: Formatted display label.

        Preserved behavior:
            Raw combination keys remain unchanged in analysis data structures; this
            method only formats display text.
        """
        return format_combination_label(combo_str, label_mode, Renderer.MATHTEXT, cfg)

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
            _itk_log.exception("Handled exception in calc_per_ml")
            return count

    @staticmethod
    def pie_data(results, combo_type, custom_colors=None, per_ml=False,
                 parent_window=None, dilution=1.0, sample_info=None, label_mode='Symbol'):
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
        unit = "P/mL" if per_ml else "P"
        labels, values, colors, keys = [], [], [], []
        for i, (combo, det, pct) in enumerate(combos):
            val = SingleMultipleElementHelper.calc_per_ml(det['count'], parent_window, dilution, sample_info) if per_ml else det['count']
            clean = SingleMultipleElementHelper.format_clean(combo, label_mode)
            labels.append(f"{clean}\n({val:.0f} {unit})")
            values.append(val)
            colors.append((custom_colors or {}).get(combo, palette[i % len(palette)]))
            keys.append(combo)
        return {'labels': labels, 'values': values, 'colors': colors, 'combinations': keys}

    @staticmethod
    def heatmap_data(results_dict, per_ml=False, parent_window=None, dilution=1.0,
                     label_mode='Symbol', cfg=None):
        """
        Build heatmap matrices for single- and multiple-element combinations.

        Args:
            results_dict (dict): Per-sample analysis results.
            per_ml (bool): Whether to convert counts to particles/mL.
            parent_window (Any): Parent window with optional transport/time metadata.
            dilution (float): Dilution factor used with particles/mL conversion.
            label_mode (str): Isotope label mode used for display labels.
            cfg (dict | None): Optional plotting config passed to label formatting.

        Returns:
            dict | None: Heatmap dataframes for particle values and percentages.

        Preserved behavior:
            Single/multiple calculations and thresholds are unchanged; only label
            formatting wiring now accepts optional config safely.
        """
        if not results_dict:
            return None
        all_single, all_multi = set(), set()
        for sr in results_dict.values():
            for c, _, _ in sr['single_combinations']:
                all_single.add(SingleMultipleElementHelper.format_clean(c, label_mode, cfg))
            for c, _, _ in sr['multiple_combinations']:
                all_multi.add(SingleMultipleElementHelper.format_clean(c, label_mode, cfg))

        names = list(results_dict.keys())
        s_part = pd.DataFrame(0.0, index=sorted(all_single), columns=names)
        s_pct = pd.DataFrame(0.0, index=sorted(all_single), columns=names)

        top_multi = sorted(all_multi, key=lambda x: sum(
            next((d['count'] for c, d, _ in sr['multiple_combinations']
                  if SingleMultipleElementHelper.format_clean(c, label_mode, cfg) == x), 0)
            for sr in results_dict.values()), reverse=True)[:30]
        m_part = pd.DataFrame(0.0, index=top_multi, columns=names)
        m_pct = pd.DataFrame(0.0, index=top_multi, columns=names)

        for sn, sr in results_dict.items():
            si = {'is_summed': False}
            for combo, det, pct in sr['single_combinations']:
                clean = SingleMultipleElementHelper.format_clean(combo, label_mode, cfg)
                if clean in s_part.index:
                    v = SingleMultipleElementHelper.calc_per_ml(det['count'], parent_window, dilution, si) if per_ml else det['count']
                    s_part.loc[clean, sn] = v
                    s_pct.loc[clean, sn] = pct
            for combo, det, pct in sr['multiple_combinations']:
                clean = SingleMultipleElementHelper.format_clean(combo, label_mode, cfg)
                if clean in m_part.index:
                    v = SingleMultipleElementHelper.calc_per_ml(det['count'], parent_window, dilution, si) if per_ml else det['count']
                    m_part.loc[clean, sn] = v
                    m_pct.loc[clean, sn] = pct

        return {'single_particles': s_part, 'single_percentage': s_pct,
                'multiple_particles': m_part, 'multiple_percentage': m_pct}

    @staticmethod
    def statistics_table(analysis_data, is_multi=False, per_ml=False, parent_window=None, dilution=1.0, label_mode='Symbol'):
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
        unit = 'P/mL' if per_ml else 'P'
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
                    rows.append([sn, 'SINGLE', SingleMultipleElementHelper.format_clean(combo, label_mode),
                                 f'{calc(det["count"]):.1f}', f'{pct:.1f}%', f'sNP {unit}'])
                for combo, det, pct in sr['multiple_combinations']:
                    ne = len(combo.split(', '))
                    rows.append([sn, 'MULTIPLE', SingleMultipleElementHelper.format_clean(combo, label_mode),
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
                rows.append(['SINGLE', SingleMultipleElementHelper.format_clean(combo, label_mode),
                             f'{calc(det["count"]):.1f}', f'{pct:.1f}%', f'sNP {unit}'])
            for combo, det, pct in analysis_data['multiple_combinations']:
                ne = len(combo.split(', '))
                rows.append(['MULTIPLE', SingleMultipleElementHelper.format_clean(combo, label_mode),
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
        """Refresh the swatch preview without styling any parent dialog."""
        self.setStyleSheet(
            "QPushButton {"
            f"background-color:{self._color};border:1px solid #666;border-radius:2px;"
            "}")

    def color(self) -> str:
        """
        Returns:
            str: Result of the operation.
        """
        return self._color

    def set_color(self, c: str):
        """Store one validated composition-preview color and refresh the swatch.

        Args:
            c (str): Hex color string selected for this preview swatch.
        """
        self._color = c
        self._apply()

    def mousePressEvent(self, event):
        """Open the shared safe color picker for this swatch on left click.

        Args:
            event (Any): Qt event object.
        """
        if event.button() == Qt.LeftButton:
            picked = pick_color_hex(self._color, owner=self,
                                    title="Select Color")
            if picked:
                self.set_color(picked)
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
        self._label_mode.addItems(LABEL_MODES)
        self._label_mode.setCurrentText(cfg.get('label_mode', 'Symbol'))
        f.addRow("Isotope Label:", self._label_mode)

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
        self._start.setRange(0, 360)
        self._start.setSuffix(DEGREE_SIGN)
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

    def __init__(self, cfg, input_data, analysis_data, parent=None, scope='all'):
        """
        Initialize Single/Multiple settings with optional scope-based filtering.

        Args:
            cfg (dict): Current plot configuration.
            input_data (dict): Current node input payload.
            analysis_data (dict): Precomputed analysis summary (read-only context).
            parent (Any): Parent widget.
            scope (str): Dialog scope. Use:
                - ``'format'`` for visual/formatting controls only.
                - ``'quantities'`` for scientific quantity/configuration controls only.
                - ``'all'`` for legacy combined behavior.

        Preserved behavior:
            The same config keys are read/written as before; only UI grouping and
            access routing are changed.
        """
        super().__init__(parent)
        if scope == 'format':
            self.setWindowTitle("Single/multiple plot format settings")
        elif scope == 'quantities':
            self.setWindowTitle("Single/multiple plot quantities configuration")
        else:
            self.setWindowTitle("Single vs Multiple Element Settings")
        self.setMinimumWidth(500)
        self._cfg = dict(cfg)
        self._input_data = input_data
        self._analysis = analysis_data
        self._multi = (input_data and input_data.get('type') == 'multiple_sample_data')
        self._scope = scope
        self.mode_combo = None
        self._build_ui()

    def _build_ui(self):
        """
        Build settings groups for the selected scope.

        ``quantities`` contains scientific/data controls (visualization type, units,
        dilution, thresholds, display mode, and quantity-side heatmap log scaling).
        ``format`` contains visual controls (pie/heatmap style, labels, fonts, legend,
        and export appearance settings.

        Preserved behavior:
            Sample color/name editing and pie label-color editing are intentionally
            not exposed for this plot type to avoid confusing controls that do not
            materially improve the Single/Multiple workflow.
        """
        root = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); lay = QVBoxLayout(inner)
        scroll.setWidget(inner); root.addWidget(scroll)

        if self._scope in ('all', 'quantities'):
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

            gq = QGroupBox("Heatmap Quantity Settings")
            fq = QFormLayout(gq)
            self.log_cb = QCheckBox(); self.log_cb.setChecked(self._cfg.get('use_log_scale', True))
            fq.addRow("Log Scale:", self.log_cb)
            lay.addWidget(gq)
            if hasattr(self, 'viz_combo'):
                self.viz_combo.currentTextChanged.connect(self._update_quantities_scope_state)
                self._update_quantities_scope_state(self.viz_combo.currentText())

        if self._scope in ('all', 'format'):
            g4 = QGroupBox("Pie Chart Settings")
            f4 = QFormLayout(g4)
            self.pct_cb = QCheckBox(); self.pct_cb.setChecked(self._cfg.get('show_percentages', True))
            f4.addRow("Show %:", self.pct_cb)
            self.explode_cb = QCheckBox(); self.explode_cb.setChecked(self._cfg.get('explode_slices', False))
            f4.addRow("Explode Slices:", self.explode_cb)
            lay.addWidget(g4)

            g5 = QGroupBox("Heatmap Settings")
            f5 = QFormLayout(g5)
            self.val_cb = QCheckBox(); self.val_cb.setChecked(self._cfg.get('show_values', True))
            f5.addRow("Show % on Cells:", self.val_cb)
            self.cmap_combo = QComboBox(); self.cmap_combo.addItems(colorheatmap)
            self.cmap_combo.setCurrentText(self._cfg.get('colormap', 'YlGn'))
            f5.addRow("Colormap:", self.cmap_combo)
            lay.addWidget(g5)

        self._font_grp = None
        self._pie_style = None
        self._legend_grp = None
        self._export_grp = None
        if self._scope in ('all', 'format'):
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

    def _update_quantities_scope_state(self, viz_type: str):
        """
        Update quantity-scope control availability based on visualization type.

        Args:
            viz_type (str): Current visualization type text selected in this dialog.

        Behavior:
            ``Log Scale`` remains available only for heatmap quantities. It is disabled
            for non-heatmap views so users are not presented with non-applicable controls.

        Preserved behavior:
            The underlying config key/value semantics are unchanged; only control
            enablement state is updated.
        """
        if not hasattr(self, 'log_cb') or self.log_cb is None:
            return
        is_heatmap = (viz_type == 'Heatmaps')
        self.log_cb.setEnabled(is_heatmap)
        if is_heatmap:
            self.log_cb.setToolTip("")
        else:
            self.log_cb.setToolTip("Log scale is only available for heatmap view.")

    def collect(self):
        """
        Collect selected settings for the active scope while preserving untouched values.

        Returns:
            dict: Updated configuration dictionary.

        Scope behavior:
            - ``format`` updates visual/style/font/legend/export appearance keys.
            - ``quantities`` updates scientific quantity/configuration keys.
            - ``all`` preserves legacy combined update behavior.

        Preserved behavior:
            Removed UI features (sample colors/names and pie label color) are
            intentionally not collected, preventing confusing no-op updates.
        """
        d = dict(self._cfg)
        if hasattr(self, 'viz_combo'):
            d['visualization_type'] = self.viz_combo.currentText()
        if hasattr(self, 'pml_cb'):
            d['use_particles_per_ml'] = self.pml_cb.isChecked()
        if hasattr(self, 'dil_spin'):
            d['dilution_factor'] = self.dil_spin.value()
        if hasattr(self, 'st_spin'):
            d['single_threshold'] = self.st_spin.value()
        if hasattr(self, 'mt_spin'):
            d['multiple_threshold'] = self.mt_spin.value()
        if hasattr(self, 'pct_cb'):
            d['show_percentages'] = self.pct_cb.isChecked()
        if hasattr(self, 'explode_cb'):
            d['explode_slices'] = self.explode_cb.isChecked()
        if hasattr(self, 'log_cb'):
            d['use_log_scale'] = self.log_cb.isChecked()
        if hasattr(self, 'val_cb'):
            d['show_values'] = self.val_cb.isChecked()
        if hasattr(self, 'cmap_combo'):
            d['colormap'] = self.cmap_combo.currentText()
        if self._font_grp is not None:
            d.update(self._font_grp.collect())
        if self._pie_style is not None:
            d.update(self._pie_style.collect())
        if self._legend_grp is not None:
            d.update(self._legend_grp.collect())
        if self._export_grp is not None:
            d.update(self._export_grp.collect())
        if self.mode_combo is not None:
            d['display_mode'] = self.mode_combo.currentText()
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
        """
        Build the display dialog with visualization and table tabs.

        Bottom buttons provide primary workflows:
        plot format settings, quantity configuration, reset, and figure export.
        Statistics-table export is exposed in the table tab (not right-click).
        """
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        self._stats = QLabel("")
        self._stats.setStyleSheet("color:#6B7280; font-size:11px; padding:2px 6px;")
        lay.addWidget(self._stats)

        self.tabs = QTabWidget()

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
            _itk_log.exception("Handled exception in _build_ui")
            pass
        viz_lay.addWidget(self.canvas, stretch=1)

        tb = QHBoxLayout()
        tb.setContentsMargins(0, 2, 0, 0)
        btn_fmt = QPushButton("Plot format settings")
        btn_fmt.clicked.connect(self._open_plot_format_settings)
        btn_qty = QPushButton("Configure plot quantities")
        btn_qty.clicked.connect(self._open_configure_plot_quantities)
        btn_r = QPushButton("Reset layout")
        btn_r.setToolTip("Reset all subplot positions to auto layout\n(or middle-click on the figure)")
        btn_r.clicked.connect(self._reset_layout)
        btn_e = QPushButton("Export figure")
        btn_e.clicked.connect(self._export_figure)
        tb.addWidget(btn_fmt)
        tb.addWidget(btn_qty)
        tb.addWidget(btn_r)
        tb.addWidget(btn_e)
        viz_lay.addLayout(tb)

        self.tabs.addTab(viz_widget, "Visualization")

        table_widget = QWidget()
        table_lay = QVBoxLayout(table_widget)
        table_lay.setContentsMargins(0, 0, 0, 0)
        table_lay.setSpacing(4)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        table_lay.addWidget(self.table)

        table_btn_row = QHBoxLayout()
        table_btn_row.setContentsMargins(0, 0, 0, 0)
        table_btn_row.addStretch()
        btn_export_table = QPushButton("Export statistics table")
        btn_export_table.clicked.connect(self._download_table)
        table_btn_row.addWidget(btn_export_table)
        table_lay.addLayout(table_btn_row)

        self.tabs.addTab(table_widget, "Statistics Table")

        lay.addWidget(self.tabs, stretch=1)
    def _ctx_menu(self, pos):
        """
        Build an intentionally minimal right-click menu.

        This menu only exposes lightweight visual quick toggles and isotope label mode.
        Full format settings, quantity configuration, reset, figure export, and
        statistics-table export are intentionally delegated to dedicated buttons.

        Preserved behavior:
            quick-toggle and isotope-label actions still update existing config keys.

        Args:
            pos (Any): Position point.
        """
        cfg = self.node.config
        menu = QMenu(self)

        tm = menu.addMenu("Quick Toggles")
        for key, label in [
            ('show_percentages', 'Show Percentages'),
            ('explode_slices', 'Explode Slices'),
            ('show_values', 'Values on Cells'),
            ('donut', 'Donut Mode'),
            ('shadow', 'Shadow'),
            ('legend_show', 'Show Legend'),
        ]:
            a = tm.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        lm = menu.addMenu("Isotope Label")
        for mode in LABEL_MODES:
            a = lm.addAction(mode); a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set('label_mode', v))

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
        """
        Open the legacy all-in-one settings dialog for compatibility.

        This preserves prior behavior and is retained as an internal fallback route.
        """
        ad = self.node.extract_analysis_data()
        dlg = SingleMultipleSettingsDialog(self.node.config, self.node.input_data, ad, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_plot_format_settings(self):
        """
        Open format-scoped settings dialog.

        Handles visual formatting controls only and preserves scientific/data
        computation semantics.
        """
        ad = self.node.extract_analysis_data()
        dlg = SingleMultipleSettingsDialog(
            self.node.config, self.node.input_data, ad, self, scope='format')
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_configure_plot_quantities(self):
        """
        Open quantities-scoped settings dialog.

        Handles scientific quantity/configuration controls (visualization type,
        units, dilution, thresholds, display mode, and heatmap log scaling).
        """
        ad = self.node.extract_analysis_data()
        dlg = SingleMultipleSettingsDialog(
            self.node.config, self.node.input_data, ad, self, scope='quantities')
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _reset_layout(self):
        """Reset subplot layout and clear persisted draggable label positions."""
        self.node.config['label_positions'] = {}
        self._anns = {}
        self.canvas.reset_layout()

    def _export_figure(self):
        """Open the existing figure export workflow for the Single/Multiple plot."""
        download_matplotlib_figure(self.fig, self, "single_multiple_analysis")

    def _download_table(self):
        """
        Export the statistics table as CSV from a table-specific UI location.

        This preserves non-figure export behavior while intentionally removing
        table export from the plot right-click menu.
        """
        ad = self.node.extract_analysis_data()
        if not ad:
            QMessageBox.warning(self, "Warning", "No data available"); return
        cfg = self.node.config
        df = SingleMultipleElementHelper.statistics_table(
            ad, self._multi, cfg.get('use_particles_per_ml'),
            self.parent_window, cfg.get('dilution_factor', 1.0),
            cfg.get('label_mode', 'Symbol'))
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
            _itk_log.exception("Handled exception in _refresh")
            print(f"Error updating SM display: {e}")
            import traceback; traceback.print_exc()


    def _draw_pies(self, ad, cfg):
        """
        Draw pie/donut visualizations for single vs multiple-element distributions.

        Args:
            ad (Any): Analysis data (single-sample dict or multi-sample mapping).
            cfg (dict): Active plot configuration.

        Preserved behavior:
            Single/multiple classification and value computations are unchanged.
            This method only controls subplot layout/routing for the selected
            multi-sample display mode.
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
            mode = cfg.get('display_mode', 'Individual Subplots')

            if mode == 'Side by Side Subplots':
                for i, sn in enumerate(names):
                    sr = ad[sn]
                    dn = get_display_name(sn, cfg)
                    si = {'is_summed': False}

                    ax1 = self.fig.add_subplot(2, n, i + 1)
                    self._pie_one(ax1, sr, 'single', s_colors, pml, dil, si, cfg, fp, lc,
                                  sp_key=f'{sn}_single')
                    ax1.set_title(f'{dn} - Single', fontproperties=fp, color=fc)

                    ax2 = self.fig.add_subplot(2, n, n + i + 1)
                    self._pie_one(ax2, sr, 'multiple', m_colors, pml, dil, si, cfg, fp, lc,
                                  sp_key=f'{sn}_multiple')
                    ax2.set_title(f'{dn} - Multiple', fontproperties=fp, color=fc)
            elif mode == 'Combined View':
                combined = self._combine_multi_analysis(ad)
                ax1 = self.fig.add_subplot(1, 2, 1)
                self._pie_one(ax1, combined, 'single', s_colors, pml, dil, None, cfg, fp, lc,
                              sp_key='combined_single')
                ax1.set_title('Combined - Single', fontproperties=fp, color=fc)

                ax2 = self.fig.add_subplot(1, 2, 2)
                self._pie_one(ax2, combined, 'multiple', m_colors, pml, dil, None, cfg, fp, lc,
                              sp_key='combined_multiple')
                ax2.set_title('Combined - Multiple', fontproperties=fp, color=fc)
            else:
                for i, sn in enumerate(names):
                    sr = ad[sn]
                    dn = get_display_name(sn, cfg)
                    si = {'is_summed': False}

                    ax1 = self.fig.add_subplot(n, 2, i*2 + 1)
                    self._pie_one(ax1, sr, 'single', s_colors, pml, dil, si, cfg, fp, lc,
                                  sp_key=f'{sn}_single')
                    ax1.set_title(f'{dn} - Single', fontproperties=fp, color=fc)

                    ax2 = self.fig.add_subplot(n, 2, i*2 + 2)
                    self._pie_one(ax2, sr, 'multiple', m_colors, pml, dil, si, cfg, fp, lc,
                                  sp_key=f'{sn}_multiple')
                    ax2.set_title(f'{dn} - Multiple', fontproperties=fp, color=fc)
        else:
            ax1 = self.fig.add_subplot(1, 2, 1)
            self._pie_one(ax1, ad, 'single', s_colors, pml, dil, None, cfg, fp, lc,
                          sp_key='single')
            ax1.set_title('Single Element Particles', fontproperties=fp, color=fc)

            ax2 = self.fig.add_subplot(1, 2, 2)
            self._pie_one(ax2, ad, 'multiple', m_colors, pml, dil, None, cfg, fp, lc,
                          sp_key='multiple')
            ax2.set_title('Multiple Element Particles', fontproperties=fp, color=fc)

    def _combine_multi_analysis(self, analysis_by_sample):
        """
        Combine per-sample analysis into one aggregated analysis structure.

        Args:
            analysis_by_sample (dict): Mapping ``sample_name -> analysis result``.

        Returns:
            dict: Aggregated analysis in the schema expected by existing pie
            rendering/statistics helpers.

        Preserved behavior:
            Classification semantics are preserved; this only aggregates counts for
            Combined View rendering.
        """
        combo_counts = defaultdict(int)
        total_particles = 0
        for sample_result in analysis_by_sample.values():
            total_particles += int(sample_result.get('total_particles', 0))
            for combo, det in sample_result.get('all_combinations', []):
                combo_counts[combo] += int(det.get('count', 0))

        all_combos = []
        for combo, count in sorted(combo_counts.items(), key=lambda kv: kv[1], reverse=True):
            all_combos.append((combo, {'count': count, 'indices': [], 'is_single': len(combo.split(', ')) == 1}))

        single = []
        multiple = []
        for combo, det in all_combos:
            pct = (det['count'] / total_particles * 100) if total_particles else 0.0
            if det['is_single']:
                single.append((combo, det, pct))
            else:
                multiple.append((combo, det, pct))

        return {
            'single_combinations': single,
            'multiple_combinations': multiple,
            'total_particles': total_particles,
            'all_combinations': all_combos,
        }

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
            results, ctype, custom_colors, pml, self.parent_window, dil, si,
            cfg.get('label_mode', 'Symbol'))
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
            lines = lbl.split('\n')
            lines[0] = format_combination_label(lines[0], mode, Renderer.MATHTEXT, cfg)
            return '\n'.join(lines)

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
                _itk_log.exception("Handled exception in _pie_one")
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
        hd = SingleMultipleElementHelper.heatmap_data(
            ad, pml, self.parent_window, dil, cfg.get('label_mode', 'Symbol'), cfg)
        if not hd:
            return
        cmap_name = cfg.get('colormap', 'YlGn')
        cmap = plt.cm.get_cmap(cmap_name)
        unit = 'P/mL' if pml else 'P'
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
        unit = "P/mL" if pml else "P"
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
                self.parent_window, cfg.get('dilution_factor', 1.0),
                cfg.get('label_mode', 'Symbol'))
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
            _itk_log.exception("Handled exception in _update_table")
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





