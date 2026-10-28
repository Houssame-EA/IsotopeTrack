"""LoRA training of Qwen3.5-family models with mlx-lm in a fraction of the memory.

In training mode mlx-lm runs the gated-delta (linear attention) layers of
Qwen3.5 / Qwen3.8 as a Python loop over the tokens, keeping every
intermediate state for the backward pass: about 10 MB per token and layer,
so even a 4096-token example needs hundreds of GB. Two changes, applied
before handing over to ``mlx_lm.lora``, bring that down to a few GB:

* Frozen layers are put back in inference mode after the trainer switches
  the model to training mode, so they use the fast Metal kernel. No gradient
  flows through them, so they never need the slow path.
* In the layers being trained, the token loop runs in chunks wrapped in
  ``mx.checkpoint``: only the state at each chunk boundary is kept and the
  steps inside a chunk are recomputed during the backward pass.
* The training step is not compiled. mlx-lm compiles it with ``mx.compile``,
  which would trace the whole token loop into one graph and can undo the
  recomputation above.
* The loss computes vocabulary scores only for the answer tokens. mlx-lm
  scores every token and masks the prompt out afterwards; with a vocabulary
  of about 248 000 that is several GB per example for nothing.

The loss and its gradients are the same; only memory and speed change.

Run it exactly like ``mlx_lm.lora``::

    python3 -m results.ai.lora_train --config ~/Desktop/ai_bench/train3/lora_config.yaml

To keep only the examples that fit, counted exactly as mlx-lm counts them
(same tokenizer and chat formatting, answer still inside the limit), and
write the matching config::

    python3 -m results.ai.lora_train --filter CONFIG --max-tokens 8192 --out-config NEW_CONFIG

To measure what one training step needs before a long run, ``--probe``
runs a single step per length, each in its own process, and prints the peak
memory and time::

    python3 -m results.ai.lora_train --probe CONFIG --lengths 1024 2048 4096 --layers 8
"""
from __future__ import annotations

import sys

CHUNK = 64
"""Tokens per recomputed chunk of the gated-delta loop."""

_CHECKPOINTED = {}


def _steps(q, k, v, g, beta, state, mask=None):
    """Run the reference gated-delta step over every token of one chunk.

    Args:
        q, k: ``[B, T, H, Dk]``, already repeated to the value heads.
        v: ``[B, T, H, Dv]``.
        g: ``[B, T, H]`` or ``[B, T, H, Dk]``.
        beta: ``[B, T, H]``.
        state: ``[B, H, Dv, Dk]``.
        mask: ``[B, T]`` or ``None``.

    Returns:
        tuple: ``(y [B, T, H, Dv], state)``.
    """
    import mlx.core as mx
    from mlx_lm.models.gated_delta import _gated_delta_step_ops
    ys = []
    for t in range(q.shape[1]):
        y, state = _gated_delta_step_ops(q[:, t], k[:, t], v[:, t], g[:, t], beta[:, t], state,
                                         None if mask is None else mask[:, t])
        ys.append(y)
    return mx.stack(ys, axis=1), state


def _checkpointed(masked):
    """The chunk function wrapped in ``mx.checkpoint``, built once per kind."""
    import mlx.core as mx
    if masked not in _CHECKPOINTED:
        if masked:
            _CHECKPOINTED[masked] = mx.checkpoint(lambda q, k, v, g, b, s, m: _steps(q, k, v, g, b, s, m))
        else:
            _CHECKPOINTED[masked] = mx.checkpoint(lambda q, k, v, g, b, s: _steps(q, k, v, g, b, s))
    return _CHECKPOINTED[masked]


def chunked_gated_delta_ops(q, k, v, g, beta, state=None, mask=None, chunk=None):
    """Drop-in for ``mlx_lm.models.gated_delta.gated_delta_ops`` that keeps one state per chunk.

    Args:
        q, k: ``[B, T, Hk, Dk]``.
        v: ``[B, T, Hv, Dv]``.
        g: ``[B, T, Hv]`` or ``[B, T, Hv, Dk]``.
        beta: ``[B, T, Hv]``.
        state: ``[B, Hv, Dv, Dk]`` or ``None``.
        mask: ``[B, T]`` or ``None``.
        chunk (int): Tokens per recomputed chunk, :data:`CHUNK` by default.

    Returns:
        tuple: ``(y [B, T, Hv, Dv], state)``, the same values as the original.
    """
    import mlx.core as mx
    chunk = int(chunk or CHUNK)
    B, T, Hk, Dk = q.shape
    Hv, Dv = v.shape[-2:]
    if state is None:
        state = mx.zeros((B, Hv, Dv, Dk), dtype=mx.float32)
    if (repeat := Hv // Hk) > 1:
        q = mx.repeat(q, repeat, -2)
        k = mx.repeat(k, repeat, -2)
    ys = []
    for s in range(0, T, chunk):
        e = min(T, s + chunk)
        parts = (q[:, s:e], k[:, s:e], v[:, s:e], g[:, s:e], beta[:, s:e], state)
        if mask is None:
            y, state = _checkpointed(False)(*parts)
        else:
            y, state = _checkpointed(True)(*parts, mask[:, s:e])
        ys.append(y)
    return mx.concatenate(ys, axis=1), state


def lean_loss(model, batch, lengths):
    """Next-token loss scored only on the answer tokens, same value as mlx-lm's ``default_loss``.

    ``lengths`` holds, per row, the first and last scored position (1-based),
    as built by mlx-lm's batch iterator. Hidden states are computed for every
    token, but the vocabulary projection only for the scored span.

    Args:
        model: The mlx-lm model.
        batch: ``[B, T]`` token ids.
        lengths: ``[B, 2]`` scored span per row.

    Returns:
        tuple: ``(mean loss, number of scored tokens)``.
    """
    import mlx.core as mx
    import mlx.nn as nn
    lm = getattr(model, 'language_model', None)
    if lm is None or not hasattr(lm, 'model'):
        from mlx_lm.tuner.trainer import default_loss
        return default_loss(model, batch, lengths)
    inputs, targets = batch[:, :-1], batch[:, 1:]
    start = max(int(lengths[:, 0].min().item()) - 1, 0)
    end = min(int(lengths[:, 1].max().item()), targets.shape[1])
    if end <= start:
        start = max(end - 1, 0)
    hidden = lm.model(inputs)[:, start:end]
    if getattr(lm.args, 'tie_word_embeddings', False):
        logits = lm.model.embed_tokens.as_linear(hidden)
    else:
        logits = lm.lm_head(hidden)
    steps = mx.arange(start + 1, end + 1)
    mask = mx.logical_and(steps >= lengths[:, 0:1], steps <= lengths[:, 1:])
    ce = nn.losses.cross_entropy(logits, targets[:, start:end]) * mask
    ntoks = mask.sum()
    return ce.astype(mx.float32).sum() / mx.maximum(ntoks, 1), ntoks


class _NoCompile:
    """Stands in for ``mlx.core`` inside mlx-lm's trainer, with ``compile`` doing nothing."""

    def __init__(self, mx):
        """Wrap the real module."""
        self._mx = mx

    def __getattr__(self, name):
        """Everything but ``compile`` comes from the real module."""
        return getattr(self._mx, name)

    @staticmethod
    def compile(fun=None, **kwargs):
        """Return the function itself instead of a compiled version."""
        if fun is None:
            return lambda f: f
        return fun


def has_trainable(module):
    """Whether a module holds any trainable parameter."""
    from mlx.utils import tree_flatten
    return bool(tree_flatten(module.trainable_parameters()))


def keep_frozen_fast(model):
    """Put the linear-attention blocks of untrained layers back in inference mode.

    Args:
        model: The mlx-lm model, after LoRA layers were added.

    Returns:
        int: How many blocks were switched.
    """
    switched = 0
    for layer in getattr(model, 'layers', []):
        block = getattr(layer, 'linear_attn', None)
        if block is not None and not has_trainable(layer):
            block.train(False)
            switched += 1
    return switched


def _wrap_train(original):
    """Wrap ``mlx_lm`` 's ``train`` so every switch to training mode keeps frozen layers fast."""
    def train(model, *args, **kwargs):
        """Run the original trainer with the frozen-layer fix applied to ``model.train``."""
        base = model.train

        def train_mode(mode=True):
            """Switch modes, then keep frozen linear-attention blocks in inference mode."""
            out = base(mode)
            if mode:
                keep_frozen_fast(model)
            return out if out is not None else model

        model.train = train_mode
        kwargs.setdefault('loss', lean_loss)
        n = keep_frozen_fast(model)
        print(f"[lora_train] {n} frozen linear-attention blocks use the fast kernel; "
              f"trained ones recompute in chunks of {CHUNK} tokens.", flush=True)
        return original(model, *args, **kwargs)
    return train


def install():
    """Apply both changes to the imported mlx-lm modules."""
    import mlx.core as mx
    import mlx_lm.lora as lora
    from mlx_lm.models import gated_delta
    from mlx_lm.tuner import trainer
    gated_delta.gated_delta_ops = chunked_gated_delta_ops
    if not isinstance(trainer.mx, _NoCompile):
        trainer.mx = _NoCompile(mx)
    if not getattr(lora.train, '_itk_wrapped', False):
        wrapped = _wrap_train(lora.train)
        wrapped._itk_wrapped = True
        lora.train = wrapped


def example_tokens(tokenizer, example):
    """Tokens and answer offset of one chat example, computed as mlx-lm's ``ChatDataset`` does.

    Args:
        tokenizer: The mlx-lm tokenizer.
        example (dict): ``{"messages": [...]}``.

    Returns:
        tuple: ``(number of tokens, offset of the answer)``.
    """
    messages = example['messages']
    tools = example.get('tools')
    tokens = tokenizer.apply_chat_template(messages, tools=tools, return_dict=False)
    add_prompt = messages[-1].get('role') == 'assistant'
    offset = tokenizer.apply_chat_template(messages[:-1], tools=tools, add_generation_prompt=add_prompt,
                                           return_dict=False)
    return len(tokens), len(offset)


def filter_split(src, dst, tokenizer, max_tokens):
    """Copy the examples of one JSONL file that fit within *max_tokens* with their answer.

    Args:
        src (str): Source JSONL.
        dst (str): Destination JSONL.
        tokenizer: The mlx-lm tokenizer.
        max_tokens (int): Longest example kept.

    Returns:
        dict: ``kept``, ``dropped`` and the ``longest`` kept length.
    """
    import json
    kept = dropped = longest = 0
    with open(src, encoding='utf-8') as fin, open(dst, 'w', encoding='utf-8') as fout:
        for line in fin:
            if not line.strip():
                continue
            n, offset = example_tokens(tokenizer, json.loads(line))
            if n <= max_tokens and offset < n:
                fout.write(line if line.endswith('\n') else line + '\n')
                kept += 1
                longest = max(longest, n)
            else:
                dropped += 1
    return {'kept': kept, 'dropped': dropped, 'longest': longest}


def filter_data(config, max_tokens, out_config, epochs=2, tokenizer=None):
    """Write a dataset of the examples that fit and a config that trains on it.

    The new data goes next to the old one as ``data<max_tokens>``; the new
    config points to it, sets ``max_seq_length`` to *max_tokens* and sets
    ``iters`` to *epochs* passes over the kept training examples.

    Args:
        config (str): The current LoRA config.
        max_tokens (int): Longest example kept.
        out_config (str): Where to write the new config.
        epochs (int): Passes over the training examples.
        tokenizer: Tokenizer to use, loaded from the config's model when omitted.

    Returns:
        dict: Per split counts, and ``iters``.
    """
    import os

    import yaml
    with open(config) as fh:
        cfg = yaml.safe_load(fh)
    if tokenizer is None:
        from pathlib import Path

        from mlx_lm.utils import load_tokenizer
        tokenizer = load_tokenizer(Path(cfg['model']))
    src = cfg['data']
    dst = os.path.join(os.path.dirname(os.path.normpath(src)), f"data{int(max_tokens)}")
    os.makedirs(dst, exist_ok=True)
    out = {}
    for split in ('train', 'valid'):
        path = os.path.join(src, f'{split}.jsonl')
        if os.path.exists(path):
            out[split] = filter_split(path, os.path.join(dst, f'{split}.jsonl'), tokenizer, int(max_tokens))
            print(f"{split}: kept {out[split]['kept']}, left out {out[split]['dropped']}, "
                  f"longest kept {out[split]['longest']} tokens", flush=True)
    cfg.update(data=dst, max_seq_length=int(max_tokens), grad_checkpoint=False,
               iters=int(epochs) * max(1, out.get('train', {}).get('kept', 0)))
    with open(out_config, 'w') as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False)
    out['iters'] = cfg['iters']
    print(f"config: {out_config} ({cfg['iters']} iterations, {cfg.get('num_layers')} layers)", flush=True)
    return out


def _probe_one(config, length, layers, answer):
    """Run one training step of *length* tokens and print peak memory and time as one line.

    Args:
        config (str): The LoRA config file (model, lora_parameters, num_layers).
        length (int): Tokens in the synthetic example.
        layers (int): Layers to train, the config's value when 0.
        answer (float): Share of the example scored as the answer.
    """
    import json
    import time

    import mlx.core as mx
    import mlx.nn as nn
    import yaml
    from mlx_lm.tuner.utils import linear_to_lora_layers
    from mlx_lm.utils import load

    with open(config) as fh:
        cfg = yaml.safe_load(fh)
    n = int(layers or cfg.get('num_layers', 8))
    install()
    model, _ = load(cfg['model'])
    model.freeze()
    linear_to_lora_layers(model, n, cfg.get('lora_parameters') or {'rank': 16, 'scale': 20.0, 'dropout': 0.0})
    model.train()
    keep_frozen_fast(model)
    mx.random.seed(0)
    batch = mx.random.randint(0, 1000, (1, length + 1))
    lengths = mx.array([[max(1, int(length * (1 - answer))), length]])
    step = nn.value_and_grad(model, lean_loss)
    mx.eval(model.parameters())
    base = mx.get_active_memory()
    mx.reset_peak_memory()
    tic = time.perf_counter()
    (loss, ntoks), grads = step(model, batch, lengths)
    mx.eval(loss, grads)
    sec = time.perf_counter() - tic
    print(json.dumps({'length': length, 'layers': n, 'ok': True,
                      'weights_gb': round(base / 1e9, 1), 'peak_gb': round(mx.get_peak_memory() / 1e9, 1),
                      'seconds': round(sec, 1), 'tok_per_s': round(length / sec, 1)}), flush=True)


def probe(config, lengths, layers=0, answer=0.3):
    """Measure one training step per length, each in a fresh process, and print a table.

    Args:
        config (str): The LoRA config file.
        lengths (list): Example lengths in tokens.
        layers (int): Layers to train, the config's value when 0.
        answer (float): Share of each example scored as the answer.

    Returns:
        list: One result dict per length.
    """
    import json
    import subprocess
    out = []
    for length in lengths:
        cmd = [sys.executable, '-m', 'results.ai.lora_train', '--probe-one', str(config),
               str(length), str(layers), str(answer)]
        run = subprocess.run(cmd, capture_output=True, text=True)
        line = next((ln for ln in run.stdout.splitlines() if ln.startswith('{')), '')
        if line:
            res = json.loads(line)
        else:
            err = [ln for ln in (run.stderr or '').splitlines() if 'Error' in ln]
            res = {'length': length, 'ok': False, 'error': (err[-1] if err else 'failed')[-160:]}
        out.append(res)
        if res.get('ok'):
            print(f"{length:>6} tokens, {res['layers']} layers: peak {res['peak_gb']} GB "
                  f"(weights {res['weights_gb']} GB), {res['seconds']} s, {res['tok_per_s']} tok/s", flush=True)
        else:
            print(f"{length:>6} tokens: FAILED - {res['error']}", flush=True)
    return out


def main(argv=None):
    """Install the changes and run ``mlx_lm.lora`` with the given arguments, or a memory probe."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ['--probe-one']:
        _probe_one(args[1], int(args[2]), int(args[3]), float(args[4]))
        return 0
    if args[:1] == ['--filter']:
        import argparse
        ap = argparse.ArgumentParser(prog='lora_train --filter')
        ap.add_argument('config')
        ap.add_argument('--max-tokens', type=int, default=8192)
        ap.add_argument('--out-config', required=True)
        ap.add_argument('--epochs', type=int, default=2)
        p = ap.parse_args(args[1:])
        filter_data(p.config, p.max_tokens, p.out_config, p.epochs)
        return 0
    if args[:1] == ['--probe']:
        import argparse
        ap = argparse.ArgumentParser(prog='lora_train --probe')
        ap.add_argument('config')
        ap.add_argument('--lengths', type=int, nargs='+', default=[1024, 2048, 4096, 8192])
        ap.add_argument('--layers', type=int, default=0)
        ap.add_argument('--answer', type=float, default=0.3)
        p = ap.parse_args(args[1:])
        probe(p.config, p.lengths, p.layers, p.answer)
        return 0
    install()
    import mlx_lm.lora as lora
    sys.argv = ['mlx_lm.lora'] + args
    return lora.main()


if __name__ == '__main__':
    sys.exit(main())
