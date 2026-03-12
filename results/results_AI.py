"""
ai_assistant_improved.py
━━━━━━━━━━━━━━━━━━━━━━━━
Drop-in replacement for your AI assistant module.

Key improvements over the original:
  1. MEMORY  — uses /api/chat endpoint with full message history
  2. FIGURES — model writes real matplotlib Python code, executed locally
  3. SMARTER PROMPT — domain-specific for spICP-ToF-MS / nanoparticle data
  4. THINKING — shows <think>...</think> blocks from reasoning models (DeepSeek-R1)
  5. EXPORT   — every figure has a Save button (PNG / PDF / SVG vector)
  6. SANDBOXED EXEC — restricted __builtins__, timeout protection
  7. AUTO-RETRY — code errors are fed back to model for self-correction (max 2)
  8. SLIDING HISTORY — conversation trimmed to fit context window
  9. MARKDOWN — rich rendering: headers, lists, tables, fenced code
 10. DARK MODE — Claude-style dark theme with smooth toggle
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QFrame,
    QTextEdit, QProgressBar, QMessageBox,
    QGroupBox, QSpinBox, QComboBox, QSlider,
    QScrollArea, QWidget, QMenu, QDialogButtonBox,
    QFileDialog, QSizePolicy, QCheckBox,
)
from PySide6.QtCore import QObject, Signal, QPointF, QThread, QTimer, Qt
from PySide6.QtGui import QPixmap, QImage, QFont, QCursor, QColor, QPalette
import requests
import io
import re
import signal
import math
import threading
import traceback
from collections import Counter, defaultdict
import numpy as np

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure as MplFigure


# ═══════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════

OLLAMA_BASE    = "http://localhost:11434"
OLLAMA_CHAT    = f"{OLLAMA_BASE}/api/chat"
OLLAMA_TAGS    = f"{OLLAMA_BASE}/api/tags"

PREFERRED_DEFAULTS = ['deepseek-r1:14b', 'deepseek-r1:7b', 'qwen2.5:14b',
                      'qwen2.5-coder:7b', 'llama3.2']

MODEL_FAMILIES = {
    'deepseek': ('#059669', 'DeepSeek — best reasoning & analysis'),
    'qwen':     ('#DC2626', 'Qwen — multilingual & technical'),
    'llama':    ('#4F46E5', 'Llama — balanced general tasks'),
    'phi':      ('#7C3AED', 'Phi — compact & efficient'),
    'gemma':    ('#F59E0B', 'Gemma — Google research models'),
    'mistral':  ('#0EA5E9', 'Mistral — fast inference'),
}

PLOT_COLORS = [
    '#663399', '#2E86AB', '#A23B72', '#F18F01', '#C73E1D',
    '#2D6A4F', '#7209B7', '#3A86FF', '#FB5607', '#8338EC',
    '#06D6A0', '#118AB2', '#EF476F', '#FFD166', '#073B4C',
]

DATA_FIELDS = {
    'counts':     'elements',
    'mass':       'element_mass_fg',
    'diameter':   'element_diameter_nm',
    'moles':      'element_moles_fmol',
    'p_mass':     'particle_mass_fg',
    'p_diameter': 'particle_diameter_nm',
    'p_moles':    'particle_moles_fmol',
}

DATA_UNITS = {
    'counts':     'Counts',
    'mass':       'Mass (fg)',
    'diameter':   'Diameter (nm)',
    'moles':      'Moles (fmol)',
    'p_mass':     'Particle Mass (fg)',
    'p_diameter': 'Particle Diameter (nm)',
    'p_moles':    'Particle Moles (fmol)',
}

# Maximum code execution time in seconds
CODE_EXEC_TIMEOUT = 30
# Maximum auto-retry attempts for failed code
MAX_CODE_RETRIES = 2
# Rough chars-per-token estimate for history trimming
CHARS_PER_TOKEN = 3.5


# ═══════════════════════════════════════════════════════════════
# Theme system — Claude-style dark mode
# ═══════════════════════════════════════════════════════════════

class Theme:
    """Centralised theme colours. Switch between light and dark."""

    _dark = False

    # ── Light palette ──
    LIGHT = {
        'bg':              '#FFFFFF',
        'bg_secondary':    '#FAFAFA',
        'bg_tertiary':     '#F3F4F6',
        'surface':         '#FFFFFF',
        'surface_hover':   '#F9FAFB',
        'border':          '#E5E7EB',
        'border_light':    '#F3F4F6',
        'text':            '#1F2937',
        'text_secondary':  '#6B7280',
        'text_tertiary':   '#9CA3AF',
        'accent':          '#D97706',        # warm amber — Claude vibe
        'accent_hover':    '#B45309',
        'accent_surface':  '#FFFBEB',
        'user_bubble':     '#D97706',
        'user_bubble_hover': '#B45309',
        'user_text':       '#FFFFFF',
        'ai_bubble':       '#F3F4F6',
        'ai_text':         '#1F2937',
        'think_bg':        '#F0FDF4',
        'think_border':    '#BBF7D0',
        'think_text':      '#166534',
        'error_bg':        '#FEF2F2',
        'error_border':    '#FECACA',
        'error_text':      '#991B1B',
        'error_code_bg':   '#FEE2E2',
        'ctx_bg':          '#F0FDF4',
        'ctx_border':      '#BBF7D0',
        'ctx_text':        '#166534',
        'banner_bg':       '#FFFBEB',
        'banner_border':   '#FDE68A',
        'banner_text':     '#92400E',
        'code_bg':         '#1F2937',
        'code_text':       '#E5E7EB',
        'input_bg':        '#FFFFFF',
        'input_border':    '#D1D5DB',
        'input_focus':     '#D97706',
        'scrollbar_bg':    '#F3F4F6',
        'scrollbar_handle': '#D1D5DB',
        'success_dot':     '#10B981',
        'warn_dot':        '#F59E0B',
        'error_dot':       '#EF4444',
        'progress_bg':     '#E5E7EB',
        'progress_chunk':  '#D97706',
        'badge_bg':        '#D1FAE5',
        'badge_text':      '#065F46',
        'sug_bg':          '#F8FAFC',
        'sug_text':        '#374151',
        'sug_border':      '#E5E7EB',
        'sug_hover_bg':    '#FFFBEB',
        'sug_hover_border': '#D97706',
        'sug_hover_text':  '#B45309',
        'fig_border':      '#E5E7EB',
        'fig_bg':          '#FFFFFF',
        'fig_btn_bg':      '#F3F4F6',
        'fig_btn_border':  '#D1D5DB',
    }

    # ── Dark palette — inspired by Claude's dark UI ──
    DARK = {
        'bg':              '#1A1A1A',
        'bg_secondary':    '#212121',
        'bg_tertiary':     '#2A2A2A',
        'surface':         '#262626',
        'surface_hover':   '#303030',
        'border':          '#3A3A3A',
        'border_light':    '#333333',
        'text':            '#ECECEC',
        'text_secondary':  '#A0A0A0',
        'text_tertiary':   '#707070',
        'accent':          '#E8A745',        # warm gold
        'accent_hover':    '#D4922E',
        'accent_surface':  '#2D2518',
        'user_bubble':     '#C8871E',
        'user_bubble_hover': '#B07518',
        'user_text':       '#FFFFFF',
        'ai_bubble':       '#2A2A2A',
        'ai_text':         '#ECECEC',
        'think_bg':        '#1A2E1A',
        'think_border':    '#2D4A2D',
        'think_text':      '#7FCC7F',
        'error_bg':        '#2E1A1A',
        'error_border':    '#4A2D2D',
        'error_text':      '#F08080',
        'error_code_bg':   '#351E1E',
        'ctx_bg':          '#1A2E1A',
        'ctx_border':      '#2D4A2D',
        'ctx_text':        '#7FCC7F',
        'banner_bg':       '#2D2518',
        'banner_border':   '#4A3A20',
        'banner_text':     '#E8C56A',
        'code_bg':         '#0D0D0D',
        'code_text':       '#D4D4D4',
        'input_bg':        '#262626',
        'input_border':    '#3A3A3A',
        'input_focus':     '#E8A745',
        'scrollbar_bg':    '#212121',
        'scrollbar_handle': '#404040',
        'success_dot':     '#34D399',
        'warn_dot':        '#FBBF24',
        'error_dot':       '#F87171',
        'progress_bg':     '#333333',
        'progress_chunk':  '#E8A745',
        'badge_bg':        '#1A2E1A',
        'badge_text':      '#7FCC7F',
        'sug_bg':          '#262626',
        'sug_text':        '#C0C0C0',
        'sug_border':      '#3A3A3A',
        'sug_hover_bg':    '#2D2518',
        'sug_hover_border': '#E8A745',
        'sug_hover_text':  '#E8A745',
        'fig_border':      '#3A3A3A',
        'fig_bg':          '#262626',
        'fig_btn_bg':      '#333333',
        'fig_btn_border':  '#444444',
    }

    @classmethod
    def is_dark(cls):
        return cls._dark

    @classmethod
    def set_dark(cls, dark: bool):
        cls._dark = dark

    @classmethod
    def toggle(cls):
        cls._dark = not cls._dark

    @classmethod
    def c(cls, key: str) -> str:
        """Get colour for current theme."""
        palette = cls.DARK if cls._dark else cls.LIGHT
        return palette.get(key, '#FF00FF')  # magenta = missing key


# ═══════════════════════════════════════════════════════════════
# Data extraction helpers
# ═══════════════════════════════════════════════════════════════

def _safe_positive(v):
    try:
        v = float(v)
        return v > 0 and not np.isnan(v)
    except (TypeError, ValueError):
        return False


def _extract_element_values(particles, data_type='counts'):
    field = DATA_FIELDS.get(data_type, 'elements')
    result = {}
    for p in particles:
        d = p.get(field, {})
        if not isinstance(d, dict):
            continue
        for el, v in d.items():
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            if v > 0 and not np.isnan(v):
                result.setdefault(el, []).append(v)
    return result


def _extract_element_counts(particles):
    counts = {}
    for p in particles:
        for el, v in p.get('elements', {}).items():
            if _safe_positive(v):
                counts[el] = counts.get(el, 0) + 1
    return counts


def _extract_combinations(particles):
    combos = {}
    for p in particles:
        detected = sorted(
            el for el, v in p.get('elements', {}).items() if _safe_positive(v))
        if detected:
            key = ' + '.join(detected)
            combos[key] = combos.get(key, 0) + 1
    return combos


def _extract_cooccurrence(particles, top_n=15):
    counts = _extract_element_counts(particles)
    top_elems = [el for el, _ in sorted(counts.items(), key=lambda x: -x[1])[:top_n]]
    n = len(top_elems)
    matrix = np.zeros((n, n), dtype=int)
    idx = {el: i for i, el in enumerate(top_elems)}
    for p in particles:
        present = [el for el in top_elems if _safe_positive(p.get('elements', {}).get(el, 0))]
        for i, a in enumerate(present):
            for b in present[i:]:
                matrix[idx[a]][idx[b]] += 1
                if a != b:
                    matrix[idx[b]][idx[a]] += 1
    return top_elems, matrix


def _extract_by_sample(particles, data_context):
    names = data_context.get('sample_names', [])
    by_sample = {}
    for p in particles:
        src = p.get('source_sample', '')
        if src:
            by_sample.setdefault(src, []).append(p)
    ordered = {}
    for name in names:
        if name in by_sample:
            ordered[name] = by_sample[name]
    for name, ps in by_sample.items():
        if name not in ordered:
            ordered[name] = ps
    return ordered


# ═══════════════════════════════════════════════════════════════
# Figure execution helpers
# ═══════════════════════════════════════════════════════════════

def _apply_style():
    for style in ['seaborn-v0_8-whitegrid', 'seaborn-whitegrid']:
        try:
            plt.style.use(style)
            return
        except OSError:
            continue


def _fig_to_pixmap(fig):
    fig.set_facecolor('white')
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    img = QImage()
    img.loadFromData(buf.getvalue())
    if img.isNull():
        return None
    return QPixmap.fromImage(img)


def _re_render_figure(code, particles, data_context, path, fmt):
    """Re-execute code and save as vector format (PDF/SVG)."""
    _, err = _execute_raw_code(code, particles, data_context, return_fig=True)
    if err:
        return False, err
    fig = plt.gcf()
    if not fig.get_axes():
        plt.close(fig)
        return False, "No figure produced on re-render."
    try:
        fig.savefig(path, format=fmt, dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        plt.close(fig)
        return True, None
    except Exception as e:
        plt.close(fig)
        return False, str(e)


# ── Sandbox builtins whitelist ───────────────────────────────

_SAFE_BUILTINS = {
    'abs': abs, 'all': all, 'any': any, 'bin': bin, 'bool': bool,
    'bytes': bytes, 'chr': chr, 'dict': dict, 'divmod': divmod,
    'enumerate': enumerate, 'filter': filter, 'float': float,
    'format': format, 'frozenset': frozenset, 'getattr': getattr,
    'hasattr': hasattr, 'hash': hash, 'hex': hex, 'int': int,
    'isinstance': isinstance, 'issubclass': issubclass, 'iter': iter,
    'len': len, 'list': list, 'map': map, 'max': max, 'min': min,
    'next': next, 'oct': oct, 'ord': ord, 'pow': pow, 'print': print,
    'range': range, 'repr': repr, 'reversed': reversed, 'round': round,
    'set': set, 'slice': slice, 'sorted': sorted, 'str': str,
    'sum': sum, 'tuple': tuple, 'type': type, 'zip': zip,
    'True': True, 'False': False, 'None': None,
    'ValueError': ValueError, 'TypeError': TypeError,
    'KeyError': KeyError, 'IndexError': IndexError,
    'RuntimeError': RuntimeError, 'StopIteration': StopIteration,
    'ZeroDivisionError': ZeroDivisionError,
    'Exception': Exception,
}


# ── Code block regex ─────────────────────────────────────────

_CODE_RE = re.compile(r'```python\s*\n(.*?)```', re.DOTALL)
_THINK_RE = re.compile(r'<think>.*?</think>', re.DOTALL)

# Regex to strip import lines that the model habitually writes
# (np, plt, stats etc. are already pre-loaded in the namespace)
_IMPORT_RE = re.compile(
    r'^\s*(?:import\s+\w+(?:\.\w+)*(?:\s+as\s+\w+)?'
    r'|from\s+\w+(?:\.\w+)*\s+import\s+.+)\s*$',
    re.MULTILINE
)


def _sanitize_code(code: str) -> str:
    """
    Strip import statements from model-generated code.
    The model habitually writes 'import numpy as np' etc.
    but these are already injected into the execution namespace.
    Also strips plt.show() and plt.savefig() calls.
    """
    # Remove import lines
    code = _IMPORT_RE.sub('', code)
    # Remove plt.show() and plt.savefig(...) calls
    code = re.sub(r'^\s*plt\.show\(\)\s*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^\s*plt\.savefig\(.*?\)\s*$', '', code, flags=re.MULTILINE)
    # Remove any os/sys/subprocess usage that slipped through
    code = re.sub(r'^\s*(?:os|sys|subprocess)\..*$', '# blocked', code, flags=re.MULTILINE)
    return code.strip()


def _execute_raw_code(code, particles, data_context, return_fig=False):
    """
    Execute matplotlib Python code written by the model.
    Uses restricted __builtins__ and a timeout thread.
    If return_fig=True, leaves the figure open for vector re-render.
    """
    # ★ Sanitize: strip imports and dangerous calls
    code = _sanitize_code(code)
    elem_vals  = _extract_element_values(particles, 'counts')
    by_sample  = _extract_by_sample(particles, data_context) if data_context else {}

    all_diameters = [v for vals in _extract_element_values(particles, 'diameter').values() for v in vals]
    all_masses    = [v for vals in _extract_element_values(particles, 'mass').values()     for v in vals]
    all_moles     = [v for vals in _extract_element_values(particles, 'moles').values()    for v in vals]

    p_diameters = [float(p['particle_diameter_nm']) for p in particles
                   if p.get('particle_diameter_nm') and _safe_positive(p.get('particle_diameter_nm', 0))]
    p_masses    = [float(p['particle_mass_fg'])     for p in particles
                   if p.get('particle_mass_fg')     and _safe_positive(p.get('particle_mass_fg', 0))]

    ns = {
        '__builtins__': _SAFE_BUILTINS,       # ★ SANDBOXED
        'np': np, 'plt': plt, 'Figure': MplFigure,
        'math': math,                         # ★ models often use math.log etc.
        'Counter': Counter,
        'defaultdict': defaultdict,
        'particles':           particles,
        'elements':            elem_vals,
        'element_counts':      _extract_element_counts(particles),
        'masses':              _extract_element_values(particles, 'mass'),
        'diameters':           _extract_element_values(particles, 'diameter'),
        'moles':               _extract_element_values(particles, 'moles'),
        'all_diameters':       all_diameters,
        'all_masses':          all_masses,
        'all_moles':           all_moles,
        'particle_diameters':  p_diameters,
        'particle_masses':     p_masses,
        'sample_names':        data_context.get('sample_names', []) if data_context else [],
        'sample_name':         data_context.get('sample_name', 'Sample') if data_context else 'Sample',
        'by_sample':           by_sample,
        'data_context':        data_context or {},
        'COLORS':              PLOT_COLORS,
    }
    try:
        from scipy import stats as sp_stats
        ns['stats'] = sp_stats
    except ImportError:
        pass

    # ── Common wrong-key suggestions for better auto-retry ──
    _KEY_HINTS = {
        'diameter_nm':    'Use particle_diameters (flat list) or diameters[element_label]',
        'diameter':       'Use particle_diameters (flat list) or diameters[element_label]',
        'mass':           'Use particle_masses (flat list) or masses[element_label]',
        'mass_fg':        'Use particle_masses (flat list) or masses[element_label]',
        'moles':          'Use all_moles (flat list) or moles[element_label]',
        'size':           'Use particle_diameters (flat list)',
        'count':          'Use element_counts[element_label]',
        'counts':         'Use elements[element_label] for count values list',
        'name':           'Use sample_name (str) or sample_names (list)',
        'sample':         'Use sample_name (str) or by_sample[name] for particles',
    }

    # ── Execute with timeout ──
    exec_error = [None]
    exec_done = threading.Event()

    def _run():
        try:
            plt.close('all')
            exec(code, ns)
        except KeyError as e:
            key = str(e).strip("'\"")
            hint = ''
            # Check for known wrong keys
            for wrong, fix in _KEY_HINTS.items():
                if wrong in key.lower():
                    hint = f"\n\n💡 FIX: {fix}"
                    break
            # Check if it looks like an element access on a particle dict
            if not hint and any(c.isalpha() for c in key):
                hint = (
                    "\n\n💡 Don't access particle dicts directly. "
                    "Use pre-loaded variables:\n"
                    "  particle_diameters → flat list of all diameters\n"
                    "  particle_masses    → flat list of all masses\n"
                    "  diameters['Fe 56'] → per-element diameter list\n"
                    "  elements['Fe 56']  → per-element count values\n"
                    "  element_counts     → {element: n_particles}\n"
                    "  list(elements.keys()) → available element names"
                )
            exec_error[0] = f"KeyError: {e}{hint}"
        except Exception as e:
            exec_error[0] = f"{type(e).__name__}: {e}"
        finally:
            exec_done.set()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=CODE_EXEC_TIMEOUT)

    if t.is_alive():
        plt.close('all')
        return None, f"Timeout: code took longer than {CODE_EXEC_TIMEOUT}s — try simpler logic."

    if exec_error[0]:
        plt.close('all')
        return None, exec_error[0]

    fig = plt.gcf()
    if not fig.get_axes():
        plt.close(fig)
        return None, "Code ran but produced no figure."

    if return_fig:
        return fig, None

    return _fig_to_pixmap(fig), None


def _parse_response(text, particles, data_context):
    """
    Parse AI response → list of:
      ('text',   str)
      ('think',  str)
      ('figure', QPixmap, src_code)
      ('error',  msg,     src_code)
    """
    parts = []

    # 1. Strip and expose <think> blocks
    think_parts = _THINK_RE.findall(text)
    clean_text  = _THINK_RE.sub('', text).strip()

    for t in think_parts:
        inner = t.replace('<think>', '').replace('</think>', '').strip()
        if inner:
            parts.append(('think', inner))

    # 2. Extract ```python blocks from cleaned text
    code_blocks = list(_CODE_RE.finditer(clean_text))
    if code_blocks:
        last_end = 0
        for m in code_blocks:
            before = clean_text[last_end:m.start()].strip()
            if before:
                parts.append(('text', before))
            code = m.group(1).strip()
            if particles:
                pix, err = _execute_raw_code(code, particles, data_context)
                if pix:
                    parts.append(('figure', pix, code))
                elif err:
                    parts.append(('error', err, code))
            else:
                parts.append(('text', f"```python\n{code}\n```"))
            last_end = m.end()
        tail = clean_text[last_end:].strip()
        if tail:
            parts.append(('text', tail))
    elif clean_text:
        parts.append(('text', clean_text))

    if not parts:
        parts.append(('text', text))

    return parts


# ═══════════════════════════════════════════════════════════════
# Improved markdown → HTML
# ═══════════════════════════════════════════════════════════════

def _md_to_html(text):
    """Convert markdown text to HTML with theme-aware colours."""
    lines = text.split('\n')
    html_lines = []
    in_code = False
    in_list = False
    code_buf = []

    code_bg = Theme.c('code_bg')
    code_fg = Theme.c('code_text')
    inline_code_bg = Theme.c('bg_tertiary')
    text_sec = Theme.c('text_secondary')
    accent = Theme.c('accent')
    border = Theme.c('border')

    for line in lines:
        # Fenced code blocks (``` not python — display-only)
        if line.strip().startswith('```') and not in_code:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            in_code = True
            code_buf = []
            continue
        if line.strip().startswith('```') and in_code:
            in_code = False
            code_html = '<br>'.join(code_buf)
            html_lines.append(
                f'<div style="background:{code_bg};color:{code_fg};'
                f'padding:10px 14px;border-radius:8px;font-family:Courier New,monospace;'
                f'font-size:12px;margin:6px 0;overflow-x:auto;">{code_html}</div>')
            continue
        if in_code:
            escaped = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            code_buf.append(escaped)
            continue

        stripped = line.strip()

        # Headers
        if stripped.startswith('### '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(
                f'<div style="font-size:14px;font-weight:700;margin:10px 0 4px 0;'
                f'color:{accent};">{_inline_fmt(stripped[4:])}</div>')
            continue
        if stripped.startswith('## '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(
                f'<div style="font-size:15px;font-weight:700;margin:12px 0 4px 0;'
                f'">{_inline_fmt(stripped[3:])}</div>')
            continue
        if stripped.startswith('# '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(
                f'<div style="font-size:16px;font-weight:700;margin:14px 0 6px 0;'
                f'">{_inline_fmt(stripped[2:])}</div>')
            continue

        # Horizontal rule
        if stripped in ('---', '***', '___'):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(
                f'<hr style="border:none;border-top:1px solid {border};margin:8px 0;">')
            continue

        # Unordered list
        if stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                html_lines.append(
                    f'<ul style="margin:4px 0 4px 18px;padding:0;'
                    f'list-style-type:disc;">')
                in_list = True
            html_lines.append(
                f'<li style="margin:2px 0;">{_inline_fmt(stripped[2:])}</li>')
            continue

        # Ordered list
        m = re.match(r'^(\d+)\.\s+(.*)$', stripped)
        if m:
            if not in_list:
                html_lines.append(
                    '<ol style="margin:4px 0 4px 18px;padding:0;">')
                in_list = True
            html_lines.append(
                f'<li style="margin:2px 0;">{_inline_fmt(m.group(2))}</li>')
            continue

        # Close list if we hit a non-list line
        if in_list:
            html_lines.append('</ul>')
            in_list = False

        # Empty line
        if not stripped:
            html_lines.append('<div style="height:6px;"></div>')
            continue

        # Regular paragraph
        html_lines.append(f'<div style="margin:2px 0;">{_inline_fmt(stripped)}</div>')

    if in_list:
        html_lines.append('</ul>')
    if in_code:
        code_html = '<br>'.join(code_buf)
        html_lines.append(
            f'<div style="background:{code_bg};color:{code_fg};'
            f'padding:10px 14px;border-radius:8px;font-family:monospace;'
            f'font-size:12px;margin:6px 0;">{code_html}</div>')

    return ''.join(html_lines)


def _inline_fmt(text):
    """Apply inline formatting: bold, italic, code, links."""
    inline_bg = Theme.c('bg_tertiary')
    # Bold
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic
    t = re.sub(r'\*(.+?)\*', r'<i>\1</i>', t)
    # Inline code
    t = re.sub(
        r'`(.+?)`',
        rf'<code style="background:{inline_bg};padding:1px 5px;'
        rf'border-radius:3px;font-family:Courier New,monospace;font-size:12px;">\1</code>',
        t)
    # Links
    t = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', t)
    return t


# ═══════════════════════════════════════════════════════════════
# History management — sliding window
# ═══════════════════════════════════════════════════════════════

def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / CHARS_PER_TOKEN))


def _trim_history(history: list, max_tokens: int) -> list:
    """
    Keep the most recent messages that fit within max_tokens.
    Always preserves at least the last user+assistant exchange.
    """
    if not history:
        return history

    # Count from the end
    total = 0
    cut = len(history)
    for i in range(len(history) - 1, -1, -1):
        msg_tokens = _estimate_tokens(history[i].get('content', ''))
        if total + msg_tokens > max_tokens:
            cut = i + 1
            break
        total += msg_tokens
    else:
        cut = 0

    # Ensure at least last 2 messages
    cut = min(cut, max(0, len(history) - 2))
    return history[cut:]


# ═══════════════════════════════════════════════════════════════
# System prompt  — domain-specific for spICP-ToF-MS
# ═══════════════════════════════════════════════════════════════

def _build_system_prompt(data_context):
    base = """You are an expert analytical chemist specialising in single-particle ICP-ToF-MS (spICP-ToF-MS) and nanoparticle characterisation.

CAPABILITIES
You can generate figures by writing Python code blocks (```python ... ```) that use:
  - matplotlib.pyplot as plt  (always available)
  - numpy as np
  - scipy.stats as stats
  - math module (math.log, math.sqrt, etc.)
  - Counter and defaultdict from collections
  - The following pre-loaded data variables:
      particles          → list of particle dicts (do NOT access particle['diameter_nm'] directly)
      elements           → {element: [count_values]}          e.g. elements['Fe 56'] = [120, 340, ...]
      element_counts     → {element: n_particles}
      masses             → {element: [mass_fg_values]}        per element
      diameters          → {element: [diameter_nm_values]}    per element
      moles              → {element: [moles_fmol_values]}     per element
      all_diameters      → flat [float, ...] all element diameters combined
      all_masses         → flat [float, ...] all element masses combined
      particle_diameters → flat [float, ...] per-particle total diameter (nm)
      particle_masses    → flat [float, ...] per-particle total mass (fg)
      sample_name        → name of current sample (str)
      sample_names       → list of all sample names
      by_sample          → {sample_name: [particles]}  for multi-sample plots
      COLORS             → list of professional hex colours

IMPORTANT DATA ACCESS RULES:
- NEVER do particle['diameter_nm'] or particle['mass'] — these keys do not exist
- For size distribution use: particle_diameters  (already a flat list, ready to plot)
- For per-element diameter: diameters['Fe 56']  (element name must match exactly)
- Element names include the mass number, e.g. 'Fe 56', 'Au 197', 'Ag 107'
- To get element names: list(elements.keys())

FIGURE RULES
- Always call plt.figure() or plt.subplots() at the start
- Set fig.set_facecolor('white')
- Add proper axis labels and a title
- Use COLORS list for consistent colouring
- Do NOT call plt.show() or plt.savefig() — the app handles saving
- For size distributions: use np.log10 scale on x-axis if range > 2 orders of magnitude
- For multi-element: use subplots not separate figures

SANDBOX RULES
- Do NOT write any import statements — they will be stripped and may cause errors
- np, plt, stats, math, Counter, defaultdict are ALREADY available — just use them directly
- Do NOT use open(), os, sys, subprocess, or any file/network operations
- Do NOT call plt.show() or plt.savefig() — the app handles rendering

SCIENTIFIC CONTEXT
- spICP-ToF-MS measures elemental composition of individual nanoparticles in suspension
- Each "particle" dict contains detected elements and their signal intensities (counts),
  converted mass (fg), equivalent spherical diameter (nm), and moles (fmol)
- Multi-element particles are real heterogeneous NPs or agglomerates
- Single-element particles are either pure NPs or matrix background signals
- Diameter is calculated from mass assuming known density — flag if density unknown
- Common artefacts: oxide interferences (e.g. Ce16O on Gd), doubly charged ions,
  dissolved background contributing false low-intensity particles

RESPONSE STYLE
- Be direct and quantitative — cite actual numbers from the data
- Interpret figures immediately after the code block
- Flag potential artefacts or data quality issues when relevant
- Keep reasoning concise unless asked to elaborate
- For multi-sample comparisons always normalise by particle count before comparing"""

    if not data_context:
        return base + "\n\nSTATUS: No data loaded yet."

    particles = data_context.get('particle_data', [])
    n = len(particles)
    if n == 0:
        return base + "\n\nSTATUS: Dataset connected but 0 particles found."

    elem_counts  = _extract_element_counts(particles)
    combos       = _extract_combinations(particles)
    top_elems    = sorted(elem_counts.items(), key=lambda x: -x[1])
    top_combos   = sorted(combos.items(), key=lambda x: -x[1])
    single       = sum(1 for p in particles
                       if sum(1 for v in p.get('elements', {}).values()
                              if _safe_positive(v)) == 1)

    avail = ['counts']
    for dt, field in [('mass','element_mass_fg'), ('diameter','element_diameter_nm'),
                      ('moles','element_moles_fmol')]:
        if any(p.get(field) for p in particles[:200]):
            avail.append(dt)

    ctx = "\n\n━━━ LOADED DATASET ━━━\n"
    dtype = data_context.get('type', '')
    if dtype == 'sample_data':
        ctx += f"Sample: {data_context.get('sample_name', '?')}\n"
    elif dtype == 'multiple_sample_data':
        names = data_context.get('sample_names', [])
        ctx += f"Samples ({len(names)}): {', '.join(names[:8])}\n"

    ctx += (
        f"Total particles : {n:,}\n"
        f"Single-element  : {single:,} ({single/n*100:.1f}%)\n"
        f"Multi-element   : {n-single:,} ({(n-single)/n*100:.1f}%)\n"
        f"Unique elements : {len(elem_counts)}\n"
        f"Data types      : {', '.join(avail)}\n\n"
        f"ELEMENT FREQUENCIES (top 25):\n"
    )
    for el, cnt in top_elems[:25]:
        bar = '█' * int(cnt/n*30)
        ctx += f"  {el:6s} {cnt:6,} ({cnt/n*100:5.1f}%)  {bar}\n"
    if len(top_elems) > 25:
        ctx += f"  ... +{len(top_elems)-25} more elements\n"

    ctx += "\nTOP 12 COMBINATIONS:\n"
    for combo, cnt in top_combos[:12]:
        ctx += f"  {cnt:6,} ({cnt/n*100:4.1f}%)  {combo}\n"

    return base + ctx


# ═══════════════════════════════════════════════════════════════
# Background workers
# ═══════════════════════════════════════════════════════════════

class OllamaStatusWorker(QThread):
    status_ready = Signal(bool, str, list)

    def run(self):
        try:
            r = requests.get(OLLAMA_TAGS, timeout=10)
            if r.status_code != 200:
                self.status_ready.emit(False, "Ollama not responding", [])
                return
            names = [m.get('name', '') for m in r.json().get('models', [])]
            self.status_ready.emit(
                True,
                f"{len(names)} models ready" if names else "No models installed",
                names)
        except Exception:
            self.status_ready.emit(False, "Ollama not running — run: ollama serve", [])


class AIGenerateWorker(QThread):
    """
    Uses /api/chat with full message history → conversation memory.
    History is pre-trimmed by the caller to fit within num_ctx.
    """
    response_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, message_history, data_context, model,
                 temperature=0.7, num_ctx=8192):
        super().__init__()
        self.message_history = message_history
        self.data_context    = data_context
        self.model           = model
        self.temperature     = temperature
        self.num_ctx         = num_ctx

    def run(self):
        try:
            system_prompt = _build_system_prompt(self.data_context)

            messages = [{"role": "system", "content": system_prompt}]
            messages += self.message_history

            r = requests.post(OLLAMA_CHAT, json={
                "model":    self.model,
                "messages": messages,
                "stream":   False,
                "options": {
                    "temperature": self.temperature,
                    "top_p":       0.9,
                    "num_ctx":     self.num_ctx,
                    "num_predict": 4096,
                },
            }, timeout=300)

            if r.status_code == 200:
                text = r.json().get('message', {}).get('content', '').strip()
                if text:
                    self.response_ready.emit(text)
                else:
                    self.error_occurred.emit("Empty response from model.")
            else:
                msg = f"Ollama HTTP {r.status_code}"
                try:
                    d = r.json().get('error', '')
                    if d:
                        msg += f": {d}"
                except Exception:
                    pass
                self.error_occurred.emit(msg)

        except requests.exceptions.ConnectionError:
            self.error_occurred.emit("connection_error")
        except requests.exceptions.Timeout:
            self.error_occurred.emit("timeout_error")
        except Exception as e:
            self.error_occurred.emit(str(e))


class AIRetryWorker(QThread):
    """
    Auto-retry worker: sends the error message back to the model
    asking it to fix the code.
    """
    response_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, message_history, data_context, model,
                 error_msg, failed_code, temperature=0.4, num_ctx=8192):
        super().__init__()
        self.message_history = message_history
        self.data_context    = data_context
        self.model           = model
        self.error_msg       = error_msg
        self.failed_code     = failed_code
        self.temperature     = temperature
        self.num_ctx         = num_ctx

    def run(self):
        try:
            system_prompt = _build_system_prompt(self.data_context)

            retry_msg = (
                f"Your previous code produced this error:\n"
                f"```\n{self.error_msg}\n```\n\n"
                f"The failing code was:\n"
                f"```python\n{self.failed_code}\n```\n\n"
                f"Please fix the code and try again. "
                f"Remember: use only the pre-loaded variables "
                f"(elements, diameters, particle_diameters, etc). "
                f"Do NOT use import statements."
            )

            messages = [{"role": "system", "content": system_prompt}]
            messages += self.message_history
            messages.append({"role": "user", "content": retry_msg})

            r = requests.post(OLLAMA_CHAT, json={
                "model":    self.model,
                "messages": messages,
                "stream":   False,
                "options": {
                    "temperature": self.temperature,
                    "top_p":       0.9,
                    "num_ctx":     self.num_ctx,
                    "num_predict": 4096,
                },
            }, timeout=300)

            if r.status_code == 200:
                text = r.json().get('message', {}).get('content', '').strip()
                if text:
                    self.response_ready.emit(text)
                else:
                    self.error_occurred.emit("Empty retry response.")
            else:
                self.error_occurred.emit(f"Retry HTTP {r.status_code}")
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit("connection_error")
        except requests.exceptions.Timeout:
            self.error_occurred.emit("timeout_error")
        except Exception as e:
            self.error_occurred.emit(str(e))


# ═══════════════════════════════════════════════════════════════
# Chat bubble widgets  (theme-aware)
# ═══════════════════════════════════════════════════════════════

class ThinkBubble(QFrame):
    """Collapsible reasoning block shown for DeepSeek-R1 <think> output."""

    def __init__(self, text):
        super().__init__()
        self._text = text
        self._expanded = False
        self.setContentsMargins(0, 2, 0, 2)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._container = QFrame()
        cl = QVBoxLayout(self._container)
        cl.setContentsMargins(12, 8, 12, 8)

        toggle_row = QHBoxLayout()
        self._toggle_btn = QPushButton("▶  Model reasoning  (click to expand)")
        self._toggle_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._toggle_btn.clicked.connect(self._toggle)
        toggle_row.addWidget(self._toggle_btn)
        toggle_row.addStretch()
        cl.addLayout(toggle_row)

        self._body = QLabel(_md_to_html(text))
        self._body.setWordWrap(True)
        self._body.setTextFormat(Qt.RichText)
        self._body.setVisible(False)
        cl.addWidget(self._body)

        layout.addWidget(self._container)
        self.apply_theme()

    def _toggle(self):
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        self._toggle_btn.setText(
            "▼  Model reasoning  (click to collapse)" if self._expanded
            else "▶  Model reasoning  (click to expand)")

    def apply_theme(self):
        bg = Theme.c('think_bg')
        bd = Theme.c('think_border')
        fg = Theme.c('think_text')
        self._container.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 1px solid {bd}; border-radius: 10px; }}")
        self._toggle_btn.setStyleSheet(
            f"QPushButton {{ background: none; border: none; color: {fg}; "
            f"font-size: 11px; font-style: italic; text-align: left; padding: 0; }}"
            f"QPushButton:hover {{ color: {fg}; }}")
        self._body.setStyleSheet(f"color: {fg}; font-size: 11px; padding-top: 4px;")
        self._body.setText(_md_to_html(self._text))


class TextBubble(QFrame):

    def __init__(self, text, is_user=False):
        super().__init__()
        self._text = text
        self._is_user = is_user
        self.setContentsMargins(0, 4, 0, 4)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._wrapper = QHBoxLayout()
        self._wrapper.setContentsMargins(0, 0, 0, 0)

        self._bubble = QFrame()
        self._bl = QVBoxLayout(self._bubble)
        self._bl.setContentsMargins(14, 10, 14, 10)

        self._lbl = QLabel()
        self._lbl.setWordWrap(True)
        if not is_user:
            self._lbl.setOpenExternalLinks(True)
            self._lbl.setTextFormat(Qt.RichText)
        self._bl.addWidget(self._lbl)

        if is_user:
            self._wrapper.addStretch()
        self._wrapper.addWidget(self._bubble)
        if not is_user:
            self._wrapper.addStretch()
        layout.addLayout(self._wrapper)
        self.apply_theme()

    def apply_theme(self):
        if self._is_user:
            bg = Theme.c('user_bubble')
            fg = Theme.c('user_text')
            self._bubble.setStyleSheet(
                f"QFrame {{ background: {bg}; color: {fg}; "
                f"border-radius: 16px; border-bottom-right-radius: 4px; }}")
            self._lbl.setStyleSheet(f"color: {fg}; font-size: 14px;")
            self._lbl.setText(self._text)
        else:
            bg = Theme.c('ai_bubble')
            fg = Theme.c('ai_text')
            self._bubble.setStyleSheet(
                f"QFrame {{ background: {bg}; color: {fg}; "
                f"border-radius: 16px; border-bottom-left-radius: 4px; }}")
            self._lbl.setStyleSheet(
                f"color: {fg}; font-size: 14px; line-height: 1.5;")
            self._lbl.setText(_md_to_html(self._text))


class FigureBubble(QFrame):

    def __init__(self, pixmap, source_text="", particles=None, data_context=None):
        super().__init__()
        self._pixmap = pixmap
        self._source = source_text
        self._particles = particles
        self._data_context = data_context
        self.setContentsMargins(0, 4, 0, 4)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._container = QFrame()
        cl = QVBoxLayout(self._container)
        cl.setContentsMargins(8, 8, 8, 6)
        cl.setSpacing(4)

        self._img = QLabel()
        self._img.setAlignment(Qt.AlignCenter)
        scaled = pixmap.scaledToWidth(min(700, pixmap.width()), Qt.SmoothTransformation)
        self._img.setPixmap(scaled)
        cl.addWidget(self._img)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._save_btn = QPushButton("💾 Save")
        self._save_btn.clicked.connect(self._save)
        btn_row.addWidget(self._save_btn)
        if source_text:
            self._code_btn = QPushButton("</> Code")
            self._code_btn.clicked.connect(self._show_code)
            btn_row.addWidget(self._code_btn)
        cl.addLayout(btn_row)
        layout.addWidget(self._container)
        self.apply_theme()

    def _save(self):
        path, filt = QFileDialog.getSaveFileName(
            self, "Save Figure", "figure.png",
            "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if not path:
            return

        ext = path.rsplit('.', 1)[-1].lower() if '.' in path else 'png'

        # ★ Vector export: re-render from code for PDF/SVG
        if ext in ('pdf', 'svg') and self._source and self._particles is not None:
            ok, err = _re_render_figure(
                self._source, self._particles, self._data_context, path, ext)
            if ok:
                return
            # Fallback to raster if re-render fails
            QMessageBox.warning(
                self, "Vector Export",
                f"Vector re-render failed ({err}).\nSaving as rasterised {ext.upper()} instead.")

        self._pixmap.save(path)

    def _show_code(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Figure Code")
        dlg.resize(640, 380)
        vl = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setFont(QFont("Courier New", 11))
        te.setPlainText(self._source)
        code_bg = Theme.c('code_bg')
        code_fg = Theme.c('code_text')
        te.setStyleSheet(
            f"background: {code_bg}; color: {code_fg}; padding: 12px; border-radius: 8px;")
        vl.addWidget(te)
        b = QPushButton("Close")
        b.clicked.connect(dlg.close)
        vl.addWidget(b)
        dlg.exec()

    def apply_theme(self):
        bg = Theme.c('fig_bg')
        bd = Theme.c('fig_border')
        btn_bg = Theme.c('fig_btn_bg')
        btn_bd = Theme.c('fig_btn_border')
        self._container.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 1px solid {bd}; border-radius: 12px; }}")
        btn_style = (
            f"QPushButton {{ background: {btn_bg}; border: 1px solid {btn_bd}; "
            f"border-radius: 6px; padding: 3px 10px; font-size: 11px; "
            f"color: {Theme.c('text')}; }}"
            f"QPushButton:hover {{ background: {Theme.c('surface_hover')}; }}")
        self._save_btn.setStyleSheet(btn_style)
        if hasattr(self, '_code_btn'):
            self._code_btn.setStyleSheet(btn_style)


class ErrorBubble(QFrame):

    def __init__(self, error_text, source_text=""):
        super().__init__()
        self._error_text = error_text
        self._source_text = source_text
        self.setContentsMargins(0, 4, 0, 4)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._container = QFrame()
        cl = QVBoxLayout(self._container)
        cl.setContentsMargins(12, 8, 12, 8)

        self._hdr = QLabel("⚠ Figure generation failed")
        cl.addWidget(self._hdr)

        self._err = QLabel(error_text)
        self._err.setWordWrap(True)
        cl.addWidget(self._err)

        if source_text:
            self._src = QLabel(source_text[:300] + ("…" if len(source_text) > 300 else ""))
            self._src.setWordWrap(True)
            cl.addWidget(self._src)

        layout.addWidget(self._container)
        self.apply_theme()

    def apply_theme(self):
        bg = Theme.c('error_bg')
        bd = Theme.c('error_border')
        fg = Theme.c('error_text')
        code_bg = Theme.c('error_code_bg')
        self._container.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 1px solid {bd}; border-radius: 12px; }}")
        self._hdr.setStyleSheet(f"color: {fg}; font-weight: 600; font-size: 12px;")
        self._err.setStyleSheet(
            f"color: {fg}; font-family: monospace; font-size: 11px; "
            f"background: {code_bg}; padding: 4px 8px; border-radius: 4px;")
        if hasattr(self, '_src'):
            self._src.setStyleSheet(
                f"color: {Theme.c('text_tertiary')}; font-family: monospace; font-size: 10px;")


# ═══════════════════════════════════════════════════════════════
# Settings Dialog
# ═══════════════════════════════════════════════════════════════

class AISettingsDialog(QDialog):

    def __init__(self, config, available_models, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Assistant Settings")
        self.setMinimumWidth(460)
        self._cfg = dict(config)
        self._available = list(available_models)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        bg = Theme.c('bg')
        fg = Theme.c('text')
        sec = Theme.c('text_secondary')
        border = Theme.c('border')
        surface = Theme.c('surface')
        accent = Theme.c('accent')
        self.setStyleSheet(
            f"QDialog {{ background: {bg}; color: {fg}; }}"
            f"QGroupBox {{ border: 1px solid {border}; border-radius: 8px; "
            f"margin-top: 8px; padding-top: 14px; color: {fg}; font-weight: 600; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 12px; "
            f"padding: 0 4px; color: {accent}; }}"
            f"QLabel {{ color: {fg}; }}"
            f"QComboBox {{ border: 1px solid {border}; border-radius: 6px; "
            f"padding: 5px 10px; background: {surface}; color: {fg}; }}"
            f"QSpinBox {{ border: 1px solid {border}; border-radius: 6px; "
            f"padding: 5px; background: {surface}; color: {fg}; }}"
        )

        # Model
        g = QGroupBox("Model")
        fl = QFormLayout(g)
        fl.setSpacing(10)
        self.model_combo = QComboBox()
        if self._available:
            for m in sorted(self._available):
                self.model_combo.addItem(m, m)
            idx = self.model_combo.findData(self._cfg.get('model', ''))
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
        else:
            self.model_combo.addItem("No models available", "none")
        fl.addRow("Active model:", self.model_combo)

        tip = QLabel(
            "Recommended: deepseek-r1:14b (reasoning) · qwen2.5:14b (technical)\n"
            "Pull with: ollama pull deepseek-r1:14b")
        tip.setStyleSheet(f"color: {sec}; font-size: 11px;")
        tip.setWordWrap(True)
        fl.addRow("", tip)
        layout.addWidget(g)

        # Generation
        g = QGroupBox("Generation")
        fl = QFormLayout(g)
        fl.setSpacing(10)
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(1, 20)
        self.temp_slider.setValue(int(self._cfg.get('temperature', 0.6) * 10))
        self._temp_lbl = QLabel(f"{self.temp_slider.value()/10:.1f}")
        self._temp_lbl.setFixedWidth(30)
        self.temp_slider.valueChanged.connect(
            lambda v: self._temp_lbl.setText(f"{v/10:.1f}"))
        row = QHBoxLayout()
        row.addWidget(self.temp_slider)
        row.addWidget(self._temp_lbl)
        fl.addRow("Temperature:", row)
        self.ctx_spin = QSpinBox()
        self.ctx_spin.setRange(2048, 32768)
        self.ctx_spin.setSingleStep(1024)
        self.ctx_spin.setValue(self._cfg.get('num_ctx', 8192))
        fl.addRow("Context window:", self.ctx_spin)
        layout.addWidget(g)

        # Memory info
        g = QGroupBox("Memory")
        fl = QFormLayout(g)
        info = QLabel(
            "✓ Full conversation history is sent with every message.\n"
            "History is automatically trimmed to fit the context window.\n"
            "Use 'Clear Chat' to start a fresh conversation.")
        info.setWordWrap(True)
        success = Theme.c('ctx_text')
        info.setStyleSheet(f"color: {success}; font-size: 12px;")
        fl.addRow(info)
        layout.addWidget(g)

        row = QHBoxLayout()
        test_btn = QPushButton("Test Connection")
        test_btn.setStyleSheet(
            f"QPushButton {{ background: {surface}; border: 1px solid {border}; "
            f"border-radius: 6px; padding: 6px 14px; color: {fg}; }}"
            f"QPushButton:hover {{ background: {Theme.c('surface_hover')}; }}")
        test_btn.clicked.connect(self._test)
        row.addWidget(test_btn)
        row.addStretch()
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        row.addWidget(btns)
        layout.addLayout(row)

    def _test(self):
        try:
            r = requests.get(OLLAMA_TAGS, timeout=5)
            if r.status_code == 200:
                n = len(r.json().get('models', []))
                QMessageBox.information(self, "Test", f"✓ Connected. {n} models available.")
            else:
                QMessageBox.warning(self, "Test", "Ollama responded but returned an error.")
        except Exception:
            QMessageBox.critical(self, "Test",
                "Cannot connect to Ollama.\n\nFix:\n  ollama serve")

    def collect(self):
        return {
            'model':       self.model_combo.currentData() or self.model_combo.currentText(),
            'temperature': self.temp_slider.value() / 10.0,
            'num_ctx':     self.ctx_spin.value(),
        }


# ═══════════════════════════════════════════════════════════════
# Chat Dialog  — with conversation memory + dark mode
# ═══════════════════════════════════════════════════════════════

class AIChatDialog(QDialog):

    def __init__(self, ai_node, parent_window=None):
        super().__init__(parent_window)
        self.node = ai_node
        self.current_data = None
        self._worker = None
        self._retry_worker = None
        self.available_models = []
        self._retry_count = 0
        self._pending_retry_error = None
        self._pending_retry_code = None

        # ★ MEMORY: store full conversation history
        self._history: list[dict] = []
        # Track all chat bubble widgets for theme updates
        self._chat_widgets: list = []

        self.setWindowTitle("AI Data Assistant")
        self.setMinimumSize(820, 680)
        self.resize(860, 720)
        self._build_ui()
        self._check_ollama()

    # ── UI construction ──────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self._header = QFrame()
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(20, 10, 20, 10)
        self._title = QLabel("🔬 AI Data Assistant")
        hl.addWidget(self._title)
        hl.addStretch()

        # Memory badge
        self._mem_badge = QLabel("✓ Memory ON")
        hl.addWidget(self._mem_badge)

        # Dark mode toggle
        self._theme_btn = QPushButton("🌙")
        self._theme_btn.setFixedSize(32, 32)
        self._theme_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._theme_btn.setToolTip("Toggle dark mode")
        self._theme_btn.clicked.connect(self._toggle_theme)
        hl.addWidget(self._theme_btn)

        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(190)
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        hl.addWidget(self.model_combo)

        self.status_dot = QLabel("●")
        hl.addWidget(self.status_dot)
        self.status_label = QLabel("Checking…")
        hl.addWidget(self.status_label)
        layout.addWidget(self._header)

        # Setup banner
        self._banner = QFrame()
        self._banner.setVisible(False)
        bl = QHBoxLayout(self._banner)
        bl.setContentsMargins(20, 8, 20, 8)
        self._banner_text = QLabel(
            "<b>Setup:</b> Install <a href='https://ollama.com'>Ollama</a>, "
            "then run:<br>"
            "<code>ollama serve</code> and "
            "<code>ollama pull deepseek-r1:14b</code>")
        self._banner_text.setOpenExternalLinks(True)
        self._banner_text.setWordWrap(True)
        bl.addWidget(self._banner_text)
        layout.addWidget(self._banner)

        # Context bar
        self._ctx_bar = QFrame()
        self._ctx_bar.setVisible(False)
        cbl = QHBoxLayout(self._ctx_bar)
        cbl.setContentsMargins(20, 5, 20, 5)
        self._ctx_label = QLabel("")
        cbl.addWidget(self._ctx_label)
        layout.addWidget(self._ctx_bar)

        # Suggestions
        self._sug_frame = QFrame()
        self._sug_layout = QHBoxLayout(self._sug_frame)
        self._sug_layout.setContentsMargins(20, 6, 20, 6)
        layout.addWidget(self._sug_frame)

        # Chat scroll
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_widget = QWidget()
        self.chat_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chat_widget.customContextMenuRequested.connect(self._ctx_menu)
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setContentsMargins(20, 12, 20, 12)
        self.chat_layout.setSpacing(4)
        self.chat_layout.addStretch()
        self.chat_scroll.setWidget(self.chat_widget)
        layout.addWidget(self.chat_scroll, stretch=1)

        # Thinking bar
        self._thinking = QFrame()
        self._thinking.setVisible(False)
        tl = QHBoxLayout(self._thinking)
        tl.setContentsMargins(20, 6, 20, 6)
        self._think_lbl = QLabel("Thinking…")
        tl.addWidget(self._think_lbl)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setMaximumHeight(3)
        tl.addWidget(self._progress)
        layout.addWidget(self._thinking)

        # Input row
        self._inp_frame = QFrame()
        il = QHBoxLayout(self._inp_frame)
        il.setContentsMargins(20, 10, 20, 10)
        il.setSpacing(10)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(
            "Ask about your data, request a figure, follow up on previous answers…")
        self.input_field.returnPressed.connect(self._send)
        il.addWidget(self.input_field)
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._send)
        il.addWidget(self.send_btn)
        layout.addWidget(self._inp_frame)

        # Apply initial theme
        self._apply_theme()

        self._add_ai(
            "Hello! I'm your local AI assistant for nanoparticle analysis.\n\n"
            "I **remember** everything we discuss in this session. "
            "You can ask follow-up questions, refer back to earlier results, "
            "and I'll generate matplotlib figures directly from your data.\n\n"
            "Right-click anywhere in the chat for quick figures without waiting for the AI."
        )
        self._update_suggestions(None)

    # ── Theme ────────────────────────────────────────────────

    def _toggle_theme(self):
        Theme.toggle()
        self._apply_theme()

    def _apply_theme(self):
        """Apply current theme to all widgets."""
        dark = Theme.is_dark()
        bg = Theme.c('bg')
        bg2 = Theme.c('bg_secondary')
        fg = Theme.c('text')
        fg2 = Theme.c('text_secondary')
        fg3 = Theme.c('text_tertiary')
        border = Theme.c('border')
        border_l = Theme.c('border_light')
        accent = Theme.c('accent')
        accent_h = Theme.c('accent_hover')
        surface = Theme.c('surface')
        surface_h = Theme.c('surface_hover')
        sb_bg = Theme.c('scrollbar_bg')
        sb_h = Theme.c('scrollbar_handle')

        # Base dialog
        self.setStyleSheet(
            f"QDialog {{ background: {bg}; }}"
            f"QScrollArea {{ border: none; background: {bg}; }}"
            f"QWidget#chat_widget {{ background: {bg}; }}"
            f"QScrollBar:vertical {{ "
            f"  background: {sb_bg}; width: 8px; border-radius: 4px; }}"
            f"QScrollBar::handle:vertical {{ "
            f"  background: {sb_h}; min-height: 30px; border-radius: 4px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )
        self.chat_widget.setObjectName("chat_widget")

        # Header
        self._header.setStyleSheet(
            f"QFrame {{ background: {bg2}; border-bottom: 1px solid {border}; }}")
        self._title.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {fg};")
        self._mem_badge.setStyleSheet(
            f"background: {Theme.c('badge_bg')}; color: {Theme.c('badge_text')}; "
            f"border-radius: 10px; padding: 3px 10px; font-size: 11px; font-weight: 600;")

        # Theme toggle button
        icon = "☀️" if dark else "🌙"
        self._theme_btn.setText(icon)
        self._theme_btn.setStyleSheet(
            f"QPushButton {{ background: {surface}; border: 1px solid {border}; "
            f"border-radius: 16px; font-size: 14px; }}"
            f"QPushButton:hover {{ background: {surface_h}; }}")

        # Model combo
        self.model_combo.setStyleSheet(
            f"QComboBox {{ border: 1px solid {border}; border-radius: 6px; "
            f"padding: 5px 10px; font-size: 13px; background: {surface}; color: {fg}; }}"
            f"QComboBox QAbstractItemView {{ background: {surface}; color: {fg}; "
            f"selection-background-color: {accent}; }}")

        # Status
        self.status_label.setStyleSheet(f"color: {fg2}; font-size: 12px;")

        # Banner
        self._banner.setStyleSheet(
            f"QFrame {{ background: {Theme.c('banner_bg')}; "
            f"border-bottom: 1px solid {Theme.c('banner_border')}; }}")
        self._banner_text.setStyleSheet(f"color: {Theme.c('banner_text')}; font-size: 12px;")

        # Context bar
        self._ctx_bar.setStyleSheet(
            f"QFrame {{ background: {Theme.c('ctx_bg')}; "
            f"border-bottom: 1px solid {Theme.c('ctx_border')}; }}")
        self._ctx_label.setStyleSheet(f"color: {Theme.c('ctx_text')}; font-size: 12px;")

        # Suggestions
        self._sug_frame.setStyleSheet(
            f"QFrame {{ border-bottom: 1px solid {border_l}; background: {bg}; }}")
        self._update_suggestion_styles()

        # Thinking bar
        self._thinking.setStyleSheet(
            f"QFrame {{ background: {bg2}; border-top: 1px solid {border_l}; }}")
        self._think_lbl.setStyleSheet(
            f"color: {fg2}; font-size: 13px; font-style: italic;")
        self._progress.setStyleSheet(
            f"QProgressBar {{ border: none; background: {Theme.c('progress_bg')}; border-radius: 1px; }}"
            f"QProgressBar::chunk {{ background: {Theme.c('progress_chunk')}; border-radius: 1px; }}")

        # Input row
        self._inp_frame.setStyleSheet(
            f"QFrame {{ background: {bg2}; border-top: 1px solid {border}; }}")
        self.input_field.setStyleSheet(
            f"QLineEdit {{ border: 1px solid {Theme.c('input_border')}; border-radius: 10px; "
            f"padding: 10px 16px; font-size: 14px; background: {Theme.c('input_bg')}; "
            f"color: {fg}; }}"
            f"QLineEdit:focus {{ border-color: {Theme.c('input_focus')}; }}")
        self.send_btn.setStyleSheet(
            f"QPushButton {{ background: {accent}; color: white; border: none; "
            f"border-radius: 10px; padding: 10px 20px; font-size: 14px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: {accent_h}; }}"
            f"QPushButton:disabled {{ background: {border}; color: {fg3}; }}")

        # Update all existing chat bubbles
        for w in self._chat_widgets:
            if hasattr(w, 'apply_theme'):
                w.apply_theme()

    def _update_suggestion_styles(self):
        for i in range(self._sug_layout.count()):
            w = self._sug_layout.itemAt(i).widget()
            if w and isinstance(w, QPushButton):
                w.setStyleSheet(
                    f"QPushButton {{ background: {Theme.c('sug_bg')}; "
                    f"color: {Theme.c('sug_text')}; "
                    f"border: 1px solid {Theme.c('sug_border')}; border-radius: 16px; "
                    f"padding: 5px 14px; font-size: 12px; }}"
                    f"QPushButton:hover {{ background: {Theme.c('sug_hover_bg')}; "
                    f"border-color: {Theme.c('sug_hover_border')}; "
                    f"color: {Theme.c('sug_hover_text')}; }}")

    # ── Context menu ─────────────────────────────────────────

    def _ctx_menu(self, pos):
        cfg = self.node.config
        menu = QMenu(self)

        # Style the context menu
        bg = Theme.c('surface')
        fg = Theme.c('text')
        border = Theme.c('border')
        accent = Theme.c('accent')
        menu.setStyleSheet(
            f"QMenu {{ background: {bg}; color: {fg}; border: 1px solid {border}; "
            f"border-radius: 8px; padding: 4px; }}"
            f"QMenu::item {{ padding: 6px 20px; border-radius: 4px; }}"
            f"QMenu::item:selected {{ background: {accent}; color: white; }}"
            f"QMenu::separator {{ height: 1px; background: {border}; margin: 4px 8px; }}")

        if self.available_models:
            mm = menu.addMenu("Switch Model")
            mm.setStyleSheet(menu.styleSheet())
            cur = cfg.get('model', '')
            for m in sorted(self.available_models):
                a = mm.addAction(m)
                a.setCheckable(True)
                a.setChecked(m == cur)
                a.triggered.connect(lambda _, mdl=m: self._quick_model(mdl))

        menu.addSeparator()
        dark_label = "☀️  Light Mode" if Theme.is_dark() else "🌙  Dark Mode"
        menu.addAction(dark_label).triggered.connect(self._toggle_theme)
        menu.addSeparator()
        menu.addAction("Clear Chat + Memory").triggered.connect(self._clear_chat)
        menu.addAction("Refresh Connection").triggered.connect(self._check_ollama)
        menu.addSeparator()
        menu.addAction("Settings…").triggered.connect(self._open_settings)
        menu.exec(self.chat_widget.mapToGlobal(pos))

    def _quick_model(self, model):
        self.node.config['model'] = model
        idx = self.model_combo.findData(model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

    def _open_settings(self):
        dlg = AISettingsDialog(self.node.config, self.available_models, self)
        if dlg.exec() == QDialog.Accepted:
            self.node.config.update(dlg.collect())
            self._update_model_combo()

    def _clear_chat(self):
        """Clear chat UI and reset conversation memory."""
        self._history.clear()
        self._chat_widgets.clear()
        self._retry_count = 0
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._add_ai("Chat cleared. Memory reset — starting fresh.")

    # ── Ollama ────────────────────────────────────────────────

    def _check_ollama(self):
        self._status_w = OllamaStatusWorker()
        self._status_w.status_ready.connect(self._on_status)
        self._status_w.start()

    def _on_status(self, ok, info, models):
        self.available_models = models
        if ok and models:
            self.status_dot.setStyleSheet(
                f"color: {Theme.c('success_dot')}; font-size: 10px;")
            self.status_label.setText(info)
            self.status_label.setStyleSheet(
                f"color: {Theme.c('ctx_text')}; font-size: 12px;")
            self._banner.setVisible(False)
            self._update_model_combo()
        elif ok:
            self.status_dot.setStyleSheet(
                f"color: {Theme.c('warn_dot')}; font-size: 10px;")
            self.status_label.setText(info)
            self._banner.setVisible(True)
        else:
            self.status_dot.setStyleSheet(
                f"color: {Theme.c('error_dot')}; font-size: 10px;")
            self.status_label.setText(info)
            self._banner.setVisible(True)
        self._update_suggestions(self.current_data)

    def _update_model_combo(self):
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        if self.available_models:
            for m in sorted(self.available_models):
                self.model_combo.addItem(m, m)
            target = self.node.config.get('model', '')
            idx = self.model_combo.findData(target)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            else:
                for d in PREFERRED_DEFAULTS:
                    idx = self.model_combo.findData(d)
                    if idx >= 0:
                        self.model_combo.setCurrentIndex(idx)
                        break
        else:
            self.model_combo.addItem("No models", "none")
        self.model_combo.blockSignals(False)

    def _on_model_changed(self, idx):
        m = self.model_combo.currentData()
        if m and m != "none":
            self.node.config['model'] = m

    # ── Suggestions ──────────────────────────────────────────

    def _update_suggestions(self, data):
        for i in reversed(range(self._sug_layout.count())):
            w = self._sug_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        if not self.available_models:
            return
        if data and data.get('type') == 'sample_data':
            items = ["Plot element frequencies", "Show size distribution",
                     "What are the main combinations?", "Any unusual particles?"]
        elif data and data.get('type') == 'multiple_sample_data':
            items = ["Compare samples", "Which elements differ most?",
                     "Show overlap heatmap"]
        else:
            items = ["What can you do?", "How do I get started?"]
        for s in items:
            btn = QPushButton(s)
            btn.setStyleSheet(
                f"QPushButton {{ background: {Theme.c('sug_bg')}; "
                f"color: {Theme.c('sug_text')}; "
                f"border: 1px solid {Theme.c('sug_border')}; border-radius: 16px; "
                f"padding: 5px 14px; font-size: 12px; }}"
                f"QPushButton:hover {{ background: {Theme.c('sug_hover_bg')}; "
                f"border-color: {Theme.c('sug_hover_border')}; "
                f"color: {Theme.c('sug_hover_text')}; }}")
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda _, t=s: self._send_text(t))
            self._sug_layout.addWidget(btn)

    def _send_text(self, text):
        self.input_field.setText(text)
        self._send()

    # ── Data context ─────────────────────────────────────────

    def update_data_context(self, data):
        self.current_data = data
        if data:
            summary = self.node.get_data_summary()
            self._ctx_label.setText(f"✓  {summary}")
            self._ctx_bar.setVisible(True)
            self._update_suggestions(data)
            dtype = data.get('type', '')
            if dtype == 'sample_data':
                n = len(data.get('particle_data', []))
                name = data.get('sample_name', '?')
                self._add_ai(f"**Dataset connected:** {name} — {n:,} particles.")
            elif dtype == 'multiple_sample_data':
                ns = len(data.get('sample_names', []))
                np_ = len(data.get('particle_data', []))
                self._add_ai(f"**Multi-sample:** {ns} samples, {np_:,} particles.")
        else:
            self._ctx_bar.setVisible(False)

    # ── Send / receive ────────────────────────────────────────

    def _send(self):
        text = self.input_field.text().strip()
        if not text:
            return
        if not self.available_models:
            self._banner.setVisible(True)
            return
        model = self.model_combo.currentData()
        if not model or model == "none":
            return

        self.input_field.setEnabled(False)
        self.send_btn.setEnabled(False)
        self._add_user(text)
        self.input_field.clear()

        # Append user message to history
        self._history.append({"role": "user", "content": text})
        self._retry_count = 0

        self._thinking.setVisible(True)
        self._think_lbl.setText(f"Thinking ({model})…")

        # ★ Trim history to fit context window
        num_ctx = self.node.config.get('num_ctx', 8192)
        # Reserve ~2000 tokens for system prompt + response
        max_hist_tokens = max(512, num_ctx - 2000)
        trimmed = _trim_history(list(self._history), max_hist_tokens)

        self._worker = AIGenerateWorker(
            message_history = trimmed,
            data_context    = self.current_data,
            model           = model,
            temperature     = self.node.config.get('temperature', 0.6),
            num_ctx         = num_ctx,
        )
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _on_response(self, text):
        self._thinking.setVisible(False)

        # Append assistant reply to history
        self._history.append({"role": "assistant", "content": text})

        particles = (self.current_data.get('particle_data', [])
                     if self.current_data else [])
        parts = _parse_response(text, particles, self.current_data)

        has_error = False
        error_info = None

        for part in parts:
            if part[0] == 'text':
                self._add_ai(part[1])
            elif part[0] == 'think':
                tb = ThinkBubble(part[1])
                self._chat_widgets.append(tb)
                self.chat_layout.insertWidget(self.chat_layout.count() - 1, tb)
            elif part[0] == 'figure':
                fb = FigureBubble(part[1], part[2], particles, self.current_data)
                self._chat_widgets.append(fb)
                self.chat_layout.insertWidget(self.chat_layout.count() - 1, fb)
            elif part[0] == 'error':
                has_error = True
                error_info = (part[1], part[2])
                eb = ErrorBubble(part[1], part[2])
                self._chat_widgets.append(eb)
                self.chat_layout.insertWidget(self.chat_layout.count() - 1, eb)

        self._scroll_bottom()

        # ★ AUTO-RETRY: if code failed and we haven't exceeded max retries
        if has_error and error_info and self._retry_count < MAX_CODE_RETRIES:
            self._retry_count += 1
            self._pending_retry_error = error_info[0]
            self._pending_retry_code = error_info[1]
            self._add_ai(f"*Auto-retrying… (attempt {self._retry_count}/{MAX_CODE_RETRIES})*")
            self._start_retry()
            return

        self._enable_input()

    def _start_retry(self):
        """Send the error back to the model for self-correction."""
        model = self.model_combo.currentData()
        if not model or model == "none":
            self._enable_input()
            return

        self._thinking.setVisible(True)
        self._think_lbl.setText(f"Retrying ({model})… attempt {self._retry_count}")

        num_ctx = self.node.config.get('num_ctx', 8192)
        max_hist_tokens = max(512, num_ctx - 2000)
        trimmed = _trim_history(list(self._history), max_hist_tokens)

        self._retry_worker = AIRetryWorker(
            message_history = trimmed,
            data_context    = self.current_data,
            model           = model,
            error_msg       = self._pending_retry_error,
            failed_code     = self._pending_retry_code,
            temperature     = 0.4,   # lower temp for corrections
            num_ctx         = num_ctx,
        )
        self._retry_worker.response_ready.connect(self._on_retry_response)
        self._retry_worker.error_occurred.connect(self._on_error)
        self._retry_worker.start()

    def _on_retry_response(self, text):
        """Handle the retry response — parse and display like a normal response."""
        self._thinking.setVisible(False)

        # Add retry exchange to history
        self._history.append({"role": "assistant", "content": text})

        particles = (self.current_data.get('particle_data', [])
                     if self.current_data else [])
        parts = _parse_response(text, particles, self.current_data)

        has_error = False
        error_info = None

        for part in parts:
            if part[0] == 'text':
                self._add_ai(part[1])
            elif part[0] == 'think':
                tb = ThinkBubble(part[1])
                self._chat_widgets.append(tb)
                self.chat_layout.insertWidget(self.chat_layout.count() - 1, tb)
            elif part[0] == 'figure':
                fb = FigureBubble(part[1], part[2], particles, self.current_data)
                self._chat_widgets.append(fb)
                self.chat_layout.insertWidget(self.chat_layout.count() - 1, fb)
            elif part[0] == 'error':
                has_error = True
                error_info = (part[1], part[2])
                eb = ErrorBubble(part[1], part[2])
                self._chat_widgets.append(eb)
                self.chat_layout.insertWidget(self.chat_layout.count() - 1, eb)

        self._scroll_bottom()

        # Continue retrying if still failing and under limit
        if has_error and error_info and self._retry_count < MAX_CODE_RETRIES:
            self._retry_count += 1
            self._pending_retry_error = error_info[0]
            self._pending_retry_code = error_info[1]
            self._add_ai(f"*Auto-retrying… (attempt {self._retry_count}/{MAX_CODE_RETRIES})*")
            self._start_retry()
            return

        if has_error:
            self._add_ai("*Auto-retry exhausted. You can try rephrasing your request.*")

        self._enable_input()

    def _on_error(self, err):
        self._thinking.setVisible(False)
        # Remove the last user message from history on error so it can be retried
        if self._history and self._history[-1]['role'] == 'user':
            self._history.pop()
        if err == "connection_error":
            self._add_ai("**Cannot connect to Ollama.** Run `ollama serve` first.")
            self._banner.setVisible(True)
        elif err == "timeout_error":
            self._add_ai("**Timeout** — try a smaller model or simpler question.")
        else:
            self._add_ai(f"**Error:** `{err}`")
        self._enable_input()

    def _enable_input(self):
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.input_field.setFocus()

    def _add_user(self, text):
        b = TextBubble(text, is_user=True)
        self._chat_widgets.append(b)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, b)
        self._scroll_bottom()

    def _add_ai(self, text):
        b = TextBubble(text, is_user=False)
        self._chat_widgets.append(b)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, b)
        self._scroll_bottom()

    def _scroll_bottom(self):
        QTimer.singleShot(
            50, lambda: self.chat_scroll.verticalScrollBar().setValue(
                self.chat_scroll.verticalScrollBar().maximum()))


# ═══════════════════════════════════════════════════════════════
# AI Assistant Node  (unchanged interface)
# ═══════════════════════════════════════════════════════════════

class AIAssistantNode(QObject):

    position_changed      = Signal(QPointF)
    configuration_changed = Signal()

    DEFAULT_CONFIG = {
        'model':       'deepseek-r1:14b',
        'temperature': 0.6,
        'num_ctx':     8192,
    }

    def __init__(self, parent_window=None):
        super().__init__()
        self.title          = "AI Data Assistant"
        self.node_type      = "ai_assistant"
        self.position       = QPointF(0, 0)
        self._has_input     = True
        self._has_output    = False
        self.input_channels  = ["input"]
        self.output_channels = []
        self.parent_window   = parent_window
        self.input_data      = None
        self.chat_dialog     = None
        self.config          = dict(self.DEFAULT_CONFIG)

    def set_position(self, pos):
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def process_data(self, input_data):
        self.input_data = input_data
        if self.chat_dialog and self.chat_dialog.isVisible():
            self.chat_dialog.update_data_context(input_data)
        self.configuration_changed.emit()

    def get_data_summary(self):
        d = self.input_data
        if not d:
            return "No data"
        dtype = d.get('type', '?')
        if dtype == 'sample_data':
            name = d.get('sample_name', '?')
            n    = len(d.get('particle_data', []))
            return f"{name} — {n:,} particles"
        if dtype == 'multiple_sample_data':
            ns = len(d.get('sample_names', []))
            n  = len(d.get('particle_data', []))
            return f"{ns} samples — {n:,} particles"
        return dtype

    def configure(self, parent_window):
        if not self.chat_dialog:
            self.chat_dialog = AIChatDialog(self, parent_window)
        if self.input_data:
            self.chat_dialog.update_data_context(self.input_data)
        self.chat_dialog.show()
        self.chat_dialog.raise_()
        self.chat_dialog.activateWindow()
        return True


# ── Factory helpers ─────────────────────────────────────────

def create_ai_assistant_node(parent_window):
    return AIAssistantNode(parent_window)


def show_ai_assistant_dialog(parent_window, input_data=None):
    node = AIAssistantNode(parent_window)
    if input_data:
        node.process_data(input_data)
    dlg = AIChatDialog(node, parent_window)
    dlg.exec()