# `unit.py`

Export unit definitions, formatting, and persistence (non-visual).

The Advanced Export Options *dialog* lives in ``tools/unit.py``; everything
here is pure logic + QSettings persistence so it can be used and tested
without constructing the GUI.

---

## Constants

| Name | Value |
|------|-------|
| `MASS_UNITS` | `{'ag': 1000.0, 'fg': 1.0, 'pg': 0.001, 'ng': 1e-06, 'µg':…` |
| `MOLES_UNITS` | `{'amol': 1000.0, 'fmol': 1.0, 'pmol': 0.001, 'nmol': 1e-0…` |
| `DIAMETER_UNITS` | `{'nm': 1.0, 'µm': 0.001}` |
| `NUMBER_FORMATS` | `('decimal', 'scientific')` |
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
| `_format` | `(self, value: float, decimals: int) → str` | Render a number in the user's chosen format. |
| `fmt_mass` | `(self, mass_fg: float) → str` | Format an internal fg mass in the user's chosen unit + format. |
| `fmt_moles` | `(self, moles_fmol: float) → str` |  |
| `fmt_diameter` | `(self, diameter_nm: float) → str` |  |
| `fmt_mass_or_zero` | `(self, mass_fg: float) → str` |  |
| `fmt_moles_or_zero` | `(self, moles_fmol: float) → str` |  |
| `fmt_diameter_or_zero` | `(self, diameter_nm: float) → str` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `load_units` | `() → ExportUnits` | Load the user's saved preferences, falling back to defaults for any |
| `save_units` | `(u: ExportUnits) → None` |  |
