# IsotopeTrack

<div align="center">

**A fast, free, and open-source desktop application for single-particle ICP-ToF-MS data analysis**

[![Docs](https://img.shields.io/badge/docs-readthedocs-blue.svg)](https://isotopetrack.readthedocs.io/en/latest/)
[![Version](https://img.shields.io/badge/version-1.10.7-blue.svg)](https://github.com/Houssame-EA/IsotopeTrack/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey.svg)](https://github.com/Houssame-EA/IsotopeTrack/releases)
[![DOI](https://img.shields.io/badge/DOI-10.1071%2FEN25111-green.svg)](https://doi.org/10.1071/EN25111)

<img src="images/mainwindow.png" width="850" alt="IsotopeTrack main window">

</div>

---

## Downloads

| Platform | Requirements | Download |
|----------|-------------|----------|
| **macOS — Apple Silicon** | macOS 11.0 (Big Sur) or later · 4 GB RAM (8 GB recommended) | [IsotopeTrack_M.dmg](https://github.com/Houssame-EA/IsotopeTrack/releases/latest) |
| **Windows** | Windows 10 (64-bit) or later · 4 GB RAM (8 GB recommended) | [IsotopeTrack_Setup_W.exe](https://github.com/Houssame-EA/IsotopeTrack/releases/latest) |

---

## Key Features

- **Multi-isotope** single-particle detection across all measured elements simultaneously
- **Three detection methods** — Compound Poisson Log-Normal, CPLN lookup table, and Manual threshold
- **Single-ion distribution (SIA)** support — per-isotope σ fitted from real single-ion data
- **Detector non-linearity filter** — flat-topped saturated events excluded automatically
- **Transport rate calibration** — liquid weight, particle number, and particle mass methods
- **Ionic calibration** — automatic model selection (force through zero, linear, weighted linear)
- **16 result plot types** on a drag-and-drop canvas — histograms, heatmaps, correlation, clustering, isotope ratios, ternary plots, network graphs, and more
- Supports **Nu Vitesse folders** (`run.info`), **TOFWERK** (`.h5`), and **CSV** formats
- Built-in **materials database** with mass fraction and density lookup
- **Batch processing** and CSV export
- **Interactive in-app documentation** — Help → User Guide (clickable screenshots of every window) and Help → Equations (every equation in LaTeX with worked examples and linked references)

---

## Recommended Workflow

### 1 · Load Sample Data
Click **Import Data** in the *File* menu or sidebar. Load all samples you plan to analyze in a single session to ensure consistent processing parameters.

### 2 · Choose Isotopes
Use the periodic table interface to select the isotopes of interest. Selected isotopes are carried automatically into all calibration panels.

### 3 · Ionic Calibration (Sensitivity)
Configure ionic calibration to convert raw counts to mass. Use `-1` to exclude samples from specific calibration sets. IsotopeTrack evaluates three calibration models and automatically selects the best R². Manual override is available.

### 4 · Transport Rate Calibration
Calibrate aerosol transport efficiency using one of three methods: liquid weight, particle number, or particle mass. Average multiple measurements or select the most reliable single value.

### 5 · Mass Fraction & Density
For each sample, specify the mass fraction of the target element and the particle density from the built-in materials database.

### 6 · Set Detection Parameters
Configure detection method, alpha error rate, minimum peak points, watershed splitting and more for each element individually or via **Batch Edit Parameters**.

### 7 · Review Results in Canvas
Use the drag-and-drop results canvas to visualize and validate the analysis. Add plot nodes, adjust parameters, and explore multi-element relationships interactively.

### 8 · Export Data
Export a **summary file** (all samples and elements, statistics, concentrations, calibration info) and/or **sample files** (individual particle data per sample).

---

## User Guide

The full **interactive user guide** ships inside the application (**Help → User Guide**): every screenshot below is clickable there, with a detailed explanation of each region, guide-wide search, and region-by-region navigation. The sections below mirror it — click any section to expand it.

<details>
<summary><b> The Main Window</b></summary>

<br>

<img src="images/mainwindow.png" width="850">

The main window is organised around four areas:

- **Sidebar** — calibration tools (Transport Rate, Sensitivity, Calibration Info) and sample management (Import Data, Add/Edit Elements, Results, Export, Sample List).
- **Data Visualization** — the raw signal of the selected isotope with zoom/pan, Time and m/z views, and the detection overlay after running Detect Peaks.
- **Particle summary statistics** — per-element particle counts, background, threshold, masses and concentrations.
- **Particle peak detection parameters** — one row per isotope: detection method, sigma, manual threshold, min points, alpha, iterative background, window size, integration method, watershed splitting and valley ratio. Below it: Batch Edit Parameters, Multi-Signal View, Detect Peaks, and the Non-linearity Filter.

</details>

<details>
<summary><b> Getting Started — welcome screen and data import</b></summary>

<br>

The welcome screen is the fastest way to begin: import data, load a saved `.itproj` project, or open a new window.

<img src="images/welcome.png" width="550">

**Import Data** asks for the data source type — Nu folders (with `run.info`), delimited data files, or TOFWERK `.h5`:

<img src="images/data_source.png" width="500">

For delimited files, the **File Import Configuration** dialog auto-detects isotope columns from their names (e.g. `107Ag`); you control the time column, dwell time, and column mappings before importing:

<img src="images/csv_file.png" width="750">

Every user action, warning and error of the session is recorded in the **Application Log** (View → Show Application Log) — invaluable when reporting an issue:

<img src="images/log.png" width="750">

</details>

<details>
<summary><b> Elements & Signals — periodic table, signal views, multi-element particles</b></summary>

<br>

**Left-click** an element to select its most abundant low-interference isotope; **right-click** to choose specific isotopes. Gray elements are not present in the dataset. Selections can be saved as named presets.

<img src="images/periodic_table.png" width="750">

After **Detect Peaks**, the signal view overlays the background level, detection threshold, integrated points (orange) and peak maxima (green):

<img src="images/signal.png" width="850">

Zooming shows exactly how each transient was integrated:

<img src="images/signal_zoom.png" width="850">

Selecting a row in the results table highlights that particle in red:

<img src="images/element_signal.png" width="850">

**Multi-Signal View** plots several isotopes together — coincident peaks reveal multi-element particles, with a per-particle composition box:

<img src="images/multi_signal_display.png" width="450">
<img src="images/particle_signal.png" width="850">

</details>

<details>
<summary><b> Detection & SIA — batch parameters, single-ion distribution, non-linearity filter</b></summary>

<br>

**Batch Edit Parameters** applies identical settings to any set of elements and samples at once:

<img src="images/Batch_parameters.png" width="600">

Upload a **single-ion distribution** (Nu Vitesse or TOFWERK) to fit the log-normal σ of the detector response — per mass or globally, with outlier flagging:

<img src="images/SIA_1.png" width="650">
<img src="images/SIA_2.png" width="650">

The **detector non-linearity filter** recognises saturated, flat-topped events and excludes their time window for all isotopes:

<img src="images/non-linear.png" width="850">
<img src="images/filter_non_linear.png" width="400">

</details>

<details>
<summary><b> Calibration — sensitivity, transport rate, mass fraction, dilution, isobaric correction</b></summary>

<br>

**Ionic Calibration Analysis** (sidebar → Sensitivity): load standards, enter concentrations (`-1` excludes a sample), and review the fits — slope, intercept, BEC, R², LOD and LOQ per isotope. Click a point to exclude it from the fit.

<img src="images/calibration_1.png" width="850">
<img src="images/calibration_2.png" width="850">

**Transport Rate Calibration** offers three methods — liquid weight, mass based, and number based:

<img src="images/TE.png" width="850">
<img src="images/TE_mass_based.png" width="850">

**Calibration Information** summarises everything: which transport methods are in use, and the full per-isotope table with MDL/MQL (fg) and SDL/SQL (nm):

<img src="images/calibration_info_TE.png" width="700">
<img src="images/calibration_info_ionic.png" width="850">

The **Mass Fraction Calculator** converts compound formulas (e.g. TiO2, Fe3O4) into mass fractions, molecular weights and densities from the built-in materials database:

<img src="images/mass_fraction.png" width="850">

**Dilution factors** (auto-detected from sample names) correct reported particles/mL, and **Isobaric Correction** subtracts isobaric interferences with editable per-analyte equations and a live before/after preview:

<img src="images/dilution.png" width="500">
<img src="images/isobaric_correction.png" width="750">

</details>

<details>
<summary><b> Results Canvas — node-based workflow builder</b></summary>

<br>

The results canvas is a **Workflow Builder**: drag data blocks (Single Sample, Multiple Sample, Batch Windows, Particle Filter) and visualization blocks (histogram, correlation, clustering, ternary, network, dashboard…) onto the canvas and connect them.

<img src="images/Canvas_results_1.png" width="850">
<img src="images/Canvas_results_2.png" width="850">

Sample nodes select and group samples (replicates can be combined automatically); the **Particle Filter** node keeps particles by elemental composition, element count, or per-element signal thresholds:

<img src="images/single_sample_results.png" width="550">
<img src="images/multi_sample_results.png" width="550">
<img src="images/Particle_filter.png" width="600">

Every plot window has format settings, quantity configuration (counts, mass, moles, diameter, element groups summed per particle) and publication-quality figure export:

<img src="images/histogram.png" width="650">
<img src="images/plot_settings.png" width="350"> <img src="images/configuration_settings.png" width="360">
<img src="images/export_figure.png" width="300">

</details>

<details>
<summary><b> Export — sample files and summary file</b></summary>

<br>

Choose the data type (Element or Particle), the samples, and the outputs: **sample files** (particle-by-particle data) and/or a **summary file** (statistics, concentrations, calibration info for all samples). Dilution factors can be set right from the export dialog.

<img src="images/export_csv.png" width="450">

</details>

---

## Data Loading

### Supported Formats
- **Folder with `run.info`** — Raw data from Nu Vitesse instruments
- **TOFWERK `.h5`** — HDF5 acquisition files
- **Data files** — Delimited/spreadsheet time-series data (`csv`, `txt`, `xls`, `xlsx`, `xlsm`, `xlsb`)

### CSV Format Requirements
- First column must be **Time** (units: `ms`, `ns`, or `s`)
- Each element column must include mass number + element symbol (e.g., `107Ag`, `56Fe`)
- Data must be provided in counts

### Example Data
Example datasets for trying out IsotopeTrack (ionic calibration sets, transport efficiency standards, and multi-element nanoparticle samples) are available as zip files in the [example-data release](https://github.com/Houssame-EA/IsotopeTrack/releases/tag/example-data). Download, unzip, and import via **File → Import Data**.

---

## Detection Methods

| Method | Description |
|--------|-------------|
| **Compound Poisson Log-Normal** | Threshold from the compound Poisson–log-normal distribution of ToF single-ion signals |
| **CPLN table** | Same quantile drawn from a precomputed λ×σ lookup table for speed and accuracy |
| **Manual** | User-defined threshold value |

Every equation behind these methods — with parameter definitions, worked numerical examples, and clickable literature references — is documented in the app under **Help → Equations**.

---

## Export Options

### Summary File
Statistical summaries (mean, median, standard deviation), particle concentrations, size distributions, calibration information and method parameters for all samples and elements.

### Sample Files
Individual particle data for each sample with complete particle-by-particle information, peak characteristics, and integration results.

---

## Acknowledgements

IsotopeTrack builds upon the work of the spICP-MS community. We are deeply grateful to all scientists whose published methodologies, open-source tools, and foundational research form the scientific backbone of this software.

### SPCal

We particularly acknowledge **SPCal**, developed by T. E. Lockwood, R. Gonzalez de Vega, L. Schlatt, and D. Clases. Certain algorithmic approaches and detection methods implemented in IsotopeTrack were informed by their work.

> Lockwood, T. E., Gonzalez de Vega, R., & Clases, D. (2021). *An interactive Python-based data processing platform for single particle and single cell ICP-MS.* Journal of Analytical Atomic Spectrometry, **36**(11), 2536–2544.
> [https://doi.org/10.1039/D1JA00297J](https://doi.org/10.1039/D1JA00297J)


If you use IsotopeTrack in your research, please cite if not enjoy using it:

> Ahabchane H, Goodman A, Hadioui M, Wilkinson K. *IsotopeTrack: A fast and flexible application for the analysis of SP-ICP-TOF-MS datasets.* Environmental Chemistry 2026; EN25111.
> [https://doi.org/10.1071/EN25111](https://doi.org/10.1071/EN25111)

---


The methodologies implemented in IsotopeTrack are based on the following studies.

**Transport efficiency & quantification**

> Pace, H. E., Rogers, N. J., Jarolimek, C., Coleman, V. A., Higgins, C. P. & Ranville, J. F. (2011). *Determining transport efficiency for the purpose of counting and sizing nanoparticles via single particle ICP-MS.* Analytical Chemistry, **83**(24), 9361–9369.
> [https://doi.org/10.1021/ac201952t](https://doi.org/10.1021/ac201952t)

> Laborda, F., Bolea, E. & Jiménez-Lamana, J. (2014). *Single particle inductively coupled plasma mass spectrometry: a powerful tool for nanoanalysis.* Analytical Chemistry, **86**(5), 2270–2278.
> [https://doi.org/10.1021/ac402980q](https://doi.org/10.1021/ac402980q)

> Hadioui, M., Knapp, G., Azimzada, A., Jreije, I., Frechette-Viens, L. & Wilkinson, K. J. (2019). *Lowering the size detection limits of Ag and TiO2 nanoparticles by single particle ICP-MS.* Analytical Chemistry, **91**(20), 13275–13284.
> [https://doi.org/10.1021/acs.analchem.9b04007](https://doi.org/10.1021/acs.analchem.9b04007)

**Particle detection & thresholding**

> Gundlach-Graham, A., Hendriks, L., Mehrabi, K. & Günther, D. (2018). *Monte Carlo simulation of low-count signals in time-of-flight mass spectrometry and its application to single-particle detection.* Analytical Chemistry, **90**(20), 11847–11855.
> [https://doi.org/10.1021/acs.analchem.8b01551](https://doi.org/10.1021/acs.analchem.8b01551)

> Hendriks, L., Gundlach-Graham, A. & Günther, D. (2019). *Performance of sp-ICP-TOFMS with signal distributions fitted to a compound Poisson model.* Journal of Analytical Atomic Spectrometry, **34**(9), 1900–1909.
> [https://doi.org/10.1039/C9JA00186G](https://doi.org/10.1039/C9JA00186G)

> Gundlach-Graham, A. & Lancaster, R. (2023). *Mass-dependent critical value expressions for particle finding in single-particle ICP-TOFMS.* Analytical Chemistry, **95**(13), 5618–5626.
> [https://doi.org/10.1021/acs.analchem.2c05243](https://doi.org/10.1021/acs.analchem.2c05243)

> Lockwood, T. E., Schlatt, L. & Clases, D. (2025). *SPCal — an open source, easy-to-use processing platform for ICP-TOFMS-based single event data.* Journal of Analytical Atomic Spectrometry, **40**(1), 130–136.
> [https://doi.org/10.1039/D4JA00241E](https://doi.org/10.1039/D4JA00241E)

> Lockwood, T. E., Gonzalez de Vega, R., Schlatt, L. & Clases, D. (2025). *Accurate thresholding using a compound-Poisson-lognormal lookup table and parameters recovered from standard single particle ICP-TOFMS data.* Journal of Analytical Atomic Spectrometry, **40**(10), 2633.
> [https://doi.org/10.1039/D5JA00230C](https://doi.org/10.1039/D5JA00230C)

**Clustering of multi-element particle data**

> Tharaud, M., Schlatt, L., Shaw, P. & Benedetti, M. F. (2022). *Nanoparticle identification using single particle ICP-ToF-MS acquisition coupled to cluster analysis. From engineered to natural nanoparticles.* Journal of Analytical Atomic Spectrometry, **37**, 2042–2052.
> [https://doi.org/10.1039/D2JA00116K](https://doi.org/10.1039/D2JA00116K)

> Erfani, M., Baalousha, M. & Goharian, E. (2023). *Unveiling elemental fingerprints: a comparative study of clustering methods for multi-element nanoparticle data.* Science of The Total Environment.
> [https://www.sciencedirect.com/science/article/abs/pii/S0048969723058035](https://www.sciencedirect.com/science/article/abs/pii/S0048969723058035)

> Cuss, C. W., Benedetti, M. F., Costamanga, C., Mesnard, L. & Tharaud, M. (2025). *Self-organizing maps for the detection and classification of natural nanoparticles, nanoparticle systems and engineered nanoparticles characterized using single particle ICP-time-of-flight-MS.* Journal of Analytical Atomic Spectrometry, **40**, 2471.
> [https://doi.org/10.1039/D5JA00179J](https://doi.org/10.1039/D5JA00179J)

The complete reference list — including the foundational statistics and every clustering algorithm and validity index — is available inside the application under **Help → Equations**, with clickable citations throughout.

---

## License

IsotopeTrack is free and open-source software released under the [GNU General Public License v3.0](LICENSE).
