"""Group comparisons and significance brackets for Figure Builder panels."""

from __future__ import annotations

import itertools

import numpy as np

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


def p_text(p: float, fmt: str) -> str:
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


def correct(pvals: list[float], method: str) -> list[float]:
    """Apply a multiple-comparison correction (none, Bonferroni or Holm)."""
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

    Args:
        samples: ``[(name, values), ...]`` in display order.
        panel: Panel dict carrying ``test``, ``pairs``, ``correction`` and
            ``test_log``. With ``test_log`` the test runs on log10 of the
            positive values, which suits log-normal particle signals.

    Returns:
        tuple: ``(pairs, lines)`` where ``pairs`` is a list of ``(i, j, p)``
        indices into ``samples`` (``(-1, -1, p)`` for an omnibus test) and
        ``lines`` are report strings.
    """
    from scipy import stats
    test = panel.get('test', 'none')
    data = [(n, np.asarray(v, dtype=float)) for n, v in samples]
    data = [(n, v[np.isfinite(v)]) for n, v in data]
    if panel.get('test_log'):
        data = [(n, np.log10(v[v > 0])) for n, v in data]
    data = [(n, v) for n, v in data if v.size >= 2]
    lines: list[str] = []
    label = STAT_TESTS.get(test, test) + (' on log10 values' if panel.get('test_log') else '')
    if test == 'none' or len(data) < 2:
        if test != 'none':
            lines.append(f'{label}: needs at least two groups with 2+ values')
        return [], lines
    if test in ('anova', 'kruskal'):
        fn = stats.f_oneway if test == 'anova' else stats.kruskal
        res = fn(*[v for _, v in data])
        name = 'F' if test == 'anova' else 'H'
        ns = ', '.join(f'{n} (n={v.size})' for n, v in data)
        lines.append(f'{label}: {name} = {res.statistic:.3g}, '
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
    method = panel.get('correction', 'none')
    adjusted = correct([r[3] for r in raw], method)
    names = [n for n, _ in samples]
    pairs = []
    for (i, j, stat, p), padj in zip(raw, adjusted):
        extra = f', adjusted ({CORRECTIONS[method]}) p = {padj:.3g}' if method != 'none' else ''
        lines.append(f'{label}: {data[i][0]} (n={data[i][1].size}) vs '
                     f'{data[j][0]} (n={data[j][1].size}): statistic = {stat:.3g}, '
                     f'p = {p:.3g}{extra}')
        pairs.append((names.index(data[i][0]), names.index(data[j][0]), padj))
    return pairs, lines


def draw_brackets(ax, pairs, positions, panel):
    """Draw significance brackets above the data, for linear or log axes.

    Room is made by stretching the top of the y-range, then brackets are
    drawn in axes-fraction coordinates so they look the same on any scale.
    """
    if not pairs:
        return
    fmt = panel.get('p_format', 'stars')
    hide_ns = bool(panel.get('hide_ns'))
    if pairs[0][0] == -1:
        ax.text(0.98, 0.98, p_text(pairs[0][2], 'p'), transform=ax.transAxes,
                ha='right', va='top', fontsize='small')
        return
    if hide_ns:
        pairs = [t for t in pairs if t[2] < 0.05]
        if not pairs:
            return
    step = 0.075
    reserve = min(0.5, step * len(pairs) + 0.03)
    lo, hi = ax.get_ylim()
    if ax.get_yscale() == 'log' and lo > 0 and hi > 0:
        llo, lhi = np.log10(lo), np.log10(hi)
        ax.set_ylim(lo, 10 ** (llo + (lhi - llo) / (1 - reserve)))
    else:
        ax.set_ylim(lo, lo + (hi - lo) / (1 - reserve))
    trans = ax.get_xaxis_transform()
    ordered = sorted(pairs, key=lambda t: abs(positions[t[1]] - positions[t[0]]))
    color = panel.get('bracket_color') or '#333333'
    for k, (i, j, p) in enumerate(ordered):
        y = 1 - reserve + 0.02 + k * step
        x1, x2 = positions[i], positions[j]
        ax.plot([x1, x1, x2, x2], [y, y + 0.02, y + 0.02, y], transform=trans,
                color=color, lw=1, clip_on=False)
        ax.text((x1 + x2) / 2, y + 0.022, p_text(p, fmt), transform=trans,
                ha='center', va='bottom', fontsize='small', color=color)
