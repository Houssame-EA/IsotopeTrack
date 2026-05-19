from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import time
import traceback
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSplitter, QTextEdit, QVBoxLayout,
    QWidget,
)
import qtawesome as qta


# ---------------------------------------------------------------------------
#  Log directory
# ---------------------------------------------------------------------------

def _get_log_dir() -> Path:
    """Return a writable log directory for all platforms and packaging modes.
    Returns:
        Path: Result of the operation.
    """
    if getattr(sys, 'frozen', False):
        if sys.platform == "darwin":
            log_dir = Path.home() / "Library" / "Logs" / "IsotopeTrack"
        elif sys.platform == "win32":
            local = os.environ.get("LOCALAPPDATA", str(Path.home()))
            log_dir = Path(local) / "IsotopeTrack" / "logs"
        else:
            xdg = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
            log_dir = Path(xdg) / "IsotopeTrack" / "logs"
    else:
        log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


LOG_DIR = _get_log_dir()


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

_LEVEL_FG: dict[str, dict[str, str]] = {
    "dark": {
        "DEBUG":    "#8a9ba8",
        "INFO":     "#4ec9b0",
        "WARNING":  "#ffcc02",
        "ERROR":    "#f44747",
        "CRITICAL": "#ff5555",
    },
    "light": {
        "DEBUG":    "#4a6a8a",
        "INFO":     "#1a7f6f",
        "WARNING":  "#9a6f00",
        "ERROR":    "#c0392b",
        "CRITICAL": "#8e0000",
    },
}

_LEVEL_BG: dict[str, dict[str, str]] = {
    "dark": {
        "DEBUG":    "#1e1e1e",
        "INFO":     "#1e2a2a",
        "WARNING":  "#2a2500",
        "ERROR":    "#2a1515",
        "CRITICAL": "#3a0000",
    },
    "light": {
        "DEBUG":    "#f8f9fa",
        "INFO":     "#f0faf8",
        "WARNING":  "#fffbe6",
        "ERROR":    "#fff5f5",
        "CRITICAL": "#ffeef0",
    },
}

_ACTION_FG: dict[str, dict[str, str]] = {
    "dark": {
        "CLICK":            "#00bcd4",
        "MENU":             "#ff9800",
        "DIALOG_OPEN":      "#b39ddb",
        "FILE_OP":          "#81c784",
        "DATA_OP":          "#64b5f6",
        "ANALYSIS":         "#f48fb1",
        "PERFORMANCE":      "#ff8a65",
        "STARTUP":          "#aed581",
        "SAMPLE_SELECT":    "#4db6ac",
        "PARAMETER_CHANGE": "#7986cb",
        "NEW_WINDOW":       "#90a4ae",
        "ERROR":            "#f44747",
    },
    "light": {
        "CLICK":            "#0097a7",
        "MENU":             "#e65100",
        "DIALOG_OPEN":      "#7b1fa2",
        "FILE_OP":          "#2e7d32",
        "DATA_OP":          "#1565c0",
        "ANALYSIS":         "#ad1457",
        "PERFORMANCE":      "#bf360c",
        "STARTUP":          "#558b2f",
        "SAMPLE_SELECT":    "#00695c",
        "PARAMETER_CHANGE": "#283593",
        "NEW_WINDOW":       "#37474f",
        "ERROR":            "#c0392b",
    },
}

_ACTION_BG: dict[str, str] = {
    "dark":  "#1a2030",
    "light": "#eff4ff",
}

_LEVEL_ICONS: dict[str, tuple[str, str]] = {
    "DEBUG":    ("fa6s.bug",                  "#8a9ba8"),
    "INFO":     ("fa6s.circle-info",          "#4ec9b0"),
    "WARNING":  ("fa6s.triangle-exclamation", "#ffcc02"),
    "ERROR":    ("fa6s.circle-xmark",         "#f44747"),
    "CRITICAL": ("fa6s.skull-crossbones",     "#ff5555"),
    "USER":     ("fa6s.user",                 "#00bcd4"),
}

_MAX_GUI_ENTRIES = 5_000
_GUI_REFRESH_MS  = 80


def _mode(palette=None) -> str:
    """Return 'dark' or 'light' given a Palette object or the live ThemeManager.
    Args:
        palette (Any): Colour palette object.
    Returns:
        str: Result of the operation.
    """
    if palette is not None:
        return palette.name if hasattr(palette, "name") else str(palette)
    try:
        from theme import ThemeManager
        return "dark" if ThemeManager().is_dark else "light"
    except Exception:
        return "dark"


# ---------------------------------------------------------------------------
#  Thread-safe Qt signal bridge
# ---------------------------------------------------------------------------

class _LogSignaller(QObject):
    log_record = Signal(dict)


# ---------------------------------------------------------------------------
#  Qt GUI log handler
# ---------------------------------------------------------------------------

class EnhancedQtLogHandler(logging.Handler):
    """Routes Python log records to the GUI log window via Qt signals."""

    def __init__(self, log_window: "EnhancedLogWindow | None" = None):
        """
        Args:
            log_window ('EnhancedLogWindow | None'): The log window.
        """
        super().__init__()
        self._signaller  = _LogSignaller()
        self._log_window = log_window
        if log_window:
            self._signaller.log_record.connect(log_window._receive_entry)

    def emit(self, record: logging.LogRecord) -> None:
        """
        Args:
            record (logging.LogRecord): The record.
        Returns:
            None
        """
        try:
            self._signaller.log_record.emit(_build_entry(record))
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
#  Entry builder
# ---------------------------------------------------------------------------

def _build_entry(record: logging.LogRecord) -> dict:
    """Convert a LogRecord to a rich entry dict used by the GUI and JSONL.
    Args:
        record (logging.LogRecord): The record.
    Returns:
        dict: Result of the operation.
    """
    ts      = datetime.fromtimestamp(record.created)
    context = getattr(record, "context", {}) or {}
    exc_text = ""
    if record.exc_info:
        exc_text = "".join(traceback.format_exception(*record.exc_info))
    elif record.exc_text:
        exc_text = record.exc_text

    return {
        "timestamp":      ts.strftime("%H:%M:%S.%f")[:-3],
        "timestamp_full": ts.isoformat(),
        "level":          record.levelname,
        "logger":         record.name,
        "module":         record.module,
        "funcName":       record.funcName,
        "lineno":         record.lineno,
        "message":        record.getMessage(),
        "context":        context,
        "exc_text":       exc_text,
        "is_user_action": "[USER ACTION]" in record.getMessage(),
    }


# ---------------------------------------------------------------------------
#  JSONL file handler
# ---------------------------------------------------------------------------

class JsonlFileHandler(logging.Handler):
    """Appends structured JSON-lines to a .jsonl log file."""

    def __init__(self, filepath: Path):
        """
        Args:
            filepath (Path): The filepath.
        """
        super().__init__()
        self._fp = open(filepath, "a", encoding="utf-8")

    def emit(self, record: logging.LogRecord) -> None:
        """
        Args:
            record (logging.LogRecord): The record.
        Returns:
            None
        """
        try:
            self._fp.write(json.dumps(_build_entry(record), default=str) + "\n")
            self._fp.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        """
        Returns:
            None
        """
        try:
            self._fp.close()
        except Exception:
            pass
        super().close()


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

class _BufferHandler(logging.Handler):
    """Fills a shared list with entry dicts until the GUI window takes over."""

    def __init__(self, buffer: list):
        """
        Args:
            buffer (list): The buffer.
        """
        super().__init__()
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        """
        Args:
            record (logging.LogRecord): The record.
        Returns:
            None
        """
        try:
            self._buffer.append(_build_entry(record))
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
#  Statistics bar
# ---------------------------------------------------------------------------

class _LogStatsBar(QFrame):
    """Live counters at the bottom of the log window."""

    def __init__(self, parent: QWidget | None = None):
        """
        Args:
            parent (QWidget | None): Parent widget or object.
        """
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(16)

        self._counts: dict[str, int] = {
            "DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0, "USER": 0,
        }
        self._labels: dict[str, QLabel] = {}

        specs = [
            ("DEBUG",    _LEVEL_ICONS["DEBUG"]),
            ("INFO",     _LEVEL_ICONS["INFO"]),
            ("WARNING",  _LEVEL_ICONS["WARNING"]),
            ("ERROR",    _LEVEL_ICONS["ERROR"]),
            ("CRITICAL", _LEVEL_ICONS["CRITICAL"]),
            ("USER",     _LEVEL_ICONS["USER"]),
        ]
        for key, (icon_name, color) in specs:
            lbl_icon = QLabel()
            lbl_icon.setPixmap(qta.icon(icon_name, color=color).pixmap(14, 14))
            lbl_count = QLabel("0")
            lbl_count.setStyleSheet(
                f"color:{color}; font-weight:bold; font-size:12px;"
                f" font-family:Consolas,monospace;"
            )
            layout.addWidget(lbl_icon)
            layout.addWidget(lbl_count)
            self._labels[key] = lbl_count

        layout.addStretch()

        self._session_lbl = QLabel("")
        layout.addWidget(self._session_lbl)

        self._t0    = datetime.now()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1_000)

        self.apply_theme()

    # -- public ------------------------------------------------------------

    def apply_theme(self, palette=None) -> None:
        """
        Args:
            palette (Any): Colour palette object.
        Returns:
            None
        """
        mode = _mode(palette)
        if mode == "dark":
            bg, border, muted = "#252526", "#3c3c3c", "#777"
        else:
            bg, border, muted = "#f0f4f8", "#cccccc", "#666"
        self.setStyleSheet(
            f"QFrame {{ background:{bg}; border-top:1px solid {border}; }}"
            f"QLabel {{ color:{muted}; font-size:12px; font-family:Consolas,monospace; }}"
        )
        self._session_lbl.setStyleSheet(
            f"color:{muted}; font-size:11px; font-family:Consolas,monospace;"
        )

    def increment(self, key: str) -> None:
        """
        Args:
            key (str): Dictionary or storage key.
        Returns:
            None
        """
        if key in self._counts:
            self._counts[key] += 1
            self._labels[key].setText(str(self._counts[key]))

    def reset(self) -> None:
        """
        Returns:
            None
        """
        for k in self._counts:
            self._counts[k] = 0
            self._labels[k].setText("0")
        self._t0 = datetime.now()

    # -- private -----------------------------------------------------------

    def _tick(self) -> None:
        """
        Returns:
            None
        """
        elapsed = int((datetime.now() - self._t0).total_seconds())
        h, r    = divmod(elapsed, 3600)
        m, s    = divmod(r, 60)
        self._session_lbl.setText(f"Session  {h:02d}:{m:02d}:{s:02d}")


# ---------------------------------------------------------------------------
#  Context / stack-trace panel
# ---------------------------------------------------------------------------

class _ContextPanel(QFrame):
    """Formatted key-value display for a selected log entry's context."""

    def __init__(self, parent: QWidget | None = None):
        """
        Args:
            parent (QWidget | None): Parent widget or object.
        """
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setMaximumHeight(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        title_row = QHBoxLayout()
        self._title_lbl = QLabel("  Context / Stack Trace")
        self._title_lbl.setObjectName("CtxTitle")
        title_row.addWidget(self._title_lbl)
        title_row.addStretch()

        self._copy_btn = QPushButton()
        self._copy_btn.setIcon(qta.icon("fa6s.copy", color="#888"))
        self._copy_btn.setToolTip("Copy to clipboard")
        self._copy_btn.setFixedSize(22, 22)
        self._copy_btn.setFlat(True)
        self._copy_btn.clicked.connect(self._copy_text)
        title_row.addWidget(self._copy_btn)
        layout.addLayout(title_row)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(QFont("Consolas", 11))
        layout.addWidget(self._text)

        self.apply_theme()

    # -- public ------------------------------------------------------------

    def apply_theme(self, palette=None) -> None:
        """
        Args:
            palette (Any): Colour palette object.
        Returns:
            None
        """
        mode = _mode(palette)
        if mode == "dark":
            frame_bg   = "#252526"
            border     = "#3c3c3c"
            title_fg   = "#888"
            text_bg    = "#1e1e1e"
            text_fg    = "#d4d4d4"
            icon_color = "#888"
        else:
            frame_bg   = "#f4f4f6"
            border     = "#cccccc"
            title_fg   = "#555"
            text_bg    = "#ffffff"
            text_fg    = "#2c3e50"
            icon_color = "#555"

        self.setStyleSheet(
            f"QFrame {{ background:{frame_bg}; border-top:1px solid {border}; }}"
            f"QLabel#CtxTitle {{ color:{title_fg}; font-size:11px;"
            f"  font-weight:bold; font-family:Consolas,monospace; }}"
        )
        self._text.setStyleSheet(
            f"QTextEdit {{ background:{text_bg}; color:{text_fg}; border:none; }}"
        )
        self._copy_btn.setIcon(qta.icon("fa6s.copy", color=icon_color))

    def show_entry(self, entry: dict) -> None:
        """
        Args:
            entry (dict): The entry.
        Returns:
            None
        """
        lines: list[str] = []
        ctx = entry.get("context") or {}
        if ctx:
            lines.append("── Context ─────────────────────────────────────")
            for k, v in ctx.items():
                if isinstance(v, dict):
                    lines.append(f"  {k}:")
                    for sk, sv in v.items():
                        lines.append(f"      {sk}: {sv}")
                else:
                    lines.append(f"  {k}: {v}")

        exc = entry.get("exc_text", "")
        if exc:
            lines.append("")
            lines.append("── Exception / Stack Trace ─────────────────────")
            lines.extend(exc.rstrip().splitlines())

        if entry.get("level") == "DEBUG":
            lines.append("")
            lines.append("── Source ──────────────────────────────────────")
            lines.append(
                f"  {entry.get('logger')} › {entry.get('funcName')}()  "
                f"line {entry.get('lineno')}  [{entry.get('module')}]"
            )

        self._text.setPlainText("\n".join(lines) if lines else "(no context)")

    def clear(self) -> None:
        """
        Returns:
            None
        """
        self._text.clear()

    # -- private -----------------------------------------------------------

    def _copy_text(self) -> None:
        """
        Returns:
            None
        """
        QApplication.clipboard().setText(self._text.toPlainText())


# ---------------------------------------------------------------------------
#  Main log window
# ---------------------------------------------------------------------------

class EnhancedLogWindow(QDialog):
    """
    Full-featured log viewer with dark / light theme support.

    Key features
    ------------
    * Theme-aware colour coding — updates live when the app theme changes
    * Level-based colour coding with background tints (dark & light)
    * DEBUG lines show module / function / line number
    * ERROR / CRITICAL lines surface exception traces in the context panel
    * Rate-limited GUI refresh — no freeze on log bursts
    * Jump-to-next-error navigation
    * Copy selected lines to clipboard
    * Save as .txt or export as .jsonl
    * Live statistics bar with session timer
    * All entries are preserved when the window is hidden / closed
    """

    def __init__(self, parent: QWidget | None = None):
        """
        Args:
            parent (QWidget | None): Parent widget or object.
        """
        super().__init__(parent)
        self.setWindowTitle("IsotopeTrack — Application Log")
        self.setWindowIcon(qta.icon("fa6s.file-lines", color="#007acc"))
        self.resize(1_300, 750)
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )

        self._entries:        list[dict] = []
        self._pending:        list[dict] = []
        self._auto_scroll     = True
        self._unread_errors   = 0
        self._mode            = _mode()

        self._setup_ui()

        try:
            from theme import ThemeManager
            ThemeManager().themeChanged.connect(self._on_theme_changed)
        except Exception:
            pass

        self._flush_timer = QTimer(self)
        self._flush_timer.timeout.connect(self._flush_pending)
        self._flush_timer.start(_GUI_REFRESH_MS)

    # ------------------------------------------------------------------
    #  UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """
        Returns:
            None
        """
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── toolbar ─────────────────────────────────────────────────────
        self._toolbar = QFrame()
        self._toolbar.setObjectName("LogToolbar")
        tb = QHBoxLayout(self._toolbar)
        tb.setContentsMargins(10, 5, 10, 5)
        tb.setSpacing(8)

        self._title_lbl = QLabel("Application Log")
        self._title_lbl.setObjectName("LogTitle")
        tb.addWidget(self._title_lbl)

        tb.addWidget(self._vline())

        tb.addWidget(self._muted_lbl("Level"))
        self._level_filter = QComboBox()
        self._level_filter.addItems(
            ["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "USER ACTION"]
        )
        self._level_filter.setMinimumWidth(110)
        self._level_filter.currentTextChanged.connect(self._apply_filter)
        tb.addWidget(self._level_filter)

        tb.addWidget(self._muted_lbl("Action"))
        self._action_filter = QComboBox()
        self._action_filter.addItems(
            ["ALL", "CLICK", "MENU", "DIALOG_OPEN", "FILE_OP",
             "DATA_OP", "ANALYSIS", "PERFORMANCE", "STARTUP",
             "SAMPLE_SELECT", "PARAMETER_CHANGE"]
        )
        self._action_filter.setMinimumWidth(130)
        self._action_filter.currentTextChanged.connect(self._apply_filter)
        tb.addWidget(self._action_filter)

        tb.addWidget(self._muted_lbl("Module"))
        self._module_filter = QComboBox()
        self._module_filter.addItems(["ALL"])
        self._module_filter.setMinimumWidth(140)
        self._module_filter.currentTextChanged.connect(self._apply_filter)
        tb.addWidget(self._module_filter)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search messages…")
        self._search.setMinimumWidth(200)
        self._search.textChanged.connect(self._apply_filter)
        self._search.addAction(
            qta.icon("fa6s.magnifying-glass", color="#888"),
            QLineEdit.LeadingPosition,
        )
        tb.addWidget(self._search)

        tb.addStretch()

        self._jump_btn = QPushButton()
        self._jump_btn.setIcon(qta.icon("fa6s.bolt", color="#f44747"))
        self._jump_btn.setText(" Next Error")
        self._jump_btn.setToolTip("Jump to next ERROR / CRITICAL entry  (repeats cyclically)")
        self._jump_btn.setObjectName("JumpErrorBtn")
        self._jump_btn.clicked.connect(self._jump_to_next_error)
        tb.addWidget(self._jump_btn)

        self._copy_sel_btn = QPushButton()
        self._copy_sel_btn.setIcon(qta.icon("fa6s.copy", color="#888"))
        self._copy_sel_btn.setText(" Copy")
        self._copy_sel_btn.setToolTip("Copy selected log text to clipboard")
        self._copy_sel_btn.clicked.connect(self._copy_selected)
        tb.addWidget(self._copy_sel_btn)

        self._autoscroll_cb = QCheckBox("Auto-scroll")
        self._autoscroll_cb.setChecked(True)
        self._autoscroll_cb.toggled.connect(self._on_autoscroll_toggled)
        tb.addWidget(self._autoscroll_cb)

        self._wrap_cb = QCheckBox("Wrap")
        self._wrap_cb.setChecked(False)
        self._wrap_cb.toggled.connect(self._on_wrap_toggled)
        tb.addWidget(self._wrap_cb)

        tb.addWidget(self._vline())

        self._clear_btn = self._flat_btn("fa6s.trash",       "#888", "Clear all log entries")
        self._clear_btn.clicked.connect(self._clear)
        tb.addWidget(self._clear_btn)

        self._save_btn = self._flat_btn("fa6s.floppy-disk",  "#888", "Save log as .txt")
        self._save_btn.clicked.connect(self._save_txt)
        tb.addWidget(self._save_btn)

        self._export_btn = self._flat_btn("fa6s.file-export", "#888", "Export log as .jsonl")
        self._export_btn.clicked.connect(self._export_jsonl)
        tb.addWidget(self._export_btn)

        self._theme_btn = QPushButton()
        self._theme_btn.setFixedSize(28, 28)
        self._theme_btn.setFlat(True)
        self._theme_btn.setToolTip("Toggle dark / light theme")
        self._theme_btn.clicked.connect(self._toggle_theme)
        tb.addWidget(self._theme_btn)

        root.addWidget(self._toolbar)

        # ── splitter: log text | context panel ──────────────────────────
        self._splitter = QSplitter(Qt.Vertical)
        self._splitter.setHandleWidth(4)

        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setFont(QFont("Consolas", 12))
        self._log_text.setLineWrapMode(QTextEdit.NoWrap)
        self._log_text.cursorPositionChanged.connect(self._on_cursor_moved)
        self._splitter.addWidget(self._log_text)

        self._ctx_panel = _ContextPanel()
        self._splitter.addWidget(self._ctx_panel)
        self._splitter.setSizes([580, 150])

        root.addWidget(self._splitter)

        # ── stats bar ───────────────────────────────────────────────────
        self._stats = _LogStatsBar()
        root.addWidget(self._stats)

        # ── error-jump state ────────────────────────────────────────────
        self._error_positions: list[int] = []
        self._error_jump_idx  = 0

        self.apply_theme()

    # ------------------------------------------------------------------
    #  Small UI helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _muted_lbl(text: str) -> QLabel:
        """
        Args:
            text (str): Text string.
        Returns:
            QLabel: Result of the operation.
        """
        lbl = QLabel(text + ":")
        lbl.setObjectName("MutedLabel")
        return lbl

    @staticmethod
    def _vline() -> QFrame:
        """
        Returns:
            QFrame: Result of the operation.
        """
        f = QFrame()
        f.setFrameShape(QFrame.VLine)
        f.setFixedHeight(20)
        f.setObjectName("VDivider")
        return f

    @staticmethod
    def _flat_btn(icon_name: str, color: str, tooltip: str) -> QPushButton:
        """
        Args:
            icon_name (str): The icon name.
            color (str): Colour value.
            tooltip (str): The tooltip.
        Returns:
            QPushButton: Result of the operation.
        """
        btn = QPushButton()
        btn.setIcon(qta.icon(icon_name, color=color))
        btn.setToolTip(tooltip)
        btn.setFixedSize(28, 28)
        btn.setFlat(True)
        return btn

    # ------------------------------------------------------------------
    #  Theme
    # ------------------------------------------------------------------

    def _on_theme_changed(self, name: str) -> None:
        """Called by ThemeManager.themeChanged — re-theme and re-render.
        Args:
            name (str): Name string.
        Returns:
            None
        """
        self._mode = name
        self.apply_theme()
        self._full_render()

    def _toggle_theme(self) -> None:
        """
        Returns:
            None
        """
        try:
            from theme import ThemeManager
            ThemeManager().toggle()
        except Exception:
            pass

    def apply_theme(self, palette=None) -> None:
        """
        Apply dark or light stylesheet to every component.

        Call this at startup and whenever the theme changes.
        Accepts an optional Palette object; otherwise reads ThemeManager.
        Args:
            palette (Any): Colour palette object.
        Returns:
            None
        """
        if palette is not None:
            self._mode = _mode(palette)
        mode = self._mode

        if mode == "dark":
            win_bg        = "#1e1e1e"
            toolbar_bg    = "#2d2d2d"
            border        = "#3c3c3c"
            text_primary  = "#cccccc"
            text_muted    = "#888888"
            input_bg      = "#3c3c3c"
            input_fg      = "#d4d4d4"
            input_border  = "#555555"
            log_bg        = "#1e1e1e"
            sel_bg        = "#264f78"
            scroll_bg     = "#252526"
            scroll_handle = "#555555"
            splitter_h    = "#3c3c3c"
            jump_bg       = "#5a1a1a"
            jump_fg       = "#f44747"
            jump_border   = "#f44747"
            jump_hover    = "#7a2a2a"
            cb_color      = "#cccccc"
            theme_icon    = "fa6s.sun"
            theme_color   = "#ffcc02"
        else:
            win_bg        = "#f0f4f8"
            toolbar_bg    = "#ffffff"
            border        = "#cccccc"
            text_primary  = "#2c3e50"
            text_muted    = "#666666"
            input_bg      = "#ffffff"
            input_fg      = "#2c3e50"
            input_border  = "#aaaaaa"
            log_bg        = "#fafafa"
            sel_bg        = "#c8e4fb"
            scroll_bg     = "#f0f0f0"
            scroll_handle = "#aaaaaa"
            splitter_h    = "#cccccc"
            jump_bg       = "#fde8e8"
            jump_fg       = "#c0392b"
            jump_border   = "#c0392b"
            jump_hover    = "#f9c8c8"
            cb_color      = "#2c3e50"
            theme_icon    = "fa6s.moon"
            theme_color   = "#5a7aaa"

        self._theme_btn.setIcon(qta.icon(theme_icon, color=theme_color))
        self._theme_btn.setToolTip(
            "Switch to light theme" if mode == "dark" else "Switch to dark theme"
        )

        self.setStyleSheet(f"QDialog {{ background:{win_bg}; }}")

        self._toolbar.setStyleSheet(f"""
            QFrame#LogToolbar {{
                background: {toolbar_bg};
                border-bottom: 1px solid {border};
            }}
            QLabel {{
                color: {text_primary};
                font-size: 12px;
            }}
            QLabel#LogTitle {{
                color: {text_primary};
                font-size: 13px;
                font-weight: bold;
                font-family: Consolas, monospace;
            }}
            QLabel#MutedLabel {{
                color: {text_muted};
                font-size: 11px;
            }}
            QFrame#VDivider {{
                color: {border};
            }}
            QComboBox, QLineEdit {{
                background: {input_bg};
                color: {input_fg};
                border: 1px solid {input_border};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 12px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {input_bg};
                color: {input_fg};
                selection-background-color: {sel_bg};
            }}
            QCheckBox {{
                color: {cb_color};
                font-size: 12px;
            }}
            QPushButton {{
                background: transparent;
                color: {text_primary};
                border: 1px solid {input_border};
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: {input_bg};
                border-color: {text_muted};
            }}
            QPushButton:flat {{
                border: none;
                background: transparent;
            }}
            QPushButton:flat:hover {{
                background: {input_bg};
                border-radius: 4px;
            }}
            QPushButton#JumpErrorBtn {{
                background: {jump_bg};
                color: {jump_fg};
                border: 1px solid {jump_border};
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton#JumpErrorBtn:hover {{
                background: {jump_hover};
            }}
        """)

        self._log_text.setStyleSheet(f"""
            QTextEdit {{
                background: {log_bg};
                border: none;
                selection-background-color: {sel_bg};
            }}
            QScrollBar:vertical {{
                background: {scroll_bg};
                width: 10px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {scroll_handle};
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar:horizontal {{
                background: {scroll_bg};
                height: 10px;
            }}
            QScrollBar::handle:horizontal {{
                background: {scroll_handle};
                border-radius: 4px;
            }}
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{ width: 0; }}
        """)

        self._splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {splitter_h}; }}"
        )

        self._ctx_panel.apply_theme(palette)
        self._stats.apply_theme(palette)

    # ------------------------------------------------------------------
    #  Receiving records (from Qt handler via signal)
    # ------------------------------------------------------------------

    def _receive_entry(self, entry: dict) -> None:
        """Buffer incoming entries; actual rendering is done by rate-limiter.
        Args:
            entry (dict): The entry.
        Returns:
            None
        """
        self._pending.append(entry)

    def _flush_pending(self) -> None:
        """Batch-render all buffered entries at most every _GUI_REFRESH_MS.
        Returns:
            None
        """
        if not self._pending:
            return

        batch, self._pending = self._pending, []

        trim = len(self._entries) + len(batch) - _MAX_GUI_ENTRIES
        if trim > 0:
            self._entries = self._entries[trim:]
            self._entries.extend(batch)
            self._full_render()
            return

        self._entries.extend(batch)

        cursor = self._log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        for entry in batch:
            self._render_entry(entry, cursor)
            self._update_stats(entry)
            self._update_module_filter(entry)

        if self._auto_scroll:
            self._log_text.setTextCursor(cursor)
            self._log_text.ensureCursorVisible()

        errors = sum(1 for e in batch if e["level"] in ("ERROR", "CRITICAL"))
        if errors:
            self._unread_errors += errors
            self.setWindowTitle(
                f"IsotopeTrack — Log  [{self._unread_errors} new error(s)]"
            )

    # ------------------------------------------------------------------
    #  Rendering
    # ------------------------------------------------------------------

    def _render_entry(self, entry: dict, cursor: QTextCursor) -> None:
        """Append one formatted entry at *cursor*.
        Args:
            entry (dict): The entry.
            cursor (QTextCursor): The cursor.
        Returns:
            None
        """
        level       = entry["level"]
        is_ua       = entry["is_user_action"]
        action_type = entry.get("context", {}).get("action_type", "")
        mode        = self._mode

        level_fg_map  = _LEVEL_FG.get(mode, _LEVEL_FG["dark"])
        level_bg_map  = _LEVEL_BG.get(mode, _LEVEL_BG["dark"])
        action_fg_map = _ACTION_FG.get(mode, _ACTION_FG["dark"])

        if is_ua and action_type:
            fg = action_fg_map.get(action_type, action_fg_map.get("CLICK", "#00bcd4"))
            bg = _ACTION_BG.get(mode, "#1a2030")
        else:
            fg = level_fg_map.get(level, level_fg_map.get("INFO", "#d4d4d4"))
            bg = level_bg_map.get(level, level_bg_map.get("DEBUG", "#1e1e1e"))

        badge   = f" {'USER':<8} " if is_ua else f" {level:<8} "
        body_fg = "#d4d4d4" if mode == "dark" else "#2c3e50"
        ts_fg   = "#555555" if mode == "dark" else "#999999"

        fmt_ts = QTextCharFormat()
        fmt_ts.setForeground(QColor(ts_fg))
        fmt_ts.setBackground(QColor(bg))

        fmt_badge = QTextCharFormat()
        fmt_badge.setForeground(QColor(fg))
        fmt_badge.setBackground(QColor(bg))
        fmt_badge.setFontWeight(700 if level in ("ERROR", "CRITICAL", "WARNING") else 400)

        fmt_msg = QTextCharFormat()
        fmt_msg.setForeground(
            QColor(fg if level in ("ERROR", "CRITICAL", "WARNING") else body_fg)
        )
        fmt_msg.setBackground(QColor(bg))

        pos_before = cursor.position()

        cursor.setCharFormat(fmt_ts)
        cursor.insertText(f"[{entry['timestamp']}]")

        cursor.setCharFormat(fmt_badge)
        cursor.insertText(badge)

        if level == "DEBUG":
            fmt_mod = QTextCharFormat()
            fmt_mod.setForeground(
                QColor("#5a7a9a" if mode == "dark" else "#7a9ab0")
            )
            fmt_mod.setBackground(QColor(bg))
            fmt_mod.setFontItalic(True)
            cursor.setCharFormat(fmt_mod)
            cursor.insertText(
                f"{entry.get('module','?')}.{entry.get('funcName','?')}"
                f":{entry.get('lineno', 0)}  "
            )

        cursor.setCharFormat(fmt_msg)
        cursor.insertText(entry["message"])

        if entry.get("exc_text"):
            fmt_exc = QTextCharFormat()
            fmt_exc.setForeground(
                QColor("#f44747" if mode == "dark" else "#c0392b")
            )
            fmt_exc.setBackground(QColor(bg))
            first_line = entry["exc_text"].splitlines()[0]
            cursor.setCharFormat(fmt_exc)
            cursor.insertText(f"  ▶ {first_line}")

        cursor.setCharFormat(QTextCharFormat())
        cursor.insertText("\n")

        if level in ("ERROR", "CRITICAL"):
            self._error_positions.append(pos_before)

    def _full_render(self) -> None:
        """Re-render all entries from scratch (used after trim or theme change).
        Returns:
            None
        """
        self._log_text.clear()
        self._error_positions.clear()
        cursor = self._log_text.textCursor()
        for entry in self._entries:
            self._render_entry(entry, cursor)
        if self._auto_scroll:
            cursor.movePosition(QTextCursor.End)
            self._log_text.setTextCursor(cursor)
            self._log_text.ensureCursorVisible()

    def _update_stats(self, entry: dict) -> None:
        """
        Args:
            entry (dict): The entry.
        Returns:
            None
        """
        key = "USER" if entry["is_user_action"] else entry["level"]
        if key in self._stats._counts:
            self._stats.increment(key)
        else:
            self._stats.increment("INFO")

    def _update_module_filter(self, entry: dict) -> None:
        """
        Args:
            entry (dict): The entry.
        Returns:
            None
        """
        mod = entry.get("module", "")
        if mod and self._module_filter.findText(mod) < 0:
            self._module_filter.addItem(mod)

    # ------------------------------------------------------------------
    #  Filtering
    # ------------------------------------------------------------------

    def _apply_filter(self) -> None:
        """
        Returns:
            None
        """
        level_sel   = self._level_filter.currentText()
        action_sel  = self._action_filter.currentText()
        module_sel  = self._module_filter.currentText()
        search_text = self._search.text().lower()

        filtered: list[dict] = []
        for e in self._entries:
            if level_sel != "ALL":
                if level_sel == "USER ACTION":
                    if not e["is_user_action"]:
                        continue
                elif e["level"] != level_sel:
                    continue
            if action_sel != "ALL":
                if e.get("context", {}).get("action_type", "") != action_sel:
                    continue
            if module_sel != "ALL":
                if e.get("module", "") != module_sel:
                    continue
            if search_text:
                haystack = e["message"].lower() + str(e.get("context", "")).lower()
                if search_text not in haystack:
                    continue
            filtered.append(e)

        self._log_text.clear()
        self._error_positions.clear()
        cursor = self._log_text.textCursor()
        for entry in filtered:
            self._render_entry(entry, cursor)

        if self._auto_scroll:
            cursor.movePosition(QTextCursor.End)
            self._log_text.setTextCursor(cursor)
            self._log_text.ensureCursorVisible()

    # ------------------------------------------------------------------
    #  Context panel — cursor click
    # ------------------------------------------------------------------

    def _on_cursor_moved(self) -> None:
        """
        Returns:
            None
        """
        line_no = self._log_text.textCursor().blockNumber()
        if 0 <= line_no < len(self._entries):
            self._ctx_panel.show_entry(self._entries[line_no])
        else:
            self._ctx_panel.clear()

    # ------------------------------------------------------------------
    #  Jump-to-error
    # ------------------------------------------------------------------

    def _jump_to_next_error(self) -> None:
        """
        Returns:
            None
        """
        if not self._error_positions:
            return
        pos = self._error_positions[self._error_jump_idx % len(self._error_positions)]
        self._error_jump_idx += 1
        cursor = self._log_text.textCursor()
        cursor.setPosition(pos)
        self._log_text.setTextCursor(cursor)
        self._log_text.ensureCursorVisible()
        self._unread_errors = 0
        self.setWindowTitle("IsotopeTrack — Application Log")

    # ------------------------------------------------------------------
    #  Toolbar actions
    # ------------------------------------------------------------------

    def _on_autoscroll_toggled(self, checked: bool) -> None:
        """
        Args:
            checked (bool): Whether the item is checked.
        Returns:
            None
        """
        self._auto_scroll = checked
        if checked:
            cursor = self._log_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self._log_text.setTextCursor(cursor)

    def _on_wrap_toggled(self, checked: bool) -> None:
        """
        Args:
            checked (bool): Whether the item is checked.
        Returns:
            None
        """
        self._log_text.setLineWrapMode(
            QTextEdit.WidgetWidth if checked else QTextEdit.NoWrap
        )

    def _copy_selected(self) -> None:
        """
        Returns:
            None
        """
        text = self._log_text.textCursor().selectedText()
        if text:
            QApplication.clipboard().setText(text)

    def _clear(self) -> None:
        """
        Returns:
            None
        """
        self._entries.clear()
        self._pending.clear()
        self._error_positions.clear()
        self._error_jump_idx = 0
        self._unread_errors  = 0
        self._log_text.clear()
        self._ctx_panel.clear()
        self._stats.reset()
        self.setWindowTitle("IsotopeTrack — Application Log")

    def _save_txt(self) -> None:
        """
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog
        fname, _ = QFileDialog.getSaveFileName(
            self, "Save Log",
            f"isotope_track_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text files (*.txt)",
        )
        if not fname:
            return
        with open(fname, "w", encoding="utf-8") as fh:
            for e in self._entries:
                ctx = e.get("context") or {}
                ctx_str = ("  context: " + json.dumps(ctx, default=str)) if ctx else ""
                exc_str = (
                    "\n  " + e["exc_text"].replace("\n", "\n  ")
                ) if e.get("exc_text") else ""
                fh.write(
                    f"[{e['timestamp_full']}] {e['level']:8} | "
                    f"{e['module']}.{e['funcName']}:{e['lineno']} | "
                    f"{e['message']}{ctx_str}{exc_str}\n"
                )

    def _export_jsonl(self) -> None:
        """
        Returns:
            None
        """
        from PySide6.QtWidgets import QFileDialog
        fname, _ = QFileDialog.getSaveFileName(
            self, "Export JSONL",
            f"isotope_track_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl",
            "JSON Lines (*.jsonl)",
        )
        if not fname:
            return
        with open(fname, "w", encoding="utf-8") as fh:
            for e in self._entries:
                fh.write(json.dumps(e, default=str) + "\n")

    # ------------------------------------------------------------------
    #  Close → hide (preserves every log entry across show/hide cycles)
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """Hide instead of destroying so the full log history is always kept.
        Args:
            event (Any): Qt event object.
        Returns:
            None
        """
        event.ignore()
        self.hide()

    # ------------------------------------------------------------------
    #  Compatibility shim  (kept for any callers using the old API)
    # ------------------------------------------------------------------

    def add_log_message(
        self,
        level: str,
        message: str,
        timestamp: str,
        context: dict | None = None,
    ) -> None:
        """Compatibility shim — prefer connecting to _receive_entry via signal.
        Args:
            level (str): The level.
            message (str): Message string.
            timestamp (str): The timestamp.
            context (dict | None): The context.
        Returns:
            None
        """
        self._receive_entry({
            "timestamp":      timestamp,
            "timestamp_full": timestamp,
            "level":          level,
            "logger":         "IsotopeTrack",
            "module":         "",
            "funcName":       "",
            "lineno":         0,
            "message":        message,
            "context":        context or {},
            "exc_text":       "",
            "is_user_action": "[USER ACTION]" in message,
        })


# ---------------------------------------------------------------------------
#  User Action Logger
# ---------------------------------------------------------------------------

class UserActionLogger:
    """Tracks user interactions and analysis workflow steps."""

    def __init__(self, logger: logging.Logger):
        """
        Args:
            logger (logging.Logger): The logger.
        """
        self._logger        = logger
        self._session_start = datetime.now()
        self._action_count  = 0

    # -- generic -----------------------------------------------------------

    def log_action(
        self,
        action_type: str,
        description: str,
        context: dict | None = None,
    ) -> None:
        """
        Args:
            action_type (str): The action type.
            description (str): The description.
            context (dict | None): The context.
        Returns:
            None
        """
        self._action_count += 1
        ctx = dict(context or {})
        ctx.update(
            action_type   = action_type,
            session_time  = str(datetime.now() - self._session_start),
            action_number = self._action_count,
        )
        record = logging.LogRecord(
            name=self._logger.name, level=logging.INFO,
            pathname="", lineno=0,
            msg=f"[USER ACTION] {action_type}: {description}",
            args=(), exc_info=None,
        )
        record.context = ctx
        self._logger.handle(record)

    # -- convenience wrappers ──────────────────────────────────────────

    def log_click(self, widget_name: str, widget_type: str = "", extra: dict | None = None) -> None:
        """
        Args:
            widget_name (str): The widget name.
            widget_type (str): The widget type.
            extra (dict | None): The extra.
        Returns:
            None
        """
        self.log_action("CLICK", f"Clicked {widget_name}",
                        {"widget_name": widget_name, "widget_type": widget_type, **(extra or {})})

    def log_menu_action(self, menu: str, action: str) -> None:
        """
        Args:
            menu (str): QMenu object.
            action (str): QAction object.
        Returns:
            None
        """
        self.log_action("MENU", f"{menu} → {action}", {"menu": menu, "action": action})

    def log_dialog_open(self, name: str, kind: str = "") -> None:
        """
        Args:
            name (str): Name string.
            kind (str): The kind.
        Returns:
            None
        """
        self.log_action("DIALOG_OPEN", f"Opened {name}", {"dialog_name": name, "dialog_type": kind})

    def log_file_operation(self, op: str, path: str | Path, success: bool = True) -> None:
        """
        Args:
            op (str): The op.
            path (str | Path): File or directory path.
            success (bool): The success.
        Returns:
            None
        """
        self.log_action("FILE_OP", f"{op}: {path}",
                        {"operation": op, "file": str(path), "success": success})

    def log_data_operation(self, op: str, details: dict | None = None) -> None:
        """
        Args:
            op (str): The op.
            details (dict | None): The details.
        Returns:
            None
        """
        self.log_action("DATA_OP", f"Data op: {op}",
                        {"operation": op, "details": details or {}})

    def log_analysis_step(
        self,
        step: str,
        parameters: dict | None = None,
        results: dict | None = None,
    ) -> None:
        """
        Args:
            step (str): The step.
            parameters (dict | None): The parameters.
            results (dict | None): The results.
        Returns:
            None
        """
        self.log_action(
            "ANALYSIS", f"Analysis: {step}",
            {"step": step, "parameters": parameters or {}, "results": results or {}},
        )


# ---------------------------------------------------------------------------
#  Central logging manager
# ---------------------------------------------------------------------------

class EnhancedLoggingManager:
    """
    Creates and manages the root logger, file handlers, and the GUI log window.

    Pre-window buffer
    -----------------
    All log records emitted before ``create_log_window`` is called are
    stored in ``_pre_window_buffer``.  When the window is first opened the
    buffer is replayed so no startup messages are ever lost.
    """

    _pre_window_buffer: list[dict] = []

    def __init__(self) -> None:
        """
        Returns:
            None
        """
        self._log_window:         EnhancedLogWindow | None  = None
        self._qt_handler:         EnhancedQtLogHandler | None = None
        self._buffer_handler:     _BufferHandler | None     = None
        self._user_action_logger: UserActionLogger | None   = None
        self._setup_logging()
        self._install_exception_hook()

    # -- setup ─────────────────────────────────────────────────────────

    def _setup_logging(self) -> None:
        """
        Returns:
            None
        """
        self._logger = logging.getLogger("IsotopeTrack")
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers.clear()

        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
        ))
        self._logger.addHandler(ch)

        stamp    = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_path = LOG_DIR / f"isotope_track_{stamp}.log"
        try:
            fh = logging.handlers.RotatingFileHandler(
                str(log_path), maxBytes=5 * 1024 * 1024, backupCount=20, encoding="utf-8"
            )
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter(
                "%(asctime)s  %(levelname)-8s  %(name)s  "
                "%(module)s.%(funcName)s:%(lineno)d  %(message)s"
            ))
            self._logger.addHandler(fh)
        except Exception as exc:
            print(f"[logging_utils] Could not create rotating log file: {exc}")

        jsonl_path = LOG_DIR / f"isotope_track_{stamp}.jsonl"
        try:
            self._logger.addHandler(JsonlFileHandler(jsonl_path))
        except Exception as exc:
            print(f"[logging_utils] Could not create JSONL log file: {exc}")

        self._buffer_handler = _BufferHandler(self._pre_window_buffer)
        self._buffer_handler.setLevel(logging.DEBUG)
        self._logger.addHandler(self._buffer_handler)

        self._prune_old_logs(keep=50)
        self._user_action_logger = UserActionLogger(self._logger)

    def _install_exception_hook(self) -> None:
        """
        Returns:
            None
        """
        _orig = sys.excepthook

        def _hook(exc_type, exc_value, exc_tb):
            """
            Args:
                exc_type (Any): The exc type.
                exc_value (Any): The exc value.
                exc_tb (Any): The exc tb.
            """
            if issubclass(exc_type, KeyboardInterrupt):
                _orig(exc_type, exc_value, exc_tb)
                return
            tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            record  = logging.LogRecord(
                name=self._logger.name, level=logging.CRITICAL,
                pathname="", lineno=0,
                msg=f"Unhandled exception: {exc_type.__name__}: {exc_value}",
                args=(), exc_info=(exc_type, exc_value, exc_tb),
            )
            record.context = {"exception_type": exc_type.__name__, "traceback": tb_text}
            self._logger.handle(record)
            _orig(exc_type, exc_value, exc_tb)

        sys.excepthook = _hook

    @staticmethod
    def _prune_old_logs(keep: int = 50) -> None:
        """
        Args:
            keep (int): The keep.
        Returns:
            None
        """
        try:
            files = sorted(
                list(LOG_DIR.glob("isotope_track_*.log")) +
                list(LOG_DIR.glob("isotope_track_*.jsonl")),
                key=os.path.getmtime,
            )
            while len(files) > keep * 2:
                files.pop(0).unlink(missing_ok=True)
        except Exception:
            pass

    # -- public API ────────────────────────────────────────────────────

    def get_logger(self, name: str | None = None) -> logging.Logger:
        """
        Args:
            name (str | None): Name string.
        Returns:
            logging.Logger: Result of the operation.
        """
        if name:
            return logging.getLogger(f"IsotopeTrack.{name}")
        return self._logger

    def get_user_action_logger(self) -> UserActionLogger:
        """
        Returns:
            UserActionLogger: Result of the operation.
        """
        return self._user_action_logger

    def create_log_window(self, parent: QWidget | None = None) -> EnhancedLogWindow:
        """
        Args:
            parent (QWidget | None): Parent widget or object.
        Returns:
            EnhancedLogWindow: Result of the operation.
        """
        if self._log_window is None:
            self._log_window = EnhancedLogWindow(parent)

            self._qt_handler = EnhancedQtLogHandler(self._log_window)
            self._qt_handler.setLevel(logging.DEBUG)
            self._qt_handler.setFormatter(logging.Formatter("%(name)s — %(message)s"))
            self._logger.addHandler(self._qt_handler)

            if self._buffer_handler:
                self._logger.removeHandler(self._buffer_handler)
                self._buffer_handler = None

            for entry in self._pre_window_buffer:
                self._log_window._receive_entry(entry)

        return self._log_window

    def show_log_window(self, parent: QWidget | None = None) -> EnhancedLogWindow:
        """
        Args:
            parent (QWidget | None): Parent widget or object.
        Returns:
            EnhancedLogWindow: Result of the operation.
        """
        win = self.create_log_window(parent)
        win.show()
        win.raise_()
        win.activateWindow()
        return win


# ---------------------------------------------------------------------------
#  Module-level singleton
# ---------------------------------------------------------------------------

logging_manager = EnhancedLoggingManager()


# ---------------------------------------------------------------------------
#  Decorators
# ---------------------------------------------------------------------------

def log_user_action(action_type: str, description: str | None = None):
    """
    Decorator: automatically log a user action when the decorated method is called.

    Usage::

        @log_user_action('CLICK', 'Detect Peaks button')
        def detect_particles(self): ...
    Args:
        action_type (str): The action type.
        description (str | None): The description.
    Returns:
        object: Result of the operation.
    """
    def decorator(func):
        """
        Args:
            func (Any): Callable to invoke.
        Returns:
            object: Result of the operation.
        """
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            """
            Args:
                *args (Any): Additional positional arguments.
                **kwargs (Any): Additional keyword arguments.
            Returns:
                object: Result of the operation.
            """
            ual: UserActionLogger | None = getattr(self, "user_action_logger", None)
            if ual:
                ctx: dict = {}
                if getattr(self, "current_sample", None):
                    ctx["current_sample"] = self.current_sample
                if getattr(self, "selected_isotopes", None):
                    ctx["selected_elements"] = list(self.selected_isotopes.keys())
                ual.log_action(action_type, description or func.__name__, ctx)
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def log_performance(threshold_ms: float = 0):
    """
    Decorator: log wall-clock execution time.

    Only logs if elapsed time >= *threshold_ms* (default 0 = always log).

    Usage::

        @log_performance(threshold_ms=200)
        def detect_particles(self): ...
    Args:
        threshold_ms (float): The threshold ms.
    Returns:
        object: Result of the operation.
    """
    def decorator(func):
        """
        Args:
            func (Any): Callable to invoke.
        Returns:
            object: Result of the operation.
        """
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            """
            Args:
                *args (Any): Additional positional arguments.
                **kwargs (Any): Additional keyword arguments.
            Returns:
                object: Result of the operation.
            """
            t0 = time.perf_counter()
            try:
                result = func(self, *args, **kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - t0) * 1_000
                if elapsed_ms >= threshold_ms:
                    ual: UserActionLogger | None = (
                        getattr(self, "user_action_logger", None)
                        or logging_manager.get_user_action_logger()
                    )
                    if ual:
                        ctx = {
                            "function":   func.__qualname__,
                            "elapsed_ms": f"{elapsed_ms:.1f}",
                        }
                        if getattr(self, "current_sample", None):
                            ctx["sample"] = self.current_sample
                        ual.log_action(
                            "PERFORMANCE",
                            f"{func.__qualname__} finished in {elapsed_ms:.1f} ms",
                            ctx,
                        )
            return result
        return wrapper
    return decorator