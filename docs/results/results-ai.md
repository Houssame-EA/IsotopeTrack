# `results_AI.py`

---

## Constants

| Name | Value |
|------|-------|
| `OLLAMA_BASE` | `'http://localhost:11434'` |
| `OLLAMA_CHAT` | `f'{OLLAMA_BASE}/api/chat'` |
| `OLLAMA_TAGS` | `f'{OLLAMA_BASE}/api/tags'` |
| `MLX_BASE` | `'http://localhost:8080'` |
| `MLX_CHAT` | `f'{MLX_BASE}/v1/chat/completions'` |
| `MLX_MODELS` | `f'{MLX_BASE}/v1/models'` |
| `CODE_EXEC_TIMEOUT` | `30` |
| `CHARS_PER_TOKEN` | `3.5` |
| `STREAM_RENDER_INTERVAL` | `80` |
| `_UI_PREFS` | `{'font_size': 14, 'chart_dpi': 100, 'show_timestamps': Fa…` |
| `_SAFE_BUILTINS` | `{'abs': abs, 'all': all, 'any': any, 'bool': bool, 'dict'…` |
| `_CODE_RE` | `re.compile('```python\\s*\\n(.*?)```', re.DOTALL)` |
| `_THINK_RE` | `re.compile('<think>.*?</think>', re.DOTALL)` |
| `_IMPORT_RE` | `re.compile('^\\s*(?:import\\s+\\w+\|from\\s+\\w+\\s+import…` |
| `_BLOCKED_CALL_NAMES` | `frozenset({'open', 'eval', 'exec', 'compile', '__import__…` |
| `_BLOCKED_ATTRS` | `frozenset({'save', 'savez', 'savez_compressed', 'load', '…` |
| `_FLOAT_TOKEN_RE` | `re.compile('[-+]?\\d[\\d,]*\\.\\d+')` |
| `_ANYNUM_TOKEN_RE` | `re.compile('[-+]?\\d[\\d,]*\\.\\d+\|[-+]?\\d[\\d,]*')` |
| `_MAX_STDOUT_CHARS` | `20000` |
| `IMAGE_EXTS` | `{'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'ima…` |
| `TEXT_EXTS` | `{'.txt', 'csv', '.json', '.md', '.tsv', '.xml'}` |

## Classes

### `Theme`

| Method | Signature | Description |
|--------|-----------|-------------|
| `is_dark` | `(cls)` |  |
| `toggle` | `(cls)` |  |
| `sync_with_global` | `(cls)` |  |
| `c` | `(cls, key)` |  |

### `StreamWorker` *(extends `QThread`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, backend, msgs, sys_prompt, config, attachments=None)` |  |
| `stop` | `(self)` |  |
| `run` | `(self)` |  |
| `_inject_attachments` | `(self, messages)` | Inject pending file/image attachments into the last user message. |
| `_inject_attachments_openai` | `(self, messages)` | OpenAI-style multipart content for MLX vision. |
| `_run_ollama` | `(self)` |  |
| `_stream_ndjson` | `(self)` |  |
| `_run_mlx` | `(self)` |  |
| `_stream_sse` | `(self)` |  |
| `_run_custom_api` | `(self)` |  |
| `_finish` | `(self, full, tc, t0)` |  |

### `ProbeWorker` *(extends `QThread`)*

Briefly probe localhost for a running model server so the assistant can
self-configure on first open — no need to visit settings. Ollama is checked
first, then MLX. Emits at most one signal.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, mlx_host=MLX_BASE)` |  |
| `run` | `(self)` |  |

### `BackendDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, current_cfg, parent=None)` |  |
| `_on_backend` | `(self, idx)` |  |
| `_fetch_ollama_models` | `(self)` |  |
| `_test_mlx` | `(self)` |  |
| `_test_custom` | `(self)` |  |
| `get_config` | `(self)` |  |

### `AttachmentChip` *(extends `QFrame`)*

Visual file-attachment card on the user side. No thumbnail — just icon + name + info.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, name, kind, info='')` |  |
| `apply_theme` | `(self)` |  |
| `__init__` | `(self, text, is_user=False)` |  |
| `_copy_text` | `(self)` |  |
| `apply_theme` | `(self)` |  |

### `AttachmentPreview` *(extends `QFrame`)*

with an image thumbnail (or file icon), filename, and a remove (×) button
overlaid on the top-right corner.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, name, kind, image_b64=None)` |  |
| `resizeEvent` | `(self, event)` |  |
| `apply_theme` | `(self)` |  |

### `TextBubble` *(extends `QFrame`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, text, is_user=False)` |  |
| `_copy_text` | `(self)` |  |
| `apply_theme` | `(self)` |  |

### `StreamBubble` *(extends `QFrame`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` |  |
| `append` | `(self, tok)` |  |
| `_flush` | `(self)` |  |
| `finalise` | `(self)` |  |
| `get_text` | `(self)` |  |
| `apply_theme` | `(self)` |  |

### `ExplorationBubble` *(extends `QFrame`)*

Collapsible bubble showing an exploration session.

Layout:
  ┌─────────────────────────────────────────┐
  │ Exploring: <question>                │
  │ Turn 3 of 10 — running query…           │
  │ [▶ Show 3 steps]                         │
  │                                          │
  │   ── steps area (hidden by default) ──   │
  │   Turn 1: <code>                         │
  │     stdout / table / chart               │
  │   Turn 2: <code>                         │
  │     ...                                  │
  │                                          │
  │ ── Findings ──                           │
  │ <final summary text>                     │
  └─────────────────────────────────────────┘

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, question)` |  |
| `set_progress` | `(self, turn, max_turns, text='')` |  |
| `add_step` | `(self, turn_num, ai_rationale, code, text_out, tables, charts, error)` | Add a step to the exploration record. Each step gets a compact |
| `set_summary` | `(self, summary_md)` | Mark exploration complete and display the final summary. |
| `mark_cancelled` | `(self, reason='stopped by user')` | Exploration was interrupted before finishing. |
| `_toggle_expand` | `(self)` |  |
| `_build_step_widget` | `(self, turn_num, rationale, code, text_out, tables, charts, error)` | Build the compact display for one exploration step. |
| `apply_theme` | `(self)` |  |

### `_NumericItem` *(extends `QTableWidgetItem`)*

QTableWidgetItem that sorts numerically when possible.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__lt__` | `(self, other)` |  |

### `InteractiveTableBubble` *(extends `QFrame`)*

Sortable, filterable table with stats panel, chart type selector, and CSV export.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, headers, rows, title='Query result')` |  |
| `_populate` | `(self, rows)` |  |
| `_apply_filter` | `(self, text)` |  |
| `_on_col_click` | `(self, col_idx)` | Select the clicked column in the stats combo and show stats. |
| `_toggle_stats` | `(self, checked)` |  |
| `_refresh_stats` | `(self)` |  |
| `_switch` | `(self, idx)` |  |
| `_set_chart_kind` | `(self, kind)` |  |
| `_draw_chart` | `(self)` |  |
| `_save_chart_png` | `(self)` |  |
| `_copy_tsv` | `(self)` |  |
| `_export_csv` | `(self)` |  |
| `apply_theme` | `(self)` |  |

### `OutputBubble` *(extends `QFrame`)*

Fallback plain-text output for non-tabular results.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, text)` |  |
| `apply_theme` | `(self)` |  |

### `ErrorBubble` *(extends `QFrame`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, err)` |  |
| `apply_theme` | `(self)` |  |

### `ChartBubble` *(extends `QFrame`)*

Renders charts from sandbox show_chart/show_pie/show_histogram calls.
Includes a type-switcher bar so the user can flip between bar/barh/pie/line.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, chart_data)` |  |
| `_switch_type` | `(self, kind)` |  |
| `_save_png` | `(self)` |  |
| `_render` | `(self)` |  |
| `apply_theme` | `(self)` |  |

### `AutoGrowTextEdit` *(extends `QPlainTextEdit`)*

Text input that grows and shrinks with content. Enter sends; Shift+Enter newline.
Can also be manually resized via set_forced_height() — when set, auto-grow is
bypassed and the input stays at the user-chosen height.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `set_forced_height` | `(self, h)` | Lock the input to a specific height (in px). Pass None to re-enable |
| `get_forced_height` | `(self)` |  |
| `_on_changed` | `(self)` |  |
| `_adjust` | `(self)` |  |
| `resizeEvent` | `(self, event)` |  |
| `keyPressEvent` | `(self, event)` |  |
| `text` | `(self)` |  |
| `setText` | `(self, t)` |  |
| `clear` | `(self)` |  |

### `ComposerResizeHandle` *(extends `QFrame`)*

Thin horizontal bar at the top of the composer — drag it up to make the
input taller, drag down to shrink. Emits delta_y on each drag step.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `mousePressEvent` | `(self, event)` |  |
| `mouseMoveEvent` | `(self, event)` |  |
| `mouseReleaseEvent` | `(self, event)` |  |
| `mouseDoubleClickEvent` | `(self, event)` |  |
| `apply_theme` | `(self)` |  |
| `paintEvent` | `(self, event)` |  |

### `CustomizeDialog` *(extends `QDialog`)*

Font size, chart quality, and display options.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` |  |
| `_dpi_value` | `(self)` |  |
| `_reset` | `(self)` |  |
| `_apply` | `(self)` |  |

### `Conversation`

One chat session: its history, widgets, and dedicated chat scroll area.
Each Conversation owns a QScrollArea + content widget so we can keep all
bubbles alive when switching tabs (no rebuild needed).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, title='New chat')` |  |

### `ConversationListItem` *(extends `QFrame`)*

Sidebar entry: clickable title row with a hover-revealed delete button.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, conv_id, title, is_current=False)` |  |
| `set_title` | `(self, t)` |  |
| `set_current` | `(self, is_current)` |  |
| `enterEvent` | `(self, event)` |  |
| `leaveEvent` | `(self, event)` |  |
| `mousePressEvent` | `(self, event)` |  |
| `_on_delete` | `(self)` |  |
| `apply_theme` | `(self)` |  |

### `AIChatDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, ai_node, pw=None)` |  |
| `_cur` | `(self)` |  |
| `_history` | `(self)` |  |
| `_widgets` | `(self)` |  |
| `_cl` | `(self)` |  |
| `_cw` | `(self)` |  |
| `_scroll` | `(self)` |  |
| `_build_ui` | `(self)` |  |
| `_open_settings` | `(self)` |  |
| `_open_customize` | `(self)` |  |
| `_update_counter` | `(self, n_chars)` |  |
| `_clear_chat` | `(self)` |  |
| `_add_conv_list_item` | `(self, conv, is_current=False)` | Create the sidebar entry for an existing Conversation. |
| `_new_conversation` | `(self, switch_to=True)` | Create a new conversation, add it to the stack and sidebar. |
| `_switch_conversation` | `(self, conv_id)` | Switch to the conversation with the given id. Saves the current draft |
| `_delete_conversation` | `(self, conv_id)` | Delete a conversation. If it's the current one, switch to a neighbour. |
| `_maybe_set_conv_title` | `(self, text)` | If the current conversation still has its auto-generated title and |
| `_set_sidebar_enabled` | `(self, enabled)` | Enable/disable conversation switching (used during streaming). |
| `_attach_file` | `(self)` |  |
| `_add_preview` | `(self, name, kind, entry, image_b64=None)` | Show an inline preview chip inside the composer |
| `_remove_preview` | `(self, prev)` | Remove one preview chip and its pending file. |
| `_clear_attachments` | `(self)` |  |
| `_on_composer_resize` | `(self, dy)` | User dragged the resize handle. dy > 0 = drag down (shrink), |
| `_reset_composer_height` | `(self)` | Double-click on the handle → back to auto-grow. |
| `_send` | `(self)` |  |
| `_on_tok` | `(self, t)` |  |
| `_on_stats` | `(self, n, el)` |  |
| `_run_cached` | `(self, code, particles)` | Execute sandbox code, memoising error-free results within the current |
| `_on_done` | `(self, full)` |  |
| `_start_interpretation` | `(self, payload, allowed)` | Second pass: hand the computed results back to the model for a short, |
| `_on_interpret_done` | `(self, full)` |  |
| `_retry_send` | `(self)` | Re-trigger the LLM after injecting a sandbox correction hint. |
| `_on_err` | `(self, err)` |  |
| `_enable` | `(self)` |  |
| `_do_stop` | `(self)` |  |
| `_explore` | `(self)` | Start an agentic exploration session: model writes one query per |
| `_run_exploration_turn` | `(self)` | Spawn a streaming worker for one exploration turn. |
| `_on_exp_tok` | `(self, t)` |  |
| `_on_exp_turn_done` | `(self, full)` | One exploration turn's response is complete. Extract the code, |
| `_on_exp_err` | `(self, err)` | Stream error during exploration — log it and either retry or stop. |
| `_finalize_exploration` | `(self, reason='')` | Ask the model for a final summary of findings, then display it. |
| `_on_exp_summary_done` | `(self, full)` | Display the final summary in the ExplorationBubble. |
| `_on_exp_summary_err` | `(self, err)` |  |
| `_teardown_exploration` | `(self)` | Reset exploration state and re-enable the UI. |
| `update_data_context` | `(self, data)` |  |
| `_update_sug` | `(self, data)` |  |
| `_style_explore_btn` | `(self, btn)` | Distinctive accent styling for the Explore button. |
| `_style_sug_btn` | `(self, btn)` |  |
| `_update_sug_style` | `(self)` |  |
| `_on_global_theme_change` | `(self, name)` |  |
| `_apply_theme` | `(self)` |  |
| `_add_user` | `(self, t)` |  |
| `_add_ai` | `(self, t)` |  |
| `_scrollb` | `(self)` |  |
| `_start_autodetect` | `(self)` | Probe localhost for a running model server and self-configure, so the |
| `_on_autodetect` | `(self, backend, model, label)` |  |
| `_on_autodetect_info` | `(self, msg)` |  |

### `AIAssistantNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, pw=None)` |  |
| `set_position` | `(self, p)` |  |
| `process_data` | `(self, d)` |  |
| `get_data_summary` | `(self)` |  |
| `configure` | `(self, pw)` |  |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_fs` | `(delta=0)` | Return current font size + delta, as int. |
| `_safe_positive` | `(v)` |  |
| `_extract_element_values` | `(particles, field='elements')` |  |
| `_extract_element_counts` | `(particles)` |  |
| `_extract_element_per_ml` | `(particles, dc)` | Compute per-element particle concentration in particles per mL. |
| `_extract_total_values` | `(particles, total_key='total_element_mass_fg')` |  |
| `_extract_combinations` | `(particles)` |  |
| `_extract_by_sample` | `(particles, dc)` |  |
| `_get_all_elements` | `(particles)` |  |
| `_build_system_prompt` | `(dc, backend='ollama')` |  |
| `_build_exploration_prompt` | `(dc, max_turns=10)` | System prompt for the agentic exploration mode. The model writes one |
| `_format_exploration_feedback` | `(text_out, tables, charts, err, turn, max_turns)` | Format the result of executing an exploration turn's code as a user |
| `_md_to_html` | `(text)` |  |
| `_ifmt` | `(t, ibg='#F3F4F6')` |  |
| `_trim_history` | `(h, max_t)` |  |
| `_sanitize_code` | `(code)` |  |
| `_screen_code` | `(code)` | Static-analyse generated code. Returns an error string if it contains a |
| `_to_float` | `(tok)` |  |
| `_floats_in_text` | `(s)` | All numeric values (int or float) appearing in a string. |
| `_numbers_in_rows` | `(rows, cap=8000)` |  |
| `_close` | `(a, b, rel=0.005)` |  |
| `_unverified_numbers` | `(prose, allowed)` | Decimal figures in prose with no match (within tolerance) in the set of |
| `_compact_table` | `(tbl, max_rows=15)` | Short plain-text rendering of a result table for the interpretation pass. |
| `_correction_hint` | `(err, import_error=False)` | Build the self-correction message fed back to the model after a sandbox |
| `_format_exec_error` | `(exc, code)` | Error string with the offending line from the generated code, so both the |
| `_execute_query_code` | `(code, particles, dc)` | Run code in sandbox. Returns (text_output, table_list, chart_list, error). |
| `_read_image_b64` | `(path)` |  |
| `_extract_pdf_text` | `(path)` |  |
| `_read_text_file` | `(path)` |  |
| `_try_parse_table` | `(text)` | Try to parse printed text as a table. Returns (headers, rows) or None. |
| `create_ai_assistant_node` | `(pw)` |  |
| `show_ai_assistant_dialog` | `(pw, data=None)` |  |
