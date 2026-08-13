# `export_workbook.py`

Excel export for the Clustering Analysis results.

Writes one workbook with a sheet per kind of result rather than a single
nested document, because the things people do with these numbers are
table-shaped: put the cluster characterisation in a paper, sort the evaluation
sweep to see which K won, check how the samples split across clusters.

Sheet map
---------
``Summary``       Configuration, optimal K and algorithm, dataset size.
``Evaluation``    One row per (algorithm, K) with every metric as a column.
``Clusters``      One row per cluster: type, particle count, dominant elements.
``Composition``   One row per (cluster, element): mean, median, std, frequency.
``Samples``       One row per (cluster, sample): count and fraction.
``Stability``     Bootstrap Jaccard per cluster, mean particle stability.
``Particles``     Per-particle stability and GMM membership, when computed.

A workbook is not a faithful round-trip — floats are written at display
precision and the nesting is flattened — so the JSON export is kept alongside
it for anyone who needs to reload the exact values.

---

## Constants

| Name | Value |
|------|-------|
| `_HEADER_FILL` | `'FF2563EB'` |
| `_HEADER_FONT` | `'FFFFFFFF'` |
| `_MAX_ROWS` | `1000000` |
| `_MAX_CHARS` | `32000` |
| `_INLINE_ITEMS` | `24` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_cell` | `(v)` | Coerce any value into something openpyxl can write. |
| `_pairs` | `(seq)` | Normalise an element list into ``(element, percentage)`` pairs. |
| `_autosize` | `(ws)` | Widen every column to fit its longest cell. |
| `_write_sheet` | `(wb, title, headers, rows)` | Add one sheet with a styled header row and frozen panes. |
| `_f` | `(v, nd=4)` | Round a value for display, passing non-numbers through. |
| `_summary_rows` | `(dlg)` | Build the Summary sheet rows. |
| `_evaluation_rows` | `(dlg)` | Build the Evaluation sheet. |
| `_cluster_rows` | `(dlg)` | Build the Clusters sheet. |
| `_composition_rows` | `(dlg)` | Build the Composition sheet. |
| `_sample_rows` | `(dlg)` | Build the Samples sheet. |
| `_as_array` | `(v)` | Return ``v`` as a NumPy array, treating None as empty. |
| `_stability_rows` | `(dlg)` | Build the Stability sheet. |
| `_particle_rows` | `(dlg)` | Build the Particles sheet from the per-particle arrays. |
| `_algo_blocks` | `(ws)` | Find the contiguous row range each algorithm occupies. |
| `_chart_evaluation` | `(wb, ws)` | Add one line chart per metric to the Evaluation sheet. |
| `_chart_clusters` | `(wb, ws)` | Add a bar chart of particle counts and a pie chart of the shares. |
| `_chart_samples` | `(wb, ws)` | Add a stacked bar chart of how samples split across the clusters. |
| `_chart_stability` | `(wb, ws)` | Add a bar chart of the per-cluster bootstrap Jaccard scores. |
| `export_workbook` | `(dlg, path)` | Write the clustering results to an Excel workbook. |
