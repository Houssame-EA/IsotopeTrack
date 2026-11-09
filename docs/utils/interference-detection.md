# `interference_detection.py`

Blind interference detection for spICP-ToF-MS spectra.

Pure logic: numpy only, no GUI. Element data (isotope masses and abundances)
is passed in as the same list of element dicts PeriodicTableWidget provides.

The sample composition is not needed. It is found from the spectrum itself:

1. ``nominal_spectrum`` sums the signal of every nominal mass, from the
   integrated data or from the resolved ``.raw`` spectrum.
2. ``identify_elements`` explains that spectrum as a non-negative sum of
   element patterns. Each pattern holds the natural isotopes, the oxide MO+
   at +16 and the doubly charged ion M2+ at half mass, with rates from
   ``data/interference_reference.json`` (measured with single-element
   standards). The oxide level of each element is fitted per sample,
   because it changes with plasma conditions. An element is kept only when
   it is statistically significant (Poisson), and, when a blank is given,
   significantly above the blank; elements only as high as in the blank are
   reported as background.
3. ``contributions`` splits the signal at one nominal mass between the
   selected isotope and every other species of the identified elements.
4. ``mass_offset`` and ``position_match`` use the resolved spectrum: after
   the calibration offset is measured on clean peaks, the peak centre tells
   which species of that nominal mass really forms the peak.
5. ``check_isotope`` combines both into rows for the Spectrum view.

---

## Constants

| Name | Value |
|------|-------|
| `OXYGEN` | `15.99491` |
| `REFERENCE_FILE` | `os.path.join(os.path.dirname(os.path.dirname(os.path.absp…` |
| `NOT_ANALYTES` | `frozenset({'H', 'He', 'Li', 'Be', 'B', 'C', 'N', 'O', 'F'…` |
| `NOBLE_GASES` | `frozenset({'He', 'Ne', 'Ar', 'Kr', 'Xe', 'Rn'})` |
| `PLASMA_SPECIES` | `frozenset({'Ar', 'O', 'N', 'H', 'C'})` |
| `PLASMA_MASSES` | `frozenset({23, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38…` |
| `OXIDE_SCALES` | `(0.3, 0.45, 0.6, 0.75, 0.9, 1.0, 1.2, 1.5)` |
| `Z_MIN` | `5.0` |
| `MODEL_ERROR` | `0.05` |
| `MOLECULAR_ERROR` | `0.5` |
| `MIN_ELEMENT_IONS` | `20.0` |
| `MIN_IONS` | `50` |
| `TIE_DA` | `0.005` |
| `SUPERSCRIPT` | `str.maketrans('0123456789+', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺')` |
| `BLANK_NAME` | `re.compile('blan[kc]\|mqw\|milli[\\s_-]?q', re.IGNORECASE)` |

## Classes

### `Identification`

Elements found in one spectrum and how they explain it.

``amounts`` holds the elements significantly above zero, or above the
blank when one was given. ``background`` lists elements that are present
but not above the blank. ``significance`` is the fitted amount divided by
its Poisson uncertainty.

| Method | Signature | Description |
|--------|-----------|-------------|
| `residual` | `(self, nominal: int) → float` | Signal at a nominal mass that no identified species explains. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `sup` | `(number) → str` | Return a number written in superscript digits. |
| `load_reference` | `(path: Optional[str]=None) → dict` | Read the measured MO+, MOH+, M2+ and MH+ rates. |
| `isotope_table` | `(elements: Sequence[dict]) → Dict[str, List[Tuple[int, float, float]]]` | Return ``{symbol: [(nominal, exact mass, fraction), ...]}`` for natural isotopes. |
| `nominal_spectrum` | `(masses, values) → Dict[int, float]` | Sum signals by nominal mass. |
| `nominal_spectrum_from_raw` | `(masses, spectrum, windows, single_ion_area=None) → Dict[int, float]` | Sum a resolved spectrum inside each integration window. |
| `_nnls` | `(A: np.ndarray, b: np.ndarray, max_iter: int=5000) → np.ndarray` | Solve min \|\|Ax - b\|\| with x >= 0 (Lawson-Hanson active set). |
| `_rate` | `(reference: dict, symbol: str, kind: str) → float` | Return the reference rate of one species, or the default. |
| `_species_signals` | `(symbol, amount, isotopes, reference, oxide_scale, usable)` | Yield ``(nominal, label, kind, signal)`` for every species of one element. |
| `_design_parts` | `(usable, table, symbols, reference)` | Return the element patterns split into a fixed part and the oxide part. |
| `_fit` | `(values, variance, usable, table, symbols, reference, molecular_error=` | Fit element patterns to a spectrum and return the oxide scales, amounts and z-scores. |
| `_doubly_charged` | `(usable, table, symbols, reference)` | Return the doubly charged part of the element patterns. |
| `identify_elements` | `(measured: Dict[int, float], elements: Sequence[dict], reference: Opti` | Find which elements explain a nominal-mass spectrum, without prior knowledge. |
| `contributions` | `(ident: Identification, nominal: int) → List[Tuple[str, str, str, floa` | Return ``(element, label, kind, share)`` of every species at a nominal mass. |
| `database_species` | `(nominal: int, present: Optional[Sequence[str]]=None) → List[Tuple[str` | Polyatomic ions of the interference database at a nominal mass. |
| `candidate_species` | `(nominal: int, table: Dict[str, List[Tuple[int, float, float]]], prese` | List every ion that can sit at a nominal mass, with its exact m/z. |
| `is_blank_name` | `(name: str) → bool` | Whether a sample name says it is a blank (Blank, Blanc, MQW, Milli-Q). |
| `analysis_time` | `(run_info: Optional[dict]) → Optional[float]` | Return the run's analysis time from ``run.info`` as a timestamp, or None. |
| `pick_blank` | `(sample: str, run_infos: Dict[str, dict]) → Optional[str]` | Choose the blank to compare a sample with: the blank run closest in time. |
| `default_elements` | `() → List[dict]` | Element data of the app's periodic table, read once. |
| `identify_run` | `(entry: Optional[dict], run_info: dict, elements: Optional[Sequence[di` | Identify the elements of one Nu run from its summed raw snapshots. |
| `peak_centre` | `(masses, spectrum, target, half_width=0.4, single_ion_area=None)` | Return ``(centre, ions)`` of the strongest peak near a mass, or None. |
| `mass_offset` | `(masses, spectrum, ident: Identification, table, single_ion_area=None,` | Measure the calibration offset of the resolved spectrum on clean peaks. |
| `position_match` | `(centre: float, offset: float, candidates) → List[Tuple[str, float, st` | Rank candidate ions by distance between their m/z and the corrected centre. |
| `check_isotope` | `(symbol: str, isotope_mass: float, ident: Optional[Identification], el` | Build the interference check of one isotope. |
