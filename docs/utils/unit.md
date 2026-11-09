# `unit.py`

The app's display units: definitions, conversion, formatting and persistence.

Data is always computed and saved in the base units (fg, fmol, nm, ppb).
The units chosen by the user only change what is shown and exported. The
shared :data:`units` object holds the current choice for the whole app and
emits ``unitsChanged`` when it changes, so every window can redraw.

The Units *dialog* lives in ``tools/unit.py``.

---

## Constants

| Name | Value |
|------|-------|
| `MASS_UNITS` | `{'ag': 1000.0, 'fg': 1.0, 'pg': 0.001, 'ng': 1e-06, 'µg':…` |
| `MOLES_UNITS` | `{'amol': 1000.0, 'fmol': 1.0, 'pmol': 0.001, 'nmol': 1e-0…` |
| `DIAMETER_UNITS` | `{'nm': 1.0, 'µm': 0.001}` |
| `CONCENTRATION_UNITS` | `{'ppt': 1000.0, 'ppb': 1.0, 'ppm': 0.001, 'ng/L': 1000.0,…` |
| `NUMBER_FORMATS` | `('decimal', 'scientific')` |
| `BASE_UNITS` | `{'mass': 'fg', 'moles': 'fmol', 'diameter': 'nm', 'concen…` |
| `FACTORS` | `{'mass': MASS_UNITS, 'moles': MOLES_UNITS, 'diameter': DI…` |
| `_KIND_OF_TOKEN` | `{'fg': 'mass', 'fmol': 'moles', 'nm': 'diameter', 'ppb': …` |
| `_UNIT_TOKEN` | `re.compile('(?<![A-Za-zµ])(fg\|fmol\|nm\|ppb)(?![A-Za-z])')` |
| `PARTICLE_FIELDS` | `{'element_mass_fg': 'mass', 'particle_mass_fg': 'mass', '…` |
| `TOTAL_FIELDS` | `{'total_element_mass_fg': 'mass', 'total_particle_mass_fg…` |
| `_SETTINGS_ORG` | `'IsotopeTrack'` |
| `_SETTINGS_APP` | `'IsotopeTrack'` |
| `_KEY_PREFIX` | `'export/units/'` |

## Classes

### `ExportUnits`

Bundles the user's unit + formatting preferences.

Defaults reproduce the original hardcoded behaviour (fg / fmol / nm,
decimal notation, 4 decimals for mass, 6 for moles, 2 for diameter).

| Method | Signature | Description |
|--------|-----------|-------------|
| `mass_label` | `(self) → str` |  |
| `moles_label` | `(self) → str` |  |
| `diameter_label` | `(self) → str` |  |
| `concentration_label` | `(self) → str` |  |
| `unit` | `(self, kind: str) → str` | The chosen unit of *kind* (``mass``, ``moles``, ``diameter`` or ``concentration``). |
| `factor` | `(self, kind: str) → float` | Multiplier from the base unit of *kind* to the chosen unit. |
| `convert` | `(self, value, kind: str)` | *value* in the base unit of *kind*, returned in the chosen unit. |
| `to_base` | `(self, value, kind: str)` | *value* in the chosen unit of *kind*, returned in the base unit. |
| `relabel` | `(self, text)` | *text* with every base unit replaced by the chosen one. |
| `_format` | `(self, value: float, decimals: int) → str` | Render a number in the user's chosen format. |
| `fmt_mass` | `(self, mass_fg: float) → str` | Format an internal fg mass in the user's chosen unit + format. |
| `fmt_moles` | `(self, moles_fmol: float) → str` |  |
| `fmt_diameter` | `(self, diameter_nm: float) → str` |  |
| `fmt_concentration` | `(self, ppb: float) → str` | Format a ppb concentration in the user's chosen unit + format. |
| `fmt_mass_or_zero` | `(self, mass_fg: float) → str` | Format a mass, rendering anything non-positive as a plain "0". |
| `fmt_moles_or_zero` | `(self, moles_fmol: float) → str` | Format an amount, rendering anything non-positive as a plain "0". |
| `fmt_diameter_or_zero` | `(self, diameter_nm: float) → str` | Format a diameter, rendering non-positive values and NaN as "0". |

### `AppUnits` *(extends `QObject`)*

The units chosen for the whole app.

Read :attr:`current` (or use the shortcuts) to show a value; connect to
``unitsChanged`` to redraw when the user picks other units.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` |  |
| `current` | `(self) → ExportUnits` | The chosen units, loaded from the settings on first use. |
| `set` | `(self, u: ExportUnits) → None` | Choose *u* for the whole app, save it and tell every window. |
| `reload` | `(self) → None` | Read the choice from the settings again. |
| `unit` | `(self, kind: str) → str` | The chosen unit of *kind*. |
| `convert` | `(self, value, kind: str)` | *value* in the base unit of *kind*, returned in the chosen unit. |
| `to_base` | `(self, value, kind: str)` | *value* in the chosen unit of *kind*, returned in the base unit. |
| `relabel` | `(self, text)` | *text* with every base unit replaced by the chosen one. |
| `convert_for` | `(self, value, label)` | *value* converted by the kind named in *label* or data key, if any. |
| `setting_for` | `(self, value, data_type)` | A number typed for a figure of *data_type*, saved in the base unit, in the chosen unit. |
| `saved_for` | `(self, value, data_type)` | The reverse of :meth:`setting_for`: a number shown in the chosen unit, to save. |
| `base_label` | `(self, text)` | *text* with the chosen units put back to the base units. |
| `is_default` | `(self) → bool` | True when every chosen unit is the base unit, so nothing changes. |
| `convert_input` | `(self, input_data)` | Canvas data with every particle's masses, moles and diameters in the chosen units. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `kind_of` | `(text) → str \| None` | The kind of quantity a label or data key is in, from its base unit. |
| `_is_number` | `(v)` | True for a real number, numpy ones included, but not a bool. |
| `convert_particle` | `(particle, u)` | A copy of one particle dict with its unit fields in the units *u*. |
| `base_label` | `(text, u)` | *text* with the units of *u* put back to the base units. |
| `load_units` | `() → ExportUnits` | Load the user's saved preferences, falling back to defaults for any |
| `save_units` | `(u: ExportUnits) → None` |  |
