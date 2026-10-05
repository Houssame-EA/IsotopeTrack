"""Figure Builder canvas node and its window.

The window has three parts: the layout page where panels are drawn
(:class:`~results.figure_builder.sketch.LayoutSketch`), the settings of the
selected panel (:class:`~results.figure_builder.editor.PanelEditor`) and a
live preview rendered at the figure's real size, so what is shown is
exactly what is exported.
"""

from __future__ import annotations

import copy
import io

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFontComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMenu, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QSplitter, QTextBrowser, QToolButton, QVBoxLayout, QWidget,
)

from results.figure_builder import engine as E
from results.figure_builder.editor import ColorButton, PanelEditor
from results.figure_builder.expressions import DATA_TYPES, ParticleTable
from results.figure_builder.sketch import LayoutSketch

import logging

_log = logging.getLogger('IsotopeTrack.results.figure_builder')


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
        labels = table.labels
        for panel in self.config['panels']:
            if panel.get('kind') in ('scatter', 'density') and labels:
                if not panel.get('x'):
                    panel['x'] = labels[0]
                if not panel.get('y'):
                    panel['y'] = labels[1] if len(labels) > 1 else labels[0]
        self.configuration_changed.emit()

    def build_table(self) -> ParticleTable:
        """Return the particle table for the current data and quantity."""
        return ParticleTable.from_input(self.input_data, self.config.get('data_type', 'Counts'))


HELP_HTML = """
<h3>Writing expressions</h3>
<p>Every box marked X, Y, Value, Condition… takes a small formula evaluated for
<b>each particle</b>.</p>
<table cellpadding="3">
<tr><td><code>Fe</code>, <code>56Fe</code></td><td>the isotope, in the quantity chosen at the top (counts, mass…). A bare symbol works when only one isotope has it.</td></tr>
<tr><td><code>Fe/Cu</code>, <code>Ag + Au</code></td><td>arithmetic: + − * / ** and brackets</td></tr>
<tr><td><code>mass:Fe</code></td><td>another quantity: <code>counts:</code> <code>mass:</code> <code>moles:</code> <code>pmass:</code> <code>pmoles:</code> <code>d:</code> (diameter) <code>pd:</code></td></tr>
<tr><td><code>total</code></td><td>sum over all isotopes of the particle, e.g. <code>100*Fe/total</code> for a percentage</td></tr>
<tr><td><code>n_elements</code></td><td>number of detected isotopes in the particle</td></tr>
<tr><td><code>sample</code>, <code>class</code></td><td>sample name and classifier class, e.g. <code>sample == "Blank"</code></td></tr>
<tr><td><code>log(Fe)</code> <code>ln</code> <code>sqrt</code> <code>abs</code> <code>exp</code></td><td>functions (log is base 10)</td></tr>
<tr><td><code>median(Fe)</code> <code>mean</code> <code>std</code> <code>percentile(Fe, 90)</code></td><td>one number over all particles, handy for thresholds</td></tr>
<tr><td><code>Fe &lt; 10</code>, <code>Fe &gt; 0 and Cu &gt; 0</code></td><td>conditions for rules and filters (<code>and</code>, <code>or</code>, <code>not</code>)</td></tr>
<tr><td><code>sample in ["A", "B"]</code></td><td>membership</td></tr>
<tr><td><code>`odd name`</code></td><td>backticks for any column with spaces or symbols</td></tr>
</table>
<h3>Colour by a condition</h3>
<p>Set <i>Group / colour by</i> to <b>By my rules</b>, then add rules such as
<code>Fe/Cu &lt; 0.5</code> → red. The first rule that matches wins; everything else
is drawn in grey as “Other”.</p>
<h3>Statistics</h3>
<p>Box, violin, bar and histogram panels compare their groups (samples, classes or
your rules) with a t-test, Mann-Whitney, KS, ANOVA or Kruskal-Wallis. Results are
listed under the preview and drawn as brackets.</p>
<h3>Anything else</h3>
<p>Choose <b>Python code</b> as the chart type to draw with matplotlib yourself:
<code>ax</code>, <code>df</code>, <code>groups</code> and <code>col("Fe/Cu")</code> are ready to use.</p>
"""


class FigureSettingsDialog(QDialog):
    """Page size, fonts, title and panel letters."""

    def __init__(self, figcfg: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Figure settings')
        self.cfg = dict(figcfg)
        form = QFormLayout(self)
        self.width = QDoubleSpinBox()
        self.width.setRange(1, 40)
        self.width.setSuffix(' in')
        self.width.setValue(float(self.cfg['width']))
        self.height = QDoubleSpinBox()
        self.height.setRange(1, 40)
        self.height.setSuffix(' in')
        self.height.setValue(float(self.cfg['height']))
        size = QWidget()
        sl = QHBoxLayout(size)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self.width)
        sl.addWidget(QLabel('×'))
        sl.addWidget(self.height)
        preset = QComboBox()
        preset.addItem('Presets…', None)
        for name, wh in [('Single column (3.5 × 3 in)', (3.5, 3.0)),
                         ('1.5 column (5.5 × 4 in)', (5.5, 4.0)),
                         ('Double column (7.2 × 5 in)', (7.2, 5.0)),
                         ('Square (6 × 6 in)', (6.0, 6.0)),
                         ('Slide 16:9 (10 × 5.6 in)', (10.0, 5.625))]:
            preset.addItem(name, wh)
        preset.currentIndexChanged.connect(
            lambda _i: preset.currentData() and (self.width.setValue(preset.currentData()[0]),
                                                 self.height.setValue(preset.currentData()[1])))
        sl.addWidget(preset)
        form.addRow('Size', size)
        self.title = QLineEdit(self.cfg.get('title', ''))
        form.addRow('Figure title', self.title)
        self.font = QFontComboBox()
        self.font.setCurrentText(self.cfg.get('font_family') or 'DejaVu Sans')
        form.addRow('Font', self.font)
        self.font_size = QSpinBox()
        self.font_size.setRange(5, 40)
        self.font_size.setValue(int(self.cfg.get('font_size') or 11))
        form.addRow('Font size', self.font_size)
        self.letters = QCheckBox('Label panels')
        self.letters.setChecked(bool(self.cfg.get('panel_letters', True)))
        self.letter_style = QComboBox()
        for k in ('a', 'A', '(a)', 'a)'):
            self.letter_style.addItem(k, k)
        self.letter_style.setCurrentIndex(max(0, self.letter_style.findData(self.cfg.get('letter_style', 'a'))))
        lw = QWidget()
        ll = QHBoxLayout(lw)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(self.letters)
        ll.addWidget(self.letter_style)
        ll.addStretch()
        form.addRow('Panel letters', lw)
        self.label_style = QComboBox()
        for k, label in [('isotope', 'Isotope (¹⁰⁷Ag)'), ('symbol', 'Symbol (Ag)'), ('raw', 'As written (107Ag)')]:
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

    def collect(self) -> dict:
        """Return the edited figure settings."""
        out = dict(self.cfg)
        out.update(width=self.width.value(), height=self.height.value(),
                   title=self.title.text(), font_family=self.font.currentText(),
                   font_size=self.font_size.value(), panel_letters=self.letters.isChecked(),
                   letter_style=self.letter_style.currentData(),
                   label_style=self.label_style.currentData(),
                   background=self.bg.color(), dpi=self.dpi.value())
        return out


class PreviewLabel(QLabel):
    """Shows the rendered figure scaled to fit, keeping its aspect ratio."""

    resized = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._pixmap = None

    def set_figure_pixmap(self, pm: QPixmap):
        """Store and display a freshly rendered pixmap."""
        self._pixmap = pm
        self._rescale()

    def _rescale(self):
        if self._pixmap is None:
            return
        dpr = self.devicePixelRatioF()
        target = QSize(int(self.width() * dpr), int(self.height() * dpr))
        pm = self._pixmap.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pm.setDevicePixelRatio(dpr)
        self.setPixmap(pm)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._rescale()
        self.resized.emit()


def render_to_pixmap(spec: dict, table: ParticleTable, dpi: float):
    """Render ``spec`` off-screen and return ``(QPixmap, RenderReport, Figure)``."""
    fig = Figure()
    FigureCanvasAgg(fig)
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
        self.setMinimumSize(1100, 720)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        node.config = E.normalise_spec(node.config)
        self.spec = node.config
        self.table = node.build_table()
        self._last_report = E.RenderReport()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(220)
        self._timer.timeout.connect(self._render)
        self._build_ui()
        self.node.configuration_changed.connect(self._on_node_data)
        first = self.spec['panels'][0]['id'] if self.spec['panels'] else ''
        self.sketch.select(first)
        self._on_select(first)
        self._schedule()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        bar = QHBoxLayout()
        bar.addWidget(QLabel('Quantity'))
        self.data_type = QComboBox()
        for k in DATA_TYPES:
            self.data_type.addItem(k, k)
        self.data_type.setCurrentIndex(max(0, self.data_type.findData(self.spec.get('data_type', 'Counts'))))
        self.data_type.setToolTip('What a bare isotope name such as Fe means in your expressions')
        self.data_type.currentIndexChanged.connect(self._on_data_type)
        bar.addWidget(self.data_type)
        layouts = QToolButton()
        layouts.setText('Layouts')
        layouts.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(layouts)
        for name in E.TEMPLATES:
            menu.addAction(name, lambda n=name: self._apply_template(n))
        menu.addSeparator()
        menu.addAction('Clear page', self._clear)
        layouts.setMenu(menu)
        bar.addWidget(layouts)
        fig_btn = QPushButton('Figure settings…')
        fig_btn.clicked.connect(self._figure_settings)
        bar.addWidget(fig_btn)
        help_btn = QPushButton('Expression help')
        help_btn.clicked.connect(self._help)
        bar.addWidget(help_btn)
        bar.addStretch()
        self.status = QLabel('')
        self.status.setMinimumWidth(240)
        self.status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status.setStyleSheet('color: #6b7280;')
        bar.addWidget(self.status)
        copy_btn = QPushButton('Copy')
        copy_btn.clicked.connect(self._copy)
        bar.addWidget(copy_btn)
        export_btn = QPushButton('Export figure…')
        export_btn.clicked.connect(self._export)
        bar.addWidget(export_btn)
        root.addLayout(bar)

        split = QSplitter(Qt.Horizontal)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        hint = QLabel('Drag on the page to draw a panel · Shift-drag draws on top (insets) · '
                      'drag a panel to move · corner to resize · right-click for options')
        hint.setWordWrap(True)
        hint.setStyleSheet('color: #6b7280; font-size: 11px;')
        ll.addWidget(hint)
        self.sketch = LayoutSketch(self.spec)
        self.sketch.panel_factory = self._new_panel
        self.sketch.setMinimumHeight(240)
        self.sketch.selection_changed.connect(self._on_select)
        self.sketch.layout_changed.connect(self._on_layout)
        self.sketch.kind_requested.connect(self._on_kind_requested)
        ll.addWidget(self.sketch, 2)
        self.editor = PanelEditor()
        self.editor.set_table(self.table)
        self.editor.changed.connect(self._schedule)
        self.editor.kind_changed.connect(self._on_editor_kind)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self.editor)
        ll.addWidget(scroll, 5)
        left.setMinimumWidth(380)
        split.addWidget(left)

        right = QSplitter(Qt.Vertical)
        frame = QFrame()
        frame.setStyleSheet('QFrame { background: #f3f4f6; border-radius: 6px; }')
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(8, 8, 8, 8)
        self.preview = PreviewLabel()
        self.preview.resized.connect(self._schedule)
        self.plot_widget = self.preview
        fl.addWidget(self.preview)
        right.addWidget(frame)
        self.stats_box = QPlainTextEdit()
        self.stats_box.setReadOnly(True)
        self.stats_box.setPlaceholderText('Statistics (fits, tests, p-values) appear here.')
        right.addWidget(self.stats_box)
        right.setStretchFactor(0, 5)
        right.setStretchFactor(1, 1)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([420, 900])
        root.addWidget(split, 1)

    def _panel(self, pid):
        for p in self.spec['panels']:
            if p['id'] == pid:
                return p
        return None

    def _fill_defaults(self, panel):
        """Pre-fill a panel's empty data fields with isotopes from the stream."""
        labs = self.table.labels
        if not labs or panel is None:
            return panel
        second = labs[1] if len(labs) > 1 else labs[0]
        kind = panel.get('kind')
        if kind in ('scatter', 'density'):
            panel['x'] = panel.get('x') or labs[0]
            panel['y'] = panel.get('y') or second
        elif kind in ('histogram', 'box', 'violin', 'bar'):
            panel['value'] = panel.get('value') or labs[0]
        elif kind == 'pie' and panel.get('pie_mode') == 'values':
            panel['value'] = panel.get('value') or ', '.join(labs[:6])
        elif kind == 'ternary':
            for key, lab in zip('abc', (labs * 3)[:3]):
                panel[key] = panel.get(key) or lab
        return panel

    def _new_panel(self, **kwargs):
        """Create a panel for the sketch, already pointing at real isotopes."""
        return self._fill_defaults(E.make_panel(**kwargs))

    def _on_editor_kind(self):
        panel = self.editor.panel
        self._fill_defaults(panel)
        self.editor.set_panel(panel)
        self.sketch.update()
        self._schedule()

    def _on_select(self, pid):
        panel = self._panel(pid)
        self.editor.set_panel(panel)
        self.editor.show_error(self._last_report.errors.get(pid) if panel else None)

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
        self._fill_defaults(panel)
        self._on_select(pid)
        self.sketch.update()
        self._schedule()

    def _on_data_type(self, _i):
        self.spec['data_type'] = self.data_type.currentData()
        self._reload_table()

    def _on_node_data(self):
        if self.node.config is not self.spec:
            self.spec = E.normalise_spec(self.node.config)
            self.node.config = self.spec
            self.sketch.set_spec(self.spec)
        self._reload_table()
        self._on_select(self.sketch.selected)

    def _reload_table(self):
        self.table = self.node.build_table()
        self.editor.set_table(self.table)
        self._schedule()

    def _apply_template(self, name):
        new = E.apply_template(self.spec, name)
        self.spec['panels'] = [self._fill_defaults(p) for p in new['panels']]
        self.sketch.set_spec(self.spec)
        self.sketch.select(self.spec['panels'][0]['id'])
        self._on_layout()

    def _clear(self):
        self.spec['panels'] = []
        self.sketch.set_spec(self.spec)
        self.sketch.select('')
        self._on_layout()

    def _figure_settings(self):
        dlg = FigureSettingsDialog(self.spec['figure'], self)
        if dlg.exec() == QDialog.Accepted:
            self.spec['figure'] = dlg.collect()
            self.sketch.update()
            self._schedule()

    def _help(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('Figure Builder — expressions')
        dlg.resize(640, 620)
        lay = QVBoxLayout(dlg)
        text = QTextBrowser()
        names = ', '.join(f'<code>{n}</code>' for n in self.table.labels) or 'connect a sample first'
        text.setHtml(HELP_HTML + f'<h3>Isotopes in this data</h3><p>{names}</p>')
        lay.addWidget(text)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.exec()

    def _schedule(self):
        self._timer.start()

    def _preview_dpi(self) -> float:
        fig = self.spec['figure']
        dpr = self.preview.devicePixelRatioF()
        w = max(100, self.preview.width()) * dpr
        h = max(100, self.preview.height()) * dpr
        dpi = min(w / float(fig['width']), h / float(fig['height']))
        return float(max(40.0, min(220.0, dpi)))

    def _render(self):
        try:
            pm, report, _fig = render_to_pixmap(self.spec, self.table, self._preview_dpi())
        except Exception as exc:
            _log.exception('Figure Builder render failed')
            self.status.setText(f'Render failed: {exc}')
            return
        self._last_report = report
        self.preview.set_figure_pixmap(pm)
        self.sketch.errors = dict(report.errors)
        self.sketch.update()
        self.editor.show_error(report.errors.get(self.sketch.selected))
        self.stats_box.setPlainText('\n'.join(report.stats))
        n = len(self.table)
        bad = len(report.errors)
        self.status.setText(f'{n:,} particles' + (f' · {bad} panel(s) need attention' if bad else ''))

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
