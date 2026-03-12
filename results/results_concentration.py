"""
Concentration-Comparison Plot Node – dot-and-circle strip chart.

Each element gets a horizontal row.
Individual sample values are small dots, group means are large open circles.
Numeric mean values displayed on the right.

Single sample  → one column of dots per element.
Multi-sample   → overlaid colours per sample / group.
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
)
import numpy as np

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS,
    get_font_config, make_qfont, FontSettingsGroup,
    get_display_name,
)
from results.utils_sort import sort_elements_by_mass


# ── Constants ──────────────────────────────────────────────────────────

CONC_DATA_TYPES = [
    'Counts',
    'Element Mass (fg)',
    'Particle Mass (fg)',
    'Element Moles (fmol)',
    'Particle Moles (fmol)',
    'Element Diameter (nm)',
    'Particle Diameter (nm)',
]

CONC_DATA_KEY_MAP = {
    'Counts': 'elements',
    'Element Mass (fg)': 'element_mass_fg',
    'Particle Mass (fg)': 'particle_mass_fg',
    'Element Moles (fmol)': 'element_moles_fmol',
    'Particle Moles (fmol)': 'particle_moles_fmol',
    'Element Diameter (nm)': 'element_diameter_nm',
    'Particle Diameter (nm)': 'particle_diameter_nm',
}

CONC_LABEL_MAP = {
    'Counts': 'Intensity (counts)',
    'Element Mass (fg)': 'Mass (fg)',
    'Particle Mass (fg)': 'Particle Mass (fg)',
    'Element Moles (fmol)': 'Moles (fmol)',
    'Particle Moles (fmol)': 'Particle Moles (fmol)',
    'Element Diameter (nm)': 'Diameter (nm)',
    'Particle Diameter (nm)': 'Particle Diameter (nm)',
}

CONC_AGG_METHODS = ['Mean', 'Median', 'Geometric Mean']

DEFAULT_CONFIG = {
    'data_type_display': 'Counts',
    'aggregation': 'Mean',
    'log_scale': True,
    'show_individual': True,
    'show_mean_circle': True,
    'show_values': True,
    'dot_size': 5,
    'circle_size_factor': 1.0,
    'row_height': 34,
    'dark_theme': True,
    'sample_colors': {},
    'sample_name_mappings': {},
    'font_family': 'Times New Roman',
    'font_size': 18,
    'font_bold': False,
    'font_italic': False,
    'font_color': '#000000',
}

DEFAULT_GROUP_COLORS = ['#60A5FA', '#F472B6', '#34D399', '#FBBF24', '#A78BFA',
                        '#FB923C', '#38BDF8', '#F87171', '#4ADE80', '#E879F9']


# ── Helpers ────────────────────────────────────────────────────────────

def _is_multi(input_data):
    return input_data and input_data.get('type') == 'multiple_sample_data'


def _agg(values, method):
    if not values:
        return 0
    arr = np.array(values, dtype=float)
    arr = arr[arr > 0]
    if len(arr) == 0:
        return 0
    if method == 'Median':
        return float(np.median(arr))
    elif method == 'Geometric Mean':
        return float(np.exp(np.mean(np.log(arr))))
    return float(np.mean(arr))


def _fmt_val(v):
    """Smart format: big nums get 2 decimals, small get more."""
    if v == 0:
        return "—"
    if abs(v) >= 100:
        return f"{v:.2f}"
    elif abs(v) >= 1:
        return f"{v:.2f}"
    elif abs(v) >= 0.01:
        return f"{v:.3f}"
    else:
        return f"{v:.4f}"


# ── Settings Dialog ────────────────────────────────────────────────────

class ConcentrationSettingsDialog(QDialog):
    def __init__(self, cfg, input_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Concentration Comparison Settings")
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
        self.dtype_combo.addItems(CONC_DATA_TYPES)
        self.dtype_combo.setCurrentText(self._cfg.get('data_type_display', 'Counts'))
        f1.addRow("Data Type:", self.dtype_combo)
        self.agg_combo = QComboBox()
        self.agg_combo.addItems(CONC_AGG_METHODS)
        self.agg_combo.setCurrentText(self._cfg.get('aggregation', 'Mean'))
        f1.addRow("Aggregation:", self.agg_combo)
        lay.addWidget(g1)

        # Display
        g2 = QGroupBox("Display")
        f2 = QFormLayout(g2)
        self.log_cb = QCheckBox()
        self.log_cb.setChecked(self._cfg.get('log_scale', True))
        f2.addRow("Log Scale:", self.log_cb)
        self.indiv_cb = QCheckBox()
        self.indiv_cb.setChecked(self._cfg.get('show_individual', True))
        f2.addRow("Show Individual Points:", self.indiv_cb)
        self.circle_cb = QCheckBox()
        self.circle_cb.setChecked(self._cfg.get('show_mean_circle', True))
        f2.addRow("Show Mean Circles:", self.circle_cb)
        self.vals_cb = QCheckBox()
        self.vals_cb.setChecked(self._cfg.get('show_values', True))
        f2.addRow("Show Numeric Values:", self.vals_cb)
        self.dark_cb = QCheckBox()
        self.dark_cb.setChecked(self._cfg.get('dark_theme', True))
        f2.addRow("Dark Theme:", self.dark_cb)
        self.row_h = QDoubleSpinBox()
        self.row_h.setRange(20, 80)
        self.row_h.setDecimals(0)
        self.row_h.setValue(self._cfg.get('row_height', 34))
        f2.addRow("Row Height:", self.row_h)
        self.dot_spin = QDoubleSpinBox()
        self.dot_spin.setRange(2, 15)
        self.dot_spin.setDecimals(0)
        self.dot_spin.setValue(self._cfg.get('dot_size', 5))
        f2.addRow("Dot Size:", self.dot_spin)
        self.csf = QDoubleSpinBox()
        self.csf.setRange(0.2, 3.0)
        self.csf.setDecimals(1)
        self.csf.setValue(self._cfg.get('circle_size_factor', 1.0))
        f2.addRow("Circle Size Factor:", self.csf)
        lay.addWidget(g2)

        # Sample colors (multi)
        if _is_multi(self._input_data):
            names = self._input_data.get('sample_names', [])
            if names:
                g3 = QGroupBox("Sample Colors & Names")
                v3 = QVBoxLayout(g3)
                self._sample_btns = {}
                self._sample_edits = {}
                sc = dict(self._cfg.get('sample_colors', {}))
                nm = dict(self._cfg.get('sample_name_mappings', {}))
                for i, sn in enumerate(names):
                    h = QHBoxLayout()
                    ed = QLineEdit(nm.get(sn, sn))
                    ed.setFixedWidth(180)
                    h.addWidget(ed)
                    self._sample_edits[sn] = ed
                    btn = QPushButton()
                    btn.setFixedSize(25, 18)
                    c = sc.get(sn, DEFAULT_GROUP_COLORS[i % len(DEFAULT_GROUP_COLORS)])
                    sc[sn] = c
                    btn.setStyleSheet(f"background-color: {c}; border:1px solid black;")
                    btn.clicked.connect(lambda _, s=sn, b=btn: self._pick_color(s, b))
                    h.addWidget(btn)
                    h.addStretch()
                    w = QWidget()
                    w.setLayout(h)
                    v3.addWidget(w)
                    self._sample_btns[sn] = (btn, c)
                self._sample_colors = sc
                lay.addWidget(g3)

        # Font
        self._font_grp = FontSettingsGroup(self._cfg)
        lay.addWidget(self._font_grp.build())

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _pick_color(self, sn, btn):
        c = QColorDialog.getColor(QColor(self._sample_colors.get(sn, '#3B82F6')), self)
        if c.isValid():
            self._sample_colors[sn] = c.name()
            btn.setStyleSheet(f"background-color: {c.name()}; border:1px solid black;")

    def collect(self):
        d = {
            'data_type_display': self.dtype_combo.currentText(),
            'aggregation': self.agg_combo.currentText(),
            'log_scale': self.log_cb.isChecked(),
            'show_individual': self.indiv_cb.isChecked(),
            'show_mean_circle': self.circle_cb.isChecked(),
            'show_values': self.vals_cb.isChecked(),
            'dark_theme': self.dark_cb.isChecked(),
            'row_height': int(self.row_h.value()),
            'dot_size': int(self.dot_spin.value()),
            'circle_size_factor': self.csf.value(),
        }
        d.update(self._font_grp.collect())
        if hasattr(self, '_sample_colors'):
            d['sample_colors'] = dict(self._sample_colors)
        if hasattr(self, '_sample_edits'):
            d['sample_name_mappings'] = {k: v.text() for k, v in self._sample_edits.items()}
        return d


# ── Custom Painting Widget ────────────────────────────────────────────

class ConcentrationWidget(QWidget):
    """Custom-painted horizontal dot/circle chart."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot_data = None
        self.cfg = {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(self, plot_data, cfg):
        """
        plot_data format:
        {
            'elements': ['Al', 'As', ...],
            'groups': {
                'Male': {'color': '#60A5FA', 'values': {'Al': [v1,v2,...], ...}, 'agg': {'Al': mean, ...}},
                'Female': { ... },
            },
            'title': '...',
            'subtitle': '...',
            'unit': '...',
        }
        """
        self.plot_data = plot_data
        self.cfg = cfg
        # Compute min size
        if plot_data:
            n_rows = len(plot_data['elements'])
            rh = cfg.get('row_height', 34)
            h = n_rows * rh + 160
            self.setMinimumHeight(max(h, 400))
        self.update()

    def paintEvent(self, event):
        if not self.plot_data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cfg = self.cfg
        dark = cfg.get('dark_theme', True)
        bg = QColor(30, 37, 55) if dark else QColor(255, 255, 255)
        painter.fillRect(self.rect(), bg)

        elements = self.plot_data['elements']
        groups = self.plot_data['groups']
        n_groups = len(groups)
        group_names = list(groups.keys())

        rh = cfg.get('row_height', 34)
        dot_size = cfg.get('dot_size', 5)
        csf = cfg.get('circle_size_factor', 1.0)
        log_scale = cfg.get('log_scale', True)
        show_indiv = cfg.get('show_individual', True)
        show_circle = cfg.get('show_mean_circle', True)
        show_vals = cfg.get('show_values', True)

        # Layout
        label_w = 40
        val_col_w = 65 * n_groups if show_vals else 0
        top_margin = 100
        left_margin = 20
        right_margin = 20

        plot_left = left_margin + label_w
        plot_right = self.width() - right_margin - val_col_w - 10
        plot_w = max(plot_right - plot_left, 100)

        # Title
        title = self.plot_data.get('title', '')
        subtitle = self.plot_data.get('subtitle', '')

        title_color = QColor('#F1F5F9') if dark else QColor('#1F2937')
        painter.setPen(title_color)
        painter.setFont(QFont(cfg.get('font_family', 'Segoe UI'), 16, QFont.Bold))
        painter.drawText(
            QRectF(0, 10, self.width(), 35),
            Qt.AlignHCenter, title)

        sub_color = QColor('#94A3B8') if dark else QColor('#6B7280')
        painter.setPen(sub_color)
        painter.setFont(QFont(cfg.get('font_family', 'Segoe UI'), 9))
        painter.drawText(
            QRectF(0, 42, self.width(), 20),
            Qt.AlignHCenter, subtitle)

        # Legend
        legend_y = 68
        legend_x = left_margin + 10
        painter.setFont(QFont(cfg.get('font_family', 'Segoe UI'), 10))
        for gn in group_names:
            gc = QColor(groups[gn]['color'])
            painter.setPen(Qt.NoPen)
            painter.setBrush(gc)
            painter.drawEllipse(QPointF(legend_x + 5, legend_y + 6), 5, 5)
            painter.setPen(gc)
            painter.drawText(QRectF(legend_x + 14, legend_y - 2, 120, 18),
                             Qt.AlignLeft | Qt.AlignVCenter, gn)
            legend_x += QFontMetrics(painter.font()).horizontalAdvance(gn) + 30

        # Compute global range for X scaling
        all_vals = []
        for gn, gd in groups.items():
            for el in elements:
                vs = gd['values'].get(el, [])
                all_vals.extend([v for v in vs if v > 0])
        if not all_vals:
            painter.end()
            return

        if log_scale:
            all_vals_t = [np.log10(v) for v in all_vals if v > 0]
        else:
            all_vals_t = list(all_vals)

        if not all_vals_t:
            painter.end()
            return

        vmin = min(all_vals_t)
        vmax = max(all_vals_t)
        vrange = vmax - vmin if vmax > vmin else 1

        def x_pos(v):
            if log_scale:
                t = np.log10(v) if v > 0 else vmin
            else:
                t = v
            return plot_left + (t - vmin) / vrange * plot_w

        # Draw rows
        txt_color = QColor('#CBD5E1') if dark else QColor('#374151')
        line_color = QColor(50, 58, 80) if dark else QColor(220, 220, 220)
        el_font = QFont(cfg.get('font_family', 'Segoe UI'), 10, QFont.Bold)
        val_font = QFont(cfg.get('font_family', 'Segoe UI'), 9)

        for ri, el in enumerate(elements):
            cy = top_margin + ri * rh + rh / 2

            # Separator line
            painter.setPen(QPen(line_color, 0.5))
            painter.drawLine(
                QPointF(plot_left, cy),
                QPointF(plot_right, cy))

            # Element label
            painter.setPen(txt_color)
            painter.setFont(el_font)
            painter.drawText(
                QRectF(left_margin, cy - rh / 2, label_w - 4, rh),
                Qt.AlignRight | Qt.AlignVCenter, el)

            # Draw data per group
            for gi, gn in enumerate(group_names):
                gc = QColor(groups[gn]['color'])
                vals = groups[gn]['values'].get(el, [])
                agg_val = groups[gn]['agg'].get(el, 0)

                # Individual dots
                if show_indiv and vals:
                    gc_light = QColor(gc)
                    gc_light.setAlpha(160)
                    painter.setPen(QPen(gc.darker(120), 0.5))
                    painter.setBrush(gc_light)
                    for v in vals:
                        if v > 0:
                            px = x_pos(v)
                            painter.drawEllipse(QPointF(px, cy), dot_size, dot_size)

                # Mean circle
                if show_circle and agg_val > 0:
                    px = x_pos(agg_val)
                    r = max(6, min(16, 8 * csf * (1 + np.log10(max(agg_val, 0.001)) / 4)))
                    painter.setPen(QPen(gc, 2.0))
                    painter.setBrush(QBrush(Qt.NoBrush))
                    painter.drawEllipse(QPointF(px, cy), r, r)

                # Numeric value on right
                if show_vals:
                    val_x = plot_right + 12 + gi * 65
                    painter.setPen(gc)
                    painter.setFont(val_font)
                    painter.drawText(
                        QRectF(val_x, cy - rh / 2, 60, rh),
                        Qt.AlignCenter, _fmt_val(agg_val))

        # Value column headers
        if show_vals:
            painter.setFont(QFont(cfg.get('font_family', 'Segoe UI'), 8, QFont.Bold))
            for gi, gn in enumerate(group_names):
                gc = QColor(groups[gn]['color'])
                painter.setPen(gc)
                val_x = plot_right + 12 + gi * 65
                painter.drawText(
                    QRectF(val_x, top_margin - 22, 60, 18),
                    Qt.AlignCenter, get_display_name(gn, cfg))

        painter.end()


# ── Display Dialog ─────────────────────────────────────────────────────

class ConcentrationDisplayDialog(QDialog):
    def __init__(self, node, parent_window=None):
        super().__init__(parent_window)
        self.node = node
        self.setWindowTitle("Concentration Comparison Plot")
        self.setMinimumSize(900, 750)
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

        self._chart = ConcentrationWidget()
        self._scroll.setWidget(self._chart)

    def _ctx_menu(self, pos):
        cfg = self.node.config
        menu = QMenu(self)

        dm = menu.addMenu("Data Type")
        for dt in CONC_DATA_TYPES:
            a = dm.addAction(dt)
            a.setCheckable(True)
            a.setChecked(cfg.get('data_type_display') == dt)
            a.triggered.connect(lambda _, v=dt: self._set('data_type_display', v))

        am = menu.addMenu("Aggregation")
        for m in CONC_AGG_METHODS:
            a = am.addAction(m)
            a.setCheckable(True)
            a.setChecked(cfg.get('aggregation') == m)
            a.triggered.connect(lambda _, v=m: self._set('aggregation', v))

        tm = menu.addMenu("Quick Toggles")
        for key, label in [
            ('log_scale', 'Log Scale'),
            ('show_individual', 'Show Individual Points'),
            ('show_mean_circle', 'Show Mean Circles'),
            ('show_values', 'Show Numeric Values'),
            ('dark_theme', 'Dark Theme'),
        ]:
            a = tm.addAction(label)
            a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

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
        dlg = ConcentrationSettingsDialog(self.node.config, self.node.input_data, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    def _download(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Concentration Plot", "concentration_comparison.png",
            "PNG (*.png);;JPEG (*.jpg)")
        if path:
            pixmap = self._chart.grab()
            pixmap.save(path)

    def _refresh(self):
        try:
            data = self.node.extract_concentration_data()
            if not data:
                self._chart.plot_data = None
                self._chart.update()
                self._info.setText("No data available. Connect to a Sample Selector node.")
                return

            cfg = self.node.config
            dark = cfg.get('dark_theme', True)
            bg = "#1E293B" if dark else "white"
            self._scroll.setStyleSheet(f"background: {bg};")

            self._chart.set_data(data, cfg)

            n_el = len(data['elements'])
            n_grp = len(data['groups'])
            self._info.setText(f"{n_el} elements · {n_grp} group(s)")

        except Exception as e:
            print(f"Error refreshing concentration plot: {e}")
            import traceback
            traceback.print_exc()


# ── Node ───────────────────────────────────────────────────────────────

class ConcentrationComparisonNode(QObject):
    position_changed = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        super().__init__()
        self.title = "Concentration"
        self.node_type = "concentration_comparison"
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
        dlg = ConcentrationDisplayDialog(self, parent_window)
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

    def extract_concentration_data(self):
        if not self.input_data:
            return None

        data_key = CONC_DATA_KEY_MAP.get(
            self.config.get('data_type_display', 'Counts'), 'elements')
        agg_method = self.config.get('aggregation', 'Mean')
        unit = CONC_LABEL_MAP.get(self.config.get('data_type_display', 'Counts'), '')
        itype = self.input_data.get('type')

        elements = self._get_elements()
        if not elements:
            return None

        if itype == 'sample_data':
            return self._extract_single(data_key, elements, agg_method, unit)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(data_key, elements, agg_method, unit)
        return None

    def _extract_single(self, data_key, elements, agg_method, unit):
        particles = self.input_data.get('particle_data', [])
        if not particles:
            return None

        sname = self.input_data.get('sample_name', 'Sample')
        sc = self.config.get('sample_colors', {})
        color = sc.get(sname, DEFAULT_GROUP_COLORS[0])

        vals_by_el = {}
        agg_by_el = {}
        for el in elements:
            vs = [p.get(data_key, {}).get(el, 0) for p in particles]
            vs = [v for v in vs if v > 0 and not (isinstance(v, float) and np.isnan(v))]
            vals_by_el[el] = vs
            agg_by_el[el] = _agg(vs, agg_method)

        return {
            'elements': elements,
            'groups': {
                sname: {
                    'color': color,
                    'values': vals_by_el,
                    'agg': agg_by_el,
                }
            },
            'title': f"{agg_method} conc. — {sname}",
            'subtitle': f"Circle={agg_method.lower()}, dot=individual · {unit}",
            'unit': unit,
        }

    def _extract_multi(self, data_key, elements, agg_method, unit):
        particles = self.input_data.get('particle_data', [])
        names = self.input_data.get('sample_names', [])
        if not particles or not names:
            return None

        sc = self.config.get('sample_colors', {})
        groups = {}

        for gi, sn in enumerate(names):
            sp = [p for p in particles if p.get('source_sample') == sn]
            if not sp:
                continue
            color = sc.get(sn, DEFAULT_GROUP_COLORS[gi % len(DEFAULT_GROUP_COLORS)])

            vals_by_el = {}
            agg_by_el = {}
            for el in elements:
                vs = [p.get(data_key, {}).get(el, 0) for p in sp]
                vs = [v for v in vs if v > 0 and not (isinstance(v, float) and np.isnan(v))]
                vals_by_el[el] = vs
                agg_by_el[el] = _agg(vs, agg_method)

            dn = get_display_name(sn, self.config)
            groups[sn] = {
                'color': color,
                'values': vals_by_el,
                'agg': agg_by_el,
            }

        if not groups:
            return None

        group_labels = ' vs '.join(
            [get_display_name(n, self.config) for n in groups.keys()])
        return {
            'elements': elements,
            'groups': groups,
            'title': f"{agg_method} conc. — {group_labels}",
            'subtitle': f"Circle={agg_method.lower()}, dot=individual · {unit}",
            'unit': unit,
        }
