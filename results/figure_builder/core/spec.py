"""The Figure Builder figure description ("spec"): defaults, panels and layouts.

A spec is plain JSON-serialisable data::

    {
        'data_type': 'Counts',
        'variables': [{'name': 'ratio', 'expr': 'Fe/Cu'}, ...],
        'figure': {'width': 8.0, 'height': 6.0, 'palette': 'IsotopeTrack', ...},
        'panels': [panel, ...],
    }

Each panel owns a rectangle on the page (fractions of the figure, origin
top-left, exactly as the user drew it), a ``kind`` and that kind's options.
"""

from __future__ import annotations

import copy
import string
import uuid

from results.figure_builder.core.styles import PALETTES, TEMPLATES


PALETTE = PALETTES['IsotopeTrack']
"""The default categorical palette."""


OTHER_COLOR = '#9a9a9a'


PANEL_KINDS = {
    'scatter': 'Scatter (X vs Y)',
    'line': 'Line / trend (binned)',
    'density': 'Density map (2-D histogram)',
    'hexbin': 'Hexbin density',
    'contour': 'Density contours (2-D KDE)',
    'pairs': 'Scatter matrix (pair plot)',
    'parallel': 'Parallel coordinates',
    'histogram': 'Histogram',
    'ecdf': 'Cumulative distribution (ECDF)',
    'ridgeline': 'Ridgeline (stacked distributions)',
    'box': 'Box plot',
    'violin': 'Violin plot',
    'strip': 'Dot plot (every particle)',
    'bar': 'Bar chart',
    'pie': 'Pie / donut',
    'composition': 'Composition (100% bars)',
    'radar': 'Radar (composition profile)',
    'combinations': 'Element combinations',
    'lollipop': 'Lollipop / dumbbell',
    'treemap': 'Treemap',
    'network': 'Correlation network',
    'pca': 'PCA of compositions (biplot)',
    'timeline': 'Particle timeline',
    'corr_matrix': 'Correlation matrix',
    'heatmap': 'Heatmap',
    'cooccurrence': 'Co-occurrence matrix',
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
    'font_family': 'Times New Roman',
    'font_size': 12,
    'title_size': 0,
    'label_size': 0,
    'tick_size': 0,
    'axes_linewidth': 1.0,
    'title': '',
    'panel_letters': True,
    'letter_style': 'a',
    'letter_size': 0,
    'label_style': 'isotope',
    'background': '#ffffff',
    'ink': '',
    'sketchy': False,
    'palette': 'IsotopeTrack',
    'text_styles': {},
}


PANEL_DEFAULTS = {
    'id': '',
    'rect': [0.0, 0.0, 1.0, 1.0],
    'kind': 'scatter',
    'data_type': '',
    'title': '',
    'isotopes': '',
    'cbar_label': '',
    'cbar_loc': 'right',
    'cbar_length': 0.0,
    'cbar_width': 0.14,
    'cbar_pad': 0.12,
    'cbar_xy': [],
    'cbar_orient': '',
    'cbar_log': False,
    'a_label': '',
    'b_label': '',
    'c_label': '',
    'text_styles': {},
    'item_labels': {},
    'corr_method': 'pearson',
    'log_values': False,
    'triangle': 'full',
    'annotate': True,
    'show_sig': False,
    'min_n': 10,
    'div_cmap': 'RdBu_r',
    'heat_rows': 'groups',
    'heat_value': 'mean',
    'heat_norm': 'none',
    'log_color': False,
    'transpose': False,
    'max_rows': 2000,
    'cooc_mode': 'joint',
    'top_n': 15,
    'as_percent': True,
    'combo_filter': 'all',
    'comp_mode': 'mean_fraction',
    'pairs_upper': 'r',
    'shapes': [],
    'x_ticks': '',
    'y_ticks': '',
    'x_format': 'auto',
    'y_format': 'auto',
    'invert_x': False,
    'invert_y': False,
    'grid_axis': 'both',
    'grid_minor': False,
    'grid_color': '#d9dde3',
    'axis_color': '',
    'summary_box': False,
    'summary_loc': 'upper right',
    'mark_stats': 'none',
    'fit_dist': 'none',
    'strip_summary': 'mean_sd',
    'jitter': 0.35,
    'sina': True,
    'overlap': 0.6,
    'levels': 6,
    'filled': True,
    'radar_mode': 'share',
    'radar_fill': True,
    'max_lines': 400,
    'parallel_scale': 'log',
    'lolli_stat': 'median',
    'lolli_sort': True,
    'lolli_vertical': False,
    'time_mode': 'rate',
    'share_mode': 'groups',
    'ellipse': 'none',
    'hull': False,
    'trend': 'none',
    'trend_bins': 15,
    'marginals': 'none',
    'fit_band': True,
    'saturation': 0.0,
    'trim_pct': 0.0,
    'min_count': 0,
    'sort_groups': 'none',
    'per_ml': False,
    'stat_band': 'none',
    'band_color': '',
    'dl_value': '',
    'dl_label': '',
    'dl_color': '',
    'c_min': '',
    'c_max': '',
    'bin_mode': 'count',
    'bin_width': 0.25,
    'bar_values': False,
    'violin_style': 'full',
    'show_outliers': True,
    'bandwidth': 0.0,
    'strip_values': False,
    'bar_swap': False,
    'sort_items': 'none',
    'pie_labels': 'pct',
    'pie_label_pos': 'inside',
    'other_pct': 0.0,
    'start_angle': 90.0,
    'pie_explode': 0.0,
    'donut_text': '',
    'heat_spread': 'none',
    'heat_sort': 'count',
    'zero_handling': '',
    'r_threshold': 0.0,
    'cell_label': 'r',
    'corr_diff': False,
    'sd_band': False,
    'poisson_band': 0.0,
    'natural_line': False,
    'natural_color': '',
    'tern_filter': 'any',
    'tern_mean': False,
    'net_r_min': 0.3,
    'node_size': 'sum',
    'edge_pos_color': '',
    'edge_neg_color': '',
    'pca_transform': 'clr',
    'pca_loadings': True,
    'facet': 'none',
    'facet_cols': 0,
    'facet_share': True,
    'inset_zoom': '',
    'inset_loc': 'upper left',
    'inset_size': 0.4,
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
    'marker_size': 16.0,
    'edge_color': '#1f2937',
    'edge_width': 0.4,
    'alpha': 0.75,
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
    'legend_frame': True,
    'legend_xy': [],
    'grid': False,
    'frame': 'box',
    'tick_dir': 'out',
    'minor_ticks': True,
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
