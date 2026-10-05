"""Figure Builder rendering engine.

A Figure Builder figure is a plain, JSON-serialisable *spec*::

    {
        'data_type': 'Counts',
        'figure': {'width': 8.0, 'height': 6.0, ...},
        'panels': [panel, ...],
    }

Each panel owns a rectangle on the page (fractions of the figure, origin
top-left, exactly as the user drew it) and a ``kind`` with its options.
:func:`render` draws the whole spec onto a :class:`matplotlib.figure.Figure`
and returns a :class:`RenderReport` with statistics results and any
per-panel errors, so a broken expression in one panel never blanks the
rest of the figure.

The module has no Qt dependency and is fully testable headless.
"""

from __future__ import annotations

import copy
import itertools
import string
import uuid
from dataclasses import dataclass, field

import numpy as np

from results.figure_builder.expressions import (
    ExpressionError, ParticleTable, evaluate, pretty, split_list)

PALETTE = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100',
           '#e87ba4', '#008300', '#4a3aa7', '#e34948']
"""Categorical colours, assigned in fixed order."""

OTHER_COLOR = '#9a9a9a'

PANEL_KINDS = {
    'scatter': 'Scatter (X vs Y)',
    'histogram': 'Histogram',
    'box': 'Box plot',
    'violin': 'Violin plot',
    'bar': 'Bar chart',
    'pie': 'Pie / donut',
    'density': 'Density map (2-D histogram)',
    'ternary': 'Ternary',
    'text': 'Text / annotation',
    'code': 'Python code',
}
"""Panel kinds and their display names."""

GROUP_MODES = {
    'none': 'No grouping',
    'sample': 'By sample',
    'class': 'By classifier class',
    'rules': 'By my rules',
}

STAT_TESTS = {
    'none': 'None',
    'welch': "Welch's t-test",
    'student': "Student's t-test (equal variance)",
    'mannwhitney': 'Mann-Whitney U',
    'ks': 'Kolmogorov-Smirnov',
    'anova': 'One-way ANOVA',
    'kruskal': 'Kruskal-Wallis',
}

PAIRWISE_TESTS = ('welch', 'student', 'mannwhitney', 'ks')

CORRECTIONS = {'none': 'No correction', 'bonferroni': 'Bonferroni', 'holm': 'Holm'}

FIGURE_DEFAULTS = {
    'width': 8.0,
    'height': 6.0,
    'dpi': 300,
    'font_family': 'DejaVu Sans',
    'font_size': 11,
    'title': '',
    'panel_letters': True,
    'letter_style': 'a',
    'label_style': 'isotope',
    'background': '#ffffff',
}

PANEL_DEFAULTS = {
    'id': '',
    'rect': [0.0, 0.0, 1.0, 1.0],
    'kind': 'scatter',
    'title': '',
    'x': '',
    'y': '',
    'y2': '',
    'value': '',
    'a': '',
    'b': '',
    'c': '',
    'x_label': '',
    'y_label': '',
    'y2_label': '',
    'log_x': False,
    'log_y': False,
    'log_y2': False,
    'x_min': '',
    'x_max': '',
    'y_min': '',
    'y_max': '',
    'filter': '',
    'drop_zeros': True,
    'group_by': 'none',
    'rules': [],
    'show_other': True,
    'other_label': 'Other',
    'color': PALETTE[0],
    'y2_color': PALETTE[1],
    'color_by': '',
    'colormap': 'viridis',
    'marker_size': 12.0,
    'alpha': 0.7,
    'bins': 40,
    'hist_style': 'filled',
    'density': False,
    'show_points': False,
    'agg': 'mean',
    'error': 'sd',
    'pie_mode': 'groups',
    'donut': False,
    'show_fit': False,
    'show_r': False,
    'hlines': '',
    'vlines': '',
    'diagonal': False,
    'test': 'none',
    'pairs': 'all',
    'correction': 'none',
    'p_format': 'stars',
    'legend': True,
    'grid': False,
    'text': '',
    'code': '',
}

CODE_EXAMPLE = (
    "ax.scatter(df['total'], df[labels[0]], s=6, color=color(0))\n"
    "ax.set_xscale('log')\n"
    "ax.set_xlabel('Total')\n"
)


@dataclass
class Group:
    """A named subset of particles drawn with one colour."""

    name: str
    mask: np.ndarray
    color: str


@dataclass
class RenderReport:
    """What happened while drawing a figure.

    Attributes:
        stats: Human-readable statistics lines, one per result.
        errors: ``{panel_id: message}`` for panels that could not be drawn.
        counts: ``{panel_id: number of particles plotted}``.
    """

    stats: list = field(default_factory=list)
    errors: dict = field(default_factory=dict)
    counts: dict = field(default_factory=dict)


def new_panel_id() -> str:
    """Return a short unique panel id."""
    return uuid.uuid4().hex[:8]


def make_panel(**overrides) -> dict:
    """Return a full panel dict with defaults, overridden by ``overrides``."""
    panel = copy.deepcopy(PANEL_DEFAULTS)
    panel['id'] = new_panel_id()
    panel.update(copy.deepcopy(overrides))
    return panel


def default_spec() -> dict:
    """Return the spec a new Figure Builder node starts with."""
    return {
        'data_type': 'Counts',
        'figure': copy.deepcopy(FIGURE_DEFAULTS),
        'panels': [make_panel(rect=[0.0, 0.0, 1.0, 1.0], kind='scatter')],
    }


def normalise_spec(spec: dict | None) -> dict:
    """Fill missing keys so older or hand-edited specs always render."""
    out = default_spec() if not isinstance(spec, dict) else copy.deepcopy(spec)
    out.setdefault('data_type', 'Counts')
    fig = copy.deepcopy(FIGURE_DEFAULTS)
    fig.update(out.get('figure') or {})
    out['figure'] = fig
    panels = []
    for p in out.get('panels') or []:
        full = copy.deepcopy(PANEL_DEFAULTS)
        full.update(p)
        if not full.get('id'):
            full['id'] = new_panel_id()
        panels.append(full)
    out['panels'] = panels
    return out


TEMPLATES = {
    'Single': [[0.0, 0.0, 1.0, 1.0]],
    'Side by side': [[0.0, 0.0, 0.5, 1.0], [0.5, 0.0, 0.5, 1.0]],
    'Stacked': [[0.0, 0.0, 1.0, 0.5], [0.0, 0.5, 1.0, 0.5]],
    '2 × 2': [[0.0, 0.0, 0.5, 0.5], [0.5, 0.0, 0.5, 0.5],
              [0.0, 0.5, 0.5, 0.5], [0.5, 0.5, 0.5, 0.5]],
    'Main + inset': [[0.0, 0.0, 1.0, 1.0], [0.55, 0.08, 0.38, 0.38]],
    'Wide + two': [[0.0, 0.0, 1.0, 0.55], [0.0, 0.55, 0.5, 0.45],
                   [0.5, 0.55, 0.5, 0.45]],
}
"""Ready-made layouts, as panel rectangles."""


def apply_template(spec: dict, name: str) -> dict:
    """Re-lay the spec's panels onto a template, keeping their settings in order."""
    rects = TEMPLATES[name]
    panels = list(spec.get('panels') or [])
    out = []
    for i, rect in enumerate(rects):
        if i < len(panels):
            p = dict(panels[i])
            p['rect'] = list(rect)
        else:
            p = make_panel(rect=list(rect))
        out.append(p)
    spec = dict(spec)
    spec['panels'] = out
    return spec


def panel_letter(index: int, style: str) -> str:
    """Return the panel letter for ``index`` in ``style`` (a, A, (a), a))."""
    ch = string.ascii_lowercase[index % 26]
    return {'A': ch.upper(), '(a)': f'({ch})', 'a)': f'{ch})'}.get(style, ch)


def _float_or_none(v):
    """Parse an optional numeric field."""
    try:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _numbers(text) -> list[float]:
    """Parse a comma separated list of numbers, ignoring junk."""
    out = []
    for part in str(text or '').replace(';', ',').split(','):
        v = _float_or_none(part)
        if v is not None:
            out.append(v)
    return out


def resolve_groups(panel: dict, table: ParticleTable) -> list[Group]:
    """Split the particles of ``table`` into the panel's groups.

    The panel filter is applied first. Rule groups use first-match-wins, so
    "points below this threshold" and "everything else" never overlap.
    """
    n = len(table)
    base = np.ones(n, dtype=bool)
    if (panel.get('filter') or '').strip():
        base &= evaluate(panel['filter'], table, as_mask=True)
    mode = panel.get('group_by', 'none')
    groups: list[Group] = []
    if mode == 'sample':
        col = table.column('sample')
        for i, s in enumerate(table.samples()):
            groups.append(Group(str(s), base & (col == s), PALETTE[i % len(PALETTE)]))
    elif mode == 'class':
        col = table.column('class')
        for i, c in enumerate(table.classes()):
            color = table.class_colors.get(c) or (
                OTHER_COLOR if c == 'Unclassified' else PALETTE[i % len(PALETTE)])
            groups.append(Group(str(c), base & (col == c), color))
    elif mode == 'rules':
        remaining = base.copy()
        for i, rule in enumerate(panel.get('rules') or []):
            when = (rule.get('when') or '').strip()
            if not when:
                continue
            m = remaining & evaluate(when, table, as_mask=True)
            remaining &= ~m
            groups.append(Group(rule.get('name') or when,
                                m, rule.get('color') or PALETTE[i % len(PALETTE)]))
        if panel.get('show_other', True):
            groups.append(Group(panel.get('other_label') or 'Other', remaining, OTHER_COLOR))
    else:
        groups.append(Group('All particles', base, panel.get('color') or PALETTE[0]))
    return groups


def _finite(*arrays, log_flags=()):
    """Mask that keeps rows finite in every array (and > 0 where log is set)."""
    mask = np.ones(len(arrays[0]), dtype=bool)
    for i, arr in enumerate(arrays):
        arr = np.asarray(arr, dtype=float)
        mask &= np.isfinite(arr)
        if i < len(log_flags) and log_flags[i]:
            mask &= arr > 0
    return mask


def _nonzero(panel, *arrays):
    """Mask hiding particles where a plotted value is exactly zero (not detected)."""
    mask = np.ones(len(arrays[0]), dtype=bool)
    if panel.get('drop_zeros', True):
        for arr in arrays:
            mask &= np.asarray(arr, dtype=float) != 0
    return mask


def _p_text(p: float, fmt: str) -> str:
    """Format a p-value as stars or a number."""
    if not np.isfinite(p):
        return 'n/a'
    if fmt == 'stars':
        if p < 1e-4:
            return '****'
        if p < 1e-3:
            return '***'
        if p < 1e-2:
            return '**'
        if p < 0.05:
            return '*'
        return 'ns'
    return f'p = {p:.2g}' if p >= 1e-4 else 'p < 0.0001'


def _correct(pvals: list[float], method: str) -> list[float]:
    """Apply a multiple-comparison correction."""
    p = np.asarray(pvals, dtype=float)
    m = len(p)
    if m <= 1 or method == 'none':
        return list(p)
    if method == 'bonferroni':
        return list(np.minimum(p * m, 1.0))
    order = np.argsort(p)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adj[idx] = min(running, 1.0)
    return list(adj)


def run_tests(samples: list[tuple[str, np.ndarray]], panel: dict):
    """Run the panel's statistical test over named samples.

    Returns:
        tuple: ``(pairs, lines)`` where ``pairs`` is a list of
        ``(i, j, p)`` for pairwise tests (empty for omnibus tests) and
        ``lines`` are report strings.
    """
    from scipy import stats
    test = panel.get('test', 'none')
    data = [(n, np.asarray(v, dtype=float)[np.isfinite(v)]) for n, v in samples]
    data = [(n, v) for n, v in data if v.size >= 2]
    lines: list[str] = []
    if test == 'none' or len(data) < 2:
        if test != 'none':
            lines.append(f'{STAT_TESTS[test]}: needs at least two groups with 2+ values')
        return [], lines
    if test in ('anova', 'kruskal'):
        fn = stats.f_oneway if test == 'anova' else stats.kruskal
        res = fn(*[v for _, v in data])
        name = 'F' if test == 'anova' else 'H'
        ns = ', '.join(f'{n} (n={v.size})' for n, v in data)
        lines.append(f'{STAT_TESTS[test]}: {name} = {res.statistic:.3g}, '
                     f'p = {res.pvalue:.3g} — {ns}')
        return [(-1, -1, float(res.pvalue))], lines
    if panel.get('pairs') == 'first':
        combos = [(0, j) for j in range(1, len(data))]
    else:
        combos = list(itertools.combinations(range(len(data)), 2))
    raw = []
    for i, j in combos:
        a, b = data[i][1], data[j][1]
        if test == 'welch':
            res = stats.ttest_ind(a, b, equal_var=False)
        elif test == 'student':
            res = stats.ttest_ind(a, b, equal_var=True)
        elif test == 'mannwhitney':
            res = stats.mannwhitneyu(a, b, alternative='two-sided')
        else:
            res = stats.ks_2samp(a, b)
        raw.append((i, j, float(res.statistic), float(res.pvalue)))
    adjusted = _correct([r[3] for r in raw], panel.get('correction', 'none'))
    pairs = []
    corr = panel.get('correction', 'none')
    for (i, j, stat, p), padj in zip(raw, adjusted):
        extra = f', adjusted ({CORRECTIONS[corr]}) p = {padj:.3g}' if corr != 'none' else ''
        lines.append(f'{STAT_TESTS[test]}: {data[i][0]} (n={data[i][1].size}) vs '
                     f'{data[j][0]} (n={data[j][1].size}): statistic = {stat:.3g}, '
                     f'p = {p:.3g}{extra}')
        names = [n for n, _ in samples]
        pairs.append((names.index(data[i][0]), names.index(data[j][0]), padj))
    return pairs, lines


def _draw_brackets(ax, pairs, positions, panel):
    """Draw significance brackets above the data, scale-agnostically."""
    if not pairs:
        return
    fmt = panel.get('p_format', 'stars')
    if pairs[0][0] == -1:
        ax.text(0.98, 0.98, _p_text(pairs[0][2], 'p'), transform=ax.transAxes,
                ha='right', va='top', fontsize='small')
        return
    step = 0.075
    n = len(pairs)
    reserve = min(0.5, step * n + 0.03)
    lo, hi = ax.get_ylim()
    if ax.get_yscale() == 'log' and lo > 0 and hi > 0:
        llo, lhi = np.log10(lo), np.log10(hi)
        ax.set_ylim(lo, 10 ** (llo + (lhi - llo) / (1 - reserve)))
    else:
        ax.set_ylim(lo, lo + (hi - lo) / (1 - reserve))
    trans = ax.get_xaxis_transform()
    ordered = sorted(pairs, key=lambda t: abs(positions[t[1]] - positions[t[0]]))
    for k, (i, j, p) in enumerate(ordered):
        y = 1 - reserve + 0.02 + k * step
        x1, x2 = positions[i], positions[j]
        ax.plot([x1, x1, x2, x2], [y, y + 0.02, y + 0.02, y], transform=trans,
                color='#333333', lw=1, clip_on=False)
        ax.text((x1 + x2) / 2, y + 0.022, _p_text(p, fmt), transform=trans,
                ha='center', va='bottom', fontsize='small', color='#222222')


def _style_axes(ax, panel, table, style, x_default='', y_default=''):
    """Apply labels, limits, log scales, guide lines and grid."""
    xl = panel.get('x_label') or (pretty(x_default, table, style) if x_default else '')
    yl = panel.get('y_label') or (pretty(y_default, table, style) if y_default else '')
    if xl:
        ax.set_xlabel(xl)
    if yl:
        ax.set_ylabel(yl)
    if panel.get('title'):
        ax.set_title(panel['title'])
    xmin, xmax = _float_or_none(panel.get('x_min')), _float_or_none(panel.get('x_max'))
    ymin, ymax = _float_or_none(panel.get('y_min')), _float_or_none(panel.get('y_max'))
    if xmin is not None or xmax is not None:
        ax.set_xlim(left=xmin, right=xmax)
    if ymin is not None or ymax is not None:
        ax.set_ylim(bottom=ymin, top=ymax)
    for v in _numbers(panel.get('hlines')):
        ax.axhline(v, color='#555555', lw=1, ls='--', zorder=1)
    for v in _numbers(panel.get('vlines')):
        ax.axvline(v, color='#555555', lw=1, ls='--', zorder=1)
    if panel.get('grid'):
        ax.grid(True, color='#e5e5e5', lw=0.6, zorder=0)
        ax.set_axisbelow(True)
    for side in ('top', 'right'):
        if side == 'right' and panel.get('y2') and panel.get('kind') == 'scatter':
            continue
        ax.spines[side].set_visible(False)


def _legend(ax, panel, handles=None, **kwargs):
    """Add a legend when the panel has more than one labelled series."""
    if not panel.get('legend', True):
        return
    h, labels = ax.get_legend_handles_labels()
    if handles:
        h = list(h) + [x for x in handles if x is not None]
        labels = list(labels) + [x.get_label() for x in handles if x is not None]
    if len(h) > 1:
        ax.legend(h, labels, frameon=False, fontsize='small', markerscale=1.5, **kwargs)


def _draw_scatter(fig, ax, panel, table, report, style):
    """Scatter of X against Y, optional right-hand Y2, rules, colour scale and fit."""
    if not panel.get('x') or not panel.get('y'):
        raise ExpressionError('Set both X and Y expressions')
    x = evaluate(panel['x'], table)
    y = evaluate(panel['y'], table)
    log_x, log_y = panel.get('log_x'), panel.get('log_y')
    if log_x:
        ax.set_xscale('log')
    if log_y:
        ax.set_yscale('log')
    groups = resolve_groups(panel, table)
    cvals = evaluate(panel['color_by'], table) if (panel.get('color_by') or '').strip() else None
    size = float(panel.get('marker_size') or 12)
    alpha = float(panel.get('alpha') or 0.7)
    total = 0
    mappable = None
    nz = _nonzero(panel, x, y)
    for g in groups:
        m = g.mask & nz & _finite(x, y, log_flags=(log_x, log_y))
        if cvals is not None:
            m &= np.isfinite(cvals)
        if not m.any():
            continue
        total += int(m.sum())
        label = f'{g.name} (n={int(m.sum())})'
        if cvals is not None:
            mappable = ax.scatter(x[m], y[m], c=cvals[m], cmap=panel.get('colormap') or 'viridis',
                                  s=size, alpha=alpha, linewidths=0, rasterized=True,
                                  label=label if len(groups) > 1 else None)
        else:
            ax.scatter(x[m], y[m], color=g.color, s=size, alpha=alpha, linewidths=0,
                       rasterized=True, label=label)
        if panel.get('show_fit') or panel.get('show_r'):
            _fit(ax, x[m], y[m], g, panel, report, log_x, log_y)
    if mappable is not None:
        cb = fig.colorbar(mappable, ax=ax, pad=0.02, fraction=0.05)
        cb.set_label(pretty(panel['color_by'], table, style))
        cb.outline.set_visible(False)
    if panel.get('diagonal'):
        lo = max(ax.get_xlim()[0], ax.get_ylim()[0])
        hi = min(ax.get_xlim()[1], ax.get_ylim()[1])
        ax.plot([lo, hi], [lo, hi], color='#555555', lw=1, ls=':', zorder=1)
    extra = None
    if (panel.get('y2') or '').strip():
        ax2 = ax.twinx()
        ax2.set_zorder(ax.get_zorder() + 0.1)
        ax2.patch.set_visible(False)
        y2 = evaluate(panel['y2'], table)
        if panel.get('log_y2'):
            ax2.set_yscale('log')
        base = np.zeros(len(table), dtype=bool)
        for g in groups:
            base |= g.mask
        m = base & _nonzero(panel, x, y2) & _finite(x, y2, log_flags=(log_x, panel.get('log_y2')))
        color = panel.get('y2_color') or PALETTE[1]
        extra = ax2.scatter(x[m], y2[m], s=size, facecolors='none', edgecolors=color,
                            linewidths=0.8, alpha=alpha, rasterized=True,
                            label=f'{pretty(panel["y2"], table, style)} (right axis)')
        ax2.set_ylabel(panel.get('y2_label') or pretty(panel['y2'], table, style), color=color)
        ax2.tick_params(axis='y', colors=color)
        ax2.spines['right'].set_color(color)
        ax2.spines['top'].set_visible(False)
    report.counts[panel['id']] = total
    _style_axes(ax, panel, table, style, panel['x'], panel['y'])
    _legend(ax, panel, [extra] if extra is not None else None)


def _fit(ax, x, y, g, panel, report, log_x, log_y):
    """Least-squares line (in plotted space) and Pearson / Spearman r."""
    from scipy import stats
    if x.size < 3:
        return
    fx = np.log10(x) if log_x else x
    fy = np.log10(y) if log_y else y
    res = stats.linregress(fx, fy)
    rho = stats.spearmanr(fx, fy).statistic
    report.stats.append(
        f'{g.name}: slope = {res.slope:.4g}, intercept = {res.intercept:.4g}, '
        f'Pearson r = {res.rvalue:.3f} (R² = {res.rvalue ** 2:.3f}, p = {res.pvalue:.3g}), '
        f'Spearman ρ = {rho:.3f}, n = {x.size}'
        + (' [fit in log space]' if (log_x or log_y) else ''))
    if panel.get('show_fit'):
        xs = np.linspace(fx.min(), fx.max(), 100)
        ys = res.intercept + res.slope * xs
        ax.plot(10 ** xs if log_x else xs, 10 ** ys if log_y else ys,
                color=g.color, lw=1.6, zorder=3)
    if panel.get('show_r'):
        existing = sum(1 for t in ax.texts if getattr(t, '_fb_r', False))
        t = ax.text(0.03, 0.97 - existing * 0.07, f'r = {res.rvalue:.3f}  R² = {res.rvalue ** 2:.3f}',
                    transform=ax.transAxes, ha='left', va='top', color=g.color,
                    fontsize='small')
        t._fb_r = True


def _value_groups(panel, table):
    """Evaluate ``value`` and split it by group, dropping non-finite values."""
    if not (panel.get('value') or '').strip():
        raise ExpressionError('Set the Value expression')
    v = evaluate(panel['value'], table)
    log = panel.get('log_y') if panel.get('kind') in ('box', 'violin', 'bar') else panel.get('log_x')
    out = []
    nz = _nonzero(panel, v)
    for g in resolve_groups(panel, table):
        m = g.mask & nz & _finite(v, log_flags=(log,))
        out.append((g, v[m]))
    return out


def _draw_histogram(fig, ax, panel, table, report, style):
    """Overlaid histograms per group with optional log binning and tests."""
    groups = [(g, v) for g, v in _value_groups(panel, table) if v.size]
    if not groups:
        raise ExpressionError('No finite values to plot')
    allv = np.concatenate([v for _, v in groups])
    bins = max(2, int(panel.get('bins') or 40))
    if panel.get('log_x'):
        ax.set_xscale('log')
        edges = np.logspace(np.log10(allv.min()), np.log10(allv.max()), bins + 1)
    else:
        edges = np.linspace(allv.min(), allv.max(), bins + 1)
    if panel.get('log_y'):
        ax.set_yscale('log')
    filled = panel.get('hist_style', 'filled') == 'filled'
    for g, v in groups:
        ax.hist(v, bins=edges, density=bool(panel.get('density')),
                histtype='stepfilled' if filled else 'step',
                alpha=(0.55 if len(groups) > 1 else 0.85) if filled else 1.0,
                color=g.color, edgecolor=g.color if not filled else 'white',
                linewidth=1.4 if not filled else 0.4, label=f'{g.name} (n={v.size})')
    report.counts[panel['id']] = int(allv.size)
    _, lines = run_tests([(g.name, v) for g, v in groups], panel)
    report.stats.extend(lines)
    ylabel = 'Density' if panel.get('density') else 'Particle count'
    _style_axes(ax, panel, table, style, panel['value'], '')
    if not panel.get('y_label'):
        ax.set_ylabel(ylabel)
    _legend(ax, panel)


def _draw_distribution(fig, ax, panel, table, report, style):
    """Box or violin plot per group, optional points and significance brackets."""
    groups = [(g, v) for g, v in _value_groups(panel, table) if v.size]
    if not groups:
        raise ExpressionError('No finite values to plot')
    log = bool(panel.get('log_y'))
    if log:
        ax.set_yscale('log')
    positions = list(range(1, len(groups) + 1))
    data = [v for _, v in groups]
    if panel['kind'] == 'violin':
        plot_data = [np.log10(v) if log else v for v in data]
        if log:
            ax.set_yscale('linear')
        parts = ax.violinplot(plot_data, positions=positions, showmedians=True,
                              showextrema=False, widths=0.8)
        for body, (g, _) in zip(parts['bodies'], groups):
            body.set_facecolor(g.color)
            body.set_edgecolor(g.color)
            body.set_alpha(0.55)
        parts['cmedians'].set_color('#222222')
        if log:
            from matplotlib.ticker import FuncFormatter, MaxNLocator
            ax.yaxis.set_major_locator(MaxNLocator(integer=True))
            ax.yaxis.set_major_formatter(FuncFormatter(lambda val, _p: f'$10^{{{val:g}}}$'))
    else:
        bp = ax.boxplot(data, positions=positions, widths=0.6, patch_artist=True,
                        showfliers=not panel.get('show_points'),
                        medianprops={'color': '#222222', 'lw': 1.4},
                        flierprops={'marker': '.', 'markersize': 3, 'alpha': 0.4})
        for box, (g, _) in zip(bp['boxes'], groups):
            box.set_facecolor(g.color)
            box.set_alpha(0.6)
            box.set_edgecolor(g.color)
    if panel.get('show_points'):
        rng = np.random.default_rng(0)
        for pos, (g, v) in zip(positions, groups):
            vv = np.log10(v) if (log and panel['kind'] == 'violin') else v
            jitter = rng.uniform(-0.18, 0.18, size=vv.size)
            ax.scatter(pos + jitter, vv, s=4, color=g.color, alpha=0.35, linewidths=0,
                       rasterized=True, zorder=3)
    ax.set_xticks(positions)
    ax.set_xticklabels([f'{g.name}\n(n={v.size})' for g, v in groups])
    report.counts[panel['id']] = int(sum(v.size for v in data))
    pairs, lines = run_tests([(g.name, v) for g, v in groups], panel)
    report.stats.extend(lines)
    _style_axes(ax, panel, table, style, '', panel['value'])
    _draw_brackets(ax, pairs, positions, panel)


def _draw_bar(fig, ax, panel, table, report, style):
    """Grouped bars: one cluster per group, one bar per value expression."""
    exprs = split_list(panel.get('value'))
    if not exprs:
        raise ExpressionError('Set one or more Value expressions (comma separated)')
    groups = resolve_groups(panel, table)
    agg = panel.get('agg', 'mean')
    err = panel.get('error', 'sd')
    log = bool(panel.get('log_y'))
    width = 0.8 / len(exprs)
    positions = np.arange(len(groups), dtype=float)
    per_group_values = [[] for _ in groups]
    for k, expr in enumerate(exprs):
        v = evaluate(expr, table)
        heights, errs = [], []
        for gi, g in enumerate(groups):
            vals = v[g.mask & np.isfinite(v)]
            if k == 0:
                per_group_values[gi] = vals
            if agg == 'count':
                heights.append(float(vals.size))
                errs.append(0.0)
                continue
            if agg == 'sum':
                heights.append(float(vals.sum()) if vals.size else 0.0)
                errs.append(0.0)
                continue
            if vals.size == 0:
                heights.append(np.nan)
                errs.append(0.0)
                continue
            centre = float(np.median(vals) if agg == 'median' else np.mean(vals))
            heights.append(centre)
            if err == 'sd':
                errs.append(float(np.std(vals, ddof=1)) if vals.size > 1 else 0.0)
            elif err == 'sem':
                errs.append(float(np.std(vals, ddof=1) / np.sqrt(vals.size)) if vals.size > 1 else 0.0)
            elif err == 'ci95':
                errs.append(float(1.96 * np.std(vals, ddof=1) / np.sqrt(vals.size)) if vals.size > 1 else 0.0)
            else:
                errs.append(0.0)
        offs = positions - 0.4 + width * (k + 0.5)
        if len(exprs) == 1:
            colors = [g.color for g in groups]
            label = None
        else:
            colors = PALETTE[k % len(PALETTE)]
            label = pretty(expr, table, style)
        show_err = agg in ('mean', 'median') and err != 'none'
        ax.bar(offs, heights, width=width * 0.92, color=colors, label=label,
               yerr=errs if show_err else None, capsize=3 if show_err else 0,
               error_kw={'elinewidth': 1, 'ecolor': '#333333'}, zorder=2)
    if log:
        ax.set_yscale('log')
    ax.set_xticks(positions)
    ax.set_xticklabels([g.name for g in groups])
    report.counts[panel['id']] = int(sum(v.size for v in per_group_values))
    ylab = {'count': 'Particle count', 'sum': 'Sum', 'median': 'Median', 'mean': 'Mean'}[agg]
    if len(exprs) == 1 and agg != 'count':
        ylab = f'{ylab} {pretty(exprs[0], table, style)}'
    _style_axes(ax, panel, table, style)
    if not panel.get('y_label'):
        ax.set_ylabel(ylab)
    if len(exprs) == 1 and agg in ('mean', 'median'):
        pairs, lines = run_tests([(g.name, v) for g, v in zip(groups, per_group_values)], panel)
        report.stats.extend(lines)
        _draw_brackets(ax, pairs, list(positions), panel)
    _legend(ax, panel)


def _draw_pie(fig, ax, panel, table, report, style):
    """Pie or donut of particle counts per group, or of summed values."""
    if panel.get('pie_mode') == 'values':
        exprs = split_list(panel.get('value'))
        if not exprs:
            raise ExpressionError('Set the Value expressions to share out (comma separated)')
        base = np.zeros(len(table), dtype=bool)
        for g in resolve_groups(panel, table):
            base |= g.mask
        sizes, labels, colors = [], [], []
        for k, expr in enumerate(exprs):
            v = evaluate(expr, table)
            sizes.append(float(np.nansum(np.where(base & np.isfinite(v), v, 0))))
            labels.append(pretty(expr, table, style))
            colors.append(PALETTE[k % len(PALETTE)])
        report.counts[panel['id']] = int(base.sum())
    else:
        groups = resolve_groups(panel, table)
        sizes = [float(g.mask.sum()) for g in groups]
        labels = [g.name for g in groups]
        colors = [g.color for g in groups]
        report.counts[panel['id']] = int(sum(sizes))
    keep = [i for i, s in enumerate(sizes) if s > 0]
    if not keep:
        raise ExpressionError('Nothing to share out')
    sizes = [sizes[i] for i in keep]
    labels = [labels[i] for i in keep]
    colors = [colors[i] for i in keep]
    wedge = {'width': 0.42, 'edgecolor': 'white', 'linewidth': 2} if panel.get('donut') \
        else {'edgecolor': 'white', 'linewidth': 2}
    wedges, _t, autotexts = ax.pie(
        sizes, colors=colors, autopct=lambda pct: f'{pct:.1f}%' if pct >= 3 else '',
        startangle=90, counterclock=False, wedgeprops=wedge,
        pctdistance=0.79 if panel.get('donut') else 0.62, textprops={'fontsize': 'small'})
    for t in autotexts:
        t.set_color('white')
        t.set_fontweight('bold')
    ax.set_aspect('equal')
    if panel.get('legend', True):
        total = float(sum(sizes))
        ax.legend(wedges, [f'{lab} ({100 * s / total:.1f}%)' for lab, s in zip(labels, sizes)],
                  loc='upper center', bbox_to_anchor=(0.5, 0.0), ncol=min(2, len(labels)),
                  frameon=False, fontsize='small', handlelength=1.0)
    if panel.get('title'):
        ax.set_title(panel['title'])


def _draw_density(fig, ax, panel, table, report, style):
    """2-D histogram of X against Y, useful when points overplot."""
    if not panel.get('x') or not panel.get('y'):
        raise ExpressionError('Set both X and Y expressions')
    from matplotlib.colors import LogNorm
    x = evaluate(panel['x'], table)
    y = evaluate(panel['y'], table)
    base = np.zeros(len(table), dtype=bool)
    for g in resolve_groups(panel, table):
        base |= g.mask
    log_x, log_y = panel.get('log_x'), panel.get('log_y')
    m = base & _nonzero(panel, x, y) & _finite(x, y, log_flags=(log_x, log_y))
    if m.sum() < 2:
        raise ExpressionError('Not enough finite points')
    xs, ys = x[m], y[m]
    bins = max(4, int(panel.get('bins') or 40))
    xe = np.logspace(np.log10(xs.min()), np.log10(xs.max()), bins + 1) if log_x \
        else np.linspace(xs.min(), xs.max(), bins + 1)
    ye = np.logspace(np.log10(ys.min()), np.log10(ys.max()), bins + 1) if log_y \
        else np.linspace(ys.min(), ys.max(), bins + 1)
    _, _, _, img = ax.hist2d(xs, ys, bins=[xe, ye], cmap=panel.get('colormap') or 'viridis',
                             norm=LogNorm(), rasterized=True)
    if log_x:
        ax.set_xscale('log')
    if log_y:
        ax.set_yscale('log')
    cb = fig.colorbar(img, ax=ax, pad=0.02, fraction=0.05)
    cb.set_label('Particles per bin')
    cb.outline.set_visible(False)
    report.counts[panel['id']] = int(m.sum())
    _style_axes(ax, panel, table, style, panel['x'], panel['y'])


def _draw_ternary(fig, ax, panel, table, report, style):
    """Ternary composition plot of three expressions (normalised per particle)."""
    if not all((panel.get(k) or '').strip() for k in 'abc'):
        raise ExpressionError('Set the three corner expressions A, B and C')
    a, b, c = (evaluate(panel[k], table) for k in 'abc')
    s = a + b + c
    groups = resolve_groups(panel, table)
    size = float(panel.get('marker_size') or 12)
    total = 0
    for g in groups:
        m = g.mask & _finite(a, b, c) & (s > 0)
        if not m.any():
            continue
        total += int(m.sum())
        ax.scatter(a[m] / s[m], b[m] / s[m], c[m] / s[m], s=size, color=g.color,
                   alpha=float(panel.get('alpha') or 0.7), linewidths=0,
                   label=f'{g.name} (n={int(m.sum())})', rasterized=True)
    ax.set_tlabel(pretty(panel['a'], table, style))
    ax.set_llabel(pretty(panel['b'], table, style))
    ax.set_rlabel(pretty(panel['c'], table, style))
    if panel.get('grid'):
        ax.grid(True, color='#e5e5e5', lw=0.6)
    if panel.get('title'):
        ax.set_title(panel['title'], pad=24)
    report.counts[panel['id']] = total
    _legend(ax, panel, loc='upper left', bbox_to_anchor=(-0.08, 1.12))


def _draw_text(fig, ax, panel, table, report, style):
    """A free text block, e.g. a caption or a method note."""
    ax.axis('off')
    ax.text(0.02, 0.98, panel.get('text') or '', transform=ax.transAxes,
            ha='left', va='top', wrap=True)


def _draw_code(fig, ax, panel, table, report, style):
    """Run the user's own matplotlib code against this panel's axes."""
    import pandas as pd
    from scipy import stats
    code = panel.get('code') or ''
    if not code.strip():
        raise ExpressionError('Write some Python in the code box (see the example)')
    df = table.dataframe()
    groups = resolve_groups(panel, table)
    ns = {
        'ax': ax, 'fig': fig, 'np': np, 'pd': pd, 'stats': stats,
        'df': df, 'labels': list(table.labels),
        'groups': {g.name: df[g.mask] for g in groups},
        'group_colors': {g.name: g.color for g in groups},
        'color': lambda i: PALETTE[int(i) % len(PALETTE)],
        'col': lambda expr: evaluate(expr, table),
        'report': report.stats.append,
    }
    exec(compile(code, f'<panel {panel["id"]}>', 'exec'), ns)
    report.counts[panel['id']] = len(df)


DRAWERS = {
    'scatter': _draw_scatter,
    'histogram': _draw_histogram,
    'box': _draw_distribution,
    'violin': _draw_distribution,
    'bar': _draw_bar,
    'pie': _draw_pie,
    'density': _draw_density,
    'ternary': _draw_ternary,
    'text': _draw_text,
    'code': _draw_code,
}


def _inner_rect(rect, fig_w, fig_h, kind, has_y2, has_title, has_cbar):
    """Inset a drawn panel rectangle to leave room for ticks and labels.

    Returns matplotlib ``[left, bottom, width, height]`` in figure fractions.
    """
    x, y, w, h = rect
    if kind == 'pie':
        ml, mr, mb, mt = 0.15, 0.15, 0.6, 0.35 if has_title else 0.15
    elif kind == 'text':
        ml, mr, mb, mt = 0.15, 0.15, 0.15, 0.35 if has_title else 0.15
    elif kind == 'ternary':
        ml, mr, mb, mt = 0.55, 0.55, 0.5, 0.75 if has_title else 0.5
    else:
        ml, mb = 0.75, 0.62
        mr = 0.75 if has_y2 else 0.2
        mr += 0.7 if has_cbar else 0.0
        mt = 0.4 if has_title else 0.18
    left = x + ml / fig_w
    right = x + w - mr / fig_w
    bottom = 1 - (y + h) + mb / fig_h
    top = 1 - y - mt / fig_h
    if right - left < 0.02:
        mid = x + w / 2
        left, right = mid - 0.01, mid + 0.01
    if top - bottom < 0.02:
        mid = 1 - y - h / 2
        bottom, top = mid - 0.01, mid + 0.01
    return [left, bottom, right - left, top - bottom]


def render(fig, spec: dict, table: ParticleTable) -> RenderReport:
    """Draw ``spec`` onto ``fig`` (which is cleared first).

    Args:
        fig: A :class:`matplotlib.figure.Figure`.
        spec: Figure Builder spec (normalised internally).
        table: Particle columns from the upstream stream.

    Returns:
        RenderReport: statistics lines, per-panel errors and counts.
    """
    import matplotlib
    spec = normalise_spec(spec)
    figcfg = spec['figure']
    report = RenderReport()
    fig.clear()
    fw, fh = float(figcfg['width']), float(figcfg['height'])
    fig.set_size_inches(fw, fh, forward=False)
    fig.set_facecolor(figcfg.get('background') or '#ffffff')
    style = figcfg.get('label_style', 'isotope')
    ensure_ternary_projection()
    rc = {
        'font.family': [figcfg.get('font_family') or 'DejaVu Sans', 'DejaVu Sans'],
        'font.size': float(figcfg.get('font_size') or 11),
        'mathtext.default': 'regular',
        'axes.titlesize': 'medium',
        'axes.titleweight': 'bold',
        'axes.linewidth': 0.8,
        'legend.frameon': False,
    }
    with matplotlib.rc_context(rc):
        if figcfg.get('title'):
            fig.suptitle(figcfg['title'], fontweight='bold')
        for index, panel in enumerate(spec['panels']):
            kind = panel.get('kind', 'scatter')
            rect = panel.get('rect') or [0, 0, 1, 1]
            has_cbar = kind == 'density' or (kind == 'scatter' and bool((panel.get('color_by') or '').strip()))
            inner = _inner_rect(rect, fw, fh, kind,
                                kind == 'scatter' and bool((panel.get('y2') or '').strip()),
                                bool(panel.get('title')), has_cbar)
            if index:
                from matplotlib.patches import Rectangle
                fig.add_artist(Rectangle((rect[0], 1 - rect[1] - rect[3]), rect[2], rect[3],
                                         transform=fig.transFigure, zorder=index + 0.5,
                                         facecolor=figcfg.get('background') or '#ffffff',
                                         edgecolor='none'))
            ax = fig.add_axes(inner, projection='ternary' if kind == 'ternary' else None)
            ax.set_zorder(index + 1)
            ax.set_facecolor('white')
            try:
                if len(table) == 0 and kind not in ('text', 'code'):
                    raise ExpressionError('No particles: connect a sample or filter node')
                DRAWERS.get(kind, _draw_scatter)(fig, ax, panel, table, report, style)
            except Exception as exc:
                report.errors[panel['id']] = str(exc)
                ax.cla()
                ax.axis('off')
                ax.text(0.5, 0.5, f'⚠ {exc}', transform=ax.transAxes, ha='center',
                        va='center', color='#b42318', wrap=True, fontsize='small')
            if figcfg.get('panel_letters') and len(spec['panels']) > 1:
                fig.text(rect[0] + 0.06 / fw, 1 - rect[1] - 0.06 / fh,
                         panel_letter(index, figcfg.get('letter_style', 'a')),
                         ha='left', va='top', fontweight='bold',
                         fontsize=float(figcfg.get('font_size') or 11) + 3, zorder=100)
    return report


def ensure_ternary_projection():
    """Register the mpltern projection if the package is available."""
    try:
        import importlib
        importlib.import_module('mpltern')
        return True
    except Exception:
        return False
