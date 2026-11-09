"""Double-clicks on the merged macOS title strip of a glass window.

The glass window's content runs up under the title bar, so macOS never sees
a double-click there. The application hands it back: a double-click on the
strip, away from any control, runs the system's title-bar action.
"""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from tools import window_glass


def glass_window():
    """A shown window marked as having a merged title strip, with a label and a button on it."""
    QApplication.instance() or QApplication([])
    win = QWidget()
    win.resize(400, 300)
    win._glass_unified = True
    label = QLabel("sidebar", win)
    label.setGeometry(0, 0, 200, 40)
    button = QPushButton("x", win)
    button.setGeometry(300, 0, 60, 24)
    win.show()
    QApplication.processEvents()
    return win, label, button


def test_double_click_on_the_title_strip_runs_the_title_bar_action(monkeypatch):
    """A double-click on plain content in the top strip zooms the window."""
    calls = []
    monkeypatch.setattr(window_glass, "titlebar_double_click", lambda w: calls.append(w))
    win, label, _button = glass_window()
    window_glass._install_titlebar_filter()
    QTest.mouseDClick(label, Qt.MouseButton.LeftButton, pos=QPoint(50, 10))
    win.close()
    assert calls == [win]


def test_controls_and_the_rest_of_the_window_keep_their_double_click(monkeypatch):
    """Buttons on the strip, and everything below it, are left alone."""
    calls = []
    monkeypatch.setattr(window_glass, "titlebar_double_click", lambda w: calls.append(w))
    win, label, button = glass_window()
    window_glass._install_titlebar_filter()
    QTest.mouseDClick(button, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    QTest.mouseDClick(label, Qt.MouseButton.LeftButton, pos=QPoint(50, 35))
    win.close()
    assert calls == []


def test_windows_without_a_merged_title_strip_are_untouched():
    """A window with the normal system title bar has no strip to watch."""
    QApplication.instance() or QApplication([])
    win = QWidget()
    assert not window_glass.in_titlebar(win, win.mapToGlobal(QPoint(10, 5)))
