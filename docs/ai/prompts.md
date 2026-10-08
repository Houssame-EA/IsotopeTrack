# `prompts.py`

What the model is told, and how it all fits in its context window.

The system prompt has three parts: how to answer (write code, then explain
from the results), what the sandbox offers (the particle table, the analysis
functions, free-form matplotlib figures), and a brief of the dataset,
including calibrated detection limits and known interferences.

Local models often run with an 8k-token window, so every prompt is
budgeted: the history gets what is left after the system prompt and a
reserve for the reply, the first message of an exploration (the question)
is never dropped, and small windows get a compact dataset brief.

---

## Constants

| Name | Value |
|------|-------|
| `CHARS_PER_TOKEN` | `3.5` |
| `COMPACT_BELOW` | `12000` |
| `_ROLE` | `"You are the data analyst inside IsotopeTrack, working on…` |
| `_HOW` | `'HOW TO ANSWER\n- For any question about the data: one sh…` |
| `_DATA` | `"THE SANDBOX\ndf: pandas DataFrame, one row per particle.…` |
| `_OUTPUT` | `"SHOWING RESULTS\nshow_table(dataframe_or_dict, title='..…` |
| `_FIGURES` | `"FIGURES — you draw them yourself with matplotlib, exactl…` |
| `_DOMAIN` | `'SPICP-TOF-MS\n- One event is one particle passing the pl…` |
| `_EXAMPLE` | `"EXAMPLE\nUser: is Ti bigger in some samples?\nComparing …` |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `estimate_tokens` | `(text)` | Rough token count of a text, about 3.5 characters per token. |
| `reply_reserve` | `(num_ctx)` | Tokens kept free for the model's answer. |
| `fit_messages` | `(messages, system_text, num_ctx, pinned=0)` | Keep the messages that fit beside the system prompt and the reply. |
| `_fmt` | `(v, digits=3)` | Short number for the brief. |
| `_interference_notes` | `(elements, limit=12)` | Masses with major or critical documented spectral interferences. |
| `dataset_brief` | `(ds, compact=False)` | Describe the dataset for the system prompt. |
| `_functions_block` | `(compact=False)` | The analysis function reference. |
| `build_system_prompt` | `(ds, num_ctx=8192, mode='chat', max_turns=10)` | Assemble the system prompt. |
| `exploration_rules` | `(max_turns)` | Instructions for the multi-turn exploration. |
| `first_exploration_message` | `(question)` | The pinned opening message of an exploration. |
| `turn_feedback` | `(digest, turn, max_turns, ledger_text, plan_text='')` | The message returned to the model after an exploration turn. |
| `summary_request` | `(ledger_text, question)` | Ask for the final exploration summary, written only from the findings. |
| `interpretation_request` | `(results_text)` | Ask for a short, grounded takeaway after code ran. |
| `correction_request` | `(error, digest='')` | Ask the model to fix code that failed. |
| `figure_fix_request` | `(warnings)` | Ask the model to fix a figure that drew but has problems. |
| `suggest_questions` | `(ds, limit=5)` | Starter questions built from what is actually in the data. |
