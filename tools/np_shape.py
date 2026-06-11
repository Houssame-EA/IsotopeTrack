"""Manages user defined nano particles shapes"""
from collections import namedtuple
from typing import Any

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QHBoxLayout, QPushButton, QStyledItemDelegate, \
    QDialog, QComboBox, QMenu
from PySide6.QtCore import QAbstractTableModel, QObject, Qt, QModelIndex, QPersistentModelIndex, QPoint


class NanoParticleShape():
    def __init__(self, formula):
        self.formula = formula

    def get_formula(self):
        """

        Returns:
            (str) string that represents the nano particle
        """
        return self.formula

    def get_shape(self):
        """
        Returns:
            (str) shape name
        """
        return "No shape name"

    def __repr__(self):
        return f"<{self.__module__}.{self.__class__.__name__} formula={self.get_formula()}, shape={self.get_shape()}>"


class NanoParticleShapeService:
    """
    This class manages the Nano Particle Shapes (NPS at an app level).

    This means that all app NPS related actions will pass by this class.
    It should be provided by dependency injection when needed. In the current
    architecture. The MainWindow will be the owner of that dependency and will
    be the one providing it.
    """

    def __init__(self, nps_list: list[NanoParticleShape] | None = None):
        if nps_list is None:
            nps_list = []
        self.nps_list = nps_list

    @staticmethod
    def validate_shape(shape: NanoParticleShape):
        """
        Validate a shape's properties to make sure that they don't violate
        nps_list.
        Args:
            shape: shape to validate

        Returns:

        Raises:

        """
        return isinstance(shape, NanoParticleShape)

    def shape_count(self):
        """

        Returns:
            (int) amount of nano particle shape stored in the service.
        """
        return len(self.nps_list)

    def get_shape(self, index: int) -> NanoParticleShape:
        """

        Args:
            index: Index of the shape in the list.

        Returns:
            the NanoParticleShape at the specified index.
        """
        return self.nps_list[index]

    def delete_shape(self, index: int):
        """
        Removes nano particule shape from the data
        Args:
            index: Index of the shape to remove
        """
        self.nps_list.pop(index)


class NanoParticleShapeModel(QAbstractTableModel):
    """Model that manages particle shapes"""
    ColumnInfo = namedtuple('ColumnInfo', ['title', 'display_fn'])

    def __init__(self, nps_service: NanoParticleShapeService, parent: QObject | Any = None):
        """

        Args:
            nps_service:
            parent:
        """
        super().__init__(parent=parent)
        self.nps_service = nps_service

        self.columns_info = [
            self.ColumnInfo("Formula", NanoParticleShape.get_formula),
            self.ColumnInfo("Shape", NanoParticleShape.get_shape),
        ]

    def rowCount(self, parent=None):
        return self.nps_service.shape_count()

    def columnCount(self, parent=None):
        return len(self.columns_info)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            nano_particle_shape = self.nps_service.get_shape(index.row())
            fn = self.columns_info[index.column()].display_fn  # TODO: make sure that the column is valid
            return fn(nano_particle_shape)
        if role == Qt.ItemDataRole.EditRole:
            # returns the entire shape because the editor is a model.
            return self.nps_service.get_shape(index.row())
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return self.columns_info[section].title
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == 0:  # TODO: Find a new way to reference the col_index
            return base
        return Qt.ItemFlag.ItemIsEditable | base

    def removeRows(self, position,  row, parent=QModelIndex()):
        print("Remove row")
        self.beginRemoveRows(parent, position, position + row - 1)
        for i in range(row):
            self.nps_service.delete_shape(position)

        self.endRemoveRows()
        self.layoutChanged.emit()
        return True


class NPSDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def createEditor(self, parent, option, index):
        editor = QDialog(parent, Qt.WindowType.Window)
        editor.open()
        editor.move(QPoint(100, 100))
        layout = QVBoxLayout(editor)
        editor.setLayout(layout)
        np_shape: NanoParticleShape = index.data(Qt.ItemDataRole.EditRole)
        layout.addWidget(QLabel(np_shape.get_formula()))
        layout.addWidget(QLabel(np_shape.get_shape()))

        return editor

    def setModelData(self, editor, model, index):
        print(editor)
        super().setModelData(editor, model, index)


class QTableViewKeyEvents(QTableView):
    """QTableView has generic keyboard control that directly affects the model underneath"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def keyPressEvent(self, event, /):
        """

        Args:
            event:

        Returns:

        """

        if event.key() == Qt.Key.Key_Delete:
            self.remove_fully_selected_rows()

    def remove_fully_selected_rows(self):
        """
        Removes all rows that are fully selected by the user.
        """
        # Find the amount of selections by rows
        rows_and_selection_count = {}
        for index in self.selectedIndexes():
            row = index.row()
            rows_and_selection_count[row] = rows_and_selection_count.get(row, 0) + 1

        # Get the rows that are fully selected
        fully_selected_rows = [row for row, count in rows_and_selection_count.items()
                               if count >= self.model().columnCount()]

        # Deletion of the rows
        fully_selected_rows.sort(reverse=True)
        for row in fully_selected_rows:
            self.model().removeRow(row)


class NanoParticleShapeWidget(QWidget):
    """
    Widget that manages Nano Particles (NP) shapes
    """

    def __init__(self, parent: QWidget | Any, /):
        super().__init__(parent=parent)
        self._setup_ui()

    def _setup_ui(self):
        """
        Sets up the widget ui.
        Returns:

        """
        layout = QVBoxLayout()
        self.setLayout(layout)

        header = self._setup_header()
        layout.addWidget(header)

        self.table = QTableViewKeyEvents(parent=self)
        np_list = [
            NanoParticleShape("1O"),
            NanoParticleShape("2H"),
            NanoParticleShape("3H"),
            NanoParticleShape("4O"),
            NanoParticleShape("5H"),
        ]
        self.nps_model = NanoParticleShapeModel(
            NanoParticleShapeService(nps_list=np_list),
            parent=self.table)
        self.table.setModel(self.nps_model)

        self.table.setItemDelegate(NPSDelegate(parent=self.table))

        layout.addWidget(self.table)

        show_model_btn = QPushButton("Remove selected row(s)")
        show_model_btn.clicked.connect(self.table.remove_fully_selected_rows)
        header.layout().addWidget(show_model_btn)

    def _setup_header(self):
        header = QWidget(self)
        layout = QHBoxLayout()
        header.setLayout(layout)

        title = QLabel("Nano Particule Shape")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px 0;")  # TODO: make a common style
        layout.addWidget(title)

        return header
