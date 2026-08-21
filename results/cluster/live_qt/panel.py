"""The control panel, the settings dialog and the algorithm parameter widgets.

Everything here emits Qt signals rather than calling the controller directly,
so the widget tree has no opinion about where the data comes from and
``live.py`` keeps one place where config changes are pushed and runs are
scheduled.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFrame,
                               QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QSlider, QTabWidget, QVBoxLayout, QWidget)

from .legend import _glyph_pixmap
from .state import (SHAPE_LABELS, SHAPES, THEME, cluster_tag,
                    element_label_text)

FONT_FAMILIES = [
    ('System default', ''),
    ('Helvetica / Arial', 'Helvetica'),
    ('Times New Roman', 'Times New Roman'),
    ('Georgia', 'Georgia'),
    ('Verdana', 'Verdana'),
    ('Palatino', 'Palatino'),
    ('Courier New', 'Courier New'),
]

PROJ_HINTS = {
    'PCA': 'Linear, fast and reproducible; axes carry an explained-variance '
           'share.',
    't-SNE': 'Non-linear: preserves local neighbourhoods, so tight groups '
             'separate. Slower, and distances between groups mean little.',
    'UMAP': 'Non-linear: keeps local and some global structure, usually faster '
            'than t-SNE.',
    'None': 'No reduction — plot two raw element channels directly.',
}


def _hint(text):
    """Build a small explanatory line under a control.

    Named so :meth:`ControlPanel.apply_theme` can restyle every one of them on
    a dark/light switch without tracking them individually.

    Args:
        text (str): Hint text.

    Returns:
        QLabel: The hint label.
    """
    l = QLabel(text)
    l.setObjectName('hint')
    l.setWordWrap(True)
    return l


def _header(text):
    """Build a section header label.

    Args:
        text (str): Header text.

    Returns:
        QLabel: The header label.
    """
    l = QLabel(text)
    l.setObjectName('sectionHeader')
    return l


class Collapsible(QWidget):
    """A section that folds away behind a caret.

    Keeps the settings dialog a fixed size: the swatch grid and the per-sample
    shape rows both grow with the dataset, and left expanded they push the
    dialog taller every time it is opened.
    """

    def __init__(self, title, expanded=False, parent=None):
        """Build a folded section.

        Args:
            title (str): Header text.
            expanded (bool): Start open rather than folded.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        self.header = QPushButton(('▾  ' if expanded else '▸  ') + title)
        self.header.setObjectName('collapseHead')
        self.header.setCheckable(True)
        self.header.setChecked(expanded)
        self.header.setCursor(Qt.PointingHandCursor)
        self._title = title
        self.header.toggled.connect(self._on_toggled)
        lay.addWidget(self.header)

        self.body = QWidget()
        self.box = QVBoxLayout(self.body)
        self.box.setContentsMargins(10, 2, 0, 6)
        self.box.setSpacing(6)
        self.body.setVisible(expanded)
        lay.addWidget(self.body)

    def _on_toggled(self, on):
        """Fold or unfold the body and flip the caret.

        Args:
            on (bool): Whether the section is open.
        """
        self.header.setText(('▾  ' if on else '▸  ') + self._title)
        self.body.setVisible(on)

    def add(self, w):
        """Append a widget to the section body.

        Args:
            w (QWidget): The widget.

        Returns:
            QWidget: The same widget, for chaining.
        """
        self.box.addWidget(w)
        return w


class _Field(QWidget):
    """A label, a control and an optional hint, stacked."""

    def __init__(self, label=None):
        """Build the field.

        Args:
            label (str | None): Label text, or None for a bare control.
        """
        super().__init__()
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(3)
        self.label = None
        self.value = None
        if label is not None:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            self.label = QLabel(label)
            self.label.setObjectName('fieldLabel')
            row.addWidget(self.label)
            row.addStretch(1)
            self.value = QLabel('')
            self.value.setObjectName('fieldValue')
            row.addWidget(self.value)
            self.box.addLayout(row)
        self._hint = None
        self._inert = None

    def add(self, w):
        """Append a control to the field.

        Args:
            w (QWidget): The control.

        Returns:
            QWidget: The same control, for chaining.
        """
        self.box.addWidget(w)
        return w

    def set_hint(self, text):
        """Set or replace the explanatory line under the control.

        Args:
            text (str): Hint text.
        """
        if self._hint is None:
            self._hint = _hint(text)
            self.box.addWidget(self._hint)
        else:
            self._hint.setText(text)

    def set_inert(self, off, why=''):
        """Grey out a parameter this illustration cannot honour.

        Args:
            off (bool): Whether to disable the field.
            why (str): Short reason, shown under the control.
        """
        self.setEnabled(not off)
        if off:
            if self._inert is None:
                self._inert = _hint(why)
                self._inert.setStyleSheet(
                    'color:%s;font-size:10px;font-style:italic;' % THEME.muted)
                self.box.addWidget(self._inert)
            else:
                self._inert.setText(why)
                self._inert.setVisible(True)
        elif self._inert is not None:
            self._inert.setVisible(False)


class AlgoParams(QWidget):
    """Parameter widgets for the selected algorithm."""

    changed = Signal(str, object)

    def __init__(self, S, parent=None):
        """Build an empty parameter block.

        Args:
            S (LiveState): The view state, for the schema and current values.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self.S = S
        self._fields = {}
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(8)

    def build(self):
        """Rebuild the widgets for the current algorithm."""
        S = self.S
        while self.box.count():
            w = self.box.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._fields = {}
        spec = ((S.schema or {}).get('algorithms') or {}).get(S.algo)
        if not spec:
            return
        S.params = {}
        vals = (S.param_values or {}).get(S.algo, {})

        for p in spec.get('params', []):
            v = vals.get(p['key'], p.get('default'))
            S.params[p['key']] = v
            kind = p.get('type')
            if kind == 'choice':
                f = self._choice(p, v)
            elif kind == 'bool':
                f = self._bool(p, v)
            else:
                f = self._range(p, v)
            self._fields[p['key']] = f
            self.box.addWidget(f)
        self.sync_availability()

    def _emit(self, key, value):
        """Record a parameter change, re-check availability and announce it.

        Args:
            key (str): Engine parameter key.
            value: The new value.
        """
        self.S.params[key] = value
        self.sync_availability()
        self.changed.emit(key, value)

    def _bool(self, p, val):
        """Build a checkbox for a boolean parameter.

        Args:
            p (dict): The parameter spec from the schema.
            val: Current value.

        Returns:
            _Field: The wrapped control.
        """
        f = _Field()
        cb = QCheckBox(p.get('label') or p['key'])
        cb.setChecked(bool(val))
        cb.toggled.connect(lambda v, k=p['key']: self._emit(k, bool(v)))
        f.add(cb)
        if p.get('help'):
            f.set_hint(p['help'])
        return f

    def _range(self, p, val):
        """Build a slider for a numeric parameter.

        ``QSlider`` is integer-only, so a float parameter rides on a scaled
        integer track and is converted back on the way out.

        Args:
            p (dict): The parameter spec from the schema.
            val: Current value.

        Returns:
            _Field: The wrapped control.
        """
        is_int = p.get('type') == 'int'
        cur = val if val is not None else p.get('default')
        f = _Field(p.get('label') or p['key'])
        step = p.get('step') or (1 if is_int else 0.01)
        lo, hi = p.get('min', 0), p.get('max', 1)
        mul = 1 if is_int else int(round(1 / step))
        s = QSlider(Qt.Horizontal)
        s.setRange(int(round(lo * mul)), int(round(hi * mul)))
        s.setSingleStep(max(1, int(round(step * mul))))
        s.setValue(int(round((cur or 0) * mul)))
        f.value.setText(str(cur if is_int else round(float(cur or 0), 2)))

        def on_change(raw, key=p['key'], m=mul, ii=is_int, fld=f):
            """Convert the integer track back to the parameter value.

            Args:
                raw (int): Slider position.
                key (str): Engine parameter key.
                m (int): Scale factor between slider and value.
                ii (bool): Whether the parameter is an integer.
                fld (_Field): The field showing the readout.
            """
            v = int(raw / m) if ii else round(raw / m, 4)
            fld.value.setText(str(v) if ii else ('%.2f' % v))
            self._emit(key, v)

        s.valueChanged.connect(on_change)
        f.add(s)
        if p.get('help'):
            f.set_hint(p['help'])
        return f

    def _choice(self, p, val):
        """Build a dropdown for a categorical parameter.

        Args:
            p (dict): The parameter spec from the schema.
            val: Current value.

        Returns:
            _Field: The wrapped control.
        """
        f = _Field(p.get('label') or p['key'])
        c = QComboBox()
        opts = [str(o) for o in p.get('options', [])]
        c.addItems(opts)
        want = str(val if val is not None else p.get('default'))
        if want in opts:
            c.setCurrentText(want)
        c.currentTextChanged.connect(lambda v, k=p['key']: self._emit(k, v))
        f.add(c)
        if p.get('help'):
            f.set_hint(p['help'])
        return f

    def sync_availability(self):
        """Grey out parameters the current configuration does not read.

        Two cases: a parameter this algorithm ignores, and one whose relevance
        depends on another — the distance metric under Ward linkage, for
        instance. Both stay visible with a reason rather than sitting there
        looking active while changing nothing.
        """
        S = self.S
        spec = ((S.schema or {}).get('algorithms') or {}).get(S.algo)
        if not spec:
            return
        for p in spec.get('params', []):
            f = self._fields.get(p['key'])
            if f is None:
                continue
            off = p.get('applies') is False
            why = 'not used by this algorithm' if off else ''
            only_if = p.get('only_if')
            if not off and only_if:
                other = S.params.get(only_if.get('key'))
                if any(str(v) == str(other) for v in (only_if.get('not') or [])):
                    off = True
                    why = 'not applicable with %s = %s' % (only_if['key'], other)
            f.set_inert(off, why)


class ControlPanel(QWidget):
    """The panel holding the Data, View and Algorithm sections."""

    config_changed = Signal(dict)
    projection_changed = Signal(str, int)
    algorithm_changed = Signal(str)
    param_changed = Signal(str, object)
    run_clicked = Signal()
    overlay_changed = Signal(str)
    colormap_changed = Signal(str)
    biplot_changed = Signal()

    def __init__(self, S, parent=None):
        """Build every section.

        Args:
            S (LiveState): The view state to reflect and update.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self.S = S
        self._loading = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(11, 11, 11, 11)
        lay.setSpacing(7)
        scroll.setWidget(body)

        self.var_info = QLabel('PCA view')
        self.var_info.setObjectName('hint')
        self.var_info.setWordWrap(True)
        lay.addWidget(self.var_info)

        lay.addWidget(_header('DATA'))
        self.data_type = QComboBox()
        self.data_type.currentTextChanged.connect(
            lambda v: self._push({'data_type': v}))
        f = _Field('Data type')
        f.add(self.data_type)
        lay.addWidget(f)

        self.scaling = QComboBox()
        self.scaling.currentTextChanged.connect(
            lambda v: self._push({'scaling': v}))
        f = _Field('Scaling')
        f.add(self.scaling)
        f.set_hint('CLR is the compositional default for particle data.')
        lay.addWidget(f)

        self.filter_zeros = QCheckBox('Drop all-zero particles')
        self.filter_zeros.setChecked(True)
        self.filter_zeros.toggled.connect(
            lambda v: self._push({'filter_zeros': bool(v)}))
        lay.addWidget(self.filter_zeros)

        self.min_type = QSlider(Qt.Horizontal)
        self.min_type.setRange(1, 100)
        self.min_type.setValue(5)
        f = _Field('Min particles / type')
        f.value.setText('5')
        self._min_type_field = f
        self.min_type.valueChanged.connect(self._on_min_type)
        f.add(self.min_type)
        f.set_hint('Drop particle types rarer than this before clustering.')
        lay.addWidget(f)

        lay.addWidget(_header('VIEW'))
        self.proj = QComboBox()
        self.proj.currentTextChanged.connect(lambda _: self._on_projection())
        f = _Field('Projection')
        f.add(self.proj)
        self.proj_hint = _hint(PROJ_HINTS['PCA'])
        f.box.addWidget(self.proj_hint)
        lay.addWidget(f)

        self.biplot_field = _Field()
        self.biplot_on = QCheckBox('Element arrows (biplot)')
        self.biplot_on.setChecked(True)
        self.biplot_on.toggled.connect(self._on_biplot_on)
        self.biplot_field.add(self.biplot_on)
        self.biplot_field.set_hint(
            'Each arrow points the way particles rich in that element lie, and '
            'its length is how much that element drives the components on '
            'screen. The sliders set how many are drawn and how far the '
            'longest one reaches.')
        self.biplot_n_label = QLabel('Arrows shown')
        self.biplot_n_label.setObjectName('fieldLabel')
        self.biplot_field.add(self.biplot_n_label)
        self.biplot_n = QSlider(Qt.Horizontal)
        self.biplot_n.setRange(1, 30)
        self.biplot_n.setValue(8)
        self.biplot_n.valueChanged.connect(self._on_biplot_n)
        self.biplot_field.add(self.biplot_n)
        self.biplot_len_label = QLabel('Arrow length')
        self.biplot_len_label.setObjectName('fieldLabel')
        self.biplot_field.add(self.biplot_len_label)
        self.biplot_len = QSlider(Qt.Horizontal)
        self.biplot_len.setRange(10, 120)
        self.biplot_len.setValue(42)
        self.biplot_len.valueChanged.connect(self._on_biplot_len)
        self.biplot_field.add(self.biplot_len)
        lay.addWidget(self.biplot_field)

        self.overlay = QComboBox()
        self.overlay.currentIndexChanged.connect(self._on_overlay)
        f = _Field('Colour by element')
        f.add(self.overlay)
        f.set_hint('Shades every particle by how much of that element it holds. '
                   'Works on any projection, so it answers what the PCA arrows '
                   'answer even on t-SNE and UMAP.')
        lay.addWidget(f)

        self.cmap_field = _Field('Colormap')
        self.cmap = QComboBox()
        self.cmap.currentTextChanged.connect(self._on_cmap)
        self.cmap_field.add(self.cmap)
        from .legend import ColorBar
        self.cmap_bar = ColorBar(S)
        self.cmap_field.add(self.cmap_bar)
        lay.addWidget(self.cmap_field)

        self.dims = QComboBox()
        self.dims.addItems(['2D', '3D'])
        self.dims.currentIndexChanged.connect(lambda _: self._on_projection())
        f = _Field('Dimensions')
        f.add(self.dims)
        self.dims_hint = _hint('Drag to rotate · scroll to zoom')
        f.box.addWidget(self.dims_hint)
        self.dims_hint.setVisible(False)
        lay.addWidget(f)

        lay.addWidget(_header('ALGORITHM'))
        self.algo = QComboBox()
        self.algo.currentTextChanged.connect(self._on_algo)
        lay.addWidget(self.algo)

        self.blurb = QLabel('')
        self.blurb.setObjectName('blurb')
        self.blurb.setWordWrap(True)
        lay.addWidget(self.blurb)

        self.params = AlgoParams(S)
        self.params.changed.connect(self.param_changed)
        lay.addWidget(self.params)

        self.run_btn = QPushButton('▶  Cluster')
        self.run_btn.setObjectName('runBtn')
        self.run_btn.clicked.connect(self.run_clicked)
        lay.addWidget(self.run_btn)

        lay.addStretch(1)
        self.apply_theme()

    def apply_theme(self):
        """Restyle for the active palette.

        One stylesheet keyed on object name rather than per-widget calls, so a
        control added later inherits the right colours automatically instead of
        silently keeping whichever mode was active when it was built.
        """
        self.setStyleSheet(
            'QWidget{background:%(panel)s;color:%(text)s;}'
            'QLabel#hint{color:%(muted)s;font-size:10px;}'
            'QLabel#sectionHeader{color:%(muted)s;font-size:10px;'
            'font-weight:600;letter-spacing:.06em;margin-top:8px;}'
            'QLabel#fieldLabel{color:%(text)s;font-size:11px;}'
            'QLabel#fieldValue{color:%(muted)s;font-size:11px;}'
            'QLabel#blurb{color:%(muted)s;font-size:10px;background:%(chip)s;'
            'border-radius:6px;padding:7px;}'
            'QPushButton#runBtn{background:%(accent)s;color:#fff;border:none;'
            'border-radius:6px;padding:8px;font-weight:600;}'
            'QComboBox{background:%(chip)s;color:%(text)s;border:1px solid '
            '%(stroke)s;border-radius:5px;padding:3px 6px;}'
            'QCheckBox{color:%(text)s;font-size:11px;}'
            % {'panel': THEME.panel, 'text': THEME.text, 'muted': THEME.muted,
               'chip': THEME.chip, 'accent': THEME.accent,
               'stroke': THEME.stroke})
        self.cmap_bar.update()

    def _push(self, patch):
        """Announce a config change unless the controls are being populated.

        Args:
            patch (dict): The keys that changed.
        """
        if not self._loading:
            self.config_changed.emit(patch)

    def _on_min_type(self, v):
        """Update the readout and push the rare-type threshold.

        Args:
            v (int): Minimum particles per type.
        """
        self._min_type_field.value.setText(str(v))
        self._push({'min_particle_type_count': int(v)})

    def _on_projection(self):
        """Push the projection method and dimensionality together.

        Both controls route here because the backend re-projects on either.
        """
        if self._loading:
            return
        self._update_proj_hint()
        dims = 3 if self.dims.currentIndex() == 1 else 2
        self.dims_hint.setVisible(dims == 3)
        self.projection_changed.emit(self.proj.currentText(), dims)

    def _on_algo(self, name):
        """Adopt a new algorithm, rebuild its parameters and announce it.

        Args:
            name (str): Algorithm name.
        """
        if self._loading or not name:
            return
        self.S.algo = name
        self.params.build()
        self._set_blurb()
        self.algorithm_changed.emit(name)

    def _on_overlay(self, _idx):
        """Adopt the colour-by-element choice and show or hide the colormap.

        Args:
            _idx (int): Unused; the element key is read from the combo data.
        """
        if self._loading:
            return
        key = self.overlay.currentData() or ''
        self.S.ui.overlay_el = key
        self.cmap_field.setVisible(bool(key))
        self.overlay_changed.emit(key)

    def _on_cmap(self, name):
        """Adopt a new overlay colormap and repaint the preview strip.

        Args:
            name (str): Colormap name.
        """
        if self._loading or not name:
            return
        self.S.ui.overlay_cmap = name
        self.cmap_bar.update()
        self.colormap_changed.emit(name)

    def _on_biplot_on(self, v):
        """Toggle the element arrows.

        Args:
            v (bool): Whether the arrows are drawn.
        """
        self.S.ui.biplot_on = bool(v)
        self.biplot_changed.emit()

    def _on_biplot_n(self, v):
        """Set how many element arrows are drawn.

        Args:
            v (int): Number of arrows, longest first.
        """
        self.biplot_n_label.setText('Arrows shown: %d' % int(v))
        self.S.ui.biplot_n = int(v)
        self.biplot_changed.emit()

    def _on_biplot_len(self, v):
        """Set how far the longest element arrow reaches.

        The value is a percentage of the visible cloud's span, applied to the
        longest arrow; the rest keep their length relative to it, so shortening
        them to uncover the points never distorts what they say.

        Args:
            v (int): Percentage of the cloud span, 10 to 120.
        """
        self.biplot_len_label.setText('Arrow length: %d%%' % int(v))
        self.S.ui.biplot_len = max(0.05, int(v) / 100.0)
        self.biplot_changed.emit()

    def _set_blurb(self):
        """Show the current algorithm's one-line description from the schema."""
        spec = ((self.S.schema or {}).get('algorithms') or {}).get(self.S.algo)
        self.blurb.setText((spec or {}).get('blurb', ''))

    def build_from_schema(self):
        """Fill every dropdown from the schema."""
        S = self.S
        schema = S.schema or {}
        self._loading = True
        try:
            self.algo.clear()
            self.algo.addItems(list((schema.get('algorithms') or {}).keys()))
            if S.algo:
                self.algo.setCurrentText(S.algo)
            self.scaling.clear()
            self.scaling.addItems(schema.get('scalings')
                                  or ['CLR', 'ILR', 'Robust Z-score', 'None'])
            self.data_type.clear()
            self.data_type.addItems(schema.get('data_types') or ['Counts'])
            self._fill_projections(schema.get('projections'), S.proj)
            self._fill_colormaps()
        finally:
            self._loading = False
        self.params.build()
        self._set_blurb()

    def _fill_projections(self, opts, val):
        """List every projection method, disabling any that is unavailable.

        An unavailable method stays listed but disabled and labelled with the
        reason, so the choice is visible rather than silently gone.

        Args:
            opts (list | None): Schema entries or bare names.
            val (str): Method to preselect.
        """
        S = self.S
        self.proj.clear()
        entries = [{'name': o, 'available': True, 'reason': ''}
                   if isinstance(o, str) else o
                   for o in (opts or ['PCA', 't-SNE', 'UMAP', 'None'])]
        S.proj_info = {}
        for i, o in enumerate(entries):
            S.proj_info[o['name']] = o
            label = o['name'] if o.get('available') else o['name'] + ' — unavailable'
            self.proj.addItem(label, o['name'])
            if not o.get('available'):
                self.proj.model().item(i).setEnabled(False)
            if o.get('reason'):
                self.proj.setItemData(i, o['reason'], Qt.ToolTipRole)
        info = S.proj_info.get(val)
        pick = val if (info and info.get('available')) else 'PCA'
        idx = self.proj.findData(pick)
        if idx >= 0:
            self.proj.setCurrentIndex(idx)
        S.proj = pick
        self._update_proj_hint()

    def _update_proj_hint(self):
        """Describe the selected projection, or say why it is unavailable."""
        name = self.proj.currentData() or self.proj.currentText()
        info = (self.S.proj_info or {}).get(name)
        if info and not info.get('available'):
            self.proj_hint.setText(info.get('reason', '') + ' — PCA is used instead.')
        else:
            self.proj_hint.setText(PROJ_HINTS.get(name, ''))

    def _fill_colormaps(self):
        """Fill the colormap dropdown from the list the backend sampled."""
        S = self.S
        schema = S.schema or {}
        names = schema.get('colormap_order') or list(
            (schema.get('colormaps') or {}).keys())
        if not names:
            return
        if S.ui.overlay_cmap not in names:
            S.ui.overlay_cmap = names[0]
        self.cmap.clear()
        self.cmap.addItems(names)
        self.cmap.setCurrentText(S.ui.overlay_cmap)
        self.cmap_bar.update()

    def build_overlay_picker(self):
        """Repopulate the colour-by-element dropdown from the element list.

        The selection survives a data change when the element is still present
        and is dropped when it is not, so changing the isotope set never leaves
        the plot coloured by something that is no longer there.
        """
        S = self.S
        els = list((S.data or {}).get('elements') or [])
        if S.ui.overlay_el and S.ui.overlay_el not in els:
            S.ui.overlay_el = ''
        self._loading = True
        try:
            self.overlay.clear()
            self.overlay.addItem('Off — colour by cluster', '')
            for e in els:
                self.overlay.addItem(element_label_text(e, S.ui.label_mode), e)
            idx = self.overlay.findData(S.ui.overlay_el)
            self.overlay.setCurrentIndex(max(0, idx))
        finally:
            self._loading = False
        self.cmap_field.setVisible(bool(S.ui.overlay_el))

    def update_biplot_availability(self):
        """Show the biplot controls only for a PCA of the element columns.

        The arrows only exist there, so the field is hidden for the embeddings,
        for the raw-axis view, and for ILR scaling, where the columns are
        balances rather than elements.
        """
        d = self.S.data or {}
        ok = d.get('projection') == 'PCA' and d.get('loadings') is not None
        self.biplot_field.setVisible(bool(ok))
        els = d.get('elements')
        if ok and els:
            self.biplot_n.setMaximum(max(2, len(els)))
        self.biplot_n_label.setText('Arrows shown: %d' % self.biplot_n.value())
        self.biplot_len_label.setText(
            'Arrow length: %d%%' % self.biplot_len.value())

    def reflect_config(self, state):
        """Push the shared node config into the controls.

        Args:
            state (dict): The state payload from the controller.
        """
        S = self.S
        c = (state or {}).get('config') or {}
        self._loading = True
        try:
            if c.get('scaling'):
                self.scaling.setCurrentText(c['scaling'])
            if c.get('data_type'):
                self.data_type.setCurrentText(c['data_type'])
            if c.get('filter_zeros') is not None:
                self.filter_zeros.setChecked(bool(c['filter_zeros']))
            if c.get('min_particle_type_count') is not None:
                v = int(c['min_particle_type_count'])
                self.min_type.setValue(v)
                self._min_type_field.value.setText(str(v))
            if state.get('algorithm'):
                self.algo.setCurrentText(state['algorithm'])
            if state.get('projection'):
                info = (S.proj_info or {}).get(state['projection'])
                if not info or info.get('available'):
                    idx = self.proj.findData(state['projection'])
                    if idx >= 0:
                        self.proj.setCurrentIndex(idx)
                self._update_proj_hint()
            if state.get('dims'):
                self.dims.setCurrentIndex(1 if int(state['dims']) == 3 else 0)
                self.dims_hint.setVisible(int(state['dims']) == 3)
            if c.get('label_mode'):
                S.ui.label_mode = c['label_mode']
            if c.get('display_max_isotopes') is not None:
                S.ui.max_iso = max(1, int(c['display_max_isotopes']))
            if c.get('display_min_pct') is not None:
                S.ui.min_pct = max(0.0, float(c['display_min_pct']))
        finally:
            self._loading = False

    def set_var_info(self, text):
        """Set the summary line above the Data section.

        Args:
            text (str): Projection, dimensions, particle count and elements.
        """
        self.var_info.setText(text)


class SettingsDialog(QDialog):
    """Plot settings: Appearance, Boxes, Export and Info."""

    appearance_changed = Signal()
    reset_colors = Signal()
    reset_shapes = Signal()
    reset_boxes = Signal()
    sample_shape_changed = Signal(str, str)
    label_mode_changed = Signal(str)
    export_plot = Signal()
    export_inset = Signal()
    boxes_toggled = Signal()

    def __init__(self, S, parent=None):
        """Build the four settings tabs.

        Args:
            S (LiveState): The view state to read and update.
            parent (QWidget | None): Parent widget.
        """
        super().__init__(parent)
        self.S = S
        self.setWindowTitle('Plot settings')
        self.resize(520, 560)
        self._loading = False

        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)
        self.tabs.addTab(self._scrolled(self._appearance_tab()), 'Appearance')
        self.tabs.addTab(self._scrolled(self._boxes_tab()), 'Boxes')
        self.tabs.addTab(self._scrolled(self._export_tab()), 'Export')
        self.tabs.addTab(self._scrolled(self._info_tab()), 'Info')
        self.setStyleSheet(
            'QPushButton#collapseHead{text-align:left;border:none;'
            'background:transparent;font-weight:600;padding:4px 0;}')

    @staticmethod
    def _scrolled(page):
        """Wrap a tab page in a scroll area.

        A section that grows with the dataset then scrolls inside a dialog of
        constant size, rather than making the dialog taller each time it opens.

        Args:
            page (QWidget): The tab page.

        Returns:
            QScrollArea: The wrapped page.
        """
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setWidget(page)
        return sc

    def _appearance_tab(self):
        """Build the Appearance tab: fonts, sizes, colours and marker shapes.

        Returns:
            QWidget: The tab page.
        """
        S = self.S
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(9)

        self.font_family = QComboBox()
        for label, fam in FONT_FAMILIES:
            self.font_family.addItem(label, fam)
        i = self.font_family.findData(S.ui.font)
        self.font_family.setCurrentIndex(max(0, i))
        self.font_family.currentIndexChanged.connect(self._on_font_family)
        f = _Field('Font family')
        f.add(self.font_family)
        f.set_hint('Families not installed on this computer fall back to the '
                   'system font.')
        lay.addWidget(f)

        self.font_size = QSlider(Qt.Horizontal)
        self.font_size.setRange(16, 48)
        self.font_size.setValue(int(S.ui.font_size * 2))
        f = _Field('Font size')
        f.value.setText(str(S.ui.font_size))
        self._fs_field = f
        self.font_size.valueChanged.connect(self._on_font_size)
        f.add(self.font_size)
        f.set_hint('8 to 24 px.')
        lay.addWidget(f)

        f = _Field('Font style')
        srow = QWidget()
        sh = QHBoxLayout(srow)
        sh.setContentsMargins(0, 0, 0, 0)
        sh.setSpacing(14)
        self.font_bold = QCheckBox('Bold')
        self.font_italic = QCheckBox('Italic')
        self.font_bold.setChecked('bold' in (S.ui.font_style or ''))
        self.font_italic.setChecked('italic' in (S.ui.font_style or ''))
        self.font_bold.toggled.connect(self._on_font_style)
        self.font_italic.toggled.connect(self._on_font_style)
        sh.addWidget(self.font_bold)
        sh.addWidget(self.font_italic)
        sh.addStretch(1)
        f.add(srow)
        f.set_hint('Applies to the axis captions, tick numbers and the '
                   'detail-view text. Both can be on together.')
        lay.addWidget(f)

        self.label_mode = QComboBox()
        self.label_mode.addItems(['Symbol', 'Mass + Symbol', 'Atomic Notation'])
        self.label_mode.setCurrentText(S.ui.label_mode)
        self.label_mode.currentTextChanged.connect(self._on_label_mode)
        f = _Field('Element labels')
        f.add(self.label_mode)
        f.set_hint('Same three styles as the clustering figures.')
        lay.addWidget(f)

        self.point_size = QSlider(Qt.Horizontal)
        self.point_size.setRange(0, 28)
        self.point_size.setValue(int(S.ui.point_size * 2))
        f = _Field('Node size')
        f.value.setText('auto')
        self._ps_field = f
        self.point_size.valueChanged.connect(self._on_point_size)
        f.add(self.point_size)
        f.set_hint('0 = auto by particle count.')
        lay.addWidget(f)

        self.cent_size = QSlider(Qt.Horizontal)
        self.cent_size.setRange(6, 56)
        self.cent_size.setValue(int(S.ui.cent_size * 2))
        f = _Field('Centroid size')
        f.value.setText(str(S.ui.cent_size))
        self._cs_field = f
        self.cent_size.valueChanged.connect(self._on_cent_size)
        f.add(self.cent_size)
        lay.addWidget(f)

        self.colors_section = Collapsible('Cluster colours')
        self.swatches = QWidget()
        self.swatch_box = QHBoxLayout(self.swatches)
        self.swatch_box.setContentsMargins(0, 0, 0, 0)
        self.swatch_box.setSpacing(4)
        self.colors_section.add(self.swatches)
        self.colors_section.add(
            _hint('Click a swatch here or in the Clusters legend to recolour '
                  'that cluster everywhere.'))
        b = QPushButton('Reset colours')
        b.clicked.connect(self.reset_colors)
        self.colors_section.add(b)
        lay.addWidget(self.colors_section)

        self.shape_field = Collapsible('Marker shapes')
        self.shape_by_sample = QCheckBox('Marker shape by sample')
        self.shape_by_sample.setChecked(S.ui.shape_by_sample)
        self.shape_by_sample.toggled.connect(self._on_shape_by_sample)
        self.shape_field.add(self.shape_by_sample)
        self.shape_field.add(_hint(
            'Colour keeps showing the cluster; the shape shows which sample '
            'the particle came from. Click a sample in the legend to show only '
            'its data.'))
        self.shape_rows = QWidget()
        self.shape_box = QVBoxLayout(self.shape_rows)
        self.shape_box.setContentsMargins(0, 0, 0, 0)
        self.shape_box.setSpacing(3)
        self.shape_field.add(self.shape_rows)
        self.shape_field.body.setVisible(self.shape_field.header.isChecked())
        b = QPushButton('Reset shapes')
        b.clicked.connect(self.reset_shapes)
        self.shape_field.add(b)
        lay.addWidget(self.shape_field)

        lay.addStretch(1)
        return w

    def _boxes_tab(self):
        """Build the Boxes tab: which floating panels are shown.

        Returns:
            QWidget: The tab page.
        """
        S = self.S
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(9)

        self.inset_on = QCheckBox("Detail view — the algorithm's own figure")
        self.inset_on.setChecked(S.inset_on)
        self.inset_on.toggled.connect(self._on_inset_on)
        f = _Field()
        f.add(self.inset_on)
        f.set_hint('Dendrogram for Hierarchical, reachability plot for OPTICS, '
                   'U-matrix for SOM, objective curve for K-Means / GMM…')
        lay.addWidget(f)

        self.eq_on = QCheckBox('Worked example — the equation with your numbers')
        self.eq_on.setChecked(S.eq_on)
        self.eq_on.toggled.connect(self._on_eq_on)
        f = _Field()
        f.add(self.eq_on)
        f.set_hint('States the equation the current step is evaluating, then '
                   "substitutes this frame's actual values into it.")
        lay.addWidget(f)

        self.legend_on = QCheckBox('Cluster legend')
        self.legend_on.setChecked(S.legend_on)
        self.legend_on.toggled.connect(self._on_legend_on)
        lay.addWidget(self.legend_on)

        b = QPushButton('Reset size & position')
        b.clicked.connect(self.reset_boxes)
        lay.addWidget(b)
        lay.addStretch(1)
        return w

    def _export_tab(self):
        """Build the Export tab: resolution, text scaling and transparency.

        Returns:
            QWidget: The tab page.
        """
        S = self.S
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(9)

        self.exp_scale = QComboBox()
        for v, t in ((2, '2× — screen quality, larger'),
                     (3, '3× — print quality (recommended)'),
                     (4, '4× — poster quality'),
                     (6, '6× — maximum')):
            self.exp_scale.addItem(t, v)
        self.exp_scale.setCurrentIndex(1)
        self.exp_scale.currentIndexChanged.connect(
            lambda _: setattr(S.exp, 'scale', int(self.exp_scale.currentData())))
        f = _Field('Resolution')
        f.add(self.exp_scale)
        lay.addWidget(f)

        self.exp_font = QSlider(Qt.Horizontal)
        self.exp_font.setRange(100, 250)
        self.exp_font.setValue(int(S.exp.font_boost * 100))
        f = _Field('Text enlargement')
        f.value.setText('%.2f×' % S.exp.font_boost)
        self._ef_field = f
        self.exp_font.valueChanged.connect(self._on_exp_font)
        f.add(self.exp_font)
        f.set_hint('Fonts, numbers and markers are drawn larger relative to the '
                   'figure so they stay readable when the image is scaled down.')
        lay.addWidget(f)

        self.exp_transparent = QCheckBox('Transparent background')
        self.exp_transparent.toggled.connect(
            lambda v: setattr(S.exp, 'transparent', bool(v)))
        lay.addWidget(self.exp_transparent)

        row = QHBoxLayout()
        b1 = QPushButton('Export main plot')
        b1.clicked.connect(self.export_plot)
        b2 = QPushButton('Export detail view')
        b2.clicked.connect(self.export_inset)
        row.addWidget(b1)
        row.addWidget(b2)
        lay.addLayout(row)
        lay.addStretch(1)
        return w

    def _info_tab(self):
        """Build the Info tab, which holds the dataset summary table.

        Returns:
            QWidget: The tab page.
        """
        w = QWidget()
        lay = QVBoxLayout(w)
        self.info = QLabel('')
        self.info.setTextFormat(Qt.RichText)
        self.info.setWordWrap(True)
        self.info.setAlignment(Qt.AlignTop)
        lay.addWidget(self.info)
        lay.addStretch(1)
        return w

    def _on_font_size(self, raw):
        """Set the base font size from the half-step slider.

        Args:
            raw (int): Slider value, twice the size in pixels.
        """
        self.S.ui.font_size = raw / 2.0
        self._fs_field.value.setText(str(raw / 2.0))
        self.appearance_changed.emit()

    def _on_point_size(self, raw):
        """Set the particle radius, where zero means auto by particle count.

        Args:
            raw (int): Slider value, twice the radius in pixels.
        """
        self.S.ui.point_size = raw / 2.0
        self._ps_field.value.setText(str(raw / 2.0) if raw else 'auto')
        self.appearance_changed.emit()

    def _on_cent_size(self, raw):
        """Set the centroid marker radius.

        Args:
            raw (int): Slider value, twice the radius in pixels.
        """
        self.S.ui.cent_size = raw / 2.0
        self._cs_field.value.setText(str(raw / 2.0))
        self.appearance_changed.emit()

    def _on_exp_font(self, raw):
        """Set how much larger type is drawn in an exported image.

        Args:
            raw (int): Slider value, the boost as a percentage.
        """
        self.S.exp.font_boost = raw / 100.0
        self._ef_field.value.setText('%.2f×' % (raw / 100.0))

    def _on_font_family(self, _idx=0):
        """Adopt the chosen typeface for the painted text.

        Args:
            _idx (int): Unused; the family is read from the combo data.
        """
        self.S.ui.font = self.font_family.currentData() or ''
        self.appearance_changed.emit()

    def _on_font_style(self, _checked=False):
        """Set the weight and slant from the Bold and Italic checkboxes.

        Args:
            _checked (bool): Unused; both boxes are read together.
        """
        parts = []
        if self.font_bold.isChecked():
            parts.append('bold')
        if self.font_italic.isChecked():
            parts.append('italic')
        self.S.ui.font_style = ' '.join(parts) or 'normal'
        self.appearance_changed.emit()

    def _on_label_mode(self, v):
        """Adopt an element label style and announce it for persisting.

        Args:
            v (str): One of Symbol, Mass + Symbol or Atomic Notation.
        """
        if self._loading:
            return
        self.S.ui.label_mode = v
        self.label_mode_changed.emit(v)

    def _on_shape_by_sample(self, v):
        """Toggle marker-shape-by-sample and rebuild the per-sample rows.

        Args:
            v (bool): Whether shape encodes the sample.
        """
        self.S.ui.shape_by_sample = bool(v)
        self.build_shape_rows()
        self.appearance_changed.emit()

    def _on_inset_on(self, v):
        """Show or hide the detail view.

        Args:
            v (bool): Whether the box is shown.
        """
        self.S.inset_on = bool(v)
        self.boxes_toggled.emit()

    def _on_eq_on(self, v):
        """Show or hide the worked example.

        Args:
            v (bool): Whether the box is shown.
        """
        self.S.eq_on = bool(v)
        self.boxes_toggled.emit()

    def _on_legend_on(self, v):
        """Show or hide the cluster legend.

        Args:
            v (bool): Whether the box is shown.
        """
        self.S.legend_on = bool(v)
        self.boxes_toggled.emit()

    def build_swatches(self, on_pick):
        """Build one clickable swatch per cluster present.

        Args:
            on_pick (callable): Called with the cluster id when one is clicked.
        """
        while self.swatch_box.count():
            w = self.swatch_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        fr = self.S.current_frame()
        ids = sorted({int(c) for c in (fr or {}).get('labels', []) if c >= 0})
        for c in ids:
            b = QPushButton()
            b.setFixedSize(18, 18)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(cluster_tag(c))
            b.setStyleSheet('background:%s;border:1px solid %s;border-radius:4px;'
                            % (self.S.cluster_color(c), THEME.stroke))
            b.clicked.connect(lambda _=False, cid=c: on_pick(cid))
            self.swatch_box.addWidget(b)
        self.swatch_box.addStretch(1)

    def build_shape_rows(self):
        """Build the per-sample marker rows, hiding them for single input."""
        S = self.S
        self.shape_field.setVisible(S.is_multi_sample())
        while self.shape_box.count():
            w = self.shape_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not S.is_multi_sample():
            return
        for name in S.sample_names():
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(7)
            gl = QLabel()
            gl.setFixedSize(13, 13)
            gl.setPixmap(_glyph_pixmap(S.shape_for(name), THEME.text))
            h.addWidget(gl)
            h.addWidget(QLabel(name), 1)
            sel = QComboBox()
            for sh in SHAPES:
                sel.addItem(SHAPE_LABELS.get(sh, sh), sh)
            i = sel.findData(S.shape_for(name))
            if i >= 0:
                sel.setCurrentIndex(i)
            sel.setEnabled(S.ui.shape_by_sample)
            sel.currentIndexChanged.connect(
                lambda _=0, nm=name, s=sel: self.sample_shape_changed.emit(
                    nm, s.currentData()))
            h.addWidget(sel)
            self.shape_box.addWidget(row)

    def build_info(self):
        """Fill the Info tab with the dataset and view details."""
        S = self.S
        d = S.data or {}
        fr = S.current_frame()
        m = (fr or {}).get('metrics') or {}
        vr = ' / '.join('%.1f%%' % (v * 100) for v in (d.get('var_ratio') or []))
        n, n_total = d.get('n'), d.get('n_total')
        shown = '–' if n is None else (
            '%s of %s' % (n, n_total) if n_total and n_total > n else str(n))
        cfg = d.get('config') or {}
        rows = [
            ('Algorithm', S.algo),
            ('Particles shown', shown),
            ('Elements', len(d.get('elements') or [])),
            ('Projection', '%s · %sD' % (d.get('projection') or 'PCA',
                                         d.get('dims') or 2)),
            ('Explained variance', vr or '—'),
            ('Data type', cfg.get('data_type') or '—'),
            ('Scaling', cfg.get('scaling') or '—'),
            ('Clusters', m.get('n_clusters', '–')),
            ('Noise points', m.get('n_noise', '–')),
            ('Inertia', '%.2f' % m['inertia'] if m.get('inertia') is not None else '–'),
            ('Silhouette', '%.3f' % m['silhouette']
             if m.get('silhouette') is not None else '–'),
            ('Davies-Bouldin', '%.3f' % m['davies_bouldin']
             if m.get('davies_bouldin') is not None else '–'),
            ('Fit', (fr or {}).get('note') or '—'),
        ]
        from html import escape
        self.info.setText(
            '<table width="100%">' + ''.join(
                '<tr><td style="color:%s">%s</td><td align="right"><b>%s</b></td></tr>'
                % (THEME.muted, escape(str(k)), escape(str(v)))
                for k, v in rows) + '</table>')

    def sync(self):
        """Push the current state into every control."""
        self._loading = True
        try:
            self.inset_on.setChecked(self.S.inset_on)
            self.eq_on.setChecked(self.S.eq_on)
            self.legend_on.setChecked(self.S.legend_on)
            self.label_mode.setCurrentText(self.S.ui.label_mode)
        finally:
            self._loading = False
