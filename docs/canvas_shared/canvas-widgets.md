# `canvas_widgets.py`

---

## Constants

| Name | Value |
|------|-------|
| `GROUP_TAG_COLORS` | `['#0072B2', '#E69F00', '#009E73', '#D55E00', '#CC79A7', '…` |
| `_PENDING_DRAG_NODE_TYPE` | `None` |
| `_NODE_IO_FAMILIES` | `{'batch_sample_selector': (None, 'batch'), 'sample_select…` |
| `_NODE_FACTORIES` | `{'sample_selector': SampleSelectorNode, 'multiple_sample_…` |
| `_NODE_ITEM_MAP` | `{'sample_selector': SampleSelectorNodeItem, 'multiple_sam…` |
| `_VIZ_NODE_TYPES` | `frozenset({'histogram_plot', 'element_bar_chart_plot', 'b…` |

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
| `paint_number_badge` | `(self, painter, number)` | Draw the node's Insights number in a small disc on the upper left of its circle. |
| `paint` | `(self, painter, option, widget=None)` |  |
| `_create_anchors` | `(self)` |  |
| `get_anchor` | `(self, channel_name)` |  |
| `boundingRect` | `(self)` |  |
| `shape` | `(self)` |  |
| `hoverEnterEvent` | `(self, event)` |  |
| `hoverLeaveEvent` | `(self, event)` |  |
| `mousePressEvent` | `(self, event)` |  |
| `show_context_menu` | `(self, global_pos)` |  |
| `_temp_wired_both_ends` | `(self)` |  |
| `remove_and_reconnect` | `(self)` |  |
| `manage_connections` | `(self)` |  |
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

### `_RowHighlight`

Finder-style highlighting of sample rows, shared by both selector dialogs.

Click highlights a row, Shift-click a range, Cmd/Ctrl-click adds or
removes one, Cmd/Ctrl+A highlights every shown row and Esc clears. The
dialog then acts on the highlighted rows from its action bar or the
right-click menu. A dialog using it provides ``_visible_samples()``,
``self._hl_row`` (``{sample: row widget}``) and ``_hl_actions()``.

| Method | Signature | Description |
|--------|-----------|-------------|
| `_hl_init` | `(self)` | Start with nothing highlighted. |
| `_hl_track` | `(self, sample, row_w, *parts)` | Make clicks on a row (outside its checkbox and fields) highlight it. |
| `eventFilter` | `(self, obj, event)` | Highlight on a left click on a tracked row. |
| `_hl_click` | `(self, sample, modifiers)` | Apply one click with its modifier keys. |
| `_hl_set` | `(self, samples)` | Highlight exactly *samples*. |
| `_hl_ordered` | `(self)` | Highlighted samples in list order. |
| `_hl_refresh` | `(self)` | Repaint the rows and update the action bar. |
| `_hl_changed` | `(self)` | Hook for dialogs that update other text when the highlight changes. |
| `_hl_build_bar` | `(self)` | The action bar shown under the list while rows are highlighted. |
| `_hl_menu` | `(self, sample, global_pos)` | Right-click menu with the same actions; a click outside the highlight highlights that row. |
| `keyPressEvent` | `(self, event)` | Cmd/Ctrl+A highlights every shown row; Esc clears the highlight before closing. |

### `SampleSelectorDialog` *(extends `_RowHighlight, QDialog`)*

Single-sample configurator: samples on the left, isotope chips on the right.

Each sample shows its particle count. Shift-click ticks a range. The
arrow buttons step to the previous or next sample; when the node passes
``on_step``, each step is applied at once so the connected plots update
while the dialog stays open.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent, samples, current_selection=None, current_isotopes=None,` |  |
| `_build` | `(self)` |  |
| `_make_section_label` | `(self, text)` |  |
| `_build_sample_list` | `(self, samples)` |  |
| `_load_isotopes` | `(self)` |  |
| `_visible_samples` | `(self)` | Samples shown under the current search, in list order. |
| `_on_check` | `(self, sample)` |  |
| `_on_clicked` | `(self, sample, checked)` | Tick or untick a range when Shift is held. |
| `_hl_actions` | `(self)` | What the action bar and right-click menu can do with the highlighted samples. |
| `_include_highlighted` | `(self)` | Tick the highlighted samples. |
| `_exclude_highlighted` | `(self)` | Untick the highlighted samples. |
| `_step` | `(self, delta)` | Show the previous or next sample on its own, and apply it when the node allows. |
| `_filter_samples` | `(self, text)` |  |
| `_select_all` | `(self)` |  |
| `_clear_all` | `(self)` |  |
| `_update_preview` | `(self)` |  |
| `get_selection` | `(self)` |  |

### `MultipleSampleSelectorDialog` *(extends `_RowHighlight, QDialog`)*

Multi-sample configurator: sample list with group fields, plus isotope chips.

Each sample shows its particle count and, once grouped, a colour tag
shared by its group. Shift-click ticks a range; "Group Checked" gives
the ticked samples one group name, suggested from their shared name when
the field is empty.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent, samples, current_selection=None, current_isotopes=None,` |  |
| `_build` | `(self)` |  |
| `_make_section_label` | `(self, text)` |  |
| `_build_sample_list` | `(self, samples)` |  |
| `_load_isotopes` | `(self)` |  |
| `_visible_samples` | `(self)` | Samples shown under the current search, in list order. |
| `_on_change` | `(self, sample)` |  |
| `_on_clicked` | `(self, sample, checked)` | Tick or untick a range when Shift is held. |
| `_filter_samples` | `(self, text)` |  |
| `_select_all` | `(self)` |  |
| `_clear_all` | `(self)` |  |
| `_clear_groups` | `(self)` |  |
| `_group_targets` | `(self)` | The samples Group acts on: the highlighted ones, else the ticked shown ones. |
| `_suggestion` | `(self)` | Suggested group name for the samples Group would act on. |
| `_apply_group_to_checked` | `(self)` | Give the highlighted (or ticked) samples one group name and tick them. |
| `_hl_actions` | `(self)` | What the action bar and right-click menu can do with the highlighted samples. |
| `_include_highlighted` | `(self)` | Tick the highlighted samples. |
| `_exclude_highlighted` | `(self)` | Untick the highlighted samples. |
| `_ungroup_highlighted` | `(self)` | Clear the group of the highlighted samples. |
| `_hl_changed` | `(self)` | Keep the suggested group name in step with the highlight. |
| `_auto_group` | `(self)` | Detect sample groups by stripping common replicate suffixes and numeric endings. |
| `_group_colors` | `(self)` | A colour per group name, in the order the groups first appear. |
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
| `configure` | `(self, parent_window)` | Open the dialog; arrow steps apply at once and Cancel restores the starting selection. |
| `_restore` | `(self, before, applied)` | Put back the selection the dialog started from, after live steps were applied. |
| `_apply_selection` | `(self, selection, parent_window)` | Store a dialog selection on the node and tell the connected nodes. |

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

### `TempPassThroughNode` *(extends `WorkflowNode`)*

Neutral single-input, single-output relay.

Created by "Create Temp Node" (Manage Connections) to hold a fan-out's
sinks in place while the user swaps in a new upstream node — passes its
input straight through unchanged. Deliberately kept single-input, with
no configuration or merge logic of its own: any real multi-source
combining need already has a home in a `supports_multi_input` node
(e.g. the Particle Filter), so this stays a plain relay rather than
becoming a second filter with its own opinions.

Holds NO data of its own — it is pure wiring, not a data bank. Anything
pulling its output reads the current upstream live (``get_output_data``),
and any value pushed into it is forwarded straight on to whatever it
feeds (``process_data`` → ``_forward``). This is what makes a source
swap behave correctly: reconnect a different upstream and the plots
behind the temp update to the new source instead of showing a cached
copy of the old one, and no second copy of the particle data is kept
alive by the temp.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window=None)` |  |
| `_forward` | `(self, data)` | Push a value straight on to every node this temp feeds. |
| `process_data` | `(self, input_data)` |  |
| `get_output_data` | `(self)` |  |

### `ManageConnectionsDialog` *(extends `QDialog`)*

Right-click "Manage Connections" — one checkbox per current link on
this node, checked = keep. Everything is staged locally and only
applied to the scene graph on OK; Cancel touches nothing. "Create Temp
Node" is the one exception — it's a distinct, deliberate compound
action (add a node + rewire several links) and commits immediately
rather than waiting for OK.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, scene, node, parent=None)` |  |
| `_current_output_links` | `(self)` |  |
| `_current_input_links` | `(self)` |  |
| `_temp_connectivity_summary` | `(self)` | Human-readable description of this Temp Node's current, |
| `_build` | `(self)` |  |
| `_section_label` | `(text)` |  |
| `_muted_label` | `(text)` |  |
| `_toggle_all` | `(self, checks)` |  |
| `_create_temp_node` | `(self)` | Insert a TempPassThroughNode between this node and the checked |
| `_apply_and_accept` | `(self)` |  |

### `BatchSampleSelectorDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent_window, previously_selected=None, saved_snapshot=None)` |  |
| `_build` | `(self)` |  |
| `_preview` | `(self)` |  |
| `get_selection` | `(self)` |  |

### `_CalculationWorker` *(extends `QThread`)*

Runs a node's ``get_output_data()`` off the GUI thread.

The Single- and Multi-Sample selector nodes filter and combine the raw
particle data when their selection is confirmed (the OK button). On large
datasets this can take a noticeable amount of time. Doing it here keeps the
canvas responsive instead of freezing while the calculation runs.

The ``finished_ok`` / ``failed`` signals are emitted from the worker thread
but, because the receiving node lives on the GUI thread, Qt delivers them
back on the GUI thread — so the slots are free to touch the scene/UI.

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
| `_cleanup_finished_worker` | `(self)` | Release the worker that just finished, on the GUI thread. |
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

Styled like the figure cards in the spread prototype: a compact white card
with rounded corners, a soft drop shadow and the plot tucked inside.

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

Mirrors the spread prototype: cards emerge from a pivot near the node and
fan out (rotation + scale + fade), staggered.

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
Right-click empty canvas → Add Note. Double-click to edit.

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
| `fit_scene_rect` | `(self)` | Grow or shrink the scrollable area so every item, wherever it is, can be reached. |
| `_on_selection` | `(self)` |  |
| `keyPressEvent` | `(self, event)` |  |
| `undo` | `(self)` | Reverse the last tracked action (add/delete node or link). |
| `delete_selected_items` | `(self)` |  |
| `delete_node` | `(self, ni)` |  |
| `remove_and_reconnect_temp` | `(self, ni)` | Right-click "Remove and Reconnect" on a Temp Node: delete it and |
| `delete_link` | `(self, li)` |  |
| `_clear_if_orphaned` | `(self, node)` | Drop a node's cached input once it has no incoming link left. |
| `_clear_node_data` | `(self, node)` |  |
| `duplicate_selected_nodes` | `(self)` |  |
| `duplicate_node` | `(self, ni)` |  |
| `node_box` | `(self, item)` | The ``(left, top, right, bottom)`` a node item takes up on the canvas. |
| `node_boxes` | `(self, skip=())` | Boxes of every node item, leaving out the workflow nodes in *skip*. |
| `arrange_nodes` | `(self, animate=True)` | Tidy every node into columns by data flow; Ctrl+Z puts them back. |
| `_animate_to` | `(self, positions, animate=True, msec=320)` | Move node items to *positions* (``workflow node -> QPointF``), gliding when asked. |
| `select_all_items` | `(self)` |  |
| `_assign_insights_number` | `(self, wf_node)` | Give a Single or Multi-Sample node a number no other node on the canvas carries. |
| `add_node` | `(self, wf_node, pos)` |  |
| `_reaches` | `(self, start, target)` | True if ``target`` is reachable downstream from ``start``. |
| `_direct_link_allowed` | `(self, src_node, snk_node)` | Whether src_node -> snk_node is a valid link on its own terms. |
| `_temp_real_peers` | `(self, temp, direction, _seen=None)` | The real (non-temp) node(s) currently wired to ``temp`` on |
| `_check_link_allowed` | `(self, src_node, snk_node)` | Temp-aware connectivity check wrapping _direct_link_allowed. |
| `add_link` | `(self, src_node, src_ch, snk_node, snk_ch)` |  |
| `_trigger_data_flow` | `(self, wl)` |  |
| `flush_data_flow` | `(self)` | Push each node's output to its sinks exactly once, sources first. |
| `_flush_data_flow_inner` | `(self)` | The topological push itself; see :meth:`flush_data_flow`. |
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
| `_is_trackpad` | `(event)` | Whether a wheel event comes from a trackpad swipe rather than a mouse wheel. |
| `wheelEvent` | `(self, event: QWheelEvent)` | Swipe on a trackpad to move around; pinch, Cmd/Ctrl + scroll or a mouse wheel to zoom. |
| `viewportEvent` | `(self, event)` | Zoom on a trackpad pinch. |
| `_zoom_by` | `(self, factor)` | Zoom by *factor*, kept between MIN_ZOOM and MAX_ZOOM. |
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
| `_apply_chrome_theme` | `(self)` | Re-style the dialog chrome and its header controls for the current theme. |
| `_logo_style` | `()` |  |
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
| `_combine_concentration_meta` | `(metas, dilution_resolution=None)` | Combine per member concentration metadata into a single entry. |
| `_warn_before_apply_changes` | `(parent, node)` | Remind the user that applying this node's configuration now may |
| `_dialog_base_style` | `()` | Dialog stylesheet synced to the current app theme. The canvas itself |
| `_canvas_chrome_style` | `()` | Stylesheet for the canvas dialog chrome (header, palette, statusbar). |
| `sample_particle_counts` | `(parent_window, samples, batch_particle_data=None)` | Particles per sample, for showing next to each name in the selectors. |
| `suggest_group_name` | `(names)` | A group name for several samples: their shared replicate root or common prefix. |
| `_count_text` | `(n)` | Short particle count for a sample row. |
| `_shift_held` | `()` | Whether Shift is held, for range selection in the sample lists. |
| `_checkbox_style` | `(p)` | Checkbox look shared by both sample lists. |
| `_step_button` | `(text, tip)` | A small arrow button for stepping through samples. |
| `_style_sample_scroll` | `(scroll, container)` | Let the sample list paint the themed background set in the dialog style. |
| `_make_viz_icon_node` | `(grad_colors, icon_name, label, dialog_class, multi_figure=False)` | Factory: creates a circular icon node for each visualization type. |
| `_io_families` | `(node)` | Return (input_family, output_family) for a node. |
| `validate_classifier_link` | `(src_node, snk_node)` | Check a proposed link against Particle Classifier connectivity rules. |
| `show_canvas_results` | `(parent_window)` |  |
