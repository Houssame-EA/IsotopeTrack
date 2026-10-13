"""spICP-ToF-MS analyses the assistant calls instead of writing them itself.

Every function takes the :class:`~results.ai.data.Dataset` first; the sandbox
binds it, so generated code calls ``compare_samples("Ti")`` directly. Each
returns a pandas DataFrame the model can pass straight to ``show_table``.
Test results and caveats go in ``df.attrs["note"]``, which the table header
shows.

The statistics are deliberately conventional: Kruskal-Wallis and
Mann-Whitney for distributions, a Poisson test of shared events against
the expected random coincidence rate, chi-square
residuals for combination enrichment, and Holm's correction whenever many
tests are run together.
"""
from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd

from results.ai.data import QUANTITY_UNITS, resolve_quantity

_RNG_SEED = 7
P_FLOOR = 1e-300


def pfloor(p):
    """Keep a p-value off exact zero, which floating point reaches but statistics never does.

    Args:
        p: p-value or array of p-values.

    Returns:
        The same, with values below 1e-300 raised to 1e-300; NaN stays NaN.
    """
    if np.ndim(p):
        arr = np.asarray(p, dtype=float)
        return np.where(np.isfinite(arr), np.maximum(arr, P_FLOOR), arr)
    p = float(p)
    return max(p, P_FLOOR) if p == p else p


def holm(pvalues):
    """Holm step-down adjustment of a list of p-values.

    Args:
        pvalues (list): Raw p-values, NaN allowed.

    Returns:
        numpy.ndarray: Adjusted p-values in the original order.
    """
    p = np.asarray(pvalues, dtype=float)
    out = np.full(p.shape, np.nan)
    ok = np.where(np.isfinite(p))[0]
    if not ok.size:
        return out
    order = ok[np.argsort(p[ok])]
    m = order.size
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[idx]))
        out[idx] = running
    return out


def _note(df, text):
    """Attach a caveat or test result to a table and return it."""
    prev = df.attrs.get('note', '')
    df.attrs['note'] = f"{prev}  {text}".strip() if prev else text
    return df


def _values(ds, quantity, element, mask=None):
    """Positive, finite values of one quantity of one element."""
    col = ds.column(quantity, element)
    s = ds.df[col]
    if mask is not None:
        s = s[mask]
    s = s[np.isfinite(s) & (s > 0)]
    return s


def _median_ci(values, n_boot=400):
    """Bootstrap 95 % interval of the median."""
    v = np.asarray(values, dtype=float)
    if v.size < 5:
        return float('nan'), float('nan')
    rng = np.random.default_rng(_RNG_SEED)
    idx = rng.integers(0, v.size, size=(n_boot, v.size))
    meds = np.median(v[idx], axis=1)
    return float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))


def _geo(v):
    """Geometric mean and geometric standard deviation of positive values."""
    v = np.asarray(v, dtype=float)
    v = v[v > 0]
    if not v.size:
        return float('nan'), float('nan')
    lg = np.log(v)
    return float(np.exp(lg.mean())), float(np.exp(lg.std(ddof=1))) if v.size > 1 else float('nan')


def _log_kde(v):
    """KDE of log10 values, or ``None`` when there are too few or identical values."""
    v = np.asarray(v, dtype=float)
    v = v[v > 0]
    if v.size < 10:
        return None
    lg = np.log10(v)
    if np.ptp(lg) == 0:
        return None
    try:
        from scipy.stats import gaussian_kde
        return gaussian_kde(lg)
    except Exception:
        return None


def _log_mode(v):
    """Most likely value of a positive distribution, from a KDE on the log scale."""
    v = np.asarray(v, dtype=float)
    v = v[v > 0]
    kde = _log_kde(v)
    if kde is None:
        return float(v[0]) if v.size else float('nan')
    lg = np.log10(v)
    grid = np.linspace(lg.min(), lg.max(), 512)
    return float(10 ** grid[np.argmax(kde(grid))])


def _height_at(v, x):
    """Height of the log-scale density at *x*, as a share of its peak."""
    kde = _log_kde(v)
    if kde is None or not (x and x > 0):
        return float('nan')
    lg = np.log10(np.asarray(v, dtype=float)[np.asarray(v) > 0])
    grid = np.linspace(lg.min(), lg.max(), 512)
    peak = float(np.max(kde(grid)))
    return float(kde([np.log10(x)])[0] / peak) if peak > 0 else float('nan')


def _groups(ds, by):
    """Group keys for *by*, which is ``sample``, ``run``, ``class`` or ``None``."""
    if by in (None, '', 'all'):
        return [('all', np.ones(len(ds.df), dtype=bool))]
    if by not in ds.df.columns:
        raise KeyError(f"Cannot group by '{by}'. Use 'sample', 'run' or 'class'.")
    keys = ds.samples if by == 'sample' else list(dict.fromkeys(ds.df[by].tolist()))
    return [(k, (ds.df[by] == k).to_numpy()) for k in keys]


def element_summary(ds, quantity='diameter_nm', by=None, elements=None):
    """Detection frequency and distribution of a quantity for every element.

    Args:
        ds: The dataset.
        quantity (str): Quantity to describe.
        by (str): ``sample``, ``run``, ``class`` or ``None`` for everything.
        elements (list): Elements to include, all by default.

    Returns:
        pandas.DataFrame: One row per element (and group) with ``n``,
        ``pct_of_particles``, ``median``, ``geo_mean``, ``p5``, ``p95`` and,
        when calibrated, the detection limit ``lod``.
    """
    q = resolve_quantity(quantity)
    els = [ds.resolve_element(e) for e in elements] if elements else ds.elements
    rows = []
    for gname, mask in _groups(ds, by):
        total = int(mask.sum())
        for el in els:
            col = f'{q}_{el}'
            if col not in ds.df.columns:
                continue
            v = ds.df.loc[mask, col]
            v = v[np.isfinite(v) & (v > 0)].to_numpy()
            if not v.size:
                continue
            gm, _ = _geo(v)
            row = {'element': el}
            if by:
                row[by] = gname
            row.update({
                'n': int(v.size),
                'pct_of_particles': 100.0 * v.size / max(total, 1),
                'median': float(np.median(v)),
                'geo_mean': gm,
                'p5': float(np.percentile(v, 5)),
                'p95': float(np.percentile(v, 95)),
            })
            if q in ('counts', 'mass_fg', 'diameter_nm'):
                lod = ds.lod(el, q, gname if by == 'sample' else None)
                row['lod'] = lod if lod else float('nan')
            rows.append(row)
    out = pd.DataFrame(rows)
    return _note(out, f"Quantity: {q} ({QUANTITY_UNITS.get(q, '')}).")


def compare_samples(ds, element, quantity='diameter_nm', by='sample', groups=None):
    """Compare one element's distribution across samples, with tests.

    Args:
        ds: The dataset.
        element (str): Element to compare.
        quantity (str): Quantity to compare.
        by (str): ``sample``, ``run`` or ``class``.
        groups (list): Restrict to these groups.

    Returns:
        pandas.DataFrame: Per group ``n``, ``detection_rate_pct``, ``median``
        with its bootstrap 95 % interval, ``geo_mean``, ``p95``, and
        ``p_vs_rest``, the Holm-adjusted Mann-Whitney p-value of the group
        against all the others. The Kruskal-Wallis result is in the note.
    """
    from scipy import stats
    q = resolve_quantity(quantity)
    el = ds.resolve_element(element)
    col = ds.column(q, el)
    parts = [(g, m) for g, m in _groups(ds, by) if not groups or g in groups]
    rows, samples = [], []
    for gname, mask in parts:
        v = ds.df.loc[mask, col]
        v = v[np.isfinite(v) & (v > 0)].to_numpy()
        samples.append(v)
        lo, hi = _median_ci(v)
        gm, gsd = _geo(v)
        rows.append({
            by: gname,
            'n': int(v.size),
            'detection_rate_pct': 100.0 * v.size / max(int(mask.sum()), 1),
            'median': float(np.median(v)) if v.size else float('nan'),
            'median_ci_low': lo,
            'median_ci_high': hi,
            'geo_mean': gm,
            'geo_sd': gsd,
            'p95': float(np.percentile(v, 95)) if v.size else float('nan'),
        })
    raw_p = []
    for i, v in enumerate(samples):
        rest = np.concatenate([s for j, s in enumerate(samples) if j != i]) if len(samples) > 1 else np.array([])
        if v.size >= 3 and rest.size >= 3:
            raw_p.append(pfloor(stats.mannwhitneyu(v, rest, alternative='two-sided').pvalue))
        else:
            raw_p.append(float('nan'))
    out = pd.DataFrame(rows)
    if len(out):
        out['p_vs_rest'] = holm(raw_p)
    usable = [s for s in samples if s.size >= 3]
    if len(usable) >= 2:
        h = stats.kruskal(*usable)
        _note(out, f"Kruskal-Wallis across {len(usable)} groups: H = {h.statistic:.3g}, p = {pfloor(h.pvalue):.3g}.")
    detected = [int(r['n']) for r in rows]
    totals = [int(m.sum()) for _, m in parts]
    if len(parts) >= 2 and sum(detected) > 0:
        table = np.array([detected, [t - d for t, d in zip(totals, detected)]])
        if (table.sum(axis=1) > 0).all():
            chi = stats.chi2_contingency(table)
            _note(out, f"Detection rate differs between groups: chi2 = {chi[0]:.3g}, p = {pfloor(chi[1]):.3g}.")
    return _note(out, f"{el}, {q} ({QUANTITY_UNITS.get(q, '')}).")


def _pair_counts(ds, a, b):
    """Particles with a, with b, with both, and in total."""
    ca = ds.df[f'counts_{a}'].notna().to_numpy() if f'counts_{a}' in ds.df else np.zeros(len(ds.df), bool)
    cb = ds.df[f'counts_{b}'].notna().to_numpy() if f'counts_{b}' in ds.df else np.zeros(len(ds.df), bool)
    return ca, cb


def coincidence(ds, element_a, element_b):
    """Are particles with both elements real, or two particles arriving together?

    Two independent particles land in the same event when their start times
    fall within the sum of their event widths. With ``n_A`` and ``n_B``
    events in a run of length ``T`` and mean widths ``w_A`` and ``w_B``,
    the expected number of chance A+B events is
    ``n_A * n_B * (w_A + w_B) / T``. The observed count is tested against
    that expectation with a one-sided Poisson test, run by run.

    Args:
        ds: The dataset.
        element_a (str): First element.
        element_b (str): Second element.

    Returns:
        pandas.DataFrame: Per run and in total: ``n_a``, ``n_b``,
        ``observed_both``, ``expected_by_chance``, ``ratio`` and ``p``. A
        ratio near 1 means the pairs are explained by coincidence.
    """
    from scipy import stats
    a = ds.resolve_element(element_a)
    b = ds.resolve_element(element_b)
    ca, cb = _pair_counts(ds, a, b)
    df = ds.df
    dur = (df['duration_ms'].to_numpy() / 1000.0)
    runs = ds.runs().set_index('run')
    rows = []
    tot_obs, tot_exp = 0, 0.0
    for run, info in runs.iterrows():
        m = (df['run'] == run).to_numpy()
        na, nb = int((ca & m).sum()), int((cb & m).sum())
        both = int((ca & cb & m).sum())
        span = float(info['span_s'])
        wa = np.nanmean(dur[ca & m]) if na else np.nan
        wb = np.nanmean(dur[cb & m]) if nb else np.nan
        if span > 0 and np.isfinite(wa) and np.isfinite(wb):
            expected = na * nb * (wa + wb) / span
        else:
            expected = float('nan')
        p = pfloor(stats.poisson.sf(both - 1, expected)) if expected == expected and expected > 0 else float('nan')
        rows.append({'run': run, 'n_a': na, 'n_b': nb, 'observed_both': both,
                     'expected_by_chance': expected,
                     'ratio': both / expected if expected and expected == expected else float('nan'),
                     'p': p, 'span_s': span})
        tot_obs += both
        if expected == expected:
            tot_exp += expected
    p_tot = pfloor(stats.poisson.sf(tot_obs - 1, tot_exp)) if tot_exp > 0 else float('nan')
    rows.append({'run': 'all runs', 'n_a': int(ca.sum()), 'n_b': int(cb.sum()),
                 'observed_both': tot_obs, 'expected_by_chance': tot_exp,
                 'ratio': tot_obs / tot_exp if tot_exp > 0 else float('nan'),
                 'p': p_tot, 'span_s': float(runs['span_s'].sum()) if len(runs) else float('nan')})
    out = pd.DataFrame(rows)
    if tot_exp > 0:
        verdict = ('more often than chance — a real association'
                   if p_tot < 0.01 and tot_obs > 2 * tot_exp else
                   'about as often as chance — likely coincidence'
                   if p_tot >= 0.01 else 'somewhat more often than chance')
        _note(out, f"{a} + {b}: observed {tot_obs}, expected by chance {tot_exp:.3g}; "
                   f"they occur together {verdict}.")
    _note(out, "Run spans are taken from the particle times, a lower bound of the acquisition time.")
    return out


def co_occurrence(ds, elements=None, min_count=10, top=25):
    """Which element pairs share particles more, or less, than chance allows.

    In spICP-ToF-MS almost every event is one particle, so the right
    baseline for a pair is not "independent detection" but the random
    coincidence rate of :func:`coincidence`. Each pair's shared count is
    tested against that rate with a Poisson test in both directions,
    Holm-adjusted over all pairs.

    Args:
        ds: The dataset.
        elements (list): Elements to pair, all by default.
        min_count (int): Ignore elements detected fewer times than this.
        top (int): Keep this many pairs, most significant first.

    Returns:
        pandas.DataFrame: ``a``, ``b``, ``n_a``, ``n_b``, ``n_both``,
        ``expected_by_chance``, ``ratio`` (observed / chance),
        ``pct_of_a`` (share of A particles that also hold B), ``p_adj`` and
        a plain ``verdict``.
    """
    from scipy import stats
    els = [ds.resolve_element(e) for e in elements] if elements else ds.elements
    df = ds.df
    present = {}
    for el in els:
        col = f'counts_{el}'
        if col in df.columns:
            mask = df[col].notna().to_numpy()
            if mask.sum() >= min_count:
                present[el] = mask
    dur = df['duration_ms'].to_numpy() / 1000.0
    runs = ds.runs().set_index('run')
    run_masks = {r: (df['run'] == r).to_numpy() for r in runs.index}
    rows = []
    for a, b in itertools.combinations(present, 2):
        ma, mb = present[a], present[b]
        na, nb, nab = int(ma.sum()), int(mb.sum()), int((ma & mb).sum())
        chance = 0.0
        for r, rm in run_masks.items():
            span = float(runs.at[r, 'span_s'])
            ra, rb = ma & rm, mb & rm
            if span > 0 and ra.any() and rb.any():
                chance += ra.sum() * rb.sum() * (np.nanmean(dur[ra]) + np.nanmean(dur[rb])) / span
        if chance > 0:
            p_hi = float(stats.poisson.sf(nab - 1, chance))
            p_lo = float(stats.poisson.cdf(nab, chance))
            p = pfloor(min(1.0, 2 * min(p_hi, p_lo)))
        else:
            p = float('nan')
        rows.append({'a': a, 'b': b, 'n_a': na, 'n_b': nb, 'n_both': nab,
                     'expected_by_chance': chance,
                     'ratio': nab / chance if chance > 0 else float('nan'),
                     'pct_of_a': 100.0 * nab / na if na else float('nan'),
                     'pct_of_b': 100.0 * nab / nb if nb else float('nan'),
                     'p': p})
    out = pd.DataFrame(rows)
    if not len(out):
        return _note(out, f"No two elements reach {min_count} detections.")
    out['p_adj'] = holm(out['p'].tolist())

    def verdict(r):
        """Plain-language reading of one pair."""
        if not np.isfinite(r['p_adj']):
            if r['expected_by_chance'] == 0 and r['n_both'] == 0:
                return 'never in the same run'
            return 'not enough timing information'
        if r['p_adj'] < 0.01 and r['ratio'] > 1:
            return 'share particles (real association)'
        if r['p_adj'] < 0.01 and r['ratio'] < 1:
            return 'fewer shared events than chance'
        return 'explained by chance coincidence'

    out['verdict'] = out.apply(verdict, axis=1)
    out = out.sort_values(['p_adj', 'n_both'], ascending=[True, False]).head(int(top)).reset_index(drop=True)
    return _note(out, "Poisson test of shared events against the random coincidence rate, Holm-adjusted.")


def coincidence_overview(ds):
    """How many multi-element events could be chance coincidences, run by run.

    With a particle rate ``r`` and a typical event width ``w``, the
    probability that another particle starts inside an event is
    ``1 - exp(-2 r w)``. Comparing that with the observed share of
    multi-element events tells whether those events are mostly real.

    Args:
        ds: The dataset.

    Returns:
        pandas.DataFrame: Per run ``n``, ``rate_per_s``,
        ``median_width_ms``, ``expected_coincident_pct`` and
        ``observed_multi_element_pct``.
    """
    df = ds.df
    rows = []
    for _, r in ds.runs().iterrows():
        m = (df['run'] == r['run']).to_numpy()
        n = int(m.sum())
        span = float(r['span_s'])
        rate = n / span if span > 0 else float('nan')
        w = float(np.nanmedian(df.loc[m, 'duration_ms'])) / 1000.0 if n else float('nan')
        exp_pct = 100.0 * (1 - math.exp(-2 * rate * w)) if rate == rate and w == w else float('nan')
        obs_pct = 100.0 * float((df.loc[m, 'n_elements'] > 1).mean()) if n else float('nan')
        rows.append({'run': r['run'], 'n': n, 'rate_per_s': rate,
                     'median_width_ms': w * 1000.0, 'expected_coincident_pct': exp_pct,
                     'observed_multi_element_pct': obs_pct})
    out = pd.DataFrame(rows)
    return _note(out, "Expected share = 1 - exp(-2 x rate x width), counting every particle as independent.")


def size_distribution(ds, element, quantity='diameter_nm', by='sample'):
    """Shape of one element's size or mass distribution, with truncation checks.

    Args:
        ds: The dataset.
        element (str): Element.
        quantity (str): Usually ``diameter_nm`` or ``mass_fg``.
        by (str): ``sample``, ``run``, ``class`` or ``None``.

    Returns:
        pandas.DataFrame: Per group ``n``, ``mode`` (log-scale KDE peak),
        ``geo_mean``, ``geo_sd``, ``median``, ``p5``, ``p95``, ``lod``,
        ``pct_within_1.5x_lod``, ``height_at_lod_pct`` (the density just
        above the limit, as a share of its peak) and ``truncated``: true
        when the distribution is still at least half its peak height at the
        detection limit, or peaks within 1.2x of it, so part of it is cut off.
    """
    q = resolve_quantity(quantity)
    el = ds.resolve_element(element)
    col = ds.column(q, el)
    rows = []
    for gname, mask in _groups(ds, by):
        v = ds.df.loc[mask, col]
        v = v[np.isfinite(v) & (v > 0)].to_numpy()
        if not v.size:
            continue
        gm, gsd = _geo(v)
        mode = _log_mode(v)
        lod = ds.lod(el, q, gname if by == 'sample' else None) if q in ('counts', 'mass_fg', 'diameter_nm') else None
        near = float(100.0 * np.mean(v <= 1.5 * lod)) if lod else float('nan')
        height = _height_at(v, 1.1 * lod) if lod else float('nan')
        truncated = bool(lod and ((mode == mode and mode <= 1.2 * lod) or (height == height and height >= 0.5)))
        row = {'element': el}
        if by:
            row[by] = gname
        row.update({'n': int(v.size), 'mode': mode, 'geo_mean': gm, 'geo_sd': gsd,
                    'median': float(np.median(v)), 'p5': float(np.percentile(v, 5)),
                    'p95': float(np.percentile(v, 95)),
                    'lod': lod if lod else float('nan'),
                    'pct_within_1.5x_lod': near, 'height_at_lod_pct': 100.0 * height,
                    'truncated': truncated})
        rows.append(row)
    out = pd.DataFrame(rows)
    if len(out) and out['truncated'].any():
        _note(out, "Some distributions are still high at the detection limit: smaller particles were "
                   "not detected, so medians and means are biased high there.")
    if len(out) and not np.isfinite(out['lod']).any():
        _note(out, "No calibrated detection limit is available for this quantity.")
    return _note(out, f"{el}, {q} ({QUANTITY_UNITS.get(q, '')}).")


def near_detection_limit(ds, quantity='mass_fg', factor=1.5, min_count=5):
    """Elements whose detections crowd against the detection limit.

    Args:
        ds: The dataset.
        quantity (str): ``counts``, ``mass_fg`` or ``diameter_nm``.
        factor (float): A value within ``factor`` times the limit counts as close.
        min_count (int): Skip element and sample pairs with fewer detections.

    Returns:
        pandas.DataFrame: Per element and sample ``n``, ``lod``,
        ``median_over_lod`` and ``pct_near_lod``, worst first.
    """
    q = resolve_quantity(quantity)
    rows = []
    for el in ds.elements:
        col = f'{q}_{el}'
        if col not in ds.df.columns:
            continue
        for sample, mask in _groups(ds, 'sample'):
            lod = ds.lod(el, q, sample)
            if not lod:
                continue
            v = ds.df.loc[mask, col]
            v = v[np.isfinite(v) & (v > 0)].to_numpy()
            if v.size < min_count:
                continue
            rows.append({'element': el, 'sample': sample, 'n': int(v.size), 'lod': lod,
                         'median_over_lod': float(np.median(v) / lod),
                         'pct_near_lod': float(100.0 * np.mean(v <= factor * lod))})
    out = pd.DataFrame(rows)
    if not len(out):
        return _note(out, "No calibrated detection limits are available.")
    out = out.sort_values('pct_near_lod', ascending=False).reset_index(drop=True)
    return _note(out, f"Close means within {factor:g}x the detection limit ({q}).")


def find_outliers(ds, quantity='mass_fg', element=None, threshold=5.0, top=50):
    """Particles far outside their element's usual range.

    Uses a robust z-score on the log scale, median and MAD, because particle
    masses and sizes are close to log-normal.

    Args:
        ds: The dataset.
        quantity (str): Quantity to test.
        element (str): One element, or ``None`` for every element.
        threshold (float): Robust z-score above which a particle is an outlier.
        top (int): Keep this many, most extreme first.

    Returns:
        pandas.DataFrame: ``particle`` (row index in ``df``), ``sample``,
        ``element``, ``value``, ``robust_z`` and ``combo``.
    """
    q = resolve_quantity(quantity)
    els = [ds.resolve_element(element)] if element else ds.elements
    rows = []
    for el in els:
        col = f'{q}_{el}'
        if col not in ds.df.columns:
            continue
        s = ds.df[col]
        s = s[np.isfinite(s) & (s > 0)]
        if len(s) < 20:
            continue
        lg = np.log10(s)
        med = float(lg.median())
        mad = float((lg - med).abs().median()) * 1.4826
        if mad <= 0:
            continue
        z = (lg - med) / mad
        hit = z[z.abs() >= threshold]
        for idx, zval in hit.items():
            rows.append({'particle': int(idx), 'sample': ds.df.at[idx, 'sample'], 'element': el,
                         'value': float(s[idx]), 'robust_z': float(zval),
                         'combo': ds.df.at[idx, 'combo']})
    out = pd.DataFrame(rows)
    if len(out):
        out = out.reindex(out['robust_z'].abs().sort_values(ascending=False).index).head(int(top))
        out = out.reset_index(drop=True)
    return _note(out, f"Robust z-score of log10({q}); |z| >= {threshold:g}.")


def time_bursts(ds, element=None, bin_s=None, alpha=0.01):
    """Stretches of a run where particles arrive far faster than usual.

    Arrivals are counted in fixed time bins and each bin is tested against
    the run's median rate with a Poisson test, Bonferroni-corrected over the
    bins. Bursts usually mean contamination, a nebuliser hiccup or a
    carry-over spike rather than the sample itself.

    Args:
        ds: The dataset.
        element (str): Count only particles with this element, or all.
        bin_s (float): Bin width in s, about 1/200 of the run by default.
        alpha (float): Significance level after correction.

    Returns:
        pandas.DataFrame: Flagged bins with ``run``, ``t_from``, ``t_to``,
        ``count``, ``expected`` and ``p``.
    """
    from scipy import stats
    df = ds.df
    mask = np.ones(len(df), dtype=bool)
    if element:
        el = ds.resolve_element(element)
        mask = df[f'counts_{el}'].notna().to_numpy()
    rows, checked = [], 0
    for _, r in ds.runs().iterrows():
        m = mask & (df['run'] == r['run']).to_numpy()
        t = df.loc[m, 't_start'].to_numpy()
        t = t[np.isfinite(t)]
        span = float(r['span_s'])
        if t.size < 20 or span <= 0:
            continue
        width = float(bin_s) if bin_s else max(span / 200.0, 1e-3)
        edges = np.arange(float(r['t0']), float(r['t1']) + width, width)
        if edges.size < 3:
            continue
        counts, edges = np.histogram(t, bins=edges)
        expected = max(float(np.median(counts)), float(t.size) / counts.size * 0.5, 0.5)
        checked += counts.size
        p = pfloor(stats.poisson.sf(counts - 1, expected))
        cut = alpha / counts.size
        for k in np.where(p < cut)[0]:
            rows.append({'run': r['run'], 't_from': float(edges[k]), 't_to': float(edges[k + 1]),
                         'count': int(counts[k]), 'expected': expected,
                         'ratio': counts[k] / expected, 'p': float(p[k])})
    out = pd.DataFrame(rows)
    return _note(out, f"{checked} time bins tested, Bonferroni-corrected at {alpha:g}.")


def combination_enrichment(ds, by='sample', min_count=5, top=30):
    """Element combinations over- or under-represented in a sample.

    Builds the combination by group contingency table and reports cells
    whose adjusted standardised residual is large, the usual follow-up to a
    chi-square test.

    Args:
        ds: The dataset.
        by (str): ``sample``, ``run`` or ``class``.
        min_count (int): Combinations seen fewer times overall are pooled
            into ``other``.
        top (int): Keep this many cells, most extreme first.

    Returns:
        pandas.DataFrame: ``combo``, group, ``observed``, ``expected``,
        ``ratio``, ``residual`` and Holm-adjusted ``p_adj``.
    """
    from scipy import stats
    df = ds.df[ds.df['n_elements'] > 0]
    if by not in df.columns:
        raise KeyError(f"Cannot group by '{by}'.")
    counts = df['combo'].value_counts()
    keep = set(counts[counts >= min_count].index)
    combo = df['combo'].where(df['combo'].isin(keep), 'other')
    table = pd.crosstab(combo, df[by])
    if table.shape[1] < 2 or table.shape[0] < 2:
        return _note(pd.DataFrame(), "Need at least two groups and two combinations.")
    chi2, p_all, _, expected = stats.chi2_contingency(table.to_numpy())
    obs = table.to_numpy().astype(float)
    n = obs.sum()
    row_p = obs.sum(axis=1, keepdims=True) / n
    col_p = obs.sum(axis=0, keepdims=True) / n
    resid = (obs - expected) / np.sqrt(expected * (1 - row_p) * (1 - col_p))
    pvals = pfloor(2 * stats.norm.sf(np.abs(resid)))
    rows = []
    for i, c in enumerate(table.index):
        for j, g in enumerate(table.columns):
            rows.append({'combo': c, by: g, 'observed': int(obs[i, j]),
                         'expected': float(expected[i, j]),
                         'ratio': obs[i, j] / expected[i, j] if expected[i, j] > 0 else float('nan'),
                         'residual': float(resid[i, j]), 'p': float(pvals[i, j])})
    out = pd.DataFrame(rows)
    out['p_adj'] = holm(out['p'].tolist())
    out = out.reindex(out['residual'].abs().sort_values(ascending=False).index).head(int(top))
    out = out.reset_index(drop=True)
    return _note(out, f"Chi-square over all combinations: chi2 = {chi2:.3g}, p = {pfloor(p_all):.3g}.")


def long_format(ds, quantity='diameter_nm', elements=None):
    """One row per particle and element, handy for per-element plots.

    Args:
        ds: The dataset.
        quantity (str): Quantity to unpivot.
        elements (list): Elements to include, all by default.

    Returns:
        pandas.DataFrame: ``particle``, ``sample``, ``run``, ``element`` and ``value``.
    """
    q = resolve_quantity(quantity)
    els = [ds.resolve_element(e) for e in elements] if elements else ds.elements
    parts = []
    for el in els:
        col = f'{q}_{el}'
        if col not in ds.df.columns:
            continue
        s = ds.df[col]
        keep = np.isfinite(s) & (s > 0)
        if not keep.any():
            continue
        parts.append(pd.DataFrame({'particle': ds.df.index[keep], 'sample': ds.df.loc[keep, 'sample'].to_numpy(),
                                   'run': ds.df.loc[keep, 'run'].to_numpy(), 'element': el,
                                   'value': s[keep].to_numpy()}))
    if not parts:
        return pd.DataFrame(columns=['particle', 'sample', 'run', 'element', 'value'])
    return pd.concat(parts, ignore_index=True)


def cluster_particles(ds, elements=None, k=3, algorithm='K-Means', scaling='CLR',
                      quantity='mass_fg', **params):
    """Cluster particles by composition with the Clustering module's engine.

    Uses the same algorithms and scalings as the Clustering node, so a
    result here can be reproduced there.

    Args:
        ds: The dataset.
        elements (list): Elements forming the composition, the ten most
            frequent by default.
        k (int): Number of clusters for algorithms that need one.
        algorithm (str): A Clustering node algorithm, e.g. ``K-Means``,
            ``Hierarchical``, ``Gaussian Mixture``, ``DBSCAN`` or ``HDBSCAN``.
        scaling (str): ``CLR``, ``Robust Z-score``, ``Standardize`` or ``None``.
        quantity (str): Quantity the composition is built from.
        **params: Extra algorithm parameters.

    Returns:
        tuple: ``(summary, labels)``. ``summary`` has one row per cluster
        with ``n``, ``pct``, ``top_elements`` and the mean share of each
        element; ``labels`` is a Series aligned with ``df``, ``-1`` for
        particles left out or marked as noise.
    """
    from results.cluster import live_engine as le
    from results.cluster.tools import ALGO_PARAM_SPECS, run_algorithm
    if algorithm not in ALGO_PARAM_SPECS or algorithm == 'SOM':
        names = ', '.join(a for a in ALGO_PARAM_SPECS if a != 'SOM')
        raise ValueError(f"Unknown algorithm '{algorithm}'. Use one of: {names}")
    q = resolve_quantity(quantity)
    els = [ds.resolve_element(e) for e in elements] if elements else ds.elements[:10]
    cols = [f'{q}_{e}' for e in els if f'{q}_{e}' in ds.df.columns]
    if len(cols) < 2:
        raise ValueError("Clustering needs at least two elements with values.")
    m = ds.df[cols].fillna(0.0).to_numpy(dtype=float)
    keep = (m > 0).any(axis=1)
    X = m[keep]
    if X.shape[0] < max(int(k), 2) * 3:
        raise ValueError("Too few particles to cluster.")
    if scaling == 'CLR':
        Xs = le._clr(X)
    elif scaling == 'Robust Z-score':
        Xs = le._robust_z(X)
    elif scaling == 'Standardize':
        Xs = le._standardize(X)
    else:
        Xs = X
    found = run_algorithm(algorithm, {'k': int(k), **params}, Xs)
    if found is None:
        raise ValueError(f"{algorithm} could not cluster this data with these settings.")
    labels = pd.Series(-1, index=ds.df.index, dtype=int)
    labels[keep] = np.asarray(found, dtype=int)
    share = X / np.where(X.sum(axis=1, keepdims=True) > 0, X.sum(axis=1, keepdims=True), 1.0)
    rows = []
    for c in sorted(set(found.tolist())):
        sel = np.asarray(found) == c
        mean_share = share[sel].mean(axis=0)
        order = np.argsort(mean_share)[::-1]
        row = {'cluster': int(c), 'n': int(sel.sum()), 'pct': 100.0 * sel.sum() / sel.size,
               'top_elements': ', '.join(els[i] for i in order[:3] if mean_share[i] > 0.01)}
        for i, e in enumerate(els):
            row[f'share_{e}'] = float(mean_share[i] * 100.0)
        rows.append(row)
    summary = pd.DataFrame(rows)
    _note(summary, f"{algorithm}, {scaling} scaling, {q} of {len(els)} elements; cluster -1 is noise.")
    return summary, labels


FUNCTIONS = {
    'element_summary': element_summary,
    'compare_samples': compare_samples,
    'coincidence': coincidence,
    'co_occurrence': co_occurrence,
    'coincidence_overview': coincidence_overview,
    'size_distribution': size_distribution,
    'near_detection_limit': near_detection_limit,
    'find_outliers': find_outliers,
    'time_bursts': time_bursts,
    'combination_enrichment': combination_enrichment,
    'long_format': long_format,
    'cluster_particles': cluster_particles,
}

SIGNATURES = [
    ("element_summary(quantity='diameter_nm', by=None, elements=None)",
     "n, % of particles, median, geo mean, p5, p95, LOD per element"),
    ("compare_samples(element, quantity='diameter_nm', by='sample')",
     "per-sample medians with 95% CI + Kruskal-Wallis and Mann-Whitney tests"),
    ("coincidence(element_a, element_b)",
     "is A+B real or two particles arriving together by chance?"),
    ("co_occurrence(elements=None, min_count=10)",
     "every element pair vs the random coincidence rate, with a verdict"),
    ("coincidence_overview()",
     "expected vs observed share of multi-element events per run"),
    ("size_distribution(element, quantity='diameter_nm', by='sample')",
     "mode, geo mean/sd, LOD and whether the distribution is truncated"),
    ("near_detection_limit(quantity='mass_fg')",
     "elements whose detections crowd the detection limit"),
    ("find_outliers(quantity='mass_fg', element=None, threshold=5)",
     "particles far outside the usual range (robust log z-score)"),
    ("time_bursts(element=None)",
     "time bins with far more arrivals than usual (contamination, spikes)"),
    ("combination_enrichment(by='sample')",
     "element combinations over/under-represented in a sample"),
    ("long_format(quantity='diameter_nm', elements=None)",
     "one row per particle and element: particle, sample, run, element, value"),
    ("cluster_particles(elements=None, k=3, algorithm='K-Means', scaling='CLR')",
     "returns (summary, labels) using the Clustering node's engine"),
    ("lod(element, quantity='mass_fg', sample=None)",
     "calibrated detection limit, None when unknown"),
]
