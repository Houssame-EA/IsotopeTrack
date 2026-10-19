# `canvas_layout.py`

Automatic layout of the Workflow Builder canvas.

Two jobs, both without Qt so they can be tested on plain numbers:

* :func:`arrange` lays the whole graph out in columns by data flow. Each
  node goes one column to the right of its furthest upstream node, nodes in
  a column are ordered to keep links from crossing, children are stacked
  next to their parent and a parent is centred on its children, so a batch
  node with five branches reads as one tidy fan. Unconnected groups are
  packed side by side in columns, shaped like the visible canvas.
* :func:`branch_slot` finds where a new branch (a selector and its plot)
  goes: in the column to the right of its source, on the first free row
  under the branches already there, instead of running off in one long
  line. With a height limit, a full column starts a new one further right.

---

## Constants

| Name | Value |
|------|-------|
| `COLUMN_GAP` | `70.0` |
| `ROW_GAP` | `28.0` |
| `GROUP_GAP` | `80.0` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_components` | `(nodes, edges)` | Connected groups of nodes, ignoring link direction, in first-seen order. |
| `_layers` | `(nodes, edges)` | Column index of each node: one more than its furthest parent. |
| `_resolve` | `(column, desired, size, gap)` | Top edges for the nodes of one column, in order, never overlapping. |
| `_arrange_group` | `(group, edges, size, current, col_gap, row_gap)` | Positions of one connected group, with its top-left corner at the origin. |
| `_pack_columns` | `(blocks, aspect, gap)` | Place blocks of ``(width, height)`` in columns, filled top to bottom, then left to right. |
| `arrange` | `(nodes, edges, size, current=None, origin=(0.0, 0.0), col_gap=COLUMN_G` | Lay the graph out in columns by data flow, with unconnected groups packed side by side. |
| `_overlaps` | `(box, boxes, pad)` | Whether *box* comes within *pad* of any of *boxes*. |
| `branch_slot` | `(source_box, widths, height, boxes, max_height=600.0, col_gap=COLUMN_G` | Where a new branch of nodes, left to right, goes next to its source. |
