# -*- coding: utf-8 -*-
"""Tests for the AI assistant's sandbox, figures and grounding helpers.

The assistant writes Python, runs it in a restricted sandbox and reports
back. These tests pin down the parts that protect the user and keep answers
honest:

* :func:`results.ai.sandbox.screen_code` blocks the known ways out of the
  namespace: dunder and underscore attributes, frame walking, and file
  access through numpy, pandas and matplotlib.
* :func:`results.ai.sandbox.execute` runs code on the particle table,
  reports errors with the failing line, and never exposes the main window.
* Figures the model draws come back drawn and described, with problems
  such as empty panels flagged.
* :func:`results.ai.sandbox.unverified_numbers` flags figures in prose that
  no computed result backs.
* The system prompt is grounded in the data and fits the context window.
"""
import pytest

from results.ai import sandbox as sb
from results.ai.data import Dataset
from results.ai.exploration import FindingsLedger, is_done, parse_plan
from results.ai.prompts import (
    build_system_prompt, estimate_tokens, fit_messages, reply_reserve, suggest_questions,
)


def _mk_particle(t, fe=None, ca=None, sample='S1'):
    """One particle with optional Fe and Ca."""
    el, mass, dia = {}, {}, {}
    if fe:
        el['56Fe'] = fe
        mass['56Fe'] = fe * 0.01
        dia['56Fe'] = fe * 0.5
    if ca:
        el['40Ca'] = ca
        mass['40Ca'] = ca * 0.01
        dia['40Ca'] = ca * 0.5
    return {
        'elements': el, 'element_mass_fg': mass, 'element_diameter_nm': dia,
        'element_moles_fmol': {}, 'mass_percentages': {}, 'mole_percentages': {},
        'totals': {'total_element_mass_fg': sum(mass.values())},
        'start_time': t, 'end_time': t + 0.001, 'source_sample': sample,
    }


@pytest.fixture
def ds():
    """A tiny two-sample dataset with a fake main window attached."""
    particles = [_mk_particle(0.0, fe=100), _mk_particle(0.1, ca=200),
                 _mk_particle(0.2, fe=50, ca=50), _mk_particle(0.3, fe=80, sample='S2')]
    dc = {'type': 'multiple_sample_data', 'sample_names': ['S1', 'S2'],
          'particle_data': particles, 'parent_window': object()}
    return Dataset(dc)


class TestSafetyScreen:
    """The static screen run before any generated code."""

    def test_blocks_filesystem_calls(self):
        """numpy, pandas and matplotlib writers are refused."""
        assert sb.screen_code("np.save('x', [1, 2])") is not None
        assert sb.screen_code("total.tofile('x')") is not None
        assert sb.screen_code("df.to_csv('x.csv')") is not None
        assert sb.screen_code("pd.read_csv('x.csv')") is not None
        assert sb.screen_code("fig.savefig('x.png')") is not None

    def test_blocks_dunder_and_private_escapes(self):
        """Introspection routes out of the namespace are refused."""
        assert sb.screen_code("y = ().__class__.__bases__[0]") is not None
        assert sb.screen_code("z = __import__('os')") is not None
        assert sb.screen_code("g = (i for i in []).gi_frame") is not None
        assert sb.screen_code("x = df._data") is not None

    def test_blocks_dangerous_builtins_and_imports(self):
        """open, eval and imports of unknown modules are refused."""
        assert sb.screen_code("open('/etc/passwd')") is not None
        assert sb.screen_code("eval('1+1')") is not None
        assert sb.screen_code("import os") is not None

    def test_allows_normal_analysis(self):
        """Ordinary pandas, numpy and plotting code passes."""
        assert sb.screen_code("x = df['mass_fg_56Fe'].dropna().median()") is None
        assert sb.screen_code("fig, ax = plt.subplots(); ax.hist([1, 2]); ax.set_xscale('log')") is None

    def test_known_imports_are_stripped(self):
        """Imports of pre-loaded libraries are removed rather than refused."""
        code = sb.sanitize_code("import numpy as np\nimport matplotlib.pyplot as plt\nprint(1)")
        assert 'import' not in code and sb.screen_code(code) is None


class TestSandboxExecution:
    """Running generated code on a dataset."""

    def test_table_from_dataframe(self, ds):
        """A DataFrame passed to show_table becomes a table with its numbers."""
        res = sb.execute("show_table(df[['sample', 'n_elements']], title='t')", ds)
        assert not res.error
        assert res.tables[0]['headers'] == ['sample', 'n_elements']
        assert len(res.tables[0]['rows']) == 4

    def test_headers_and_rows_still_work(self, ds):
        """The older headers-and-rows form is accepted."""
        res = sb.execute("show_table(['el', 'n'], [[e, 1] for e in elements])", ds)
        assert not res.error and res.tables[0]['rows']

    def test_runtime_error_reports_line(self, ds):
        """A runtime error names the failing line for the correction round."""
        res = sb.execute("x = 1\nprint(1 / 0)", ds)
        assert 'ZeroDivisionError' in res.error and 'line 2' in res.error

    def test_blocked_code_is_not_executed(self, ds):
        """Refused code never runs."""
        res = sb.execute("np.save('escape', [1])", ds)
        assert res.error.startswith('Blocked')

    def test_main_window_is_not_reachable(self, ds):
        """The data context handed to code has no main window."""
        res = sb.execute("print('parent_window' in data_context)", ds)
        assert res.text == 'False'

    def test_element_and_quantity_aliases(self, ds):
        """col() accepts symbols and quantity aliases."""
        res = sb.execute("print(col('size', 'fe'))", ds)
        assert res.text == 'diameter_nm_56Fe'

    def test_timeout_stops_the_code(self, ds):
        """Endless code is stopped, not left running, and explained."""
        import threading
        before = threading.active_count()
        res = sb.execute("while True:\n    pass", ds, timeout=0.5)
        assert 'timed out' in res.error
        assert threading.active_count() == before


class TestFigures:
    """Figures the model draws itself."""

    def test_subplots_figure_is_drawn_and_described(self, ds):
        """A figure made with plt.subplots is rendered and described."""
        code = ("fig, ax = plt.subplots()\n"
                "ax.hist(df['mass_fg_56Fe'].dropna(), bins=5)\n"
                "ax.set_xscale('log'); ax.set_xlabel('Fe mass (fg)'); ax.set_ylabel('Particles')")
        res = sb.execute(code, ds)
        assert not res.error
        assert len(res.figures) == 1
        assert res.figures[0]['png'].startswith(b'\x89PNG')
        assert '(log)' in res.figures[0]['description']
        assert not res.warnings

    def test_pyplot_state_style(self, ds):
        """Stateful plt calls draw on the current axes."""
        res = sb.execute("plt.figure()\nplt.plot([1, 2], [3, 4])\nplt.xlabel('a')\nplt.ylabel('b')\nplt.show()", ds)
        assert not res.error and len(res.figures) == 1
        assert "x 'a'" in res.figures[0]['description']

    def test_empty_figure_is_flagged(self, ds):
        """An empty panel produces a warning the model is asked to fix."""
        res = sb.execute("fig, ax = new_figure()\nax.set_title('nothing')", ds)
        assert any('empty' in w for w in res.warnings)

    def test_too_many_figures_is_an_error(self, ds):
        """A runaway loop of figures stops at the limit."""
        res = sb.execute("for i in range(20):\n    plt.subplots()", ds)
        assert 'At most' in res.error

    def test_savefig_writes_nothing(self, ds, tmp_path, monkeypatch):
        """A plt.savefig line is dropped and fig.savefig is refused."""
        monkeypatch.chdir(tmp_path)
        res = sb.execute("fig, ax = plt.subplots()\nax.plot([1, 2])\nplt.savefig('x.png')", ds)
        assert not res.error and not (tmp_path / 'x.png').exists()
        assert sb.screen_code("fig.savefig('x.png')") is not None


class TestNumberProvenance:
    """Flagging figures that no computed result backs."""

    def test_flags_fabricated_decimal(self):
        """A decimal absent from the results is flagged."""
        assert sb.unverified_numbers("mean 12.34 and also 999.99", [12.34]) == ['999.99']

    def test_verified_decimal_within_tolerance(self):
        """Rounding of a computed value is accepted."""
        assert sb.unverified_numbers("the mean is 12.34", [12.339, 5.0]) == []

    def test_percentage_form_is_accepted(self):
        """A fraction restated as a percentage counts as backed."""
        assert sb.unverified_numbers("about 45.2% of particles", [0.452]) == []

    def test_integers_are_ignored(self):
        """Whole numbers are not checked."""
        assert sb.unverified_numbers("there are 7 particles in 3 samples", []) == []

    def test_floats_in_text_handles_thousands(self):
        """Thousands separators are parsed."""
        assert 1234.5 in sb.floats_in_text("1,234.5 fg measured")


class TestPrompts:
    """The system prompt and the context budget."""

    def test_reports_concentration_unavailable(self, ds):
        """Missing concentration metadata is stated."""
        assert 'NOT available' in build_system_prompt(ds, 8192)

    def test_reports_concentration_available(self):
        """Available concentration metadata is stated."""
        dc = {'type': 'sample_data', 'sample_name': 'S1',
              'particle_data': [_mk_particle(0.0, fe=100)],
              'concentration_meta': {'S1': {'volume_ml': 1.0, 'dilution_factor': 1.0}}}
        assert 'Concentrations: available' in build_system_prompt(Dataset(dc), 8192)

    def test_includes_known_interferences(self, ds):
        """Documented interferences on the detected masses are listed."""
        assert 'interferences' in build_system_prompt(ds, 32768).lower()

    def test_compact_prompt_for_small_windows(self, ds):
        """Small windows get a shorter prompt without the worked example."""
        small = build_system_prompt(ds, 8192)
        large = build_system_prompt(ds, 32768)
        assert estimate_tokens(small) < estimate_tokens(large)
        assert 'EXAMPLE' in large and 'EXAMPLE' not in small

    def test_budget_counts_the_system_prompt(self):
        """History is trimmed so system prompt, history and reply fit."""
        system = 'x' * 14000
        history = [{'role': 'user', 'content': 'y' * 3500} for _ in range(10)]
        kept = fit_messages(history, system, 8192)
        total = estimate_tokens(system) + sum(estimate_tokens(m['content']) for m in kept)
        assert total + reply_reserve(8192) <= 8192
        assert kept and kept[-1] is history[-1]

    def test_pinned_question_survives(self):
        """The first message of an exploration is never dropped."""
        history = [{'role': 'user', 'content': 'QUESTION'}] + \
                  [{'role': 'user', 'content': 'z' * 4000} for _ in range(10)]
        kept = fit_messages(history, 'sys', 8192, pinned=1)
        assert kept[0]['content'] == 'QUESTION'

    def test_suggestions_follow_the_data(self, ds):
        """Suggestions are label and question pairs about this data."""
        items = suggest_questions(ds)
        assert items and all(len(i) == 2 for i in items)
        assert any('Fe' in label for label, _ in items)


class TestExploration:
    """Plan parsing and the findings ledger."""

    def test_parse_plan(self):
        """Numbered hypotheses after PLAN: are extracted."""
        text = "PLAN:\n1. Ti differs between samples\n2) Ce+La is real\n- Fe bursts\nTesting 1.\n```python\nx=1\n```"
        assert parse_plan(text) == ['Ti differs between samples', 'Ce+La is real', 'Fe bursts']

    def test_done_marker(self):
        """EXPLORATION DONE is recognised only at the start of a line."""
        assert is_done("All covered.\nEXPLORATION DONE")
        assert not is_done("I am not done with the exploration done yet")

    def test_ledger_dedupes_and_ranks(self):
        """Duplicate claims are dropped and significant findings come first."""
        led = FindingsLedger()
        led.add([{'claim': 'B weak', 'p': 0.3}, {'claim': 'A strong', 'p': 1e-6, 'effect': 3}], turn=1)
        led.add([{'claim': 'a strong'}], turn=2)
        assert len(led) == 2
        assert led.ranked()[0].claim == 'A strong'
        assert 'not supported' in led.as_text()
