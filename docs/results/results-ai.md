# `results_AI.py`

---

## Constants

| Name | Value |
|------|-------|
| `OLLAMA_BASE` | `'http://localhost:11434'` |
| `OLLAMA_CHAT` | `f'{OLLAMA_BASE}/api/chat'` |
| `OLLAMA_TAGS` | `f'{OLLAMA_BASE}/api/tags'` |
| `ANTHROPIC_API_URL` | `'https://api.anthropic.com/v1/messages'` |
| `ANTHROPIC_MODEL` | `'claude-sonnet-4-20250514'` |
| `PLOT_COLORS` | `['#663399', '#2E86AB', '#A23B72', '#F18F01', '#...` |
| `CODE_EXEC_TIMEOUT` | `30` |
| `MAX_CODE_RETRIES` | `2` |
| `CHARS_PER_TOKEN` | `3.5` |
| `STREAM_RENDER_INTERVAL_MS` | `80` |
| `SAMPLE_PARTICLES_COUNT` | `15` |
| `WIDGET_MAP` | `{'histogram': HistogramWidget, 'scatter': Scatt...` |
| `_SAFE_BUILTINS` | `{'abs': abs, 'all': all, 'any': any, 'bool': bo...` |
| `_CODE_RE` | `re.compile('```python\\s*\\n(.*?)```', re.DOTALL)` |
| `_THINK_RE` | `re.compile('<think>.*?</think>', re.DOTALL)` |
| `_JSON_VIZ_RE` | `re.compile('```json-viz\\s*\\n(.*?)```', re.DOT...` |
| `_JSON_RE` | `re.compile('```json\\s*\\n(.*?)```', re.DOTALL)` |
| `_IMPORT_RE` | `re.compile('^\\s*(?:import\\s+\\w+|from\\s+\\w+...` |

## Classes

### `Theme`

### `InteractiveFigureWidget` *(extends `QFrame`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, spec, particles, dc)` | Args: |
| `_save` | `(self, fmt = 'png')` | Args: |
| `_add_combo` | `(self, label, items, default = None, cb = None)` | Args: |
| `_add_slider` | `(self, label, mn, mx, val, cb = None)` | Args: |
| `_add_toggle` | `(self, label, default = False, cb = None)` | Args: |
| `apply_theme` | `(self)` |  |

### `HistogramWidget` *(extends `InteractiveFigureWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `_build_controls` | `(self)` |  |
| `_render` | `(self)` |  |

### `ScatterWidget` *(extends `InteractiveFigureWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `_build_controls` | `(self)` |  |
| `_render` | `(self)` |  |

### `BarChartWidget` *(extends `InteractiveFigureWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `_build_controls` | `(self)` |  |
| `_render` | `(self)` |  |

### `BoxPlotWidget` *(extends `InteractiveFigureWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `_build_controls` | `(self)` |  |
| `_render` | `(self)` |  |

### `HeatmapWidget` *(extends `InteractiveFigureWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `_build_controls` | `(self)` |  |
| `_render` | `(self)` |  |

### `PieChartWidget` *(extends `InteractiveFigureWidget`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `_build_controls` | `(self)` |  |
| `_render` | `(self)` |  |

### `FigureCarousel` *(extends `QFrame`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` |  |
| `add_figure` | `(self, w)` | Args: |
| `_go_prev` | `(self)` |  |
| `_go_next` | `(self)` |  |
| `_upd_nav` | `(self)` |  |
| `clear` | `(self)` |  |
| `apply_theme` | `(self)` |  |

### `StreamWorker` *(extends `QThread`)*

Unified streaming worker for both Ollama and Claude API.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, backend, msgs, sys_prompt, config)` | Args: |
| `stop` | `(self)` |  |
| `run` | `(self)` |  |
| `_run_claude` | `(self)` |  |
| `_run_ollama` | `(self)` |  |

### `BackendDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, current_cfg, parent = None)` | Args: |
| `_on_backend` | `(self, idx)` | Args: |
| `_test_claude` | `(self)` |  |
| `_test_ollama` | `(self)` |  |
| `get_config` | `(self)` | Returns: |

### `TextBubble` *(extends `QFrame`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, text, is_user = False)` | Args: |
| `apply_theme` | `(self)` |  |

### `StreamBubble` *(extends `QFrame`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` |  |
| `append` | `(self, tok)` | Args: |
| `_flush` | `(self)` |  |
| `finalise` | `(self)` |  |
| `get_text` | `(self)` | Returns: |
| `apply_theme` | `(self)` |  |

### `FigureBubble` *(extends `QFrame`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, pix)` | Args: |

### `ErrorBubble` *(extends `QFrame`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, err)` | Args: |

### `AIChatDialog` *(extends `QDialog`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, ai_node, pw = None)` | Args: |
| `_build_ui` | `(self)` |  |
| `_open_settings` | `(self)` |  |
| `_on_global_theme_change` | `(self, name)` | Sync with the main window's theme and re-apply. |
| `_apply_theme` | `(self)` |  |
| `_update_sug` | `(self, data)` | Args: |
| `update_data_context` | `(self, data)` | Args: |
| `_do_stop` | `(self)` |  |
| `_send` | `(self)` |  |
| `_on_tok` | `(self, t)` | Args: |
| `_on_stats` | `(self, n, el)` | Args: |
| `_on_usage` | `(self, i, o)` | Args: |
| `_on_done` | `(self, full)` | Args: |
| `_on_err` | `(self, err)` | Args: |
| `_enable` | `(self)` |  |
| `_add_user` | `(self, t)` | Args: |
| `_add_ai` | `(self, t)` | Args: |
| `_scrollb` | `(self)` |  |

### `AIAssistantNode` *(extends `QObject`)*

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, pw = None)` | Args: |
| `set_position` | `(self, p)` | Args: |
| `process_data` | `(self, d)` | Args: |
| `get_data_summary` | `(self)` | Returns: |
| `configure` | `(self, pw)` | Args: |

## Functions

### `_safe_positive`

```python
def _safe_positive(v)
```


**Args:**

- `v (Any): The v.`

**Returns:**

- `object: Result of the operation.`

### `_extract_element_values`

```python
def _extract_element_values(particles, field = 'elements')
```

Extract per-element values from a dict field. Returns {label: [values]}.

**Args:**

- `particles (Any): The particles.`
- `field (Any): The field.`

### `_extract_element_counts`

```python
def _extract_element_counts(particles)
```

Count how many particles contain each element (by counts > 0).

**Args:**

- `particles (Any): The particles.`

**Returns:**

- `object: Result of the operation.`

### `_extract_total_values`

```python
def _extract_total_values(particles, total_key = 'total_element_mass_fg')
```

Extract a scalar from the 'totals' dict for each particle.

**Args:**

- `particles (Any): The particles.`
- `total_key (Any): The total key.`

**Returns:**

- `object: Result of the operation.`

### `_extract_combinations`

```python
def _extract_combinations(particles)
```


**Args:**

- `particles (Any): The particles.`

**Returns:**

- `object: Result of the operation.`

### `_extract_by_sample`

```python
def _extract_by_sample(particles, dc)
```


**Args:**

- `particles (Any): The particles.`
- `dc (Any): The dc.`

**Returns:**

- `object: Result of the operation.`

### `_get_all_elements`

```python
def _get_all_elements(particles)
```


**Args:**

- `particles (Any): The particles.`

**Returns:**

- `list: Result of the operation.`

### `_get_element_data`

```python
def _get_element_data(particles, var, element)
```

Get data for a specific variable and element (or ALL).

**Args:**

- `particles (Any): The particles.`
- `var (Any): The var.`
- `element (Any): The element.`

**Returns:**

- `tuple: Result of the operation.`

### `_get_total_data`

```python
def _get_total_data(particles, var)
```

Get per-particle total values.

**Args:**

- `particles (Any): The particles.`
- `var (Any): The var.`

**Returns:**

- `object: Result of the operation.`

### `build_figure_widget`

```python
def build_figure_widget(spec, particles, dc)
```


**Args:**

- `spec (Any): The spec.`
- `particles (Any): The particles.`
- `dc (Any): The dc.`

**Returns:**

- `object: Result of the operation.`

### `_sanitize_code`

```python
def _sanitize_code(code)
```


**Args:**

- `code (Any): The code.`

**Returns:**

- `object: Result of the operation.`

### `_execute_raw_code`

```python
def _execute_raw_code(code, particles, dc, return_fig = False)
```


**Args:**

- `code (Any): The code.`
- `particles (Any): The particles.`
- `dc (Any): The dc.`
- `return_fig (Any): The return fig.`

**Returns:**

- `tuple: Result of the operation.`

### `_md_to_html`

```python
def _md_to_html(text)
```


**Args:**

- `text (Any): Text string.`

**Returns:**

- `object: Result of the operation.`

### `_ifmt`

```python
def _ifmt(t, ibg = '#F3F4F6')
```


**Args:**

- `t (Any): The t.`
- `ibg (Any): The ibg.`

**Returns:**

- `object: Result of the operation.`

### `_trim_history`

```python
def _trim_history(h, max_t)
```


**Args:**

- `h (Any): The h.`
- `max_t (Any): The max t.`

**Returns:**

- `object: Result of the operation.`

### `_build_system_prompt`

```python
def _build_system_prompt(dc, backend = 'claude')
```


**Args:**

- `dc (Any): The dc.`
- `backend (Any): The backend.`

**Returns:**

- `object: Result of the operation.`

### `show_ai_assistant_dialog`

```python
def show_ai_assistant_dialog(pw, data = None)
```


**Args:**

- `pw (Any): The pw.`
- `data (Any): Input data.`
