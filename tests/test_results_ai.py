# -*- coding: utf-8 -*-
"""Tests for the results AI assistant sandbox and grounding helpers.

The AI assistant writes Python, runs it in a restricted sandbox, and reports
back. These tests pin down the parts that protect the user and keep answers
honest:

* ``_screen_code`` — the AST safety pass that blocks sandbox-escape attempts
  (dunder attribute walking) and filesystem access (``np.save`` and friends),
  which the builtins whitelist alone cannot stop.
* ``_execute_query_code`` — happy path, blocked code, and that a runtime error
  is reported with the offending source line (used by the self-correction loop).
* ``_unverified_numbers`` — the no-fabrication guardrail: decimal figures in
  prose that the executed code never produced are flagged.
* ``_build_system_prompt`` — that the prompt is grounded with concentration
  availability and known spectral interferences from the project database.

The conftest forces Qt offscreen, so importing the module is safe in CI.
"""
import pytest

from results import results_AI as ai


def _mk_particle(t, fe=None, ca=None):
    el, mass, dia = {}, {}, {}
    if fe:
        el['56Fe'] = fe; mass['56Fe'] = fe * 0.01; dia['56Fe'] = fe * 0.5
    if ca:
        el['40Ca'] = ca; mass['40Ca'] = ca * 0.01; dia['40Ca'] = ca * 0.5
    return {
        'elements': el, 'element_mass_fg': mass, 'element_diameter_nm': dia,
        'element_moles_fmol': {}, 'mass_percentages': {}, 'mole_percentages': {},
        'totals': {'total_element_mass_fg': sum(mass.values())},
        'start_time': t, 'end_time': t + 0.001, 'source_sample': 'S1',
    }


@pytest.fixture
def dataset():
    particles = [_mk_particle(0.0, fe=100),
                 _mk_particle(0.1, ca=200),
                 _mk_particle(0.2, fe=50, ca=50)]
    dc = {'type': 'multiple_sample_data', 'sample_names': ['S1'],
          'particle_data': particles}
    return particles, dc


class TestSafetyScreen:
    def test_blocks_filesystem_calls(self):
        assert ai._screen_code("np.save('x', [1, 2])") is not None
        assert ai._screen_code("total.tofile('x')") is not None

    def test_blocks_dunder_escape(self):
        assert ai._screen_code("y = ().__class__.__bases__[0]") is not None
        assert ai._screen_code("z = __import__('os')") is not None

    def test_blocks_dangerous_builtins(self):
        assert ai._screen_code("open('/etc/passwd')") is not None
        assert ai._screen_code("eval('1+1')") is not None

    def test_allows_normal_analysis(self):
        assert ai._screen_code("x = sum(total_masses) / max(len(particles), 1)") is None
        assert ai._screen_code(
            "show_table(['a'], [[1]], title='t')") is None


class TestSandboxExecution:
    def test_happy_path_returns_table(self, dataset):
        particles, dc = dataset
        _, tables, _, err = ai._execute_query_code(
            "show_table(['el', 'n'], [[k, str(v)] for k, v in element_counts.items()])",
            particles, dc)
        assert err is None
        assert tables and tables[0]['rows']

    def test_runtime_error_reports_line(self, dataset):
        particles, dc = dataset
        _, _, _, err = ai._execute_query_code("print(1 / 0)", particles, dc)
        assert err and 'ZeroDivisionError' in err and 'line' in err

    def test_blocked_code_is_not_executed(self, dataset):
        particles, dc = dataset
        _, _, _, err = ai._execute_query_code(
            "np.save('escape', total_masses)", particles, dc)
        assert err and 'Blocked' in err


class TestNumberProvenance:
    def test_flags_fabricated_decimal(self):
        assert ai._unverified_numbers("mean 12.34 and also 999.99", [12.34]) == ['999.99']

    def test_verified_decimal_within_tolerance(self):
        assert ai._unverified_numbers("the mean is 12.34", [12.339, 5.0]) == []

    def test_integers_are_ignored(self):
        assert ai._unverified_numbers("there are 7 particles in 3 samples", []) == []

    def test_floats_in_text_handles_thousands(self):
        assert 1234.5 in ai._floats_in_text("1,234.5 fg measured")


class TestGroundedPrompt:
    def test_reports_concentration_unavailable(self, dataset):
        _, dc = dataset
        sp = ai._build_system_prompt(dc, 'ollama')
        assert 'DATA AVAILABILITY' in sp and 'NOT AVAILABLE' in sp

    def test_reports_concentration_available(self, dataset):
        _, dc = dataset
        dc = dict(dc)
        dc['concentration_meta'] = {'S1': {'volume_ml': 1.0, 'dilution_factor': 1.0}}
        assert 'AVAILABLE — element_per_ml' in ai._build_system_prompt(dc, 'ollama')

    def test_includes_known_interferences(self, dataset):
        _, dc = dataset
        sp = ai._build_system_prompt(dc, 'ollama')
        # 40Ca (40Ar) and 56Fe (40Ar16O) carry documented interferences
        assert 'KNOWN SPECTRAL INTERFERENCES' in sp
