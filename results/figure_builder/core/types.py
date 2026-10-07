"""Particle types defined by composition, shared by Insights and the Figure Builder.

A type is a centre in centred-log-ratio (CLR) space plus a radius. A
particle belongs to the nearest type whose radius it falls within, using
only the particle's own element amounts, so the same particle always gets
the same type, in whatever figure or sample it appears.

The CLR follows Aitchison (1986). Zeros, which are non-detections, are
replaced multiplicatively with a fixed fraction of a per-element floor
(Martín-Fernández et al. 2003, via
:func:`results.compositional.multiplicative_replacement`). The floor is
stored with the types rather than recomputed from each data set, which keeps
the assignment identical everywhere.

A type definition is a dict::

    {"prefix": "mass", "elements": ["48Ti", "93Nb", ...],
     "floor": [0.01, 0.002, ...], "min_elements": 2,
     "types": [{"name": "Ti–Nb", "color": "#3B82F6",
                "centroid": [...], "radius": 1.8}, ...]}
"""

from __future__ import annotations

import numpy as np


def clr_rows(matrix: np.ndarray, floor) -> np.ndarray:
    """CLR coordinates of each row after multiplicative zero replacement.

    Args:
        matrix: Non-negative amounts, one row per particle.
        floor: Per-column detection floor; zeros become 0.65 × floor.

    Returns:
        The CLR matrix, same shape as *matrix*.
    """
    from results.compositional import multiplicative_replacement
    X = multiplicative_replacement(np.asarray(matrix, dtype=float), threshold=np.asarray(floor, dtype=float))
    logs = np.log(X)
    return logs - logs.mean(axis=1, keepdims=True)


def amounts(table, definition: dict) -> np.ndarray:
    """The type definition's element amounts for every particle of *table*."""
    from results.figure_builder.core.expressions import evaluate
    prefix = definition.get('prefix') or 'mass'
    cols = [np.clip(np.nan_to_num(evaluate(f'{prefix}:{label}', table), nan=0.0), 0, None)
            for label in definition.get('elements') or []]
    return np.column_stack(cols) if cols else np.zeros((len(table), 0))


def assign(matrix: np.ndarray, definition: dict) -> np.ndarray:
    """Index of each row's type, or -1 when it has none.

    A row gets no type when fewer than ``min_elements`` of the elements were
    detected in it, or when it lies outside the radius of every type.

    Args:
        matrix: Amounts in the definition's element order.
        definition: A type definition (see the module docstring).
    """
    types = definition.get('types') or []
    out = np.full(matrix.shape[0], -1, dtype=int)
    if not types or matrix.shape[0] == 0:
        return out
    detected = (matrix > 0).sum(axis=1)
    ok = detected >= int(definition.get('min_elements') or 2)
    if not ok.any():
        return out
    clr = clr_rows(matrix[ok], definition['floor'])
    centres = np.asarray([t['centroid'] for t in types], dtype=float)
    radii = np.asarray([float(t.get('radius') or np.inf) for t in types])
    dist = np.sqrt(((clr[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2))
    nearest = dist.argmin(axis=1)
    within = dist[np.arange(dist.shape[0]), nearest] <= radii[nearest]
    idx = np.flatnonzero(ok)
    out[idx[within]] = nearest[within]
    return out


def table_types(table, definition: dict) -> np.ndarray:
    """Type index of every particle of *table* (-1 for none)."""
    return assign(amounts(table, definition), definition)
