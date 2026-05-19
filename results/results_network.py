"""
Network / Chord Diagram Node – circular element correlation network.

Elements are arranged around a circle.  Edges represent significant
pairwise Pearson correlations.  Red = positive, Blue = negative.
Edge width ∝ |r|.

Rendered with Matplotlib (MplDraggableCanvas) for full drag/export support.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QDoubleSpinBox, QCheckBox, QGroupBox, QColorDialog,
    QPushButton, QWidget, QMenu, QDialogButtonBox, QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QCursor
from matplotlib.figure import Figure
from matplotlib.patches import Circle, FancyArrowPatch
import matplotlib.patheffects as pe
import numpy as np
import math
from scipy.stats import pearsonr

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS,
    get_font_config,
    FontSettingsGroup, ExportSettingsGroup, MplDraggableCanvas,
    LABEL_MODES, format_element_label,
    get_display_name, download_matplotlib_figure,
)
from results.utils_sort import sort_elements_by_mass


# ── Constants ──────────────────────────────────────────────────────────

NET_DATA_TYPES = [
    'Counts',
    'Element Mass (fg)',
    'Particle Mass (fg)',
    'Element Moles (fmol)',
    'Particle Moles (fmol)',
    'Element Diameter (nm)',
    'Particle Diameter (nm)',
]

NET_DATA_KEY_MAP = {
    'Counts': 'elements',
    'Element Mass (fg)': 'element_mass_fg',
    'Particle Mass (fg)': 'particle_mass_fg',
    'Element Moles (fmol)': 'element_moles_fmol',
    'Particle Moles (fmol)': 'particle_moles_fmol',
    'Element Diameter (nm)': 'element_diameter_nm',
    'Particle Diameter (nm)': 'particle_diameter_nm',
}

DEFAULT_CONFIG = {
    'data_type_display':    'Counts',
    'r_threshold':          0.3,
    'min_particles':        5,
    'positive_color':       '#EF4444',
    'negative_color':       '#3B82F6',
    'node_color':           '#14B8A6',
    'edge_alpha':           0.6,
    'edge_width_factor':    3.0,
    'node_radius':          0.06,
    'show_labels':          True,
    'show_edge_count':      True,
    'layout_radius_factor': 0.38,
    'label_mode':           'Symbol',
    'font_family':          'Times New Roman',
    'font_size':            10,
    'font_bold':            False,
    'font_italic':          False,
    'font_color':           '#000000',
    'sample_name_mappings': {},
    'bg_color':             '#FFFFFF',
    'export_format':        'svg',
    'export_dpi':           300,
    'use_custom_figsize':   False,
    'figsize_w':            14.0,
    'figsize_h':            8.0,
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


def _compute_edges(particles, elements, data_key, r_threshold, min_n):
    """Return list of (i, j, r) where |r| >= threshold.
    Args:
        particles (Any): The particles.
        elements (Any): The elements.
        data_key (Any): The data key.
        r_threshold (Any): The r threshold.
        min_n (Any): The min n.
    Returns:
        object: Result of the operation.
    """
    n = len(elements)
    vectors = {el: [] for el in elements}
    for p in particles:
        d = p.get(data_key, {})
        for el in elements:
            v = d.get(el, 0)
            if data_key != 'elements':
                if v <= 0 or (isinstance(v, float) and np.isnan(v)):
                    v = 0
            vectors[el].append(v)
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            vi = np.array(vectors[elements[i]], dtype=float)
            vj = np.array(vectors[elements[j]], dtype=float)
            mask = (vi > 0) & (vj > 0)
            if mask.sum() >= min_n:
                try:
                    r, p = pearsonr(vi[mask], vj[mask])
                    if abs(r) >= r_threshold:
                        edges.append((i, j, r))
                except Exception:
                    pass
    return edges


# ── Settings Dialog ────────────────────────────────────────────────────

class _ColorBtn(QPushButton):
    def __init__(self, color='#FFFFFF', parent=None):
        """
        Args:
            color (Any): Colour value.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setFixedSize(34, 22)
        self._color = color
        self._apply()

    def _apply(self):
        self.setStyleSheet(
            f'background-color:{self._color};border:1px solid #666;border-radius:2px;')

    def color(self):
        """
        Returns:
            object: Result of the operation.
        """
        return self._color

    def mousePressEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        if event.button() == Qt.LeftButton:
            c = QColorDialog.getColor(QColor(self._color), self)
            if c.isValid():
                self._color = c.name()
                self._apply()
        super().mousePressEvent(event)


class NetworkSettingsDialog(QDialog):
    def __init__(self, cfg, input_data, parent=None):
        """
        Args:
            cfg (Any): The cfg.
            input_data (Any): The input data.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("Network Diagram Settings")
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
        self.dtype_combo.addItems(NET_DATA_TYPES)
        self.dtype_combo.setCurrentText(self._cfg.get('data_type_display', 'Counts'))
        f1.addRow("Data Type:", self.dtype_combo)
        self.thresh_spin = QDoubleSpinBox()
        self.thresh_spin.setRange(0.0, 0.99); self.thresh_spin.setDecimals(2)
        self.thresh_spin.setValue(self._cfg.get('r_threshold', 0.3))
        f1.addRow("|r| Threshold:", self.thresh_spin)
        self.min_part = QDoubleSpinBox()
        self.min_part.setRange(2, 1000); self.min_part.setDecimals(0)
        self.min_part.setValue(self._cfg.get('min_particles', 5))
        f1.addRow("Min Particles:", self.min_part)
        lay.addWidget(g1)

        g2 = QGroupBox("Colors")
        f2 = QFormLayout(g2)
        self._pos_btn  = _ColorBtn(self._cfg.get('positive_color', '#EF4444'))
        self._neg_btn  = _ColorBtn(self._cfg.get('negative_color', '#3B82F6'))
        self._node_btn = _ColorBtn(self._cfg.get('node_color', '#14B8A6'))
        f2.addRow("Positive (r>0):", self._pos_btn)
        f2.addRow("Negative (r<0):", self._neg_btn)
        f2.addRow("Node Color:", self._node_btn)
        lay.addWidget(g2)

        g3 = QGroupBox("Display")
        f3 = QFormLayout(g3)
        self.alpha_spin = QDoubleSpinBox()
        self.alpha_spin.setRange(0.1, 1.0); self.alpha_spin.setDecimals(1)
        self.alpha_spin.setValue(self._cfg.get('edge_alpha', 0.6))
        f3.addRow("Edge Transparency:", self.alpha_spin)
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.5, 10.0); self.width_spin.setDecimals(1)
        self.width_spin.setValue(self._cfg.get('edge_width_factor', 3.0))
        f3.addRow("Edge Width Factor:", self.width_spin)
        self.node_r = QDoubleSpinBox()
        self.node_r.setRange(0.02, 0.15); self.node_r.setDecimals(3)
        self.node_r.setValue(self._cfg.get('node_radius', 0.06))
        f3.addRow("Node Radius:", self.node_r)
        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(0.15, 0.48); self.radius_spin.setDecimals(2)
        self.radius_spin.setValue(self._cfg.get('layout_radius_factor', 0.38))
        f3.addRow("Layout Radius:", self.radius_spin)
        self.labels_cb = QCheckBox()
        self.labels_cb.setChecked(self._cfg.get('show_labels', True))
        f3.addRow("Show Labels:", self.labels_cb)
        self.edge_count_cb = QCheckBox()
        self.edge_count_cb.setChecked(self._cfg.get('show_edge_count', True))
        f3.addRow("Show Edge Count:", self.edge_count_cb)
        self.label_mode_combo = QComboBox()
        self.label_mode_combo.addItems(LABEL_MODES)
        self.label_mode_combo.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
        f3.addRow("Label Mode:", self.label_mode_combo)
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
            'data_type_display':    self.dtype_combo.currentText(),
            'r_threshold':          self.thresh_spin.value(),
            'min_particles':        int(self.min_part.value()),
            'positive_color':       self._pos_btn.color(),
            'negative_color':       self._neg_btn.color(),
            'node_color':           self._node_btn.color(),
            'edge_alpha':           self.alpha_spin.value(),
            'edge_width_factor':    self.width_spin.value(),
            'node_radius':          self.node_r.value(),
            'layout_radius_factor': self.radius_spin.value(),
            'show_labels':          self.labels_cb.isChecked(),
            'show_edge_count':      self.edge_count_cb.isChecked(),
            'label_mode':           self.label_mode_combo.currentText(),
        }
        d.update(self._font_grp.collect())
        d.update(self._export_grp.collect())
        return d


# ── Display Dialog ─────────────────────────────────────────────────────

class NetworkDisplayDialog(QDialog):
    def __init__(self, node, parent_window=None):
        """
        Args:
            node (Any): Tree or graph node.
            parent_window (Any): The parent window.
        """
        super().__init__(parent_window)
        self.node = node
        self.setWindowTitle("Element Correlation Network")
        self.setMinimumSize(1000, 700)
        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        self._info = QLabel("")
        self._info.setStyleSheet("color:#94A3B8; font-size:11px; padding:2px 6px;")
        lay.addWidget(self._info)

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
        for dt in NET_DATA_TYPES:
            a = dm.addAction(dt); a.setCheckable(True)
            a.setChecked(cfg.get('data_type_display') == dt)
            a.triggered.connect(lambda _, v=dt: self._set('data_type_display', v))

        tm = menu.addMenu("Quick Toggles")
        for key, label in [('show_labels', 'Show Labels'),
                            ('show_edge_count', 'Show Edge Count')]:
            a = tm.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        lm = menu.addMenu("Label Mode")
        for mode in LABEL_MODES:
            a = lm.addAction(mode); a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set('label_mode', v))

        pm = menu.addMenu("|r| Threshold")
        for t in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
            a = pm.addAction(f"≥ {t}"); a.setCheckable(True)
            a.setChecked(abs(cfg.get('r_threshold', 0.3) - t) < 0.01)
            a.triggered.connect(lambda _, v=t: self._set('r_threshold', v))

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
        download_matplotlib_figure(self.figure, self, "network_diagram")

    def _open_settings(self):
        dlg = NetworkSettingsDialog(self.node.config, self.node.input_data, self)
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

            data = self.node.extract_network_data()
            if not data:
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5, 'No data available\nConnect to a Sample Selector node.',
                        ha='center', va='center', transform=ax.transAxes,
                        fontsize=12, color='gray')
                ax.axis('off')
                self._info.setText("")
                self.canvas.draw()
                return

            if isinstance(data, dict) and 'elements' in data:
                ax = self.figure.add_subplot(111)
                self._draw_network(ax, data, cfg)
                self._info.setText(
                    f"{len(data['elements'])} elements · "
                    f"{len(data['edges'])} edges · "
                    f"{data.get('n_particles', 0)} particles")
            else:
                names = list(data.keys())
                n = len(names)
                cols = min(n, 3)
                rows = math.ceil(n / cols)
                total_edges = 0
                for idx, sn in enumerate(names):
                    nd = data[sn]
                    ax = self.figure.add_subplot(rows, cols, idx + 1)
                    self._draw_network(ax, nd, cfg)
                    total_edges += len(nd['edges'])
                self._info.setText(f"{n} groups · {total_edges} total edges")

            self.figure.tight_layout()
            self.canvas.draw()
            self.canvas.snapshot_positions()

        except Exception as e:
            print(f"Error refreshing network diagram: {e}")
            import traceback; traceback.print_exc()

    def _draw_network(self, ax, net_data, cfg):
        """Draw one circular correlation network onto ax.
        Args:
            ax (Any): The ax.
            net_data (Any): The net data.
            cfg (Any): The cfg.
        """
        elements = net_data['elements']
        edges    = net_data['edges']
        title    = net_data.get('title', '')
        n        = len(elements)

        bg       = cfg.get('bg_color', '#FFFFFF')
        pos_c    = cfg.get('positive_color', '#EF4444')
        neg_c    = cfg.get('negative_color', '#3B82F6')
        node_c   = cfg.get('node_color', '#14B8A6')
        edge_a   = cfg.get('edge_alpha', 0.6)
        edge_wf  = cfg.get('edge_width_factor', 3.0)
        node_r   = cfg.get('node_radius', 0.06)
        R        = cfg.get('layout_radius_factor', 0.38)
        label_mode = cfg.get('label_mode', 'Symbol')
        fc       = get_font_config(cfg)

        fmt_labels = [format_element_label(el, label_mode) for el in elements]

        ax.set_facecolor(bg)
        ax.set_xlim(-0.55, 0.55)
        ax.set_ylim(-0.55, 0.55)
        ax.set_aspect('equal')
        ax.axis('off')

        if n < 2:
            ax.text(0, 0, 'Insufficient elements', ha='center', va='center',
                    color='gray', fontsize=fc['size'])
            return

        positions = []
        for i in range(n):
            angle = 2 * math.pi * i / n - math.pi / 2
            positions.append((R * math.cos(angle), R * math.sin(angle)))

        mean_r = np.mean([abs(e[2]) for e in edges]) if edges else 0.0
        for (i, j, r) in edges:
            xi, yi = positions[i]
            xj, yj = positions[j]
            color = pos_c if r > 0 else neg_c
            lw = max(0.5, abs(r) * edge_wf)
            ax.plot([xi, xj], [yi, yj], color=color, lw=lw,
                    alpha=edge_a, solid_capstyle='round', zorder=1)

        for i, el in enumerate(elements):
            px, py = positions[i]
            fmt_el = fmt_labels[i]

            circle = Circle((px, py), node_r, color=node_c, zorder=3,
                             linewidth=1.5, edgecolor='white')
            ax.add_patch(circle)

            ax.text(px, py, fmt_el, ha='center', va='center',
                    fontsize=max(6, fc['size'] - 2), color='white',
                    fontweight='bold', zorder=4)

            if cfg.get('show_labels', True):
                angle = 2 * math.pi * i / n - math.pi / 2
                lx = (R + node_r + 0.04) * math.cos(angle)
                ly = (R + node_r + 0.04) * math.sin(angle)
                ha = 'center'
                if math.cos(angle) > 0.1:
                    ha = 'left'
                elif math.cos(angle) < -0.1:
                    ha = 'right'
                va = 'center'
                if math.sin(angle) > 0.1:
                    va = 'bottom'
                elif math.sin(angle) < -0.1:
                    va = 'top'
                ax.text(lx, ly, fmt_el, ha=ha, va=va,
                        fontsize=fc['size'], color=fc['color'],
                        fontweight='bold' if fc['bold'] else 'normal',
                        fontstyle='italic' if fc['italic'] else 'normal', zorder=5)

        subtitle_parts = [f"{len(edges)} edges"]
        if edges:
            subtitle_parts.append(f"mean|r|={mean_r:.2f}")
        if cfg.get('show_edge_count', True):
            subtitle_parts.append(f"n={net_data.get('n_particles', 0)}")
        subtitle = "  ·  ".join(subtitle_parts)

        if title:
            ax.set_title(f"{title}\n{subtitle}", fontsize=fc['size'],
                         color=fc['color'], pad=6,
                         fontweight='bold' if fc['bold'] else 'normal')
        else:
            ax.set_title(subtitle, fontsize=fc['size'],
                         color=fc['color'], pad=6)

        import matplotlib.lines as mlines
        pos_line = mlines.Line2D([], [], color=pos_c, lw=2, label='r > 0')
        neg_line = mlines.Line2D([], [], color=neg_c, lw=2, label='r < 0')
        ax.legend(handles=[pos_line, neg_line], loc='lower right',
                  fontsize=max(6, fc['size'] - 2), framealpha=0.7)


# ── Node ───────────────────────────────────────────────────────────────

class NetworkDiagramNode(QObject):
    position_changed      = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        """
        Args:
            parent_window (Any): The parent window.
        """
        super().__init__()
        self.title           = "Network"
        self.node_type       = "network_diagram"
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
        dlg = NetworkDisplayDialog(self, parent_window)
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

    def extract_network_data(self):
        """
        Returns:
            None
        """
        if not self.input_data:
            return None
        data_key    = NET_DATA_KEY_MAP.get(
            self.config.get('data_type_display', 'Counts'), 'elements')
        r_threshold = self.config.get('r_threshold', 0.3)
        min_n       = self.config.get('min_particles', 5)
        itype       = self.input_data.get('type')
        elements    = self._get_elements()
        if len(elements) < 2:
            return None
        if itype == 'sample_data':
            return self._extract_single(data_key, elements, r_threshold, min_n)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(data_key, elements, r_threshold, min_n)
        return None

    def _extract_single(self, data_key, elements, r_threshold, min_n):
        """
        Args:
            data_key (Any): The data key.
            elements (Any): The elements.
            r_threshold (Any): The r threshold.
            min_n (Any): The min n.
        Returns:
            dict: Result of the operation.
        """
        particles = self.input_data.get('particle_data', [])
        if not particles:
            return None
        edges  = _compute_edges(particles, elements, data_key, r_threshold, min_n)
        sname  = self.input_data.get('sample_name', 'Sample')
        return {
            'elements':    elements,
            'edges':       edges,
            'n_particles': len(particles),
            'title':       f"{get_display_name(sname, self.config)}  (n={len(particles)})",
        }

    def _extract_multi(self, data_key, elements, r_threshold, min_n):
        """
        Args:
            data_key (Any): The data key.
            elements (Any): The elements.
            r_threshold (Any): The r threshold.
            min_n (Any): The min n.
        Returns:
            object: Result of the operation.
        """
        particles = self.input_data.get('particle_data', [])
        names     = self.input_data.get('sample_names', [])
        if not particles or not names:
            return None
        result = {}
        for sn in names:
            sp = [p for p in particles if p.get('source_sample') == sn]
            if len(sp) < min_n:
                continue
            edges = _compute_edges(sp, elements, data_key, r_threshold, min_n)
            dn    = get_display_name(sn, self.config)
            result[sn] = {
                'elements':    elements,
                'edges':       edges,
                'n_particles': len(sp),
                'title':       f"{dn}  (n={len(sp)})",
            }
        return result if result else None