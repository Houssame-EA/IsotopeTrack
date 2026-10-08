"""Chat window building blocks: message bubbles, tables, figures and inputs."""
import base64
import logging
import os
import re
import time
import uuid

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from results.ai.sandbox import to_float
from results.ai.theme import CODE_RE, UI_PREFS, Theme, fs, md_to_html, strip_thinking

_itk_log = logging.getLogger("IsotopeTrack.results.ai.widgets")

STREAM_RENDER_INTERVAL = 80


class AttachmentChip(QFrame):
    """Visual file-attachment card on the user side. No thumbnail — just icon + name + info."""
    _ICONS = {'image': '🖼', 'pdf': '📄', 'text': '📝',
              'csv': '📊', 'json': '{}', 'default': '📎'}
    _TYPE_LABELS = {
        '.pdf':'PDF', '.txt':'Text', '.csv':'CSV', '.json':'JSON',
        '.md':'Markdown', '.tsv':'TSV', '.png':'Image', '.jpg':'Image',
        '.jpeg':'Image', '.bmp':'Image', '.tiff':'Image', '.webp':'Image',
    }

    def __init__(self, name, kind, info=''):
        """Create the card.

        Args:
            name (str): File name.
            kind (str): ``image``, ``pdf`` or ``text``.
            info (str): Extra detail such as the size.
        """
        super().__init__()
        ext = os.path.splitext(name)[1].lower()
        type_label = self._TYPE_LABELS.get(ext, kind.upper())
        self.setContentsMargins(0, 3, 0, 3)

        root = QHBoxLayout(self); root.setContentsMargins(0,0,0,0)
        root.addStretch()

        self._card = QFrame()
        self._card.setMaximumWidth(300)
        cl = QHBoxLayout(self._card); cl.setContentsMargins(12, 10, 14, 10); cl.setSpacing(11)

        icon_w = QLabel(self._ICONS.get(kind, self._ICONS['default']))
        icon_w.setAlignment(Qt.AlignCenter)
        icon_w.setFixedSize(40, 40)
        icon_w.setStyleSheet("font-size:24px;border:none;background:transparent;")
        cl.addWidget(icon_w)

        text_col = QVBoxLayout(); text_col.setSpacing(3)
        display_name = name if len(name) <= 26 else name[:23] + '…'
        self._name_lbl = QLabel(display_name)
        self._name_lbl.setToolTip(name)
        parts = [type_label]
        if info: parts.append(info)
        self._info_lbl = QLabel('  •  '.join(parts))
        text_col.addWidget(self._name_lbl)
        text_col.addWidget(self._info_lbl)
        cl.addLayout(text_col, stretch=1)
        root.addWidget(self._card)
        self.apply_theme()

    def apply_theme(self):
        """Restyle for the current theme."""
        size = fs(); fs2 = fs(-2)
        if Theme.is_dark():
            bg, bd, fg, fg2 = '#1C2E4A', '#2D4A6E', '#CBD5E1', '#64748B'
        else:
            bg, bd, fg, fg2 = '#EFF6FF', '#BFDBFE', '#1E3A5F', '#4B6282'
        self._card.setStyleSheet(
            f"QFrame{{background:{bg};border:1px solid {bd};"
            f"border-radius:14px;border-bottom-right-radius:4px;}}")
        self._name_lbl.setStyleSheet(
            f"color:{fg};font-size:{size}px;font-weight:600;"
            f"background:transparent;border:none;")
        self._info_lbl.setStyleSheet(
            f"color:{fg2};font-size:{fs2}px;"
            f"background:transparent;border:none;")


class AttachmentPreview(QFrame):
    """
    with an image thumbnail (or file icon), filename, and a remove (×) button
    overlaid on the top-right corner.
    """
    removed = Signal(object)  
    _ICONS  = {'image':'🖼','pdf':'📄','text':'📝','csv':'📊','json':'{}','default':'📎'}

    def __init__(self, name, kind, image_b64=None):
        """Create the preview.

        Args:
            name (str): File name.
            kind (str): ``image``, ``pdf`` or ``text``.
            image_b64 (str): Image data for a thumbnail.
        """
        super().__init__()
        self._name = name
        self.setFixedHeight(58)
        self.setMinimumWidth(160)
        lo = QHBoxLayout(self); lo.setContentsMargins(8, 10, 28, 8); lo.setSpacing(8)

        self._thumb = QLabel(); self._thumb.setFixedSize(38, 38)
        self._thumb.setAlignment(Qt.AlignCenter)
        if kind == 'image' and image_b64:
            try:
                pix = QPixmap()
                pix.loadFromData(base64.b64decode(image_b64))
                scaled = pix.scaled(38, 38, Qt.KeepAspectRatioByExpanding,
                                    Qt.SmoothTransformation)
                self._thumb.setPixmap(scaled)
                self._thumb.setScaledContents(True)
                self._thumb.setStyleSheet("border-radius:6px;background:transparent;")
            except Exception:
                _itk_log.exception("Handled exception in __init__")
                self._thumb.setText(self._ICONS['image'])
                self._thumb.setStyleSheet("font-size:20px;background:transparent;")
        else:
            self._thumb.setText(self._ICONS.get(kind, self._ICONS['default']))
            self._thumb.setStyleSheet("font-size:20px;background:transparent;")
        lo.addWidget(self._thumb)

        disp = name if len(name) <= 18 else name[:15] + '…'
        self._lbl = QLabel(disp); self._lbl.setToolTip(name)
        lo.addWidget(self._lbl, stretch=1)

        self._x = QPushButton("✕", self)
        self._x.setFixedSize(22, 22)
        self._x.setCursor(QCursor(Qt.PointingHandCursor))
        self._x.setToolTip("Remove this file")
        self._x.clicked.connect(lambda: self.removed.emit(self))
        self._x.raise_()

        self.apply_theme()

    def resizeEvent(self, event):
        """Keep the remove button in the top-right corner."""
        super().resizeEvent(event)
        if hasattr(self, '_x'):
            self._x.move(self.width() - self._x.width() - 4, 4)

    def apply_theme(self):
        """Restyle for the current theme."""
        size = fs(-2)
        if Theme.is_dark():
            bg, bd, fg = '#243449', '#34506E', '#CBD5E1'
            x_bg, x_fg, x_hover_bg, x_hover_fg = '#334155', '#E2E8F0', '#DC2626', '#FFFFFF'
        else:
            bg, bd, fg = '#F1F5F9', '#CBD5E1', '#334155'
            x_bg, x_fg, x_hover_bg, x_hover_fg = '#FFFFFF', '#475569', '#EF4444', '#FFFFFF'
        self.setStyleSheet(
            f"AttachmentPreview{{background:{bg};border:1px solid {bd};border-radius:10px;}}")
        self._lbl.setStyleSheet(
            f"color:{fg};font-size:{size}px;font-weight:500;background:transparent;border:none;")
        self._x.setStyleSheet(
            f"QPushButton{{background:{x_bg};color:{x_fg};border:1px solid {bd};"
            f"border-radius:11px;font-size:12px;font-weight:700;padding:0;}}"
            f"QPushButton:hover{{background:{x_hover_bg};color:{x_hover_fg};"
            f"border-color:{x_hover_bg};}}")


class TextBubble(QFrame):
    """A chat message, from the user or the assistant."""
    def __init__(self, text, is_user=False):
        """Create the message.

        Args:
            text (str): Plain text for the user, markdown for the assistant.
            is_user (bool): Whether the user wrote it.
        """
        super().__init__()
        self._text = text; self._iu = is_user
        self._ts = time.strftime("%H:%M")
        self.setContentsMargins(0, 2, 0, 2)

        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        row  = QHBoxLayout(); row.setContentsMargins(0,0,0,0); row.setSpacing(6)

        self._b = QFrame()
        bl = QVBoxLayout(self._b); bl.setSpacing(4)

        if is_user:
            self._b.setMaximumWidth(UI_PREFS['bubble_max_width'])
            bl.setContentsMargins(16, 10, 16, 10)
        else:
            self._b.setMaximumWidth(16_777_215)
            bl.setContentsMargins(0, 4, 8, 4)

        self._l = QLabel(); self._l.setWordWrap(True)
        self._l.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        if not is_user:
            self._l.setTextFormat(Qt.RichText)
            self._l.setOpenExternalLinks(True)
            self._l.setTextInteractionFlags(
                Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        else:
            self._l.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bl.addWidget(self._l)

        if not is_user:
            footer = QHBoxLayout(); footer.setContentsMargins(0,3,0,0); footer.setSpacing(6)
            self._ts_lbl = QLabel(self._ts)
            self._ts_lbl.setVisible(UI_PREFS['show_timestamps'])
            footer.addWidget(self._ts_lbl)
            self._copy_btn = QPushButton("\u2398 Copy")
            self._copy_btn.setFixedHeight(20)
            self._copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
            self._copy_btn.clicked.connect(self._copy_text)
            footer.addWidget(self._copy_btn)
            footer.addStretch()
            bl.addLayout(footer)
        else:
            self._ts_lbl = None; self._copy_btn = None

        if is_user:
            row.addStretch(); row.addWidget(self._b)
        else:
            row.addWidget(self._b); row.addStretch()

        root.addLayout(row)
        self.apply_theme()

    def _copy_text(self):
        """Copy the message text to the clipboard."""
        plain = re.sub(r'<[^>]+>', '', self._text)
        QApplication.clipboard().setText(plain.strip())
        if self._copy_btn:
            self._copy_btn.setText("\u2713 Copied")
            QTimer.singleShot(1500, lambda: self._copy_btn.setText("\u2398 Copy")
                              if self._copy_btn else None)

    def apply_theme(self):
        """Restyle for the current theme."""
        size = fs(); fs2 = fs(-2)
        if self._iu:
            self._b.setStyleSheet(
                f"QFrame{{background:{Theme.c('user_bubble')};"
                f"border-radius:18px;border-bottom-right-radius:4px;}}")
            self._l.setStyleSheet(
                f"color:{Theme.c('user_text')};font-size:{size}px;line-height:1.5;")
            self._l.setText(self._text)
        else:
            self._b.setStyleSheet("QFrame{background:transparent;border:none;}")
            self._l.setStyleSheet(
                f"color:{Theme.c('text')};font-size:{size}px;line-height:1.65;")
            self._l.setText(md_to_html(self._text))
            if self._ts_lbl:
                self._ts_lbl.setStyleSheet(
                    f"color:{Theme.c('text_tertiary')};font-size:{fs2}px;")
                self._ts_lbl.setVisible(UI_PREFS['show_timestamps'])
            if self._copy_btn:
                self._copy_btn.setStyleSheet(
                    f"QPushButton{{background:transparent;border:none;"
                    f"color:{Theme.c('text_tertiary')};font-size:{fs2}px;padding:0 2px;}}"
                    f"QPushButton:hover{{color:{Theme.c('accent')};}}")


class StreamBubble(QFrame):
    """The assistant's reply while it is being written."""
    def __init__(self):
        """Create an empty reply that renders at a steady rate."""
        super().__init__()
        self._raw = ""; self._pend = []
        self.setContentsMargins(0, 2, 0, 2)
        lo = QVBoxLayout(self); lo.setContentsMargins(0,0,0,0)
        w = QHBoxLayout(); w.setContentsMargins(0,0,0,0)
        self._b = QFrame()
        self._b.setMaximumWidth(16_777_215) 
        bl = QVBoxLayout(self._b); bl.setContentsMargins(0, 4, 8, 4)
        self._l = QLabel(); self._l.setWordWrap(True); self._l.setTextFormat(Qt.RichText)
        self._l.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self._l.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        bl.addWidget(self._l); w.addWidget(self._b); w.addStretch(); lo.addLayout(w)
        self._t = QTimer(self); self._t.setInterval(STREAM_RENDER_INTERVAL)
        self._t.timeout.connect(self._flush); self.apply_theme()

    def append(self, tok):
        """Queue a streamed token.

        Args:
            tok (str): Token text.
        """
        self._pend.append(tok)
        if not self._t.isActive(): self._t.start()

    def _flush(self):
        """Render the tokens received so far."""
        if not self._pend: self._t.stop(); return
        self._raw += ''.join(self._pend); self._pend.clear()
        d = strip_thinking(self._raw).strip()
        self._l.setText(md_to_html(d) + f'<span style="color:{Theme.c("accent")};">▊</span>')

    def finalise(self, full=None):
        """Stop streaming and show the final text without code blocks.

        Args:
            full (str): The complete reply, which replaces what was streamed.
        """
        self._t.stop()
        if self._pend: self._raw += ''.join(self._pend); self._pend.clear()
        if full is not None:
            self._raw = full
        d = strip_thinking(self._raw).strip()
        d = CODE_RE.sub('', d)
        self._l.setText(md_to_html(d.strip()))

    def get_text(self):
        """Return the raw text received."""
        return self._raw

    def apply_theme(self):
        """Restyle for the current theme."""
        size = fs()
        self._b.setStyleSheet("QFrame{background:transparent;border:none;}")
        self._l.setStyleSheet(
            f"color:{Theme.c('text')};font-size:{size}px;line-height:1.65;")


class ExplorationBubble(QFrame):
    """Card that follows an exploration: plan, live findings, steps and summary.

    The plan and the findings stay visible while the model works. Each
    turn's code, tables and figures sit in a collapsible list of steps, and
    the final summary appears at the bottom.
    """

    def __init__(self, question):
        """Create the card.

        Args:
            question (str): What the user asked to explore.
        """
        super().__init__()
        self._question = question
        self._steps = 0
        self._expanded = False
        self.setContentsMargins(0, 4, 0, 4)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._card = QFrame()
        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(14, 12, 14, 12)
        cl.setSpacing(8)
        title_row = QHBoxLayout()
        self._title_lbl = QLabel("Exploring")
        title_row.addWidget(self._title_lbl)
        title_row.addStretch()
        self._badge = QLabel("Turn 0")
        title_row.addWidget(self._badge)
        cl.addLayout(title_row)
        self._q_lbl = QLabel(f'"{question}"')
        self._q_lbl.setWordWrap(True)
        cl.addWidget(self._q_lbl)
        self._prog_lbl = QLabel("Starting exploration…")
        self._prog_lbl.setWordWrap(True)
        cl.addWidget(self._prog_lbl)
        self._prog_bar = QProgressBar()
        self._prog_bar.setRange(0, 0)
        self._prog_bar.setMaximumHeight(3)
        self._prog_bar.setTextVisible(False)
        cl.addWidget(self._prog_bar)
        self._plan_hdr = QLabel("Plan")
        self._plan_lbl = QLabel("")
        self._plan_lbl.setWordWrap(True)
        self._plan_lbl.setTextFormat(Qt.RichText)
        self._findings_hdr = QLabel("Findings so far")
        self._findings_lbl = QLabel("")
        self._findings_lbl.setWordWrap(True)
        self._findings_lbl.setTextFormat(Qt.RichText)
        for w in (self._plan_hdr, self._plan_lbl, self._findings_hdr, self._findings_lbl):
            w.setVisible(False)
            cl.addWidget(w)
        self._toggle_btn = QPushButton("▶  Show 0 steps")
        self._toggle_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._toggle_btn.clicked.connect(self._toggle_expand)
        self._toggle_btn.setVisible(False)
        cl.addWidget(self._toggle_btn, alignment=Qt.AlignLeft)
        self._steps_frame = QFrame()
        self._steps_lo = QVBoxLayout(self._steps_frame)
        self._steps_lo.setContentsMargins(0, 4, 0, 4)
        self._steps_lo.setSpacing(6)
        self._steps_frame.setVisible(False)
        cl.addWidget(self._steps_frame)
        self._summary_sep = QFrame()
        self._summary_sep.setFrameShape(QFrame.HLine)
        self._summary_sep.setVisible(False)
        cl.addWidget(self._summary_sep)
        self._summary_hdr = QLabel("Summary")
        self._summary_hdr.setVisible(False)
        cl.addWidget(self._summary_hdr)
        self._summary_lbl = QLabel("")
        self._summary_lbl.setWordWrap(True)
        self._summary_lbl.setTextFormat(Qt.RichText)
        self._summary_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self._summary_lbl.setVisible(False)
        cl.addWidget(self._summary_lbl)
        root.addWidget(self._card)
        self.apply_theme()

    def set_progress(self, turn, max_turns, text=""):
        """Show the current turn and what the model is doing.

        Args:
            turn (int): Current turn.
            max_turns (int): Turn budget.
            text (str): Status line.
        """
        self._badge.setText(f"Turn {turn} / {max_turns}")
        if text:
            self._prog_lbl.setText(text)

    def set_plan(self, items):
        """Show the model's hypotheses.

        Args:
            items (list): Hypotheses in order.
        """
        if not items:
            return
        self._plan_lbl.setText(md_to_html('\n'.join(f"{i}. {h}" for i, h in enumerate(items, start=1))))
        self._plan_hdr.setVisible(True)
        self._plan_lbl.setVisible(True)

    def set_findings(self, ledger):
        """Show the findings recorded so far.

        Args:
            ledger (FindingsLedger): The findings.
        """
        if not len(ledger):
            return
        lines = []
        for f in ledger.ranked()[:12]:
            mark = '✓' if f.supported else '✗'
            lines.append(f"- {mark} {f.line()}")
        self._findings_lbl.setText(md_to_html('\n'.join(lines)))
        self._findings_hdr.setVisible(True)
        self._findings_lbl.setVisible(True)

    def add_step(self, turn_num, rationale, code, result):
        """Add one turn to the list of steps.

        Args:
            turn_num (int): Turn number.
            rationale (str): The model's one-line reason for the query.
            code (str): The code that ran.
            result (ExecResult): What it produced.
        """
        self._steps += 1
        self._steps_lo.addWidget(self._build_step_widget(turn_num, rationale, code, result))
        self._update_toggle()
        self._toggle_btn.setVisible(True)

    def set_summary(self, summary_md):
        """Show the final summary and stop the progress bar.

        Args:
            summary_md (str): Summary in markdown.
        """
        self._prog_lbl.setText(f"✓ Exploration complete — {self._steps} turn{'s' if self._steps != 1 else ''}")
        self._badge.setText("Done")
        self._prog_bar.setVisible(False)
        self._summary_sep.setVisible(True)
        self._summary_hdr.setVisible(True)
        self._summary_lbl.setVisible(True)
        self._summary_lbl.setText(md_to_html(summary_md or "(no summary provided)"))
        self.apply_theme()

    def mark_cancelled(self, reason="stopped by user"):
        """Show that the exploration ended early.

        Args:
            reason (str): Why it ended.
        """
        self._prog_lbl.setText(f"⏹ Exploration ended — {reason}")
        self._prog_bar.setVisible(False)
        if self._steps:
            self._summary_sep.setVisible(True)
            self._summary_hdr.setText("Ended early")
            self._summary_hdr.setVisible(True)
            self._summary_lbl.setText(md_to_html(
                f"No summary was written. The {self._steps} step{'s' if self._steps != 1 else ''} "
                "and the findings above are still available."))
            self._summary_lbl.setVisible(True)
        self.apply_theme()

    def _update_toggle(self):
        """Refresh the show/hide steps button text."""
        n = self._steps
        self._toggle_btn.setText(
            f"{'▼' if self._expanded else '▶'}  {'Hide' if self._expanded else 'Show'} "
            f"{n} step{'s' if n != 1 else ''}")

    def _toggle_expand(self):
        """Show or hide the steps."""
        self._expanded = not self._expanded
        self._steps_frame.setVisible(self._expanded)
        self._update_toggle()

    def _build_step_widget(self, turn_num, rationale, code, result):
        """Build the compact view of one turn."""
        f = QFrame()
        lo = QVBoxLayout(f)
        lo.setContentsMargins(10, 8, 10, 8)
        lo.setSpacing(4)
        hdr = QLabel(f"<b>Turn {turn_num}</b>")
        hdr.setTextFormat(Qt.RichText)
        lo.addWidget(hdr)
        if rationale and rationale.strip():
            r = QLabel(rationale.strip())
            r.setWordWrap(True)
            r.setStyleSheet(f"color:{Theme.c('text_secondary')};font-size:{fs(-1)}px;"
                            f"font-style:italic;background:transparent;border:none;")
            lo.addWidget(r)
        if code:
            lo.addWidget(CodeBubble(code))
        if result is not None:
            if result.error:
                lo.addWidget(NoticeBubble(result.error, kind='error'))
            if result.text:
                shown = result.text if len(result.text) <= 1500 else result.text[:1500] + "\n... [truncated]"
                lo.addWidget(OutputBubble(shown))
            for tbl in result.tables:
                try:
                    lo.addWidget(InteractiveTableBubble(tbl['headers'], tbl['rows'], tbl.get('title', ''),
                                                        note=tbl.get('note', '')))
                except Exception:
                    _itk_log.exception("Could not show an exploration table")
            for fig in result.figures:
                try:
                    lo.addWidget(FigureBubble(fig['figure'], fig.get('title', ''), code=None))
                except Exception:
                    _itk_log.exception("Could not show an exploration figure")
            for item in result.findings:
                lo.addWidget(NoticeBubble("Finding: " + str(item.get('claim', '')), kind='info'))
        f.setStyleSheet(
            f"QFrame{{background:{Theme.c('bg_secondary')};"
            f"border:1px solid {Theme.c('border_light')};border-radius:8px;}}"
            f"QLabel{{background:transparent;border:none;color:{Theme.c('text')};}}")
        return f

    def apply_theme(self):
        """Restyle for the current theme and font size."""
        size, size2, size3 = fs(), fs(-1), fs(1)
        ac = Theme.c('accent')
        fg = Theme.c('text')
        fg2 = Theme.c('text_secondary')
        bd = Theme.c('border')
        bg = Theme.c('accent_surface')
        self._card.setStyleSheet(
            f"QFrame{{background:{bg};border:1px solid {ac};border-left:4px solid {ac};border-radius:10px;}}")
        plain = "background:transparent;border:none;"
        self._title_lbl.setStyleSheet(f"color:{ac};font-size:{size3}px;font-weight:700;{plain}")
        self._badge.setStyleSheet(f"color:{ac};font-size:{size2}px;font-weight:600;{plain}")
        self._q_lbl.setStyleSheet(f"color:{fg};font-size:{size}px;font-style:italic;{plain}")
        self._prog_lbl.setStyleSheet(f"color:{fg2};font-size:{size2}px;{plain}")
        hdr = (f"color:{ac};font-size:{size2}px;font-weight:700;text-transform:uppercase;"
               f"letter-spacing:0.6px;{plain}")
        for w in (self._plan_hdr, self._findings_hdr, self._summary_hdr):
            w.setStyleSheet(hdr)
        for w in (self._plan_lbl, self._findings_lbl):
            w.setStyleSheet(f"color:{fg};font-size:{size2}px;{plain}")
        self._toggle_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{ac};border:none;"
            f"font-size:{size2}px;font-weight:600;padding:2px 0;text-align:left;}}"
            f"QPushButton:hover{{color:{Theme.c('accent_hover')};}}")
        self._summary_sep.setStyleSheet(f"QFrame{{border:none;border-top:1px solid {bd};background:transparent;}}")
        self._summary_lbl.setStyleSheet(f"color:{fg};font-size:{size}px;line-height:1.6;{plain}")
        self._steps_frame.setStyleSheet("QFrame{background:transparent;border:none;}")


class _NumericItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically when possible."""
    def __lt__(self, other):
        """Compare numerically when both cells hold numbers."""
        def _num(s):
            """Parse a cell as a number, ignoring thousands separators and %."""
            try:
                return float(s.replace(',', '').replace('%', ''))
            except (ValueError, AttributeError):
                return None
        a, b = _num(self.text()), _num(other.text())
        if a is not None and b is not None: return a < b
        return self.text() < other.text()


class InteractiveTableBubble(QFrame):
    """Sortable, filterable table with stats panel, chart type selector, and CSV export."""

    _CHART_TYPES = [('Bar', 'bar'), ('Barh', 'barh'), ('Line', 'line'), ('Pie', 'pie')]
    _COLORS = ['#3B82F6','#10B981','#F59E0B','#EF4444','#8B5CF6',
               '#06B6D4','#F97316','#EC4899','#84CC16','#6B7280']

    def __init__(self, headers, rows, title="Query result", note=''):
        """Create the table.

        Args:
            headers (list): Column names.
            rows (list): Rows of display strings.
            title (str): Caption.
            note (str): Test results or caveats shown under the caption.
        """
        super().__init__()
        self._headers   = headers
        self._all_rows  = rows
        self._title     = title
        self._chart_kind = 'barh'  
        self.setContentsMargins(0, 4, 0, 4)
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        top = QFrame(); tl = QHBoxLayout(top); tl.setContentsMargins(6,4,6,4); tl.setSpacing(6)
        self._title_lbl = QLabel(f"\u25b6 {title}"); tl.addWidget(self._title_lbl)
        self._badge = QLabel(f"{len(rows)} rows")
        self._badge.setFixedHeight(20); tl.addWidget(self._badge)
        tl.addStretch()
        self._stats_btn = QPushButton("\u03a3 Stats"); self._stats_btn.setCheckable(True)
        self._stats_btn.setFixedHeight(26)
        self._stats_btn.toggled.connect(self._toggle_stats)
        tl.addWidget(self._stats_btn)
        self._tab_btn   = QPushButton("Table"); self._tab_btn.setCheckable(True); self._tab_btn.setChecked(True)
        self._chart_btn = QPushButton("Chart"); self._chart_btn.setCheckable(True)
        self._tab_btn.setFixedHeight(26); self._chart_btn.setFixedHeight(26)
        self._tab_btn.clicked.connect(lambda: self._switch(0))
        self._chart_btn.clicked.connect(lambda: self._switch(1))
        tl.addWidget(self._tab_btn); tl.addWidget(self._chart_btn)
        csv_btn = QPushButton("\u2193 CSV"); csv_btn.setFixedHeight(26)
        csv_btn.clicked.connect(self._export_csv); tl.addWidget(csv_btn)
        tsv_btn = QPushButton("\u2398 TSV"); tsv_btn.setFixedHeight(26)
        tsv_btn.clicked.connect(self._copy_tsv); tl.addWidget(tsv_btn)
        root.addWidget(top); self._top = top
        self._note_lbl = QLabel(note or '')
        self._note_lbl.setWordWrap(True)
        self._note_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._note_lbl.setVisible(bool(note))
        root.addWidget(self._note_lbl)

        self._stats_frame = QFrame(); self._stats_frame.setVisible(False)
        sl = QHBoxLayout(self._stats_frame); sl.setContentsMargins(8,4,8,4); sl.setSpacing(8)
        sl.addWidget(QLabel("Column:"))
        self._stats_col = QComboBox()
        self._numeric_cols = []
        for i, h in enumerate(headers):
            vals = [r[i] for r in rows if i < len(r) and r[i]]
            sample = vals[:10]
            if sample and all(to_float(str(v).replace('%', '')) is not None
                              for v in sample):
                self._numeric_cols.append((i, h))
                self._stats_col.addItem(h)
        sl.addWidget(self._stats_col)
        self._stats_lbl = QLabel("")
        self._stats_lbl.setWordWrap(False)
        sl.addWidget(self._stats_lbl, stretch=1)
        self._stats_col.currentIndexChanged.connect(self._refresh_stats)
        root.addWidget(self._stats_frame)

        filt_frame = QFrame()
        fl = QHBoxLayout(filt_frame); fl.setContentsMargins(6,4,6,4); fl.setSpacing(6)
        self._filter = QLineEdit(); self._filter.setPlaceholderText("Filter rows\u2026")
        self._filter.setFixedHeight(28)
        self._filter.textChanged.connect(self._apply_filter)
        fl.addWidget(self._filter, stretch=1)
        self._filter_lbl = QLabel(f"{len(rows)} shown")
        fl.addWidget(self._filter_lbl)
        root.addWidget(filt_frame); self._filt_frame = filt_frame

        self._stack = QStackedWidget(); root.addWidget(self._stack)

        self._table = QTableWidget()
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setSortingEnabled(True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table_h = int(min(len(rows) * (fs() + 12) + 62, 420))
        self._table.setFixedHeight(self._table_h)
        self._table.horizontalHeader().sectionClicked.connect(self._on_col_click)
        self._stack.addWidget(self._table)

        self._chart_page = QFrame()
        cl = QVBoxLayout(self._chart_page); cl.setContentsMargins(8,8,8,8); cl.setSpacing(6)
        chart_ctrl = QHBoxLayout(); chart_ctrl.setSpacing(6)
        chart_ctrl.addWidget(QLabel("Column:"))
        self._col_combo = QComboBox()
        for _, h in self._numeric_cols: self._col_combo.addItem(h)
        chart_ctrl.addWidget(self._col_combo)
        chart_ctrl.addSpacing(12)
        chart_ctrl.addWidget(QLabel("Type:"))
        self._type_btns = []
        for label, kind in self._CHART_TYPES:
            b = QPushButton(label); b.setCheckable(True); b.setFixedHeight(24)
            b.setChecked(kind == self._chart_kind)
            b.clicked.connect(lambda checked, k=kind: self._set_chart_kind(k))
            chart_ctrl.addWidget(b); self._type_btns.append((b, kind))
        chart_ctrl.addStretch()
        self._chart_save_btn = QPushButton("\u2193 PNG"); self._chart_save_btn.setFixedHeight(24)
        self._chart_save_btn.clicked.connect(self._save_chart_png)
        chart_ctrl.addWidget(self._chart_save_btn)
        cl.addLayout(chart_ctrl)
        self._chart_canvas_frame = QFrame()
        self._chart_canvas_frame.setMinimumHeight(280)
        cl.addWidget(self._chart_canvas_frame, stretch=1)
        self._col_combo.currentIndexChanged.connect(self._draw_chart)
        self._stack.addWidget(self._chart_page)

        self._stack.setFixedHeight(self._table_h)
        self._populate(rows)
        self._refresh_stats()
        self.apply_theme()


    def _populate(self, rows):
        """Fill the table with rows.

        Args:
            rows (list): Rows to show.
        """
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(rows))
        font = QFont(self._table.font())
        font.setPixelSize(fs(-2))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = _NumericItem(str(val))
                item.setFont(font)
                self._table.setItem(r, c, item)
        self._table.setSortingEnabled(True)
        self._badge.setText(f"{len(rows)} rows")
        self._filter_lbl.setText(f"{len(rows)} shown")

    def _apply_filter(self, text):
        """Show only rows containing the filter text.

        Args:
            text (str): Filter text.
        """
        text = text.lower()
        filtered = [r for r in self._all_rows
                    if not text or any(text in str(v).lower() for v in r)]
        self._populate(filtered)

    def _on_col_click(self, col_idx):
        """Select the clicked column in the stats combo and show stats."""
        for ci, (idx, _) in enumerate(self._numeric_cols):
            if idx == col_idx:
                self._stats_col.setCurrentIndex(ci)
                if not self._stats_btn.isChecked():
                    self._stats_btn.setChecked(True)
                    self._stats_frame.setVisible(True)
                break


    def _toggle_stats(self, checked):
        """Show or hide the column statistics.

        Args:
            checked (bool): Show them.
        """
        self._stats_frame.setVisible(checked)
        if checked: self._refresh_stats()

    def _refresh_stats(self):
        """Compute statistics of the selected numeric column."""
        if not self._numeric_cols: return
        ci = self._stats_col.currentIndex()
        if ci < 0: return
        col_idx = self._numeric_cols[ci][0]
        vals = []
        for r in self._all_rows:
            if col_idx < len(r):
                try: vals.append(float(str(r[col_idx]).replace(",","").replace("%","")))
                except Exception:
                    _itk_log.exception("Handled exception in _refresh_stats")
        if not vals:
            self._stats_lbl.setText("No numeric data"); return
        a = np.array(vals)
        self._stats_lbl.setText(
            f"N: {len(a):,}  \u2022  "
            f"Mean: {np.mean(a):.4g}  \u2022  "
            f"Median: {np.median(a):.4g}  \u2022  "
            f"Std: {np.std(a):.4g}  \u2022  "
            f"Min: {np.min(a):.4g}  \u2022  "
            f"Max: {np.max(a):.4g}  \u2022  "
            f"P95: {np.percentile(a,95):.4g}")


    def _switch(self, idx):
        """Show the table (0) or the quick chart (1)."""
        self._stack.setCurrentIndex(idx)
        self._stack.setFixedHeight(self._table_h if idx == 0 else 360)
        self._tab_btn.setChecked(idx == 0)
        self._chart_btn.setChecked(idx == 1)
        if idx == 1: self._draw_chart()
        self.apply_theme()

    def _set_chart_kind(self, kind):
        """Change the quick chart type.

        Args:
            kind (str): ``bar``, ``barh``, ``line`` or ``pie``.
        """
        self._chart_kind = kind
        for b, k in self._type_btns:
            b.setChecked(k == kind)
        self._draw_chart()

    def _draw_chart(self):
        """Draw the selected numeric column as a quick chart of the table."""
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure
        if not self._numeric_cols:
            return
        ci = self._col_combo.currentIndex()
        if ci < 0 or ci >= len(self._numeric_cols):
            return
        col_idx, col_name = self._numeric_cols[ci]
        is_dark = Theme.is_dark()
        bg = "#0F172A" if is_dark else "#F8FAFC"
        fg = "#F1F5F9" if is_dark else "#0F172A"
        gc = "#334155" if is_dark else "#E2E8F0"
        dpi = UI_PREFS["chart_dpi"]
        size = fs(-4)
        labels, values = [], []
        for r in self._all_rows[:25]:
            v = to_float(str(r[col_idx]).replace("%", "")) if col_idx < len(r) else None
            if v is not None:
                labels.append(str(r[0]))
                values.append(v)
        if not values:
            return
        kind = self._chart_kind
        cols = (self._COLORS * 4)[:len(labels)]
        if kind == "pie":
            fig = Figure(figsize=(5, 4.5), dpi=dpi)
            ax = fig.subplots()
            _, _, autos = ax.pie(values, labels=labels, autopct="%1.1f%%", colors=cols, startangle=90,
                                 textprops={"color": fg, "fontsize": size})
            for at in autos:
                at.set_color(fg)
                at.set_fontsize(size - 1)
            ax.set_title(col_name, color=fg, fontsize=size + 1)
        elif kind == "barh":
            fig = Figure(figsize=(5.5, max(2.2, len(labels) * 0.34)), dpi=dpi)
            ax = fig.subplots()
            ax.barh(range(len(labels)), values[::-1], color="#3B82F6", alpha=0.88)
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels[::-1], fontsize=size, color=fg)
            ax.set_xlabel(col_name, fontsize=size, color=fg)
            ax.xaxis.grid(True, color=gc, linewidth=0.5)
        elif kind == "line":
            fig = Figure(figsize=(6, 3.5), dpi=dpi)
            ax = fig.subplots()
            ax.plot(range(len(values)), values, color="#3B82F6", lw=2, marker="o", ms=3)
            step = max(1, len(labels) // 15)
            ax.set_xticks(range(0, len(labels), step))
            ax.set_xticklabels(labels[::step], rotation=35, ha="right", fontsize=size, color=fg)
            ax.set_ylabel(col_name, fontsize=size, color=fg)
            ax.yaxis.grid(True, color=gc, linewidth=0.5)
        else:
            fig = Figure(figsize=(max(4, len(labels) * 0.4), 3.5), dpi=dpi)
            ax = fig.subplots()
            ax.bar(range(len(labels)), values, color=cols, alpha=0.88)
            step = max(1, len(labels) // 15)
            ax.set_xticks(range(0, len(labels), step))
            ax.set_xticklabels(labels[::step], rotation=35, ha="right", fontsize=size, color=fg)
            ax.set_ylabel(col_name, fontsize=size, color=fg)
            ax.yaxis.grid(True, color=gc, linewidth=0.5)
        fig.patch.set_facecolor(bg)
        ax.set_facecolor(bg)
        ax.tick_params(colors=fg)
        for sp in ax.spines.values():
            sp.set_edgecolor(gc)
        fig.tight_layout(pad=1.0)
        self._last_fig = fig
        for child in self._chart_canvas_frame.findChildren(FigureCanvasQTAgg):
            child.setParent(None)
            child.deleteLater()
        canvas = FigureCanvasQTAgg(fig)
        lay = self._chart_canvas_frame.layout() or QVBoxLayout(self._chart_canvas_frame)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(canvas)
        canvas.draw()

    def _save_chart_png(self):
        """Save the quick chart as a PNG."""
        fig = getattr(self, "_last_fig", None)
        if not fig: return
        path, _ = QFileDialog.getSaveFileName(self, "Save chart", "", "PNG (*.png)")
        if path:
            fig.savefig(path, dpi=max(UI_PREFS["chart_dpi"], 150),
                        bbox_inches="tight", facecolor=fig.get_facecolor())


    def _copy_tsv(self):
        """Copy the visible rows as tab-separated text."""
        rows = ['\t'.join(self._headers)]
        for r in range(self._table.rowCount()):
            rows.append('\t'.join(
                self._table.item(r, c).text()
                for c in range(self._table.columnCount())))
        QApplication.clipboard().setText('\n'.join(rows))

    def _export_csv(self):
        """Save the visible rows as a CSV file."""
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "", "CSV (*.csv)")
        if not path: return
        import csv as _csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = _csv.writer(f); w.writerow(self._headers)
            for r in range(self._table.rowCount()):
                w.writerow(self._table.item(r, c).text()
                           for c in range(self._table.columnCount()))


    def apply_theme(self):
        """Restyle for the current theme."""
        fs2 = fs(-2); fs3 = fs(-3)
        bg = Theme.c("bg_secondary"); fg = Theme.c("text")
        fg2 = Theme.c("text_secondary"); bd = Theme.c("border")
        ac = Theme.c("accent"); sf = Theme.c("surface")

        self._top.setStyleSheet(f"QFrame{{background:{bg};border-radius:8px 8px 0 0;}}")
        self._title_lbl.setStyleSheet(
            f"color:{fg2};font-size:{fs2}px;font-weight:600;")
        self._note_lbl.setStyleSheet(
            f"color:{fg2};font-size:{fs3}px;font-style:italic;padding:2px 8px;background:transparent;")
        self._badge.setStyleSheet(
            f"background:{Theme.c('accent_surface')};color:{ac};"
            f"border-radius:10px;padding:0 8px;font-size:{fs3}px;")
        tog = (f"QPushButton{{background:transparent;border:0.5px solid {bd};"
               f"border-radius:5px;padding:2px 10px;font-size:{fs3}px;color:{fg2};}}"
               f"QPushButton:checked{{background:{ac};color:white;border-color:{ac};}}"
               f"QPushButton:hover{{border-color:{ac};}}")
        self._tab_btn.setStyleSheet(tog); self._chart_btn.setStyleSheet(tog)
        self._stats_btn.setStyleSheet(tog)
        smll = (f"QPushButton{{background:transparent;border:0.5px solid {bd};"
                f"border-radius:5px;padding:2px 8px;font-size:{fs3}px;color:{fg2};}}"
                f"QPushButton:hover{{background:{Theme.c('accent_surface')};color:{ac};}}")
        for child in self._top.findChildren(QPushButton):
            if child not in (self._tab_btn, self._chart_btn, self._stats_btn):
                child.setStyleSheet(smll)
        self._stats_frame.setStyleSheet(
            f"QFrame{{background:{Theme.c('bg_tertiary')};border-bottom:1px solid {bd};}}"
            f"QLabel{{color:{fg2};font-size:{fs3}px;}}"
            f"QComboBox{{background:{sf};color:{fg};border:1px solid {bd};"
            f"border-radius:4px;padding:2px 6px;font-size:{fs3}px;}}")
        self._stats_lbl.setStyleSheet(
            f"color:{fg};font-size:{fs3}px;font-family:monospace;")
        self._filt_frame.setStyleSheet(f"QFrame{{background:{bg};}}")
        self._filter.setStyleSheet(
            f"QLineEdit{{border:0.5px solid {bd};border-radius:6px;"
            f"padding:4px 10px;font-size:{fs2}px;background:{sf};color:{fg};}}")
        self._filter_lbl.setStyleSheet(
            f"color:{fg2};font-size:{fs3}px;")
        self._table.setStyleSheet(
            f"QTableWidget{{background:{sf};color:{fg};border:0.5px solid {bd};"
            f"gridline-color:{bd};font-size:{fs2}px;alternate-background-color:{bg};}}"
            f"QHeaderView::section{{background:{bg};color:{fg2};border:none;"
            f"border-bottom:0.5px solid {bd};padding:4px 8px;"
            f"font-size:{fs2}px;font-weight:600;}}"
            f"QTableWidget::item{{padding:4px 8px;}}"
            f"QTableWidget::item:selected{{background:{Theme.c('accent_surface')};color:{ac};}}"
            f"QTableWidget::item:hover{{background:{Theme.c('surface_hover')};}}")
        self._table.verticalHeader().setDefaultSectionSize(fs() + 12)
        for b, _ in self._type_btns: b.setStyleSheet(tog)
        smll2 = smll
        self._chart_save_btn.setStyleSheet(smll2)
        for child in self._chart_page.findChildren(QLabel):
            child.setStyleSheet(f"color:{fg2};font-size:{fs3}px;")
        if hasattr(self, "_col_combo"):
            self._col_combo.setStyleSheet(
                f"QComboBox{{background:{sf};color:{fg};border:0.5px solid {bd};"
                f"border-radius:4px;padding:2px 6px;font-size:{fs3}px;}}")


class OutputBubble(QFrame):
    """Fallback plain-text output for non-tabular results."""
    def __init__(self, text):
        """Create the view.

        Args:
            text (str): Printed output.
        """
        super().__init__()
        self.setContentsMargins(0,4,0,4)
        lo = QVBoxLayout(self); lo.setContentsMargins(0,0,0,0); lo.setSpacing(2)
        hdr = QLabel("▶ Query result")
        hdr.setStyleSheet(
            f"color:{Theme.c('text_secondary')};font-size:{fs(-2)}px;padding:0 4px;")
        lo.addWidget(hdr)
        self._te = QTextEdit(); self._te.setReadOnly(True)
        self._te.setPlainText(text)
        lines = text.count('\n') + 1
        self._te.setFixedHeight(min(max(60, lines * (fs() + 4) + 20), 400))
        lo.addWidget(self._te)
        self.apply_theme()

    def apply_theme(self):
        """Restyle for the current theme."""
        size = fs(-1)
        self._te.setStyleSheet(
            f"QTextEdit{{background:{Theme.c('output_bg')};color:{Theme.c('output_text')};"
            f"border:0.5px solid {Theme.c('output_border')};border-radius:8px;"
            f"font-family:monospace;font-size:{size}px;padding:8px;}}")


class NoticeBubble(QFrame):
    """A short coloured notice: an error, a warning or a note."""

    _KINDS = {'error': ('error_bg', 'error_border', 'error_text', '⚠'),
              'warn': ('warn_bg', 'warn_border', 'warn_text', '⚠'),
              'info': ('accent_surface', 'border', 'text', 'ℹ')}

    def __init__(self, text, kind='warn'):
        """Create the notice.

        Args:
            text (str): Message.
            kind (str): ``error``, ``warn`` or ``info``.
        """
        super().__init__()
        self._kind = kind if kind in self._KINDS else 'warn'
        self.setContentsMargins(0, 3, 0, 3)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        self._card = QFrame()
        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(12, 7, 12, 7)
        self._lbl = QLabel(f"{self._KINDS[self._kind][3]} {text}")
        self._lbl.setWordWrap(True)
        self._lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        cl.addWidget(self._lbl)
        lo.addWidget(self._card)
        self.apply_theme()

    def apply_theme(self):
        """Restyle for the current theme."""
        bg, bd, fg, _ = self._KINDS[self._kind]
        self._card.setStyleSheet(
            f"QFrame{{background:{Theme.c(bg)};border:1px solid {Theme.c(bd)};border-radius:10px;}}")
        self._lbl.setStyleSheet(
            f"color:{Theme.c(fg)};font-size:{fs(-2)}px;background:transparent;border:none;")


class CodeBubble(QFrame):
    """The code that produced a result, folded away until asked for."""

    def __init__(self, code, expanded=False):
        """Create the view.

        Args:
            code (str): Python source.
            expanded (bool): Start unfolded.
        """
        super().__init__()
        self._code = code
        self.setContentsMargins(0, 2, 0, 2)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(2)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        self._toggle = QPushButton()
        self._toggle.setCursor(QCursor(Qt.PointingHandCursor))
        self._toggle.clicked.connect(self._flip)
        row.addWidget(self._toggle)
        row.addStretch()
        self._copy = QPushButton("⎘ Copy code")
        self._copy.setCursor(QCursor(Qt.PointingHandCursor))
        self._copy.clicked.connect(self._copy_code)
        row.addWidget(self._copy)
        lo.addLayout(row)
        self._view = QPlainTextEdit()
        self._view.setReadOnly(True)
        self._view.setPlainText(code)
        lines = code.count('\n') + 1
        self._view.setFixedHeight(min(max(60, lines * (fs(-2) + 6) + 20), 360))
        self._view.setLineWrapMode(QPlainTextEdit.NoWrap)
        lo.addWidget(self._view)
        self._expanded = expanded
        self._view.setVisible(expanded)
        self._update()
        self.apply_theme()

    def _update(self):
        """Refresh the fold button."""
        self._toggle.setText(("▼ Hide code" if self._expanded else "▶ Show code"))

    def _flip(self):
        """Fold or unfold the code."""
        self._expanded = not self._expanded
        self._view.setVisible(self._expanded)
        self._update()

    def _copy_code(self):
        """Copy the code to the clipboard."""
        QApplication.clipboard().setText(self._code)
        self._copy.setText("✓ Copied")
        QTimer.singleShot(1500, lambda: self._copy.setText("⎘ Copy code"))

    def apply_theme(self):
        """Restyle for the current theme."""
        link = (f"QPushButton{{background:transparent;border:none;color:{Theme.c('text_tertiary')};"
                f"font-size:{fs(-3)}px;padding:0 2px;text-align:left;}}"
                f"QPushButton:hover{{color:{Theme.c('accent')};}}")
        self._toggle.setStyleSheet(link)
        self._copy.setStyleSheet(link)
        self._view.setStyleSheet(
            f"QPlainTextEdit{{background:{Theme.c('code_bg')};color:{Theme.c('code_text')};"
            f"border:none;border-radius:6px;font-family:Menlo,Consolas,monospace;"
            f"font-size:{fs(-2)}px;padding:6px;}}")


class FigureWindow(QWidget):
    """A figure in its own resizable window, with zoom and pan."""

    def __init__(self, figure, title, parent=None):
        """Open the window.

        Args:
            figure (Figure): The figure to show.
            title (str): Window title.
            parent (QWidget): Owner.
        """
        super().__init__(parent, Qt.Window)
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
        self._fig = figure
        self._size = tuple(figure.get_size_inches())
        self.setWindowTitle(title or "Figure")
        lo = QVBoxLayout(self)
        self._canvas = FigureCanvasQTAgg(figure)
        lo.addWidget(NavigationToolbar2QT(self._canvas, self))
        lo.addWidget(self._canvas, stretch=1)
        self.resize(int(self._size[0] * 110), int(self._size[1] * 110) + 50)

    def closeEvent(self, event):
        """Give the figure back its original size so exports stay as drawn."""
        try:
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            self._fig.set_size_inches(*self._size)
            FigureCanvasAgg(self._fig)
        except Exception:
            _itk_log.exception("Could not restore the figure size")
        super().closeEvent(event)


class FigureBubble(QFrame):
    """A figure the model drew, with copy, save and pop-out.

    The preview is a crisp image of the figure at the size the model chose,
    scaled down only when the window is narrower. Saving always uses the
    original size at publication resolution.
    """

    PREVIEW_DPI = 200

    def __init__(self, figure, title='', code=None):
        """Create the card.

        Args:
            figure (Figure): The figure.
            title (str): Caption.
            code (str): The code that drew it, shown folded.
        """
        super().__init__()
        self._fig = figure
        self._title = title or 'Figure'
        self._window = None
        self._pix = None
        self.setContentsMargins(0, 4, 0, 4)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(2)
        hdr = QHBoxLayout()
        hdr.setContentsMargins(6, 2, 6, 2)
        self._title_lbl = QLabel(f"▶ {self._title}")
        hdr.addWidget(self._title_lbl)
        hdr.addStretch()
        self._btns = []
        for text, slot, tip in (("⤢ Open", self._pop_out, "Open in a window with zoom and pan"),
                                ("⎘ Copy", self._copy_image, "Copy the image to the clipboard"),
                                ("↓ Save…", self._save, "Save as PNG, SVG, PDF or TIFF")):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setCursor(QCursor(Qt.PointingHandCursor))
            b.clicked.connect(slot)
            hdr.addWidget(b)
            self._btns.append(b)
        lo.addLayout(hdr)
        self._img = QLabel()
        self._img.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        lo.addWidget(self._img)
        if code:
            self._code = CodeBubble(code)
            lo.addWidget(self._code)
        else:
            self._code = None
        self._render()
        self.apply_theme()

    def _render(self):
        """Draw the preview image."""
        from results.ai.figures import render_png
        try:
            png = render_png(self._fig, dpi=self.PREVIEW_DPI)
        except Exception as e:
            _itk_log.exception("Figure preview failed")
            self._img.setText(f"⚠ Could not draw the figure: {e}")
            return
        pix = QPixmap()
        pix.loadFromData(png)
        pix.setDevicePixelRatio(self.PREVIEW_DPI / 100.0)
        self._pix = pix
        self._fit()

    def _fit(self):
        """Scale the preview to the available width."""
        if self._pix is None:
            return
        ratio = self._pix.devicePixelRatio()
        logical_w = self._pix.width() / ratio
        avail = max(200, self.width() - 12) if self.width() > 50 else logical_w
        if logical_w > avail:
            scaled = self._pix.scaledToWidth(int(avail * ratio), Qt.SmoothTransformation)
            scaled.setDevicePixelRatio(ratio)
            self._img.setPixmap(scaled)
        else:
            self._img.setPixmap(self._pix)

    def resizeEvent(self, event):
        """Keep the preview within the chat width."""
        super().resizeEvent(event)
        self._fit()

    def _copy_image(self):
        """Copy the figure image to the clipboard."""
        if self._pix is not None:
            QApplication.clipboard().setPixmap(self._pix)
            self._btns[1].setText("✓ Copied")
            QTimer.singleShot(1500, lambda: self._btns[1].setText("⎘ Copy"))

    def _save(self):
        """Save the figure at its original size and publication resolution."""
        import matplotlib
        from results.ai.figures import STYLE
        safe = re.sub(r'[^\w\- ]+', '', self._title).strip().replace(' ', '_') or 'figure'
        path, chosen = QFileDialog.getSaveFileName(
            self, "Save figure", f"{safe}.png",
            "PNG, 300 dpi (*.png);;SVG (*.svg);;PDF (*.pdf);;TIFF, 300 dpi (*.tiff)")
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        if not ext:
            ext = {'SVG': '.svg', 'PDF': '.pdf', 'TIFF': '.tiff'}.get(chosen.split(' ')[0].rstrip(','), '.png')
            path += ext
        try:
            with matplotlib.rc_context(STYLE):
                self._fig.savefig(path, dpi=300, bbox_inches='tight', facecolor='white')
        except Exception as e:
            _itk_log.exception("Saving the figure failed")
            self._title_lbl.setText(f"⚠ Could not save: {e}")

    def _pop_out(self):
        """Open the figure in its own window."""
        if self._window is None or not self._window.isVisible():
            self._window = FigureWindow(self._fig, self._title, self.window())
        self._window.show()
        self._window.raise_()

    def apply_theme(self):
        """Restyle for the current theme."""
        self._title_lbl.setStyleSheet(f"color:{Theme.c('text_secondary')};font-size:{fs(-2)}px;font-weight:600;")
        for b in self._btns:
            b.setStyleSheet(
                f"QPushButton{{background:transparent;border:0.5px solid {Theme.c('border')};"
                f"border-radius:5px;padding:2px 8px;font-size:{fs(-3)}px;color:{Theme.c('text_secondary')};}}"
                f"QPushButton:hover{{background:{Theme.c('accent_surface')};color:{Theme.c('accent')};}}")
        self._img.setStyleSheet("background:white;border-radius:6px;padding:4px;")
        if self._code is not None:
            self._code.apply_theme()


class AutoGrowTextEdit(QPlainTextEdit):
    """Text input that grows and shrinks with content. Enter sends; Shift+Enter newline.
    Can also be manually resized via set_forced_height() — when set, auto-grow is
    bypassed and the input stays at the user-chosen height.
    """
    submit       = Signal()
    char_changed = Signal(int)

    _MIN_H = 40
    _MAX_H = 600          
    _AUTO_MAX_H = 240   

    def __init__(self, parent=None):
        """Create the input.

        Args:
            parent (QWidget): Owner.
        """
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(self._MIN_H)
        self.setFrameShape(QFrame.NoFrame)
        self._forced_h = None  
        self.textChanged.connect(self._on_changed)

    def set_forced_height(self, h):
        """Lock the input to a specific height (in px). Pass None to re-enable
        auto-grow."""
        if h is None:
            self._forced_h = None
        else:
            self._forced_h = max(self._MIN_H, min(int(h), self._MAX_H))
        self._adjust()

    def get_forced_height(self):
        """Return the height the user dragged to, or ``None``."""
        return self._forced_h

    def _on_changed(self):
        """Report the length and resize after an edit."""
        self.char_changed.emit(len(self.toPlainText()))
        self._adjust()

    def _adjust(self):
        """Fit the height to the text, or keep the forced height."""
        if self._forced_h is not None:
            if self.height() != self._forced_h:
                self.setFixedHeight(self._forced_h)
            doc = self.document()
            vw = self.viewport().width()
            if vw > 10: doc.setTextWidth(vw)
            h = doc.size().height() + 2 * self.frameWidth() + 12
            self.setVerticalScrollBarPolicy(
                Qt.ScrollBarAsNeeded if h > self._forced_h else Qt.ScrollBarAlwaysOff)
            return
        doc = self.document()
        vw = self.viewport().width()
        if vw > 10:
            doc.setTextWidth(vw)
        h = doc.size().height() + 2 * self.frameWidth() + 12
        target = int(min(max(self._MIN_H, h), self._AUTO_MAX_H))
        if self.height() != target:
            self.setFixedHeight(target)
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded if h > self._AUTO_MAX_H else Qt.ScrollBarAlwaysOff)

    def resizeEvent(self, event):
        """Refit the height when the width changes."""
        super().resizeEvent(event)
        self._adjust()   

    def keyPressEvent(self, event):
        """Send on Enter; Shift+Enter inserts a new line."""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submit.emit()
        else:
            super().keyPressEvent(event)

    def text(self):
        """Return the text without surrounding whitespace."""
        return self.toPlainText().strip()

    def setText(self, t):
        """Replace the text.

        Args:
            t (str): New text.
        """
        self.setPlainText(t)

    def clear(self):
        """Remove all text."""
        super().clear()


class ComposerResizeHandle(QFrame):
    """Thin horizontal bar at the top of the composer — drag it up to make the
    input taller, drag down to shrink. Emits delta_y on each drag step."""

    delta_y = Signal(int)   
    reset   = Signal()     

    def __init__(self, parent=None):
        """Create the handle.

        Args:
            parent (QWidget): Owner.
        """
        super().__init__(parent)
        self.setFixedHeight(8)
        self.setCursor(QCursor(Qt.SizeVerCursor))
        self.setMouseTracking(True)
        self._press_y = None
        self.apply_theme()

    def mousePressEvent(self, event):
        """Start a drag."""
        if event.button() == Qt.LeftButton:
            self._press_y = event.globalPosition().y()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Report how far the drag moved."""
        if self._press_y is not None:
            cur = event.globalPosition().y()
            dy = cur - self._press_y
            if abs(dy) >= 1:
                self.delta_y.emit(int(dy))
                self._press_y = cur
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """End the drag."""
        self._press_y = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Ask for the automatic height back."""
        self.reset.emit()
        super().mouseDoubleClickEvent(event)

    def apply_theme(self):
        """Restyle for the current theme."""
        c1 = Theme.c('border')
        self.setStyleSheet(
            f"ComposerResizeHandle{{background:transparent;}}"
            f"ComposerResizeHandle:hover{{background:{c1};}}")

    def paintEvent(self, event):
        """Draw the grip bar."""
        super().paintEvent(event)
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        col = QColor(Theme.c('text_tertiary'))
        p.setPen(Qt.NoPen); p.setBrush(col)
        w = 36; h = 3
        x = (self.width() - w) // 2
        y = (self.height() - h) // 2
        p.drawRoundedRect(x, y, w, h, 1.5, 1.5)
        p.end()


class Conversation:
    """One chat session: its history, widgets, and dedicated chat scroll area.
    Each Conversation owns a QScrollArea + content widget so we can keep all
    bubbles alive when switching tabs (no rebuild needed)."""

    def __init__(self, title="New chat"):
        """Start an empty conversation.

        Args:
            title (str): Sidebar title.
        """
        self.id          = uuid.uuid4().hex[:12]
        self.title       = title
        self.history     = []      
        self.widgets     = []      
        self.draft_text  = ""      
        self.draft_files = []
        self.transcript = []
        self._auto_title = True

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cw = QWidget()
        self.cw.setObjectName('chatContent')
        self.cl = QVBoxLayout(self.cw)
        self.cl.setContentsMargins(20, 16, 20, 16)
        self.cl.setSpacing(6)
        self.cl.addStretch()
        self.scroll.setWidget(self.cw)


class ConversationListItem(QFrame):
    """Sidebar entry: clickable title row with a hover-revealed delete button."""

    selected = Signal(str)  
    deleted  = Signal(str)  

    def __init__(self, conv_id, title, is_current=False):
        """Create the entry.

        Args:
            conv_id (str): Conversation id.
            title (str): Title shown.
            is_current (bool): Whether it is on screen.
        """
        super().__init__()
        self.conv_id  = conv_id
        self._is_cur  = is_current
        self.setFixedHeight(34)
        self.setCursor(QCursor(Qt.PointingHandCursor))

        lo = QHBoxLayout(self); lo.setContentsMargins(10, 4, 6, 4); lo.setSpacing(6)
        self._title_lbl = QLabel(title)
        self._title_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._title_lbl.setToolTip(title)
        lo.addWidget(self._title_lbl, stretch=1)

        self._x = QPushButton("✕"); self._x.setFixedSize(18, 18)
        self._x.setCursor(QCursor(Qt.PointingHandCursor))
        self._x.setToolTip("Delete this conversation")
        self._x.setVisible(False)  
        self._x.clicked.connect(self._on_delete)
        lo.addWidget(self._x)

        self.apply_theme()

    def set_title(self, t):
        """Change the title shown.

        Args:
            t (str): New title.
        """
        self._title_lbl.setText(t)
        self._title_lbl.setToolTip(t)

    def set_current(self, is_current):
        """Mark the entry as the conversation on screen, or not.

        Args:
            is_current (bool): On screen.
        """
        self._is_cur = is_current
        self.apply_theme()

    def enterEvent(self, event):
        """Reveal the delete button on hover."""
        self._x.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Hide the delete button."""
        self._x.setVisible(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Select the conversation unless the delete button was hit."""
        if event.button() == Qt.LeftButton and not self._x.geometry().contains(event.pos()):
            self.selected.emit(self.conv_id)
        super().mousePressEvent(event)

    def _on_delete(self):
        """Ask for the conversation to be deleted."""
        self.deleted.emit(self.conv_id)

    def apply_theme(self):
        """Restyle for the current theme."""
        size = fs(-1)
        fg  = Theme.c('text');           fg2 = Theme.c('text_secondary')
        bd  = Theme.c('border_light');   ac  = Theme.c('accent')
        if self._is_cur:
            bg     = Theme.c('accent_surface')
            text_c = Theme.c('accent')
            self.setStyleSheet(
                f"ConversationListItem{{background:{bg};border:2px solid {ac};"
                f"border-radius:8px;}}")
            self._title_lbl.setStyleSheet(
                f"color:{text_c};font-size:{size}px;font-weight:700;"
                f"background:transparent;border:none;")
        else:
            self.setStyleSheet(
                f"ConversationListItem{{background:transparent;border:1px solid transparent;"
                f"border-radius:8px;}}"
                f"ConversationListItem:hover{{background:{Theme.c('surface_hover')};"
                f"border-color:{bd};}}")
            self._title_lbl.setStyleSheet(
                f"color:{fg};font-size:{size}px;font-weight:500;"
                f"background:transparent;border:none;")
        self._x.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;color:{fg2};"
            f"font-size:11px;border-radius:9px;}}"
            f"QPushButton:hover{{background:{Theme.c('error_bg')};"
            f"color:{Theme.c('error_text')};}}")

