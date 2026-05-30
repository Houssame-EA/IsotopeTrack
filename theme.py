import sys
from dataclasses import dataclass
from PySide6.QtCore import QObject, Signal, QSettings


# --------------------------------------------------------------------------- #
# System theme detection
# --------------------------------------------------------------------------- #

def _detect_system_theme() -> str:
    """
    Detect the OS dark/light mode preference.

    Tries three methods in order:
      1. Qt 6.5+ QStyleHints.colorScheme()  — cross-platform, most reliable
      2. macOS ``defaults read -g AppleInterfaceStyle``  — works on macOS 10.14+
      3. Windows registry AppsUseLightTheme key  — works on Windows 10+

    Returns 'dark' or 'light'.
    """
    # ── Method 1: Qt 6.5+ cross-platform ────────────────────────────────────
    try:
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtCore import Qt
        app = QGuiApplication.instance()
        if app is not None:
            scheme = app.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return "dark"
            if scheme == Qt.ColorScheme.Light:
                return "light"
    except (AttributeError, ImportError):
        pass

    # ── Method 2: macOS ─────────────────────────────────────────────────────
    if sys.platform == "darwin":
        try:
            import subprocess
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2,
            )
            return "dark" if "dark" in result.stdout.lower() else "light"
        except Exception:
            pass

    # ── Method 3: Windows registry ──────────────────────────────────────────
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "light" if val == 1 else "dark"
        except Exception:
            pass

    return "light"  


# --------------------------------------------------------------------------- #
# Palette
# --------------------------------------------------------------------------- #





@dataclass(frozen=True)
class Palette:
    """A complete color palette. All fields are hex strings '#rrggbb'."""
    bg_primary: str
    bg_secondary: str
    bg_tertiary: str
    bg_sidebar: str
    bg_sidebar_alt: str
    bg_hover: str
    bg_selected: str

    text_primary: str
    text_secondary: str
    text_inverse: str
    text_on_sidebar: str
    text_muted: str

    border: str
    border_subtle: str
    border_strong: str

    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str

    success: str
    warning: str
    warning_bg: str
    warning_border: str
    danger: str
    disabled: str

    plot_bg: str
    plot_fg: str

    tier_critical: str
    tier_high: str
    tier_medium: str
    tier_low: str
    tier_text: str

    name: str


LIGHT = Palette(
    name="light",
    bg_primary="#e8edf3",
    bg_secondary="#ffffff",
    bg_tertiary="#f6f8fb",
    bg_sidebar="#2c3e50",
    bg_sidebar_alt="#34495e",
    bg_hover="#f0f4f8",
    bg_selected="#e3f2fd",
    text_primary="#2c3e50",
    text_secondary="#5a6c7d",
    text_inverse="#ffffff",
    text_on_sidebar="#ecf0f1",
    text_muted="#7f8c8d",
    border="#d4dde6",
    border_subtle="#e6edf3",
    border_strong="#3498db",
    accent="#2196F3",
    accent_hover="#1976D2",
    accent_pressed="#0D47A1",
    accent_soft="#e3f2fd",
    success="#4CAF50",
    warning="#f39c12",
    warning_bg="#fff3cd",
    warning_border="#ffeaa7",
    danger="#e74c3c",
    disabled="#BDBDBD",
    plot_bg="#ffffff",
    plot_fg="#2c3e50",
    tier_critical="#ffc8c8",
    tier_high="#ffdcc8",
    tier_medium="#ffffc8",
    tier_low="#c8ffc8",
    tier_text="#2c3e50",
)


DARK = Palette(
    name="dark",
    bg_primary="#1e1e1e",
    bg_secondary="#252526",
    bg_tertiary="#2d2d30",
    bg_sidebar="#181818",
    bg_sidebar_alt="#2a2a2d",
    bg_hover="#2a2d2e",
    bg_selected="#094771",
    text_primary="#d4d4d4",
    text_secondary="#9d9d9d",
    text_inverse="#ffffff",
    text_on_sidebar="#cccccc",
    text_muted="#858585",
    border="#3c3c3c",
    border_subtle="#2d2d30",
    border_strong="#007acc",
    accent="#007acc",
    accent_hover="#1f8ad2",
    accent_pressed="#0b5a94",
    accent_soft="#094771",
    success="#4ec9b0",
    warning="#dcdcaa",
    warning_bg="#3a3a1f",
    warning_border="#5a5a2f",
    danger="#f48771",
    disabled="#4a4a4a",
    plot_bg="#1e1e1e",
    plot_fg="#d4d4d4",
    tier_critical="#5a2a2a",
    tier_high="#5a3a2a",
    tier_medium="#5a5a2a",
    tier_low="#2a5a2a",
    tier_text="#f0f0f0",
)


# --------------------------------------------------------------------------- #
# ThemeManager
# --------------------------------------------------------------------------- #

class ThemeManager(QObject):
    """
    Singleton theme manager.

    Emits ``themeChanged(palette_name)`` whenever the active theme changes.
    Widgets should connect to ``themeChanged`` and reapply their stylesheets.

    System-theme integration
    ------------------------
    On first run (no saved preference) the OS dark/light setting is used
    automatically.  Call ``sync_with_system()`` once after ``QApplication``
    is created to:
      • Apply the detected OS preference if follow-system is enabled.
      • Hook into ``QStyleHints.colorSchemeChanged`` for live OS changes
        (Qt 6.5 / PySide6 ≥ 6.5, macOS 13+, Windows 10+).

    The saved setting can be ``'light'``, ``'dark'``, or ``'system'``
    (follow OS automatically).
    """

    themeChanged = Signal(str)
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        super().__init__()
        self._initialized = True
        self._follow_system = False
        self._settings = QSettings("IsotopeTrack", "IsotopeTrack")

        saved = self._settings.value("theme/name", "system")   

        if saved == "system":
            self._follow_system = True
            try:
                detected = _detect_system_theme()
                self._palette = DARK if detected == "dark" else LIGHT
            except Exception:
                self._palette = LIGHT
        else:
            self._follow_system = False
            self._palette = DARK if saved == "dark" else LIGHT

    # -- System-theme integration ------------------------------------------- #

    def sync_with_system(self) -> None:
        """
        Call **once** right after ``QApplication`` is created (before the
        main window is shown).

        • If follow-system is enabled: detects the current OS preference
          and emits ``themeChanged`` if it differs from the placeholder
          set during ``__init__``.
        • Connects ``QStyleHints.colorSchemeChanged`` for live OS updates
          (Qt 6.5+; silently skipped on older Qt versions).

        Usage in your entry-point::

            app = QApplication(sys.argv)
            theme.sync_with_system()        # ← add this line
            window = MainWindow()
            window.showMaximized()
            sys.exit(app.exec())
        """
        if self._follow_system:
            detected = _detect_system_theme()
            new_palette = DARK if detected == "dark" else LIGHT
            if new_palette.name != self._palette.name:
                self._palette = new_palette
                self.themeChanged.emit(new_palette.name)

        try:
            from PySide6.QtGui import QGuiApplication
            hints = QGuiApplication.instance().styleHints()
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)
        except (AttributeError, TypeError, RuntimeError):
            pass  

    def _on_system_scheme_changed(self) -> None:
        """Qt slot: called automatically when the OS changes dark/light mode."""
        if not self._follow_system:
            return
        detected = _detect_system_theme()
        new_palette = DARK if detected == "dark" else LIGHT
        if new_palette.name != self._palette.name:
            self._palette = new_palette
            self.themeChanged.emit(new_palette.name)

    # -- Public API --------------------------------------------------------- #

    @property
    def palette(self) -> Palette:
        return self._palette

    @property
    def is_dark(self) -> bool:
        return self._palette.name == "dark"

    @property
    def follow_system(self) -> bool:
        """True when the theme automatically tracks the OS preference."""
        return self._follow_system

    def set_follow_system(self, follow: bool) -> None:
        """
        Enable or disable automatic OS-theme following.

        When *follow* is ``True``:
          • Detects the current OS preference and applies it immediately.
          • Saves ``'system'`` to QSettings.

        When *follow* is ``False``:
          • Freezes the current palette.
          • Saves the palette name (``'dark'`` / ``'light'``) to QSettings.
        """
        self._follow_system = follow
        if follow:
            self._settings.setValue("theme/name", "system")
            detected = _detect_system_theme()
            self._apply_palette(DARK if detected == "dark" else LIGHT)
        else:
            self._settings.setValue("theme/name", self._palette.name)

    def set_theme(self, name: str) -> None:
        """
        Manually set 'dark' or 'light'.  Disables follow-system automatically
        so the manual choice is preserved across restarts.
        """
        new_palette = DARK if name == "dark" else LIGHT
        self._follow_system = False
        self._settings.setValue("theme/name", new_palette.name)
        self._apply_palette(new_palette)

    def toggle(self) -> None:
        """Toggle between dark and light, disabling follow-system."""
        self.set_theme("light" if self.is_dark else "dark")

    def connect_theme(self, slot) -> callable:
        """
        Connect *slot* to ``themeChanged`` and return a zero-argument
        disconnect callable (safe to call even after the manager is gone).
        """
        self.themeChanged.connect(slot)

        def _disconnect():
            try:
                self.themeChanged.disconnect(slot)
            except RuntimeError:
                pass

        return _disconnect

    # -- Internal ----------------------------------------------------------- #

    def _apply_palette(self, new_palette: "Palette") -> None:
        if new_palette.name == self._palette.name:
            return
        self._palette = new_palette
        self.themeChanged.emit(new_palette.name)


theme = ThemeManager()


# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #

def main_window_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QMainWindow, QWidget {{
            background-color: {p.bg_primary};
            color: {p.text_primary};
        }}
        QGroupBox {{
            color: {p.text_primary};
            font-weight: bold;
            border: 1px solid {p.border};
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 10px;
            background-color: {p.bg_secondary};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 5px;
        }}
        QPushButton {{
            background-color: {p.accent};
            color: {p.text_inverse};
            border: none;
            border-radius: 6px;
            padding: 6px 12px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {p.accent_hover};
        }}
        QPushButton:pressed {{
            background-color: {p.accent_pressed};
        }}
        QPushButton:disabled {{
            background-color: {p.disabled};
            color: {p.text_muted};
        }}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 6px;
            padding: 6px;
            selection-background-color: {p.accent};
            selection-color: {p.text_inverse};
        }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border: 1px solid {p.accent};
        }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QComboBox QAbstractItemView {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            selection-background-color: {p.accent_soft};
            selection-color: {p.text_primary};
            border: 1px solid {p.border};
            outline: 0;
        }}
        QTableWidget {{
            background-color: {p.bg_secondary};
            alternate-background-color: {p.bg_tertiary};
            color: {p.text_primary};
            gridline-color: {p.border};
            border: 1px solid {p.border};
            selection-background-color: {p.accent_soft};
            selection-color: {p.text_primary};
        }}
        QHeaderView::section {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            padding: 6px;
            border: none;
            border-right: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
            font-weight: bold;
        }}
        QTableCornerButton::section {{
            background-color: {p.bg_tertiary};
            border: none;
            border-right: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
        }}
        QLabel {{
            color: {p.text_primary};
            background-color: transparent;
        }}
        QTabWidget::pane {{
            border: 1px solid {p.border};
            border-radius: 4px;
            background-color: {p.bg_secondary};
            top: -1px;
        }}
        /* QTabBar itself — without this the strip after the last tab
           shows the OS default (white on macOS). */
        QTabBar {{
            background-color: {p.bg_primary};
            qproperty-drawBase: 0;
        }}
        QTabWidget::tab-bar {{ alignment: left; }}
        QTabBar::tab {{
            background-color: {p.bg_tertiary};
            color: {p.text_secondary};
            border: 1px solid {p.border};
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 8px 16px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border-bottom: 1px solid {p.bg_secondary};
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {p.bg_hover};
            color: {p.text_primary};
        }}
        QListWidget {{
            background-color: {p.bg_secondary};
            alternate-background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
        }}
        QListWidget::item:selected {{
            background-color: {p.accent_soft};
            color: {p.text_primary};
        }}
        /* Scrollbars — consistent across themes */
        QScrollBar:vertical {{
            background: {p.bg_primary};
            width: 10px;
            border: none;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {p.border};
            border-radius: 5px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {p.text_muted}; }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{
            background: {p.bg_primary};
            height: 10px;
            border: none;
        }}
        QScrollBar::handle:horizontal {{
            background: {p.border};
            border-radius: 5px;
            min-width: 20px;
        }}
        QScrollBar::handle:horizontal:hover {{ background: {p.text_muted}; }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{ width: 0; }}

        /* ────────────────────────────────────────────────────────────
           Helper object names — widgets can just setObjectName() to
           pick up these styles instead of hardcoding per-widget QSS.
           Using these keeps label styling consistent across modules
           and means dark mode "just works" for every label.
           ──────────────────────────────────────────────────────────── */

        /* Italic muted instruction/hint text — used for "Click to..."
           messages, subtitles, explanatory captions. */
        QLabel#hintLabel {{
            color: {p.text_muted};
            font-style: italic;
            background-color: transparent;
        }}

        /* Status label in its neutral/idle state — bold, muted. */
        QLabel#statusMuted {{
            color: {p.text_muted};
            font-weight: bold;
            background-color: transparent;
        }}

        /* Status label when something succeeded / loaded. */
        QLabel#statusOk {{
            color: {p.success};
            font-weight: bold;
            background-color: transparent;
        }}

        /* Large section title at the top of a window. */
        QLabel#titleLabel {{
            color: {p.text_primary};
            font-size: 20px;
            font-weight: bold;
        }}

        /* Even larger dialog-heading title. */
        QLabel#dialogTitle {{
            color: {p.text_primary};
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 10px;
        }}

        /* Emphasised bold label inside a dialog (e.g. "Choose..." prompt). */
        QLabel#dialogInstruction {{
            color: {p.text_primary};
            font-size: 14px;
            font-weight: bold;
            margin: 10px;
        }}

        /* Small muted description text under a radio button etc. */
        QLabel#helpMuted {{
            color: {p.text_muted};
            margin-left: 20px;
            font-size: 11px;
            background-color: transparent;
        }}

        /* Blue info banner. */
        QLabel#helpInfo {{
            background-color: {p.accent_soft};
            color: {p.text_primary};
            padding: 10px;
            border-radius: 4px;
        }}

        /* Yellow warning banner. */
        QLabel#helpWarning {{
            background-color: {p.warning_bg};
            color: {p.text_primary};
            border: 1px solid {p.warning_border};
            padding: 10px;
            border-radius: 4px;
        }}

        /* Boxed instruction panel with a light background. */
        QFrame#instructionBox {{
            background-color: {p.bg_tertiary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 10px;
        }}

        /* Summary panel (e.g. "N samples, M particles detected"). */
        QLabel#summaryPanel {{
            background-color: {p.accent_soft};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 12px;
        }}

        /* Primary call-to-action button (green accent). */
        QPushButton#primaryBtn {{
            background-color: {p.success};
            color: {p.text_inverse};
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
            min-width: 80px;
        }}
        QPushButton#primaryBtn:hover {{ background-color: {p.accent_hover}; }}

        /* Neutral secondary button. */
        QPushButton#secondaryBtn {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
            min-width: 80px;
        }}
        QPushButton#secondaryBtn:hover {{
            background-color: {p.bg_hover};
            border-color: {p.accent};
        }}

        /* Warning-style button (orange/yellow). */
        QPushButton#warningBtn {{
            background-color: {p.warning};
            color: {p.text_primary};
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-weight: bold;
        }}
        QPushButton#warningBtn:hover {{
            background-color: {p.accent_hover};
            color: {p.text_inverse};
        }}

        /* Bordered table frame wrapper. */
        QFrame#tableFrame {{
            background-color: {p.bg_secondary};
            border: 1px solid {p.border};
            border-radius: 4px;
        }}
    """
        

def sidebar_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QWidget {{
            background-color: {p.bg_sidebar};
            color: {p.text_on_sidebar};
        }}
        QWidget#sidebar {{
            border-top-right-radius: 14px;
            border-bottom-right-radius: 14px;
        }}
        QPushButton {{
            background-color: transparent;
            color: {p.text_on_sidebar};
            text-align: left;
            padding: 12px 16px;
            border: none;
            border-radius: 6px;
            margin: 1px 8px;
        }}
        QPushButton:hover {{
            background-color: {p.accent};
            color: {p.text_inverse};
        }}
        QPushButton:pressed {{
            background-color: {p.accent_pressed};
            color: {p.text_inverse};
        }}
        QGroupBox {{
            font-weight: bold;
            font-size: 16px;
            border: none;
            margin-top: 0.8em;
            padding-top: 14px;
            color: {p.accent};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 8px;
            padding: 0 6px;
            color: {p.accent};
        }}
    """


def edge_strip_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QWidget {{
            background-color: transparent;
        }}
        QWidget:hover {{
            background-color: {p.accent};
        }}
    """


def sidebar_logo_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"font-size: 30px; color: {p.accent}; font-weight: bold;"


def sidebar_list_label_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QLabel {{
            font-weight: bold;
            font-size: 11px;
            padding: 16px 15px 6px 15px;
            color: {p.text_on_sidebar};
        }}
    """


def calibration_panel_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QTextEdit {{
            background-color: {p.bg_sidebar_alt};
            color: {p.text_on_sidebar};
            border: none;
            padding: 10px;
        }}
    """


def sample_table_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QTableWidget {{
            background-color: {p.bg_sidebar_alt};
            color: {p.text_on_sidebar};
            border: none;
            gridline-color: {p.bg_sidebar};
        }}
        QTableWidget::item {{
            padding: 5px;
        }}
        QTableWidget::item:selected {{
            background-color: {p.accent};
            color: {p.text_inverse};
        }}
        QHeaderView::section {{
            background-color: {p.bg_sidebar};
            color: {p.text_on_sidebar};
            padding: 5px;
            border: none;
        }}
    """


def parameters_table_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QTableWidget {{
            gridline-color: {p.border};
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 5px;
            font-size: 14px;
            alternate-background-color: {p.bg_tertiary};
        }}
        QTableWidget::item {{
            padding: 5px;
            min-height: 20px;
        }}
        QHeaderView::section {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            padding: 7px 7px;
            border: 1px solid {p.border};
            font-weight: bold;
            font-size: 12px;
            min-height: 25px;
        }}
        QTableWidget::item:selected {{
            background-color: {p.accent_soft};
            color: {p.text_primary};
        }}
    """


def info_button_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QPushButton {{
            background-color: {p.bg_secondary};
            border: 1px solid {p.border_subtle};
            border-radius: 16px;
            padding: 4px;
        }}
        QPushButton:hover {{
            background-color: {p.bg_hover};
            border: 1px solid {p.accent};
        }}
    """


def theme_toggle_button_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QPushButton {{
            background-color: {p.bg_secondary};
            border: 1px solid {p.border_subtle};
            border-radius: 16px;
            padding: 4px;
        }}
        QPushButton:hover {{
            background-color: {p.bg_hover};
            border: 1px solid {p.accent};
        }}
    """


def sidebar_toggle_button_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QPushButton {{
            border-radius: 16px;
            padding: 4px;
            margin: 0px;
            background-color: transparent;
        }}
        QPushButton:hover {{
            background-color: {p.bg_sidebar_alt};
        }}
    """


def primary_button_qss(p: Palette) -> str:
    """Used by batch_edit_button, show_all_signals_button, detect_button.
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QPushButton {{
            padding: 8px 15px;
            background-color: {p.accent};
            color: {p.text_inverse};
            border-radius: 4px;
            font-weight: bold;
            border: none;
        }}
        QPushButton:hover {{
            background-color: {p.accent_hover};
        }}
        QPushButton:pressed {{
            background-color: {p.accent_pressed};
        }}
        QPushButton:disabled {{
            background-color: {p.disabled};
            color: {p.text_muted};
        }}
        QPushButton:checked {{
            background-color: {p.success};
        }}
    """


def progress_bar_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QProgressBar {{
            border: 1px solid {p.border};
            border-radius: 3px;
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            text-align: center;
        }}
        QProgressBar::chunk {{
            background-color: {p.accent};
        }}
    """


def groupbox_qss(p: Palette) -> str:
    """Used by plot, control panel, summary group boxes.
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QGroupBox {{
            font-weight: bold;
            font-size: 14px;
            border: none;
            border-radius: 10px;
            margin-top: 1.4em;
            padding: 16px 10px 10px 10px;
            color: {p.text_secondary};
            background-color: {p.bg_secondary};
        }}
        QGroupBox#plotCard {{
            margin-top: 0px;
            padding: 6px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 14px;
            padding: 2px 6px;
            color: {p.text_secondary};
        }}
    """


def summary_label_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QLabel {{
            font-size: 13px;
            padding: 10px;
            color: {p.text_primary};
            background-color: {p.bg_tertiary};
            border-radius: 5px;
        }}
    """


def results_container_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QWidget {{
            background-color: {p.bg_tertiary};
            border-radius: 8px;
        }}
    """


def results_header_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QWidget {{
            background-color: {p.bg_secondary};
            border-radius: 6px;
            border: 1px solid {p.border_subtle};
        }}
    """


def results_title_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QLabel {{
            font-size: 18px;
            font-weight: bold;
            color: {p.text_primary};
            padding: 0px;
            background: transparent;
            border: none;
        }}
    """


def perf_tip_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QLabel {{
            font-size: 12px;
            color: {p.text_muted};
            font-style: italic;
            padding: 2px 8px;
            background-color: {p.warning_bg};
            border: 1px solid {p.warning_border};
            border-radius: 4px;
        }}
    """


def enhanced_checkbox_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    check_svg_b64 = (
        "PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9"
        "Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9"
        "Ik0xIDQuNUw0LjUgOEwxMSAxIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIi"
        "IHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8"
        "L3N2Zz4K"
    )
    return f"""
        QCheckBox {{
            font-size: 14px;
            font-weight: 500;
            padding: 8px 12px;
            color: {p.text_primary};
            background-color: {p.bg_secondary};
            border: 2px solid {p.border_subtle};
            border-radius: 8px;
            spacing: 8px;
        }}
        QCheckBox:hover {{
            background-color: {p.bg_hover};
            border: 2px solid {p.accent};
            color: {p.text_primary};
        }}
        QCheckBox:checked {{
            background-color: {p.accent_soft};
            border: 2px solid {p.accent};
            color: {p.text_primary};
        }}
        QCheckBox::indicator {{
            width: 20px;
            height: 20px;
            border-radius: 4px;
        }}
        QCheckBox::indicator:unchecked {{
            border: 2px solid {p.border};
            background-color: {p.bg_secondary};
        }}
        QCheckBox::indicator:unchecked:hover {{
            border: 2px solid {p.accent};
            background-color: {p.bg_hover};
        }}
        QCheckBox::indicator:checked {{
            border: 2px solid {p.accent};
            background-color: {p.accent};
            image: url(data:image/svg+xml;base64,{check_svg_b64});
        }}
        QCheckBox::indicator:checked:hover {{
            background-color: {p.accent_hover};
            border: 2px solid {p.accent_hover};
        }}
    """


def table_header_label_qss(p: Palette, bg_color: str, text_color: str) -> str:
    """The create_table_header helper takes explicit colors; this keeps that API
    but funnels through the theme-aware border.
    Args:
        p (Palette): The p.
        bg_color (str): The bg color.
        text_color (str): The text color.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QLabel {{
            font-size: 16px;
            font-weight: bold;
            color: {text_color};
            padding: 12px 15px;
            background-color: {bg_color};
            border-radius: 6px;
            border: 1px solid {p.border_subtle};
        }}
    """


def context_menu_qss(p: Palette) -> str:
    """
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QMenu {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            padding: 4px;
        }}
        QMenu::item {{
            padding: 6px 24px 6px 12px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background-color: {p.accent_soft};
            color: {p.text_primary};
        }}
        QMenu::separator {{
            height: 1px;
            background: {p.border_subtle};
            margin: 4px 8px;
        }}
    """


def results_table_qss(p: Palette) -> str:
    """Styling for results_table and multi_element_table (data tables under
    the Results Display section).
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QTableWidget {{
            gridline-color: {p.border};
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            font-size: 13px;
            alternate-background-color: {p.bg_tertiary};
            selection-background-color: {p.accent};
            selection-color: {p.text_inverse};
        }}
        QTableWidget::item {{
            padding: 4px;
            color: {p.text_primary};
        }}
        QTableWidget::item:selected {{
            background-color: {p.accent};
            color: {p.text_inverse};
        }}
        QHeaderView::section {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            padding: 6px 7px;
            border: none;
            border-right: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
            font-weight: bold;
            font-size: 12px;
        }}
        QHeaderView::section:vertical {{
            background-color: {p.bg_tertiary};
            color: {p.text_secondary};
            padding: 4px 8px;
        }}
        QTableCornerButton::section {{
            background-color: {p.bg_tertiary};
            border: none;
            border-right: 1px solid {p.border};
            border-bottom: 1px solid {p.border};
        }}
    """


def dialog_qss(p: Palette) -> str:
    """Generic QDialog styling — covers background, labels, group boxes,
    and radio buttons inside popup dialogs. Use for dialogs you don't have
    direct control over creating.
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        QDialog {{
            background-color: {p.bg_primary};
            color: {p.text_primary};
        }}
        QDialog QLabel {{
            color: {p.text_primary};
            background-color: transparent;
        }}
        QDialog QGroupBox {{
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 6px;
            margin-top: 1em;
            padding-top: 10px;
            background-color: {p.bg_secondary};
        }}
        QDialog QGroupBox::title {{
            subcontrol-origin: margin;
            padding: 0 8px;
            color: {p.text_primary};
        }}
        QDialog QRadioButton {{
            color: {p.text_primary};
            background-color: transparent;
            padding: 4px;
            spacing: 6px;
        }}
        QDialog QRadioButton::indicator {{
            width: 16px;
            height: 16px;
        }}
        QDialog QRadioButton::indicator:unchecked {{
            border: 2px solid {p.border};
            border-radius: 9px;
            background-color: {p.bg_secondary};
        }}
        QDialog QRadioButton::indicator:checked {{
            border: 2px solid {p.accent};
            border-radius: 9px;
            background-color: {p.bg_secondary};
        }}
        QDialog QPushButton {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 6px 16px;
            min-width: 80px;
        }}
        QDialog QPushButton:hover {{
            background-color: {p.bg_hover};
            border: 1px solid {p.accent};
        }}
        QDialog QPushButton:default {{
            background-color: {p.accent};
            color: {p.text_inverse};
            border: 1px solid {p.accent};
        }}
        QDialog QPushButton:default:hover {{
            background-color: {p.accent_hover};
        }}

        /* Inputs inside dialogs — match main-window input styling so dark
           mode actually reaches these widgets instead of falling back to
           the OS default (white on macOS). */
        QDialog QLineEdit,
        QDialog QComboBox,
        QDialog QSpinBox,
        QDialog QDoubleSpinBox {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 4px 8px;
            selection-background-color: {p.accent};
            selection-color: {p.text_inverse};
        }}
        QDialog QLineEdit:focus,
        QDialog QComboBox:focus,
        QDialog QSpinBox:focus,
        QDialog QDoubleSpinBox:focus {{
            border: 1px solid {p.accent};
        }}
        QDialog QLineEdit:disabled,
        QDialog QComboBox:disabled,
        QDialog QSpinBox:disabled,
        QDialog QDoubleSpinBox:disabled {{
            background-color: {p.bg_secondary};
            color: {p.text_muted};
            border: 1px solid {p.border_subtle};
        }}
        QDialog QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QDialog QComboBox QAbstractItemView {{
            background-color: {p.bg_secondary};
            color: {p.text_primary};
            selection-background-color: {p.accent_soft};
            selection-color: {p.text_primary};
            border: 1px solid {p.border};
            outline: 0;
        }}

        /* List widgets — the main culprit of the white patches in the
           Batch Edit dialog. */
        QDialog QListWidget {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 4px;
            padding: 4px;
            outline: 0;
        }}
        QDialog QListWidget::item {{
            padding: 4px 8px;
            border-radius: 3px;
            color: {p.text_primary};
        }}
        QDialog QListWidget::item:hover {{
            background-color: {p.bg_hover};
        }}
        QDialog QListWidget::item:selected {{
            background-color: {p.accent_soft};
            color: {p.text_primary};
        }}
        QDialog QListWidget::item:selected:active {{
            background-color: {p.accent};
            color: {p.text_inverse};
        }}

        /* Scroll areas inside dialogs (the Elements list container). */
        QDialog QScrollArea {{
            background-color: {p.bg_tertiary};
            border: 1px solid {p.border};
            border-radius: 4px;
        }}
        QDialog QScrollArea > QWidget > QWidget {{
            background-color: {p.bg_tertiary};
        }}
        QDialog QScrollBar:vertical {{
            background: {p.bg_tertiary};
            width: 10px;
            border: none;
            margin: 0;
        }}
        QDialog QScrollBar::handle:vertical {{
            background: {p.border};
            border-radius: 5px;
            min-height: 20px;
        }}
        QDialog QScrollBar::handle:vertical:hover {{
            background: {p.text_muted};
        }}
        QDialog QScrollBar::add-line:vertical,
        QDialog QScrollBar::sub-line:vertical {{
            height: 0;
        }}

        /* Checkboxes inside dialogs — simple indicator styling so the box
           itself is visible on dark backgrounds. */
        QDialog QCheckBox {{
            color: {p.text_primary};
            background-color: transparent;
            spacing: 6px;
            padding: 2px;
        }}
        QDialog QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 3px;
        }}
        QDialog QCheckBox::indicator:unchecked {{
            border: 1px solid {p.border};
            background-color: {p.bg_tertiary};
        }}
        QDialog QCheckBox::indicator:unchecked:hover {{
            border: 1px solid {p.accent};
        }}
        QDialog QCheckBox::indicator:checked {{
            border: 1px solid {p.accent};
            background-color: {p.accent};
        }}
    """


def tier_colors(p: Palette) -> dict:
    """Returns a dict mapping tier name -> QColor-compatible hex string.
    Replacement for hardcoded (255,200,200) style row backgrounds.
    Args:
        p (Palette): The p.
    """
    return {
        'critical': p.tier_critical,
        'high': p.tier_high,
        'medium': p.tier_medium,
        'low': p.tier_low,
        'text': p.tier_text,
    }


def html_table_css(p: Palette) -> str:
    """CSS block for HTML tables rendered inside QLabel/QTextEdit via RichText.
    Qt's rich-text engine supports a subset of CSS; we stick to attributes
    that are known to work (border, background-color, color, padding).

    Usage:
        html = f"<style>{html_table_css(theme.palette)}</style><table>...</table>"
        label.setText(html)
    Args:
        p (Palette): The p.
    Returns:
        str: Result of the operation.
    """
    return f"""
        table {{
            border-collapse: collapse;
            width: 100%;
            color: {p.text_primary};
            background-color: {p.bg_secondary};
        }}
        th, td {{
            border: 1px solid {p.border};
            padding: 8px;
            text-align: left;
            color: {p.text_primary};
        }}
        th {{
            background-color: {p.bg_tertiary};
            color: {p.text_primary};
            font-weight: bold;
        }}
        td {{
            background-color: {p.bg_secondary};
        }}
        .no-particles {{
            background-color: {p.warning_bg};
            color: {p.text_primary};
        }}
        .warning {{
            background-color: {p.warning_bg};
            color: {p.text_primary};
        }}
        .info {{
            background-color: {p.accent_soft};
            color: {p.text_primary};
        }}
    """