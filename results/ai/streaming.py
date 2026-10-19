"""Background threads that talk to the model servers.

:class:`StreamWorker` streams one chat completion from Ollama, an MLX server
or any OpenAI-compatible API. :class:`ProbeWorker` looks for a running local
server so the assistant can connect without a trip to the settings.

Requests go through :class:`CancellableStream`, a thin layer over
:mod:`http.client` whose socket can be shut from the GUI thread at any
moment, including while the server is still reading the prompt. Closing the
connection is how Ollama and MLX servers are told to stop generating, so
Stop really stops the model instead of only hiding its output.
"""
import http.client
import json
import logging
import socket
import threading
import time
from urllib.parse import urlsplit

from PySide6.QtCore import QThread, Signal

from results.ai.servers import (
    MLX_BASE, OLLAMA_BASE, PROBE_ATTEMPTS, PROBE_RETRY_GAP, fetch_ollama_models,
    fetch_openai_models,
)

_itk_log = logging.getLogger("IsotopeTrack.results.ai.streaming")

READ_TIMEOUT = 600


class StreamCancelled(Exception):
    """Raised inside the worker when the user stopped the request."""


class CancellableStream:
    """One streaming POST request that another thread can abort at once.

    Attributes:
        url (str): Endpoint.
        status (int): HTTP status once the response arrived.
    """

    def __init__(self, url, payload, headers=None, timeout=READ_TIMEOUT):
        """Prepare the request.

        Args:
            url (str): Full endpoint URL.
            payload (dict): JSON body.
            headers (dict): Extra headers.
            timeout (float): Socket timeout in seconds.
        """
        self.url = url
        self._payload = payload
        self._headers = dict(headers or {})
        self._timeout = timeout
        self._conn = None
        self._sock = None
        self._resp = None
        self._aborted = threading.Event()
        self.status = 0

    def open(self):
        """Send the request and wait for the response headers.

        Returns:
            http.client.HTTPResponse: The response.

        Raises:
            StreamCancelled: When :meth:`abort` was called meanwhile.
        """
        parts = urlsplit(self.url)
        cls = http.client.HTTPSConnection if parts.scheme == 'https' else http.client.HTTPConnection
        self._conn = cls(parts.hostname, parts.port, timeout=self._timeout)
        if self._aborted.is_set():
            raise StreamCancelled()
        path = parts.path or '/'
        if parts.query:
            path += '?' + parts.query
        body = json.dumps(self._payload).encode('utf-8')
        headers = {'Content-Type': 'application/json', 'Accept': 'text/event-stream, application/x-ndjson',
                   **self._headers}
        try:
            self._conn.connect()
            self._sock = self._conn.sock
            if self._aborted.is_set():
                raise StreamCancelled()
            self._conn.request('POST', path, body=body, headers=headers)
            self._resp = self._conn.getresponse()
        except (OSError, http.client.HTTPException):
            if self._aborted.is_set():
                raise StreamCancelled() from None
            raise
        self.status = self._resp.status
        return self._resp

    def lines(self):
        """Yield the response body line by line, decoded.

        Raises:
            StreamCancelled: When :meth:`abort` cut the stream.
        """
        try:
            while True:
                if self._aborted.is_set():
                    raise StreamCancelled()
                raw = self._resp.readline()
                if not raw:
                    break
                yield raw.decode('utf-8', 'replace').rstrip('\r\n')
        except (OSError, http.client.HTTPException, ValueError, AttributeError):
            if self._aborted.is_set():
                raise StreamCancelled() from None
            raise

    def read_error(self, limit=2000):
        """Read a short error body.

        Returns:
            str: The server's error message, or an empty string.
        """
        try:
            text = self._resp.read(limit).decode('utf-8', 'replace')
        except Exception:
            return ''
        try:
            data = json.loads(text)
            err = data.get('error')
            if isinstance(err, dict):
                return str(err.get('message', ''))
            return str(err or text)
        except Exception:
            return text.strip()[:300]

    def abort(self):
        """Cut the connection now; the server sees the client go and stops generating."""
        self._aborted.set()
        sock = self._sock or getattr(self._conn, 'sock', None)
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        for closable in (self._resp, self._conn):
            try:
                if closable is not None:
                    closable.close()
            except Exception:
                pass

    def close(self):
        """Release the connection after a normal finish."""
        try:
            if self._conn is not None:
                self._conn.close()
        except Exception:
            pass


class StreamWorker(QThread):
    """Stream one chat completion from Ollama, MLX or an OpenAI-compatible API."""

    token_received = Signal(str)
    stream_done = Signal(str)
    error_occurred = Signal(str)
    stats_update = Signal(int, float)
    usage_update = Signal(int, int)

    def __init__(self, backend, msgs, sys_prompt, config, attachments=None):
        """Prepare the request.

        Args:
            backend (str): ``ollama``, ``mlx`` or ``custom``.
            msgs (list): Chat messages.
            sys_prompt (str): System prompt.
            config (dict): Backend settings.
            attachments (list): Files attached to the last user message.
        """
        super().__init__()
        self.backend = backend
        self.msgs = msgs
        self.sys = sys_prompt
        self.cfg = config
        self.attachments = attachments or []
        self._cancelled = threading.Event()
        self._stream = None

    def stop(self):
        """Stop the request immediately, wherever it is."""
        self._cancelled.set()
        stream = self._stream
        if stream is not None:
            stream.abort()

    @property
    def cancelled(self):
        """Whether :meth:`stop` was called."""
        return self._cancelled.is_set()

    def _inject_attachments(self, messages):
        """Inject pending file/image attachments into the last user message."""
        if not self.attachments: return messages
        msgs = list(messages)
        for i in range(len(msgs)-1, -1, -1):
            if msgs[i].get('role') == 'user':
                original = msgs[i].get('content', '')
                images  = [a for a in self.attachments if a['type'] == 'image']
                texts   = [a for a in self.attachments if a['type'] == 'text']
                prefix = ''
                for a in texts:
                    prefix += f"\n[Attached file: {a['name']}]\n{a['content']}\n\n"
                if prefix:
                    msgs[i] = dict(msgs[i]); msgs[i]['content'] = prefix + original

                if images:
                    msgs[i] = dict(msgs[i])
                    msgs[i]['images'] = [a['data'] for a in images]
                break
        return msgs

    def _inject_attachments_openai(self, messages):
        """OpenAI-style multipart content for MLX vision."""
        if not self.attachments: return messages
        msgs = list(messages)
        for i in range(len(msgs)-1, -1, -1):
            if msgs[i].get('role') == 'user':
                images = [a for a in self.attachments if a['type'] == 'image']
                texts  = [a for a in self.attachments if a['type'] == 'text']
                original = msgs[i].get('content', '')
                prefix = ''.join(f"\n[Attached: {a['name']}]\n{a['content']}\n\n" for a in texts)
                content = [{"type": "text", "text": prefix + original}]
                for a in images:
                    content.append({"type": "image_url",
                                    "image_url": {"url": f"data:{a['mime']};base64,{a['data']}"}})
                msgs[i] = dict(msgs[i]); msgs[i]['content'] = content
                break
        return msgs

    def _ollama_request(self):
        """URL, payload and headers for Ollama's chat endpoint."""
        host = (self.cfg.get('ollama_host') or OLLAMA_BASE).rstrip('/')
        messages = self._inject_attachments([{"role": "system", "content": self.sys}] + self.msgs)
        payload = {
            "model": self.cfg.get('model', ''),
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": self.cfg.get('temperature', 0.2),
                "num_ctx": self.cfg.get('num_ctx', 8192),
                "num_predict": int(self.cfg.get('max_reply_tokens', 4096)),
            },
            "think": bool(self.cfg.get('thinking', False)),
        }
        return f"{host}/api/chat", payload, {}

    def _openai_payload(self, model):
        """OpenAI-style payload shared by MLX and custom APIs."""
        messages = self._inject_attachments_openai([{"role": "system", "content": self.sys}] + self.msgs)
        payload = {
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": self.cfg.get('temperature', 0.2),
            "max_tokens": int(self.cfg.get('max_reply_tokens', 4096)),
        }
        if model:
            payload['model'] = model
        return payload

    def _mlx_request(self):
        """URL, payload and headers for an MLX server, resolving the served model id."""
        host = (self.cfg.get('mlx_host') or MLX_BASE).rstrip('/')
        model = self.cfg.get('model', '')
        ids, reachable, _ = fetch_openai_models(host, timeout=4)
        if reachable and ids and model not in ids:
            _itk_log.info("MLX model %r not served; using %r instead", model, ids[0])
            model = ids[0]
        elif not model and ids:
            model = ids[0]
        url = host if host.endswith('/v1') else f"{host}/v1"
        payload = self._openai_payload(model)
        payload['chat_template_kwargs'] = {"enable_thinking": bool(self.cfg.get('thinking', False))}
        return f"{url}/chat/completions", payload, {}

    def _custom_request(self):
        """URL, payload and headers for a user-configured OpenAI-compatible API."""
        base = self.cfg.get('custom_base_url', '').rstrip('/')
        if not base:
            raise ValueError("No base URL configured for the custom API.")
        headers = {}
        key = self.cfg.get('custom_api_key', '')
        if key:
            headers['Authorization'] = f'Bearer {key}'
        model = self.cfg.get('custom_model', '') or self.cfg.get('model', '')
        return f"{base}/chat/completions", self._openai_payload(model), headers

    def _connect_hint(self):
        """What to tell the user when the server cannot be reached."""
        if self.backend == 'mlx':
            return ("Cannot connect to the MLX server.\n"
                    "Start it with:  mlx_lm.server --model <model-path> --port 8080")
        if self.backend == 'custom':
            return f"Cannot connect to {self.cfg.get('custom_base_url', 'the API')}"
        return "Cannot connect to Ollama. Run: ollama serve"

    def run(self):
        """Send the request, stream the reply, and stop as soon as asked."""
        full, tc, t0 = [], 0, time.monotonic()
        try:
            if self.backend == 'mlx':
                url, payload, headers = self._mlx_request()
            elif self.backend == 'custom':
                url, payload, headers = self._custom_request()
            else:
                url, payload, headers = self._ollama_request()
            if self.cancelled:
                raise StreamCancelled()
            self._stream = CancellableStream(url, payload, headers)
            if self.cancelled:
                raise StreamCancelled()
            self._stream.open()
            status = self._stream.status
            if status != 200 and 'think' in payload:
                detail = self._stream.read_error()
                if 'think' in (detail or '').lower():
                    self._stream.close()
                    payload = {k: v for k, v in payload.items() if k != 'think'}
                    self._stream = CancellableStream(url, payload, headers)
                    if self.cancelled:
                        raise StreamCancelled()
                    self._stream.open()
                    status = self._stream.status
                else:
                    self.error_occurred.emit(f"HTTP {status}" + (f": {detail}" if detail else ''))
                    return
            if status != 200:
                detail = self._stream.read_error()
                if self.backend == 'mlx' and status == 404:
                    detail = (f"the server did not recognise the model id '{payload.get('model', 'none sent')}'. "
                              "Restart mlx_lm.server with that model.")
                self.error_occurred.emit(f"HTTP {status}" + (f": {detail}" if detail else ''))
                return
            reader = self._read_ndjson if self.backend == 'ollama' else self._read_sse
            tc = reader(full, t0)
        except StreamCancelled:
            pass
        except (ConnectionRefusedError, socket.gaierror):
            if not self.cancelled:
                self.error_occurred.emit(self._connect_hint())
            return
        except Exception as e:
            if not self.cancelled:
                _itk_log.exception("Model request failed")
                self.error_occurred.emit(str(e) or type(e).__name__)
            return
        finally:
            if self._stream is not None:
                self._stream.close()
        self._finish(full, tc, t0)

    def _read_ndjson(self, full, t0):
        """Read Ollama's newline-delimited JSON stream.

        Returns:
            int: Number of chunks received.
        """
        tc = 0
        for line in self._stream.lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except ValueError:
                continue
            if chunk.get('error'):
                raise RuntimeError(str(chunk['error']))
            content = (chunk.get('message') or {}).get('content', '')
            if content:
                full.append(content)
                tc += 1
                self.token_received.emit(content)
                if tc % 10 == 0:
                    self.stats_update.emit(tc, time.monotonic() - t0)
            if chunk.get('done', False):
                self.usage_update.emit(int(chunk.get('prompt_eval_count', 0) or 0),
                                       int(chunk.get('eval_count', 0) or 0))
                break
        return tc

    def _read_sse(self, full, t0):
        """Read an OpenAI-style server-sent event stream.

        Returns:
            int: Number of chunks received.
        """
        tc = 0
        for line in self._stream.lines():
            if not line.startswith('data:'):
                continue
            data = line[5:].strip()
            if data == '[DONE]':
                break
            try:
                ev = json.loads(data)
            except ValueError:
                continue
            usage = ev.get('usage') or {}
            if usage:
                self.usage_update.emit(int(usage.get('prompt_tokens', 0) or 0),
                                       int(usage.get('completion_tokens', 0) or 0))
            choices = ev.get('choices') or []
            content = ((choices[0].get('delta') or {}).get('content') or '') if choices else ''
            if content:
                full.append(content)
                tc += 1
                self.token_received.emit(content)
                if tc % 10 == 0:
                    self.stats_update.emit(tc, time.monotonic() - t0)
        return tc

    def _finish(self, full, tc, t0):
        """Emit the complete reply, or an error when it is empty."""
        complete = ''.join(full).strip()
        if self.cancelled:
            self.stream_done.emit((complete + "\n\n*[Stopped]*") if complete else "*[Stopped]*")
        elif complete:
            self.stats_update.emit(tc, time.monotonic() - t0)
            self.stream_done.emit(complete)
        else:
            self.error_occurred.emit("Empty response.")


class CodeWorker(QThread):
    """Run generated code off the GUI thread, so the window stays usable and Stop works."""

    result_ready = Signal(str, object)

    def __init__(self, code, dataset, timeout=None):
        """Prepare the run.

        Args:
            code (str): Python written by the model.
            dataset (Dataset): The data it works on.
            timeout (float): Seconds allowed, ``None`` to run until the code
                finishes or Stop is pressed.
        """
        super().__init__()
        self.code = code
        self.dataset = dataset
        self.timeout = timeout
        self._stop = threading.Event()

    def stop(self):
        """Stop the code at its next line."""
        self._stop.set()

    def run(self):
        """Execute the code and hand back the result."""
        from results.ai.sandbox import ExecResult, execute
        try:
            res = execute(self.code, self.dataset, self.timeout, stop_event=self._stop)
        except Exception as e:
            _itk_log.exception("Sandbox run failed")
            res = ExecResult(error=f"{type(e).__name__}: {e}")
        self.result_ready.emit(self.code, res)


class ProbeWorker(QThread):
    """Probe loopback for a running model server so the assistant can
    self-configure on first open — no need to visit settings.

    Ollama is checked first, then MLX, and both are retried a few times because
    a server that is still loading its model list refuses connections for the
    first second or two after launch. Emits at most one ``ready`` signal.
    """
    ready = Signal(str, str, str)
    info  = Signal(str)

    def __init__(self, mlx_host=MLX_BASE, attempts=PROBE_ATTEMPTS):
        """Prepare the probe.

        Args:
            mlx_host (str): MLX server base URL.
            attempts (int): How many times to try.
        """
        super().__init__()
        self._mlx_host = (mlx_host or MLX_BASE).rstrip('/')
        self._attempts = max(1, int(attempts))
        self._stop = threading.Event()

    def stop(self):
        """Ask the probe loop to end before its next retry."""
        self._stop.set()

    def run(self):
        """Look for Ollama, then MLX, retrying while servers start."""
        ollama_up_empty = False
        for attempt in range(self._attempts):
            if self._stop.is_set():
                return
            models, reachable, _ = fetch_ollama_models()
            if models:
                self.ready.emit('ollama', models[0], f"Ollama · {models[0]}")
                return
            ollama_up_empty = ollama_up_empty or reachable

            ids, mlx_reachable, _ = fetch_openai_models(self._mlx_host)
            if mlx_reachable:
                model = ids[0] if ids else ''
                label = (model.split('/')[-1] if model else 'loaded model')
                self.ready.emit('mlx', model, f"MLX · {label}")
                return

            if attempt < self._attempts - 1 and not self._stop.wait(PROBE_RETRY_GAP):
                continue
            break

        if ollama_up_empty:
            self.info.emit("Ollama is running but has no models — run: ollama pull llama3.1")
