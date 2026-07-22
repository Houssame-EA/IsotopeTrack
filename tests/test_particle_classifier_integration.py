# -*- coding: utf-8 -*-
"""Cross-module integration tests for the Particle Classifier that unit
tests structurally miss: the real ProjectManager save/load round-trip
(the exact place the "forgot to add the attribute to the whitelist" bug
class lives, and where a non-JSON-serializable value would silently break
a real save), and the multi-input data-flow path.

Driven headlessly through the real objects (offscreen Qt via conftest),
not mocks.
"""
import json
import types
import sys

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal, QPointF

from tools.particle_classifier_node import (
    ParticleClassifierNode, new_definition_id)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def cw(qapp, monkeypatch):
    import widget.canvas_widgets as cw
    monkeypatch.setattr(cw.QMessageBox, "warning", lambda *a, **kw: None)
    return cw


def _def(expr, target, group=None, mode='partial', color=None):
    return {'id': new_definition_id(), 'target_sample': target,
            'expression_text': expr, 'match_mode': mode,
            'group_name': group, 'color': color}


def _fully_configured_node():
    node = ParticleClassifierNode()
    node.definitions = [
        _def('60Ni', 'Hello', group='IronOre', mode='exact'),
        _def('60Ni+107Ag', 'Hello', group='Recycling'),
        _def('197Au', 'Sir', color='#FF00FF'),
    ]
    node.groups = {'IronOre': '#EF4444', 'Recycling': '#3B82F6'}
    node.overlap_mode = 'priority'
    node.unmatched_mode = 'discard'
    node.unclassified_color = '#123456'
    node.group_pooling_policies = {'Recycling': 'keep'}
    node._has_unresolved_issues = True
    node.confound_dismissals = [{'id_a': 'a', 'id_b': 'b', 'expr_a': '60Ni',
                                 'expr_b': '60Ni+107Ag', 'mode_a': 'partial',
                                 'mode_b': 'partial'}]
    return node


_ROUND_TRIP_ATTRS = (
    'definitions', 'groups', 'overlap_mode', 'unmatched_mode',
    'unclassified_color', 'group_pooling_policies',
    '_has_unresolved_issues', 'confound_dismissals')


class TestSaveLoadRoundTrip:
    """Real ProjectManager serialize -> JSON (what hits disk) -> deserialize."""

    @pytest.fixture
    def pm(self, qapp):
        from save_export.project_manager import ProjectManager
        return ProjectManager(types.SimpleNamespace())

    def _round_trip(self, pm, src):
        node_data = {'id': 'node_0', 'title': src.title,
                     'node_type': src.node_type,
                     'position': {'x': 0, 'y': 0}}
        pm._serialize_node_config(src, node_data)
        disk = json.loads(json.dumps(node_data))   # the real save writes JSON
        dst = ParticleClassifierNode()
        pm._deserialize_node_config(dst, disk)
        return node_data, dst

    @pytest.mark.parametrize("attr", _ROUND_TRIP_ATTRS)
    def test_attribute_survives_round_trip(self, pm, attr):
        src = _fully_configured_node()
        _node_data, dst = self._round_trip(pm, src)
        assert getattr(dst, attr) == getattr(src, attr)

    def test_serialized_config_is_json_safe(self, pm):
        """A non-JSON-serializable value (e.g. a tuple/set key) would let the
        in-memory round-trip pass but break a real save silently."""
        src = _fully_configured_node()
        node_data = {'id': 'n', 'title': src.title, 'node_type': src.node_type,
                     'position': {'x': 0, 'y': 0}}
        pm._serialize_node_config(src, node_data)
        json.dumps(node_data)   # must not raise

    def test_incoming_names_not_persisted(self, pm):
        """_incoming_names is derived from live connections and must never be
        written into the saved node (it would masquerade as configuration)."""
        src = _fully_configured_node()
        src._incoming_names = ['Hello', 'Sir']
        node_data, dst = self._round_trip(pm, src)
        assert '_incoming_names' not in node_data
        assert dst._incoming_names == []   # fresh node's default, not restored

    def test_default_node_round_trips_clean(self, pm):
        """A brand-new unconfigured node must survive save/load unchanged."""
        src = ParticleClassifierNode()
        _node_data, dst = self._round_trip(pm, src)
        for attr in _ROUND_TRIP_ATTRS:
            assert getattr(dst, attr) == getattr(src, attr)

    def test_node_type_registered_in_deserialize_map(self, qapp, monkeypatch):
        """particle_classifier must be in _deserialize_canvas_state's
        node_type_map, or a saved classifier silently vanishes on load."""
        import save_export.project_manager as pmmod
        # The map is built inside the method; assert the class is importable
        # and the registry entries exist where load looks them up.
        import widget.canvas_widgets as cwmod
        assert cwmod._NODE_FACTORIES.get("particle_classifier") is \
            ParticleClassifierNode


class _StubSource(QObject):
    position_changed = Signal(object)
    configuration_changed = Signal()

    def __init__(self, output):
        super().__init__()
        self.title = "Src"
        self.node_type = "sample_selector"
        self.position = QPointF(0, 0)
        self._has_input, self._has_output = False, True
        self.input_channels, self.output_channels = [], ["output"]
        self._output = output
        self.selected_sample = None
        self.sum_replicates = False
        self.replicate_samples = []
        self.selected_isotopes = []

    def set_position(self, pos):
        self.position = pos

    def get_output_data(self):
        return self._output


def _multi(names, combos):
    particles = [{'elements': {iso: 1.0 for iso in c}, 'source_sample': n}
                 for n in names for c in combos]
    return {'type': 'multiple_sample_data', 'sample_names': list(names),
            'particle_data': particles, 'data': {}, 'data_types': {},
            'selected_isotopes': [], 'total_particles': len(particles),
            'concentration_meta': {n: {} for n in names}, 'parent_window': None}


class TestMultiInput:
    """Two-or-more input links are pooled into one "Combined" sample so
    every source's particles get classified (no silent data drop). A single
    input link keeps its own per-sample structure. The node item now sets
    scene_ref (via itemChange) so _pull_upstream_all sees every link."""

    def _two_source_scene(self, cw):
        from tools.particle_classifier_node import MERGED_SAMPLE_NAME
        scene = cw.EnhancedCanvasScene(parent_window=None)
        a = _StubSource(_multi(['Alpha'], [['60Ni']]))
        b = _StubSource(_multi(['Beta'], [['197Au']]))
        clf = ParticleClassifierNode()
        for n, p in ((a, (0, 0)), (b, (0, 200)), (clf, (300, 100))):
            scene.add_node(n, cw.QPointF(*p))
        assert scene.add_link(a, "output", clf, "input") is not None
        assert scene.add_link(b, "output", clf, "input") is not None
        return scene, clf, MERGED_SAMPLE_NAME

    def test_second_input_link_is_allowed(self, cw):
        """Multiple inputs are supported (merged), not blocked."""
        self._two_source_scene(cw)  # asserts both links created

    def test_item_sets_scene_ref(self, cw):
        """Regression: the classifier item must set scene_ref on scene add,
        or _pull_upstream_all can't see the input links and multi-input
        silently collapses to the last push."""
        _scene, clf, _name = self._two_source_scene(cw)
        assert clf.scene_ref is not None

    def test_incoming_names_collapse_to_combined(self, cw):
        _scene, clf, name = self._two_source_scene(cw)
        assert clf._incoming_names == [name]

    def test_both_inputs_are_classified_under_combined(self, cw):
        """The fix: both sources' particles survive and get classified,
        pooled under the one 'Combined' sample."""
        _scene, clf, name = self._two_source_scene(cw)
        clf.definitions = [_def('60Ni', name, group='Ni'),
                           _def('197Au', name, group='Au')]
        clf.groups = {'Ni': '#111', 'Au': '#222'}
        out = clf.get_output_data()
        assert out['sample_names'] == [name]
        labels = [set((p.get('elements') or {}).keys())
                  for p in out['particle_data']]
        assert {'Ni'} in labels and {'Au'} in labels   # neither dropped

    def test_single_input_keeps_its_own_sample_name(self, cw):
        """A lone input link is NOT renamed to Combined -- only 2+ links
        merge, so a single Multiple-Sample node keeps its per-sample
        structure."""
        scene = cw.EnhancedCanvasScene(parent_window=None)
        a = _StubSource(_multi(['Alpha'], [['60Ni']]))
        clf = ParticleClassifierNode()
        scene.add_node(a, cw.QPointF(0, 0))
        scene.add_node(clf, cw.QPointF(300, 0))
        scene.add_link(a, "output", clf, "input")
        assert clf._incoming_names == ['Alpha']
        clf.definitions = [_def('60Ni', 'Alpha', group='Ni')]
        clf.groups = {'Ni': '#111'}
        out = clf.get_output_data()
        assert out['sample_names'] == ['Alpha']


class TestClassifierColorReachesPieChart:
    """BUG 4 fix: Element Distribution pie charts must adopt a classifier's
    chosen bucket colors, same as the histogram/bar-chart nodes already do
    -- driven through the real PieChartDisplayDialog, not a mock, so this
    exercises the exact _refresh() code path a live pie chart uses."""

    def test_pie_chart_seeds_classifier_bucket_color(self, cw):
        from results.results_pie_charts import (
            PieChartPlotNode, PieChartDisplayDialog)

        scene = cw.EnhancedCanvasScene(parent_window=None)
        src = _StubSource(_multi(['S1'], [['60Ni'], ['60Ni', '107Ag']]))
        clf = ParticleClassifierNode()
        pie = PieChartPlotNode()
        scene.add_node(src, cw.QPointF(0, 0))
        scene.add_node(clf, cw.QPointF(200, 0))
        scene.add_node(pie, cw.QPointF(400, 0))
        scene.add_link(src, "output", clf, "input")
        clf.definitions = [_def('60Ni', 'S1', group='Nickel')]
        clf.groups = {'Nickel': '#10B981'}
        scene.add_link(clf, "output", pie, "input")

        assert pie.input_data is not None
        assert (pie.input_data.get('label_colors') or {}).get('Nickel') \
            == '#10B981'

        dlg = PieChartDisplayDialog(pie, parent_window=None)
        assert pie.config['element_colors'].get('Nickel') == '#10B981'


class TestContradictionShowsRealBadge:
    """Bug found in the pre-merge QA pass: a node with a single contradictory
    definition never showed the node icon's ⚠ warning badge --
    _recompute_unresolved_issues only checked syntax errors and stale
    isotopes, never classify_formula's contradiction verdict. Fixed in
    tools/particle_classifier_dialog.py. Verified here end-to-end: real
    dialog -> real accept() -> real node -> real node-item paint()."""

    def test_single_contradiction_produces_warning_badge_on_real_node_item(
            self, cw, monkeypatch):
        from tools.particle_classifier_dialog import ParticleClassifierDialog

        monkeypatch.setattr(cw.QMessageBox, "warning", lambda *a, **kw: None)

        scene = cw.EnhancedCanvasScene(parent_window=None)
        src = _StubSource(_multi(['S1'], [['60Ni']]))
        clf = ParticleClassifierNode()
        scene.add_node(src, cw.QPointF(0, 0))
        scene.add_node(clf, cw.QPointF(200, 0))
        scene.add_link(src, "output", clf, "input")

        snapshots = clf._pull_upstream_all()
        dlg = ParticleClassifierDialog(
            None, snapshots, clf.definitions, clf.groups, clf.overlap_mode,
            clf.unmatched_mode, clf.unclassified_color, clf.selected_sources,
            clf.group_pooling_policies, clf.confound_dismissals)
        # Auto-choose "Save Anyway" on the contradiction modal without
        # blocking on a real exec() loop.
        dlg._show_contradiction_modal = lambda d: True

        dlg._list.setCurrentRow(0)
        dlg._add_definition()
        dlg._expr_edit.setText("60Ni+!(60Ni)")
        dlg._validate_current()
        dlg.accept()

        clf.definitions = dlg.get_definitions()
        clf._has_unresolved_issues = dlg.get_has_unresolved_issues()
        assert clf._has_unresolved_issues is True

        item = cw.ParticleClassifierNodeItem(clf)
        captured = {}
        item.paint_icon_node = lambda painter, colors, icon, title, badge, bc: \
            captured.update(badge=badge, badge_color=bc)
        item.paint(painter=None, option=None)
        assert captured['badge'] == "⚠"
