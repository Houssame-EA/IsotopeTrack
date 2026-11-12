"""Frosted-glass window backdrops for macOS and Windows 11.

On macOS an ``NSVisualEffectView`` is placed behind the Qt content view so
the desktop and other windows show through, blurred, wherever the Qt widgets
paint a transparent or semi-transparent background (only the sidebar). On Windows 11 the DWM
system backdrop (Acrylic on 22H2 and later, Mica on 21H2) is enabled for the
same effect. Every other platform, and Windows 10, keeps an opaque window.

Everything is done through ``ctypes`` so no extra dependency is needed and
PyInstaller builds are unaffected. Any failure leaves the window opaque.
"""

import ctypes
import ctypes.util
import logging
import os
import sys

from PySide6.QtCore import Qt

_log = logging.getLogger("IsotopeTrack.WindowGlass")

_MAC_MATERIAL_SIDEBAR = 7
_MAC_BLENDING_BEHIND_WINDOW = 0
_MAC_STATE_ACTIVE = 1
_MAC_AUTORESIZE_WIDTH_HEIGHT = 2 | 16
_MAC_WINDOW_BELOW = -1
_MAC_FULL_SIZE_CONTENT = 1 << 15
_MAC_TITLE_HIDDEN = 1

TITLEBAR_INSET = 28

_WIN_ATTR_DARK_MODE = 20
_WIN_ATTR_SYSTEM_BACKDROP = 38
_WIN_ATTR_MICA_LEGACY = 1029
_WIN_BACKDROP_ACRYLIC = 3
_WIN_BUILD_MICA = 22000
_WIN_BUILD_ACRYLIC = 22621


def titlebar_inset(widget):
    """Return how far content must stay below the window's top edge.

    On macOS the glass window has no separate title bar: the content runs up
    to the top edge under the traffic-light buttons, so that strip is kept
    clear. Everywhere else the system title bar is unchanged and this is 0.

    Args:
        widget (QWidget): The top-level window.

    Returns:
        int: Inset in pixels.
    """
    return TITLEBAR_INSET if getattr(widget, "_glass_unified", False) else 0


def is_supported():
    """Return True when the current platform can draw a frosted backdrop.

    Setting the environment variable ``ISOTOPETRACK_NO_GLASS=1`` turns the
    effect off, which keeps a plain opaque window for comparison or fallback.

    Returns:
        bool: True on macOS and on Windows 11 (build 22000 or later).
    """
    if os.environ.get("ISOTOPETRACK_NO_GLASS"):
        return False
    if sys.platform == "darwin":
        return True
    if sys.platform == "win32":
        try:
            return sys.getwindowsversion().build >= _WIN_BUILD_MICA
        except Exception:
            return False
    return False


def prepare(widget):
    """Mark a top-level widget as translucent before its native window exists.

    Must be called before the widget is first shown.

    Args:
        widget (QWidget): The top-level window.

    Returns:
        bool: True if the widget was prepared for a glass backdrop.
    """
    if not is_supported():
        return False
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    if sys.platform == "darwin":
        expand = getattr(Qt.WindowType, "ExpandedClientAreaHint", None)
        no_bar = getattr(Qt.WindowType, "NoTitleBarBackgroundHint", None)
        if expand is not None and no_bar is not None:
            widget.setWindowFlag(expand, True)
            widget.setWindowFlag(no_bar, True)
            widget._glass_qt_unified = True
        ignore_safe_area(widget)
    widget._glass_prepared = True
    return True


_safe_area_filter = None
_titlebar_filter = None


def _install_safe_area_filter():
    """Make every widget in a merged-title-bar window ignore the safe area.

    Qt adds the title-bar height to the contents margins of any widget that
    overlaps the top strip, so a scrolled page would suddenly be pushed down.
    An application-wide filter clears that behaviour on each widget as it is
    polished, which also covers widgets created later (tables, dialogs' children).
    """
    global _safe_area_filter
    if _safe_area_filter is not None:
        return
    from PySide6.QtCore import QEvent, QObject
    from PySide6.QtWidgets import QApplication, QWidget

    class _SafeAreaFilter(QObject):
        """Clears WA_ContentsMarginsRespectsSafeArea inside glass windows."""

        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.Polish and isinstance(obj, QWidget):
                try:
                    if getattr(obj.window(), "_glass_prepared", False):
                        ignore_safe_area(obj)
                except RuntimeError:
                    pass
            return False

    app = QApplication.instance()
    if app is None:
        return
    _safe_area_filter = _SafeAreaFilter(app)
    app.installEventFilter(_safe_area_filter)


def ignore_safe_area_tree(widget):
    """Clear the safe-area margins on a window and all its current children.

    Args:
        widget (QWidget): The top-level window.
    """
    from PySide6.QtWidgets import QWidget
    ignore_safe_area(widget)
    for child in widget.findChildren(QWidget):
        ignore_safe_area(child)
    _install_safe_area_filter()


def ignore_safe_area(widget):
    """Let a widget's layout use the strip under the merged macOS title bar.

    Qt 6.9 adds the title-bar height to a window's contents margins (the
    "safe area"), which would push the content back down below an empty band.

    Args:
        widget (QWidget): Widget whose layout should start at the top edge.
    """
    attr = getattr(Qt.WidgetAttribute, "WA_ContentsMarginsRespectsSafeArea", None)
    if attr is not None:
        widget.setAttribute(attr, False)


def apply(widget, dark):
    """Install the frosted backdrop behind a prepared, shown top-level widget.

    Safe to call more than once; later calls only refresh the appearance.
    On macOS it also makes double-clicks on the merged title strip work.

    Args:
        widget (QWidget): The top-level window passed to :func:`prepare`.
        dark (bool): Whether the app is currently using the dark theme.

    Returns:
        bool: True if the backdrop is active.
    """
    if not getattr(widget, "_glass_prepared", False):
        return False
    try:
        if sys.platform == "darwin":
            active = _apply_mac(widget)
            if active and titlebar_inset(widget):
                _install_titlebar_filter()
            return active
        if sys.platform == "win32":
            return _apply_windows(widget, dark)
    except Exception:
        _log.exception("Could not apply the frosted window backdrop")
    return False


class _NSRect(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double),
                ("w", ctypes.c_double), ("h", ctypes.c_double)]


_objc = None


def _objc_lib():
    """Load libobjc and AppKit once and return the libobjc handle."""
    global _objc
    if _objc is None:
        lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
        lib.objc_getClass.restype = ctypes.c_void_p
        lib.objc_getClass.argtypes = [ctypes.c_char_p]
        lib.sel_registerName.restype = ctypes.c_void_p
        lib.sel_registerName.argtypes = [ctypes.c_char_p]
        _objc = lib
    return _objc


def _send(receiver, selector, restype=ctypes.c_void_p, argtypes=(), *args):
    """Call ``objc_msgSend`` with an explicit prototype.

    Args:
        receiver (int): Object or class pointer.
        selector (str): Selector name.
        restype: ctypes return type.
        argtypes (tuple): ctypes types of the extra arguments.
        *args: The extra arguments.

    Returns:
        The message result converted by ``restype``.
    """
    lib = _objc_lib()
    proto = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *argtypes)
    fn = proto(ctypes.cast(lib.objc_msgSend, ctypes.c_void_p).value)
    return fn(receiver, lib.sel_registerName(selector.encode()), *args)


def _rect(view, selector="bounds"):
    """Return an NSRect-valued property of an Objective-C view.

    Uses ``objc_msgSend_stret`` on Intel, where large structs are returned
    through memory, and ``objc_msgSend`` on Apple silicon.
    """
    import platform
    lib = _objc_lib()
    name = "objc_msgSend" if platform.machine() == "arm64" else "objc_msgSend_stret"
    proto = ctypes.CFUNCTYPE(_NSRect, ctypes.c_void_p, ctypes.c_void_p)
    fn = proto(ctypes.cast(getattr(lib, name), ctypes.c_void_p).value)
    return fn(view, lib.sel_registerName(selector.encode()))


def _cls(name):
    """Return the Objective-C class pointer for ``name``."""
    return _objc_lib().objc_getClass(name.encode())


def _ns_string(text):
    """Return an autoreleased NSString for ``text``."""
    return _send(_cls("NSString"), "stringWithUTF8String:",
                 ctypes.c_void_p, (ctypes.c_char_p,), text.encode())


def _apply_mac(widget):
    """Put an NSVisualEffectView behind the Qt content and merge the title bar.

    The title bar is made transparent and the content extends under it, so
    the sidebar runs up to the top edge with the traffic-light buttons on it,
    as one continuous column. The window title text is hidden. Only the parts
    of the Qt content that paint transparent (the sidebar) show the blur.
    """
    view = int(widget.winId())
    window = _send(view, "window")
    if not window:
        return False
    content = _send(window, "contentView")
    frame_view = _send(content, "superview")
    if not content or not frame_view:
        return False

    _send(window, "setBackgroundColor:", None, (ctypes.c_void_p,),
          _send(_cls("NSColor"), "windowBackgroundColor"))

    mask = _send(window, "styleMask", ctypes.c_ulong)
    _send(window, "setStyleMask:", None, (ctypes.c_ulong,), mask | _MAC_FULL_SIZE_CONTENT)
    _send(window, "setTitlebarAppearsTransparent:", None, (ctypes.c_bool,), True)
    _send(window, "setTitleVisibility:", None, (ctypes.c_long,), _MAC_TITLE_HIDDEN)
    widget._glass_unified = True

    old = getattr(widget, "_glass_view", None)
    if old and _send(old, "superview") == frame_view:
        return True

    try:
        full = _rect(frame_view)
        full = _NSRect(0.0, 0.0, full.w, full.h)
    except Exception:
        frame = widget.frameGeometry()
        full = _NSRect(0.0, 0.0, float(frame.width()), float(frame.height()) + TITLEBAR_INSET)
    fx = _send(_send(_cls("NSVisualEffectView"), "alloc"), "init")
    _send(fx, "setFrame:", None, (_NSRect,), full)
    _send(fx, "setAutoresizingMask:", None, (ctypes.c_ulong,), _MAC_AUTORESIZE_WIDTH_HEIGHT)
    _send(fx, "setMaterial:", None, (ctypes.c_long,), _MAC_MATERIAL_SIDEBAR)
    _send(fx, "setBlendingMode:", None, (ctypes.c_long,), _MAC_BLENDING_BEHIND_WINDOW)
    _send(fx, "setState:", None, (ctypes.c_long,), _MAC_STATE_ACTIVE)
    appearance = _send(_cls("NSAppearance"), "appearanceNamed:", ctypes.c_void_p,
                       (ctypes.c_void_p,), _ns_string("NSAppearanceNameDarkAqua"))
    if appearance:
        _send(fx, "setAppearance:", None, (ctypes.c_void_p,), appearance)
    _send(frame_view, "addSubview:positioned:relativeTo:", None,
          (ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p),
          fx, _MAC_WINDOW_BELOW, content)
    widget._glass_view = fx
    return True


def window_buttons_geometry(widget):
    """Locate the macOS close/minimise/zoom buttons of a glass window.

    Args:
        widget (QWidget): A window passed to :func:`apply`.

    Returns:
        tuple[float, float] | None: ``(right_x, center_y)`` of the button group
        in Qt coordinates (points from the window's top-left), or None when it
        cannot be read (other platforms, Intel builds, or any failure).
    """
    import platform
    if sys.platform != "darwin" or platform.machine() != "arm64":
        return None
    try:
        view = int(widget.winId())
        window = _send(view, "window")
        if not window:
            return None
        zoom = _send(window, "standardWindowButton:", ctypes.c_void_p, (ctypes.c_long,), 2)
        content = _send(window, "contentView")
        if not zoom or not content:
            return None
        bounds = _send(zoom, "bounds", _NSRect)
        rect = _send(zoom, "convertRect:toView:", _NSRect,
                     (_NSRect, ctypes.c_void_p), bounds, content)
        flipped = _send(content, "isFlipped", ctypes.c_bool)
        height = _send(content, "frame", _NSRect).h
        center = rect.y + rect.h / 2.0
        center_y = center if flipped else height - center
        return rect.x + rect.w, center_y
    except Exception:
        _log.exception("Could not read the window button positions")
        return None


class _Margins(ctypes.Structure):
    _fields_ = [("left", ctypes.c_int), ("right", ctypes.c_int),
                ("top", ctypes.c_int), ("bottom", ctypes.c_int)]


def _apply_windows(widget, dark):
    """Enable the DWM Acrylic (or Mica) backdrop for the window."""
    dwm = ctypes.windll.dwmapi
    hwnd = ctypes.c_void_p(int(widget.winId()))
    build = sys.getwindowsversion().build

    dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(_Margins(-1, -1, -1, -1)))
    flag = ctypes.c_int(1 if dark else 0)
    dwm.DwmSetWindowAttribute(hwnd, _WIN_ATTR_DARK_MODE,
                              ctypes.byref(flag), ctypes.sizeof(flag))
    if build >= _WIN_BUILD_ACRYLIC:
        value = ctypes.c_int(_WIN_BACKDROP_ACRYLIC)
        result = dwm.DwmSetWindowAttribute(hwnd, _WIN_ATTR_SYSTEM_BACKDROP,
                                           ctypes.byref(value), ctypes.sizeof(value))
    else:
        value = ctypes.c_int(1)
        result = dwm.DwmSetWindowAttribute(hwnd, _WIN_ATTR_MICA_LEGACY,
                                           ctypes.byref(value), ctypes.sizeof(value))
    return result == 0


def titlebar_action():
    """Return what a title-bar double-click does in the user's macOS settings.

    Reads ``AppleActionOnDoubleClick`` (Desktop & Dock → "Double-click a
    window's title bar to"), falling back on the older
    ``AppleMiniaturizeOnDoubleClick`` switch.

    Returns:
        str: ``"zoom"``, ``"minimize"`` or ``"none"``.
    """
    try:
        defaults = _send(_cls("NSUserDefaults"), "standardUserDefaults")
        value = _send(defaults, "stringForKey:", ctypes.c_void_p, (ctypes.c_void_p,),
                      _ns_string("AppleActionOnDoubleClick"))
        if value:
            text = _send(value, "UTF8String", ctypes.c_char_p).decode()
            return {"minimize": "minimize", "none": "none"}.get(text.lower(), "zoom")
        mini = _send(defaults, "boolForKey:", ctypes.c_bool, (ctypes.c_void_p,),
                     _ns_string("AppleMiniaturizeOnDoubleClick"))
        return "minimize" if mini else "zoom"
    except Exception:
        _log.exception("Could not read the title-bar double-click setting")
        return "zoom"


def titlebar_double_click(widget):
    """Do what macOS does when the title bar of *widget*'s window is double-clicked.

    The merged title bar of a glass window is Qt content, so macOS never sees
    the double-click there; this hands it back to the window.

    Args:
        widget (QWidget): A glass window.
    """
    if sys.platform != "darwin":
        return
    try:
        window = _send(int(widget.winId()), "window")
        if not window:
            return
        action = titlebar_action()
        if action == "zoom":
            _send(window, "performZoom:", None, (ctypes.c_void_p,), None)
        elif action == "minimize":
            _send(window, "performMiniaturize:", None, (ctypes.c_void_p,), None)
    except Exception:
        _log.exception("Could not handle the title-bar double-click")


def in_titlebar(window, global_pos):
    """Whether a point lies on the merged title strip of a glass window, off any control.

    Args:
        window (QWidget): The top-level window.
        global_pos (QPoint): Screen position of the click.
    """
    from PySide6.QtWidgets import (
        QAbstractButton, QAbstractSlider, QAbstractSpinBox, QComboBox, QLineEdit, QMenuBar,
        QTabBar, QTextEdit,
    )
    inset = titlebar_inset(window)
    if not inset:
        return False
    pos = window.mapFromGlobal(global_pos)
    if not (0 <= pos.y() < inset and 0 <= pos.x() < window.width()):
        return False
    controls = (QAbstractButton, QAbstractSlider, QAbstractSpinBox, QComboBox, QLineEdit,
                QMenuBar, QTabBar, QTextEdit)
    child = window.childAt(pos)
    while child is not None and child is not window:
        if isinstance(child, controls):
            return False
        child = child.parentWidget()
    return True


def _install_titlebar_filter():
    """Send double-clicks on the merged title strip of glass windows back to macOS."""
    global _titlebar_filter
    if _titlebar_filter is not None:
        return
    from PySide6.QtCore import QEvent, QObject
    from PySide6.QtWidgets import QApplication, QWidget

    class _TitlebarFilter(QObject):
        """Turns a double-click on the title strip into the system's title-bar action."""

        def eventFilter(self, obj, event):
            if (event.type() == QEvent.Type.MouseButtonDblClick
                    and event.button() == Qt.MouseButton.LeftButton
                    and isinstance(obj, QWidget)):
                try:
                    window = obj.window()
                    if in_titlebar(window, event.globalPosition().toPoint()):
                        titlebar_double_click(window)
                        return True
                except RuntimeError:
                    pass
            return False

    app = QApplication.instance()
    if app is None:
        return
    _titlebar_filter = _TitlebarFilter(app)
    app.installEventFilter(_titlebar_filter)


class _ShowWatcher:
    """Runs the glass activation once a window has finished showing."""

    def __init__(self, widget, on_active):
        from PySide6.QtCore import QEvent, QObject, QTimer

        watcher = self

        class _Filter(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.Show:
                    QTimer.singleShot(0, watcher.activate)
                return False

        self.widget = widget
        self.on_active = on_active
        self.filter = _Filter(widget)
        widget.installEventFilter(self.filter)

    def activate(self):
        """Apply the backdrop and tell the window how tall the title strip is."""
        from tools.theme import theme
        w = self.widget
        try:
            if not w.isVisible():
                return
        except RuntimeError:
            return
        if getattr(w, "_glass_active", False):
            apply(w, theme.is_dark)
            return
        if apply(w, theme.is_dark):
            w._glass_active = True
            ignore_safe_area_tree(w)
            if self.on_active is not None:
                self.on_active(titlebar_inset(w))
            theme.themeChanged.connect(lambda *_: _refresh(w))


def _refresh(widget):
    """Re-apply the backdrop after a theme switch (updates Windows dark mode)."""
    from tools.theme import theme
    try:
        apply(widget, theme.is_dark)
    except RuntimeError:
        pass


def attach(widget, on_active=None):
    """Give a top-level window the frosted sidebar treatment.

    Call before the window is first shown. Once it is on screen the backdrop is
    applied and ``on_active(inset)`` is called, where ``inset`` is the height of
    the merged title-bar strip (0 when the system title bar is kept). The
    window should then restyle itself so its sidebar paints a translucent tint
    and the rest stays opaque.

    Args:
        widget (QWidget): The top-level window.
        on_active (callable | None): Called with the title-bar inset.

    Returns:
        bool: True if the platform supports the effect.
    """
    if not prepare(widget):
        return False
    widget._glass_active = False
    widget._glass_watcher = _ShowWatcher(widget, on_active)
    return True

