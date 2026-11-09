# `window_glass.py`

Frosted-glass window backdrops for macOS and Windows 11.

On macOS an ``NSVisualEffectView`` is placed behind the Qt content view so
the desktop and other windows show through, blurred, wherever the Qt widgets
paint a transparent or semi-transparent background (only the sidebar). On Windows 11 the DWM
system backdrop (Acrylic on 22H2 and later, Mica on 21H2) is enabled for the
same effect. Every other platform, and Windows 10, keeps an opaque window.

Everything is done through ``ctypes`` so no extra dependency is needed and
PyInstaller builds are unaffected. Any failure leaves the window opaque.

---

## Constants

| Name | Value |
|------|-------|
| `_MAC_MATERIAL_SIDEBAR` | `7` |
| `_MAC_BLENDING_BEHIND_WINDOW` | `0` |
| `_MAC_STATE_ACTIVE` | `1` |
| `_MAC_AUTORESIZE_WIDTH_HEIGHT` | `2 \| 16` |
| `_MAC_WINDOW_BELOW` | `-1` |
| `_MAC_FULL_SIZE_CONTENT` | `1 << 15` |
| `_MAC_TITLE_HIDDEN` | `1` |
| `TITLEBAR_INSET` | `28` |
| `_WIN_ATTR_DARK_MODE` | `20` |
| `_WIN_ATTR_SYSTEM_BACKDROP` | `38` |
| `_WIN_ATTR_MICA_LEGACY` | `1029` |
| `_WIN_BACKDROP_ACRYLIC` | `3` |
| `_WIN_BUILD_MICA` | `22000` |
| `_WIN_BUILD_ACRYLIC` | `22621` |

## Classes

### `_NSRect` *(extends `ctypes.Structure`)*

### `_Margins` *(extends `ctypes.Structure`)*

### `_ShowWatcher`

Runs the glass activation once a window has finished showing.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, widget, on_active)` |  |
| `activate` | `(self)` | Apply the backdrop and tell the window how tall the title strip is. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `titlebar_inset` | `(widget)` | Return how far content must stay below the window's top edge. |
| `is_supported` | `()` | Return True when the current platform can draw a frosted backdrop. |
| `prepare` | `(widget)` | Mark a top-level widget as translucent before its native window exists. |
| `_install_safe_area_filter` | `()` | Make every widget in a merged-title-bar window ignore the safe area. |
| `ignore_safe_area_tree` | `(widget)` | Clear the safe-area margins on a window and all its current children. |
| `ignore_safe_area` | `(widget)` | Let a widget's layout use the strip under the merged macOS title bar. |
| `apply` | `(widget, dark)` | Install the frosted backdrop behind a prepared, shown top-level widget. |
| `_objc_lib` | `()` | Load libobjc and AppKit once and return the libobjc handle. |
| `_send` | `(receiver, selector, restype=ctypes.c_void_p, argtypes=(), *args)` | Call ``objc_msgSend`` with an explicit prototype. |
| `_rect` | `(view, selector='bounds')` | Return an NSRect-valued property of an Objective-C view. |
| `_cls` | `(name)` | Return the Objective-C class pointer for ``name``. |
| `_ns_string` | `(text)` | Return an autoreleased NSString for ``text``. |
| `_apply_mac` | `(widget)` | Put an NSVisualEffectView behind the Qt content and merge the title bar. |
| `window_buttons_geometry` | `(widget)` | Locate the macOS close/minimise/zoom buttons of a glass window. |
| `_apply_windows` | `(widget, dark)` | Enable the DWM Acrylic (or Mica) backdrop for the window. |
| `titlebar_action` | `()` | Return what a title-bar double-click does in the user's macOS settings. |
| `titlebar_double_click` | `(widget)` | Do what macOS does when the title bar of *widget*'s window is double-clicked. |
| `in_titlebar` | `(window, global_pos)` | Whether a point lies on the merged title strip of a glass window, off any control. |
| `_install_titlebar_filter` | `()` | Send double-clicks on the merged title strip of glass windows back to macOS. |
| `_refresh` | `(widget)` | Re-apply the backdrop after a theme switch (updates Windows dark mode). |
| `attach` | `(widget, on_active=None)` | Give a top-level window the frosted sidebar treatment. |
