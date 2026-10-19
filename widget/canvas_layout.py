"""Automatic layout of the Workflow Builder canvas.

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
"""
from __future__ import annotations

import math
from collections import defaultdict

COLUMN_GAP = 70.0
ROW_GAP = 28.0
GROUP_GAP = 80.0


def _components(nodes, edges):
    """Connected groups of nodes, ignoring link direction, in first-seen order."""
    nbr = defaultdict(set)
    for a, b in edges:
        nbr[a].add(b)
        nbr[b].add(a)
    seen, groups = set(), []
    for n in nodes:
        if n in seen:
            continue
        stack, group = [n], []
        seen.add(n)
        while stack:
            cur = stack.pop()
            group.append(cur)
            for m in nbr[cur]:
                if m not in seen:
                    seen.add(m)
                    stack.append(m)
        groups.append([g for g in nodes if g in set(group)])
    return groups


def _layers(nodes, edges):
    """Column index of each node: one more than its furthest parent.

    A link that would close a loop is ignored, so a stray cycle never
    blocks the layout.
    """
    parents = defaultdict(list)
    children = defaultdict(list)
    for a, b in edges:
        children[a].append(b)
        parents[b].append(a)
    indeg = {n: len(parents[n]) for n in nodes}
    ready = [n for n in nodes if indeg[n] == 0]
    order, layer = [], {}
    while ready:
        n = ready.pop(0)
        order.append(n)
        layer[n] = max((layer[p] + 1 for p in parents[n] if p in layer), default=0)
        for c in children[n]:
            indeg[c] -= 1
            if indeg[c] == 0:
                ready.append(c)
    for n in nodes:
        if n not in layer:
            layer[n] = max((layer[p] + 1 for p in parents[n] if p in layer), default=0)
    return layer


def _resolve(column, desired, size, gap):
    """Top edges for the nodes of one column, in order, never overlapping."""
    out, floor = {}, None
    for n in column:
        y = desired[n] if floor is None else max(desired[n], floor)
        out[n] = y
        floor = y + size[n][1] + gap
    return out


def _arrange_group(group, edges, size, current, col_gap, row_gap):
    """Positions of one connected group, with its top-left corner at the origin."""
    inside = set(group)
    local = [(a, b) for a, b in edges if a in inside and b in inside]
    layer = _layers(group, local)
    parents, children = defaultdict(list), defaultdict(list)
    for a, b in local:
        parents[b].append(a)
        children[a].append(b)
    depth = max(layer.values()) + 1
    columns = [[n for n in group if layer[n] == k] for k in range(depth)]
    columns[0].sort(key=lambda n: (current[n][1], current[n][0]))
    for _ in range(2):
        for k in range(1, depth):
            rank = {n: i for i, n in enumerate(columns[k - 1])}
            columns[k].sort(key=lambda n: (
                sum(rank[p] for p in parents[n] if p in rank) / max(1, sum(p in rank for p in parents[n]))
                if any(p in rank for p in parents[n]) else len(rank),
                current[n][1]))
        for k in range(depth - 2, -1, -1):
            rank = {n: i for i, n in enumerate(columns[k + 1])}
            columns[k].sort(key=lambda n: (
                sum(rank[c] for c in children[n] if c in rank) / max(1, sum(c in rank for c in children[n]))
                if any(c in rank for c in children[n]) else len(rank),
                current[n][1]))
    xs, x = [], 0.0
    for col in columns:
        xs.append(x)
        x += max(size[n][0] for n in col) + col_gap
    y = {}
    y.update(_resolve(columns[0], {n: 0.0 for n in columns[0]}, size, row_gap))
    for k in range(1, depth):
        desired, siblings = {}, defaultdict(list)
        for n in columns[k]:
            ps = [p for p in parents[n] if p in y]
            if len(ps) == 1:
                siblings[ps[0]].append(n)
            elif ps:
                desired[n] = sum(y[p] + size[p][1] / 2 for p in ps) / len(ps) - size[n][1] / 2
            else:
                desired[n] = 0.0
        for p, kids in siblings.items():
            block = sum(size[c][1] for c in kids) + row_gap * (len(kids) - 1)
            top = y[p] + size[p][1] / 2 - block / 2
            for c in kids:
                desired[c] = top
                top += size[c][1] + row_gap
        y.update(_resolve(columns[k], desired, size, row_gap))
    for k in range(depth - 2, -1, -1):
        desired = {}
        for n in columns[k]:
            cs = [c for c in children[n] if c in y and layer[c] == k + 1 and len(parents[c]) == 1]
            if cs:
                top = min(y[c] for c in cs)
                bottom = max(y[c] + size[c][1] for c in cs)
                desired[n] = (top + bottom) / 2 - size[n][1] / 2
            else:
                desired[n] = y[n]
        y.update(_resolve(columns[k], desired, size, row_gap))
    low = min(y.values())
    return {n: (xs[layer[n]], y[n] - low) for n in group}


def _pack_columns(blocks, aspect, gap):
    """Place blocks of ``(width, height)`` in columns, filled top to bottom, then left to right.

    Every column count from one up to one per block is tried, each column
    filled until it would pass the height the count calls for, and the
    count whose overall shape is closest to *aspect* (width / height) wins.

    Args:
        blocks (list): ``(width, height)`` of each block, in reading order.
        aspect (float): Wanted width / height of the whole.
        gap (float): Space between blocks and between columns.

    Returns:
        list: ``(x, y)`` offset of each block.
    """
    if not blocks:
        return []
    total = sum(h for _, h in blocks) + gap * (len(blocks) - 1)
    tallest = max(h for _, h in blocks)
    best, best_score = None, None
    for k in range(1, len(blocks) + 1):
        limit = max(tallest, total / k)
        spots, x, y, col_w = [], 0.0, 0.0, 0.0
        for w, h in blocks:
            if y > 0 and y + h > limit + 1e-6:
                x += col_w + gap
                y, col_w = 0.0, 0.0
            spots.append((x, y))
            y += h + gap
            col_w = max(col_w, w)
        width = max(sx + w for (sx, _), (w, _) in zip(spots, blocks))
        height = max(sy + h for (_, sy), (_, h) in zip(spots, blocks))
        score = abs(math.log((width / max(height, 1.0)) / aspect))
        if best_score is None or score < best_score - 1e-9:
            best, best_score = spots, score
    return best


def arrange(nodes, edges, size, current=None, origin=(0.0, 0.0),
            col_gap=COLUMN_GAP, row_gap=ROW_GAP, group_gap=GROUP_GAP, aspect=1.6):
    """Lay the graph out in columns by data flow, with unconnected groups packed side by side.

    Args:
        nodes (list): Node keys, in any order.
        edges (list): ``(source, sink)`` pairs.
        size (dict): ``key -> (width, height)``.
        current (dict): ``key -> (x, y)`` now; keeps the user's top-to-bottom
            order where the links leave a choice, and sets the origin.
        origin (tuple): Top-left corner when *current* is not given.
        col_gap (float): Space between columns.
        row_gap (float): Space between nodes in a column.
        group_gap (float): Space between unconnected groups.
        aspect (float): Wanted width / height of the whole layout, usually
            the visible canvas; ``None`` stacks every group in one column.

    Returns:
        dict: ``key -> (x, y)`` top-left positions.
    """
    nodes = list(nodes)
    if not nodes:
        return {}
    current = dict(current or {})
    for n in nodes:
        current.setdefault(n, origin)
    keyset = set(nodes)
    edges = [(a, b) for a, b in edges if a in keyset and b in keyset and a != b]
    ox = min(current[n][0] for n in nodes)
    oy = min(current[n][1] for n in nodes)
    groups = _components(nodes, edges)
    groups.sort(key=lambda g: (min(current[n][0] for n in g) // 600, min(current[n][1] for n in g)))
    layouts, blocks = [], []
    for g in groups:
        local = _arrange_group(g, edges, size, current, col_gap, row_gap)
        layouts.append(local)
        blocks.append((max(x + size[n][0] for n, (x, y) in local.items()),
                       max(y + size[n][1] for n, (x, y) in local.items())))
    if aspect:
        spots = _pack_columns(blocks, float(aspect), group_gap)
    else:
        spots, y = [], 0.0
        for _, h in blocks:
            spots.append((0.0, y))
            y += h + group_gap
    out = {}
    for local, (bx, by) in zip(layouts, spots):
        for n, (x, y) in local.items():
            out[n] = (ox + bx + x, oy + by + y)
    return out


def _overlaps(box, boxes, pad):
    """Whether *box* comes within *pad* of any of *boxes*."""
    left, top, right, bottom = box
    for l2, t2, r2, b2 in boxes:
        if left < r2 + pad and right > l2 - pad and top < b2 + pad and bottom > t2 - pad:
            return True
    return False


def branch_slot(source_box, widths, height, boxes, max_height=600.0,
                col_gap=COLUMN_GAP, row_gap=ROW_GAP):
    """Where a new branch of nodes, left to right, goes next to its source.

    The branch starts one column right of the source, level with it, and
    moves down a row at a time until nothing is in the way. Past
    *max_height* below the source it starts again at the source's level, one
    branch-width further right.

    Args:
        source_box (tuple): ``(left, top, right, bottom)`` of the source node,
            or ``None`` for an empty canvas.
        widths (list): Width of each node of the branch, left to right.
        height (float): Height of the tallest node of the branch.
        boxes (list): ``(left, top, right, bottom)`` of every node already placed.
        max_height (float): How far down a column may grow, usually the
            visible canvas height.
        col_gap (float): Space between the nodes of the branch and columns.
        row_gap (float): Space between rows.

    Returns:
        list: ``(x, y)`` for each node of the branch.
    """
    if source_box is None:
        source_box = (0.0, 0.0, 0.0, 0.0)
        start_x = 0.0
    else:
        start_x = source_box[2] + col_gap
    span = sum(widths) + col_gap * (len(widths) - 1)
    step = height + row_gap
    rows = 10_000 if max_height == float('inf') else max(1, int(max(max_height, step) // step))
    for band in range(40):
        x0 = start_x + band * (span + col_gap)
        for row in range(rows):
            y0 = source_box[1] + row * step
            xs, x = [], x0
            for w in widths:
                xs.append(x)
                x += w + col_gap
            cells = [(xi, y0, xi + w, y0 + height) for xi, w in zip(xs, widths)]
            if not any(_overlaps(c, boxes, row_gap / 2) for c in cells):
                return [(xi, y0) for xi in xs]
    x0 = start_x + 40 * (span + col_gap)
    xs, x = [], x0
    for w in widths:
        xs.append(x)
        x += w + col_gap
    return [(xi, source_box[1]) for xi in xs]
