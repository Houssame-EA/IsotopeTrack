"""
Correlation-Matrix Plot Node – pairwise Pearson-r heat-maps.

Single sample  → one matrix.
Multi-sample   → side-by-side matrices (like Male / Female comparison).

Uses PyQtGraph ImageItem for the colour-mapped grid and shared_plot_utils
for fonts / download.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QDoubleSpinBox, QCheckBox, QGroupBox, QColorDialog,
    QPushButton, QWidget, QMenu, QDialogButtonBox, QScrollArea,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsSimpleTextItem,
    QGraphicsLineItem, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QObject, QRectF, QPointF
from PySide6.QtGui import (
    QColor, QPen, QBrush, QFont, QPainter, QLinearGradient,
    QPixmap, QImage,
)
import pyqtgraph as pg
import numpy as np
import math
from scipy.stats import pearsonr

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS,
    get_font_config, make_qfont, apply_font_to_pyqtgraph, set_axis_labels,
    FontSettingsGroup, get_sample_color, get_display_name,
    download_pyqtgraph_figure,
)
from results.utils_sort import sort_elements_by_mass, sort_element_dict_by_mass


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

MATRIX_COLOR_MAPS = [
    'RdBu_r (Red–Blue)',
    'coolwarm',
    'seismic',
    'BrBG',
    'PiYG',
    'PRGn',
]

MATRIX_DISPLAY_MODES = [
    'Side by Side',
    'Individual Subplots',
    'Difference Matrix',
]

DEFAULT_CONFIG = {
    'data_type_display': 'Counts',
    'min_particles': 5,
    'r_threshold': 0.0,
    'show_values': False,
    'show_diagonal': True,
    'colormap': 'RdBu_r (Red–Blue)',
    'display_mode': 'Side by Side',
    'cell_size': 18,
    'font_family': 'Times New Roman',
    'font_size': 18,
    'font_bold': False,
    'font_italic': False,
    'font_color': '#000000',
    'dark_theme': True,
    'sample_colors': {},
    'sample_name_mappings': {},
}


# ── Helpers ────────────────────────────────────────────────────────────

def _is_multi(input_data):
    return input_data and input_data.get('type') == 'multiple_sample_data'


def _available_elements(input_data):
    if not input_data:
        return []
    sel = input_data.get('selected_isotopes', [])
    if sel:
        return sort_elements_by_mass([i['label'] for i in sel])
    return []


def _compute_correlation_matrix(particles, elements, data_key):
    """Build NxN Pearson-r matrix from particle data."""
    n = len(elements)
    if n < 2:
        return None, None

    # Build value vectors per element
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
            # Only use particles where both are > 0
            mask = (vi > 0) & (vj > 0)
            if mask.sum() >= 5:
                try:
                    r, p = pearsonr(vi[mask], vj[mask])
                    mat[i, j] = r
                    p_mat[i, j] = p
                except Exception:
                    pass
    return mat, p_mat


def _r_to_color(r, dark=True):
    """Map correlation r ∈ [-1,1] to QColor (red=positive, blue=negative)."""
    if np.isnan(r):
        return QColor(40, 40, 50) if dark else QColor(220, 220, 220)
    r = max(-1, min(1, r))
    if r >= 0:
        # White → Red
        t = r
        if dark:
            return QColor(
                int(60 + 195 * t),    # R
                int(60 - 20 * t),     # G
                int(70 - 40 * t),     # B
            )
        else:
            return QColor(
                255,
                int(255 * (1 - t)),
                int(255 * (1 - t)),
            )
    else:
        t = -r
        if dark:
            return QColor(
                int(60 - 20 * t),     # R
                int(60 + 50 * t),     # G
                int(70 + 185 * t),    # B
            )
        else:
            return QColor(
                int(255 * (1 - t)),
                int(255 * (1 - t)),
                255,
            )


def _matrix_stats(mat):
    """Return summary statistics string."""
    valid = mat[~np.isnan(mat)]
    # Exclude diagonal (r=1)
    n = mat.shape[0]
    off_diag = []
    for i in range(n):
        for j in range(n):
            if i != j and not np.isnan(mat[i, j]):
                off_diag.append(mat[i, j])
    if not off_diag:
        return "No valid correlations"
    arr = np.array(off_diag)
    mean_abs = np.mean(np.abs(arr))
    pct_high = np.mean(np.abs(arr) > 0.7) * 100
    return f"mean|r|={mean_abs:.3f} · {pct_high:.0f}% pairs >0.7"


# ── Settings Dialog ────────────────────────────────────────────────────

class MatrixSettingsDialog(QDialog):
    def __init__(self, cfg, input_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Correlation Matrix Settings")
        self.setMinimumWidth(460)
        self._cfg = dict(cfg)
        self._input_data = input_data
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        scroll.setWidget(inner)
        root.addWidget(scroll)

        # Data type
        g1 = QGroupBox("Data")
        f1 = QFormLayout(g1)
        self.dtype_combo = QComboBox()
        self.dtype_combo.addItems(MATRIX_DATA_TYPES)
        self.dtype_combo.setCurrentText(self._cfg.get('data_type_display', 'Counts'))
        f1.addRow("Data Type:", self.dtype_combo)

        self.min_part = QDoubleSpinBox()
        self.min_part.setRange(2, 1000)
        self.min_part.setDecimals(0)
        self.min_part.setValue(self._cfg.get('min_particles', 5))
        f1.addRow("Min Particles:", self.min_part)
        lay.addWidget(g1)

        # Display
        g2 = QGroupBox("Display")
        f2 = QFormLayout(g2)
        self.show_vals = QCheckBox()
        self.show_vals.setChecked(self._cfg.get('show_values', False))
        f2.addRow("Show r Values:", self.show_vals)

        self.show_diag = QCheckBox()
        self.show_diag.setChecked(self._cfg.get('show_diagonal', True))
        f2.addRow("Show Diagonal:", self.show_diag)

        self.dark_cb = QCheckBox()
        self.dark_cb.setChecked(self._cfg.get('dark_theme', True))
        f2.addRow("Dark Theme:", self.dark_cb)

        self.cell_spin = QDoubleSpinBox()
        self.cell_spin.setRange(8, 50)
        self.cell_spin.setDecimals(0)
        self.cell_spin.setValue(self._cfg.get('cell_size', 18))
        f2.addRow("Cell Size:", self.cell_spin)

        self.thresh_spin = QDoubleSpinBox()
        self.thresh_spin.setRange(0.0, 0.99)
        self.thresh_spin.setDecimals(2)
        self.thresh_spin.setValue(self._cfg.get('r_threshold', 0.0))
        f2.addRow("|r| Threshold:", self.thresh_spin)
        lay.addWidget(g2)

        # Multi-sample mode
        if _is_multi(self._input_data):
            g3 = QGroupBox("Multi-Sample Display")
            f3 = QFormLayout(g3)
            self.mode_combo = QComboBox()
            self.mode_combo.addItems(MATRIX_DISPLAY_MODES)
            self.mode_combo.setCurrentText(
                self._cfg.get('display_mode', MATRIX_DISPLAY_MODES[0]))
            f3.addRow("Display Mode:", self.mode_combo)
            lay.addWidget(g3)

        # Font
        self._font_grp = FontSettingsGroup(self._cfg)
        lay.addWidget(self._font_grp.build())

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def collect(self):
        d = {
            'data_type_display': self.dtype_combo.currentText(),
            'min_particles': int(self.min_part.value()),
            'show_values': self.show_vals.isChecked(),
            'show_diagonal': self.show_diag.isChecked(),
            'dark_theme': self.dark_cb.isChecked(),
            'cell_size': int(self.cell_spin.value()),
            'r_threshold': self.thresh_spin.value(),
        }
        d.update(self._font_grp.collect())
        if hasattr(self, 'mode_combo'):
            d['display_mode'] = self.mode_combo.currentText()
        return d


# ── Custom Matrix Widget (QPainter-based for pixel control) ───────────

class MatrixWidget(QWidget):
    """Draws a single correlation matrix as a color-coded grid."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mat = None
        self.elements = []
        self.cfg = {}
        self.title = ""
        self.stats_text = ""
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(self, mat, elements, cfg, title="", stats=""):
        self.mat = mat
        self.elements = elements
        self.cfg = cfg
        self.title = title
        self.stats_text = stats
        self.update()

    def paintEvent(self, event):
        if self.mat is None or len(self.elements) == 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        dark = self.cfg.get('dark_theme', True)
        bg = QColor(30, 37, 55) if dark else QColor(255, 255, 255)
        painter.fillRect(self.rect(), bg)

        n = len(self.elements)
        cs = self.cfg.get('cell_size', 18)
        threshold = self.cfg.get('r_threshold', 0.0)
        show_vals = self.cfg.get('show_values', False)
        show_diag = self.cfg.get('show_diagonal', True)

        # Compute layout
        label_w = 30
        top_label_h = 40
        title_h = 50 if self.title else 0
        stats_h = 25 if self.stats_text else 0

        grid_w = n * cs
        grid_h = n * cs
        total_w = label_w + grid_w + 10
        total_h = title_h + stats_h + top_label_h + grid_h + 10

        # Center in widget
        ox = max(0, (self.width() - total_w) // 2)
        oy = max(0, (self.height() - total_h) // 2)

        # Title
        if self.title:
            title_color = QColor('#60A5FA') if dark else QColor('#2563EB')
            painter.setPen(title_color)
            painter.setFont(QFont(self.cfg.get('font_family', 'Segoe UI'), 14, QFont.Bold))
            painter.drawText(
                QRectF(ox, oy, total_w, title_h),
                Qt.AlignHCenter | Qt.AlignVCenter, self.title)
            oy += title_h

        # Stats
        if self.stats_text:
            stats_color = QColor('#94A3B8') if dark else QColor('#6B7280')
            painter.setPen(stats_color)
            painter.setFont(QFont(self.cfg.get('font_family', 'Segoe UI'), 9))
            painter.drawText(
                QRectF(ox, oy, total_w, stats_h),
                Qt.AlignHCenter | Qt.AlignVCenter, self.stats_text)
            oy += stats_h

        gx = ox + label_w
        gy = oy + top_label_h

        # Column labels (top, rotated)
        txt_color = QColor('#CBD5E1') if dark else QColor('#1F2937')
        painter.setPen(txt_color)
        label_font = QFont(self.cfg.get('font_family', 'Segoe UI'), 7)
        painter.setFont(label_font)
        for j, el in enumerate(self.elements):
            cx = gx + j * cs + cs / 2
            painter.save()
            painter.translate(cx, gy - 4)
            painter.rotate(-45)
            painter.drawText(0, 0, el)
            painter.restore()

        # Row labels (left)
        for i, el in enumerate(self.elements):
            cy = gy + i * cs + cs / 2
            painter.drawText(
                QRectF(ox, cy - cs / 2, label_w - 4, cs),
                Qt.AlignRight | Qt.AlignVCenter, el)

        # Cells
        val_font = QFont(self.cfg.get('font_family', 'Segoe UI'), max(5, cs // 3))
        for i in range(n):
            for j in range(n):
                x = gx + j * cs
                y = gy + i * cs
                r = self.mat[i, j]

                if i == j and not show_diag:
                    c = QColor(50, 55, 70) if dark else QColor(230, 230, 230)
                    painter.fillRect(QRectF(x, y, cs, cs), c)
                    continue

                if np.isnan(r):
                    c = QColor(40, 40, 50) if dark else QColor(230, 230, 230)
                elif abs(r) < threshold and i != j:
                    c = QColor(40, 45, 55) if dark else QColor(240, 240, 240)
                else:
                    c = _r_to_color(r, dark)

                painter.fillRect(QRectF(x, y, cs, cs), c)

                # Grid lines
                grid_color = QColor(25, 30, 42) if dark else QColor(200, 200, 200)
                painter.setPen(QPen(grid_color, 0.5))
                painter.drawRect(QRectF(x, y, cs, cs))

                # Value text
                if show_vals and not np.isnan(r) and cs >= 14:
                    painter.setPen(QColor(255, 255, 255) if dark else QColor(0, 0, 0))
                    painter.setFont(val_font)
                    painter.drawText(
                        QRectF(x, y, cs, cs),
                        Qt.AlignCenter, f"{r:.1f}")

        # Color bar
        bar_x = gx + grid_w + 15
        bar_w = 12
        bar_h = grid_h
        bar_y = gy
        for py in range(int(bar_h)):
            t = 1.0 - py / bar_h  # top=+1, bottom=-1
            r_val = t * 2 - 1
            c = _r_to_color(r_val, dark)
            painter.setPen(Qt.NoPen)
            painter.setBrush(c)
            painter.drawRect(QRectF(bar_x, bar_y + py, bar_w, 1))

        painter.setPen(txt_color)
        painter.setFont(QFont(self.cfg.get('font_family', 'Segoe UI'), 7))
        painter.drawText(QRectF(bar_x + bar_w + 2, bar_y - 4, 30, 12),
                         Qt.AlignLeft, "+1")
        painter.drawText(QRectF(bar_x + bar_w + 2, bar_y + bar_h - 8, 30, 12),
                         Qt.AlignLeft, "-1")
        painter.drawText(QRectF(bar_x + bar_w + 2, bar_y + bar_h / 2 - 6, 30, 12),
                         Qt.AlignLeft, " 0")

        painter.end()


# ── Display Dialog ─────────────────────────────────────────────────────

class CorrelationMatrixDisplayDialog(QDialog):
    """Main dialog – one or more MatrixWidgets laid out."""

    def __init__(self, node, parent_window=None):
        super().__init__(parent_window)
        self.node = node
        self.setWindowTitle("Correlation Matrix Analysis")
        self.setMinimumSize(1200, 800)

        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _build_ui(self):
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(6, 6, 6, 6)

        # Title / stats bar
        self._header = QLabel("")
        self._header.setStyleSheet(
            "color: #94A3B8; font-size: 12px; padding: 4px 8px;")
        self._root.addWidget(self._header)

        # Scroll area for matrices
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setContextMenuPolicy(Qt.CustomContextMenu)
        self._scroll.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._scroll, stretch=1)

        self._container = QWidget()
        self._container_lay = QHBoxLayout(self._container)
        self._container_lay.setContentsMargins(8, 8, 8, 8)
        self._scroll.setWidget(self._container)

        self._matrix_widgets = []

    def _ctx_menu(self, pos):
        cfg = self.node.config
        menu = QMenu(self)

        dm = menu.addMenu("Data Type")
        for dt in MATRIX_DATA_TYPES:
            a = dm.addAction(dt)
            a.setCheckable(True)
            a.setChecked(cfg.get('data_type_display') == dt)
            a.triggered.connect(lambda _, v=dt: self._set('data_type_display', v))

        tm = menu.addMenu("Quick Toggles")
        for key, label in [
            ('show_values', 'Show r Values'),
            ('show_diagonal', 'Show Diagonal'),
            ('dark_theme', 'Dark Theme'),
        ]:
            a = tm.addAction(label)
            a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        if _is_multi(self.node.input_data):
            mm = menu.addMenu("Display Mode")
            for m in MATRIX_DISPLAY_MODES:
                a = mm.addAction(m)
                a.setCheckable(True)
                a.setChecked(cfg.get('display_mode') == m)
                a.triggered.connect(lambda _, v=m: self._set('display_mode', v))

        menu.addSeparator()
        menu.addAction("Configure…").triggered.connect(self._open_settings)
        menu.addAction("Download Figure…").triggered.connect(self._download)
        menu.exec(self._scroll.mapToGlobal(pos))

    def _toggle(self, key):
        self.node.config[key] = not self.node.config.get(key, False)
        self._refresh()

    def _set(self, key, value):
        self.node.config[key] = value
        self._refresh()

    def _open_settings(self):
        dlg = MatrixSettingsDialog(self.node.config, self.node.input_data, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _download(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Correlation Matrix", "correlation_matrix.png",
            "PNG (*.png);;JPEG (*.jpg);;SVG (*.svg)")
        if path:
            pixmap = self._container.grab()
            pixmap.save(path)

    def _refresh(self):
        try:
            # Clear old widgets
            for w in self._matrix_widgets:
                self._container_lay.removeWidget(w)
                w.deleteLater()
            self._matrix_widgets.clear()

            data = self.node.extract_matrix_data()
            if not data:
                lbl = QLabel("No data available.\nConnect to a Sample Selector node.")
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setStyleSheet("color: gray; font-size: 14px;")
                self._container_lay.addWidget(lbl)
                self._matrix_widgets.append(lbl)
                self._header.setText("")
                return

            cfg = self.node.config
            dark = cfg.get('dark_theme', True)
            bg_style = "background: #1E293B;" if dark else "background: white;"
            self._container.setStyleSheet(bg_style)
            self._scroll.setStyleSheet(bg_style)

            multi = _is_multi(self.node.input_data)

            if multi:
                mode = cfg.get('display_mode', 'Side by Side')
                if mode == 'Difference Matrix' and len(data) == 2:
                    self._draw_difference(data, cfg)
                else:
                    self._draw_multi(data, cfg)
            else:
                self._draw_single(data, cfg)

        except Exception as e:
            print(f"Error refreshing correlation matrix: {e}")
            import traceback
            traceback.print_exc()

    def _draw_single(self, data, cfg):
        # data = {'elements': [...], 'matrix': np.array, 'n_particles': int}
        info = data
        if isinstance(data, dict) and 'matrix' in data:
            mat = data['matrix']
            elems = data['elements']
            n = data.get('n_particles', 0)
            stats = f"n={n} · " + _matrix_stats(mat)
            self._header.setText(
                f"SEX COMPARISON" if False else f"Correlation Matrix · {len(elems)} elements · {n} particles")

            w = MatrixWidget()
            w.set_data(mat, elems, cfg, title="", stats=stats)
            w.setMinimumSize(
                len(elems) * cfg.get('cell_size', 18) + 120,
                len(elems) * cfg.get('cell_size', 18) + 140)
            self._container_lay.addWidget(w)
            self._matrix_widgets.append(w)

    def _draw_multi(self, data, cfg):
        """Side-by-side matrices per sample."""
        # data = {sample_name: {'elements': [...], 'matrix': ..., 'n_particles': int}}
        names = list(data.keys())
        self._header.setText(f"SEX COMPARISON" if False else
                             f"Correlation Matrices · {len(names)} groups")

        for sn in names:
            info = data[sn]
            mat = info['matrix']
            elems = info['elements']
            n = info.get('n_particles', 0)
            stats = f"n={n} · " + _matrix_stats(mat)
            dn = get_display_name(sn, cfg)

            w = MatrixWidget()
            w.set_data(mat, elems, cfg, title=dn, stats=stats)
            w.setMinimumSize(
                len(elems) * cfg.get('cell_size', 18) + 120,
                len(elems) * cfg.get('cell_size', 18) + 180)
            self._container_lay.addWidget(w)
            self._matrix_widgets.append(w)

    def _draw_difference(self, data, cfg):
        """Difference matrix between first two samples."""
        names = list(data.keys())
        if len(names) < 2:
            self._draw_multi(data, cfg)
            return

        info1 = data[names[0]]
        info2 = data[names[1]]

        # Common elements
        common = [e for e in info1['elements'] if e in info2['elements']]
        if not common:
            self._draw_multi(data, cfg)
            return

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

        stats = f"Δr = {names[0]} − {names[1]} · " + _matrix_stats(diff)
        w = MatrixWidget()
        w.set_data(diff, common, cfg, title=f"Difference: {names[0]} − {names[1]}", stats=stats)
        w.setMinimumSize(
            n * cfg.get('cell_size', 18) + 120,
            n * cfg.get('cell_size', 18) + 180)
        self._container_lay.addWidget(w)
        self._matrix_widgets.append(w)


# ── Node ───────────────────────────────────────────────────────────────

class CorrelationMatrixNode(QObject):
    position_changed = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        super().__init__()
        self.title = "Corr. Matrix"
        self.node_type = "correlation_matrix"
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
        dlg = CorrelationMatrixDisplayDialog(self, parent_window)
        dlg.exec()
        return True

    def process_data(self, input_data):
        if not input_data:
            return
        self.input_data = input_data
        self.configuration_changed.emit()

    def extract_matrix_data(self):
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
        sel = self.input_data.get('selected_isotopes', [])
        if sel:
            return sort_elements_by_mass([i['label'] for i in sel])
        # Fallback: gather from particles
        particles = self.input_data.get('particle_data', [])
        all_elems = set()
        for p in particles:
            all_elems.update(p.get('elements', {}).keys())
        return sort_elements_by_mass(list(all_elems))

    def _extract_single(self, data_key):
        particles = self.input_data.get('particle_data', [])
        if not particles:
            return None
        elements = self._get_elements()
        if len(elements) < 2:
            return None
        mat, p_mat = _compute_correlation_matrix(particles, elements, data_key)
        if mat is None:
            return None
        return {
            'elements': elements,
            'matrix': mat,
            'p_matrix': p_mat,
            'n_particles': len(particles),
        }

    def _extract_multi(self, data_key):
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
                result[sn] = {
                    'elements': elements,
                    'matrix': mat,
                    'p_matrix': p_mat,
                    'n_particles': len(sp),
                }
        return result if result else None
