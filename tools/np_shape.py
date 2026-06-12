"""Manages user defined nano particles shapes"""
from collections import namedtuple
from typing import Any

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QHBoxLayout, QPushButton, QStyledItemDelegate, \
    QDialog, QComboBox, QFormLayout, QTextEdit, QLineEdit
from PySide6.QtCore import QAbstractTableModel, QObject, Qt, QModelIndex, Signal, QAbstractItemModel


class NanoParticleShape:
    def __init__(self, formula=None):
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


class ShellNPS(NanoParticleShape):

    def __init__(self, formula=None):
        super().__init__(formula=formula)
        self.core = None
        self.shell = None

    def get_formula(self):
        return f"{str(self.core)}  + {self.shell}"

    def get_shape(self):
        return "Shell"


class ShpereNPS(NanoParticleShape):
    def get_shape(self):
        return "Shpere"

class RodNPS(NanoParticleShape):
    def get_shape(self):
        return "Rod"

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

    def get_shape(self, index: int) -> NanoParticleShape | None:
        """

        Args:
            index: Index of the shape in the list.

        Returns:
            the NanoParticleShape at the specified index or None if the
            index is invalid
        """
        if self.is_index_invalid(index):
            return None
        return self.nps_list[index]

    def is_index_invalid(self, index: int) -> bool:
        return index < 0 or index >= len(self.nps_list)

    def delete_shape(self, index: int):
        """
        Removes nano particule shape from the data
        Args:
            index: Index of the shape to remove
        """
        self.nps_list.pop(index)

    def update_shape(self, index: int, nps: NanoParticleShape):
        if not self.validate_shape(nps):
            print("Shape faild validations")  # TODO: raise an error
            return

        if index == len(self.nps_list):
            self.nps_list.append(nps)

        if self.is_index_invalid(index):
            print("Le changement n'a pas eu lieu")  # TODO: raise an error
            return
        self.nps_list[index] = nps


class NanoParticleShapeModel(QAbstractTableModel):
    """Model that manages particle shapes"""
    ColumnInfo = namedtuple('ColumnInfo', ['title'])

    def __init__(self, nps_service: NanoParticleShapeService, parent: QObject | Any = None):
        """

        Args:
            nps_service:
            parent:
        """
        super().__init__(parent=parent)
        self.nps_service = nps_service

        self.columns_info = [
            self.ColumnInfo("Formula"),
            self.ColumnInfo("Shape"),
        ]

    def rowCount(self, parent=None):
        return self.nps_service.shape_count()

    def columnCount(self, parent=None):
        return len(self.columns_info)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            shape = self.nps_service.get_shape(index.row())
            if shape is None:
                return ""

            match index.column():
                case 0:
                    return shape.get_formula()
                case 1:
                    return shape.get_shape()
                case column:
                    if column < len(self.columns_info):
                        raise NotImplementedError(f"There's no implementation for column # {column}")
                    return ""
        if role == Qt.ItemDataRole.EditRole:
            # returns the entire shape because the editor is a model.
            return self.nps_service.get_shape(index.row())
        return None

    def setData(self, index, value, /, role=Qt.ItemDataRole.EditRole):
        if role == Qt.ItemDataRole.EditRole:
            self.nps_service.update_shape(index.row(), value)

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

    def removeRows(self, position, row, parent=QModelIndex()):
        print("Remove row")
        self.beginRemoveRows(parent, position, position + row - 1)
        for i in range(row):
            self.nps_service.delete_shape(position)

        self.endRemoveRows()
        self.layoutChanged.emit()
        return True

    def addData(self, nps: NanoParticleShape):
        insert_index = self.rowCount()
        index = self.index(insert_index, 0)  # TODO: Is this okay?
        self.beginInsertRows(index, insert_index, insert_index + 1)

        print("Row inserted")
        self.nps_service.update_shape(insert_index, nps)

        self.endInsertRows()


class ShellNPSEditor(QWidget):
    def __init__(self, shell: ShellNPS, /):
        super().__init__()
        self.shell = shell
        self.core_edit = QLineEdit(str(shell.core or ""),
                                   placeholderText="Core")
        self.core_edit.textChanged.connect(self.set_core)
        self.shell_edit = QLineEdit(str(shell.shell or ""),
                                    placeholderText="Shell")
        self.shell_edit.textChanged.connect(self.set_shell)
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout()
        self.setLayout(layout)

        layout.addRow("Core", self.core_edit)
        layout.addRow("Shell", self.shell_edit)

    def set_core(self):
        self.shell.core = self.core_edit.text()

    def set_shell(self):
        self.shell.shell = self.shell_edit.text()

    def get_nps(self):
        # TODO: Raise en error if the nps is not valid
        return self.shell


class NPSEditor(QDialog):
    """The NPS Editor is the editor for a specific"""
    nps_changed = Signal(NanoParticleShape)

    def __init__(self, index: QModelIndex | None, model: QAbstractItemModel, parent: QWidget | Any):
        super().__init__(parent=parent)
        self.model = model
        self.index = index
        self.nps = (model.data(index, Qt.ItemDataRole.EditRole) if index is not None
                    else self.get_default_shape())  # TODO: Make this flexible for None NPS
        self.current_form_widget = None

        self.nps_changed.connect(self._setup_form)

        self._setup_ui()
        self._setup_form(self.nps)

    def _setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self._setup_header())

    def _setup_header(self):
        header = QWidget()
        header_layout = QHBoxLayout()
        header.setLayout(header_layout)

        self.nps_combo_box = QComboBox(parent=header)
        header_layout.addWidget(self.nps_combo_box)
        self.nps_combo_box.currentIndexChanged.connect(self.change_current_form_widget)

        for index, sub_class in enumerate(NanoParticleShape.__subclasses__()):
            if sub_class == type(self.nps):
                self.nps_combo_box.addItem(self.nps.get_shape(), self.nps)
                self.nps_combo_box.setCurrentIndex(index)
                continue
            sub_class_instance = sub_class()
            self.nps_combo_box.addItem(sub_class_instance.get_shape(), sub_class_instance)

        title = QLabel("Editor")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px 0;")  # TODO: make a common style
        header_layout.addWidget(title)

        return header

    def _setup_form(self, nps):
        layout = self.layout()

        if self.current_form_widget is not None:
            layout.removeWidget(self.current_form_widget)

        match nps:
            case ShellNPS():
                print("Form for ShellNPS")
                layout.addWidget(ShellNPSEditor(nps))
            case ShpereNPS():
                print("Form for RodNPS")
            case obj:
                raise NotImplementedError(f"No NPS class for the type : {obj.__class__}")

        if isinstance(nps, ShellNPS):
            pass


    @property
    def nps(self):
        return self._nps

    @nps.setter
    def nps(self, nps: NanoParticleShape):
        self._nps = nps
        self.nps_changed.emit(self._nps)

    def get_default_shape(self):
        return ShellNPS()  # TODO: Could we add parameters???

    def change_current_form_widget(self, index: int):
        nps = self.nps_combo_box.itemData(index)
        print(nps)


class QTableViewKeyEvents(QTableView):
    """QTableView that has basic direct model control"""
    DB_CLICK_DEBOUNCE_MS = 1000  # TODO: Trouver un autre nom
    on_double_left_click = Signal(QModelIndex)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def mouseDoubleClickEvent(self, event, /):
        """

        Args:
            event:
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_double_left_click.emit(self.currentIndex())

    def keyPressEvent(self, event, /):
        """

        Args:
            event:
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
    Widget that connects all the needed components and controls to manage Nano
    Particles (NP) shapes (NPS).
    """

    def __init__(self, parent: QWidget | Any,
                 nps_service: NanoParticleShapeService = NanoParticleShapeService(nps_list=[

                     ShpereNPS(formula="1O"),
                     ShellNPS(formula="2H"),
                     ShpereNPS(formula="3H"),
                     ShellNPS(formula="4H"),
                     ShellNPS(formula="5H"),
                     ShellNPS(formula="6H"),  # TODO: remove this atrocity
                 ]), /):
        super().__init__(parent=parent)
        self.nps_editor = None

        self.nps_table = QTableViewKeyEvents(parent=self)
        self.nps_model = NanoParticleShapeModel(nps_service=nps_service,
                                                parent=self.nps_table)  # TODO:  Move to __init__
        self.nps_table.setModel(self.nps_model)

        self._setup_ui()

    def _setup_ui(self):
        """
        Sets up the widget ui.
        """
        layout = QVBoxLayout()
        self.setLayout(layout)

        header = self._setup_header()
        layout.addWidget(header)
        layout.addWidget(self.nps_table)

        # TODO: Move btns to _setup_header
        show_model_btn = QPushButton("Remove selected shape(s)")
        header.layout().addWidget(show_model_btn)
        show_model_btn.clicked.connect(self.nps_table.remove_fully_selected_rows)

        new_shpae_btn = QPushButton("New Shape")
        header.layout().addWidget(new_shpae_btn)
        new_shpae_btn.clicked.connect(self.open_nps_editor_new)

        self.nps_table.on_double_left_click.connect(self.open_nps_editor_edit)

    def _setup_header(self):
        header = QWidget(self)
        layout = QHBoxLayout()
        header.setLayout(layout)

        title = QLabel("Nano Particule Shape")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px 0;")  # TODO: make a common style
        layout.addWidget(title)

        return header

    def open_nps_editor_edit(self, index: QModelIndex):
        self.nps_editor = self._create_and_open_nps_editor(index)
        self.nps_editor.accepted.connect(
            lambda nps: self.modify_nps(nps, index)
        )

    def modify_nps(self, nps: NanoParticleShape, index: QModelIndex):
        self.nps_model.setData(index, nps)

    def open_nps_editor_new(self):
        self.nps_editor = self._create_and_open_nps_editor()
        self.nps_editor.accepted.connect(self.new_nps)

    def new_nps(self, nps: NanoParticleShape):
        self.nps_model.addData(nps)

    def _create_and_open_nps_editor(self, index: QModelIndex | None = None):
        """
        Opens the NPS editor with the required model and parent.
        Args:
            index:
        """
        if not isinstance(index, QModelIndex):
            index = None

        nps_editor = NPSEditor(index, model=self.nps_model, parent=self)
        nps_editor.open()
        return nps_editor
