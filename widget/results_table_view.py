"""Fast model/view table for the Single Element and Multi-Element results.

``QTableWidget`` creates one item object per cell, so refilling a table with
thousands of particles and dozens of element columns is slow. This view keeps
the rows as plain Python values in a ``QAbstractTableModel`` and only formats
the cells Qt actually paints, the same approach as the detection parameters
table.
"""

import math

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView


def _format(value, fmt):
    """Return the display text for one cell.

    Args:
        value: Raw cell value.
        fmt (str | None): ``format`` spec such as ``".4f"``; None uses ``str``.

    Returns:
        str: Text shown in the cell.
    """
    if value is None:
        return ""
    if fmt and isinstance(value, (int, float)):
        try:
            return format(value, fmt)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def _sort_key(value):
    """Sort numbers numerically, then text alphabetically, blanks last."""
    if isinstance(value, bool):
        return (0, float(value), "")
    if isinstance(value, (int, float)):
        v = float(value)
        return (0, v if not math.isnan(v) else math.inf, "")
    if value is None or value == "":
        return (2, 0.0, "")
    number = _as_number(value)
    if number is not None:
        return (0, number, "")
    return (1, 0.0, str(value).lower())


def _as_number(value):
    """Read a cell as a number, allowing thousands separators and a percent sign."""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


class ResultsTableModel(QAbstractTableModel):
    """Rows of raw values with per-column display formats."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = []
        self._formats = []
        self._rows = []
        self._row_brush = None
        self._align_numbers = False
        self._tooltips = False

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            row = self._rows[index.row()]
            col = index.column()
            value = row[col] if col < len(row) else None
            fmt = self._formats[col] if col < len(self._formats) else None
            return _format(value, fmt)
        if role == Qt.ItemDataRole.UserRole:
            row = self._rows[index.row()]
            return row[index.column()] if index.column() < len(row) else None
        if role == Qt.ItemDataRole.BackgroundRole and self._row_brush is not None:
            return self._row_brush(self._rows[index.row()])
        if role == Qt.ItemDataRole.TextAlignmentRole and self._align_numbers:
            row = self._rows[index.row()]
            value = row[index.column()] if index.column() < len(row) else None
            if value not in (None, "") and _as_number(value) is not None:
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return None
        if role == Qt.ItemDataRole.ToolTipRole and self._tooltips:
            return self.data(index, Qt.ItemDataRole.DisplayRole)
        return None

    def set_display_options(self, align_numbers=False, tooltips=False):
        """Right-align numeric cells and/or show each cell's text as its tooltip."""
        self._align_numbers = bool(align_numbers)
        self._tooltips = bool(tooltips)

    def set_row_brush(self, func):
        """Set a callable ``row -> QBrush | None`` that tints whole rows.

        Args:
            func (callable | None): Receives the raw row values; None removes tinting.
        """
        self._row_brush = func
        if self._rows:
            self.dataChanged.emit(self.index(0, 0),
                                  self.index(len(self._rows) - 1, max(0, len(self._headers) - 1)),
                                  [Qt.ItemDataRole.BackgroundRole])

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._headers[section] if section < len(self._headers) else None
        return str(section + 1)

    def set_table(self, headers, rows, formats=None):
        """Replace the whole table in one reset.

        Args:
            headers (list[str]): Column titles.
            rows (list[list]): Raw values, one list per row.
            formats (list[str | None] | None): Display format per column.
        """
        self.beginResetModel()
        self._headers = list(headers)
        self._formats = list(formats) if formats else [None] * len(self._headers)
        self._rows = [list(r) for r in rows]
        self.endResetModel()

    def clear_rows(self):
        """Remove every row but keep the columns."""
        self.beginResetModel()
        self._rows = []
        self.endResetModel()

    def raw(self, row, col):
        """Return the raw value of a cell, or None when out of range."""
        if 0 <= row < len(self._rows) and 0 <= col < len(self._rows[row]):
            return self._rows[row][col]
        return None

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        """Sort the rows by one column, keeping selections on the same rows."""
        if not (0 <= column < len(self._headers)) or not self._rows:
            return
        self.layoutAboutToBeChanged.emit()
        old_persistent = self.persistentIndexList()
        old_rows = [idx.row() for idx in old_persistent]
        reverse = order == Qt.SortOrder.DescendingOrder
        order_idx = sorted(range(len(self._rows)),
                           key=lambda i: _sort_key(self._rows[i][column]
                                                   if column < len(self._rows[i]) else None),
                           reverse=reverse)
        self._rows = [self._rows[i] for i in order_idx]
        new_pos = {old: new for new, old in enumerate(order_idx)}
        self.changePersistentIndexList(
            old_persistent,
            [self.index(new_pos.get(r, r), idx.column()) for r, idx in zip(old_rows, old_persistent)])
        self.layoutChanged.emit()


class ResultsTableView(QTableView):
    """Read-only, sortable results table backed by :class:`ResultsTableModel`."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = ResultsTableModel(self)
        self.setModel(self._model)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self.horizontalHeader().setResizeContentsPrecision(200)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.verticalHeader().setDefaultSectionSize(26)

    def set_table(self, headers, rows, formats=None):
        """Fill the table, keeping the current sort column and selected row numbers.

        Args:
            headers (list[str]): Column titles.
            rows (list[list]): Raw values, one list per row.
            formats (list[str | None] | None): Display format per column.
        """
        selected = sorted({i.row() for i in self.selectionModel().selectedRows()})
        header = self.horizontalHeader()
        sort_col = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        self._model.set_table(headers, rows, formats)
        if 0 <= sort_col < len(headers):
            self._model.sort(sort_col, sort_order)
        for r in selected:
            if r < self._model.rowCount():
                self.selectRow(r)

    def clear_rows(self):
        """Remove every row but keep the columns."""
        self._model.clear_rows()

    def set_row_brush(self, func):
        """Tint whole rows; see :meth:`ResultsTableModel.set_row_brush`."""
        self._model.set_row_brush(func)

    def set_display_options(self, align_numbers=False, tooltips=False):
        """See :meth:`ResultsTableModel.set_display_options`."""
        self._model.set_display_options(align_numbers, tooltips)

    def rowCount(self):
        """Number of rows currently shown."""
        return self._model.rowCount()

    def columnCount(self):
        """Number of columns currently shown."""
        return self._model.columnCount()

    def header_text(self, col):
        """Return the title of column ``col``."""
        return self._model.headerData(col, Qt.Orientation.Horizontal) or ""

    def cell_text(self, row, col):
        """Return the displayed text of a cell."""
        return self._model.data(self._model.index(row, col)) or ""

    def cell_value(self, row, col):
        """Return the raw value of a cell."""
        return self._model.raw(row, col)

    def selected_row(self):
        """Return the first selected row, or None."""
        rows = self.selectionModel().selectedRows()
        if not rows:
            rows = self.selectionModel().selectedIndexes()
        return rows[0].row() if rows else None
