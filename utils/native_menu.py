"""System right-click menus on macOS.

Qt draws its pop-up menus itself, and the application's style sheet restyles
them, so on a Mac they do not look like the menus of other applications.
:func:`install_native_menus` makes every pop-up menu, from ``QMenu.exec``
or ``QMenu.popup``, show the system menu instead (``NSMenu``, through PyObjC): the same items,
shortcuts, check marks, disabled items, separators, section titles and
submenus, with the system's look, blur and dark mode. Choosing an item
triggers the same ``QAction``, so nothing else in the application changes.

A menu is shown by Qt as before when

* the platform is not macOS, or PyObjC is not installed;
* the menu holds a widget (a ``QWidgetAction`` with a widget, such as the
  range boxes of pyqtgraph's plot menu), which a system menu cannot show;
* the menu has the property ``itkQtMenu`` set to ``True``; or
* the environment variable ``ITK_QT_MENUS`` is set, to compare the two.

The menu is read into plain :class:`Entry` objects by :func:`describe`, so
the translation can be checked on any platform; only :class:`AppKitBackend`
needs macOS.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field

from PySide6.QtCore import QBuffer, QEvent, QIODevice, QObject, QPoint, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeyEvent, QKeySequence, QWindow
from PySide6.QtWidgets import QApplication, QMenu, QMenuBar, QWidgetAction

_log = logging.getLogger("IsotopeTrack.native_menu")

OPT_OUT = "ITK_QT_MENUS"
"""Environment variable that keeps Qt's own menus when set."""

DEBUG = "ITK_MENU_DEBUG"
"""Environment variable that logs every step of every system menu when set."""

NO_RESET = "ITK_MENU_NO_RESET"
"""Environment variable that skips clearing the mouse buttons after a menu."""

NO_THEME = "ITK_MENU_NO_THEME"
"""Environment variable that leaves title bars and menus to macOS."""


def trace(message: str, *args) -> None:
    """Log one step of a system menu when :data:`DEBUG` is set."""
    if os.environ.get(DEBUG):
        _log.warning("[menu] " + message, *args)


KEEP_QT = "itkQtMenu"
"""Menu property that keeps one menu a Qt menu when set to ``True``."""


@dataclass
class Entry:
    """One row of a menu, read from Qt.

    Attributes:
        kind: ``"action"``, ``"submenu"``, ``"separator"`` or ``"header"``.
        text: Text shown, with Qt's ``&`` mnemonics removed.
        enabled: Whether it can be chosen.
        checkable: Whether it shows a check mark when checked.
        checked: Whether it is checked.
        shortcut: Its first shortcut in portable text, e.g. ``"Ctrl+C"``.
        icon: Its ``QIcon``, or ``None``.
        action: The ``QAction`` it triggers.
        menu: The ``QMenu`` it opens, for a submenu.
        children: The submenu's entries.
    """

    kind: str
    text: str = ""
    enabled: bool = True
    checkable: bool = False
    checked: bool = False
    shortcut: str = ""
    icon: object = None
    action: object = None
    menu: object = None
    children: list = field(default_factory=list)


def clean_text(text: str) -> tuple[str, str]:
    """Remove ``&`` mnemonics and split off a shortcut written after a tab.

    ``"&Copy\\tCtrl+C"`` → ``("Copy", "Ctrl+C")``; ``"Fish && Chips"`` keeps one ``&``.
    """
    label, _, tail = (text or "").partition("\t")
    out, i = [], 0
    while i < len(label):
        ch = label[i]
        if ch == "&":
            if i + 1 < len(label) and label[i + 1] == "&":
                out.append("&")
                i += 2
                continue
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out).strip(), tail.strip()


def submenu(action):
    """The submenu *action* opens, or ``None``.

    PySide6 6.9 invalidates a submenu's Python object when the object of the
    action that returned it is released, so the action is kept alive with
    its submenu.
    """
    sub = action.menu()
    if sub is not None:
        try:
            sub._itk_menu_action = action
        except Exception:
            _log.debug("could not keep the submenu's action", exc_info=True)
    return sub


def supported(menu: QMenu) -> bool:
    """Whether a system menu can show *menu* and all its submenus."""
    for action in menu.actions():
        if isinstance(action, QWidgetAction) and action.defaultWidget() is not None:
            return False
        sub = submenu(action)
        if sub is not None and not supported(sub):
            return False
    return True


def describe(menu: QMenu, show: bool = True) -> list[Entry]:
    """Read a Qt menu into entries, as it would appear now.

    Each submenu's ``aboutToShow`` is emitted first, because menus that fill
    themselves just before they open would otherwise come out empty.

    Args:
        menu: The menu to read.
        show: Emit ``aboutToShow`` on *menu* itself too; Qt has already done
            so for a menu it is opening.

    Returns:
        The visible entries, in order, with no leading, trailing or doubled
        separators.
    """
    if show:
        try:
            menu.aboutToShow.emit()
        except Exception:
            _log.debug("aboutToShow failed", exc_info=True)
    entries: list[Entry] = []
    for action in menu.actions():
        if not action.isVisible():
            continue
        text, written = clean_text(action.text())
        if action.isSeparator():
            entries.append(Entry("header", text, enabled=False) if text else Entry("separator"))
            continue
        sub = submenu(action)
        seq = action.shortcut()
        shortcut = seq.toString(QKeySequence.PortableText) if not seq.isEmpty() else written
        if sub is not None:
            icon = action.icon() if not action.icon().isNull() else sub.icon()
            entries.append(Entry("submenu", text or clean_text(sub.title())[0],
                                 enabled=action.isEnabled() and sub.isEnabled(),
                                 icon=None if icon.isNull() else icon,
                                 action=action, menu=sub, children=describe(sub)))
            continue
        icon = action.icon()
        entries.append(Entry("action", text, enabled=action.isEnabled(),
                             checkable=action.isCheckable(), checked=action.isChecked(),
                             shortcut=shortcut, icon=None if icon.isNull() else icon,
                             action=action))
    tidy: list[Entry] = []
    for e in entries:
        if e.kind == "separator" and (not tidy or tidy[-1].kind == "separator"):
            continue
        tidy.append(e)
    while tidy and tidy[-1].kind == "separator":
        tidy.pop()
    return tidy


def owners(action, root: QMenu) -> list[QMenu]:
    """The menus from *root* down to the one holding *action*, outermost first."""
    def walk(menu, path):
        for a in menu.actions():
            if a is action:
                return path + [menu]
            sub = submenu(a)
            if sub is not None:
                found = walk(sub, path + [menu])
                if found:
                    return found
        return None
    return walk(root, []) or [root]


MODIFIERS = {"ctrl": 1 << 20, "meta": 1 << 18, "alt": 1 << 19, "shift": 1 << 17}
"""Qt modifier names to macOS modifier flags; Qt's Ctrl is the Command key on a Mac."""


def key_equivalent(shortcut: str) -> tuple[str, int]:
    """A shortcut as a macOS key equivalent: ``"Ctrl+Shift+C"`` → ``("c", ⌘⇧)``.

    Only single-character keys are shown; others give ``("", 0)``.
    """
    if not shortcut:
        return "", 0
    first = shortcut.split(",")[0].strip()
    parts = first.split("+")
    key = parts[-1] if parts[-1] else "+"
    if len(key) != 1:
        return "", 0
    mask = 0
    for p in parts[:-1]:
        mask |= MODIFIERS.get(p.strip().lower(), 0)
    return key.lower(), mask


ICON_POINTS = 16
"""Size of menu icons, in points, as in the system's own menus."""


def icon_png(icon, points: int = ICON_POINTS) -> bytes:
    """A ``QIcon`` as PNG bytes at twice *points*, sharp on Retina screens."""
    pixmap = icon.pixmap(points * 2, points * 2)
    if pixmap.isNull():
        return b""
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    pixmap.save(buf, "PNG")
    return bytes(buf.data())


class AppKitBackend:
    """Shows entries as a macOS system menu and returns the chosen ``QAction``."""

    def __init__(self):
        import AppKit
        import Foundation
        import objc
        self.AppKit, self.Foundation, self.objc = AppKit, Foundation, objc
        self._target = _target_class(objc, Foundation)

    def popup(self, entries: list[Entry], pos: QPoint):
        """Show the menu at global position *pos*; block until it closes."""
        AppKit = self.AppKit
        registry: list = []
        target = self._target.alloc().init()
        menu = self._build(entries, target, registry)
        screens = AppKit.NSScreen.screens()
        height = screens[0].frame().size.height if screens and len(screens) else 0
        point = self.Foundation.NSMakePoint(float(pos.x()), float(height - pos.y()))
        _OPEN["registry"], _OPEN["chosen"] = registry, None
        try:
            menu.popUpMenuPositioningItem_atLocation_inView_(None, point, None)
            return _OPEN["chosen"]
        finally:
            _OPEN["registry"], _OPEN["chosen"] = [], None
            self.reset_mouse_buttons()

    def reset_mouse_buttons(self):
        """Tell Qt's windows that no mouse button is held any more.

        A system menu swallows the mouse release that ends the click which
        opened it, so Qt would go on believing the button is down: plots
        kept zooming and the canvas kept drawing a selection rectangle.
        Qt's own system menus clear this the same way.

        The method is called directly rather than through
        ``performSelector:``, which would read its empty result as an object
        and crash.
        """
        if os.environ.get(NO_RESET):
            trace("reset: skipped")
            return
        for window in QGuiApplication.topLevelWindows():
            if not isinstance(window, QWindow) or not window.isVisible():
                continue
            try:
                view = self.objc.objc_object(c_void_p=int(window.winId()))
                if view.respondsToSelector_("resetMouseButtons"):
                    view.resetMouseButtons()
                    trace("reset: %s", window.title() or type(window).__name__)
            except Exception:
                _log.debug("could not reset mouse buttons", exc_info=True)

    def set_appearance(self, dark):
        """Make title bars and system menus dark, light, or follow macOS.

        Args:
            dark: ``True`` or ``False`` for the application's theme, or
                ``None`` to follow the system setting.
        """
        AppKit = self.AppKit
        app = AppKit.NSApplication.sharedApplication()
        if dark is None:
            app.setAppearance_(None)
            return
        name = AppKit.NSAppearanceNameDarkAqua if dark else AppKit.NSAppearanceNameAqua
        app.setAppearance_(AppKit.NSAppearance.appearanceNamed_(name))

    def _image(self, icon):
        """A 16-point ``NSImage`` of a ``QIcon``, or ``None``."""
        if icon is None:
            return None
        try:
            data = icon_png(icon, ICON_POINTS)
            if not data:
                return None
            image = self.AppKit.NSImage.alloc().initWithData_(
                self.Foundation.NSData.dataWithBytes_length_(data, len(data)))
            image.setSize_(self.Foundation.NSMakeSize(ICON_POINTS, ICON_POINTS))
            return image
        except Exception:
            _log.debug("icon conversion failed", exc_info=True)
            return None

    def _build(self, entries, target, registry):
        AppKit = self.AppKit
        menu = AppKit.NSMenu.alloc().initWithTitle_("")
        menu.setAutoenablesItems_(False)
        for e in entries:
            if e.kind == "separator":
                menu.addItem_(AppKit.NSMenuItem.separatorItem())
                continue
            if e.kind == "header":
                item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(e.text, None, "")
                item.setEnabled_(False)
                menu.addItem_(item)
                continue
            key, mask = key_equivalent(e.shortcut) if e.kind == "action" else ("", 0)
            selector = "fire:" if e.kind == "action" else None
            item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(e.text, selector, key)
            if key:
                item.setKeyEquivalentModifierMask_(mask)
            item.setEnabled_(bool(e.enabled))
            image = self._image(e.icon)
            if image is not None:
                item.setImage_(image)
            if e.kind == "action":
                item.setTarget_(target)
                item.setTag_(len(registry))
                registry.append(e.action)
                if e.checkable:
                    on = getattr(AppKit, "NSControlStateValueOn", getattr(AppKit, "NSOnState", 1))
                    off = getattr(AppKit, "NSControlStateValueOff", getattr(AppKit, "NSOffState", 0))
                    item.setState_(on if e.checked else off)
            else:
                item.setSubmenu_(self._build(e.children, target, registry))
            menu.addItem_(item)
        return menu


_TARGET = None

_OPEN: dict = {"registry": [], "chosen": None}
"""The system menu now open: its actions by item tag, and the one chosen.

A system menu is modal, so only one is ever open at a time.
"""


def _target_class(objc, Foundation):
    """The Objective-C class receiving the chosen item, defined once per process."""
    global _TARGET
    if _TARGET is None:
        class ITKNativeMenuTarget(Foundation.NSObject):
            """Receives the system menu's choice and records its action."""

            @objc.typedSelector(b"v@:@")
            def fire_(self, sender):
                """Called by the chosen menu item; records its action by tag."""
                tag = int(sender.tag())
                registry = _OPEN.get("registry") or []
                if 0 <= tag < len(registry):
                    _OPEN["chosen"] = registry[tag]

        _TARGET = ITKNativeMenuTarget
    return _TARGET


class NativeMenus(QObject):
    """Shows each Qt pop-up menu as a system menu as soon as Qt opens it.

    ``QMenu.exec`` cannot be replaced from Python in PySide6, so the menus are
    caught when they are shown instead: the Qt menu is made transparent, the
    system menu is shown at the same place, and the choice is handed back to
    the Qt menu, which then runs it itself. ``exec`` therefore returns the
    chosen action, and ``triggered``, check marks and ``aboutToHide`` behave
    exactly as with Qt's own menus.
    """

    GUARDED = (QEvent.Close, QEvent.MouseButtonPress, QEvent.MouseButtonRelease,
               QEvent.MouseButtonDblClick, QEvent.MouseMove)
    """Events kept from the transparent Qt menu while the system menu is open.

    Clicking in the system menu counts, for Qt, as a click outside its own
    menu, which would close it before the choice could be handed back.
    """

    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.backend = backend
        self.busy = False
        self.current = None

    def wants(self, menu) -> bool:
        """Whether *menu* should be shown as a system menu."""
        if self.busy or not isinstance(menu, QMenu) or not menu.isWindow():
            return False
        if menu.property(KEEP_QT):
            return False
        if isinstance(menu.parentWidget(), (QMenu, QMenuBar)):
            return False
        active = QApplication.activePopupWidget()
        if isinstance(active, QMenu) and active is not menu and active.isVisible():
            return False
        return supported(menu)

    def eventFilter(self, obj, event):
        """Catch a top-level menu as it is shown, and keep it open meanwhile."""
        if self.current is not None and obj is self.current and event.type() in self.GUARDED:
            if event.type() == QEvent.Close:
                event.ignore()
                trace("kept the Qt menu open")
            return True
        if event.type() == QEvent.Show and self.wants(obj):
            trace("caught %s at %s", type(obj).__name__, obj.pos())
            self.current = obj
            self.busy = True
            obj.setWindowOpacity(0.0)
            QTimer.singleShot(0, lambda m=obj: self.run(m))
        return False

    def run(self, menu: QMenu) -> None:
        """Show the system menu for *menu* and hand back the choice."""
        chosen = None
        try:
            trace("run: Qt menu visible=%s", menu.isVisible())
            if menu.isVisible():
                entries = describe(menu, show=False)
                trace("run: %d entries, showing at %s", len(entries), menu.pos())
                if entries:
                    chosen = self.backend.popup(entries, menu.pos())
                if chosen is not None and not alive(chosen):
                    trace("run: the chosen action was deleted while the menu was open")
                    chosen = None
                trace("run: system menu closed, chosen=%r",
                      chosen.text() if chosen is not None else None)
        except Exception:
            _log.exception("System menu failed")
        finally:
            release_buttons(menu)
            self.current = None
            try:
                deliver(menu, chosen)
            finally:
                self.busy = False
                trace("run: done, Qt menu visible=%s, buttons=%s",
                      menu.isVisible(), QGuiApplication.mouseButtons())


def alive(obj) -> bool:
    """Whether a Qt object still exists on the C++ side.

    A menu can be rebuilt while the system menu is open, which deletes the
    action that was then chosen.
    """
    try:
        from shiboken6 import isValid
        return bool(isValid(obj))
    except Exception:
        return False


def release_buttons(menu: QMenu) -> None:
    """Let Qt know the mouse buttons are up again, without anyone seeing a click.

    The system menu swallows the release of the click that opened it, so Qt
    still counts the button as held, and the next click in a plot or the
    canvas is read as a drag with two buttons. The release is sent through
    Qt's window system to the transparent menu, which is still open and
    keeps it to itself, exactly as Qt's own menu would have done.
    """
    held = QGuiApplication.mouseButtons()
    window = menu.windowHandle() if menu.isVisible() else None
    if held == Qt.NoButton or not isinstance(window, QWindow):
        return
    try:
        from PySide6.QtTest import QTest
    except Exception:
        _log.debug("QtTest is not available", exc_info=True)
        return
    for button in (Qt.LeftButton, Qt.RightButton, Qt.MiddleButton):
        if held & button:
            QTest.mouseRelease(window, button, Qt.NoModifier, QPoint(1, 1))
    trace("released %s, buttons now %s", held, QGuiApplication.mouseButtons())


def deliver(menu: QMenu, chosen) -> None:
    """Hand the choice to the Qt menu, which runs it and closes.

    The submenus leading to the chosen action are opened, transparent, and
    the action is activated from the menu holding it, as if clicked there.
    Qt therefore returns it from ``exec`` and emits ``triggered`` on every
    menu holding it, exactly as with its own menus.
    """
    chain = [menu]
    try:
        if chosen is None or not alive(chosen) or not chosen.isEnabled():
            menu.close()
            return
        if not menu.isVisible():
            trace("deliver: Qt menu already closed, triggering %r directly", chosen.text())
            chosen.trigger()
            return
        path = owners(chosen, menu)
        for parent, child in zip(path, path[1:]):
            child.setWindowOpacity(0.0)
            chain.append(child)
            parent.setActiveAction(child.menuAction())
            if not child.isVisible():
                child.popup(parent.mapToGlobal(parent.actionGeometry(child.menuAction()).topRight()))
        holder = chain[-1]
        holder.setActiveAction(chosen)
        trace("deliver: %d menus open, active=%r", len(chain),
              holder.activeAction().text() if holder.activeAction() else None)
        QApplication.sendEvent(holder, QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
        trace("deliver: after Return, Qt menu visible=%s", menu.isVisible())
        if menu.isVisible():
            menu.close()
    finally:
        for m in chain:
            m.setWindowOpacity(1.0)


_INSTALLED: dict = {}

_THEME: dict = {}
"""The theme manager being followed and the function applying it."""


def install_native_menus(app=None, backend=None) -> bool:
    """Make every Qt pop-up menu show as a system menu, where that is possible.

    Args:
        app: The application; the running one by default.
        backend: What shows the menus; :class:`AppKitBackend` on macOS by default.

    Returns:
        Whether system menus are now used.
    """
    if _INSTALLED:
        return True
    app = app or QApplication.instance()
    if app is None:
        return False
    if backend is None:
        if sys.platform != "darwin" or os.environ.get(OPT_OUT):
            return False
        try:
            backend = AppKitBackend()
        except Exception as exc:
            _log.warning("System menus are off, Qt menus are kept: %r", exc)
            return False
    catcher = NativeMenus(backend, app)
    app.installEventFilter(catcher)
    _INSTALLED.update(app=app, catcher=catcher)
    follow_theme(backend)
    return True


def follow_theme(backend, manager=None) -> bool:
    """Keep the system's title bars and menus in the application's theme.

    With the theme set to follow the system, macOS decides; otherwise the
    application's light or dark choice is applied, and again on each change.

    Args:
        backend: The menu backend; nothing happens without ``set_appearance``.
        manager: The theme manager; the application's own by default.

    Returns:
        Whether the theme is now followed.
    """
    if not hasattr(backend, "set_appearance") or os.environ.get(NO_THEME):
        return False
    if manager is None:
        try:
            from tools.theme import theme as manager
        except Exception:
            _log.debug("no theme manager", exc_info=True)
            return False

    def apply(*_):
        try:
            backend.set_appearance(None if manager.follow_system else bool(manager.is_dark))
        except Exception:
            _log.debug("could not set the appearance", exc_info=True)

    unfollow_theme()
    apply()
    manager.themeChanged.connect(apply)
    _THEME.update(manager=manager, apply=apply)
    return True


def unfollow_theme() -> None:
    """Stop following the application's theme."""
    if not _THEME:
        return
    try:
        _THEME["manager"].themeChanged.disconnect(_THEME["apply"])
    except Exception:
        _log.debug("theme already disconnected", exc_info=True)
    _THEME.clear()


def uninstall_native_menus() -> None:
    """Go back to Qt's own menus."""
    if not _INSTALLED:
        return
    _INSTALLED["app"].removeEventFilter(_INSTALLED["catcher"])
    unfollow_theme()
    _INSTALLED["catcher"].deleteLater()
    _INSTALLED.clear()
