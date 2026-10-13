# `exploration.py`

State of an agentic exploration: the plan, the findings and the steps.

An exploration is a loop in which the model writes one query per turn and
sees its results. What it learns is kept here, outside the chat history,
so trimming old messages to fit the context window never loses a finding,
and the final summary is written from this record rather than from memory.

---

## Constants

| Name | Value |
|------|-------|
| `DONE_RE` | `re.compile('^\\s*\\**\\s*EXPLORATION\\s+DONE\\b', re.IGNO…` |
| `_PLAN_RE` | `re.compile('PLAN\\s*:\\s*(.*?)(?:```\|\\Z)', re.IGNORECASE…` |
| `_ITEM_RE` | `re.compile('^\\s*(?:\\d+[.)]\|[-*•])\\s+(.+?)\\s*$', re.MU…` |

## Classes

### `Finding`

One result the model recorded with ``record_finding``.

Attributes:
    claim (str): The finding in plain words.
    n (float): Particles or samples involved.
    p (float): p-value of the supporting test.
    effect (float): Effect size, e.g. a ratio of medians.
    evidence (str): Extra detail.
    turn (int): Exploration turn that produced it.

| Method | Signature | Description |
|--------|-----------|-------------|
| `supported` | `(self)` | Whether the finding is backed by a significant test, or untested. |
| `line` | `(self)` | One-line text form for prompts and summaries. |

### `FindingsLedger`

The findings of one exploration, de-duplicated and ranked.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self)` | Start empty. |
| `__len__` | `(self)` | Number of findings. |
| `add` | `(self, raw, turn)` | Record findings from one turn. |
| `ranked` | `(self)` | Findings ordered by strength: significant first, then by effect size. |
| `as_text` | `(self, limit=20)` | Numbered text form for prompts. |
| `numbers` | `(self)` | Every number the findings hold, for the fabrication check. |

### `ExplorationState`

Everything one exploration run keeps between turns.

Attributes:
    question (str): What the user asked.
    max_turns (int): Turn budget.
    turn (int): Turns run so far.
    plan (list): The model's hypotheses.
    ledger (FindingsLedger): Findings recorded so far.
    messages (list): The exploration's own chat history.
    numbers (list): Every number produced across turns.
    failures (int): Consecutive turns that ended in an error.

| Method | Signature | Description |
|--------|-----------|-------------|
| `plan_text` | `(self)` | The plan as a numbered list. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_num` | `(v)` | Return *v* as a finite float, or ``None``. |
| `parse_plan` | `(text)` | Pull the numbered hypotheses out of a ``PLAN:`` section. |
| `is_done` | `(text)` | Whether the model declared the exploration finished. |
