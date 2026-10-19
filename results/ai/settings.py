"""Settings dialogs: which model to use, and how the chat looks."""
import logging
import subprocess
import time

import requests
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSlider, QSpinBox,
    QVBoxLayout,
)

from results.ai.memory import (
    fit, fmt_gb, folder_is_quantized, folder_weight_bytes, memory_line, mlx_model_folder, recommend,
    system_memory,
)
from results.ai.servers import (
    MLX_BASE, OLLAMA_TAGS, add_mlx_model_dir, discover_local_models, fetch_ollama_details,
    fetch_ollama_model_context, fetch_ollama_models, fetch_openai_models, install_server_shutdown_hooks,
    mlx_server_command, pids_listening_on, port_of, register_launched_server, shutdown_launched_servers,
    terminate_pids,
)

IDLE_CHOICES = [("Never", 0), ("5 minutes", 5), ("10 minutes", 10), ("15 minutes", 15),
                ("30 minutes", 30), ("1 hour", 60)]
RECOMMENDED_MARK = "★ Recommended for this computer"
from results.ai.theme import UI_PREFS, style_combo_popup, style_model_list

_itk_log = logging.getLogger("IsotopeTrack.results.ai.settings")


class BackendDialog(QDialog):
    """Choose the model backend, model, context window and answer checks."""
    def __init__(self, current_cfg, parent=None):
        """Build the dialog.

        Args:
            current_cfg (dict): Current settings.
            parent (QWidget): Owner.
        """
        super().__init__(parent)
        self.setWindowTitle("AI Backend Settings"); self.setMinimumWidth(520)
        self._cfg = dict(current_cfg)
        self._ctx = None
        self._ctx_note = None
        self._model = None
        self._mlx_model_combo = None
        self._sizes = {}
        self._mem_total, self._mem_avail = system_memory()
        lo = QVBoxLayout(self); lo.setSpacing(12)

        hl = QHBoxLayout(); hl.addWidget(QLabel("Backend:"))
        self._backend = style_combo_popup(QComboBox())
        self._backend.addItems(["Ollama (local)", "MLX (local)", "Custom API"])
        if current_cfg.get('backend') == 'mlx': self._backend.setCurrentIndex(1)
        elif current_cfg.get('backend') == 'custom': self._backend.setCurrentIndex(2)
        self._backend.currentIndexChanged.connect(self._on_backend)
        hl.addWidget(self._backend, stretch=1); lo.addLayout(hl)
        self._mem_note = QLabel(memory_line(self._mem_total, self._mem_avail))
        self._mem_note.setObjectName('fbStatus')
        self._mem_note.setToolTip(
            "Models marked ★ leave about half of the memory for your other work.\n"
            "The sizes are what a model needs while answering: its weights plus working memory.")
        lo.addWidget(self._mem_note)

        self._ollama_frame = QFrame()
        of = QVBoxLayout(self._ollama_frame); of.setContentsMargins(0,0,0,0); of.setSpacing(8)
        mh = QHBoxLayout()
        mh.addWidget(QLabel("Installed models — click one to select:"))
        mh.addStretch()
        rb = QPushButton("↻"); rb.setFixedWidth(32); rb.setToolTip("Refresh model list")
        rb.clicked.connect(self._fetch_ollama_models); mh.addWidget(rb)
        of.addLayout(mh)
        self._model = style_model_list(QListWidget())
        self._model.itemDoubleClicked.connect(lambda _: self.accept())
        self._model.currentItemChanged.connect(lambda *_: self._apply_model_context())
        self._model.currentItemChanged.connect(lambda *_: self._update_fit())
        of.addWidget(self._model)
        cur = current_cfg.get('model', '')
        if cur:
            item = QListWidgetItem(cur)
            item.setData(Qt.UserRole, cur)
            self._model.addItem(item)
            self._model.setCurrentRow(0)
        self._ollama_status = QLabel(""); of.addWidget(self._ollama_status)
        lo.addWidget(self._ollama_frame)

        self._mlx_frame = QFrame()
        mf = QVBoxLayout(self._mlx_frame); mf.setContentsMargins(0,0,0,0); mf.setSpacing(8)
        info = QLabel("Models already downloaded on this machine are listed below. "
                      "Pick one and press Start server if it is not running yet.")
        info.setWordWrap(True); mf.addWidget(info)
        mmh = QHBoxLayout()
        mmh.addWidget(QLabel("Local models — click one to select:"))
        mmh.addStretch()
        mrb = QPushButton("↻"); mrb.setFixedWidth(32)
        mrb.setToolTip("Rescan the local model cache")
        mrb.clicked.connect(self._scan_mlx_models); mmh.addWidget(mrb)
        afb = QPushButton("Add folder…")
        afb.setToolTip("Add a folder holding MLX models, e.g. converted or fine-tuned ones")
        afb.clicked.connect(self._add_model_folder); mmh.addWidget(afb)
        mf.addLayout(mmh)
        self._mlx_model_combo = style_model_list(QListWidget())
        self._mlx_model_combo.currentItemChanged.connect(lambda *_: self._update_fit())
        mf.addWidget(self._mlx_model_combo)
        ph = QHBoxLayout(); ph.addWidget(QLabel("Host:"))
        self._mlx_host = QLineEdit()
        self._mlx_host.setText(current_cfg.get('mlx_host', MLX_BASE))
        ph.addWidget(self._mlx_host, stretch=1); mf.addLayout(ph)
        bh = QHBoxLayout()
        self._mlx_start_btn = QPushButton("Start server")
        self._mlx_start_btn.clicked.connect(self._start_mlx_server)
        bh.addWidget(self._mlx_start_btn)
        mtb = QPushButton("Test connection"); mtb.clicked.connect(self._test_mlx)
        bh.addWidget(mtb)
        self._mlx_stop_btn = QPushButton("Stop server")
        self._mlx_stop_btn.setToolTip("Unload the model and free its memory")
        self._mlx_stop_btn.clicked.connect(self._stop_mlx_server)
        bh.addWidget(self._mlx_stop_btn)
        mf.addLayout(bh)
        self._mlx_status = QLabel(""); self._mlx_status.setWordWrap(True)
        mf.addWidget(self._mlx_status)
        self._mlx_model = current_cfg.get('model', '') if current_cfg.get('backend') == 'mlx' else ''
        self._mlx_proc = None
        self._mlx_wait_timer = None
        lo.addWidget(self._mlx_frame)

        self._custom_frame = QFrame()
        xf = QVBoxLayout(self._custom_frame); xf.setContentsMargins(0,0,0,0); xf.setSpacing(8)
        xf.addWidget(QLabel("OpenAI-compatible endpoint (Groq, OpenRouter, LM Studio, …)"))
        ph = QHBoxLayout(); ph.addWidget(QLabel("Base URL:"))
        self._custom_url = QLineEdit()
        self._custom_url.setText(current_cfg.get('custom_base_url','https://api.groq.com/openai/v1'))
        self._custom_url.setPlaceholderText("https://api.groq.com/openai/v1")
        ph.addWidget(self._custom_url, stretch=1); xf.addLayout(ph)
        kh = QHBoxLayout(); kh.addWidget(QLabel("API Key:"))
        self._custom_key = QLineEdit()
        self._custom_key.setEchoMode(QLineEdit.Password)
        self._custom_key.setText(current_cfg.get('custom_api_key',''))
        self._custom_key.setPlaceholderText("sk-...")
        kh.addWidget(self._custom_key, stretch=1); xf.addLayout(kh)
        mh2 = QHBoxLayout(); mh2.addWidget(QLabel("Model:"))
        self._custom_model = QLineEdit()
        self._custom_model.setText(current_cfg.get('custom_model',''))
        self._custom_model.setPlaceholderText("e.g. llama-3.3-70b-versatile")
        mh2.addWidget(self._custom_model, stretch=1); xf.addLayout(mh2)
        xtb = QPushButton("Test connection"); xtb.clicked.connect(self._test_custom); xf.addWidget(xtb)
        self._custom_status = QLabel(""); xf.addWidget(self._custom_status)
        lo.addWidget(self._custom_frame)

        cl = QHBoxLayout(); cl.addWidget(QLabel("Context window (tokens):"))
        self._ctx = style_combo_popup(QComboBox())
        self._ctx.setEditable(True)
        self._ctx.addItems(['4096','8192','16384','32768','65536','131072'])
        self._ctx.setCurrentText(str(current_cfg.get('num_ctx', 8192)))
        self._ctx.setToolTip(
            "Detected from the selected model when the server reports it. "
            "Larger windows use more memory.")
        self._ctx.setMinimumWidth(120)
        cl.addWidget(self._ctx)
        cl.addStretch(); lo.addLayout(cl)
        self._ctx_note = QLabel("")
        self._ctx_note.setWordWrap(True)
        self._ctx_note.setObjectName('fbStatus')
        lo.addWidget(self._ctx_note)
        self._fit_note = QLabel("")
        self._fit_note.setWordWrap(True)
        lo.addWidget(self._fit_note)

        il = QHBoxLayout()
        il.addWidget(QLabel("Free the model's memory after:"))
        self._idle = style_combo_popup(QComboBox())
        for text, minutes in IDLE_CHOICES:
            self._idle.addItem(text, minutes)
        idle_now = int(current_cfg.get('idle_unload_min', 10))
        self._idle.setCurrentIndex(max(0, [m for _, m in IDLE_CHOICES].index(idle_now)
                                       if idle_now in [m for _, m in IDLE_CHOICES] else 2))
        self._idle.setToolTip(
            "Unload the model when no question was asked for this long, so its memory\n"
            "goes back to your other work. It loads again on your next question\n"
            "(a few seconds to a minute, depending on the model).")
        il.addWidget(self._idle)
        il.addWidget(QLabel("without questions"))
        il.addStretch(); lo.addLayout(il)
        self._close_chk = QCheckBox("Also free it when the AI window closes")
        self._close_chk.setChecked(bool(current_cfg.get('unload_on_close', True)))
        lo.addWidget(self._close_chk)

        el = QHBoxLayout()
        el.addWidget(QLabel("Exploration depth (turns):"))
        self._explore_turns = style_combo_popup(QComboBox())
        self._explore_turns.addItems(['5','10','15','20','30'])
        self._explore_turns.setMinimumWidth(90)
        self._explore_turns.setToolTip(
            "How many query→result cycles the model runs when you click Explore.\n"
            "More turns = deeper analysis but slower.")
        self._explore_turns.setCurrentText(str(current_cfg.get('explore_max_turns', 10)))
        el.addWidget(self._explore_turns); el.addStretch(); lo.addLayout(el)

        self._interpret_chk = QCheckBox("Explain results after the code runs")
        self._interpret_chk.setToolTip(
            "After the code runs, the model is shown the exact results and writes the takeaway.\n"
            "Costs a second, short request per question.")
        self._interpret_chk.setChecked(bool(current_cfg.get('interpret_results', True)))
        lo.addWidget(self._interpret_chk)
        self._verify_chk = QCheckBox("Flag figures in answers that the code did not produce")
        self._verify_chk.setChecked(bool(current_cfg.get('verify_numbers', True)))
        lo.addWidget(self._verify_chk)
        self._figfix_chk = QCheckBox("Ask the model to fix empty or unlabelled figures")
        self._figfix_chk.setChecked(bool(current_cfg.get('fix_figures', True)))
        lo.addWidget(self._figfix_chk)
        self._think_chk = QCheckBox("Thinking mode (slower)")
        self._think_chk.setToolTip(
            "Lets models that can reason (for example Qwen) think before they answer.\n"
            "It can help on hard questions, but every answer takes much longer,\n"
            "often several times longer. Leave it off for everyday use.\n"
            "Ollama and MLX only; models without thinking ignore it.")
        self._think_chk.setChecked(bool(current_cfg.get('thinking', False)))
        lo.addWidget(self._think_chk)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._accept_if_fits); btns.rejected.connect(self.reject)
        lo.addWidget(btns)

        self._on_backend(self._backend.currentIndex())
        from results.figure_builder.ui import look
        look.style(self)
        QTimer.singleShot(80, self._fetch_ollama_models)
        QTimer.singleShot(120, self._scan_mlx_models)
        QTimer.singleShot(160, self._apply_model_context)

    def _on_backend(self, idx):
        """Show the settings of the selected backend.

        Args:
            idx (int): 0 Ollama, 1 MLX, 2 custom API.
        """
        self._ollama_frame.setVisible(idx == 0)
        self._mlx_frame.setVisible(idx == 1)
        self._custom_frame.setVisible(idx == 2)
        self._update_fit()
        if idx == 0:
            QTimer.singleShot(0, self._fetch_ollama_models)
        elif idx == 1:
            QTimer.singleShot(0, self._scan_mlx_models)

    def _fetch_ollama_models(self):
        """Refresh the model combo from the running Ollama server."""
        if self._backend.currentIndex() != 0: return
        self._ollama_status.setText("Fetching installed models…")
        QApplication.processEvents()
        try:
            models, reachable, detail = fetch_ollama_models(timeout=6)
            if models:
                cur = self._selected_ollama_model()
                details = fetch_ollama_details(timeout=6)
                infos = [{'model': n, **details.get(n, {'bytes': 0, 'quantized': False})} for n in models]
                self._fill_list(self._model, [(n, n) for n in models], infos)
                self._model.setCurrentRow(models.index(cur) if cur in models else 0)
                self._ollama_status.setText(f"✓ {len(models)} model(s) installed — "
                                            f"selected: {self._selected_ollama_model()}")
            elif reachable:
                self._ollama_status.setText(
                    f"⚠ Ollama reachable but {detail or 'no models found'} — run: ollama pull <model>")
            else:
                _itk_log.info("Ollama not reachable at %s — server not running.", OLLAMA_TAGS)
                self._ollama_status.setText("✗ Cannot reach Ollama — run: ollama serve")
        except Exception:
            _itk_log.exception("Unexpected error fetching Ollama models")
            self._ollama_status.setText("✗ Cannot reach Ollama — run: ollama serve")

    def _test_mlx(self):
        """Check the MLX server and report the models it exposes."""
        host = self._mlx_host.text().strip().rstrip('/') or MLX_BASE
        self._mlx_status.setText("Testing…")
        QApplication.processEvents()
        try:
            models, reachable, detail = fetch_openai_models(host, timeout=6)
            if models:
                self._mlx_model = models[0]
                self._mlx_status.setText(f"✓ Connected  —  {', '.join(models[:3])}")
            elif reachable:
                self._mlx_status.setText(f"✓ Connected  —  {detail or 'no models listed'}")
            else:
                _itk_log.info("MLX not reachable at %s — server not running.", host)
                self._mlx_status.setText("✗ Cannot reach MLX — start: mlx_lm.server --port 8080")
        except Exception as e:
            _itk_log.exception("Unexpected error testing MLX")
            self._mlx_status.setText(f"✗ {e}")

    def _scan_mlx_models(self):
        """Fill the MLX model list from the running server and the local cache."""
        if self._mlx_model_combo is None:
            return
        host = self._mlx_host.text().strip().rstrip('/') or MLX_BASE
        current = self._selected_mlx_model() or self._mlx_model
        entries = [e for e in discover_local_models(host) if e['backend'] == 'mlx']
        infos = []
        for entry in entries:
            folder = mlx_model_folder(entry['model'])
            infos.append({'model': entry['model'], 'bytes': folder_weight_bytes(folder) if folder else 0,
                          'quantized': folder_is_quantized(folder) if folder else False})
        self._fill_list(self._mlx_model_combo, [(e['label'], e['model']) for e in entries], infos)
        if entries:
            ids = [e['model'] for e in entries]
            self._mlx_model_combo.setCurrentRow(
                ids.index(current) if current in ids else 0)
        running = [e for e in entries if e['ready']]
        if running:
            self._mlx_model = running[0]['model']
            self._mlx_status.setText(f"✓ Server running — {running[0]['model']}")
        elif entries:
            self._mlx_status.setText(
                f"Found {len(entries)} cached model(s) — press Start server to load one")
        else:
            self._mlx_status.setText(
                "No local models found — download one, e.g. "
                "huggingface-cli download mlx-community/<model>")

    def _fill_list(self, widget, rows, infos):
        """Fill a model list, adding each model's memory need and the recommended mark.

        Args:
            widget (QListWidget): The list.
            rows (list): ``(label, model id)`` pairs.
            infos (list): Dicts with ``model``, ``bytes`` and ``quantized``.
        """
        best = recommend(infos, self._mem_total)
        widget.clear()
        for (label, model), info in zip(rows, infos):
            self._sizes[model] = info.get('bytes') or 0
            text = label
            if info.get('bytes'):
                from results.ai.memory import needed_bytes
                text += f"   ·   needs ~{fmt_gb(needed_bytes(info['bytes']))}"
            if model == best:
                text += f"   {RECOMMENDED_MARK}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, model)
            if model == best:
                font = item.font(); font.setBold(True); item.setFont(font)
            widget.addItem(item)

    def _current_model_for_fit(self):
        """The model the fit note describes: the one selected for the active backend."""
        idx = self._backend.currentIndex()
        if idx == 0:
            return self._selected_ollama_model()
        if idx == 1:
            return self._selected_mlx_model()
        return ''

    def _model_fit(self):
        """Whether the selected model fits this computer now."""
        self._mem_total, self._mem_avail = system_memory()
        model = self._current_model_for_fit()
        return fit(self._sizes.get(model, 0), self._mem_total, self._mem_avail)

    def _update_fit(self):
        """Show whether the selected model fits, in colour when it does not."""
        if getattr(self, '_fit_note', None) is None:
            return
        verdict = self._model_fit()
        self._mem_note.setText(memory_line(self._mem_total, self._mem_avail))
        self._fit_note.setText(verdict['text'])
        colour = {'too_big': '#D55E00', 'tight': '#E69F00'}.get(verdict['level'])
        self._fit_note.setStyleSheet(f"color:{colour}; font-weight:600;" if colour else "")
        self._fit_note.setObjectName('' if colour else 'fbStatus')

    def _confirm_fit(self):
        """Ask before using a model that does not fit now.

        Returns:
            bool: True to go ahead.
        """
        verdict = self._model_fit()
        if verdict['level'] not in ('too_big', 'tight'):
            return True
        answer = QMessageBox.question(
            self, "Model may not fit", verdict['text'] + "\n\nUse it anyway?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return answer == QMessageBox.Yes

    def _accept_if_fits(self):
        """Close with OK, after a warning when the model will not fit."""
        if self._confirm_fit():
            self.accept()

    def _add_model_folder(self):
        """Let the user add a folder of MLX models and list them."""
        path = QFileDialog.getExistingDirectory(self, "Folder with MLX models")
        if not path:
            return
        add_mlx_model_dir(path)
        self._scan_mlx_models()

    def _selected_mlx_model(self):
        """Return the model id chosen in the MLX list.

        Rows show friendly labels such as ``MLX (running) · Qwen3-4bit`` while
        the real repo id lives in the item data, so the label is never sent to
        the server as an id.

        Returns:
            str: Repo id or local path.
        """
        if self._mlx_model_combo is None:
            return ''
        item = self._mlx_model_combo.currentItem()
        if item is None:
            return ''
        return str(item.data(Qt.UserRole) or '')

    def _start_mlx_server(self):
        """Launch mlx_lm.server for the selected model and wait for it to answer."""
        model = self._selected_mlx_model()
        if not model:
            self._mlx_status.setText("✗ Pick a model first")
            return
        if not self._confirm_fit():
            return
        host = self._mlx_host.text().strip().rstrip('/') or MLX_BASE
        if fetch_openai_models(host, timeout=2)[1]:
            self._mlx_status.setText("✓ A server is already running on this host")
            self._scan_mlx_models()
            return
        try:
            port = int(host.rsplit(':', 1)[-1].split('/')[0])
        except ValueError:
            port = 8080
        cmd = mlx_server_command(model, port)
        if not cmd:
            self._mlx_status.setText(
                "✗ mlx_lm is not installed for this Python — run: pip install mlx-lm")
            return
        try:
            self._mlx_proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            register_launched_server(self._mlx_proc)
            install_server_shutdown_hooks()
        except Exception as e:
            _itk_log.exception("Failed to launch mlx_lm.server")
            self._mlx_status.setText(f"✗ Could not start server: {e}")
            return
        self._mlx_start_btn.setEnabled(False)
        self._mlx_status.setText(f"Starting server for {model} — loading weights…")
        self._mlx_wait_deadline = time.monotonic() + 180
        self._mlx_wait_timer = QTimer(self)
        self._mlx_wait_timer.timeout.connect(lambda: self._poll_mlx_server(model, host))
        self._mlx_wait_timer.start(2000)

    def _stop_mlx_server(self):
        """Stop the MLX server and free the memory its weights occupy."""
        if shutdown_launched_servers():
            self._mlx_status.setText("✓ Server stopped — model unloaded")
            QTimer.singleShot(600, self._scan_mlx_models)
            return
        host = self._mlx_host.text().strip().rstrip('/') or MLX_BASE
        pids = pids_listening_on(port_of(host))
        if not pids:
            self._mlx_status.setText("No server is running on " + host)
            return
        answer = QMessageBox.question(
            self, "Stop server",
            f"A server this app did not start is running on {host} "
            f"(pid {', '.join(str(p) for p in pids)}).\n\nStop it?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        terminate_pids(pids)
        self._mlx_status.setText("✓ Server stopped — memory freed")
        QTimer.singleShot(600, self._scan_mlx_models)

    def _poll_mlx_server(self, model, host):
        """Check whether the launched MLX server has finished loading."""
        ids, reachable, _ = fetch_openai_models(host, timeout=2)
        if reachable:
            self._mlx_wait_timer.stop()
            self._mlx_start_btn.setEnabled(True)
            self._mlx_model = ids[0] if ids else model
            self._mlx_status.setText(f"✓ Server ready — {self._mlx_model}")
            self._scan_mlx_models()
            return
        if time.monotonic() > self._mlx_wait_deadline:
            self._mlx_wait_timer.stop()
            self._mlx_start_btn.setEnabled(True)
            self._mlx_status.setText(
                "✗ Server did not answer in time — large models can take several "
                "minutes to load, press Test connection again later")

    def _ctx_value(self):
        """Return the context window as an integer, falling back to 8192.

        Returns:
            int: Token budget for the model context.
        """
        try:
            return max(512, int(str(self._ctx.currentText()).strip()))
        except (TypeError, ValueError):
            return 8192

    def _apply_model_context(self):
        """Set the context window to what the selected Ollama model supports.

        Runs on selection changes, including the one emitted while the dialog is
        still being built, so it returns early until the widgets it needs exist.
        """
        if self._ctx is None or self._ctx_note is None:
            return
        if self._backend.currentIndex() != 0:
            return
        model = self._selected_ollama_model()
        if not model:
            return
        length = fetch_ollama_model_context(model, timeout=3)
        if not length:
            self._ctx_note.setText("")
            return
        if self._ctx.findText(str(length)) < 0:
            self._ctx.addItem(str(length))
        self._ctx.setCurrentText(str(length))
        self._ctx_note.setText(f"Context window detected for {model}.")

    def _selected_ollama_model(self):
        """Return the Ollama model name highlighted in the list.

        Returns:
            str: Model name, or an empty string when nothing is selected.
        """
        if self._model is None:
            return ''
        item = self._model.currentItem()
        if item is None:
            return ''
        return str(item.data(Qt.UserRole) or item.text())

    def _resolve_mlx_model(self):
        """Ask the MLX server which model it has loaded.

        mlx_lm.server answers /v1/chat/completions with HTTP 404 when the
        request carries no model id, so the id has to be resolved before the
        first chat request.

        Returns:
            str: Model id, or an empty string when the server cannot be reached.
        """
        host = self._mlx_host.text().strip().rstrip('/') or MLX_BASE
        try:
            models, _, _ = fetch_openai_models(host, timeout=4)
        except Exception:
            _itk_log.exception("Handled exception in _resolve_mlx_model")
            return ''
        return models[0] if models else ''

    def _test_custom(self):
        """Check the custom OpenAI-compatible endpoint and prefill a model."""
        base = self._custom_url.text().strip().rstrip('/')
        key  = self._custom_key.text().strip()
        self._custom_status.setText("Testing…")
        QApplication.processEvents()
        try:
            hdrs = {'Content-Type':'application/json'}
            if key: hdrs['Authorization'] = f'Bearer {key}'
            r = requests.get(f"{base}/models", headers=hdrs, timeout=6)
            if r.status_code == 200:
                try:
                    models = [m.get('id','') for m in r.json().get('data',[])]
                    self._custom_status.setText(f"✓ Connected — {len(models)} models")
                    if models and not self._custom_model.text():
                        self._custom_model.setText(models[0])
                except Exception:
                    _itk_log.exception("Handled exception in _test_custom")
                    self._custom_status.setText("✓ Connected")
            elif r.status_code in (401, 403):
                self._custom_status.setText("✗ Auth failed — check API key")
            else:
                self._custom_status.setText(f"✗ HTTP {r.status_code}")
        except requests.exceptions.ConnectionError:
            _itk_log.exception("Handled exception in _test_custom")
            self._custom_status.setText("✗ Cannot connect — check URL")
        except Exception as e:
            _itk_log.exception("Handled exception in _test_custom")
            self._custom_status.setText(f"✗ {str(e)[:60]}")

    def get_config(self):
        """Collect the chosen settings.

        Returns:
            dict: Backend configuration for the chat window.
        """
        idx = self._backend.currentIndex()
        base = {
            'temperature': 0.2,
            'num_ctx': self._ctx_value(),
            'explore_max_turns': int(self._explore_turns.currentText()),
            'interpret_results': self._interpret_chk.isChecked(),
            'verify_numbers': self._verify_chk.isChecked(),
            'fix_figures': self._figfix_chk.isChecked(),
            'thinking': self._think_chk.isChecked(),
            'idle_unload_min': int(self._idle.currentData() or 0),
            'unload_on_close': self._close_chk.isChecked(),
            'mlx_host': self._mlx_host.text().strip(),
            'custom_base_url': self._custom_url.text().strip() if idx == 2 else '',
            'custom_api_key':  self._custom_key.text().strip() if idx == 2 else '',
            'custom_model':    self._custom_model.text().strip() if idx == 2 else '',
        }
        if idx == 0:
            base.update({'backend':'ollama','model':self._selected_ollama_model()})
        elif idx == 1:
            chosen = self._selected_mlx_model()
            base.update({'backend':'mlx',
                         'model': chosen or self._mlx_model or self._resolve_mlx_model()})
        else:
            base.update({'backend':'custom','model':self._custom_model.text().strip()})
        return base


class CustomizeDialog(QDialog):
    """Font size, chart quality, and display options."""

    applied = Signal() 

    def __init__(self, parent=None):
        """Build the dialog.

        Args:
            parent (QWidget): Owner.
        """
        super().__init__(parent)
        self.setWindowTitle("Customize Appearance")
        self.setMinimumWidth(380); self.setMaximumWidth(440)
        lo = QVBoxLayout(self); lo.setSpacing(14)

        from results.figure_builder.ui import look
        look.style(self)

        fs_row = QHBoxLayout()
        fs_row.addWidget(QLabel("Font size:"))
        self._fs_lbl = QLabel(f"{UI_PREFS['font_size']} px")
        self._fs_lbl.setMinimumWidth(36)
        self._fs_slider = QSlider(Qt.Horizontal)
        self._fs_slider.setRange(11, 20); self._fs_slider.setValue(UI_PREFS['font_size'])
        self._fs_slider.setTickInterval(1); self._fs_slider.setTickPosition(QSlider.TicksBelow)
        self._fs_slider.valueChanged.connect(
            lambda v: self._fs_lbl.setText(f"{v} px"))
        fs_row.addWidget(self._fs_slider, stretch=1)
        fs_row.addWidget(self._fs_lbl)
        lo.addLayout(fs_row)

        bw_row = QHBoxLayout()
        bw_row.addWidget(QLabel("Bubble max width:"))
        self._bw_spin = QSpinBox()
        self._bw_spin.setRange(400, 1000); self._bw_spin.setSingleStep(20)
        self._bw_spin.setValue(UI_PREFS['bubble_max_width'])
        self._bw_spin.setSuffix(" px")
        bw_row.addWidget(self._bw_spin); bw_row.addStretch()
        lo.addLayout(bw_row)

        dpi_row = QHBoxLayout()
        dpi_row.addWidget(QLabel("Chart quality (DPI):"))
        self._dpi_combo = QComboBox()
        self._dpi_combo.addItems(["72 — draft", "100 — standard", "150 — high", "200 — ultra"])
        dpi_map = {72: 0, 100: 1, 150: 2, 200: 3}
        self._dpi_combo.setCurrentIndex(dpi_map.get(UI_PREFS['chart_dpi'], 1))
        dpi_row.addWidget(self._dpi_combo); dpi_row.addStretch()
        lo.addLayout(dpi_row)

        self._ts_chk = QCheckBox("Show message timestamps")
        self._ts_chk.setChecked(UI_PREFS['show_timestamps'])
        lo.addWidget(self._ts_chk)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        lo.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        reset_btn = QPushButton("Reset defaults")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)
        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("fbPrimary")
        apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(apply_btn)
        lo.addLayout(btn_row)

    def _dpi_value(self):
        """Return the chosen chart resolution in dpi."""
        return [72, 100, 150, 200][self._dpi_combo.currentIndex()]

    def _reset(self):
        """Put every control back to its default."""
        self._fs_slider.setValue(14)
        self._bw_spin.setValue(740)
        self._dpi_combo.setCurrentIndex(1)
        self._ts_chk.setChecked(False)

    def _apply(self):
        """Store the choices and close."""
        UI_PREFS['font_size']       = self._fs_slider.value()
        UI_PREFS['bubble_max_width']= self._bw_spin.value()
        UI_PREFS['chart_dpi']       = self._dpi_value()
        UI_PREFS['show_timestamps'] = self._ts_chk.isChecked()
        self.applied.emit()
        self.accept()

