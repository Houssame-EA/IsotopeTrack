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

<h2>Data Loading</h2>
        
        <h3>Supported Data Formats</h3>
        <ul>
            <li>Folder with run.info: Raw data from TOF Vitesse</li>
            <li>CSV Files: Time series data</li>
        </ul>
        
        <h3>Loading Process</h3>
        <ol>
            <li>Click "Import Data" in the File menu or sidebar</li>
            <li>Select either "Folder(s) with run.info" or "CSV File(s)"</li>
            <li>Browse to your data location and select one or more folders/files</li>
            <li>The app validates your data and shows progress</li>
            <li>Successfully loaded samples appear in the Samples table in the sidebar</li>
        </ol>
        
        <h3>CSV Format Requirements</h3>
        <p>If using CSV files, they should follow this format:</p>
        <ul>
            <li>First column must be Time (labeled with units: ms, ns, or s)</li>
            <li>Each element column should include mass number and element symbol (e.g., "107Ag")</li>
            <li>Data should be in counts</li>
        </ul>
        
        <h3>Sample Management</h3>
        <p>Once loaded, you can:</p>
        <ul>
            <li>Click on any sample in the sidebar to switch between samples</li>
            <li>Right-click on sample for additional information about the sample</li>
            <li>Process all samples at once with the same parameters</li>
        </ul>
        """

<p align="center">
  <img src="https://raw.githubusercontent.com/Houssame-EA/IsotopeTrack/main/images/1.gif" width="700">
</p>


