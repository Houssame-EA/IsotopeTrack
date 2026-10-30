"""State of an agentic exploration: the plan, the findings and the steps.

An exploration is a loop in which the model writes one query per turn and
sees its results. What it learns is kept here, outside the chat history,
so trimming old messages to fit the context window never loses a finding,
and the final summary is written from this record rather than from memory.
"""
from __future__ import annotations

import ast
import itertools
import math
import re
from dataclasses import dataclass, field

from results.ai.analysis import element_symbol

MAX_EXPLORE_FIXES = 2
MAX_FAILED_TURNS = 2
MAX_REPEATS = 2
"""Times the model may send code it already ran before the exploration ends."""
KEEP_FULL_TURNS = 2

ELEMENT_NAMES = dict(pair.split(':') for pair in (
    'H:hydrogen He:helium Li:lithium Be:beryllium B:boron C:carbon N:nitrogen O:oxygen F:fluorine '
    'Ne:neon Na:sodium Mg:magnesium Al:aluminium Si:silicon P:phosphorus S:sulfur Cl:chlorine Ar:argon '
    'K:potassium Ca:calcium Sc:scandium Ti:titanium V:vanadium Cr:chromium Mn:manganese Fe:iron '
    'Co:cobalt Ni:nickel Cu:copper Zn:zinc Ga:gallium Ge:germanium As:arsenic Se:selenium Br:bromine '
    'Kr:krypton Rb:rubidium Sr:strontium Y:yttrium Zr:zirconium Nb:niobium Mo:molybdenum '
    'Tc:technetium Ru:ruthenium Rh:rhodium Pd:palladium Ag:silver Cd:cadmium In:indium Sn:tin '
    'Sb:antimony Te:tellurium I:iodine Xe:xenon Cs:caesium Ba:barium La:lanthanum Ce:cerium '
    'Pr:praseodymium Nd:neodymium Pm:promethium Sm:samarium Eu:europium Gd:gadolinium Tb:terbium '
    'Dy:dysprosium Ho:holmium Er:erbium Tm:thulium Yb:ytterbium Lu:lutetium Hf:hafnium Ta:tantalum '
    'W:tungsten Re:rhenium Os:osmium Ir:iridium Pt:platinum Au:gold Hg:mercury Tl:thallium Pb:lead '
    'Bi:bismuth Po:polonium At:astatine Rn:radon Fr:francium Ra:radium Ac:actinium Th:thorium '
    'Pa:protactinium U:uranium Np:neptunium Pu:plutonium Am:americium').split())
"""English element names by symbol, for questions that name an element in words."""
ELEMENT_NAME_VARIANTS = {'aluminum': 'Al', 'cesium': 'Cs', 'sulphur': 'S', 'wolfram': 'W'}
WORD_SYMBOLS = frozenset({'I', 'In', 'As', 'At', 'Be', 'He', 'No', 'Am'})
"""Symbols that are also English words; written alone they count only inside a sentence."""

TYPED_NUMBER_RE = re.compile(r'(?<![\w.%])\d+\.\d+|(?<![\w.%])\d+(?:\.\d+)?[eE][-+]?\d+')
"""A decimal or scientific number written into the code by hand."""
FOLD_RE = re.compile(r'[-+]?\d[\d.,]*(?:[eE][-+]?\d+)?\s*(?:x|×|-?fold)(?![A-Za-z])', re.IGNORECASE)
"""Fold changes such as ``35.8x``, which the model derives from two results."""
PREMATURE_FINDING = (
    "record_finding on line {line} types numbers by hand after this block computes a new result, so "
    "they cannot come from that result: you have not seen it yet. Build the claim from the computed "
    "values with an f-string, e.g. f\"median {{res['median_ratio'].iloc[0]:.3g}}\", and pass p from the "
    "table, or record the finding next turn once you have seen the result. A finding about an earlier "
    "turn's result goes at the top of the block, before any new code.")
UNBACKED_FINDING = (
    "record_finding quotes {numbers}, which no result you have seen contains. Quote the numbers of the "
    "tables you were shown, or compute them in the code; pass p from the test you ran, and p=None for a "
    "descriptive finding with no test.")

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


def _is_record_call(node):
    """Whether an AST node calls ``record_finding``."""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == 'record_finding')


def _typed_numbers(call):
    """Whether a ``record_finding`` call holds numbers written by hand.

    A float literal (``p=1e-300``) or a decimal inside a string literal
    (``'median 0.18'``) counts; values inside the braces of an f-string are
    computed, and whole numbers such as isotope masses or ``95%`` are ignored.

    Args:
        call (ast.Call): The call.

    Returns:
        bool: True when a hand-written number is found.
    """
    def walk(node):
        if isinstance(node, ast.FormattedValue):
            return False
        if isinstance(node, ast.Constant):
            if isinstance(node.value, float):
                return True
            return isinstance(node.value, str) and bool(TYPED_NUMBER_RE.search(node.value))
        return any(walk(child) for child in ast.iter_child_nodes(node))
    return any(walk(a) for a in list(call.args) + [k.value for k in call.keywords])


def finding_layout(code):
    """Where a turn's code records its findings.

    Findings typed by hand may only describe results the model has already
    seen, so they belong before any new computation in the block. One that
    comes after it was written before its result existed.

    Args:
        code (str): One turn's code.

    Returns:
        tuple: ``(leading, premature)``: how many ``record_finding`` calls
        open the block before any other code, and the lines where a call
        with hand-written numbers follows new code. ``(0, [])`` when the
        code does not parse.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return 0, []
    leading, lines, at_top = 0, [], True
    for stmt in tree.body:
        if at_top and isinstance(stmt, ast.Expr) and _is_record_call(stmt.value):
            leading += 1
            continue
        at_top = False
        lines.extend(node.lineno for node in ast.walk(stmt) if _is_record_call(node) and _typed_numbers(node))
    return leading, sorted(lines)


def premature_finding_lines(code):
    """Lines where a finding with hand-written numbers follows new code, see :func:`finding_layout`."""
    return finding_layout(code)[1]


def unbacked_numbers(finding, pool):
    """Numbers in a finding that no result the model saw contains.

    Fold changes (``35.8x``) are left out, since they are derived from two
    results rather than read from one.

    Args:
        finding (dict): ``claim``, ``p``, ``effect`` and ``evidence``.
        pool (list): Every number the model has been shown.

    Returns:
        list: The unbacked numbers as written.
    """
    from results.ai.sandbox import to_float, unverified_numbers
    text = ' '.join(str(finding.get(k) or '') for k in ('claim', 'effect', 'evidence'))
    bad = unverified_numbers(FOLD_RE.sub(' ', text), pool)
    p = to_float(finding.get('p'))
    if p is not None and math.isfinite(p) and not any(
            a is not None and math.isfinite(a) and abs(a - p) <= 0.006 * max(abs(a), abs(p))
            for a in pool):
        bad.append(f"p={finding.get('p')}")
    return bad


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
        fixes (int): Fix attempts spent on the current turn.
        retry (bool): The next request fixes the current turn's code, so
            it does not start a new turn.
        codes (dict): Code already run, normalised, mapped to its turn.
        repeats (int): Times the model sent code it had already run.
    """

    question: str
    max_turns: int = 10
    turn: int = 0
    plan: list = field(default_factory=list)
    ledger: FindingsLedger = field(default_factory=FindingsLedger)
    messages: list = field(default_factory=list)
    numbers: list = field(default_factory=list)
    failures: int = 0
    fixes: int = 0
    retry: bool = False
    codes: dict = field(default_factory=dict)
    repeats: int = 0

    def plan_text(self):
        """The plan as a numbered list."""
        return '\n'.join(f"{i}. {h}" for i, h in enumerate(self.plan, start=1))

    def seen_numbers(self):
        """Every number in the messages the model has been sent so far."""
        from results.ai.sandbox import floats_in_text
        nums = []
        for m in self.messages:
            if m.get('role') == 'user':
                nums.extend(floats_in_text(m.get('content', '')))
        return nums

    def vet_findings(self, code, result):
        """Refuse findings whose numbers do not come from a result the model has seen.

        A finding typed by hand after new code, or one typed at the top of
        the block that quotes a number no result shown so far holds, sets
        ``result.error`` so the turn is
        sent back for a fix that does not use a turn, and the turn's findings
        are dropped; the fixed code records them again.

        Args:
            code (str): The turn's code.
            result (ExecResult): Its run, changed in place.

        Returns:
            str: The problem told to the model, empty when the findings are fine.
        """
        from results.ai.sandbox import output_numbers
        if result.error or not result.findings:
            return ''
        leading, lines = finding_layout(code)
        if lines:
            problem = PREMATURE_FINDING.format(line=lines[0])
        else:
            pool = self.seen_numbers() + output_numbers(result)
            bad = [n for f in result.findings[:leading] for n in unbacked_numbers(f, pool)]
            problem = UNBACKED_FINDING.format(numbers=', '.join(dict.fromkeys(bad))) if bad else ''
        if problem:
            result.findings = []
            result.error = problem
        return problem

    def begin_turn(self):
        """Start the next request: a fix of the current turn or a new turn.

        Returns:
            bool: False when the turn budget is used up.
        """
        if self.retry:
            self.retry = False
            return True
        if self.turn >= self.max_turns:
            return False
        self.turn += 1
        self.fixes = 0
        return True

    def repeated(self, code):
        """Whether *code* was already run, ignoring comments and spacing.

        New code is remembered under the current turn. A repeat is counted;
        :meth:`too_many_repeats` then says when to stop.

        Args:
            code (str): The turn's code.

        Returns:
            int: The turn that already ran it, or 0 when it is new.
        """
        key = code_key(code)
        if key in self.codes:
            self.repeats += 1
            return self.codes[key]
        self.codes[key] = self.turn
        return 0

    def too_many_repeats(self):
        """Whether the model keeps resending code it already ran."""
        return self.repeats >= MAX_REPEATS

    def after_code(self, error, done):
        """Decide what follows a turn's code.

        A failed run is sent back for a fix that does not use a turn, up to
        :data:`MAX_EXPLORE_FIXES` times, so one typo does not cost a whole
        hypothesis. Turns that still fail count towards stopping.

        Args:
            error (str): The sandbox error, empty when the code ran.
            done (bool): Whether the model declared the exploration finished.

        Returns:
            str: ``fix``, ``finish`` or ``next``.
        """
        if error and self.fixes < MAX_EXPLORE_FIXES:
            self.fixes += 1
            self.retry = True
            return 'fix'
        self.failures = self.failures + 1 if error else 0
        if self.failures >= MAX_FAILED_TURNS or done:
            return 'finish'
        return 'next'


def code_key(code):
    """Code reduced to what it does: no comment lines, no trailing spaces, no blank lines."""
    lines = []
    for line in str(code or '').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        lines.append(' '.join(line.rstrip().split()))
    return '\n'.join(lines)


def repeat_request(turn):
    """Tell the model it sent code it already ran.

    Args:
        turn (int): The turn that ran it.

    Returns:
        str: Message text.
    """
    return (f"[REPEATED CODE] This is the same code you ran in turn {turn}; its results are already above, "
            "so it was not run again. Test a different hypothesis from your plan with new code, "
            "or reply EXPLORATION DONE.")


def compact_messages(messages, keep_last=KEEP_FULL_TURNS):
    """Shorten old exploration turns so each request stays small and fast.

    The first message (the question and first look) and the last
    *keep_last* turns stay whole. Older replies keep their hypothesis line
    and lose their code; older results keep their heading, since every new
    result message repeats the plan and all findings recorded so far.

    Args:
        messages (list): The exploration's chat history.
        keep_last (int): Recent turns to keep whole.

    Returns:
        list: A new, shorter list of messages.
    """
    if len(messages) <= 1 + 2 * keep_last:
        return list(messages)
    head, body = messages[:1], messages[1:]
    old, recent = body[:-2 * keep_last], body[-2 * keep_last:]
    out = list(head)
    for m in old:
        text = str(m.get('content', ''))
        if m.get('role') == 'assistant':
            cut = text.find('```')
            text = (text[:cut].strip() if cut >= 0 else text.strip())[:300]
            text = (text + "\n[code omitted]").strip()
        else:
            first = text.strip().split('\n', 1)[0]
            text = first[:200] + "\n[results omitted; their findings are listed below]"
        out.append({'role': m.get('role', 'user'), 'content': text})
    out.extend(recent)
    return out


def _fmt(v):
    """Short number for the first look."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    if v != v:
        return 'n/a'
    if v and (abs(v) < 0.01 or abs(v) >= 1e4):
        return f"{v:.2g}"
    return f"{v:.3g}"


MIN_GROUP = 10
RATIO_FOLD = 1.3
SLOPE_GAP = 0.15
ISOTOPE_DEV_PCT = 5.0
ISOTOPE_OUTSIDE_PCT = 20.0
MASS_FOLD = 3.0


def _p(v):
    """A p value as text, floor values shown as a bound."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 'n/a'
    if v != v:
        return 'n/a'
    return '<1e-300' if v <= 1e-299 else _fmt(v)


def _ratio(v):
    """A ratio with two decimals, or three significant digits when far from 1."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 'n/a'
    return f"{v:.2f}" if 0.1 <= abs(v) < 100 else _fmt(v)


def _usable(frame, by='sample'):
    """Rows of a per-group table with enough particles, as (group, row) pairs."""
    return [(r[by], r) for _, r in frame.iterrows() if r.get('n', 0) >= MIN_GROUP]


CRUST_FOLD = 3.0


def _crust_table(ds, a, b):
    """Per-sample crust comparison of a pair, or None when the crust has no value for it."""
    from results.ai import analysis as A
    try:
        return A.crust_ratio(ds, a, b)
    except Exception:
        return None


def _crust_reading(ds, a, b, samples):
    """How the named samples compare with the crustal ratio, as one clause."""
    cr = _crust_table(ds, a, b)
    if cr is None:
        return ''
    cr = cr.set_index('sample')
    parts = []
    for g in samples:
        ef = cr.at[g, 'ef_particles'] if g in cr.index else float('nan')
        if ef != ef:
            continue
        parts.append(f"{g} crust-like (EF {_fmt(ef)})" if 1 / 1.5 <= ef <= 1.5 else f"{g} EF {_fmt(ef)}")
    if not parts:
        return ''
    from results.ai.crust import SHORT_REFERENCE
    sa, sb = element_symbol(a), element_symbol(b)
    return (f"upper crust {sa}/{sb} mass ratio is {_fmt(cr['crust_ratio'].iloc[0])} ({SHORT_REFERENCE}): "
            + ', '.join(parts))


def _crust_far(ds, a, b):
    """A lead when a pair's ratio in particles is far from the crust in every sample that has it."""
    cr = _crust_table(ds, a, b)
    if cr is None:
        return ''
    efs = [(r['sample'], r['ef_particles']) for _, r in cr.iterrows() if r['ef_particles'] == r['ef_particles']]
    if not efs or not all(ef >= CRUST_FOLD or ef <= 1 / CRUST_FOLD for _, ef in efs):
        return ''
    from results.ai.crust import SHORT_REFERENCE
    sa, sb = element_symbol(a), element_symbol(b)
    where = ', '.join(f"EF {_fmt(ef)} in {g}" for g, ef in efs)
    return (f"{sa}/{sb} mass ratio in particles is far from the upper crust ({_fmt(cr['crust_ratio'].iloc[0])}, "
            f"{SHORT_REFERENCE}): {where}. Not crust-like material; an engineered or anthropogenic source?")


def _pair_leads(ds, a, b, multi):
    """Leads for one pair of elements that really share particles.

    Args:
        ds (Dataset): The dataset.
        a (str): First element.
        b (str): Second element.
        multi (bool): Whether there is more than one sample.

    Returns:
        tuple: ``(leads, quiet)`` where leads are ``(score, text)`` pairs and
        quiet names the checks that found nothing.
    """
    from results.ai import analysis as A
    leads, quiet = [], []
    sa, sb = element_symbol(a), element_symbol(b)
    mr = A.molar_ratio(ds, a, b)
    rows = _usable(mr)
    tight = [(g, r) for g, r in rows if r['log10_iqr'] == r['log10_iqr'] and r['log10_iqr'] < 0.15]
    differ = None
    if multi and len(rows) >= 2:
        hi = max(rows, key=lambda t: t[1]['median_ratio'])
        lo = min(rows, key=lambda t: t[1]['median_ratio'])
        fold = hi[1]['median_ratio'] / lo[1]['median_ratio'] if lo[1]['median_ratio'] > 0 else float('nan')
        p_min = min(float(r['p_vs_rest']) for _, r in rows)
        if fold == fold and fold >= RATIO_FOLD and p_min < 1e-3:
            def show(t):
                """One sample's ratio with its whole-number form."""
                simple = f" (about {t[1]['simple_ratio']})" if t[1]['simple_ratio'] else ''
                return f"{_ratio(t[1]['median_ratio'])}{simple} in {t[0]}"
            differ = (f"{sa}/{sb} molar ratio differs between samples: {show(hi)} vs {show(lo)} "
                      f"(x{_fmt(fold)}, p vs rest {_p(p_min)})")
            if tight:
                differ += ("; the ratio is tight in " + ', '.join(
                    f"{g} (log10 IQR {_fmt(r['log10_iqr'])})" for g, r in tight) + ", a fixed composition there")
            near = _crust_reading(ds, a, b, [hi[0], lo[0]])
            if near:
                differ += f"; {near}"
            leads.append((8 + math.log2(fold), differ + f". Different {sa}-{sb} materials?"))
        else:
            quiet.append(f"{sa}/{sb} molar ratio (same in all samples)")
    if differ is None:
        far = _crust_far(ds, a, b)
        if far:
            leads.append((5.5, far))
    if tight and differ is None:
        g, r = tight[0]
        where = ', '.join(t[0] for t in tight) if multi else 'the sample'
        simple = f", about {r['simple_ratio']}" if r['simple_ratio'] else ''
        leads.append((5, f"{sa}/{sb} molar ratio is tight in {where}: median {_ratio(r['median_ratio'])}{simple}, "
                         f"log10 IQR {_fmt(r['log10_iqr'])}. One compound or alloy of fixed composition?"))
    if multi:
        corr = A.element_correlation(ds, a, b)
        fits = [(g, r) for g, r in _usable(corr) if r.get('slope') == r.get('slope')]
        if len(fits) >= 2:
            hi = max(fits, key=lambda t: t[1]['slope'])
            lo = min(fits, key=lambda t: t[1]['slope'])
            gap = hi[1]['slope'] - lo[1]['slope']
            if gap >= SLOPE_GAP and lo[1]['slope_high'] < hi[1]['slope_low']:
                bent = [g for g, r in fits if not r['slope_low'] <= 1.0 <= r['slope_high'] and abs(r['slope'] - 1) >= 0.1]
                where = (f"the {sb}/{sa} ratio changes with particle size in {', '.join(bent)}"
                         if bent else "the two samples scale differently")
                leads.append((7 + 5 * gap,
                              f"{sb} against {sa} (log mass) has a slope of {_fmt(hi[1]['slope'])} in {hi[0]} "
                              f"but {_fmt(lo[1]['slope'])} in {lo[0]} (95% intervals apart): {where}."))
            else:
                quiet.append(f"{sa}-{sb} scaling with size (same slope)")
        strong = [g for g, r in fits if r['spearman_rho'] >= 0.5 and r['p'] < 1e-3]
        weak = [g for g, r in fits if r['spearman_rho'] < 0.2]
        if strong and weak:
            leads.append((6, f"{sa} and {sb} are correlated in {', '.join(strong)} but not in {', '.join(weak)}."))
        shared = mr.set_index('sample')['n']
        only = [g for g, n in shared.items() if n >= MIN_GROUP]
        none = [g for g, n in shared.items() if n <= 1]
        if only and none:
            def missing(g):
                """The pair's elements with no detection at all in sample *g*."""
                return tuple(e for e in (a, b) if not ds.df.loc[ds.df['sample'] == g, f'counts_{e}'].notna().any())
            gone = {g: missing(g) for g in none}
            if all(len(m) == 2 for m in gone.values()):
                reason = " (neither element is detected there)"
            elif any(gone.values()):
                reason = " (" + '; '.join(f"{', '.join(m)} not detected in {g}" for g, m in gone.items() if m) + ")"
            else:
                reason = " although both elements are detected there"
            leads.append((6.5 if len(only) == 1 else 3,
                          f"{a} + {b} particles occur only in {', '.join(only)} "
                          f"({', '.join(str(int(shared[g])) for g in only)} particles), none in "
                          f"{', '.join(none)}{reason}."))
    return leads, quiet


def _isotope_leads(ds, multi):
    """Leads from isotope ratios of elements measured on two or more isotopes."""
    from results.ai import analysis as A
    leads, quiet = [], []
    by_symbol = {}
    for el in ds.elements:
        by_symbol.setdefault(element_symbol(el), []).append(el)
    for sym, isos in by_symbol.items():
        if len(isos) < 2:
            continue
        for num, den in itertools.combinations(isos, 2):
            try:
                ir = A.isotope_ratio(ds, num, den)
            except Exception:
                continue
            rows = [(g, r) for g, r in _usable(ir) if r['deviation_pct'] == r['deviation_pct']]
            if not rows:
                if _usable(ir) and multi:
                    vals = [(g, r['ratio']) for g, r in _usable(ir)]
                    hi, lo = max(vals, key=lambda t: t[1]), min(vals, key=lambda t: t[1])
                    if lo[1] > 0 and hi[1] / lo[1] - 1 >= ISOTOPE_DEV_PCT / 100:
                        leads.append((9, f"{num}/{den} ratio differs between samples: {_fmt(hi[1])} in {hi[0]} "
                                         f"vs {_fmt(lo[1])} in {lo[0]} (natural ratio unknown)."))
                continue
            off = [(g, r) for g, r in rows if abs(r['deviation_pct']) >= ISOTOPE_DEV_PCT
                   and r['pct_outside_2sd'] >= ISOTOPE_OUTSIDE_PCT]
            near = [g for g, r in rows if abs(r['deviation_pct']) < ISOTOPE_DEV_PCT]
            if off and (near or not multi):
                for g, r in off:
                    leads.append((10 + min(abs(r['deviation_pct']), 50) / 5,
                                  f"{num}/{den} = {_fmt(r['ratio'])} in {g}, {_fmt(r['deviation_pct'])}% from natural "
                                  f"{_fmt(r['natural'])}, with {_fmt(r['pct_outside_2sd'])}% of its particles outside "
                                  f"counting error (5% by chance)"
                                  + (f"; {', '.join(near)} natural." if near else ".")
                                  + f" A non-natural {sym} source?"))
            elif off:
                devs = ', '.join(f"{_fmt(r['deviation_pct'])}% in {g}" for g, r in off)
                leads.append((4, f"{num}/{den} is off natural {_fmt(off[0][1]['natural'])} in every sample "
                                 f"({devs}): mass bias, or one {sym} source for all?"))
            else:
                quiet.append(f"{num}/{den} (natural in {'all samples' if multi else 'the sample'})")
    return leads, quiet


def _mass_leads(ds):
    """Low-priority leads: large mass differences and elements missing from samples."""
    from scipy import stats
    from results.ai import analysis as A
    leads, flat = [], []
    summ = A.element_summary(ds, by='sample')
    for el, g in summ.groupby('element', sort=False):
        g = g[g['n'] >= MIN_GROUP]
        if len(g) < 2:
            continue
        vals = [ds.df.loc[ds.df['sample'] == smp, f'mass_fg_{el}'].dropna().to_numpy() for smp in g['sample']]
        vals = [v for v in vals if v.size >= 3]
        p = stats.kruskal(*vals).pvalue if len(vals) >= 2 else float('nan')
        hi, lo = g.loc[g['median'].idxmax()], g.loc[g['median'].idxmin()]
        fold = hi['median'] / lo['median'] if lo['median'] > 0 else float('nan')
        if fold == fold and fold >= MASS_FOLD and p < 1e-6:
            leads.append((3 + math.log2(fold) / 2,
                          f"{el} particles are heavier in {hi['sample']}: median {_fmt(hi['median'])} fg vs "
                          f"{_fmt(lo['median'])} fg in {lo['sample']} (x{_fmt(fold)}, Kruskal p {_p(p)})."))
        else:
            flat.append(el)
    counts = ds.df.groupby('sample').size()
    absent_by = {}
    for el in ds.elements:
        have = ds.df.groupby('sample')[f'counts_{el}'].count()
        absent = tuple(smp for smp in ds.samples if have.get(smp, 0) == 0 and counts.get(smp, 0) > 0)
        if absent and len(absent) < len(ds.samples):
            absent_by.setdefault(absent, []).append(el)
    for absent, els in absent_by.items():
        leads.append((2, f"{', '.join(els)} {'is' if len(els) == 1 else 'are'} not detected at all in "
                         f"{', '.join(absent)}.", set(els)))
    quiet = [f"particle mass of {', '.join(flat[:6])}{' and others' if len(flat) > 6 else ''} "
             f"(within x{_fmt(MASS_FOLD)} between samples)"] if flat else []
    return leads, quiet


def elements_named(ds, question):
    """The dataset's elements that a question names.

    An element counts when the question writes its isotope label
    (``56Fe``, ``Fe56``, ``Fe-56``), its symbol with the exact case
    (``Fe``) or its English name in any case (``iron``). Symbols that are
    also English words (``In``, ``As``, ``I``...) count alone only when they
    do not open a sentence, and ``I`` never counts alone.

    Args:
        ds (Dataset): The dataset.
        question (str): The user's question.

    Returns:
        list: Element symbols, in the dataset's order, each listed once.
    """
    text = str(question or '')
    present = {}
    for lab in ds.elements:
        present.setdefault(element_symbol(lab), lab)
    if not text or not present:
        return []
    found = set()
    for mass, sym in re.findall(r'(?<![A-Za-z\d])(\d{1,3})\s?-?([A-Z][a-z]?)(?![a-z])', text):
        found.add(sym)
    for sym, mass in re.findall(r'(?<![A-Za-z\d])([A-Z][a-z]?)-?(\d{1,3})(?![\d])', text):
        found.add(sym)
    for m in re.finditer(r'(?<![A-Za-z\d])([A-Z][a-z]?)(?![A-Za-z\d])', text):
        sym = m.group(1)
        if sym in WORD_SYMBOLS:
            before = text[:m.start()].rstrip()
            if sym == 'I' or not before or before[-1] in '.!?:;':
                continue
        found.add(sym)
    words = {name: sym for sym, name in ELEMENT_NAMES.items()}
    words.update(ELEMENT_NAME_VARIANTS)
    for word in re.findall(r'[A-Za-z]+', text.lower()):
        if word in words:
            found.add(words[word])
    return [sym for sym in present if sym in found]


def _burst_stretches(table):
    """Join flagged time bins that touch into stretches, one row per stretch."""
    out = []
    for run, g in table.sort_values(['run', 't_from']).groupby('run', sort=False):
        cur = None
        for _, r in g.iterrows():
            width = r['t_to'] - r['t_from']
            if cur and r['t_from'] - cur['t_to'] <= 0.01 * width:
                cur['t_to'] = r['t_to']
                cur['count'] += int(r['count'])
                cur['expected'] += float(r['expected'])
                cur['p'] = min(cur['p'], float(r['p']))
            else:
                cur = {'run': run, 't_from': float(r['t_from']), 't_to': float(r['t_to']),
                       'count': int(r['count']), 'expected': float(r['expected']), 'p': float(r['p'])}
                out.append(cur)
    return sorted(out, key=lambda c: -(c['count'] - c['expected']))


def _element_leads(ds, label):
    """Time bursts and outliers of one element, for a question about that element."""
    from results.ai import analysis as A
    leads, quiet = [], []
    run_sample = dict(zip(ds.df['run'], ds.df['sample'])) if 'sample' in ds.df.columns else {}
    try:
        table = A.time_bursts(ds, label)
        stretches = _burst_stretches(table) if len(table) else []
    except Exception:
        stretches = None
    if stretches:
        for c in stretches[:3]:
            smp = run_sample.get(c['run'], c['run'])
            where = smp if smp == c['run'] else f"run {c['run']} ({smp})"
            leads.append((40 + min(c['count'] / max(c['expected'], 1.0), 50) / 5,
                          f"{label} particles arrive in a burst in {where} from {_fmt(c['t_from'])} to "
                          f"{_fmt(c['t_to'])} s: {c['count']} particles where about {_fmt(c['expected'])} are "
                          f"expected (x{_fmt(c['count'] / max(c['expected'], 1e-9))}, p {_p(c['p'])}). "
                          f"Contamination or a nebuliser spike?"))
        if len(stretches) > 3:
            leads.append((39, f"{label} has {len(stretches) - 3} smaller burst(s) in time as well."))
    elif stretches is not None:
        quiet.append(f"{label} arrival in time (no bursts)")
    try:
        out = A.find_outliers(ds, element=label)
    except Exception:
        out = None
    col = f'mass_fg_{label}'
    if out is not None and len(out) and col in ds.df.columns:
        med = float(ds.df[col][ds.df[col] > 0].median())
        by = out['sample'].value_counts()
        top = out.iloc[0]
        leads.append((38, f"{len(out)} {label} particle(s) lie far outside the usual mass range (robust z >= 5), "
                          f"most in {by.index[0]} ({int(by.iloc[0])}); the most extreme is {_fmt(top['value'])} fg "
                          f"against a median of {_fmt(med)} fg, in {top['sample']}."))
    elif out is not None and col in ds.df.columns:
        quiet.append(f"{label} particle mass (no outliers)")
    return leads, quiet


def samples_named(ds, question):
    """The dataset's samples that a question names.

    A name matches in any case, with underscores, spaces and hyphens
    interchangeable (``River_A``, ``river a``, ``River-A``).

    Args:
        ds (Dataset): The dataset.
        question (str): The user's question.

    Returns:
        list: Sample names, in the dataset's order.
    """
    text = str(question or '')
    found = []
    for smp in ds.samples:
        parts = [re.escape(x) for x in re.split(r'[_\s-]+', str(smp)) if x]
        if parts and re.search(r'(?<![A-Za-z\d])' + r'[_\s-]?'.join(parts) + r'(?![A-Za-z\d])', text, re.I):
            found.append(smp)
    return found


def _focus_on_samples(leads, named, others):
    """Order leads for a question about some samples.

    Leads naming more of the asked samples come first, keeping the screen's
    order within each group; leads that name only other samples are dropped.

    Args:
        leads (list): ``(priority, text)`` pairs.
        named (list): Samples the question names.
        others (list): The dataset's other samples.

    Returns:
        list: The kept leads, most relevant first.
    """
    def mentions(text, smp):
        return re.search(r'(?<![A-Za-z\d])' + re.escape(smp) + r'(?![A-Za-z\d])', text) is not None
    kept = []
    for prio, text in leads:
        hits = sum(mentions(text, smp) for smp in named)
        if not hits and any(mentions(text, smp) for smp in others):
            continue
        kept.append((hits, prio, text))
    kept.sort(key=lambda t: (-t[0], -t[1]))
    return [(prio, text) for _, prio, text in kept]


def first_look(ds, question='', max_items=7):
    """A silent deep screen of the data, given before the first turn.

    Looks for what would surprise an analyst: molar ratios that differ
    between samples or are fixed, element pairs whose scaling with size
    changes between samples, pairs found in one sample only, isotope ratios
    away from natural, and, with low priority, large mass differences and
    missing elements. Only the leads are reported, most surprising first,
    with one line naming what was checked and found unremarkable. Bursts,
    outliers and truncation are left to the user's questions, except when
    the question names exactly one element: that element's time bursts and
    mass outliers are then screened too and lead the list. When the question
    names samples, the leads about those samples come first and leads about
    other samples only are left out.

    Args:
        ds (Dataset): The dataset.
        question (str): The user's question, or empty.
        max_items (int): Most leads to report.

    Returns:
        str: The screen as text, empty when nothing could be computed.
    """
    from results.ai import analysis as A
    multi = len(ds.samples) > 1
    leads, quiet = [], []
    named = elements_named(ds, question)
    if len(named) == 1:
        label = next(lab for lab in ds.elements if element_symbol(lab) == named[0])
        found, flat = _element_leads(ds, label)
        leads.extend(found)
        quiet.extend(flat)
    try:
        co = A.co_occurrence(ds)
        real = co[co['verdict'].str.contains('real', case=False)]
        for _, r in real.head(10).iterrows():
            try:
                found, flat = _pair_leads(ds, r['a'], r['b'], multi)
            except Exception:
                continue
            leads.extend(found)
            quiet.extend(flat)
        chance = int(co['verdict'].str.contains('chance', case=False).sum())
        if chance:
            quiet.append(f"{chance} other element pairs (shared particles only by chance)")
    except Exception:
        pass
    try:
        found, flat = _isotope_leads(ds, multi)
        leads.extend(found)
        quiet.extend(flat)
    except Exception:
        pass
    if multi:
        try:
            found, flat = _mass_leads(ds)
            covered = set()
            for _, text in leads:
                if ' particles occur only in ' in text:
                    covered.update(text.split(' particles occur only in ')[0].split(' + '))
            leads.extend((lead[0], lead[1]) for lead in found if len(lead) == 2 or not lead[2] <= covered)
            quiet.extend(flat)
        except Exception:
            pass
    if not leads and not quiet:
        return ''
    leads.sort(key=lambda t: -t[0])
    named_samples = samples_named(ds, question) if multi else []
    if named_samples:
        leads = _focus_on_samples(leads, named_samples, [x for x in ds.samples if x not in named_samples])
    lines = ["FIRST LOOK (an automatic screen, most surprising first; confirm each lead with your own "
             "tests and dig into it):"]
    if leads:
        lines.append("Leads:")
        lines.extend(f"  {i}. {text}" for i, (_, text) in enumerate(leads[:max_items], 1))
        if len(leads) > max_items:
            lines.append(f"  ({len(leads) - max_items} weaker lead(s) not shown.)")
    else:
        lines.append("Leads: none; nothing in the screen stands out.")
    if quiet:
        lines.append("Checked, nothing unusual: " + '; '.join(quiet) + '.')
    return '\n'.join(lines)
