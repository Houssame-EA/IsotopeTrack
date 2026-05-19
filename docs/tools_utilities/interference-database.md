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

### `get_interferences_for_mass`

```python
def get_interferences_for_mass(nominal_mass: int) → list
```

Get all known interferences for a given nominal mass.


**Args:**

- `nominal_mass: Integer nominal mass (e.g. 56 for 56Fe)`


**Returns:**

- `List of interference dicts, empty if none known`

### `get_particle_relevant_interferences`

```python
def get_particle_relevant_interferences(nominal_mass: int, elements_in_particle: Set[str]) → list
```

Get interferences that are plausible for a specific particle based on
which elements were co-detected.

Plasma-based interferences (ArO+, Ar2+, etc.) are always included.
Non-plasma interferences are only included if ALL required non-plasma
components are present in the particle.


**Args:**

- `nominal_mass: Integer nominal mass being evaluated`
- `elements_in_particle: Set of element symbols detected in this particle`


**Returns:**

- `List of plausible interference dicts`

### `get_worst_severity`

```python
def get_worst_severity(interferences: list) → str
```

Get the worst (most severe) interference severity from a list.


**Args:**

- `interferences: List of interference dicts`


**Returns:**

- `'critical', 'major', 'minor', or 'none'`

### `has_any_interference`

```python
def has_any_interference(nominal_mass: int) → bool
```

Quick check if a nominal mass has any known interferences.


**Args:**

- `nominal_mass: Integer nominal mass`


**Returns:**

- `True if interferences are known`

### `score_isotope`

```python
def score_isotope(mass: float, abundance: float, interferences: list, abundance_weight: float = 1.0, interference_weight: float = 50.0, min_abundance: float = 0.5) → float
```

Score an isotope for auto-selection. Higher score = better choice.

The score balances abundance (we want high signal) against interference
risk (we want clean measurements).

Score = abundance - (severity_penalty * interference_weight)

For isotopes below min_abundance, a heavy penalty is applied to avoid
selecting isotopes with too little signal.


**Args:**

- `mass: Exact isotope mass`
- `abundance: Natural abundance as percentage (0-100)`
- `interferences: List of interference dicts for this mass`
- `abundance_weight: Weight for abundance term (default 1.0)`
- `interference_weight: Penalty weight per interference (default 50.0)`
- `min_abundance: Minimum abundance % to consider (default 0.5)`


**Returns:**

- `Float score (higher is better)`

### `get_best_isotope`

```python
def get_best_isotope(element_data: dict, available_masses: list = None, abundance_weight: float = 1.0, interference_weight: float = 50.0, min_abundance: float = 0.5) → Optional[dict]
```

Select the best isotope for an element based on abundance and
interference scoring.


**Args:**

- `element_data: Element dict from PeriodicTableWidget containing`
- `'symbol', 'isotopes' list`
- `available_masses: Optional list of masses available in the data.`
- `If provided, only isotopes matching available masses are`
- `considered (tolerance 0.5 Da).`
- `abundance_weight: Weight for abundance in scoring`
- `interference_weight: Weight for interference penalty`
- `min_abundance: Minimum abundance to consider`


**Returns:**

- `Best isotope dict {'mass', 'abundance', 'label', 'score',`
- `'interferences'} or None if no isotopes available`

### `build_smart_preferred_isotopes`

```python
def build_smart_preferred_isotopes(elements_data: list, available_masses: list = None) → dict
```

Build a complete preferred isotopes dictionary using smart scoring.

This replaces the hardcoded PREFERRED_ISOTOPES dict in IsotopeDisplay.


**Args:**

- `elements_data: List of element dicts from PeriodicTableWidget`
- `available_masses: Optional list of available masses`


**Returns:**

- `Dict mapping element symbol to preferred isotope label string`
- `e.g. {'Ca': '44Ca', 'Fe': '57Fe', 'Au': '197Au'}`

### `get_isotope_interference_summary`

```python
def get_isotope_interference_summary(element_data: dict, available_masses: list = None) → list
```

Get a summary of all isotopes for an element with their interference
status, for display in the periodic table isotope panel.


**Args:**

- `element_data: Element dict from PeriodicTableWidget`
- `available_masses: Optional list of available masses`


**Returns:**

- `List of dicts with keys:`
- `mass, abundance, label, nominal_mass,`
- `has_interference, worst_severity, interferences, score`
- `Sorted by mass.`
