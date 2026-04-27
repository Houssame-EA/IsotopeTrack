# `canvas_widgets.py`

---

## Constants

| Name | Value |
|------|-------|
| `_NODE_FACTORIES` | `{'sample_selector': SampleSelectorNode, 'multip...` |
| `_NODE_ITEM_MAP` | `{'sample_selector': SampleSelectorNodeItem, 'mu...` |

## Classes

### `DS`

| Method | Signature | Description |
|--------|-----------|-------------|
| `font` | `(size = None, bold = False)` | Args: |
| `pen` | `(color, width = 1.0)` | Args: |
| `brush` | `(color)` | Args: |

### `WorkflowLink` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, source_node, source_channel, sink_node, sink_channel)` | Args: |
| `get_data` | `(self)` | Returns: |

### `WorkflowNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, title, node_type)` | Args: |
| `set_position` | `(self, pos)` | Args: |
| `configure` | `(self, parent_window)` | Args: |

### `AnchorPointSignals` *(extends `QObject`)*

### `AnchorPoint` *(extends `QGraphicsEllipseItem`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent, channel_name, is_input = True)` | Args: |
| `_apply_style` | `(self, hover = False)` | Args: |
| `itemChange` | `(self, change, value)` | Args: |
| `shape` | `(self)` | Creates an invisible, larger hitbox for easier clicking and dragging. |
| `hoverEnterEvent` | `(self, event)` | Args: |
| `hoverLeaveEvent` | `(self, event)` | Args: |

### `NodeItem` *(extends `QGraphicsWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, workflow_node, parent = None)` | Args: |
| `paint_icon_node` | `(self, painter, grad_colors, icon_name, label_text, badge_text = '', b` | Args: |
| `paint` | `(self, painter, option, widget = None)` | Args: |
| `_create_anchors` | `(self)` |  |
| `get_anchor` | `(self, channel_name)` | Args: |
| `boundingRect` | `(self)` | Returns: |
| `shape` | `(self)` | Returns: |
| `hoverEnterEvent` | `(self, event)` | Args: |
| `hoverLeaveEvent` | `(self, event)` | Args: |
| `mousePressEvent` | `(self, event)` | Args: |
| `show_context_menu` | `(self, global_pos)` | Args: |
| `_ctx_menu_style` | `()` | Returns: |
| `duplicate_node` | `(self)` |  |
| `delete_node` | `(self)` |  |
| `itemChange` | `(self, change, value)` | Args: |
| `mouseDoubleClickEvent` | `(self, event)` | Args: |
| `configure_node` | `(self)` |  |

### `LinkCurveItem` *(extends `QGraphicsWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `_advance_dots` | `(self)` |  |
| `set_curve_path` | `(self, path)` | Args: |
| `set_pen` | `(self, pen)` | Args: |
| `boundingRect` | `(self)` | Returns: |
| `paint` | `(self, painter, option, widget = None)` | Args: |
| `hoverEnterEvent` | `(self, event)` | Args: |
| `hoverLeaveEvent` | `(self, event)` | Args: |

### `LinkItem` *(extends `QGraphicsWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `set_source_anchor` | `(self, anchor)` | Args: |
| `set_sink_anchor` | `(self, anchor)` | Args: |
| `set_workflow_link` | `(self, link)` | Args: |
| `__update_curve` | `(self)` |  |
| `boundingRect` | `(self)` | Returns: |
| `shape` | `(self)` | Returns: |
| `mousePressEvent` | `(self, event)` | Args: |
| `_show_ctx` | `(self, pos)` | Args: |
| `delete_connection` | `(self)` |  |
| `hoverEnterEvent` | `(self, event)` | Args: |
| `hoverLeaveEvent` | `(self, event)` | Args: |
| `itemChange` | `(self, change, value)` | Args: |
| `mouseDoubleClickEvent` | `(self, event)` | Args: |

### `SampleSelectorDialog` *(extends `QDialog`)*

Simplified single-sample configurator: samples on left, isotope chips on right.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent, samples, current_selection = None, current_isotopes = N` | Args: |
| `_build` | `(self)` |  |
| `_make_section_label` | `(self, text)` | Args: |
| `_build_sample_list` | `(self, samples)` | Args: |
| `_load_isotopes` | `(self)` |  |
| `_on_check` | `(self, sample)` | Args: |
| `_filter_samples` | `(self, text)` | Args: |
| `_select_all` | `(self)` |  |
| `_clear_all` | `(self)` |  |
| `_update_preview` | `(self)` |  |
| `get_selection` | `(self)` | Returns: |

### `MultipleSampleSelectorDialog` *(extends `QDialog`)*

Simplified multi-sample configurator: sample list with inline group fields + isotope chips.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent, samples, current_selection = None, current_isotopes = N` | Args: |
| `_build` | `(self)` |  |
| `_make_section_label` | `(self, text)` | Args: |
| `_build_sample_list` | `(self, samples)` | Args: |
| `_load_isotopes` | `(self)` |  |
| `_on_change` | `(self, sample)` | Args: |
| `_filter_samples` | `(self, text)` | Args: |
| `_select_all` | `(self)` |  |
| `_clear_all` | `(self)` |  |
| `_clear_groups` | `(self)` |  |
| `_apply_group_to_checked` | `(self)` |  |
| `_auto_group` | `(self)` | Detect sample groups by stripping common replicate suffixes and numeric endings. |
| `_update_preview` | `(self)` |  |
| `get_selection` | `(self)` | Returns: |

### `SampleSelectorNode` *(extends `WorkflowNode`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `get_output_data` | `(self)` | Returns: |
| `_get_particles` | `(self)` | Returns: |
| `_filter` | `(self, particles)` | Args: |
| `_sample_data` | `(self)` | Returns: |
| `configure` | `(self, parent_window)` | Args: |

### `MultipleSampleSelectorNode` *(extends `WorkflowNode`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `process_data` | `(self, input_data)` | Args: |
| `get_output_data` | `(self)` | Returns: |
| `_add_individual` | `(self, name, src, out)` | Args: |
| `_add_group` | `(self, gname, members, out)` | Args: |
| `_raw_particles` | `(self, sample)` | Args: |
| `_filter` | `(self, particles)` | Args: |
| `configure` | `(self, parent_window)` | Args: |

### `BatchSampleSelectorNode` *(extends `WorkflowNode`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `get_output_data` | `(self)` | Returns: |
| `configure` | `(self, parent_window)` | Args: |

### `BatchSampleSelectorDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window, previously_selected = None)` | Args: |
| `_build` | `(self)` |  |
| `_preview` | `(self)` |  |
| `get_selection` | `(self)` | Returns: |

### `_StatusNodeMixin`

Adds status badge rendering to icon nodes.

| Method | Signature | Description |
|--------|-----------|-------------|
| `_status_text` | `(self)` | Returns: |
| `_status_color` | `(self)` | Returns: |

### `SampleSelectorNodeItem` *(extends `NodeItem, _StatusNodeMixin`)*

Single beaker icon.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, wf, pw = None)` | Args: |
| `paint` | `(self, painter, option, widget = None)` | Args: |
| `_trigger` | `(self)` |  |
| `configure_node` | `(self)` |  |
| `_build_tooltip_lines` | `(self)` | Returns: |
| `_show_tooltip` | `(self)` |  |
| `hoverEnterEvent` | `(self, event)` | Args: |
| `hoverMoveEvent` | `(self, event)` | Args: |
| `hoverLeaveEvent` | `(self, event)` | Args: |

### `ModernNodeTooltip` *(extends `QWidget`)*

Custom floating tooltip with glow effect.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `set_content` | `(self, lines, accent_color = None)` | Args: |
| `_recompute_size` | `(self)` |  |
| `_title_font` | `(self)` | Returns: |
| `_body_font` | `(self)` | Returns: |
| `paintEvent` | `(self, event)` | Args: |

### `StickyNoteItem` *(extends `QGraphicsWidget`)*

A movable, editable sticky note with color, font-size and transparency support.
Right-click empty canvas → Add Note. Double-click to edit.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, text = 'Double-click to edit…', parent = None)` | Args: |
| `_current_colors` | `(self)` | Return (bg_color, border_color, text_color) based on current settings. |
| `boundingRect` | `(self)` | Returns: |
| `paint` | `(self, painter, option, widget = None)` | Args: |
| `hoverEnterEvent` | `(self, event)` | Args: |
| `hoverLeaveEvent` | `(self, event)` | Args: |
| `mouseDoubleClickEvent` | `(self, event)` | Args: |
| `mousePressEvent` | `(self, event)` | Args: |
| `_show_context_menu` | `(self, global_pos)` | Args: |
| `_set_color` | `(self, index)` | Args: |
| `_set_font_size` | `(self, size)` | Args: |
| `_toggle_transparent` | `(self)` |  |
| `_delete_self` | `(self)` |  |

### `MultipleSampleSelectorNodeItem` *(extends `NodeItem, _StatusNodeMixin`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, wf, pw = None)` | Args: |
| `paint` | `(self, painter, option, widget = None)` | Args: |
| `_trigger` | `(self)` |  |
| `configure_node` | `(self)` |  |
| `_build_tooltip_lines` | `(self)` | Returns: |
| `_show_tooltip` | `(self)` |  |
| `hoverEnterEvent` | `(self, event)` | Args: |
| `hoverMoveEvent` | `(self, event)` | Args: |
| `hoverLeaveEvent` | `(self, event)` | Args: |

### `BatchSampleSelectorNodeItem` *(extends `NodeItem, _StatusNodeMixin`)*

Globe / multi-window icon.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, wf, pw = None)` | Args: |
| `paint` | `(self, painter, option, widget = None)` | Args: |
| `_trigger` | `(self)` |  |
| `configure_node` | `(self)` |  |

### `AIAssistantNodeItem` *(extends `NodeItem`)*

AI sparkle icon.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, wf, pw = None)` | Args: |
| `paint` | `(self, painter, option, widget = None)` | Args: |
| `configure_node` | `(self)` |  |

### `DraggableNodeButton` *(extends `QPushButton`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, text, node_type, icon_name = None, color = None)` | Args: |
| `_refresh_style` | `(self)` |  |
| `mousePressEvent` | `(self, event)` | Args: |

### `_CollapsibleGroup` *(extends `QWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, title, parent = None)` | Args: |
| `_apply_theme` | `(self)` |  |
| `addWidget` | `(self, w)` | Args: |
| `toggle` | `(self)` |  |

### `NodePalette` *(extends `QWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `_setup` | `(self)` |  |
| `_apply_palette_theme` | `(self)` |  |
| `_filter` | `(self, text)` | Args: |

### `EnhancedCanvasScene` *(extends `QGraphicsScene`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `_on_selection` | `(self)` |  |
| `keyPressEvent` | `(self, event)` | Args: |
| `undo` | `(self)` | Reverse the last tracked action (add/delete node or link). |
| `delete_selected_items` | `(self)` |  |
| `delete_node` | `(self, ni)` | Args: |
| `delete_link` | `(self, li)` | Args: |
| `duplicate_selected_nodes` | `(self)` |  |
| `duplicate_node` | `(self, ni)` | Args: |
| `select_all_items` | `(self)` |  |
| `add_node` | `(self, wf_node, pos)` | Args: |
| `add_link` | `(self, src_node, src_ch, snk_node, snk_ch)` | Args: |
| `_trigger_data_flow` | `(self, wl)` | Args: |
| `contextMenuEvent` | `(self, event)` | Right-click on empty canvas space → canvas context menu. |
| `mousePressEvent` | `(self, event)` | Args: |
| `mouseMoveEvent` | `(self, event)` | Args: |
| `mouseReleaseEvent` | `(self, event)` | Args: |
| `_start_drag` | `(self, anchor, pos)` | Args: |
| `_end_drag` | `(self, pos)` | Args: |

### `EnhancedCanvasView` *(extends `QGraphicsView`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window = None)` | Args: |
| `_apply_view_theme` | `(self)` |  |
| `_safe_apply_view_theme` | `(self)` |  |
| `_view_disconnect_theme` | `(self)` |  |
| `_setup_shortcuts` | `(self)` |  |
| `wheelEvent` | `(self, event: QWheelEvent)` | Args: |
| `set_zoom` | `(self, value)` | Args: |
| `fit_content` | `(self)` |  |
| `mousePressEvent` | `(self, event)` | Args: |
| `mouseMoveEvent` | `(self, event)` | Args: |
| `mouseReleaseEvent` | `(self, event)` | Args: |
| `drawBackground` | `(self, painter, rect)` | Args: |
| `dragEnterEvent` | `(self, event)` | Args: |
| `dragMoveEvent` | `(self, event)` | Args: |
| `dropEvent` | `(self, event)` | Args: |
| `keyPressEvent` | `(self, event)` | Args: |

### `CanvasResultsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent = None)` | Args: |
| `_apply_chrome_theme` | `(self)` |  |
| `_build` | `(self)` |  |
| `_update_sel` | `(self, count)` | Args: |
| `_tool_btn_style` | `()` | Returns: |
| `clear_canvas` | `(self)` |  |

## Functions

### `_ual`

```python
def _ual()
```

Return the UserActionLogger, or None if logging isn't ready.

**Returns:**

- `object: Result of the operation.`

### `_dialog_base_style`

```python
def _dialog_base_style()
```

Dialog stylesheet synced to the current app theme. The canvas itself
(nodes, links, grid) keeps the DS design system — those are intentionally
always-dark like the canvas in Figma or Final Cut. But pop-up dialogs
should match whichever theme the user has chosen.

**Returns:**

- `object: Result of the operation.`

### `_canvas_chrome_style`

```python
def _canvas_chrome_style()
```

Stylesheet for the canvas dialog chrome (header, palette, statusbar).
The canvas itself (nodes/links/grid) stays always-dark like Figma.

**Returns:**

- `object: Result of the operation.`

### `_make_viz_icon_node`

```python
def _make_viz_icon_node(grad_colors, icon_name, label, dialog_class)
```

Factory: creates a circular icon node for each visualization type.

**Args:**

- `grad_colors (Any): The grad colors.`
- `icon_name (Any): The icon name.`
- `label (Any): Label text.`
- `dialog_class (Any): The dialog class.`

**Returns:**

- `object: Result of the operation.`

### `show_canvas_results`

```python
def show_canvas_results(parent_window)
```


**Args:**

- `parent_window (Any): The parent window.`
