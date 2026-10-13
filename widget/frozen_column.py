"""Keep the first columns of a table in place while it scrolls sideways."""
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView


class FrozenColumns(QTableView):
    """
    An overlay that keeps the first *count* columns of a table visible.

    It is a second view of the same model and selection model, drawn over
    the left edge of the table and showing only the frozen columns, so
    editing, selection, copy/paste, the context menu and cell clicks act on
    the table exactly as before. Column widths, row heights and vertical
    scrolling follow the table.

    Args:
        table: The QTableView or QTableWidget to freeze columns of.
        count: Number of leading columns to keep in place.
    """

    def __init__(self, table, count=1):
        super().__init__(table)
        self._table = table
        self._count = count
        self.setObjectName("frozenColumn")
        self.setModel(table.model())
        self.setSelectionModel(table.selectionModel())
        self.setSelectionMode(table.selectionMode())
        self.setSelectionBehavior(table.selectionBehavior())
        self.setEditTriggers(table.editTriggers())
        self.setAlternatingRowColors(table.alternatingRowColors())
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.verticalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(table.verticalScrollMode())
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.viewport().stackUnder(self)

        for col in range(count):
            delegate = table.itemDelegateForColumn(col)
            if delegate is not None:
                self.setItemDelegateForColumn(col, delegate)

        if table.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu:
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self._forward_context_menu)
        self.clicked.connect(self._forward_click)

        table.horizontalHeader().sectionResized.connect(self._on_column_resized)
        table.verticalHeader().sectionResized.connect(self._on_row_resized)
        self.verticalScrollBar().valueChanged.connect(table.verticalScrollBar().setValue)
        table.verticalScrollBar().valueChanged.connect(self.verticalScrollBar().setValue)

        model = table.model()
        for signal in (model.columnsInserted, model.columnsRemoved, model.modelReset,
                       model.rowsInserted, model.rowsRemoved, model.layoutChanged):
            signal.connect(self._sync)
        self._filter = _ResizeWatcher(self._update_geometry)
        table.installEventFilter(self._filter)
        table.verticalHeader().installEventFilter(self._filter)
        self._sync()
        self.show()

    def _sync(self, *_):
        """Show only the frozen columns, at the table's widths and heights."""
        try:
            self._sync_now()
        except RuntimeError:
            pass

    def _sync_now(self):
        model = self.model()
        for col in range(model.columnCount()):
            self.setColumnHidden(col, col >= self._count)
            if col < self._count:
                self.setColumnWidth(col, self._table.columnWidth(col))
        for row in range(model.rowCount()):
            self.setRowHeight(row, self._table.rowHeight(row))
        self._update_geometry()

    def _on_column_resized(self, column, _old, new):
        if column < self._count:
            self.setColumnWidth(column, new)
            self._update_geometry()

    def _on_row_resized(self, row, _old, new):
        self.setRowHeight(row, new)

    def _update_geometry(self):
        """Place the overlay over the frozen columns of the table."""
        try:
            self._place()
        except RuntimeError:
            pass

    def _place(self):
        table = self._table
        frame = table.frameWidth()
        header = table.verticalHeader()
        left = (header.width() if header.isVisible() else 0) + frame
        width = sum(table.columnWidth(c) for c in range(min(self._count, table.model().columnCount())))
        height = table.viewport().height() + table.horizontalHeader().height()
        self.horizontalHeader().setFixedHeight(table.horizontalHeader().height())
        self.setGeometry(left, frame, width + self.frameWidth() * 2, height)
        self.verticalScrollBar().setValue(table.verticalScrollBar().value())

    def _forward_click(self, index):
        """Report clicks as clicks on the table, and give it the keyboard."""
        self._table.setFocus()
        cell_clicked = getattr(self._table, "cellClicked", None)
        if cell_clicked is not None:
            cell_clicked.emit(index.row(), index.column())
        else:
            self._table.clicked.emit(index)

    def _forward_context_menu(self, pos):
        """Open the table's own context menu at the same place."""
        self._table.setFocus()
        target = self._table.viewport().mapFromGlobal(self.viewport().mapToGlobal(pos))
        self._table.customContextMenuRequested.emit(target)


class _ResizeWatcher(QObject):
    """Calls *callback* whenever a watched widget is resized or shown."""

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest):
            self._callback()
        return False
