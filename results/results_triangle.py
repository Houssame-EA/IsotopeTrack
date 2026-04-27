"""
Ternary Plot Node — full-figure view with right-click context menu.

Features:
- Three-element ternary composition diagram (mpltern)
- Scatter and density (hexbin) plot types
- Color-by-fourth-element option for scatter plots
- Average point with optional 2σ confidence ellipse
- Particle statistics bar (total, filtered, per-sample)
- Multiple sample support (overlaid, subplots, side-by-side, combined)
- Right-click context menu replaces sidebar for all settings
- Shared font, color, and export utilities via shared_plot_utils
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QPushButton,
    QLineEdit, QFrame, QScrollArea, QWidget, QMenu, QSlider,
    QDialogButtonBox, QMessageBox, QColorDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QCursor
from matplotlib.figure import Figure
from matplotlib.patches import Ellipse
import numpy as np
import math
import mpltern

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS,
    TERNARY_DATA_TYPE_OPTIONS, TERNARY_DATA_KEY_MAPPING,
    get_font_config, make_font_properties,
    apply_font_to_ternary, apply_font_to_colorbar_standalone,
    FontSettingsGroup, LegendGroup, ExportSettingsGroup, MplDraggableCanvas,
    LABEL_MODES, format_element_label,
    get_sample_color, get_display_name,
    download_matplotlib_figure,
)


DISPLAY_MODES = [
    'Individual Subplots',
    'Side by Side Subplots',
    'Combined Plot',
    'Overlaid Samples',
]

PLOT_TYPES = ['Scatter Plot', 'Density Plot (Hexbin)']

COLORMAPS = [
    'YlGn', 'viridis', 'plasma', 'inferno', 'magma', 'cividis',
    'YlOrRd', 'BuPu', 'GnBu', 'PuBu', 'YlGnBu', 'PuBuGn',
    'Blues', 'Greens', 'Oranges', 'Reds', 'Purples', 'Greys',
    'coolwarm', 'RdYlBu', 'Spectral', 'turbo', 'jet',
]


def setup_ternary_axes(ax, element_labels, config):
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
    """
    fp   = make_font_properties(config)
    fc   = get_font_config(config)
    mode = config.get('label_mode', 'Symbol')
    fmt  = [format_element_label(e, mode) for e in element_labels]

    ax.set_llabel(fmt[0], fontproperties=fp, color=fc['color'])
    ax.set_rlabel(fmt[1], fontproperties=fp, color=fc['color'])
    ax.set_tlabel(fmt[2], fontproperties=fp, color=fc['color'])

    if config.get('show_grid', True):
        ax.grid(True, alpha=0.3)
        ticks = [0, 0.2, 0.4, 0.6, 0.8, 1.0]
        tick_labels = [f'{int(t * 100)}%' for t in ticks]
        for axis in (ax.taxis, ax.laxis, ax.raxis):
            axis.set_ticks(ticks)
            axis.set_ticklabels(tick_labels)
            for lbl in axis.get_ticklabels():
                lbl.set_fontproperties(fp)
                lbl.set_color(fc['color'])
    else:
        ax.grid(False)

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
        return None


class TernarySettingsDialog(QDialog):
    """Full settings dialog opened from right-click → Configure."""

    def __init__(self, config, available_elements, is_multi, sample_names, parent=None):
        """
        Args:
            config (Any): Configuration dictionary.
            available_elements (Any): The available elements.
            is_multi (Any): The is multi.
            sample_names (Any): The sample names.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("Ternary Plot Settings")
        self.setMinimumWidth(500)
        self._cfg = dict(config)
        self._elems = available_elements
        self._is_multi = is_multi
        self._sample_names = sample_names
        self._build_ui()

    # ── UI construction ─────────────────────

    def _build_ui(self):
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
            self.display_mode.addItems(DISPLAY_MODES)
            self.display_mode.setCurrentText(self._cfg.get('display_mode', DISPLAY_MODES[0]))
            fl.addRow("Display Mode:", self.display_mode)
            layout.addWidget(g)

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

        self.color_elem = QComboBox()
        self.color_elem.addItems(['(None — use index)'] + self._elems)
        ce = self._cfg.get('color_element', '')
        if ce in self._elems:
            self.color_elem.setCurrentText(ce)
        fl.addRow("Color By Element:", self.color_elem)

        layout.addWidget(g)

        g = QGroupBox("Data Type")
        fl = QFormLayout(g)
        self.data_type = QComboBox()
        self.data_type.addItems(TERNARY_DATA_TYPE_OPTIONS)
        self.data_type.setCurrentText(self._cfg.get('data_type_display', 'Counts (%)'))
        fl.addRow("Data:", self.data_type)
        self.label_mode_combo = QComboBox()
        self.label_mode_combo.addItems(LABEL_MODES)
        self.label_mode_combo.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
        fl.addRow("Label Mode:", self.label_mode_combo)
        layout.addWidget(g)

        g = QGroupBox("Plot Style")
        fl = QFormLayout(g)

        self.plot_type = QComboBox()
        self.plot_type.addItems(PLOT_TYPES)
        self.plot_type.setCurrentText(self._cfg.get('plot_type', 'Scatter Plot'))
        self.plot_type.currentTextChanged.connect(self._on_plot_type_changed)
        fl.addRow("Plot Type:", self.plot_type)

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

        self._hexbin_frame = QFrame()
        hfl = QFormLayout(self._hexbin_frame)
        hfl.setContentsMargins(0, 0, 0, 0)

        self.hexbin_grid = QSpinBox()
        self.hexbin_grid.setRange(10, 100)
        self.hexbin_grid.setValue(self._cfg.get('hexbin_gridsize', 30))
        hfl.addRow("Grid Size:", self.hexbin_grid)

        self.hexbin_alpha = QSlider(Qt.Horizontal)
        self.hexbin_alpha.setRange(10, 100)
        self.hexbin_alpha.setValue(int(self._cfg.get('hexbin_alpha', 0.8) * 100))
        hfl.addRow("Transparency:", self.hexbin_alpha)
        fl.addRow(self._hexbin_frame)

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

        self.cbar_label = QLineEdit(self._cfg.get('colorbar_label', 'Density'))
        fl.addRow("Color Bar Label:", self.cbar_label)

        layout.addWidget(g)

        self._on_plot_type_changed()

        g = QGroupBox("Average Point")
        fl = QFormLayout(g)

        self.show_avg = QCheckBox()
        self.show_avg.setChecked(self._cfg.get('show_average_point', True))
        fl.addRow("Show Average:", self.show_avg)

        self.avg_only_all = QCheckBox()
        self.avg_only_all.setChecked(self._cfg.get('average_only_with_all_elements', True))
        fl.addRow("Only Particles With All 3:", self.avg_only_all)

        self.show_avg_text = QCheckBox()
        self.show_avg_text.setChecked(self._cfg.get('show_average_text', True))
        fl.addRow("Show Stats Text:", self.show_avg_text)

        self.show_ellipse = QCheckBox()
        self.show_ellipse.setChecked(self._cfg.get('show_confidence_ellipse', False))
        fl.addRow("Show 2σ Confidence Ellipse:", self.show_ellipse)

        self.avg_size = QSpinBox()
        self.avg_size.setRange(20, 300)
        self.avg_size.setValue(self._cfg.get('average_point_size', 100))
        fl.addRow("Average Marker Size:", self.avg_size)

        self._avg_color = QColor(self._cfg.get('average_point_color', '#FF0000'))
        self.avg_color_btn = QPushButton()
        self.avg_color_btn.setStyleSheet(
            f"background-color: {self._avg_color.name()}; min-height: 25px; border: 1px solid black;")
        self.avg_color_btn.clicked.connect(self._pick_avg_color)
        fl.addRow("Average Color:", self.avg_color_btn)

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

        layout.addWidget(g)

        if self._is_multi:
            g = QGroupBox("Sample Colors & Names")
            vl = QVBoxLayout(g)
            self._color_btns = {}
            self._name_edits = {}
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

                rst = QPushButton("↺")
                rst.setFixedSize(22, 22)
                rst.setToolTip(f"Reset to: {sn}")
                rst.clicked.connect(lambda _, orig=sn: self._reset_name(orig))
                row.addWidget(rst)

                row.addStretch()
                w = QWidget()
                w.setLayout(row)
                vl.addWidget(w)
            layout.addWidget(g)

        self._font_group = FontSettingsGroup(self._cfg)
        layout.addWidget(self._font_group.build())

        self._legend_grp = LegendGroup(self._cfg)
        layout.addWidget(self._legend_grp.build())

        self._export_grp = ExportSettingsGroup(self._cfg)
        layout.addWidget(self._export_grp.build())

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    # ── Slots ───────────────────────────────

    def _on_plot_type_changed(self):
        is_scatter = self.plot_type.currentText() == 'Scatter Plot'
        self._scatter_frame.setVisible(is_scatter)
        self._hexbin_frame.setVisible(not is_scatter)

    def _pick_avg_color(self):
        from PySide6.QtWidgets import QColorDialog
        c = QColorDialog.getColor(self._avg_color, self, "Average Point Color")
        if c.isValid():
            self._avg_color = c
            self.avg_color_btn.setStyleSheet(
                f"background-color: {c.name()}; min-height: 25px; border: 1px solid black;")

    def _pick_sample_color(self, name, btn):
        """
        Args:
            name (Any): Name string.
            btn (Any): The btn.
        """
        from PySide6.QtWidgets import QColorDialog
        cur = QColor(self._color_btns[name][1])
        c = QColorDialog.getColor(cur, self, f"Color for {name}")
        if c.isValid():
            btn.setStyleSheet(f"background-color: {c.name()}; border: 1px solid black;")
            self._color_btns[name] = (btn, c.name())

    def _reset_name(self, original):
        """
        Args:
            original (Any): The original.
        """
        if original in self._name_edits:
            self._name_edits[original].setText(original)

    # ── Collect ─────────────────────────────

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        out = dict(self._cfg)
        ea = self.elem_a.currentText()
        out['element_a'] = '' if ea.startswith('--') else ea
        eb = self.elem_b.currentText()
        out['element_b'] = '' if eb.startswith('--') else eb
        ec = self.elem_c.currentText()
        out['element_c'] = '' if ec.startswith('--') else ec
        ce = self.color_elem.currentText()
        out['color_element'] = '' if ce.startswith('(') else ce

        out['data_type_display'] = self.data_type.currentText()
        out['label_mode']        = self.label_mode_combo.currentText()
        out['plot_type'] = self.plot_type.currentText()
        out['marker_size'] = self.marker_size.value()
        out['marker_alpha'] = self.marker_alpha.value() / 100.0
        out['hexbin_gridsize'] = self.hexbin_grid.value()
        out['hexbin_alpha'] = self.hexbin_alpha.value() / 100.0
        out['show_grid'] = self.show_grid.isChecked()
        out['colormap'] = self.colormap.currentText()
        out['show_colorbar'] = self.show_colorbar.isChecked()
        out['colorbar_label'] = self.cbar_label.text()

        out['show_average_point'] = self.show_avg.isChecked()
        out['average_only_with_all_elements'] = self.avg_only_all.isChecked()
        out['show_average_text'] = self.show_avg_text.isChecked()
        out['show_confidence_ellipse'] = self.show_ellipse.isChecked()
        out['average_point_size'] = self.avg_size.value()
        out['average_point_color'] = self._avg_color.name()

        out['min_total'] = self.min_total.value()
        out['max_particles'] = self.max_particles.value()

        if self._is_multi:
            out['display_mode'] = self.display_mode.currentText()
            out['sample_colors'] = {sn: c for sn, (_, c) in self._color_btns.items()}
            out['sample_name_mappings'] = {sn: ne.text() for sn, ne in self._name_edits.items()}

        out.update(self._font_group.collect())
        out.update(self._legend_grp.collect())
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
        """
        Args:
            color (Any): Colour value.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setFixedSize(36, 24)
        self._color = color
        self._update()

    def _update(self):
        self.setStyleSheet(
            f'background-color:{self._color};'
            f'border:1px solid #888;border-radius:3px;')

    def color(self):
        """
        Returns:
            object: Result of the operation.
        """
        return self._color

    def set_color(self, c):
        """
        Args:
            c (Any): The c.
        """
        self._color = c
        self._update()

    def mousePressEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        if event.button() == Qt.LeftButton:
            c = QColorDialog.getColor(QColor(self._color), self)
            if c.isValid():
                self.set_color(c.name())
        super().mousePressEvent(event)


class AnnotationDialog(QDialog):
    """Add or edit a single ternary-plot annotation (Text / Marker / Marker+Text)."""

    def __init__(self, ann: dict | None = None, parent=None):
        """
        Args:
            ann (dict | None): The ann.
            parent (Any): Parent widget or object.
        """
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
        """
        Args:
            t (Any): The t.
        """
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
        """
        Returns:
            dict: Result of the operation.
        """
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
    """
    Args:
        hbox (QHBoxLayout): The hbox.
    Returns:
        QWidget: Result of the operation.
    """
    w = QWidget(); w.setLayout(hbox); return w


class ManageAnnotationsDialog(QDialog):
    """View, edit, reorder and delete existing annotations."""

    _TYPE_ICONS = {'Text': '', 'Marker': '●', 'Marker + Text': '●'}

    def __init__(self, annotations: list, parent=None):
        """
        Args:
            annotations (list): The annotations.
            parent (Any): Parent widget or object.
        """
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
        """
        Returns:
            object: Result of the operation.
        """
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
        """
        Returns:
            list: Result of the operation.
        """
        return [dict(a) for a in self._anns]


class TriangleDisplayDialog(QDialog):
    """Full-figure dialog with right-click context menu for all settings."""

    def __init__(self, triangle_node, parent_window=None):
        """
        Args:
            triangle_node (Any): The triangle node.
            parent_window (Any): The parent window.
        """
        super().__init__(parent_window)
        self.node = triangle_node
        self.parent_window = parent_window
        self.setWindowTitle("Ternary Composition Analysis")
        self.setMinimumSize(1000, 750)

        self._setup_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    # ── Helpers ─────────────────────────────

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

    def _available_elements(self) -> list:
        """
        Returns:
            list: Result of the operation.
        """
        if not self.node.input_data:
            return []
        elems = set()
        for p in self.node.input_data.get('particle_data', []):
            elems.update(p.get('elements', {}).keys())
        return sorted(elems)

    # ── UI ──────────────────────────────────

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        self.figure = Figure(figsize=(14, 10), dpi=140, tight_layout=True)
        self.canvas = MplDraggableCanvas(self.figure)
        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._show_context_menu)
        main_layout.addWidget(self.canvas, stretch=1)

        self.canvas.mpl_connect('button_release_event', self._save_ann_positions)

        # ── Bottom toolbar ────────────────────────────────────────────
        tb = QHBoxLayout()
        tb.setContentsMargins(0, 2, 0, 0)
        btn_s = QPushButton("Settings")
        btn_s.clicked.connect(self._open_settings)
        btn_r = QPushButton("Reset Layout")
        btn_r.setToolTip("Reset all subplot positions\n(or middle-click on the figure)")
        btn_r.clicked.connect(self._reset_layout)
        btn_e = QPushButton("Export…")
        btn_e.clicked.connect(self._export_figure)
        tb.addWidget(btn_s); tb.addWidget(btn_r)
        tb.addStretch(); tb.addWidget(btn_e)
        main_layout.addLayout(tb)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            "color: #6B7280; font-size: 11px; padding: 2px 8px; "
            "background-color: #F8FAFC; border-top: 1px solid #E2E8F0;")
        main_layout.addWidget(self.stats_label)

    # ── Context menu ────────────────────────

    def _show_context_menu(self, pos):
        """
        Args:
            pos (Any): Position point.
        """
        cfg = self.node.config
        menu = QMenu(self)

        toggle_menu = menu.addMenu("Quick Toggles")
        self._add_toggle(toggle_menu, "Show Grid", 'show_grid')
        self._add_toggle(toggle_menu, "Show Color Bar", 'show_colorbar')
        self._add_toggle(toggle_menu, "Show Average Point", 'show_average_point')
        self._add_toggle(toggle_menu, "Show Stats Text", 'show_average_text')
        self._add_toggle(toggle_menu, "Show 2σ Ellipse", 'show_confidence_ellipse')
        self._add_toggle(toggle_menu, "Average: All 3 Required", 'average_only_with_all_elements')

        elems = self._available_elements()
        if elems:
            ea_menu = menu.addMenu("Element A (Left)")
            for e in elems:
                a = ea_menu.addAction(e)
                a.setCheckable(True)
                a.setChecked(e == cfg.get('element_a'))
                a.triggered.connect(lambda _, el=e: self._set('element_a', el))

            eb_menu = menu.addMenu("Element B (Right)")
            for e in elems:
                a = eb_menu.addAction(e)
                a.setCheckable(True)
                a.setChecked(e == cfg.get('element_b'))
                a.triggered.connect(lambda _, el=e: self._set('element_b', el))

            ec_menu = menu.addMenu("Element C (Top)")
            for e in elems:
                a = ec_menu.addAction(e)
                a.setCheckable(True)
                a.setChecked(e == cfg.get('element_c'))
                a.triggered.connect(lambda _, el=e: self._set('element_c', el))

            ce_menu = menu.addMenu("Color By Element")
            a_none = ce_menu.addAction("(None — use index)")
            a_none.setCheckable(True)
            a_none.setChecked(not cfg.get('color_element'))
            a_none.triggered.connect(lambda _: self._set('color_element', ''))
            for e in elems:
                a = ce_menu.addAction(e)
                a.setCheckable(True)
                a.setChecked(e == cfg.get('color_element'))
                a.triggered.connect(lambda _, el=e: self._set('color_element', el))

        dt_menu = menu.addMenu("Data Type")
        cur_dt = cfg.get('data_type_display', 'Counts (%)')
        for dt in TERNARY_DATA_TYPE_OPTIONS:
            a = dt_menu.addAction(dt)
            a.setCheckable(True)
            a.setChecked(dt == cur_dt)
            a.triggered.connect(lambda _, d=dt: self._set('data_type_display', d))

        pt_menu = menu.addMenu("Plot Type")
        cur_pt = cfg.get('plot_type', 'Scatter Plot')
        for pt in PLOT_TYPES:
            a = pt_menu.addAction(pt)
            a.setCheckable(True)
            a.setChecked(pt == cur_pt)
            a.triggered.connect(lambda _, p=pt: self._set('plot_type', p))

        cm_menu = menu.addMenu("Color Map")
        cur_cm = cfg.get('colormap', 'YlGn')
        for cm in COLORMAPS:
            a = cm_menu.addAction(cm)
            a.setCheckable(True)
            a.setChecked(cm == cur_cm)
            a.triggered.connect(lambda _, c=cm: self._set('colormap', c))

        if self._is_multi():
            dm_menu = menu.addMenu("Display Mode")
            cur = cfg.get('display_mode', DISPLAY_MODES[0])
            for m in DISPLAY_MODES:
                a = dm_menu.addAction(m)
                a.setCheckable(True)
                a.setChecked(m == cur)
                a.triggered.connect(lambda _, mode=m: self._set('display_mode', mode))

        menu.addSeparator()
        menu.addAction("Reset Layout").triggered.connect(self._reset_layout)

        lm = menu.addMenu("Label Mode")
        for mode in LABEL_MODES:
            a = lm.addAction(mode); a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set('label_mode', v))

        menu.addSeparator()
        menu.addAction("Add Annotation…").triggered.connect(self._add_annotation)
        menu.addAction("Manage Annotations…").triggered.connect(self._manage_annotations)

        menu.addSeparator()
        settings_action = menu.addAction("⚙  Configure…")
        settings_action.triggered.connect(self._open_settings)

        dl_action = menu.addAction("Download Figure…")
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

    def _set(self, key, value):
        """
        Args:
            key (Any): Dictionary or storage key.
            value (Any): Value to set or process.
        """
        self.node.config[key] = value
        self._refresh()

    def _add_annotation(self):
        dlg = AnnotationDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            anns = list(self.node.config.get('annotations', []))
            anns.append(dlg.collect())
            self.node.config['annotations'] = anns
            self._refresh()

    def _manage_annotations(self):
        anns = list(self.node.config.get('annotations', []))
        dlg = ManageAnnotationsDialog(anns, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config['annotations'] = dlg.collect()
            self._refresh()

    def _open_settings(self):
        dlg = TernarySettingsDialog(
            self.node.config, self._available_elements(),
            self._is_multi(), self._sample_names(), self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _reset_layout(self):
        self.canvas.reset_layout()

    def _export_figure(self):
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
                elif mode == 'Side by Side Subplots':
                    self._draw_side_by_side(plot_data, cfg)
                elif mode == 'Combined Plot':
                    self._draw_combined(plot_data, cfg)
                else:
                    self._draw_overlaid(plot_data, cfg)
                for ax in self.figure.get_axes():
                    self._draw_annotations(ax, cfg)
            else:
                ax = self.figure.add_subplot(111, projection='ternary')
                self._draw_sample(ax, plot_data, cfg, "Ternary Plot")
                apply_font_to_ternary(ax, cfg)
                self._draw_annotations(ax, cfg)

            self._update_stats(plot_data)

            self.figure.tight_layout()
            self.canvas.draw()
            self.canvas.snapshot_positions()

        except Exception as e:
            print(f"Error updating ternary display: {e}")
            import traceback
            traceback.print_exc()

    # ── Annotation rendering ─────────────────

    def _draw_annotations(self, ax, cfg):
        """Render all custom annotations onto a ternary axes.

        Text annotations are placed in axes-fraction space (draggable).
        Marker annotations are placed at ternary data coordinates.
        Position changes from dragging are saved back to config on mouse release.
        Args:
            ax (Any): The ax.
            cfg (Any): The cfg.
        """
        anns = cfg.get('annotations', [])
        if not anns:
            return

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
                try:
                    ax.scatter([t], [l], [r],
                               marker=ann.get('marker', 'o'),
                               s=ann.get('marker_size', 80),
                               c=[ann.get('marker_color', '#3B82F6')],
                               alpha=ann.get('marker_alpha', 0.85),
                               edgecolors=ann.get('marker_edge_color', '#1D4ED8'),
                               linewidths=ann.get('marker_edge_width', 1.5),
                               zorder=18)
                except Exception:
                    pass

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
                    pass

    def _save_ann_positions(self, event=None):
        """Called on mouse button release — persist dragged text positions back to config.
        Args:
            event (Any): Qt event object.
        """
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
                        pass
            if changed:
                self.node.config['annotations'] = anns
        except Exception:
            pass

    def _update_stats(self, plot_data):
        """Update the bottom statistics label.
        Args:
            plot_data (Any): The plot data.
        """
        cfg = self.node.config

        if self._is_multi():
            total = sum(len(sd) for sd in plot_data.values())
            n_samples = len(plot_data)
            parts = [f"{n_samples} samples", f"{total:,} particles plotted"]

            if cfg.get('average_only_with_all_elements', True):
                n_all = 0
                for sd in plot_data.values():
                    n_all += sum(1 for p in sd if p['a'] > 0 and p['b'] > 0 and p['c'] > 0)
                if n_all < total:
                    parts.append(f"{n_all:,} with all 3 elements")

            self.stats_label.setText("  ·  ".join(parts))
        else:
            total = len(plot_data)
            parts = [f"{total:,} particles plotted"]

            if cfg.get('average_only_with_all_elements', True):
                n_all = sum(1 for p in plot_data if p['a'] > 0 and p['b'] > 0 and p['c'] > 0)
                if n_all < total:
                    parts.append(f"{n_all:,} with all 3 elements")

            self.stats_label.setText("  ·  ".join(parts))


    def _draw_sample(self, ax, sample_data, cfg, title, sample_color=None):
        """
        Draw a ternary scatter or hexbin for one sample.

        Args:
            ax:           mpltern axes
            sample_data:  list of dicts with keys 'a', 'b', 'c' (and optionally 'color_val')
            cfg:          config dict
            title:        plot title string
            sample_color: if provided, all markers use this color (for overlaid mode)
        """
        if not sample_data:
            return

        ea = cfg.get('element_a', 'A')
        eb = cfg.get('element_b', 'B')
        ec = cfg.get('element_c', 'C')
        setup_ternary_axes(ax, [ea, eb, ec], cfg)

        a_vals = np.array([p['a'] for p in sample_data])
        b_vals = np.array([p['b'] for p in sample_data])
        c_vals = np.array([p['c'] for p in sample_data])

        plot_type = cfg.get('plot_type', 'Scatter Plot')
        cmap = cfg.get('colormap', 'YlGn')
        show_cbar = cfg.get('show_colorbar', True)

        if plot_type == 'Scatter Plot':
            size = cfg.get('marker_size', 20)
            alpha = cfg.get('marker_alpha', 0.7)
            color_elem = cfg.get('color_element', '')

            if color_elem and not sample_color:
                color_vals = np.array([p.get('color_val', 0) for p in sample_data])
                scatter = ax.scatter(
                    b_vals, c_vals, a_vals,
                    s=size, alpha=alpha, c=color_vals, cmap=cmap,
                    edgecolors='white', linewidth=0.5)
                if show_cbar:
                    cbar = self.figure.colorbar(scatter, ax=ax, shrink=0.8, aspect=20)
                    apply_font_to_colorbar_standalone(
                        cbar, cfg, cfg.get('colorbar_label', color_elem))
            elif sample_color:
                scatter = ax.scatter(
                    b_vals, c_vals, a_vals,
                    s=size, alpha=alpha, color=sample_color,
                    edgecolors='white', linewidth=0.5, label=title)
            else:
                scatter = ax.scatter(
                    b_vals, c_vals, a_vals,
                    s=size, alpha=alpha, c=range(len(b_vals)), cmap=cmap,
                    edgecolors='white', linewidth=0.5)
                if show_cbar:
                    cbar = self.figure.colorbar(scatter, ax=ax, shrink=0.8, aspect=20)
                    apply_font_to_colorbar_standalone(
                        cbar, cfg, cfg.get('colorbar_label', 'Point Index'))
        else:
            gridsize = cfg.get('hexbin_gridsize', 30)
            alpha = cfg.get('hexbin_alpha', 0.8)
            hexbin = ax.hexbin(
                b_vals, c_vals, a_vals,
                gridsize=gridsize, cmap=cmap, alpha=alpha, mincnt=1)
            if show_cbar:
                cbar = self.figure.colorbar(hexbin, ax=ax, shrink=0.8, aspect=20)
                apply_font_to_colorbar_standalone(
                    cbar, cfg, cfg.get('colorbar_label', 'Density'))

        self._draw_average(ax, sample_data, cfg, title)

    def _draw_average(self, ax, sample_data, cfg, sample_name):
        """Draw average point with optional stats text and confidence ellipse.
        Args:
            ax (Any): The ax.
            sample_data (Any): The sample data.
            cfg (Any): The cfg.
            sample_name (Any): The sample name.
        """
        if not cfg.get('show_average_point', True) or not sample_data:
            return

        if cfg.get('average_only_with_all_elements', True):
            data = [p for p in sample_data if p['a'] > 0 and p['b'] > 0 and p['c'] > 0]
        else:
            data = sample_data

        if not data:
            return

        a_vals = np.array([p['a'] for p in data])
        b_vals = np.array([p['b'] for p in data])
        c_vals = np.array([p['c'] for p in data])

        ma, mb, mc = a_vals.mean(), b_vals.mean(), c_vals.mean()
        sa, sb, sc = a_vals.std(), b_vals.std(), c_vals.std()

        avg_color = cfg.get('average_point_color', '#FF0000')
        avg_size = cfg.get('average_point_size', 100)

        n_filt = len(data)
        n_total = len(sample_data)
        suffix = f" ({n_filt}/{n_total})" if n_filt < n_total else ""

        ax.scatter(
            [mb], [mc], [ma],
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

            tx = mb + 0.15
            ty = mc + 0.01
            tz = max(1.0 - tx - ty, 0.01)
            ax.text(tx, ty, tz, text,
                    fontproperties=fp, color='black',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                              alpha=0.85, edgecolor='gray'),
                    ha='left', va='bottom', zorder=11)

        if cfg.get('show_confidence_ellipse', False) and len(data) >= 3:
            params = confidence_ellipse_params(b_vals, c_vals, n_std=2.0)
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
        """
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        samples = list(plot_data.keys())
        n = len(samples)
        cols = min(2, n)
        rows = math.ceil(n / cols)

        for idx, sn in enumerate(samples):
            ax = self.figure.add_subplot(rows, cols, idx + 1, projection='ternary')
            sd = plot_data[sn]
            if sd:
                dname = get_display_name(sn, cfg)
                self._draw_sample(ax, sd, cfg, dname)
                fc = get_font_config(cfg)
                ax.set_title(dname, fontsize=fc['size'] - 2, color=fc['color'])
                apply_font_to_ternary(ax, cfg)

    def _draw_side_by_side(self, plot_data, cfg):
        """
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        samples = list(plot_data.keys())
        n = len(samples)

        for idx, sn in enumerate(samples):
            ax = self.figure.add_subplot(1, n, idx + 1, projection='ternary')
            sd = plot_data[sn]
            if sd:
                dname = get_display_name(sn, cfg)
                self._draw_sample(ax, sd, cfg, dname)
                fc = get_font_config(cfg)
                ax.set_title(dname, fontsize=fc['size'] - 2, color=fc['color'])
                apply_font_to_ternary(ax, cfg)

    def _draw_combined(self, plot_data, cfg):
        """
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        ax = self.figure.add_subplot(111, projection='ternary')
        combined = []
        for sd in plot_data.values():
            combined.extend(sd)
        if combined:
            self._draw_sample(ax, combined, cfg,
                              f"Combined ({len(plot_data)} samples)")
            apply_font_to_ternary(ax, cfg)

    def _draw_overlaid(self, plot_data, cfg):
        """
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        """
        ax = self.figure.add_subplot(111, projection='ternary')

        ea = cfg.get('element_a', 'A')
        eb = cfg.get('element_b', 'B')
        ec = cfg.get('element_c', 'C')
        setup_ternary_axes(ax, [ea, eb, ec], cfg)

        alpha = cfg.get('marker_alpha', 0.7)
        size = cfg.get('marker_size', 20)

        for idx, (sn, sd) in enumerate(plot_data.items()):
            if not sd:
                continue
            color = get_sample_color(sn, idx, cfg)
            dname = get_display_name(sn, cfg)

            a_vals = np.array([p['a'] for p in sd])
            b_vals = np.array([p['b'] for p in sd])
            c_vals = np.array([p['c'] for p in sd])

            ax.scatter(
                b_vals, c_vals, a_vals,
                s=size, alpha=alpha, color=color, label=dname,
                edgecolors='white', linewidth=0.5)

            self._draw_average(ax, sd, cfg, dname)

        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
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
        'color_element': '',
        'data_type_display': 'Counts (%)',
        'plot_type': 'Scatter Plot',
        'marker_size': 20,
        'marker_alpha': 0.7,
        'hexbin_gridsize': 30,
        'hexbin_alpha': 0.8,
        'show_grid': True,
        'colormap': 'YlGn',
        'show_colorbar': True,
        'colorbar_label': 'Density',
        'min_total': 0.0,
        'max_particles': 100_000_000,
        'show_average_point': True,
        'average_point_color': '#FF0000',
        'average_point_size': 100,
        'show_average_text': True,
        'average_only_with_all_elements': True,
        'show_confidence_ellipse': False,
        'display_mode': 'Individual Subplots',
        'sample_colors': {},
        'sample_name_mappings': {},
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
        """
        Args:
            parent_window (Any): The parent window.
        """
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
        dlg = TriangleDisplayDialog(self, parent_window)
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
            each with keys 'a', 'b', 'c', 'total', and optionally 'color_val'.
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
        color_elem = self.config.get('color_element', '')
        itype = self.input_data.get('type')

        if itype == 'sample_data':
            return self._extract_single(dk, ea, eb, ec, color_elem)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(dk, ea, eb, ec, color_elem)
        return None

    def _extract_particles(self, particles, dk, ea, eb, ec, color_elem):
        """
        Extract ternary points from a list of particle dicts.

        For each particle, reads the three element values from the chosen data key,
        normalises them to fractions summing to 1.0, and optionally reads a fourth
        element value for color mapping.

        Args:
            particles:  list of particle dicts
            dk:         data key ('elements', 'element_mass_fg', etc.)
            ea, eb, ec: element label strings
            color_elem: optional fourth element label for coloring (or '')

        Returns:
            list of point dicts or None
        """
        min_total = self.config.get('min_total', 0.0)
        max_pts = self.config.get('max_particles', 100_000_000)
        result = []

        for p in particles:
            if len(result) >= max_pts:
                break
            d = p.get(dk, {})
            va = d.get(ea, 0)
            vb = d.get(eb, 0)
            vc = d.get(ec, 0)

            if dk == 'elements':
                if va <= 0 or vb <= 0 or vc <= 0:
                    continue
            else:
                try:
                    if (np.isnan(va) or np.isnan(vb) or np.isnan(vc)
                            or va < 0 or vb < 0 or vc < 0):
                        continue
                except TypeError:
                    continue

            total = va + vb + vc
            if total < min_total or total <= 0:
                continue

            point = {
                'a': va / total,
                'b': vb / total,
                'c': vc / total,
                'total': total,
            }

            if color_elem:
                point['color_val'] = d.get(color_elem, 0)

            result.append(point)

        return result or None

    def _extract_single(self, dk, ea, eb, ec, color_elem):
        """
        Args:
            dk (Any): The dk.
            ea (Any): The ea.
            eb (Any): The eb.
            ec (Any): The ec.
            color_elem (Any): The color elem.
        Returns:
            object: Result of the operation.
        """
        particles = self.input_data.get('particle_data')
        if not particles:
            return None
        return self._extract_particles(particles, dk, ea, eb, ec, color_elem)

    def _extract_multi(self, dk, ea, eb, ec, color_elem):
        """
        Args:
            dk (Any): The dk.
            ea (Any): The ea.
            eb (Any): The eb.
            ec (Any): The ec.
            color_elem (Any): The color elem.
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
            pts = self._extract_particles(plist, dk, ea, eb, ec, color_elem)
            if pts:
                result[sn] = pts
        return result or None