"""End-to-end export tests that reproduce the reported Chinese-Windows crash.

The two failures were reported against a real project, so these tests drive the
real writers — :func:`export_summary_file_with_mass_fractions` and
:func:`export_sample_file_with_mass_fractions` — against a minimal stand-in for
MainWindow that carries the values that broke them:

* calibration slopes, thresholds and backgrounds stored as numpy arrays rather
  than scalars, which is what a moving-window background produces;
* element labels and unit headers containing 'µ' and '³', which have no cp936
  mapping.

Before the fix the sample writer raised ``TypeError: unsupported format string
passed to numpy.ndarray.__format__`` and, on a GBK system, both writers raised
``UnicodeEncodeError``.
"""
import numpy as np
import pytest

pytest.importorskip("PySide6.QtWidgets")

from save_export.export_utils import (  # noqa: E402
    export_sample_file_with_mass_fractions,
    export_summary_file_with_mass_fractions,
)
from utils.unit import ExportUnits  # noqa: E402

SAMPLE = "测试样品 µ³"
ELEMENT_KEY = "Ag-106.9051"
DISPLAY_LABEL = "¹⁰⁷Ag"
ALL_ELEMENTS = [(ELEMENT_KEY, DISPLAY_LABEL, "Ag", 106.9051, 106.9051)]


class _FakeMassFractionService:
    """Mass fractions for a single non-pure element.

    A non-pure fraction is used deliberately: it drives the ``use_particle_calc``
    branch of both writers, which is where the compound density and molecular
    weight lookups happen.
    """

    def __init__(self):
        self.element_mass_fractions = {"Ag": 0.87}
        self.element_densities = {"Ag": 5.6}
        self.element_molecular_weights = {"Ag": 187.77}
        self.sample_mass_fractions = {SAMPLE: {"Ag": 0.87}}
        self.sample_densities = {SAMPLE: {"Ag": 5.6}}
        self.sample_molecular_weights = {SAMPLE: {"Ag": 187.77}}

    def get_mass_fraction(self, element_key, sample_name=None):
        """Return the mass fraction for an element key."""
        return 0.87

    def get_molecular_weight(self, element_key, sample_name=None):
        """Return the compound molecular weight in g/mol."""
        return 187.77

    def get_element_density(self, element_key, sample_name=None):
        """Return the compound density in g/cm³."""
        return 5.6


class _FakePeriodicTable:
    """Minimal periodic table covering the one element under test."""

    def element_exists(self, element):
        """Report whether the element is known."""
        return element == "Ag"

    def get_density_by_element(self, element):
        """Return the pure-element density in g/cm³."""
        return 10.49 if element == "Ag" else None


class _FakeMainWindow:
    """Stand-in for MainWindow exposing only what the export writers read.

    Every quantity the writers format is stored as a numpy array here, not a
    float. That is the whole point of the fixture: a scalar-only fake would
    pass against the unfixed code.
    """

    def __init__(self):
        self.mass_fraction_service = _FakeMassFractionService()
        self.periodic_table_info = _FakePeriodicTable()

        self.average_transport_rate = np.array([12.5])
        self.sample_dwell_times = {SAMPLE: np.array([1.0])}
        self.sample_analysis_dates = {SAMPLE: {"date": "2026-06-25",
                                               "time": "22:05:07"}}

        self.calibration_results = {
            "Ionic Calibration": {
                ELEMENT_KEY: {
                    "zero": {
                        "slope": np.array([1234.5]),
                        "intercept": 0.0,
                        "r_squared": np.array([0.9987]),
                        "lod": np.array([0.31]),
                        "loq": np.array([1.03]),
                        "bec": np.array([0.12]),
                        "density": 10.49,
                    }
                }
            }
        }
        self.isotope_method_preferences = {ELEMENT_KEY: "Force through zero"}

        self.element_thresholds = {
            SAMPLE: {
                ELEMENT_KEY: {
                    "threshold": np.linspace(4.0, 6.0, 64),
                    "background": np.linspace(1.0, 2.0, 64),
                    "LOD_counts": np.array([5.0]),
                    "LOD_MDL": np.array([3.5]),
                }
            }
        }
        self.element_limits = {
            SAMPLE: {
                ELEMENT_KEY: {
                    "MDL": np.array([0.02]),
                    "MQL": np.array([0.07]),
                    "background_ppt": np.array([0.834]),
                    "background_sd_ppt": np.array([0.091]),
                }
            }
        }

        self.sample_parameters = {
            SAMPLE: {ELEMENT_KEY: {"include": True, "sigma": 0.55,
                                   "use_window_size": True, "window_size": 5000}}
        }
        self._sigma_mode = "global"
        self._global_sigma = np.array([0.55])

        peak = {"total_counts": np.array([420.0]), "left_idx": 0, "right_idx": 3}
        self.sample_detected_peaks = {SAMPLE: {("Ag", 106.9051): [peak, peak]}}
        self.sample_particle_data = {
            SAMPLE: [
                {"start_time": np.array([0.0125]),
                 "end_time": np.array([0.0131]),
                 "elements": {DISPLAY_LABEL: np.array([420.0])}},
                {"start_time": np.array([0.0400]),
                 "end_time": np.array([0.0406]),
                 "elements": {DISPLAY_LABEL: np.array([610.0])}},
            ]
        }

    def effective_volume_ml(self, sample_name):
        """Return the analysed volume in mL."""
        return 0.75

    def mass_to_diameter(self, mass_fg, density):
        """Convert a mass in fg to a spherical-equivalent diameter in nm."""
        volume_cm3 = float(np.asarray(mass_fg).mean()) * 1e-15 / float(density)
        return (6.0 * volume_cm3 / np.pi) ** (1.0 / 3.0) * 1e7


@pytest.fixture
def main_window():
    """A fake project whose every numeric field is a numpy array."""
    return _FakeMainWindow()


def test_sample_file_exports_with_array_valued_fields(main_window, tmp_path):
    """The reported crash: per-particle files must now write.

    Every field the sample writer formats is an array in the fixture, so this
    fails with ``unsupported format string passed to numpy.ndarray.__format__``
    against the unfixed writer.
    """
    path = tmp_path / "sample_results.csv"
    export_sample_file_with_mass_fractions(
        main_window, SAMPLE, str(path), ALL_ELEMENTS,
        main_window.calibration_results["Ionic Calibration"],
        main_window.element_thresholds[SAMPLE],
        dilution_factor=2.0, data_type="particle", units=ExportUnits(),
    )
    text = path.read_text(encoding="utf-8")
    assert "Results:" in text
    assert "µL/s" in text
    assert "g/cm³" in text


def test_sample_file_writes_every_particle_row(main_window, tmp_path):
    """The per-particle block must contain one row per particle, with values.

    Guards against a fix that merely swallows the error and emits 'N/A'
    everywhere.
    """
    path = tmp_path / "sample_results.csv"
    export_sample_file_with_mass_fractions(
        main_window, SAMPLE, str(path), ALL_ELEMENTS,
        main_window.calibration_results["Ionic Calibration"],
        main_window.element_thresholds[SAMPLE],
        dilution_factor=2.0, data_type="particle", units=ExportUnits(),
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    start = lines.index("Results:")
    rows = [ln for ln in lines[start + 2:] if ln.strip()]
    assert len(rows) == 2
    assert rows[0].startswith("1,0.012500,0.013100")
    assert rows[1].startswith("2,0.040000,0.040600")
    assert "420.0000" in rows[0]
    assert "610.0000" in rows[1]


def test_calibration_block_renders_array_slopes_as_numbers(main_window, tmp_path):
    """Slope, R² and the limits must be real numbers, not the fallback."""
    path = tmp_path / "sample_results.csv"
    export_sample_file_with_mass_fractions(
        main_window, SAMPLE, str(path), ALL_ELEMENTS,
        main_window.calibration_results["Ionic Calibration"],
        main_window.element_thresholds[SAMPLE],
        dilution_factor=2.0, data_type="particle", units=ExportUnits(),
    )
    text = path.read_text(encoding="utf-8")
    assert "1.23e+03" in text
    assert "0.998700" in text
    assert "0.83400" in text
    assert "Transport Rate: 12.5000 µL/s" in text


def test_window_mode_arrays_collapse_to_their_mean(main_window, tmp_path):
    """A full-length window-mode threshold must summarise, not abort.

    ``threshold`` spans 4.0–6.0 and ``background`` 1.0–2.0, so the file should
    carry their means rather than a formatting failure. The values here come
    from ``LOD_counts`` and ``LOD_MDL``, which the detection engine already
    stores as the window means.
    """
    path = tmp_path / "sample_results.csv"
    export_sample_file_with_mass_fractions(
        main_window, SAMPLE, str(path), ALL_ELEMENTS,
        main_window.calibration_results["Ionic Calibration"],
        main_window.element_thresholds[SAMPLE],
        dilution_factor=2.0, data_type="particle", units=ExportUnits(),
    )
    text = path.read_text(encoding="utf-8")
    assert "5.00" in text
    assert "3.50" in text
    assert "N/A,N/A,N/A,N/A,N/A" not in text


def test_summary_file_exports_with_array_valued_fields(main_window, tmp_path):
    """The summary writer must survive the same fixture."""
    path = tmp_path / "summary_results.csv"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        export_summary_file_with_mass_fractions(
            main_window, fh, [SAMPLE], ALL_ELEMENTS, [DISPLAY_LABEL],
            {SAMPLE: 2.0}, "particle", units=ExportUnits(),
        )
    text = path.read_text(encoding="utf-8")
    assert "IsotopeTrack Summary Results" in text
    assert SAMPLE in text


def test_exported_files_are_utf8_not_the_ansi_code_page(main_window, tmp_path):
    """Bytes on disk must be UTF-8 regardless of the machine's locale.

    Decoding as cp936 either fails or yields mojibake, which is exactly what a
    Chinese-Windows user saw before the fix.
    """
    path = tmp_path / "sample_results.csv"
    export_sample_file_with_mass_fractions(
        main_window, SAMPLE, str(path), ALL_ELEMENTS,
        main_window.calibration_results["Ionic Calibration"],
        main_window.element_thresholds[SAMPLE],
        dilution_factor=2.0, data_type="particle", units=ExportUnits(),
    )
    raw = path.read_bytes()
    assert "µL/s".encode("utf-8") in raw
    assert raw.decode("utf-8")


def test_sample_name_with_chinese_characters_round_trips(main_window, tmp_path):
    """A Simplified Chinese sample name must survive the write."""
    path = tmp_path / "sample_results.csv"
    export_sample_file_with_mass_fractions(
        main_window, SAMPLE, str(path), ALL_ELEMENTS,
        main_window.calibration_results["Ionic Calibration"],
        main_window.element_thresholds[SAMPLE],
        dilution_factor=2.0, data_type="particle", units=ExportUnits(),
    )
    assert f"Sample: {SAMPLE}" in path.read_text(encoding="utf-8")
