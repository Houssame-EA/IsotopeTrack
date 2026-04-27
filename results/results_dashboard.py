from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QMessageBox, QFileDialog,
)
from PySide6.QtCore import QObject, Signal, QPointF, Qt
from PySide6.QtGui import QFont

import json
import numpy as np

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebChannel import QWebChannel
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False


def _safe_positive(v):
    """
    Args:
        v (Any): The v.
    Returns:
        object: Result of the operation.
    """
    try:
        v = float(v)
        return v > 0 and not np.isnan(v)
    except:
        return False


def _build_dashboard_data(data_context):
    """Extract everything the dashboard JS needs.
    Args:
        data_context (Any): The data context.
    Returns:
        dict: Result of the operation.
    """
    if not data_context:
        return None

    particles = data_context.get('particle_data', [])
    if not particles:
        return None

    dtype = data_context.get('type', '')
    sample_name = data_context.get('sample_name', 'Unknown')
    sample_names = data_context.get('sample_names', [])

    elem_counts = {}
    for p in particles:
        for el, v in p.get('elements', {}).items():
            if _safe_positive(v):
                elem_counts[el] = elem_counts.get(el, 0) + 1

    top_elements = sorted(elem_counts.items(), key=lambda x: -x[1])

    elem_stats = {}
    for el, count in top_elements[:30]:
        diams, masses, moles, mass_pcts, counts_vals = [], [], [], [], []
        for p in particles:
            cv = p.get('elements', {}).get(el)
            if cv and _safe_positive(cv):
                counts_vals.append(round(float(cv), 2))
            d = p.get('element_diameter_nm', {}).get(el)
            if d and _safe_positive(d):
                diams.append(round(float(d), 2))
            m = p.get('element_mass_fg', {}).get(el)
            if m and _safe_positive(m):
                masses.append(round(float(m), 3))
            mo = p.get('element_moles_fmol', {}).get(el)
            if mo and _safe_positive(mo):
                moles.append(round(float(mo), 6))
            mp = p.get('mass_percentages', {}).get(el)
            if mp and _safe_positive(mp):
                mass_pcts.append(round(float(mp), 1))

        def _stats(arr):
            """
            Args:
                arr (Any): The arr.
            Returns:
                dict: Result of the operation.
            """
            if not arr:
                return {'mean': 0, 'std': 0, 'min': 0, 'max': 0,
                        'q1': 0, 'median': 0, 'q3': 0}
            a = np.array(arr)
            return {
                'mean': round(float(np.mean(a)), 4),
                'std': round(float(np.std(a)), 4),
                'min': round(float(np.min(a)), 4),
                'max': round(float(np.max(a)), 4),
                'q1': round(float(np.percentile(a, 25)), 4),
                'median': round(float(np.median(a)), 4),
                'q3': round(float(np.percentile(a, 75)), 4),
            }

        elem_stats[el] = {
            'count': count,
            'diameters': diams[:3000],
            'masses': masses[:3000],
            'moles': moles[:3000],
            'mass_pct': mass_pcts[:3000],
            'counts': counts_vals[:3000],
            'diam_stats': _stats(diams),
            'mass_stats': _stats(masses),
            'moles_stats': _stats(moles),
            'counts_stats': _stats(counts_vals),
        }

    combos = {}
    for p in particles:
        det = sorted(el for el, v in p.get('elements', {}).items() if _safe_positive(v))
        if det:
            key = ' + '.join(det)
            combos[key] = combos.get(key, 0) + 1
    top_combos = sorted(combos.items(), key=lambda x: -x[1])[:20]

    single_count = sum(
        1 for p in particles
        if sum(1 for v in p.get('elements', {}).values() if _safe_positive(v)) == 1
    )

   
    corr_elements = [el for el, _ in top_elements[:15]]
    corr_data = []
    for p in particles:
        row = {}
        for el in corr_elements:
            v = p.get('elements', {}).get(el, 0)
            if _safe_positive(v):
                row[el] = round(float(v), 2)
            else:
                row[el] = 0
        for el in corr_elements:
            d = p.get('element_diameter_nm', {}).get(el, 0)
            row[f'{el}_diam'] = round(float(d), 2) if _safe_positive(d) else 0
            m = p.get('element_mass_fg', {}).get(el, 0)
            row[f'{el}_mass'] = round(float(m), 3) if _safe_positive(m) else 0
        corr_data.append(row)

    corr_data = corr_data[:5000]

    top10 = [el for el, _ in top_elements[:10]]
    cooccurrence = {a: {b: 0 for b in top10} for a in top10}
    for p in particles:
        present = [el for el in top10 if _safe_positive(p.get('elements', {}).get(el, 0))]
        for a in present:
            for b in present:
                cooccurrence[a][b] += 1

    by_sample = {}
    if dtype == 'multiple_sample_data':
        for p in particles:
            src = p.get('source_sample', '?')
            by_sample.setdefault(src, {'count': 0, 'elements': {}})
            by_sample[src]['count'] += 1
            for el, v in p.get('elements', {}).items():
                if _safe_positive(v):
                    by_sample[src]['elements'][el] = \
                        by_sample[src]['elements'].get(el, 0) + 1

    combo_heatmap = {}
    for combo_name, combo_count in top_combos[:15]:
        elements_in_combo = [e.strip() for e in combo_name.split('+')]
        combo_heatmap[combo_name] = {
            'count': combo_count,
            'elements': elements_in_combo,
        }

    return {
        'type': dtype,
        'sample_name': sample_name,
        'sample_names': sample_names,
        'total_particles': len(particles),
        'single_element': single_count,
        'multi_element': len(particles) - single_count,
        'unique_elements': len(elem_counts),
        'element_labels': [el for el, _ in top_elements],
        'element_counts': {el: c for el, c in top_elements},
        'element_stats': elem_stats,
        'combinations': top_combos,
        'combo_heatmap': combo_heatmap,
        'corr_elements': corr_elements,
        'corr_data': corr_data,
        'by_sample': by_sample,
        'cooccurrence_labels': top10,
        'cooccurrence_matrix': [[cooccurrence[a][b] for b in top10] for a in top10],
    }


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Outfit:wght@300;400;500;600;700;800&display=swap');

  * { margin:0; padding:0; box-sizing:border-box; }

  :root {
    --bg: #06080E;
    --bg2: #0D1117;
    --bg3: #161B22;
    --surface: #1C2333;
    --surface2: #242D3D;
    --border: #2D3748;
    --border2: #4A5568;
    --text: #E8ECF1;
    --text2: #8B98AD;
    --text3: #5A6577;
    --accent: #58A6FF;
    --accent2: #79C0FF;
    --accent-dim: rgba(88,166,255,0.12);
    --purple: #BC8CFF;
    --purple-dim: rgba(188,140,255,0.12);
    --teal: #3CEAD8;
    --teal-dim: rgba(60,234,216,0.10);
    --orange: #FFA657;
    --orange-dim: rgba(255,166,87,0.10);
    --pink: #F778BA;
    --pink-dim: rgba(247,120,186,0.10);
    --green: #56D364;
    --green-dim: rgba(86,211,100,0.10);
    --red: #F85149;
    --amber: #E3B341;
    --radius: 10px;
    --font-size: 13px;
    --font-family: 'Outfit', -apple-system, sans-serif;
    --mono: 'JetBrains Mono', monospace;
    --shadow: 0 2px 8px rgba(0,0,0,0.3);
    --transition: 0.2s cubic-bezier(0.4,0,0.2,1);
  }

  body {
    font-family: var(--font-family);
    font-size: var(--font-size);
    background: var(--bg);
    color: var(--text);
    overflow-x: hidden;
    line-height: 1.5;
  }

  /* ── Header ─────────────────────────── */
  .header {
    background: linear-gradient(135deg, #0D1117 0%, #161637 50%, #0D1117 100%);
    border-bottom: 1px solid var(--border);
    padding: 16px 24px;
    display: flex; align-items: center; justify-content: space-between;
    position: sticky; top: 0; z-index: 100;
    backdrop-filter: blur(12px);
  }
  .header-left { display:flex; align-items:center; gap:12px; }
  .header-logo {
    width:32px; height:32px; border-radius:8px;
    background: linear-gradient(135deg, var(--accent), var(--purple));
    display:flex; align-items:center; justify-content:center;
    font-weight:800; font-size:16px; color:#fff;
  }
  .header h1 { font-size:16px; font-weight:700; letter-spacing:-0.4px; }
  .header h1 span { color: var(--accent2); }
  .header-sub { color: var(--text2); font-size:12px; font-weight:400; }
  .header-right { display:flex; align-items:center; gap:16px; }
  .header-badge {
    background: var(--accent-dim); color: var(--accent);
    padding: 4px 10px; border-radius: 20px;
    font-size: 11px; font-weight: 600; letter-spacing: 0.3px;
  }

  /* ── Tabs ────────────────────────────── */
  .tabs {
    display:flex; gap:0; padding:0 24px;
    background: var(--bg2); border-bottom:1px solid var(--border);
    overflow-x: auto;
  }
  .tab {
    padding:11px 18px; cursor:pointer; font-size:13px; font-weight:500;
    color: var(--text3); border-bottom:2px solid transparent;
    transition: var(--transition); white-space:nowrap; user-select:none;
  }
  .tab:hover { color: var(--text2); background: rgba(255,255,255,0.02); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight:600; }
  .tab-panel { display:none; }
  .tab-panel.active { display:block; }

  /* ── Metrics row ────────────────────── */
  .metrics {
    display:grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap:10px; padding:16px 24px;
  }
  .metric {
    background: var(--bg2); border:1px solid var(--border); border-radius: var(--radius);
    padding:14px 16px; position:relative; overflow:hidden;
    transition: var(--transition);
  }
  .metric:hover { border-color: var(--border2); transform: translateY(-1px); box-shadow: var(--shadow); }
  .metric::before {
    content:''; position:absolute; top:0; left:0; right:0; height:2px;
  }
  .metric:nth-child(1)::before { background: var(--accent); }
  .metric:nth-child(2)::before { background: var(--purple); }
  .metric:nth-child(3)::before { background: var(--teal); }
  .metric:nth-child(4)::before { background: var(--orange); }
  .metric:nth-child(5)::before { background: var(--pink); }
  .metric:nth-child(6)::before { background: var(--green); }
  .metric-label { font-size:10px; color:var(--text3); font-weight:600; text-transform:uppercase; letter-spacing:0.8px; }
  .metric-value { font-size:24px; font-weight:700; margin-top:2px; letter-spacing:-0.5px; font-family:var(--mono); }
  .metric-sub { font-size:11px; color:var(--text2); margin-top:1px; }

  /* ── Card grid ──────────────────────── */
  .grid {
    display:grid; grid-template-columns: 1fr 1fr; gap:14px; padding:16px 24px;
  }
  .card {
    background: var(--bg2); border:1px solid var(--border); border-radius: var(--radius);
    padding:16px; transition: var(--transition);
  }
  .card:hover { border-color: var(--border2); }
  .card-title {
    font-size:13px; font-weight:600; color:var(--text); margin-bottom:10px;
    display:flex; align-items:center; gap:8px;
  }
  .card-title .dot { width:7px; height:7px; border-radius:50%; display:inline-block; }
  .chart-wrap { position:relative; width:100%; }
  .full-width { grid-column: 1 / -1; }
  .third-width { }

  /* ── Controls row ───────────────────── */
  .controls {
    padding:10px 24px; display:flex; gap:12px; align-items:center; flex-wrap:wrap;
    background: var(--bg2); border-bottom:1px solid var(--border); border-top:1px solid var(--border);
  }
  .controls label {
    font-size:10px; color:var(--text3); font-weight:600;
    text-transform:uppercase; letter-spacing:0.6px;
  }
  .ctrl-select, .ctrl-input {
    background: var(--bg); color: var(--text); border:1px solid var(--border);
    border-radius:6px; padding:5px 10px; font-size:12px; font-family:inherit; outline:none;
    transition: var(--transition);
  }
  .ctrl-select:focus, .ctrl-input:focus { border-color: var(--accent); }
  input[type=range] { accent-color: var(--accent); }
  .ctrl-val { font-size:12px; color:var(--text2); min-width:22px; font-family:var(--mono); }

  /* ── Combo tags ─────────────────────── */
  .combo-list { display:flex; flex-wrap:wrap; gap:5px; margin-top:6px; }
  .combo-tag {
    background: var(--bg3); border:1px solid var(--border); border-radius:16px;
    padding:3px 10px; font-size:11px; color:var(--text2); white-space:nowrap;
    transition: var(--transition);
  }
  .combo-tag:hover { border-color: var(--accent); color: var(--text); }
  .combo-tag .cnt { color:var(--accent2); font-weight:600; margin-left:4px; font-family:var(--mono); }

  /* ── Table ──────────────────────────── */
  .table-wrap { overflow-x:auto; margin-top:8px; }
  table { width:100%; border-collapse:collapse; font-size:12px; }
  th {
    text-align:left; padding:8px 10px; color:var(--text3); font-weight:600;
    font-size:10px; text-transform:uppercase; letter-spacing:0.5px;
    border-bottom:1px solid var(--border); position:sticky; top:0;
    background: var(--bg2);
  }
  td { padding:6px 10px; border-bottom:1px solid rgba(45,55,72,0.4); color:var(--text2); }
  tr:hover td { background: rgba(88,166,255,0.04); }
  td:first-child { color:var(--text); font-weight:500; font-family:var(--mono); }

  /* ── Context menu ───────────────────── */
  .ctx-menu {
    display:none; position:fixed; z-index:9999;
    background: var(--bg3); border:1px solid var(--border2);
    border-radius:10px; padding:6px 0; min-width:200px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5); backdrop-filter: blur(16px);
  }
  .ctx-menu.show { display:block; }
  .ctx-item {
    padding:7px 16px; cursor:pointer; font-size:12px; color:var(--text2);
    display:flex; align-items:center; gap:8px; transition: var(--transition);
  }
  .ctx-item:hover { background: var(--accent-dim); color:var(--accent); }
  .ctx-sep { height:1px; background:var(--border); margin:4px 0; }
  .ctx-sub { position:relative; }
  .ctx-sub .ctx-submenu {
    display:none; position:absolute; left:100%; top:0;
    background:var(--bg3); border:1px solid var(--border2);
    border-radius:10px; padding:6px 0; min-width:160px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
  }
  .ctx-sub:hover .ctx-submenu { display:block; }
  .ctx-item .check { font-size:10px; margin-left:auto; }

  /* ── Correlation info badge ──────────── */
  .corr-badge {
    display:inline-flex; align-items:center; gap:6px;
    background: var(--surface); border:1px solid var(--border);
    border-radius:8px; padding:6px 12px; font-size:12px;
  }
  .corr-r { font-family:var(--mono); font-weight:700; font-size:14px; }
  .corr-n { color:var(--text3); font-size:11px; }

  /* ── Stat summary boxes ─────────────── */
  .stat-grid {
    display:grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
    gap:8px; margin-top:8px;
  }
  .stat-box {
    background: var(--bg); border:1px solid var(--border); border-radius:8px;
    padding:8px 10px; text-align:center;
  }
  .stat-box-label { font-size:9px; color:var(--text3); text-transform:uppercase; letter-spacing:0.5px; }
  .stat-box-value { font-size:15px; font-weight:700; font-family:var(--mono); margin-top:2px; }

  /* ── Responsive ─────────────────────── */
  @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>

<!-- Context menu -->
<div class="ctx-menu" id="ctx-menu">
  <div class="ctx-sub">
    <div class="ctx-item">Font Size ▸</div>
    <div class="ctx-submenu" id="ctx-fontsize">
      <div class="ctx-item" onclick="setFontSize(11)">Small (11px)</div>
      <div class="ctx-item" onclick="setFontSize(13)">Default (13px)</div>
      <div class="ctx-item" onclick="setFontSize(15)">Large (15px)</div>
      <div class="ctx-item" onclick="setFontSize(17)">X-Large (17px)</div>
    </div>
  </div>
  <div class="ctx-sub">
    <div class="ctx-item">Chart Font ▸</div>
    <div class="ctx-submenu">
      <div class="ctx-item" onclick="setChartFont('Outfit')">Outfit</div>
      <div class="ctx-item" onclick="setChartFont('JetBrains Mono')">JetBrains Mono</div>
      <div class="ctx-item" onclick="setChartFont('Times New Roman')">Times New Roman</div>
      <div class="ctx-item" onclick="setChartFont('Arial')">Arial</div>
    </div>
  </div>
  <div class="ctx-sub">
    <div class="ctx-item">Chart Size ▸</div>
    <div class="ctx-submenu">
      <div class="ctx-item" onclick="setChartHeight(250)">Compact</div>
      <div class="ctx-item" onclick="setChartHeight(320)">Default</div>
      <div class="ctx-item" onclick="setChartHeight(420)">Tall</div>
      <div class="ctx-item" onclick="setChartHeight(520)">Extra Tall</div>
    </div>
  </div>
  <div class="ctx-sep"></div>
  <div class="ctx-sub">
    <div class="ctx-item">Accent Color ▸</div>
    <div class="ctx-submenu">
      <div class="ctx-item" onclick="setAccent('#58A6FF','#79C0FF')">Blue (default)</div>
      <div class="ctx-item" onclick="setAccent('#BC8CFF','#D4B3FF')">Purple</div>
      <div class="ctx-item" onclick="setAccent('#3CEAD8','#6EF3E6')">Teal</div>
      <div class="ctx-item" onclick="setAccent('#FFA657','#FFBE7A')">Orange</div>
      <div class="ctx-item" onclick="setAccent('#56D364','#7EE087')">Green</div>
    </div>
  </div>
  <div class="ctx-sep"></div>
  <div class="ctx-item" onclick="refreshAll()">Refresh Charts</div>
</div>

<!-- Header -->
<div class="header">
  <div class="header-left">
    <div class="header-logo">◆</div>
    <div>
      <h1><span>IsotopeTrack</span> Dashboard</h1>
      <div class="header-sub" id="subtitle">Loading…</div>
    </div>
  </div>
  <div class="header-right">
    <div class="header-badge" id="header-badge">—</div>
    <div class="header-sub" id="header-info">Right-click for settings</div>
  </div>
</div>

<!-- Tabs -->
<div class="tabs">
  <div class="tab active" data-tab="overview">Overview</div>
  <div class="tab" data-tab="distribution">Distribution</div>
  <div class="tab" data-tab="correlation">Correlation</div>
  <div class="tab" data-tab="heatmap">Heatmap</div>
  <div class="tab" data-tab="statistics">Statistics</div>
</div>

<!-- ═══ OVERVIEW TAB ═══ -->
<div class="tab-panel active" id="panel-overview">
  <div class="metrics" id="metrics"></div>
  <div class="grid">
    <div class="card">
      <div class="card-title"><span class="dot" style="background:var(--accent)"></span>Element Frequency</div>
      <div class="chart-wrap" style="height:320px"><canvas id="freqChart"></canvas></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="dot" style="background:var(--purple)"></span>Single vs Multi-element</div>
      <div class="chart-wrap" style="height:260px"><canvas id="pieChart"></canvas></div>
      <div style="margin-top:12px;">
        <div class="card-title" style="font-size:12px;"><span class="dot" style="background:var(--green)"></span>Top Combinations</div>
        <div class="combo-list" id="combo-list"></div>
      </div>
    </div>
    <div class="card">
      <div class="card-title"><span class="dot" style="background:var(--teal)"></span>Mean Diameter by Element</div>
      <div class="chart-wrap" style="height:280px"><canvas id="diamChart"></canvas></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="dot" style="background:var(--orange)"></span>Mean Mass by Element</div>
      <div class="chart-wrap" style="height:280px"><canvas id="massChart"></canvas></div>
    </div>
    <div class="card full-width">
      <div class="card-title"><span class="dot" style="background:var(--amber)"></span>Co-occurrence (top 10 elements)</div>
      <div class="chart-wrap" style="height:340px"><canvas id="heatChart"></canvas></div>
    </div>
    <div class="card full-width" id="sample-card" style="display:none">
      <div class="card-title"><span class="dot" style="background:var(--accent)"></span>Element Count by Sample</div>
      <div class="chart-wrap" style="height:300px"><canvas id="sampleChart"></canvas></div>
    </div>
  </div>
</div>

<!-- ═══ DISTRIBUTION TAB ═══ -->
<div class="tab-panel" id="panel-distribution">
  <div class="controls">
    <label>Element</label>
    <select class="ctrl-select" id="dist-el"></select>
    <label>Variable</label>
    <select class="ctrl-select" id="dist-var">
      <option value="diameters">Diameter (nm)</option>
      <option value="masses">Mass (fg)</option>
      <option value="moles">Moles (fmol)</option>
      <option value="mass_pct">Mass %</option>
      <option value="counts">Intensity (counts)</option>
    </select>
    <label>Bins</label>
    <input type="range" id="dist-bins" min="8" max="100" value="35" step="1">
    <span class="ctrl-val" id="dist-bins-val">35</span>
    <label style="margin-left:16px;">
      <input type="checkbox" id="dist-log" style="accent-color:var(--accent)">
      Log Y
    </label>
  </div>
  <div class="grid">
    <div class="card full-width">
      <div class="card-title"><span class="dot" style="background:var(--purple)"></span>Histogram — <span id="hist-label">?</span></div>
      <div class="chart-wrap" style="height:360px"><canvas id="histChart"></canvas></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="dot" style="background:var(--teal)"></span>Summary Statistics</div>
      <div class="stat-grid" id="dist-stats"></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="dot" style="background:var(--accent)"></span>Box Plot Summary (all elements)</div>
      <div class="chart-wrap" style="height:300px"><canvas id="boxSummaryChart"></canvas></div>
    </div>
  </div>
</div>

<!-- ═══ CORRELATION TAB ═══ -->
<div class="tab-panel" id="panel-correlation">
  <div class="controls">
    <label>X Element</label>
    <select class="ctrl-select" id="corr-x"></select>
    <label>Y Element</label>
    <select class="ctrl-select" id="corr-y"></select>
    <label>Color by</label>
    <select class="ctrl-select" id="corr-color"></select>
    <label>Data</label>
    <select class="ctrl-select" id="corr-dtype">
      <option value="counts">Counts</option>
      <option value="diam">Diameter (nm)</option>
      <option value="mass">Mass (fg)</option>
    </select>
    <label style="margin-left:12px;">
      <input type="checkbox" id="corr-trend" checked style="accent-color:var(--accent)">
      Trend
    </label>
    <label>
      <input type="checkbox" id="corr-logx" style="accent-color:var(--accent)">
      Log X
    </label>
    <label>
      <input type="checkbox" id="corr-logy" style="accent-color:var(--accent)">
      Log Y
    </label>
  </div>
  <div class="grid">
    <div class="card full-width">
      <div class="card-title">
        <span class="dot" style="background:var(--accent)"></span>
        Scatter — <span id="corr-title">?</span>
        <span id="corr-info" class="corr-badge" style="margin-left:auto;"></span>
      </div>
      <div class="chart-wrap" style="height:440px"><canvas id="corrChart"></canvas></div>
    </div>
    <div class="card full-width">
      <div class="card-title"><span class="dot" style="background:var(--purple)"></span>Correlation Matrix (top elements)</div>
      <div class="chart-wrap" style="height:360px"><canvas id="corrMatrixChart"></canvas></div>
    </div>
  </div>
</div>

<!-- ═══ HEATMAP TAB ═══ -->
<div class="tab-panel" id="panel-heatmap">
  <div class="controls">
    <label>Top N combos</label>
    <input type="range" id="hm-count" min="5" max="20" value="12" step="1">
    <span class="ctrl-val" id="hm-count-val">12</span>
    <label style="margin-left:12px;">
      <input type="checkbox" id="hm-numbers" checked style="accent-color:var(--accent)">
      Show Numbers
    </label>
  </div>
  <div class="grid">
    <div class="card full-width">
      <div class="card-title"><span class="dot" style="background:var(--orange)"></span>Element Combination Heatmap</div>
      <div class="chart-wrap" style="height:440px"><canvas id="comboHeatChart"></canvas></div>
    </div>
  </div>
</div>

<!-- ═══ STATISTICS TAB ═══ -->
<div class="tab-panel" id="panel-statistics">
  <div class="controls">
    <label>Data</label>
    <select class="ctrl-select" id="stats-dtype">
      <option value="diam">Diameter (nm)</option>
      <option value="mass">Mass (fg)</option>
      <option value="moles">Moles (fmol)</option>
      <option value="counts">Counts</option>
    </select>
  </div>
  <div class="grid">
    <div class="card full-width">
      <div class="card-title"><span class="dot" style="background:var(--purple)"></span>Element Statistics</div>
      <div class="table-wrap" id="stats-table" style="max-height:600px;overflow-y:auto;"></div>
    </div>
  </div>
</div>


<script>
/* ═══ GLOBALS ═══ */
const COLORS = ['#58A6FF','#BC8CFF','#3CEAD8','#FFA657','#F778BA','#56D364','#F85149','#E3B341',
                '#6366F1','#06B6D4','#8B5CF6','#10B981','#F43F5E','#84CC16','#0EA5E9'];
const GRID = 'rgba(45,55,72,0.25)';
let CHART_FONT = {family:"'Outfit',sans-serif", color:'#8B98AD', size:12};
let DATA = null;
let charts = {};

/* ═══ SETTINGS (right-click) ═══ */
document.addEventListener('contextmenu', e => {
  e.preventDefault();
  const m = document.getElementById('ctx-menu');
  m.style.left = Math.min(e.clientX, window.innerWidth-220) + 'px';
  m.style.top = Math.min(e.clientY, window.innerHeight-300) + 'px';
  m.classList.add('show');
});
document.addEventListener('click', () => document.getElementById('ctx-menu').classList.remove('show'));

function setFontSize(px) {
  document.documentElement.style.setProperty('--font-size', px+'px');
  document.body.style.fontSize = px+'px';
  CHART_FONT.size = px - 1;
  refreshAll();
}
function setChartFont(f) {
  CHART_FONT.family = "'" + f + "',sans-serif";
  refreshAll();
}
function setChartHeight(h) {
  document.querySelectorAll('.chart-wrap').forEach(w => w.style.height = h + 'px');
  refreshAll();
}
function setAccent(a, a2) {
  document.documentElement.style.setProperty('--accent', a);
  document.documentElement.style.setProperty('--accent2', a2);
  document.documentElement.style.setProperty('--accent-dim', a + '1F');
}

/* ═══ TABS ═══ */
document.querySelectorAll('.tab').forEach(t => {
  t.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    document.getElementById('panel-' + t.dataset.tab).classList.add('active');
    // Lazy build
    if (DATA) {
      if (t.dataset.tab === 'distribution') buildDistribution();
      if (t.dataset.tab === 'correlation') buildCorrelation();
      if (t.dataset.tab === 'heatmap') buildComboHeatmap();
      if (t.dataset.tab === 'statistics') buildStatsTable();
    }
  });
});

/* ═══ HELPERS ═══ */
function destroyChart(id) { if(charts[id]) { charts[id].destroy(); delete charts[id]; } }

function tooltipOpts() {
  return { backgroundColor:'#1C2333', titleColor:'#E8ECF1', bodyColor:'#8B98AD',
           borderColor:'#2D3748', borderWidth:1, cornerRadius:8, padding:10,
           titleFont:{family:CHART_FONT.family}, bodyFont:{family:CHART_FONT.family} };
}
function scaleOpts(axis, label, grid) {
  return {
    grid: grid ? {color:GRID} : {display:false},
    ticks: {color:CHART_FONT.color, font:{family:CHART_FONT.family, size:CHART_FONT.size}},
    title: label ? {display:true, text:label, color:CHART_FONT.color, font:{family:CHART_FONT.family, size:CHART_FONT.size+1}} : undefined
  };
}

/* ═══ INIT ═══ */
function init(jsonStr) {
  DATA = typeof jsonStr === 'string' ? JSON.parse(jsonStr) : jsonStr;

  document.getElementById('subtitle').textContent =
    DATA.type === 'multiple_sample_data'
      ? 'Multi-sample: ' + DATA.sample_names.join(', ')
      : DATA.sample_name || 'Sample';
  document.getElementById('header-badge').textContent =
    DATA.total_particles.toLocaleString() + ' particles';
  document.getElementById('header-info').textContent =
    DATA.unique_elements + ' elements detected  ·  Right-click for settings';

  buildMetrics();
  buildFreqChart();
  buildPieChart();
  buildCombos();
  buildMeanCharts();
  buildHeatmap();
  buildSampleChart();
  populateDistSelects();
  populateCorrSelects();

  // Wire up controls
  ['dist-el','dist-var','dist-log'].forEach(id => document.getElementById(id).addEventListener('change', buildDistribution));
  document.getElementById('dist-bins').addEventListener('input', function(){
    document.getElementById('dist-bins-val').textContent = this.value; buildDistribution(); });

  ['corr-x','corr-y','corr-color','corr-dtype','corr-trend','corr-logx','corr-logy'].forEach(id =>
    document.getElementById(id).addEventListener('change', buildCorrelation));

  document.getElementById('hm-count').addEventListener('input', function(){
    document.getElementById('hm-count-val').textContent = this.value; buildComboHeatmap(); });
  document.getElementById('hm-numbers').addEventListener('change', buildComboHeatmap);
  document.getElementById('stats-dtype').addEventListener('change', buildStatsTable);
}

function refreshAll() {
  if (!DATA) return;
  buildFreqChart(); buildPieChart(); buildMeanCharts(); buildHeatmap(); buildSampleChart();
  buildDistribution(); buildCorrelation(); buildComboHeatmap(); buildStatsTable();
}

/* ═══ OVERVIEW: Metrics ═══ */
function buildMetrics() {
  const el = document.getElementById('metrics');
  const items = [
    {label:'Total Particles', value:DATA.total_particles.toLocaleString(),
     sub:DATA.type==='multiple_sample_data'?DATA.sample_names.length+' samples':''},
    {label:'Unique Elements', value:DATA.unique_elements,
     sub:DATA.element_labels.slice(0,4).join(', ')+'…'},
    {label:'Single-Element', value:DATA.single_element.toLocaleString(),
     sub:(DATA.single_element/DATA.total_particles*100).toFixed(1)+'%'},
    {label:'Multi-Element', value:DATA.multi_element.toLocaleString(),
     sub:(DATA.multi_element/DATA.total_particles*100).toFixed(1)+'%'},
    {label:'Top Element', value:DATA.element_labels[0]||'—',
     sub:(DATA.element_counts[DATA.element_labels[0]]||0).toLocaleString()+' detections'},
    {label:'Combinations', value:DATA.combinations.length,
     sub:'unique compositions'},
  ];
  el.innerHTML = items.map(i=>`
    <div class="metric">
      <div class="metric-label">${i.label}</div>
      <div class="metric-value">${i.value}</div>
      ${i.sub?'<div class="metric-sub">'+i.sub+'</div>':''}
    </div>`).join('');
}

/* ═══ OVERVIEW: Frequency ═══ */
function buildFreqChart() {
  destroyChart('freq');
  const labels = DATA.element_labels.slice(0,20);
  const values = labels.map(e=>DATA.element_counts[e]);
  charts.freq = new Chart(document.getElementById('freqChart'), {
    type:'bar', data:{labels, datasets:[{data:values,
      backgroundColor:labels.map((_,i)=>COLORS[i%COLORS.length]), borderRadius:5, borderSkipped:false}]},
    options:{indexAxis:'y', responsive:true, maintainAspectRatio:false,
      plugins:{legend:{display:false}, tooltip:tooltipOpts()},
      scales:{x:scaleOpts('x','Particle count',true), y:{grid:{display:false},
        ticks:{color:'#E8ECF1', font:{family:CHART_FONT.family, weight:500, size:CHART_FONT.size}}}}}
  });
}

/* ═══ OVERVIEW: Pie ═══ */
function buildPieChart() {
  destroyChart('pie');
  charts.pie = new Chart(document.getElementById('pieChart'), {
    type:'doughnut',
    data:{labels:['Single-element','Multi-element'],
      datasets:[{data:[DATA.single_element,DATA.multi_element],
        backgroundColor:['#58A6FF','#BC8CFF'], borderColor:'#0D1117', borderWidth:3}]},
    options:{responsive:true, maintainAspectRatio:false, cutout:'65%',
      plugins:{legend:{position:'bottom',labels:{color:CHART_FONT.color,
        font:{family:CHART_FONT.family,size:CHART_FONT.size},padding:14}}, tooltip:tooltipOpts()}}
  });
}

/* ═══ OVERVIEW: Combos ═══ */
function buildCombos() {
  const el = document.getElementById('combo-list');
  if(!DATA.combinations.length) { el.innerHTML='<span style="color:var(--text3)">None</span>'; return; }
  el.innerHTML = DATA.combinations.slice(0,15).map(([n,c])=>
    `<span class="combo-tag">${n}<span class="cnt">${c}</span></span>`).join('');
}

/* ═══ OVERVIEW: Mean charts ═══ */
function buildMeanCharts() {
  destroyChart('diam'); destroyChart('mass');
  const labels = DATA.element_labels.slice(0,15);
  const mkBar=(id,canvas,vals,color,unit)=>{
    charts[id]=new Chart(document.getElementById(canvas),{
      type:'bar',data:{labels,datasets:[{data:vals,backgroundColor:color,borderRadius:5,borderSkipped:false}]},
      options:{responsive:true,maintainAspectRatio:false,
        plugins:{legend:{display:false},tooltip:tooltipOpts()},
        scales:{x:{grid:{display:false},ticks:{color:CHART_FONT.color,maxRotation:45,font:{family:CHART_FONT.family,size:CHART_FONT.size}}},
                y:scaleOpts('y',unit,true)}}});
  };
  mkBar('diam','diamChart',labels.map(e=>DATA.element_stats[e]?.diam_stats?.mean||0),'#3CEAD8','Diameter (nm)');
  mkBar('mass','massChart',labels.map(e=>DATA.element_stats[e]?.mass_stats?.mean||0),'#FFA657','Mass (fg)');
}

/* ═══ OVERVIEW: Co-occurrence heatmap ═══ */
function buildHeatmap() {
  destroyChart('heat');
  const labels = DATA.cooccurrence_labels;
  const matrix = DATA.cooccurrence_matrix;
  if(!labels||!labels.length) return;
  const pts = []; let mx=0;
  for(let i=0;i<labels.length;i++) for(let j=0;j<labels.length;j++){
    const v=matrix[i][j]; if(v>mx)mx=v; pts.push({x:j,y:i,v});
  }
  charts.heat = new Chart(document.getElementById('heatChart'),{
    type:'scatter',
    data:{datasets:[{data:pts.map(p=>({x:p.x,y:p.y})),
      backgroundColor:pts.map(p=>{
        const t=mx>0?p.v/mx:0;
        return `rgba(${Math.round(88+t*(188-88))},${Math.round(166+t*(140-166))},${Math.round(255+t*(255-255))},${Math.max(0.12,t)})`;
      }),
      pointRadius:pts.map(p=>{const t=mx>0?p.v/mx:0; return 7+t*16;}),
      pointHoverRadius:pts.map(p=>{const t=mx>0?p.v/mx:0; return 9+t*18;})
    }]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{...tooltipOpts(),
        callbacks:{title:ctx=>{const p=pts[ctx[0].dataIndex];return labels[p.y]+' × '+labels[p.x];},
                   label:ctx=>'Co-occurrence: '+pts[ctx.dataIndex].v}}},
      scales:{
        x:{type:'linear',min:-0.5,max:labels.length-0.5,
          ticks:{stepSize:1,color:'#E8ECF1',font:{family:CHART_FONT.family,size:CHART_FONT.size},callback:v=>labels[v]||''},grid:{color:GRID}},
        y:{type:'linear',min:-0.5,max:labels.length-0.5,reverse:true,
          ticks:{stepSize:1,color:'#E8ECF1',font:{family:CHART_FONT.family,size:CHART_FONT.size},callback:v=>labels[v]||''},grid:{color:GRID}}
      }}
  });
}

/* ═══ OVERVIEW: Sample compare ═══ */
function buildSampleChart() {
  if(DATA.type!=='multiple_sample_data'||!DATA.by_sample) return;
  document.getElementById('sample-card').style.display='block';
  destroyChart('sample');
  const samples=Object.keys(DATA.by_sample);
  const topEls=DATA.element_labels.slice(0,10);
  const ds=samples.map((s,si)=>({label:s,
    data:topEls.map(e=>DATA.by_sample[s]?.elements?.[e]||0),
    backgroundColor:COLORS[si%COLORS.length],borderRadius:4,borderSkipped:false}));
  charts.sample=new Chart(document.getElementById('sampleChart'),{
    type:'bar',data:{labels:topEls,datasets:ds},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{position:'top',labels:{color:CHART_FONT.color,font:{family:CHART_FONT.family},boxWidth:12,padding:14}},tooltip:tooltipOpts()},
      scales:{x:{grid:{display:false},ticks:{color:'#E8ECF1',font:{family:CHART_FONT.family}}},
              y:scaleOpts('y','Count',true)}}
  });
}

/* ═══ DISTRIBUTION ═══ */
function populateDistSelects() {
  const sel = document.getElementById('dist-el');
  sel.innerHTML = DATA.element_labels.map(e=>
    `<option value="${e}">${e} (${DATA.element_counts[e]})</option>`).join('');
}

function buildDistribution() {
  destroyChart('hist'); destroyChart('boxSummary');
  const el = document.getElementById('dist-el').value;
  const varKey = document.getElementById('dist-var').value;
  const numBins = parseInt(document.getElementById('dist-bins').value);
  const logY = document.getElementById('dist-log').checked;
  const stats = DATA.element_stats[el];
  if(!stats) return;
  const vals = stats[varKey]||[];
  const unitMap = {diameters:'nm',masses:'fg',moles:'fmol',mass_pct:'%',counts:'counts'};
  document.getElementById('hist-label').textContent = `${el} — ${varKey.replace('_',' ')} (n=${vals.length})`;

  // Summary stats
  const sKey = {diameters:'diam_stats',masses:'mass_stats',moles:'moles_stats',counts:'counts_stats',mass_pct:'diam_stats'}[varKey]||'diam_stats';
  const s = stats[sKey]||{};
  const sg = document.getElementById('dist-stats');
  sg.innerHTML = [
    {l:'N',v:vals.length.toLocaleString()}, {l:'Mean',v:(s.mean||0).toPrecision(4)},
    {l:'Std',v:(s.std||0).toPrecision(4)}, {l:'Min',v:(s.min||0).toPrecision(4)},
    {l:'Q1',v:(s.q1||0).toPrecision(4)}, {l:'Median',v:(s.median||0).toPrecision(4)},
    {l:'Q3',v:(s.q3||0).toPrecision(4)}, {l:'Max',v:(s.max||0).toPrecision(4)},
  ].map(i=>`<div class="stat-box"><div class="stat-box-label">${i.l}</div><div class="stat-box-value">${i.v}</div></div>`).join('');

  if(vals.length===0) return;
  const mn=Math.min(...vals), mx=Math.max(...vals);
  const bw=(mx-mn)/numBins||1;
  const bins=Array(numBins).fill(0);
  const labels=[];
  for(let i=0;i<numBins;i++){
    const lo=mn+i*bw; labels.push(lo.toPrecision(3));
    vals.forEach(v=>{if(v>=lo&&(i===numBins-1?v<=lo+bw:v<lo+bw))bins[i]++;});
  }

  charts.hist = new Chart(document.getElementById('histChart'),{
    type:'bar',data:{labels,datasets:[{data:bins,
      backgroundColor:'rgba(188,140,255,0.7)',hoverBackgroundColor:'rgba(188,140,255,0.9)',
      borderRadius:2,borderSkipped:false}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:tooltipOpts()},
      scales:{
        x:{grid:{display:false},ticks:{color:CHART_FONT.color,maxRotation:45,autoSkip:true,font:{family:CHART_FONT.family,size:CHART_FONT.size}},
           title:{display:true,text:unitMap[varKey]||'',color:CHART_FONT.color,font:{family:CHART_FONT.family}}},
        y:{type:logY?'logarithmic':'linear',grid:{color:GRID},
           ticks:{color:CHART_FONT.color,font:{family:CHART_FONT.family}},
           title:{display:true,text:'Count',color:CHART_FONT.color,font:{family:CHART_FONT.family}}}
      }}
  });

  // Box plot summary: mean ± std for all elements (current variable)
  const boxEls = DATA.element_labels.slice(0,15);
  const means=[], lows=[], highs=[];
  boxEls.forEach(e=>{
    const st = DATA.element_stats[e];
    if(!st) {means.push(0);lows.push(0);highs.push(0);return;}
    const sk = {diameters:'diam_stats',masses:'mass_stats',moles:'moles_stats',counts:'counts_stats',mass_pct:'diam_stats'}[varKey]||'diam_stats';
    const ss = st[sk]||{};
    means.push(ss.mean||0);
    lows.push(ss.q1||0);
    highs.push(ss.q3||0);
  });
  charts.boxSummary = new Chart(document.getElementById('boxSummaryChart'),{
    type:'bar',
    data:{labels:boxEls, datasets:[
      {label:'Q1',data:lows,backgroundColor:'rgba(88,166,255,0.3)',borderRadius:3,borderSkipped:false},
      {label:'Mean',data:means,backgroundColor:'rgba(88,166,255,0.7)',borderRadius:3,borderSkipped:false},
      {label:'Q3',data:highs,backgroundColor:'rgba(88,166,255,0.3)',borderRadius:3,borderSkipped:false},
    ]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{position:'top',labels:{color:CHART_FONT.color,font:{family:CHART_FONT.family},boxWidth:10}},tooltip:tooltipOpts()},
      scales:{x:{grid:{display:false},ticks:{color:CHART_FONT.color,maxRotation:45,font:{family:CHART_FONT.family,size:CHART_FONT.size}}},
              y:scaleOpts('y',unitMap[varKey]||'Value',true)}}
  });
}

/* ═══ CORRELATION ═══ */
function populateCorrSelects() {
  const elems = DATA.corr_elements;
  ['corr-x','corr-y'].forEach((id,i)=>{
    const sel = document.getElementById(id);
    sel.innerHTML = elems.map(e=>`<option value="${e}">${e}</option>`).join('');
    if(elems.length > i) sel.selectedIndex = i;
  });
  const csel = document.getElementById('corr-color');
  csel.innerHTML = '<option value="none">None</option>' +
    elems.map(e=>`<option value="${e}">${e}</option>`).join('');
}

function buildCorrelation() {
  destroyChart('corr'); destroyChart('corrMatrix');
  const xEl = document.getElementById('corr-x').value;
  const yEl = document.getElementById('corr-y').value;
  const cEl = document.getElementById('corr-color').value;
  const dtype = document.getElementById('corr-dtype').value;
  const showTrend = document.getElementById('corr-trend').checked;
  const logX = document.getElementById('corr-logx').checked;
  const logY = document.getElementById('corr-logy').checked;
  if(!xEl||!yEl||!DATA.corr_data.length) return;

  const suffix = dtype==='diam'?'_diam':dtype==='mass'?'_mass':'';
  const xKey = xEl + suffix;
  const yKey = yEl + suffix;
  const cKey = cEl!=='none' ? (cEl + suffix) : null;

  // Extract valid points
  let pts = [];
  DATA.corr_data.forEach(row => {
    let xv = row[xKey]||0, yv = row[yKey]||0;
    if(xv<=0||yv<=0) return;
    if(logX) xv = Math.log10(xv);
    if(logY) yv = Math.log10(yv);
    if(!isFinite(xv)||!isFinite(yv)) return;
    let cv = cKey ? (row[cKey]||0) : 0;
    pts.push({x:xv, y:yv, c:cv});
  });

  const unitLabel = {counts:'counts',diam:'nm',mass:'fg'}[dtype];
  document.getElementById('corr-title').textContent =
    `${xEl} vs ${yEl}` + (cEl!=='none'?' (color: '+cEl+')':'') + ` [${unitLabel}]`;

  // Compute r
  let rText = '—', nText = pts.length + ' pts';
  if(pts.length > 2) {
    const xm=pts.reduce((s,p)=>s+p.x,0)/pts.length;
    const ym=pts.reduce((s,p)=>s+p.y,0)/pts.length;
    let sxy=0,sxx=0,syy=0;
    pts.forEach(p=>{const dx=p.x-xm,dy=p.y-ym;sxy+=dx*dy;sxx+=dx*dx;syy+=dy*dy;});
    const r=sxx>0&&syy>0?sxy/Math.sqrt(sxx*syy):0;
    rText = r.toFixed(4);
  }
  document.getElementById('corr-info').innerHTML =
    `<span class="corr-r" style="color:${parseFloat(rText)>0.5?'var(--green)':parseFloat(rText)<-0.5?'var(--red)':'var(--text2)'}">r = ${rText}</span>`+
    `<span class="corr-n">(n = ${nText})</span>`;

  // Color mapping
  let bgColors, borderColors;
  if(cKey && pts.some(p=>p.c>0)) {
    const cvals = pts.map(p=>p.c);
    const cmn=Math.min(...cvals.filter(v=>v>0)), cmx=Math.max(...cvals);
    bgColors = pts.map(p=>{
      if(p.c<=0) return 'rgba(90,101,119,0.4)';
      const t = cmx>cmn?(p.c-cmn)/(cmx-cmn):0.5;
      const r=Math.round(88+t*(247-88)), g=Math.round(166+t*(120-166)), b=Math.round(255+t*(186-255));
      return `rgba(${r},${g},${b},0.7)`;
    });
    borderColors = bgColors;
  } else {
    bgColors = 'rgba(88,166,255,0.5)';
    borderColors = 'rgba(88,166,255,0.8)';
  }

  // Trend line dataset
  const datasets = [{data:pts.map(p=>({x:p.x,y:p.y})),
    backgroundColor:bgColors, borderColor:borderColors,
    pointRadius:3.5, pointHoverRadius:6}];

  if(showTrend && pts.length>2) {
    const xm=pts.reduce((s,p)=>s+p.x,0)/pts.length;
    const ym=pts.reduce((s,p)=>s+p.y,0)/pts.length;
    let sxy=0,sxx=0;
    pts.forEach(p=>{sxy+=(p.x-xm)*(p.y-ym);sxx+=(p.x-xm)**2;});
    const slope=sxx>0?sxy/sxx:0;
    const intercept=ym-slope*xm;
    const xs=pts.map(p=>p.x).sort((a,b)=>a-b);
    const x1=xs[0],x2=xs[xs.length-1];
    datasets.push({data:[{x:x1,y:slope*x1+intercept},{x:x2,y:slope*x2+intercept}],
      type:'line',borderColor:'rgba(247,120,186,0.8)',borderWidth:2,borderDash:[6,4],
      pointRadius:0,fill:false});
  }

  charts.corr = new Chart(document.getElementById('corrChart'),{
    type:'scatter',data:{datasets},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{...tooltipOpts(),
        callbacks:{label:ctx=>`(${ctx.parsed.x.toPrecision(4)}, ${ctx.parsed.y.toPrecision(4)})`}}},
      scales:{
        x:scaleOpts('x',(logX?'log₁₀ ':'')+xEl+' ('+unitLabel+')',true),
        y:scaleOpts('y',(logY?'log₁₀ ':'')+yEl+' ('+unitLabel+')',true)
      }}
  });

  // Correlation matrix
  buildCorrMatrix();
}

function buildCorrMatrix() {
  destroyChart('corrMatrix');
  const elems = DATA.corr_elements.slice(0,10);
  if(elems.length<2) return;
  // Build correlation matrix
  const n = elems.length;
  const cols = {};
  elems.forEach(el=>{cols[el]=DATA.corr_data.map(r=>r[el]||0);});

  const rMatrix = [];
  for(let i=0;i<n;i++){
    rMatrix.push([]);
    for(let j=0;j<n;j++){
      const a=cols[elems[i]], b=cols[elems[j]];
      // Filter pairs where both > 0
      let sx=0,sy=0,sxy=0,sxx=0,syy=0,cnt=0;
      for(let k=0;k<a.length;k++){
        if(a[k]>0&&b[k]>0){sx+=a[k];sy+=b[k];cnt++;}
      }
      if(cnt<3){rMatrix[i].push(0);continue;}
      const mx=sx/cnt,my=sy/cnt;
      for(let k=0;k<a.length;k++){
        if(a[k]>0&&b[k]>0){sxy+=(a[k]-mx)*(b[k]-my);sxx+=(a[k]-mx)**2;syy+=(b[k]-my)**2;}
      }
      rMatrix[i].push(sxx>0&&syy>0?sxy/Math.sqrt(sxx*syy):0);
    }
  }

  const pts=[]; let mx=0;
  for(let i=0;i<n;i++) for(let j=0;j<n;j++){
    const v=rMatrix[i][j]; pts.push({x:j,y:i,v}); if(Math.abs(v)>mx) mx=Math.abs(v);
  }

  charts.corrMatrix = new Chart(document.getElementById('corrMatrixChart'),{
    type:'scatter',
    data:{datasets:[{data:pts.map(p=>({x:p.x,y:p.y})),
      backgroundColor:pts.map(p=>{
        const v=p.v;
        if(v>0) return `rgba(86,211,100,${Math.max(0.1,Math.abs(v))})`;
        if(v<0) return `rgba(248,81,73,${Math.max(0.1,Math.abs(v))})`;
        return 'rgba(90,101,119,0.15)';
      }),
      pointRadius:pts.map(p=>7+Math.abs(p.v)*14),
      pointHoverRadius:pts.map(p=>9+Math.abs(p.v)*16),
    }]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{...tooltipOpts(),
        callbacks:{title:ctx=>{const p=pts[ctx[0].dataIndex];return elems[p.y]+' × '+elems[p.x];},
                   label:ctx=>'r = '+pts[ctx.dataIndex].v.toFixed(4)}}},
      scales:{
        x:{type:'linear',min:-0.5,max:n-0.5,ticks:{stepSize:1,color:'#E8ECF1',
          font:{family:CHART_FONT.family,size:CHART_FONT.size},callback:v=>elems[v]||''},grid:{color:GRID}},
        y:{type:'linear',min:-0.5,max:n-0.5,reverse:true,ticks:{stepSize:1,color:'#E8ECF1',
          font:{family:CHART_FONT.family,size:CHART_FONT.size},callback:v=>elems[v]||''},grid:{color:GRID}}
      }}
  });
}

/* ═══ HEATMAP (combinations) ═══ */
function buildComboHeatmap() {
  destroyChart('comboHeat');
  const count = parseInt(document.getElementById('hm-count').value);
  const showNums = document.getElementById('hm-numbers').checked;
  const combos = DATA.combinations.slice(0,count);
  if(!combos.length) return;

  // Gather all elements across combos
  const allElems = new Set();
  combos.forEach(([name])=>name.split(' + ').forEach(e=>allElems.add(e.trim())));
  const elems = Array.from(allElems);

  // Build matrix: rows=combos, cols=elements, value=1 (present) or count
  const matrix = combos.map(([name, cnt])=>{
    const parts = name.split(' + ').map(e=>e.trim());
    return elems.map(el=>parts.includes(el)?cnt:0);
  });

  const labels = combos.map(([n,c])=>n+' ('+c+')');

  // Use stacked horizontal bars
  const datasets = elems.map((el,ei)=>({
    label:el,
    data:matrix.map(row=>row[ei]),
    backgroundColor:COLORS[ei%COLORS.length],
    borderRadius:2, borderSkipped:false,
  }));

  charts.comboHeat = new Chart(document.getElementById('comboHeatChart'),{
    type:'bar',
    data:{labels, datasets},
    options:{indexAxis:'y', responsive:true, maintainAspectRatio:false,
      plugins:{legend:{position:'top',labels:{color:CHART_FONT.color,font:{family:CHART_FONT.family},boxWidth:10,padding:10}},
               tooltip:tooltipOpts()},
      scales:{
        x:scaleOpts('x','Particle count',true),
        y:{grid:{display:false},ticks:{color:'#E8ECF1',font:{family:CHART_FONT.family,size:CHART_FONT.size}}}
      }}
  });
}

/* ═══ STATISTICS TABLE ═══ */
function buildStatsTable() {
  const dtype = document.getElementById('stats-dtype').value;
  const sKey = {diam:'diam_stats',mass:'mass_stats',moles:'moles_stats',counts:'counts_stats'}[dtype]||'diam_stats';
  const unit = {diam:'nm',mass:'fg',moles:'fmol',counts:'cts'}[dtype];
  const el = document.getElementById('stats-table');
  const labels = DATA.element_labels.slice(0,30);
  let html = `<table><thead><tr>
    <th>Element</th><th>Count</th><th>Mean (${unit})</th><th>Std</th>
    <th>Min</th><th>Q1</th><th>Median</th><th>Q3</th><th>Max</th>
  </tr></thead><tbody>`;
  labels.forEach(e=>{
    const s = DATA.element_stats[e];
    if(!s) return;
    const st = s[sKey]||{};
    const fmt = v => typeof v==='number' ? (Math.abs(v)>=100?v.toFixed(1):Math.abs(v)>=1?v.toFixed(2):v.toPrecision(3)) : '—';
    html += `<tr>
      <td>${e}</td><td>${s.count.toLocaleString()}</td>
      <td>${fmt(st.mean)}</td><td>${fmt(st.std)}</td>
      <td>${fmt(st.min)}</td><td>${fmt(st.q1)}</td><td>${fmt(st.median)}</td>
      <td>${fmt(st.q3)}</td><td>${fmt(st.max)}</td></tr>`;
  });
  html += '</tbody></table>';
  el.innerHTML = html;
}

/* Entry point */
window.loadDashboardData = init;
</script>
</body>
</html>"""


class DashboardDisplayDialog(QDialog):
    """Full-window enhanced Chart.js dashboard."""

    def __init__(self, dashboard_node, parent_window=None):
        """
        Args:
            dashboard_node (Any): The dashboard node.
            parent_window (Any): The parent window.
        """
        super().__init__(parent_window)
        self.node = dashboard_node
        self.parent_window = parent_window
        self.setWindowTitle("IsotopeTrack — Dashboard")
        self.setMinimumSize(1200, 800)
        self.resize(1500, 950)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if not HAS_WEBENGINE:
            msg = QLabel(
                "Dashboard requires QWebEngineView.\n\n"
                "Install with:\n  pip install PySide6-WebEngine\n\n"
                "Then restart IsotopeTrack."
            )
            msg.setAlignment(Qt.AlignCenter)
            msg.setStyleSheet("font-size: 16px; padding: 40px; color: #94A3B8;")
            layout.addWidget(msg)
            return

        self._web = QWebEngineView()
        layout.addWidget(self._web)

        self._web.setHtml(DASHBOARD_HTML)
        self._web.loadFinished.connect(self._inject_data)

    def _inject_data(self, ok):
        """
        Args:
            ok (Any): The ok.
        """
        if not ok:
            return

        data = self.node.get_output_data() if hasattr(self.node, 'get_output_data') else None
        if not data:
            data = self.node.input_data

        if not data or not data.get('particle_data'):
            self._web.page().runJavaScript(
                'document.body.innerHTML = "<div style=\\"text-align:center;'
                'padding:80px;color:#8B98AD;font-size:16px;font-family:Outfit,sans-serif;\\">'
                'No data connected.<br>Connect a sample selector node first.</div>";'
            )
            return

        dashboard_data = _build_dashboard_data(data)
        if not dashboard_data:
            return

        json_str = json.dumps(dashboard_data, default=str)
        json_str = json_str.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
        self._web.page().runJavaScript(f"loadDashboardData('{json_str}');")


class DashboardNode(QObject):
    position_changed = Signal(QPointF)
    configuration_changed = Signal()

    def __init__(self, parent_window=None):
        """
        Args:
            parent_window (Any): The parent window.
        """
        super().__init__()
        self.title = "Dashboard"
        self.node_type = "dashboard"
        self.position = QPointF(0, 0)
        self._has_input = True
        self._has_output = False
        self.input_channels = ["input"]
        self.output_channels = []
        self.parent_window = parent_window
        self.input_data = None

    def set_position(self, pos):
        """
        Args:
            pos (Any): Position point.
        """
        if self.position != pos:
            self.position = pos
            self.position_changed.emit(pos)

    def process_data(self, input_data):
        """
        Args:
            input_data (Any): The input data.
        """
        self.input_data = input_data
        self.configuration_changed.emit()

    def get_data_summary(self):
        """
        Returns:
            object: Result of the operation.
        """
        if not self.input_data:
            return "No data"
        n = len(self.input_data.get('particle_data', []))
        return f"{n:,} particles"

    def configure(self, parent_window):
        """
        Args:
            parent_window (Any): The parent window.
        Returns:
            bool: Result of the operation.
        """
        dlg = DashboardDisplayDialog(self, parent_window)
        dlg.exec()
        return True