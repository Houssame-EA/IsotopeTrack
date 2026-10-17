# -*- coding: utf-8 -*-
"""Tests for answers that report results without running code.

Covers the detector, the one-time request to compute first in the
benchmark turn, dropping those replies from the training data, cutting
results guessed after the code, the log scale on a box plot's group axis,
the negation-aware check for "real association" and the column notes.
"""
import re

import numpy as np
import pytest

from results.ai.analysis import SIGNATURES
from results.ai.benchmark import AFFIRMED_REAL, Outcome, _chat_turn
from results.ai.data import Dataset
from results.ai.figures import describe_figure
from results.ai.prompts import EMPTY_PREFIX, NO_CODE_PREFIX, build_system_prompt, needs_code
from results.ai.synthetic import make_dataset
from results.ai.theme import cut_after_code
from results.ai.training import keep_calls

BRIEF = "Samples: Ni-Fe-Mo_250000x_2 (2,740 particles), Fe-Cr-Co_500000x_2. Total 5,480 particles."


@pytest.fixture(scope='module')
def planted():
    """The synthetic dataset with its limits."""
    dc, truth, limits = make_dataset(seed=11)
    ds = Dataset(dc)
    ds.set_limits(limits)
    return ds


@pytest.mark.parametrize('text', [
    '.', '', 'The median Ag mass percentage is **52.6%**.',
    'The box plot above shows the Ti diameter for each sample.',
    'The exact numbers will appear once the code runs.',
    'Based on 476 particles, the median is about half.',
])
def test_made_up_results_are_caught(text):
    """Empty answers, invented numbers and figures "above" need code."""
    assert needs_code(text, BRIEF)


@pytest.mark.parametrize('text', [
    'Hello! You have 2 samples with 5,480 particles loaded. What would you like to look at?',
    'Hi! What would you like to look at in Ni-Fe-Mo_250000x_2?',
    '1. Count particles\n2. Compare samples\n3. Make figures',
    '56Fe suffers from the 40Ar16O interference.',
    'I can compare sizes between samples with a Kruskal-Wallis test.',
])
def test_plain_answers_pass(text):
    """Greetings, lists, isotope labels and numbers from the brief do not."""
    assert not needs_code(text, BRIEF)


def test_benchmark_turn_asks_for_code_once(planted):
    """An invented answer goes back once; the coded answer is then used."""
    replies = iter([
        "The median Ti diameter is 96.9 nm.",
        "```python\nprint(len(df))\n```",
        "There are that many particles.",
    ])
    seen = []

    def model(messages, system):
        """Replay the scripted replies and keep what was sent."""
        seen.append(messages[-1]['content'])
        return next(replies)

    out = Outcome('q', 'rivers', 'dev', 'count')
    messages = [{"role": "user", "content": "What is the median Ti diameter?"}]
    system = build_system_prompt(planted, 16384, 'chat', 10)
    _chat_turn(messages, system, planted, model, 16384, out, [])
    assert seen[1].startswith(NO_CODE_PREFIX)
    assert out.attempts == 1 and out.fixes == 1


def test_benchmark_turn_does_not_loop(planted):
    """A second answer without code is returned as it is."""
    replies = iter(["The median is 96.9 nm.", "Still 96.9 nm."])
    out = Outcome('q', 'rivers', 'dev', 'count')
    messages = [{"role": "user", "content": "What is the median Ti diameter?"}]
    system = build_system_prompt(planted, 16384, 'chat', 10)
    answer = _chat_turn(messages, system, planted, lambda m, s: next(replies), 16384, out, [])
    assert answer == "Still 96.9 nm." and out.attempts == 0


def test_invented_reply_is_not_learned():
    """The reply sent back for code is dropped from the training data."""
    q = [{"role": "user", "content": "Median Ti?"}]
    bad = "The median is 96.9 nm."
    calls = [
        {'messages': q, 'reply': bad},
        {'messages': q + [{"role": "assistant", "content": bad},
                          {"role": "user", "content": NO_CODE_PREFIX + " Your answer has no code"}],
         'reply': "```python\nprint(1)\n```"},
    ]
    kept = keep_calls(calls)
    assert [c['reply'] for c in kept] == ["```python\nprint(1)\n```"]


@pytest.mark.parametrize('text, claimed', [
    ("Ti and Fe do not show a real association: 147 vs 158 expected by chance.", False),
    ("There is no real association between Ti and Fe.", False),
    ("It isn't a real association; it is chance.", False),
    ("They are explained by coincidence rather than a real association.", False),
    ("Ti and Fe form a real association, far above chance.", True),
    ("They occur by chance. However, Ti+Fe is a real association in one sample.", True),
])
def test_real_association_claim(text, claimed):
    """A negated "real association" is not counted as the claim."""
    assert bool(re.search(AFFIRMED_REAL, text, re.I)) is claimed


def test_column_meanings_are_explained(planted):
    """The prompt says what mass % and the detection rate mean."""
    prompt = build_system_prompt(planted, 16384, 'chat', 10)
    assert "whole particle's mass" in prompt
    compare = next(desc for sig, desc in SIGNATURES if sig.startswith('compare_samples'))
    assert 'not the share below the LOD' in compare


GUESSED = ("I'll test it.\n```python\nshow_table(coincidence('Ti', 'Fe'))\n```\n"
           "**What the numbers show**: 145 vs 13.6 expected, a real association.")


def test_text_after_the_code_is_dropped():
    """Results described before the code ran are cut; text before the code stays."""
    assert cut_after_code(GUESSED) == "I'll test it.\n```python\nshow_table(coincidence('Ti', 'Fe'))\n```"
    assert cut_after_code("No code here, 12.5 nm.") == "No code here, 12.5 nm."


def test_benchmark_keeps_only_the_code_part(planted):
    """The conversation keeps the reply without the guessed results."""
    replies = iter([GUESSED, "They occur about as often as chance."])
    out = Outcome('q', 'rivers', 'dev', 'reasoning')
    messages = [{"role": "user", "content": "Ti and Fe real?"}]
    system = build_system_prompt(planted, 16384, 'chat', 10)
    _chat_turn(messages, system, planted, lambda m, s: next(replies), 16384, out, [])
    assert '13.6' not in messages[1]['content']


def test_training_learns_to_stop_after_the_code():
    """A kept reply ends with its code block."""
    calls = [{'messages': [{"role": "user", "content": "Ti and Fe real?"}], 'reply': GUESSED}]
    assert keep_calls(calls)[0]['reply'].endswith("```")


def test_reply_sent_back_after_a_cut_is_still_dropped():
    """A reply whose kept part was sent back for a fix is not learned."""
    q = [{"role": "user", "content": "Ti and Fe real?"}]
    calls = [
        {'messages': q, 'reply': GUESSED},
        {'messages': q + [{"role": "assistant", "content": cut_after_code(GUESSED)},
                          {"role": "user", "content": "[SANDBOX ERROR] Your code failed"}],
         'reply': "```python\nprint(1)\n```"},
    ]
    assert [c['reply'] for c in keep_calls(calls)] == ["```python\nprint(1)\n```"]


def _boxes(scale_axis, vert=True):
    """A labelled box plot with a log scale on one axis."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    data = [np.random.default_rng(k).lognormal(3, 1, 200) for k in range(3)]
    ax.boxplot(data, tick_labels=['A', 'B', 'C'], orientation='vertical' if vert else 'horizontal')
    getattr(ax, f'set_{scale_axis}scale')('log')
    ax.set_xlabel('Sample' if vert else 'Diameter (nm)')
    ax.set_ylabel('Diameter (nm)' if vert else 'Sample')
    return describe_figure(fig)[1]


def test_log_scale_on_the_group_axis_is_flagged():
    """A log scale that hides the sample names asks for the value axis."""
    assert any("set_yscale('log')" in w for w in _boxes('x'))
    assert any("set_xscale('log')" in w for w in _boxes('y', vert=False))


def test_log_scale_on_the_value_axis_is_fine():
    """The usual log value axis raises nothing."""
    assert not any('groups of the box' in w for w in _boxes('y'))


def test_prompt_says_to_stop_after_the_code(planted):
    """The rules tell the model to end with the code and not to read figures it cannot see."""
    from results.ai.prompts import interpretation_request
    assert 'end your reply there' in build_system_prompt(planted, 16384, 'chat', 10)
    assert 'You cannot see the figures' in interpretation_request('x')


def test_empty_reply_is_asked_again(planted):
    """A "." reply gets one more request, after which the code runs."""
    replies = iter([
        "The Ti + Fe pair is a real association: 145 observed vs 26.6 expected.",
        ".",
        "```python\nshow_table(coincidence('Ti', 'Fe'))\n```",
        "They occur about as often as chance coincidence predicts.",
    ])
    seen = []

    def model(messages, system):
        """Replay the scripted replies and keep what was sent."""
        seen.append(messages[-1]['content'])
        return next(replies)

    out = Outcome('q', 'rivers', 'dev', 'reasoning')
    messages = [{"role": "user", "content": "Ti and Fe real?"}]
    system = build_system_prompt(planted, 16384, 'chat', 10)
    answer = _chat_turn(messages, system, planted, model, 16384, out, [])
    assert seen[1].startswith(NO_CODE_PREFIX) and seen[2].startswith(EMPTY_PREFIX)
    assert out.attempts == 1 and 'chance' in answer


def test_symbol_helper_and_chance_rule(planted):
    """symbol() maps isotope labels to symbols; the rules forbid recomputing chance by hand."""
    from results.ai.sandbox import execute
    res = execute("print(symbol('56Fe'), symbol('238U'), symbol('Fe'))", planted, 30)
    assert res.text.strip() == 'Fe U Fe'
    prompt = build_system_prompt(planted, 16384, 'chat', 10)
    assert 'Never recompute chance co-occurrence' in prompt and "symbol('56Fe')" in prompt
