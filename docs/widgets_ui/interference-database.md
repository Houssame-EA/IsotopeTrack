# `interference_database.py`

ICP-MS Interference Database for spICP-ToF-MS

---

## Constants

| Name | Value |
|------|-------|
| `PLASMA_SPECIES` | `frozenset({'Ar', 'O', 'N', 'H', 'C'})` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `get_interferences_for_mass` | `(nominal_mass: int) → list` | Get all known interferences for a given nominal mass. |
| `get_particle_relevant_interferences` | `(nominal_mass: int, elements_in_particle: Set[str]) → list` | Get interferences that are plausible for a specific particle based on |
| `get_worst_severity` | `(interferences: list) → str` | Get the worst (most severe) interference severity from a list. |
| `has_any_interference` | `(nominal_mass: int) → bool` | Quick check if a nominal mass has any known interferences. |
| `score_isotope` | `(mass: float, abundance: float, interferences: list, abundance_weight:` | Score an isotope for auto-selection. Higher score = better choice. |
| `get_best_isotope` | `(element_data: dict, available_masses: list=None, abundance_weight: fl` | Select the best isotope for an element based on abundance and |
| `build_smart_preferred_isotopes` | `(elements_data: list, available_masses: list=None) → dict` | Build a complete preferred isotopes dictionary using smart scoring. |
| `get_isotope_interference_summary` | `(element_data: dict, available_masses: list=None) → list` | Get a summary of all isotopes for an element with their interference |
