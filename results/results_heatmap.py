from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QCheckBox, QGroupBox, QPushButton, QLineEdit, QFrame,
    QScrollArea, QWidget, QMenu, QDialogButtonBox, QMessageBox, QInputDialog, QColorDialog
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QCursor
from matplotlib.figure import Figure
import numpy as np
import math

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS, DATA_KEY_MAPPING,
    FontSettingsGroup, ExportSettingsGroup, MplDraggableCanvas,
    get_font_config, apply_font_to_matplotlib,
    apply_font_to_colorbar_standalone, get_display_name, get_sample_color,
    download_matplotlib_figure,
)

from results.utils_sort import (
    sort_elements_by_mass, format_element_label, format_combination_label
)
from widget.colors import colorheatmap


HEATMAP_DATA_TYPES = [
    'Counts', 'Element Mass (fg)', 'Particle Mass (fg)',
    'Element Moles (fmol)', 'Particle Moles (fmol)',
    'Element Mass %', 'Particle Mass %', 'Element Mole %', 'Particle Mole %'
]


class HeatmapSettingsDialog(QDialog):
    """Full settings dialog opened from right-click → Configure…"""

    def __init__(self, config: dict, is_multi: bool,
                 sample_names: list, parent=None):
        """
        Args:
            config (dict): Configuration dictionary.
            is_multi (bool): The is multi.
            sample_names (list): The sample names.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("Heatmap Settings")
        self.setMinimumWidth(480)
        self._config = dict(config)
        self._is_multi = is_multi
        self._sample_names = sample_names
        self._build()

    def _build(self):
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
                'Individual Subplots', 'Side by Side Subplots',
                'Combined Heatmap', 'Comparative View'
            ])
            self.display_mode.setCurrentText(
                self._config.get('display_mode', 'Individual Subplots'))
            fl.addRow("Display Mode:", self.display_mode)
            layout.addWidget(g)

        g = QGroupBox("Data Type")
        vl = QVBoxLayout(g)
        self.data_type = QComboBox()
        self.data_type.addItems(HEATMAP_DATA_TYPES)
        self.data_type.setCurrentText(
            self._config.get('data_type_display', 'Counts'))
        vl.addWidget(self.data_type)
        layout.addWidget(g)

        g = QGroupBox("Element Search & Filter")
        sl = QVBoxLayout(g)
        row = QHBoxLayout()
        row.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit(self._config.get('search_element', ''))
        self.search_edit.setPlaceholderText("e.g. Fe, Ti (order doesn't matter)")
        row.addWidget(self.search_edit)
        sl.addLayout(row)
        self.highlight_cb = QCheckBox("Highlight matches")
        self.highlight_cb.setChecked(self._config.get('highlight_matches', True))
        sl.addWidget(self.highlight_cb)
        self.filter_only_cb = QCheckBox("Show only matches")
        self.filter_only_cb.setChecked(self._config.get('filter_combinations', False))
        sl.addWidget(self.filter_only_cb)
        layout.addWidget(g)

        g = QGroupBox("Combination Range")
        fl = QFormLayout(g)
        self.start_spin = QSpinBox()
        self.start_spin.setRange(1, 1000)
        self.start_spin.setValue(self._config.get('start_range', 1))
        fl.addRow("Start:", self.start_spin)
        self.end_spin = QSpinBox()
        self.end_spin.setRange(2, 1000)
        self.end_spin.setValue(self._config.get('end_range', 10))
        fl.addRow("End:", self.end_spin)
        layout.addWidget(g)

        g = QGroupBox("Filters")
        fl = QFormLayout(g)
        self.filter_zeros = QCheckBox()
        self.filter_zeros.setChecked(self._config.get('filter_zeros', True))
        fl.addRow("Filter zeros:", self.filter_zeros)
        self.min_particles = QSpinBox()
        self.min_particles.setRange(1, 1000)
        self.min_particles.setValue(self._config.get('min_particles', 1))
        fl.addRow("Min particles:", self.min_particles)
        layout.addWidget(g)

        g = QGroupBox("Labels")
        fl = QFormLayout(g)
        self.mass_numbers_cb = QCheckBox()
        self.mass_numbers_cb.setChecked(self._config.get('show_mass_numbers', True))
        fl.addRow("Show mass numbers:", self.mass_numbers_cb)
        layout.addWidget(g)

        g = QGroupBox("Display")
        fl = QFormLayout(g)
        self.show_numbers_cb = QCheckBox()
        self.show_numbers_cb.setChecked(self._config.get('show_numbers', True))
        fl.addRow("Show numbers:", self.show_numbers_cb)
        self.show_colorbar_cb = QCheckBox()
        self.show_colorbar_cb.setChecked(self._config.get('show_colorbar', True))
        fl.addRow("Show colorbar:", self.show_colorbar_cb)
        layout.addWidget(g)

        g = QGroupBox("Color Scale")
        vl = QVBoxLayout(g)
        self.colorscale = QComboBox()
        self.colorscale.addItems(colorheatmap)
        self.colorscale.setCurrentText(self._config.get('colorscale', 'YlGnBu'))
        vl.addWidget(self.colorscale)
        layout.addWidget(g)

        from PySide6.QtWidgets import QDoubleSpinBox as _QDbl
        g = QGroupBox("Color Range")
        fl = QFormLayout(g)
        self.log_scale_cb = QCheckBox()
        self.log_scale_cb.setChecked(self._config.get('log_scale', False))
        fl.addRow("Log scale:", self.log_scale_cb)
        self.custom_range_cb = QCheckBox()
        self.custom_range_cb.setChecked(self._config.get('use_custom_range', False))
        fl.addRow("Custom range:", self.custom_range_cb)
        self.vmin_spin = _QDbl()
        self.vmin_spin.setRange(-1e9, 1e9); self.vmin_spin.setDecimals(3)
        self.vmin_spin.setValue(self._config.get('vmin', 0.0))
        fl.addRow("vmin:", self.vmin_spin)
        self.vmax_spin = _QDbl()
        self.vmax_spin.setRange(-1e9, 1e9); self.vmax_spin.setDecimals(3)
        self.vmax_spin.setValue(self._config.get('vmax', 100.0))
        fl.addRow("vmax:", self.vmax_spin)
        layout.addWidget(g)

        g = QGroupBox("Cell Appearance")
        fl = QFormLayout(g)
        self.x_rotation_spin = QSpinBox()
        self.x_rotation_spin.setRange(0, 90); self.x_rotation_spin.setSuffix("°")
        self.x_rotation_spin.setValue(self._config.get('x_rotation', 0))
        fl.addRow("X label rotation:", self.x_rotation_spin)
        self.ann_fontsize_spin = QSpinBox()
        self.ann_fontsize_spin.setRange(0, 24)
        self.ann_fontsize_spin.setSpecialValueText("Auto")
        self.ann_fontsize_spin.setValue(self._config.get('annotation_fontsize', 0))
        fl.addRow("Annotation font size:", self.ann_fontsize_spin)
        self.cell_lw_spin = _QDbl()
        self.cell_lw_spin.setRange(0.0, 5.0); self.cell_lw_spin.setSingleStep(0.25)
        self.cell_lw_spin.setDecimals(2); self.cell_lw_spin.setSpecialValueText("Off")
        self.cell_lw_spin.setValue(self._config.get('cell_linewidth', 0.5))
        fl.addRow("Cell border width:", self.cell_lw_spin)
        layout.addWidget(g)

        self._font_group = FontSettingsGroup(self._config)
        layout.addWidget(self._font_group.build())

        self._export_grp = ExportSettingsGroup(self._config)
        layout.addWidget(self._export_grp.build())

        if self._is_multi:
            g = QGroupBox("Sample Colors")
            sl_layout = QVBoxLayout(g)
            self._sample_btns = {}
            colors = self._config.get('sample_colors', {})
            for i, sn in enumerate(self._sample_names):
                row = QHBoxLayout()
                lbl = QLabel(sn[:25] + "…" if len(sn) > 25 else sn)
                lbl.setFixedWidth(160)
                row.addWidget(lbl)
                btn = QPushButton()
                btn.setFixedSize(30, 20)
                c = colors.get(sn, DEFAULT_SAMPLE_COLORS[i % len(DEFAULT_SAMPLE_COLORS)])
                btn.setStyleSheet(f"background-color:{c}; border:1px solid black;")
                btn.clicked.connect(lambda _, s=sn, b=btn: self._pick_color(s, b))
                row.addWidget(btn)
                row.addStretch()
                w = QWidget(); w.setLayout(row)
                sl_layout.addWidget(w)
                self._sample_btns[sn] = (btn, c)
            layout.addWidget(g)

        layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def _pick_color(self, name, btn):
        """
        Args:
            name (Any): Name string.
            btn (Any): The btn.
        """
        c = QColorDialog.getColor(QColor(self._sample_btns[name][1]), self)
        if c.isValid():
            btn.setStyleSheet(f"background-color:{c.name()}; border:1px solid black;")
            b, _ = self._sample_btns[name]
            self._sample_btns[name] = (b, c.name())

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        cfg = dict(self._config)
        cfg['data_type_display'] = self.data_type.currentText()
        cfg['search_element'] = self.search_edit.text().strip()
        cfg['highlight_matches'] = self.highlight_cb.isChecked()
        cfg['filter_combinations'] = self.filter_only_cb.isChecked()
        cfg['start_range'] = self.start_spin.value()
        cfg['end_range'] = self.end_spin.value()
        cfg['filter_zeros'] = self.filter_zeros.isChecked()
        cfg['min_particles'] = self.min_particles.value()
        cfg['show_mass_numbers'] = self.mass_numbers_cb.isChecked()
        cfg['show_numbers'] = self.show_numbers_cb.isChecked()
        cfg['show_colorbar'] = self.show_colorbar_cb.isChecked()
        cfg['colorscale'] = self.colorscale.currentText()
        cfg['log_scale']         = self.log_scale_cb.isChecked()
        cfg['use_custom_range']  = self.custom_range_cb.isChecked()
        cfg['vmin']              = self.vmin_spin.value()
        cfg['vmax']              = self.vmax_spin.value()
        cfg['x_rotation']          = self.x_rotation_spin.value()
        cfg['annotation_fontsize'] = self.ann_fontsize_spin.value()
        cfg['cell_linewidth']      = self.cell_lw_spin.value()
        cfg.update(self._font_group.collect())
        cfg.update(self._export_grp.collect())

        if self._is_multi:
            cfg['display_mode'] = self.display_mode.currentText()
            sc = {}
            for sn, (btn, c) in self._sample_btns.items():
                sc[sn] = c
            cfg['sample_colors'] = sc
        return cfg


class HeatmapDisplayDialog(QDialog):
    """
    Full-figure heatmap dialog with right-click context menu.
    """

    def __init__(self, heatmap_node, parent_window=None):
        """
        Args:
            heatmap_node (Any): The heatmap node.
            parent_window (Any): The parent window.
        """
        super().__init__(parent_window)
        self.node = heatmap_node
        self.parent_window = parent_window
        self.setWindowTitle("Element Combination Heatmap")
        self.setMinimumSize(1000, 700)
        self._setup_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

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

    # ── UI ──────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.figure = Figure(figsize=(16, 10), dpi=140, tight_layout=True)
        self.canvas = MplDraggableCanvas(self.figure)
        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.canvas)

        # ── Bottom toolbar ────────────────────────────────────────────
        bb = QHBoxLayout()
        bb.setContentsMargins(0, 4, 0, 0)
        btn_s = QPushButton("⚙  Settings")
        btn_s.clicked.connect(self._open_settings)
        btn_r = QPushButton("↺  Reset Layout")
        btn_r.setToolTip("Reset all subplot positions to auto layout\n(or middle-click on the figure)")
        btn_r.clicked.connect(self._reset_layout)
        btn_e = QPushButton("⬆  Export…")
        btn_e.clicked.connect(self._export_figure)
        bb.addWidget(btn_s)
        bb.addWidget(btn_r)
        bb.addStretch()
        bb.addWidget(btn_e)
        layout.addLayout(bb)

    # ── Context menu ────────────────────────

    def _show_context_menu(self, pos):
        """
        Args:
            pos (Any): Position point.
        """
        cfg = self.node.config
        menu = QMenu(self)

        toggle_menu = menu.addMenu("Quick Toggles")
        self._add_toggle(toggle_menu, "Show Numbers", 'show_numbers')
        self._add_toggle(toggle_menu, "Show Colorbar", 'show_colorbar')
        self._add_toggle(toggle_menu, "Show Mass Numbers", 'show_mass_numbers')
        self._add_toggle(toggle_menu, "Filter Zeros", 'filter_zeros')
        self._add_toggle(toggle_menu, "Highlight Matches", 'highlight_matches')
        self._add_toggle(toggle_menu, "Filter to Matches Only", 'filter_combinations')
        self._add_toggle(toggle_menu, "Log Scale", 'log_scale')
        self._add_toggle(toggle_menu, "Custom Color Range", 'use_custom_range')

        dt_menu = menu.addMenu("Data Type")
        current_dt = cfg.get('data_type_display', 'Counts')
        for dt in HEATMAP_DATA_TYPES:
            a = dt_menu.addAction(dt)
            a.setCheckable(True)
            a.setChecked(dt == current_dt)
            a.triggered.connect(lambda _, d=dt: self._set_and_refresh('data_type_display', d))

        cs_menu = menu.addMenu("Color Scale")
        current_cs = cfg.get('colorscale', 'YlGnBu')
        for cs in colorheatmap:
            a = cs_menu.addAction(cs)
            a.setCheckable(True)
            a.setChecked(cs == current_cs)
            a.triggered.connect(lambda _, c=cs: self._set_and_refresh('colorscale', c))

        rot_menu = menu.addMenu("X Label Rotation")
        cur_rot = cfg.get('x_rotation', 0)
        for rot in [0, 30, 45, 60, 90]:
            a = rot_menu.addAction(f"{rot}°")
            a.setCheckable(True)
            a.setChecked(cur_rot == rot)
            a.triggered.connect(lambda _, r=rot: self._set_and_refresh('x_rotation', r))

        search_action = menu.addAction("🔍 Search Elements…")
        search_action.triggered.connect(self._search_dialog)

        range_action = menu.addAction("📊 Set Range…")
        range_action.triggered.connect(self._range_dialog)

        if self._is_multi():
            dm_menu = menu.addMenu("Display Mode")
            modes = ['Individual Subplots', 'Side by Side Subplots',
                     'Combined Heatmap', 'Comparative View']
            cur = cfg.get('display_mode', modes[0])
            for m in modes:
                a = dm_menu.addAction(m)
                a.setCheckable(True)
                a.setChecked(m == cur)
                a.triggered.connect(lambda _, mode=m: self._set_and_refresh('display_mode', mode))

        menu.addSeparator()
        menu.addAction("↺  Reset Layout").triggered.connect(self._reset_layout)
        settings_action = menu.addAction("⚙  Configure…")
        settings_action.triggered.connect(self._open_settings)

        dl_action = menu.addAction("💾 Download Figure…")
        dl_action.triggered.connect(self._export_figure)

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

    def _set_and_refresh(self, key, value):
        """
        Args:
            key (Any): Dictionary or storage key.
            value (Any): Value to set or process.
        """
        self.node.config[key] = value
        self._refresh()

    def _search_dialog(self):
        text, ok = QInputDialog.getText(
            self, "Search Elements",
            "Enter element names (space-separated, order doesn't matter):",
            text=self.node.config.get('search_element', ''))
        if ok:
            self.node.config['search_element'] = text.strip()
            self._refresh()

    def _range_dialog(self):
        """Quick range adjustment via two input dialogs."""
        start, ok1 = QInputDialog.getInt(
            self, "Range Start", "Start from combination #:",
            self.node.config.get('start_range', 1), 1, 1000)
        if not ok1:
            return
        end, ok2 = QInputDialog.getInt(
            self, "Range End", "End at combination #:",
            self.node.config.get('end_range', 10), start + 1, 1000)
        if ok2:
            self.node.config['start_range'] = start
            self.node.config['end_range'] = end
            self._refresh()

    def _open_settings(self):
        dlg = HeatmapSettingsDialog(
            self.node.config, self._is_multi(), self._sample_names(), self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _reset_layout(self):
        self.canvas.reset_layout()

    def _export_figure(self):
        download_matplotlib_figure(self.figure, self, "heatmap")

    def _refresh(self):
        try:
            cfg = self.node.config

            if cfg.get('use_custom_figsize', False):
                self.figure.set_size_inches(cfg.get('figsize_w', 16.0),
                                            cfg.get('figsize_h', 10.0))

            self.figure.clear()
            bg = cfg.get('bg_color', '#FFFFFF')
            self.figure.patch.set_facecolor(bg)

            data = self.node.extract_combinations_data()

            if not data:
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5,
                        'No data available\nRight-click for options',
                        ha='center', va='center', transform=ax.transAxes,
                        fontsize=12, color='gray')
                ax.set_xticks([]); ax.set_yticks([])
            else:
                cfg = self.node.config
                if self._is_multi():
                    dm = cfg.get('display_mode', 'Individual Subplots')
                    self._draw_multi(data, cfg, dm)
                else:
                    ax = self.figure.add_subplot(111)
                    self._draw_heatmap(ax, data, cfg, "Element Combinations")
                    apply_font_to_matplotlib(ax, cfg)

            self.figure.tight_layout()
            self.canvas.draw()
            self.canvas.snapshot_positions()
        except Exception as e:
            print(f"Error refreshing heatmap: {e}")
            import traceback; traceback.print_exc()

    # ── Multi-sample dispatch ───────────────

    def _draw_multi(self, data, cfg, display_mode):
        """
        Args:
            data (Any): Input data.
            cfg (Any): The cfg.
            display_mode (Any): The display mode.
        """
        names = list(data.keys())
        n = len(names)

        if display_mode == 'Individual Subplots':
            cols = min(2, n)
            rows = math.ceil(n / cols)
            for i, sn in enumerate(names):
                ax = self.figure.add_subplot(rows, cols, i + 1)
                self._draw_heatmap(ax, data[sn], cfg, sn)
                apply_font_to_matplotlib(ax, cfg)

        elif display_mode == 'Side by Side Subplots':
            for i, sn in enumerate(names):
                ax = self.figure.add_subplot(1, n, i + 1)
                self._draw_heatmap(ax, data[sn], cfg, sn)
                apply_font_to_matplotlib(ax, cfg)

        elif display_mode == 'Combined Heatmap':
            combined = self._combine_data(data)
            ax = self.figure.add_subplot(111)
            self._draw_heatmap(ax, combined, cfg,
                               f"Combined ({len(data)} samples)")
            apply_font_to_matplotlib(ax, cfg)

        else:
            for i, sn in enumerate(names[:2]):
                ax = self.figure.add_subplot(1, 2, i + 1)
                self._draw_heatmap(ax, data[sn], cfg, sn)
                apply_font_to_matplotlib(ax, cfg)

    @staticmethod
    def _combine_data(data):
        """
        Args:
            data (Any): Input data.
        Returns:
            object: Result of the operation.
        """
        combined = {}
        for sample_data in data.values():
            for combo, d in sample_data.items():
                if combo not in combined:
                    combined[combo] = {
                        'count': 0, 'total_values': {}, 'particle_count': 0}
                combined[combo]['count'] += d['count']
                combined[combo]['particle_count'] += d['particle_count']
                for elem, vals in d['total_values'].items():
                    combined[combo].setdefault('total_values', {}).setdefault(elem, []).extend(vals)
        return combined

    # ── Core heatmap drawing ────────────────

    def _draw_heatmap(self, ax, sample_data, cfg, title):
        """
        Args:
            ax (Any): The ax.
            sample_data (Any): The sample data.
            cfg (Any): The cfg.
            title (Any): Window or dialog title.
        """
        if not sample_data:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                    transform=ax.transAxes, color='gray')
            return

        dt = cfg.get('data_type_display', 'Counts')
        search_text = cfg.get('search_element', '').strip()
        highlight = cfg.get('highlight_matches', True)
        filter_combos = cfg.get('filter_combinations', False)
        start = cfg.get('start_range', 1)
        end = cfg.get('end_range', 10)
        min_p = cfg.get('min_particles', 1)
        show_mass = cfg.get('show_mass_numbers', True)
        cscale = cfg.get('colorscale', 'YlGnBu')
        show_nums = cfg.get('show_numbers', True)
        show_cbar = cfg.get('show_colorbar', True)
        log_scale = cfg.get('log_scale', False)
        use_custom_range = cfg.get('use_custom_range', False)
        vmin_cfg = cfg.get('vmin', None) if use_custom_range else None
        vmax_cfg = cfg.get('vmax', None) if use_custom_range else None
        x_rotation = cfg.get('x_rotation', 0)
        ann_fs = cfg.get('annotation_fontsize', 0) or None
        cell_lw = cfg.get('cell_linewidth', 0.5)
        fc = get_font_config(cfg)

        search_elems = []
        if search_text:
            search_elems = [e.strip() for e in search_text.replace(',', ' ').split() if e.strip()]

        sorted_combos = sorted(sample_data.items(),
                                key=lambda x: x[1]['particle_count'], reverse=True)

        if search_elems and filter_combos:
            sorted_combos = [(c, d) for c, d in sorted_combos
                             if _combo_matches(c, search_elems)]

        sorted_combos = [(c, d) for c, d in sorted_combos
                         if d['particle_count'] >= min_p]

        end = min(end, len(sorted_combos))
        start = max(1, min(start, end))
        selected = sorted_combos[start - 1:end]

        if not selected:
            ax.text(0.5, 0.5, 'No combinations match filters',
                    ha='center', va='center', transform=ax.transAxes, color='gray')
            return

        all_elems = set()
        for _, d in selected:
            all_elems.update(d['total_values'].keys())
        all_elems = sort_elements_by_mass(list(all_elems))

        labels = []
        matrix = []
        hl_rows = []

        for combo, d in selected:
            count = d['particle_count']
            fmt = format_combination_label(combo, show_mass)
            labels.append(f"{fmt} ({count})")
            hl_rows.append(bool(search_elems and _combo_matches(combo, search_elems)))

            is_pct = dt.endswith('%')
            total_sum = 0
            if is_pct:
                for vals in d['total_values'].values():
                    if vals:
                        total_sum += np.sum(vals)

            row = []
            for elem in all_elems:
                vals = d['total_values'].get(elem, [])
                if not vals:
                    row.append(0)
                elif is_pct:
                    row.append((np.sum(vals) / total_sum * 100) if total_sum > 0 else 0)
                else:
                    row.append(np.mean(vals))
            matrix.append(row)

        matrix = np.nan_to_num(np.array(matrix), nan=0.0)

        plot_matrix = matrix.copy()
        if log_scale:
            plot_matrix = np.log10(np.where(plot_matrix > 0, plot_matrix, np.nan))

        imshow_kw = dict(cmap=cscale, aspect='auto', interpolation='nearest')
        if use_custom_range:
            imshow_kw['vmin'] = vmin_cfg
            imshow_kw['vmax'] = vmax_cfg
        im = ax.imshow(plot_matrix, **imshow_kw)

        if cell_lw > 0:
            ax.set_xticks(np.arange(len(all_elems) + 1) - 0.5, minor=True)
            ax.set_yticks(np.arange(len(labels) + 1) - 0.5, minor=True)
            ax.grid(which='minor', color='white', linewidth=cell_lw)
            ax.tick_params(which='minor', length=0)

        x_labels = [format_element_label(e, show_mass) for e in all_elems]
        ax.set_xticks(range(len(x_labels)))
        ax.set_xticklabels(x_labels, rotation=x_rotation,
                           ha='right' if x_rotation > 0 else 'center',
                           fontsize=fc['size'], fontweight='bold' if fc['bold'] else 'normal')
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=fc['size'],
                           fontweight='bold' if fc['bold'] else 'normal')

        if search_elems and highlight:
            for i, hl in enumerate(hl_rows):
                if hl:
                    ax.axhline(y=i + 0.35, color='black', linewidth=2, alpha=0.9,
                               xmin=-0.15, xmax=0, clip_on=False)
                    ax.get_yticklabels()[i].set_weight('bold')

        if self._is_multi():
            ax.set_title(title, fontsize=fc['size'] + 2, fontweight='bold', pad=20)

        if show_cbar:
            cbar = self.figure.colorbar(im, ax=ax, shrink=0.8)
            cbar_label = dt
            if log_scale:
                cbar_label = f"log₁₀({dt})"
            apply_font_to_colorbar_standalone(cbar, cfg, cbar_label)

        eff_fs = ann_fs if ann_fs else fc['size']
        if show_nums and plot_matrix.size < 1000:
            is_pct = dt.endswith('%')
            weight = 'bold' if fc['bold'] else 'normal'
            mx = np.nanmax(plot_matrix) if not np.all(np.isnan(plot_matrix)) else 1
            for i in range(len(labels)):
                for j in range(len(all_elems)):
                    v = plot_matrix[i, j]
                    v_orig = matrix[i, j]
                    if not np.isnan(v) and v_orig > 0:
                        tc = 'white' if v > mx * 0.5 else 'black'
                        if is_pct:
                            txt = f'{v_orig:.1f}%'
                        elif v_orig >= 1000:
                            txt = f'{v_orig:.0f}'
                        elif v_orig >= 1:
                            txt = f'{v_orig:.1f}'
                        else:
                            txt = f'{v_orig:.2f}'
                        ax.text(j, i, txt, ha='center', va='center',
                                color=tc, fontsize=eff_fs,
                                fontfamily=fc['family'], weight=weight)


def _combo_matches(combination: str, search_elements: list) -> bool:
    """Check if a combination string contains all search elements (order-independent).
    Args:
        combination (str): The combination.
        search_elements (list): The search elements.
    Returns:
        bool: Result of the operation.
    """
    combo_parts = [p.strip() for p in combination.split(',')]
    for se in search_elements:
        found = False
        se_clean = format_element_label(se, False).lower()
        for cp in combo_parts:
            cp_clean = format_element_label(cp, False).lower()
            if se.lower() in cp.lower() or se_clean in cp_clean:
                found = True
                break
        if not found:
            return False
    return True


class HeatmapPlotNode(QObject):
    """Heatmap plot node with multiple sample support."""

    position_changed = Signal(object)
    configuration_changed = Signal()

    DEFAULT_CONFIG = {
        'data_type_display': 'Counts',
        'search_element': '', 'highlight_matches': True,
        'filter_combinations': False,
        'start_range': 1, 'end_range': 10,
        'filter_zeros': True, 'min_particles': 1,
        'show_mass_numbers': True, 'colorscale': 'YlGnBu',
        'show_numbers': True, 'show_colorbar': True,
        'display_mode': 'Individual Subplots',
        'sample_colors': {},
        'font_family': 'Times New Roman', 'font_size': 12,
        'font_bold': False, 'font_italic': False, 'font_color': '#000000',
        # ── Color range ──────────────────────────────────────────────────
        'use_custom_range':  False,
        'vmin':              0.0,
        'vmax':              100.0,
        'log_scale':         False,
        # ── Cell appearance ──────────────────────────────────────────────
        'x_rotation':        0,
        'annotation_fontsize': 0,
        'cell_linewidth':    0.5,
        # ── Export / appearance ──────────────────────────────────────────
        'bg_color':          '#FFFFFF',
        'export_format':     'svg',
        'export_dpi':        300,
        'use_custom_figsize': False,
        'figsize_w':         16.0,
        'figsize_h':         10.0,
    }

    def __init__(self, parent_window=None):
        """
        Args:
            parent_window (Any): The parent window.
        """
        super().__init__()
        self.title = "Element Heatmap"
        self.node_type = "heatmap_plot"
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
        dlg = HeatmapDisplayDialog(self, parent_window)
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

    def extract_combinations_data(self):
        """
        Returns:
            None
        """
        if not self.input_data:
            return None
        dt = self.config.get('data_type_display', 'Counts')
        dk = DATA_KEY_MAPPING.get(dt, 'elements')
        itype = self.input_data.get('type')

        if itype == 'sample_data':
            return self._extract_single(dk)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(dk)
        return None

    def _extract_single(self, data_key):
        """
        Args:
            data_key (Any): The data key.
        Returns:
            object: Result of the operation.
        """
        particles = self.input_data.get('particle_data')
        if not particles:
            return None
        return _build_combinations(particles, data_key)

    def _extract_multi(self, data_key):
        """
        Args:
            data_key (Any): The data key.
        Returns:
            object: Result of the operation.
        """
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
            combos = _build_combinations(plist, data_key)
            if combos:
                result[sn] = combos
        return result or None


def _build_combinations(particles, data_key):
    """Build combination dict from a list of particle dicts.
    Args:
        particles (Any): The particles.
        data_key (Any): The data key.
    Returns:
        object: Result of the operation.
    """
    try:
        combos = {}
        for particle in particles:
            d = particle.get(data_key, {})
            elems = []
            vals = {}
            for name, v in d.items():
                if data_key == 'elements':
                    if v > 0:
                        elems.append(name)
                        vals[name] = v
                else:
                    if v > 0 and not np.isnan(v):
                        elems.append(name)
                        vals[name] = v

            if not elems:
                continue

            key = ', '.join(sort_elements_by_mass(elems))
            if key not in combos:
                combos[key] = {'count': 0, 'particle_count': 0, 'total_values': {}}
            combos[key]['count'] += 1
            combos[key]['particle_count'] += 1
            for e, v in vals.items():
                combos[key]['total_values'].setdefault(e, []).append(v)

        return combos or None
    except Exception as e:
        print(f"Error building combinations: {e}")
        import traceback; traceback.print_exc()
        return None