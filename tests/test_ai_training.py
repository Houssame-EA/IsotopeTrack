# -*- coding: utf-8 -*-
"""Tests for the fine-tuning data generator.

The built-in reference answers stand in for the teacher model, so the
whole path runs offline: new datasets, verified answers, the filter that
drops failed replies and fabricated numbers, and the files for mlx_lm.lora.
"""
import json
import os

import pytest

from results.ai.benchmark import reference_model
from results.ai.training import (
    HELDOUT_TEMPLATES, build, generate, keep_calls, random_spec, training_questions,
)


def test_random_datasets_vary_and_avoid_the_test_set():
    """Names, sample counts and planted features vary; nothing looks like the lakes."""
    specs = [random_spec(1000 + i) for i in range(40)]
    styles = {s['samples'][0].rstrip('0123456789 x').split('_')[0] for s in specs}
    assert len(styles) >= 6
    assert {len(s['samples']) for s in specs} >= {2, 3, 4, 5, 6}
    for s in specs:
        assert not any('lake' in n.lower() for n in s['samples'])
        assert len(set(s['samples'])) == len(s['samples'])
        ti = s['ti_median_nm']
        top = max(ti, key=ti.get)
        assert top != s['samples'][0]
        assert sorted(ti.values())[-1] >= 1.4 * sorted(ti.values())[-2]


def test_held_out_templates_are_never_asked():
    """The templates kept for testing are not in the training questions."""
    _, _, qs = training_questions(1000)
    templates = {q.qid.split('.', 1)[1] for q in qs}
    assert templates and not templates & HELDOUT_TEMPLATES


def _call(messages, reply):
    """A recorded call."""
    return {'system': 'sys', 'messages': messages, 'reply': reply}


def test_failed_replies_and_invented_numbers_are_dropped():
    """A reply sent back for a fix is not learned; its fix is; a takeaway with an unbacked decimal is dropped."""
    bad = "Trying.\n```python\nprint(df['x'])\n```"
    good = "Fixed.\n```python\nprint(1)\n```"
    calls = [
        _call([{'role': 'user', 'content': 'q'}], bad),
        _call([{'role': 'user', 'content': 'q'}, {'role': 'assistant', 'content': bad},
               {'role': 'user', 'content': "[SANDBOX ERROR] Your code failed:\nKeyError"}], good),
        _call([{'role': 'user', 'content': 'Here are the EXACT results your code just produced:\n\nPRINTED:\n3.25'}],
              "The median is 3.25 fg."),
        _call([{'role': 'user', 'content': 'Here are the EXACT results your code just produced:\n\nPRINTED:\n3.25'}],
              "The median is 4.75 fg."),
    ]
    kept = [c['reply'] for c in keep_calls(calls)]
    assert kept == [good, "The median is 3.25 fg."]


def test_generate_and_build(tmp_path):
    """Verified answers become chat examples, and build writes the mlx_lm files and config."""
    out = str(tmp_path)
    stats = generate(reference_model, out, n_datasets=2, categories=['count', 'edit'], verbose=False)
    assert stats['questions'] and stats['passed'] == stats['questions'] and stats['examples'] > stats['questions']
    again = generate(reference_model, out, n_datasets=2, categories=['count', 'edit'], verbose=False)
    assert again['questions'] == 0
    rows = [json.loads(line) for line in open(os.path.join(out, 'examples.jsonl'), encoding='utf-8')]
    first = rows[0]['messages']
    assert first[0]['role'] == 'system' and 'IsotopeTrack' in first[0]['content']
    assert first[-1]['role'] == 'assistant'
    counts = build(out, valid_every=2)
    assert counts['train'] and counts['valid']
    for name in ('train.jsonl', 'valid.jsonl'):
        line = open(os.path.join(out, 'data', name), encoding='utf-8').readline()
        assert set(json.loads(line)) == {'messages'}
    config = open(os.path.join(out, 'lora_config.yaml'), encoding='utf-8').read()
    assert 'mask_prompt: true' in config and f"iters: {counts['iters']}" in config


def test_answers_without_code_and_unreached_teacher_are_not_kept(tmp_path):
    """A reply read off the dataset description is not learned; a failed request is asked again next run."""
    from results.ai.training import is_backend_error, retrying

    def no_code(question):
        """A teacher that answers count questions from memory."""
        return lambda messages, system: f"There are {question.expected} particles."

    out = str(tmp_path)
    stats = generate(no_code, out, n_datasets=1, categories=['count'], verbose=False)
    assert stats['passed'] > 0 and stats['examples'] == 0
    calls = {'n': 0}

    def down(question):
        """A teacher whose server is not running."""
        def reply(messages, system):
            """Fail like an unreachable server."""
            calls['n'] += 1
            raise ConnectionError("Max retries exceeded")
        return reply

    out2 = str(tmp_path / 'b')
    generate(down, out2, n_datasets=1, categories=['count'], verbose=False)
    first = calls['n']
    generate(down, out2, n_datasets=1, categories=['count'], verbose=False)
    assert first > 0 and calls['n'] == 2 * first
    assert is_backend_error("ConnectionError: Max retries exceeded") and not is_backend_error("KeyError: 'sample'")
    tries = {'n': 0}

    def flaky(messages, system):
        """Fail once, then answer."""
        tries['n'] += 1
        if tries['n'] == 1:
            raise TimeoutError("timed out")
        return "ok"
    assert retrying(flaky, wait_s=0.01)([], '') == 'ok' and tries['n'] == 2


def test_ignored_calls_are_removed_from_targets():
    """plt.show() and tight_layout() lines are dropped from kept replies."""
    reply = "Plot.\n```python\nfig, ax = plt.subplots()\nax.plot([1])\nplt.tight_layout()\nplt.show()\n```"
    kept = keep_calls([_call([{'role': 'user', 'content': 'q'}], reply)])
    assert kept[0]['reply'] == "Plot.\n```python\nfig, ax = plt.subplots()\nax.plot([1])\n```"


def test_http_errors_carry_the_server_message():
    """An HTTP error names the server's reason and counts as the teacher not being reached."""
    from results.ai.benchmark import _raise_for_status
    from results.ai.training import is_backend_error

    class R:
        """A failed response."""
        status_code = 500
        url = 'http://127.0.0.1:11434/api/chat'
        text = '{"error":"model runner has unexpectedly stopped"}'

    with pytest.raises(RuntimeError) as err:
        _raise_for_status(R())
    assert 'model runner has unexpectedly stopped' in str(err.value) and is_backend_error(str(err.value))
