"""Vertical file list for the import dialog.

The list sits beside the preview rather than above it, so the preview keeps the
height it needs. Each row carries a small thumbnail of that file's own first
rows, drawn as bars the way a document viewer renders page text, which is
enough to tell a two-column rinse from a six-column run without reading
anything. Selecting a row loads that file into the preview.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QLabel, QListWidget, QListWidgetItem, QVBoxLayout,
    QWidget,
)

from tools.theme import theme

_itk_log = logging.getLogger("IsotopeTrack.loading.file_list_panel")

THUMB_W = 76
THUMB_H = 50
THUMB_COLUMNS = 5
THUMB_ROWS = 5
SPINE_W = 4.0


class FileEntry:
    """Display state and thumbnail content for one file in the list."""

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
        self.header: list[float] = []
        self.cells: list[list[float]] = []
        self.removed_columns: set[int] = set()

    def set_thumbnail(self, columns, rows) -> None:
        """Store a miniature of the file as relative bar widths.

        Args:
            columns: Iterable of column names.
            rows: Iterable of row sequences holding the first cell values.
        """
        names = [str(c) for c in columns][:THUMB_COLUMNS]
        self.header = [self._fill(n) for n in names]
        self.cells = []
        for row in list(rows)[:THUMB_ROWS]:
            values = list(row)[:THUMB_COLUMNS]
            self.cells.append([self._fill(v) for v in values])

    @staticmethod
    def _fill(value) -> float:
        """Return how full a thumbnail cell should look, from 0 to 1.

        Args:
            value: Raw cell or header value.

        Returns:
            float: Fraction of the cell width the bar should occupy.
        """
        text = "" if value is None else str(value).strip()
        if not text or text.lower() == "nan":
            return 0.0
        return min(1.0, 0.34 + len(text) * 0.08)


def render_thumbnail(entry: FileEntry, accent: QColor, muted: QColor,
                     danger: QColor, surface: QColor, border: QColor,
                     selected: bool = False) -> QPixmap:
    """Draw one file as a small card carrying a miniature of its data.

    The card keeps the look of a document: a page with a coloured spine down
    the left edge and its text reduced to bars. That is enough to tell a
    two-column rinse from a six-column run without reading anything.

    Args:
        entry (FileEntry): File whose card is wanted.
        accent (QColor): Spine colour, reflecting the file's state.
        muted (QColor): Colour for the data bars.
        danger (QColor): Colour marking removed columns.
        surface (QColor): Card background.
        border (QColor): Card outline.
        selected (bool): True when this is the file on screen.

    Returns:
        QPixmap: The rendered card.
    """
    pixmap = QPixmap(THUMB_W, THUMB_H)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)

    frame = QRectF(0.5, 0.5, THUMB_W - 1.5, THUMB_H - 1.5)
    card = QPainterPath()
    card.addRoundedRect(frame, 4, 4)
    painter.fillPath(card, surface)
    painter.setPen(QPen(QColor(accent) if selected else border,
                        1.6 if selected else 1.0))
    painter.drawPath(card)

    spine = QPainterPath()
    spine.addRoundedRect(
        QRectF(frame.left() + 1, frame.top() + 2, SPINE_W, frame.height() - 4),
        2, 2)
    painter.fillPath(spine, accent)

    if not entry.header:
        painter.setPen(QPen(muted))
        font = QFont(painter.font())
        font.setPointSizeF(max(5.5, font.pointSizeF() - 3.0))
        painter.setFont(font)
        painter.drawText(frame.adjusted(SPINE_W + 4, 0, -2, 0),
                         Qt.AlignCenter, entry.kind)
        painter.end()
        return pixmap

    inner = frame.adjusted(SPINE_W + 5, 5, -5, -5)
    columns = max(1, len(entry.header))
    col_w = inner.width() / columns
    bar_h = 2.4
    gap = 2.2

    header_colour = QColor(accent)
    header_colour.setAlpha(210)
    cell_colour = QColor(muted)
    cell_colour.setAlpha(160)
    removed_colour = QColor(danger)
    removed_colour.setAlpha(160)

    y = inner.top()
    for col, fill in enumerate(entry.header):
        if fill <= 0:
            continue
        colour = removed_colour if col in entry.removed_columns else header_colour
        painter.fillRect(
            QRectF(inner.left() + col * col_w, y,
                   max(2.0, (col_w - 1.8) * fill), bar_h + 0.6), colour)

    y += bar_h + gap + 1.4
    for row in entry.cells:
        for col, fill in enumerate(row):
            if fill <= 0:
                continue
            colour = (removed_colour if col in entry.removed_columns
                      else cell_colour)
            painter.fillRect(
                QRectF(inner.left() + col * col_w, y,
                       max(1.8, (col_w - 1.8) * fill), bar_h), colour)
        y += bar_h + gap
        if y > inner.bottom():
            break

    painter.end()
    return pixmap


class FileListPanel(QWidget):
    """List of the files being imported, with the open one selected.

    Signals:
        currentChanged: Emitted with the new index when the selection moves.
    """

    currentChanged = Signal(int)
    selectionChanged = Signal()

    def __init__(self, paths=None, parent=None):
        """Build the list and start it on the first file.

        Args:
            paths: Iterable of file paths to show, or None for an empty list.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._entries: list[FileEntry] = []
        self._guard = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._heading = QLabel("Files")
        layout.addWidget(self._heading)

        self.list = QListWidget()
        self.list.setIconSize(QSize(THUMB_W, THUMB_H))
        self.list.setUniformItemSizes(True)
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.currentRowChanged.connect(self._on_row_changed)
        self.list.itemSelectionChanged.connect(self.selectionChanged.emit)
        layout.addWidget(self.list, 1)

        self._apply_theme()
        theme.themeChanged.connect(self._apply_theme)

        if paths:
            self.set_files(paths)

    def cleanup(self) -> None:
        """Disconnect the theme signal so the widget can be collected."""
        try:
            theme.themeChanged.disconnect(self._apply_theme)
        except (RuntimeError, TypeError):
            _itk_log.debug("File list theme signal already disconnected")

    def set_files(self, paths) -> None:
        """Replace the list with rows for ``paths``.

        Args:
            paths: Iterable of file paths.
        """
        self._entries = [FileEntry(p) for p in paths]
        self._guard = True
        try:
            self.list.clear()
            for entry in self._entries:
                item = QListWidgetItem(entry.name)
                item.setToolTip(entry.path)
                self.list.addItem(item)
            if self._entries:
                self.list.setCurrentRow(0)
        finally:
            self._guard = False
        self._refresh_rows()
        self._refresh_heading()

    def count(self) -> int:
        """Return how many files are listed."""
        return len(self._entries)

    def current_index(self) -> int:
        """Return the index of the file being previewed."""
        return self.list.currentRow()

    def selected_indexes(self) -> list[int]:
        """Return every highlighted file, for acting on several at once.

        Ctrl-click and shift-click extend the highlight without changing which
        file the preview shows, so a setup can be pushed to a chosen subset of
        the batch rather than always to all of it.

        Returns:
            list[int]: Positions of the highlighted files, in order.
        """
        return sorted(self.list.row(item)
                      for item in self.list.selectedItems())

    def card(self, index: int) -> FileEntry | None:
        """Return one entry, or None when the index is out of range.

        Args:
            index (int): Position in the list.
        """
        if 0 <= index < len(self._entries):
            return self._entries[index]
        return None

    def set_current(self, index: int, animate: bool = True) -> None:
        """Select one file.

        Args:
            index (int): Position in the list.
            animate (bool): Accepted for call compatibility and ignored.
        """
        if 0 <= index < len(self._entries):
            self.list.setCurrentRow(index)

    def set_status(self, index: int, subtitle: str = "", badge: str = "",
                   ready: bool = False, failed: bool = False) -> None:
        """Update the state markers shown on one row.

        Args:
            index (int): Position in the list.
            subtitle (str): Detail line such as what has been removed.
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
        self._refresh_row(index)
        self._refresh_heading()

    def set_thumbnail(self, index: int, columns, rows,
                      removed_columns=None) -> None:
        """Give one row the miniature of its file.

        Args:
            index (int): Position in the list.
            columns: Iterable of column names.
            rows: Iterable of row sequences holding the first cell values.
            removed_columns: Iterable of column positions the user has removed.
        """
        entry = self.card(index)
        if entry is None:
            return
        entry.set_thumbnail(columns, rows)
        entry.removed_columns = {int(c) for c in (removed_columns or ())}
        self._refresh_row(index)

    def _on_row_changed(self, row: int) -> None:
        """Relay a selection change to listeners.

        Args:
            row (int): Newly selected row.
        """
        if self._guard or row < 0:
            return
        self._refresh_rows()
        self.currentChanged.emit(row)

    def _refresh_heading(self) -> None:
        """Update the heading with how many files are ready to import."""
        total = len(self._entries)
        ready = sum(1 for e in self._entries if e.ready)
        self._heading.setText(f"Files  ({ready} of {total} mapped)")

    def _refresh_rows(self) -> None:
        """Redraw every row."""
        for index in range(len(self._entries)):
            self._refresh_row(index)

    def _refresh_row(self, index: int) -> None:
        """Redraw one row's thumbnail, label and colour.

        Args:
            index (int): Position in the list.
        """
        item = self.list.item(index)
        entry = self.card(index)
        if item is None or entry is None:
            return

        p = theme.palette
        accent = QColor(p.danger if entry.failed
                        else p.success if entry.ready else p.accent)
        item.setIcon(QIcon(render_thumbnail(
            entry, accent, QColor(p.text_muted), QColor(p.danger),
            QColor(p.bg_primary), QColor(p.border),
            selected=index == self.list.currentRow())))

        label = entry.name
        if entry.badge:
            label = f"{entry.name}\n{entry.badge} mapped"
        elif entry.failed:
            label = f"{entry.name}\ncould not be read"
        item.setText(label)
        item.setToolTip(f"{entry.path}\n{entry.subtitle}"
                        if entry.subtitle else entry.path)
        item.setForeground(QColor(p.danger if entry.failed else p.text_primary))

    def _apply_theme(self, *_) -> None:
        """Restyle the list for the active palette."""
        p = theme.palette
        self._heading.setStyleSheet(
            f"color: {p.text_secondary}; font-weight: bold; padding: 2px;")
        self.list.setStyleSheet(f"""
            QListWidget {{
                background-color: {p.bg_secondary};
                border: 1px solid {p.border};
                border-radius: 4px;
                color: {p.text_primary};
                outline: none;
            }}
            QListWidget::item {{
                padding: 6px 8px;
                margin: 2px 3px;
                border-radius: 5px;
            }}
            QListWidget::item:selected {{
                background-color: {p.accent_soft};
                color: {p.text_primary};
            }}
            QListWidget::item:hover {{
                background-color: {p.bg_hover};
            }}
        """)
        self._refresh_rows()
