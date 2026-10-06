"""Chart drawers, one function per panel kind.

Every drawer has the signature ``draw(fig, ax, panel, table, report, style)``
and raises :class:`~results.figure_builder.core.expressions.ExpressionError`
with a readable message when the panel cannot be drawn.
"""

from results.figure_builder.charts.categorical import (
    draw_bar, draw_combinations, draw_composition, draw_pie)
from results.figure_builder.charts.matrices import (
    draw_cooccurrence, draw_corr_matrix, draw_heatmap, draw_pairs)
from results.figure_builder.charts.distributions import draw_distribution, draw_histogram
from results.figure_builder.charts.extra import (
    draw_contour, draw_hexbin, draw_parallel, draw_radar, draw_ridgeline, draw_strip)
from results.figure_builder.charts.more import (
    draw_ecdf, draw_lollipop, draw_timeline, draw_treemap)
from results.figure_builder.charts.network import draw_network, draw_pca
from results.figure_builder.charts.special import draw_code, draw_ternary, draw_text
from results.figure_builder.charts.xy import draw_density, draw_line, draw_scatter

DRAWERS = {
    'scatter': draw_scatter,
    'line': draw_line,
    'histogram': draw_histogram,
    'box': draw_distribution,
    'violin': draw_distribution,
    'bar': draw_bar,
    'pie': draw_pie,
    'density': draw_density,
    'ternary': draw_ternary,
    'corr_matrix': draw_corr_matrix,
    'heatmap': draw_heatmap,
    'cooccurrence': draw_cooccurrence,
    'combinations': draw_combinations,
    'composition': draw_composition,
    'pairs': draw_pairs,
    'strip': draw_strip,
    'ridgeline': draw_ridgeline,
    'hexbin': draw_hexbin,
    'contour': draw_contour,
    'radar': draw_radar,
    'parallel': draw_parallel,
    'ecdf': draw_ecdf,
    'lollipop': draw_lollipop,
    'treemap': draw_treemap,
    'timeline': draw_timeline,
    'network': draw_network,
    'pca': draw_pca,
    'text': draw_text,
    'code': draw_code,
}
