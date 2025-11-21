from PySide6.QtWidgets import (QDialog, QTabWidget, QVBoxLayout, QPushButton, 
                              QLabel, QScrollArea, QWidget)
from PySide6.QtCore import Qt


class UserGuideDialog(QDialog):
    """
    User guide dialog with comprehensive documentation.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the user guide dialog.
        
        Args:
            parent (QWidget, optional): Parent widget
            
        Returns:
            None
        """
        super().__init__(parent)
        self.setWindowTitle("IsotopeTrack User Guide")
        
        layout = QVBoxLayout(self)
        
        tab_widget = QTabWidget()
        
        tab_widget.addTab(self.create_overview_tab(), "Overview")
        tab_widget.addTab(self.create_workflow_tab(), "Workflow")
        tab_widget.addTab(self.create_data_loading_tab(), "Data Loading")
        tab_widget.addTab(self.create_element_selection_tab(), "Element Selection")
        tab_widget.addTab(self.create_calibration_tab(), "Calibration")
        tab_widget.addTab(self.create_parameters_tab(), "Parameters")
        tab_widget.addTab(self.create_results_tab(), "Results & Export")
        
        layout.addWidget(tab_widget)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignRight)
        
    def create_formatted_text_widget(self, html_content):
        """
        Create a formatted text widget with HTML content.
        
        Args:
            html_content (str): HTML formatted content
            
        Returns:
            QScrollArea: Scrollable widget with formatted content
        """
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        content = QLabel(html_content)
        content.setWordWrap(True)
        content.setOpenExternalLinks(True)
        content.setTextFormat(Qt.RichText)
        
        scroll.setWidget(content)
        return scroll
        
    def create_overview_tab(self):
        """
        Create overview tab content.
        
        Args:
            None
            
        Returns:
            QWidget: Overview tab widget
        """
        content = """
        <h2>IsotopeTrack Overview</h2>
        <p>IsotopeTrack is a comprehensive software for analyzing single particle ICP-MS data, providing tools for peak detection, calibration, and quantitative analysis of nanoparticles in solution.</p>
        
        <h3>Key Features:</h3>
        <ul>
            <li>Multiple detection algorithms (Currie, Formula C, Compound Poisson LogNormal, Manual)</li>
            <li>Ionic and transport efficiency calibration tools</li>
            <li>Interactive visualization and data exploration</li>
            <li>Batch processing capabilities</li>
            <li>Comprehensive export options</li>
            <li>Real-time parameter adjustment and optimization</li>
        </ul>
        
        <h3>Main Interface Components:</h3>
        <ul>
            <li>Sample loading and management panel</li>
            <li>Interactive periodic table for isotope selection</li>
            <li>Parameter configuration table</li>
            <li>Real-time data visualization canvas</li>
            <li>Results tables and summary statistics</li>
        </ul>
        """
        return self.create_formatted_text_widget(content)
        
    def create_workflow_tab(self):
        """
        Create workflow tab content.
        
        Args:
            None
            
        Returns:
            QWidget: Workflow tab widget
        """
        content = """
        <h2>Recommended Workflow for IsotopeTrack</h2>
        
        <h3>1. Load Sample Data</h3>
        <p>Start by loading your sample data files. IsotopeTrack supports both raw data folders with run.info files and CSV formatted time-series data. It is best practice to load all samples you plan to analyze in a single session to ensure consistent processing parameters.</p>
        
        <h3>2. Choose Isotopes</h3>
        <p>After data is loaded, use the periodic table interface to select the isotopes of interest. The selected isotopes in the main window will automatically be selected when you proceed to calibration. Available isotopes are highlighted based on your loaded data.</p>
        
        <h3>3. Ionic Calibration (Sensitivity)</h3>
        <p>Configure ionic calibration to convert raw counts to mass:</p>
        <ul>
            <li>The isotopes selected in the main window will appear in the sensitivity calibration</li>
            <li>You can set multiple calibration sets for different experimental conditions</li>
            <li>Use "-1" in the table to remove samples from calibration sets if needed</li>
            <li>The system tests three calibration methods: Simple Linear, Linear, and Weighted</li>
            <li>IsotopeTrack automatically chooses the calibration with the best R² value</li>
            <li>You can manually override the automatic selection if preferred</li>
        </ul>
        
        <h3>4. Transport Rate Calibration</h3>
        <p>Calibrate the transport efficiency using one of three methods:</p>
        <ul>
            <li>Mass-based method</li>
            <li>Number-based method</li>
            <li>Weighted liquid method</li>
        </ul>
        <p>Reference: Pace et al. (2011) "Determining transport efficiency for the purpose of counting and sizing nanoparticles via single particle inductively coupled plasma-mass spectrometry" Anal Chem 83:9361-9369</p>
        <p>After calibration, you can either average multiple measurements or select the most reliable single calibrated rate.</p>
        
        <h3>5. Configure Mass Fraction and Density</h3>
        <p>For each sample, specify:</p>
        <ul>
            <li>Mass fraction of the target element in the nanoparticles</li>
            <li>Particle density using the built-in materials database</li>
            <li>These parameters are essential for accurate size calculations</li>
        </ul>
        
        <h3>6. Set Detection Parameters</h3>
        <p>Configure detection parameters for each element individually or use batch parameters to apply settings to multiple elements:</p>
        <ul>
            <li>Detection method (Currie, Formula C, Compound Poisson LogNormal, Manual)</li>
            <li>Confidence levels and threshold settings</li>
            <li>minimum peak requirements</li>
            <li>Use batch editing, change the parameters for each isotope</li>
        </ul>
        
        <h3>7. Review Results in Canvas</h3>
        <p>Use the results canvas to visualize and validate your analysis:</p>
        <ul>
            <li>Select specific samples and elements to display</li>
            <li>Choose from various plot types and visualization options</li>
            <li>Adjust parameters as needed based on visual inspection</li>
        </ul>
        
        <h3>8. Export Data</h3>
        <p>Export your results in two formats:</p>
        <ul>
            <li>Summary file: data for all samples and elements</li>
            <li>Details file: Contains individual particle data for each sample</li>
            <li>Both formats include all relevant calibration and parameter information</li>
        </ul>
        """
        return self.create_formatted_text_widget(content)
    
    def create_data_loading_tab(self):
        """
        Create data loading tab content.
        
        Args:
            None
            
        Returns:
            QWidget: Data loading tab widget
        """
        content = """
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
        return self.create_formatted_text_widget(content)
    
    def create_element_selection_tab(self):
        """
        Create element selection tab content.
        
        Args:
            None
            
        Returns:
            QWidget: Element selection tab widget
        """
        content = """
        <h2>Element Selection</h2>
        
        <h3>Using the Periodic Table</h3>
        <p>The interactive periodic table allows you to select elements and specific isotopes for analysis:</p>
        <ol>
            <li>Left-click on an element to select the most abundant, less interference isotope</li>
            <li>Right-click on an element to see all available isotopes and select specific ones</li>
            <li>Right-click again on a selected element to deselect it</li>
            <li>Click "Confirm" to finalize your selection</li>
            <li>Gray elements: Not available in your loaded data</li>
        </ol>
        """
        return self.create_formatted_text_widget(content)
    
    def create_calibration_tab(self):
        """
        Create calibration tab content.
        
        Args:
            None
            
        Returns:
            QWidget: Calibration tab widget
        """
        content = """
        <h2>Calibration Methods</h2>
        
        <h3>Ionic Calibration (Sensitivity)</h3>
        <p>Establishes the relationship between element concentration and instrument response:</p>
        
        <h4>Process:</h4>
        <ol>
            <li>Selected isotopes from the main window appear automatically</li>
            <li>Set up multiple calibration sets</li>
            <li>Use "-1" in the table to exclude samples from specific calibration sets</li>
            <li>System automatically tests three calibration methods:</li>
            <ul>
                <li>Simple Linear: Basic linear regression</li>
                <li>Linear: Linear regression with intercept</li>
                <li>Weighted: Weighted linear regression</li>
            </ul>
            <li>IsotopeTrack selects the method with the best R² value</li>
            <li>You can manually override the automatic selection</li>
        </ol>
        
        <h3>Transport Rate Calibration</h3>
        <p>Determines the efficiency of sample transport to the plasma:</p>
        
        <h4>Three Available Methods:</h4>
        <ul>
            <li>Mass-based method</li>
            <li>Number-based method</li>
            <li>Weighted liquid method</li>
        </ul>
        
        <p>Reference: Pace, H.E., et al. (2011) "Determining transport efficiency for the purpose of counting and sizing nanoparticles via single particle inductively coupled plasma-mass spectrometry" Analytical Chemistry 83:9361-9369</p>
        
        <h4>After Calibration:</h4>
        <ul>
            <li>Calculate the average of multiple transport rate measurements</li>
            <li>Or select the most reliable single calibrated rate</li>
            <li>The chosen value will be used for all subsequent mass and particle concentration calculations</li>
        </ul>
        
        <h3>Mass Fraction and Density Configuration</h3>
        <p>For accurate particle sizing, specify for each sample:</p>
        <ul>
            <li>Mass fraction of the target element in the particles</li>
            <li>Particle density using materials database</li>
        </ul>
        """
        return self.create_formatted_text_widget(content)
    
    def create_parameters_tab(self):
        """
        Create parameters tab content.
        
        Args:
            None
            
        Returns:
            QWidget: Parameters tab widget
        """
        content = """
        <h2>Detection Parameters</h2>
        
        <h3>Element Parameters Table</h3>
        <p>Each element has customizable detection parameters:</p>
        <ul>
            <li>Include: Whether to include the element in analysis</li>
            <li>Method: Detection algorithm (Currie, Formula C, Compound Poisson LogNormal, Manual)</li>
            <li>Min Points: Minimum continuous points above threshold to consider a particle</li>
            <li>Confidence Level: Statistical confidence for threshold determination (99.999% default)</li>
            <li>Smoothing optional</li>
            <li>Alpha error rate</li>
            <li>Iterative threshold calculation</li>
            <li>Window size for threshold calculation</li>
        </ul>
        
        <h3>Detection Methods</h3>
        <h4>Currie Method:</h4>
        <p>Classical approach using Poisson statistics with critical value determination.</p>
        <p>Currie, L.A. J Radioanal Nucl Chem 276, 285–297 (2008)</p>
        
        <h4>Formula C:</h4>
        <p>MARLAP-based method with enhanced statistical balance between false positive and false negative.</p>
        <p>MARLAP Manual Volume III: Chapter 20, Detection and Quantification Capabilities Overview : Formula C 20.52</p>

        
        <h4>Compound Poisson LogNormal:</h4>
        <p>Advanced method accounting for signal distribution characteristics, includes sigma parameter for distribution shape.</p>
        <p>Lockwood, T. E.; Schlatt, L.; Clases, D. SPCal – an open source, easy-to-use processing platform for ICP-TOFMS-based single event data. Journal of Analytical Atomic Spectrometry 2025.</p>
        
        
        <h4>Manual:</h4>
        <p>User-defined threshold.</p>
        
        <h3>Batch Parameter Editing</h3>
        <p>To apply the same parameters to multiple elements:</p>
        <ol>
            <li>Click "Batch Edit Parameters"</li>
            <li>Select elements to modify</li>
            <li>Set parameters that should apply to all selected elements</li>
            <li>Optionally select which samples should receive these parameters</li>
            <li>This is particularly useful when analyzing the same elements across multiple samples</li>
        </ol>
        """
        return self.create_formatted_text_widget(content)
    
    def create_results_tab(self):
        """
        Create results and export tab content.
        
        Args:
            None
            
        Returns:
            QWidget: Results tab widget
        """
        content = """
        <h2>Results Canvas & Visualization</h2>
        
        <h3>Results Canvas</h3>
        <p>The results canvas provides interactive visualization of your analysis:</p>
        <ul>
            <li>Select specific samples from the dropdown menu</li>
            <li>Choose elements to display from available options</li>
            <li>Select different figure types for various visualization needs</li>
            <li>Updates are as you change selections</li>
        </ul>
        
        <h3>Single Element Results</h3>
        <p>The "Single Element Results" tab shows:</p>
        <ul>
            <li>Start and end times of each detected particle</li>
            <li>Total counts for each particle</li>
            <li>Peak height and signal-to-noise ratio</li>
        </ul>
        
        <h3>Particle Results</h3>
        <p>The "Particle Results" tab shows multi-element particles:</p>
        <ul>
            <li>Particle identification numbers</li>
            <li>Temporal overlap information</li>
            <li>Count data for each element in coincident particles</li>
        </ul>
        
        <h3>Data Export Options</h3>
        
        <h4>Summary File Export:</h4>
        <ul>
            <li>data for all samples and elements</li>
            <li>Statistical summaries (mean, median, standard deviation)</li>
            <li>Particle concentrations</li>
            <li>Calibration information and method parameters</li>
            <li>Ideal for comparative analysis</li>
        </ul>
        
        <h4>Details File Export:</h4>
        <ul>
            <li>Individual particle data for each sample</li>
            <li>Complete particle-by-particle information</li>
            <li>Peak characteristics and integration results</li>
        </ul>
        """
        return self.create_formatted_text_widget(content)