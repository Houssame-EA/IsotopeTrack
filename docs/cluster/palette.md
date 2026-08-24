# `palette.py`

Cluster colours shared by every clustering view.

One palette and one override map, so a cluster is the same colour in the ②
Cluster scatters, the Overview strips and heatmap, and the ④ How it works
animation. Overrides live in ``node.config`` and are therefore saved with the
project.

Colours are keyed by the cluster's **label**, not by its position in the list
of labels present. That distinction matters for the density-based algorithms:
if noise (-1) is filtered out of an enumeration, position-keyed colouring
shifts every cluster by one and the same particles change colour between
figures.

---

## Constants

| Name | Value |
|------|-------|
| `CLUSTER_COLORS` | `['#2563EB', '#DC2626', '#16A34A', '#D97706', '#7C3AED', '…` |
| `NOISE_COLOR` | `'#9CA3AF'` |
| `OVERRIDE_KEY` | `'cluster_colors'` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `color_overrides` | `(cfg)` | Return the per-cluster colour overrides as ``{int: '#RRGGBB'}``. |
| `cluster_color` | `(cid, cfg=None)` | Colour for cluster ``cid``, honouring any saved override. |
| `set_color_override` | `(cfg, cid, color)` | Store one cluster's colour on the config, or clear it. |
| `clear_color_overrides` | `(cfg)` | Drop every override, returning the clusters to the default palette. |
