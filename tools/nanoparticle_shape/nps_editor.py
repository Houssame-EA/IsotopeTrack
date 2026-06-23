"""Defines the editor ui"""
from typing import Any, Optional

from PySide6.QtCore import Signal, QModelIndex, QAbstractItemModel, Qt
from PySide6.QtWidgets import QWidget, QLineEdit, QFormLayout, QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, \
    QPushButton, QMessageBox, QSizePolicy, QGridLayout, QCompleter

from tools.logging_utils import logging_manager
from tools.nanoparticle_shape.database_adapter import CompoundDatabaseModel, DirectQCompleter, CompoundService
from tools.nanoparticle_shape.nanoparticle_shapes import SphereNPS, CoreShellNPS, NanoParticleShape, Compound
from tools.theme import results_title_qss, theme, primary_button_qss
from utils.validation import ValidationInfos

class IGetComponent:
    def get_component(self) -> tuple[Any, ValidationInfos]:
        pass

class CompoundEditor(QWidget, IGetComponent):
    def __init__(self, name: str, compound: Compound, compound_model: CompoundDatabaseModel | CompoundService, parent):
        """Note: The database should be unique to the Compound Editor"""
        super().__init__(parent=parent)

        self.name = name
        self.compound = compound

        self.row_label = QLabel(self.name)
        self.formula_editor = QLineEdit(text=compound.formula,
                                        parent=parent)
        self.density_editor = QLineEdit(text=str(compound.density),
                                        parent=parent)
        if isinstance(compound_model, CompoundService):
            compound_model = compound_model.get_searchable_model()
        self.compound_model = compound_model
        self._setup_completion()

        self._setup_ui()

    def _setup_completion(self):
        formula_completion = DirectQCompleter()
        formula_completion.setModel(self.compound_model)
        formula_completion.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        formula_completion.setFilterMode(Qt.MatchFlag.MatchFixedString)
        self.formula_editor.setCompleter(formula_completion)
        self.formula_editor.textEdited.connect(self.compound_model.search)

        formula_completion.activated[QModelIndex].connect(self.handle_selected_formula)

        density_completion = DirectQCompleter()
        density_completion.setModel(self.compound_model)
        density_completion.setCompletionRole(Qt.ItemDataRole.UserRole)
        self.density_editor.setCompleter(density_completion)

    def handle_selected_formula(self, index: QModelIndex):
        print(index)
        density = self.compound_model.data(index, Qt.ItemDataRole.UserRole)
        self.density_editor.setText(str(density))

    def _setup_ui(self):
        row_layout = QGridLayout()
        self.setLayout(row_layout)

        row_layout.addWidget(self.row_label,
                             0, 0, 2, 1,
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        row_layout.addWidget(QLabel("Formula:"),
                             0, 1, 1, 1,
                             Qt.AlignmentFlag.AlignLeft)
        row_layout.addWidget(self.formula_editor,
                             1, 1, 1, 1)

        row_layout.addWidget(QLabel("Density (g/cm³):"),
                             0, 2, 1, 1,
                             Qt.AlignmentFlag.AlignLeft)
        row_layout.addWidget(self.density_editor,
                             1, 2, 1, 1)

    def get_component(self):
        self.compound.formula = self.formula_editor.text()
        try:
            self.compound.density = float(self.density_editor.text())
        except ValueError:
            density_num_validation = ValidationInfos(errors=["The density wasn't a valid number."])
        else:
            density_num_validation = ValidationInfos()

        print(self.compound)

        return self.compound, density_num_validation


class SphereNPSEditor(QWidget, IGetComponent):
    """Sphere part of the `NPSEditor`"""
    def __init__(self, sphere: SphereNPS, compound_serivce: CompoundService):
        super().__init__()
        self.sphere = sphere
        self.formula_edit = CompoundEditor("Formula",
                                           self.sphere.formula,
                                           compound_serivce,
                                           parent=self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.formula_edit)

    def get_component(self) -> tuple[Any, ValidationInfos]:
        self.sphere.formula, validation = self.formula_edit.get_component()
        print(self.sphere)
        print(self.sphere.formula)
        return self.sphere, validation


class CoreShellNPSEditor(QWidget, IGetComponent):
    """Core-Shell part of the `NPSEditor"""
    def __init__(self, core_shell: CoreShellNPS, compound_service: CompoundService, /):
        super().__init__()
        self.compound_service = compound_service

        self.core_shell = core_shell
        self.core_edit = CompoundEditor("Core",
                                         self.core_shell.core,
                                         self.compound_service,
                                         parent=self)

        self.shell_edit = CompoundEditor("Shell",
                                         self.core_shell.shell,
                                         self.compound_service,
                                         parent=self)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(self.core_edit)
        layout.addWidget(self.shell_edit)

    def get_component(self) -> tuple[Any, ValidationInfos]:
        self.core_shell.core, validation_core = self.core_edit.get_component()
        self.core_shell.shell, validation_shell = self.shell_edit.get_component()
        return self.core_shell, validation_core.merge(validation_shell)


class NPSEditor(QDialog):
    """The NPS Editor is the editor for a specific"""
    accept_with_nps = Signal(NanoParticleShape)

    def __init__(self,
                 index: QModelIndex | None,
                 nps_model: QAbstractItemModel,
                 compound_service:CompoundService,
                 parent: QWidget | Any):
        super().__init__(parent=parent)
        self.logger = logging_manager.get_logger(self.__class__.__name__)
        self.model = nps_model
        self.compound_service = compound_service
        self.index = index
        self.nps = (nps_model.data(index, Qt.ItemDataRole.EditRole) if index is not None
                    else self.get_default_shape())
        self.nps_name = self.nps.get_name() or ""
        self.nps_name_edit = QLineEdit(str(self.nps_name),
                                       placeholderText="Name (default: shape formula)")

        self.current_form_widget: Optional[IGetComponent] = None
        self.nps_form_layout_index = 0

        self.error_label = None

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

    def _build_name_form(self):
        widget = QWidget(parent=self)
        layout = QFormLayout()
        widget.setLayout(layout)
        layout.addRow("Name", self.nps_name_edit)
        return widget

    def display_form_for_nps(self, nps: NanoParticleShape):
        """
        Displays the form with the right fields for the parameter's
        `NanoParticleShape` variation.

        Args:
            nps (NanoParticleShape): `NanoParticleShape` to be displayed.
        """
        layout = self.layout()

        # TODO: Find a smoother alternative
        assert isinstance(layout, QVBoxLayout)

        if isinstance(self.current_form_widget, QWidget):
            layout.removeWidget(self.current_form_widget)
            self.current_form_widget.hide()
            self.current_form_widget.deleteLater()
            self.current_form_widget = None

        match nps:
            case CoreShellNPS():
                self.logger.info("Displays core-shell form")
                self.current_form_widget = CoreShellNPSEditor(nps, self.compound_service)
                layout.insertWidget(self.nps_form_layout_index, self.current_form_widget)
            case SphereNPS():
                self.logger.info("Displays sphere form")
                self.current_form_widget = SphereNPSEditor(nps, self.compound_service)
                layout.insertWidget(self.nps_form_layout_index, self.current_form_widget)
            case obj:
                self.logger.critical(f"Class ({obj.__class__}) doesn't have a form")
                raise NotImplementedError(f"No NPS class for the type : {obj.__class__}")

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

    def handle_nps_selection_change(self, index: int):
        """
        Handles a user changing nps selection by displaying the new form.

        Args:
            index: index of the item in the `self.nps_combo_box`.
        """
        self.logger.info("NPS selection changed")
        self.nps = self.nps_combo_box.itemData(index)
        self.display_form_for_nps(self.nps)

    def emit_accept_with_nps(self):
        """
        Makes final preparation before emitting `accept_with_nps`.
        """
        self.nps, validation = self.current_form_widget.get_component()
        self.nps.name = self.nps_name_edit.text()
        validation.merge(self.nps.validate())

        if validation.has_errors() or validation.has_messages():
            self.logger.info("Display nps errors and/or messages")
            self._exec_validation_message_box(validation)

        if validation.has_errors():
            self.handle_errors(validation.errors)
        else:
            self.logger.info("Nps accepted")
            self.accept_with_nps.emit(self.nps)

    def _exec_validation_message_box(self, validation: ValidationInfos):
        message_box = QMessageBox(parent=self)
        message_box.setIcon(QMessageBox.Icon.Critical if validation.has_errors()
                            else QMessageBox.Icon.NoIcon)
        message_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        title_list = []
        text_message = ""
        if validation.has_errors():
            title_list.append("Errors")
            text_message += self._errors_to_html(validation.errors)

        if validation.has_messages():
            title_list.append("Messages")
            text_message += self._messages_to_html(validation.messages)

        message_box.setWindowTitle(" and ".join(title_list) + " List(s)")
        message_box.setText(text_message)

        message_box.exec()

    @staticmethod
    def _messages_to_html(messages: list[str]) -> str:
        return ("<p>Messages:</p>"
                + "<ul>"
                + "".join([f"<li>{message}</li>" for message in messages])
                + "</ul>")

    @staticmethod
    def _errors_to_html(errors: list[str]) -> str:
        return ("<p>Errors:</p>"
                + "<ul>"
                + "".join([f"<li>{error}</li>" for error in errors])
                + "</ul>")

    def handle_errors(self, errors: list[str]):
        """
        Shows the errors to the user while making sure the latest info is
        available.
        Args:
            errors (list[str]): list of error messages to be displayed to
            the user.
        """
        self.logger.info("Handling errors")
        self._update_forms()
        self._add_or_replace_error_label(errors)

    def _update_forms(self):
        self.nps_name_edit.setText(self.nps.get_name())
        self.display_form_for_nps(self.nps)

    def _add_or_replace_error_label(self, errors: list[str]):
        layout = self.layout()
        if not isinstance(layout, QVBoxLayout):
            raise Exception("the NPSEditor Layout is not of QVBoxLayout as expected")

        if isinstance(self.error_label, QLabel):
            self.error_label.setText(self._errors_to_html(errors))
            return

        self.error_label = QLabel(self._errors_to_html(errors))
        self.error_label.setStyleSheet("color: red;")
        layout.insertWidget(layout.count() - 1, self.error_label)

    @staticmethod
    def get_default_shape():
        """Defines a default `NanoParticleShape` to display."""
        return SphereNPS()  # TODO: Could we add a setting for that
