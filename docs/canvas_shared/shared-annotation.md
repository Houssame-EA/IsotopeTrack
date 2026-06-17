# `shared_annotation.py`

shared_annotations.py — Figure annotation system for IsotopeTrack.

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
| `__init__` | `(self, limit: int=100)` | Args: |
| `push` | `(self, cmd: _Command)` | Args: |
| `undo` | `(self)` |  |
| `redo` | `(self)` |  |
| `can_undo` | `(self) → bool` |  |
| `can_redo` | `(self) → bool` |  |

### `_DraggableText` *(extends `pg.TextItem`)*

TextItem with built-in drag-to-move + arrow line to an optional target.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, html: str='', color='#000000', anchor=(0, 0))` | Args: |
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

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, manager)` | Args: |
| `eventFilter` | `(self, obj, event)` | Args: |

### `AnnotationManager` *(extends `QObject`)*

Owns cfg['annotations'], the list of live annotation wrappers, the selection

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, cfg: dict, parent=None)` | Args: |
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
| `__init__` | `(self, hex_color: str, selected: bool=False, size: int=20, parent=None` | Args: |
| `_set_selected` | `(self, sel: bool)` | Args: |
| `set_selected` | `(self, sel: bool)` | Args: |

### `_CustomColorButton` *(extends `QToolButton`)*

The '+' button that opens a QColorDialog. Emits sig_picked(hex).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, size: int=20, parent=None)` | Args: |
| `_pick` | `(self)` |  |

### `FloatingInspector` *(extends `QFrame`)*

Small popover shown next to the currently selected annotation.

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
| `_add_text_editor` | `(self, layout, data, key: str, placeholder: str='')` | Args: |
| `_add_style_row` | `(self, layout, data)` | Args: |
| `_add_opacity_row` | `(self, layout, data)` | Args: |
| `_add_border_width_row` | `(self, layout, data)` | Args: |
| `_add_arrow_fields` | `(self, layout, data)` | Args: |
| `_build_color_row` | `(self, data) → QWidget` | Args: |
| `_on_swatch_picked` | `(self, hx: str)` | Args: |
| `_commit` | `(self)` |  |

### `AnnotationShelfButton` *(extends `QPushButton`)*

A small pill showing "≡ N annotations". Clicking opens a popup menu

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, mgr: 'AnnotationManager', parent=None)` | Args: |
| `_refresh` | `(self)` |  |
| `_summarize` | `(self, d: dict) → str` | Args: |
| `_show_menu` | `(self)` |  |
| `_clear_all` | `(self)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_new_id` | `() → str` | Returns: |
| `_default_data` | `(ann_type: str, x: float=0.0, y: float=0.0) → dict` | Return a default data dict for a new annotation of the given type. |
| `make_annotation` | `(data: dict) → BaseAnnotation` | Args: |
| `build_annotate_submenu` | `(parent_menu, mgr: 'AnnotationManager', data_x: float, data_y: float, ` | Insert annotation items at the top of `parent_menu`, with coordinates |
| `_anchor_for` | `(data: dict, viewbox) → tuple[float, float]` | Return (data_x, data_y) near which the floating inspector should sit. |
| `install_annotation_shortcuts` | `(widget: QWidget, mgr: AnnotationManager)` | Install Del / Ctrl+Z / Ctrl+Shift+Z / Esc shortcuts on a dialog. |
