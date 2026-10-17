# -*- coding: utf-8 -*-
"""Tests for the thinking-mode option of the AI assistant.

Thinking is off unless the user ticks it in the settings. A small fake
Ollama records each request body, and can refuse ``think`` the way Ollama
does for models that cannot reason, so the retry without it is checked too.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PySide6.QtWidgets import QApplication

from results.ai import streaming
from results.ai.streaming import StreamWorker


class RecordingOllama(BaseHTTPRequestHandler):
    """Records request bodies; can refuse requests that ask for thinking."""

    bodies = []
    refuse_think = False

    def log_message(self, *args):
        """Keep test output quiet."""

    def do_POST(self):
        """Answer with two tokens, or a 400 when thinking is refused."""
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        RecordingOllama.bodies.append(body)
        if RecordingOllama.refuse_think and 'think' in body:
            msg = json.dumps({'error': '"fake" does not support thinking'}).encode()
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson')
        self.end_headers()
        for chunk in ({'message': {'thinking': 'hmm', 'content': ''}, 'done': False},
                      {'message': {'content': 'Hello '}, 'done': False},
                      {'message': {'content': 'there'}, 'done': True}):
            self.wfile.write((json.dumps(chunk) + '\n').encode())
        self.wfile.flush()


@pytest.fixture
def server():
    """Run the recording server on a free port."""
    RecordingOllama.bodies = []
    RecordingOllama.refuse_think = False
    srv = ThreadingHTTPServer(('127.0.0.1', 0), RecordingOllama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _run(host, **cfg):
    """Run one request on this thread and return ``(reply, errors)``."""
    QApplication.instance() or QApplication([])
    w = StreamWorker('ollama', [{'role': 'user', 'content': 'hi'}], 'sys',
                     {'model': 'fake', 'ollama_host': host, 'num_ctx': 2048, **cfg})
    done, errors = [], []
    w.stream_done.connect(done.append)
    w.error_occurred.connect(errors.append)
    w.run()
    return (done[0] if done else ''), errors


def test_thinking_is_off_by_default(server):
    """Without the option, Ollama is asked not to think and only the answer is kept."""
    reply, errors = _run(server)
    assert errors == [] and reply == 'Hello there'
    assert RecordingOllama.bodies[0]['think'] is False


def test_thinking_on_when_ticked(server):
    """Ticking the option asks Ollama to think."""
    _run(server, thinking=True)
    assert RecordingOllama.bodies[0]['think'] is True


def test_model_without_thinking_is_retried(server):
    """A model that refuses thinking still answers, through one retry without it."""
    RecordingOllama.refuse_think = True
    reply, errors = _run(server, thinking=True)
    assert errors == [] and reply == 'Hello there'
    assert len(RecordingOllama.bodies) == 2 and 'think' not in RecordingOllama.bodies[1]


def test_mlx_payload(monkeypatch):
    """MLX gets the chat-template switch, off by default and on when ticked."""
    monkeypatch.setattr(streaming, 'fetch_openai_models', lambda host, timeout=4: (['m'], True, None))
    QApplication.instance() or QApplication([])
    off = StreamWorker('mlx', [], 'sys', {'model': 'm'})._mlx_request()[1]
    on = StreamWorker('mlx', [], 'sys', {'model': 'm', 'thinking': True})._mlx_request()[1]
    assert off['chat_template_kwargs'] == {'enable_thinking': False}
    assert on['chat_template_kwargs'] == {'enable_thinking': True}


def test_custom_api_gets_no_thinking_fields():
    """An OpenAI-compatible API is never sent fields it may reject."""
    QApplication.instance() or QApplication([])
    w = StreamWorker('custom', [], 'sys', {'custom_base_url': 'http://x/v1', 'model': 'm', 'thinking': True})
    payload = w._custom_request()[1]
    assert 'think' not in payload and 'chat_template_kwargs' not in payload


def test_settings_checkbox_default_and_tooltip():
    """The settings show the option unticked, with a note that it is slower."""
    QApplication.instance() or QApplication([])
    from results.ai.settings import BackendDialog
    d = BackendDialog({'backend': 'ollama', 'model': ''})
    assert not d._think_chk.isChecked()
    assert 'longer' in d._think_chk.toolTip()
    assert d.get_config()['thinking'] is False
    d._think_chk.setChecked(True)
    assert d.get_config()['thinking'] is True
    d.deleteLater()
