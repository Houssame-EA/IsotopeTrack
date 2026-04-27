# `shared_annotation.py`

shared_annotations.py — Figure annotation system for IsotopeTrack.

PowerPoint-style overlay for any PyQtGraph plot: click-to-select, drag-to-move,
resize handles, inspector panel, undo/redo. Designed to plug into any plot node
via a small integration (see `integrate_with_plot_widget` and `AnnotationManager`).

The annotation state lives in cfg['annotations'] (a list of plain dicts), so it
serializes with the workflow and can be rendered to either PyQtGraph (interactive)
or Matplotlib (publication export, future work).

Annotation schema (MVP — 5 types):
Common fields:
'id':    str       — unique identifier (e.g. 'ann_3f9a2b')
'type':  str       — 'text' | 'vline' | 'hline' | 'vband' | 'rect'
'color': str       — hex, e.g. '#A32D2D'
'width': int       — line/border width in px
'alpha': float     — 0..1 fill opacity (where applicable)

Type-specific fields:
text:  'x', 'y', 'text', 'font_size', 'box'(bool),
'arrow_to': [x, y] | None
vline: 'x', 'label', 'style'('solid'|'dash'|'dot')
hline: 'y', 'label', 'style'
vband: 'x1', 'x2', 'label'
rect:  'x1', 'y1', 'x2', 'y2', 'label', 'filled'(bool)

Usage in a display dialog:

from results.shared_annotations import (
AnnotationManager, AnnotationToolbar, AnnotationInspector,
draw_annotations,
)

# In _build_ui:
self.ann_mgr = AnnotationManager(self.node.config, parent=self)
self.ann_toolbar = AnnotationToolbar(self.ann_mgr, parent=self)
self.ann_inspector = AnnotationInspector(self.ann_mgr, parent=self)
# ... add toolbar to top, inspector to right-side of layout

# In _refresh, after drawing the plot:
self.ann_mgr.attach_plot(plot_item)  # rebuilds annotation items on the plot

---

## Constants

| Name | Value |
|------|-------|
| `ANNOTATION_TYPES` | `['text', 'vline', 'hline', 'vband', 'rect']` |
| `LINE_STYLES` | `{'solid': Qt.SolidLine, 'dash': Qt.DashLine, 'd...` |
| `DEFAULT_COLOR` | `'#A32D2D'` |
| `SELECTION_COLOR` | `'#378ADD'` |
| `HANDLE_SIZE_PX` | `8` |
| `QUICK_COLORS` | `['#A32D2D', '#185FA5', '#0F6E56', '#BA7517', '#...` |
| `_ANNOTATION_CLASSES` | `{'text': TextAnnotation, 'vline': VLineAnnotati...` |

## Classes

### `_Command`

### `AddCommand` *(extends `_Command`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, mgr, data)` | Args: |
| `apply` | `(self)` |  |
| `revert` | `(self)` |  |

### `RemoveCommand` *(extends `_Command`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, mgr, data, index)` | Args: |
| `apply` | `(self)` |  |
| `revert` | `(self)` |  |

### `ModifyCommand` *(extends `_Command`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, mgr, ann_id, before, after)` | Args: |
| `apply` | `(self)` |  |
| `revert` | `(self)` |  |

### `UndoStack` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, limit: int = 100)` | Args: |
| `push` | `(self, cmd: _Command)` | Args: |
| `undo` | `(self)` |  |
| `redo` | `(self)` |  |

### `_DraggableText` *(extends `pg.TextItem`)*

TextItem with built-in drag-to-move + arrow line to an optional target.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, html: str = '', color = '#000000', anchor = (0, 0))` | Args: |
| `hoverEnterEvent` | `(self, ev)` | Args: |
| `hoverLeaveEvent` | `(self, ev)` | Args: |
| `mousePressEvent` | `(self, ev)` | Args: |
| `mouseMoveEvent` | `(self, ev)` | Args: |
| `mouseReleaseEvent` | `(self, ev)` | Args: |

### `BaseAnnotation` *(extends `QObject`)*

Base wrapper. Subclasses implement _build_item, _sync_from_data, _hookup.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, data: dict)` | Args: |
| `attach` | `(self, plot_item)` | Create and add item(s) to the plot. |
| `detach` | `(self)` | Remove all items from the plot. |
| `refresh` | `(self)` | Reapply data → visual. |
| `set_selected` | `(self, selected: bool)` | Args: |
| `_build_item` | `(self, plot_item)` | Args: |
| `_sync_from_data` | `(self)` |  |
| `_hookup` | `(self)` | Wire pyqtgraph signals to sig_clicked / sig_drag_finished. |
| `_apply_selection_style` | `(self)` | Visual change when selected vs. unselected. |
| `_color` | `(self) → QColor` | Returns: |
| `_pen` | `(self) → QPen` | Returns: |

### `TextAnnotation` *(extends `BaseAnnotation`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, data)` | Args: |
| `_build_item` | `(self, plot_item)` | Args: |
| `_sync_from_data` | `(self)` |  |
| `_hookup` | `(self)` |  |
| `_on_drag_done` | `(self, _)` | Args: |
| `_apply_selection_style` | `(self)` |  |

### `_LineAnnotation` *(extends `BaseAnnotation`)*

Shared logic for vertical & horizontal lines.

| Method | Signature | Description |
|--------|-----------|-------------|
| `_build_item` | `(self, plot_item)` | Args: |
| `_sync_from_data` | `(self)` |  |
| `_hookup` | `(self)` |  |
| `_on_drag_done` | `(self, _)` | Args: |
| `_apply_selection_style` | `(self)` |  |

### `VLineAnnotation` *(extends `_LineAnnotation`)*

### `HLineAnnotation` *(extends `_LineAnnotation`)*

### `VBandAnnotation` *(extends `BaseAnnotation`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `_build_item` | `(self, plot_item)` | Args: |
| `_sync_from_data` | `(self)` |  |
| `_hookup` | `(self)` |  |
| `_on_drag_done` | `(self, _)` | Args: |

### `RectAnnotation` *(extends `BaseAnnotation`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, data)` | Args: |
| `_build_item` | `(self, plot_item)` | Args: |
| `_sync_from_data` | `(self)` |  |
| `_hookup` | `(self)` |  |
| `_apply_selection_style` | `(self)` |  |
| `_ensure_handles` | `(self)` | Create the four corner-drag handles if they don't already exist. |
| `_remove_handles` | `(self)` |  |
| `_on_handle_done` | `(self, which: str, handle)` | Args: |
| `detach` | `(self)` |  |

### `_SceneMouseEventFilter` *(extends `QObject`)*

Event filter installed on the pyqtgraph plot scene.

Purpose: consume mouse press / release / move events at the scene level
so they never bubble to the parent dialog or the OS window manager.
Without this, macOS treats an unaccepted scene-level mouse release
(produced after dragging an annotation to a new position) as a click
outside the focused dialog, which raises the main application window
above the dialog.

We don't filter events that would block interaction — pyqtgraph items
still receive their own mousePressEvent / mouseMoveEvent / mouseReleaseEvent
via the scene's normal event dispatch. The filter only accepts the event
*after* dispatch, preventing onward propagation.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, manager)` | Args: |
| `eventFilter` | `(self, obj, event)` | Args: |

### `AnnotationManager` *(extends `QObject`)*

Owns cfg['annotations'], the list of live annotation wrappers, the selection
state, and the undo stack. Exposes methods for toolbar/inspector to call.

Flow:
- Plot dialog calls attach_plot(plot_item) after every _refresh to rebuild items.
- Toolbar calls begin_insert(type) to enter insert mode; next click on the
plot scene creates an annotation at the clicked (data) coordinates.
- Inspector calls update_selected(new_data) to modify the selected annotation.
- Manager emits sig_selection_changed when selection changes.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict, parent = None)` | Args: |
| `attach_plot` | `(self, plot_item)` | Called after every plot refresh. Rebuilds all annotation items. |
| `_detach_all` | `(self)` |  |
| `_build_wrapper` | `(self, data)` | Args: |
| `begin_insert` | `(self, ann_type: str)` | Args: |
| `cancel_insert` | `(self)` |  |
| `is_inserting` | `(self) → bool` | Returns: |
| `_on_scene_clicked` | `(self, ev)` | Scene-level click: either places a new annotation (insert mode), |
| `add_new` | `(self, ann_type: str, x: float, y: float)` | Args: |
| `remove_selected` | `(self)` |  |
| `update_selected` | `(self, new_data: dict)` | Args: |
| `select` | `(self, ann_id: Optional[str])` | Args: |
| `get_selected_data` | `(self) → Optional[dict]` | Returns: |
| `get_all_data` | `(self) → list` | Returns: |
| `_raw_add` | `(self, data)` | Args: |
| `_raw_insert` | `(self, index, data)` | Args: |
| `_raw_remove` | `(self, ann_id)` | Args: |
| `_raw_update` | `(self, ann_id, new_data)` | Args: |
| `_on_item_clicked` | `(self, ann_id: str)` | Args: |
| `_on_item_drag_done` | `(self, ann_id: str, new_data: dict)` | Args: |
| `_on_undo_changed` | `(self)` |  |

### `_ColorSwatch` *(extends `QToolButton`)*

A round, clickable color dot. Emits sig_picked(hex_str).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, hex_color: str, selected: bool = False, size: int = 20, parent ` | Args: |
| `_set_selected` | `(self, sel: bool)` | Args: |
| `set_selected` | `(self, sel: bool)` | Args: |

### `_CustomColorButton` *(extends `QToolButton`)*

The '+' button that opens a QColorDialog. Emits sig_picked(hex).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, size: int = 20, parent = None)` | Args: |
| `_pick` | `(self)` |  |

### `FloatingInspector` *(extends `QFrame`)*

Small popover shown next to the currently selected annotation.

Parented to a *persistent* container (not the plot widget, which gets
recreated on every refresh). Uses a getter to find the current plot
widget / viewbox for positioning.

Lifecycle:
fi = FloatingInspector(mgr, parent=plot_container)
fi.set_plot_accessor(lambda: (self.pw, self.primary_plot_item))
# after every _refresh() in the host dialog:
fi.attach(current_plot_item)

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, mgr: 'AnnotationManager', parent: QWidget)` | Args: |
| `set_plot_accessor` | `(self, fn: Callable)` | fn() → (plot_widget, plot_item).  Both may be None. |
| `attach` | `(self, plot_item)` | Called after each host-dialog _refresh to rebind positioning signals. |
| `_on_selection_changed` | `(self, data)` | Args: |
| `_resize_to_content` | `(self)` | Force the inspector to shrink/grow to its form's sizeHint. |
| `_reposition` | `(self)` |  |
| `_clear_form` | `(self)` |  |
| `_build_for` | `(self, data: dict)` | Args: |
| `_title_for` | `(self, data: dict) → str` | Args: |
| `_add_text_editor` | `(self, layout, data, key: str, placeholder: str = '')` | Args: |
| `_add_style_row` | `(self, layout, data)` | Args: |
| `_add_opacity_row` | `(self, layout, data)` | Args: |
| `_add_border_width_row` | `(self, layout, data)` | Args: |
| `_add_arrow_fields` | `(self, layout, data)` | Args: |
| `_build_color_row` | `(self, data) → QWidget` | Args: |
| `_on_swatch_picked` | `(self, hx: str)` | Args: |
| `_commit` | `(self)` |  |

### `AnnotationShelfButton` *(extends `QPushButton`)*

A small pill showing "≡ N annotations". Clicking opens a popup menu
with each annotation (select, toggle visible, delete) and a "clear all".

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, mgr: 'AnnotationManager', parent = None)` | Args: |
| `_refresh` | `(self)` |  |
| `_summarize` | `(self, d: dict) → str` | Args: |
| `_show_menu` | `(self)` |  |
| `_clear_all` | `(self)` |  |

## Functions

### `_new_id`

```python
def _new_id() → str
```


**Returns:**

- `str: Result of the operation.`

### `_default_data`

```python
def _default_data(ann_type: str, x: float = 0.0, y: float = 0.0) → dict
```

Return a default data dict for a new annotation of the given type.

**Args:**

- `ann_type (str): The ann type.`
- `x (float): Input array or value.`
- `y (float): Input array or value.`

**Returns:**

- `dict: Result of the operation.`

### `make_annotation`

```python
def make_annotation(data: dict) → BaseAnnotation
```


**Args:**

- `data (dict): Input data.`

**Returns:**

- `BaseAnnotation: Result of the operation.`

### `build_annotate_submenu`

```python
def build_annotate_submenu(parent_menu, mgr: 'AnnotationManager', data_x: float, data_y: float, smart_actions = None, title_prefix: str = 'Annotate here') → None
```

Insert annotation items at the top of `parent_menu`, with coordinates
pre-filled from (data_x, data_y). Lays out inline (no submenu cascade)
so the menu is fast to scan and robust against Qt-side menu lifetime
issues.


**Args:**

- `parent_menu:    an existing QMenu to prepend into`
- `mgr:            AnnotationManager for this plot`
- `data_x, data_y: click coordinates in plot data space`
- `smart_actions:  optional list of (label:str, callback:callable) for`
- `plot-type-specific data-aware actions`
- `title_prefix:   header text before the coord pair`

**Returns:**

- `None`

### `_anchor_for`

```python
def _anchor_for(data: dict, viewbox) → tuple[float, float]
```

Return (data_x, data_y) near which the floating inspector should sit.

**Args:**

- `data (dict): Input data.`
- `viewbox (Any): The viewbox.`

**Returns:**

- `tuple[float, float]: Result of the operation.`

### `install_annotation_shortcuts`

```python
def install_annotation_shortcuts(widget: QWidget, mgr: AnnotationManager)
```

Install Del / Ctrl+Z / Ctrl+Shift+Z / Esc shortcuts on a dialog.

**Args:**

- `widget (QWidget): Target widget.`
- `mgr (AnnotationManager): The mgr.`

**Returns:**

- `object: Result of the operation.`
