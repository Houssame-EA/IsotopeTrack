from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QCheckBox, QGroupBox, QPushButton, QLineEdit, QScrollArea,
    QWidget, QMenu, QDialogButtonBox, QInputDialog, QColorDialog
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QCursor, QColor
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

DEFAULT_UNDERLINE_COLOR = '#000000'

#: Config key holding which classifier group PANELS role shows (multi-sample
#: only -- single-sample PANELS shows every group at once, no selection).
PANEL_GROUP_CONFIG_KEY = 'classifier_panel_group'

#: Current config key holding manual per-row underline colors.
UNDERLINE_CONFIG_KEY = 'underlined_combos'

#: The pre-2026-08-25 name for the same thing, back when this feature was
#: called "highlight". Renamed to "underline" because that is what it
#: actually draws (a colored bar under the row label), but saved projects
#: still carry the old key -- always read through
#: :func:`_read_underlined_combos` so their underlines survive a load.
LEGACY_UNDERLINE_CONFIG_KEY = 'highlighted_combos'


def _normalize_underlined_combos(raw):
    """Return ``{combo_key: color_or_colors}`` from either the current dict
    format or the legacy list format (list of combo keys, all rendered
    black)."""
    if isinstance(raw, dict):
        return dict(raw)
    return {k: DEFAULT_UNDERLINE_COLOR for k in (raw or [])}


def _read_underlined_combos(cfg):
    """Manual per-row underline overrides from a config, honoring the
    pre-rename key so saved projects don't silently lose their underlines.

    Args:
        cfg (dict): A heatmap node config.

    Returns:
        dict: ``{combo_key: color_or_colors}``. The current key wins when
        both are somehow present (a project saved after the rename, then
        opened by an older build, then saved again).
    """
    if UNDERLINE_CONFIG_KEY in (cfg or {}):
        return _normalize_underlined_combos(cfg.get(UNDERLINE_CONFIG_KEY))
    return _normalize_underlined_combos((cfg or {}).get(LEGACY_UNDERLINE_CONFIG_KEY, {}))


def _write_underlined_combos(cfg, value):
    """Store manual underline overrides under the current key, clearing the
    legacy one so a migrated project doesn't keep two diverging copies."""
    cfg[UNDERLINE_CONFIG_KEY] = value
    cfg.pop(LEGACY_UNDERLINE_CONFIG_KEY, None)


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
        # Declared here like every other widget so a scope that doesn't build
        # them still has a real attribute to test -- collect() previously
        # relied on getattr() defaults to cover the gap.
        self.cell_stat_combo = None
        self.cell_spread_combo = None
        self._font_group = None
        self._export_grp = None
        self._sample_name_edits = None
        self._classifier_group = None
        self.denominator_combo = None
        self.show_expression_cb = None
        self.panel_group_combo = None
        self._display_mode_note = None
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

        if self._scope in ('all', 'quantities'):
            from results.shared_plot_utils import ClassifierViewGroup
            from results import classifier_view as cv
            self._classifier_group = ClassifierViewGroup(
                self._config, self._input_data, cv.ARITY_HEATMAP)
            layout.addWidget(self._classifier_group.build())

            if self._classifier_group._applicable:
                g = QGroupBox("Group Cell Denominator")
                vl = QVBoxLayout(g)
                self.denominator_combo = QComboBox()
                for denom in (cv.DENOMINATOR_WHOLE_GROUP, cv.DENOMINATOR_DETECTED_ONLY):
                    self.denominator_combo.addItem(cv.DENOMINATOR_LABELS.get(denom, denom), denom)
                current_denom = cv.effective_denominator(self._config, self._input_data)
                d_idx = self.denominator_combo.findData(current_denom)
                if d_idx >= 0:
                    self.denominator_combo.setCurrentIndex(d_idx)
                vl.addWidget(self.denominator_combo)
                layout.addWidget(g)

                role_combo = self._classifier_group.role_combo

                def _sync_denominator_enabled():
                    """Only meaningful under GROUPS: every other role either
                    shows real particles/isotopes directly (PANELS/COLORS/OFF)
                    or has no per-group value list to take a denominator over.
                    """
                    is_groups = role_combo.currentData() == cv.ROLE_SERIES
                    self.denominator_combo.setEnabled(is_groups)
                    self.denominator_combo.setToolTip(
                        "" if is_groups else
                        "Only applies under GROUPS -- every other role "
                        "already shows real particles/isotopes directly, "
                        "with no per-group cell value for this to affect.")
                if role_combo is not None:
                    role_combo.currentIndexChanged.connect(_sync_denominator_enabled)
                    _sync_denominator_enabled()

                # PANELS group selector -- multi-sample only. Single-sample
                # PANELS shows every group at once, so there is nothing to
                # select between there.
                if self._is_multi:
                    groups = list(cv.bucket_registry(self._input_data).keys())
                    g = QGroupBox("Panel Group")
                    vl = QVBoxLayout(g)
                    self.panel_group_combo = QComboBox()
                    for lbl in groups:
                        self.panel_group_combo.addItem(lbl, lbl)
                    stored_group = self._config.get(PANEL_GROUP_CONFIG_KEY)
                    g_idx = self.panel_group_combo.findData(stored_group)
                    if g_idx >= 0:
                        self.panel_group_combo.setCurrentIndex(g_idx)
                    vl.addWidget(QLabel(
                        "Which classifier group to show, one subplot per sample:"))
                    vl.addWidget(self.panel_group_combo)
                    layout.addWidget(g)

                    def _sync_panel_group_enabled():
                        """PANELS-only: every other role plots all particles
                        together rather than one group at a time."""
                        is_panels = role_combo.currentData() == cv.ROLE_FACET
                        self.panel_group_combo.setEnabled(is_panels)
                        self.panel_group_combo.setToolTip(
                            "" if is_panels else
                            "Only applies under PANELS -- other roles don't "
                            "show one classifier group at a time.")
                    if role_combo is not None:
                        role_combo.currentIndexChanged.connect(_sync_panel_group_enabled)
                        _sync_panel_group_enabled()

        if self._scope in ('all', 'quantities') and self._is_multi:
            g = QGroupBox("Multiple Sample Display")
            fl = QFormLayout(g)
            self.display_mode = QComboBox()
            self.display_mode.addItems(HEATMAP_MULTI_DISPLAY_MODES)
            self.display_mode.setCurrentText(
                _normalize_heatmap_display_mode(
                    self._config.get('display_mode', 'Individual Subplots')))
            fl.addRow("Display Mode:", self.display_mode)
            self._display_mode_note = QLabel(
                "Unavailable under PANELS — that role already defines its own "
                "layout (one subplot per sample, for the selected group).")
            self._display_mode_note.setWordWrap(True)
            self._display_mode_note.setStyleSheet("color:#B45309; font-size:11px;")
            self._display_mode_note.setVisible(False)
            fl.addRow(self._display_mode_note)
            layout.addWidget(g)

            # PANELS dictates its own layout, so these modes have nothing to
            # act on -- disabled with a visible reason rather than silently
            # ignored (same convention as the role picker's disabled entries).
            if self._classifier_group is not None and self._classifier_group.role_combo is not None:
                from results import classifier_view as cv
                _role_combo = self._classifier_group.role_combo

                def _sync_display_mode_enabled():
                    is_panels = _role_combo.currentData() == cv.ROLE_FACET
                    self.display_mode.setEnabled(not is_panels)
                    self._display_mode_note.setVisible(is_panels)
                _role_combo.currentIndexChanged.connect(_sync_display_mode_enabled)
                _sync_display_mode_enabled()

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

            # Cell Statistic belongs to QUANTITIES, not format: these two
            # choose WHAT NUMBER each cell reports (which central statistic
            # over the cell's value list, and which spread to append), not
            # how it is drawn. Moved out of the format scope 2026-08-26 --
            # it sat there historically, alongside the genuinely cosmetic
            # "Cell Appearance" group it is easy to confuse it with.
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

            from results import classifier_view as cv
            if cv.is_classifier_stream(self._input_data):
                g = QGroupBox("Classifier Group Labels")
                vl = QVBoxLayout(g)
                self.show_expression_cb = QCheckBox(
                    "Show expression next to group label")
                self.show_expression_cb.setChecked(
                    self._config.get('show_group_expression', False))
                self.show_expression_cb.setToolTip(
                    "GROUPS role only. Unclassified has no expression, so "
                    "nothing is added to its label either way.")
                vl.addWidget(self.show_expression_cb)
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
        if self._classifier_group is not None:
            cfg.update(self._classifier_group.collect())
        if self.denominator_combo is not None:
            from results import classifier_view as cv
            cfg[cv.DENOMINATOR_CONFIG_KEY] = self.denominator_combo.currentData()
        if self.show_expression_cb is not None:
            cfg['show_group_expression'] = self.show_expression_cb.isChecked()
        if self.panel_group_combo is not None and self.panel_group_combo.count():
            cfg[PANEL_GROUP_CONFIG_KEY] = self.panel_group_combo.currentData()
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
        underlined = _read_underlined_combos(cfg)
        role = self.node.classifier_role()
        from results import classifier_view as cv
        is_colors_role = role == cv.ROLE_ENCODE
        if row_combo is not None:
            menu.addSeparator()
            if row_combo in underlined:
                a = menu.addAction("Revert to classifier coloring" if is_colors_role
                                   else "Remove underline from this row")
                a.triggered.connect(lambda _, rc=row_combo: self._toggle_row_underline(rc, False))
                a3 = menu.addAction("Change underline color...")
                a3.triggered.connect(lambda _, rc=row_combo: self._change_row_underline_color(rc))
            else:
                a = menu.addAction("Underline this row")
                a.triggered.connect(lambda _, rc=row_combo: self._toggle_row_underline(rc, True))

        if underlined:
            if row_combo is None:
                menu.addSeparator()
            a2 = menu.addAction("Clear all row underlines")
            a2.triggered.connect(lambda _: self._clear_all_underlines())

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

    def _toggle_row_underline(self, combo_key, add):
        underlined = _read_underlined_combos(self.node.config)
        if add:
            underlined[combo_key] = underlined.get(combo_key, DEFAULT_UNDERLINE_COLOR)
        else:
            underlined.pop(combo_key, None)
        _write_underlined_combos(self.node.config, underlined)
        self._refresh()

    def _change_row_underline_color(self, combo_key):
        underlined = _read_underlined_combos(self.node.config)
        current = underlined.get(combo_key, DEFAULT_UNDERLINE_COLOR)
        # A classifier-derived default can be a LIST of colors (a row whose
        # particles matched several buckets under double_count); the color
        # dialog needs a single seed, so take the first.
        if isinstance(current, (list, tuple)):
            current = current[0] if current else DEFAULT_UNDERLINE_COLOR
        color = QColorDialog.getColor(QColor(current), self, "Choose Underline Color")
        if color.isValid():
            underlined[combo_key] = color.name()
            _write_underlined_combos(self.node.config, underlined)
            self._refresh()

    def _clear_all_underlines(self):
        _write_underlined_combos(self.node.config, {})
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
        data = self.node.extract_plot_data()
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
            from results import classifier_view as cv
            self._axes_row_combos = {}
            self._axes_sample_map = {}
            self._any_underlines_this_render = False
            cfg = self.node.config
            role = self.node.classifier_role()

            if cfg.get('use_custom_figsize', False):
                self.figure.set_size_inches(cfg.get('figsize_w', 16.0),
                                            cfg.get('figsize_h', 10.0))

            if role != cv.ROLE_FACET:
                self.figure.clear()
                bg = cfg.get('bg_color', '#FFFFFF')
                self.figure.patch.set_facecolor(bg)

                data = self.node.extract_plot_data()

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
                        self._draw_multi(data, cfg, dm, role)
                    else:
                        ax = self.figure.add_subplot(111)
                        self._draw_heatmap(
                            ax, data, cfg, self._single_sample_title(cfg),
                            role=role, particles_for_colors=self._all_particles(),
                            data_key=self._current_data_key())
                        apply_font_to_matplotlib(ax, cfg)

                self.figure.tight_layout()
                self._ensure_underline_margin()
            else:
                self._refresh_panels()

            self.canvas.draw()
            self.canvas.snapshot_positions()
        except Exception as e:
            _itk_log.exception("Handled exception in _refresh")
            _itk_log.error(f"Error refreshing heatmap: {e}")
            import traceback; traceback.print_exc()

    def _current_data_key(self):
        dt = self.node.config.get('data_type_display', 'Counts')
        return DATA_KEY_MAPPING.get(dt, 'elements')

    def _all_particles(self):
        return self.node.input_data.get('particle_data', []) if self.node.input_data else []

    def _particles_for_sample(self, sample_name):
        return [p for p in self._all_particles()
               if p.get('source_sample') == sample_name]

    # ── PANELS role ────────────────────────────────────────────────────

    def _panel_title_for(self, label):
        """Panel/window title for one classifier group, honoring the
        "show expression next to group label" toggle (GROUPS-role setting,
        reused here so one preference governs both roles)."""
        from results import classifier_view as cv
        if self.node.config.get('show_group_expression', False):
            return cv.bucket_caption(self.node.input_data, label)
        return label

    def _refresh_panels(self):
        """Draw PANELS role.

        Two different layouts, because the useful comparison differs
        (explicit user spec, 2026-08-25):

        - **Single sample**: one subplot per classifier group, all in this
          window, no selector -- "for this sample, what does each group's
          composition look like?". Includes the Unclassified group when the
          classifier is in unclassified mode.
        - **Multi-sample**: the user picks ONE group in "Configure plot
          quantities"; this window then shows one subplot per SAMPLE for
          that group -- "for this group, how does it differ across my
          samples?". Samples where the group has no particles (never
          defined for that sample, or defined but matched nothing) get no
          subplot rather than an empty one.

        Every panel is today's *unmodified* combination-row heatmap built
        from that partition's own particles -- no GROUPS-role concepts
        (aggregation scope, group-cell denominator, raw row labels) apply,
        since each panel shows real per-particle isotope composition.

        This function never decides *which* group a particle belongs to --
        it only sorts particles by the bucket the classifier already
        assigned. Whether a particle appears under one group or several is
        entirely the classifier's own overlap decision (priority ordering
        vs. double_count), faithfully reflected here rather than
        second-guessed.
        """
        cfg = self.node.config
        panel_data = self.node.extract_panel_data()

        self.figure.clear()
        bg = cfg.get('bg_color', '#FFFFFF')
        self.figure.patch.set_facecolor(bg)

        if self._is_multi():
            group = self.node.panel_group()
            per_sample = (panel_data or {}).get(group) or {}
            panels = [(get_display_name(sn, cfg), combos)
                     for sn, combos in per_sample.items()]
            empty_msg = (f'No particles in "{group}" for any sample'
                        if group else 'No classifier group selected')
            suptitle = self._panel_title_for(group) if group else None
        else:
            panels = [(self._panel_title_for(lbl), combos)
                     for lbl, combos in (panel_data or {}).items()]
            empty_msg = 'No classified data available'
            suptitle = None

        if not panels:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, f'{empty_msg}\nRight-click for options',
                    ha='center', va='center', transform=ax.transAxes,
                    fontsize=12, color='gray')
            ax.set_xticks([]); ax.set_yticks([])
            self.figure.tight_layout()
            return

        cols = min(2, len(panels))
        rows = math.ceil(len(panels) / cols)
        for i, (panel_title, combos) in enumerate(panels):
            ax = self.figure.add_subplot(rows, cols, i + 1)
            row_combos = draw_combinations_heatmap(
                ax, self.figure, combos, cfg, title=panel_title, is_multi=True)
            if row_combos is not None:
                self._axes_row_combos[id(ax)] = row_combos
            apply_font_to_matplotlib(ax, cfg)

        if suptitle:
            fc = get_font_config(cfg)
            self.figure.suptitle(suptitle, fontsize=fc['size'] + 4,
                                 fontweight='bold', color=fc['color'],
                                 fontfamily=fc['family'])
        self.figure.tight_layout()

    # ── Multi-sample dispatch ───────────────

    def _draw_multi(self, data, cfg, display_mode, role=None):
        """Draw the active multi-sample Heatmap layout.

        Preserved behavior:
            This changes only panel layout and display-only sample titles.
            Heatmap values, aggregation, color scaling, and colormap behavior
            remain unchanged.
        """
        display_mode = _normalize_heatmap_display_mode(display_mode)
        names = list(data.keys())
        n = len(names)
        data_key = self._current_data_key()

        if display_mode == 'Individual Subplots':
            cols = min(2, n)
            rows = math.ceil(n / cols)
            for i, sn in enumerate(names):
                ax = self.figure.add_subplot(rows, cols, i + 1)
                self._axes_sample_map[id(ax)] = sn
                self._draw_heatmap(ax, data[sn], cfg, get_display_name(sn, cfg),
                                   role=role, particles_for_colors=self._particles_for_sample(sn),
                                   data_key=data_key)
                apply_font_to_matplotlib(ax, cfg)

        elif display_mode == 'Side by Side Subplots':
            for i, sn in enumerate(names):
                ax = self.figure.add_subplot(1, n, i + 1)
                self._axes_sample_map[id(ax)] = sn
                self._draw_heatmap(ax, data[sn], cfg, get_display_name(sn, cfg),
                                   role=role, particles_for_colors=self._particles_for_sample(sn),
                                   data_key=data_key)
                apply_font_to_matplotlib(ax, cfg)

        else:
            combined = self._combine_data(data)
            ax = self.figure.add_subplot(111)
            self._draw_heatmap(ax, combined, cfg,
                               f"Combined ({len(data)} samples)",
                               role=role, particles_for_colors=self._all_particles(),
                               data_key=data_key)
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

    def _draw_heatmap(self, ax, sample_data, cfg, title, role=None,
                       particles_for_colors=None, data_key=None):
        """
        Args:
            ax (Any): The ax.
            sample_data (Any): The sample data.
            cfg (Any): The cfg.
            title (Any): Window or dialog title.
            role (str | None): Current classifier role (GROUPS/COLORS/OFF --
                PANELS never reaches this method, see ``_refresh_panels``).
                Resolved from the node if not given.
            particles_for_colors (list | None): The real particle dicts this
                specific axes' rows were built from (one sample's worth, or
                every sample combined) -- needed under COLORS role to derive
                each row's default classifier color(s); ignored otherwise.
            data_key (str | None): The composition key currently selected
                (``'elements'``, ``'element_mass_fg'``, ...) -- needed
                alongside ``particles_for_colors`` to recompute which row a
                particle lands in (see ``_default_row_bucket_colors_by_combo``).
        """
        from results import classifier_view as cv
        if role is None:
            role = self.node.classifier_role()

        row_label_raw = (role == cv.ROLE_SERIES)
        draw_cfg = cfg
        bucket_legend = None
        manual_keys = None

        if role == cv.ROLE_ENCODE:
            stored = _read_underlined_combos(cfg)
            defaults = {}
            if particles_for_colors and data_key:
                defaults = _default_row_bucket_colors_by_combo(
                    particles_for_colors, data_key, self.node.input_data)
            merged = dict(defaults)
            merged.update(stored)  # a manual right-click override always wins
            draw_cfg = dict(cfg)
            _write_underlined_combos(draw_cfg, merged)
            if merged:
                self._any_underlines_this_render = True
            manual_keys = set(stored)
            bucket_legend = self._bucket_legend_entries()
            # Diagnostic: this path silently produced nothing in a live QA
            # session that no fixture could reproduce, so leave a trace of
            # exactly which input was empty rather than only the outcome.
            _itk_log.info(
                "Heatmap COLORS: %d particles, data_key=%r, registry=%d, "
                "defaults=%d rows, manual=%d rows, legend=%d entries",
                len(particles_for_colors or []), data_key,
                len(cv.bucket_registry(self.node.input_data)),
                len(defaults), len(stored), len(bucket_legend or []))

        row_combos = draw_combinations_heatmap(
            ax, self.figure, sample_data, draw_cfg, title=title,
            is_multi=self._is_multi(), row_label_raw=row_label_raw,
            bucket_legend=bucket_legend, manual_underline_keys=manual_keys,
        )
        if row_combos is not None:
            self._axes_row_combos[id(ax)] = row_combos

    def _ensure_underline_margin(self):
        """Widen the figure's left margin when COLORS-role underline
        segments were drawn this render, so they have real room to be
        visible instead of running off the edge of the canvas.

        **Real bug, found by actually rendering and looking, not just
        checking that the Line2D/Legend objects exist** (2026-08-25):
        the underline is drawn at ``xmin=-0.22`` in AXES-fraction
        coordinates (see ``draw_combinations_heatmap``) -- 22% of the
        AXES' own width, to its left. ``tight_layout()`` sizes the left
        margin from standard tick-label width alone; it has no idea a
        custom, off-axes decoration needs room too. On a real render this
        left the axes' own left edge at ~8% of FIGURE width while the
        underline needed ~16% of figure width further left than that --
        landing at a *negative* figure-fraction x position, i.e. past the
        edge of the canvas entirely, rendering as a barely-visible sliver
        at best. Confirmed by saving an actual PNG and inspecting it, not
        by assumption.
        """
        if not getattr(self, '_any_underlines_this_render', False):
            return
        min_left = 0.24
        try:
            if self.figure.subplotpars.left < min_left:
                self.figure.subplots_adjust(left=min_left)
        except Exception:
            pass

    def _bucket_legend_entries(self):
        """``[(label, color), ...]`` for the COLORS-role "what color is what
        classifier group" legend, registry order. Sample-independent (the
        registry is stream-wide), unlike the per-row color merge itself.

        Excludes ``Unclassified`` to stay consistent with what actually gets
        drawn: COLORS underlines only particles that matched something the
        user defined, so an Unclassified legend swatch would name a color
        that appears nowhere on the plot. A bucket whose registry entry has
        no usable color still appears, with the shared fallback color,
        rather than being dropped -- see
        ``classifier_view.default_row_bucket_colors``.
        """
        from results import classifier_view as cv
        registry = cv.bucket_registry(self.node.input_data)
        return [(lbl, entry.get('color') or cv.FALLBACK_BUCKET_COLOR)
               for lbl, entry in registry.items()
               if lbl != cv.UNCLASSIFIED_LABEL]


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


def _fmt_cell_number(v):
    """Format one numeric cell value with the heatmap's standard precision.

    Units are deliberately omitted. The colorbar and the Data Type setting
    already state whether the matrix is in fg, fmol or %, so repeating a suffix
    in every cell only adds clutter — the sole exception is CV, which is a
    percentage *of the mean* rather than of the data type and so carries its
    own '%' at the call site.
    """
    if v >= 1000:
        return f'{v:.0f}'
    if v >= 1:
        return f'{v:.1f}'
    return f'{v:.2f}'


def _per_particle_percentages(total_values):
    """Convert a combination's raw per-element values into per-particle %.

    ``total_values`` is ``{element: [v_particle0, v_particle1, ...]}`` and the
    lists are parallel: index *i* is the same particle in every element, because
    a combination is defined by the exact element set its particles share. Each
    particle is therefore normalised on its own total, giving a distribution of
    composition percentages per element instead of a single bulk number. That
    distribution is what makes Mean/Median/Mode and SD/SEM/IQR meaningful for
    the ``%`` data types.

    Args:
        total_values (dict): ``{element: [values...]}`` for one combination.

    Returns:
        dict | None: ``{element: [pct...]}`` with one percentage per particle,
        or None when the lists are not parallel (e.g. synthesised rows from the
        clustering Overview tab), in which case the caller falls back to the
        bulk percentage.
    """
    elems = [e for e, v in total_values.items() if v]
    if not elems:
        return None

    lengths = {len(total_values[e]) for e in elems}
    if len(lengths) != 1:
        return None
    n = lengths.pop()
    if n == 0:
        return None

    arrs = {}
    for e in elems:
        a = np.asarray(total_values[e], dtype=float)
        arrs[e] = np.nan_to_num(a, nan=0.0)

    totals = np.zeros(n, dtype=float)
    for a in arrs.values():
        totals += a

    valid = totals > 0
    if not np.any(valid):
        return None

    return {e: (a[valid] / totals[valid] * 100.0) for e, a in arrs.items()}


def _bulk_percentages(total_values):
    """Bulk composition %: each element's summed signal over the grand total.

    Used as the fallback when per-particle normalisation isn't possible.
    """
    sums = {e: float(np.nansum(v)) for e, v in total_values.items() if v}
    grand = sum(sums.values())
    if grand <= 0:
        return None
    return {e: [s / grand * 100.0] for e, s in sums.items()}


def draw_combinations_heatmap(ax, fig, sample_data, cfg, title='',
                             is_multi=False, row_label_raw=False,
                             bucket_legend=None, manual_underline_keys=None):
    """Draw a combinations heatmap onto an arbitrary axes/figure.

    This is the standalone, ``self``-free version of
    ``HeatmapDisplayDialog._draw_heatmap``. It's used by other tabs (e.g. the
    clustering Overview tab) that want the *exact same* heatmap rendering
    without instantiating a HeatmapDisplayDialog, and by classifier GROUPS
    role, whose rows are classifier bucket labels rather than isotope
    combinations but need every other piece of this pipeline (cell
    statistic, cell spread, search/filter, sorting, percentage handling)
    unchanged -- see ``classifier_view.group_composition_rows``.

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
        ``cell_linewidth``. ``underlined_combos`` (read through
        ``_read_underlined_combos``, which also honors the pre-rename
        ``highlighted_combos`` key) values may be a hex color string
        (single-color underline, the historical shape) OR a list of hex
        strings (an equal-fraction multi-color underline, split evenly
        across the list -- used by classifier COLORS role for a row whose
        members matched more than one bucket under ``double_count``).
        title (str): Title to render above the heatmap when provided.
        is_multi (bool): Whether this is a multi-sample panel. This still
            controls compatibility with existing multi-sample rendering paths,
            but a non-empty title is now honored in single-sample mode too.
        row_label_raw (bool): Skip isotope-combination label formatting
            (``format_combination_label``) for row labels and use the row
            key text as-is. Column labels are unaffected -- they're always
            real isotopes even under classifier GROUPS role. Needed because
            a classifier bucket label ("Smelter", or "Smelter (60Ni)" with
            the expression shown) is a human-chosen name, not an isotope
            token list, and running it through isotope-label formatting can
            mangle it (e.g. "Smelter" starts with the real element symbol
            "Sm" under 'Symbol'/'Atomic Notation' label modes).
        bucket_legend (list[tuple[str, str]] | None): ``[(bucket_label,
            hex_color), ...]`` to render as a "what color is what classifier
            group" legend below the axes -- COLORS role only.
        manual_underline_keys (set | None): Row keys carrying a MANUAL
            right-click color override. The legend is suppressed when any
            row **actually on screen** is manually overridden, because a
            legend claiming "this color means this group" would be wrong
            next to a hand-recolored row. Deliberately evaluated against
            the selected/visible rows rather than the whole stored dict:
            heatmap only shows a top-N slice, so an override left on a row
            that has since dropped out of range must not keep the legend
            hidden forever (bug found 2026-08-25).
    """
    if not sample_data:
        ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                transform=ax.transAxes, color='gray')
        return

    dt = cfg.get('data_type_display', 'Counts')
    search_text = cfg.get('search_element', '').strip()
    underlined_combos = _read_underlined_combos(cfg)
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
        fmt = combo if row_label_raw else format_combination_label(
            combo, label_mode, Renderer.MATHTEXT, cfg)
        if cfg.get('y_axis_unit', 'count') == 'per_ml' and d.get('pml', 0.0) > 0:
            labels.append(f"{fmt} ({format_per_ml(d['pml'], Renderer.MATHTEXT, cfg)})")
        else:
            labels.append(f"{fmt} ({count})")

        is_pct = dt.endswith('%')
        pct_values = None
        if is_pct:
            pct_values = (_per_particle_percentages(d['total_values'])
                          or _bulk_percentages(d['total_values'])
                          or {})

        row = []
        spread_row = []
        for elem in all_elems:
            vals = (pct_values.get(elem, []) if is_pct
                    else d['total_values'].get(elem, []))
            if len(vals) == 0:
                row.append(0)
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

    combo_keys_list = [c for c, _ in selected]
    if underlined_combos:
        # Widened from the historical -0.15 so an equal-fraction multi-color
        # split (classifier COLORS role, a row matching 2+ buckets under
        # double_count) stays legible instead of shrinking into a sliver.
        underline_xmin, underline_xmax = -0.22, 0.0
        for i, ck in enumerate(combo_keys_list):
            hv = underlined_combos.get(ck)
            if not hv:
                continue
            # A single hex string (the historical shape, and always what a
            # manual right-click override writes) draws one solid segment.
            # A list (classifier-derived default, one color per distinct
            # matched bucket) splits the same span into equal fractions --
            # see classifier_view.default_row_bucket_colors for why an equal
            # split is the complete answer here, not a headcount-weighted one.
            colors = list(hv) if isinstance(hv, (list, tuple)) else [hv]
            colors = [c for c in colors if c] or [DEFAULT_UNDERLINE_COLOR]
            seg_width = (underline_xmax - underline_xmin) / len(colors)
            for j, color in enumerate(colors):
                seg_xmin = underline_xmin + j * seg_width
                ax.axhline(y=i + 0.35, color=color, linewidth=2, alpha=0.9,
                           xmin=seg_xmin, xmax=seg_xmin + seg_width, clip_on=False)
            ax.get_yticklabels()[i].set_weight('bold')

    # Suppress the legend only when a row that is ACTUALLY VISIBLE carries a
    # manual override -- not merely when one exists somewhere in the config
    # for a row outside this top-N slice.
    if manual_underline_keys and any(ck in manual_underline_keys
                                     for ck in combo_keys_list):
        bucket_legend = None

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
        weight = 'bold' if fc['bold'] else 'normal'
        mx = np.nanmax(plot_matrix) if not np.all(np.isnan(plot_matrix)) else 1
        for i in range(len(labels)):
            for j in range(len(all_elems)):
                v = plot_matrix[i, j]
                v_orig = matrix[i, j]
                if not np.isnan(v) and v_orig > 0:
                    tc = 'white' if v > mx * 0.5 else 'black'
                    txt = _fmt_cell_number(v_orig)
                    sp = spread_matrix[i][j]
                    if sp is not None:
                      
                        if isinstance(sp, tuple) and sp[0] == '%':
                            txt = f'{txt} ({sp[1]:.0f}%)'
                        elif isinstance(sp, tuple):
                            txt = (f'{txt} ({_fmt_cell_number(sp[0])}'
                                   f'–{_fmt_cell_number(sp[1])})')
                        else:
                            txt = f'{txt} ± {_fmt_cell_number(sp)}'
                    ax.text(j, i, txt, ha='center', va='center',
                            color=tc, fontsize=eff_fs,
                            fontfamily=fc['family'], weight=weight,
                            style='italic' if fc['italic'] else 'normal')

    if bucket_legend:
        from matplotlib.patches import Patch
        handles = [Patch(facecolor=color, edgecolor='none', label=label)
                  for label, color in bucket_legend]
        ncol = min(len(handles), 4)
        ax.legend(handles=handles, loc='upper center',
                  bbox_to_anchor=(0.5, -0.12), ncol=ncol,
                  frameon=False, fontsize=max(6, fc['size'] - 2))

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
        # Manual per-row underline overrides. Renamed from the legacy
        # 'highlighted_combos' (2026-08-25); saved projects using the old key
        # are still read via _read_underlined_combos. NOTE: the separate
        # 'highlight_matches' key above is a DIFFERENT feature (search-term
        # matching), deliberately not renamed.
        'underlined_combos': {},
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
        # ── Classifier group rows (GROUPS role) ─────────────────────────
        'classifier_group_denominator': 'whole_group',
        'show_group_expression': False,
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
        from results.shared_plot_utils import deep_copy_config
        self.config = deep_copy_config(self.DEFAULT_CONFIG)
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

    def classifier_role(self):
        """The GROUPS/PANELS/COLORS/OFF role in force for this render (see
        ``results.classifier_view``'s role-model docs). Resolved fresh every
        call, never cached -- the upstream stream or the user's own choice
        can change between renders.

        **Config-derived, and therefore view-sensitive.** This node is
        multi-figure: its dialog is handed a ``_FigureView``, not the node,
        and the user's role choice lands in *that figure's* config. The
        ``classifier_`` prefix is what makes ``_FigureView`` evaluate this
        against the figure's config instead of the node's -- do not rename it
        without adding ``@view_config_method``, or this silently returns the
        default role forever and the whole classifier UI goes dead in the app
        while every test still passes. See
        ``shared_plot_utils._FigureView._VIEW_CONFIG_PREFIXES``.
        """
        from results import classifier_view as cv
        return cv.effective_role(self.config, self.input_data, cv.ARITY_HEATMAP)

    def classifier_scope(self):
        """The DEFINITION-or-TOTAL-PARTICLE aggregation scope in force for
        this render. Only changes anything under GROUPS role; harmless to
        resolve and pass through unconditionally otherwise. For heatmap
        specifically this only changes which isotope COLUMNS are eligible to
        appear at all, never the numeric value within a shown cell -- see
        ``classifier_view.group_composition_rows``.
        """
        from results import classifier_view as cv
        return cv.effective_scope(self.config, self.input_data)

    def classifier_denominator(self):
        """The Whole-Group-or-Detected-Only denominator in force for this
        render. Only changes anything under GROUPS role.
        """
        from results import classifier_view as cv
        return cv.effective_denominator(self.config, self.input_data)

    def extract_plot_data(self):
        """Row data for the GROUPS/COLORS/OFF roles, in the same
        ``{combo_or_group_label: {'particle_count', 'total_values', 'pml'}}``
        (single-sample) / ``{sample: {...}}`` (multi-sample) shape regardless
        of role -- GROUPS rows are classifier buckets (see ``_group_rows``),
        COLORS/OFF rows are real isotope co-occurrence combinations exactly
        as before classifier awareness existed.

        Returns ``None`` under PANELS role: its shape is a sample-nested set
        of *per-group* combination dicts, which callers of this method don't
        expect -- ``HeatmapDisplayDialog`` calls ``extract_panel_data()``
        directly instead when it detects PANELS, bypassing this method
        entirely, so this contract stays exactly what it always was for
        every other role (and for the clustering Overview tab, which reuses
        ``draw_combinations_heatmap`` directly with its own synthesised data
        and never goes through this method at all).
        """
        if not self.input_data:
            return None
        from results import classifier_view as cv
        role = self.classifier_role()
        if role == cv.ROLE_FACET:
            return None
        dt = self.config.get('data_type_display', 'Counts')
        dk = DATA_KEY_MAPPING.get(dt, 'elements')
        itype = self.input_data.get('type')

        if itype == 'sample_data':
            return self._extract_single(dk, role)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(dk, role)
        return None

    def _extract_single(self, data_key, role=None):
        from results import classifier_view as cv
        if role is None:
            role = self.classifier_role()
        particles = self.input_data.get('particle_data')
        if not particles:
            return None
        sname = self.input_data.get('sample_name', 'Sample')
        pml = per_ml_factor(self.input_data, sname)
        if role == cv.ROLE_SERIES:
            return self._group_rows(particles, data_key, pml)
        return _build_combinations(particles, data_key, pml)

    def _extract_multi(self, data_key, role=None):
        from results import classifier_view as cv
        if role is None:
            role = self.classifier_role()
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
            pml = per_ml_factor(self.input_data, sn)
            rows = (self._group_rows(plist, data_key, pml) if role == cv.ROLE_SERIES
                   else _build_combinations(plist, data_key, pml))
            if rows:
                result[sn] = rows
        return result or None

    def _group_rows(self, particles, data_key, pml_factor):
        """GROUPS-role rows: one row per classifier bucket, built via
        ``classifier_view.group_composition_rows`` (real per-isotope values
        aggregated across the bucket's members, honoring the aggregation
        scope and group-cell denominator currently configured) and adapted
        into the exact shape ``draw_combinations_heatmap`` already knows how
        to render -- a group row is indistinguishable from a combination row
        to that function.

        Args:
            particles (list): One sample's particle dicts.
            data_key (str): e.g. ``'elements'``, ``'element_mass_fg'``.
            pml_factor (float): Per-mL multiplier for this sample (see
                ``shared_plot_utils.per_ml_factor``), applied the same way
                ``_build_combinations`` applies it for combination rows.

        Returns:
            dict | None: ``{row_key: {'count', 'particle_count',
            'total_values', 'pml'}}``, or ``None`` when there is nothing
            classified to show (e.g. every particle is passthrough).
            ``row_key`` is the bare bucket label, or ``"Label (expression)"``
            when "Show expression next to group label" is on (Unclassified
            has no expression, so its label is unaffected either way -- see
            ``classifier_view.bucket_caption``). ``count`` duplicates
            ``particle_count`` -- both are always equal, kept only because
            ``_combine_data`` (Combined Heatmap display mode) reads ``count``
            specifically, matching ``_build_combinations``'s own shape.
        """
        from results import classifier_view as cv
        scope = self.classifier_scope()
        denominator = self.classifier_denominator()
        rows = cv.group_composition_rows(particles, data_key, scope, denominator)
        if not rows:
            return None
        show_expr = self.config.get('show_group_expression', False)
        out = {}
        for label, row in rows.items():
            key = cv.bucket_caption(self.input_data, label) if show_expr else label
            out[key] = {
                'count': row['particle_count'],
                'particle_count': row['particle_count'],
                'total_values': row['total_values'],
                'pml': pml_factor * row['particle_count'],
            }
        return out

    def panel_groups(self):
        """Every classifier group PANELS role can show, in registry order.

        Registry order (the order the user defined them) rather than
        abundance, so the dropdown doesn't reshuffle itself when the data
        changes. Passthrough particles are absent by construction -- they
        carry no bucket -- which is deliberate: a researcher who wants to
        inspect unmatched particles switches the classifier's unmatched
        mode to "unclassified", rather than this node inventing a synthetic
        panel for data the classifier declined to label. (Noted as a known
        rough edge in ``.claude/aug24.md``.)
        """
        from results import classifier_view as cv
        return list(cv.bucket_registry(self.input_data).keys())

    def panel_group(self):
        """The single classifier group PANELS role is showing per sample
        (multi-sample only; single-sample shows every group at once).

        Resolved fresh each render against the CURRENT group list, so a
        stored choice that no longer exists (definition renamed or deleted,
        or a saved project opened against a re-configured classifier) falls
        back to the first available group instead of rendering nothing.
        """
        groups = self.panel_groups()
        if not groups:
            return None
        stored = self.config.get(PANEL_GROUP_CONFIG_KEY)
        return stored if stored in groups else groups[0]

    def extract_panel_data(self):
        """PANELS-role data: particles partitioned by the bucket the
        CLASSIFIER assigned them, then each partition run through today's
        unmodified combination-row builder -- "just a standard heatmap, but
        for each classifier group". No scope or denominator applies: each
        panel shows real, unfiltered per-particle composition, the same as
        OFF, restricted to one partition at a time.

        This method never decides group membership itself; it reads
        ``BUCKET_KEY`` as emitted upstream. A particle appearing under two
        groups means the classifier's ``double_count`` overlap mode put it
        in both, and a particle appearing under only one means priority
        ordering resolved it -- either way this is reporting that decision,
        not making it.

        Returns:
            dict | None: Always ``{group_label: {sample_or_none: ...}}``-
            shaped by GROUP first, so the multi-sample dropdown can select a
            group without re-partitioning:

            - single-sample: ``{group_label: combo_dict}``
            - multi-sample: ``{group_label: {sample_name: combo_dict}}``,
              omitting any sample where that group has no particles at all
              (never defined for it, or defined but unmatched) so no empty
              panel is ever drawn.

            ``None`` when the upstream isn't a classifier stream or has no
            particles.
        """
        if not self.input_data:
            return None
        from results import classifier_view as cv
        if not cv.is_classifier_stream(self.input_data):
            return None
        dt = self.config.get('data_type_display', 'Counts')
        dk = DATA_KEY_MAPPING.get(dt, 'elements')
        itype = self.input_data.get('type')

        def _by_group(particles, pml_factor):
            """``{group_label: combo_dict}`` for one sample's particles."""
            buckets = cv.particles_by_bucket(particles, include_unclassified=True)
            out = {}
            for label, plist in buckets.items():
                if label is None or not plist:
                    continue  # passthrough: no bucket, nothing to panel by
                combos = _build_combinations(plist, dk, pml_factor)
                if combos:
                    out[label] = combos
            return out

        if itype == 'sample_data':
            particles = self.input_data.get('particle_data')
            if not particles:
                return None
            sname = self.input_data.get('sample_name', 'Sample')
            return _by_group(particles, per_ml_factor(self.input_data, sname)) or None

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
            for sn in names:  # sample_names order, not dict insertion order
                for label, combos in _by_group(
                        grouped[sn], per_ml_factor(self.input_data, sn)).items():
                    result.setdefault(label, {})[sn] = combos
            return result or None
        return None


def _combo_signature(particle, data_key):
    """One particle's contribution to a combination row for ``data_key``.

    The "which isotopes actually carry a positive value" rule a combination
    row is grouped by -- pulled out of ``_build_combinations`` so any other
    code that needs to answer "which row would this particle land in" (e.g.
    matching a classifier bucket's color to that row for COLORS role, see
    ``_default_row_bucket_colors_by_combo``) uses the identical rule by
    construction, rather than a second copy that could drift out of sync.

    Reads through ``classifier_view.composition(..., collapsed=False)``,
    not a direct ``particle.get(data_key)`` -- **load-bearing, not
    cosmetic**: a matched classifier particle's OWN ``data_key`` entry has
    already been destructively collapsed to a single ``{bucket_label:
    value}`` entry by the time it reaches this node, so every particle
    sharing a bucket would otherwise produce the IDENTICAL one-isotope
    signature ``frozenset({bucket_label})`` -- the exact "degenerates to a
    1x1 diagonal per bucket" failure this whole classifier-heatmap effort
    exists to fix (``.claude/aug24.md``'s arity taxonomy table). Safe for
    non-classifier data unconditionally: ``composition()`` falls back to
    the particle's own real dict whenever there is no dual-carried raw
    snapshot to read instead, so this is a strict bugfix, not a behavior
    change, for anything that was never touched by a classifier.
    """
    from results import classifier_view as cv
    d = cv.composition(particle, data_key, collapsed=False)
    vals = {}
    for name, v in d.items():
        if data_key == 'elements':
            if v > 0:
                vals[name] = v
        else:
            if v > 0 and v == v:  # v==v false only for NaN, faster than np.isnan on a scalar
                vals[name] = v
    if not vals:
        return None
    return frozenset(vals.keys()), vals


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
        # sort_elements_by_mass() output depends only on the SET of element
        # names (it re-sorts regardless of input order), and real particle
        # populations reuse the same handful of isotope combinations across
        # many thousands of particles — memoizing by that set avoids
        # re-running the mass-parsing regex + sort for every repeat.
        key_cache = {}
        for particle in particles:
            sig = _combo_signature(particle, data_key)
            if sig is None:
                continue
            combo_id, vals = sig

            key = key_cache.get(combo_id)
            if key is None:
                key = ', '.join(sort_elements_by_mass(list(combo_id)))
                key_cache[combo_id] = key
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


def _default_row_bucket_colors_by_combo(particles, data_key, input_data):
    """``{combo_key: [hex_color, ...]}`` classifier-derived defaults for
    every combination row ``_build_combinations(particles, data_key, ...)``
    would produce for these same particles.

    The COLORS-role counterpart to ``_build_combinations``, computed as its
    own pass rather than threaded through it: a combination row's aggregated
    ``total_values`` doesn't retain which raw particles fed it, and
    ``classifier_view.default_row_bucket_colors`` needs the row's actual
    member particles (to collect their bucket labels), not its aggregated
    values. Uses ``_combo_signature`` -- the exact same grouping rule -- so
    which particles land in which row can never drift between the two
    passes.

    Args:
        particles (list): Particle dicts (one sample's worth, or a combined
            multi-sample list for "Combined Heatmap" display mode).
        data_key (str): e.g. ``'elements'``, ``'element_mass_fg'``.
        input_data (dict | None): The node's upstream data (for bucket
            registry colors).

    Returns:
        dict: ``{combo_key: [hex_color, ...]}``. A row with no classified
        members at all (all-passthrough) is simply absent -- nothing to
        color, and an absent key reads as "no default" to any merge with a
        manual override dict.
    """
    from results import classifier_view as cv
    grouped = {}
    key_cache = {}
    for particle in particles:
        sig = _combo_signature(particle, data_key)
        if sig is None:
            continue
        combo_id, _ = sig
        key = key_cache.get(combo_id)
        if key is None:
            key = ', '.join(sort_elements_by_mass(list(combo_id)))
            key_cache[combo_id] = key
        grouped.setdefault(key, []).append(particle)

    out = {}
    for key, plist in grouped.items():
        colors = cv.default_row_bucket_colors(input_data, plist)
        if colors:
            out[key] = colors
    return out
