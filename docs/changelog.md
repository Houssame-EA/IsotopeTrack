# Changelog

All notable changes to IsotopeTrack are documented here.

---

## v1.0.10 — (dev)

### New Features (in development)
- Filter non-linear particles
- Isobaric correction module

### Improvements
- Added legend to network results figure
- Cluster results now saved with project

## v1.0.9 — 2026-06-09

### Bug Fixes
- Fixed bugs with table parameters
- Fixed bugs in results figures


## v1.0.8 — 2026-06-06

### New Features
- CLI support — app can now be launched from terminal with arguments:
  - Load project files directly
  - Load Nu and TOFWERK data files
  - Select isotopes and presets via command line
  - See `tools/cli_utils.py` for details
- Isobaric correction module (still in development)

### Improvements
- Improved Windows performance — replaced QTableWidget with QTableView in main window reducing lag significantly
- Theme file moved to `tools/` for better organization

## v1.0.7 — 2026-06-01

### New Features
- Cluster analysis added option to test all clustering methods at once

### Improvements
- Particle concentration per mL now reported in results figures
- UI improvements in the main window

## v1.0.7 — (dev)

### New Features
- Cluster analysis added option to test all clustering methods at once

### Improvements
- UI improvements in the mainwindow

## v1.0.7 — 2026-05-31 (dev)

### Improvements

- Particle concentration per mL now reported in results figures

## v1.0.6 — 2026-05-30
New Features

Version checker app now automatically checks for newer versions on startup
Cluster analysis new metric scores added

Improvements

Updated main window UI
Standardized Results plot dialogs with a four-button UI contract (Plot format settings, Configure plot quantities, Reset layout, Export figure) across: Ternary plots, Correlation Matrix, Concentration, Network, Pie Chart, Heatmap, Single/Multiple
Cleaned right-click menus to avoid duplicating bottom-button actions while preserving quick toggles and isotope label controls

Bug Fixes

Fixed memory leaks across multiple modules
Fixed errors and bugs in the AI results module
Fixed mass method — users can now select a new isotope after an initial selection
Fixed cluster visualisation bugs
Fixed requirements


## 2026-05-30 (dev)

### New Features
- Version checker app now automatically checks for newer versions on startup
- Cluster analysis new metric scores added

### Improvements
- Updated main window UI
- Fixed cluster visualisation bugs

### Bug Fixes
- Fixed requirements
- Fixed memory leaks across multiple modules
- Fixed errors and bugs in the AI results module

##  2026-05-27
### Bug Fixes
- Fixed memory leaks across multiple modules
- Fixed errors and bugs in the AI results module
- Fixed mass method — users can now select a new isotope after an initial selection

##  2026-05-22
Standardizes several Results plot dialogs around the four-button UI contract:Plot format settingsConfigure plot quantitiesReset layoutExport figureAlso cleans right-click menus to avoid duplicating bottom-button actions, while preserving quick toggles and isotope label controls.Implemented the feature for:-Ternary plots-Correlation Matrix-Concentration-Network-Pie Chart-Heatmap-Single/MultipleMinor rendering bug with the x axis rotation option, easy fix and will be done.Manually tested migrated plots after merging latest dev:Network, Correlation Matrix, Concentration, Heatmap, Triangle, Single/Multiple, Pie chart.

## v1.0.5 — 2026-05-22

### Bug Fixes
- Fixed atomic notation rendering inconsistency across platforms

## v1.0.4 — 2026-05-21
 
### New Features
- **Window titles** — each window now displays its own name in the title bar
- **CPLN quantiles** — implemented Compound Poisson Log-Normal quantiles from SPCal lookup table (`cpln_quantiles.npz`)
- **Detection method info** — added additional information displayed in the detection method panel
### Bug Fixes
- Fixed main window: the background bug, when the user calculate the background using window size
- Fixed bar plot display order — elements now appear in the correct order
### Internal
- Automated CI/CD pipeline for macOS and Windows builds
- Added `version.py` to update version across all files in one command

---

## v1.0.3 — 2026-05-19

### Improvements
- Integrated data points are now shown directly in the main window results
- Updated cluster analysis with improved metrics

### Bug Fixes
- Fixed several rendering and interaction bugs on the results canvas

---

## v1.0.2 — 2026-04-30

### Main Window
- Full light / dark theme toggle with live switching across all dialogs and widgets

### Single-Ion Analysis (SIA)
- Detection parameters now configured independently per isotope

### Export
- CSV export supports multiple unit systems (ag, fg, pg, ng · amol, fmol, pmol · nm, µm)
- Export includes additional analysis detection parameters

### Peak Detection
- Added integration threshold method
- Added midpoint and watershed separation
- Added Aiken iterative threshold method
- Detection engine now uses Compound Poisson Log-Normal as the primary model
- Implemented result caching — significantly reduces processing time on large datasets

### Signal Time Scan
- Exclusion regions can now be defined per sample and per isotope

### Ionic Calibration
- Mass range mismatches detected and reported for Nu Vitesse data
- Individual calibration points can be excluded interactively

### Transport Rate Calibration
- All three calibration tabs unified in a single window

### Results Canvas
- Plot backends unified: Matplotlib and PyQtGraph for interactive plots
- Clustering module improved with more control over distance metrics and linkage

---

## v1.0.1 — 2026-03-11

### New Features
- Results Canvas completely redesigned with three new figures:
  - **Network** — multi-element particle relationships
  - **Concentration** — particle concentration overview
  - **Matrix** — element correlation matrix
- Intel Mac support — dedicated native bundle for Intel-based Macs (x86_64)
- Faster project saving and loading

### Bug Fixes
- Fixed multiple bugs in the Results Canvas display
- Fixed several issues in the main window
- Fixed Windows lag and slow response

---

## v1.0.0 — 2025-11-21

First public release of IsotopeTrack for macOS and Windows.
