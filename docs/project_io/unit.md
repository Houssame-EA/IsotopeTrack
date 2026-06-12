# `unit.py`

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

| Method | Signature | Description |
|--------|-----------|-------------|
| `mass_label` | `(self) → str` | Returns: |
| `moles_label` | `(self) → str` | Returns: |
| `diameter_label` | `(self) → str` | Returns: |
| `_format` | `(self, value: float, decimals: int) → str` | Render a number in the user's chosen format. |
| `fmt_mass` | `(self, mass_fg: float) → str` | Format an internal fg mass in the user's chosen unit + format. |
| `fmt_moles` | `(self, moles_fmol: float) → str` | Args: |
| `fmt_diameter` | `(self, diameter_nm: float) → str` | Args: |
| `fmt_mass_or_zero` | `(self, mass_fg: float) → str` | Args: |
| `fmt_moles_or_zero` | `(self, moles_fmol: float) → str` | Args: |
| `fmt_diameter_or_zero` | `(self, diameter_nm: float) → str` | Args: |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `load_units` | `() → ExportUnits` | Load the user's saved preferences, falling back to defaults for any |
| `save_units` | `(u: ExportUnits) → None` | Args: |
| `show_advanced_dialog` | `(parent, current: ExportUnits) → ExportUnits \| None` | Open the Advanced Options dialog and return the updated ExportUnits, |
