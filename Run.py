import sys
import os
from tools.cli_utils import get_argument_parser
import logging
_itk_log = logging.getLogger("IsotopeTrack.Run")


# Early parsing to avoid PySide6 import load time
cli_parser = get_argument_parser()
if __name__ == '__main__':
    cli_parser.parse_args()


from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from tools.splash_screen import SplashCoordinator
from mainwindow import MainWindow

def resource_path(relative_path):
    """Get absolute path to resource — works for dev and PyInstaller."""
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

    coordinator = SplashCoordinator(main_window_class=MainWindow, cli_parser=cli_parser)
    coordinator.start()

    exit_code = app.exec()

    for w in app.main_windows:
        try:
            w.close()
        except Exception:
            _itk_log.exception("Handled exception in <module>")
    app.main_windows.clear()

    logging.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code if isinstance(exit_code, int) else 0)