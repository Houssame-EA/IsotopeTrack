"""Background threads that talk to the model servers.

:class:`StreamWorker` streams one chat completion from Ollama, an MLX server
or any OpenAI-compatible API. :class:`ProbeWorker` looks for a running local
server so the assistant can connect without a trip to the settings.
"""
import json
import logging
import threading
import time

import requests
from PySide6.QtCore import QThread, Signal

from results.ai.servers import (
    MLX_BASE, OLLAMA_CHAT, PROBE_ATTEMPTS, PROBE_RETRY_GAP,
    fetch_ollama_models, fetch_openai_models, local_session,
)

_itk_log = logging.getLogger("IsotopeTrack.results.ai.streaming")


class StreamWorker(QThread):
    """Stream one chat completion from Ollama, MLX or an OpenAI-compatible API."""
    token_received  = Signal(str)
    stream_done     = Signal(str)
    error_occurred  = Signal(str)
    stats_update    = Signal(int, float)
    usage_update    = Signal(int, int)

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
        self.backend     = backend
        self.msgs        = msgs
        self.sys         = sys_prompt
        self.cfg         = config
        self.attachments = attachments or []
        self._cancelled  = threading.Event()
        self._resp       = None

    def stop(self):
        """Cancel the request and close the stream."""
        self._cancelled.set()
        if self._resp:
            try: self._resp.close()
            except Exception:
                _itk_log.exception("Handled exception in stop")

    def run(self):
        """Send the request to the configured backend."""
        if   self.backend == 'mlx':    self._run_mlx()
        elif self.backend == 'custom': self._run_custom_api()
        else:                          self._run_ollama()


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


    def _run_ollama(self):
        """Stream from Ollama's chat endpoint."""
        try:
            base_msgs = [{"role": "system", "content": self.sys}] + self.msgs
            messages  = self._inject_attachments(base_msgs)
            self._resp = local_session().post(OLLAMA_CHAT, json={
                "model":   self.cfg.get('model', ''),
                "messages": messages,
                "stream":  True,
                "options": {
                    "temperature": self.cfg.get('temperature', 0.2),
                    "num_ctx":     self.cfg.get('num_ctx', 8192),
                    "num_predict": int(self.cfg.get('max_reply_tokens', 4096)),
                },
            }, timeout=300, stream=True)
            if self._resp.status_code != 200:
                self.error_occurred.emit(f"Ollama HTTP {self._resp.status_code}"); return
            self._stream_ndjson()
        except requests.exceptions.ConnectionError:
            _itk_log.exception("Handled exception in _run_ollama")
            if not self._cancelled.is_set():
                self.error_occurred.emit("Cannot connect to Ollama. Run: ollama serve")
        except Exception as e:
            _itk_log.exception("Handled exception in _run_ollama")
            if not self._cancelled.is_set(): self.error_occurred.emit(str(e))

    def _iter_stream_lines(self):
        """Yield response lines, absorbing the teardown that Stop causes.

        Stop closes the streaming response from the GUI thread while this
        thread is mid-read, which surfaces from urllib3 as an assortment of
        errors on a socket that no longer exists. Those are expected once
        cancellation is set and must not reach the user as a failure.
        """
        try:
            for line in self._resp.iter_lines(decode_unicode=True):
                yield line
        except Exception:
            if not self._cancelled.is_set():
                raise
            _itk_log.info("Stream closed while stopping — ignoring teardown error")

    def _stream_ndjson(self):
        """Read Ollama's newline-delimited JSON stream."""
        full = []; tc = 0; t0 = time.monotonic()
        for line in self._iter_stream_lines():
            if self._cancelled.is_set(): break
            if not line: continue
            try: chunk = json.loads(line)
            except Exception:
                _itk_log.exception("Handled exception in _stream_ndjson")
                continue
            content = chunk.get('message', {}).get('content', '')
            if content: full.append(content); tc += 1; self.token_received.emit(content)
            if tc % 10 == 0: self.stats_update.emit(tc, time.monotonic()-t0)
            if chunk.get('done', False):
                self.usage_update.emit(int(chunk.get('prompt_eval_count', 0) or 0),
                                       int(chunk.get('eval_count', 0) or 0))
                break
        self._finish(full, tc, t0)


    def _run_mlx(self):
        """Stream from an MLX server's OpenAI-compatible endpoint."""
        try:
            host = self.cfg.get('mlx_host', MLX_BASE).rstrip('/')
            base_msgs = [{"role": "system", "content": self.sys}] + self.msgs
            messages  = self._inject_attachments_openai(base_msgs)
            model = self.cfg.get('model', '')
            ids, reachable, _ = fetch_openai_models(host, timeout=4)
            if reachable and ids and model not in ids:
                _itk_log.info("MLX model %r not served; using %r instead", model, ids[0])
                model = ids[0]
            elif not model and ids:
                model = ids[0]
            payload = {
                "messages":    messages,
                "stream":      True,
                "stream_options": {"include_usage": True},
                "temperature": self.cfg.get('temperature', 0.2),
                "max_tokens":  int(self.cfg.get('max_reply_tokens', 4096)),
            }
            if model:
                payload['model'] = model
            self._resp = local_session().post(
                f"{host}/v1/chat/completions", json=payload, timeout=300, stream=True)
            if self._resp.status_code == 404:
                self.error_occurred.emit(
                    "MLX HTTP 404 — the server did not recognise the model id "
                    f"'{model or 'none sent'}'. Check the id listed by "
                    f"{host}/v1/models and restart mlx_lm.server with that model.")
                return
            if self._resp.status_code != 200:
                self.error_occurred.emit(f"MLX HTTP {self._resp.status_code}"); return
            self._stream_sse()
        except requests.exceptions.ConnectionError:
            _itk_log.exception("Handled exception in _run_mlx")
            if not self._cancelled.is_set():
                self.error_occurred.emit(
                    "Cannot connect to MLX server.\n"
                    "Start it with:  mlx_lm.server --model <model-path> --port 8080")
        except Exception as e:
            _itk_log.exception("Handled exception in _run_mlx")
            if not self._cancelled.is_set(): self.error_occurred.emit(str(e))

    def _stream_sse(self):
        """Read an OpenAI-style server-sent event stream."""
        full = []; tc = 0; t0 = time.monotonic()
        for line in self._iter_stream_lines():
            if self._cancelled.is_set(): break
            if not line or not line.startswith('data: '): continue
            ds = line[6:]
            if ds.strip() == '[DONE]': break
            try: ev = json.loads(ds)
            except Exception:
                _itk_log.exception("Handled exception in _stream_sse")
                continue
            usage = ev.get('usage') or {}
            if usage:
                self.usage_update.emit(int(usage.get('prompt_tokens', 0) or 0),
                                       int(usage.get('completion_tokens', 0) or 0))
            choices = ev.get('choices') or [{}]
            content = choices[0].get('delta', {}).get('content', '') if choices else ''
            if content: full.append(content); tc += 1; self.token_received.emit(content)
            if tc % 10 == 0: self.stats_update.emit(tc, time.monotonic()-t0)
        self._finish(full, tc, t0)


    def _run_custom_api(self):
        """Stream from a user-configured OpenAI-compatible API."""
        try:
            base = self.cfg.get('custom_base_url', '').rstrip('/')
            key  = self.cfg.get('custom_api_key', '')
            model= self.cfg.get('custom_model', '')
            if not base:
                self.error_occurred.emit("No base URL configured for Custom API."); return
            hdrs = {'Content-Type': 'application/json'}
            if key: hdrs['Authorization'] = f'Bearer {key}'
            base_msgs = [{"role":"system","content":self.sys}] + self.msgs
            messages  = self._inject_attachments_openai(base_msgs)
            self._resp = requests.post(
                f"{base}/chat/completions",
                headers=hdrs,
                json={"model":model,"messages":messages,"stream":True,
                      "stream_options":{"include_usage":True},
                      "temperature":self.cfg.get('temperature',0.2),
                      "max_tokens":int(self.cfg.get('max_reply_tokens', 4096))},
                timeout=300, stream=True)
            if self._resp.status_code != 200:
                try: detail = self._resp.json().get('error',{}).get('message','')
                except Exception:
                    _itk_log.exception("Handled exception in _run_custom_api")
                    detail = ''
                self.error_occurred.emit(f"API HTTP {self._resp.status_code}: {detail}"); return
            self._stream_sse()
        except requests.exceptions.ConnectionError:
            _itk_log.exception("Handled exception in _run_custom_api")
            if not self._cancelled.is_set():
                self.error_occurred.emit(f"Cannot connect to {self.cfg.get('custom_base_url','API')}")
        except Exception as e:
            _itk_log.exception("Handled exception in _run_custom_api")
            if not self._cancelled.is_set(): self.error_occurred.emit(str(e))

    def _finish(self, full, tc, t0):
        """Emit the complete reply, or an error when it is empty."""
        complete = ''.join(full).strip()
        if self._cancelled.is_set():
            self.stream_done.emit((complete+"\n\n*[Stopped]*") if complete else "*[Cancelled]*")
        elif complete:
            self.stats_update.emit(tc, time.monotonic()-t0)
            self.stream_done.emit(complete)
        else:
            self.error_occurred.emit("Empty response.")


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
