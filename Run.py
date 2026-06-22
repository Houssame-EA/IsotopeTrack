import sys
import os
from tools.cli_utils import get_argument_parser
import logging
_itk_log = logging.getLogger("IsotopeTrack.Run")

cli_parser = get_argument_parser()
if __name__ == '__main__':
    cli_parser.parse_args()


from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QEvent
from tools.splash_screen import SplashCoordinator
from mainwindow import MainWindow


class IsotopeTrackApplication(QApplication):
    """QApplication that handles the macOS 'open document' event.

    When a .itproj file is double-clicked in Finder while IsotopeTrack is already
    running, macOS delivers a QFileOpenEvent rather than a command-line argument.
    This routes that file to an open window — or queues it until one exists. A
    cold launch is handled separately by ``argv_emulation`` plus the CLI parser.
    """

    def __init__(self, argv):
        super().__init__(argv)
        self._pending_open_files = []

    def event(self, e):
        if e.type() == QEvent.Type.FileOpen:
            try:
                path = e.file()
            except Exception:
                path = ""
            if path:
                if not self._dispatch_open(path):
                    self._pending_open_files.append(path)
            return True
        return super().event(e)

    def _dispatch_open(self, path):
        """Load ``path`` into a visible window. Returns False if none exists yet."""
        windows = list(getattr(self, 'main_windows', []) or [])
        target = None
        for w in windows:
            try:
                if w.isVisible():
                    target = w
                    break
            except RuntimeError:
                continue
        if target is None and windows:
            target = windows[-1]
        if target is None:
            return False
        try:
            target.load_project(filepath=path)
            target.raise_()
            target.activateWindow()
        except Exception:
            _itk_log.exception("Could not open project file %s", path)
        return True  # handled (don't requeue a file that errored)

    def flush_pending_opens(self):
        """Load any open requests that arrived before a window existed."""
        pending, self._pending_open_files = self._pending_open_files, []
        for path in pending:
            self._dispatch_open(path)

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
    app = IsotopeTrackApplication(sys.argv)
    app.setAttribute(Qt.AA_DontShowIconsInMenus, False)
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