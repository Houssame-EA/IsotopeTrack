# `native_menu.py`

System right-click menus on macOS.

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

---

## Constants

| Name | Value |
|------|-------|
| `OPT_OUT` | `'ITK_QT_MENUS'` |
| `DEBUG` | `'ITK_MENU_DEBUG'` |
| `NO_RESET` | `'ITK_MENU_NO_RESET'` |
| `NO_THEME` | `'ITK_MENU_NO_THEME'` |
| `KEEP_QT` | `'itkQtMenu'` |
| `MODIFIERS` | `{'ctrl': 1 << 20, 'meta': 1 << 18, 'alt': 1 << 19, 'shift…` |
| `ICON_POINTS` | `16` |
| `_TARGET` | `None` |

## Classes

### `Entry`

One row of a menu, read from Qt.

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

### `AppKitBackend`

Shows entries as a macOS system menu and returns the chosen ``QAction``.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` |  |
| `popup` | `(self, entries: list[Entry], pos: QPoint)` | Show the menu at global position *pos*; block until it closes. |
| `reset_mouse_buttons` | `(self)` | Tell Qt's windows that no mouse button is held any more. |
| `set_appearance` | `(self, dark)` | Make title bars and system menus dark, light, or follow macOS. |
| `_image` | `(self, icon)` | A 16-point ``NSImage`` of a ``QIcon``, or ``None``. |
| `_build` | `(self, entries, target, registry)` |  |

### `NativeMenus` *(extends `QObject`)*

Shows each Qt pop-up menu as a system menu as soon as Qt opens it.

``QMenu.exec`` cannot be replaced from Python in PySide6, so the menus are
caught when they are shown instead: the Qt menu is made transparent, the
system menu is shown at the same place, and the choice is handed back to
the Qt menu, which then runs it itself. ``exec`` therefore returns the
chosen action, and ``triggered``, check marks and ``aboutToHide`` behave
exactly as with Qt's own menus.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, backend, parent=None)` |  |
| `wants` | `(self, menu) → bool` | Whether *menu* should be shown as a system menu. |
| `eventFilter` | `(self, obj, event)` | Catch a top-level menu as it is shown, and keep it open meanwhile. |
| `run` | `(self, menu: QMenu) → None` | Show the system menu for *menu* and hand back the choice. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `trace` | `(message: str, *args) → None` | Log one step of a system menu when :data:`DEBUG` is set. |
| `clean_text` | `(text: str) → tuple[str, str]` | Remove ``&`` mnemonics and split off a shortcut written after a tab. |
| `submenu` | `(action)` | The submenu *action* opens, or ``None``. |
| `supported` | `(menu: QMenu) → bool` | Whether a system menu can show *menu* and all its submenus. |
| `describe` | `(menu: QMenu, show: bool=True) → list[Entry]` | Read a Qt menu into entries, as it would appear now. |
| `owners` | `(action, root: QMenu) → list[QMenu]` | The menus from *root* down to the one holding *action*, outermost first. |
| `key_equivalent` | `(shortcut: str) → tuple[str, int]` | A shortcut as a macOS key equivalent: ``"Ctrl+Shift+C"`` → ``("c", ⌘⇧)``. |
| `icon_png` | `(icon, points: int=ICON_POINTS) → bytes` | A ``QIcon`` as PNG bytes at twice *points*, sharp on Retina screens. |
| `_target_class` | `(objc, Foundation)` | The Objective-C class receiving the chosen item, defined once per process. |
| `alive` | `(obj) → bool` | Whether a Qt object still exists on the C++ side. |
| `release_buttons` | `(menu: QMenu) → None` | Let Qt know the mouse buttons are up again, without anyone seeing a click. |
| `deliver` | `(menu: QMenu, chosen) → None` | Hand the choice to the Qt menu, which runs it and closes. |
| `install_native_menus` | `(app=None, backend=None) → bool` | Make every Qt pop-up menu show as a system menu, where that is possible. |
| `follow_theme` | `(backend, manager=None) → bool` | Keep the system's title bars and menus in the application's theme. |
| `unfollow_theme` | `() → None` | Stop following the application's theme. |
| `uninstall_native_menus` | `() → None` | Go back to Qt's own menus. |
