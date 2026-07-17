from PySide6.QtWidgets import (
    QDialog, QTabWidget, QVBoxLayout, QPushButton,
    QLabel, QScrollArea, QWidget, QLineEdit, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt
import re

from tools.theme import theme
import logging
_itk_log = logging.getLogger("IsotopeTrack.tools.tutorial")


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------
def _section(html: str) -> QLabel:
    """Rich-text section label with consistent styling."""
    lbl = QLabel(html)
    lbl.setWordWrap(True)
    lbl.setOpenExternalLinks(True)
    lbl.setTextFormat(Qt.RichText)
    lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    lbl.setStyleSheet(f"font-size:13px; line-height:1.5; color:{theme.palette.text_primary};")
    return lbl


def _scroll_tab(*widgets) -> QScrollArea:
    """Wrap a list of widgets in a scrollable tab."""
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
    """Return a horizontal-rule label for separating sections.

    Returns:
        QLabel: Rich-text label rendering a horizontal rule.
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
        """Build the user-guide dialog and all its tabs.

        Args:
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("IsotopeTrack — User Guide")
        self.resize(820, 740)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._search_index = []
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText(
            "Search the whole guide…  (e.g. threshold, dilution, sigma)")
        self._search_box.setClearButtonEnabled(True)
        self._search_box.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_box)

        self._search_results = QListWidget()
        self._search_results.setVisible(False)
        self._search_results.setMaximumHeight(180)
        self._search_results.itemClicked.connect(self._on_result_clicked)
        layout.addWidget(self._search_results)

        self._tabs = QTabWidget()
        self._tabs.setUsesScrollButtons(True)
        self._tabs.addTab(self._tab_overview(), "Overview")
        self._tabs.addTab(self._tab_workflow(), "Workflow")
        for section in self._interactive_sections():
            self._tabs.addTab(section["widget"], section["title"])

        layout.addWidget(self._tabs)
        self._search_index = self._build_search_index()

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
            QLineEdit {{
                background-color: {p.bg_tertiary};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {p.accent};
            }}
            QListWidget {{
                background-color: {p.bg_tertiary};
                color: {p.text_primary};
                border: 1px solid {p.border};
                border-radius: 6px;
                font-size: 12px;
            }}
            QListWidget::item {{
                padding: 5px 8px;
            }}
            QListWidget::item:hover {{
                background-color: {p.bg_hover};
            }}
            QListWidget::item:selected {{
                background-color: {p.accent};
                color: {p.text_inverse};
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
        """Disconnect theme signals when the dialog closes.

        Args:
            event (QCloseEvent): Close event from Qt.
        """
        try:
            theme.themeChanged.disconnect(self.apply_theme)
        except (TypeError, RuntimeError):
            _itk_log.exception("Handled exception in closeEvent")
        super().closeEvent(event)

    # ------------------------------------------------------------------ #
    # Tab: Overview
    # ------------------------------------------------------------------ #
    def _tab_overview(self):
        """Build the Overview tab.

        Returns:
            QScrollArea: Scrollable tab widget with overview content.
        """
        return _scroll_tab(
            _section("""
            <h2>IsotopeTrack v1.10.7</h2>
            <p>Software application for analyzing single particle
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
                    Apple Silicon (M1/M2/M3/M4/M5) recommended &nbsp;·&nbsp;
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
    # Guide-wide search                                                    #
    # ------------------------------------------------------------------ #
    def _build_search_index(self):
        """Index every hotspot of every interactive page for search.

        Returns:
            list[dict]: Entries with display path, navigation targets and
            lowercase searchable text.
        """
        try:
            from tools.interactive_guide import InteractiveImagePage
        except Exception:
            _itk_log.exception("Could not import guide pages for search")
            return []
        index = []
        for top in range(self._tabs.count()):
            section_widget = self._tabs.widget(top)
            section_title = self._tabs.tabText(top)
            if isinstance(section_widget, InteractiveImagePage):
                pages = [(-1, section_widget)]
            elif isinstance(section_widget, QTabWidget):
                pages = [(i, section_widget.widget(i))
                         for i in range(section_widget.count())]
            else:
                continue
            for inner, page_widget in pages:
                if not isinstance(page_widget, InteractiveImagePage):
                    continue
                page = page_widget._page
                for spot in page["hotspots"]:
                    text = " ".join((
                        section_title, page["title"], spot["title"],
                        re.sub(r"<[^>]+>", " ", spot["body"]))).lower()
                    index.append(dict(
                        display=(f"{section_title}  ›  {page['title']}"
                                 f"  ›  {spot['title']}"),
                        top=top, inner=inner, spot_id=spot["id"],
                        page_widget=page_widget,
                        section_widget=section_widget, text=text))
        return index

    def _on_search_changed(self, text):
        """Filter the search index and show matching regions.

        Args:
            text (str): Current search-box text.
        """
        query = text.strip().lower()
        self._search_results.clear()
        if len(query) < 2:
            self._search_results.setVisible(False)
            return
        words = query.split()
        matches = [e for e in self._search_index
                   if all(w in e["text"] for w in words)]
        for entry in matches[:15]:
            item = QListWidgetItem(entry["display"])
            item.setData(Qt.UserRole, entry)
            self._search_results.addItem(item)
        if not matches:
            item = QListWidgetItem("No matches — try another word")
            item.setFlags(Qt.NoItemFlags)
            self._search_results.addItem(item)
        self._search_results.setVisible(True)

    def _on_result_clicked(self, item):
        """Navigate to the clicked search result.

        Args:
            item (QListWidgetItem): The clicked result item.
        """
        entry = item.data(Qt.UserRole)
        if not entry:
            return
        self._tabs.setCurrentIndex(entry["top"])
        if entry["inner"] >= 0:
            entry["section_widget"].setCurrentIndex(entry["inner"])
        entry["page_widget"].show_hotspot(entry["spot_id"])
        self._search_results.setVisible(False)

    # ------------------------------------------------------------------ #
    # Interactive sections (clickable screenshots)                         #
    # ------------------------------------------------------------------ #
    def _interactive_sections(self):
        """Build the interactive guide sections from guide_content.

        Returns:
            list[dict]: Dicts with 'title' and 'widget' for each section.
        """
        try:
            from tools.interactive_guide import build_section_widget
            from tools.guide_content import SECTIONS
        except Exception:
            _itk_log.exception("Could not build interactive guide sections")
            return []
        built = []
        for section in SECTIONS:
            try:
                built.append(dict(
                    title=section["title"],
                    widget=build_section_widget(section, self)))
            except Exception:
                _itk_log.exception(
                    "Could not build guide section %s",
                    section.get("title"))
        return built

    # ------------------------------------------------------------------ #
    # Tab: Workflow                                                         #
    # ------------------------------------------------------------------ #
    def _tab_workflow(self):
        """Build the Workflow tab.

        Returns:
            QScrollArea: Scrollable tab widget with the recommended
            step-by-step workflow.
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

