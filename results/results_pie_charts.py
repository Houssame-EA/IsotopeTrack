from __future__ import annotations

import math
import re
import traceback

import numpy as np
import pandas as pd
import matplotlib.patches as mpatches
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMenu, QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QVBoxLayout, QWidget,
)

from results.shared_plot_utils import (
    DEFAULT_SAMPLE_COLORS, FontSettingsGroup, get_display_name,
)
from results.utils_sort import sort_elements_by_mass

# ── Constants ──────────────────────────────────────────────────────────

PIE_CHART_TYPES = ['Element Distribution', 'Particle Count Distribution']
PIE_DATA_TYPES = [
    'Counts', 'Element Mass (fg)', 'Particle Mass (fg)',
    'Element Moles (fmol)', 'Particle Moles (fmol)',
]
PIE_DISPLAY_MODES = [
    'Individual Subplots', 'Side by Side Subplots',
    'Combined Distribution', 'Overlaid Comparison',
]
COMP_ANALYSIS_TYPES = [
    'Single vs Multiple Elements',
    'Specific Element Combinations',
    'Element Distribution by Data Type',
]
DEFAULT_PIE_COLORS = [
    '#FF6347', '#FFD700', '#FFA500', '#20B2AA', '#00BFFF',
    '#F0E68C', '#E0FFFF', '#AFEEEE', '#DDA0DD', '#FFE4E1',
    '#FAEBD7', '#D3D3D3', '#90EE90', '#FFB6C1', '#FFA07A',
]
DEFAULT_COMBO_COLORS = [
    '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
    '#FF6B35', '#FFD700', '#20B2AA', '#FF69B4', '#32CD32',
    '#FF4500', '#9370DB', '#00CED1', '#FF1493', '#00FF7F',
]
LABEL_MODES = ['Symbol', 'Mass + Symbol']
LEGEND_POSITIONS = [
    'best', 'upper right', 'upper left', 'lower left', 'lower right',
    'center left', 'center right', 'lower center', 'upper center', 'center',
]
_LINE_STYLES = ['-', '--', '-.', ':']
_LINE_NAMES  = ['Solid', 'Dashed', 'Dash-dot', 'Dotted']
EXPORT_FORMATS = ['svg', 'pdf', 'png', 'eps']

# ── Small helper ───────────────────────────────────────────────────────

def _is_multi(input_data):
    """
    Args:
        input_data (Any): The input data.
    Returns:
        object: Result of the operation.
    """
    return bool(input_data and input_data.get('type') == 'multiple_sample_data')


def _format_element_label(key: str, mode: str) -> str:
    """Format an element key for display according to label mode.

    'Symbol'        → bare symbol, stripping any leading mass number
                      e.g. '107Ag' → 'Ag',  '107Ag, 197Au' → 'Ag, Au'
    'Mass + Symbol' → keep as-is (full isotope notation)
                      e.g. '107Ag',          '107Ag, 197Au'
    Args:
        key (str): Dictionary or storage key.
        mode (str): Operating mode string.
    Returns:
        str: Result of the operation.
    """
    if mode == 'Mass + Symbol':
        return key
    tokens = [re.sub(r'^\d+', '', tok.strip()) for tok in key.split(',')]
    return ', '.join(tokens)


class _ColorBtn(QPushButton):
    """Single-click colour-picker button with a colour swatch."""

    def __init__(self, color: str = '#FFFFFF', parent=None):
        """
        Args:
            color (str): Colour value.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setFixedSize(30, 20)
        self._color = color
        self._apply()

    def _apply(self):
        self.setStyleSheet(
            f'background-color:{self._color};'
            f'border:1px solid #666;border-radius:2px;'
        )

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
        self._color = c
        self._apply()

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
    """Donut, start angle, shadow, edge style, label distance."""

    def __init__(self, cfg: dict):
        """
        Args:
            cfg (dict): The cfg.
        """
        self._cfg = cfg
        self._edge_btn = _ColorBtn(cfg.get('edge_color', '#FFFFFF'))

    def build(self) -> QGroupBox:
        """
        Returns:
            QGroupBox: Result of the operation.
        """
        cfg = self._cfg
        g = QGroupBox("Pie / Donut Style")
        f = QFormLayout(g)

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

        f.addRow("Edge Colour:", self._edge_btn)

        self._edge_w = QDoubleSpinBox()
        self._edge_w.setRange(0.0, 5.0); self._edge_w.setSingleStep(0.5)
        self._edge_w.setValue(cfg.get('edge_width', 1.5))
        f.addRow("Edge Width:", self._edge_w)

        self._ldist = QDoubleSpinBox()
        self._ldist.setRange(1.05, 2.50); self._ldist.setSingleStep(0.05)
        self._ldist.setValue(cfg.get('label_distance', 1.25))
        f.addRow("Label Distance:", self._ldist)

        return g

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        return {
            'donut':             self._donut.isChecked(),
            'donut_hole_size':   self._hole.value(),
            'donut_center_text': self._center_text.text().strip(),
            'start_angle':       self._start.value(),
            'shadow':            self._shadow.isChecked(),
            'edge_color':        self._edge_btn.color(),
            'edge_width':        self._edge_w.value(),
            'label_distance':    self._ldist.value(),
        }


class LabelLineGroup:
    """Connection lines + label background box."""

    def __init__(self, cfg: dict):
        """
        Args:
            cfg (dict): The cfg.
        """
        self._cfg = cfg
        self._line_color = _ColorBtn(cfg.get('connection_line_color', '#888888'))

    def build(self) -> QGroupBox:
        """
        Returns:
            QGroupBox: Result of the operation.
        """
        cfg = self._cfg
        g = QGroupBox("Labels & Connection Lines")
        f = QFormLayout(g)

        self._show_lines = QCheckBox("Show Connection Lines")
        self._show_lines.setChecked(cfg.get('show_connection_lines', True))
        f.addRow("", self._show_lines)

        self._line_style = QComboBox()
        self._line_style.addItems(_LINE_NAMES)
        cur = cfg.get('connection_line_style', '-')
        self._line_style.setCurrentIndex(
            _LINE_STYLES.index(cur) if cur in _LINE_STYLES else 0)
        f.addRow("Line Style:", self._line_style)

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
            'show_connection_lines': self._show_lines.isChecked(),
            'connection_line_style': _LINE_STYLES[self._line_style.currentIndex()],
            'connection_line_color': self._line_color.color(),
            'label_bbox':            self._bbox.isChecked(),
        }


class LegendGroup:
    """Legend visibility and placement."""

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
        g = QGroupBox("Legend")
        f = QFormLayout(g)

        self._show = QCheckBox("Show Legend")
        self._show.setChecked(cfg.get('legend_show', False))
        f.addRow("", self._show)

        self._pos = QComboBox()
        self._pos.addItems(LEGEND_POSITIONS)
        cur = cfg.get('legend_position', 'best')
        if cur in LEGEND_POSITIONS:
            self._pos.setCurrentText(cur)
        f.addRow("Position:", self._pos)

        self._outside = QCheckBox("Place Outside Axes")
        self._outside.setChecked(cfg.get('legend_outside', False))
        f.addRow("", self._outside)

        return g

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        return {
            'legend_show':     self._show.isChecked(),
            'legend_position': self._pos.currentText(),
            'legend_outside':  self._outside.isChecked(),
        }


class ExportGroup:
    """Export format, DPI, background colour."""

    def __init__(self, cfg: dict):
        """
        Args:
            cfg (dict): The cfg.
        """
        self._cfg = cfg
        self._bg_btn = _ColorBtn(cfg.get('bg_color', '#FFFFFF'))

    def build(self) -> QGroupBox:
        """
        Returns:
            QGroupBox: Result of the operation.
        """
        cfg = self._cfg
        g = QGroupBox("Export Settings")
        f = QFormLayout(g)

        self._fmt = QComboBox()
        self._fmt.addItems([s.upper() for s in EXPORT_FORMATS])
        cur = cfg.get('export_format', 'svg').upper()
        self._fmt.setCurrentText(cur if cur in [s.upper() for s in EXPORT_FORMATS] else 'SVG')
        f.addRow("Format:", self._fmt)

        self._dpi = QSpinBox()
        self._dpi.setRange(72, 1200); self._dpi.setSuffix(" dpi")
        self._dpi.setValue(cfg.get('export_dpi', 300))
        f.addRow("Resolution:", self._dpi)

        f.addRow("Background:", self._bg_btn)

        return g

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        return {
            'export_format': self._fmt.currentText().lower(),
            'export_dpi':    self._dpi.value(),
            'bg_color':      self._bg_btn.color(),
        }


class MplPieCanvas(QWidget):
    """
    Matplotlib FigureCanvasQTAgg wrapped in a QWidget.

    • Renders one or more pie / donut subplots in a grid.
    • Every label annotation is individually draggable.
    • Drag positions are saved back to cfg['label_positions'][key][label]
      on mouse-button release – they persist across redraws.
    • Right-click is forwarded to the parent dialog via a callback so the
      existing context-menu code works unchanged.
    """

    def __init__(self, cfg: dict, parent=None):
        """
        Args:
            cfg (dict): The cfg.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self._cfg  = cfg
        self._anns: dict[str, dict] = {}

        self.figure = Figure(tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.canvas)

        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._fwd_ctx)
        self._ctx_cb = None

        self.canvas.mpl_connect('button_release_event', self._persist_positions)

        self._drag_ax        = None
        self._drag_start_px  = None
        self._drag_ax_pos0   = None
        self.canvas.mpl_connect('button_press_event',   self._pie_drag_press)
        self.canvas.mpl_connect('motion_notify_event',  self._pie_drag_motion)
        self.canvas.mpl_connect('button_release_event', self._pie_drag_release)

    # ── Public API ─────────────────────────────────────────────────────

    def set_context_menu_callback(self, fn):
        """
        Args:
            fn (Any): The fn.
        """
        self._ctx_cb = fn

    def render(self, subplots: list[dict]):
        """
        subplots – list of dicts:
            labels : list[str]
            sizes  : list[float]   (percentages, ≈ sum 100)
            texts  : list[str]     (annotation text per wedge)
            colors : list[str]     (hex colours)
            title  : str
            key    : str           (unique key for position persistence)
        Args:
            subplots (list[dict]): The subplots.
        """
        self.figure.clear()
        self._anns = {}

        cfg = self._cfg
        bg  = cfg.get('bg_color', '#FFFFFF')
        self.figure.patch.set_facecolor(bg)

        n = len(subplots)
        if n == 0:
            ax = self.figure.add_subplot(111)
            ax.text(0.5, 0.5, 'No data available',
                    ha='center', va='center', transform=ax.transAxes,
                    color='#888888', fontsize=11)
            ax.axis('off')
            self.canvas.draw()
            return

        cols = min(3, n)
        rows = math.ceil(n / cols)

        for i, sp in enumerate(subplots):
            ax = self.figure.add_subplot(rows, cols, i + 1)
            ax.set_facecolor(bg)
            if sp.get('labels'):
                self._draw_one(ax, sp, cfg)
            else:
                ax.text(0.5, 0.5, f"{sp.get('title', '')}\n(no data)",
                        ha='center', va='center', transform=ax.transAxes,
                        color='#888888', fontsize=9)
                ax.axis('off')

        self.figure.tight_layout(pad=1.5)
        self.canvas.draw()

    def reset_label_positions(self, key: str | None = None):
        """Clear saved drag positions – all subplots or one.
        Args:
            key (str | None): Dictionary or storage key.
        """
        lp = self._cfg.get('label_positions', {})
        if key:
            lp.pop(key, None)
        else:
            lp.clear()
        self._cfg['label_positions'] = lp

    def export_figure(self, parent=None):
        """
        Args:
            parent (Any): Parent widget or object.
        """
        fmt  = self._cfg.get('export_format', 'svg')
        dpi  = self._cfg.get('export_dpi', 300)
        filt = ('SVG Vector (*.svg);;PDF Document (*.pdf);;'
                'PNG Image (*.png);;EPS Vector (*.eps)')
        path, _ = QFileDialog.getSaveFileName(
            parent, 'Export Figure', f'pie_chart.{fmt}', filt)
        if path:
            self.figure.savefig(
                path, dpi=dpi, bbox_inches='tight',
                facecolor=self.figure.get_facecolor())

    # ── Internal ───────────────────────────────────────────────────────

    def _fwd_ctx(self, pos):
        """
        Args:
            pos (Any): Position point.
        """
        if self._ctx_cb:
            self._ctx_cb(self.canvas.mapToGlobal(pos))

    def _persist_positions(self, _event):
        """
        Args:
            _event (Any): The  event.
        """
        for sp_key, anns in self._anns.items():
            bucket = (self._cfg
                      .setdefault('label_positions', {})
                      .setdefault(sp_key, {}))
            for label, ann in anns.items():
                p = ann.get_position()
                bucket[label] = (float(p[0]), float(p[1]))

    # ── Pie-axes drag ──────────────────────────────────────────────────

    def _pie_drag_press(self, event):
        """Start dragging an axes when the user clicks on its background.
        Args:
            event (Any): Qt event object.
        """
        if event.button != 1 or event.inaxes is None:
            return
        for anns in self._anns.values():
            for ann in anns.values():
                try:
                    hit, _ = ann.contains(event)
                    if hit:
                        return
                except Exception:
                    pass
        self._drag_ax       = event.inaxes
        self._drag_start_px = (event.x, event.y)
        self._drag_ax_pos0  = event.inaxes.get_position()

    def _pie_drag_motion(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        if self._drag_ax is None or event.x is None:
            return
        w_px, h_px = (self.figure.get_size_inches() * self.figure.dpi)
        dx = (event.x - self._drag_start_px[0]) / w_px
        dy = (event.y - self._drag_start_px[1]) / h_px
        p  = self._drag_ax_pos0
        self._drag_ax.set_position([p.x0 + dx, p.y0 + dy, p.width, p.height])
        self.canvas.draw_idle()

    def _pie_drag_release(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        self._drag_ax       = None
        self._drag_start_px = None
        self._drag_ax_pos0  = None

    def _draw_one(self, ax, sp: dict, cfg: dict):
        """
        Args:
            ax (Any): The ax.
            sp (dict): The sp.
            cfg (dict): The cfg.
        """
        labels   = sp['labels']
        sizes    = sp['sizes']
        texts    = sp['texts']
        colors   = sp['colors']
        title    = sp['title']
        sp_key   = sp['key']

        # ── Font ──────────────────────────────────────────────────────
        ff  = cfg.get('font_family', 'DejaVu Sans')
        fs  = int(cfg.get('font_size', 10))
        fc  = cfg.get('font_color', cfg.get('label_color', '#000000'))

        # ── Pie geometry ──────────────────────────────────────────────
        donut     = cfg.get('donut', False)
        hole      = cfg.get('donut_hole_size', 0.4)
        start_ang = cfg.get('start_angle', 90)
        shadow    = cfg.get('shadow', False)
        edge_c    = cfg.get('edge_color', '#FFFFFF')
        edge_w    = cfg.get('edge_width', 1.5)
        explode_d = cfg.get('explode', {})

        wp = {'linewidth': edge_w, 'edgecolor': edge_c}
        if donut:
            wp['width'] = max(0.05, 1.0 - hole)

        explode = tuple(explode_d.get(lbl, 0.0) for lbl in labels)

        result  = ax.pie(
            sizes,
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

        ax.set_title(title, fontsize=fs + 2, color=fc, fontfamily=ff, pad=8)

        # ── Draggable annotations ─────────────────────────────────────
        show_lines = cfg.get('show_connection_lines', True)
        line_color = cfg.get('connection_line_color', '#888888')
        line_style = cfg.get('connection_line_style', '-')
        label_dist = cfg.get('label_distance', 1.25)
        use_bbox   = cfg.get('label_bbox', True)
        saved      = cfg.get('label_positions', {}).get(sp_key, {})

        anns: dict = {}
        for wedge, label, text in zip(wedges, labels, texts):
            theta = np.radians((wedge.theta1 + wedge.theta2) / 2)
            exp   = explode_d.get(label, 0.0)

            tip_x = (1.0 + exp) * np.cos(theta)
            tip_y = (1.0 + exp) * np.sin(theta)

            if label in saved:
                lx, ly = saved[label]
            else:
                lx = label_dist * (1.0 + exp) * np.cos(theta)
                ly = label_dist * (1.0 + exp) * np.sin(theta)

            ann = ax.annotate(
                text,
                xy=(tip_x, tip_y),
                xytext=(lx, ly),
                ha='center', va='center',
                fontsize=fs, color=fc, fontfamily=ff,
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
            anns[label] = ann

        self._anns[sp_key] = anns

        # ── Legend ────────────────────────────────────────────────────
        if cfg.get('legend_show', False):
            handles = [mpatches.Patch(facecolor=c, label=l)
                       for c, l in zip(colors, labels)]
            kw = dict(handles=handles, fontsize=max(6, fs - 2), framealpha=0.8)
            if cfg.get('legend_outside', False):
                ax.legend(loc='upper left', bbox_to_anchor=(1.0, 1.0), **kw)
            else:
                ax.legend(loc=cfg.get('legend_position', 'best'), **kw)

        # ── Donut centre label ────────────────────────────────────────
        centre = cfg.get('donut_center_text', '')
        if donut and centre:
            ax.text(0, 0, centre, ha='center', va='center',
                    fontsize=fs, color=fc, fontfamily=ff, zorder=11)

        ax.set_aspect('equal')
        ax.axis('off')


class PieChartSettingsDialog(QDialog):
    def __init__(self, cfg, input_data, available_elements, parent=None):
        """
        Args:
            cfg (Any): The cfg.
            input_data (Any): The input data.
            available_elements (Any): The available elements.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("Pie Chart Settings")
        self.setMinimumWidth(520)
        self._cfg  = dict(cfg)
        self._input_data = input_data
        self._available_elements = available_elements
        self._build_ui()

    def _build_ui(self):
        root   = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner  = QWidget(); lay = QVBoxLayout(inner)
        scroll.setWidget(inner); root.addWidget(scroll)

        # ── Data & Chart Type ─────────────────────────────────────────
        g1 = QGroupBox("Data & Chart Type"); f1 = QFormLayout(g1)
        self._chart_type = QComboBox()
        self._chart_type.addItems(PIE_CHART_TYPES)
        self._chart_type.setCurrentText(self._cfg.get('chart_type', PIE_CHART_TYPES[0]))
        f1.addRow("Chart Type:", self._chart_type)
        self._data_type = QComboBox()
        self._data_type.addItems(PIE_DATA_TYPES)
        self._data_type.setCurrentText(self._cfg.get('data_type_display', PIE_DATA_TYPES[0]))
        f1.addRow("Data Type:", self._data_type)
        lay.addWidget(g1)

        # ── Display Mode (multi-sample only) ──────────────────────────
        self._display_mode = None
        if _is_multi(self._input_data):
            g2 = QGroupBox("Multiple Sample Display"); f2 = QFormLayout(g2)
            self._display_mode = QComboBox()
            self._display_mode.addItems(PIE_DISPLAY_MODES)
            self._display_mode.setCurrentText(
                self._cfg.get('display_mode', PIE_DISPLAY_MODES[0]))
            f2.addRow("Mode:", self._display_mode)
            lay.addWidget(g2)

        # ── Labels & Thresholds ───────────────────────────────────────
        g3 = QGroupBox("Labels & Thresholds"); f3 = QFormLayout(g3)
        self._thresh = QDoubleSpinBox()
        self._thresh.setRange(0.0, 50.0); self._thresh.setSuffix(" %")
        self._thresh.setValue(self._cfg.get('threshold', 1.0))
        f3.addRow("Threshold ('Others'):", self._thresh)
        self._filter_zeros = QCheckBox("Filter Zero Values")
        self._filter_zeros.setChecked(self._cfg.get('filter_zeros', True))
        f3.addRow("", self._filter_zeros)
        self._show_counts = QCheckBox("Show Particle Counts")
        self._show_counts.setChecked(self._cfg.get('show_counts', True))
        f3.addRow("", self._show_counts)
        self._show_pct = QCheckBox("Show Percentages")
        self._show_pct.setChecked(self._cfg.get('show_percentages', True))
        f3.addRow("", self._show_pct)
        self._label_mode = QComboBox()
        self._label_mode.addItems(LABEL_MODES)
        self._label_mode.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
        f3.addRow("Label Mode:", self._label_mode)
        lay.addWidget(g3)

        # ── Wedge Colours + Explode ───────────────────────────────────
        self._elem_color_btns: dict[str, _ColorBtn]     = {}
        self._elem_explode:    dict[str, QDoubleSpinBox] = {}
        if self._available_elements:
            g4 = QGroupBox("Wedge Colours & Explode Offset")
            v4 = QVBoxLayout(g4)
            ec      = self._cfg.get('element_colors', {})
            exp_d   = self._cfg.get('explode', {})
            hdr = QHBoxLayout()
            hdr.addWidget(QLabel("<b>Element</b>"), 3)
            hdr.addWidget(QLabel("<b>Colour</b>"), 1)
            hdr.addWidget(QLabel("<b>Explode</b>"), 2)
            v4.addLayout(hdr)
            for i, el in enumerate(self._available_elements):
                row = QHBoxLayout()
                row.addWidget(QLabel(el), 3)
                btn = _ColorBtn(ec.get(el, DEFAULT_PIE_COLORS[i % len(DEFAULT_PIE_COLORS)]))
                self._elem_color_btns[el] = btn
                row.addWidget(btn, 1)
                sb = QDoubleSpinBox()
                sb.setRange(0.0, 0.30); sb.setSingleStep(0.02); sb.setDecimals(2)
                sb.setValue(exp_d.get(el, 0.0))
                self._elem_explode[el] = sb
                row.addWidget(sb, 2)
                w = QWidget(); w.setLayout(row); v4.addWidget(w)
            lay.addWidget(g4)

        # ── Sample Name Mappings (multi only) ─────────────────────────
        self._sample_edits: dict[str, QLineEdit] = {}
        if _is_multi(self._input_data):
            names = self._input_data.get('sample_names', [])
            if names:
                g5 = QGroupBox("Sample Display Names"); v5 = QVBoxLayout(g5)
                nm = dict(self._cfg.get('sample_name_mappings', {}))
                for sn in names:
                    row = QHBoxLayout()
                    row.addWidget(QLabel(sn))
                    ed = QLineEdit(nm.get(sn, sn))
                    row.addWidget(ed)
                    self._sample_edits[sn] = ed
                    w = QWidget(); w.setLayout(row); v5.addWidget(w)
                lay.addWidget(g5)

        # ── New shared groups ─────────────────────────────────────────
        self._pie_style  = PieStyleGroup(self._cfg)
        self._label_line = LabelLineGroup(self._cfg)
        self._legend     = LegendGroup(self._cfg)
        self._export     = ExportGroup(self._cfg)
        for grp in (self._pie_style, self._label_line, self._legend, self._export):
            lay.addWidget(grp.build())

        # ── Font ──────────────────────────────────────────────────────
        self._font_grp = FontSettingsGroup(self._cfg)
        lay.addWidget(self._font_grp.build())

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        d = {
            'chart_type':         self._chart_type.currentText(),
            'data_type_display':  self._data_type.currentText(),
            'threshold':          self._thresh.value(),
            'filter_zeros':       self._filter_zeros.isChecked(),
            'show_counts':        self._show_counts.isChecked(),
            'show_percentages':   self._show_pct.isChecked(),
            'label_mode':         self._label_mode.currentText(),
            'element_colors':     {k: b.color() for k, b in self._elem_color_btns.items()},
            'explode':            {k: sb.value() for k, sb in self._elem_explode.items()},
        }
        if self._display_mode is not None:
            d['display_mode'] = self._display_mode.currentText()
        if self._sample_edits:
            d['sample_name_mappings'] = {k: v.text() for k, v in self._sample_edits.items()}
        d.update(self._pie_style.collect())
        d.update(self._label_line.collect())
        d.update(self._legend.collect())
        d.update(self._export.collect())
        d.update(self._font_grp.collect())
        return d


class PieChartDisplayDialog(QDialog):
    def __init__(self, node, parent_window=None):
        """
        Args:
            node (Any): Tree or graph node.
            parent_window (Any): The parent window.
        """
        super().__init__(parent_window)
        self.node = node
        self.setWindowTitle("Element Distribution Pie Charts")
        self.setMinimumSize(1100, 750)
        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        self.canvas_widget = MplPieCanvas(self.node.config)
        self.canvas_widget.set_context_menu_callback(self._ctx_menu)
        lay.addWidget(self.canvas_widget)

        # ── Bottom toolbar ────────────────────────────────────────────
        bb = QHBoxLayout(); bb.setContentsMargins(0, 4, 0, 0)
        btn_s = QPushButton("⚙  Settings");     btn_s.clicked.connect(self._open_settings)
        btn_r = QPushButton("↺  Reset Labels"); btn_r.clicked.connect(self._reset_labels)
        btn_e = QPushButton("⬆  Export…");      btn_e.clicked.connect(self._export)
        bb.addWidget(btn_s); bb.addWidget(btn_r)
        bb.addStretch(); bb.addWidget(btn_e)
        lay.addLayout(bb)

    # ── Context menu ──────────────────────────────────────────────────

    def _ctx_menu(self, global_pos):
        """
        Args:
            global_pos (Any): The global pos.
        """
        cfg  = self.node.config
        menu = QMenu(self)

        cm = menu.addMenu("Chart Type")
        for ct in PIE_CHART_TYPES:
            a = cm.addAction(ct); a.setCheckable(True)
            a.setChecked(cfg.get('chart_type') == ct)
            a.triggered.connect(lambda _, v=ct: self._set('chart_type', v))

        dm = menu.addMenu("Data Type")
        for dt in PIE_DATA_TYPES:
            a = dm.addAction(dt); a.setCheckable(True)
            a.setChecked(cfg.get('data_type_display') == dt)
            a.triggered.connect(lambda _, v=dt: self._set('data_type_display', v))

        tm = menu.addMenu("Quick Toggles")
        for key, lbl in [
            ('show_counts',           'Show Counts'),
            ('show_percentages',      'Show Percentages'),
            ('show_connection_lines', 'Connection Lines'),
            ('donut',                 'Donut Mode'),
            ('legend_show',           'Legend'),
            ('shadow',                'Shadow'),
            ('label_bbox',            'Label Box'),
        ]:
            a = tm.addAction(lbl); a.setCheckable(True)
            a.setChecked(bool(cfg.get(key, False)))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        lm = menu.addMenu("Label Mode")
        for mode in LABEL_MODES:
            a = lm.addAction(mode); a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set('label_mode', v))

        if _is_multi(self.node.input_data):
            mm = menu.addMenu("Display Mode")
            for m in PIE_DISPLAY_MODES:
                a = mm.addAction(m); a.setCheckable(True)
                a.setChecked(cfg.get('display_mode') == m)
                a.triggered.connect(lambda _, v=m: self._set('display_mode', v))

        menu.addSeparator()
        menu.addAction("Configure…").triggered.connect(self._open_settings)
        menu.addAction("Reset Label Positions").triggered.connect(self._reset_labels)
        menu.addAction("Export Figure…").triggered.connect(self._export)
        menu.exec(global_pos)

    # ── Slot helpers ──────────────────────────────────────────────────

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

    def _reset_labels(self):
        self.canvas_widget.reset_label_positions()
        self._refresh()

    def _export(self):
        self.canvas_widget.export_figure(self)

    def _open_settings(self):
        elems = self._get_available_elements()
        dlg   = PieChartSettingsDialog(
            self.node.config, self.node.input_data, elems, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _get_available_elements(self):
        """
        Returns:
            object: Result of the operation.
        """
        pd_data = self.node.extract_plot_data()
        elems   = set()
        if pd_data:
            if _is_multi(self.node.input_data):
                for sd in pd_data.values():
                    if 'element_data' in sd:
                        elems.update(sd['element_data'].columns)
            elif 'element_data' in pd_data:
                elems.update(pd_data['element_data'].columns)
        return sort_elements_by_mass(list(elems))

    # ── Render pipeline ───────────────────────────────────────────────

    def _refresh(self):
        try:
            plot_data = self.node.extract_plot_data()
            if not plot_data:
                self.canvas_widget.render([])
                return

            cfg      = self.node.config
            subplots = []

            if _is_multi(self.node.input_data):
                mode = cfg.get('display_mode', PIE_DISPLAY_MODES[0])
                if mode == 'Combined Distribution':
                    comb_data, comb_counts = {}, {}
                    for sd in plot_data.values():
                        d, c = self._calc_single(sd, cfg)
                        for k, v in d.items(): comb_data[k]   = comb_data.get(k, 0) + v
                        for k, v in c.items(): comb_counts[k] = comb_counts.get(k, 0) + v
                    subplots.append(
                        self._build_sp(comb_data, comb_counts, cfg, 'Combined', 'combined'))
                else:
                    for sn, sd in plot_data.items():
                        d, cnt = self._calc_single(sd, cfg)
                        subplots.append(
                            self._build_sp(d, cnt, cfg, get_display_name(sn, cfg), sn))
            else:
                d, cnt = self._calc_single(plot_data, cfg)
                subplots.append(
                    self._build_sp(d, cnt, cfg, 'Element Distribution', 'default'))

            self.canvas_widget.render(subplots)
        except Exception:
            traceback.print_exc()

    def _calc_single(self, sample_data, cfg):
        """
        Args:
            sample_data (Any): The sample data.
            cfg (Any): The cfg.
        Returns:
            tuple: Result of the operation.
        """
        ed = sample_data.get('element_data')
        if ed is None:
            return {}, {}
        chart_type     = cfg.get('chart_type', PIE_CHART_TYPES[0])
        data_totals    = {}
        particle_counts = {}
        for col in ed.columns:
            pc = int((ed[col] > 0).sum())
            if pc > 0:
                particle_counts[col] = pc
                if chart_type == 'Particle Count Distribution':
                    data_totals[col] = pc
                else:
                    filt = ed[col][ed[col] > 0] if cfg.get('filter_zeros', True) else ed[col]
                    data_totals[col] = filt.sum()
        return data_totals, particle_counts

    def _build_sp(self, data, orig_counts, cfg, title, key) -> dict:
        """
        Args:
            data (Any): Input data.
            orig_counts (Any): The orig counts.
            cfg (Any): The cfg.
            title (Any): Window or dialog title.
            key (Any): Dictionary or storage key.
        Returns:
            dict: Result of the operation.
        """
        empty = {'labels': [], 'sizes': [], 'texts': [],
                 'colors': [], 'title': title, 'key': key}
        if not data:
            return empty
        total = sum(data.values())
        if total == 0:
            return empty

        pcts   = {k: (v / total) * 100 for k, v in data.items()}
        thresh = cfg.get('threshold', 1.0)
        main   = {k: v for k, v in pcts.items() if v >= thresh}
        others = {k: v for k, v in pcts.items() if v < thresh}
        if others:
            main['Others'] = sum(others.values())

        sorted_e = sorted(main.items(), key=lambda x: x[1], reverse=True)
        labels = [x[0] for x in sorted_e]
        sizes  = [x[1] for x in sorted_e]
        ec     = cfg.get('element_colors', {})

        colors, texts = [], []
        for i, (lbl, sz) in enumerate(zip(labels, sizes)):
            if lbl == 'Others':
                colors.append('#808080')
                count = sum(orig_counts.get(k, 0) for k in others)
            else:
                colors.append(ec.get(lbl, DEFAULT_PIE_COLORS[i % len(DEFAULT_PIE_COLORS)]))
                count = orig_counts.get(lbl, 0)

            parts = [_format_element_label(lbl, cfg.get('label_mode', 'Symbol'))]
            if cfg.get('show_counts', True):      parts.append(f"({count:,})")
            if cfg.get('show_percentages', True):  parts.append(f"{sz:.1f}%")
            texts.append('\n'.join(parts))

        return {'labels': labels, 'sizes': sizes, 'texts': texts,
                'colors': colors, 'title': title, 'key': key}


class PieChartPlotNode(QObject):
    position_changed      = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        """
        Args:
            parent_window (Any): The parent window.
        """
        super().__init__()
        self.title           = "Element Distribution"
        self.node_type       = "pie_chart_plot"
        self.parent_window   = parent_window
        self.position        = None
        self._has_input      = True
        self._has_output     = False
        self.input_channels  = ["input"]
        self.output_channels = []

        self.config = {
            'chart_type':            'Element Distribution',
            'data_type_display':     'Counts',
            'threshold':             1.0,
            'filter_zeros':          True,
            'display_mode':          'Individual Subplots',
            'element_colors':        {},
            'sample_name_mappings':  {},
            'show_counts':           True,
            'show_percentages':      True,
            'label_mode':            'Symbol',
            'show_connection_lines': True,
            'connection_line_color': '#888888',
            'connection_line_style': '-',
            'label_bbox':            True,
            'label_distance':        1.25,
            'label_positions':       {},
            'donut':                 False,
            'donut_hole_size':       0.4,
            'donut_center_text':     '',
            'start_angle':           90,
            'shadow':                False,
            'edge_color':            '#FFFFFF',
            'edge_width':            1.5,
            'explode':               {},
            'legend_show':           False,
            'legend_position':       'best',
            'legend_outside':        False,
            'font_family':           'DejaVu Sans',
            'font_size':             10,
            'font_color':            '#000000',
            'bg_color':              '#FFFFFF',
            'export_format':         'svg',
            'export_dpi':            300,
        }
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
        dlg = PieChartDisplayDialog(self, parent_window)
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

    def extract_plot_data(self):
        """
        Returns:
            None
        """
        if not self.input_data:
            return None
        dt = self.config.get('data_type_display', 'Counts')
        dk = {
            'Counts':               'elements',
            'Element Mass (fg)':    'element_mass_fg',
            'Particle Mass (fg)':   'particle_mass_fg',
            'Element Moles (fmol)': 'element_moles_fmol',
            'Particle Moles (fmol)':'particle_moles_fmol',
        }.get(dt, 'elements')
        if self.input_data.get('type') == 'sample_data':
            return self._extract_single(dk)
        elif self.input_data.get('type') == 'multiple_sample_data':
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
        all_elems = sorted({e for p in particles for e in p.get(data_key, {})})
        if not all_elems:
            return None
        mat = []
        for p in particles:
            row = []
            for e in all_elems:
                v = p.get(data_key, {}).get(e, 0)
                row.append(v if (v > 0 and (data_key == 'elements' or not np.isnan(v))) else 0)
            mat.append(row)
        return {'element_data': pd.DataFrame(mat, columns=all_elems)} if mat else None

    def _extract_multi(self, data_key):
        """
        Args:
            data_key (Any): The data key.
        Returns:
            object: Result of the operation.
        """
        particles = self.input_data.get('particle_data', [])
        names     = self.input_data.get('sample_names', [])
        if not particles:
            return None
        all_elems = sorted({e for p in particles for e in p.get(data_key, {})})
        if not all_elems:
            return None
        sd = {n: [] for n in names}
        for p in particles:
            src = p.get('source_sample')
            if src in sd:
                row = []
                for e in all_elems:
                    v = p.get(data_key, {}).get(e, 0)
                    row.append(
                        v if (v > 0 and (data_key == 'elements' or not np.isnan(v))) else 0)
                sd[src].append(row)
        return ({n: {'element_data': pd.DataFrame(m, columns=all_elems)}
                 for n, m in sd.items() if m} or None)


class ElementCompositionSettingsDialog(QDialog):
    def __init__(self, cfg, input_data, available_combos, parent=None):
        """
        Args:
            cfg (Any): The cfg.
            input_data (Any): The input data.
            available_combos (Any): The available combos.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("Element Composition Settings")
        self.setMinimumWidth(540)
        self._cfg  = dict(cfg)
        self._input_data = input_data
        self._available_combos = available_combos
        self._build_ui()

    def _build_ui(self):
        root   = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner  = QWidget(); lay = QVBoxLayout(inner)
        scroll.setWidget(inner); root.addWidget(scroll)

        # ── Analysis & Data Type ──────────────────────────────────────
        g1 = QGroupBox("Analysis & Data Type"); f1 = QFormLayout(g1)
        self._analysis = QComboBox()
        self._analysis.addItems(COMP_ANALYSIS_TYPES)
        self._analysis.setCurrentText(
            self._cfg.get('analysis_type', COMP_ANALYSIS_TYPES[0]))
        f1.addRow("Analysis:", self._analysis)
        self._data_type = QComboBox()
        self._data_type.addItems(PIE_DATA_TYPES)
        self._data_type.setCurrentText(
            self._cfg.get('data_type_display', PIE_DATA_TYPES[0]))
        f1.addRow("Data Type:", self._data_type)
        lay.addWidget(g1)

        # ── Display Mode (multi only) ─────────────────────────────────
        self._display_mode = None
        if _is_multi(self._input_data):
            g2 = QGroupBox("Multiple Sample Display"); f2 = QFormLayout(g2)
            self._display_mode = QComboBox()
            self._display_mode.addItems(
                ['Individual Subplots', 'Side by Side Subplots',
                 'Combined Analysis', 'Comparative View'])
            self._display_mode.setCurrentText(
                self._cfg.get('display_mode', 'Individual Subplots'))
            f2.addRow("Mode:", self._display_mode)
            lay.addWidget(g2)

        # ── Thresholds & Labels ───────────────────────────────────────
        g3 = QGroupBox("Thresholds & Labels"); f3 = QFormLayout(g3)
        self._p_thresh = QSpinBox()
        self._p_thresh.setRange(1, 10000)
        self._p_thresh.setValue(self._cfg.get('particle_threshold', 10))
        f3.addRow("Min Particles:", self._p_thresh)
        self._pct_thresh = QDoubleSpinBox()
        self._pct_thresh.setRange(0.0, 50.0); self._pct_thresh.setSuffix(" %")
        self._pct_thresh.setValue(self._cfg.get('percentage_threshold', 1.0))
        f3.addRow("Min Percentage:", self._pct_thresh)
        self._show_vals   = QCheckBox("Show Data Values")
        self._show_vals.setChecked(self._cfg.get('show_data_values', True))
        self._show_counts = QCheckBox("Show Counts")
        self._show_counts.setChecked(self._cfg.get('show_counts', True))
        self._show_pct    = QCheckBox("Show Percentages")
        self._show_pct.setChecked(self._cfg.get('show_percentages', True))
        self._show_epct   = QCheckBox("Show Element % in Combos")
        self._show_epct.setChecked(self._cfg.get('show_element_percentages', False))
        for cb in (self._show_vals, self._show_counts, self._show_pct, self._show_epct):
            f3.addRow("", cb)
        self._label_mode = QComboBox()
        self._label_mode.addItems(LABEL_MODES)
        self._label_mode.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
        f3.addRow("Label Mode:", self._label_mode)
        lay.addWidget(g3)

        # ── Combination Colours + Explode ─────────────────────────────
        self._combo_color_btns: dict[str, _ColorBtn]     = {}
        self._combo_explode:    dict[str, QDoubleSpinBox] = {}
        if self._available_combos:
            g4 = QGroupBox("Wedge Colours & Explode (Top 15)")
            v4 = QVBoxLayout(g4)
            cc    = self._cfg.get('combination_colors', {})
            exp_d = self._cfg.get('explode', {})
            hdr   = QHBoxLayout()
            hdr.addWidget(QLabel("<b>Combination</b>"), 4)
            hdr.addWidget(QLabel("<b>Colour</b>"),      1)
            hdr.addWidget(QLabel("<b>Explode</b>"),     2)
            v4.addLayout(hdr)
            for i, combo in enumerate(self._available_combos[:15]):
                row   = QHBoxLayout()
                short = combo if len(combo) <= 28 else combo[:25] + "…"
                row.addWidget(QLabel(short), 4)
                btn = _ColorBtn(cc.get(combo, DEFAULT_COMBO_COLORS[i % len(DEFAULT_COMBO_COLORS)]))
                self._combo_color_btns[combo] = btn
                row.addWidget(btn, 1)
                sb = QDoubleSpinBox()
                sb.setRange(0.0, 0.30); sb.setSingleStep(0.02); sb.setDecimals(2)
                sb.setValue(exp_d.get(combo, 0.0))
                self._combo_explode[combo] = sb
                row.addWidget(sb, 2)
                w = QWidget(); w.setLayout(row); v4.addWidget(w)
            lay.addWidget(g4)

        # ── New shared groups ─────────────────────────────────────────
        self._pie_style  = PieStyleGroup(self._cfg)
        self._label_line = LabelLineGroup(self._cfg)
        self._legend     = LegendGroup(self._cfg)
        self._export     = ExportGroup(self._cfg)
        for grp in (self._pie_style, self._label_line, self._legend, self._export):
            lay.addWidget(grp.build())

        # ── Font ──────────────────────────────────────────────────────
        self._font_grp = FontSettingsGroup(self._cfg)
        lay.addWidget(self._font_grp.build())

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        d = {
            'analysis_type':            self._analysis.currentText(),
            'data_type_display':        self._data_type.currentText(),
            'particle_threshold':       self._p_thresh.value(),
            'percentage_threshold':     self._pct_thresh.value(),
            'show_data_values':         self._show_vals.isChecked(),
            'show_counts':              self._show_counts.isChecked(),
            'show_percentages':         self._show_pct.isChecked(),
            'show_element_percentages': self._show_epct.isChecked(),
            'label_mode':               self._label_mode.currentText(),
            'combination_colors':  {k: b.color() for k, b in self._combo_color_btns.items()},
            'explode':             {k: sb.value() for k, sb in self._combo_explode.items()},
        }
        if self._display_mode is not None:
            d['display_mode'] = self._display_mode.currentText()
        d.update(self._pie_style.collect())
        d.update(self._label_line.collect())
        d.update(self._legend.collect())
        d.update(self._export.collect())
        d.update(self._font_grp.collect())
        return d


class ElementCompositionDisplayDialog(QDialog):
    def __init__(self, node, parent_window=None):
        """
        Args:
            node (Any): Tree or graph node.
            parent_window (Any): The parent window.
        """
        super().__init__(parent_window)
        self.node = node
        self.setWindowTitle("Element Combination Analysis")
        self.setMinimumSize(1100, 750)
        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        self.canvas_widget = MplPieCanvas(self.node.config)
        self.canvas_widget.set_context_menu_callback(self._ctx_menu)
        lay.addWidget(self.canvas_widget)

        bb = QHBoxLayout(); bb.setContentsMargins(0, 4, 0, 0)
        btn_s = QPushButton("⚙  Settings");     btn_s.clicked.connect(self._open_settings)
        btn_r = QPushButton("↺  Reset Labels"); btn_r.clicked.connect(self._reset_labels)
        btn_e = QPushButton("⬆  Export…");      btn_e.clicked.connect(self._export)
        bb.addWidget(btn_s); bb.addWidget(btn_r)
        bb.addStretch(); bb.addWidget(btn_e)
        lay.addLayout(bb)

    def _ctx_menu(self, global_pos):
        """
        Args:
            global_pos (Any): The global pos.
        """
        cfg  = self.node.config
        menu = QMenu(self)

        am = menu.addMenu("Analysis Type")
        for ct in COMP_ANALYSIS_TYPES:
            a = am.addAction(ct); a.setCheckable(True)
            a.setChecked(cfg.get('analysis_type') == ct)
            a.triggered.connect(lambda _, v=ct: self._set('analysis_type', v))

        dm = menu.addMenu("Data Type")
        for dt in PIE_DATA_TYPES:
            a = dm.addAction(dt); a.setCheckable(True)
            a.setChecked(cfg.get('data_type_display') == dt)
            a.triggered.connect(lambda _, v=dt: self._set('data_type_display', v))

        tm = menu.addMenu("Quick Toggles")
        for key, lbl in [
            ('show_data_values',      'Data Values'),
            ('show_counts',           'Counts'),
            ('show_percentages',      'Percentages'),
            ('show_connection_lines', 'Connection Lines'),
            ('donut',                 'Donut Mode'),
            ('legend_show',           'Legend'),
            ('shadow',                'Shadow'),
            ('label_bbox',            'Label Box'),
        ]:
            a = tm.addAction(lbl); a.setCheckable(True)
            a.setChecked(bool(cfg.get(key, False)))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        if _is_multi(self.node.input_data):
            mm = menu.addMenu("Display Mode")
            for m in ['Individual Subplots', 'Side by Side Subplots',
                      'Combined Analysis', 'Comparative View']:
                a = mm.addAction(m); a.setCheckable(True)
                a.setChecked(cfg.get('display_mode') == m)
                a.triggered.connect(lambda _, v=m: self._set('display_mode', v))

        lm = menu.addMenu("Label Mode")
        for mode in LABEL_MODES:
            a = lm.addAction(mode); a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set('label_mode', v))

        menu.addSeparator()
        menu.addAction("Configure…").triggered.connect(self._open_settings)
        menu.addAction("Reset Label Positions").triggered.connect(self._reset_labels)
        menu.addAction("Export Figure…").triggered.connect(self._export)
        menu.exec(global_pos)

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

    def _reset_labels(self):
        self.canvas_widget.reset_label_positions()
        self._refresh()

    def _export(self):
        self.canvas_widget.export_figure(self)

    def _get_actual_combos(self) -> list[str]:
        """
        Returns:
            list[str]: Result of the operation.
        """
        plot_data = self.node.extract_plot_data()
        if not plot_data:
            return []
        all_c: dict = {}
        if _is_multi(self.node.input_data):
            for sd in plot_data.values():
                for c, info in sd.items():
                    all_c[c] = all_c.get(c, 0) + info.get('particle_count', 0)
        else:
            for c, info in plot_data.items():
                all_c[c] = info.get('particle_count', 0)
        return [k for k, _ in sorted(all_c.items(), key=lambda x: x[1], reverse=True)]

    def _open_settings(self):
        combos = self._get_actual_combos()
        dlg    = ElementCompositionSettingsDialog(
            self.node.config, self.node.input_data, combos, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _refresh(self):
        try:
            plot_data = self.node.extract_plot_data()
            if not plot_data:
                self.canvas_widget.render([])
                return

            cfg      = self.node.config
            subplots = []

            if _is_multi(self.node.input_data):
                mode = cfg.get('display_mode', 'Individual Subplots')
                if mode == 'Combined Analysis':
                    comb: dict = {}
                    for sd in plot_data.values():
                        for k, v in sd.items():
                            if k not in comb:
                                comb[k] = {'particle_count': 0, 'data_value': 0, 'elements': {}}
                            comb[k]['particle_count'] += v.get('particle_count', 0)
                            comb[k]['data_value']     += v.get('data_value', 0)
                    subplots.append(
                        self._build_sp(self._calc_data(comb, cfg), cfg, 'Combined', 'combined'))
                else:
                    for sn, sd in plot_data.items():
                        data = self._calc_data(sd, cfg)
                        subplots.append(
                            self._build_sp(data, cfg, get_display_name(sn, cfg), sn))
            else:
                data = self._calc_data(plot_data, cfg)
                subplots.append(
                    self._build_sp(data, cfg, 'Element Combinations', 'default'))

            self.canvas_widget.render(subplots)
        except Exception:
            traceback.print_exc()

    def _calc_data(self, plot_data, cfg) -> dict:
        """
        Args:
            plot_data (Any): The plot data.
            cfg (Any): The cfg.
        Returns:
            dict: Result of the operation.
        """
        at       = cfg.get('analysis_type', COMP_ANALYSIS_TYPES[0])
        pt       = cfg.get('particle_threshold', 10)
        filtered = {k: v for k, v in plot_data.items()
                    if v.get('particle_count', 0) >= pt}

        if at == 'Single vs Multiple Elements':
            res = {
                'Single Elements':   {'particle_count': 0, 'data_value': 0, 'elements': {}},
                'Multiple Elements': {'particle_count': 0, 'data_value': 0, 'elements': {}},
            }
            for k, v in filtered.items():
                tgt = ('Single Elements' if len(k.split(',')) == 1
                       else 'Multiple Elements')
                res[tgt]['particle_count'] += v.get('particle_count', 0)
                res[tgt]['data_value']     += v.get('data_value', 0)
            return {k: v for k, v in res.items() if v['particle_count'] > 0}

        return filtered

    def _build_sp(self, data, cfg, title, key) -> dict:
        """
        Args:
            data (Any): Input data.
            cfg (Any): The cfg.
            title (Any): Window or dialog title.
            key (Any): Dictionary or storage key.
        Returns:
            dict: Result of the operation.
        """
        empty = {'labels': [], 'sizes': [], 'texts': [],
                 'colors': [], 'title': title, 'key': key}
        if not data:
            return empty
        dt      = cfg.get('data_type_display', 'Counts')
        val_key = 'particle_count' if dt == 'Counts' else 'data_value'
        total   = sum(v.get(val_key, 0) for v in data.values())
        if total == 0:
            return empty

        pcts   = {k: (v.get(val_key, 0) / total) * 100 for k, v in data.items()}
        thresh = cfg.get('percentage_threshold', 1.0)
        main   = {k: v for k, v in pcts.items() if v >= thresh}
        others = {k: v for k, v in pcts.items() if v < thresh}
        if others:
            main['Others'] = sum(others.values())

        sorted_c = sorted(main.items(), key=lambda x: x[1], reverse=True)
        labels   = [x[0] for x in sorted_c]
        sizes    = [x[1] for x in sorted_c]
        cc       = cfg.get('combination_colors', {})

        colors, texts = [], []
        for i, (lbl, sz) in enumerate(zip(labels, sizes)):
            if lbl == 'Others':
                colors.append('#808080')
                pc    = sum(data[k].get('particle_count', 0) for k in others)
                dv    = sum(data[k].get('data_value', 0)     for k in others)
                elems = {}
            else:
                colors.append(cc.get(lbl, DEFAULT_COMBO_COLORS[i % len(DEFAULT_COMBO_COLORS)]))
                pc    = data[lbl].get('particle_count', 0) if lbl in data else 0
                dv    = data[lbl].get('data_value', 0)    if lbl in data else 0
                elems = data[lbl].get('elements', {})      if lbl in data else {}

            mode  = cfg.get('label_mode', 'Symbol')
            parts = [_format_element_label(lbl, mode)]
            if cfg.get('show_counts', True):
                parts.append(f"({pc:,} particles)")
            if cfg.get('show_data_values', True) and dt != 'Counts':
                unit = 'fg' if 'Mass' in dt else 'fmol' if 'Moles' in dt else ''
                parts.append(f"[{dv:.2f} {unit}]".strip())
            if cfg.get('show_percentages', True):
                parts.append(f"{sz:.1f}%")
            if cfg.get('show_element_percentages', False) and elems and len(elems) > 1:
                etot = sum(elems.values())
                if etot > 0:
                    eparts = [f"{e}: {(v/etot)*100:.1f}%" for e, v in elems.items()]
                    parts.append(f"({', '.join(eparts)})")
            texts.append('\n'.join(parts))

        return {'labels': labels, 'sizes': sizes, 'texts': texts,
                'colors': colors, 'title': title, 'key': key}


class ElementCompositionPlotNode(QObject):
    position_changed      = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        """
        Args:
            parent_window (Any): The parent window.
        """
        super().__init__()
        self.title           = "Element Composition"
        self.node_type       = "element_composition_plot"
        self.parent_window   = parent_window
        self.position        = None
        self._has_input      = True
        self._has_output     = False
        self.input_channels  = ["input"]
        self.output_channels = []

        self.config = {
            'analysis_type':             'Single vs Multiple Elements',
            'data_type_display':         'Counts',
            'particle_threshold':        10,
            'percentage_threshold':      1.0,
            'filter_zeros':              True,
            'display_mode':              'Individual Subplots',
            'combination_colors':        {},
            'show_data_values':          True,
            'show_counts':               True,
            'show_percentages':          True,
            'show_element_percentages':  False,
            'label_mode':                'Symbol',
            'show_connection_lines':     True,
            'connection_line_color':     '#888888',
            'connection_line_style':     '-',
            'label_bbox':                True,
            'label_distance':            1.25,
            'label_positions':           {},
            'donut':                     False,
            'donut_hole_size':           0.4,
            'donut_center_text':         '',
            'start_angle':               90,
            'shadow':                    False,
            'edge_color':                '#FFFFFF',
            'edge_width':                1.5,
            'explode':                   {},
            'legend_show':               False,
            'legend_position':           'best',
            'legend_outside':            False,
            'font_family':               'DejaVu Sans',
            'font_size':                 10,
            'font_color':                '#000000',
            'bg_color':                  '#FFFFFF',
            'export_format':             'svg',
            'export_dpi':                300,
        }
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
        dlg = ElementCompositionDisplayDialog(self, parent_window)
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

    def extract_plot_data(self):
        """
        Returns:
            None
        """
        if not self.input_data:
            return None
        dt = self.config.get('data_type_display', 'Counts')
        dk = {
            'Counts':               'elements',
            'Element Mass (fg)':    'element_mass_fg',
            'Particle Mass (fg)':   'particle_mass_fg',
            'Element Moles (fmol)': 'element_moles_fmol',
            'Particle Moles (fmol)':'particle_moles_fmol',
        }.get(dt, 'elements')
        if self.input_data.get('type') == 'sample_data':
            return self._extract_single_enhanced(dk)
        elif self.input_data.get('type') == 'multiple_sample_data':
            return self._extract_multi_enhanced(dk)
        return None

    def _extract_single_enhanced(self, data_key):
        """
        Args:
            data_key (Any): The data key.
        Returns:
            object: Result of the operation.
        """
        particles = self.input_data.get('particle_data')
        if not particles:
            return None
        combos: dict = {}
        for p in particles:
            elems = {
                e: v for e, v in p.get(data_key, {}).items()
                if v > 0 and (data_key == 'elements' or not np.isnan(v))
            }
            if elems:
                c_name = ', '.join(sorted(elems.keys()))
                if c_name not in combos:
                    combos[c_name] = {'particle_count': 0, 'data_value': 0, 'elements': {}}
                combos[c_name]['particle_count'] += 1
                combos[c_name]['data_value']     += sum(elems.values())
                for e, v in elems.items():
                    combos[c_name]['elements'][e] = combos[c_name]['elements'].get(e, 0) + v
        return combos or None

    def _extract_multi_enhanced(self, data_key):
        """
        Args:
            data_key (Any): The data key.
        Returns:
            object: Result of the operation.
        """
        particles = self.input_data.get('particle_data', [])
        names     = self.input_data.get('sample_names', [])
        if not particles:
            return None
        sd = {n: {} for n in names}
        for p in particles:
            src = p.get('source_sample')
            if src not in sd:
                continue
            elems = {
                e: v for e, v in p.get(data_key, {}).items()
                if v > 0 and (data_key == 'elements' or not np.isnan(v))
            }
            if elems:
                c_name = ', '.join(sorted(elems.keys()))
                if c_name not in sd[src]:
                    sd[src][c_name] = {'particle_count': 0, 'data_value': 0, 'elements': {}}
                sd[src][c_name]['particle_count'] += 1
                sd[src][c_name]['data_value']     += sum(elems.values())
                for e, v in elems.items():
                    sd[src][c_name]['elements'][e] = sd[src][c_name]['elements'].get(e, 0) + v
        return {k: v for k, v in sd.items() if v} or None