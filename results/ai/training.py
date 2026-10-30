"""Training data for fine-tuning the assistant's model on IsotopeTrack work.

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
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from dataclasses import replace

import numpy as np

from results.ai.benchmark import ask, build_questions, build_variant, complete, reference_model
from results.ai.data import Dataset
from results.ai.prompts import EMPTY_PREFIX, NO_CODE_PREFIX, estimate_tokens
from results.ai.sandbox import floats_in_text, unverified_numbers
from results.ai.theme import cut_after_code, strip_thinking

HELDOUT_TEMPLATES = frozenset({
    'count_above', 'p90_ce', 'ti_differ', 'fig_ecdf', 'fig_annotate', 'table_pct',
    'edit_bars', 'explore_compare',
})

FIX_PREFIXES = ('[SANDBOX ERROR]', '[FIGURE CHECK]', NO_CODE_PREFIX, EMPTY_PREFIX, 'Write one line naming the hypothesis')
TAKEAWAY_PREFIX = 'Here are the EXACT results your code just produced:'
ELEMENT_WORDS = {'Ti': 'titanium', 'Fe': 'iron', 'Ce': 'cerium', 'La': 'lanthanum',
                 'Ag': 'silver', 'Au': 'gold', 'Al': 'aluminium'}

PARAPHRASE_SYSTEM = (
    "You rewrite questions that scientists type into a data-analysis assistant. Rewrite the question "
    "in different words, the way a researcher in a lab might type it: sometimes shorter, sometimes more "
    "casual, sometimes more formal. Keep every sample name, element, number, unit and plotting request "
    "exactly. Reply with the rewritten question only.")


def _letters(n):
    """Sample suffixes A, B, C, ..."""
    return [chr(65 + i) for i in range(n)]


def sample_names(rng, n):
    """Pick a naming style and return *n* sample names in it.

    The styles cover what labs actually type, so the model does not tie its
    answers to one naming habit. None of them resembles the held-out lakes.

    Args:
        rng (numpy.random.Generator): Random source.
        n (int): Number of samples.

    Returns:
        list: Unique sample names.
    """
    site = int(rng.integers(1, 9))
    dil = int(rng.choice([5, 10, 20, 50]))
    styles = [
        lambda: [f"River_{x}" for x in _letters(n)],
        lambda: [f"Site{i + 1}" for i in range(n)],
        lambda: [f"S{i + 1}" for i in range(n)],
        lambda: [f"Tap_{i + 1}" for i in range(n)],
        lambda: [f"Sea_{x}" for x in _letters(n)],
        lambda: [f"Soil_extract_{i + 1}" for i in range(n)],
        lambda: [f"{k}_Day{d}" for d in range(1, n // 2 + 2) for k in ('Influent', 'Effluent')][:n],
        lambda: [f"WWTP{site}_{k}_{d}" for d in range(1, n // 2 + 2) for k in ('INF', 'EFF')][:n],
        lambda: [f"S{site}-{k}-{d} {dil}x" for d in range(1, n // 2 + 2) for k in ('INF', 'EFF')][:n],
        lambda: ['Control'] + [f"Treated_{i}" for i in range(1, n)],
        lambda: [f"Well_{x}{i}" for i, x in zip(range(1, n + 1), _letters(n))],
        lambda: [f"Sample {i + 1}" for i in range(n)],
    ]
    return styles[int(rng.integers(len(styles)))]()


def random_spec(seed):
    """A random dataset specification with one clearly larger Ti sample.

    Args:
        seed (int): Random seed.

    Returns:
        dict: Specification for :func:`results.ai.benchmark.build_variant`.
    """
    rng = np.random.default_rng(seed)
    n = int(rng.integers(2, 7))
    names = sample_names(rng, n)
    ti = {s: float(rng.uniform(45, 75)) for s in names}
    largest = names[int(rng.integers(1, n))]
    ti[largest] = max(ti.values()) * float(rng.uniform(1.45, 2.0))
    burst_sample = names[int(rng.integers(n))]
    t0 = float(np.round(rng.uniform(6, 50), 0))
    alloy = names[int(rng.integers(n))]
    with_cela = [s for s in names if s != alloy]
    shift = with_cela[int(rng.integers(1, len(with_cela)))] if len(with_cela) > 1 else ''
    pb = names[int(rng.integers(n))]
    return {'seed': seed, 'samples': names, 'ti_median_nm': ti,
            'burst': (burst_sample, t0, t0 + 2.0), 'alloy_sample': alloy,
            'cela_shift_sample': shift, 'pb_sample': pb,
            'scale': float(np.round(rng.uniform(0.6, 1.3), 2))}


def training_questions(seed, categories=None):
    """The dataset and the training questions for one seed.

    Args:
        seed (int): Dataset seed.
        categories (list): Only these categories, all by default.

    Returns:
        tuple: ``(name, dataset, questions)``.
    """
    spec = random_spec(seed)
    name = f"train{seed}"
    dc, truth, limits = build_variant(spec)
    ds = Dataset(dc)
    ds.set_limits(limits)
    qs = []
    for q in build_questions(name, dc, truth):
        template = q.qid.split('.', 1)[1]
        if template in HELDOUT_TEMPLATES:
            continue
        if categories and q.category not in categories:
            continue
        qs.append(q)
    return name, ds, qs


class Recorder:
    """Wraps a model and keeps every request it answered, exactly as sent."""

    def __init__(self, model):
        """Wrap *model*, a ``(messages, system) -> reply`` callable."""
        self.model = model
        self.calls = []

    def __call__(self, messages, system):
        """Answer and remember the request and the reply."""
        reply = self.model(messages, system)
        self.calls.append({'system': system, 'messages': [dict(m) for m in messages],
                           'reply': strip_thinking(reply or '').strip()})
        return reply


def keep_calls(calls):
    """The replies worth learning from in one verified-correct conversation.

    A reply is dropped when the next request sent it back for a fix (its
    code crashed, its figure failed the checks, it quoted results without
    running code, or it wrote no code during an exploration), and a
    takeaway is dropped when it quotes a decimal number that the results it
    was shown do not contain.

    Args:
        calls (list): Recorded calls in order.

    Returns:
        list: The calls to keep.
    """
    keep = []
    for k, call in enumerate(calls):
        reply = call['reply']
        if not reply:
            continue
        if k + 1 < len(calls):
            nxt = calls[k + 1]['messages']
            if (len(nxt) >= 2 and nxt[-2].get('role') == 'assistant'
                    and _shown(nxt[-2].get('content', '')) == _shown(reply)
                    and str(nxt[-1].get('content', '')).startswith(FIX_PREFIXES)):
                continue
        last = str(call['messages'][-1].get('content', '')) if call['messages'] else ''
        if last.startswith(TAKEAWAY_PREFIX) and unverified_numbers(reply, floats_in_text(last)):
            continue
        keep.append(dict(call, reply=_tidy(reply)))
    return keep


_SHOW_RE = re.compile(r'^[ \t]*plt\.(show|tight_layout)\(\)[ \t]*\n?', re.MULTILINE)


def _shown(reply):
    """A reply as the conversation keeps it: no reasoning, nothing after the last code block."""
    return cut_after_code(strip_thinking(reply or '').strip())


def _tidy(reply):
    """Drop what the app ignores and its rules forbid, so the model does not learn it.

    That is ``plt.show()`` and ``tight_layout()`` calls and anything written
    after the last code block, where results would be guessed.
    """
    return _SHOW_RE.sub('', cut_after_code(reply))


def _protected(text, samples):
    """Words a paraphrase must keep: sample names, elements and numbers."""
    must = [s for s in samples if s in text]
    for sym, word in ELEMENT_WORDS.items():
        if re.search(rf'(?-i:\b{sym}\b)', text):
            must.append(sym)
        if re.search(rf'\b{word}\b', text, re.IGNORECASE):
            must.append(word)
    must += re.findall(r'\d+(?:\.\d+)?', ' '.join(t for t in text.split() if t not in samples))
    return must


def paraphrase(model_cfg, text, samples):
    """Ask the teacher to reword a question, keeping it only when nothing was lost.

    Args:
        model_cfg (dict): Teacher settings for :func:`results.ai.benchmark.complete`.
        text (str): The question.
        samples (list): Sample names that must survive.

    Returns:
        str: The new wording, or *text* when the rewrite dropped something.
    """
    try:
        out = strip_thinking(complete(model_cfg, [{'role': 'user', 'content': text}],
                                      PARAPHRASE_SYSTEM, timeout=120) or '').strip().strip('"')
    except Exception:
        return text
    if not out or len(out) > 3 * len(text) + 40 or '```' in out:
        return text
    low = out.lower()
    for word in _protected(text, samples):
        if word.lower() not in low:
            return text
    return out


def _reworded(question, model_cfg, samples):
    """The question with its user-facing text paraphrased by the teacher."""
    if model_cfg is None:
        return question
    if question.kind == 'conversation':
        steps = [dict(s, text=paraphrase(model_cfg, s['text'], samples)) for s in question.steps]
        return replace(question, steps=steps)
    return replace(question, text=paraphrase(model_cfg, question.text, samples))


_BACKEND_ERROR_RE = re.compile(r'HTTP|Connection|Timeout|timed out|Max retries|RemoteDisconnected|'
                               r'Broken pipe|server', re.IGNORECASE)


def is_backend_error(error):
    """Whether an error came from reaching the teacher model rather than from its code."""
    return bool(error) and bool(_BACKEND_ERROR_RE.search(str(error).split('\n', 1)[0]))


def retrying(model, attempts=3, wait_s=5.0):
    """Wrap a model so a failed request is tried again after a short wait.

    Args:
        model (callable): ``(messages, system) -> reply``.
        attempts (int): Tries in total.
        wait_s (float): Seconds before the first retry, doubled each time.

    Returns:
        callable: The same interface.
    """
    def call(messages, system):
        """Ask, retrying on any error."""
        delay = wait_s
        for k in range(attempts):
            try:
                return model(messages, system)
            except Exception:
                if k == attempts - 1:
                    raise
                time.sleep(delay)
                delay *= 2
    return call


def _done_ids(path):
    """Question ids already handled in an earlier run; a request that never reached the teacher is asked again."""
    done = set()
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get('backend_error'):
                    continue
                if 'qid' in row:
                    done.add(row['qid'])
    return done


def generate(model_factory, out_dir, n_datasets=10, start=0, categories=None, model_cfg=None,
             paraphrase_questions=True, verbose=True):
    """Put the training questions to a teacher and keep its verified-correct replies.

    Args:
        model_factory (callable): ``question -> model``; the model is
            ``(messages, system) -> reply``.
        out_dir (str): Folder for ``examples.jsonl`` and ``progress.jsonl``.
        n_datasets (int): Synthetic datasets to make.
        start (int): Index of the first dataset, to add more later.
        categories (list): Only these question categories.
        model_cfg (dict): Teacher settings, used to paraphrase questions.
        paraphrase_questions (bool): Reword each question with the teacher.
        verbose (bool): Print each question as it finishes.

    Returns:
        dict: ``questions``, ``passed`` and ``examples`` written in this run.
    """
    os.makedirs(out_dir, exist_ok=True)
    ex_path = os.path.join(out_dir, 'examples.jsonl')
    log_path = os.path.join(out_dir, 'progress.jsonl')
    done = _done_ids(log_path)
    stats = {'questions': 0, 'passed': 0, 'examples': 0}
    for i in range(start, start + n_datasets):
        seed = 1000 + i
        num_ctx = 8192 if i % 4 == 3 else 16384
        name, ds, questions = training_questions(seed, categories)
        for q in questions:
            if q.qid in done:
                continue
            asked = _reworded(q, model_cfg if paraphrase_questions else None, ds.samples)
            rec = Recorder(model_factory(asked))
            t0 = time.time()
            outcome = ask(asked, ds, rec, num_ctx)
            backend_error = is_backend_error(outcome.error) or (not rec.calls and bool(outcome.error))
            ran_code = outcome.attempts > 0
            kept = keep_calls(rec.calls) if outcome.passed and ran_code and not backend_error else []
            with open(ex_path, 'a', encoding='utf-8') as f:
                for k, call in enumerate(kept):
                    msgs = ([{'role': 'system', 'content': call['system']}] + call['messages']
                            + [{'role': 'assistant', 'content': call['reply']}])
                    f.write(json.dumps({'id': f"{q.qid}.{k}", 'dataset': name,
                                        'template': q.qid.split('.', 1)[1], 'category': q.category,
                                        'messages': msgs}, ensure_ascii=False) + '\n')
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'qid': q.qid, 'passed': outcome.passed, 'kept': len(kept),
                                    'calls': len(rec.calls), 'ran_code': ran_code, 'detail': outcome.detail,
                                    'error': (outcome.error or '')[:300], 'backend_error': backend_error,
                                    'seconds': round(time.time() - t0, 1)}) + '\n')
            stats['questions'] += 1
            stats['passed'] += int(outcome.passed)
            stats['examples'] += len(kept)
            if verbose:
                why = '' if kept else ('  [teacher not reached: ' + outcome.error.splitlines()[0][:70] + ']'
                                       if backend_error else '  [answered without code]' if outcome.passed
                                       and not ran_code else '')
                print(f"{'KEEP' if kept else 'skip'}  {q.qid:<34} {time.time() - t0:6.1f}s  "
                      f"{len(kept)}/{len(rec.calls)} replies kept  {outcome.detail[:60]}{why}", flush=True)
    if verbose:
        print(f"\n{stats['passed']}/{stats['questions']} answered correctly, "
              f"{stats['examples']} training examples written to {ex_path}")
    return stats


LORA_CONFIG = """model: {model}
train: true
data: {data}
fine_tune_type: lora
num_layers: 8
batch_size: 1
iters: {iters}
learning_rate: 1.0e-5
steps_per_report: 10
steps_per_eval: 100
val_batches: 25
save_every: 100
adapter_path: {adapters}
max_seq_length: {max_len}
grad_checkpoint: false
mask_prompt: true
lora_parameters:
  rank: 16
  scale: 20.0
  dropout: 0.05
"""


def drop_empty_retries(messages):
    """Remove empty replies and the request that asked for them again.

    Some teachers answer the first question with a call to a tool that does
    not exist, which leaves the reply empty; the conversation then asks again.
    The good reply that follows answers the original question, so the empty
    exchange is left out of the training history.

    Args:
        messages (list): Chat messages of one example.

    Returns:
        list: The messages without those pairs.
    """
    out, i = [], 0
    while i < len(messages):
        m = messages[i]
        nxt = messages[i + 1] if i + 1 < len(messages) else None
        if (m.get('role') == 'assistant' and not str(m.get('content') or '').strip() and nxt is not None
                and nxt.get('role') == 'user' and str(nxt.get('content', '')).startswith(EMPTY_PREFIX)):
            i += 2
            continue
        out.append(m)
        i += 1
    return out


def build(out_dir, model='mlx-community/Qwen3.5-9B-MLX-4bit', epochs=2, max_len=12288, valid_every=8):
    """Split the examples into training and validation files and write the LoRA config.

    Whole datasets go to validation, never single replies, so validation
    measures questions on data the model did not train on. Empty replies
    and their retry requests are left out, see :func:`drop_empty_retries`.

    Args:
        out_dir (str): Folder holding ``examples.jsonl``.
        model (str): Base model for the config.
        epochs (int): Passes over the training examples.
        max_len (int): Longest example in tokens; longer ones are dropped,
            since truncation would cut the reply being learned.
        valid_every (int): Every n-th dataset goes to validation.

    Returns:
        dict: Counts of training and validation examples and of dropped ones.
    """
    src = os.path.join(out_dir, 'examples.jsonl')
    data_dir = os.path.join(out_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    rows = []
    with open(src, encoding='utf-8') as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    datasets = sorted({r['dataset'] for r in rows})
    valid_sets = set(datasets[valid_every - 1::valid_every]) or set(datasets[-1:])
    if len(datasets) < 2:
        valid_sets = set()
    counts = {'train': 0, 'valid': 0, 'too_long': 0, 'heldout': 0}
    files = {k: open(os.path.join(data_dir, f'{k}.jsonl'), 'w', encoding='utf-8') for k in ('train', 'valid')}
    try:
        for r in rows:
            if r.get('template') in HELDOUT_TEMPLATES:
                counts['heldout'] += 1
                continue
            text = '\n'.join(str(m.get('content', '')) for m in r['messages'])
            if estimate_tokens(text) > max_len * 0.95:
                counts['too_long'] += 1
                continue
            split = 'valid' if r['dataset'] in valid_sets else 'train'
            files[split].write(json.dumps({'messages': drop_empty_retries(r['messages'])}, ensure_ascii=False) + '\n')
            counts[split] += 1
    finally:
        for f in files.values():
            f.close()
    if not counts['valid'] and counts['train']:
        with open(os.path.join(data_dir, 'train.jsonl'), encoding='utf-8') as f:
            first = f.readline()
        with open(os.path.join(data_dir, 'valid.jsonl'), 'w', encoding='utf-8') as f:
            f.write(first)
        counts['valid'] = 1
    iters = max(50, int(math.ceil(epochs * counts['train'])))
    with open(os.path.join(out_dir, 'lora_config.yaml'), 'w', encoding='utf-8') as f:
        f.write(LORA_CONFIG.format(model=model, data=data_dir, iters=iters,
                                   adapters=os.path.join(out_dir, 'adapters'), max_len=max_len))
    counts['iters'] = iters
    return counts


def main(argv=None):
    """Command-line entry point."""
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    g = sub.add_parser('generate', help="ask the teacher and keep verified-correct replies")
    g.add_argument('--backend', default='ollama', choices=['ollama', 'mlx', 'custom'])
    g.add_argument('--model', default='')
    g.add_argument('--host', default='')
    g.add_argument('--api-key', default='')
    g.add_argument('--datasets', type=int, default=10, help="synthetic datasets to make")
    g.add_argument('--start', type=int, default=0, help="index of the first dataset")
    g.add_argument('--category', nargs='*', default=None, help="only these categories")
    g.add_argument('--no-paraphrase', action='store_true', help="keep the template wording")
    g.add_argument('--num-ctx', type=int, default=16384,
                   help="context window the teacher reserves memory for; lower it if the teacher runs out of memory")
    g.add_argument('--reference', action='store_true',
                   help="use the built-in reference answers instead of a teacher (for testing only)")
    g.add_argument('--out', required=True)
    b = sub.add_parser('build', help="write train/valid files and the LoRA config")
    b.add_argument('--out', required=True)
    b.add_argument('--model', default='mlx-community/Qwen3.5-9B-MLX-4bit')
    b.add_argument('--epochs', type=int, default=2)
    b.add_argument('--max-len', type=int, default=12288)
    args = ap.parse_args(argv)
    out = os.path.expanduser(args.out)
    if args.cmd == 'build':
        counts = build(out, args.model, args.epochs, args.max_len)
        print(f"{counts['train']} training and {counts['valid']} validation examples "
              f"({counts['too_long']} too long dropped); {counts['iters']} iterations")
        print(f"Config: {os.path.join(out, 'lora_config.yaml')}")
        print(f"Train:  python3 -m results.ai.lora_train --config {os.path.join(out, 'lora_config.yaml')}")
        return 0
    if args.reference:
        factory, cfg = reference_model, None
    else:
        cfg = {'backend': args.backend, 'model': args.model, 'host': args.host, 'api_key': args.api_key,
               'num_ctx': int(args.num_ctx), 'temperature': 0.2, 'think': False}
        factory = lambda q: retrying(lambda messages, system: complete(cfg, messages, system))
    generate(factory, out, args.datasets, args.start, args.category, cfg,
             paraphrase_questions=not args.no_paraphrase and cfg is not None)
    return 0


if __name__ == '__main__':
    sys.exit(main())
