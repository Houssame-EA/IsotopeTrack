"""Everything clustering, in one package.

Grouped here so the whole clustering feature — the dialog, the parameter
sweep, the animated teaching view and its browser assets — can be reasoned
about and changed in one place.

Modules
-------
``dialog``
    :class:`ClusteringDisplayDialog` / :class:`ClusteringPlotNode` — the main
    clustering dialog: evaluate K, cluster, strips, heatmaps and exports.
``tools``
    "Everything everywhere all at once" — the pipeline sweep that scores many
    preprocessing/algorithm combinations, with or without ground truth.
``live``
    The Qt tab hosting the *how it works* view. It reuses ``dialog``'s fit
    whenever one applies, so a clustering is never computed twice.
``live_engine``
    Preprocessing, validity metrics and the algorithm parameter schema.
``detail``
    Turns a finished fit into the per-algorithm *detail view* (dendrogram,
    reachability plot, U-matrix, objective curves …) and worked example.
``live_qt``
    The live tab's Qt widgets — scatter, legends, control panel, detail plots,
    worked example and export.
``palette``
    Per-cluster colour overrides shared by the dialog and the live tab.

The "① Evaluate K" sweep and its matplotlib panel live in ``dialog`` itself
(``_run_evaluation`` / ``_EvalWorker`` / ``_build_eval_tab``), not in a
separate module.

Nothing is imported eagerly: the dialog pulls in the heavier pieces only when
the corresponding tab is opened, so importing this package stays cheap.
"""
