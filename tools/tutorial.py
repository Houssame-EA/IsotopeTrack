from PySide6.QtWidgets import (
    QDialog, QTabWidget, QVBoxLayout, QPushButton,
    QLabel, QScrollArea, QWidget, QHBoxLayout, QSizePolicy,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QMovie, QPixmap
from pathlib import Path
import sys

from theme import theme


def get_resource_path(relative_path):
    """
    Args:
        relative_path (Any): The relative path.
    Returns:
        object: Result of the operation.
    """
    try:
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        base_path = Path(__file__).parent.parent
    return base_path / relative_path


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------
def _section(html: str) -> QLabel:
    """Rich-text section label with consistent styling.
    Args:
        html (str): The html.
    Returns:
        QLabel: Result of the operation.
    """
    lbl = QLabel(html)
    lbl.setWordWrap(True)
    lbl.setOpenExternalLinks(True)
    lbl.setTextFormat(Qt.RichText)
    lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    lbl.setStyleSheet(f"font-size:13px; line-height:1.5; color:{theme.palette.text_primary};")
    return lbl


def _gif_widget(filename: str, width: int = 680) -> QWidget:
    """
    Return a widget displaying an animated GIF from the images/ folder.
    Falls back to a styled placeholder if the file is not found.
    Args:
        filename (str): The filename.
        width (int): Width in pixels.
    Returns:
        QWidget: Result of the operation.
    """
    path = get_resource_path(f"images/{filename}")

    container = QWidget()
    lay = QVBoxLayout(container)
    lay.setContentsMargins(0, 8, 0, 8)
    lay.setAlignment(Qt.AlignHCenter)

    if Path(path).exists():
        movie_label = QLabel()
        movie_label.setAlignment(Qt.AlignCenter)
        movie = QMovie(str(path))
        movie.setScaledSize(QSize(width, width * 9 // 16))
        movie_label.setMovie(movie)
        movie.start()
        lay.addWidget(movie_label)
    else:
        p = theme.palette
        placeholder = QLabel(f"[ Animation: {filename} ]")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet(
            f"background:{p.accent_soft}; border:2px dashed {p.accent}; "
            f"border-radius:8px; padding:24px; color:{p.accent}; "
            f"font-size:12px; font-style:italic;"
        )
        placeholder.setMinimumHeight(80)
        lay.addWidget(placeholder)

    return container


def _scroll_tab(*widgets) -> QScrollArea:
    """Wrap a list of widgets in a scrollable tab.
    Args:
        *widgets (Any): Additional positional arguments.
    Returns:
        QScrollArea: Result of the operation.
    """
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)

    scroll.viewport().setAutoFillBackground(False)

    content = QWidget()
    content.setObjectName("tutorialContent")
    content.setAutoFillBackground(True)
    lay = QVBoxLayout(content)
    lay.setContentsMargins(20, 16, 20, 24)
    lay.setSpacing(10)

    for w in widgets:
        lay.addWidget(w)
    lay.addStretch()

    scroll.setWidget(content)
    return scroll


def _hr() -> QLabel:
    """
    Returns:
        QLabel: Result of the operation.
    """
    lbl = QLabel("<hr>")
    lbl.setTextFormat(Qt.RichText)
    return lbl


# ---------------------------------------------------------------------------
#  User guide dialog
# ---------------------------------------------------------------------------
class UserGuideDialog(QDialog):
    """
    User guide dialog — content mirrors the IsotopeTrack README.
    """

    def __init__(self, parent=None):
        """
        Args:
            parent (Any): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("IsotopeTrack — User Guide")
        self.resize(820, 740)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        tabs = QTabWidget()
        tabs.addTab(self._tab_overview(),    "Overview")
        tabs.addTab(self._tab_workflow(),    "Workflow")
        tabs.addTab(self._tab_data(),        "Data Loading")
        tabs.addTab(self._tab_calibration(), "Calibration")
        tabs.addTab(self._tab_parameters(),  "Parameters")
        tabs.addTab(self._tab_results(),     "Results & Export")

        layout.addWidget(tabs)

        btn = QPushButton("Close")
        btn.setFixedWidth(90)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignRight)

        theme.themeChanged.connect(self.apply_theme)
        self.apply_theme()

    def apply_theme(self):
        """Apply the currently active theme palette."""
        p = theme.palette
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {p.bg_primary};
                color: {p.text_primary};
            }}
            QWidget {{
                color: {p.text_primary};
            }}
            QLabel {{
                color: {p.text_primary};
                background-color: transparent;
            }}
            /* The inner widget inside each tab's QScrollArea — without
               this, macOS paints it with its default white surface and
               the tab body stays bright even in dark mode. */
            QWidget#tutorialContent {{
                background-color: {p.bg_secondary};
                color: {p.text_primary};
            }}
            /* The scroll area's viewport is the widget between the scroll
               area and the content — on macOS this one paints white by
               default and hides whatever the content widget is doing. */
            QScrollArea > QWidget > QWidget {{
                background-color: {p.bg_secondary};
            }}
            QTabWidget::pane {{
                border: 1px solid {p.border};
                background-color: {p.bg_secondary};
                border-radius: 6px;
            }}
            QTabBar::tab {{
                background-color: {p.bg_tertiary};
                color: {p.text_secondary};
                border: 1px solid {p.border};
                padding: 8px 14px;
                margin-right: 2px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
            QTabBar::tab:selected {{
                background-color: {p.bg_secondary};
                color: {p.accent};
                font-weight: 600;
                border-bottom: 1px solid {p.bg_secondary};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {p.bg_hover};
            }}
            QScrollArea {{
                border: none;
                background-color: {p.bg_secondary};
            }}
            QScrollBar:vertical {{
                background: {p.bg_secondary};
                width: 10px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {p.border};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {p.text_muted};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QPushButton {{
                background-color: {p.accent};
                color: {p.text_inverse};
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {p.accent_hover};
            }}
        """)
        self._refresh_section_styles()

    def _refresh_section_styles(self):
        """Restyle all _section() labels to use the current palette."""
        for lbl in self.findChildren(QLabel):
            if lbl.textFormat() == Qt.RichText:
                p = theme.palette
                lbl.setStyleSheet(
                    f"font-size:13px; line-height:1.5; "
                    f"color:{p.text_primary}; background:transparent;"
                )

    def closeEvent(self, event):
        """
        Args:
            event (Any): Qt event object.
        """
        try:
            theme.themeChanged.disconnect(self.apply_theme)
        except (TypeError, RuntimeError):
            pass
        super().closeEvent(event)

    # ------------------------------------------------------------------ #
    # Tab: Overview
    # ------------------------------------------------------------------ #
    def _tab_overview(self):
        """
        Returns:
            object: Result of the operation.
        """
        return _scroll_tab(
            _section("""
            <h2>IsotopeTrack v1.0.2</h2>
            <p>A comprehensive software application for analyzing single particle
            ICP-ToF-MS (Inductively Coupled Plasma Time-of-Flight Mass Spectrometry) data.</p>

            <h3>Key Features</h3>
            <ul>
              <li>Multi-isotope particle detection</li>
              <li>Transport rate &amp; ionic calibration</li>
              <li>Support for NU Instruments folders(<code>run.info</code>), TOFWERK files (.h5) and CSV formats</li>
              <li>Interactive visualization and data exploration</li>
              <li>Batch processing capabilities</li>
              <li>Comprehensive export options</li>
            </ul>

            <h3>System Requirements</h3>
            <table cellspacing="6">
              <tr>
                <td><b>macOS</b></td>
                <td>macOS 11.0 (Big Sur) or later &nbsp;·&nbsp;
                    Apple Silicon (M1/M2/M3) recommended &nbsp;·&nbsp;
                    4 GB RAM (8 GB recommended) &nbsp;·&nbsp</td>
              </tr>
              <tr>
                <td><b>Windows</b></td>
                <td>Windows 10 (64-bit) or later &nbsp;·&nbsp;
                    4 GB RAM (8 GB recommended) &nbsp;·&nbsp;</td>
              </tr>
            </table>

            <h3>Citation</h3>
            <p>When using IsotopeTrack in your work, please cite:</p>
            <blockquote>
              Ahabchane H, Goodman A, Hadioui M, Wilkinson K.
              <i>IsotopeTrack: A fast and flexible application for the analysis of
              SP-ICP-TOF-MS datasets.</i>
              Environmental Chemistry 2026; EN25111.<br>
              <a href="https://doi.org/10.1071/EN25111">https://doi.org/10.1071/EN25111</a>
            </blockquote>
            """),
        )

    # ------------------------------------------------------------------ #
    # Tab: Workflow                                                         #
    # ------------------------------------------------------------------ #
    def _tab_workflow(self):
        """
        Returns:
            object: Result of the operation.
        """
        return _scroll_tab(
            _section("""
            <h2>Recommended Workflow</h2>

            <h3>1 · Load Sample Data</h3>
            <p>Click <b>Import Data</b> in the <i>File</i> menu or sidebar.
            Load all samples you plan to analyze in a single session to ensure
            consistent processing parameters.</p>

            <h3>2 · Choose Isotopes</h3>
            <p>Use the periodic table interface to select the isotopes of interest.
            Selected isotopes in the main window are carried automatically into
            the calibration panels.</p>

            <h3>3 · Ionic Calibration (Sensitivity)</h3>
            <p>Configure ionic calibration to convert raw counts to mass.
            Use <code>-1</code> to exclude samples from specific calibration sets.
            IsotopeTrack tests three calibration models and selects the best R².</p>

            <h3>4 · Transport Rate Calibration</h3>
            <p>Calibrate aerosol transport efficiency using one of three methods:
            mass-based, number-based, or weighted liquid.
            Average multiple measurements or select the most reliable single value.</p>

            <h3>5 · Mass Fraction &amp; Density</h3>
            <p>For each sample, specify the mass fraction of the target element
            and the particle density (from the built-in materials database).</p>

            <h3>6 · Set Detection Parameters</h3>
            <p>Configure detection method, confidence level, minimum peak points,
            and optional smoothing for each element individually or via
            <b>Batch Edit Parameters</b>.</p>

            <h3>7 · Review Results in Canvas</h3>
            <p>Use the results canvas to visualize and validate the analysis.
            Adjust parameters as needed based on visual inspection.</p>

            <h3>8 · Export Data</h3>
            <p>Export a <b>summary file</b> (all samples and elements, statistics,
            concentrations, calibration info) and/or a <b>details file</b>
            (individual particle data per sample).</p>
            """),
        )

    # ------------------------------------------------------------------ #
    # Tab: Data Loading                                                    #
    # ------------------------------------------------------------------ #
    def _tab_data(self):
        """
        Returns:
            object: Result of the operation.
        """
        return _scroll_tab(
            _section("""
            <h2>Data Loading</h2>

            <h3>Supported Formats</h3>
            <ul>
              <li><b>Folder with <code>run.info</code></b> — Raw data from TOF Vitesse
                  and multiple files from TOFWERK <code>.h5</code></li>
              <li><b>CSV files</b> — Time-series data</li>
            </ul>

            <h3>Loading Process</h3>
            <ol>
              <li>Click <b>Import Data</b> in the <i>File</i> menu or sidebar</li>
              <li>Select <i>Folder(s) with <code>run.info</code></i>,
                  <i>CSV file(s)</i>, or <i>TOFWERK .h5</i></li>
              <li>Browse to your data location and select one or more folders/files</li>
              <li>The application validates the data and displays loading progress</li>
              <li>Successfully loaded samples appear in the <b>Samples</b> table in the sidebar</li>
            </ol>

            <h3>CSV Format Requirements</h3>
            <ul>
              <li>First column must be <b>Time</b> (units: <code>ms</code>,
                  <code>ns</code>, or <code>s</code>)</li>
              <li>Each element column must include <b>mass number + element symbol</b>
                  (e.g., <code>107Ag</code>)</li>
              <li>Data must be provided in <b>counts</b></li>
            </ul>

            <h3>Sample Management</h3>
            <ul>
              <li>Click a sample in the sidebar to switch between samples</li>
              <li>Right-click a sample to view additional metadata</li>
              <li>Process all samples simultaneously using the same parameters</li>
            </ul>

            <h2>Element Selection</h2>

            <h3>Using the Periodic Table</h3>
            <p>The interactive periodic table allows selection of elements and
            specific isotopes for analysis:</p>
            <ol>
              <li><b>Left-click</b> an element to select the most abundant isotope
                  with minimal interferences</li>
              <li><b>Right-click</b> an element to display all available isotopes
                  and select specific ones</li>
              <li><b>Right-click again</b> on a selected element to deselect it</li>
              <li>Click <b>Confirm</b> to finalize the selection</li>
              <li>Gray elements indicate elements not present in the loaded dataset</li>
            </ol>
            """
            ),
            _gif_widget("1.gif"),
        )

    # ------------------------------------------------------------------ #
    # Tab: Calibration                                                     #
    # ------------------------------------------------------------------ #
    def _tab_calibration(self):
        """
        Returns:
            object: Result of the operation.
        """
        return _scroll_tab(
            _section("""
            <h2>Calibration Methods</h2>

            <h3>Ionic Calibration (Sensitivity)</h3>
            <p>Establishes the relationship between elemental concentration and
            instrument response.</p>

            <h4>Process</h4>
            <ol>
              <li>Selected isotopes are automatically imported from the main window</li>
              <li>Create one or more calibration sets</li>
              <li>Enter <code>-1</code> to exclude samples from specific calibration sets</li>
              <li>The system automatically evaluates three calibration models:
                <ul>
                  <li><b>Simple Linear</b> (no intercept)</li>
                  <li><b>Linear</b> (with intercept)</li>
                  <li><b>Weighted Linear</b></li>
                </ul>
              </li>
              <li>The model with the highest R² is automatically selected</li>
              <li>Manual override is available</li>
            </ol>
            """),
            _hr(),
            _section("""
            <h3>Transport Rate Calibration</h3>
            <p>Determines the efficiency of aerosol transport into the plasma.</p>

            <h4>Available Methods</h4>
            <ul>
              <li>Mass-based method</li>
              <li>Number-based method</li>
              <li>Weighted liquid method</li>
            </ul>

            <p><b>Reference:</b><br>
            Pace, H. E., et al. (2011).
            <i>Determining transport efficiency for the purpose of counting and sizing
            nanoparticles via single-particle ICP-MS.</i>
            Analytical Chemistry, <b>83</b>, 9361–9369.<br>
            <a href="https://doi.org/10.1021/ac201952t">https://doi.org/10.1021/ac201952t</a></p>

            <h4>After Calibration</h4>
            <ul>
              <li>Average multiple transport efficiency measurements, <b>or</b></li>
              <li>Select the most reliable single value</li>
            </ul>
            <p>The chosen transport rate is applied to all subsequent particle mass
            and number concentration calculations.</p>

            <h3>Mass Fraction &amp; Density Configuration</h3>
            <p>For accurate particle sizing, specify for each sample:</p>
            <ul>
              <li>Mass fraction of the target element in the particles</li>
              <li>Particle density selected from the materials database</li>
            </ul>
            """),
            _gif_widget("4.gif"),
        )

    # ------------------------------------------------------------------ #
    # Tab: Parameters                                                      #
    # ------------------------------------------------------------------ #
    def _tab_parameters(self):
        """
        Returns:
            object: Result of the operation.
        """
        return _scroll_tab(
            _section("""
            <h2>Detection Parameters</h2>

            <h3>Element Parameters Table</h3>
            <p>Each element includes customizable detection parameters:</p>
            <ul>
              <li><b>Include</b> — Enable or disable the element in analysis</li>
              <li><b>Method</b> — Detection algorithm (see below)</li>
              <li><b>Min Points</b> — Minimum consecutive points above threshold
                  to define a particle</li>
              <li><b>Confidence Level</b> — Statistical confidence for threshold
                  determination (default: 99.999&nbsp;%)</li>
              <li>Optional smoothing</li>
              <li>Alpha error rate</li>
              <li>Iterative threshold calculation</li>
              <li>Window size for threshold calculation</li>
            </ul>

            <h3>Detection Methods</h3>

            <h4>Compound Poisson Log-Normal</h4>
            <p>Advanced method accounting for signal distribution characteristics;
            includes a sigma parameter describing distribution shape.</p>
            <p><b>Reference:</b> Lockwood, T. E., Schlatt, L., &amp; Clases, D. (2025).
            <i>SPCal – an open-source processing platform for ICP-TOFMS-based
            single-event data.</i>
            J. Anal. At. Spectrom.<br>
            <a href="https://pubs.rsc.org/en/journal/jaas">
            https://pubs.rsc.org/en/journal/jaas</a></p>

            <h4>Manual</h4>
            <p>User-defined threshold value.</p>
            """),
            _gif_widget("2.gif"),
            _hr(),
            _section("""
            <h3>Batch Parameter Editing</h3>
            <p>To apply identical parameters to multiple elements:</p>
            <ol>
              <li>Click <b>Batch Edit Parameters</b></li>
              <li>Select elements to modify</li>
              <li>Define shared parameters</li>
              <li>Optionally select target samples</li>
              <li>Apply settings to all selected elements simultaneously</li>
            </ol>
            <p>Particularly useful when analyzing identical elements across
            multiple samples.</p>
            """),
        )


    def _tab_results(self):
        """
        Returns:
            object: Result of the operation.
        """
        return _scroll_tab(
            _section("""
            <h2>Results Canvas &amp; Visualization</h2>

            <p>The results canvas provides interactive visualization of your analysis:</p>
            <ol>
              <li>Select specific samples from the dropdown menu</li>
              <li>Choose elements to display from available options</li>
              <li>Select different figure types for various visualization needs</li>
              <li>View updates in real time as you change selections</li>
            </ol>
            """),
            _gif_widget("5.gif"),
            _hr(),
            _section("""
            <h3>Single Element Results</h3>
            <p>The <i>Single Element Results</i> tab displays:</p>
            <ul>
              <li>Start and end times of each detected particle</li>
              <li>Total counts for each particle</li>
              <li>Peak height and signal-to-noise ratio</li>
            </ul>

            <h3>Particle Results</h3>
            <p>The <i>Particle Results</i> tab provides multi-element particle info:</p>
            <ul>
              <li>Particle identification numbers</li>
              <li>Temporal overlap information</li>
              <li>Count data for each element in coincident particles</li>
            </ul>

            <h3>Data Export Options</h3>

            <h4>Summary File</h4>
            <ul>
              <li>Data for all samples and elements</li>
              <li>Statistical summaries (mean, median, standard deviation)</li>
              <li>Particle concentrations</li>
              <li>Calibration information and method parameters</li>
              <li>Ideal for comparative analysis across samples</li>
            </ul>

            <h4>Details File</h4>
            <ul>
              <li>Individual particle data for each sample</li>
              <li>Complete particle-by-particle information</li>
              <li>Peak characteristics and integration results</li>
            </ul>
            """),
        )