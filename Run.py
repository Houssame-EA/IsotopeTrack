import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from tools.splash_screen import SplashCoordinator
from mainwindow import MainWindow

if __name__ == "__main__":
    """
    Main application entry point.
    
    Creates QApplication instance, initializes MainWindow, and starts event loop.
    """
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.main_windows = []
    
    coordinator = SplashCoordinator(main_window_class=MainWindow)
    coordinator.start()
    
    sys.exit(app.exec())