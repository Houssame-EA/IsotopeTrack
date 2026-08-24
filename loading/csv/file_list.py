"""Sliding file browser for the import dialog.

The files are shown one at a time as a card that slides sideways, the way a
gallery pages through images, rather than as a scrolling list. Each card
carries a miniature of that file's own first rows, drawn as bars the way a
document viewer renders page text, so a two-column rinse and a six-column run
are told apart at a glance without reading anything.

One card at a time earns the space: the panel is narrow, and a list of the same
width could only afford a thumbnail the size of a postage stamp. Sliding still
keeps the neighbours in view at the edges, so a file never looks like the only
one in the batch.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import (
    Property, QEasingCurve, QPropertyAnimation, QRectF, Qt, Signal,
)
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import QLabel, QSizePolicy, QToolTip, QVBoxLayout, QWidget

from tools.theme import theme

_itk_log = logging.getLogger("IsotopeTrack.loading.csv.file_list")

THUMB_COLUMNS = 10
THUMB_ROWS = 10

CARD_GAP = 16.0
CARD_MAX_W = 260.0
SIDE_MARGIN = 26.0
FOOTER_H = 26.0
NEIGHBOUR_REACH = 1.8


class FileEntry:
    """Display state and thumbnail content for one file in the slider."""

    def __init__(self, path: str):
        """Derive the entry's labels from a file path.

        Args:
            path (str): Path of the file this entry represents.
        """
        self.path = str(path)
        self.name = Path(path).name
        suffix = Path(path).suffix.lower().lstrip('.')
        self.kind = suffix.upper() if suffix else "FILE"
        self.subtitle = ""
        self.badge = ""
        self.ready = False
        self.failed = False
        self.header: list[str] = []
        self.cells: list[list[str]] = []
        self.removed_columns: set[int] = set()

    def set_thumbnail(self, columns, rows) -> None:
        """Store the corner of the file the card should show.

        The values are kept as text rather than reduced to bars: a card that
        shows real numbers tells you whether you are looking at the right file,
        which is the whole point of having it there.

        Args:
            columns: Iterable of column names.
            rows: Iterable of row sequences holding the first cell values.
        """
        self.header = [self._text(c) for c in list(columns)[:THUMB_COLUMNS]]
        self.cells = []
        for row in list(rows)[:THUMB_ROWS]:
            values = list(row)[:THUMB_COLUMNS]
            self.cells.append([self._text(v) for v in values])

    @staticmethod
    def _text(value) -> str:
        """Return a short display string for one cell of the card.

        Args:
            value: Raw cell or header value.

        Returns:
            str: Text trimmed of the noise a float repr brings with it.
        """
        if value is None:
            return ""
        if isinstance(value, float):
            if value != value:
                return ""
            if value == int(value) and abs(value) < 1e12:
                return str(int(value))
            return f"{value:.4g}"
        text = str(value).strip()
        return "" if text.lower() == "nan" else text


class FileSlider(QWidget):
    """Painted deck of file cards that slides one file at a time.

    Signals:
        currentChanged: Emitted with the new index when the selection moves.
    """

    currentChanged = Signal(int)

    def __init__(self, parent=None):
        """Build an empty slider."""
        super().__init__(parent)
        self._entries: list[FileEntry] = []
        self._current = -1
        self._position = 0.0
        self._hover = -1
        self._card_rects: list[tuple[int, QRectF]] = []
        self._prev_rect = QRectF()
        self._next_rect = QRectF()

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)

        self._slide = QPropertyAnimation(self, b"position", self)
        self._slide.setDuration(300)
        self._slide.setEasingCurve(QEasingCurve.OutCubic)

        theme.themeChanged.connect(self._on_theme_changed)

    def cleanup(self) -> None:
        """Disconnect the theme signal so the widget can be collected."""
        try:
            theme.themeChanged.disconnect(self._on_theme_changed)
        except (RuntimeError, TypeError):
            _itk_log.debug("Slider theme signal already disconnected")

    def set_entries(self, entries) -> None:
        """Replace the deck.

        Args:
            entries: The ``FileEntry`` objects to show.
        """
        self._entries = list(entries)
        self._current = 0 if self._entries else -1
        self._position = float(max(0, self._current))
        self.update()

    def current_index(self) -> int:
        """Return the index of the file on show."""
        return self._current

    def set_current(self, index: int, animate: bool = True) -> None:
        """Slide to one file.

        Args:
            index (int): Position in the deck.
            animate (bool): False to jump without the slide.
        """
        if not (0 <= index < len(self._entries)) or index == self._current:
            return
        self._current = index
        self._slide.stop()
        if animate:
            self._slide.setStartValue(self._position)
            self._slide.setEndValue(float(index))
            self._slide.start()
        else:
            self._position = float(index)
            self.update()
        self.currentChanged.emit(index)

    def step(self, delta: int) -> None:
        """Move a number of files forward or back.

        Args:
            delta (int): How far to move, negative for back.
        """
        if not self._entries:
            return
        self.set_current(
            max(0, min(len(self._entries) - 1, self._current + delta)))

    def _get_position(self) -> float:
        """Return the animated deck position in card units."""
        return self._position

    def _set_position(self, value: float) -> None:
        """Set the animated deck position and repaint.

        Args:
            value (float): Fractional index of the card at the front.
        """
        self._position = float(value)
        self.update()

    position = Property(float, _get_position, _set_position)

    def mousePressEvent(self, event):
        """Page on an arrow, or slide to a card that was clicked.

        Args:
            event: Qt mouse event.
        """
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return
        point = event.position()
        if self._prev_rect.contains(point):
            self.step(-1)
        elif self._next_rect.contains(point):
            self.step(1)
        else:
            for index, rect in self._card_rects:
                if rect.contains(point) and index != self._current:
                    self.set_current(index)
                    break
        event.accept()

    def mouseMoveEvent(self, event):
        """Track what is under the pointer and show that file's detail.

        Args:
            event: Qt mouse event.
        """
        point = event.position()
        hover = -1
        if self._prev_rect.contains(point):
            hover = -2
        elif self._next_rect.contains(point):
            hover = -3
        else:
            for index, rect in self._card_rects:
                if rect.contains(point):
                    hover = index
                    break
        if hover != self._hover:
            self._hover = hover
            self.update()
        if hover >= 0:
            entry = self._entries[hover]
            detail = entry.subtitle or entry.path
            QToolTip.showText(event.globalPosition().toPoint(),
                              f"{entry.name}\n{detail}", self)
        event.accept()

    def leaveEvent(self, event):
        """Clear the hover highlight when the pointer leaves.

        Args:
            event: Qt leave event.
        """
        if self._hover != -1:
            self._hover = -1
            self.update()
        super().leaveEvent(event)

    def wheelEvent(self, event):
        """Page through the files with the wheel.

        Args:
            event: Qt wheel event.
        """
        delta = event.angleDelta().y() or event.angleDelta().x()
        if delta:
            self.step(-1 if delta > 0 else 1)
            event.accept()

    def keyPressEvent(self, event):
        """Page through the files with the arrow, home and end keys.

        Args:
            event: Qt key event.
        """
        if not self._entries:
            super().keyPressEvent(event)
            return
        if event.key() in (Qt.Key_Left, Qt.Key_Up):
            self.step(-1)
        elif event.key() in (Qt.Key_Right, Qt.Key_Down):
            self.step(1)
        elif event.key() == Qt.Key_Home:
            self.set_current(0)
        elif event.key() == Qt.Key_End:
            self.set_current(len(self._entries) - 1)
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def _on_theme_changed(self, *_):
        """Repaint after a palette change."""
        self.update()

    def _card_size(self) -> tuple[float, float]:
        """Return the width and height one card should be drawn at."""
        width = min(CARD_MAX_W, max(120.0, self.width() - SIDE_MARGIN * 2))
        height = max(90.0, self.height() - FOOTER_H - 8)
        return width, height

    def paintEvent(self, event):
        """Draw the neighbours, then the current card, then the chrome.

        Args:
            event: Qt paint event.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        self._card_rects.clear()

        p = theme.palette
        if not self._entries:
            painter.setPen(QPen(QColor(p.text_muted)))
            painter.drawText(self.rect(), Qt.AlignCenter, "No files selected")
            painter.end()
            return

        card_w, card_h = self._card_size()
        centre_x = self.width() / 2.0
        centre_y = (self.height() - FOOTER_H) / 2.0
        step = card_w + CARD_GAP

        order = sorted(range(len(self._entries)),
                       key=lambda i: abs(i - self._position), reverse=True)
        for index in order:
            distance = index - self._position
            if abs(distance) > NEIGHBOUR_REACH:
                continue
            near = min(abs(distance), 1.0)
            scale = 1.0 - 0.12 * near
            opacity = max(0.0, 1.0 - 0.62 * min(abs(distance), 1.6))
            width = card_w * scale
            height = card_h * scale
            rect = QRectF(centre_x + distance * step - width / 2.0,
                          centre_y - height / 2.0, width, height)
            self._card_rects.append((index, QRectF(rect)))
            painter.save()
            painter.setOpacity(opacity)
            self._paint_card(painter, self._entries[index], rect,
                             focused=index == self._current,
                             hovered=index == self._hover)
            painter.restore()

        self._paint_arrows(painter, centre_y)
        self._paint_footer(painter)
        painter.end()

    def _paint_card(self, painter: QPainter, entry: FileEntry, rect: QRectF,
                    focused: bool, hovered: bool) -> None:
        """Draw one file card.

        Args:
            painter (QPainter): Active painter.
            entry (FileEntry): File being drawn.
            rect (QRectF): Where the card sits.
            focused (bool): True when this is the open file.
            hovered (bool): True when the pointer is over it.
        """
        p = theme.palette
        accent = QColor(p.danger if entry.failed
                        else p.success if entry.ready else p.accent)

        if focused:
            shadow = QPainterPath()
            shadow.addRoundedRect(QRectF(rect).adjusted(0, 3, 0, 4), 8, 8)
            painter.fillPath(shadow, QColor(0, 0, 0, 44))

        body = QPainterPath()
        body.addRoundedRect(rect, 7, 7)
        painter.fillPath(body, QColor(p.bg_secondary if focused
                                      else p.bg_tertiary))
        if focused:
            painter.setPen(QPen(accent, 2.0))
        elif hovered:
            painter.setPen(QPen(QColor(p.accent_hover), 1.3))
        else:
            painter.setPen(QPen(QColor(p.border), 1.0))
        painter.drawPath(body)

        spine = QPainterPath()
        spine.addRoundedRect(
            QRectF(rect.left() + 2, rect.top() + 4, 5.0, rect.height() - 8),
            2.5, 2.5)
        painter.fillPath(spine, accent)

        inner = rect.adjusted(14, 10, -10, -10)
        self._paint_name(painter, entry, inner, focused, accent)
        self._paint_thumbnail(painter, entry, inner, accent)

    def _paint_name(self, painter: QPainter, entry: FileEntry, inner: QRectF,
                    focused: bool, accent: QColor) -> None:
        """Draw the file name and its state line.

        Args:
            painter (QPainter): Active painter.
            entry (FileEntry): File being drawn.
            inner (QRectF): Content area of the card.
            focused (bool): True when this is the open file.
            accent (QColor): Colour reflecting the file's state.
        """
        p = theme.palette
        font = QFont(painter.font())
        font.setBold(focused)
        font.setPointSizeF(max(7.5, font.pointSizeF() - 0.5))
        painter.setFont(font)
        painter.setPen(QPen(QColor(p.text_primary)))
        metrics = QFontMetrics(font)
        name_rect = QRectF(inner.left(), inner.top(), inner.width(), 16)
        painter.drawText(
            name_rect, Qt.AlignLeft | Qt.AlignVCenter,
            metrics.elidedText(entry.name, Qt.ElideMiddle,
                               int(name_rect.width())))

        state = QFont(painter.font())
        state.setBold(False)
        state.setPointSizeF(max(6.5, state.pointSizeF() - 1.5))
        painter.setFont(state)
        if entry.failed:
            text, colour = "could not be read", QColor(p.danger)
        elif entry.badge:
            text, colour = f"{entry.badge} mapped", accent
        else:
            text, colour = "not mapped yet", QColor(p.text_muted)
        painter.setPen(QPen(colour))
        painter.drawText(
            QRectF(inner.left(), inner.top() + 16, inner.width(), 13),
            Qt.AlignLeft | Qt.AlignVCenter, text)

    def _paint_thumbnail(self, painter: QPainter, entry: FileEntry,
                         inner: QRectF, accent: QColor) -> None:
        """Draw the corner of the file as a miniature table.

        The card shows the top-left of the data, header row included, so the
        file can be recognised by what is actually in it. Cells are elided
        rather than shrunk past legibility, and a removed column is struck
        through so the card agrees with the preview beside it.

        Args:
            painter (QPainter): Active painter.
            entry (FileEntry): File being drawn.
            inner (QRectF): Content area of the card.
            accent (QColor): Colour for the header band.
        """
        p = theme.palette
        area = QRectF(inner.left(), inner.top() + 34,
                      inner.width(), max(0.0, inner.height() - 34))
        if area.height() < 20:
            return

        if not entry.header:
            painter.setPen(QPen(QColor(p.text_muted)))
            painter.drawText(area, Qt.AlignCenter, entry.kind)
            return

        columns = max(1, len(entry.header))
        shown_rows = min(THUMB_ROWS, len(entry.cells))
        col_w = area.width() / columns
        row_h = max(8.0, min(24.0, area.height() / (shown_rows + 1)))

        font = QFont(painter.font())
        font.setBold(False)
        font.setPixelSize(
            int(max(6.0, min(row_h * 0.60, col_w * 0.34, 13.0))))
        metrics = QFontMetrics(font)
        painter.setFont(font)

        head_font = QFont(font)
        head_font.setBold(True)

        band = QColor(accent)
        band.setAlpha(48)
        painter.fillRect(QRectF(area.left(), area.top(),
                                area.width(), row_h), band)

        stripe = QColor(p.text_muted)
        stripe.setAlpha(16)
        for index in range(shown_rows):
            if index % 2:
                painter.fillRect(
                    QRectF(area.left(), area.top() + (index + 1) * row_h,
                           area.width(), row_h), stripe)

        rule = QColor(p.border)
        rule.setAlpha(90)
        painter.setPen(QPen(rule, 0.6))
        for index in range(1, columns):
            x = area.left() + index * col_w
            painter.drawLine(QRectF(x, area.top(), 0, 0).topLeft(),
                             QRectF(x, area.top() + (shown_rows + 1) * row_h,
                                    0, 0).topLeft())

        for col, name in enumerate(entry.header):
            removed = col in entry.removed_columns
            painter.setFont(head_font)
            painter.setPen(QPen(QColor(p.danger if removed
                                       else p.text_primary)))
            cell = QRectF(area.left() + col * col_w + 1.5, area.top(),
                          col_w - 3.0, row_h)
            painter.drawText(
                cell, Qt.AlignLeft | Qt.AlignVCenter,
                metrics.elidedText(name, Qt.ElideRight, int(cell.width())))

        painter.setFont(font)
        muted = QColor(p.text_secondary)
        removed_ink = QColor(p.danger)
        removed_ink.setAlpha(150)
        for index in range(shown_rows):
            top = area.top() + (index + 1) * row_h
            if top + row_h > area.bottom() + 1:
                break
            for col, value in enumerate(entry.cells[index]):
                if not value:
                    continue
                painter.setPen(QPen(removed_ink if col in entry.removed_columns
                                    else muted))
                cell = QRectF(area.left() + col * col_w + 1.5, top,
                              col_w - 3.0, row_h)
                painter.drawText(
                    cell, Qt.AlignLeft | Qt.AlignVCenter,
                    metrics.elidedText(value, Qt.ElideRight, int(cell.width())))

    def _paint_arrows(self, painter: QPainter, centre_y: float) -> None:
        """Draw the paging chevrons and record where they are.

        Args:
            painter (QPainter): Active painter.
            centre_y (float): Vertical centre of the card area.
        """
        p = theme.palette
        size = 20.0
        self._prev_rect = QRectF(2, centre_y - size / 2, size, size)
        self._next_rect = QRectF(self.width() - size - 2, centre_y - size / 2,
                                 size, size)

        font = QFont(painter.font())
        font.setPointSizeF(max(10.0, font.pointSizeF() + 3))
        painter.setFont(font)
        painter.setOpacity(1.0)

        for rect, enabled, glyph, hovered in (
                (self._prev_rect, self._current > 0, "‹", self._hover == -2),
                (self._next_rect, self._current < len(self._entries) - 1, "›",
                 self._hover == -3)):
            if not enabled:
                painter.setPen(QPen(QColor(p.disabled)))
            elif hovered:
                painter.setPen(QPen(QColor(p.accent)))
            else:
                painter.setPen(QPen(QColor(p.text_secondary)))
            painter.drawText(rect, Qt.AlignCenter, glyph)

    def _paint_footer(self, painter: QPainter) -> None:
        """Draw the position indicator under the cards.

        Args:
            painter (QPainter): Active painter.
        """
        p = theme.palette
        total = len(self._entries)
        strip = QRectF(0, self.height() - FOOTER_H, self.width(), FOOTER_H)
        painter.setOpacity(1.0)

        if total <= 12:
            radius = 3.0
            spacing = 11.0
            start = strip.center().x() - (total - 1) * spacing / 2.0
            for index in range(total):
                dot = QRectF(start + index * spacing - radius,
                             strip.center().y() - radius,
                             radius * 2, radius * 2)
                path = QPainterPath()
                path.addEllipse(dot)
                if index == self._current:
                    painter.fillPath(path, QColor(p.accent))
                else:
                    faint = QColor(p.text_muted)
                    faint.setAlpha(110)
                    painter.fillPath(path, faint)
            return

        font = QFont(painter.font())
        font.setPointSizeF(max(6.5, font.pointSizeF() - 1.5))
        painter.setFont(font)
        painter.setPen(QPen(QColor(p.text_muted)))
        painter.drawText(strip, Qt.AlignCenter,
                         f"{self._current + 1} of {total}")


class FileListPanel(QWidget):
    """Heading plus the sliding file browser.

    Signals:
        currentChanged: Emitted with the new index when the selection moves.
        selectionChanged: Emitted whenever the shown file changes.
    """

    currentChanged = Signal(int)
    selectionChanged = Signal()

    def __init__(self, paths=None, parent=None):
        """Build the panel and start it on the first file.

        Args:
            paths: Iterable of file paths to show, or None for an empty panel.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._entries: list[FileEntry] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._heading = QLabel("Files")
        layout.addWidget(self._heading)

        self.slider = FileSlider()
        self.slider.currentChanged.connect(self._on_current_changed)
        layout.addWidget(self.slider, 1)

        self._apply_theme()
        theme.themeChanged.connect(self._apply_theme)

        if paths:
            self.set_files(paths)

    def cleanup(self) -> None:
        """Disconnect theme signals so the widget can be collected."""
        self.slider.cleanup()
        try:
            theme.themeChanged.disconnect(self._apply_theme)
        except (RuntimeError, TypeError):
            _itk_log.debug("File panel theme signal already disconnected")

    def set_files(self, paths) -> None:
        """Replace the deck with cards for ``paths``.

        Args:
            paths: Iterable of file paths.
        """
        self._entries = [FileEntry(p) for p in paths]
        self.slider.set_entries(self._entries)
        self._refresh_heading()

    def count(self) -> int:
        """Return how many files are in the deck."""
        return len(self._entries)

    def current_index(self) -> int:
        """Return the index of the file on show."""
        return self.slider.current_index()

    def selected_indexes(self) -> list[int]:
        """Return the file on show, as the default target for an apply.

        Returns:
            list[int]: A single index, or an empty list when there are no files.
        """
        index = self.slider.current_index()
        return [index] if index >= 0 else []

    def card(self, index: int) -> FileEntry | None:
        """Return one entry, or None when the index is out of range.

        Args:
            index (int): Position in the deck.
        """
        if 0 <= index < len(self._entries):
            return self._entries[index]
        return None

    def set_current(self, index: int, animate: bool = True) -> None:
        """Slide to one file.

        Args:
            index (int): Position in the deck.
            animate (bool): False to jump without the slide.
        """
        self.slider.set_current(index, animate)

    def set_status(self, index: int, subtitle: str = "", badge: str = "",
                   ready: bool = False, failed: bool = False) -> None:
        """Update the state markers shown on one card.

        Args:
            index (int): Position in the deck.
            subtitle (str): Tooltip detail such as what has been removed.
            badge (str): Short text, such as the mapped-column count.
            ready (bool): True to mark the file as configured.
            failed (bool): True to mark the file as unreadable.
        """
        entry = self.card(index)
        if entry is None:
            return
        entry.subtitle = subtitle
        entry.badge = badge
        entry.ready = ready
        entry.failed = failed
        self.slider.update()
        self._refresh_heading()

    def set_thumbnail(self, index: int, columns, rows,
                      removed_columns=None) -> None:
        """Give one card the miniature of its file.

        Args:
            index (int): Position in the deck.
            columns: Iterable of column names.
            rows: Iterable of row sequences holding the first cell values.
            removed_columns: Iterable of column positions the user has removed.
        """
        entry = self.card(index)
        if entry is None:
            return
        entry.set_thumbnail(columns, rows)
        entry.removed_columns = {int(c) for c in (removed_columns or ())}
        self.slider.update()

    def _on_current_changed(self, index: int) -> None:
        """Relay a slide to listeners.

        Args:
            index (int): Newly shown file.
        """
        self.currentChanged.emit(index)
        self.selectionChanged.emit()

    def _refresh_heading(self) -> None:
        """Update the heading with how many files are ready to import."""
        total = len(self._entries)
        ready = sum(1 for e in self._entries if e.ready)
        self._heading.setText(f"Files  ({ready} of {total} mapped)")

    def _apply_theme(self, *_) -> None:
        """Restyle the panel for the active palette."""
        p = theme.palette
        self._heading.setStyleSheet(
            f"color: {p.text_secondary}; font-weight: bold; padding: 2px;")
        self.slider.setStyleSheet(
            f"background-color: {p.bg_secondary};"
            f"border: 1px solid {p.border}; border-radius: 4px;")
        self.slider.update()
