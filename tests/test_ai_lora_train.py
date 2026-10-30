# -*- coding: utf-8 -*-
"""Tests for the memory-safe LoRA launcher of Qwen3.5-family models.

Skipped where MLX is not installed. The chunked gated-delta loop must give
the same values and gradients as mlx-lm's own loop, and after training mode
is switched on only the trained layers may stay on the slow path. The
answer-only loss must equal mlx-lm's, and mlx-lm's own trainer must run
through the launcher.
"""
import pytest

mx = pytest.importorskip("mlx.core")
pytest.importorskip("mlx_lm")
import mlx.nn as nn
from mlx.utils import tree_flatten
from mlx_lm.models import gated_delta as gd
from mlx_lm.models import qwen3_5 as Q
from mlx_lm.tuner.utils import linear_to_lora_layers

from results.ai import lora_train as LT

ORIGINAL = gd.gated_delta_ops

TEXT = dict(model_type='qwen3_5_text', hidden_size=64, intermediate_size=128, num_hidden_layers=8,
            num_attention_heads=4, num_key_value_heads=2, vocab_size=100, linear_num_value_heads=4,
            linear_num_key_heads=2, linear_key_head_dim=32, linear_value_head_dim=32, head_dim=16,
            full_attention_interval=4)


@pytest.mark.parametrize('T, Hk, Hv, Dv, vec, masked, chunk', [
    (150, 2, 4, 32, False, False, 64), (97, 2, 2, 16, True, True, 16), (64, 1, 2, 32, False, False, 64)])
def test_chunked_loop_matches_the_original(T, Hk, Hv, Dv, vec, masked, chunk):
    """Same output, state and gradients as mlx-lm's loop, with or without a mask."""
    mx.random.seed(0)
    q = mx.random.normal((1, T, Hk, 32)) * 0.3
    k = mx.random.normal((1, T, Hk, 32)) * 0.3
    v = mx.random.normal((1, T, Hv, Dv))
    g = mx.sigmoid(mx.random.normal((1, T, Hv, 32) if vec else (1, T, Hv)))
    beta = mx.sigmoid(mx.random.normal((1, T, Hv)))
    m = (mx.random.uniform(shape=(1, T)) > 0.2) if masked else None

    def loss(fn, *x):
        """Sum of squared outputs plus the final state."""
        y, s = fn(*x, None, m) if fn is ORIGINAL else fn(*x, None, m, chunk=chunk)
        return (y * y).sum() + s.sum()

    a, ga = mx.value_and_grad(lambda *x: loss(ORIGINAL, *x), argnums=(0, 1, 2, 3, 4))(q, k, v, g, beta)
    b, gb = mx.value_and_grad(lambda *x: loss(LT.chunked_gated_delta_ops, *x), argnums=(0, 1, 2, 3, 4))(
        q, k, v, g, beta)
    assert float(a) == pytest.approx(float(b), rel=1e-6)
    for x, y in zip(ga, gb):
        assert float(mx.abs(x - y).max()) <= 1e-5 * (float(mx.abs(x).max()) + 1e-6)


def _model():
    """A tiny Qwen3.5 model with LoRA on its last three layers."""
    mx.random.seed(1)
    model = Q.Model(Q.ModelArgs.from_dict({'model_type': 'qwen3_5', 'text_config': TEXT}))
    model.freeze()
    for layer in model.layers[-3:]:
        layer.unfreeze()
    linear_to_lora_layers(model, 3, {'rank': 4, 'scale': 10.0, 'dropout': 0.0})
    return model


def _modes(model):
    """Training flag of each layer's linear-attention block, None for attention layers."""
    return [l.linear_attn.training if hasattr(l, 'linear_attn') else None for l in model.layers]


def test_only_trained_layers_stay_on_the_slow_path():
    """Frozen linear-attention blocks go back to inference mode, also after evaluate-then-train."""
    seen = {}

    def fake_trainer(model, *args, **kwargs):
        """Switch modes the way mlx-lm's trainer does and record them."""
        model.train()
        seen['train'] = _modes(model)
        model.eval()
        model.train()
        seen['again'] = _modes(model)
        return 'ok'

    assert LT._wrap_train(fake_trainer)(_model()) == 'ok'
    expected = [False, False, False, None, False, True, True, None]
    assert seen['train'] == expected and seen['again'] == expected


def test_training_loss_and_gradients_are_unchanged():
    """With both changes installed the LoRA loss and gradients match plain mlx-lm.

    On a GPU the frozen layers run the Metal kernel instead of the token loop,
    which rounds differently, so the match is to float32 rounding, not exact.
    """
    x = mx.random.randint(0, 100, (1, 200))

    def loss(model, x):
        """Next-token cross-entropy."""
        return nn.losses.cross_entropy(model(x[:, :-1]), x[:, 1:]).mean()

    base = _model()
    base.train()
    gd.gated_delta_ops = ORIGINAL
    l0, g0 = nn.value_and_grad(base, loss)(base, x)
    try:
        gd.gated_delta_ops = LT.chunked_gated_delta_ops
        model = _model()
        model.train()
        assert LT.keep_frozen_fast(model) == 4
        l1, g1 = nn.value_and_grad(model, loss)(model, x)
    finally:
        gd.gated_delta_ops = ORIGINAL
    assert float(l0) == pytest.approx(float(l1), rel=1e-4)
    a = mx.concatenate([v.reshape(-1) for _, v in tree_flatten(g0)])
    b = mx.concatenate([v.reshape(-1) for _, v in tree_flatten(g1)])
    assert float(mx.linalg.norm(a - b) / mx.linalg.norm(a)) < 1e-2


def test_lean_loss_matches_mlx_lm_loss():
    """Scoring only the answer span gives the same loss and gradients as mlx-lm's default loss."""
    from mlx_lm.tuner.trainer import default_loss
    batch = mx.random.randint(0, 100, (2, 120))
    lengths = mx.array([[40, 110], [0, 95]])
    model = _model()
    model.train()
    (l0, n0), g0 = nn.value_and_grad(model, default_loss)(model, batch, lengths)
    (l1, n1), g1 = nn.value_and_grad(model, LT.lean_loss)(model, batch, lengths)
    assert int(n0) == int(n1)
    assert float(l0) == pytest.approx(float(l1), rel=1e-5)
    a = mx.concatenate([v.reshape(-1) for _, v in tree_flatten(g0)])
    b = mx.concatenate([v.reshape(-1) for _, v in tree_flatten(g1)])
    assert float(mx.linalg.norm(a - b) / mx.linalg.norm(a)) < 1e-3


def test_mlx_lm_trainer_runs_through_the_launcher(tmp_path):
    """mlx-lm's own trainer runs a few steps with all changes installed and the loss goes down."""
    import mlx.optimizers as optim
    from mlx_lm.tuner import trainer as T
    original_ops, original_mx = gd.gated_delta_ops, T.mx
    try:
        gd.gated_delta_ops = LT.chunked_gated_delta_ops
        T.mx = LT._NoCompile(original_mx)
        model = _model()
        mx.random.seed(3)
        data = [(mx.random.randint(0, 100, (150,)).tolist(), 60) for _ in range(4)]
        losses = []

        class Record(T.TrainingCallback):
            """Keep the reported training losses."""

            def on_train_loss_report(self, info):
                """Remember one report."""
                losses.append(info['train_loss'])

        args = T.TrainingArgs(batch_size=1, iters=24, val_batches=1, steps_per_report=8,
                              steps_per_eval=1000, steps_per_save=1000, max_seq_length=256,
                              adapter_file=str(tmp_path / 'adapters.safetensors'))
        LT._wrap_train(T.train)(model=model, optimizer=optim.Adam(learning_rate=1e-2),
                                train_dataset=data, val_dataset=data, args=args, training_callback=Record())
    finally:
        gd.gated_delta_ops, T.mx = original_ops, original_mx
    assert len(losses) == 3 and losses[-1] < losses[0]
    assert _modes(model) == [False, False, False, None, False, True, True, None]


def test_probe_measures_one_training_step(tmp_path, monkeypatch, capsys):
    """The memory probe runs one LoRA step and reports peak memory and speed as JSON."""
    import json

    import mlx_lm.utils as U
    cfg = tmp_path / 'cfg.yaml'
    cfg.write_text("model: tiny\nnum_layers: 3\nlora_parameters:\n  rank: 4\n  scale: 10.0\n  dropout: 0.0\n")

    def tiny_load(path, *a, **k):
        """The tiny model in place of the real one."""
        mx.random.seed(1)
        return Q.Model(Q.ModelArgs.from_dict({'model_type': 'qwen3_5', 'text_config': TEXT})), None

    monkeypatch.setattr(U, 'load', tiny_load)
    original = gd.gated_delta_ops
    try:
        LT._probe_one(str(cfg), 96, 0, 0.3)
    finally:
        gd.gated_delta_ops = original
    res = json.loads([ln for ln in capsys.readouterr().out.splitlines() if ln.startswith('{')][-1])
    assert res['ok'] and res['length'] == 96 and res['layers'] == 3
    assert res['peak_gb'] >= 0 and res['tok_per_s'] > 0


class _Tok:
    """A stand-in tokenizer: one token per word, plus 3 per message and 2 for a generation prompt."""

    def apply_chat_template(self, messages, tools=None, add_generation_prompt=False, return_dict=False):
        """Count tokens the way a chat template would, roughly."""
        n = sum(3 + len(m['content'].split()) for m in messages) + (2 if add_generation_prompt else 0)
        return list(range(n))


def test_filter_keeps_examples_that_fit_with_their_answer(tmp_path):
    """Examples over the limit are left out, and the new config trains on what is left."""
    import json

    import yaml
    data = tmp_path / 'data'
    data.mkdir()
    rows = [{'messages': [{'role': 'user', 'content': 'w ' * n}, {'role': 'assistant', 'content': 'a b c'}]}
            for n in (10, 40, 80, 5)]
    (data / 'train.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    (data / 'valid.jsonl').write_text(json.dumps(rows[0]) + '\n')
    cfg = tmp_path / 'cfg.yaml'
    cfg.write_text(yaml.safe_dump({'model': 'm', 'data': str(data), 'num_layers': 4, 'iters': 1}))
    out = LT.filter_data(str(cfg), 50, str(tmp_path / 'new.yaml'), epochs=2, tokenizer=_Tok())
    assert out['train'] == {'kept': 3, 'dropped': 1, 'longest': 49}
    new = yaml.safe_load((tmp_path / 'new.yaml').read_text())
    assert new['iters'] == 6 and new['max_seq_length'] == 50 and new['data'].endswith('data50')
    assert new['grad_checkpoint'] is False and new['num_layers'] == 4
    assert LT.example_tokens(_Tok(), rows[0]) == (19, 15)


def test_loss_is_zero_when_the_answer_was_cut_off():
    """An example truncated before its answer gives a zero loss instead of an error."""
    model = _model()
    model.train()
    batch = mx.random.randint(0, 100, (1, 64))
    loss, ntoks = LT.lean_loss(model, batch, mx.array([[80, 63]]))
    assert int(ntoks) == 0 and float(loss) == 0.0
