from typing import Any

from PySide6.QtCore import Signal, QModelIndex, QAbstractItemModel, Qt
from PySide6.QtWidgets import QWidget, QLineEdit, QFormLayout, QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, \
    QPushButton, QMessageBox, QSizePolicy

from tools.nano_particle_shape.nano_particle_shapes import SphereNPS, CoreShellNPS, NanoParticleShape
from tools.theme import results_title_qss, theme, primary_button_qss
from utils.validation import ValidationInfos


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
                                       placeholderText="Name (default: shape formula)")

        self.current_form_widget = None
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
        self.nps = self.nps_combo_box.itemData(index)
        self.display_form_for_nps(self.nps)

    def emit_accept_with_nps(self):
        """
        Makes final preparation before emitting `accept_with_nps`.
        """
        self.nps.name = self.nps_name_edit.text()
        validation = self.nps.validate()

        if validation.has_errors() or validation.has_messages():
            self._exec_validation_message_box(validation)

        if validation.has_errors():
            self.handle_errors(validation.errors)
        else:
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
