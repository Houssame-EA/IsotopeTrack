import sys
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QComboBox, QMessageBox, QFormLayout, QApplication, QGroupBox,
    QMainWindow, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator

from calibration_methods.te_common import (
    BASE_STYLESHEET, PREVIEW_STYLES, create_scrollable_container,
    weight_method_transport_rate,
    base_stylesheet, preview_styles,
)
from theme import theme


class InputMethodCalibration(QMainWindow):
    """Weight-method calibration widget with live preview and direct-rate entry."""

    calibration_completed = Signal(str, float)

    def __init__(self, parent=None):
        """
        Initialise the Weight Method Calibration window.

        Args:
            parent (QWidget | None): Parent widget for this window.
        """
        super().__init__(parent)
        self._init_ui()
        self.apply_theme()
        self._theme_cleanup = theme.connect_theme(self.apply_theme)
        self.destroyed.connect(lambda *_: self._theme_cleanup())            

    # ── Theme ────────────────────────────────────────────────────────────

    def apply_theme(self, *_):
        """Re-apply styling from the current theme palette.  Covers the
        window QSS, the preview label (which is driven by palette-aware
        preview_styles), and the calculate button.
        Args:
            *_ (Any): Additional positional arguments.
        """
        p = theme.palette
        self.setStyleSheet(base_stylesheet(p))
        self._preview_styles = preview_styles(p)
        if hasattr(self, "result_preview") and hasattr(self, "_preview_key"):
            self.result_preview.setStyleSheet(
                self._preview_styles.get(self._preview_key,
                                         self._preview_styles["default"])
            )
        if hasattr(self, "calc_btn"):
            self.calc_btn.setStyleSheet(
                "QPushButton { font-size: 16px; font-weight: bold; }"
            )

    # ── UI construction ──────────────────────────────────────────────────

    def _init_ui(self):
        """
        Build and wire all UI elements.

        Returns:
            None
        """
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        _scroll, scroll_layout = create_scrollable_container(main_layout)

        self._create_intro_section(scroll_layout)
        self._create_measurement_section(scroll_layout)
        self._create_calculation_section(scroll_layout)

        self.setWindowTitle("Weight Method Calibration")
        self.setMinimumSize(800, 600)

        for widget in (self.initial_weight, self.final_weight,
                       self.waste_weight, self.analysis_time):
            widget.textChanged.connect(self._update_preview)
        self.weight_unit.currentIndexChanged.connect(self._update_preview)
        self.time_unit.currentIndexChanged.connect(self._update_preview)

    def _create_intro_section(self, parent_layout):
        """
        Add the introductory description group box.

        Args:
            parent_layout (QVBoxLayout): Layout to append the section to.

        Returns:
            None
        """
        group = QGroupBox("1. Weight Method Calibration")
        layout = QVBoxLayout(group)
        desc = QLabel(
            "The weight method determines transport rate by measuring weight "
            "changes in the sample vial and waste collection container during "
            "analysis. This provides a direct physical measurement of the "
            "actual sample volume transported to the plasma."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        parent_layout.addWidget(group)

    def _create_measurement_section(self, parent_layout):
        """
        Add the measurement-input group box (units + four fields).

        Args:
            parent_layout (QVBoxLayout): Layout to append the section to.

        Returns:
            None
        """
        group = QGroupBox("2. Enter Measurements")
        group_layout = QVBoxLayout(group)

        units_row = QHBoxLayout()
        units_row.setSpacing(20)
        self.weight_unit = QComboBox()
        self.weight_unit.addItems(["mg", "g"])
        self.time_unit = QComboBox()
        self.time_unit.addItems(["seconds", "minutes"])
        for label, combo in [("Mass unit:", self.weight_unit),
                             ("Time unit:", self.time_unit)]:
            units_row.addWidget(QLabel(label))
            units_row.addWidget(combo)
            units_row.addSpacing(40)
        units_row.addStretch()
        group_layout.addLayout(units_row)

        form = QFormLayout()
        form.setSpacing(15)
        validator = QDoubleValidator(0.0, 100_000.0, 5)

        self.initial_weight = self._make_line_edit("Initial mass...", validator)
        self.final_weight = self._make_line_edit("Final mass...", validator)
        self.waste_weight = self._make_line_edit("Waste mass...", validator)
        self.analysis_time = self._make_line_edit(
            "Analysis time...", QDoubleValidator(0.0, 10_000.0, 2)
        )

        form.addRow("Initial sample mass:", self.initial_weight)
        form.addRow("Final sample mass:", self.final_weight)
        form.addRow("Waste container mass:", self.waste_weight)
        form.addRow("Analysis time:", self.analysis_time)
        group_layout.addLayout(form)

        parent_layout.addWidget(group)

    def _create_calculation_section(self, parent_layout):
        """
        Add the calculation group box (preview, calculate, direct entry).

        Args:
            parent_layout (QVBoxLayout): Layout to append the section to.

        Returns:
            None
        """
        group = QGroupBox("3. Calculate Transport Rate")
        group_layout = QVBoxLayout(group)

        self.result_preview = QLabel(
            "Enter measurements to see calculation preview"
        )
        self.result_preview.setWordWrap(True)
        self.result_preview.setAlignment(Qt.AlignCenter)
        self.result_preview.setMinimumHeight(60)
        self._preview_key = "default"
        group_layout.addWidget(self.result_preview)

        self.calc_btn = QPushButton("Calculate Transport Rate")
        self.calc_btn.setMinimumHeight(40)
        self.calc_btn.clicked.connect(self._calculate)
        group_layout.addWidget(self.calc_btn)

        direct_row = QHBoxLayout()
        self.direct_rate = QLineEdit()
        self.direct_rate.setPlaceholderText("Enter known rate...")
        self.direct_rate.setValidator(QDoubleValidator(0.0, 1000.0, 5))
        self.direct_rate.setMaximumWidth(150)

        direct_btn = QPushButton("Submit Direct")
        direct_btn.clicked.connect(self._submit_direct)
        direct_btn.setMaximumWidth(120)

        direct_row.addWidget(QLabel("Or enter known rate:"))
        direct_row.addWidget(self.direct_rate)
        direct_row.addWidget(QLabel("μL/s"))
        direct_row.addWidget(direct_btn)
        direct_row.addStretch()
        group_layout.addLayout(direct_row)

        parent_layout.addWidget(group)

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _make_line_edit(placeholder, validator):
        """
        Create a QLineEdit with placeholder text and a validator.

        Args:
            placeholder (str): Placeholder text shown when the field is empty.
            validator (QValidator): Input validator to apply.

        Returns:
            QLineEdit: Configured line-edit widget.
        """
        le = QLineEdit()
        le.setPlaceholderText(placeholder)
        le.setValidator(validator)
        return le

    def _read_inputs(self):
        """
        Parse and unit-convert all measurement fields.

        Returns:
            tuple[float, float, float, float]: (w_initial_g, w_final_g,
            w_waste_g, time_s) all in grams and seconds.

        Raises:
            ValueError: If any field is empty or non-numeric.
        """
        texts = [
            self.initial_weight.text(), self.final_weight.text(),
            self.waste_weight.text(), self.analysis_time.text(),
        ]
        if not all(texts):
            raise ValueError("Please fill in all measurement fields.")

        w_i, w_f, w_w, t = (float(t) for t in texts)

        if self.weight_unit.currentText() == "mg":
            w_i /= 1000.0
            w_f /= 1000.0
            w_w /= 1000.0
        if self.time_unit.currentText() == "minutes":
            t *= 60.0

        return w_i, w_f, w_w, t

    def _set_preview(self, text, style_key="default"):
        """
        Update the preview label's text and style.

        Args:
            text (str): Message to display.
            style_key (str): One of the keys in preview_styles()
                ('default', 'error', 'warning', 'success').

        Returns:
            None
        """
        self.result_preview.setText(text)
        self._preview_key = style_key
        styles = getattr(self, "_preview_styles", None) or preview_styles(theme.palette)
        self.result_preview.setStyleSheet(
            styles.get(style_key, styles["default"])
        )

    # ── Slots ─────────────────────────────────────────────────────────────

    def _update_preview(self):
        """
        Recalculate and display the transport rate in the preview label.

        Connected to every input widget's change signal for real-time feedback.

        Returns:
            None
        """
        try:
            w_i, w_f, w_w, t = self._read_inputs()
            result = weight_method_transport_rate(w_i, w_f, w_w, t)
            rate = result["transport_rate_ul_s"]
            self._set_preview(
                f"Calculated transport rate: {rate:.6f} μL/s", "success"
            )
        except ValueError as exc:
            msg = str(exc)
            if "fill in" in msg.lower():
                self._set_preview(
                    "Enter all measurements to see calculation preview", "default"
                )
            else:
                self._set_preview(f"{msg}", "error")

    def _calculate(self):
        """
        Compute the transport rate, emit the result, and show a detail dialog.

        Returns:
            None
        """
        try:
            w_i, w_f, w_w, t = self._read_inputs()
            result = weight_method_transport_rate(w_i, w_f, w_w, t)
            rate = result["transport_rate_ul_s"]

            self.calibration_completed.emit("Weight Method", rate)

            detail = (
                f"Transport Rate: {rate:.6f} μL/s\n\n"
                f"Calculation Details:\n"
                f"• Sample consumed: {result['sample_consumed_g']:.5f} g\n"
                f"• Volume to plasma: {result['volume_to_plasma_g']:.5f} g\n"
                f"• Analysis time: {t:.1f} seconds"
            )
            QMessageBox.information(self, "Calculation Results", detail)

        except ValueError as exc:
            QMessageBox.warning(self, "Input Error", str(exc))

    def _submit_direct(self):
        """
        Validate and emit a user-supplied transport rate.

        Returns:
            None
        """
        try:
            rate = float(self.direct_rate.text())
            if rate <= 0:
                raise ValueError("Transport rate must be greater than zero.")
            self.calibration_completed.emit("Weight Method", rate)
            QMessageBox.information(
                self, "Success",
                f"Transport rate of {rate:.6f} μL/s submitted successfully."
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Input Error", str(exc))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = InputMethodCalibration()
    window.show()
    sys.exit(app.exec())