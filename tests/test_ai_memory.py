# -*- coding: utf-8 -*-
"""Tests for the memory checks: reading the RAM, sizing models, recommending one and warning.

The rules are checked on the models benchmarked for the lab: on 32 GB the
9B 4-bit is recommended, from 48 GB the 27B 4-bit, and the 4-bit model is
preferred over its 16-bit version.
"""
import json
import os

import pytest
from PySide6.QtWidgets import QApplication

import results.ai.memory as M
import results.ai.settings as S
from results.ai.servers import folder_models

GB = M.GB

MODELS = [
    {'model': 'q27-4bit', 'bytes': 15 * GB, 'quantized': True},
    {'model': 'q27-bf16', 'bytes': 51 * GB, 'quantized': False},
    {'model': 'q9-4bit', 'bytes': int(5.6 * GB), 'quantized': True},
    {'model': 'q9-bf16', 'bytes': 17 * GB, 'quantized': False},
    {'model': 'q4-bf16', 'bytes': int(7.9 * GB), 'quantized': False},
]


@pytest.mark.parametrize('ram, expected', [(16, 'q9-4bit'), (32, 'q9-4bit'), (48, 'q27-4bit'),
                                           (64, 'q27-4bit'), (128, 'q27-4bit'), (8, '')])
def test_recommendation_by_ram(ram, expected):
    """The recommended model leaves half the memory free and prefers 4-bit."""
    assert M.recommend(MODELS, ram * GB) == expected


def test_fit_levels():
    """A model too big for the computer, one that does not fit now, and one that fits."""
    assert M.fit(51 * GB, 32 * GB, 20 * GB)['level'] == 'too_big'
    tight = M.fit(15 * GB, 32 * GB, 10 * GB)
    assert tight['level'] == 'tight' and '10 GB is free' in tight['text'].replace('10.0', '10')
    assert M.fit(int(5.6 * GB), 32 * GB, 20 * GB)['level'] == 'ok'
    assert M.fit(0, 32 * GB, 20 * GB)['level'] == 'unknown'


def test_vm_stat_parsing():
    """Free, inactive, speculative and purgeable pages count as available."""
    text = ("Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
            "Pages free:                               100000.\n"
            "Pages active:                             500000.\n"
            "Pages inactive:                           200000.\n"
            "Pages speculative:                         10000.\n"
            "Pages purgeable:                            5000.\n")
    assert M.parse_vm_stat(text) == 315000 * 16384


def _model_folder(base, name, gb, quantized):
    """A fake MLX model folder with a config and a weights file of a given size."""
    path = os.path.join(base, name)
    os.makedirs(path)
    cfg = {'model_type': 'qwen3_5'}
    if quantized:
        cfg['quantization'] = {'bits': 4, 'group_size': 64}
    with open(os.path.join(path, 'config.json'), 'w') as fh:
        json.dump(cfg, fh)
    with open(os.path.join(path, 'model.safetensors'), 'wb') as fh:
        fh.truncate(int(gb * GB))
    return path


def test_model_folders_are_found_and_sized(tmp_path):
    """Models in an added folder are listed with their size and precision."""
    q27 = _model_folder(str(tmp_path), 'Qwen3.8-27B-4bit', 15, True)
    _model_folder(str(tmp_path), 'Qwen3.5-9B-bf16', 17, False)
    os.makedirs(tmp_path / 'not_a_model')
    found = folder_models([str(tmp_path)])
    assert [os.path.basename(p) for p in found] == ['Qwen3.5-9B-bf16', 'Qwen3.8-27B-4bit']
    assert M.mlx_model_folder(q27) == q27
    assert M.folder_weight_bytes(q27) == 15 * GB and M.folder_is_quantized(q27)


def test_cached_repo_is_located(tmp_path):
    """A Hugging Face repo id resolves to its snapshot in the cache."""
    snap = tmp_path / 'models--mlx-community--Qwen3.5-9B-MLX-4bit' / 'snapshots'
    os.makedirs(snap)
    path = _model_folder(str(snap), 'abc123', 0.01, True)
    assert M.mlx_model_folder('mlx-community/Qwen3.5-9B-MLX-4bit', [str(tmp_path)]) == path
    assert M.mlx_model_folder('mlx-community/missing', [str(tmp_path)]) == ''


def test_settings_mark_the_recommended_model_and_warn(tmp_path, monkeypatch):
    """On a 32 GB computer the 9B 4-bit is starred and the 27B selection gets a warning."""
    app = QApplication.instance() or QApplication([])
    q27 = _model_folder(str(tmp_path), 'Qwen3.8-27B-4bit', 15, True)
    q9 = _model_folder(str(tmp_path), 'Qwen3.5-9B-4bit', 5.6, True)
    entries = [{'backend': 'mlx', 'model': p, 'label': f"MLX (folder) · {os.path.basename(p)}", 'ready': False}
               for p in (q27, q9)]
    monkeypatch.setattr(S, 'discover_local_models', lambda host: entries)
    monkeypatch.setattr(S, 'system_memory', lambda: (32 * GB, 12 * GB))
    monkeypatch.setattr(S, 'fetch_ollama_models', lambda timeout=0: ([], False, ''))
    d = S.BackendDialog({'backend': 'mlx', 'model': q27})
    d._scan_mlx_models()
    texts = [d._mlx_model_combo.item(i).text() for i in range(d._mlx_model_combo.count())]
    assert any('Qwen3.5-9B-4bit' in t and S.RECOMMENDED_MARK in t for t in texts)
    assert not any('27B' in t and S.RECOMMENDED_MARK in t for t in texts)
    d._mlx_model_combo.setCurrentRow(0)
    d._update_fit()
    assert '12 GB is free' in d._fit_note.text()
    assert '32 GB RAM, 12 GB free now' in d._mem_note.text()
    cfg = d.get_config()
    assert cfg['idle_unload_min'] == 10 and cfg['unload_on_close'] is True
    d.deleteLater()
