# `nu_blanking.py`

Blanker windows and autoblank periods of a Nu Vitesse acquisition.

Qt-free helpers used to tell the user which masses the instrument blanked:

* fixed windows set by the method (``Blanker<N>EdgeTimesNs`` in ``run.info``),
* extra windows closed by autoblanking during the run (``.autob`` files),
  with the fraction of the run each one lasted.

Edge times are converted to m/z with the blanker mass calibration
(``BlMassCalStartCoef`` / ``BlMassCalEndCoef``). With these coefficients the
start of a blanked window follows the end calibration and its end follows the
start calibration, which reproduces the method's ``SkipMassRanges``.

---

## Constants

| Name | Value |
|------|-------|
| `TICK_NS` | `1.25` |
| `MASS_TOL` | `0.5` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `edges_to_windows` | `(edges_ns, start_coef, end_coef)` | Blanked m/z windows from a list of blanker edge times. |
| `subtract_windows` | `(windows, remove)` | Parts of ``windows`` not covered by any window in ``remove``. |
| `_in_windows` | `(mass, windows)` |  |
| `read_nu_blanking` | `(folder)` | Fixed and autoblank windows of one Nu Vitesse folder. |
| `mass_flags` | `(masses, blanking)` | Blanking state of each mass. |
| `isotope_flag` | `(isotope_mass, flags, tol=MASS_TOL)` | Blanking state of the measured mass closest to an isotope. |
| `windows_text` | `(windows, low=1.0, high=300.0)` | Short text such as ``'m/z 27–33, 36.5–60'`` for windows inside a span. |
