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
    framed = bool(panel.get('legend_frame', True)) and loc not in ('outside right', 'below', 'above', 'ternary')
    kw = {'frameon': framed, 'fontsize': panel.get('legend_size') or 'small', 'ncol': cols}
    if framed:
        kw.update(framealpha=0.88, facecolor='white', edgecolor='#d0d5dd', fancybox=True,
                  borderpad=0.5, handletextpad=0.5)
    if panel.get('legend_title'):
        kw['title'] = panel['legend_title']
    xy = panel.get('legend_xy') or []
    if loc == 'custom' and len(xy) == 2:
        kw.update(loc='upper left', bbox_to_anchor=(float(xy[0]), float(xy[1])), borderaxespad=0)
        kw['_custom'] = True
        return kw
    if loc == 'custom':
        loc = 'best'
    if loc == 'outside right':
        kw.update(loc='upper left', bbox_to_anchor=(1.02, 1.0), borderaxespad=0)
    elif loc == 'below':
        kw.update(loc='upper center', bbox_to_anchor=(0.5, -0.16),
                  ncol=max(cols, min(4, n_items)))
    elif loc == 'above':
        kw.update(loc='lower center', bbox_to_anchor=(0.5, 1.02),
                  ncol=max(cols, min(4, n_items)))
    elif loc == 'ternary':
        kw.update(loc='upper center', bbox_to_anchor=(0.5, -0.3),
                  ncol=max(cols, min(3, n_items)))
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
        kw = legend_kwargs(panel, len(h), default_loc)
        custom = kw.pop('_custom', False)
        leg = ax.legend(h, labels, markerscale=1.4, **kw)
        leg._fb_custom = custom


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
        which_axis = panel.get('grid_axis') or 'both'
        gcol = panel.get('grid_color') or '#d9dde3'
        ax.grid(True, which='major', axis=which_axis, color=gcol, lw=0.6, ls=(0, (4, 3)), zorder=0)
        if panel.get('grid_minor'):
            ax.minorticks_on()
            ax.grid(True, which='minor', axis=which_axis, color=gcol, lw=0.35, ls=':', alpha=0.8,
                    zorder=0)
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
    apply_axis_controls(ax, panel)


TICK_FORMATS = {
    'auto': 'Automatic',
    'plain': 'Plain numbers (100, 1000)',
    'sci': 'Scientific (1×10³)',
    'power': 'Powers of ten (10³)',
    'int': 'Whole numbers',
    '1dp': 'One decimal',
    '2dp': 'Two decimals',
    'percent': 'Percent (adds %)',
    'thousands': 'Thousands separator (1,000)',
}
"""Tick label formats offered for each axis."""


def _formatter(fmt: str):
    """A matplotlib tick formatter for one of :data:`TICK_FORMATS` (None = automatic)."""
    from matplotlib import ticker
    if fmt == 'plain':
        return ticker.FuncFormatter(lambda v, _p: f'{v:g}' if abs(v) < 1e6 else f'{v:.0f}')
    if fmt == 'sci':
        def sci(v, _p):
            if v == 0:
                return '0'
            exp = int(np.floor(np.log10(abs(v))))
            mant = v / 10 ** exp
            return f'${mant:g}\\times10^{{{exp}}}$' if abs(mant - 1) > 1e-9 else f'$10^{{{exp}}}$'
        return ticker.FuncFormatter(sci)
    if fmt == 'power':
        return ticker.LogFormatterMathtext()
    if fmt == 'int':
        return ticker.FuncFormatter(lambda v, _p: f'{v:.0f}')
    if fmt == '1dp':
        return ticker.FuncFormatter(lambda v, _p: f'{v:.1f}')
    if fmt == '2dp':
        return ticker.FuncFormatter(lambda v, _p: f'{v:.2f}')
    if fmt == 'percent':
        return ticker.FuncFormatter(lambda v, _p: f'{v:g}%')
    if fmt == 'thousands':
        return ticker.FuncFormatter(lambda v, _p: f'{v:,.0f}')
    return None


def _set_ticks(axis, text, scale):
    """Tick spacing (a single number) or exact tick values (a comma list)."""
    from matplotlib import ticker
    text = str(text or '').strip()
    if not text:
        return
    values = numbers(text)
    if not values:
        return
    if len(values) > 1 or ',' in text or ';' in text:
        axis.set_major_locator(ticker.FixedLocator(values))
        return
    step = values[0]
    if step <= 0:
        return
    if scale == 'log':
        axis.set_major_locator(ticker.LogLocator(base=step if step > 1 else 10))
    else:
        axis.set_major_locator(ticker.MultipleLocator(step))


def apply_axis_controls(ax, panel):
    """Tick spacing, tick formats, reversed axes and axis colour of one panel."""
    from matplotlib import ticker
    _set_ticks(ax.xaxis, panel.get('x_ticks'), ax.get_xscale())
    _set_ticks(ax.yaxis, panel.get('y_ticks'), ax.get_yscale())
    for axis, key in ((ax.xaxis, 'x_format'), (ax.yaxis, 'y_format')):
        fmt = _formatter(panel.get(key) or 'auto')
        if fmt is not None:
            axis.set_major_formatter(fmt)
            axis.set_minor_formatter(ticker.NullFormatter())
    if panel.get('invert_x') and not ax.xaxis_inverted():
        ax.invert_xaxis()
    if panel.get('invert_y') and not ax.yaxis_inverted():
        ax.invert_yaxis()
    color = panel.get('axis_color')
    if color:
        for spine in ax.spines.values():
            spine.set_color(color)
        ax.tick_params(which='both', colors=color)
        ax.xaxis.label.set_color(color)
        ax.yaxis.label.set_color(color)


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


def _shrink_for_legend(fig, ax, leg, rect, renderer, partners, original, allow_width=True):
    """Shrink ``ax`` (and its partners) until ``leg`` fits inside ``rect``; True on success.

    ``allow_width=False`` is used for legends above or below the plot: those
    cannot be fixed by narrowing the plot, only by fewer columns.
    """
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
        if dx > 1e-4 and not allow_width:
            return False
        w = pos.width - dx
        y0, h = pos.y0, pos.height
        if dy_low > 1e-4:
            y0 += dy_low
            h -= dy_low
        if dy_high > 1e-4:
            h -= dy_high
        if w < 0.55 * original.width or h < 0.5 * original.height:
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
    if leg is None or leg.get_bbox_to_anchor() is None or getattr(leg, '_fb_custom', False):
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
    vertical = anchor.y0 < 0 or anchor.y0 > 1
    if vertical and not was_right:
        loc = leg._loc
        ncols = getattr(leg, '_ncols', 1)
        bbox = (anchor.x0, anchor.y0)
        leg.remove()
        for n in range(max(1, ncols - 1), 0, -1):
            trial = ax.legend(handles, labels, loc=loc, bbox_to_anchor=bbox, ncol=n,
                              frameon=False, fontsize=size, title=title)
            if _shrink_for_legend(fig, ax, trial, rect, renderer, partners, original,
                                  allow_width=False):
                return
            for a in [ax] + partners:
                a.set_position(original)
            trial.remove()
        ax.legend(handles, labels, loc='best', frameon=False, fontsize=size, title=title)
        return
    leg.remove()
    if was_right:
        for n in range(min(3, max(1, len(labels))), 0, -1):
            below = ax.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, -0.14),
                              ncol=n, frameon=False, fontsize=size, title=title)
            if _shrink_for_legend(fig, ax, below, rect, renderer, partners, original,
                                  allow_width=False):
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



def fit_decorations(fig, handles_: dict, rect, pad: float = 0.008):
    """Shrink a panel's plot so every label, tick, legend and colour bar stays in its rectangle.

    All axes belonging to the panel (main, right axis, colour bar, pair-plot
    cells) are scaled together, so their relative layout is kept.

    Args:
        fig: The figure (already drawn once is not required).
        handles_: The panel's artist record (``ax``, ``ax2``, ``cbar``, ``extra_axes``).
        rect: The panel rectangle ``[x, y, w, h]`` (figure fractions, top-left origin).
        pad: Breathing room kept inside the rectangle, in figure fractions.
    """
    ax = handles_.get('ax')
    if ax is None:
        return
    group = [ax]
    if handles_.get('ax2') is not None:
        group.append(handles_['ax2'])
    if handles_.get('cbar') is not None:
        group.append(handles_['cbar'].ax)
    group.extend(handles_.get('extra_axes') or [])
    visible = [a for a in group if a.get_visible()]
    if not visible:
        return
    canvas = fig.canvas
    if not hasattr(canvas, 'get_renderer'):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        canvas = FigureCanvasAgg(fig)
    renderer = canvas.get_renderer()
    left, right = rect[0] + pad, rect[0] + rect[2] - pad
    bottom, top = 1 - rect[1] - rect[3] + pad, 1 - rect[1] - pad
    inv = fig.transFigure.inverted()
    legends = [a.get_legend() for a in visible if a.get_legend() is not None]
    for leg in legends:
        leg.set_in_layout(False)
    try:
        _fit_group(visible, renderer, inv, left, right, bottom, top)
    finally:
        for leg in legends:
            leg.set_in_layout(True)


def _fit_group(visible, renderer, inv, left, right, bottom, top):
    """Scale a group of axes until their tight boxes fit inside the given bounds."""
    for _ in range(3):
        boxes = []
        for a in visible:
            try:
                tb = a.get_tightbbox(renderer)
            except Exception:
                tb = None
            if tb is not None and tb.width > 0:
                boxes.append(tb.transformed(inv))
        if not boxes:
            return
        x0 = min(b.x0 for b in boxes)
        x1 = max(b.x1 for b in boxes)
        y0 = min(b.y0 for b in boxes)
        y1 = max(b.y1 for b in boxes)
        over_l = max(0.0, left - x0)
        over_r = max(0.0, x1 - right)
        over_b = max(0.0, bottom - y0)
        over_t = max(0.0, y1 - top)
        if max(over_l, over_r, over_b, over_t) < 1e-3:
            return
        movable = [a for a in visible if a.get_axes_locator() is None]
        if not movable:
            return
        positions = [a.get_position() for a in movable]
        gx0 = min(p.x0 for p in positions)
        gx1 = max(p.x1 for p in positions)
        gy0 = min(p.y0 for p in positions)
        gy1 = max(p.y1 for p in positions)
        nx0, nx1 = gx0 + over_l, gx1 - over_r
        ny0, ny1 = gy0 + over_b, gy1 - over_t
        if nx1 - nx0 < 0.25 * (gx1 - gx0) or ny1 - ny0 < 0.25 * (gy1 - gy0):
            return
        sx = (nx1 - nx0) / max(1e-9, gx1 - gx0)
        sy = (ny1 - ny0) / max(1e-9, gy1 - gy0)
        for a, p in zip(movable, positions):
            a.set_position([nx0 + (p.x0 - gx0) * sx, ny0 + (p.y0 - gy0) * sy,
                            p.width * sx, p.height * sy])


SHAPE_TYPES = {
    'xband': 'Shaded X range (vertical band)',
    'yband': 'Shaded Y range (horizontal band)',
    'box': 'Shaded rectangle',
    'vline': 'Vertical line',
    'hline': 'Horizontal line',
    'line': 'Line y = slope × x + intercept',
}
"""Kinds of shapes a panel can carry."""

HATCHES = {'': 'None', '//': 'Diagonal', '\\\\': 'Back-diagonal', 'xx': 'Cross', '..': 'Dots',
           '--': 'Horizontal', '||': 'Vertical'}


def draw_shapes(ax, panel):
    """Draw the panel's grey areas, rectangles and reference lines.

    Empty bounds run to the edge of the plot. Shapes are drawn behind the
    data unless their layer is "front"; labelled shapes join the legend.
    The visible range is kept as it was before the shapes were added.

    Returns:
        list: Legend handles of labelled shapes.
    """
    shapes = panel.get('shapes') or []
    if not shapes or getattr(ax, 'name', '') in ('ternary', 'polar'):
        return []
    from matplotlib.patches import Rectangle
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    handles_out = []
    for sh in shapes:
        kind = sh.get('type') or 'xband'
        color = sh.get('color') or '#9ca3af'
        alpha = float_or_none(sh.get('alpha'))
        alpha = 0.25 if alpha is None else max(0.0, min(1.0, alpha))
        z = 6 if sh.get('layer') == 'front' else 0.6
        label = (sh.get('label') or '').strip() or None
        hatch = sh.get('hatch') or None
        lw = float_or_none(sh.get('width')) or 1.2
        ls = sh.get('style') or '-'
        x1, x2 = float_or_none(sh.get('x1')), float_or_none(sh.get('x2'))
        y1, y2 = float_or_none(sh.get('y1')), float_or_none(sh.get('y2'))
        lo_x, hi_x = sorted(xlim)
        lo_y, hi_y = sorted(ylim)
        artist = None
        if kind == 'xband':
            a, b = (lo_x if x1 is None else x1), (hi_x if x2 is None else x2)
            artist = ax.axvspan(min(a, b), max(a, b), color=color, alpha=alpha, zorder=z, lw=0,
                                hatch=hatch, label=label)
        elif kind == 'yband':
            a, b = (lo_y if y1 is None else y1), (hi_y if y2 is None else y2)
            artist = ax.axhspan(min(a, b), max(a, b), color=color, alpha=alpha, zorder=z, lw=0,
                                hatch=hatch, label=label)
        elif kind == 'box':
            a, b = (lo_x if x1 is None else x1), (hi_x if x2 is None else x2)
            c, d = (lo_y if y1 is None else y1), (hi_y if y2 is None else y2)
            artist = Rectangle((min(a, b), min(c, d)), abs(b - a), abs(d - c), facecolor=color,
                               alpha=alpha, zorder=z, hatch=hatch, label=label,
                               edgecolor=color if hatch else 'none', lw=0.8 if hatch else 0)
            ax.add_patch(artist)
        elif kind == 'vline' and x1 is not None:
            artist = ax.axvline(x1, color=color, lw=lw, ls=ls, zorder=z, label=label,
                                alpha=max(alpha, 0.6))
        elif kind == 'hline' and y1 is not None:
            artist = ax.axhline(y1, color=color, lw=lw, ls=ls, zorder=z, label=label,
                                alpha=max(alpha, 0.6))
        elif kind == 'line':
            slope = float_or_none(sh.get('slope'))
            icpt = float_or_none(sh.get('intercept')) or 0.0
            slope = 1.0 if slope is None else slope
            if ax.get_xscale() == 'log':
                xs = np.logspace(np.log10(max(lo_x, 1e-300)), np.log10(hi_x), 200)
            else:
                xs = np.linspace(lo_x, hi_x, 200)
            artist, = ax.plot(xs, slope * xs + icpt, color=color, lw=lw, ls=ls, zorder=z,
                              label=label, alpha=max(alpha, 0.6))
        if artist is not None and label:
            handles_out.append(artist)
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    return handles_out


def merge_legend(ax, panel, extra_handles):
    """Rebuild a panel's legend so it also lists ``extra_handles``."""
    if not extra_handles or not panel.get('legend', True):
        return
    leg = ax.get_legend()
    handles_, labels = [], []
    if leg is not None:
        handles_ = list(getattr(leg, 'legend_handles', None) or getattr(leg, 'legendHandles', []))
        labels = [t.get_text() for t in leg.get_texts()]
        leg.remove()
    handles_ += list(extra_handles)
    labels += [h.get_label() for h in extra_handles]
    kw = legend_kwargs(panel, len(handles_))
    custom = kw.pop('_custom', False)
    new = ax.legend(handles_, labels, **kw)
    new._fb_custom = custom


def summary_text(items) -> str:
    """Multi-line n / mean ± SD / median summary of named value arrays."""
    lines = []
    for label, v in items:
        v = np.asarray(v, dtype=float)
        v = v[np.isfinite(v)]
        if v.size == 0:
            continue
        sd = np.std(v, ddof=1) if v.size > 1 else 0.0
        lines.append(f'{label}: n = {v.size:,}, mean = {np.mean(v):.3g} ± {sd:.2g}, '
                     f'median = {np.median(v):.3g}')
    return '\n'.join(lines)


def draw_summary_box(ax, panel, items):
    """Put a small statistics box inside the plot when the panel asks for one."""
    if not panel.get('summary_box') or not items:
        return
    text = summary_text(items)
    if not text:
        return
    loc = panel.get('summary_loc') or 'upper right'
    pos = {'upper right': (0.98, 0.98, 'right', 'top'), 'upper left': (0.02, 0.98, 'left', 'top'),
           'lower right': (0.98, 0.02, 'right', 'bottom'),
           'lower left': (0.02, 0.02, 'left', 'bottom')}.get(loc, (0.98, 0.98, 'right', 'top'))
    t = ax.text(pos[0], pos[1], text, transform=ax.transAxes, ha=pos[2], va=pos[3],
                fontsize='x-small', zorder=20, linespacing=1.4,
                bbox={'boxstyle': 'round,pad=0.4', 'fc': 'white', 'ec': '#d0d5dd', 'lw': 0.6,
                      'alpha': 0.92})
    t._fb_cell = True



CBAR_LOCATIONS = {
    'right': 'Right of the plot',
    'left': 'Left of the plot',
    'top': 'Above the plot',
    'bottom': 'Below the plot',
    'inside right': 'Inside, right',
    'inside top': 'Inside, top',
    'custom': 'Where I dragged it',
}
"""Where a panel's colour bar can go."""


class _CbarLocator:
    """Keeps a colour bar at fixed axes-fraction bounds of its parent plot."""

    def __init__(self, parent, bounds):
        self.parent = parent
        self.bounds = list(bounds)

    def __call__(self, cax, renderer):
        from matplotlib.transforms import Bbox, TransformedBbox
        bb = TransformedBbox(Bbox.from_bounds(*self.bounds), self.parent.transAxes)
        return TransformedBbox(bb, cax.figure.transSubfigure.inverted())


def _cbar_orientation(panel) -> str:
    loc = panel.get('cbar_loc') or 'right'
    if loc == 'custom':
        return panel.get('cbar_orient') or 'vertical'
    return 'horizontal' if loc in ('top', 'bottom', 'inside top') else 'vertical'


def _tidy_log_ticks(cb):
    """Readable 1-2-5 labels on a log colour bar instead of crowded minor labels."""
    from matplotlib.colors import LogNorm
    from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter
    if not isinstance(cb.norm, LogNorm):
        return
    vmin, vmax = cb.norm.vmin, cb.norm.vmax
    if not vmin or not vmax or vmin <= 0:
        return
    axis = cb.ax.xaxis if cb.orientation == 'horizontal' else cb.ax.yaxis
    if np.log10(vmax / vmin) < 2.5:
        axis.set_major_locator(LogLocator(subs=(1.0, 2.0, 5.0)))
        axis.set_major_formatter(FuncFormatter(lambda v, _p: f'{v:g}'))
    axis.set_minor_formatter(NullFormatter())


def _cbar_side(panel, orient) -> str:
    """Side of the colour bar that carries its ticks and label."""
    loc = panel.get('cbar_loc') or 'right'
    side = {'right': 'right', 'left': 'left', 'top': 'top', 'bottom': 'bottom',
            'inside right': 'left', 'inside top': 'bottom'}.get(loc)
    if side is None or (orient == 'vertical') != (side in ('left', 'right')):
        side = 'right' if orient == 'vertical' else 'bottom'
    return side


def add_colorbar(fig, ax, mappable, panel, report, label):
    """Attach a colour bar that the user can place, resize and drag.

    The bar is an inset of the plot, so it follows the plot when the layout
    changes; :func:`place_colorbar` puts it at the chosen position, clear of
    a right-hand axis and of tick labels.
    """
    orient = _cbar_orientation(panel)
    cax = ax.inset_axes([1.02, 0.0, 0.04, 1.0])
    cb = fig.colorbar(mappable, cax=cax, orientation=orient, ticklocation=_cbar_side(panel, orient))
    cax.set_zorder(ax.get_zorder() + 0.2)
    cb.outline.set_linewidth(0.6)
    cb.ax.tick_params(direction='out', length=3, width=0.6)
    cb.set_label(panel.get('cbar_label') or label)
    _tidy_log_ticks(cb)
    hd = handles(report, panel)
    hd['cbar'] = cb
    hd['cbar_orient'] = orient
    return cb


def _decoration_extent(fig, axes, renderer):
    """Union of the tight boxes of ``axes`` in figure fractions (or None)."""
    inv = fig.transFigure.inverted()
    boxes = []
    for a in axes:
        if a is None or not a.get_visible():
            continue
        try:
            tb = a.get_tightbbox(renderer)
        except Exception:
            tb = None
        if tb is not None and tb.width > 0:
            boxes.append(tb.transformed(inv))
    if not boxes:
        return None
    from matplotlib.transforms import Bbox
    return Bbox.union(boxes)


def place_colorbar(fig, panel, handles_):
    """Put a panel's colour bar where the user wants it, clear of the plot's labels."""
    cb = handles_.get('cbar')
    ax = handles_.get('ax')
    if cb is None or ax is None:
        return
    canvas = fig.canvas
    if not hasattr(canvas, 'get_renderer'):
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        canvas = FigureCanvasAgg(fig)
    renderer = canvas.get_renderer()
    pos = ax.get_position()
    fw, fh = fig.get_figwidth(), fig.get_figheight()
    ax_w_in = max(1e-6, pos.width * fw)
    ax_h_in = max(1e-6, pos.height * fh)
    loc = panel.get('cbar_loc') or 'right'
    orient = handles_.get('cbar_orient') or 'vertical'
    thick_in = float_or_none(panel.get('cbar_width')) or 0.14
    pad_in = float_or_none(panel.get('cbar_pad'))
    pad_in = 0.12 if pad_in is None else max(0.0, pad_in)
    inside = loc.startswith('inside')
    length = float_or_none(panel.get('cbar_length'))
    length = (0.45 if inside else 1.0) if not length else max(0.1, min(1.0, length))
    ax2 = handles_.get('ax2')
    cb.ax.set_axes_locator(None)
    cb.ax.set_in_layout(False)
    try:
        bounds = _cbar_bounds(fig, ax, ax2, panel, renderer, loc, orient, pos,
                              (fw, fh, ax_w_in, ax_h_in, thick_in, pad_in, length, inside))
    finally:
        cb.ax.set_in_layout(True)
    cb.ax.set_axes_locator(_CbarLocator(ax, bounds))
    cb.ax.patch.set_alpha(0.0 if inside else 1.0)


def _cbar_bounds(fig, ax, ax2, panel, renderer, loc, orient, pos, sizes):
    """Inset bounds ``[x0, y0, w, h]`` (axes fraction) of a colour bar."""
    fw, fh, ax_w_in, ax_h_in, thick_in, pad_in, length, inside = sizes
    if orient == 'vertical':
        w = thick_in / ax_w_in
        h = length
        y0 = (1 - h) / 2
        if loc == 'right':
            extra = 0.0
            if ax2 is not None:
                ext = _decoration_extent(fig, [ax2], renderer)
                if ext is not None:
                    extra = max(0.0, (ext.x1 - pos.x1) * fw)
            x0 = 1 + (pad_in + extra) / ax_w_in
        elif loc == 'left':
            ext = _decoration_extent(fig, [ax], renderer)
            extra = max(0.0, (pos.x0 - ext.x0) * fw) if ext is not None else 0.6
            x0 = -(pad_in + extra + thick_in) / ax_w_in
        elif loc == 'inside right':
            x0 = 1 - (0.12 + thick_in) / ax_w_in
            y0 = 1 - h - 0.12 / ax_h_in
        else:
            xy = panel.get('cbar_xy') or [1.05, 0.0]
            x0, y0 = float(xy[0]), float(xy[1])
        bounds = [x0, y0, w, h]
    else:
        h = thick_in / ax_h_in
        w = length
        x0 = (1 - w) / 2
        if loc == 'top':
            y0 = 1 + pad_in / ax_h_in
        elif loc == 'bottom':
            ext = _decoration_extent(fig, [ax], renderer)
            extra = max(0.0, (pos.y0 - ext.y0) * fh) if ext is not None else 0.5
            y0 = -(pad_in + extra + thick_in) / ax_h_in
        elif loc == 'inside top':
            y0 = 1 - (0.12 + thick_in) / ax_h_in
            x0 = 1 - w - 0.12 / ax_w_in
        else:
            xy = panel.get('cbar_xy') or [0.0, 1.05]
            x0, y0 = float(xy[0]), float(xy[1])
        bounds = [x0, y0, w, h]
    return bounds
