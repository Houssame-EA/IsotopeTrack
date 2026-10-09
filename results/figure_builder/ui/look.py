"""Figure Builder window styling, driven by the application's theme.

Every colour comes from :mod:`tools.theme`, so the window matches the rest of
IsotopeTrack and follows the light/dark switch. Widgets only carry object
names (``fbHint``, ``fbError``, ``fbPrimary`` …); this module turns the
current palette into one stylesheet for the whole window.
"""

from __future__ import annotations

from types import SimpleNamespace

_FALLBACK = SimpleNamespace(
    name='light', bg_primary='#e8edf3', bg_secondary='#ffffff', bg_tertiary='#f1f4f8',
    bg_hover='#e3e9f1', bg_selected='#dbe8fb', text_primary='#1f2937', text_secondary='#4b5563',
    text_inverse='#ffffff', text_muted='#6b7280', border='#cfd6df', border_subtle='#e3e7ec',
    border_strong='#9aa4b2', accent='#2196F3', accent_hover='#1e88e5', accent_pressed='#1976d2',
    accent_soft='#e3f2fd', danger='#d32f2f', danger_bg='#fdecea', success='#2e7d32',
    plot_bg='#ffffff', plot_fg='#000000')


def palette():
    """The application's current palette (a light fallback outside the app)."""
    try:
        from tools.theme import theme
        return theme.palette
    except Exception:
        return _FALLBACK


def is_dark() -> bool:
    """Whether the application is in dark mode."""
    try:
        from tools.theme import theme
        return bool(theme.is_dark)
    except Exception:
        return False


def connect(slot):
    """Call ``slot`` whenever the application theme changes (no-op outside the app)."""
    try:
        from tools.theme import theme
        theme.themeChanged.connect(lambda _name: slot())
    except Exception:
        pass


def window_qss(p=None) -> str:
    """Stylesheet for the Figure Builder window and its child dialogs.

    It is the shared application sheet (:func:`tools.theme.app_qss`), so the
    builder and every window that uses that sheet look the same.
    """
    p = p or palette()
    try:
        from tools.theme import app_qss
    except Exception:
        return ''
    return app_qss(p)


def style(widget):
    """Apply the window stylesheet to a dialog (and keep it in sync with the theme)."""
    widget.setStyleSheet(window_qss())
    connect(lambda w=widget: _restyle(w))


def _restyle(widget):
    try:
        widget.setStyleSheet(window_qss())
    except RuntimeError:
        pass


def icon_color() -> str:
    """Colour for toolbar icons in the current theme."""
    return palette().text_secondary


def danger() -> str:
    """The theme's error colour."""
    return palette().danger
