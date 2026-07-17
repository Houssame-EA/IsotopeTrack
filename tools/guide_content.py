"""Content definitions for the interactive user guide.

Each SECTION contains PAGES; each page shows one screenshot from the
images/ folder with clickable hotspots. Hotspot rectangles are
(x, y, w, h) normalised to the image size (0..1). The 'body' HTML is
shown in the detail panel when the region is clicked.

Rendering is done by tools/interactive_guide.py.
"""

SECTION_MAIN_WINDOW = dict(
    title="Main Window",
    pages=[dict(
        title="Main Window",
        image="mainwindow.png",
        intro="""
        <p>The main window is organised around the <b>sidebar</b>
        (calibration and sample management), the <b>data visualization</b>
        plot, the <b>particle summary statistics</b> panel, and the
        <b>particle peak detection parameters</b>.</p>
        """,
        hotspots=[
            dict(
                id="transport_rate",
                title="Transport Rate",
                rect=(0.036, 0.142, 0.098, 0.033),
                body="""
                <p>Opens the <b>Transport Rate calibration</b> window, which
                determines the efficiency with which the aerosol is
                transported into the plasma. Three methods are available:
                <b>Liquid weight</b>, <b>Mass based</b>, and
                <b>Number based</b> (see the Calibration section of this
                guide).</p>
                <p>The chosen transport rate is applied to all subsequent
                particle mass and number-concentration calculations.</p>
                <p><i>Reference:</i> Pace, H. E., et al. (2011).
                <i>Analytical Chemistry</i>, 83, 9361–9369.</p>
                """),
            dict(
                id="sensitivity",
                title="Sensitivity",
                rect=(0.036, 0.178, 0.098, 0.033),
                body="""
                <p>Opens the <b>Ionic Calibration Analysis</b> window, which
                establishes the relationship between elemental concentration
                and instrument response — converting raw counts into mass.</p>
                <p>Load calibration standards, enter concentrations, and the
                software fits calibration curves per isotope. Enter
                <code>-1</code> to exclude a sample from a calibration set.
                The model with the best R² is selected automatically, with
                manual override available.</p>
                """),
            dict(
                id="show_calibration_info",
                title="Show Calibration Info",
                rect=(0.036, 0.214, 0.098, 0.033),
                body="""
                <p>Opens the <b>Calibration Information</b> dialog summarising
                the current calibration state: which transport-rate methods
                are calibrated and in use, and the full ionic-calibration
                table per isotope (slope, R², LOD, size detection limits…).</p>
                <p>Use it to verify at a glance which calibration values will
                be applied before running detection or exporting.</p>
                """),
            dict(
                id="import_data",
                title="Import Data",
                rect=(0.036, 0.287, 0.098, 0.033),
                body="""
                <p>Loads raw data (also in the <i>File</i> menu, shortcut
                <b>⌘I</b>). Supported sources: <b>Nu Vitesse folders</b>
                (containing <code>run.info</code>), <b>TOFWERK</b>
                <code>.h5</code> files, and <b>delimited data files</b>
                (csv, txt, xls, xlsx, xlsm, xlsb).</p>
                <p>Load all samples for the session at once so they share
                consistent parameters; loaded samples appear in the
                <b>Sample List</b>.</p>
                """),
            dict(
                id="add_edit_elements",
                title="Add/Edit Elements",
                rect=(0.036, 0.323, 0.098, 0.033),
                body="""
                <p>Opens the <b>interactive periodic table</b>:
                <b>left-click</b> an element to select its most abundant
                low-interference isotope, <b>right-click</b> to choose
                specific isotopes, right-click again to deselect.
                Gray elements are not present in the loaded dataset.
                Click <b>Confirm</b> to apply.</p>
                <p>Selected isotopes populate the parameters table and are
                carried into the calibration panels automatically.</p>
                """),
            dict(
                id="results_button",
                title="Results",
                rect=(0.036, 0.359, 0.098, 0.033),
                body="""
                <p>Opens the <b>Workflow Builder</b> results canvas — a
                node-based environment where you connect samples to
                visualizations (histograms, correlations, clustering…).</p>
                <p>This button is <b>highlighted</b> when parameters or the
                signal changed since the last run, reminding you the stored
                results are out of date.</p>
                """),
            dict(
                id="export_button",
                title="Export",
                rect=(0.036, 0.395, 0.098, 0.033),
                body="""
                <p>Opens <b>Export Options</b> (also <b>⌘E</b>). Export
                <b>sample files</b> (particle-by-particle data per sample)
                and/or a <b>summary file</b> (statistics, concentrations and
                calibration info for all samples), for element or particle
                data types.</p>
                """),
            dict(
                id="sample_list",
                title="Sample List",
                rect=(0.030, 0.437, 0.106, 0.475),
                body="""
                <p>Every loaded sample appears here with its <b>name</b> and
                <b>status</b>. <b>Click</b> a sample to make it active — the
                plot, summary statistics and parameters follow.
                <b>Right-click</b> for metadata and actions; navigate with
                the arrow keys.</p>
                """),
            dict(
                id="plot_toolbar",
                title="Plot Toolbar (Time / m/z, info, theme)",
                rect=(0.800, 0.066, 0.155, 0.033),
                body="""
                <p>Controls at the top-right of the plot header:</p>
                <ul>
                  <li><b>◀ / ▶</b> — step through the selected isotopes.</li>
                  <li><b>Grid button</b> — element picker for the displayed
                      isotope.</li>
                  <li><b>Time</b> — raw time trace (default view).</li>
                  <li><b>m/z</b> — mass-spectrum style bar plot.</li>
                  <li><b>ⓘ</b> — information about the current sample.</li>
                  <li><b>🌙</b> — toggle light / dark mode.</li>
                </ul>
                """),
            dict(
                id="plot_area",
                title="Data Visualization",
                rect=(0.158, 0.103, 0.792, 0.360),
                body="""
                <p>Shows the raw signal of the selected isotope — counts per
                dwell time vs. acquisition time. Scroll to zoom, drag to pan.
                After <b>Detect Peaks</b>, the background level, detection
                threshold, integrated points and peak maxima are drawn on the
                signal (see the Elements &amp; Signals section).</p>
                <p>Exclusion regions can be drawn directly on the plot to
                remove time windows from the analysis. Before any data is
                loaded, the <i>Get started</i> card lists importable
                formats.</p>
                """),
            dict(
                id="summary_stats",
                title="Particle Summary Statistics",
                rect=(0.156, 0.479, 0.798, 0.127),
                body="""
                <p>After detection, shows a per-element summary for the
                active sample: number of detected particles, background,
                threshold, and key statistics of the particle signals
                (with masses and concentrations when calibration is
                applied). Select an element to display its statistics.</p>
                """),
            dict(
                id="search_box",
                title="Search / Filter Elements",
                rect=(0.165, 0.664, 0.250, 0.033),
                body="""
                <p>Filters the rows of the parameters table. Typing
                <code>Ag</code> shows only silver isotopes — useful when many
                isotopes are selected.</p>
                """),
            dict(
                id="sigma_controls",
                title="Sigma (Global / Per-Isotope)",
                rect=(0.421, 0.664, 0.162, 0.033),
                body="""
                <p><b>Sigma</b> is the log-normal shape parameter of the
                single-ion signal distribution used by the Compound Poisson
                LogNormal method. <b>Global</b> applies one value (default
                0.55) to every isotope; <b>Per-Isotope</b> uses each
                isotope's sigma from the loaded Single-Ion Distribution,
                falling back to the global value when no SIA data matches.
                Sigma can also be edited per row in the table.</p>
                """),
            dict(
                id="sid_buttons",
                title="Single-Ion Distribution (SIA)",
                rect=(0.590, 0.664, 0.140, 0.033),
                body="""
                <p>Manages the single-ion area distribution used for
                per-isotope sigma: <b>📁 upload</b> from Nu Vitesse or
                TOFWERK data, <b>ⓘ</b> inspect the loaded distribution, and
                <b>🗑</b> clear it. See the Detection section of this guide
                for the full SIA workflow.</p>
                """),
            dict(
                id="parameters_table",
                title="Detection Parameters Table",
                rect=(0.165, 0.706, 0.781, 0.132),
                body="""
                <p>One row per selected isotope:</p>
                <ul>
                  <li><b>Element</b> — the isotope (e.g. ¹⁰⁷Ag).</li>
                  <li><b>Include</b> — enable/disable in the analysis.</li>
                  <li><b>Detection Method</b> — <i>Manual</i>,
                      <i>Compound Poisson LogNormal</i>, or
                      <i>CPLN table</i>.</li>
                  <li><b>Sigma</b> — per-isotope CPLN sigma.</li>
                  <li><b>Manual Threshold</b> — counts threshold for the
                      Manual method.</li>
                  <li><b>Min Points</b> — minimum consecutive points above
                      threshold to accept a particle.</li>
                  <li><b>Alpha (Error Rate)</b> — false-positive rate for the
                      threshold (e.g. 1×10⁻⁶).</li>
                  <li><b>Iterative</b> — iterative background calculation
                      (recommended).</li>
                  <li><b>Window Size</b> — rolling window for local
                      background.</li>
                  <li><b>Integration Method</b> — <i>Background</i>,
                      <i>Threshold</i>, or <i>Midpoint</i>.</li>
                  <li><b>Split Method</b> — <i>No Splitting</i> or
                      <i>1D Watershed</i> for overlapping events.</li>
                  <li><b>Valley Ratio</b> — how deep the valley between two
                      maxima must be for a watershed split.</li>
                </ul>
                <p><i>Tip:</i> Help → Detection Methods offers interactive
                visualizations of each algorithm.</p>
                """),
            dict(
                id="batch_edit",
                title="Batch Edit Parameters",
                rect=(0.165, 0.868, 0.191, 0.032),
                body="""
                <p>Applies identical parameters to multiple elements and
                samples at once — see the Detection section for the full
                dialog.</p>
                """),
            dict(
                id="multi_signal",
                title="Multi-Signal View",
                rect=(0.361, 0.868, 0.191, 0.032),
                body="""
                <p>Opens the <b>Multi-Signal Display</b> selector to plot
                several isotope traces together with detection overlaid —
                ideal for spotting multi-element particles.</p>
                """),
            dict(
                id="detect_peaks",
                title="Detect Peaks",
                rect=(0.557, 0.868, 0.191, 0.032),
                body="""
                <p>Runs particle detection with the current parameters: the
                background and threshold are computed per isotope, events
                above threshold with at least <i>Min Points</i> consecutive
                points are integrated, and optional watershed splitting
                separates overlapping events. Results feed the summary
                panel, the plot overlay, the Workflow Builder and exports.
                Re-run after any parameter or calibration change.</p>
                """),
            dict(
                id="nonlinearity_filter",
                title="Non-linearity Filter",
                rect=(0.753, 0.868, 0.193, 0.032),
                body="""
                <p>Excludes events recorded under non-linear detector
                response, identified from wide, flat-topped peak shapes.
                <b>Left-click</b> toggles the filter; <b>right-click</b>
                opens the configuration menu. The button label shows the
                current state and criterion, e.g.
                <i>OFF (FWHM &gt; 1.5 ms)</i>. See the Detection section for
                details.</p>
                """),
            dict(
                id="status_bar",
                title="Status Bar",
                rect=(0.027, 0.912, 0.950, 0.024),
                body="""
                <p>Shows the application state (<i>Ready</i>, loading,
                detecting…) and a progress bar during long operations.</p>
                """),
        ],
    )],
)

SECTION_GETTING_STARTED = dict(
    title="Getting Started",
    pages=[
        dict(
            title="Welcome Screen",
            image="welcome.png",
            intro="""
            <p>Shown on startup (Help → Welcome Screen brings it back).
            It is the fastest way to begin a session.</p>
            """,
            hotspots=[
                dict(
                    id="import_card",
                    title="Import Data",
                    rect=(0.131, 0.248, 0.231, 0.138),
                    body="""
                    <p>Starts a new analysis by importing raw data — a
                    Nu Vitesse folder, a TOFWERK <code>.h5</code> file, or
                    delimited data files. Equivalent to the sidebar
                    <b>Import Data</b> button.</p>
                    """),
                dict(
                    id="load_card",
                    title="Load Project",
                    rect=(0.388, 0.248, 0.231, 0.138),
                    body="""
                    <p>Opens a saved <code>.itproj</code> project file,
                    restoring samples, selected isotopes, parameters,
                    calibrations and results exactly as saved.</p>
                    """),
                dict(
                    id="new_window_card",
                    title="New Window",
                    rect=(0.642, 0.248, 0.234, 0.138),
                    body="""
                    <p>Starts a fresh, independent session in a new window —
                    useful for working on two datasets side by side.</p>
                    """),
                dict(
                    id="recent",
                    title="Recent Projects",
                    rect=(0.127, 0.446, 0.754, 0.297),
                    body="""
                    <p>Lists recently saved projects; double-click one to
                    reopen it immediately.</p>
                    """),
                dict(
                    id="links",
                    title="Documentation · Paper · GitHub",
                    rect=(0.127, 0.758, 0.478, 0.042),
                    body="""
                    <p>Quick links to the online documentation, the
                    IsotopeTrack publication (Ahabchane et&nbsp;al.,
                    <i>Environmental Chemistry</i> 2026, EN25111), and the
                    source repository.</p>
                    """),
                dict(
                    id="startup_checkbox",
                    title="Show this screen on startup",
                    rect=(0.127, 0.817, 0.343, 0.042),
                    body="""
                    <p>Untick to skip the welcome screen next time; it stays
                    available under Help → Welcome Screen.</p>
                    """),
            ],
        ),
        dict(
            title="Select Data Source",
            image="data_source.png",
            intro="""
            <p>Appears after clicking <b>Import Data</b>: choose the type of
            raw data to load.</p>
            """,
            hotspots=[
                dict(
                    id="radio_nu",
                    title="NU Folders (with run.info files)",
                    rect=(0.129, 0.282, 0.484, 0.049),
                    body="""
                    <p>Raw data from a Nu Instruments Vitesse: select one or
                    more folders each containing a <code>run.info</code>
                    file. Multiple folders are loaded as separate samples
                    for batch processing.</p>
                    """),
                dict(
                    id="radio_files",
                    title="Data Files (csv, txt, xls, xlsx, xlsm, xlsb)",
                    rect=(0.129, 0.337, 0.532, 0.049),
                    body="""
                    <p>Delimited or spreadsheet time-series data. After
                    choosing files you configure column mappings and time
                    settings in the <b>File Import Configuration</b> dialog
                    (next page of this guide).</p>
                    """),
                dict(
                    id="radio_tofwerk",
                    title="TOFWERK Files (*.h5)",
                    rect=(0.129, 0.394, 0.403, 0.049),
                    body="""
                    <p>TofDAQ acquisitions in HDF5 format. Multiple files are
                    supported for batch processing.</p>
                    """),
                dict(
                    id="notes",
                    title="Format notes",
                    rect=(0.153, 0.459, 0.726, 0.194),
                    body="""
                    <p>Reminders for each source type — folders must contain
                    <code>run.info</code>; data files let you configure
                    column mappings and time settings; TOFWERK files come
                    from TofDAQ acquisitions.</p>
                    """),
                dict(
                    id="continue_cancel",
                    title="Continue / Cancel",
                    rect=(0.484, 0.749, 0.389, 0.065),
                    body="""
                    <p><b>Continue</b> opens the file/folder picker for the
                    chosen source type; <b>Cancel</b> closes without
                    importing.</p>
                    """),
            ],
        ),
        dict(
            title="File Import Configuration",
            image="csv_file.png",
            intro="""
            <p>Shown when importing delimited data files. Isotopes are
            auto-detected from column names; you can adjust everything
            before importing.</p>
            """,
            hotspots=[
                dict(
                    id="file_bar",
                    title="File info bar",
                    rect=(0.060, 0.097, 0.878, 0.070),
                    body="""
                    <p>The file being configured, with its detected shape
                    (rows × columns), size and format (e.g. DELIMITED).
                    When several files are imported, each can be configured
                    and the settings applied to all.</p>
                    """),
                dict(
                    id="advanced",
                    title="Advanced file settings",
                    rect=(0.055, 0.180, 0.115, 0.030),
                    body="""
                    <p>Expands delimiter, header-row and decimal-separator
                    options for files that are not detected correctly.</p>
                    """),
                dict(
                    id="time_format",
                    title="Time · Data Format",
                    rect=(0.060, 0.222, 0.579, 0.178),
                    body="""
                    <ul>
                      <li><b>Time column</b> — pick the column holding time,
                          or <i>None — generate from dwell</i> to build the
                          time axis from the dwell time.</li>
                      <li><b>Time unit</b> — seconds, ms or ns.</li>
                      <li><b>Dwell time</b> — calculate from the time data,
                          or enter it manually in ms.</li>
                      <li><b>Data type</b> — the signal unit
                          (<i>Counts</i>).</li>
                    </ul>
                    """),
                dict(
                    id="preview_mapping",
                    title="Preview / column mapping",
                    rect=(0.060, 0.411, 0.579, 0.432),
                    body="""
                    <p>Preview of the parsed table. Isotopes are auto-detected
                    from column names (e.g. <code>107Ag</code>); click the
                    badge above a column to change or unmap it, or
                    <b>+ assign</b> to map an unrecognised column. Errors
                    (like an unreadable file) are reported here.</p>
                    """),
                dict(
                    id="current_mappings",
                    title="Current mappings",
                    rect=(0.645, 0.232, 0.293, 0.551),
                    body="""
                    <p>The list of column → isotope assignments that will be
                    imported. <b>Remove selected</b> unmaps entries;
                    <b>Re-detect isotopes</b> re-runs auto-detection.</p>
                    """),
                dict(
                    id="bottom_buttons",
                    title="Apply to all files / Cancel / Import data",
                    rect=(0.625, 0.862, 0.313, 0.036),
                    body="""
                    <p><b>Apply to all files</b> copies this configuration to
                    every file in the batch; <b>Import data</b> loads the
                    file(s) as samples.</p>
                    """),
            ],
        ),
        dict(
            title="File Menu",
            image="file.png",
            intro="<p>Project and data operations.</p>",
            hotspots=[
                dict(
                    id="new_window",
                    title="New Window (⌘N)",
                    rect=(0.038, 0.109, 0.923, 0.104),
                    body="""
                    <p>Opens an independent IsotopeTrack window with its own
                    samples, parameters and results.</p>
                    """),
                dict(
                    id="import",
                    title="Import Data (⌘I)",
                    rect=(0.038, 0.261, 0.923, 0.109),
                    body="""
                    <p>Opens the Select Data Source dialog to load Nu Vitesse
                    folders, TOFWERK .h5 files or delimited data files.</p>
                    """),
                dict(
                    id="save",
                    title="Save Project (⌘S) / Save Project As (⇧⌘S)",
                    rect=(0.038, 0.378, 0.923, 0.200),
                    body="""
                    <p>Saves the whole session — samples, isotope selection,
                    parameters, calibrations and results — to an
                    <code>.itproj</code> file. <b>Save As…</b> picks a new
                    location.</p>
                    """),
                dict(
                    id="load",
                    title="Load Project (⌘O)",
                    rect=(0.038, 0.587, 0.923, 0.100),
                    body="""
                    <p>Restores a saved <code>.itproj</code> session exactly
                    as it was saved.</p>
                    """),
                dict(
                    id="export",
                    title="Export (⌘E)",
                    rect=(0.038, 0.730, 0.923, 0.117),
                    body="""
                    <p>Opens the Export Options dialog (see the Export
                    section of this guide).</p>
                    """),
            ],
        ),
    ],
)

SECTION_MENUS = dict(
    title="Menus & Settings",
    pages=[
        dict(
            title="View Menu",
            image="view.png",
            intro="<p>Window layout and appearance.</p>",
            hotspots=[
                dict(
                    id="toggle_sidebar",
                    title="Toggle Sidebar (⌘À)",
                    rect=(0.034, 0.109, 0.931, 0.100),
                    body="""
                    <p>Collapses or expands the Tools sidebar to give the
                    plot more room; the arrow button in the sidebar header
                    does the same.</p>
                    """),
                dict(
                    id="results",
                    title="Results (⌘R)",
                    rect=(0.034, 0.222, 0.931, 0.100),
                    body="""
                    <p>Opens the Workflow Builder results canvas, like the
                    sidebar Results button.</p>
                    """),
                dict(
                    id="show_log",
                    title="Show Application Log (⇧⌘L)",
                    rect=(0.034, 0.365, 0.931, 0.100),
                    body="""
                    <p>Opens the log window with every user action, debug
                    message and error of the session (next page of this
                    guide).</p>
                    """),
                dict(
                    id="theme_items",
                    title="Switch to Dark Mode / System Theme",
                    rect=(0.034, 0.513, 0.931, 0.205),
                    body="""
                    <p>Switches between light and dark palettes, or follows
                    the operating-system theme automatically. The moon
                    button in the plot toolbar is a shortcut.</p>
                    """),
                dict(
                    id="full_screen",
                    title="Enter Full Screen",
                    rect=(0.034, 0.735, 0.931, 0.104),
                    body="<p>Expands the window to full screen.</p>"),
            ],
        ),
        dict(
            title="Tools Menu",
            image="tools.png",
            intro="<p>Analysis tools and settings.</p>",
            hotspots=[
                dict(
                    id="isobaric",
                    title="Isobaric Correction (⇧⌘B)",
                    rect=(0.032, 0.104, 0.935, 0.100),
                    body="""
                    <p>Opens the Isobaric Correction dialog to subtract
                    isobaric interferences from analyte signals with
                    per-analyte correction equations (see the Calibration
                    section).</p>
                    """),
                dict(
                    id="add_edit_pt",
                    title="Add/Edit Element PT (⌘T)",
                    rect=(0.032, 0.213, 0.935, 0.100),
                    body="""
                    <p>Opens the periodic table to change the selected
                    isotopes — same as the sidebar button.</p>
                    """),
                dict(
                    id="mass_fraction",
                    title="Mass Fraction Calculator (⇧⌘M)",
                    rect=(0.032, 0.326, 0.935, 0.100),
                    body="""
                    <p>Computes the mass fraction of each element from a
                    compound formula, with molecular weight and density from
                    the built-in materials database (see the Calibration
                    section).</p>
                    """),
                dict(
                    id="sensitivity_item",
                    title="Sensitivity (⇧⌘I)",
                    rect=(0.032, 0.439, 0.935, 0.100),
                    body="""
                    <p>Opens the Ionic Calibration Analysis window — same as
                    the sidebar Sensitivity button.</p>
                    """),
                dict(
                    id="dilution_item",
                    title="Dilution Factor (⇧⌘D)",
                    rect=(0.032, 0.552, 0.935, 0.100),
                    body="""
                    <p>Sets a dilution factor per sample so reported
                    particles/mL are corrected for sample dilution (see the
                    Calibration section).</p>
                    """),
                dict(
                    id="autosave_item",
                    title="Auto Save Settings (⇧⌘S)",
                    rect=(0.032, 0.696, 0.935, 0.113),
                    body="""
                    <p>Configures automatic project saving (next page of
                    this guide).</p>
                    """),
            ],
        ),
        dict(
            title="Help Menu",
            image="help.png",
            intro="<p>Documentation, learning tools and updates.</p>",
            hotspots=[
                dict(
                    id="welcome_screen",
                    title="Welcome Screen",
                    rect=(0.025, 0.270, 0.950, 0.096),
                    body="<p>Reopens the startup welcome screen.</p>"),
                dict(
                    id="user_guide",
                    title="User Guide",
                    rect=(0.025, 0.409, 0.950, 0.100),
                    body="""
                    <p>Opens this guide — including the interactive
                    screenshots you are reading now.</p>
                    """),
                dict(
                    id="detection_methods",
                    title="Detection Methods",
                    rect=(0.025, 0.517, 0.950, 0.100),
                    body="""
                    <p>Interactive explanations of the detection algorithms:
                    a signal simulator, peak integration, iterative
                    threshold, watershed splitting and the CPLN lookup
                    table.</p>
                    """),
                dict(
                    id="calibration_methods",
                    title="Equations",
                    rect=(0.025, 0.626, 0.950, 0.100),
                    body="""
                    <p>Opens the <b>Equations</b> window (previously called
                    <i>Calibration Methods</i>): every equation used in the
                    project rendered in LaTeX, grouped into Sensitivity,
                    Transport Rate, Detection &amp; SIA, Quantification and
                    Clustering. Each equation comes with a description, a
                    definition of every parameter, a worked numerical
                    example, and clickable citations that jump to full
                    references with links to the studies.</p>
                    """),
                dict(
                    id="updates",
                    title="Check for Updates…",
                    rect=(0.025, 0.761, 0.950, 0.113),
                    body="""
                    <p>Checks online whether a newer IsotopeTrack version is
                    available.</p>
                    """),
            ],
        ),
        dict(
            title="Auto Save Settings",
            image="auto-save.png",
            intro="""
            <p>Automatic background saving of the current project
            (Tools → Auto Save Settings).</p>
            """,
            hotspots=[
                dict(
                    id="enable",
                    title="Enable automatic saving",
                    rect=(0.159, 0.274, 0.529, 0.071),
                    body="""
                    <p>Turns auto-save on. The project must have been saved
                    once so IsotopeTrack knows the target file.</p>
                    """),
                dict(
                    id="interval",
                    title="Save every (h / min)",
                    rect=(0.165, 0.413, 0.529, 0.113),
                    body="""
                    <p>The saving interval in hours and minutes. The minimum
                    interval is 30 seconds; zero hours and zero minutes
                    defaults to 30 s.</p>
                    """),
                dict(
                    id="ok_cancel",
                    title="OK / Cancel",
                    rect=(0.540, 0.677, 0.297, 0.097),
                    body="<p>Applies or discards the auto-save settings.</p>"),
            ],
        ),
        dict(
            title="Application Log",
            image="log.png",
            intro="""
            <p>Every user action, debug message and error of the session
            (View → Show Application Log). Invaluable when reporting an
            issue.</p>
            """,
            hotspots=[
                dict(
                    id="filters",
                    title="Level / Action / Module filters",
                    rect=(0.119, 0.084, 0.369, 0.034),
                    body="""
                    <p>Restrict the list by severity (USER, DEBUG, ERROR…),
                    action type, or the module that emitted the message.</p>
                    """),
                dict(
                    id="search",
                    title="Search messages",
                    rect=(0.492, 0.084, 0.135, 0.034),
                    body="<p>Free-text filter over the log messages.</p>"),
                dict(
                    id="next_error",
                    title="Next Error",
                    rect=(0.630, 0.084, 0.076, 0.034),
                    body="""
                    <p>Jumps to the next ERROR entry; the window title shows
                    how many new errors were recorded.</p>
                    """),
                dict(
                    id="toolbar_right",
                    title="Copy · Auto-scroll · Wrap · clear/save/export",
                    rect=(0.711, 0.084, 0.244, 0.034),
                    body="""
                    <p><b>Copy</b> puts the visible log on the clipboard;
                    <b>Auto-scroll</b> follows new entries; <b>Wrap</b>
                    wraps long lines. The icon buttons clear the log, save
                    it, export it, and toggle the theme.</p>
                    """),
                dict(
                    id="log_list",
                    title="Log entries",
                    rect=(0.041, 0.121, 0.921, 0.588),
                    body="""
                    <p>Timestamped entries: user actions (clicks, menu
                    choices, sample selections), file operations, analysis
                    steps, debug details and errors (in red). <b>W1</b>
                    identifies the window that generated the entry.</p>
                    """),
                dict(
                    id="stack_trace",
                    title="Context / Stack Trace",
                    rect=(0.041, 0.734, 0.921, 0.151),
                    body="""
                    <p>Selecting an error shows its full context and Python
                    stack trace here — copy it into bug reports.</p>
                    """),
                dict(
                    id="counters",
                    title="Session counters",
                    rect=(0.041, 0.890, 0.271, 0.028),
                    body="""
                    <p>Totals per category (debug, info, warnings, errors,
                    user actions) plus the session duration.</p>
                    """),
            ],
        ),
    ],
)

SECTION_ELEMENTS_SIGNALS = dict(
    title="Elements & Signals",
    pages=[
        dict(
            title="Periodic Table",
            image="periodic_table.png",
            intro="""
            <p>Choose the isotopes to analyze
            (sidebar → Add/Edit Elements, or Tools → Add/Edit Element PT).</p>
            """,
            hotspots=[
                dict(
                    id="table",
                    title="Element grid",
                    rect=(0.057, 0.123, 0.898, 0.711),
                    body="""
                    <p><b>Left-click</b> an element to select its most
                    abundant isotope with minimal interferences.
                    <b>Right-click</b> to list all isotopes present in the
                    dataset and pick specific ones; right-click again to
                    deselect. <b>Gray</b> elements are not present in the
                    loaded data. Colors mark selected elements, and each
                    tile shows the atomic number and mass.</p>
                    """),
                dict(
                    id="preset",
                    title="Preset list",
                    rect=(0.062, 0.838, 0.157, 0.042),
                    body="""
                    <p>Name the current selection to save it as a preset,
                    then reload it in any session with <b>Load</b>.</p>
                    """),
                dict(
                    id="preset_buttons",
                    title="Clear All / Save / Load",
                    rect=(0.223, 0.838, 0.155, 0.042),
                    body="""
                    <p><b>Clear All</b> deselects everything; <b>Save</b> /
                    <b>Load</b> store and restore named isotope presets.</p>
                    """),
                dict(
                    id="confirm",
                    title="Confirm",
                    rect=(0.384, 0.838, 0.062, 0.042),
                    body="""
                    <p>Applies the selection: the parameters table, plot
                    element picker and calibration panels are updated.</p>
                    """),
            ],
        ),
        dict(
            title="Signal View",
            image="signal.png",
            intro="""
            <p>The main plot after running <b>Detect Peaks</b> — the full
            time trace of one isotope with the detection overlay.</p>
            """,
            hotspots=[
                dict(
                    id="trace",
                    title="Signal trace with detected particles",
                    rect=(0.047, 0.025, 0.778, 0.835),
                    body="""
                    <p>The blue line is the raw counts-per-dwell signal.
                    Detected particle events are marked by <b>green peak
                    maxima</b> and <b>orange integrated points</b> (the dwell
                    points summed into the particle signal). Scroll to zoom
                    in on any region; the threshold and background lines
                    become visible at closer zoom.</p>
                    """),
                dict(
                    id="legend",
                    title="Legend",
                    rect=(0.831, 0.063, 0.163, 0.481),
                    body="""
                    <ul>
                      <li><b>Mass trace</b> — the raw isotope signal.</li>
                      <li><b>Background Level</b> — estimated baseline.</li>
                      <li><b>Detection Threshold</b> — computed from the
                          chosen method and alpha.</li>
                      <li><b>Integrated points</b> — dwell points counted
                          into each particle.</li>
                      <li><b>Peak Maximum</b> — the apex of each detected
                          particle.</li>
                    </ul>
                    """),
            ],
        ),
        dict(
            title="Zoomed Peak",
            image="signal_zoom.png",
            intro="""
            <p>Zooming into a single particle event shows exactly how it was
            detected and integrated.</p>
            """,
            hotspots=[
                dict(
                    id="peak",
                    title="A single particle event",
                    rect=(0.311, 0.025, 0.373, 0.809),
                    body="""
                    <p>The transient lasts a fraction of a millisecond. Every
                    orange point above the threshold is integrated into the
                    particle's total counts; the green dot is the peak
                    maximum used for peak-height statistics.</p>
                    """),
                dict(
                    id="threshold_lines",
                    title="Background and threshold lines",
                    rect=(0.047, 0.674, 0.778, 0.110),
                    body="""
                    <p>The gray dashed line is the estimated background; the
                    red dashed line is the detection threshold. Points must
                    exceed the threshold for at least <i>Min Points</i>
                    consecutive dwells to count as a particle.</p>
                    """),
            ],
        ),
        dict(
            title="Highlighted Peak",
            image="element_signal.png",
            intro="""
            <p>Selecting a row in the <b>Single Element Results</b> table
            highlights the corresponding particle in the plot.</p>
            """,
            hotspots=[
                dict(
                    id="highlighted",
                    title="Highlighted particle",
                    rect=(0.349, 0.068, 0.343, 0.745),
                    body="""
                    <p>The red segment marks the particle currently selected
                    in the results table, so you can visually validate every
                    detection: its start/end, integrated points and
                    maximum.</p>
                    """),
                dict(
                    id="legend",
                    title="Legend",
                    rect=(0.848, 0.056, 0.147, 0.485),
                    body="""
                    <p>Identical to the signal view, plus
                    <b>Highlighted Peak</b> — the particle selected in the
                    results table.</p>
                    """),
            ],
        ),
        dict(
            title="Multi-Signal Display",
            image="multi_signal_display.png",
            intro="""
            <p>Opened from <b>Multi-Signal View</b> in the main window:
            choose samples and isotopes to plot together.</p>
            """,
            hotspots=[
                dict(
                    id="samples",
                    title="Samples panel",
                    rect=(0.103, 0.092, 0.382, 0.755),
                    body="""
                    <p>Tick the samples to display (the counter shows how
                    many are selected). <b>Select all</b> / <b>Clear</b>
                    apply to the whole list.</p>
                    """),
                dict(
                    id="elements",
                    title="Elements panel",
                    rect=(0.506, 0.092, 0.393, 0.755),
                    body="""
                    <p>Tick the isotopes to plot; each has its own trace
                    color (shown in the swatch). The filter box narrows long
                    lists.</p>
                    """),
                dict(
                    id="buttons",
                    title="Plot Signals",
                    rect=(0.559, 0.870, 0.343, 0.041),
                    body="""
                    <p>Opens the combined plot with particle detection
                    overlaid on every selected trace — ideal for comparing
                    isotopes and spotting coincident particles.</p>
                    """),
            ],
        ),
        dict(
            title="Multi-Element Particle",
            image="particle_signal.png",
            intro="""
            <p>The multi-signal plot zoomed on one particle detected in
            several isotopes at once.</p>
            """,
            hotspots=[
                dict(
                    id="particle_window",
                    title="Coincident particle window",
                    rect=(0.498, 0.011, 0.059, 0.835),
                    body="""
                    <p>The shaded band marks one particle's time window. All
                    isotope traces peaking inside it belong to the same
                    physical particle — here Fe, Si, Pb, Al, Cu and Ti
                    coincide.</p>
                    """),
                dict(
                    id="composition",
                    title="Particle composition box",
                    rect=(0.063, 0.327, 0.091, 0.388),
                    body="""
                    <p>Summary of the selected particle: its number,
                    duration, and integrated counts per isotope, sorted by
                    contribution.</p>
                    """),
                dict(
                    id="legend",
                    title="Legend with counts",
                    rect=(0.866, 0.056, 0.127, 0.433),
                    body="""
                    <p>Each isotope's trace color with its integrated counts
                    for the selected particle.</p>
                    """),
            ],
        ),
    ],
)

SECTION_DETECTION = dict(
    title="Detection",
    pages=[
        dict(
            title="Batch Edit Parameters",
            image="Batch_parameters.png",
            intro="""
            <p>Apply identical detection parameters to many elements and
            samples at once.</p>
            """,
            hotspots=[
                dict(
                    id="samples",
                    title="Samples list",
                    rect=(0.099, 0.106, 0.382, 0.322),
                    body="""
                    <p>Tick the samples to modify; <b>Select all</b> targets
                    the whole session.</p>
                    """),
                dict(
                    id="elements",
                    title="Elements list",
                    rect=(0.519, 0.106, 0.382, 0.322),
                    body="""
                    <p>Tick the isotopes whose parameters should change; the
                    filter box narrows the list.</p>
                    """),
                dict(
                    id="param_settings",
                    title="Parameter Settings",
                    rect=(0.099, 0.444, 0.813, 0.144),
                    body="""
                    <p>The shared values: include/exclude the elements in
                    the analysis, the <b>Detection Method</b> (Manual, CPLN,
                    CPLN table) and <b>iterative thresholding</b>
                    (recommended).</p>
                    """),
                dict(
                    id="advanced",
                    title="Advanced",
                    rect=(0.099, 0.598, 0.813, 0.258),
                    body="""
                    <p>The remaining per-element settings: <b>Minimum
                    Points</b>, <b>Alpha</b>, optional <b>Custom Window
                    Size</b>, <b>Integration Method</b> (Background /
                    Threshold / Midpoint), <b>Split Method</b> (No Splitting
                    / 1D Watershed) and <b>Valley Ratio</b>.</p>
                    """),
                dict(
                    id="ok",
                    title="OK / Cancel",
                    rect=(0.640, 0.861, 0.272, 0.038),
                    body="""
                    <p><b>OK</b> writes the settings to every selected
                    element in every selected sample simultaneously.</p>
                    """),
            ],
        ),
        dict(
            title="SIA — Loading",
            image="SIA_message.png",
            intro="""
            <p>Clicking the SIA upload button (📁) in the main window asks
            which data to load for the single-ion area calculation.</p>
            """,
            hotspots=[
                dict(
                    id="text",
                    title="Data type question",
                    rect=(0.148, 0.276, 0.704, 0.276),
                    body="""
                    <p>The single-ion distribution is measured from a
                    dedicated acquisition: a <b>Nu Vitesse folder</b>
                    (containing run.info) or a single <b>TOFWERK .h5</b>
                    file.</p>
                    """),
                dict(
                    id="buttons",
                    title="Vitesse Folder / TOFWERK .h5 / Cancel",
                    rect=(0.167, 0.569, 0.694, 0.117),
                    body="""
                    <p>Choose the instrument type; a picker opens and
                    processing runs in the background with progress in the
                    status bar.</p>
                    """),
            ],
        ),
        dict(
            title="SIA — Loaded",
            image="SIA_results.png",
            intro="<p>Confirmation shown when SIA processing finishes.</p>",
            hotspots=[
                dict(
                    id="info",
                    title="Result summary",
                    rect=(0.291, 0.211, 0.583, 0.434),
                    body="""
                    <p>Instrument, source sample, number of distribution
                    points, the calculated global <b>σ</b> and the mean
                    signal. The real single-ion distribution is now applied
                    to the analysis: the ⓘ and 🗑 SIA buttons become
                    active, and <b>Per-Isotope</b> sigma can be enabled.</p>
                    """),
            ],
        ),
        dict(
            title="SIA — Distribution",
            image="SIA_1.png",
            intro="""
            <p>The ⓘ button opens Single-Ion Distribution Information —
            here the <b>Individual Distribution</b> view.</p>
            """,
            hotspots=[
                dict(
                    id="info_table",
                    title="Summary table",
                    rect=(0.068, 0.119, 0.225, 0.138),
                    body="""
                    <p>Sample name, calculated global σ, number of
                    distribution points, and mean signal of the single-ion
                    data.</p>
                    """),
                dict(
                    id="toolbar",
                    title="Export CSV · Export Plot · Q-Q Plot · Overlays",
                    rect=(0.068, 0.271, 0.635, 0.037),
                    body="""
                    <p>Export the distribution data or figure, open a Q-Q
                    plot to judge log-normality, and load/clear an overlay
                    distribution for comparison.</p>
                    """),
                dict(
                    id="assign",
                    title="Assign Per-Mass σ",
                    rect=(0.773, 0.271, 0.160, 0.037),
                    body="""
                    <p>Writes each isotope's fitted σ into the parameters
                    table — the table rows are highlighted to show they now
                    carry SIA-derived sigma values.</p>
                    """),
                dict(
                    id="mass_select",
                    title="View individual mass",
                    rect=(0.068, 0.319, 0.446, 0.037),
                    body="""
                    <p>Pick a specific m/z to inspect its own single-ion
                    distribution instead of the global one.</p>
                    """),
                dict(
                    id="view_type",
                    title="View Type / Exclude outliers",
                    rect=(0.068, 0.367, 0.468, 0.034),
                    body="""
                    <p>Switch between <b>Individual Distribution</b> and
                    <b>Sigma Comparison</b>; optionally exclude flagged
                    outlier masses from the global σ.</p>
                    """),
                dict(
                    id="plot",
                    title="Distribution histogram",
                    rect=(0.068, 0.410, 0.863, 0.447),
                    body="""
                    <p>The single-ion area histogram with its log-normal fit
                    (red) and fitted σ. The dashed line marks the
                    0.9999<sup>th</sup> quantile of the distribution.</p>
                    """),
            ],
        ),
        dict(
            title="SIA — Sigma Comparison",
            image="SIA_2.png",
            intro="""
            <p>The <b>Sigma Comparison</b> view plots the fitted σ of every
            measured mass.</p>
            """,
            hotspots=[
                dict(
                    id="plot",
                    title="σ vs m/z scatter",
                    rect=(0.068, 0.410, 0.863, 0.447),
                    body="""
                    <p>Each point is one mass's fitted σ. The solid line is
                    the mean σ, dashed lines mark ±1 SD and dotted lines
                    ±2 SD (with a Shapiro normality p-value). Masses outside
                    ±2 SD are flagged red as outliers and can be excluded
                    from the global σ with the checkbox above.</p>
                    """),
                dict(
                    id="view_type",
                    title="View Type radios",
                    rect=(0.068, 0.367, 0.468, 0.034),
                    body="""
                    <p>Return to <b>Individual Distribution</b> or stay in
                    <b>Sigma Comparison</b>; <b>Exclude outliers from global
                    σ</b> recomputes the global value without flagged
                    masses.</p>
                    """),
            ],
        ),
        dict(
            title="Non-linearity Filter Settings",
            image="filter_non_linear.png",
            intro="""
            <p>Right-click the Non-linearity Filter button →
            <b>Configure filter…</b>. Events recorded under non-linear
            detector response are identified from their peak shape.</p>
            """,
            hotspots=[
                dict(
                    id="description",
                    title="How it works",
                    rect=(0.146, 0.168, 0.707, 0.229),
                    body="""
                    <p>A saturated response stays wide at the top instead of
                    narrowing like a normal particle transient. When any
                    isotope shows such a peak, the whole time window is
                    excluded for <b>all</b> isotopes, and the excluded time
                    is subtracted from the analysis time used for particle
                    number concentrations.</p>
                    """),
                dict(
                    id="fwhm",
                    title="Maximum peak FWHM",
                    rect=(0.152, 0.404, 0.537, 0.057),
                    body="""
                    <p>Peaks wider than this full-width-at-half-maximum
                    (default 1.5 ms) are candidates for exclusion.</p>
                    """),
                dict(
                    id="snr",
                    title="Minimum peak SNR to flag",
                    rect=(0.152, 0.486, 0.512, 0.057),
                    body="""
                    <p>Only strong peaks (signal-to-noise above this value,
                    default 10) can be flagged — prevents noise from
                    triggering exclusions.</p>
                    """),
                dict(
                    id="flattop",
                    title="Minimum flat-top ratio (W_top/FWHM)",
                    rect=(0.152, 0.564, 0.596, 0.057),
                    body="""
                    <p>The width of the peak's top relative to its FWHM. A
                    high ratio (default 0.50) means the peak is flat-topped —
                    the signature of detector saturation.</p>
                    """),
                dict(
                    id="topwidth",
                    title="Top width measured at (% of max)",
                    rect=(0.152, 0.644, 0.557, 0.057),
                    body="""
                    <p>The height (default 90&nbsp;% of the maximum) at which
                    the top width is measured for the flat-top ratio.</p>
                    """),
                dict(
                    id="highlight",
                    title="Highlight filtered particles in the plot",
                    rect=(0.146, 0.716, 0.566, 0.042),
                    body="""
                    <p>Marks excluded events in red in the signal plot so you
                    can review what the filter removed.</p>
                    """),
            ],
        ),
        dict(
            title="Filtered Peak Example",
            image="non-linear.png",
            intro="""
            <p>A 56Fe trace with the non-linearity filter active.</p>
            """,
            hotspots=[
                dict(
                    id="flat_peak",
                    title="Non-linear (filtered) event",
                    rect=(0.370, 0.063, 0.081, 0.835),
                    body="""
                    <p>This event is intense and <b>flat-topped / doubled</b>
                    — the detector response was non-linear. It is marked red
                    and excluded from results, summaries and exports for all
                    isotopes, and its duration is removed from the analysis
                    time.</p>
                    """),
                dict(
                    id="accepted",
                    title="Accepted particles",
                    rect=(0.457, 0.418, 0.096, 0.392),
                    body="""
                    <p>Normal, sharp transients keep their green peak-maximum
                    markers and stay in the analysis.</p>
                    """),
                dict(
                    id="legend",
                    title="Legend",
                    rect=(0.829, 0.063, 0.163, 0.544),
                    body="""
                    <p>Adds <b>Non-linear (filtered)</b> — red markers on
                    events excluded by the filter.</p>
                    """),
            ],
        ),
        dict(
            title="Filter Menu",
            image="non_linear_dialogue.png",
            intro="""
            <p>Right-clicking the Non-linearity Filter button shows this
            menu.</p>
            """,
            hotspots=[
                dict(
                    id="configure",
                    title="Configure filter…",
                    rect=(0.022, 0.070, 0.956, 0.226),
                    body="""
                    <p>Opens the Detector Non-linearity Filter Settings
                    dialog (previous page).</p>
                    """),
                dict(
                    id="highlight",
                    title="Highlight filtered particles in plot",
                    rect=(0.022, 0.296, 0.956, 0.217),
                    body="""
                    <p>Toggles the red highlighting of excluded events in
                    the signal plot.</p>
                    """),
                dict(
                    id="excluded",
                    title="Excluded summary",
                    rect=(0.022, 0.591, 0.956, 0.278),
                    body="""
                    <p>Live count of excluded events and the total excluded
                    analysis time for the current sample.</p>
                    """),
            ],
        ),
    ],
)

SECTION_CALIBRATION = dict(
    title="Calibration",
    pages=[
        dict(
            title="Ionic Cal. — Data",
            image="calibration_1.png",
            intro="""
            <p>The <b>Ionic Calibration Analysis</b> window
            (sidebar → Sensitivity), <b>Data Management</b> tab: load
            calibration standards and set their concentrations.</p>
            """,
            hotspots=[
                dict(
                    id="toolbar",
                    title="Load Folders · Sessions · Calculate · Unit",
                    rect=(0.030, 0.063, 0.290, 0.028),
                    body="""
                    <p><b>Load Folders</b> imports the calibration standard
                    acquisitions. <b>Save/Load Session</b> stores the whole
                    calibration setup for reuse. <b>Calculate</b> fits the
                    calibration curves. <b>Select Elements</b> opens the
                    periodic table to add isotope columns, and <b>Unit</b>
                    sets the concentration unit (e.g. ppb).</p>
                    """),
                dict(
                    id="tabs",
                    title="Data Management / Manual Sensitivity / Results",
                    rect=(0.033, 0.138, 0.216, 0.031),
                    body="""
                    <p>The three stages: enter data and concentrations,
                    optionally type sensitivities manually, and review the
                    fitted calibration curves.</p>
                    """),
                dict(
                    id="samples_table",
                    title="Calibration Samples table",
                    rect=(0.044, 0.229, 0.911, 0.315),
                    body="""
                    <p>One row per loaded standard, one column per isotope.
                    Enter each standard's concentration for every isotope.
                    Enter <code>-1</code> to exclude a sample from that
                    isotope's calibration. Right-click for additional
                    options.</p>
                    """),
                dict(
                    id="fill_buttons",
                    title="Fill Selected with -1 / Auto-Fill Concentrations",
                    rect=(0.044, 0.544, 0.177, 0.026),
                    body="""
                    <p>Shortcuts for large tables: exclude the selected
                    cells, or auto-fill concentrations detected from sample
                    names.</p>
                    """),
                dict(
                    id="plot",
                    title="Count vs Time plot",
                    rect=(0.038, 0.584, 0.922, 0.328),
                    body="""
                    <p>Displays the raw counts of the selected standard over
                    time so you can verify signal stability before
                    calibrating (dropdown switches the displayed
                    quantity).</p>
                    """),
                dict(
                    id="back",
                    title="Back to Main",
                    rect=(0.893, 0.101, 0.074, 0.037),
                    body="""
                    <p>Returns to the main window; the calibration is kept
                    and visible via <b>Show Calibration Info</b>.</p>
                    """),
            ],
        ),
        dict(
            title="Ionic Cal. — Results",
            image="calibration_2.png",
            intro="""
            <p>The <b>Calibration Results</b> tab after clicking
            <b>Calculate</b>: inspect and refine each isotope's fit.</p>
            """,
            hotspots=[
                dict(
                    id="controls",
                    title="Isotope · Method · Apply to All · Include all",
                    rect=(0.044, 0.212, 0.532, 0.030),
                    body="""
                    <p>Step through isotopes and choose the fit per isotope:
                    <b>Force through zero</b>, linear with intercept, or
                    weighted — or <b>Auto (Best R²)</b> applied to all.
                    <b>Include all</b> restores excluded points; clicking a
                    point in the plot excludes it from the fit.</p>
                    """),
                dict(
                    id="plot",
                    title="Calibration plot",
                    rect=(0.038, 0.249, 0.920, 0.363),
                    body="""
                    <p>Signal (cps) vs concentration with the fitted line,
                    its equation and R². Error bars show the signal spread;
                    blue points are included, crossed points excluded.
                    Click a point to toggle its inclusion.</p>
                    """),
                dict(
                    id="results_table",
                    title="Calibration Results table",
                    rect=(0.044, 0.699, 0.911, 0.205),
                    body="""
                    <p>Per isotope: method, slope (cps/conc), intercept,
                    BEC, R², density, LOD and LOQ. <b>Filter Results</b>
                    narrows the list; <b>Export Results</b> saves it.</p>
                    """),
            ],
        ),
        dict(
            title="Transport — Liquid Weight",
            image="TE.png",
            intro="""
            <p>The <b>Transport Rate Calibration</b> window
            (sidebar → Transport Rate) with the <b>Liquid weight</b>
            method.</p>
            """,
            hotspots=[
                dict(
                    id="method_select",
                    title="Select Method",
                    rect=(0.089, 0.129, 0.062, 0.028),
                    body="""
                    <p>Switch between <b>Liquid weight</b>, <b>Mass based</b>
                    and <b>Number based</b> transport-rate methods — each has
                    its own workflow page in this guide.</p>
                    """),
                dict(
                    id="step1",
                    title="1 · Weight Method Calibration",
                    rect=(0.058, 0.208, 0.885, 0.212),
                    body="""
                    <p>The weight method measures the sample uptake directly:
                    weigh the sample vial (and optionally the waste
                    container) before and after a timed aspiration. It gives
                    the liquid flow to the nebulizer.</p>
                    """),
                dict(
                    id="step2",
                    title="2 · Enter Measurements",
                    rect=(0.058, 0.433, 0.885, 0.223),
                    body="""
                    <p>Choose the mass and time units, then enter the
                    initial and final sample mass, the waste-container mass,
                    and the analysis time.</p>
                    """),
                dict(
                    id="step3",
                    title="3 · Calculate Transport Rate",
                    rect=(0.058, 0.698, 0.885, 0.135),
                    body="""
                    <p>The preview shows the computed rate from your
                    measurements; <b>Calculate Transport Rate</b> stores it
                    as the Weight Method result.</p>
                    """),
                dict(
                    id="known_rate",
                    title="Or enter known rate (Submit Direct)",
                    rect=(0.063, 0.844, 0.223, 0.030),
                    body="""
                    <p>If the transport rate is already known (µL/s), type it
                    and <b>Submit Direct</b> — no measurements needed.</p>
                    """),
            ],
        ),
        dict(
            title="Transport — Mass Based",
            image="TE_mass_based.png",
            intro="""
            <p>The <b>Mass based</b> method uses a reference particle
            standard of known mass (Pace et&nbsp;al., 2011).</p>
            """,
            hotspots=[
                dict(
                    id="step1",
                    title="1 · Sample Data",
                    rect=(0.050, 0.192, 0.890, 0.258),
                    body="""
                    <p><b>Select Particle Folders</b> — load acquisitions of
                    the reference particle standard; each folder is one
                    measurement.</p>
                    """),
                dict(
                    id="step2",
                    title="2 · Element Selection",
                    rect=(0.050, 0.470, 0.890, 0.070),
                    body="""
                    <p>Open the periodic table and pick the element of the
                    reference particles (right-click for a specific
                    isotope).</p>
                    """),
                dict(
                    id="step3",
                    title="3 · Detection Parameters",
                    rect=(0.050, 0.549, 0.890, 0.254),
                    body="""
                    <p>Configure detection per sample — the same parameter
                    columns as the main window (method, min points, alpha,
                    sigma…). A <b>Global Method</b> can be applied to all
                    samples at once. Click a row to preview its signal
                    below.</p>
                    """),
                dict(
                    id="detect",
                    title="Detect Particles for All Samples",
                    rect=(0.057, 0.808, 0.876, 0.031),
                    body="""
                    <p>Runs detection on every loaded standard; the transport
                    efficiency is then computed from the known particle mass
                    and the measured particle signals.</p>
                    """),
                dict(
                    id="signal_viz",
                    title="Signal Visualization",
                    rect=(0.050, 0.852, 0.890, 0.070),
                    body="""
                    <p>Preview of the selected sample's signal with the
                    current detection parameters — verify the threshold
                    before calculating.</p>
                    """),
            ],
        ),
        dict(
            title="Transport — Number Based",
            image="TE_number_based.png",
            intro="""
            <p>The <b>Number based</b> method uses a reference particle
            standard of known number concentration (Pace et&nbsp;al.,
            2011).</p>
            """,
            hotspots=[
                dict(
                    id="step1",
                    title="1 · Sample Data",
                    rect=(0.050, 0.192, 0.890, 0.258),
                    body="""
                    <p><b>Select Sample Folders</b> — each folder is one
                    measurement of the number-concentration standard; the
                    table shows name, path and status.</p>
                    """),
                dict(
                    id="step2",
                    title="2 · Element Selection",
                    rect=(0.050, 0.462, 0.890, 0.070),
                    body="""
                    <p>Pick the element of the reference particles from the
                    periodic table.</p>
                    """),
                dict(
                    id="step3",
                    title="3 · Detection Parameters",
                    rect=(0.050, 0.540, 0.890, 0.253),
                    body="""
                    <p>Same per-sample detection setup as the mass-based
                    page; click a row to preview its signal.</p>
                    """),
                dict(
                    id="detect",
                    title="Detect Particles for All Samples",
                    rect=(0.057, 0.796, 0.876, 0.031),
                    body="""
                    <p>Counts the detected particles; the transport
                    efficiency follows from the expected vs. measured
                    particle number.</p>
                    """),
            ],
        ),
        dict(
            title="Calibration Info — Transport",
            image="calibration_info_TE.png",
            intro="""
            <p><b>Show Calibration Info</b> (sidebar) → Transport Rate tab:
            review and choose which transport-rate results are used.</p>
            """,
            hotspots=[
                dict(
                    id="summary",
                    title="Header summary",
                    rect=(0.061, 0.095, 0.881, 0.032),
                    body="""
                    <p>One-line status: how many methods are calibrated, how
                    many isotopes have ionic calibration (and with
                    R² &gt; 0.99), and the average transport rate in use.</p>
                    """),
                dict(
                    id="table",
                    title="Methods table",
                    rect=(0.074, 0.226, 0.853, 0.159),
                    body="""
                    <p>The three methods (Weight, Particle, Mass) with their
                    calibrated rate and status. Tick <b>Use in
                    Calculation</b> for each method to include; the
                    <b>average of the selected methods</b> is used for all
                    conversions.</p>
                    """),
                dict(
                    id="avg",
                    title="Average transport rate",
                    rect=(0.076, 0.802, 0.378, 0.030),
                    body="""
                    <p>The rate applied to concentration and size
                    calculations, with the number of methods averaged.</p>
                    """),
                dict(
                    id="buttons",
                    title="Export Data / Refresh",
                    rect=(0.060, 0.861, 0.164, 0.039),
                    body="""
                    <p><b>Export Data</b> saves the calibration summary;
                    <b>Refresh</b> re-reads the latest calibration
                    results.</p>
                    """),
            ],
        ),
        dict(
            title="Calibration Info — Ionic",
            image="calibration_info_ionic.png",
            intro="""
            <p>The Ionic Calibration tab of Calibration Information: the
            full per-isotope calibration and detection-limit table.</p>
            """,
            hotspots=[
                dict(
                    id="search",
                    title="Search / R² filter",
                    rect=(0.084, 0.189, 0.867, 0.041),
                    body="""
                    <p>Filter by isotope or element; <b>Show only
                    (R² &gt; 0.9)</b> hides poorly calibrated isotopes.</p>
                    """),
                dict(
                    id="table",
                    title="Per-isotope table",
                    rect=(0.049, 0.254, 0.902, 0.579),
                    body="""
                    <p>For every calibrated isotope: fit method and slope,
                    BEC, LOD, LOQ, R² and a quality grade, the density used,
                    the detection threshold in counts, and the derived
                    limits — <b>MDL/MQL</b> (mass detection/quantification
                    limit, fg) and <b>SDL/SQL</b> (size detection/
                    quantification limit, nm) — plus a completion status.</p>
                    """),
                dict(
                    id="buttons",
                    title="Export Data / Refresh / Close",
                    rect=(0.040, 0.861, 0.164, 0.039),
                    body="""
                    <p><b>Export Data</b> writes this table to a file for
                    reporting method performance.</p>
                    """),
            ],
        ),
        dict(
            title="Mass Fraction Calculator",
            image="mass_fraction.png",
            intro="""
            <p>Tools → Mass Fraction Calculator: define what compound each
            element belongs to, so particle masses convert correctly to
            particle sizes.</p>
            """,
            hotspots=[
                dict(
                    id="sample_panel",
                    title="Sample Selection",
                    rect=(0.055, 0.104, 0.160, 0.783),
                    body="""
                    <p>Choose which samples the mass fractions apply to, and
                    whether to apply to the selected samples only or to all
                    samples (global).</p>
                    """),
                dict(
                    id="table",
                    title="Compound table",
                    rect=(0.233, 0.178, 0.711, 0.645),
                    body="""
                    <p>Per element: type a <b>Compound Formula</b> (e.g.
                    TiO2 for Ti) and the <b>Mass Fraction</b>, molecular
                    weight and compound density are computed from the
                    materials database (the counter shows its size).
                    <b>Open</b> shows the compound structure options. Pure
                    elements default to mass fraction 1.0 and elemental
                    density.</p>
                    """),
                dict(
                    id="reset_calc",
                    title="Reset to Pure Elements / Calculate All",
                    rect=(0.233, 0.834, 0.251, 0.040),
                    body="""
                    <p><b>Reset to Pure Elements</b> clears all formulas;
                    <b>Calculate All Mass Fractions</b> recomputes every row
                    from its formula.</p>
                    """),
                dict(
                    id="apply",
                    title="Apply Changes",
                    rect=(0.775, 0.834, 0.170, 0.040),
                    body="""
                    <p>Writes the mass fractions and densities to the chosen
                    samples — they are used in particle mass and size
                    calculations.</p>
                    """),
            ],
        ),
        dict(
            title="Dilution Factor",
            image="dilution.png",
            intro="""
            <p>Tools → Dilution Factor: correct reported particle
            concentrations for sample dilution.</p>
            """,
            hotspots=[
                dict(
                    id="rows",
                    title="Per-sample dilution factors",
                    rect=(0.108, 0.209, 0.781, 0.586),
                    body="""
                    <p>Each sample has a factor field; corrected
                    particles/mL = measured value × factor. The <b>Apply
                    (…)</b> button fills the factor detected from the sample
                    name (e.g. <i>100000x</i>).</p>
                    """),
                dict(
                    id="autofill",
                    title="Autofill all detected / Reset all",
                    rect=(0.108, 0.819, 0.339, 0.047),
                    body="""
                    <p><b>Autofill all detected</b> applies every factor
                    found in sample names in one click; <b>Reset all</b>
                    returns to 1.000×.</p>
                    """),
                dict(
                    id="save",
                    title="Save / Cancel",
                    rect=(0.711, 0.819, 0.197, 0.047),
                    body="""
                    <p><b>Save</b> stores the factors; they are applied to
                    concentration outputs in results and exports.</p>
                    """),
            ],
        ),
        dict(
            title="Dilution Reminder",
            image="dilution_message.png",
            intro="""
            <p>Shown when a transport rate is available and particle
            concentrations can be reported.</p>
            """,
            hotspots=[
                dict(
                    id="text",
                    title="Reminder text",
                    rect=(0.283, 0.185, 0.623, 0.467),
                    body="""
                    <p>If your samples were diluted, set the factors under
                    Tools → Dilution Factor. After entering them, close the
                    results canvas, reopen it, reselect the sample nodes
                    containing those samples and click OK so the corrected
                    concentrations propagate.</p>
                    """),
                dict(
                    id="buttons",
                    title="Later / Open Dilution Factor",
                    rect=(0.402, 0.730, 0.438, 0.070),
                    body="""
                    <p><b>Open Dilution Factor</b> jumps straight to the
                    dialog; <b>Don't show this message again</b> silences
                    the reminder.</p>
                    """),
            ],
        ),
        dict(
            title="Isobaric Correction",
            image="isobaric_correction.png",
            intro="""
            <p>Tools → Isobaric Correction: subtract isobaric interferences
            from analyte signals before detection.</p>
            """,
            hotspots=[
                dict(
                    id="intro_text",
                    title="How corrections work",
                    rect=(0.068, 0.102, 0.863, 0.058),
                    body="""
                    <p>Each analyte has one correction <b>equation</b>. The
                    default comes from the reference table; you can replace
                    it with any calculator-style expression using
                    <code>raw</code>, channel tokens like
                    <code>Hg202</code>, numbers, + − × ÷, parentheses and
                    log / sqrt / exp / abs. Results are clamped at zero and
                    custom equations are saved automatically. Nothing
                    changes until you click <b>Apply</b>.</p>
                    """),
                dict(
                    id="preview_sample",
                    title="Preview sample",
                    rect=(0.068, 0.169, 0.450, 0.041),
                    body="""
                    <p>The sample used for the before/after preview plot on
                    the right.</p>
                    """),
                dict(
                    id="analyte_table",
                    title="Analyte table",
                    rect=(0.068, 0.219, 0.396, 0.628),
                    body="""
                    <p>Analytes with a known interference: the equation, its
                    source (Table or Custom) and a status —
                    <b>✓ Ready</b> when all required channels were measured,
                    or a warning when a channel (e.g. m/z 44 for Ti 48) is
                    missing from the dataset.</p>
                    """),
                dict(
                    id="plot",
                    title="Before/after preview",
                    rect=(0.478, 0.227, 0.445, 0.419),
                    body="""
                    <p>The raw signal (red) and the corrected signal overlaid
                    for the selected analyte — inspect the effect before
                    applying.</p>
                    """),
                dict(
                    id="equation",
                    title="Equation editor",
                    rect=(0.478, 0.657, 0.445, 0.087),
                    body="""
                    <p>Edit the correction expression, e.g.
                    <code>corrected(Ti 48) = max(raw − 0.089645×Ca44, 0)</code>.
                    <b>Reset to default</b> restores the reference-table
                    equation.</p>
                    """),
                dict(
                    id="apply",
                    title="Apply / Revert / Close",
                    rect=(0.735, 0.860, 0.198, 0.040),
                    body="""
                    <p><b>Apply</b> overwrites the working signal with the
                    corrected one (particle detection is invalidated and
                    must be re-run); <b>Revert</b> restores the raw signal
                    everywhere a correction was applied.</p>
                    """),
            ],
        ),
    ],
)

SECTION_RESULTS = dict(
    title="Results Canvas",
    pages=[
        dict(
            title="Workflow Builder",
            image="Canvas_results_1.png",
            intro="""
            <p>The results canvas (sidebar → Results) is a node-based
            <b>Workflow Builder</b>: drag blocks from the left panel onto
            the canvas and connect them.</p>
            """,
            hotspots=[
                dict(
                    id="search_nodes",
                    title="Search nodes",
                    rect=(0.022, 0.109, 0.108, 0.029),
                    body="<p>Filters the node palette by name.</p>"),
                dict(
                    id="data_processing",
                    title="Data Processing nodes",
                    rect=(0.020, 0.152, 0.110, 0.152),
                    body="""
                    <p><b>Single Sample</b> and <b>Multiple Sample</b> feed
                    particle results into the workflow; <b>Batch Windows</b>
                    pulls results from other open windows; <b>Particle
                    Filter</b> filters particles by composition, element
                    count or signal threshold before visualization.</p>
                    """),
                dict(
                    id="visualization",
                    title="Visualization nodes",
                    rect=(0.020, 0.311, 0.110, 0.558),
                    body="""
                    <p>Connect a sample node to any of these: Histogram,
                    Element Bar Chart, Box Plot, Correlation, Pie Chart,
                    Composition, Heatmap, Molar Ratio, Isotopic Ratio,
                    Ternary Plot, Single/Multiple, Clustering, Correlation
                    Matrix, Concentration, Network and Dashboard. An
                    <b>AI Analytics</b> category follows below.</p>
                    """),
                dict(
                    id="canvas",
                    title="Canvas",
                    rect=(0.140, 0.103, 0.830, 0.826),
                    body="""
                    <p>Drop nodes here and drag between ports to connect a
                    sample to a visualization. Shortcuts: <b>Del</b> deletes
                    a node, <b>Ctrl+C</b> duplicates, <b>Ctrl+Z</b> undoes.
                    Double-click a node to configure or open it.</p>
                    """),
                dict(
                    id="zoom",
                    title="Zoom / Fit",
                    rect=(0.724, 0.070, 0.098, 0.030),
                    body="""
                    <p>Zoom the canvas in/out, back to 100&nbsp;%, or
                    <b>Fit</b> everything into view.</p>
                    """),
                dict(
                    id="insights",
                    title="Insights",
                    rect=(0.834, 0.070, 0.042, 0.029),
                    body="""
                    <p>Generates automatic observations about the connected
                    results.</p>
                    """),
                dict(
                    id="clear_close",
                    title="Clear All / Close",
                    rect=(0.884, 0.070, 0.086, 0.029),
                    body="""
                    <p><b>Clear All</b> empties the canvas; <b>Close</b>
                    returns to the main window (the workflow is kept with
                    the project).</p>
                    """),
            ],
        ),
        dict(
            title="Nodes & Connections",
            image="Canvas_results_2.png",
            intro="""
            <p>A Sample node and a Histogram node on the canvas, not yet
            connected.</p>
            """,
            hotspots=[
                dict(
                    id="sample_node",
                    title="Sample node",
                    rect=(0.350, 0.300, 0.060, 0.120),
                    body="""
                    <p>Double-click to choose the sample(s) it represents.
                    The red badge means it still needs configuration. The
                    <b>green port</b> (left) accepts input (e.g. Batch
                    Windows); the <b>orange port</b> (right) outputs particle
                    data — drag from it to a visualization's input port.</p>
                    """),
                dict(
                    id="histogram_node",
                    title="Visualization node",
                    rect=(0.525, 0.303, 0.060, 0.120),
                    body="""
                    <p>A Histogram block waiting for data: drag a connection
                    from a sample node's output into its green input port,
                    then double-click to open the histogram window.</p>
                    """),
                dict(
                    id="status",
                    title="Selection status",
                    rect=(0.850, 0.913, 0.120, 0.022),
                    body="""
                    <p>Shows how many nodes are selected; selected nodes can
                    be deleted (Del) or duplicated (Ctrl+C).</p>
                    """),
            ],
        ),
        dict(
            title="Single Sample Node",
            image="single_sample_results.png",
            intro="""
            <p>Configuration dialog of a <b>Single Sample</b> node.</p>
            """,
            hotspots=[
                dict(
                    id="banner",
                    title="Instruction banner",
                    rect=(0.071, 0.122, 0.857, 0.044),
                    body="""
                    <p>Check one sample for individual analysis, or several
                    to <b>sum/combine</b> them into one dataset.</p>
                    """),
                dict(
                    id="samples",
                    title="Samples panel",
                    rect=(0.071, 0.188, 0.380, 0.563),
                    body="""
                    <p>Search and tick the sample(s) to analyze; the banner
                    below confirms the selection.</p>
                    """),
                dict(
                    id="isotopes",
                    title="Isotopes panel",
                    rect=(0.459, 0.188, 0.469, 0.563),
                    body="""
                    <p>The isotopes available in the selection, shown as
                    colored chips. Restrict the node to a subset with
                    <b>Select All</b> / <b>Clear</b> and individual
                    clicks.</p>
                    """),
                dict(
                    id="ok",
                    title="OK / Cancel",
                    rect=(0.669, 0.836, 0.259, 0.044),
                    body="""
                    <p><b>OK</b> stores the configuration; the node's red
                    badge disappears and connected visualizations update.</p>
                    """),
            ],
        ),
        dict(
            title="Multiple Sample Node",
            image="multi_sample_results.png",
            intro="""
            <p>Configuration dialog of a <b>Multiple Sample</b> node —
            compare samples or groups of samples.</p>
            """,
            hotspots=[
                dict(
                    id="banner",
                    title="Instruction banner",
                    rect=(0.065, 0.118, 0.870, 0.043),
                    body="""
                    <p>Check the samples to include. Give the same
                    <b>Group</b> name to samples that should be combined;
                    leave the group blank for individual analysis.</p>
                    """),
                dict(
                    id="group_controls",
                    title="Group name / Apply to Checked",
                    rect=(0.317, 0.208, 0.236, 0.046),
                    body="""
                    <p>Type a group name and <b>Apply to Checked</b> to
                    assign it to every ticked sample at once.</p>
                    """),
                dict(
                    id="group_fields",
                    title="Per-sample Group fields",
                    rect=(0.451, 0.262, 0.090, 0.436),
                    body="""
                    <p>Each sample's group can also be typed directly —
                    replicates given the same name (e.g. their dilution) are
                    merged in the visualizations.</p>
                    """),
                dict(
                    id="group_buttons",
                    title="Clear Groups / Auto-Group",
                    rect=(0.232, 0.714, 0.200, 0.040),
                    body="""
                    <p><b>Auto-Group</b> derives groups from sample names
                    (e.g. replicates <i>_1, _2, _3</i>); <b>Clear Groups</b>
                    empties all assignments.</p>
                    """),
                dict(
                    id="isotopes",
                    title="Isotopes panel",
                    rect=(0.562, 0.181, 0.373, 0.577),
                    body="""
                    <p>Same as the single-sample node: restrict which
                    isotopes flow into the connected visualizations.</p>
                    """),
            ],
        ),
        dict(
            title="Batch Windows",
            image="batch_window_results.png",
            intro="""
            <p>Configuration of a <b>Batch Windows</b> node: pull particle
            results from other open IsotopeTrack windows.</p>
            """,
            hotspots=[
                dict(
                    id="window_row",
                    title="Window entry",
                    rect=(0.085, 0.184, 0.351, 0.034),
                    body="""
                    <p>Each open window appears with its project name and
                    the size of its results (samples and particles). Tick
                    the windows to include and connect the node to a Sample
                    node.</p>
                    """),
                dict(
                    id="buttons",
                    title="OK / Cancel",
                    rect=(0.665, 0.828, 0.259, 0.046),
                    body="""
                    <p><b>OK</b> makes the selected windows' results
                    available downstream.</p>
                    """),
            ],
        ),
        dict(
            title="Particle Filter",
            image="Particle_filter.png",
            intro="""
            <p>Configuration of a <b>Particle Filter</b> node — placed
            between a sample node and a visualization to keep only certain
            particles.</p>
            """,
            hotspots=[
                dict(
                    id="samples",
                    title="Samples panel",
                    rect=(0.067, 0.104, 0.272, 0.683),
                    body="""
                    <p>Samples arriving from the upstream node. Check =
                    include in the output; click = edit that sample's
                    filter. Connect and configure a sample node first.</p>
                    """),
                dict(
                    id="composition",
                    title="Element Composition filter",
                    rect=(0.353, 0.146, 0.576, 0.271),
                    body="""
                    <p>Keep particles by their elemental make-up. Select
                    isotopes and a <b>match mode</b>: AND (contains all
                    selected elements), OR, or exclusive variants.</p>
                    """),
                dict(
                    id="count",
                    title="Element Count filter",
                    rect=(0.353, 0.423, 0.576, 0.107),
                    body="""
                    <p>Keep particles with at least / at most / exactly N
                    detected elements — e.g. only multi-element particles
                    with ≥ 2 elements.</p>
                    """),
                dict(
                    id="threshold",
                    title="Per-Element Signal Threshold",
                    rect=(0.353, 0.537, 0.576, 0.171),
                    body="""
                    <p>Minimum signal for an element to count as
                    "present", in counts (or calibrated units) — near-zero
                    detections are ignored. Leave 0 for no threshold.</p>
                    """),
                dict(
                    id="apply_all",
                    title="Apply to all samples",
                    rect=(0.794, 0.105, 0.141, 0.037),
                    body="""
                    <p>Copies the current filter to every connected
                    sample.</p>
                    """),
            ],
        ),
        dict(
            title="Histogram Window",
            image="histogram.png",
            intro="""
            <p>Double-clicking a configured Histogram node opens the
            analysis window.</p>
            """,
            hotspots=[
                dict(
                    id="plot",
                    title="Histogram plot",
                    rect=(0.126, 0.128, 0.809, 0.633),
                    body="""
                    <p>Distribution of the selected quantity (intensity,
                    mass, size, moles…) per element — here Si and Fe
                    overlaid. Zoom and pan with the mouse; the legend
                    identifies each element's color.</p>
                    """),
                dict(
                    id="format_btn",
                    title="Plot format settings",
                    rect=(0.052, 0.872, 0.223, 0.038),
                    body="""
                    <p>Fonts, colors, density curve, statistics box and
                    figure frame (next page of this guide).</p>
                    """),
                dict(
                    id="quantities_btn",
                    title="Configure plot quantities",
                    rect=(0.281, 0.872, 0.219, 0.038),
                    body="""
                    <p>Choose the plotted data (Counts, Mass, Moles,
                    Diameter), the y-axis mode, and element groups summed
                    per particle (two pages ahead).</p>
                    """),
                dict(
                    id="reset_btn",
                    title="Reset layout",
                    rect=(0.502, 0.872, 0.221, 0.038),
                    body="<p>Restores the default zoom and layout.</p>"),
                dict(
                    id="export_btn",
                    title="Export figure",
                    rect=(0.725, 0.872, 0.221, 0.038),
                    body="""
                    <p>Saves the figure to PNG/SVG/PDF with configurable
                    resolution (see the Export Figure page).</p>
                    """),
            ],
        ),
        dict(
            title="Plot Format Settings",
            image="plot_settings.png",
            intro="""
            <p>Formatting options shared by the visualization windows.</p>
            """,
            hotspots=[
                dict(
                    id="font",
                    title="Font & Text",
                    rect=(0.143, 0.180, 0.697, 0.402),
                    body="""
                    <p>Font family, size, bold/italic and color for the
                    figure text; <b>Isotope Label</b> chooses how elements
                    are written (symbol, isotope notation…).</p>
                    """),
                dict(
                    id="toggles",
                    title="Visual Toggles",
                    rect=(0.143, 0.607, 0.697, 0.172),
                    body="""
                    <p>Show/hide the density curve, the statistics box and
                    the figure frame.</p>
                    """),
                dict(
                    id="buttons",
                    title="Apply / Done / Cancel",
                    rect=(0.536, 0.800, 0.349, 0.049),
                    body="""
                    <p><b>Apply</b> updates the plot immediately so you can
                    iterate; <b>Done</b> applies and closes.</p>
                    """),
            ],
        ),
        dict(
            title="Plot Quantities",
            image="configuration_settings.png",
            intro="""
            <p>What the histogram actually plots.</p>
            """,
            hotspots=[
                dict(
                    id="data_type",
                    title="Data Type",
                    rect=(0.136, 0.172, 0.727, 0.189),
                    body="""
                    <p><b>Data</b> — the quantity on the x-axis: Counts, or
                    calibrated Mass / Moles / Diameter. <b>Y Axis</b> —
                    per-particle counts or frequency/density.</p>
                    """),
                dict(
                    id="groups",
                    title="Element Groups (Sum per Particle)",
                    rect=(0.136, 0.380, 0.727, 0.402),
                    body="""
                    <p>Group elements to sum their values within each
                    particle — e.g. group Fe + Si + Ti so each particle's
                    combined mass is plotted as one value. Applies to
                    Counts, Mass and Moles (not Diameter). <b>+ Add
                    Group</b> creates a group; <b>− Remove</b> deletes
                    it.</p>
                    """),
            ],
        ),
        dict(
            title="Figure Previews",
            image="preview.png",
            intro="""
            <p>Small preview cards appear while composing figures.</p>
            """,
            hotspots=[
                dict(
                    id="cards",
                    title="Preview cards",
                    rect=(0.145, 0.154, 0.763, 0.731),
                    body="""
                    <p>Each card is a live thumbnail of a generated figure —
                    click to bring the corresponding window forward, or the
                    <b>✕</b> to dismiss it.</p>
                    """),
            ],
        ),
        dict(
            title="Export Figure",
            image="export_figure.png",
            intro="""
            <p>Saving a visualization to an image file.</p>
            """,
            hotspots=[
                dict(
                    id="file",
                    title="File",
                    rect=(0.173, 0.145, 0.653, 0.176),
                    body="""
                    <p>Filename (without extension) and format — PNG for
                    presentations, SVG/PDF for publication-quality vector
                    output.</p>
                    """),
                dict(
                    id="resolution",
                    title="Resolution / Size",
                    rect=(0.159, 0.359, 0.694, 0.267),
                    body="""
                    <p>Either a <b>scale factor</b> of the on-screen size
                    (2× default) or exact custom pixel dimensions (width ×
                    height).</p>
                    """),
                dict(
                    id="appearance",
                    title="Appearance",
                    rect=(0.173, 0.664, 0.653, 0.115),
                    body="""
                    <p>Background color of the exported figure — white for
                    documents, or transparent/dark options.</p>
                    """),
            ],
        ),
        dict(
            title="Results Tables",
            image="single_element&multi-element.png",
            intro="""
            <p>The Results Display strip below the main window's parameter
            panel.</p>
            """,
            hotspots=[
                dict(
                    id="single_cb",
                    title="Single Element Results",
                    rect=(0.023, 0.517, 0.127, 0.310),
                    body="""
                    <p>Shows a table of every detected particle for the
                    selected element: peak start/end (s), total counts, peak
                    height and height/threshold ratio. Selecting a row
                    highlights that particle in the signal plot.</p>
                    """),
                dict(
                    id="multi_cb",
                    title="Multi-Element Particles",
                    rect=(0.161, 0.517, 0.129, 0.310),
                    body="""
                    <p>Shows particles containing multiple elements:
                    particle number, start/end time, and the counts of each
                    included element in the coincident event.</p>
                    """),
                dict(
                    id="tip",
                    title="Performance tip",
                    rect=(0.722, 0.193, 0.238, 0.248),
                    body="""
                    <p>Keeping both tables unchecked speeds up analysis —
                    updating them can be resource-intensive with many
                    peaks.</p>
                    """),
            ],
        ),
    ],
)

SECTION_EXPORT = dict(
    title="Export",
    pages=[dict(
        title="Export Options",
        image="export_csv.png",
        intro="""
        <p>Sidebar → Export (or File → Export, ⌘E): write the analysis to
        files.</p>
        """,
        hotspots=[
            dict(
                id="data_type",
                title="Data Type: Element / Particle",
                rect=(0.107, 0.113, 0.374, 0.038),
                body="""
                <p><b>Element</b> exports per-element results (one row per
                detected event per isotope); <b>Particle</b> exports
                multi-element particle results (one row per coincident
                particle).</p>
                """),
            dict(
                id="samples",
                title="Samples panel",
                rect=(0.111, 0.179, 0.774, 0.485),
                body="""
                <p>Choose which samples to export — <b>Select all</b> /
                <b>Clear</b>, with the counter showing the selection.</p>
                """),
            dict(
                id="dilution_btn",
                title="Set Dilution Factors…",
                rect=(0.131, 0.669, 0.734, 0.036),
                body="""
                <p>Shortcut to the Dilution Factor dialog so exported
                concentrations are corrected before writing files.</p>
                """),
            dict(
                id="export_section",
                title="Sample files / Summary file",
                rect=(0.111, 0.733, 0.774, 0.090),
                body="""
                <p><b>Sample files</b> — one detailed file per sample with
                particle-by-particle data (peak characteristics, integration
                results). <b>Summary file</b> — one file covering all
                samples: statistics (mean, median, SD), particle
                concentrations, calibration information and method
                parameters. Both can be exported together.</p>
                """),
            dict(
                id="advanced",
                title="Advanced…",
                rect=(0.111, 0.841, 0.171, 0.038),
                body="""
                <p>Extra export options such as file format and included
                columns.</p>
                """),
            dict(
                id="export_btn",
                title="Export",
                rect=(0.518, 0.841, 0.368, 0.038),
                body="""
                <p>Choose a destination folder and write the files; progress
                is shown in the status bar.</p>
                """),
        ],
    )],
)

SECTIONS = [
    SECTION_MAIN_WINDOW,
    SECTION_GETTING_STARTED,
    SECTION_MENUS,
    SECTION_ELEMENTS_SIGNALS,
    SECTION_DETECTION,
    SECTION_CALIBRATION,
    SECTION_RESULTS,
    SECTION_EXPORT,
]
