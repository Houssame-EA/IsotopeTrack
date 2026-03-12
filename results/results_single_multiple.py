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
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
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
    FontSettingsGroup, get_sample_color, get_display_name,
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
}


# ── Helper class (logic only, no UI) ──────────────────────────────────

class SingleMultipleElementHelper:
    """Analysis helper for single vs multiple element particle classification."""

    @staticmethod
    def analyze_particles(particle_data, pct_single=0.5, pct_multiple=0.5):
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
        return ', '.join(re.sub(r'^\d+', '', e.strip()) for e in combo_str.split(','))

    @staticmethod
    def calc_per_ml(count, parent_window, dilution=1.0, sample_info=None):
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


# ── Settings Dialog ────────────────────────────────────────────────────

class SingleMultipleSettingsDialog(QDialog):

    def __init__(self, cfg, input_data, analysis_data, parent=None):
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

        # ── Viz type ──
        g1 = QGroupBox("Visualization")
        f1 = QFormLayout(g1)
        self.viz_combo = QComboBox(); self.viz_combo.addItems(VIZ_TYPES)
        self.viz_combo.setCurrentText(self._cfg.get('visualization_type', 'Pie Charts'))
        f1.addRow("Type:", self.viz_combo)
        lay.addWidget(g1)

        # ── Units ──
        g2 = QGroupBox("Units & Dilution")
        f2 = QFormLayout(g2)
        self.pml_cb = QCheckBox(); self.pml_cb.setChecked(self._cfg.get('use_particles_per_ml', False))
        f2.addRow("Use Particles/mL:", self.pml_cb)
        self.dil_spin = QDoubleSpinBox(); self.dil_spin.setRange(0.001, 100000)
        self.dil_spin.setDecimals(3); self.dil_spin.setValue(self._cfg.get('dilution_factor', 1.0))
        f2.addRow("Dilution Factor:", self.dil_spin)
        lay.addWidget(g2)

        # ── Display mode (multi) ──
        if self._multi:
            gm = QGroupBox("Multiple Sample Display")
            fm = QFormLayout(gm)
            self.mode_combo = QComboBox(); self.mode_combo.addItems(SM_DISPLAY_MODES)
            self.mode_combo.setCurrentText(self._cfg.get('display_mode', SM_DISPLAY_MODES[0]))
            fm.addRow("Mode:", self.mode_combo)
            lay.addWidget(gm)

        # ── Thresholds ──
        g3 = QGroupBox("Thresholds")
        f3 = QFormLayout(g3)
        self.st_spin = QDoubleSpinBox(); self.st_spin.setRange(0, 10); self.st_spin.setDecimals(2)
        self.st_spin.setSuffix('%'); self.st_spin.setValue(self._cfg.get('single_threshold', 0.5))
        f3.addRow("Single Threshold:", self.st_spin)
        self.mt_spin = QDoubleSpinBox(); self.mt_spin.setRange(0, 10); self.mt_spin.setDecimals(2)
        self.mt_spin.setSuffix('%'); self.mt_spin.setValue(self._cfg.get('multiple_threshold', 0.5))
        f3.addRow("Multiple Threshold:", self.mt_spin)
        lay.addWidget(g3)

        # ── Pie settings ──
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

        # ── Heatmap settings ──
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

        # ── Sample colors (multi) ──
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

        # ── Font ──
        self._font_grp = FontSettingsGroup(self._cfg)
        lay.addWidget(self._font_grp.build())

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _pick_lbl_color(self):
        c = QColorDialog.getColor(self._lbl_color, self)
        if c.isValid():
            self._lbl_color = c
            self.lbl_btn.setStyleSheet(f"background-color:{c.name()}; min-height:25px;")

    def _pick_sc(self, sn, btn):
        c = QColorDialog.getColor(QColor(self._sc.get(sn, '#3B82F6')), self)
        if c.isValid():
            self._sc[sn] = c.name()
            btn.setStyleSheet(f"background-color:{c.name()}; border:1px solid black;")

    def collect(self):
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
        super().__init__(parent_window)
        self.node = node
        self.parent_window = parent_window
        self.setWindowTitle("Single vs Multiple Element Analysis")
        self.setMinimumSize(1400, 900)
        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    @property
    def _multi(self):
        return (self.node.input_data and self.node.input_data.get('type') == 'multiple_sample_data')

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        self._stats = QLabel("")
        self._stats.setStyleSheet("color:#6B7280; font-size:11px; padding:2px 6px;")
        lay.addWidget(self._stats)

        self.tabs = QTabWidget()

        # Viz tab
        self.fig = Figure(figsize=(16, 10), dpi=100, tight_layout=True)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._ctx_menu)
        self.tabs.addTab(self.canvas, "Visualization")

        # Stats table tab
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.table, "Statistics Table")

        lay.addWidget(self.tabs, stretch=1)

    # ── Context menu ──

    def _ctx_menu(self, pos):
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
                           ('use_particles_per_ml', 'Particles/mL')]:
            a = tm.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        if self._multi:
            mm = menu.addMenu("Display Mode")
            for m in SM_DISPLAY_MODES:
                a = mm.addAction(m); a.setCheckable(True)
                a.setChecked(cfg.get('display_mode') == m)
                a.triggered.connect(lambda _, v=m: self._set('display_mode', v))

        menu.addSeparator()
        menu.addAction("Configure…").triggered.connect(self._open_settings)
        menu.addAction("Download Figure…").triggered.connect(
            lambda: download_matplotlib_figure(self.fig, self, "single_multiple_analysis.png"))
        menu.addAction("Download Statistics Table…").triggered.connect(self._download_table)

        menu.exec(self.canvas.mapToGlobal(pos))

    def _toggle(self, key):
        self.node.config[key] = not self.node.config.get(key, False)
        self._refresh()

    def _set(self, key, value):
        self.node.config[key] = value
        self._refresh()

    def _open_settings(self):
        ad = self.node.extract_analysis_data()
        dlg = SingleMultipleSettingsDialog(self.node.config, self.node.input_data, ad, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

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

    # ── Refresh ──

    def _refresh(self):
        try:
            self.fig.clear()
            ad = self.node.extract_analysis_data()
            cfg = self.node.config

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
        except Exception as e:
            print(f"Error updating SM display: {e}")
            import traceback; traceback.print_exc()

    # ── Pie charts ──

    def _draw_pies(self, ad, cfg):
        fp = make_font_properties(cfg)
        fc = cfg.get('font_color', '#000000')
        lc = cfg.get('label_color', '#000000')
        pml = cfg.get('use_particles_per_ml', False)
        dil = cfg.get('dilution_factor', 1.0)
        s_colors = cfg.get('single_pie_colors', {})
        m_colors = cfg.get('multiple_pie_colors', {})

        if self._multi:
            names = list(ad.keys())
            n = len(names)
            for i, sn in enumerate(names):
                sr = ad[sn]
                dn = get_display_name(sn, cfg)
                si = {'is_summed': False}

                ax1 = self.fig.add_subplot(n, 2, i*2 + 1)
                self._pie_one(ax1, sr, 'single', s_colors, pml, dil, si, cfg, fp, lc)
                ax1.set_title(f'{dn} – Single', fontproperties=fp, color=fc)

                ax2 = self.fig.add_subplot(n, 2, i*2 + 2)
                self._pie_one(ax2, sr, 'multiple', m_colors, pml, dil, si, cfg, fp, lc)
                ax2.set_title(f'{dn} – Multiple', fontproperties=fp, color=fc)
        else:
            ax1 = self.fig.add_subplot(1, 2, 1)
            self._pie_one(ax1, ad, 'single', s_colors, pml, dil, None, cfg, fp, lc)
            ax1.set_title('Single Element Particles', fontproperties=fp, color=fc)

            ax2 = self.fig.add_subplot(1, 2, 2)
            self._pie_one(ax2, ad, 'multiple', m_colors, pml, dil, None, cfg, fp, lc)
            ax2.set_title('Multiple Element Particles', fontproperties=fp, color=fc)

    def _pie_one(self, ax, results, ctype, custom_colors, pml, dil, si, cfg, fp, lc):
        pd = SingleMultipleElementHelper.pie_data(
            results, ctype, custom_colors, pml, self.parent_window, dil, si)
        if not pd:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                    transform=ax.transAxes, color='gray')
            return
        explode = [0.1]*len(pd['values']) if cfg.get('explode_slices') else None
        autopct = '%1.1f%%' if cfg.get('show_percentages') else None
        wedges, texts, autotexts = ax.pie(
            pd['values'], labels=pd['labels'], colors=pd['colors'],
            autopct=autopct, explode=explode)
        for t in texts:
            t.set_fontproperties(fp); t.set_color(lc)
        if autotexts:
            for at in autotexts:
                at.set_fontproperties(fp); at.set_color('black'); at.set_weight('bold')

    # ── Heatmaps ──

    def _draw_heatmaps(self, ad, cfg):
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

    # ── Stats ──

    def _update_stats(self, ad):
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
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        dlg = SingleMultipleElementDisplayDialog(self, parent_window)
        dlg.exec()
        return True

    def process_data(self, input_data):
        if not input_data:
            return
        self.input_data = input_data
        self.configuration_changed.emit()

    def extract_analysis_data(self):
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