# `synthetic.py`

Synthetic spICP-ToF-MS particle streams with known ground truth.

Used by the tests and by :mod:`results.ai.benchmark`. Each element's
particles arrive as an independent Poisson process with a log-normal size
distribution; events that overlap in time merge into one multi-element
event, exactly as two particles hitting the plasma together would. Anything
planted on top, a real Ce+La association, an Ag+Au alloy population, a
contamination burst, a sample whose Ce-La particles have another
composition, or a sample with non-natural Pb isotopes, is listed in
:class:`Truth`.

---

## Constants

| Name | Value |
|------|-------|
| `DENSITY` | `{'48Ti': 4.23, '56Fe': 5.24, '140Ce': 7.22, '139La': 6.51…` |
| `MOLAR` | `{'48Ti': 47.95, '56Fe': 55.93, '140Ce': 139.9, '139La': 1…` |
| `SENSITIVITY` | `{'48Ti': 60.0, '56Fe': 45.0, '140Ce': 900.0, '139La': 850…` |
| `PB_NATURAL` | `1.0934` |
| `PB_SHIFTED` | `0.93` |
| `LA_CE_SHIFTED` | `1.0` |
| `LA_CE_SLOPE_SHIFTED` | `0.7` |
| `LOD_MASS_FG` | `{'48Ti': 0.12, '56Fe': 0.15, '140Ce': 0.02, '139La': 0.02…` |

## Classes

### `Truth`

What was planted in a synthetic stream.

Attributes:
    samples (list): Sample names in order.
    span_s (float): Acquisition time of each run.
    ti_median_nm (dict): Median Ti diameter used per sample.
    burst (tuple): ``(sample, t_from, t_to)`` of the Fe contamination burst.
    alloy_sample (str): The only sample holding Ag+Au particles.
    lod_mass_fg (dict): Mass detection limit per element.
    associated (tuple): The element pair planted as one particle type.
    chance_pair (tuple): A pair that only meets by coincidence.
    cela_shift_sample (str): Sample whose Ce-La particles have another
        La/Ce ratio and La growing more slowly than Ce.
    pb_sample (str): Sample whose lead has a non-natural 206Pb/207Pb ratio.

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `planted_defaults` | `(samples, alloy_sample)` | Which samples get the shifted Ce-La particles and the non-natural lead. |
| `_mass_fg` | `(d_nm, rho)` | Mass in fg of a sphere of diameter *d_nm* and density *rho*. |
| `_diameter_nm` | `(mass_fg, rho)` | Diameter in nm of a sphere of mass *mass_fg* and density *rho*. |
| `_arrivals` | `(rng, rate, span, start=0.0)` | Poisson arrival times over ``[start, start + span)``. |
| `_events` | `(rng, sample, truth, scale)` | Draw the single-particle events of one sample before merging. |
| `_merge` | `(events)` | Merge events whose time windows overlap into multi-element events. |
| `_particle` | `(sample, t0, t1, comp, rng, lod)` | Build a particle dictionary shaped like the app's, or ``None`` below LOD. |
| `make_dataset` | `(seed=11, scale=1.0)` | Generate a three-sample stream and the truth behind it. |
