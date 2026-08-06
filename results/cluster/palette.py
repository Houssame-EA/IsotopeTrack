"""Cluster colours shared by every clustering view.

One palette and one override map, so a cluster is the same colour in the ②
Cluster scatters, the Overview strips and heatmap, and the ④ How it works
animation. Overrides live in ``node.config`` and are therefore saved with the
project.

Colours are keyed by the cluster's **label**, not by its position in the list
of labels present. That distinction matters for the density-based algorithms:
if noise (-1) is filtered out of an enumeration, position-keyed colouring
shifts every cluster by one and the same particles change colour between
figures.
"""

from __future__ import annotations

import logging

_log = logging.getLogger("IsotopeTrack.results.cluster.palette")

#: Default cluster colours, cycled for cluster ids beyond its length.
CLUSTER_COLORS = [
    '#2563EB', '#DC2626', '#16A34A', '#D97706', '#7C3AED',
    '#0891B2', '#DB2777', '#65A30D', '#EA580C', '#4F46E5',
    '#0D9488', '#C026D3', '#CA8A04', '#E11D48', '#2DD4BF',
    '#6366F1', '#F59E0B', '#10B981', '#EF4444', '#8B5CF6',
]

#: Colour used for noise points (label -1) from the density-based algorithms.
NOISE_COLOR = '#9CA3AF'

#: ``node.config`` key holding ``{cluster_id: '#RRGGBB'}`` overrides.
OVERRIDE_KEY = 'cluster_colors'


def color_overrides(cfg):
    """Return the per-cluster colour overrides as ``{int: '#RRGGBB'}``.

    JSON round-trips turn the integer keys into strings, so both forms are
    accepted and normalised here.

    Args:
        cfg (dict | None): The node config.

    Returns:
        dict: Cluster id to colour. Empty when nothing has been overridden.
    """
    raw = (cfg or {}).get(OVERRIDE_KEY) or {}
    out = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        try:
            if v:
                out[int(k)] = str(v)
        except (TypeError, ValueError):
            _log.debug("Ignoring malformed colour override %r: %r", k, v)
    return out


def cluster_color(cid, cfg=None):
    """Colour for cluster ``cid``, honouring any saved override.

    Args:
        cid (int): Cluster label. Negative means noise.
        cfg (dict | None): The node config, for overrides.

    Returns:
        str: A ``#RRGGBB`` colour.
    """
    try:
        c = int(cid)
    except (TypeError, ValueError):
        return CLUSTER_COLORS[0]
    if c < 0:
        return NOISE_COLOR
    override = color_overrides(cfg).get(c)
    return override or CLUSTER_COLORS[c % len(CLUSTER_COLORS)]


def set_color_override(cfg, cid, color):
    """Store one cluster's colour on the config, or clear it.

    Args:
        cfg (dict): The node config, modified in place.
        cid (int): Cluster label.
        color (str | None): ``#RRGGBB``, or None/empty to revert to the palette.

    Returns:
        bool: True when the config changed.
    """
    if cfg is None:
        return False
    current = color_overrides(cfg)
    try:
        c = int(cid)
    except (TypeError, ValueError):
        return False
    if color:
        if current.get(c) == color:
            return False
        current[c] = str(color)
    else:
        if c not in current:
            return False
        current.pop(c)
    # Stored with string keys so the config survives a JSON round-trip.
    cfg[OVERRIDE_KEY] = {str(k): v for k, v in sorted(current.items())}
    return True


def clear_color_overrides(cfg):
    """Drop every override, returning the clusters to the default palette.

    Args:
        cfg (dict): The node config, modified in place.

    Returns:
        bool: True when the config changed.
    """
    if cfg is None or not cfg.get(OVERRIDE_KEY):
        return False
    cfg[OVERRIDE_KEY] = {}
    return True
