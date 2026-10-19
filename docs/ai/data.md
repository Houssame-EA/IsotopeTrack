# `data.py`

The particle data the assistant works on, as one pandas table.

A canvas stream is a list of particle dictionaries. Small models make many
mistakes walking those nested dictionaries, so :class:`Dataset` turns the
stream into one row per particle with flat columns such as ``mass_fg_56Fe``,
and gathers what the main window knows about it: the samples, each run's
acquisition time and the calibrated detection limits.

Nothing here touches Qt, so it is cheap to test.

---

## Constants

| Name | Value |
|------|-------|
| `QUANTITIES` | `{'counts': 'elements', 'mass_fg': 'element_mass_fg', 'mol…` |
| `QUANTITY_UNITS` | `{'counts': 'counts', 'mass_fg': 'fg', 'moles_fmol': 'fmol…` |
| `QUANTITY_ALIASES` | `{'count': 'counts', 'signal': 'counts', 'intensity': 'cou…` |
| `LIMIT_KEYS` | `{'counts': 'counts', 'mass_fg': 'mass', 'diameter_nm': 'd'}` |
| `LIMIT_QUANTITIES` | `('counts', 'mass_fg', 'diameter_nm', 'particle_mass_fg', …` |
| `_HIDDEN_CONTEXT_KEYS` | `('parent_window', 'particle_data', 'acquisition')` |

## Classes

### `Dataset`

Everything the assistant knows about the connected particle stream.

The particle table and the summaries are built once and cached, so every
question in a conversation reuses them.

Attributes:
    particles (list): Raw particle dictionaries.
    kind (str): ``sample_data`` or ``multiple_sample_data``.
    sample_names (list): Samples in canvas order.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, data_context=None, parent_window=None)` | Wrap a canvas data context. |
| `__len__` | `(self)` | Return the number of particles. |
| `default_sample` | `(self)` | Name used for particles that do not carry a sample. |
| `df` | `(self)` | The particle table (see :func:`particle_frame`), built on first use. |
| `elements` | `(self)` | Detected isotope labels, most frequent first. |
| `samples` | `(self)` | Sample names, in canvas order first, then any others found. |
| `safe_context` | `(self)` | Return the data context without the main window or the raw particles. |
| `resolve_element` | `(self, name)` | Find the isotope label a user or model meant. |
| `column` | `(self, quantity, element)` | Return the column name for a quantity of an element. |
| `runs` | `(self)` | Acquisition span of each run, the base of the coincidence estimates. |
| `limits` | `(self)` | Calibrated detection limits, per element, quantity and sample. |
| `acquisition` | `(self)` | Raw signals and per-sample results, or ``None`` when there are none. |
| `set_limits` | `(self, limits)` | Replace the detection limits, mainly for tests and the benchmark. |
| `_add_particle_limits` | `(self, limits)` | Add the compound-corrected limits next to the element ones. |
| `lod` | `(self, element, quantity='mass_fg', sample=None)` | Detection limit of one element. |
| `concentrations_available` | `(self)` | Whether particle number concentrations can be computed. |
| `per_ml_factor` | `(self)` | Particles-per-mL factor of each sample, from the concentration metadata. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `resolve_quantity` | `(name)` | Map a loosely written quantity name to its canonical form. |
| `_float` | `(v)` | Return *v* as a float, or NaN when it is missing or not a number. |
| `_class_lookup` | `()` | Return the classifier's particle-to-class function, or ``None``. |
| `particle_frame` | `(particles, default_sample='Sample')` | Build one row per particle with flat per-element columns. |
| `_symbol` | `(label)` | Return the element symbol of an isotope label such as ``56Fe``. |
