"""Figure Builder canvas node and its window.

The window has three areas: the layout page where panels are drawn
(:class:`~results.figure_builder.sketch.LayoutSketch`) with the tabbed
settings of the selected panel underneath
(:class:`~results.figure_builder.editor.PanelEditor`); a live preview
rendered at the figure's real size, so what is shown is exactly what is
exported; and, below the preview, tabs for statistics, the particle data
and user-defined variables.
"""

from __future__ import annotations

import copy
import io
import json
import time

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QObject, QPoint, QRectF, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor, QIcon, QImage, QKeySequence, QPainter, QPen, QPixmap, QShortcut)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFontComboBox, QFormLayout, QFrame,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox,
    QPlainTextEdit, QPushButton, QSizePolicy, QSpinBox, QSplitter, QTabWidget,
    QTextBrowser, QToolButton, QVBoxLayout, QWidget,
)

from results.figure_builder.core import engine as E
from results.figure_builder.core import styles as S
from results.figure_builder.ui.dataview import DataExplorer
from results.figure_builder.ui import interact
from results.figure_builder.ui.editor import PanelEditor
from results.figure_builder.core.expressions import DATA_TYPES, ParticleTable
from results.figure_builder.ui.sketch import LayoutSketch
from results.figure_builder.ui.widgets import ColorButton, RowTable

import logging

_log = logging.getLogger('IsotopeTrack.results.figure_builder')

SETTINGS = ('IsotopeTrack', 'IsotopeTrack')
DESIGNS_KEY = 'figure_builder/designs'


class FigureBuilderNode(QObject):
    """Canvas node that draws a user-designed, multi-panel figure.

    The whole design lives in ``config`` (see :mod:`results.figure_builder.engine`),
    so it is saved and restored with the project like every other node.
    Classifier streams are kept as they are: classes are a grouping option.
    """

    position_changed = Signal(object)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        super().__init__()
        self.title = 'Figure Builder'
        self.node_type = 'figure_builder'
        self.parent_window = parent_window
        self.position = None
        self._has_input = True
        self._has_output = False
        self.input_channels = ['input']
        self.output_channels = []
        self.config = E.default_spec()
        self.input_data = None

    def set_position(self, pos):
        """Move the node and notify the canvas."""
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def configure(self, parent_window):
        """Open this node's window, reusing one persistent window."""
        from results.shared_plot_utils import show_persistent_figure
        return show_persistent_figure(self, lambda: FigureBuilderDialog(self, parent_window))

    def process_data(self, input_data):
        """Receive the upstream stream and fill empty axes with the first isotopes."""
        if not input_data:
            return
        self.input_data = input_data
        self.config = E.normalise_spec(self.config)
        table = ParticleTable.from_input(input_data, self.config.get('data_type', 'Counts'))
        for panel in self.config['panels']:
            fill_panel_defaults(panel, table)
        self.configuration_changed.emit()

    def build_table(self) -> ParticleTable:
        """Return the particle table for the current data and quantity."""
        table = ParticleTable.from_input(self.input_data, self.config.get('data_type', 'Counts'))
        table.set_variables(self.config.get('variables'))
        return table


def fill_panel_defaults(panel: dict | None, table: ParticleTable) -> dict | None:
    """Pre-fill a panel's empty data fields with isotopes from the stream."""
    labs = table.labels
    if not labs or panel is None:
        return panel
    second = labs[1] if len(labs) > 1 else labs[0]
    kind = panel.get('kind')
    if kind in ('scatter', 'density'):
        panel['x'] = panel.get('x') or labs[0]
        panel['y'] = panel.get('y') or second
    elif kind == 'line':
        panel['x'] = panel.get('x') or 'time'
    elif kind in ('histogram', 'box', 'violin', 'bar'):
        panel['value'] = panel.get('value') or labs[0]
    elif kind == 'pie' and panel.get('pie_mode') == 'values':
        panel['value'] = panel.get('value') or ', '.join(labs[:6])
    elif kind == 'ternary':
        for key, lab in zip('abc', (labs * 3)[:3]):
            panel[key] = panel.get(key) or lab
    return panel


HELP_HTML = """
<h3>Drawing the layout</h3>
<p>Drag on the page to draw a panel. <b>Shift-drag</b> draws on top of another panel (insets).
Drag a panel to move it, its corner to resize it; arrow keys nudge the selected panel
(Shift + arrows resize). Right-click a panel to change its type, duplicate, restack or delete.
Click a panel in the preview to edit it.</p>
<h3>Writing expressions</h3>
<p>Every box marked X, Y, Value, Condition… takes a small formula evaluated for
<b>each particle</b>. Click the coloured chips to insert names.</p>
<table cellpadding="3">
<tr><td><code>Fe</code>, <code>56Fe</code></td><td>the isotope, in the quantity chosen at the top (counts, mass…). A bare symbol works when only one isotope has it.</td></tr>
<tr><td><code>Fe/Cu</code>, <code>Ag + Au</code></td><td>arithmetic: + − * / ** and brackets</td></tr>
<tr><td><code>mass:Fe</code></td><td>another quantity: <code>counts:</code> <code>mass:</code> <code>moles:</code> <code>pmass:</code> <code>pmoles:</code> <code>d:</code> (diameter) <code>pd:</code></td></tr>
<tr><td><code>total</code></td><td>sum over all isotopes of the particle, e.g. <code>100*Fe/total</code> for a percentage</td></tr>
<tr><td><code>n_elements</code></td><td>number of detected isotopes in the particle</td></tr>
<tr><td><code>sample</code>, <code>class</code>, <code>time</code></td><td>sample name, classifier class and particle time, e.g. <code>sample == "Blank"</code></td></tr>
<tr><td><code>log(Fe)</code> <code>ln</code> <code>sqrt</code> <code>abs</code> <code>exp</code></td><td>functions (log is base 10)</td></tr>
<tr><td><code>median(Fe)</code> <code>mean</code> <code>std</code> <code>percentile(Fe, 90)</code></td><td>one number over all particles, handy for thresholds</td></tr>
<tr><td><code>Fe &lt; 10</code>, <code>Fe &gt; 0 and Cu &gt; 0</code></td><td>conditions for rules and filters (<code>and</code>, <code>or</code>, <code>not</code>)</td></tr>
<tr><td><code>sample in ["A", "B"]</code></td><td>membership</td></tr>
<tr><td><code>where(Fe &gt; 0, Fe, nan)</code></td><td>pick values by condition</td></tr>
<tr><td><code>`odd name`</code></td><td>backticks for any column with spaces or symbols</td></tr>
</table>
<h3>Your own variables</h3>
<p>In the <b>Variables</b> tab under the preview, define names such as
<code>ratio = Fe/Cu</code> or <code>pctFe = 100*Fe/total</code> once and use them in every panel,
rule and filter. Variables may use other variables.</p>
<h3>Colour by a condition</h3>
<p>In the <b>Groups</b> tab set <i>Group / colour by</i> to <b>By my rules</b>, then add rules such as
<code>Fe/Cu &lt; 0.5</code> → red. The first rule that matches wins; everything else is grey “Other”.
Samples, classes and rules can all be hidden, renamed, recoloured and reordered.</p>
<h3>Statistics</h3>
<p>Box, violin, bar and histogram panels compare their groups with a t-test, Mann-Whitney, KS,
ANOVA or Kruskal-Wallis (with Holm or Bonferroni correction). Results are listed in the
<b>Statistics</b> tab and drawn as brackets. Scatter panels can show a fit line with r and R².</p>
<h3>Designs</h3>
<p><b>Designs ▸ Save current design</b> stores the whole figure (layout, styles, variables) so you can
apply it to another sample in one click, or export it to a file to share.</p>
<h3>Anything else</h3>
<p>Choose <b>Python code</b> as the chart type to draw with matplotlib yourself:
<code>ax</code>, <code>df</code>, <code>groups</code> and <code>col("Fe/Cu")</code> are ready to use.</p>
"""


def _icon(name: str, color: str = '#374151') -> QIcon:
    """A qtawesome icon, or an empty icon when unavailable."""
    try:
        import qtawesome as qta
        return qta.icon(name, color=color)
    except Exception:
        return QIcon()


def _swatch_icon(colors, w=64, h=14) -> QIcon:
    """An icon showing a strip of palette colours."""
    pm = QPixmap(w, h)
    pm.fill(Qt.transparent)
    qp = QPainter(pm)
    step = w / max(1, len(colors))
    for i, c in enumerate(colors):
        qp.fillRect(int(i * step), 0, int(step) + 1, h, QColor(c))
    qp.end()
    return QIcon(pm)


class FigureSettingsDialog(QDialog):
    """Page size, fonts, text sizes, title, palette and panel letters."""

    def __init__(self, figcfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Figure settings')
        self.cfg = dict(figcfg)
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignRight)
        self.width = QDoubleSpinBox()
        self.width.setRange(1, 40)
        self.width.setDecimals(2)
        self.width.setSuffix(' in')
        self.width.setValue(float(self.cfg['width']))
        self.height = QDoubleSpinBox()
        self.height.setRange(1, 40)
        self.height.setDecimals(2)
        self.height.setSuffix(' in')
        self.height.setValue(float(self.cfg['height']))
        self.cm = QLabel('')
        size = QWidget()
        sl = QHBoxLayout(size)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self.width)
        sl.addWidget(QLabel('×'))
        sl.addWidget(self.height)
        sl.addWidget(self.cm)
        self.width.valueChanged.connect(self._update_cm)
        self.height.valueChanged.connect(self._update_cm)
        self._update_cm()
        form.addRow('Size', size)
        preset = QComboBox()
        preset.addItem('Choose a preset size…', None)
        for name, wh in S.SIZE_PRESETS.items():
            preset.addItem(name, wh)
        preset.currentIndexChanged.connect(
            lambda _i: preset.currentData() and (self.width.setValue(preset.currentData()[0]),
                                                 self.height.setValue(preset.currentData()[1])))
        form.addRow('', preset)
        self.title = QLineEdit(self.cfg.get('title', ''))
        self.title.setPlaceholderText('optional')
        form.addRow('Figure title', self.title)
        self.font = QFontComboBox()
        self.font.setCurrentText(self.cfg.get('font_family') or 'DejaVu Sans')
        form.addRow('Font', self.font)
        self.font_size = self._spin(int(self.cfg.get('font_size') or 11), 5, 48)
        form.addRow('Base text size', self.font_size)
        self.title_size = self._spin(int(self.cfg.get('title_size') or 0), 0, 60, 'auto')
        form.addRow('Panel titles', self.title_size)
        self.label_size = self._spin(int(self.cfg.get('label_size') or 0), 0, 60, 'auto')
        form.addRow('Axis labels', self.label_size)
        self.tick_size = self._spin(int(self.cfg.get('tick_size') or 0), 0, 60, 'auto')
        form.addRow('Tick labels', self.tick_size)
        self.axes_lw = QDoubleSpinBox()
        self.axes_lw.setRange(0.2, 4)
        self.axes_lw.setSingleStep(0.1)
        self.axes_lw.setValue(float(self.cfg.get('axes_linewidth') or 0.8))
        form.addRow('Axis line width', self.axes_lw)
        self.palette = QComboBox()
        for name, cols in S.PALETTES.items():
            self.palette.addItem(_swatch_icon(cols), name, name)
        self.palette.setIconSize(QSize(64, 14))
        self.palette.setCurrentIndex(max(0, self.palette.findData(self.cfg.get('palette', 'Default'))))
        form.addRow('Colour palette', self.palette)
        self.letters = QCheckBox('Label panels')
        self.letters.setChecked(bool(self.cfg.get('panel_letters', True)))
        self.letter_style = QComboBox()
        for k in ('a', 'A', '(a)', '(A)', 'a)'):
            self.letter_style.addItem(k, k)
        self.letter_style.setCurrentIndex(max(0, self.letter_style.findData(self.cfg.get('letter_style', 'a'))))
        self.letter_size = self._spin(int(self.cfg.get('letter_size') or 0), 0, 60, 'auto')
        lw = QWidget()
        ll = QHBoxLayout(lw)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(self.letters)
        ll.addWidget(self.letter_style)
        ll.addWidget(QLabel('size'))
        ll.addWidget(self.letter_size)
        ll.addStretch()
        form.addRow('Panel letters', lw)
        self.label_style = QComboBox()
        for k, label in [('isotope', 'Isotope (¹⁰⁷Ag)'), ('symbol', 'Symbol (Ag)'),
                         ('raw', 'As written (107Ag)')]:
            self.label_style.addItem(label, k)
        self.label_style.setCurrentIndex(max(0, self.label_style.findData(self.cfg.get('label_style', 'isotope'))))
        form.addRow('Isotope labels', self.label_style)
        self.bg = ColorButton(self.cfg.get('background') or '#ffffff')
        form.addRow('Background', self.bg)
        self.dpi = QSpinBox()
        self.dpi.setRange(72, 1200)
        self.dpi.setValue(int(self.cfg.get('dpi') or 300))
        form.addRow('Copy resolution (dpi)', self.dpi)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    @staticmethod
    def _spin(value, lo, hi, special=None):
        s = QSpinBox()
        s.setRange(lo, hi)
        if special:
            s.setSpecialValueText(special)
        s.setValue(value)
        return s

    def _update_cm(self):
        self.cm.setText(f'= {self.width.value() * 2.54:.1f} × {self.height.value() * 2.54:.1f} cm')

    def collect(self) -> dict:
        """Return the edited figure settings."""
        out = dict(self.cfg)
        out.update(width=self.width.value(), height=self.height.value(),
                   title=self.title.text(), font_family=self.font.currentText(),
                   font_size=self.font_size.value(), title_size=self.title_size.value(),
                   label_size=self.label_size.value(), tick_size=self.tick_size.value(),
                   axes_linewidth=self.axes_lw.value(), palette=self.palette.currentData(),
                   panel_letters=self.letters.isChecked(),
                   letter_style=self.letter_style.currentData(),
                   letter_size=self.letter_size.value(),
                   label_style=self.label_style.currentData(),
                   background=self.bg.color() or '#ffffff', dpi=self.dpi.value())
        return out


class PreviewLabel(QLabel):
    """Shows the rendered figure scaled to fit and reports where the user clicks.

    Coordinates are figure fractions with the origin at the top-left.

    Signals:
        resized(): the widget changed size.
        clicked(float, float): left click.
        double_clicked(float, float): double click.
        context_requested(float, float, QPoint): right click, with the global position.
    """

    resized = Signal()
    clicked = Signal(float, float)
    double_clicked = Signal(float, float)
    context_requested = Signal(float, float, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setToolTip('Click to select · double-click text to rename it · right-click for options')
        self._pixmap = None
        self._shown = None
        self._selection = None

    def set_figure_pixmap(self, pm: QPixmap):
        """Store and display a freshly rendered pixmap."""
        self._pixmap = pm
        self._rescale()

    def set_selection(self, rect):
        """Outline ``rect`` (figure fractions, top-left origin), or nothing when None."""
        self._selection = rect
        self.update()

    def _rescale(self):
        if self._pixmap is None:
            return
        dpr = self.devicePixelRatioF()
        target = QSize(int(self.width() * dpr), int(self.height() * dpr))
        pm = self._pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pm.setDevicePixelRatio(dpr)
        self._shown = pm
        self.setPixmap(pm)

    def _geometry(self):
        if self._shown is None:
            return None
        dpr = self._shown.devicePixelRatio()
        w, h = self._shown.width() / dpr, self._shown.height() / dpr
        return (self.width() - w) / 2, (self.height() - h) / 2, w, h

    def _to_fraction(self, pos):
        g = self._geometry()
        if g is None:
            return None
        x0, y0, w, h = g
        fx = (pos.x() - x0) / max(1.0, w)
        fy = (pos.y() - y0) / max(1.0, h)
        if 0 <= fx <= 1 and 0 <= fy <= 1:
            return fx, fy
        return None

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._rescale()
        self.resized.emit()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        g = self._geometry()
        if g is None or not self._selection:
            return
        x0, y0, w, h = g
        x, y, rw, rh = self._selection
        qp = QPainter(self)
        pen = QPen(QColor('#2a78d6'), 1.6, Qt.DashLine)
        qp.setPen(pen)
        qp.setBrush(Qt.NoBrush)
        qp.drawRect(QRectF(x0 + x * w + 1, y0 + y * h + 1, rw * w - 2, rh * h - 2))
        qp.end()

    def mousePressEvent(self, ev):
        pt = self._to_fraction(ev.position())
        if pt is None:
            return super().mousePressEvent(ev)
        if ev.button() == Qt.LeftButton:
            self.clicked.emit(*pt)
        elif ev.button() == Qt.RightButton:
            self.context_requested.emit(pt[0], pt[1], ev.globalPosition().toPoint())

    def mouseDoubleClickEvent(self, ev):
        pt = self._to_fraction(ev.position())
        if pt is not None and ev.button() == Qt.LeftButton:
            self.double_clicked.emit(*pt)


def render_to_pixmap(spec: dict, table: ParticleTable, dpi: float):
    """Render ``spec`` off-screen and return ``(QPixmap, RenderReport, Figure)``."""
    fig = Figure()
    FigureCanvasAgg(fig)
    fig.set_dpi(dpi)
    report = E.render(fig, spec, table)
    fig.set_dpi(dpi)
    canvas = fig.canvas
    canvas.draw()
    buf = np.asarray(canvas.buffer_rgba())
    h, w, _ = buf.shape
    img = QImage(buf.tobytes(), w, h, 4 * w, QImage.Format_RGBA8888).copy()
    return QPixmap.fromImage(img), report, fig


class FigureBuilderDialog(QDialog):
    """Window where a figure is designed panel by panel."""

    def __init__(self, node: FigureBuilderNode, parent_window=None):
        super().__init__(parent_window)
        self.node = node
        self.parent_window = parent_window
        self.setWindowTitle('Figure Builder')
        self.setMinimumSize(1200, 760)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        node.config = E.normalise_spec(node.config)
        self.spec = node.config
        self.table = node.build_table()
        self._last_report = E.RenderReport()
        self.last_fig = None
        self._hits = []
        self._history: list[str] = []
        self._hindex = -1
        self._restoring = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(220)
        self._timer.timeout.connect(self._render)
        self._build_ui()
        self._shortcuts()
        self.node.configuration_changed.connect(self._on_node_data)
        first = self.spec['panels'][0]['id'] if self.spec['panels'] else ''
        self.sketch.select(first)
        self._on_select(first)
        self._push_history()
        self._schedule()

    def _tool(self, text, icon, tip, slot=None, menu=None):
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setIcon(_icon(icon))
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        b.setAutoRaise(True)
        if menu is not None:
            b.setMenu(menu)
            b.setPopupMode(QToolButton.InstantPopup)
        if slot is not None:
            b.clicked.connect(slot)
        return b

    def _sep(self):
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setStyleSheet('color: #d1d5db;')
        return line

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(6)
        bar = QHBoxLayout()
        bar.setSpacing(2)
        self.sidebar_btn = self._tool('', 'fa6s.table-columns', 'Show or hide the settings sidebar',
                                      self._toggle_sidebar)
        self.sidebar_btn.setCheckable(True)
        self.sidebar_btn.setChecked(True)
        bar.addWidget(self.sidebar_btn)
        bar.addWidget(self._sep())
        self.undo_btn = self._tool('', 'fa6s.rotate-left', 'Undo (Ctrl+Z)', self.undo)
        self.redo_btn = self._tool('', 'fa6s.rotate-right', 'Redo (Ctrl+Shift+Z)', self.redo)
        bar.addWidget(self.undo_btn)
        bar.addWidget(self.redo_btn)
        bar.addWidget(self._sep())
        add_menu = QMenu(self)
        for key, label in E.PANEL_KINDS.items():
            add_menu.addAction(label, lambda k=key: self.add_panel(k))
        bar.addWidget(self._tool('Add panel', 'fa6s.square-plus', 'Add a panel of a given type',
                                 menu=add_menu))
        layout_menu = QMenu(self)
        for name in S.TEMPLATES:
            layout_menu.addAction(name, lambda n=name: self._apply_template(n))
        layout_menu.addSeparator()
        layout_menu.addAction('Clear page', self._clear)
        bar.addWidget(self._tool('Layouts', 'fa6s.table-cells-large', 'Ready-made layouts',
                                 menu=layout_menu))
        bar.addWidget(self._sep())
        bar.addWidget(self._tool('Figure', 'fa6s.sliders', 'Size, fonts, palette, panel letters',
                                 self._figure_settings))
        bar.addWidget(self._tool('Text', 'fa6s.font', 'Bold, italic, size and colour of every text '
                                 'in the whole figure', self._figure_text_styles))
        style_menu = QMenu(self)
        for name in S.STYLE_PRESETS:
            style_menu.addAction(name, lambda n=name: self._apply_style(n))
        bar.addWidget(self._tool('Style', 'fa6s.wand-magic-sparkles',
                                 'Apply a style to the whole figure', menu=style_menu))
        self.palette_menu = QMenu(self)
        for name, cols in S.PALETTES.items():
            act = self.palette_menu.addAction(_swatch_icon(cols), name)
            act.triggered.connect(lambda _=False, n=name: self._set_palette(n))
        bar.addWidget(self._tool('Colours', 'fa6s.palette', 'Colour palette for groups',
                                 menu=self.palette_menu))
        bar.addWidget(self._sep())
        self.designs_menu = QMenu(self)
        self.designs_menu.aboutToShow.connect(self._fill_designs_menu)
        bar.addWidget(self._tool('Designs', 'fa6s.bookmark',
                                 'Save this figure design and reuse it on other data',
                                 menu=self.designs_menu))
        bar.addWidget(self._tool('Help', 'fa6s.circle-question', 'How to write expressions and more',
                                 self._help))
        bar.addSpacing(12)
        bar.addWidget(QLabel('Default quantity'))
        self.data_type = QComboBox()
        for k in DATA_TYPES:
            self.data_type.addItem(k, k)
        self.data_type.setCurrentIndex(max(0, self.data_type.findData(self.spec.get('data_type', 'Counts'))))
        self.data_type.setToolTip('What a bare isotope name such as Fe means in your expressions')
        self.data_type.currentIndexChanged.connect(self._on_data_type)
        bar.addWidget(self.data_type)
        bar.addStretch()
        self.status = QLabel('')
        self.status.setMinimumWidth(260)
        self.status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status.setStyleSheet('color: #6b7280;')
        bar.addWidget(self.status)
        bar.addWidget(self._tool('Copy', 'fa6s.copy', 'Copy the figure as an image (Ctrl+Shift+C)',
                                 self._copy))
        export = QPushButton(_icon('fa6s.file-export', '#ffffff'), ' Export figure…')
        export.setStyleSheet('QPushButton { background: #2a78d6; color: white; border: none;'
                             ' border-radius: 6px; padding: 6px 12px; font-weight: 600; }'
                             ' QPushButton:hover { background: #256abf; }')
        export.clicked.connect(self._export)
        bar.addWidget(export)
        root.addLayout(bar)

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        left = QSplitter(Qt.Vertical)
        left.setChildrenCollapsible(False)
        top = QWidget()
        tl = QVBoxLayout(top)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(2)
        self.sketch = LayoutSketch(self.spec)
        self.sketch.setToolTip('Drag to draw a panel · Shift-drag for insets · drag to move · '
                               'corner to resize · arrows nudge · right-click for more')
        self.sketch.panel_factory = self._new_panel
        self.sketch.setMinimumHeight(110)
        self.sketch.selection_changed.connect(self._on_select)
        self.sketch.layout_changed.connect(self._on_layout)
        self.sketch.kind_requested.connect(self._on_kind_requested)
        tl.addWidget(self.sketch, 1)
        left.addWidget(top)
        self.editor = PanelEditor()
        self.editor.set_table(self.table, S.palette_colors(self.spec['figure'].get('palette')))
        self.editor.changed.connect(self._schedule)
        self.editor.kind_changed.connect(self._on_editor_kind)
        self.editor.styles_requested.connect(self._panel_text_styles)
        self.editor.rename_requested.connect(
            lambda: self.after_edit(interact.rename_items(self, self.editor.panel)) if self.editor.panel else None)
        left.addWidget(self.editor)
        left.setStretchFactor(0, 1)
        left.setStretchFactor(1, 5)
        left.setSizes([150, 620])
        left.setMinimumWidth(300)
        self.left_panel = left
        split.addWidget(left)

        right = QSplitter(Qt.Vertical)
        right.setChildrenCollapsible(False)
        frame = QFrame()
        frame.setObjectName('fbPreview')
        frame.setStyleSheet('QFrame#fbPreview { background: #e5e7eb; border-radius: 8px; }')
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(10, 10, 10, 10)
        self.preview = PreviewLabel()
        self.preview.resized.connect(self._schedule)
        self.preview.clicked.connect(self._on_preview_click)
        self.preview.double_clicked.connect(self._on_preview_double)
        self.preview.context_requested.connect(self._on_preview_context)
        self.plot_widget = self.preview
        fl.addWidget(self.preview)
        right.addWidget(frame)
        self.bottom = QTabWidget()
        self.bottom.setDocumentMode(True)
        stats_page = QWidget()
        sl = QVBoxLayout(stats_page)
        sl.setContentsMargins(0, 4, 0, 0)
        self.stats_box = QPlainTextEdit()
        self.stats_box.setReadOnly(True)
        self.stats_box.setPlaceholderText('Fits, tests and p-values appear here.')
        sl.addWidget(self.stats_box)
        self.bottom.addTab(stats_page, 'Statistics')
        self.data_view = DataExplorer()
        self.data_view.set_table(self.table)
        self.bottom.addTab(self.data_view, 'Data')
        var_page = QWidget()
        vl = QVBoxLayout(var_page)
        vl.setContentsMargins(0, 4, 0, 0)
        tip = QLabel('Define your own per-particle values once and use them anywhere, '
                     'e.g. ratio = Fe/Cu or pctAg = 100*Ag/total.')
        tip.setWordWrap(True)
        tip.setStyleSheet('color: #6b7280; font-size: 11px;')
        vl.addWidget(tip)
        self.var_table = RowTable([('name', 'Name', 'text', None, 120),
                                   ('expr', 'Expression', 'expr', None, 0)],
                                  '+ Add variable',
                                  lambda i: {'name': f'var{i + 1}', 'expr': ''})
        self.var_table.set_rows(self.spec.get('variables'))
        self.var_table.set_table_source(self.table)
        self.var_table.changed.connect(self._on_variables)
        vl.addWidget(self.var_table)
        self.var_status = QLabel('')
        self.var_status.setWordWrap(True)
        self.var_status.setStyleSheet('color: #b42318;')
        vl.addWidget(self.var_status)
        vl.addStretch()
        self.bottom.addTab(var_page, 'Variables')
        right.addWidget(self.bottom)
        right.setStretchFactor(0, 5)
        right.setStretchFactor(1, 2)
        right.setSizes([720, 150])
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([360, 1060])
        root.addWidget(split, 1)

    def _shortcuts(self):
        for seq, slot in ((QKeySequence.Undo, self.undo), (QKeySequence.Redo, self.redo),
                          (QKeySequence('Ctrl+Shift+Z'), self.redo),
                          (QKeySequence('Ctrl+D'), self.sketch.duplicate_selected),
                          (QKeySequence('Ctrl+Shift+C'), self._copy),
                          (QKeySequence('Ctrl+E'), self._export)):
            sc = QShortcut(seq, self)
            sc.setContext(Qt.WindowShortcut)
            sc.activated.connect(slot)

    def _panel(self, pid):
        for p in self.spec['panels']:
            if p['id'] == pid:
                return p
        return None

    def _palette(self):
        return S.palette_colors(self.spec['figure'].get('palette'))

    def _new_panel(self, **kwargs):
        """Create a panel for the sketch, already pointing at real isotopes."""
        return fill_panel_defaults(E.make_panel(**kwargs), self.table)

    def add_panel(self, kind: str, at=None):
        """Add a new panel of ``kind`` (centred on ``at`` when given) and select it."""
        n = len(self.spec['panels'])
        off = 0.04 * (n % 5)
        if at is not None:
            w = h = 0.4
            x = min(1 - w, max(0.0, at[0] - w / 2))
            y = min(1 - h, max(0.0, at[1] - h / 2))
            rect = [round(x, 4), round(y, 4), w, h]
        else:
            rect = [0.25 + off, 0.25 + off, 0.5, 0.5]
        panel = self._kind_defaults(self._new_panel(kind=kind, rect=rect))
        if not self.spec['panels']:
            panel['rect'] = [0.0, 0.0, 1.0, 1.0]
        self.spec['panels'].append(panel)
        self.sketch.set_spec(self.spec)
        self.sketch.select(panel['id'])
        self._on_layout()

    def _kind_defaults(self, panel):
        """Settings that suit a chart type the moment it is chosen."""
        if panel is None:
            return panel
        kind = panel.get('kind')
        if kind == 'combinations':
            panel['horizontal'] = True
        if kind == 'pairs' and not (panel.get('isotopes') or '').strip() and len(self.table.labels) > 4:
            panel['isotopes'] = ', '.join(self.table.labels[:4])
        return fill_panel_defaults(panel, self.table)

    def _on_editor_kind(self):
        panel = self.editor.panel
        self._kind_defaults(panel)
        self.editor.set_panel(panel)
        self.sketch.update()
        self._schedule()

    def _on_select(self, pid):
        panel = self._panel(pid)
        self.editor.set_panel(panel)
        self.editor.show_error(self._last_report.errors.get(pid) if panel else None)
        self.preview.set_selection(panel['rect'] if panel else None)

    def _hit(self, fx, fy):
        hit = interact.hit_at(self._hits, fx, fy)
        if hit is None:
            for p in reversed(self.spec['panels']):
                x, y, w, h = p['rect']
                if x <= fx <= x + w and y <= fy <= y + h:
                    return interact.Hit((x, y, x + w, y + h), p['id'], 'panel')
        return hit

    def _on_preview_click(self, fx, fy):
        hit = self._hit(fx, fy)
        if hit is not None and hit.panel_id:
            self.sketch.select(hit.panel_id)

    def _on_preview_double(self, fx, fy):
        hit = self._hit(fx, fy)
        if hit is None:
            return
        if hit.panel_id:
            self.sketch.select(hit.panel_id)
        if hit.element in ('plot', 'panel'):
            self.show_editor_tab('Data')
            return
        self.after_edit(interact.edit_text(self, hit))

    def _on_preview_context(self, fx, fy, global_pos):
        hit = self._hit(fx, fy)
        if hit is not None and hit.panel_id:
            self.sketch.select(hit.panel_id)
        menu = interact.build_menu(self, hit, fx, fy)
        menu.exec(global_pos)

    @property
    def last_report(self):
        """Report of the most recent render."""
        return self._last_report

    def panel_by_id(self, pid):
        """The panel dict with id ``pid`` (or None)."""
        return self._panel(pid)

    def after_edit(self, changed=True):
        """Refresh the editor and redraw after an edit made from the preview."""
        if not changed:
            return
        self.sketch.update()
        self._on_select(self.sketch.selected)
        self._schedule()

    def show_editor_tab(self, name: str):
        """Open the sidebar on the named tab (Data, Groups, Style, Axes, Stats, Notes)."""
        if not self.left_panel.isVisible():
            self._toggle_sidebar(True)
        tabs = self.editor.tabs
        for i in range(tabs.count()):
            if tabs.tabText(i) == name and tabs.isTabVisible(i):
                tabs.setCurrentIndex(i)
                return

    def set_panel_kind(self, panel, kind: str):
        """Change a panel's chart type and fill sensible defaults."""
        self._on_kind_requested(panel['id'], kind)

    def duplicate_panel(self, panel):
        """Copy a panel, slightly offset, and select the copy."""
        self.sketch.select(panel['id'])
        self.sketch.duplicate_selected()

    def restack_panel(self, panel, front: bool):
        """Draw a panel above (or below) all the others."""
        others = [p for p in self.spec['panels'] if p['id'] != panel['id']]
        self.spec['panels'] = others + [panel] if front else [panel] + others
        self.sketch.set_spec(self.spec)
        self.after_edit(True)

    def delete_panel(self, panel):
        """Remove a panel."""
        self.spec['panels'] = [p for p in self.spec['panels'] if p['id'] != panel['id']]
        self.sketch.set_spec(self.spec)
        self.sketch.select(self.spec['panels'][0]['id'] if self.spec['panels'] else '')
        self.after_edit(True)

    def apply_layout(self, name: str):
        """Re-lay the panels onto a ready-made layout."""
        self._apply_template(name)

    def apply_style(self, name: str):
        """Apply a style preset to the whole figure."""
        self._apply_style(name)

    def open_figure_settings(self):
        """Open the figure settings dialog."""
        self._figure_settings()

    def _toggle_sidebar(self, checked=None):
        show = (not self.left_panel.isVisible()) if checked is None else bool(checked)
        self.left_panel.setVisible(show)
        self.sidebar_btn.setChecked(show)
        self._schedule()

    def _panel_text_styles(self):
        from results.figure_builder.core import textstyle as T
        panel = self.editor.panel
        if panel is None:
            return
        elements = T.KIND_ELEMENTS.get(panel['kind'], list(T.PANEL_ELEMENTS))
        self.after_edit(interact.style_dialog(self, panel, elements, 'Text styles — this panel'))

    def _figure_text_styles(self):
        from results.figure_builder.core import textstyle as T
        self.after_edit(interact.style_dialog(self, None, list(T.ALL_ELEMENTS),
                                              'Text styles — whole figure'))

    def _on_layout(self):
        self._on_select(self.sketch.selected)
        self._schedule()

    def _on_kind_requested(self, pid, kind):
        panel = self._panel(pid)
        if panel is None:
            return
        panel['kind'] = kind
        if kind == 'code' and not (panel.get('code') or '').strip():
            panel['code'] = E.CODE_EXAMPLE
        self._kind_defaults(panel)
        self._on_select(pid)
        self.sketch.update()
        self._schedule()

    def _on_data_type(self, _i):
        self.spec['data_type'] = self.data_type.currentData()
        self._reload_table()

    def _on_variables(self):
        self.spec['variables'] = [r for r in self.var_table.rows()
                                  if (r.get('name') or '').strip() or (r.get('expr') or '').strip()]
        problems = self.table.set_variables(self.spec['variables'])
        self.var_status.setText('\n'.join(f'{k}: {v}' for k, v in problems.items()))
        self.editor.set_table(self.table, self._palette())
        self.data_view.set_table(self.table)
        self._schedule()

    def _on_node_data(self):
        if self.node.config is not self.spec:
            self._load_spec(self.node.config)
        self._reload_table()
        self._on_select(self.sketch.selected)

    def _reload_table(self):
        self.table = self.node.build_table()
        problems = self.table.set_variables(self.spec.get('variables'))
        self.var_status.setText('\n'.join(f'{k}: {v}' for k, v in problems.items()))
        self.var_table.set_table_source(self.table)
        self.editor.set_table(self.table, self._palette())
        self.data_view.set_table(self.table)
        self._schedule()

    def _load_spec(self, spec: dict, keep_selection: bool = True):
        """Replace the whole design (undo, redo, designs) and refresh every view."""
        selected = self.sketch.selected
        self.spec = E.normalise_spec(spec)
        self.node.config = self.spec
        self.sketch.set_spec(self.spec)
        self.var_table.set_rows(self.spec.get('variables'))
        self.data_type.blockSignals(True)
        self.data_type.setCurrentIndex(max(0, self.data_type.findData(self.spec.get('data_type', 'Counts'))))
        self.data_type.blockSignals(False)
        self.table = self.node.build_table()
        self.var_table.set_table_source(self.table)
        self.editor.set_table(self.table, self._palette())
        self.data_view.set_table(self.table)
        ids = [p['id'] for p in self.spec['panels']]
        pid = selected if (keep_selection and selected in ids) else (ids[0] if ids else '')
        self.sketch.selected = ''
        self.sketch.select(pid)
        self._on_select(pid)
        self._schedule()

    def _apply_template(self, name):
        new = E.apply_template(self.spec, name)
        self.spec['panels'] = [fill_panel_defaults(p, self.table) for p in new['panels']]
        self.sketch.set_spec(self.spec)
        self.sketch.select(self.spec['panels'][0]['id'])
        self._on_layout()

    def _apply_style(self, name):
        self._load_spec(S.apply_style_preset(self.spec, name))

    def _set_palette(self, name):
        self.spec['figure']['palette'] = name
        for p in self.spec['panels']:
            p['group_colors'] = {}
            if p.get('group_by', 'none') == 'none':
                p['color'] = S.palette_colors(name)[0]
        self.editor.set_table(self.table, self._palette())
        self._on_select(self.sketch.selected)
        self._schedule()

    def _clear(self):
        self.spec['panels'] = []
        self.sketch.set_spec(self.spec)
        self.sketch.select('')
        self._on_layout()

    def _figure_settings(self):
        dlg = FigureSettingsDialog(self.spec['figure'], self)
        if dlg.exec() == QDialog.Accepted:
            old_palette = self.spec['figure'].get('palette')
            self.spec['figure'] = dlg.collect()
            if self.spec['figure'].get('palette') != old_palette:
                self._set_palette(self.spec['figure']['palette'])
            self.sketch.update()
            self._schedule()

    def _help(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('Figure Builder — help')
        dlg.resize(700, 680)
        lay = QVBoxLayout(dlg)
        text = QTextBrowser()
        names = ', '.join(f'<code>{n}</code>' for n in self.table.labels) or 'connect a sample first'
        text.setHtml(HELP_HTML + f'<h3>Isotopes in this data</h3><p>{names}</p>')
        lay.addWidget(text)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.exec()

    def _settings(self):
        return QSettings(*SETTINGS)

    def saved_designs(self) -> dict:
        """Designs saved in the application settings, ``{name: spec}``."""
        raw = self._settings().value(DESIGNS_KEY, '{}')
        try:
            data = json.loads(raw) if isinstance(raw, str) else {}
        except ValueError:
            data = {}
        return data if isinstance(data, dict) else {}

    def _store_designs(self, designs: dict):
        self._settings().setValue(DESIGNS_KEY, json.dumps(designs))

    def _fill_designs_menu(self):
        m = self.designs_menu
        m.clear()
        m.addAction(_icon('fa6s.floppy-disk'), 'Save current design…', self._save_design)
        designs = self.saved_designs()
        if designs:
            m.addSeparator()
            for name in sorted(designs):
                m.addAction(name, lambda n=name: self.apply_design(designs[n]))
            delete = m.addMenu('Delete a saved design')
            for name in sorted(designs):
                delete.addAction(name, lambda n=name: self._delete_design(n))
        m.addSeparator()
        m.addAction('Import design from file…', self._import_design)
        m.addAction('Export design to file…', self._export_design)

    def _save_design(self):
        name, ok = QInputDialog.getText(self, 'Save design', 'Name for this design:')
        if not ok or not name.strip():
            return
        designs = self.saved_designs()
        designs[name.strip()] = E.strip_spec(self.spec)
        self._store_designs(designs)
        self.status.setText(f'Design “{name.strip()}” saved')

    def _delete_design(self, name):
        designs = self.saved_designs()
        designs.pop(name, None)
        self._store_designs(designs)

    def apply_design(self, design: dict):
        """Replace the current figure with a saved design (data stays the same)."""
        spec = E.normalise_spec(copy.deepcopy(design))
        for p in spec['panels']:
            p['id'] = E.new_panel_id()
        self._load_spec(spec, keep_selection=False)

    def _export_design(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Export design', 'figure_design.json',
                                              'Figure design (*.json)')
        if path:
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(E.strip_spec(self.spec), fh, indent=2)

    def _import_design(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import design', '', 'Figure design (*.json)')
        if not path:
            return
        try:
            with open(path, encoding='utf-8') as fh:
                design = json.load(fh)
            if not isinstance(design, dict) or 'panels' not in design:
                raise ValueError('not a Figure Builder design')
        except Exception as exc:
            QMessageBox.warning(self, 'Import design', f'Could not read this file: {exc}')
            return
        self.apply_design(design)

    def _push_history(self):
        state = json.dumps(self.spec, sort_keys=True, default=str)
        if self._hindex >= 0 and self._history[self._hindex] == state:
            return
        del self._history[self._hindex + 1:]
        self._history.append(state)
        if len(self._history) > 200:
            self._history.pop(0)
        self._hindex = len(self._history) - 1
        self._update_undo_buttons()

    def _update_undo_buttons(self):
        self.undo_btn.setEnabled(self._hindex > 0)
        self.redo_btn.setEnabled(self._hindex < len(self._history) - 1)

    def undo(self):
        """Go back one change."""
        if self._hindex <= 0:
            return
        self._hindex -= 1
        self._restore()

    def redo(self):
        """Re-apply an undone change."""
        if self._hindex >= len(self._history) - 1:
            return
        self._hindex += 1
        self._restore()

    def _restore(self):
        self._restoring = True
        try:
            self._load_spec(json.loads(self._history[self._hindex]))
        finally:
            self._restoring = False
        self._update_undo_buttons()

    def _schedule(self):
        self._timer.start()

    def _preview_dpi(self) -> float:
        fig = self.spec['figure']
        dpr = self.preview.devicePixelRatioF()
        w = max(100, self.preview.width()) * dpr
        h = max(100, self.preview.height()) * dpr
        dpi = min(w / float(fig['width']), h / float(fig['height']))
        return float(max(40.0, min(240.0, dpi)))

    def _render(self):
        t0 = time.perf_counter()
        try:
            pm, report, fig = render_to_pixmap(self.spec, self.table, self._preview_dpi())
        except Exception as exc:
            _log.exception('Figure Builder render failed')
            self.status.setText(f'Render failed: {exc}')
            return
        ms = (time.perf_counter() - t0) * 1000
        self._last_report = report
        self.last_fig = fig
        try:
            self._hits = interact.collect_hits(fig, report, self.spec)
        except Exception:
            _log.exception('Figure Builder hit map failed')
            self._hits = []
        self.preview.set_figure_pixmap(pm)
        sel = self._panel(self.sketch.selected)
        self.preview.set_selection(sel['rect'] if sel else None)
        self.sketch.errors = dict(report.errors)
        self.sketch.update()
        self.editor.show_error(report.errors.get(self.sketch.selected))
        self.stats_box.setPlainText('\n'.join(report.stats))
        self.bottom.setTabText(0, f'Statistics ({len(report.stats)})' if report.stats else 'Statistics')
        if report.variable_errors:
            self.var_status.setText('\n'.join(f'{k}: {v}' for k, v in report.variable_errors.items()))
        n = len(self.table)
        bad = len(report.errors)
        self.status.setText(f'{n:,} particles · {len(self.spec["panels"])} panel(s)'
                            + (f' · ⚠ {bad} need attention' if bad else '') + f' · {ms:.0f} ms')
        if not self._restoring:
            self._push_history()

    def _export(self):
        from results.shared_plot_utils import download_matplotlib_figure
        fig = Figure()
        FigureCanvasAgg(fig)
        E.render(fig, self.spec, self.table)
        csv = self.table.dataframe() if len(self.table) else None
        download_matplotlib_figure(fig, self, 'figure', csv_data=csv)

    def _copy(self):
        dpi = float(self.spec['figure'].get('dpi') or 300)
        pm, _r, _f = render_to_pixmap(self.spec, self.table, min(dpi, 600.0))
        QApplication.clipboard().setPixmap(pm)
        self.status.setText('Figure copied to the clipboard')

    def export_bytes(self, fmt: str = 'png', dpi: float = 150) -> bytes:
        """Render the figure to bytes, used by tests and automation."""
        fig = Figure()
        FigureCanvasAgg(fig)
        E.render(fig, copy.deepcopy(self.spec), self.table)
        buf = io.BytesIO()
        fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches='tight')
        return buf.getvalue()
