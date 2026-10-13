# -*- coding: utf-8 -*-
"""Tests that Stop really stops the model and that quitting frees it.

A small fake model server stands in for Ollama. It can hold the response
back, as a model does while it reads a long prompt, or stream tokens slowly,
and it records when the client goes away, which is how Ollama and MLX know
to stop generating.
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PySide6.QtWidgets import QApplication

from results.ai import servers
from results.ai.data import Dataset
from results.ai.sandbox import execute
from results.ai.streaming import StreamWorker


class FakeOllama(BaseHTTPRequestHandler):
    """Answers /api/chat slowly and notes when the client disconnects."""

    mode = 'stream'
    disconnected = threading.Event()
    received = threading.Event()

    def log_message(self, *args):
        """Keep test output quiet."""

    def do_POST(self):
        """Hold the headers back, or stream tokens until the client leaves."""
        length = int(self.headers.get('Content-Length', 0))
        self.rfile.read(length)
        FakeOllama.received.set()
        try:
            if FakeOllama.mode == 'slow_prompt':
                for _ in range(300):
                    time.sleep(0.02)
                    self.connection.settimeout(0.001)
                    try:
                        if self.connection.recv(1, 2) == b'':
                            raise ConnectionResetError
                    except (BlockingIOError, TimeoutError, OSError) as e:
                        if isinstance(e, ConnectionResetError):
                            raise
                    finally:
                        self.connection.settimeout(None)
            self.send_response(200)
            self.send_header('Content-Type', 'application/x-ndjson')
            self.end_headers()
            for i in range(300):
                chunk = {'message': {'content': f'tok{i} '}, 'done': False}
                self.wfile.write((json.dumps(chunk) + '\n').encode())
                self.wfile.flush()
                time.sleep(0.02)
        except (BrokenPipeError, ConnectionResetError, OSError):
            FakeOllama.disconnected.set()


@pytest.fixture
def fake_server():
    """Run the fake model server on a free port."""
    FakeOllama.disconnected = threading.Event()
    FakeOllama.received = threading.Event()
    srv = ThreadingHTTPServer(('127.0.0.1', 0), FakeOllama)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _worker(host):
    """A streaming worker pointed at the fake server."""
    QApplication.instance() or QApplication([])
    return StreamWorker('ollama', [{'role': 'user', 'content': 'hi'}], 'sys',
                        {'model': 'fake', 'ollama_host': host, 'num_ctx': 2048})


def test_stop_while_the_model_reads_the_prompt(fake_server):
    """Stop cuts the request before any token arrived."""
    FakeOllama.mode = 'slow_prompt'
    w = _worker(fake_server)
    w.start()
    assert FakeOllama.received.wait(3)
    t0 = time.monotonic()
    w.stop()
    assert w.wait(3000)
    assert time.monotonic() - t0 < 2
    assert FakeOllama.disconnected.wait(3)
    w.deleteLater()


def test_stop_while_streaming(fake_server):
    """Stop cuts a stream in progress and the server sees the client leave."""
    FakeOllama.mode = 'stream'
    w = _worker(fake_server)
    got = []
    w.token_received.connect(got.append)
    w.start()
    time.sleep(0.3)
    w.stop()
    assert w.wait(3000)
    assert FakeOllama.disconnected.wait(3)
    w.deleteLater()


def test_quitting_unloads_the_models_used(monkeypatch):
    """Every Ollama model used is unloaded once when the app quits."""
    calls = []
    monkeypatch.setattr(servers, 'unload_ollama_model', lambda m, host, timeout=4: calls.append(m) or True)
    monkeypatch.setattr(servers, '_RELEASED', False)
    monkeypatch.setattr(servers, '_MODELS_IN_USE', {})
    servers.note_model_in_use('ollama', 'qwen-a', 'http://127.0.0.1:11434')
    servers.note_model_in_use('ollama', 'qwen-a', 'http://127.0.0.1:11434')
    servers.note_model_in_use('custom', 'remote', 'https://api.example')
    assert servers.release_models() >= 1
    assert calls == ['qwen-a']
    assert servers.release_models() == 0


def test_run_py_releases_models_before_exiting():
    """Run.py frees the models itself, because os._exit skips atexit."""
    with open('Run.py', encoding='utf-8') as f:
        src = f.read()
    assert src.index('release_models()') < src.index('os._exit(')


def test_stop_interrupts_running_code():
    """A stop request ends running code at its next line."""
    ds = Dataset({'type': 'sample_data', 'sample_name': 'S', 'particle_data': [
        {'elements': {'56Fe': 1.0}, 'start_time': 0.0, 'end_time': 0.001}]})
    stop = threading.Event()
    threading.Timer(0.3, stop.set).start()
    t0 = time.monotonic()
    res = execute("while True:\n    pass", ds, timeout=30, stop_event=stop)
    assert res.error == "Stopped by the user."
    assert time.monotonic() - t0 < 3
