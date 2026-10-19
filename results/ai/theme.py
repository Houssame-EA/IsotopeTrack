"""Colours, font sizes and markdown rendering shared by the AI chat widgets."""
import logging
import re

from PySide6.QtWidgets import QListView


_itk_log = logging.getLogger("IsotopeTrack.results.ai.theme")


class Theme:
    """Chat window colours, taken from the application theme.

    Every colour comes from the palette in :mod:`tools.theme`, the same one
    the Figure Builder and the main window use, so the assistant looks like
    the rest of IsotopeTrack and follows the light and dark switch. The keys
    below are the chat window's names for palette entries.
    """

    _dark = False
    _MAP = {
        'bg': 'bg_primary', 'bg_secondary': 'bg_secondary', 'bg_tertiary': 'bg_tertiary',
        'surface': 'bg_secondary', 'surface_hover': 'bg_hover',
        'border': 'border', 'border_light': 'border_subtle',
        'text': 'text_primary', 'text_secondary': 'text_secondary', 'text_tertiary': 'text_muted',
        'accent': 'accent', 'accent_hover': 'accent_hover', 'accent_surface': 'accent_soft',
        'user_bubble': 'accent', 'user_text': 'text_inverse',
        'ai_bubble': 'bg_secondary', 'ai_text': 'text_primary',
        'error_bg': 'danger_bg', 'error_border': 'danger_border', 'error_text': 'text_primary',
        'warn_bg': 'warning_bg', 'warn_border': 'warning_border', 'warn_text': 'text_primary',
        'input_bg': 'bg_secondary', 'input_border': 'border', 'input_focus': 'accent',
        'scrollbar_bg': 'bg_primary', 'scrollbar_handle': 'border',
        'success_dot': 'success', 'warn_dot': 'warning', 'error_dot': 'danger',
        'progress_bg': 'border_subtle', 'progress_chunk': 'accent',
        'sug_bg': 'bg_secondary', 'sug_text': 'text_primary', 'sug_border': 'border',
        'sug_hover_bg': 'accent_soft', 'sug_hover_border': 'accent', 'sug_hover_text': 'text_primary',
        'stop_bg': 'danger', 'stop_hover': 'danger_border', 'speed_text': 'text_muted',
        'think_bg': 'bg_tertiary', 'think_border': 'border_subtle', 'think_text': 'text_secondary',
    }
    _CODE = {'light': {'code_bg': '#1f2937', 'code_text': '#e5e7eb', 'output_bg': '#1f2937',
                       'output_border': '#374151', 'output_text': '#d1d5db'},
             'dark': {'code_bg': '#181818', 'code_text': '#d4d4d4', 'output_bg': '#181818',
                      'output_border': '#3c3c3c', 'output_text': '#c8c8c8'}}

    @classmethod
    def palette(cls):
        """The application's current palette."""
        from results.figure_builder.ui import look
        return look.palette()

    @classmethod
    def is_dark(cls):
        """Return whether the application is in dark mode."""
        from results.figure_builder.ui import look
        return look.is_dark()

    @classmethod
    def toggle(cls):
        """Kept for compatibility; the application theme decides."""
        cls._dark = not cls._dark

    @classmethod
    def sync_with_global(cls):
        """Follow the application-wide theme."""
        cls._dark = cls.is_dark()

    @classmethod
    def c(cls, key):
        """Return the colour for *key* in the current application theme.

        Args:
            key (str): Chat window colour name.

        Returns:
            str: Hex colour.
        """
        code = cls._CODE['dark' if cls.is_dark() else 'light']
        if key in code:
            return code[key]
        p = cls.palette()
        return getattr(p, cls._MAP.get(key, key), None) or getattr(p, 'text_primary', '#000000')


Theme.sync_with_global()

UI_PREFS = {
    'font_size': 14,
    'chart_dpi': 100,
    'show_timestamps': False,
    'bubble_max_width': 740,
}


def fs(delta=0):
    """Return the chat font size plus *delta*, clamped to a readable range.

    Args:
        delta (int): Offset from the base size.

    Returns:
        int: Font size in pixels.
    """
    return max(11, min(20, UI_PREFS['font_size'] + delta))


_ARROW_PATH = None


def _arrow_image():
    """Path of a small grey chevron used as the drop-down arrow, drawn once.

    The shared stylesheet restyles combo boxes, and on macOS that removes the
    native arrow, so a list looks like a plain text field. Drawing the arrow
    here keeps it visible on every platform and in both themes.

    Returns:
        str: File path with forward slashes, or an empty string on failure.
    """
    global _ARROW_PATH
    if _ARROW_PATH is not None:
        return _ARROW_PATH
    _ARROW_PATH = ''
    try:
        import os
        import tempfile
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QColor, QImage, QPainter, QPen
        img = QImage(40, 40, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor('#8a8a8a'), 5)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline([QPointF(8, 14), QPointF(20, 27), QPointF(32, 14)])
        painter.end()
        path = os.path.join(tempfile.gettempdir(), 'isotopetrack_ai_combo_arrow.png')
        if img.save(path, 'PNG'):
            _ARROW_PATH = path.replace('\\', '/')
    except Exception:
        _itk_log.exception("Could not draw the combo arrow")
    return _ARROW_PATH


def style_combo_popup(combo):
    """Make a combo box drop-down readable inside themed dialogs.

    On macOS the popup is a separate top-level window, so the dialog-scoped
    theme rules do not always reach it and the list renders as an empty panel
    with invisible rows. Giving the combo an explicit list view and styling that
    view directly guarantees visible, clickable items.

    It also draws the drop-down arrow, which the shared stylesheet hides on
    macOS, so the box reads as a list to pick from.

    Args:
        combo (QComboBox): Combo box to fix.

    Returns:
        QComboBox: The same combo, for chaining.
    """
    try:
        arrow = _arrow_image()
        if arrow:
            combo.setStyleSheet(
                "QComboBox{padding-right:24px;}"
                "QComboBox::drop-down{subcontrol-origin:padding;subcontrol-position:center right;"
                "width:22px;border:none;}"
                f"QComboBox::down-arrow{{image:url({arrow});width:11px;height:11px;}}")
        view = QListView()
        combo.setView(view)
        combo.setMaxVisibleItems(12)
        view.setStyleSheet(
            f"QListView{{background:{Theme.c('surface')};"
            f"color:{Theme.c('text')};"
            f"border:1px solid {Theme.c('border')};outline:0;}}"
            f"QListView::item{{min-height:24px;padding:4px 8px;"
            f"color:{Theme.c('text')};background:{Theme.c('surface')};}}"
            f"QListView::item:selected,QListView::item:hover{{"
            f"background:{Theme.c('accent_surface')};color:{Theme.c('text')};}}")
    except Exception:
        _itk_log.exception("Handled exception in style_combo_popup")
    return combo


def style_model_list(widget):
    """Style an always-visible model list so rows stay readable and clickable.

    A plain list avoids the macOS combo-box popup, which renders as an empty
    panel inside themed dialogs and makes the entries impossible to pick.

    Args:
        widget (QListWidget): List to style.

    Returns:
        QListWidget: The same widget, for chaining.
    """
    try:
        widget.setMinimumHeight(110)
        widget.setMaximumHeight(190)
        widget.setAlternatingRowColors(False)
        widget.setStyleSheet(
            f"QListWidget{{background:{Theme.c('surface')};"
            f"color:{Theme.c('text')};"
            f"border:1px solid {Theme.c('border')};border-radius:6px;outline:0;}}"
            f"QListWidget::item{{min-height:26px;padding:4px 8px;"
            f"color:{Theme.c('text')};}}"
            f"QListWidget::item:hover{{background:{Theme.c('surface_hover')};}}"
            f"QListWidget::item:selected{{background:{Theme.c('accent')};"
            f"color:#FFFFFF;}}")
    except Exception:
        _itk_log.exception("Handled exception in style_model_list")
    return widget


CODE_RE = re.compile(r'```(?:python|py)?[ \t]*\n(.*?)```', re.DOTALL)
THINK_RE = re.compile(r'<think>.*?</think>', re.DOTALL)
OPEN_THINK_RE = re.compile(r'<think>.*\Z', re.DOTALL)


def cut_after_code(text):
    """Drop what a reply says after its last code block.

    The code has not run yet when the model writes that part, so any result
    it describes there is a guess. A reply without code is returned as it is.

    Args:
        text (str): Reply text, reasoning already removed.

    Returns:
        str: The reply up to the end of its last code block.
    """
    ends = [m.end() for m in CODE_RE.finditer(text or '')]
    return text[:ends[-1]] if ends else text


def strip_thinking(text):
    """Remove reasoning blocks, including one still being streamed.

    Args:
        text (str): Raw model output.

    Returns:
        str: Text without ``<think>`` sections. When the opening tag was
        part of the prompt, the reply holds only the closing one; everything
        up to it is reasoning and is dropped too.
    """
    text = THINK_RE.sub('', text or '')
    text = OPEN_THINK_RE.sub('', text)
    if '</think>' in text:
        text = text.rsplit('</think>', 1)[1].lstrip()
    return text


def _escape(text):
    """Escape HTML special characters."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def inline_markdown(t, ibg='#F3F4F6'):
    """Render bold, italic and inline code inside one line of markdown.

    Args:
        t (str): Line of text.
        ibg (str): Background colour for inline code.

    Returns:
        str: HTML fragment.
    """
    t = _escape(t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'<i>\1</i>', t)
    t = re.sub(r'`(.+?)`',
               rf'<code style="background:{ibg};padding:1px 5px;border-radius:3px;'
               rf'font-family:monospace;font-size:12px;">\1</code>', t)
    return t


def md_to_html(text):
    """Render the subset of markdown the assistant writes into Qt rich text.

    Handles headings, bullet and numbered lists, fenced code and inline
    styling. Anything else is shown as plain paragraphs.

    Args:
        text (str): Markdown text.

    Returns:
        str: HTML for a rich-text QLabel.
    """
    lines = (text or '').split('\n')
    html = []
    in_code = False
    in_list = False
    buf = []
    cbg = Theme.c('code_bg')
    cfg = Theme.c('code_text')
    ac = Theme.c('accent')
    ibg = Theme.c('bg_tertiary')
    for line in lines:
        s = line.strip()
        if s.startswith('```') and not in_code:
            if in_list:
                html.append('</ul>')
                in_list = False
            in_code = True
            buf = []
            continue
        if s.startswith('```') and in_code:
            in_code = False
            html.append(f'<div style="background:{cbg};color:{cfg};padding:10px 14px;border-radius:8px;'
                        f'font-family:monospace;font-size:12px;margin:6px 0;white-space:pre;">'
                        f'{"<br>".join(buf)}</div>')
            continue
        if in_code:
            buf.append(_escape(line))
            continue
        if s.startswith('### '):
            html.append(f'<div style="font-size:14px;font-weight:700;margin:10px 0 4px;color:{ac};">'
                        f'{inline_markdown(s[4:], ibg)}</div>')
            continue
        if s.startswith('## '):
            html.append(f'<div style="font-size:15px;font-weight:700;margin:12px 0 4px;">'
                        f'{inline_markdown(s[3:], ibg)}</div>')
            continue
        if s.startswith('# '):
            html.append(f'<div style="font-size:16px;font-weight:700;margin:14px 0 6px;">'
                        f'{inline_markdown(s[2:], ibg)}</div>')
            continue
        bullet = re.match(r'^(?:[-*]|\d+[.)])\s+(.*)$', s)
        if bullet:
            if not in_list:
                html.append('<ul style="margin:4px 0 4px 18px;padding:0;">')
                in_list = True
            html.append(f'<li style="margin:2px 0;">{inline_markdown(bullet.group(1), ibg)}</li>')
            continue
        if in_list:
            html.append('</ul>')
            in_list = False
        if not s:
            html.append('<div style="height:6px;"></div>')
            continue
        html.append(f'<div style="margin:2px 0;">{inline_markdown(s, ibg)}</div>')
    if in_list:
        html.append('</ul>')
    if in_code and buf:
        html.append(f'<div style="background:{cbg};color:{cfg};padding:10px 14px;border-radius:8px;'
                    f'font-family:monospace;font-size:12px;margin:6px 0;white-space:pre;">'
                    f'{"<br>".join(buf)}</div>')
    return ''.join(html)
