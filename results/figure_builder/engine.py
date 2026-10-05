"""Figure Builder rendering engine.

A Figure Builder figure is a plain, JSON-serialisable *spec*::

    {
        'data_type': 'Counts',
        'variables': [{'name': 'ratio', 'expr': 'Fe/Cu'}, ...],
        'figure': {'width': 8.0, 'height': 6.0, 'palette': 'Default', ...},
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
import logging
import string
import uuid
from dataclasses import dataclass, field

import numpy as np

from results.figure_builder.expressions import (
    ExpressionError, ParticleTable, evaluate, pretty, split_list)
from results.figure_builder.stats import (
    CORRECTIONS, PAIRWISE_TESTS, STAT_TESTS, correct, draw_brackets, p_text, run_tests)
from results.figure_builder.styles import (
    PALETTES, STYLE_PRESETS, TEMPLATES, apply_style_preset, palette_colors)

__all__ = [
    'CORRECTIONS', 'PAIRWISE_TESTS', 'STAT_TESTS', 'PALETTES', 'STYLE_PRESETS',
    'TEMPLATES', 'apply_style_preset', 'correct', 'p_text', 'run_tests',
]

PALETTE = PALETTES['Default']
"""The default categorical palette."""

OTHER_COLOR = '#9a9a9a'

PANEL_KINDS = {
    'scatter': 'Scatter (X vs Y)',
    'line': 'Line / trend (binned)',
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

FIGURE_DEFAULTS = {
    'width': 8.0,
    'height': 6.0,
    'dpi': 300,
    'font_family': 'DejaVu Sans',
    'font_size': 11,
    'title_size': 0,
    'label_size': 0,
    'tick_size': 0,
    'axes_linewidth': 0.8,
    'title': '',
    'panel_letters': True,
    'letter_style': 'a',
    'letter_size': 0,
    'label_style': 'isotope',
    'background': '#ffffff',
    'palette': 'Default',
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
    'group_colors': {},
    'group_labels': {},
    'hidden_groups': [],
    'group_order': [],
    'show_n': True,
    'color': PALETTE[0],
    'y2_color': PALETTE[1],
    'color_by': '',
    'size_by': '',
    'colormap': 'viridis',
    'reverse_cmap': False,
    'marker': 'o',
    'marker_size': 12.0,
    'edge_color': '#ffffff',
    'edge_width': 0.0,
    'alpha': 0.7,
    'line_width': 1.6,
    'line_style': '-',
    'bins': 40,
    'hist_style': 'filled',
    'density': False,
    'cumulative': False,
    'kde': False,
    'show_points': False,
    'notch': False,
    'show_mean': False,
    'agg': 'mean',
    'error': 'sd',
    'band': 'sem',
    'horizontal': False,
    'stacked': False,
    'pie_mode': 'groups',
    'donut': False,
    'show_fit': False,
    'show_r': False,
    'hlines': '',
    'vlines': '',
    'diagonal': False,
    'series': [],
    'annotations': [],
    'test': 'none',
    'pairs': 'all',
    'correction': 'none',
    'p_format': 'stars',
    'hide_ns': False,
    'legend': True,
    'legend_loc': 'best',
    'legend_cols': 1,
    'legend_title': '',
    'legend_size': 'small',
    'grid': False,
    'frame': 'open',
    'tick_dir': 'out',
    'minor_ticks': False,
    'sci_x': False,
    'sci_y': False,
    'aspect_equal': False,
    'xtick_rotation': 0,
    'panel_bg': '#ffffff',
    'text': '',
    'text_size': 0,
    'code': '',
}

CODE_EXAMPLE = (
    "ax.scatter(df['total'], df[labels[0]], s=6, color=color(0))\n"
    "ax.set_xscale('log')\n"
    "ax.set_xlabel('Total')\n"
)


@dataclass
class Group:
    """A subset of particles drawn with one colour.

    Attributes:
        key: Stable identity (sample name, class or rule name).
        label: What legends and tick labels show (user-renamable).
        mask: Boolean particle mask.
        color: Matplotlib colour.
    """

    key: str
    label: str
    mask: np.ndarray
    color: str

    @property
    def name(self) -> str:
        """Display name (alias of ``label``)."""
        return self.label


@dataclass
class RenderReport:
    """What happened while drawing a figure.

    Attributes:
        stats: Human-readable statistics lines, one per result.
        errors: ``{panel_id: message}`` for panels that could not be drawn.
        counts: ``{panel_id: number of particles plotted}``.
        variable_errors: ``{variable: message}`` for invalid variables.
        axes: ``{panel_id: [left, bottom, width, height]}`` drawn axes boxes.
    """

    stats: list = field(default_factory=list)
    errors: dict = field(default_factory=dict)
    counts: dict = field(default_factory=dict)
    variable_errors: dict = field(default_factory=dict)
    axes: dict = field(default_factory=dict)


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
        'variables': [],
        'figure': copy.deepcopy(FIGURE_DEFAULTS),
        'panels': [make_panel(rect=[0.0, 0.0, 1.0, 1.0], kind='scatter')],
    }


def normalise_spec(spec: dict | None) -> dict:
    """Return a full copy of ``spec`` with every missing key filled in."""
    out = default_spec() if not isinstance(spec, dict) else copy.deepcopy(spec)
    out.setdefault('data_type', 'Counts')
    out['variables'] = [dict(v) for v in (out.get('variables') or []) if isinstance(v, dict)]
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


def strip_spec(spec: dict) -> dict:
    """Return ``spec`` without values equal to their defaults (compact designs)."""
    spec = normalise_spec(spec)
    fig = {k: v for k, v in spec['figure'].items() if FIGURE_DEFAULTS.get(k) != v}
    panels = []
    for p in spec['panels']:
        panels.append({k: v for k, v in p.items()
                       if k in ('id', 'rect', 'kind') or PANEL_DEFAULTS.get(k) != v})
    return {'data_type': spec['data_type'], 'variables': spec['variables'],
            'figure': fig, 'panels': panels}


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
    return {'A': ch.upper(), '(a)': f'({ch})', 'a)': f'{ch})', '(A)': f'({ch.upper()})'}.get(style, ch)


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


def _palette(panel) -> list[str]:
    """The palette injected into ``panel`` by :func:`render`."""
    return panel.get('_palette') or PALETTE


def candidate_groups(panel: dict, table: ParticleTable) -> list[Group]:
    """Every group the panel's grouping produces, before hiding and reordering."""
    n = len(table)
    base = np.ones(n, dtype=bool)
    if (panel.get('filter') or '').strip():
        base &= evaluate(panel['filter'], table, as_mask=True)
    pal = _palette(panel)
    mode = panel.get('group_by', 'none')
    groups: list[Group] = []
    if mode == 'sample':
        col = table.column('sample')
        for i, s in enumerate(table.samples()):
            groups.append(Group(str(s), str(s), base & (col == s), pal[i % len(pal)]))
    elif mode == 'class':
        col = table.column('class')
        for i, c in enumerate(table.classes()):
            color = table.class_colors.get(c) or (
                OTHER_COLOR if c == 'Unclassified' else pal[i % len(pal)])
            groups.append(Group(str(c), str(c), base & (col == c), color))
    elif mode == 'rules':
        remaining = base.copy()
        for i, rule in enumerate(panel.get('rules') or []):
            when = (rule.get('when') or '').strip()
            if not when:
                continue
            m = remaining & evaluate(when, table, as_mask=True)
            remaining &= ~m
            name = rule.get('name') or when
            groups.append(Group(name, name, m, rule.get('color') or pal[i % len(pal)]))
        if panel.get('show_other', True):
            other = panel.get('other_label') or 'Other'
            groups.append(Group('__other__', other, remaining, OTHER_COLOR))
    else:
        groups.append(Group('__all__', 'All particles', base, panel.get('color') or pal[0]))
    return groups


def resolve_groups(panel: dict, table: ParticleTable) -> list[Group]:
    """Split the particles into the panel's groups, applying user overrides.

    The panel filter is applied first. Rule groups use first-match-wins, so
    "points below this threshold" and "everything else" never overlap.
    Per-group colours, display names, hidden groups and order chosen in the
    Groups tab are applied last.
    """
    groups = candidate_groups(panel, table)
    colors = panel.get('group_colors') or {}
    labels = panel.get('group_labels') or {}
    hidden = set(panel.get('hidden_groups') or [])
    order = list(panel.get('group_order') or [])
    single = panel.get('group_by', 'none') == 'none'
    out = []
    for g in groups:
        if g.key in hidden:
            continue
        if g.key in colors and not single:
            g.color = colors[g.key]
        if labels.get(g.key):
            g.label = labels[g.key]
        out.append(g)
    if order:
        rank = {k: i for i, k in enumerate(order)}
        out.sort(key=lambda g: rank.get(g.key, len(rank)))
    return out


def _finite(*arrays, log_flags=()):
    """Mask keeping rows finite in every array (and > 0 where log is set)."""
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


def _label_n(g: Group, n: int, panel) -> str:
    """Legend label for a group, with its count when requested."""
    return f'{g.label} (n={n})' if panel.get('show_n', True) else g.label


def _cmap(panel) -> str:
    """Colour map name, reversed when asked."""
    name = panel.get('colormap') or 'viridis'
    return f'{name}_r' if panel.get('reverse_cmap') else name


def _edge(panel) -> dict:
    """Marker edge keyword arguments."""
    width = float(panel.get('edge_width') or 0)
    if width <= 0:
        return {'linewidths': 0}
    return {'linewidths': width, 'edgecolors': panel.get('edge_color') or '#ffffff'}


def _legend_kwargs(panel, n_items: int, default_loc: str | None = None) -> dict:
    """Matplotlib legend placement keywords for the panel's legend setting."""
    loc = panel.get('legend_loc') or 'best'
    if loc == 'best' and default_loc:
        loc = default_loc
    cols = max(1, int(panel.get('legend_cols') or 1))
    kw = {'frameon': False, 'fontsize': panel.get('legend_size') or 'small', 'ncol': cols}
    if panel.get('legend_title'):
        kw['title'] = panel['legend_title']
    if loc == 'outside right':
        kw.update(loc='upper left', bbox_to_anchor=(1.02, 1.0), borderaxespad=0)
    elif loc == 'below':
        kw.update(loc='upper center', bbox_to_anchor=(0.5, -0.16),
                  ncol=max(cols, min(4, n_items)))
    elif loc == 'above':
        kw.update(loc='lower center', bbox_to_anchor=(0.5, 1.02),
                  ncol=max(cols, min(4, n_items)))
    elif loc == 'ternary':
        kw.update(loc='upper left', bbox_to_anchor=(-0.08, 1.12))
    else:
        kw['loc'] = loc
    return kw


def _legend(ax, panel, extra=None, default_loc=None, min_items=2):
    """Add a legend when the panel has enough labelled series."""
    if not panel.get('legend', True):
        return
    h, labels = ax.get_legend_handles_labels()
    for x in extra or []:
        if x is not None:
            h.append(x)
            labels.append(x.get_label())
    if len(h) >= min_items:
        ax.legend(h, labels, markerscale=1.4, **_legend_kwargs(panel, len(h), default_loc))


def _style_axes(ax, panel, table, style, x_default='', y_default='', swap=False):
    """Apply labels, limits, scales' cosmetics, guide lines, frame and ticks."""
    xl = panel.get('x_label') or (pretty(x_default, table, style) if x_default else '')
    yl = panel.get('y_label') or (pretty(y_default, table, style) if y_default else '')
    if swap:
        xl, yl = yl, xl
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
        ax.grid(True, which='major', color='#e5e5e5', lw=0.6, zorder=0)
        ax.set_axisbelow(True)
    frame = panel.get('frame', 'open')
    keep_right = bool(panel.get('y2')) and panel.get('kind') == 'scatter'
    for side in ('top', 'right', 'left', 'bottom'):
        if frame == 'box':
            visible = True
        elif frame == 'none':
            visible = False
        else:
            visible = side in ('left', 'bottom') or (side == 'right' and keep_right)
        ax.spines[side].set_visible(visible)
    if panel.get('minor_ticks'):
        ax.minorticks_on()
    ax.tick_params(which='both', direction=panel.get('tick_dir') or 'out',
                   top=frame == 'box', right=frame == 'box' and not keep_right)
    for axis, key in (('x', 'sci_x'), ('y', 'sci_y')):
        scale = ax.get_xscale() if axis == 'x' else ax.get_yscale()
        if panel.get(key) and scale == 'linear':
            ax.ticklabel_format(style='sci', axis=axis, scilimits=(0, 0), useMathText=True)
    rot = float(panel.get('xtick_rotation') or 0)
    if rot:
        for t in ax.get_xticklabels():
            t.set_rotation(rot)
            t.set_ha('right' if 0 < rot < 90 else 'center')
    if panel.get('aspect_equal'):
        ax.set_aspect('equal', adjustable='datalim')


def _annotate(ax, panel):
    """Draw the panel's free text annotations, with optional arrows."""
    for a in panel.get('annotations') or []:
        text = a.get('text') or ''
        if not text.strip():
            continue
        coords = 'data' if a.get('coords') == 'data' else 'axes fraction'
        x = _float_or_none(a.get('x'))
        y = _float_or_none(a.get('y'))
        if x is None or y is None:
            continue
        kw = {'fontsize': _float_or_none(a.get('size')) or 'medium',
              'color': a.get('color') or '#222222',
              'fontweight': 'bold' if a.get('bold') else 'normal',
              'ha': 'left', 'va': 'center', 'zorder': 20}
        if a.get('box'):
            kw['bbox'] = {'boxstyle': 'round,pad=0.3', 'fc': 'white', 'ec': '#999999', 'lw': 0.6}
        ax_, ay_ = _float_or_none(a.get('arrow_x')), _float_or_none(a.get('arrow_y'))
        if ax_ is not None and ay_ is not None:
            ax.annotate(text, xy=(ax_, ay_), xytext=(x, y), xycoords=coords,
                        textcoords=coords, arrowprops={'arrowstyle': '->', 'color': kw['color'],
                                                       'lw': 1}, **kw)
        else:
            ax.annotate(text, xy=(x, y), xycoords=coords, **kw)


def _sizes(panel, table, base: float):
    """Per-particle marker sizes from ``size_by`` (None when unused)."""
    expr = (panel.get('size_by') or '').strip()
    if not expr:
        return None
    v = evaluate(expr, table)
    ok = np.isfinite(v)
    if not ok.any():
        return None
    lo, hi = np.nanpercentile(v[ok], [2, 98])
    span = hi - lo if hi > lo else 1.0
    t = np.clip((np.where(ok, v, lo) - lo) / span, 0, 1)
    return base * 0.25 + t * base * 3.5


def _draw_scatter(fig, ax, panel, table, report, style):
    """Scatter of X against Y with rules, colour/size scales, overlays and a right axis."""
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
    sizes = _sizes(panel, table, size)
    alpha = float(panel.get('alpha') or 0.7)
    marker = panel.get('marker') or 'o'
    edge = _edge(panel) if marker not in ('+', 'x', '.') else {}
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
        s = sizes[m] if sizes is not None else size
        if cvals is not None:
            mappable = ax.scatter(x[m], y[m], c=cvals[m], cmap=_cmap(panel), s=s, alpha=alpha,
                                  marker=marker, rasterized=True,
                                  label=_label_n(g, int(m.sum()), panel) if len(groups) > 1 else None,
                                  **edge)
        else:
            ax.scatter(x[m], y[m], color=g.color, s=s, alpha=alpha, marker=marker,
                       rasterized=True, label=_label_n(g, int(m.sum()), panel), **edge)
        if panel.get('show_fit') or panel.get('show_r'):
            _fit(ax, x[m], y[m], g, panel, report, log_x, log_y)
    _draw_series(ax, panel, table, style, log_x, log_y)
    if mappable is not None:
        cb = fig.colorbar(mappable, ax=ax, pad=0.02, fraction=0.05)
        cb.ax.set_zorder(ax.get_zorder())
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
                            linewidths=0.8, alpha=alpha, marker=marker if marker not in ('+', 'x', '.') else 'o',
                            rasterized=True,
                            label=f'{pretty(panel["y2"], table, style)} (right axis)')
        ax2.set_ylabel(panel.get('y2_label') or pretty(panel['y2'], table, style), color=color)
        ax2.tick_params(axis='y', colors=color, direction=panel.get('tick_dir') or 'out')
        ax2.spines['right'].set_color(color)
        for side in ('top', 'left', 'bottom'):
            ax2.spines[side].set_visible(False)
    report.counts[panel['id']] = total
    _style_axes(ax, panel, table, style, panel['x'], panel['y'])
    _legend(ax, panel, [extra] if extra is not None else None)


def _draw_series(ax, panel, table, style, log_x, log_y):
    """Extra X/Y series drawn on top of a scatter panel."""
    pal = _palette(panel)
    for i, s in enumerate(panel.get('series') or []):
        xe, ye = (s.get('x') or '').strip(), (s.get('y') or '').strip()
        if not xe or not ye:
            continue
        x = evaluate(xe, table)
        y = evaluate(ye, table)
        m = _nonzero(panel, x, y) & _finite(x, y, log_flags=(log_x, log_y))
        if (s.get('filter') or '').strip():
            m &= evaluate(s['filter'], table, as_mask=True)
        if not m.any():
            continue
        color = s.get('color') or pal[(i + 2) % len(pal)]
        label = s.get('label') or f'{pretty(ye, table, style)} vs {pretty(xe, table, style)}'
        mode = s.get('style') or 'points'
        xs, ys = x[m], y[m]
        if mode in ('line', 'points+line'):
            order = np.argsort(xs)
            ax.plot(xs[order], ys[order], color=color, lw=float(panel.get('line_width') or 1.6),
                    ls=panel.get('line_style') or '-', label=label if mode == 'line' else None,
                    zorder=4)
        if mode in ('points', 'points+line'):
            mk = s.get('marker') or 'o'
            ax.scatter(xs, ys, color=color, s=float(s.get('size') or panel.get('marker_size') or 12),
                       marker=mk, alpha=float(panel.get('alpha') or 0.7),
                       linewidths=1.2 if mk in ('+', 'x', '.') else 0, rasterized=True,
                       label=f'{label} (n={xs.size})', zorder=4)


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
        f'{g.label}: slope = {res.slope:.4g}, intercept = {res.intercept:.4g}, '
        f'Pearson r = {res.rvalue:.3f} (R² = {res.rvalue ** 2:.3f}, p = {res.pvalue:.3g}), '
        f'Spearman ρ = {rho:.3f}, n = {x.size}'
        + (' [fit in log space]' if (log_x or log_y) else ''))
    if panel.get('show_fit'):
        xs = np.linspace(fx.min(), fx.max(), 100)
        ys = res.intercept + res.slope * xs
        ax.plot(10 ** xs if log_x else xs, 10 ** ys if log_y else ys,
                color=g.color, lw=float(panel.get('line_width') or 1.6),
                ls=panel.get('line_style') or '-', zorder=3)
    if panel.get('show_r'):
        existing = sum(1 for t in ax.texts if getattr(t, '_fb_r', False))
        t = ax.text(0.03, 0.97 - existing * 0.07,
                    f'r = {res.rvalue:.3f}  R² = {res.rvalue ** 2:.3f}',
                    transform=ax.transAxes, ha='left', va='top', color=g.color,
                    fontsize='small')
        t._fb_r = True


def _bin_edges(values, bins, log):
    """Linear or logarithmic bin edges spanning ``values``."""
    lo, hi = float(np.min(values)), float(np.max(values))
    if hi <= lo:
        hi = lo + (abs(lo) * 0.1 or 1.0)
    if log:
        return np.logspace(np.log10(lo), np.log10(hi), bins + 1)
    return np.linspace(lo, hi, bins + 1)


def _draw_line(fig, ax, panel, table, report, style):
    """Binned trend: Y aggregated in bins of X, one line per group with a band."""
    if not (panel.get('x') or '').strip():
        raise ExpressionError('Set the X expression (e.g. time)')
    x = evaluate(panel['x'], table)
    y_expr = (panel.get('y') or '').strip()
    y = evaluate(y_expr, table) if y_expr else np.ones(len(table))
    log_x = bool(panel.get('log_x'))
    groups = resolve_groups(panel, table)
    agg = panel.get('agg', 'mean') if y_expr else 'count'
    nz = _nonzero(panel, x, y) if y_expr else _nonzero(panel, x)
    ok = nz & _finite(x, y, log_flags=(log_x, False))
    if ok.sum() < 2:
        raise ExpressionError('Not enough finite values')
    bins = max(2, int(panel.get('bins') or 40))
    edges = _bin_edges(x[ok], bins, log_x)
    centres = np.sqrt(edges[:-1] * edges[1:]) if log_x else (edges[:-1] + edges[1:]) / 2
    total = 0
    for g in groups:
        m = g.mask & ok
        if not m.any():
            continue
        total += int(m.sum())
        idx = np.clip(np.digitize(x[m], edges) - 1, 0, bins - 1)
        vals = y[m]
        mid, lo, hi = np.full(bins, np.nan), np.full(bins, np.nan), np.full(bins, np.nan)
        for b in range(bins):
            v = vals[idx == b]
            if agg == 'count':
                mid[b] = v.size
                continue
            if v.size == 0:
                continue
            mid[b] = {'mean': np.mean, 'median': np.median, 'sum': np.sum}.get(agg, np.mean)(v)
            band = panel.get('band', 'sem')
            if v.size > 1 and band != 'none' and agg in ('mean', 'median'):
                if band == 'iqr':
                    lo[b], hi[b] = np.percentile(v, [25, 75])
                else:
                    sd = np.std(v, ddof=1)
                    w = sd if band == 'sd' else sd / np.sqrt(v.size)
                    lo[b], hi[b] = mid[b] - w, mid[b] + w
        marker = panel.get('marker') if panel.get('show_points') else None
        ax.plot(centres, mid, color=g.color, lw=float(panel.get('line_width') or 1.6),
                ls=panel.get('line_style') or '-', marker=marker,
                ms=np.sqrt(float(panel.get('marker_size') or 12)),
                label=_label_n(g, int(m.sum()), panel))
        if np.isfinite(lo).any():
            ax.fill_between(centres, lo, hi, color=g.color, alpha=0.18, lw=0)
    if log_x:
        ax.set_xscale('log')
    if panel.get('log_y'):
        ax.set_yscale('log')
    report.counts[panel['id']] = total
    ylab = 'Particles per bin' if agg == 'count' else f'{agg.capitalize()} {pretty(y_expr, table, style)}'
    _style_axes(ax, panel, table, style, panel['x'], '')
    if not panel.get('y_label'):
        ax.set_ylabel(ylab)
    _legend(ax, panel)


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
    """Overlaid histograms per group with log binning, KDE, cumulative and tests."""
    from scipy import stats
    groups = [(g, v) for g, v in _value_groups(panel, table) if v.size]
    if not groups:
        raise ExpressionError('No finite values to plot')
    allv = np.concatenate([v for _, v in groups])
    bins = max(2, int(panel.get('bins') or 40))
    log_x = bool(panel.get('log_x'))
    edges = _bin_edges(allv, bins, log_x)
    if log_x:
        ax.set_xscale('log')
    if panel.get('log_y'):
        ax.set_yscale('log')
    filled = panel.get('hist_style', 'filled') == 'filled'
    density = bool(panel.get('density'))
    cumulative = bool(panel.get('cumulative'))
    for g, v in groups:
        if cumulative:
            xs = np.sort(v)
            ys = np.arange(1, xs.size + 1, dtype=float)
            if density:
                ys /= xs.size
            ax.step(np.r_[xs[0], xs], np.r_[0.0, ys], where='post', color=g.color,
                    lw=float(panel.get('line_width') or 1.6), ls=panel.get('line_style') or '-',
                    label=_label_n(g, v.size, panel))
            continue
        ax.hist(v, bins=edges, density=density,
                histtype='stepfilled' if filled else 'step',
                alpha=(0.55 if len(groups) > 1 else 0.85) if filled else 1.0,
                color=g.color, edgecolor=g.color if not filled else 'white',
                linewidth=float(panel.get('line_width') or 1.4) if not filled else 0.4,
                label=_label_n(g, v.size, panel))
        if panel.get('kde') and v.size > 2 and not cumulative:
            t = np.log10(v) if log_x else v
            if np.ptp(t) > 0:
                kde = stats.gaussian_kde(t)
                grid = np.linspace(t.min(), t.max(), 256)
                width = (np.log10(edges[1]) - np.log10(edges[0])) if log_x else (edges[1] - edges[0])
                scale = 1.0 if density and not log_x else v.size * width
                if density and log_x:
                    scale = 1.0 / (np.log(10) * 10 ** grid)
                yk = kde(grid) * scale
                ax.plot(10 ** grid if log_x else grid, yk, color=g.color,
                        lw=float(panel.get('line_width') or 1.6), ls=panel.get('line_style') or '-')
    report.counts[panel['id']] = int(allv.size)
    _, lines = run_tests([(g.label, v) for g, v in groups], panel)
    report.stats.extend(lines)
    if cumulative:
        ylabel = 'Cumulative fraction' if density else 'Cumulative count'
    else:
        ylabel = 'Density' if density else 'Particle count'
    _style_axes(ax, panel, table, style, panel['value'], '')
    if not panel.get('y_label'):
        ax.set_ylabel(ylabel)
    _legend(ax, panel)


def _draw_distribution(fig, ax, panel, table, report, style):
    """Box or violin plot per group, optional points, mean, notches and brackets."""
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
        if panel.get('show_mean'):
            ax.scatter(positions, [np.mean(v) for v in plot_data], marker='D', s=22,
                       color='white', edgecolors='#222222', zorder=4)
        if log:
            from matplotlib.ticker import FuncFormatter, MaxNLocator
            ax.yaxis.set_major_locator(MaxNLocator(integer=True))
            ax.yaxis.set_major_formatter(FuncFormatter(lambda val, _p: f'$10^{{{val:g}}}$'))
    else:
        bp = ax.boxplot(data, positions=positions, widths=0.6, patch_artist=True,
                        notch=bool(panel.get('notch')), showmeans=bool(panel.get('show_mean')),
                        showfliers=not panel.get('show_points'),
                        medianprops={'color': '#222222', 'lw': 1.4},
                        meanprops={'marker': 'D', 'markerfacecolor': 'white',
                                   'markeredgecolor': '#222222', 'markersize': 5},
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
    ax.set_xticklabels([f'{g.label}\n(n={v.size})' if panel.get('show_n', True) else g.label
                        for g, v in groups])
    report.counts[panel['id']] = int(sum(v.size for v in data))
    pairs, lines = run_tests([(g.label, v) for g, v in groups], panel)
    report.stats.extend(lines)
    _style_axes(ax, panel, table, style, '', panel['value'])
    draw_brackets(ax, pairs, positions, panel)


def _draw_bar(fig, ax, panel, table, report, style):
    """Grouped, stacked or horizontal bars: clusters per group, bars per value."""
    exprs = split_list(panel.get('value'))
    if not exprs:
        raise ExpressionError('Set one or more Value expressions (comma separated)')
    groups = resolve_groups(panel, table)
    if not groups:
        raise ExpressionError('Every group is hidden')
    agg = panel.get('agg', 'mean')
    err = panel.get('error', 'sd')
    log = bool(panel.get('log_y'))
    horizontal = bool(panel.get('horizontal'))
    stacked = bool(panel.get('stacked')) and len(exprs) > 1
    pal = _palette(panel)
    width = 0.8 if stacked else 0.8 / len(exprs)
    positions = np.arange(len(groups), dtype=float)
    per_group_values = [np.array([]) for _ in groups]
    bottoms = np.zeros(len(groups))
    for k, expr in enumerate(exprs):
        v = evaluate(expr, table)
        heights, errs = [], []
        for gi, g in enumerate(groups):
            vals = v[g.mask & np.isfinite(v)]
            if panel.get('drop_zeros', True) and agg in ('mean', 'median'):
                vals = vals[vals != 0]
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
            sd = float(np.std(vals, ddof=1)) if vals.size > 1 else 0.0
            errs.append({'sd': sd, 'sem': sd / np.sqrt(vals.size),
                         'ci95': 1.96 * sd / np.sqrt(vals.size)}.get(err, 0.0))
        offs = positions if stacked else positions - 0.4 + width * (k + 0.5)
        if len(exprs) == 1:
            colors = [g.color for g in groups]
            label = None
        else:
            colors = pal[k % len(pal)]
            label = pretty(expr, table, style)
        show_err = agg in ('mean', 'median') and err != 'none' and not stacked
        heights = np.asarray(heights, dtype=float)
        kw = dict(color=colors, label=label, zorder=2,
                  edgecolor=panel.get('edge_color') if float(panel.get('edge_width') or 0) > 0 else None,
                  linewidth=float(panel.get('edge_width') or 0),
                  error_kw={'elinewidth': 1, 'ecolor': '#333333'},
                  capsize=3 if show_err else 0)
        if horizontal:
            ax.barh(offs, heights, height=width * 0.92, left=bottoms if stacked else None,
                    xerr=errs if show_err else None, **kw)
        else:
            ax.bar(offs, heights, width=width * 0.92, bottom=bottoms if stacked else None,
                   yerr=errs if show_err else None, **kw)
        if stacked:
            bottoms = bottoms + np.nan_to_num(heights)
    names = [g.label for g in groups]
    if horizontal:
        ax.set_yticks(positions)
        ax.set_yticklabels(names)
        ax.invert_yaxis()
        if log:
            ax.set_xscale('log')
    else:
        ax.set_xticks(positions)
        ax.set_xticklabels(names)
        if log:
            ax.set_yscale('log')
    report.counts[panel['id']] = int(sum(v.size for v in per_group_values))
    vlab = {'count': 'Particle count', 'sum': 'Sum', 'median': 'Median', 'mean': 'Mean'}[agg]
    if len(exprs) == 1 and agg != 'count':
        vlab = f'{vlab} {pretty(exprs[0], table, style)}'
    _style_axes(ax, panel, table, style, swap=horizontal)
    if not panel.get('y_label'):
        (ax.set_xlabel if horizontal else ax.set_ylabel)(vlab)
    if len(exprs) == 1 and agg in ('mean', 'median') and not horizontal:
        pairs, lines = run_tests([(g.label, v) for g, v in zip(groups, per_group_values)], panel)
        report.stats.extend(lines)
        draw_brackets(ax, pairs, list(positions), panel)
    _legend(ax, panel)


def _draw_pie(fig, ax, panel, table, report, style):
    """Pie or donut of particle counts per group, or of summed values."""
    pal = _palette(panel)
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
            colors.append(pal[k % len(pal)])
        report.counts[panel['id']] = int(base.sum())
    else:
        groups = resolve_groups(panel, table)
        sizes = [float(g.mask.sum()) for g in groups]
        labels = [g.label for g in groups]
        colors = [g.color for g in groups]
        report.counts[panel['id']] = int(sum(sizes))
    keep = [i for i, s in enumerate(sizes) if s > 0]
    if not keep:
        raise ExpressionError('Nothing to share out')
    sizes = [sizes[i] for i in keep]
    labels = [labels[i] for i in keep]
    colors = [colors[i] for i in keep]
    edge = panel.get('edge_color') or 'white'
    lw = float(panel.get('edge_width') or 0) or 2
    wedge = {'edgecolor': edge, 'linewidth': lw}
    if panel.get('donut'):
        wedge['width'] = 0.42
    wedges, _t, autotexts = ax.pie(
        sizes, colors=colors, autopct=lambda pct: f'{pct:.1f}%' if pct >= 3 else '',
        startangle=90, counterclock=False, wedgeprops=wedge,
        pctdistance=0.79 if panel.get('donut') else 0.62, textprops={'fontsize': 'small'})
    from matplotlib import patheffects
    for t in autotexts:
        t.set_color('#1f2937')
        t.set_fontweight('bold')
        t.set_path_effects([patheffects.withStroke(linewidth=2.5, foreground='white')])
    ax.set_aspect('equal')
    if panel.get('title'):
        ax.set_title(panel['title'])
    if panel.get('legend', True):
        total = float(sum(sizes))
        ax.legend(wedges, [f'{lab} ({100 * s / total:.1f}%)' for lab, s in zip(labels, sizes)],
                  handlelength=1.0, **_legend_kwargs(panel, len(labels), 'below'))


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
    _, _, _, img = ax.hist2d(xs, ys, bins=[_bin_edges(xs, bins, log_x), _bin_edges(ys, bins, log_y)],
                             cmap=_cmap(panel), norm=LogNorm(), rasterized=True)
    if log_x:
        ax.set_xscale('log')
    if log_y:
        ax.set_yscale('log')
    cb = fig.colorbar(img, ax=ax, pad=0.02, fraction=0.05)
    cb.ax.set_zorder(ax.get_zorder())
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
    marker = panel.get('marker') or 'o'
    total = 0
    for g in groups:
        m = g.mask & _finite(a, b, c) & (s > 0)
        if not m.any():
            continue
        total += int(m.sum())
        ax.scatter(a[m] / s[m], b[m] / s[m], c[m] / s[m], s=size, color=g.color, marker=marker,
                   alpha=float(panel.get('alpha') or 0.7), rasterized=True,
                   label=_label_n(g, int(m.sum()), panel),
                   **(_edge(panel) if marker not in ('+', 'x', '.') else {}))
    ax.set_tlabel(pretty(panel['a'], table, style))
    ax.set_llabel(pretty(panel['b'], table, style))
    ax.set_rlabel(pretty(panel['c'], table, style))
    if panel.get('grid'):
        ax.grid(True, color='#e5e5e5', lw=0.6)
    if panel.get('title'):
        ax.set_title(panel['title'], pad=24)
    report.counts[panel['id']] = total
    _legend(ax, panel, default_loc='ternary')


def _draw_text(fig, ax, panel, table, report, style):
    """A free text block, e.g. a caption or a method note."""
    ax.axis('off')
    size = _float_or_none(panel.get('text_size')) or None
    ax.text(0.02, 0.98, panel.get('text') or '', transform=ax.transAxes,
            ha='left', va='top', wrap=True, fontsize=size)
    if panel.get('title'):
        ax.set_title(panel['title'])


def _draw_code(fig, ax, panel, table, report, style):
    """Run the user's own matplotlib code against this panel's axes."""
    import pandas as pd
    from scipy import stats
    code = panel.get('code') or ''
    if not code.strip():
        raise ExpressionError('Write some Python in the code box (see the example)')
    df = table.dataframe()
    groups = resolve_groups(panel, table)
    pal = _palette(panel)
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


DRAWERS = {
    'scatter': _draw_scatter,
    'line': _draw_line,
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


def _inner_rect(rect, fig_w, fig_h, panel):
    """Inset a drawn panel rectangle to leave room for ticks, labels and legends.

    Returns matplotlib ``[left, bottom, width, height]`` in figure fractions.
    """
    kind = panel.get('kind', 'scatter')
    has_title = bool(panel.get('title'))
    has_y2 = kind == 'scatter' and bool((panel.get('y2') or '').strip())
    has_cbar = kind == 'density' or (kind == 'scatter' and bool((panel.get('color_by') or '').strip()))
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
        if float(panel.get('xtick_rotation') or 0):
            mb += 0.35
        if kind in ('box', 'violin') and panel.get('show_n', True):
            mb += 0.15
        if kind == 'bar' and panel.get('horizontal'):
            ml += 0.5
    if panel.get('legend', True) and kind not in ('text', 'code'):
        loc = panel.get('legend_loc')
        if loc == 'outside right':
            mr += 1.5
        elif loc == 'below' and kind != 'pie':
            mb += 0.55
        elif loc == 'above':
            mt += 0.45
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


def _fit_outside_legend(fig, ax, rect):
    """Shrink the axes until a legend placed outside them fits in the panel.

    When the legend is so wide that the plot would become unreadably small,
    the legend is moved back inside the plot instead.
    """
    leg = ax.get_legend()
    if leg is None or leg.get_bbox_to_anchor() is None:
        return
    canvas = fig.canvas
    if not hasattr(canvas, 'get_renderer'):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        canvas = FigureCanvasAgg(fig)
    renderer = canvas.get_renderer()
    right = rect[0] + rect[2]
    bottom, top = 1 - rect[1] - rect[3], 1 - rect[1]
    original = ax.get_position()
    partners = [o for o in fig.axes if o is not ax and abs(o.get_zorder() - ax.get_zorder()) < 0.5
                and getattr(o, '_colorbar', None) is None]
    for _ in range(4):
        box = leg.get_window_extent(renderer).transformed(fig.transFigure.inverted())
        pos = ax.get_position()
        dx = max(0.0, box.x1 - (right - 0.005))
        dy_low = max(0.0, (bottom + 0.005) - box.y0)
        dy_high = max(0.0, box.y1 - (top - 0.005))
        if dx <= 1e-4 and dy_low <= 1e-4 and dy_high <= 1e-4:
            return
        w = pos.width - dx
        y0, h = pos.y0, pos.height
        if dy_low > 1e-4:
            y0 += dy_low
            h -= dy_low
        if dy_high > 1e-4:
            h -= dy_high
        if w < 0.4 * original.width or h < 0.4 * original.height:
            break
        for a in [ax] + partners:
            a.set_position([pos.x0, y0, w, h])
    else:
        return
    for a in [ax] + partners:
        a.set_position(original)
    handles = list(getattr(leg, 'legend_handles', None) or getattr(leg, 'legendHandles', []))
    labels = [t.get_text() for t in leg.get_texts()]
    title = leg.get_title().get_text()
    size = leg.get_texts()[0].get_fontsize() if labels else None
    leg.remove()
    ax.legend(handles, labels, loc='best', frameon=False, fontsize=size,
              title=title or None)


def ensure_ternary_projection():
    """Register the mpltern projection if the package is available."""
    try:
        import importlib
        importlib.import_module('mpltern')
        return True
    except Exception:
        return False


def render(fig, spec: dict, table: ParticleTable) -> RenderReport:
    """Draw ``spec`` onto ``fig`` (which is cleared first).

    Args:
        fig: A :class:`matplotlib.figure.Figure`.
        spec: Figure Builder spec (normalised internally, never modified).
        table: Particle columns from the upstream stream; the spec's
            variables are installed on it.

    Returns:
        RenderReport: statistics lines, per-panel errors and counts.
    """
    import matplotlib
    from matplotlib.patches import Rectangle
    spec = normalise_spec(spec)
    figcfg = spec['figure']
    report = RenderReport()
    report.variable_errors = table.set_variables(spec.get('variables'))
    fig.clear()
    fw, fh = float(figcfg['width']), float(figcfg['height'])
    fig.set_size_inches(fw, fh, forward=False)
    bg = figcfg.get('background') or '#ffffff'
    fig.set_facecolor(bg)
    style = figcfg.get('label_style', 'isotope')
    pal = palette_colors(figcfg.get('palette'))
    ensure_ternary_projection()
    fs = float(figcfg.get('font_size') or 11)
    lw = float(figcfg.get('axes_linewidth') or 0.8)
    rc = {
        'font.family': [figcfg.get('font_family') or 'DejaVu Sans', 'DejaVu Sans'],
        'font.size': fs,
        'axes.titlesize': float(figcfg.get('title_size') or fs * 1.05),
        'axes.labelsize': float(figcfg.get('label_size') or fs),
        'xtick.labelsize': float(figcfg.get('tick_size') or fs * 0.9),
        'ytick.labelsize': float(figcfg.get('tick_size') or fs * 0.9),
        'mathtext.default': 'regular',
        'axes.titleweight': 'bold',
        'axes.linewidth': lw,
        'xtick.major.width': lw,
        'ytick.major.width': lw,
        'xtick.minor.width': lw * 0.7,
        'ytick.minor.width': lw * 0.7,
        'legend.frameon': False,
    }
    font_log = logging.getLogger('matplotlib.font_manager')
    previous = font_log.level
    font_log.setLevel(logging.ERROR)
    try:
        with matplotlib.rc_context(rc):
            if figcfg.get('title'):
                fig.suptitle(figcfg['title'], fontweight='bold')
            for index, panel in enumerate(spec['panels']):
                panel['_palette'] = pal
                _render_panel(fig, index, panel, spec, table, report, style, fw, fh, bg, Rectangle)
    finally:
        font_log.setLevel(previous)
    return report


def _render_panel(fig, index, panel, spec, table, report, style, fw, fh, bg, Rectangle):
    """Draw one panel, catching its errors so the rest of the figure survives."""
    figcfg = spec['figure']
    kind = panel.get('kind', 'scatter')
    rect = panel.get('rect') or [0, 0, 1, 1]
    if index:
        fig.add_artist(Rectangle((rect[0], 1 - rect[1] - rect[3]), rect[2], rect[3],
                                 transform=fig.transFigure, zorder=index + 0.5,
                                 facecolor=bg, edgecolor='none'))
    inner = _inner_rect(rect, fw, fh, panel)
    report.axes[panel['id']] = inner
    ax = fig.add_axes(inner, projection='ternary' if kind == 'ternary' else None)
    ax.set_zorder(index + 1)
    ax.set_facecolor(panel.get('panel_bg') or '#ffffff')
    try:
        if len(table) == 0 and kind not in ('text', 'code'):
            raise ExpressionError('No particles: connect a sample or filter node')
        DRAWERS.get(kind, _draw_scatter)(fig, ax, panel, table, report, style)
        _annotate(ax, panel)
        _fit_outside_legend(fig, ax, rect)
    except Exception as exc:
        report.errors[panel['id']] = str(exc)
        ax.cla()
        ax.axis('off')
        ax.text(0.5, 0.5, f'⚠ {exc}', transform=ax.transAxes, ha='center',
                va='center', color='#b42318', wrap=True, fontsize='small')
    if figcfg.get('panel_letters') and len(spec['panels']) > 1:
        size = float(figcfg.get('letter_size') or 0) or float(figcfg.get('font_size') or 11) + 3
        fig.text(rect[0] + 0.06 / fw, 1 - rect[1] - 0.06 / fh,
                 panel_letter(index, figcfg.get('letter_style', 'a')),
                 ha='left', va='top', fontweight='bold', fontsize=size, zorder=100)
