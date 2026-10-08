"""Colours, font sizes and markdown rendering shared by the AI chat widgets."""
import logging
import re

from PySide6.QtWidgets import QListView

from tools.theme import theme as global_theme

_itk_log = logging.getLogger("IsotopeTrack.results.ai.theme")


class Theme:
    """Light and dark palettes for the chat window, following the app theme."""

    _dark = False
    LIGHT = {
        'bg': '#F8FAFC', 'bg_secondary': '#F1F5F9', 'bg_tertiary': '#E2E8F0',
        'surface': '#FFFFFF', 'surface_hover': '#F1F5F9',
        'border': '#CBD5E1', 'border_light': '#E2E8F0',
        'text': '#0F172A', 'text_secondary': '#475569', 'text_tertiary': '#94A3B8',
        'accent': '#3B82F6', 'accent_hover': '#60A5FA', 'accent_surface': '#EFF6FF',
        'user_bubble': '#3B82F6', 'user_text': '#FFFFFF',
        'ai_bubble': '#FFFFFF', 'ai_text': '#0F172A',
        'think_bg': '#F0FDF4', 'think_border': '#BBF7D0', 'think_text': '#166534',
        'error_bg': '#FEF2F2', 'error_border': '#FECACA', 'error_text': '#991B1B',
        'warn_bg': '#FFFBEB', 'warn_border': '#FDE68A', 'warn_text': '#92400E',
        'code_bg': '#0F172A', 'code_text': '#E2E8F0',
        'input_bg': '#FFFFFF', 'input_border': '#CBD5E1', 'input_focus': '#3B82F6',
        'scrollbar_bg': '#E2E8F0', 'scrollbar_handle': '#94A3B8',
        'success_dot': '#22C55E', 'warn_dot': '#F59E0B', 'error_dot': '#EF4444',
        'progress_bg': '#E2E8F0', 'progress_chunk': '#3B82F6',
        'sug_bg': '#F8FAFC', 'sug_text': '#334155', 'sug_border': '#CBD5E1',
        'sug_hover_bg': '#EFF6FF', 'sug_hover_border': '#3B82F6', 'sug_hover_text': '#2563EB',
        'stop_bg': '#EF4444', 'stop_hover': '#DC2626', 'speed_text': '#94A3B8',
        'output_bg': '#0F172A', 'output_border': '#1E293B', 'output_text': '#94A3B8',
    }
    DARK = {
        'bg': '#0F172A', 'bg_secondary': '#1E293B', 'bg_tertiary': '#334155',
        'surface': '#1E293B', 'surface_hover': '#334155',
        'border': '#334155', 'border_light': '#1E293B',
        'text': '#F1F5F9', 'text_secondary': '#94A3B8', 'text_tertiary': '#64748B',
        'accent': '#3B82F6', 'accent_hover': '#60A5FA', 'accent_surface': '#1E3A5F',
        'user_bubble': '#2563EB', 'user_text': '#FFFFFF',
        'ai_bubble': '#1E293B', 'ai_text': '#F1F5F9',
        'think_bg': '#052E16', 'think_border': '#166534', 'think_text': '#4ADE80',
        'error_bg': '#450A0A', 'error_border': '#7F1D1D', 'error_text': '#FCA5A5',
        'warn_bg': '#422006', 'warn_border': '#854D0E', 'warn_text': '#FCD34D',
        'code_bg': '#020617', 'code_text': '#CBD5E1',
        'input_bg': '#1E293B', 'input_border': '#334155', 'input_focus': '#3B82F6',
        'scrollbar_bg': '#1E293B', 'scrollbar_handle': '#475569',
        'success_dot': '#22C55E', 'warn_dot': '#FBBF24', 'error_dot': '#F87171',
        'progress_bg': '#334155', 'progress_chunk': '#3B82F6',
        'sug_bg': '#1E293B', 'sug_text': '#CBD5E1', 'sug_border': '#334155',
        'sug_hover_bg': '#1E3A5F', 'sug_hover_border': '#3B82F6', 'sug_hover_text': '#60A5FA',
        'stop_bg': '#DC2626', 'stop_hover': '#B91C1C', 'speed_text': '#64748B',
        'output_bg': '#020617', 'output_border': '#1E293B', 'output_text': '#94A3B8',
    }

    @classmethod
    def is_dark(cls):
        """Return whether the dark palette is active."""
        return cls._dark

    @classmethod
    def toggle(cls):
        """Switch between the light and dark palettes."""
        cls._dark = not cls._dark

    @classmethod
    def sync_with_global(cls):
        """Follow the application-wide theme."""
        cls._dark = global_theme.is_dark

    @classmethod
    def c(cls, key):
        """Return the colour for *key* in the active palette.

        Args:
            key (str): Palette entry name.

        Returns:
            str: Hex colour, magenta when the key is unknown.
        """
        return (cls.DARK if cls._dark else cls.LIGHT).get(key, '#FF00FF')


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


def style_combo_popup(combo):
    """Make a combo box drop-down readable inside themed dialogs.

    On macOS the popup is a separate top-level window, so the dialog-scoped
    theme rules do not always reach it and the list renders as an empty panel
    with invisible rows. Giving the combo an explicit list view and styling that
    view directly guarantees visible, clickable items.

    Args:
        combo (QComboBox): Combo box to fix.

    Returns:
        QComboBox: The same combo, for chaining.
    """
    try:
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


def strip_thinking(text):
    """Remove reasoning blocks, including one still being streamed.

    Args:
        text (str): Raw model output.

    Returns:
        str: Text without ``<think>`` sections.
    """
    text = THINK_RE.sub('', text or '')
    return OPEN_THINK_RE.sub('', text)


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
