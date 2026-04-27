"""
Concentration-Comparison Plot Node – dot-and-circle strip chart.

Each element gets a horizontal row.
Individual sample values are small dots (jittered), group means are large
open circles.  Numeric mean values displayed on the right.

Single sample  → one column of dots per element.
Multi-sample   → overlaid colours per sample / group.

Rendered with Matplotlib (MplDraggableCanvas) for full drag/export support.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QComboBox,
    QDoubleSpinBox, QSpinBox, QCheckBox, QGroupBox, QColorDialog,
    QPushButton, QWidget, QMenu, QDialogButtonBox, QScrollArea, QLineEdit,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QCursor
from matplotlib.figure import Figure
import matplotlib.ticker as mticker
import numpy as np
import math

from results.shared_plot_utils import (
    FONT_FAMILIES, DEFAULT_SAMPLE_COLORS,
    get_font_config, apply_font_to_matplotlib,
    FontSettingsGroup, ExportSettingsGroup, MplDraggableCanvas,
    LABEL_MODES, format_element_label,
    get_display_name, download_matplotlib_figure,
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
    'Counts':                  'elements',
    'Element Mass (fg)':       'element_mass_fg',
    'Particle Mass (fg)':      'particle_mass_fg',
    'Element Moles (fmol)':    'element_moles_fmol',
    'Particle Moles (fmol)':   'particle_moles_fmol',
    'Element Diameter (nm)':   'element_diameter_nm',
    'Particle Diameter (nm)':  'particle_diameter_nm',
}

CONC_LABEL_MAP = {
    'Counts':                  'Intensity (counts)',
    'Element Mass (fg)':       'Mass (fg)',
    'Particle Mass (fg)':      'Particle Mass (fg)',
    'Element Moles (fmol)':    'Moles (fmol)',
    'Particle Moles (fmol)':   'Particle Moles (fmol)',
    'Element Diameter (nm)':   'Diameter (nm)',
    'Particle Diameter (nm)':  'Particle Diameter (nm)',
}

CONC_AGG_METHODS = ['Mean', 'Median', 'Geometric Mean']

DEFAULT_CONFIG = {
    'data_type_display':  'Counts',
    'aggregation':        'Mean',
    'log_scale':          True,
    'show_individual':    True,
    'show_mean_circle':   True,
    'show_values':        True,
    'dot_size':           5,
    'dot_alpha':          0.4,
    'circle_size':        120,
    'jitter':             0.15,
    'label_mode':         'Symbol',
    'font_family':        'Times New Roman',
    'font_size':          10,
    'font_bold':          False,
    'font_italic':        False,
    'font_color':         '#000000',
    'sample_colors':      {},
    'sample_name_mappings': {},
    'bg_color':           '#FFFFFF',
    'export_format':      'svg',
    'export_dpi':         300,
    'use_custom_figsize': False,
    'figsize_w':          12.0,
    'figsize_h':          8.0,
}

DEFAULT_GROUP_COLORS = [
    '#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6',
    '#EC4899', '#06B6D4', '#F97316', '#84CC16', '#6366F1',
]


# ── Helpers ────────────────────────────────────────────────────────────

def _is_multi(input_data):
    """
    Args:
        input_data (Any): The input data.
    Returns:
        object: Result of the operation.
    """
    return input_data and input_data.get('type') == 'multiple_sample_data'


def _agg(values, method):
    """
    Args:
        values (Any): Array or sequence of values.
        method (Any): The method.
    Returns:
        object: Result of the operation.
    """
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
    """
    Args:
        v (Any): The v.
    Returns:
        object: Result of the operation.
    """
    if v == 0:
        return "—"
    if abs(v) >= 1000:
        return f"{v:.2e}"
    elif abs(v) >= 1:
        return f"{v:.2f}"
    elif abs(v) >= 0.01:
        return f"{v:.3f}"
    return f"{v:.2e}"


# ── Settings Dialog ────────────────────────────────────────────────────

class ConcentrationSettingsDialog(QDialog):
    def __init__(self, cfg, input_data, parent=None):
        """
        Args:
            cfg (Any): The cfg.
            input_data (Any): The input data.
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("Concentration Comparison Settings")
        self.setMinimumWidth(500)
        self._cfg = dict(cfg)
        self._input_data = input_data
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); lay = QVBoxLayout(inner)
        scroll.setWidget(inner); root.addWidget(scroll)

        # ── Data ──────────────────────────────────────────────────────
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

        # ── Display ───────────────────────────────────────────────────
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
        f2.addRow("Show Mean Markers:", self.circle_cb)

        self.vals_cb = QCheckBox()
        self.vals_cb.setChecked(self._cfg.get('show_values', True))
        f2.addRow("Show Numeric Values:", self.vals_cb)

        self.dot_spin = QSpinBox()
        self.dot_spin.setRange(2, 20)
        self.dot_spin.setValue(self._cfg.get('dot_size', 5))
        f2.addRow("Dot Size:", self.dot_spin)

        self.dot_alpha = QDoubleSpinBox()
        self.dot_alpha.setRange(0.05, 1.0); self.dot_alpha.setSingleStep(0.05)
        self.dot_alpha.setDecimals(2)
        self.dot_alpha.setValue(self._cfg.get('dot_alpha', 0.4))
        f2.addRow("Dot Alpha:", self.dot_alpha)

        self.circle_size = QSpinBox()
        self.circle_size.setRange(20, 500)
        self.circle_size.setValue(self._cfg.get('circle_size', 120))
        f2.addRow("Mean Marker Size:", self.circle_size)

        self.jitter_spin = QDoubleSpinBox()
        self.jitter_spin.setRange(0.0, 0.45); self.jitter_spin.setSingleStep(0.05)
        self.jitter_spin.setDecimals(2)
        self.jitter_spin.setSpecialValueText("No jitter")
        self.jitter_spin.setValue(self._cfg.get('jitter', 0.15))
        f2.addRow("Vertical Jitter:", self.jitter_spin)

        self.label_mode_combo = QComboBox()
        self.label_mode_combo.addItems(LABEL_MODES)
        self.label_mode_combo.setCurrentText(self._cfg.get('label_mode', 'Symbol'))
        f2.addRow("Label Mode:", self.label_mode_combo)

        lay.addWidget(g2)

        # ── Sample colors (multi) ─────────────────────────────────────
        self._sample_btns = {}
        self._sample_edits = {}
        self._sample_colors = {}
        if _is_multi(self._input_data):
            names = self._input_data.get('sample_names', [])
            if names:
                g3 = QGroupBox("Sample Colors & Names")
                v3 = QVBoxLayout(g3)
                sc = dict(self._cfg.get('sample_colors', {}))
                nm = dict(self._cfg.get('sample_name_mappings', {}))
                for i, sn in enumerate(names):
                    h = QHBoxLayout()
                    ed = QLineEdit(nm.get(sn, sn)); ed.setFixedWidth(180)
                    h.addWidget(ed); self._sample_edits[sn] = ed
                    c = sc.get(sn, DEFAULT_GROUP_COLORS[i % len(DEFAULT_GROUP_COLORS)])
                    sc[sn] = c
                    btn = QPushButton(); btn.setFixedSize(26, 20)
                    btn.setStyleSheet(f"background-color:{c}; border:1px solid black;")
                    btn.clicked.connect(lambda _, s=sn, b=btn: self._pick_color(s, b))
                    h.addWidget(btn); h.addStretch()
                    w = QWidget(); w.setLayout(h); v3.addWidget(w)
                    self._sample_btns[sn] = (btn, c)
                self._sample_colors = sc
                lay.addWidget(g3)

        # ── Font ──────────────────────────────────────────────────────
        self._font_grp = FontSettingsGroup(self._cfg)
        lay.addWidget(self._font_grp.build())

        # ── Export / appearance ───────────────────────────────────────
        self._export_grp = ExportSettingsGroup(self._cfg)
        lay.addWidget(self._export_grp.build())

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _pick_color(self, sn, btn):
        """
        Args:
            sn (Any): The sn.
            btn (Any): The btn.
        """
        c = QColorDialog.getColor(QColor(self._sample_colors.get(sn, '#3B82F6')), self)
        if c.isValid():
            self._sample_colors[sn] = c.name()
            btn.setStyleSheet(f"background-color:{c.name()}; border:1px solid black;")

    def collect(self) -> dict:
        """
        Returns:
            dict: Result of the operation.
        """
        d = {
            'data_type_display': self.dtype_combo.currentText(),
            'aggregation':       self.agg_combo.currentText(),
            'log_scale':         self.log_cb.isChecked(),
            'show_individual':   self.indiv_cb.isChecked(),
            'show_mean_circle':  self.circle_cb.isChecked(),
            'show_values':       self.vals_cb.isChecked(),
            'dot_size':          self.dot_spin.value(),
            'dot_alpha':         self.dot_alpha.value(),
            'circle_size':       self.circle_size.value(),
            'jitter':            self.jitter_spin.value(),
            'label_mode':        self.label_mode_combo.currentText(),
        }
        d.update(self._font_grp.collect())
        d.update(self._export_grp.collect())
        if self._sample_colors:
            d['sample_colors'] = dict(self._sample_colors)
        if self._sample_edits:
            d['sample_name_mappings'] = {k: v.text() for k, v in self._sample_edits.items()}
        return d


# ── Display Dialog ─────────────────────────────────────────────────────

class ConcentrationDisplayDialog(QDialog):
    """Matplotlib-based concentration strip-chart with drag support."""

    def __init__(self, node, parent_window=None):
        """
        Args:
            node (Any): Tree or graph node.
            parent_window (Any): The parent window.
        """
        super().__init__(parent_window)
        self.node = node
        self.setWindowTitle("Concentration Comparison Plot")
        self.setMinimumSize(950, 700)
        self._build_ui()
        self._refresh()
        self.node.configuration_changed.connect(self._refresh)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        self._info = QLabel("")
        self._info.setStyleSheet("color:#94A3B8; font-size:11px; padding:2px 6px;")
        lay.addWidget(self._info)

        self.figure = Figure(figsize=(12, 8), dpi=120, tight_layout=True)
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
        for dt in CONC_DATA_TYPES:
            a = dm.addAction(dt); a.setCheckable(True)
            a.setChecked(cfg.get('data_type_display') == dt)
            a.triggered.connect(lambda _, v=dt: self._set('data_type_display', v))

        am = menu.addMenu("Aggregation")
        for m in CONC_AGG_METHODS:
            a = am.addAction(m); a.setCheckable(True)
            a.setChecked(cfg.get('aggregation') == m)
            a.triggered.connect(lambda _, v=m: self._set('aggregation', v))

        tm = menu.addMenu("Quick Toggles")
        for key, label in [
            ('log_scale',        'Log Scale'),
            ('show_individual',  'Show Individual Points'),
            ('show_mean_circle', 'Show Mean Markers'),
            ('show_values',      'Show Numeric Values'),
        ]:
            a = tm.addAction(label); a.setCheckable(True)
            a.setChecked(cfg.get(key, False))
            a.triggered.connect(lambda _, k=key: self._toggle(k))

        lm = menu.addMenu("Label Mode")
        for mode in LABEL_MODES:
            a = lm.addAction(mode); a.setCheckable(True)
            a.setChecked(cfg.get('label_mode', 'Symbol') == mode)
            a.triggered.connect(lambda _, v=mode: self._set('label_mode', v))

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
        download_matplotlib_figure(self.figure, self, "concentration_comparison")

    def _open_settings(self):
        dlg = ConcentrationSettingsDialog(self.node.config, self.node.input_data, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._refresh()

    # ── Refresh / draw ─────────────────────────────────────────────────

    def _refresh(self):
        try:
            cfg = self.node.config

            if cfg.get('use_custom_figsize', False):
                self.figure.set_size_inches(cfg.get('figsize_w', 12.0),
                                            cfg.get('figsize_h', 8.0))
            self.figure.clear()
            self.figure.patch.set_facecolor(cfg.get('bg_color', '#FFFFFF'))

            data = self.node.extract_concentration_data()

            if not data:
                ax = self.figure.add_subplot(111)
                ax.text(0.5, 0.5,
                        'No data available\nConnect to a Sample Selector node.',
                        ha='center', va='center', transform=ax.transAxes,
                        fontsize=12, color='gray')
                ax.axis('off')
                self._info.setText("")
                self.canvas.draw()
                return

            self._draw_chart(data, cfg)

            n_el  = len(data['elements'])
            n_grp = len(data['groups'])
            self._info.setText(
                f"{n_el} elements · {n_grp} group(s) · "
                f"{data.get('subtitle', '')}")

            self.figure.tight_layout()
            self.canvas.draw()
            self.canvas.snapshot_positions()

        except Exception as e:
            print(f"Error refreshing concentration plot: {e}")
            import traceback; traceback.print_exc()

    # ── Core drawing ───────────────────────────────────────────────────

    def _draw_chart(self, data, cfg):
        """Draw the horizontal strip chart onto self.figure.
        Args:
            data (Any): Input data.
            cfg (Any): The cfg.
        """
        elements   = data['elements']
        groups     = data['groups']
        group_names = list(groups.keys())
        n_el       = len(elements)
        n_grp      = len(group_names)

        fc         = get_font_config(cfg)
        label_mode = cfg.get('label_mode', 'Symbol')
        log_scale  = cfg.get('log_scale', True)
        show_indiv = cfg.get('show_individual', True)
        show_circ  = cfg.get('show_mean_circle', True)
        show_vals  = cfg.get('show_values', True)
        dot_size   = cfg.get('dot_size', 5)
        dot_alpha  = cfg.get('dot_alpha', 0.4)
        circle_s   = cfg.get('circle_size', 120)
        jitter_fac = cfg.get('jitter', 0.15)
        bg         = cfg.get('bg_color', '#FFFFFF')

        y_labels = [format_element_label(e, label_mode) for e in elements]
        y_pos = list(range(n_el - 1, -1, -1))

        min_h = max(4.0, n_el * 0.38 + 1.5)
        cur_h = self.figure.get_size_inches()[1]
        if not cfg.get('use_custom_figsize', False):
            self.figure.set_size_inches(self.figure.get_size_inches()[0],
                                        max(cur_h, min_h))

        ax = self.figure.add_subplot(111)
        ax.set_facecolor(bg)

        all_vals = []
        for gd in groups.values():
            for el in elements:
                all_vals.extend([v for v in gd['values'].get(el, []) if v > 0])

        if not all_vals:
            ax.text(0.5, 0.5, 'No positive values to display',
                    ha='center', va='center', transform=ax.transAxes, color='gray')
            return

        if log_scale:
            ax.set_xscale('log')
            ax.xaxis.set_major_formatter(mticker.LogFormatterSciNotation(base=10))

        # ── Draw per element row ────────────────────────────────────────
        rng = np.random.default_rng(42)

        for ei, (el, yp) in enumerate(zip(elements, y_pos)):
            if ei % 2 == 0:
                band_color = '#F8F9FA' if bg == '#FFFFFF' else '#00000008'
                ax.axhspan(yp - 0.5, yp + 0.5, color=band_color, zorder=0)

            offsets = np.linspace(-jitter_fac * 0.5 * (n_grp - 1),
                                   jitter_fac * 0.5 * (n_grp - 1), n_grp) \
                      if n_grp > 1 else [0.0]

            for gi, gn in enumerate(group_names):
                gd     = groups[gn]
                color  = gd['color']
                vals   = [v for v in gd['values'].get(el, []) if v > 0]
                agg_v  = gd['agg'].get(el, 0)
                y_off  = offsets[gi]

                if show_indiv and vals:
                    jit = rng.uniform(-jitter_fac, jitter_fac, size=len(vals))
                    ys  = yp + y_off + jit
                    ax.scatter(vals, ys,
                               s=dot_size ** 2,
                               color=color, alpha=dot_alpha,
                               linewidths=0, zorder=2)

                if show_circ and agg_v > 0:
                    ax.scatter([agg_v], [yp + y_off],
                               s=circle_s,
                               facecolors='none',
                               edgecolors=color,
                               linewidths=2.0,
                               zorder=4)

                if show_vals and agg_v > 0:
                    ax.annotate(
                        _fmt_val(agg_v),
                        xy=(1.0, yp + y_off),
                        xycoords=('axes fraction', 'data'),
                        xytext=(8 + gi * 60, 0),
                        textcoords='offset points',
                        va='center', ha='left',
                        fontsize=max(6, fc['size'] - 2),
                        color=color,
                        fontfamily=fc['family'],
                        fontweight='bold' if fc['bold'] else 'normal',
                        zorder=5,
                    )

        # ── Y axis (element labels) ─────────────────────────────────────
        ax.set_yticks(y_pos)
        ax.set_yticklabels(
            y_labels,
            fontsize=fc['size'],
            fontfamily=fc['family'],
            fontweight='bold' if fc['bold'] else 'normal',
            color=fc['color'],
        )
        ax.set_ylim(-0.6, n_el - 0.4)

        # ── X axis ─────────────────────────────────────────────────────
        unit = data.get('unit', '')
        ax.set_xlabel(unit, fontsize=fc['size'], color=fc['color'],
                      fontfamily=fc['family'],
                      fontweight='bold' if fc['bold'] else 'normal')
        ax.tick_params(axis='x', labelsize=max(7, fc['size'] - 1),
                       colors=fc['color'])
        ax.tick_params(axis='y', length=0)

        # ── Title ──────────────────────────────────────────────────────
        title = data.get('title', '')
        if title:
            ax.set_title(title, fontsize=fc['size'] + 2, color=fc['color'],
                         fontfamily=fc['family'],
                         fontweight='bold' if fc['bold'] else 'normal', pad=10)

        # ── Legend ─────────────────────────────────────────────────────
        if n_grp > 1:
            import matplotlib.lines as mlines
            handles = [
                mlines.Line2D([], [], color=groups[gn]['color'],
                              marker='o', markersize=7, linestyle='none',
                              markerfacecolor='none', markeredgewidth=2,
                              label=get_display_name(gn, cfg))
                for gn in group_names
            ]
            ax.legend(handles=handles,
                      fontsize=max(7, fc['size'] - 1),
                      loc='upper right', framealpha=0.8)

        ax.grid(axis='x', linestyle='--', alpha=0.35, zorder=1)
        ax.set_axisbelow(True)

        if show_vals and n_grp:
            extra = 0.04 + n_grp * 0.08
            ax.set_position([ax.get_position().x0,
                             ax.get_position().y0,
                             ax.get_position().width * (1 - extra),
                             ax.get_position().height])

        apply_font_to_matplotlib(ax, cfg)


# ── Node ───────────────────────────────────────────────────────────────

class ConcentrationComparisonNode(QObject):
    position_changed      = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        """
        Args:
            parent_window (Any): The parent window.
        """
        super().__init__()
        self.title           = "Concentration"
        self.node_type       = "concentration_comparison"
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
        dlg = ConcentrationDisplayDialog(self, parent_window)
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

    def extract_concentration_data(self):
        """
        Returns:
            None
        """
        if not self.input_data:
            return None

        data_key   = CONC_DATA_KEY_MAP.get(
            self.config.get('data_type_display', 'Counts'), 'elements')
        agg_method = self.config.get('aggregation', 'Mean')
        unit       = CONC_LABEL_MAP.get(
            self.config.get('data_type_display', 'Counts'), '')
        itype      = self.input_data.get('type')
        elements   = self._get_elements()
        if not elements:
            return None

        if itype == 'sample_data':
            return self._extract_single(data_key, elements, agg_method, unit)
        elif itype == 'multiple_sample_data':
            return self._extract_multi(data_key, elements, agg_method, unit)
        return None

    def _extract_single(self, data_key, elements, agg_method, unit):
        """
        Args:
            data_key (Any): The data key.
            elements (Any): The elements.
            agg_method (Any): The agg method.
            unit (Any): The unit.
        Returns:
            dict: Result of the operation.
        """
        particles = self.input_data.get('particle_data', [])
        if not particles:
            return None
        sname = self.input_data.get('sample_name', 'Sample')
        color = self.config.get('sample_colors', {}).get(sname, DEFAULT_GROUP_COLORS[0])

        vals_by_el = {}
        agg_by_el  = {}
        for el in elements:
            vs = [p.get(data_key, {}).get(el, 0) for p in particles]
            vs = [v for v in vs if v > 0 and not (isinstance(v, float) and np.isnan(v))]
            vals_by_el[el] = vs
            agg_by_el[el]  = _agg(vs, agg_method)

        return {
            'elements': elements,
            'groups': {
                sname: {'color': color, 'values': vals_by_el, 'agg': agg_by_el}
            },
            'title':    f"{agg_method} — {sname}",
            'subtitle': f"Open circle = {agg_method.lower()}, dots = individual · {unit}",
            'unit':     unit,
        }

    def _extract_multi(self, data_key, elements, agg_method, unit):
        """
        Args:
            data_key (Any): The data key.
            elements (Any): The elements.
            agg_method (Any): The agg method.
            unit (Any): The unit.
        Returns:
            dict: Result of the operation.
        """
        particles = self.input_data.get('particle_data', [])
        names     = self.input_data.get('sample_names', [])
        if not particles or not names:
            return None

        sc     = self.config.get('sample_colors', {})
        groups = {}
        for gi, sn in enumerate(names):
            sp = [p for p in particles if p.get('source_sample') == sn]
            if not sp:
                continue
            color      = sc.get(sn, DEFAULT_GROUP_COLORS[gi % len(DEFAULT_GROUP_COLORS)])
            vals_by_el = {}
            agg_by_el  = {}
            for el in elements:
                vs = [p.get(data_key, {}).get(el, 0) for p in sp]
                vs = [v for v in vs if v > 0 and not (isinstance(v, float) and np.isnan(v))]
                vals_by_el[el] = vs
                agg_by_el[el]  = _agg(vs, agg_method)
            groups[sn] = {'color': color, 'values': vals_by_el, 'agg': agg_by_el}

        if not groups:
            return None

        labels = ' vs '.join(get_display_name(n, self.config) for n in groups)
        return {
            'elements': elements,
            'groups':   groups,
            'title':    f"{agg_method} — {labels}",
            'subtitle': f"Open circle = {agg_method.lower()}, dots = individual · {unit}",
            'unit':     unit,
        }