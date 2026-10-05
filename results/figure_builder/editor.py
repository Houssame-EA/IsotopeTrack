"""Property editor for one Figure Builder panel.

The editor is a single scrollable form whose rows show or hide according
to the panel's chart type, grouping mode and statistical test. Every edit
is written straight into the panel dict and announced with ``changed`` so
the preview can redraw.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QStringListModel, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QCompleter, QDoubleSpinBox,
    QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from results.figure_builder import engine as E
from results.figure_builder.expressions import validate

PLOTS = {'scatter', 'histogram', 'box', 'violin', 'bar', 'density'}
XY = {'scatter', 'density'}
DIST = {'box', 'violin', 'bar'}
TESTABLE = {'histogram', 'box', 'violin', 'bar'}
ALL = set(E.PANEL_KINDS)

FIELDS = [
    ('Panel', 'kind', 'Chart type', 'combo', ALL, E.PANEL_KINDS),
    ('Panel', 'title', 'Panel title', 'text', ALL - {'text'}, None),
    ('Data', 'x', 'X', 'expr', XY, 'e.g. Fe   or   log(Ag)'),
    ('Data', 'y', 'Y', 'expr', XY, 'e.g. Fe/Cu'),
    ('Data', 'y2', 'Right Y (optional)', 'expr', {'scatter'}, 'second axis, e.g. mass:Fe'),
    ('Data', 'value', 'Value', 'expr', {'histogram', 'box', 'violin', 'bar', 'pie'}, 'e.g. mass:Ag'),
    ('Data', 'a', 'Top corner (A)', 'expr', {'ternary'}, 'e.g. Ag'),
    ('Data', 'b', 'Left corner (B)', 'expr', {'ternary'}, 'e.g. Au'),
    ('Data', 'c', 'Right corner (C)', 'expr', {'ternary'}, 'e.g. Cu'),
    ('Data', 'filter', 'Only particles where', 'mask', ALL - {'text'}, 'e.g. Ag > 0 and Au > 0'),
    ('Data', 'drop_zeros', 'Hide zero values', 'check', XY | {'histogram', 'box', 'violin'}, None),
    ('Groups and colours', 'group_by', 'Group / colour by', 'combo',
     {'scatter', 'histogram', 'box', 'violin', 'bar', 'pie', 'ternary', 'code'}, E.GROUP_MODES),
    ('Groups and colours', 'rules', 'Rules (first match wins)', 'rules', set(), None),
    ('Groups and colours', 'show_other', 'Show particles matching no rule', 'check', set(), None),
    ('Groups and colours', 'other_label', 'Name for the rest', 'text', set(), None),
    ('Groups and colours', 'color', 'Colour', 'color',
     {'scatter', 'histogram', 'box', 'violin', 'bar', 'ternary'}, None),
    ('Groups and colours', 'color_by', 'Colour scale by', 'expr', {'scatter'}, 'optional, e.g. total'),
    ('Groups and colours', 'colormap', 'Colour map', 'combo', {'scatter', 'density'},
     {k: k for k in ('viridis', 'magma', 'plasma', 'cividis', 'Blues', 'Greys', 'coolwarm')}),
    ('Groups and colours', 'y2_color', 'Right axis colour', 'color', {'scatter'}, None),
    ('Appearance', 'marker_size', 'Marker size', 'float', {'scatter', 'ternary'}, (1, 200, 1)),
    ('Appearance', 'alpha', 'Opacity', 'float', {'scatter', 'ternary'}, (0.05, 1, 0.05)),
    ('Appearance', 'bins', 'Bins', 'int', {'histogram', 'density'}, (2, 500)),
    ('Appearance', 'hist_style', 'Style', 'combo', {'histogram'},
     {'filled': 'Filled', 'step': 'Outline'}),
    ('Appearance', 'density', 'Normalise (density)', 'check', {'histogram'}, None),
    ('Appearance', 'show_points', 'Show individual points', 'check', {'box', 'violin'}, None),
    ('Appearance', 'agg', 'Bar height', 'combo', {'bar'},
     {'mean': 'Mean', 'median': 'Median', 'sum': 'Sum', 'count': 'Particle count'}),
    ('Appearance', 'error', 'Error bars', 'combo', {'bar'},
     {'sd': 'Standard deviation', 'sem': 'Standard error', 'ci95': '95% CI', 'none': 'None'}),
    ('Appearance', 'pie_mode', 'Slices are', 'combo', {'pie'},
     {'groups': 'Particle count per group', 'values': 'Share of the Value list'}),
    ('Appearance', 'donut', 'Donut', 'check', {'pie'}, None),
    ('Appearance', 'legend', 'Legend', 'check', {'scatter', 'histogram', 'bar', 'ternary', 'pie'}, None),
    ('Appearance', 'grid', 'Grid', 'check', PLOTS | {'ternary'}, None),
    ('Axes', 'x_label', 'X label', 'text', XY | {'histogram'}, 'automatic'),
    ('Axes', 'y_label', 'Y label', 'text', PLOTS, 'automatic'),
    ('Axes', 'y2_label', 'Right Y label', 'text', {'scatter'}, 'automatic'),
    ('Axes', 'log_x', 'Log X', 'check', XY | {'histogram'}, None),
    ('Axes', 'log_y', 'Log Y', 'check', PLOTS, None),
    ('Axes', 'log_y2', 'Log right Y', 'check', {'scatter'}, None),
    ('Axes', 'x_min', 'X min', 'text', XY | {'histogram'}, 'auto'),
    ('Axes', 'x_max', 'X max', 'text', XY | {'histogram'}, 'auto'),
    ('Axes', 'y_min', 'Y min', 'text', PLOTS, 'auto'),
    ('Axes', 'y_max', 'Y max', 'text', PLOTS, 'auto'),
    ('Axes', 'hlines', 'Horizontal lines at', 'text', PLOTS, 'e.g. 1, 10'),
    ('Axes', 'vlines', 'Vertical lines at', 'text', XY | {'histogram'}, 'e.g. 100'),
    ('Axes', 'diagonal', 'y = x line', 'check', {'scatter'}, None),
    ('Statistics', 'show_fit', 'Fit line', 'check', {'scatter'}, None),
    ('Statistics', 'show_r', 'Show r and R²', 'check', {'scatter'}, None),
    ('Statistics', 'test', 'Compare groups with', 'combo', TESTABLE, E.STAT_TESTS),
    ('Statistics', 'pairs', 'Pairs', 'combo', set(),
     {'all': 'Every pair', 'first': 'Each group vs the first'}),
    ('Statistics', 'correction', 'Multiple comparisons', 'combo', set(), E.CORRECTIONS),
    ('Statistics', 'p_format', 'Show p as', 'combo', set(),
     {'stars': 'Stars (*, **, ns)', 'p': 'Numbers (p = …)'}),
    ('Text', 'text', 'Text', 'longtext', {'text'}, None),
    ('Python', 'code', 'Code', 'code', {'code'}, None),
]
"""(section, key, label, widget type, kinds, options) for every panel field."""


class ExpressionEdit(QLineEdit):
    """Line edit that completes isotope and column names word by word."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = QStringListModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setWidget(self)
        self._completer.activated.connect(self._insert)
        self.textEdited.connect(self._on_edit)
        mono = QFont('Menlo')
        mono.setStyleHint(QFont.Monospace)
        self.setFont(mono)

    def set_names(self, names):
        """Set the names offered for completion."""
        self._model.setStringList(sorted(set(names), key=lambda s: (len(s), s)))

    def _token(self):
        before = self.text()[:self.cursorPosition()]
        m = re.search(r'[A-Za-z0-9_:]+$', before)
        return m.group(0) if m else ''

    def _on_edit(self, _text):
        tok = self._token()
        if not tok or tok[0].isdigit() and len(tok) < 2:
            self._completer.popup().hide()
            return
        self._completer.setCompletionPrefix(tok)
        if self._completer.completionCount() == 0 or (
                self._completer.completionCount() == 1
                and self._completer.currentCompletion() == tok):
            self._completer.popup().hide()
            return
        self._completer.complete()

    def _insert(self, text):
        tok = self._token()
        pos = self.cursorPosition()
        full = self.text()
        new = full[:pos - len(tok)] + text + full[pos:]
        self.setText(new)
        self.setCursorPosition(pos - len(tok) + len(text))
        self.textEdited.emit(new)


class ColorButton(QPushButton):
    """Small swatch button that opens the app's colour picker."""

    color_changed = Signal(str)

    def __init__(self, color='#2a78d6', parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 22)
        self.clicked.connect(self._pick)
        self.set_color(color)

    def set_color(self, color):
        """Show ``color`` on the swatch."""
        self._color = color or '#2a78d6'
        self.setStyleSheet(f'QPushButton {{ background: {self._color}; border: 1px solid #888;'
                           f' border-radius: 4px; }}')

    def color(self):
        """Return the current colour as hex."""
        return self._color

    def _pick(self):
        try:
            from results.shared_plot_utils import pick_color_hex
            picked = pick_color_hex(self._color, self, 'Choose colour')
        except Exception:
            from PySide6.QtWidgets import QColorDialog
            c = QColorDialog.getColor(QColor(self._color), self)
            picked = c.name() if c.isValid() else None
        if picked:
            self.set_color(picked)
            self.color_changed.emit(picked)


class RulesTable(QWidget):
    """Editable list of colour rules: name, condition and colour."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Name', 'Condition', 'Colour'])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 90)
        self.table.setColumnWidth(2, 56)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setMinimumHeight(110)
        self.table.itemChanged.connect(lambda _i: self._emit())
        lay.addWidget(self.table)
        row = QHBoxLayout()
        add = QPushButton('+ Add rule')
        add.clicked.connect(self._add)
        rem = QPushButton('Remove')
        rem.clicked.connect(self._remove)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch()
        lay.addLayout(row)
        self._loading = False
        self._table_source = None

    def set_rules(self, rules):
        """Load a list of ``{'name', 'when', 'color'}`` dicts."""
        self._loading = True
        self.table.setRowCount(0)
        for r in rules or []:
            self._append(r.get('name', ''), r.get('when', ''), r.get('color'))
        self._loading = False
        self.mark_errors()

    def rules(self):
        """Return the rules currently shown."""
        out = []
        for i in range(self.table.rowCount()):
            name = (self.table.item(i, 0) or QTableWidgetItem('')).text()
            when = (self.table.item(i, 1) or QTableWidgetItem('')).text()
            btn = self.table.cellWidget(i, 2)
            out.append({'name': name, 'when': when, 'color': btn.color() if btn else None})
        return out

    def _append(self, name, when, color):
        i = self.table.rowCount()
        self.table.insertRow(i)
        self.table.setItem(i, 0, QTableWidgetItem(name))
        self.table.setItem(i, 1, QTableWidgetItem(when))
        btn = ColorButton(color or E.PALETTE[(i + 1) % len(E.PALETTE)])
        btn.color_changed.connect(lambda _c: self._emit())
        self.table.setCellWidget(i, 2, btn)

    def _add(self):
        self._loading = True
        n = self.table.rowCount()
        self._append(f'Group {n + 1}', '', E.PALETTE[(n + 1) % len(E.PALETTE)])
        self._loading = False
        self.table.editItem(self.table.item(n, 1))

    def _remove(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not rows and self.table.rowCount():
            rows = [self.table.rowCount() - 1]
        for r in rows:
            self.table.removeRow(r)
        self._emit()

    def set_table_source(self, table):
        """Give the particle table used to check conditions."""
        self._table_source = table
        self.mark_errors()

    def mark_errors(self):
        """Colour conditions red when they do not evaluate."""
        self._loading, was = True, self._loading
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 1)
            if item is None:
                continue
            msg = None
            if self._table_source is not None and len(self._table_source) and item.text().strip():
                msg = validate(item.text(), self._table_source)
            item.setForeground(QColor('#b42318') if msg else QColor())
            item.setToolTip(msg or '')
        self._loading = was

    def _emit(self):
        if self._loading:
            return
        self.mark_errors()
        self.changed.emit()


class PanelEditor(QWidget):
    """Form editing the settings of the selected panel.

    Signals:
        changed(): any field of the panel changed.
        kind_changed(): the chart type changed (the sketch glyph needs a repaint).
    """

    changed = Signal()
    kind_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.panel = None
        self.table = None
        self._loading = False
        self.widgets: dict = {}
        self.rows: dict = {}
        self.sections: dict = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        self.empty = QLabel('Select a panel on the page, or drag on the page to draw a new one.')
        self.empty.setWordWrap(True)
        self.empty.setStyleSheet('color: #6b7280; padding: 12px;')
        root.addWidget(self.empty)
        self.error = QLabel('')
        self.error.setWordWrap(True)
        self.error.setStyleSheet('color: #b42318; font-weight: 600; padding: 2px 4px;')
        self.error.hide()
        root.addWidget(self.error)
        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)
        for section, key, label, kind, _kinds, opts in FIELDS:
            if section not in self.sections:
                box = QGroupBox(section)
                form = QFormLayout(box)
                form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
                form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.sections[section] = (box, form)
                body.addWidget(box)
            box, form = self.sections[section]
            w = self._make(key, kind, opts)
            self.widgets[key] = (kind, w)
            if kind in ('rules', 'code', 'longtext'):
                lab = QLabel(label)
                form.addRow(lab)
                form.addRow(w)
                self.rows[key] = (lab, w)
            else:
                form.addRow(label, w)
                self.rows[key] = (form.labelForField(w), w)
        body.addStretch()
        root.addWidget(self.body)
        self.body.hide()

    def _make(self, key, kind, opts):
        """Create the widget for one field and wire it to the panel."""
        if kind == 'combo':
            w = QComboBox()
            for k, label in opts.items():
                w.addItem(label, k)
            w.currentIndexChanged.connect(lambda _i, k=key, ww=w: self._set(k, ww.currentData()))
        elif kind in ('text', 'expr', 'mask'):
            w = ExpressionEdit() if kind in ('expr', 'mask') else QLineEdit()
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
            w.valueChanged.connect(lambda v, k=key: self._set(k, float(v)))
        elif kind == 'int':
            w = QSpinBox()
            w.setRange(*opts)
            w.valueChanged.connect(lambda v, k=key: self._set(k, int(v)))
        elif kind == 'color':
            w = ColorButton()
            w.color_changed.connect(lambda c, k=key: self._set(k, c))
        elif kind == 'rules':
            w = RulesTable()
            w.changed.connect(lambda ww=w: self._set('rules', ww.rules()))
        elif kind == 'longtext':
            w = QPlainTextEdit()
            w.setMinimumHeight(90)
            w.textChanged.connect(lambda ww=w: self._set('text', ww.toPlainText()))
        else:
            w = QPlainTextEdit()
            mono = QFont('Menlo')
            mono.setStyleHint(QFont.Monospace)
            w.setFont(mono)
            w.setMinimumHeight(200)
            w.setPlaceholderText(
                'Variables: ax, fig, df (one row per particle), labels, groups, '
                'group_colors, col("Fe/Cu"), color(i), np, pd, stats, report("text")\n\n'
                + E.CODE_EXAMPLE)
            w.textChanged.connect(lambda ww=w: self._set('code', ww.toPlainText()))
        return w

    def set_table(self, table):
        """Give the editor the particle table for completion and checks."""
        self.table = table
        names = table.names() if table is not None else []
        for _key, (kind, w) in self.widgets.items():
            if isinstance(w, ExpressionEdit):
                w.set_names(names + list(_FUNCTION_HINTS))
            if isinstance(w, RulesTable):
                w.set_table_source(table)
        self._check_expressions()

    def set_panel(self, panel):
        """Show ``panel`` (a dict, edited in place) or nothing when None."""
        self.panel = panel
        self.empty.setVisible(panel is None)
        self.body.setVisible(panel is not None)
        if panel is None:
            self.error.hide()
            return
        self._loading = True
        for key, (kind, w) in self.widgets.items():
            v = panel.get(key, E.PANEL_DEFAULTS.get(key))
            if kind == 'combo':
                i = w.findData(v)
                w.setCurrentIndex(max(0, i))
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
            elif kind == 'rules':
                w.set_rules(v)
            else:
                if w.toPlainText() != (v or ''):
                    w.setPlainText(v or '')
        self._loading = False
        self._update_visibility()
        self._check_expressions()

    def show_error(self, message):
        """Show the last render error of this panel (or hide it)."""
        self.error.setText(f'⚠ {message}' if message else '')
        self.error.setVisible(bool(message) and self.panel is not None)

    def _set(self, key, value):
        if self._loading or self.panel is None:
            return
        self.panel[key] = value
        if key in ('kind', 'group_by', 'test', 'pie_mode'):
            if key == 'kind' and value == 'code' and not (self.panel.get('code') or '').strip():
                self.panel['code'] = E.CODE_EXAMPLE
                self._loading = True
                self.widgets['code'][1].setPlainText(E.CODE_EXAMPLE)
                self._loading = False
            self._update_visibility()
            if key in ('kind', 'pie_mode'):
                self.kind_changed.emit()
        if self.widgets.get(key, (None,))[0] in ('expr', 'mask'):
            self._check_expressions()
        self.changed.emit()

    def _visible(self, key, kinds):
        """Whether ``key`` should show for the current panel state."""
        p = self.panel
        kind = p.get('kind')
        group = p.get('group_by', 'none')
        if key in ('rules', 'show_other', 'other_label'):
            return group == 'rules' and kind in self._kinds('group_by')
        if key in ('pairs', 'correction', 'p_format'):
            if kind not in TESTABLE or p.get('test') not in E.PAIRWISE_TESTS:
                return False
            return not (key == 'p_format' and kind == 'histogram')
        if key == 'color':
            return kind in kinds and (group == 'none' or kind not in self._kinds('group_by'))
        if key == 'value' and kind == 'pie':
            return p.get('pie_mode') == 'values'
        return kind in kinds

    @staticmethod
    def _kinds(key):
        for _s, k, _l, _t, kinds, _o in FIELDS:
            if k == key:
                return kinds
        return set()

    def _update_visibility(self):
        if self.panel is None:
            return
        shown = {name: False for name in self.sections}
        for section, key, _label, _t, kinds, _o in FIELDS:
            vis = self._visible(key, kinds)
            lab, w = self.rows[key]
            if lab is not None:
                lab.setVisible(vis)
            w.setVisible(vis)
            shown[section] = shown[section] or vis
        for name, (box, _form) in self.sections.items():
            box.setVisible(shown[name])
        value_label = self.rows['value'][0]
        if value_label is not None:
            multi = self.panel.get('kind') in ('bar', 'pie')
            value_label.setText('Values (comma separated)' if multi else 'Value')

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
                if key in ('value',) and self.panel.get('kind') in ('bar', 'pie'):
                    from results.figure_builder.expressions import split_list
                    for part in split_list(text):
                        msg = validate(part, self.table) or msg
                else:
                    msg = validate(text, self.table)
            w.setStyleSheet('QLineEdit { border: 1.5px solid #b42318; border-radius: 4px; }'
                            if msg else '')
            w.setToolTip(msg or '')


_FUNCTION_HINTS = ('log', 'ln', 'sqrt', 'abs', 'exp', 'min', 'max', 'where',
                   'mean', 'median', 'std', 'percentile')
