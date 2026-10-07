"""The Insights side panel of the results canvas.

The panel searches every loaded sample on its own with the engine in
:mod:`results.insights.engine`, lists what it finds under section headings,
explains each finding, and builds the plot or the explained figure a finding
calls for, behind a selector holding only the samples and elements involved.

Public entry points for the canvas dialog are :func:`integrate_insights_panel`
and :func:`make_insights_toggle_button`.
"""

from __future__ import annotations

import copy
import re

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMenu, QProgressBar, QPushButton, QScrollArea,
    QSplitter, QToolButton, QVBoxLayout, QWidget,
)

from results.figure_builder.core.limits import detection_limits
from results.insights import discovery as _disc
from results.insights import figures as _figures
from results.insights.explain import explanation_for
from results.insights.engine import (
    _ANALYSERS, _FONT, FOCUSED_CARD_LIMIT, NODE_TYPE_META, AnalysisScope, Suggestion,
    _AnalysisWorker, _dedupe_suggestions, _find_batch_node, _itk_log, analysers_for,
    category_keys, gather_scope_data, invalidate_context_cache, node_type_keys,
    resolve_scope,
)
from tools.theme import theme as _theme


def _find_source_node(scene) -> object | None:
    """Find the node a newly added plot node should be wired to.

    Picks the configured node carrying the most particles, on the assumption
    that it is the one the user is actually working from.

    Args:
        scene: The canvas scene.

    Returns:
        The chosen workflow node, or ``None`` if nothing on the canvas has
        output data yet.
    """
    best, best_n = None, 0
    for node in scene.workflow_nodes:
        if not getattr(node, "_has_output", False):
            continue
        for d in [
            *(
                [node.get_output_data()]
                if hasattr(node, "get_output_data")
                else []
            ),
            getattr(node, "input_data", None),
        ]:
            if not isinstance(d, dict):
                continue
            cnt = len(d.get("particle_data", []))
            if cnt > best_n:
                best, best_n = node, cnt
    return best


_NODE_SLOT_W = 150


_NODE_SLOT_H = 125


_SLOT_SPAN = 6


def _occupied_rects(scene) -> list[tuple[float, float, float, float]]:
    """List the space every node on the canvas already takes up.

    Args:
        scene: The canvas scene.

    Returns:
        One ``(left, top, right, bottom)`` box per placed node.
    """
    boxes = []
    for item in getattr(scene, "node_items", {}).values():
        try:
            pos = item.pos()
            left, top = float(pos.x()), float(pos.y())
        except Exception:
            continue
        width = float(getattr(item, "width", 0) or _NODE_SLOT_W)
        height = float(getattr(item, "height", 0) or _NODE_SLOT_H)
        boxes.append((left, top, left + width, top + height))
    return boxes


def _free_position(scene, preferred):
    """Find a spot for a new node that no existing node is sitting on.

    The old placement walked a fixed diagonal, which looks fine for the first
    couple of nodes and then starts dropping them on top of each other. This
    starts from where the node ideally wants to go, works rightwards along the
    row, and wraps to the next row once the row is full.

    Args:
        scene: The canvas scene.
        preferred: The ``QPointF`` the caller would like to use.

    Returns:
        A ``QPointF`` that overlaps nothing, or *preferred* when the canvas is
        empty.
    """
    boxes = _occupied_rects(scene)
    if not boxes:
        return preferred

    def clear(x: float, y: float) -> bool:
        """Report whether a node placed at this corner would overlap anything.

        Args:
            x: Left edge of the candidate slot.
            y: Top edge of the candidate slot.

        Returns:
            True when the slot is free.
        """
        right, bottom = x + _NODE_SLOT_W, y + _NODE_SLOT_H
        for left, top, r, b in boxes:
            if x < r and right > left and y < b and bottom > top:
                return False
        return True

    start_x, start_y = float(preferred.x()), float(preferred.y())
    for step in range(64):
        row, column = divmod(step, _SLOT_SPAN)
        x = start_x + column * _NODE_SLOT_W
        y = start_y + row * _NODE_SLOT_H
        if clear(x, y):
            return QPointF(x, y)

    return QPointF(start_x + 65 * _NODE_SLOT_W, start_y)


def _raw_pool_for(scene, parent_window) -> dict:
    """Every loaded particle by sample, as the engine reads it."""
    from results.insights.engine import _raw_pool
    return _raw_pool(scene, parent_window)


def _isotope_entries(parent_window, scene, labels) -> list[dict]:
    """Resolve element labels into the isotope records a selector expects.

    A selector node stores isotopes as dicts carrying ``symbol``, ``mass``,
    ``key`` and ``label``. Particle data only ever names the label, so the
    remaining fields are recovered from the isotopes the app has loaded. They
    matter because the configuration dialog matches on symbol and mass, and a
    record missing them would open blank.

    Args:
        parent_window: Main window exposing ``selected_isotopes`` and
            ``get_formatted_label``.
        scene: The canvas scene, checked for a batch node whose isotope list
            takes precedence.
        labels: Element labels to resolve, e.g. ``("56Fe", "55Mn")``.

    Returns:
        One record per resolved label, in the order given. Labels that cannot
        be matched are skipped, so an empty list means none resolved.
    """
    available = None
    for node in getattr(scene, "workflow_nodes", []):
        batch = getattr(node, "batch_available_isotopes", None)
        if batch:
            available = batch
            break
    if not available:
        available = getattr(parent_window, "selected_isotopes", None)
    if not isinstance(available, dict) or not available:
        return []

    formatter = getattr(parent_window, "get_formatted_label", None)
    by_label: dict[str, dict] = {}
    for symbol, masses in available.items():
        for mass in masses or ():
            try:
                key = f"{symbol}-{float(mass):.4f}"
            except (TypeError, ValueError):
                continue
            label = key
            if callable(formatter):
                try:
                    label = formatter(key) or key
                except Exception:
                    _itk_log.exception("[Insights] label lookup failed")
            by_label.setdefault(
                label,
                {"symbol": symbol, "mass": mass, "key": key, "label": label},
            )

    return [by_label[l] for l in labels if l in by_label]


SECTIONS: tuple[tuple[str, frozenset], ...] = (
    ("Data quality", frozenset({"quality", "time"})),
    ("Interferences", frozenset({"interference"})),
    ("Isotope ratios", frozenset({"isotope", "isotope_groups"})),
    ("Differences between groups", frozenset({"comparison", "signature"})),
    ("Replicates", frozenset({"replicate"})),
    ("Fixed ratios and co-occurrence", frozenset({"stoichiometry", "cooccurrence"})),
    ("Correlations", frozenset({"correlation", "network"})),
    ("Composition", frozenset({"composition", "ternary", "single_multi", "size"})),
    ("Particle types", frozenset({"types"})),
    ("Distributions and rare particles", frozenset({"distribution", "outlier", "rare"})),
)
"""Card sections in the order the panel lists them.

Findings that affect whether the data can be trusted come first, then what
the data says about isotopes, groups and composition.
"""


_ISOTOPE_IN_TEXT = re.compile(r"(?<![\w.])(\d{1,3})([A-Z][a-z]?)(?![a-z])")


def isotope_markup(text: str) -> str:
    """Write isotope labels in text with a superscript mass number.

    ``"206Pb/207Pb"`` becomes ``"<sup>206</sup>Pb/<sup>207</sup>Pb"``; the rest
    of the text is escaped so it displays as written.

    Args:
        text: Plain text from a finding.

    Returns:
        Rich text for a ``QLabel``.
    """
    import html
    escaped = html.escape(text, quote=False)
    return _ISOTOPE_IN_TEXT.sub(r"<sup>\1</sup>\2", escaped)


def section_of(category: str) -> str:
    """Return the section heading a finding of *category* is listed under."""
    for title, categories in SECTIONS:
        if category in categories:
            return title
    return SECTIONS[-1][0]


def strength_label(confidence: float) -> tuple[str, int]:
    """Word and number of filled dots describing how strong a finding is."""
    if confidence >= 0.75:
        return "Strong", 3
    if confidence >= 0.45:
        return "Moderate", 2
    return "Weak", 1


class _IsotopeTile(QWidget):
    """A small periodic-table tile: mass number above the element symbol."""

    def __init__(self, label: str, parent=None):
        """Create a tile for an isotope label such as ``"56Fe"``."""
        super().__init__(parent)
        mass, symbol = _disc.mass_symbol(label)
        self._mass = str(mass) if mass else ""
        self._symbol = symbol or label
        self.setToolTip(label)
        width = 30 if len(self._symbol) <= 2 else 36
        self.setFixedSize(width, 32)

    def paintEvent(self, event):
        """Draw the tile in the current theme."""
        from PySide6.QtGui import QColor, QFont, QPainter, QPen
        p = _theme.palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.setPen(QPen(QColor(p.border), 1))
        painter.setBrush(QColor(p.bg_primary))
        painter.drawRoundedRect(rect, 4, 4)
        small = QFont(self.font())
        small.setPixelSize(8)
        painter.setFont(small)
        painter.setPen(QColor(p.text_muted))
        painter.drawText(rect.adjusted(4, 2, 0, 0), Qt.AlignLeft | Qt.AlignTop, self._mass)
        big = QFont(self.font())
        big.setPixelSize(13)
        big.setBold(True)
        painter.setFont(big)
        painter.setPen(QColor(p.text_primary))
        painter.drawText(rect.adjusted(0, 8, 0, 0), Qt.AlignHCenter | Qt.AlignVCenter,
                         self._symbol)
        painter.end()


class _RefreshButton(QPushButton):
    """Square button drawing its own circular arrow.

    The arrow is painted rather than typed as a glyph, because the "↻"
    character is missing from some system fonts and then shows as a
    placeholder.
    """

    def __init__(self, parent=None):
        """Create the button without text; the arrow is drawn in :meth:`paintEvent`."""
        super().__init__("", parent)
        self.setAttribute(Qt.WA_Hover, True)

    def paintEvent(self, event):
        """Draw the frame from the style sheet, then the arrow in the theme colour."""
        super().paintEvent(event)
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
        p = _theme.palette
        if not self.isEnabled():
            colour = p.disabled
        elif self.underMouse():
            colour = p.text_primary
        else:
            colour = p.text_secondary
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height())
        r = side * 0.26
        cx, cy = self.width() / 2, self.height() / 2
        box = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        pen = QPen(QColor(colour), max(1.6, side / 16))
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(box, 60 * 16, 290 * 16)
        tip = QPointF(cx + r * 0.5, cy - r * 0.866)
        head = r * 0.75
        arrow = QPainterPath()
        arrow.moveTo(tip + QPointF(-head * 0.95, -head * 0.55))
        arrow.lineTo(tip)
        arrow.lineTo(tip + QPointF(-head * 0.2, head * 1.05))
        painter.drawPath(arrow)
        painter.end()


class _StrengthDots(QWidget):
    """Three dots, filled to show how strong a finding is."""

    def __init__(self, filled: int, parent=None):
        """Create the dots with *filled* of three filled."""
        super().__init__(parent)
        self._filled = filled
        self.setFixedSize(26, 10)

    def paintEvent(self, event):
        """Draw the dots in the theme's accent colour."""
        from PySide6.QtGui import QColor, QPainter
        p = _theme.palette
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        for i in range(3):
            painter.setBrush(QColor(p.accent if i < self._filled else p.border))
            painter.drawEllipse(i * 9, 2, 6, 6)
        painter.end()


class _Card(QFrame):
    """One finding in the panel.

    The isotopes the finding is about lead the card as periodic-table tiles,
    followed by the headline, the evidence, the samples it covers, how strong
    it is, and a button naming the plot it adds.
    """

    def __init__(self, s: Suggestion, on_add, samples_text: str = "", on_figure=None,
                 parent=None, on_cluster=None):
        """Build a card for one suggestion.

        Args:
            s: The suggestion to display.
            on_add: Callback invoked with *s* when the add button is pressed.
            samples_text: Short description of the samples the finding covers.
            on_figure: Callback invoked with *s* to add the explained figure,
                or ``None`` when the finding has no figure design.
            parent: Optional parent widget.
            on_cluster: Callback invoked with *s* to explore a particle-type
                finding in the Clustering node; only particle-type cards
                show the button.
        """
        super().__init__(parent)
        self._s = s
        self._on_add = on_add
        self._on_figure = on_figure
        self._on_cluster = on_cluster if s.category == "types" else None
        self._samples_text = samples_text
        self._details: QWidget | None = None
        self.setObjectName("insightCard")
        self._build()

    def _build(self):
        """Lay out the card's contents."""
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(5)

        if self._s.elements:
            tiles = QHBoxLayout()
            tiles.setSpacing(4)
            for label in self._s.elements[:6]:
                tiles.addWidget(_IsotopeTile(label))
            if len(self._s.elements) > 6:
                more = QLabel(f"+{len(self._s.elements) - 6}")
                more.setObjectName("iMuted")
                tiles.addWidget(more)
            tiles.addStretch()
            root.addLayout(tiles)

        title = QLabel(isotope_markup(self._s.title))
        title.setTextFormat(Qt.RichText)
        title.setObjectName("iCardTitle")
        title.setWordWrap(True)
        root.addWidget(title)

        reason = QLabel(isotope_markup(self._s.reasoning))
        reason.setTextFormat(Qt.RichText)
        reason.setObjectName("iCardBody")
        reason.setWordWrap(True)
        reason.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(reason)

        if self._samples_text:
            samples = QLabel(self._samples_text)
            samples.setObjectName("iMuted")
            samples.setWordWrap(True)
            root.addWidget(samples)

        explanation = explanation_for(self._s.explain_key, self._s.category)
        if self._s.details or explanation is not None:
            self._details_btn = QToolButton()
            self._details_btn.setObjectName("iDetailsBtn")
            self._details_btn.setText("Show details")
            self._details_btn.setCursor(Qt.PointingHandCursor)
            self._details_btn.clicked.connect(self._toggle_details)
            root.addWidget(self._details_btn, 0, Qt.AlignLeft)
            self._details = self._build_details(explanation)
            self._details.setVisible(False)
            root.addWidget(self._details)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        word, filled = strength_label(self._s.confidence)
        dots = _StrengthDots(filled)
        dots.setToolTip(f"Ranking score {self._s.confidence:.2f}")
        footer.addWidget(dots)
        strength = QLabel(word)
        strength.setObjectName("iMuted")
        footer.addWidget(strength)
        footer.addStretch()
        plot_name = NODE_TYPE_META.get(self._s.node_type, "plot")
        self._add_btn = QPushButton(f"Add {plot_name.lower()}"
                                    + ("" if plot_name.lower().endswith(("plot", "builder",
                                                                         "chart", "matrix"))
                                       else " plot"))
        self._add_btn.setObjectName("iAddBtn")
        self._add_btn.setCursor(Qt.PointingHandCursor)
        self._add_btn.setToolTip("Adds the plot with a selector holding only these samples "
                                 "and elements")
        self._add_btn.clicked.connect(self._clicked)
        footer.addWidget(self._add_btn)
        root.addLayout(footer)

        if self._on_figure is not None:
            figure_row = QHBoxLayout()
            figure_row.addStretch()
            self._figure_btn = QPushButton("Add explained figure")
            self._figure_btn.setObjectName("iFigureBtn")
            self._figure_btn.setCursor(Qt.PointingHandCursor)
            self._figure_btn.setToolTip(
                "Adds a Figure Builder figure, panels a to f with a legend, that tells this "
                "finding's story: the pattern, the evidence, what it means and its limits")
            self._figure_btn.clicked.connect(self._figure_clicked)
            if self._on_cluster is not None:
                self._cluster_btn = QPushButton("Explore in Clustering")
                self._cluster_btn.setObjectName("iFigureBtn")
                self._cluster_btn.setCursor(Qt.PointingHandCursor)
                self._cluster_btn.setToolTip(
                    "Adds a Clustering node fed by a selector with these samples and elements, "
                    "to explore the particle types further with your own settings")
                self._cluster_btn.clicked.connect(lambda: self._on_cluster(self._s))
                figure_row.addWidget(self._cluster_btn)
            figure_row.addWidget(self._figure_btn)
            root.addLayout(figure_row)

    def _build_details(self, explanation) -> QWidget:
        """Build the hidden details section: key numbers, then the explanation."""
        box = QFrame()
        box.setObjectName("iDetails")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)
        if self._s.details:
            from PySide6.QtWidgets import QGridLayout
            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(2)
            for row, (label, value) in enumerate(self._s.details):
                name = QLabel(isotope_markup(str(label)))
                name.setObjectName("iDetailKey")
                name.setTextFormat(Qt.RichText)
                name.setWordWrap(True)
                val = QLabel(isotope_markup(str(value)))
                val.setObjectName("iDetailValue")
                val.setTextFormat(Qt.RichText)
                val.setWordWrap(True)
                val.setTextInteractionFlags(Qt.TextSelectableByMouse)
                grid.addWidget(name, row, 0, Qt.AlignTop)
                grid.addWidget(val, row, 1, Qt.AlignTop)
            grid.setColumnStretch(1, 1)
            lay.addLayout(grid)
        if explanation is not None:
            for text in (explanation.found, explanation.meaning, explanation.check):
                para = QLabel(isotope_markup(text))
                para.setObjectName("iDetailText")
                para.setTextFormat(Qt.RichText)
                para.setWordWrap(True)
                lay.addWidget(para)
        return box

    def _toggle_details(self):
        """Show or hide the details section."""
        if self._details is None:
            return
        shown = not self._details.isVisible()
        self._details.setVisible(shown)
        self._details_btn.setText("Hide details" if shown else "Show details")

    def _figure_clicked(self):
        """Add the explained figure, and confirm on the button."""
        self._on_figure(self._s)
        original = self._figure_btn.text()
        self._figure_btn.setText("Figure added")
        self._figure_btn.setEnabled(False)

        def restore():
            """Put the button back as it was."""
            try:
                self._figure_btn.setText(original)
                self._figure_btn.setEnabled(True)
            except RuntimeError:
                pass

        QTimer.singleShot(1400, restore)

    def _clicked(self):
        """Add the plot, and confirm on the button."""
        self._on_add(self._s)
        original = self._add_btn.text()
        self._add_btn.setText("Added")
        self._add_btn.setEnabled(False)

        def restore():
            """Put the button back as it was."""
            try:
                self._add_btn.setText(original)
                self._add_btn.setEnabled(True)
            except RuntimeError:
                pass

        QTimer.singleShot(1400, restore)


def selection_units(s: Suggestion, scope: AnalysisScope | None) -> list[tuple[str, tuple[str, ...]]]:
    """Group a suggestion's samples the way its selector will treat them.

    Args:
        s: The suggestion.
        scope: The scope it was found in, used when the suggestion names no
            samples of its own.

    Returns:
        ``(label, members)`` pairs. A label shared by several members is a
        replicate group the selector pools; a lone member keeps its own name.
    """
    if s.samples:
        samples = list(s.samples)
        groups = dict(s.sample_groups)
    elif scope is not None:
        samples = list(scope.sample_names)
        groups = {}
        for g in scope.groups:
            for m in g.members:
                groups[m] = g.name if g.is_replicated else ""
    else:
        return []
    units: dict[str, list[str]] = {}
    for m in samples:
        label = groups.get(m) or m
        units.setdefault(label, []).append(m)
    return [(label, tuple(members)) for label, members in units.items()]


def describe_samples(s: Suggestion, scope: AnalysisScope | None) -> str:
    """Describe the samples a card covers in a few words.

    Args:
        s: The suggestion.
        scope: The scope it was found in.

    Returns:
        Text such as ``"liver (3 replicates), kidney"``.
    """
    units = selection_units(s, scope)
    if not units:
        return ""
    parts = []
    for label, members in units[:4]:
        if len(members) > 1:
            parts.append(f"{label} ({len(members)} replicates)")
        else:
            parts.append(members[0])
    text = ", ".join(parts)
    if len(units) > 4:
        text += f" and {len(units) - 4} more"
    return text


def describe_scope(scope: AnalysisScope) -> tuple[str, str]:
    """Two plain sentences describing what Insights searches.

    Args:
        scope: The resolved scope.

    Returns:
        ``(samples_sentence, replicates_sentence)``.
    """
    n = len(scope.sample_names)
    first = (f"{n} sample{'s' if n != 1 else ''} and {scope.total_particles:,} particles, "
             "every element.")
    replicated = [g for g in scope.groups if g.is_replicated]
    if not replicated:
        return first, "No replicates found."
    shown = ", ".join(f"{g.name} ({len(g.members)})" for g in replicated[:4])
    if len(replicated) > 4:
        shown += f" and {len(replicated) - 4} more"
    sources = {g.source for g in replicated}
    origin = ("your selector groups" if sources == {"user"}
              else "sample names" if sources == {"auto"}
              else "your groups and sample names")
    return first, f"Replicates: {shown}, from {origin}."


_FILTER_KEY = "insights/plot_filter"


def _load_filter() -> str | None:
    """Read the plot type the user last chose to show, or ``None`` for all."""
    try:
        from PySide6.QtCore import QSettings
        raw = QSettings("IsotopeTrack", "IsotopeTrack").value(_FILTER_KEY, "")
    except Exception:
        return None
    raw = str(raw or "")
    return raw if raw in NODE_TYPE_META else None


def _save_filter(node_type: str | None) -> None:
    """Remember which plot type the user chose to show."""
    try:
        from PySide6.QtCore import QSettings
        QSettings("IsotopeTrack", "IsotopeTrack").setValue(_FILTER_KEY, node_type or "")
    except Exception:
        _itk_log.debug("[Insights] could not save the plot type filter")


def _discard(widget: QWidget):
    """Take a widget off the screen now and delete it once Qt is idle.

    ``deleteLater`` alone leaves the widget drawn where it was until the
    event loop gets round to deleting it, which after a menu click can be
    long enough for old cards to stay on screen next to the new ones.
    """
    widget.hide()
    widget.setParent(None)
    widget.deleteLater()


def card_key(s: Suggestion) -> tuple:
    """Identity of a finding's card, so a card can be kept across refreshes."""
    return (s.node_type, s.category, s.title, tuple(s.samples), tuple(s.elements))


# ──────────────────────────────────────────────────────────────────────────────
# The integrated panel
# ──────────────────────────────────────────────────────────────────────────────

class SmartInsightsPanel(QWidget):
    """Resizable pane that searches the data and lists what it finds.

    Embedded as the rightmost pane of the canvas splitter and hidden by default,
    toggled by the button from :func:`make_insights_toggle_button`.

    The panel searches on its own: when it is shown, when the loaded samples or
    their replicate groups change, and when another plot type is picked. Every
    loaded sample and every element is searched, whatever is selected on the
    canvas. The plot types menu chooses which kinds of plot to search for;
    findings are listed under section headings, and each card builds its plot
    with only the samples and elements the finding is about.

    Use :func:`integrate_insights_panel` to construct and attach one rather than
    instantiating this directly.
    """

    SCOPE_POLL_MS = 2500
    MIN_WIDTH = 320
    DEFAULT_WIDTH = 380
    MIN_CANVAS = 320
    """How often a visible panel checks whether the loaded data changed."""

    def __init__(self, scene, parent_window, parent=None):
        """Build the panel and subscribe it to theme and selection changes.

        Args:
            scene: The canvas scene to analyse and watch for changes.
            parent_window: Main window holding the loaded particle data.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._scene = scene
        self._pw = parent_window
        self._worker: _AnalysisWorker | None = None
        self._suggestions: list[Suggestion] = []
        self._found: list[Suggestion] = []
        self._ran: set[str] = set()
        self._pending: set[str] = set()
        self._scope: AnalysisScope | None = None
        self._retired: list[_AnalysisWorker] = []
        self._filter: str | None = _load_filter()
        self._cards: dict[tuple, _Card] = {}
        self._held = False
        self.setMinimumWidth(self.MIN_WIDTH)

        self._build_ui()
        self._apply_theme()
        self._theme_dc = _theme.connect_theme(lambda _: self._apply_theme())

        self._poll = QTimer(self)
        self._poll.setInterval(self.SCOPE_POLL_MS)
        self._poll.timeout.connect(self._check_scope)

        try:
            scene.node_selection_changed.connect(self._on_scene_selection)
        except Exception:
            _itk_log.debug("[Insights] scene has no node_selection_changed signal")

    def _build_ui(self):
        """Assemble the header, scope summary, plot type menu and finding list."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._hdr = QFrame()
        self._hdr.setObjectName("iHdr")
        head = QVBoxLayout(self._hdr)
        head.setContentsMargins(14, 12, 10, 10)
        head.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(6)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        self._title_lbl = QLabel("Insights")
        self._title_lbl.setObjectName("iTitleLbl")
        self._count_lbl = QLabel("")
        self._count_lbl.setObjectName("iCountLbl")
        titles.addWidget(self._title_lbl)
        titles.addWidget(self._count_lbl)
        top.addLayout(titles)
        top.addStretch()
        self._refresh_btn = _RefreshButton()
        self._refresh_btn.setObjectName("iRefreshBtn")
        self._refresh_btn.setFixedSize(28, 28)
        self._refresh_btn.setToolTip("Search again from scratch")
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.clicked.connect(self.refresh)
        top.addWidget(self._refresh_btn, 0, Qt.AlignTop)
        head.addLayout(top)

        self._sample_lbl = QLabel("")
        self._sample_lbl.setObjectName("iScopeLbl")
        self._sample_lbl.setWordWrap(True)
        self._group_lbl = QLabel("")
        self._group_lbl.setObjectName("iScopeLbl")
        self._group_lbl.setWordWrap(True)
        head.addWidget(self._sample_lbl)
        head.addWidget(self._group_lbl)

        self._types_btn = QToolButton()
        self._types_btn.setObjectName("iTypesBtn")
        self._types_btn.setPopupMode(QToolButton.InstantPopup)
        self._types_btn.setCursor(Qt.PointingHandCursor)
        self._types_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        from PySide6.QtGui import QActionGroup
        self._types_menu = QMenu(self._types_btn)
        group = QActionGroup(self._types_menu)
        group.setExclusive(True)
        self._all_action = self._types_menu.addAction("All plot types")
        self._all_action.setCheckable(True)
        group.addAction(self._all_action)
        self._all_action.triggered.connect(lambda: self._set_filter(None))
        self._types_menu.addSeparator()
        self._type_actions = {}
        for key in node_type_keys():
            action = self._types_menu.addAction(NODE_TYPE_META[key])
            action.setCheckable(True)
            group.addAction(action)
            action.triggered.connect(lambda _checked=False, k=key: self._set_filter(k))
            self._type_actions[key] = action
        self._sync_filter_actions()
        self._types_btn.setMenu(self._types_menu)
        types_row = QHBoxLayout()
        types_row.addWidget(self._types_btn)
        types_row.addStretch()
        head.addLayout(types_row)
        root.addWidget(self._hdr)

        self._bar = QProgressBar()
        self._bar.setObjectName("iBar")
        self._bar.setRange(0, 0)
        self._bar.setFixedHeight(2)
        self._bar.setTextVisible(False)
        self._bar.setVisible(False)
        root.addWidget(self._bar)

        self._status = QLabel("")
        self._status.setObjectName("iStatus")
        self._status.setWordWrap(True)
        self._status.setVisible(False)
        root.addWidget(self._status)

        self._new_bar = QPushButton("")
        self._new_bar.setObjectName("iNewBar")
        self._new_bar.setCursor(Qt.PointingHandCursor)
        self._new_bar.setVisible(False)
        self._new_bar.clicked.connect(self._release_held)
        root.addWidget(self._new_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._card_w = QWidget()
        self._card_w.setObjectName("iCardW")
        self._card_layout = QVBoxLayout(self._card_w)
        self._card_layout.setContentsMargins(10, 6, 10, 12)
        self._card_layout.setSpacing(8)
        self._card_layout.addStretch()
        scroll.setWidget(self._card_w)
        root.addWidget(scroll, 1)
        self._scroll = scroll
        scroll.viewport().installEventFilter(self)

        self._chips = self._type_actions
        self._update_types_label()

    def _apply_theme(self):
        """Restyle the panel from the current theme palette."""
        p = _theme.palette
        self.setStyleSheet(f"""
            SmartInsightsPanel {{ background: {p.bg_primary}; border-left: 1px solid {p.border}; }}
            QFrame#iHdr {{ background: {p.bg_primary}; border-bottom: 1px solid {p.border_subtle}; }}
            QLabel#iTitleLbl {{ color: {p.text_primary}; font-size: 15px; font-weight: 600;
                               background: transparent; }}
            QLabel#iCountLbl {{ color: {p.text_muted}; font-size: 11px; background: transparent; }}
            QLabel#iScopeLbl {{ color: {p.text_secondary}; font-size: 11px; background: transparent; }}
            QLabel#iStatus {{ color: {p.text_muted}; font-size: 11px; background: transparent;
                             padding: 6px 14px 0 14px; }}
            QLabel#iSection {{ color: {p.text_primary}; font-size: 12px; font-weight: 600;
                              background: transparent; padding: 10px 2px 0 2px; }}
            QLabel#iSectionCount {{ color: {p.text_muted}; font-size: 11px; background: transparent;
                                   padding: 10px 2px 0 2px; }}
            QLabel#iPlaceholder {{ color: {p.text_secondary}; font-size: 12px; background: transparent;
                                  padding: 28px 12px; }}
            QToolButton#iTypesBtn {{ background: {p.bg_secondary}; color: {p.text_primary};
                                    border: 1px solid {p.border}; border-radius: 6px;
                                    padding: 4px 10px; font-size: 11px; }}
            QToolButton#iTypesBtn:hover {{ border-color: {p.accent}; }}
            QToolButton#iTypesBtn::menu-indicator {{ image: none; width: 0; }}
            QPushButton#iRefreshBtn {{ background: transparent; color: {p.text_secondary};
                                      border: 1px solid {p.border_subtle}; border-radius: 6px; }}
            QPushButton#iRefreshBtn:hover {{ color: {p.text_primary}; border-color: {p.accent}; }}
            QPushButton#iRefreshBtn:disabled {{ color: {p.disabled}; }}
            QFrame#insightCard {{ background: {p.bg_secondary}; border: 1px solid {p.border_subtle};
                                 border-radius: 8px; }}
            QFrame#insightCard:hover {{ border-color: {p.border_strong}; }}
            QFrame#insightCard QLabel {{ background: transparent; }}
            QLabel#iCardTitle {{ color: {p.text_primary}; font-size: 13px; font-weight: 600; }}
            QLabel#iCardBody {{ color: {p.text_secondary}; font-size: 11px; }}
            QLabel#iMuted {{ color: {p.text_muted}; font-size: 10px; }}
            QPushButton#iAddBtn {{ background: transparent; color: {p.accent};
                                  border: 1px solid {p.accent}; border-radius: 6px;
                                  padding: 3px 10px; font-size: 11px; font-weight: 600; }}
            QPushButton#iAddBtn:hover {{ background: {p.accent}; color: {p.text_inverse}; }}
            QPushButton#iAddBtn:disabled {{ color: {p.success}; border-color: {p.success}; }}
            QPushButton#iFigureBtn {{ background: transparent; color: {p.text_secondary};
                                     border: 1px solid {p.border}; border-radius: 6px;
                                     padding: 3px 10px; font-size: 11px; }}
            QPushButton#iFigureBtn:hover {{ color: {p.accent}; border-color: {p.accent}; }}
            QPushButton#iFigureBtn:disabled {{ color: {p.success}; border-color: {p.success}; }}
            QToolButton#iDetailsBtn {{ background: transparent; color: {p.accent}; border: none;
                                      padding: 0; font-size: 11px; }}
            QToolButton#iDetailsBtn:hover {{ text-decoration: underline; }}
            QPushButton#iNewBar {{ background: {p.accent_soft}; color: {p.accent}; border: none;
                                  border-bottom: 1px solid {p.border_subtle}; padding: 6px 14px;
                                  font-size: 11px; font-weight: 600; text-align: left; }}
            QPushButton#iNewBar:hover {{ background: {p.accent}; color: {p.text_inverse}; }}
            QFrame#iDetails {{ background: {p.bg_primary}; border: 1px solid {p.border_subtle};
                              border-radius: 6px; }}
            QLabel#iDetailKey {{ color: {p.text_muted}; font-size: 10px; }}
            QLabel#iDetailValue {{ color: {p.text_primary}; font-size: 10px; }}
            QLabel#iDetailText {{ color: {p.text_secondary}; font-size: 11px; }}
            QProgressBar#iBar {{ background: {p.bg_primary}; border: none; }}
            QProgressBar#iBar::chunk {{ background: {p.accent}; }}
            QWidget#iCardW {{ background: {p.bg_primary}; }}
            QScrollArea {{ border: none; background: {p.bg_primary}; }}
            QScrollBar:vertical {{ background: transparent; width: 6px; }}
            QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 3px; min-height: 24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        if self._suggestions:
            self._rebuild_cards()

    def _update_types_label(self):
        """Say on the plot types button what is being shown."""
        if self._filter is None:
            text = "Showing: all plot types  ▾"
        else:
            text = f"Showing: {NODE_TYPE_META[self._filter].lower()}  ▾"
        self._types_btn.setText(text)

    def _sync_filter_actions(self):
        """Tick the menu item matching the current filter."""
        self._all_action.setChecked(self._filter is None)
        for key, action in self._type_actions.items():
            action.setChecked(key == self._filter)
        self._update_types_label()

    def current_filter(self) -> str | None:
        """Return the plot type being shown, or ``None`` for all of them."""
        return self._filter

    def _set_filter(self, node_type: str | None):
        """Show one plot type, or all of them.

        The search always covers every plot type, so changing what is shown
        never starts or stops a search.

        Args:
            node_type: The plot type to show, or ``None`` for all.
        """
        self._filter = node_type if node_type in NODE_TYPE_META else None
        _save_filter(self._filter)
        self._sync_filter_actions()
        self._held = False
        self._new_bar.setVisible(False)
        self._render(force=True)

    def _show_only(self, key: str):
        """Show one plot type only.

        Args:
            key: The node type to show.
        """
        self._set_filter(key)

    def _set_status(self, text: str):
        """Show a short progress line under the header, or hide it when empty."""
        self._status.setText(text)
        self._status.setVisible(bool(text))

    def scan(self, force: bool = False):
        """Search for whatever the picked plot types still need.

        Detectors already run against the current scope are not run again, so
        picking another plot type only pays for the detectors it adds. A change
        of loaded samples or replicate groups discards everything found so far.

        Args:
            force: Discard everything found so far and search again.
        """
        scope = resolve_scope(self._scene, self._pw)
        if force or self._scope is None or scope.key != self._scope.key:
            self._stop_worker()
            self._found, self._ran, self._pending = [], set(), set()
        self._scope = scope
        self._update_sample_strip(scope)

        if not scope.sample_names:
            self._stop_worker()
            self._bar.setVisible(False)
            self._set_status("")
            self._count_lbl.setText("")
            self._suggestions = []
            self._update_chip_counts()
            self._clear_cards()
            self._show_empty()
            return

        needed = set(category_keys()) - self._ran
        if not needed or needed <= self._pending:
            self._render()
            return

        self._stop_worker()
        self._pending = needed
        self._bar.setVisible(True)
        self._bar.setRange(0, 0)
        self._refresh_btn.setEnabled(False)
        self._count_lbl.setText("Searching…")
        if not self._found:
            self._clear_cards()
            self._show_placeholder("Searching every sample and element. Findings appear "
                                   "here as each check finishes.")

        particles, sample_idx = gather_scope_data(self._scene, self._pw, scope)
        order = [k for k in category_keys() if k in needed]
        self._worker = _AnalysisWorker(scope, particles, sample_idx,
                                       categories=order, dedupe=False)
        self._worker.progress.connect(self._set_status)
        self._worker.partial.connect(
            lambda found, detector, key=scope.key: self._on_partial(found, detector, key))
        self._worker.results_ready.connect(
            lambda _found, keys=frozenset(needed), key=scope.key: self._on_done(keys, key))
        self._worker.start()

    def refresh(self):
        """Search everything again from scratch."""
        invalidate_context_cache()
        self.scan(force=True)

    def run_category(self, key: str, force: bool = False):
        """Show only the plot types one detector feeds, and search for them.

        Kept for callers of the earlier, category-driven panel.

        Args:
            key: Detector key from :func:`category_keys`.
            force: Search again from scratch.
        """
        analyser = _ANALYSERS.get(key)
        if analyser is None:
            return
        self._set_filter(next(iter(sorted(analyser.node_types)), None))
        self.scan(force=force)

    def _check_scope(self):
        """Search again when the loaded samples or replicate groups have changed."""
        if not self.isVisible():
            return
        scope = resolve_scope(self._scene, self._pw)
        if self._scope is None or scope.key != self._scope.key:
            self.scan()

    def _on_scene_selection(self, *_):
        """Re-check the scope soon after the canvas changes."""
        if self.isVisible():
            QTimer.singleShot(400, self._check_scope)

    def _stop_worker(self):
        """Cancel any in-flight analysis and stop listening to it.

        Disconnecting matters as much as cancelling: a worker that has already
        passed its last abort check will still emit, and without this it would
        deliver results for the previous scope into the current panel.

        A cancelled worker is held in ``_retired`` until its thread actually
        exits, because letting a running ``QThread`` be garbage collected
        crashes the interpreter.
        """
        w = self._worker
        self._pending = set()
        if w is None:
            return
        for signal in (w.progress, w.partial, w.results_ready):
            try:
                signal.disconnect()
            except (RuntimeError, TypeError):
                pass
        self._worker = None
        if w.isRunning():
            w.cancel()
            self._retired.append(w)
            w.finished.connect(lambda: self._retired.remove(w)
                               if w in self._retired else None)

    def _update_sample_strip(self, scope: AnalysisScope | None = None):
        """Describe which samples are searched and how they group into replicates.

        Args:
            scope: Scope to describe. Resolved from the scene when omitted.
        """
        if scope is None:
            scope = resolve_scope(self._scene, self._pw)
        if not scope.sample_names:
            self._sample_lbl.setText("No samples loaded yet.")
            self._group_lbl.setText("")
            self._group_lbl.setVisible(False)
            return
        first, second = describe_scope(scope)
        self._sample_lbl.setText(first)
        self._group_lbl.setText(second)
        self._group_lbl.setVisible(True)

    def _on_partial(self, suggestions: list[Suggestion], detector: str, scope_key: str):
        """Show one detector's findings as soon as it finishes.

        Args:
            suggestions: What the detector found.
            detector: The detector's key.
            scope_key: The scope the search was for. Results for a scope that
                is no longer current are dropped.
        """
        if self._scope is None or scope_key != self._scope.key or detector in self._ran:
            return
        self._found.extend(suggestions)
        self._ran.add(detector)
        self._render(searching=True)

    def _on_done(self, keys=frozenset(), scope_key: str = ""):
        """Finish a search and start another if more plot types were picked meanwhile.

        Args:
            keys: The detectors that ran.
            scope_key: The scope the search was for.
        """
        self._worker = None
        self._pending = set()
        self._bar.setVisible(False)
        self._set_status("")
        self._refresh_btn.setEnabled(True)
        if self._scope is None or (scope_key and scope_key != self._scope.key):
            return
        self._ran |= set(keys)
        self._render()
        if set(category_keys()) - self._ran:
            self.scan()

    def visible_suggestions(self) -> list[Suggestion]:
        """Return the cards for the picked plot types, ranked and de-duplicated."""
        if self._filter is None:
            return _dedupe_suggestions(self._found)
        wanted = [s for s in self._found if s.node_type == self._filter]
        return _dedupe_suggestions(wanted, FOCUSED_CARD_LIMIT)

    def _update_chip_counts(self):
        """Write how many findings each plot type has into the menu.

        Once the search is over, plot types with nothing to show are greyed
        out, so picking one never leads to an empty list.
        """
        finished = self._worker is None and self._scope is not None and bool(self._ran)
        total = len(_dedupe_suggestions(self._found))
        self._all_action.setText(f"All plot types  ({total})" if self._ran else "All plot types")
        for key, action in self._type_actions.items():
            label = NODE_TYPE_META[key]
            searched = set(analysers_for({key})) <= self._ran and self._scope is not None
            if not searched:
                action.setText(label)
                action.setEnabled(True)
                continue
            count = len(_dedupe_suggestions(
                [s for s in self._found if s.node_type == key], FOCUSED_CARD_LIMIT))
            action.setText(f"{label}  ({count})" if count else f"{label}  (none)")
            action.setEnabled(bool(count) or not finished or key == self._filter)

    def _render(self, searching: bool = False, force: bool = False):
        """Show the findings for the current filter, under their section headings.

        While a search is still delivering findings and the pointer is over
        the list, new findings are held back behind a bar instead of moving
        the cards the user is about to click.

        Args:
            searching: Whether detectors are still running.
            force: Redraw now even if the pointer is over the list.
        """
        self._suggestions = self.visible_suggestions()
        self._update_chip_counts()
        n = len(self._suggestions)
        busy = searching or self._worker is not None
        if busy:
            self._count_lbl.setText(f"Searching… {n} finding{'s' if n != 1 else ''} so far")
        else:
            self._count_lbl.setText(f"{n} finding{'s' if n != 1 else ''}" if n
                                    else "No findings")
        if not force and self._cards and self._pointer_over_list():
            shown = set(self._cards)
            new = sum(1 for s in self._suggestions if card_key(s) not in shown)
            if new:
                self._held = True
                self._new_bar.setText(f"Show {new} new finding{'s' if new != 1 else ''}")
                self._new_bar.setVisible(True)
                return
        self._apply_render(busy)

    def _apply_render(self, busy: bool = False):
        """Lay out the current findings, keeping cards that are already shown."""
        self._held = False
        self._new_bar.setVisible(False)
        if self._suggestions:
            self._rebuild_cards()
        else:
            self._clear_cards()
            if not busy:
                self._show_empty()
            else:
                self._show_placeholder("Searching every sample and element. Findings appear "
                                       "here as each check finishes.")

    def _release_held(self):
        """Show findings that were held back while the pointer was over the list."""
        self._apply_render(self._worker is not None)

    def _pointer_over_list(self) -> bool:
        """Whether the mouse is over the list of findings."""
        try:
            return self._scroll.viewport().underMouse()
        except RuntimeError:
            return False

    def eventFilter(self, watched, event):
        """Show held-back findings once the pointer leaves the list."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Leave and self._held:
            QTimer.singleShot(150, lambda: self._held and not self._pointer_over_list()
                              and self._release_held())
        return super().eventFilter(watched, event)

    def _rebuild_cards(self):
        """Lay out section headings and cards, reusing the cards already on screen.

        A reused card keeps its open details and its place under the pointer;
        only headings are recreated, and cards for findings that are no longer
        shown are deleted.
        """
        wanted = {card_key(s): s for s in self._suggestions}
        while self._card_layout.count() > 1:
            item = self._card_layout.takeAt(0)
            widget = item.widget()
            if widget is None:
                continue
            if (isinstance(widget, _Card) and card_key(widget._s) in wanted
                    and self._cards.get(card_key(widget._s)) is widget):
                continue
            if isinstance(widget, _Card) and self._cards.get(card_key(widget._s)) is widget:
                self._cards.pop(card_key(widget._s))
            _discard(widget)
        by_section: dict[str, list[Suggestion]] = {}
        placed: set = set()
        for s in self._suggestions:
            if card_key(s) in placed:
                continue
            placed.add(card_key(s))
            by_section.setdefault(section_of(s.category), []).append(s)
        for title, _cats in SECTIONS:
            items = by_section.get(title)
            if not items:
                continue
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            heading = QLabel(title)
            heading.setObjectName("iSection")
            count = QLabel(str(len(items)))
            count.setObjectName("iSectionCount")
            row.addWidget(heading)
            row.addStretch()
            row.addWidget(count)
            holder = QWidget()
            holder.setObjectName("iSectionRow")
            holder.setLayout(row)
            self._card_layout.insertWidget(self._card_layout.count() - 1, holder)
            for s in items:
                key = card_key(s)
                card = self._cards.get(key)
                if card is None:
                    has_figure = ((s.explain_key or s.category) in _figures.DESIGNS
                                  or s.category in _figures.DESIGNS)
                    card = _Card(s, on_add=self._add_suggestion,
                                 samples_text=describe_samples(s, self._scope),
                                 on_figure=self._add_figure if has_figure else None,
                                 on_cluster=self._add_clustering)
                    self._cards[key] = card
                self._card_layout.insertWidget(self._card_layout.count() - 1, card)
                card.setVisible(True)
        for key in [k for k in self._cards if k not in wanted]:
            _discard(self._cards.pop(key))

    def _empty_message(self) -> str:
        """Explain why there are no cards, and what to do about it.

        Returns:
            A short message for the empty list.
        """
        scope = self._scope
        if scope is None or not scope.sample_names:
            return ("Load a sample to start. Insights searches every sample and element on "
                    "its own.")
        if scope.total_particles < 5:
            return f"Only {scope.total_particles} particles are loaded, too few to search."
        if self._filter is not None:
            return (f"Nothing to show as a {NODE_TYPE_META[self._filter].lower()} plot. "
                    "Choose All plot types to see every finding.")
        return "Nothing stands out yet. Load more samples to compare."

    def _show_empty(self):
        """Show the empty-state message in place of the cards."""
        self._show_placeholder(self._empty_message())

    def _show_placeholder(self, text: str):
        """Put a short message where the cards would go.

        Args:
            text: Message to display.
        """
        lbl = QLabel(text)
        lbl.setObjectName("iPlaceholder")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        self._card_layout.insertWidget(self._card_layout.count() - 1, lbl)

    def _clear_cards(self):
        """Remove every card and heading, leaving the trailing stretch in place."""
        self._cards.clear()
        while self._card_layout.count() > 1:
            item = self._card_layout.takeAt(0)
            if item.widget():
                _discard(item.widget())

    def _add_figure(self, s: Suggestion):
        """Add the figure that walks through a finding, panels a to f with a legend.

        The figure is a Figure Builder node behind a selector holding the
        finding's samples with every element kept, because several panels
        compare particles with and without an element.

        Args:
            s: The finding.
        """
        units = selection_units(s, self._scope)
        samples = [m for _label, members in units for m in members]
        pool = _raw_pool_for(self._scene, self._pw)
        particles = [p for name in samples for p in pool.get(name, ())]
        labels = list(s.elements)
        for panel in (s.config or {}).get("panels") or []:
            for label in (panel.get("types") or {}).get("elements") or ():
                if label not in labels:
                    labels.append(label)
        ctx = _figures.context_from(
            particles, labels,
            detection_limits(self._pw, samples, labels),
            multi_sample=len(units) > 1, groups=len(units))
        spec = _figures.figure_for(s, ctx)
        if spec is None:
            self._flash_status("No figure is available for this finding")
            return
        self._add_suggestion(s, node_type="figure_builder", config=spec, narrow_elements=False)

    def _add_clustering(self, s: Suggestion):
        """Add a Clustering node over a particle-type finding's samples and elements.

        The node starts with its own default settings; Insights' types are
        shown in the card's figures, while the Clustering node is for
        exploring them with other methods and parameters.

        Args:
            s: A particle-type finding.
        """
        self._add_suggestion(s, node_type="clustering_plot", config={})

    def _add_suggestion(self, s: Suggestion, node_type: str | None = None,
                        config: dict | None = None, narrow_elements: bool = True):
        """Build the branch a suggestion describes and wire it into the canvas.

        A fresh sample selector is created holding only the samples where the
        finding held, and, when the finding names elements, only those
        elements. One sample gets a single selector; one replicate group gets a
        single selector summing its replicates; anything wider gets a
        multi-sample selector with replicates pooled into their groups. The
        plot node hangs off that selector, so the new branch shows exactly what
        the card describes.

        Args:
            s: The suggestion whose Add button was pressed.
            node_type: Node to add instead of the suggestion's own.
            config: Settings for that node instead of the suggestion's.
            narrow_elements: Keep only the finding's elements in the selector.
        """
        node_type = node_type or s.node_type
        config = s.config if config is None else config
        try:
            from widget.canvas_widgets import _NODE_FACTORIES
        except ImportError:
            _itk_log.exception("[Insights] Could not import _NODE_FACTORIES")
            self._flash_status("Could not reach the node factory")
            return

        factory = _NODE_FACTORIES.get(node_type)
        if factory is None:
            _itk_log.error(f"[Insights] Unknown node_type: {node_type}")
            self._flash_status(f"No node type '{node_type}'")
            return

        scene = self._scene
        plot_node = factory(self._pw)
        if config and isinstance(getattr(plot_node, "config", None), dict):
            plot_node.config.update(copy.deepcopy(config))

        selector = self._build_scoped_selector(s, _NODE_FACTORIES, narrow_elements)
        source = selector or _find_source_node(scene)

        anchor = QPointF(300, 200)
        if source is not None:
            item = scene.node_items.get(source)
            if item is not None:
                anchor = QPointF(item.pos().x() + _NODE_SLOT_W,
                                 item.pos().y())

        if selector is not None:
            base = _free_position(scene, anchor)
            scene.add_node(selector, base)
            upstream = _find_batch_node(scene)
            if upstream is not None:
                scene.add_link(upstream, "output", selector, "input")
            anchor = QPointF(base.x() + _NODE_SLOT_W, base.y())

        scene.add_node(plot_node, _free_position(scene, anchor))
        if source is not None and getattr(source, "_has_output", False):
            scene.add_link(source, "output", plot_node, "input")

        if selector is not None:
            units = selection_units(s, self._scope)
            self._flash_status(
                f"Added selector ({len(units)} sample group{'s' if len(units) != 1 else ''}"
                + (f", {len(s.elements)} element{'s' if len(s.elements) != 1 else ''}"
                   if s.elements else "") + ") + plot"
            )

    def _build_scoped_selector(self, s: Suggestion, factories: dict,
                               narrow_elements: bool = True):
        """Create a sample selector holding only what the finding is about.

        Args:
            s: The suggestion being added.
            factories: The canvas node factory mapping.
            narrow_elements: Keep only the finding's elements; when false the
                selector keeps every element of the finding's samples.

        Returns:
            The configured selector node, or ``None`` when there is no scope or
            the selector type is unavailable.
        """
        units = selection_units(s, self._scope)
        if not units:
            return None

        entries = []
        if s.elements and narrow_elements:
            entries = _isotope_entries(self._pw, self._scene, s.elements)
            if not entries:
                _itk_log.warning(
                    f"[Insights] could not resolve isotopes for {list(s.elements)}; "
                    "the selector keeps every element"
                )
                self._flash_status("Could not narrow the elements, so the selector keeps all of them")

        single = len(units) == 1
        node_type = "sample_selector" if single else "multiple_sample_selector"
        factory = factories.get(node_type)
        if factory is None:
            return None

        selector = factory(self._pw)
        selector.selected_isotopes = entries

        if single:
            label, members = units[0]
            selector.selected_sample = members[0]
            if len(members) > 1:
                selector.sum_replicates = True
                selector.replicate_samples = list(members)
        else:
            samples = [m for _label, members in units for m in members]
            selector.selected_samples = samples
            selector.sample_config = {
                m: {"included": True,
                    "sum_group": label if len(members) > 1 else "",
                    "custom_name": m}
                for label, members in units for m in members
            }

        title = getattr(selector, "title", None)
        if isinstance(title, str):
            where = units[0][0] if single else f"{len(units)} groups"
            what = (", ".join(s.elements[:3]) if s.elements and narrow_elements
                    else "all elements")
            selector.title = f"{where}: {what}"
        return selector

    def _flash_status(self, message: str, msec: int = 2600):
        """Show a transient message in the status line.

        Args:
            message: Text to show.
            msec: How long to leave it up.
        """
        self._set_status(message)
        QTimer.singleShot(msec, lambda: (
            self._set_status("") if self._status.text() == message else None
        ))

    def showEvent(self, event):
        """Start searching as soon as the panel is shown."""
        super().showEvent(event)
        self._poll.start()
        QTimer.singleShot(0, self.scan)

    def hideEvent(self, event):
        """Stop watching for data changes while hidden."""
        self._poll.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        """Release resources if the panel is ever closed directly."""
        self._teardown()
        super().closeEvent(event)

    def _teardown(self):
        """Drop the theme subscription and stop any running analysis.

        Safe to call more than once, since it may arrive from either the panel
        closing or the parent dialog finishing.
        """
        if getattr(self, "_torn_down", False):
            return
        self._torn_down = True
        self._poll.stop()
        try:
            self._theme_dc()
        except Exception:
            _itk_log.exception("[Insights] theme disconnect failed")
        self._stop_worker()


# ──────────────────────────────────────────────────────────────────────────────
# Integration helpers — call from CanvasResultsDialog._build()
# ──────────────────────────────────────────────────────────────────────────────

def integrate_insights_panel(canvas_dialog, splitter: QSplitter) -> SmartInsightsPanel:
    """Append a :class:`SmartInsightsPanel` as the rightmost pane of *splitter*.

    The panel starts hidden. Teardown is hung off the dialog's ``finished``
    signal, because a widget inside a splitter never receives ``closeEvent``
    and the theme subscription would otherwise outlive the panel.

    Call from ``CanvasResultsDialog._build()`` after the splitter has its
    palette and canvas panes::

        self.insights_panel = integrate_insights_panel(self, splitter)
        splitter.setSizes([240, 820, 0])

        self._insights_btn = make_insights_toggle_button(self, splitter)
        hl.addWidget(self._insights_btn)

    Args:
        canvas_dialog: The dialog owning the canvas and splitter.
        splitter: Splitter to append the panel to.

    Returns:
        The panel, also assign it to ``canvas_dialog.insights_panel`` so the
        toggle button can find it.
    """
    panel = SmartInsightsPanel(
        scene=canvas_dialog.canvas.scene,
        parent_window=canvas_dialog.parent,
        parent=canvas_dialog,
    )
    panel.setVisible(False)
    splitter.addWidget(panel)
    splitter.setCollapsible(splitter.indexOf(panel), False)

    if hasattr(canvas_dialog, "finished"):
        canvas_dialog.finished.connect(lambda *_: panel._teardown())
    return panel


def make_insights_toggle_button(canvas_dialog, splitter: QSplitter) -> QPushButton:
    """Create the header button that shows and hides the insights panel.

    The button label reflects the current state, and the panel's last width is
    remembered so reopening restores it rather than snapping to a default.

    Args:
        canvas_dialog: The dialog holding ``insights_panel``.
        splitter: The splitter the panel lives in.

    Returns:
        The toggle button, ready to add to the header layout.
    """

    def _toggle():
        """Show or hide the panel, resizing the splitter to match."""
        panel = canvas_dialog.insights_panel
        if panel.isVisible():
            width = splitter.sizes()[-1]
            if width >= panel.MIN_WIDTH:
                canvas_dialog._insights_prev_w = width
            panel.setVisible(False)
            btn.setText("✦  Insights")
            btn.setToolTip("Open Insights")
        else:
            panel.setVisible(True)
            _open_sizes()
            QTimer.singleShot(0, _open_sizes)
            btn.setText("✦  Insights  ‹")
            btn.setToolTip("Close Insights")

    def _open_sizes():
        """Give the open panel a usable width, taken from the canvas.

        The remembered width is used when there is one, never less than the
        panel's minimum, and the canvas keeps at least
        :attr:`SmartInsightsPanel.MIN_CANVAS` pixels. Run once straight away
        and once after Qt has laid out the newly shown panel, because the
        splitter can otherwise squeeze it back to a sliver.
        """
        panel = canvas_dialog.insights_panel
        if not panel.isVisible():
            return
        sizes = splitter.sizes()
        total = sum(sizes) or splitter.width()
        fixed = sum(sizes[:-2])
        room = max(0, total - fixed - panel.MIN_CANVAS)
        wanted = max(panel.MIN_WIDTH,
                     getattr(canvas_dialog, "_insights_prev_w", 0) or panel.DEFAULT_WIDTH)
        width = max(panel.MIN_WIDTH, min(wanted, room)) if room else panel.MIN_WIDTH
        if abs(sizes[-1] - width) <= 2:
            return
        new_sizes = list(sizes)
        new_sizes[-1] = width
        new_sizes[-2] = max(1, total - fixed - width)
        splitter.setSizes(new_sizes)

    def _style():
        """Apply the current theme palette to the button."""
        p = _theme.palette
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {p.accent_soft}; color: {p.accent};
                border: 1px solid {p.accent}; border-radius: 6px;
                padding: 0 14px; font-size: 11px; font-weight: 700;
                font-family: '{_FONT}';
            }}
            QPushButton:hover {{
                background: {p.accent_hover}; color: {p.text_inverse};
            }}
            QPushButton:pressed {{
                background: {p.accent_pressed}; color: {p.text_inverse};
            }}
        """)

    btn = QPushButton("✦  Insights")
    btn.setFixedHeight(30)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setToolTip("Open Insights")
    _style()
    _theme.connect_theme(lambda _: _style())
    btn.clicked.connect(_toggle)
    return btn