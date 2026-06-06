"""
tools/element_picker.py
=======================
ElementGridPopup and ElementPicker widgets — extracted from mainwindow.py to
keep that file smaller.
"""

import qtawesome as qta

from PySide6.QtCore import Qt, QSize, QPoint, QEvent, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

import theme as _theme_module   # import the module so we always get the live palette


class ElementGridPopup(QWidget):
    """Pop-up grid of every element, shown only while the user is choosing.

    Built fresh each time it opens. The currently selected element is
    highlighted. Clicking any chip emits ``selected(index)`` and closes the
    pop-up. Clicking outside (or pressing Esc) just closes it.
    """

    selected = Signal(int)

    def __init__(self, items, current_index, columns, chip_qss, palette, parent=None):
        super().__init__(parent, Qt.Popup)
        self._columns = max(1, int(columns))
        p = palette
        self.setObjectName("elementGridPopup")
        self.setStyleSheet(
            f"QWidget#elementGridPopup {{ background:{p.bg_secondary}; "
            f"border:1px solid {p.border}; border-radius:8px; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QWidget#popupGridContent { background: transparent; }"
        )

        content = QWidget()
        content.setObjectName("popupGridContent")
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)

        self._buttons = []
        for idx, (key, label) in enumerate(items):
            b = QPushButton(str(label))
            b.setCheckable(True)
            b.setChecked(idx == current_index)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.setMinimumSize(QSize(50, 30))
            if chip_qss:
                b.setStyleSheet(chip_qss)
            b.clicked.connect(lambda _checked=False, i=idx: self._choose(i))
            grid.addWidget(b, idx // self._columns, idx % self._columns)
            self._buttons.append(b)

        scroll.setWidget(content)
        outer.addWidget(scroll)

        rows = max(1, (len(items) + self._columns - 1) // self._columns)
        chip_w, chip_h, gap = 56, 30, 6
        max_rows_visible = 8
        vis_rows = min(rows, max_rows_visible)
        width = self._columns * chip_w + (self._columns - 1) * gap + 16
        height = vis_rows * chip_h + (vis_rows - 1) * gap + 16
        if rows > max_rows_visible:
            width += 12
        self.setFixedWidth(width)
        self.setFixedHeight(height)

    def _choose(self, idx):
        self.selected.emit(idx)
        self.close()


class ElementPicker(QWidget):
    """Compact element navigator for the plot header.

    Three small controls: a left arrow (previous element), a grid button that
    opens :class:`ElementGridPopup`, and a right arrow (next element). No
    element name is shown. Activating any of them emits
    ``elementActivated(element_key)``; the host commits the change and calls
    :meth:`set_current_key` to keep this widget in sync.
    """

    elementActivated = Signal(str)

    def __init__(self, columns=7, parent=None):
        super().__init__(parent)
        self._columns = columns
        self._keys = []
        self._labels = []
        self._current_index = -1
        self._chip_qss = ""
        self._current_popup = None   # track open popup

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self._prev_btn = QPushButton()
        self._grid_btn = QPushButton()
        self._next_btn = QPushButton()
        for b in (self._prev_btn, self._grid_btn, self._next_btn):
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
        self._prev_btn.setFixedSize(28, 28)
        self._next_btn.setFixedSize(28, 28)
        self._grid_btn.setFixedSize(34, 28)
        self._prev_btn.setToolTip("Previous element")
        self._next_btn.setToolTip("Next element")
        self._grid_btn.setToolTip("Choose element")

        self._prev_btn.clicked.connect(lambda: self._step(-1))
        self._next_btn.clicked.connect(lambda: self._step(1))
        self._grid_btn.clicked.connect(self._open_popup)

        lay.addWidget(self._prev_btn)
        lay.addWidget(self._grid_btn)
        lay.addWidget(self._next_btn)

        self._update_enabled()

    # ── Styling ──────────────────────────────────────────────────────────────

    def set_chip_style(self, qss):
        self._chip_qss = qss

    def apply_button_style(self, p):
        btn_qss = (
            f"QPushButton{{background:{p.bg_tertiary};color:{p.text_primary};"
            f"border:1px solid {p.border};border-radius:6px;}}"
            f"QPushButton:hover{{border-color:{p.accent};background:{p.bg_hover};}}"
            f"QPushButton:disabled{{color:{p.text_muted};"
            f"border-color:{p.border_subtle};}}"
        )
        grid_qss = (
            f"QPushButton{{background:{p.bg_tertiary};color:{p.text_primary};"
            f"border:1px solid {p.accent};border-radius:6px;}}"
            f"QPushButton:hover{{background:{p.bg_hover};}}"
            f"QPushButton:disabled{{border-color:{p.border_subtle};}}"
        )
        self._prev_btn.setStyleSheet(btn_qss)
        self._next_btn.setStyleSheet(btn_qss)
        self._grid_btn.setStyleSheet(grid_qss)
        self._prev_btn.setIcon(qta.icon('fa6s.chevron-left', color=p.text_primary))
        self._next_btn.setIcon(qta.icon('fa6s.chevron-right', color=p.text_primary))
        self._grid_btn.setIcon(qta.icon('fa6s.table-cells', color=p.accent))
        self._prev_btn.setIconSize(QSize(14, 14))
        self._next_btn.setIconSize(QSize(14, 14))
        self._grid_btn.setIconSize(QSize(15, 15))

    # ── Population / selection ────────────────────────────────────────────────

    def set_elements(self, items):
        """``items``: list of ``(element_key, label)`` in display order."""
        prev_key = self.current_key()
        self._keys = [k for k, _ in items]
        self._labels = [l for _, l in items]
        if prev_key is not None and prev_key in self._keys:
            self._current_index = self._keys.index(prev_key)
        elif self._keys:
            self._current_index = 0
        else:
            self._current_index = -1
        self._update_enabled()

    def current_key(self):
        if 0 <= self._current_index < len(self._keys):
            return self._keys[self._current_index]
        return None

    def set_current_key(self, key, emit=False):
        if key in self._keys:
            self._current_index = self._keys.index(key)
            self._update_enabled()
            if emit:
                self.elementActivated.emit(key)

    def _update_enabled(self):
        n = len(self._keys)
        i = self._current_index
        self._grid_btn.setEnabled(n > 0)
        self._prev_btn.setEnabled(n > 0 and i > 0)
        self._next_btn.setEnabled(n > 0 and 0 <= i < n - 1)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _emit_index(self, i):
        if 0 <= i < len(self._keys):
            self.elementActivated.emit(self._keys[i])

    def _step(self, delta):
        if not self._keys:
            return
        i = self._current_index if self._current_index >= 0 else 0
        self._emit_index(max(0, min(i + delta, len(self._keys) - 1)))

    def _on_popup_selected(self, idx):
        self._emit_index(idx)

    def _open_popup(self):
        if not self._keys:
            return
        # Close any previously open popup
        if self._current_popup is not None:
            self._current_popup.close()
            self._current_popup = None

        items = list(zip(self._keys, self._labels))
        popup = ElementGridPopup(
            items, self._current_index, self._columns,
            self._chip_qss, _theme_module.palette, self,
        )
        popup.setAttribute(Qt.WA_DeleteOnClose)
        popup.selected.connect(self._on_popup_selected)
        popup.destroyed.connect(self._on_popup_destroyed)
        popup.adjustSize()

        anchor = self._grid_btn.mapToGlobal(QPoint(0, self._grid_btn.height() + 4))
        x, y = anchor.x(), anchor.y()
        try:
            btn_global = self._grid_btn.mapToGlobal(QPoint(0, 0))
            scr = QGuiApplication.screenAt(btn_global)
            if scr is None:
                scr = QGuiApplication.primaryScreen()
            geom = scr.availableGeometry()
            if x + popup.width() > geom.right():
                x = geom.right() - popup.width() - 8
            if x < geom.left():
                x = geom.left() + 8
            if y + popup.height() > geom.bottom():
                y = btn_global.y() - popup.height() - 4
        except Exception:
            pass
        popup.move(x, y)
        popup.show()
        self._current_popup = popup

        # Close popup if the main window moves (it would be left behind)
        top = self.window()
        if top and top is not self:
            top.installEventFilter(self)

    def _on_popup_destroyed(self):
        self._current_popup = None
        top = self.window()
        if top and top is not self:
            top.removeEventFilter(self)

    def eventFilter(self, obj, event):
        if self._current_popup and event.type() in (
            QEvent.Move, QEvent.WindowDeactivate
        ):
            self._current_popup.close()
        return super().eventFilter(obj, event)
