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
from results.ai.benchmark import DATASETS, build_questions, make_variant, reference_model, run
from results.ai.node import AIAssistantNode
from results.ai.synthetic import make_dataset
from results.ai.prompts import NO_CODE_PREFIX
from results.ai.widgets import FigureBubble, InteractiveTableBubble, NoticeBubble, StreamBubble


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
        "Fixed.\n```python\nshow_table(compare_samples('Ti', 'diameter_nm'))\nfig, ax = plt.subplots()\n"
        "ax.hist(df[col('size','Ti')].dropna(), bins=np.logspace(1, 3, 40))\n"
        "ax.set_xscale('log'); ax.set_xlabel('Ti diameter (nm)'); ax.set_ylabel('Particles')\n```",
        "Spiked_C has the largest Ti particles (median 94.42 nm); an average of 12.5 nm is made up.",
    ]
    dialog._input.setText("Is Ti bigger in some samples?")
    dialog._send()
    _pump(dialog)
    assert not ScriptedWorker.script
    assert len(_of(dialog, InteractiveTableBubble)) == 1
    assert len(_of(dialog, FigureBubble)) == 1
    notices = [w._lbl.text() for w in _of(dialog, NoticeBubble)]
    assert any('corrected its code 1 time' in n for n in notices)
    assert any('12.5' in n for n in notices) and not any('94.42' in n for n in notices)
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


def test_explore_fixes_failed_code_without_using_a_turn(dialog):
    """A failing turn goes back for a fix on the same turn, and the first look is in the opening message."""
    ScriptedWorker.script += [
        "PLAN:\n1. Ce+La is real\nTesting 1.\n```python\nprint(df['nope'])\n```",
        "Fixed.\n```python\nc = coincidence('Ce', 'La')\n"
        "record_finding('Ce+La far above chance', p=1e-20)\n```",
        "EXPLORATION DONE",
        "**Supported**\n- Ce+La far above chance.",
    ]
    dialog._cfg['explore_max_turns'] = 2
    dialog._input.setText("Which elements share particles?")
    dialog._explore()
    _pump(dialog)
    assert not ScriptedWorker.script
    opening = ScriptedWorker.requests[0].msgs[0]['content']
    assert 'FIRST LOOK' in opening and 'Ce/La molar ratio differs' in opening
    fix = ScriptedWorker.requests[1].msgs[-1]['content']
    assert 'KeyError' in fix and 'does not use one of your turns' in fix
    third = ScriptedWorker.requests[2].msgs[-1]['content']
    assert third.startswith('[TURN 1 RESULT')
    assert 'Ce+La far above chance' in dialog._history[-1]['content']


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
    """Every question of every benchmark dataset has reference code."""
    for name in DATASETS:
        dc, truth, _ = make_variant(name)
        for q in build_questions(name, dc, truth):
            if q.kind == 'conversation':
                assert q.steps and all(step['reference'].strip() for step in q.steps)
            elif q.kind == 'explore':
                assert q.steps and q.reference_answer.strip()
            else:
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


def test_closing_the_window_frees_the_model_by_default(dialog, monkeypatch):
    """Closing the chat window unloads the model so its memory goes back to other work."""
    unloaded = []
    monkeypatch.setattr(D, 'unload_ollama_model', lambda model, base: unloaded.append(model) or True)
    dialog.close()
    assert unloaded == ['scripted']


def test_closing_can_keep_the_model(dialog, monkeypatch):
    """With the option off, closing leaves the model loaded for next time."""
    unloaded = []
    monkeypatch.setattr(D, 'unload_ollama_model', lambda model, base: unloaded.append(model) or True)
    dialog._cfg['unload_on_close'] = False
    dialog.close()
    assert not unloaded


def test_idle_model_is_freed_and_status_comes_back(dialog, monkeypatch):
    """After the idle time the model is unloaded; the next request marks it connected again."""
    unloaded = []
    monkeypatch.setattr(D, 'unload_ollama_model', lambda model, base: unloaded.append(model) or True)
    dialog._cfg['idle_unload_min'] = 10
    dialog._idle()
    assert dialog._idle_timer.isActive() and dialog._idle_timer.interval() == 600_000
    dialog._on_idle_timeout()
    assert unloaded == ['scripted'] and 'unloaded' in dialog._status.text()
    ScriptedWorker.script += ["Hello! What would you like to look at?"]
    dialog._input.setText("hi")
    dialog._send()
    _pump(dialog)
    assert 'unloaded' not in dialog._status.text()


def test_idle_timer_waits_while_busy(dialog, monkeypatch):
    """No unloading while a request or exploration is running."""
    unloaded = []
    monkeypatch.setattr(D, 'unload_ollama_model', lambda model, base: unloaded.append(model) or True)
    dialog._exp_mode = True
    dialog._on_idle_timeout()
    dialog._exp_mode = False
    assert not unloaded and dialog._idle_timer.isActive()


def test_freed_mlx_model_is_started_before_the_question(dialog, monkeypatch):
    """A question to a freed MLX model starts its server, waits, then sends."""
    started, sent = [], []
    dialog._cfg.update({'backend': 'mlx', 'model': '/models/Qwen-4bit'})
    monkeypatch.setattr(D, 'mlx_model_folder', lambda m: m)
    state = {'up': False}
    monkeypatch.setattr(D, 'fetch_openai_models', lambda host, timeout=0: ([], state['up'], ''))
    monkeypatch.setattr(D, 'mlx_server_command', lambda model, port: ['mlx_lm.server', '--model', model])

    class FakeProc:
        """Stands in for the server process."""
        def poll(self):
            """Still running."""
            return None
    monkeypatch.setattr(D.subprocess, 'Popen', lambda cmd, **kw: started.append(cmd) or FakeProc())
    monkeypatch.setattr(D, 'register_launched_server', lambda proc: None)
    assert dialog._mlx_needs_start()
    dialog._start_mlx_then(lambda: sent.append(1))
    assert started and 'Loading' in dialog._tlbl.text() and not sent
    state['up'] = True
    dialog._poll_loading()
    assert sent == [1] and dialog._loading is None


def test_reading_earlier_messages_is_not_interrupted(dialog):
    """Scrolling up while the model writes keeps the view where the user put it."""
    import time as _t
    app = QApplication.instance()
    dialog.resize(900, 600)
    dialog.show()
    for k in range(25):
        dialog._add_ai(f"Earlier answer {k}\n\n" + "A line of text. " * 40)
    for _ in range(20):
        app.processEvents()
        _t.sleep(0.01)
    bar = dialog._cur.scroll.verticalScrollBar()
    assert bar.maximum() > 0 and bar.value() == bar.maximum()
    bar.setValue(0)
    app.processEvents()
    assert dialog._cur.follow is False
    for k in range(5):
        dialog._add_ai(f"New output {k}\n\n" + "More text. " * 40)
    for _ in range(20):
        app.processEvents()
        _t.sleep(0.01)
    assert bar.value() == 0
    dialog._add_user("A new question")
    for _ in range(20):
        app.processEvents()
        _t.sleep(0.01)
    assert dialog._cur.follow is True and bar.value() == bar.maximum()
    dialog.hide()


def test_answer_without_code_is_computed_first(dialog):
    """Invented numbers go back once for code; the invented bubble is replaced."""
    ScriptedWorker.script += [
        "The median Ti diameter is 52.6 nm, as the histogram above shows.",
        "```python\nprint(df[col('size','Ti')].median())\n```",
        "That is the median Ti diameter.",
    ]
    dialog._input.setText("What is the median Ti diameter?")
    dialog._send()
    _pump(dialog)
    assert not ScriptedWorker.script
    assert ScriptedWorker.requests[1].msgs[-1]['content'].startswith(NO_CODE_PREFIX)
    notices = [w._lbl.text() for w in _of(dialog, NoticeBubble)]
    assert not any('check its numbers' in n for n in notices)
    shown = ' '.join(w.get_text() for w in _of(dialog, StreamBubble))
    assert '52.6' not in shown


def test_greeting_is_not_sent_back(dialog):
    """A plain greeting with data loaded is shown as it is."""
    ScriptedWorker.script += ["Hello! What would you like to look at in your samples?"]
    dialog._input.setText("hi")
    dialog._send()
    _pump(dialog)
    assert len(ScriptedWorker.requests) == 1


def test_fix_attempt_text_is_not_shown(dialog):
    """After a fix, the reply keeps the first attempt's intro, not the fix talk."""
    ScriptedWorker.script += [
        "Comparing Ti across samples.\n```python\nprint(df['diameter_Ti'])\n```",
        "The crash is fixed; now I just need to add labels.\n```python\nshow_table(compare_samples('Ti'))\n```",
        "Spiked_C has the largest Ti particles.",
    ]
    dialog._input.setText("Is Ti bigger in some samples?")
    dialog._send()
    _pump(dialog)
    shown = ' '.join(w.get_text() for w in _of(dialog, StreamBubble))
    assert 'Comparing Ti across samples.' in shown and 'crash is fixed' not in shown


def test_stopped_exploration_keeps_its_findings(dialog):
    """Stopping after a turn keeps the findings in the export and the history."""
    ScriptedWorker.script += [
        "PLAN:\n1. Ce+La is real\nTesting 1.\n```python\nc = coincidence('Ce', 'La')\n"
        "record_finding('Ce+La far above chance', p=1e-20)\n```",
    ]
    dialog._cfg['explore_max_turns'] = 4
    dialog._explore()
    app = QApplication.instance()
    end = time.time() + 30
    while time.time() < end and not (dialog._exp and dialog._exp.ledger.as_text()):
        app.processEvents()
        time.sleep(0.005)
    dialog._do_stop()
    kinds = [r['kind'] for r in dialog._cur.transcript]
    assert 'exploration' in kinds
    rec = [r for r in dialog._cur.transcript if r['kind'] == 'exploration'][-1]
    assert 'stopped' in rec['summary'] and 'Ce+La far above chance' in rec['findings']
    assert 'Ce+La far above chance' in dialog._history[-1]['content']


def test_explore_shows_only_the_fixed_attempt(dialog):
    """A turn whose first attempt failed shows one step, the fixed one."""
    ScriptedWorker.script += [
        "PLAN:\n1. Ce+La is real\nTesting 1.\n```python\nfig, ax = plt.subplots()\nax.plot([1, 2])\nprint(df['nope'])\n```",
        "Fixed.\n```python\nc = coincidence('Ce', 'La')\nrecord_finding('Ce+La far above chance', p=1e-20)\n```",
        "EXPLORATION DONE",
        "**Supported**\n- Ce+La far above chance.",
    ]
    dialog._cfg['explore_max_turns'] = 2
    dialog._explore()
    session = dialog._exp_session
    _pump(dialog)
    assert not ScriptedWorker.script
    assert session._steps == 1
