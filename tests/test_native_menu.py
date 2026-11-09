"""System menus on macOS: how Qt menus are read, shown and their choice run."""

from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QMenu, QSpinBox, QWidgetAction

from utils import native_menu as nm


@pytest.fixture(scope="module")
def app():
    """The running QApplication, created if needed."""
    return QApplication.instance() or QApplication([])


class FakeBackend:
    """Stands in for the macOS menu: records what it was shown and picks by text."""

    def __init__(self, pick=None):
        self.pick = pick
        self.shown = None
        self.pos = None
        self.during = None

    def popup(self, entries, pos):
        """Remember the entries and return the action whose text matches ``pick``."""
        self.shown, self.pos = entries, pos
        if self.during:
            self.during()

        def find(items):
            for e in items:
                if e.kind == "action" and e.text == self.pick:
                    return e.action
                if e.kind == "submenu":
                    found = find(e.children)
                    if found:
                        return found
            return None
        return find(entries) if self.pick else None


@pytest.fixture
def backend(app):
    """Install system menus with a fake backend, and remove them afterwards."""
    b = FakeBackend()
    nm.uninstall_native_menus()
    assert nm.install_native_menus(app, backend=b)
    yield b
    nm.uninstall_native_menus()


def sample_menu():
    """A menu with every kind of row the application uses."""
    menu = QMenu()
    copy = menu.addAction("&Copy\tCtrl+C")
    copy.setShortcut(QKeySequence("Ctrl+C"))
    menu.addSeparator()
    menu.addSeparator()
    grid = menu.addAction("Show grid")
    grid.setCheckable(True)
    grid.setChecked(True)
    off = menu.addAction("Disabled thing")
    off.setEnabled(False)
    hidden = menu.addAction("Hidden")
    hidden.setVisible(False)
    menu.addSection("Export")
    sub = menu.addMenu("Save &as")
    sub.addAction("PNG")
    sub.addAction("Fish && Chips")
    menu.addSeparator()
    return menu


def test_text_and_shortcuts_are_cleaned():
    """Mnemonics go, doubled ampersands stay single, tab shortcuts are split off."""
    assert nm.clean_text("&Copy\tCtrl+C") == ("Copy", "Ctrl+C")
    assert nm.clean_text("Fish && Chips") == ("Fish & Chips", "")
    assert nm.clean_text("  Add Note") == ("Add Note", "")
    assert nm.key_equivalent("Ctrl+Shift+C") == ("c", nm.MODIFIERS["ctrl"] | nm.MODIFIERS["shift"])
    assert nm.key_equivalent("F12") == ("", 0)
    assert nm.key_equivalent("") == ("", 0)


def test_menu_is_read_as_it_appears(app):
    """Hidden rows skipped, doubled and trailing separators dropped, sections become titles."""
    entries = nm.describe(sample_menu())
    kinds = [(e.kind, e.text) for e in entries]
    assert kinds == [("action", "Copy"), ("separator", ""), ("action", "Show grid"),
                     ("action", "Disabled thing"), ("header", "Export"), ("submenu", "Save as")]
    assert entries[0].shortcut == "Ctrl+C"
    assert entries[2].checkable and entries[2].checked
    assert not entries[3].enabled
    assert [c.text for c in entries[5].children] == ["PNG", "Fish & Chips"]


def test_icons_are_kept(app):
    """An action's icon is read and turns into PNG bytes for the system menu."""
    from PySide6.QtGui import QColor, QIcon, QPixmap
    pm = QPixmap(32, 32)
    pm.fill(QColor("red"))
    menu = QMenu()
    menu.addAction(QIcon(pm), "  Red")
    entry = nm.describe(menu)[0]
    assert entry.text == "Red" and entry.icon is not None
    assert nm.icon_png(entry.icon).startswith(b"\x89PNG")


def test_submenu_added_without_a_parent_is_not_shown_twice(app, backend):
    """A submenu with no parent widget still opens inside the system menu only."""
    menu = QMenu()
    sub = QMenu("Add")
    pick = sub.addAction("Node")
    menu.addMenu(sub)
    backend.pick = "Node"
    assert menu.exec(QPoint(1, 1)) is pick
    assert not sub.isVisible() and not menu.isVisible()


def test_submenus_survive_their_actions_being_released(app):
    """A submenu read from its action stays usable after the action is dropped."""
    def build():
        m = QMenu()
        m.addMenu("Sub").addAction("PNG")
        return m
    menu = build()
    sub = next(nm.submenu(a) for a in menu.actions() if nm.submenu(a) is not None)
    import gc
    gc.collect()
    assert sub.actions()[0].text() == "PNG"
    assert nm.supported(menu)
    assert [c.text for c in nm.describe(menu)[0].children] == ["PNG"]
    assert sub.actions()[0].text() == "PNG"


def test_menus_filled_on_about_to_show_are_not_empty(app):
    """A menu that adds its actions just before opening shows them."""
    menu = QMenu()
    menu.aboutToShow.connect(lambda: menu.addAction("Late") if not menu.actions() else None)
    assert [e.text for e in nm.describe(menu)] == ["Late"]


def test_widget_menus_stay_qt_menus(app):
    """A menu holding a widget cannot be a system menu, nor can one with such a submenu."""
    menu = QMenu()
    menu.addAction("Plain")
    assert nm.supported(menu)
    sub = menu.addMenu("Range")
    wa = QWidgetAction(sub)
    wa.setDefaultWidget(QSpinBox())
    sub.addAction(wa)
    assert not nm.supported(menu)


def test_choice_triggers_the_action_and_the_menu_signals(app, backend):
    """exec returns the choice, which runs, toggles and emits triggered and aboutToHide."""
    menu = sample_menu()
    grid = next(a for a in menu.actions() if a.text() == "Show grid")
    seen = []
    menu.triggered.connect(lambda a: seen.append(("menu", a.text())))
    grid.triggered.connect(lambda checked: seen.append(("grid", checked)))
    hidden = []
    menu.aboutToHide.connect(lambda: hidden.append(True))
    backend.pick = "Show grid"
    chosen = menu.exec(QPoint(120, 80))
    assert chosen is grid and not grid.isChecked()
    assert ("grid", False) in seen and ("menu", "Show grid") in seen
    assert hidden == [True]
    assert not menu.isVisible() and menu.windowOpacity() == 1.0
    assert backend.shown[0].text == "Copy"


def test_submenu_choice_is_returned_and_reaches_both_menus(app, backend):
    """An item in a submenu is returned by exec and emits triggered on both menus."""
    menu = sample_menu()
    sub = next(nm.submenu(a) for a in menu.actions() if nm.submenu(a) is not None)
    png = sub.actions()[0]
    seen = []
    menu.triggered.connect(lambda a: seen.append(("root", a.text())))
    sub.triggered.connect(lambda a: seen.append(("sub", a.text())))
    backend.pick = "PNG"
    assert menu.exec(QPoint(0, 0)) is png
    assert seen == [("sub", "PNG"), ("root", "PNG")]
    assert png not in menu.actions() and png in sub.actions()


def test_qt_closing_its_menu_meanwhile_does_not_lose_the_choice(app, backend):
    """A click in the system menu makes Qt close its own; exec still returns the choice."""
    menu = QMenu()
    act = menu.addAction("Show sample info")
    other = menu.addAction("Remove sample")
    ran = []
    act.triggered.connect(lambda *_: ran.append("info"))
    other.triggered.connect(lambda *_: ran.append("remove"))
    backend.pick = "Show sample info"
    backend.during = menu.close
    assert menu.exec(QPoint(5, 5)) is act
    assert ran == ["info"] and not menu.isVisible()


def test_the_click_that_opened_the_menu_is_released(app, backend):
    """After the menu, Qt no longer counts the right button as held, and no widget sees a click."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QWidget

    class Plot(QWidget):
        def __init__(self):
            super().__init__()
            self.releases = 0

        def mouseReleaseEvent(self, event):
            self.releases += 1

    plot = Plot()
    plot.resize(200, 200)
    plot.show()
    QTest.qWaitForWindowExposed(plot)
    QTest.mousePress(plot.windowHandle(), Qt.RightButton, Qt.NoModifier, QPoint(50, 50))
    assert QGuiApplication.mouseButtons() & Qt.RightButton
    menu = QMenu()
    act = menu.addAction("Zoom out")
    backend.pick = "Zoom out"
    assert menu.exec(QPoint(60, 60)) is act
    assert QGuiApplication.mouseButtons() == Qt.NoButton
    assert plot.releases == 0
    plot.close()


def test_dismissed_menu_returns_none(app, backend):
    """Closing the menu without choosing returns None and runs nothing."""
    menu = QMenu()
    act = menu.addAction("Delete everything")
    ran = []
    act.triggered.connect(lambda *_: ran.append(True))
    backend.pick = None
    assert menu.exec(QPoint(5, 5)) is None
    assert ran == [] and not menu.isVisible()


def test_popup_runs_the_choice_too(app, backend):
    """popup() shows the system menu and runs the chosen action."""
    menu = QMenu()
    act = menu.addAction("Reset layout")
    ran = []
    act.triggered.connect(lambda *_: ran.append(True))
    backend.pick = "Reset layout"
    menu.popup(QPoint(10, 10))
    deadline = time.monotonic() + 3
    while menu.isVisible() and time.monotonic() < deadline:
        app.processEvents()
    assert ran == [True] and not menu.isVisible()


def test_static_exec_is_shown_as_a_system_menu(app, backend):
    """Qt's static QMenu.exec(actions, pos) form goes through the system menu too."""
    a, b = QAction("One"), QAction("Two")
    backend.pick = "Two"
    assert QMenu.exec([a, b], QPoint(3, 3)) is b


def test_widget_and_opted_out_menus_are_left_to_qt(app, backend):
    """Menus holding a widget, or marked to keep Qt, are not converted."""
    catcher = nm._INSTALLED["catcher"]
    plain = QMenu()
    plain.addAction("Plain")
    assert catcher.wants(plain)
    kept = QMenu()
    kept.addAction("Kept")
    kept.setProperty(nm.KEEP_QT, True)
    assert not catcher.wants(kept)
    boxed = QMenu()
    wa = QWidgetAction(boxed)
    wa.setDefaultWidget(QSpinBox())
    boxed.addAction(wa)
    assert not catcher.wants(boxed)
    sub = plain.addMenu("Sub")
    assert not catcher.wants(sub)


def test_title_bars_and_menus_follow_the_theme(app):
    """The app's dark or light choice is applied, None when it follows macOS."""
    from PySide6.QtCore import QObject, Signal

    class Manager(QObject):
        themeChanged = Signal(str)
        follow_system = False
        is_dark = True

    class Backend:
        def __init__(self):
            self.calls = []

        def set_appearance(self, dark):
            self.calls.append(dark)

    manager, backend = Manager(), Backend()
    assert nm.follow_theme(backend, manager)
    manager.is_dark = False
    manager.themeChanged.emit("light")
    manager.follow_system = True
    manager.themeChanged.emit("system")
    assert backend.calls == [True, False, None]
    nm.unfollow_theme()
    manager.themeChanged.emit("again")
    assert backend.calls == [True, False, None]
    assert not nm.follow_theme(FakeBackend(), manager)


def test_nothing_is_installed_off_macos_without_a_backend(app, monkeypatch):
    """On other platforms, or with the opt-out set, Qt keeps its menus."""
    nm.uninstall_native_menus()
    monkeypatch.setattr(nm.sys, "platform", "linux")
    assert nm.install_native_menus(app) is False
    assert not nm._INSTALLED
    monkeypatch.setattr(nm.sys, "platform", "darwin")
    monkeypatch.setenv(nm.OPT_OUT, "1")
    assert nm.install_native_menus(app) is False
    assert not nm._INSTALLED


def test_menu_rebuilt_while_open_is_closed_without_a_crash(app):
    """A menu cleared while the system menu is open (its chosen action deleted) just closes."""

    class Rebuilding(FakeBackend):
        """Clears the Qt menu while the system menu is up, as a panel refreshing it would."""

        def popup(self, entries, pos):
            chosen = super().popup(entries, pos)
            self.menu.clear()
            return chosen

    b = Rebuilding()
    nm.uninstall_native_menus()
    assert nm.install_native_menus(app, backend=b)
    try:
        menu = QMenu()
        menu.addAction("Node 1")
        b.menu = menu
        b.pick = "Node 1"
        assert menu.exec(QPoint(5, 5)) is None
        assert not menu.isVisible()
    finally:
        nm.uninstall_native_menus()
