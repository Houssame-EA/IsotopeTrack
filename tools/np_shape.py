"""Manages user defined nanoparticles shapes"""
from collections import namedtuple
from typing import Any

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QHBoxLayout, QPushButton, \
    QAbstractItemView, QCompleter, QLineEdit
from PySide6.QtCore import QAbstractTableModel, QObject, Qt, QModelIndex, Signal, QSortFilterProxyModel

from tools.logging_utils import logging_manager
from tools.mass_fraction_calculator_utils.compound_database import CSVCompoundDatabase
from tools.nanoparticle_shape.database_adapter import CompoundDatabaseModel, CompoundService, DirectQCompleter
from tools.nanoparticle_shape.nanoparticle_shapes import NanoParticleShape, CoreShellNPS, SphereNPS
from tools.nanoparticle_shape.nps_editor import NPSEditor
from tools.nanoparticle_shape.nps_service import NanoParticleShapeService
from utils.validation import ValidationErrorException


class NanoParticleShapeModel(QAbstractTableModel):
    """Adaptor between views and `NanoParticleShapeService`."""
    ColumnInfo = namedtuple('ColumnInfo', ['title'])

    def __init__(self, nps_service: NanoParticleShapeService, parent: QObject | Any = None):
        super().__init__(parent=parent)
        self.nps_service = nps_service

        self.columns_info = [
            self.ColumnInfo("Name"),
            self.ColumnInfo("Formula"),
            self.ColumnInfo("Shape"),
        ]
        self.logger = logging_manager.get_logger(self.__class__.__name__)

    def rowCount(self, parent=None):
        return self.nps_service.shape_count()

    def columnCount(self, parent=None):
        return len(self.columns_info)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            shape = self.nps_service.get_shape(index.row())
            if shape is None:
                return ""

            match index.column():  # TODO: Reduce hard coding
                case 0:
                    return shape.get_name()
                case 1:
                    return shape.get_formula()
                case 2:
                    return shape.get_shape()
                case column:
                    if column < len(self.columns_info):
                        raise NotImplementedError(f"There's no implementation for column # {column}")
                    return ""
        if role == Qt.ItemDataRole.EditRole:
            # returns the entire shape because the editor is a model.
            self.logger.info(f"data(..., role=Qt.ItemDataRole.EditRole): "
                             f"Getting the shape from the service")
            return self.nps_service.get_shape(index.row())
        return None

    def setData(self, index, value, /, role=Qt.ItemDataRole.EditRole):
        if role == Qt.ItemDataRole.EditRole:
            self.logger.info("setData: Setting data with the service")
            try:
                self.nps_service.update_shape(index.row(), value)
            except ValidationErrorException as err:
                self.logger.exception(err)
            except IndexError as err:
                self.logger.exception(err)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                return self.columns_info[section].title
        return None

    def removeRows(self, position, row, parent=QModelIndex()):
        self.logger.info("removeRows: Removing rows with the service")
        self.beginRemoveRows(parent, position, position + row - 1)
        for i in range(row):
            self.nps_service.delete_shape(position)  # TODO: Manage exceptions

        self.endRemoveRows()
        self.layoutChanged.emit()
        return True

    def addData(self, nps: NanoParticleShape):
        self.logger.info("addData: adding data from the model")
        insert_index = self.rowCount()
        index = self.index(insert_index, 0)
        self.beginInsertRows(index, insert_index, insert_index)

        try:
            self.nps_service.update_shape(insert_index, nps)
        except ValidationErrorException as err:
            self.logger.exception(err)
        except IndexError as err:
            self.logger.exception(err)

        self.endInsertRows()


class QTableViewKeyEvents(QTableView):
    """QTableView that has basic direct model control"""
    on_edit = Signal(QModelIndex)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def mouseDoubleClickEvent(self, event, /):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_edit.emit(self.currentIndex())

    def keyPressEvent(self, event, /):

        if event.key() == Qt.Key.Key_Delete:
            self.remove_fully_selected_rows()
        if event.key() in [Qt.Key.Key_Enter, Qt.Key.Key_Return]:
            self.on_edit.emit(self.currentIndex())

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
    Widget that connects all the needed components and controls to manage Nano
    Particles (NP) shapes (NPS).
    """

    def __init__(self, parent: QWidget | Any,
                 nps_service: NanoParticleShapeService,
                 csv_database: CSVCompoundDatabase,
                 tracked_elements: list[str],/):
        super().__init__(parent=parent)
        self.logger = logging_manager.get_logger(self.__class__.__name__)
        self.nps_editor = None

        self.csv_database = csv_database
        self.tracked_elements = tracked_elements

        self.nps_table = QTableViewKeyEvents(parent=self)
        self.nps_model = NanoParticleShapeModel(nps_service=nps_service,
                                                parent=self.nps_table)
        self.nps_table.setModel(self.nps_model)

        self._setup_ui()

    def _setup_ui(self):
        """
        Sets up the widget ui.
        """
        self.logger.info("Setting up UI")
        layout = QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(self._setup_header())
        layout.addWidget(self.nps_table)

        # TODO: remove this example
        line_edit_test = QLineEdit(parent=self)

        model = CompoundDatabaseModel(CompoundService(self.csv_database, self.tracked_elements))
        completer = DirectQCompleter()
        completer.setModel(model)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchFixedString)

        line_edit_test.setCompleter(completer)
        line_edit_test.textEdited.connect(model.search)




        layout.addWidget(line_edit_test)

        self.nps_table.on_edit.connect(self.open_nps_editor_for_modification)

    def _setup_header(self):
        header = QWidget(self)
        layout = QHBoxLayout()
        header.setLayout(layout)

        title = QLabel("NanoParticle Shape")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px 0;")  # TODO: make a common style
        layout.addWidget(title)

        show_model_btn = QPushButton("Remove selected shape(s)")
        header.layout().addWidget(show_model_btn)
        show_model_btn.clicked.connect(self.nps_table.remove_fully_selected_rows)

        new_shape_btn = QPushButton("New Shape")
        header.layout().addWidget(new_shape_btn)
        new_shape_btn.clicked.connect(self.open_nps_editor_for_new)

        return header

    def open_nps_editor_for_modification(self, index: QModelIndex):
        """
        Opens the nps editor at a certain index of the model (using `QTableView`).
        Args:
            index: index of the nps in the model
        """
        self.logger.info("Opening NPS editor")
        self.nps_editor = self._create_and_open_nps_editor(index)
        self.nps_editor.accept_with_nps.connect(
            lambda nps: self.handle_modify_nps(nps, index)
        )

    def handle_modify_nps(self, nps: NanoParticleShape, index: QModelIndex):
        """
        Calls the model to set the `nps` of a specific `index.
        Args:
            nps: `NanoParticleShape` that will take the place of the one at
                `index` in the model.
            index: index of the `nps` to switch.
        """
        self.nps_model.setData(index, nps)
        self.nps_editor = None

    def open_nps_editor_for_new(self):
        """ Opens the nps editor with the goal of creating a new NPS. """
        self.nps_editor = self._create_and_open_nps_editor()
        self.nps_editor.accept_with_nps.connect(self.handle_new_nps)

    def handle_new_nps(self, nps: NanoParticleShape):
        """
        Calls the model to add a new nps.
        Args:
            nps: new nps to be added
        """
        self.nps_model.addData(nps)
        self.nps_editor = None

    def _create_and_open_nps_editor(self, index: QModelIndex | None = None):
        """
        Opens the NPS editor with the required information.
        Args:
            index: index of the data in the model if nps already exists.
        """
        if not isinstance(index, QModelIndex):
            index = None

        nps_editor = NPSEditor(index, model=self.nps_model, parent=self)
        nps_editor.open()
        return nps_editor
