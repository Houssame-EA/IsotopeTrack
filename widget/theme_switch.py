# -*- coding: utf-8 -*-
"""Sliding light/dark switch for window headers.

A rounded track with a sun on the left and a moon on the right; a knob
slides over the active side. It is a checkable button: checked means dark.
Colours come from the application palette and are refreshed with
:meth:`ThemeSwitch.set_palette`.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton

import qtawesome as qta

_SUN_ON = '#f39c12'
_MOON_ON = '#f5d76e'


class ThemeSwitch(QAbstractButton):
    """Sliding sun / moon switch; checked means dark mode.

    Args:
        parent: Parent widget.
    """

    _W, _H = 52, 28

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(self._W, self._H)
        self._offset = 0.0
        self._track = QColor('#eef2f6')
        self._border = QColor('#d4dde6')
        self._knob = QColor('#ffffff')
        self._muted = QColor('#7f8c8d')
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._slide)

    def sizeHint(self):
        return QSize(self._W, self._H)

    def _get_offset(self):
        return self._offset

    def _set_offset(self, value):
        self._offset = float(value)
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _slide(self, checked):
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def set_dark(self, dark):
        """Show the given mode without emitting signals.

        Args:
            dark (bool): True for dark mode.
        """
        if self.isChecked() == bool(dark):
            return
        self.blockSignals(True)
        self.setChecked(bool(dark))
        self.blockSignals(False)
        self._anim.stop()
        self._offset = 1.0 if dark else 0.0
        self.update()

    def set_palette(self, p):
        """Take the track, knob and icon colours from an application palette.

        Args:
            p: A :class:`tools.theme.Palette`.
        """
        dark = getattr(p, 'name', 'light') == 'dark'
        self._track = QColor(p.bg_tertiary if not dark else '#1b1b1c')
        self._border = QColor(p.border)
        self._knob = QColor('#ffffff' if not dark else '#3a3a3d')
        self._muted = QColor(p.text_muted)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        track = QRectF(0.5, 0.5, w - 1, h - 1)
        painter.setPen(QPen(self._border, 1))
        painter.setBrush(self._track)
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)

        icon = 12
        pad = (h - icon) / 2
        sun_on = self._offset < 0.5
        sun = qta.icon('fa6s.sun', color=_SUN_ON if sun_on else self._muted.name())
        moon = qta.icon('fa6s.moon', color=self._muted.name() if sun_on else _MOON_ON)
        painter.drawPixmap(int(pad + 1), int(pad), sun.pixmap(icon, icon))
        painter.drawPixmap(int(w - pad - icon - 1), int(pad), moon.pixmap(icon, icon))

        knob = h - 6
        x = 3 + self._offset * (w - knob - 6)
        painter.setPen(QPen(self._border, 1))
        painter.setBrush(self._knob)
        painter.drawEllipse(QRectF(x, 3, knob, knob))
        active = moon if not sun_on else sun
        painter.drawPixmap(int(x + (knob - icon) / 2), int(3 + (knob - icon) / 2),
                           active.pixmap(icon, icon))
        painter.end()
