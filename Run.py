import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from tools.splash_screen import SplashCoordinator
from mainwindow import MainWindow


def resource_path(relative_path):
    """Get absolute path to resource — works for dev and PyInstaller.
    Args:
        relative_path (Any): The relative path.
    Returns:
        object: Result of the operation.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


if __name__ == "__main__":
    """
    Main application entry point.

    Creates QApplication instance, initializes MainWindow, and starts event loop.
    """
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    app.main_windows = []

    app.setWindowIcon(QIcon(resource_path("images/isotrack_icon.ico")))

    coordinator = SplashCoordinator(main_window_class=MainWindow)
    coordinator.start()

    exit_code = app.exec()

    for w in app.main_windows:
        try:
            w.close()
        except Exception:
            pass
    app.main_windows.clear()