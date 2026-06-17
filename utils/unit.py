"""Export unit definitions, formatting, and persistence (non-visual).

The Advanced Export Options *dialog* lives in ``tools/unit.py``; everything
here is pure logic + QSettings persistence so it can be used and tested
without constructing the GUI.
"""
from dataclasses import dataclass
from PySide6.QtCore import QSettings
import logging
_itk_log = logging.getLogger("IsotopeTrack.utils.unit")


# --------------------------------------------------------------------------- #
# Unit factor tables
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
        return self.mass_unit

    @property
    def moles_label(self) -> str:
        return self.moles_unit

    @property
    def diameter_label(self) -> str:
        return self.diameter_unit

    # ---- Formatters -------------------------------------------------- #
    def _format(self, value: float, decimals: int) -> str:
        """Render a number in the user's chosen format.
        Args:
            value (float): Value to set or process.
            decimals (int): The decimals.
        """
        if value is None:
            return "0"
        try:
            v = float(value)
        except (TypeError, ValueError):
            _itk_log.exception("Handled exception in _format")
            return "0"
        if self.number_format == "scientific":
            return f"{v:.{decimals}e}"
        return f"{v:.{decimals}f}"

    def fmt_mass(self, mass_fg: float) -> str:
        """Format an internal fg mass in the user's chosen unit + format."""
        factor = MASS_UNITS.get(self.mass_unit, 1.0)
        return self._format(mass_fg * factor, self.mass_decimals)

    def fmt_moles(self, moles_fmol: float) -> str:
        factor = MOLES_UNITS.get(self.moles_unit, 1.0)
        return self._format(moles_fmol * factor, self.moles_decimals)

    def fmt_diameter(self, diameter_nm: float) -> str:
        factor = DIAMETER_UNITS.get(self.diameter_unit, 1.0)
        return self._format(diameter_nm * factor, self.diameter_decimals)

    def fmt_mass_or_zero(self, mass_fg: float) -> str:
        return self.fmt_mass(mass_fg) if mass_fg and mass_fg > 0 else "0"

    def fmt_moles_or_zero(self, moles_fmol: float) -> str:
        return self.fmt_moles(moles_fmol) if moles_fmol and moles_fmol > 0 else "0"

    def fmt_diameter_or_zero(self, diameter_nm: float) -> str:
        if not diameter_nm or diameter_nm <= 0:
            return "0"
        try:
            if diameter_nm != diameter_nm:
                return "0"
        except Exception:
            _itk_log.exception("Handled exception in fmt_diameter_or_zero")
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
    """
    s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)

    def _get_str(key, default, valid):
        v = s.value(_KEY_PREFIX + key, default)
        return v if v in valid else default

    def _get_int(key, default, lo=0, hi=12):
        try:
            v = int(s.value(_KEY_PREFIX + key, default))
            return max(lo, min(hi, v))
        except (TypeError, ValueError):
            _itk_log.exception("Handled exception in _get_int")
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
    s = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
    s.setValue(_KEY_PREFIX + "mass", u.mass_unit)
    s.setValue(_KEY_PREFIX + "moles", u.moles_unit)
    s.setValue(_KEY_PREFIX + "diameter", u.diameter_unit)
    s.setValue(_KEY_PREFIX + "number_format", u.number_format)
    s.setValue(_KEY_PREFIX + "mass_decimals", int(u.mass_decimals))
    s.setValue(_KEY_PREFIX + "moles_decimals", int(u.moles_decimals))
    s.setValue(_KEY_PREFIX + "diameter_decimals", int(u.diameter_decimals))
