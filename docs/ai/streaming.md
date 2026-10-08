# `streaming.py`

Background threads that talk to the model servers.

:class:`StreamWorker` streams one chat completion from Ollama, an MLX server
or any OpenAI-compatible API. :class:`ProbeWorker` looks for a running local
server so the assistant can connect without a trip to the settings.

---

## Classes

### `StreamWorker` *(extends `QThread`)*

Stream one chat completion from Ollama, MLX or an OpenAI-compatible API.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, backend, msgs, sys_prompt, config, attachments=None)` | Prepare the request. |
| `stop` | `(self)` | Cancel the request and close the stream. |
| `run` | `(self)` | Send the request to the configured backend. |
| `_inject_attachments` | `(self, messages)` | Inject pending file/image attachments into the last user message. |
| `_inject_attachments_openai` | `(self, messages)` | OpenAI-style multipart content for MLX vision. |
| `_run_ollama` | `(self)` | Stream from Ollama's chat endpoint. |
| `_iter_stream_lines` | `(self)` | Yield response lines, absorbing the teardown that Stop causes. |
| `_stream_ndjson` | `(self)` | Read Ollama's newline-delimited JSON stream. |
| `_run_mlx` | `(self)` | Stream from an MLX server's OpenAI-compatible endpoint. |
| `_stream_sse` | `(self)` | Read an OpenAI-style server-sent event stream. |
| `_run_custom_api` | `(self)` | Stream from a user-configured OpenAI-compatible API. |
| `_finish` | `(self, full, tc, t0)` | Emit the complete reply, or an error when it is empty. |

### `ProbeWorker` *(extends `QThread`)*

Probe loopback for a running model server so the assistant can
self-configure on first open — no need to visit settings.

Ollama is checked first, then MLX, and both are retried a few times because
a server that is still loading its model list refuses connections for the
first second or two after launch. Emits at most one ``ready`` signal.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, mlx_host=MLX_BASE, attempts=PROBE_ATTEMPTS)` | Prepare the probe. |
| `stop` | `(self)` | Ask the probe loop to end before its next retry. |
| `run` | `(self)` | Look for Ollama, then MLX, retrying while servers start. |
