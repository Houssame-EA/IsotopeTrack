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
| `MAX_EXPLORE_FIXES` | `2` |
| `MAX_FAILED_TURNS` | `2` |
| `MAX_REPEATS` | `2` |
| `KEEP_FULL_TURNS` | `2` |
| `ELEMENT_NAMES` | `dict((pair.split(':') for pair in 'H:hydrogen He:helium L…` |
| `ELEMENT_NAME_VARIANTS` | `{'aluminum': 'Al', 'cesium': 'Cs', 'sulphur': 'S', 'wolfr…` |
| `WORD_SYMBOLS` | `frozenset({'I', 'In', 'As', 'At', 'Be', 'He', 'No', 'Am'})` |
| `TYPED_NUMBER_RE` | `re.compile('(?<![\\w.%])\\d+\\.\\d+\|(?<![\\w.%])\\d+(?:\\…` |
| `FOLD_RE` | `re.compile('[-+]?\\d[\\d.,]*(?:[eE][-+]?\\d+)?\\s*(?:x\|×\|…` |
| `PREMATURE_FINDING` | `'record_finding on line {line} types numbers by hand afte…` |
| `UNBACKED_FINDING` | `'record_finding quotes {numbers}, which no result you hav…` |
| `DONE_RE` | `re.compile('^\\s*\\**\\s*EXPLORATION\\s+DONE\\b', re.IGNO…` |
| `_PLAN_RE` | `re.compile('PLAN\\s*:\\s*(.*?)(?:```\|\\Z)', re.IGNORECASE…` |
| `_ITEM_RE` | `re.compile('^\\s*(?:\\d+[.)]\|[-*•])\\s+(.+?)\\s*$', re.MU…` |
| `MIN_GROUP` | `10` |
| `RATIO_FOLD` | `1.3` |
| `SLOPE_GAP` | `0.15` |
| `ISOTOPE_DEV_PCT` | `5.0` |
| `ISOTOPE_OUTSIDE_PCT` | `20.0` |
| `MASS_FOLD` | `3.0` |
| `CRUST_FOLD` | `3.0` |

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
    fixes (int): Fix attempts spent on the current turn.
    retry (bool): The next request fixes the current turn's code, so
        it does not start a new turn.
    codes (dict): Code already run, normalised, mapped to its turn.
    repeats (int): Times the model sent code it had already run.

| Method | Signature | Description |
|--------|-----------|-------------|
| `plan_text` | `(self)` | The plan as a numbered list. |
| `seen_numbers` | `(self)` | Every number in the messages the model has been sent so far. |
| `vet_findings` | `(self, code, result)` | Refuse findings whose numbers do not come from a result the model has seen. |
| `begin_turn` | `(self)` | Start the next request: a fix of the current turn or a new turn. |
| `repeated` | `(self, code)` | Whether *code* was already run, ignoring comments and spacing. |
| `too_many_repeats` | `(self)` | Whether the model keeps resending code it already ran. |
| `after_code` | `(self, error, done)` | Decide what follows a turn's code. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_num` | `(v)` | Return *v* as a finite float, or ``None``. |
| `_is_record_call` | `(node)` | Whether an AST node calls ``record_finding``. |
| `_typed_numbers` | `(call)` | Whether a ``record_finding`` call holds numbers written by hand. |
| `finding_layout` | `(code)` | Where a turn's code records its findings. |
| `premature_finding_lines` | `(code)` | Lines where a finding with hand-written numbers follows new code, see :func:`finding_layout`. |
| `unbacked_numbers` | `(finding, pool)` | Numbers in a finding that no result the model saw contains. |
| `parse_plan` | `(text)` | Pull the numbered hypotheses out of a ``PLAN:`` section. |
| `is_done` | `(text)` | Whether the model declared the exploration finished. |
| `code_key` | `(code)` | Code reduced to what it does: no comment lines, no trailing spaces, no blank lines. |
| `repeat_request` | `(turn)` | Tell the model it sent code it already ran. |
| `compact_messages` | `(messages, keep_last=KEEP_FULL_TURNS)` | Shorten old exploration turns so each request stays small and fast. |
| `_fmt` | `(v)` | Short number for the first look. |
| `_p` | `(v)` | A p value as text, floor values shown as a bound. |
| `_ratio` | `(v)` | A ratio with two decimals, or three significant digits when far from 1. |
| `_usable` | `(frame, by='sample')` | Rows of a per-group table with enough particles, as (group, row) pairs. |
| `_crust_table` | `(ds, a, b)` | Per-sample crust comparison of a pair, or None when the crust has no value for it. |
| `_crust_reading` | `(ds, a, b, samples)` | How the named samples compare with the crustal ratio, as one clause. |
| `_crust_far` | `(ds, a, b)` | A lead when a pair's ratio in particles is far from the crust in every sample that has it. |
| `_pair_leads` | `(ds, a, b, multi)` | Leads for one pair of elements that really share particles. |
| `_isotope_leads` | `(ds, multi)` | Leads from isotope ratios of elements measured on two or more isotopes. |
| `_mass_leads` | `(ds)` | Low-priority leads: large mass differences and elements missing from samples. |
| `elements_named` | `(ds, question)` | The dataset's elements that a question names. |
| `_burst_stretches` | `(table)` | Join flagged time bins that touch into stretches, one row per stretch. |
| `_element_leads` | `(ds, label)` | Time bursts and outliers of one element, for a question about that element. |
| `samples_named` | `(ds, question)` | The dataset's samples that a question names. |
| `_focus_on_samples` | `(leads, named, others)` | Order leads for a question about some samples. |
| `first_look` | `(ds, question='', max_items=7)` | A silent deep screen of the data, given before the first turn. |
