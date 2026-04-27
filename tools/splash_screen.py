"""Animated splash screen with particle effects and progressive loading integration."""
from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QObject,
    QParallelAnimationGroup,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSequentialAnimationGroup,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QLabel,
    QWidget,
)


# ---------------------------------------------------------------------------
# Design constants — tweak here, not in the code below
# ---------------------------------------------------------------------------
class Config:
    SIZE = 500

    PROGRESS_RADIUS = 120
    INNER_RADIUS = 80
    GLOW_EXTRA = 40
    RING_INSET = 15
    RING_WIDTH = 8

    LOGO_SIZE = 80
    LOGO_Y_OFFSET = -60

    FRAME_MS = 16
    LOGO_ANIM_MS = 800
    TEXT_ANIM_MS = 600
    GLOW_ANIM_MS = 1000
    COMPLETE_DELAY_MS = 500
    TIME_WRAP = 100_000

    ORBIT_RATIOS = (0.70, 0.85, 1.00, 1.15)
    PARTICLES_PER_RING = 12

    PARTICLE_PALETTE = (
        QColor(100, 200, 255),
        QColor(200, 100, 255),
        QColor(150, 255, 150),
        QColor(255, 200, 100),
    )
    PROGRESS_GRADIENT_COLORS = (
        QColor(100, 200, 255),
        QColor(150, 150, 255),
        QColor(200, 100, 255),
    )
    GLOW_INNER = QColor(100, 200, 255)
    GLOW_MID = QColor(200, 100, 255)
    BG_RING_STOPS = (
        (0.0, QColor(45, 45, 55, 220)),
        (0.8, QColor(30, 30, 40, 200)),
        (1.0, QColor(20, 20, 30, 180)),
    )
    INNER_RING_STOPS = (
        (0.0, QColor(60, 60, 70, 180)),
        (1.0, QColor(40, 40, 50, 200)),
    )
    RING_BORDER = QColor(80, 80, 90, 150)
    INNER_BORDER = QColor(100, 100, 110, 100)
    PROGRESS_TRACK = QColor(60, 60, 70, 150)


# ---------------------------------------------------------------------------
# Animatable scalar — parented cleanly, no QObject.parent() shadowing
# ---------------------------------------------------------------------------
class AnimatedValue(QObject):
    """Animatable float that triggers a widget repaint on every change."""

    def __init__(self, widget: QWidget, initial: float = 0.0):
        """
        Args:
            widget (QWidget): Target widget.
            initial (float): The initial.
        """
        super().__init__(widget)
        self._widget = widget
        self._value = initial

    def _get(self) -> float:
        """
        Returns:
            float: Result of the operation.
        """
        return self._value

    def _set(self, value: float) -> None:
        """
        Args:
            value (float): Value to set or process.
        Returns:
            None
        """
        self._value = value
        self._widget.update()

    value = Property(float, _get, _set)


# ---------------------------------------------------------------------------
# Particle
# ---------------------------------------------------------------------------
@dataclass
class Particle:
    """Particle orbiting a center point with a pulsing size/opacity."""
    center: QPointF
    orbit_radius: float
    angle: float
    speed: float
    base_size: float
    base_opacity: float
    color: QColor
    pulse_offset: float
    current_size: float = 0.0
    current_opacity: float = 0.0

    @classmethod
    def random(cls, center: QPointF, orbit_radius: float) -> "Particle":
        """
        Args:
            center (QPointF): The center.
            orbit_radius (float): The orbit radius.
        Returns:
            'Particle': Result of the operation.
        """
        return cls(
            center=center,
            orbit_radius=orbit_radius + random.uniform(-20, 20),
            angle=random.uniform(0, 2 * math.pi),
            speed=random.uniform(0.005, 0.02),
            base_size=random.uniform(1.5, 4.0),
            base_opacity=random.uniform(0.3, 0.8),
            color=random.choice(Config.PARTICLE_PALETTE),
            pulse_offset=random.uniform(0, 2 * math.pi),
        )

    def update(self, time_factor: float) -> None:
        """
        Args:
            time_factor (float): The time factor.
        Returns:
            None
        """
        self.angle = (self.angle + self.speed * time_factor) % (2 * math.pi)
        pulse = math.sin(time_factor * 0.05 + self.pulse_offset) * 0.3 + 0.7
        self.current_size = self.base_size * pulse
        self.current_opacity = self.base_opacity * pulse

    def position(self) -> QPointF:
        """
        Returns:
            QPointF: Result of the operation.
        """
        return QPointF(
            self.center.x() + self.orbit_radius * math.cos(self.angle),
            self.center.y() + self.orbit_radius * math.sin(self.angle),
        )


# ---------------------------------------------------------------------------
# Splash screen
# ---------------------------------------------------------------------------
class SplashScreen(QWidget):
    """Animated circular splash screen with particle effects and progress."""

    finished = Signal()

    def __init__(
        self,
        logo_path: Optional[str] = None,
        app_name: str = "IsotopeTrack",
        version: str = "Version 1.0.2:Beta",
    ):
        """
        Args:
            logo_path (Optional[str]): The logo path.
            app_name (str): The app name.
            version (str): The version.
        """
        super().__init__()
        self.app_name = app_name
        self.version = version
        self.logo_path = logo_path
        self.current_status = "Initializing..."
        self._progress = 0.0
        self.time_factor = 0.0

        self._configure_window()
        self.center = QPointF(Config.SIZE / 2, Config.SIZE / 2)

        self._glow_intensity = AnimatedValue(self)
        self._logo_scale = AnimatedValue(self)

        self._build_particles()
        self._build_ui()
        self._build_gradients()
        self._build_animations()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(Config.FRAME_MS)

    # ---------- Setup ----------

    def _configure_window(self) -> None:
        """
        Returns:
            None
        """
        self.setWindowTitle("sp-IsotopeTrack")
        self.setFixedSize(Config.SIZE, Config.SIZE)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def _build_particles(self) -> None:
        """
        Returns:
            None
        """
        self.particles: list[Particle] = []
        for ratio in Config.ORBIT_RATIOS:
            orbit = Config.PROGRESS_RADIUS * ratio
            count = max(1, int(Config.PARTICLES_PER_RING * ratio))
            self.particles.extend(
                Particle.random(self.center, orbit) for _ in range(count)
            )

    def _build_ui(self) -> None:
        """
        Returns:
            None
        """
        cx = int(self.center.x())
        cy = int(self.center.y())

        self.logo_label: Optional[QLabel] = None
        if self.logo_path:
            pixmap = QPixmap(self.logo_path)
            if not pixmap.isNull():
                self.logo_label = QLabel(self)
                scaled = pixmap.scaled(
                    Config.LOGO_SIZE, Config.LOGO_SIZE,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
                self.logo_label.setPixmap(scaled)
                self.logo_label.setGeometry(
                    cx - Config.LOGO_SIZE // 2,
                    cy + Config.LOGO_Y_OFFSET,
                    Config.LOGO_SIZE, Config.LOGO_SIZE,
                )
                self.logo_label.setStyleSheet("background: transparent;")

        self.app_label = QLabel(self.app_name, self)
        self.app_label.setStyleSheet(
            "color: white; font-size: 28px; font-weight: bold; "
            "font-family: Arial, sans-serif; background: transparent;"
        )
        self.app_label.setAlignment(Qt.AlignCenter)
        self.app_label.setGeometry(cx - 100, cy + 30, 200, 40)

        self.version_label = QLabel(self.version, self)
        self.version_label.setStyleSheet(
            "color: #cccccc; font-size: 14px; "
            "font-family: Arial, sans-serif; background: transparent;"
        )
        self.version_label.setAlignment(Qt.AlignCenter)
        self.version_label.setGeometry(cx - 75, cy + 75, 150, 25)

        self.status_label = QLabel(self.current_status, self)
        self.status_label.setStyleSheet(
            "color: rgba(255, 255, 255, 180); font-size: 12px; "
            "font-family: Arial, sans-serif; background: transparent;"
        )
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setGeometry(cx - 120, cy + 140, 240, 25)

        self._app_opacity = QGraphicsOpacityEffect(self.app_label)
        self._app_opacity.setOpacity(0.0)
        self.app_label.setGraphicsEffect(self._app_opacity)

        self._version_opacity = QGraphicsOpacityEffect(self.version_label)
        self._version_opacity.setOpacity(0.0)
        self.version_label.setGraphicsEffect(self._version_opacity)

    def _build_gradients(self) -> None:
        """Pre-compute gradients that never change between frames.
        Returns:
            None
        """
        self._bg_gradient = QRadialGradient(self.center, Config.PROGRESS_RADIUS)
        for stop, color in Config.BG_RING_STOPS:
            self._bg_gradient.setColorAt(stop, color)

        self._inner_gradient = QRadialGradient(self.center, Config.INNER_RADIUS)
        for stop, color in Config.INNER_RING_STOPS:
            self._inner_gradient.setColorAt(stop, color)

        self._progress_gradient = QLinearGradient(0, 0, Config.SIZE, Config.SIZE)
        c1, c2, c3 = Config.PROGRESS_GRADIENT_COLORS
        self._progress_gradient.setColorAt(0.0, c1)
        self._progress_gradient.setColorAt(0.5, c2)
        self._progress_gradient.setColorAt(1.0, c3)

    def _build_animations(self) -> None:
        """
        Returns:
            None
        """
        logo_anim = QPropertyAnimation(self._logo_scale, b"value", self)
        logo_anim.setDuration(Config.LOGO_ANIM_MS)
        logo_anim.setStartValue(0.0)
        logo_anim.setEndValue(1.0)
        logo_anim.setEasingCurve(QEasingCurve.OutBack)

        app_fade = QPropertyAnimation(self._app_opacity, b"opacity", self)
        app_fade.setDuration(Config.TEXT_ANIM_MS)
        app_fade.setStartValue(0.0)
        app_fade.setEndValue(1.0)
        app_fade.setEasingCurve(QEasingCurve.InOutQuad)

        version_fade = QPropertyAnimation(self._version_opacity, b"opacity", self)
        version_fade.setDuration(Config.TEXT_ANIM_MS)
        version_fade.setStartValue(0.0)
        version_fade.setEndValue(1.0)
        version_fade.setEasingCurve(QEasingCurve.InOutQuad)

        glow_anim = QPropertyAnimation(self._glow_intensity, b"value", self)
        glow_anim.setDuration(Config.GLOW_ANIM_MS)
        glow_anim.setStartValue(0.0)
        glow_anim.setEndValue(1.0)
        glow_anim.setEasingCurve(QEasingCurve.InOutSine)

        parallel = QParallelAnimationGroup(self)
        parallel.addAnimation(app_fade)
        parallel.addAnimation(version_fade)
        parallel.addAnimation(glow_anim)

        self._animations = QSequentialAnimationGroup(self)
        self._animations.addAnimation(logo_anim)
        self._animations.addAnimation(parallel)
        self._animations.start()

    # ---------- Public API ----------

    def update_progress(self, progress: float, status_text: str = "") -> None:
        """Update progress (0–100) and optional status text.
        Args:
            progress (float): Progress value (0–100).
            status_text (str): The status text.
        Returns:
            None
        """
        self._progress = max(0.0, min(100.0, progress))
        if status_text:
            self.current_status = status_text
            self.status_label.setText(status_text)
        self.update()

    def set_loading_complete(self) -> None:
        """Mark loading complete and schedule the close.
        Returns:
            None
        """
        self._progress = 100.0
        self.current_status = "Loading complete!"
        self.status_label.setText(self.current_status)
        self.update()
        QTimer.singleShot(Config.COMPLETE_DELAY_MS, self._finish)

    def get_progress(self) -> float:
        """
        Returns:
            float: Result of the operation.
        """
        return self._progress

    def set_progress(self, value: float) -> None:
        """
        Args:
            value (float): Value to set or process.
        Returns:
            None
        """
        self._progress = value
        self.update()

    progress = Property(float, get_progress, set_progress)

    # ---------- Animation loop ----------

    def _tick(self) -> None:
        """
        Returns:
            None
        """
        self.time_factor = (self.time_factor + 1) % Config.TIME_WRAP

        for particle in self.particles:
            particle.update(self.time_factor)

        if self.logo_label:
            scale = self._logo_scale.value
            if 0 < scale < 1.0:
                size = int(Config.LOGO_SIZE * scale)
                self.logo_label.resize(size, size)
                self.logo_label.move(
                    int(self.center.x()) - size // 2,
                    int(self.center.y()) + Config.LOGO_Y_OFFSET,
                )
            elif scale >= 1.0 and self.logo_label.width() != Config.LOGO_SIZE:
                self.logo_label.resize(Config.LOGO_SIZE, Config.LOGO_SIZE)
                self.logo_label.move(
                    int(self.center.x()) - Config.LOGO_SIZE // 2,
                    int(self.center.y()) + Config.LOGO_Y_OFFSET,
                )

        self.update()

    # ---------- Painting ----------

    def paintEvent(self, event) -> None:
        """
        Args:
            event (Any): Qt event object.
        Returns:
            None
        """
        if not self.isVisible():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        try:
            self._paint_glow(painter)
            self._paint_rings(painter)
            self._paint_particles(painter)
            self._paint_progress_arc(painter)
            self._paint_progress_text(painter)
        finally:
            painter.end()

    def _paint_glow(self, painter: QPainter) -> None:
        """
        Args:
            painter (QPainter): QPainter instance.
        Returns:
            None
        """
        intensity = self._glow_intensity.value
        if intensity <= 0:
            return
        radius = Config.PROGRESS_RADIUS + Config.GLOW_EXTRA
        gradient = QRadialGradient(self.center, radius)
        inner = QColor(Config.GLOW_INNER)
        inner.setAlpha(int(50 * intensity))
        mid = QColor(Config.GLOW_MID)
        mid.setAlpha(int(30 * intensity))
        gradient.setColorAt(0.0, inner)
        gradient.setColorAt(0.7, mid)
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(self.center, radius, radius)

    def _paint_rings(self, painter: QPainter) -> None:
        """
        Args:
            painter (QPainter): QPainter instance.
        Returns:
            None
        """
        painter.setBrush(self._bg_gradient)
        painter.setPen(QPen(Config.RING_BORDER, 2))
        painter.drawEllipse(self.center, Config.PROGRESS_RADIUS, Config.PROGRESS_RADIUS)

        painter.setBrush(self._inner_gradient)
        painter.setPen(QPen(Config.INNER_BORDER, 1))
        painter.drawEllipse(self.center, Config.INNER_RADIUS, Config.INNER_RADIUS)

    def _paint_particles(self, painter: QPainter) -> None:
        """
        Args:
            painter (QPainter): QPainter instance.
        Returns:
            None
        """
        painter.setPen(Qt.NoPen)
        for p in self.particles:
            color = QColor(p.color)
            color.setAlphaF(max(0.0, min(1.0, p.current_opacity)))
            painter.setBrush(color)
            painter.drawEllipse(p.position(), p.current_size, p.current_size)

    def _paint_progress_arc(self, painter: QPainter) -> None:
        """
        Args:
            painter (QPainter): QPainter instance.
        Returns:
            None
        """
        if self._progress <= 0:
            return
        arc_radius = Config.PROGRESS_RADIUS - Config.RING_INSET

        painter.setPen(QPen(Config.PROGRESS_TRACK, Config.RING_WIDTH))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(self.center, arc_radius, arc_radius)

        rect = QRectF(
            self.center.x() - arc_radius,
            self.center.y() - arc_radius,
            arc_radius * 2,
            arc_radius * 2,
        )
        path = QPainterPath()
        path.arcMoveTo(rect, 90)
        path.arcTo(rect, 90, -self._progress * 3.6)

        painter.setPen(QPen(
            QBrush(self._progress_gradient),
            Config.RING_WIDTH,
            Qt.SolidLine,
            Qt.RoundCap,
        ))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    def _paint_progress_text(self, painter: QPainter) -> None:
        """
        Args:
            painter (QPainter): QPainter instance.
        Returns:
            None
        """
        if self._progress <= 0:
            return
        painter.setFont(QFont("Arial", 18, QFont.Bold))
        text = f"{int(self._progress)}%"

        painter.setPen(QColor(0, 0, 0, 100))
        painter.drawText(
            QRectF(self.center.x() - 49, self.center.y() - 9, 100, 30),
            Qt.AlignCenter, text,
        )
        painter.setPen(QColor(255, 255, 255, 240))
        painter.drawText(
            QRectF(self.center.x() - 50, self.center.y() - 10, 100, 30),
            Qt.AlignCenter, text,
        )

    # ---------- Lifecycle ----------

    def _finish(self) -> None:
        """
        Returns:
            None
        """
        self._timer.stop()
        self._animations.stop()
        self.close()
        self.finished.emit()

    def closeEvent(self, event) -> None:
        """
        Args:
            event (Any): Qt event object.
        Returns:
            None
        """
        self._timer.stop()
        self._animations.stop()
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------
class SplashCoordinator(QObject):
    """Coordinates the splash screen with progressive main-window loading."""

    def __init__(
        self,
        logo_path: Optional[str] = None,
        main_window_class: Optional[type] = None,
    ):
        """
        Args:
            logo_path (Optional[str]): The logo path.
            main_window_class (Optional[type]): The main window class.
        """
        super().__init__()
        self.splash = SplashScreen(logo_path=logo_path)
        self.main_window_class = main_window_class
        self.main_window = None
        self.progressive_loader = None
        self.splash.finished.connect(self._on_splash_finished)

    def start(self) -> None:
        """
        Returns:
            None
        """
        self.splash.show()

        if self.main_window_class is None:
            self.splash.update_progress(100, "Ready!")
            QTimer.singleShot(2000, self.splash.set_loading_complete)
            return

        try:
            from tools.progressive_main_window import ProgressiveMainWindow
        except ImportError:
            self.splash.update_progress(100, "Ready!")
            QTimer.singleShot(2000, self.splash.set_loading_complete)
            return

        self.progressive_loader = ProgressiveMainWindow()
        self.progressive_loader.progress_updated.connect(self.splash.update_progress)
        self.progressive_loader.loading_complete.connect(self._on_loading_complete)
        QTimer.singleShot(100, self.progressive_loader.start_loading)

    def _on_loading_complete(self) -> None:
        """
        Returns:
            None
        """
        if self.progressive_loader:
            self.main_window = self.progressive_loader.get_main_window()
        self.splash.set_loading_complete()

    def _on_splash_finished(self) -> None:
        """
        Returns:
            None
        """
        if self.main_window:
            self.main_window.show()
        else:
            QApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    coordinator = SplashCoordinator()
    coordinator.start()
    sys.exit(app.exec())