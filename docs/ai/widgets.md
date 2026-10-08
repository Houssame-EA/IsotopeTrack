# `widgets.py`

Chat window building blocks: message bubbles, tables, figures and inputs.

---

## Constants

| Name | Value |
|------|-------|
| `STREAM_RENDER_INTERVAL` | `80` |

## Classes

### `AttachmentChip` *(extends `QFrame`)*

Visual file-attachment card on the user side. No thumbnail — just icon + name + info.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, name, kind, info='')` | Create the card. |
| `apply_theme` | `(self)` | Restyle for the current theme. |

### `AttachmentPreview` *(extends `QFrame`)*

with an image thumbnail (or file icon), filename, and a remove (×) button
overlaid on the top-right corner.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, name, kind, image_b64=None)` | Create the preview. |
| `resizeEvent` | `(self, event)` | Keep the remove button in the top-right corner. |
| `apply_theme` | `(self)` | Restyle for the current theme. |

### `TextBubble` *(extends `QFrame`)*

A chat message, from the user or the assistant.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, text, is_user=False)` | Create the message. |
| `_copy_text` | `(self)` | Copy the message text to the clipboard. |
| `apply_theme` | `(self)` | Restyle for the current theme. |

### `StreamBubble` *(extends `QFrame`)*

The assistant's reply while it is being written.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` | Create an empty reply that renders at a steady rate. |
| `append` | `(self, tok)` | Queue a streamed token. |
| `_flush` | `(self)` | Render the tokens received so far. |
| `finalise` | `(self, full=None)` | Stop streaming and show the final text without code blocks. |
| `get_text` | `(self)` | Return the raw text received. |
| `apply_theme` | `(self)` | Restyle for the current theme. |

### `ExplorationBubble` *(extends `QFrame`)*

Card that follows an exploration: plan, live findings, steps and summary.

The plan and the findings stay visible while the model works. Each
turn's code, tables and figures sit in a collapsible list of steps, and
the final summary appears at the bottom.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, question)` | Create the card. |
| `set_progress` | `(self, turn, max_turns, text='')` | Show the current turn and what the model is doing. |
| `set_plan` | `(self, items)` | Show the model's hypotheses. |
| `set_findings` | `(self, ledger)` | Show the findings recorded so far. |
| `add_step` | `(self, turn_num, rationale, code, result)` | Add one turn to the list of steps. |
| `set_summary` | `(self, summary_md)` | Show the final summary and stop the progress bar. |
| `mark_cancelled` | `(self, reason='stopped by user')` | Show that the exploration ended early. |
| `_update_toggle` | `(self)` | Refresh the show/hide steps button text. |
| `_toggle_expand` | `(self)` | Show or hide the steps. |
| `_build_step_widget` | `(self, turn_num, rationale, code, result)` | Build the compact view of one turn. |
| `apply_theme` | `(self)` | Restyle for the current theme and font size. |

### `_NumericItem` *(extends `QTableWidgetItem`)*

QTableWidgetItem that sorts numerically when possible.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__lt__` | `(self, other)` | Compare numerically when both cells hold numbers. |

### `InteractiveTableBubble` *(extends `QFrame`)*

Sortable, filterable table with stats panel, chart type selector, and CSV export.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, headers, rows, title='Query result', note='')` | Create the table. |
| `_populate` | `(self, rows)` | Fill the table with rows. |
| `_apply_filter` | `(self, text)` | Show only rows containing the filter text. |
| `_on_col_click` | `(self, col_idx)` | Select the clicked column in the stats combo and show stats. |
| `_toggle_stats` | `(self, checked)` | Show or hide the column statistics. |
| `_refresh_stats` | `(self)` | Compute statistics of the selected numeric column. |
| `_switch` | `(self, idx)` | Show the table (0) or the quick chart (1). |
| `_set_chart_kind` | `(self, kind)` | Change the quick chart type. |
| `_draw_chart` | `(self)` | Draw the selected numeric column as a quick chart of the table. |
| `_save_chart_png` | `(self)` | Save the quick chart as a PNG. |
| `_copy_tsv` | `(self)` | Copy the visible rows as tab-separated text. |
| `_export_csv` | `(self)` | Save the visible rows as a CSV file. |
| `apply_theme` | `(self)` | Restyle for the current theme. |

### `OutputBubble` *(extends `QFrame`)*

Fallback plain-text output for non-tabular results.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, text)` | Create the view. |
| `apply_theme` | `(self)` | Restyle for the current theme. |

### `NoticeBubble` *(extends `QFrame`)*

A short coloured notice: an error, a warning or a note.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, text, kind='warn')` | Create the notice. |
| `apply_theme` | `(self)` | Restyle for the current theme. |

### `CodeBubble` *(extends `QFrame`)*

The code that produced a result, folded away until asked for.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, code, expanded=False)` | Create the view. |
| `_update` | `(self)` | Refresh the fold button. |
| `_flip` | `(self)` | Fold or unfold the code. |
| `_copy_code` | `(self)` | Copy the code to the clipboard. |
| `apply_theme` | `(self)` | Restyle for the current theme. |

### `FigureWindow` *(extends `QWidget`)*

A figure in its own resizable window, with zoom and pan.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, figure, title, parent=None)` | Open the window. |
| `closeEvent` | `(self, event)` | Give the figure back its original size so exports stay as drawn. |

### `FigureBubble` *(extends `QFrame`)*

A figure the model drew, with copy, save and pop-out.

The preview is a crisp image of the figure at the size the model chose,
scaled down only when the window is narrower. Saving always uses the
original size at publication resolution.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, figure, title='', code=None)` | Create the card. |
| `_render` | `(self)` | Draw the preview image. |
| `_fit` | `(self)` | Scale the preview to the available width. |
| `resizeEvent` | `(self, event)` | Keep the preview within the chat width. |
| `_copy_image` | `(self)` | Copy the figure image to the clipboard. |
| `_save` | `(self)` | Save the figure at its original size and publication resolution. |
| `_pop_out` | `(self)` | Open the figure in its own window. |
| `apply_theme` | `(self)` | Restyle for the current theme. |

### `AutoGrowTextEdit` *(extends `QPlainTextEdit`)*

Text input that grows and shrinks with content. Enter sends; Shift+Enter newline.
Can also be manually resized via set_forced_height() — when set, auto-grow is
bypassed and the input stays at the user-chosen height.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Create the input. |
| `set_forced_height` | `(self, h)` | Lock the input to a specific height (in px). Pass None to re-enable |
| `get_forced_height` | `(self)` | Return the height the user dragged to, or ``None``. |
| `_on_changed` | `(self)` | Report the length and resize after an edit. |
| `_adjust` | `(self)` | Fit the height to the text, or keep the forced height. |
| `resizeEvent` | `(self, event)` | Refit the height when the width changes. |
| `keyPressEvent` | `(self, event)` | Send on Enter; Shift+Enter inserts a new line. |
| `text` | `(self)` | Return the text without surrounding whitespace. |
| `setText` | `(self, t)` | Replace the text. |
| `clear` | `(self)` | Remove all text. |

### `ComposerResizeHandle` *(extends `QFrame`)*

Thin horizontal bar at the top of the composer — drag it up to make the
input taller, drag down to shrink. Emits delta_y on each drag step.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, parent=None)` | Create the handle. |
| `mousePressEvent` | `(self, event)` | Start a drag. |
| `mouseMoveEvent` | `(self, event)` | Report how far the drag moved. |
| `mouseReleaseEvent` | `(self, event)` | End the drag. |
| `mouseDoubleClickEvent` | `(self, event)` | Ask for the automatic height back. |
| `apply_theme` | `(self)` | Restyle for the current theme. |
| `paintEvent` | `(self, event)` | Draw the grip bar. |

### `Conversation`

One chat session: its history, widgets, and dedicated chat scroll area.
Each Conversation owns a QScrollArea + content widget so we can keep all
bubbles alive when switching tabs (no rebuild needed).

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, title='New chat')` | Start an empty conversation. |

### `ConversationListItem` *(extends `QFrame`)*

Sidebar entry: clickable title row with a hover-revealed delete button.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, conv_id, title, is_current=False)` | Create the entry. |
| `set_title` | `(self, t)` | Change the title shown. |
| `set_current` | `(self, is_current)` | Mark the entry as the conversation on screen, or not. |
| `enterEvent` | `(self, event)` | Reveal the delete button on hover. |
| `leaveEvent` | `(self, event)` | Hide the delete button. |
| `mousePressEvent` | `(self, event)` | Select the conversation unless the delete button was hit. |
| `_on_delete` | `(self)` | Ask for the conversation to be deleted. |
| `apply_theme` | `(self)` | Restyle for the current theme. |
