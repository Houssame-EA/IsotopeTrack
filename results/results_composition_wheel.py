"""
Composition Wheel (2D / 3D) — single & multi-sample particle-signature plot.

A polar "fingerprint" view of single-particle data, inspired by the
colorguesser composition wheel:

    • angle  = composition  (categorical element OR continuous A/(A+B) ratio)
    • radius = particle mass / counts (small near centre, large at the rim)
    • z-axis = particle-count density  OR  sample layer (3D modes)
    • colour = element  OR  sample

Multi-sample modes:  stacked discs, overlaid, small-multiples.
The 3D view uses pyqtgraph.opengl when available and transparently falls
back to a matplotlib 3D canvas otherwise.

Wiring (all shared, no duplication):
    build_element_matrix, get_sample_color, get_display_name,
    format_element_label / Renderer, FontSettingsGroup,
    DownloadConfigDialog / download helpers, sort_elements_by_mass.

Drop-in node for the canvas workflow editor — mirrors the
ElementCompositionPlotNode / …DisplayDialog / …Canvas triple.
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd

import matplotlib.patches as mpatches
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QMenu, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
    QDialogButtonBox,
)

from results.shared_plot_utils import copy_figure_to_clipboard
from results.shared_plot_utils import (
    FontSettingsGroup, Renderer, LABEL_MODES, build_element_matrix,
    format_element_label, get_display_name, get_sample_color,
    DownloadConfigDialog, make_font_properties,
)
from results.utils_sort import sort_elements_by_mass
import logging
_itk_log = logging.getLogger("IsotopeTrack.results.results_composition_wheel")


try:
    import pyqtgraph.opengl as gl
    _HAVE_GL = True
except Exception:                                   # pragma: no cover
    _itk_log.exception("Handled exception in <module>")
    _HAVE_GL = False


WHEEL_MODES = [
    'Single sample',
    'Stacked discs (Z = sample)',
    'Overlaid (colour = sample)',
    'Small multiples',
    'Density surface (Z = count)',
]
ANGLE_MODES = [
    'Element (categorical)',
    'Ratio A/(A+B) (continuous)',
]
RADIUS_MODES = ['Mass', 'Counts']
DATA_KEY_MAP = {
    'Counts':                'elements',
    'Element Mass (fg)':     'element_mass_fg',
    'Particle Mass (fg)':    'particle_mass_fg',
    'Element Moles (fmol)':  'element_moles_fmol',
    'Particle Moles (fmol)': 'particle_moles_fmol',
}


# ─────────────────────────────────────────────────────────────────────────
# Geometry helpers (pure, shared by 2D and 3D canvases)
# ─────────────────────────────────────────────────────────────────────────

def _dominant_element(row: pd.Series) -> str | None:
    """Element with the largest value in a particle row (None if all zero)."""
    if row.empty:
        return None
    e = row.idxmax()
    return e if row[e] > 0 else None


def compute_wheel_xy(df: pd.DataFrame, cfg: dict) -> dict:
    """
    Map a particles × elements matrix into wheel coordinates.

    Returns dict with arrays:
        x, y      : unit-disc coordinates (0° at top, clockwise)
        elem      : dominant element per particle (categorical colouring)
        r_raw     : the radial magnitude before normalisation
    Honours angle_mode / radius_mode from cfg.
    """
    if df is None or df.empty:
        return {'x': np.array([]), 'y': np.array([]),
                'elem': [], 'r_raw': np.array([])}

    elements = sort_elements_by_mass(list(df.columns))
    df = df[elements]
    ang = {e: i / len(elements) * 2 * math.pi for i, e in enumerate(elements)}

    angle_mode = cfg.get('angle_mode', ANGLE_MODES[0])
    radius_mode = cfg.get('radius_mode', 'Mass')

    vals = df.values.astype(float)
    row_sum = vals.sum(axis=1)
    keep = row_sum > 0
    vals, row_sum = vals[keep], row_sum[keep]
    sub = df[keep]

    # ── angle ────────────────────────────────────────────────
    if angle_mode.startswith('Ratio'):
        a_el = cfg.get('ratio_a') or elements[0]
        b_el = cfg.get('ratio_b') or (elements[1] if len(elements) > 1 else elements[0])
        va = sub[a_el].values.astype(float) if a_el in sub else np.zeros(len(sub))
        vb = sub[b_el].values.astype(float) if b_el in sub else np.zeros(len(sub))
        denom = va + vb
        with np.errstate(divide='ignore', invalid='ignore'):
            frac = np.where(denom > 0, va / denom, 0.5)
        theta = frac * 2 * math.pi            # pure-B at 0°, pure-A at 360°
        dom = [a_el if f >= 0.5 else b_el for f in frac]
    else:
        dom = [_dominant_element(sub.iloc[i]) for i in range(len(sub))]
        jitter = np.random.default_rng(0).normal(0, 0.14, size=len(sub))
        theta = np.array([ang.get(d, 0.0) for d in dom]) + jitter

    # ── radius ───────────────────────────────────────────────
    if radius_mode == 'Counts':
        r_raw = np.ones(len(sub))             # all particles share rim band
    else:
        r_raw = row_sum
    if r_raw.size and r_raw.max() > r_raw.min():
        lr = np.log10(np.clip(r_raw, 1e-12, None))
        r = 0.12 + (lr - lr.min()) / (lr.max() - lr.min()) * 0.86
    else:
        r = np.full(len(sub), 0.6)

    x = r * np.sin(theta)
    y = -r * np.cos(theta)
    return {'x': x, 'y': y, 'elem': dom, 'r_raw': r_raw, 'elements': elements}


def polar_histogram(x: np.ndarray, y: np.ndarray,
                    n_ang: int = 24, n_rad: int = 6) -> np.ndarray:
    """Bin wheel points into an (n_ang × n_rad) count grid for the Z surface."""
    grid = np.zeros((n_ang, n_rad))
    if x.size == 0:
        return grid
    a = np.arctan2(y, x)
    a[a < 0] += 2 * math.pi
    r = np.clip(np.hypot(x, y), 0, 0.999)
    ia = np.clip((a / (2 * math.pi) * n_ang).astype(int), 0, n_ang - 1)
    ir = np.clip((r * n_rad).astype(int), 0, n_rad - 1)
    for i, j in zip(ia, ir):
        grid[i, j] += 1
    return grid


# ─────────────────────────────────────────────────────────────────────────
# 3D canvas — pyqtgraph.opengl preferred, matplotlib fallback
# ─────────────────────────────────────────────────────────────────────────

class CompositionWheelCanvas(QWidget):
    """
    Renders the composition wheel. Holds either a GLViewWidget (3D, GPU) or
    a matplotlib FigureCanvas (2D, and 3D fallback). `render(samples, cfg)`
    is the single entry point; everything else is internal.
    """

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self._gl_view = None
        self.figure = Figure(tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        if _HAVE_GL:
            self._gl_view = gl.GLViewWidget()
            self._gl_view.setCameraPosition(distance=3.2, elevation=22, azimuth=-60)
            self._gl_view.setBackgroundColor(self._qcolor(cfg.get('bg_color', '#FFFFFF')))
            lay.addWidget(self._gl_view)
        lay.addWidget(self.canvas)
        self._show_for_mode(cfg.get('wheel_mode', WHEEL_MODES[0]))

        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._fwd_ctx)
        self._ctx_cb = None

    # ── public API ──────────────────────────────────────────
    def set_context_menu_callback(self, fn):
        self._ctx_cb = fn

    def _fwd_ctx(self, pos):
        if self._ctx_cb:
            self._ctx_cb(self.canvas.mapToGlobal(pos))

    def render(self, samples: dict, cfg: dict):
        """
        samples: {sample_name: {'x':, 'y':, 'elem':, 'r_raw':}}  (wheel coords)
        cfg:     node.config
        """
        self._cfg = cfg
        mode = cfg.get('wheel_mode', WHEEL_MODES[0])
        self._show_for_mode(mode)

        is3d = mode.startswith('Stacked') or mode.startswith('Density')
        if is3d and self._gl_view is not None:
            self._render_gl(samples, cfg, mode)
        elif is3d:
            self._render_mpl_3d(samples, cfg, mode)
        else:
            self._render_mpl_2d(samples, cfg, mode)

    def export_figure(self, parent=None):
        """Reuse the standard download dialog (matplotlib path)."""
        dlg = DownloadConfigDialog('composition_wheel', parent=parent)
        if dlg.exec() != QDialog.Accepted:
            return
        c = dlg.collect()
        from PySide6.QtWidgets import QFileDialog
        if c['format'] == 'CSV':
            return                                   # data CSV wired by dialog
        ext = {'PNG': 'png', 'SVG': 'svg', 'PDF': 'pdf'}[c['format']]
        path, _ = QFileDialog.getSaveFileName(
            parent, 'Save Figure', f"{c['filename']}.{ext}",
            f'{c["format"]} Files (*.{ext})')
        if not path:
            return
        if not path.lower().endswith(f'.{ext}'):
            path += f'.{ext}'
        self.figure.savefig(path, dpi=c.get('dpi', 300),
                            bbox_inches='tight',
                            facecolor=self.figure.get_facecolor())

    # ── visibility toggling between GL / mpl ─────────────────
    def _show_for_mode(self, mode: str):
        is3d = mode.startswith('Stacked') or mode.startswith('Density')
        gl_on = is3d and self._gl_view is not None
        if self._gl_view is not None:
            self._gl_view.setVisible(gl_on)
        # mpl canvas hidden only when GL is actively driving 3D
        self.canvas.setVisible(not gl_on)

    # ── colour helpers ──────────────────────────────────────
    @staticmethod
    def _qcolor(hexstr):
        c = QColor(hexstr)
        return (c.redF(), c.greenF(), c.blueF(), 1.0)

    def _elem_palette(self, elements):
        base = ['#d8d8d8', '#c0533b', '#e0b34d', '#7fb04d', '#9aa7b0',
                '#6fae8f', '#5b8fc9', '#9b7bd1', '#EC4899', '#F59E0B']
        return {e: base[i % len(base)] for i, e in enumerate(elements)}

    # ── 2D matplotlib (single / overlay / small multiples) ───
    def _render_mpl_2d(self, samples, cfg, mode):
        self.figure.clear()
        bg = cfg.get('bg_color', '#FFFFFF')
        self.figure.patch.set_facecolor(bg)
        fp = make_font_properties(cfg)

        names = list(samples.keys())
        if mode == 'Small multiples' and len(names) > 1:
            cols = min(3, len(names))
            rows = math.ceil(len(names) / cols)
            for i, n in enumerate(names):
                ax = self.figure.add_subplot(rows, cols, i + 1)
                self._draw_disc(ax, {n: samples[n]}, cfg, by_sample=False,
                                title=get_display_name(n, cfg))
        else:
            ax = self.figure.add_subplot(111)
            by_sample = mode.startswith('Overlaid')
            self._draw_disc(ax, samples, cfg, by_sample=by_sample,
                            title=cfg.get('title', ''))
        self.canvas.draw()

    def _draw_disc(self, ax, samples, cfg, by_sample, title):
        bg = cfg.get('bg_color', '#FFFFFF')
        ax.set_facecolor(bg)
        ax.set_aspect('equal')
        ax.set_xlim(-1.25, 1.25)
        ax.set_ylim(-1.25, 1.25)
        ax.axis('off')

        # guide rings + spokes
        for rr in (0.5, 1.0):
            ax.add_patch(mpatches.Circle((0, 0), rr, fill=False,
                         ls='--', lw=0.5, ec='#cccccc'))

        # element rim labels (from first sample's element set)
        any_elems = next((s.get('elements') for s in samples.values()
                          if s.get('elements')), [])
        n = len(any_elems)
        lm = cfg.get('label_mode', 'Symbol')
        for i, e in enumerate(any_elems):
            a = i / n * 2 * math.pi
            ax.plot([0, math.sin(a)], [0, -math.cos(a)],
                    color='#e5e5e5', lw=0.5, zorder=0)
            lbl = format_element_label(e, lm, Renderer.MATHTEXT, cfg)
            ax.text(1.12 * math.sin(a), -1.12 * math.cos(a), lbl,
                    ha='center', va='center', fontproperties=fp_or_none(cfg),
                    color=cfg.get('font_color', '#000000'))

        handles = []
        for idx, (name, s) in enumerate(samples.items()):
            if by_sample:
                col = get_sample_color(name, idx, cfg)
                ax.scatter(s['x'], s['y'], s=14, c=col, alpha=0.55,
                           edgecolors='white', linewidths=0.3, zorder=3)
                handles.append(mpatches.Patch(
                    color=col, label=get_display_name(name, cfg)))
            else:
                pal = self._elem_palette(s.get('elements', []))
                cols = [pal.get(e, '#888888') for e in s['elem']]
                ax.scatter(s['x'], s['y'], s=14, c=cols, alpha=0.55,
                           edgecolors='white', linewidths=0.3, zorder=3)
        if title:
            ax.set_title(title, fontproperties=fp_or_none(cfg),
                         color=cfg.get('font_color', '#000000'))
        if by_sample and handles and cfg.get('legend_show', True):
            ax.legend(handles=handles, loc=cfg.get('legend_position', 'best'),
                      frameon=False)

    # ── 3D matplotlib fallback ───────────────────────────────
    def _render_mpl_3d(self, samples, cfg, mode):
        self.figure.clear()
        self.figure.patch.set_facecolor(cfg.get('bg_color', '#FFFFFF'))
        ax = self.figure.add_subplot(111, projection='3d')
        if mode.startswith('Density'):
            name = cfg.get('active_sample') or next(iter(samples), None)
            if name is None:
                self.canvas.draw(); return
            s = samples[name]
            grid = polar_histogram(s['x'], s['y'])
            n_ang, n_rad = grid.shape
            for ia in range(n_ang):
                for ir in range(n_rad):
                    h = grid[ia, ir]
                    if h <= 0:
                        continue
                    a = (ia + 0.5) / n_ang * 2 * math.pi
                    r = (ir + 0.5) / n_rad
                    ax.bar3d(r * math.cos(a), r * math.sin(a), 0,
                             0.06, 0.06, h, shade=True,
                             color=_viridis(h / grid.max()))
        else:  # stacked
            for i, (name, s) in enumerate(samples.items()):
                z = (i - (len(samples) - 1) / 2) * 1.0
                col = get_sample_color(name, i, cfg)
                ax.scatter(s['x'], s['y'], np.full(len(s['x']), z),
                           s=10, c=col, alpha=0.6,
                           label=get_display_name(name, cfg))
            if cfg.get('legend_show', True):
                ax.legend(loc='upper left', frameon=False)
        ax.set_axis_off()
        self.canvas.draw()

    # ── 3D OpenGL (fast path) ────────────────────────────────
    def _render_gl(self, samples, cfg, mode):
        v = self._gl_view
        v.clear()
        v.setBackgroundColor(self._qcolor(cfg.get('bg_color', '#FFFFFF')))

        def disc_rings(z):
            for rr in (0.5, 1.0):
                pts = np.array([[rr * math.cos(t), rr * math.sin(t), z]
                                for t in np.linspace(0, 2 * math.pi, 64)])
                v.addItem(gl.GLLinePlotItem(pos=pts, color=(0.6, 0.6, 0.6, 1),
                                            antialias=True, mode='line_strip'))

        if mode.startswith('Density'):
            name = cfg.get('active_sample') or next(iter(samples), None)
            if name is None:
                return
            s = samples[name]
            disc_rings(0)
            grid = polar_histogram(s['x'], s['y'])
            mx = grid.max() or 1
            n_ang, n_rad = grid.shape
            for ia in range(n_ang):
                for ir in range(n_rad):
                    h = grid[ia, ir]
                    if h <= 0:
                        continue
                    a = (ia + 0.5) / n_ang * 2 * math.pi
                    r = (ir + 0.5) / n_rad
                    box = gl.GLBoxItem(size=None)
                    mesh = _gl_bar(r * math.cos(a), r * math.sin(a),
                                   0.07, h / mx * 1.4, _viridis(h / mx))
                    v.addItem(mesh)
        else:  # stacked discs
            for i, (name, s) in enumerate(samples.items()):
                z = (i - (len(samples) - 1) / 2) * 0.9
                disc_rings(z)
                if s['x'].size == 0:
                    continue
                pos = np.column_stack([s['x'], s['y'], np.full(len(s['x']), z)])
                col = QColor(get_sample_color(name, i, cfg))
                rgba = (col.redF(), col.greenF(), col.blueF(), 0.85)
                v.addItem(gl.GLScatterPlotItem(pos=pos, size=6,
                          color=rgba, pxMode=True))


# small free helpers ----------------------------------------------------------

def fp_or_none(cfg):
    try:
        return make_font_properties(cfg)
    except Exception:
        _itk_log.exception("Handled exception in fp_or_none")
        return None


def _viridis(t: float):
    t = max(0.0, min(1.0, t))
    stops = np.array([[0.27, 0.00, 0.33], [0.23, 0.32, 0.55],
                      [0.13, 0.57, 0.55], [0.37, 0.79, 0.38],
                      [0.99, 0.91, 0.14]])
    pos = np.linspace(0, 1, len(stops))
    r = np.interp(t, pos, stops[:, 0])
    g = np.interp(t, pos, stops[:, 1])
    b = np.interp(t, pos, stops[:, 2])
    return (r, g, b, 1.0)


def _gl_bar(cx, cy, w, h, rgba):
    """A coloured vertical box mesh for the density surface."""
    md = gl.MeshData.cylinder(rows=1, cols=4, radius=[w, w], length=h)
    item = gl.GLMeshItem(meshdata=md, smooth=False,
                         color=rgba, shader='shaded', glOptions='opaque')
    item.translate(cx, cy, 0)
    return item


# ─────────────────────────────────────────────────────────────────────────
# Settings dialog
# ─────────────────────────────────────────────────────────────────────────

class CompositionWheelSettingsDialog(QDialog):
    preview_requested = Signal(dict)

    def __init__(self, cfg, input_data, available_elements, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Composition Wheel — settings')
        self._cfg = cfg
        self._elements = available_elements or []
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)

        gb = QGroupBox('Mapping')
        form = QFormLayout(gb)
        self.mode_cb = QComboBox(); self.mode_cb.addItems(WHEEL_MODES)
        self.mode_cb.setCurrentText(self._cfg.get('wheel_mode', WHEEL_MODES[0]))
        form.addRow('Display mode:', self.mode_cb)

        self.dt_cb = QComboBox(); self.dt_cb.addItems(list(DATA_KEY_MAP.keys()))
        self.dt_cb.setCurrentText(self._cfg.get('data_type_display', 'Counts'))
        form.addRow('Data type:', self.dt_cb)

        self.angle_cb = QComboBox(); self.angle_cb.addItems(ANGLE_MODES)
        self.angle_cb.setCurrentText(self._cfg.get('angle_mode', ANGLE_MODES[0]))
        self.angle_cb.currentTextChanged.connect(self._sync_ratio)
        form.addRow('Angle:', self.angle_cb)

        self.radius_cb = QComboBox(); self.radius_cb.addItems(RADIUS_MODES)
        self.radius_cb.setCurrentText(self._cfg.get('radius_mode', 'Mass'))
        form.addRow('Radius:', self.radius_cb)

        self.ratio_a = QComboBox(); self.ratio_a.addItems(self._elements)
        self.ratio_b = QComboBox(); self.ratio_b.addItems(self._elements)
        if self._cfg.get('ratio_a'):
            self.ratio_a.setCurrentText(self._cfg['ratio_a'])
        if self._cfg.get('ratio_b'):
            self.ratio_b.setCurrentText(self._cfg['ratio_b'])
        rrow = QHBoxLayout(); rrow.addWidget(self.ratio_a)
        rrow.addWidget(QLabel('/ (A+B), B =')); rrow.addWidget(self.ratio_b)
        self._rrow_w = QWidget(); self._rrow_w.setLayout(rrow)
        form.addRow('Ratio A:', self._rrow_w)
        lay.addWidget(gb)

        self.lm_cb = QComboBox(); self.lm_cb.addItems(LABEL_MODES)
        self.lm_cb.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
        self.legend_cb = QCheckBox('Show legend')
        self.legend_cb.setChecked(self._cfg.get('legend_show', True))
        lrow = QFormLayout(); lrow.addRow('Isotope label:', self.lm_cb)
        lrow.addRow('', self.legend_cb)
        lay.addLayout(lrow)

        self.font_group = FontSettingsGroup(self._cfg)
        lay.addWidget(self.font_group.build())

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
        lay.addLayout(_btn_row)
        self._sync_ratio(self.angle_cb.currentText())

    def _sync_ratio(self, mode):
        self._rrow_w.setEnabled(mode.startswith('Ratio'))

    def collect(self) -> dict:
        out = {
            'wheel_mode':        self.mode_cb.currentText(),
            'data_type_display': self.dt_cb.currentText(),
            'angle_mode':        self.angle_cb.currentText(),
            'radius_mode':       self.radius_cb.currentText(),
            'ratio_a':           self.ratio_a.currentText(),
            'ratio_b':           self.ratio_b.currentText(),
            'label_mode':        self.lm_cb.currentText(),
            'legend_show':       self.legend_cb.isChecked(),
        }
        out.update(self.font_group.collect())
        return out


# ─────────────────────────────────────────────────────────────────────────
# Display dialog (standard four-button bar)
# ─────────────────────────────────────────────────────────────────────────

class CompositionWheelDisplayDialog(QDialog):
    def __init__(self, node, parent_window=None):
        super().__init__(parent_window)
        self.node = node
        self.setWindowTitle('Composition Wheel')
        self.setMinimumSize(1000, 760)
        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        # active-sample picker (used by single / density modes)
        top = QHBoxLayout()
        top.addWidget(QLabel('Sample:'))
        self.sample_cb = QComboBox()
        self.sample_cb.currentTextChanged.connect(self._on_sample)
        top.addWidget(self.sample_cb); top.addStretch()
        lay.addLayout(top)

        self.canvas_widget = CompositionWheelCanvas(self.node.config)
        self.canvas_widget.set_context_menu_callback(self._ctx_menu)
        lay.addWidget(self.canvas_widget)

        bb = QHBoxLayout(); bb.setContentsMargins(0, 4, 0, 0)
        b_fmt = QPushButton('Plot format settings'); b_fmt.clicked.connect(self._settings)
        b_qty = QPushButton('Configure mapping');     b_qty.clicked.connect(self._settings)
        b_rst = QPushButton('Reset view');            b_rst.clicked.connect(self._refresh)
        b_exp = QPushButton('Export figure');         b_exp.clicked.connect(self._export)
        for b in (b_fmt, b_qty, b_rst, b_exp):
            bb.addWidget(b)
        lay.addLayout(bb)

    def _on_sample(self, name):
        if name:
            self.node.config['active_sample'] = name
            self._refresh(repopulate=False)

    def _settings(self):
        _snap = dict(self.node.config)
        elements = self.node.available_elements()
        dlg = CompositionWheelSettingsDialog(
            self.node.config, None, elements, self)
        dlg.preview_requested.connect(lambda cfg: (self.node.config.update(cfg), self._refresh()))
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()
        else:
            self.node.config.clear()
            self.node.config.update(_snap)
            self._refresh()

    def _ctx_menu(self, global_pos):
        cfg = self.node.config
        menu = QMenu(self)
        mm = menu.addMenu('Display mode')
        for m in WHEEL_MODES:
            a = mm.addAction(m); a.setCheckable(True)
            a.setChecked(cfg.get('wheel_mode') == m)
            a.triggered.connect(lambda _, v=m: self._set('wheel_mode', v))
        lm = menu.addMenu('Isotope label')
        for m in LABEL_MODES:
            a = lm.addAction(m); a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == m)
            a.triggered.connect(lambda _, v=m: self._set('label_mode', v))
        a = menu.addAction('Show legend'); a.setCheckable(True)
        a.setChecked(cfg.get('legend_show', True))
        a.triggered.connect(lambda _: self._set('legend_show',
                                                not cfg.get('legend_show', True)))
        menu.addSeparator()
        act_copy_fig = menu.addAction("Copy figure")
        act_copy_fig.triggered.connect(
            lambda: copy_figure_to_clipboard(self.canvas_widget))
        menu.exec(global_pos)

    def _set(self, k, v):
        self.node.config[k] = v
        self._refresh()

    def _export(self):
        self.canvas_widget.export_figure(self)

    def _refresh(self, repopulate=True):
        samples = self.node.extract_plot_data()
        if samples is None:
            samples = {}
        if repopulate:
            cur = self.sample_cb.currentText()
            self.sample_cb.blockSignals(True)
            self.sample_cb.clear()
            self.sample_cb.addItems(list(samples.keys()))
            if cur in samples:
                self.sample_cb.setCurrentText(cur)
            self.sample_cb.blockSignals(False)
            self.node.config.setdefault(
                'active_sample',
                self.sample_cb.currentText() or None)
        self.canvas_widget.render(samples, self.node.config)


# ─────────────────────────────────────────────────────────────────────────
# Plot node  (mirror of ElementCompositionPlotNode)
# ─────────────────────────────────────────────────────────────────────────

class CompositionWheelPlotNode(QObject):
    position_changed      = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        super().__init__()
        self.title           = 'Composition Wheel'
        self.node_type       = 'composition_wheel_plot'
        self.parent_window   = parent_window
        self.position        = None
        self._has_input      = True
        self._has_output     = False
        self.input_channels  = ['input']
        self.output_channels = []

        self.config = {
            'wheel_mode':        WHEEL_MODES[0],
            'data_type_display': 'Counts',
            'angle_mode':        ANGLE_MODES[0],
            'radius_mode':       'Mass',
            'ratio_a':           None,
            'ratio_b':           None,
            'label_mode':        'Symbol',
            'legend_show':       True,
            'active_sample':     None,
            'sample_colors':     {},
            'sample_name_mappings': {},
            'font_family':       'DejaVu Sans',
            'font_size':         10,
            'font_color':        '#000000',
            'bg_color':          '#FFFFFF',
            'export_format':     'svg',
            'export_dpi':        300,
        }
        self.input_data = None

    # ── canvas-workflow API ─────────────────────────────────
    def set_position(self, pos):
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        CompositionWheelDisplayDialog(self, parent_window).exec()
        return True

    def process_data(self, input_data):
        if not input_data:
            return
        self.input_data = input_data
        self.configuration_changed.emit()

    # ── data extraction ─────────────────────────────────────
    def _data_key(self):
        return DATA_KEY_MAP.get(self.config.get('data_type_display', 'Counts'),
                                'elements')

    def available_elements(self) -> list:
        df_map = self._matrices()
        cols = set()
        for df in df_map.values():
            if df is not None:
                cols.update(df.columns)
        return sort_elements_by_mass(list(cols))

    def _matrices(self) -> dict:
        """Return {sample_name: particles×elements DataFrame}."""
        if not self.input_data:
            return {}
        dk = self._data_key()
        t = self.input_data.get('type')
        if t == 'sample_data':
            name = self.input_data.get('sample_name', 'Sample')
            df = build_element_matrix(
                self.input_data.get('particle_data', []), dk)
            return {name: df}
        if t == 'multiple_sample_data':
            particles = self.input_data.get('particle_data', [])
            names = self.input_data.get('sample_names', [])
            out = {}
            for n in names:
                subset = [p for p in particles if p.get('source_sample') == n]
                out[n] = build_element_matrix(subset, dk)
            return out
        return {}

    def extract_plot_data(self):
        """Return {sample_name: wheel-coord dict} or None."""
        mats = self._matrices()
        if not mats:
            return None
        return {n: compute_wheel_xy(df, self.config)
                for n, df in mats.items() if df is not None}