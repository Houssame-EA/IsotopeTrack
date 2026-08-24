"""Interactive user-guide framework.

Renders annotated screenshots of IsotopeTrack windows. Every functional
region of a screenshot is a clickable hotspot: hovering highlights it,
clicking shows a detailed explanation section below the image.

Page content (images, hotspot rectangles, and explanation HTML) lives in
tools/guide_content.py. This module only provides the widgets.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame,
    QTabWidget, QPushButton, QToolTip,
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QFont

from pathlib import Path
import sys

from tools.theme import theme
import logging
_itk_log = logging.getLogger("IsotopeTrack.tools.interactive_guide")


def get_resource_path(relative_path):
    """Resolve a resource path relative to the app bundle or source root.

    Args:
        relative_path (str | Path): Path relative to the application root.

    Returns:
        Path: Absolute path to the resource.
    """
    base_path = getattr(sys, "_MEIPASS", None)
    if base_path is None:
        base_path = Path(__file__).parent.parent
    return Path(base_path) / relative_path


class HotspotImage(QWidget):
    """Paint a screenshot scaled to the widget width and overlay
    clickable, hover-highlighted hotspot regions."""

    hotspotClicked = Signal(str)

    def __init__(self, image_path, hotspots, parent=None):
        """Initialise the widget with an image and its hotspot list.

        Args:
            image_path (str | Path): Absolute path to the screenshot.
            hotspots (list[dict]): Hotspot dicts with 'id', 'title',
                'rect' (x, y, w, h normalised to 0..1) and 'body' HTML.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self._pixmap = QPixmap(str(image_path))
        self._image_name = Path(str(image_path)).name
        self._hotspots = hotspots
        self._hover_id = None
        self._selected_id = None
        self.setMouseTracking(True)
        self.setMinimumWidth(360)

    def _aspect(self):
        """Return the height/width ratio of the loaded screenshot.

        Returns:
            float: Aspect ratio, with a fallback for missing images.
        """
        if self._pixmap.isNull() or self._pixmap.width() == 0:
            return 0.6
        return self._pixmap.height() / self._pixmap.width()

    def resizeEvent(self, event):
        """Keep the widget height locked to the image aspect ratio.

        Args:
            event (QResizeEvent): Resize event from Qt.
        """
        self.setFixedHeight(int(self.width() * self._aspect()))
        super().resizeEvent(event)

    def sizeHint(self):
        """Return the preferred size of the widget.

        Returns:
            QSize: Preferred size derived from the image aspect ratio.
        """
        return QSize(860, int(860 * self._aspect()))

    def _hotspot_rect(self, spot):
        """Map a hotspot's normalised rect to widget coordinates.

        Args:
            spot (dict): Hotspot definition.

        Returns:
            QRectF: Rectangle in widget pixel coordinates.
        """
        x, y, w, h = spot["rect"]
        return QRectF(x * self.width(), y * self.height(),
                      w * self.width(), h * self.height())

    def _spot_at(self, pos):
        """Return the hotspot under a mouse position, if any.

        Args:
            pos (QPointF): Position in widget coordinates.

        Returns:
            dict | None: Hotspot definition or None.
        """
        pt = QPointF(pos)
        for spot in self._hotspots:
            if self._hotspot_rect(spot).contains(pt):
                return spot
        return None

    def mouseMoveEvent(self, event):
        """Track hover state and switch the cursor over hotspots.

        Args:
            event (QMouseEvent): Mouse move event.
        """
        spot = self._spot_at(event.position())
        new_id = spot["id"] if spot else None
        if new_id != self._hover_id:
            self._hover_id = new_id
            self.setCursor(Qt.PointingHandCursor if spot else Qt.ArrowCursor)
            if spot:
                QToolTip.showText(
                    event.globalPosition().toPoint(), spot["title"], self)
            else:
                QToolTip.hideText()
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        """Clear the hover highlight when the mouse leaves the image.

        Args:
            event (QEvent): Leave event.
        """
        if self._hover_id is not None:
            self._hover_id = None
            self.setCursor(Qt.ArrowCursor)
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Emit hotspotClicked when a hotspot is left-clicked.

        Args:
            event (QMouseEvent): Mouse press event.
        """
        if event.button() == Qt.LeftButton:
            spot = self._spot_at(event.position())
            if spot:
                self._selected_id = spot["id"]
                self.update()
                self.hotspotClicked.emit(spot["id"])
        super().mousePressEvent(event)

    def set_selected(self, spot_id):
        """Mark a hotspot as the current selection and repaint.

        Args:
            spot_id (str | None): Hotspot id to select.
        """
        self._selected_id = spot_id
        self.update()

    def paintEvent(self, event):
        """Draw the screenshot and the hotspot overlays.

        Args:
            event (QPaintEvent): Paint event.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._pixmap.isNull():
            painter.setPen(QColor(theme.palette.text_muted))
            painter.drawText(self.rect(), Qt.AlignCenter,
                             f"Screenshot not found: images/{self._image_name}")
            return
        painter.drawPixmap(self.rect(), self._pixmap)
        accent = QColor(theme.palette.accent)
        for spot in self._hotspots:
            rect = self._hotspot_rect(spot)
            hovered = spot["id"] == self._hover_id
            selected = spot["id"] == self._selected_id
            if hovered or selected:
                fill = QColor(accent)
                fill.setAlpha(60 if hovered else 40)
                painter.setBrush(fill)
                pen = QPen(accent, 2.5 if selected else 2.0)
            else:
                painter.setBrush(Qt.NoBrush)
                outline = QColor(accent)
                outline.setAlpha(110)
                pen = QPen(outline, 1.2, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRoundedRect(rect, 4, 4)
        self._paint_badges(painter, accent)

    def _paint_badges(self, painter, accent):
        """Draw a numbered circle badge on each hotspot.

        Args:
            painter (QPainter): Active painter for this paint event.
            accent (QColor): Accent color of the current theme.
        """
        badge_font = QFont(painter.font())
        badge_font.setPointSize(8)
        badge_font.setBold(True)
        painter.setFont(badge_font)
        diameter = 18.0
        for index, spot in enumerate(self._hotspots, start=1):
            rect = self._hotspot_rect(spot)
            cx = min(max(rect.left() + 1, 0), self.width() - diameter - 1)
            cy = min(max(rect.top() + 1, 0), self.height() - diameter - 1)
            badge = QRectF(cx, cy, diameter, diameter)
            fill = QColor(accent)
            fill.setAlpha(235)
            painter.setBrush(fill)
            painter.setPen(QPen(QColor("#ffffff"), 1.0))
            painter.drawEllipse(badge)
            painter.drawText(badge, Qt.AlignCenter, str(index))


class InteractiveImagePage(QWidget):
    """Scrollable page: intro text, interactive screenshot, and a
    detailed explanation section below the image."""

    def __init__(self, page, parent=None):
        """Build the page from its content definition.

        Args:
            page (dict): Page definition with 'title', 'image', 'intro'
                and 'hotspots' keys (see tools/guide_content.py).
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self._page = page
        self._spots_by_id = {s["id"]: s for s in page["hotspots"]}
        self._current_index = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.viewport().setAutoFillBackground(False)

        content = QWidget()
        content.setObjectName("tutorialContent")
        content.setAutoFillBackground(True)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(20, 16, 20, 24)
        lay.setSpacing(12)

        intro_html = (
            f"<h2>{page['title']}</h2>"
            f"{page.get('intro', '')}"
            "<p><b>Click any outlined region</b> of the screenshot below "
            "for a detailed explanation.</p>"
        )
        self._intro = QLabel(intro_html)
        self._intro.setWordWrap(True)
        self._intro.setTextFormat(Qt.RichText)
        self._intro.setOpenExternalLinks(True)
        lay.addWidget(self._intro)

        self._image = HotspotImage(
            get_resource_path(f"images/{page['image']}"), page["hotspots"])
        self._image.hotspotClicked.connect(self._show_detail)
        lay.addWidget(self._image)

        self._detail_frame = QFrame()
        self._detail_frame.setObjectName("guideDetailFrame")
        detail_lay = QVBoxLayout(self._detail_frame)
        detail_lay.setContentsMargins(16, 12, 16, 14)

        nav = QHBoxLayout()
        nav.setSpacing(6)
        self._nav_counter = QLabel("")
        self._btn_prev = QPushButton("◀")
        self._btn_next = QPushButton("▶")
        for btn in (self._btn_prev, self._btn_next):
            btn.setFixedSize(30, 24)
            btn.setCursor(Qt.PointingHandCursor)
        self._btn_prev.setToolTip("Previous region")
        self._btn_next.setToolTip("Next region")
        self._btn_prev.clicked.connect(lambda: self._step(-1))
        self._btn_next.clicked.connect(lambda: self._step(1))
        nav.addStretch()
        nav.addWidget(self._nav_counter)
        nav.addWidget(self._btn_prev)
        nav.addWidget(self._btn_next)
        detail_lay.addLayout(nav)

        self._detail = QLabel()
        self._detail.setWordWrap(True)
        self._detail.setTextFormat(Qt.RichText)
        self._detail.setOpenExternalLinks(True)
        self._detail.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        detail_lay.addWidget(self._detail)

        lay.addWidget(self._detail_frame)
        lay.addStretch()

        self._scroll.setWidget(content)
        outer.addWidget(self._scroll)

        self._show_overview()
        self.apply_theme()
        theme.themeChanged.connect(self.apply_theme)

    def _show_overview(self):
        """Show the default detail text listing all clickable regions."""
        items = "".join(
            f"<li><b>{s['title']}</b></li>" for s in self._page["hotspots"])
        self._detail.setText(
            "<h3>Regions in this window</h3>"
            "<p>Click a numbered region in the screenshot above, or use the "
            "◀ ▶ buttons to step through them in order:</p>"
            f"<ol>{items}</ol>"
        )
        self._nav_counter.setText("")

    def _show_detail(self, spot_id):
        """Display the explanation for the clicked hotspot.

        Args:
            spot_id (str): Id of the clicked hotspot.
        """
        spot = self._spots_by_id.get(spot_id)
        if not spot:
            return
        spots = self._page["hotspots"]
        index = next(
            (i for i, s in enumerate(spots) if s["id"] == spot_id), 0)
        self._current_index = index
        self._nav_counter.setText(f"{index + 1} / {len(spots)}")
        self._detail.setText(
            f"<h3>{index + 1} · {spot['title']}</h3>{spot['body']}")
        self._image.set_selected(spot_id)
        self._scroll.ensureWidgetVisible(self._detail_frame, 0, 40)

    def show_hotspot(self, spot_id):
        """Publicly select a hotspot and show its explanation.

        Args:
            spot_id (str): Id of the hotspot to show.
        """
        self._show_detail(spot_id)

    def _step(self, delta):
        """Step to the previous or next hotspot on this page.

        Args:
            delta (int): -1 for previous, +1 for next.
        """
        spots = self._page["hotspots"]
        if not spots:
            return
        current = getattr(self, "_current_index", None)
        if current is None:
            index = 0 if delta > 0 else len(spots) - 1
        else:
            index = (current + delta) % len(spots)
        self._show_detail(spots[index]["id"])

    def apply_theme(self):
        """Apply the currently active theme palette to the page."""
        p = theme.palette
        self._detail_frame.setStyleSheet(f"""
            QFrame#guideDetailFrame {{
                background-color: {p.bg_tertiary};
                border: 1px solid {p.border};
                border-left: 4px solid {p.accent};
                border-radius: 6px;
            }}
        """)
        for lbl in (self._intro, self._detail):
            lbl.setStyleSheet(
                f"font-size:13px; line-height:1.5; "
                f"color:{p.text_primary}; background:transparent;")
        self._nav_counter.setStyleSheet(
            f"font-size:11px; color:{p.text_muted}; background:transparent;")
        self._image.update()


def build_section_widget(section, parent=None):
    """Build the widget for one guide section.

    A section with a single page returns that page directly; a section
    with several pages returns an inner tab widget with one tab per page.

    Args:
        section (dict): Section definition with 'title' and 'pages'.
        parent (QWidget | None): Parent widget.

    Returns:
        QWidget: The section widget to place in the user-guide dialog.
    """
    pages = section["pages"]
    if len(pages) == 1:
        return InteractiveImagePage(pages[0], parent)
    tabs = QTabWidget(parent)
    tabs.setUsesScrollButtons(True)
    for page in pages:
        tabs.addTab(InteractiveImagePage(page, tabs), page["title"])
    return tabs
