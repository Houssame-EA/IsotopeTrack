# Tests

Unit tests for IsotopeTrack, focused on the parts where a silent change would
quietly corrupt scientific results: the detection statistics, the isobaric
correction engine, unit conversions, and dilution handling.

## Running

From the repository root:

```bash
pip install -r requirements.txt -r requirements-test.txt
pytest
```

The suite runs headlessly — `tests/conftest.py` forces Qt into its `offscreen`
platform, so no display server is needed (this is what lets it run in CI).

Useful invocations:

```bash
pytest -v                              # verbose
pytest tests/test_isobaric_correction.py   # one file
pytest -k "quantile"                   # by keyword
pytest --cov=processing --cov=tools    # with coverage
```

## What's covered

| File | Module under test | Why it matters |
|------|-------------------|----------------|
| `test_peak_detection_math.py` | `processing/peak_detection.py` | The Compound Poisson Log-Normal statistics behind detection thresholds — checked against SciPy and closed-form properties. |
| `test_detection_threshold.py` | `processing/peak_detection.py` | `get_threshold` (the count above which a signal is called a particle), its cached variant, and peak-region splitting (`_assignments_to_regions`). |
| `test_isobaric_correction.py` | `tools/isobaric_correction.py` | Overlap-correction arithmetic **and** the security whitelist of the free-text equation evaluator (rejects imports, attribute access, arbitrary calls). |
| `test_transport_rate.py` | `calibration_methods/te_common.py` | Transport-efficiency math: sphere mass/volume, particle-number method, liquid-weight method. |
| `test_concentration.py` | `tools/dilution_utils.py` | The acquisition-time → volume → particles/mL chain, including dilution. |
| `test_dilution_utils.py` | `tools/dilution_utils.py` | Dilution-factor coercion and filename auto-detection (`*_50x`). |
| `test_formula_parsing.py` | `tools/mass_fraction_calculator.py` | Chemical-formula parsing (nested groups), GCD reduction, canonicalisation. |
| `test_particle_filter.py` | `tools/particle_filter.py` | Which particles pass a filter: AND/OR/EXACT composition, count operators, threshold gating. |
| `test_ionic_calibration.py` | `calibration_methods/ionic_CAL.py` | The three regression fits (force-zero, OLS, weighted), R², LOD/LOQ/BEC, and the best-R² model selection. |
| `test_project_io.py` | `save_export/fast_project_io.py`, `save_export/ionic_session.py` | Save/load round-trip of particle data (columnar ↔ dicts) and numpy→JSON conversion. |
| `test_units.py` | `tools/unit.py` | Unit conversion factors and number formatting for exported masses, moles and sizes. |
| `test_utils_sort.py` | `results/utils_sort.py` | Isotope ordering by mass and by symbol. |
| `test_atomic_notation_format.py` | `results/shared_plot_utils.py` | Isotope label formatting (pre-existing). |

## Notes / next steps

The original follow-ups are now covered:

- **Ionic calibration model selection** — `test_ionic_calibration.py` tests the
  three fits, R², LOD/LOQ/BEC and the best-R² choice. The fit methods are called
  via a small proxy object so no `QMainWindow` is constructed.
- **Transport-efficiency methods** — the number- and weight-based methods are in
  `test_transport_rate.py`; the mass-based method delegates to
  `particle_mass_from_diameter`, which is tested there too.
- **Project round-trip I/O** — `test_project_io.py` verifies the columnar
  save/load pair is a faithful round-trip, plus the numpy→JSON conversion.

Remaining higher-effort targets (need real GUI/window state, so they'd suit an
integration test rather than a unit test):

- End-to-end save/load through `ProjectManager` against a real `MainWindow`.
- The full `PeakDetection.detect()` pipeline on a synthetic signal trace.
