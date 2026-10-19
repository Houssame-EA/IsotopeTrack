# `streaming.py`

Background threads that talk to the model servers.

:class:`StreamWorker` streams one chat completion from Ollama, an MLX server
or any OpenAI-compatible API. :class:`ProbeWorker` looks for a running local
server so the assistant can connect without a trip to the settings.

Requests go through :class:`CancellableStream`, a thin layer over
:mod:`http.client` whose socket can be shut from the GUI thread at any
moment, including while the server is still reading the prompt. Closing the
connection is how Ollama and MLX servers are told to stop generating, so
Stop really stops the model instead of only hiding its output.

---

## Constants

| Name | Value |
|------|-------|
| `READ_TIMEOUT` | `600` |

## Classes

### `StreamCancelled` *(extends `Exception`)*

Raised inside the worker when the user stopped the request.

### `CancellableStream`

One streaming POST request that another thread can abort at once.

Attributes:
    url (str): Endpoint.
    status (int): HTTP status once the response arrived.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, url, payload, headers=None, timeout=READ_TIMEOUT)` | Prepare the request. |
| `open` | `(self)` | Send the request and wait for the response headers. |
| `lines` | `(self)` | Yield the response body line by line, decoded. |
| `read_error` | `(self, limit=2000)` | Read a short error body. |
| `abort` | `(self)` | Cut the connection now; the server sees the client go and stops generating. |
| `close` | `(self)` | Release the connection after a normal finish. |

### `StreamWorker` *(extends `QThread`)*

Stream one chat completion from Ollama, MLX or an OpenAI-compatible API.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, backend, msgs, sys_prompt, config, attachments=None)` | Prepare the request. |
| `stop` | `(self)` | Stop the request immediately, wherever it is. |
| `cancelled` | `(self)` | Whether :meth:`stop` was called. |
| `_inject_attachments` | `(self, messages)` | Inject pending file/image attachments into the last user message. |
| `_inject_attachments_openai` | `(self, messages)` | OpenAI-style multipart content for MLX vision. |
| `_ollama_request` | `(self)` | URL, payload and headers for Ollama's chat endpoint. |
| `_openai_payload` | `(self, model)` | OpenAI-style payload shared by MLX and custom APIs. |
| `_mlx_request` | `(self)` | URL, payload and headers for an MLX server, resolving the served model id. |
| `_custom_request` | `(self)` | URL, payload and headers for a user-configured OpenAI-compatible API. |
| `_connect_hint` | `(self)` | What to tell the user when the server cannot be reached. |
| `run` | `(self)` | Send the request, stream the reply, and stop as soon as asked. |
| `_read_ndjson` | `(self, full, t0)` | Read Ollama's newline-delimited JSON stream. |
| `_read_sse` | `(self, full, t0)` | Read an OpenAI-style server-sent event stream. |
| `_finish` | `(self, full, tc, t0)` | Emit the complete reply, or an error when it is empty. |

### `CodeWorker` *(extends `QThread`)*

Run generated code off the GUI thread, so the window stays usable and Stop works.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, code, dataset, timeout=None)` | Prepare the run. |
| `stop` | `(self)` | Stop the code at its next line. |
| `run` | `(self)` | Execute the code and hand back the result. |

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
