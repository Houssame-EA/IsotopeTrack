# `dialog.py`

The AI Data Assistant chat window.

A question goes through three steps. The model writes code; the sandbox runs
it on the full particle table and the tables and figures appear in the
chat. If the code fails or a figure comes out empty, the model is shown the
problem and fixes it. Finally the model sees the exact results and writes
the takeaway, and any figure in that text that the code did not produce is
flagged.

Explore runs the same loop for several turns, keeping a plan and a ledger
of findings outside the chat history so nothing is lost when old messages
are trimmed, and writes its summary from that ledger.

---

## Constants

| Name | Value |
|------|-------|
| `MAX_FIX_ATTEMPTS` | `3` |
| `MAX_FIGURE_FIXES` | `1` |

## Classes

### `AIChatDialog` *(extends `QDialog`)*

Chat window of the AI Assistant node.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, ai_node, pw=None)` | Build the window. |
| `_cur` | `(self)` | The conversation on screen. |
| `_history` | `(self)` | Chat history of the conversation on screen. |
| `_widgets` | `(self)` | Widgets of the conversation on screen. |
| `_cl` | `(self)` | Layout holding the conversation's bubbles. |
| `_cw` | `(self)` | Widget holding the conversation's bubbles. |
| `_scroll` | `(self)` | Scroll area of the conversation on screen. |
| `_num_ctx` | `(self)` | Context window of the configured model. |
| `_worker_cfg` | `(self)` | Backend settings for one request, with the reply budget set. |
| `_system_prompt` | `(self, mode='chat')` | System prompt for the current data, cached until the data changes. |
| `_add_widget` | `(self, w)` | Append a widget to the conversation on screen. |
| `_record` | `(self, kind, **data)` | Add an entry to the conversation's report transcript. |
| `_busy` | `(self, label)` | Lock the input while the model works. |
| `_idle` | `(self)` | Unlock the input after the model finished and release the worker. |
| `_arm_idle_timer` | `(self)` | Start the countdown after which the model's memory is freed. |
| `_on_idle_timeout` | `(self)` | Free the model's memory after the idle time, unless work is still running. |
| `_free_model_memory` | `(self, reason='')` | Unload the model so its memory goes back to other programs. |
| `_mlx_needs_start` | `(self)` | Whether the chosen MLX model is on this computer but its server is not running. |
| `_start_mlx_then` | `(self, action)` | Start the MLX server for the chosen model, then run *action* once it answers. |
| `_poll_loading` | `(self)` | Wait for the MLX server to answer, then continue with the pending action. |
| `_mark_reloaded` | `(self)` | Turn the status back to connected once a freed model is used again. |
| `_start_worker` | `(self, messages, system, on_done, on_error=None, stream_to_bubble=True` | Start one streaming request. |
| `_send` | `(self)` | Send the composer text as a question about the data. |
| `_request_answer` | `(self)` | Ask the model for an answer to the latest message. |
| `_run_codes` | `(self, codes, on_done)` | Run code blocks one after the other in the background. |
| `_next_code` | `(self)` | Start the next queued code block, or hand all results on. |
| `_hold_focus` | `(self)` | Keep the chat window in front while results are being added. |
| `_on_code_result` | `(self, code, res)` | Keep one code block's result and move on to the next. |
| `_show_result` | `(self, code, res)` | Put a result's tables, figures and text in the chat. |
| `_record_result` | `(self, code, res)` | Add a successful result to the report transcript. |
| `_on_done` | `(self, full)` | Handle the model's answer: run its code, fix problems, then explain. |
| `_after_codes` | `(self, results)` | Show the results, ask for fixes when needed, then ask for the takeaway. |
| `_on_interpret_done` | `(self, full)` | Show the grounded takeaway and check its numbers. |
| `_finish_turn` | `(self)` | End a question: scroll, unlock the input. |
| `_on_err` | `(self, err)` | Show a backend error and unlock the input. |
| `_do_stop` | `(self)` | Stop the request in progress. |
| `_clear_chat` | `(self)` | Empty the conversation on screen. |
| `_explore` | `(self)` | Start a multi-turn exploration of the data. |
| `_await_first_look` | `(self, thread, holder, state)` | Start the first turn once the first look is ready. |
| `_run_exploration_turn` | `(self)` | Ask the model for its next query. |
| `_on_exp_turn_done` | `(self, full)` | Run the turn's code, record findings and continue or finish. |
| `_on_exp_code_done` | `(self, results, rationale, done)` | Record a turn's result and continue or finish the exploration. |
| `_on_exp_err` | `(self, err)` | Handle a backend error during exploration. |
| `_finalize_exploration` | `(self, reason='')` | Ask for the final summary, written from the recorded findings. |
| `_on_exp_summary_done` | `(self, full)` | Show the summary, check its numbers and keep it in the chat history. |
| `_on_exp_summary_err` | `(self, err)` | Handle a failed summary request. |
| `_keep_unfinished_exploration` | `(self, reason)` | Keep what an exploration found when it ends before its summary. |
| `_teardown_exploration` | `(self)` | Forget the exploration state. |
| `update_data_context` | `(self, data)` | Receive new particle data from the node. |
| `_update_sug` | `(self, data)` | Rebuild the suggestion chips for the current data and enable Explore. |
| `_export_report` | `(self)` | Save the conversation on screen as an HTML report. |
| `_tool` | `(self, text, icon, tip, slot)` | A toolbar button in the Figure Builder style. |
| `_sep` | `(self)` | A thin vertical separator for the toolbar. |
| `_build_ui` | `(self)` | Build the toolbar, conversation list, chat panel and composer. |
| `_toggle_sidebar` | `(self)` | Show or hide the conversation list. |
| `_open_settings` | `(self)` | Open the backend settings and apply the chosen model. |
| `_open_customize` | `(self)` | Open the appearance settings. |
| `_update_counter` | `(self, n_chars)` | Show the composer's character count and token estimate. |
| `eventFilter` | `(self, obj, event)` | Outline the message box while the user is typing in it. |
| `_add_conv_list_item` | `(self, conv, is_current=False)` | Create the sidebar entry for an existing Conversation. |
| `_new_conversation` | `(self, switch_to=True)` | Create a new conversation, add it to the stack and sidebar. |
| `_switch_conversation` | `(self, conv_id)` | Switch to the conversation with the given id. Saves the current draft |
| `_delete_conversation` | `(self, conv_id)` | Delete a conversation. If it's the current one, switch to a neighbour. |
| `_maybe_set_conv_title` | `(self, text)` | If the current conversation still has its auto-generated title and |
| `_set_sidebar_enabled` | `(self, enabled)` | Enable/disable conversation switching (used during streaming). |
| `_attach_file` | `(self)` | Let the user attach an image, PDF or text file to the next message. |
| `_add_preview` | `(self, name, kind, entry, image_b64=None)` | Show an inline preview chip inside the composer |
| `_remove_preview` | `(self, prev)` | Remove one preview chip and its pending file. |
| `_clear_attachments` | `(self)` | Remove every pending attachment from the composer. |
| `_on_composer_resize` | `(self, dy)` | User dragged the resize handle. dy > 0 = drag down (shrink), |
| `_reset_composer_height` | `(self)` | Double-click on the handle → back to auto-grow. |
| `_on_tok` | `(self, t)` | Append a streamed token to the live reply. |
| `_on_usage` | `(self, prompt_tokens, completion_tokens)` | Show the token counts reported by the backend for the last reply. |
| `_on_stats` | `(self, n, el)` | Show the generation speed. |
| `_enable` | `(self)` | Re-enable the composer and the sidebar. |
| `_style_sug_btn` | `(self, btn)` | Mark a suggestion chip for the window stylesheet. |
| `_update_sug_style` | `(self)` | Kept for callers; chips are styled by the window stylesheet. |
| `_on_global_theme_change` | `(self, name)` | Follow the application theme. |
| `_window_qss` | `(self)` | The Figure Builder stylesheet plus the chat window's own pieces. |
| `_set_dot` | `(self, kind)` | Colour the connection dot. |
| `_apply_theme` | `(self)` | Restyle the whole window for the current theme and font size. |
| `_add_user` | `(self, t)` | Show a user message. |
| `_add_ai` | `(self, t)` | Show an assistant message. |
| `_scrollb` | `(self, force=False)` | Scroll the chat to the newest message, unless the user scrolled up to read. |
| `_start_autodetect` | `(self)` | Probe loopback for a running model server and self-configure, so the |
| `_on_autodetect` | `(self, backend, model, label)` | Apply a detected backend unless the user already picked one. |
| `_on_autodetect_info` | `(self, msg)` | Show a hint from the server probe. |
| `_eject_model` | `(self)` | Free the memory held by the model currently loaded. |
| `_set_disconnected_status` | `(self)` | Reset the header indicator after a model has been unloaded. |
| `shutdown` | `(self, release=False)` | Stop background work, and optionally free the model's memory. |
| `closeEvent` | `(self, event)` | Stop any running request when the window closes, and free the model's memory if set to. |
| `_set_connected_status` | `(self, label)` | Turn the header indicator green and show the active backend label. |
| `_ensure_backend_ready` | `(self)` | Detect a local server on demand when nothing is configured yet. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_icon` | `(name, color)` | A qtawesome icon, or an empty icon when qtawesome is unavailable. |
