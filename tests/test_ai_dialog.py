# -*- coding: utf-8 -*-
"""End-to-end tests of the AI chat window with a scripted model.

A stand-in for the streaming worker replays prepared replies, so the whole
loop runs headless: code runs on the synthetic dataset, a failing attempt is
corrected and replaced, the takeaway's numbers are checked, an exploration
records findings and writes its summary, and the conversation exports.
"""
import time

import pytest
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

import results.ai.dialog as D
from results.ai.benchmark import build_questions, reference_model, run
from results.ai.node import AIAssistantNode
from results.ai.synthetic import make_dataset
from results.ai.widgets import FigureBubble, InteractiveTableBubble, NoticeBubble


class ScriptedWorker(QObject):
    """Replays the next scripted reply instead of calling a model."""

    token_received = Signal(str)
    stream_done = Signal(str)
    error_occurred = Signal(str)
    stats_update = Signal(int, float)
    usage_update = Signal(int, int)
    script = []
    requests = []

    def __init__(self, backend, msgs, sys_prompt, cfg, attachments=None):
        """Remember the request."""
        super().__init__()
        self.msgs, self.sys, self.cfg = msgs, sys_prompt, cfg

    def start(self):
        """Emit the next reply on the next event-loop turn."""
        ScriptedWorker.requests.append(self)
        reply = ScriptedWorker.script.pop(0)
        QTimer.singleShot(0, lambda: (self.token_received.emit(reply), self.stream_done.emit(reply)))

    def isFinished(self):
        """Always finished."""
        return True

    def stop(self):
        """Nothing to stop."""

    def wait(self, *args):
        """Nothing to wait for."""
        return True

    def requestInterruption(self):
        """Nothing to interrupt."""


def _pump(dialog, timeout=60.0):
    """Run the Qt event loop until the script is used up and the window is idle."""
    app = QApplication.instance()
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if not ScriptedWorker.script and dialog._worker is None and dialog._exp is None:
            for _ in range(5):
                app.processEvents()
            return
        time.sleep(0.005)
    raise AssertionError("the chat window did not finish in time")


@pytest.fixture
def dialog(monkeypatch):
    """A chat window on the synthetic dataset, wired to the scripted worker."""
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(D, 'StreamWorker', ScriptedWorker)
    monkeypatch.setattr(D.AIChatDialog, '_start_autodetect', lambda self: None)
    ScriptedWorker.script = []
    ScriptedWorker.requests = []
    dc, truth, limits = make_dataset()
    node = AIAssistantNode(None)
    node.process_data(dc)
    node.configure(None)
    d = node.chat_dialog
    d._ds.set_limits(limits)
    d._sys_cache.clear()
    d._cfg.update({'backend': 'ollama', 'model': 'scripted'})
    yield d
    d.shutdown()
    d.close()
    node.chat_dialog = None
    d.deleteLater()
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def _of(d, cls):
    """Widgets of one type in the conversation."""
    return [w for w in d._widgets if isinstance(w, cls)]


def test_failed_code_is_corrected_and_takeaway_checked(dialog):
    """A failing attempt is replaced by the fix and invented figures are flagged."""
    ScriptedWorker.script += [
        "Comparing.\n```python\nprint(df['diameter_Ti'])\n```",
        "Fixed.\n```python\nshow_table(compare_samples('Ti'))\nfig, ax = plt.subplots()\n"
        "ax.hist(df[col('size','Ti')].dropna(), bins=np.logspace(1, 3, 40))\n"
        "ax.set_xscale('log'); ax.set_xlabel('Ti diameter (nm)'); ax.set_ylabel('Particles')\n```",
        "Spiked_C has the largest Ti particles (median 96.91 nm); an average of 12.5 nm is made up.",
    ]
    dialog._input.setText("Is Ti bigger in some samples?")
    dialog._send()
    _pump(dialog)
    assert not ScriptedWorker.script
    assert len(_of(dialog, InteractiveTableBubble)) == 1
    assert len(_of(dialog, FigureBubble)) == 1
    notices = [w._lbl.text() for w in _of(dialog, NoticeBubble)]
    assert any('corrected its code 1 time' in n for n in notices)
    assert any('12.5' in n for n in notices) and not any('96.91' in n for n in notices)
    assert dialog._worker is None
    correction = ScriptedWorker.requests[1].msgs[-1]['content']
    assert 'KeyError' in correction


def test_explore_runs_after_a_question(dialog):
    """Exploration works after a chat question, records findings and summarises."""
    ScriptedWorker.script += [
        "No code needed: spICP-ToF-MS measures single particles.",
        "PLAN:\n1. Ce+La is real\n2. Ti+Fe is chance\nTesting 1.\n```python\n"
        "c = coincidence('Ce', 'La')\nshow_table(c)\n"
        "record_finding('Ce+La far above chance', n=int(c['observed_both'].iloc[-1]), p=1e-20, effect=100)\n```",
        "Testing 2.\n```python\nt = coincidence('Ti', 'Fe')\n"
        "record_finding('Ti+Fe explained by chance', p=float(t['p'].iloc[-1]))\n```",
        "EXPLORATION DONE",
        "**Supported**\n- Ce+La far above chance.\n\n**Not supported**\n- Ti+Fe association.",
    ]
    dialog._input.setText("What is spICP-ToF-MS?")
    ScriptedWorker.script, later = ScriptedWorker.script[:1], ScriptedWorker.script[1:]
    dialog._send()
    _pump(dialog)
    ScriptedWorker.script += later
    dialog._explore()
    _pump(dialog)
    assert not ScriptedWorker.script
    assert dialog._exp is None and dialog._worker is None
    last = dialog._history[-1]['content']
    assert 'Ce+La far above chance' in last and 'Recorded findings' in last
    pinned = ScriptedWorker.requests[-1].msgs[0]['content']
    assert pinned.startswith('USER QUESTION')
    kinds = [r['kind'] for r in dialog._cur.transcript]
    assert 'exploration' in kinds and 'table' in kinds


def test_export_report(dialog, tmp_path, monkeypatch):
    """The conversation exports as one HTML file with embedded figures."""
    ScriptedWorker.script += [
        "Plotting.\n```python\nfig, ax = plt.subplots()\nax.plot([1, 2], [1, 4])\n"
        "ax.set_xlabel('x'); ax.set_ylabel('y')\n```",
        "A straight line.",
    ]
    dialog._input.setText("plot")
    dialog._send()
    _pump(dialog)
    target = tmp_path / 'report.html'
    monkeypatch.setattr(D.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(target), ''))
    dialog._export_report()
    html = target.read_text()
    assert 'data:image/png;base64' in html and 'Code that ran' in html


def test_benchmark_reference_passes_and_wrong_model_fails():
    """The benchmark accepts correct answers and rejects wrong ones."""
    good = run(reference_model, verbose=False, only=['count_total', 'largest_ti', 'tife_chance', 'fig_hist'])
    assert all(o.passed for o in good)

    def wrong(question):
        """A model that always names the wrong sample and claims a real association."""
        def reply(messages, system):
            """Answer without code."""
            return "River_A has the largest particles; Ti+Fe is a real association. There are 5 particles."
        return reply

    bad = run(wrong, verbose=False, only=['count_total', 'largest_ti', 'tife_chance', 'fig_hist'])
    assert not any(o.passed for o in bad)


def test_benchmark_questions_have_reference_code():
    """Every question can be answered by its reference code."""
    dc, truth, _ = make_dataset()
    for q in build_questions(dc, truth):
        assert q.reference.strip()


def test_stop_interrupts_running_code_and_frees_the_window(dialog):
    """Stop during a long code run ends it at once and unlocks the input."""
    ScriptedWorker.script += ["Looping.\n```python\nwhile True:\n    pass\n```"]
    dialog._input.setText("loop forever")
    dialog._send()
    app = QApplication.instance()
    end = time.time() + 10
    while time.time() < end and dialog._code_worker is None:
        app.processEvents()
        time.sleep(0.01)
    assert dialog._code_worker is not None
    t0 = time.time()
    dialog._do_stop()
    assert dialog._worker is None and dialog._code_worker is None
    assert dialog._input.isEnabled()
    assert time.time() - t0 < 3
    assert any('Stopped' in w._lbl.text() for w in _of(dialog, NoticeBubble))


def test_closing_the_window_keeps_the_model(dialog, monkeypatch):
    """Closing the chat window stops work but leaves the model loaded for next time."""
    released = []
    monkeypatch.setattr('results.ai.servers.release_models', lambda *a, **k: released.append(1))
    dialog.close()
    assert not released
