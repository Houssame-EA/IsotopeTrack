# `benchmark.py`

Score a model on questions with known answers.

The assistant can only be improved if "better" is measured. This module
generates synthetic datasets whose truth is known (see
:mod:`results.ai.synthetic`), asks a model a fixed set of questions through
the same pipeline the chat window uses (code, sandbox, correction, grounded
takeaway) and checks every answer automatically.

The question set is built from 36 templates (counts, statistics, yes/no
reasoning and figures) asked on three datasets with different samples,
sizes, a contamination burst and an alloy population planted in different
places. Datasets ``rivers`` and ``wastewater`` form the ``dev`` split;
``lakes`` is the ``test`` split and should never be used to make training
examples, so a model trained on the others is still measured on data it has
not seen.

Figures are checked on what was actually drawn: axis scales, number of
panels, series, points or bars, axis labels and titles where asked for,
reference lines, colour maps, and the drawing warnings the chat shows the
model (empty panels, missing axis labels, overlapping text).

On top of those, each dataset has:

- ``custom``: single requests for detailed figure customisation (a second
  y-axis, points above a threshold in another colour, a colour scale for a
  third quantity, error bars, axis range and grid, a fixed colour for one
  sample, an annotation with an arrow, marker shape and legend placement);
- ``table``: one table covering every element in every sample, checked
  value by value;
- ``edit``: conversations of three requests where each one changes the
  previous figure; every step must keep what was asked before and add the
  new change, which tests whether the model edits its own code instead of
  starting over;
- ``explore``: open and targeted explorations run through the same loop as
  the Explore button, scored on how many of the planted features the
  summary reports (the Ce:La ratio shift, the non-natural Pb isotope ratio,
  the Ag+Au alloy sample, the sample with larger Ti, the Fe burst for the
  iron question) and failed on a false discovery (Ti+Fe called a real
  association).

Every question goes through the same steps as the chat window: up to three
code corrections, one figure redraw when the drawing checks complain, and
the grounded takeaway, with the history kept the way the chat keeps it.

Run it from the repository root against a local model::

    python -m results.ai.benchmark --backend ollama --model qwen3.8:27b-mlx
    python -m results.ai.benchmark --backend mlx --host http://127.0.0.1:8080
    python -m results.ai.benchmark --reference

Thinking is off by default, as in the app; ``--think`` switches it on.

``--reference`` answers with the built-in reference code instead of a model,
which checks the benchmark itself. ``--split``, ``--dataset``, ``--category``
and ``--only`` select part of the set. Results print per question with a
summary per category and split, and can be saved as JSON with ``--out``.

---

## Constants

| Name | Value |
|------|-------|
| `ISOTOPES` | `{'Ti': '48Ti', 'Fe': '56Fe', 'Ce': '140Ce', 'La': '139La'…` |
| `QUALITY_WARNINGS` | `('is empty', 'overlap', 'has no x-axis label', 'has no y-…` |
| `MAX_FIX_ATTEMPTS` | `3` |
| `MAX_FIGURE_FIXES` | `1` |
| `EXEC_TIMEOUT_S` | `300` |
| `CATEGORIES` | `['count', 'stats', 'reasoning', 'figure', 'custom', 'tabl…` |
| `DATASETS` | `{'rivers': {'split': 'dev', 'seed': 11, 'builtin': True},…` |
| `ELEMENT_PATTERNS` | `{'Ti': '(?-i:\\b(48)?Ti\\b)\|titanium', 'Fe': '(?-i:\\b(56…` |
| `AFFIRMED_REAL` | `"(?:^\|[.!?:]\\s+)(?:(?!\\b(?:not\|no\|rather than\|unlikely\|…` |

## Classes

### `Question`

One benchmark question.

Attributes:
    qid (str): Identifier, ``dataset.template``.
    text (str): The question as a user would ask it.
    kind (str): ``number``, ``text`` or ``figure``.
    expected: Number, regular expression or figure requirement.
    tolerance (float): Relative tolerance for numbers.
    reference (str): Code that answers it correctly, for ``--reference``.
    reject (str): Regular expression that must not match the answer.
    first_of (dict): Name to regular expression; when set, ``expected``
        must be the first of these names the answer mentions.
    reference_answer (str): The takeaway the reference model gives.
    dataset (str): Dataset key.
    split (str): ``dev`` or ``test``.
    category (str): One of :data:`CATEGORIES`.
    steps (list): For ``conversation`` questions, one dict per request
        with ``text``, ``req`` (what the figure must show after that
        request, counting everything asked so far) and ``reference``.
    findings (dict): For ``explore`` questions, name to
        ``(patterns, unless)``: one sentence of the summary must match
        every pattern and not ``unless`` for the feature to count.
    forbidden (dict): Claims that fail an ``explore`` question, in the
        same form as ``findings``.
    need (int): Findings required to pass an ``explore`` question.
    max_turns (int): Exploration turn budget.

### `Outcome`

How one question went.

Attributes:
    qid (str): Question id.
    dataset (str): Dataset key.
    split (str): ``dev`` or ``test``.
    category (str): Question category.
    passed (bool): Whether the answer was right.
    attempts (int): Code runs needed.
    fixes (int): Corrections and figure redraws the model was asked for.
    seconds (float): Wall time.
    error (str): Last sandbox or backend error.
    detail (str): Why it passed or failed.
    answer (str): The final answer text.
    transcript (list): The whole conversation with the model, code
        included, so a failure can be read afterwards.

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `make_variant` | `(name)` | Generate one of the benchmark datasets. |
| `build_variant` | `(spec)` | Generate a dataset from a specification. |
| `truth_frame` | `(dc)` | A plain table of the particles, built without :mod:`results.ai.data`. |
| `_names` | `(names)` | Map names to escaped regular expressions for ``first_of``. |
| `_hist_ref` | `(sym, quantity, label)` | Reference code for one log-binned histogram per sample. |
| `build_questions` | `(name, dc, truth)` | The question set for one dataset. |
| `_add_custom` | `(add, S, n_s, s0, tf)` | Single requests for detailed figure customisation. |
| `_add_tables` | `(add, S, tf)` | Questions answered by one table over every element in every sample. |
| `_add_edits` | `(add, S, n_s, burst_sample, b0, b1, span, cela, tf)` | Three-request conversations that each change the previous figure. |
| `_name_pattern` | `(name, group=())` | A pattern for a sample name as people write it. |
| `_add_explore` | `(add, S, s0, largest_ti, burst_sample, b0, b1, truth)` | Open and targeted explorations scored on the planted features. |
| `_raise_for_status` | `(response)` | Raise on an HTTP error with the server's own message, which says what went wrong. |
| `complete` | `(cfg, messages, system, timeout=600)` | One non-streaming chat completion. |
| `reference_model` | `(question)` | A stand-in model that answers with the question's reference code. |
| `_panels` | `(fig)` | The data panels of a figure, without colour bars. |
| `_series` | `(ax)` | Number of plotted series on a panel, as the legend or artists show it. |
| `_points` | `(ax)` | Number of scatter markers on a panel. |
| `_ticklabels` | `(ax, axis='x')` | Tick label texts of one axis. |
| `_has_image` | `(ax)` | Whether a panel shows an image or a colour mesh. |
| `_drawn` | `(ax)` | Whether anything is drawn on a panel. |
| `_panel_ok` | `(ax, spec)` | Check one panel against a requirement. |
| `_rgba` | `(colors)` | Colours as an RGBA array, empty when they cannot be read. |
| `_is_color` | `(rgba, name)` | Whether an RGBA colour reads as the named colour. |
| `_point_colors` | `(ax)` | Every visible scatter point of a panel as ``x, y, r, g, b, a`` rows. |
| `_threshold_ok` | `(ax, th)` | Whether points beyond a threshold, and only those, have the asked colour. |
| `_constant` | `(values, target, rtol=0.03)` | Whether a line is flat at *target*. |
| `_mapped` | `(c)` | Whether a collection is coloured through a colour map. |
| `_has_errorbars` | `(ax)` | Whether a panel holds error bars. |
| `_series_has_color` | `(ax, label, name)` | Whether the series with this legend label is drawn in the named colour. |
| `_has_triangles` | `(ax)` | Whether the scatter markers are triangles. |
| `_legend_outside` | `(ax)` | Whether a legend sits to the right of the panel. |
| `_bars_sorted` | `(ax)` | Whether the bars run from the highest to the lowest. |
| `_has_twin` | `(panels)` | Whether two drawn panels share the same place, as ``twinx`` makes. |
| `_has_span` | `(ax, t0, t1)` | Whether a shaded band covers ``t0`` to ``t1`` on the x-axis. |
| `_figure_ok` | `(fig, req)` | Check one figure against a requirement. |
| `_check_figure` | `(req, results)` | Whether any figure meets the requirement without drawing problems. |
| `score` | `(question, results, answer)` | Decide whether an answer is right. |
| `_chat_turn` | `(messages, system, ds, model, num_ctx, out, results)` | One user request handled the way the chat window handles it. |
| `_sentence_hit` | `(sentences, patterns, unless='')` | Whether one sentence matches every pattern and not *unless*. |
| `_without_rejected_titles` | `(text)` | Drop the bold hypothesis titles listed under a "Not supported" heading. |
| `score_exploration` | `(question, text)` | Score an exploration summary against the planted features. |
| `_ask_conversation` | `(question, ds, model, num_ctx)` | Run a multi-request figure conversation and check every step. |
| `_ask_explore` | `(question, ds, model, num_ctx)` | Run an exploration the way the Explore button does and score its summary. |
| `ask` | `(question, ds, model, num_ctx=8192)` | Put one question through the chat pipeline. |
| `_summary` | `(outcomes)` | Print the totals per category and split. |
| `run` | `(model_factory, num_ctx=8192, only=None, split=None, datasets=None, ca` | Run the question set. |
| `main` | `(argv=None)` | Command-line entry point. |
