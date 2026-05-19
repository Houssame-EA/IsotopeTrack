# `unit.py`

---

## Constants

| Name | Value |
|------|-------|
| `MASS_UNITS` | `{'ag': 1000.0, 'fg': 1.0, 'pg': 0.001, 'ng': 1e...` |
| `MOLES_UNITS` | `{'amol': 1000.0, 'fmol': 1.0, 'pmol': 0.001, 'n...` |
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

### `load_units`

```python
def load_units() → ExportUnits
```

Load the user's saved preferences, falling back to defaults for any
missing / invalid values.

**Returns:**

- `ExportUnits: Result of the operation.`

### `save_units`

```python
def save_units(u: ExportUnits) → None
```


**Args:**

- `u (ExportUnits): The u.`

**Returns:**

- `None`

### `show_advanced_dialog`

```python
def show_advanced_dialog(parent, current: ExportUnits) → ExportUnits | None
```

Open the Advanced Options dialog and return the updated ExportUnits,
or None if the user cancels.  Saves to QSettings on OK.

**Args:**

- `parent (Any): Parent widget or object.`
- `current (ExportUnits): The current.`

**Returns:**

- `ExportUnits | None: Result of the operation.`
