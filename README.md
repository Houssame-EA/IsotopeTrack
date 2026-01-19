IsotopeTrack v1.0.0 - Initial Release
First stable release!
A comprehensive software application for analyzing single particle ICP-ToF-MS (Inductively Coupled Plasma Time-of-Flight Mass Spectrometry) data.
Download
macOS (Apple Silicon - M1/M2/M3)
[IsotopeTrack-v1.0.0-macOS-arm64.dmg]
Windows
[IsotopeTrack-v1.0.0-Windows-x64.exe]

Installation

macOS
1.	Download the DMG file
2.	Open and drag to Applications
3.	Right-click → Open (first time only)

Windows
1.	Download the Windows exe

What's New
•	Multi-isotope particle detection
•	Transport rate & ionic calibration
•	Support for NU, CSV, and TOFWERK formats (futur version)
•	Interactive visualization
•	Comprehensive export options

System Requirements
macOS
•	macOS 11.0 (Big Sur) or later
•	Apple Silicon (M1/M2/M3) recommended
•	4 GB RAM (8 GB recommended)
•	3 GB free disk space
Windows
•	Windows 10 (64-bit) or later
•	4 GB RAM (8 GB recommended)
•	3 GB free disk space

Documentation

## Data Loading

### Supported Data Formats
- **Folder with `run.info`**: Raw data from TOF Vitesse and for multiple files from **TOFWERK .h5** type file
- **CSV files**: Time-series data  

### Loading Process
1. Click **Import Data** in the *File* menu or sidebar  
2. Select **Folder(s) with `run.info`** or **CSV file(s)** or **TOFWERK .h5** 
3. Browse to your data location and select one or more folders/files  
4. The application validates the data and displays loading progress  
5. Successfully loaded samples appear in the **Samples** table in the sidebar  

### CSV Format Requirements
If using CSV files, they must follow this structure:

- The first column must be **Time** (units: `ms`, `ns`, or `s`)  
- Each element column must include **mass number + element symbol**  
  - Example: `107Ag`  
- Data must be provided in **counts**  

### Sample Management
Once data are loaded, you can:

- Click a sample in the sidebar to switch between samples  
- Right-click a sample to view additional metadata  
- Process all samples simultaneously using the same parameters  

<p align="center">
  <img src="https://raw.githubusercontent.com/Houssame-EA/IsotopeTrack/main/images/1.gif" width="700">
</p>

## Element Selection

### Using the Periodic Table
The interactive periodic table allows selection of elements and specific isotopes for analysis:

1. Left-click an element to select the most abundant isotope with minimal interferences  
2. Right-click an element to display all available isotopes and select specific ones  
3. Right-click again on a selected element to deselect it  
4. Click **Confirm** to finalize the selection  
5. Gray elements indicate elements not present in the loaded dataset  

---

## Calibration Methods

### Ionic Calibration (Sensitivity)
Establishes the relationship between elemental concentration and instrument response.

#### Process
1. Selected isotopes are automatically imported from the main window  
2. Create one or more calibration sets  
3. Enter `-1` to exclude samples from specific calibration sets  
4. The system automatically evaluates three calibration models:
   - **Simple Linear** (no intercept)
   - **Linear** (with intercept)
   - **Weighted Linear**
5. The model with the highest R² is automatically selected  
6. Manual override is available  

<p align="center">
  <img src="https://raw.githubusercontent.com/Houssame-EA/IsotopeTrack/main/images/3.gif" width="700">
</p>

---

### Transport Rate Calibration
Determines the efficiency of aerosol transport into the plasma.

#### Available Methods
- Mass-based method  
- Number-based method  
- Weighted liquid method  

**Reference:**  
Pace, H. E., et al. (2011).  
*Determining transport efficiency for the purpose of counting and sizing nanoparticles via single-particle ICP-MS*.  
Analytical Chemistry, **83**, 9361–9369.  
https://doi.org/10.1021/ac201952t

#### After Calibration
- Average multiple transport efficiency measurements **or**  
- Select the most reliable single value  

The chosen transport rate is applied to all subsequent particle mass and number concentration calculations.

---

### Mass Fraction and Density Configuration
For accurate particle sizing, specify for each sample:

- Mass fraction of the target element in the particles  
- Particle density selected from the materials database  

---

## Detection Parameters

### Element Parameters Table
Each element includes customizable detection parameters:

- **Include**: Enable or disable the element in analysis  
- **Method**: Detection algorithm  
  - Currie  
  - Formula C  
  - Compound Poisson Log-Normal  
  - Manual  
- **Min Points**: Minimum consecutive points above threshold to define a particle  
- **Confidence Level**: Statistical confidence for threshold determination (default: 99.999%)  
- Optional smoothing  
- Alpha error rate  
- Iterative threshold calculation  
- Window size for threshold calculation  

---

### Detection Methods

#### Currie Method
Classical detection approach based on Poisson statistics and critical level determination.

**Reference:**  
Currie, L. A. (2008). *Detection and quantification limits: Origins and historical overview*.  
Journal of Radioanalytical and Nuclear Chemistry, **276**, 285–297.  
https://doi.org/10.1007/s10967-007-0451-1

---

#### Formula C
MARLAP-based method offering a balanced trade-off between false positives and false negatives.

**Reference:**  
MARLAP Manual, Volume III – Chapter 20: Detection and Quantification Capabilities (Formula C, Eq. 20.52).  
U.S. EPA.  
https://www.epa.gov/radiation/marlap-manual

---

#### Compound Poisson Log-Normal
Advanced method accounting for signal distribution characteristics; includes a sigma parameter describing distribution shape.

**Reference:**  
Lockwood, T. E., Schlatt, L., & Clases, D. (2025).  
*SPCal – an open-source processing platform for ICP-TOFMS-based single-event data*.  
Journal of Analytical Atomic Spectrometry.  
https://pubs.rsc.org/en/journal/jaas

---

#### Manual
User-defined detection threshold.

---

### Batch Parameter Editing
To apply identical parameters to multiple elements:

1. Click **Batch Edit Parameters**  
2. Select elements to modify  
3. Define shared parameters  
4. Optionally select target samples  
5. Apply settings to all selected elements simultaneously  

This approach is particularly useful when analyzing identical elements across multiple samples.


<p align="center">
  <img src="https://raw.githubusercontent.com/Houssame-EA/IsotopeTrack/main/images/2.gif" width="700">
</p>
