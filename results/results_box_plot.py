"""
Distribution Plot Node – Box / Violin / Strip / Bar-with-errors.

Keeps **PyQtGraph** for interactive zoom/pan.
Sidebar replaced by **right-click context menu** + settings dialog.
Uses shared_plot_utils for fonts, colors, sample helpers, and download.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QPushButton,
    QLineEdit, QFrame, QScrollArea, QWidget, QMenu, QDialogButtonBox,
    QListWidget,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor
import pyqtgraph as pg
import numpy as np
import math
from scipy.stats import gaussian_kde

from results.shared_plot_utils import (
    DEFAULT_SAMPLE_COLORS, apply_font_to_pyqtgraph,
    FontSettingsGroup, get_display_name, download_pyqtgraph_figure, copy_figure_to_clipboard, format_element_label,
    LABEL_MODES, Renderer, HtmlAxisItem,
    SHADE_TYPES,
    _apply_box, _add_hband, _add_det_limit_h, apply_plot_title_style,
    apply_axis_label_style,
)
from results.utils_sort import (
    sort_elements_by_mass,
    sort_element_dict_by_mass,
    element_alphabetical_key,
)
import logging
_itk_log = logging.getLogger("IsotopeTrack.results.results_box_plot")

try:
    from results.results_bar_charts import (
        EnhancedGraphicsLayoutWidget, _PlotWidgetAdapter,
        _get_broken_cuts, _render_broken_or_plain, BrokenYAxisEditor,
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
    _get_broken_cuts = lambda cfg: []
    _render_broken_or_plain = None
    BrokenYAxisEditor = None

# ── Constants ──────────────────────────────────────────────────────────

PLOT_SHAPES = [
    'Box Plot (Traditional)',
    'Violin Plot',
    'Box + Violin (Overlay)',
    'Strip Plot (Dots)',
    'Half Violin + Half Box',
    'Notched Box Plot',
    'Bar Plot with Error Bars',
]

BOX_DATA_TYPES = [
    'Counts',
    'Element Mass (fg)',
    'Particle Mass (fg)',
    'Element Moles (fmol)',
    'Particle Moles (fmol)',
    'Element Diameter (nm)',
    'Particle Diameter (nm)',
]

BOX_DATA_KEY_MAP = {
    'Counts': 'elements',
    'Element Mass (fg)': 'element_mass_fg',
    'Particle Mass (fg)': 'particle_mass_fg',
    'Element Moles (fmol)': 'element_moles_fmol',
    'Particle Moles (fmol)': 'particle_moles_fmol',
    'Element Diameter (nm)': 'element_diameter_nm',
    'Particle Diameter (nm)': 'particle_diameter_nm',
}

BOX_LABEL_MAP = {
    'Counts': 'Intensity (counts)',
    'Element Mass (fg)': 'Element Mass (fg)',
    'Particle Mass (fg)': 'Particle Mass (fg)',
    'Element Moles (fmol)': 'Element Moles (fmol)',
    'Particle Moles (fmol)': 'Particle Moles (fmol)',
    'Element Diameter (nm)': 'Element Diameter (nm)',
    'Particle Diameter (nm)': 'Particle Diameter (nm)',
}

BOX_DISPLAY_MODES = [
    'Side by Side',
    'Subplots by sample',
    'Subplots by isotope',
]

BOX_SORT_OPTIONS = [
    'No Sorting',
    'Ascending',
    'Descending',
    'Alphabetical',
]

DEFAULT_ELEMENT_COLORS = [
    '#663399', '#2E86AB', '#A23B72', '#F18F01', '#C73E1D',
    '#7209B7', '#F72585', '#4361EE', '#277DA1', '#F8961E',
]

DEFAULT_CONFIG = {
    'data_type_display': 'Counts',
    'plot_shape': 'Box Plot (Traditional)',
    'violin_bandwidth': 0.2,
    'strip_jitter': 0.2,
    'show_outliers': True,
    'show_mean': True,
    'show_median': True,
    'alpha': 0.7,
    'log_y': False,
    'show_stats': False,
    'plot_width': 0.8,
    'y_min': 0,
    'y_max': 100,
    'auto_y': True,
    'filter_outliers': False,
    'outlier_percentile': 99.0,
    'show_box': True,
    'shade_type': 'None',
    'shade_color': '#534AB7',
    'shade_alpha': 0.18,
    'shade_min': 0.0,
    'shade_max': 1.0,
    'show_det_limit': False,
    'det_limit_value': 1.0,
    'det_limit_color': '#DC2626',
    'det_limit_style': 'dash',
    'det_limit_width': 2,
    'det_limit_label': '',
    'element_colors': {},
    'display_mode': 'Side by Side',
    'sample_colors': {},
    'sample_name_mappings': {},
    'sample_order': [],
    'custom_titles': {},
    'custom_axis_labels': {},
    'sort_categories': 'No Sorting',
    'label_mode': 'Symbol',
    'min_particle_count': 0,
    'font_family': 'Times New Roman',
    'font_size': 18,
    'font_bold': False,
    'font_italic': False,
    'font_color': '#000000',
    'show_x_grid': False,
    'show_y_grid': False,
    'grid_alpha': 50,
}

_DISPLAY_MODE_ALIASES = {
    'Individual Subplots': 'Subplots by sample',
    'Grouped by Element': 'Subplots by isotope',
    'By Sample (Ordered)': 'Subplots by isotope',
}


# ── Helpers ────────────────────────────────────────────────────────────

def _y_label(cfg):
    base = BOX_LABEL_MAP.get(cfg.get('data_type_display', 'Counts'), 'Values')
    return BOX_LABEL_MAP.get(cfg.get('data_type_display', 'Counts'), 'Values')


def _element_color(element, index, cfg):
    return cfg.get('element_colors', {}).get(
        element, DEFAULT_ELEMENT_COLORS[index % len(DEFAULT_ELEMENT_COLORS)])


def _fmt_elem(elem, cfg):
    return format_element_label(elem, cfg.get('label_mode', 'Symbol'), Renderer.HTML)


def _is_multi(input_data):
    return (input_data and input_data.get('type') == 'multiple_sample_data')


def _available_elements(input_data):
    if not input_data:
        return []
    sel = input_data.get('selected_isotopes', [])
    if sel:
        return sort_elements_by_mass([i['label'] for i in sel])
    return []


def _filter_values(values, data_type, log_y, cfg=None):
    if data_type != 'Counts':
        vals = [v for v in values if v > 0 and not np.isnan(v)]
    else:
        vals = list(values)
    if not vals:
        return None
    if cfg and cfg.get('filter_outliers', False) and len(vals) > 3:
        arr = np.array(vals)
        pct = float(cfg.get('outlier_percentile', 99.0))
        lo, hi = np.percentile(arr, [100.0 - pct, pct])
        vals = list(arr[(arr >= lo) & (arr <= hi)])
    if not vals:
        return None
    if log_y:
        vals = list(np.log10(np.array(vals)))
    return vals


def _apply_box_overlays(plot_item, all_values_flat, cfg):
    """Apply horizontal band + detection limit + figure box to a finished plot."""
    shade_type = cfg.get('shade_type', 'None')
    if shade_type != 'None' and all_values_flat:
        arr = np.array(all_values_flat)
        lo = hi = None
        if shade_type == 'User-defined range':
            lo = float(cfg.get('shade_min', 0.0))
            hi = float(cfg.get('shade_max', 1.0))
        elif shade_type == 'Mean +/- 1 SD':
            mu, sd = float(np.mean(arr)), float(np.std(arr))
            lo, hi = mu - sd, mu + sd
        elif shade_type == 'Mean +/- 2 SD':
            mu, sd = float(np.mean(arr)), float(np.std(arr))
            lo, hi = mu - 2*sd, mu + 2*sd
        elif shade_type == 'Median +/- IQR  (Q1-Q3)':
            lo, hi = float(np.percentile(arr, 25)), float(np.percentile(arr, 75))
        elif shade_type == 'P5 - P95':
            lo, hi = float(np.percentile(arr, 5)), float(np.percentile(arr, 95))
        elif shade_type == 'P1 - P99':
            lo, hi = float(np.percentile(arr, 1)), float(np.percentile(arr, 99))
        if lo is not None and np.isfinite(lo) and np.isfinite(hi):
            _add_hband(plot_item, lo, hi,
                       color=cfg.get('shade_color', '#534AB7'),
                       alpha=cfg.get('shade_alpha', 0.18))
    _add_det_limit_h(plot_item, cfg)
    _apply_box(plot_item, cfg)


def _normalize_box_display_mode(mode):
    """Normalize legacy Box Plot display-mode values to supported UI modes.

    Preserved behavior:
        Keeps backward compatibility for older configs by mapping legacy
        mode names (``Individual Subplots``, ``Grouped by Element``, and
        ``By Sample (Ordered)``) to the current user-facing names
        (``Subplots by sample`` / ``Subplots by isotope``).
    """
    return _DISPLAY_MODE_ALIASES.get(mode, mode)


def _apply_boxplot_grid(plot_item, cfg):
    """Apply config-driven grid visibility to one Box Plot ``PlotItem``.

    This helper is used by every Box Plot draw branch so grid toggles from
    ``Plot format settings`` propagate uniformly across single-plot and
    multi-subplot layouts.
    """
    show_x = bool(cfg.get('show_x_grid', False))
    show_y = bool(cfg.get('show_y_grid', False))
    alpha = max(0.0, min(1.0, float(cfg.get('grid_alpha', 50)) / 255.0))
    plot_item.showGrid(x=show_x, y=show_y, alpha=alpha)


def _sort_box_category_records(records, sort_mode):
    """Return Box Plot display records in the requested display order.

    Args:
        records (list[dict]): Category display records containing at least
            ``sort_key``, ``display_label``, and ``sort_metric`` fields. When
            a record also carries a raw canonical isotope/element key in
            ``raw_key``, alphabetical sorting uses that scientific key rather
            than any rendered label text.
        sort_mode (str): Sort mode such as ``'No Sorting'``,
            ``'Ascending'``, ``'Descending'``, or ``'Alphabetical'``.

    Returns:
        list[dict]: Ordered category records for display only.

    Preserved behavior:
        This helper changes only rendered category order. It does not modify
        the underlying values, group membership, or computed statistics.
    """
    items = list(records or [])
    if sort_mode == 'Alphabetical':
        def _alphabetical_record_key(item):
            """Return the display-order key for Box Plot alphabetical sorting.

            Element/isotope categories must follow the raw scientific key so
            label mode changes such as ``Mass + Symbol`` or atomic notation do
            not change ordering. Other category types fall back to the generic
            stored sort key.
            """
            raw_key = item.get('raw_key')
            if raw_key is not None:
                return element_alphabetical_key(raw_key)
            return str(item.get('sort_key', '')).lower()

        return sorted(
            items,
            key=_alphabetical_record_key,
        )
    if sort_mode == 'Ascending':
        return sorted(items, key=lambda item: float(item.get('sort_metric', 0.0)))
    if sort_mode == 'Descending':
        return sorted(
            items,
            key=lambda item: float(item.get('sort_metric', 0.0)),
            reverse=True,
        )
    return items


def _sort_box_sample_records(records, sort_mode):
    """Return ``Subplots by isotope`` sample records in subplot display order.

    Args:
        records (list[dict]): Sample category records for one isotope subplot.
            Each record should include the raw sample key, visible display
            label, original subplot order, and optionally filtered plotted
            values.
        sort_mode (str): Active Box Plot sort mode.

    Returns:
        list[dict]: Ordered sample records for one isotope subplot.

    Preserved behavior:
        Sorting changes only the rendered x-axis/sample order inside the
        current isotope subplot. Raw sample keys remain canonical for lookup,
        and the filtered values used to compute box statistics are not changed.
    """
    items = list(records or [])
    if sort_mode == 'No Sorting':
        return sorted(items, key=lambda item: int(item.get('original_index', 0)))

    if sort_mode == 'Alphabetical':
        return sorted(
            items,
            key=lambda item: (
                str(item.get('display_label', '')).casefold(),
                str(item.get('raw_sample_name', '')).casefold(),
                int(item.get('original_index', 0)),
            ),
        )

    descending = (sort_mode == 'Descending')

    def _sample_metric_key(item):
        """Return a deterministic sort key for mean-based sample ordering."""
        mean_value = item.get('sort_metric')
        missing = mean_value is None
        numeric = 0.0 if missing else float(mean_value)
        ordered_value = -numeric if descending else numeric
        return (
            missing,
            ordered_value,
            str(item.get('display_label', '')).casefold(),
            str(item.get('raw_sample_name', '')).casefold(),
            int(item.get('original_index', 0)),
        )

    return sorted(items, key=_sample_metric_key)


# ── Settings Dialog ────────────────────────────────────────────────────

class BoxPlotSettingsDialog(QDialog):
    """Scope-aware settings dialog for Box Plot format or quantity controls."""

    preview_requested = Signal(dict)

    def __init__(self, cfg, input_data, parent=None, scope='all'):
        """
        Preserved behavior:
            Under ``all`` scope this dialog remains backward compatible with
            the legacy combined settings route. Scoped routes collect only
            relevant controls to avoid cross-overwrites.
        """
        super().__init__(parent)
        if scope == 'format':
            self.setWindowTitle("Box plot format settings")
        elif scope == 'quantities':
            self.setWindowTitle("Box plot quantities configuration")
        else:
            self.setWindowTitle("Distribution Plot Settings")
        self.setMinimumWidth(480)
        self._cfg = dict(cfg)
        self._input_data = input_data
        self._multi = _is_multi(input_data)
        self._samples = (input_data.get('sample_names', [])
                         if input_data else [])
        self._scope = scope

        self.shape_combo = None
        self.bw_spin = None
        self.jitter_spin = None
        self.dtype_combo = None
        self.mode_combo = None
        self.outliers_cb = None
        self.mean_cb = None
        self.median_cb = None
        self.stats_cb = None
        self.alpha_spin = None
        self.width_spin = None
        self.log_y_cb = None
        self.label_mode = None
        self.min_count = None
        self.y_min = None
        self.y_max = None
        self.auto_y = None
        self.filter_outliers_cb = None
        self.outlier_pct = None
        self.show_box_cb = None
        self.shade_combo = None
        self._shade_clr_btn = None
        self._shade_alpha = None
        self._shade_min = None
        self._shade_max = None
        self.show_det_cb = None
        self.det_val = None
        self.det_label_edit = None
        self._sample_edits = None
        self._order_list = None
        self._font_group = None
        self.show_x_grid_cb = None
        self.show_y_grid_cb = None
        self.grid_alpha_spin = None

        self._build_ui()

    def _build_ui(self):
        """Build settings widgets for the selected scope.

        ``scope='format'`` exposes visual controls (fonts/grid/overlays) that
        are applied via config + redraw to all Box Plot subplots. In
        multi-sample format scope, title text editing is intentionally not
        exposed here; a note explains that subplot titles are data-driven.
        """
        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        scroll.setWidget(inner)
        root.addWidget(scroll)

        if self._scope == 'all':
            g1 = QGroupBox("Plot Shape")
            f1 = QFormLayout(g1)
            self.shape_combo = QComboBox()
            self.shape_combo.addItems(PLOT_SHAPES)
            self.shape_combo.setCurrentText(
                self._cfg.get('plot_shape', PLOT_SHAPES[0]))
            f1.addRow("Shape:", self.shape_combo)
            self.bw_spin = QDoubleSpinBox()
            self.bw_spin.setRange(0.01, 2.0)
            self.bw_spin.setDecimals(2)
            self.bw_spin.setValue(self._cfg.get('violin_bandwidth', 0.2))
            f1.addRow("Violin Bandwidth:", self.bw_spin)
            self.jitter_spin = QDoubleSpinBox()
            self.jitter_spin.setRange(0.0, 0.5)
            self.jitter_spin.setDecimals(2)
            self.jitter_spin.setValue(self._cfg.get('strip_jitter', 0.2))
            f1.addRow("Strip Jitter:", self.jitter_spin)
            lay.addWidget(g1)

        if self._scope in ('all', 'quantities'):
            g2 = QGroupBox("Data Type")
            f2 = QFormLayout(g2)
            self.dtype_combo = QComboBox()
            self.dtype_combo.addItems(BOX_DATA_TYPES)
            self.dtype_combo.setCurrentText(
                self._cfg.get('data_type_display', BOX_DATA_TYPES[0]))
            f2.addRow("Type:", self.dtype_combo)
            lay.addWidget(g2)

        if self._multi and self._scope in ('all', 'quantities'):
            g_dm = QGroupBox("Multiple Sample Display")
            f_dm = QFormLayout(g_dm)
            self.mode_combo = QComboBox()
            self.mode_combo.addItems(BOX_DISPLAY_MODES)
            current_mode = _normalize_box_display_mode(
                self._cfg.get('display_mode', BOX_DISPLAY_MODES[0]))
            if current_mode not in BOX_DISPLAY_MODES:
                current_mode = BOX_DISPLAY_MODES[0]
            self.mode_combo.setCurrentText(current_mode)
            f_dm.addRow("Display Mode:", self.mode_combo)
            lay.addWidget(g_dm)

        if self._scope in ('all', 'format'):
            self._font_group = FontSettingsGroup(self._cfg)
            lay.addWidget(self._font_group.build())

            g_grid = QGroupBox("Grid")
            f_grid = QFormLayout(g_grid)
            self.show_x_grid_cb = QCheckBox()
            self.show_x_grid_cb.setChecked(self._cfg.get('show_x_grid', False))
            f_grid.addRow("Show X Grid:", self.show_x_grid_cb)
            self.show_y_grid_cb = QCheckBox()
            self.show_y_grid_cb.setChecked(self._cfg.get('show_y_grid', False))
            f_grid.addRow("Show Y Grid:", self.show_y_grid_cb)
            self.grid_alpha_spin = QSpinBox()
            self.grid_alpha_spin.setRange(0, 255)
            self.grid_alpha_spin.setValue(int(self._cfg.get('grid_alpha', 50)))
            f_grid.addRow("Grid Opacity (0-255):", self.grid_alpha_spin)
            lay.addWidget(g_grid)

            if self._multi:
                title_note = QLabel(
                    "Title text is managed per subplot in this display mode.")
                title_note.setWordWrap(True)
                title_note.setStyleSheet("color:#6B7280; font-size:11px;")
                lay.addWidget(title_note)

        g3 = QGroupBox("Plot Options")
        f3 = QFormLayout(g3)
        if self._scope in ('all', 'format'):
            if self._scope == 'all':
                self.outliers_cb = QCheckBox()
                self.outliers_cb.setChecked(self._cfg.get('show_outliers', True))
                f3.addRow("Show Outliers:", self.outliers_cb)
            self.mean_cb = QCheckBox()
            self.mean_cb.setChecked(self._cfg.get('show_mean', True))
            f3.addRow("Show Mean:", self.mean_cb)
            self.median_cb = QCheckBox()
            self.median_cb.setChecked(self._cfg.get('show_median', True))
            f3.addRow("Show Median:", self.median_cb)
            self.stats_cb = QCheckBox()
            self.stats_cb.setChecked(self._cfg.get('show_stats', False))
            f3.addRow("Show Statistics:", self.stats_cb)
            self.alpha_spin = QDoubleSpinBox()
            self.alpha_spin.setRange(0.1, 1.0)
            self.alpha_spin.setDecimals(1)
            self.alpha_spin.setValue(self._cfg.get('alpha', 0.7))
            f3.addRow("Transparency:", self.alpha_spin)
            self.width_spin = QDoubleSpinBox()
            self.width_spin.setRange(0.1, 2.0)
            self.width_spin.setDecimals(1)
            self.width_spin.setValue(self._cfg.get('plot_width', 0.8))
            f3.addRow("Plot Width:", self.width_spin)
            if self._scope == 'all':
                self.label_mode = QComboBox()
                self.label_mode.addItems(LABEL_MODES)
                self.label_mode.setCurrentText(
                    self._cfg.get('label_mode', 'Symbol'))
                f3.addRow("Isotope Label:", self.label_mode)
        if self._scope in ('all', 'quantities'):
            self.log_y_cb = QCheckBox()
            self.log_y_cb.setChecked(self._cfg.get('log_y', False))
            f3.addRow("Log Y-axis:", self.log_y_cb)
            self.min_count = QSpinBox()
            self.min_count.setRange(0, 100000)
            self.min_count.setValue(self._cfg.get('min_particle_count', 0))
            self.min_count.setSuffix(" particles")
            self.min_count.setToolTip(
                "Hide elements with fewer particles than this threshold.\n"
                "Set to 0 to show all elements.")
            f3.addRow("Min Particle Count:", self.min_count)
        if f3.rowCount() > 0:
            lay.addWidget(g3)

        if self._scope in ('all', 'quantities'):
            g4 = QGroupBox("Y-Axis Limits")
            f4 = QFormLayout(g4)
            row = QHBoxLayout()
            self.y_min = QDoubleSpinBox()
            self.y_min.setRange(-999999, 999999)
            self.y_min.setValue(self._cfg.get('y_min', 0))
            self.y_max = QDoubleSpinBox()
            self.y_max.setRange(-999999, 999999)
            self.y_max.setValue(self._cfg.get('y_max', 100))
            self.auto_y = QCheckBox("Auto")
            self.auto_y.setChecked(self._cfg.get('auto_y', True))
            self.auto_y.stateChanged.connect(lambda: (
                self.y_min.setEnabled(not self.auto_y.isChecked()),
                self.y_max.setEnabled(not self.auto_y.isChecked())))
            self.y_min.setEnabled(not self.auto_y.isChecked())
            self.y_max.setEnabled(not self.auto_y.isChecked())
            row.addWidget(self.y_min)
            row.addWidget(QLabel("to"))
            row.addWidget(self.y_max)
            row.addWidget(self.auto_y)
            f4.addRow("Y Range:", row)
            lay.addWidget(g4)

            if BrokenYAxisEditor is not None:
                self._broken_editor = BrokenYAxisEditor(
                    self._cfg, log_y_checkbox=self.log_y_cb)
                lay.addWidget(self._broken_editor)

        if self._scope in ('all', 'quantities'):
            g_filt = QGroupBox("Outlier Filtering")
            f_filt = QFormLayout(g_filt)
            self.filter_outliers_cb = QCheckBox()
            self.filter_outliers_cb.setChecked(self._cfg.get('filter_outliers', False))
            f_filt.addRow("Filter Outliers:", self.filter_outliers_cb)
            self.outlier_pct = QDoubleSpinBox()
            self.outlier_pct.setRange(90.0, 99.9); self.outlier_pct.setDecimals(1)
            self.outlier_pct.setValue(self._cfg.get('outlier_percentile', 99.0))
            f_filt.addRow("Keep Below Percentile:", self.outlier_pct)
            lay.addWidget(g_filt)

        if self._scope in ('all', 'format'):
            g_ov = QGroupBox("Statistical Overlays")
            f_ov = QFormLayout(g_ov)
            self.show_box_cb = QCheckBox()
            self.show_box_cb.setChecked(self._cfg.get('show_box', True))
            f_ov.addRow("Figure Box (frame):", self.show_box_cb)
            self.shade_combo = QComboBox()
            self.shade_combo.addItems(SHADE_TYPES + ['User-defined range'])
            self.shade_combo.setCurrentText(self._cfg.get('shade_type', 'None'))
            self.shade_combo.currentTextChanged.connect(self._on_shade_type_changed)
            f_ov.addRow("Horizontal Band:", self.shade_combo)

            shade_clr_row = QHBoxLayout()
            self._shade_color = self._cfg.get('shade_color', '#534AB7')
            self._shade_clr_btn = QPushButton(); self._shade_clr_btn.setFixedSize(26, 22)
            self._shade_clr_btn.setStyleSheet(f"background:{self._shade_color};")
            self._shade_clr_btn.clicked.connect(self._pick_shade_color)
            self._shade_alpha = QDoubleSpinBox()
            self._shade_alpha.setRange(0.01, 1.0); self._shade_alpha.setDecimals(2)
            self._shade_alpha.setValue(self._cfg.get('shade_alpha', 0.18))
            shade_clr_row.addWidget(self._shade_clr_btn)
            shade_clr_row.addWidget(QLabel("alpha:")); shade_clr_row.addWidget(self._shade_alpha)
            shade_clr_row.addStretch()
            f_ov.addRow("Band Color / alpha:", shade_clr_row)

            self._user_range_frame = QFrame()
            ur = QHBoxLayout(self._user_range_frame)
            ur.setContentsMargins(0, 0, 0, 0)
            self._shade_min = QDoubleSpinBox(); self._shade_min.setRange(-1e9, 1e9)
            self._shade_min.setDecimals(4); self._shade_min.setValue(self._cfg.get('shade_min', 0.0))
            self._shade_max = QDoubleSpinBox(); self._shade_max.setRange(-1e9, 1e9)
            self._shade_max.setDecimals(4); self._shade_max.setValue(self._cfg.get('shade_max', 1.0))
            ur.addWidget(QLabel("Min:")); ur.addWidget(self._shade_min)
            ur.addWidget(QLabel("Max:")); ur.addWidget(self._shade_max)
            ur.addStretch()
            f_ov.addRow("User Range:", self._user_range_frame)
            self._on_shade_type_changed(self.shade_combo.currentText())

            self.show_det_cb = QCheckBox()
            self.show_det_cb.setChecked(self._cfg.get('show_det_limit', False))
            f_ov.addRow("Detection Limit Line:", self.show_det_cb)
            self.det_val = QDoubleSpinBox()
            self.det_val.setRange(0.0, 999999999); self.det_val.setDecimals(4)
            self.det_val.setValue(self._cfg.get('det_limit_value', 1.0))
            f_ov.addRow("DL Value:", self.det_val)
            self.det_label_edit = QLineEdit(self._cfg.get('det_limit_label', ''))
            self.det_label_edit.setPlaceholderText("Auto  (e.g.  DL: 1.0)")
            f_ov.addRow("DL Label:", self.det_label_edit)
            lay.addWidget(g_ov)

        if self._multi and self._samples and self._scope in ('all', 'format'):
            g6 = QGroupBox("Sample Names")
            v6 = QVBoxLayout(g6)
            self._sample_edits = {}
            nm = dict(self._cfg.get('sample_name_mappings', {}))
            for sn in self._samples:
                h = QHBoxLayout()
                h.addWidget(QLabel(sn[:20]))
                ed = QLineEdit(nm.get(sn, sn))
                ed.setFixedWidth(200)
                h.addWidget(ed)
                self._sample_edits[sn] = ed
                rst = QPushButton("Reset")
                rst.setFixedHeight(22)
                rst.clicked.connect(
                    lambda _, o=sn: self._sample_edits[o].setText(o))
                h.addWidget(rst)
                h.addStretch()
                w = QWidget()
                w.setLayout(h)
                v6.addWidget(w)
            lay.addWidget(g6)

        if self._multi and self._samples and self._scope in ('all', 'quantities'):
            g7 = QGroupBox("Sample Display Order")
            v7 = QVBoxLayout(g7)
            hint = QLabel(
                "Drag or use Move up / Move down to reorder (useful for time series).")
            hint.setStyleSheet("color:#6B7280; font-size:10px;")
            hint.setWordWrap(True)
            v7.addWidget(hint)
            from PySide6.QtWidgets import QAbstractItemView as _AIV
            self._order_list = QListWidget()
            self._order_list.setMaximumHeight(130)
            self._order_list.setDragDropMode(_AIV.InternalMove)
            cur_order = self._cfg.get('sample_order', [])
            ordered = [s for s in cur_order if s in self._samples]
            ordered += [s for s in self._samples if s not in ordered]
            for s in ordered:
                self._order_list.addItem(s)
            v7.addWidget(self._order_list)
            btn_row = QHBoxLayout()
            up_btn = QPushButton("Move up")
            up_btn.setFixedWidth(82)
            up_btn.clicked.connect(self._move_up)
            dn_btn = QPushButton("Move down")
            dn_btn.setFixedWidth(92)
            dn_btn.clicked.connect(self._move_down)
            btn_row.addWidget(up_btn)
            btn_row.addWidget(dn_btn)
            btn_row.addStretch()
            v7.addLayout(btn_row)
            lay.addWidget(g7)

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
        root.addLayout(_btn_row)

    def _pick_shade_color(self):
        from PySide6.QtWidgets import QColorDialog
        from PySide6.QtGui import QColor
        c = QColorDialog.getColor(QColor(self._shade_color), self)
        if c.isValid():
            self._shade_color = c.name()
            self._shade_clr_btn.setStyleSheet(f"background:{self._shade_color};")

    def _on_shade_type_changed(self, text):
        is_user = (text == 'User-defined range')
        self._user_range_frame.setVisible(is_user)

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

    def collect(self):
        """Collect settings from the active scope without touching missing widgets.

        Returns:
            dict: Configuration updates for the selected scope.

        Preserved behavior:
            Scientific extraction semantics are unchanged. Under scoped usage,
            only created controls contribute values so unrelated keys are not
            overwritten by absent widgets.
        """
        d = {
        }
        if self.shape_combo is not None:
            d['plot_shape'] = self.shape_combo.currentText()
            d['violin_bandwidth'] = self.bw_spin.value()
            d['strip_jitter'] = self.jitter_spin.value()
        if self.dtype_combo is not None:
            d['data_type_display'] = self.dtype_combo.currentText()
        if self.outliers_cb is not None:
            d['show_outliers'] = self.outliers_cb.isChecked()
        if self.mean_cb is not None:
            d['show_mean'] = self.mean_cb.isChecked()
            d['show_median'] = self.median_cb.isChecked()
            d['show_stats'] = self.stats_cb.isChecked()
            d['alpha'] = self.alpha_spin.value()
            d['plot_width'] = self.width_spin.value()
        if self.label_mode is not None:
            d['label_mode'] = self.label_mode.currentText()
        if self.log_y_cb is not None:
            d['log_y'] = self.log_y_cb.isChecked()
            d['min_particle_count'] = self.min_count.value()
        if self.auto_y is not None:
            d['y_min'] = self.y_min.value()
            d['y_max'] = self.y_max.value()
            d['auto_y'] = self.auto_y.isChecked()
        if getattr(self, '_broken_editor', None) is not None:
            self._broken_editor.collect_into(d)
        if self.filter_outliers_cb is not None:
            d['filter_outliers'] = self.filter_outliers_cb.isChecked()
            d['outlier_percentile'] = self.outlier_pct.value()
        if self.show_box_cb is not None:
            d['show_box'] = self.show_box_cb.isChecked()
            d['shade_type'] = self.shade_combo.currentText()
            d['shade_color'] = self._shade_color
            d['shade_alpha'] = self._shade_alpha.value()
            d['shade_min'] = self._shade_min.value()
            d['shade_max'] = self._shade_max.value()
            d['show_det_limit'] = self.show_det_cb.isChecked()
            d['det_limit_value'] = self.det_val.value()
            d['det_limit_label'] = self.det_label_edit.text().strip()
        if self.mode_combo is not None:
            d['display_mode'] = _normalize_box_display_mode(
                self.mode_combo.currentText())
        if self._font_group is not None:
            d.update(self._font_group.collect())
        if self.show_x_grid_cb is not None:
            d['show_x_grid'] = self.show_x_grid_cb.isChecked()
            d['show_y_grid'] = self.show_y_grid_cb.isChecked()
            d['grid_alpha'] = self.grid_alpha_spin.value()
        if self._sample_edits is not None:
            d['sample_name_mappings'] = {
                k: v.text() for k, v in self._sample_edits.items()}
        if self._order_list is not None:
            d['sample_order'] = [
                self._order_list.item(i).text()
                for i in range(self._order_list.count())]
        return d


# ── Drawing helpers (PyQtGraph) ────────────────────────────────────────

def _tag_box_color_identity(item, cfg):
    """Tag a box rect with its colour identity so double-click edits persist.

    ``cfg['_box_identity']`` is a transient ``(key, role)`` set per series by
    ``_draw_single_element``; role is 'sample' or 'element'.
    """
    ident = cfg.get('_box_identity')
    if not ident:
        return
    key, role = ident
    setattr(item, '_color_identity_role', role)
    if role == 'sample':
        setattr(item, '_color_identity_key', key)
    else:
        setattr(item, '_raw_element_key', key)


def _draw_box(plot_item, x, values, color, alpha, width, cfg):
    if len(values) < 2:
        return
    q1, median, q3 = np.percentile(values, [25, 50, 75])
    iqr = q3 - q1
    co = QColor(color)

    box = pg.QtWidgets.QGraphicsRectItem(x - width/2, q1, width, q3 - q1)
    box.setBrush(pg.mkBrush(co.red(), co.green(), co.blue(), alpha))
    box.setPen(pg.mkPen(color, width=2))
    _tag_box_color_identity(box, cfg)
    plot_item.addItem(box)

    if cfg.get('show_median', True):
        plot_item.addItem(pg.PlotDataItem(
            [x - width/2, x + width/2], [median, median], pen=pg.mkPen('black', width=3)))

    lo = max(q1 - 1.5*iqr, min(values))
    hi = min(q3 + 1.5*iqr, max(values))
    wp = pg.mkPen('black', width=2)
    plot_item.addItem(pg.PlotDataItem([x, x], [q1, lo], pen=wp))
    plot_item.addItem(pg.PlotDataItem([x, x], [q3, hi], pen=wp))
    cw = width * 0.3
    plot_item.addItem(pg.PlotDataItem([x-cw/2, x+cw/2], [lo, lo], pen=wp))
    plot_item.addItem(pg.PlotDataItem([x-cw/2, x+cw/2], [hi, hi], pen=wp))

    if cfg.get('show_outliers', True):
        outliers = [v for v in values if v < q1 - 1.5*iqr or v > q3 + 1.5*iqr]
        if outliers:
            plot_item.addItem(pg.ScatterPlotItem(
                x=[x]*len(outliers), y=outliers, pen=pg.mkPen('black'),
                brush=pg.mkBrush('red'), size=6, symbol='o'))

    if cfg.get('show_mean', True):
        plot_item.addItem(pg.ScatterPlotItem(
            x=[x], y=[np.mean(values)], pen=pg.mkPen('white', width=2),
            brush=pg.mkBrush('blue'), size=8, symbol='s'))


def _draw_violin(plot_item, x, values, color, alpha, width, cfg):
    if len(values) < 2:
        return
    try:
        bw = cfg.get('violin_bandwidth', 0.2)
        kde = gaussian_kde(values, bw_method=bw)
        ymin, ymax = min(values), max(values)
        yr = ymax - ymin
        yv = np.linspace(ymin - 0.1*yr, ymax + 0.1*yr, 100)
        d = kde(yv)
        mx = np.max(d)
        nd = (d / mx * width/2) if mx > 0 else np.zeros_like(d)
        co = QColor(color)
        ha = alpha // 2

        plot_item.addItem(pg.PlotDataItem(x=x - nd, y=yv, pen=pg.mkPen(color, width=2),
            fillLevel=x, brush=pg.mkBrush(co.red(), co.green(), co.blue(), ha)))
        plot_item.addItem(pg.PlotDataItem(x=x + nd, y=yv, pen=pg.mkPen(color, width=2),
            fillLevel=x, brush=pg.mkBrush(co.red(), co.green(), co.blue(), ha)))

        q1, med, q3 = np.percentile(values, [25, 50, 75])
        if cfg.get('show_median', True):
            plot_item.addItem(pg.PlotDataItem(
                [x - width/4, x + width/4], [med, med], pen=pg.mkPen('white', width=4)))
        plot_item.addItem(pg.PlotDataItem(
            [x - width/6, x + width/6], [q1, q1], pen=pg.mkPen('white', width=2)))
        plot_item.addItem(pg.PlotDataItem(
            [x - width/6, x + width/6], [q3, q3], pen=pg.mkPen('white', width=2)))

        if cfg.get('show_mean', True):
            plot_item.addItem(pg.ScatterPlotItem(
                x=[x], y=[np.mean(values)], pen=pg.mkPen('white', width=2),
                brush=pg.mkBrush('red'), size=8, symbol='d'))
    except Exception:
        _itk_log.exception("Handled exception in _draw_violin")
        _draw_box(plot_item, x, values, color, alpha, width, cfg)


def _draw_box_violin(plot_item, x, values, color, alpha, width, cfg):
    _draw_violin(plot_item, x, values, color, alpha // 2, width, cfg)
    box_cfg = dict(cfg); box_cfg['show_median'] = True; box_cfg['show_mean'] = False
    _draw_box(plot_item, x, values, color, alpha, width * 0.3, box_cfg)


def _draw_strip(plot_item, x, values, color, alpha, width, cfg):
    jitter = cfg.get('strip_jitter', 0.2)
    np.random.seed(42)
    xj = x + np.random.uniform(-jitter, jitter, len(values))
    co = QColor(color)
    plot_item.addItem(pg.ScatterPlotItem(
        x=xj, y=values, pen=pg.mkPen(color),
        brush=pg.mkBrush(co.red(), co.green(), co.blue(), alpha), size=6, symbol='o'))
    if cfg.get('show_mean', True):
        plot_item.addItem(pg.PlotDataItem(
            [x - width/2, x + width/2], [np.mean(values)]*2, pen=pg.mkPen('red', width=3)))
    if cfg.get('show_median', True):
        plot_item.addItem(pg.PlotDataItem(
            [x - width/2, x + width/2], [np.median(values)]*2, pen=pg.mkPen('blue', width=2)))


def _draw_half_violin_box(plot_item, x, values, color, alpha, width, cfg):
    co = QColor(color)
    try:
        bw = cfg.get('violin_bandwidth', 0.2)
        kde = gaussian_kde(values, bw_method=bw)
        ymin, ymax = min(values), max(values)
        yr = ymax - ymin
        yv = np.linspace(ymin - 0.1*yr, ymax + 0.1*yr, 100)
        d = kde(yv)
        mx = np.max(d)
        nd = (d / mx * width/2) if mx > 0 else np.zeros_like(d)
        plot_item.addItem(pg.PlotDataItem(x=x - nd, y=yv, pen=pg.mkPen(color, width=2),
            fillLevel=x, brush=pg.mkBrush(co.red(), co.green(), co.blue(), alpha // 2)))
    except Exception:
        _itk_log.exception("Handled exception in _draw_half_violin_box")

    q1, med, q3 = np.percentile(values, [25, 50, 75])
    box = pg.QtWidgets.QGraphicsRectItem(x, q1, width/2, q3 - q1)
    box.setBrush(pg.mkBrush(co.red(), co.green(), co.blue(), alpha))
    box.setPen(pg.mkPen(color, width=2))
    plot_item.addItem(box)
    if cfg.get('show_median', True):
        plot_item.addItem(pg.PlotDataItem(
            [x, x + width/2], [med, med], pen=pg.mkPen('black', width=3)))


def _draw_notched_box(plot_item, x, values, color, alpha, width, cfg):
    q1, med, q3 = np.percentile(values, [25, 50, 75])
    iqr = q3 - q1
    n = len(values)
    ne = 1.57 * iqr / np.sqrt(n) if n > 0 else 0
    nl, nu = med - ne, med + ne
    nw = width * 0.3
    co = QColor(color)

    pts = [(x - width/2, q1), (x + width/2, q1), (x + width/2, nl),
           (x + nw/2, med), (x + width/2, nu), (x + width/2, q3),
           (x - width/2, q3), (x - width/2, nu), (x - nw/2, med), (x - width/2, nl)]
    xc = [p[0] for p in pts] + [pts[0][0]]
    yc = [p[1] for p in pts] + [pts[0][1]]
    plot_item.addItem(pg.PlotDataItem(x=xc, y=yc, pen=pg.mkPen(color, width=2),
        brush=pg.mkBrush(co.red(), co.green(), co.blue(), alpha)))

    if cfg.get('show_median', True):
        plot_item.addItem(pg.PlotDataItem(
            [x - nw/2, x + nw/2], [med, med], pen=pg.mkPen('black', width=3)))

    lo = max(q1 - 1.5*iqr, min(values))
    hi = min(q3 + 1.5*iqr, max(values))
    wp = pg.mkPen('black', width=2)
    plot_item.addItem(pg.PlotDataItem([x, x], [q1, lo], pen=wp))
    plot_item.addItem(pg.PlotDataItem([x, x], [q3, hi], pen=wp))


def _draw_bar_errors(plot_item, x, values, color, alpha, width, cfg):
    mean_v = np.mean(values)
    sem = np.std(values) / np.sqrt(len(values))
    co = QColor(color)

    bar = pg.QtWidgets.QGraphicsRectItem(x - width/2, 0, width, mean_v)
    bar.setBrush(pg.mkBrush(co.red(), co.green(), co.blue(), alpha))
    bar.setPen(pg.mkPen(color, width=2))
    plot_item.addItem(bar)

    ep = pg.mkPen('black', width=2)
    cw = width * 0.3
    for sign in [1, -1]:
        ev = mean_v + sign * sem
        if sign == -1:
            ev = max(0, ev)
        plot_item.addItem(pg.PlotDataItem([x, x], [mean_v, ev], pen=ep))
        plot_item.addItem(pg.PlotDataItem([x - cw/2, x + cw/2], [ev, ev], pen=ep))


_SHAPE_DRAWERS = {
    'Box Plot (Traditional)': _draw_box,
    'Violin Plot': _draw_violin,
    'Box + Violin (Overlay)': _draw_box_violin,
    'Strip Plot (Dots)': _draw_strip,
    'Half Violin + Half Box': _draw_half_violin_box,
    'Notched Box Plot': _draw_notched_box,
    'Bar Plot with Error Bars': _draw_bar_errors,
}


def _draw_single_element(plot_item, x, values, sample_name, element, cfg, is_multi):
    """Dispatch one series to the configured Box Plot shape drawer.
    Preserved behavior:
        In combined multi-sample modes (``is_multi=True``), color identity
        remains sample-based. In single-sample/per-sample panels
        (``is_multi=False``), color identity remains element/isotope-based.
    """
    if len(values) < 2:
        return
    sc = cfg.get('sample_colors', {})
    ec = cfg.get('element_colors', {})
    if is_multi:
        color = sc.get(sample_name, DEFAULT_SAMPLE_COLORS[0])
    else:
        color = ec.get(element, DEFAULT_ELEMENT_COLORS[0])
    alpha = int(cfg.get('alpha', 0.7) * 255)
    width = cfg.get('plot_width', 0.8)
    shape = cfg.get('plot_shape', PLOT_SHAPES[0])
    drawer = _SHAPE_DRAWERS.get(shape, _draw_box)
    dcfg = dict(cfg)
    dcfg['_box_identity'] = (
        (sample_name, 'sample') if is_multi else (element, 'element'))
    drawer(plot_item, x, values, color, alpha, width, dcfg)


def _add_empty_panel_message(plot_item, message="No valid data"):
    """Add a small, panel-local empty-state note for subplot readability.

    This message is used when filtering/min-count/log transforms leave a
    sample panel with no drawable element distributions. It preserves all
    scientific settings and only communicates that the current panel has no
    valid plotted values.
    """
    txt = pg.TextItem(message, anchor=(0.5, 0.5), color='gray')
    plot_item.addItem(txt)
    txt.setPos(0.5, 0.5)


def _add_stats_text(plot_item, plot_data, cfg):
    """Add statistics text box."""
    dt = cfg.get('data_type_display', 'Counts')
    shape = cfg.get('plot_shape', PLOT_SHAPES[0])
    lines = [f"Statistics ({dt}):", f"Plot: {shape}"]
    for el, vals in plot_data.items():
        if not vals:
            continue
        fv = [v for v in vals if v > 0 and not np.isnan(v)] if dt != 'Counts' else vals
        if not fv:
            continue
        n = len(fv)
        mu, med = np.mean(fv), np.median(fv)
        q1, q3 = np.percentile(fv, [25, 75])
        sd = np.std(fv)
        if 'Mass' in dt:
            lines.append(f"{el}: {n} particles")
            lines.append(f"  Mean: {mu:.2f}±{sd:.2f} fg, Median: {med:.2f} (Q1:{q1:.2f}, Q3:{q3:.2f})")
        elif 'Moles' in dt:
            lines.append(f"{el}: {n} particles")
            lines.append(f"  Mean: {mu:.4f}±{sd:.4f} fmol, Median: {med:.4f} (Q1:{q1:.4f}, Q3:{q3:.4f})")
        elif 'Diameter' in dt:
            lines.append(f"{el}: {n} particles")
            lines.append(f"  Mean: {mu:.1f}±{sd:.1f} nm, Median: {med:.1f} (Q1:{q1:.1f}, Q3:{q3:.1f})")
        else:
            lines.append(f"{el}: {n} particles")
            lines.append(f"  Mean: {mu:.1f}±{sd:.1f}, Median: {med:.1f} (Q1:{q1:.1f}, Q3:{q3:.1f})")

    txt = pg.TextItem('\n'.join(lines), anchor=(0, 1),
                      border=pg.mkPen('black', width=1),
                      fill=pg.mkBrush(255, 255, 255, 200))
    plot_item.addItem(txt)
    try:
        vb = plot_item.getViewBox().state['viewRange']
        txt.setPos(vb[0][0] + 0.02*(vb[0][1]-vb[0][0]),
                   vb[1][0] + 0.98*(vb[1][1]-vb[1][0]))
    except Exception:
        _itk_log.exception("Handled exception in _add_stats_text")
        txt.setPos(0.02, 0.98)


# ── Display Dialog ─────────────────────────────────────────────────────

class BoxPlotDisplayDialog(QDialog):
    """Main dialog with PyQtGraph plot and right-click context menu."""

    def __init__(self, node, parent_window=None):
        super().__init__(parent_window)
        self.node = node
        self._subplot_context_by_plotitem = {}
        self.setWindowTitle("Particle Data Distribution Plot Analysis")
        self.setMinimumSize(1100, 750)

        pg.setConfigOptions(antialias=True, useOpenGL=False)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _build_ui(self):
        """Build plot canvas, stats row, and standardized bottom action buttons.

        Preserved behavior:
            Plot calculations and extraction logic are unchanged. This only
            adds homogenized UI routing for format, quantities, reset, and
            export actions.
        """
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        self._stats = QLabel("")
        self._stats.setStyleSheet("color:#6B7280; font-size:11px; padding:2px 6px;")
        lay.addWidget(self._stats)

        self.pw = EnhancedGraphicsLayoutWidget()
        self.pw.setBackground('w')
        self.pw.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pw.customContextMenuRequested.connect(self._ctx_menu)
        lay.addWidget(self.pw, stretch=1)

        bb = QHBoxLayout()
        bb.setContentsMargins(0, 0, 0, 0)
        btn_fmt = QPushButton("Plot format settings")
        btn_fmt.clicked.connect(self._open_plot_format_settings)
        btn_qty = QPushButton("Configure plot quantities")
        btn_qty.clicked.connect(self._open_configure_plot_quantities)
        btn_reset = QPushButton("Reset layout")
        btn_reset.setToolTip("Reset plot ranges to automatic view.")
        btn_reset.clicked.connect(self._reset_layout)
        btn_export = QPushButton("Export figure")
        btn_export.clicked.connect(self._export_figure)
        bb.addWidget(btn_fmt)
        bb.addWidget(btn_qty)
        bb.addWidget(btn_reset)
        bb.addWidget(btn_export)
        lay.addLayout(bb)


    def _ctx_menu(self, pos):
        """Show Box Plot custom right-click menu with Box-specific quick actions.

        Preserved behavior:
            Keeps only lightweight visual toggles plus Box-specific ``Plot
            Shape`` and ``Show Outliers`` actions in right-click. Quantity,
            reset, and export workflows are routed through bottom buttons.
        """
        cfg = self.node.config
        display_mode = _normalize_box_display_mode(
            cfg.get('display_mode', 'Side by Side'))
        clicked_plot = self._plot_item_at(pos)
        subplot_ctx = self._subplot_context_by_plotitem.get(clicked_plot)
        if clicked_plot is not None and subplot_ctx is None:
            try:
                scene_pos = self.pw.mapToScene(pos)
                for pi, ctx in self._subplot_context_by_plotitem.items():
                    try:
                        rect = pi.mapRectToScene(pi.boundingRect())
                    except Exception:
                        _itk_log.exception("Handled exception in _ctx_menu")
                        continue
                    if rect.contains(scene_pos):
                        clicked_plot = pi
                        subplot_ctx = ctx
                        break
            except Exception:
                _itk_log.exception("Handled exception in _ctx_menu")
        menu = QMenu(self)

        tm = menu.addMenu("Quick Toggles")
        for key, label, default in [
            ('show_mean',       'Show Mean',            True),
            ('show_median',     'Show Median',          True),
            ('show_stats',      'Show Statistics',      False),
            ('show_box',        'Figure Box (frame)',   True),
            ('show_det_limit',  'Detection Limit Line', False),
        ]:
            a = tm.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, default))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        lm = menu.addMenu("Isotope Label")
        for label_mode in LABEL_MODES:
            a = lm.addAction(label_mode); a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == label_mode)
            a.triggered.connect(
                lambda _, v=label_mode: self._set('label_mode', v))

        sm = menu.addMenu("Plot Shape")
        for s in PLOT_SHAPES:
            a = sm.addAction(s); a.setCheckable(True)
            a.setChecked(cfg.get('plot_shape') == s)
            a.triggered.connect(lambda _, v=s: self._set('plot_shape', v))

        sort_menu = menu.addMenu("Sort Categories")
        current_sort = cfg.get('sort_categories', BOX_SORT_OPTIONS[0])
        for sort_mode in BOX_SORT_OPTIONS:
            a = sort_menu.addAction(sort_mode)
            a.setCheckable(True)
            a.setChecked(sort_mode == current_sort)
            a.triggered.connect(
                lambda _, v=sort_mode: self._set('sort_categories', v))

        show_outliers = menu.addAction("Show Outliers")
        show_outliers.setCheckable(True)
        show_outliers.setChecked(cfg.get('show_outliers', True))
        show_outliers.triggered.connect(lambda _: self._toggle('show_outliers'))

        can_export_subplot = (
            display_mode == 'Subplots by isotope'
            and clicked_plot is not None
            and subplot_ctx is not None
        )
        if can_export_subplot:
            exp_act = menu.addAction("Export this subplot...")
            exp_act.triggered.connect(
                lambda _: self._export_subplot(clicked_plot, subplot_ctx))
        else:
            exp_act = menu.addAction("Export this subplot... (unavailable here)")
            exp_act.setEnabled(False)
            hint = "Right-click a subplot panel to export only that panel."
            exp_act.setToolTip(hint)
            exp_act.setStatusTip(hint)
        menu.addSeparator()
        act_copy_fig = menu.addAction("Copy figure")
        act_copy_fig.triggered.connect(
            lambda: copy_figure_to_clipboard(self.pw))
        menu.exec(self.pw.mapToGlobal(pos))

    def _plot_item_at(self, pos):
        """Resolve the clicked subplot via ``mapRectToScene`` hit testing.

        ``customContextMenuRequested`` provides widget coordinates. This helper
        maps to scene coordinates and checks each ``pg.PlotItem`` using
        ``item.mapRectToScene(item.boundingRect())`` to mirror the working
        Histogram decomposition behavior. This avoids fragile
        ``sceneBoundingRect()`` mismatches seen in some Box Plot layouts.
        """
        try:
            scene_pos = self.pw.mapToScene(pos)
        except Exception:
            _itk_log.exception("Handled exception in _plot_item_at")
            return None
        for item in self.pw.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    rect = item.mapRectToScene(item.boundingRect())
                except Exception:
                    _itk_log.exception("Handled exception in _plot_item_at")
                    continue
                if rect is not None and rect.contains(scene_pos):
                    return item
        return None

    @staticmethod
    def _sanitize_filename_part(value):
        """Convert subplot context text into a filesystem-safe token."""
        if value is None:
            return "subplot"
        text = str(value).strip()
        if not text:
            return "subplot"
        keep = []
        for ch in text:
            if ch.isalnum() or ch in ("-", "_"):
                keep.append(ch)
            elif ch.isspace():
                keep.append("_")
        cleaned = "".join(keep).strip("_")
        return cleaned or "subplot"

    def _export_subplot(self, plot_item, subplot_ctx):
        """Export one already-rendered Box Plot subplot using shared workflow.

        The export dialog/options are reused from ``download_pyqtgraph_figure``
        so format/resolution behavior remains consistent with full-figure
        export. Only the clicked ``PlotItem`` is targeted when available.
        """
        raw_elem = subplot_ctx.get('element') if subplot_ctx else None
        title = subplot_ctx.get('title') if subplot_ctx else None
        stem = (
            f"boxplot_{self._sanitize_filename_part(raw_elem or title)}_by_sample"
        )
        download_pyqtgraph_figure(
            self.pw,
            self,
            default_name=stem or "subplot_export",
            export_item=plot_item,
        )

    def _toggle(self, key):
        self.node.config[key] = not self.node.config.get(key, False)
        self._refresh()

    def _set(self, key, value):
        self.node.config[key] = value
        self._refresh()

    def _open_settings(self, scope='all', title_override=None):
        """Open scoped Box Plot settings dialog and apply updates on accept.

        Args:
            scope (str): ``'format'``, ``'quantities'``, or ``'all'``.
            title_override (str | None): Optional explicit window title.

        Preserved behavior:
            Reuses existing Box Plot settings schema while allowing scoped
            routes for homogenized bottom-button workflows.
        """
        _snap = dict(self.node.config)
        dlg = BoxPlotSettingsDialog(
            self.node.config, self.node.input_data, self, scope=scope)
        if title_override:
            dlg.setWindowTitle(title_override)
        dlg.preview_requested.connect(lambda cfg: (self.node.config.update(cfg), self._refresh()))
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()
        else:
            self.node.config.clear()
            self.node.config.update(_snap)
            self._refresh()

    def _open_plot_settings(self):
        """Open rich PyQtGraph visual settings dialog bound to one PlotItem.

        This route exposes shared PlotSettings controls (fonts, colors, grid,
        title/axis styling, and trace appearance) for Box Plot presentation.
        It is intentionally single-plot and therefore not used for
        multi-subplot homogenized formatting.
        """
        if not _CUSTOM_PLOT_AVAILABLE or _PlotSettingsDialog is None \
                or _PlotWidgetAdapter is None:
            return
        pi = next(
            (item for item in self.pw.scene().items()
             if isinstance(item, pg.PlotItem)),
            None,
        )
        if pi is not None:
            dlg = _PlotSettingsDialog(
                _PlotWidgetAdapter(self.pw, pi),
                self,
                show_apply=False,
            )
            dlg.setWindowTitle("Box plot format settings")
            dlg.exec()

    def _open_plot_format_settings(self):
        """Open Box Plot visual format settings in a config-driven route.

        Preserved behavior:
            Keeps scientific/data quantity configuration in the separate
            quantities dialog while this route focuses on visual formatting.
            In multi-subplot modes this route applies style through config and
            redraw so axis/tick/title style updates propagate to every panel
            without binding to a single PlotItem.
        """
        self._open_settings(
            scope='format',
            title_override="Box plot format settings",
        )

    def _open_configure_plot_quantities(self):
        """Open quantity/data Box Plot settings routed from bottom button."""
        self._open_settings(
            scope='quantities',
            title_override="Box plot quantities configuration",
        )

    def _export_figure(self):
        """Export the current Box Plot figure using the existing helper."""
        download_pyqtgraph_figure(self.pw, self, "distribution_plot.png")

    def _disable_native_pyqtgraph_context_menu(self):
        """Disable native PyQtGraph menus locally for Box Plot dialog only.

        Preserved behavior:
            Prevents stacked native menus while leaving global PyQtGraph menu
            behavior for other plot types unchanged.
        """
        for item in self.pw.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    item.setMenuEnabled(False)
                except Exception:
                    _itk_log.exception("Handled exception in _disable_native_pyqtgraph_context_menu")
                try:
                    vb = item.getViewBox()
                    if vb is not None:
                        vb.setMenuEnabled(False)
                except Exception:
                    _itk_log.exception("Handled exception in _disable_native_pyqtgraph_context_menu")

    def _reset_layout(self):
        """Reset Box Plot view ranges to auto layout without changing data.

        Preserved behavior:
            Keeps scientific settings (data type, filtering, display mode,
            shape, and label mode) intact; only view range state is reset.
        """
        self.node.config['auto_y'] = True
        for item in self.pw.scene().items():
            if isinstance(item, pg.PlotItem):
                try:
                    item.enableAutoRange(axis='xy', enable=True)
                    vb = item.getViewBox()
                    if vb is not None:
                        vb.autoRange()
                except Exception:
                    _itk_log.exception("Handled exception in _reset_layout")
        self._refresh()

    def _get_custom_title_map(self):
        """Return the canonical custom-title mapping for this Box Plot dialog.

        Returns:
            dict: Mutable mapping of stable raw plot keys to display-only
                custom title overrides.
        """
        custom_titles = self.node.config.get('custom_titles')
        if not isinstance(custom_titles, dict):
            custom_titles = {}
            self.node.config['custom_titles'] = custom_titles
        return custom_titles

    @staticmethod
    def _title_key_for_combined_plot(is_multi):
        """Return the stable custom-title key for one combined Box Plot.

        Args:
            is_multi (bool): Whether the current Box Plot is multi-sample.

        Returns:
            str: Stable raw key for the combined plot title override.
        """
        return 'combined:multi' if is_multi else 'combined:single'

    @staticmethod
    def _title_key_for_sample_plot(sample_name):
        """Return the stable custom-title key for one sample subplot.

        Args:
            sample_name (str): Canonical raw sample key.

        Returns:
            str: Stable raw key for the corresponding sample subplot.
        """
        return f'sample:{sample_name}'

    @staticmethod
    def _title_key_for_element_plot(raw_element_key):
        """Return the stable custom-title key for one element subplot.

        Args:
            raw_element_key (str): Canonical raw element/isotope key.

        Returns:
            str: Stable raw key for the corresponding element subplot.
        """
        return f'element:{raw_element_key}'

    def _effective_title_for_key(self, plot_key, default_title=''):
        """Resolve the effective title for one Box Plot panel key.

        Args:
            plot_key (str): Stable raw key for the target plot panel.
            default_title (str): Default title used when no override exists.

        Returns:
            str: Display title text to render for the target plot panel.
        """
        custom_title = self._get_custom_title_map().get(plot_key)
        if isinstance(custom_title, str):
            stripped = custom_title.strip()
            if stripped:
                return stripped
        return default_title or ''

    def _apply_title_text_to_plot(self, plot_item, title_text):
        """Apply a Box Plot title while preserving the current title styling.

        Args:
            plot_item (Any): Target ``pg.PlotItem``.
            title_text (str): Effective title text to render.
        """
        apply_plot_title_style(plot_item, title_text, config=self.node.config)

    def _store_custom_title_text(self, plot_key, title_text):
        """Store or clear one display-only Box Plot title override.

        Args:
            plot_key (str): Stable raw key for the target plot panel.
            title_text (str): User-entered display title text.
        """
        clean_text = (title_text or '').strip()
        custom_titles = dict(self._get_custom_title_map())
        if clean_text:
            custom_titles[plot_key] = clean_text
        else:
            custom_titles.pop(plot_key, None)
        self.node.config['custom_titles'] = custom_titles

    def _apply_custom_title_edit(self, plot_item, plot_key, title_text,
                                 default_title=''):
        """Persist one Box Plot title edit and reapply the effective title.

        Args:
            plot_item (Any): Target ``pg.PlotItem`` whose title was edited.
            plot_key (str): Stable raw key for the target plot panel.
            title_text (str): User-entered display title text.
            default_title (str): Default title used when the override is
                cleared or blank.
        """
        self._store_custom_title_text(plot_key, title_text)
        self._apply_title_text_to_plot(
            plot_item, self._effective_title_for_key(plot_key, default_title))

    def _configure_plot_title(self, plot_item, plot_key, default_title=''):
        """Bind text-only title editing and render the effective Box Plot title.

        Args:
            plot_item (Any): Target ``pg.PlotItem``.
            plot_key (str): Stable raw key for the target plot panel.
            default_title (str): Default title used when no override exists.
        """
        def _title_apply_callback(text, _plot_item=plot_item, _plot_key=plot_key,
                                  _default_title=default_title):
            """Persist one Box Plot title edit for the associated plot item."""
            self._apply_custom_title_edit(
                _plot_item, _plot_key, text, _default_title)

        plot_item._title_editor_options = {
            'text_only': True,
            'title_apply_callback': _title_apply_callback,
        }
        self._apply_title_text_to_plot(
            plot_item, self._effective_title_for_key(plot_key, default_title))

    def _get_custom_axis_label_map(self):
        """Return the canonical custom axis-label mapping for this Box Plot.

        Returns:
            dict: Mutable mapping of stable raw plot keys to per-axis
                display-only label overrides.
        """
        custom_axis_labels = self.node.config.get('custom_axis_labels')
        if not isinstance(custom_axis_labels, dict):
            custom_axis_labels = {}
            self.node.config['custom_axis_labels'] = custom_axis_labels
        return custom_axis_labels

    def _effective_axis_labels_for_key(self, plot_key, default_axis_labels):
        """Resolve effective bottom/left axis labels for one Box Plot key.

        Args:
            plot_key (str): Stable raw key for the target plot panel.
            default_axis_labels (dict): Default axis-label mapping with
                ``bottom`` and ``left`` entries.

        Returns:
            dict: Effective axis-label mapping for the target plot panel.
        """
        resolved = {
            axis_name: {
                'text': (info or {}).get('text', ''),
                'units': (info or {}).get('units', None),
            }
            for axis_name, info in (default_axis_labels or {}).items()
        }
        stored = self._get_custom_axis_label_map().get(plot_key, {})
        if not isinstance(stored, dict):
            return resolved
        for axis_name in ('bottom', 'left'):
            axis_info = stored.get(axis_name, {})
            if not isinstance(axis_info, dict):
                continue
            custom_text = (axis_info.get('text') or '').strip()
            if custom_text:
                resolved[axis_name] = {
                    'text': custom_text,
                    'units': axis_info.get('units', None),
                }
        return resolved

    def _store_custom_axis_label(self, plot_key, axis_name, text, units):
        """Store or clear one display-only Box Plot axis-label override.

        Args:
            plot_key (str): Stable raw key for the target plot panel.
            axis_name (str): Axis identifier such as ``'bottom'`` or
                ``'left'``.
            text (str): User-entered axis-label text.
            units (str | None): Optional units text from the editor.
        """
        clean_text = (text or '').strip()
        custom_axis_labels = dict(self._get_custom_axis_label_map())
        plot_labels = dict(custom_axis_labels.get(plot_key, {}))
        if clean_text:
            plot_labels[axis_name] = {
                'text': clean_text,
                'units': units,
            }
        else:
            plot_labels.pop(axis_name, None)
        if plot_labels:
            custom_axis_labels[plot_key] = plot_labels
        else:
            custom_axis_labels.pop(plot_key, None)
        self.node.config['custom_axis_labels'] = custom_axis_labels

    def _apply_effective_axis_labels(self, plot_item, plot_key,
                                     default_axis_labels):
        """Apply effective Box Plot axis labels and persistence callbacks.

        Args:
            plot_item (Any): Target ``pg.PlotItem``.
            plot_key (str): Stable raw key for the target plot panel.
            default_axis_labels (dict): Default axis-label mapping with
                ``bottom`` and ``left`` entries.
        """
        effective_labels = self._effective_axis_labels_for_key(
            plot_key, default_axis_labels)

        def _make_axis_callback(axis_name):
            """Build one Box Plot axis-label persistence callback."""
            def _axis_apply_callback(text, units, _axis_name=axis_name):
                """Persist one Box Plot axis-label content edit."""
                self._store_custom_axis_label(
                    plot_key, _axis_name, text, units)
            return _axis_apply_callback

        plot_item._axis_label_editor_options = {
            'bottom': {'axis_apply_callback': _make_axis_callback('bottom')},
            'left': {'axis_apply_callback': _make_axis_callback('left')},
        }
        plot_item._custom_axis_labels = {
            axis_name: {
                'text': axis_info.get('text', ''),
                'units': axis_info.get('units', None),
            }
            for axis_name, axis_info in effective_labels.items()
        }
        for axis_name in ('bottom', 'left'):
            axis_info = effective_labels.get(axis_name, {})
            apply_axis_label_style(
                plot_item,
                axis_name,
                axis_info.get('text', ''),
                units=axis_info.get('units', None),
                config=self.node.config,
            )

    @staticmethod
    def _category_sort_mode(cfg):
        """Return the active Box Plot category sort mode.

        Args:
            cfg (dict): Active Box Plot configuration.

        Returns:
            str: One of the supported Box Plot category sort modes.
        """
        sort_mode = cfg.get('sort_categories', BOX_SORT_OPTIONS[0])
        if sort_mode not in BOX_SORT_OPTIONS:
            return BOX_SORT_OPTIONS[0]
        return sort_mode


    def _refresh(self):
        """Rebuild the Box Plot from extracted data and current config.

        Preserved behavior:
            Data-type switching remains scientifically correct because redraw
            always calls ``BoxPlotNode.extract_plot_data()`` with current
            ``data_type_display``. This method additionally reapplies local
            native-menu suppression after each redraw. Legacy display-mode
            config values are normalized here so older names render through
            ``Subplots by sample`` / ``Subplots by isotope``.
        """
        try:
            self.pw.clear()
            self._subplot_context_by_plotitem = {}
            plot_data = self.node.extract_plot_data()
            if not plot_data:
                pi = self.pw.addPlot()
                t = pg.TextItem("No particle data available\nConnect to Sample Selector",
                                anchor=(0.5, 0.5), color='gray')
                pi.addItem(t); t.setPos(0.5, 0.5)
                pi.hideAxis('left'); pi.hideAxis('bottom')
                self._stats.setText("")
                return

            cfg = self.node.config
            multi = _is_multi(self.node.input_data)

            if multi:
                mode = _normalize_box_display_mode(
                    cfg.get('display_mode', 'Side by Side'))
                cfg['display_mode'] = mode
                if mode == 'Subplots by sample':
                    self._draw_subplots(plot_data, cfg)
                elif mode == 'Subplots by isotope':
                    self._draw_grouped(plot_data, cfg)
                else:
                    cuts = _get_broken_cuts(cfg)

                    def _draw(pi, is_top, is_bottom):
                        """Draw one stacked broken-axis panel (see _render_broken_or_plain)."""
                        self._draw_combined(pi, plot_data, cfg)
                        apply_font_to_pyqtgraph(pi, cfg)

                    _render_broken_or_plain(
                        self.pw, cuts, _draw,
                        axis_factory=lambda: {'bottom': HtmlAxisItem('bottom')},
                        cfg=cfg)
            else:
                cuts = _get_broken_cuts(cfg)

                def _draw(pi, is_top, is_bottom):
                    """Draw one stacked broken-axis panel (see _render_broken_or_plain)."""
                    self._draw_single_sample(pi, plot_data, cfg)
                    apply_font_to_pyqtgraph(pi, cfg)

                _render_broken_or_plain(
                    self.pw, cuts, _draw,
                    axis_factory=lambda: {'bottom': HtmlAxisItem('bottom')},
                    cfg=cfg)

            self._disable_native_pyqtgraph_context_menu()
            self._update_stats(plot_data, multi)
            self.pw.reapply_inline_overrides()
        except Exception as e:
            _itk_log.exception("Handled exception in _refresh")
            _itk_log.error(f"Error updating distribution plot: {e}")
            import traceback; traceback.print_exc()
    def _draw_single_sample(self, pi, data, cfg):
        """Draw one sample panel with element-only x-axis labels.

        In ``Subplots by sample``, sample identity is conveyed by panel title.
        X-axis ticks stay isotope/element-only for readability, and element
        colors are applied per series inside the sample panel.

        Returns:
            bool: ``True`` when at least one element distribution was drawn.
        """
        min_count = cfg.get('min_particle_count', 0)
        sort_mode = self._category_sort_mode(cfg)
        sorted_data = sort_element_dict_by_mass(data)
        category_records = []
        for el, vals in sorted_data.items():
            if min_count > 0 and len(vals) < min_count:
                continue
            fv = _filter_values(vals, cfg.get('data_type_display', 'Counts'),
                                cfg.get('log_y'), cfg)
            if fv and len(fv) >= 2:
                category_records.append({
                    'raw_key': el,
                    'display_label': _fmt_elem(el, cfg),
                    'values': fv,
                    'sort_key': el,
                    'sort_metric': float(np.median(np.asarray(fv, dtype=float))),
                })
        category_records = _sort_box_category_records(category_records, sort_mode)
        xp, xl = [], []
        x = 0
        all_vals_flat = []
        stats_source = {}
        for idx, record in enumerate(category_records):
            el = record['raw_key']
            fv = record['values']
            element_cfg = dict(cfg)
            element_cfg.setdefault('element_colors', {})
            element_cfg['element_colors'].setdefault(
                el, _element_color(el, idx, cfg))
            _draw_single_element(pi, x, fv, None, el, element_cfg, False)
            all_vals_flat.extend(fv)
            xp.append(x)
            xl.append(record['display_label'])
            stats_source[el] = data.get(el, [])
            x += 1
        if xp:
            pi.getAxis('bottom').setTicks([list(zip(xp, xl))])
        else:
            _add_empty_panel_message(pi, "No valid data")
        self._apply_effective_axis_labels(
            pi,
            self._title_key_for_combined_plot(False),
            {
                'bottom': {'text': "Elements", 'units': None},
                'left': {'text': _y_label(cfg), 'units': None},
            },
        )
        if cfg.get('log_y'):
            pi.getAxis('left').setLogMode(True)
        if not cfg.get('auto_y', True):
            pi.setYRange(cfg['y_min'], cfg['y_max'])
        if cfg.get('show_stats', False) and xp:
            _add_stats_text(pi, stats_source, cfg)
        _apply_box_overlays(pi, all_vals_flat, cfg)
        _apply_boxplot_grid(pi, cfg)
        self._configure_plot_title(
            pi, self._title_key_for_combined_plot(False), default_title='')
        return bool(xp)
    def _draw_combined(self, pi, plot_data, cfg):
        """Draw the dense multi-sample ``Side by Side`` combined layout.

        This mode remains a single-plot view where each tick combines element
        and sample name. Font and grid style are still applied from config so
        format settings remain consistent with subplot modes.
        """
        min_count = cfg.get('min_particle_count', 0)
        sort_mode = self._category_sort_mode(cfg)
        category_records = []
        for sn, sdata in plot_data.items():
            if not sdata:
                continue
            for el, vals in sort_element_dict_by_mass(sdata).items():
                if min_count > 0 and len(vals) < min_count:
                    continue
                fv = _filter_values(vals, cfg.get('data_type_display'),
                                    cfg.get('log_y'), cfg)
                if fv and len(fv) >= 2:
                    dn = get_display_name(sn, cfg)
                    category_records.append({
                        'sample_name': sn,
                        'raw_key': el,
                        'display_label': f"{_fmt_elem(el, cfg)}\n({dn})",
                        'values': fv,
                        'sort_key': f"{el}|{sn}",
                        'sort_metric': float(np.median(np.asarray(fv, dtype=float))),
                    })
        category_records = _sort_box_category_records(category_records, sort_mode)
        xp, xl = [], []
        x = 0
        all_vals_flat = []
        for record in category_records:
            _draw_single_element(
                pi, x, record['values'], record['sample_name'],
                record['raw_key'], cfg, True)
            all_vals_flat.extend(record['values'])
            xp.append(x)
            xl.append(record['display_label'])
            x += 1
        if xp:
            pi.getAxis('bottom').setTicks([list(zip(xp, xl))])
        self._apply_effective_axis_labels(
            pi,
            self._title_key_for_combined_plot(True),
            {
                'bottom': {'text': "Elements", 'units': None},
                'left': {'text': _y_label(cfg), 'units': None},
            },
        )
        if cfg.get('log_y'):
            pi.getAxis('left').setLogMode(True)
        if not cfg.get('auto_y', True):
            pi.setYRange(cfg['y_min'], cfg['y_max'])
        _apply_box_overlays(pi, all_vals_flat, cfg)
        _apply_boxplot_grid(pi, cfg)
        self._configure_plot_title(
            pi, self._title_key_for_combined_plot(True), default_title='')
    def _draw_subplots(self, plot_data, cfg):
        """Draw ``Subplots by sample`` as one panel per sample.

        Each sample panel title shows the sample display name while the panel
        x-axis uses only formatted isotope/element labels. This prevents dense
        repeated sample names in tick labels and keeps sample identity in panel
        position/title. Empty sample panels show a visible ``No valid data``
        note.
        """
        sample_order = cfg.get('sample_order', [])
        if sample_order:
            names = [s for s in sample_order if s in plot_data]
            names += [s for s in plot_data if s not in names]
        else:
            names = list(plot_data.keys())
        cols = min(3, len(names))
        rows = math.ceil(len(names) / cols)
        first_pi = None
        cuts = _get_broken_cuts(cfg)
        for i, sn in enumerate(names):
            r, c = divmod(i, cols)
            sd = plot_data[sn]

            def _draw(pi, is_top, is_bottom, sn=sn, sd=sd):
                """Draw one stacked broken-axis panel (see _render_broken_or_plain)."""
                if sd:
                    self._draw_single_sample(
                        pi, sort_element_dict_by_mass(sd), cfg)
                elif is_top:
                    _add_empty_panel_message(pi, "No valid data")
                self._apply_effective_axis_labels(
                    pi,
                    self._title_key_for_sample_plot(sn),
                    {
                        'bottom': {'text': "Elements", 'units': None},
                        'left': {'text': _y_label(cfg), 'units': None},
                    },
                )
                _apply_boxplot_grid(pi, cfg)
                apply_font_to_pyqtgraph(pi, cfg)

            panels = _render_broken_or_plain(
                self.pw, (cuts if sd else []), _draw,
                axis_factory=lambda: {'bottom': HtmlAxisItem('bottom')},
                row=r, col=c, cfg=cfg)
            self._configure_plot_title(
                panels[-1], self._title_key_for_sample_plot(sn),
                default_title=get_display_name(sn, cfg))
            if i == 0:
                first_pi = panels[0]
            elif cols > 1 and r == 0:
                for pi in panels:
                    if not cuts:
                        pi.setYLink(first_pi)
                    pi.getAxis('left').setLabel('')
                    pi.getAxis('left').setStyle(showValues=False)
    def _draw_grouped(self, plot_data, cfg):
        """Draw ``Subplots by isotope`` with one panel per element/isotope.

        This is the canonical isotope-subplot multi-sample layout and the
        target of legacy grouped/by-sample alias values. Each subplot sorts its
        own sample categories independently so one isotope can order sample
        boxes differently from another without changing any extracted values or
        computed statistics. Axis/tick font, grid styling, and figure overlays
        (including frame) are applied per subplot from config.
        """
        min_count = cfg.get('min_particle_count', 0)
        sort_mode = self._category_sort_mode(cfg)
        sample_order = cfg.get('sample_order', [])
        if sample_order:
            ordered_samples = [s for s in sample_order if s in plot_data]
            ordered_samples += [s for s in plot_data if s not in ordered_samples]
        else:
            ordered_samples = list(plot_data.keys())

        all_elems = set()
        for sd in plot_data.values():
            all_elems.update(sd.keys())
        all_elems = sort_elements_by_mass(list(all_elems))
        cols = min(3, len(all_elems))
        rows = math.ceil(len(all_elems) / cols)
        cuts = _get_broken_cuts(cfg)
        for i, el in enumerate(all_elems):
            r, c = divmod(i, cols)
            sample_records = []
            for original_index, sn in enumerate(ordered_samples):
                sd = plot_data.get(sn, {})
                vals = sd.get(el, [])
                fv = None
                if not (min_count > 0 and len(vals) < min_count):
                    fv = _filter_values(
                        vals,
                        cfg.get('data_type_display'),
                        cfg.get('log_y'),
                        cfg,
                    )
                    if fv and len(fv) < 2:
                        fv = None
                sample_records.append({
                    'raw_sample_name': sn,
                    'display_label': get_display_name(sn, cfg),
                    'original_index': original_index,
                    'values': fv,
                    'sort_metric': (
                        float(np.mean(np.asarray(fv, dtype=float)))
                        if fv else None
                    ),
                })

            sorted_records = _sort_box_sample_records(sample_records, sort_mode)

            def _draw(pi, is_top, is_bottom, el=el,
                      sorted_records=sorted_records):
                """Draw one stacked broken-axis panel (see _render_broken_or_plain)."""
                drawn_any = False
                panel_values = []
                tick_pairs = []
                for x_pos, record in enumerate(sorted_records):
                    sn = record['raw_sample_name']
                    fv = record['values']
                    tick_pairs.append((x_pos, record['display_label']))
                    if fv:
                        _draw_single_element(pi, x_pos, fv, sn, el, cfg, True)
                        panel_values.extend(fv)
                        drawn_any = True
                if tick_pairs:
                    pi.getAxis('bottom').setTicks([tick_pairs])
                self._subplot_context_by_plotitem[pi] = {
                    "mode": "Subplots by isotope",
                    "element": el,
                    "title": self._effective_title_for_key(
                        self._title_key_for_element_plot(el),
                        _fmt_elem(el, cfg)),
                }
                self._apply_effective_axis_labels(
                    pi,
                    self._title_key_for_element_plot(el),
                    {
                        'bottom': {'text': "Samples", 'units': None},
                        'left': {'text': _y_label(cfg), 'units': None},
                    },
                )
                if cfg.get('log_y'):
                    pi.getAxis('left').setLogMode(True)
                _apply_box_overlays(pi, panel_values, cfg)
                if not drawn_any and is_top:
                    _add_empty_panel_message(pi, "No valid data")
                _apply_boxplot_grid(pi, cfg)
                apply_font_to_pyqtgraph(pi, cfg)

            panels = _render_broken_or_plain(
                self.pw, cuts, _draw, axis_factory=lambda: {},
                row=r, col=c, cfg=cfg)
            self._configure_plot_title(
                panels[-1], self._title_key_for_element_plot(el),
                default_title=_fmt_elem(el, cfg))

    def _draw_by_sample(self, plot_data, cfg):
        """X-axis = samples (time-ordered), one subplot per element.
        Colors = element colors. Sample order respected.

        Compatibility note:
            This renderer is retained for backward safety, but current config
            normalization aliases legacy ``By Sample (Ordered)`` to
            ``Subplots by isotope`` before draw dispatch.
        """
        min_count = cfg.get('min_particle_count', 0)
        sample_order = cfg.get('sample_order', [])
        if sample_order:
            samples = [s for s in sample_order if s in plot_data]
            samples += [s for s in plot_data if s not in samples]
        else:
            samples = list(plot_data.keys())

        all_elems_set = set()
        for sd in plot_data.values():
            all_elems_set.update(sd.keys())
        if min_count > 0:
            all_elems_set = {
                e for e in all_elems_set
                if sum(len(plot_data[s].get(e, []))
                       for s in samples) >= min_count}
        all_elems = sort_elements_by_mass(list(all_elems_set))

        cols = min(3, max(len(all_elems), 1))
        rows = math.ceil(len(all_elems) / cols)

        for idx, el in enumerate(all_elems):
            r, c = divmod(idx, cols)
            pi = self.pw.addPlot(row=r, col=c)
            color = _element_color(el, idx, cfg)
            xp, xl = [], []
            x = 0
            for sn in samples:
                sd = plot_data.get(sn, {})
                vals = sd.get(el, [])
                if min_count > 0 and len(vals) < min_count:
                    continue
                fv = _filter_values(vals, cfg.get('data_type_display'), cfg.get('log_y'), cfg)
                if fv and len(fv) >= 2:
                    _draw_single_element(pi, x, fv, sn, el, cfg, False)
                    xp.append(x)
                    xl.append(get_display_name(sn, cfg))
                    x += 1
            if xp:
                pi.getAxis('bottom').setTicks([list(zip(xp, xl))])
            self._configure_plot_title(
                pi, self._title_key_for_element_plot(el),
                default_title=_fmt_elem(el, cfg))
            self._apply_effective_axis_labels(
                pi,
                self._title_key_for_element_plot(el),
                {
                    'bottom': {'text': "Sample", 'units': None},
                    'left': {'text': _y_label(cfg), 'units': None},
                },
            )
            if cfg.get('log_y'):
                pi.getAxis('left').setLogMode(True)
            if not cfg.get('auto_y', True):
                pi.setYRange(cfg['y_min'], cfg['y_max'])
            _apply_boxplot_grid(pi, cfg)
            apply_font_to_pyqtgraph(pi, cfg)

    def _update_stats(self, plot_data, multi):
        if multi:
            total = sum(sum(len(v) for v in sd.values()) for sd in plot_data.values() if sd)
            ns = len(plot_data)
            self._stats.setText(f"{ns} samples  |  {total} total data points")
        else:
            total = sum(len(v) for v in plot_data.values())
            ne = len(plot_data)
            self._stats.setText(f"{ne} elements  |  {total} total data points")


# ── Node ───────────────────────────────────────────────────────────────

class BoxPlotNode(QObject):
    position_changed = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        super().__init__()
        self.title = "Distribution Plot"
        self.node_type = "box_plot"
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
        """Open this node's figure, reusing one persistent (hide-on-close) window."""
        from results.shared_plot_utils import show_persistent_figure
        return show_persistent_figure(
            self, lambda: BoxPlotDisplayDialog(self, parent_window))

    def process_data(self, input_data):
        if not input_data:
            return
        self.input_data = input_data
        self.configuration_changed.emit()

    def extract_plot_data(self):
        if not self.input_data:
            return None
        data_key = BOX_DATA_KEY_MAP.get(
            self.config.get('data_type_display', 'Counts'), 'elements')
        itype = self.input_data.get('type')
        if itype == 'sample_data':
            return self._extract_single(data_key)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(data_key)
        return None

    def _extract_single(self, data_key):
        particles = self.input_data.get('particle_data')
        if not particles:
            return None
        result = {}
        for p in particles:
            for el, val in p.get(data_key, {}).items():
                if data_key == 'elements':
                    if val > 0:
                        result.setdefault(el, []).append(val)
                else:
                    if val > 0 and not np.isnan(val):
                        result.setdefault(el, []).append(val)
        return sort_element_dict_by_mass(result) if result else None

    def _extract_multi(self, data_key):
        particles = self.input_data.get('particle_data', [])
        names = self.input_data.get('sample_names', [])
        if not particles:
            return None
        sd = {n: {} for n in names}
        for p in particles:
            src = p.get('source_sample')
            if src and src in sd:
                for el, val in p.get(data_key, {}).items():
                    if data_key == 'elements':
                        if val > 0:
                            sd[src].setdefault(el, []).append(val)
                    else:
                        if val > 0 and not np.isnan(val):
                            sd[src].setdefault(el, []).append(val)
        result = {}
        for sn, d in sd.items():
            if d:
                result[sn] = sort_element_dict_by_mass(d)
        return result if result else None

