# `spectrum.py`

Interferences seen in the resolved mass spectrum of Nu runs.

Nu Instruments software writes a few raw digitizer snapshots per run, and
their sum is a resolved spectrum (see :mod:`loading.nu_raw_spectrum`). Around
each selected isotope this module looks for two signs that something other
than the isotope adds counts to its integration window:

* the peak sits off the isotope's exact mass, toward a known interfering
  species. Every peak of a run shares the run's mass calibration error, so
  the median offset of all well-measured peaks is removed first and only what
  is left counts as a shift;
* a second, partly resolved peak sits inside or right next to the
  integration window.

A third check says how much of each isotope's signal other species make.
The elements of the sample are identified from the spectrum itself, against
the closest blank when one is loaded, with
:func:`utils.interference_detection.identify_run`, the same identification the
Spectrum view shows, so both always agree. Candidate species (isobars, oxides
and doubly charged ions of the elements found, and polyatomic ions of the
interference database) come from
:func:`utils.interference_detection.candidate_species`.

---

## Constants

| Name | Value |
|------|-------|
| `SEARCH_HALF_WIDTH` | `0.35` |
| `ZOOM_HALF_WIDTH` | `0.5` |
| `MIN_IONS` | `200` |
| `MIN_PEAKS_FOR_OFFSET` | `3` |
| `SHIFT_MIN_DA` | `0.006` |
| `SHIFT_MIN_WIDTHS` | `0.2` |
| `NEIGHBOUR_MIN_HEIGHT` | `0.1` |
| `NEIGHBOUR_MIN_SEPARATION` | `0.6` |
| `NEIGHBOUR_MAX_VALLEY` | `0.85` |
| `NEIGHBOUR_MIN_IONS` | `30` |
| `FIGURE_POINTS` | `400` |
| `FIGURE_ZOOM_WIDTHS` | `4.0` |
| `OFFSET_NOTE_DA` | `0.0005` |
| `SHARE_CLEAN` | `0.95` |
| `SHARE_MAJOR` | `0.5` |
| `_SUPERSCRIPT` | `str.maketrans('0123456789', '⁰¹²³⁴⁵⁶⁷⁸⁹')` |
| `_SPECTRA_LOCK` | `threading.Lock()` |
| `_KINDS` | `{'atom': 'isobaric', 'doubly charged': 'doubly_charged'}` |
| `_IDENTIFIED_LOCK` | `threading.Lock()` |
| `SOURCES_KEY` | `'spectrum_sources'` |

## Classes

### `SpectrumSource`

What one sample offers for the spectrum checks.

Attributes:
    sample: Sample name.
    run_info: Nu ``run.info`` with ``MassCalCoefficients``.
    folder: Nu run folder holding the ``.raw`` snapshots.
    entry: Spectrum already read by the main window, ``{'spectrum',
        'n_snapshots'}``; read from *folder* when ``None``.
    identification: ``(Identification, blank name)`` already made by
        the Spectrum view, or ``None`` to make it here.

### `Peak`

The measured peak of one isotope in one sample.

Attributes:
    sample: Sample name.
    label: Isotope label, e.g. ``"56Fe"``.
    exact: Exact mass of the isotope.
    centre: Measured peak centre (m/z).
    width: Peak width (FWHM, Da).
    ions: Ions in the integration window, or ``None`` without a single
        ion area.
    window: Integration window ``(start, end)`` in m/z, or ``None``.
    mz: m/z of the zoomed spectrum around the isotope.
    y: Signal of the zoomed spectrum, in ions per bin when the run has a
        single ion area.

| Method | Signature | Description |
|--------|-----------|-------------|
| `trusted` | `(self) → bool` | Whether enough ions make the peak's centre and shape meaningful. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `load` | `(source: SpectrumSource) → dict \| None` | Return a sample's resolved spectrum, reading its snapshots once per folder. |
| `isotope_name` | `(number: int, element: str, charge: str='⁺') → str` | Write an ion as ``⁵⁶Fe⁺``. |
| `known_species` | `(label: str, exact: float, present=None) → list[tuple[str, float, str]` | Known species that land at an isotope's nominal mass. |
| `identify` | `(source: SpectrumSource, blanks: dict) → tuple` | Identify the elements of one sample, against the closest blank. |
| `measure` | `(source: SpectrumSource, isotopes) → list[Peak]` | Measure the peak of every isotope in one sample's spectrum. |
| `run_offset` | `(peaks: list[Peak]) → float` | The run's mass calibration offset: the median shift of its trusted peaks. |
| `whole_run_offset` | `(source: SpectrumSource, ident) → float \| None` | The run's mass calibration offset measured on every clean peak of the run. |
| `nearest_species` | `(species, target: float, exact: float, width: float, side: float=0.0)` | The known species closest to *target*, within one peak width of it. |
| `_smooth` | `(y: np.ndarray) → np.ndarray` | Three-point running mean, to keep counting noise from making extra maxima. |
| `find_neighbour` | `(peak: Peak, offset: float) → dict \| None` | Find a second, partly resolved peak next to an isotope's peak. |
| `thin` | `(mz: np.ndarray, y: np.ndarray, n: int=FIGURE_POINTS) → tuple[list, li` | Keep at most *n* points of a zoomed spectrum, keeping every local maximum. |
| `share_finding` | `(peak: Peak, ident, blank) → dict \| None` | How much of an isotope's signal other species make, from the elements found. |
| `check_sample` | `(source: SpectrumSource, isotopes, identification=None) → list[dict]` | Run the spectrum checks on every isotope of one sample. |
| `_mda` | `(value: float) → str` | A mass difference in mDa, signed. |
| `_figure_facts` | `(kind: str, items: list[dict], species, units: str) → dict` | What the explained figure needs: each sample's zoomed spectrum and the marks. |
| `_shift_card` | `(rr, label: str, items: list[dict], n_samples: int, units: str)` | Card for an isotope whose peak sits off its exact mass. |
| `_neighbour_card` | `(rr, label: str, items: list[dict], n_samples: int, units: str)` | Card for an isotope with a second peak next to its own. |
| `_share_card` | `(rr, label: str, items: list[dict], n_samples: int, units: str, shifts` | Card for an isotope whose signal is partly or mostly another species. |
| `analyse` | `(ctx, progress=None) → list` | Insights detector: spectrum interferences on the scope's isotopes. |
