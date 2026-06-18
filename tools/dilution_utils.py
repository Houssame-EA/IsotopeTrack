"""Dilution factor UI: the per-sample editor dialog and the one-time prompt.

The underlying calculations (dilution detection, effective volume,
particles/mL, etc.) live in ``utils/dilution.py``. This module only builds
the Qt dialogs and menu hints.
"""
from PySide6.QtCore import Qt, QPropertyAnimation, QSettings
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget,
    QPushButton, QDoubleSpinBox, QMessageBox, QCheckBox, QGraphicsOpacityEffect,
)
import logging

from utils.dilution import (
    normalize_factor, get_sample_dilution, set_sample_dilution,
    detect_dilution_for_sample, has_transport_rate,
)

_itk_log = logging.getLogger("IsotopeTrack.tools.dilution_utils")


def open_dilution_factor_dialog(window):
    """Open the per sample dilution factor editor for a window."""
    samples = list(getattr(window, 'data_by_sample', {}).keys())
    if not samples:
        QMessageBox.information(window, "No Samples",
                                "Import data before setting dilution factors.")
        return
    dialog = DilutionFactorDialog(window, samples)
    dialog.exec()


def maybe_prompt_dilution(window):
    """Show a one time prompt inviting dilution correction of particles per mL.

    The prompt appears when a transport rate is available, no sample has a
    dilution factor set, and the user has not chosen to hide it. When declined,
    the Tools menu is highlighted to indicate where the factor is entered.
    """
    if not has_transport_rate(window):
        return
    settings = QSettings("IsotopeTrack", "IsotopeTrack")
    if settings.value("hide_dilution_prompt", False, type=bool):
        return
    dilutions = getattr(window, 'sample_dilutions', {}) or {}
    if any(normalize_factor(v) > 1.0 for v in dilutions.values()):
        return
    box = QMessageBox(window)
    box.setIcon(QMessageBox.Information)
    box.setWindowTitle("Correct Particles per mL?")
    box.setText(
        "A transport rate is available, so particle concentrations "
        "(particles/mL) can be reported.\n\n"
        "If your samples were diluted, enter the dilution factor under "
        "Tools → Dilution Factor to correct the concentrations.")
    dont_show = QCheckBox("Don't show this message again")
    box.setCheckBox(dont_show)
    open_btn = box.addButton("Open Dilution Factor", QMessageBox.AcceptRole)
    box.addButton("Later", QMessageBox.RejectRole)
    box.exec()
    if dont_show.isChecked():
        settings.setValue("hide_dilution_prompt", True)
    if box.clickedButton() is open_btn:
        open_dilution_factor_dialog(window)
    else:
        highlight_tools_menu(window)


def highlight_tools_menu(window):
    """Briefly animate the Tools menu to indicate where dilution is entered."""
    from PySide6.QtWidgets import QMenuBar
    menu_bar = window.menuBar()
    if not isinstance(menu_bar, QMenuBar):
        # Defensive: PySide6 can return a stale QWidgetItem wrapper; skip the
        # cosmetic animation rather than crash.
        return
    tools_action = None
    for action in menu_bar.actions():
        if action.text() == "Tools":
            tools_action = action
            break
    if tools_action is None:
        return
    rect = menu_bar.actionGeometry(tools_action)
    indicator = QLabel(menu_bar)
    indicator.setText("▲ Dilution Factor here")
    indicator.setStyleSheet(
        "color: #B45309; font-weight: bold; background: transparent;")
    indicator.adjustSize()
    indicator.move(rect.left(), rect.bottom())
    indicator.show()
    effect = QGraphicsOpacityEffect(indicator)
    indicator.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", window)
    anim.setDuration(2400)
    anim.setKeyValueAt(0.0, 0.0)
    anim.setKeyValueAt(0.2, 1.0)
    anim.setKeyValueAt(0.8, 1.0)
    anim.setKeyValueAt(1.0, 0.0)
    anim.setLoopCount(2)
    anim.finished.connect(indicator.deleteLater)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    window._dilution_hint_anim = anim


class DilutionFactorDialog(QDialog):
    """Per sample dilution factor editor with filename auto detection."""

    def __init__(self, main_window, sample_names):
        """Build the dilution factor dialog for the given samples.

        Args:
            main_window (Any): Owning window providing dilution storage.
            sample_names (list): Sample identifiers to expose for editing.
        """
        super().__init__(main_window)
        self.main_window = main_window
        self.sample_names = list(sample_names)
        self.spinboxes = {}
        self.setWindowTitle("Dilution Factor")
        self.setMinimumWidth(460)
        self._build_ui()

    def _build_ui(self):
        """Construct the dialog widgets and populate stored values."""
        outer = QVBoxLayout(self)

        info = QLabel(
            "Set a dilution factor per sample. Corrected particles/mL is the "
            "measured value multiplied by this factor.")
        info.setWordWrap(True)
        outer.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        grid = QVBoxLayout(container)

        any_detected = False
        for sample_name in self.sample_names:
            row = QHBoxLayout()
            label = QLabel(sample_name)
            label.setMinimumWidth(180)
            row.addWidget(label)

            spin = QDoubleSpinBox()
            spin.setRange(1.0, 1000000.0)
            spin.setDecimals(3)
            spin.setSuffix("x")
            spin.setFocusPolicy(Qt.StrongFocus)
            spin.setValue(get_sample_dilution(self.main_window, sample_name))
            self.spinboxes[sample_name] = spin
            row.addWidget(spin)

            detected = detect_dilution_for_sample(self.main_window, sample_name)
            if detected is not None:
                any_detected = True
                btn = QPushButton(f"Apply ({detected:g}x)")
                btn.clicked.connect(
                    lambda _=False, s=sample_name, d=detected: self._apply_detected(s, d))
                row.addWidget(btn)

            grid.addLayout(row)

        grid.addStretch(1)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        btn_row = QHBoxLayout()
        if any_detected:
            apply_all = QPushButton("Autofill all detected")
            apply_all.clicked.connect(self._apply_all_detected)
            btn_row.addWidget(apply_all)
        reset_btn = QPushButton("Reset all")
        reset_btn.clicked.connect(self._reset_all)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        outer.addLayout(btn_row)

    def _apply_detected(self, sample_name, value):
        """Set a single sample spinbox to a detected dilution factor.

        Args:
            sample_name (str): Sample to update.
            value (float): Detected dilution factor.
        """
        if sample_name in self.spinboxes:
            self.spinboxes[sample_name].setValue(value)

    def _apply_all_detected(self):
        """Apply every detectable dilution factor to its sample spinbox."""
        for sample_name, spin in self.spinboxes.items():
            detected = detect_dilution_for_sample(self.main_window, sample_name)
            if detected is not None:
                spin.setValue(detected)

    def _reset_all(self):
        """Reset every sample spinbox to a dilution factor of one."""
        for spin in self.spinboxes.values():
            spin.setValue(1.0)

    def _save(self):
        """Persist all spinbox values into the main window dilution store."""
        for sample_name, spin in self.spinboxes.items():
            set_sample_dilution(self.main_window, sample_name, spin.value())
        self.accept()
