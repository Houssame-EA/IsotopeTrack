"""Direct manipulation in the preview: hover read-outs and drags.

* :func:`readout` describes what is under the cursor — the nearest particle
  of a scatter plot with its values, a matrix cell, a histogram bin, a group
  summary, a pie slice or plain X/Y coordinates.
* :func:`drag_mode` decides what a press-and-drag will do at a point:
  move the legend or a note, draw a zoom box, move or resize the panel.
* :func:`apply_drag` writes the result of a finished drag into the spec.

Positions use figure fractions with the origin at the top-left, like the
rest of the Figure Builder window.
"""

from __future__ import annotations

import numpy as np

from results.figure_builder.core.expressions import plain

ZOOM_X = {'scatter', 'line', 'density', 'histogram'}
ZOOM_Y = {'scatter', 'line', 'density', 'histogram', 'box', 'violin', 'bar'}
CORNER = 0.025
SNAP = 1.0 / 96.0


def _display(fig, fx, fy):
    """Display (pixel) coordinates of a figure-fraction point."""
    return fig.transFigure.transform((fx, 1.0 - fy))


def _fmt(v) -> str:
    """Compact number formatting for read-outs."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    if not np.isfinite(v):
        return '—'
    if v != 0 and (abs(v) >= 1e5 or abs(v) < 1e-3):
        return f'{v:.3e}'
    return f'{v:.4g}'


def _nearest_point(fig, ax, hd, disp, radius_px):
    """The particle drawn closest to ``disp`` within ``radius_px`` (or None)."""
    best = None
    for layer in hd.get('points') or []:
        cache = layer.get('_disp')
        if cache is None:
            pts = np.column_stack([layer['x'], layer['y']]).astype(float)
            try:
                cache = ax.transData.transform(pts)
            except Exception:
                continue
            layer['_disp'] = cache
        if cache.size == 0:
            continue
        d2 = ((cache - disp) ** 2).sum(axis=1)
        i = int(np.argmin(d2))
        if d2[i] <= radius_px ** 2 and (best is None or d2[i] < best[0]):
            best = (d2[i], layer, i)
    return best


def readout(win, hit, fx, fy) -> str:
    """Text describing what lies under the cursor (empty when nothing useful)."""
    fig = win.last_fig
    if fig is None or hit is None:
        return ''
    if hit.element not in ('plot',):
        return _element_hint(hit)
    hd = win.last_report.artists.get(hit.panel_id) or {}
    ax = hd.get('ax')
    if ax is None:
        return ''
    disp = _display(fig, fx, fy)
    radius = max(6.0, fig.dpi * 0.09)
    near = _nearest_point(fig, ax, hd, disp, radius)
    if near is not None:
        _d, layer, i = near
        idx = int(layer['index'][i])
        table = hd.get('table')
        lines = [f'Particle #{idx + 1} · {layer["group"]}']
        lines.append(f'{hd.get("x_name", "x")} = {_fmt(layer["x"][i])}')
        lines.append(f'{hd.get("y_name", "y")} = {_fmt(layer["y"][i])}')
        if table is not None and idx < len(table):
            try:
                sample = table.column('sample')[idx]
                cls = table.column('class')[idx]
                extra = f'sample: {sample}'
                if cls and cls != 'Unclassified':
                    extra += f' · class: {cls}'
                lines.append(extra)
                parts = [f'{lab} {_fmt(table.column(lab)[idx])}' for lab in table.labels[:6]
                         if table.column(lab)[idx] > 0]
                if parts:
                    lines.append(', '.join(parts))
            except Exception:
                pass
        return '\n'.join(lines)
    matrix = hd.get('matrix')
    if matrix is not None:
        try:
            cx, cy = ax.transData.inverted().transform(disp)
        except Exception:
            return ''
        j, i = int(round(cx)), int(round(cy))
        vals = matrix['values']
        if 0 <= i < vals.shape[0] and 0 <= j < vals.shape[1]:
            rows, cols = matrix.get('rows') or [], matrix.get('cols') or []
            r = plain(rows[i]) if i < len(rows) else f'row {i + 1}'
            c = plain(cols[j]) if j < len(cols) else f'column {j + 1}'
            text = f'{r} × {c}\n{plain(matrix.get("label", "value"))} = {_fmt(vals[i, j])}'
            if 'n' in matrix:
                text += f'\nparticles = {int(matrix["n"][i, j])}'
                p = matrix['p'][i, j]
                if np.isfinite(p):
                    text += f' · p = {p:.3g}'
            return text
        return ''
    for wedge, label, size, pct in hd.get('wedges') or []:
        if wedge.contains_point(disp):
            return f'{plain(label)}\n{int(size):,} particles · {pct:.1f}%' if float(size).is_integer() \
                else f'{plain(label)}\n{_fmt(size)} · {pct:.1f}%'
    try:
        x, y = ax.transData.inverted().transform(disp)
    except Exception:
        return ''
    cats = hd.get('categories')
    if cats:
        coord = x if cats['axis'] == 'x' else y
        pos = np.asarray(cats['positions'], dtype=float)
        if pos.size:
            k = int(np.argmin(np.abs(pos - coord)))
            if abs(pos[k] - coord) <= 0.5:
                label, v = cats['items'][k]
                v = np.asarray(v, dtype=float)
                v = v[np.isfinite(v)]
                if v.size:
                    q1, med, q3 = np.percentile(v, [25, 50, 75])
                    return (f'{plain(label)} (n = {v.size:,})\nmedian {_fmt(med)} · mean {_fmt(np.mean(v))}'
                            f'\nIQR {_fmt(q1)} – {_fmt(q3)} · range {_fmt(v.min())} – {_fmt(v.max())}')
    hist = hd.get('hist')
    if hist:
        lines = []
        for label, edges, counts in hist:
            b = int(np.searchsorted(edges, x, side='right') - 1)
            if 0 <= b < len(counts):
                lines.append(f'{plain(label)}: {int(counts[b])} particles in {_fmt(edges[b])} – {_fmt(edges[b + 1])}')
        if lines:
            return '\n'.join(lines)
    if getattr(ax, 'name', '') == 'ternary':
        return ''
    return f'x = {_fmt(x)}\ny = {_fmt(y)}'


def _element_hint(hit) -> str:
    """Short help shown when hovering a text element or the panel margin."""
    if hit.element in ('legend', 'annotation'):
        return 'Drag to move · right-click for options'
    if hit.element == 'panel':
        return 'Drag to move this panel · drag its lower-right corner to resize'
    if hit.element in ('ticks_x', 'ticks_y'):
        return 'Right-click for bold, italic and size · double-click to rename items'
    if hit.element == 'letters':
        return 'Right-click to style the panel letters'
    return 'Double-click to rename · right-click for bold, italic, size, colour'


def drag_mode(win, hit, fx, fy):
    """What a drag starting here will do: ``(mode, box)`` or None.

    ``box`` is the region drawn as a live outline (figure fractions,
    top-left origin) for moves and resizes.
    """
    if hit is None or not hit.panel_id:
        return None
    panel = win.panel_by_id(hit.panel_id)
    if panel is None:
        return None
    x, y, w, h = panel['rect']
    if abs(fx - (x + w)) <= CORNER and abs(fy - (y + h)) <= CORNER:
        return 'resize', (x, y, x + w, y + h)
    if hit.element == 'legend':
        return 'legend', hit.box
    if hit.element == 'annotation':
        return 'note', hit.box
    if hit.element == 'plot':
        kind = panel.get('kind')
        if kind in ZOOM_Y:
            return 'zoom', None
        return 'move', (x, y, x + w, y + h)
    if hit.element == 'panel':
        return 'move', (x, y, x + w, y + h)
    return None


def _snap(v: float) -> float:
    return round(v / SNAP) * SNAP


def apply_drag(win, hit, mode, start, end) -> bool:
    """Apply a finished drag; returns True when the spec changed."""
    panel = win.panel_by_id(hit.panel_id) if hit is not None else None
    if panel is None:
        return False
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    if mode == 'move':
        x, y, w, h = panel['rect']
        nx = min(1.0 - w, max(0.0, _snap(x + dx)))
        ny = min(1.0 - h, max(0.0, _snap(y + dy)))
        panel['rect'] = [round(nx, 4), round(ny, 4), w, h]
        return True
    if mode == 'resize':
        x, y, w, h = panel['rect']
        nw = min(1.0 - x, max(0.08, _snap(ex - x)))
        nh = min(1.0 - y, max(0.08, _snap(ey - y)))
        panel['rect'] = [x, y, round(nw, 4), round(nh, 4)]
        return True
    fig = win.last_fig
    hd = win.last_report.artists.get(panel['id']) or {}
    ax = hd.get('ax')
    if fig is None or ax is None:
        return False
    if mode == 'legend':
        x0, y0, _x1, _y1 = hit.box
        disp = _display(fig, x0 + dx, y0 + dy)
        ax_x, ax_y = ax.transAxes.inverted().transform(disp)
        panel['legend'] = True
        panel['legend_loc'] = 'custom'
        panel['legend_xy'] = [round(float(ax_x), 4), round(float(ax_y), 4)]
        return True
    if mode == 'note':
        notes = panel.get('annotations') or []
        if not 0 <= hit.index < len(notes):
            return False
        note = notes[hit.index]
        x0, y0, _x1, y1 = hit.box
        disp = _display(fig, x0 + dx, (y0 + y1) / 2 + dy)
        if note.get('coords') == 'data':
            nx, ny = ax.transData.inverted().transform(disp)
            note['x'], note['y'] = f'{nx:.6g}', f'{ny:.6g}'
        else:
            nx, ny = ax.transAxes.inverted().transform(disp)
            note['x'], note['y'] = f'{nx:.3f}', f'{ny:.3f}'
        return True
    if mode == 'zoom':
        if abs(dx) < 0.01 and abs(dy) < 0.01:
            return False
        inv = ax.transData.inverted()
        a = inv.transform(_display(fig, sx, sy))
        b = inv.transform(_display(fig, ex, ey))
        kind = panel.get('kind')
        horizontal_bar = kind == 'bar' and panel.get('horizontal')
        if kind in ZOOM_X or horizontal_bar:
            if abs(dx) >= 0.01:
                lo, hi = sorted((float(a[0]), float(b[0])))
                panel['x_min'], panel['x_max'] = f'{lo:.6g}', f'{hi:.6g}'
        if kind in ZOOM_Y and not horizontal_bar:
            if abs(dy) >= 0.01:
                lo, hi = sorted((float(a[1]), float(b[1])))
                panel['y_min'], panel['y_max'] = f'{lo:.6g}', f'{hi:.6g}'
        return True
    return False


def reset_zoom(panel) -> bool:
    """Forget a panel's axis limits; returns True when any were set."""
    changed = any(panel.get(k) for k in ('x_min', 'x_max', 'y_min', 'y_max'))
    for k in ('x_min', 'x_max', 'y_min', 'y_max'):
        panel[k] = ''
    return changed
