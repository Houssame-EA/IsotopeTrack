# IsotopeTrack

<div align="center">

**A fast, free, and open-source desktop application for single-particle ICP-ToF-MS data analysis**

[![Version](https://img.shields.io/badge/version-1.0.2-blue.svg)](https://github.com/Houssame-EA/IsotopeTrack/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey.svg)](https://github.com/Houssame-EA/IsotopeTrack/releases)
[![DOI](https://img.shields.io/badge/DOI-10.1071%2FEN25111-green.svg)](https://doi.org/10.1071/EN25111)

</div>

---

## Downloads

| Platform | Requirements | Download |
|----------|-------------|----------|
| **macOS — Apple Silicon** | macOS 11.0 (Big Sur) or later · 4 GB RAM (8 GB recommended) | [IsotopeTrack_M.dmg](https://github.com/Houssame-EA/IsotopeTrack/releases/latest) |
| **Windows** | Windows 10 (64-bit) or later · 4 GB RAM (8 GB recommended) | [IsotopeTrack_Setup_1.0.2_W.exe](https://github.com/Houssame-EA/IsotopeTrack/releases/latest) |

---

## Key Features

- **Multi-isotope** single-particle detection across all measured elements simultaneously
- **Three detection methods** — Currie, Formula C, Compound Poisson Log-Normal, and Manual threshold
- **Transport rate calibration** — mass-based, number-based, and weighted liquid methods
- **Ionic calibration** — automatic model selection (Simple Linear, Linear with intercept, Weighted Linear)
- **16 result plot types** on a drag-and-drop canvas — bar charts, heatmaps, correlation, clustering, isotope ratios, triangle plots, network graphs, and more
- Supports **Nu Vitesse folders** (`run.info`), **TOFWERK** (`.h5`), and **CSV** formats
- Built-in **materials database** with mass fraction and density lookup
- **Batch processing** and comprehensive CSV export
- Light / dark theme with fully responsive UI

---

## Recommended Workflow

### 1 · Load Sample Data
Click **Import Data** in the *File* menu or sidebar. Load all samples you plan to analyze in a single session to ensure consistent processing parameters.

### 2 · Choose Isotopes
Use the periodic table interface to select the isotopes of interest. Selected isotopes are carried automatically into all calibration panels.

![Element Selection](images/1.gif)

### 3 · Ionic Calibration (Sensitivity)
Configure ionic calibration to convert raw counts to mass. Use `-1` to exclude samples from specific calibration sets. IsotopeTrack evaluates three calibration models and automatically selects the best R². Manual override is available.

### 4 · Transport Rate Calibration
Calibrate aerosol transport efficiency using one of three methods: mass-based, number-based, or weighted liquid. Average multiple measurements or select the most reliable single value.

![Calibration](images/4.gif)

### 5 · Mass Fraction & Density
For each sample, specify the mass fraction of the target element and the particle density from the built-in materials database.

### 6 · Set Detection Parameters
Configure detection method, confidence level, minimum peak points, and optional smoothing for each element individually or via **Batch Edit Parameters**.

![Detection Parameters](images/2.gif)

### 7 · Review Results in Canvas
Use the drag-and-drop results canvas to visualize and validate the analysis. Add plot nodes, adjust parameters, and explore multi-element relationships interactively.

![Results Canvas](images/5.gif)

### 8 · Export Data
Export a **summary file** (all samples and elements, statistics, concentrations, calibration info) and/or a **details file** (individual particle data per sample).

---

## Data Loading

### Supported Formats
- **Folder with `run.info`** — Raw data from Nu Vitesse instruments
- **TOFWERK `.h5`** — HDF5 acquisition files
- **CSV files** — Time-series data

### CSV Format Requirements
- First column must be **Time** (units: `ms`, `ns`, or `s`)
- Each element column must include mass number + element symbol (e.g., `107Ag`, `56Fe`)
- Data must be provided in counts

---

## Detection Methods

| Method | Description |
|--------|-------------|
| **Compound Poisson Log-Normal** | Advanced method accounting for signal distribution characteristics |
| **Manual** | User-defined threshold value |

---

## Export Options

### Summary File
Statistical summaries (mean, median, standard deviation), particle concentrations, size distributions, calibration information and method parameters for all samples and elements.

### Details File
Individual particle data for each sample with complete particle-by-particle information, peak characteristics, and integration results.

---

## Citation

If you use IsotopeTrack in your research, please cite:

> Ahabchane H, Goodman A, Hadioui M, Wilkinson K. *IsotopeTrack: A fast and flexible application for the analysis of SP-ICP-TOF-MS datasets.* Environmental Chemistry 2026; EN25111.
> [https://doi.org/10.1071/EN25111](https://doi.org/10.1071/EN25111)

---

## Acknowledgements

IsotopeTrack builds upon the work of the SP-ICP-MS community. We are deeply grateful to all scientists whose published methodologies, open-source tools, and foundational research form the scientific backbone of this software.

### SPCal

We particularly acknowledge **SPCal**, developed by T. E. Lockwood, R. Gonzalez de Vega, L. Schlatt, and D. Clases. Certain algorithmic approaches and detection methods implemented in IsotopeTrack were informed by their work.

> Lockwood, T. E., Gonzalez de Vega, R., & Clases, D. (2021). *An interactive Python-based data processing platform for single particle and single cell ICP-MS.* Journal of Analytical Atomic Spectrometry, **36**(11), 2536–2544.
> [https://doi.org/10.1039/D1JA00297J](https://doi.org/10.1039/D1JA00297J)

> Lockwood, T. E., Schlatt, L., & Clases, D. (2025). *SPCal – an open source, easy-to-use processing platform for ICP-TOFMS-based single event data.* Journal of Analytical Atomic Spectrometry.
> [https://doi.org/10.1039/d4ja00241e](https://doi.org/10.1039/d4ja00241e)

**Compound Poisson signal distribution models:**

> Hendriks, L., Gundlach-Graham, A., & Günther, D. (2019). *Performance of sp-ICP-TOFMS with signal distributions fitted to a compound Poisson model.* Journal of Analytical Atomic Spectrometry.
> [https://doi.org/10.1039/c9ja00186g](https://doi.org/10.1039/c9ja00186g)

> Gundlach-Graham, A., et al. (2018). *Monte Carlo Simulation of Low-Count Signals in Time-of-Flight Mass Spectrometry and Its Application to Single-Particle Detection.* Analytical Chemistry, **90**(20), 11847–11855.
> [https://doi.org/10.1021/acs.analchem.8b01551](https://doi.org/10.1021/acs.analchem.8b01551)

**Transport rate reference:**

> Pace, H. E., et al. (2011). *Determining transport efficiency for the purpose of counting and sizing nanoparticles via single-particle ICP-MS.* Analytical Chemistry, **83**, 9361–9369.
> [https://doi.org/10.1021/ac201952t](https://doi.org/10.1021/ac201952t)

---

## License

IsotopeTrack is free and open-source software released under the [GNU General Public License v3.0](LICENSE).
