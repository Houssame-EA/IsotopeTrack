import sys
from PySide6.QtWidgets import QApplication
from tools.splash_screen import SplashCoordinator
from mainwindow import MainWindow

if __name__ == "__main__":
    """
    Main application entry point.
    
    Creates QApplication instance, initializes MainWindow, and starts event loop.
    """
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    app.main_windows = []

    coordinator = SplashCoordinator(main_window_class=MainWindow)
    coordinator.start()

    exit_code = app.exec()
    
    for w in app.main_windows:
        try:
            w.close()
        except Exception:
            pass
    app.main_windows.clear()