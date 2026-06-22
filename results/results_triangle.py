"""
Ternary Plot Node — full-figure view with right-click context menu.

Features:
- Three-element ternary composition diagram (mpltern)
- Scatter and density (tribin) plot types
- Color-by-fourth-element option for scatter plots
- Average point with optional 2σ confidence ellipse
- Particle statistics bar (total, filtered, per-sample)
- Multiple sample support (overlaid, subplots, combined)
- Right-click context menu replaces sidebar for all settings
- Shared font, color, and export utilities via shared_plot_utils
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QPushButton,
    QLineEdit, QFrame, QScrollArea, QWidget, QMenu, QSlider,
    QDialogButtonBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QCursor
from matplotlib.figure import Figure
from matplotlib.patches import Ellipse, Patch
from matplotlib.lines import Line2D
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import numpy as np
import math
import mpltern  # noqa: F401  (side effect: registers ternary projection)

from results.shared_plot_utils import (
    DEFAULT_SAMPLE_COLORS, TERNARY_DATA_TYPE_OPTIONS,
    TERNARY_DATA_KEY_MAPPING, get_font_config,
    make_font_properties, apply_font_to_ternary,
    apply_font_to_colorbar_standalone, FontSettingsGroup,
    LegendGroup, ExportSettingsGroup, MplDraggableCanvas, LABEL_MODES,
    format_element_label, Renderer, get_sample_color,
    get_display_name, download_matplotlib_figure,
    pick_color_hex,
)
import logging
_itk_log = logging.getLogger("IsotopeTrack.results.results_triangle")


DISPLAY_MODES = [
    'Individual Subplots',
    'Combined Plot',
    'Overlaid Samples',
]

PLOT_TYPES = ['Scatter Plot', 'Density Plot (Tribin)']

COLORMAPS = [
    'YlGn', 'viridis', 'plasma', 'inferno', 'magma', 'cividis',
    'YlOrRd', 'BuPu', 'GnBu', 'PuBu', 'YlGnBu', 'PuBuGn',
    'Blues', 'Greens', 'Oranges', 'Reds', 'Purples', 'Greys',
    'coolwarm', 'RdYlBu', 'Spectral', 'turbo', 'jet',
]

# ── Scatter color-encoding options ──────────────────────────────────────────
# Mode A: whole-particle aggregate quantities
COLOR_PARTICLE_QUANTITY_OPTIONS = [
    ('Total Counts',                'total_counts'),
    ('Total Isotope Mass (fg)',     'total_element_mass_fg'),
    ('Total Isotope Moles (fmol)', 'total_element_moles_fmol'),
    ('Total Particle Mass (fg)',   'total_particle_mass_fg'),
    ('Total Particle Moles (fmol)', 'total_particle_moles_fmol'),
]
COLOR_PARTICLE_QUANTITY_LABELS = [x[0] for x in COLOR_PARTICLE_QUANTITY_OPTIONS]
COLOR_PARTICLE_QUANTITY_KEYS   = [x[1] for x in COLOR_PARTICLE_QUANTITY_OPTIONS]

# Mode B: per-isotope measurement data types
COLOR_ISOTOPE_DATA_TYPE_OPTIONS = [
    ('Counts',                  'counts'),
    ('Isotope Mass (fg)',       'element_mass_fg'),
    ('Isotope Moles (fmol)',   'element_moles_fmol'),
    ('Particle Mass (fg)',     'particle_mass_fg'),
    ('Particle Moles (fmol)', 'particle_moles_fmol'),
]
COLOR_ISOTOPE_DATA_TYPE_LABELS = [x[0] for x in COLOR_ISOTOPE_DATA_TYPE_OPTIONS]
COLOR_ISOTOPE_DATA_TYPE_KEYS   = [x[1] for x in COLOR_ISOTOPE_DATA_TYPE_OPTIONS]

# Mapping from COLOR_ISOTOPE_DATA_TYPE key → particle dict key for extraction
_COLOR_ISOTOPE_DK_MAP = {
    'counts':              'elements',
    'element_mass_fg':    'element_mass_fg',
    'element_moles_fmol': 'element_moles_fmol',
    'particle_mass_fg':   'particle_mass_fg',
    'particle_moles_fmol': 'particle_moles_fmol',
}


def _full_triangle_viewport() -> dict:
    """Return the default full ternary viewport."""
    return {'a_min': 0.0, 'b_min': 0.0, 'c_min': 0.0}


def _validate_triangle_viewport(viewport: dict | None) -> dict:
    """Return a sanitized valid ternary viewport or the full viewport.

    Args:
        viewport (dict | None): Lower-bound ternary viewport candidate.

    Returns:
        dict: Validated viewport with ``a_min``, ``b_min``, and ``c_min``.
    """
    if not isinstance(viewport, dict):
        return _full_triangle_viewport()
    try:
        a_min = max(0.0, float(viewport.get('a_min', 0.0)))
        b_min = max(0.0, float(viewport.get('b_min', 0.0)))
        c_min = max(0.0, float(viewport.get('c_min', 0.0)))
    except Exception:
        return _full_triangle_viewport()
    if a_min + b_min + c_min >= 1.0:
        return _full_triangle_viewport()
    return {'a_min': a_min, 'b_min': b_min, 'c_min': c_min}


def _is_full_triangle_viewport(viewport: dict, tol: float = 1e-12) -> bool:
    """Return whether the viewport matches the full simplex within tolerance."""
    vp = _validate_triangle_viewport(viewport)
    return (
        abs(vp['a_min']) <= tol and
        abs(vp['b_min']) <= tol and
        abs(vp['c_min']) <= tol
    )


def _viewport_remaining(viewport: dict) -> float:
    """Return the remaining simplex width for a lower-bound ternary viewport."""
    vp = _validate_triangle_viewport(viewport)
    return 1.0 - (vp['a_min'] + vp['b_min'] + vp['c_min'])


def _point_in_triangle_viewport(a: float, b: float, c: float,
                                viewport: dict, tol: float = 1e-9) -> bool:
    """Return whether a ternary point lies inside the viewport."""
    vp = _validate_triangle_viewport(viewport)
    return (
        a >= vp['a_min'] - tol and
        b >= vp['b_min'] - tol and
        c >= vp['c_min'] - tol
    )


def _remap_point_to_triangle_viewport(a: float, b: float, c: float,
                                      viewport: dict) -> tuple[float, float, float]:
    """Map original ternary fractions into local viewport fractions."""
    vp = _validate_triangle_viewport(viewport)
    remaining = _viewport_remaining(vp)
    if remaining <= 0:
        return a, b, c
    a_local = (a - vp['a_min']) / remaining
    b_local = (b - vp['b_min']) / remaining
    c_local = (c - vp['c_min']) / remaining
    return a_local, b_local, c_local


def _viewport_tick_labels(viewport: dict, component_key: str,
                          ticks: list[float]) -> list[str]:
    """Return original-composition percentage labels for local ternary ticks."""
    vp = _validate_triangle_viewport(viewport)
    remaining = _viewport_remaining(vp)
    base = vp.get(component_key, 0.0)
    return [f'{int(round((base + tick * remaining) * 100))}%' for tick in ticks]


def setup_ternary_axes(ax, element_labels, config, viewport=None):
    """
    Configure mpltern axes with labels, grid, and font settings.

    Ternary coordinate mapping (mpltern convention):
        L (left)   = element A = bottom-left vertex
        R (right)  = element B = bottom-right vertex
        T (top)    = element C = top vertex

    Args:
        ax:             mpltern axes (projection='ternary')
        element_labels: [elem_a, elem_b, elem_c]
        config:         node config dict
        viewport:       optional lower-bound ternary viewport dict
    """
    fp   = make_font_properties(config)
    fc   = get_font_config(config)
    mode = config.get('label_mode', 'Symbol')
    fmt  = [format_element_label(e, mode, Renderer.MATHTEXT, config) for e in element_labels]
    viewport = _validate_triangle_viewport(viewport)

    # Clear mpltern's default vertex labels (they appear ambiguously at the
    # 100%-composition corners, making it unclear whether they mark the
    # start or end of the axis).
    ax.set_llabel('')
    ax.set_rlabel('')
    ax.set_tlabel('')

    # Place element labels at the midpoints of the triangle edges, outside
    # the triangle — the same position as "X Axis"/"Y Axis"/"Z Axis" in a
    # standard ternary diagram.  Each label sits on the edge adjacent to its
    # component's vertex:
    #
    #   element_a (L, bottom-left vertex) → left  edge, rotation +60°
    #   element_b (R, bottom-right vertex) → right edge, rotation −60°
    #   element_c (T, top vertex)          → bottom edge, rotation   0°
    #
    # mpltern Cartesian data-space corners (confirmed by _ternary_xdata_to_abc):
    #   T vertex: (0,       1.0)
    #   L vertex: (−1/√3,   0.0)
    #   R vertex: (+1/√3,   0.0)
    _s   = 1.0 / math.sqrt(3.0)   # ≈ 0.5774
    _pad = 0.12         # outward offset in data units

    # Resolve per-axis colors.  When colored_axes is off every axis uses the
    # global font color so the rest of the rendering path is identical.
    colored = config.get('colored_axes', False)
    if colored:
        axis_a_color = config.get('axis_a_color', '#E74C3C')
        axis_b_color = config.get('axis_b_color', '#2980B9')
        axis_c_color = config.get('axis_c_color', '#27AE60')
    else:
        axis_a_color = axis_b_color = axis_c_color = fc['color']

    # bottom edge midpoint (0, 0) — element_b; outward = (0, −1)
    ax.text(
        0.0, -_pad,
        fmt[1],
        transform=ax.transData,
        ha='center', va='top', rotation=0,
        fontproperties=fp, color=axis_b_color,
    )
    # left edge midpoint (−_s/2, 0.5) — element_a; outward normal ≈ (−√3/2, +½)
    ax.text(
        -_s * 0.5 - _pad * (math.sqrt(3) / 2),
        0.5 + _pad * 0.5,
        fmt[0],
        transform=ax.transData,
        ha='right', va='center', rotation=60,
        fontproperties=fp, color=axis_a_color,
    )
    # right edge midpoint (+_s/2, 0.5) — element_c; outward normal ≈ (+√3/2, +½)
    ax.text(
        _s * 0.5 + _pad * (math.sqrt(3) / 2),
        0.5 + _pad * 0.5,
        fmt[2],
        transform=ax.transData,
        ha='left', va='center', rotation=-60,
        fontproperties=fp, color=axis_c_color,
    )

    show_grid = config.get('show_grid', True)
    if colored:
        # Color triangle border spines.
        # mpltern spine keys confirmed from _base.py: tside/tcorner registered with taxis,
        # lside/lcorner with laxis, rside/rcorner with raxis.
        _spine_map = {
            'tside':   axis_c_color, 'tcorner': axis_c_color,
            'lside':   axis_a_color, 'lcorner': axis_a_color,
            'rside':   axis_b_color, 'rcorner': axis_b_color,
        }
        for _key, _col in _spine_map.items():
            if _key in ax.spines:
                ax.spines[_key].set_color(_col)
        # Color tick marks. TernaryAxis inherits Axis.set_tick_params (NOT tick_params).
        # Use color= (tick marks only); label colors are set in the axis_specs loop below.
        ax.taxis.set_tick_params(which='major', color=axis_c_color)
        ax.laxis.set_tick_params(which='major', color=axis_a_color)
        ax.raxis.set_tick_params(which='major', color=axis_b_color)
        # Per-axis gridlines — always solid lines when colored.
        # TernaryAxis.grid() is inherited from Axis and prepends 'grid_' to kwargs internally.
        if show_grid:
            ax.taxis.grid(True, color=axis_c_color, alpha=0.4, linestyle='-')
            ax.laxis.grid(True, color=axis_a_color, alpha=0.4, linestyle='-')
            ax.raxis.grid(True, color=axis_b_color, alpha=0.4, linestyle='-')
        else:
            ax.taxis.grid(False)
            ax.laxis.grid(False)
            ax.raxis.grid(False)
    else:
        if show_grid:
            ax.grid(True, alpha=0.3)
        else:
            ax.grid(False)

    ticks = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
    # axis_specs: (mpltern axis, viewport component key, label/tick color)
    # taxis tick labels appear on the right edge (adjacent to element_c label) so
    # they use axis_c_color; raxis tick labels appear at the bottom (adjacent to
    # element_b label) so they use axis_b_color.
    axis_specs = (
        (ax.taxis, 'c_min', axis_c_color),
        (ax.laxis, 'a_min', axis_a_color),
        (ax.raxis, 'b_min', axis_b_color),
    )
    for axis, component_key, tick_color in axis_specs:
        axis.set_ticks(ticks)
        axis.set_ticklabels(_viewport_tick_labels(viewport, component_key, ticks))
        for lbl in axis.get_ticklabels():
            lbl.set_fontproperties(fp)
            lbl.set_color(tick_color)

    ax.set_title('')


def confidence_ellipse_params(data_x, data_y, n_std=2.0):
    """
    Compute 2D confidence ellipse parameters from data.

    Performs eigendecomposition of the covariance matrix to get the orientation
    and semi-axes of the n_std confidence region.

    Args:
        data_x:  array of x-coordinates (e.g. b_vals in ternary space)
        data_y:  array of y-coordinates (e.g. c_vals in ternary space)
        n_std:   number of standard deviations (2.0 ≈ 95% for bivariate normal)

    Returns:
        dict with cx, cy, width, height, angle_deg — or None if < 3 points.
    """
    if len(data_x) < 3:
        return None
    try:
        cov = np.cov(data_x, data_y)
        eigvals, eigvecs = np.linalg.eigh(cov)
        order = eigvals.argsort()[::-1]
        eigvals = eigvals[order]
        eigvecs = eigvecs[:, order]
        if eigvals[0] <= 0 or eigvals[1] <= 0:
            return None
        angle = np.degrees(np.arctan2(eigvecs[1, 0], eigvecs[0, 0]))
        w = 2 * n_std * np.sqrt(eigvals[0])
        h = 2 * n_std * np.sqrt(eigvals[1])
        return {
            'cx': np.mean(data_x), 'cy': np.mean(data_y),
            'width': w, 'height': h, 'angle_deg': angle,
        }
    except Exception:
        _itk_log.exception("Handled exception in confidence_ellipse_params")
        return None


class TernarySettingsDialog(QDialog):
    """Scoped settings dialog for triangle plot format and quantity configuration."""

    preview_requested = Signal(dict)

    def __init__(self, config, available_elements, is_multi, sample_names, parent=None, scope='all'):
        """
        Initialize the triangle settings dialog.

        Args:
            config (dict): Current triangle configuration.
            available_elements (list): Elements available for A/B/C and color-by selectors.
            is_multi (bool): Whether the plot is currently in multi-sample mode.
            sample_names (list): Sample names used by sample visual settings.
            parent: Parent widget.
            scope (str): One of 'format', 'quantities', or 'all'.
                - 'format' shows only visual/appearance settings.
                - 'quantities' shows only scientific/data selection settings.
                - 'all' preserves legacy combined dialog behavior.
        """
        super().__init__(parent)
        if scope == 'format':
            self.setWindowTitle("Triangle plot format settings")
        elif scope == 'quantities':
            self.setWindowTitle("Triangle plot quantities configuration")
        else:
            self.setWindowTitle("Ternary Plot Settings")
        self.setMinimumWidth(500)
        self._cfg = dict(config)
        self._elems = available_elements
        self._is_multi = is_multi
        self._sample_names = sample_names
        self._scope = scope

        self.display_mode = None
        self.elem_a = None
        self.elem_b = None
        self.elem_c = None
        self.color_elem = None
        self.data_type = None
        self.label_mode_combo = None
        self.plot_type = None
        self.marker_size = None
        self.marker_alpha = None
        self.tribin_side = None
        self.tribin_alpha = None
        self.show_grid = None
        self.colormap = None
        self.show_colorbar = None
        self.cbar_label = None
        self.show_avg = None
        self.element_filter_mode = None
        self.show_avg_text = None
        self.show_ellipse = None
        self.avg_size = None
        self.avg_color_btn = None
        self.min_total = None
        self.max_particles = None
        self._avg_color = QColor(self._cfg.get('average_point_color', '#FF0000'))
        self._font_group = None
        self._legend_grp = None
        self._export_grp = None
        self._scatter_frame = None
        self._tribin_frame = None
        # Scatter color-encoding widgets (new two-mode system)
        self._scatter_color_group = None
        self._tribin_color_group = None
        self.color_source_combo = None
        self._scatter_color_particle_frame = None
        self._scatter_color_isotope_frame = None
        self.color_particle_quantity_combo = None
        self.color_isotope_combo = None
        self.color_isotope_data_type_combo = None
        self.color_log_scale_cb = None
        # Tribin color-encoding widgets (new two-mode system)
        self.tribin_color_mode_combo = None
        self._tribin_color_isotope_frame = None
        self.tribin_color_isotope_combo = None
        self.tribin_color_data_type_combo = None
        self._color_btns = {}
        self._mean_color_btns = {}
        self._name_edits = {}
        self.colored_axes_cb = None
        self.axis_a_btn = None
        self.axis_b_btn = None
        self.axis_c_btn = None
        self._axis_a_color = self._cfg.get('axis_a_color', '#E74C3C')
        self._axis_b_color = self._cfg.get('axis_b_color', '#27AE60')
        self._axis_c_color = self._cfg.get('axis_c_color', '#2980B9')
        self._build_ui()

    def _build_ui(self):
        """
        Build the dialog UI based on scope while preserving existing control behavior.

        Scope routing:
            - quantities: element selection, data type, filters, display mode.
            - format: isotope label mode, plot style, average visuals, sample colors/names,
              font/legend/export appearance controls.
            - all: includes both groups (legacy behavior).
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
            self.display_mode.addItems(DISPLAY_MODES)
            self.display_mode.setCurrentText(self._cfg.get('display_mode', DISPLAY_MODES[0]))
            fl.addRow("Display Mode:", self.display_mode)
            layout.addWidget(g)

        if self._scope in ('all', 'quantities'):
            g = QGroupBox("Element Selection")
            fl = QFormLayout(g)
            placeholder = ['-- Select --']

            self.elem_a = QComboBox()
            self.elem_a.addItems(placeholder + self._elems)
            ea = self._cfg.get('element_a', '')
            if ea in self._elems:
                self.elem_a.setCurrentText(ea)
            fl.addRow("Element A (Bottom Left):", self.elem_a)

            self.elem_b = QComboBox()
            self.elem_b.addItems(placeholder + self._elems)
            eb = self._cfg.get('element_b', '')
            if eb in self._elems:
                self.elem_b.setCurrentText(eb)
            fl.addRow("Element B (Bottom Right):", self.elem_b)

            self.elem_c = QComboBox()
            self.elem_c.addItems(placeholder + self._elems)
            ec = self._cfg.get('element_c', '')
            if ec in self._elems:
                self.elem_c.setCurrentText(ec)
            fl.addRow("Element C (Top):", self.elem_c)
            layout.addWidget(g)

            # ── Plot Type (moved here from Format Settings) ─────────────────
            g_pt = QGroupBox("Plot Type")
            fl_pt = QFormLayout(g_pt)
            self.plot_type = QComboBox()
            if self._cfg.get('display_mode', '') == 'Overlaid Samples':
                # Tribin is not meaningful in overlaid mode — scatter only
                self.plot_type.addItems(['Scatter Plot'])
            else:
                self.plot_type.addItems(PLOT_TYPES)
            self.plot_type.setCurrentText(self._cfg.get('plot_type', 'Scatter Plot'))
            self.plot_type.currentTextChanged.connect(self._on_plot_type_changed)
            fl_pt.addRow("Plot Type:", self.plot_type)
            layout.addWidget(g_pt)

            # ── Hexbin Color Encoding (shown only for Hexbin) ───────────────
            self._tribin_color_group = QGroupBox("Tribin Color Encoding")
            hcfl = QFormLayout(self._tribin_color_group)

            self.tribin_color_mode_combo = QComboBox()
            self.tribin_color_mode_combo.addItem(
                "Density (particle events per bin)", "density")
            self.tribin_color_mode_combo.addItem(
                "Isotope Measurement", "isotope_measurement")
            _cur_hcm = self._cfg.get('tribin_color_mode', 'density')
            _hcmi = self.tribin_color_mode_combo.findData(_cur_hcm)
            self.tribin_color_mode_combo.setCurrentIndex(max(0, _hcmi))
            self.tribin_color_mode_combo.currentIndexChanged.connect(
                self._on_tribin_color_mode_changed)
            hcfl.addRow("Color Mode:", self.tribin_color_mode_combo)

            # Sub-frame: isotope measurement controls
            self._tribin_color_isotope_frame = QFrame()
            hcisfl = QFormLayout(self._tribin_color_isotope_frame)
            hcisfl.setContentsMargins(0, 0, 0, 0)

            self.tribin_color_isotope_combo = QComboBox()
            self.tribin_color_isotope_combo.addItems(['(None)'] + self._elems)
            _cur_hci = self._cfg.get('tribin_color_isotope', '')
            if _cur_hci in self._elems:
                self.tribin_color_isotope_combo.setCurrentText(_cur_hci)
            hcisfl.addRow("Isotope:", self.tribin_color_isotope_combo)

            self.tribin_color_data_type_combo = QComboBox()
            for lbl, key in COLOR_ISOTOPE_DATA_TYPE_OPTIONS:
                self.tribin_color_data_type_combo.addItem(lbl, key)
            _cur_hcdt = self._cfg.get('tribin_color_data_type', 'counts')
            _hcdti = self.tribin_color_data_type_combo.findData(_cur_hcdt)
            self.tribin_color_data_type_combo.setCurrentIndex(max(0, _hcdti))
            hcisfl.addRow("Data Type:", self.tribin_color_data_type_combo)

            hcfl.addRow(self._tribin_color_isotope_frame)
            layout.addWidget(self._tribin_color_group)

            # Set initial isotope sub-frame visibility
            self._on_tribin_color_mode_changed()

            # ── Scatter Color Encoding (shown only for Scatter) ─────────────
            self._scatter_color_group = QGroupBox("Scatter Color Encoding")
            scfl = QFormLayout(self._scatter_color_group)

            self.color_source_combo = QComboBox()
            self.color_source_combo.addItem("Particle quantity", "particle_quantity")
            self.color_source_combo.addItem("Isotope measurement", "isotope_measurement")
            _cur_source = self._cfg.get('color_source', 'particle_quantity')
            _si = self.color_source_combo.findData(_cur_source)
            self.color_source_combo.setCurrentIndex(max(0, _si))
            self.color_source_combo.currentIndexChanged.connect(self._on_color_mode_changed)
            scfl.addRow("Color Mode:", self.color_source_combo)

            # Frame A: particle quantity
            self._scatter_color_particle_frame = QFrame()
            pqfl = QFormLayout(self._scatter_color_particle_frame)
            pqfl.setContentsMargins(0, 0, 0, 0)
            self.color_particle_quantity_combo = QComboBox()
            for lbl, key in COLOR_PARTICLE_QUANTITY_OPTIONS:
                self.color_particle_quantity_combo.addItem(lbl, key)
            _cur_pq = self._cfg.get('color_particle_quantity', 'total_counts')
            _pqi = self.color_particle_quantity_combo.findData(_cur_pq)
            self.color_particle_quantity_combo.setCurrentIndex(max(0, _pqi))
            pqfl.addRow("Quantity:", self.color_particle_quantity_combo)
            scfl.addRow(self._scatter_color_particle_frame)

            # Frame B: isotope measurement
            self._scatter_color_isotope_frame = QFrame()
            isfl = QFormLayout(self._scatter_color_isotope_frame)
            isfl.setContentsMargins(0, 0, 0, 0)
            self.color_isotope_combo = QComboBox()
            self.color_isotope_combo.addItems(['(None)'] + self._elems)
            _cur_iso = self._cfg.get('color_isotope', '')
            if _cur_iso in self._elems:
                self.color_isotope_combo.setCurrentText(_cur_iso)
            isfl.addRow("Isotope:", self.color_isotope_combo)
            self.color_isotope_data_type_combo = QComboBox()
            for lbl, key in COLOR_ISOTOPE_DATA_TYPE_OPTIONS:
                self.color_isotope_data_type_combo.addItem(lbl, key)
            _cur_idt = self._cfg.get('color_isotope_data_type', 'counts')
            _idti = self.color_isotope_data_type_combo.findData(_cur_idt)
            self.color_isotope_data_type_combo.setCurrentIndex(max(0, _idti))
            isfl.addRow("Data Type:", self.color_isotope_data_type_combo)
            scfl.addRow(self._scatter_color_isotope_frame)

            self.color_log_scale_cb = QCheckBox("Log₁₀ color scale")
            self.color_log_scale_cb.setChecked(self._cfg.get('color_log_scale', False))
            scfl.addRow("Color Scale:", self.color_log_scale_cb)

            layout.addWidget(self._scatter_color_group)

            # Trigger visibility for both color groups and sub-frames
            self._on_plot_type_changed()
            self._on_color_mode_changed()
            self._on_tribin_color_mode_changed()

            g = QGroupBox("Composition Basis")
            fl = QFormLayout(g)
            self.data_type = QComboBox()
            self.data_type.addItems(TERNARY_DATA_TYPE_OPTIONS)
            self.data_type.setCurrentText(self._cfg.get('data_type_display', 'Counts (%)'))
            fl.addRow("Composition Basis:", self.data_type)
            layout.addWidget(g)

            g = QGroupBox("Filtering")
            fl = QFormLayout(g)
            self.min_total = QDoubleSpinBox()
            self.min_total.setRange(0.0, 1e9)
            self.min_total.setDecimals(2)
            self.min_total.setValue(self._cfg.get('min_total', 0.0))
            fl.addRow("Min Total (A+B+C):", self.min_total)
            self.max_particles = QSpinBox()
            self.max_particles.setRange(1, 100_000_000)
            self.max_particles.setValue(self._cfg.get('max_particles', 100_000_000))
            fl.addRow("Max Particles:", self.max_particles)
            self.element_filter_mode = QComboBox()
            self.element_filter_mode.addItem(
                "Show particles with at least 1 selected element", "any_one")
            self.element_filter_mode.addItem(
                "Show selected elements present (partial match)", "partial")
            self.element_filter_mode.addItem(
                "Show selected elements only (exact match)", "exact")
            # Migrate legacy boolean config to the new string key
            _legacy = self._cfg.get('average_only_with_all_elements', True)
            _mode = self._cfg.get('element_filter_mode',
                                  'partial' if _legacy else 'any_one')
            _idx = self.element_filter_mode.findData(_mode)
            self.element_filter_mode.setCurrentIndex(max(0, _idx))
            fl.addRow("Element filter:", self.element_filter_mode)
            layout.addWidget(g)

        if self._scope in ('all', 'format'):
            g = QGroupBox("Labels")
            fl = QFormLayout(g)
            self.label_mode_combo = QComboBox()
            self.label_mode_combo.addItems(LABEL_MODES)
            self.label_mode_combo.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
            fl.addRow("Isotope Label:", self.label_mode_combo)
            layout.addWidget(g)

            g = QGroupBox("Plot Style")
            fl = QFormLayout(g)

            self._scatter_frame = QFrame()
            sfl = QFormLayout(self._scatter_frame)
            sfl.setContentsMargins(0, 0, 0, 0)
            self.marker_size = QSpinBox()
            self.marker_size.setRange(1, 100)
            self.marker_size.setValue(self._cfg.get('marker_size', 20))
            sfl.addRow("Marker Size:", self.marker_size)
            self.marker_alpha = QSlider(Qt.Horizontal)
            self.marker_alpha.setRange(10, 100)
            self.marker_alpha.setValue(int(self._cfg.get('marker_alpha', 0.7) * 100))
            sfl.addRow("Transparency:", self.marker_alpha)
            fl.addRow(self._scatter_frame)

            self._tribin_frame = QFrame()
            hfl = QFormLayout(self._tribin_frame)
            hfl.setContentsMargins(0, 0, 0, 0)
            self.tribin_side = QDoubleSpinBox()
            self.tribin_side.setRange(1.0, 25.0)
            self.tribin_side.setSingleStep(0.5)
            self.tribin_side.setDecimals(1)
            self.tribin_side.setValue(self._cfg.get('tribin_side_pct', 5.0))
            hfl.addRow("Triangle Side (%):", self.tribin_side)
            self.tribin_alpha = QSlider(Qt.Horizontal)
            self.tribin_alpha.setRange(10, 100)
            self.tribin_alpha.setValue(int(self._cfg.get('tribin_alpha', 0.8) * 100))
            hfl.addRow("Transparency:", self.tribin_alpha)
            fl.addRow(self._tribin_frame)

            self.show_grid = QCheckBox()
            self.show_grid.setChecked(self._cfg.get('show_grid', True))
            fl.addRow("Show Grid:", self.show_grid)
            self.colormap = QComboBox()
            self.colormap.addItems(COLORMAPS)
            cm = self._cfg.get('colormap', 'YlGn')
            if cm in COLORMAPS:
                self.colormap.setCurrentText(cm)
            fl.addRow("Color Map:", self.colormap)
            self.show_colorbar = QCheckBox()
            self.show_colorbar.setChecked(self._cfg.get('show_colorbar', True))
            fl.addRow("Show Color Bar:", self.show_colorbar)
            layout.addWidget(g)
            self._on_plot_type_changed()

            g = QGroupBox("Axis Colors")
            fl = QFormLayout(g)
            self.colored_axes_cb = QCheckBox()
            self.colored_axes_cb.setChecked(self._cfg.get('colored_axes', False))
            fl.addRow("Color Axes:", self.colored_axes_cb)
            elem_a = self._cfg.get('element_a', 'A') or 'A'
            elem_b = self._cfg.get('element_b', 'B') or 'B'
            elem_c = self._cfg.get('element_c', 'C') or 'C'
            self.axis_a_btn = QPushButton()
            self.axis_a_btn.setStyleSheet(
                f"background-color: {self._axis_a_color}; min-height: 25px; border: 1px solid black;")
            self.axis_a_btn.clicked.connect(lambda: self._pick_axis_color('a'))
            fl.addRow(f"Element A ({elem_a}) color:", self.axis_a_btn)
            self.axis_b_btn = QPushButton()
            self.axis_b_btn.setStyleSheet(
                f"background-color: {self._axis_b_color}; min-height: 25px; border: 1px solid black;")
            self.axis_b_btn.clicked.connect(lambda: self._pick_axis_color('b'))
            fl.addRow(f"Element B ({elem_b}) color:", self.axis_b_btn)
            self.axis_c_btn = QPushButton()
            self.axis_c_btn.setStyleSheet(
                f"background-color: {self._axis_c_color}; min-height: 25px; border: 1px solid black;")
            self.axis_c_btn.clicked.connect(lambda: self._pick_axis_color('c'))
            fl.addRow(f"Element C ({elem_c}) color:", self.axis_c_btn)
            layout.addWidget(g)

            g = QGroupBox("Average Point")
            fl = QFormLayout(g)
            self.show_avg = QCheckBox()
            self.show_avg.setChecked(self._cfg.get('show_average_point', True))
            fl.addRow("Show Average:", self.show_avg)
            self.show_avg_text = QCheckBox()
            self.show_avg_text.setChecked(self._cfg.get('show_average_text', True))
            fl.addRow("Show Stats Text:", self.show_avg_text)
            self.show_ellipse = QCheckBox()
            self.show_ellipse.setChecked(self._cfg.get('show_confidence_ellipse', False))
            fl.addRow("Show 2s Confidence Ellipse:", self.show_ellipse)
            self.avg_size = QSpinBox()
            self.avg_size.setRange(20, 300)
            self.avg_size.setValue(self._cfg.get('average_point_size', 100))
            fl.addRow("Average Marker Size:", self.avg_size)
            self.avg_color_btn = QPushButton()
            self.avg_color_btn.setStyleSheet(
                f"background-color: {self._avg_color.name()}; min-height: 25px; border: 1px solid black;")
            self.avg_color_btn.clicked.connect(self._pick_avg_color)
            fl.addRow("Average Color:", self.avg_color_btn)
            layout.addWidget(g)

            if self._is_multi:
                g = QGroupBox("Sample Colors & Names")
                vl = QVBoxLayout(g)
                colors = self._cfg.get('sample_colors', {})
                mappings = self._cfg.get('sample_name_mappings', {})
                for i, sn in enumerate(self._sample_names):
                    row = QHBoxLayout()
                    ne = QLineEdit(mappings.get(sn, sn))
                    ne.setFixedWidth(180)
                    row.addWidget(ne)
                    self._name_edits[sn] = ne
                    cb = QPushButton()
                    cb.setFixedSize(30, 22)
                    c = colors.get(sn, DEFAULT_SAMPLE_COLORS[i % len(DEFAULT_SAMPLE_COLORS)])
                    cb.setStyleSheet(f"background-color: {c}; border: 1px solid black;")
                    cb.clicked.connect(lambda _, s=sn, b=cb: self._pick_sample_color(s, b))
                    row.addWidget(cb)
                    self._color_btns[sn] = (cb, c)
                    rst = QPushButton("R")
                    rst.setFixedSize(22, 22)
                    rst.setToolTip(f"Reset to: {sn}")
                    rst.clicked.connect(lambda _, orig=sn: self._reset_name(orig))
                    row.addWidget(rst)
                    row.addStretch()
                    w = QWidget()
                    w.setLayout(row)
                    vl.addWidget(w)
                layout.addWidget(g)

                g2 = QGroupBox("Mean Marker Colors (Overlaid Mode)")
                vl2 = QVBoxLayout(g2)
                mean_colors_cfg = self._cfg.get('sample_mean_colors', {})
                sc_map = self._cfg.get('sample_colors', {})
                for i2, sn in enumerate(self._sample_names):
                    row2 = QHBoxLayout()
                    name_text = (self._name_edits[sn].text()
                                 if sn in self._name_edits else sn)
                    lbl2 = QLabel(name_text)
                    lbl2.setFixedWidth(180)
                    row2.addWidget(lbl2)
                    def_c = sc_map.get(
                        sn, DEFAULT_SAMPLE_COLORS[i2 % len(DEFAULT_SAMPLE_COLORS)])
                    mc = mean_colors_cfg.get(sn, def_c)
                    mcb = QPushButton()
                    mcb.setFixedSize(30, 22)
                    mcb.setStyleSheet(
                        f'background-color: {mc}; border: 1px solid black;')
                    mcb.clicked.connect(
                        lambda _, s=sn, b=mcb: self._pick_mean_color(s, b))
                    row2.addWidget(mcb)
                    self._mean_color_btns[sn] = (mcb, mc)
                    row2.addStretch()
                    w2 = QWidget()
                    w2.setLayout(row2)
                    vl2.addWidget(w2)
                layout.addWidget(g2)

            self._font_group = FontSettingsGroup(self._cfg)
            layout.addWidget(self._font_group.build())
            self._legend_grp = LegendGroup(self._cfg)
            layout.addWidget(self._legend_grp.build())
            self._export_grp = ExportSettingsGroup(self._cfg)
            layout.addWidget(self._export_grp.build())

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

    def _on_plot_type_changed(self):
        """Toggle scatter/tribin sub-sections for both format controls and color encoding groups."""
        # Determine plot type from the quantities-scope combo or fall back to saved config.
        if self.plot_type is not None:
            is_scatter = self.plot_type.currentText() == 'Scatter Plot'
        else:
            is_scatter = self._cfg.get('plot_type', 'Scatter Plot') == 'Scatter Plot'

        # Format-scope frames (exist when scope is 'format' or 'all')
        if self._scatter_frame is not None:
            self._scatter_frame.setVisible(is_scatter)
        if self._tribin_frame is not None:
            self._tribin_frame.setVisible(not is_scatter)

        # Quantities-scope color groups (exist when scope is 'quantities' or 'all')
        if self._scatter_color_group is not None:
            self._scatter_color_group.setVisible(is_scatter)
        if self._tribin_color_group is not None:
            self._tribin_color_group.setVisible(not is_scatter)

    def _on_color_mode_changed(self):
        """Toggle particle-quantity vs isotope-measurement sub-frames inside scatter color group."""
        if self.color_source_combo is None:
            return
        is_particle_qty = self.color_source_combo.currentData() == 'particle_quantity'
        if self._scatter_color_particle_frame is not None:
            self._scatter_color_particle_frame.setVisible(is_particle_qty)
        if self._scatter_color_isotope_frame is not None:
            self._scatter_color_isotope_frame.setVisible(not is_particle_qty)

    def _on_tribin_color_mode_changed(self):
        """Show/hide isotope sub-frame inside the tribin color encoding group."""
        if self.tribin_color_mode_combo is None:
            return
        is_isotope = self.tribin_color_mode_combo.currentData() == 'isotope_measurement'
        if self._tribin_color_isotope_frame is not None:
            self._tribin_color_isotope_frame.setVisible(is_isotope)

    def _pick_avg_color(self):
        """Pick average-point color used for plot formatting only."""
        from PySide6.QtWidgets import QColorDialog
        c = QColorDialog.getColor(self._avg_color, self, "Average Point Color")
        if c.isValid():
            self._avg_color = c
            self.avg_color_btn.setStyleSheet(
                f"background-color: {c.name()}; min-height: 25px; border: 1px solid black;")

    def _pick_axis_color(self, which):
        """Pick color for a single ternary axis (a, b, or c)."""
        from PySide6.QtWidgets import QColorDialog
        cur_map = {'a': self._axis_a_color, 'b': self._axis_b_color, 'c': self._axis_c_color}
        btn_map  = {'a': self.axis_a_btn,   'b': self.axis_b_btn,   'c': self.axis_c_btn}
        c = QColorDialog.getColor(QColor(cur_map[which]), self, f"Axis {which.upper()} Color")
        if c.isValid():
            if which == 'a':
                self._axis_a_color = c.name()
            elif which == 'b':
                self._axis_b_color = c.name()
            else:
                self._axis_c_color = c.name()
            btn_map[which].setStyleSheet(
                f"background-color: {c.name()}; min-height: 25px; border: 1px solid black;")

    def _pick_sample_color(self, name, btn):
        """
        Pick visual color for a sample in multi-sample format settings.

        Args:
            name (str): Raw sample key.
            btn (QPushButton): Swatch button to update.
        """
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._color_btns[name][1])
        c = QColorDialog.getColor(cur, self, f"Color for {name}")
        if c.isValid():
            btn.setStyleSheet(f"background-color: {c.name()}; border: 1px solid black;")
            self._color_btns[name] = (btn, c.name())

    def _pick_mean_color(self, name, btn):
        """Pick mean marker color for a sample in overlaid mode."""
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._mean_color_btns[name][1])
        c = QColorDialog.getColor(cur, self, f'Mean marker color for {name}')
        if c.isValid():
            btn.setStyleSheet(
                f'background-color: {c.name()}; border: 1px solid black;')
            self._mean_color_btns[name] = (btn, c.name())

    def _reset_name(self, original):
        """
        Reset user-facing sample display name to the raw original sample name.

        This preserves sample identity while changing only visual labeling.
        """
        if original in self._name_edits:
            self._name_edits[original].setText(original)

    def collect(self) -> dict:
        """
        Collect dialog values for the active scope and preserve untouched config fields.

        Returns:
            dict: Updated config containing scoped changes only.
        """
        out = dict(self._cfg)
        if self.elem_a is not None:
            ea = self.elem_a.currentText()
            out['element_a'] = '' if ea.startswith('--') else ea
        if self.elem_b is not None:
            eb = self.elem_b.currentText()
            out['element_b'] = '' if eb.startswith('--') else eb
        if self.elem_c is not None:
            ec = self.elem_c.currentText()
            out['element_c'] = '' if ec.startswith('--') else ec
        # ── Scatter color encoding keys ──────────────────────────────────────
        if self.color_source_combo is not None:
            out['color_source'] = self.color_source_combo.currentData()
        if self.color_particle_quantity_combo is not None:
            out['color_particle_quantity'] = self.color_particle_quantity_combo.currentData()
        if self.color_isotope_combo is not None:
            ci = self.color_isotope_combo.currentText()
            out['color_isotope'] = '' if ci.startswith('(') else ci
        if self.color_isotope_data_type_combo is not None:
            out['color_isotope_data_type'] = self.color_isotope_data_type_combo.currentData()
        if self.color_log_scale_cb is not None:
            out['color_log_scale'] = self.color_log_scale_cb.isChecked()
        # ── Hexbin color encoding keys ───────────────────────────────────────
        if self.tribin_color_mode_combo is not None:
            out['tribin_color_mode'] = self.tribin_color_mode_combo.currentData()
        if self.tribin_color_isotope_combo is not None:
            hci = self.tribin_color_isotope_combo.currentText()
            out['tribin_color_isotope'] = '' if hci.startswith('(') else hci
        if self.tribin_color_data_type_combo is not None:
            out['tribin_color_data_type'] = self.tribin_color_data_type_combo.currentData()
        if self.data_type is not None:
            out['data_type_display'] = self.data_type.currentText()
        if self.label_mode_combo is not None:
            out['label_mode'] = self.label_mode_combo.currentText()
        if self.plot_type is not None:
            out['plot_type'] = self.plot_type.currentText()
        if self.marker_size is not None:
            out['marker_size'] = self.marker_size.value()
        if self.marker_alpha is not None:
            out['marker_alpha'] = self.marker_alpha.value() / 100.0
        if self.tribin_side is not None:
            out['tribin_side_pct'] = self.tribin_side.value()
        if self.tribin_alpha is not None:
            out['tribin_alpha'] = self.tribin_alpha.value() / 100.0
        if self.show_grid is not None:
            out['show_grid'] = self.show_grid.isChecked()
        if self.colormap is not None:
            out['colormap'] = self.colormap.currentText()
        if self.show_colorbar is not None:
            out['show_colorbar'] = self.show_colorbar.isChecked()
        if self.show_avg is not None:
            out['show_average_point'] = self.show_avg.isChecked()
        if self.element_filter_mode is not None:
            out['element_filter_mode'] = self.element_filter_mode.currentData()
        if self.show_avg_text is not None:
            out['show_average_text'] = self.show_avg_text.isChecked()
        if self.show_ellipse is not None:
            out['show_confidence_ellipse'] = self.show_ellipse.isChecked()
        if self.avg_size is not None:
            out['average_point_size'] = self.avg_size.value()
        out['average_point_color'] = self._avg_color.name()
        if self.min_total is not None:
            out['min_total'] = self.min_total.value()
        if self.max_particles is not None:
            out['max_particles'] = self.max_particles.value()
        if self._is_multi and self.display_mode is not None:
            out['display_mode'] = self.display_mode.currentText()
        if self._is_multi and self._color_btns:
            out['sample_colors'] = {sn: c for sn, (_, c) in self._color_btns.items()}
        if self._is_multi and self._name_edits:
            out['sample_name_mappings'] = {sn: ne.text() for sn, ne in self._name_edits.items()}
        if self._is_multi and self._mean_color_btns:
            out['sample_mean_colors'] = {
                sn: c for sn, (_, c) in self._mean_color_btns.items()}
        if self.colored_axes_cb is not None:
            out['colored_axes'] = self.colored_axes_cb.isChecked()
        out['axis_a_color'] = self._axis_a_color
        out['axis_b_color'] = self._axis_b_color
        out['axis_c_color'] = self._axis_c_color
        if self._font_group is not None:
            out.update(self._font_group.collect())
        if self._legend_grp is not None:
            out.update(self._legend_grp.collect())
        if self._export_grp is not None:
            out.update(self._export_grp.collect())
        return out

ANNOTATION_MARKERS = [
    ('● Circle',       'o'),
    ('■ Square',       's'),
    ('▲ Triangle ▲',   '^'),
    ('▼ Triangle ▼',   'v'),
    ('◆ Diamond',      'D'),
    ('◇ Thin Diamond', 'd'),
    ('★ Star',         '*'),
    ('✚ Plus',         '+'),
    ('✖ Cross',        'x'),
    ('⬠ Pentagon',     'p'),
    ('⬡ Hexagon',      'H'),
    ('⯄ Octagon',      '8'),
    ('◀ Tri Left',     '<'),
    ('▶ Tri Right',    '>'),
    ('• Point',        '.'),
]
_MARKER_NAMES  = [m[0] for m in ANNOTATION_MARKERS]
_MARKER_CODES  = [m[1] for m in ANNOTATION_MARKERS]

ANN_TYPES = ['Text', 'Marker', 'Marker + Text']

_ANN_DEFAULTS = {
    'type':              'Text',
    'x_frac':            0.50,
    'y_frac':            0.50,
    't':                 0.33,
    'l':                 0.33,
    'r':                 0.34,
    'text':              'Annotation',
    'color':             '#222222',
    'fontsize':          11,
    'bold':              False,
    'italic':            False,
    'show_box':          True,
    'box_color':         '#FFFFFF',
    'box_alpha':         0.75,
    'marker':            'o',
    'marker_size':       80,
    'marker_color':      '#3B82F6',
    'marker_edge_color': '#1D4ED8',
    'marker_edge_width': 1.5,
    'marker_alpha':      0.85,
}


class _ColorSwatch(QPushButton):
    """Compact colour-picker button."""
    def __init__(self, color='#FFFFFF', parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 24)
        self._color = color
        self._update()

    def _update(self):
        """Refresh the swatch preview without styling any parent dialog."""
        self.setStyleSheet(
            "QPushButton {"
            f"background-color:{self._color};"
            "border:1px solid #888;border-radius:3px;"
            "}")

    def color(self):
        return self._color

    def set_color(self, c):
        """Store one validated triangle-preview color and refresh the swatch."""
        self._color = c
        self._update()

    def mousePressEvent(self, event):
        """Open the shared safe color picker for this swatch on left click."""
        if event.button() == Qt.LeftButton:
            picked = pick_color_hex(self._color, owner=self,
                                    title="Select Color")
            if picked:
                self.set_color(picked)
        super().mousePressEvent(event)


class AnnotationDialog(QDialog):
    """Add or edit a single ternary-plot annotation (Text / Marker / Marker+Text)."""

    def __init__(self, ann: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Annotation" if ann is None else "Edit Annotation")
        self.setMinimumWidth(460)
        self._ann = dict(_ANN_DEFAULTS)
        if ann:
            self._ann.update(ann)
        self._build()

    # ── UI ────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); lay = QVBoxLayout(inner)
        lay.setSpacing(8)
        scroll.setWidget(inner); root.addWidget(scroll)

        # ── Type selector ────────────────────
        g0 = QGroupBox("Annotation Type")
        f0 = QFormLayout(g0)
        self._type_combo = QComboBox()
        self._type_combo.addItems(ANN_TYPES)
        self._type_combo.setCurrentText(self._ann.get('type', 'Text'))
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        f0.addRow("Type:", self._type_combo)
        lay.addWidget(g0)

        self._text_pos_grp = QGroupBox("Text Position  (0 = left/bottom  →  1 = right/top)")
        fp = QFormLayout(self._text_pos_grp)
        self._xfrac = QDoubleSpinBox()
        self._xfrac.setRange(0.0, 1.0); self._xfrac.setDecimals(3); self._xfrac.setSingleStep(0.02)
        self._xfrac.setValue(self._ann.get('x_frac', 0.50))
        fp.addRow("X (horizontal):", self._xfrac)
        self._yfrac = QDoubleSpinBox()
        self._yfrac.setRange(0.0, 1.0); self._yfrac.setDecimals(3); self._yfrac.setSingleStep(0.02)
        self._yfrac.setValue(self._ann.get('y_frac', 0.50))
        fp.addRow("Y (vertical):", self._yfrac)
        lay.addWidget(self._text_pos_grp)

        self._tern_pos_grp = QGroupBox("Marker Position  (ternary coordinates, T + L + R = 1)")
        ft = QFormLayout(self._tern_pos_grp)

        self._sum_lbl = QLabel()
        self._sum_lbl.setStyleSheet("color:#6B7280; font-size:10px;")
        ft.addRow("", self._sum_lbl)

        coord_row = QHBoxLayout()
        self._t = QDoubleSpinBox(); self._t.setRange(0, 1); self._t.setDecimals(3)
        self._t.setSingleStep(0.01); self._t.setValue(self._ann.get('t', 0.33))
        self._l = QDoubleSpinBox(); self._l.setRange(0, 1); self._l.setDecimals(3)
        self._l.setSingleStep(0.01); self._l.setValue(self._ann.get('l', 0.33))
        self._r = QDoubleSpinBox(); self._r.setRange(0, 1); self._r.setDecimals(3)
        self._r.setSingleStep(0.01); self._r.setValue(self._ann.get('r', 0.34))
        for lbl_txt, sp in [("T (top):", self._t), ("L (left):", self._l), ("R (right):", self._r)]:
            row = QHBoxLayout()
            row.addWidget(QLabel(lbl_txt, minimumWidth=60)); row.addWidget(sp)
            ft.addRow(row)
            sp.valueChanged.connect(self._update_sum)

        norm_btn = QPushButton("⟳  Normalize  (force T+L+R = 1)")
        norm_btn.clicked.connect(self._normalize)
        ft.addRow("", norm_btn)
        lay.addWidget(self._tern_pos_grp)
        self._update_sum()

        # ── Text style ───────────────────────
        self._text_style_grp = QGroupBox("Text Style")
        fts = QFormLayout(self._text_style_grp)

        self._text_edit = QLineEdit(self._ann.get('text', 'Annotation'))
        fts.addRow("Text:", self._text_edit)

        self._fs = QSpinBox(); self._fs.setRange(6, 48)
        self._fs.setValue(self._ann.get('fontsize', 11))
        fts.addRow("Font Size:", self._fs)

        style_h = QHBoxLayout()
        self._bold   = QCheckBox("Bold");   self._bold.setChecked(self._ann.get('bold', False))
        self._italic = QCheckBox("Italic"); self._italic.setChecked(self._ann.get('italic', False))
        style_h.addWidget(self._bold); style_h.addWidget(self._italic); style_h.addStretch()
        fts.addRow("Style:", _hbox_widget(style_h))

        self._text_col = _ColorSwatch(self._ann.get('color', '#222222'))
        fts.addRow("Text Color:", self._text_col)

        box_h = QHBoxLayout()
        self._show_box = QCheckBox("Background box")
        self._show_box.setChecked(self._ann.get('show_box', True))
        self._box_col   = _ColorSwatch(self._ann.get('box_color', '#FFFFFF'))
        self._box_alpha = QDoubleSpinBox()
        self._box_alpha.setRange(0.0, 1.0); self._box_alpha.setDecimals(2); self._box_alpha.setSingleStep(0.05)
        self._box_alpha.setValue(self._ann.get('box_alpha', 0.75))
        box_h.addWidget(self._show_box)
        box_h.addWidget(QLabel("Color:")); box_h.addWidget(self._box_col)
        box_h.addWidget(QLabel("Alpha:")); box_h.addWidget(self._box_alpha)
        box_h.addStretch()
        fts.addRow("Box:", _hbox_widget(box_h))
        lay.addWidget(self._text_style_grp)

        # ── Marker style ─────────────────────
        self._marker_style_grp = QGroupBox("Marker Style")
        fms = QFormLayout(self._marker_style_grp)

        self._marker_combo = QComboBox()
        self._marker_combo.addItems(_MARKER_NAMES)
        cur_code = self._ann.get('marker', 'o')
        self._marker_combo.setCurrentIndex(
            _MARKER_CODES.index(cur_code) if cur_code in _MARKER_CODES else 0)
        fms.addRow("Symbol:", self._marker_combo)

        self._marker_size = QSpinBox(); self._marker_size.setRange(10, 500)
        self._marker_size.setSuffix(" pt²")
        self._marker_size.setValue(self._ann.get('marker_size', 80))
        fms.addRow("Size:", self._marker_size)

        self._marker_alpha = QDoubleSpinBox()
        self._marker_alpha.setRange(0.0, 1.0); self._marker_alpha.setDecimals(2); self._marker_alpha.setSingleStep(0.05)
        self._marker_alpha.setValue(self._ann.get('marker_alpha', 0.85))
        fms.addRow("Alpha:", self._marker_alpha)

        self._marker_col  = _ColorSwatch(self._ann.get('marker_color', '#3B82F6'))
        fms.addRow("Fill Color:", self._marker_col)

        edge_h = QHBoxLayout()
        self._edge_col = _ColorSwatch(self._ann.get('marker_edge_color', '#1D4ED8'))
        self._edge_w   = QDoubleSpinBox()
        self._edge_w.setRange(0.0, 6.0); self._edge_w.setDecimals(1); self._edge_w.setSingleStep(0.5)
        self._edge_w.setValue(self._ann.get('marker_edge_width', 1.5))
        edge_h.addWidget(self._edge_col)
        edge_h.addWidget(QLabel("Width:")); edge_h.addWidget(self._edge_w)
        edge_h.addStretch()
        fms.addRow("Edge:", _hbox_widget(edge_h))
        lay.addWidget(self._marker_style_grp)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

        self._on_type_changed(self._type_combo.currentText())

    # ── Helpers ───────────────────────────────

    def _on_type_changed(self, t):
        is_text   = t in ('Text',)
        is_marker = t in ('Marker', 'Marker + Text')
        is_text_c = t in ('Text', 'Marker + Text')
        self._text_pos_grp.setVisible(is_text)
        self._tern_pos_grp.setVisible(is_marker)
        self._text_style_grp.setVisible(is_text_c)
        self._marker_style_grp.setVisible(is_marker)

    def _update_sum(self):
        s = self._t.value() + self._l.value() + self._r.value()
        ok = abs(s - 1.0) < 0.001
        color = '#16A34A' if ok else '#DC2626'
        self._sum_lbl.setText(f"T + L + R = {s:.3f}")
        self._sum_lbl.setStyleSheet(f"color:{color}; font-size:10px; font-weight:bold;")

    def _normalize(self):
        t, l, r = self._t.value(), self._l.value(), self._r.value()
        s = t + l + r
        if s > 0:
            for sp, v in [(self._t, t/s), (self._l, l/s), (self._r, r/s)]:
                sp.blockSignals(True); sp.setValue(round(v, 3)); sp.blockSignals(False)
        self._update_sum()

    def collect(self) -> dict:
        ann_type = self._type_combo.currentText()
        return {
            'type':              ann_type,
            'x_frac':            self._xfrac.value(),
            'y_frac':            self._yfrac.value(),
            't':                 self._t.value(),
            'l':                 self._l.value(),
            'r':                 self._r.value(),
            'text':              self._text_edit.text().strip() or 'Annotation',
            'color':             self._text_col.color(),
            'fontsize':          self._fs.value(),
            'bold':              self._bold.isChecked(),
            'italic':            self._italic.isChecked(),
            'show_box':          self._show_box.isChecked(),
            'box_color':         self._box_col.color(),
            'box_alpha':         self._box_alpha.value(),
            'marker':            _MARKER_CODES[self._marker_combo.currentIndex()],
            'marker_size':       self._marker_size.value(),
            'marker_alpha':      self._marker_alpha.value(),
            'marker_color':      self._marker_col.color(),
            'marker_edge_color': self._edge_col.color(),
            'marker_edge_width': self._edge_w.value(),
        }


def _hbox_widget(hbox: QHBoxLayout) -> QWidget:
    w = QWidget(); w.setLayout(hbox); return w


class ManageAnnotationsDialog(QDialog):
    """View, edit, reorder and delete existing annotations."""

    _TYPE_ICONS = {'Text': '', 'Marker': '●', 'Marker + Text': '●'}

    def __init__(self, annotations: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Annotations")
        self.setMinimumSize(640, 400)
        self._anns = [dict(a) for a in annotations]
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["", "Type", "Text / Symbol", "T", "L", "R"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 30)
        self._table.setColumnWidth(1, 90)
        self._table.setColumnWidth(3, 55)
        self._table.setColumnWidth(4, 55)
        self._table.setColumnWidth(5, 55)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.doubleClicked.connect(self._edit)
        lay.addWidget(self._table)

        btns = QHBoxLayout()
        for label, slot in [
            ("Add",   self._add),
            ("Edit",  self._edit),
            ("Delete",self._delete),
            ("▲ Up",    self._move_up),
            ("▼ Down",  self._move_down),
        ]:
            b = QPushButton(label); b.clicked.connect(slot); btns.addWidget(b)
        btns.addStretch()
        lay.addLayout(btns)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        self._reload()

    def _reload(self):
        self._table.setRowCount(0)
        for a in self._anns:
            r = self._table.rowCount()
            self._table.insertRow(r)

            ann_type = a.get('type', 'Text')
            icon = self._TYPE_ICONS.get(ann_type, '?')

            swatch = QTableWidgetItem()
            col = a.get('marker_color' if 'Marker' in ann_type else 'color', '#3B82F6')
            swatch.setBackground(QColor(col))
            self._table.setItem(r, 0, swatch)

            self._table.setItem(r, 1, QTableWidgetItem(f"{icon} {ann_type}"))

            if ann_type == 'Text':
                preview = a.get('text', '')
            elif ann_type == 'Marker':
                mc = a.get('marker', 'o')
                preview = _MARKER_NAMES[_MARKER_CODES.index(mc)] if mc in _MARKER_CODES else mc
            else:
                mc = a.get('marker', 'o')
                sym = _MARKER_NAMES[_MARKER_CODES.index(mc)] if mc in _MARKER_CODES else mc
                preview = f'{sym}  \u201c{a.get("text", "")}\u201d'
            self._table.setItem(r, 2, QTableWidgetItem(preview))

            t_val = a.get('t', 0.33)
            l_val = a.get('l', 0.33)
            r_val = a.get('r', 0.34)
            if ann_type == 'Text':
                self._table.setItem(r, 3, QTableWidgetItem(f"x={a.get('x_frac', 0.5):.2f}"))
                self._table.setItem(r, 4, QTableWidgetItem(f"y={a.get('y_frac', 0.5):.2f}"))
                self._table.setItem(r, 5, QTableWidgetItem("—"))
            else:
                self._table.setItem(r, 3, QTableWidgetItem(f"{t_val:.2f}"))
                self._table.setItem(r, 4, QTableWidgetItem(f"{l_val:.2f}"))
                self._table.setItem(r, 5, QTableWidgetItem(f"{r_val:.2f}"))

    def _selected_row(self):
        rows = self._table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _add(self):
        dlg = AnnotationDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._anns.append(dlg.collect())
            self._reload()

    def _edit(self):
        idx = self._selected_row()
        if idx < 0:
            return
        dlg = AnnotationDialog(ann=self._anns[idx], parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._anns[idx] = dlg.collect()
            self._reload(); self._table.selectRow(idx)

    def _delete(self):
        idx = self._selected_row()
        if idx >= 0:
            self._anns.pop(idx); self._reload()

    def _move_up(self):
        idx = self._selected_row()
        if idx > 0:
            self._anns[idx - 1], self._anns[idx] = self._anns[idx], self._anns[idx - 1]
            self._reload(); self._table.selectRow(idx - 1)

    def _move_down(self):
        idx = self._selected_row()
        if 0 <= idx < len(self._anns) - 1:
            self._anns[idx], self._anns[idx + 1] = self._anns[idx + 1], self._anns[idx]
            self._reload(); self._table.selectRow(idx + 1)

    def collect(self) -> list:
        return [dict(a) for a in self._anns]


class TriangleDisplayDialog(QDialog):
    """Full-figure dialog with right-click context menu for all settings."""

    def __init__(self, triangle_node, parent_window=None):
        super().__init__(parent_window)
        self.node = triangle_node
        self.parent_window = parent_window
        self.setWindowTitle("Ternary Composition Analysis")
        self.setMinimumSize(1000, 750)
        self._triangle_viewport = _full_triangle_viewport()
        self._last_layout_key = None
        self._pending_shared_cbar = None
        self._overlaid_stats_dlg = None
        self._overlaid_stats_data = []

        self._ternary_zoom_active    = False
        self._ternary_zoom_press     = None
        self._ternary_zoom_cids      = []
        self._ternary_zoom_rubberband = None
        self._ternary_zoom_bg = None   # blit background captured on press
        self._ternary_zoom_ax = None   # axes reference held during drag

        self._setup_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    # ── Helpers ─────────────────────────────

    def _is_multi(self) -> bool:
        return bool(self.node.input_data and
                    self.node.input_data.get('type') == 'multiple_sample_data')

    def _sample_names(self) -> list:
        if self._is_multi():
            return self.node.input_data.get('sample_names', [])
        return []

    def _single_sample_triangle_zoom_supported(self) -> bool:
        """Return whether ternary zoom is currently supported for single-sample view.

        The generic shared rectangle zoom is scientifically invalid for a single
        ternary simplex because it crops Cartesian projection space without
        redrawing ternary ticks/grid for a true sub-simplex viewport.
        The ternary-aware viewport zoom is implemented via custom handlers.
        """
        return True

    def _triangle_viewport_summary(self) -> str:
        """Return a short human-readable summary of the active single-sample viewport."""
        vp = _validate_triangle_viewport(self._triangle_viewport)
        if _is_full_triangle_viewport(vp):
            return "Full viewport"
        return (
            f"Viewport: A >= {vp['a_min'] * 100:.0f}%, "
            f"B >= {vp['b_min'] * 100:.0f}%, "
            f"C >= {vp['c_min'] * 100:.0f}%"
        )

    def _enable_ternary_zoom(self):
        """Activate ternary zoom: connect our mouse handlers.
        Canvas stays in Cursor so shared Cartesian zoom never fires.
        """
        if self._ternary_zoom_active:
            return
        self._ternary_zoom_active = True
        cid_p = self.canvas.mpl_connect(
            'button_press_event',   self._ternary_zoom_on_press)
        cid_m = self.canvas.mpl_connect(
            'motion_notify_event',  self._ternary_zoom_on_motion)
        cid_r = self.canvas.mpl_connect(
            'button_release_event', self._ternary_zoom_on_release)
        self._ternary_zoom_cids = [cid_p, cid_m, cid_r]

    def _disable_ternary_zoom(self):
        """Deactivate ternary zoom: disconnect handlers, clear rubber-band."""
        self._ternary_zoom_active = False
        self._ternary_zoom_press  = None
        for cid in self._ternary_zoom_cids:
            self.canvas.mpl_disconnect(cid)
        self._ternary_zoom_cids = []
        self._ternary_zoom_clear_rubberband(redraw=False)

    def _ternary_zoom_clear_rubberband(self, redraw: bool = True):
        """Remove rubber-band artist and clear all blit state.

        Args:
            redraw: whether to call draw_idle after removal.
        """
        if self._ternary_zoom_rubberband is not None:
            try:
                self._ternary_zoom_rubberband.remove()
            except Exception:
                pass
            self._ternary_zoom_rubberband = None
        self._ternary_zoom_bg = None
        self._ternary_zoom_ax = None
        if redraw:
            self.canvas.draw_idle()

    @staticmethod
    def _ternary_xdata_to_abc(xdata: float, ydata: float) -> tuple:
        """Convert mpltern Cartesian projection coords to visual ternary (a, b, c).

        mpltern 1.0.4 corner positions in data space (confirmed by probe):
            T corner (t=1): ( 0.0,      1.0)  → physical top
            L corner (l=1): (-1/sqrt3,  0.0)  → physical bottom-left
            R corner (r=1): (+1/sqrt3,  0.0)  → physical bottom-right

        The scatter call scatter(b, c, a) maps data elements to physical
        corners in a way that disagrees with the axis labels. The entire
        viewport engine (axis_specs, filtering, tick labels) operates in
        visual/label space where:
            a = Ag → visual bottom-left (L corner)
            b = V  → visual bottom-right (R corner)
            c = Cr → visual top (T corner)

        Correct inverse for visual (a, b, c) from physical (xdata, ydata):
            a = (1 - ydata - xdata * sqrt(3)) / 2    (Ag, bottom-left)
            b = (1 - ydata + xdata * sqrt(3)) / 2    (V,  bottom-right)
            c = ydata                                  (Cr, top)

        Returns:
            tuple: visual (a, b, c) floats; caller validates all >= 0.
        """
        a = (1.0 - ydata - xdata * math.sqrt(3.0)) / 2.0
        b = (1.0 - ydata + xdata * math.sqrt(3.0)) / 2.0
        c = ydata
        return a, b, c

    @staticmethod
    def _ternary_abc_to_xdata(a: float, b: float, c: float) -> tuple:
        """Convert visual ternary (a, b, c) to mpltern Cartesian (xdata, ydata).

        Forward of _ternary_xdata_to_abc. See that method for derivation.
        Visual convention: a=Ag=bottom-left, b=V=bottom-right, c=Cr=top.
            xdata = (b - a) / sqrt(3)
            ydata = c
        """
        return (b - a) / math.sqrt(3.0), c

    def _ternary_main_edge_px(self, ax) -> float:
        """Return the pixel length of the main triangle edge.

        Uses the bottom edge from L corner (-1/sqrt3, 0) to
        R corner (+1/sqrt3, 0) in mpltern's Cartesian data space.
        Edge length = 2/sqrt3 in data units.

        Args:
            ax: the active mpltern axes after draw.

        Returns:
            float: edge length in pixels (at least 1.0).
        """
        s = 1.0 / math.sqrt(3.0)
        pt_l = ax.transData.transform([-s, 0.0])
        pt_r = ax.transData.transform([ s, 0.0])
        return max(float(np.linalg.norm(pt_r - pt_l)), 1.0)

    def _ternary_zoom_on_press(self, event):
        """Record anchor vertex and capture blit background."""
        if not self._ternary_zoom_active:
            return
        if event.button != 1:
            if self._ternary_zoom_press is not None:
                self._ternary_zoom_press = None
                self._ternary_zoom_clear_rubberband()
            return
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            return
        a, b, c = self._ternary_xdata_to_abc(event.xdata, event.ydata)
        if a < -0.01 or b < -0.01 or c < -0.01:
            return

        self._ternary_zoom_press = event
        self._ternary_zoom_ax    = event.inaxes

        # Create animated Line2D at a degenerate zero-area triangle.
        # animated=True means canvas.draw() skips it, so the captured
        # background will not contain the rubber band.
        xp, yp = self._ternary_abc_to_xdata(a, b, c)
        line = Line2D([xp, xp, xp, xp], [yp, yp, yp, yp],
                      color='black', linewidth=1.5, linestyle='--',
                      zorder=100, animated=True)
        self._ternary_zoom_ax.add_line(line)
        self._ternary_zoom_rubberband = line

        # Full draw (rubber band excluded by animated=True), then capture.
        self.canvas.draw()
        try:
            self._ternary_zoom_bg = self.canvas.copy_from_bbox(
                self._ternary_zoom_ax.bbox)
        except Exception:
            self._ternary_zoom_bg = None

    def _ternary_zoom_on_motion(self, event):
        """Update rubber-band triangle in-place using blitting."""
        if not self._ternary_zoom_active or self._ternary_zoom_press is None:
            return
        if event.inaxes is None or event.xdata is None:
            return
        if self._ternary_zoom_rubberband is None:
            return

        press     = self._ternary_zoom_press
        ax        = self._ternary_zoom_ax
        drag_px   = math.sqrt((event.x - press.x)**2 + (event.y - press.y)**2)
        edge_px   = self._ternary_main_edge_px(ax)
        remaining = drag_px / edge_px

        a1, b1, c1   = self._ternary_xdata_to_abc(press.xdata, press.ydata)
        dominant_idx = int(np.argmax([a1, b1, c1]))
        vals         = [a1, b1, c1]
        dominant_val = vals[dominant_idx]

        if remaining <= 0 or remaining >= dominant_val:
            return

        mins = list(vals)
        mins[dominant_idx] = dominant_val - remaining
        a_min, b_min, c_min = mins[0], mins[1], mins[2]

        corners_abc = [
            (1.0 - b_min - c_min, b_min,               c_min              ),
            (a_min,               1.0 - a_min - c_min,  c_min              ),
            (a_min,               b_min,                1.0 - a_min - b_min),
        ]
        xs, ys = [], []
        for (ca, cb, cc) in corners_abc:
            xd, yd = self._ternary_abc_to_xdata(ca, cb, cc)
            xs.append(xd)
            ys.append(yd)
        xs.append(xs[0])
        ys.append(ys[0])

        self._ternary_zoom_rubberband.set_xdata(xs)
        self._ternary_zoom_rubberband.set_ydata(ys)

        if self._ternary_zoom_bg is not None:
            try:
                self.canvas.restore_region(self._ternary_zoom_bg)
                ax.draw_artist(self._ternary_zoom_rubberband)
                self.canvas.blit(ax.bbox)
                return
            except Exception:
                self._ternary_zoom_bg = None
        self.canvas.draw_idle()

    def _ternary_zoom_on_release(self, event):
        """On left release, compute final viewport and apply it."""
        if not self._ternary_zoom_active or self._ternary_zoom_press is None:
            return
        if event.button != 1:
            return

        press = self._ternary_zoom_press
        self._ternary_zoom_press = None
        self._ternary_zoom_clear_rubberband(redraw=False)

        if event.inaxes is None or event.xdata is None:
            return

        ax        = event.inaxes
        drag_px   = math.sqrt((event.x - press.x)**2 + (event.y - press.y)**2)
        edge_px   = self._ternary_main_edge_px(ax)
        remaining = drag_px / edge_px

        a1, b1, c1   = self._ternary_xdata_to_abc(press.xdata, press.ydata)
        dominant_idx = int(np.argmax([a1, b1, c1]))
        vals         = [a1, b1, c1]
        dominant_val = vals[dominant_idx]

        MIN_REMAINING = 0.05
        if remaining < MIN_REMAINING or remaining >= dominant_val:
            return

        mins = list(vals)
        mins[dominant_idx] = dominant_val - remaining

        viewport = {
            'a_min': max(0.0, mins[0]),
            'b_min': max(0.0, mins[1]),
            'c_min': max(0.0, mins[2]),
        }

        if not _validate_triangle_viewport(viewport):
            return

        self._triangle_viewport = viewport
        self._refresh()

    def _available_elements(self) -> list:
        if not self.node.input_data:
            return []
        elems = set()
        for p in self.node.input_data.get('particle_data', []):
            elems.update(p.get('elements', {}).keys())
        return sorted(elems)

    # ── UI ──────────────────────────────────

    def _setup_ui(self):
        """Build the triangle display UI and wire bottom actions without altering plot logic."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        self.figure = Figure(figsize=(14, 10), dpi=100, tight_layout=True)
        self.canvas = MplDraggableCanvas(self.figure)
        self.canvas.enable_view_limit_tracking(True)
        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._show_context_menu)
        main_layout.addWidget(self.canvas, stretch=1)

        self.canvas.mpl_connect('button_release_event', self._save_ann_positions)

        # ── Bottom toolbar ────────────────────────────────────────────
        tb = QHBoxLayout()
        tb.setContentsMargins(0, 2, 0, 0)
        btn_fmt = QPushButton("Plot format settings")
        btn_fmt.clicked.connect(self._open_plot_format_settings)
        btn_qty = QPushButton("Configure plot quantities")
        btn_qty.clicked.connect(self._open_configure_plot_quantities)
        btn_r = QPushButton("Reset layout")
        btn_r.setToolTip("Reset all subplot positions\n(or middle-click on the figure)")
        btn_r.clicked.connect(self._reset_layout)
        btn_e = QPushButton("Export figure")
        btn_e.clicked.connect(self._export_figure)
        tb.addWidget(btn_fmt); tb.addWidget(btn_qty)
        tb.addWidget(btn_r); tb.addWidget(btn_e)
        main_layout.addLayout(tb)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            "color: #6B7280; font-size: 11px; padding: 2px 8px; "
            "background-color: #F8FAFC; border-top: 1px solid #E2E8F0;")
        main_layout.addWidget(self.stats_label)

    # ── Context menu ────────────────────────

    def _show_context_menu(self, pos):
        """Build the intentionally minimal Triangle right-click menu.

        The context menu is intentionally limited to lightweight quick controls only:
        - `Quick Toggles` for fast visual toggles already supported by current config.
        - `Isotope Label` for quick label-mode switching.

        Full configuration, quantities, reset, export, and annotation entry points are
        intentionally excluded here to avoid duplicating bottom-button workflows:
        `Plot format settings`, `Configure plot quantities`, `Reset layout`, and
        `Export figure`.

        Preserved behavior:
        - Toggle and isotope label actions still update the same config keys.
        - Plot calculations/data semantics are unchanged.
        """
        cfg = self.node.config
        menu = QMenu(self)

        toggle_menu = menu.addMenu("Quick Toggles")
        self._add_toggle(toggle_menu, "Show Grid", 'show_grid')
        self._add_toggle(toggle_menu, "Show Color Bar", 'show_colorbar')
        self._add_toggle(toggle_menu, "Show Average Point", 'show_average_point')
        self._add_toggle(toggle_menu, "Show Stats Text", 'show_average_text')
        self._add_toggle(toggle_menu, "Show 2s Ellipse", 'show_confidence_ellipse')
        # Element filter mode is a 3-way dropdown — not a simple boolean toggle.
        # It is exposed in Configure Plot Quantities instead.

        lm = menu.addMenu("Isotope Label")
        for mode in LABEL_MODES:
            a = lm.addAction(mode)
            a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set('label_mode', v))

        in_subplots = (self._is_multi()
                       and cfg.get('display_mode', '') == 'Individual Subplots')
        if not in_subplots:
            mm = menu.addMenu("Mouse mode")
            if not self._is_multi() and self._ternary_zoom_active:
                current_mouse_mode = "Zoom"
            else:
                current_mouse_mode = self.canvas.mouse_mode()
            zoom_supported = self._is_multi() or self._single_sample_triangle_zoom_supported()
            for mode in ("Cursor", "Zoom"):
                action = mm.addAction(mode)
                action.setCheckable(True)
                action.setChecked(current_mouse_mode == mode)
                if mode == "Zoom" and not zoom_supported:
                    action.setChecked(False)
                    action.setEnabled(False)
                    action.setText("Zoom (unavailable for single-sample ternary)")
                    reason = (
                        "Single-sample ternary zoom is disabled until a true "
                        "ternary-aware viewport is implemented."
                    )
                    action.setStatusTip(reason)
                    action.setToolTip(reason)
                else:
                    action.triggered.connect(lambda _, m=mode: self._set_mouse_mode(m))

        # "Examine" — only in Individual Subplots mode when clicking a specific subplot
        if (self._is_multi()
                and cfg.get('display_mode', '') == 'Individual Subplots'):
            sn = self._subplot_under_cursor(pos)
            if sn is not None:
                dname = get_display_name(sn, cfg)
                menu.addSeparator()
                act = menu.addAction(f"Examine  '{dname}'")
                act.triggered.connect(lambda _=False, s=sn: self._examine_sample(s))

        menu.exec(QCursor.pos())

    def _subplot_under_cursor(self, widget_pos):
        """Return the sample key of the subplot under widget_pos, or None."""
        cw = self.canvas.width()
        ch = self.canvas.height()
        if cw <= 0 or ch <= 0:
            return None
        nx = widget_pos.x() / cw
        ny = 1.0 - widget_pos.y() / ch      # flip: Qt origin top-left, mpl bottom-left
        for ax in self.figure.get_axes():
            sn = getattr(ax, '_exam_sample_key', None)
            if sn is None:
                continue
            bb = ax.get_position()
            if bb.x0 <= nx <= bb.x1 and bb.y0 <= ny <= bb.y1:
                return sn
        return None

    def _examine_sample(self, sample_key):
        """Open a full single-sample ternary window for one subplot."""
        all_particles = self.node.input_data.get('particle_data', [])
        sample_particles = [p for p in all_particles
                            if p.get('source_sample') == sample_key]
        if not sample_particles:
            return

        single_input = {
            'type': 'sample_data',
            'particle_data': sample_particles,
        }

        node = TrianglePlotNode(parent_window=self.parent_window)
        node.config = dict(self.node.config)   # inherit element choices and style
        node.process_data(single_input)

        dname = get_display_name(sample_key, self.node.config)
        dlg = TriangleDisplayDialog(node, parent_window=self)
        dlg.setWindowTitle(f"Ternary — {dname}")
        dlg.setMinimumSize(1000, 750)
        dlg.show()

        # Hold a reference so the dialog isn't garbage-collected
        if not hasattr(self, '_examine_dialogs'):
            self._examine_dialogs = []
        self._examine_dialogs.append(dlg)
        dlg.finished.connect(
            lambda _: self._examine_dialogs.remove(dlg)
            if dlg in self._examine_dialogs else None)

    def _add_toggle(self, menu, label, key):
        a = menu.addAction(label)
        a.setCheckable(True)
        a.setChecked(self.node.config.get(key, False))
        a.triggered.connect(lambda checked, k=key: self._toggle(k, checked))

    def _toggle(self, key, value):
        self.node.config[key] = value
        self._refresh()

    def _set(self, key, value):
        self.node.config[key] = value
        self._refresh()

    def _set_mouse_mode(self, mode: str):
        """Update Triangle mouse interaction mode.

        For single-sample Zoom, keeps the canvas in Cursor mode and
        activates our own ternary zoom handlers instead of the shared
        Cartesian zoom path, which is scientifically invalid for mpltern.
        """
        if mode == "Zoom" and not self._is_multi():
            self.canvas.set_mouse_mode("TernaryZoom")
            self._enable_ternary_zoom()
            return
        self._disable_ternary_zoom()
        self.canvas.set_mouse_mode(mode)

    def _add_annotation(self):
        """Open annotation creator; preserves existing annotation data model/behavior."""
        dlg = AnnotationDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            anns = list(self.node.config.get('annotations', []))
            anns.append(dlg.collect())
            self.node.config['annotations'] = anns
            self._refresh()

    def _manage_annotations(self):
        """Open annotation manager; preserves existing annotation ordering/edit behavior."""
        anns = list(self.node.config.get('annotations', []))
        dlg = ManageAnnotationsDialog(anns, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config['annotations'] = dlg.collect()
            self._refresh()

    def _open_settings(self):
        """Open legacy combined settings dialog to preserve backward-compatible entry point."""
        dlg = TernarySettingsDialog(
            self.node.config, self._available_elements(),
            self._is_multi(), self._sample_names(), self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _open_plot_format_settings(self):
        """
        Open format-scoped settings dialog.

        This exposes visual controls only and preserves scientific/data selection semantics.
        """
        _snap = dict(self.node.config)
        dlg = TernarySettingsDialog(
            self.node.config, self._available_elements(),
            self._is_multi(), self._sample_names(), self, scope='format')
        dlg.preview_requested.connect(lambda cfg: (self.node.config.update(cfg), self._refresh()))
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()
        else:
            self.node.config.clear()
            self.node.config.update(_snap)
            self._refresh()

    def _open_configure_plot_quantities(self):
        """
        Open quantities-scoped settings dialog.

        This exposes element/data/filter choices only and preserves format/export behavior.
        """
        _snap = dict(self.node.config)
        dlg = TernarySettingsDialog(
            self.node.config, self._available_elements(),
            self._is_multi(), self._sample_names(), self, scope='quantities')
        dlg.preview_requested.connect(lambda cfg: (self.node.config.update(cfg), self._refresh()))
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()
        else:
            self.node.config.clear()
            self.node.config.update(_snap)
            self._refresh()

    def _reset_layout(self):
        """Reset subplot layout/view positions; same behavior as prior reset action."""
        self._last_layout_key = None
        self._pending_shared_cbar = None
        self._triangle_viewport = _full_triangle_viewport()
        self.canvas.reset_layout()
        if self._is_multi():
            self.canvas.restore_view_limits()
        self._refresh()

    def _export_figure(self):
        """Open the existing figure export workflow for the ternary figure."""
        download_matplotlib_figure(self.figure, self, "ternary_plot")

    # ── Refresh / draw ──────────────────────

    def _refresh(self):
        try:
            cfg = self.node.config

            if cfg.get('use_custom_figsize', False):
                self.figure.set_size_inches(cfg.get('figsize_w', 14.0),
                                            cfg.get('figsize_h', 10.0))
            self.figure.clear()
            self.figure.patch.set_facecolor(cfg.get('bg_color', '#FFFFFF'))

            plot_data = self.node.extract_plot_data()

            if not plot_data:
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5,
                        'No particle data available\nConnect to Sample Selector\n'
                        'Select 3 elements for ternary plot',
                        ha='center', va='center', transform=ax.transAxes,
                        fontsize=12, color='gray')
                ax.set_xticks([])
                ax.set_yticks([])
                self.stats_label.setText("")
                self.canvas.draw()
                return

            cfg = self.node.config

            if self._is_multi():
                mode = cfg.get('display_mode', DISPLAY_MODES[0])
                if mode == 'Individual Subplots':
                    self._draw_subplots(plot_data, cfg)
                elif mode == 'Combined Plot':
                    self._draw_combined(plot_data, cfg)
                else:
                    self._draw_overlaid(plot_data, cfg)
                for ax in self.figure.get_axes():
                    self._draw_annotations(ax, cfg, _full_triangle_viewport())
            else:
                ax = self.figure.add_subplot(111, projection='ternary')
                title = "Ternary Plot"
                if not _is_full_triangle_viewport(self._triangle_viewport):
                    title = f"{title} ({self._triangle_viewport_summary()})"
                self._draw_sample(
                    ax, plot_data, cfg, title,
                    viewport=self._triangle_viewport)
                apply_font_to_ternary(ax, cfg)
                self._draw_annotations(ax, cfg, self._triangle_viewport)

            self._update_stats(plot_data)

            in_overlaid = (self._is_multi() and
                           cfg.get('display_mode', '') == 'Overlaid Samples')
            if in_overlaid and cfg.get('show_average_text', False):
                self._open_or_update_stats_table()
            elif self._overlaid_stats_dlg is not None:
                self._overlaid_stats_dlg.hide()

            if self._is_multi():
                pending = self._pending_shared_cbar
                layout_key = (
                    len(self.figure.get_axes()),
                    cfg.get('display_mode', ''),
                    pending is not None,
                )
                if layout_key != self._last_layout_key:
                    _dmode = cfg.get('display_mode', '')
                    _n_ax = len(self.figure.get_axes())
                    if _dmode == 'Overlaid Samples' and _n_ax > 1:
                        # Left legend + right density colorbar
                        rect = [0.18, 0, 0.87, 1]
                    elif _dmode == 'Overlaid Samples':
                        # Left legend, no colorbar on right
                        rect = [0.18, 0, 1, 1]
                    elif pending is not None:
                        rect = [0, 0, 0.87, 1]
                    else:
                        rect = [0, 0, 1, 1]
                    self.figure.tight_layout(
                        pad=0.3, h_pad=0.1, w_pad=0.1, rect=rect)
                    # Clamp inter-subplot gaps — tight_layout is over-generous
                    # with ternary axis label room
                    if cfg.get('display_mode', '') == 'Individual Subplots':
                        self.figure.subplots_adjust(hspace=0.15, wspace=0.08)
                    self._last_layout_key = layout_key
                if pending is not None:
                    self._pending_shared_cbar = None
                    sm, cb_label = pending
                    cbar_ax = self.figure.add_axes([0.89, 0.10, 0.025, 0.80])
                    cbar = self.figure.colorbar(sm, cax=cbar_ax)
                    apply_font_to_colorbar_standalone(cbar, cfg, cb_label)
            else:
                self.figure.tight_layout()
                self._last_layout_key = None
            self.canvas.draw()
            self.canvas.snapshot_positions()
            self.canvas.snapshot_view_limits()

        except Exception as e:
            _itk_log.exception("Handled exception in _refresh")
            _itk_log.error(f"Error updating ternary display: {e}")
            import traceback
            traceback.print_exc()

    # ── Annotation rendering ─────────────────

    def _draw_annotations(self, ax, cfg, viewport=None):
        """Render all custom annotations onto a ternary axes.

        Text annotations are placed in axes-fraction space (draggable).
        Marker annotations are placed at ternary data coordinates.
        Position changes from dragging are saved back to config on mouse release.
        """
        anns = cfg.get('annotations', [])
        if not anns:
            return
        viewport = _validate_triangle_viewport(viewport)

        fc_cfg = get_font_config(cfg)

        for idx, ann in enumerate(anns):
            ann_type = ann.get('type', 'Text')

            # ── Common text style ───────────────────────────────────────
            txt    = ann.get('text', '')
            col    = ann.get('color', '#222222')
            fs     = ann.get('fontsize', 11)
            fw     = 'bold'   if ann.get('bold',   False) else 'normal'
            fi     = 'italic' if ann.get('italic', False) else 'normal'
            bbox_kw = None
            if ann.get('show_box', True):
                bbox_kw = dict(
                    boxstyle='round,pad=0.3',
                    fc=ann.get('box_color', '#FFFFFF'),
                    alpha=ann.get('box_alpha', 0.75),
                    ec='#AAAAAA', linewidth=0.5,
                )

            # ── Marker (scatter at ternary position) ────────────────────
            if ann_type in ('Marker', 'Marker + Text'):
                t = ann.get('t', 0.33)
                l = ann.get('l', 0.33)
                r = ann.get('r', 0.34)
                s = t + l + r
                if s > 0:
                    t, l, r = t/s, l/s, r/s
                a_val, b_val, c_val = l, r, t
                if not _point_in_triangle_viewport(a_val, b_val, c_val, viewport):
                    continue
                a_local, b_local, c_local = _remap_point_to_triangle_viewport(
                    a_val, b_val, c_val, viewport)
                try:
                    ax.scatter([c_local], [a_local], [b_local],
                               marker=ann.get('marker', 'o'),
                               s=ann.get('marker_size', 80),
                               c=[ann.get('marker_color', '#3B82F6')],
                               alpha=ann.get('marker_alpha', 0.85),
                               edgecolors=ann.get('marker_edge_color', '#1D4ED8'),
                               linewidths=ann.get('marker_edge_width', 1.5),
                               zorder=18)
                except Exception:
                    _itk_log.exception("Handled exception in _draw_annotations")

            # ── Text (axes-fraction position, draggable) ────────────────
            if ann_type in ('Text', 'Marker + Text') and txt:
                x_frac = ann.get('x_frac', 0.5)
                y_frac = ann.get('y_frac', 0.5)

                try:
                    text_art = ax.text(
                        x_frac, y_frac, txt,
                        transform=ax.transAxes,
                        fontsize=fs, color=col,
                        fontweight=fw, fontstyle=fi,
                        bbox=bbox_kw,
                        ha='center', va='center',
                        zorder=20,
                        picker=True,
                    )
                    text_art._ann_idx = idx
                    text_art.draggable(True, use_blit=True)
                except Exception:
                    _itk_log.exception("Handled exception in _draw_annotations")

    def _save_ann_positions(self, event=None):
        """Called on mouse button release — persist dragged text positions back to config.
        Args:
            event (Any): Qt event object.
        """
        if self.canvas.mouse_mode() == "Zoom" or self._ternary_zoom_active:
            return
        try:
            anns = self.node.config.get('annotations', [])
            changed = False
            for ax in self.figure.get_axes():
                for artist in ax.get_children():
                    idx = getattr(artist, '_ann_idx', None)
                    if idx is None or idx >= len(anns):
                        continue
                    ann = anns[idx]
                    if ann.get('type', 'Text') not in ('Text', 'Marker + Text'):
                        continue
                    try:
                        x, y = artist.get_position()
                        if (abs(x - ann.get('x_frac', 0.5)) > 0.001 or
                                abs(y - ann.get('y_frac', 0.5)) > 0.001):
                            ann['x_frac'] = round(float(x), 4)
                            ann['y_frac'] = round(float(y), 4)
                            changed = True
                    except Exception:
                        _itk_log.exception("Handled exception in _save_ann_positions")
            if changed:
                self.node.config['annotations'] = anns
        except Exception:
            _itk_log.exception("Handled exception in _save_ann_positions")

    def _update_stats(self, plot_data):
        """Update the bottom statistics label."""
        cfg = self.node.config
        mode = cfg.get('element_filter_mode', 'partial')
        if 'element_filter_mode' not in cfg:
            mode = 'partial' if cfg.get('average_only_with_all_elements', True) else 'any_one'

        def _n_avg(points):
            """Count points that pass the element filter for avg/stats."""
            if mode == 'any_one':
                return sum(1 for p in points
                           if p['a'] > 0 or p['b'] > 0 or p['c'] > 0)
            # partial and exact both require all three non-zero at render time
            return sum(1 for p in points
                       if p['a'] > 0 and p['b'] > 0 and p['c'] > 0)

        if self._is_multi():
            total = sum(len(sd) for sd in plot_data.values())
            n_samples = len(plot_data)
            parts = [f"{n_samples} samples", f"{total:,} particles plotted"]
            n_avg = sum(_n_avg(sd) for sd in plot_data.values())
            if n_avg < total:
                parts.append(f"{n_avg:,} used for averages")
            self.stats_label.setText("  ·  ".join(parts))
        else:
            total = len(plot_data)
            parts = [f"{total:,} particles plotted"]
            n_avg = _n_avg(plot_data)
            if n_avg < total:
                parts.append(f"{n_avg:,} used for averages")
            if not _is_full_triangle_viewport(self._triangle_viewport):
                parts.append(self._triangle_viewport_summary())
            self.stats_label.setText("  ·  ".join(parts))

    def _open_or_update_stats_table(self):
        """Show or refresh the per-sample statistics table for overlaid mode."""
        stats = self._overlaid_stats_data
        if not stats:
            return

        cfg = self.node.config
        ea = cfg.get('element_a', 'A') or 'A'
        eb = cfg.get('element_b', 'B') or 'B'
        ec = cfg.get('element_c', 'C') or 'C'

        row_labels = [
            'Particles (all 3 elements)',
            f'{ea} mean ± std (%)',
            f'{eb} mean ± std (%)',
            f'{ec} mean ± std (%)',
        ]
        col_labels = [s['dname'] for s in stats]
        n_rows = len(row_labels)
        n_cols = len(col_labels)

        if self._overlaid_stats_dlg is None:
            dlg = QDialog(self)
            dlg.setWindowTitle('Overlaid Samples — Statistics')
            dlg.setWindowFlags(
                dlg.windowFlags() | Qt.Window)
            dlg.setMinimumSize(max(320, n_cols * 140), 300)
            lay = QVBoxLayout(dlg)
            tbl = QTableWidget(n_rows, n_cols)
            tbl.setHorizontalHeaderLabels(col_labels)
            tbl.setVerticalHeaderLabels(row_labels)
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            tbl.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
            tbl.setAlternatingRowColors(True)
            lay.addWidget(tbl)
            bb = QDialogButtonBox(QDialogButtonBox.Close)
            def _on_close():
                dlg.hide()
                self.node.config['show_average_text'] = False
                self._refresh()
            bb.rejected.connect(_on_close)
            lay.addWidget(bb)
            dlg._tbl = tbl
            self._overlaid_stats_dlg = dlg

        dlg = self._overlaid_stats_dlg
        tbl = dlg._tbl

        if tbl.columnCount() != n_cols or tbl.rowCount() != n_rows:
            tbl.setColumnCount(n_cols)
            tbl.setRowCount(n_rows)
        tbl.setHorizontalHeaderLabels(col_labels)
        tbl.setVerticalHeaderLabels(row_labels)

        for ci, s in enumerate(stats):
            pm = '±'
            cell_vals = [
                f"{s['n']:,}",
                f"{s['ma']*100:.2f} {pm} {s['sa']*100:.2f}",
                f"{s['mb']*100:.2f} {pm} {s['sb']*100:.2f}",
                f"{s['mc']*100:.2f} {pm} {s['sc']*100:.2f}",
            ]
            for ri, v in enumerate(cell_vals):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignCenter)
                tbl.setItem(ri, ci, item)

        if not dlg.isVisible():
            dlg.show()

    @staticmethod
    def _element_filter_mask(a_raw, b_raw, c_raw, cfg):
        """Return a boolean mask for the element filter mode.

        Modes:
            'any_one'  – particle has at least one of the three elements > 0
            'partial'  – particle has ALL three elements > 0 (legacy "with all 3")
            'exact'    – particle has ALL three elements > 0 AND no other elements
                         (exact logic is enforced at extraction time; here same as partial)

        The 'exact' case is handled during data extraction in _extract_particles
        so that only exact-match particles enter the point list at all.  At render
        time the mask is therefore identical to 'partial'.
        """
        mode = cfg.get('element_filter_mode', 'partial')
        # Legacy migration: honour old boolean key if new key absent
        if 'element_filter_mode' not in cfg:
            legacy = cfg.get('average_only_with_all_elements', True)
            mode = 'partial' if legacy else 'any_one'
        if mode == 'any_one':
            return (a_raw > 0) | (b_raw > 0) | (c_raw > 0)
        # 'partial' and 'exact' both require all three non-zero at render time
        return (a_raw > 0) & (b_raw > 0) & (c_raw > 0)

    def _auto_colorbar_label(self, cfg, is_tribin=False):
        """Return an automatic colorbar label based on plot mode and color encoding config.

        Args:
            cfg: Node config dict.
            is_tribin: True when generating a label for a tribin plot (uses "Mean" prefix
                       when a color element is selected; "Count per bin" otherwise).

        Returns:
            str: Colorbar label suitable for ``apply_font_to_colorbar_standalone``.
        """
        # ── Tribin: new two-mode system ──────────────────────────────────────
        if is_tribin:
            tribin_color_mode = cfg.get('tribin_color_mode', 'density')
            if tribin_color_mode == 'isotope_measurement':
                tribin_color_isotope = cfg.get('tribin_color_isotope', '')
                tribin_color_dt = cfg.get('tribin_color_data_type', 'counts')
                dt_label_map = {
                    'counts':              'Counts',
                    'element_mass_fg':     'Mass (fg)',
                    'element_moles_fmol': 'Moles (fmol)',
                    'particle_mass_fg':   'Particle Mass (fg)',
                    'particle_moles_fmol': 'Particle Moles (fmol)',
                }
                dt_label = dt_label_map.get(tribin_color_dt, 'Counts')
                if tribin_color_isotope:
                    label_mode = cfg.get('label_mode', 'Symbol')
                    elem_label = format_element_label(
                        tribin_color_isotope, label_mode, Renderer.MATHTEXT, cfg)
                    return f"{elem_label} · {dt_label} (mean per bin)"
                # isotope_measurement selected but no isotope chosen — fall back
            return "Bin density (in particles)"

        # ── Scatter: new two-mode color encoding system ──────────────────────
        color_source = cfg.get('color_source', 'particle_quantity')
        if color_source == 'particle_quantity':
            qty_key = cfg.get('color_particle_quantity', 'total_counts')
            label_map = {
                'total_counts':              'Total Counts',
                'total_element_mass_fg':     'Total Isotope Mass (fg)',
                'total_element_moles_fmol': 'Total Isotope Moles (fmol)',
                'total_particle_mass_fg':   'Total Particle Mass (fg)',
                'total_particle_moles_fmol': 'Total Particle Moles (fmol)',
            }
            return label_map.get(qty_key, 'Total Counts')
        else:  # 'isotope_measurement'
            label_mode = cfg.get('label_mode', 'Symbol')
            color_isotope = cfg.get('color_isotope', '')
            color_isotope_dt = cfg.get('color_isotope_data_type', 'counts')
            dt_label_map = {
                'counts':              'Counts',
                'element_mass_fg':     'Mass (fg)',
                'element_moles_fmol': 'Moles (fmol)',
                'particle_mass_fg':   'Particle Mass (fg)',
                'particle_moles_fmol': 'Particle Moles (fmol)',
            }
            dt_label = dt_label_map.get(color_isotope_dt, 'Counts')
            if color_isotope:
                elem_label = format_element_label(
                    color_isotope, label_mode, Renderer.MATHTEXT, cfg)
                return f"{elem_label} · {dt_label}"
            return dt_label

    def _draw_sample(self, ax, sample_data, cfg, title, sample_color=None, viewport=None,
                     return_mappable=False):
        """
        Draw a ternary scatter or tribin for one sample.

        Args:
            ax:           mpltern axes
            sample_data:  list of dicts with keys 'a', 'b', 'c', 'color_val'
            cfg:          config dict
            title:        plot title string
            sample_color: if provided, all markers use this color (for overlaid mode)
            viewport:     optional lower-bound ternary viewport for single-sample redraw
        """
        if not sample_data:
            return

        ea = cfg.get('element_a', 'A')
        eb = cfg.get('element_b', 'B')
        ec = cfg.get('element_c', 'C')
        viewport = _validate_triangle_viewport(viewport)
        setup_ternary_axes(ax, [ea, eb, ec], cfg, viewport)

        # Vectorised extraction & viewport filtering
        a_raw = np.array([p['a'] for p in sample_data])
        b_raw = np.array([p['b'] for p in sample_data])
        c_raw = np.array([p['c'] for p in sample_data])

        tol = 1e-9
        # Base mask: viewport bounds only — used for scatter/tribin rendering so
        # that particles with zero in one element still appear on ternary edges.
        mask = (
            (a_raw >= viewport['a_min'] - tol) &
            (b_raw >= viewport['b_min'] - tol) &
            (c_raw >= viewport['c_min'] - tol)
        )

        if not mask.any():
            ax.text(
                0.5, 0.5,
                "No points in current viewport",
                transform=ax.transAxes,
                ha='center', va='center',
                color='#6B7280', fontsize=11,
            )
            return

        # Remap filtered points to local viewport coordinates
        remaining = _viewport_remaining(viewport)
        a_orig = a_raw[mask]
        b_orig = b_raw[mask]
        c_orig = c_raw[mask]
        a_vals = (a_orig - viewport['a_min']) / remaining
        b_vals = (b_orig - viewport['b_min']) / remaining
        c_vals = (c_orig - viewport['c_min']) / remaining

        # Separate average mask: applies element filter mode.
        # Only used for average/stats — scatter/tribin render uses the plain
        # viewport mask so edge-particles still appear.
        avg_only = mask & self._element_filter_mask(a_raw, b_raw, c_raw, cfg)
        a_orig_avg = a_raw[avg_only]
        b_orig_avg = b_raw[avg_only]
        c_orig_avg = c_raw[avg_only]
        a_vals_avg = (a_orig_avg - viewport['a_min']) / remaining
        b_vals_avg = (b_orig_avg - viewport['b_min']) / remaining
        c_vals_avg = (c_orig_avg - viewport['c_min']) / remaining

        plot_type = cfg.get('plot_type', 'Scatter Plot')
        cmap = cfg.get('colormap', 'YlGn')
        show_cbar = cfg.get('show_colorbar', True) and not return_mappable
        _mappable = None

        _ZERO_THRESH = 1e-12  # values below this are treated as scientifically zero

        def _warn_zero_color(ax_):
            """Overlay a note when the active color quantity is zero for all plotted points."""
            ax_.text(
                0.5, 0.04,
                "Given the chosen configuration, all plotted particles\n"
                "have a value of 0 in the color scale quantity.",
                transform=ax_.transAxes,
                ha='center', va='bottom',
                color='#6B7280', fontsize=9, style='italic',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.75,
                          edgecolor='#D1D5DB'),
            )

        if plot_type == 'Scatter Plot':
            size = cfg.get('marker_size', 20)
            alpha = cfg.get('marker_alpha', 0.7)

            if sample_color:
                # Overlaid multi-sample mode: use per-sample solid color, no colorbar
                scatter = ax.scatter(
                    c_vals, a_vals, b_vals,
                    s=size, alpha=alpha, color=sample_color,
                    edgecolors='white', linewidth=0.5, label=title)
            else:
                # New two-mode color encoding: color_val always populated by _extract_particles
                color_vals = np.array([p.get('color_val', 0) for p in sample_data])[mask]
                _cv_max = float(np.max(color_vals)) if color_vals.size else 0.0
                _use_log = (cfg.get('color_log_scale', False)
                            and _cv_max >= _ZERO_THRESH
                            and np.any(color_vals > 0))
                if _use_log:
                    _pos = color_vals[color_vals > 0]
                    _log_vmin = float(_pos.min())
                    _log_vmax = float(_cv_max)
                    scatter = ax.scatter(
                        c_vals, a_vals, b_vals,
                        s=size, alpha=alpha, c=color_vals, cmap=cmap,
                        norm=mcolors.LogNorm(
                            vmin=_log_vmin,
                            vmax=max(_log_vmax, _log_vmin)),
                        edgecolors='white', linewidth=0.5)
                else:
                    # Linear: force non-negative colorbar
                    scatter = ax.scatter(
                        c_vals, a_vals, b_vals,
                        s=size, alpha=alpha, c=color_vals, cmap=cmap,
                        edgecolors='white', linewidth=0.5)
                    # Clean fallback avoids 1e-12 on axis when all-zero
                    scatter.set_clim(
                        vmin=0,
                        vmax=_cv_max if _cv_max >= _ZERO_THRESH else 1.0)
                _mappable = scatter
                if show_cbar:
                    cbar = self.figure.colorbar(scatter, ax=ax, shrink=0.8, aspect=20)
                    apply_font_to_colorbar_standalone(
                        cbar, cfg, self._auto_colorbar_label(cfg, is_tribin=False))
                if np.all(np.abs(color_vals) < _ZERO_THRESH):
                    _warn_zero_color(ax)
        else:
            # ── Tribin: equilateral-triangle binning ────────────────────────
            _side_pct = cfg.get('tribin_side_pct', 5.0)
            _side = _side_pct / 100.0  # fraction of local viewport (0-1)
            _tb_alpha = cfg.get('tribin_alpha', 0.8)
            _tribin_cmode = cfg.get('tribin_color_mode', 'density')
            _tribin_isotope = cfg.get('tribin_color_isotope', '')
            _is_isotope = (_tribin_cmode == 'isotope_measurement'
                           and bool(_tribin_isotope))

            # ── Performance / validity warnings ──────────────────────────────────────
            _SIDE_PERF = 1.0 / 50  # 2% -> ~2500 triangles
            if 0 < _side < _SIDE_PERF:
                from PySide6.QtWidgets import QMessageBox
                _warn_box = QMessageBox()
                _warn_box.setIcon(QMessageBox.Warning)
                _warn_box.setWindowTitle('Tribin Performance Warning')
                _warn_box.setText(
                    f'Triangle side is {_side_pct:.1f}% of the viewport '
                    f'(< 2%). This may generate over '
                    f'{int((1.0/_side)**2):,} triangles and slow rendering.\n\n'
                    'Consider increasing Triangle Side (%) in Configure Plot.')
                _warn_box.exec()

            if _side <= 0 or _side >= 1.0:
                ax.text(0.5, 0.04,
                    'Triangle Side (%) is out of range -- adjust the setting.',
                    transform=ax.transAxes, ha='center', va='bottom',
                    color='#6B7280', fontsize=9, style='italic',
                    bbox=dict(boxstyle='round,pad=0.3',
                              facecolor='white', alpha=0.75,
                              edgecolor='#D1D5DB'))
                _mappable = None
            else:
                # ── Gather per-particle color values (isotope mode only) ────
                _cv_arr = (np.array([p.get('color_val', 0)
                                     for p in sample_data])[mask]
                           if _is_isotope else None)

                # ── Bin points into (i, j, tri_type) cells ─────────────
                #  tri_type 0 = up (triangle up), 1 = down (triangle down)
                _bins = {}
                for _k in range(len(a_vals)):
                    _a, _b = float(a_vals[_k]), float(b_vals[_k])
                    if _a < 0 or _b < 0:
                        continue
                    _i = int(_a / _side)
                    _j = int(_b / _side)
                    _fa = _a / _side - _i
                    _fb = _b / _side - _j
                    _ttype = 0 if (_fa + _fb) < 1.0 else 1
                    _key = (_i, _j, _ttype)
                    if _key not in _bins:
                        _bins[_key] = []
                    _bins[_key].append(
                        float(_cv_arr[_k]) if _is_isotope else 1)

                if not _bins:
                    _warn_zero_color(ax)
                    _mappable = None
                else:
                    # ── Compute scalar value per bin ──────────────────────
                    _bin_vals = {
                        k: (float(np.mean(v)) if _is_isotope
                            else float(len(v)))
                        for k, v in _bins.items()
                    }
                    _all_tb = np.array(
                        list(_bin_vals.values()), dtype=float)
                    _tb_max = float(_all_tb.max())
                    _tb_vmax = (_tb_max if _tb_max >= _ZERO_THRESH
                                else 1.0)
                    _tb_norm = mcolors.Normalize(
                        vmin=0.0, vmax=_tb_vmax)
                    _sm = cm.ScalarMappable(
                        cmap=cfg.get('colormap', 'YlGn'),
                        norm=_tb_norm)
                    _sm.set_array(_all_tb)
                    _cmap_fn = _sm.cmap  # callable colormap object

                    # ── Draw each non-empty bin as a filled triangle ─────────
                    for (_i, _j, _ttype), _val in _bin_vals.items():
                        if _ttype == 0:  # up triangle
                            _ca = [_i * _side, (_i + 1) * _side,
                                   _i * _side]
                            _cb = [_j * _side, _j * _side,
                                   (_j + 1) * _side]
                        else:            # down triangle
                            _ca = [(_i + 1) * _side, _i * _side,
                                   (_i + 1) * _side]
                            _cb = [_j * _side, (_j + 1) * _side,
                                   (_j + 1) * _side]
                        _cc = [1.0 - _a - _b
                               for _a, _b in zip(_ca, _cb)]
                        # Skip bins whose corners fall outside the simplex
                        if any(_c < -1e-9 for _c in _cc):
                            continue
                        _rgba = _cmap_fn(_tb_norm(_val))
                        # mpltern fill: (top=c, left=a, right=b)
                        ax.fill(_cc, _ca, _cb,
                                color=(*_rgba[:3], _tb_alpha),
                                linewidth=0)

                    _mappable = _sm

                    if _is_isotope and np.all(_all_tb < _ZERO_THRESH):
                        _warn_zero_color(ax)

                    if show_cbar:
                        cbar = self.figure.colorbar(
                            _sm, ax=ax, shrink=0.8, aspect=20)
                        apply_font_to_colorbar_standalone(
                            cbar, cfg,
                            self._auto_colorbar_label(
                                cfg, is_tribin=True))

        # Use avg_only arrays for average/stats so the element filter only
        # affects the mean marker and stats box, not the scatter/tribin render.
        self._draw_average_arrays(ax, a_orig_avg, b_orig_avg, c_orig_avg,
                                   a_vals_avg, b_vals_avg, c_vals_avg,
                                   cfg, title, viewport)

        if return_mappable:
            return _mappable

    def _draw_average(self, ax, sample_data, cfg, sample_name, viewport=None):
        """Draw average point with optional stats text and confidence ellipse."""
        if not cfg.get('show_average_point', True) or not sample_data:
            return
        viewport = _validate_triangle_viewport(viewport)

        a_arr = np.array([p['a'] for p in sample_data])
        b_arr = np.array([p['b'] for p in sample_data])
        c_arr = np.array([p['c'] for p in sample_data])
        avg_mask = self._element_filter_mask(a_arr, b_arr, c_arr, cfg)
        data = [p for p, m in zip(sample_data, avg_mask) if m]

        if not data:
            return

        a_vals = np.array([p['a'] for p in data])
        b_vals = np.array([p['b'] for p in data])
        c_vals = np.array([p['c'] for p in data])

        ma, mb, mc = a_vals.mean(), b_vals.mean(), c_vals.mean()
        sa, sb, sc = a_vals.std(), b_vals.std(), c_vals.std()
        if not _point_in_triangle_viewport(ma, mb, mc, viewport):
            return
        ma_local, mb_local, mc_local = _remap_point_to_triangle_viewport(
            ma, mb, mc, viewport)

        avg_color = cfg.get('average_point_color', '#FF0000')
        avg_size = cfg.get('average_point_size', 100)

        n_filt = len(data)
        n_total = len(sample_data)
        suffix = f" ({n_filt}/{n_total})" if n_filt < n_total else ""

        ax.scatter(
            [mc_local], [ma_local], [mb_local],
            s=avg_size, marker='*', color=avg_color,
            edgecolors='black', linewidth=1.5, zorder=10,
            label=f'Average{" (" + sample_name + ")" if sample_name else ""}{suffix}')

        if cfg.get('show_average_text', True):
            fp = make_font_properties(cfg)
            ea = cfg.get('element_a', 'A')
            eb = cfg.get('element_b', 'B')
            ec = cfg.get('element_c', 'C')

            text = (f"{ea}: {ma*100:.1f}±{sa*100:.1f}%\n"
                    f"{eb}: {mb*100:.1f}±{sb*100:.1f}%\n"
                    f"{ec}: {mc*100:.1f}±{sc*100:.1f}%")

            tx = min(mb_local + 0.15, 0.98)
            ty = min(mc_local + 0.01, 0.98)
            tz = max(1.0 - tx - ty, 0.01)
            ax.text(tx, ty, tz, text,
                    fontproperties=fp, color='black',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                              alpha=0.85, edgecolor='gray'),
                    ha='left', va='bottom', zorder=11)

        if (_is_full_triangle_viewport(viewport)
                and cfg.get('show_confidence_ellipse', False) and len(data) >= 3):
            params = confidence_ellipse_params(b_vals, c_vals, n_std=2.0)
            if params:
                ellipse = Ellipse(
                    (params['cx'], params['cy']),
                    params['width'], params['height'],
                    angle=params['angle_deg'],
                    fill=False, edgecolor=avg_color,
                    linewidth=2, linestyle='--', zorder=9)
                ax.add_patch(ellipse)

    def _draw_average_arrays(self, ax, a_orig, b_orig, c_orig,
                              a_local, b_local, c_local,
                              cfg, sample_name, viewport=None, n_unfiltered=None,
                              avg_color_override=None, stats_box_idx=0):
        """Draw average point, stats text and confidence ellipse from pre-filtered numpy arrays.

        Avoids list comprehension passes over already-extracted data.

        Args:
            ax:                     mpltern axes
            a_orig, b_orig, c_orig: original ternary fractions (pre-viewport remap),
                                    already filtered by viewport and all_elements
            a_local, b_local, c_local: viewport-remapped local coordinates (same length)
            cfg:                    config dict
            sample_name:            label string for this sample
            viewport:               ternary viewport dict (or None for full)
            n_unfiltered:           if provided and > len(a_orig), appends
                                    "(n_filt/n_total)" to the average point label
        """
        if not cfg.get('show_average_point', True) or len(a_orig) == 0:
            return
        viewport = _validate_triangle_viewport(viewport)

        ma, mb, mc = a_orig.mean(), b_orig.mean(), c_orig.mean()
        sa, sb, sc = a_orig.std(), b_orig.std(), c_orig.std()

        if not _point_in_triangle_viewport(ma, mb, mc, viewport):
            return
        ma_local, mb_local, mc_local = _remap_point_to_triangle_viewport(
            ma, mb, mc, viewport)

        avg_color = (avg_color_override if avg_color_override is not None
                     else cfg.get('average_point_color', '#FF0000'))
        avg_size  = cfg.get('average_point_size', 100)

        n_filt = len(a_orig)
        suffix = (f" ({n_filt}/{n_unfiltered})"
                  if n_unfiltered is not None and n_filt < n_unfiltered else "")
        label = f'Average{(" (" + sample_name + ")") if sample_name else ""}{suffix}'

        ax.scatter(
            [mc_local], [ma_local], [mb_local],
            s=avg_size, marker='*', color=avg_color,
            edgecolors='black', linewidth=1.5, zorder=10,
            label=label)

        if cfg.get('show_average_text', True):
            fp = make_font_properties(cfg)
            label_mode = cfg.get('label_mode', 'Symbol')
            ea = format_element_label(cfg.get('element_a', 'A') or 'A', label_mode, Renderer.MATHTEXT, cfg)
            eb = format_element_label(cfg.get('element_b', 'B') or 'B', label_mode, Renderer.MATHTEXT, cfg)
            ec = format_element_label(cfg.get('element_c', 'C') or 'C', label_mode, Renderer.MATHTEXT, cfg)

            title_line = f'-- {sample_name} --\n' if sample_name else ''
            text = (title_line +
                    f"{ea}: {ma*100:.1f}±{sa*100:.1f}%\n"
                    f"{eb}: {mb*100:.1f}±{sb*100:.1f}%\n"
                    f"{ec}: {mc*100:.1f}±{sc*100:.1f}%")

            y_pos = max(0.04, 0.97 - stats_box_idx * 0.34)
            ax.text(
                0.05, y_pos, text,
                transform=ax.transAxes,
                fontproperties=fp, color='black',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                          alpha=0.85, edgecolor='gray'),
                ha='left', va='top', zorder=11,
            )

        if (_is_full_triangle_viewport(viewport)
                and cfg.get('show_confidence_ellipse', False) and len(a_orig) >= 3):
            params = confidence_ellipse_params(b_orig, c_orig, n_std=2.0)
            if params:
                ellipse = Ellipse(
                    (params['cx'], params['cy']),
                    params['width'], params['height'],
                    angle=params['angle_deg'],
                    fill=False, edgecolor=avg_color,
                    linewidth=2, linestyle='--', zorder=9)
                ax.add_patch(ellipse)

    # ── Multi-sample layouts ────────────────

    def _draw_subplots(self, plot_data, cfg):
        """Draw one ternary subplot per sample in a 2-column grid
        with a single shared density/color legend spanning the full
        data range across all plots.

        Args:
            plot_data (Any): dict mapping sample name to point list.
            cfg (Any): node config dict.
        """
        samples = list(plot_data.keys())
        n = len(samples)
        cols = 3 if n >= 5 else min(2, n)
        rows = math.ceil(n / cols)

        if (cfg.get('plot_type', 'Scatter Plot') != 'Scatter Plot'
                and cfg.get('show_colorbar', True)):
            self.figure.subplots_adjust(
                left=0.07, right=0.85,
                top=0.91, bottom=0.09,
                hspace=0.15, wspace=0.10)

        mappables = []
        for idx, sn in enumerate(samples):
            ax = self.figure.add_subplot(
                rows, cols, idx + 1, projection='ternary')
            ax._exam_sample_key = sn          # for "Examine this ternary" right-click
            sd = plot_data[sn]
            if sd:
                dname = get_display_name(sn, cfg)
                m = self._draw_sample(
                    ax, sd, cfg, dname, return_mappable=True)
                if m is not None:
                    mappables.append(m)
                fc = get_font_config(cfg)
                ax.set_title(
                    dname, fontsize=fc['size'] - 2,
                    color=fc['color'])
                apply_font_to_ternary(ax, cfg)

        self._pending_shared_cbar = None
        if mappables and cfg.get('show_colorbar', True):
            global_min = float('inf')
            global_max = float('-inf')
            for m in mappables:
                try:
                    arr = m.get_array()
                    if arr is not None and len(arr) > 0:
                        vmin = float(np.ma.min(arr))
                        vmax = float(np.ma.max(arr))
                        if np.isfinite(vmin):
                            global_min = min(global_min, vmin)
                        if np.isfinite(vmax):
                            global_max = max(global_max, vmax)
                except Exception:
                    pass

            if (np.isfinite(global_min) and np.isfinite(global_max)
                    and global_max > global_min):
                norm = mcolors.Normalize(
                    vmin=global_min, vmax=global_max)
                for m in mappables:
                    try:
                        m.set_norm(norm)
                    except Exception:
                        pass
                sm = cm.ScalarMappable(
                    cmap=cfg.get('colormap', 'YlGn'), norm=norm)
                sm.set_array([])
                self._pending_shared_cbar = (
                    sm, self._auto_colorbar_label(
                        cfg,
                        is_tribin=(cfg.get('plot_type', 'Scatter Plot') != 'Scatter Plot')))

    def _draw_combined(self, plot_data, cfg):
        ax = self.figure.add_subplot(111, projection='ternary')
        combined = []
        for sd in plot_data.values():
            combined.extend(sd)
        if combined:
            self._draw_sample(ax, combined, cfg,
                              f"Combined ({len(plot_data)} samples)")
            apply_font_to_ternary(ax, cfg)

    def _draw_overlaid(self, plot_data, cfg):
        """Render all samples on a single ternary axes.

        Each sample keeps its unique solid colour; alpha (darkness) encodes
        the chosen colour-scale quantity (same config as single-sample scatter)
        normalised globally across all samples so the greyscale bar is shared.
        """
        ax = self.figure.add_subplot(111, projection='ternary')

        ea = cfg.get('element_a', 'A')
        eb = cfg.get('element_b', 'B')
        ec = cfg.get('element_c', 'C')
        setup_ternary_axes(ax, [ea, eb, ec], cfg)

        size = cfg.get('marker_size', 20)
        alpha_base = cfg.get('marker_alpha', 0.7)
        sample_mean_colors = cfg.get('sample_mean_colors', {})
        legend_handles = []
        self._overlaid_stats_data = []
        _ZERO_THRESH = 1e-12

        # ── Pass 1: gather all color_vals to find global range ───────────────
        all_cv = []
        for sd in plot_data.values():
            if sd:
                for p in sd:
                    all_cv.append(p.get('color_val', 0.0))

        global_max = float(max(all_cv)) if all_cv else 0.0
        all_zero = global_max < _ZERO_THRESH

        # ── Pass 2: draw each sample ─────────────────────────────────────────
        for idx, (sn, sd) in enumerate(plot_data.items()):
            if not sd:
                continue
            sample_color = get_sample_color(sn, idx, cfg)
            mean_color = sample_mean_colors.get(sn, sample_color)
            dname = get_display_name(sn, cfg)

            a_vals = np.array([p['a'] for p in sd])
            b_vals = np.array([p['b'] for p in sd])
            c_vals = np.array([p['c'] for p in sd])
            color_vals = np.array([p.get('color_val', 0.0) for p in sd])

            if all_zero:
                # Flat mid-alpha when every point is zero
                alphas = np.full(len(a_vals), 0.45)
            else:
                norm_vals = np.clip(color_vals / global_max, 0.0, 1.0)
                # [0.10, 0.90]: faintest points still visible, darkest fully opaque
                alphas = 0.10 + 0.80 * norm_vals

            rgb = mcolors.to_rgb(sample_color)
            rgba = np.zeros((len(a_vals), 4))
            rgba[:, :3] = rgb
            rgba[:, 3] = alphas
            ax.scatter(c_vals, a_vals, b_vals, s=size, c=rgba,
                       edgecolors='none', linewidth=0.0)

            # Legend handle
            if cfg.get('show_average_point', True):
                legend_handles.append(
                    Line2D([0], [0], marker='*', color=sample_color,
                           markerfacecolor=mean_color, markeredgecolor='black',
                           markersize=11, linewidth=3, label=dname))
            else:
                legend_handles.append(Patch(facecolor=sample_color, label=dname))

            # Average marker (element-filter-aware)
            avg_mask = self._element_filter_mask(a_vals, b_vals, c_vals, cfg)
            if avg_mask.any():
                a_avg = a_vals[avg_mask]
                b_avg = b_vals[avg_mask]
                c_avg = c_vals[avg_mask]
                self._overlaid_stats_data.append({
                    'sn': sn, 'dname': dname,
                    'n': int(avg_mask.sum()),
                    'ma': float(a_avg.mean()), 'sa': float(a_avg.std()),
                    'mb': float(b_avg.mean()), 'sb': float(b_avg.std()),
                    'mc': float(c_avg.mean()), 'sc': float(c_avg.std()),
                })
                cfg_marker_only = dict(cfg, show_average_text=False)
                self._draw_average_arrays(
                    ax, a_avg, b_avg, c_avg, a_avg, b_avg, c_avg,
                    cfg_marker_only, dname, None, n_unfiltered=len(a_vals),
                    avg_color_override=mean_color,
                    stats_box_idx=0,
                )

        # ── Shared greyscale colorbar ─────────────────────────────────────────
        if cfg.get('show_colorbar', True):
            _vmax = global_max if not all_zero else 1.0
            norm = mcolors.Normalize(vmin=0, vmax=_vmax)
            sm = cm.ScalarMappable(cmap='Greys', norm=norm)
            sm.set_array([])
            cbar = self.figure.colorbar(sm, ax=ax, shrink=0.65, aspect=22, pad=0.10)
            # Label: auto-generated quantity name + overlaid note
            qty_label = self._auto_colorbar_label(cfg, is_tribin=False)
            apply_font_to_colorbar_standalone(
                cbar, cfg, qty_label + '\n(alpha ~ value, all samples)')

        # ── All-zero warning ──────────────────────────────────────────────────
        if all_zero:
            ax.text(
                0.5, 0.04,
                'Given the chosen configuration, all plotted particles\n'
                'have a value of 0 in the color scale quantity.',
                transform=ax.transAxes,
                ha='center', va='bottom',
                color='#6B7280', fontsize=9, style='italic',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                          alpha=0.75, edgecolor='#D1D5DB'),
            )

        fp = make_font_properties(cfg)
        if legend_handles:
            ax.legend(
                handles=legend_handles,
                loc='upper right',
                bbox_to_anchor=(-0.02, 1.0),
                ncol=1,
                framealpha=0.9,
                prop=fp,
            )

        apply_font_to_ternary(ax, cfg)

class TrianglePlotNode(QObject):
    """
    Ternary plot node with right-click driven configuration.
    """

    position_changed = Signal(object)
    configuration_changed = Signal()

    DEFAULT_CONFIG = {
        'custom_title': 'Ternary Plot',
        'element_a': '',
        'element_b': '',
        'element_c': '',
        'color_element': '',          # tribin: retained for backward compat only (not used)
        # Tribin color encoding (new two-mode system)
        'tribin_color_mode': 'density',        # 'density' | 'isotope_measurement'
        'tribin_color_isotope': '',            # isotope label for isotope_measurement mode
        'tribin_color_data_type': 'counts',   # data type key for isotope_measurement mode
        # Scatter color encoding (new two-mode system)
        'color_source': 'particle_quantity',   # 'particle_quantity' | 'isotope_measurement'
        'color_particle_quantity': 'total_counts',  # MODE A key
        'color_isotope': '',                   # MODE B: isotope label
        'color_isotope_data_type': 'counts',   # MODE B: data type key
        'color_log_scale': False,              # scatter: log₁₀ colorbar
        'data_type_display': 'Counts (%)',
        'plot_type': 'Scatter Plot',
        'marker_size': 20,
        'marker_alpha': 0.7,
        'tribin_side_pct': 5.0,
        'tribin_alpha': 0.8,
        'show_grid': True,
        'colored_axes': False,
        'axis_a_color': '#E74C3C',
        'axis_b_color': '#27AE60',
        'axis_c_color': '#2980B9',
        'colormap': 'YlGn',
        'show_colorbar': True,
        'min_total': 0.0,
        'max_particles': 100_000_000,
        'show_average_point': True,
        'average_point_color': '#FF0000',
        'average_point_size': 100,
        'show_average_text': True,
        'element_filter_mode': 'partial',
        'show_confidence_ellipse': False,
        'display_mode': 'Individual Subplots',
        'sample_colors': {},
        'sample_name_mappings': {},
        'sample_mean_colors': {},
        'font_family': 'Times New Roman',
        'font_size': 18,
        'font_bold': False,
        'font_italic': False,
        'font_color': '#000000',
        'label_mode':  'Symbol',
        'annotations': [],
        'legend_show':     False,
        'legend_position': 'best',
        'legend_outside':  False,
        'bg_color':          '#FFFFFF',
        'export_format':     'svg',
        'export_dpi':        300,
        'use_custom_figsize': False,
        'figsize_w':         14.0,
        'figsize_h':         10.0,
    }

    def __init__(self, parent_window=None):
        super().__init__()
        self.title = "Ternary Plot"
        self.node_type = "triangle_plot"
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        self.config = dict(self.DEFAULT_CONFIG)
        self.input_data = None
        self.plot_widget = None

    def set_position(self, pos):
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        dlg = TriangleDisplayDialog(self, parent_window)
        dlg.exec()
        return True

    def process_data(self, input_data):
        if not input_data:
            return
        self.input_data = input_data

        ea = self.config.get('element_a', '')
        if not ea or ea.startswith('--'):
            self._auto_configure_elements()

        self.configuration_changed.emit()

    def _auto_configure_elements(self):
        """Pick first 3 elements from input data."""
        if not self.input_data:
            return
        elems = set()
        for p in self.input_data.get('particle_data', []):
            elems.update(p.get('elements', {}).keys())
        elems = sorted(elems)
        if len(elems) >= 3:
            self.config['element_a'] = elems[0]
            self.config['element_b'] = elems[1]
            self.config['element_c'] = elems[2]

    # ── Data extraction ─────────────────────

    def extract_plot_data(self):
        """
        Extract ternary data — normalised fractions of the three selected elements.

        Returns:
            list (single sample) or dict (multi-sample) of point dicts,
            each with keys 'a', 'b', 'c', 'total', and 'color_val'.
            Returns None if data is insufficient.
        """
        if not self.input_data:
            return None

        ea = self.config.get('element_a', '')
        eb = self.config.get('element_b', '')
        ec = self.config.get('element_c', '')

        if not ea or not eb or not ec:
            return None
        if ea.startswith('--') or eb.startswith('--') or ec.startswith('--'):
            return None

        dk = TERNARY_DATA_KEY_MAPPING.get(
            self.config.get('data_type_display', 'Counts (%)'), 'elements')
        itype = self.input_data.get('type')

        if itype == 'sample_data':
            return self._extract_single(dk, ea, eb, ec)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(dk, ea, eb, ec)
        return None

    def _extract_particles(self, particles, dk, ea, eb, ec):
        """Extract ternary points from a list of particle dicts.

        For each particle, reads the three element values from the chosen data key,
        normalises them to fractions summing to 1.0, and populates 'color_val'
        based on the current color encoding config.

        Args:
            particles:  list of particle dicts
            dk:         composition data key ('elements', 'element_mass_fg', etc.)
            ea, eb, ec: element label strings for the three ternary axes
        """
        min_total = self.config.get('min_total', 0.0)
        max_pts = self.config.get('max_particles', 100_000_000)
        filter_mode = self.config.get('element_filter_mode', 'partial')
        # Legacy migration
        if 'element_filter_mode' not in self.config:
            filter_mode = 'partial' if self.config.get(
                'average_only_with_all_elements', True) else 'any_one'

        plot_type = self.config.get('plot_type', 'Scatter Plot')

        # Scatter color config (read once per call for efficiency)
        color_source = self.config.get('color_source', 'particle_quantity')
        color_particle_qty = self.config.get('color_particle_quantity', 'total_counts')
        color_isotope = self.config.get('color_isotope', '')
        color_isotope_dk = _COLOR_ISOTOPE_DK_MAP.get(
            self.config.get('color_isotope_data_type', 'counts'), 'elements')

        # Tribin color config (new two-mode system)
        tribin_color_mode = self.config.get('tribin_color_mode', 'density')
        tribin_color_isotope = self.config.get('tribin_color_isotope', '')
        tribin_color_dk = _COLOR_ISOTOPE_DK_MAP.get(
            self.config.get('tribin_color_data_type', 'counts'), 'elements')

        result = []

        for p in particles:
            if len(result) >= max_pts:
                break
            d = p.get(dk, {})
            va = d.get(ea, 0)
            vb = d.get(eb, 0)
            vc = d.get(ec, 0)

            try:
                if (np.isnan(va) or np.isnan(vb) or np.isnan(vc)
                        or va < 0 or vb < 0 or vc < 0):
                    continue
            except TypeError:
                continue

            total = va + vb + vc
            if total < min_total or total <= 0:
                continue

            # 'exact' mode: particle must have ONLY the three selected elements
            # and no others with a non-zero value in this data key.
            if filter_mode == 'exact':
                other_vals = [v for k, v in d.items()
                              if k not in (ea, eb, ec) and v > 0]
                if other_vals or va <= 0 or vb <= 0 or vc <= 0:
                    continue
            # 'partial' mode: all three selected elements must be present.
            # 'any_one' mode: no extraction-time filter beyond total > 0 —
            # the render-time mask handles which points feed the avg marker.
            elif filter_mode == 'partial':
                if va <= 0 or vb <= 0 or vc <= 0:
                    continue

            point = {
                'a': va / total,
                'b': vb / total,
                'c': vc / total,
                'total': total,
            }

            # ── Color value ─────────────────────────────────────────────────
            if plot_type == 'Scatter Plot':
                # New two-mode system: always populate color_val for scatter
                if color_source == 'particle_quantity':
                    if color_particle_qty == 'total_counts':
                        cv = float(sum(p.get('elements', {}).values()))
                    else:
                        cv = float(p.get('totals', {}).get(color_particle_qty) or 0)
                else:  # 'isotope_measurement'
                    if color_isotope:
                        cv = float(
                            p.get(color_isotope_dk, {}).get(color_isotope) or 0)
                    else:
                        cv = 0.0
                point['color_val'] = cv
            else:
                # Tribin: new two-mode system
                if (tribin_color_mode == 'isotope_measurement'
                        and tribin_color_isotope):
                    point['color_val'] = float(
                        p.get(tribin_color_dk, {}).get(tribin_color_isotope) or 0)

            result.append(point)

        return result or None

    def _extract_single(self, dk, ea, eb, ec):
        particles = self.input_data.get('particle_data')
        if not particles:
            return None
        return self._extract_particles(particles, dk, ea, eb, ec)

    def _extract_multi(self, dk, ea, eb, ec):
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
            pts = self._extract_particles(plist, dk, ea, eb, ec)
            if pts:
                result[sn] = pts
        return result or None

