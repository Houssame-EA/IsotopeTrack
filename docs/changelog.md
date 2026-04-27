# Changelog

## v1.0.2 — Latest

What's New in v1.0.2
Main Window
Full light / dark theme toggle with live switching across all dialogs and widgets
Single-Ion Analysis (SIA)
Detection parameters are now configured independently per isotope, giving finer control over threshold and method on a per-element basis
Export
CSV export now supports multiple unit systems (ag, fg, pg, ng for mass; amol, fmol, pmol for moles; nm, µm for diameter)
Export includes additional analysis detection parameters
Peak Detection
Added integration threshold method
Added midpoint separation
Added watershed separation
Added Aiken iterative threshold method for robust automatic threshold estimation
Detection engine now uses Compound Poisson Log-Normal as the primary statistical model for all elements
Implemented result caching to avoid redundant recomputation when switching between samples or adjusting parameters — significantly reduces processing time on large datasets
Remove all other methods
Signal Time Scan
Exclusion regions can now be defined per sample and per isotope, allowing fine-grained control over which time segments are included in the analysis
Ionic Calibration (Sensitivity)
Nu Vitesse data: mass range mismatches are now detected and reported with a clear warning; the user can choose to ignore the mismatch and proceed with calibration
Individual calibration points can be excluded from the curve interactively
Transport Rate Calibration
All three calibration method tabs (weight, number, mass) are now unified in a single window for easier switching and comparison
Results Canvas
Improvements across all plot types
Plot backends unified: Matplotlib, PyQtGraph used for interactive real-time plots.
Clustering module improved with more control over distance metrics and linkage parameters (SOM clustering coming in a future release)
References & Citations
Improved citation formatting and added missing references throughout the application

---

## v1.0.1 — March 2026

- Initial public release
- macOS Apple Silicon, macOS Intel, and Windows builds
- Multi-isotope detection with 4 detection methods
- 16 result plot types on drag-and-drop canvas
- Nu Vitesse, TOFWERK, and CSV data support

---

## v1.0.0 — February 2026

- Beta release
