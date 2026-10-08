"""Score a model on questions with known answers.

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
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field

import numpy as np

from results.ai.data import Dataset
from results.ai.prompts import (
    build_system_prompt, correction_request, interpretation_request, reply_reserve,
)
from results.ai.sandbox import execute, floats_in_text, result_digest
from results.ai.synthetic import make_dataset
from results.ai.theme import CODE_RE, strip_thinking


def _has(p, el):
    """Whether a particle dictionary holds element *el*."""
    try:
        return float((p.get('elements') or {}).get(el, 0)) > 0
    except (TypeError, ValueError):
        return False


def _truth_values(dc, truth):
    """Reference answers computed straight from the particle dictionaries.

    Kept independent of :mod:`results.ai.analysis`, so a bug there cannot
    make a wrong answer pass.
    """
    ps = dc['particle_data']
    ti_c = [p['element_diameter_nm']['48Ti'] for p in ps
            if p['source_sample'] == 'Spiked_C' and _has(p, '48Ti')]
    ce = [p for p in ps if _has(p, '140Ce')]
    medians = {}
    for s in truth.samples:
        v = [p['element_diameter_nm']['48Ti'] for p in ps if p['source_sample'] == s and _has(p, '48Ti')]
        medians[s] = float(np.median(v))
    multi = sum(1 for p in ps if sum(1 for v in p['elements'].values() if v > 0) > 1)
    return {
        'n_total': len(ps),
        'n_ti': sum(1 for p in ps if _has(p, '48Ti')),
        'ti_median_c': float(np.median(ti_c)),
        'largest_ti': max(medians, key=medians.get),
        'cela_pct': 100.0 * sum(1 for p in ce if _has(p, '139La')) / len(ce),
        'multi_pct': 100.0 * multi / len(ps),
    }


@dataclass
class Question:
    """One benchmark question.

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
    """

    qid: str
    text: str
    kind: str
    expected: object = None
    tolerance: float = 0.01
    reference: str = ''
    reject: str = ''
    first_of: list = field(default_factory=list)
    reference_answer: str = ''


def build_questions(dc, truth):
    """The question set for a synthetic dataset.

    Args:
        dc (dict): The synthetic data context.
        truth (Truth): What was planted.

    Returns:
        list: :class:`Question` objects.
    """
    t = _truth_values(dc, truth)
    burst_sample, b0, b1 = truth.burst
    return [
        Question('count_total', "How many particles are in the dataset?", 'number', t['n_total'], 0.0,
                 "print(len(df))"),
        Question('count_ti', "How many particles contain titanium?", 'number', t['n_ti'], 0.0,
                 "print(int(df[col('counts','Ti')].notna().sum()))"),
        Question('ti_median_c', "What is the median Ti equivalent diameter in sample Spiked_C, in nm?",
                 'number', t['ti_median_c'], 0.01,
                 "print(df.loc[df['sample']=='Spiked_C', col('size','Ti')].median())"),
        Question('largest_ti', "Which sample has the largest Ti particles?", 'text',
                 t['largest_ti'], 0.0,
                 "show_table(compare_samples('Ti'))", first_of=list(truth.samples),
                 reference_answer=f"{t['largest_ti']} has the largest Ti particles."),
        Question('alloy_sample', "Which sample contains particles with both Ag and Au?", 'text',
                 re.escape(truth.alloy_sample), 0.0,
                 "both = df[df[col('counts','Ag')].notna() & df[col('counts','Au')].notna()]\n"
                 "show_table(both['sample'].value_counts())"),
        Question('cela_pct', "What percentage of Ce-containing particles also contain La?", 'number',
                 t['cela_pct'], 0.01,
                 "ce = df[col('counts','Ce')].notna()\n"
                 "print(100 * (ce & df[col('counts','La')].notna()).sum() / ce.sum())"),
        Question('multi_pct', "What percentage of particles contain more than one element?", 'number',
                 t['multi_pct'], 0.01,
                 "print(100 * (df['n_elements'] > 1).mean())"),
        Question('tife_chance', "Are particles with both Ti and Fe real associations, or explained by "
                 "chance coincidence?", 'text', r'chance|coinciden', 0.0,
                 "show_table(coincidence('Ti', 'Fe'))", reject=r'\breal association\b(?!.*not)',
                 reference_answer="They occur about as often as chance coincidence predicts."),
        Question('cela_real', "Are Ce+La particles real associations or chance coincidences?", 'text',
                 r'real|genuine|associat|not.{0,20}(chance|coinciden)', 0.0,
                 "show_table(coincidence('Ce', 'La'))",
                 reference_answer="They are a real association, far above the chance rate."),
        Question('fe_burst', "Is there a burst of iron particles at some point in time? In which sample "
                 "and roughly when?", 'text', re.escape(burst_sample) + r'(?s:.*?)\b(19|20|21|22)\b', 0.0,
                 "show_table(time_bursts('Fe'))"),
        Question('fig_hist', "Plot a histogram of Fe particle mass for each sample, on a log mass axis.",
                 'figure', {'xscale': 'log', 'min_series': 3}, 0.0,
                 "fig, ax = plt.subplots()\n"
                 "for s in samples:\n"
                 "    ax.hist(df.loc[df['sample']==s, col('mass','Fe')].dropna(), bins=np.logspace(-2, 1, 50),"
                 " histtype='step', label=s)\n"
                 "ax.set_xscale('log'); ax.set_xlabel('Fe mass (fg)'); ax.set_ylabel('Particles'); ax.legend()"),
        Question('fig_scatter', "Make a log-log scatter plot of Ti mass versus Ti diameter, coloured by sample.",
                 'figure', {'xscale': 'log', 'yscale': 'log', 'min_series': 1, 'min_points': 1000}, 0.0,
                 "fig, ax = plt.subplots()\n"
                 "for s in samples:\n"
                 "    sub = df[df['sample']==s]\n"
                 "    ax.scatter(sub[col('size','Ti')], sub[col('mass','Ti')], s=3, label=s)\n"
                 "ax.set_xscale('log'); ax.set_yscale('log'); ax.set_xlabel('Ti diameter (nm)');"
                 " ax.set_ylabel('Ti mass (fg)'); ax.legend()"),
    ]


def complete(cfg, messages, system, timeout=600):
    """One non-streaming chat completion.

    Args:
        cfg (dict): ``backend`` (``ollama``, ``mlx`` or ``custom``),
            ``model``, ``host``, ``api_key``, ``num_ctx``, ``temperature``.
        messages (list): Chat messages.
        system (str): System prompt.
        timeout (float): Seconds to wait.

    Returns:
        str: The reply text.
    """
    from results.ai.servers import MLX_BASE, OLLAMA_BASE, local_session
    msgs = [{"role": "system", "content": system}] + list(messages)
    num_ctx = int(cfg.get('num_ctx', 8192))
    if cfg.get('backend', 'ollama') == 'ollama':
        host = (cfg.get('host') or OLLAMA_BASE).rstrip('/')
        with local_session() as s:
            r = s.post(f"{host}/api/chat", json={
                "model": cfg.get('model', ''), "messages": msgs, "stream": False,
                "options": {"temperature": cfg.get('temperature', 0.2), "num_ctx": num_ctx,
                            "num_predict": reply_reserve(num_ctx)}}, timeout=timeout)
        r.raise_for_status()
        return (r.json().get('message') or {}).get('content', '')
    host = (cfg.get('host') or MLX_BASE).rstrip('/')
    url = host if host.endswith('/v1') else f"{host}/v1"
    headers = {'Content-Type': 'application/json'}
    if cfg.get('api_key'):
        headers['Authorization'] = f"Bearer {cfg['api_key']}"
    payload = {"messages": msgs, "stream": False, "temperature": cfg.get('temperature', 0.2),
               "max_tokens": reply_reserve(num_ctx)}
    if cfg.get('model'):
        payload['model'] = cfg['model']
    session = local_session()
    if cfg.get('backend') == 'custom':
        import requests
        session = requests.Session()
    with session as s:
        r = s.post(f"{url}/chat/completions", json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content']


def reference_model(question):
    """A stand-in model that answers with the question's reference code.

    Args:
        question (Question): The question.

    Returns:
        callable: ``(messages, system) -> reply``.
    """
    state = {'calls': 0}

    def reply(messages, system):
        """Return the reference code first, then a takeaway quoting the results."""
        state['calls'] += 1
        if state['calls'] == 1:
            return f"Computing it.\n```python\n{question.reference}\n```"
        if question.reference_answer:
            return question.reference_answer
        return "From the results: " + messages[-1]['content'][:1500]
    return reply


@dataclass
class Outcome:
    """How one question went.

    Attributes:
        qid (str): Question id.
        passed (bool): Whether the answer was right.
        attempts (int): Code runs needed.
        seconds (float): Wall time.
        error (str): Last sandbox or backend error.
        detail (str): Why it passed or failed.
        answer (str): The final answer text.
    """

    qid: str
    passed: bool = False
    attempts: int = 0
    seconds: float = 0.0
    error: str = ''
    detail: str = ''
    answer: str = field(default='', repr=False)


def _check_figure(req, results):
    """Whether any figure meets the requirement."""
    for res in results:
        for f in res.figures:
            for ax in f['figure'].axes:
                if req.get('xscale') and ax.get_xscale() != req['xscale']:
                    continue
                if req.get('yscale') and ax.get_yscale() != req['yscale']:
                    continue
                series = len(ax.lines) + len(ax.collections) + len({id(c) for c in ax.containers})
                if ax.patches and not ax.containers:
                    series += 1 if len(ax.patches) else 0
                leg = ax.get_legend()
                if leg is not None:
                    series = max(series, len(leg.get_texts()))
                points = sum(len(c.get_offsets()) for c in ax.collections if hasattr(c, 'get_offsets'))
                if series >= req.get('min_series', 1) and points >= req.get('min_points', 0):
                    return True, f"figure ok ({series} series, {points} points)"
    return False, "no figure meets the requirement"


def score(question, results, answer):
    """Decide whether an answer is right.

    Args:
        question (Question): The question.
        results (list): Every :class:`~results.ai.sandbox.ExecResult` produced.
        answer (str): The final answer text.

    Returns:
        tuple: ``(passed, detail)``.
    """
    if question.kind == 'figure':
        return _check_figure(question.expected, results)
    pool = answer + '\n' + '\n'.join(result_digest(r, 50) for r in results)
    if question.kind == 'number':
        exp = float(question.expected)
        for v in floats_in_text(pool):
            if abs(v - exp) <= max(1e-9, question.tolerance * abs(exp)):
                return True, f"found {v:g} (expected {exp:g})"
        return False, f"expected {exp:g}, not found"
    if question.reject and re.search(question.reject, answer, re.I):
        return False, "answer contains a rejected claim"
    if question.first_of:
        hits = sorted((m.start(), name) for name in question.first_of
                      for m in [re.search(re.escape(name), answer)] if m)
        if hits and hits[0][1] == question.expected:
            return True, f"answer names {question.expected} first"
        return False, f"answer does not name {question.expected} first"
    target = answer if question.reference_answer else pool
    if re.search(question.expected, target, re.I):
        return True, "expected text found"
    return False, f"/{question.expected}/ not found"


def ask(question, ds, model, num_ctx=8192, max_fixes=2):
    """Put one question through the chat pipeline.

    Args:
        question (Question): The question.
        ds (Dataset): The dataset.
        model (callable): ``(messages, system) -> reply``.
        num_ctx (int): Context window.
        max_fixes (int): Correction rounds allowed.

    Returns:
        Outcome: The result.
    """
    out = Outcome(qid=question.qid)
    t0 = time.time()
    system = build_system_prompt(ds, num_ctx)
    messages = [{"role": "user", "content": question.text}]
    results = []
    answer = ''
    try:
        for _ in range(max_fixes + 1):
            reply = strip_thinking(model(messages, system))
            codes = [c for c in CODE_RE.findall(reply) if c.strip()]
            messages.append({"role": "assistant", "content": reply})
            if not codes:
                answer = reply
                break
            batch = [execute(c, ds) for c in codes]
            out.attempts += 1
            errors = [r.error for r in batch if r.error]
            results.extend(r for r in batch if not r.error)
            if errors:
                out.error = errors[0]
                messages.append({"role": "user", "content": correction_request(errors[0])})
                continue
            out.error = ''
            digest = '\n\n'.join(result_digest(r, 15) for r in batch)
            messages.append({"role": "user", "content": interpretation_request(digest)})
            answer = CODE_RE.sub('', strip_thinking(model(messages, system)))
            break
    except Exception as e:
        out.error = f"{type(e).__name__}: {e}"
    out.answer = answer
    out.passed, out.detail = score(question, results, answer)
    out.seconds = time.time() - t0
    return out


def run(model_factory, seed=11, num_ctx=8192, only=None, verbose=True):
    """Run the whole question set.

    Args:
        model_factory (callable): ``question -> model`` where a model is
            ``(messages, system) -> reply``.
        seed (int): Dataset seed.
        num_ctx (int): Context window given to the prompts.
        only (list): Question ids to run, all by default.
        verbose (bool): Print each outcome as it finishes.

    Returns:
        list: :class:`Outcome` per question.
    """
    dc, truth, limits = make_dataset(seed)
    ds = Dataset(dc)
    ds.set_limits(limits)
    outcomes = []
    for q in build_questions(dc, truth):
        if only and q.qid not in only:
            continue
        o = ask(q, ds, model_factory(q), num_ctx)
        outcomes.append(o)
        if verbose:
            mark = 'PASS' if o.passed else 'FAIL'
            print(f"{mark}  {o.qid:<14} {o.seconds:6.1f}s  attempts={o.attempts}  {o.detail}"
                  + (f"  [{o.error.splitlines()[0][:80]}]" if o.error else ''), flush=True)
    if verbose and outcomes:
        n = sum(o.passed for o in outcomes)
        print(f"\n{n}/{len(outcomes)} passed ({100.0 * n / len(outcomes):.0f}%), "
              f"mean {np.mean([o.seconds for o in outcomes]):.1f}s per question, "
              f"{sum(o.attempts > 1 for o in outcomes)} needed a correction.")
    return outcomes


def main(argv=None):
    """Command-line entry point."""
    ap = argparse.ArgumentParser(description="Score a model on the AI assistant benchmark.")
    ap.add_argument('--backend', default='ollama', choices=['ollama', 'mlx', 'custom'])
    ap.add_argument('--model', default='')
    ap.add_argument('--host', default='')
    ap.add_argument('--api-key', default='')
    ap.add_argument('--num-ctx', type=int, default=8192)
    ap.add_argument('--temperature', type=float, default=0.2)
    ap.add_argument('--seed', type=int, default=11)
    ap.add_argument('--only', nargs='*', default=None, help="question ids to run")
    ap.add_argument('--reference', action='store_true', help="answer with the reference code")
    ap.add_argument('--out', default='', help="save the outcomes as JSON")
    args = ap.parse_args(argv)
    if args.reference:
        factory = reference_model
    else:
        cfg = {'backend': args.backend, 'model': args.model, 'host': args.host, 'api_key': args.api_key,
               'num_ctx': args.num_ctx, 'temperature': args.temperature}
        factory = lambda q: (lambda messages, system: complete(cfg, messages, system))
    outcomes = run(factory, args.seed, args.num_ctx, args.only)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump({'model': args.model or ('reference' if args.reference else ''),
                       'backend': args.backend, 'num_ctx': args.num_ctx, 'seed': args.seed,
                       'outcomes': [asdict(o) for o in outcomes]}, f, indent=2)
    return 0 if all(o.passed for o in outcomes) else 1


if __name__ == '__main__':
    sys.exit(main())
