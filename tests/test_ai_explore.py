# -*- coding: utf-8 -*-
"""Tests for the exploration helpers and the small assistant fixes.

Covers the automatic first look, fixing failed code without using a turn,
shortening old turns, orphan reasoning tags, the figure checks that used
to raise false alarms, ternary plots and the list of preloaded tools.
"""
import pytest

from results.ai.data import Dataset
from results.ai.exploration import (
    MAX_EXPLORE_FIXES, ExplorationState, compact_messages, elements_named, first_look, premature_finding_lines,
    samples_named, unbacked_numbers,
)
from results.ai.prompts import build_system_prompt
from results.ai.sandbox import NAN_ON_CATEGORY, execute
from results.ai.synthetic import make_dataset
from results.ai.theme import strip_thinking


@pytest.fixture(scope='module')
def planted():
    """The synthetic dataset with its limits."""
    dc, truth, limits = make_dataset(seed=11)
    ds = Dataset(dc)
    ds.set_limits(limits)
    return ds, truth


def test_first_look_finds_what_was_planted(planted):
    """The screen leads with the planted surprises and lists the rest as unremarkable."""
    ds, truth = planted
    text = first_look(ds)
    assert text.startswith('FIRST LOOK')
    leads = [ln for ln in text.splitlines() if ln.strip()[:2] in {f'{i}.' for i in range(1, 10)}]
    assert '206Pb/207Pb' in leads[0] and truth.pb_sample in leads[0] and 'from natural' in leads[0]
    assert 'Ce/La molar ratio differs' in leads[1] and '2:1' in leads[1] and '1:1' in leads[1]
    assert any('slope' in ln and truth.cela_shift_sample in ln for ln in leads)
    assert any('107Ag + 197Au particles occur only in Spiked_C' in ln for ln in leads)
    assert any('48Ti particles are heavier in Spiked_C' in ln for ln in leads)
    assert 'River_A crust-like' in leads[1] and 'Rudnick & Gao' in leads[1]
    assert any('Ag/Au mass ratio in particles is far from the upper crust' in ln for ln in leads)
    quiet = [ln for ln in text.splitlines() if ln.startswith('Checked, nothing unusual')]
    assert quiet and 'shared particles only by chance' in quiet[0]


def test_first_look_leaves_out_bursts_outliers_and_isotope_pairs(planted):
    """Bursts, outliers and truncation are not screened, and isotopes of one element are not a pair."""
    ds, _ = planted
    text = first_look(ds).lower()
    for word in ('burst', 'outlier', 'truncat', 'detection limit'):
        assert word not in text
    assert '206pb + 207pb' not in text


def test_first_look_single_sample():
    """A single sample skips the between-sample checks but still screens ratios."""
    dc, _, _ = make_dataset(seed=5)
    one = [p for p in dc['particle_data'] if p['source_sample'] == 'River_A']
    ds = Dataset({'type': 'sample_data', 'sample_name': 'River_A', 'particle_data': one})
    text = first_look(ds)
    assert 'differs between samples' not in text and 'heavier in' not in text
    assert 'Ce/La molar ratio is tight in the sample' in text


def _leads(text):
    """The numbered lead lines of a first look."""
    return [ln for ln in text.splitlines() if ln.strip()[:2] in {f'{i}.' for i in range(1, 10)}]


@pytest.mark.parametrize('question, expected', [
    ("Is there anything unusual about iron in this data?", ['Fe']),
    ("Anything odd with 56Fe?", ['Fe']),
    ("Look at Fe-56 and Fe56 over time", ['Fe']),
    ("Tell me about lead", ['Pb']),
    ("Compare Ce and La", ['Ce', 'La']),
    ("Explore the dataset and tell me what is interesting.", []),
    ("In River_A, is aluminum fine?", ['Al']),
    ("Is there any uranium?", []),
])
def test_elements_named(planted, question, expected):
    """Symbols, isotope labels and English names count; absent elements and English words do not."""
    ds, _ = planted
    assert elements_named(ds, question) == expected


def test_first_look_screens_the_named_element(planted):
    """A question about one element puts that element's time burst first."""
    ds, truth = planted
    smp, t0, t1 = truth.burst
    for q in ("Is there anything unusual about iron in this data?", "Is Fe unusual?", "What about 56Fe?"):
        lead = _leads(first_look(ds, q))[0].strip()
        assert lead.startswith('1. 56Fe particles arrive in a burst in ' + smp)
        start, end = (float(x) for x in lead.split(' from ')[1].split(' s:')[0].split(' to '))
        assert t0 - 0.5 <= start <= t0 + 0.5 and t1 - 0.5 <= end <= t1 + 0.5


def test_first_look_says_when_the_named_element_is_quiet(planted):
    """A named element without bursts or outliers is listed as checked."""
    ds, _ = planted
    text = first_look(ds, "Is anything unusual with titanium?")
    assert 'arrive in a burst' not in text
    quiet = [ln for ln in text.splitlines() if ln.startswith('Checked, nothing unusual')][0]
    assert '48Ti arrival in time (no bursts)' in quiet and '48Ti particle mass (no outliers)' in quiet


@pytest.mark.parametrize('question', ["Explore the dataset and tell me what is interesting.",
                                      "Do Fe and Ti occur together?"])
def test_first_look_skips_bursts_for_open_and_pair_questions(planted, question):
    """Open questions and questions about several elements are screened as before."""
    ds, _ = planted
    assert first_look(ds, question) == first_look(ds)


@pytest.mark.parametrize('question, expected', [
    ("Compare River_A and Spiked_C.", ['River_A', 'Spiked_C']),
    ("compare river a with spiked-c", ['River_A', 'Spiked_C']),
    ("What is special about Spiked_C?", ['Spiked_C']),
    ("Explore the dataset and tell me what is interesting.", []),
])
def test_samples_named(planted, question, expected):
    """Sample names match in any case, with underscores, spaces or hyphens."""
    ds, _ = planted
    assert samples_named(ds, question) == expected


def test_first_look_puts_the_compared_samples_first(planted):
    """A comparison question gets the leads about both samples first and none about other samples only."""
    ds, _ = planted
    leads = [ln.strip() for ln in _leads(first_look(ds, "Compare River_A and Spiked_C."))]
    both = [ln for ln in leads if 'River_A' in ln and 'Spiked_C' in ln]
    assert leads[:len(both)] == both
    assert any('48Ti particles are heavier in Spiked_C' in ln for ln in leads[:3])
    assert all('River_A' in ln or 'Spiked_C' in ln for ln in leads)


GUESSED = """res = molar_ratio('Ce', 'La', by='sample')
show_table(res, title='Ce/La molar ratio by sample')
record_finding('Ce/La median ~1.5 in River_A, a fixed stoichiometry', n=161, p=1e-300)
"""


@pytest.mark.parametrize('code, lines', [
    (GUESSED, [3]),
    ("record_finding('Fe/Ni median 0.18 in Ni-Fe-Mo', p=1e-300)\nres = molar_ratio('Ni', 'Mn')\n", []),
    ("res = molar_ratio('Co', 'Mn')\nm = res['median_ratio'].iloc[0]\n"
     "record_finding(f'Co/Mn median {m:.3g}', p=float(res['p_vs_rest'].min()))\n", []),
    ("res = molar_ratio('Co', 'Mn')\nrecord_finding('Co/Mn median %.2f' % res['median_ratio'].iloc[0])\n", []),
    ("res = isotope_ratio('206Pb', '207Pb')\nrecord_finding('206Pb/207Pb natural in every sample at 95% level')\n", []),
    ("res = coincidence('Ti', 'Fe')\nrecord_finding('Ti and Fe meet only by chance')\n", []),
    ("res = coincidence('Ti', 'Fe')\nfor r in [1]:\n    record_finding('ratio 0.98', p=0.63)\n", [3]),
    ("x = 1\nrecord_finding(f'ratio {x} vs 6.34')\n", [2]),
])
def test_premature_finding_lines(code, lines):
    """Numbers typed after new code are flagged; f-strings, earlier results and plain words are not."""
    assert premature_finding_lines(code) == lines


def test_unbacked_numbers():
    """Every decimal and the p of a finding must be among the numbers shown; fold changes are derived."""
    pool = [0.177, 0.1794, 0.654, 6.34, 0.18, 3.76e-160]
    assert unbacked_numbers({'claim': 'Fe/Ni 0.18 vs 6.34, 35.2x apart', 'p': 3.76e-160}, pool) == []
    assert unbacked_numbers({'claim': 'Co/Mn median ~1.0', 'p': 1e-300}, pool) == ['1.0', 'p=1e-300']
    assert unbacked_numbers({'claim': 'Cr/Fe the same', 'p': 0.654, 'effect': 'median 0.5'}, pool) == ['0.5']


def test_vet_findings_sends_guessed_findings_back(planted):
    """A finding written before its result existed is dropped and the turn goes back for a fix."""
    ds, _ = planted
    st = ExplorationState(question='q', max_turns=3)
    st.messages = [{'role': 'user', 'content': 'FIRST LOOK: nothing yet'}]
    st.begin_turn()
    res = execute(GUESSED, ds)
    assert res.findings and not res.error
    problem = st.vet_findings(GUESSED, res)
    assert problem.startswith('record_finding on line 3 types numbers by hand')
    assert res.error == problem and res.findings == []
    assert st.after_code(res.error, False) == 'fix'


def test_vet_findings_keeps_computed_findings(planted):
    """A claim built from the computed values passes, and so does one quoting an earlier table."""
    ds, _ = planted
    st = ExplorationState(question='q', max_turns=3)
    st.messages = [{'role': 'user', 'content': 'TABLE: median_ratio 1.98 | p 4.4e-110'}]
    st.begin_turn()
    code = ("record_finding('Ce/La 1.98 in River_A', p=4.4e-110)\n"
            "res = molar_ratio('Ce', 'La', by='sample')\n"
            "m = res.loc[res['sample'] == 'River_B', 'median_ratio'].iloc[0]\n"
            "record_finding(f'Ce/La median {m:.3g} in River_B', p=float(res['p_vs_rest'].min()))\n")
    res = execute(code, ds)
    assert st.vet_findings(code, res) == '' and len(res.findings) == 2 and not res.error


def test_vet_findings_refuses_invented_numbers_at_the_top(planted):
    """A finding typed at the top must still quote numbers the model was shown."""
    ds, _ = planted
    st = ExplorationState(question='q', max_turns=3)
    st.messages = [{'role': 'user', 'content': 'TABLE: median_ratio 0.177 | p 0.654'}]
    st.begin_turn()
    code = "record_finding('Cr/Fe median 0.5 in all samples', p=0.654)\nprint(1)\n"
    res = execute(code, ds)
    assert st.vet_findings(code, res).startswith('record_finding quotes 0.5, which no result you have seen')


def test_fix_does_not_use_a_turn():
    """Errors are sent back for a fix up to the limit, then the turn counts as failed."""
    st = ExplorationState(question='q', max_turns=3)
    assert st.begin_turn() and st.turn == 1
    for _ in range(MAX_EXPLORE_FIXES):
        assert st.after_code('KeyError', False) == 'fix'
        assert st.begin_turn() and st.turn == 1
    assert st.after_code('KeyError', False) == 'next'
    assert st.failures == 1
    assert st.begin_turn() and st.turn == 2 and st.fixes == 0
    assert st.after_code('', False) == 'next' and st.failures == 0
    assert st.after_code('', True) == 'finish'


def test_two_failed_turns_stop():
    """Two turns that still fail after their fixes end the exploration."""
    st = ExplorationState(question='q', max_turns=10)
    actions = []
    for _ in range(2):
        st.begin_turn()
        for _ in range(MAX_EXPLORE_FIXES + 1):
            actions.append(st.after_code('boom', False))
            if actions[-1] == 'fix':
                st.begin_turn()
    assert actions[-1] == 'finish'


def test_turn_budget():
    """No turn starts past the budget."""
    st = ExplorationState(question='q', max_turns=1)
    assert st.begin_turn()
    assert not st.begin_turn()


def test_compact_messages_keeps_recent_turns_whole():
    """Old turns lose their code and results; the opening and the last turns stay."""
    msgs = [{'role': 'user', 'content': 'USER QUESTION: x'}]
    for k in range(1, 5):
        msgs.append({'role': 'assistant', 'content': f'Testing {k}.\n```python\nprint({k})\n```'})
        msgs.append({'role': 'user', 'content': f'[TURN {k} RESULT]\nlong table {k}'})
    out = compact_messages(msgs, keep_last=2)
    assert out[0] == msgs[0]
    assert out[1]['content'] == 'Testing 1.\n[code omitted]'
    assert out[2]['content'].startswith('[TURN 1 RESULT]') and 'long table 1' not in out[2]['content']
    assert out[-4:] == msgs[-4:]
    assert compact_messages(msgs[:3]) == msgs[:3]


def test_orphan_think_tag_is_removed():
    """Reasoning before a lone closing tag is dropped; normal text is kept."""
    assert strip_thinking('reasoning here\n</think>\n\nThe answer.') == 'The answer.'
    assert strip_thinking('<think>a</think>B') == 'B'
    assert strip_thinking('plain text') == 'plain text'


def test_twin_axis_and_ecdf_raise_no_false_alarm(planted):
    """A twin y axis and an ECDF pass the checks; a bad figure still fails them."""
    ds, _ = planted
    twin = ("v = np.sort(df[col('mass','Ti')].dropna().to_numpy())\n"
            "fig, ax = plt.subplots(); ax.hist(v, bins=np.logspace(-1, 3, 40)); ax.set_xscale('log')\n"
            "ax.set_xlabel('Ti mass (fg)'); ax.set_ylabel('Particles')\n"
            "ax2 = ax.twinx(); ax2.plot(v, np.arange(1, len(v) + 1) / len(v)); ax2.set_ylabel('Cumulative fraction')\n")
    ecdf = ("v = np.sort(df[col('mass','Ti')].dropna().to_numpy())\n"
            "fig, ax = plt.subplots(); ax.step(v, np.arange(1, len(v) + 1) / len(v)); ax.set_xscale('log')\n"
            "ax.set_xlabel('Ti mass (fg)'); ax.set_ylabel('ECDF')\n")
    bad = ("v = np.sort(df[col('mass','Ti')].dropna().to_numpy())\n"
           "fig, ax = plt.subplots(); ax.plot(v, v ** 2, 'o'); ax.set_ylabel('y')\n")
    assert execute(twin, ds, None).warnings == []
    assert execute(ecdf, ds, None).warnings == []
    warns = execute(bad, ds, None).warnings
    assert any('no x-axis label' in w for w in warns) and any('y data span' in w for w in warns)


def test_ternary_plot(planted):
    """Ternary panels draw through plt.subplots and new_figure."""
    ds, _ = planted
    code = ("m = df[df[col('counts','Ag')].notna() & df[col('counts','Au')].notna()]\n"
            "a, b = m[col('mass','Ag')], m[col('mass','Au')]\n"
            "fig, ax = new_figure(projection='ternary'); ax.scatter(a, b, a * 0 + 0.1, s=5)\n"
            "fig2, ax2 = plt.subplots(subplot_kw={'projection': 'ternary'}); ax2.scatter(a, b, b, s=5)\n")
    res = execute(code, ds, None)
    assert res.error == ''
    assert len(res.figures) == 2 and 'ternary projection' in res.figures[0]['description']


def test_prompt_lists_preloaded_tools(planted):
    """The prompt names the preloaded helpers and the ternary recipe."""
    ds, _ = planted
    text = build_system_prompt(ds, 16384)
    assert 'Already loaded, never import them: LogNorm, Normalize' in text
    assert 'PALETTE is a list' in text and "projection='ternary'" in text
    explore = build_system_prompt(ds, 16384, 'explore')
    assert 'fixing it does not use a turn' in explore and 'FIRST LOOK' in explore


@pytest.mark.parametrize('code, expected', [
    ("b = time_bursts('Fe')\nprint(b['sample'])", "b has columns: run, t_from"),
    ("print(df['mass_fg_Fe'].median())", "'mass_fg_56Fe'"),
    ("print(df['107Ag'].sum())", "is an element, not a column"),
    ("e = combination_enrichment()\nprint(e['combination'])", "Did you mean 'combo'?"),
    ("print(binom_test(3, 10))", "stats.binomtest"),
    ("fig, ax = plt.subplots()\nax.scatter(df['t_start'], df['total_mass_fg'], c=df['sample'])", "To colour by sample"),
    ("co_occurrence(by='sample')", "Signature: co_occurrence("),
    ("element_summary('Ti', 'mass')", "element_summary('mass_fg', elements=['Ti'])"),
])
def test_error_hints_name_the_fix(planted, code, expected):
    """The commonest slips of small models come back with the fix named."""
    ds, _ = planted
    res = execute(code, ds, None)
    assert expected in res.error
    assert len(res.error.split('\n')[0]) < 320


def test_stats_functions_by_name(planted):
    """Common scipy.stats functions work without the stats prefix."""
    ds, _ = planted
    res = execute("print(round(kruskal([1, 2, 3], [4, 5, 6]).pvalue, 3), "
                  "round(mannwhitneyu([1, 2, 3], [4, 5, 6]).pvalue, 3))", ds, None)
    assert res.error == '' and res.text == '0.05 0.1'


@pytest.mark.parametrize('code, check', [
    ("show_table(co_occurrence('107Ag', '197Au'))", lambda r: len(r.tables[0]['rows']) == 1),
    ("print(len(element_summary(elements='Ti')))", lambda r: r.text == '1'),
    ("t = df.groupby('sample').size().reset_index().rename(columns={0: 'n'})\nprint(list(t.columns))",
     lambda r: r.text == "['sample', 'n']"),
    ("a = [1, 2]\na.remove(1)\nprint(a)", lambda r: r.text == '[2]'),
    ("fig, ax = plt.subplots()\nsc = ax.scatter(df['t_start'], df['total_mass_fg'], c=df['total_mass_fg'], "
     "norm=plt.Normalize())\nplt.colorbar(sc)\nax.set_xlabel('t (s)')\nax.set_ylabel('Mass (fg)')",
     lambda r: len(r.figures) == 1),
])
def test_common_forms_are_accepted(planted, code, check):
    """Forms small models write often work instead of failing."""
    ds, _ = planted
    res = execute(code, ds, None)
    assert res.error == '' and check(res)


def test_file_access_still_blocked(planted):
    """Allowing rename and remove does not open a path to the file system."""
    ds, _ = planted
    assert 'Blocked' in execute("x = np.os", ds, None).error
    assert 'Blocked' in execute("p = pathlib.Path('x')", ds, None).error


def test_lab_style_is_the_default():
    """Every figure is serif bold without top/right axis lines, and samples get the lab colours."""
    from results.ai.benchmark import make_variant
    from results.ai.figures import LAB_EFFLUENT, LAB_INFLUENT, figure_rc, lab_colors
    dc, _, limits = make_variant('wastewater')
    ds = Dataset(dc)
    ds.set_limits(limits)
    code = ("print(SAMPLE_COLORS['Influent_Day1'], SAMPLE_COLORS['Effluent_Day2'])\n"
            "fig, ax = plt.subplots()\n"
            "for s in samples:\n"
            "    ax.hist(df.loc[df['sample'] == s, col('mass', 'Ti')].dropna(), bins=30, histtype='step', "
            "color=SAMPLE_COLORS[s], label=s)\n"
            "ax.set_xlabel('Ti mass (fg)'); ax.set_ylabel('Particles'); ax.legend()\n")
    res = execute(code, ds, None)
    assert res.error == ''
    assert res.text == f"{LAB_INFLUENT} {LAB_EFFLUENT}"
    fig = res.figures[0]['figure']
    ax = fig.axes[0]
    assert figure_rc(fig)['font.weight'] == 'bold' and figure_rc(fig)['font.family'][-1] == 'DejaVu Sans'
    assert not ax.spines['top'].get_visible() and ax.xaxis.label.get_fontweight() == 'bold'
    assert ax.get_xticklabels()[0].get_fontweight() == 'bold'
    assert lab_colors(['S5-INF-2 10x', 'WWTP1_EFF_1', 'River_A'])['S5-INF-2 10x'] == LAB_INFLUENT
    assert lab_colors(['WWTP1_EFF_1'])['WWTP1_EFF_1'] == LAB_EFFLUENT


def test_user_can_change_the_style(planted):
    """A style change asked for in the code stays with the figure when it is drawn and saved."""
    from results.ai.figures import figure_rc
    ds, _ = planted
    code = ("plt.rcParams['font.weight'] = 'normal'\n"
            "plt.rc('font', family='sans-serif')\n"
            "fig, ax = plt.subplots()\nax.plot([1, 2], [1, 2])\nax.set_xlabel('x'); ax.set_ylabel('y')")
    res = execute(code, ds, None)
    assert res.error == ''
    fig = res.figures[0]['figure']
    rc = figure_rc(fig)
    assert rc['font.weight'] == 'normal' and rc['font.family'] == ['sans-serif']
    assert fig.axes[0].get_xticklabels()[0].get_fontweight() == 'normal'
    assert 'Blocked' not in execute("plt.rcParams['font.size'] = 12", ds, None).error
    assert 'font.nope' in execute("plt.rcParams['font.nope'] = 1", ds, None).error


def test_prompt_describes_the_style(planted):
    """The prompt says the lab style is the default and how to change it, for any samples."""
    ds, _ = planted
    text = build_system_prompt(ds, 16384)
    assert 'SAMPLE_COLORS[s]' in text and 'lab style (Times New Roman bold' in text
    assert "plt.rcParams['font.family']" in text and 'lab_style' not in text


def test_special_characters_draw_in_the_lab_font(planted):
    """Characters Times New Roman lacks, like superscript minus, come from a fallback font without warnings."""
    import warnings
    ds, _ = planted
    code = ("fig, ax = plt.subplots()\nax.plot([0.001, 10], [1, 2])\nax.set_xscale('log')\n"
            "ax.set_xlabel('Particles cm⁻³ ∝ mass'); ax.set_ylabel('Count')")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        res = execute(code, ds, None)
    assert res.error == ''
    assert not [w for w in caught if 'missing from font' in str(w.message)]


def test_only_installed_fonts_are_listed():
    """Every font named in the style is installed, so drawing prints no font warnings."""
    from matplotlib import font_manager
    from results.ai.figures import LAB_STYLE
    have = {f.name for f in font_manager.fontManager.ttflist}
    assert all(name in have for name in LAB_STYLE['font.family'])


def test_repeated_code_is_caught_ignoring_comments():
    """The same code with other comments or spacing counts as a repeat; two repeats end it."""
    from results.ai.exploration import ExplorationState
    st = ExplorationState(question='q', max_turns=10)
    st.begin_turn()
    assert st.repeated("x = 1\nshow_table(x)") == 0
    st.begin_turn()
    assert st.repeated("# again\nx = 1\n\nshow_table(x)   ") == 1
    assert not st.too_many_repeats()
    st.begin_turn()
    assert st.repeated("x = 2") == 0
    st.begin_turn()
    assert st.repeated("x = 2  # same") == 0 or st.too_many_repeats()


def test_benchmark_explore_does_not_rerun_repeated_code(planted):
    """A repeated turn is not run again and the model is told so."""
    from results.ai.benchmark import _ask_explore, build_questions
    ds, _ = planted
    dc, truth, _ = make_dataset(seed=11)
    q = next(x for x in build_questions('rivers', dc, truth) if x.category == 'explore')
    code = "PLAN:\n1. Ce+La\nTesting.\n```python\nc = coincidence('Ce', 'La')\nrecord_finding('Ce+La real', p=1e-20)\n```"
    replies = iter([code, code.replace('Testing.', 'Again.'), "EXPLORATION DONE", "**Supported**\n- Ce+La real."])
    sent = []

    def model(messages, system):
        """Replay the replies and keep what was sent."""
        sent.append(messages[-1]['content'])
        return next(replies)
    out = _ask_explore(q, ds, model, 16384)
    assert out.attempts == 1
    assert any(m.startswith('[REPEATED CODE] This is the same code you ran in turn 1') for m in sent)


def test_benchmark_iron_question_gets_the_burst_lead(planted):
    """The benchmark passes the question to the first look."""
    from results.ai.benchmark import _ask_explore, build_questions
    ds, truth = planted
    dc, _, _ = make_dataset(seed=11)
    q = next(x for x in build_questions('rivers', dc, truth) if x.qid.endswith('explore_iron'))
    sent = []

    def model(messages, system):
        """Stop at once and keep what was sent."""
        sent.append(messages[-1]['content'])
        return "EXPLORATION DONE"
    _ask_explore(q, ds, model, 16384)
    assert f"56Fe particles arrive in a burst in {truth.burst[0]}" in sent[0]


@pytest.mark.parametrize('text', ["Ti is 3.3x heavier in Spiked_C (median 1.86 fg vs 0.558 fg in River_A).",
                                  "Spiked_C carries larger Ti particles than River_A.",
                                  "Ti particles in Spiked_C are more massive."])
def test_explore_compare_accepts_heavier(planted, text):
    """Heavier and more massive Ti count as the larger-Ti finding."""
    from results.ai.benchmark import build_questions, score_exploration
    _, truth = planted
    dc, _, _ = make_dataset(seed=11)
    q = next(x for x in build_questions('rivers', dc, truth) if x.qid.endswith('explore_compare'))
    assert score_exploration(q, text)[0]
    assert not score_exploration(q, "Ti is the same in both samples.")[0]


@pytest.mark.parametrize('legend', [True, False])
def test_nan_on_a_category_axis_gets_a_clear_error(planted, legend):
    """A NaN point on a text axis is explained instead of matplotlib's internal error."""
    ds, _ = planted
    code = ("fig, ax = plt.subplots()\n"
            "ax.scatter(['River_A'], [1.0], label='River_A')\n"
            "ax.scatter(['Spiked_C'], [float('nan')], label='Spiked_C')\n"
            "ax.set_ylabel('Ce/La')\n" + ("ax.legend()\n" if legend else ""))
    res = execute(code, ds)
    assert res.error == f"Figure 1 could not be drawn — {NAN_ON_CATEGORY}"


def test_benchmark_explore_without_tests_fails(planted):
    """A summary that only restates the first look, with no code run, does not pass."""
    from results.ai.benchmark import _ask_explore, build_questions
    ds, truth = planted
    dc, _, _ = make_dataset(seed=11)
    q = next(x for x in build_questions('rivers', dc, truth) if x.qid.endswith('explore_iron'))
    summary = f"**Supported**\n- There is a burst of Fe particles in {truth.burst[0]} around 20 to 22 s."
    replies = iter(["PLAN:\n1. Fe burst", "Testing the Fe burst.", summary])

    def model(messages, system):
        """Plan, never write code, then restate the screen."""
        return next(replies)
    out = _ask_explore(q, ds, model, 16384)
    assert not out.passed and out.detail.endswith('no test ran without an error')


def test_benchmark_explore_with_a_test_passes(planted):
    """The same summary passes once a test ran and a computed finding was recorded."""
    from results.ai.benchmark import _ask_explore, build_questions
    ds, truth = planted
    dc, _, _ = make_dataset(seed=11)
    q = next(x for x in build_questions('rivers', dc, truth) if x.qid.endswith('explore_iron'))
    code = ("PLAN:\n1. Fe burst\nTesting the Fe burst.\n```python\nb = time_bursts('Fe')\nshow_table(b)\n"
            "record_finding(f\"Fe burst in {b['run'].iloc[0]}\", p=float(b['p'].min()))\n```")
    summary = f"**Supported**\n- There is a burst of Fe particles in {truth.burst[0]} around 20 to 22 s."
    replies = iter([code, "EXPLORATION DONE", summary])

    def model(messages, system):
        """One real test, then the summary."""
        return next(replies)
    out = _ask_explore(q, ds, model, 16384)
    assert out.passed, out.detail


def test_rules_for_p_values_and_truncation(planted):
    """The explore rules forbid placeholder p-values; truncation comes from the truncated column."""
    from results.ai.analysis import SIGNATURES
    ds, _ = planted
    prompt = build_system_prompt(ds, 16384, 'explore', 10)
    assert 'Never pass p=1.0 or p=1e-300 as a placeholder' in prompt
    assert 'Never type a number you have not been shown' in prompt
    sd = next(desc for sig, desc in SIGNATURES if sig.startswith('size_distribution'))
    assert "truncated is 'yes'" in sd
