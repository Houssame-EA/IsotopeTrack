# `benchmark.py`

Score a model on questions with known answers.

The assistant can only be improved if "better" is measured. This module
generates a synthetic dataset whose truth is known (see
:mod:`results.ai.synthetic`), asks a model a fixed set of questions through
the same pipeline the chat window uses (code, sandbox, correction, grounded
takeaway) and checks every answer automatically.

Run it from the repository root against a local model::

    python -m results.ai.benchmark --backend ollama --model qwen2.5-coder:14b --num-ctx 16384
    python -m results.ai.benchmark --backend mlx --host http://127.0.0.1:8080
    python -m results.ai.benchmark --reference

``--reference`` answers with the built-in reference code instead of a model,
which checks the benchmark itself. Results print as a table and can be
saved as JSON with ``--out`` to compare models or prompt changes over time.

---

## Classes

### `Question`

One benchmark question.

Attributes:
    qid (str): Short identifier.
    text (str): The question as a user would ask it.
    kind (str): ``number``, ``text`` or ``figure``.
    expected: Number, regular expression or figure requirement.
    tolerance (float): Relative tolerance for numbers.
    reference (str): Code that answers it correctly, for ``--reference``.
    reject (str): Regular expression that must not match the answer.
    first_of (list): When set, the expected name must be the first of
        these that the answer mentions.
    reference_answer (str): The takeaway the reference model gives.

### `Outcome`

How one question went.

Attributes:
    qid (str): Question id.
    passed (bool): Whether the answer was right.
    attempts (int): Code runs needed.
    seconds (float): Wall time.
    error (str): Last sandbox or backend error.
    detail (str): Why it passed or failed.
    answer (str): The final answer text.

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_has` | `(p, el)` | Whether a particle dictionary holds element *el*. |
| `_truth_values` | `(dc, truth)` | Reference answers computed straight from the particle dictionaries. |
| `build_questions` | `(dc, truth)` | The question set for a synthetic dataset. |
| `complete` | `(cfg, messages, system, timeout=600)` | One non-streaming chat completion. |
| `reference_model` | `(question)` | A stand-in model that answers with the question's reference code. |
| `_check_figure` | `(req, results)` | Whether any figure meets the requirement. |
| `score` | `(question, results, answer)` | Decide whether an answer is right. |
| `ask` | `(question, ds, model, num_ctx=8192, max_fixes=2)` | Put one question through the chat pipeline. |
| `run` | `(model_factory, seed=11, num_ctx=8192, only=None, verbose=True)` | Run the whole question set. |
| `main` | `(argv=None)` | Command-line entry point. |
