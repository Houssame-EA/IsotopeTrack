"""Tests for the discovery detectors and replicate handling behind Insights.

Covers :mod:`results.insights.replicates`, every detector in
:mod:`results.insights.discovery`, the group-aware comparison and signature
analysers, the per-group search and merge, and how a card's samples turn into
a selector.

Each detector is checked on planted data, where the effect is put there on
purpose, and on clean data, where it must stay quiet.
"""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from results import results_reader as rr
from results.insights import discovery as disc
from results.insights.replicates import (
    ReplicateGroup, auto_group_map, describe_grouping, replicate_root, resolve_groups,
    user_group_map,
)


class FakeNode:
    """Stand-in for a workflow node, carrying whatever attributes a test needs."""

    def __init__(self, node_type, **kw):
        """Create a node of *node_type* with arbitrary extra attributes."""
        self.node_type = node_type
        self.__dict__.update(kw)


class FakeScene:
    """Stand-in for the canvas scene."""

    def __init__(self, nodes=()):
        """Create a scene holding *nodes*."""
        self.workflow_nodes = list(nodes)

    def selectedItems(self):
        """Return no selection."""
        return []


class FakeWindow:
    """Stand-in for the main window, holding the loaded particle pool."""

    def __init__(self, pool):
        """Expose *pool* as ``sample_particle_data``."""
        self.sample_particle_data = pool


@pytest.fixture(autouse=True)
def _clear_cache():
    """Isolate each test from contexts cached by its neighbours."""
    rr.invalidate_context_cache()
    yield
    rr.invalidate_context_cache()


def context(pool, nodes=()):
    """Build an analysis context over *pool*.

    Args:
        pool: Sample name to particle dicts.
        nodes: Canvas nodes, for user-defined replicate groups.

    Returns:
        The analysis context.
    """
    rr.invalidate_context_cache()
    return rr.build_context(FakeScene(nodes), FakeWindow(pool))


def tissue(n, fe_mu, seed, drift=0.0):
    """Particles with Fe, and Al and Ti now and then, timed 50 ms apart.

    Args:
        n: How many particles.
        fe_mu: Mean of log Fe.
        seed: Random seed.
        drift: How far log Fe falls from the start to the end of the run.

    Returns:
        Particle dicts.
    """
    rng = random.Random(seed)
    out = []
    for i in range(n):
        t = i * 0.05
        elements = {"56Fe": math.exp(rng.gauss(fe_mu - drift * i / n, 0.6))}
        if rng.random() < 0.6:
            elements["27Al"] = math.exp(rng.gauss(2.0, 0.6))
        if rng.random() < 0.4:
            elements["48Ti"] = math.exp(rng.gauss(1.5, 0.6))
        out.append({"elements": elements, "start_time": t, "end_time": t + 0.001})
    return out


@pytest.mark.parametrize("name,root", [
    ("liver_1", "liver"),
    ("liver_rep2", "liver"),
    ("ctrl_R1", "ctrl"),
    ("HgSe_1mg_r1", "HgSe_1mg"),
    ("2024_Au_A", "2024_Au"),
    ("blank 3", "blank"),
    ("S1", "S1"),
    ("Au_10nm", "Au_10nm"),
])
def test_replicate_root(name, root):
    """Replicate suffixes are stripped, and a word ending in r is left alone."""
    assert replicate_root(name) == root


def test_auto_groups_need_two_members():
    """A lone sample with a suffix is not a group of one."""
    mapping = auto_group_map(["liver_1", "liver_2", "kidney_1"])
    assert mapping == {"liver_1": "liver", "liver_2": "liver"}


def test_user_groups_override_names_only_for_their_samples():
    """User groups win for the samples they name; the rest are still guessed."""
    groups = resolve_groups(
        ["liver_1", "liver_2", "kidney_1", "kidney_2", "blank"],
        {"kidney_1": "kidney", "kidney_2": "kidney"},
    )
    by_name = {g.name: g for g in groups}
    assert by_name["kidney"].source == "user"
    assert by_name["liver"].source == "auto"
    assert by_name["liver"].members == ("liver_1", "liver_2")
    assert by_name["blank"].source == "single"


def test_user_can_split_samples_that_look_like_replicates():
    """Giving each sample its own group keeps look-alike names apart."""
    groups = resolve_groups(["site_A", "site_B"], {"site_A": "site_A", "site_B": "site_B"})
    assert all(not g.is_replicated for g in groups)


def test_user_group_map_reads_both_selector_kinds():
    """Multi selectors give groups by sum_group; single selectors by summed replicates."""
    multi = FakeNode("multiple_sample_selector",
                     sample_config={"a": {"sum_group": "x"}, "b": {"sum_group": "x"},
                                    "c": {"sum_group": ""}})
    single = FakeNode("sample_selector", sum_replicates=True,
                      replicate_samples=["dog_1", "dog_2"])
    mapping = user_group_map(FakeScene([multi, single]), ["a", "b", "c", "dog_1", "dog_2"])
    assert mapping == {"a": "x", "b": "x", "dog_1": "dog", "dog_2": "dog"}


def test_describe_grouping():
    """The header says how many samples, groups and replicated groups there are."""
    groups = resolve_groups(["liver_1", "liver_2", "kidney"])
    text = describe_grouping(groups)
    assert "3 samples" in text and "1 with replicates" in text
    assert "no replicates" in describe_grouping(resolve_groups(["a", "b"]))


def replicated_pool(liver3_mu=2.0):
    """Two tissues with three replicates each; kidney carries three times the Fe."""
    return {
        "liver_1": tissue(400, 2.0, 1), "liver_2": tissue(400, 2.0, 2),
        "liver_3": tissue(400, liver3_mu, 3),
        "kidney_1": tissue(400, 3.1, 4), "kidney_2": tissue(400, 3.1, 5),
        "kidney_3": tissue(400, 3.1, 6),
    }


def test_comparison_compares_groups_with_replicate_test():
    """Replicated groups are compared as groups, on replicate medians."""
    cards = rr._analyse_comparison(context(replicated_pool()))
    assert cards
    card = cards[0]
    assert card.elements == ("56Fe",)
    assert "ANOVA on replicate medians" in card.reasoning
    assert set(card.samples) == {f"{t}_{i}" for t in ("liver", "kidney") for i in (1, 2, 3)}
    assert card.sample_groups["liver_1"] == "liver"


def test_replicates_of_one_material_are_never_compared():
    """Replicates of the same material produce no comparison card at all."""
    pool = {"liver_1": tissue(400, 2.0, 1), "liver_2": tissue(400, 2.6, 2)}
    assert rr._analyse_comparison(context(pool)) == []
    assert rr._analyse_signature(context(pool)) == []


def test_difference_smaller_than_replicate_spread_is_rejected():
    """A group gap that does not beat the spread between replicates is not reported."""
    pool = {
        "alpha_1": tissue(400, 2.0, 1), "alpha_2": tissue(400, 2.9, 2),
        "beta_1": tissue(400, 2.5, 3), "beta_2": tissue(400, 3.3, 4),
    }
    assert not [c for c in rr._analyse_comparison(context(pool)) if c.elements == ("56Fe",)]


def test_replicates_that_agree_get_an_agreement_card():
    """Agreeing replicates are reported as such, with every replicate kept separate."""
    cards = disc.analyse_replicates(context(replicated_pool()))
    agree = [c for c in cards if "agree" in c.title]
    assert len(agree) == 2
    assert all(v == "" for c in agree for v in c.sample_groups.values())


def test_the_odd_replicate_is_named():
    """With three replicates, the one off from its agreeing siblings is named."""
    cards = disc.analyse_replicates(context(replicated_pool(liver3_mu=2.9)))
    flagged = [c for c in cards if "disagrees" in c.title]
    assert len(flagged) == 1
    assert "liver_3" in flagged[0].title
    assert flagged[0].elements[0] == "56Fe"


def test_two_disagreeing_replicates_are_not_blamed():
    """With two replicates the disagreement is reported without picking one."""
    pool = {"liver_1": tissue(400, 2.0, 1), "liver_2": tissue(400, 2.8, 2)}
    cards = disc.analyse_replicates(context(pool))
    assert cards and "disagree" in cards[0].title
    assert "not possible to tell" in cards[0].reasoning


def cerium(n, oxide, seed=1):
    """Ce particles with either a CeO+ shadow at mass 156 or an independent 156 element."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        ce = math.exp(rng.gauss(4.0, 0.9))
        elements = {"140Ce": ce}
        if oxide and ce * 0.02 > 1.0:
            elements["156Gd"] = ce * 0.02 * math.exp(rng.gauss(0, 0.1))
        if not oxide and rng.random() < 0.3:
            elements["156Gd"] = math.exp(rng.gauss(2.0, 0.8))
        out.append({"elements": elements})
    return out


def test_interference_finds_an_oxide():
    """A mass at M+16 that tracks M at a small fixed ratio is flagged as MO+."""
    cards = disc.analyse_interference(context({"S": cerium(1500, True)}))
    assert len(cards) == 1
    assert cards[0].elements == ("140Ce", "156Gd")
    assert "CeO" in cards[0].title
    assert cards[0].config["log_x"] and cards[0].config["log_y"]


def test_interference_ignores_an_independent_element():
    """A genuine element at M+16 is not mistaken for an oxide."""
    assert disc.analyse_interference(context({"S": cerium(1500, False)})) == []


def ilmenite(n, fixed, seed=2):
    """Fe and Ti particles, at a fixed 1:1 molar ratio or independent."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        size = math.exp(rng.gauss(0, 1))
        ti = size * (math.exp(rng.gauss(0, 0.08)) if fixed else math.exp(rng.gauss(0, 1.2)))
        out.append({"elements": {"56Fe": size * 100, "48Ti": ti * 100},
                    "element_moles_fmol": {"56Fe": size, "48Ti": ti}})
    return out


def test_stoichiometry_finds_a_fixed_molar_ratio():
    """A tight molar ratio becomes a molar ratio card naming the simple ratio."""
    cards = disc.analyse_stoichiometry(context({"S": ilmenite(800, True)}))
    assert len(cards) == 1
    assert cards[0].node_type == "molar_ratio_plot"
    assert "1:1" in cards[0].reasoning


def test_stoichiometry_ignores_elements_that_only_share_size():
    """Two elements that merely grow with particle size have no fixed ratio."""
    assert disc.analyse_stoichiometry(context({"S": ilmenite(800, False)})) == []


def test_correlation_card_flags_a_ratio_that_shifts_with_size():
    """Elements that rise together but not in proportion are called out."""
    rng = random.Random(7)
    particles = []
    for _ in range(800):
        size = math.exp(rng.gauss(0, 1))
        particles.append({"elements": {"56Fe": size * 100,
                                       "48Ti": 50 * size ** 0.15 * math.exp(rng.gauss(0, 0.02))}})
    cards = [c for c in rr._analyse_correlation(context({"S": particles}))
             if c.node_type == "correlation_plot"]
    assert cards and "not proportional" in cards[0].reasoning


def test_correlation_card_flags_a_fixed_ratio():
    """Elements in a fixed ratio are described as one phase."""
    cards = [c for c in rr._analyse_correlation(context({"S": ilmenite(800, True)}))
             if c.node_type == "correlation_plot"]
    assert cards and "nearly constant" in cards[0].reasoning


def neodymium(n, seed=3):
    """Pr only ever with Nd; Ti and Fe never together; six U+Th particles."""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        elements = {}
        if rng.random() < 0.4:
            elements["146Nd"] = rng.uniform(1, 50)
            if rng.random() < 0.5:
                elements["141Pr"] = rng.uniform(1, 20)
        if rng.random() < 0.5:
            if "146Nd" not in elements:
                elements["48Ti"] = rng.uniform(1, 50)
        else:
            elements["56Fe"] = rng.uniform(1, 50)
        if i < 6:
            elements["238U"] = 5.0
            elements["232Th"] = 3.0
        out.append({"elements": elements})
    return out


def test_cooccurrence_finds_both_kinds_of_rule():
    """An always-together pair and an avoiding pair are both reported."""
    titles = [c.title for c in disc.analyse_cooccurrence(context({"S": neodymium(2000)}))]
    assert "146Nd comes with 141Pr" in titles
    assert any("avoid each other" in t for t in titles)


def test_cooccurrence_quiet_for_independent_elements():
    """Elements scattered independently give no co-occurrence card."""
    rng = random.Random(4)
    particles = [{"elements": {el: 1.0 for el in ("56Fe", "27Al", "48Ti")
                               if rng.random() < 0.5} or {"56Fe": 1.0}}
                 for _ in range(2000)]
    assert disc.analyse_cooccurrence(context({"S": particles})) == []


def test_rare_find_lists_true_companions_once():
    """Six U particles with Th are one rare find, without chance companions."""
    cards = disc.analyse_rare(context({"S": neodymium(2000)}))
    assert len(cards) == 1
    assert cards[0].elements == ("238U", "232Th")


def test_detection_limit_cut_is_flagged_and_clean_data_is_not():
    """A distribution truncated at its low end is flagged; a full one is not."""
    rng = random.Random(5)
    cut = [v for v in (math.exp(rng.gauss(3, 1.0)) for _ in range(3000)) if v > 30]
    flagged = disc.analyse_detection_limit(context({"S": [{"elements": {"56Fe": v}} for v in cut]}))
    assert flagged and flagged[0].config["show_det_limit"]
    full = [{"elements": {"56Fe": math.exp(rng.gauss(3, 0.5))}} for _ in range(2000)]
    assert disc.analyse_detection_limit(context({"S": full})) == []


def test_time_drift_is_found_and_steady_runs_are_quiet():
    """A signal falling through a run is flagged; a steady run is not."""
    cards = disc.analyse_time(context({"run": tissue(3000, 3.0, 9, drift=1.0)}))
    assert cards and cards[0].category == "time"
    assert cards[0].node_type == "figure_builder"
    assert cards[0].samples == ("run",)
    assert cards[0].config["panels"][0]["kind"] == "timeline"
    assert disc.analyse_time(context({"run": tissue(3000, 3.0, 9)})) == []


def test_size_composition_trend():
    """A coating element whose share falls with size is reported."""
    rng = random.Random(6)
    particles = []
    for _ in range(600):
        core = math.exp(rng.gauss(1.0, 0.8))
        shell = 0.3 * core ** 0.5
        particles.append({"elements": {"79Au": core * 50, "107Ag": shell * 50},
                          "element_mass_fg": {"79Au": core, "107Ag": shell}})
    cards = disc.analyse_size_composition(context({"S": particles}))
    titles = [c.title for c in cards]
    assert "107Ag share falls with particle size" in titles
    assert all(c.node_type == "figure_builder" and c.elements == () for c in cards)


def test_within_detectors_run_per_group_and_name_where_they_held():
    """An oxide present in only one tissue is reported for that tissue alone."""
    pool = {
        "ree_1": cerium(800, True, 1), "ree_2": cerium(800, True, 2),
        "clean_1": cerium(800, False, 3), "clean_2": cerium(800, False, 4),
    }
    cards = rr.analyse(context(pool), categories=["interference"])
    assert len(cards) == 1
    assert set(cards[0].samples) == {"ree_1", "ree_2"}
    assert "Only in ree" in cards[0].reasoning


def test_findings_in_every_group_are_merged_into_one_card():
    """The same finding in two groups becomes one card covering both."""
    pool = {"alpha_1": cerium(800, True, 1), "alpha_2": cerium(800, True, 2),
            "beta_1": cerium(800, True, 3), "beta_2": cerium(800, True, 4)}
    cards = rr.analyse(context(pool), categories=["interference"])
    assert len(cards) == 1
    assert len(cards[0].samples) == 4
    assert "Seen in every group" in cards[0].reasoning


def test_node_type_filter_runs_only_what_is_needed():
    """Asking for one node type returns only cards of that type."""
    cards = rr.analyse(context(replicated_pool()), node_types={"concentration_comparison"})
    assert cards
    assert {c.node_type for c in cards} == {"concentration_comparison"}
    assert rr.analysers_for({"triangle_plot"}) == ["ternary"]


def test_every_detector_feeds_a_known_node_type():
    """No detector can propose a node the panel does not list, and no clustering."""
    for analyser in rr._ANALYSERS.values():
        assert analyser.node_types
        assert analyser.node_types <= set(rr.NODE_TYPE_META)
        assert analyser.key in rr._CAT_META
    assert "clustering_plot" not in rr.NODE_TYPE_META


def test_full_search_is_fast_enough():
    """Every detector over six samples finishes well inside the panel's patience."""
    import time
    ctx = context(replicated_pool())
    start = time.time()
    cards = rr.analyse(ctx)
    assert cards
    assert time.time() - start < 10.0


def test_selection_units_pool_groups_and_keep_singles():
    """Grouped samples form one unit; ungrouped samples stand alone."""
    s = rr.Suggestion("t", "r", "comparison", 0.5, "concentration_comparison",
                      samples=("k_1", "k_2", "blank"),
                      sample_groups={"k_1": "k", "k_2": "k", "blank": ""})
    assert rr.selection_units(s, None) == [("k", ("k_1", "k_2")), ("blank", ("blank",))]
    assert "k (2 replicates)" in rr.describe_samples(s, None)


def test_selection_units_fall_back_to_the_scope():
    """A card without samples covers the whole scope, grouped as the scope is."""
    scope = rr.resolve_scope(FakeScene(), FakeWindow({"alpha_1": tissue(30, 2, 1),
                                                      "alpha_2": tissue(30, 2, 2)}))
    s = rr.Suggestion("t", "r", "composition", 0.5, "pie_chart_plot")
    assert rr.selection_units(s, scope) == [("alpha", ("alpha_1", "alpha_2"))]


def test_merge_keeps_strongest_wording():
    """Merging keeps the most confident version of a finding."""
    g1, g2 = ReplicateGroup("g1", ("a",)), ReplicateGroup("g2", ("b",))
    weak = rr.Suggestion("t", "weak", "x", 0.4, "histogram_plot", elements=("56Fe",))
    strong = rr.Suggestion("t", "strong", "x", 0.9, "histogram_plot", elements=("56Fe",))
    merged = disc.merge_group_findings([(weak, g1), (strong, g2)], ["a", "b"], 2)
    assert len(merged) == 1
    assert merged[0].reasoning.startswith("strong")
    assert merged[0].samples == ("a", "b")


def test_mass_helpers():
    """Isotope labels parse in both orders and oxide relations are recognised."""
    assert disc.mass_symbol("56Fe") == (56, "Fe")
    assert disc.mass_symbol("Fe56") == (56, "Fe")
    assert disc.mass_symbol("total") == (None, None)
    assert disc.mass_related("140Ce", "156Gd")
    assert disc.mass_related("138Ba", "69Ga")
    assert not disc.mass_related("56Fe", "48Ti")
