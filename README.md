# IsotopeTrack v1.0.1

A comprehensive software application for analyzing single particle ICP-ToF-MS (Inductively Coupled Plasma Time-of-Flight Mass Spectrometry) data.

---

## Key Features

- Multi-isotope particle detection
- Transport rate & ionic calibration
- Support for NU Instruments folders (`run.info`), TOFWERK files (`.h5`) and CSV formats
- Interactive visualization and data exploration
- Batch processing capabilities
- Comprehensive export options

---

## System Requirements & Downloads

| Platform | Requirements | Download |
|----------|-------------|----------|
| **macOS — Apple Silicon (M1/M2/M3)** | macOS 11.0 (Big Sur) or later · 4 GB RAM (8 GB recommended) | `IsotopeTrack_M.dmg` |
| **macOS — Intel** | macOS 10.15 (Catalina) or later · 4 GB RAM (8 GB recommended) | `IsotopeTrack_Intel.dmg` |
| **Windows** | Windows 10 (64-bit) or later · 4 GB RAM (8 GB recommended) | `IsotopeTrack_Windows.exe` |

---

## Recommended Workflow

### 1 · Load Sample Data
Click **Import Data** in the *File* menu or sidebar. Load all samples you plan to analyze in a single session to ensure consistent processing parameters.

### 2 · Choose Isotopes
Use the periodic table interface to select the isotopes of interest. Selected isotopes in the main window are carried automatically into the calibration panels.

![Element Selection](images/1.gif)

### 3 · Ionic Calibration (Sensitivity)
Configure ionic calibration to convert raw counts to mass. Use `-1` to exclude samples from specific calibration sets. IsotopeTrack tests three calibration models and selects the best R².

### 4 · Transport Rate Calibration
Calibrate aerosol transport efficiency using one of three methods: mass-based, number-based, or weighted liquid. Average multiple measurements or select the most reliable single value.

![Calibration](images/4.gif)

### 5 · Mass Fraction & Density
For each sample, specify the mass fraction of the target element and the particle density from the built-in materials database.

### 6 · Set Detection Parameters
Configure detection method, confidence level, minimum peak points, and optional smoothing for each element individually or via **Batch Edit Parameters**.

![Detection Parameters](images/2.gif)

### 7 · Review Results in Canvas
Use the results canvas to visualize and validate the analysis. Adjust parameters as needed based on visual inspection.

![Results Canvas](images/5.gif)

### 8 · Export Data
Export a **summary file** (all samples and elements, statistics, concentrations, calibration info) and/or a **details file** (individual particle data per sample).

---

## Data Loading

### Supported Formats
- **Folder with `run.info`** — Raw data from TOF Vitesse and TOFWERK `.h5` files
- **CSV files** — Time-series data

### CSV Format Requirements
- First column must be **Time** (units: `ms`, `ns`, or `s`)
- Each element column must include mass number + element symbol (e.g., `107Ag`)
- Data must be provided in counts

---

## Calibration

### Ionic Calibration
Establishes the relationship between elemental concentration and instrument response. The system evaluates three models (Simple Linear, Linear with intercept, Weighted Linear) and automatically selects the highest R². Manual override is available.

### Transport Rate Calibration
Determines the efficiency of aerosol transport into the plasma. Available methods: mass-based, number-based, and weighted liquid.

> **Reference:** Pace, H. E., et al. (2011). *Determining transport efficiency for the purpose of counting and sizing nanoparticles via single-particle ICP-MS.* Analytical Chemistry, **83**, 9361–9369. https://doi.org/10.1021/ac201952t

---

## Detection Methods

| Method | Description |
|--------|-------------|
| **Currie Method** | Classical detection based on Poisson statistics and critical level determination |
| **Formula C** | MARLAP-based method balancing false positives and negatives |
| **Compound Poisson Log-Normal** | Advanced method accounting for signal distribution characteristics |
| **Manual** | User-defined threshold value |

---

## Acknowledgements

IsotopeTrack builds upon the work of the SP-ICP-MS community and would not have been possible without the contributions of researchers who have advanced the field of single particle analysis. We are deeply grateful to all scientists whose published methodologies, open-source tools, and foundational research form the scientific backbone of this software.

### SPCal

We would like to particularly acknowledge **SPCal**, developed by T. E. Lockwood, R. Gonzalez de Vega, L. Schlatt, and D. Clases. Certain algorithmic approaches and detection methods implemented in IsotopeTrack were informed by their work. We are grateful for their commitment to open science and reproducible research.

> Lockwood, T. E., Gonzalez de Vega, R., & Clases, D. (2021). *An interactive Python-based data processing platform for single particle and single cell ICP-MS.* Journal of Analytical Atomic Spectrometry, **36**(11), 2536–2544.
> https://doi.org/10.1039/D1JA00297J

> Lockwood, T. E., Schlatt, L., & Clases, D. (2025). *SPCal – an open source, easy-to-use processing platform for ICP-TOFMS-based single event data.* Journal of Analytical Atomic Spectrometry.
> https://doi.org/10.1039/d4ja00241e

The following works provided the theoretical foundation for the compound Poisson signal distribution models

> Hendriks, L., Gundlach-Graham, A., & Günther, D. (2019). *Performance of sp-ICP-TOFMS with signal distributions fitted to a compound Poisson model.* Journal of Analytical Atomic Spectrometry.
> https://doi.org/10.1039/c9ja00186g

> Gundlach-Graham, A., et al. (2018). *Monte Carlo Simulation of Low-Count Signals in Time-of-Flight Mass Spectrometry and Its Application to Single-Particle Detection.* Analytical Chemistry, **90**(20), 11847–11855.
> https://doi.org/10.1021/acs.analchem.8b01551

### SP-ICP-MS Research Community

We also acknowledge the broader SP-ICP-MS research community whose foundational and continued contributions have shaped the methods and tools available in this field

---

## Export Options

### Summary File
Data for all samples and elements, statistical summaries (mean, median, standard deviation), particle concentrations, calibration information and method parameters.

### Details File
Individual particle data for each sample, complete particle-by-particle information, peak characteristics and integration results.

---

## Citation

When using IsotopeTrack in your work, please cite:

> Ahabchane H, Goodman A, Hadioui M, Wilkinson K. *IsotopeTrack: A fast and flexible application for the analysis of SP-ICP-TOF-MS datasets.* Environmental Chemistry 2026; EN25111.
> https://doi.org/10.1071/EN25111

---

## License

See the [LICENSE](LICENSE) file included with this distribution.
