# `mass_fraction_service.py`

This file contains code that help the Mass Fraction Calculator to share its
data with other parts of the code.

---

## Classes

### `MassFractionService`

Is the manager and provider for Mass Fractions data.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, periodic_table_info: PeriodicTableInfo)` |  |
| `set_element_infos` | `(self, mass_fractions: dict, densities: dict, molecular_weights: dict)` | Updates element level information. |
| `set_sample_infos` | `(self, mass_fractions: dict, densities: dict, molecular_weights: dict,` | Updates sample level information for selected samples |
| `get_mass_fraction` | `(self, element_key, sample_name=None)` | Get mass fraction for element in compound. |
| `get_molecular_weight` | `(self, element_key: str, sample_name: Optional[str]=None) → Optional[f` | Get molecular weight for element compound. |
| `get_element_density` | `(self, element_key: str, sample_name: Optional[str]=None) → Optional[f` | Get density for element compound. |
| `reset` | `(self)` | Resets all data structures of the service. |
| `add_fingerprint_to` | `(self, crypto)` | Adds the mass fraction's fingerprint to the updatable hash |
