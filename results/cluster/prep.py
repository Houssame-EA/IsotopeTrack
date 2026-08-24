"""Shared preprocessing rules for every clustering entry point.

Keeps the ② Cluster tab, the ④ How it works view and the sweep tool agreeing on
how the scaled matrix is reduced before clustering.
"""

from __future__ import annotations

#: Dimensions kept for the embedding methods. t-SNE and UMAP are visualisation
#: embeddings — they have no notion of "all components" and t-SNE's exact
EMBED_DIMS = 3


def reduction_components(dim_reduction, n_features):
    """Number of components to keep for ``dim_reduction``.

    PCA keeps **all** of them. That is deliberate: PCA with a full component
    set is an orthonormal rotation, so Euclidean distances — and therefore any
    K-Means, Ward or DBSCAN result computed from them — are identical to
    clustering the scaled element matrix directly. The user gets principal
    components to plot against without the clustering silently throwing away
    the variance that the discarded components carried.

    That is why there is no "Components" setting: choosing a small number was
    the only way to lose information here, and it usually lost the rare
    particle types that matter most.

    Args:
        dim_reduction (str): 'PCA', 't-SNE', 'UMAP' or 'None'.
        n_features (int): Columns available in the scaled matrix.

    Returns:
        int or None: Components to request, or None when no reduction applies.
    """
    n_features = max(1, int(n_features))
    if dim_reduction == 'PCA':
        return n_features
    if dim_reduction in ('t-SNE', 'UMAP'):
        return min(EMBED_DIMS, n_features)
    return None
