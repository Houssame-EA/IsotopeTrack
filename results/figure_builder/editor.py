"""Tabbed property editor for one Figure Builder panel.

The editor splits a panel's settings into tabs (Data, Groups, Style, Axes,
Stats, Notes). Rows show or hide according to the panel's chart type,
grouping mode and statistical test, and tabs with nothing relevant are
hidden. Every edit is written straight into the panel dict and announced
with ``changed`` so the preview can redraw.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QGroupBox,
    QLabel, QLineEdit, QPlainTextEdit, QScrollArea, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from results.figure_builder import engine as E
from results.figure_builder import styles as S
from results.figure_builder.expressions import split_list, validate
from results.figure_builder.widgets import (
    ChipBar, ColorButton, ExpressionEdit, GroupsTable, RowTable, mono_font)

PLOTS = {'scatter', 'line', 'histogram', 'box', 'violin', 'bar', 'density'}
XY = {'scatter', 'density'}
XLINE = XY | {'line'}
DIST = {'box', 'violin'}
TESTABLE = {'histogram', 'box', 'violin', 'bar'}
GROUPING = {'scatter', 'line', 'histogram', 'box', 'violin', 'bar', 'pie', 'ternary', 'code'}
ALL = set(E.PANEL_KINDS)
MARKED = {'scatter', 'ternary', 'line'}

AGG = {'mean': 'Mean', 'median': 'Median', 'sum': 'Sum', 'count': 'Particle count'}

RULE_COLUMNS = [
    ('name', 'Name', 'text', None, 100),
    ('when', 'Condition', 'mask', None, 0),
    ('color', 'Colour', 'color', None, 58),
]

SERIES_COLUMNS = [
    ('label', 'Label', 'text', None, 90),
    ('x', 'X', 'expr', None, 0),
    ('y', 'Y', 'expr', None, 90),
    ('filter', 'Only where', 'mask', None, 90),
    ('style', 'Style', 'combo', {'points': 'Points', 'line': 'Line', 'points+line': 'Both'}, 80),
    ('marker', 'Marker', 'combo', S.MARKERS, 90),
    ('size', 'Size', 'float', (1, 300, 2), 64),
    ('color', 'Colour', 'color', None, 58),
]

ANNOTATION_COLUMNS = [
    ('text', 'Text', 'text', None, 0),
    ('x', 'x', 'text', None, 48),
    ('y', 'y', 'text', None, 48),
    ('coords', 'Position in', 'combo', {'axes': 'Panel (0–1)', 'data': 'Axis values'}, 100),
    ('arrow_x', 'Arrow x', 'text', None, 58),
    ('arrow_y', 'Arrow y', 'text', None, 58),
    ('size', 'Size', 'float', (4, 48, 1), 58),
    ('color', 'Colour', 'color', None, 58),
    ('bold', 'Bold', 'check', None, 40),
    ('box', 'Box', 'check', None, 40),
]

FIELDS = [
    ('Data', 'Chart', 'kind', 'Chart type', 'combo', ALL, E.PANEL_KINDS),
    ('Data', 'Chart', 'title', 'Panel title', 'text', ALL, 'optional'),
    ('Data', 'What to plot', 'x', 'X', 'expr', XLINE, 'e.g. Fe   or   log(Ag)'),
    ('Data', 'What to plot', 'y', 'Y', 'expr', XLINE, 'e.g. Fe/Cu'),
    ('Data', 'What to plot', 'y2', 'Right Y axis', 'expr', {'scatter'}, 'optional, e.g. mass:Fe'),
    ('Data', 'What to plot', 'value', 'Value', 'expr', {'histogram', 'box', 'violin', 'bar', 'pie'}, 'e.g. mass:Ag'),
    ('Data', 'What to plot', 'a', 'Top corner (A)', 'expr', {'ternary'}, 'e.g. Ag'),
    ('Data', 'What to plot', 'b', 'Left corner (B)', 'expr', {'ternary'}, 'e.g. Au'),
    ('Data', 'What to plot', 'c', 'Right corner (C)', 'expr', {'ternary'}, 'e.g. Cu'),
    ('Data', 'What to plot', 'agg', 'Summarise as', 'combo', {'bar', 'line'}, AGG),
    ('Data', 'What to plot', 'pie_mode', 'Slices are', 'combo', {'pie'},
     {'groups': 'Particle count per group', 'values': 'Share of the Value list'}),
    ('Data', 'Which particles', 'filter', 'Only particles where', 'mask', ALL - {'text'},
     'e.g. Ag > 0 and Au > 0'),
    ('Data', 'Which particles', 'drop_zeros', 'Hide zero values (not detected)', 'check',
     XLINE | {'histogram', 'box', 'violin', 'bar'}, None),
    ('Data', 'Extra series on this plot', 'series', '', 'series', {'scatter'}, None),
    ('Data', 'Text', 'text', '', 'longtext', {'text'}, None),
    ('Data', 'Text', 'text_size', 'Text size (0 = auto)', 'float', {'text'}, (0, 72, 1)),
    ('Data', 'Python', 'code', '', 'code', {'code'}, None),
    ('Groups', 'Grouping', 'group_by', 'Group / colour by', 'combo', GROUPING, E.GROUP_MODES),
    ('Groups', 'Grouping', 'color', 'Colour', 'color', PLOTS | {'ternary'}, None),
    ('Groups', 'Rules (first match wins)', 'rules', '', 'rules', set(), None),
    ('Groups', 'Rules (first match wins)', 'show_other', 'Show particles matching no rule', 'check', set(), None),
    ('Groups', 'Rules (first match wins)', 'other_label', 'Name for the rest', 'text', set(), None),
    ('Groups', 'Show, rename, recolour, reorder', 'groups', '', 'groups', set(), None),
    ('Groups', 'Show, rename, recolour, reorder', 'show_n', 'Show particle counts (n=…)', 'check',
     GROUPING - {'code', 'pie'}, None),
    ('Style', 'Markers', 'marker', 'Shape', 'combo', MARKED, S.MARKERS),
    ('Style', 'Markers', 'marker_size', 'Size', 'float', MARKED, (1, 400, 1)),
    ('Style', 'Markers', 'alpha', 'Opacity', 'float', {'scatter', 'ternary'}, (0.05, 1, 0.05)),
    ('Style', 'Markers', 'edge_color', 'Outline colour', 'color', {'scatter', 'ternary', 'bar', 'pie'}, None),
    ('Style', 'Markers', 'edge_width', 'Outline width', 'float', {'scatter', 'ternary', 'bar', 'pie'}, (0, 6, 0.2)),
    ('Style', 'Markers', 'size_by', 'Size by value', 'expr', {'scatter'}, 'optional, e.g. total'),
    ('Style', 'Colour scale', 'color_by', 'Colour by value', 'expr', {'scatter'}, 'optional, e.g. total'),
    ('Style', 'Colour scale', 'colormap', 'Colour map', 'combo', {'scatter', 'density'},
     {k: k for k in S.COLORMAPS}),
    ('Style', 'Colour scale', 'reverse_cmap', 'Reverse colour map', 'check', {'scatter', 'density'}, None),
    ('Style', 'Colour scale', 'y2_color', 'Right axis colour', 'color', {'scatter'}, None),
    ('Style', 'Lines', 'line_width', 'Line width', 'float', {'scatter', 'line', 'histogram'}, (0.2, 8, 0.2)),
    ('Style', 'Lines', 'line_style', 'Line style', 'combo', {'scatter', 'line', 'histogram'}, S.LINE_STYLES),
    ('Style', 'Chart options', 'bins', 'Bins', 'int', {'histogram', 'density', 'line'}, (2, 500)),
    ('Style', 'Chart options', 'hist_style', 'Bars', 'combo', {'histogram'},
     {'filled': 'Filled', 'step': 'Outline'}),
    ('Style', 'Chart options', 'density', 'Normalise (density / fraction)', 'check', {'histogram'}, None),
    ('Style', 'Chart options', 'kde', 'Smooth density curve (KDE)', 'check', {'histogram'}, None),
    ('Style', 'Chart options', 'cumulative', 'Cumulative', 'check', {'histogram'}, None),
    ('Style', 'Chart options', 'band', 'Shaded band', 'combo', {'line'},
     {'sem': 'Standard error', 'sd': 'Standard deviation', 'iqr': 'Interquartile range', 'none': 'None'}),
    ('Style', 'Chart options', 'show_points', 'Show points / markers', 'check', DIST | {'line'}, None),
    ('Style', 'Chart options', 'notch', 'Notched boxes', 'check', {'box'}, None),
    ('Style', 'Chart options', 'show_mean', 'Mark the mean', 'check', DIST, None),
    ('Style', 'Chart options', 'error', 'Error bars', 'combo', {'bar'},
     {'sd': 'Standard deviation', 'sem': 'Standard error', 'ci95': '95% CI', 'none': 'None'}),
    ('Style', 'Chart options', 'horizontal', 'Horizontal bars', 'check', {'bar'}, None),
    ('Style', 'Chart options', 'stacked', 'Stack the values', 'check', {'bar'}, None),
    ('Style', 'Chart options', 'donut', 'Donut', 'check', {'pie'}, None),
    ('Style', 'Background', 'panel_bg', 'Panel background', 'color', PLOTS | {'ternary', 'text', 'code'}, None),
    ('Axes', 'Labels', 'x_label', 'X label', 'text', XLINE | {'histogram'}, 'automatic'),
    ('Axes', 'Labels', 'y_label', 'Y label', 'text', PLOTS, 'automatic'),
    ('Axes', 'Labels', 'y2_label', 'Right Y label', 'text', {'scatter'}, 'automatic'),
    ('Axes', 'Scale', 'log_x', 'Log X', 'check', XLINE | {'histogram'}, None),
    ('Axes', 'Scale', 'log_y', 'Log Y', 'check', PLOTS, None),
    ('Axes', 'Scale', 'log_y2', 'Log right Y', 'check', {'scatter'}, None),
    ('Axes', 'Range', 'x_min', 'X from', 'text', XLINE | {'histogram'}, 'auto'),
    ('Axes', 'Range', 'x_max', 'X to', 'text', XLINE | {'histogram'}, 'auto'),
    ('Axes', 'Range', 'y_min', 'Y from', 'text', PLOTS, 'auto'),
    ('Axes', 'Range', 'y_max', 'Y to', 'text', PLOTS, 'auto'),
    ('Axes', 'Ticks and frame', 'frame', 'Frame', 'combo', PLOTS,
     {'open': 'Open (left + bottom)', 'box': 'Box (all sides)', 'none': 'None'}),
    ('Axes', 'Ticks and frame', 'tick_dir', 'Ticks', 'combo', PLOTS,
     {'out': 'Outside', 'in': 'Inside', 'inout': 'Crossing'}),
    ('Axes', 'Ticks and frame', 'minor_ticks', 'Minor ticks', 'check', PLOTS, None),
    ('Axes', 'Ticks and frame', 'sci_x', 'Scientific notation X', 'check', XLINE | {'histogram'}, None),
    ('Axes', 'Ticks and frame', 'sci_y', 'Scientific notation Y', 'check', PLOTS, None),
    ('Axes', 'Ticks and frame', 'xtick_rotation', 'Rotate X labels (°)', 'int', PLOTS, (-90, 90)),
    ('Axes', 'Ticks and frame', 'grid', 'Grid', 'check', PLOTS | {'ternary'}, None),
    ('Axes', 'Ticks and frame', 'aspect_equal', 'Equal X/Y scale', 'check', XY, None),
    ('Axes', 'Guide lines', 'hlines', 'Horizontal lines at', 'text', PLOTS, 'e.g. 1, 10'),
    ('Axes', 'Guide lines', 'vlines', 'Vertical lines at', 'text', XLINE | {'histogram'}, 'e.g. 100'),
    ('Axes', 'Guide lines', 'diagonal', 'y = x line', 'check', {'scatter'}, None),
    ('Axes', 'Legend', 'legend', 'Show legend', 'check', ALL - {'text', 'code', 'box', 'violin', 'density'}, None),
    ('Axes', 'Legend', 'legend_loc', 'Position', 'combo', ALL - {'text', 'code', 'box', 'violin', 'density'},
     S.LEGEND_LOCATIONS),
    ('Axes', 'Legend', 'legend_cols', 'Columns', 'int', ALL - {'text', 'code', 'box', 'violin', 'density'}, (1, 8)),
    ('Axes', 'Legend', 'legend_title', 'Title', 'text', ALL - {'text', 'code', 'box', 'violin', 'density'}, 'optional'),
    ('Axes', 'Legend', 'legend_size', 'Text size', 'combo', ALL - {'text', 'code', 'box', 'violin', 'density'},
     S.FONT_SIZES),
    ('Stats', 'Fit', 'show_fit', 'Fit line', 'check', {'scatter'}, None),
    ('Stats', 'Fit', 'show_r', 'Show r and R² on the plot', 'check', {'scatter'}, None),
    ('Stats', 'Compare groups', 'test', 'Test', 'combo', TESTABLE, E.STAT_TESTS),
    ('Stats', 'Compare groups', 'pairs', 'Pairs', 'combo', set(),
     {'all': 'Every pair', 'first': 'Each group vs the first'}),
    ('Stats', 'Compare groups', 'correction', 'Multiple comparisons', 'combo', set(), E.CORRECTIONS),
    ('Stats', 'Compare groups', 'p_format', 'Show p as', 'combo', set(),
     {'stars': 'Stars (*, **, ns)', 'p': 'Numbers (p = …)'}),
    ('Stats', 'Compare groups', 'hide_ns', 'Hide non-significant brackets', 'check', set(), None),
    ('Notes', 'Text and arrows on this panel', 'annotations', '', 'annotations',
     ALL - {'text'}, None),
]
"""(tab, section, key, label, widget type, kinds, options) for every panel field."""

LABELS = {
    ('x', 'line'): 'X (binned)',
    ('y', 'line'): 'Y (blank = count)',
    ('value', 'bar'): 'Values (comma separated)',
    ('value', 'pie'): 'Values (comma separated)',
}

TAB_HINTS = {
    'Stats': 'Results (test statistics, p-values, fits) are listed under the preview.',
    'Notes': 'x and y from 0 to 1 place text inside the panel; choose “Axis values” to use '
             'your data coordinates. Fill Arrow x/y to point an arrow at something.',
    'Groups': 'Rules colour particles by conditions you write, e.g. Fe/Cu < 0.5. '
              'Untick a group to hide it, type a legend name to rename it.',
}

SPECIAL_CHIPS = ('total', 'n_elements', 'sample', 'class', 'time', 'log(', 'mass:', 'moles:', 'd:')


class PanelEditor(QWidget):
    """Tabbed form editing the settings of the selected panel.

    Signals:
        changed(): any field of the panel changed.
        kind_changed(): the chart type (or pie mode) changed.
    """

    changed = Signal()
    kind_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.panel = None
        self.table = None
        self.palette = list(E.PALETTE)
        self._loading = False
        self._last_expr = None
        self.widgets: dict = {}
        self.rows: dict = {}
        self.sections: dict = {}
        self.tab_pages: dict = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        self.empty = QLabel('Select a panel on the page, or drag on the page to draw a new one.')
        self.empty.setWordWrap(True)
        self.empty.setStyleSheet('color: #6b7280; padding: 12px;')
        root.addWidget(self.empty)
        self.error = QLabel('')
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #b42318; font-weight: 600; padding: 2px 4px;')
        self.error.hide()
        root.addWidget(self.error)
        self.chips = ChipBar()
        self.chips.insert.connect(self._insert_chip)
        self.chips_label = QLabel('Click to insert into the last expression box:')
        self.chips_label.setStyleSheet('color: #6b7280; font-size: 11px;')
        root.addWidget(self.chips_label)
        root.addWidget(self.chips)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        root.addWidget(self.tabs, 1)
        for tab, section, key, label, kind, _kinds, opts in FIELDS:
            if tab not in self.tab_pages:
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setFrameShape(QFrame.NoFrame)
                page = QWidget()
                lay = QVBoxLayout(page)
                lay.setContentsMargins(4, 6, 4, 6)
                lay.setSpacing(8)
                if tab in TAB_HINTS:
                    hint = QLabel(TAB_HINTS[tab])
                    hint.setWordWrap(True)
                    hint.setStyleSheet('color: #6b7280; font-size: 11px;')
                    lay.addWidget(hint)
                scroll.setWidget(page)
                self.tabs.addTab(scroll, tab)
                self.tab_pages[tab] = (scroll, lay)
            if (tab, section) not in self.sections:
                box = QGroupBox(section)
                form = QFormLayout(box)
                form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
                form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
                form.setVerticalSpacing(6)
                self.sections[(tab, section)] = (box, form)
                self.tab_pages[tab][1].addWidget(box)
            box, form = self.sections[(tab, section)]
            w = self._make(key, kind, opts)
            self.widgets[key] = (kind, w)
            if kind in ('rules', 'series', 'annotations', 'groups', 'code', 'longtext'):
                form.addRow(w)
                self.rows[key] = (None, w)
            else:
                form.addRow(label, w)
                self.rows[key] = (form.labelForField(w), w)
        for _scroll, lay in self.tab_pages.values():
            lay.addStretch()
        self.tabs.hide()
        self.chips.hide()
        self.chips_label.hide()

    def _make(self, key, kind, opts):
        """Create the widget for one field and wire it to the panel."""
        if kind == 'combo':
            w = QComboBox()
            for k, label in opts.items():
                w.addItem(label, k)
            w.currentIndexChanged.connect(lambda _i, k=key, ww=w: self._set(k, ww.currentData()))
        elif kind in ('expr', 'mask'):
            w = ExpressionEdit()
            if opts:
                w.setPlaceholderText(opts)
            w.textEdited.connect(lambda t, k=key: self._set(k, t))
            w.focused.connect(self._remember_expr)
        elif kind == 'text':
            w = QLineEdit()
            if opts:
                w.setPlaceholderText(opts)
            w.textEdited.connect(lambda t, k=key: self._set(k, t))
        elif kind == 'check':
            w = QCheckBox()
            w.toggled.connect(lambda v, k=key: self._set(k, bool(v)))
        elif kind == 'float':
            w = QDoubleSpinBox()
            lo, hi, step = opts
            w.setRange(lo, hi)
            w.setSingleStep(step)
            w.setDecimals(2)
            w.setKeyboardTracking(False)
            w.valueChanged.connect(lambda v, k=key: self._set(k, float(v)))
        elif kind == 'int':
            w = QSpinBox()
            w.setRange(*opts)
            w.setKeyboardTracking(False)
            w.valueChanged.connect(lambda v, k=key: self._set(k, int(v)))
        elif kind == 'color':
            w = ColorButton()
            w.color_changed.connect(lambda c, k=key: self._set(k, c))
        elif kind == 'rules':
            w = RowTable(RULE_COLUMNS, '+ Add rule',
                         lambda i: {'name': f'Group {i + 1}', 'when': '',
                                    'color': self.palette[(i + 1) % len(self.palette)]})
            w.changed.connect(lambda ww=w: self._set('rules', ww.rows()))
        elif kind == 'series':
            w = RowTable(SERIES_COLUMNS, '+ Add series',
                         lambda i: {'label': '', 'x': (self.panel or {}).get('x', ''), 'y': '',
                                    'filter': '', 'style': 'points', 'marker': 'o', 'size': 14.0,
                                    'color': self.palette[(i + 2) % len(self.palette)]})
            w.changed.connect(lambda ww=w: self._set('series', ww.rows()))
        elif kind == 'annotations':
            w = RowTable(ANNOTATION_COLUMNS, '+ Add text',
                         lambda i: {'text': 'Note', 'x': '0.05', 'y': f'{0.92 - 0.08 * i:.2f}',
                                    'coords': 'axes', 'size': 10.0, 'color': '#222222'})
            w.changed.connect(lambda ww=w: self._set('annotations', ww.rows()))
        elif kind == 'groups':
            w = GroupsTable()
            w.changed.connect(self._groups_changed)
        elif kind == 'longtext':
            w = QPlainTextEdit()
            w.setMinimumHeight(120)
            w.setPlaceholderText('Caption, method note, sample description…')
            w.textChanged.connect(lambda ww=w: self._set('text', ww.toPlainText()))
        else:
            w = QPlainTextEdit()
            w.setFont(mono_font())
            w.setMinimumHeight(260)
            w.setPlaceholderText(
                'Variables: ax, fig, df (one row per particle), labels, groups, '
                'group_colors, col("Fe/Cu"), color(i), np, pd, stats, report("text")\n\n'
                + E.CODE_EXAMPLE)
            w.textChanged.connect(lambda ww=w: self._set('code', ww.toPlainText()))
        return w

    def _remember_expr(self, w):
        self._last_expr = w

    def _insert_chip(self, text):
        target = self._last_expr
        if target is None or not target.isVisible():
            for key in ('x', 'value', 'a', 'filter'):
                cand = self.widgets[key][1]
                if cand.isVisible():
                    target = cand
                    break
        if target is not None:
            target.insert_text(text)

    def set_table(self, table, palette=None):
        """Give the editor the particle table for completion, chips and checks."""
        self.table = table
        if palette:
            self.palette = list(palette)
        names = table.names() if table is not None else []
        hints = names + ['log', 'ln', 'sqrt', 'abs', 'exp', 'min', 'max', 'where',
                         'mean', 'median', 'std', 'percentile']
        for _key, (kind, w) in self.widgets.items():
            if isinstance(w, ExpressionEdit):
                w.set_names(hints)
            if isinstance(w, RowTable):
                w.set_table_source(table)
        if table is not None:
            aliases = table.symbol_aliases()
            iso = [s for s in aliases] or list(table.labels)
            self.chips.set_names(iso, list(table.variables), SPECIAL_CHIPS)
        self._check_expressions()
        self.refresh_groups()

    def set_panel(self, panel):
        """Show ``panel`` (a dict, edited in place) or nothing when None."""
        self.panel = panel
        self.empty.setVisible(panel is None)
        self.tabs.setVisible(panel is not None)
        self.chips.setVisible(panel is not None)
        self.chips_label.setVisible(panel is not None)
        if panel is None:
            self.error.hide()
            return
        self._loading = True
        for key, (kind, w) in self.widgets.items():
            v = panel.get(key, E.PANEL_DEFAULTS.get(key))
            if kind == 'combo':
                w.setCurrentIndex(max(0, w.findData(v)))
            elif kind in ('text', 'expr', 'mask'):
                w.setText('' if v is None else str(v))
            elif kind == 'check':
                w.setChecked(bool(v))
            elif kind == 'float':
                w.setValue(float(v or 0))
            elif kind == 'int':
                w.setValue(int(v or 0))
            elif kind == 'color':
                w.set_color(v)
            elif kind in ('rules', 'series', 'annotations'):
                w.set_rows(v)
            elif kind == 'groups':
                pass
            else:
                if w.toPlainText() != (v or ''):
                    w.setPlainText(v or '')
        self._loading = False
        self._update_visibility()
        self._check_expressions()
        self.refresh_groups()

    def refresh_groups(self):
        """Rebuild the groups table from the current data and grouping."""
        if self.panel is None or self.table is None:
            return
        w = self.widgets['groups'][1]
        if not w.isVisibleTo(self) and self.panel.get('group_by', 'none') == 'none':
            return
        try:
            probe = dict(self.panel)
            probe['_palette'] = self.palette
            groups = E.candidate_groups(probe, self.table) if len(self.table) else []
        except Exception:
            groups = []
        w.set_groups(self.panel, groups)

    def show_error(self, message):
        """Show the last render error of this panel (or hide it)."""
        self.error.setText(f'⚠ {message}' if message else '')
        self.error.setVisible(bool(message) and self.panel is not None)

    def _groups_changed(self):
        self.refresh_groups()
        self.changed.emit()

    def _set(self, key, value):
        if self._loading or self.panel is None:
            return
        self.panel[key] = value
        if key in ('kind', 'group_by', 'test', 'pie_mode', 'rules', 'y'):
            if key == 'kind' and value == 'code' and not (self.panel.get('code') or '').strip():
                self.panel['code'] = E.CODE_EXAMPLE
                self._loading = True
                self.widgets['code'][1].setPlainText(E.CODE_EXAMPLE)
                self._loading = False
            self._update_visibility()
            if key in ('kind', 'pie_mode'):
                self.kind_changed.emit()
            if key in ('group_by', 'rules', 'kind'):
                self.refresh_groups()
        if key == 'filter':
            self.refresh_groups()
        if self.widgets.get(key, (None,))[0] in ('expr', 'mask'):
            self._check_expressions()
        self.changed.emit()

    @staticmethod
    def _kinds(key):
        for _t, _s, k, _l, _w, kinds, _o in FIELDS:
            if k == key:
                return kinds
        return set()

    def _visible(self, key, kinds):
        """Whether ``key`` should show for the current panel state."""
        p = self.panel
        kind = p.get('kind')
        group = p.get('group_by', 'none')
        grouped = kind in GROUPING
        if key in ('rules', 'show_other', 'other_label'):
            return group == 'rules' and grouped
        if key == 'groups':
            return group != 'none' and grouped
        if key in ('pairs', 'correction', 'p_format', 'hide_ns'):
            if kind not in TESTABLE or p.get('test') not in E.PAIRWISE_TESTS:
                return False
            return not (key in ('p_format', 'hide_ns') and kind == 'histogram')
        if key == 'color':
            return kind in kinds and (group == 'none' or not grouped)
        if key == 'value' and kind == 'pie':
            return p.get('pie_mode') == 'values'
        if key == 'agg' and kind == 'line':
            return bool((p.get('y') or '').strip())
        return kind in kinds

    def _update_visibility(self):
        if self.panel is None:
            return
        kind = self.panel.get('kind')
        shown = {name: False for name in self.sections}
        for tab, section, key, label, _t, kinds, _o in FIELDS:
            vis = self._visible(key, kinds)
            lab, w = self.rows[key]
            if lab is not None:
                lab.setVisible(vis)
                if isinstance(lab, QLabel):
                    lab.setText(LABELS.get((key, kind), label))
            w.setVisible(vis)
            shown[(tab, section)] = shown[(tab, section)] or vis
        tab_any = {}
        for (tab, section), (box, _form) in self.sections.items():
            box.setVisible(shown[(tab, section)])
            tab_any[tab] = tab_any.get(tab, False) or shown[(tab, section)]
        for i in range(self.tabs.count()):
            name = self.tabs.tabText(i)
            self.tabs.setTabVisible(i, tab_any.get(name, False))

    def _check_expressions(self):
        """Mark expression fields that do not evaluate on the current data."""
        if self.panel is None:
            return
        for key, (kind, w) in self.widgets.items():
            if kind not in ('expr', 'mask'):
                continue
            text = w.text().strip()
            msg = None
            if text and self.table is not None and len(self.table):
                if key == 'value' and self.panel.get('kind') in ('bar', 'pie'):
                    for part in split_list(text):
                        msg = validate(part, self.table) or msg
                else:
                    msg = validate(text, self.table)
            w.mark(msg)
