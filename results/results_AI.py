from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QFrame, QTextEdit, QProgressBar, QComboBox, QScrollArea, QWidget,
    QDialogButtonBox, QFileDialog, QSizePolicy, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QApplication, QAbstractItemView, QStackedWidget, QPlainTextEdit,
    QSlider, QSpinBox,
)
from PySide6.QtCore import QObject, Signal, QPointF, QThread, QTimer, Qt
from PySide6.QtGui import QPixmap, QFont, QCursor, QColor, QKeySequence
import requests, io, re, json, time, math, threading, base64, os, uuid, ast, traceback
from collections import Counter, defaultdict
import numpy as np
from tools.theme import theme as global_theme
import logging
_itk_log = logging.getLogger("IsotopeTrack.results.results_AI")

OLLAMA_BASE = "http://localhost:11434"
OLLAMA_CHAT = f"{OLLAMA_BASE}/api/chat"
OLLAMA_TAGS = f"{OLLAMA_BASE}/api/tags"

MLX_BASE    = "http://localhost:8080"
MLX_CHAT    = f"{MLX_BASE}/v1/chat/completions"
MLX_MODELS  = f"{MLX_BASE}/v1/models"

CODE_EXEC_TIMEOUT      = 30
CHARS_PER_TOKEN        = 3.5
STREAM_RENDER_INTERVAL = 80


# ── Theme ────────────────────────────────────────────────────────────────────

class Theme:
    _dark = False
    LIGHT = {
        'bg':'#F8FAFC','bg_secondary':'#F1F5F9','bg_tertiary':'#E2E8F0',
        'surface':'#FFFFFF','surface_hover':'#F1F5F9',
        'border':'#CBD5E1','border_light':'#E2E8F0',
        'text':'#0F172A','text_secondary':'#475569','text_tertiary':'#94A3B8',
        'accent':'#3B82F6','accent_hover':'#60A5FA','accent_surface':'#EFF6FF',
        'user_bubble':'#3B82F6','user_text':'#FFFFFF',
        'ai_bubble':'#FFFFFF','ai_text':'#0F172A',
        'think_bg':'#F0FDF4','think_border':'#BBF7D0','think_text':'#166534',
        'error_bg':'#FEF2F2','error_border':'#FECACA','error_text':'#991B1B',
        'code_bg':'#0F172A','code_text':'#E2E8F0',
        'input_bg':'#FFFFFF','input_border':'#CBD5E1','input_focus':'#3B82F6',
        'scrollbar_bg':'#E2E8F0','scrollbar_handle':'#94A3B8',
        'success_dot':'#22C55E','warn_dot':'#F59E0B','error_dot':'#EF4444',
        'progress_bg':'#E2E8F0','progress_chunk':'#3B82F6',
        'sug_bg':'#F8FAFC','sug_text':'#334155','sug_border':'#CBD5E1',
        'sug_hover_bg':'#EFF6FF','sug_hover_border':'#3B82F6','sug_hover_text':'#2563EB',
        'stop_bg':'#EF4444','stop_hover':'#DC2626','speed_text':'#94A3B8',
        'output_bg':'#0F172A','output_border':'#1E293B','output_text':'#94A3B8',
    }
    DARK = {
        'bg':'#0F172A','bg_secondary':'#1E293B','bg_tertiary':'#334155',
        'surface':'#1E293B','surface_hover':'#334155',
        'border':'#334155','border_light':'#1E293B',
        'text':'#F1F5F9','text_secondary':'#94A3B8','text_tertiary':'#64748B',
        'accent':'#3B82F6','accent_hover':'#60A5FA','accent_surface':'#1E3A5F',
        'user_bubble':'#2563EB','user_text':'#FFFFFF',
        'ai_bubble':'#1E293B','ai_text':'#F1F5F9',
        'think_bg':'#052E16','think_border':'#166534','think_text':'#4ADE80',
        'error_bg':'#450A0A','error_border':'#7F1D1D','error_text':'#FCA5A5',
        'code_bg':'#020617','code_text':'#CBD5E1',
        'input_bg':'#1E293B','input_border':'#334155','input_focus':'#3B82F6',
        'scrollbar_bg':'#1E293B','scrollbar_handle':'#475569',
        'success_dot':'#22C55E','warn_dot':'#FBBF24','error_dot':'#F87171',
        'progress_bg':'#334155','progress_chunk':'#3B82F6',
        'sug_bg':'#1E293B','sug_text':'#CBD5E1','sug_border':'#334155',
        'sug_hover_bg':'#1E3A5F','sug_hover_border':'#3B82F6','sug_hover_text':'#60A5FA',
        'stop_bg':'#DC2626','stop_hover':'#B91C1C','speed_text':'#64748B',
        'output_bg':'#020617','output_border':'#1E293B','output_text':'#94A3B8',
    }
    @classmethod
    def is_dark(cls): return cls._dark
    @classmethod
    def toggle(cls): cls._dark = not cls._dark
    @classmethod
    def sync_with_global(cls): cls._dark = global_theme.is_dark
    @classmethod
    def c(cls, key): return (cls.DARK if cls._dark else cls.LIGHT).get(key, '#FF00FF')

Theme.sync_with_global()

# ── UI Preferences (font size, chart quality, etc.) ──────────────────────────

_UI_PREFS = {
    'font_size':       14,    
    'chart_dpi':       100,  
    'show_timestamps': False, 
    'bubble_max_width':740,  
}

def _fs(delta=0):
    """Return current font size + delta, as int."""
    return max(11, min(20, _UI_PREFS['font_size'] + delta))


# ── Data helpers ─────────────────────────────────────────────────────────────

def _safe_positive(v):
    try:
        v = float(v)
        # v == v is False only for NaN; np.isnan on a scalar is much slower
        # than this comparison and this runs once per particle per element.
        return v > 0 and v == v
    except Exception:
        _itk_log.exception("Handled exception in _safe_positive")
        return False

def _extract_element_values(particles, field='elements'):
    result = {}
    for p in particles:
        d = p.get(field, {})
        if not isinstance(d, dict): continue
        for el, v in d.items():
            try: v = float(v)
            except Exception:
                _itk_log.exception("Handled exception in _extract_element_values")
                continue
            if v > 0 and v == v: result.setdefault(el, []).append(v)
    return result

def _extract_element_counts(particles):
    c = {}
    for p in particles:
        for el, v in p.get('elements', {}).items():
            if _safe_positive(v): c[el] = c.get(el, 0) + 1
    return c

def _extract_element_per_ml(particles, dc):
    """Compute per-element particle concentration in particles per mL.

    Each particle's element detection is attributed to that particle's source
    sample, multiplied by the sample's dilution-over-volume factor taken from
    the node's concentration metadata. Returns an empty dict when no transport
    rate is available.

    Args:
        particles (list): Particle dictionaries.
        dc (dict): Data context carrying concentration_meta and sample keys.

    Returns:
        dict: Mapping of element label to particles-per-mL concentration.
    """
    meta = (dc or {}).get('concentration_meta', {})
    if not isinstance(meta, dict) or not meta:
        return {}

    def _factor(sample_name):
        entry = meta.get(sample_name)
        if not entry:
            return 0.0
        vol = entry.get('volume_ml', 0.0)
        if not vol or vol <= 0:
            return 0.0
        return entry.get('dilution_factor', 1.0) / vol

    default_sample = (dc or {}).get('sample_name', 'Sample')
    out = {}
    for p in particles:
        sn = p.get('source_sample', default_sample)
        f = _factor(sn)
        if f <= 0:
            continue
        for el, v in p.get('elements', {}).items():
            if _safe_positive(v):
                out[el] = out.get(el, 0.0) + f
    return out

def _extract_total_values(particles, total_key='total_element_mass_fg'):
    vals = []
    for p in particles:
        t = p.get('totals', {})
        if isinstance(t, dict) and total_key in t:
            v = t[total_key]
            if _safe_positive(v): vals.append(float(v))
    return vals

def _extract_combinations(particles):
    combos = {}
    for p in particles:
        det = sorted(el for el, v in p.get('elements', {}).items() if _safe_positive(v))
        if det: key = ' + '.join(det); combos[key] = combos.get(key, 0) + 1
    return combos

def _extract_by_sample(particles, dc):
    names = dc.get('sample_names', [])
    bs = {}
    for p in particles:
        src = p.get('source_sample', p.get('_source_sample', ''))
        if src: bs.setdefault(src, []).append(p)
    ordered = {}
    for n in names:
        if n in bs: ordered[n] = bs[n]
    for n, ps in bs.items():
        if n not in ordered: ordered[n] = ps
    return ordered

def _get_all_elements(particles):
    ec = _extract_element_counts(particles)
    return [el for el, _ in sorted(ec.items(), key=lambda x: -x[1])]


# ── System prompt ─────────────────────────────────────────────────────────────

def _build_system_prompt(dc, backend='ollama'):
    intro = """You are a scientific data analyst specialising in spICP-ToF-MS (single-particle ICP Time-of-Flight Mass Spectrometry) and nanoparticle analysis.

YOUR ROLE:
- Query the particle data, find patterns, report findings as clean tables or plain text
- Never invent interpretations or conclusions about what a particle "is" or "where it comes from"
- Only name phases or compounds (e.g. rutile, aluminosilicate) if the USER explicitly tells you to reason about that
- Report what the DATA shows — the user brings the domain knowledge

HOW TO ANSWER:
- For any analytical question, ALWAYS write Python code to compute from ALL particles
- Never estimate or guess from examples — always compute from the full dataset
- Return results as clean plain-text tables using print()
- If the user asks a simple factual question you can answer from the dataset summary below, answer directly

WHAT YOU KNOW ABOUT spICP-ToF-MS:
- Each particle event = one nanoparticle passing through the plasma torch
- Elements detected in the same event = co-located in one particle
- element_diameter_nm = equivalent sphere diameter from mass and element density
- particle_diameter_nm = same but using compound density (differs when compound ≠ pure element)
- Multi-element particles = aggregates or composite/alloy nanoparticles
- start_time / end_time = acquisition timestamp (~1 ms duration typical at ToF acquisition rates)
- mass_percentages / mole_percentages = elemental composition of that particle
- Rare element detections (n < 10) should be interpreted cautiously

DATA STRUCTURE — each particle is a Python dict:
  elements              {'56Fe': 141.3, '27Al': 62.4}        raw signal counts
  element_mass_fg       {'56Fe': 1.05, '27Al': 3.72}         mass in femtograms per element
  element_moles_fmol    {'56Fe': 0.019, '27Al': 0.138}       moles in femtomoles per element
  element_diameter_nm   {'56Fe': 63.3, '27Al': 138.1}        equivalent sphere diameter (nm)
  particle_mass_fg      {'56Fe': 1.05}                        compound-corrected mass (DICT not scalar)
  particle_diameter_nm  {'56Fe': 63.3}                        compound-corrected diameter (DICT not scalar)
  mass_percentages      {'56Fe': 6.7, '27Al': 23.0}          mass % composition
  mole_percentages      {'56Fe': 3.4, '27Al': 24.5}          mole % composition
  totals                total_element_mass_fg, total_element_moles_fmol,
                        total_particle_mass_fg, total_particle_moles_fmol
  source_sample         which sample this particle came from
  start_time / end_time float seconds

ELEMENT LABELS: format is mass_number+symbol with NO space (e.g. '56Fe', '208Pb', '27Al', '48Ti').
ALWAYS use list(element_counts.keys()) to discover which elements are present. Never assume.

CODE SANDBOX — pre-loaded variables:
  particles        all particle dicts (full dataset)
  elements         {el: [counts...]}           element_counts  {el: n_particles}
  masses           {el: [mass_fg...]}           diameters       {el: [diameter_nm...]}
  moles            {el: [moles_fmol...]}        mass_pct        {el: [mass_%...]}
  mole_pct         {el: [mole_%...]}            total_masses    [total_mass_fg per particle]
  total_moles      [total_moles_fmol per particle]
  element_per_ml   {el: particles_per_mL}  (empty if no transport rate; already dilution-corrected)
  by_sample        {sample_name: [particles]}   sample_names    [list of names]
  sample_name      current sample name (single mode)
  np, math, Counter, defaultdict, stats (scipy.stats)

  show_table(headers, rows, title="") — renders an INTERACTIVE sortable table in the UI.
    headers: list of column name strings
    rows:    list of lists (one per row), values auto-converted to string
    Use this for ANY tabular result — it gives the user sort, filter, and chart controls.

  show_chart(labels, values, kind='bar', title='', xlabel='', ylabel='') — renders a chart.
    labels: list of category/x-axis strings (same length as values)
    values: list of numeric values
    kind:   'bar' (vertical bars), 'barh' (horizontal bars), 'line', or 'scatter'
    Example: show_chart(['Fe','Al','Ti'], [45.2, 22.1, 8.7], kind='barh', title='Element %')

  show_pie(labels, values, title='') — renders a pie chart of proportions.
    labels: list of category name strings
    values: list of numeric values (normalized automatically)
    Example: show_pie(['REE','Silicate','Metal'], [18450, 8234, 3125], title='Particle groups')

  show_histogram(values, bins=30, title='', xlabel='') — renders a histogram of a numeric array.
    values: list or array of raw numeric values
    Example: show_histogram(diameters.get('56Fe',[]), bins=40, title='Fe diameter', xlabel='nm')

CODE RULES:
  - No import statements — everything is pre-loaded
  - Use show_table() for tabular results — preferred over print()
  - Use show_pie() for pie/donut charts, show_chart() for bar/line, show_histogram() for distributions
  - Use print() only for short plain-text summaries (< 5 lines)
  - NEVER write import, plt, fig, matplotlib, or seaborn — they are blocked
  - _safe(p, field, key) → True if p.get(field,{}).get(key,0) > 0  (use for filtering)

EXAMPLE — particles where both Zr and Cu are detected:
```python
hits = [p for p in particles
        if _safe(p,'element_mass_fg','90Zr') and _safe(p,'element_mass_fg','63Cu')]
rows = [[f"{p['element_diameter_nm'].get('90Zr',0):.1f}",
         f"{p['element_diameter_nm'].get('63Cu',0):.1f}",
         f"{p['element_mass_fg'].get('90Zr',0):.3f}",
         f"{p['element_mass_fg'].get('63Cu',0):.3f}",
         p.get('source_sample','')] for p in hits]
show_table(['Zr diam (nm)','Cu diam (nm)','Zr mass (fg)','Cu mass (fg)','Sample'],
           rows, title=f"Zr + Cu co-detected — {len(hits)} particles")
```

EXAMPLE — element frequency and size table:
```python
rows = []
for el, n in sorted(element_counts.items(), key=lambda x: -x[1]):
    d = diameters.get(el, []); m = masses.get(el, [])
    rows.append([el, f"{n:,}", f"{n/len(particles)*100:.1f}%",
                 f"{np.mean(d):.1f}" if d else "—",
                 f"{np.median(d):.1f}" if d else "—",
                 f"{np.percentile(d,95):.1f}" if d else "—",
                 f"{np.mean(m):.3f}" if m else "—"])
show_table(['Element','N','% total','Diam mean','Diam median','Diam p95','Mass mean (fg)'],
           rows, title="Element frequency and size statistics")
```"""

    base = intro

    if not dc: return base + "\n\nSTATUS: No data loaded yet."
    particles = dc.get('particle_data', [])
    n = len(particles)
    if n == 0: return base + "\n\nSTATUS: 0 particles."

    ec = _extract_element_counts(particles)
    combos = _extract_combinations(particles)
    top_e = sorted(ec.items(), key=lambda x: -x[1])
    top_c = sorted(combos.items(), key=lambda x: -x[1])
    single = sum(1 for p in particles
                 if sum(1 for v in p.get('elements', {}).values() if _safe_positive(v)) == 1)

    diam_vals = _extract_element_values(particles, 'element_diameter_nm')
    mass_vals  = _extract_element_values(particles, 'element_mass_fg')

    def _st(arr):
        a = np.array(arr)
        return np.mean(a), np.std(a), np.percentile(a, 5), np.median(a), np.percentile(a, 95)

    durations_ms = []
    for p in particles:
        try:
            d = (float(p['end_time']) - float(p['start_time'])) * 1000
            if d > 0: durations_ms.append(d)
        except Exception:
            _itk_log.exception("Handled exception in _build_system_prompt")

    total_masses = _extract_total_values(particles, 'total_element_mass_fg')

    ctx = "\n\n━━━ DATASET SUMMARY ━━━\n"
    dt = dc.get('type', '')
    if dt == 'sample_data':
        ctx += f"Sample: {dc.get('sample_name','?')}\n"
        tp = dc.get('total_particles', n)
        fp = dc.get('filtered_particles', n)
        ctx += f"Particles: {fp:,}" + (f" (filtered from {tp:,})" if tp != fp else "") + "\n"
    elif dt == 'multiple_sample_data':
        names = dc.get('sample_names', [])
        ctx += f"Samples ({len(names)}): {', '.join(str(x) for x in names)}\n"
        ctx += f"Total particles: {n:,}\n"

    ctx += (f"Single-element: {single:,} ({single/n*100:.1f}%)   "
            f"Multi-element: {n-single:,} ({(n-single)/n*100:.1f}%)\n"
            f"Unique elements: {len(ec)}\n")

    if durations_ms:
        dm, _, dp5, _, dp95 = _st(durations_ms)
        ctx += f"Particle duration: mean={dm:.3f} ms  p5={dp5:.3f}  p95={dp95:.3f} ms\n"

    if total_masses:
        tm, ts, tp5, tmed, tp95 = _st(total_masses)
        ctx += f"Total particle mass: mean={tm:.2f}  median={tmed:.2f}  p5={tp5:.2f}  p95={tp95:.2f} fg\n"

    ctx += "\n── ELEMENT FREQUENCIES ──\n"
    ctx += f"  {'Element':<12} {'N':>8} {'%':>7}  {'diam mean':>10} {'diam p5':>9} {'diam p95':>9}  {'mass mean':>10} {'mass p95':>9}\n"
    for el, cnt in top_e:
        d = diam_vals.get(el, [])
        m = mass_vals.get(el, [])
        dm  = f"{np.mean(d):.1f}"  if d else "—"
        dp5 = f"{np.percentile(d,5):.1f}" if d else "—"
        dp95= f"{np.percentile(d,95):.1f}" if d else "—"
        mm  = f"{np.mean(m):.3f}" if m else "—"
        mp95= f"{np.percentile(m,95):.3f}" if m else "—"
        ctx += f"  {el:<12} {cnt:>8,} {cnt/n*100:>6.1f}%  {dm:>10} {dp5:>9} {dp95:>9}  {mm:>10} {mp95:>9}\n"

    ctx += "\n── TOP COMBINATIONS ──\n"
    for combo, cnt in top_c[:12]:
        ctx += f"  {cnt:6,} ({cnt/n*100:.1f}%)  {combo}\n"

    # ── Data availability (so the model knows what it may report) ──
    has_conc = bool((dc or {}).get('concentration_meta'))
    ctx += "\n── DATA AVAILABILITY ──\n"
    if has_conc:
        ctx += "  Concentrations: AVAILABLE — element_per_ml is valid (particles/mL).\n"
    else:
        ctx += ("  Concentrations: NOT AVAILABLE — element_per_ml is empty; "
                "do not report per-mL concentrations.\n")

    # ── Known spectral interferences, sourced from the validated database ──
    # Grounds caveats in IsotopeTrack's own reference data rather than the model's
    # training. Only flags masses with major/critical documented interferences.
    try:
        from widget.interference_database import (
            get_interferences_for_mass, get_worst_severity)
        notes = []
        for el, _cnt in top_e:
            mm = re.match(r'(\d+)', str(el))
            if not mm:
                continue
            ints = get_interferences_for_mass(int(mm.group(1)))
            if not ints:
                continue
            sev = get_worst_severity(ints)
            if sev in ('critical', 'major'):
                species = ', '.join(str(i.get('species', '?')) for i in ints[:3])
                notes.append(f"  {el:<8} {sev:<9} possible: {species}")
        if notes:
            ctx += ("\n── KNOWN SPECTRAL INTERFERENCES ──\n"
                    "  Documented for these masses — caveat any finding that hinges on them.\n"
                    + "\n".join(notes[:15]) + "\n")
    except Exception:
        _itk_log.exception("Handled exception building interference notes")

    ctx += "\n── 3 REPRESENTATIVE PARTICLES ──\n"
    for label, idx in [('first', 0), ('middle', n//2), ('last', n-1)]:
        p = particles[idx]
        compact = {
            'start_time': round(float(p.get('start_time', 0)), 6),
            'end_time':   round(float(p.get('end_time', 0)), 6),
            'elements':          {k: round(v,2) for k,v in p.get('elements',{}).items() if _safe_positive(v)},
            'element_mass_fg':   {k: round(v,4) for k,v in p.get('element_mass_fg',{}).items() if _safe_positive(v)},
            'element_diameter_nm':{k:round(v,2) for k,v in p.get('element_diameter_nm',{}).items() if _safe_positive(v)},
            'mass_percentages':  {k: round(v,2) for k,v in p.get('mass_percentages',{}).items() if _safe_positive(v)},
            'totals':            {k: round(v,4) for k,v in p.get('totals',{}).items() if _safe_positive(v)},
            'source_sample':     p.get('source_sample', p.get('_source_sample', '')),
        }
        ctx += f"\n[{label} — index {idx}]\n{json.dumps(compact, indent=2, default=str)}\n"

    return base + ctx


def _build_exploration_prompt(dc, max_turns=10):
    """System prompt for the agentic exploration mode. The model writes one
    Python query per turn; we execute it and feed results back so it can
    decide what to investigate next."""

    base = _build_system_prompt(dc, backend='ollama')

    extension = f"""

━━━ EXPLORATION MODE — READ CAREFULLY ━━━

You are now in AGENTIC EXPLORATION MODE. Instead of answering in one shot,
you will run a multi-turn investigation. You have UP TO {max_turns} TURNS.

GOAL — Find anomalies, outliers, and unusual patterns that a simple summary
would miss. Treat this as a real scientific data-exploration session.

PROTOCOL
- Each turn: write ONE focused Python code block, nothing else.
- I will execute it and return the printed output + table contents.
- Based on what you find, decide what to investigate next turn.
- DO NOT try to do everything in one turn. Be iterative and curious.
- Each query should be FOCUSED (one specific question, < 40 lines of code).

WHAT TO LOOK FOR (suggested investigation priorities)
1. SAMPLE-LEVEL DIFFERENCES — when multiple samples exist, compare element
   abundance, size distributions, and unique element combos across samples.
   Look for samples that stand out.
2. OUTLIERS — particles with mass / diameter / element count far beyond p99.
3. RARE BUT REAL — element combinations that appear only a few times. Are
   they noise or a meaningful subpopulation?
4. UNEXPECTED CO-OCCURRENCE — elements that always (or never) appear together.
5. TIME CLUSTERS — burst patterns in start_time that suggest contamination
   events or instrument artifacts.
6. SIZE / MASS INCONSISTENCY — particles where element_diameter and
   particle_diameter disagree strongly.
7. DETECTION LIMITS — elements with very low counts (n<10) might be noise;
   call this out if you see suspect detections.

OUTPUT FORMAT FOR EACH EXPLORATION TURN
Write a short rationale (1-2 lines), then ONE code block. Example:

  Checking whether sample 2 has unusually many Fe+Cu particles compared to others.
  ```python
  bs = by_sample
  rows = []
  for name, ps in bs.items():
      n_fecu = sum(1 for p in ps if _safe(p,'element_mass_fg','56Fe') and _safe(p,'element_mass_fg','63Cu'))
      rows.append([name, len(ps), n_fecu, f"{{n_fecu/max(len(ps),1)*100:.1f}}%"])
  show_table(['Sample','N total','N Fe+Cu','% Fe+Cu'], rows, title='Fe+Cu rate by sample')
  ```

FINISHING
- When you have enough findings (or by turn {max_turns} at the latest), write
  `EXPLORATION DONE` on its own line at the START of a new response and STOP
  producing any further code. After `EXPLORATION DONE`, I will ask you for a
  final summary.

REMEMBER
- All sandbox functions are pre-loaded (np, math, Counter, _safe, particles,
  by_sample, element_counts, masses, diameters, etc.).
- Never use import statements.
- Use show_table for tabular results — keep tables under 50 rows where possible.
- Use print() for short text findings.
"""
    return base + extension


def _format_exploration_feedback(text_out, tables, charts, err, turn, max_turns):
    """Format the result of executing an exploration turn's code as a user
    message that goes back into the model's context. Keeps things compact
    (large tables get truncated) so the context window doesn't explode."""

    parts = [f"[TURN {turn} RESULT — {max_turns - turn} turns remaining]\n"]

    if err:
        parts.append(f"⚠ ERROR while executing your code:\n{err}\n")
        parts.append("Either fix the error in the next turn, or move on to a different query.")
        return ''.join(parts)

    if text_out:
        if len(text_out) > 3000:
            text_out = text_out[:3000] + "\n... [output truncated]"
        parts.append("STDOUT:\n" + text_out + "\n")

    for i, tbl in enumerate(tables):
        title   = tbl.get('title', f'Table {i+1}')
        headers = tbl.get('headers', [])
        rows    = tbl.get('rows', [])
        parts.append(f"\nTABLE — {title}  ({len(rows)} rows)")
        parts.append("  " + " | ".join(headers))
        for r in rows[:30]:
            parts.append("  " + " | ".join(str(v) for v in r))
        if len(rows) > 30:
            parts.append(f"  ... [{len(rows) - 30} more rows omitted]")

    if charts:
        kinds = ', '.join(c.get('type','?') for c in charts)
        parts.append(f"\n[CHARTS RENDERED: {kinds} — visible to the user, "
                     f"summarize the takeaway in your next turn]")

    if not text_out and not tables and not charts:
        parts.append("(Code ran but produced no output. Your next query should "
                     "print() or show_table() so you can see results.)")

    parts.append(
        f"\n\nWhat's your next focused query? Or write `EXPLORATION DONE` "
        f"if you have enough findings.")
    return '\n'.join(parts)


# ── Markdown renderer ─────────────────────────────────────────────────────────

def _md_to_html(text):
    lines = text.split('\n'); html = []; in_code = False; in_list = False; buf = []
    cbg = Theme.c('code_bg'); cfg = Theme.c('code_text')
    ac = Theme.c('accent'); ibg = Theme.c('bg_tertiary')
    for line in lines:
        if line.strip().startswith('```') and not in_code:
            if in_list: html.append('</ul>'); in_list = False
            in_code = True; buf = []; continue
        if line.strip().startswith('```') and in_code:
            in_code = False
            html.append(f'<div style="background:{cbg};color:{cfg};padding:10px 14px;border-radius:8px;'
                        f'font-family:monospace;font-size:12px;margin:6px 0;white-space:pre;">'
                        f'{"<br>".join(buf)}</div>')
            continue
        if in_code: buf.append(line.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')); continue
        s = line.strip()
        if s.startswith('### '): html.append(f'<div style="font-size:14px;font-weight:700;margin:10px 0 4px;color:{ac};">{_ifmt(s[4:],ibg)}</div>'); continue
        if s.startswith('## '): html.append(f'<div style="font-size:15px;font-weight:700;margin:12px 0 4px;">{_ifmt(s[3:],ibg)}</div>'); continue
        if s.startswith('# '): html.append(f'<div style="font-size:16px;font-weight:700;margin:14px 0 6px;">{_ifmt(s[2:],ibg)}</div>'); continue
        if s.startswith('- ') or s.startswith('* '):
            if not in_list: html.append('<ul style="margin:4px 0 4px 18px;padding:0;">'); in_list = True
            html.append(f'<li style="margin:2px 0;">{_ifmt(s[2:],ibg)}</li>'); continue
        if in_list: html.append('</ul>'); in_list = False
        if not s: html.append('<div style="height:6px;"></div>'); continue
        html.append(f'<div style="margin:2px 0;">{_ifmt(s,ibg)}</div>')
    if in_list: html.append('</ul>')
    return ''.join(html)

def _ifmt(t, ibg='#F3F4F6'):
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'\*(.+?)\*',     r'<i>\1</i>', t)
    t = re.sub(r'`(.+?)`',
               rf'<code style="background:{ibg};padding:1px 5px;border-radius:3px;'
               rf'font-family:monospace;font-size:12px;">\1</code>', t)
    return t

def _trim_history(h, max_t):
    if not h: return h
    total = 0; cut = len(h)
    for i in range(len(h)-1, -1, -1):
        total += max(1, int(len(h[i].get('content',''))/CHARS_PER_TOKEN))
        if total > max_t: cut = i+1; break
    else: cut = 0
    return h[min(cut, max(0, len(h)-2)):]


# ── Code execution (stdout capture) ──────────────────────────────────────────

_SAFE_BUILTINS = {
    'abs':abs,'all':all,'any':any,'bool':bool,'dict':dict,'enumerate':enumerate,
    'filter':filter,'float':float,'format':format,'int':int,'isinstance':isinstance,
    'len':len,'list':list,'map':map,'max':max,'min':min,'print':print,'range':range,
    'round':round,'set':set,'sorted':sorted,'str':str,'sum':sum,'tuple':tuple,
    'type':type,'zip':zip,'True':True,'False':False,'None':None,
    'ValueError':ValueError,'TypeError':TypeError,'KeyError':KeyError,'Exception':Exception,
}
_CODE_RE   = re.compile(r'```python\s*\n(.*?)```', re.DOTALL)
_THINK_RE  = re.compile(r'<think>.*?</think>', re.DOTALL)
_IMPORT_RE = re.compile(r'^\s*(?:import\s+\w+|from\s+\w+\s+import\s+.+)\s*$', re.MULTILINE)

def _sanitize_code(code):
    code = _IMPORT_RE.sub('', code)
    code = re.sub(r'^\s*plt\.show\(\)\s*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^\s*plt\.savefig\(.*?\)\s*$', '', code, flags=re.MULTILINE)
    return code.strip()


# ── AST safety screen ─────────────────────────────────────────────────────────
# The exec namespace already removes dangerous builtins (no open/eval/exec/
# __import__). This AST pass closes the two remaining gaps we cannot cover with a
# builtins whitelist alone: (1) the classic introspection escape via dunder
# attribute walking — ().__class__.__bases__[0].__subclasses__() — and (2)
# numpy's own filesystem helpers (np.save/np.load/...), since np is pre-injected.
# It is a *safety* screen for locally-generated code, not a hard security
# boundary; full process isolation (resource limits / hard kill) is a separate,
# larger change documented for follow-up.
_BLOCKED_CALL_NAMES = frozenset({
    'open', 'eval', 'exec', 'compile', '__import__', 'input',
    'getattr', 'setattr', 'delattr', 'globals', 'locals', 'vars', 'memoryview',
})
_BLOCKED_ATTRS = frozenset({
    # numpy / generic filesystem + serialization escape hatches
    'save', 'savez', 'savez_compressed', 'load', 'loadtxt', 'savetxt',
    'genfromtxt', 'fromfile', 'tofile', 'memmap', 'fromregex', 'DataSource',
    'system', 'popen', 'remove', 'unlink', 'rename', 'rmdir', 'makedirs',
})

def _screen_code(code):
    """Static-analyse generated code. Returns an error string if it contains a
    disallowed construct, else None. Runs before exec()."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e.msg} (line {e.lineno})"
    for node in ast.walk(tree):
        # Block dunder attribute access (escape via __class__/__subclasses__/...)
        if isinstance(node, ast.Attribute) and isinstance(node.attr, str):
            if node.attr.startswith('__') and node.attr.endswith('__'):
                return ("Blocked: dunder attribute access "
                        f"('{node.attr}') is not allowed in the sandbox.")
            if node.attr in _BLOCKED_ATTRS:
                return (f"Blocked: '{node.attr}(...)' is not allowed "
                        "(filesystem/serialization access is disabled).")
        # Block dunder name references and known dangerous builtins
        if isinstance(node, ast.Name) and isinstance(node.id, str):
            if node.id.startswith('__') and node.id.endswith('__'):
                return f"Blocked: '{node.id}' is not allowed in the sandbox."
            if node.id in _BLOCKED_CALL_NAMES:
                return (f"Blocked: '{node.id}(...)' is not allowed in the sandbox.")
    return None


# ── Number provenance (no-fabrication guardrail) ──────────────────────────────
# The model computes numbers via code (good) but can still restate wrong figures
# in prose. These helpers collect every number the sandbox actually produced and
# flag specific decimal figures in prose that are not backed by that output.
_FLOAT_TOKEN_RE   = re.compile(r'[-+]?\d[\d,]*\.\d+')
_ANYNUM_TOKEN_RE  = re.compile(r'[-+]?\d[\d,]*\.\d+|[-+]?\d[\d,]*')

def _to_float(tok):
    try:
        return float(str(tok).replace(',', ''))
    except (ValueError, TypeError):
        return None

def _floats_in_text(s):
    """All numeric values (int or float) appearing in a string."""
    out = []
    for tok in _ANYNUM_TOKEN_RE.findall(str(s)):
        v = _to_float(tok)
        if v is not None:
            out.append(v)
    return out

def _numbers_in_rows(rows, cap=8000):
    out = []
    for row in rows:
        for cell in row:
            out.extend(_floats_in_text(cell))
            if len(out) >= cap:
                return out
    return out

def _close(a, b, rel=0.005):
    return abs(a - b) <= max(1e-9, rel * max(abs(a), abs(b)))

def _unverified_numbers(prose, allowed):
    """Decimal figures in prose with no match (within tolerance) in the set of
    numbers the code produced. Only decimals are flagged, to avoid noise from
    counts, percentages-as-integers, indices, etc."""
    allowed = list(allowed)
    bad, seen = [], set()
    for tok in _FLOAT_TOKEN_RE.findall(str(prose)):
        if tok in seen:
            continue
        seen.add(tok)
        v = _to_float(tok)
        if v is None:
            continue
        if not any(_close(v, a) for a in allowed):
            bad.append(tok)
    return bad


def _compact_table(tbl, max_rows=15):
    """Short plain-text rendering of a result table for the interpretation pass."""
    headers = tbl.get('headers', [])
    rows = tbl.get('rows', [])
    lines = [f"TABLE: {tbl.get('title', '')}", " | ".join(str(h) for h in headers)]
    for r in rows[:max_rows]:
        lines.append(" | ".join(str(c) for c in r))
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows) - max_rows} more rows)")
    return "\n".join(lines)


def _correction_hint(err, import_error=False):
    """Build the self-correction message fed back to the model after a sandbox
    error, so it can fix and retry (generalises the old import-only hint)."""
    hint = (
        "[SANDBOX CORRECTION] Your code raised an error when it ran:\n"
        f"{err}\n\n"
        "Rewrite the code to fix it. Reminders:\n"
        "- No import statements — np, math, Counter, defaultdict, stats are pre-loaded.\n"
        "- Discover elements with list(element_counts.keys()); never assume a label exists.\n"
        "- Use .get(...) for dict access and check keys before indexing.\n"
        "- Produce output via show_table / show_chart / show_pie / show_histogram or print().\n"
        "- Do not use file access, dunder attributes, or imports."
    )
    if import_error:
        hint += "\n- Imports are blocked; remove every import line."
    return hint


_MAX_STDOUT_CHARS = 20000

def _format_exec_error(exc, code):
    """Error string with the offending line from the generated code, so both the
    user and the self-correction retry can see exactly what failed."""
    msg = f"{type(exc).__name__}: {exc}"
    try:
        tb = traceback.extract_tb(exc.__traceback__)
        lineno = next((fr.lineno for fr in reversed(tb)
                       if fr.filename == '<string>'), None)
        src = code.split('\n')
        if lineno and 1 <= lineno <= len(src):
            msg += f"\n  → line {lineno}: {src[lineno - 1].strip()}"
    except Exception:
        _itk_log.exception("Handled exception in _format_exec_error")
    return msg

def _execute_query_code(code, particles, dc):
    """Run code in sandbox. Returns (text_output, table_list, chart_list, error).
    table_list = [{'title':str, 'headers':[str], 'rows':[[str]]}]
    chart_list = [{'type':str, 'labels':[str], 'values':[float], 'title':str, ...}]
    """
    from contextlib import redirect_stdout
    code = _sanitize_code(code)
    screen_err = _screen_code(code)
    if screen_err:
        return None, [], [], screen_err
    bs = _extract_by_sample(particles, dc) if dc else {}

    def _safe(p, field, key): return p.get(field, {}).get(key, 0) > 0

    _tables = []
    _charts = []

    def show_table(headers, rows, title="Query result"):
        """Display data as an interactive sortable table."""
        _tables.append({
            'title':   str(title),
            'headers': [str(h) for h in headers],
            'rows':    [[str(v) for v in row] for row in rows],
        })

    def show_chart(labels, values, kind='bar', title='', xlabel='', ylabel=''):
        """Render a bar, horizontal-bar, line, or scatter chart."""
        try:
            vals = [float(v) for v in values]
        except Exception as e:
            raise ValueError(f"show_chart: values must be numeric — {e}")
        _charts.append({
            'type':   str(kind),
            'labels': [str(l) for l in labels],
            'values': vals,
            'title':  str(title),
            'xlabel': str(xlabel),
            'ylabel': str(ylabel),
        })

    def show_pie(labels, values, title=''):
        """Render a pie chart of proportions."""
        try:
            vals = [float(v) for v in values]
        except Exception as e:
            raise ValueError(f"show_pie: values must be numeric — {e}")
        _charts.append({
            'type':   'pie',
            'labels': [str(l) for l in labels],
            'values': vals,
            'title':  str(title),
            'xlabel': '', 'ylabel': '',
        })

    def show_histogram(values, bins=30, title='', xlabel=''):
        """Render a histogram of raw numeric values."""
        try:
            vals = [float(v) for v in values]
        except Exception as e:
            raise ValueError(f"show_histogram: values must be numeric — {e}")
        _charts.append({
            'type':   'histogram',
            'labels': [],
            'values': vals,
            'bins':   int(bins),
            'title':  str(title),
            'xlabel': str(xlabel),
            'ylabel': 'Count',
        })

    ns = {
        '__builtins__': _SAFE_BUILTINS,
        'np': np, 'math': math, 'Counter': Counter, 'defaultdict': defaultdict,
        '_safe': _safe,
        'show_table': show_table, 'show_chart': show_chart,
        'show_pie': show_pie, 'show_histogram': show_histogram,
        'particles':      particles,
        'elements':       _extract_element_values(particles, 'elements'),
        'element_counts': _extract_element_counts(particles),
        'element_per_ml': _extract_element_per_ml(particles, dc),
        'masses':         _extract_element_values(particles, 'element_mass_fg'),
        'diameters':      _extract_element_values(particles, 'element_diameter_nm'),
        'moles':          _extract_element_values(particles, 'element_moles_fmol'),
        'mass_pct':       _extract_element_values(particles, 'mass_percentages'),
        'mole_pct':       _extract_element_values(particles, 'mole_percentages'),
        'total_masses':   _extract_total_values(particles, 'total_element_mass_fg'),
        'total_moles':    _extract_total_values(particles, 'total_element_moles_fmol'),
        'sample_names':   dc.get('sample_names', []) if dc else [],
        'sample_name':    dc.get('sample_name', 'Sample') if dc else 'Sample',
        'by_sample': bs, 'data_context': dc or {},
    }
    try:
        from scipy import stats; ns['stats'] = stats
    except Exception:
        _itk_log.exception("Handled exception in _execute_query_code")

    out = io.StringIO(); err = [None]
    def _run():
        try:
            with redirect_stdout(out): exec(code, ns)
        except Exception as e:
            _itk_log.exception("Handled exception in _run")
            err[0] = _format_exec_error(e, code)

    t = threading.Thread(target=_run, daemon=True)
    t.start(); t.join(timeout=CODE_EXEC_TIMEOUT)
    if t.is_alive():
        return None, [], [], (
            f"Code execution timed out after {CODE_EXEC_TIMEOUT}s — "
            "simplify the query or process fewer particles at once.")
    if err[0]: return None, _tables, _charts, err[0]
    text = out.getvalue().strip()
    if len(text) > _MAX_STDOUT_CHARS:
        text = text[:_MAX_STDOUT_CHARS] + "\n... [output truncated]"
    return (text if text else None), _tables, _charts, None


# ── File attachment helpers ───────────────────────────────────────────────────

IMAGE_EXTS = {'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg',
              '.bmp':'image/bmp','.tiff':'image/tiff','.webp':'image/webp'}
TEXT_EXTS  = {'.txt','csv','.json','.md','.tsv','.xml'}

def _read_image_b64(path):
    ext = os.path.splitext(path)[1].lower()
    mime = IMAGE_EXTS.get(ext, 'image/png')
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode()
    return data, mime

def _extract_pdf_text(path):
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        text = '\n'.join(pg.extract_text() or '' for pg in reader.pages)
        return text.strip() or None
    except ImportError:
        _itk_log.debug("Handled exception in _extract_pdf_text")
        return "__MISSING_PYPDF__"
    except Exception as e:
        _itk_log.exception("Handled exception in _extract_pdf_text")
        return None

def _read_text_file(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    if len(content) > 60000:
        content = content[:60000] + "\n\n[... file truncated at 60,000 chars ...]"
    return content


def _try_parse_table(text):
    """Try to parse printed text as a table. Returns (headers, rows) or None."""
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 2: return None
    sep_idx = None
    for i, l in enumerate(lines):
        if re.match(r'^[\s\-=|]+$', l) and len(l.strip()) > 4:
            sep_idx = i; break
    header_idx = (sep_idx - 1) if sep_idx and sep_idx > 0 else 0
    data_start  = (sep_idx + 1) if sep_idx is not None else 1
    header_line = lines[header_idx]
    data_lines  = lines[data_start:]
    if not data_lines: return None
    def _split(line):
        return [c.strip() for c in re.split(r'  +|\t', line.strip()) if c.strip()]
    headers = _split(header_line)
    if len(headers) < 2: return None
    rows = []
    for l in data_lines:
        if re.match(r'^[\s\-=|]+$', l): continue
        row = _split(l)
        if len(row) >= 2: rows.append(row)
    if not rows: return None
    nc = len(headers)
    rows = [(r + [''] * nc)[:nc] for r in rows]
    return headers, rows




class StreamWorker(QThread):
    token_received  = Signal(str)
    stream_done     = Signal(str)
    error_occurred  = Signal(str)
    stats_update    = Signal(int, float)

    def __init__(self, backend, msgs, sys_prompt, config, attachments=None):
        super().__init__()
        self.backend     = backend
        self.msgs        = msgs
        self.sys         = sys_prompt
        self.cfg         = config
        self.attachments = attachments or []
        self._cancelled  = threading.Event()
        self._resp       = None

    def stop(self):
        self._cancelled.set()
        if self._resp:
            try: self._resp.close()
            except Exception:
                _itk_log.exception("Handled exception in stop")

    def run(self):
        if   self.backend == 'mlx':    self._run_mlx()
        elif self.backend == 'custom': self._run_custom_api()
        else:                          self._run_ollama()

    # ── Build messages with optional image attachments ──────────────────────

    def _inject_attachments(self, messages):
        """Inject pending file/image attachments into the last user message."""
        if not self.attachments: return messages
        msgs = list(messages)
        for i in range(len(msgs)-1, -1, -1):
            if msgs[i].get('role') == 'user':
                original = msgs[i].get('content', '')
                images  = [a for a in self.attachments if a['type'] == 'image']
                texts   = [a for a in self.attachments if a['type'] == 'text']
                prefix = ''
                for a in texts:
                    prefix += f"\n[Attached file: {a['name']}]\n{a['content']}\n\n"
                if prefix:
                    msgs[i] = dict(msgs[i]); msgs[i]['content'] = prefix + original

                if images:
                    msgs[i] = dict(msgs[i])
                    msgs[i]['images'] = [a['data'] for a in images]
                break
        return msgs

    def _inject_attachments_openai(self, messages):
        """OpenAI-style multipart content for MLX vision."""
        if not self.attachments: return messages
        msgs = list(messages)
        for i in range(len(msgs)-1, -1, -1):
            if msgs[i].get('role') == 'user':
                images = [a for a in self.attachments if a['type'] == 'image']
                texts  = [a for a in self.attachments if a['type'] == 'text']
                original = msgs[i].get('content', '')
                prefix = ''.join(f"\n[Attached: {a['name']}]\n{a['content']}\n\n" for a in texts)
                content = [{"type": "text", "text": prefix + original}]
                for a in images:
                    content.append({"type": "image_url",
                                    "image_url": {"url": f"data:{a['mime']};base64,{a['data']}"}})
                msgs[i] = dict(msgs[i]); msgs[i]['content'] = content
                break
        return msgs

    # ── Ollama ───────────────────────────────────────────────────────────────

    def _run_ollama(self):
        try:
            base_msgs = [{"role": "system", "content": self.sys}] + self.msgs
            messages  = self._inject_attachments(base_msgs)
            self._resp = requests.post(OLLAMA_CHAT, json={
                "model":   self.cfg.get('model', ''),
                "messages": messages,
                "stream":  True,
                "options": {
                    "temperature": self.cfg.get('temperature', 0.2),
                    "num_ctx":     self.cfg.get('num_ctx', 8192),
                    "num_predict": 4096,
                },
            }, timeout=300, stream=True)
            if self._resp.status_code != 200:
                self.error_occurred.emit(f"Ollama HTTP {self._resp.status_code}"); return
            self._stream_ndjson()
        except requests.exceptions.ConnectionError:
            _itk_log.exception("Handled exception in _run_ollama")
            if not self._cancelled.is_set():
                self.error_occurred.emit("Cannot connect to Ollama. Run: ollama serve")
        except Exception as e:
            _itk_log.exception("Handled exception in _run_ollama")
            if not self._cancelled.is_set(): self.error_occurred.emit(str(e))

    def _stream_ndjson(self):
        full = []; tc = 0; t0 = time.monotonic()
        for line in self._resp.iter_lines(decode_unicode=True):
            if self._cancelled.is_set(): break
            if not line: continue
            try: chunk = json.loads(line)
            except Exception:
                _itk_log.exception("Handled exception in _stream_ndjson")
                continue
            content = chunk.get('message', {}).get('content', '')
            if content: full.append(content); tc += 1; self.token_received.emit(content)
            if tc % 10 == 0: self.stats_update.emit(tc, time.monotonic()-t0)
            if chunk.get('done', False): break
        self._finish(full, tc, t0)

    # ── MLX (OpenAI-compatible) ──────────────────────────────────────────────

    def _run_mlx(self):
        try:
            host = self.cfg.get('mlx_host', MLX_BASE).rstrip('/')
            base_msgs = [{"role": "system", "content": self.sys}] + self.msgs
            messages  = self._inject_attachments_openai(base_msgs)
            self._resp = requests.post(f"{host}/v1/chat/completions", json={
                "messages":    messages,
                "stream":      True,
                "temperature": self.cfg.get('temperature', 0.2),
                "max_tokens":  4096,
            }, timeout=300, stream=True)
            if self._resp.status_code != 200:
                self.error_occurred.emit(f"MLX HTTP {self._resp.status_code}"); return
            self._stream_sse()
        except requests.exceptions.ConnectionError:
            _itk_log.exception("Handled exception in _run_mlx")
            if not self._cancelled.is_set():
                self.error_occurred.emit(
                    "Cannot connect to MLX server.\n"
                    "Start it with:  mlx_lm.server --model <model-path> --port 8080")
        except Exception as e:
            _itk_log.exception("Handled exception in _run_mlx")
            if not self._cancelled.is_set(): self.error_occurred.emit(str(e))

    def _stream_sse(self):
        full = []; tc = 0; t0 = time.monotonic()
        for line in self._resp.iter_lines(decode_unicode=True):
            if self._cancelled.is_set(): break
            if not line or not line.startswith('data: '): continue
            ds = line[6:]
            if ds.strip() == '[DONE]': break
            try: ev = json.loads(ds)
            except Exception:
                _itk_log.exception("Handled exception in _stream_sse")
                continue
            content = ev.get('choices', [{}])[0].get('delta', {}).get('content', '')
            if content: full.append(content); tc += 1; self.token_received.emit(content)
            if tc % 10 == 0: self.stats_update.emit(tc, time.monotonic()-t0)
        self._finish(full, tc, t0)

    # ── Custom OpenAI-compatible API ─────────────────────────────────────────

    def _run_custom_api(self):
        try:
            base = self.cfg.get('custom_base_url', '').rstrip('/')
            key  = self.cfg.get('custom_api_key', '')
            model= self.cfg.get('custom_model', '')
            if not base:
                self.error_occurred.emit("No base URL configured for Custom API."); return
            hdrs = {'Content-Type': 'application/json'}
            if key: hdrs['Authorization'] = f'Bearer {key}'
            base_msgs = [{"role":"system","content":self.sys}] + self.msgs
            messages  = self._inject_attachments_openai(base_msgs)
            self._resp = requests.post(
                f"{base}/chat/completions",
                headers=hdrs,
                json={"model":model,"messages":messages,"stream":True,
                      "temperature":self.cfg.get('temperature',0.2),"max_tokens":4096},
                timeout=300, stream=True)
            if self._resp.status_code != 200:
                try: detail = self._resp.json().get('error',{}).get('message','')
                except Exception:
                    _itk_log.exception("Handled exception in _run_custom_api")
                    detail = ''
                self.error_occurred.emit(f"API HTTP {self._resp.status_code}: {detail}"); return
            self._stream_sse()
        except requests.exceptions.ConnectionError:
            _itk_log.exception("Handled exception in _run_custom_api")
            if not self._cancelled.is_set():
                self.error_occurred.emit(f"Cannot connect to {self.cfg.get('custom_base_url','API')}")
        except Exception as e:
            _itk_log.exception("Handled exception in _run_custom_api")
            if not self._cancelled.is_set(): self.error_occurred.emit(str(e))

    def _finish(self, full, tc, t0):
        complete = ''.join(full).strip()
        if self._cancelled.is_set():
            self.stream_done.emit((complete+"\n\n*[Stopped]*") if complete else "*[Cancelled]*")
        elif complete:
            self.stats_update.emit(tc, time.monotonic()-t0)
            self.stream_done.emit(complete)
        else:
            self.error_occurred.emit("Empty response.")


# ── Auto-detect probe ─────────────────────────────────────────────────────────

class ProbeWorker(QThread):
    """Briefly probe localhost for a running model server so the assistant can
    self-configure on first open — no need to visit settings. Ollama is checked
    first, then MLX. Emits at most one signal."""
    ready = Signal(str, str, str)     # backend, model, human-readable label
    info  = Signal(str)               # non-fatal hint (e.g. server up, no models)

    def __init__(self, mlx_host=MLX_BASE):
        super().__init__()
        self._mlx_host = (mlx_host or MLX_BASE).rstrip('/')

    def run(self):
        ollama_up_empty = False
        try:
            r = requests.get(OLLAMA_TAGS, timeout=1.5)
            if r.status_code == 200:
                models = sorted(m.get('name', '')
                                for m in r.json().get('models', []) if m.get('name'))
                if models:
                    self.ready.emit('ollama', models[0], f"Ollama · {models[0]}")
                    return
                ollama_up_empty = True
        except Exception:
            pass    # server not running — expected, keep probing
        try:
            r = requests.get(f"{self._mlx_host}/v1/models", timeout=1.5)
            if r.status_code == 200:
                ids = [m.get('id', '') for m in r.json().get('data', []) if m.get('id')]
                model = ids[0] if ids else ''
                label = (model.split('/')[-1] if model else 'loaded model')
                self.ready.emit('mlx', model, f"MLX · {label}")
                return
        except Exception:
            pass
        if ollama_up_empty:
            self.info.emit("Ollama is running but has no models — run: ollama pull llama3.1")


# ── Backend settings dialog ───────────────────────────────────────────────────

class BackendDialog(QDialog):
    def __init__(self, current_cfg, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Backend Settings"); self.setMinimumWidth(520)
        self._cfg = dict(current_cfg)
        lo = QVBoxLayout(self); lo.setSpacing(12)

        hl = QHBoxLayout(); hl.addWidget(QLabel("Backend:"))
        self._backend = QComboBox()
        self._backend.addItems(["Ollama (local)", "MLX (local)", "Custom API"])
        if current_cfg.get('backend') == 'mlx': self._backend.setCurrentIndex(1)
        elif current_cfg.get('backend') == 'custom': self._backend.setCurrentIndex(2)
        self._backend.currentIndexChanged.connect(self._on_backend)
        hl.addWidget(self._backend, stretch=1); lo.addLayout(hl)

        # ── Ollama frame ─────────────────────────────────────────────────────
        self._ollama_frame = QFrame()
        of = QVBoxLayout(self._ollama_frame); of.setContentsMargins(0,0,0,0); of.setSpacing(8)
        mh = QHBoxLayout()
        mh.addWidget(QLabel("Model:"))
        self._model = QComboBox(); self._model.setEditable(True); self._model.setMinimumWidth(260)
        cur = current_cfg.get('model', '')
        if cur: self._model.addItem(cur); self._model.setCurrentText(cur)
        mh.addWidget(self._model, stretch=1)
        rb = QPushButton("↻"); rb.setFixedWidth(32); rb.setToolTip("Refresh model list")
        rb.clicked.connect(self._fetch_ollama_models); mh.addWidget(rb)
        of.addLayout(mh)
        self._ollama_status = QLabel(""); of.addWidget(self._ollama_status)
        lo.addWidget(self._ollama_frame)

        # ── MLX frame ────────────────────────────────────────────────────────
        self._mlx_frame = QFrame()
        mf = QVBoxLayout(self._mlx_frame); mf.setContentsMargins(0,0,0,0); mf.setSpacing(8)
        info = QLabel("Start the server before connecting:\n"
                       "  mlx_lm.server --model <model-path> --port 8080")
        info.setWordWrap(True); mf.addWidget(info)
        ph = QHBoxLayout(); ph.addWidget(QLabel("Host:"))
        self._mlx_host = QLineEdit()
        self._mlx_host.setText(current_cfg.get('mlx_host', 'http://localhost:8080'))
        ph.addWidget(self._mlx_host, stretch=1); mf.addLayout(ph)
        mtb = QPushButton("Test connection"); mtb.clicked.connect(self._test_mlx); mf.addWidget(mtb)
        self._mlx_status = QLabel(""); mf.addWidget(self._mlx_status)
        lo.addWidget(self._mlx_frame)

        # ── Custom API frame ──────────────────────────────────────────────────
        self._custom_frame = QFrame()
        xf = QVBoxLayout(self._custom_frame); xf.setContentsMargins(0,0,0,0); xf.setSpacing(8)
        xf.addWidget(QLabel("OpenAI-compatible endpoint (Groq, OpenRouter, LM Studio, …)"))
        ph = QHBoxLayout(); ph.addWidget(QLabel("Base URL:"))
        self._custom_url = QLineEdit()
        self._custom_url.setText(current_cfg.get('custom_base_url','https://api.groq.com/openai/v1'))
        self._custom_url.setPlaceholderText("https://api.groq.com/openai/v1")
        ph.addWidget(self._custom_url, stretch=1); xf.addLayout(ph)
        kh = QHBoxLayout(); kh.addWidget(QLabel("API Key:"))
        self._custom_key = QLineEdit()
        self._custom_key.setEchoMode(QLineEdit.Password)
        self._custom_key.setText(current_cfg.get('custom_api_key',''))
        self._custom_key.setPlaceholderText("sk-...")
        kh.addWidget(self._custom_key, stretch=1); xf.addLayout(kh)
        mh2 = QHBoxLayout(); mh2.addWidget(QLabel("Model:"))
        self._custom_model = QLineEdit()
        self._custom_model.setText(current_cfg.get('custom_model',''))
        self._custom_model.setPlaceholderText("e.g. llama-3.3-70b-versatile")
        mh2.addWidget(self._custom_model, stretch=1); xf.addLayout(mh2)
        xtb = QPushButton("Test connection"); xtb.clicked.connect(self._test_custom); xf.addWidget(xtb)
        self._custom_status = QLabel(""); xf.addWidget(self._custom_status)
        lo.addWidget(self._custom_frame)

        cl = QHBoxLayout(); cl.addWidget(QLabel("Context window (tokens):"))
        self._ctx = QComboBox()
        self._ctx.addItems(['4096','8192','16384','32768','65536'])
        self._ctx.setCurrentText(str(current_cfg.get('num_ctx', 8192)))
        cl.addWidget(self._ctx); cl.addStretch(); lo.addLayout(cl)

        el = QHBoxLayout()
        el.addWidget(QLabel("Exploration depth (turns):"))
        self._explore_turns = QComboBox()
        self._explore_turns.addItems(['5','10','15','20','30'])
        self._explore_turns.setToolTip(
            "How many query→result cycles the model runs when you click Explore.\n"
            "More turns = deeper analysis but slower.")
        self._explore_turns.setCurrentText(str(current_cfg.get('explore_max_turns', 10)))
        el.addWidget(self._explore_turns); el.addStretch(); lo.addLayout(el)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        lo.addWidget(btns)

        self._on_backend(self._backend.currentIndex())
        QTimer.singleShot(80, self._fetch_ollama_models)

    def _on_backend(self, idx):
        self._ollama_frame.setVisible(idx == 0)
        self._mlx_frame.setVisible(idx == 1)
        self._custom_frame.setVisible(idx == 2)

    def _fetch_ollama_models(self):
        if self._backend.currentIndex() != 0: return
        self._ollama_status.setText("Fetching installed models…")
        try:
            r = requests.get(OLLAMA_TAGS, timeout=5)
            if r.status_code == 200:
                models = sorted(m.get('name', '') for m in r.json().get('models', []))
                if models:
                    cur = self._model.currentText()
                    self._model.clear(); self._model.addItems(models)
                    if cur in models: self._model.setCurrentText(cur)
                    else: self._model.setCurrentIndex(0)
                    self._ollama_status.setText(f"✓ {len(models)} model(s) installed")
                else:
                    self._ollama_status.setText("⚠ No models found — run: ollama pull <model>")
            else:
                self._ollama_status.setText(f"✗ Ollama returned HTTP {r.status_code}")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _itk_log.info("Ollama not reachable at %s — server not running.", OLLAMA_TAGS)
            self._ollama_status.setText("✗ Cannot reach Ollama — run: ollama serve")
        except Exception:
            _itk_log.exception("Unexpected error fetching Ollama models")
            self._ollama_status.setText("✗ Cannot reach Ollama — run: ollama serve")

    def _test_mlx(self):
        host = self._mlx_host.text().strip().rstrip('/')
        self._mlx_status.setText("Testing…")
        try:
            r = requests.get(f"{host}/v1/models", timeout=5)
            if r.status_code == 200:
                models = [m.get('id','') for m in r.json().get('data', [])]
                self._mlx_status.setText(f"✓ Connected  —  {', '.join(models[:3]) or 'no models listed'}")
            else:
                self._mlx_status.setText(f"✗ HTTP {r.status_code}")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _itk_log.info("MLX not reachable at %s — server not running.", host)
            self._mlx_status.setText("✗ Cannot reach MLX — start: mlx_lm.server --port 8080")
        except Exception as e:
            _itk_log.exception("Unexpected error testing MLX")
            self._mlx_status.setText(f"✗ {e}")

    def _test_custom(self):
        base = self._custom_url.text().strip().rstrip('/')
        key  = self._custom_key.text().strip()
        self._custom_status.setText("Testing…")
        try:
            hdrs = {'Content-Type':'application/json'}
            if key: hdrs['Authorization'] = f'Bearer {key}'
            r = requests.get(f"{base}/models", headers=hdrs, timeout=6)
            if r.status_code == 200:
                try:
                    models = [m.get('id','') for m in r.json().get('data',[])]
                    self._custom_status.setText(f"✓ Connected — {len(models)} models")
                    if models and not self._custom_model.text():
                        self._custom_model.setText(models[0])
                except Exception:
                    _itk_log.exception("Handled exception in _test_custom")
                    self._custom_status.setText("✓ Connected")
            elif r.status_code in (401, 403):
                self._custom_status.setText("✗ Auth failed — check API key")
            else:
                self._custom_status.setText(f"✗ HTTP {r.status_code}")
        except requests.exceptions.ConnectionError:
            _itk_log.exception("Handled exception in _test_custom")
            self._custom_status.setText("✗ Cannot connect — check URL")
        except Exception as e:
            _itk_log.exception("Handled exception in _test_custom")
            self._custom_status.setText(f"✗ {str(e)[:60]}")

    def get_config(self):
        idx = self._backend.currentIndex()
        base = {
            'temperature': 0.2,
            'num_ctx': int(self._ctx.currentText()),
            'explore_max_turns': int(self._explore_turns.currentText()),
            'mlx_host': self._mlx_host.text().strip(),
            'custom_base_url': self._custom_url.text().strip() if idx == 2 else '',
            'custom_api_key':  self._custom_key.text().strip() if idx == 2 else '',
            'custom_model':    self._custom_model.text().strip() if idx == 2 else '',
        }
        if idx == 0:
            base.update({'backend':'ollama','model':self._model.currentText()})
        elif idx == 1:
            base.update({'backend':'mlx','model':''})
        else:
            base.update({'backend':'custom','model':self._custom_model.text().strip()})
        return base


# ── Chat bubbles ──────────────────────────────────────────────────────────────

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
        fs = _fs(); fs2 = _fs(-2)
        if Theme.is_dark():
            bg, bd, fg, fg2 = '#1C2E4A', '#2D4A6E', '#CBD5E1', '#64748B'
        else:
            bg, bd, fg, fg2 = '#EFF6FF', '#BFDBFE', '#1E3A5F', '#4B6282'
        self._card.setStyleSheet(
            f"QFrame{{background:{bg};border:1px solid {bd};"
            f"border-radius:14px;border-bottom-right-radius:4px;}}")
        self._name_lbl.setStyleSheet(
            f"color:{fg};font-size:{fs}px;font-weight:600;"
            f"background:transparent;border:none;")
        self._info_lbl.setStyleSheet(
            f"color:{fg2};font-size:{fs2}px;"
            f"background:transparent;border:none;")


    def __init__(self, text, is_user=False):
        import time as _time
        super().__init__()
        self._text = text; self._iu = is_user
        self._ts = _time.strftime("%H:%M")
        self.setContentsMargins(0, 2, 0, 2)

        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        row  = QHBoxLayout(); row.setContentsMargins(0,0,0,0); row.setSpacing(6)

        self._b = QFrame()
        bl = QVBoxLayout(self._b); bl.setSpacing(4)

        if is_user:
            self._b.setMaximumWidth(_UI_PREFS['bubble_max_width'])
            bl.setContentsMargins(16, 10, 16, 10)
        else:
            self._b.setMaximumWidth(16_777_215)
            bl.setContentsMargins(0, 4, 8, 4)

        # ── Content label ─────────────────────────────────────────────────
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

        # ── Footer: timestamp + copy (AI only) ────────────────────────────
        if not is_user:
            footer = QHBoxLayout(); footer.setContentsMargins(0,3,0,0); footer.setSpacing(6)
            self._ts_lbl = QLabel(self._ts)
            self._ts_lbl.setVisible(_UI_PREFS['show_timestamps'])
            footer.addWidget(self._ts_lbl)
            footer.addStretch()
            self._copy_btn = QPushButton("⎘ Copy")
            self._copy_btn.setFixedHeight(20)
            self._copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
            self._copy_btn.clicked.connect(self._copy_text)
            footer.addWidget(self._copy_btn)
            bl.addLayout(footer)
        else:
            self._ts_lbl = None; self._copy_btn = None

        if is_user:
            row.addStretch()
            row.addWidget(self._b)
        else:
            row.addWidget(self._b)
            row.addStretch()

        root.addLayout(row)
        self.apply_theme()

    def _copy_text(self):
        plain = re.sub(r'<[^>]+>', '', self._text)
        QApplication.clipboard().setText(plain.strip())
        if self._copy_btn:
            self._copy_btn.setText("✓ Copied")
            QTimer.singleShot(1500, lambda: self._copy_btn.setText("⎘ Copy")
                              if self._copy_btn else None)

    def apply_theme(self):
        fs = _fs(); fs2 = _fs(-2)
        if self._iu:
            self._b.setStyleSheet(
                f"QFrame{{background:{Theme.c('user_bubble')};"
                f"border-radius:18px;border-bottom-right-radius:4px;}}")
            self._l.setStyleSheet(
                f"color:{Theme.c('user_text')};font-size:{fs}px;line-height:1.5;")
            self._l.setText(self._text)
        else:
            self._b.setStyleSheet("QFrame{background:transparent;border:none;}")
            self._l.setStyleSheet(
                f"color:{Theme.c('text')};font-size:{fs}px;line-height:1.65;")
            self._l.setText(_md_to_html(self._text))
            if self._ts_lbl:
                self._ts_lbl.setStyleSheet(
                    f"color:{Theme.c('text_tertiary')};font-size:{fs2}px;")
                self._ts_lbl.setVisible(_UI_PREFS['show_timestamps'])
            if self._copy_btn:
                self._copy_btn.setStyleSheet(
                    f"QPushButton{{background:transparent;border:none;"
                    f"color:{Theme.c('text_tertiary')};font-size:{fs2}px;padding:0 2px;}}"
                    f"QPushButton:hover{{color:{Theme.c('accent')};}}")


class AttachmentPreview(QFrame):
    """
    with an image thumbnail (or file icon), filename, and a remove (×) button
    overlaid on the top-right corner.
    """
    removed = Signal(object)  
    _ICONS  = {'image':'🖼','pdf':'📄','text':'📝','csv':'📊','json':'{}','default':'📎'}

    def __init__(self, name, kind, image_b64=None):
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
        super().resizeEvent(event)
        if hasattr(self, '_x'):
            self._x.move(self.width() - self._x.width() - 4, 4)

    def apply_theme(self):
        fs = _fs(-2)
        if Theme.is_dark():
            bg, bd, fg = '#243449', '#34506E', '#CBD5E1'
            x_bg, x_fg, x_hover_bg, x_hover_fg = '#334155', '#E2E8F0', '#DC2626', '#FFFFFF'
        else:
            bg, bd, fg = '#F1F5F9', '#CBD5E1', '#334155'
            x_bg, x_fg, x_hover_bg, x_hover_fg = '#FFFFFF', '#475569', '#EF4444', '#FFFFFF'
        self.setStyleSheet(
            f"AttachmentPreview{{background:{bg};border:1px solid {bd};border-radius:10px;}}")
        self._lbl.setStyleSheet(
            f"color:{fg};font-size:{fs}px;font-weight:500;background:transparent;border:none;")
        self._x.setStyleSheet(
            f"QPushButton{{background:{x_bg};color:{x_fg};border:1px solid {bd};"
            f"border-radius:11px;font-size:12px;font-weight:700;padding:0;}}"
            f"QPushButton:hover{{background:{x_hover_bg};color:{x_hover_fg};"
            f"border-color:{x_hover_bg};}}")


class TextBubble(QFrame):
    def __init__(self, text, is_user=False):
        import time as _time
        super().__init__()
        self._text = text; self._iu = is_user
        self._ts = _time.strftime("%H:%M")
        self.setContentsMargins(0, 2, 0, 2)

        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        row  = QHBoxLayout(); row.setContentsMargins(0,0,0,0); row.setSpacing(6)

        self._b = QFrame()
        bl = QVBoxLayout(self._b); bl.setSpacing(4)

        if is_user:
            self._b.setMaximumWidth(_UI_PREFS['bubble_max_width'])
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
            self._ts_lbl.setVisible(_UI_PREFS['show_timestamps'])
            footer.addWidget(self._ts_lbl)
            footer.addStretch()
            self._copy_btn = QPushButton("\u2398 Copy")
            self._copy_btn.setFixedHeight(20)
            self._copy_btn.setCursor(QCursor(Qt.PointingHandCursor))
            self._copy_btn.clicked.connect(self._copy_text)
            footer.addWidget(self._copy_btn)
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
        plain = re.sub(r'<[^>]+>', '', self._text)
        QApplication.clipboard().setText(plain.strip())
        if self._copy_btn:
            self._copy_btn.setText("\u2713 Copied")
            QTimer.singleShot(1500, lambda: self._copy_btn.setText("\u2398 Copy")
                              if self._copy_btn else None)

    def apply_theme(self):
        fs = _fs(); fs2 = _fs(-2)
        if self._iu:
            self._b.setStyleSheet(
                f"QFrame{{background:{Theme.c('user_bubble')};"
                f"border-radius:18px;border-bottom-right-radius:4px;}}")
            self._l.setStyleSheet(
                f"color:{Theme.c('user_text')};font-size:{fs}px;line-height:1.5;")
            self._l.setText(self._text)
        else:
            self._b.setStyleSheet("QFrame{background:transparent;border:none;}")
            self._l.setStyleSheet(
                f"color:{Theme.c('text')};font-size:{fs}px;line-height:1.65;")
            self._l.setText(_md_to_html(self._text))
            if self._ts_lbl:
                self._ts_lbl.setStyleSheet(
                    f"color:{Theme.c('text_tertiary')};font-size:{fs2}px;")
                self._ts_lbl.setVisible(_UI_PREFS['show_timestamps'])
            if self._copy_btn:
                self._copy_btn.setStyleSheet(
                    f"QPushButton{{background:transparent;border:none;"
                    f"color:{Theme.c('text_tertiary')};font-size:{fs2}px;padding:0 2px;}}"
                    f"QPushButton:hover{{color:{Theme.c('accent')};}}")


class StreamBubble(QFrame):
    def __init__(self):
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
        self._pend.append(tok)
        if not self._t.isActive(): self._t.start()

    def _flush(self):
        if not self._pend: self._t.stop(); return
        self._raw += ''.join(self._pend); self._pend.clear()
        d = _THINK_RE.sub('', self._raw).strip()
        self._l.setText(_md_to_html(d) + f'<span style="color:{Theme.c("accent")};">▊</span>')

    def finalise(self):
        self._t.stop()
        if self._pend: self._raw += ''.join(self._pend); self._pend.clear()
        d = _THINK_RE.sub('', self._raw).strip()
        d = _CODE_RE.sub('', d)
        self._l.setText(_md_to_html(d.strip()))

    def get_text(self): return self._raw

    def apply_theme(self):
        fs = _fs()
        self._b.setStyleSheet("QFrame{background:transparent;border:none;}")
        self._l.setStyleSheet(
            f"color:{Theme.c('text')};font-size:{fs}px;line-height:1.65;")


class ExplorationBubble(QFrame):
    """Collapsible bubble showing an exploration session.

    Layout:
      ┌─────────────────────────────────────────┐
      │ Exploring: <question>                │
      │ Turn 3 of 10 — running query…           │
      │ [▶ Show 3 steps]                         │
      │                                          │
      │   ── steps area (hidden by default) ──   │
      │   Turn 1: <code>                         │
      │     stdout / table / chart               │
      │   Turn 2: <code>                         │
      │     ...                                  │
      │                                          │
      │ ── Findings ──                           │
      │ <final summary text>                     │
      └─────────────────────────────────────────┘
    """

    def __init__(self, question):
        super().__init__()
        self._question = question
        self._turns_data = []  
        self._step_widgets = [] 
        self._summary_text = ""
        self._expanded = False
        self._completed = False

        self.setContentsMargins(0, 4, 0, 4)
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # ── Header card ─────────────────────────────────────────────────
        self._card = QFrame()
        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(14, 12, 14, 12); cl.setSpacing(8)

        title_row = QHBoxLayout(); title_row.setSpacing(8)
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
        self._prog_bar.setRange(0, 0); self._prog_bar.setMaximumHeight(3)
        self._prog_bar.setTextVisible(False)
        cl.addWidget(self._prog_bar)

        self._toggle_btn = QPushButton("▶  Show 0 steps")
        self._toggle_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._toggle_btn.clicked.connect(self._toggle_expand)
        self._toggle_btn.setVisible(False)   
        cl.addWidget(self._toggle_btn, alignment=Qt.AlignLeft)

        self._steps_frame = QFrame()
        self._steps_lo = QVBoxLayout(self._steps_frame)
        self._steps_lo.setContentsMargins(0, 4, 0, 4); self._steps_lo.setSpacing(6)
        self._steps_frame.setVisible(False)
        cl.addWidget(self._steps_frame)

        self._summary_sep = QFrame()
        self._summary_sep.setFrameShape(QFrame.HLine)
        self._summary_sep.setVisible(False)
        cl.addWidget(self._summary_sep)

        self._summary_hdr = QLabel("Findings")
        self._summary_hdr.setVisible(False)
        cl.addWidget(self._summary_hdr)

        self._summary_lbl = QLabel("")
        self._summary_lbl.setWordWrap(True)
        self._summary_lbl.setTextFormat(Qt.RichText)
        self._summary_lbl.setTextInteractionFlags(
            Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self._summary_lbl.setVisible(False)
        cl.addWidget(self._summary_lbl)

        root.addWidget(self._card)
        self.apply_theme()

    # ── Updates from the controller ───────────────────────────────────────

    def set_progress(self, turn, max_turns, text=""):
        self._badge.setText(f"Turn {turn} / {max_turns}")
        if text:
            self._prog_lbl.setText(text)

    def add_step(self, turn_num, ai_rationale, code, text_out, tables, charts, error):
        """Add a step to the exploration record. Each step gets a compact
        widget shown inside the steps container."""
        self._turns_data.append({
            'turn': turn_num, 'rationale': ai_rationale, 'code': code,
            'text': text_out, 'tables': tables, 'charts': charts, 'error': error,
        })
        step_widget = self._build_step_widget(
            turn_num, ai_rationale, code, text_out, tables, charts, error)
        self._steps_lo.addWidget(step_widget)
        self._step_widgets.append(step_widget)
        n = len(self._turns_data)
        self._toggle_btn.setText(
            f"{'▼' if self._expanded else '▶'}  "
            f"{'Hide' if self._expanded else 'Show'} {n} step{'s' if n != 1 else ''}")
        self._toggle_btn.setVisible(True)

    def set_summary(self, summary_md):
        """Mark exploration complete and display the final summary."""
        self._completed = True
        self._summary_text = summary_md or "(no summary provided)"
        self._prog_lbl.setText(f"✓ Exploration complete — {len(self._turns_data)} turns")
        self._prog_bar.setVisible(False)
        self._summary_sep.setVisible(True)
        self._summary_hdr.setVisible(True)
        self._summary_lbl.setVisible(True)
        self._summary_lbl.setText(_md_to_html(self._summary_text))
        self.apply_theme()

    def mark_cancelled(self, reason="stopped by user"):
        """Exploration was interrupted before finishing."""
        self._completed = True
        self._prog_lbl.setText(f"⏹ Exploration cancelled — {reason}")
        self._prog_bar.setVisible(False)
        if self._turns_data:
            partial = ("Exploration was stopped before a final summary was produced. "
                       f"You can review the {len(self._turns_data)} step"
                       f"{'s' if len(self._turns_data)!=1 else ''} above.")
            self._summary_sep.setVisible(True)
            self._summary_hdr.setText("Cancelled")
            self._summary_hdr.setVisible(True)
            self._summary_lbl.setText(_md_to_html(partial))
            self._summary_lbl.setVisible(True)
        self.apply_theme()

    # ── Internal ──────────────────────────────────────────────────────────

    def _toggle_expand(self):
        self._expanded = not self._expanded
        self._steps_frame.setVisible(self._expanded)
        n = len(self._turns_data)
        self._toggle_btn.setText(
            f"{'▼' if self._expanded else '▶'}  "
            f"{'Hide' if self._expanded else 'Show'} {n} step{'s' if n != 1 else ''}")

    def _build_step_widget(self, turn_num, rationale, code, text_out, tables, charts, error):
        """Build the compact display for one exploration step."""
        f = QFrame()
        lo = QVBoxLayout(f); lo.setContentsMargins(10, 8, 10, 8); lo.setSpacing(4)

        hdr = QLabel(f"<b>Turn {turn_num}</b>")
        hdr.setTextFormat(Qt.RichText)
        lo.addWidget(hdr)

        if rationale and rationale.strip():
            r = QLabel(rationale.strip())
            r.setWordWrap(True)
            r.setStyleSheet(f"color:{Theme.c('text_secondary')};font-size:{_fs(-1)}px;"
                            f"font-style:italic;background:transparent;border:none;")
            lo.addWidget(r)

        if code:
            code_lbl = QLabel(code)
            code_lbl.setWordWrap(False)
            code_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            code_lbl.setStyleSheet(
                f"background:{Theme.c('code_bg')};color:{Theme.c('code_text')};"
                f"padding:8px 10px;border-radius:6px;font-family:monospace;"
                f"font-size:{_fs(-2)}px;")
            lo.addWidget(code_lbl)

        if error:
            err_lbl = QLabel(f"⚠ {error}")
            err_lbl.setWordWrap(True)
            err_lbl.setStyleSheet(
                f"background:{Theme.c('error_bg')};color:{Theme.c('error_text')};"
                f"padding:6px 8px;border-radius:4px;font-size:{_fs(-2)}px;"
                f"border:1px solid {Theme.c('error_border')};")
            lo.addWidget(err_lbl)

        if text_out:
            shown = text_out if len(text_out) <= 800 else text_out[:800] + "\n... [truncated in step view]"
            out_lbl = QLabel(shown)
            out_lbl.setWordWrap(False)
            out_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            out_lbl.setStyleSheet(
                f"background:{Theme.c('output_bg')};color:{Theme.c('output_text')};"
                f"padding:8px 10px;border-radius:6px;font-family:monospace;"
                f"font-size:{_fs(-2)}px;white-space:pre;")
            lo.addWidget(out_lbl)

        for tbl in tables:
            try:
                t = InteractiveTableBubble(tbl['headers'], tbl['rows'], tbl.get('title',''))
                lo.addWidget(t)
            except Exception:
                _itk_log.exception("Handled exception in _build_step_widget")

        for ch in charts:
            try:
                lo.addWidget(ChartBubble(ch))
            except Exception:
                _itk_log.exception("Handled exception in _build_step_widget")

        f.setStyleSheet(
            f"QFrame{{background:{Theme.c('bg_secondary')};"
            f"border:1px solid {Theme.c('border_light')};border-radius:8px;}}"
            + " ".join([
                f"QLabel{{background:transparent;border:none;"
                f"color:{Theme.c('text')};}}"
            ]))
        return f

    def apply_theme(self):
        fs = _fs(); fs2 = _fs(-1); fs3 = _fs(1)
        ac  = Theme.c('accent');         fg  = Theme.c('text')
        fg2 = Theme.c('text_secondary'); bd  = Theme.c('border')
        bg  = Theme.c('accent_surface')

        self._card.setStyleSheet(
            f"QFrame{{background:{bg};border:1px solid {ac};"
            f"border-left:4px solid {ac};border-radius:10px;}}")
        self._title_lbl.setStyleSheet(
            f"color:{ac};font-size:{fs3}px;font-weight:700;"
            f"background:transparent;border:none;")
        self._badge.setStyleSheet(
            f"color:{ac};font-size:{fs2}px;font-weight:600;"
            f"background:transparent;border:none;")
        self._q_lbl.setStyleSheet(
            f"color:{fg};font-size:{fs}px;font-style:italic;"
            f"background:transparent;border:none;")
        self._prog_lbl.setStyleSheet(
            f"color:{fg2};font-size:{fs2}px;background:transparent;border:none;")
        self._toggle_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{ac};border:none;"
            f"font-size:{fs2}px;font-weight:600;padding:2px 0;text-align:left;}}"
            f"QPushButton:hover{{color:{Theme.c('accent_hover')};}}")
        self._summary_sep.setStyleSheet(
            f"QFrame{{border:none;border-top:1px solid {bd};background:transparent;}}")
        self._summary_hdr.setStyleSheet(
            f"color:{ac};font-size:{fs2}px;font-weight:700;text-transform:uppercase;"
            f"letter-spacing:0.6px;background:transparent;border:none;")
        self._summary_lbl.setStyleSheet(
            f"color:{fg};font-size:{fs}px;line-height:1.6;"
            f"background:transparent;border:none;")
        self._steps_frame.setStyleSheet("QFrame{background:transparent;border:none;}")


class _NumericItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically when possible."""
    def __lt__(self, other):
        def _num(s):
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

    def __init__(self, headers, rows, title="Query result"):
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

        self._stats_frame = QFrame(); self._stats_frame.setVisible(False)
        sl = QHBoxLayout(self._stats_frame); sl.setContentsMargins(8,4,8,4); sl.setSpacing(8)
        sl.addWidget(QLabel("Column:"))
        self._stats_col = QComboBox()
        self._numeric_cols = []
        for i, h in enumerate(headers):
            vals = [r[i] for r in rows if i < len(r) and r[i]]
            sample = vals[:10]
            # A column is numeric only if every sampled value parses as a number.
            # Text columns (e.g. element labels like '27Al') are normal, not errors.
            if sample and all(_to_float(str(v).replace('%', '')) is not None
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

        self._stack = QStackedWidget(); root.addWidget(self._stack, stretch=1)

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
        self._table.setMinimumHeight(min(len(rows) * 28 + 40, 400))
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

        self._populate(rows)
        self._refresh_stats()
        self.apply_theme()

    # ── Data operations ───────────────────────────────────────────────────

    def _populate(self, rows):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(rows))
        fs = _fs(-2)
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = _NumericItem(str(val))
                item.setFont(QFont("", fs))
                self._table.setItem(r, c, item)
        self._table.setSortingEnabled(True)
        self._badge.setText(f"{len(rows)} rows")
        self._filter_lbl.setText(f"{len(rows)} shown")

    def _apply_filter(self, text):
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

    # ── Stats ─────────────────────────────────────────────────────────────

    def _toggle_stats(self, checked):
        self._stats_frame.setVisible(checked)
        if checked: self._refresh_stats()

    def _refresh_stats(self):
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

    # ── Chart ─────────────────────────────────────────────────────────────

    def _switch(self, idx):
        self._stack.setCurrentIndex(idx)
        self._tab_btn.setChecked(idx == 0)
        self._chart_btn.setChecked(idx == 1)
        if idx == 1: self._draw_chart()
        self.apply_theme()

    def _set_chart_kind(self, kind):
        self._chart_kind = kind
        for b, k in self._type_btns:
            b.setChecked(k == kind)
        self._draw_chart()

    def _draw_chart(self):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        if not self._numeric_cols: return
        ci = self._col_combo.currentIndex()
        if ci < 0 or ci >= len(self._numeric_cols): return
        col_idx, col_name = self._numeric_cols[ci]
        is_dark = Theme.is_dark()
        bg = "#0F172A" if is_dark else "#F8FAFC"
        fg = "#F1F5F9" if is_dark else "#0F172A"
        gc = "#334155" if is_dark else "#E2E8F0"
        dpi = _UI_PREFS["chart_dpi"]
        fs  = _fs(-4)

        labels, values = [], []
        for r in self._all_rows[:25]:
            try:
                v = float(str(r[col_idx]).replace(",","").replace("%",""))
                labels.append(str(r[0])); values.append(v)
            except Exception:
                _itk_log.exception("Handled exception in _draw_chart")
        if not values: return

        kind = self._chart_kind
        cols = (self._COLORS * 4)[:len(labels)]

        if kind == "pie":
            fig, ax = plt.subplots(figsize=(5, 4.5), dpi=dpi)
            fig.patch.set_facecolor(bg); ax.set_facecolor(bg)
            wedges, texts, autos = ax.pie(values, labels=labels, autopct="%1.1f%%",
                                          colors=cols, startangle=90,
                                          textprops={"color": fg, "fontsize": fs})
            for at in autos: at.set_color(fg); at.set_fontsize(fs - 1)
            ax.set_title(col_name, color=fg, fontsize=fs + 1)
        elif kind == "barh":
            lbl_r, val_r = labels[::-1], values[::-1]
            fig, ax = plt.subplots(figsize=(5.5, max(2.2, len(lbl_r) * 0.34)), dpi=dpi)
            fig.patch.set_facecolor(bg); ax.set_facecolor(bg)
            ax.barh(range(len(lbl_r)), val_r, color="#3B82F6", alpha=0.88)
            ax.set_yticks(range(len(lbl_r))); ax.set_yticklabels(lbl_r, fontsize=fs, color=fg)
            ax.set_xlabel(col_name, fontsize=fs, color=fg)
            ax.tick_params(colors=fg); ax.xaxis.grid(True, color=gc, linewidth=0.5)
            for s in ax.spines.values(): s.set_edgecolor(gc)
        elif kind == "line":
            fig, ax = plt.subplots(figsize=(6, 3.5), dpi=dpi)
            fig.patch.set_facecolor(bg); ax.set_facecolor(bg)
            ax.plot(range(len(values)), values, color="#3B82F6", lw=2, marker="o", ms=3)
            step = max(1, len(labels) // 15)
            ax.set_xticks(range(0, len(labels), step))
            ax.set_xticklabels(labels[::step], rotation=35, ha="right", fontsize=fs, color=fg)
            ax.set_ylabel(col_name, fontsize=fs, color=fg)
            ax.tick_params(colors=fg); ax.yaxis.grid(True, color=gc, linewidth=0.5)
            for s in ax.spines.values(): s.set_edgecolor(gc)
        else: 
            fig, ax = plt.subplots(figsize=(max(4, len(labels) * 0.4), 3.5), dpi=dpi)
            fig.patch.set_facecolor(bg); ax.set_facecolor(bg)
            ax.bar(range(len(labels)), values, color=cols, alpha=0.88)
            step = max(1, len(labels) // 15)
            ax.set_xticks(range(0, len(labels), step))
            ax.set_xticklabels(labels[::step], rotation=35, ha="right", fontsize=fs, color=fg)
            ax.set_ylabel(col_name, fontsize=fs, color=fg)
            ax.tick_params(colors=fg); ax.yaxis.grid(True, color=gc, linewidth=0.5)
            for s in ax.spines.values(): s.set_edgecolor(gc)

        fig.tight_layout(pad=1.0)
        _old_fig = getattr(self, "_last_fig", None)
        self._last_fig = fig

        for child in self._chart_canvas_frame.findChildren(FigureCanvasQTAgg):
            child.setParent(None); child.deleteLater()
        if _old_fig is not None and _old_fig is not fig:
            plt.close(_old_fig)  # release previous figure from matplotlib's global registry
        canvas = FigureCanvasQTAgg(fig)
        lay = self._chart_canvas_frame.layout() or QVBoxLayout(self._chart_canvas_frame)
        lay.setContentsMargins(0,0,0,0); lay.addWidget(canvas)
        canvas.draw()

    def _save_chart_png(self):
        fig = getattr(self, "_last_fig", None)
        if not fig: return
        path, _ = QFileDialog.getSaveFileName(self, "Save chart", "", "PNG (*.png)")
        if path:
            fig.savefig(path, dpi=max(_UI_PREFS["chart_dpi"], 150),
                        bbox_inches="tight", facecolor=fig.get_facecolor())

    # ── Export ────────────────────────────────────────────────────────────

    def _copy_tsv(self):
        rows = ['\t'.join(self._headers)]
        for r in range(self._table.rowCount()):
            rows.append('\t'.join(
                self._table.item(r, c).text()
                for c in range(self._table.columnCount())))
        QApplication.clipboard().setText('\n'.join(rows))

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "", "CSV (*.csv)")
        if not path: return
        import csv as _csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = _csv.writer(f); w.writerow(self._headers)
            for r in range(self._table.rowCount()):
                w.writerow(self._table.item(r, c).text()
                           for c in range(self._table.columnCount()))

    # ── Theme ─────────────────────────────────────────────────────────────

    def apply_theme(self):
        fs = _fs(); fs2 = _fs(-2); fs3 = _fs(-3)
        bg = Theme.c("bg_secondary"); fg = Theme.c("text")
        fg2 = Theme.c("text_secondary"); bd = Theme.c("border")
        ac = Theme.c("accent"); sf = Theme.c("surface")

        self._top.setStyleSheet(f"QFrame{{background:{bg};border-radius:8px 8px 0 0;}}")
        self._title_lbl.setStyleSheet(
            f"color:{fg2};font-size:{fs2}px;font-weight:600;")
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
        self._table.verticalHeader().setDefaultSectionSize(_fs() + 12)
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
        super().__init__()
        self.setContentsMargins(0,4,0,4)
        lo = QVBoxLayout(self); lo.setContentsMargins(0,0,0,0); lo.setSpacing(2)
        hdr = QLabel("▶ Query result")
        hdr.setStyleSheet(
            f"color:{Theme.c('text_secondary')};font-size:{_fs(-2)}px;padding:0 4px;")
        lo.addWidget(hdr)
        self._te = QTextEdit(); self._te.setReadOnly(True)
        self._te.setPlainText(text)
        lines = text.count('\n') + 1
        self._te.setFixedHeight(min(max(60, lines * (_fs() + 4) + 20), 400))
        lo.addWidget(self._te)
        self.apply_theme()

    def apply_theme(self):
        fs = _fs(-1)
        self._te.setStyleSheet(
            f"QTextEdit{{background:{Theme.c('output_bg')};color:{Theme.c('output_text')};"
            f"border:0.5px solid {Theme.c('output_border')};border-radius:8px;"
            f"font-family:monospace;font-size:{fs}px;padding:8px;}}")


class ErrorBubble(QFrame):
    def __init__(self, err):
        super().__init__()
        self.setContentsMargins(0,4,0,4)
        lo = QVBoxLayout(self); lo.setContentsMargins(0,0,0,0)
        c = QFrame(); cl = QVBoxLayout(c); cl.setContentsMargins(12,8,12,8)
        cl.addWidget(QLabel(f"⚠ {err}")); lo.addWidget(c)
        c.setStyleSheet(f"QFrame{{background:{Theme.c('error_bg')};border:1px solid {Theme.c('error_border')};border-radius:12px;}}")
    def apply_theme(self): pass


class ChartBubble(QFrame):
    """Renders charts from sandbox show_chart/show_pie/show_histogram calls.
    Includes a type-switcher bar so the user can flip between bar/barh/pie/line.
    """

    _COLORS = ['#3B82F6','#10B981','#F59E0B','#EF4444','#8B5CF6',
               '#06B6D4','#F97316','#EC4899','#84CC16','#6B7280',
               '#A78BFA','#34D399','#FBBF24','#F87171','#60A5FA']

    _SWITCH_TYPES = [('Bar', 'bar'), ('Barh', 'barh'), ('Pie', 'pie'), ('Line', 'line')]

    def __init__(self, chart_data):
        super().__init__()
        self._data      = dict(chart_data)
        self._orig_kind = chart_data.get('type', 'bar')
        self._fig       = None
        self.setContentsMargins(0, 4, 0, 4)
        lo = QVBoxLayout(self); lo.setContentsMargins(0,0,0,0); lo.setSpacing(0)

        # ── Header row ────────────────────────────────────────────────────
        hdr = QFrame(); hl = QHBoxLayout(hdr); hl.setContentsMargins(6,3,6,3); hl.setSpacing(6)
        title = chart_data.get('title', '')
        self._hdr_lbl = QLabel(f"\u25b6 {title}" if title else "\u25b6 Chart")
        hl.addWidget(self._hdr_lbl)
        hl.addStretch()

        self._type_btns = []
        if self._orig_kind != 'histogram':
            for label, kind in self._SWITCH_TYPES:
                b = QPushButton(label); b.setCheckable(True); b.setFixedHeight(22)
                b.setChecked(kind == self._orig_kind)
                b.setCursor(QCursor(Qt.PointingHandCursor))
                b.clicked.connect(lambda _, k=kind: self._switch_type(k))
                hl.addWidget(b); self._type_btns.append((b, kind))

        self._save_btn = QPushButton("\u2193 PNG")
        self._save_btn.setFixedHeight(22)
        self._save_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._save_btn.clicked.connect(self._save_png)
        hl.addWidget(self._save_btn)
        lo.addWidget(hdr); self._hdr = hdr

        self._canvas_frame = QFrame()
        self._canvas_frame.setMinimumHeight(340)
        lo.addWidget(self._canvas_frame, stretch=1)
        QTimer.singleShot(0, self._render)

    def _switch_type(self, kind):
        self._data['type'] = kind
        for b, k in self._type_btns:
            b.setChecked(k == kind)
        self._render()

    def _save_png(self):
        if not self._fig: return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save chart as PNG", "", "PNG image (*.png)")
        if path:
            self._fig.savefig(path, dpi=max(_UI_PREFS['chart_dpi'], 150),
                              bbox_inches='tight', facecolor=self._fig.get_facecolor())

    def _render(self):
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

            dpi    = _UI_PREFS['chart_dpi']
            mfs    = max(7, _fs() - 5)  
            d      = self._data
            kind   = d.get('type', 'bar')
            labels = d.get('labels', [])
            values = d.get('values', [])
            title  = d.get('title', '')
            xlabel = d.get('xlabel', '')
            ylabel = d.get('ylabel', '')
            is_dark = Theme.is_dark()
            bg = '#0F172A' if is_dark else '#F8FAFC'
            fg = '#F1F5F9' if is_dark else '#0F172A'
            gc = '#334155' if is_dark else '#E2E8F0'
            n  = max(len(labels), 1)
            cols = (self._COLORS * math.ceil(n / len(self._COLORS)))[:n]

            if kind == 'pie':
                fig, ax = plt.subplots(figsize=(6, 5), dpi=dpi)
                fig.patch.set_facecolor(bg); ax.set_facecolor(bg)
                wedges, texts, autos = ax.pie(
                    values, labels=labels, autopct='%1.1f%%',
                    colors=cols, startangle=90,
                    textprops={'color': fg, 'fontsize': mfs})
                for at in autos: at.set_color(fg); at.set_fontsize(mfs - 1)
                if title: ax.set_title(title, color=fg, fontsize=mfs + 2, pad=12)

            elif kind == 'barh':
                lr, vr = labels[::-1], values[::-1]
                fig, ax = plt.subplots(figsize=(6, max(2.5, len(lr) * 0.36)), dpi=dpi)
                fig.patch.set_facecolor(bg); ax.set_facecolor(bg)
                ax.barh(range(len(lr)), vr, color='#3B82F6', alpha=0.88)
                ax.set_yticks(range(len(lr))); ax.set_yticklabels(lr, fontsize=mfs, color=fg)
                if xlabel: ax.set_xlabel(xlabel, color=fg, fontsize=mfs)
                if ylabel: ax.set_ylabel(ylabel, color=fg, fontsize=mfs)
                if title: ax.set_title(title, color=fg, fontsize=mfs + 2)
                ax.tick_params(colors=fg); ax.xaxis.grid(True, color=gc, linewidth=0.5)
                for s in ax.spines.values(): s.set_edgecolor(gc)

            elif kind == 'line':
                fig, ax = plt.subplots(figsize=(7, 4), dpi=dpi)
                fig.patch.set_facecolor(bg); ax.set_facecolor(bg)
                ax.plot(range(len(values)), values, color='#3B82F6', lw=2, marker='o', ms=4)
                step = max(1, len(labels) // 20)
                ax.set_xticks(range(0, len(labels), step))
                ax.set_xticklabels(labels[::step], rotation=40, ha='right', fontsize=mfs, color=fg)
                if xlabel: ax.set_xlabel(xlabel, color=fg, fontsize=mfs)
                if ylabel: ax.set_ylabel(ylabel, color=fg, fontsize=mfs)
                if title: ax.set_title(title, color=fg, fontsize=mfs + 2)
                ax.tick_params(colors=fg); ax.yaxis.grid(True, color=gc, linewidth=0.5)
                for s in ax.spines.values(): s.set_edgecolor(gc)

            elif kind == 'scatter':
                fig, ax = plt.subplots(figsize=(6, 4), dpi=dpi)
                fig.patch.set_facecolor(bg); ax.set_facecolor(bg)
                ax.scatter(range(len(values)), values, color='#3B82F6', alpha=0.7, s=18)
                if xlabel: ax.set_xlabel(xlabel, color=fg, fontsize=mfs)
                if ylabel: ax.set_ylabel(ylabel, color=fg, fontsize=mfs)
                if title: ax.set_title(title, color=fg, fontsize=mfs + 2)
                ax.tick_params(colors=fg)
                for s in ax.spines.values(): s.set_edgecolor(gc)

            elif kind == 'histogram':
                bins = d.get('bins', 30)
                fig, ax = plt.subplots(figsize=(7, 4), dpi=dpi)
                fig.patch.set_facecolor(bg); ax.set_facecolor(bg)
                ax.hist(values, bins=bins, color='#3B82F6', alpha=0.85, edgecolor='none')
                if xlabel: ax.set_xlabel(xlabel, color=fg, fontsize=mfs)
                ax.set_ylabel('Count', color=fg, fontsize=mfs)
                if title: ax.set_title(title, color=fg, fontsize=mfs + 2)
                ax.tick_params(colors=fg); ax.yaxis.grid(True, color=gc, linewidth=0.5)
                for s in ax.spines.values(): s.set_edgecolor(gc)

            else: 
                w = max(4.5, min(len(labels) * 0.45, 12))
                fig, ax = plt.subplots(figsize=(w, 4), dpi=dpi)
                fig.patch.set_facecolor(bg); ax.set_facecolor(bg)
                ax.bar(range(len(labels)), values, color=cols, alpha=0.88)
                step = max(1, len(labels) // 20)
                ax.set_xticks(range(0, len(labels), step))
                ax.set_xticklabels(labels[::step], rotation=40, ha='right', fontsize=mfs, color=fg)
                if xlabel: ax.set_xlabel(xlabel, color=fg, fontsize=mfs)
                if ylabel: ax.set_ylabel(ylabel, color=fg, fontsize=mfs)
                if title: ax.set_title(title, color=fg, fontsize=mfs + 2)
                ax.tick_params(colors=fg); ax.yaxis.grid(True, color=gc, linewidth=0.5)
                for s in ax.spines.values(): s.set_edgecolor(gc)

            fig.tight_layout(pad=1.2)
            _old_fig = getattr(self, "_fig", None)
            self._fig = fig

            for child in self._canvas_frame.findChildren(FigureCanvasQTAgg):
                child.setParent(None); child.deleteLater()
            if _old_fig is not None and _old_fig is not fig:
                plt.close(_old_fig)  # release previous figure from matplotlib's global registry
            canvas = FigureCanvasQTAgg(fig)
            lay = self._canvas_frame.layout() or QVBoxLayout(self._canvas_frame)
            lay.setContentsMargins(0,0,0,0); lay.addWidget(canvas)
            canvas.draw()

        except Exception as e:
            _itk_log.exception("Handled exception in _render")
            lay = self._canvas_frame.layout() or QVBoxLayout(self._canvas_frame)
            err_lbl = QLabel(f"\u26a0 Chart render error: {e}")
            err_lbl.setStyleSheet(
                f"color:{Theme.c('error_text')};font-size:{_fs(-2)}px;padding:8px;")
            lay.addWidget(err_lbl)

    def apply_theme(self):
        fs = _fs(-3)
        fg2 = Theme.c('text_secondary'); fg3 = Theme.c('text_tertiary')
        ac  = Theme.c('accent');         bd  = Theme.c('border')
        sf  = Theme.c('surface')
        self._hdr_lbl.setStyleSheet(f"color:{fg2};font-size:{fs}px;")
        tog = (f"QPushButton{{background:transparent;border:0.5px solid {bd};"
               f"border-radius:4px;padding:1px 8px;font-size:{fs}px;color:{fg2};}}"
               f"QPushButton:checked{{background:{ac};color:white;border-color:{ac};}}"
               f"QPushButton:hover{{border-color:{ac};}}")
        for b, _ in self._type_btns: b.setStyleSheet(tog)
        self._save_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{fg3};font-size:{fs}px;padding:0 4px;}}"
            f"QPushButton:hover{{color:{ac};}}")



# ── Auto-growing text input ───────────────────────────────────────────────────

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
        return self._forced_h

    def _on_changed(self):
        self.char_changed.emit(len(self.toPlainText()))
        self._adjust()

    def _adjust(self):
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
        super().resizeEvent(event)
        self._adjust()   

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submit.emit()
        else:
            super().keyPressEvent(event)

    def text(self):       return self.toPlainText().strip()
    def setText(self, t): self.setPlainText(t)
    def clear(self):      super().clear()


# ── Drag handle for resizing the composer ─────────────────────────────────────

class ComposerResizeHandle(QFrame):
    """Thin horizontal bar at the top of the composer — drag it up to make the
    input taller, drag down to shrink. Emits delta_y on each drag step."""

    delta_y = Signal(int)   
    reset   = Signal()     

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(8)
        self.setCursor(QCursor(Qt.SizeVerCursor))
        self.setMouseTracking(True)
        self._press_y = None
        self.apply_theme()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_y = event.globalPosition().y()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press_y is not None:
            cur = event.globalPosition().y()
            dy = cur - self._press_y
            if abs(dy) >= 1:
                self.delta_y.emit(int(dy))
                self._press_y = cur
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._press_y = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.reset.emit()
        super().mouseDoubleClickEvent(event)

    def apply_theme(self):
        c1 = Theme.c('border'); c2 = Theme.c('text_tertiary')
        self.setStyleSheet(
            f"ComposerResizeHandle{{background:transparent;}}"
            f"ComposerResizeHandle:hover{{background:{c1};}}")

    def paintEvent(self, event):
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


# ── Customize dialog ──────────────────────────────────────────────────────────

class CustomizeDialog(QDialog):
    """Font size, chart quality, and display options."""

    applied = Signal() 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customize Appearance")
        self.setMinimumWidth(380); self.setMaximumWidth(440)
        lo = QVBoxLayout(self); lo.setSpacing(14)

        fg  = Theme.c('text'); fg2 = Theme.c('text_secondary')
        bg  = Theme.c('bg');   bd  = Theme.c('border')
        sf  = Theme.c('surface'); ac = Theme.c('accent')
        base_ss = (f"QDialog{{background:{bg};}} QLabel{{color:{fg};}} "
                   f"QFrame{{border:none;}} QGroupBox{{color:{fg};border:1px solid {bd};"
                   f"border-radius:8px;margin-top:6px;padding-top:6px;font-weight:600;}}")
        self.setStyleSheet(base_ss)

        # ── Font size ─────────────────────────────────────────────────────
        fs_row = QHBoxLayout()
        fs_row.addWidget(QLabel("Font size:"))
        self._fs_lbl = QLabel(f"{_UI_PREFS['font_size']} px")
        self._fs_lbl.setMinimumWidth(36)
        self._fs_slider = QSlider(Qt.Horizontal)
        self._fs_slider.setRange(11, 20); self._fs_slider.setValue(_UI_PREFS['font_size'])
        self._fs_slider.setTickInterval(1); self._fs_slider.setTickPosition(QSlider.TicksBelow)
        self._fs_slider.valueChanged.connect(
            lambda v: self._fs_lbl.setText(f"{v} px"))
        fs_row.addWidget(self._fs_slider, stretch=1)
        fs_row.addWidget(self._fs_lbl)
        lo.addLayout(fs_row)

        # ── Bubble max width ──────────────────────────────────────────────
        bw_row = QHBoxLayout()
        bw_row.addWidget(QLabel("Bubble max width:"))
        self._bw_spin = QSpinBox()
        self._bw_spin.setRange(400, 1000); self._bw_spin.setSingleStep(20)
        self._bw_spin.setValue(_UI_PREFS['bubble_max_width'])
        self._bw_spin.setSuffix(" px")
        self._bw_spin.setStyleSheet(
            f"QSpinBox{{background:{sf};color:{fg};border:1px solid {bd};"
            f"border-radius:6px;padding:4px 8px;}}")
        bw_row.addWidget(self._bw_spin); bw_row.addStretch()
        lo.addLayout(bw_row)

        # ── Chart DPI ─────────────────────────────────────────────────────
        dpi_row = QHBoxLayout()
        dpi_row.addWidget(QLabel("Chart quality (DPI):"))
        self._dpi_combo = QComboBox()
        self._dpi_combo.addItems(["72 — draft", "100 — standard", "150 — high", "200 — ultra"])
        dpi_map = {72: 0, 100: 1, 150: 2, 200: 3}
        self._dpi_combo.setCurrentIndex(dpi_map.get(_UI_PREFS['chart_dpi'], 1))
        self._dpi_combo.setStyleSheet(
            f"QComboBox{{background:{sf};color:{fg};border:1px solid {bd};"
            f"border-radius:6px;padding:4px 8px;}}")
        dpi_row.addWidget(self._dpi_combo); dpi_row.addStretch()
        lo.addLayout(dpi_row)

        # ── Timestamps ────────────────────────────────────────────────────
        self._ts_chk = QCheckBox("Show message timestamps")
        self._ts_chk.setChecked(_UI_PREFS['show_timestamps'])
        self._ts_chk.setStyleSheet(f"QCheckBox{{color:{fg};font-size:13px;}}")
        lo.addWidget(self._ts_chk)

        # ── Separator ─────────────────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"QFrame{{border:none;border-top:1px solid {bd};}}")
        lo.addWidget(sep)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        reset_btn = QPushButton("Reset defaults")
        reset_btn.setStyleSheet(
            f"QPushButton{{background:{sf};color:{fg2};border:1px solid {bd};"
            f"border-radius:8px;padding:8px 16px;font-size:13px;}}"
            f"QPushButton:hover{{background:{Theme.c('surface_hover')};}}")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet(
            f"QPushButton{{background:{ac};color:white;border:none;"
            f"border-radius:8px;padding:8px 20px;font-size:13px;font-weight:600;}}"
            f"QPushButton:hover{{background:{Theme.c('accent_hover')};}}")
        apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(apply_btn)
        lo.addLayout(btn_row)

    def _dpi_value(self):
        return [72, 100, 150, 200][self._dpi_combo.currentIndex()]

    def _reset(self):
        self._fs_slider.setValue(14)
        self._bw_spin.setValue(740)
        self._dpi_combo.setCurrentIndex(1)
        self._ts_chk.setChecked(False)

    def _apply(self):
        _UI_PREFS['font_size']       = self._fs_slider.value()
        _UI_PREFS['bubble_max_width']= self._bw_spin.value()
        _UI_PREFS['chart_dpi']       = self._dpi_value()
        _UI_PREFS['show_timestamps'] = self._ts_chk.isChecked()
        self.applied.emit()
        self.accept()


# ── Multi-conversation support ────────────────────────────────────────────────

class Conversation:
    """One chat session: its history, widgets, and dedicated chat scroll area.
    Each Conversation owns a QScrollArea + content widget so we can keep all
    bubbles alive when switching tabs (no rebuild needed)."""

    def __init__(self, title="New chat"):
        self.id          = uuid.uuid4().hex[:12]
        self.title       = title
        self.history     = []      
        self.widgets     = []      
        self.draft_text  = ""      
        self.draft_files = []      
        self._auto_title = True    

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cw = QWidget()
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
        self._title_lbl.setText(t)
        self._title_lbl.setToolTip(t)

    def set_current(self, is_current):
        self._is_cur = is_current
        self.apply_theme()

    def enterEvent(self, event):
        self._x.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._x.setVisible(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self._x.geometry().contains(event.pos()):
            self.selected.emit(self.conv_id)
        super().mousePressEvent(event)

    def _on_delete(self):
        self.deleted.emit(self.conv_id)

    def apply_theme(self):
        fs = _fs(-1)
        fg  = Theme.c('text');           fg2 = Theme.c('text_secondary')
        bd  = Theme.c('border_light');   ac  = Theme.c('accent')
        sf  = Theme.c('surface')
        if self._is_cur:
            bg     = Theme.c('accent_surface')
            text_c = Theme.c('accent')
            self.setStyleSheet(
                f"ConversationListItem{{background:{bg};border:2px solid {ac};"
                f"border-radius:8px;}}")
            self._title_lbl.setStyleSheet(
                f"color:{text_c};font-size:{fs}px;font-weight:700;"
                f"background:transparent;border:none;")
        else:
            self.setStyleSheet(
                f"ConversationListItem{{background:transparent;border:1px solid transparent;"
                f"border-radius:8px;}}"
                f"ConversationListItem:hover{{background:{Theme.c('surface_hover')};"
                f"border-color:{bd};}}")
            self._title_lbl.setStyleSheet(
                f"color:{fg};font-size:{fs}px;font-weight:500;"
                f"background:transparent;border:none;")
        self._x.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;color:{fg2};"
            f"font-size:11px;border-radius:9px;}}"
            f"QPushButton:hover{{background:{Theme.c('error_bg')};"
            f"color:{Theme.c('error_text')};}}")


# ── Main chat dialog ──────────────────────────────────────────────────────────

class AIChatDialog(QDialog):
    def __init__(self, ai_node, pw=None):
        super().__init__(pw)
        self.node = ai_node; self.current_data = None; self._worker = None
        self._sb = None; self._retry = 0
        self._pending_files = []
        self._user_stopped = False
        self._interpreting  = False          # second-pass interpretation guard
        self._code_cache    = {}             # (code, data id, n) -> exec result
        self._interpret_allowed = []         # numbers the last result produced
        self._autoconfigured = False         # auto-detect ran/applied
        self._probe = None                   # background server probe
        self._exp_mode      = False
        self._exp_session   = None
        self._exp_messages  = []
        self._exp_buf       = []
        self._exp_turn      = 0
        self._exp_max_turns = 10
        self._exp_question  = ""
        self._exp_sys       = ""
        self._conversations = [Conversation(title="New chat")]
        self._current_idx   = 0
        self._conv_items    = {}   

        self._cfg = {'backend': 'ollama', 'model': '', 'mlx_host': MLX_BASE,
                     'temperature': 0.2, 'num_ctx': 8192,
                     'explore_max_turns': 10,
                     'interpret_results': True, 'verify_numbers': True}
        self.setWindowTitle("AI Data Assistant")
        self.setMinimumSize(900, 650); self.resize(1240, 750)
        self._build_ui()
        self._start_autodetect()

    @property
    def _cur(self):
        return self._conversations[self._current_idx]

    @property
    def _history(self):
        return self._cur.history

    @property
    def _widgets(self):
        return self._cur.widgets

    @property
    def _cl(self):
        return self._cur.cl

    @property
    def _cw(self):
        return self._cur.cw

    @property
    def _scroll(self):
        return self._cur.scroll

    def _build_ui(self):
        root = QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # ── Sidebar (conversation list) ───────────────────────────────────────
        self._sidebar = QFrame()
        self._sidebar.setFixedWidth(230)
        sb = QVBoxLayout(self._sidebar)
        sb.setContentsMargins(10, 12, 10, 12); sb.setSpacing(8)

        self._new_chat_btn = QPushButton("＋  New chat")
        self._new_chat_btn.setFixedHeight(36)
        self._new_chat_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._new_chat_btn.setToolTip("Start a new conversation (Ctrl+N)")
        self._new_chat_btn.clicked.connect(lambda: self._new_conversation(switch_to=True))
        sb.addWidget(self._new_chat_btn)

        self._conv_hdr = QLabel("Conversations")
        sb.addWidget(self._conv_hdr)

        self._conv_list_sc = QScrollArea()
        self._conv_list_sc.setWidgetResizable(True)
        self._conv_list_sc.setFrameShape(QFrame.NoFrame)
        self._conv_list_sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._conv_list_w = QWidget()
        self._conv_list_lo = QVBoxLayout(self._conv_list_w)
        self._conv_list_lo.setContentsMargins(0, 0, 0, 0)
        self._conv_list_lo.setSpacing(2)
        self._conv_list_lo.addStretch()
        self._conv_list_sc.setWidget(self._conv_list_w)
        sb.addWidget(self._conv_list_sc, stretch=1)

        root.addWidget(self._sidebar)

        # ── Main content area ────────────────────────────────────────────────
        main_wrap = QFrame()
        main = QVBoxLayout(main_wrap); main.setContentsMargins(0,0,0,0); main.setSpacing(0)

        # ── Header ───────────────────────────────────────────────────────────
        hdr = QFrame(); hl = QHBoxLayout(hdr); hl.setContentsMargins(20,10,20,10); hl.setSpacing(8)
        self._title = QLabel("AI Data Assistant"); hl.addWidget(self._title); hl.addStretch()
        self._speed = QLabel(""); self._speed.setVisible(False); hl.addWidget(self._speed)
        # Customize button
        self._cust_btn = QPushButton("Customize")
        self._cust_btn.setToolTip("Font size, chart quality, timestamps")
        self._cust_btn.clicked.connect(self._open_customize); hl.addWidget(self._cust_btn)
        # Clear chat button
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setToolTip("Clear chat history (Ctrl+K)")
        self._clear_btn.clicked.connect(self._clear_chat); hl.addWidget(self._clear_btn)
        # Settings button
        tb = QPushButton("Settings"); tb.clicked.connect(self._open_settings)
        hl.addWidget(tb); self._sbtn = tb
        self._dot = QLabel("●"); hl.addWidget(self._dot)
        self._status = QLabel("Not connected"); hl.addWidget(self._status)
        main.addWidget(hdr); self._hdr = hdr

        # ── Suggestions ───────────────────────────────────────────────────────
        self._sug = QFrame(); self._sug_lo = QHBoxLayout(self._sug)
        self._sug_lo.setContentsMargins(12,6,12,6)
        main.addWidget(self._sug)

        # ── Chat area: QStackedWidget — one scroll area per conversation ─────
        self._chat_stack = QStackedWidget()
        self._chat_stack.addWidget(self._conversations[0].scroll)
        main.addWidget(self._chat_stack, stretch=1)

        # ── Thinking indicator ────────────────────────────────────────────────
        self._think = QFrame(); self._think.setVisible(False)
        tl = QHBoxLayout(self._think); tl.setContentsMargins(20,5,20,5); tl.setSpacing(8)
        self._tlbl = QLabel("Thinking…"); tl.addWidget(self._tlbl)
        prog = QProgressBar(); prog.setRange(0,0); prog.setMaximumHeight(3)
        tl.addWidget(prog); main.addWidget(self._think)

        outer = QFrame(); outer_l = QVBoxLayout(outer)
        outer_l.setContentsMargins(16, 8, 16, 10); outer_l.setSpacing(2)

        self._resize_handle = ComposerResizeHandle()
        self._resize_handle.setToolTip("Drag to resize the input — double-click to reset")
        self._resize_handle.delta_y.connect(self._on_composer_resize)
        self._resize_handle.reset.connect(self._reset_composer_height)
        outer_l.addWidget(self._resize_handle)

        self._composer = QFrame()
        comp_l = QVBoxLayout(self._composer); comp_l.setContentsMargins(8, 8, 8, 8); comp_l.setSpacing(6)

        self._preview_row = QWidget()
        self._preview_lo = QHBoxLayout(self._preview_row)
        self._preview_lo.setContentsMargins(2, 2, 2, 2); self._preview_lo.setSpacing(6)
        self._preview_lo.addStretch()
        self._preview_row.setVisible(False)
        comp_l.addWidget(self._preview_row)
        self._previews = []  

        in_row = QHBoxLayout(); in_row.setContentsMargins(0,0,0,0); in_row.setSpacing(8)
        self._attach_btn = QPushButton("+"); self._attach_btn.setFixedSize(38, 38)
        self._attach_btn.setToolTip("Attach image, PDF, or text file")
        self._attach_btn.clicked.connect(self._attach_file)
        in_row.addWidget(self._attach_btn, alignment=Qt.AlignBottom)

        self._input = AutoGrowTextEdit()
        self._input.setPlaceholderText(
            "Ask about your data\u2026   (Shift+Enter for new line, Esc to stop)")
        self._input.submit.connect(self._send)
        in_row.addWidget(self._input, stretch=1)

        btn_col = QVBoxLayout(); btn_col.setSpacing(4)
        self._stop = QPushButton("\u25a0"); self._stop.setVisible(False); self._stop.setFixedSize(60, 38)
        self._stop.clicked.connect(self._do_stop); btn_col.addWidget(self._stop)
        self._sendb = QPushButton("Send \u21b5"); self._sendb.setFixedHeight(38)
        self._sendb.clicked.connect(self._send); btn_col.addWidget(self._sendb)
        in_row.addLayout(btn_col)
        comp_l.addLayout(in_row)
        outer_l.addWidget(self._composer)

        self._counter = QLabel("0 chars")
        self._counter.setAlignment(Qt.AlignRight)
        self._input.char_changed.connect(self._update_counter)
        outer_l.addWidget(self._counter)

        main.addWidget(outer); self._inp_frame = outer
        root.addWidget(main_wrap, stretch=1)

        self._attach_bar = self._preview_row
        self._attach_lbl = self._counter

        # ── Keyboard shortcuts ────────────────────────────────────────────────
        from PySide6.QtGui import QShortcut
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self._clear_chat)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(
            lambda: self._new_conversation(switch_to=True))
        QShortcut(QKeySequence("Escape"), self).activated.connect(
            lambda: self._do_stop() if self._worker else None)

        self._add_conv_list_item(self._conversations[0], is_current=True)

        self._apply_theme()
        global_theme.themeChanged.connect(self._on_global_theme_change)
        self._add_ai(
            "**AI Data Assistant — local models only.**\n\n"
            "Click **Settings** to connect Ollama or MLX.\n\n")
        self._update_sug(None)

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        d = BackendDialog(self._cfg, self)
        if d.exec() == QDialog.Accepted:
            self._cfg = d.get_config()
            b = self._cfg['backend']
            if b == 'ollama' and self._cfg.get('model'):
                self._dot.setStyleSheet(f"color:{Theme.c('success_dot')};font-size:10px;")
                self._status.setText(f"Ollama: {self._cfg['model']}")
                self._add_ai(f"**Connected — Ollama** `{self._cfg['model']}`")
            elif b == 'mlx':
                self._dot.setStyleSheet(f"color:{Theme.c('success_dot')};font-size:10px;")
                self._status.setText(f"MLX: {self._cfg.get('mlx_host','')}")
                self._add_ai(f"**Connected — MLX** `{self._cfg.get('mlx_host','')}`")
            elif b == 'custom' and self._cfg.get('custom_base_url'):
                self._dot.setStyleSheet(f"color:{Theme.c('success_dot')};font-size:10px;")
                mdl = self._cfg.get('custom_model','')
                self._status.setText(f"Custom API: {mdl or self._cfg.get('custom_base_url','')}")
                self._add_ai(f"**Connected — Custom API** `{mdl}`")
            else:
                self._dot.setStyleSheet(f"color:{Theme.c('error_dot')};font-size:10px;")
                self._status.setText("Not connected")
            self._update_sug(self.current_data)

    def _open_customize(self):
        d = CustomizeDialog(self)
        d.applied.connect(self._apply_theme) 
        d.exec()

    def _update_counter(self, n_chars):
        tokens = max(0, round(n_chars / 3.5))
        self._counter.setText(f"{n_chars:,} chars  ~{tokens:,} tokens")

    def _clear_chat(self):
        if self._worker: return  
        for w in list(self._widgets):
            w.setParent(None); w.deleteLater()
        self._widgets.clear()
        self._history.clear()
        self._add_ai("Chat cleared. Ask me anything about your data.")

    # ── Conversations (sidebar) ───────────────────────────────────────────────

    def _add_conv_list_item(self, conv, is_current=False):
        """Create the sidebar entry for an existing Conversation."""
        item = ConversationListItem(conv.id, conv.title, is_current=is_current)
        item.selected.connect(self._switch_conversation)
        item.deleted.connect(self._delete_conversation)
        self._conv_list_lo.insertWidget(self._conv_list_lo.count() - 1, item)
        self._conv_items[conv.id] = item

    def _new_conversation(self, switch_to=True):
        """Create a new conversation, add it to the stack and sidebar."""
        if self._worker:
            return   
        existing_titles = {c.title for c in self._conversations}
        if "New chat" not in existing_titles:
            title = "New chat"
        else:
            n = 2
            while f"New chat {n}" in existing_titles:
                n += 1
            title = f"New chat {n}"
        conv = Conversation(title=title)
        self._conversations.append(conv)
        self._chat_stack.addWidget(conv.scroll)
        self._add_conv_list_item(conv, is_current=False)
        if switch_to:
            self._switch_conversation(conv.id)
            self._add_ai(
                "**New conversation.** Ask me anything about your data — "
                "I'll keep this thread separate from the others.")

    def _switch_conversation(self, conv_id):
        """Switch to the conversation with the given id. Saves the current draft
        (composer text + attachments) and restores the target's draft."""
        if self._worker:
            return  
        target_idx = None
        for i, c in enumerate(self._conversations):
            if c.id == conv_id:
                target_idx = i; break
        if target_idx is None or target_idx == self._current_idx:
            return

        cur = self._cur
        cur.draft_text  = self._input.toPlainText()
        cur.draft_files = list(self._pending_files)

        old_item = self._conv_items.get(cur.id)
        if old_item: old_item.set_current(False)

        self._current_idx = target_idx
        self._chat_stack.setCurrentWidget(self._cur.scroll)

        new_item = self._conv_items.get(self._cur.id)
        if new_item: new_item.set_current(True)

        self._clear_attachments()
        self._input.setPlainText(self._cur.draft_text or "")
        for entry in (self._cur.draft_files or []):
            self._pending_files.append(entry)
            kind = entry.get('type', 'text')
            img_b64 = entry.get('data') if kind == 'image' else None
            self._add_preview(entry.get('name', '?'), kind, entry, image_b64=img_b64)

        self._update_sug(self.current_data)
        self._scrollb()

    def _delete_conversation(self, conv_id):
        """Delete a conversation. If it's the current one, switch to a neighbour.
        If it's the last conversation, replace it with a fresh empty one."""
        if self._worker:
            return
        idx = None
        for i, c in enumerate(self._conversations):
            if c.id == conv_id:
                idx = i; break
        if idx is None: return

        if len(self._conversations) == 1:
            self._clear_chat()
            return

        conv = self._conversations[idx]
        was_current = (idx == self._current_idx)

        item = self._conv_items.pop(conv_id, None)
        if item:
            item.setParent(None); item.deleteLater()

        self._chat_stack.removeWidget(conv.scroll)
        conv.scroll.setParent(None); conv.scroll.deleteLater()

        del self._conversations[idx]

        if was_current:
            new_idx = max(0, idx - 1)
            self._current_idx = new_idx
            self._chat_stack.setCurrentWidget(self._cur.scroll)
            new_item = self._conv_items.get(self._cur.id)
            if new_item: new_item.set_current(True)
            self._clear_attachments()
            self._input.setPlainText(self._cur.draft_text or "")
            for entry in (self._cur.draft_files or []):
                self._pending_files.append(entry)
                kind = entry.get('type', 'text')
                img_b64 = entry.get('data') if kind == 'image' else None
                self._add_preview(entry.get('name','?'), kind, entry, image_b64=img_b64)
            self._update_sug(self.current_data)
            self._scrollb()
        elif idx < self._current_idx:
            self._current_idx -= 1

    def _maybe_set_conv_title(self, text):
        """If the current conversation still has its auto-generated title and
        the user just sent their first message, derive a short title from it."""
        conv = self._cur
        if not conv._auto_title: return
        if not text: return
        title = text.strip().split('\n', 1)[0]
        if len(title) > 32: title = title[:30].rstrip() + '…'
        conv.title       = title
        conv._auto_title = False
        item = self._conv_items.get(conv.id)
        if item: item.set_title(title)

    def _set_sidebar_enabled(self, enabled):
        """Enable/disable conversation switching (used during streaming)."""
        self._new_chat_btn.setEnabled(enabled)
        for item in self._conv_items.values():
            item.setEnabled(enabled)

    # ── File attachment ────────────────────────────────────────────────────────

    def _attach_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach File", "",
            "Supported files (*.png *.jpg *.jpeg *.bmp *.tiff *.webp "
            "*.pdf *.txt *.csv *.json *.md *.tsv);;"
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.webp);;"
            "Documents (*.pdf *.txt *.csv *.json *.md *.tsv)")
        if not path: return
        ext  = os.path.splitext(path)[1].lower()
        name = os.path.basename(path)

        if ext in IMAGE_EXTS:
            data, mime = _read_image_b64(path)
            entry = {'type':'image','name':name,'data':data,'mime':mime}
            self._pending_files.append(entry)
            self._add_preview(name, 'image', entry, image_b64=data)

        elif ext == '.pdf':
            text = _extract_pdf_text(path)
            if text == "__MISSING_PYPDF__":
                self._add_ai("PDF reading requires pypdf.\nInstall with:  `pip install pypdf`")
                return
            if not text:
                self._add_ai(f"Could not extract text from **{name}**.")
                return
            entry = {'type':'text','name':name,'content':text}
            self._pending_files.append(entry)
            self._add_preview(name, 'pdf', entry)

        else:
            try:
                content = _read_text_file(path)
                entry = {'type':'text','name':name,'content':content}
                self._pending_files.append(entry)
                self._add_preview(name, 'text', entry)
            except Exception as e:
                _itk_log.exception("Handled exception in _attach_file")
                self._add_ai(f"Could not read **{name}**: {e}")

    def _add_preview(self, name, kind, entry, image_b64=None):
        """Show an inline preview chip inside the composer"""
        prev = AttachmentPreview(name, kind, image_b64=image_b64)
        prev._entry = entry  
        prev.removed.connect(self._remove_preview)
        self._preview_lo.insertWidget(self._preview_lo.count() - 1, prev)
        self._previews.append(prev)
        self._preview_row.setVisible(True)

    def _remove_preview(self, prev):
        """Remove one preview chip and its pending file."""
        entry = getattr(prev, '_entry', None)
        if entry in self._pending_files:
            self._pending_files.remove(entry)
        if prev in self._previews:
            self._previews.remove(prev)
        prev.setParent(None); prev.deleteLater()
        if not self._previews:
            self._preview_row.setVisible(False)

    def _clear_attachments(self):
        for prev in list(self._previews):
            prev.setParent(None); prev.deleteLater()
        self._previews.clear()
        self._pending_files.clear()
        self._preview_row.setVisible(False)

    # ── Composer resize (drag handle) ─────────────────────────────────────────

    def _on_composer_resize(self, dy):
        """User dragged the resize handle. dy > 0 = drag down (shrink),
        dy < 0 = drag up (grow)."""
        cur = self._input.get_forced_height() or self._input.height()
        new_h = cur - dy
        self._input.set_forced_height(new_h)

    def _reset_composer_height(self):
        """Double-click on the handle → back to auto-grow."""
        self._input.set_forced_height(None)

    # ── Sending ───────────────────────────────────────────────────────────────

    def _send(self):
        text = self._input.text().strip()
        if not text and not self._pending_files: return
        b = self._cfg.get('backend', '')
        if not b or (b == 'ollama' and not self._cfg.get('model')) or \
           (b == 'custom' and not self._cfg.get('custom_base_url')):
            self._open_settings(); return

        self._user_stopped = False
        self._maybe_set_conv_title(text)
        self._set_sidebar_enabled(False)
        self._input.setEnabled(False); self._sendb.setVisible(False)
        self._stop.setVisible(True); self._attach_btn.setEnabled(False)

        attachments = list(self._pending_files)

        for a in attachments:
            chip = AttachmentChip(a['name'], a.get('type', 'text'))
            self._widgets.append(chip)
            self._cl.insertWidget(self._cl.count()-1, chip)

        if text:
            self._add_user(text)
        self._input.clear()
        self._clear_attachments() 

        self._history.append({"role":"user","content":text or "(see attached file)"})
        self._retry = 0
        self._think.setVisible(True); self._tlbl.setText("Thinking…")
        self._speed.setVisible(True); self._speed.setText("")

        self._sb = StreamBubble(); self._widgets.append(self._sb)
        self._cl.insertWidget(self._cl.count()-1, self._sb)

        sys_prompt = _build_system_prompt(self.current_data, b)
        max_t = max(512, self._cfg.get('num_ctx', 8192) - 2000)
        trimmed = _trim_history(list(self._history), max_t)

        self._worker = StreamWorker(b, trimmed, sys_prompt, self._cfg, attachments)
        self._worker.token_received.connect(self._on_tok)
        self._worker.stats_update.connect(self._on_stats)
        self._worker.stream_done.connect(self._on_done)
        self._worker.error_occurred.connect(self._on_err)
        self._worker.start()

    def _on_tok(self, t):
        if self._user_stopped: return
        if self._sb: self._sb.append(t); self._scrollb()

    def _on_stats(self, n, el):
        if self._user_stopped: return
        if el > 0: self._speed.setText(f"{n/el:.1f} tok/s")

    MAX_AI_RETRIES = 3

    def _run_cached(self, code, particles):
        """Execute sandbox code, memoising error-free results within the current
        dataset so identical queries are deterministic and instant."""
        key = (code, id(self.current_data), len(particles))
        hit = self._code_cache.get(key)
        if hit is not None:
            return hit
        res = _execute_query_code(code, particles, self.current_data)
        if res[3] is None:                       # cache only successful runs
            if len(self._code_cache) > 64:
                self._code_cache.clear()
            self._code_cache[key] = res
        return res

    def _on_done(self, full):
        if self._user_stopped:
            self._user_stopped = False
            return
        self._think.setVisible(False); self._stop.setVisible(False)
        self._sendb.setVisible(True)
        if self._sb: self._sb.finalise()
        self._history.append({"role": "assistant", "content": full})

        particles = self.current_data.get('particle_data', []) if self.current_data else []
        exec_error   = None
        import_error = False
        produced     = False
        computed_numbers = []          # every number the code actually produced
        result_payload   = []          # compact result text for interpretation

        for m in _CODE_RE.finditer(full):
            if not particles: continue
            code = m.group(1).strip()
            text_out, tables, charts, err = self._run_cached(code, particles)

            for tbl in tables:
                if tbl['headers'] and tbl['rows']:
                    w = InteractiveTableBubble(tbl['headers'], tbl['rows'], tbl['title'])
                    self._widgets.append(w)
                    self._cl.insertWidget(self._cl.count()-1, w)
                    produced = True
                    computed_numbers.extend(_numbers_in_rows(tbl['rows']))
                    result_payload.append(_compact_table(tbl))

            for ch in charts:
                w = ChartBubble(ch)
                self._widgets.append(w)
                self._cl.insertWidget(self._cl.count()-1, w)
                produced = True
                computed_numbers.extend(
                    _floats_in_text(' '.join(str(v) for v in ch.get('values', []))))

            if text_out:
                produced = True
                computed_numbers.extend(_floats_in_text(text_out))
                result_payload.append(text_out[:1500])
                parsed = _try_parse_table(text_out)
                if parsed:
                    headers, rows = parsed
                    w = InteractiveTableBubble(headers, rows)
                else:
                    w = OutputBubble(text_out)
                self._widgets.append(w)
                self._cl.insertWidget(self._cl.count()-1, w)

            if err:
                exec_error = err
                if '__import__' in err:
                    import_error = True

        self._sb = None; self._scrollb()

        # ── #1 self-correction: feed ANY sandbox error back and retry ──
        if exec_error and self._retry < self.MAX_AI_RETRIES:
            self._retry += 1
            self._history.append({"role": "user",
                                  "content": _correction_hint(exec_error, import_error)})
            notice = ErrorBubble(
                f"⟳ Fixing sandbox error (attempt {self._retry}/{self.MAX_AI_RETRIES})…")
            self._widgets.append(notice)
            self._cl.insertWidget(self._cl.count()-1, notice)
            self._scrollb()
            QTimer.singleShot(200, self._retry_send)
            return

        if exec_error:                            # retries exhausted — surface it
            eb = ErrorBubble(exec_error)
            self._widgets.append(eb)
            self._cl.insertWidget(self._cl.count()-1, eb)

        self._retry = 0

        # ── #3 flag prose figures not backed by the computed output ──
        if produced and self._cfg.get('verify_numbers', True):
            unverified = _unverified_numbers(_CODE_RE.sub('', full), computed_numbers)
            if unverified:
                shown = ", ".join(unverified[:8]) + (" …" if len(unverified) > 8 else "")
                note = OutputBubble("⚠ Unverified figures (not produced by the code): " + shown)
                self._widgets.append(note)
                self._cl.insertWidget(self._cl.count()-1, note)
                self._scrollb()

        # ── #2 grounded second pass when the model gave code but little prose ──
        first_prose = _CODE_RE.sub('', full).strip()
        if (produced and result_payload and not self._interpreting
                and len(first_prose) < 40
                and self._cfg.get('interpret_results', True)):
            self._start_interpretation(result_payload, computed_numbers)
            return

        QTimer.singleShot(5000, lambda: self._speed.setVisible(False))
        self._enable()

    def _start_interpretation(self, payload, allowed):
        """Second pass: hand the computed results back to the model for a short,
        grounded takeaway. It may only restate numbers already produced."""
        try:
            b = self._cfg.get('backend', '')
            self._interpreting = True
            self._interpret_allowed = list(allowed)
            self._think.setVisible(True); self._tlbl.setText("Interpreting…")
            self._stop.setVisible(True); self._sendb.setVisible(False)
            self._sb = StreamBubble(); self._widgets.append(self._sb)
            self._cl.insertWidget(self._cl.count()-1, self._sb)
            results_txt = "\n\n".join(payload)[:6000]
            msgs = list(self._history) + [{
                "role": "user",
                "content": ("Here are the EXACT results your code just produced:\n\n"
                            f"{results_txt}\n\n"
                            "Give a 1-3 sentence plain-language takeaway for the user. "
                            "Use ONLY numbers shown above — introduce no new figures — "
                            "and do not write any code.")
            }]
            sys_prompt = _build_system_prompt(self.current_data, b)
            max_t = max(512, self._cfg.get('num_ctx', 8192) - 2000)
            msgs = _trim_history(msgs, max_t)
            self._worker = StreamWorker(b, msgs, sys_prompt, self._cfg, [])
            self._worker.token_received.connect(self._on_tok)
            self._worker.stats_update.connect(self._on_stats)
            self._worker.stream_done.connect(self._on_interpret_done)
            self._worker.error_occurred.connect(self._on_err)
            self._worker.start()
        except Exception:
            _itk_log.exception("Handled exception in _start_interpretation")
            self._interpreting = False
            self._enable()

    def _on_interpret_done(self, full):
        self._interpreting = False
        if self._user_stopped:
            self._user_stopped = False
            return
        self._think.setVisible(False); self._stop.setVisible(False)
        self._sendb.setVisible(True)
        if self._sb: self._sb.finalise(); self._sb = None
        prose = _CODE_RE.sub('', full).strip()       # never execute this pass
        if prose:
            self._history.append({"role": "assistant", "content": prose})
            if self._cfg.get('verify_numbers', True):
                unv = _unverified_numbers(prose, self._interpret_allowed)
                if unv:
                    note = OutputBubble("⚠ Unverified figures in summary: "
                                        + ", ".join(unv[:8]))
                    self._widgets.append(note)
                    self._cl.insertWidget(self._cl.count()-1, note)
        self._scrollb()
        QTimer.singleShot(5000, lambda: self._speed.setVisible(False))
        self._enable()

    def _retry_send(self):
        """Re-trigger the LLM after injecting a sandbox correction hint."""
        b = self._cfg.get('backend', '')
        self._input.setEnabled(False); self._sendb.setVisible(False)
        self._stop.setVisible(True); self._attach_btn.setEnabled(False)
        self._think.setVisible(True); self._tlbl.setText("Retrying…")
        self._speed.setVisible(True)
        self._sb = StreamBubble(); self._widgets.append(self._sb)
        self._cl.insertWidget(self._cl.count()-1, self._sb)
        sys_prompt = _build_system_prompt(self.current_data, b)
        max_t = max(512, self._cfg.get('num_ctx', 8192) - 2000)
        trimmed = _trim_history(list(self._history), max_t)
        self._worker = StreamWorker(b, trimmed, sys_prompt, self._cfg, [])
        self._worker.token_received.connect(self._on_tok)
        self._worker.stats_update.connect(self._on_stats)
        self._worker.stream_done.connect(self._on_done)
        self._worker.error_occurred.connect(self._on_err)
        self._worker.start()

    def _on_err(self, err):
        # An error during the optional interpretation pass should fail quietly —
        # the computed results are already on screen.
        if self._interpreting:
            self._interpreting = False
            self._think.setVisible(False); self._stop.setVisible(False)
            self._sendb.setVisible(True); self._speed.setVisible(False)
            if self._sb: self._sb.finalise(); self._sb = None
            self._enable()
            return
        if self._user_stopped:
            self._user_stopped = False
            return
        self._think.setVisible(False); self._stop.setVisible(False)
        self._sendb.setVisible(True); self._speed.setVisible(False)
        if self._sb: self._sb.finalise(); self._sb = None
        if self._history and self._history[-1]['role'] == 'user': self._history.pop()
        self._add_ai(f"**Error:** {err}"); self._enable()

    def _enable(self):
        self._input.setEnabled(True); self._sendb.setVisible(True)
        self._stop.setVisible(False); self._attach_btn.setEnabled(True)
        self._set_sidebar_enabled(True)
        self._input.setFocus()

    def _do_stop(self):
        if not self._worker: return
        self._user_stopped = True
        self._interpreting = False
        try: self._worker.stop()
        except Exception:
            _itk_log.exception("Handled exception in _do_stop")
        self._think.setVisible(False); self._stop.setVisible(False)
        self._sendb.setVisible(True); self._speed.setVisible(False)
        if self._sb:
            try:
                self._sb._raw = (self._sb._raw or "").rstrip() + "\n\n*[Stopped]*"
                self._sb.finalise()
            except Exception:
                _itk_log.exception("Handled exception in _do_stop")
            self._sb = None
        try:
            self._worker.token_received.disconnect()
            self._worker.stats_update.disconnect()
            self._worker.stream_done.disconnect()
            self._worker.error_occurred.disconnect()
        except Exception:
            _itk_log.exception("Handled exception in _do_stop")
        self._worker = None
        if getattr(self, '_exp_mode', False):
            if getattr(self, '_exp_session', None):
                self._exp_session.mark_cancelled("stopped by user")
            self._teardown_exploration()
        self._enable()

    # ── Agentic exploration ──────────────────────────────────────────────────

    def _explore(self):
        """Start an agentic exploration session: model writes one query per
        turn, sandbox executes, result fed back, until DONE or max_turns hit.
        Then ask the model for a final summary."""
        if not self.current_data:
            self._add_ai("⚠ Connect a data source first — exploration needs particle data.")
            return
        particles = self.current_data.get('particle_data', [])
        if not particles:
            self._add_ai("⚠ No particles loaded — nothing to explore.")
            return
        b = self._cfg.get('backend', '')
        if not b or (b == 'ollama' and not self._cfg.get('model')) or \
           (b == 'custom' and not self._cfg.get('custom_base_url')):
            self._open_settings(); return
        if self._worker:
            return   

        question = self._input.text().strip() or \
            "Scan the dataset for anomalies, outliers, and unusual patterns. " \
            "Compare samples if multiple are present."
        self._input.clear()

        # ── Exploration session state ────────────────────────────────────
        self._exp_mode      = True
        self._exp_question  = question
        self._exp_turn      = 0
        self._exp_max_turns = int(self._cfg.get('explore_max_turns', 10))
        self._exp_messages  = [{
            "role": "user",
            "content": (f"USER QUESTION: {question}\n\n"
                        f"Begin exploration. Write a brief rationale (1-2 lines) "
                        f"followed by ONE Python code block.")
        }]
        self._exp_sys = _build_exploration_prompt(self.current_data, self._exp_max_turns)
        self._user_stopped = False

        # ── UI setup ─────────────────────────────────────────────────────
        self._maybe_set_conv_title(f"Explore: {question}")
        self._add_user(f"**Explore:** {question}")
        self._exp_session = ExplorationBubble(question)
        self._exp_session.set_progress(0, self._exp_max_turns, "Preparing exploration…")
        self._widgets.append(self._exp_session)
        self._cl.insertWidget(self._cl.count()-1, self._exp_session)
        self._scrollb()

        self._set_sidebar_enabled(False)
        self._input.setEnabled(False); self._sendb.setVisible(False)
        self._stop.setVisible(True);  self._attach_btn.setEnabled(False)
        if getattr(self, '_explore_btn', None):
            self._explore_btn.setEnabled(False)
        self._think.setVisible(True); self._tlbl.setText("Exploring…")

        self._run_exploration_turn()

    def _run_exploration_turn(self):
        """Spawn a streaming worker for one exploration turn."""
        if self._user_stopped or not getattr(self, '_exp_mode', False):
            return
        if self._exp_turn >= self._exp_max_turns:
            self._finalize_exploration(reason="turn limit reached")
            return
        self._exp_turn += 1
        self._exp_session.set_progress(
            self._exp_turn, self._exp_max_turns,
            f"Turn {self._exp_turn}: model is choosing what to investigate…")
        self._tlbl.setText(f"Exploring — turn {self._exp_turn}/{self._exp_max_turns}…")

        b = self._cfg.get('backend', '')
        max_t   = max(512, self._cfg.get('num_ctx', 8192) - 2000)
        trimmed = _trim_history(list(self._exp_messages), max_t)
        self._exp_buf = []
        self._worker = StreamWorker(b, trimmed, self._exp_sys, self._cfg, [])
        self._worker.token_received.connect(self._on_exp_tok)
        self._worker.stream_done.connect(self._on_exp_turn_done)
        self._worker.error_occurred.connect(self._on_exp_err)
        self._worker.start()

    def _on_exp_tok(self, t):
        if self._user_stopped: return
        self._exp_buf.append(t)

    def _on_exp_turn_done(self, full):
        """One exploration turn's response is complete. Extract the code,
        execute it, store the step, and either continue or finalize."""
        if self._user_stopped or not getattr(self, '_exp_mode', False):
            return

        if re.search(r'EXPLORATION\s+DONE', full, re.IGNORECASE):
            self._exp_messages.append({"role": "assistant", "content": full})
            self._finalize_exploration(reason="model said it was done")
            return

        m = _CODE_RE.search(full)
        rationale = full
        code = None
        if m:
            code = m.group(1).strip()
            before = full[:m.start()].strip()
            rationale = before or "(no rationale provided)"
            rationale = _THINK_RE.sub('', rationale).strip()

        particles = self.current_data.get('particle_data', []) if self.current_data else []
        if code:
            text_out, tables, charts, err = _execute_query_code(
                code, particles, self.current_data)
        else:
            text_out, tables, charts, err = "", [], [], None

        self._exp_session.add_step(
            self._exp_turn, rationale, code or "", text_out, tables, charts, err)
        self._scrollb()

        if not code:
            self._exp_messages.append({"role": "assistant", "content": full})
            self._finalize_exploration(reason="model stopped writing code")
            return

        feedback = _format_exploration_feedback(
            text_out, tables, charts, err,
            self._exp_turn, self._exp_max_turns)
        self._exp_messages.append({"role": "assistant", "content": full})
        self._exp_messages.append({"role": "user", "content": feedback})

        self._worker = None
        QTimer.singleShot(50, self._run_exploration_turn)

    def _on_exp_err(self, err):
        """Stream error during exploration — log it and either retry or stop."""
        if self._user_stopped or not getattr(self, '_exp_mode', False):
            return
        self._exp_session.set_progress(
            self._exp_turn, self._exp_max_turns,
            f"⚠ Error on turn {self._exp_turn}: {err}")
        if self._exp_turn <= 1:
            self._exp_session.mark_cancelled(f"backend error: {err}")
            self._teardown_exploration()
            self._enable()
            return
        self._finalize_exploration(reason=f"error on turn {self._exp_turn}")

    def _finalize_exploration(self, reason=""):
        """Ask the model for a final summary of findings, then display it."""
        if self._user_stopped: return
        if not getattr(self, '_exp_mode', False): return

        self._exp_turn_final = True
        self._exp_session.set_progress(
            self._exp_turn, self._exp_max_turns,
            f"Writing final summary… ({reason})")
        self._tlbl.setText("Writing summary…")

        self._exp_messages.append({
            "role": "user",
            "content": (
                "EXPLORATION PHASE OVER. Write the final findings summary now.\n\n"
                "FORMAT:\n"
                "Use markdown. Start with a short 1-2 sentence headline of the "
                "most important observation. Then list each notable anomaly as a "
                "bullet with: **what** it is, **how many** particles or samples "
                "are affected (with numbers), and **why** it might be worth "
                "investigating. If you found nothing unusual, say so plainly.\n\n"
                "DO NOT write any code in this response. Plain prose only."
            )
        })

        b = self._cfg.get('backend', '')
        max_t   = max(512, self._cfg.get('num_ctx', 8192) - 2000)
        trimmed = _trim_history(list(self._exp_messages), max_t)
        self._exp_buf = []
        self._worker = StreamWorker(b, trimmed, self._exp_sys, self._cfg, [])
        self._worker.token_received.connect(self._on_exp_tok)
        self._worker.stream_done.connect(self._on_exp_summary_done)
        self._worker.error_occurred.connect(self._on_exp_summary_err)
        self._worker.start()

    def _on_exp_summary_done(self, full):
        """Display the final summary in the ExplorationBubble."""
        if self._user_stopped: return
        if not getattr(self, '_exp_mode', False): return
        clean = _THINK_RE.sub('', full).strip()
        clean = _CODE_RE.sub('', clean).strip()
        if self._exp_session:
            self._exp_session.set_summary(clean)
        self._history.append({
            "role": "user",
            "content": f"🔍 Exploration: {self._exp_question}"
        })
        self._history.append({
            "role": "assistant",
            "content": f"[Ran {self._exp_turn}-turn exploration]\n\n{clean}"
        })
        self._teardown_exploration()
        self._enable()
        self._scrollb()

    def _on_exp_summary_err(self, err):
        if self._user_stopped: return
        if not getattr(self, '_exp_mode', False): return
        if self._exp_session:
            self._exp_session.mark_cancelled(f"summary failed: {err}")
        self._teardown_exploration()
        self._enable()

    def _teardown_exploration(self):
        """Reset exploration state and re-enable the UI."""
        self._exp_mode      = False
        self._exp_session   = None
        self._exp_messages  = []
        self._exp_buf       = []
        self._worker        = None
        self._think.setVisible(False)
        if getattr(self, '_explore_btn', None):
            self._explore_btn.setEnabled(True)

    # ── Data context ──────────────────────────────────────────────────────────

    def update_data_context(self, data):
        self.current_data = data
        self._code_cache.clear()        # results are dataset-specific
        if data:
            self._update_sug(data)
            dt = data.get('type','')
            if dt == 'sample_data':
                n = len(data.get('particle_data',[]))
                self._add_ai(f"**Data loaded:** {data.get('sample_name','?')} — {n:,} particles.")
            elif dt == 'multiple_sample_data':
                ns = len(data.get('sample_names',[]))
                np_ = len(data.get('particle_data',[]))
                self._add_ai(f"**Multi-sample:** {ns} samples, {np_:,} particles total.")

    # ── Suggestions ───────────────────────────────────────────────────────────

    def _update_sug(self, data):
        for i in reversed(range(self._sug_lo.count())):
            w = self._sug_lo.itemAt(i).widget()
            if w: w.setParent(None)
        b = self._cfg.get('backend','')
        if not b or (b == 'ollama' and not self._cfg.get('model')): return

        if data:
            explore_btn = QPushButton("Explore Data")
            explore_btn.setCursor(QCursor(Qt.PointingHandCursor))
            explore_btn.setToolTip(
                "Run an agentic exploration loop over the full dataset.\n"
                "The model writes queries, sees results, and looks for anomalies\n"
                "across multiple turns. Configure depth in Settings.")
            self._style_explore_btn(explore_btn)
            explore_btn.clicked.connect(self._explore)
            self._sug_lo.addWidget(explore_btn)
            self._explore_btn = explore_btn
        else:
            self._explore_btn = None

        items = (["Element frequency table","Size statistics by element",
                  "Top element combinations","Single-element particles only",
                  "Most abundant element by mass"]
                 if data else ["What can you do?"])
        for s in items:
            btn = QPushButton(s)
            self._style_sug_btn(btn)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda _, t=s: (self._input.setText(t), self._send()))
            self._sug_lo.addWidget(btn)

    def _style_explore_btn(self, btn):
        """Distinctive accent styling for the Explore button."""
        fs = _fs(-2)
        ac = Theme.c('accent'); ac2 = Theme.c('accent_hover')
        btn.setStyleSheet(
            f"QPushButton{{background:{ac};color:white;"
            f"border:1px solid {ac};border-radius:16px;"
            f"padding:5px 14px;font-size:{fs}px;font-weight:600;}}"
            f"QPushButton:hover{{background:{ac2};border-color:{ac2};}}"
            f"QPushButton:disabled{{background:{Theme.c('text_tertiary')};"
            f"color:{Theme.c('bg')};border-color:{Theme.c('text_tertiary')};}}")

    def _style_sug_btn(self, btn):
        fs = _fs(-2)
        btn.setStyleSheet(
            f"QPushButton{{background:{Theme.c('sug_bg')};color:{Theme.c('sug_text')};"
            f"border:1px solid {Theme.c('sug_border')};border-radius:16px;"
            f"padding:5px 14px;font-size:{fs}px;}}"
            f"QPushButton:hover{{background:{Theme.c('sug_hover_bg')};"
            f"border-color:{Theme.c('sug_hover_border')};color:{Theme.c('sug_hover_text')};}}")

    def _update_sug_style(self):
        for i in range(self._sug_lo.count()):
            w = self._sug_lo.itemAt(i).widget()
            if isinstance(w, QPushButton):
                if getattr(self, '_explore_btn', None) is w:
                    self._style_explore_btn(w)
                else:
                    self._style_sug_btn(w)

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _on_global_theme_change(self, name):
        Theme._dark = (name == "dark"); self._apply_theme()

    def _apply_theme(self):
        fs = _fs(); fs2 = _fs(-2); fs3 = _fs(2)
        bg  = Theme.c('bg');   bg2 = Theme.c('bg_secondary')
        fg  = Theme.c('text'); fg2 = Theme.c('text_secondary')
        bd  = Theme.c('border'); ac = Theme.c('accent'); sf = Theme.c('surface')
        self.setStyleSheet(
            f"QDialog{{background:{bg};}}"
            f"QScrollArea{{border:none;background:{bg};}}"
            f"QScrollBar:vertical{{background:{Theme.c('scrollbar_bg')};width:8px;border-radius:4px;}}"
            f"QScrollBar::handle:vertical{{background:{Theme.c('scrollbar_handle')};min-height:30px;border-radius:4px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}")
        if hasattr(self, '_sidebar'):
            self._sidebar.setStyleSheet(
                f"QFrame{{background:{bg2};border-right:1px solid {bd};}}")
            self._new_chat_btn.setStyleSheet(
                f"QPushButton{{background:{sf};color:{fg};border:1px solid {bd};"
                f"border-radius:8px;padding:6px 10px;font-size:{fs2}px;font-weight:600;"
                f"text-align:left;}}"
                f"QPushButton:hover{{background:{Theme.c('surface_hover')};border-color:{ac};}}")
            self._conv_hdr.setStyleSheet(
                f"color:{fg2};font-size:{_fs(-3)}px;font-weight:600;"
                f"text-transform:uppercase;letter-spacing:0.6px;padding-left:6px;"
                f"background:transparent;")
            self._conv_list_w.setStyleSheet(f"QWidget{{background:transparent;}}")
            self._conv_list_sc.setStyleSheet(f"QScrollArea{{background:transparent;}}")
            for it in self._conv_items.values():
                it.apply_theme()
        self._hdr.setStyleSheet(f"QFrame{{background:{bg2};border-bottom:1px solid {bd};}}")
        self._title.setStyleSheet(f"font-size:{fs3}px;font-weight:700;color:{fg};")
        self._speed.setStyleSheet(f"color:{Theme.c('speed_text')};font-size:11px;font-family:monospace;")
        _hdr_btn = (f"QPushButton{{background:{sf};border:1px solid {bd};border-radius:6px;"
                    f"padding:5px 12px;font-size:{fs2}px;color:{fg};}}"
                    f"QPushButton:hover{{background:{Theme.c('surface_hover')};}}")
        self._sbtn.setStyleSheet(_hdr_btn)
        self._cust_btn.setStyleSheet(_hdr_btn)
        self._clear_btn.setStyleSheet(_hdr_btn)
        self._status.setStyleSheet(f"color:{fg2};font-size:{fs2}px;")
        self._sug.setStyleSheet(f"QFrame{{border-bottom:1px solid {Theme.c('border_light')};background:{bg};}}")
        self._think.setStyleSheet(f"QFrame{{background:{bg2};border-top:1px solid {Theme.c('border_light')};}}")
        self._tlbl.setStyleSheet(f"color:{fg2};font-size:{fs2}px;font-style:italic;")
        self._inp_frame.setStyleSheet(f"QFrame{{background:{bg2};border-top:1px solid {bd};}}")
        self._composer.setStyleSheet(
            f"QFrame{{background:{Theme.c('input_bg')};border:1px solid {Theme.c('input_border')};"
            f"border-radius:16px;}}")
        self._counter.setStyleSheet(
            f"color:{Theme.c('text_tertiary')};font-size:{_fs(-3)}px;"
            f"font-family:monospace;padding-right:6px;background:transparent;")
        self._input.setStyleSheet(
            f"QPlainTextEdit{{border:none;background:transparent;color:{fg};"
            f"font-size:{fs}px;padding:6px 4px;}}")
        self._attach_btn.setStyleSheet(
            f"QPushButton{{background:{sf};border:1px solid {bd};border-radius:10px;"
            f"font-size:20px;color:{fg};}}"
            f"QPushButton:hover{{background:{Theme.c('surface_hover')};border-color:{ac};}}")
        _send_ss = (f"QPushButton{{background:{ac};color:white;border:none;border-radius:10px;"
                    f"padding:8px 16px;font-size:{fs2}px;font-weight:600;}}"
                    f"QPushButton:hover{{background:{Theme.c('accent_hover')};}}")
        self._sendb.setStyleSheet(_send_ss)
        self._stop.setStyleSheet(
            f"QPushButton{{background:{Theme.c('stop_bg')};color:white;border:none;"
            f"border-radius:10px;font-size:{fs2}px;font-weight:600;}}"
            f"QPushButton:hover{{background:{Theme.c('stop_hover')};}}")
        for w in self._widgets:
            if hasattr(w, 'apply_theme'): w.apply_theme()
        for p in getattr(self, '_previews', []):
            p.apply_theme()
        if hasattr(self, '_resize_handle'):
            self._resize_handle.apply_theme()
            self._resize_handle.update()
        self._update_sug_style()

    # ── Bubble helpers ────────────────────────────────────────────────────────

    def _add_user(self, t):
        b = TextBubble(t, True); self._widgets.append(b)
        self._cl.insertWidget(self._cl.count()-1, b); self._scrollb()

    def _add_ai(self, t):
        b = TextBubble(t, False); self._widgets.append(b)
        self._cl.insertWidget(self._cl.count()-1, b); self._scrollb()

    def _scrollb(self):
        QTimer.singleShot(50, lambda:
            self._scroll.verticalScrollBar().setValue(
                self._scroll.verticalScrollBar().maximum()))

    # ── Auto-detect a running model server ─────────────────────────────────────

    def _start_autodetect(self):
        """Probe localhost for a running model server and self-configure, so the
        user can start chatting without opening settings."""
        try:
            self._probe = ProbeWorker(self._cfg.get('mlx_host', MLX_BASE))
            self._probe.ready.connect(self._on_autodetect)
            self._probe.info.connect(self._on_autodetect_info)
            self._probe.start()
        except Exception:
            _itk_log.exception("Handled exception in _start_autodetect")

    def _on_autodetect(self, backend, model, label):
        # Don't override a model the user already selected this session.
        if self._autoconfigured or self._cfg.get('model'):
            return
        self._autoconfigured = True
        self._cfg['backend'] = backend
        self._cfg['model'] = model
        _itk_log.info("Auto-detected model server: %s", label)
        self._add_ai(f"✓ Connected to {label} — ask a question about your data, "
                     "or click Explore.")

    def _on_autodetect_info(self, msg):
        if not self._autoconfigured:
            self._add_ai(f"ℹ {msg}")


# ── Node ──────────────────────────────────────────────────────────────────────

class AIAssistantNode(QObject):
    position_changed      = Signal(QPointF)
    configuration_changed = Signal()
    DEFAULT_CONFIG = {'backend': 'ollama', 'model': ''}

    def __init__(self, pw=None):
        super().__init__()
        self.title = "AI Data Assistant"; self.node_type = "ai_assistant"
        self.position = QPointF(0, 0); self._has_input = True; self._has_output = False
        self.input_channels = ["input"]; self.output_channels = []
        self.parent_window = pw; self.input_data = None; self.chat_dialog = None
        self.config = dict(self.DEFAULT_CONFIG)

    def set_position(self, p):
        if self.position != p: self.position = p; self.position_changed.emit(p)

    def process_data(self, d):
        self.input_data = d
        if self.chat_dialog and self.chat_dialog.isVisible():
            self.chat_dialog.update_data_context(d)
        self.configuration_changed.emit()

    def get_data_summary(self):
        d = self.input_data
        if not d: return "No data"
        dt = d.get('type', '?')
        if dt == 'sample_data':
            return f"{d.get('sample_name','?')} — {len(d.get('particle_data',[])):,} particles"
        if dt == 'multiple_sample_data':
            return f"{len(d.get('sample_names',[]))} samples — {len(d.get('particle_data',[])):,} particles"
        return dt

    def configure(self, pw):
        if not self.chat_dialog: self.chat_dialog = AIChatDialog(self, pw)
        if self.input_data: self.chat_dialog.update_data_context(self.input_data)
        self.chat_dialog.show(); self.chat_dialog.raise_(); self.chat_dialog.activateWindow()
        return True


def create_ai_assistant_node(pw): return AIAssistantNode(pw)

def show_ai_assistant_dialog(pw, data=None):
    n = AIAssistantNode(pw)
    if data: n.process_data(data)
    AIChatDialog(n, pw).exec()