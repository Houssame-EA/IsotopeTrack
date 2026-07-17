"""Equations & References — complete mathematical reference.

Every equation used in IsotopeTrack, organised by topic (Sensitivity,
Transport Rate, Detection & SIA, Quantification, Clustering). Equations
are rendered as real LaTeX via matplotlib mathtext; every equation has a
description, a definition of every parameter, and a worked numerical
example. References are given for each topic.

All formulas mirror the actual implementation in
calibration_methods/ionic_CAL.py, calibration_methods/te_common.py,
calibration_methods/TE_mass.py, processing/peak_detection.py,
loading/SIA_manager.py, mainwindow.py, utils/dilution.py,
tools/mass_fraction_calculator.py and results/results_cluster.py.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea,
)
from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QImage, QPixmap, QDesktopServices

from tools.theme import theme
import logging
_itk_log = logging.getLogger("IsotopeTrack.tools.equations_reference")

_PIXMAP_CACHE = {}

REFERENCES = {
    "currie1968": dict(
        label="Currie 1968",
        citation="Currie, L. A. (1968). Limits for qualitative detection "
                 "and quantitative determination — application to "
                 "radiochemistry. <i>Analytical Chemistry</i>, 40(3), "
                 "586–593.",
        url="https://doi.org/10.1021/ac60259a007",
        used="3σ/10σ LOD–LOQ convention in the Sensitivity figures of "
             "merit, and counts-based decision limits in Detection."),
    "miller2010": dict(
        label="Miller & Miller 2010",
        citation="Miller, J. N. &amp; Miller, J. C. (2010). <i>Statistics "
                 "and Chemometrics for Analytical Chemistry</i>, 6th ed., "
                 "Pearson Education, Harlow.",
        url=None,
        used="Weighted regression and figures-of-merit conventions used "
             "by the ionic calibration fits."),
    "pace2011": dict(
        label="Pace 2011",
        citation="Pace, H. E., Rogers, N. J., Jarolimek, C., Coleman, "
                 "V. A., Higgins, C. P. &amp; Ranville, J. F. (2011). "
                 "Determining transport efficiency for the purpose of "
                 "counting and sizing nanoparticles via single particle "
                 "ICP-MS. <i>Analytical Chemistry</i>, 83(24), 9361–9369.",
        url="https://doi.org/10.1021/ac201952t",
        used="All three transport-efficiency methods (Transport Rate "
             "window) and the counts→mass→size relations in "
             "Quantification."),
    "laborda2014": dict(
        label="Laborda 2014",
        citation="Laborda, F., Bolea, E. &amp; Jiménez-Lamana, J. (2014). "
                 "Single particle inductively coupled plasma mass "
                 "spectrometry: a powerful tool for nanoanalysis. "
                 "<i>Analytical Chemistry</i>, 86(5), 2270–2278.",
        url="https://doi.org/10.1021/ac402980q",
        used="General spICP-MS quantification framework: number "
             "concentrations and detection/size limits."),
    "gundlach2018": dict(
        label="Gundlach-Graham 2018",
        citation="Gundlach-Graham, A., Hendriks, L., Mehrabi, K. &amp; "
                 "Günther, D. (2018). Monte Carlo simulation of low-count "
                 "signals in time-of-flight mass spectrometry and its "
                 "application to single-particle detection. <i>Analytical "
                 "Chemistry</i>, 90(20), 11847–11855.",
        url="https://doi.org/10.1021/acs.analchem.8b01551",
        used="Established that ToF background signals follow a compound "
             "Poisson distribution — the foundation of the CPLN "
             "thresholding used in Detection."),
    "hendriks2019": dict(
        label="Hendriks 2019",
        citation="Hendriks, L., Gundlach-Graham, A. &amp; Günther, D. "
                 "(2019). Performance of sp-ICP-TOFMS with signal "
                 "distributions fitted to a compound Poisson model. "
                 "<i>Journal of Analytical Atomic Spectrometry</i>, "
                 "34(9), 1900–1909.",
        url="https://doi.org/10.1039/C9JA00186G",
        used="Compound-Poisson critical values as detection decision "
             "levels for sp-ICP-TOFMS — basis of the per-dwell threshold "
             "in Detection."),
    "lockwood2025b": dict(
        label="Lockwood 2025b",
        citation="Lockwood, T. E., Gonzalez de Vega, R., Schlatt, L. "
                 "&amp; Clases, D. (2025). Accurate thresholding using a "
                 "compound-Poisson-lognormal lookup table and parameters "
                 "recovered from standard single particle ICP-TOFMS data. "
                 "<i>Journal of Analytical Atomic Spectrometry</i>, "
                 "40(10), 2633.",
        url="https://doi.org/10.1039/D5JA00230C",
        used="The precomputed λ×σ quantile lookup table behind the "
             "<i>CPLN table</i> detection method."),
    "hadioui2019": dict(
        label="Hadioui 2019",
        citation="Hadioui, M., Knapp, G., Azimzada, A., Jreije, I., "
                 "Frechette-Viens, L. &amp; Wilkinson, K. J. (2019). "
                 "Lowering the size detection limits of Ag and TiO₂ "
                 "nanoparticles by single particle ICP-MS. <i>Analytical "
                 "Chemistry</i>, 91(20), 13275–13284.",
        url="https://doi.org/10.1021/acs.analchem.9b04007",
        used="Source of the transport-efficiency / size-detection-limit "
             "figure shown in the Transport Rate tab."),
    "cuss2025": dict(
        label="Cuss 2025",
        citation="Cuss, C. W., Benedetti, M. F., Costamanga, C., "
                 "Mesnard, L. &amp; Tharaud, M. (2025). Self-organizing "
                 "maps for the detection and classification of natural "
                 "nanoparticles, nanoparticle systems and engineered "
                 "nanoparticles characterized using single particle "
                 "ICP-time-of-flight-MS. <i>Journal of Analytical Atomic "
                 "Spectrometry</i>, 40, 2471.",
        url="https://doi.org/10.1039/D5JA00179J",
        used="SOM classification of natural and engineered nanoparticles "
             "from spICP-ToF-MS data (Clustering node, SOM method)."),
    "erfani2023": dict(
        label="Erfani 2023",
        citation="Erfani, M., Baalousha, M. &amp; Goharian, E. (2023). "
                 "Unveiling elemental fingerprints: a comparative study "
                 "of clustering methods for multi-element nanoparticle "
                 "data. <i>Science of The Total Environment</i>, 166986.",
        url="https://www.sciencedirect.com/science/article/abs/pii/"
            "S0048969723058035",
        used="Comparison of hierarchical, spectral and t-SNE+DBSCAN "
             "clustering on multi-element nanoparticle data (Clustering "
             "node method choice)."),
    "tharaud2022": dict(
        label="Tharaud 2022",
        citation="Tharaud, M., Schlatt, L., Shaw, P. &amp; Benedetti, "
                 "M. F. (2022). Nanoparticle identification using single "
                 "particle ICP-ToF-MS acquisition coupled to cluster "
                 "analysis. From engineered to natural nanoparticles. "
                 "<i>Journal of Analytical Atomic Spectrometry</i>, 37, "
                 "2042–2052.",
        url="https://doi.org/10.1039/D2JA00116K",
        used="Hierarchical agglomerative clustering of spICP-ToF-MS "
             "particle fingerprints, from engineered to natural "
             "nanoparticles (Clustering node, Hierarchical method)."),
    "lockwood2025": dict(
        label="Lockwood 2025",
        citation="Lockwood, T. E., Schlatt, L. &amp; Clases, D. (2025). "
                 "SPCal — an open source, easy-to-use processing platform "
                 "for ICP-TOFMS-based single event data. <i>Journal of "
                 "Analytical Atomic Spectrometry</i>, 40, 130–136.",
        url="https://doi.org/10.1039/D4JA00241E",
        used="Compound Poisson–LogNormal thresholding and single-ion-area "
             "σ treatment (Detection Method column and SIA buttons)."),
    "fenton1960": dict(
        label="Fenton 1960",
        citation="Fenton, L. F. (1960). The sum of log-normal probability "
                 "distributions in scatter transmission systems. <i>IRE "
                 "Transactions on Communications Systems</i>, 8(1), 57–67.",
        url="https://doi.org/10.1109/TCOM.1960.1097606",
        used="Fenton–Wilkinson approximation for summing log-normal "
             "single-ion areas inside the CPLN threshold."),
    "gundlach2023": dict(
        label="Gundlach-Graham 2023",
        citation="Gundlach-Graham, A. &amp; Lancaster, R. (2023). "
                 "Mass-dependent critical value expressions for particle "
                 "finding in single-particle ICP-TOFMS. <i>Analytical "
                 "Chemistry</i>, 95(13), 5618–5626.",
        url="https://doi.org/10.1021/acs.analchem.2c05243",
        used="Critical-value formulation for particle finding that "
             "underlies the CPLN table (lookup) method."),
    "lloyd1982": dict(
        label="Lloyd 1982",
        citation="Lloyd, S. (1982). Least squares quantization in PCM. "
                 "<i>IEEE Transactions on Information Theory</i>, 28(2), "
                 "129–137.",
        url="https://doi.org/10.1109/TIT.1982.1056489",
        used="K-Means algorithm (Clustering node)."),
    "sculley2010": dict(
        label="Sculley 2010",
        citation="Sculley, D. (2010). Web-scale k-means clustering. "
                 "<i>Proceedings of the 19th International Conference on "
                 "World Wide Web</i>, 1177–1178.",
        url="https://doi.org/10.1145/1772690.1772862",
        used="Mini-Batch K-Means (Clustering node)."),
    "dempster1977": dict(
        label="Dempster 1977",
        citation="Dempster, A. P., Laird, N. M. &amp; Rubin, D. B. (1977). "
                 "Maximum likelihood from incomplete data via the EM "
                 "algorithm. <i>Journal of the Royal Statistical Society "
                 "B</i>, 39(1), 1–38.",
        url="https://doi.org/10.1111/j.2517-6161.1977.tb01600.x",
        used="EM fitting of Gaussian mixture models (Clustering node)."),
    "ester1996": dict(
        label="Ester 1996",
        citation="Ester, M., Kriegel, H.-P., Sander, J. &amp; Xu, X. "
                 "(1996). A density-based algorithm for discovering "
                 "clusters in large spatial databases with noise. "
                 "<i>Proceedings of KDD-96</i>, 226–231.",
        url="https://cdn.aaai.org/KDD/1996/KDD96-037.pdf",
        used="DBSCAN (Clustering node)."),
    "campello2013": dict(
        label="Campello 2013",
        citation="Campello, R. J. G. B., Moulavi, D. &amp; Sander, J. "
                 "(2013). Density-based clustering based on hierarchical "
                 "density estimates. <i>PAKDD 2013</i>, 160–172.",
        url="https://doi.org/10.1007/978-3-642-37456-2_14",
        used="HDBSCAN (Clustering node)."),
    "ankerst1999": dict(
        label="Ankerst 1999",
        citation="Ankerst, M., Breunig, M. M., Kriegel, H.-P. &amp; "
                 "Sander, J. (1999). OPTICS: ordering points to identify "
                 "the clustering structure. <i>SIGMOD Record</i>, 28(2), "
                 "49–60.",
        url="https://doi.org/10.1145/304182.304187",
        used="OPTICS (Clustering node)."),
    "comaniciu2002": dict(
        label="Comaniciu 2002",
        citation="Comaniciu, D. &amp; Meer, P. (2002). Mean shift: a "
                 "robust approach toward feature space analysis. <i>IEEE "
                 "TPAMI</i>, 24(5), 603–619.",
        url="https://doi.org/10.1109/34.1000236",
        used="Mean Shift (Clustering node)."),
    "ward1963": dict(
        label="Ward 1963",
        citation="Ward, J. H. (1963). Hierarchical grouping to optimize "
                 "an objective function. <i>Journal of the American "
                 "Statistical Association</i>, 58(301), 236–244.",
        url="https://doi.org/10.1080/01621459.1963.10500845",
        used="Ward linkage for hierarchical clustering (Clustering "
             "node)."),
    "vonluxburg2007": dict(
        label="von Luxburg 2007",
        citation="von Luxburg, U. (2007). A tutorial on spectral "
                 "clustering. <i>Statistics and Computing</i>, 17, "
                 "395–416.",
        url="https://doi.org/10.1007/s11222-007-9033-z",
        used="Spectral clustering (Clustering node)."),
    "zhang1996": dict(
        label="Zhang 1996",
        citation="Zhang, T., Ramakrishnan, R. &amp; Livny, M. (1996). "
                 "BIRCH: an efficient data clustering method for very "
                 "large databases. <i>SIGMOD Record</i>, 25(2), 103–114.",
        url="https://doi.org/10.1145/233269.233324",
        used="BIRCH clustering-feature tree (Clustering node)."),
    "kohonen1982": dict(
        label="Kohonen 1982",
        citation="Kohonen, T. (1982). Self-organized formation of "
                 "topologically correct feature maps. <i>Biological "
                 "Cybernetics</i>, 43, 59–69.",
        url="https://doi.org/10.1007/BF00337288",
        used="Self-organising maps (Clustering node)."),
    "pearson1901": dict(
        label="Pearson 1901",
        citation="Pearson, K. (1901). On lines and planes of closest fit "
                 "to systems of points in space. <i>Philosophical "
                 "Magazine</i>, 2(11), 559–572.",
        url="https://doi.org/10.1080/14786440109462720",
        used="Principal component analysis (dimensionality-reduction "
             "option of the Clustering node)."),
    "vandermaaten2008": dict(
        label="van der Maaten 2008",
        citation="van der Maaten, L. &amp; Hinton, G. (2008). Visualizing "
                 "data using t-SNE. <i>Journal of Machine Learning "
                 "Research</i>, 9, 2579–2605.",
        url="https://jmlr.org/papers/v9/vandermaaten08a.html",
        used="t-SNE embedding (dimensionality-reduction option of the "
             "Clustering node)."),
    "rousseeuw1987": dict(
        label="Rousseeuw 1987",
        citation="Rousseeuw, P. J. (1987). Silhouettes: a graphical aid "
                 "to the interpretation and validation of cluster "
                 "analysis. <i>Journal of Computational and Applied "
                 "Mathematics</i>, 20, 53–65.",
        url="https://doi.org/10.1016/0377-0427(87)90125-7",
        used="Silhouette validity index."),
    "calinski1974": dict(
        label="Caliński 1974",
        citation="Caliński, T. &amp; Harabasz, J. (1974). A dendrite "
                 "method for cluster analysis. <i>Communications in "
                 "Statistics</i>, 3(1), 1–27.",
        url="https://doi.org/10.1080/03610927408827101",
        used="Calinski–Harabasz validity index."),
    "davies1979": dict(
        label="Davies & Bouldin 1979",
        citation="Davies, D. L. &amp; Bouldin, D. W. (1979). A cluster "
                 "separation measure. <i>IEEE TPAMI</i>, 1(2), 224–227.",
        url="https://doi.org/10.1109/TPAMI.1979.4766909",
        used="Davies–Bouldin validity index."),
    "xie1991": dict(
        label="Xie & Beni 1991",
        citation="Xie, X. L. &amp; Beni, G. (1991). A validity measure "
                 "for fuzzy clustering. <i>IEEE TPAMI</i>, 13(8), "
                 "841–847.",
        url="https://doi.org/10.1109/34.85677",
        used="Xie–Beni validity index."),
    "dunn1974": dict(
        label="Dunn 1974",
        citation="Dunn, J. C. (1974). Well-separated clusters and optimal "
                 "fuzzy partitions. <i>Journal of Cybernetics</i>, 4(1), "
                 "95–104.",
        url="https://doi.org/10.1080/01969727408546059",
        used="Dunn validity index."),
    "hubert1976": dict(
        label="Hubert & Levin 1976",
        citation="Hubert, L. J. &amp; Levin, J. R. (1976). A general "
                 "statistical framework for assessing categorical "
                 "clustering in free recall. <i>Psychological "
                 "Bulletin</i>, 83(6), 1072–1080.",
        url="https://doi.org/10.1037/0033-2909.83.6.1072",
        used="C-index validity index."),
    "pakhira2004": dict(
        label="Pakhira 2004",
        citation="Pakhira, M. K., Bandyopadhyay, S. &amp; Maulik, U. "
                 "(2004). Validity index for crisp and fuzzy clusters. "
                 "<i>Pattern Recognition</i>, 37(3), 487–501.",
        url="https://doi.org/10.1016/j.patcog.2003.06.005",
        used="PBM validity index."),
    "halkidi2001": dict(
        label="Halkidi 2001",
        citation="Halkidi, M. &amp; Vazirgiannis, M. (2001). Clustering "
                 "validity assessment: finding the optimal partitioning "
                 "of a data set. <i>Proceedings of ICDM 2001</i>, "
                 "187–194.",
        url="https://doi.org/10.1109/ICDM.2001.989517",
        used="S_Dbw validity index."),
}


def render_latex(latex, color, fontsize=13, scale=2.0):
    """Render a LaTeX (mathtext) string to a high-DPI QPixmap.

    Args:
        latex (str): LaTeX source without surrounding dollar signs.
        color (str): Text color as a hex string.
        fontsize (float): Font size in points.
        scale (float): Supersampling factor for crisp rendering.

    Returns:
        QPixmap | None: Rendered equation, or None when matplotlib is
        unavailable or the expression fails to parse.
    """
    key = (latex, color, fontsize, scale)
    if key in _PIXMAP_CACHE:
        return _PIXMAP_CACHE[key]
    try:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        fig = Figure(figsize=(1, 1), dpi=100 * scale)
        canvas = FigureCanvasAgg(fig)
        fig.patch.set_alpha(0.0)
        text = fig.text(0, 0, f"${latex}$", fontsize=fontsize,
                        color=color, ha="left", va="bottom")
        canvas.draw()
        bbox = text.get_window_extent()
        pad = 4 * scale
        width = bbox.width + 2 * pad
        height = bbox.height + 2 * pad
        fig.set_size_inches(width / fig.dpi, height / fig.dpi)
        text.set_position((pad / width, pad / height))
        canvas.draw()
        buffer = canvas.buffer_rgba()
        image = QImage(bytes(buffer), int(fig.bbox.width),
                       int(fig.bbox.height), QImage.Format_RGBA8888).copy()
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(scale)
        _PIXMAP_CACHE[key] = pixmap
        return pixmap
    except Exception:
        _itk_log.exception("Could not render LaTeX: %s", latex)
        return None


class EquationLabel(QLabel):
    """Label displaying one LaTeX equation, re-rendered on theme change."""

    def __init__(self, latex, fontsize=13, parent=None):
        """Store the LaTeX source and render it.

        Args:
            latex (str): LaTeX source without dollar signs.
            fontsize (float): Font size in points.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self._latex = latex
        self._fontsize = fontsize
        self.setContentsMargins(26, 2, 2, 2)
        self._render()
        theme.themeChanged.connect(self._render)

    def _render(self):
        """Render the equation with the current theme text color."""
        pixmap = render_latex(self._latex, theme.palette.text_primary,
                              self._fontsize)
        if pixmap is None:
            self.setTextFormat(Qt.RichText)
            self.setText(f"<i>{self._latex}</i>")
        else:
            self.setPixmap(pixmap)


class ExampleBox(QFrame):
    """Highlighted 'Worked example' box, styled with the theme accent."""

    def __init__(self, html, parent=None):
        """Build the example box.

        Args:
            html (str): Rich-text body of the example.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self.setObjectName("exampleBox")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        self._label = QLabel(f"<p><b>Worked example</b></p>{html}")
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.RichText)
        self._label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        lay.addWidget(self._label)
        self.apply_theme()
        theme.themeChanged.connect(self.apply_theme)

    def apply_theme(self):
        """Apply the current theme palette to the box."""
        p = theme.palette
        self.setStyleSheet(f"""
            QFrame#exampleBox {{
                background-color: {p.bg_tertiary};
                border: 1px solid {p.border};
                border-left: 4px solid {p.accent};
                border-radius: 6px;
            }}
        """)
        self._label.setStyleSheet(
            f"font-size:12px; line-height:1.5; "
            f"color:{p.text_primary}; background:transparent;")


class RefEntry(QFrame):
    """One reference in the References section: full citation, where it
    is used in IsotopeTrack, and a clickable link to the study."""

    def __init__(self, key, parent=None):
        """Build the reference entry.

        Args:
            key (str): Key into REFERENCES.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self.setObjectName("refEntry")
        ref = REFERENCES[key]
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 10)
        link = ""
        if ref["url"]:
            link = (f"<br><a href='{ref['url']}'>{ref['url']}</a>")
        self._label = QLabel(
            f"<p><b>[{ref['label']}]</b>&nbsp; {ref['citation']}<br>"
            f"<i>Used in IsotopeTrack for:</i> {ref['used']}{link}</p>")
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.RichText)
        self._label.setOpenExternalLinks(True)
        self._label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        lay.addWidget(self._label)
        self.apply_theme()
        theme.themeChanged.connect(self.apply_theme)

    def apply_theme(self, highlight=False):
        """Apply the theme palette, optionally with a flash highlight.

        Args:
            highlight (bool): Draw the entry with an accent border when
                True (used briefly after a citation click).
        """
        p = theme.palette
        border = p.accent if highlight else p.border
        background = p.bg_hover if highlight else p.bg_tertiary
        self.setStyleSheet(f"""
            QFrame#refEntry {{
                background-color: {background};
                border: {'2' if highlight else '1'}px solid {border};
                border-radius: 6px;
            }}
        """)
        self._label.setStyleSheet(
            f"font-size:12px; line-height:1.5; "
            f"color:{p.text_primary}; background:transparent;")

    def flash(self):
        """Briefly highlight the entry after a citation click."""
        self.apply_theme(highlight=True)
        QTimer.singleShot(1600, self.apply_theme)


def _scroll_ancestor(widget):
    """Find the QScrollArea containing a widget, if any.

    Args:
        widget (QWidget): Widget whose ancestors are searched.

    Returns:
        QScrollArea | None: The enclosing scroll area.
    """
    parent = widget.parentWidget()
    while parent is not None and not isinstance(parent, QScrollArea):
        parent = parent.parentWidget()
    return parent


def _handle_link(href, container):
    """Handle a clicked link: jump to a reference or open a URL.

    Args:
        href (str): The clicked href — 'ref:<key>' for an in-text
            citation, otherwise an external URL.
        container (QWidget): Topic container holding the reference
            widgets in its _ref_widgets dict.
    """
    if href.startswith("ref:"):
        entry = getattr(container, "_ref_widgets", {}).get(href[4:])
        if entry is not None:
            scroll = _scroll_ancestor(entry)
            if scroll is not None:
                scroll.ensureWidgetVisible(entry, 0, 60)
            entry.flash()
    else:
        QDesktopServices.openUrl(QUrl(href))


def _prose_label(html):
    """Create a themed rich-text prose label.

    Args:
        html (str): Rich-text content.

    Returns:
        QLabel: Configured label.
    """
    label = QLabel(html)
    label.setWordWrap(True)
    label.setTextFormat(Qt.RichText)
    label.setOpenExternalLinks(True)
    label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    label.setStyleSheet(
        f"font-size:13px; line-height:1.5; "
        f"color:{theme.palette.text_primary}; background:transparent;")
    return label


def _where_html(rows):
    """Build the 'where:' parameter-definition table HTML.

    Args:
        rows (list[tuple[str, str]]): (symbol, definition) pairs.

    Returns:
        str: HTML for the parameter table.
    """
    body = "".join(
        f"<tr><td width='130'><b>{sym}</b></td><td>{desc}</td></tr>"
        for sym, desc in rows)
    return ("<p><i>where:</i></p>"
            f"<table cellspacing='0' cellpadding='3'>{body}</table>")


def build_topic_widget(topic_key, parent=None):
    """Build the widget for one equations topic.

    Args:
        topic_key (str): Key into TOPICS ('sensitivity', 'transport',
            'detection', 'quantification', 'clustering').
        parent (QWidget | None): Parent widget.

    Returns:
        QWidget: Vertical stack of prose, LaTeX equations, parameter
        tables and worked-example boxes.
    """
    container = QWidget(parent)
    container._ref_widgets = {}
    lay = QVBoxLayout(container)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)

    def _connect(label):
        """Route the label's links through the citation handler.

        Args:
            label (QLabel): Prose label possibly containing links.
        """
        label.setOpenExternalLinks(False)
        label.linkActivated.connect(
            lambda href, c=container: _handle_link(href, c))
        return label

    for kind, payload in TOPICS[topic_key]:
        if kind == "h":
            lay.addWidget(_connect(_prose_label(payload)))
        elif kind == "eq":
            lay.addWidget(EquationLabel(payload))
        elif kind == "where":
            lay.addWidget(_connect(_prose_label(_where_html(payload))))
        elif kind == "ex":
            lay.addWidget(ExampleBox(payload))
        elif kind == "refs":
            lay.addWidget(_prose_label(
                "<h3>References</h3>"
                "<p>Click a citation marker anywhere above to jump here; "
                "click a link to open the study.</p>"))
            for key in payload:
                entry = RefEntry(key, container)
                container._ref_widgets[key] = entry
                lay.addWidget(entry)
    return container


TOPIC_SENSITIVITY = [
    ("h", """
     <h2>Sensitivity — equations &amp; worked examples</h2>
     <p>Three regression models relate the measured signal <i>S</i> (cps)
     of dissolved standards to their concentration <i>C</i>; the best R²
     is selected automatically.</p>
     <h3>1 · Force through zero (FTZ)</h3>
     <p>Least squares with the intercept fixed at zero — appropriate when
     a blank produces no signal.</p>"""),
    ("eq", r"S = a\,C"),
    ("eq", r"a = \frac{\sum_i C_i S_i}{\sum_i C_i^2}"),
    ("eq", r"R^2 = 1 - \frac{\sum_i (S_i - \hat{S}_i)^2}{\sum_i S_i^2}"),
    ("where", [
        ("S", "measured signal (counts per second, cps)"),
        ("C", "standard concentration (e.g. ppb)"),
        ("a", "sensitivity — calibration slope (cps per concentration unit)"),
        ("Ŝᵢ", "signal predicted by the fit at Cᵢ"),
    ]),
    ("ex", """
     <p>⁸⁰Se standards at C = 0, 2, 5, 10, 20 ppb give mean signals
     S = 0, 4 824, 12 059, 24 118, 48 236 cps.</p>
     <p>Σ CᵢSᵢ = 2·4824 + 5·12059 + 10·24118 + 20·48236 = 1 275 843;
     Σ Cᵢ² = 4 + 25 + 100 + 400 = 529.</p>
     <p><b>a = 1 275 843 / 529 = 2 412 cps/ppb</b>, R² = 0.9997 — exactly
     the fit shown in the Calibration Results screenshot
     (y = 2412·x, R² = 0.99970).</p>"""),
    ("h", """
     <h3>2 · Simple linear (OLS)</h3>
     <p>Ordinary least squares with a free intercept — accounts for a
     constant blank contribution.</p>"""),
    ("eq", r"S = a\,C + b"),
    ("eq", r"[a,\ b]^{T} = (X^{T}X)^{-1}X^{T}S"),
    ("eq",
     r"R^2 = 1 - \frac{\sum_i (S_i - \hat{S}_i)^2}{\sum_i (S_i - \bar{S})^2}"),
    ("where", [
        ("b", "intercept (cps) — signal at zero concentration"),
        ("X", "design matrix: concentrations plus a column of ones"),
        ("S̄", "mean measured signal"),
    ]),
    ("ex", """
     <p>Same ⁸⁰Se standards but with a 150 cps blank background on every
     measurement: the fit returns a = 2 412 cps/ppb and b = 150 cps.
     The predicted signal at 5 ppb is
     Ŝ = 2412·5 + 150 = <b>12 210 cps</b>. FTZ would be biased here,
     which is why OLS wins the R² comparison for such data.</p>"""),
    ("h", """
     <h3>3 · Weighted linear (WLS)</h3>
     <p>Each standard is weighted by the inverse of its signal variance,
     so precise points dominate the fit.</p>"""),
    ("eq", r"w_i = 1/\sigma_i^{2}"),
    ("eq",
     r"a = \frac{\sum w \sum wCS - \sum wC \sum wS}"
     r"{\sum w \sum wC^2 - (\sum wC)^2}"),
    ("eq",
     r"b = \frac{\sum wC^2 \sum wS - \sum wC \sum wCS}"
     r"{\sum w \sum wC^2 - (\sum wC)^2}"),
    ("eq",
     r"R_w^2 = 1 - \frac{\sum_i w_i (S_i-\hat{S}_i)^2}"
     r"{\sum_i w_i (S_i-\bar{S}_w)^2}"),
    ("where", [
        ("wᵢ", "weight of standard i"),
        ("σᵢ", "standard deviation of the replicate signal of standard i"),
        ("S̄_w", "weighted mean signal"),
    ]),
    ("ex", """
     <p>The blank replicates scatter by σ = 50 cps while the 20 ppb
     standard scatters by σ = 3 100 cps. Their weight ratio is
     (1/50²)/(1/3100²) = (3100/50)² ≈ <b>3 844×</b> — the low end of the
     curve anchors the fit, which improves LOD accuracy. When all σᵢ are
     equal the solution reduces to OLS.</p>"""),
    ("h", """
     <h3>Figures of merit</h3>
     <p>Computed from the selected fit for every isotope, following the
     3σ/10σ convention <a href='ref:currie1968'>[Currie 1968]</a>
     <a href='ref:miller2010'>[Miller &amp; Miller 2010]</a>.</p>"""),
    ("eq", r"LOD = \frac{3\,\sigma_{blank}}{a} \qquad "
           r"LOQ = \frac{10\,\sigma_{blank}}{a} \qquad "
           r"BEC = \frac{b}{a}"),
    ("where", [
        ("LOD", "limit of detection (concentration units)"),
        ("LOQ", "limit of quantification (concentration units)"),
        ("BEC", "blank-equivalent concentration (0 for FTZ, where b ≡ 0)"),
        ("σ_blank", "standard deviation of the lowest standard's signal "
                    "(proxy for blank noise)"),
    ]),
    ("ex", """
     <p>⁸⁰Se: σ_blank = 456 cps, a = 2 412 cps/ppb →
     LOD = 3·456/2412 = <b>0.567 ppb</b> and
     LOQ = 10·456/2412 = <b>1.89 ppb</b> — the exact LOD/LOQ values shown
     in the Calibration Results table (5.67×10⁻¹ and 1.89×10⁰ ppb).</p>"""),
    ("refs", ["currie1968", "miller2010"]),
]


TOPIC_TRANSPORT = [
    ("h", """
     <h2>Transport Rate — equations &amp; worked examples</h2>
     <p>The transport rate η<sub>V</sub> (µL/s) is the volume of sample
     that reaches the plasma per unit time
     <a href='ref:pace2011'>[Pace 2011]</a>. The average of the selected
     methods is used in every conversion. The transport-efficiency and
     size-detection-limit figure shown above is adapted from
     <a href='ref:hadioui2019'>[Hadioui 2019]</a>.</p>
     <h3>1 · Liquid weight method</h3>
     <p>Direct gravimetric measurement over a timed aspiration.</p>"""),
    ("eq", r"m_{consumed} = m_{initial} - m_{final}"),
    ("eq", r"m_{plasma} = m_{consumed} - m_{waste}"),
    ("eq", r"\eta_V = \frac{m_{plasma}\cdot 1000}{t}"),
    ("where", [
        ("m_initial", "sample mass before aspiration (g)"),
        ("m_final", "sample mass after aspiration (g)"),
        ("m_waste", "mass gained by the waste container (g)"),
        ("m_plasma", "liquid reaching the plasma (g ≈ mL for water)"),
        ("t", "analysis time (s)"),
        ("η_V", "transport rate (µL/s)"),
    ]),
    ("ex", """
     <p>Vial: 50.000 g → 48.000 g (2.000 g consumed); waste container
     gains 1.200 g; t = 1 800 s.</p>
     <p>m_plasma = 2.000 − 1.200 = 0.800 g →
     η_V = 800 µL / 1800 s = <b>0.444 µL/s</b> — matching the average
     rate (0.443 µL/s) shown in Calibration Information.</p>"""),
    ("h", """
     <h3>2 · Particle number method</h3>
     <p>A reference nanoparticle standard of certified size and mass
     concentration: the expected particle number is compared with the
     number actually detected <a href='ref:pace2011'>[Pace 2011]</a>.</p>"""),
    ("eq", r"m_p = \rho\,\frac{\pi}{6}\,d^{3}"),
    ("eq", r"C_N = \frac{C_m}{m_p}"),
    ("eq", r"\eta_V = \frac{N_{detected}}{C_N \cdot t}"),
    ("where", [
        ("d", "certified particle diameter (nm → m)"),
        ("ρ", "particle density (g/cm³ → kg/m³)"),
        ("m_p", "mass of one particle (kg, reported in fg)"),
        ("C_m", "mass concentration of the standard (ng/L)"),
        ("C_N", "number concentration (particles/mL)"),
        ("N_detected", "particle events detected"),
        ("t", "effective acquisition time (s), exclusion windows removed"),
        ("η_V", "transport rate (reported in µL/s)"),
    ]),
    ("ex", """
     <p>60 nm Au standard (ρ = 19.32 g/cm³) at C_m = 10 ng/L, measured
     60 s, 120 particles detected.</p>
     <p>m_p = 19 320 · (π/6) · (60×10⁻⁹)³ = 2.19×10⁻¹⁸ kg =
     <b>2.19 fg</b>;<br>
     C_N = 10 ng/L ÷ 2.19×10⁻³ ng = 4.58×10⁶ /L = 4 577 /mL;<br>
     η_V = 120 / (4577 · 60) = 4.37×10⁻⁴ mL/s = <b>0.437 µL/s</b>.</p>"""),
    ("h", """
     <h3>3 · Particle mass method</h3>
     <p>The sensitivity to dissolved standards (per unit time) divided by
     the sensitivity to particle standards of known mass gives the volume
     flow contributing to the signal
     <a href='ref:pace2011'>[Pace 2011]</a>.</p>"""),
    ("eq", r"\eta_V = \frac{a_{ionic}'}{a_{particle}}"),
    ("where", [
        ("a_particle", "particle calibration slope — signal vs particle "
                       "mass (counts/fg)"),
        ("a_ionic′", "ionic slope converted to counts·s⁻¹ per µg/L "
                     "(ppb slopes divided by 1000)"),
        ("η_V", "transport rate (µL/s)"),
    ]),
    ("ex", """
     <p>a_ionic = 2 412 cps/ppb → a_ionic′ = 2.412 counts·s⁻¹ per µg/L;
     particle standards give a_particle = 5.45 counts/fg.</p>
     <p>η_V = 2.412 / 5.45 = <b>0.443 µL/s</b> — consistent with the two
     other methods above.</p>"""),
    ("h", "<h3>Averaging</h3>"),
    ("eq", r"\bar{\eta}_V = \frac{1}{n}\sum_{selected} \eta_{V}"),
    ("ex", """
     <p>If only the Particle Method (0.4430 µL/s) is ticked in
     Calibration Information → Transport Rate, then
     η̄_V = <b>0.4430 µL/s</b> from 1 selected method — exactly the
     status line shown in that dialog.</p>"""),
    ("refs", ["pace2011", "hadioui2019"]),
]

TOPIC_DETECTION = [
    ("h", """
     <h2>Detection &amp; Single-Ion Distribution (SIA)</h2>
     <h3>Background model — Poisson</h3>
     <p>The dissolved/instrumental background in counts per dwell follows
     Poisson counting statistics.</p>"""),
    ("eq", r"P(k;\lambda) = \frac{\lambda^{k} e^{-\lambda}}{k!}"),
    ("where", [
        ("k", "observed counts in one dwell"),
        ("λ", "mean background counts per dwell (estimated iteratively)"),
    ]),
    ("ex", """
     <p>With λ = 0.5 counts/dwell: P(0) = e⁻⁰·⁵ = 60.7 %,
     P(1) = 30.3 %, P(2) = 7.6 %, and P(k ≥ 5) ≈ 2×10⁻⁴ — rare
     background spikes still occur, which is why the threshold must be
     set from the full distribution rather than the mean.</p>"""),
    ("h", """
     <h3>Single-ion distribution (SIA) — the σ parameter</h3>
     <p>On a ToF detector, one ion does not always produce the same
     signal: single-ion areas A follow a log-normal distribution
     <a href='ref:lockwood2025'>[Lockwood 2025]</a>. The SIA data
     (uploaded from a Nu Vitesse folder or TOFWERK file) is used to fit
     σ.</p>"""),
    ("eq",
     r"f(A) = \frac{1}{A\,\sigma\sqrt{2\pi}}\;"
     r"\exp\!\left(-\frac{(\ln A - \mu)^2}{2\sigma^2}\right)"),
    ("eq", r"\mu = -\sigma^{2}/2 \quad (\mathrm{unit\ mean})"),
    ("eq", r"\bar{\sigma} = \frac{1}{M}\sum_{m=1}^{M} \sigma_m , \qquad "
           r"\mathrm{outlier} \Leftrightarrow "
           r"|\sigma_m - \bar{\sigma}| > 2\,s_{\sigma}"),
    ("where", [
        ("A", "single-ion area (counts)"),
        ("σ", "log-normal shape parameter of the single-ion response"),
        ("μ", "log-normal location; fixed so the mean response is 1"),
        ("σ_m", "σ fitted for one mass m/z"),
        ("σ̄, s_σ", "mean and standard deviation of σ over all masses "
                    "(the global σ used as fallback)"),
        ("M", "number of masses with SIA data"),
    ]),
    ("ex", """
     <p>Sample 71A_2ppb: 402 distribution points, mean signal
     2 532.8 counts → global σ = <b>0.632</b>. The individual
     distribution of Mg-24 fits σ = <b>0.56</b>. Across all masses the
     mean σ is 0.623, and 2 masses fall outside ±2 SD and are flagged
     as outliers (red in the Sigma Comparison plot) — excluding them
     refines the global σ. <i>Assign Per-Mass σ</i> writes each σ_m into
     the parameters table.</p>"""),
    ("h", """
     <h3>Compound Poisson–LogNormal (CPLN) threshold</h3>
     <p>Monte Carlo modelling first showed that low-count ToF signals
     follow a compound Poisson distribution
     <a href='ref:gundlach2018'>[Gundlach-Graham 2018]</a>, and
     compound-Poisson critical values were then established as detection
     decision levels for sp-ICP-TOFMS
     <a href='ref:hendriks2019'>[Hendriks 2019]</a>
     <a href='ref:gundlach2023'>[Gundlach-Graham 2023]</a>. IsotopeTrack
     models a dwell's signal as the sum of N single-ion areas with
     N ~ Poisson(λ) <a href='ref:lockwood2025'>[Lockwood 2025]</a>: the
     detection threshold is the (1 − α) quantile of this compound
     distribution, evaluated with the zero-truncated quantile and the
     Fenton–Wilkinson approximation for sums of log-normals
     <a href='ref:fenton1960'>[Fenton 1960]</a>. The <i>CPLN table</i>
     method draws the same quantile from a precomputed λ×σ lookup table
     for speed and accuracy at high σ and λ
     <a href='ref:lockwood2025b'>[Lockwood 2025b]</a>.</p>"""),
    ("eq", r"\mathrm{signal} = \sum_{i=1}^{N} A_i,\quad "
           r"N \sim \mathrm{Poisson}(\lambda),\quad "
           r"A_i \sim \mathrm{LogNormal}(\mu,\sigma)"),
    ("eq", r"T = Q_{CPLN}(1-\alpha;\ \lambda,\mu,\sigma)"),
    ("eq", r"q_0 = \frac{q - e^{-\lambda}}{1 - e^{-\lambda}}"),
    ("eq", r"\sigma_x^2 = \ln\!\left(\frac{e^{\sigma^2}-1}{k}+1\right), "
           r"\qquad \mu_x = \ln k + \mu + \frac{\sigma^2 - \sigma_x^2}{2}"),
    ("where", [
        ("α", "false-positive rate per dwell (Alpha column, default 10⁻⁶)"),
        ("T", "detection threshold (counts per dwell)"),
        ("q₀", "zero-truncated quantile level"),
        ("k", "number of ions in the sum"),
        ("μₓ, σₓ", "log-normal parameters approximating the sum of k "
                   "single-ion areas (Fenton–Wilkinson)"),
    ]),
    ("ex", """
     <p>λ = 0.5 counts/dwell, σ = 0.55, α = 10⁻⁶ →
     <b>T = 11.49 counts</b> (computed with IsotopeTrack's own CPLN
     implementation). A Gaussian rule λ + 3√λ would give only
     2.6 counts and drown the results in false positives — this is why
     CPLN is the default for ToF data. The <i>CPLN table</i> method
     reads the same quantile from a precomputed λ×σ lookup table for
     speed; the fallback when the approximation fails numerically is
     T = λ + 3√λ (e.g. 19.5 for λ = 10).</p>"""),
    ("h", """
     <h3>Iterative background refinement (with Aitken Δ²)</h3>
     <p>Particles bias a naive background estimate upward, so background
     and threshold are refined as a fixed-point iteration accelerated by
     Aitken's Δ² extrapolation.</p>"""),
    ("eq", r"\lambda_n = \mathrm{mean}\left(\,\mathrm{signal}"
           r"[\mathrm{signal} < T_{n-1}]\,\right), \qquad T_n = f(\lambda_n)"),
    ("eq", r"T_{accel} = T_0 - \frac{(T_1-T_0)^2}{T_2 - 2T_1 + T_0}"),
    ("where", [
        ("Tₙ", "threshold at iteration n"),
        ("f", "threshold function of the chosen method"),
        ("T₀, T₁, T₂", "three consecutive iterates used for extrapolation"),
    ]),
    ("ex", """
     <p>Iterates T₀ = 20, T₁ = 16, T₂ = 14.7 counts →
     T_accel = 20 − (16−20)²/(14.7 − 32 + 20) = 20 − 16/2.7 =
     <b>14.07 counts</b> — the converged threshold in one extra step
     instead of several. With <i>Window Size</i> enabled, λ becomes a
     rolling mean so the threshold follows slow background drift.</p>"""),
    ("h", """
     <h3>Particle acceptance and counts-based LOD</h3>
     <p>Decision limits follow the counting-statistics framework of
     <a href='ref:currie1968'>[Currie 1968]</a>.</p>"""),
    ("eq", r"\mathrm{accepted} \Leftrightarrow \geq n_{min}\ "
           r"\mathrm{consecutive\ dwells\ with\ signal} > T"),
    ("eq", r"LOD_{counts} = T, \qquad LOD_{MDL} = \max(0,\ T-\lambda)"),
    ("where", [
        ("n_min", "Min Points parameter"),
        ("LOD_MDL", "net counts above background, used for the mass "
                    "detection limit"),
    ]),
    ("ex", """
     <p>With T = 11.49 and n_min = 2, a single isolated dwell of
     14 counts is rejected (only 1 point above T), while two consecutive
     dwells of 14 and 13 counts are accepted as one particle.
     LOD_MDL = 11.49 − 0.5 ≈ <b>11.0 counts</b>.</p>"""),
    ("h", """
     <h3>1D Watershed peak splitting</h3>
     <p>Overlapping particle events are split at signal valleys.</p>"""),
    ("eq", r"\mathrm{split} \Leftrightarrow "
           r"\frac{v}{\min(p_{left},\,p_{right})} < r_{valley}"),
    ("where", [
        ("v", "signal at the valley minimum"),
        ("p_left, p_right", "heights of the two neighbouring maxima"),
        ("r_valley", "Valley Ratio parameter (default 0.50)"),
    ]),
    ("ex", """
     <p>Two maxima of 100 and 180 counts with a valley of 40 counts:
     40 / min(100, 180) = 0.40 &lt; 0.50 → the region is <b>split</b> at
     the valley into two particles. The rule is applied recursively for
     nested doublets.</p>"""),
    ("h", """
     <h3>Detector non-linearity (saturation) filter</h3>
     <p>Saturated events are recognised from their flat-topped shape.</p>"""),
    ("eq", r"\mathrm{flagged} \Leftrightarrow FWHM > FWHM_{max}\ \wedge\ "
           r"SNR \geq SNR_{min}\ \wedge\ \frac{W_{top}}{FWHM} \geq r_{flat}"),
    ("where", [
        ("FWHM", "full width at half maximum of the peak (ms)"),
        ("FWHM_max", "maximum allowed width (default 1.5 ms)"),
        ("SNR", "peak height over background noise (default min 10)"),
        ("W_top", "width measured at the configured height "
                  "(default 90 % of maximum)"),
        ("r_flat", "minimum flat-top ratio (default 0.50)"),
    ]),
    ("ex", """
     <p>A ⁵⁶Fe event with FWHM = 2.3 ms, SNR = 45 and
     W_top/FWHM = 0.61 meets all three criteria → its whole time window
     is excluded for <b>all</b> isotopes and its duration is subtracted
     from the analysis time used for concentrations.</p>"""),
    ("refs", ["gundlach2018", "hendriks2019", "lockwood2025",
              "lockwood2025b", "gundlach2023", "fenton1960",
              "currie1968"]),
]


TOPIC_QUANTIFICATION = [
    ("h", """
     <h2>Quantification — from counts to mass, size and concentration</h2>
     <p>The conversion chain follows the established spICP-MS framework
     <a href='ref:pace2011'>[Pace 2011]</a>
     <a href='ref:laborda2014'>[Laborda 2014]</a>.</p>
     <h3>Counts → element mass</h3>
     <p>The ionic sensitivity divided by the transport rate converts
     integrated counts of a particle event into element mass.</p>"""),
    ("eq", r"f = \frac{a}{\bar{\eta}_V \cdot 1000}"),
    ("eq", r"m_{el} = \frac{I_p}{f}"),
    ("where", [
        ("a", "ionic calibration slope of the isotope (cps per µg/L)"),
        ("η̄_V", "average transport rate (µL/s)"),
        ("f", "conversion factor (counts per fg)"),
        ("I_p", "integrated counts of one particle event"),
        ("m_el", "element mass in the particle (fg)"),
    ]),
    ("ex", """
     <p>⁵⁶Fe: a = 2 412 cps/ppb, η̄_V = 0.443 µL/s →
     f = 2412/(0.443·1000) = <b>5.445 counts/fg</b>.
     The multi-element particle #1643 carried I_p = 1 722 Fe counts →
     m_Fe = 1722/5.445 = <b>316 fg</b>.</p>"""),
    ("h", """
     <h3>Element mass → particle (compound) mass</h3>
     <p>If the particles are a compound, the element mass is scaled by
     its mass fraction.</p>"""),
    ("eq", r"m_{part} = \frac{m_{el}}{w_{el}}"),
    ("eq", r"M_{compound} = \sum_i n_i M_i, \qquad "
           r"w_{el} = \frac{n_{el}\,M_{el}}{M_{compound}}"),
    ("where", [
        ("w_el", "mass fraction of the element in the compound "
                 "(Tools → Mass Fraction Calculator; 1.0 for pure "
                 "elements)"),
        ("nᵢ", "stoichiometric count of element i in the formula"),
        ("Mᵢ", "atomic mass of element i (g/mol)"),
        ("M_compound", "molecular weight of the compound (g/mol)"),
    ]),
    ("ex", """
     <p>Magnetite Fe₃O₄: M = 3·55.845 + 4·15.999 = 231.53 g/mol,
     w_Fe = 167.54/231.53 = <b>0.724</b>. The 316 fg of Fe above →
     m_part = 316/0.724 = <b>437 fg of Fe₃O₄</b>.
     Another example: TiO₂ gives M = 79.87 g/mol and w_Ti = 0.599.</p>"""),
    ("h", "<h3>Moles per particle (molar &amp; isotopic ratios)</h3>"),
    ("eq", r"n_{el} = \frac{m_{el}}{M_{el}}\ (\mathrm{fmol}), \qquad "
           r"n_{part} = \frac{m_{part}}{M_{compound}}\ (\mathrm{fmol})"),
    ("ex", """
     <p>n_Fe = 316/55.845 = <b>5.66 fmol</b>;
     n_Fe₃O₄ = 437/231.53 = <b>1.89 fmol</b>.
     The molar-ratio views of the results canvas plot ratios such as
     n_Fe/n_Ni between two elements of the same particle; isotopic
     ratios compare two isotopes of one element the same way.</p>"""),
    ("h", "<h3>Mass → spherical diameter</h3>"),
    ("eq", r"d = \left(\frac{6\,m}{\pi\,\rho}\right)^{1/3}"),
    ("where", [
        ("m", "particle mass (fg → g)"),
        ("ρ", "particle density (g/cm³, from the materials database)"),
        ("d", "equivalent spherical diameter (→ nm)"),
    ]),
    ("ex", """
     <p>m = 437 fg of Fe₃O₄ (ρ = 5.17 g/cm³):
     d = (6·4.37×10⁻¹³ / (π·5.17))^(1/3) = 5.45×10⁻⁵ cm =
     <b>545 nm</b>.</p>"""),
    ("h", "<h3>Analyzed volume and concentrations</h3>"),
    ("eq", r"V_{eff} = \frac{\bar{\eta}_V \cdot t_{eff}}{1000}\ (\mathrm{mL})"),
    ("eq", r"C_p = \frac{N_{particles}}{V_{eff}}, \qquad "
           r"C_{p,corr} = C_p \cdot D"),
    ("where", [
        ("t_eff", "effective acquisition time (s): total minus manual "
                  "exclusions and non-linearity-filtered windows"),
        ("V_eff", "analyzed sample volume (mL)"),
        ("N_particles", "number of detected particles"),
        ("C_p", "particle number concentration (particles/mL)"),
        ("D", "dilution factor (Tools → Dilution Factor)"),
    ]),
    ("ex", """
     <p>η̄_V = 0.443 µL/s over t_eff = 60 s →
     V_eff = 0.443·60/1000 = <b>0.0266 mL</b>. With 1 550 particles:
     C_p = 1550/0.0266 = <b>5.8×10⁴ particles/mL</b>; the sample was
     diluted 100 000× → C_p,corr = <b>5.8×10⁹ particles/mL</b>.</p>"""),
    ("h", "<h3>Mass and size detection limits per isotope</h3>"),
    ("eq", r"MDL = \frac{LOD_{MDL}}{f}, \qquad MQL = MDL \cdot \frac{10}{3}"),
    ("eq", r"SDL = \left(\frac{6\,MDL}{\pi\rho}\right)^{1/3}, \qquad "
           r"SQL = \left(\frac{6\,MQL}{\pi\rho}\right)^{1/3}"),
    ("eq", r"C_{bkg} = \frac{\lambda / t_{dwell}}{a} \cdot 1000\ "
           r"(\mathrm{ppt})"),
    ("where", [
        ("MDL, MQL", "mass detection / quantification limit (fg)"),
        ("SDL, SQL", "size detection / quantification limit (nm)"),
        ("t_dwell", "dwell time (s)"),
        ("C_bkg", "dissolved background expressed as concentration"),
    ]),
    ("ex", """
     <p>⁵⁶Fe: LOD_MDL = 16.5 counts, f = 5.445 counts/fg →
     MDL = <b>3.03 fg</b>, MQL = <b>10.1 fg</b>. With ρ_Fe =
     7.87 g/cm³: SDL = <b>90 nm</b>, SQL = <b>135 nm</b> — the values
     reported in Calibration Information → Ionic Calibration.
     Background: λ = 0.05 counts per 0.1 ms dwell → 500 cps →
     C_bkg = 500/2412·1000 = <b>207 ppt</b>.</p>"""),
    ("refs", ["pace2011", "laborda2014"]),
]

TOPIC_CLUSTERING = [
    ("h", """
     <h2>Clustering — every method, explained</h2>
     <p>The Clustering node groups particles by their multi-element
     composition (counts, masses or moles per element). The pipeline is:
     feature scaling → optional dimensionality reduction → clustering
     algorithm → validity indices to score the partition and choose the
     number of clusters.</p>
     <h3>Feature scaling (z-scores)</h3>
     <p>Elements have very different signal magnitudes, so every feature
     is standardised first — otherwise the largest element dominates all
     distances.</p>"""),
    ("eq", r"z = \frac{x - \bar{x}}{s}"),
    ("where", [
        ("x", "feature value (e.g. Fe mass of one particle)"),
        ("x̄, s", "mean and standard deviation of that feature over all "
                  "particles"),
    ]),
    ("ex", """
     <p>Fe masses average 300 fg with s = 120 fg. A particle with
     540 fg becomes z = (540−300)/120 = <b>2.0</b> — two standard
     deviations above the mean, directly comparable with the z-scores of
     Ni or Co no matter their absolute scale.</p>"""),
    ("h", """
     <h3>Dimensionality reduction</h3>
     <p><b>PCA</b> <a href='ref:pearson1901'>[Pearson 1901]</a> rotates
     the data onto orthogonal axes of maximal variance (eigenvectors of
     the covariance matrix) — with many isotopes, the first 2–3
     components usually carry most of the structure.</p>"""),
    ("eq", r"\max_{\Vert u \Vert = 1}\ \mathrm{Var}(Xu) "
           r"\ \Rightarrow\ \Sigma u = \lambda u"),
    ("h", """
     <p><b>t-SNE</b> <a href='ref:vandermaaten2008'>[van der Maaten
     2008]</a> embeds particles in 2D by matching pairwise similarity
     distributions (p in high dimension, q in the embedding) through the
     Kullback–Leibler divergence — excellent for visual inspection, but
     distances between far clusters are not quantitative.</p>"""),
    ("eq", r"KL(P\Vert Q) = \sum_{i \neq j} p_{ij}\,"
           r"\ln\frac{p_{ij}}{q_{ij}}"),
    ("ex", """
     <p>42 samples × 54 isotopes → PCA first: PC1 captures the
     Fe–Ni–Co alloy axis (72 % of variance), PC2 separates Si-rich
     particles. Clustering on 2 PCs instead of 54 raw features is faster
     and less noisy.</p>"""),
    ("h", """
     <h3>Partitioning methods</h3>
     <p><b>K-Means</b> <a href='ref:lloyd1982'>[Lloyd 1982]</a> — picks
     k centroids, assigns each particle to the nearest one, recomputes
     centroids, repeats (Lloyd's algorithm). Fast and reliable for
     round, similar-sized clusters; k must be chosen (use the validity
     indices).</p>"""),
    ("eq", r"J = \sum_{c=1}^{k}\ \sum_{x \in c} \Vert x - \mu_c \Vert^2"),
    ("h", """
     <p><b>Mini-Batch K-Means</b>
     <a href='ref:sculley2010'>[Sculley 2010]</a> — the same objective
     optimised on random subsets (mini-batches); nearly identical
     results on large particle populations at a fraction of the time.</p>
     <p><b>Gaussian Mixture Model (GMM)</b> — soft clustering: the data
     is modelled as a sum of k Gaussians and each particle gets a
     membership probability γ for every component, fitted by
     Expectation–Maximisation
     <a href='ref:dempster1977'>[Dempster 1977]</a>.</p>"""),
    ("eq", r"p(x) = \sum_{c=1}^{k} \pi_c\, \mathcal{N}(x;\,\mu_c,\Sigma_c)"),
    ("eq", r"\gamma_{ic} = \frac{\pi_c \mathcal{N}(x_i;\mu_c,\Sigma_c)}"
           r"{\sum_j \pi_j \mathcal{N}(x_i;\mu_j,\Sigma_j)}"),
    ("where", [
        ("μ_c", "centroid (K-Means) or mean (GMM) of cluster c"),
        ("π_c, Σ_c", "mixture weight and covariance of component c"),
        ("γ_ic", "probability that particle i belongs to component c"),
    ]),
    ("ex", """
     <p>Fe–Ni particle data with k = 2: K-Means converges to centroids
     μ₁ = (z_Fe 1.2, z_Ni 1.1) — the alloy cluster — and
     μ₂ = (0.4, −0.9) — pure-Fe particles. A borderline particle gets
     GMM memberships γ = (0.65, 0.35) instead of a hard label, useful
     when compositions overlap.</p>"""),
    ("h", """
     <h3>Density-based methods</h3>
     <p><b>DBSCAN</b> <a href='ref:ester1996'>[Ester 1996]</a> — a
     particle is a <i>core point</i> if at least minPts neighbours lie
     within radius ε; clusters are chains of connected core points,
     everything unreachable is labelled noise. Finds arbitrarily shaped
     clusters and needs no k, but ε is sensitive.</p>"""),
    ("eq", r"\mathrm{core}(x) \Leftrightarrow |N_\varepsilon(x)| \geq minPts"),
    ("h", """
     <p><b>HDBSCAN</b> <a href='ref:campello2013'>[Campello 2013]</a> —
     hierarchical DBSCAN over all densities: it replaces distances with
     the <i>mutual reachability distance</i>, builds a density hierarchy
     and keeps the most stable clusters, so no ε needs to be chosen.
     Usually the best default for spICP-ToF-MS data.</p>"""),
    ("eq", r"d_{mreach}(a,b) = \max\{\,core_k(a),\ core_k(b),\ d(a,b)\,\}"),
    ("h", """
     <p><b>OPTICS</b> <a href='ref:ankerst1999'>[Ankerst 1999]</a> —
     orders points by reachability distance instead of fixing one ε;
     valleys in the reachability plot are clusters at any density.</p>"""),
    ("eq", r"reach(o,p) = \max\{\,core(p),\ d(p,o)\,\}"),
    ("h", """
     <p><b>Mean Shift</b>
     <a href='ref:comaniciu2002'>[Comaniciu 2002]</a> — every point
     climbs the estimated density gradient by repeatedly moving to the
     weighted mean of its neighbourhood (kernel bandwidth h); points
     converging to the same mode form one cluster. k is discovered
     automatically.</p>"""),
    ("eq", r"m(x) = \frac{\sum_i x_i\,K\!\left(\frac{x_i - x}{h}\right)}"
           r"{\sum_i K\!\left(\frac{x_i - x}{h}\right)} - x"),
    ("where", [
        ("ε", "neighbourhood radius (DBSCAN)"),
        ("minPts", "minimum neighbours for a core point"),
        ("core_k(a)", "distance from a to its k-th nearest neighbour"),
        ("K, h", "kernel function and bandwidth (Mean Shift)"),
    ]),
    ("ex", """
     <p>A dilution series produces a dense cloud of background-like
     small particles plus two sparse alloy populations. DBSCAN with
     ε = 0.5, minPts = 10 marks 3 % of particles as noise and finds
     both alloy clusters without specifying k; HDBSCAN finds the same
     structure with no tuning at all.</p>"""),
    ("h", """
     <h3>Hierarchical and graph methods</h3>
     <p><b>Hierarchical (agglomerative)</b> — starts with every particle
     as its own cluster and repeatedly merges the two closest, producing
     a dendrogram that is cut at k clusters. IsotopeTrack uses Ward
     linkage <a href='ref:ward1963'>[Ward 1963]</a>, which merges the
     pair causing the smallest increase of within-cluster variance.
     Hierarchical clustering of spICP-ToF-MS fingerprints has been used
     to identify engineered and natural nanoparticles
     <a href='ref:tharaud2022'>[Tharaud 2022]</a>.</p>"""),
    ("eq", r"\Delta(i,j) = \frac{n_i\,n_j}{n_i + n_j}\,"
           r"\Vert \mu_i - \mu_j \Vert^2"),
    ("h", """
     <p><b>Spectral clustering</b>
     <a href='ref:vonluxburg2007'>[von Luxburg 2007]</a> — builds a
     similarity graph between particles, computes the graph Laplacian,
     and clusters the rows of its first k eigenvectors with K-Means.
     Captures non-convex shapes that defeat plain K-Means; a comparative
     study on multi-element nanoparticle data found spectral clustering
     the most robust choice, ahead of hierarchical clustering and
     t-SNE + DBSCAN <a href='ref:erfani2023'>[Erfani 2023]</a>.</p>"""),
    ("eq", r"L = D - W, \qquad L\,u = \lambda\,u"),
    ("h", """
     <p><b>Birch</b> <a href='ref:zhang1996'>[Zhang 1996]</a> — streams
     particles into a tree of Clustering Features CF = (N, LS, SS)
     (count, linear sum, square sum), from which centroids and radii are
     computed without revisiting the data — built for very large
     datasets.</p>"""),
    ("eq", r"CF = (N,\ \vec{LS},\ SS), \qquad "
           r"\mu = \vec{LS}/N"),
    ("h", """
     <p><b>Self-Organising Map (SOM)</b>
     <a href='ref:kohonen1982'>[Kohonen 1982]</a> — a grid of neurons
     with weight vectors is trained so that neighbouring neurons respond
     to similar particles; the winning neuron b and its neighbours move
     toward each presented particle. SOMs have been applied to detect
     and classify natural and engineered nanoparticles from
     spICP-ToF-MS data <a href='ref:cuss2025'>[Cuss 2025]</a>.</p>"""),
    ("eq", r"w(t+1) = w(t) + \alpha(t)\,h_{b}(t)\,\left(x - w(t)\right)"),
    ("where", [
        ("n_i, μ_i", "size and centroid of cluster i (Ward)"),
        ("W, D, L", "similarity matrix, degree matrix and Laplacian"),
        ("N, LS, SS", "count, linear sum, square sum of a CF node"),
        ("α(t), h_b(t)", "learning rate and neighbourhood function "
                         "around the winner b"),
    ]),
    ("ex", """
     <p>Cutting a Ward dendrogram of 2 000 particles at k = 3 splits
     them into Fe-rich, FeNiCo-alloy and Si-rich groups; the same data
     on a 8×8 SOM shows the alloy particles occupying one corner of the
     map — a quick visual fingerprint of the sample.</p>"""),
    ("h", """
     <h3>Cluster validity indices — choosing k and scoring partitions</h3>
     <p><b>Silhouette</b> <a href='ref:rousseeuw1987'>[Rousseeuw
     1987]</a> (higher is better, range −1…1): compares each particle's
     cohesion with its separation.</p>"""),
    ("eq", r"s(i) = \frac{b(i) - a(i)}{\max\{a(i),\,b(i)\}}"),
    ("ex", """
     <p>A particle sits on average a(i) = 0.2 from its own cluster and
     b(i) = 0.8 from the nearest other cluster →
     s = (0.8−0.2)/0.8 = <b>0.75</b> — well clustered. Averaged over all
     particles, the k with the highest mean silhouette wins.</p>"""),
    ("h", """
     <p><b>Calinski–Harabasz</b>
     <a href='ref:calinski1974'>[Caliński 1974]</a> (higher better):
     between-cluster over within-cluster dispersion.</p>"""),
    ("eq", r"CH = \frac{\mathrm{tr}(B)/(k-1)}{\mathrm{tr}(W)/(n-k)}"),
    ("h", "<p><b>Davies–Bouldin</b> <a href='ref:davies1979'>[Davies "
          "&amp; Bouldin 1979]</a> (lower better): worst-case overlap "
          "of each cluster with its most similar neighbour.</p>"),
    ("eq", r"DB = \frac{1}{k}\sum_{i=1}^{k} \max_{j \neq i}"
           r"\frac{\sigma_i + \sigma_j}{d(c_i, c_j)}"),
    ("ex", """
     <p>Two clusters with mean internal spreads σ₁ = 0.3, σ₂ = 0.4 and
     centroid distance 2.0 → DB = (0.3+0.4)/2.0 = <b>0.35</b> — compact
     and far apart. Values above ≈1 signal heavy overlap.</p>"""),
    ("h", "<p><b>Xie–Beni</b> <a href='ref:xie1991'>[Xie &amp; Beni "
          "1991]</a> (lower better): total within-cluster scatter over "
          "the closest pair of centroids.</p>"),
    ("eq", r"XB = \frac{\sum_i \Vert x_i - \mu_{c(i)} \Vert^2}"
           r"{n \cdot \min_{i \neq j} d^2(c_i, c_j)}"),
    ("h", "<p><b>Dunn</b> <a href='ref:dunn1974'>[Dunn 1974]</a> "
          "(higher better): smallest inter-cluster distance over the "
          "largest cluster diameter.</p>"),
    ("eq", r"D = \frac{\min_{i \neq j} d(C_i, C_j)}"
           r"{\max_k\ \mathrm{diam}(C_k)}"),
    ("ex", """
     <p>Closest clusters are 1.5 apart (z-units) and the widest cluster
     has diameter 0.6 → D = 1.5/0.6 = <b>2.5</b>; anything above 1
     means clusters are separated by more than their own size.</p>"""),
    ("h", "<p><b>C-index</b> <a href='ref:hubert1976'>[Hubert &amp; "
          "Levin 1976]</a> (lower better): compares the sum of "
          "within-cluster distances with the best and worst possible "
          "sums over the same number of pairs.</p>"),
    ("eq", r"C = \frac{S_w - S_{min}}{S_{max} - S_{min}}"),
    ("h", """
     <p><b>PBM</b> <a href='ref:pakhira2004'>[Pakhira 2004]</a> (higher
     better) and <b>S_Dbw</b> <a href='ref:halkidi2001'>[Halkidi
     2001]</a> (lower better) complete the panel — PBM rewards compact,
     well-separated partitions relative to the unclustered data; S_Dbw
     combines average cluster scatter with inter-cluster density.
     IsotopeTrack evaluates all eight indices across a range of k and
     highlights the consensus optimum.</p>"""),
    ("where", [
        ("a(i)", "mean distance of particle i to its own cluster"),
        ("b(i)", "mean distance of particle i to the nearest other "
                 "cluster"),
        ("B, W", "between- and within-cluster scatter matrices"),
        ("k, n", "number of clusters and of particles"),
        ("σ_i, c_i", "mean spread and centroid of cluster i"),
        ("S_w", "sum of within-cluster pairwise distances; S_min/S_max "
                "are its best/worst possible values"),
    ]),
    ("ex", """
     <p><b>Full workflow example.</b> 2 709a+2 710a mixture, 1 550
     particles, features = z-scored masses of Fe, Ni, Co, Si. PCA → 2
     components (81 %). HDBSCAN finds 3 clusters + 2 % noise. Scores:
     silhouette 0.71, CH 1 840, DB 0.42, Dunn 1.8 — consistent, so the
     partition is trusted. Cluster 1 (Fe:Ni:Co ≈ 0.71:0.19:0.10, n=612)
     is the FeNiCo alloy; cluster 2 is pure Fe (n=803); cluster 3 is
     Si-rich (n=104). The composition wheel and heatmap nodes then
     visualise exactly these groups.</p>"""),
    ("refs", [
        "tharaud2022", "erfani2023", "cuss2025",
        "lloyd1982", "sculley2010", "dempster1977", "ester1996",
        "campello2013", "ankerst1999", "comaniciu2002", "ward1963",
        "vonluxburg2007", "zhang1996", "kohonen1982", "pearson1901",
        "vandermaaten2008", "rousseeuw1987", "calinski1974", "davies1979",
        "xie1991", "dunn1974", "hubert1976", "pakhira2004", "halkidi2001",
    ]),
]


TOPICS = {
    "sensitivity": TOPIC_SENSITIVITY,
    "transport": TOPIC_TRANSPORT,
    "detection": TOPIC_DETECTION,
    "quantification": TOPIC_QUANTIFICATION,
    "clustering": TOPIC_CLUSTERING,
}
