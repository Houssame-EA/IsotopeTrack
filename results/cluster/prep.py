"""Shared preprocessing rules for every clustering entry point.

Keeps the ② Cluster tab, the ④ How it works view, the live panel and the sweep
tool agreeing on how the scaled matrix is reduced before clustering.

Every reduction parameter the app exposes is declared once here, in
:data:`DR_PARAM_SPECS`, and applied once here, in :func:`apply_reduction`. That
matters more than it looks: before this module owned them, the sweep, the
clustering matrix and the live projection each built their own t-SNE with their
own hard-coded perplexity, so a pipeline the sweep ranked first could not be
reproduced by the tab the user then clicked into.

scikit-learn and umap are imported lazily inside the functions that need them,
so importing this module stays cheap for callers that only want
:func:`reduction_components`.
"""

from __future__ import annotations

import logging

_log = logging.getLogger("IsotopeTrack.results.cluster.prep")

#: Dimensions kept for t-SNE and for the live view's display projections.
EMBED_DIMS = 3

#: The ``n_components`` value meaning "keep everything" — the default, and the
#: only value the main clustering pipeline used before it was configurable.
KEEP_ALL = 'all'

#: Distance metrics offered to the neighbour-graph reductions. Deliberately
#: short: these are the ones both t-SNE and UMAP accept without an optional
#: dependency.
DR_METRIC_OPTIONS = ['euclidean', 'manhattan', 'cosine', 'chebyshev',
                     'correlation']

#: Every tunable parameter of every reduction, with the value ranges the UI
#: builds its controls from. ``default`` is a *list* because the sweep tool
#: expands it into a grid; every other caller takes the first entry.
DR_PARAM_SPECS = {
    'None': {'params': {}},
    'PCA': {
        'params': {
            'n_components': {'kind': 'choice', 'label': 'n_components',
                             'options': [KEEP_ALL, '2', '3', '5', '10',
                                         '0.95', '0.99'],
                             'default': [KEEP_ALL]},
            'whiten':       {'kind': 'choice', 'label': 'whiten',
                             'options': ['off', 'on'], 'default': ['off']},
            'svd_solver':   {'kind': 'choice', 'label': 'svd_solver',
                             'options': ['auto', 'full', 'covariance_eigh',
                                         'randomized', 'arpack'],
                             'default': ['auto']},
            'random_state': {'kind': 'int_range', 'label': 'random_state',
                             'default': [42], 'min': 0, 'max': 99999},
        },
    },
    't-SNE': {
        'params': {
            'n_components':       {'kind': 'int_range', 'label': 'n_components',
                                   'default': [3], 'min': 1, 'max': 3},
            'perplexity':         {'kind': 'float_range', 'label': 'perplexity',
                                   'default': [30.0], 'min': 2.0, 'max': 500.0,
                                   'decimals': 1},
            'early_exaggeration': {'kind': 'float_range',
                                   'label': 'early_exaggeration',
                                   'default': [12.0], 'min': 1.0, 'max': 100.0,
                                   'decimals': 1},
            'learning_rate':      {'kind': 'choice', 'label': 'learning_rate',
                                   'options': ['auto', '10', '50', '200',
                                               '500', '1000'],
                                   'default': ['auto']},
            'max_iter':           {'kind': 'int_range', 'label': 'max_iter',
                                   'default': [1000], 'min': 250, 'max': 10000},
            'init':               {'kind': 'choice', 'label': 'init',
                                   'options': ['pca', 'random'],
                                   'default': ['pca']},
            'metric':             {'kind': 'choice', 'label': 'metric',
                                   'options': DR_METRIC_OPTIONS,
                                   'default': ['euclidean']},
            'random_state':       {'kind': 'int_range', 'label': 'random_state',
                                   'default': [42], 'min': 0, 'max': 99999},
        },
    },
    'UMAP': {
        'params': {
            'n_components': {'kind': 'choice', 'label': 'n_components',
                             'options': [KEEP_ALL, '2', '3', '5', '10'],
                             'default': [KEEP_ALL]},
            'n_neighbors':  {'kind': 'int_range', 'label': 'n_neighbors',
                             'default': [15], 'min': 2, 'max': 200},
            'min_dist':     {'kind': 'float_range', 'label': 'min_dist',
                             'default': [0.0], 'min': 0.0, 'max': 0.99,
                             'decimals': 2},
            'spread':       {'kind': 'float_range', 'label': 'spread',
                             'default': [1.0], 'min': 0.1, 'max': 10.0,
                             'decimals': 2},
            'metric':       {'kind': 'choice', 'label': 'metric',
                             'options': DR_METRIC_OPTIONS,
                             'default': ['euclidean']},
            'random_state': {'kind': 'int_range', 'label': 'random_state',
                             'default': [42], 'min': 0, 'max': 99999},
        },
    },
}

def dr_defaults(dim_reduction):
    """Return ``{param: default}`` for one reduction.

    Args:
        dim_reduction (str): A key of :data:`DR_PARAM_SPECS`.

    Returns:
        dict: The first default of every parameter, or ``{}`` when the
        reduction has none.
    """
    spec = DR_PARAM_SPECS.get(dim_reduction, {}).get('params', {})
    return {k: (v.get('default') or [None])[0] for k, v in spec.items()}


def dr_params_str(dim_reduction, params):
    """Return a compact human-readable parameter string for a reduction.

    Args:
        dim_reduction (str): A key of :data:`DR_PARAM_SPECS`.
        params (dict or None): The parameters in use.

    Returns:
        str: ``'perplexity=50, init=pca'``-style text, or ``''``.
    """
    if not params:
        return ''
    order = list(DR_PARAM_SPECS.get(dim_reduction, {}).get('params', {}).keys())
    return ', '.join(f"{k}={params[k]}" for k in order if k in params)


def non_default_dr_params(dim_reduction, params):
    """Return only the parameters that differ from the reduction's defaults.

    Used wherever a caveat is worth showing but noise is not: a pipeline left
    entirely at its defaults behaves exactly as it always has, and saying so
    would be clutter.

    Args:
        dim_reduction (str): A key of :data:`DR_PARAM_SPECS`.
        params (dict or None): The parameters in use.

    Returns:
        dict: ``{param: value}`` for each parameter away from its default.
    """
    defaults = dr_defaults(dim_reduction)
    out = {}
    for k, v in (params or {}).items():
        if k in defaults and str(v) != str(defaults[k]):
            out[k] = v
    return out


def reduction_components(dim_reduction, n_features):
    """Number of components to keep for ``dim_reduction`` by default.

    PCA and UMAP keep **all** of them. That is deliberate: PCA with a full
    component set is an orthonormal rotation, so Euclidean distances — and
    therefore any K-Means, Ward or DBSCAN result computed from them — are
    identical to clustering the scaled element matrix directly. The user gets
    principal components to plot against without the clustering silently
    throwing away the variance that the discarded components carried.

    t-SNE stays at :data:`EMBED_DIMS`: its Barnes-Hut solver is undefined
    above three components and the exact solver is quadratic in time and
    memory.

    This remains the default everywhere. Choosing a small number is the one way
    to lose information here, and it usually loses the rare particle types that
    matter most — which is why ``n_components`` defaults to :data:`KEEP_ALL` in
    :data:`DR_PARAM_SPECS` and carries that warning wherever it is exposed.

    Args:
        dim_reduction (str): 'PCA', 't-SNE', 'UMAP' or 'None'.
        n_features (int): Columns available in the scaled matrix.

    Returns:
        int or None: Components to request, or None when no reduction applies.
    """
    n_features = max(1, int(n_features))
    if dim_reduction in ('PCA', 'UMAP'):
        return n_features
    if dim_reduction == 't-SNE':
        return min(EMBED_DIMS, n_features)
    return None


def supported_kwargs(cls, kwargs):
    """Drop keyword arguments the estimator does not accept.

    scikit-learn renames parameters between releases — ``n_iter`` became
    ``max_iter`` on :class:`~sklearn.manifold.TSNE`, and ``covariance_eigh``
    only exists as a PCA solver from 1.5 — and umap is an optional dependency
    whose version we do not control. Filtering by the constructor's real
    signature means an unsupported knob is quietly ignored on an older install
    instead of raising ``TypeError`` and taking the whole run down with it.

    Args:
        cls (type): The estimator class.
        kwargs (dict): Candidate keyword arguments.

    Returns:
        dict: The subset ``cls.__init__`` accepts.
    """
    try:
        import inspect
        sig = inspect.signature(cls.__init__)
    except (TypeError, ValueError):
        _log.debug("Handled exception in supported_kwargs")
        return dict(kwargs)
    if any(p.kind is p.VAR_KEYWORD for p in sig.parameters.values()):
        return dict(kwargs)
    return {k: v for k, v in kwargs.items() if k in sig.parameters}


def n_components_value(raw, dim_reduction, n_features, n_samples):
    """Resolve an ``n_components`` selection to what the estimator should get.

    :data:`KEEP_ALL` defers to :func:`reduction_components`, which is what keeps
    PCA a plain rotation and UMAP information-preserving. A fractional value
    passes through to PCA untouched, where scikit-learn reads it as a variance
    ratio. Anything else is clamped to what the data can actually supply.

    Args:
        raw: The selected value (:data:`KEEP_ALL`, an int, or a float < 1).
        dim_reduction (str): Reduction key.
        n_features (int): Columns in the scaled matrix.
        n_samples (int): Rows in the scaled matrix.

    Returns:
        int | float | None: The value to hand the estimator.
    """
    default = reduction_components(dim_reduction, n_features)
    if raw is None or str(raw).strip().lower() in ('', KEEP_ALL, 'none'):
        return None if default is None else min(default, max(1, n_samples))
    try:
        val = float(raw)
    except (TypeError, ValueError):
        _log.debug("Handled exception in n_components_value")
        return default
    if 0 < val < 1 and dim_reduction == 'PCA':
        return val
    val = int(round(val))
    ceiling = max(1, min(n_features, n_samples))
    if dim_reduction == 't-SNE':
        ceiling = min(ceiling, EMBED_DIMS)
    return max(1, min(val, ceiling))


def learning_rate_value(raw):
    """Resolve a t-SNE learning rate, which may be the string ``'auto'``.

    Args:
        raw: The selected value.

    Returns:
        str | float: ``'auto'`` or a float.
    """
    if raw is None or str(raw).strip().lower() in ('', 'auto'):
        return 'auto'
    try:
        return float(raw)
    except (TypeError, ValueError):
        _log.debug("Handled exception in learning_rate_value")
        return 'auto'


def reduction_kwargs(dim_reduction, params, n_samples, n_features,
                     n_components=None, default_random_state=42):
    """Build the estimator keyword arguments for one reduction.

    Every value is clamped to what the data can support before it reaches the
    estimator: t-SNE requires ``perplexity < n_samples`` and UMAP requires
    ``n_neighbors <= n_samples - 1``, and violating either raises rather than
    degrading gracefully. Clamping keeps one badly-sized setting from voiding a
    whole run — a perplexity that only makes sense on a bigger dataset should
    not be fatal on a small one.

    The returned dict is *not* yet filtered against the estimator signature;
    pass it through :func:`supported_kwargs` at the call site, which is where
    the estimator class is known.

    The per-reduction rules applied here:

    * t-SNE's perplexity is held below the sample count, at the commonly cited
      safe ceiling of ``(n - 1) / 3``, which is what Barnes-Hut requires.
    * ``max_iter`` is emitted under both its names, since scikit-learn renamed
      it from ``n_iter`` in 1.5; :func:`supported_kwargs` keeps whichever
      spelling the installed version understands.
    * A ``'pca'`` init is downgraded to ``'random'`` for a non-Euclidean
      metric, a PCA init being meaningful only in the metric it was computed
      in.
    * UMAP's ``min_dist`` is held at or below ``spread``, which UMAP requires
      and otherwise errors out on.

    Args:
        dim_reduction (str): Reduction key.
        params (dict or None): Parameters; None means spec defaults.
        n_samples (int): Rows the estimator will be fitted on.
        n_features (int): Columns in the matrix.
        n_components (int or None): Overrides the resolved component count.
            The live panel passes 2 or 3, since its output must be drawable.
        default_random_state (int): Seed used when ``params`` names none.

    Returns:
        dict: Keyword arguments for the estimator.
    """
    params = dict(params or {})
    seed = params.get('random_state', default_random_state)
    try:
        seed = int(seed)
    except (TypeError, ValueError):
        seed = default_random_state

    if n_components is None:
        nc = n_components_value(params.get('n_components'), dim_reduction,
                                n_features, n_samples)
    else:
        nc = int(n_components)

    if dim_reduction == 'PCA':
        return {'n_components': nc,
                'whiten': str(params.get('whiten', 'off')).lower() == 'on',
                'svd_solver': params.get('svd_solver', 'auto'),
                'random_state': seed}

    if dim_reduction == 't-SNE':
        perp = float(params.get('perplexity', 30.0) or 30.0)
        perp = max(1.0, min(perp, max(1.0, (n_samples - 1) / 3.0)))
        kw = {'n_components': nc or min(EMBED_DIMS, n_features),
              'perplexity': perp,
              'early_exaggeration': float(
                  params.get('early_exaggeration', 12.0) or 12.0),
              'learning_rate': learning_rate_value(params.get('learning_rate')),
              'init': params.get('init', 'pca'),
              'metric': params.get('metric', 'euclidean'),
              'random_state': seed}
        n_iter = params.get('max_iter')
        if n_iter:
            kw['max_iter'] = int(n_iter)
            kw['n_iter'] = int(n_iter)
        if kw['init'] == 'pca' and str(kw['metric']) != 'euclidean':
            kw['init'] = 'random'
        return kw

    if dim_reduction == 'UMAP':
        nn = int(params.get('n_neighbors', 15) or 15)
        nn = max(2, min(nn, max(2, n_samples - 1)))
        kw = {'n_components': nc or n_features,
              'n_neighbors': nn,
              'min_dist': float(params.get('min_dist', 0.0) or 0.0),
              'spread': float(params.get('spread', 1.0) or 1.0),
              'metric': params.get('metric', 'euclidean'),
              'random_state': seed}
        if kw['min_dist'] > kw['spread']:
            kw['min_dist'] = kw['spread']
        return kw

    return {}


def apply_reduction(dim_reduction, m, params=None, default_random_state=42):
    """Reduce ``m`` with ``dim_reduction`` under ``params``.

    The single place the clustering matrix is reduced, shared by the ② Cluster
    tab and the sweep tool so a pipeline the sweep ranks can be reproduced by
    the tab.

    A PCA whose solver rejects the requested component count is retried with
    ``svd_solver='auto'`` rather than failing: ``'arpack'`` refuses
    ``n_components == n_features``, and ``'covariance_eigh'`` does not exist
    before scikit-learn 1.5.

    Args:
        dim_reduction (str): A reduction key, or ``'None'``.
        m (np.ndarray): The scaled matrix.
        params (dict or None): Reduction parameters; None means spec defaults.
        default_random_state (int): Seed used when ``params`` names none.

    Returns:
        np.ndarray: The reduced matrix, or ``m`` when no reduction applies.
    """
    if m is None or getattr(m, 'ndim', 0) != 2 or m.shape[1] < 2:
        return m
    n_samples, n_features = m.shape
    kw = reduction_kwargs(dim_reduction, params, n_samples, n_features,
                          default_random_state=default_random_state)

    if dim_reduction == 'PCA':
        from sklearn.decomposition import PCA
        try:
            return PCA(**supported_kwargs(PCA, kw)).fit_transform(m)
        except Exception:
            _log.exception("PCA fell back to the default solver")
            kw['svd_solver'] = 'auto'
            return PCA(**supported_kwargs(PCA, kw)).fit_transform(m)

    if dim_reduction == 't-SNE':
        from sklearn.manifold import TSNE
        return TSNE(**supported_kwargs(TSNE, kw)).fit_transform(m)

    if dim_reduction == 'UMAP':
        try:
            from umap import UMAP
        except ImportError:
            _log.debug("UMAP requested but umap-learn is not installed")
            return m
        from utils.numba_guard import numba_serial
        with numba_serial("UMAP (cluster reduction)"):
            return UMAP(**supported_kwargs(UMAP, kw)).fit_transform(m)

    return m
