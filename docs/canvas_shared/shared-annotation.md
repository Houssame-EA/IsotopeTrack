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
| `LINE_STYLES` | `{'solid': Qt.SolidLine, 'dash': Qt.DashLine, 'dot': Qt.Do…` |
| `DEFAULT_COLOR` | `'#A32D2D'` |
| `SELECTION_COLOR` | `'#378ADD'` |
| `HANDLE_SIZE_PX` | `8` |
| `QUICK_COLORS` | `['#A32D2D', '#185FA5', '#0F6E56', '#BA7517', '#444441', '…` |
| `_ANNOTATION_CLASSES` | `{'text': TextAnnotation, 'vline': VLineAnnotation, 'hline…` |

## Classes

### `_Command`

| Method | Signature | Description |
|--------|-----------|-------------|
| `apply` | `(self)` |  |
| `revert` | `(self)` |  |

### `AddCommand` *(extends `_Command`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, mgr, data)` |  |
| `apply` | `(self)` |  |
| `revert` | `(self)` |  |

### `RemoveCommand` *(extends `_Command`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, mgr, data, index)` |  |
| `apply` | `(self)` |  |
| `revert` | `(self)` |  |

### `ModifyCommand` *(extends `_Command`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, mgr, ann_id, before, after)` |  |
| `apply` | `(self)` |  |
| `revert` | `(self)` |  |

### `UndoStack` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, limit: int=100)` |  |
| `push` | `(self, cmd: _Command)` |  |
| `undo` | `(self)` |  |
| `redo` | `(self)` |  |
| `can_undo` | `(self) → bool` |  |
| `can_redo` | `(self) → bool` |  |

### `_DraggableText` *(extends `pg.TextItem`)*

TextItem with built-in drag-to-move + arrow line to an optional target.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, html: str='', color='#000000', anchor=(0, 0))` |  |
| `hoverEnterEvent` | `(self, ev)` |  |
| `hoverLeaveEvent` | `(self, ev)` |  |
| `mousePressEvent` | `(self, ev)` |  |
| `mouseMoveEvent` | `(self, ev)` |  |
| `mouseReleaseEvent` | `(self, ev)` |  |

### `BaseAnnotation` *(extends `QObject`)*

Base wrapper. Subclasses implement _build_item, _sync_from_data, _hookup.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, data: dict)` |  |
| `attach` | `(self, plot_item)` | Create and add item(s) to the plot. |
| `detach` | `(self)` | Remove all items from the plot. |
| `refresh` | `(self)` | Reapply data → visual. |
| `set_selected` | `(self, selected: bool)` |  |
| `_build_item` | `(self, plot_item)` |  |
| `_sync_from_data` | `(self)` |  |
| `_hookup` | `(self)` | Wire pyqtgraph signals to sig_clicked / sig_drag_finished. |
| `_apply_selection_style` | `(self)` | Visual change when selected vs. unselected. |
| `_color` | `(self) → QColor` |  |
| `_pen` | `(self) → QPen` |  |

### `TextAnnotation` *(extends `BaseAnnotation`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, data)` |  |
| `_build_item` | `(self, plot_item)` |  |
| `_sync_from_data` | `(self)` |  |
| `_hookup` | `(self)` |  |
| `_on_drag_done` | `(self, _)` |  |
| `_apply_selection_style` | `(self)` |  |

### `_LineAnnotation` *(extends `BaseAnnotation`)*

Shared logic for vertical & horizontal lines.

| Method | Signature | Description |
|--------|-----------|-------------|
| `_build_item` | `(self, plot_item)` |  |
| `_sync_from_data` | `(self)` |  |
| `_hookup` | `(self)` |  |
| `_on_drag_done` | `(self, _)` |  |
| `_apply_selection_style` | `(self)` |  |

### `VLineAnnotation` *(extends `_LineAnnotation`)*

### `HLineAnnotation` *(extends `_LineAnnotation`)*

### `VBandAnnotation` *(extends `BaseAnnotation`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `_build_item` | `(self, plot_item)` |  |
| `_sync_from_data` | `(self)` |  |
| `_hookup` | `(self)` |  |
| `_on_drag_done` | `(self, _)` |  |

### `RectAnnotation` *(extends `BaseAnnotation`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, data)` |  |
| `_build_item` | `(self, plot_item)` |  |
| `_sync_from_data` | `(self)` |  |
| `_hookup` | `(self)` |  |
| `_apply_selection_style` | `(self)` |  |
| `_ensure_handles` | `(self)` | Create the four corner-drag handles if they don't already exist. |
| `_remove_handles` | `(self)` |  |
| `_on_handle_done` | `(self, which: str, handle)` |  |
| `detach` | `(self)` |  |

### `_SceneMouseEventFilter` *(extends `QObject`)*

Event filter installed on the pyqtgraph plot scene.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, manager)` |  |
| `eventFilter` | `(self, obj, event)` |  |

### `AnnotationManager` *(extends `QObject`)*

Owns cfg['annotations'], the list of live annotation wrappers, the selection

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict, parent=None)` |  |
| `attach_plot` | `(self, plot_item)` | Called after every plot refresh. Rebuilds all annotation items. |
| `_detach_all` | `(self)` |  |
| `_build_wrapper` | `(self, data)` |  |
| `begin_insert` | `(self, ann_type: str)` |  |
| `cancel_insert` | `(self)` |  |
| `is_inserting` | `(self) → bool` |  |
| `_on_scene_clicked` | `(self, ev)` | Scene-level click: either places a new annotation (insert mode), |
| `add_new` | `(self, ann_type: str, x: float, y: float)` |  |
| `remove_selected` | `(self)` |  |
| `update_selected` | `(self, new_data: dict)` |  |
| `select` | `(self, ann_id: Optional[str])` |  |
| `get_selected_data` | `(self) → Optional[dict]` |  |
| `get_all_data` | `(self) → list` |  |
| `_raw_add` | `(self, data)` |  |
| `_raw_insert` | `(self, index, data)` |  |
| `_raw_remove` | `(self, ann_id)` |  |
| `_raw_update` | `(self, ann_id, new_data)` |  |
| `_on_item_clicked` | `(self, ann_id: str)` |  |
| `_on_item_drag_done` | `(self, ann_id: str, new_data: dict)` |  |
| `_on_undo_changed` | `(self)` |  |

### `_ColorSwatch` *(extends `QToolButton`)*

A round, clickable color dot. Emits sig_picked(hex_str).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, hex_color: str, selected: bool=False, size: int=20, parent=None` |  |
| `_set_selected` | `(self, sel: bool)` |  |
| `set_selected` | `(self, sel: bool)` |  |

### `_CustomColorButton` *(extends `QToolButton`)*

The '+' button that opens a QColorDialog. Emits sig_picked(hex).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, size: int=20, parent=None)` |  |
| `_pick` | `(self)` |  |

### `FloatingInspector` *(extends `QFrame`)*

Small popover shown next to the currently selected annotation.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, mgr: 'AnnotationManager', parent: QWidget)` |  |
| `set_plot_accessor` | `(self, fn: Callable)` | fn() → (plot_widget, plot_item).  Both may be None. |
| `attach` | `(self, plot_item)` | Called after each host-dialog _refresh to rebind positioning signals. |
| `_on_selection_changed` | `(self, data)` |  |
| `_resize_to_content` | `(self)` | Force the inspector to shrink/grow to its form's sizeHint. |
| `_reposition` | `(self)` |  |
| `_clear_form` | `(self)` |  |
| `_build_for` | `(self, data: dict)` |  |
| `_title_for` | `(self, data: dict) → str` |  |
| `_add_text_editor` | `(self, layout, data, key: str, placeholder: str='')` |  |
| `_add_style_row` | `(self, layout, data)` |  |
| `_add_opacity_row` | `(self, layout, data)` |  |
| `_add_border_width_row` | `(self, layout, data)` |  |
| `_add_arrow_fields` | `(self, layout, data)` |  |
| `_build_color_row` | `(self, data) → QWidget` |  |
| `_on_swatch_picked` | `(self, hx: str)` |  |
| `_commit` | `(self)` |  |

### `AnnotationShelfButton` *(extends `QPushButton`)*

A small pill showing "≡ N annotations". Clicking opens a popup menu

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, mgr: 'AnnotationManager', parent=None)` |  |
| `_refresh` | `(self)` |  |
| `_summarize` | `(self, d: dict) → str` |  |
| `_show_menu` | `(self)` |  |
| `_clear_all` | `(self)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_new_id` | `() → str` |  |
| `_default_data` | `(ann_type: str, x: float=0.0, y: float=0.0) → dict` | Return a default data dict for a new annotation of the given type. |
| `make_annotation` | `(data: dict) → BaseAnnotation` |  |
| `build_annotate_submenu` | `(parent_menu, mgr: 'AnnotationManager', data_x: float, data_y: float, ` | Insert annotation items at the top of `parent_menu`, with coordinates |
| `_anchor_for` | `(data: dict, viewbox) → tuple[float, float]` | Return (data_x, data_y) near which the floating inspector should sit. |
| `install_annotation_shortcuts` | `(widget: QWidget, mgr: AnnotationManager)` | Install Del / Ctrl+Z / Ctrl+Shift+Z / Esc shortcuts on a dialog. |
