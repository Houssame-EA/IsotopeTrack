import sys
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QLabel, QWidget, QScrollArea
)
from PySide6.QtCore import Qt, Signal
import qtawesome as qta

from calibration_methods.TE_input import InputMethodCalibration
from calibration_methods.TE_number import NumberMethodWidget
from calibration_methods.TE_mass import MassMethodWidget
from calibration_methods.te_common import (
    RETURN_BUTTON_STYLE,
    base_stylesheet, return_button_style,
)
from theme import theme

# ── user-action logging ──────────────────────────────────────────────────────
def _ual():
    """Return the UserActionLogger, or None if logging isn't ready.
    Returns:
        object: Result of the operation.
    """
    try:
        from tools.logging_utils import logging_manager
        return logging_manager.get_user_action_logger()
    except Exception:
        return None

_METHOD_SIGNAL_MAP = {
    "Liquid weight": "Weight Method",
    "Number based": "Particle Method",
    "Mass based": "Mass Method",
}


class TransportRateCalibrationWindow(QDialog):
    """Top-level dialog housing the three calibration method widgets."""

    calibration_completed = Signal(str, float)

    def __init__(self, selected_methods, parent=None):
        """
        Initialise the Transport Rate Calibration dialog.

        Args:
            selected_methods (list[str]): Method labels to expose
                (e.g. ``['Liquid weight', 'Number based', 'Mass based']``).
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Transport Rate Calibration")
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.selected_methods = selected_methods
        self._build_ui()
        self.apply_theme()
        self._theme_cleanup = theme.connect_theme(self.apply_theme)
        self.destroyed.connect(lambda *_: self._theme_cleanup())
        self.showMaximized()
        ual = _ual()
        if ual:
            ual.log_action('DIALOG_OPEN', 'Opened Transport Rate Calibration',
                           {'methods': self.selected_methods})

    # ── Event overrides ──────────────────────────────────────────────────

    def closeEvent(self, event):
        """
        Hide the window instead of destroying it on close.

        Args:
            event (QCloseEvent): The close event to intercept.

        Returns:
            None
        """
        event.ignore()
        self.hide()

    # ── Theme ────────────────────────────────────────────────────────────

    def apply_theme(self, *_):
        """Re-apply all stylesheets from the current theme palette.
        Runs on init and whenever theme.themeChanged fires.
        Args:
            *_ (Any): Additional positional arguments.
        """
        p = theme.palette
        self.setStyleSheet(
            base_stylesheet(p)
            + f"""
                QDialog {{ background-color: {p.bg_primary}; }}
                QScrollArea {{ border: none; background-color: transparent; }}
                QToolButton {{ border: none; padding: 5px; }}
                QToolButton:hover {{
                    background-color: {p.bg_hover};
                    border-radius: 3px;
                }}
            """
        )
        if hasattr(self, "return_btn"):
            self.return_btn.setStyleSheet(return_button_style(p))
            icon_color = "#ffffff" if p.name == "dark" else "#B81414"
            self.return_btn.setIcon(qta.icon("fa6s.house", color=icon_color))

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self):
        """
        Construct the header, method selector, content area, and scroll wrapper.

        Returns:
            None
        """
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        header = QHBoxLayout()
        title = QLabel("Transport Rate Calibration")
        title.setObjectName("dialogTitle")
        header.addWidget(title)
        header.addStretch()

        self.return_btn = QPushButton("Back to Main")
        self.return_btn.setObjectName("returnButton")
        self.return_btn.setFixedSize(150, 45)
        def _back_and_log():
            ual = _ual()
            if ual:
                ual.log_action('CLICK', 'Transport Rate Calibration — Back to Main')
            self.hide()
        self.return_btn.clicked.connect(_back_and_log)
        header.addWidget(self.return_btn)
        main_layout.addLayout(header)

        selector_row = QHBoxLayout()
        self.method_combo = QComboBox()
        self.method_combo.addItems(self.selected_methods)
        selector_row.addWidget(QLabel("Select Method:"))
        selector_row.addWidget(self.method_combo)
        selector_row.addStretch()
        main_layout.addLayout(selector_row)

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)

        self._method_widgets = {
            "Liquid weight": InputMethodCalibration(),
            "Number based": NumberMethodWidget(),
            "Mass based": MassMethodWidget(),
        }
        for w in self._method_widgets.values():
            w.calibration_completed.connect(self._on_calibration_completed)

        if self.selected_methods:
            self._content_layout.addWidget(
                self._method_widgets[self.selected_methods[0]]
            )

        main_layout.addWidget(self._content_widget)

        scroll = QScrollArea()
        scroll.setWidget(main_widget)
        scroll.setWidgetResizable(True)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(scroll)

        self.method_combo.currentIndexChanged.connect(self._show_selected_method)
        self.setMinimumSize(800, 600)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _show_selected_method(self, index):
        """
        Swap the visible calibration widget to match the combo-box selection.

        Args:
            index (int): Combo-box index of the newly selected method.

        Returns:
            None
        """
        if 0 <= index < len(self.selected_methods):
            _method_key = self.selected_methods[index]
        else:
            _method_key = self.method_combo.currentText()
        ual = _ual()
        if ual:
            ual.log_action('CLICK', f'Transport Rate method switched: {_method_key}',
                           {'method': _method_key, 'index': index})
        for i in reversed(range(self._content_layout.count())):
            item = self._content_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        if 0 <= index < len(self.selected_methods):
            key = self.selected_methods[index]
        else:
            key = self.method_combo.currentText()

        widget = self._method_widgets.get(key)
        if widget:
            self._content_layout.addWidget(widget)
        else:
            print(f"Warning: no widget for method '{key}'")

    def _on_calibration_completed(self, method, transport_rate):
        """
        Re-emit the calibration result with a standardised method name.

        Args:
            method (str): Method name as emitted by the child widget.
            transport_rate (float): Calculated transport rate in µL/s.

        Returns:
            None
        """
        standardised = _METHOD_SIGNAL_MAP.get(method, method)
        ual = _ual()
        if ual:
            ual.log_action('ANALYSIS',
                           f'Transport Rate calibration completed: {standardised}',
                           {'method': standardised,
                            'transport_rate_uL_s': round(transport_rate, 6)})
        self.calibration_completed.emit(standardised, transport_rate)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TransportRateCalibrationWindow(
        ["Liquid weight", "Number based", "Mass based"]
    )
    window.showMaximized()
    sys.exit(app.exec())