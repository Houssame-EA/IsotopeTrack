# `canvas_widgets.py`

---

## Constants

| Name | Value |
|------|-------|
| `_PENDING_DRAG_NODE_TYPE` | `None` |
| `_NODE_FACTORIES` | `{'sample_selector': SampleSelectorNode, 'multiple_sample_…` |
| `_NODE_ITEM_MAP` | `{'sample_selector': SampleSelectorNodeItem, 'multiple_sam…` |

## Classes

### `DS`

| Method | Signature | Description |
|--------|-----------|-------------|
| `font` | `(size=None, bold=False)` |  |
| `pen` | `(color, width=1.0)` |  |
| `brush` | `(color)` |  |

### `WorkflowLink` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, source_node, source_channel, sink_node, sink_channel)` |  |
| `get_data` | `(self)` |  |

### `WorkflowNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, title, node_type)` |  |
| `set_position` | `(self, pos)` |  |
| `configure` | `(self, parent_window)` | Args: |

### `AnchorPointSignals` *(extends `QObject`)*

### `AnchorPoint` *(extends `QGraphicsEllipseItem`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent, channel_name, is_input=True)` |  |
| `_apply_style` | `(self, hover=False)` |  |
| `itemChange` | `(self, change, value)` |  |
| `shape` | `(self)` | Creates an invisible, larger hitbox for easier clicking and dragging. |
| `hoverEnterEvent` | `(self, event)` |  |
| `hoverLeaveEvent` | `(self, event)` |  |
| `set_drag_target` | `(self, state)` | Highlight this input port while a connection is being dragged. |

### `NodeItem` *(extends `QGraphicsWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, workflow_node, parent=None)` |  |
| `paint_icon_node` | `(self, painter, grad_colors, icon_name, label_text, badge_text='', bad` | Paint a circular icon node with its label. |
| `paint` | `(self, painter, option, widget=None)` |  |
| `_create_anchors` | `(self)` |  |
| `get_anchor` | `(self, channel_name)` |  |
| `boundingRect` | `(self)` |  |
| `shape` | `(self)` |  |
| `hoverEnterEvent` | `(self, event)` |  |
| `hoverLeaveEvent` | `(self, event)` |  |
| `mousePressEvent` | `(self, event)` |  |
| `show_context_menu` | `(self, global_pos)` |  |
| `_ctx_menu_style` | `()` |  |
| `duplicate_node` | `(self)` |  |
| `delete_node` | `(self)` |  |
| `itemChange` | `(self, change, value)` |  |
| `mouseDoubleClickEvent` | `(self, event)` |  |
| `configure_node` | `(self)` |  |

### `LinkCurveItem` *(extends `QGraphicsWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `_advance_dots` | `(self)` |  |
| `set_curve_path` | `(self, path)` |  |
| `set_pen` | `(self, pen)` |  |
| `boundingRect` | `(self)` |  |
| `paint` | `(self, painter, option, widget=None)` |  |
| `hoverEnterEvent` | `(self, event)` |  |
| `hoverLeaveEvent` | `(self, event)` |  |

### `LinkItem` *(extends `QGraphicsWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `set_source_anchor` | `(self, anchor)` |  |
| `set_sink_anchor` | `(self, anchor)` |  |
| `set_workflow_link` | `(self, link)` |  |
| `__update_curve` | `(self)` |  |
| `boundingRect` | `(self)` |  |
| `shape` | `(self)` |  |
| `mousePressEvent` | `(self, event)` |  |
| `_show_ctx` | `(self, pos)` |  |
| `delete_connection` | `(self)` |  |
| `hoverEnterEvent` | `(self, event)` |  |
| `hoverLeaveEvent` | `(self, event)` |  |
| `itemChange` | `(self, change, value)` |  |
| `mouseDoubleClickEvent` | `(self, event)` |  |

### `SampleSelectorDialog` *(extends `QDialog`)*

Simplified single-sample configurator: samples on left, isotope chips on right.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent, samples, current_selection=None, current_isotopes=None,` |  |
| `_build` | `(self)` |  |
| `_make_section_label` | `(self, text)` |  |
| `_build_sample_list` | `(self, samples)` |  |
| `_load_isotopes` | `(self)` |  |
| `_on_check` | `(self, sample)` |  |
| `_filter_samples` | `(self, text)` |  |
| `_select_all` | `(self)` |  |
| `_clear_all` | `(self)` |  |
| `_update_preview` | `(self)` |  |
| `get_selection` | `(self)` |  |

### `MultipleSampleSelectorDialog` *(extends `QDialog`)*

Simplified multi-sample configurator: sample list with inline group fields + isotope chips.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent, samples, current_selection=None, current_isotopes=None,` |  |
| `_build` | `(self)` |  |
| `_make_section_label` | `(self, text)` |  |
| `_build_sample_list` | `(self, samples)` |  |
| `_load_isotopes` | `(self)` |  |
| `_on_change` | `(self, sample)` |  |
| `_filter_samples` | `(self, text)` |  |
| `_select_all` | `(self)` |  |
| `_clear_all` | `(self)` |  |
| `_clear_groups` | `(self)` |  |
| `_apply_group_to_checked` | `(self)` |  |
| `_auto_group` | `(self)` | Detect sample groups by stripping common replicate suffixes and numeric endings. |
| `_update_preview` | `(self)` |  |
| `get_selection` | `(self)` |  |

### `SampleSelectorNode` *(extends `WorkflowNode`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `process_data` | `(self, input_data)` |  |
| `get_output_data` | `(self)` |  |
| `_get_particles` | `(self)` |  |
| `_filter` | `(self, particles)` |  |
| `_sample_data` | `(self)` |  |
| `configure` | `(self, parent_window)` |  |

### `MultipleSampleSelectorNode` *(extends `WorkflowNode`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `process_data` | `(self, input_data)` |  |
| `get_output_data` | `(self)` |  |
| `_add_individual` | `(self, name, src, out)` |  |
| `_add_group` | `(self, gname, members, out)` |  |
| `_raw_particles` | `(self, sample)` |  |
| `_filter` | `(self, particles)` |  |
| `configure` | `(self, parent_window)` |  |

### `BatchSampleSelectorNode` *(extends `WorkflowNode`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `get_output_data` | `(self)` | Combined dataset for the selected windows. |
| `configure` | `(self, parent_window)` | Open the window selector; selecting live windows rebuilds the batch. |

### `BatchSampleSelectorDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window, previously_selected=None, saved_snapshot=None)` |  |
| `_build` | `(self)` |  |
| `_preview` | `(self)` |  |
| `get_selection` | `(self)` |  |

### `_CalculationWorker` *(extends `QThread`)*

Runs a node's ``get_output_data()`` off the GUI thread.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, compute_fn, parent=None)` |  |
| `run` | `(self)` | Execute the calculation and report the result via a signal. |

### `_StatusNodeMixin`

Adds status badge rendering to icon nodes.

| Method | Signature | Description |
|--------|-----------|-------------|
| `_status_text` | `(self)` |  |
| `_status_color` | `(self)` |  |
| `_is_calc_busy` | `(self)` | Return True while a background calculation is running. |
| `_run_calculation_async` | `(self)` | Compute this node's output in a background thread, then push the |
| `_on_calc_done` | `(self, result)` | Deliver the freshly computed output to every connected sink. |
| `_on_calc_failed` | `(self, message)` | Handle a failed background calculation. |
| `_cleanup_worker` | `(self, worker)` | Drop a finished worker so it can be garbage-collected. |

### `SampleSelectorNodeItem` *(extends `NodeItem, _StatusNodeMixin`)*

Single beaker icon.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, wf, pw=None)` |  |
| `paint` | `(self, painter, option, widget=None)` |  |
| `_trigger` | `(self)` | Run the node calculation in a background thread on (re)configure. |
| `configure_node` | `(self)` |  |
| `_build_tooltip_lines` | `(self)` |  |
| `_show_tooltip` | `(self)` |  |
| `hoverEnterEvent` | `(self, event)` |  |
| `hoverMoveEvent` | `(self, event)` |  |
| `hoverLeaveEvent` | `(self, event)` |  |

### `ModernNodeTooltip` *(extends `QWidget`)*

Custom floating tooltip with glow effect.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `set_content` | `(self, lines, accent_color=None)` |  |
| `_recompute_size` | `(self)` |  |
| `_title_font` | `(self)` |  |
| `_body_font` | `(self)` |  |
| `paintEvent` | `(self, event)` |  |

### `FigurePreviewPopup` *(extends `QWidget`)*

Small framed thumbnail preview of a node's figure, shown on hover.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `set_pixmap` | `(self, pm, accent=None)` | Set the preview thumbnail and resize the card to fit it. |
| `paintEvent` | `(self, event)` | Paint a soft-shadowed white card with the figure thumbnail inside. |

### `_FanCardItem` *(extends `QGraphicsObject`)*

One animated figure card in the hover fan (rotates/scales into place).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, view, accent, pm)` |  |
| `boundingRect` | `(self)` |  |
| `paint` | `(self, p, opt, widget=None)` | Draw the white card, the clipped plot image, the accent border and |
| `mousePressEvent` | `(self, event)` | Emit ``killed`` when the ✕ is clicked, otherwise ``selected``. |
| `hoverEnterEvent` | `(self, event)` |  |
| `hoverLeaveEvent` | `(self, event)` |  |
| `_scale_to` | `(self, scale)` | Animate the card to ``scale`` (used for the hover pop). |
| `animate_to` | `(self, pos, rot, scale, opac, delay, dur=440)` | Animate position, rotation, scale and opacity together (after an |

### `FigureFanPopup` *(extends `QWidget`)*

Hover fan of a node's open figures: spread, animated cards you pick/kill.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `eventFilter` | `(self, obj, event)` | Forward viewport enter/leave to the on_enter/on_leave callbacks. |
| `has_cards` | `(self)` | True if the fan currently holds any figure cards. |
| `_placeholder_pixmap` | `(self, w, idx, accent)` | A neutral 'Figure N' card image for a restored figure with no thumbnail. |
| `set_views` | `(self, views, accent, zoom=1.0)` | Build one card per figure view and fan them out around a pivot. |
| `enterEvent` | `(self, event)` |  |
| `leaveEvent` | `(self, event)` |  |

### `StickyNoteItem` *(extends `QGraphicsWidget`)*

A movable, editable sticky note with color, font-size and transparency support.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, text='Double-click to edit…', parent=None)` |  |
| `_current_colors` | `(self)` | Return (bg_color, border_color, text_color) based on current settings. |
| `boundingRect` | `(self)` |  |
| `paint` | `(self, painter, option, widget=None)` |  |
| `hoverEnterEvent` | `(self, event)` |  |
| `hoverLeaveEvent` | `(self, event)` |  |
| `mouseDoubleClickEvent` | `(self, event)` |  |
| `mousePressEvent` | `(self, event)` |  |
| `_show_context_menu` | `(self, global_pos)` |  |
| `_set_color` | `(self, index)` |  |
| `_set_font_size` | `(self, size)` |  |
| `_toggle_transparent` | `(self)` |  |
| `_delete_self` | `(self)` |  |

### `MultipleSampleSelectorNodeItem` *(extends `NodeItem, _StatusNodeMixin`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, wf, pw=None)` |  |
| `paint` | `(self, painter, option, widget=None)` |  |
| `_trigger` | `(self)` | Run the node calculation in a background thread on (re)configure. |
| `configure_node` | `(self)` |  |
| `_build_tooltip_lines` | `(self)` |  |
| `_show_tooltip` | `(self)` |  |
| `hoverEnterEvent` | `(self, event)` |  |
| `hoverMoveEvent` | `(self, event)` |  |
| `hoverLeaveEvent` | `(self, event)` |  |

### `BatchSampleSelectorNodeItem` *(extends `NodeItem, _StatusNodeMixin`)*

Globe / multi-window icon.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, wf, pw=None)` |  |
| `paint` | `(self, painter, option, widget=None)` |  |
| `_trigger` | `(self)` |  |
| `configure_node` | `(self)` |  |

### `AIAssistantNodeItem` *(extends `NodeItem`)*

AI sparkle icon.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, wf, pw=None)` |  |
| `paint` | `(self, painter, option, widget=None)` |  |
| `configure_node` | `(self)` |  |

### `DraggableNodeButton` *(extends `QPushButton`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, text, node_type, icon_name=None, color=None)` |  |
| `_refresh_style` | `(self)` |  |
| `mousePressEvent` | `(self, event)` |  |

### `_CollapsibleGroup` *(extends `QWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, title, parent=None)` |  |
| `_apply_theme` | `(self)` |  |
| `addWidget` | `(self, w)` |  |
| `toggle` | `(self)` |  |

### `NodePalette` *(extends `QWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `_setup` | `(self)` |  |
| `_apply_palette_theme` | `(self)` |  |
| `_filter` | `(self, text)` |  |

### `EnhancedCanvasScene` *(extends `QGraphicsScene`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `_on_selection` | `(self)` |  |
| `keyPressEvent` | `(self, event)` |  |
| `undo` | `(self)` | Reverse the last tracked action (add/delete node or link). |
| `delete_selected_items` | `(self)` |  |
| `delete_node` | `(self, ni)` |  |
| `delete_link` | `(self, li)` |  |
| `duplicate_selected_nodes` | `(self)` |  |
| `duplicate_node` | `(self, ni)` |  |
| `select_all_items` | `(self)` |  |
| `add_node` | `(self, wf_node, pos)` |  |
| `add_link` | `(self, src_node, src_ch, snk_node, snk_ch)` |  |
| `_trigger_data_flow` | `(self, wl)` |  |
| `contextMenuEvent` | `(self, event)` | Right-click on empty canvas space → canvas context menu. |
| `mousePressEvent` | `(self, event)` |  |
| `mouseMoveEvent` | `(self, event)` |  |
| `mouseReleaseEvent` | `(self, event)` |  |
| `_nearest_candidate` | `(self, pos, radius)` | Closest highlighted input anchor to ``pos`` within ``radius``, or None. |
| `_start_drag` | `(self, anchor, pos)` | Begin a connection drag from ``anchor``. |
| `_end_drag` | `(self, pos)` | Finish a connection drag. |

### `EnhancedCanvasView` *(extends `QGraphicsView`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `_apply_view_theme` | `(self)` |  |
| `_safe_apply_view_theme` | `(self)` |  |
| `_view_disconnect_theme` | `(self)` |  |
| `_setup_shortcuts` | `(self)` |  |
| `wheelEvent` | `(self, event: QWheelEvent)` |  |
| `set_zoom` | `(self, value)` |  |
| `fit_content` | `(self)` |  |
| `mousePressEvent` | `(self, event)` |  |
| `mouseMoveEvent` | `(self, event)` |  |
| `mouseReleaseEvent` | `(self, event)` |  |
| `drawBackground` | `(self, painter, rect)` |  |
| `drawForeground` | `(self, painter, rect)` | Draw a centered hint while the canvas has no result blocks yet. |
| `_drag_node_type` | `(self, event)` | Return the node type carried by a drag/drop event, or None. |
| `dragEnterEvent` | `(self, event)` |  |
| `dragMoveEvent` | `(self, event)` |  |
| `dropEvent` | `(self, event)` |  |
| `keyPressEvent` | `(self, event)` |  |

### `CanvasResultsDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `_apply_chrome_theme` | `(self)` |  |
| `_build` | `(self)` |  |
| `_update_sel` | `(self, count)` |  |
| `_tool_btn_style` | `()` |  |
| `clear_canvas` | `(self)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_ual` | `()` | Return the UserActionLogger, or None if logging isn't ready. |
| `_collect_main_windows` | `()` | Return every visible MainWindow in this process. |
| `_sample_concentration_meta` | `(window, sample_name)` | Build the per sample concentration metadata for a source window. |
| `_combine_concentration_meta` | `(metas)` | Combine per member concentration metadata into a single entry. |
| `_dialog_base_style` | `()` | Dialog stylesheet synced to the current app theme. The canvas itself |
| `_canvas_chrome_style` | `()` | Stylesheet for the canvas dialog chrome (header, palette, statusbar). |
| `_make_viz_icon_node` | `(grad_colors, icon_name, label, dialog_class, multi_figure=False)` | Factory: creates a circular icon node for each visualization type. |
| `show_canvas_results` | `(parent_window)` |  |
