"""Tabbed property editor for one Figure Builder panel.

The editor splits a panel's settings into tabs (Data, Groups, Style, Axes,
Stats, Notes). Rows show or hide according to the panel's chart type,
grouping mode and statistical test, and tabs with nothing relevant are
hidden. Every edit is written straight into the panel dict and announced
with ``changed`` so the preview can redraw.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame, QGroupBox,
    QLabel, QLineEdit, QMenu, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox,
    QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

from results.figure_builder.core import engine as E
from results.figure_builder.charts.categorical import BAR_SORTS, PIE_LABELS, PIE_MODES
from results.figure_builder.charts.distributions import MARKS
from results.figure_builder.charts.matrices import HEAT_SPREADS, ZERO_HANDLING
from results.figure_builder.charts.more import LOLLI_STATS, SHARE_MODES, TIME_MODES
from results.figure_builder.charts.network import NODE_SIZES, PCA_TRANSFORMS
from results.figure_builder.charts.special import TERNARY_FILTERS
from results.figure_builder.charts.overlays import ELLIPSES, INSET_LOCS, MARGINALS, TRENDS
from results.figure_builder.core import styles as S
from results.figure_builder.core.common import BANDS, GROUP_SORTS, HATCHES, SHAPE_TYPES, TICK_FORMATS
from results.figure_builder.core.expressions import (
    DATA_TYPES, QUANTITY_PREFIXES, split_list, validate)
from results.figure_builder.ui.widgets import (
    ColorButton, ExpressionEdit, GroupsTable, RowTable, mono_font)

PLOTS = {'scatter', 'line', 'histogram', 'box', 'violin', 'bar', 'density', 'hexbin', 'contour', 'strip',
         'ecdf', 'timeline', 'lollipop'}
XY = {'scatter', 'density', 'hexbin', 'contour'}
XLINE = XY | {'line'}
DIST = {'box', 'violin'}
VALUED = {'histogram', 'box', 'violin', 'bar', 'pie', 'strip', 'ridgeline', 'ecdf', 'timeline'}
SUMMARISED = {'histogram', 'box', 'violin', 'strip', 'ridgeline'}
MATRIX = {'corr_matrix', 'heatmap', 'cooccurrence'}
CBAR = {'scatter', 'density', 'hexbin', 'ternary'} | MATRIX
MARKABLE = {'histogram', 'ecdf', 'ridgeline', 'box', 'violin', 'strip', 'scatter', 'bar'}
SORTABLE = {'box', 'violin', 'strip', 'ridgeline', 'histogram', 'ecdf'}
PER_ML = {'histogram', 'bar', 'pie'}
ITEMS = MATRIX | {'composition', 'combinations', 'pairs', 'radar', 'parallel', 'lollipop', 'treemap',
                  'network', 'pca', 'pie'}
COMBOS = {'combinations', 'treemap'}
SHARES = {'treemap'}
TESTABLE = {'histogram', 'box', 'violin', 'bar', 'strip', 'ridgeline'}
GROUPING = {'scatter', 'line', 'histogram', 'box', 'violin', 'bar', 'pie', 'ternary', 'code',
            'strip', 'ridgeline', 'contour', 'hexbin', 'ecdf', 'timeline'} | ITEMS
ALL = set(E.PANEL_KINDS)
MARKED = {'scatter', 'ternary', 'line', 'pairs', 'strip', 'timeline', 'lollipop'}
LEGENDED = ALL - {'text', 'code', 'box', 'violin', 'density', 'hexbin', 'strip', 'ridgeline'} - MATRIX
SHAPED = set(E.SHAPE_KINDS)
TICKED = PLOTS | {'ridgeline', 'parallel', 'combinations', 'composition'}
RENAMEABLE = ITEMS | {'bar', 'pie'}

AGG = {'mean': 'Mean', 'median': 'Median', 'sum': 'Sum', 'count': 'Particle count'}

RULE_COLUMNS = [
    ('name', 'Name', 'text', None, 100),
    ('when', 'Condition', 'mask', None, 0),
    ('color', 'Colour', 'color', None, 58),
]

SERIES_COLUMNS = [
    ('label', 'Label', 'text', None, 90),
    ('x', 'X', 'expr', None, 0),
    ('y', 'Y', 'expr', None, 90),
    ('filter', 'Only where', 'mask', None, 90),
    ('style', 'Style', 'combo', {'points': 'Points', 'line': 'Line', 'points+line': 'Both'}, 80),
    ('marker', 'Marker', 'combo', S.MARKERS, 90),
    ('size', 'Size', 'float', (1, 300, 2), 64),
    ('color', 'Colour', 'color', None, 58),
]

SHAPE_COLUMNS = [
    ('type', 'Shape', 'combo', SHAPE_TYPES, 150),
    ('x1', 'From x', 'text', None, 64),
    ('x2', 'To x', 'text', None, 64),
    ('y1', 'From y', 'text', None, 64),
    ('y2', 'To y', 'text', None, 64),
    ('slope', 'Slope', 'text', None, 56),
    ('intercept', 'Intercept', 'text', None, 64),
    ('label', 'Legend label', 'text', None, 0),
    ('color', 'Colour', 'color', None, 58),
    ('alpha', 'Opacity', 'float', (0, 1, 0.05), 64),
    ('hatch', 'Hatch', 'combo', HATCHES, 90),
    ('style', 'Line', 'combo', S.LINE_STYLES, 80),
    ('layer', 'Layer', 'combo', {'back': 'Behind data', 'front': 'In front'}, 100),
    ('text', 'Write label', 'check', None, 70),
]

ANNOTATION_COLUMNS = [
    ('text', 'Text', 'text', None, 0),
    ('x', 'x', 'text', None, 48),
    ('y', 'y', 'text', None, 48),
    ('coords', 'Position in', 'combo', {'axes': 'Panel (0–1)', 'data': 'Axis values'}, 100),
    ('arrow_x', 'Arrow x', 'text', None, 58),
    ('arrow_y', 'Arrow y', 'text', None, 58),
    ('size', 'Size', 'float', (4, 48, 1), 58),
    ('color', 'Colour', 'color', None, 58),
    ('bold', 'Bold', 'check', None, 40),
    ('italic', 'Italic', 'check', None, 40),
    ('box', 'Box', 'check', None, 40),
]

FIELDS = [
    ('Data', 'Chart', 'kind', 'Chart type', 'combo', ALL, E.PANEL_KINDS),
    ('Data', 'Chart', 'data_type', 'Quantity (unit)', 'combo', ALL - {'text'},
     {'': 'Figure default', **{k: k for k in DATA_TYPES}}),
    ('Data', 'Chart', 'title', 'Panel title', 'text', ALL, 'optional'),
    ('Data', 'What to plot', 'x', 'X', 'expr', XLINE, 'e.g. Fe   or   log(Ag)'),
    ('Data', 'What to plot', 'y', 'Y', 'expr', XLINE, 'e.g. Fe/Cu'),
    ('Data', 'What to plot', 'y2', 'Right Y axis', 'expr', {'scatter'}, 'optional, e.g. mass:Fe'),
    ('Data', 'What to plot', 'value', 'Value', 'expr', VALUED, 'e.g. mass:Ag'),
    ('Data', 'What to plot', 'isotopes', 'Isotopes', 'expr', ITEMS, 'blank = all, or e.g. Ag, Au, Fe/Cu'),
    ('Data', 'What to plot', 'a', 'Top corner (A)', 'expr', {'ternary'}, 'e.g. Ag'),
    ('Data', 'What to plot', 'b', 'Left corner (B)', 'expr', {'ternary'}, 'e.g. Au'),
    ('Data', 'What to plot', 'c', 'Right corner (C)', 'expr', {'ternary'}, 'e.g. Cu'),
    ('Data', 'What to plot', 'agg', 'Summarise as', 'combo', {'bar', 'line'}, AGG),
    ('Data', 'What to plot', 'pie_mode', 'Slices are', 'combo', {'pie'}, PIE_MODES),
    ('Data', 'What to plot', 'heat_rows', 'Rows', 'combo', {'heatmap'},
     {'groups': 'Groups (samples, classes, rules)', 'combinations': 'Element combinations',
      'particles': 'Individual particles'}),
    ('Data', 'What to plot', 'heat_value', 'Cell value', 'combo', {'heatmap'},
     {'mean': 'Mean', 'median': 'Median', 'gmean': 'Geometric mean', 'mode': 'Mode', 'sum': 'Sum',
      'detect': 'Detected in (% of particles)', 'count': 'Particles detected'}),
    ('Data', 'What to plot', 'heat_sort', 'Rank combinations by', 'combo', {'heatmap'},
     {'count': 'Number of particles', 'amount': 'Share of the summed amount'}),
    ('Data', 'What to plot', 'zero_handling', 'Particles in each pair', 'combo', {'corr_matrix'},
     {'': 'Automatic (hide zero values)', **ZERO_HANDLING}),
    ('Data', 'What to plot', 'corr_diff', 'Difference of the first two groups (Δr)', 'check',
     {'corr_matrix'}, None),
    ('Data', 'What to plot', 'tern_filter', 'Keep particles with', 'combo', {'ternary'}, TERNARY_FILTERS),
    ('Data', 'What to plot', 'net_r_min', 'Link when |r| ≥', 'float', {'network'}, (0, 1, 0.05)),
    ('Data', 'What to plot', 'node_size', 'Node size shows', 'combo', {'network'}, NODE_SIZES),
    ('Data', 'What to plot', 'pca_transform', 'Prepare values', 'combo', {'pca'}, PCA_TRANSFORMS),
    ('Data', 'What to plot', 'per_ml', 'Count as particles per mL', 'check', PER_ML, None),
    ('Data', 'What to plot', 'corr_method', 'Correlation', 'combo', {'corr_matrix', 'pairs'},
     {'pearson': 'Pearson', 'spearman': 'Spearman (rank)', 'kendall': 'Kendall'}),
    ('Data', 'What to plot', 'log_values', 'Log-transform values first', 'check',
     {'corr_matrix', 'pairs', 'network'}, None),
    ('Data', 'What to plot', 'min_n', 'Min. particles per pair', 'int', {'corr_matrix', 'network'}, (3, 1000000)),
    ('Data', 'What to plot', 'cooc_mode', 'Cell value', 'combo', {'cooccurrence'},
     {'joint': '% of particles with both', 'conditional': '% of row particles with column',
      'count': 'Number of particles'}),
    ('Data', 'What to plot', 'comp_mode', 'Share computed as', 'combo', {'composition'},
     {'mean_fraction': "Mean of each particle's share", 'total': 'Share of the summed amounts'}),
    ('Data', 'What to plot', 'lolli_stat', 'Each isotope shows', 'combo', {'lollipop'}, LOLLI_STATS),
    ('Data', 'What to plot', 'time_mode', 'Show', 'combo', {'timeline'}, TIME_MODES),
    ('Data', 'What to plot', 'share_mode', 'Share out', 'combo', SHARES, SHARE_MODES),
    ('Data', 'What to plot', 'combo_filter', 'Combinations', 'combo', COMBOS,
     {'all': 'All', 'single': 'Single-element only', 'multi': 'Multi-element only'}),
    ('Data', 'What to plot', 'top_n', 'Show the top', 'int', COMBOS | {'heatmap', 'pie'}, (1, 500)),
    ('Data', 'What to plot', 'as_percent', 'As % of particles', 'check', {'combinations'}, None),
    ('Data', 'What to plot', 'pairs_upper', 'Upper triangle', 'combo', {'pairs'},
     {'r': 'Correlation value', 'scatter': 'Scatter (mirror)', 'empty': 'Empty'}),
    ('Data', 'What to plot', 'radar_mode', 'Spokes show', 'combo', {'radar'},
     {'share': 'Mean share of each isotope (%)', 'detect': 'Detected in (% of particles)',
      'mean': 'Mean value (scaled to the largest group)'}),
    ('Data', 'What to plot', 'parallel_scale', 'Axes', 'combo', {'parallel'},
     {'log': 'Log, scaled 0–1', 'minmax': 'Linear, scaled 0–1', 'raw': 'Raw values'}),
    ('Data', 'What to plot', 'max_lines', 'Max lines per group', 'int', {'parallel'}, (20, 100000)),
    ('Data', 'Which particles', 'filter', 'Only where', 'mask', ALL - {'text'},
     'e.g. Ag > 0 and Au > 0'),
    ('Data', 'Which particles', 'saturation', 'Drop saturated particles (counts ≥, 0 = off)', 'float',
     ALL - {'text', 'code'}, (0, 1e9, 1000)),
    ('Data', 'Which particles', 'trim_pct', 'Trim outliers: keep up to percentile (0 = off)', 'float',
     VALUED - {'pie'} | {'scatter'}, (0, 99.9, 0.5)),
    ('Data', 'Which particles', 'min_count', 'Hide groups / rows with fewer particles than', 'int',
     SORTABLE | {'bar', 'heatmap'}, (0, 1000000)),
    ('Data', 'Which particles', 'drop_zeros', 'Hide zero values', 'check',
     XLINE | VALUED - {'pie'} | {'corr_matrix', 'heatmap', 'pairs'}, None),
    ('Data', 'Extra series on this plot', 'series', '', 'series', {'scatter'}, None),
    ('Data', 'Text', 'text', '', 'longtext', {'text'}, None),
    ('Data', 'Text', 'text_size', 'Text size (0 = auto)', 'float', {'text'}, (0, 72, 1)),
    ('Data', 'Python', 'code', '', 'code', {'code'}, None),
    ('Groups', 'Grouping', 'group_by', 'Group / colour by', 'combo', GROUPING, E.GROUP_MODES),
    ('Groups', 'Grouping', 'color', 'Colour', 'color', PLOTS | {'ternary', 'network'}, None),
    ('Groups', 'Grouping', 'sort_groups', 'Order groups', 'combo', SORTABLE, GROUP_SORTS),
    ('Groups', 'One small plot per group', 'facet', 'Layout', 'combo', ALL - {'text', 'code', 'pairs'},
     {'none': 'All groups together', 'groups': 'One small plot per group'}),
    ('Groups', 'One small plot per group', 'facet_cols', 'Columns (0 = auto)', 'int',
     ALL - {'text', 'code', 'pairs'}, (0, 12)),
    ('Groups', 'One small plot per group', 'facet_share', 'Same axis ranges', 'check',
     ALL - {'text', 'code', 'pairs'}, None),
    ('Groups', 'Rules (first match wins)', 'rules', '', 'rules', set(), None),
    ('Groups', 'Rules (first match wins)', 'show_other', 'Show the rest', 'check', set(), None),
    ('Groups', 'Rules (first match wins)', 'other_label', 'Name for the rest', 'text', set(), None),
    ('Groups', 'Show, rename, recolour, reorder', 'groups', '', 'groups', set(), None),
    ('Groups', 'Show, rename, recolour, reorder', 'show_n', 'Show counts (n=…)', 'check',
     GROUPING - {'code', 'pie'} - MATRIX, None),
    ('Style', 'Markers', 'marker', 'Shape', 'combo', MARKED - {'pairs'}, S.MARKERS),
    ('Style', 'Markers', 'marker_size', 'Size', 'float', MARKED, (1, 400, 1)),
    ('Style', 'Markers', 'alpha', 'Opacity', 'float', {'scatter', 'ternary', 'pairs', 'strip', 'parallel'}, (0.05, 1, 0.05)),
    ('Style', 'Markers', 'edge_color', 'Outline colour', 'color', {'scatter', 'ternary', 'bar', 'pie'}, None),
    ('Style', 'Markers', 'edge_width', 'Outline width', 'float', {'scatter', 'ternary', 'bar', 'pie'}, (0, 6, 0.2)),
    ('Style', 'Markers', 'size_by', 'Size by value', 'expr', {'scatter'}, 'optional, e.g. total'),
    ('Style', 'Around the groups', 'ellipse', 'Ellipse', 'combo', {'scatter'}, ELLIPSES),
    ('Style', 'Around the groups', 'hull', 'Outline (convex hull)', 'check', {'scatter'}, None),
    ('Style', 'Around the groups', 'trend', 'Trend curve', 'combo', {'scatter'}, TRENDS),
    ('Style', 'Around the groups', 'trend_bins', 'Trend points', 'int', {'scatter'}, (4, 60)),
    ('Style', 'Around the groups', 'marginals', 'Along the edges', 'combo', {'scatter'}, MARGINALS),
    ('Style', 'Colour scale', 'color_by', 'Colour by value', 'expr', {'scatter', 'ternary'}, 'optional, e.g. total'),
    ('Style', 'Colour scale', 'colormap', 'Colour map', 'combo',
     {'scatter', 'density', 'heatmap', 'cooccurrence', 'hexbin', 'ternary'},
     {k: k for k in S.COLORMAPS}),
    ('Style', 'Colour scale', 'div_cmap', 'Colour map', 'combo', {'corr_matrix'},
     {k: k for k in ('RdBu_r', 'coolwarm', 'bwr', 'seismic', 'PiYG', 'PRGn', 'BrBG', 'RdYlBu_r')}),
    ('Style', 'Colour scale', 'reverse_cmap', 'Reverse colour map', 'check',
     {'scatter', 'density', 'hexbin'} | MATRIX, None),
    ('Style', 'Colour bar', 'cbar_loc', 'Position', 'combo', CBAR, E.CBAR_LOCATIONS),
    ('Style', 'Colour bar', 'cbar_length', 'Length (0 = auto)', 'float', CBAR, (0, 1, 0.05)),
    ('Style', 'Colour bar', 'cbar_width', 'Thickness (inches)', 'float', CBAR, (0.04, 1, 0.02)),
    ('Style', 'Colour bar', 'cbar_pad', 'Gap from the plot (inches)', 'float', CBAR, (0, 2, 0.02)),
    ('Style', 'Colour bar', 'cbar_log', 'Log colour scale', 'check', {'scatter', 'ternary'}, None),
    ('Style', 'Colour bar', 'c_min', 'Colour range from', 'text', CBAR, 'auto'),
    ('Style', 'Colour bar', 'c_max', 'Colour range to', 'text', CBAR, 'auto'),
    ('Style', 'Colour scale', 'y2_color', 'Right axis colour', 'color', {'scatter'}, None),
    ('Style', 'Lines', 'line_width', 'Line width', 'float',
     {'scatter', 'line', 'histogram', 'radar', 'ecdf', 'lollipop', 'timeline'}, (0.2, 8, 0.2)),
    ('Style', 'Lines', 'line_style', 'Line style', 'combo', {'scatter', 'line', 'histogram'}, S.LINE_STYLES),
    ('Style', 'Chart options', 'annotate', 'Show values', 'check',
     MATRIX | {'composition', 'combinations', 'lollipop'}, None),
    ('Style', 'Chart options', 'lolli_vertical', 'Vertical', 'check', {'lollipop'}, None),
    ('Style', 'Chart options', 'lolli_sort', 'Sort by value', 'check', {'lollipop'}, None),
    ('Style', 'Chart options', 'show_sig', 'Significance stars', 'check', {'corr_matrix'}, None),
    ('Style', 'Chart options', 'triangle', 'Show', 'combo', {'corr_matrix', 'cooccurrence'},
     {'full': 'Full matrix', 'lower': 'Lower triangle', 'upper': 'Upper triangle'}),
    ('Style', 'Chart options', 'heat_norm', 'Normalise', 'combo', {'heatmap'},
     {'none': 'No', 'particle': '% of each particle first', 'row': 'Each row to its max',
      'column': 'Each column to its max', 'zscore': 'z-score per column'}),
    ('Style', 'Chart options', 'heat_spread', 'Spread under values', 'combo', {'heatmap'}, HEAT_SPREADS),
    ('Style', 'Chart options', 'cell_label', 'Cells show', 'combo', {'corr_matrix'},
     {'r': 'Correlation', 'n': 'Number of particles', 'both': 'Both'}),
    ('Style', 'Chart options', 'r_threshold', 'Blank cells with |r| below', 'float', {'corr_matrix'},
     (0, 1, 0.05)),
    ('Style', 'Chart options', 'tern_mean', 'Mark the mean composition', 'check', {'ternary'}, None),
    ('Style', 'Chart options', 'pca_loadings', 'Draw isotope arrows (loadings)', 'check', {'pca'}, None),
    ('Style', 'Chart options', 'edge_pos_color', 'Positive links', 'color', {'network'}, None),
    ('Style', 'Chart options', 'edge_neg_color', 'Negative links', 'color', {'network'}, None),
    ('Style', 'Chart options', 'log_color', 'Log colour scale', 'check', {'heatmap', 'hexbin'}, None),
    ('Style', 'Chart options', 'transpose', 'Swap rows and columns', 'check', {'heatmap'}, None),
    ('Style', 'Chart options', 'max_rows', 'Max particles shown', 'int', {'heatmap'}, (10, 1000000)),
    ('Style', 'Chart options', 'bin_mode', 'Bins set by', 'combo', {'histogram'},
     {'count': 'Number of bins', 'width': 'Bin width (decades on a log axis)'}),
    ('Style', 'Chart options', 'bins', 'Bins', 'int', {'histogram', 'density', 'line', 'hexbin', 'timeline'},
     (2, 500)),
    ('Style', 'Chart options', 'bin_width', 'Bin width', 'float', {'histogram'}, (0.001, 1e6, 0.05)),
    ('Style', 'Chart options', 'bar_values', 'Write values on the bars', 'check', {'histogram', 'bar'}, None),
    ('Style', 'Chart options', 'bar_swap', 'Isotopes on the axis, one bar per group', 'check', {'bar'}, None),
    ('Style', 'Chart options', 'sort_items', 'Order bars', 'combo', {'bar'}, BAR_SORTS),
    ('Style', 'Chart options', 'violin_style', 'Violin', 'combo', {'violin'},
     {'full': 'Full violin', 'half': 'Half violin + box (raincloud)'}),
    ('Style', 'Chart options', 'bandwidth', 'Smoothing (0 = auto)', 'float', {'violin'}, (0, 5, 0.05)),
    ('Style', 'Chart options', 'show_outliers', 'Show outliers', 'check', {'box'}, None),
    ('Style', 'Chart options', 'strip_values', 'Write the summary value', 'check', {'strip'}, None),
    ('Style', 'Chart options', 'pie_labels', 'Slice labels', 'combo', {'pie'}, PIE_LABELS),
    ('Style', 'Chart options', 'pie_label_pos', 'Labels', 'combo', {'pie'},
     {'inside': 'Inside the slices', 'outside': 'Outside, with lines'}),
    ('Style', 'Chart options', 'other_pct', 'Group slices below (%) as Others', 'float', {'pie'}, (0, 50, 0.5)),
    ('Style', 'Chart options', 'start_angle', 'Start angle (°)', 'float', {'pie'}, (0, 360, 15)),
    ('Style', 'Chart options', 'pie_explode', 'Gap between slices', 'float', {'pie'}, (0, 0.3, 0.02)),
    ('Style', 'Chart options', 'donut_text', 'Text in the centre', 'text', {'pie'}, '{n} = particle count'),
    ('Style', 'Chart options', 'strip_summary', 'Show', 'combo', {'strip'},
     {'mean_sd': 'Mean ± SD (geometric on a log axis)', 'gmean': 'Geometric mean × / ÷ GSD',
      'median_iqr': 'Median and IQR', 'mean_ci': 'Mean ± 95% CI', 'none': 'Dots only'}),
    ('Style', 'Chart options', 'jitter', 'Spread width', 'float', {'strip'}, (0.05, 0.48, 0.05)),
    ('Style', 'Chart options', 'sina', 'Spread by density (sina)', 'check', {'strip'}, None),
    ('Style', 'Chart options', 'overlap', 'Overlap', 'float', {'ridgeline'}, (0, 2.5, 0.1)),
    ('Style', 'Chart options', 'levels', 'Contour levels', 'int', {'contour'}, (2, 20)),
    ('Style', 'Chart options', 'filled', 'Filled contours', 'check', {'contour'}, None),
    ('Style', 'Chart options', 'radar_fill', 'Fill the shapes', 'check', {'radar'}, None),
    ('Style', 'Chart options', 'mark_stats', 'Mark', 'combo', {'histogram', 'ridgeline'}, MARKS),
    ('Style', 'Statistics and limits', 'stat_band', 'Shade', 'combo', MARKABLE, BANDS),
    ('Style', 'Statistics and limits', 'band_color', 'Shade colour', 'color', MARKABLE, None),
    ('Style', 'Statistics and limits', 'dl_value', 'Detection limit at', 'text', MARKABLE, 'optional'),
    ('Style', 'Statistics and limits', 'dl_label', 'Detection limit label', 'text', MARKABLE, 'DL: value'),
    ('Style', 'Statistics and limits', 'dl_color', 'Detection limit colour', 'color', MARKABLE, None),
    ('Style', 'Chart options', 'fit_dist', 'Fit a distribution', 'combo', {'histogram'},
     {'none': 'None', 'normal': 'Normal', 'lognormal': 'Log-normal'}),
    ('Style', 'Chart options', 'summary_box', 'Statistics box', 'check', SUMMARISED, None),
    ('Style', 'Chart options', 'summary_loc', 'Box position', 'combo', SUMMARISED,
     {'upper right': 'Upper right', 'upper left': 'Upper left', 'lower right': 'Lower right',
      'lower left': 'Lower left'}),
    ('Style', 'Chart options', 'hist_style', 'Bars', 'combo', {'histogram'},
     {'filled': 'Filled', 'step': 'Outline'}),
    ('Style', 'Chart options', 'density', 'Normalise (density)', 'check', {'histogram'}, None),
    ('Style', 'Chart options', 'kde', 'Smooth curve (KDE)', 'check', {'histogram'}, None),
    ('Style', 'Chart options', 'cumulative', 'Cumulative', 'check', {'histogram'}, None),
    ('Style', 'Chart options', 'band', 'Shaded band', 'combo', {'line'},
     {'sem': 'Standard error', 'sd': 'Standard deviation', 'iqr': 'Interquartile range', 'none': 'None'}),
    ('Style', 'Chart options', 'show_points', 'Show points', 'check', DIST | {'line', 'contour'}, None),
    ('Style', 'Chart options', 'notch', 'Notched boxes', 'check', {'box'}, None),
    ('Style', 'Chart options', 'show_mean', 'Mark the mean', 'check', DIST, None),
    ('Style', 'Chart options', 'error', 'Error bars', 'combo', {'bar'},
     {'sd': 'Standard deviation', 'sem': 'Standard error', 'ci95': '95% CI', 'none': 'None'}),
    ('Style', 'Chart options', 'horizontal', 'Horizontal', 'check', {'bar', 'combinations', 'composition'}, None),
    ('Style', 'Chart options', 'stacked', 'Stack the values', 'check', {'bar'}, None),
    ('Style', 'Chart options', 'donut', 'Donut', 'check', {'pie'}, None),
    ('Style', 'Background', 'panel_bg', 'Panel background', 'color', ALL - {'pairs'}, None),
    ('Axes', 'Labels', 'x_label', 'X label', 'text', XLINE | {'histogram', 'heatmap', 'combinations', 'composition', 'ridgeline'}, 'automatic'),
    ('Axes', 'Labels', 'y_label', 'Y label', 'text', PLOTS | {'heatmap', 'combinations', 'composition', 'parallel'}, 'automatic'),
    ('Axes', 'Labels', 'y2_label', 'Right Y label', 'text', {'scatter'}, 'automatic'),
    ('Axes', 'Labels', 'a_label', 'Top corner', 'text', {'ternary'}, 'automatic'),
    ('Axes', 'Labels', 'b_label', 'Left corner', 'text', {'ternary'}, 'automatic'),
    ('Axes', 'Labels', 'c_label', 'Right corner', 'text', {'ternary'}, 'automatic'),
    ('Axes', 'Labels', 'cbar_label', 'Colour bar label', 'text', {'scatter', 'density', 'hexbin'} | MATRIX, 'automatic'),
    ('Axes', 'Labels', 'styles_button', '', 'button', ALL, 'Text styles: bold, italic, size, colour…'),
    ('Axes', 'Labels', 'rename_button', '', 'button', RENAMEABLE, 'Rename isotopes / items…'),
    ('Axes', 'Scale', 'log_x', 'Log X', 'check', XLINE | {'histogram', 'ridgeline', 'ecdf'}, None),
    ('Axes', 'Scale', 'log_y', 'Log Y', 'check', PLOTS - {'ecdf'} | {'combinations'}, None),
    ('Axes', 'Scale', 'log_y2', 'Log right Y', 'check', {'scatter'}, None),
    ('Axes', 'Range', 'x_min', 'X from', 'text', XLINE | {'histogram'}, 'auto'),
    ('Axes', 'Range', 'x_max', 'X to', 'text', XLINE | {'histogram'}, 'auto'),
    ('Axes', 'Range', 'y_min', 'Y from', 'text', PLOTS, 'auto'),
    ('Axes', 'Range', 'y_max', 'Y to', 'text', PLOTS, 'auto'),
    ('Axes', 'Ticks and frame', 'frame', 'Frame', 'combo', PLOTS,
     {'open': 'Open (left + bottom)', 'box': 'Box (all sides)', 'none': 'None'}),
    ('Axes', 'Ticks and frame', 'tick_dir', 'Ticks', 'combo', PLOTS,
     {'out': 'Outside', 'in': 'Inside', 'inout': 'Crossing'}),
    ('Axes', 'Ticks and frame', 'minor_ticks', 'Minor ticks', 'check', PLOTS, None),
    ('Axes', 'Ticks and frame', 'sci_x', 'Scientific X', 'check', XLINE | {'histogram'}, None),
    ('Axes', 'Ticks and frame', 'sci_y', 'Scientific Y', 'check', PLOTS, None),
    ('Axes', 'Ticks and frame', 'xtick_rotation', 'Rotate X labels (°)', 'int',
     PLOTS | MATRIX | {'combinations', 'parallel'}, (-90, 90)),
    ('Axes', 'Ticks and frame', 'x_ticks', 'X ticks', 'text', TICKED, 'step (e.g. 50) or values (1, 10, 100)'),
    ('Axes', 'Ticks and frame', 'y_ticks', 'Y ticks', 'text', TICKED, 'step or values'),
    ('Axes', 'Ticks and frame', 'x_format', 'X numbers', 'combo', TICKED, TICK_FORMATS),
    ('Axes', 'Ticks and frame', 'y_format', 'Y numbers', 'combo', TICKED, TICK_FORMATS),
    ('Axes', 'Ticks and frame', 'invert_x', 'Reverse X', 'check', TICKED, None),
    ('Axes', 'Ticks and frame', 'invert_y', 'Reverse Y', 'check', TICKED, None),
    ('Axes', 'Ticks and frame', 'axis_color', 'Axis colour', 'color', TICKED, None),
    ('Axes', 'Grid', 'grid', 'Grid', 'check', PLOTS | {'ternary', 'combinations'}, None),
    ('Axes', 'Grid', 'grid_axis', 'Grid lines on', 'combo', TICKED,
     {'both': 'X and Y', 'x': 'X only', 'y': 'Y only'}),
    ('Axes', 'Grid', 'grid_minor', 'Minor grid', 'check', TICKED, None),
    ('Axes', 'Grid', 'grid_color', 'Grid colour', 'color', TICKED, None),
    ('Axes', 'Ticks and frame', 'aspect_equal', 'Equal X/Y scale', 'check', XY, None),
    ('Axes', 'Guide lines', 'hlines', 'Horizontal lines at', 'text', PLOTS, 'e.g. 1, 10'),
    ('Axes', 'Guide lines', 'vlines', 'Vertical lines at', 'text', XLINE | {'histogram'}, 'e.g. 100'),
    ('Axes', 'Guide lines', 'diagonal', 'y = x line', 'check', {'scatter'}, None),
    ('Axes', 'Legend', 'legend', 'Show legend', 'check', LEGENDED, None),
    ('Axes', 'Legend', 'legend_frame', 'Frame behind the legend', 'check', LEGENDED, None),
    ('Axes', 'Legend', 'legend_loc', 'Position', 'combo', LEGENDED, S.LEGEND_LOCATIONS),
    ('Axes', 'Legend', 'legend_cols', 'Columns', 'int', LEGENDED, (1, 8)),
    ('Axes', 'Legend', 'legend_title', 'Title', 'text', LEGENDED, 'optional'),
    ('Axes', 'Legend', 'legend_size', 'Text size', 'combo', LEGENDED, S.FONT_SIZES),
    ('Stats', 'Fit', 'show_fit', 'Fit line', 'check', {'scatter'}, None),
    ('Stats', 'Fit', 'fit_band', '95% confidence band', 'check', {'scatter'}, None),
    ('Stats', 'Fit', 'sd_band', 'Fit ± SD of the residuals', 'check', {'scatter'}, None),
    ('Stats', 'Fit', 'show_r', 'Show r and R²', 'check', {'scatter'}, None),
    ('Stats', 'Isotope ratios', 'poisson_band', 'Counting-statistics band (± kσ, 0 = off)', 'float',
     {'scatter'}, (0, 5, 0.5)),
    ('Stats', 'Isotope ratios', 'natural_line', 'Natural abundance ratio line', 'check', {'scatter'}, None),
    ('Stats', 'Isotope ratios', 'natural_color', 'Line colour', 'color', {'scatter'}, None),
    ('Axes', 'Zoom inset', 'inset_zoom', 'Zoom on', 'text', {'scatter'}, 'x from, x to, y from, y to'),
    ('Axes', 'Zoom inset', 'inset_loc', 'Inset position', 'combo', {'scatter'}, INSET_LOCS),
    ('Axes', 'Zoom inset', 'inset_size', 'Inset size', 'float', {'scatter'}, (0.15, 0.7, 0.05)),
    ('Stats', 'Compare groups', 'test', 'Test', 'combo', TESTABLE, E.STAT_TESTS),
    ('Stats', 'Compare groups', 'pairs', 'Pairs', 'combo', set(),
     {'all': 'Every pair', 'first': 'Each group vs the first'}),
    ('Stats', 'Compare groups', 'correction', 'Multiple comparisons', 'combo', set(), E.CORRECTIONS),
    ('Stats', 'Compare groups', 'p_format', 'Show p as', 'combo', set(),
     {'stars': 'Stars (*, **, ns)', 'p': 'Numbers (p = …)'}),
    ('Stats', 'Compare groups', 'hide_ns', 'Hide non-significant', 'check', set(), None),
    ('Stats', 'Compare groups', 'test_log', 'Test on log values', 'check', set(), None),
    ('Shapes', 'Grey areas, rectangles and lines', 'shapes', '', 'shapes', SHAPED, None),
    ('Notes', 'Text and arrows on this panel', 'annotations', '', 'annotations',
     ALL - {'text'}, None),
]
"""(tab, section, key, label, widget type, kinds, options) for every panel field."""

LABELS = {
    ('x', 'line'): 'X (binned)',
    ('y', 'line'): 'Y (blank = count)',
    ('value', 'bar'): 'Values (comma separated)',
    ('value', 'pie'): 'Values (comma separated)',
    ('value', 'timeline'): 'Value (optional)',
    ('isotopes', 'lollipop'): 'Isotopes (rows)',
}

TAB_HINTS = {
    'Shapes': 'Grey areas, rectangles and reference lines. Leave a bound empty to run to the edge '
              'of the plot. On the figure: Shift-drag shades an X range, Ctrl/⌘-drag a Y range.',
    'Stats': 'Results (test statistics, p-values, fits) are listed under the preview.',
    'Notes': 'x and y from 0 to 1 place text inside the panel; choose “Axis values” to use '
             'your data coordinates. Fill Arrow x/y to point an arrow at something.',
    'Groups': 'Rules colour particles by conditions you write, e.g. Fe/Cu < 0.5. '
              'Untick a group to hide it, type a legend name to rename it.',
}

SPECIAL_NAMES = ('total', 'n_elements', 'sample', 'class', 'time', 'per_ml', 'max_counts')
FUNCTION_SNIPPETS = ('log()', 'ln()', 'sqrt()', 'abs()', 'percentile(, 90)', 'median()', 'mean()',
                     'where(, , nan)')



class PanelEditor(QWidget):
    """Tabbed form editing the settings of the selected panel.

    Signals:
        changed(): any field of the panel changed.
        kind_changed(): the chart type (or pie mode) changed.
    """

    changed = Signal()
    kind_changed = Signal()
    styles_requested = Signal()
    rename_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.panel = None
        self.table = None
        self.palette = list(E.PALETTE)
        self._loading = False
        self._last_expr = None
        self.widgets: dict = {}
        self.rows: dict = {}
        self.sections: dict = {}
        self.tab_pages: dict = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        self.empty = QLabel('Select a panel on the page, or drag on the page to draw a new one.')
        self.empty.setWordWrap(True)
        self.empty.setObjectName('fbEmpty')
        root.addWidget(self.empty)
        self.error = QLabel('')
        self.error.setWordWrap(True)
        self.error.setObjectName('fbError')
        self.error.hide()
        root.addWidget(self.error)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(True)
        self.insert_btn = QToolButton()
        self.insert_btn.setText('Insert ▾')
        self.insert_btn.setToolTip('Insert an isotope, quantity, variable or function into the '
                                   'last expression box you used')
        self.insert_btn.setPopupMode(QToolButton.InstantPopup)
        self.insert_btn.setAutoRaise(True)
        self.insert_menu = QMenu(self.insert_btn)
        self.insert_btn.setMenu(self.insert_menu)
        self.tabs.setCornerWidget(self.insert_btn, Qt.TopRightCorner)
        root.addWidget(self.tabs, 1)
        for tab, section, key, label, kind, _kinds, opts in FIELDS:
            if tab not in self.tab_pages:
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setFrameShape(QFrame.NoFrame)
                page = QWidget()
                lay = QVBoxLayout(page)
                lay.setContentsMargins(2, 4, 2, 4)
                lay.setSpacing(4)
                if tab in TAB_HINTS:
                    hint = QLabel(TAB_HINTS[tab])
                    hint.setWordWrap(True)
                    hint.setObjectName('fbHint')
                    lay.addWidget(hint)
                scroll.setWidget(page)
                self.tabs.addTab(scroll, tab)
                self.tab_pages[tab] = (scroll, lay)
            if (tab, section) not in self.sections:
                box = QGroupBox(section)
                form = QFormLayout(box)
                form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
                form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
                form.setVerticalSpacing(4)
                form.setHorizontalSpacing(8)
                form.setContentsMargins(6, 4, 6, 4)
                self.sections[(tab, section)] = (box, form)
                self.tab_pages[tab][1].addWidget(box)
            box, form = self.sections[(tab, section)]
            w = self._make(key, kind, opts)
            self.widgets[key] = (kind, w)
            if kind in ('rules', 'series', 'annotations', 'shapes', 'groups', 'code', 'longtext', 'button'):
                form.addRow(w)
                self.rows[key] = (None, w)
            else:
                form.addRow(label, w)
                self.rows[key] = (form.labelForField(w), w)
        for _scroll, lay in self.tab_pages.values():
            lay.addStretch()
        self.tabs.hide()

    def _make(self, key, kind, opts):
        """Create the widget for one field and wire it to the panel."""
        if kind == 'combo':
            w = QComboBox()
            for k, label in opts.items():
                w.addItem(label, k)
            w.currentIndexChanged.connect(lambda _i, k=key, ww=w: self._set(k, ww.currentData()))
        elif kind in ('expr', 'mask'):
            w = ExpressionEdit()
            if opts:
                w.setPlaceholderText(opts)
            w.textEdited.connect(lambda t, k=key: self._set(k, t))
            w.focused.connect(self._remember_expr)
        elif kind == 'text':
            w = QLineEdit()
            if opts:
                w.setPlaceholderText(opts)
            w.textEdited.connect(lambda t, k=key: self._set(k, t))
        elif kind == 'check':
            w = QCheckBox()
            w.toggled.connect(lambda v, k=key: self._set(k, bool(v)))
        elif kind == 'float':
            w = QDoubleSpinBox()
            lo, hi, step = opts
            w.setRange(lo, hi)
            w.setSingleStep(step)
            w.setDecimals(2)
            w.setKeyboardTracking(False)
            w.valueChanged.connect(lambda v, k=key: self._set(k, float(v)))
        elif kind == 'int':
            w = QSpinBox()
            w.setRange(*opts)
            w.setKeyboardTracking(False)
            w.valueChanged.connect(lambda v, k=key: self._set(k, int(v)))
        elif kind == 'color':
            w = ColorButton()
            w.color_changed.connect(lambda c, k=key: self._set(k, c))
        elif kind == 'rules':
            w = RowTable(RULE_COLUMNS, '+ Add rule',
                         lambda i: {'name': f'Group {i + 1}', 'when': '',
                                    'color': self.palette[(i + 1) % len(self.palette)]})
            w.changed.connect(lambda ww=w: self._set('rules', ww.rows()))
        elif kind == 'series':
            w = RowTable(SERIES_COLUMNS, '+ Add series',
                         lambda i: {'label': '', 'x': (self.panel or {}).get('x', ''), 'y': '',
                                    'filter': '', 'style': 'points', 'marker': 'o', 'size': 14.0,
                                    'color': self.palette[(i + 2) % len(self.palette)]})
            w.changed.connect(lambda ww=w: self._set('series', ww.rows()))
        elif kind == 'shapes':
            w = RowTable(SHAPE_COLUMNS, '+ Add grey area or line',
                         lambda i: {'type': 'xband', 'color': '#9ca3af', 'alpha': 0.25,
                                    'hatch': '', 'style': '--', 'layer': 'back'})
            w.changed.connect(lambda ww=w: self._set('shapes', ww.rows()))
        elif kind == 'annotations':
            w = RowTable(ANNOTATION_COLUMNS, '+ Add text',
                         lambda i: {'text': 'Note', 'x': '0.05', 'y': f'{0.92 - 0.08 * i:.2f}',
                                    'coords': 'axes', 'size': 10.0, 'color': '#222222'})
            w.changed.connect(lambda ww=w: self._set('annotations', ww.rows()))
        elif kind == 'groups':
            w = GroupsTable()
            w.changed.connect(self._groups_changed)
        elif kind == 'button':
            w = QPushButton(opts)
            w.clicked.connect(self.styles_requested if key == 'styles_button' else self.rename_requested)
        elif kind == 'longtext':
            w = QPlainTextEdit()
            w.setMinimumHeight(120)
            w.setPlaceholderText('Caption, method note, sample description…')
            w.textChanged.connect(lambda ww=w: self._set('text', ww.toPlainText()))
        else:
            w = QPlainTextEdit()
            w.setFont(mono_font())
            w.setMinimumHeight(260)
            w.setPlaceholderText(
                'Variables: ax, fig, df (one row per particle), labels, groups, '
                'group_colors, col("Fe/Cu"), color(i), np, pd, stats, report("text")\n\n'
                + E.CODE_EXAMPLE)
            w.textChanged.connect(lambda ww=w: self._set('code', ww.toPlainText()))
        return w

    def _remember_expr(self, w):
        self._last_expr = w

    def _build_insert_menu(self, table):
        m = self.insert_menu
        m.clear()
        if table is None:
            return
        aliases = table.symbol_aliases()
        iso_names = list(aliases) or list(table.labels)
        iso = m.addMenu('Isotope')
        for name in iso_names:
            iso.addAction(name, lambda n=name: self._insert_chip(n))
        if aliases:
            full = m.addMenu('Isotope (full label)')
            for lab in table.labels:
                full.addAction(lab, lambda n=lab: self._insert_chip(n))
        for prefix, (_key, human, unit) in QUANTITY_PREFIXES.items():
            if prefix == table.default_prefix:
                continue
            sub = m.addMenu(f'{(human or prefix).capitalize()} ({unit})')
            for name in iso_names:
                sub.addAction(f'{prefix}:{name}', lambda n=f'{prefix}:{name}': self._insert_chip(n))
        if table.variables:
            var = m.addMenu('My variables')
            for name in table.variables:
                var.addAction(name, lambda n=name: self._insert_chip(n))
        special = m.addMenu('Built-in values')
        for name in SPECIAL_NAMES:
            special.addAction(name, lambda n=name: self._insert_chip(n))
        funcs = m.addMenu('Functions')
        for name in FUNCTION_SNIPPETS:
            funcs.addAction(name, lambda n=name: self._insert_chip(n))

    def _insert_chip(self, text):
        target = self._last_expr
        if target is None or not target.isVisible():
            for key in ('x', 'value', 'a', 'filter'):
                cand = self.widgets[key][1]
                if cand.isVisible():
                    target = cand
                    break
        if target is not None:
            target.insert_text(text)

    def set_table(self, table, palette=None):
        """Give the editor the particle table for completion, chips and checks."""
        self.table = table
        if palette:
            self.palette = list(palette)
        names = table.names() if table is not None else []
        hints = names + ['log', 'ln', 'sqrt', 'abs', 'exp', 'min', 'max', 'where',
                         'mean', 'median', 'std', 'percentile']
        for _key, (kind, w) in self.widgets.items():
            if isinstance(w, ExpressionEdit):
                w.set_names(hints)
            if isinstance(w, RowTable):
                w.set_table_source(table)
        self._build_insert_menu(table)
        self._check_expressions()
        self.refresh_groups()

    def set_panel(self, panel):
        """Show ``panel`` (a dict, edited in place) or nothing when None."""
        self.panel = panel
        self.empty.setVisible(panel is None)
        self.tabs.setVisible(panel is not None)
        if panel is None:
            self.error.hide()
            return
        self._loading = True
        for key, (kind, w) in self.widgets.items():
            v = panel.get(key, E.PANEL_DEFAULTS.get(key))
            if kind == 'combo':
                w.setCurrentIndex(max(0, w.findData(v)))
            elif kind in ('text', 'expr', 'mask'):
                w.setText('' if v is None else str(v))
            elif kind == 'check':
                w.setChecked(bool(v))
            elif kind == 'float':
                w.setValue(float(v or 0))
            elif kind == 'int':
                w.setValue(int(v or 0))
            elif kind == 'color':
                w.set_color(v)
            elif kind in ('rules', 'series', 'annotations', 'shapes'):
                w.set_rows(v)
            elif kind in ('groups', 'button'):
                pass
            else:
                if w.toPlainText() != (v or ''):
                    w.setPlainText(v or '')
        self._loading = False
        self._update_visibility()
        self._check_expressions()
        self.refresh_groups()

    def refresh_groups(self):
        """Rebuild the groups table from the current data and grouping."""
        if self.panel is None or self.table is None:
            return
        w = self.widgets['groups'][1]
        if not w.isVisibleTo(self) and self.panel.get('group_by', 'none') == 'none':
            return
        try:
            probe = dict(self.panel)
            probe['_palette'] = self.palette
            groups = E.candidate_groups(probe, self.table) if len(self.table) else []
        except Exception:
            groups = []
        w.set_groups(self.panel, groups)

    def show_error(self, message):
        """Show the last render error of this panel (or hide it)."""
        self.error.setText(f'⚠ {message}' if message else '')
        self.error.setVisible(bool(message) and self.panel is not None)

    def _groups_changed(self):
        self.refresh_groups()
        self.changed.emit()

    def _set(self, key, value):
        if self._loading or self.panel is None:
            return
        self.panel[key] = value
        if key in ('kind', 'group_by', 'test', 'pie_mode', 'rules', 'y', 'heat_rows', 'show_fit', 'trend',
                   'share_mode', 'facet', 'bin_mode', 'donut', 'color_by', 'agg', 'stat_band',
                   'natural_line', 'dl_value'):
            if key == 'kind' and value == 'code' and not (self.panel.get('code') or '').strip():
                self.panel['code'] = E.CODE_EXAMPLE
                self._loading = True
                self.widgets['code'][1].setPlainText(E.CODE_EXAMPLE)
                self._loading = False
            self._update_visibility()
            if key in ('kind', 'pie_mode'):
                self.kind_changed.emit()
            if key in ('group_by', 'rules', 'kind'):
                self.refresh_groups()
        if key == 'filter':
            self.refresh_groups()
        if self.widgets.get(key, (None,))[0] in ('expr', 'mask'):
            self._check_expressions()
        self.changed.emit()

    @staticmethod
    def _kinds(key):
        for _t, _s, k, _l, _w, kinds, _o in FIELDS:
            if k == key:
                return kinds
        return set()

    def _visible(self, key, kinds):
        """Whether ``key`` should show for the current panel state."""
        p = self.panel
        kind = p.get('kind')
        group = p.get('group_by', 'none')
        grouped = kind in GROUPING
        if key in ('rules', 'show_other', 'other_label'):
            return group == 'rules' and grouped
        if key == 'groups':
            return group != 'none' and grouped
        if key == 'test_log':
            return kind in TESTABLE and p.get('test', 'none') != 'none'
        if key in ('pairs', 'correction', 'p_format', 'hide_ns'):
            if kind not in TESTABLE or p.get('test') not in E.PAIRWISE_TESTS:
                return False
            return not (key in ('p_format', 'hide_ns') and kind == 'histogram')
        if key == 'color':
            return kind in kinds and (group == 'none' or not grouped)
        if key == 'value' and kind == 'pie':
            return p.get('pie_mode') == 'values'
        if kind == 'pie' and key in ('isotopes', 'top_n'):
            mode = p.get('pie_mode', 'groups')
            return mode in ('detect', 'combinations', 'single_multi') and (key == 'isotopes' or mode == 'combinations')
        if key == 'per_ml':
            if self.table is None or not self.table.has_per_ml():
                return False
            if kind == 'bar':
                return p.get('agg') in ('count', 'detect')
            if kind == 'pie':
                return p.get('pie_mode', 'groups') != 'values'
            return kind in kinds
        if key in ('facet_cols', 'facet_share'):
            return kind in kinds and p.get('facet') == 'groups'
        if key == 'facet':
            return kind in kinds and group != 'none'
        if key in ('bins', 'bin_width') and kind == 'histogram':
            return (p.get('bin_mode') == 'width') == (key == 'bin_width')
        if key == 'donut_text':
            return kind == 'pie' and bool(p.get('donut'))
        if key in ('sd_band',):
            return kind == 'scatter' and bool(p.get('show_fit'))
        if key == 'natural_color':
            return kind == 'scatter' and bool(p.get('natural_line'))
        if key == 'band_color':
            return kind in kinds and p.get('stat_band', 'none') != 'none'
        if key in ('dl_label', 'dl_color'):
            return kind in kinds and bool(str(p.get('dl_value') or '').strip())
        if key == 'heat_sort':
            return kind == 'heatmap' and p.get('heat_rows') == 'combinations'
        if key == 'heat_spread':
            return kind == 'heatmap' and p.get('heat_rows') != 'particles'
        if key in ('c_min', 'c_max') and kind in ('scatter', 'ternary'):
            return bool((p.get('color_by') or '').strip())
        if key == 'agg' and kind == 'line':
            return bool((p.get('y') or '').strip())
        if key.startswith('cbar_') and key != 'cbar_label' and kind == 'scatter':
            return bool((p.get('color_by') or '').strip())
        if kind in SHARES and key in ('isotopes', 'top_n', 'combo_filter'):
            return p.get('share_mode') == 'combinations'
        if key == 'trend_bins':
            return kind == 'scatter' and p.get('trend', 'none') != 'none'
        if key == 'fit_band':
            return kind == 'scatter' and bool(p.get('show_fit'))
        if key == 'max_rows':
            return kind == 'heatmap' and p.get('heat_rows') == 'particles'
        if key == 'top_n' and kind == 'heatmap':
            return p.get('heat_rows') == 'combinations'
        if key == 'heat_value':
            return kind == 'heatmap' and p.get('heat_rows') != 'particles'
        return kind in kinds

    def _update_visibility(self):
        if self.panel is None:
            return
        kind = self.panel.get('kind')
        shown = {name: False for name in self.sections}
        for tab, section, key, label, _t, kinds, _o in FIELDS:
            vis = self._visible(key, kinds)
            lab, w = self.rows[key]
            if lab is not None:
                lab.setVisible(vis)
                if isinstance(lab, QLabel):
                    lab.setText(LABELS.get((key, kind), label))
            w.setVisible(vis)
            shown[(tab, section)] = shown[(tab, section)] or vis
        tab_any = {}
        for (tab, section), (box, _form) in self.sections.items():
            box.setVisible(shown[(tab, section)])
            tab_any[tab] = tab_any.get(tab, False) or shown[(tab, section)]
        for i in range(self.tabs.count()):
            name = self.tabs.tabText(i)
            self.tabs.setTabVisible(i, tab_any.get(name, False))

    def _check_expressions(self):
        """Mark expression fields that do not evaluate on the current data."""
        if self.panel is None:
            return
        for key, (kind, w) in self.widgets.items():
            if kind not in ('expr', 'mask'):
                continue
            text = w.text().strip()
            msg = None
            if text and self.table is not None and len(self.table):
                tbl = self.table.view(self.panel.get('data_type'))
                if key == 'isotopes' or (key == 'value' and self.panel.get('kind') in ('bar', 'pie')):
                    for part in split_list(text):
                        msg = validate(part, tbl) or msg
                else:
                    msg = validate(text, tbl)
            w.mark(msg)
