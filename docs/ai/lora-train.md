# `lora_train.py`

LoRA training of Qwen3.5-family models with mlx-lm in a fraction of the memory.

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

---

## Constants

| Name | Value |
|------|-------|
| `CHUNK` | `64` |
| `_CHECKPOINTED` | `{}` |

## Classes

### `_NoCompile`

Stands in for ``mlx.core`` inside mlx-lm's trainer, with ``compile`` doing nothing.

| Method | Signature | Description |
|--------|-----------|-------------|
| `__init__` | `(self, mx)` | Wrap the real module. |
| `__getattr__` | `(self, name)` | Everything but ``compile`` comes from the real module. |
| `compile` | `(fun=None, **kwargs)` | Return the function itself instead of a compiled version. |

## Functions

| Function | Signature | Description |
|----------|-----------|-------------|
| `_steps` | `(q, k, v, g, beta, state, mask=None)` | Run the reference gated-delta step over every token of one chunk. |
| `_checkpointed` | `(masked)` | The chunk function wrapped in ``mx.checkpoint``, built once per kind. |
| `chunked_gated_delta_ops` | `(q, k, v, g, beta, state=None, mask=None, chunk=None)` | Drop-in for ``mlx_lm.models.gated_delta.gated_delta_ops`` that keeps one state per chunk. |
| `lean_loss` | `(model, batch, lengths)` | Next-token loss scored only on the answer tokens, same value as mlx-lm's ``default_loss``. |
| `has_trainable` | `(module)` | Whether a module holds any trainable parameter. |
| `keep_frozen_fast` | `(model)` | Put the linear-attention blocks of untrained layers back in inference mode. |
| `_wrap_train` | `(original)` | Wrap ``mlx_lm`` 's ``train`` so every switch to training mode keeps frozen layers fast. |
| `install` | `()` | Apply both changes to the imported mlx-lm modules. |
| `example_tokens` | `(tokenizer, example)` | Tokens and answer offset of one chat example, computed as mlx-lm's ``ChatDataset`` does. |
| `filter_split` | `(src, dst, tokenizer, max_tokens)` | Copy the examples of one JSONL file that fit within *max_tokens* with their answer. |
| `filter_data` | `(config, max_tokens, out_config, epochs=2, tokenizer=None)` | Write a dataset of the examples that fit and a config that trains on it. |
| `_probe_one` | `(config, length, layers, answer)` | Run one training step of *length* tokens and print peak memory and time as one line. |
| `probe` | `(config, lengths, layers=0, answer=0.3)` | Measure one training step per length, each in a fresh process, and print a table. |
| `main` | `(argv=None)` | Install the changes and run ``mlx_lm.lora`` with the given arguments, or a memory probe. |
