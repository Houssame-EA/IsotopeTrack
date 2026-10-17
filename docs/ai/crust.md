# `crust.py`

Upper continental crust composition, used to compare element ratios with crustal values.

Values are mass fractions in ppm (ug/g) from Rudnick & Gao, "Composition of
the Continental Crust", Treatise on Geochemistry (2003, vol. 3, 1-64;
2nd edition 2014, vol. 4, 1-51), table of the upper continental crust.
Major elements given there as oxides (SiO2, Al2O3, FeO total, MnO, MgO,
CaO, Na2O, TiO2, K2O, P2O5) are converted to the element.

---

## Constants

| Name | Value |
|------|-------|
| `REFERENCE` | `'Rudnick & Gao (2003, 2014), upper continental crust'` |
| `SHORT_REFERENCE` | `'Rudnick & Gao'` |
| `UCC_PPM` | `{'Si': 311300.0, 'Al': 81510.0, 'Fe': 39180.0, 'Mn': 774.…` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `crust_ppm` | `(symbol)` | Upper-crust abundance of an element in ppm, or None when not tabulated. |
| `crust_mass_ratio` | `(a, b)` | Mass ratio a/b in the upper crust, or None when either is not tabulated. |
