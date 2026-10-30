# `training.py`

Training data for fine-tuning the assistant's model on IsotopeTrack work.

The examples are made the way a good student learns from solved exercises.
Many new synthetic datasets are generated, each with its own sample names,
sizes, contamination burst and alloy sample, and the benchmark's question
templates are put to a strong teacher model through exactly the same loop as
the chat window. Only answers the benchmark verifies as correct are kept,
and inside them only the replies that did not fail: code that crashed or a
figure that had to be redrawn is never a training target, while the fix
that followed is. A takeaway quoting a number the results do not contain is
dropped too.

The ``lakes`` dataset and the templates in :data:`HELDOUT_TEMPLATES` never
appear here, so the benchmark's test split still measures what the model
learned rather than what it memorised.

Run from the repository root::

    python -m results.ai.training generate --backend ollama --model <teacher> --datasets 12 --out ~/Desktop/ai_train
    python -m results.ai.training build --out ~/Desktop/ai_train
    python -m results.ai.lora_train --config ~/Desktop/ai_train/lora_config.yaml

``generate`` can be stopped and started again; finished questions are
skipped. ``build`` splits the examples into ``train.jsonl`` and
``valid.jsonl`` for ``mlx_lm.lora`` and writes a ready ``lora_config.yaml``.
Train with :mod:`results.ai.lora_train` rather than ``mlx_lm.lora`` itself:
for Qwen3.5-family models plain ``mlx_lm.lora`` needs hundreds of GB.

---

## Constants

| Name | Value |
|------|-------|
| `HELDOUT_TEMPLATES` | `frozenset({'count_above', 'p90_ce', 'ti_differ', 'fig_ecd…` |
| `FIX_PREFIXES` | `('[SANDBOX ERROR]', '[FIGURE CHECK]', NO_CODE_PREFIX, EMP…` |
| `TAKEAWAY_PREFIX` | `'Here are the EXACT results your code just produced:'` |
| `ELEMENT_WORDS` | `{'Ti': 'titanium', 'Fe': 'iron', 'Ce': 'cerium', 'La': 'l…` |
| `PARAPHRASE_SYSTEM` | `'You rewrite questions that scientists type into a data-a…` |
| `_SHOW_RE` | `re.compile('^[ \\t]*plt\\.(show\|tight_layout)\\(\\)[ \\t]…` |
| `_BACKEND_ERROR_RE` | `re.compile('HTTP\|Connection\|Timeout\|timed out\|Max retries…` |
| `LORA_CONFIG` | `'model: {model}\ntrain: true\ndata: {data}\nfine_tune_typ…` |

## Classes

### `Recorder`

Wraps a model and keeps every request it answered, exactly as sent.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, model)` | Wrap *model*, a ``(messages, system) -> reply`` callable. |
| `__call__` | `(self, messages, system)` | Answer and remember the request and the reply. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_letters` | `(n)` | Sample suffixes A, B, C, ... |
| `sample_names` | `(rng, n)` | Pick a naming style and return *n* sample names in it. |
| `random_spec` | `(seed)` | A random dataset specification with one clearly larger Ti sample. |
| `training_questions` | `(seed, categories=None)` | The dataset and the training questions for one seed. |
| `keep_calls` | `(calls)` | The replies worth learning from in one verified-correct conversation. |
| `_shown` | `(reply)` | A reply as the conversation keeps it: no reasoning, nothing after the last code block. |
| `_tidy` | `(reply)` | Drop what the app ignores and its rules forbid, so the model does not learn it. |
| `_protected` | `(text, samples)` | Words a paraphrase must keep: sample names, elements and numbers. |
| `paraphrase` | `(model_cfg, text, samples)` | Ask the teacher to reword a question, keeping it only when nothing was lost. |
| `_reworded` | `(question, model_cfg, samples)` | The question with its user-facing text paraphrased by the teacher. |
| `is_backend_error` | `(error)` | Whether an error came from reaching the teacher model rather than from its code. |
| `retrying` | `(model, attempts=3, wait_s=5.0)` | Wrap a model so a failed request is tried again after a short wait. |
| `_done_ids` | `(path)` | Question ids already handled in an earlier run; a request that never reached the teacher is asked again. |
| `generate` | `(model_factory, out_dir, n_datasets=10, start=0, categories=None, mode` | Put the training questions to a teacher and keep its verified-correct replies. |
| `drop_empty_retries` | `(messages)` | Remove empty replies and the request that asked for them again. |
| `build` | `(out_dir, model='mlx-community/Qwen3.5-9B-MLX-4bit', epochs=2, max_len` | Split the examples into training and validation files and write the LoRA config. |
| `main` | `(argv=None)` | Command-line entry point. |
