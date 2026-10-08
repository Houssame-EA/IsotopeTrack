"""Reusable widgets for the Figure Builder editor.

* :class:`ExpressionEdit` — line edit with word-by-word completion of
  isotopes, variables and functions, and a red border when invalid.
* :class:`ColorButton` — colour swatch opening the app's colour picker.
* :class:`RowTable` — small spreadsheet of dicts (rules, overlay series,
  annotations, variables) with typed columns.
* :class:`GroupsTable` — show/hide, rename, recolour and reorder groups.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QStringListModel, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QCompleter, QDoubleSpinBox,
    QHBoxLayout, QHeaderView, QLineEdit, QPushButton,
    QStyledItemDelegate, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from results.figure_builder.core.expressions import validate


def _danger() -> str:
    from results.figure_builder.ui.look import danger
    return danger()


def mono_font() -> QFont:
    """A monospace font for expressions and code."""
    f = QFont('Menlo')
    f.setStyleHint(QFont.Monospace)
    return f


class ExpressionEdit(QLineEdit):
    """Line edit that completes isotope and column names word by word.

    Signals:
        focused(object): emitted with itself when it gains focus, so a chip
            bar knows where to insert.
    """

    focused = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = QStringListModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setWidget(self)
        self._completer.activated.connect(self._insert)
        self.textEdited.connect(self._on_edit)
        self.setFont(mono_font())

    def set_names(self, names):
        """Set the names offered for completion."""
        self._model.setStringList(sorted(set(names), key=lambda s: (len(s), s)))

    def focusInEvent(self, ev):
        super().focusInEvent(ev)
        self.focused.emit(self)

    def _token(self):
        before = self.text()[:self.cursorPosition()]
        m = re.search(r'[A-Za-z0-9_:]+$', before)
        return m.group(0) if m else ''

    def _on_edit(self, _text):
        tok = self._token()
        if not tok or (tok[0].isdigit() and len(tok) < 2):
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

    def insert_text(self, text: str):
        """Insert ``text`` at the cursor, adding spaces around operators."""
        pos = self.cursorPosition()
        full = self.text()
        new = full[:pos] + text + full[pos:]
        self.setText(new)
        self.setCursorPosition(pos + len(text))
        self.setFocus()
        self.textEdited.emit(new)

    def mark(self, message: str | None):
        """Show ``message`` as an error (red border + tooltip), or clear it."""
        self.setProperty('invalid', bool(message))
        self.style().unpolish(self)
        self.style().polish(self)
        self.setToolTip(message or '')


class ColorButton(QPushButton):
    """Small swatch button that opens the app's colour picker."""

    color_changed = Signal(str)

    def __init__(self, color='#2a78d6', parent=None, allow_none=False):
        super().__init__(parent)
        self.setFixedSize(44, 22)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self._pick)
        self._allow_none = allow_none
        self.set_color(color)

    def set_color(self, color):
        """Show ``color`` on the swatch (empty means automatic)."""
        self._color = color or ''
        if self._color:
            self.setStyleSheet(f'QPushButton {{ background: {self._color}; border: 1px solid #888;'
                               f' border-radius: 4px; }}')
            self.setText('')
            self.setToolTip(self._color)
        else:
            self.setStyleSheet('QPushButton { border: 1px dashed #888; border-radius: 4px;'
                               ' font-size: 9px; }')
            self.setText('auto')
            self.setToolTip('Automatic colour')

    def color(self):
        """Return the current colour as hex (empty string for automatic)."""
        return self._color

    def _pick(self):
        try:
            from results.shared_plot_utils import pick_color_hex
            picked = pick_color_hex(self._color or '#2a78d6', self, 'Choose colour')
        except Exception:
            from PySide6.QtWidgets import QColorDialog
            c = QColorDialog.getColor(QColor(self._color or '#2a78d6'), self)
            picked = c.name() if c.isValid() else None
        if picked:
            self.set_color(picked)
            self.color_changed.emit(picked)

    def contextMenuEvent(self, ev):
        if not self._allow_none:
            return
        self.set_color('')
        self.color_changed.emit('')


class _MonoDelegate(QStyledItemDelegate):
    """Item delegate giving expression cells a monospace editor."""

    def createEditor(self, parent, option, index):
        ed = super().createEditor(parent, option, index)
        if isinstance(ed, QLineEdit):
            ed.setFont(mono_font())
        return ed


class RowTable(QWidget):
    """Editable table of dict rows with typed columns.

    Args:
        columns: list of ``(key, header, kind, options, width)`` where kind is
            ``text``, ``expr``, ``mask``, ``color``, ``combo``, ``float`` or
            ``check``; options is a dict for combos, a ``(lo, hi, step)``
            tuple for floats.
        add_label: Caption of the add button.
        new_row: Callable returning the dict for a new row.

    Signals:
        changed(): rows were edited, added, removed or moved.
    """

    changed = Signal()

    def __init__(self, columns, add_label='+ Add', new_row=None, parent=None):
        super().__init__(parent)
        self.columns = columns
        self.new_row = new_row or (lambda i: {})
        self._table_source = None
        self._loading = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels([c[1] for c in columns])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        self.table.setItemDelegate(_MonoDelegate(self.table))
        self.table.setWordWrap(False)
        self.table.setMinimumHeight(96)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        hh = self.table.horizontalHeader()
        stretch_col = next((i for i, c in enumerate(columns) if c[2] in ('expr', 'mask')),
                           next((i for i, c in enumerate(columns) if c[2] == 'text'), 0))
        for i, c in enumerate(columns):
            if i == stretch_col:
                hh.setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                hh.setSectionResizeMode(i, QHeaderView.Interactive)
                self.table.setColumnWidth(i, c[4] if len(c) > 4 and c[4] else 70)
        self.table.itemChanged.connect(lambda _i: self._emit())
        lay.addWidget(self.table)
        row = QHBoxLayout()
        row.setSpacing(4)
        add = QPushButton(add_label)
        add.clicked.connect(self._add)
        row.addWidget(add)
        for text, slot, tip in (('▲', lambda: self._move(-1), 'Move up'),
                                ('▼', lambda: self._move(1), 'Move down'),
                                ('Remove', self._remove, 'Remove the selected row')):
            b = QPushButton(text)
            b.setToolTip(tip)
            if len(text) == 1:
                b.setFixedWidth(30)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)

    def set_rows(self, rows):
        """Load a list of dicts."""
        self._loading = True
        self.table.setRowCount(0)
        for r in rows or []:
            self._append(r)
        self._fit_height()
        self._loading = False
        self.mark_errors()

    def rows(self):
        """Return the rows currently shown, as dicts."""
        out = []
        for i in range(self.table.rowCount()):
            row = {}
            for j, (key, _h, kind, _o, *_w) in enumerate(self.columns):
                if kind == 'color':
                    w = self.table.cellWidget(i, j)
                    row[key] = w.color() if w else ''
                elif kind == 'combo':
                    w = self.table.cellWidget(i, j)
                    row[key] = w.currentData() if w else None
                elif kind == 'check':
                    w = self.table.cellWidget(i, j)
                    row[key] = bool(w.findChild(QCheckBox).isChecked()) if w else False
                elif kind == 'float':
                    w = self.table.cellWidget(i, j)
                    row[key] = float(w.value()) if w else 0.0
                else:
                    item = self.table.item(i, j)
                    row[key] = item.text() if item else ''
            out.append(row)
        return out

    def _append(self, data):
        i = self.table.rowCount()
        self.table.insertRow(i)
        for j, (key, _h, kind, opts, *_w) in enumerate(self.columns):
            v = data.get(key)
            if kind == 'color':
                w = ColorButton(v or '', allow_none=True)
                w.color_changed.connect(lambda _c: self._emit())
                self.table.setCellWidget(i, j, w)
            elif kind == 'combo':
                w = QComboBox()
                for k, lab in opts.items():
                    w.addItem(lab, k)
                w.setCurrentIndex(max(0, w.findData(v)))
                w.currentIndexChanged.connect(lambda _i: self._emit())
                self.table.setCellWidget(i, j, w)
            elif kind == 'check':
                holder = QWidget()
                hl = QHBoxLayout(holder)
                hl.setContentsMargins(0, 0, 0, 0)
                hl.setAlignment(Qt.AlignCenter)
                cb = QCheckBox()
                cb.setChecked(bool(v))
                cb.toggled.connect(lambda _v: self._emit())
                hl.addWidget(cb)
                self.table.setCellWidget(i, j, holder)
            elif kind == 'float':
                w = QDoubleSpinBox()
                lo, hi, step = opts
                w.setRange(lo, hi)
                w.setSingleStep(step)
                w.setValue(float(v or 0))
                w.valueChanged.connect(lambda _v: self._emit())
                self.table.setCellWidget(i, j, w)
            else:
                item = QTableWidgetItem('' if v is None else str(v))
                if kind in ('expr', 'mask'):
                    item.setFont(mono_font())
                self.table.setItem(i, j, item)

    def _fit_height(self):
        n = self.table.rowCount()
        h = self.table.horizontalHeader().height() + max(2, min(n, 8)) * 30 + 6
        self.table.setMinimumHeight(h)
        self.table.setMaximumHeight(h + 4)

    def _add(self):
        self._loading = True
        self._append(self.new_row(self.table.rowCount()))
        self._fit_height()
        self._loading = False
        self._emit()
        first = next((j for j, c in enumerate(self.columns) if c[2] in ('expr', 'mask', 'text')), None)
        if first is not None:
            last = self.table.rowCount() - 1
            self.table.setCurrentCell(last, first)
            self.table.editItem(self.table.item(last, first))

    def _selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return rows

    def _remove(self):
        rows = self._selected()
        if not rows and self.table.rowCount():
            rows = [self.table.rowCount() - 1]
        for r in reversed(rows):
            self.table.removeRow(r)
        self._fit_height()
        self._emit()

    def _move(self, step):
        rows = self._selected()
        if len(rows) != 1:
            return
        data = self.rows()
        i = rows[0]
        j = i + step
        if not 0 <= j < len(data):
            return
        data[i], data[j] = data[j], data[i]
        self.set_rows(data)
        self.table.selectRow(j)
        self.changed.emit()

    def set_table_source(self, table):
        """Give the particle table used to check expression cells."""
        self._table_source = table
        self.mark_errors()

    def mark_errors(self):
        """Colour expression cells red when they do not evaluate."""
        was, self._loading = self._loading, True
        for j, (_k, _h, kind, _o, *_w) in enumerate(self.columns):
            if kind not in ('expr', 'mask'):
                continue
            for i in range(self.table.rowCount()):
                item = self.table.item(i, j)
                if item is None:
                    continue
                msg = None
                src = self._table_source
                if src is not None and len(src) and item.text().strip():
                    msg = validate(item.text(), src)
                item.setForeground(QColor(_danger()) if msg else QColor())
                item.setToolTip(msg or '')
        self._loading = was

    def _emit(self):
        if self._loading:
            return
        self.mark_errors()
        self.changed.emit()


class GroupsTable(QWidget):
    """Show/hide, rename, recolour and reorder the groups of a panel.

    Signals:
        changed(): the panel's group overrides were edited.
    """

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.panel = None
        self._loading = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Show', 'Group', 'Legend name', 'Colour'])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 44)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(3, 58)
        self.table.itemChanged.connect(self._on_item)
        lay.addWidget(self.table)
        row = QHBoxLayout()
        for text, slot, tip in (('▲', lambda: self._move(-1), 'Move up'),
                                ('▼', lambda: self._move(1), 'Move down'),
                                ('Reset', self._reset, 'Forget custom names, colours, order and hidden groups')):
            b = QPushButton(text)
            b.setToolTip(tip)
            if len(text) == 1:
                b.setFixedWidth(30)
            b.clicked.connect(slot)
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        self._keys: list[str] = []

    def set_groups(self, panel, groups):
        """Show ``groups`` (from :func:`engine.candidate_groups`) for ``panel``."""
        self.panel = panel
        self._loading = True
        colors = panel.get('group_colors') or {}
        labels = panel.get('group_labels') or {}
        hidden = set(panel.get('hidden_groups') or [])
        order = list(panel.get('group_order') or [])
        rank = {k: i for i, k in enumerate(order)}
        groups = sorted(groups, key=lambda g: rank.get(g.key, len(rank)))
        self._keys = [g.key for g in groups]
        self.table.setRowCount(0)
        for i, g in enumerate(groups):
            self.table.insertRow(i)
            holder = QWidget()
            hl = QHBoxLayout(holder)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setAlignment(Qt.AlignCenter)
            cb = QCheckBox()
            cb.setChecked(g.key not in hidden)
            cb.toggled.connect(self._commit)
            hl.addWidget(cb)
            self.table.setCellWidget(i, 0, holder)
            name = QTableWidgetItem(g.key if not g.key.startswith('__') else g.label)
            name.setFlags(name.flags() & ~Qt.ItemIsEditable)
            name.setToolTip(f'{int(g.mask.sum())} particles')
            self.table.setItem(i, 1, name)
            self.table.setItem(i, 2, QTableWidgetItem(labels.get(g.key, '')))
            btn = ColorButton(colors.get(g.key) or g.color)
            btn.color_changed.connect(lambda _c: self._commit())
            self.table.setCellWidget(i, 3, btn)
        n = len(groups)
        self.table.setFixedHeight(self.table.horizontalHeader().height() + max(1, min(n, 8)) * 30 + 6)
        self._loading = False

    def _on_item(self, _item):
        if not self._loading:
            self._commit()

    def _commit(self, *_args):
        if self._loading or self.panel is None:
            return
        hidden, labels, colors = [], {}, {}
        for i, key in enumerate(self._keys):
            holder = self.table.cellWidget(i, 0)
            if holder is not None and not holder.findChild(QCheckBox).isChecked():
                hidden.append(key)
            item = self.table.item(i, 2)
            if item is not None and item.text().strip():
                labels[key] = item.text().strip()
            btn = self.table.cellWidget(i, 3)
            if btn is not None:
                colors[key] = btn.color()
        self.panel['hidden_groups'] = hidden
        self.panel['group_labels'] = labels
        self.panel['group_colors'] = colors
        self.panel['group_order'] = list(self._keys)
        self.changed.emit()

    def _move(self, step):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if len(rows) != 1 or self.panel is None:
            return
        i, j = rows[0], rows[0] + step
        if not 0 <= j < len(self._keys):
            return
        self._commit()
        keys = list(self._keys)
        keys[i], keys[j] = keys[j], keys[i]
        self.panel['group_order'] = keys
        self.changed.emit()
        self.table.selectRow(j)

    def _reset(self):
        if self.panel is None:
            return
        for k in ('hidden_groups', 'group_order'):
            self.panel[k] = []
        for k in ('group_labels', 'group_colors'):
            self.panel[k] = {}
        self.changed.emit()
