# -*- coding: utf-8 -*-
"""Tests for ``results/results_matrix.py`` (Correlation Matrix).

Currently covers the **triviality marker** (2026-08-26): a correlation that
is arithmetic rather than evidence is marked with ``TRIVIALITY_MARKER``
instead of being printed as a number the reader has to mentally discount.

Two behaviours share the one symbol:

* **replaces** the value when the correlation is fixed by construction --
  today the leading diagonal, which is exactly 1 in every correlation matrix
  ever drawn, classifier or not;
* **annotates** the value (``0.87*``) for part-whole contamination, where the
  number is real and worth reading but inflated because one side is a sum
  containing the other. Nothing generates that mask yet -- it lands with the
  classifier pass, where a group's value is a sum over isotopes -- so it is
  tested here by passing the mask explicitly.

The point of the marker is inverted from what it looks like: it exists so a
*genuine* r = 1 between two things that are NOT definitionally linked reads as
a finding instead of blending into a wall of guaranteed 1s.

Dialogs are built through a ``_FigureView``, never the bare node -- that is
the path the app actually uses for multi-figure viz nodes, and testing the
node directly is how a whole day of heatmap work shipped broken while the
suite stayed green (see ``.claude/aug24.md``).
"""
import numpy as np
import pytest

from results import classifier_view as cv
from results.results_matrix import (
    CorrelationMatrixNode, CorrelationMatrixDisplayDialog, TRIVIALITY_MARKER,
    ZERO_MODE_BOTH, ZERO_MODE_EITHER, ZERO_MODE_ALL,
    PANEL_GROUP_CONFIG_KEY, PART_WHOLE_IN_STATS_KEY)
from results.shared_plot_utils import _FigureView


def _stream(n=60, seed=0):
    """One sample where 60Ni tracks 56Fe almost exactly and 63Cu is
    independent -- so the OFF-diagonal Fe/Ni pair genuinely correlates at
    ~1.00 and must stay readable as a number."""
    rng = np.random.default_rng(seed)
    particles = []
    for _ in range(n):
        fe = float(rng.integers(5, 50))
        particles.append({'elements': {
            '56Fe': fe,
            '60Ni': fe * 2 + float(rng.normal(0, 1)),
            '63Cu': float(rng.integers(5, 50)),
        }})
    return {'type': 'sample_data', 'sample_name': 'S1',
            'particle_data': particles,
            'selected_isotopes': [{'label': x}
                                  for x in ('56Fe', '60Ni', '63Cu')]}


@pytest.fixture(scope="module")
def qapp():
    """Per-file, matching this suite's existing convention (every Qt test
    module declares its own rather than sharing one via conftest)."""
    from PySide6.QtWidgets import QApplication
    import sys
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def view_and_dialog(qapp):
    node = CorrelationMatrixNode()
    node.process_data(_stream())
    view = _FigureView(node, CorrelationMatrixDisplayDialog, None)
    dlg = CorrelationMatrixDisplayDialog(view, None)
    return view, dlg


def _cell_texts(dlg):
    """Cell labels in (i, j) order -- ``_draw_matrix_ax`` adds them row-major
    and skips NaN cells, so callers that disable cells must not index."""
    ax = [a for a in dlg.figure.get_axes() if a.get_xticklabels()][0]
    return [t.get_text() for t in ax.texts]


def _classified_stream(sample='E1', overlap='priority', seed=7):
    """Classifier stream shaped so every branch of GROUPS is exercised.

    ``common`` = ``49Ti+27Al``, ``carney`` = ``27Al``. Deliberately includes
    Al-WITHOUT-Ti particles: under ``priority`` the earlier, narrower
    ``common`` otherwise claims every Al-bearing particle and ``carney`` is
    starved to zero members (a real behaviour, and an easy fixture trap).
    """
    from tools.particle_classifier_node import (
        ParticleClassifierNode, new_definition_id)
    rng = np.random.default_rng(seed)

    def p(**iso):
        return {'elements': dict(iso),
                'element_mass_fg': {k: v * 10.0 for k, v in iso.items()},
                'source_sample': sample}

    parts = []
    for _ in range(40):                       # -> common (Ti and Al)
        al = float(rng.integers(5, 40))
        parts.append(p(**{'27Al': al,
                          '49Ti': al * 1.5 + float(rng.normal(0, 2)),
                          '56Fe': float(rng.integers(5, 40))}))
    for _ in range(12):                       # -> carney (Al, no Ti)
        al = float(rng.integers(5, 40))
        parts.append(p(**{'27Al': al, '56Fe': al * 0.8 + float(rng.normal(0, 2))}))
    for _ in range(15):                       # -> Unclassified
        parts.append(p(**{'63Cu': float(rng.integers(5, 40))}))

    clf = ParticleClassifierNode()
    clf.input_data = {'type': 'sample_data', 'sample_name': sample,
                      'particle_data': parts,
                      'selected_isotopes': [{'label': x} for x in
                                            ('27Al', '49Ti', '56Fe', '63Cu')]}
    clf.definitions = [
        {'id': new_definition_id(), 'target_sample': sample,
         'expression_text': '49Ti+27Al', 'match_mode': 'partial',
         'group_name': 'common', 'color': None},
        {'id': new_definition_id(), 'target_sample': sample,
         'expression_text': '27Al', 'match_mode': 'partial',
         'group_name': 'carney', 'color': None},
    ]
    clf.groups = {'common': '#E11D48', 'carney': '#2563EB'}
    clf.unmatched_mode = 'unclassified'
    clf.overlap_mode = overlap
    return clf.get_output_data()


@pytest.fixture
def classified(qapp):
    """(view, dialog) on a classifier stream, through the real proxy path."""
    node = CorrelationMatrixNode()
    node.process_data(_classified_stream())
    view = _FigureView(node, CorrelationMatrixDisplayDialog, None)
    view.config['min_particles'] = 2
    return view, CorrelationMatrixDisplayDialog(view, None)


class TestZeroHandling:
    """Which particles a pair is correlated over -- a real scientific choice
    that was hardcoded to "both present" forever, and applies with or without
    a classifier."""

    PARTICLES = [{'elements': {'56Fe': 10.0, '60Ni': 20.0}},
                 {'elements': {'56Fe': 30.0, '60Ni': 60.0}},
                 {'elements': {'56Fe': 5.0}},
                 {'elements': {'60Ni': 8.0}}]

    def test_default_is_unchanged_from_before_the_option_existed(self):
        from results.results_matrix import _compute_correlation_matrix
        mat, _, counts = _compute_correlation_matrix(
            self.PARTICLES, ['56Fe', '60Ni'], 'elements', min_particles=2)
        assert abs(mat[0, 1] - 1.0) < 1e-9
        # Only the 2 particles carrying both -- the historical rule.
        assert counts[0, 1] == 2

    @pytest.mark.parametrize('mode,expected_n', [
        (ZERO_MODE_BOTH, 2), (ZERO_MODE_EITHER, 4), (ZERO_MODE_ALL, 4)])
    def test_counts_follow_the_active_rule(self, mode, expected_n):
        """``min_particles`` and the header's pair-count line must describe
        the rule in force, not a co-detection rule the matrix may no longer
        be using."""
        from results.results_matrix import _compute_correlation_matrix
        _, _, counts = _compute_correlation_matrix(
            self.PARTICLES, ['56Fe', '60Ni'], 'elements', 2, zero_mode=mode)
        assert counts[0, 1] == expected_n

    def test_including_zeros_changes_r(self):
        from results.results_matrix import _compute_correlation_matrix
        both, _, _ = _compute_correlation_matrix(
            self.PARTICLES, ['56Fe', '60Ni'], 'elements', 2,
            zero_mode=ZERO_MODE_BOTH)
        allp, _, _ = _compute_correlation_matrix(
            self.PARTICLES, ['56Fe', '60Ni'], 'elements', 2,
            zero_mode=ZERO_MODE_ALL)
        assert both[0, 1] != allp[0, 1]

    def test_effective_mode_falls_back_on_garbage(self):
        from results.results_matrix import effective_zero_mode
        assert effective_zero_mode({}) == ZERO_MODE_BOTH
        assert effective_zero_mode({'zero_handling': 'nonsense'}) == ZERO_MODE_BOTH
        assert effective_zero_mode({'zero_handling': ZERO_MODE_ALL}) == ZERO_MODE_ALL


class TestGroupsRoleMixedVocabulary:
    def test_axes_are_isotopes_then_groups(self, classified):
        view, _ = classified
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        data = view.extract_matrix_data()
        # Blocked, not interleaved, so the three regions stay separable.
        assert data['elements'] == ['27Al', '49Ti', '56Fe', '63Cu',
                                    'common', 'carney', 'Unclassified']

    def test_isotope_by_group_cells_are_populated(self, classified):
        """The reason mixed beats group-only: these need no overlap between
        definitions, so they work under plain ``priority``."""
        view, _ = classified
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        data = view.extract_matrix_data()
        e = data['elements']
        assert not np.isnan(data['matrix'][e.index('56Fe'), e.index('common')])
        assert not np.isnan(data['matrix'][e.index('27Al'), e.index('common')])

    def test_group_by_group_is_empty_under_priority_and_explained(self, classified):
        """Structurally impossible, not a failure: a particle belongs to one
        bucket, so no two groups ever co-occur. Must be stated, not left as a
        blank grid."""
        view, dlg = classified
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        data = view.extract_matrix_data()
        e = data['elements']
        assert np.isnan(data['matrix'][e.index('common'), e.index('carney')])
        dlg._refresh()
        assert 'priority' in dlg._header.text()

    def test_off_role_is_the_plain_isotope_matrix(self, classified):
        view, _ = classified
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_OFF
        data = view.extract_matrix_data()
        assert data['elements'] == ['27Al', '49Ti', '56Fe', '63Cu']
        assert 'exact_trivial' not in data

    def test_diameter_drops_groups_and_says_why(self, classified):
        """The classifier never sums a diameter across isotopes, so a group
        has no scalar value to correlate -- drop the columns rather than
        invent one."""
        view, dlg = classified
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        view.config['data_type_display'] = 'Element Diameter (nm)'
        data = view.extract_matrix_data()
        assert 'common' not in data['elements']
        assert data['groups_dropped'] is True
        dlg._refresh()
        assert 'diameter' in dlg._header.text()


class TestDoubleCountRecombination:
    """Found in manual QA, 2026-08-26: **every** group x group cell was blank
    even with ``double_count`` enabled -- the exact situation double-counting
    exists to make plottable.

    Cause: ``build_mixed_columns`` iterated the classifier's emitted COPIES.
    A particle matching two definitions arrives as two dicts, each carrying
    one bucket key, so it produced one row with ``common>0, carney=0`` and
    another with ``common=0, carney>0``. No row ever held both, so the pair
    could never co-occur. The same bug also made a doubly-matched particle
    contribute its isotope values twice, double-weighting every isotope x
    isotope correlation on the matrix.
    """

    def _dc_view(self, qapp, scope=None):
        node = CorrelationMatrixNode()
        node.process_data(_classified_stream(overlap='double_count'))
        view = _FigureView(node, CorrelationMatrixDisplayDialog, None)
        view.config['min_particles'] = 2
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        if scope:
            view.config[cv.SCOPE_CONFIG_KEY] = scope
        return view

    def test_group_by_group_populates_under_double_count(self, qapp):
        view = self._dc_view(qapp)
        data = view.extract_matrix_data()
        e = data['elements']
        r = data['matrix'][e.index('common'), e.index('carney')]
        assert not np.isnan(r), "group x group must populate under double_count"

    def test_one_row_per_real_particle(self, qapp):
        from results.results_matrix import build_mixed_columns, _merge_copies_by_identity
        stream = _classified_stream(overlap='double_count')
        particles = stream['particle_data']
        n_real = len(_merge_copies_by_identity(particles))
        assert n_real < len(particles), "fixture must actually double-count"
        cols, _ = build_mixed_columns(
            particles, ['27Al', '49Ti', '56Fe', '63Cu'],
            ['common', 'carney'], 'elements', cv.SCOPE_TOTAL_PARTICLE)
        assert {len(c) for c in cols.values()} == {n_real}

    def test_isotope_pairs_are_not_double_weighted(self, qapp):
        """OFF role is a pure isotope statistic, so each real particle must
        count once no matter how many buckets claimed it."""
        view = self._dc_view(qapp)
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_OFF
        data = view.extract_matrix_data()
        e = data['elements']
        n_used = data['pair_counts'][e.index('27Al'), e.index('56Fe')]
        # 40 Ti+Al+Fe particles + 12 Al+Fe particles, each counted ONCE.
        assert n_used == 52, n_used

    def test_group_by_group_is_tautological_under_total_particle(self, qapp):
        """Exposed only once the recombination fix made these cells
        computable at all: under TOTAL PARTICLE a group's value is the sum of
        every isotope on the particle, which does not depend on which group
        is asking -- so two groups sharing a particle hold identical numbers
        and correlate at exactly 1. Marked, not reported as a finding."""
        view = self._dc_view(qapp, cv.SCOPE_TOTAL_PARTICLE)
        data = view.extract_matrix_data()
        e = data['elements']
        i, j = e.index('common'), e.index('carney')
        assert abs(data['matrix'][i, j] - 1.0) < 1e-9
        assert data['exact_trivial'][i, j]

    def test_by_definition_group_pairs_stay_informative(self, qapp):
        """Different isotope sets are summed, so the same cell IS a real
        correlation and must NOT be marked."""
        view = self._dc_view(qapp, cv.SCOPE_DEFINITION)
        data = view.extract_matrix_data()
        e = data['elements']
        i, j = e.index('common'), e.index('carney')
        assert not data['exact_trivial'][i, j]
        assert not np.isnan(data['matrix'][i, j])

    def test_priority_mode_is_still_genuinely_empty(self, qapp):
        """The fix must not paper over the case the warning describes."""
        node = CorrelationMatrixNode()
        node.process_data(_classified_stream(overlap='priority'))
        view = _FigureView(node, CorrelationMatrixDisplayDialog, None)
        view.config['min_particles'] = 2
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        data = view.extract_matrix_data()
        e = data['elements']
        assert np.isnan(data['matrix'][e.index('common'), e.index('carney')])
        dlg = CorrelationMatrixDisplayDialog(view, None)
        dlg._refresh()
        assert 'priority' in dlg._header.text()


class TestGroupByGroupTrivialityFollowsZeroMode:
    """The group x group tautology under TOTAL PARTICLE only BINDS under the
    both-present rule, and the mask must say so.

    Found in manual QA 2026-08-26. The mask was unconditional on scope alone,
    so widening the zero mode replaced a real number with a bare marker --
    silent on-screen data loss, and in the actively misleading direction:
    the wider modes exist precisely to measure CO-OCCURRENCE, and group x
    group is the cell that measures it.
    """

    def _view(self, qapp, overlap, zero_mode, scope=cv.SCOPE_TOTAL_PARTICLE):
        from results.results_matrix import ZERO_MODE_CONFIG_KEY
        node = CorrelationMatrixNode()
        node.process_data(_classified_stream(overlap=overlap))
        view = _FigureView(node, CorrelationMatrixDisplayDialog, None)
        view.config['min_particles'] = 2
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        view.config[cv.SCOPE_CONFIG_KEY] = scope
        view.config[ZERO_MODE_CONFIG_KEY] = zero_mode
        return view

    def _gxg(self, view):
        data = view.extract_matrix_data()
        e = data['elements']
        i, j = e.index('common'), e.index('carney')
        return data, i, j

    def test_both_present_still_replaces_the_tautology(self, qapp):
        """The original behaviour is the one case that was always right: the
        pair is correlated over exactly the rows where the columns are
        identical, so r is pinned to 1 and carries nothing."""
        data, i, j = self._gxg(
            self._view(qapp, 'double_count', ZERO_MODE_BOTH))
        assert abs(data['matrix'][i, j] - 1.0) < 1e-9
        assert data['exact_trivial'][i, j]
        assert not data['partial_trivial'][i, j]

    @pytest.mark.parametrize('zero_mode', [ZERO_MODE_EITHER, ZERO_MODE_ALL])
    def test_wider_modes_annotate_instead_of_replacing(self, qapp, zero_mode):
        """Rows where a particle is in one group but not the other come back
        in, the columns stop being identical, and r stops being 1 -- so the
        number must survive. Still annotated: the shared rows remain
        identical, so it is inflated by construction."""
        data, i, j = self._gxg(
            self._view(qapp, 'double_count', zero_mode))
        r = data['matrix'][i, j]
        assert not np.isnan(r)
        assert abs(r - 1.0) > 1e-6, "r must no longer be pinned to 1"
        assert not data['exact_trivial'][i, j], "value must not be replaced"
        assert data['partial_trivial'][i, j], "but it IS still contaminated"

    def test_priority_anti_correlation_reaches_the_screen(self, qapp):
        """The starkest case. Under ``priority`` the groups are mutually
        exclusive, so with zeros included they anti-correlate strongly --
        a real, interesting result that was being blanked to a bare '*'."""
        view = self._view(qapp, 'priority', ZERO_MODE_EITHER)
        data, i, j = self._gxg(view)
        r = data['matrix'][i, j]
        assert not np.isnan(r)
        assert r < -0.3, r
        assert not data['exact_trivial'][i, j]
        dlg = CorrelationMatrixDisplayDialog(view, None)
        dlg._refresh()
        # Read what is DRAWN, not just the mask -- masks have been right here
        # while the screen was wrong.
        texts = _cell_texts(dlg)
        assert f'{r:.2f}{TRIVIALITY_MARKER}' in texts, sorted(set(texts))

    def test_by_definition_is_unmarked_in_every_zero_mode(self, qapp):
        """Scope still decides first: different isotope sets are summed, so
        the cell is informative however the zeros are handled."""
        for zm in (ZERO_MODE_BOTH, ZERO_MODE_EITHER, ZERO_MODE_ALL):
            data, i, j = self._gxg(self._view(
                qapp, 'double_count', zm, scope=cv.SCOPE_DEFINITION))
            assert not data['exact_trivial'][i, j], zm
            assert not data['partial_trivial'][i, j], zm

    def test_isotope_by_group_marking_is_unaffected(self, qapp):
        """Part-whole contamination is a property of the sum, not of which
        particles the pair is correlated over -- it must not move."""
        for zm in (ZERO_MODE_BOTH, ZERO_MODE_EITHER, ZERO_MODE_ALL):
            view = self._view(qapp, 'double_count', zm)
            data = view.extract_matrix_data()
            e = data['elements']
            assert data['partial_trivial'][e.index('27Al'), e.index('common')], zm

    def test_empty_note_is_not_claimed_when_the_region_populates(self, qapp):
        """``_group_note`` said group x group is empty under 'priority'. With
        zeros included it is not empty, so the note would contradict the grid
        the user is looking at."""
        view = self._view(qapp, 'priority', ZERO_MODE_EITHER)
        dlg = CorrelationMatrixDisplayDialog(view, None)
        dlg._refresh()
        header = dlg._header.text()
        assert 'is empty' not in header, header
        assert 'mutual' in header or 'anti-correlate' in header, header

    def test_empty_note_is_still_shown_under_both_present(self, qapp):
        """And the original note must survive where it is still true."""
        view = self._view(qapp, 'priority', ZERO_MODE_BOTH)
        dlg = CorrelationMatrixDisplayDialog(view, None)
        dlg._refresh()
        assert 'empty' in dlg._header.text()

    def test_non_classifier_matrices_are_untouched(self, view_and_dialog):
        """No groups means no masks at all, in any zero mode -- this fix must
        not reach an ordinary isotope matrix."""
        from results.results_matrix import ZERO_MODE_CONFIG_KEY
        view, _ = view_and_dialog
        for zm in (ZERO_MODE_BOTH, ZERO_MODE_EITHER, ZERO_MODE_ALL):
            view.config[ZERO_MODE_CONFIG_KEY] = zm
            data = view.extract_matrix_data()
            assert 'exact_trivial' not in data, zm


class TestPartWholeMasks:
    def test_total_particle_marks_every_contributing_isotope(self, classified):
        view, _ = classified
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        data = view.extract_matrix_data()
        e = data['elements']
        partial = data['partial_trivial']
        assert partial[e.index('27Al'), e.index('common')]
        # Fe is not in common's EXPRESSION, but under TOTAL PARTICLE it still
        # feeds common's sum, so it is part-whole too.
        assert partial[e.index('56Fe'), e.index('common')]

    def test_by_definition_narrows_the_contaminated_set(self, classified):
        view, _ = classified
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        view.config[cv.SCOPE_CONFIG_KEY] = cv.SCOPE_DEFINITION
        data = view.extract_matrix_data()
        e = data['elements']
        assert not data['partial_trivial'][e.index('56Fe'), e.index('common')]
        # carney's expression names 27Al alone, so its column IS Al ->
        # correlation of 1 by construction -> exact, not partial.
        assert data['exact_trivial'][e.index('27Al'), e.index('carney')]

    def test_default_scope_is_total_particle(self, classified):
        """BY DEFINITION collapses a single-isotope group to a 1x1 -- i.e.
        nothing -- so it is a power-user view, not a sane default."""
        view, _ = classified
        assert view.classifier_scope() == cv.SCOPE_TOTAL_PARTICLE

    def test_part_whole_cells_are_annotated_not_replaced(self, classified):
        view, dlg = classified
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        dlg._refresh()
        texts = _cell_texts(dlg)
        annotated = [t for t in texts
                     if t.endswith(TRIVIALITY_MARKER) and len(t) > 1]
        assert annotated, texts
        # A part-whole cell that really does compute to 1.00 keeps its number.
        assert any(t.startswith('1.00') for t in annotated), annotated

    def test_a_genuine_correlation_is_not_marked(self, classified):
        """Al/Ti genuinely co-vary at ~0.99 here and are not definitionally
        linked -- that number must stay clean."""
        view, dlg = classified
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        data = view.extract_matrix_data()
        e = data['elements']
        i, j = e.index('27Al'), e.index('49Ti')
        assert not data['exact_trivial'][i, j]
        assert not data['partial_trivial'][i, j]

    def test_header_stats_exclude_part_whole_by_default(self, classified):
        view, dlg = classified
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_SERIES
        view.config[PART_WHOLE_IN_STATS_KEY] = False
        dlg._refresh()
        excluded = dlg._header.text()
        view.config[PART_WHOLE_IN_STATS_KEY] = True
        dlg._refresh()
        included = dlg._header.text()
        assert excluded != included


class TestMatrixPanelsRole:
    def test_extract_matrix_data_defers_to_panel_data(self, classified):
        view, _ = classified
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_FACET
        assert view.extract_matrix_data() is None
        assert view.extract_panel_data()

    def test_single_sample_gives_one_matrix_per_group(self, classified):
        view, dlg = classified
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_FACET
        dlg._refresh()
        titles = [a.get_title() for a in dlg.figure.get_axes() if a.get_title()]
        assert any('common' in t for t in titles), titles
        assert any('carney' in t for t in titles), titles

    def test_multi_sample_gives_one_matrix_per_sample(self, qapp):
        a = _classified_stream('A')
        b = _classified_stream('B')
        multi = dict(a)
        multi.update({'type': 'multiple_sample_data', 'sample_names': ['A', 'B'],
                      'particle_data': a['particle_data'] + b['particle_data']})
        node = CorrelationMatrixNode()
        node.process_data(multi)
        view = _FigureView(node, CorrelationMatrixDisplayDialog, None)
        view.config['min_particles'] = 2
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_FACET
        view.config[PANEL_GROUP_CONFIG_KEY] = 'common'
        dlg = CorrelationMatrixDisplayDialog(view, None)
        dlg._refresh()
        titles = [a_.get_title() for a_ in dlg.figure.get_axes() if a_.get_title()]
        assert len(titles) == 2, titles
        assert 'common' in dlg._header.text()

    def test_stale_panel_group_falls_back(self, classified):
        view, _ = classified
        view.config[PANEL_GROUP_CONFIG_KEY] = 'no_longer_exists'
        assert view.panel_group() in view.panel_groups()


class TestMatrixSettingsWiring:
    def _dialog(self, input_data, cfg=None):
        from results.results_matrix import MatrixSettingsDialog
        return MatrixSettingsDialog(dict(cfg or {}), input_data, scope='quantities')

    def test_matrix_has_its_own_arity_offering_groups(self, qapp):
        """Own constant, not a widened ARITY_MULTI_KEY -- otherwise network,
        the ratio nodes and ternary would inherit GROUPS and degenerate."""
        sd = self._dialog(_classified_stream())
        offered = [sd._classifier_group.role_combo.itemData(i)
                   for i in range(sd._classifier_group.role_combo.count())]
        assert set(offered) == {cv.ROLE_SERIES, cv.ROLE_FACET,
                                cv.ROLE_ENCODE, cv.ROLE_OFF}
        assert cv.ROLE_SERIES not in cv.available_roles(cv.ARITY_MULTI_KEY)

    def test_colors_is_offered_but_disabled(self, qapp):
        """Shown-and-explained beats silently missing: a matrix cell is an
        aggregate, so there is no per-particle mark to colour."""
        sd = self._dialog(_classified_stream())
        combo = sd._classifier_group.role_combo
        idx = combo.findData(cv.ROLE_ENCODE)
        assert idx >= 0
        assert not combo.model().item(idx).isEnabled()

    def test_panel_group_and_display_mode_gating(self, qapp):
        a = _classified_stream('A')
        multi = dict(a)
        multi.update({'type': 'multiple_sample_data', 'sample_names': ['A'],
                      'particle_data': a['particle_data']})
        sd = self._dialog(multi)
        rc = sd._classifier_group.role_combo
        rc.setCurrentIndex(rc.findData(cv.ROLE_FACET))
        assert sd.panel_group_combo.isEnabled()
        assert not sd.mode_combo.isEnabled()
        rc.setCurrentIndex(rc.findData(cv.ROLE_OFF))
        assert not sd.panel_group_combo.isEnabled()
        assert sd.mode_combo.isEnabled()

    def test_collect_round_trips_the_new_keys(self, qapp):
        from results.results_matrix import ZERO_MODE_CONFIG_KEY
        sd = self._dialog(_classified_stream())
        sd.zero_mode_combo.setCurrentIndex(
            sd.zero_mode_combo.findData(ZERO_MODE_ALL))
        sd.part_whole_cb.setChecked(True)
        out = sd.collect()
        assert out[ZERO_MODE_CONFIG_KEY] == ZERO_MODE_ALL
        assert out[PART_WHOLE_IN_STATS_KEY] is True

    def test_classifier_methods_route_through_the_figure_view(self, qapp):
        """Same trap that hid a day of heatmap work: these are config-derived
        and must resolve against the FIGURE's config, not the node's."""
        node = CorrelationMatrixNode()
        node.process_data(_classified_stream())
        view = _FigureView(node, CorrelationMatrixDisplayDialog, None)
        view.config[cv.ROLE_CONFIG_KEY] = cv.ROLE_FACET
        view.config[cv.SCOPE_CONFIG_KEY] = cv.SCOPE_DEFINITION
        view.config[PANEL_GROUP_CONFIG_KEY] = 'carney'
        assert node.config.get(cv.ROLE_CONFIG_KEY) is None
        assert view.classifier_role() == cv.ROLE_FACET
        assert view.classifier_scope() == cv.SCOPE_DEFINITION
        assert view.panel_group() == 'carney'


class TestDiagonalTrivialityMarker:
    def test_diagonal_is_marked_and_real_values_are_not(self, view_and_dialog):
        _, dlg = view_and_dialog
        dlg._refresh()
        texts = _cell_texts(dlg)
        assert len(texts) == 9
        diag = [0, 4, 8]  # row-major, no NaN cells in this fixture
        assert all(texts[k] == TRIVIALITY_MARKER for k in diag), texts
        assert not any(texts[k] == TRIVIALITY_MARKER
                       for k in range(9) if k not in diag), texts

    def test_a_genuine_r_of_one_stays_a_number(self, view_and_dialog):
        """The whole reason the marker exists: Fe/Ni really do correlate at
        1.00 here, and that must NOT be flattened into the same glyph as the
        diagonal."""
        _, dlg = view_and_dialog
        dlg._refresh()
        texts = _cell_texts(dlg)
        assert texts[1] == texts[3] == '1.00', texts

    def test_both_label_mode_keeps_the_particle_count(self, view_and_dialog):
        """A trivial cell's particle count is a real observation (how many
        particles carry that element) -- only the r half is replaced."""
        view, dlg = view_and_dialog
        view.config['cell_label'] = 'Both'
        dlg._refresh()
        texts = _cell_texts(dlg)
        marked = [t for t in texts if t.startswith(TRIVIALITY_MARKER + '\n')]
        assert len(marked) == 3, texts
        for t in marked:
            count = t.split('\n')[1]
            assert count.isdigit() and int(count) > 0, t

    def test_particle_count_mode_shows_no_marker(self, view_and_dialog):
        """That mode never prints an r at all, so there is nothing to mark."""
        view, dlg = view_and_dialog
        view.config['cell_label'] = 'Particle count'
        dlg._refresh()
        texts = _cell_texts(dlg)
        assert TRIVIALITY_MARKER not in texts, texts
        assert all(t.isdigit() for t in texts), texts

    def test_hiding_the_diagonal_still_wins(self, view_and_dialog):
        """``show_diagonal`` blanks those cells entirely; the marker must not
        resurrect them."""
        view, dlg = view_and_dialog
        view.config['show_diagonal'] = False
        dlg._refresh()
        texts = _cell_texts(dlg)
        assert TRIVIALITY_MARKER not in texts, texts
        assert len(texts) == 6

    def test_difference_matrix_diagonal_is_marked_too(self, qapp):
        """A difference matrix's diagonal is 1 - 1 = 0: still fixed by
        construction, still not evidence."""
        base = _stream()
        multi = {
            'type': 'multiple_sample_data', 'sample_names': ['S1', 'S2'],
            'particle_data': (
                [dict(p, source_sample='S1') for p in base['particle_data']]
                + [dict(p, source_sample='S2') for p in base['particle_data']]),
            'selected_isotopes': base['selected_isotopes'],
        }
        node = CorrelationMatrixNode()
        node.process_data(multi)
        view = _FigureView(node, CorrelationMatrixDisplayDialog, None)
        view.config['display_mode'] = 'Difference Matrix'
        dlg = CorrelationMatrixDisplayDialog(view, None)
        dlg._refresh()
        texts = _cell_texts(dlg)
        assert texts.count(TRIVIALITY_MARKER) == 3, texts


class TestExplicitTrivialityMasks:
    """The part-whole (annotating) behaviour, plus caller-supplied exact
    cells. No production caller passes these yet -- they arrive with the
    classifier pass -- so they are exercised directly here."""

    MAT = np.array([[1.0, 0.87, 0.10],
                    [0.87, 1.0, 0.20],
                    [0.10, 0.20, 1.0]])

    def _draw(self, dlg, exact=None, partial=None):
        dlg.figure.clear()
        ax = dlg.figure.add_subplot(111)
        dlg._draw_matrix_ax(ax, self.MAT, ['A', 'B', 'C'], {},
                            exact_trivial=exact, partial_trivial=partial)
        return [t.get_text() for t in ax.texts]

    def test_partial_mask_annotates_without_destroying_the_value(self, view_and_dialog):
        _, dlg = view_and_dialog
        partial = np.zeros((3, 3), dtype=bool)
        partial[0, 1] = partial[1, 0] = True
        texts = self._draw(dlg, partial=partial)
        assert texts.count(f'0.87{TRIVIALITY_MARKER}') == 2, texts
        assert '0.20' in texts, texts  # untouched ordinary cell

    def test_extra_exact_cells_replace_the_value(self, view_and_dialog):
        _, dlg = view_and_dialog
        exact = np.zeros((3, 3), dtype=bool)
        exact[0, 2] = exact[2, 0] = True
        texts = self._draw(dlg, exact=exact)
        # 3 diagonal (always) + the 2 requested
        assert texts.count(TRIVIALITY_MARKER) == 5, texts

    def test_diagonal_is_marked_even_when_no_mask_is_passed(self, view_and_dialog):
        _, dlg = view_and_dialog
        texts = self._draw(dlg)
        assert texts.count(TRIVIALITY_MARKER) == 3, texts
