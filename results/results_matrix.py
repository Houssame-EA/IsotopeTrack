"""
Correlation-Matrix Plot Node – pairwise Pearson-r heat-maps.

Single sample  → one matrix.
Multi-sample   → side-by-side or individual subplot matrices.

Rendered with Matplotlib (MplDraggableCanvas) for full drag/export support.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QDoubleSpinBox, QCheckBox, QGroupBox,
    QPushButton, QWidget, QMenu, QDialogButtonBox, QScrollArea,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QCursor
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
import math
from scipy.stats import pearsonr

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS,
    get_font_config, apply_font_to_matplotlib,
    apply_font_to_colorbar_standalone,
    FontSettingsGroup, ExportSettingsGroup, MplDraggableCanvas,
    LABEL_MODES, format_element_label,
    get_display_name, download_matplotlib_figure,
)
from results.utils_sort import sort_elements_by_mass


# ── Constants ──────────────────────────────────────────────────────────

MATRIX_DATA_TYPES = [
    'Counts',
    'Element Mass (fg)',
    'Particle Mass (fg)',
    'Element Moles (fmol)',
    'Particle Moles (fmol)',
    'Element Diameter (nm)',
    'Particle Diameter (nm)',
]

MATRIX_DATA_KEY_MAP = {
    'Counts': 'elements',
    'Element Mass (fg)': 'element_mass_fg',
    'Particle Mass (fg)': 'particle_mass_fg',
    'Element Moles (fmol)': 'element_moles_fmol',
    'Particle Moles (fmol)': 'particle_moles_fmol',
    'Element Diameter (nm)': 'element_diameter_nm',
    'Particle Diameter (nm)': 'particle_diameter_nm',
}

MATRIX_COLORMAPS = [
    'RdBu_r', 'coolwarm', 'seismic', 'BrBG', 'PiYG', 'PRGn',
    'RdYlBu', 'Spectral', 'bwr',
]

MATRIX_DISPLAY_MODES = [
    'Side by Side',
    'Individual Subplots',
    'Difference Matrix',
]

DEFAULT_CONFIG = {
    'data_type_display':  'Counts',
    'min_particles':      5,
    'r_threshold':        0.0,
    'show_values':        True,
    'show_diagonal':      True,
    'colormap':           'RdBu_r',
    'display_mode':       'Side by Side',
    'font_family':        'Times New Roman',
    'font_size':          10,
    'font_bold':          False,
    'font_italic':        False,
    'font_color':         '#000000',
    'sample_colors':      {},
    'sample_name_mappings': {},
    'label_mode':         'Symbol',
    'x_rotation':         0,
    'bg_color':           '#FFFFFF',
    'export_format':      'svg',
    'export_dpi':         300,
    'use_custom_figsize': False,
    'figsize_w':          14.0,
    'figsize_h':          8.0,
}


# ── Helpers ────────────────────────────────────────────────────────────

def _is_multi(input_data):
    """
    Args:
        input_data (Any): The input data.
    Returns:
        object: Result of the operation.
    """
    return input_data and input_data.get('type') == 'multiple_sample_data'


def _compute_correlation_matrix(particles, elements, data_key):
    """Build NxN Pearson-r matrix from particle data.
    Args:
        particles (Any): The particles.
        elements (Any): The elements.
        data_key (Any): The data key.
    Returns:
        tuple: Result of the operation.
    """
    n = len(elements)
    if n < 2:
        return None, None
    vectors = {el: [] for el in elements}
    for p in particles:
        d = p.get(data_key, {})
        vals = {}
        for el in elements:
            v = d.get(el, 0)
            if data_key != 'elements':
                if v <= 0 or (isinstance(v, float) and np.isnan(v)):
                    v = 0
            vals[el] = v
        for el in elements:
            vectors[el].append(vals[el])

    mat = np.full((n, n), np.nan)
    p_mat = np.full((n, n), np.nan)
    for i in range(n):
        for j in range(n):
            vi = np.array(vectors[elements[i]], dtype=float)
            vj = np.array(vectors[elements[j]], dtype=float)
            mask = (vi > 0) & (vj > 0)
            if mask.sum() >= 5:
                try:
                    r, p = pearsonr(vi[mask], vj[mask])
                    mat[i, j] = r
                    p_mat[i, j] = p
                except Exception:
                    pass
    return mat, p_mat


def _matrix_stats(mat):
    """
    Args:
        mat (Any): The mat.
    Returns:
        object: Result of the operation.
    """
    n = mat.shape[0]
    off_diag = [mat[i, j] for i in range(n) for j in range(n)
                if i != j and not np.isnan(mat[i, j])]
    if not off_diag:
        return "No valid correlations"
    arr = np.array(off_diag)
    return f"mean|r|={np.mean(np.abs(arr)):.3f}  ·  {np.mean(np.abs(arr) > 0.7)*100:.0f}% pairs >0.7"


# ── Settings Dialog ────────────────────────────────────────────────────

class MatrixSettingsDialog(QDialog):
    def __init__(self, cfg, input_data, parent=None):
        """
        Args:
            cfg (Any): The cfg.
            input_data (Any): The input data.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("Correlation Matrix Settings")
        self.setMinimumWidth(480)
        self._cfg = dict(cfg)
        self._input_data = input_data
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); lay = QVBoxLayout(inner)
        scroll.setWidget(inner); root.addWidget(scroll)

        g1 = QGroupBox("Data")
        f1 = QFormLayout(g1)
        self.dtype_combo = QComboBox()
        self.dtype_combo.addItems(MATRIX_DATA_TYPES)
        self.dtype_combo.setCurrentText(self._cfg.get('data_type_display', 'Counts'))
        f1.addRow("Data Type:", self.dtype_combo)
        self.min_part = QDoubleSpinBox()
        self.min_part.setRange(2, 1000); self.min_part.setDecimals(0)
        self.min_part.setValue(self._cfg.get('min_particles', 5))
        f1.addRow("Min Particles:", self.min_part)
        self.thresh_spin = QDoubleSpinBox()
        self.thresh_spin.setRange(0.0, 0.99); self.thresh_spin.setDecimals(2)
        self.thresh_spin.setValue(self._cfg.get('r_threshold', 0.0))
        f1.addRow("|r| Threshold:", self.thresh_spin)
        lay.addWidget(g1)

        g2 = QGroupBox("Display")
        f2 = QFormLayout(g2)
        self.show_vals = QCheckBox()
        self.show_vals.setChecked(self._cfg.get('show_values', True))
        f2.addRow("Show r Values:", self.show_vals)
        self.show_diag = QCheckBox()
        self.show_diag.setChecked(self._cfg.get('show_diagonal', True))
        f2.addRow("Show Diagonal:", self.show_diag)
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(MATRIX_COLORMAPS)
        raw_cmap = self._cfg.get('colormap', 'RdBu_r').split()[0]
        self.cmap_combo.setCurrentText(raw_cmap if raw_cmap in MATRIX_COLORMAPS else 'RdBu_r')
        f2.addRow("Colormap:", self.cmap_combo)
        self.label_mode_combo = QComboBox()
        self.label_mode_combo.addItems(LABEL_MODES)
        self.label_mode_combo.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
        f2.addRow("Label Mode:", self.label_mode_combo)
        from PySide6.QtWidgets import QSpinBox as _QSpin
        self.x_rotation_spin = _QSpin()
        self.x_rotation_spin.setRange(0, 90); self.x_rotation_spin.setSuffix("°")
        self.x_rotation_spin.setValue(self._cfg.get('x_rotation', 0))
        f2.addRow("X Label Rotation:", self.x_rotation_spin)
        lay.addWidget(g2)

        if _is_multi(self._input_data):
            g3 = QGroupBox("Multi-Sample Display")
            f3 = QFormLayout(g3)
            self.mode_combo = QComboBox()
            self.mode_combo.addItems(MATRIX_DISPLAY_MODES)
            self.mode_combo.setCurrentText(
                self._cfg.get('display_mode', MATRIX_DISPLAY_MODES[0]))
            f3.addRow("Display Mode:", self.mode_combo)
            lay.addWidget(g3)

        self._font_grp = FontSettingsGroup(self._cfg)
        lay.addWidget(self._font_grp.build())

        self._export_grp = ExportSettingsGroup(self._cfg)
        lay.addWidget(self._export_grp.build())

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def collect(self):
        """
        Returns:
            object: Result of the operation.
        """
        d = {
            'data_type_display': self.dtype_combo.currentText(),
            'min_particles':     int(self.min_part.value()),
            'r_threshold':       self.thresh_spin.value(),
            'show_values':       self.show_vals.isChecked(),
            'show_diagonal':     self.show_diag.isChecked(),
            'colormap':          self.cmap_combo.currentText(),
            'label_mode':        self.label_mode_combo.currentText(),
            'x_rotation':        self.x_rotation_spin.value(),
        }
        d.update(self._font_grp.collect())
        d.update(self._export_grp.collect())
        if hasattr(self, 'mode_combo'):
            d['display_mode'] = self.mode_combo.currentText()
        return d


# ── Display Dialog ─────────────────────────────────────────────────────

class CorrelationMatrixDisplayDialog(QDialog):
    """Matplotlib-based correlation matrix dialog with drag support."""

    def __init__(self, node, parent_window=None):
        """
        Args:
            node (Any): Tree or graph node.
            parent_window (Any): The parent window.
        """
        super().__init__(parent_window)
        self.node = node
        self.setWindowTitle("Correlation Matrix Analysis")
        self.setMinimumSize(1100, 750)
        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        self._header = QLabel("")
        self._header.setStyleSheet("color:#94A3B8; font-size:12px; padding:4px 8px;")
        lay.addWidget(self._header)

        self.figure = Figure(figsize=(14, 8), dpi=120, tight_layout=True)
        self.canvas = MplDraggableCanvas(self.figure)
        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._ctx_menu)
        lay.addWidget(self.canvas, stretch=1)

        tb = QHBoxLayout(); tb.setContentsMargins(0, 2, 0, 0)
        btn_s = QPushButton("⚙  Settings"); btn_s.clicked.connect(self._open_settings)
        btn_r = QPushButton("↺  Reset Layout")
        btn_r.setToolTip("Reset subplot positions (or middle-click)")
        btn_r.clicked.connect(self._reset_layout)
        btn_e = QPushButton("⬆  Export…"); btn_e.clicked.connect(self._export_figure)
        tb.addWidget(btn_s); tb.addWidget(btn_r); tb.addStretch(); tb.addWidget(btn_e)
        lay.addLayout(tb)

    # ── Context menu ───────────────────────────────────────────────────

    def _ctx_menu(self, pos):
        """
        Args:
            pos (Any): Position point.
        """
        cfg = self.node.config
        menu = QMenu(self)

        dm = menu.addMenu("Data Type")
        for dt in MATRIX_DATA_TYPES:
            a = dm.addAction(dt); a.setCheckable(True)
            a.setChecked(cfg.get('data_type_display') == dt)
            a.triggered.connect(lambda _, v=dt: self._set('data_type_display', v))

        cm = menu.addMenu("Colormap")
        for c in MATRIX_COLORMAPS:
            a = cm.addAction(c); a.setCheckable(True)
            a.setChecked(cfg.get('colormap') == c)
            a.triggered.connect(lambda _, v=c: self._set('colormap', v))

        tm = menu.addMenu("Quick Toggles")
        for key, label in [('show_values', 'Show r Values'),
                            ('show_diagonal', 'Show Diagonal')]:
            a = tm.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        lm = menu.addMenu("Label Mode")
        for mode in LABEL_MODES:
            a = lm.addAction(mode); a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set('label_mode', v))

        rot_menu = menu.addMenu("X Label Rotation")
        cur_rot = cfg.get('x_rotation', 0)
        for rot in [0, 30, 45, 60, 90]:
            a = rot_menu.addAction(f"{rot}°"); a.setCheckable(True)
            a.setChecked(cur_rot == rot)
            a.triggered.connect(lambda _, r=rot: self._set('x_rotation', r))

        if _is_multi(self.node.input_data):
            mm = menu.addMenu("Display Mode")
            for m in MATRIX_DISPLAY_MODES:
                a = mm.addAction(m); a.setCheckable(True)
                a.setChecked(cfg.get('display_mode') == m)
                a.triggered.connect(lambda _, v=m: self._set('display_mode', v))

        menu.addSeparator()
        menu.addAction("↺  Reset Layout").triggered.connect(self._reset_layout)
        menu.addAction("⚙  Configure…").triggered.connect(self._open_settings)
        menu.addAction("💾 Download Figure…").triggered.connect(self._export_figure)
        menu.exec(QCursor.pos())

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

    def _reset_layout(self):
        self.canvas.reset_layout()

    def _export_figure(self):
        download_matplotlib_figure(self.figure, self, "correlation_matrix")

    def _open_settings(self):
        dlg = MatrixSettingsDialog(self.node.config, self.node.input_data, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    # ── Refresh / draw ─────────────────────────────────────────────────

    def _refresh(self):
        try:
            cfg = self.node.config
            if cfg.get('use_custom_figsize', False):
                self.figure.set_size_inches(cfg.get('figsize_w', 14.0),
                                            cfg.get('figsize_h', 8.0))
            self.figure.clear()
            self.figure.patch.set_facecolor(cfg.get('bg_color', '#FFFFFF'))

            data = self.node.extract_matrix_data()
            if not data:
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5, 'No data available\nConnect to a Sample Selector node.',
                        ha='center', va='center', transform=ax.transAxes,
                        fontsize=12, color='gray')
                ax.axis('off')
                self._header.setText("")
                self.canvas.draw()
                return

            multi = _is_multi(self.node.input_data)
            if multi:
                mode = cfg.get('display_mode', 'Side by Side')
                if mode == 'Difference Matrix' and len(data) == 2:
                    self._draw_difference(data, cfg)
                else:
                    self._draw_multi(data, cfg)
            else:
                self._draw_single(data, cfg)

            self.figure.tight_layout()
            self.canvas.draw()
            self.canvas.snapshot_positions()

        except Exception as e:
            print(f"Error refreshing correlation matrix: {e}")
            import traceback; traceback.print_exc()

    def _draw_single(self, data, cfg):
        """
        Args:
            data (Any): Input data.
            cfg (Any): The cfg.
        """
        mat = data['matrix']
        elems = data['elements']
        n = data.get('n_particles', 0)
        self._header.setText(
            f"Correlation Matrix · {len(elems)} elements · {n} particles · {_matrix_stats(mat)}")
        ax = self.figure.add_subplot(111)
        self._draw_matrix_ax(ax, mat, elems, cfg, title="")
        apply_font_to_matplotlib(ax, cfg)

    def _draw_multi(self, data, cfg):
        """
        Args:
            data (Any): Input data.
            cfg (Any): The cfg.
        """
        names = list(data.keys())
        n = len(names)
        cols = min(n, 3)
        rows = math.ceil(n / cols)
        self._header.setText(f"Correlation Matrices · {n} groups")
        for idx, sn in enumerate(names):
            info = data[sn]
            ax = self.figure.add_subplot(rows, cols, idx + 1)
            dn = get_display_name(sn, cfg)
            self._draw_matrix_ax(ax, info['matrix'], info['elements'], cfg,
                                 title=f"{dn}  (n={info.get('n_particles',0)})")
            apply_font_to_matplotlib(ax, cfg)

    def _draw_difference(self, data, cfg):
        """
        Args:
            data (Any): Input data.
            cfg (Any): The cfg.
        """
        names = list(data.keys())
        info1, info2 = data[names[0]], data[names[1]]
        common = [e for e in info1['elements'] if e in info2['elements']]
        if not common:
            self._draw_multi(data, cfg); return
        idx1 = {e: i for i, e in enumerate(info1['elements'])}
        idx2 = {e: i for i, e in enumerate(info2['elements'])}
        n = len(common)
        diff = np.full((n, n), np.nan)
        for i, ei in enumerate(common):
            for j, ej in enumerate(common):
                r1 = info1['matrix'][idx1[ei], idx1[ej]]
                r2 = info2['matrix'][idx2[ei], idx2[ej]]
                if not np.isnan(r1) and not np.isnan(r2):
                    diff[i, j] = r1 - r2
        self._header.setText(f"Δr = {names[0]} − {names[1]} · {_matrix_stats(diff)}")
        ax = self.figure.add_subplot(111)
        self._draw_matrix_ax(ax, diff, common, cfg,
                             title=f"Difference: {names[0]} − {names[1]}")
        apply_font_to_matplotlib(ax, cfg)

    def _draw_matrix_ax(self, ax, mat, elems, cfg, title=""):
        """Draw one correlation matrix onto ax using imshow.
        Args:
            ax (Any): The ax.
            mat (Any): The mat.
            elems (Any): The elems.
            cfg (Any): The cfg.
            title (Any): Window or dialog title.
        """
        n = len(elems)
        threshold = cfg.get('r_threshold', 0.0)
        show_diag = cfg.get('show_diagonal', True)
        show_vals = cfg.get('show_values', True)
        cmap      = cfg.get('colormap', 'RdBu_r').split()[0]
        label_mode = cfg.get('label_mode', 'Symbol')
        x_rotation = cfg.get('x_rotation', 0)
        fc        = get_font_config(cfg)

        plot_mat = mat.copy()
        for i in range(n):
            for j in range(n):
                if i != j and not np.isnan(plot_mat[i, j]):
                    if abs(plot_mat[i, j]) < threshold:
                        plot_mat[i, j] = np.nan
            if not show_diag:
                plot_mat[i, i] = np.nan

        im = ax.imshow(plot_mat, cmap=cmap, vmin=-1, vmax=1,
                       aspect='equal', interpolation='nearest')

        fmt_elems = [format_element_label(e, label_mode) for e in elems]

        ax.set_xticks(range(n))
        ax.set_xticklabels(fmt_elems, rotation=x_rotation,
                           ha='right' if x_rotation > 0 else 'center',
                           fontsize=fc['size'], color=fc['color'])
        ax.set_yticks(range(n))
        ax.set_yticklabels(fmt_elems, fontsize=fc['size'], color=fc['color'])

        if title:
            ax.set_title(title, fontsize=fc['size'] + 2,
                         fontweight='bold' if fc['bold'] else 'normal',
                         color=fc['color'], pad=10)

        if show_vals:
            for i in range(n):
                for j in range(n):
                    v = mat[i, j]
                    if not np.isnan(v):
                        tc = 'white' if abs(v) > 0.6 else 'black'
                        ax.text(j, i, f"{v:.2f}", ha='center', va='center',
                                fontsize=max(6, fc['size'] - 2), color=tc,
                                fontweight='bold' if fc['bold'] else 'normal')

        cbar = self.figure.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
        apply_font_to_colorbar_standalone(cbar, cfg, "Pearson r")

        ax.set_facecolor(cfg.get('bg_color', '#FFFFFF'))


# ── Node ───────────────────────────────────────────────────────────────

class CorrelationMatrixNode(QObject):
    position_changed      = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        """
        Args:
            parent_window (Any): The parent window.
        """
        super().__init__()
        self.title           = "Corr. Matrix"
        self.node_type       = "correlation_matrix"
        self.parent_window   = parent_window
        self.position        = None
        self._has_input      = True
        self._has_output     = False
        self.input_channels  = ["input"]
        self.output_channels = []
        self.config          = dict(DEFAULT_CONFIG)
        self.input_data      = None

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
        dlg = CorrelationMatrixDisplayDialog(self, parent_window)
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

    def extract_matrix_data(self):
        """
        Returns:
            None
        """
        if not self.input_data:
            return None
        data_key = MATRIX_DATA_KEY_MAP.get(
            self.config.get('data_type_display', 'Counts'), 'elements')
        itype = self.input_data.get('type')
        if itype == 'sample_data':
            return self._extract_single(data_key)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(data_key)
        return None

    def _get_elements(self):
        """
        Returns:
            object: Result of the operation.
        """
        sel = self.input_data.get('selected_isotopes', [])
        if sel:
            return sort_elements_by_mass([i['label'] for i in sel])
        particles = self.input_data.get('particle_data', [])
        all_elems = set()
        for p in particles:
            all_elems.update(p.get('elements', {}).keys())
        return sort_elements_by_mass(list(all_elems))

    def _extract_single(self, data_key):
        """
        Args:
            data_key (Any): The data key.
        Returns:
            dict: Result of the operation.
        """
        particles = self.input_data.get('particle_data', [])
        if not particles:
            return None
        elements = self._get_elements()
        if len(elements) < 2:
            return None
        mat, p_mat = _compute_correlation_matrix(particles, elements, data_key)
        if mat is None:
            return None
        return {'elements': elements, 'matrix': mat,
                'p_matrix': p_mat, 'n_particles': len(particles)}

    def _extract_multi(self, data_key):
        """
        Args:
            data_key (Any): The data key.
        Returns:
            object: Result of the operation.
        """
        particles = self.input_data.get('particle_data', [])
        names = self.input_data.get('sample_names', [])
        if not particles or not names:
            return None
        elements = self._get_elements()
        if len(elements) < 2:
            return None
        result = {}
        for sn in names:
            sp = [p for p in particles if p.get('source_sample') == sn]
            if len(sp) < self.config.get('min_particles', 5):
                continue
            mat, p_mat = _compute_correlation_matrix(sp, elements, data_key)
            if mat is not None:
                result[sn] = {'elements': elements, 'matrix': mat,
                              'p_matrix': p_mat, 'n_particles': len(sp)}
        return result if result else None