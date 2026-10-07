"""Special panels: ternary diagrams, free text and user Python code."""

from __future__ import annotations

import numpy as np

from results.figure_builder.core.common import (
    add_colorbar, add_legend, cmap_name, edge_kwargs, float_or_none, ink, label_n, panel_palette,
    resolve_groups)
from results.figure_builder.core.expressions import ExpressionError, evaluate, plain, pretty


TERNARY_FILTERS = {'any': 'At least one of the three', 'all': 'All three present',
                   'exact': 'Exactly these three (nothing else)'}
"""Which particles a ternary diagram keeps."""


def draw_ternary(fig, ax, panel, table, report, style):
    """Ternary composition plot of three expressions (normalised per particle).

    As in the Ternary node, particles can be required to contain one, all or
    exactly the three corner elements; points can be coloured by any value;
    and each group's mean composition can be marked with a star and reported
    with its spread and the share of the particle the three corners cover.
    """
    if not all((panel.get(k) or '').strip() for k in 'abc'):
        raise ExpressionError('Set the three corner expressions A, B and C')
    a, b, c = (np.nan_to_num(evaluate(panel[k], table), nan=0.0) for k in 'abc')
    a, b, c = np.clip(a, 0, None), np.clip(b, 0, None), np.clip(c, 0, None)
    s = a + b + c
    mode = panel.get('tern_filter', 'any')
    present = (a > 0).astype(int) + (b > 0) + (c > 0)
    keep = s > 0
    if mode == 'all':
        keep &= present == 3
    elif mode == 'exact':
        keep &= (present == 3) & (table.column('n_elements') == 3)
    groups = resolve_groups(panel, table)
    size = float(panel.get('marker_size') or 12)
    marker = panel.get('marker') or 'o'
    cvals = evaluate(panel['color_by'], table) if (panel.get('color_by') or '').strip() else None
    norm = None
    if cvals is not None:
        from matplotlib.colors import LogNorm, Normalize
        ok = cvals[np.isfinite(cvals) & keep]
        if panel.get('cbar_log') and (ok > 0).any():
            norm = LogNorm(vmin=float(ok[ok > 0].min()), vmax=float(ok.max()))
        elif ok.size:
            norm = Normalize(vmin=float(ok.min()), vmax=float(ok.max()))
    total = 0
    mappable = None
    stars = []
    tot_all = table.column('total') if len(table) else np.zeros(0)
    for g in groups:
        m = g.mask & keep
        if cvals is not None:
            m &= np.isfinite(cvals)
        if not m.any():
            continue
        total += int(m.sum())
        ta, tb, tc = a[m] / s[m], b[m] / s[m], c[m] / s[m]
        kw = dict(s=size, marker=marker, alpha=float(panel.get('alpha') or 0.7), rasterized=True,
                  label=label_n(g, int(m.sum()), panel),
                  **(edge_kwargs(panel) if marker not in ('+', 'x', '.') else {}))
        if cvals is not None:
            mappable = ax.scatter(ta, tb, tc, c=cvals[m], cmap=cmap_name(panel), norm=norm, **kw)
        else:
            ax.scatter(ta, tb, tc, color=g.color, **kw)
        if panel.get('tern_mean'):
            mean = np.array([ta.mean(), tb.mean(), tc.mean()])
            sd = np.array([ta.std(ddof=1), tb.std(ddof=1), tc.std(ddof=1)]) if ta.size > 1 else np.zeros(3)
            stars.append((g, mean))
            cover = ''
            if tot_all.size:
                with np.errstate(all='ignore'):
                    share = 100 * s[m] / tot_all[m]
                share = share[np.isfinite(share)]
                if share.size:
                    cover = f'; the three cover {np.mean(share):.1f} ± {np.std(share):.1f}% of the particle'
            names = [panel.get(f'{k}_label') or plain(pretty(panel[k], table, style, with_unit=False))
                     for k in 'abc']
            report.stats.append(f'{g.label}: mean composition ' + ', '.join(
                f'{n} {100 * mu:.1f} ± {100 * sdv:.1f}%' for n, mu, sdv in zip(names, mean, sd))
                + f' (n = {ta.size}){cover}')
    _draw_references(ax, panel, table, report)
    for g, mean in stars:
        ax.scatter([mean[0]], [mean[1]], [mean[2]], marker='*', s=size * 14 + 120, color=g.color,
                   edgecolors=ink('#111827'), linewidths=1.0, zorder=10)
    ax.set_tlabel(panel.get('a_label') or pretty(panel['a'], table, style))
    ax.set_llabel(panel.get('b_label') or pretty(panel['b'], table, style))
    ax.set_rlabel(panel.get('c_label') or pretty(panel['c'], table, style))
    if panel.get('grid'):
        ax.grid(True, color='#e5e5e5', lw=0.6)
    if panel.get('title'):
        ax.set_title(panel['title'], pad=24)
    report.counts[panel['id']] = total
    if total == 0:
        raise ExpressionError('No particle passes the ternary filter')
    if mappable is not None:
        add_colorbar(fig, ax, mappable, panel, report, pretty(panel['color_by'], table, style))
    add_legend(ax, panel, default_loc='ternary')


def corner_basis(panel, table) -> str | None:
    """``'moles'`` or ``'mass'`` when all three corners are single elements in that basis.

    Reference points are only comparable with particles plotted in moles or
    mass; counts depend on each isotope's sensitivity.
    """
    import re
    from results.figure_builder.core.expressions import QUANTITY_PREFIXES
    from results.figure_builder.core.references import symbol_of
    bases = set()
    for k in 'abc':
        expr = (panel.get(k) or '').strip()
        m = re.match(r'^(\w+):', expr)
        prefix = m.group(1) if m and m.group(1) in QUANTITY_PREFIXES else table.default_prefix
        try:
            symbol_of(expr)
        except ValueError:
            return None
        bases.add({'moles': 'moles', 'pmoles': 'moles', 'mass': 'mass', 'pmass': 'mass'}.get(prefix))
    return bases.pop() if len(bases) == 1 and None not in bases else None


def _halo():
    """White outline that keeps a label readable over dense points."""
    from matplotlib import patheffects
    return [patheffects.withStroke(linewidth=2.6, foreground='white')]


def _draw_references(ax, panel, table, report):
    """Mark reference minerals, the upper crust and a bulk value on a ternary.

    Each reference is placed from its formula (or the crust table) in the
    same basis as the corners, so the points sit where a particle of that
    composition would. Nothing is drawn, and the report says why, when the
    corners are not single elements in moles or mass.
    """
    from results.figure_builder.core import references as R
    entries = R.split_entries(panel.get('tern_refs') or '')
    bulk_text = (panel.get('tern_bulk') or '').strip()
    if not entries and not bulk_text:
        return
    basis = corner_basis(panel, table)
    color = panel.get('tern_ref_color') or '#1f2937'
    if entries:
        if basis is None:
            report.stats.append('Reference minerals need the three corners as single elements '
                                'in moles or mass (e.g. moles:Al), so they were not drawn')
        else:
            symbols = [R.symbol_of(panel[k]) for k in 'abc']
            placed = []
            for label, ref in entries:
                try:
                    t, l, r = R.composition(ref, symbols, basis)
                except ValueError as exc:
                    report.stats.append(f'Reference {label}: {exc}')
                    continue
                ax.scatter([t], [l], [r], marker='D', s=46, color=color, edgecolors='white',
                           linewidths=0.8, zorder=11)
                txt = ax.text(t, l, r, f'  {label}', fontsize='small', color=color, ha='left',
                              va='center', zorder=12, path_effects=_halo())
                txt._fb_cell = True
                placed.append(f'{label} ({100 * t:.0f}/{100 * l:.0f}/{100 * r:.0f} %)')
            if placed:
                report.stats.append(f'Reference points ({basis} basis): ' + ', '.join(placed))
    if bulk_text:
        try:
            parts = [float(x) for x in bulk_text.replace(';', ',').split(',')]
            if len(parts) != 3 or min(parts) < 0 or sum(parts) <= 0:
                raise ValueError
        except ValueError:
            report.stats.append('Bulk value: give three non-negative numbers, A, B, C')
            return
        t, l, r = (x / sum(parts) for x in parts)
        ax.plot([t], [l], [r], marker='o', ms=11, fillstyle='left', color='#dc2626',
                markeredgecolor=ink('#111827'), markerfacecoloralt='white', linestyle='none', zorder=12)
        txt = ax.text(t, l, r, '   bulk', fontsize='small', color='#dc2626', ha='left', va='center',
                      zorder=12, path_effects=_halo())
        txt._fb_cell = True


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
