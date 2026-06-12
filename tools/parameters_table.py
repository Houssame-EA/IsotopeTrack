"""
Drop-in replacement for the QTableWidget used as the parameters table in
IsotopeTrack.
"""

from contextlib import contextmanager

from PySide6.QtCore import (Qt, QAbstractTableModel, QModelIndex, QRect,
                             QEvent, Signal)
from PySide6.QtGui import QBrush, QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QHeaderView, QHBoxLayout, QSpinBox, QStyle, QStyleOptionButton,
    QStyledItemDelegate, QTableView, QWidget,
)

COL_ELEMENT   = 0
COL_INCLUDE   = 1
COL_METHOD    = 2
COL_SIGMA     = 3
COL_THRESHOLD = 4
COL_MIN_CONT  = 5
COL_ALPHA     = 6
COL_ITERATIVE = 7
COL_WINDOW    = 8
COL_INTEG     = 9
COL_SPLIT     = 10
COL_VALLEY    = 11

NUM_COLUMNS = 12

_HEADERS = [
    'Element', 'Include', 'Detection Method', 'Sigma',
    'Manual Threshold', 'Min Points', 'Alpha (Error Rate)', 'Iterative',
    'Window Size', 'Integration Method', 'Split Method', 'Valley Ratio',
]

_TOOLTIPS = [
    'element',
    'include in analysis',
    'detection method',
    'per-isotope sigma for Compound Poisson LogNormal',
    'manual threshold value (when Manual method selected)',
    'minimum continuous dwell time points above the threshold',
    'Alpha',
    'iterative background calculation (recommended)',
    'window size for background calculation',
    'integration method',
    'split method',
    'valley ratio for watershed',
]

METHOD_OPTIONS = ["Manual", "Compound Poisson LogNormal", "CPLN table"]
INTEG_OPTIONS  = ["Background", "Threshold", "Midpoint"]
SPLIT_OPTIONS  = ["No Splitting", "1D Watershed"]

_SIGMA_HIGHLIGHT_LIGHT = "#FFF3CD"
_SIGMA_HIGHLIGHT_DARK  = "#3a3a1f"

_SUP = str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')


def _fmt_alpha(v):
    """Return alpha as compact scientific notation, e.g. 1x10^-6."""
    if v == 0:
        return '0'
    exp = int('{:.0e}'.format(v).split('e')[1])
    mant = v / (10 ** exp)
    mant_s = '{:.2g}'.format(mant).rstrip('0').rstrip('.')
    sup = str(exp).replace('-', '⁻').translate(_SUP)
    return '{}×10{}'.format(mant_s, sup)


# ==============================================================================
# Model
# ==============================================================================
class ParametersModel(QAbstractTableModel):
    """Stores all parameter data as a list of plain Python dicts.
    No Qt widgets are ever created here."""

    cellChanged = Signal(int, int)

    sigma_hl_color = _SIGMA_HIGHLIGHT_LIGHT

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self._suppress = False

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return NUM_COLUMNS

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return _HEADERS[section]
            if role == Qt.ToolTipRole:
                return _TOOLTIPS[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if index.column() == COL_ELEMENT:
            return base
        return base | Qt.ItemIsEditable

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        r, c = index.row(), index.column()
        d = self._rows[r]

        if role == Qt.DisplayRole:
            return _display(d, c)
        if role == Qt.EditRole:
            return _edit_value(d, c)
        if role == Qt.CheckStateRole:
            if c == COL_INCLUDE:
                return Qt.Checked if d['include'] else Qt.Unchecked
            if c == COL_ITERATIVE:
                return Qt.Checked if d['iterative'] else Qt.Unchecked
        if role == Qt.BackgroundRole:
            bg = d.get('_bg_color')
            if bg is not None:
                return bg
            if c == COL_SIGMA and d.get('_sigma_highlighted'):
                return QBrush(QColor(ParametersModel.sigma_hl_color))
            return None
        if role == Qt.ForegroundRole:
            return d.get('_fg_color')
        if role == Qt.UserRole:
            return d
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False
        r, c = index.row(), index.column()
        d = self._rows[r]

        if role == Qt.CheckStateRole:
            if c == COL_INCLUDE:
                d['include'] = (value == Qt.Checked)
            elif c == COL_ITERATIVE:
                d['iterative'] = (value == Qt.Checked)
            else:
                return False
            self.dataChanged.emit(index, index, [role, Qt.DisplayRole])
            if not self._suppress:
                self.cellChanged.emit(r, c)
            return True

        if role == Qt.EditRole:
            _apply_edit(d, c, value)
            self.dataChanged.emit(index, index, [role, Qt.DisplayRole])
            if not self._suppress:
                self.cellChanged.emit(r, c)
            return True

        if role == Qt.BackgroundRole:
            d['_bg_color'] = value
            self._emit_row(r, [Qt.BackgroundRole])
            return True

        if role == Qt.ForegroundRole:
            d['_fg_color'] = value
            self._emit_row(r, [Qt.ForegroundRole])
            return True

        return False

    def _emit_row(self, row, roles):
        tl = self.index(row, 0)
        br = self.index(row, NUM_COLUMNS - 1)
        self.dataChanged.emit(tl, br, roles)

    def populate(self, rows):
        self.beginResetModel()
        self._rows = [dict(r) for r in rows]
        self.endResetModel()

    def clear(self):
        self.populate([])

    def row_data(self, row):
        if 0 <= row < len(self._rows):
            return dict(self._rows[row])
        return {}

    def set_field(self, row, field, value, emit_changed=False):
        if not (0 <= row < len(self._rows)):
            return
        self._rows[row][field] = value
        col = _FIELD_TO_COL.get(field, 0)
        idx = self.index(row, col)
        self.dataChanged.emit(idx, idx, [Qt.DisplayRole, Qt.EditRole,
                                         Qt.BackgroundRole])
        if emit_changed and not self._suppress:
            self.cellChanged.emit(row, col)

    def set_row_colors(self, row, bg=None, fg=None):
        if not (0 <= row < len(self._rows)):
            return
        d = self._rows[row]
        if bg is not None:
            if isinstance(bg, QBrush) and not bg.color().isValid():
                d.pop('_bg_color', None)
            else:
                d['_bg_color'] = bg
        if fg is not None:
            if isinstance(fg, QBrush) and not fg.color().isValid():
                d.pop('_fg_color', None)
            else:
                d['_fg_color'] = fg
        self._emit_row(row, [Qt.BackgroundRole, Qt.ForegroundRole])

    @contextmanager
    def bulk_update(self):
        self._suppress = True
        try:
            yield
        finally:
            self._suppress = False


_FIELD_TO_COL = {
    'include': COL_INCLUDE,
    'method': COL_METHOD,
    'sigma': COL_SIGMA,
    '_sigma_highlighted': COL_SIGMA,
    'manual_threshold': COL_THRESHOLD,
    'min_continuous': COL_MIN_CONT,
    'alpha': COL_ALPHA,
    'iterative': COL_ITERATIVE,
    'use_window_size': COL_WINDOW,
    'window_size': COL_WINDOW,
    'integration_method': COL_INTEG,
    'split_method': COL_SPLIT,
    'valley_ratio': COL_VALLEY,
}


def _display(d, col):
    if col == COL_ELEMENT:   return d.get('element_label', '')
    if col == COL_INCLUDE:   return ''
    if col == COL_METHOD:    return d.get('method', '')
    if col == COL_SIGMA:     return '{:.3f}'.format(d.get('sigma', 0))
    if col == COL_THRESHOLD: return '{:.2f}'.format(d.get('manual_threshold', 0))
    if col == COL_MIN_CONT:  return str(int(d.get('min_continuous', 1)))
    if col == COL_ALPHA:     return _fmt_alpha(d.get('alpha', 0))
    if col == COL_ITERATIVE: return ''
    if col == COL_WINDOW:
        if d.get('use_window_size'):
            return '✓ {}'.format(int(d.get('window_size', 5000)))
        return '☐ —'
    if col == COL_INTEG:     return d.get('integration_method', '')
    if col == COL_SPLIT:     return d.get('split_method', '')
    if col == COL_VALLEY:    return '{:.2f}'.format(d.get('valley_ratio', 0))
    return ''


def _edit_value(d, col):
    if col == COL_INCLUDE:   return d.get('include', True)
    if col == COL_METHOD:    return d.get('method', 'CPLN table')
    if col == COL_SIGMA:     return d.get('sigma', 0.55)
    if col == COL_THRESHOLD: return d.get('manual_threshold', 10.0)
    if col == COL_MIN_CONT:  return d.get('min_continuous', 1.0)
    if col == COL_ALPHA:     return d.get('alpha', 0.000001)
    if col == COL_ITERATIVE: return d.get('iterative', True)
    if col == COL_WINDOW:
        return (d.get('use_window_size', False), d.get('window_size', 5000))
    if col == COL_INTEG:     return d.get('integration_method', 'Background')
    if col == COL_SPLIT:     return d.get('split_method', '1D Watershed')
    if col == COL_VALLEY:    return d.get('valley_ratio', 0.50)
    return None


def _apply_edit(d, col, value):
    if col == COL_INCLUDE:     d['include'] = bool(value)
    elif col == COL_METHOD:    d['method'] = str(value)
    elif col == COL_SIGMA:     d['sigma'] = float(value)
    elif col == COL_THRESHOLD: d['manual_threshold'] = float(value)
    elif col == COL_MIN_CONT:  d['min_continuous'] = float(value)
    elif col == COL_ALPHA:     d['alpha'] = float(value)
    elif col == COL_ITERATIVE: d['iterative'] = bool(value)
    elif col == COL_WINDOW:
        use, size = value
        d['use_window_size'] = bool(use)
        d['window_size'] = int(size)
    elif col == COL_INTEG:   d['integration_method'] = str(value)
    elif col == COL_SPLIT:   d['split_method'] = str(value)
    elif col == COL_VALLEY:  d['valley_ratio'] = float(value)


# ==============================================================================
# Delegate
# ==============================================================================
class ParametersDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        col = index.column()
        self.initStyleOption(option, index)

        style = QApplication.style()
        style.drawPrimitive(QStyle.PE_PanelItemViewItem, option, painter,
                            option.widget)

        rect = option.rect
        d = index.data(Qt.UserRole) or {}

        if col in (COL_INCLUDE, COL_ITERATIVE):
            checked = index.data(Qt.CheckStateRole) == Qt.Checked
            self._paint_check(painter, rect, checked, option)
        else:
            text = index.data(Qt.DisplayRole) or ''
            pal = option.widget.palette() if option.widget else option.palette

            painter.save()
            if option.state & QStyle.State_Selected:
                painter.setPen(pal.highlightedText().color())
            else:
                fg = index.data(Qt.ForegroundRole)
                if fg:
                    painter.setPen(
                        fg.color() if isinstance(fg, QBrush) else QColor(fg))
                elif _is_cell_disabled(d, col):
                    painter.setPen(pal.color(
                        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text))
                else:
                    painter.setPen(pal.text().color())

            painter.drawText(
                rect.adjusted(4, 0, -4, 0),
                Qt.AlignVCenter | Qt.AlignLeft,
                text,
            )
            painter.restore()

    @staticmethod
    def _paint_check(painter, rect, checked, option):
        opt = QStyleOptionButton()
        ind_w = QApplication.style().pixelMetric(QStyle.PM_IndicatorWidth)
        ind_h = QApplication.style().pixelMetric(QStyle.PM_IndicatorHeight)
        x = rect.x() + (rect.width()  - ind_w) // 2
        y = rect.y() + (rect.height() - ind_h) // 2
        opt.rect  = QRect(x, y, ind_w, ind_h)
        opt.state = (QStyle.State_Enabled |
                     (QStyle.State_On if checked else QStyle.State_Off))
        QApplication.style().drawControl(QStyle.CE_CheckBox, opt, painter)

    def editorEvent(self, event, model, option, index):
        col = index.column()

        if col in (COL_INCLUDE, COL_ITERATIVE):
            if event.type() == QEvent.MouseButtonRelease:
                cur = index.data(Qt.CheckStateRole)
                new = Qt.Unchecked if cur == Qt.Checked else Qt.Checked
                model.setData(index, new, Qt.CheckStateRole)
                return True

        if col == COL_WINDOW:
            if event.type() == QEvent.MouseButtonRelease:
                rel_x = event.position().x() - option.rect.x()
                if rel_x < 24:
                    d = index.data(Qt.UserRole) or {}
                    model.setData(index,
                                  (not d.get('use_window_size', False),
                                   d.get('window_size', 5000)),
                                  Qt.EditRole)
                    return True

        return super().editorEvent(event, model, option, index)

    def createEditor(self, parent, option, index):
        col = index.column()

        if col in (COL_INCLUDE, COL_ITERATIVE, COL_ELEMENT):
            return None

        if col == COL_METHOD:
            w = QComboBox(parent)
            w.addItems(METHOD_OPTIONS)
            return w

        if col == COL_SIGMA:
            w = QDoubleSpinBox(parent)
            w.setRange(0.01, 2.0)
            w.setDecimals(3)
            w.setSingleStep(0.01)
            return w

        if col == COL_THRESHOLD:
            w = QDoubleSpinBox(parent)
            w.setRange(0.0, 999999.0)
            w.setDecimals(2)
            w.setSingleStep(10.0)
            return w

        if col == COL_MIN_CONT:
            w = QDoubleSpinBox(parent)
            w.setRange(1, 5)
            w.setDecimals(0)
            w.setSingleStep(1)
            return w

        if col == COL_ALPHA:
            w = QDoubleSpinBox(parent)
            w.setRange(0.00000001, 0.1)
            w.setDecimals(8)
            w.setSingleStep(0.000001)
            return w

        if col == COL_WINDOW:
            container = QWidget(parent)
            layout = QHBoxLayout(container)
            layout.setContentsMargins(2, 2, 2, 2)
            layout.setSpacing(4)
            cb = QCheckBox(container)
            cb.setObjectName('_use_win_cb')
            sp = QSpinBox(container)
            sp.setObjectName('_win_size_sp')
            sp.setRange(10, 100000)
            sp.setSingleStep(100)
            layout.addWidget(cb)
            layout.addWidget(sp)
            return container

        if col == COL_INTEG:
            w = QComboBox(parent)
            w.addItems(INTEG_OPTIONS)
            return w

        if col == COL_SPLIT:
            w = QComboBox(parent)
            w.addItems(SPLIT_OPTIONS)
            return w

        if col == COL_VALLEY:
            w = QDoubleSpinBox(parent)
            w.setRange(0.01, 0.99)
            w.setDecimals(2)
            w.setSingleStep(0.05)
            return w

        return None

    def setEditorData(self, editor, index):
        col = index.column()
        val = index.data(Qt.EditRole)

        if isinstance(editor, QComboBox):
            editor.setCurrentText(str(val) if val is not None else '')
        elif isinstance(editor, QDoubleSpinBox):
            editor.setValue(float(val) if val is not None else 0.0)
        elif col == COL_WINDOW:
            use, size = val if val else (False, 5000)
            cb = editor.findChild(QCheckBox, '_use_win_cb')
            sp = editor.findChild(QSpinBox, '_win_size_sp')
            if cb:
                cb.setChecked(bool(use))
            if sp:
                sp.setValue(int(size))

    def setModelData(self, editor, model, index):
        col = index.column()

        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText(), Qt.EditRole)
        elif isinstance(editor, QDoubleSpinBox):
            model.setData(index, editor.value(), Qt.EditRole)
        elif col == COL_WINDOW:
            cb   = editor.findChild(QCheckBox, '_use_win_cb')
            sp   = editor.findChild(QSpinBox, '_win_size_sp')
            use  = cb.isChecked() if cb else False
            size = sp.value() if sp else 5000
            model.setData(index, (use, size), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


def _is_cell_disabled(d, col):
    if col == COL_THRESHOLD:
        return d.get('method', '') != 'Manual'
    if col == COL_VALLEY:
        return d.get('split_method', '') != '1D Watershed'
    return False


# ==============================================================================
# View
# ==============================================================================
_DEFAULT_COL_WIDTHS = {
    0: 80, 1: 50, 2: 155, 3: 130, 4: 130, 5: 100,
    6: 130, 7: 90, 8: 140, 9: 130, 10: 140, 11: 100,
}


class ParametersTableView(QTableView):

    cellClicked = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model    = ParametersModel(self)
        self._delegate = ParametersDelegate(self)
        self.setModel(self._model)
        self.setItemDelegate(self._delegate)

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setMinimumSectionSize(70)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalHeader().setDefaultSectionSize(45)

        self.clicked.connect(
            lambda idx: self.cellClicked.emit(idx.row(), idx.column()))

    def populate(self, rows):
        self._model.populate(rows)
        for col, w in _DEFAULT_COL_WIDTHS.items():
            self.setColumnWidth(col, w)

    def get_row_params(self, row):
        return self._model.row_data(row)

    def set_row_field(self, row, field, value, emit_changed=False):
        self._model.set_field(row, field, value, emit_changed=emit_changed)

    def set_row_colors(self, row, bg=None, fg=None):
        self._model.set_row_colors(row, bg, fg)

    def rowCount(self):
        return self._model.rowCount()

    def columnCount(self):
        return self._model.columnCount()

    def currentRow(self):
        return self.currentIndex().row()

    def setCurrentCell(self, row, col):
        self.setCurrentIndex(self._model.index(row, col))

    def item(self, row, col):
        return _ItemProxy(self._model, row, col)

    def setRowCount(self, n):
        if n == 0:
            self._model.clear()

    def setColumnCount(self, n):
        pass

    def setHorizontalHeaderLabels(self, labels):
        pass

    def horizontalHeaderItem(self, col):
        return None

    def insertRow(self, row):
        pass

    def setItem(self, row, col, item):
        pass

    def setCellWidget(self, row, col, widget):
        pass

    def cellWidget(self, row, col):
        return _CellProxy(self._model, row, col)

    def setSelectionBehavior(self, behavior):
        super().setSelectionBehavior(behavior)

    def setEditTriggers(self, triggers):
        super().setEditTriggers(triggers)


# ==============================================================================
# Compatibility proxies
# ==============================================================================
class _ItemProxy:
    def __init__(self, model, row, col):
        self._m   = model
        self._row = row
        self._col = col

    def text(self):
        idx = self._m.index(self._row, self._col)
        return self._m.data(idx, Qt.DisplayRole) or ''

    def setBackground(self, brush):
        self._m.set_row_colors(self._row, bg=brush)

    def setForeground(self, brush):
        self._m.set_row_colors(self._row, fg=brush)

    def setFlags(self, flags):
        pass

    def __bool__(self):
        return 0 <= self._row < self._m.rowCount()


class _CellProxy:
    def __init__(self, model, row, col):
        self._m   = model
        self._row = row
        self._col = col

    def _d(self):
        return self._m.row_data(self._row)

    def isChecked(self):
        d = self._d()
        if self._col == COL_INCLUDE:
            return d.get('include', True)
        if self._col == COL_ITERATIVE:
            return d.get('iterative', True)
        return False

    def currentText(self):
        d = self._d()
        if self._col == COL_METHOD:
            return d.get('method', '')
        if self._col == COL_INTEG:
            return d.get('integration_method', '')
        if self._col == COL_SPLIT:
            return d.get('split_method', '')
        return ''

    def value(self):
        d = self._d()
        if self._col == COL_SIGMA:     return d.get('sigma', 0.55)
        if self._col == COL_THRESHOLD: return d.get('manual_threshold', 10.0)
        if self._col == COL_MIN_CONT:  return d.get('min_continuous', 1)
        if self._col == COL_ALPHA:     return d.get('alpha', 0.000001)
        if self._col == COL_VALLEY:    return d.get('valley_ratio', 0.50)
        return 0.0

    def setValue(self, v):
        field = {
            COL_SIGMA:     'sigma',
            COL_THRESHOLD: 'manual_threshold',
            COL_MIN_CONT:  'min_continuous',
            COL_ALPHA:     'alpha',
            COL_VALLEY:    'valley_ratio',
        }.get(self._col)
        if field:
            self._m.set_field(self._row, field, v, emit_changed=False)

    def blockSignals(self, block):
        pass

    def setEnabled(self, enabled):
        pass

    def setStyleSheet(self, qss):
        if self._col == COL_SIGMA:
            self._m.set_field(self._row, '_sigma_highlighted', bool(qss))

    def findChild(self, type_, name=''):
        if self._col == COL_WINDOW:
            is_cb = (type_ is QCheckBox
                     or getattr(type_, '__name__', '') in ('QCheckBox',))
            return _WindowChildProxy(self._m, self._row, is_checkbox=is_cb)
        return None

    def __bool__(self):
        return 0 <= self._row < self._m.rowCount()


class _WindowChildProxy:
    def __init__(self, model, row, *, is_checkbox):
        self._m           = model
        self._row         = row
        self._is_checkbox = is_checkbox

    def isChecked(self):
        return self._m.row_data(self._row).get('use_window_size', False)

    def value(self):
        return self._m.row_data(self._row).get('window_size', 5000)

    def setEnabled(self, enabled):
        pass

    def __bool__(self):
        return True
