"""Special panels: ternary diagrams, free text and user Python code."""

from __future__ import annotations

import numpy as np

from results.figure_builder.core.common import (
    add_legend, edge_kwargs, finite_mask, float_or_none, label_n, panel_palette, resolve_groups)
from results.figure_builder.core.expressions import ExpressionError, evaluate, pretty


def draw_ternary(fig, ax, panel, table, report, style):
    """Ternary composition plot of three expressions (normalised per particle)."""
    if not all((panel.get(k) or '').strip() for k in 'abc'):
        raise ExpressionError('Set the three corner expressions A, B and C')
    a, b, c = (evaluate(panel[k], table) for k in 'abc')
    s = a + b + c
    groups = resolve_groups(panel, table)
    size = float(panel.get('marker_size') or 12)
    marker = panel.get('marker') or 'o'
    total = 0
    for g in groups:
        m = g.mask & finite_mask(a, b, c) & (s > 0)
        if not m.any():
            continue
        total += int(m.sum())
        ax.scatter(a[m] / s[m], b[m] / s[m], c[m] / s[m], s=size, color=g.color, marker=marker,
                   alpha=float(panel.get('alpha') or 0.7), rasterized=True,
                   label=label_n(g, int(m.sum()), panel),
                   **(edge_kwargs(panel) if marker not in ('+', 'x', '.') else {}))
    ax.set_tlabel(panel.get('a_label') or pretty(panel['a'], table, style))
    ax.set_llabel(panel.get('b_label') or pretty(panel['b'], table, style))
    ax.set_rlabel(panel.get('c_label') or pretty(panel['c'], table, style))
    if panel.get('grid'):
        ax.grid(True, color='#e5e5e5', lw=0.6)
    if panel.get('title'):
        ax.set_title(panel['title'], pad=24)
    report.counts[panel['id']] = total
    add_legend(ax, panel, default_loc='ternary')


def draw_text(fig, ax, panel, table, report, style):
    """A free text block, e.g. a caption or a method note."""
    ax.axis('off')
    size = float_or_none(panel.get('text_size')) or None
    ax.text(0.02, 0.98, panel.get('text') or '', transform=ax.transAxes,
            ha='left', va='top', wrap=True, fontsize=size)
    if panel.get('title'):
        ax.set_title(panel['title'])


def draw_code(fig, ax, panel, table, report, style):
    """Run the user's own matplotlib code against this panel's axes."""
    import pandas as pd
    from scipy import stats
    code = panel.get('code') or ''
    if not code.strip():
        raise ExpressionError('Write some Python in the code box (see the example)')
    df = table.dataframe()
    groups = resolve_groups(panel, table)
    pal = panel_palette(panel)
    ns = {
        'ax': ax, 'fig': fig, 'np': np, 'pd': pd, 'stats': stats,
        'df': df, 'labels': list(table.labels),
        'groups': {g.label: df[g.mask] for g in groups},
        'group_colors': {g.label: g.color for g in groups},
        'color': lambda i: pal[int(i) % len(pal)],
        'col': lambda expr: evaluate(expr, table),
        'report': report.stats.append,
    }
    exec(compile(code, f'<panel {panel["id"]}>', 'exec'), ns)
    report.counts[panel['id']] = len(df)
