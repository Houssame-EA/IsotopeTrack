from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QCheckBox, QGroupBox, QPushButton, QLineEdit, QScrollArea,
    QWidget, QMenu, QDialogButtonBox, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QCursor
from matplotlib.figure import Figure
import numpy as np
import math

from results.shared_plot_utils import copy_figure_to_clipboard
from results.shared_plot_utils import (
    DATA_KEY_MAPPING, FontSettingsGroup,
    ExportSettingsGroup, MplDraggableCanvas, get_font_config,
    apply_font_to_matplotlib, apply_font_to_colorbar_standalone,
    get_display_name, download_matplotlib_figure,
    LABEL_MODES, format_element_label, format_combination_label, Renderer, per_ml_factor,
    conc_meta_available, format_per_ml, single_sample_name,
)

from results.utils_sort import (
    sort_elements_by_mass
)
from widget.colors import colorheatmap
import logging
_itk_log = logging.getLogger("IsotopeTrack.results.results_heatmap")


HEATMAP_DATA_TYPES = [
    'Counts', 'Element Mass (fg)', 'Particle Mass (fg)',
    'Element Moles (fmol)', 'Particle Moles (fmol)',
    'Element Mass %', 'Particle Mass %', 'Element Mole %', 'Particle Mole %'
]

DEGREE_SIGN = "\N{DEGREE SIGN}"
HEATMAP_MULTI_DISPLAY_MODES = [
    'Individual Subplots',
    'Side by Side Subplots',
    'Combined Heatmap',
]


def _normalize_heatmap_display_mode(display_mode: str) -> str:
    """Normalize legacy Heatmap display-mode values to supported UI modes.

    Args:
        display_mode (str): Configured Heatmap display mode string.

    Returns:
        str: A supported Heatmap multi-sample display mode.

    Preserved behavior:
        This keeps old saved configs safe by mapping removed or unknown modes
        to the non-lossy default ``Individual Subplots`` without changing any
        heatmap values, aggregation, or color scaling.
    """
    if display_mode in HEATMAP_MULTI_DISPLAY_MODES:
        return display_mode
    if display_mode == 'Comparative View':
        return 'Individual Subplots'
    return 'Individual Subplots'


class HeatmapSettingsDialog(QDialog):
    """Scoped settings dialog for heatmap format/quantity configuration."""

    preview_requested = Signal(dict)

    def __init__(self, config: dict, is_multi: bool,
                 sample_names: list, parent=None, scope='all', input_data=None):
        super().__init__(parent)
        if scope == 'format':
            self.setWindowTitle("Heatmap plot format settings")
        elif scope == 'quantities':
            self.setWindowTitle("Heatmap plot quantities configuration")
        else:
            self.setWindowTitle("Heatmap Settings")
        self.setMinimumWidth(480)
        self._config = dict(config)
        self._is_multi = is_multi
        self._sample_names = sample_names
        self._scope = scope
        self._input_data = input_data
        self.display_mode = None
        self.data_type = None
        self.y_axis_unit = None
        self.search_edit = None
        self.filter_only_cb = None
        self.filter_exact_cb = None
        self.start_spin = None
        self.end_spin = None
        self.filter_zeros = None
        self.min_particles = None
        self.label_mode_combo = None
        self.show_numbers_cb = None
        self.show_colorbar_cb = None
        self.colorscale = None
        self.log_scale_cb = None
        self.custom_range_cb = None
        self.vmin_spin = None
        self.vmax_spin = None
        self.x_rotation_spin = None
        self.ann_fontsize_spin = None
        self.cell_lw_spin = None
        self._font_group = None
        self._export_grp = None
        self._sample_name_edits = None
        self._build()

    def _sample_name_keys(self) -> list[str]:
        """Return raw sample keys that can be renamed in Heatmap settings.

        Returns:
            list[str]: Canonical sample keys used for display-name overrides.

        Preserved behavior:
            Raw sample keys remain canonical. This helper only determines which
            visible labels can receive display-only rename overrides.
        """
        if self._is_multi:
            return list(self._sample_names)
        single_name = single_sample_name(self._input_data)
        return [single_name] if single_name else []

    def _build(self):
        """Build scoped Heatmap settings controls for the current route.

        Preserved behavior:
            Format and quantity controls stay separated by scope so the Results
            four-button contract remains intact and removed no-op controls do
            not leave stale widget references behind.
        """
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        if self._scope in ('all', 'quantities') and self._is_multi:
            g = QGroupBox("Multiple Sample Display")
            fl = QFormLayout(g)
            self.display_mode = QComboBox()
            self.display_mode.addItems(HEATMAP_MULTI_DISPLAY_MODES)
            self.display_mode.setCurrentText(
                _normalize_heatmap_display_mode(
                    self._config.get('display_mode', 'Individual Subplots')))
            fl.addRow("Display Mode:", self.display_mode)
            layout.addWidget(g)

        if self._scope in ('all', 'quantities'):
            g = QGroupBox("Data Type")
            vl = QVBoxLayout(g)
            self.data_type = QComboBox()
            self.data_type.addItems(HEATMAP_DATA_TYPES)
            self.data_type.setCurrentText(
                self._config.get('data_type_display', 'Counts'))
            vl.addWidget(self.data_type)
            self.y_axis_unit = QComboBox()
            self.y_axis_unit.addItem("Particle", "count")
            self.y_axis_unit.addItem("Particle per mL", "per_ml")
            _cu = self._config.get('y_axis_unit', 'count')
            self.y_axis_unit.setCurrentIndex(1 if _cu == 'per_ml' else 0)
            if not conc_meta_available(getattr(self, '_input_data', None)):
                _ix = self.y_axis_unit.findData('per_ml')
                _it = self.y_axis_unit.model().item(_ix)
                if _it is not None:
                    _it.setEnabled(False)
                if _cu == 'per_ml':
                    self.y_axis_unit.setCurrentIndex(0)
            vl.addWidget(QLabel("Row count unit:"))
            vl.addWidget(self.y_axis_unit)
            layout.addWidget(g)

            g = QGroupBox("Element Search & Filter")
            sl = QVBoxLayout(g)
            row = QHBoxLayout()
            row.addWidget(QLabel("Search:"))
            self.search_edit = QLineEdit(self._config.get('search_element', ''))
            self.search_edit.setPlaceholderText("e.g. Fe, Ti (order doesn't matter)")
            row.addWidget(self.search_edit)
            sl.addLayout(row)
            self.filter_only_cb = QCheckBox("Show selected elements present (partial match)")
            self.filter_only_cb.setChecked(self._config.get('filter_combinations', False))
            sl.addWidget(self.filter_only_cb)
            self.filter_exact_cb = QCheckBox("Show selected elements only (exact match)")
            self.filter_exact_cb.setChecked(self._config.get('filter_exact_match', False))
            sl.addWidget(self.filter_exact_cb)
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
            self.log_scale_cb = QCheckBox()
            self.log_scale_cb.setChecked(self._config.get('log_scale', False))
            fl.addRow("Log scale:", self.log_scale_cb)
            self.min_particles = QSpinBox()
            self.min_particles.setRange(1, 1000)
            self.min_particles.setValue(self._config.get('min_particles', 1))
            fl.addRow("Min particles:", self.min_particles)
            layout.addWidget(g)

        if self._scope in ('all', 'format'):
            g = QGroupBox("Labels")
            fl = QFormLayout(g)
            self.label_mode_combo = QComboBox()
            self.label_mode_combo.addItems(LABEL_MODES)
            self.label_mode_combo.setCurrentText(self._config.get('label_mode', 'Mass + Symbol'))
            fl.addRow("Isotope Label:", self.label_mode_combo)
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
            self.x_rotation_spin.setRange(0, 90)
            self.x_rotation_spin.setSuffix(DEGREE_SIGN)
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

            g = QGroupBox("Cell Statistic")
            fl = QFormLayout(g)
            self.cell_stat_combo = QComboBox()
            self.cell_stat_combo.addItems(CELL_STAT_OPTIONS)
            self.cell_stat_combo.setCurrentText(self._config.get('cell_stat', 'Mean'))
            fl.addRow("Cell value:", self.cell_stat_combo)
            self.cell_spread_combo = QComboBox()
            self.cell_spread_combo.addItems(CELL_SPREAD_OPTIONS)
            self.cell_spread_combo.setCurrentText(
                self._config.get('cell_spread', 'None'))
            fl.addRow("Show spread:", self.cell_spread_combo)
            layout.addWidget(g)

            self._font_group = FontSettingsGroup(self._config)
            layout.addWidget(self._font_group.build())

            self._export_grp = ExportSettingsGroup(self._config)
            layout.addWidget(self._export_grp.build())

            sample_name_keys = self._sample_name_keys()
            if sample_name_keys:
                g = QGroupBox("Sample Names")
                sl_layout = QVBoxLayout(g)
                self._sample_name_edits = {}
                mappings = dict(self._config.get('sample_name_mappings', {}))
                for sample_name in sample_name_keys:
                    row = QHBoxLayout()
                    lbl = QLabel(sample_name[:25] + "…" if len(sample_name) > 25 else sample_name)
                    lbl.setFixedWidth(160)
                    row.addWidget(lbl)
                    edit = QLineEdit(mappings.get(sample_name, sample_name))
                    edit.setFixedWidth(220)
                    row.addWidget(edit)
                    reset = QPushButton("Reset")
                    reset.setFixedHeight(22)
                    reset.clicked.connect(lambda _, key=sample_name: self._sample_name_edits[key].setText(key))
                    row.addWidget(reset)
                    row.addStretch()
                    wrapper = QWidget()
                    wrapper.setLayout(row)
                    sl_layout.addWidget(wrapper)
                    self._sample_name_edits[sample_name] = edit
                layout.addWidget(g)

        layout.addStretch()

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
        outer.addLayout(_btn_row)

    def collect(self) -> dict:
        """Collect Heatmap settings without touching removed or missing widgets.

        Returns:
            dict: Configuration updates for the active settings scope.

        Preserved behavior:
            This stays scope-safe so removing no-op controls such as Heatmap
            sample colors does not leave stale widget accesses or `NoneType`
            errors in format or quantity routes.
        """
        cfg = dict(self._config)
        cfg['data_type_display'] = self.data_type.currentText() if self.data_type else self._config.get('data_type_display', 'Counts')
        if self.y_axis_unit is not None:
            cfg['y_axis_unit'] = self.y_axis_unit.currentData()
        cfg['search_element'] = self.search_edit.text().strip() if self.search_edit else self._config.get('search_element', '')
        cfg['filter_combinations'] = self.filter_only_cb.isChecked() if self.filter_only_cb else self._config.get('filter_combinations', False)
        cfg['filter_exact_match'] = self.filter_exact_cb.isChecked() if self.filter_exact_cb else self._config.get('filter_exact_match', False)
        cfg['start_range'] = self.start_spin.value() if self.start_spin else self._config.get('start_range', 1)
        cfg['end_range'] = self.end_spin.value() if self.end_spin else self._config.get('end_range', 10)
        cfg['filter_zeros'] = self.filter_zeros.isChecked() if self.filter_zeros else self._config.get('filter_zeros', True)
        cfg['min_particles'] = self.min_particles.value() if self.min_particles else self._config.get('min_particles', 1)

        selected_mode = self.label_mode_combo.currentText() if self.label_mode_combo else self._config.get('label_mode', 'Mass + Symbol')
        cfg['label_mode'] = selected_mode

        cfg['show_numbers'] = self.show_numbers_cb.isChecked() if self.show_numbers_cb else self._config.get('show_numbers', True)
        cfg['show_colorbar'] = self.show_colorbar_cb.isChecked() if self.show_colorbar_cb else self._config.get('show_colorbar', True)
        cfg['colorscale'] = self.colorscale.currentText() if self.colorscale else self._config.get('colorscale', 'YlGnBu')
        cfg['log_scale'] = self.log_scale_cb.isChecked() if self.log_scale_cb else self._config.get('log_scale', False)
        cfg['use_custom_range'] = self.custom_range_cb.isChecked() if self.custom_range_cb else self._config.get('use_custom_range', False)
        cfg['vmin'] = self.vmin_spin.value() if self.vmin_spin else self._config.get('vmin', 0.0)
        cfg['vmax'] = self.vmax_spin.value() if self.vmax_spin else self._config.get('vmax', 100.0)
        cfg['x_rotation'] = self.x_rotation_spin.value() if self.x_rotation_spin else self._config.get('x_rotation', 0)
        cfg['annotation_fontsize'] = self.ann_fontsize_spin.value() if self.ann_fontsize_spin else self._config.get('annotation_fontsize', 0)
        cfg['cell_linewidth'] = self.cell_lw_spin.value() if self.cell_lw_spin else self._config.get('cell_linewidth', 0.5)
        cfg['cell_stat'] = (self.cell_stat_combo.currentText()
                            if getattr(self, 'cell_stat_combo', None)
                            else self._config.get('cell_stat', 'Mean'))
        cfg['cell_spread'] = (self.cell_spread_combo.currentText()
                              if getattr(self, 'cell_spread_combo', None)
                              else self._config.get('cell_spread', 'None'))

        if self._font_group is not None:
            cfg.update(self._font_group.collect())
        if self._export_grp is not None:
            cfg.update(self._export_grp.collect())

        if self._is_multi:
            cfg['display_mode'] = (
                _normalize_heatmap_display_mode(self.display_mode.currentText())
                if self.display_mode else
                _normalize_heatmap_display_mode(self._config.get('display_mode', 'Individual Subplots'))
            )
        if self._sample_name_edits is not None:
            mappings = {}
            for sample_name, edit in self._sample_name_edits.items():
                value = edit.text().strip()
                if value and value != sample_name:
                    mappings[sample_name] = value
            cfg['sample_name_mappings'] = mappings
        return cfg


class HeatmapDisplayDialog(QDialog):
    """
    Full-figure heatmap dialog with right-click context menu.
    """

    def __init__(self, heatmap_node, parent_window=None):
        super().__init__(parent_window)
        self.node = heatmap_node
        self.parent_window = parent_window
        self.setWindowTitle("Element Combination Heatmap")
        self.setMinimumSize(1000, 700)
        self._setup_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _is_multi(self) -> bool:
        return bool(self.node.input_data and
                    self.node.input_data.get('type') == 'multiple_sample_data')

    def _sample_names(self) -> list:
        if self._is_multi():
            return self.node.input_data.get('sample_names', [])
        return []

    def _single_sample_name(self) -> str:
        """Return the canonical single-sample key when one is available.

        Returns:
            str: Raw single-sample name, or an empty string when unavailable.
        """
        return single_sample_name(self.node.input_data)

    def _single_sample_title(self, cfg: dict) -> str:
        """Return the visible single-sample Heatmap title.

        Args:
            cfg (dict): Active Heatmap configuration.

        Returns:
            str: Title that includes the display sample name when a reliable
                canonical single-sample key is available.
        """
        sample_name = self._single_sample_name()
        if sample_name:
            return f"{get_display_name(sample_name, cfg)} - Element Combinations"
        return "Element Combinations"

    # ── UI ──────────────────────────────────

    def _setup_ui(self):
        self._axes_row_combos = {}
        self._axes_sample_map = {}
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
        btn_fmt = QPushButton("Plot format settings")
        btn_fmt.clicked.connect(self._open_plot_format_settings)
        btn_qty = QPushButton("Configure plot quantities")
        btn_qty.clicked.connect(self._open_configure_plot_quantities)
        btn_r = QPushButton("Reset layout")
        btn_r.setToolTip("Reset all subplot positions to auto layout\n(or middle-click on the figure)")
        btn_r.clicked.connect(self._reset_layout)
        btn_e = QPushButton("Export figure")
        btn_e.clicked.connect(self._export_figure)
        bb.addWidget(btn_fmt)
        bb.addWidget(btn_qty)
        bb.addWidget(btn_r)
        bb.addWidget(btn_e)
        layout.addLayout(bb)

    # ── Context menu ────────────────────────

    def _show_context_menu(self, pos):
        """Build a minimal Heatmap right-click menu with quick controls only.

        The context menu is intentionally limited to `Quick Toggles` and
        `Isotope Label`. Full format/quantity configuration, reset, and export
        are intentionally delegated to the four bottom buttons.

        Preserved behavior:
        - Toggle and label-mode actions still update the same config keys.
        - Heatmap calculations and search-safe label behavior remain unchanged.
        """
        cfg = self.node.config
        hovered_sample = self._axes_sample_at(pos)
        menu = QMenu(self)

        toggle_menu = menu.addMenu("Quick Toggles")
        self._add_toggle(toggle_menu, "Show Numbers", 'show_numbers')
        self._add_toggle(toggle_menu, "Show Colorbar", 'show_colorbar')
        self._add_toggle(toggle_menu, "Filter Zeros", 'filter_zeros')
        self._add_toggle(toggle_menu, "Show Selected Elements Present (Partial Match)", 'filter_combinations')
        self._add_toggle(toggle_menu, "Show Selected Elements Only (Exact Match)", 'filter_exact_match')
        self._add_toggle(toggle_menu, "Log Scale", 'log_scale')
        self._add_toggle(toggle_menu, "Custom Color Range", 'use_custom_range')

        row_combo = self._get_row_at(pos)
        if row_combo is not None:
            highlighted = set(cfg.get('highlighted_combos', []))
            menu.addSeparator()
            if row_combo in highlighted:
                a = menu.addAction("Remove highlight from this row")
                a.triggered.connect(lambda _, rc=row_combo: self._toggle_row_highlight(rc, False))
            else:
                a = menu.addAction("Highlight this row")
                a.triggered.connect(lambda _, rc=row_combo: self._toggle_row_highlight(rc, True))

        if cfg.get('highlighted_combos', []):
            if row_combo is None:
                menu.addSeparator()
            a2 = menu.addAction("Clear all row highlights")
            a2.triggered.connect(lambda _: self._clear_all_highlights())

        lm_menu = menu.addMenu("Isotope Label")
        current_mode = cfg.get('label_mode', 'Mass + Symbol')
        for mode in LABEL_MODES:
            a = lm_menu.addAction(mode)
            a.setCheckable(True)
            a.setChecked(mode == current_mode)
            a.triggered.connect(lambda _, m=mode: self._set_label_mode(m))

        dm = _normalize_heatmap_display_mode(
            cfg.get('display_mode', 'Individual Subplots'))
        can_export_sub = (self._is_multi()
                         and dm in ('Individual Subplots', 'Side by Side Subplots')
                         and hovered_sample is not None)
        menu.addSeparator()
        if can_export_sub:
            exp_act = menu.addAction("Export this subplot...")
            exp_act.triggered.connect(
                lambda *_: self._export_subplot(hovered_sample))
        else:
            exp_act = menu.addAction("Export this subplot... (unavailable here)")
            exp_act.setEnabled(False)
            exp_act.setToolTip(
                "Right-click over a subplot panel in Individual or Side by Side mode.")

        menu.addSeparator()
        act_copy_fig = menu.addAction("Copy figure")
        act_copy_fig.triggered.connect(
            lambda: copy_figure_to_clipboard(self.canvas))
        menu.exec(QCursor.pos())
    def _get_row_at(self, widget_pos):
        """Return the raw combo key for the heatmap row at widget_pos, or None."""
        canvas_h = self.canvas.height()
        mpl_x = float(widget_pos.x())
        mpl_y = float(canvas_h - widget_pos.y())
        for ax in self.figure.get_axes():
            row_combos = self._axes_row_combos.get(id(ax))
            if not row_combos:
                continue
            try:
                inv = ax.transData.inverted()
                data_x, data_y = inv.transform((mpl_x, mpl_y))
                row_idx = int(round(data_y))
                xlim = ax.get_xlim(); ylim = ax.get_ylim()
                x_min = min(xlim); x_max = max(xlim)
                y_min = min(ylim); y_max = max(ylim)
                if (x_min - 0.5 <= data_x <= x_max + 0.5
                        and y_min - 0.5 <= data_y <= y_max + 0.5
                        and 0 <= row_idx < len(row_combos)):
                    return row_combos[row_idx]
            except Exception:
                pass
        return None

    def _axes_sample_at(self, widget_pos):
        """Return the sample name for the heatmap axes under widget_pos, or None."""
        w = self.canvas.width()
        h = self.canvas.height()
        if w <= 0 or h <= 0:
            return None
        x_norm = widget_pos.x() / w
        y_norm = 1.0 - widget_pos.y() / h
        for ax in self.figure.get_axes():
            sn = self._axes_sample_map.get(id(ax))
            if sn is None:
                continue
            try:
                if ax.get_position().contains(x_norm, y_norm):
                    return sn
            except Exception:
                pass
        return None

    def _toggle_row_highlight(self, combo_key, add):
        highlighted = set(self.node.config.get('highlighted_combos', []))
        if add:
            highlighted.add(combo_key)
        else:
            highlighted.discard(combo_key)
        self.node.config['highlighted_combos'] = list(highlighted)
        self._refresh()

    def _clear_all_highlights(self):
        self.node.config['highlighted_combos'] = []
        self._refresh()

    def _add_toggle(self, menu, label, key):
        a = menu.addAction(label)
        a.setCheckable(True)
        a.setChecked(self.node.config.get(key, False))
        a.triggered.connect(lambda checked, k=key: self._toggle(k, checked))

    def _toggle(self, key, value):
        self.node.config[key] = value
        self._refresh()

    def _set_label_mode(self, mode):
        self.node.config['label_mode'] = mode
        self._refresh()

    def _set_and_refresh(self, key, value):
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
            self.node.config, self._is_multi(), self._sample_names(), self,
            input_data=self.node.input_data)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_plot_format_settings(self):
        _snap = dict(self.node.config)
        dlg = HeatmapSettingsDialog(
            self.node.config, self._is_multi(), self._sample_names(), self, scope='format',
            input_data=self.node.input_data)
        dlg.preview_requested.connect(lambda cfg: (self.node.config.update(cfg), self._refresh()))
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()
        else:
            self.node.config.clear()
            self.node.config.update(_snap)
            self._refresh()

    def _open_configure_plot_quantities(self):
        _snap = dict(self.node.config)
        dlg = HeatmapSettingsDialog(
            self.node.config, self._is_multi(), self._sample_names(), self, scope='quantities',
            input_data=self.node.input_data)
        dlg.preview_requested.connect(lambda cfg: (self.node.config.update(cfg), self._refresh()))
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()
        else:
            self.node.config.clear()
            self.node.config.update(_snap)
            self._refresh()

    def _reset_layout(self):
        self.canvas.reset_layout()

    def _export_figure(self):
        download_matplotlib_figure(self.figure, self, "heatmap")

    def _export_subplot(self, sample_name):
        """Export one heatmap subplot as a standalone single-panel figure."""
        data = self.node.extract_combinations_data()
        if not data or sample_name not in data:
            return
        cfg = self.node.config
        title = get_display_name(sample_name, cfg)
        fig = Figure(tight_layout=True)
        ax = fig.add_subplot(111)
        draw_combinations_heatmap(ax, fig, data[sample_name], cfg,
                                  title=title, is_multi=False)
        apply_font_to_matplotlib(ax, cfg)
        safe = ''.join(c if c.isalnum() or c in ('_', '-') else '_'
                       for c in title).strip('_') or 'subplot'
        download_matplotlib_figure(fig, self, f"heatmap_{safe}")

    def _refresh(self):
        """Rebuild the Heatmap figure from current config and extracted data.

        Preserved behavior:
            Heatmap values, aggregation, normalization, and colormap handling
            remain unchanged. This refresh only normalizes legacy display modes
            and reapplies display-only sample names in rendered titles.
        """
        try:
            self._axes_row_combos = {}
            self._axes_sample_map = {}
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
                    dm = _normalize_heatmap_display_mode(
                        cfg.get('display_mode', 'Individual Subplots'))
                    cfg['display_mode'] = dm
                    self._draw_multi(data, cfg, dm)
                else:
                    ax = self.figure.add_subplot(111)
                    self._draw_heatmap(ax, data, cfg, self._single_sample_title(cfg))
                    apply_font_to_matplotlib(ax, cfg)

            self.figure.tight_layout()
            self.canvas.draw()
            self.canvas.snapshot_positions()
        except Exception as e:
            _itk_log.exception("Handled exception in _refresh")
            _itk_log.error(f"Error refreshing heatmap: {e}")
            import traceback; traceback.print_exc()

    # ── Multi-sample dispatch ───────────────

    def _draw_multi(self, data, cfg, display_mode):
        """Draw the active multi-sample Heatmap layout.

        Preserved behavior:
            This changes only panel layout and display-only sample titles.
            Heatmap values, aggregation, color scaling, and colormap behavior
            remain unchanged.
        """
        display_mode = _normalize_heatmap_display_mode(display_mode)
        names = list(data.keys())
        n = len(names)

        if display_mode == 'Individual Subplots':
            cols = min(2, n)
            rows = math.ceil(n / cols)
            for i, sn in enumerate(names):
                ax = self.figure.add_subplot(rows, cols, i + 1)
                self._axes_sample_map[id(ax)] = sn
                self._draw_heatmap(ax, data[sn], cfg, get_display_name(sn, cfg))
                apply_font_to_matplotlib(ax, cfg)

        elif display_mode == 'Side by Side Subplots':
            for i, sn in enumerate(names):
                ax = self.figure.add_subplot(1, n, i + 1)
                self._axes_sample_map[id(ax)] = sn
                self._draw_heatmap(ax, data[sn], cfg, get_display_name(sn, cfg))
                apply_font_to_matplotlib(ax, cfg)

        else:
            combined = self._combine_data(data)
            ax = self.figure.add_subplot(111)
            self._draw_heatmap(ax, combined, cfg,
                               f"Combined ({len(data)} samples)")
            apply_font_to_matplotlib(ax, cfg)

    @staticmethod
    def _combine_data(data):
        combined = {}
        for sample_data in data.values():
            for combo, d in sample_data.items():
                if combo not in combined:
                    combined[combo] = {
                        'count': 0, 'total_values': {}, 'particle_count': 0,
                        'pml': 0.0}
                combined[combo]['count'] += d['count']
                combined[combo]['particle_count'] += d['particle_count']
                combined[combo]['pml'] += d.get('pml', 0.0)
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
        row_combos = draw_combinations_heatmap(
            ax, self.figure, sample_data, cfg, title=title,
            is_multi=self._is_multi(),
        )
        if row_combos is not None:
            self._axes_row_combos[id(ax)] = row_combos


def _combo_matches(combination: str, search_elements: list) -> bool:
    """Check if a combination string contains all search elements (order-independent)."""
    combo_parts = [p.strip() for p in combination.split(',')]
    for se in search_elements:
        found = False
        se_clean = format_element_label(se, 'Symbol', Renderer.MATHTEXT).lower()
        for cp in combo_parts:
            cp_clean = format_element_label(cp, 'Symbol', Renderer.MATHTEXT).lower()
            if se.lower() in cp.lower() or se_clean in cp_clean:
                found = True
                break
        if not found:
            return False
    return True


def _combo_exact_matches(combination: str, search_elements: list) -> bool:
    """Check if a combination has exactly the search elements — no more, no less."""
    combo_parts = [p.strip() for p in combination.split(',')]
    if len(combo_parts) != len(search_elements):
        return False
    return _combo_matches(combination, search_elements)


def _mode_estimate(arr):
    """Estimate the mode of continuous values from the densest histogram bin."""
    if arr.size == 1:
        return float(arr[0])
    try:
        bins = min(50, max(5, int(np.sqrt(arr.size))))
        counts, edges = np.histogram(arr, bins=bins)
        k = int(np.argmax(counts))
        return float((edges[k] + edges[k + 1]) / 2.0)
    except Exception:
        return float(np.mean(arr))


CELL_STAT_OPTIONS = ['Mean', 'Median', 'Mode', 'Geometric Mean']


def _cell_center(vals, stat):
    """Central value for one heatmap cell: Mean, Median, Mode, or Geo. Mean."""
    arr = np.asarray(vals, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return 0.0
    if stat == 'Median':
        return float(np.median(arr))
    if stat == 'Mode':
        return _mode_estimate(arr)
    if stat.startswith('Geo'):
        pos = arr[arr > 0]
        return float(np.exp(np.mean(np.log(pos)))) if pos.size else 0.0
    return float(np.mean(arr))


CELL_SPREAD_OPTIONS = ['None', 'SD', 'SEM', 'IQR (Q1–Q3)', 'Min–Max', 'CV %']


def _cell_spread_value(vals, spread):
    """Secondary value shown after a cell centre.

    Returns a scalar (rendered as ``± x``), a ``(low, high)`` tuple (rendered as
    ``(low–high)``), a ``('%', cv)`` marker for coefficient of variation, or
    None. Supported: SD, SEM, IQR (Q1–Q3), Min–Max, CV %.
    """
    if spread in (None, 'None', ''):
        return None
    arr = np.asarray(vals, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return None
    if spread == 'SD':
        return float(np.std(arr))
    if spread == 'SEM':
        return float(np.std(arr) / np.sqrt(arr.size))
    if spread.startswith('IQR'):
        return (float(np.percentile(arr, 25)), float(np.percentile(arr, 75)))
    if spread.startswith('Min'):
        return (float(np.min(arr)), float(np.max(arr)))
    if spread.startswith('CV'):
        m = float(np.mean(arr))
        return ('%', float(np.std(arr) / m * 100.0)) if m else None
    return None


def _fmt_cell_number(v, is_pct):
    """Format one numeric cell value with the heatmap's standard precision."""
    if is_pct:
        return f'{v:.1f}%'
    if v >= 1000:
        return f'{v:.0f}'
    if v >= 1:
        return f'{v:.1f}'
    return f'{v:.2f}'


def draw_combinations_heatmap(ax, fig, sample_data, cfg, title='',
                             is_multi=False):
    """Draw a combinations heatmap onto an arbitrary axes/figure.

    This is the standalone, ``self``-free version of
    ``HeatmapDisplayDialog._draw_heatmap``. It's used by other tabs (e.g. the
    clustering Overview tab) that want the *exact same* heatmap rendering
    without instantiating a HeatmapDisplayDialog.

    Args:
        ax: Target matplotlib Axes.
        fig: The Figure that owns ``ax`` (needed to attach the colorbar).
        sample_data (dict): ``{combination_label: {'particle_count': int,
            'total_values': {element: [values...]}}}``. This is the shape the
            Heatmap tab builds internally and the clustering Overview tab
            synthesises from per-cluster characterisation.
        cfg (dict): Display configuration. Honours the same keys as the
        Heatmap tab: ``data_type_display``, ``colorscale``,
        ``show_numbers``, ``show_colorbar``, ``log_scale``,
        ``use_custom_range``/``vmin``/``vmax``, ``start_range``,
        ``end_range``, ``min_particles``, ``label_mode``,
        ``search_element``, ``highlight_matches``,
        ``filter_combinations``, ``x_rotation``, ``annotation_fontsize``,
        ``cell_linewidth``.
        title (str): Title to render above the heatmap when provided.
        is_multi (bool): Whether this is a multi-sample panel. This still
            controls compatibility with existing multi-sample rendering paths,
            but a non-empty title is now honored in single-sample mode too.
    """
    if not sample_data:
        ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                transform=ax.transAxes, color='gray')
        return

    dt = cfg.get('data_type_display', 'Counts')
    search_text = cfg.get('search_element', '').strip()
    highlighted_combos = set(cfg.get('highlighted_combos', []))
    filter_combos = cfg.get('filter_combinations', False)
    filter_exact = cfg.get('filter_exact_match', False)
    start = cfg.get('start_range', 1)
    end = cfg.get('end_range', 10)
    min_p = cfg.get('min_particles', 1)
    label_mode = cfg.get('label_mode', 'Mass + Symbol')
    import matplotlib.cm as _cm
    cscale = cfg.get('colorscale', 'YlGnBu')
    if cscale not in _cm._colormaps:
        cscale = 'YlGnBu'
    show_nums = cfg.get('show_numbers', True)
    show_cbar = cfg.get('show_colorbar', True)
    log_scale = cfg.get('log_scale', False)
    use_custom_range = cfg.get('use_custom_range', False)
    vmin_cfg = cfg.get('vmin', None) if use_custom_range else None
    vmax_cfg = cfg.get('vmax', None) if use_custom_range else None
    x_rotation = cfg.get('x_rotation', 0)
    ann_fs = cfg.get('annotation_fontsize', 0) or None
    cell_lw = cfg.get('cell_linewidth', 0.5)
    cell_stat = cfg.get('cell_stat', 'Mean')
    cell_spread = cfg.get('cell_spread', 'None')
    fc = get_font_config(cfg)

    search_elems = []
    if search_text:
        search_elems = [e.strip() for e in search_text.replace(',', ' ').split()
                        if e.strip()]

    sorted_combos = sorted(sample_data.items(),
                           key=lambda x: x[1]['particle_count'], reverse=True)

    if search_elems and filter_exact:
        sorted_combos = [(c, d) for c, d in sorted_combos
                         if _combo_exact_matches(c, search_elems)]
    elif search_elems and filter_combos:
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
    spread_matrix = []

    for combo, d in selected:
        count = d['particle_count']
        fmt = format_combination_label(combo, label_mode, Renderer.MATHTEXT, cfg)
        if cfg.get('y_axis_unit', 'count') == 'per_ml' and d.get('pml', 0.0) > 0:
            labels.append(f"{fmt} ({format_per_ml(d['pml'], Renderer.MATHTEXT, cfg)})")
        else:
            labels.append(f"{fmt} ({count})")

        is_pct = dt.endswith('%')
        total_sum = 0
        if is_pct:
            for vals in d['total_values'].values():
                if vals:
                    total_sum += np.sum(vals)

        row = []
        spread_row = []
        for elem in all_elems:
            vals = d['total_values'].get(elem, [])
            if not vals:
                row.append(0)
                spread_row.append(None)
            elif is_pct:
                row.append((np.sum(vals) / total_sum * 100) if total_sum > 0 else 0)
                spread_row.append(None)
            else:
                row.append(_cell_center(vals, cell_stat))
                spread_row.append(_cell_spread_value(vals, cell_spread))
        matrix.append(row)
        spread_matrix.append(spread_row)

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

    x_labels = [format_element_label(e, label_mode, Renderer.MATHTEXT, cfg)
                for e in all_elems]
    fw = 'bold' if fc['bold'] else 'normal'
    fst = 'italic' if fc['italic'] else 'normal'
    ax.set_xticks(range(len(x_labels)))
    ax.set_xticklabels(x_labels, rotation=x_rotation,
                       ha='right' if x_rotation > 0 else 'center',
                       fontsize=fc['size'], fontfamily=fc['family'],
                       fontweight=fw, fontstyle=fst, color=fc['color'])
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=fc['size'], fontfamily=fc['family'],
                       fontweight=fw, fontstyle=fst, color=fc['color'])

    if highlighted_combos:
        combo_keys_list = [c for c, _ in selected]
        for i, ck in enumerate(combo_keys_list):
            if ck in highlighted_combos:
                ax.axhline(y=i + 0.35, color='black', linewidth=2, alpha=0.9,
                           xmin=-0.15, xmax=0, clip_on=False)
                ax.get_yticklabels()[i].set_weight('bold')

    if title:
        ax.set_title(title, fontsize=fc['size'] + 2, fontfamily=fc['family'],
                     fontweight=fw, fontstyle=fst, color=fc['color'], pad=20)

    if show_cbar:
        cbar = fig.colorbar(im, ax=ax, shrink=0.8)
        cbar_label = dt
        if log_scale:
            cbar_label = f"log10({dt})"
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
                    txt = _fmt_cell_number(v_orig, is_pct)
                    sp = spread_matrix[i][j]
                    if sp is not None and not is_pct:
                        if isinstance(sp, tuple) and sp[0] == '%':
                            txt = f'{txt} ({sp[1]:.0f}%)'
                        elif isinstance(sp, tuple):
                            txt = (f'{txt} ({_fmt_cell_number(sp[0], False)}'
                                   f'–{_fmt_cell_number(sp[1], False)})')
                        else:
                            txt = f'{txt} ± {_fmt_cell_number(sp, False)}'
                    ax.text(j, i, txt, ha='center', va='center',
                            color=tc, fontsize=eff_fs,
                            fontfamily=fc['family'], weight=weight,
                            style='italic' if fc['italic'] else 'normal')

    return [c for c, _ in selected]


class HeatmapPlotNode(QObject):
    """Heatmap plot node with multiple sample support."""

    position_changed = Signal(object)
    configuration_changed = Signal()

    DEFAULT_CONFIG = {
        'data_type_display': 'Counts',
        'y_axis_unit': 'count',
        'search_element': '', 'highlight_matches': True,
        'filter_combinations': False,
        'filter_exact_match': False,
        'highlighted_combos': [],
        'start_range': 1, 'end_range': 10,
        'filter_zeros': True, 'min_particles': 1,
        'label_mode': 'Mass + Symbol',
        'colorscale': 'YlGnBu',
        'show_numbers': True, 'show_colorbar': True,
        'display_mode': 'Individual Subplots',
        'sample_name_mappings': {},
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
        'cell_stat':         'Mean',
        'cell_spread':       'None',
        # ── Export / appearance ──────────────────────────────────────────
        'bg_color':          '#FFFFFF',
        'export_format':     'svg',
        'export_dpi':        300,
        'use_custom_figsize': False,
        'figsize_w':         16.0,
        'figsize_h':         10.0,
    }

    def __init__(self, parent_window=None):
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
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        """Open this node's figure, reusing one persistent (hide-on-close) window."""
        from results.shared_plot_utils import show_persistent_figure
        return show_persistent_figure(
            self, lambda: HeatmapDisplayDialog(self, parent_window))

    def process_data(self, input_data):
        if not input_data:
            return
        self.input_data = input_data
        self.configuration_changed.emit()

    def extract_combinations_data(self):
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
        particles = self.input_data.get('particle_data')
        if not particles:
            return None
        sname = self.input_data.get('sample_name', 'Sample')
        return _build_combinations(particles, data_key,
                                   per_ml_factor(self.input_data, sname))

    def _extract_multi(self, data_key):
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
            combos = _build_combinations(plist, data_key,
                                         per_ml_factor(self.input_data, sn))
            if combos:
                result[sn] = combos
        return result or None


def _build_combinations(particles, data_key, pml_factor=0.0):
    """Build combination dict from a list of particle dicts.
    Args:
        particles (Any): The particles.
        data_key (Any): The data key.
        pml_factor (float): Multiplier converting a particle count to
            particles per mL for the sample these particles belong to.
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
                combos[key] = {'count': 0, 'particle_count': 0, 'pml': 0.0,
                               'total_values': {}}
            combos[key]['count'] += 1
            combos[key]['particle_count'] += 1
            combos[key]['pml'] += pml_factor
            for e, v in vals.items():
                combos[key]['total_values'].setdefault(e, []).append(v)

        return combos or None
    except Exception as e:
        _itk_log.exception("Handled exception in _build_combinations")
        _itk_log.error(f"Error building combinations: {e}")
        import traceback; traceback.print_exc()
        return None
