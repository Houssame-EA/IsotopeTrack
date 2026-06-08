import re
from PySide6.QtCore import Qt, QPropertyAnimation, QSettings
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget,
    QPushButton, QDoubleSpinBox, QMessageBox, QCheckBox, QGraphicsOpacityEffect,
)


def normalize_factor(value, minimum=1.0):
    """
    Coerce a value into a valid dilution factor.

    Args:
        value (Any): Raw value to normalize.
        minimum (float): Lower bound enforced on the result.

    Returns:
        float: A float not below minimum, defaulting to minimum on failure.
    """
    try:
        result = float(value)
    except (TypeError, ValueError):
        return minimum
    return result if result >= minimum else minimum


def get_sample_dilution(window, sample_name):
    """
    Return the dilution factor stored for a sample on a window.

    Args:
        window (Any): Owning window holding a sample_dilutions mapping.
        sample_name (str): Sample identifier.

    Returns:
        float: Stored dilution factor, defaulting to 1.0 when unset.
    """
    store = getattr(window, 'sample_dilutions', None)
    if not isinstance(store, dict):
        return 1.0
    return normalize_factor(store.get(sample_name, 1.0))


def set_sample_dilution(window, sample_name, factor):
    """
    Store a dilution factor for a sample on a window.

    Args:
        window (Any): Owning window holding a sample_dilutions mapping.
        sample_name (str): Sample identifier.
        factor (float): Dilution factor to store, clamped to a minimum of 1.0.

    Returns:
        None
    """
    if not isinstance(getattr(window, 'sample_dilutions', None), dict):
        window.sample_dilutions = {}
    window.sample_dilutions[sample_name] = normalize_factor(factor)


def detect_dilution_from_name(name):
    """
    Detect a dilution factor encoded in a sample or file name.

    Recognizes a number followed by the letter x as a separate token, such as
    sample_50x or run-2.5x, ignoring case and any known file extension. When
    several such tokens are present the last one is used, since the dilution is
    conventionally written at the end of the name.

    Args:
        name (str): Sample name or file name to inspect.

    Returns:
        float: Detected dilution factor, or None when no pattern matches.
    """
    if not name:
        return None
    stem = re.sub(r'\.(csv|tsv|xlsx|xls|h5|txt)$', '', str(name), flags=re.IGNORECASE)
    matches = re.findall(r'(?:^|[\s_\-])(\d+(?:\.\d+)?)[xX](?=$|[\s_\-])', stem)
    if not matches:
        return None
    try:
        value = float(matches[-1])
    except ValueError:
        return None
    return value if value >= 1.0 else None


def detect_dilution_for_sample(window, sample_name):
    """
    Detect a dilution factor for a sample, preferring its source file name.

    The original file or folder path recorded for the sample is inspected
    first, since sample display names are often cleaned of the encoded factor.
    The sample name itself is used as a fallback.

    Args:
        window (Any): Owning window exposing sample_to_folder_map.
        sample_name (str): Sample identifier.

    Returns:
        float: Detected dilution factor, or None when no pattern matches.
    """
    source = None
    folder_map = getattr(window, 'sample_to_folder_map', None)
    if isinstance(folder_map, dict):
        source = folder_map.get(sample_name)
    if source:
        try:
            from pathlib import Path
            stem = Path(str(source)).name
        except Exception:
            stem = str(source)
        detected = detect_dilution_from_name(stem)
        if detected is not None:
            return detected
    return detect_dilution_from_name(sample_name)


def has_transport_rate(window):
    """
    Report whether a window has a usable transport rate calibration.

    Args:
        window (Any): Owning window exposing average_transport_rate.

    Returns:
        bool: True when an average transport rate greater than zero exists.
    """
    rate = getattr(window, 'average_transport_rate', 0)
    return bool(rate and rate > 0)


def effective_acquisition_time(window, sample_name, element_key=None):
    """
    Return the analyzed acquisition time in seconds for a sample.

    Excluded time regions visible for the sample are subtracted from the full
    acquisition span. Sample scope exclusions always apply; element scope
    exclusions apply only when element_key matches the stored region.

    Args:
        window (Any): Owning window exposing time arrays and exclusion regions.
        sample_name (str): Sample identifier.
        element_key (str): Optional element key for element scope exclusions.

    Returns:
        float: Effective acquisition time in seconds, never negative.
    """
    time_array = None
    by_sample = getattr(window, 'time_array_by_sample', {})
    if sample_name in by_sample:
        time_array = by_sample.get(sample_name)
    elif sample_name == getattr(window, 'current_sample', None):
        time_array = getattr(window, 'time_array', None)
    if time_array is None or len(time_array) < 2:
        return 0.0
    t_min = float(time_array[0])
    t_max = float(time_array[-1])
    total_time = t_max - t_min
    if hasattr(window, '_visible_exclusion_entries_for'):
        for entry in window._visible_exclusion_entries_for(sample_name, element_key):
            bounds = entry.get('bounds')
            if not bounds:
                continue
            x0 = max(float(bounds[0]), t_min)
            x1 = min(float(bounds[1]), t_max)
            if x1 > x0:
                total_time -= (x1 - x0)
    return max(total_time, 0.0)


def effective_volume_ml(window, sample_name, element_key=None):
    """
    Return the analyzed sample volume in millilitres for a sample.

    Volume is the average transport rate in microlitres per second multiplied
    by the effective acquisition time, converted to millilitres.

    Args:
        window (Any): Owning window exposing the transport rate.
        sample_name (str): Sample identifier.
        element_key (str): Optional element key for element scope exclusions.

    Returns:
        float: Effective analyzed volume in millilitres, 0.0 when no transport
            rate calibration is available.
    """
    rate = getattr(window, 'average_transport_rate', 0)
    if not rate or rate <= 0:
        return 0.0
    seconds = effective_acquisition_time(window, sample_name, element_key)
    return (rate * seconds) / 1000.0


def particles_per_ml(window, sample_name, particle_count, element_key=None,
                     apply_dilution=True):
    """
    Return the particle number concentration in particles per millilitre.

    Args:
        window (Any): Owning window exposing volume and dilution helpers.
        sample_name (str): Sample identifier.
        particle_count (int): Number of particles for the quantity of interest.
        element_key (str): Optional element key for element scope exclusions.
        apply_dilution (bool): Multiply by the sample dilution factor when True.

    Returns:
        float: Concentration in particles per millilitre, 0.0 when the analyzed
            volume is unavailable.
    """
    volume_ml = effective_volume_ml(window, sample_name, element_key)
    if volume_ml <= 0 or not particle_count:
        return 0.0
    value = particle_count / volume_ml
    if apply_dilution:
        value *= get_sample_dilution(window, sample_name)
    return value


def open_dilution_factor_dialog(window):
    """
    Open the per sample dilution factor editor for a window.

    Args:
        window (Any): Owning window exposing data_by_sample.

    Returns:
        None
    """
    samples = list(getattr(window, 'data_by_sample', {}).keys())
    if not samples:
        QMessageBox.information(window, "No Samples",
                                "Import data before setting dilution factors.")
        return
    dialog = DilutionFactorDialog(window, samples)
    dialog.exec()


def maybe_prompt_dilution(window):
    """
    Show a one time prompt inviting dilution correction of particles per mL.

    The prompt appears when a transport rate is available, no sample has a
    dilution factor set, and the user has not chosen to hide it. When declined,
    the Tools menu is highlighted to indicate where the factor is entered.

    Args:
        window (Any): Owning window.

    Returns:
        None
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
        "Tools \u2192 Dilution Factor to correct the concentrations.")
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
    """
    Briefly animate the Tools menu to indicate where dilution is entered.

    Args:
        window (Any): Owning window with a menu bar containing a Tools menu.

    Returns:
        None
    """
    menu_bar = window.menuBar()
    tools_action = None
    for action in menu_bar.actions():
        if action.text() == "Tools":
            tools_action = action
            break
    if tools_action is None:
        return
    rect = menu_bar.actionGeometry(tools_action)
    indicator = QLabel(menu_bar)
    indicator.setText("\u25b2 Dilution Factor here")
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
        """
        Build the dilution factor dialog for the given samples.

        Args:
            main_window (Any): Owning window providing dilution storage.
            sample_names (list): Sample identifiers to expose for editing.

        Returns:
            None
        """
        super().__init__(main_window)
        self.main_window = main_window
        self.sample_names = list(sample_names)
        self.spinboxes = {}
        self.setWindowTitle("Dilution Factor")
        self.setMinimumWidth(460)
        self._build_ui()

    def _build_ui(self):
        """
        Construct the dialog widgets and populate stored values.

        Args:
            self: DilutionFactorDialog instance.

        Returns:
            None
        """
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
        """
        Set a single sample spinbox to a detected dilution factor.

        Args:
            sample_name (str): Sample to update.
            value (float): Detected dilution factor.

        Returns:
            None
        """
        if sample_name in self.spinboxes:
            self.spinboxes[sample_name].setValue(value)

    def _apply_all_detected(self):
        """
        Apply every detectable dilution factor to its sample spinbox.

        Args:
            self: DilutionFactorDialog instance.

        Returns:
            None
        """
        for sample_name, spin in self.spinboxes.items():
            detected = detect_dilution_for_sample(self.main_window, sample_name)
            if detected is not None:
                spin.setValue(detected)

    def _reset_all(self):
        """
        Reset every sample spinbox to a dilution factor of one.

        Args:
            self: DilutionFactorDialog instance.

        Returns:
            None
        """
        for spin in self.spinboxes.values():
            spin.setValue(1.0)

    def _save(self):
        """
        Persist all spinbox values into the main window dilution store.

        Args:
            self: DilutionFactorDialog instance.

        Returns:
            None
        """
        for sample_name, spin in self.spinboxes.items():
            set_sample_dilution(self.main_window, sample_name, spin.value())
        self.accept()