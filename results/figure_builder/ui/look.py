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
    """Stylesheet for the Figure Builder window and its child dialogs."""
    p = p or palette()
    return f"""
    QDialog, QWidget#fbRoot {{
        background: {p.bg_primary};
        color: {p.text_primary};
    }}
    QLabel {{ color: {p.text_primary}; background: transparent; }}
    QLabel#fbHint {{ color: {p.text_muted}; font-size: 11px; }}
    QLabel#fbStatus {{ color: {p.text_muted}; }}
    QLabel#fbError {{ color: {p.danger}; font-weight: 600; padding: 2px 4px; }}
    QLabel#fbEmpty {{ color: {p.text_muted}; padding: 12px; }}
    QFrame#fbToolbar {{
        background: {p.bg_secondary};
        border: 1px solid {p.border_subtle};
        border-radius: 8px;
    }}
    QFrame#fbSep {{ color: {p.border}; }}
    QFrame#fbPreview {{
        background: {p.bg_tertiary};
        border: 1px solid {p.border_subtle};
        border-radius: 8px;
    }}
    QToolButton {{
        background: transparent;
        color: {p.text_primary};
        border: 1px solid transparent;
        border-radius: 6px;
        padding: 4px 8px;
    }}
    QToolButton:hover {{ background: {p.accent_soft}; border-color: {p.border}; }}
    QToolButton:pressed, QToolButton:checked {{ background: {p.bg_selected}; border-color: {p.accent}; }}
    QToolButton:disabled {{ color: {p.text_muted}; }}
    QToolButton::menu-indicator {{ image: none; width: 0; }}
    QPushButton {{
        background: {p.bg_tertiary};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: 6px;
        padding: 5px 12px;
        font-weight: 600;
    }}
    QPushButton:hover {{ background: {p.accent_soft}; border-color: {p.accent}; }}
    QPushButton#fbPrimary {{
        background: {p.accent};
        color: {p.text_inverse};
        border: none;
        padding: 6px 14px;
    }}
    QPushButton#fbPrimary:hover {{ background: {p.accent_hover}; }}
    QPushButton#fbPrimary:pressed {{ background: {p.accent_pressed}; }}
    QTabWidget::pane {{
        border: 1px solid {p.border_subtle};
        border-radius: 6px;
        background: {p.bg_secondary};
        top: -1px;
    }}
    QTabBar::tab {{
        background: transparent;
        color: {p.text_secondary};
        padding: 5px 10px;
        border-bottom: 2px solid transparent;
        font-weight: 600;
    }}
    QTabBar::tab:selected {{ color: {p.accent}; border-bottom: 2px solid {p.accent}; }}
    QTabBar::tab:hover {{ color: {p.text_primary}; }}
    QGroupBox {{
        background: {p.bg_secondary};
        border: 1px solid {p.border_subtle};
        border-radius: 8px;
        margin-top: 14px;
        padding: 8px 6px 4px 6px;
        font-weight: 600;
        color: {p.text_secondary};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 4px;
        color: {p.text_secondary};
    }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QFontComboBox {{
        background: {p.bg_secondary};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: 5px;
        padding: 3px 6px;
        min-height: 20px;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {p.accent};
    }}
    QLineEdit[invalid="true"] {{ border: 1.5px solid {p.danger}; background: {p.danger_bg}; }}
    QComboBox QAbstractItemView {{
        background: {p.bg_secondary};
        color: {p.text_primary};
        selection-background-color: {p.accent_soft};
        selection-color: {p.text_primary};
    }}
    QPlainTextEdit, QTextBrowser, QTableView, QTableWidget {{
        background: {p.bg_secondary};
        color: {p.text_primary};
        border: 1px solid {p.border_subtle};
        border-radius: 6px;
        gridline-color: {p.border_subtle};
        selection-background-color: {p.accent_soft};
        selection-color: {p.text_primary};
        alternate-background-color: {p.bg_tertiary};
    }}
    QHeaderView::section {{
        background: {p.bg_tertiary};
        color: {p.text_secondary};
        border: none;
        border-right: 1px solid {p.border_subtle};
        border-bottom: 1px solid {p.border_subtle};
        padding: 4px 6px;
        font-weight: 600;
    }}
    QCheckBox {{ color: {p.text_primary}; spacing: 6px; }}
    QCheckBox::indicator {{
        width: 15px; height: 15px; border-radius: 4px;
        border: 1.5px solid {p.border_strong}; background: {p.bg_secondary};
    }}
    QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; }}
    QCheckBox::indicator:indeterminate {{ background: {p.accent_soft}; border-color: {p.accent}; }}
    QMenu {{
        background: {p.bg_secondary};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: 6px;
        padding: 4px;
    }}
    QMenu::item {{ padding: 5px 22px 5px 12px; border-radius: 4px; }}
    QMenu::item:selected {{ background: {p.accent_soft}; color: {p.text_primary}; }}
    QMenu::item:disabled {{ color: {p.text_muted}; }}
    QMenu::separator {{ height: 1px; background: {p.border_subtle}; margin: 4px 8px; }}
    QSplitter::handle {{ background: transparent; }}
    QSplitter::handle:hover {{ background: {p.accent_soft}; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 4px; min-height: 24px; }}
    QScrollBar::handle:vertical:hover {{ background: {p.text_muted}; }}
    QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: 4px; min-width: 24px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QToolTip {{
        background: {p.bg_secondary};
        color: {p.text_primary};
        border: 1px solid {p.border};
        padding: 4px 6px;
    }}
    """


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
