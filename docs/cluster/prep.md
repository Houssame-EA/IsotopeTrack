# `prep.py`

Shared preprocessing rules for every clustering entry point.

Keeps the ② Cluster tab, the ④ How it works view and the sweep tool agreeing on
how the scaled matrix is reduced before clustering.

---

## Constants

| Name | Value |
|------|-------|
| `EMBED_DIMS` | `3` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `reduction_components` | `(dim_reduction, n_features)` | Number of components to keep for ``dim_reduction``. |
