"""Helpers shared by every chart: groups, masks, legends, axes styling."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from results.figure_builder.core.expressions import (
    ExpressionError, ParticleTable, evaluate, pretty)
from results.figure_builder.core.spec import OTHER_COLOR, PALETTE


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
    artists: dict = field(default_factory=dict)


def float_or_none(v):
    """Parse an optional numeric field."""
    try:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def numbers(text) -> list[float]:
    """Parse a comma separated list of numbers, ignoring junk."""
    out = []
    for part in str(text or '').replace(';', ',').split(','):
        v = float_or_none(part)
        if v is not None:
            out.append(v)
    return out


def panel_palette(panel) -> list[str]:
    """The palette injected into ``panel`` by :func:`render`."""
    return panel.get('_palette') or PALETTE


def candidate_groups(panel: dict, table: ParticleTable) -> list[Group]:
    """Every group the panel's grouping produces, before hiding and reordering."""
    n = len(table)
    base = np.ones(n, dtype=bool)
    if (panel.get('filter') or '').strip():
        base &= evaluate(panel['filter'], table, as_mask=True)
    pal = panel_palette(panel)
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


def finite_mask(*arrays, log_flags=()):
    """Mask keeping rows finite in every array (and > 0 where log is set)."""
    mask = np.ones(len(arrays[0]), dtype=bool)
    for i, arr in enumerate(arrays):
        arr = np.asarray(arr, dtype=float)
        mask &= np.isfinite(arr)
        if i < len(log_flags) and log_flags[i]:
            mask &= arr > 0
    return mask


def nonzero_mask(panel, *arrays):
    """Mask hiding particles where a plotted value is exactly zero (not detected)."""
    mask = np.ones(len(arrays[0]), dtype=bool)
    if panel.get('drop_zeros', True):
        for arr in arrays:
            mask &= np.asarray(arr, dtype=float) != 0
    return mask


def label_n(g: Group, n: int, panel) -> str:
    """Legend label for a group, with its count when requested."""
    return f'{g.label} (n={n})' if panel.get('show_n', True) else g.label


def cmap_name(panel) -> str:
    """Colour map name, reversed when asked."""
    name = panel.get('colormap') or 'viridis'
    return f'{name}_r' if panel.get('reverse_cmap') else name


def edge_kwargs(panel) -> dict:
    """Marker edge keyword arguments."""
    width = float(panel.get('edge_width') or 0)
    if width <= 0:
        return {'linewidths': 0}
    return {'linewidths': width, 'edgecolors': panel.get('edge_color') or '#ffffff'}


def legend_kwargs(panel, n_items: int, default_loc: str | None = None) -> dict:
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


def add_legend(ax, panel, extra=None, default_loc=None, min_items=2):
    """Add a legend when the panel has enough labelled series."""
    if not panel.get('legend', True):
        return
    h, labels = ax.get_legend_handles_labels()
    for x in extra or []:
        if x is not None:
            h.append(x)
            labels.append(x.get_label())
    if len(h) >= min_items:
        ax.legend(h, labels, markerscale=1.4, **legend_kwargs(panel, len(h), default_loc))


def style_axes(ax, panel, table, style, x_default='', y_default='', swap=False):
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
    xmin, xmax = float_or_none(panel.get('x_min')), float_or_none(panel.get('x_max'))
    ymin, ymax = float_or_none(panel.get('y_min')), float_or_none(panel.get('y_max'))
    if xmin is not None or xmax is not None:
        ax.set_xlim(left=xmin, right=xmax)
    if ymin is not None or ymax is not None:
        ax.set_ylim(bottom=ymin, top=ymax)
    for v in numbers(panel.get('hlines')):
        ax.axhline(v, color='#555555', lw=1, ls='--', zorder=1)
    for v in numbers(panel.get('vlines')):
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


def annotate(ax, panel):
    """Draw the panel's free text annotations, with optional arrows."""
    for index, a in enumerate(panel.get('annotations') or []):
        text = a.get('text') or ''
        if not text.strip():
            continue
        coords = 'data' if a.get('coords') == 'data' else 'axes fraction'
        x = float_or_none(a.get('x'))
        y = float_or_none(a.get('y'))
        if x is None or y is None:
            continue
        kw = {'fontsize': float_or_none(a.get('size')) or 'medium',
              'color': a.get('color') or '#222222',
              'fontweight': 'bold' if a.get('bold') else 'normal',
              'fontstyle': 'italic' if a.get('italic') else 'normal',
              'ha': 'left', 'va': 'center', 'zorder': 20}
        if a.get('box'):
            kw['bbox'] = {'boxstyle': 'round,pad=0.3', 'fc': 'white', 'ec': '#999999', 'lw': 0.6}
        ax_, ay_ = float_or_none(a.get('arrow_x')), float_or_none(a.get('arrow_y'))
        if ax_ is not None and ay_ is not None:
            t = ax.annotate(text, xy=(ax_, ay_), xytext=(x, y), xycoords=coords,
                            textcoords=coords, arrowprops={'arrowstyle': '->', 'color': kw['color'],
                                                           'lw': 1}, **kw)
        else:
            t = ax.annotate(text, xy=(x, y), xycoords=coords, **kw)
        t._fb_annotation = index


def marker_sizes(panel, table, base: float):
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


def bin_edges(values, bins, log):
    """Linear or logarithmic bin edges spanning ``values``."""
    lo, hi = float(np.min(values)), float(np.max(values))
    if hi <= lo:
        hi = lo + (abs(lo) * 0.1 or 1.0)
    if log:
        return np.logspace(np.log10(lo), np.log10(hi), bins + 1)
    return np.linspace(lo, hi, bins + 1)


def value_groups(panel, table):
    """Evaluate ``value`` and split it by group, dropping non-finite values."""
    if not (panel.get('value') or '').strip():
        raise ExpressionError('Set the Value expression')
    v = evaluate(panel['value'], table)
    log = panel.get('log_y') if panel.get('kind') in ('box', 'violin', 'bar') else panel.get('log_x')
    out = []
    nz = nonzero_mask(panel, v)
    for g in resolve_groups(panel, table):
        m = g.mask & nz & finite_mask(v, log_flags=(log,))
        out.append((g, v[m]))
    return out


def _shrink_for_legend(fig, ax, leg, rect, renderer, partners, original):
    """Shrink ``ax`` (and its partners) until ``leg`` fits inside ``rect``; True on success."""
    right = rect[0] + rect[2]
    bottom, top = 1 - rect[1] - rect[3], 1 - rect[1]
    for _ in range(5):
        box = leg.get_window_extent(renderer).transformed(fig.transFigure.inverted())
        pos = ax.get_position()
        dx = max(0.0, box.x1 - (right - 0.005))
        dy_low = max(0.0, (bottom + 0.005) - box.y0)
        dy_high = max(0.0, box.y1 - (top - 0.005))
        if dx <= 1e-4 and dy_low <= 1e-4 and dy_high <= 1e-4:
            return True
        w = pos.width - dx
        y0, h = pos.y0, pos.height
        if dy_low > 1e-4:
            y0 += dy_low
            h -= dy_low
        if dy_high > 1e-4:
            h -= dy_high
        if w < 0.4 * original.width or h < 0.4 * original.height:
            return False
        for a in [ax] + partners:
            a.set_position([pos.x0, y0, w, h])
    return False


def fit_outside_legend(fig, ax, rect):
    """Make a legend placed outside the plot fit inside its panel.

    The plot shrinks to make room. If an outside-right legend is too wide,
    it is moved below the plot; if that does not fit either, it goes back
    inside the plot.
    """
    leg = ax.get_legend()
    if leg is None or leg.get_bbox_to_anchor() is None:
        return
    canvas = fig.canvas
    if not hasattr(canvas, 'get_renderer'):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        canvas = FigureCanvasAgg(fig)
    renderer = canvas.get_renderer()
    original = ax.get_position()
    partners = [o for o in fig.axes if o is not ax and abs(o.get_zorder() - ax.get_zorder()) < 0.5
                and getattr(o, '_colorbar', None) is None]
    if _shrink_for_legend(fig, ax, leg, rect, renderer, partners, original):
        return
    for a in [ax] + partners:
        a.set_position(original)
    handles = list(getattr(leg, 'legend_handles', None) or getattr(leg, 'legendHandles', []))
    labels = [t.get_text() for t in leg.get_texts()]
    title = leg.get_title().get_text() or None
    size = leg.get_texts()[0].get_fontsize() if labels else None
    anchor = leg.get_bbox_to_anchor().transformed(ax.transAxes.inverted())
    was_right = anchor.x0 > 0.9
    leg.remove()
    if was_right:
        below = ax.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, -0.14),
                          ncol=min(3, max(1, len(labels))), frameon=False, fontsize=size, title=title)
        if _shrink_for_legend(fig, ax, below, rect, renderer, partners, original):
            return
        for a in [ax] + partners:
            a.set_position(original)
        below.remove()
    ax.legend(handles, labels, loc='best', frameon=False, fontsize=size, title=title)


def item_label(panel: dict, expr: str, table: ParticleTable, style: str,
               short: bool = False) -> str:
    """Display name of an isotope or expression, honouring the panel's renames.

    ``short`` drops the quantity and unit (used for matrix tick labels).
    """
    custom = (panel.get('item_labels') or {}).get(expr)
    return custom if custom else pretty(expr, table, style, with_unit=not short)


def item_exprs(panel: dict, table: ParticleTable) -> list[str]:
    """Expressions listed in the panel's ``isotopes`` field, or every isotope."""
    from results.figure_builder.core.expressions import split_list
    exprs = split_list(panel.get('isotopes') or '')
    return exprs or list(table.labels)


def base_mask(panel: dict, table: ParticleTable) -> np.ndarray:
    """Particles kept by the panel filter and visible groups."""
    mask = np.zeros(len(table), dtype=bool)
    for g in resolve_groups(panel, table):
        mask |= g.mask
    return mask


def handles(report, panel: dict) -> dict:
    """The artist record of ``panel`` in ``report`` (created on demand)."""
    return report.artists.setdefault(panel['id'], {})

