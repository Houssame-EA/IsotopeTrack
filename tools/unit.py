from dataclasses import dataclass, field
from PySide6.QtCore import QSettings


# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

MASS_UNITS = {
    "ag":  1e3,
    "fg":  1.0,
    "pg":  1e-3,
    "ng":  1e-6,
    "µg":  1e-9,
    "mg":  1e-12,
    "g":   1e-15,
}

MOLES_UNITS = {
    "amol": 1e3,
    "fmol": 1.0,
    "pmol": 1e-3,
    "nmol": 1e-6,
    "µmol": 1e-9,
    "mmol": 1e-12,
    "mol":  1e-15,
}

DIAMETER_UNITS = {
    "nm": 1.0,
    "µm": 1e-3,
}

NUMBER_FORMATS = ("decimal", "scientific")


# --------------------------------------------------------------------------- #
# ExportUnits value object
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ExportUnits:
    """Bundles the user's unit + formatting preferences.

    Defaults reproduce the original hardcoded behaviour (fg / fmol / nm,
    decimal notation, 4 decimals for mass, 6 for moles, 2 for diameter).
    """
    mass_unit: str = "fg"
    moles_unit: str = "fmol"
    diameter_unit: str = "nm"
    number_format: str = "decimal"
    mass_decimals: int = 4
    moles_decimals: int = 6
    diameter_decimals: int = 2

    # ---- Unit labels for CSV headers --------------------------------- #
    @property
    def mass_label(self) -> str:
        """
        Returns:
            str: Result of the operation.
        """
        return self.mass_unit

    @property
    def moles_label(self) -> str:
        """
        Returns:
            str: Result of the operation.
        """
        return self.moles_unit

    @property
    def diameter_label(self) -> str:
        """
        Returns:
            str: Result of the operation.
        """
        return self.diameter_unit

    # ---- Formatters -------------------------------------------------- #
    def _format(self, value: float, decimals: int) -> str:
        """Render a number in the user's chosen format.
        Args:
            value (float): Value to set or process.
            decimals (int): The decimals.
        Returns:
            str: Result of the operation.
        """
        if value is None:
            return "0"
        try:
            v = float(value)
        except (TypeError, ValueError):
            return "0"
        if self.number_format == "scientific":
            return f"{v:.{decimals}e}"
        return f"{v:.{decimals}f}"

    def fmt_mass(self, mass_fg: float) -> str:
        """Format an internal fg mass in the user's chosen unit + format.
        Args:
            mass_fg (float): The mass fg.
        Returns:
            str: Result of the operation.
        """
        factor = MASS_UNITS.get(self.mass_unit, 1.0)
        return self._format(mass_fg * factor, self.mass_decimals)

    def fmt_moles(self, moles_fmol: float) -> str:
        """
        Args:
            moles_fmol (float): The moles fmol.
        Returns:
            str: Result of the operation.
        """
        factor = MOLES_UNITS.get(self.moles_unit, 1.0)
        return self._format(moles_fmol * factor, self.moles_decimals)

    def fmt_diameter(self, diameter_nm: float) -> str:
        """
        Args:
            diameter_nm (float): The diameter nm.
        Returns:
            str: Result of the operation.
        """
        factor = DIAMETER_UNITS.get(self.diameter_unit, 1.0)
        return self._format(diameter_nm * factor, self.diameter_decimals)

    def fmt_mass_or_zero(self, mass_fg: float) -> str:
        """
        Args:
            mass_fg (float): The mass fg.
        Returns:
            str: Result of the operation.
        """
        return self.fmt_mass(mass_fg) if mass_fg and mass_fg > 0 else "0"

    def fmt_moles_or_zero(self, moles_fmol: float) -> str:
        """
        Args:
            moles_fmol (float): The moles fmol.
        Returns:
            str: Result of the operation.
        """
        return self.fmt_moles(moles_fmol) if moles_fmol and moles_fmol > 0 else "0"

    def fmt_diameter_or_zero(self, diameter_nm: float) -> str:
        """
        Args:
            diameter_nm (float): The diameter nm.
        Returns:
            str: Result of the operation.
        """
        if not diameter_nm or diameter_nm <= 0:
            return "0"
        try:
            if diameter_nm != diameter_nm:
                return "0"
        except Exception:
            return "0"
        return self.fmt_diameter(diameter_nm)


# --------------------------------------------------------------------------- #
# Persistence (QSettings)
# --------------------------------------------------------------------------- #

_SETTINGS_ORG = "IsotopeTrack"
_SETTINGS_APP = "IsotopeTrack"
_KEY_PREFIX   = "export/units/"


def load_units() -> ExportUnits:
    """Load the user's saved preferences, falling back to defaults for any
    missing / invalid values.
    Returns:
        ExportUnits: Result of the operation.
    """
    s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)

    def _get_str(key, default, valid):
        """
        Args:
            key (Any): Dictionary or storage key.
            default (Any): The default.
            valid (Any): The valid.
        Returns:
            object: Result of the operation.
        """
        v = s.value(_KEY_PREFIX + key, default)
        return v if v in valid else default

    def _get_int(key, default, lo=0, hi=12):
        """
        Args:
            key (Any): Dictionary or storage key.
            default (Any): The default.
            lo (Any): The lo.
            hi (Any): The hi.
        Returns:
            object: Result of the operation.
        """
        try:
            v = int(s.value(_KEY_PREFIX + key, default))
            return max(lo, min(hi, v))
        except (TypeError, ValueError):
            return default

    return ExportUnits(
        mass_unit=_get_str("mass", "fg", MASS_UNITS.keys()),
        moles_unit=_get_str("moles", "fmol", MOLES_UNITS.keys()),
        diameter_unit=_get_str("diameter", "nm", DIAMETER_UNITS.keys()),
        number_format=_get_str("number_format", "decimal", NUMBER_FORMATS),
        mass_decimals=_get_int("mass_decimals", 4),
        moles_decimals=_get_int("moles_decimals", 6),
        diameter_decimals=_get_int("diameter_decimals", 2),
    )


def save_units(u: ExportUnits) -> None:
    """
    Args:
        u (ExportUnits): The u.
    Returns:
        None
    """
    s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    s.setValue(_KEY_PREFIX + "mass", u.mass_unit)
    s.setValue(_KEY_PREFIX + "moles", u.moles_unit)
    s.setValue(_KEY_PREFIX + "diameter", u.diameter_unit)
    s.setValue(_KEY_PREFIX + "number_format", u.number_format)
    s.setValue(_KEY_PREFIX + "mass_decimals", int(u.mass_decimals))
    s.setValue(_KEY_PREFIX + "moles_decimals", int(u.moles_decimals))
    s.setValue(_KEY_PREFIX + "diameter_decimals", int(u.diameter_decimals))


# --------------------------------------------------------------------------- #
# Advanced Options dialog
# --------------------------------------------------------------------------- #

def show_advanced_dialog(parent, current: ExportUnits) -> ExportUnits | None:
    """Open the Advanced Options dialog and return the updated ExportUnits,
    or None if the user cancels.  Saves to QSettings on OK.
    Args:
        parent (Any): Parent widget or object.
        current (ExportUnits): The current.
    Returns:
        ExportUnits | None: Result of the operation.
    """
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
        QComboBox, QSpinBox, QLabel, QDialogButtonBox, QPushButton,
    )
    from PySide6.QtCore import Qt
    from theme import theme, dialog_qss

    dlg = QDialog(parent)
    dlg.setWindowTitle("Advanced Export Options")
    dlg.setObjectName("advancedExportDialog")
    dlg.setMinimumWidth(440)

    def _apply(*_):
        """
        Args:
            *_ (Any): Additional positional arguments.
        """
        dlg.setStyleSheet(dialog_qss(theme.palette))
    _apply()
    theme.themeChanged.connect(_apply)
    dlg.destroyed.connect(lambda *_: theme.themeChanged.disconnect(_apply))

    root = QVBoxLayout(dlg)
    root.setContentsMargins(16, 16, 16, 16)
    root.setSpacing(14)

    intro = QLabel(
        "Choose the units and numeric format used in exported CSV files.\n"
        "Column headers will reflect your selected units."
    )
    intro.setWordWrap(True)
    intro.setStyleSheet(f"color: {theme.palette.text_secondary};")
    root.addWidget(intro)

    # ---- Units group ------------------------------------------------------
    units_group = QGroupBox("Units")
    units_form = QFormLayout()
    units_form.setContentsMargins(12, 10, 12, 12)
    units_form.setSpacing(10)
    units_form.setLabelAlignment(Qt.AlignLeft)

    mass_cb = QComboBox()
    mass_cb.addItems(MASS_UNITS.keys())
    mass_cb.setCurrentText(current.mass_unit)

    moles_cb = QComboBox()
    moles_cb.addItems(MOLES_UNITS.keys())
    moles_cb.setCurrentText(current.moles_unit)

    diameter_cb = QComboBox()
    diameter_cb.addItems(DIAMETER_UNITS.keys())
    diameter_cb.setCurrentText(current.diameter_unit)

    units_form.addRow("Mass:", mass_cb)
    units_form.addRow("Moles:", moles_cb)
    units_form.addRow("Diameter:", diameter_cb)
    units_group.setLayout(units_form)
    root.addWidget(units_group)

    # ---- Number format group ---------------------------------------------
    format_group = QGroupBox("Number Format")
    format_form = QFormLayout()
    format_form.setContentsMargins(12, 10, 12, 12)
    format_form.setSpacing(10)

    format_cb = QComboBox()
    format_cb.addItem("Decimal (e.g. 0.00012)",  "decimal")
    format_cb.addItem("Scientific (e.g. 1.2e-4)", "scientific")
    format_cb.setCurrentIndex(0 if current.number_format == "decimal" else 1)

    mass_dec = QSpinBox();  mass_dec.setRange(0, 12);  mass_dec.setValue(current.mass_decimals)
    moles_dec = QSpinBox(); moles_dec.setRange(0, 12); moles_dec.setValue(current.moles_decimals)
    dia_dec = QSpinBox();   dia_dec.setRange(0, 12);   dia_dec.setValue(current.diameter_decimals)

    format_form.addRow("Format:", format_cb)
    format_form.addRow("Mass decimals:", mass_dec)
    format_form.addRow("Moles decimals:", moles_dec)
    format_form.addRow("Diameter decimals:", dia_dec)
    format_group.setLayout(format_form)
    root.addWidget(format_group)

    # ---- Preview ----------------------------------------------------------
    preview_label = QLabel()
    preview_label.setStyleSheet(
        f"color: {theme.palette.text_secondary}; "
        f"background: {theme.palette.bg_tertiary}; "
        f"border: 1px solid {theme.palette.border}; "
        f"border-radius: 4px; padding: 8px;"
    )
    preview_label.setTextFormat(Qt.PlainText)
    root.addWidget(preview_label)

    def _update_preview(*_):
        """
        Args:
            *_ (Any): Additional positional arguments.
        """
        sample_mass_fg = 0.00012345
        sample_moles_fmol = 0.00000678
        sample_diameter_nm = 45.67
        u = ExportUnits(
            mass_unit=mass_cb.currentText(),
            moles_unit=moles_cb.currentText(),
            diameter_unit=diameter_cb.currentText(),
            number_format=format_cb.currentData(),
            mass_decimals=mass_dec.value(),
            moles_decimals=moles_dec.value(),
            diameter_decimals=dia_dec.value(),
        )
        preview_label.setText(
            "Preview:\n"
            f"  Mass      → {u.fmt_mass(sample_mass_fg)} {u.mass_label}\n"
            f"  Moles     → {u.fmt_moles(sample_moles_fmol)} {u.moles_label}\n"
            f"  Diameter  → {u.fmt_diameter(sample_diameter_nm)} {u.diameter_label}"
        )

    for w in (mass_cb, moles_cb, diameter_cb, format_cb):
        w.currentIndexChanged.connect(_update_preview)
    for w in (mass_dec, moles_dec, dia_dec):
        w.valueChanged.connect(_update_preview)
    _update_preview()

    # ---- Buttons ----------------------------------------------------------
    btn_row = QHBoxLayout()
    reset_btn = QPushButton("Reset to defaults")
    btn_row.addWidget(reset_btn)
    btn_row.addStretch()

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.button(QDialogButtonBox.Ok).setDefault(True)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    btn_row.addWidget(buttons)
    root.addLayout(btn_row)

    def _reset():
        defaults = ExportUnits()
        mass_cb.setCurrentText(defaults.mass_unit)
        moles_cb.setCurrentText(defaults.moles_unit)
        diameter_cb.setCurrentText(defaults.diameter_unit)
        format_cb.setCurrentIndex(0)
        mass_dec.setValue(defaults.mass_decimals)
        moles_dec.setValue(defaults.moles_decimals)
        dia_dec.setValue(defaults.diameter_decimals)
    reset_btn.clicked.connect(_reset)

    if dlg.exec() != QDialog.Accepted:
        return None

    updated = ExportUnits(
        mass_unit=mass_cb.currentText(),
        moles_unit=moles_cb.currentText(),
        diameter_unit=diameter_cb.currentText(),
        number_format=format_cb.currentData(),
        mass_decimals=mass_dec.value(),
        moles_decimals=moles_dec.value(),
        diameter_decimals=dia_dec.value(),
    )
    save_units(updated)
    return updated