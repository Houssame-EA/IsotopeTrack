# `interference_database.py`

ICP-MS Interference Database for spICP-ToF-MS

Comprehensive database of known spectral interferences including:
- Isobaric (same nominal mass from different elements)
- Polyatomic / Argide (ArO+, ArAr+, ArN+, ArCl+, etc.)
- Oxide (MO+, MOH+)
- Chloride (MCl+)
- Doubly-charged (M2+)
- Nitride / Hydride adducts

Used for:
1. Per-particle interference diagnosis
2. Smart isotope auto-selection (scoring function)
3. Visual warnings in periodic table and plots

References:
    May & Wiedmeyer, Atomic Spectroscopy 19(5), 150-155 (1998)
    Thomas, Practical Guide to ICP-MS, 3rd Ed. (2013)
    Balcaen et al., Anal. Chim. Acta 894, 7-19 (2015)

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
