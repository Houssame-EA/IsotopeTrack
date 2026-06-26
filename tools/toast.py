"""Non-blocking toast notifications for IsotopeTrack.

A lightweight, theme-aware replacement for transient ``QMessageBox.information``
popups. Toasts slide in from the top-right of the host window, stack
vertically, auto-dismiss, and never steal focus or block the UI.

Usage:
    self.toasts = ToastManager(self)          # once, on the main window
    self.toasts.show("Project saved", "success")

Levels: "success", "info", "warning", "error".
"""
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QGraphicsOpacityEffect, QWidget,
)
from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QObject, QEvent,
    QParallelAnimationGroup,
)
import logging

from tools.theme import theme

try:
    import qtawesome as qta
except Exception:
    qta = None

_itk_log = logging.getLogger("IsotopeTrack.tools.toast")

_LEVELS = {
    "success": ("fa6s.circle-check", "success"),
    "info":    ("fa6s.circle-info", "accent"),
    "warning": ("fa6s.triangle-exclamation", "warning"),
    "error":   ("fa6s.circle-xmark", "danger"),
}

_MARGIN = 18      # distance from the window's top-right corner
_GAP = 10         # vertical gap between stacked toasts
_WIDTH = 330


class Toast(QFrame):
    """A single auto-dismissing notification card."""

    def __init__(self, host, message, level="info", duration=3500, on_done=None):
        super().__init__(host)
        self._host = host
        self._on_done = on_done
        self._duration = max(1200, int(duration))
        self._closing = False

        self.setObjectName("toastCard")
        self.setFixedWidth(_WIDTH)
        self.setAttribute(Qt.WA_StyledBackground, True)

        icon_name, color_attr = _LEVELS.get(level, _LEVELS["info"])
        accent = getattr(theme.palette, color_attr, theme.palette.accent)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 10, 12)
        lay.setSpacing(10)

        self._icon = QLabel()
        if qta is not None:
            try:
                self._icon.setPixmap(qta.icon(icon_name, color=accent).pixmap(20, 20))
            except Exception:
                _itk_log.debug("toast icon unavailable")
        self._icon.setFixedWidth(22)
        self._icon.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        lay.addWidget(self._icon, 0, Qt.AlignTop)

        self._label = QLabel(message)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self._label, 1)

        self._close = QPushButton("✕")  # ✕
        self._close.setCursor(Qt.PointingHandCursor)
        self._close.setFixedSize(20, 20)
        self._close.setFlat(True)
        self._close.clicked.connect(self.dismiss)
        lay.addWidget(self._close, 0, Qt.AlignTop)

        self._apply_style(accent)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.dismiss)

        self.adjustSize()

    # -- styling ---------------------------------------------------------------

    def _apply_style(self, accent):
        p = theme.palette
        self.setStyleSheet(
            f"""
            QFrame#toastCard {{
                background: {p.bg_secondary};
                border: 1px solid {p.border};
                border-left: 4px solid {accent};
                border-radius: 10px;
            }}
            QLabel {{ color: {p.text_primary}; background: transparent;
                      font-size: 13px; }}
            QPushButton {{ color: {p.text_muted}; background: transparent;
                           border: none; font-size: 13px; font-weight: bold; }}
            QPushButton:hover {{ color: {p.text_primary}; }}
            """
        )

    # -- animation lifecycle ---------------------------------------------------

    def appear(self, target: QPoint):
        """Slide in from the right + fade in to *target* (top-left in host)."""
        self.show()
        self.raise_()
        start = QPoint(target.x() + 40, target.y())
        self.move(start)

        self._anim = QParallelAnimationGroup(self)

        slide = QPropertyAnimation(self, b"pos")
        slide.setDuration(240)
        slide.setEasingCurve(QEasingCurve.OutCubic)
        slide.setStartValue(start)
        slide.setEndValue(target)
        self._anim.addAnimation(slide)

        fade = QPropertyAnimation(self._opacity, b"opacity")
        fade.setDuration(240)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        self._anim.addAnimation(fade)

        self._anim.start()
        self._dismiss_timer.start(self._duration)

    def move_to(self, target: QPoint):
        """Animate a reposition (when toasts above are dismissed)."""
        try:
            self._reflow = QPropertyAnimation(self, b"pos")
            self._reflow.setDuration(180)
            self._reflow.setEasingCurve(QEasingCurve.OutCubic)
            self._reflow.setStartValue(self.pos())
            self._reflow.setEndValue(target)
            self._reflow.start()
        except Exception:
            self.move(target)

    def dismiss(self):
        if self._closing:
            return
        self._closing = True
        self._dismiss_timer.stop()
        try:
            self._out = QParallelAnimationGroup(self)
            slide = QPropertyAnimation(self, b"pos")
            slide.setDuration(200)
            slide.setEasingCurve(QEasingCurve.InCubic)
            slide.setStartValue(self.pos())
            slide.setEndValue(QPoint(self.pos().x() + 40, self.pos().y()))
            self._out.addAnimation(slide)
            fade = QPropertyAnimation(self._opacity, b"opacity")
            fade.setDuration(200)
            fade.setStartValue(self._opacity.opacity())
            fade.setEndValue(0.0)
            self._out.addAnimation(fade)
            self._out.finished.connect(self._finalize)
            self._out.start()
        except Exception:
            self._finalize()

    def _finalize(self):
        if callable(self._on_done):
            try:
                self._on_done(self)
            except Exception:
                _itk_log.debug("toast on_done failed")
        self.setParent(None)
        self.deleteLater()

    def enterEvent(self, event):
        # Pause auto-dismiss while hovered.
        self._dismiss_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._closing:
            self._dismiss_timer.start(1500)
        super().leaveEvent(event)


class ToastManager(QObject):
    """Owns the stack of toasts for one window and keeps them positioned."""

    def __init__(self, host: QWidget):
        super().__init__(host)
        self._host = host
        self._toasts = []
        host.installEventFilter(self)

    def show(self, message, level="info", duration=3500):
        try:
            toast = Toast(self._host, message, level, duration, on_done=self._remove)
            self._toasts.append(toast)
            self._reflow(animate_existing=True, appear=toast)
            return toast
        except Exception:
            _itk_log.exception("Could not show toast")
            return None

    # Convenience shortcuts
    def success(self, message, duration=3500):
        return self.show(message, "success", duration)

    def info(self, message, duration=3500):
        return self.show(message, "info", duration)

    def warning(self, message, duration=4500):
        return self.show(message, "warning", duration)

    def error(self, message, duration=6000):
        return self.show(message, "error", duration)

    # -- internals -------------------------------------------------------------

    def _remove(self, toast):
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._reflow()

    def _target_for(self, index):
        x = self._host.width() - _WIDTH - _MARGIN
        y = _MARGIN
        for t in self._toasts[:index]:
            y += t.height() + _GAP
        return QPoint(max(_MARGIN, x), y)

    def _reflow(self, animate_existing=False, appear=None):
        for i, t in enumerate(self._toasts):
            target = self._target_for(i)
            if t is appear:
                t.appear(target)
            elif animate_existing:
                t.move_to(target)
            else:
                t.move_to(target)

    def eventFilter(self, obj, event):
        if obj is self._host and event.type() in (QEvent.Resize, QEvent.Move):
            self._reflow()
        return False
