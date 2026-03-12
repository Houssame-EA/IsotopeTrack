"""
Network / Chord Diagram Node – circular element correlation network.

Elements are arranged around a circle.  Edges represent significant
pairwise Pearson correlations.  Red = positive, Blue = negative.
Edge width ∝ |r|.

Single sample  → one network.
Multi-sample   → tiled networks per sample / group.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QDoubleSpinBox, QCheckBox, QGroupBox, QColorDialog,
    QPushButton, QWidget, QMenu, QDialogButtonBox, QScrollArea,
    QSizePolicy, QLineEdit,
)
from PySide6.QtCore import Qt, Signal, QObject, QRectF, QPointF
from PySide6.QtGui import (
    QColor, QPen, QBrush, QFont, QPainter, QFontMetrics,
    QPainterPath, QRadialGradient,
)
import numpy as np
import math
from scipy.stats import pearsonr

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS,
    FontSettingsGroup, get_display_name,
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
    'data_type_display': 'Counts',
    'r_threshold': 0.3,
    'min_particles': 5,
    'positive_color': '#EF4444',
    'negative_color': '#3B82F6',
    'node_color': '#14B8A6',
    'edge_alpha': 0.6,
    'edge_width_factor': 3.0,
    'node_radius': 16,
    'show_labels': True,
    'show_edge_count': True,
    'dark_theme': True,
    'layout_radius_factor': 0.35,
    'font_family': 'Times New Roman',
    'font_size': 18,
    'font_bold': False,
    'font_italic': False,
    'font_color': '#000000',
    'sample_colors': {},
    'sample_name_mappings': {},
}


# ── Helpers ────────────────────────────────────────────────────────────

def _is_multi(input_data):
    return input_data and input_data.get('type') == 'multiple_sample_data'


def _compute_edges(particles, elements, data_key, r_threshold, min_n):
    """Return list of (i, j, r) where |r| >= threshold."""
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

class NetworkSettingsDialog(QDialog):
    def __init__(self, cfg, input_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Network Diagram Settings")
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

        # Data
        g1 = QGroupBox("Data")
        f1 = QFormLayout(g1)
        self.dtype_combo = QComboBox()
        self.dtype_combo.addItems(NET_DATA_TYPES)
        self.dtype_combo.setCurrentText(self._cfg.get('data_type_display', 'Counts'))
        f1.addRow("Data Type:", self.dtype_combo)
        self.thresh_spin = QDoubleSpinBox()
        self.thresh_spin.setRange(0.0, 0.99)
        self.thresh_spin.setDecimals(2)
        self.thresh_spin.setValue(self._cfg.get('r_threshold', 0.3))
        f1.addRow("|r| Threshold:", self.thresh_spin)
        self.min_part = QDoubleSpinBox()
        self.min_part.setRange(2, 1000)
        self.min_part.setDecimals(0)
        self.min_part.setValue(self._cfg.get('min_particles', 5))
        f1.addRow("Min Particles:", self.min_part)
        lay.addWidget(g1)

        # Colors
        g2 = QGroupBox("Colors")
        f2 = QFormLayout(g2)
        self._pos_btn = QPushButton()
        self._pos_btn.setFixedSize(30, 20)
        pc = self._cfg.get('positive_color', '#EF4444')
        self._pos_btn.setStyleSheet(f"background-color: {pc}; border:1px solid black;")
        self._pos_btn.clicked.connect(lambda: self._pick('positive_color', self._pos_btn))
        f2.addRow("Positive (r>0):", self._pos_btn)

        self._neg_btn = QPushButton()
        self._neg_btn.setFixedSize(30, 20)
        nc = self._cfg.get('negative_color', '#3B82F6')
        self._neg_btn.setStyleSheet(f"background-color: {nc}; border:1px solid black;")
        self._neg_btn.clicked.connect(lambda: self._pick('negative_color', self._neg_btn))
        f2.addRow("Negative (r<0):", self._neg_btn)

        self._node_btn = QPushButton()
        self._node_btn.setFixedSize(30, 20)
        ndc = self._cfg.get('node_color', '#14B8A6')
        self._node_btn.setStyleSheet(f"background-color: {ndc}; border:1px solid black;")
        self._node_btn.clicked.connect(lambda: self._pick('node_color', self._node_btn))
        f2.addRow("Node Color:", self._node_btn)
        lay.addWidget(g2)

        self._colors = {
            'positive_color': pc,
            'negative_color': nc,
            'node_color': ndc,
        }

        # Display
        g3 = QGroupBox("Display")
        f3 = QFormLayout(g3)
        self.alpha_spin = QDoubleSpinBox()
        self.alpha_spin.setRange(0.1, 1.0)
        self.alpha_spin.setDecimals(1)
        self.alpha_spin.setValue(self._cfg.get('edge_alpha', 0.6))
        f3.addRow("Edge Transparency:", self.alpha_spin)
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.5, 10.0)
        self.width_spin.setDecimals(1)
        self.width_spin.setValue(self._cfg.get('edge_width_factor', 3.0))
        f3.addRow("Edge Width Factor:", self.width_spin)
        self.node_r = QDoubleSpinBox()
        self.node_r.setRange(6, 40)
        self.node_r.setDecimals(0)
        self.node_r.setValue(self._cfg.get('node_radius', 16))
        f3.addRow("Node Radius:", self.node_r)
        self.labels_cb = QCheckBox()
        self.labels_cb.setChecked(self._cfg.get('show_labels', True))
        f3.addRow("Show Labels:", self.labels_cb)
        self.edge_count_cb = QCheckBox()
        self.edge_count_cb.setChecked(self._cfg.get('show_edge_count', True))
        f3.addRow("Show Edge Count:", self.edge_count_cb)
        self.dark_cb = QCheckBox()
        self.dark_cb.setChecked(self._cfg.get('dark_theme', True))
        f3.addRow("Dark Theme:", self.dark_cb)
        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(0.15, 0.48)
        self.radius_spin.setDecimals(2)
        self.radius_spin.setValue(self._cfg.get('layout_radius_factor', 0.35))
        f3.addRow("Layout Radius:", self.radius_spin)
        lay.addWidget(g3)

        # Font
        self._font_grp = FontSettingsGroup(self._cfg)
        lay.addWidget(self._font_grp.build())

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _pick(self, key, btn):
        c = QColorDialog.getColor(QColor(self._colors.get(key, '#FFFFFF')), self)
        if c.isValid():
            self._colors[key] = c.name()
            btn.setStyleSheet(f"background-color: {c.name()}; border:1px solid black;")

    def collect(self):
        d = {
            'data_type_display': self.dtype_combo.currentText(),
            'r_threshold': self.thresh_spin.value(),
            'min_particles': int(self.min_part.value()),
            'edge_alpha': self.alpha_spin.value(),
            'edge_width_factor': self.width_spin.value(),
            'node_radius': int(self.node_r.value()),
            'show_labels': self.labels_cb.isChecked(),
            'show_edge_count': self.edge_count_cb.isChecked(),
            'dark_theme': self.dark_cb.isChecked(),
            'layout_radius_factor': self.radius_spin.value(),
        }
        d.update(self._colors)
        d.update(self._font_grp.collect())
        return d


# ── Custom Network Widget ─────────────────────────────────────────────

class NetworkWidget(QWidget):
    """Draws one circular network diagram."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.net_data = None
        self.cfg = {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(400, 400)

    def set_data(self, net_data, cfg):
        """
        net_data = {
            'elements': [...],
            'edges': [(i, j, r), ...],
            'n_particles': int,
            'title': str,
        }
        """
        self.net_data = net_data
        self.cfg = cfg
        self.update()

    def paintEvent(self, event):
        if not self.net_data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cfg = self.cfg
        dark = cfg.get('dark_theme', True)
        bg = QColor(30, 37, 55) if dark else QColor(255, 255, 255)
        painter.fillRect(self.rect(), bg)

        elements = self.net_data['elements']
        edges = self.net_data['edges']
        n = len(elements)
        if n < 2:
            painter.end()
            return

        title = self.net_data.get('title', '')
        n_particles = self.net_data.get('n_particles', 0)
        n_edges = len(edges)
        mean_r = np.mean([abs(e[2]) for e in edges]) if edges else 0

        # Layout parameters
        w = self.width()
        h = self.height()
        cx = w / 2
        title_h = 80
        cy = title_h + (h - title_h) / 2
        radius_fac = cfg.get('layout_radius_factor', 0.35)
        R = min(w, h - title_h) * radius_fac
        node_r = cfg.get('node_radius', 16)

        # Title
        title_color = QColor('#14B8A6') if dark else QColor('#0F766E')
        painter.setPen(title_color)
        painter.setFont(QFont(cfg.get('font_family', 'Segoe UI'), 16, QFont.Bold))
        painter.drawText(
            QRectF(0, 8, w, 35), Qt.AlignHCenter, title)

        # Subtitle: edge count + mean|r|
        sub_color = QColor('#94A3B8') if dark else QColor('#6B7280')
        painter.setPen(sub_color)
        painter.setFont(QFont(cfg.get('font_family', 'Segoe UI'), 10))
        sub = f"{n_edges} edges  ·  mean|r|={mean_r:.3f}"
        painter.drawText(
            QRectF(0, 40, w, 22), Qt.AlignHCenter, sub)

        # Compute node positions
        positions = []
        for i in range(n):
            angle = 2 * math.pi * i / n - math.pi / 2  # start at top
            px = cx + R * math.cos(angle)
            py = cy + R * math.sin(angle)
            positions.append(QPointF(px, py))

        # Draw edges
        pos_color = QColor(cfg.get('positive_color', '#EF4444'))
        neg_color = QColor(cfg.get('negative_color', '#3B82F6'))
        alpha = int(cfg.get('edge_alpha', 0.6) * 255)
        wf = cfg.get('edge_width_factor', 3.0)

        for (i, j, r) in edges:
            ec = QColor(pos_color) if r > 0 else QColor(neg_color)
            ec.setAlpha(alpha)
            lw = max(0.5, abs(r) * wf)
            painter.setPen(QPen(ec, lw))
            painter.drawLine(positions[i], positions[j])

        # Draw nodes
        nc = QColor(cfg.get('node_color', '#14B8A6'))
        for i, el in enumerate(elements):
            pos = positions[i]

            # Node circle with gradient
            grad = QRadialGradient(pos, node_r)
            grad.setColorAt(0.0, nc.lighter(140))
            grad.setColorAt(1.0, nc)
            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(nc.darker(130), 2.0))
            painter.drawEllipse(pos, node_r, node_r)

            # Label
            if cfg.get('show_labels', True):
                txt_color = QColor('#E2E8F0') if dark else QColor('#1F2937')
                painter.setPen(txt_color)
                font_size = max(7, min(10, node_r // 2 + 2))
                painter.setFont(QFont(cfg.get('font_family', 'Segoe UI'), font_size, QFont.Bold))

                # Position label outside the circle
                angle = 2 * math.pi * i / n - math.pi / 2
                label_dist = node_r + 12
                lx = pos.x() + label_dist * math.cos(angle)
                ly = pos.y() + label_dist * math.sin(angle)
                fm = QFontMetrics(painter.font())
                tw = fm.horizontalAdvance(el)
                th = fm.height()

                # Adjust for quadrant
                if abs(math.cos(angle)) < 0.1:
                    lx -= tw / 2
                elif math.cos(angle) < 0:
                    lx -= tw
                if abs(math.sin(angle)) < 0.1:
                    ly += th / 4
                elif math.sin(angle) < 0:
                    ly -= 2

                painter.drawText(QPointF(lx, ly), el)

        painter.end()


# ── Display Dialog ─────────────────────────────────────────────────────

class NetworkDisplayDialog(QDialog):
    def __init__(self, node, parent_window=None):
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
        self._info.setStyleSheet("color: #94A3B8; font-size: 11px; padding: 2px 6px;")
        lay.addWidget(self._info)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setContextMenuPolicy(Qt.CustomContextMenu)
        self._scroll.customContextMenuRequested.connect(self._ctx_menu)
        lay.addWidget(self._scroll, stretch=1)

        self._container = QWidget()
        self._container_lay = QHBoxLayout(self._container)
        self._container_lay.setContentsMargins(8, 8, 8, 8)
        self._scroll.setWidget(self._container)
        self._widgets = []

    def _ctx_menu(self, pos):
        cfg = self.node.config
        menu = QMenu(self)

        dm = menu.addMenu("Data Type")
        for dt in NET_DATA_TYPES:
            a = dm.addAction(dt)
            a.setCheckable(True)
            a.setChecked(cfg.get('data_type_display') == dt)
            a.triggered.connect(lambda _, v=dt: self._set('data_type_display', v))

        tm = menu.addMenu("Quick Toggles")
        for key, label in [
            ('show_labels', 'Show Labels'),
            ('show_edge_count', 'Show Edge Count'),
            ('dark_theme', 'Dark Theme'),
        ]:
            a = tm.addAction(label)
            a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        # Threshold presets
        pm = menu.addMenu("|r| Threshold")
        for t in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
            a = pm.addAction(f"≥ {t}")
            a.setCheckable(True)
            a.setChecked(abs(cfg.get('r_threshold', 0.3) - t) < 0.01)
            a.triggered.connect(lambda _, v=t: self._set('r_threshold', v))

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
        dlg = NetworkSettingsDialog(self.node.config, self.node.input_data, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _download(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Network Diagram", "network_diagram.png",
            "PNG (*.png);;JPEG (*.jpg)")
        if path:
            pixmap = self._container.grab()
            pixmap.save(path)

    def _refresh(self):
        try:
            for w in self._widgets:
                self._container_lay.removeWidget(w)
                w.deleteLater()
            self._widgets.clear()

            data = self.node.extract_network_data()
            if not data:
                lbl = QLabel("No data available.\nConnect to a Sample Selector node.")
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setStyleSheet("color: gray; font-size: 14px;")
                self._container_lay.addWidget(lbl)
                self._widgets.append(lbl)
                self._info.setText("")
                return

            cfg = self.node.config
            dark = cfg.get('dark_theme', True)
            bg = "#1E293B" if dark else "white"
            self._container.setStyleSheet(f"background: {bg};")
            self._scroll.setStyleSheet(f"background: {bg};")

            if isinstance(data, dict) and 'elements' in data:
                # Single network
                w = NetworkWidget()
                w.set_data(data, cfg)
                w.setMinimumSize(500, 500)
                self._container_lay.addWidget(w)
                self._widgets.append(w)
                self._info.setText(
                    f"{len(data['elements'])} elements · "
                    f"{len(data['edges'])} edges · "
                    f"{data.get('n_particles', 0)} particles")
            elif isinstance(data, dict):
                # Multi: dict of {name: net_data}
                total_edges = 0
                for sn, nd in data.items():
                    w = NetworkWidget()
                    w.set_data(nd, cfg)
                    w.setMinimumSize(450, 450)
                    self._container_lay.addWidget(w)
                    self._widgets.append(w)
                    total_edges += len(nd['edges'])
                self._info.setText(
                    f"{len(data)} groups · {total_edges} total edges")

        except Exception as e:
            print(f"Error refreshing network diagram: {e}")
            import traceback
            traceback.print_exc()


# ── Node ───────────────────────────────────────────────────────────────

class NetworkDiagramNode(QObject):
    position_changed = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        super().__init__()
        self.title = "Network"
        self.node_type = "network_diagram"
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
        dlg = NetworkDisplayDialog(self, parent_window)
        dlg.exec()
        return True

    def process_data(self, input_data):
        if not input_data:
            return
        self.input_data = input_data
        self.configuration_changed.emit()

    def _get_elements(self):
        sel = self.input_data.get('selected_isotopes', [])
        if sel:
            return sort_elements_by_mass([i['label'] for i in sel])
        particles = self.input_data.get('particle_data', [])
        all_elems = set()
        for p in particles:
            all_elems.update(p.get('elements', {}).keys())
        return sort_elements_by_mass(list(all_elems))

    def extract_network_data(self):
        if not self.input_data:
            return None

        data_key = NET_DATA_KEY_MAP.get(
            self.config.get('data_type_display', 'Counts'), 'elements')
        r_threshold = self.config.get('r_threshold', 0.3)
        min_n = self.config.get('min_particles', 5)
        itype = self.input_data.get('type')

        elements = self._get_elements()
        if len(elements) < 2:
            return None

        if itype == 'sample_data':
            return self._extract_single(data_key, elements, r_threshold, min_n)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(data_key, elements, r_threshold, min_n)
        return None

    def _extract_single(self, data_key, elements, r_threshold, min_n):
        particles = self.input_data.get('particle_data', [])
        if not particles:
            return None
        edges = _compute_edges(particles, elements, data_key, r_threshold, min_n)
        sname = self.input_data.get('sample_name', 'Sample')
        return {
            'elements': elements,
            'edges': edges,
            'n_particles': len(particles),
            'title': f"{get_display_name(sname, self.config)}  (n={len(particles)})",
        }

    def _extract_multi(self, data_key, elements, r_threshold, min_n):
        particles = self.input_data.get('particle_data', [])
        names = self.input_data.get('sample_names', [])
        if not particles or not names:
            return None

        result = {}
        for sn in names:
            sp = [p for p in particles if p.get('source_sample') == sn]
            if len(sp) < min_n:
                continue
            edges = _compute_edges(sp, elements, data_key, r_threshold, min_n)
            dn = get_display_name(sn, self.config)
            result[sn] = {
                'elements': elements,
                'edges': edges,
                'n_particles': len(sp),
                'title': f"{dn}  (n={len(sp)})",
            }
        return result if result else None
