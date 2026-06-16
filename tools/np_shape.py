"""Manages user defined nano particles shapes"""
import copy
from collections import namedtuple
from typing import Any

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableView, QHBoxLayout, QPushButton, \
    QDialog, QComboBox, QFormLayout, QLineEdit, QAbstractItemView
from PySide6.QtCore import QAbstractTableModel, QObject, Qt, QModelIndex, Signal, QAbstractItemModel

from tools.theme import primary_button_qss, theme, results_title_qss


class NanoParticleShape:
    def __init__(self, name=None):
        self.name = name

    def get_name(self):
        """
        Returns:
            (str) string of the informal way of calling the nano particle shape.
        """
        return self.name

    def get_formula(self):
        """
        Returns:
            (str) string that represents the nano particle.
        """
        return "No formula"

    def get_shape(self):
        """
        Returns:
            (str) shape name.
        """
        return "No shape name"

    def __repr__(self):
        return f"<{self.__module__}.{self.__class__.__name__} formula={self.get_formula()}, shape={self.get_shape()}>"


class CoreShellNPS(NanoParticleShape):
    """

    """

    def __init__(self, name=None, core=None, shell=None):
        super().__init__(name=name)
        self.core: str | None = core
        self.shell: str | None = shell

    def get_formula(self):
        return f"{str(self.core)}  + {self.shell}"

    def get_shape(self):
        return "Core-Shell"


class SphereNPS(NanoParticleShape):
    def __init__(self, formula=None, name=None):
        super().__init__(name=name)
        self.formula: str | None = formula

    def get_formula(self):
        return self.formula

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
        return copy.deepcopy(self.nps_list[index])

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
    """Adaptor between views and `NanoParticleShapeService`."""
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
            self.ColumnInfo("Name"),
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
        if role == Qt.ItemDataRole.EditRole:  # TODO: stop using that
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
        index = self.index(insert_index, 0)
        self.beginInsertRows(index, insert_index, insert_index)

        print("Row inserted")
        self.nps_service.update_shape(insert_index, nps)

        self.endInsertRows()


class SphereNPSEditor(QWidget):
    def __init__(self, sphere: SphereNPS):
        super().__init__()
        self.sphere = sphere
        self.formula_edit = QLineEdit(str(self.sphere.formula) if self.sphere.formula
                                      else "",
                                      placeholderText="Formula")
        self.formula_edit.textChanged.connect(self.set_formula)

        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout()
        self.setLayout(layout)
        layout.addRow("Formula", self.formula_edit)

    def set_formula(self):
        self.sphere.formula = self.formula_edit.text()


class CoreShellNPSEditor(QWidget):
    def __init__(self, core_shell: CoreShellNPS, /):
        super().__init__()
        self.core_shell = core_shell
        self.core_edit = QLineEdit(str(core_shell.core or ""),
                                   placeholderText="Core")
        self.core_edit.textChanged.connect(self.set_core)
        self.shell_edit = QLineEdit(str(core_shell.shell or ""),
                                    placeholderText="Shell")
        self.shell_edit.textChanged.connect(self.set_shell)
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout()
        self.setLayout(layout)

        layout.addRow("Core", self.core_edit)
        layout.addRow("Shell", self.shell_edit)

    def set_core(self):
        self.core_shell.core = self.core_edit.text()

    def set_shell(self):
        self.core_shell.shell = self.shell_edit.text()

    def get_nps(self):
        # TODO: Raise en error if the nps is not valid
        return self.core_shell


class NPSEditor(QDialog):
    """The NPS Editor is the editor for a specific"""
    accept_with_nps = Signal(NanoParticleShape)

    def __init__(self, index: QModelIndex | None, model: QAbstractItemModel, parent: QWidget | Any):
        super().__init__(parent=parent)
        self.model = model
        self.index = index
        self.nps = (model.data(index, Qt.ItemDataRole.EditRole) if index is not None
                    else self.get_default_shape())  # TODO: Make this flexible for None NPS
        self.nps_name = self.nps.get_name() or ""
        self.nps_name_edit = QLineEdit(str(self.nps_name),
                                       placeholderText="Name")

        self.current_form_widget = None

        self.nps_form_layout_index = 0

        self.accept_with_nps.connect(self.accept)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self._build_header())
        layout.addWidget(self._build_name_form())
        self.nps_form_layout_index = layout.count()
        self.display_form_for_nps(self.nps)
        layout.addStretch(1)
        layout.addWidget(self._build_footer())

    def _build_header(self):
        header = QWidget(parent=self)
        header_layout = QHBoxLayout()
        header.setLayout(header_layout)

        # Setting up the dropdown with all NanoParticleShape available
        self.nps_combo_box = QComboBox(header)

        current_nps_index = -1

        for index, sub_class in enumerate(NanoParticleShape.__subclasses__()):
            if sub_class == type(self.nps):
                # Uses the pre-existing nps to get user's entries
                self.nps_combo_box.addItem(self.nps.get_shape(), userData=self.nps)
                current_nps_index = index
                continue
            sub_class_instance = sub_class()
            self.nps_combo_box.addItem(sub_class_instance.get_shape(), sub_class_instance)

        self.nps_combo_box.setCurrentIndex(current_nps_index)
        self.nps_combo_box.currentIndexChanged.connect(self.handle_nps_selection_change)

        title = QLabel("Editor")
        title.setStyleSheet(results_title_qss(theme.palette))  # TODO: make a common style
        header_layout.addWidget(title)
        header_layout.addWidget(self.nps_combo_box)

        return header

    def emit_accept_with_nps(self):
        """
        Makes final preparation before emitting `accept_with_nps`.
        """
        self.nps.name = self.nps_name_edit.text()
        self.accept_with_nps.emit(self.nps)

    def display_form_for_nps(self, nps: NanoParticleShape):
        """
        Display the form with the right fields for the parameter's
        `NanoParticleShape` variation.

        Args:
            nps (NanoParticleShape): `NanoParticleShape` to be displayed.
        """
        layout = self.layout()

        # TODO: Find a smoother alternative
        assert isinstance(layout, QVBoxLayout)

        if isinstance(self.current_form_widget, QWidget):
            print("Widget removed")
            layout.removeWidget(self.current_form_widget)
            self.current_form_widget.hide()
            self.current_form_widget.deleteLater()
            self.current_form_widget = None

        match nps:
            case CoreShellNPS():
                print("Form for CoreShellNPS")
                self.current_form_widget = CoreShellNPSEditor(nps)
                layout.insertWidget(self.nps_form_layout_index, self.current_form_widget)
            case SphereNPS():
                print("Form for ShperesNPS")
                self.current_form_widget = SphereNPSEditor(nps)
                layout.insertWidget(self.nps_form_layout_index, self.current_form_widget)
            case obj:
                raise NotImplementedError(f"No NPS class for the type : {obj.__class__}")

    @staticmethod
    def get_default_shape():
        """Defines a default `NanoParticleShape` to display."""
        return CoreShellNPS()  # TODO: Could we add a setting for that

    def handle_nps_selection_change(self, index: int):
        """
        Handles a user changing nps selection by displaying the new form.

        Args:
            index: index of the item in the `self.nps_combo_box`.
        """
        self.nps = self.nps_combo_box.itemData(index)
        self.display_form_for_nps(self.nps)

    def _build_name_form(self):
        widget = QWidget(parent=self)
        layout = QFormLayout()
        widget.setLayout(layout)
        layout.addRow("Name", self.nps_name_edit)
        return widget

    def _build_footer(self):
        widget = QWidget()
        layout = QHBoxLayout()
        widget.setLayout(layout)

        accept_btn = QPushButton("Apply")
        accept_btn.setStyleSheet(primary_button_qss(theme.palette))
        accept_btn.clicked.connect(self.emit_accept_with_nps)
        layout.addWidget(accept_btn)

        reject_btn = QPushButton("Cancel")
        reject_btn.clicked.connect(self.close)
        layout.addWidget(reject_btn)
        return widget


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
                 nps_service: NanoParticleShapeService = NanoParticleShapeService(nps_list=[

                     SphereNPS(name="That", formula="1O"),
                     CoreShellNPS(name="2H", core="Ti", shell="Fe"),
                     SphereNPS(name="This", formula="3H"),
                     CoreShellNPS(name="4H", core="Ti", shell="Fe"),
                     CoreShellNPS(name="5H", core="Ti", shell="Fe"),
                     CoreShellNPS(name="6H", core="Ti", shell="Fe"),  # TODO: remove this atrocity
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

        layout.addWidget(self._setup_header())
        layout.addWidget(self.nps_table)

        self.nps_table.on_edit.connect(self.open_nps_editor_with_index)

    def _setup_header(self):
        header = QWidget(self)
        layout = QHBoxLayout()
        header.setLayout(layout)

        title = QLabel("Nano Particule Shape")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px 0;")  # TODO: make a common style
        layout.addWidget(title)

        show_model_btn = QPushButton("Remove selected shape(s)")
        header.layout().addWidget(show_model_btn)
        show_model_btn.clicked.connect(self.nps_table.remove_fully_selected_rows)

        new_shape_btn = QPushButton("New Shape")
        header.layout().addWidget(new_shape_btn)
        new_shape_btn.clicked.connect(self.open_nps_editor)

        return header

    def open_nps_editor_with_index(self, index: QModelIndex):
        print("Editor edit")
        print(index)
        self.nps_editor = self._create_and_open_nps_editor(index)
        self.nps_editor.accept_with_nps.connect(
            lambda nps: self.handle_modify_nps(nps, index)
        )

    def handle_modify_nps(self, nps: NanoParticleShape, index: QModelIndex):
        print("Modify nps")
        self.nps_model.setData(index, nps)
        self.nps_editor = None

    def open_nps_editor(self):
        self.nps_editor = self._create_and_open_nps_editor()
        self.nps_editor.accept_with_nps.connect(self.handle_new_nps)

    def handle_new_nps(self, nps: NanoParticleShape):
        print("New nps")
        self.nps_model.addData(nps)
        self.nps_editor = None

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
