"""Qt widgets for the Cluster Lab view.

These draw the clustering the Clustering Analysis dialog computed, over the
particle data it is working with, together with the detail figure and worked
example :mod:`results.cluster.detail` derives from that same fit.

Module map
----------
``state`` Palette, marker geometry, element-label parsing, the view state.
``viewmath`` Projection, rotation, tick selection and easing.
``scatter`` The main 2-D/3-D figure: points, centroids, axes, biplot, SOM.
``insets`` The four detail plots: curve, bars, dendrogram, grid.
``equation`` The worked example, typeset with LaTeX.
``legend`` Cluster and sample legends, colour overrides.
``floatbox`` Draggable, resizable panels that float over the plot.
``panel`` Settings dialog, algorithm parameter widgets, context menu.
``export`` PNG export at the chosen scale.

The result arrives on a worker thread and is handed to
:class:`~results.cluster.live_qt.view.LiveView` as NumPy arrays, which go
straight into the plot items.
"""

from __future__ import annotations

__all__ = ["state", "viewmath"]
