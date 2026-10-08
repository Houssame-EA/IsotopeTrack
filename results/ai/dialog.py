"""The AI Data Assistant chat window.

A question goes through three steps. The model writes code; the sandbox runs
it on the full particle table and the tables and figures appear in the
chat. If the code fails or a figure comes out empty, the model is shown the
problem and fixes it. Finally the model sees the exact results and writes
the takeaway, and any figure in that text that the code did not produce is
flagged.

Explore runs the same loop for several turns, keeping a plan and a ledger
of findings outside the chat history so nothing is lost when old messages
are trimmed, and writes its summary from that ledger.
"""
import logging
import os
import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor, QKeySequence
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSplitter, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from results.ai.attachments import (
    IMAGE_EXTS, extract_pdf_text, read_image_b64, read_text_file, try_parse_table,
)
from results.ai.data import Dataset
from results.ai.exploration import ExplorationState, is_done, parse_plan
from results.ai.prompts import (
    build_system_prompt, correction_request, figure_fix_request, first_exploration_message,
    fit_messages, interpretation_request, reply_reserve, suggest_questions, summary_request,
    turn_feedback,
)
from results.ai.report import build_html
from results.ai.sandbox import result_digest, unverified_numbers
from results.ai.servers import (
    MLX_BASE, OLLAMA_BASE, fetch_ollama_models, fetch_openai_models, install_server_shutdown_hooks,
    note_model_in_use, park_thread, pids_listening_on, port_of, retire_thread,
    shutdown_launched_servers, terminate_pids, unload_ollama_model,
)
from results.ai.settings import BackendDialog, CustomizeDialog
from results.ai.streaming import CodeWorker, ProbeWorker, StreamWorker
from results.ai.theme import CODE_RE, Theme, fs, strip_thinking
from results.ai.widgets import (
    AttachmentChip, AttachmentPreview, AutoGrowTextEdit, CodeBubble, ComposerResizeHandle,
    Conversation, ConversationListItem, ExplorationBubble, FigureBubble, InteractiveTableBubble,
    NoticeBubble, OutputBubble, StreamBubble, TextBubble,
)
from tools.theme import theme as global_theme

_itk_log = logging.getLogger("IsotopeTrack.results.ai.dialog")

MAX_FIX_ATTEMPTS = 3


def _icon(name, color):
    """A qtawesome icon, or an empty icon when qtawesome is unavailable."""
    try:
        import qtawesome as qta
        return qta.icon(name, color=color)
    except Exception:
        return QIcon()

MAX_FIGURE_FIXES = 1


class AIChatDialog(QDialog):
    """Chat window of the AI Assistant node."""

    def __init__(self, ai_node, pw=None):
        """Build the window.

        Args:
            ai_node (AIAssistantNode): The node that owns the window.
            pw: The main window, used for detection limits.
        """
        super().__init__(pw)
        self.node = ai_node
        self.parent_window = pw
        self.current_data = None
        self._ds = None
        self._worker = None
        self._code_worker = None
        self._code_queue = []
        self._code_results = []
        self._code_done = None
        self._sb = None
        self._pending_files = []
        self._user_stopped = False
        self._interpreting = False
        self._code_cache = {}
        self._sys_cache = {}
        self._turn = None
        self._autoconfigured = False
        self._probe = None
        self._exp = None
        self._exp_mode = False
        self._exp_session = None
        self._conversations = [Conversation(title="New chat")]
        self._current_idx = 0
        self._conv_items = {}
        self._cfg = {'backend': 'ollama', 'model': '', 'mlx_host': MLX_BASE,
                     'temperature': 0.2, 'num_ctx': 8192, 'explore_max_turns': 10,
                     'interpret_results': True, 'verify_numbers': True, 'fix_figures': True}
        self.setWindowTitle("AI Data Assistant")
        self.setMinimumSize(900, 650)
        self.resize(1240, 780)
        self._build_ui()
        self._start_autodetect()
        install_server_shutdown_hooks()

    @property
    def _cur(self):
        """The conversation on screen."""
        return self._conversations[self._current_idx]

    @property
    def _history(self):
        """Chat history of the conversation on screen."""
        return self._cur.history

    @property
    def _widgets(self):
        """Widgets of the conversation on screen."""
        return self._cur.widgets

    @property
    def _cl(self):
        """Layout holding the conversation's bubbles."""
        return self._cur.cl

    @property
    def _cw(self):
        """Widget holding the conversation's bubbles."""
        return self._cur.cw

    @property
    def _scroll(self):
        """Scroll area of the conversation on screen."""
        return self._cur.scroll

    @property
    def _num_ctx(self):
        """Context window of the configured model."""
        try:
            return max(2048, int(self._cfg.get('num_ctx', 8192) or 8192))
        except (TypeError, ValueError):
            return 8192

    def _worker_cfg(self):
        """Backend settings for one request, with the reply budget set."""
        cfg = dict(self._cfg)
        cfg['max_reply_tokens'] = reply_reserve(self._num_ctx)
        return cfg

    def _system_prompt(self, mode='chat'):
        """System prompt for the current data, cached until the data changes."""
        turns = int(self._cfg.get('explore_max_turns', 10))
        key = (mode, self._num_ctx, turns, id(self._ds))
        if key not in self._sys_cache:
            try:
                self._sys_cache[key] = build_system_prompt(self._ds, self._num_ctx, mode, turns)
            except Exception:
                _itk_log.exception("Could not build the dataset brief")
                self._sys_cache[key] = build_system_prompt(None, self._num_ctx, mode, turns)
        return self._sys_cache[key]

    def _add_widget(self, w):
        """Append a widget to the conversation on screen."""
        self._widgets.append(w)
        self._cl.insertWidget(self._cl.count() - 1, w)
        return w

    def _record(self, kind, **data):
        """Add an entry to the conversation's report transcript."""
        self._cur.transcript.append({'kind': kind, **data})

    def _busy(self, label):
        """Lock the input while the model works."""
        self._set_sidebar_enabled(False)
        self._input.setEnabled(False)
        self._sendb.setVisible(False)
        self._stop.setVisible(True)
        self._attach_btn.setEnabled(False)
        self._explore_btn.setEnabled(False)
        self._think.setVisible(True)
        self._tlbl.setText(label)

    def _idle(self):
        """Unlock the input after the model finished and release the worker."""
        park_thread(self._worker)
        self._worker = None
        self._think.setVisible(False)
        self._stop.setVisible(False)
        self._sendb.setVisible(True)
        self._explore_btn.setEnabled(self._ds is not None and len(self._ds) > 0)
        QTimer.singleShot(5000, lambda: self._speed.setVisible(False))
        self._enable()

    def _start_worker(self, messages, system, on_done, on_error=None, stream_to_bubble=True):
        """Start one streaming request.

        Args:
            messages (list): Chat messages, already fitted to the window.
            system (str): System prompt.
            on_done (callable): Slot receiving the full reply.
            on_error (callable): Slot receiving an error message.
            stream_to_bubble (bool): Show tokens live in a stream bubble.
        """
        park_thread(self._worker)
        backend = self._cfg.get('backend', '')
        host = self._cfg.get('mlx_host', MLX_BASE) if backend == 'mlx' else OLLAMA_BASE
        note_model_in_use(backend, self._cfg.get('model', ''), host)
        attachments = self._turn.get('attachments', []) if self._turn and stream_to_bubble else []
        self._worker = StreamWorker(self._cfg.get('backend', ''), messages, system,
                                    self._worker_cfg(), attachments)
        if self._turn is not None:
            self._turn['attachments'] = []
        if stream_to_bubble:
            self._sb = StreamBubble()
            self._add_widget(self._sb)
            self._worker.token_received.connect(self._on_tok)
        self._worker.stats_update.connect(self._on_stats)
        self._worker.usage_update.connect(self._on_usage)
        self._worker.stream_done.connect(on_done)
        self._worker.error_occurred.connect(on_error or self._on_err)
        self._speed.setVisible(True)
        self._worker.start()

    def _send(self):
        """Send the composer text as a question about the data."""
        text = self._input.text().strip()
        if not text and not self._pending_files:
            return
        if self._worker:
            return
        if not self._ensure_backend_ready():
            self._open_settings()
            return
        self._user_stopped = False
        self._maybe_set_conv_title(text)
        attachments = list(self._pending_files)
        for a in attachments:
            self._add_widget(AttachmentChip(a['name'], a.get('type', 'text')))
        if text:
            self._add_user(text)
            self._record('user', text=text)
        self._input.clear()
        self._clear_attachments()
        self._history.append({"role": "user", "content": text or "(see attached file)"})
        self._turn = {'fixes': 0, 'figure_fixes': 0, 'numbers': [], 'attempt_widgets': [],
                      'attachments': attachments}
        self._busy("Thinking…")
        self._request_answer()

    def _request_answer(self):
        """Ask the model for an answer to the latest message."""
        system = self._system_prompt('chat')
        msgs = fit_messages(list(self._history), system, self._num_ctx)
        self._start_worker(msgs, system, self._on_done)

    def _run_codes(self, codes, on_done):
        """Run code blocks one after the other in the background.

        Args:
            codes (list): Code blocks to run.
            on_done (callable): Receives ``[(code, ExecResult), ...]`` when all have run.
        """
        self._code_queue = list(codes)
        self._code_results = []
        self._code_done = on_done
        self._next_code()

    def _next_code(self):
        """Start the next queued code block, or hand all results on."""
        if self._user_stopped:
            return
        if not self._code_queue:
            done, results = self._code_done, self._code_results
            self._code_done = None
            self._code_results = []
            if done is not None:
                done(results)
            return
        code = self._code_queue.pop(0)
        hit = self._code_cache.get((code, id(self._ds)))
        if hit is not None:
            self._code_results.append((code, hit))
            QTimer.singleShot(0, self._next_code)
            return
        self._tlbl.setText("Running the code on your particles…")
        park_thread(self._code_worker)
        self._code_worker = CodeWorker(code, self._ds)
        self._code_worker.result_ready.connect(self._on_code_result)
        self._code_worker.start()

    def _on_code_result(self, code, res):
        """Keep one code block's result and move on to the next."""
        if self._user_stopped or self._code_done is None:
            return
        park_thread(self._code_worker)
        self._code_worker = None
        if not res.error:
            if len(self._code_cache) > 64:
                self._code_cache.clear()
            self._code_cache[(code, id(self._ds))] = res
        self._code_results.append((code, res))
        self._next_code()

    def _show_result(self, code, res):
        """Put a result's tables, figures and text in the chat.

        Returns:
            list: The widgets added, so a failed attempt can be removed.
        """
        added = []
        for tbl in res.tables:
            if tbl['headers']:
                added.append(self._add_widget(InteractiveTableBubble(
                    tbl['headers'], tbl['rows'], tbl['title'], note=tbl.get('note', ''))))
        for fig in res.figures:
            added.append(self._add_widget(FigureBubble(fig['figure'], fig['title'])))
        if res.text:
            parsed = try_parse_table(res.text)
            if parsed:
                added.append(self._add_widget(InteractiveTableBubble(parsed[0], parsed[1])))
            else:
                added.append(self._add_widget(OutputBubble(res.text)))
        for f in res.findings:
            added.append(self._add_widget(NoticeBubble("Finding: " + f['claim'], kind='info')))
        added.append(self._add_widget(CodeBubble(code)))
        return added

    def _record_result(self, code, res):
        """Add a successful result to the report transcript."""
        self._record('code', text=code)
        for tbl in res.tables:
            self._record('table', table=tbl)
        for fig in res.figures:
            self._record('figure', png=fig.get('png'), title=fig.get('title', ''))
        if res.text:
            self._record('text', text=res.text)

    def _on_done(self, full):
        """Handle the model's answer: run its code, fix problems, then explain."""
        if self._user_stopped:
            self._user_stopped = False
            return
        clean = strip_thinking(full).strip()
        if self._sb:
            self._sb.finalise(clean)
            self._turn['attempt_widgets'].append(self._sb)
            self._sb = None
        self._history.append({"role": "assistant", "content": clean})
        codes = [c.strip() for c in CODE_RE.findall(clean) if c.strip()]
        prose = CODE_RE.sub('', clean).strip()
        if not codes:
            self._record('assistant', text=prose)
            self._finish_turn()
            return
        if self._ds is None or not len(self._ds):
            self._add_widget(NoticeBubble("Connect particle data to the AI node to run the analysis.", kind='warn'))
            self._finish_turn()
            return
        current_bubble = self._turn['attempt_widgets'].pop() if self._turn['attempt_widgets'] else None
        for w in self._turn['attempt_widgets']:
            w.setParent(None)
            w.deleteLater()
            if w in self._widgets:
                self._widgets.remove(w)
        self._turn['attempt_widgets'] = [current_bubble] if current_bubble is not None else []
        self._turn['prose'] = prose
        self._run_codes(codes, self._after_codes)

    def _after_codes(self, results):
        """Show the results, ask for fixes when needed, then ask for the takeaway."""
        if self._turn is None:
            return
        prose = self._turn.get('prose', '')
        for code, res in results:
            self._turn['attempt_widgets'].extend(self._show_result(code, res))
        self._scrollb()
        errors = [r.error for _, r in results if r.error]
        if errors and self._turn['fixes'] < MAX_FIX_ATTEMPTS:
            self._turn['fixes'] += 1
            digest = '\n\n'.join(result_digest(r, 6) for _, r in results if r.produced)
            self._history.append({"role": "user", "content": correction_request(errors[0], digest)})
            self._turn['attempt_widgets'].append(self._add_widget(NoticeBubble(
                f"{errors[0].splitlines()[0]} — asking the model to fix it "
                f"(attempt {self._turn['fixes']}/{MAX_FIX_ATTEMPTS})", kind='warn')))
            self._tlbl.setText("Fixing the code…")
            self._request_answer()
            return
        warns = [w for _, r in results for w in r.warnings]
        if (warns and not errors and self._cfg.get('fix_figures', True)
                and self._turn['figure_fixes'] < MAX_FIGURE_FIXES):
            self._turn['figure_fixes'] += 1
            self._history.append({"role": "user", "content": figure_fix_request(warns)})
            self._turn['attempt_widgets'].append(self._add_widget(NoticeBubble(
                "The figure has problems (" + warns[0] + ") — asking the model to redraw it.", kind='info')))
            self._tlbl.setText("Improving the figure…")
            self._request_answer()
            return
        if errors:
            self._add_widget(NoticeBubble(errors[0], kind='error'))
            self._record('error', text=errors[0])
        elif self._turn['fixes'] or self._turn['figure_fixes']:
            n = self._turn['fixes'] + self._turn['figure_fixes']
            self._add_widget(NoticeBubble(
                f"The model corrected its code {n} time{'s' if n != 1 else ''} before this result.", kind='info'))
        if prose:
            self._record('assistant', text=prose)
        for code, res in results:
            self._turn['numbers'].extend(res.numbers)
            if not res.error:
                self._record_result(code, res)
        if prose:
            if self._cfg.get('verify_numbers', True):
                bad = unverified_numbers(prose, self._turn['numbers'])
                if bad:
                    self._add_widget(NoticeBubble(
                        "Figures written before the results, not produced by the code: " + ", ".join(bad[:8]),
                        kind='warn'))
        produced = [r for _, r in results if r.produced]
        if produced and self._cfg.get('interpret_results', True):
            digest = '\n\n'.join(result_digest(r, 15) for r in produced)
            self._turn['digest'] = digest
            self._history.append({"role": "user", "content": interpretation_request(digest)})
            self._interpreting = True
            self._tlbl.setText("Reading the results…")
            system = self._system_prompt('chat')
            msgs = fit_messages(list(self._history), system, self._num_ctx)
            self._start_worker(msgs, system, self._on_interpret_done)
            return
        self._finish_turn()

    def _on_interpret_done(self, full):
        """Show the grounded takeaway and check its numbers."""
        self._interpreting = False
        if self._user_stopped:
            self._user_stopped = False
            return
        prose = CODE_RE.sub('', strip_thinking(full)).strip()
        if self._sb:
            self._sb.finalise(prose)
            self._sb = None
        digest = (self._turn or {}).get('digest', '')
        if self._history and self._history[-1]['role'] == 'user':
            self._history[-1] = {"role": "user", "content": "[Results of the code above]\n" + digest[:3000]}
        if prose:
            self._history.append({"role": "assistant", "content": prose})
            self._record('assistant', text=prose)
            if self._cfg.get('verify_numbers', True):
                bad = unverified_numbers(prose, (self._turn or {}).get('numbers', []))
                if bad:
                    self._add_widget(NoticeBubble(
                        "Not found in the computed results: " + ", ".join(bad[:8]), kind='warn'))
        self._finish_turn()

    def _finish_turn(self):
        """End a question: scroll, unlock the input."""
        self._turn = None
        self._scrollb()
        self._idle()

    def _on_err(self, err):
        """Show a backend error and unlock the input."""
        if self._user_stopped:
            self._user_stopped = False
            return
        if self._sb:
            self._sb.finalise()
            self._sb = None
        if self._interpreting:
            self._interpreting = False
            if self._history and self._history[-1]['role'] == 'user':
                self._history.pop()
            self._finish_turn()
            return
        if self._history and self._history[-1]['role'] == 'user':
            self._history.pop()
        self._add_widget(NoticeBubble(f"Error: {err}", kind='error'))
        self._finish_turn()

    def _do_stop(self):
        """Stop the request in progress."""
        if not self._worker and not self._code_worker:
            return
        self._user_stopped = True
        self._interpreting = False
        for w in (self._worker, self._code_worker):
            if w is None:
                continue
            try:
                w.stop()
            except Exception:
                _itk_log.exception("Handled exception in _do_stop")
        if self._code_worker is not None:
            try:
                self._code_worker.result_ready.disconnect()
            except Exception:
                pass
            park_thread(self._code_worker)
            self._code_worker = None
        self._code_queue = []
        self._code_done = None
        self._code_results = []
        if self._sb:
            try:
                self._sb._raw = (self._sb._raw or "").rstrip() + "\n\n*[Stopped]*"
                self._sb.finalise()
            except Exception:
                _itk_log.exception("Handled exception in _do_stop")
            self._sb = None
        for sig in ('token_received', 'stats_update', 'usage_update', 'stream_done', 'error_occurred'):
            try:
                getattr(self._worker, sig).disconnect()
            except Exception:
                pass
        park_thread(self._worker)
        self._worker = None
        self._add_widget(NoticeBubble("Stopped.", kind='info'))
        if self._exp_mode:
            if self._exp_session:
                self._exp_session.mark_cancelled("stopped by user")
            self._teardown_exploration()
        self._turn = None
        self._idle()

    def _clear_chat(self):
        """Empty the conversation on screen."""
        if self._worker:
            return
        for w in list(self._widgets):
            w.setParent(None)
            w.deleteLater()
        self._widgets.clear()
        self._history.clear()
        self._cur.transcript.clear()
        self._add_ai("Chat cleared. Ask me anything about your data.")

    def _explore(self):
        """Start a multi-turn exploration of the data."""
        if self._ds is None or not len(self._ds):
            self._add_ai("⚠ Connect particle data first — exploration needs it.")
            return
        if self._worker:
            return
        if not self._ensure_backend_ready():
            self._open_settings()
            return
        question = self._input.text().strip() or (
            "Scan the dataset for anything unusual: differences between samples, real versus chance "
            "multi-element particles, truncation at the detection limit, outliers and time bursts.")
        self._input.clear()
        self._user_stopped = False
        self._exp_mode = True
        self._exp = ExplorationState(question=question, max_turns=int(self._cfg.get('explore_max_turns', 10)))
        self._exp.messages = [{"role": "user", "content": first_exploration_message(question)}]
        self._maybe_set_conv_title(f"Explore: {question}")
        self._add_user(f"Explore: {question}")
        self._record('user', text=f"Explore: {question}")
        self._exp_session = self._add_widget(ExplorationBubble(question))
        self._exp_session.set_progress(0, self._exp.max_turns, "Planning…")
        self._scrollb()
        self._busy("Exploring…")
        self._run_exploration_turn()

    def _run_exploration_turn(self):
        """Ask the model for its next query."""
        if self._user_stopped or not self._exp_mode:
            return
        st = self._exp
        if st.turn >= st.max_turns:
            self._finalize_exploration("turn limit reached")
            return
        st.turn += 1
        self._exp_session.set_progress(st.turn, st.max_turns, f"Turn {st.turn}: choosing what to test…")
        self._tlbl.setText(f"Exploring — turn {st.turn}/{st.max_turns}…")
        system = self._system_prompt('explore')
        msgs = fit_messages(st.messages, system, self._num_ctx, pinned=1)
        self._start_worker(msgs, system, self._on_exp_turn_done, self._on_exp_err, stream_to_bubble=False)

    def _on_exp_turn_done(self, full):
        """Run the turn's code, record findings and continue or finish."""
        if self._user_stopped or not self._exp_mode:
            return
        st = self._exp
        clean = strip_thinking(full).strip()
        st.messages.append({"role": "assistant", "content": clean})
        if not st.plan:
            st.plan = parse_plan(clean)
            self._exp_session.set_plan(st.plan)
        m = CODE_RE.search(clean)
        done = is_done(clean)
        if not m:
            if done or st.turn >= st.max_turns:
                self._finalize_exploration("the model finished")
                return
            st.failures += 1
            if st.failures >= 2:
                self._finalize_exploration("the model stopped writing code")
                return
            st.messages.append({"role": "user", "content":
                                "Write one line naming the hypothesis, then ONE ```python block — or EXPLORATION DONE."})
            QTimer.singleShot(50, self._run_exploration_turn)
            return
        code = m.group(1).strip()
        rationale = clean[:m.start()].strip()
        rationale = rationale.split('PLAN:')[0].strip() if st.turn == 1 and 'PLAN:' in rationale else rationale
        self._exp_session.set_progress(st.turn, st.max_turns, f"Turn {st.turn}: running the code…")
        self._run_codes([code], lambda results, r=rationale, d=done: self._on_exp_code_done(results, r, d))

    def _on_exp_code_done(self, results, rationale, done):
        """Record a turn's result and continue or finish the exploration."""
        if self._user_stopped or not self._exp_mode:
            return
        st = self._exp
        code, res = results[0]
        st.ledger.add(res.findings, st.turn)
        st.numbers.extend(res.numbers)
        self._exp_session.add_step(st.turn, rationale[-400:], code, res)
        self._exp_session.set_findings(st.ledger)
        if not res.error:
            self._record_result(code, res)
        st.failures = st.failures + 1 if res.error else 0
        self._scrollb()
        if st.failures >= 3:
            self._finalize_exploration("the code kept failing")
            return
        if done:
            self._finalize_exploration("the model finished")
            return
        st.messages.append({"role": "user", "content": turn_feedback(
            result_digest(res, 12), st.turn, st.max_turns, st.ledger.as_text(), st.plan_text())})
        park_thread(self._worker)
        self._worker = None
        QTimer.singleShot(50, self._run_exploration_turn)

    def _on_exp_err(self, err):
        """Handle a backend error during exploration."""
        if self._user_stopped or not self._exp_mode:
            return
        if self._exp.turn <= 1:
            self._exp_session.mark_cancelled(f"backend error: {err}")
            self._teardown_exploration()
            self._idle()
            return
        self._finalize_exploration(f"backend error on turn {self._exp.turn}")

    def _finalize_exploration(self, reason=""):
        """Ask for the final summary, written from the recorded findings."""
        if self._user_stopped or not self._exp_mode:
            return
        st = self._exp
        self._exp_session.set_progress(st.turn, st.max_turns, f"Writing the summary… ({reason})")
        self._tlbl.setText("Writing the summary…")
        st.messages.append({"role": "user", "content": summary_request(st.ledger.as_text(), st.question)})
        system = self._system_prompt('explore')
        msgs = fit_messages(st.messages, system, self._num_ctx, pinned=1)
        self._start_worker(msgs, system, self._on_exp_summary_done, self._on_exp_summary_err,
                           stream_to_bubble=False)

    def _on_exp_summary_done(self, full):
        """Show the summary, check its numbers and keep it in the chat history."""
        if self._user_stopped or not self._exp_mode:
            return
        st = self._exp
        clean = CODE_RE.sub('', strip_thinking(full)).strip()
        self._exp_session.set_summary(clean)
        if self._cfg.get('verify_numbers', True):
            bad = unverified_numbers(clean, st.numbers + st.ledger.numbers())
            if bad:
                self._add_widget(NoticeBubble(
                    "Summary figures not found in any result: " + ", ".join(bad[:8]), kind='warn'))
        findings = st.ledger.as_text()
        self._history.append({"role": "user", "content": f"Explore: {st.question}"})
        self._history.append({"role": "assistant", "content":
                              f"[Ran a {st.turn}-turn exploration]\n\n{clean}\n\nRecorded findings:\n{findings}"})
        self._record('exploration', question=st.question, summary=clean, findings=findings)
        self._teardown_exploration()
        self._idle()
        self._scrollb()

    def _on_exp_summary_err(self, err):
        """Handle a failed summary request."""
        if self._user_stopped or not self._exp_mode:
            return
        if self._exp_session:
            self._exp_session.mark_cancelled(f"summary failed: {err}")
        self._teardown_exploration()
        self._idle()

    def _teardown_exploration(self):
        """Forget the exploration state."""
        self._exp_mode = False
        self._exp_session = None
        self._exp = None
        self._worker = None

    def update_data_context(self, data):
        """Receive new particle data from the node.

        The particle table is built in the background so the first question
        does not wait for it.

        Args:
            data (dict): The node's input data.
        """
        self.current_data = data
        self._code_cache.clear()
        self._sys_cache.clear()
        self._ds = Dataset(data, self.parent_window) if data else None
        if self._ds is not None and len(self._ds):
            threading.Thread(target=lambda ds=self._ds: ds.df, daemon=True).start()
        self._update_sug(data)
        if data:
            dt = data.get('type', '')
            n = len(data.get('particle_data', []) or [])
            if dt == 'sample_data':
                self._add_ai(f"**Data loaded:** {data.get('sample_name', '?')} — {n:,} particles.")
            elif dt == 'multiple_sample_data':
                self._add_ai(f"**Multi-sample:** {len(data.get('sample_names', []))} samples, {n:,} particles total.")

    def _update_sug(self, data):
        """Rebuild the suggestion chips for the current data and enable Explore."""
        while self._sug_lo.count():
            item = self._sug_lo.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
        b = self._cfg.get('backend', '')
        ready = bool(b) and not (b == 'ollama' and not self._cfg.get('model'))
        has_data = bool(data) and self._ds is not None and len(self._ds) > 0
        self._explore_btn.setEnabled(ready and has_data)
        if not ready:
            self._sug.setVisible(False)
            return
        try:
            items = suggest_questions(self._ds) if has_data else [("What can you do?", "What can you do?")]
        except Exception:
            _itk_log.exception("Could not build suggestions")
            items = [("Element table", "Element frequency and size table")]
        for label, question in items:
            btn = QPushButton(label)
            btn.setToolTip(question)
            self._style_sug_btn(btn)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda _, t=question: (self._input.setText(t), self._send()))
            self._sug_lo.addWidget(btn)
        self._sug_lo.addStretch()
        self._sug.setVisible(True)

    def _export_report(self):
        """Save the conversation on screen as an HTML report."""
        if not self._cur.transcript:
            self._add_ai("Nothing to export yet — ask a question first.")
            return
        safe = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in self._cur.title).strip() or 'AI report'
        path, _ = QFileDialog.getSaveFileName(self, "Export conversation", f"{safe}.html", "HTML report (*.html)")
        if not path:
            return
        if not path.lower().endswith('.html'):
            path += '.html'
        line = ''
        if self.node is not None:
            try:
                line = self.node.get_data_summary()
            except Exception:
                line = ''
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(build_html(self._cur.title, self._cur.transcript, line))
            self._add_ai(f"✓ Report saved to `{os.path.basename(path)}`.")
        except Exception as e:
            _itk_log.exception("Report export failed")
            self._add_ai(f"⚠ Could not save the report: {e}")

    def _tool(self, text, icon, tip, slot):
        """A toolbar button in the Figure Builder style."""
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon if text else Qt.ToolButtonIconOnly)
        b.setAutoRaise(True)
        b.setCursor(QCursor(Qt.PointingHandCursor))
        b.clicked.connect(slot)
        self._icon_buttons.append((b, icon, False))
        return b

    def _sep(self):
        """A thin vertical separator for the toolbar."""
        line = QFrame()
        line.setObjectName('fbSep')
        line.setFrameShape(QFrame.VLine)
        return line

    def _build_ui(self):
        """Build the toolbar, conversation list, chat panel and composer."""
        self._icon_buttons = []
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        toolbar = QFrame()
        toolbar.setObjectName('fbToolbar')
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(6, 4, 6, 4)
        bar.setSpacing(2)
        self._sidebar_btn = self._tool('', 'fa6s.table-columns', 'Show or hide the conversations',
                                       self._toggle_sidebar)
        self._sidebar_btn.setCheckable(True)
        self._sidebar_btn.setChecked(True)
        bar.addWidget(self._sidebar_btn)
        bar.addWidget(self._sep())
        self._new_chat_btn = self._tool('New chat', 'fa6s.pen-to-square', 'Start a new conversation (Ctrl+N)',
                                        lambda: self._new_conversation(switch_to=True))
        bar.addWidget(self._new_chat_btn)
        self._clear_btn = self._tool('Clear', 'fa6s.eraser', 'Clear this conversation (Ctrl+K)', self._clear_chat)
        bar.addWidget(self._clear_btn)
        bar.addWidget(self._sep())
        self._explore_btn = self._tool(
            'Explore data', 'fa6s.wand-magic-sparkles',
            'Let the model plan and test hypotheses over several turns, recording what it finds.\n'
            'Type a question first to focus it. The number of turns is set in Settings.', self._explore)
        bar.addWidget(self._explore_btn)
        bar.addWidget(self._sep())
        self._sbtn = self._tool('Model', 'fa6s.microchip', 'Choose the model, context window and checks',
                                self._open_settings)
        bar.addWidget(self._sbtn)
        self._eject_btn = self._tool('', 'fa6s.eject', 'Unload the model from memory now.\n'
                                     'It is also unloaded when IsotopeTrack closes.', self._eject_model)
        bar.addWidget(self._eject_btn)
        self._cust_btn = self._tool('', 'fa6s.font', 'Font size, preview quality, timestamps', self._open_customize)
        bar.addWidget(self._cust_btn)
        bar.addStretch()
        self._speed = QLabel("")
        self._speed.setObjectName('fbStatus')
        self._speed.setVisible(False)
        bar.addWidget(self._speed)
        self._usage = QLabel("")
        self._usage.setObjectName('fbStatus')
        self._usage.setVisible(False)
        bar.addWidget(self._usage)
        bar.addSpacing(8)
        self._dot = QLabel("●")
        bar.addWidget(self._dot)
        self._status = QLabel("Not connected")
        self._status.setObjectName('fbStatus')
        bar.addWidget(self._status)
        bar.addSpacing(8)
        self._export_btn = QPushButton(' Export report…')
        self._export_btn.setObjectName('fbPrimary')
        self._export_btn.setToolTip("Save this conversation, with its tables, figures and code, as an HTML report")
        self._export_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._export_btn.clicked.connect(self._export_report)
        bar.addWidget(self._export_btn)
        root.addWidget(toolbar)
        self._hdr = toolbar

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        self._sidebar = QFrame()
        self._sidebar.setObjectName('aiPanel')
        self._sidebar.setMinimumWidth(190)
        sb = QVBoxLayout(self._sidebar)
        sb.setContentsMargins(8, 10, 8, 8)
        sb.setSpacing(6)
        self._conv_hdr = QLabel("Conversations")
        self._conv_hdr.setObjectName('aiSection')
        sb.addWidget(self._conv_hdr)
        self._conv_list_sc = QScrollArea()
        self._conv_list_sc.setObjectName('aiPlain')
        self._conv_list_sc.setWidgetResizable(True)
        self._conv_list_sc.setFrameShape(QFrame.NoFrame)
        self._conv_list_sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._conv_list_w = QWidget()
        self._conv_list_w.setObjectName('aiPlain')
        self._conv_list_lo = QVBoxLayout(self._conv_list_w)
        self._conv_list_lo.setContentsMargins(0, 0, 0, 0)
        self._conv_list_lo.setSpacing(2)
        self._conv_list_lo.addStretch()
        self._conv_list_sc.setWidget(self._conv_list_w)
        sb.addWidget(self._conv_list_sc, stretch=1)
        split.addWidget(self._sidebar)

        main_wrap = QWidget()
        main = QVBoxLayout(main_wrap)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(6)
        self._sug = QFrame()
        self._sug.setObjectName('aiPlain')
        self._sug_lo = QHBoxLayout(self._sug)
        self._sug_lo.setContentsMargins(2, 0, 2, 0)
        self._sug_lo.setSpacing(6)
        main.addWidget(self._sug)

        self._chat_panel = QFrame()
        self._chat_panel.setObjectName('fbPreview')
        cp = QVBoxLayout(self._chat_panel)
        cp.setContentsMargins(1, 1, 1, 1)
        cp.setSpacing(0)
        self._chat_stack = QStackedWidget()
        self._chat_stack.addWidget(self._conversations[0].scroll)
        cp.addWidget(self._chat_stack, stretch=1)
        self._think = QFrame()
        self._think.setObjectName('aiThink')
        self._think.setVisible(False)
        tl = QHBoxLayout(self._think)
        tl.setContentsMargins(14, 5, 14, 5)
        tl.setSpacing(8)
        self._tlbl = QLabel("Thinking…")
        self._tlbl.setObjectName('fbStatus')
        tl.addWidget(self._tlbl)
        prog = QProgressBar()
        prog.setRange(0, 0)
        prog.setMaximumHeight(3)
        prog.setTextVisible(False)
        tl.addWidget(prog)
        cp.addWidget(self._think)
        main.addWidget(self._chat_panel, stretch=1)

        outer = QWidget()
        outer_l = QVBoxLayout(outer)
        outer_l.setContentsMargins(0, 0, 0, 0)
        outer_l.setSpacing(2)
        self._resize_handle = ComposerResizeHandle()
        self._resize_handle.setToolTip("Drag to resize the input — double-click to reset")
        self._resize_handle.delta_y.connect(self._on_composer_resize)
        self._resize_handle.reset.connect(self._reset_composer_height)
        outer_l.addWidget(self._resize_handle)
        self._composer = QFrame()
        self._composer.setObjectName('aiComposer')
        comp_l = QVBoxLayout(self._composer)
        comp_l.setContentsMargins(8, 6, 8, 6)
        comp_l.setSpacing(6)
        self._preview_row = QWidget()
        self._preview_lo = QHBoxLayout(self._preview_row)
        self._preview_lo.setContentsMargins(2, 2, 2, 2)
        self._preview_lo.setSpacing(6)
        self._preview_lo.addStretch()
        self._preview_row.setVisible(False)
        comp_l.addWidget(self._preview_row)
        self._previews = []
        in_row = QHBoxLayout()
        in_row.setContentsMargins(0, 0, 0, 0)
        in_row.setSpacing(6)
        self._attach_btn = QToolButton()
        self._attach_btn.setToolTip("Attach an image, PDF or text file")
        self._attach_btn.setAutoRaise(True)
        self._attach_btn.clicked.connect(self._attach_file)
        self._icon_buttons.append((self._attach_btn, 'fa6s.paperclip', False))
        in_row.addWidget(self._attach_btn, alignment=Qt.AlignBottom)
        self._input = AutoGrowTextEdit()
        self._input.setObjectName('aiInput')
        self._input.setPlaceholderText("Ask about your data…   (Shift+Enter for a new line, Esc to stop)")
        self._input.submit.connect(self._send)
        in_row.addWidget(self._input, stretch=1)
        self._stop = QPushButton(" Stop")
        self._stop.setObjectName('aiStop')
        self._stop.setToolTip("Stop the model and any running code now (Esc)")
        self._stop.setVisible(False)
        self._stop.clicked.connect(self._do_stop)
        self._icon_buttons.append((self._stop, 'fa6s.stop', True))
        in_row.addWidget(self._stop, alignment=Qt.AlignBottom)
        self._sendb = QPushButton(" Send")
        self._sendb.setObjectName('fbPrimary')
        self._sendb.clicked.connect(self._send)
        self._icon_buttons.append((self._sendb, 'fa6s.paper-plane', True))
        in_row.addWidget(self._sendb, alignment=Qt.AlignBottom)
        comp_l.addLayout(in_row)
        outer_l.addWidget(self._composer)
        self._counter = QLabel("0 chars")
        self._counter.setObjectName('fbHint')
        self._counter.setAlignment(Qt.AlignRight)
        self._input.char_changed.connect(self._update_counter)
        outer_l.addWidget(self._counter)
        main.addWidget(outer)
        self._inp_frame = outer
        split.addWidget(main_wrap)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([220, 1000])
        root.addWidget(split, stretch=1)

        self._attach_bar = self._preview_row
        self._attach_lbl = self._counter

        from PySide6.QtGui import QShortcut
        QShortcut(QKeySequence("Ctrl+K"), self).activated.connect(self._clear_chat)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(
            lambda: self._new_conversation(switch_to=True))
        QShortcut(QKeySequence("Escape"), self).activated.connect(
            lambda: self._do_stop() if (self._worker or self._code_worker) else None)

        self._add_conv_list_item(self._conversations[0], is_current=True)

        self._apply_theme()
        global_theme.themeChanged.connect(self._on_global_theme_change)
        self._add_ai(
            "**AI Data Assistant — runs on your own computer.**\n\n"
            "Start Ollama or an MLX server, or click **Model** to choose one.")
        self._update_sug(None)

    def _toggle_sidebar(self):
        """Show or hide the conversation list."""
        self._sidebar.setVisible(self._sidebar_btn.isChecked())

    def _open_settings(self):
        """Open the backend settings and apply the chosen model."""
        d = BackendDialog(self._cfg, self)
        if d.exec() == QDialog.Accepted:
            self._cfg = d.get_config()
            b = self._cfg['backend']
            if b == 'ollama' and self._cfg.get('model'):
                self._set_dot('success_dot')
                self._status.setText(f"Ollama: {self._cfg['model']}")
                self._add_ai(f"**Connected — Ollama** `{self._cfg['model']}`")
            elif b == 'mlx':
                self._set_dot('success_dot')
                self._status.setText(f"MLX: {self._cfg.get('mlx_host','')}")
                self._add_ai(f"**Connected — MLX** `{self._cfg.get('mlx_host','')}`")
            elif b == 'custom' and self._cfg.get('custom_base_url'):
                self._set_dot('success_dot')
                mdl = self._cfg.get('custom_model','')
                self._status.setText(f"Custom API: {mdl or self._cfg.get('custom_base_url','')}")
                self._add_ai(f"**Connected — Custom API** `{mdl}`")
            else:
                self._set_dot('error_dot')
                self._status.setText("Not connected")
            self._update_sug(self.current_data)

    def _open_customize(self):
        """Open the appearance settings."""
        d = CustomizeDialog(self)
        d.applied.connect(self._apply_theme) 
        d.exec()

    def _update_counter(self, n_chars):
        """Show the composer's character count and token estimate.

        Args:
            n_chars (int): Characters typed.
        """
        tokens = max(0, round(n_chars / 3.5))
        self._counter.setText(f"{n_chars:,} chars  ~{tokens:,} tokens")

    def _add_conv_list_item(self, conv, is_current=False):
        """Create the sidebar entry for an existing Conversation."""
        item = ConversationListItem(conv.id, conv.title, is_current=is_current)
        item.selected.connect(self._switch_conversation)
        item.deleted.connect(self._delete_conversation)
        self._conv_list_lo.insertWidget(self._conv_list_lo.count() - 1, item)
        self._conv_items[conv.id] = item

    def _new_conversation(self, switch_to=True):
        """Create a new conversation, add it to the stack and sidebar."""
        if self._worker:
            return   
        existing_titles = {c.title for c in self._conversations}
        if "New chat" not in existing_titles:
            title = "New chat"
        else:
            n = 2
            while f"New chat {n}" in existing_titles:
                n += 1
            title = f"New chat {n}"
        conv = Conversation(title=title)
        self._conversations.append(conv)
        self._chat_stack.addWidget(conv.scroll)
        self._add_conv_list_item(conv, is_current=False)
        if switch_to:
            self._switch_conversation(conv.id)
            self._add_ai(
                "**New conversation.** Ask me anything about your data — "
                "I'll keep this thread separate from the others.")

    def _switch_conversation(self, conv_id):
        """Switch to the conversation with the given id. Saves the current draft
        (composer text + attachments) and restores the target's draft."""
        if self._worker:
            return  
        target_idx = None
        for i, c in enumerate(self._conversations):
            if c.id == conv_id:
                target_idx = i; break
        if target_idx is None or target_idx == self._current_idx:
            return

        cur = self._cur
        cur.draft_text  = self._input.toPlainText()
        cur.draft_files = list(self._pending_files)

        old_item = self._conv_items.get(cur.id)
        if old_item: old_item.set_current(False)

        self._current_idx = target_idx
        self._chat_stack.setCurrentWidget(self._cur.scroll)

        new_item = self._conv_items.get(self._cur.id)
        if new_item: new_item.set_current(True)

        self._clear_attachments()
        self._input.setPlainText(self._cur.draft_text or "")
        for entry in (self._cur.draft_files or []):
            self._pending_files.append(entry)
            kind = entry.get('type', 'text')
            img_b64 = entry.get('data') if kind == 'image' else None
            self._add_preview(entry.get('name', '?'), kind, entry, image_b64=img_b64)

        self._update_sug(self.current_data)
        self._scrollb()

    def _delete_conversation(self, conv_id):
        """Delete a conversation. If it's the current one, switch to a neighbour.
        If it's the last conversation, replace it with a fresh empty one."""
        if self._worker:
            return
        idx = None
        for i, c in enumerate(self._conversations):
            if c.id == conv_id:
                idx = i; break
        if idx is None: return

        if len(self._conversations) == 1:
            self._clear_chat()
            return

        conv = self._conversations[idx]
        was_current = (idx == self._current_idx)

        item = self._conv_items.pop(conv_id, None)
        if item:
            item.setParent(None); item.deleteLater()

        self._chat_stack.removeWidget(conv.scroll)
        conv.scroll.setParent(None); conv.scroll.deleteLater()

        del self._conversations[idx]

        if was_current:
            new_idx = max(0, idx - 1)
            self._current_idx = new_idx
            self._chat_stack.setCurrentWidget(self._cur.scroll)
            new_item = self._conv_items.get(self._cur.id)
            if new_item: new_item.set_current(True)
            self._clear_attachments()
            self._input.setPlainText(self._cur.draft_text or "")
            for entry in (self._cur.draft_files or []):
                self._pending_files.append(entry)
                kind = entry.get('type', 'text')
                img_b64 = entry.get('data') if kind == 'image' else None
                self._add_preview(entry.get('name','?'), kind, entry, image_b64=img_b64)
            self._update_sug(self.current_data)
            self._scrollb()
        elif idx < self._current_idx:
            self._current_idx -= 1

    def _maybe_set_conv_title(self, text):
        """If the current conversation still has its auto-generated title and
        the user just sent their first message, derive a short title from it."""
        conv = self._cur
        if not conv._auto_title: return
        if not text: return
        title = text.strip().split('\n', 1)[0]
        if len(title) > 32: title = title[:30].rstrip() + '…'
        conv.title       = title
        conv._auto_title = False
        item = self._conv_items.get(conv.id)
        if item: item.set_title(title)

    def _set_sidebar_enabled(self, enabled):
        """Enable/disable conversation switching (used during streaming)."""
        self._new_chat_btn.setEnabled(enabled)
        for item in self._conv_items.values():
            item.setEnabled(enabled)

    def _attach_file(self):
        """Let the user attach an image, PDF or text file to the next message."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Attach File", "",
            "Supported files (*.png *.jpg *.jpeg *.bmp *.tiff *.webp "
            "*.pdf *.txt *.csv *.json *.md *.tsv);;"
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.webp);;"
            "Documents (*.pdf *.txt *.csv *.json *.md *.tsv)")
        if not path: return
        ext  = os.path.splitext(path)[1].lower()
        name = os.path.basename(path)

        if ext in IMAGE_EXTS:
            data, mime = read_image_b64(path)
            entry = {'type':'image','name':name,'data':data,'mime':mime}
            self._pending_files.append(entry)
            self._add_preview(name, 'image', entry, image_b64=data)

        elif ext == '.pdf':
            text = extract_pdf_text(path)
            if text == "__MISSING_PYPDF__":
                self._add_ai("PDF reading requires pypdf.\nInstall with:  `pip install pypdf`")
                return
            if not text:
                self._add_ai(f"Could not extract text from **{name}**.")
                return
            entry = {'type':'text','name':name,'content':text}
            self._pending_files.append(entry)
            self._add_preview(name, 'pdf', entry)

        else:
            try:
                content = read_text_file(path)
                entry = {'type':'text','name':name,'content':content}
                self._pending_files.append(entry)
                self._add_preview(name, 'text', entry)
            except Exception as e:
                _itk_log.exception("Handled exception in _attach_file")
                self._add_ai(f"Could not read **{name}**: {e}")

    def _add_preview(self, name, kind, entry, image_b64=None):
        """Show an inline preview chip inside the composer"""
        prev = AttachmentPreview(name, kind, image_b64=image_b64)
        prev._entry = entry  
        prev.removed.connect(self._remove_preview)
        self._preview_lo.insertWidget(self._preview_lo.count() - 1, prev)
        self._previews.append(prev)
        self._preview_row.setVisible(True)

    def _remove_preview(self, prev):
        """Remove one preview chip and its pending file."""
        entry = getattr(prev, '_entry', None)
        if entry in self._pending_files:
            self._pending_files.remove(entry)
        if prev in self._previews:
            self._previews.remove(prev)
        prev.setParent(None); prev.deleteLater()
        if not self._previews:
            self._preview_row.setVisible(False)

    def _clear_attachments(self):
        """Remove every pending attachment from the composer."""
        for prev in list(self._previews):
            prev.setParent(None); prev.deleteLater()
        self._previews.clear()
        self._pending_files.clear()
        self._preview_row.setVisible(False)

    def _on_composer_resize(self, dy):
        """User dragged the resize handle. dy > 0 = drag down (shrink),
        dy < 0 = drag up (grow)."""
        cur = self._input.get_forced_height() or self._input.height()
        new_h = cur - dy
        self._input.set_forced_height(new_h)

    def _reset_composer_height(self):
        """Double-click on the handle → back to auto-grow."""
        self._input.set_forced_height(None)

    def _on_tok(self, t):
        """Append a streamed token to the live reply.

        Args:
            t (str): Token text.
        """
        if self._user_stopped: return
        if self._sb: self._sb.append(t); self._scrollb()

    def _on_usage(self, prompt_tokens, completion_tokens):
        """Show the token counts reported by the backend for the last reply.

        Args:
            prompt_tokens (int): Tokens the server consumed for the prompt.
            completion_tokens (int): Tokens the server generated.
        """
        if not (prompt_tokens or completion_tokens):
            return
        self._session_tokens = getattr(self, '_session_tokens', 0) + \
            prompt_tokens + completion_tokens
        limit = int(self._cfg.get('num_ctx', 8192) or 8192)
        share = f" · {prompt_tokens * 100 // limit}% of {limit:,} ctx" if limit else ""
        self._usage.setVisible(True)
        self._usage.setText(
            f"{prompt_tokens:,} in · {completion_tokens:,} out{share} · "
            f"session {self._session_tokens:,}")
        self._usage.setToolTip(
            "Tokens reported by the model server for the last message, and the "
            "running total for this session.")

    def _on_stats(self, n, el):
        """Show the generation speed.

        Args:
            n (int): Tokens so far.
            el (float): Seconds elapsed.
        """
        if self._user_stopped: return
        if el > 0: self._speed.setText(f"{n/el:.1f} tok/s")

    MAX_AI_RETRIES = 3

    def _enable(self):
        """Re-enable the composer and the sidebar."""
        self._input.setEnabled(True); self._sendb.setVisible(True)
        self._stop.setVisible(False); self._attach_btn.setEnabled(True)
        self._set_sidebar_enabled(True)
        self._input.setFocus()

    def _style_sug_btn(self, btn):
        """Mark a suggestion chip for the window stylesheet.

        Args:
            btn (QPushButton): The chip.
        """
        btn.setObjectName('aiChip')

    def _update_sug_style(self):
        """Kept for callers; chips are styled by the window stylesheet."""

    def _on_global_theme_change(self, name):
        """Follow the application theme.

        Args:
            name (str): ``light`` or ``dark``.
        """
        self._apply_theme()

    def _window_qss(self):
        """The Figure Builder stylesheet plus the chat window's own pieces."""
        from results.figure_builder.ui import look
        p = look.palette()
        size = fs()
        return look.window_qss(p) + f"""
        QFrame#aiPanel {{
            background: {p.bg_secondary};
            border: 1px solid {p.border_subtle};
            border-radius: 8px;
        }}
        QLabel#aiSection {{
            color: {p.text_muted}; font-size: {fs(-3)}px; font-weight: 700;
            letter-spacing: 0.6px; text-transform: uppercase; padding-left: 4px;
        }}
        QScrollArea#aiPlain, QWidget#aiPlain, QFrame#aiPlain {{ background: transparent; border: none; }}
        QFrame#fbPreview QScrollArea {{ background: transparent; border: none; }}
        QFrame#aiThink {{ background: {p.bg_secondary}; border-top: 1px solid {p.border_subtle}; }}
        QFrame#aiComposer {{
            background: {p.bg_secondary};
            border: 1px solid {p.border};
            border-radius: 10px;
        }}
        QPlainTextEdit#aiInput {{
            border: none; background: transparent; color: {p.text_primary};
            font-size: {size}px; padding: 6px 4px;
        }}
        QPushButton#aiChip {{
            background: {p.bg_secondary};
            color: {p.text_primary};
            border: 1px solid {p.border};
            border-radius: 13px;
            padding: 4px 12px;
            font-weight: 500;
            font-size: {fs(-2)}px;
        }}
        QPushButton#aiChip:hover {{ background: {p.accent_soft}; border-color: {p.accent}; }}
        QPushButton#aiStop {{
            background: {p.danger};
            color: {p.text_inverse};
            border: none;
            padding: 6px 14px;
        }}
        QPushButton#aiStop:hover {{ background: {p.danger_border}; }}
        QPushButton#fbPrimary:disabled {{ background: {p.disabled}; }}
        """

    def _set_dot(self, kind):
        """Colour the connection dot.

        Args:
            kind (str): ``success_dot``, ``error_dot`` or another colour name.
        """
        self._dot_kind = kind
        self._dot.setStyleSheet(f"color:{Theme.c(kind)};font-size:10px;background:transparent;")

    def _apply_theme(self):
        """Restyle the whole window for the current theme and font size."""
        from results.figure_builder.ui import look
        p = look.palette()
        self.setStyleSheet(self._window_qss())
        for button, name, inverse in getattr(self, '_icon_buttons', []):
            try:
                button.setIcon(_icon(name, p.text_inverse if inverse else look.icon_color()))
            except RuntimeError:
                pass
        self._set_dot(getattr(self, '_dot_kind', 'text_tertiary'))
        for conv in self._conversations:
            conv.cw.setStyleSheet(f"QWidget#chatContent{{background:{p.bg_tertiary};}}")
            for w in conv.widgets:
                if hasattr(w, 'apply_theme'):
                    w.apply_theme()
        for it in self._conv_items.values():
            it.apply_theme()
        for prev in getattr(self, '_previews', []):
            prev.apply_theme()
        if hasattr(self, '_resize_handle'):
            self._resize_handle.apply_theme()
            self._resize_handle.update()

    def _add_user(self, t):
        """Show a user message.

        Args:
            t (str): Message text.
        """
        b = TextBubble(t, True); self._widgets.append(b)
        self._cl.insertWidget(self._cl.count()-1, b); self._scrollb()

    def _add_ai(self, t):
        """Show an assistant message.

        Args:
            t (str): Markdown text.
        """
        b = TextBubble(t, False); self._widgets.append(b)
        self._cl.insertWidget(self._cl.count()-1, b); self._scrollb()

    def _scrollb(self):
        """Scroll the chat to the newest message."""
        QTimer.singleShot(50, lambda:
            self._scroll.verticalScrollBar().setValue(
                self._scroll.verticalScrollBar().maximum()))

    def _start_autodetect(self):
        """Probe loopback for a running model server and self-configure, so the
        user can start chatting without opening settings."""
        if self._probe is not None and self._probe.isRunning():
            return
        try:
            self._probe = ProbeWorker(self._cfg.get('mlx_host', MLX_BASE))
            self._probe.ready.connect(self._on_autodetect)
            self._probe.info.connect(self._on_autodetect_info)
            self._probe.start()
        except Exception:
            _itk_log.exception("Handled exception in _start_autodetect")

    def _on_autodetect(self, backend, model, label):
        """Apply a detected backend unless the user already picked one."""
        if self._autoconfigured or self._cfg.get('model'):
            return
        self._autoconfigured = True
        self._cfg['backend'] = backend
        self._cfg['model'] = model
        _itk_log.info("Auto-detected model server: %s", label)
        self._set_connected_status(label)
        self._add_ai(f"✓ Connected to {label} — ask a question about your data, "
                     "or click Explore.")
        self._update_sug(self.current_data)

    def _on_autodetect_info(self, msg):
        """Show a hint from the server probe.

        Args:
            msg (str): The hint.
        """
        if not self._autoconfigured:
            self._add_ai(f"ℹ {msg}")

    def _eject_model(self):
        """Free the memory held by the model currently loaded.

        Ollama is asked to evict the model. For MLX the server itself holds the
        weights, so a server this app started is stopped outright, and one the
        user started is only stopped after they confirm.
        """
        backend = self._cfg.get('backend', '')
        model = self._cfg.get('model', '')
        if backend == 'ollama':
            if unload_ollama_model(model):
                self._add_ai(f"✓ Ejected `{model}` — Ollama released its memory.")
            else:
                self._add_ai("⚠ Could not eject the model — is Ollama still running?")
            return

        if backend != 'mlx':
            self._add_ai("ℹ Nothing to eject — a remote API holds no local memory.")
            return

        if shutdown_launched_servers():
            self._add_ai("✓ Ejected — the MLX server this app started was stopped.")
            self._set_disconnected_status()
            return

        host = self._cfg.get('mlx_host', MLX_BASE)
        pids = pids_listening_on(port_of(host))
        if not pids:
            self._add_ai("ℹ No MLX server found on " + host)
            return
        answer = QMessageBox.question(
            self, "Eject model",
            f"An MLX server this app did not start is running on {host} "
            f"(pid {', '.join(str(p) for p in pids)}).\n\n"
            "Stop it and free its memory?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        terminate_pids(pids)
        self._add_ai("✓ Ejected — the MLX server was stopped and its memory freed.")
        self._set_disconnected_status()

    def _set_disconnected_status(self):
        """Reset the header indicator after a model has been unloaded."""
        try:
            self._set_dot('error_dot')
            self._status.setText("Not connected")
            self._autoconfigured = False
            self._cfg['model'] = ''
        except Exception:
            _itk_log.exception("Handled exception in _set_disconnected_status")

    def shutdown(self, release=False):
        """Stop background work, and optionally free the model's memory.

        Args:
            release (bool): Also unload the models used and stop servers the
                app started. The application does this when it quits.
        """
        if self._worker is not None or self._code_worker is not None:
            try:
                self._do_stop()
            except Exception:
                _itk_log.exception("Handled exception stopping the request")
        for name in ('_probe', '_worker', '_code_worker'):
            thread = getattr(self, name, None)
            if thread is None:
                continue
            setattr(self, name, None)
            retire_thread(thread)
        if release:
            from results.ai.servers import release_models
            release_models()

    def closeEvent(self, event):
        """Stop any running request when the window closes; the model stays loaded until the app quits."""
        try:
            self.shutdown(release=False)
        except Exception:
            _itk_log.exception("Handled exception in closeEvent")
        super().closeEvent(event)

    def _set_connected_status(self, label):
        """Turn the header indicator green and show the active backend label.

        Args:
            label (str): Human-readable backend description, e.g. ``Ollama · x``.
        """
        try:
            self._set_dot('success_dot')
            self._status.setText(label)
        except Exception:
            _itk_log.exception("Handled exception in _set_connected_status")

    def _ensure_backend_ready(self):
        """Detect a local server on demand when nothing is configured yet.

        Called before sending so a server the user started after opening the
        assistant is picked up instead of bouncing them into settings.

        Returns:
            bool: True when a usable backend is configured.
        """
        backend = self._cfg.get('backend', '')
        if backend == 'mlx':
            return True
        if backend == 'custom' and self._cfg.get('custom_base_url'):
            return True
        if backend == 'ollama' and self._cfg.get('model'):
            return True

        models, _, _ = fetch_ollama_models(timeout=3)
        if models:
            self._cfg['backend'] = 'ollama'
            self._cfg['model'] = models[0]
            self._autoconfigured = True
            self._set_connected_status(f"Ollama: {models[0]}")
            self._add_ai(f"✓ Connected to Ollama · `{models[0]}`")
            self._update_sug(self.current_data)
            return True

        host = self._cfg.get('mlx_host', MLX_BASE)
        ids, reachable, _ = fetch_openai_models(host, timeout=3)
        if reachable:
            self._cfg['backend'] = 'mlx'
            self._cfg['model'] = ids[0] if ids else ''
            self._autoconfigured = True
            label = ids[0].split('/')[-1] if ids else 'loaded model'
            self._set_connected_status(f"MLX: {label}")
            self._add_ai(f"✓ Connected to MLX · `{label}`")
            self._update_sug(self.current_data)
            return True
        return False
