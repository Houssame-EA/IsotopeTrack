# `isobaric_correction.py`

Isobaric correction engine for spICP-ToF-MS.

---

## Constants

| Name | Value |
|------|-------|
| `_CHANNEL_NAME_RE` | `re.compile('^(?:[A-Za-z]{1,3})(\\d{1,3})$')` |
| `_ALLOWED_BINOPS` | `(ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)` |
| `_ALLOWED_UNARYOPS` | `(ast.USub, ast.UAdd)` |
| `_TABLE_PATH` | `os.path.join(os.path.dirname(__file__), 'data', 'interfer…` |
| `_OVERRIDES_PATH` | `os.path.join(os.path.dirname(__file__), 'data', 'isobaric…` |

## Classes

### `IsobaricCorrection`

One TERM of a correction equation for an analyte channel.

| Method | Signature | Description |
|--------|-----------|-------------|
| `override_key` | `(self) → str` | Key identifying this analyte's custom equation in the overrides file. |
| `is_customized` | `(self) → bool` | True when this term differs from its table default (or is user-added). |
| `term_text` | `(self) → str` | Human-readable text for this single term, e.g. '− 0.2301 × Hg 202'. |
| `equation_text` | `(self) → str` | Human-readable single-term equation with the real numbers filled in. |

### `EquationCorrection`

A free-text correction equation for one analyte channel.

| Method | Signature | Description |
|--------|-----------|-------------|
| `override_key` | `(self) → str` | Key identifying this analyte's custom equation in the overrides file. |
| `is_customized` | `(self) → bool` | Free-text equations are by definition user customizations. |
| `equation_text` | `(self) → str` | Human-readable equation with the clamp made explicit. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_nominal` | `(mass: float) → int` | Return the nominal (integer) mass by rounding to the nearest integer. |
| `equation_text_for` | `(analyte_label: str, analyte_mass: float, terms: List['IsobaricCorrect` | Full multi-term equation text for one analyte channel. |
| `term_to_dict` | `(c: 'IsobaricCorrection') → dict` | Serialize one term for the overrides file. |
| `term_from_dict` | `(analyte_symbol: str, analyte_mass: float, analyte_label: str, d: dict` | Deserialize one term from the overrides file. |
| `_channel_nominal_from_name` | `(name: str) → Optional[int]` | Nominal mass encoded in a channel token, or None if not a channel token. |
| `_walk_expression` | `(expr: str) → Tuple[ast.Expression, List[str]]` | Parse an expression and verify every node is whitelisted. |
| `validate_expression` | `(expr: str, available_nominals: Optional[set]=None) → Tuple[bool, str,` | Check an equation expression for syntax and channel availability. |
| `_eval_node` | `(node, env: Dict[str, np.ndarray])` | Recursively evaluate a whitelisted AST node against the channel env. |
| `evaluate_equation` | `(eq: EquationCorrection, sample_data: Dict[float, np.ndarray], find_cl` | Evaluate a free-text equation for one sample. |
| `expression_from_terms` | `(terms: List[IsobaricCorrection]) → str` | Render a list of term objects as an editable expression string. |
| `_isotopes` | `(element_data: dict) → List[dict]` | Return the list of isotope dicts for an element, or an empty list if unavailable. |
| `_abundance_at` | `(element_data: dict, mass: float, tol: float=0.3) → float` | Abundance (percent) of the isotope nearest `mass`, by nominal mass. |
| `_isotope_dict_at` | `(element_data: dict, mass: float) → Optional[dict]` | Return the isotope dict whose nominal mass matches *mass*, or None if not found. |
| `correction_factor` | `(interferent_symbol: str, overlap_mass: float, monitor_mass: float, ge` | R = abundance(interferent @ overlap) / abundance(interferent @ monitor). |
| `apply_to_signal` | `(analyte_signal: np.ndarray, monitor_signal: np.ndarray, factor: float` | corrected = analyte - factor * monitor, clamped at 0. |
| `correct_sample_channels` | `(sample_data: Dict[float, np.ndarray], corrections: List[IsobaricCorre` | Return corrected copies of the analyte channels for one sample. |
| `load_overrides` | `(path: str=_OVERRIDES_PATH) → Dict[str, dict]` | Load persisted user overrides. |
| `save_overrides` | `(overrides: Dict[str, dict], path: str=_OVERRIDES_PATH) → None` | Persist user overrides to disk (atomic-ish write). |
| `monitor_candidates` | `(interferent_symbol: str, analyte_mass: float, get_element_by_symbol: ` | All isotopes of the interfering element usable as a monitor. |
| `load_table_corrections` | `(path: str=_TABLE_PATH) → List[dict]` | Load the empirical interference correction table from a JSON file. |
| `lookup_table_entry` | `(analyte_nominal: int, element_symbol: Optional[str]=None, path: str=_` | Return the table record for *analyte_nominal* mass, or None. |
| `build_table_corrections` | `(selected_isotopes: Dict[str, List[float]], available_masses: Optional` | Build IsobaricCorrection objects from the empirical reference table. |
| `default_table_terms` | `(analyte_symbol: str, analyte_mass: float, path: str=_TABLE_PATH) → Li` | The pristine table terms for one analyte (used by 'Reset to default'). |
