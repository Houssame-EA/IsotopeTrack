"""What the model is told, and how it all fits in its context window.

The system prompt has three parts: how to answer (write code, then explain
from the results), what the sandbox offers (the particle table, the analysis
functions, free-form matplotlib figures), and a brief of the dataset,
including calibrated detection limits and known interferences.

Local models often run with an 8k-token window, so every prompt is
budgeted: the history gets what is left after the system prompt and a
reserve for the reply, the first message of an exploration (the question)
is never dropped, and small windows get a compact dataset brief.
"""
from __future__ import annotations

import logging
import re

import numpy as np

from results.ai.analysis import SIGNATURES

_itk_log = logging.getLogger("IsotopeTrack.results.ai.prompts")

CHARS_PER_TOKEN = 3.5
COMPACT_BELOW = 12000


def estimate_tokens(text):
    """Rough token count of a text, about 3.5 characters per token.

    Args:
        text (str | list): Text, or OpenAI-style content parts.

    Returns:
        int: Estimated tokens, at least 1.
    """
    if isinstance(text, list):
        text = ' '.join(p.get('text', '') for p in text if isinstance(p, dict))
    return max(1, int(len(text or '') / CHARS_PER_TOKEN) + 4)


def reply_reserve(num_ctx):
    """Tokens kept free for the model's answer.

    Args:
        num_ctx (int): Context window.

    Returns:
        int: Between 768 and 4096 tokens.
    """
    return int(min(4096, max(768, int(num_ctx) // 4)))


def fit_messages(messages, system_text, num_ctx, pinned=0):
    """Keep the messages that fit beside the system prompt and the reply.

    The first *pinned* messages are always kept (shortened if they must be),
    then the most recent messages are added until the budget is used.

    Args:
        messages (list): Chat messages, oldest first.
        system_text (str): The system prompt.
        num_ctx (int): Context window in tokens.
        pinned (int): Leading messages that must survive.

    Returns:
        list: Messages to send, oldest first.
    """
    budget = int(num_ctx) - estimate_tokens(system_text) - reply_reserve(num_ctx) - 64
    budget = max(budget, 256)
    head = [dict(m) for m in messages[:pinned]]
    tail = messages[pinned:]
    used = 0
    for m in head:
        cost = estimate_tokens(m.get('content', ''))
        if used + cost > budget // 2 and isinstance(m.get('content'), str):
            keep = int((budget // 2 - used) * CHARS_PER_TOKEN)
            m['content'] = m['content'][:max(keep, 200)] + "\n[... shortened to fit]"
            cost = estimate_tokens(m['content'])
        used += cost
    kept = []
    for m in reversed(tail):
        cost = estimate_tokens(m.get('content', ''))
        if used + cost > budget:
            if not kept and isinstance(m.get('content'), str):
                keep = int((budget - used) * CHARS_PER_TOKEN)
                m = dict(m)
                m['content'] = "[... start shortened to fit]\n" + m['content'][-max(keep, 200):]
                kept.append(m)
            break
        kept.append(m)
        used += cost
    return head + list(reversed(kept))


def _fmt(v, digits=3):
    """Short number for the brief."""
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return '—'
    v = float(v)
    if v == 0:
        return '0'
    if abs(v) >= 1000 or abs(v) < 0.01:
        return f"{v:.{digits - 1}e}"
    return f"{v:.{digits}g}"


def _interference_notes(elements, limit=12):
    """Masses with major or critical documented spectral interferences."""
    try:
        from widget.interference_database import get_interferences_for_mass, get_worst_severity
    except Exception:
        return []
    notes = []
    for el in elements:
        m = re.match(r'(\d+)', str(el))
        if not m:
            continue
        try:
            ints = get_interferences_for_mass(int(m.group(1)))
        except Exception:
            continue
        if not ints:
            continue
        sev = get_worst_severity(ints)
        if sev in ('critical', 'major'):
            species = ', '.join(str(i.get('species', '?')) for i in ints[:3])
            notes.append(f"  {el:<8} {sev:<9} possible: {species}")
        if len(notes) >= limit:
            break
    return notes


def dataset_brief(ds, compact=False, mass_basis='element'):
    """Describe the dataset for the system prompt.

    Args:
        ds (Dataset): The dataset.
        compact (bool): Shorter brief for small context windows.
        mass_basis (str): Which mass and size to list, ``element`` or ``particle``.

    Returns:
        str: The brief.
    """
    if ds is None or not len(ds):
        return "DATASET\nNo particle data is connected yet. Ask the user to connect a sample to the AI node."
    df = ds.df
    n = len(df)
    lines = ["DATASET"]
    if ds.kind == 'sample_data':
        tp = ds.data_context.get('total_particles', n)
        lines.append(f"Sample: {ds.default_sample}; {n:,} particles" + (f" (filtered from {tp:,})" if tp and tp != n else ''))
    by_sample = df['sample'].value_counts()
    runs = ds.runs().set_index('run')
    if ds.kind != 'sample_data' or len(by_sample) > 1:
        lines.append(f"{len(by_sample)} samples, {n:,} particles:")
        for s in ds.samples[: (8 if compact else 30)]:
            span = runs['span_s'].get(s)
            extra = f", ~{span:.0f} s acquired" if span is not None and np.isfinite(span) else ''
            lines.append(f"  {s}: {int(by_sample.get(s, 0)):,} particles{extra}")
        if len(ds.samples) > (8 if compact else 30):
            lines.append(f"  ... and {len(ds.samples) - (8 if compact else 30)} more")
    if df['run'].nunique() != df['sample'].nunique():
        lines.append(f"Samples pool {df['run'].nunique()} acquisitions; column 'run' holds the original one.")
    multi = int((df['n_elements'] > 1).sum())
    lines.append(f"Multi-element particles: {multi:,} ({100.0 * multi / max(n, 1):.1f}%). "
                 f"Median event width {np.nanmedian(df['duration_ms']):.3g} ms.")
    if 'class' in df.columns:
        vc = df['class'].value_counts().head(8)
        lines.append("Particle classes: " + ', '.join(f"{k} ({v:,})" for k, v in vc.items()))
    els = ds.elements[: (12 if compact else 40)]
    lim = ds.limits()
    lines.append("")
    pre = 'particle_' if mass_basis == 'particle' else ''
    kind = 'particle values, compound-corrected' if pre else 'element values'
    lines.append(f"Elements (n, % of particles; {kind}: median mass fg, LOD mass fg, "
                 "median diameter nm, LOD diameter nm):")
    for el in els:
        m = df.get(f'{pre}mass_fg_{el}')
        d = df.get(f'{pre}diameter_nm_{el}')
        cnt = int(df[f'counts_{el}'].notna().sum()) if f'counts_{el}' in df else 0
        mmed = float(np.nanmedian(m)) if m is not None and m.notna().any() else None
        dmed = float(np.nanmedian(d)) if d is not None and d.notna().any() else None
        lm = max((lim.get(el, {}).get(f'{pre}mass_fg') or {0: None}).values(), default=None, key=lambda x: x or 0)
        ld = max((lim.get(el, {}).get(f'{pre}diameter_nm') or {0: None}).values(), default=None, key=lambda x: x or 0)
        lines.append(f"  {el:<7} {cnt:>7,} {100.0 * cnt / max(n, 1):5.1f}%  m={_fmt(mmed)}  LODm={_fmt(lm)}  "
                     f"d={_fmt(dmed)}  LODd={_fmt(ld)}")
    if len(ds.elements) > len(els):
        lines.append(f"  ... {len(ds.elements) - len(els)} rarer elements: {', '.join(ds.elements[len(els):][:20])}")
    combos = df.loc[df['n_elements'] > 1, 'combo'].value_counts().head(6 if compact else 12)
    if len(combos):
        lines.append("")
        lines.append("Most common multi-element combinations:")
        for c, k in combos.items():
            lines.append(f"  {k:6,}  {c}")
    lines.append("")
    if ds.concentrations_available():
        lines.append("Concentrations: available — per_ml_factor[sample] converts a particle count to particles/mL.")
    elif ds.acquisition is not None:
        lines.append("Concentrations: per_ml_factor is empty; take particles/mL from sample_summary().")
    else:
        lines.append("Concentrations: NOT available — do not report particles/mL.")
    if not lim:
        lines.append("Detection limits: not available (no calibration connected).")
    acq = ds.acquisition
    if acq is not None:
        runs = acq.run_names()
        shown = ', '.join(runs[: (6 if compact else 20)]) + (' ...' if len(runs) > (6 if compact else 20) else '')
        lines.append(f"Raw signal and per-sample results: available for {len(runs)} runs ({shown}).")
    else:
        lines.append("Raw signal and per-sample results: NOT available — do not call signal() or sample_summary().")
    notes = _interference_notes(ds.elements[:20], 6 if compact else 12)
    if notes:
        lines.append("Known spectral interferences — caveat findings that depend on these masses:")
        lines.extend(notes)
    return '\n'.join(lines)


_ROLE = """You are the data analyst inside IsotopeTrack, working on single-particle ICP-ToF-MS (spICP-ToF-MS) data. You answer by writing Python that runs on the user's full dataset; the user sees the tables and figures it produces, and you then explain what came out."""

_HOW = """HOW TO ANSWER
- For any question about the data: one short line saying what you will compute, then ONE ```python block. It runs at once on all particles. You will then be shown the exact results and asked for the takeaway, so do not state any numbers before that.
- Present results the way a good paper would. When a result is a distribution, a comparison between samples, a relationship, a composition or a change over time, draw a figure designed for that result in the same code block, and keep tables short (the key rows and columns) for the exact numbers.
- For questions about concepts or methods (not this data), answer in plain text without code.
- Report what the data shows. Do not name phases, sources or origins unless the user asks you to interpret.
- If a request is ambiguous, pick the most sensible reading and say which one you used."""

_DATA = """THE SANDBOX
df: pandas DataFrame, one row per particle. Columns:
  sample, run, t_start, t_end (s), duration_ms, n_elements, combo (e.g. '48Ti + 56Fe'), total_mass_fg{class_col}
  per element <el>: counts_<el>, mass_fg_<el>, moles_fmol_<el>, diameter_nm_<el>, mass_pct_<el>, mole_pct_<el>,
                    particle_mass_fg_<el>, particle_diameter_nm_<el> (compound-corrected)
  NaN means the element was not detected in that particle: df['particle_mass_fg_48Ti'].dropna()
{quantity_rule}
elements: labels, most frequent first (e.g. '56Fe'); samples: sample names; runs: acquisition spans
col('size', 'Ti') -> 'diameter_nm_48Ti' (accepts symbols and aliases); element('Fe') -> '56Fe'
lod('Ti', 'mass_fg', sample=None) -> calibrated detection limit on the same scale as that column, or None
np, pd, math, stats (scipy.stats), Counter are loaded. No imports, no file access."""

_ACQUISITION = """RAW SIGNAL AND PER-SAMPLE RESULTS (from the main window, same numbers as the summary export)
sample_summary() -> DataFrame, one row per run and element. Columns:
  sample (after pooling), run (original acquisition), element ('56Fe')
  particles, particles_per_ml (in the measured solution), particles_per_ml_corrected (x dilution, the original sample)
  mean_mass_fg, median_mass_fg, total_mass_fg, mean_diameter_nm, mass_conc_ug_l (element only)
  particle_mean_mass_fg, particle_median_mass_fg, particle_total_mass_fg, particle_mean_diameter_nm,
  particle_mass_conc_ug_l (compound-corrected), mass_fraction (1 = pure element)
  every *_ug_l is the particulate mass concentration, dilution-corrected
  mean_signal_counts, signal_sd_counts, signal_rsd_pct, mean_signal_ppb (whole trace: dissolved + particles)
  background_counts, background_ppt, background_sd_ppt (dissolved / ionic background)
  threshold_counts (detection threshold), lod_net_counts, mdl_fg, mql_fg, sdl_nm, sql_nm
  slope_cps_per_ppb, calibration_method, transport_rate_ul_s, dwell_ms, acquisition_s, volume_ml, dilution
  NaN means the value is not calibrated; never replace it with 0.
signal(run, 'Fe', t0=None, t1=None) -> DataFrame time_s, counts: the raw trace of one run, one point per dwell time.
  Pass a run name (sample_summary()['run']); a pooled sample works only when it holds one run.
  Traces are long: plot with ax.plot(..., lw=0.5) and slice with t0/t1 to zoom in."""

_OUTPUT = """SHOWING RESULTS
show_table(dataframe_or_dict, title='...')  interactive table; pass analysis results straight in
print(...)  only for short text"""

_FIGURES = """FIGURES — you design and draw them yourself with matplotlib; there are no templates
  fig, ax = plt.subplots(nrows, ncols, figsize=(w, h))   or   fig, ax = new_figure(nrows, ncols, size=(w, h))
Choose the form that shows the result best, for example:
  sizes or masses by sample -> overlaid log-binned step histograms, or box/violin plots on a log axis
  one quantity against another -> scatter on log-log axes, small markers, alpha for dense clouds, one colour per sample
  composition of particle types -> horizontal stacked bars of percentages, sorted
  pair or sample statistics -> heatmap (ax.imshow with a colour bar) with annotated cells
  arrival over time -> time series of counts per bin, bursts shaded with ax.axvspan
  many samples -> small multiples sharing axes rather than one crowded panel
Make it look professional:
- one message per figure; descriptive axis labels with units; a short title on the panel OR a figure title, not both on a single-panel figure
- masses and sizes are close to log-normal: log axes and np.logspace bins unless asked otherwise
- the same colour for the same sample in every panel, from PALETTE (colour-blind safe); at most about 8 legend entries
- mark detection limits with ax.axvline(lod(element, quantity), ls='--', color='0.4') using the plotted quantity; annotate key numbers on the plot when it helps
- never call df.plot(), plt.show(), savefig or tight_layout; the layout is handled for you
- to change a figure the user already has, rewrite its full code with the change"""

_DOMAIN = """SPICP-TOF-MS
- One event is one particle passing the plasma. Elements in one event are in one particle, or two particles arrived together by chance: check multi-element claims with coincidence(a, b) or co_occurrence().
- Near the detection limit, distributions are truncated and medians are biased high; size_distribution() flags this.
- Treat detections with n < 10 with caution."""

_EXAMPLE = """EXAMPLE
User: is Ti bigger in some samples?
Comparing Ti masses across samples, with tests and a log-scale histogram.
```python
res = compare_samples('Ti', '{mq}')
show_table(res, title='Ti {mname} by sample')
fig, ax = plt.subplots(figsize=(6.5, 4))
c = col('{mq}', 'Ti')
v = df[c].dropna()
bins = np.logspace(np.log10(v.min()), np.log10(v.max()), 60)
for s in samples:
    ax.hist(df.loc[df['sample'] == s, c].dropna(), bins=bins, histtype='step', lw=1.5, label=s)
m = lod('Ti', '{mq}')
if m:
    ax.axvline(m, ls='--', color='grey', label='LOD')
ax.set_xscale('log'); ax.set_xlabel('Ti {mname} (fg)'); ax.set_ylabel('Particles'); ax.legend()
```"""


MASS_BASES = ('element', 'particle')


def quantity_rule(mass_basis='element'):
    """The rule telling the model which mass and size to use.

    Args:
        mass_basis (str): ``element`` for the measured element mass, or
            ``particle`` for the compound-corrected particle mass.

    Returns:
        str: The rule text.
    """
    if mass_basis == 'particle':
        default, other = 'particle (compound-corrected)', 'element'
        cols, other_cols = 'particle_mass_fg_<el> and particle_diameter_nm_<el>', 'mass_fg_<el> and diameter_nm_<el>'
        ask = "the element mass or size ('element mass', 'only Ti', 'without the compound')"
    else:
        default, other = 'element', 'particle (compound-corrected)'
        cols, other_cols = 'mass_fg_<el> and diameter_nm_<el>', 'particle_mass_fg_<el> and particle_diameter_nm_<el>'
        ask = "the particle or compound-corrected mass or size ('particle mass', 'corrected', 'as TiO2')"
    return (
        "WHICH QUANTITY — follow this every time:\n"
        "  - Mass first. Unless the user asks for size or diameter, analyse and plot mass.\n"
        f"  - Use the {default} values by default: {cols}.\n"
        f"  - Use the {other} values ({other_cols}) only when the user asks for {ask}.\n"
        "    Without a compound set, both are the same.\n"
        "  - If the user asks to switch (e.g. 'use the particle mass from now on'), keep the new choice for the\n"
        "    rest of the conversation until they switch back.\n"
        "  - In sample_summary() the same rule picks between the plain columns and the particle_ ones.\n"
        "  - Say in the axis label which one you used, e.g. 'Ti mass (fg)' or 'Ti particle mass (fg)'.")


def _example(mass_basis='element'):
    """The worked example, using the default mass."""
    mq = 'particle_mass_fg' if mass_basis == 'particle' else 'mass_fg'
    mname = 'particle mass' if mass_basis == 'particle' else 'mass'
    return _EXAMPLE.replace('{mq}', mq).replace('{mname}', mname)


def _functions_block(compact=False):
    """The analysis function reference."""
    lines = ["ANALYSIS FUNCTIONS — prefer these to hand-written statistics; each returns a DataFrame (test results in .attrs['note'])"]
    for sig, what in SIGNATURES:
        lines.append(f"  {sig}" if compact else f"  {sig}\n      {what}")
    return '\n'.join(lines)


def build_system_prompt(ds, num_ctx=8192, mode='chat', max_turns=10, mass_basis='element'):
    """Assemble the system prompt.

    Args:
        ds (Dataset): The dataset, or ``None``.
        num_ctx (int): Context window; small windows get a compact prompt.
        mode (str): ``chat`` or ``explore``.
        max_turns (int): Exploration turn budget.
        mass_basis (str): Default mass, ``element`` or ``particle``.

    Returns:
        str: The system prompt.
    """
    compact = int(num_ctx) < COMPACT_BELOW
    class_col = ', class' if ds is not None and len(ds) and 'class' in ds.df.columns else ''
    parts = [_ROLE, _HOW, _DATA.replace('{class_col}', class_col).replace('{quantity_rule}', quantity_rule(mass_basis))]
    if ds is not None and ds.acquisition is not None:
        parts.append(_ACQUISITION)
    parts += [_functions_block(compact), _OUTPUT, _FIGURES, _DOMAIN]
    if not compact:
        parts.append(_example(mass_basis))
    if mode == 'explore':
        parts.append(exploration_rules(max_turns))
    parts.append(dataset_brief(ds, compact, mass_basis))
    return '\n\n'.join(parts)


def exploration_rules(max_turns):
    """Instructions for the multi-turn exploration.

    Args:
        max_turns (int): Turn budget.

    Returns:
        str: The rules section.
    """
    return f"""EXPLORATION MODE — you have up to {max_turns} turns
- Turn 1: start with a line "PLAN:" followed by 3 to 6 numbered hypotheses worth testing for the user's question (for example: differences between samples, real associations versus chance coincidence, truncation at the detection limit, outliers, time bursts, enriched combinations). Then ONE python block testing the first.
- Every later turn: one line naming the hypothesis you test, then ONE python block under 50 lines.
- Show the evidence for each hypothesis as a figure you design for it, plus a short table of the key numbers.
- In the code, call record_finding(claim, n=..., p=..., effect=...) whenever a result supports or rejects a hypothesis. Write the claim in plain words with its key numbers, and record negative results too.
- After each turn you see the results and the findings so far. Do not repeat a test you already ran.
- When the plan is covered or nothing new appears, reply with the line EXPLORATION DONE and no code."""


def first_exploration_message(question):
    """The pinned opening message of an exploration.

    Args:
        question (str): The user's question.

    Returns:
        str: Message text.
    """
    return (f"USER QUESTION: {question}\n\n"
            "Begin: write PLAN: with your numbered hypotheses, then ONE python block testing the first.")


def turn_feedback(digest, turn, max_turns, ledger_text, plan_text=''):
    """The message returned to the model after an exploration turn.

    Args:
        digest (str): Compact results of the turn.
        turn (int): Turn just run.
        max_turns (int): Turn budget.
        ledger_text (str): Findings recorded so far.
        plan_text (str): The model's plan, repeated so it is never lost.

    Returns:
        str: Message text.
    """
    left = max_turns - turn
    parts = [f"[TURN {turn} RESULT — {left} turn{'s' if left != 1 else ''} left]", digest]
    if plan_text:
        parts.append("YOUR PLAN:\n" + plan_text)
    parts.append("FINDINGS SO FAR:\n" + (ledger_text or "(none recorded yet — use record_finding)"))
    if left <= 0:
        parts.append("No turns left. Reply EXPLORATION DONE.")
    else:
        parts.append("Next: one line naming the hypothesis, then ONE python block — or EXPLORATION DONE.")
    return '\n\n'.join(parts)


def summary_request(ledger_text, question):
    """Ask for the final exploration summary, written only from the findings.

    Args:
        ledger_text (str): The findings ledger.
        question (str): The user's question.

    Returns:
        str: Message text.
    """
    return f"""EXPLORATION OVER. Write the final summary for: {question}

Use ONLY the findings below and the results you were shown; introduce no new numbers.

FINDINGS:
{ledger_text or '(no findings were recorded)'}

Format in markdown:
- One or two sentence headline with the most important result.
- "**Supported**": one bullet per supported finding: what, how many particles or samples, the test result (p or effect), why it matters.
- "**Not supported**": hypotheses the data did not back.
- "**Caveats**": detection-limit truncation, coincidence, interferences or small numbers that affect the reading, only if they apply.
No code."""


def interpretation_request(results_text):
    """Ask for a short, grounded takeaway after code ran.

    Args:
        results_text (str): Compact results.

    Returns:
        str: Message text.
    """
    return ("Here are the EXACT results your code just produced:\n\n"
            f"{results_text}\n\n"
            "Give the user the takeaway in 1 to 4 sentences. Use only numbers shown above, "
            "mention test results when there are any, and point out a caveat from the notes if one applies. "
            "If a figure has a problem listed under FIGURE CHECKS, say so briefly. Do not write code.")


def correction_request(error, digest=''):
    """Ask the model to fix code that failed.

    Args:
        error (str): The error.
        digest (str): Any partial output.

    Returns:
        str: Message text.
    """
    msg = ("[SANDBOX ERROR] Your code failed:\n"
           f"{error}\n\n"
           "Rewrite the whole code block with the fix. Reminders:\n"
           "- No imports; np, pd, math, stats, plt are loaded.\n"
           "- Element labels look like '56Fe'; use col('mass', 'Fe') or element('Fe') when unsure, and check df.columns.\n"
           "- NaN means not detected: use .dropna() before statistics.\n"
           "- Draw figures with plt.subplots / new_figure and the axes methods; no savefig, no df.plot().\n"
           "- No file access, no attributes starting with an underscore.")
    if digest:
        msg += "\n\nOutput before the error:\n" + digest
    return msg


def figure_fix_request(warnings):
    """Ask the model to fix a figure that drew but has problems.

    Args:
        warnings (list): Figure check messages.

    Returns:
        str: Message text.
    """
    return ("[FIGURE CHECK] The figure was drawn but has problems:\n"
            + "\n".join(f"- {w}" for w in warnings)
            + "\n\nRewrite the full code with these fixed.")


def suggest_questions(ds, limit=5):
    """Starter questions built from what is actually in the data.

    Args:
        ds (Dataset): The dataset.
        limit (int): Most questions to return.

    Returns:
        list: ``(label, question)`` pairs; the short label goes on the chip,
        the question is what gets sent.
    """
    if ds is None or not len(ds):
        return [("What can you do?", "What can you do?")]
    df = ds.df
    els = ds.elements
    out = []
    multi_sample = df['sample'].nunique() > 1
    top = re.sub(r'^\d+', '', els[0]) if els else ''
    if top and multi_sample:
        out.append((f"{top} size by sample",
                    f"Compare {top} particle size across samples, with tests and a log-scale histogram"))
    combos = df.loc[df['n_elements'] == 2, 'combo'].value_counts()
    if len(combos):
        pair = [re.sub(r'^\d+', '', x) for x in combos.index[0].split(' + ')]
        out.append((f"{pair[0]}+{pair[1]}: real or chance?",
                    f"Are {pair[0]}+{pair[1]} particles real associations or chance coincidences?"))
    if ds.limits():
        out.append(("Near detection limit?",
                    "Which elements are close to the detection limit, and are their size distributions truncated?"))
    if multi_sample:
        out.append(("Enriched combinations",
                    "Which element combinations are over- or under-represented in each sample?"))
    out.append(("Bursts over time?", "Are there contamination bursts or spikes over time in any run?"))
    if top:
        out.append((f"{top} mass vs size plot",
                    f"Plot {top} mass versus diameter on log axes, coloured by sample"))
    out.append(("Element table", "Element frequency and size table"))
    return out[:limit]
