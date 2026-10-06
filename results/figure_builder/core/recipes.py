"""One-click panels that recreate the app's visualisation nodes inside the Figure Builder.

Each recipe returns a ready panel dict pointing at the isotopes present in the
data, so a user can start from the familiar node figure and then change
anything in it.
"""

from __future__ import annotations

from results.figure_builder.core.spec import make_panel

RECIPES: dict[str, str] = {
    'histogram': 'Histogram node — size distribution',
    'bar': 'Bar Chart node — particles containing each isotope',
    'box': 'Box Plot node — distribution per sample',
    'correlation': 'Correlation node — X against Y with fit and r',
    'pie': 'Pie Chart node — particles containing each isotope',
    'composition': 'Composition node — element combinations pie',
    'heatmap': 'Heatmap node — combinations × isotopes',
    'molar_ratio': 'Molar Ratio node — ratio histogram',
    'isotope_ratio': 'Isotope Ratio node — ratio vs counts with Poisson band',
    'ternary': 'Ternary node — three-element composition',
    'single_multi': 'Single/Multiple node — single vs multi-element',
    'matrix': 'Correlation Matrix node',
    'concentration': 'Concentration node — values per sample with geometric mean',
    'network': 'Network node — correlation network',
    'clustering': 'Clustering node — PCA projection by class',
}
"""Recipe key → menu label."""


def _same_element_pair(labels):
    """Two isotopes of the same element (for isotope ratios), or the first two labels."""
    from results.figure_builder.core.expressions import split_symbol
    by_symbol: dict[str, list[str]] = {}
    for lab in labels:
        sym, _mass = split_symbol(lab)
        by_symbol.setdefault(sym, []).append(lab)
    for labs in by_symbol.values():
        if len(labs) >= 2:
            return labs[0], labs[1]
    return (labels[0], labels[1]) if len(labels) > 1 else (labels[0], labels[0])


def _has(table, prefix, label) -> bool:
    """Whether the data carries ``prefix`` values (diameter, moles...) for ``label``."""
    try:
        import numpy as np
        return bool(len(table)) and bool(np.any(table.column(f'{prefix}:{label}') > 0))
    except Exception:
        return False


def recipe_panel(key: str, table, **overrides) -> dict:
    """A new panel recreating the named node figure for ``table``'s isotopes.

    Args:
        key: One of :data:`RECIPES`.
        table: The :class:`ParticleTable` the panel will draw.
        **overrides: Extra panel fields (``rect`` for example).
    """
    labels = list(getattr(table, 'labels', []) or [])
    if not labels:
        labels = ['Isotope']
    first = labels[0]
    second = labels[1] if len(labels) > 1 else first
    third = labels[2] if len(labels) > 2 else second
    multi = len(set(table.column('sample').tolist())) > 1 if len(table) else False
    by = 'sample' if multi else 'none'
    some = ', '.join(labels[:8])
    has_ml = table.has_per_ml() if hasattr(table, 'has_per_ml') else False
    tail = RECIPES.get(key, '').split('—')[-1].strip()
    title = tail[:1].upper() + tail[1:]
    p: dict = {}
    if key == 'histogram':
        value = f'd:{first}' if _has(table, 'd', first) else first
        p = dict(kind='histogram', value=value, log_x=True, bin_mode='width', bin_width=0.05,
                 kde=True, mark_stats='median', group_by=by, per_ml=has_ml, summary_box=True)
    elif key == 'bar':
        p = dict(kind='bar', value=some, agg='detect', group_by=by, bar_swap=True, bar_values=True,
                 min_count=10, per_ml=has_ml)
    elif key == 'box':
        p = dict(kind='box', value=f'mass:{first}', group_by=by, log_y=True, summary_box=True, show_mean=True)
    elif key == 'correlation':
        p = dict(kind='scatter', x=first, y=second, log_x=True, log_y=True, show_fit=True, show_r=True,
                 fit_band=False, sd_band=True, saturation=10000, group_by=by)
    elif key == 'pie':
        p = dict(kind='pie', pie_mode='detect', isotopes=some, other_pct=1.0, pie_labels='name_pct',
                 pie_label_pos='outside', legend=False, per_ml=has_ml)
    elif key == 'composition':
        p = dict(kind='pie', pie_mode='combinations', isotopes=some, top_n=8, other_pct=1.0,
                 pie_labels='name_pct', pie_label_pos='outside', legend=False)
    elif key == 'heatmap':
        p = dict(kind='heatmap', heat_rows='combinations', isotopes=some, top_n=10, heat_value='mean',
                 data_type='Element Mass (fg)', log_color=True, min_count=10)
    elif key == 'molar_ratio':
        q = 'moles' if _has(table, 'moles', first) and _has(table, 'moles', second) else 'counts'
        p = dict(kind='histogram', value=f'{q}:{first}/{q}:{second}', log_x=True, kde=True,
                 mark_stats='all', stat_band='iqr', summary_box=True, trim_pct=99, group_by=by)
    elif key == 'isotope_ratio':
        a, b = _same_element_pair(labels)
        p = dict(kind='scatter', x=f'counts:{b}', y=f'counts:{a}/counts:{b}', log_x=True,
                 poisson_band=2, natural_line=True, saturation=10000, group_by=by,
                 hlines='', marker_size=10)
    elif key == 'ternary':
        p = dict(kind='ternary', a=first, b=second, c=third, tern_filter='all', tern_mean=True,
                 grid=True, group_by=by)
    elif key == 'single_multi':
        p = dict(kind='pie', pie_mode='single_multi', isotopes=some, donut=True,
                 donut_text='{n}\nparticles', pie_labels='count_pct', per_ml=has_ml)
    elif key == 'matrix':
        p = dict(kind='corr_matrix', isotopes=some, zero_handling='both', min_n=10, cell_label='r')
    elif key == 'concentration':
        p = dict(kind='strip', value=f'mass:{first}', group_by=by, strip_summary='gmean',
                 strip_values=True, log_y=True)
    elif key == 'network':
        p = dict(kind='network', isotopes=some, net_r_min=0.3, min_n=10, node_size='sum')
    elif key == 'clustering':
        p = dict(kind='pca', isotopes=some, group_by='class' if getattr(table, 'class_order', None) else by,
                 pca_transform='clr')
    else:
        raise KeyError(key)
    p.setdefault('title', title)
    p.update(overrides)
    return make_panel(**p)
