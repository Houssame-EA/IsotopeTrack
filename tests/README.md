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
| `test_isobaric_correction.py` | `tools/isobaric_correction.py` | Overlap-correction arithmetic **and** the security whitelist of the free-text equation evaluator (rejects imports, attribute access, arbitrary calls). |
| `test_units.py` | `tools/unit.py` | Unit conversion factors and number formatting for exported masses, moles and sizes. |
| `test_dilution_utils.py` | `tools/dilution_utils.py` | Dilution-factor coercion and filename auto-detection (`*_50x`). |
| `test_atomic_notation_format.py` | `results/shared_plot_utils.py` | Isotope label formatting (pre-existing). |

## Notes / next steps

These cover pure, GUI-independent logic. Natural follow-ups that would add the
most value next:

- **Ionic calibration model selection** (`calibration_methods/ionic_CAL.py`) —
  verifying the automatic Simple/Intercept/Weighted linear choice and the R²
  computation against known fits.
- **Transport-efficiency methods** (`calibration_methods/TE_*.py`) — the
  mass-, number-, and weighted-liquid calculations against worked examples.
- **Project round-trip I/O** (`save_export/`) — save a project, reload it, and
  assert the data structures are identical.

These were left out here because they are more tightly coupled to the
`MainWindow` state; isolating them is worthwhile but is a larger refactor.
