"""Animated splash screen with particle effects and progressive loading integration."""
import sys
import random
import math
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QObject, Property, QPointF, QRectF, QSequentialAnimationGroup, QParallelAnimationGroup, Signal
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QPainterPath, QLinearGradient, QRadialGradient, QPen, QBrush

class AnimatedValue(QObject):
    """
    Wrapper class for animatable floating point values.
    """
    
    def __init__(self, initial_value=0.0):
        """
        Initialize animated value.
        
        Args:
            initial_value (float, optional): Starting value. Defaults to 0.0
            
        Returns:
            None
        """
        super().__init__()
        self._value = initial_value

    def get_value(self):
        """
        Get current value.
        
        Args:
            None
            
        Returns:
            float: Current value
        """
        return self._value

    def set_value(self, value):
        """
        Set value and trigger parent widget update.
        
        Args:
            value (float): New value
            
        Returns:
            None
        """
        self._value = value
        if hasattr(self, 'parent') and self.parent():
            self.parent().update()

    value = Property(float, get_value, set_value)

class Particle:
    """
    Animated particle that orbits around a center point with pulsing effects.
    """
    
    def __init__(self, center_x, center_y, orbit_radius):
        """
        Initialize a particle.
        
        Args:
            center_x (float): X coordinate of orbit center
            center_y (float): Y coordinate of orbit center
            orbit_radius (float): Base radius of particle orbit
            
        Returns:
            None
        """
        self.center_x = center_x
        self.center_y = center_y
        self.orbit_radius = orbit_radius + random.uniform(-20, 20)
        self.angle = random.uniform(0, 2 * math.pi)
        self.speed = random.uniform(0.005, 0.02)
        self.size = random.uniform(1.5, 4)
        self.opacity = random.uniform(0.3, 0.8)
        self.color_variant = random.choice([
            QColor(100, 200, 255),
            QColor(200, 100, 255),
            QColor(150, 255, 150),
            QColor(255, 200, 100)
        ])
        self.pulse_offset = random.uniform(0, 2 * math.pi)
        self.current_size = self.size
        self.current_opacity = self.opacity
        
    def update(self, time_factor):
        """
        Update particle position and appearance.
        
        Args:
            time_factor (float): Time-based animation factor
            
        Returns:
            None
        """
        self.angle += self.speed * time_factor
        if self.angle > 2 * math.pi:
            self.angle -= 2 * math.pi
            
        pulse = math.sin(time_factor * 0.05 + self.pulse_offset) * 0.3 + 0.7
        self.current_size = self.size * pulse
        self.current_opacity = self.opacity * pulse
        
    def get_position(self):
        """
        Calculate current particle position.
        
        Args:
            None
            
        Returns:
            QPointF: Current position in 2D space
        """
        x = self.center_x + self.orbit_radius * math.cos(self.angle)
        y = self.center_y + self.orbit_radius * math.sin(self.angle)
        return QPointF(x, y)

class EnhancedCircularSplashScreen(QWidget):
    """
    Animated circular splash screen with particle effects and progress tracking.
    """
    
    finished = Signal()
    
    def __init__(self, logo_path=None, app_name="IsotopeTrack", version="Version 1.0.0:Beta"):
        """
        Initialize the splash screen.
        
        Args:
            logo_path (str, optional): Path to logo image file
            app_name (str, optional): Application name to display
            version (str, optional): Version string to display
            
        Returns:
            None
        """
        super().__init__()
        self.app_name = app_name
        self.version = version
        self.logo_path = logo_path
        
        self.auto_close_enabled = False
        self.current_status = "Initializing..."
        
        self.setWindowTitle('sp-IsotopeTrack')
        self.setFixedSize(500, 500)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self._progress = 0
        self._glow_intensity = AnimatedValue(0.0)
        self._logo_scale = AnimatedValue(0.0)
        self._text_opacity = AnimatedValue(0.0)
        
        self._glow_intensity.parent = lambda: self
        self._logo_scale.parent = lambda: self
        self._text_opacity.parent = lambda: self
        
        self.center_x = self.width() // 2
        self.center_y = self.height() // 2
        self.progress_radius = 120
        self.inner_radius = 80
        
        self.particles = []
        self.init_particles()
        
        self.setup_ui()
        
        self.setup_animations()
        
        self.time_factor = 0
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_animation)
        self.update_timer.start(33)

    def init_particles(self):
        """
        Initialize particle system with multiple orbital rings.
        
        Args:
            None
            
        Returns:
            None
        """
        for orbit in [0.7, 0.85, 1.0, 1.15]:
            orbit_radius = self.progress_radius * orbit
            particle_count = int(12 * orbit)
            for _ in range(particle_count):
                self.particles.append(Particle(self.center_x, self.center_y, orbit_radius))

    def setup_animations(self):
        """
        Setup property animations for logo, text, and glow effects.
        
        Args:
            None
            
        Returns:
            None
        """
        self.animation_group = QSequentialAnimationGroup(self)
        
        logo_anim = QPropertyAnimation(self._logo_scale, b"value")
        logo_anim.setDuration(800)
        logo_anim.setStartValue(0.0)
        logo_anim.setEndValue(1.0)
        logo_anim.setEasingCurve(QEasingCurve.OutBack)
        
        text_anim = QPropertyAnimation(self._text_opacity, b"value")
        text_anim.setDuration(600)
        text_anim.setStartValue(0.0)
        text_anim.setEndValue(1.0)
        text_anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        glow_anim = QPropertyAnimation(self._glow_intensity, b"value")
        glow_anim.setDuration(1000)
        glow_anim.setStartValue(0.0)
        glow_anim.setEndValue(1.0)
        glow_anim.setEasingCurve(QEasingCurve.InOutSine)
        
        parallel_group = QParallelAnimationGroup()
        parallel_group.addAnimation(text_anim)
        parallel_group.addAnimation(glow_anim)
        
        self.animation_group.addAnimation(logo_anim)
        self.animation_group.addAnimation(parallel_group)
        
        self.animation_group.start()

    def setup_ui(self):
        """
        Setup UI elements including logo, app name, version, and status labels.
        
        Args:
            None
            
        Returns:
            None
        """
        self.logo_label = None
        if self.logo_path:
            try:
                pixmap = QPixmap(self.logo_path)
                if not pixmap.isNull():
                    self.logo_label = QLabel(self)
                    logo_size = 80
                    scaled_pixmap = pixmap.scaled(
                        logo_size, logo_size, 
                        Qt.KeepAspectRatio, 
                        Qt.SmoothTransformation
                    )
                    self.logo_label.setPixmap(scaled_pixmap)
                    self.logo_label.setGeometry(
                        self.center_x - logo_size // 2,
                        self.center_y - 60,
                        logo_size, logo_size
                    )
                    self.logo_label.setStyleSheet("background: transparent;")
            except Exception as e:
                print(f"Error loading logo: {e}")
                self.logo_label = None
        
        self.app_label = QLabel(self.app_name, self)
        self.app_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0); 
            font-size: 28px; 
            font-weight: bold;
            font-family: Arial, sans-serif;
            background: transparent;
        """)
        self.app_label.setAlignment(Qt.AlignCenter)
        self.app_label.setGeometry(self.center_x - 100, self.center_y + 30, 200, 40)
        
        self.version_label = QLabel(self.version, self)
        self.version_label.setStyleSheet("""
            color: rgba(204, 204, 204, 0); 
            font-size: 14px;
            font-family: Arial, sans-serif;
            background: transparent;
        """)
        self.version_label.setAlignment(Qt.AlignCenter)
        self.version_label.setGeometry(self.center_x - 75, self.center_y + 75, 150, 25)
        
        self.status_label = QLabel(self.current_status, self)
        self.status_label.setStyleSheet("""
            color: rgba(255, 255, 255, 180); 
            font-size: 12px;
            font-family: Arial, sans-serif;
            background: transparent;
        """)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setGeometry(self.center_x - 120, self.center_y + 140, 240, 25)

    def update_progress(self, progress, status_text=""):
        """
        Update progress bar and status text from external source.
        
        Args:
            progress (int): Progress percentage (0-100)
            status_text (str, optional): Status message to display
            
        Returns:
            None
        """
        self._progress = max(0, min(100, progress))
        if status_text:
            self.current_status = status_text
            self.status_label.setText(status_text)
        self.update()

    def set_loading_complete(self):
        """
        Mark loading as complete and initiate splash screen closure.
        
        Args:
            None
            
        Returns:
            None
        """
        self._progress = 100
        self.current_status = "Loading complete!"
        self.status_label.setText(self.current_status)
        self.update()
        
        QTimer.singleShot(500, self.finish_splash)

    def update_animation(self):
        """
        Update all animated elements including particles and UI components.
        
        Args:
            None
            
        Returns:
            None
        """
        self.time_factor += 1
        
        for particle in self.particles:
            particle.update(self.time_factor)
        
        if self.logo_label:
            scale = self._logo_scale.value
            if scale > 0:
                size = int(80 * scale)
                self.logo_label.resize(size, size)
                self.logo_label.move(
                    self.center_x - size // 2,
                    self.center_y - 60
                )
        
        opacity = self._text_opacity.value
        self.app_label.setStyleSheet(f"""
            color: rgba(255, 255, 255, {opacity}); 
            font-size: 28px; 
            font-weight: bold;
            font-family: Arial, sans-serif;
            background: transparent;
        """)
        self.version_label.setStyleSheet(f"""
            color: rgba(204, 204, 204, {opacity}); 
            font-size: 14px;
            font-family: Arial, sans-serif;
            background: transparent;
        """)
        
        if self.isVisible():
            self.update()

    def paintEvent(self, event):
        """
        Custom paint event for rendering animated graphics.
        
        Args:
            event (QPaintEvent): Paint event
            
        Returns:
            None
        """
        if not self.isVisible():
            return
            
        painter = QPainter(self)
        if not painter.isActive():
            return
            
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            
            center = QPointF(self.center_x, self.center_y)
            
            glow_intensity = self._glow_intensity.value
            if glow_intensity > 0:
                glow_gradient = QRadialGradient(center, self.progress_radius + 40)
                glow_gradient.setColorAt(0, QColor(100, 200, 255, int(50 * glow_intensity)))
                glow_gradient.setColorAt(0.7, QColor(200, 100, 255, int(30 * glow_intensity)))
                glow_gradient.setColorAt(1, QColor(0, 0, 0, 0))
                painter.setBrush(glow_gradient)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(center, self.progress_radius + 40, self.progress_radius + 40)
            
            bg_gradient = QRadialGradient(center, self.progress_radius)
            bg_gradient.setColorAt(0, QColor(45, 45, 55, 220))
            bg_gradient.setColorAt(0.8, QColor(30, 30, 40, 200))
            bg_gradient.setColorAt(1, QColor(20, 20, 30, 180))
            painter.setBrush(bg_gradient)
            painter.setPen(QPen(QColor(80, 80, 90, 150), 2))
            painter.drawEllipse(center, self.progress_radius, self.progress_radius)
            
            inner_gradient = QRadialGradient(center, self.inner_radius)
            inner_gradient.setColorAt(0, QColor(60, 60, 70, 180))
            inner_gradient.setColorAt(1, QColor(40, 40, 50, 200))
            painter.setBrush(inner_gradient)
            painter.setPen(QPen(QColor(100, 100, 110, 100), 1))
            painter.drawEllipse(center, self.inner_radius, self.inner_radius)
            
            painter.setPen(Qt.NoPen)
            for particle in self.particles:
                pos = particle.get_position()
                color = QColor(particle.color_variant)
                color.setAlphaF(particle.current_opacity)
                painter.setBrush(color)
                painter.drawEllipse(pos, particle.current_size, particle.current_size)
            
            if self._progress > 0:
                painter.setPen(QPen(QColor(60, 60, 70, 150), 8))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(center, self.progress_radius - 15, self.progress_radius - 15)
                
                rect = QRectF(center.x() - self.progress_radius + 15, 
                             center.y() - self.progress_radius + 15,
                             (self.progress_radius - 15) * 2, 
                             (self.progress_radius - 15) * 2)
                
                progress_path = QPainterPath()
                progress_path.arcMoveTo(rect, 90)
                progress_path.arcTo(rect, 90, -self._progress * 3.6)
                
                progress_gradient = QLinearGradient(0, 0, self.width(), self.height())
                progress_gradient.setColorAt(0, QColor(100, 200, 255, 255))
                progress_gradient.setColorAt(0.5, QColor(150, 150, 255, 255))
                progress_gradient.setColorAt(1, QColor(200, 100, 255, 255))
                
                painter.setPen(QPen(QBrush(progress_gradient), 8, Qt.SolidLine, Qt.RoundCap))
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(progress_path)
            
            if self._progress > 0:
                painter.setFont(QFont("Arial", 18, QFont.Bold))
                
                painter.setPen(QColor(0, 0, 0, 100))
                painter.drawText(QRectF(center.x() - 49, center.y() - 9, 100, 30), 
                               Qt.AlignCenter, f"{int(self._progress)}%")
                
                painter.setPen(QColor(255, 255, 255, 240))
                painter.drawText(QRectF(center.x() - 50, center.y() - 10, 100, 30), 
                               Qt.AlignCenter, f"{int(self._progress)}%")
                
        except Exception as e:
            print(f"Paint error: {e}")
        finally:
            painter.end()

    def finish_splash(self):
        """
        Finish splash screen animation and close.
        
        Args:
            None
            
        Returns:
            None
        """
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        if hasattr(self, 'animation_group'):
            self.animation_group.stop()
            
        self.close()
        self.finished.emit()

    def closeEvent(self, event):
        """
        Handle close event and cleanup.
        
        Args:
            event (QCloseEvent): Close event
            
        Returns:
            None
        """
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        if hasattr(self, 'animation_group'):
            self.animation_group.stop()
        super().closeEvent(event)

    def get_progress(self):
        """Get current progress value."""
        return self._progress

    def set_progress(self, value):
        """Set progress value and trigger update."""
        self._progress = value
        if self.isVisible():
            self.update()

    progress = Property(float, get_progress, set_progress)

class SplashCoordinator(QObject):
    """
    Coordinator for splash screen and main window progressive loading.
    """
    
    def __init__(self, logo_path=None, main_window_class=None):
        """
        Initialize the splash coordinator.
        
        Args:
            logo_path (str, optional): Path to logo image
            main_window_class (class, optional): Main window class to load
            
        Returns:
            None
        """
        super().__init__()
        self.splash = EnhancedCircularSplashScreen(
            logo_path=logo_path,
            app_name="IsotopeTrack",
            version="Version 1.0.0:Beta"
        )
        
        self.main_window_class = main_window_class
        self.main_window = None
        self.progressive_loader = None
        self.splash.finished.connect(self.on_splash_finished)

    def start(self):
        """
        Start the splash screen and loading process.
        
        Args:
            None
            
        Returns:
            None
        """
        self.splash.show()
        
        if self.main_window_class:
            self.start_progressive_loading()
        else:
            self.splash.update_progress(100, "Ready!")
            QTimer.singleShot(2000, self.splash.set_loading_complete)

    def start_progressive_loading(self):
        """
        Start progressive loading with real-time updates to splash screen.
        
        Args:
            None
            
        Returns:
            None
        """
        from tools.progressive_main_window import ProgressiveMainWindow
        
        self.progressive_loader = ProgressiveMainWindow()
        
        self.progressive_loader.progress_updated.connect(self.splash.update_progress)
        self.progressive_loader.loading_complete.connect(self.on_loading_complete)
        
        QTimer.singleShot(100, self.progressive_loader.start_loading)

    def on_loading_complete(self):
        """
        Called when main window loading is complete.
        
        Args:
            None
            
        Returns:
            None
        """
        if self.progressive_loader:
            self.main_window = self.progressive_loader.get_main_window()
        
        self.splash.set_loading_complete()

    def on_splash_finished(self):
        """
        Called when splash screen closes, shows main window or quits.
        
        Args:
            None
            
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