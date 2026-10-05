"""Figure Builder: design any multi-panel figure from canvas particle data.

Draw panels on a page, choose a chart type for each, describe axes with
expressions (``Fe``, ``Fe/Cu``, ``mass:Ag``), colour particles by your own
rules, add a right-hand axis or statistics, and export the result.
"""

from results.figure_builder.dialog import FigureBuilderDialog, FigureBuilderNode

__all__ = ['FigureBuilderDialog', 'FigureBuilderNode']
