"""Score a model on questions with known answers.

The assistant can only be improved if "better" is measured. This module
generates synthetic datasets whose truth is known (see
:mod:`results.ai.synthetic`), asks a model a fixed set of questions through
the same pipeline the chat window uses (code, sandbox, correction, grounded
takeaway) and checks every answer automatically.

The question set is built from 36 templates (counts, statistics, yes/no
reasoning and figures) asked on three datasets with different samples,
sizes, a contamination burst and an alloy population planted in different
places. Datasets ``rivers`` and ``wastewater`` form the ``dev`` split;
``lakes`` is the ``test`` split and should never be used to make training
examples, so a model trained on the others is still measured on data it has
not seen.

Figures are checked on what was actually drawn: axis scales, number of
panels, series, points or bars, axis labels and titles where asked for,
reference lines, colour maps, and the drawing warnings the chat shows the
model (empty panels, missing axis labels, overlapping text).

On top of those, each dataset has:

- ``custom``: single requests for detailed figure customisation (a second
  y-axis, points above a threshold in another colour, a colour scale for a
  third quantity, error bars, axis range and grid, a fixed colour for one
  sample, an annotation with an arrow, marker shape and legend placement);
- ``table``: one table covering every element in every sample, checked
  value by value;
- ``edit``: conversations of three requests where each one changes the
  previous figure; every step must keep what was asked before and add the
  new change, which tests whether the model edits its own code instead of
  starting over;
- ``explore``: open and targeted explorations run through the same loop as
  the Explore button, scored on how many of the planted features the
  summary reports (the Ce:La ratio shift, the non-natural Pb isotope ratio,
  the Ag+Au alloy sample, the sample with larger Ti, the Fe burst for the
  iron question) and failed on a false discovery (Ti+Fe called a real
  association).

Every question goes through the same steps as the chat window: up to three
code corrections, one figure redraw when the drawing checks complain, and
the grounded takeaway, with the history kept the way the chat keeps it.

Run it from the repository root against a local model::

    python -m results.ai.benchmark --backend ollama --model qwen3.8:27b-mlx
    python -m results.ai.benchmark --backend mlx --host http://127.0.0.1:8080
    python -m results.ai.benchmark --reference

Thinking is off by default, as in the app; ``--think`` switches it on.

``--reference`` answers with the built-in reference code instead of a model,
which checks the benchmark itself. ``--split``, ``--dataset``, ``--category``
and ``--only`` select part of the set. Results print per question with a
summary per category and split, and can be saved as JSON with ``--out``.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd
from matplotlib.colors import LogNorm, to_rgba_array

from results.ai.data import Dataset
from results.ai.exploration import (
    ExplorationState, compact_messages, first_look, is_done, parse_plan, repeat_request,
)
from results.ai.figures import axes_title
from results.ai.prompts import (
    build_system_prompt, code_first_request, correction_request, explore_fix_request, figure_fix_request,
    empty_reply_request, first_exploration_message, fit_messages, interpretation_request, is_empty_reply,
    needs_code, reply_reserve, summary_request, turn_feedback,
)
from results.ai.sandbox import execute, floats_in_text, result_digest
from results.ai.synthetic import (
    DENSITY, LOD_MASS_FG, SENSITIVITY, Truth, _diameter_nm, _events, _merge, _particle, make_dataset,
    planted_defaults,
)
from results.ai.theme import CODE_RE, cut_after_code, strip_thinking

ISOTOPES = {'Ti': '48Ti', 'Fe': '56Fe', 'Ce': '140Ce', 'La': '139La',
            'Ag': '107Ag', 'Au': '197Au', 'Al': '27Al'}
QUALITY_WARNINGS = ('is empty', 'overlap', 'has no x-axis label', 'has no y-axis label')
MAX_FIX_ATTEMPTS = 3
MAX_FIGURE_FIXES = 1
EXEC_TIMEOUT_S = 300
CATEGORIES = ['count', 'stats', 'reasoning', 'figure', 'custom', 'table', 'edit', 'explore']

DATASETS = {
    'rivers': {'split': 'dev', 'seed': 11, 'builtin': True},
    'wastewater': {
        'split': 'dev', 'seed': 23,
        'samples': ['Influent_Day1', 'Effluent_Day1', 'Influent_Day2', 'Effluent_Day2'],
        'ti_median_nm': {'Influent_Day1': 85.0, 'Effluent_Day1': 58.0,
                         'Influent_Day2': 92.0, 'Effluent_Day2': 55.0},
        'burst': ('Effluent_Day2', 35.0, 37.0), 'alloy_sample': 'Influent_Day1',
    },
    'lakes': {
        'split': 'test', 'seed': 37,
        'samples': ['Lake_North', 'Lake_South', 'Lake_East', 'Lake_West', 'Lake_Centre'],
        'ti_median_nm': {'Lake_North': 66.0, 'Lake_South': 50.0, 'Lake_East': 72.0,
                         'Lake_West': 52.0, 'Lake_Centre': 110.0},
        'burst': ('Lake_East', 41.0, 43.0), 'alloy_sample': 'Lake_South',
    },
}


def make_variant(name):
    """Generate one of the benchmark datasets.

    Args:
        name (str): Key of :data:`DATASETS`.

    Returns:
        tuple: ``(data_context, truth, limits)`` as returned by
        :func:`results.ai.synthetic.make_dataset`.
    """
    spec = DATASETS[name]
    if spec.get('builtin'):
        return make_dataset(spec['seed'])
    return build_variant(spec)


def build_variant(spec):
    """Generate a dataset from a specification.

    Args:
        spec (dict): ``seed``, ``samples``, ``ti_median_nm``, ``burst``,
            ``alloy_sample`` and optionally ``scale`` (arrival-rate factor),
            ``cela_shift_sample`` and ``pb_sample`` (chosen by
            :func:`results.ai.synthetic.planted_defaults` otherwise).

    Returns:
        tuple: ``(data_context, truth, limits)``.
    """
    rng = np.random.default_rng(spec['seed'])
    shift, pb = planted_defaults(list(spec['samples']), spec['alloy_sample'])
    truth = Truth(samples=list(spec['samples']), span_s=60.0,
                  ti_median_nm=dict(spec['ti_median_nm']), burst=tuple(spec['burst']),
                  alloy_sample=spec['alloy_sample'], lod_mass_fg=dict(LOD_MASS_FG),
                  cela_shift_sample=spec.get('cela_shift_sample', shift), pb_sample=spec.get('pb_sample', pb))
    scale = float(spec.get('scale', 1.0))
    particles = []
    for sample in truth.samples:
        for t0, t1, comp in _merge(_events(rng, sample, truth, scale)):
            p = _particle(sample, t0, t1, comp, rng, truth.lod_mass_fg)
            if p is not None:
                particles.append(p)
    dc = {'type': 'multiple_sample_data', 'sample_names': list(truth.samples),
          'particle_data': particles,
          'concentration_meta': {s: {'volume_ml': 0.5, 'dilution_factor': 10.0,
                                     'te_available': True} for s in truth.samples}}
    limits = {}
    for el, lod in truth.lod_mass_fg.items():
        limits[el] = {'mass_fg': {s: lod for s in truth.samples},
                      'diameter_nm': {s: _diameter_nm(lod, DENSITY[el]) for s in truth.samples},
                      'counts': {s: lod * SENSITIVITY[el] for s in truth.samples}}
    return dc, truth, limits


def truth_frame(dc):
    """A plain table of the particles, built without :mod:`results.ai.data`.

    Reference answers come from this table, so a bug in the code the model
    uses cannot make a wrong answer pass.

    Args:
        dc (dict): Synthetic data context.

    Returns:
        pandas.DataFrame: One row per particle with ``sample``, ``t`` and
        ``mass_X``, ``diam_X``, ``pct_X`` columns per element symbol (NaN when
        absent).
    """
    rows = []
    for p in dc['particle_data']:
        row = {'sample': p['source_sample'], 't': p['start_time'],
               'n_el': sum(1 for v in p['elements'].values() if v > 0)}
        for sym, iso in ISOTOPES.items():
            present = float(p['elements'].get(iso, 0) or 0) > 0
            row[f'mass_{sym}'] = p['element_mass_fg'][iso] if present else np.nan
            row[f'diam_{sym}'] = p['element_diameter_nm'][iso] if present else np.nan
            row[f'pct_{sym}'] = p['mass_percentages'][iso] if present else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


@dataclass
class Question:
    """One benchmark question.

    Attributes:
        qid (str): Identifier, ``dataset.template``.
        text (str): The question as a user would ask it.
        kind (str): ``number``, ``text`` or ``figure``.
        expected: Number, regular expression or figure requirement.
        tolerance (float): Relative tolerance for numbers.
        reference (str): Code that answers it correctly, for ``--reference``.
        reject (str): Regular expression that must not match the answer.
        first_of (dict): Name to regular expression; when set, ``expected``
            must be the first of these names the answer mentions.
        reference_answer (str): The takeaway the reference model gives.
        dataset (str): Dataset key.
        split (str): ``dev`` or ``test``.
        category (str): One of :data:`CATEGORIES`.
        steps (list): For ``conversation`` questions, one dict per request
            with ``text``, ``req`` (what the figure must show after that
            request, counting everything asked so far) and ``reference``.
        findings (dict): For ``explore`` questions, name to
            ``(patterns, unless)``: one sentence of the summary must match
            every pattern and not ``unless`` for the feature to count.
        forbidden (dict): Claims that fail an ``explore`` question, in the
            same form as ``findings``.
        need (int): Findings required to pass an ``explore`` question.
        max_turns (int): Exploration turn budget.
    """

    qid: str
    text: str
    kind: str
    expected: object = None
    tolerance: float = 0.01
    reference: str = ''
    reject: str = ''
    first_of: dict = field(default_factory=dict)
    reference_answer: str = ''
    dataset: str = ''
    split: str = ''
    category: str = ''
    steps: list = field(default_factory=list)
    findings: dict = field(default_factory=dict)
    forbidden: dict = field(default_factory=dict)
    need: int = 1
    max_turns: int = 6


def _names(names):
    """Map names to escaped regular expressions for ``first_of``."""
    return {n: re.escape(n) for n in names}


ELEMENT_PATTERNS = {'Ti': r'(?-i:\b(48)?Ti\b)|titanium', 'Fe': r'(?-i:\b(56)?Fe\b)|\biron\b',
                    'Ce': r'(?-i:\b(140)?Ce\b)|cerium', 'La': r'(?-i:\b(139)?La\b)|lanthanum',
                    'Ag': r'(?-i:\b(107)?Ag\b)|silver', 'Au': r'(?-i:\b(197)?Au\b)|\bgold\b',
                    'Al': r'(?-i:\b(27)?Al\b)|alumin', 'Pb': r'(?-i:\b(20[4678])?Pb\b)|lead isotop'}


def _hist_ref(sym, quantity, label):
    """Reference code for one log-binned histogram per sample."""
    return (f"fig, ax = plt.subplots()\n"
            f"v = df[col('{quantity}','{sym}')].dropna()\n"
            f"bins = np.logspace(np.log10(v.min()), np.log10(v.max()), 50)\n"
            f"for s in samples:\n"
            f"    ax.hist(df.loc[df['sample']==s, col('{quantity}','{sym}')].dropna(), bins=bins,"
            f" histtype='step', label=s)\n"
            f"ax.set_xscale('log'); ax.set_xlabel('{label}'); ax.set_ylabel('Particles'); ax.legend()")


AFFIRMED_REAL = (r"(?:^|[.!?:]\s+)(?:(?!\b(?:not|no|rather than|unlikely|neither|nor|instead of)\b|n't)[^.!?])*"
                 r"\breal associations?\b")


def build_questions(name, dc, truth):
    """The question set for one dataset.

    Args:
        name (str): Dataset key.
        dc (dict): The synthetic data context.
        truth (Truth): What was planted.

    Returns:
        list: :class:`Question` objects.
    """
    tf = truth_frame(dc)
    S = list(truth.samples)
    n_s = len(S)
    s0, s1, sl = S[0], S[1], S[-1]
    burst_sample, b0, b1 = truth.burst
    split = DATASETS.get(name, {}).get('split', 'train')
    has = {sym: tf[f'mass_{sym}'].notna() for sym in ISOTOPES}

    ti_med = {s: float(tf.loc[(tf['sample'] == s) & has['Ti'], 'diam_Ti'].median()) for s in S}
    largest_ti = max(ti_med, key=ti_med.get)
    counts = tf['sample'].value_counts()
    most = str(counts.idxmax())
    el_med = {sym: float(tf[f'diam_{sym}'].median()) for sym in ISOTOPES}
    largest_el = max(el_med, key=el_med.get)
    cela = has['Ce'] & has['La']
    agau = has['Ag'] & has['Au']
    no_ce = [s for s in S if not (has['Ce'] & (tf['sample'] == s)).any()]
    span = truth.span_s
    burst_nums = '|'.join(str(k) for k in range(int(math.floor(b0)) - 1, int(math.ceil(b1)) + 2))
    lod_ce_d = _diameter_nm(LOD_MASS_FG['140Ce'], DENSITY['140Ce'])
    n_cela = int(cela.sum())

    q = []

    def add(tid, text, kind, expected, category, tolerance=0.01, reference='', **kw):
        """Append one question for this dataset."""
        q.append(Question(f"{name}.{tid}", text, kind, expected, tolerance, reference,
                          dataset=name, split=split, category=category, **kw))

    add('count_total', "How many particles are in the dataset?", 'number', len(tf), 'count', 0.0,
        "print(len(df))")
    add('count_fe', "How many particles contain iron?", 'number', int(has['Fe'].sum()), 'count', 0.0,
        "print(int(df[col('counts','Fe')].notna().sum()))")
    add('count_sample', f"How many particles were detected in sample {s1}?", 'number',
        int(counts[s1]), 'count', 0.0, f"print(int((df['sample']=='{s1}').sum()))")
    add('count_pair', "How many particles contain both Ti and Fe?", 'number',
        int((has['Ti'] & has['Fe']).sum()), 'count', 0.0,
        "print(int((df[col('counts','Ti')].notna() & df[col('counts','Fe')].notna()).sum()))")
    add('count_above', f"How many Ti particles in {s0} are larger than 100 nm?", 'number',
        int(((tf['sample'] == s0) & (tf['diam_Ti'] > 100)).sum()), 'count', 0.0,
        f"print(int(((df['sample']=='{s0}') & (df[col('size','Ti')] > 100)).sum()))")
    add('pct_multi', "What percentage of particles contain more than one element?", 'number',
        100.0 * float((tf['n_el'] > 1).mean()), 'count', 0.01,
        "print(100 * (df['n_elements'] > 1).mean())")
    add('pct_cela', "What percentage of Ce-containing particles also contain La?", 'number',
        100.0 * float(cela.sum()) / float(has['Ce'].sum()), 'count', 0.01,
        "ce = df[col('counts','Ce')].notna()\n"
        "print(100 * (ce & df[col('counts','La')].notna()).sum() / ce.sum())")
    add('rate', f"What is the particle detection rate in {s0}, in particles per second?", 'number',
        float(counts[s0]) / span, 'stats', 0.01,
        f"r = runs.set_index('run').loc['{s0}']\nprint(r['n'] / r['span_s'])")
    add('median_ti', f"What is the median Ti equivalent diameter in sample {sl}, in nm?", 'number',
        ti_med[sl], 'stats', 0.01, f"print(df.loc[df['sample']=='{sl}', col('size','Ti')].median())")
    add('mean_fe', f"What is the mean Fe mass per particle in {s0}, in fg?", 'number',
        float(tf.loc[tf['sample'] == s0, 'mass_Fe'].mean()), 'stats', 0.01,
        f"print(df.loc[df['sample']=='{s0}', col('mass','Fe')].mean())")
    add('p90_ce', "What is the 90th percentile of the Ce diameter over all samples, in nm?", 'number',
        float(np.percentile(tf['diam_Ce'].dropna(), 90)), 'stats', 0.01,
        "print(np.percentile(df[col('size','Ce')].dropna(), 90))")
    add('al_total', f"What is the total Al mass detected in {s1}, in fg?", 'number',
        float(tf.loc[tf['sample'] == s1, 'mass_Al'].sum()), 'stats', 0.01,
        f"print(df.loc[df['sample']=='{s1}', col('mass','Al')].sum())")
    add('lace_ratio', "In particles that contain both Ce and La, what is the median La/Ce mass ratio?",
        'number', float((tf.loc[cela, 'mass_La'] / tf.loc[cela, 'mass_Ce']).median()), 'stats', 0.01,
        "m = df[df[col('counts','Ce')].notna() & df[col('counts','La')].notna()]\n"
        "print((m[col('mass','La')] / m[col('mass','Ce')]).median())")
    add('ag_pct', "What is the median Ag mass percentage in particles that contain both Ag and Au?",
        'number', float(tf.loc[agau, 'pct_Ag'].median()), 'stats', 0.01,
        "m = df[df[col('counts','Ag')].notna() & df[col('counts','Au')].notna()]\n"
        "print(m[col('mass_pct','Ag')].median())")

    add('largest_ti', "Which sample has the largest Ti particles?", 'text', largest_ti, 'reasoning',
        reference="show_table(compare_samples('Ti'))", first_of=_names(S),
        reference_answer=f"{largest_ti} has the largest Ti particles.")
    add('most_particles', "Which sample has the most particles?", 'text', most, 'reasoning',
        reference="show_table(df['sample'].value_counts())", first_of=_names(S),
        reference_answer=f"{most} has the most particles.")
    add('largest_element', "Which element forms the largest particles, by median diameter?", 'text',
        largest_el, 'reasoning',
        reference="show_table(element_summary('diameter_nm'))", first_of=dict(ELEMENT_PATTERNS),
        reference_answer=f"{largest_el} forms the largest particles.")
    add('alloy_sample', "Which sample contains particles with both Ag and Au?", 'text',
        re.escape(truth.alloy_sample), 'reasoning',
        reference="both = df[df[col('counts','Ag')].notna() & df[col('counts','Au')].notna()]\n"
                  "show_table(both['sample'].value_counts())")
    if len(no_ce) == 1:
        add('no_ce', "Is there a sample without any Ce particles? Which one?", 'text', no_ce[0],
            'reasoning', reference="show_table(df.groupby('sample')[col('counts','Ce')].count())",
            first_of=_names(S), reference_answer=f"{no_ce[0]} has no Ce particles.")
    add('tife_chance', "Are particles with both Ti and Fe real associations, or explained by "
        "chance coincidence?", 'text', r'chance|coinciden', 'reasoning',
        reference="show_table(coincidence('Ti', 'Fe'))", reject=AFFIRMED_REAL,
        reference_answer="They occur about as often as chance coincidence predicts.")
    add('cela_real', "Are Ce+La particles real associations or chance coincidences?", 'text',
        r'real|genuine|associat|not.{0,20}(chance|coinciden)', 'reasoning',
        reference="show_table(coincidence('Ce', 'La'))",
        reference_answer="They are a real association, far above the chance rate.")
    add('ti_differ', f"Is the Ti particle size significantly different between {s0} and {largest_ti}?",
        'text', r'significant|differ', 'reasoning',
        reference=f"show_table(compare_samples('Ti', groups=['{s0}', '{largest_ti}']))",
        reject=r'not (statistically )?significant|no significant|not differ|no difference',
        reference_answer=f"Yes, Ti particles in {largest_ti} are significantly larger than in {s0}.")
    add('fe_burst', "Is there a burst of iron particles at some point in time? In which sample "
        "and roughly when?", 'text', re.escape(burst_sample) + rf'(?s:.*?)\b({burst_nums})\b',
        'reasoning', reference="show_table(time_bursts('Fe'))")

    add('fig_hist', "Plot a histogram of Fe particle mass for each sample, on a log mass axis.",
        'figure', {'any': {'xscale': 'log', 'min_series': n_s}}, 'figure',
        reference=_hist_ref('Fe', 'mass', 'Fe mass (fg)'))
    add('fig_scatter', "Make a log-log scatter plot of Ti mass versus Ti diameter, coloured by sample.",
        'figure', {'any': {'xscale': 'log', 'yscale': 'log', 'min_series': n_s, 'min_points': 1000}},
        'figure',
        reference="fig, ax = plt.subplots()\n"
                  "for s in samples:\n"
                  "    sub = df[df['sample']==s]\n"
                  "    ax.scatter(sub[col('size','Ti')], sub[col('mass','Ti')], s=3, label=s)\n"
                  "ax.set_xscale('log'); ax.set_yscale('log'); ax.set_xlabel('Ti diameter (nm)');"
                  " ax.set_ylabel('Ti mass (fg)'); ax.legend()")
    add('fig_bar_counts', "Make a bar chart of the number of particles in each sample.", 'figure',
        {'any': {'min_patches': n_s, 'ticklabels_all': S}}, 'figure',
        reference="c = df['sample'].value_counts().reindex(samples)\n"
                  "fig, ax = plt.subplots(figsize=(8, 4.5))\n"
                  "ax.bar(samples, c.values)\n"
                  "ax.set_ylabel('Particles'); ax.tick_params(axis='x', labelrotation=30)")
    add('fig_box', "Show a box plot of Ti diameter for each sample, on a log axis.", 'figure',
        {'any': {'log_any': True, 'ticklabels_any_axis': S}}, 'figure',
        reference="fig, ax = plt.subplots(figsize=(8, 4.5))\n"
                  "ax.boxplot([df.loc[df['sample']==s, col('size','Ti')].dropna() for s in samples])\n"
                  "ax.set_xticks(range(1, len(samples) + 1), samples, rotation=30)\n"
                  "ax.set_yscale('log'); ax.set_ylabel('Ti diameter (nm)')")
    add('fig_burst_trace', f"Plot the number of Fe particles per second over time for sample "
        f"{burst_sample}.", 'figure', {'any': {'min_bins_or_points': 30, 'xlabel': r'time|\(s\)|\bs\b|sec'}},
        'figure',
        reference=f"t = df.loc[(df['sample']=='{burst_sample}') & df[col('counts','Fe')].notna(), 't_start']\n"
                  f"n, edges = np.histogram(t, bins=np.arange(0, {int(span) + 1}, 1))\n"
                  f"fig, ax = plt.subplots()\n"
                  f"ax.step(edges[:-1], n, where='post')\n"
                  f"ax.set_xlabel('Time (s)'); ax.set_ylabel('Fe particles per second')")
    add('fig_panels', "Make one histogram of Ti diameter per sample, each sample in its own panel "
        "with the sample name as the panel title.", 'figure',
        {'panels': n_s, 'each': {'nonempty': True}, 'titles_all': S}, 'figure',
        reference="n = len(samples); nc = min(n, 3); nr = (n + nc - 1) // nc\n"
                  "fig, axes = plt.subplots(nr, nc, figsize=(4 * nc, 3.2 * nr), squeeze=False)\n"
                  "flat = list(axes.ravel())\n"
                  "for ax, s in zip(flat, samples):\n"
                  "    ax.hist(df.loc[df['sample']==s, col('size','Ti')].dropna(), bins=40)\n"
                  "    ax.set_title(s); ax.set_xlabel('Ti diameter (nm)'); ax.set_ylabel('Particles')\n"
                  "for ax in flat[n:]:\n"
                  "    fig.delaxes(ax)")
    add('fig_lod_line', "Plot a histogram of Ce diameter for all particles and mark the Ce size "
        "detection limit with a vertical line.", 'figure',
        {'any': {'nonempty': True, 'vline_at': lod_ce_d}}, 'figure',
        reference="fig, ax = plt.subplots()\n"
                  "ax.hist(df[col('size','Ce')].dropna(), bins=60)\n"
                  "ax.axvline(lod('Ce', 'diameter_nm'), color='k', ls='--', label='LOD')\n"
                  "ax.set_xlabel('Ce diameter (nm)'); ax.set_ylabel('Particles'); ax.legend()")
    add('fig_cela', "Scatter plot of La mass versus Ce mass for the particles that contain both, "
        "with log-log axes.", 'figure',
        {'any': {'xscale': 'log', 'yscale': 'log', 'min_points': int(0.95 * n_cela)}}, 'figure',
        reference="m = df[df[col('counts','Ce')].notna() & df[col('counts','La')].notna()]\n"
                  "fig, ax = plt.subplots()\n"
                  "ax.scatter(m[col('mass','Ce')], m[col('mass','La')], s=4)\n"
                  "ax.set_xscale('log'); ax.set_yscale('log')\n"
                  "ax.set_xlabel('Ce mass (fg)'); ax.set_ylabel('La mass (fg)')")
    add('fig_combos', "Bar chart of the 5 most common element combinations.", 'figure',
        {'any': {'min_patches': 5}}, 'figure',
        reference="c = df['combo'].value_counts().head(5)\n"
                  "fig, ax = plt.subplots(figsize=(8, 4.5))\n"
                  "ax.barh(c.index[::-1], c.values[::-1])\n"
                  "ax.set_xlabel('Particles'); ax.set_ylabel('Element combination')")
    add('fig_ecdf', "Plot the cumulative distribution of Fe diameter for each sample, one curve "
        "per sample.", 'figure', {'any': {'min_series': n_s, 'ymax_between': [(0.98, 1.02), (98, 102)]}},
        'figure',
        reference="fig, ax = plt.subplots()\n"
                  "for s in samples:\n"
                  "    v = np.sort(df.loc[df['sample']==s, col('size','Fe')].dropna().to_numpy())\n"
                  "    ax.plot(v, np.arange(1, v.size + 1) / v.size, label=s)\n"
                  "ax.set_xscale('log'); ax.set_xlabel('Fe diameter (nm)')\n"
                  "ax.set_ylabel('Cumulative fraction'); ax.legend()")
    add('fig_heatmap', "Draw a heatmap of how often each pair of elements occurs together in the "
        "same particle.", 'figure', {'any': {'image': True, 'ticklabels_min': (list(ISOTOPES), 5)}},
        'figure',
        reference="els = elements\n"
                  "pres = np.column_stack([df[col('counts', e)].notna().to_numpy() for e in els]).astype(int)\n"
                  "m = pres.T @ pres\n"
                  "fig, ax = plt.subplots(figsize=(6, 5))\n"
                  "im = ax.imshow(m, cmap='viridis')\n"
                  "ax.set_xticks(range(len(els)), els, rotation=45)\n"
                  "ax.set_yticks(range(len(els)), els)\n"
                  "fig.colorbar(im, ax=ax, label='Particles')")
    add('fig_format', f"Make a bar histogram of Ti diameter in sample {s0} with exactly 40 bins, the "
        f"x-axis labelled 'Diameter (nm)' and the title 'Ti in {s0}'.", 'figure',
        {'any': {'patches_exact': 40, 'xlabel': r'^\s*Diameter \(nm\)\s*$',
                 'title': re.escape(f'Ti in {s0}')}}, 'figure',
        reference=f"fig, ax = plt.subplots()\n"
                  f"ax.hist(df.loc[df['sample']=='{s0}', col('size','Ti')].dropna(), bins=40)\n"
                  f"ax.set_xlabel('Diameter (nm)'); ax.set_ylabel('Particles'); ax.set_title('Ti in {s0}')")
    add('fig_two_panels', "Make a figure with two panels side by side: Ti mass histogram on the "
        "left, Fe mass histogram on the right, both with log x axes.", 'figure',
        {'panels': 2, 'ordered': [{'xscale': 'log', 'nonempty': True, 'label_or_title': r'\bTi\b|titan'},
                                  {'xscale': 'log', 'nonempty': True, 'label_or_title': r'\bFe\b|iron'}]},
        'figure',
        reference="fig, axes = plt.subplots(1, 2, figsize=(10, 4))\n"
                  "for ax, el in zip(axes, ['Ti', 'Fe']):\n"
                  "    v = df[col('mass', el)].dropna()\n"
                  "    ax.hist(v, bins=np.logspace(np.log10(v.min()), np.log10(v.max()), 50))\n"
                  "    ax.set_xscale('log'); ax.set_xlabel(f'{el} mass (fg)'); ax.set_ylabel('Particles')")

    _add_custom(add, S, n_s, s0, tf)
    _add_tables(add, S, tf)
    _add_edits(add, S, n_s, burst_sample, b0, b1, span, cela, tf)
    _add_explore(add, S, s0, largest_ti, burst_sample, b0, b1, truth)
    return q


def _add_custom(add, S, n_s, s0, tf):
    """Single requests for detailed figure customisation."""
    ti_max = float(tf['diam_Ti'].max())
    add('fig_twin_y', "Plot the number of Ti particles and the number of Fe particles in each sample as "
        "two lines, Ti on the left y-axis and Fe on a second y-axis on the right.", 'figure',
        {'twin': True}, 'custom',
        reference="ti = [int(df.loc[df['sample']==s, col('counts','Ti')].notna().sum()) for s in samples]\n"
                  "fe = [int(df.loc[df['sample']==s, col('counts','Fe')].notna().sum()) for s in samples]\n"
                  "fig, ax = plt.subplots(figsize=(8, 4.5))\n"
                  "ax.plot(samples, ti, 'o-', color='C0'); ax.set_ylabel('Ti particles', color='C0')\n"
                  "ax2 = ax.twinx()\n"
                  "ax2.plot(samples, fe, 's-', color='C1'); ax2.set_ylabel('Fe particles', color='C1')\n"
                  "ax.tick_params(axis='x', labelrotation=30)")
    add('fig_threshold', "Make a log-log scatter plot with Fe mass on the x-axis and Fe diameter on the "
        "y-axis, with the points above 1 fg coloured red and the others blue.", 'figure',
        {'any': {'xscale': 'log', 'yscale': 'log',
                 'threshold': {'axis': 'x', 'value': 1.0, 'above': 'red', 'below': 'blue'}}}, 'custom',
        reference="m = df[col('mass','Fe')]; d = df[col('size','Fe')]; ok = m.notna(); hi = ok & (m > 1)\n"
                  "fig, ax = plt.subplots()\n"
                  "ax.scatter(m[ok & ~hi], d[ok & ~hi], s=3, color='blue', label='1 fg or less')\n"
                  "ax.scatter(m[hi], d[hi], s=3, color='red', label='above 1 fg')\n"
                  "ax.set_xscale('log'); ax.set_yscale('log')\n"
                  "ax.set_xlabel('Fe mass (fg)'); ax.set_ylabel('Fe diameter (nm)'); ax.legend()")
    add('fig_color_by', "Make a log-log scatter plot of Ti mass versus Ti diameter, coloured by detection "
        "time, with a colour bar.", 'figure',
        {'colorbar': True, 'any': {'xscale': 'log', 'yscale': 'log', 'mapped': True}}, 'custom',
        reference="sub = df[df[col('counts','Ti')].notna()]\n"
                  "fig, ax = plt.subplots()\n"
                  "sc = ax.scatter(sub[col('size','Ti')], sub[col('mass','Ti')], c=sub['t_start'], s=3,"
                  " cmap='viridis')\n"
                  "fig.colorbar(sc, ax=ax, label='Detection time (s)')\n"
                  "ax.set_xscale('log'); ax.set_yscale('log')\n"
                  "ax.set_xlabel('Ti diameter (nm)'); ax.set_ylabel('Ti mass (fg)')")
    add('fig_errorbars', "Make a bar chart of the median Ti diameter in each sample, with error bars "
        "showing the interquartile range.", 'figure',
        {'any': {'min_patches': n_s, 'errorbars': True}}, 'custom',
        reference="q = [df.loc[df['sample']==s, col('size','Ti')].dropna().quantile([0.25, 0.5, 0.75])"
                  " for s in samples]\n"
                  "med = np.array([v[0.5] for v in q])\n"
                  "lo = med - np.array([v[0.25] for v in q]); hi = np.array([v[0.75] for v in q]) - med\n"
                  "fig, ax = plt.subplots(figsize=(8, 4.5))\n"
                  "ax.bar(samples, med, yerr=[lo, hi], capsize=4)\n"
                  "ax.set_ylabel('Median Ti diameter (nm)'); ax.tick_params(axis='x', labelrotation=30)")
    add('fig_limits_grid', "Make a histogram of Ti diameter for all samples together, with the x-axis "
        "from 0 to 300 nm and a grid.", 'figure',
        {'any': {'nonempty': True, 'xlim': (0.0, 300.0), 'grid': True}}, 'custom',
        reference="fig, ax = plt.subplots()\n"
                  "ax.hist(df[col('size','Ti')].dropna(), bins=np.linspace(0, 300, 61))\n"
                  "ax.set_xlim(0, 300); ax.grid(True)\n"
                  "ax.set_xlabel('Ti diameter (nm)'); ax.set_ylabel('Particles')")
    add('fig_sample_color', f"Make a histogram of Fe diameter for each sample, with {s0} in black and the "
        f"other samples in other colours, and a legend.", 'figure',
        {'any': {'min_series': n_s, 'series_color': (s0, 'black'), 'legend': True}}, 'custom',
        reference="cols = ['black'] + [f'C{i}' for i in range(1, len(samples))]\n"
                  "v = df[col('size','Fe')].dropna()\n"
                  "bins = np.linspace(v.min(), v.quantile(0.995), 60)\n"
                  "fig, ax = plt.subplots()\n"
                  "for s, c in zip(samples, cols):\n"
                  "    ax.hist(df.loc[df['sample']==s, col('size','Fe')].dropna(), bins=bins, histtype='step',"
                  " color=c, label=s)\n"
                  "ax.set_xlabel('Fe diameter (nm)'); ax.set_ylabel('Particles'); ax.legend()")
    add('fig_annotate', "Make a log-log scatter plot of Ti mass versus Ti diameter and annotate the largest "
        "Ti particle with an arrow and its diameter in nm.", 'figure',
        {'any': {'xscale': 'log', 'yscale': 'log', 'arrow': True, 'texts_numbers': ([ti_max], 0.01)}},
        'custom',
        reference="d = df[col('size','Ti')]; m = df[col('mass','Ti')]\n"
                  "i = d.idxmax(); x, y = d[i], m[i]\n"
                  "fig, ax = plt.subplots()\n"
                  "ax.scatter(d, m, s=3)\n"
                  "ax.set_xscale('log'); ax.set_yscale('log')\n"
                  "ax.annotate(f'{x:.1f} nm', xy=(x, y), xytext=(x / 3, y * 2),"
                  " arrowprops=dict(arrowstyle='->'))\n"
                  "ax.set_xlabel('Ti diameter (nm)'); ax.set_ylabel('Ti mass (fg)')")
    add('fig_marker_legend', "Make a log-log scatter plot of La mass versus Ce mass for each sample, with "
        "triangle markers and the legend outside the plot on the right.", 'figure',
        {'any': {'xscale': 'log', 'yscale': 'log', 'marker': 'triangle', 'legend_outside': True}},
        'custom',
        reference="fig, ax = plt.subplots(figsize=(8, 4.5))\n"
                  "for s in samples:\n"
                  "    sub = df[(df['sample']==s) & df[col('counts','Ce')].notna() & df[col('counts','La')].notna()]\n"
                  "    if len(sub):\n"
                  "        ax.scatter(sub[col('mass','Ce')], sub[col('mass','La')], marker='^', s=12, label=s)\n"
                  "ax.set_xscale('log'); ax.set_yscale('log')\n"
                  "ax.set_xlabel('Ce mass (fg)'); ax.set_ylabel('La mass (fg)')\n"
                  "ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5))")


def _add_tables(add, S, tf):
    """Questions answered by one table over every element in every sample."""
    counts, medians, pcts = [], [], []
    for s in S:
        sub = tf[tf['sample'] == s]
        for sym in ISOTOPES:
            v = sub[f'diam_{sym}'].dropna()
            if len(v):
                counts.append((float(len(v)), 0.0))
                medians.append((float(v.median()), 0.01))
                pcts.append((100.0 * len(v) / len(sub), 0.01, 0.06))
    add('table_counts_sizes', "For each element and each sample, give the number of particles and the "
        "median diameter in nm, as one table.", 'table', counts + medians, 'table',
        reference="rows = []\n"
                  "for s in samples:\n"
                  "    sub = df[df['sample']==s]\n"
                  "    for e in elements:\n"
                  "        v = sub[col('size', e)].dropna()\n"
                  "        if len(v):\n"
                  "            rows.append({'sample': s, 'element': e, 'particles': len(v),"
                  " 'median_diameter_nm': v.median()})\n"
                  "show_table(pd.DataFrame(rows))")
    add('table_pct', "For each sample, what percentage of particles contain each element? One table, "
        "samples as rows and elements as columns.", 'table', pcts, 'table',
        reference="t = pd.DataFrame({e: [100 * df.loc[df['sample']==s, col('counts', e)].notna().mean()"
                  " for s in samples] for e in elements}, index=samples)\n"
                  "t.insert(0, 'sample', samples)\n"
                  "show_table(t)")


def _add_edits(add, S, n_s, burst_sample, b0, b1, span, cela, tf):
    """Three-request conversations that each change the previous figure."""
    lod_ti = LOD_MASS_FG['48Ti']
    n_cela = int(cela.sum())
    counts = [float(c) for c in tf['sample'].value_counts().reindex(S)]
    ti_med = [float(tf.loc[(tf['sample'] == s), 'diam_Ti'].median()) for s in S]

    sc1 = ("fig, ax = plt.subplots()\n"
           "ax.scatter(df[col('size','Ti')], df[col('mass','Ti')], s=3, color='grey')\n"
           "ax.set_xscale('log'); ax.set_yscale('log')\n"
           "ax.set_xlabel('Ti diameter (nm)'); ax.set_ylabel('Ti mass (fg)')")
    sc2 = ("d = df[col('size','Ti')]; m = df[col('mass','Ti')]; ok = d.notna(); hi = ok & (d > 100)\n"
           "fig, ax = plt.subplots()\n"
           "ax.scatter(d[ok & ~hi], m[ok & ~hi], s=3, color='grey', label='100 nm or less')\n"
           "ax.scatter(d[hi], m[hi], s=3, color='red', label='above 100 nm')\n"
           "ax.set_xscale('log'); ax.set_yscale('log')\n"
           "ax.set_xlabel('Ti diameter (nm)'); ax.set_ylabel('Ti mass (fg)')")
    sc3 = sc2 + "\nax.axhline(lod('Ti', 'mass_fg'), ls='--', color='k', label='Ti mass LOD')\nax.legend()"
    base1 = {'xscale': 'log', 'yscale': 'log', 'min_points': 1000}
    base2 = dict(base1, threshold={'axis': 'x', 'value': 100.0, 'above': 'red', 'below': 'grey'})
    add('edit_threshold', "", 'conversation', None, 'edit', steps=[
        {'text': "Make a log-log scatter plot of Ti mass versus Ti diameter for all particles.",
         'req': {'any': base1}, 'reference': sc1},
        {'text': "Now colour the points with a Ti diameter above 100 nm red and keep the others grey.",
         'req': {'any': base2}, 'reference': sc2},
        {'text': "Add a horizontal dashed line at the Ti mass detection limit, and a legend.",
         'req': {'any': dict(base2, hline_at=lod_ti, legend=True)}, 'reference': sc3}])

    tr = (f"t = df.loc[(df['sample']=='{burst_sample}') & df[col('counts','Fe')].notna(), 't_start']\n"
          f"n, edges = np.histogram(t, bins=np.arange(0, {int(span) + 1}, 1))\n"
          f"fig, ax = plt.subplots()\n"
          f"ax.step(edges[:-1], n, where='post', color='C0')\n"
          f"ax.set_xlabel('Time (s)'); ax.set_ylabel('Fe particles per second', color='C0')")
    tr2 = (tr + f"\ntt = df.loc[(df['sample']=='{burst_sample}') & df[col('counts','Ti')].notna(), 't_start']\n"
           f"n2, _ = np.histogram(tt, bins=edges)\n"
           f"ax2 = ax.twinx()\n"
           f"ax2.step(edges[:-1], n2, where='post', color='C3')\n"
           f"ax2.set_ylabel('Ti particles per second', color='C3')")
    tr3 = tr2 + f"\nax.axvspan({b0:g}, {b1:g}, color='lightgrey', alpha=0.6)"
    tbase = {'min_bins_or_points': 30, 'xlabel': r'time|\(s\)|\bs\b|sec'}
    add('edit_twin_trace', "", 'conversation', None, 'edit', steps=[
        {'text': f"Plot the number of Fe particles per second over time for sample {burst_sample}.",
         'req': {'any': tbase}, 'reference': tr},
        {'text': "Add the number of Ti particles per second on a second y-axis, in a different colour.",
         'req': {'twin': True, 'any': tbase}, 'reference': tr2},
        {'text': f"Shade the period from {b0:g} to {b1:g} s in light grey.",
         'req': {'twin': True, 'vspan': (b0, b1), 'any': tbase}, 'reference': tr3}])

    bc1 = ("c = df['sample'].value_counts().reindex(samples)\n"
           "fig, ax = plt.subplots(figsize=(8, 4.5))\n"
           "ax.bar(c.index, c.values)\n"
           "ax.set_ylabel('Particles'); ax.tick_params(axis='x', labelrotation=30)")
    bc2 = bc1.replace(".reindex(samples)", ".sort_values(ascending=False)")
    bc3 = bc2.replace("ax.bar(c.index, c.values)", "bars = ax.bar(c.index, c.values)") + "\nax.bar_label(bars)"
    bbase = {'min_patches': n_s, 'ticklabels_all': S}
    add('edit_bars', "", 'conversation', None, 'edit', steps=[
        {'text': "Make a bar chart of the number of particles in each sample.",
         'req': {'any': bbase}, 'reference': bc1},
        {'text': "Sort the bars from the highest to the lowest.",
         'req': {'any': dict(bbase, sorted_desc=True)}, 'reference': bc2},
        {'text': "Write the number of particles above each bar.",
         'req': {'any': dict(bbase, sorted_desc=True, bar_numbers=counts)}, 'reference': bc3}])

    hb = ("v = df[col('mass','Fe')].dropna()\n"
          "bins = np.linspace(v.min(), v.quantile(0.99), 60)\n"
          "fig, ax = plt.subplots()\n"
          "for s in samples:\n"
          "    ax.hist(df.loc[df['sample']==s, col('mass','Fe')].dropna(), bins=bins, histtype='step', label=s)\n"
          "ax.set_xlabel('Fe mass (fg)'); ax.set_ylabel('Particles'); ax.legend()")
    hb2 = (hb.replace("bins = np.linspace(v.min(), v.quantile(0.99), 60)",
                      "bins = np.logspace(np.log10(v.min()), np.log10(v.max()), 60)")
           + "\nax.set_xscale('log')")
    hb3 = ("v = df[col('mass','Fe')].dropna()\n"
           "bins = np.logspace(np.log10(v.min()), np.log10(v.max()), 60)\n"
           "n = len(samples); nc = min(n, 3); nr = (n + nc - 1) // nc\n"
           "fig, axes = plt.subplots(nr, nc, figsize=(4 * nc, 3.2 * nr), squeeze=False)\n"
           "flat = list(axes.ravel())\n"
           "for i, (ax, s) in enumerate(zip(flat, samples)):\n"
           "    ax.hist(df.loc[df['sample']==s, col('mass','Fe')].dropna(), bins=bins, histtype='step',"
           " color=f'C{i}')\n"
           "    ax.set_xscale('log'); ax.set_title(s); ax.set_xlabel('Fe mass (fg)'); ax.set_ylabel('Particles')\n"
           "for ax in flat[n:]:\n"
           "    fig.delaxes(ax)")
    add('edit_panels', "", 'conversation', None, 'edit', steps=[
        {'text': "Plot a histogram of Fe particle mass for each sample, all in one figure.",
         'req': {'any': {'min_series': n_s}}, 'reference': hb},
        {'text': "Use a log scale for the mass axis.",
         'req': {'any': {'min_series': n_s, 'xscale': 'log'}}, 'reference': hb2},
        {'text': "Now put each sample in its own panel, keep the log mass axis, and use the sample name "
                 "as each panel title.",
         'req': {'panels': n_s, 'each': {'xscale': 'log', 'nonempty': True}, 'titles_all': S},
         'reference': hb3}])

    cl = ("m = df[df[col('counts','Ce')].notna() & df[col('counts','La')].notna()]\n"
          "fig, ax = plt.subplots()\n"
          "ax.scatter(m[col('mass','Ce')], m[col('mass','La')], s=5)\n"
          "ax.set_xscale('log'); ax.set_yscale('log')\n"
          "ax.set_xlabel('Ce mass (fg)'); ax.set_ylabel('La mass (fg)')")
    cl2 = cl.replace("ax.scatter(m[col('mass','Ce')], m[col('mass','La')], s=5)",
                     "sc = ax.scatter(m[col('mass','Ce')], m[col('mass','La')], c=m['total_mass_fg'], s=5)") \
        + "\nfig.colorbar(sc, ax=ax)"
    cl3 = cl2.replace("c=m['total_mass_fg'], s=5)", "c=m['total_mass_fg'], s=5, norm=LogNorm())") \
        .replace("fig.colorbar(sc, ax=ax)", "fig.colorbar(sc, ax=ax, label='Total mass (fg)')")
    cbase = {'xscale': 'log', 'yscale': 'log', 'min_points': int(0.95 * n_cela)}
    add('edit_colorscale', "", 'conversation', None, 'edit', steps=[
        {'text': "Make a scatter plot of La mass versus Ce mass for the particles that contain both, with "
                 "log-log axes.",
         'req': {'any': cbase}, 'reference': cl},
        {'text': "Colour the points by the particle's total mass and add a colour bar.",
         'req': {'colorbar': True, 'any': dict(cbase, mapped=True)}, 'reference': cl2},
        {'text': "Use a logarithmic colour scale and label the colour bar 'Total mass (fg)'.",
         'req': {'colorbar': True, 'colorbar_label': r'Total mass \(fg\)',
                 'any': dict(cbase, mapped=True, lognorm=True)}, 'reference': cl3}])

    bx = ("fig, ax = plt.subplots(figsize=(8, 4.5))\n"
          "data = [df.loc[df['sample']==s, col('size','Ti')].dropna() for s in samples]\n"
          "ax.boxplot(data)\n"
          "ax.set_xticks(range(1, len(samples) + 1), samples, rotation=30)\n"
          "ax.set_ylabel('Ti diameter (nm)')")
    bx2 = bx + "\nax.set_yscale('log')"
    bx3 = bx2 + ("\nfor i, v in enumerate(data, start=1):\n"
                 "    ax.text(i + 0.3, v.median(), f'{v.median():.1f}', va='center', fontsize=8)")
    xbase = {'ticklabels_any_axis': S}
    add('edit_box_labels', "", 'conversation', None, 'edit', steps=[
        {'text': "Show a box plot of Ti diameter for each sample.",
         'req': {'any': xbase}, 'reference': bx},
        {'text': "Use a log scale for the diameter axis.",
         'req': {'any': dict(xbase, log_any=True)}, 'reference': bx2},
        {'text': "Write the median value on each box.",
         'req': {'any': dict(xbase, log_any=True, texts_numbers=(ti_med, 0.02))}, 'reference': bx3}])


def _name_pattern(name, group=()):
    """A pattern for a sample name as people write it.

    Underscores may be written as spaces or hyphens, and the last part of the
    name (``Day2`` for ``Influent_Day2``) counts when no other name in
    *group* ends the same way.

    Args:
        name (str): Sample name.
        group (list): The names it must be told apart from.

    Returns:
        str: Regular expression.
    """
    parts = [r'\s?'.join(re.escape(r) for r in re.findall(r'[A-Za-z]+|\d+|[^A-Za-z\d]+', x))
             for x in re.split(r'[_\s-]+', name) if x]
    pats = [r'[_\s-]?'.join(parts)]
    tail = parts[-1] if len(parts) > 1 else ''
    others = [g for g in group if g != name]
    last = re.split(r'[_\s-]+', name)[-1] if len(parts) > 1 else ''
    if len(last) >= 3 and group and not any(re.split(r'[_\s-]+', g)[-1].lower() == last.lower()
                                            for g in others):
        pats.append(rf'\b{tail}\b')
    return '|'.join(f'(?:{p})' for p in pats)


def _add_explore(add, S, s0, largest_ti, burst_sample, b0, b1, truth):
    """Open and targeted explorations scored on the planted features."""
    E = ELEMENT_PATTERNS
    real = (r'real|genuine|associat|above chance|more (often )?than (expected|chance|random)|excess|'
            r'enrich|significant|alloy|co-?occur')
    not_real = (r'explained by chance|consistent with chance|expected by chance|chance (coincidence )?'
                r'(alone|only)|not (a )?real|no real|not significant|random coincidence|rather than')
    planted = {
        'Ce+La real': ([E['Ce'], E['La'], real], not_real),
        'Ce:La shift': ([E['Ce'], E['La'], _name_pattern(truth.cela_shift_sample, S),
                         r'ratio|stoichiom|1\s*:\s*1|slope|scal'], ''),
        'Pb isotopes': ([E['Pb'], _name_pattern(truth.pb_sample, S),
                         r'isotop|206|207|natural|non-?natural|anthropogenic|deviat'], ''),
        'Fe burst': ([_name_pattern(burst_sample, S), r'\bbursts?\b|\bspikes?\b|\bsurges?\b|\bpeaks?\b|\bsudden|\btransient|\bepisod|\banomal'], ''),
        'Ag+Au sample': ([E['Ag'], E['Au'], _name_pattern(truth.alloy_sample, S)], ''),
        f'larger Ti in {largest_ti}': ([_name_pattern(largest_ti, S), E['Ti'],
                                         r'larg|bigger|greater|higher|coarser'], ''),
        'Ag+Au real': ([E['Ag'], E['Au'], real], not_real),
    }
    forbidden = {'Ti+Fe called real': ([E['Ti'], E['Fe'],
                                         r'\breal\b.{0,25}(associat|mix|particle|phase|co-?occur)|'
                                         r'\bgenuine(ly)?\b.{0,25}(associat|mix|particle|phase|co-?occur)|'
                                         r'true association|\bassociated\b|significant(ly)? (associat|enrich|co-?occur)'],
                                        r"chance|coinciden|random|\bnot\b|\bno\b|n't|rather than|separate|independent")}
    lines = {
        'Ce+La real': "Ce and La occur together far more often than chance, a real association.",
        'Ce:La shift': (f"The Ce/La molar ratio is about 1:1 in {truth.cela_shift_sample}, against 2:1 in the "
                        f"other samples, and the ratio changes with particle size there."),
        'Pb isotopes': f"The 206Pb/207Pb ratio in {truth.pb_sample} is about 15% below natural, a non-natural Pb source.",
        'Fe burst': f"There is a burst of Fe particles in {burst_sample} around {b0:g} to {b1:g} s.",
        'Ag+Au sample': f"Ag and Au particles appear only in {truth.alloy_sample}.",
        f'larger Ti in {largest_ti}': f"{largest_ti} has larger Ti particles than the other samples.",
        'Ag+Au real': "Ag and Au form a real association, far above chance.",
    }
    tife = "Ti and Fe meet only by chance coincidence."

    def pick(names):
        """The planted features and reference summary for these names."""
        return {k: planted[k] for k in names}, ' '.join([lines[k] for k in names] + [tife])

    script = ["PLAN:\n1. Associations between elements\n2. Ce/La molar ratio by sample\n3. Pb isotope ratio\n"
              "4. Bursts in time\n```python\n"
              "show_table(coincidence_overview())\n"
              "record_finding('Element pairs compared with the chance coincidence rate')\n```",
              "Ce/La molar ratio by sample.\n```python\nshow_table(molar_ratio('Ce', 'La'))\n```",
              "Pb isotope ratio by sample.\n```python\nshow_table(isotope_ratio('206Pb', '207Pb'))\n```",
              "Time bursts of Fe.\n```python\nshow_table(time_bursts('Fe'))\n```",
              "EXPLORATION DONE"]
    names_open = [k for k, ok in (('Ce:La shift', truth.cela_shift_sample), ('Pb isotopes', truth.pb_sample),
                                  ('Ag+Au sample', True), (f'larger Ti in {largest_ti}', True)) if ok]
    f, ref = pick(names_open)
    add('explore_open', "Explore the dataset and tell me what is interesting.", 'explore', None, 'explore',
        findings=f, forbidden=forbidden, need=min(3, len(names_open)), max_turns=8, reference_answer=ref, steps=script)
    f, ref = pick(['Fe burst'])
    add('explore_iron', "Is there anything unusual about iron in this data?", 'explore', None, 'explore',
        findings=f, forbidden=forbidden, need=1, max_turns=5, reference_answer=ref, steps=script)
    f, ref = pick(['Ce+La real', 'Ag+Au real'])
    add('explore_pairs', "Which elements occur together in the same particles more often than chance "
        "would predict?", 'explore', None, 'explore',
        findings=f, forbidden=forbidden, need=2, max_turns=5, reference_answer=ref, steps=script)
    f, ref = pick([f'larger Ti in {largest_ti}'])
    f = {k: ([_name_pattern(largest_ti, [s0, largest_ti])] + pats[1:], unless) for k, (pats, unless) in f.items()}
    add('explore_compare', f"Compare {s0} and {largest_ti}.", 'explore', None, 'explore',
        findings=f, forbidden=forbidden, need=1, max_turns=5, reference_answer=ref, steps=script)


def _raise_for_status(response):
    """Raise on an HTTP error with the server's own message, which says what went wrong."""
    if response.status_code >= 400:
        detail = (response.text or '').strip().replace('\n', ' ')[:400]
        raise RuntimeError(f"HTTP {response.status_code} from {response.url}: {detail}")


def complete(cfg, messages, system, timeout=600):
    """One non-streaming chat completion.

    Args:
        cfg (dict): ``backend`` (``ollama``, ``mlx`` or ``custom``),
            ``model``, ``host``, ``api_key``, ``num_ctx``, ``temperature``
            and ``think`` (True lets a thinking model reason first; off by
            default, as in the app).
        messages (list): Chat messages.
        system (str): System prompt.
        timeout (float): Seconds to wait.

    Returns:
        str: The reply text.
    """
    from results.ai.servers import MLX_BASE, OLLAMA_BASE, local_session
    msgs = [{"role": "system", "content": system}] + list(messages)
    num_ctx = int(cfg.get('num_ctx', 8192))
    if cfg.get('backend', 'ollama') == 'ollama':
        host = (cfg.get('host') or OLLAMA_BASE).rstrip('/')
        with local_session() as s:
            r = s.post(f"{host}/api/chat", json={
                "model": cfg.get('model', ''), "messages": msgs, "stream": False,
                "options": {"temperature": cfg.get('temperature', 0.2), "num_ctx": num_ctx,
                            "num_predict": reply_reserve(num_ctx)},
                "think": bool(cfg.get('think', False))}, timeout=timeout)
        _raise_for_status(r)
        return (r.json().get('message') or {}).get('content', '')
    host = (cfg.get('host') or MLX_BASE).rstrip('/')
    url = host if host.endswith('/v1') else f"{host}/v1"
    headers = {'Content-Type': 'application/json'}
    if cfg.get('api_key'):
        headers['Authorization'] = f"Bearer {cfg['api_key']}"
    payload = {"messages": msgs, "stream": False, "temperature": cfg.get('temperature', 0.2),
               "max_tokens": reply_reserve(num_ctx)}
    if cfg.get('model'):
        payload['model'] = cfg['model']
    if cfg.get('backend') != 'custom':
        payload['chat_template_kwargs'] = {"enable_thinking": bool(cfg.get('think', False))}
    session = local_session()
    if cfg.get('backend') == 'custom':
        import requests
        session = requests.Session()
    with session as s:
        r = s.post(f"{url}/chat/completions", json=payload, headers=headers, timeout=timeout)
    _raise_for_status(r)
    return r.json()['choices'][0]['message']['content']


def reference_model(question):
    """A stand-in model that answers with the question's reference code.

    Args:
        question (Question): The question.

    Returns:
        callable: ``(messages, system) -> reply``.
    """
    if question.kind == 'conversation':
        codes = {s['text']: s['reference'] for s in question.steps}

        def edit_reply(messages, system):
            """Answer each request with its reference code, anything else with a short note."""
            last = messages[-1]['content'] if messages else ''
            if last in codes:
                return f"Updating the figure.\n```python\n{codes[last]}\n```"
            return "The figure is updated as asked."
        return edit_reply
    if question.kind == 'explore':
        turns = {'n': 0}

        def explore_reply(messages, system):
            """Play a short scripted exploration, then the reference summary."""
            last = messages[-1]['content'] if messages else ''
            if last.startswith('EXPLORATION OVER'):
                return question.reference_answer
            turns['n'] += 1
            return question.steps[min(turns['n'], len(question.steps)) - 1]
        return explore_reply
    state = {'calls': 0}

    def reply(messages, system):
        """Return the reference code first, then a takeaway quoting the results."""
        state['calls'] += 1
        if state['calls'] == 1:
            return f"Computing it.\n```python\n{question.reference}\n```"
        if question.reference_answer:
            return question.reference_answer
        return "From the results: " + messages[-1]['content'][:1500]
    return reply


@dataclass
class Outcome:
    """How one question went.

    Attributes:
        qid (str): Question id.
        dataset (str): Dataset key.
        split (str): ``dev`` or ``test``.
        category (str): Question category.
        passed (bool): Whether the answer was right.
        attempts (int): Code runs needed.
        fixes (int): Corrections and figure redraws the model was asked for.
        seconds (float): Wall time.
        error (str): Last sandbox or backend error.
        detail (str): Why it passed or failed.
        answer (str): The final answer text.
        transcript (list): The whole conversation with the model, code
            included, so a failure can be read afterwards.
    """

    qid: str
    dataset: str = ''
    split: str = ''
    category: str = ''
    passed: bool = False
    attempts: int = 0
    fixes: int = 0
    seconds: float = 0.0
    error: str = ''
    detail: str = ''
    answer: str = field(default='', repr=False)
    transcript: list = field(default_factory=list, repr=False)


def _panels(fig):
    """The data panels of a figure, without colour bars."""
    return [ax for ax in fig.axes if ax.get_label() != '<colorbar>']


def _series(ax):
    """Number of plotted series on a panel, as the legend or artists show it."""
    series = len(ax.lines) + len(ax.collections) + len({id(c) for c in ax.containers})
    if ax.patches and not ax.containers:
        series += 1
    leg = ax.get_legend()
    if leg is not None:
        series = max(series, len(leg.get_texts()))
    return series


def _points(ax):
    """Number of scatter markers on a panel."""
    n = 0
    for c in ax.collections:
        try:
            n += len(c.get_offsets())
        except Exception:
            pass
    return n


def _ticklabels(ax, axis='x'):
    """Tick label texts of one axis."""
    labels = ax.get_xticklabels() if axis == 'x' else ax.get_yticklabels()
    return [t.get_text() for t in labels]


def _has_image(ax):
    """Whether a panel shows an image or a colour mesh."""
    if ax.images:
        return True
    return any(type(c).__name__ in ('QuadMesh', 'PolyQuadMesh') for c in ax.collections)


def _drawn(ax):
    """Whether anything is drawn on a panel."""
    return bool(ax.lines or ax.patches or ax.images or ax.collections)


def _panel_ok(ax, spec):
    """Check one panel against a requirement.

    Args:
        ax (Axes): The panel.
        spec (dict): Requirement keys, see :func:`build_questions`.

    Returns:
        tuple: ``(ok, reason)``.
    """
    if spec.get('nonempty') and not _drawn(ax):
        return False, "empty panel"
    for key in ('xscale', 'yscale'):
        want = spec.get(key)
        got = ax.get_xscale() if key == 'xscale' else ax.get_yscale()
        if want and got != want:
            return False, f"{key} is {got}, not {want}"
    if spec.get('log_any') and 'log' not in (ax.get_xscale(), ax.get_yscale()):
        return False, "no log axis"
    if _series(ax) < spec.get('min_series', 0):
        return False, f"{_series(ax)} series, need {spec['min_series']}"
    if _points(ax) < spec.get('min_points', 0):
        return False, f"{_points(ax)} points, need {spec['min_points']}"
    if len(ax.patches) < spec.get('min_patches', 0):
        return False, f"{len(ax.patches)} bars, need {spec['min_patches']}"
    if 'patches_exact' in spec and len(ax.patches) != spec['patches_exact']:
        return False, f"{len(ax.patches)} bars, need exactly {spec['patches_exact']}"
    if 'min_bins_or_points' in spec:
        k = spec['min_bins_or_points']
        line_pts = max([len(ln.get_xdata()) for ln in ax.lines] or [0])
        if max(len(ax.patches), line_pts, _points(ax)) < k:
            return False, f"fewer than {k} time bins"
    if spec.get('xlabel') and not re.search(spec['xlabel'], ax.get_xlabel(), re.I):
        return False, f"x label '{ax.get_xlabel()}'"
    if spec.get('title') and not re.search(spec['title'], axes_title(ax)):
        return False, f"title '{axes_title(ax)}'"
    if spec.get('label_or_title'):
        text = ' '.join([axes_title(ax), ax.get_xlabel(), ax.get_ylabel()])
        if not re.search(spec['label_or_title'], text, re.I):
            return False, "panel does not name its element"
    if spec.get('ticklabels_all'):
        ticks = ' '.join(_ticklabels(ax, 'x') + _ticklabels(ax, 'y'))
        missing = [s for s in spec['ticklabels_all'] if s not in ticks]
        if missing:
            return False, f"tick labels miss {missing[:2]}"
    if spec.get('ticklabels_any_axis'):
        ticks = ' '.join(_ticklabels(ax, 'x') + _ticklabels(ax, 'y'))
        leg = ax.get_legend()
        if leg is not None:
            ticks += ' ' + ' '.join(t.get_text() for t in leg.get_texts())
        missing = [s for s in spec['ticklabels_any_axis'] if s not in ticks]
        if missing:
            return False, f"samples not labelled: {missing[:2]}"
    if spec.get('ticklabels_min'):
        names, k = spec['ticklabels_min']
        ticks = ' '.join(_ticklabels(ax, 'x') + _ticklabels(ax, 'y'))
        if sum(1 for n in names if n in ticks) < k:
            return False, "element names missing from the axes"
    if spec.get('image') and not _has_image(ax):
        return False, "no image or colour mesh"
    if 'vline_at' in spec:
        x = spec['vline_at']
        hit = False
        for ln in ax.lines:
            xs = np.asarray(ln.get_xdata(), dtype=float)
            if xs.size >= 2 and np.allclose(xs, xs[0]) and abs(xs[0] - x) <= 0.03 * abs(x):
                hit = True
        if not hit:
            return False, f"no vertical line at {x:.3g}"
    if spec.get('ymax_between'):
        ys = [np.nanmax(np.asarray(ln.get_ydata(), dtype=float)) for ln in ax.lines
              if len(ln.get_ydata())]
        top = max(ys) if ys else float('nan')
        if not any(lo <= top <= hi for lo, hi in spec['ymax_between']):
            return False, f"curves end at {top:.3g}, not at 1 or 100%"
    if spec.get('threshold'):
        ok, why = _threshold_ok(ax, spec['threshold'])
        if not ok:
            return False, why
    if 'hline_at' in spec:
        y = spec['hline_at']
        if not any(_constant(ln.get_ydata(), y) for ln in ax.lines):
            return False, f"no horizontal line at {y:.3g}"
    if spec.get('legend') and ax.get_legend() is None and not ax.figure.legends:
        return False, "no legend"
    if spec.get('mapped') and not any(_mapped(c) for c in ax.collections):
        return False, "points not coloured by a value"
    if spec.get('lognorm') and not any(_mapped(c) and isinstance(c.norm, LogNorm) for c in ax.collections):
        return False, "colour scale is not logarithmic"
    if spec.get('errorbars') and not _has_errorbars(ax):
        return False, "no error bars"
    if spec.get('xlim'):
        lo, hi = spec['xlim']
        x0, x1 = ax.get_xlim()
        tol = 0.02 * (hi - lo)
        if abs(x0 - lo) > tol or abs(x1 - hi) > tol:
            return False, f"x range {x0:.3g} to {x1:.3g}"
    if spec.get('grid') and not any(g.get_visible() for g in ax.get_xgridlines() + ax.get_ygridlines()):
        return False, "no grid"
    if spec.get('series_color'):
        label, colour = spec['series_color']
        if not _series_has_color(ax, label, colour):
            return False, f"{label} is not {colour}"
    if spec.get('texts_numbers'):
        values, rtol = spec['texts_numbers']
        nums = [v for t in ax.texts for v in floats_in_text(t.get_text())]
        missing = [v for v in values if not any(abs(n - v) <= rtol * abs(v) for n in nums)]
        if missing:
            return False, f"value {missing[0]:.4g} not written on the figure"
    if spec.get('bar_numbers'):
        nums = [v for t in ax.texts for v in floats_in_text(t.get_text())]
        missing = [v for v in spec['bar_numbers'] if not any(abs(n - v) < 0.5 for n in nums)]
        if missing:
            return False, f"bar value {missing[0]:g} not written"
    if spec.get('arrow') and not any(getattr(t, 'arrow_patch', None) is not None for t in ax.texts):
        return False, "no arrow annotation"
    if spec.get('marker') == 'triangle' and not _has_triangles(ax):
        return False, "markers are not triangles"
    if spec.get('legend_outside') and not _legend_outside(ax):
        return False, "legend is not outside on the right"
    if spec.get('sorted_desc') and not _bars_sorted(ax):
        return False, "bars not sorted from highest to lowest"
    return True, ''


def _rgba(colors):
    """Colours as an RGBA array, empty when they cannot be read."""
    try:
        return to_rgba_array(colors)
    except Exception:
        return np.empty((0, 4))


def _is_color(rgba, name):
    """Whether an RGBA colour reads as the named colour."""
    r, g, b = float(rgba[0]), float(rgba[1]), float(rgba[2])
    if name == 'red':
        return r > 0.6 and g < 0.45 and b < 0.45
    if name == 'blue':
        return b > 0.5 and r < 0.45 and b > g
    if name == 'black':
        return max(r, g, b) < 0.25
    if name == 'grey':
        return abs(r - g) < 0.08 and abs(g - b) < 0.08 and 0.25 <= r <= 0.92
    return False


def _point_colors(ax):
    """Every visible scatter point of a panel as ``x, y, r, g, b, a`` rows.

    A point drawn several times, e.g. all points in grey and then the
    selected ones again in red on top, keeps only the colour drawn last.
    """
    rows = []
    for c in sorted(ax.collections, key=lambda c: c.get_zorder()):
        try:
            off = np.asarray(c.get_offsets(), dtype=float)
        except Exception:
            continue
        if off.ndim != 2 or not len(off):
            continue
        fc = _rgba(c.get_facecolors())
        if not len(fc):
            fc = _rgba(c.get_edgecolors())
        if len(fc) == 1:
            fc = np.repeat(fc, len(off), axis=0)
        if len(fc) != len(off):
            continue
        rows.append(np.column_stack([off, fc[:, :4]]))
    if not rows:
        return np.empty((0, 6))
    pts = np.vstack(rows)
    keys = np.round(pts[:, :2], 9)
    _, last = np.unique(keys[::-1], axis=0, return_index=True)
    return pts[::-1][last]


def _threshold_ok(ax, th):
    """Whether points beyond a threshold, and only those, have the asked colour."""
    pts = _point_colors(ax)
    if not len(pts):
        return False, "no scatter points"
    v = pts[:, 0] if th['axis'] == 'x' else pts[:, 1]
    good = np.isfinite(v)
    above = good & (v > th['value'])
    below = good & (v <= th['value'])
    if not above.any() or not below.any():
        return False, "no points on both sides of the threshold"
    is_above = np.array([_is_color(c, th['above']) for c in pts[:, 2:6]])
    if is_above[above].mean() < 0.98:
        return False, f"points above {th['value']:g} are not {th['above']}"
    if is_above[below].mean() > 0.02:
        return False, f"points below {th['value']:g} are also {th['above']}"
    if th.get('below'):
        is_below = np.array([_is_color(c, th['below']) for c in pts[below][:, 2:6]])
        if is_below.mean() < 0.98:
            return False, f"points below {th['value']:g} are not {th['below']}"
    return True, ''


def _constant(values, target, rtol=0.03):
    """Whether a line is flat at *target*."""
    a = np.asarray(values, dtype=float)
    return a.size >= 2 and np.allclose(a, a[0]) and abs(a[0] - target) <= rtol * abs(target)


def _mapped(c):
    """Whether a collection is coloured through a colour map."""
    try:
        arr = c.get_array()
    except Exception:
        return False
    return arr is not None and np.size(arr) > 1


def _has_errorbars(ax):
    """Whether a panel holds error bars."""
    for c in ax.containers:
        if type(c).__name__ == 'ErrorbarContainer' or getattr(c, 'errorbar', None) is not None:
            return True
    return False


def _series_has_color(ax, label, name):
    """Whether the series with this legend label is drawn in the named colour."""
    artists = list(ax.lines) + list(ax.collections) + list(ax.patches) + list(ax.containers)
    for a in artists:
        try:
            text = str(a.get_label())
        except Exception:
            continue
        if text != label and not re.search(rf'(?<![\w]){re.escape(label)}(?![\w])', text):
            continue
        target = a.patches[0] if hasattr(a, 'patches') and a.patches else a
        cols = []
        for getter in ('get_color', 'get_facecolor', 'get_edgecolor', 'get_facecolors', 'get_edgecolors'):
            fn = getattr(target, getter, None)
            if fn is not None:
                try:
                    cols.extend(c for c in _rgba(fn()) if c[3] > 0)
                except Exception:
                    pass
        if any(_is_color(c, name) for c in cols):
            return True
    return False


def _has_triangles(ax):
    """Whether the scatter markers are triangles."""
    for c in ax.collections:
        try:
            paths = c.get_paths()
        except Exception:
            continue
        for path in paths[:1]:
            if len(np.unique(np.round(path.vertices, 6), axis=0)) == 3:
                return True
    return False


def _legend_outside(ax):
    """Whether a legend sits to the right of the panel."""
    fig = ax.figure
    legends = [lg for lg in [ax.get_legend()] + list(fig.legends) if lg is not None]
    if not legends:
        return False
    try:
        renderer = fig.canvas.get_renderer()
        box = ax.get_window_extent(renderer)
        return any(lg.get_window_extent(renderer).x0 >= box.x1 - 2 for lg in legends)
    except Exception:
        return False


def _bars_sorted(ax):
    """Whether the bars run from the highest to the lowest."""
    rects = [p for p in ax.patches if type(p).__name__ == 'Rectangle' and p.get_width() and p.get_height()]
    if len(rects) < 2:
        return False

    def falling(seq):
        """Non-increasing and not constant."""
        return len(set(seq)) > 1 and all(a >= b for a, b in zip(seq, seq[1:]))
    vertical = [p.get_height() for p in sorted(rects, key=lambda p: p.get_x())]
    horizontal = [p.get_width() for p in sorted(rects, key=lambda p: -p.get_y())]
    return falling(vertical) or falling(horizontal)


def _has_twin(panels):
    """Whether two drawn panels share the same place, as ``twinx`` makes."""
    for i, a in enumerate(panels):
        for b in panels[i + 1:]:
            if np.allclose(a.get_position().bounds, b.get_position().bounds, atol=1e-3) \
                    and _drawn(a) and _drawn(b):
                return True
    return False


def _has_span(ax, t0, t1):
    """Whether a shaded band covers ``t0`` to ``t1`` on the x-axis."""
    for p in ax.patches:
        try:
            if hasattr(p, 'get_x') and hasattr(p, 'get_width'):
                x0 = float(p.get_x())
                x1 = x0 + float(p.get_width())
            else:
                xs = np.asarray(p.get_xy(), dtype=float)[:, 0]
                x0, x1 = float(xs.min()), float(xs.max())
        except Exception:
            continue
        if abs(x0 - t0) <= 1.0 and abs(x1 - t1) <= 1.0 and (x1 - x0) >= 0.6 * (t1 - t0):
            return True
    return False


def _figure_ok(fig, req):
    """Check one figure against a requirement.

    Args:
        fig (Figure): The figure.
        req (dict): ``panels``, ``each``, ``any``, ``ordered`` and
            ``titles_all`` keys, all optional.

    Returns:
        tuple: ``(ok, reason)``.
    """
    panels = _panels(fig)
    if req.get('twin'):
        if not _has_twin(panels):
            return False, "no second y-axis"
    if req.get('colorbar') and not any(ax.get_label() == '<colorbar>' for ax in fig.axes):
        return False, "no colour bar"
    if req.get('colorbar_label'):
        labels = ' '.join(ax.get_ylabel() + ' ' + ax.get_xlabel() for ax in fig.axes
                          if ax.get_label() == '<colorbar>')
        if not re.search(req['colorbar_label'], labels):
            return False, f"colour bar label '{labels.strip()}'"
    if req.get('vspan') and not any(_has_span(ax, *req['vspan']) for ax in _panels(fig)):
        return False, "no shaded period"
    if 'panels' in req and len(panels) != req['panels']:
        return False, f"{len(panels)} panels, need {req['panels']}"
    if req.get('each'):
        for ax in panels:
            ok, why = _panel_ok(ax, req['each'])
            if not ok:
                return False, why
    if req.get('ordered'):
        for ax, spec in zip(panels, req['ordered']):
            ok, why = _panel_ok(ax, spec)
            if not ok:
                return False, why
    if req.get('titles_all'):
        titles = ' '.join(axes_title(ax) for ax in panels)
        missing = [s for s in req['titles_all'] if s not in titles]
        if missing:
            return False, f"panel titles miss {missing[:2]}"
    if req.get('any'):
        reasons = []
        for ax in panels:
            ok, why = _panel_ok(ax, req['any'])
            if ok:
                return True, ''
            reasons.append(why)
        return False, reasons[0] if reasons else "no panels"
    return True, ''


def _check_figure(req, results):
    """Whether any figure meets the requirement without drawing problems.

    Args:
        req (dict): Figure requirement.
        results (list): Every :class:`~results.ai.sandbox.ExecResult` produced.

    Returns:
        tuple: ``(passed, detail)``.
    """
    reason = "no figure"
    for res in results:
        problems = [w for w in res.warnings if any(k in w for k in QUALITY_WARNINGS)]
        if any(_has_twin(_panels(f['figure'])) for f in res.figures):
            problems = [w for w in problems if 'has no x-axis label' not in w]
        for f in res.figures:
            ok, why = _figure_ok(f['figure'], req)
            if ok and not problems:
                p = _panels(f['figure'])
                return True, f"figure ok ({len(p)} panel(s), {sum(_series(a) for a in p)} series)"
            reason = why if not ok else f"drawing problem: {problems[0][:70]}"
    return False, reason


def score(question, results, answer):
    """Decide whether an answer is right.

    Args:
        question (Question): The question.
        results (list): Every :class:`~results.ai.sandbox.ExecResult` produced.
        answer (str): The final answer text.

    Returns:
        tuple: ``(passed, detail)``.
    """
    if question.kind == 'figure':
        return _check_figure(question.expected, results)
    if question.kind == 'table':
        nums = list(floats_in_text(answer))
        for r in results:
            nums.extend(r.numbers)
        nums = np.asarray([v for v in nums if v == v], dtype=float)
        hit = 0
        for item in question.expected:
            v, tol = item[0], item[1]
            atol = item[2] if len(item) > 2 else 0.0
            if nums.size and np.any(np.abs(nums - v) <= max(1e-9, tol * abs(v), atol)):
                hit += 1
        need = int(math.ceil(0.95 * len(question.expected)))
        detail = f"{hit}/{len(question.expected)} table values found"
        return hit >= need, detail
    pool = answer + '\n' + '\n'.join(result_digest(r, 50) for r in results)
    if question.kind == 'number':
        exp = float(question.expected)
        for v in floats_in_text(pool):
            if abs(v - exp) <= max(1e-9, question.tolerance * abs(exp)):
                return True, f"found {v:g} (expected {exp:g})"
        return False, f"expected {exp:g}, not found"
    if question.reject and re.search(question.reject, answer, re.I):
        return False, "answer contains a rejected claim"
    if question.first_of:
        hits = sorted((m.start(), name) for name, pat in question.first_of.items()
                      for m in [re.search(pat, answer, re.I)] if m)
        if hits and hits[0][1] == question.expected:
            return True, f"answer names {question.expected} first"
        return False, f"answer does not name {question.expected} first"
    target = answer if question.reference_answer else pool
    if re.search(question.expected, target, re.I):
        return True, "expected text found"
    return False, f"/{question.expected[:40]}/ not found"


def _chat_turn(messages, system, ds, model, num_ctx, out, results):
    """One user request handled the way the chat window handles it.

    An empty answer is asked for again once, and an answer without code that
    quotes results goes back once to be computed first. The model's code runs; a failure goes back for a fix (up to
    :data:`MAX_FIX_ATTEMPTS`), a figure with drawing problems goes back once
    for a redraw, and the results are then shown to the model for the
    takeaway. The history ends as the chat keeps it: the code reply, the
    results, then the takeaway, so a follow-up request can build on the code.

    Args:
        messages (list): Conversation so far, ending with the user request;
            extended in place.
        system (str): System prompt.
        ds (Dataset): The dataset.
        model (callable): ``(messages, system) -> reply``.
        num_ctx (int): Context window.
        out (Outcome): Receives attempts and errors.
        results (list): Receives every result that ran without error.

    Returns:
        str: The final answer text.
    """
    fixes = figure_fixes = 0
    nudged = emptied = False
    while True:
        reply = cut_after_code(strip_thinking(model(fit_messages(messages, system, num_ctx), system) or '').strip())
        messages.append({"role": "assistant", "content": reply})
        codes = [c for c in CODE_RE.findall(reply) if c.strip()]
        prose = CODE_RE.sub('', reply).strip()
        if not codes:
            if not emptied and is_empty_reply(prose):
                emptied = True
                out.fixes += 1
                messages.append({"role": "user", "content": empty_reply_request()})
                continue
            if not nudged and needs_code(prose, system):
                nudged = True
                out.fixes += 1
                messages.append({"role": "user", "content": code_first_request()})
                continue
            return prose
        batch = [execute(c, ds, EXEC_TIMEOUT_S) for c in codes]
        out.attempts += 1
        errors = [r.error for r in batch if r.error]
        results.extend(r for r in batch if not r.error)
        if errors and fixes < MAX_FIX_ATTEMPTS:
            fixes += 1
            out.fixes += 1
            out.error = errors[0]
            digest = '\n\n'.join(result_digest(r, 6) for r in batch if r.produced)
            messages.append({"role": "user", "content": correction_request(errors[0], digest)})
            continue
        warns = [w for r in batch for w in r.warnings]
        if warns and not errors and figure_fixes < MAX_FIGURE_FIXES:
            figure_fixes += 1
            out.fixes += 1
            messages.append({"role": "user", "content": figure_fix_request(warns)})
            continue
        if errors:
            out.error = errors[0]
            return prose
        out.error = ''
        produced = [r for r in batch if r.produced]
        if not produced:
            return prose
        digest = '\n\n'.join(result_digest(r, 15) for r in produced)
        messages.append({"role": "user", "content": interpretation_request(digest)})
        text = CODE_RE.sub('', strip_thinking(model(fit_messages(messages, system, num_ctx), system) or '')).strip()
        messages[-1] = {"role": "user", "content": "[Results of the code above]\n" + digest[:3000]}
        if text:
            messages.append({"role": "assistant", "content": text})
        return text or prose


def _sentence_hit(sentences, patterns, unless=''):
    """Whether one sentence matches every pattern and not *unless*."""
    for s in sentences:
        if all(re.search(p, s, re.I) for p in patterns) and not (unless and re.search(unless, s, re.I)):
            return True
    return False


def _without_rejected_titles(text):
    """Drop the bold hypothesis titles listed under a "Not supported" heading.

    A summary lists rejected hypotheses by name, e.g. "**Ti+Fe as a real
    particle type.**", followed by the evidence against it. The title is not
    a claim; the text after it still is and is kept.

    Args:
        text (str): Summary text.

    Returns:
        str: The text with those titles removed.
    """
    out = []
    rejected = False
    for line in (text or '').splitlines():
        t = line.strip()
        heading = (t.startswith('#') or bool(re.match(r'^\*\*[^*]{2,60}\*\*:?\s*$', t))
                   or bool(re.match(r'^\*\*[^*]{2,60}:\*\*', t)) or bool(re.match(r'^[A-Z][A-Za-z ]{2,40}:$', t)))
        if heading:
            rejected = bool(re.search(r'not\s+supported|rejected|ruled out', t, re.I))
        if rejected and not heading:
            line = re.sub(r'\*\*[^*]+\*\*', '', line)
        out.append(line)
    return '\n'.join(out)


def score_exploration(question, text):
    """Score an exploration summary against the planted features.

    Args:
        question (Question): An ``explore`` question.
        text (str): Summary plus the recorded findings.

    Returns:
        tuple: ``(passed, detail)``.
    """
    sentences = [s for s in re.split(r'(?<=[.!?;])\s+|\n+', text or '') if s.strip()]
    claimed = [s for s in re.split(r'(?<=[.!?;])\s+|\n+', _without_rejected_titles(text)) if s.strip()]
    clauses = [c for s in claimed
               for c in re.split(r'[,;:(]|\b(?:whereas|while|but|conversely|however|unlike|than)\b', s, flags=re.I)
               if c and c.strip()]
    found = [n for n, (pats, unless) in question.findings.items() if _sentence_hit(sentences, pats, unless)]
    false = [n for n, (pats, unless) in question.forbidden.items() if _sentence_hit(clauses, pats, unless)]
    detail = f"found {len(found)}/{len(question.findings)}" + (f" ({', '.join(found)})" if found else '')
    if false:
        return False, detail + f"; false claim: {false[0]}"
    return len(found) >= question.need, detail


def _ask_conversation(question, ds, model, num_ctx):
    """Run a multi-request figure conversation and check every step."""
    out = Outcome(qid=question.qid, dataset=question.dataset, split=question.split,
                  category=question.category)
    t0 = time.time()
    system = build_system_prompt(ds, num_ctx)
    messages = []
    out.transcript = messages
    n = len(question.steps)
    k = 0
    shown = []
    try:
        for k, step in enumerate(question.steps, start=1):
            messages.append({"role": "user", "content": step['text']})
            results = []
            out.answer = _chat_turn(messages, system, ds, model, num_ctx, out, results)
            if any(r.figures for r in results):
                shown = results
            ok, why = _check_figure(step['req'], shown)
            if not ok:
                out.detail = f"step {k}/{n}: {why}"
                break
        else:
            out.passed = True
            out.detail = f"all {n} steps ok"
    except Exception as e:
        out.error = f"{type(e).__name__}: {e}"
        out.detail = out.detail or f"step {k}/{n}: stopped by an error"
    out.seconds = time.time() - t0
    return out


def _ask_explore(question, ds, model, num_ctx):
    """Run an exploration the way the Explore button does and score its summary."""
    out = Outcome(qid=question.qid, dataset=question.dataset, split=question.split,
                  category=question.category)
    t0 = time.time()
    st = ExplorationState(question=question.text, max_turns=question.max_turns)
    st.messages = [{"role": "user", "content": first_exploration_message(question.text, first_look(ds))}]
    out.transcript = st.messages
    system = build_system_prompt(ds, num_ctx, 'explore', question.max_turns)
    summary = ''
    try:
        while st.begin_turn():
            reply = strip_thinking(model(fit_messages(compact_messages(st.messages), system, num_ctx, pinned=1),
                                         system) or '').strip()
            done = is_done(reply)
            if not st.plan:
                st.plan = parse_plan(reply)
            reply = cut_after_code(reply)
            st.messages.append({"role": "assistant", "content": reply})
            m = CODE_RE.search(reply)
            if not m:
                if done:
                    break
                st.failures += 1
                if st.failures >= 2:
                    break
                st.messages.append({"role": "user", "content":
                                    "Write one line naming the hypothesis, then ONE ```python block — "
                                    "or EXPLORATION DONE."})
                continue
            earlier = st.repeated(m.group(1).strip())
            if earlier:
                if st.too_many_repeats():
                    break
                st.messages.append({"role": "user", "content": repeat_request(earlier)})
                continue
            res = execute(m.group(1).strip(), ds, EXEC_TIMEOUT_S)
            out.attempts += 1
            st.ledger.add(res.findings, st.turn)
            out.error = res.error or out.error
            action = st.after_code(res.error, done)
            if action == 'finish':
                break
            if action == 'fix':
                out.fixes += 1
                st.messages.append({"role": "user", "content": explore_fix_request(res.error, result_digest(res, 6))})
                continue
            st.messages.append({"role": "user", "content": turn_feedback(
                result_digest(res, 12), st.turn, st.max_turns, st.ledger.as_text(), st.plan_text())})
        st.messages.append({"role": "user", "content": summary_request(st.ledger.as_text(), question.text)})
        summary = CODE_RE.sub('', strip_thinking(
            model(fit_messages(compact_messages(st.messages), system, num_ctx, pinned=1), system) or '')).strip()
    except Exception as e:
        out.error = f"{type(e).__name__}: {e}"
    out.answer = summary
    out.passed, out.detail = score_exploration(question, summary + '\n' + st.ledger.as_text())
    out.seconds = time.time() - t0
    return out


def ask(question, ds, model, num_ctx=8192):
    """Put one question through the chat pipeline.

    Args:
        question (Question): The question.
        ds (Dataset): The dataset.
        model (callable): ``(messages, system) -> reply``.
        num_ctx (int): Context window.

    Returns:
        Outcome: The result.
    """
    if question.kind == 'conversation':
        return _ask_conversation(question, ds, model, num_ctx)
    if question.kind == 'explore':
        return _ask_explore(question, ds, model, num_ctx)
    out = Outcome(qid=question.qid, dataset=question.dataset, split=question.split,
                  category=question.category)
    t0 = time.time()
    system = build_system_prompt(ds, num_ctx)
    messages = [{"role": "user", "content": question.text}]
    out.transcript = messages
    results = []
    answer = ''
    try:
        answer = _chat_turn(messages, system, ds, model, num_ctx, out, results)
    except Exception as e:
        out.error = f"{type(e).__name__}: {e}"
    out.answer = answer
    out.passed, out.detail = score(question, results, answer)
    out.seconds = time.time() - t0
    return out


def _summary(outcomes):
    """Print the totals per category and split."""
    def line(label, rows):
        """One summary line."""
        n = sum(o.passed for o in rows)
        return f"  {label:<12} {n:>3}/{len(rows):<3} ({100.0 * n / len(rows):3.0f}%)"
    print()
    for key in ('category', 'split'):
        for value in sorted({getattr(o, key) for o in outcomes}):
            print(line(value, [o for o in outcomes if getattr(o, key) == value]))
    n = sum(o.passed for o in outcomes)
    print(f"\n{n}/{len(outcomes)} passed ({100.0 * n / len(outcomes):.0f}%), "
          f"mean {np.mean([o.seconds for o in outcomes]):.1f}s per question, "
          f"{sum(o.fixes > 0 for o in outcomes)} needed a correction or a redraw.")


def run(model_factory, num_ctx=8192, only=None, split=None, datasets=None, category=None,
        verbose=True):
    """Run the question set.

    Args:
        model_factory (callable): ``question -> model`` where a model is
            ``(messages, system) -> reply``.
        num_ctx (int): Context window given to the prompts.
        only (list): Question ids or template names to run, all by default.
        split (str): ``dev`` or ``test``, both by default.
        datasets (list): Dataset keys, all by default.
        category (list): Categories, all by default.
        verbose (bool): Print each outcome as it finishes.

    Returns:
        list: :class:`Outcome` per question.
    """
    outcomes = []
    for name, spec in DATASETS.items():
        if split and spec['split'] != split:
            continue
        if datasets and name not in datasets:
            continue
        dc, truth, limits = make_variant(name)
        ds = Dataset(dc)
        ds.set_limits(limits)
        for q in build_questions(name, dc, truth):
            if only and q.qid not in only and q.qid.split('.', 1)[1] not in only:
                continue
            if category and q.category not in category:
                continue
            o = ask(q, ds, model_factory(q), num_ctx)
            outcomes.append(o)
            if verbose:
                mark = 'PASS' if o.passed else 'FAIL'
                print(f"{mark}  {o.qid:<28} {o.seconds:6.1f}s  fixes={o.fixes}  {o.detail}"
                      + (f"  [{o.error.splitlines()[0][:80]}]" if o.error else ''), flush=True)
    if verbose and outcomes:
        _summary(outcomes)
    return outcomes


def main(argv=None):
    """Command-line entry point."""
    ap = argparse.ArgumentParser(description="Score a model on the AI assistant benchmark.")
    ap.add_argument('--backend', default='ollama', choices=['ollama', 'mlx', 'custom'])
    ap.add_argument('--model', default='')
    ap.add_argument('--host', default='')
    ap.add_argument('--api-key', default='')
    ap.add_argument('--num-ctx', type=int, default=16384)
    ap.add_argument('--temperature', type=float, default=0.2)
    ap.add_argument('--think', action='store_true', help="switch the model's thinking on (off by default)")
    ap.add_argument('--no-think', action='store_true', help="kept for old commands; thinking is off by default")
    ap.add_argument('--split', choices=['dev', 'test'], default=None, help="only one split")
    ap.add_argument('--dataset', nargs='*', default=None, choices=list(DATASETS),
                    help="only these datasets")
    ap.add_argument('--category', nargs='*', default=None, choices=CATEGORIES,
                    help="only these categories")
    ap.add_argument('--only', nargs='*', default=None,
                    help="question ids (rivers.fig_hist) or template names (fig_hist)")
    ap.add_argument('--reference', action='store_true', help="answer with the reference code")
    ap.add_argument('--out', default='', help="save the outcomes as JSON")
    args = ap.parse_args(argv)
    if args.reference:
        factory = reference_model
    else:
        cfg = {'backend': args.backend, 'model': args.model, 'host': args.host, 'api_key': args.api_key,
               'num_ctx': args.num_ctx, 'temperature': args.temperature,
               'think': bool(args.think and not args.no_think)}
        factory = lambda q: (lambda messages, system: complete(cfg, messages, system))
    outcomes = run(factory, args.num_ctx, args.only, args.split, args.dataset, args.category)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump({'model': args.model or ('reference' if args.reference else ''),
                       'backend': args.backend, 'num_ctx': args.num_ctx,
                       'think': bool(args.think and not args.no_think), 'split': args.split,
                       'outcomes': [asdict(o) for o in outcomes]}, f, indent=2)
    return 0 if outcomes and all(o.passed for o in outcomes) else 1


if __name__ == '__main__':
    sys.exit(main())
