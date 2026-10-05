"""Editing the figure directly in the preview.

After each render the window asks :func:`collect_hits` where every panel,
axis label, title, legend, tick-label strip, colour bar label, note and
panel letter ended up. Clicks on the preview are mapped to the smallest
region under the cursor, which drives:

* a right-click menu tailored to what was clicked (:func:`build_menu`),
* double-click renaming of any text (:func:`edit_text`),
* the text-style dialog (:class:`TextStyleDialog`) for bold, italic, size,
  colour and font of any text element, per panel or for the whole figure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFontDatabase
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QHeaderView, QInputDialog, QLabel, QMenu, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from results.figure_builder.core import engine as E
from results.figure_builder.core import styles as S
from results.figure_builder.core import textstyle as T
from results.figure_builder.core.expressions import DATA_TYPES, plain
from results.figure_builder.ui.widgets import ColorButton

XYISH = {'scatter', 'line', 'density', 'histogram', 'box', 'violin', 'bar', 'hexbin', 'contour',
         'strip'}
RENAMEABLE = {'corr_matrix', 'heatmap', 'cooccurrence', 'composition', 'pairs', 'bar', 'pie',
              'combinations'}

TEXT_FIELDS = {
    'title': 'title', 'x_label': 'x_label', 'y_label': 'y_label', 'y2_label': 'y2_label',
    'cbar_label': 'cbar_label', 'corner_a': 'a_label', 'corner_b': 'b_label', 'corner_c': 'c_label',
}
"""Hit element → panel field holding its text."""

STYLE_ELEMENT = {
    'corner_a': 'corner_labels', 'corner_b': 'corner_labels', 'corner_c': 'corner_labels',
    'ticks_x': 'ticks', 'ticks_y': 'ticks', 'cbar': 'ticks',
}
"""Hit element → text-style element (identity when absent)."""

ELEMENT_NAMES = {
    'title': 'panel title', 'x_label': 'X axis label', 'y_label': 'Y axis label',
    'y2_label': 'right axis label', 'cbar_label': 'colour bar label', 'legend': 'legend',
    'ticks_x': 'X tick labels', 'ticks_y': 'Y tick labels', 'corner_a': 'top corner label',
    'corner_b': 'left corner label', 'corner_c': 'right corner label', 'annotation': 'note',
    'figure_title': 'figure title', 'letters': 'panel letter', 'plot': 'plot', 'panel': 'panel',
    'cbar': 'colour bar',
}


@dataclass
class Hit:
    """One clickable region of the rendered figure.

    Attributes:
        box: ``(x0, y0, x1, y1)`` in figure fractions, origin top-left.
        panel_id: Owning panel ('' for figure-level text).
        element: What was hit (see :data:`ELEMENT_NAMES`).
        index: Annotation index for notes.
        text: The text shown, when the element is text.
    """

    box: tuple
    panel_id: str
    element: str
    index: int = -1
    text: str = ''
    data: dict = field(default_factory=dict)

    @property
    def area(self) -> float:
        """Area of the region (smaller wins when regions overlap)."""
        return max(0.0, self.box[2] - self.box[0]) * max(0.0, self.box[3] - self.box[1])

    def contains(self, fx: float, fy: float) -> bool:
        """Whether a point (figure fractions, top-left origin) is inside."""
        pad = 0.004
        return self.box[0] - pad <= fx <= self.box[2] + pad and self.box[1] - pad <= fy <= self.box[3] + pad


def _box(fig, artist, renderer):
    """Figure-fraction box (top-left origin) of an artist, or None."""
    try:
        if not artist.get_visible():
            return None
        if hasattr(artist, 'get_text') and not artist.get_text():
            return None
        bb = artist.get_window_extent(renderer)
    except Exception:
        return None
    if bb.width <= 0 or bb.height <= 0:
        return None
    f = bb.transformed(fig.transFigure.inverted())
    return (f.x0, 1 - f.y1, f.x1, 1 - f.y0)


def _union(boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def collect_hits(fig, report, spec) -> list[Hit]:
    """Every clickable region of a freshly drawn figure."""
    canvas = fig.canvas
    renderer = canvas.get_renderer()
    hits: list[Hit] = []
    for panel in spec.get('panels', []):
        pid = panel['id']
        x, y, w, h = panel['rect']
        hits.append(Hit((x, y, x + w, y + h), pid, 'panel'))
        hd = report.artists.get(pid) or {}
        ax = hd.get('ax')
        if ax is None:
            continue
        axes = [ax] + list(hd.get('extra_axes') or [])
        plot_box = _union([_box(fig, a, renderer) if a.get_visible() and a.axison else None
                           for a in axes]) or _box(fig, ax, renderer)
        if plot_box:
            hits.append(Hit(plot_box, pid, 'plot'))
        b = _box(fig, ax.title, renderer)
        if b:
            hits.append(Hit(b, pid, 'title', text=ax.title.get_text()))
        if getattr(ax, 'name', '') == 'ternary':
            for key, axis_name in (('corner_a', 'taxis'), ('corner_b', 'laxis'), ('corner_c', 'raxis')):
                axis = getattr(ax, axis_name, None)
                if axis is not None:
                    b = _box(fig, axis.label, renderer)
                    if b:
                        hits.append(Hit(b, pid, key, text=axis.label.get_text()))
        elif ax.axison:
            for key, lab in (('x_label', ax.xaxis.label), ('y_label', ax.yaxis.label)):
                b = _box(fig, lab, renderer)
                if b:
                    hits.append(Hit(b, pid, key, text=lab.get_text()))
            b = _union([_box(fig, t, renderer) for t in ax.get_xticklabels()])
            if b:
                hits.append(Hit(b, pid, 'ticks_x'))
            b = _union([_box(fig, t, renderer) for t in ax.get_yticklabels()])
            if b:
                hits.append(Hit(b, pid, 'ticks_y'))
        ax2 = hd.get('ax2')
        if ax2 is not None:
            b = _box(fig, ax2.yaxis.label, renderer)
            if b:
                hits.append(Hit(b, pid, 'y2_label', text=ax2.yaxis.label.get_text()))
        cb = hd.get('cbar')
        if cb is not None and cb.ax.get_visible():
            try:
                tb = cb.ax.get_tightbbox(renderer)
            except Exception:
                tb = None
            if tb is not None and tb.width > 0:
                f = tb.transformed(fig.transFigure.inverted())
                hits.append(Hit((f.x0, 1 - f.y1, f.x1, 1 - f.y0), pid, 'cbar'))
        if cb is not None:
            lab = cb.ax.yaxis.label if cb.ax.yaxis.label.get_text() else cb.ax.xaxis.label
            b = _box(fig, lab, renderer)
            if b:
                hits.append(Hit(b, pid, 'cbar_label', text=lab.get_text()))
        for a in axes:
            leg = a.get_legend()
            if leg is not None:
                b = _box(fig, leg, renderer)
                if b:
                    hits.append(Hit(b, pid, 'legend'))
        for t in ax.texts:
            idx = getattr(t, '_fb_annotation', None)
            if idx is not None:
                b = _box(fig, t, renderer)
                if b:
                    hits.append(Hit(b, pid, 'annotation', index=idx, text=t.get_text()))
    for t in fig.texts:
        tag = getattr(t, '_fb_element', None)
        if tag:
            b = _box(fig, t, renderer)
            if b:
                hits.append(Hit(b, tag[0], tag[1], text=t.get_text()))
    sup = getattr(fig, '_suptitle', None)
    if sup is not None and sup.get_text():
        b = _box(fig, sup, renderer)
        if b:
            hits.append(Hit(b, '', 'figure_title', text=sup.get_text()))
    return hits


def hit_at(hits: list[Hit], fx: float, fy: float) -> Hit | None:
    """The most specific region under a point."""
    inside = [h for h in hits if h.contains(fx, fy)]
    if not inside:
        return None
    rank = {'panel': 3, 'plot': 2}
    return min(inside, key=lambda h: (rank.get(h.element, 0), h.area))


class TextStyleDialog(QDialog):
    """Size, bold, italic, colour and font for a set of text elements.

    Bold and italic checkboxes are three-state: the middle state means
    "inherit" (keep the figure default).
    """

    def __init__(self, elements: list[str], styles: dict, title: str, parent=None,
                 figure_level: bool = False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.elements = elements
        lay = QVBoxLayout(self)
        info = QLabel('Size 0 = automatic. Bold / Italic: tick = on, empty = off, '
                      'filled square = keep the default. Right-click a colour to reset it.')
        info.setWordWrap(True)
        info.setObjectName('fbHint')
        lay.addWidget(info)
        self.table = QTableWidget(len(elements), 6)
        self.table.setHorizontalHeaderLabels(['Text', 'Size', 'Bold', 'Italic', 'Colour', 'Font'])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.Stretch)
        families = ['(default)'] + sorted(set(QFontDatabase.families()))
        self._rows = []
        for i, el in enumerate(elements):
            st = styles.get(el) or {}
            name = QTableWidgetItem(T.ALL_ELEMENTS.get(el, el))
            name.setFlags(name.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, name)
            size = QDoubleSpinBox()
            size.setRange(0, 96)
            size.setSpecialValueText('auto')
            size.setValue(float(st.get('size') or 0))
            self.table.setCellWidget(i, 1, size)
            bold = self._tri(st.get('bold'))
            italic = self._tri(st.get('italic'))
            self.table.setCellWidget(i, 2, bold)
            self.table.setCellWidget(i, 3, italic)
            color = ColorButton(st.get('color') or '', allow_none=True)
            self.table.setCellWidget(i, 4, color)
            fam = QComboBox()
            fam.addItems(families)
            fam.setCurrentIndex(max(0, fam.findText(st.get('family') or '(default)')))
            self.table.setCellWidget(i, 5, fam)
            self._rows.append((el, size, bold, italic, color, fam))
        self.table.resizeRowsToContents()
        self.table.setMinimumWidth(620)
        self.table.setMinimumHeight(min(420, 40 + 34 * len(elements)))
        lay.addWidget(self.table)
        self.all_panels = QCheckBox('Apply to every panel (figure default)')
        self.all_panels.setChecked(figure_level)
        self.all_panels.setVisible(not figure_level)
        lay.addWidget(self.all_panels)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    @staticmethod
    def _tri(value):
        cb = QCheckBox()
        cb.setTristate(True)
        cb.setCheckState(Qt.PartiallyChecked if value is None
                         else Qt.Checked if value else Qt.Unchecked)
        return cb

    def styles(self) -> dict:
        """The edited styles, keyed by element, with inherited keys left out."""
        out = {}
        for el, size, bold, italic, color, fam in self._rows:
            st = {}
            if size.value():
                st['size'] = size.value()
            for key, box in (('bold', bold), ('italic', italic)):
                if box.checkState() != Qt.PartiallyChecked:
                    st[key] = box.checkState() == Qt.Checked
            if color.color():
                st['color'] = color.color()
            if fam.currentIndex() > 0:
                st['family'] = fam.currentText()
            out[el] = st
        return out


class ItemLabelsDialog(QDialog):
    """Rename the isotopes or expressions shown by a panel."""

    def __init__(self, items: list[tuple[str, str]], current: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Rename items')
        lay = QVBoxLayout(self)
        tip = QLabel('Leave a name empty to use the automatic one.')
        tip.setObjectName('fbHint')
        lay.addWidget(tip)
        self.table = QTableWidget(len(items), 2)
        self.table.setHorizontalHeaderLabels(['Item', 'Show as'])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.keys = []
        for i, (key, auto) in enumerate(items):
            a = QTableWidgetItem(plain(auto) if auto else key)
            a.setFlags(a.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, a)
            self.table.setItem(i, 1, QTableWidgetItem(current.get(key, '')))
            self.keys.append(key)
        self.table.setMinimumWidth(420)
        lay.addWidget(self.table)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def labels(self) -> dict:
        """``{item: new name}`` for every renamed item."""
        out = {}
        for i, key in enumerate(self.keys):
            item = self.table.item(i, 1)
            if item is not None and item.text().strip():
                out[key] = item.text().strip()
        return out


def edit_text(win, hit: Hit) -> bool:
    """Ask for new text for a clicked label; returns True when something changed."""
    spec = win.spec
    if hit.element == 'figure_title':
        new, ok = QInputDialog.getText(win, 'Figure title', 'Title:', text=spec['figure'].get('title', ''))
        if ok:
            spec['figure']['title'] = new
        return ok
    panel = win.panel_by_id(hit.panel_id)
    if panel is None:
        return False
    if hit.element == 'annotation':
        notes = panel.get('annotations') or []
        if 0 <= hit.index < len(notes):
            new, ok = QInputDialog.getText(win, 'Edit note', 'Text:', text=notes[hit.index].get('text', ''))
            if ok:
                notes[hit.index]['text'] = new
            return ok
        return False
    if hit.element == 'legend':
        win.show_editor_tab('Groups')
        return False
    if hit.element in ('ticks_x', 'ticks_y'):
        if panel.get('kind') in RENAMEABLE:
            return rename_items(win, panel)
        if panel.get('group_by', 'none') != 'none':
            win.show_editor_tab('Groups')
        return False
    key = TEXT_FIELDS.get(hit.element)
    if key is None:
        return False
    shown = plain(hit.text)
    current = panel.get(key) or shown
    new, ok = QInputDialog.getText(win, f'Edit {ELEMENT_NAMES.get(hit.element, "text")}',
                                   'Text (leave empty for automatic; $...$ for math):',
                                   text=current)
    if ok:
        panel[key] = new
    return ok


def rename_items(win, panel) -> bool:
    """Open the rename dialog for a panel's isotopes / expressions."""
    from results.figure_builder.core.common import item_exprs
    from results.figure_builder.core.expressions import pretty, split_list
    table = win.table.view(panel.get('data_type'))
    if panel.get('kind') in ('bar', 'pie'):
        exprs = split_list(panel.get('value') or '')
    else:
        exprs = item_exprs(panel, table)
    items = []
    for e in exprs:
        try:
            items.append((e, pretty(e, table, win.spec['figure'].get('label_style', 'isotope'))))
        except Exception:
            items.append((e, e))
    if not items:
        return False
    dlg = ItemLabelsDialog(items, panel.get('item_labels') or {}, win)
    if dlg.exec() != QDialog.Accepted:
        return False
    panel['item_labels'] = dlg.labels()
    return True


def style_dialog(win, panel, elements, title) -> bool:
    """Text-style dialog for ``elements`` of ``panel`` (None = figure level)."""
    figcfg = win.spec['figure']
    figure_level = panel is None
    current = {}
    for el in elements:
        src = (figcfg.get('text_styles') or {}) if figure_level else (panel.get('text_styles') or {})
        current[el] = dict(src.get(el) or {})
    dlg = TextStyleDialog(elements, current, title, win, figure_level=figure_level)
    if dlg.exec() != QDialog.Accepted:
        return False
    new = dlg.styles()
    if figure_level or dlg.all_panels.isChecked():
        fs = dict(figcfg.get('text_styles') or {})
        for el, st in new.items():
            fs[el] = st
        figcfg['text_styles'] = fs
        if not figure_level:
            for p in win.spec['panels']:
                ps = dict(p.get('text_styles') or {})
                for el in new:
                    ps.pop(el, None)
                p['text_styles'] = ps
    else:
        ps = dict(panel.get('text_styles') or {})
        ps.update(new)
        panel['text_styles'] = ps
    return True


def _toggle_style(win, panel, element, key, value=None, delta=None):
    """Flip bold/italic or nudge the size of one element of one panel (or the figure)."""
    figcfg = win.spec['figure']
    owner = figcfg if panel is None else panel
    styles = dict(owner.get('text_styles') or {})
    st = dict(styles.get(element) or {})
    if delta is not None:
        base = T.resolve(figcfg, panel, element).get('size') or float(figcfg.get('font_size') or 11)
        st['size'] = max(4.0, float(base) + delta)
    elif value is None:
        resolved = T.resolve(figcfg, panel, element)
        default_bold = element in ('title', 'figure_title', 'letters')
        st[key] = not resolved.get(key, default_bold if key == 'bold' else False)
    else:
        st[key] = value
    styles[element] = st
    owner['text_styles'] = styles


def _submenu(menu, title):
    """A submenu parented to ``menu`` and kept alive with it."""
    sub = QMenu(title, menu)
    menu.addMenu(sub)
    keep = getattr(menu, '_fb_children', None)
    if keep is None:
        keep = []
        menu._fb_children = keep
    keep.append(sub)
    return sub


def _add(menu, text, slot, checked=None, enabled=True):
    act = QAction(text, menu)
    if checked is not None:
        act.setCheckable(True)
        act.setChecked(bool(checked))
    act.setEnabled(enabled)
    act.triggered.connect(lambda _=False: slot())
    menu.addAction(act)
    return act


def _data_coords(win, panel, fx, fy):
    """Data and axes-fraction coordinates of a click inside a panel's plot."""
    hd = win.last_report.artists.get(panel['id']) or {}
    ax = hd.get('ax')
    fig = win.last_fig
    if ax is None or fig is None:
        return None, None
    disp = fig.transFigure.transform((fx, 1 - fy))
    frac = ax.transAxes.inverted().transform(disp)
    try:
        data = ax.transData.inverted().transform(disp)
    except Exception:
        data = None
    return tuple(frac), (tuple(data) if data is not None else None)


def build_menu(win, hit: Hit | None, fx: float, fy: float) -> QMenu:
    """Right-click menu for whatever is under the cursor in the preview."""
    menu = QMenu(win)
    if hit is None or hit.element == 'figure_title' or not hit.panel_id:
        _page_menu(win, menu, fx, fy, hit)
        return menu
    panel = win.panel_by_id(hit.panel_id)
    if panel is None:
        _page_menu(win, menu, fx, fy, None)
        return menu
    letter = E.panel_letter(win.spec['panels'].index(panel), 'a')
    head = menu.addAction(f'Panel {letter} — {E.PANEL_KINDS.get(panel["kind"], panel["kind"])}')
    head.setEnabled(False)
    if hit.element == 'cbar':
        _cbar_menu(win, menu, panel)
        menu.addSeparator()
        sub = _submenu(menu, 'Tick labels')
        _text_menu(win, sub, panel, hit)
        sub = _submenu(menu, 'Panel')
        _panel_menu(win, sub, panel, fx, fy)
    elif hit.element not in ('plot', 'panel'):
        _text_menu(win, menu, panel, hit)
        if hit.element == 'cbar_label':
            menu.addSeparator()
            _cbar_menu(win, _submenu(menu, 'Colour bar'), panel)
        menu.addSeparator()
        sub = _submenu(menu, 'Panel')
        _panel_menu(win, sub, panel, fx, fy)
    else:
        _panel_menu(win, menu, panel, fx, fy)
    return menu


def _text_menu(win, menu, panel, hit):
    element = STYLE_ELEMENT.get(hit.element, hit.element)
    owner = None if hit.element in ('letters', 'figure_title') else panel
    name = ELEMENT_NAMES.get(hit.element, hit.element)
    if hit.element in TEXT_FIELDS or hit.element in ('annotation',) or (
            hit.element in ('ticks_x', 'ticks_y') and panel.get('kind') in RENAMEABLE):
        label = 'Rename items…' if hit.element.startswith('ticks') else f'Edit {name}…'
        _add(menu, label, lambda: win.after_edit(edit_text(win, hit)))
    if hit.element == 'legend':
        _legend_menu(win, menu, panel)
        menu.addSeparator()
    if hit.element == 'annotation':
        notes = panel.get('annotations') or []
        if 0 <= hit.index < len(notes):
            note = notes[hit.index]
            _add(menu, 'Bold', lambda: (note.update(bold=not note.get('bold')), win.after_edit(True)),
                 checked=note.get('bold'))
            _add(menu, 'Italic', lambda: (note.update(italic=not note.get('italic')), win.after_edit(True)),
                 checked=note.get('italic'))
            _add(menu, 'Box around text', lambda: (note.update(box=not note.get('box')), win.after_edit(True)),
                 checked=note.get('box'))
            _add(menu, 'Delete note', lambda: (notes.pop(hit.index), win.after_edit(True)))
        return
    resolved = T.resolve(win.spec['figure'], owner, element)
    default_bold = element in ('title', 'figure_title', 'letters')
    _add(menu, 'Bold', lambda: (_toggle_style(win, owner, element, 'bold'), win.after_edit(True)),
         checked=resolved.get('bold', default_bold))
    _add(menu, 'Italic', lambda: (_toggle_style(win, owner, element, 'italic'), win.after_edit(True)),
         checked=resolved.get('italic', False))
    _add(menu, 'Bigger', lambda: (_toggle_style(win, owner, element, 'size', delta=1.5), win.after_edit(True)))
    _add(menu, 'Smaller', lambda: (_toggle_style(win, owner, element, 'size', delta=-1.5), win.after_edit(True)))
    _add(menu, f'Text style of the {name}…',
         lambda: win.after_edit(style_dialog(win, owner, [element], f'Style — {name}')))

    def reset():
        target = win.spec['figure'] if owner is None else owner
        styles = dict(target.get('text_styles') or {})
        styles.pop(element, None)
        target['text_styles'] = styles
        if hit.element in TEXT_FIELDS and owner is not None:
            owner[TEXT_FIELDS[hit.element]] = ''
        win.after_edit(True)
    _add(menu, 'Reset to automatic', reset)


def _cbar_menu(win, menu, panel):
    """Position, size and colours of a panel's colour bar."""
    def setp(**kw):
        panel.update(**kw)
        win.after_edit(True)

    pos = _submenu(menu, 'Colour bar position')
    for key, label in E.CBAR_LOCATIONS.items():
        if key == 'custom' and panel.get('cbar_loc') != 'custom':
            continue
        _add(pos, label, lambda k=key: setp(cbar_loc=k), checked=(panel.get('cbar_loc') or 'right') == key)
    size = _submenu(menu, 'Colour bar length')
    for frac, label in ((0, 'Automatic'), (1.0, 'Full'), (0.75, '3/4'), (0.5, 'Half'), (0.33, 'Third')):
        _add(size, label, lambda f=frac: setp(cbar_length=f),
             checked=float(panel.get('cbar_length') or 0) == frac)
    width = float(panel.get('cbar_width') or 0.14)
    _add(menu, 'Thicker', lambda: setp(cbar_width=round(min(1.0, width * 1.3), 3)))
    _add(menu, 'Thinner', lambda: setp(cbar_width=round(max(0.04, width / 1.3), 3)))
    gap = float(panel.get('cbar_pad') if panel.get('cbar_pad') is not None else 0.12)
    _add(menu, 'Further from the plot', lambda: setp(cbar_pad=round(min(2.0, gap + 0.08), 3)))
    _add(menu, 'Closer to the plot', lambda: setp(cbar_pad=round(max(0.0, gap - 0.08), 3)))
    if panel.get('kind') != 'corr_matrix':
        cmaps = _submenu(menu, 'Colour map')
        for name in S.COLORMAPS:
            _add(cmaps, name, lambda n=name: setp(colormap=n), checked=panel.get('colormap') == name)
    _add(menu, 'Reverse colours', lambda: setp(reverse_cmap=not panel.get('reverse_cmap')),
         checked=panel.get('reverse_cmap'))
    if panel.get('kind') == 'scatter':
        _add(menu, 'Log colour scale', lambda: setp(cbar_log=not panel.get('cbar_log')),
             checked=panel.get('cbar_log'))
    _add(menu, 'Edit colour bar label…', lambda: win.after_edit(edit_text(
        win, Hit((0, 0, 0, 0), panel['id'], 'cbar_label', text=panel.get('cbar_label') or ''))))
    _add(menu, 'All colour bar options…', lambda: win.show_editor_tab('Style'))


def _legend_menu(win, menu, panel):
    _add(menu, 'Show legend', lambda: (panel.update(legend=not panel.get('legend', True)), win.after_edit(True)),
         checked=panel.get('legend', True))
    pos = _submenu(menu, 'Legend position')
    for key, label in S.LEGEND_LOCATIONS.items():
        _add(pos, label, lambda k=key: (panel.update(legend=True, legend_loc=k), win.after_edit(True)),
             checked=panel.get('legend_loc', 'best') == key)
    cols = _submenu(menu, 'Legend columns')
    for n in range(1, 6):
        _add(cols, str(n), lambda n=n: (panel.update(legend_cols=n), win.after_edit(True)),
             checked=int(panel.get('legend_cols') or 1) == n)
    _add(menu, 'Rename / recolour groups…', lambda: win.show_editor_tab('Groups'))


def _panel_menu(win, menu, panel, fx, fy):
    kind = panel['kind']
    types = _submenu(menu, 'Chart type')
    for key, label in E.PANEL_KINDS.items():
        _add(types, label, lambda k=key: win.set_panel_kind(panel, k), checked=kind == key)
    quantity = _submenu(menu, 'Quantity (unit)')
    _add(quantity, f'Figure default ({win.spec.get("data_type", "Counts")})',
         lambda: (panel.update(data_type=''), win.after_edit(True)), checked=not panel.get('data_type'))
    for key in DATA_TYPES:
        _add(quantity, key, lambda k=key: (panel.update(data_type=k), win.after_edit(True)),
             checked=panel.get('data_type') == key)
    group = _submenu(menu, 'Group / colour by')
    for key, label in E.GROUP_MODES.items():
        _add(group, label, lambda k=key: (panel.update(group_by=k), win.after_edit(True),
                                          win.show_editor_tab('Groups') if k == 'rules' else None),
             checked=panel.get('group_by', 'none') == key)
    menu.addSeparator()
    if kind in ('scatter', 'line', 'density', 'histogram', 'hexbin', 'contour', 'ridgeline'):
        _add(menu, 'Log X', lambda: (panel.update(log_x=not panel.get('log_x')), win.after_edit(True)),
             checked=panel.get('log_x'))
    if kind in XYISH or kind == 'combinations':
        _add(menu, 'Log Y', lambda: (panel.update(log_y=not panel.get('log_y')), win.after_edit(True)),
             checked=panel.get('log_y'))
    if any(panel.get(k) for k in ('x_min', 'x_max', 'y_min', 'y_max')):
        from results.figure_builder.ui.direct import reset_zoom
        _add(menu, 'Reset zoom', lambda: win.after_edit(reset_zoom(panel)))
    if kind in ('scatter', 'density'):
        def swap():
            panel['x'], panel['y'] = panel.get('y', ''), panel.get('x', '')
            panel['log_x'], panel['log_y'] = panel.get('log_y'), panel.get('log_x')
            panel['x_label'], panel['y_label'] = panel.get('y_label', ''), panel.get('x_label', '')
            win.after_edit(True)
        _add(menu, 'Swap X and Y', swap)
    if kind == 'scatter':
        _add(menu, 'Fit line', lambda: (panel.update(show_fit=not panel.get('show_fit')), win.after_edit(True)),
             checked=panel.get('show_fit'))
        extras = _submenu(menu, 'Extras')
        for key, value, label in (('ellipse', '2sd', '95% ellipse around each group'),
                                  ('ellipse', '1sd', '68% ellipse around each group'),
                                  ('trend', 'median', 'Running median curve'),
                                  ('marginals', 'hist', 'Histograms along the edges'),
                                  ('marginals', 'kde', 'Smooth curves along the edges'),
                                  ('marginals', 'box', 'Box plots along the edges')):
            on = panel.get(key) == value
            _add(extras, label, lambda k=key, v=value, o=on: (panel.update({k: 'none' if o else v}),
                                                               win.after_edit(True)), checked=on)
        _add(extras, 'Outline each group (hull)',
             lambda: (panel.update(hull=not panel.get('hull')), win.after_edit(True)), checked=panel.get('hull'))
        _add(extras, 'Zoom inset…', lambda: win.show_editor_tab('Axes'))
    if kind in ('corr_matrix', 'pairs'):
        method = _submenu(menu, 'Correlation')
        for key, label in (('pearson', 'Pearson'), ('spearman', 'Spearman'), ('kendall', 'Kendall')):
            _add(method, label, lambda k=key: (panel.update(corr_method=k), win.after_edit(True)),
                 checked=panel.get('corr_method', 'pearson') == key)
        _add(menu, 'Log values first', lambda: (panel.update(log_values=not panel.get('log_values')),
                                               win.after_edit(True)), checked=panel.get('log_values'))
    if kind in ('corr_matrix', 'heatmap', 'cooccurrence', 'composition', 'combinations'):
        _add(menu, 'Show values', lambda: (panel.update(annotate=not panel.get('annotate', True)),
                                          win.after_edit(True)), checked=panel.get('annotate', True))
    if kind in XYISH or kind in ('ternary', 'combinations'):
        _add(menu, 'Grid', lambda: (panel.update(grid=not panel.get('grid')), win.after_edit(True)),
             checked=panel.get('grid'))
    if kind in ('bar', 'combinations', 'composition'):
        _add(menu, 'Horizontal', lambda: (panel.update(horizontal=not panel.get('horizontal')),
                                         win.after_edit(True)), checked=panel.get('horizontal'))
    if kind not in ('text', 'code', 'box', 'violin', 'density', 'corr_matrix', 'heatmap', 'cooccurrence'):
        leg = _submenu(menu, 'Legend')
        _legend_menu(win, leg, panel)
    if kind in RENAMEABLE:
        _add(menu, 'Rename items…', lambda: win.after_edit(rename_items(win, panel)))
    menu.addSeparator()
    add = _submenu(menu, 'Add')
    frac, data = _data_coords(win, panel, fx, fy)

    def add_note(arrow=False):
        text, ok = QInputDialog.getText(win, 'Add note', 'Text:')
        if not ok or not text.strip():
            return
        notes = list(panel.get('annotations') or [])
        x, y = (frac if frac else (0.05, 0.9))
        note = {'text': text, 'x': f'{x:.3f}', 'y': f'{y:.3f}', 'coords': 'axes', 'size': 10.0,
                'color': '#222222'}
        if arrow:
            note.update(x=f'{min(0.95, x + 0.12):.3f}', y=f'{min(0.95, y + 0.12):.3f}',
                        arrow_x=f'{x:.3f}', arrow_y=f'{y:.3f}')
        notes.append(note)
        panel['annotations'] = notes
        win.after_edit(True)
    _add(add, 'Text here…', add_note)
    _add(add, 'Arrow pointing here…', lambda: add_note(True))
    if data is not None and kind in XYISH:
        _add(add, f'Horizontal line at y = {data[1]:.3g}',
             lambda: (panel.update(hlines=', '.join(filter(None, [panel.get('hlines', ''), f'{data[1]:.4g}']))),
                      win.after_edit(True)))
        if kind in ('scatter', 'line', 'density', 'histogram'):
            _add(add, f'Vertical line at x = {data[0]:.3g}',
                 lambda: (panel.update(vlines=', '.join(filter(None, [panel.get('vlines', ''), f'{data[0]:.4g}']))),
                          win.after_edit(True)))
    if kind in SHAPEABLE:
        add.addSeparator()
        _shape_items(win, add, panel, data)
    menu.addSeparator()
    _add(menu, 'Text styles of this panel…',
         lambda: win.after_edit(style_dialog(win, panel, T.KIND_ELEMENTS.get(kind, list(T.PANEL_ELEMENTS)),
                                             'Text styles — this panel')))
    _add(menu, 'Edit all settings…', lambda: win.show_editor_tab('Data'))
    menu.addSeparator()
    _add(menu, 'Duplicate', lambda: win.duplicate_panel(panel))
    _add(menu, 'Bring to front', lambda: win.restack_panel(panel, True))
    _add(menu, 'Send to back', lambda: win.restack_panel(panel, False))
    _add(menu, 'Delete panel', lambda: win.delete_panel(panel))


SHAPEABLE = {'scatter', 'line', 'density', 'hexbin', 'contour', 'histogram', 'box', 'violin',
             'strip', 'bar', 'combinations', 'composition', 'ridgeline'}


def _add_shape(win, panel, **shape):
    base = {'type': 'xband', 'color': '#9ca3af', 'alpha': 0.3, 'hatch': '', 'style': '--',
            'layer': 'back', 'label': ''}
    base.update(shape)
    panel['shapes'] = list(panel.get('shapes') or []) + [base]
    win.after_edit(True)


def _ask_range(win, title, suggestion):
    text, ok = QInputDialog.getText(win, title, 'From, to (leave one empty to run to the edge):',
                                    text=suggestion)
    if not ok:
        return None
    parts = [p.strip() for p in text.replace(';', ',').split(',')]
    parts += [''] * (2 - len(parts))
    return parts[0], parts[1]


def _shape_items(win, menu, panel, data):
    """Right-click entries that add grey areas and reference lines to a panel."""
    hd = win.last_report.artists.get(panel['id']) or {}
    ax = hd.get('ax')
    xs = ys = ('', '')
    if ax is not None:
        x0, x1 = sorted(ax.get_xlim())
        y0, y1 = sorted(ax.get_ylim())
        if data is not None:
            cx, cy = data
            if ax.get_xscale() == 'log' and cx > 0:
                xs = (f'{cx / 1.5:.4g}', f'{cx * 1.5:.4g}')
            else:
                w = (x1 - x0) * 0.1
                xs = (f'{cx - w:.4g}', f'{cx + w:.4g}')
            if ax.get_yscale() == 'log' and cy > 0:
                ys = (f'{cy / 1.5:.4g}', f'{cy * 1.5:.4g}')
            else:
                h = (y1 - y0) * 0.1
                ys = (f'{cy - h:.4g}', f'{cy + h:.4g}')

    def x_band():
        r = _ask_range(win, 'Grey area over an X range', f'{xs[0]}, {xs[1]}')
        if r:
            _add_shape(win, panel, type='xband', x1=r[0], x2=r[1])

    def y_band():
        r = _ask_range(win, 'Grey area over a Y range', f'{ys[0]}, {ys[1]}')
        if r:
            _add_shape(win, panel, type='yband', y1=r[0], y2=r[1])
    _add(menu, 'Grey area over an X range…', x_band)
    _add(menu, 'Grey area over a Y range…', y_band)
    if data is not None:
        _add(menu, f'Grey area left of x = {data[0]:.3g}',
             lambda: _add_shape(win, panel, type='xband', x1='', x2=f'{data[0]:.6g}'))
        _add(menu, f'Grey area below y = {data[1]:.3g}',
             lambda: _add_shape(win, panel, type='yband', y1='', y2=f'{data[1]:.6g}'))
    if panel.get('kind') in ('scatter', 'density', 'hexbin', 'contour'):
        _add(menu, 'Line y = x', lambda: _add_shape(win, panel, type='line', slope='1', intercept='0',
                                                    color='#374151', alpha=0.8, style='--'))
    _add(menu, 'All grey areas and lines…', lambda: win.show_editor_tab('Shapes'))
    if panel.get('shapes'):
        _add(menu, 'Remove all grey areas and lines',
             lambda: (panel.update(shapes=[]), win.after_edit(True)))


def _page_menu(win, menu, fx, fy, hit):
    if hit is not None and hit.element == 'figure_title':
        _add(menu, 'Edit figure title…', lambda: win.after_edit(edit_text(win, hit)))
        _add(menu, 'Text style of the figure title…',
             lambda: win.after_edit(style_dialog(win, None, ['figure_title'], 'Style — figure title')))
        menu.addSeparator()
    add = _submenu(menu, 'Add panel here')
    for key, label in E.PANEL_KINDS.items():
        _add(add, label, lambda k=key: win.add_panel(k, at=(fx, fy)))
    _add(menu, 'Chart gallery…', win.open_gallery)
    _add(menu, 'Surprise me', win.surprise)
    layouts = _submenu(menu, 'Layouts')
    for name in S.TEMPLATES:
        _add(layouts, name, lambda n=name: win.apply_layout(n))
    style = _submenu(menu, 'Style')
    for name in S.STYLE_PRESETS:
        _add(style, name, lambda n=name: win.apply_style(n))
    _add(menu, 'Figure title…', lambda: win.after_edit(edit_text(win, Hit((0, 0, 0, 0), '', 'figure_title'))))
    _add(menu, 'Text styles of the whole figure…',
         lambda: win.after_edit(style_dialog(win, None, list(T.ALL_ELEMENTS), 'Text styles — whole figure')))
    _add(menu, 'Figure settings…', win.open_figure_settings)
