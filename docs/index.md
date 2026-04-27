# IsotopeTrack Documentation

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Version](https://img.shields.io/badge/version-1.0.2-green.svg)](https://github.com/Houssame-EA/IsotopeTrack/releases)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey.svg)](https://github.com/Houssame-EA/IsotopeTrack/releases)

**IsotopeTrack** is a free, open-source desktop application for **single-particle ICP-ToF-MS (spICP-MS)** data analysis.  
It supports Nu Vitesse and TOFWERK instruments and provides a full graphical pipeline — from raw signal loading to multi-element statistical results.

---

## Citation

If you use IsotopeTrack in your research, please cite:

!!! quote ""
    Ahabchane H, Goodman A, Hadioui M, Wilkinson K. *IsotopeTrack: A fast and flexible application for the analysis of SP-ICP-TOF-MS datasets.* Environmental Chemistry 2026; EN25111.  
    [https://doi.org/10.1071/EN25111](https://doi.org/10.1071/EN25111)

---

## Downloads

| Platform | Requirements | File |
|----------|-------------|------|
| **macOS — Apple Silicon (M1/M2/M3)** | macOS 11.0+ · 4 GB RAM | `IsotopeTrack_M.dmg` |
| **macOS — Intel** | macOS 10.15+ · 4 GB RAM | `IsotopeTrack_Intel.dmg` |
| **Windows** | Windows 10 64-bit+ · 4 GB RAM | `IsotopeTrack_Windows.exe` |

---

## Key Features

- Multi-isotope single-particle detection
- Transport rate & ionic calibration (3 methods each)
- Supports Nu Vitesse folders (`run.info`), TOFWERK (`.h5`), and CSV
- Interactive drag-and-drop results canvas with 16 plot types
- Batch processing and comprehensive export options
- Light / dark theme, fully responsive UI

---

## Recommended Workflow

```
1. Load Sample Data      →  File > Import Data
2. Select Isotopes       →  Periodic table interface
3. Ionic Calibration     →  Sensitivity (counts → mass)
4. Transport Rate        →  Aerosol efficiency (3 methods)
5. Mass Fraction/Density →  Per-sample material properties
6. Detection Parameters  →  Method, confidence level, smoothing
7. Review in Canvas      →  Visualize and validate
8. Export               →  Summary + Details CSV
```

---

## Detection Methods

| Method | Description |
|--------|-------------|
| **Currie Method** | Classical detection based on Poisson statistics |
| **Formula C** | MARLAP-based, balances false positives/negatives |
| **Compound Poisson Log-Normal** | Advanced — accounts for signal distribution |
| **Manual** | User-defined threshold |

---

## Supported Data Formats

- **Nu Vitesse folder** — directory containing `run.info`
- **TOFWERK `.h5`** — HDF5 acquisition files
- **CSV** — Time-series (first column = Time in ms/ns/s; element columns as `107Ag`, `56Fe`, …)

---

## Architecture Overview

```
Run.py
└── SplashCoordinator → ProgressiveMainWindow
    └── MainWindow
        ├── theme.py              (ThemeManager, palettes, QSS)
        ├── Project I/O           (fast_project_io, project_manager)
        ├── Peak Detection        (peak_detection, SIA_manager)
        ├── Calibration           (ionic_CAL, TE_*)
        └── Results Canvas        (canvas_widgets)
            ├── shared_plot_utils / shared_annotation
            └── results_*.py      (16 plot modules)
```

---

## Code Statistics

| | |
|---|---|
| **Modules** | 50 |
| **Classes** | 236 |
| **Methods** | 2134 |
| **Functions** | 292 |
| **License** | GPL-3.0 |
| **Version** | 1.0.2 |

---

## Acknowledgements

IsotopeTrack builds on the work of the SP-ICP-MS community.

**SPCal** — T. E. Lockwood, R. Gonzalez de Vega, L. Schlatt, D. Clases:

> Lockwood et al. (2021). *An interactive Python-based data processing platform for single particle and single cell ICP-MS.* J. Anal. At. Spectrom., 36(11), 2536–2544. [DOI](https://doi.org/10.1039/D1JA00297J)

> Lockwood, Schlatt & Clases (2025). *SPCal – an open source, easy-to-use processing platform for ICP-TOFMS-based single event data.* J. Anal. At. Spectrom. [DOI](https://doi.org/10.1039/d4ja00241e)

**Compound Poisson models:**

> Hendriks et al. (2019). *Performance of sp-ICP-TOFMS with signal distributions fitted to a compound Poisson model.* J. Anal. At. Spectrom. [DOI](https://doi.org/10.1039/c9ja00186g)

> Gundlach-Graham et al. (2018). *Monte Carlo Simulation of Low-Count Signals in ToF-MS.* Anal. Chem., 90(20), 11847–11855. [DOI](https://doi.org/10.1021/acs.analchem.8b01551)
