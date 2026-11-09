"""The app's display units: definitions, conversion, formatting and persistence.

Data is always computed and saved in the base units (fg, fmol, nm, ppb).
The units chosen by the user only change what is shown and exported. The
shared :data:`units` object holds the current choice for the whole app and
emits ``unitsChanged`` when it changes, so every window can redraw.

The Units *dialog* lives in ``tools/unit.py``.
"""
import numbers
import re
from dataclasses import dataclass

from PySide6.QtCore import QObject, QSettings, Signal

from utils.numeric_format import as_scalar
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

CONCENTRATION_UNITS = {
    "ppt":  1e3,
    "ppb":  1.0,
    "ppm":  1e-3,
    "ng/L": 1e3,
    "µg/L": 1.0,
    "mg/L": 1e-3,
}
"""Dissolved mass concentration, relative to ppb (1 ppb taken as 1 µg/L)."""

NUMBER_FORMATS = ("decimal", "scientific")

BASE_UNITS = {"mass": "fg", "moles": "fmol", "diameter": "nm", "concentration": "ppb"}
"""The unit every value is computed and saved in, by kind."""

FACTORS = {"mass": MASS_UNITS, "moles": MOLES_UNITS, "diameter": DIAMETER_UNITS,
           "concentration": CONCENTRATION_UNITS}


_KIND_OF_TOKEN = {"fg": "mass", "fmol": "moles", "nm": "diameter", "ppb": "concentration"}
_UNIT_TOKEN = re.compile(r"(?<![A-Za-zµ])(fg|fmol|nm|ppb)(?![A-Za-z])")


def kind_of(text) -> str | None:
    """The kind of quantity a label or data key is in, from its base unit.

    ``"Particle Mass (fg)"`` and ``"element_mass_fg"`` give ``"mass"``;
    a label without a base unit gives ``None``.
    """
    if not isinstance(text, str):
        return None
    m = _UNIT_TOKEN.search(text) or re.search(r"_(fg|fmol|nm|ppb)$", text)
    return _KIND_OF_TOKEN[m.group(1)] if m else None


PARTICLE_FIELDS = {
    "element_mass_fg": "mass", "particle_mass_fg": "mass", "mass_fg": "mass",
    "element_moles_fmol": "moles", "particle_moles_fmol": "moles",
    "element_diameter_nm": "diameter", "particle_diameter_nm": "diameter",
}
"""Per-element particle fields that carry a unit, by kind."""

TOTAL_FIELDS = {
    "total_element_mass_fg": "mass", "total_particle_mass_fg": "mass",
    "total_element_moles_fmol": "moles", "total_particle_moles_fmol": "moles",
}
"""Fields of a particle's ``totals`` that carry a unit, by kind."""


def _is_number(v):
    """True for a real number, numpy ones included, but not a bool."""
    return isinstance(v, numbers.Real) and not isinstance(v, bool)


def convert_particle(particle, u):
    """A copy of one particle dict with its unit fields in the units *u*."""
    if not isinstance(particle, dict):
        return particle
    out = dict(particle)
    for field, kind in PARTICLE_FIELDS.items():
        values = particle.get(field)
        if isinstance(values, dict):
            f = u.factor(kind)
            out[field] = {k: (v * f if _is_number(v) else v) for k, v in values.items()}
    totals = particle.get("totals")
    if isinstance(totals, dict):
        t = dict(totals)
        for field, kind in TOTAL_FIELDS.items():
            if _is_number(t.get(field)):
                t[field] = t[field] * u.factor(kind)
        out["totals"] = t
    return out


def base_label(text, u):
    """*text* with the units of *u* put back to the base units."""
    if not isinstance(text, str) or not text:
        return text
    chosen = {u.unit(k): BASE_UNITS[k] for k in BASE_UNITS if u.unit(k) != BASE_UNITS[k]}
    if not chosen:
        return text
    pattern = re.compile(r"(?<![A-Za-zµ])(" + "|".join(re.escape(c) for c in
                                                       sorted(chosen, key=len, reverse=True))
                         + r")(?![A-Za-z])")
    return pattern.sub(lambda m: chosen[m.group(0)], text)


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
    concentration_unit: str = "ppb"
    concentration_decimals: int = 5

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

    @property
    def concentration_label(self) -> str:
        return self.concentration_unit

    def unit(self, kind: str) -> str:
        """The chosen unit of *kind* (``mass``, ``moles``, ``diameter`` or ``concentration``)."""
        return {"mass": self.mass_unit, "moles": self.moles_unit,
                "diameter": self.diameter_unit,
                "concentration": self.concentration_unit}.get(kind, BASE_UNITS.get(kind, ""))

    def factor(self, kind: str) -> float:
        """Multiplier from the base unit of *kind* to the chosen unit."""
        table = FACTORS.get(kind)
        return table.get(self.unit(kind), 1.0) if table else 1.0

    def convert(self, value, kind: str):
        """*value* in the base unit of *kind*, returned in the chosen unit.

        Works on numbers, numpy arrays and lists; ``None`` stays ``None``.
        """
        if value is None:
            return None
        f = self.factor(kind)
        if isinstance(value, (list, tuple)):
            return type(value)(v * f if v is not None else None for v in value)
        return value * f

    def to_base(self, value, kind: str):
        """*value* in the chosen unit of *kind*, returned in the base unit."""
        if value is None:
            return None
        f = self.factor(kind)
        if isinstance(value, (list, tuple)):
            return type(value)(v / f if v is not None else None for v in value)
        return value / f

    def relabel(self, text):
        """*text* with every base unit replaced by the chosen one.

        ``"Element Mass (fg)"`` becomes ``"Element Mass (pg)"`` when the mass
        unit is pg; rates such as ``fg/mL`` follow too. Text without a base
        unit is returned unchanged.
        """
        if not isinstance(text, str) or not text:
            return text
        return _UNIT_TOKEN.sub(lambda m: self.unit(_KIND_OF_TOKEN[m.group(0)]), text)

    # ---- Formatters -------------------------------------------------- #
    def _format(self, value: float, decimals: int) -> str:
        """Render a number in the user's chosen format.

        The value is unwrapped with :func:`utils.numeric_format.as_scalar`
        first. Passing a numpy array straight to ``float()`` only works by way
        of a NumPy deprecation that is scheduled to become an error, and a
        multi-element array raises today.

        Args:
            value (float): Value to set or process.
            decimals (int): The decimals.
        """
        if value is None:
            return "0"
        try:
            v = float(as_scalar(value))
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

    def fmt_concentration(self, ppb: float) -> str:
        """Format a ppb concentration in the user's chosen unit + format."""
        return self._format(ppb * self.factor("concentration"), self.concentration_decimals)

    def fmt_mass_or_zero(self, mass_fg: float) -> str:
        """Format a mass, rendering anything non-positive as a plain "0"."""
        mass_fg = as_scalar(mass_fg)
        return self.fmt_mass(mass_fg) if mass_fg and mass_fg > 0 else "0"

    def fmt_moles_or_zero(self, moles_fmol: float) -> str:
        """Format an amount, rendering anything non-positive as a plain "0"."""
        moles_fmol = as_scalar(moles_fmol)
        return self.fmt_moles(moles_fmol) if moles_fmol and moles_fmol > 0 else "0"

    def fmt_diameter_or_zero(self, diameter_nm: float) -> str:
        """Format a diameter, rendering non-positive values and NaN as "0"."""
        diameter_nm = as_scalar(diameter_nm)
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
        concentration_unit=_get_str("concentration", "ppb", CONCENTRATION_UNITS.keys()),
        concentration_decimals=_get_int("concentration_decimals", 5),
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
    s.setValue(_KEY_PREFIX + "concentration", u.concentration_unit)
    s.setValue(_KEY_PREFIX + "concentration_decimals", int(u.concentration_decimals))


class AppUnits(QObject):
    """The units chosen for the whole app.

    Read :attr:`current` (or use the shortcuts) to show a value; connect to
    ``unitsChanged`` to redraw when the user picks other units.
    """

    unitsChanged = Signal(object)

    def __init__(self):
        super().__init__()
        self._current = None

    @property
    def current(self) -> ExportUnits:
        """The chosen units, loaded from the settings on first use."""
        if self._current is None:
            self._current = load_units()
        return self._current

    def set(self, u: ExportUnits) -> None:
        """Choose *u* for the whole app, save it and tell every window."""
        changed = u != self.current
        self._current = u
        save_units(u)
        if changed:
            self.unitsChanged.emit(u)

    def reload(self) -> None:
        """Read the choice from the settings again."""
        self._current = load_units()

    def unit(self, kind: str) -> str:
        """The chosen unit of *kind*."""
        return self.current.unit(kind)

    def convert(self, value, kind: str):
        """*value* in the base unit of *kind*, returned in the chosen unit."""
        return self.current.convert(value, kind)

    def to_base(self, value, kind: str):
        """*value* in the chosen unit of *kind*, returned in the base unit."""
        return self.current.to_base(value, kind)

    def relabel(self, text):
        """*text* with every base unit replaced by the chosen one."""
        return self.current.relabel(text)

    def convert_for(self, value, label):
        """*value* converted by the kind named in *label* or data key, if any."""
        kind = kind_of(label)
        return self.current.convert(value, kind) if kind else value

    def base_label(self, text):
        """*text* with the chosen units put back to the base units.

        The reverse of :meth:`relabel`: ``"Element Mass (pg)"`` gives back the
        saved key ``"Element Mass (fg)"`` when the mass unit is pg.
        """
        return base_label(text, self.current)

    def is_default(self) -> bool:
        """True when every chosen unit is the base unit, so nothing changes."""
        return all(self.current.factor(k) == 1.0 for k in FACTORS)

    def convert_input(self, input_data):
        """Canvas data with every particle's masses, moles and diameters in the chosen units.

        The particles are copied, so the main window's data stays in the base
        units. Data without particles, or with the base units chosen, is
        returned as it is.
        """
        if self.is_default() or not isinstance(input_data, dict):
            return input_data
        particles = input_data.get('particle_data')
        if not particles:
            return input_data
        out = dict(input_data)
        out['particle_data'] = [convert_particle(p, self.current) for p in particles]
        return out


units = AppUnits()
"""The units of the whole app."""
