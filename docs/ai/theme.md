# `theme.py`

Colours, font sizes and markdown rendering shared by the AI chat widgets.

---

## Constants

| Name | Value |
|------|-------|
| `UI_PREFS` | `{'font_size': 14, 'chart_dpi': 100, 'show_timestamps': Fa…` |
| `CODE_RE` | `re.compile('```(?:python\|py)?[ \\t]*\\n(.*?)```', re.DOTALL)` |
| `THINK_RE` | `re.compile('<think>.*?</think>', re.DOTALL)` |
| `OPEN_THINK_RE` | `re.compile('<think>.*\\Z', re.DOTALL)` |

## Classes

### `Theme`

Light and dark palettes for the chat window, following the app theme.

| Method | Signature | Description |
|--------|-----------|-------------|
| `is_dark` | `(cls)` | Return whether the dark palette is active. |
| `toggle` | `(cls)` | Switch between the light and dark palettes. |
| `sync_with_global` | `(cls)` | Follow the application-wide theme. |
| `c` | `(cls, key)` | Return the colour for *key* in the active palette. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `fs` | `(delta=0)` | Return the chat font size plus *delta*, clamped to a readable range. |
| `style_combo_popup` | `(combo)` | Make a combo box drop-down readable inside themed dialogs. |
| `style_model_list` | `(widget)` | Style an always-visible model list so rows stay readable and clickable. |
| `strip_thinking` | `(text)` | Remove reasoning blocks, including one still being streamed. |
| `_escape` | `(text)` | Escape HTML special characters. |
| `inline_markdown` | `(t, ibg='#F3F4F6')` | Render bold, italic and inline code inside one line of markdown. |
| `md_to_html` | `(text)` | Render the subset of markdown the assistant writes into Qt rich text. |
