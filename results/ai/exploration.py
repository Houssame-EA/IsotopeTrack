"""State of an agentic exploration: the plan, the findings and the steps.

An exploration is a loop in which the model writes one query per turn and
sees its results. What it learns is kept here, outside the chat history,
so trimming old messages to fit the context window never loses a finding,
and the final summary is written from this record rather than from memory.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

DONE_RE = re.compile(r'^\s*\**\s*EXPLORATION\s+DONE\b', re.IGNORECASE | re.MULTILINE)
_PLAN_RE = re.compile(r'PLAN\s*:\s*(.*?)(?:```|\Z)', re.IGNORECASE | re.DOTALL)
_ITEM_RE = re.compile(r'^\s*(?:\d+[.)]|[-*•])\s+(.+?)\s*$', re.MULTILINE)


def _num(v):
    """Return *v* as a finite float, or ``None``."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


@dataclass
class Finding:
    """One result the model recorded with ``record_finding``.

    Attributes:
        claim (str): The finding in plain words.
        n (float): Particles or samples involved.
        p (float): p-value of the supporting test.
        effect (float): Effect size, e.g. a ratio of medians.
        evidence (str): Extra detail.
        turn (int): Exploration turn that produced it.
    """

    claim: str
    n: float | None = None
    p: float | None = None
    effect: float | None = None
    evidence: str = ''
    turn: int = 0

    @property
    def supported(self):
        """Whether the finding is backed by a significant test, or untested."""
        return self.p is None or self.p < 0.05

    def line(self):
        """One-line text form for prompts and summaries."""
        bits = [self.claim]
        extra = []
        if self.n is not None:
            extra.append(f"n={self.n:g}")
        if self.p is not None:
            extra.append(f"p={self.p:.3g}")
        if self.effect is not None:
            extra.append(f"effect={self.effect:.3g}")
        if extra:
            bits.append(f"({', '.join(extra)})")
        if self.evidence:
            bits.append(f"— {self.evidence}")
        return ' '.join(bits)


class FindingsLedger:
    """The findings of one exploration, de-duplicated and ranked."""

    def __init__(self):
        """Start empty."""
        self.findings = []

    def __len__(self):
        """Number of findings."""
        return len(self.findings)

    def add(self, raw, turn):
        """Record findings from one turn.

        Args:
            raw (list): Dicts from the sandbox's ``record_finding``.
            turn (int): The turn number.

        Returns:
            int: How many new findings were added.
        """
        added = 0
        seen = {f.claim.strip().lower() for f in self.findings}
        for r in raw or []:
            claim = str(r.get('claim', '')).strip()
            if not claim or claim.lower() in seen:
                continue
            self.findings.append(Finding(claim=claim, n=_num(r.get('n')), p=_num(r.get('p')),
                                         effect=_num(r.get('effect')),
                                         evidence=str(r.get('evidence') or '').strip(), turn=turn))
            seen.add(claim.lower())
            added += 1
        return added

    def ranked(self):
        """Findings ordered by strength: significant first, then by effect size."""
        def key(f):
            """Sort key: supported, p-value, effect magnitude."""
            p = f.p if f.p is not None else 0.5
            eff = abs(math.log(abs(f.effect))) if f.effect not in (None, 0) else 0.0
            return (not f.supported, p, -eff)
        return sorted(self.findings, key=key)

    def as_text(self, limit=20):
        """Numbered text form for prompts.

        Args:
            limit (int): Most findings to include.

        Returns:
            str: One finding per line, or an empty string.
        """
        lines = []
        for i, f in enumerate(self.ranked()[:limit], start=1):
            tag = 'supported' if f.supported else 'not supported'
            lines.append(f"{i}. [{tag}, turn {f.turn}] {f.line()}")
        return '\n'.join(lines)

    def numbers(self):
        """Every number the findings hold, for the fabrication check."""
        from results.ai.sandbox import floats_in_text
        out = []
        for f in self.findings:
            out.extend(v for v in (f.n, f.p, f.effect) if v is not None)
            out.extend(floats_in_text(f.claim))
            out.extend(floats_in_text(f.evidence))
        return out


def parse_plan(text):
    """Pull the numbered hypotheses out of a ``PLAN:`` section.

    Args:
        text (str): The model's first exploration reply.

    Returns:
        list: Hypotheses in order, empty when there is no plan.
    """
    m = _PLAN_RE.search(text or '')
    if not m:
        return []
    items = [s.strip() for s in _ITEM_RE.findall(m.group(1))]
    return [s for s in items if len(s) > 3][:8]


def is_done(text):
    """Whether the model declared the exploration finished.

    Args:
        text (str): Model reply.

    Returns:
        bool: True when ``EXPLORATION DONE`` starts a line.
    """
    return bool(DONE_RE.search(text or ''))


@dataclass
class ExplorationState:
    """Everything one exploration run keeps between turns.

    Attributes:
        question (str): What the user asked.
        max_turns (int): Turn budget.
        turn (int): Turns run so far.
        plan (list): The model's hypotheses.
        ledger (FindingsLedger): Findings recorded so far.
        messages (list): The exploration's own chat history.
        numbers (list): Every number produced across turns.
        failures (int): Consecutive turns that ended in an error.
    """

    question: str
    max_turns: int = 10
    turn: int = 0
    plan: list = field(default_factory=list)
    ledger: FindingsLedger = field(default_factory=FindingsLedger)
    messages: list = field(default_factory=list)
    numbers: list = field(default_factory=list)
    failures: int = 0

    def plan_text(self):
        """The plan as a numbered list."""
        return '\n'.join(f"{i}. {h}" for i, h in enumerate(self.plan, start=1))
