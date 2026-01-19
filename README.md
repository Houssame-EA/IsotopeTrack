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
- **Folder with `run.info`**: Raw data from TOF Vitesse  
- **CSV files**: Time-series data  

### Loading Process
1. Click **Import Data** in the *File* menu or sidebar  
2. Select **Folder(s) with `run.info`** or **CSV file(s)**  
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


