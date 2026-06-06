#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f'invalid json object: {path}')
    return payload


def _ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _fmt(v: Any) -> str:
    if v is None:
        return 'n/a'
    if isinstance(v, float):
        return f'{v:.4f}'
    return str(v)


def _resolve_pred_csv(manifest: Dict[str, Any], manifest_json: str) -> str:
    diag = dict(manifest.get('diagnostic_artifacts', {}) or {})
    path = str(diag.get('global_aggregation_predictions_csv', '')).strip()
    if not path:
        raise ValueError(f'manifest missing diagnostic_artifacts.global_aggregation_predictions_csv: {manifest_json}')
    return path


def _resolve_calibrator_json(manifest: Dict[str, Any], manifest_json: str) -> str:
    diag = dict(manifest.get('diagnostic_artifacts', {}) or {})
    path = str(diag.get('global_aggregation_calibrator_json', '')).strip()
    if path:
        return path
    base = os.path.basename(manifest_json)
    if 'release_manifest' in base:
        return os.path.join(os.path.dirname(manifest_json), base.replace('release_manifest', 'global_aggregation_calibrator'))
    if manifest_json.endswith('.json'):
        return manifest_json[:-5] + '_global_aggregation_calibrator.json'
    return manifest_json + '_global_aggregation_calibrator.json'


def _table(headers: List[str], rows: List[List[str]]) -> str:
    thead = ''.join(f'<th>{html.escape(h)}</th>' for h in headers)
    body = []
    for row in rows:
        body.append('<tr>' + ''.join(f'<td>{html.escape(str(cell))}</td>' for cell in row) + '</tr>')
    return '<table><thead><tr>' + thead + '</tr></thead><tbody>' + ''.join(body) + '</tbody></table>'


def _bar_cell(value: Any, *, positive_color: str = "#2563eb", negative_color: str = "#dc2626", width_scale: float = 100.0) -> str:
    try:
        v = float(value)
    except Exception:
        return f'<span>{html.escape(_fmt(value))}</span>'
    mag = max(0.0, min(abs(v) * width_scale, 100.0))
    color = positive_color if v >= 0.0 else negative_color
    return (
        '<div style="display:flex; align-items:center; gap:10px;">'
        f'<span style="min-width:58px;">{html.escape(_fmt(v))}</span>'
        '<div style="flex:1; height:10px; background:#eef2f6; border-radius:999px; overflow:hidden;">'
        f'<div style="width:{mag:.1f}%; height:100%; background:{color};"></div>'
        '</div>'
        '</div>'
    )


def build_payload(manifest_json: str, compare_json: str = '', top_k: int = 20) -> Dict[str, Any]:
    manifest = _load_json(manifest_json)
    calibrator_json = _resolve_calibrator_json(manifest, manifest_json)
    calibrator = _load_json(calibrator_json)
    pred_csv = _resolve_pred_csv(manifest, manifest_json)
    df = pd.read_csv(pred_csv)
    df['risk_gap'] = df['pred_aggregation_risk_global'].astype(float) - df['pred_aggregation_prob'].astype(float)

    branch_summary = (
        df.groupby('branch_label', dropna=False)
        .agg(
            rows=('branch_label', 'size'),
            positives=('true_aggregation_flag', 'sum'),
            mean_raw_prob=('pred_aggregation_prob', 'mean'),
            mean_global_risk=('pred_aggregation_risk_global', 'mean'),
            mean_risk_gap=('risk_gap', 'mean'),
        )
        .reset_index()
        .sort_values('mean_global_risk', ascending=False, kind='mergesort')
        .to_dict(orient='records')
    )
    holdout_summary = (
        df.groupby('__holdout', dropna=False)
        .agg(
            rows=('__holdout', 'size'),
            positives=('true_aggregation_flag', 'sum'),
            mean_raw_prob=('pred_aggregation_prob', 'mean'),
            mean_global_risk=('pred_aggregation_risk_global', 'mean'),
            mean_risk_gap=('risk_gap', 'mean'),
        )
        .reset_index()
        .sort_values('mean_global_risk', ascending=False, kind='mergesort')
        .to_dict(orient='records')
    )
    top_rows = (
        df.sort_values('pred_aggregation_risk_global', ascending=False, kind='mergesort')
        .head(max(int(top_k), 1))[
            [
                '__fold_index', '__holdout', 'target', 'condition_group', 'branch_label', 'pred_state',
                'true_aggregation_flag', 'pred_aggregation_prob', 'pred_aggregation_risk_global',
                'risk_gap', 'pred_rank_compactness', 'pred_rank_helicity', 'pred_rank_condensation'
            ]
        ].to_dict(orient='records')
    )
    all_rows_light = df[
        [
            '__fold_index', '__holdout', 'target', 'condition_group', 'branch_label', 'pred_state',
            'true_aggregation_flag', 'pred_aggregation_prob', 'pred_aggregation_risk_global',
            'risk_gap', 'pred_rank_compactness', 'pred_rank_helicity', 'pred_rank_condensation'
        ]
    ].sort_values('pred_aggregation_risk_global', ascending=False, kind='mergesort').to_dict(orient='records')

    compare_payload: Dict[str, Any] = {}
    if compare_json and os.path.exists(compare_json):
        compare_payload = _load_json(compare_json)

    return {
        'manifest_json': manifest_json,
        'manifest': manifest,
        'calibrator_json': calibrator_json,
        'calibrator': calibrator,
        'predictions_csv': pred_csv,
        'branch_summary': branch_summary,
        'holdout_summary': holdout_summary,
        'top_rows': top_rows,
        'all_rows_light': all_rows_light,
        'historical_compare': compare_payload,
    }


def render_html(payload: Dict[str, Any]) -> str:
    manifest = payload['manifest']
    calibrator = payload['calibrator']
    baseline = dict(calibrator.get('baseline_metrics', {}) or {})
    calibrated = dict(calibrator.get('calibrated_metrics', {}) or {})
    compare = dict(payload.get('historical_compare', {}) or {})
    comparison_rows = list(compare.get('comparison', []) or [])
    release_label = str(manifest.get('release_label', ''))
    all_rows_light = list(payload.get('all_rows_light', []) or [])

    branch_rows = [[
        row['branch_label'], row['rows'], row['positives'], _fmt(row['mean_raw_prob']), _fmt(row['mean_global_risk']), _fmt(row['mean_risk_gap'])
    ] for row in payload['branch_summary']]
    holdout_rows = [[
        row['__holdout'], row['rows'], row['positives'], _fmt(row['mean_raw_prob']), _fmt(row['mean_global_risk']), _fmt(row['mean_risk_gap'])
    ] for row in payload['holdout_summary'][:20]]
    top_rows = [[
        row['__fold_index'], row['__holdout'], row['condition_group'], row['branch_label'], row['pred_state'],
        _fmt(row['pred_aggregation_prob']), _fmt(row['pred_aggregation_risk_global']), _fmt(row['risk_gap'])
    ] for row in payload['top_rows']]
    hist_rows = [[
        row.get('release_label', ''), _fmt(row.get('raw_global_aggregation_pr_auc')),
        _fmt(row.get('calibrated_global_aggregation_pr_auc')),
        _fmt(row.get('improvement_vs_raw_global_pr_auc')),
        _fmt(row.get('oof_aggregation_prone_ap')),
        _fmt(row.get('oof_llps_lcd_ap')),
        _fmt(row.get('oof_helix_tad_ap')),
    ] for row in comparison_rows]
    branch_options = sorted({str(row.get('branch_label', '')) for row in all_rows_light if str(row.get('branch_label', '')).strip()})
    holdout_options = sorted({str(row.get('__holdout', '')) for row in all_rows_light if str(row.get('__holdout', '')).strip()})
    top_risky_holdouts = list(payload["holdout_summary"][:3])

    branch_summary_html = "<table><thead><tr><th>Branch</th><th>Rows</th><th>Positives</th><th>Mean Raw</th><th>Mean Global</th><th>Mean Gap</th></tr></thead><tbody>"
    for row in payload["branch_summary"]:
        branch_badge = f'<span class="badge branch-{html.escape(str(row["branch_label"]))}">{html.escape(str(row["branch_label"]))}</span>'
        branch_summary_html += (
            "<tr>"
            + f"<td>{branch_badge}</td>"
            + f"<td>{int(row['rows'])}</td>"
            + f"<td>{int(row['positives'])}</td>"
            + f"<td>{_bar_cell(row['mean_raw_prob'], positive_color='#7c3aed', width_scale=100.0)}</td>"
            + f"<td>{_bar_cell(row['mean_global_risk'], positive_color='#2563eb', width_scale=100.0)}</td>"
            + f"<td>{_bar_cell(row['mean_risk_gap'], positive_color='#059669', negative_color='#dc2626', width_scale=160.0)}</td>"
            + "</tr>"
        )
    branch_summary_html += "</tbody></table>"

    holdout_summary_html = "<table><thead><tr><th>Holdout</th><th>Rows</th><th>Positives</th><th>Mean Raw</th><th>Mean Global</th><th>Mean Gap</th></tr></thead><tbody>"
    for row in payload["holdout_summary"][:20]:
        holdout_summary_html += (
            "<tr>"
            + f"<td>{html.escape(str(row['__holdout']))}</td>"
            + f"<td>{int(row['rows'])}</td>"
            + f"<td>{int(row['positives'])}</td>"
            + f"<td>{_bar_cell(row['mean_raw_prob'], positive_color='#7c3aed', width_scale=100.0)}</td>"
            + f"<td>{_bar_cell(row['mean_global_risk'], positive_color='#2563eb', width_scale=100.0)}</td>"
            + f"<td>{_bar_cell(row['mean_risk_gap'], positive_color='#059669', negative_color='#dc2626', width_scale=160.0)}</td>"
            + "</tr>"
        )
    holdout_summary_html += "</tbody></table>"

    def card(title: str, value: Any, sub: str = '') -> str:
        return (
            '<div class="card">'
            f'<div class="label">{html.escape(title)}</div>'
            f'<div class="value">{html.escape(_fmt(value))}</div>'
            f'<div class="sub">{html.escape(sub)}</div>'
            '</div>'
        )

    cards = ''.join([
        card('Release', release_label, os.path.basename(payload['manifest_json'])),
        card('Raw Global AP', baseline.get('raw_global_aggregation_pr_auc'), 'branch-unaware diagnostic'),
        card('Calibrated Global AP', calibrated.get('oof_global_aggregation_pr_auc'), 'OOF post-hoc diagnostic'),
        card('Improvement', calibrated.get('improvement_vs_raw_global_pr_auc'), 'calibrated - raw'),
    ])
    risky_cards = ''.join(
        (
            '<button class="card risky-card" type="button" '
            + f'data-holdout="{html.escape(str(row.get("__holdout", "")))}">'
            + f'<div class="label">Top Risk #{idx}</div>'
            + f'<div class="value">{html.escape(_fmt(row.get("mean_global_risk")))}</div>'
            + f'<div class="sub">{html.escape(str(row.get("__holdout", "")))} | gap={html.escape(_fmt(row.get("mean_risk_gap")))}</div>'
            + '</button>'
        )
        for idx, row in enumerate(top_risky_holdouts, start=1)
    )

    return f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>IDP Global Aggregation Dashboard</title>
<style>
body {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; margin: 24px; color:#16202a; background:#f6f8fb; }}
h1,h2 {{ margin: 0 0 12px 0; }}
small, .muted {{ color:#5f6b7a; }}
.grid {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin: 16px 0 24px; }}
.card {{ background:#fff; border:1px solid #dbe2ea; border-radius:14px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,0.03); }}
.risky-card {{ text-align:left; cursor:pointer; }}
.risky-card:hover {{ border-color:#93c5fd; box-shadow:0 3px 10px rgba(37,99,235,0.10); }}
.label {{ font-size:12px; color:#5f6b7a; text-transform:uppercase; letter-spacing:.03em; }}
.value {{ font-size:28px; font-weight:700; margin-top:8px; }}
.sub {{ font-size:12px; color:#6a7685; margin-top:6px; }}
section {{ margin: 24px 0; }}
table {{ width:100%; border-collapse: collapse; background:#fff; border:1px solid #dbe2ea; border-radius:14px; overflow:hidden; }}
th,td {{ padding:10px 12px; border-bottom:1px solid #eef2f6; text-align:left; font-size:14px; }}
th {{ background:#eef4fb; }}
tr:last-child td {{ border-bottom:none; }}
.code {{ font-family: ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; background:#edf2f7; padding:2px 6px; border-radius:6px; }}
.controls {{ display:flex; gap:12px; flex-wrap:wrap; margin: 12px 0 16px; }}
.controls label {{ font-size:12px; color:#5f6b7a; display:flex; flex-direction:column; gap:6px; }}
.controls input,.controls select {{ min-width:180px; padding:8px 10px; border:1px solid #cfd8e3; border-radius:10px; background:#fff; }}
.controls .button-wrap {{ justify-content:flex-end; }}
.controls button {{ min-width:140px; padding:8px 12px; border:1px solid #cfd8e3; border-radius:10px; background:#fff; cursor:pointer; font-weight:600; color:#334155; }}
.controls button:hover {{ background:#f8fafc; border-color:#93c5fd; }}
.badge {{ display:inline-block; padding:3px 8px; border-radius:999px; font-size:12px; font-weight:600; }}
.branch-aggregation_prone {{ background:#fee2e2; color:#991b1b; }}
.branch-llps_lcd {{ background:#dbeafe; color:#1d4ed8; }}
.branch-helix_tad {{ background:#dcfce7; color:#166534; }}
.sort-note {{ font-size:12px; color:#6a7685; margin-top:-6px; margin-bottom:10px; }}
</style>
</head>
<body>
<h1>IDP Global Aggregation Dashboard</h1>
<p class="muted">Release-level diagnostic view for branch-local aggregation scores and calibrated global aggregation risk.</p>
<div class="grid">{cards}</div>
<section>
<h2>Top Risky Holdouts</h2>
<div class="grid">{risky_cards}</div>
</section>
<section>
<h2>Artifacts</h2>
<p><span class="code">manifest</span> {html.escape(payload['manifest_json'])}<br/>
<span class="code">calibrator</span> {html.escape(payload['calibrator_json'])}<br/>
<span class="code">predictions</span> {html.escape(payload['predictions_csv'])}</p>
</section>
<section>
<h2>Branch Summary</h2>
{branch_summary_html}
</section>
<section>
<h2>Historical Comparison</h2>
{_table(['Release','Raw Global AP','Calibrated Global AP','Improvement','Agg OOF','LLPS OOF','Helix OOF'], hist_rows) if hist_rows else '<p class="muted">No historical comparison JSON provided.</p>'}
</section>
<section>
<h2>Top Global Aggregation Risk Rows</h2>
<div class="controls">
  <label>Search
    <input id="searchInput" type="text" placeholder="holdout / target / condition / state" />
  </label>
  <label>Branch
    <select id="branchFilter">
      <option value="">All</option>
      {''.join(f'<option value="{html.escape(x)}">{html.escape(x)}</option>' for x in branch_options)}
    </select>
  </label>
  <label>Holdout
    <select id="holdoutFilter">
      <option value="">All</option>
      {''.join(f'<option value="{html.escape(x)}">{html.escape(x)}</option>' for x in holdout_options)}
    </select>
  </label>
  <label>Row Sort
    <select id="rowSort">
      <option value="pred_aggregation_risk_global:desc">Global Risk ↓</option>
      <option value="pred_aggregation_risk_global:asc">Global Risk ↑</option>
      <option value="pred_aggregation_prob:desc">Raw Prob ↓</option>
      <option value="pred_aggregation_prob:asc">Raw Prob ↑</option>
      <option value="risk_gap:desc">Gap ↓</option>
      <option value="risk_gap:asc">Gap ↑</option>
    </select>
  </label>
  <label>Holdout Sort
    <select id="holdoutSort">
      <option value="mean_global_risk:desc">Mean Global ↓</option>
      <option value="mean_global_risk:asc">Mean Global ↑</option>
      <option value="mean_raw_prob:desc">Mean Raw ↓</option>
      <option value="mean_raw_prob:asc">Mean Raw ↑</option>
      <option value="mean_risk_gap:desc">Mean Gap ↓</option>
      <option value="mean_risk_gap:asc">Mean Gap ↑</option>
    </select>
  </label>
  <label class="button-wrap">Filters
    <button id="resetFilters" type="button">Reset Filters</button>
  </label>
</div>
<div class="sort-note">branch는 색상 배지로 표시되고, row/holdout 정렬은 드롭다운에서 바로 바꿀 수 있습니다.</div>
<div id="rowsTable"></div>
</section>
<section>
<h2>Top Holdouts By Mean Global Risk</h2>
<div id="holdoutTable">{holdout_summary_html}</div>
</section>
<script>
const allRows = {json.dumps(all_rows_light, ensure_ascii=False)};
const allHoldouts = {json.dumps(payload['holdout_summary'], ensure_ascii=False)};

function esc(x) {{
  return String(x ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
}}

function renderTable(rows) {{
  const header = ['Fold','Holdout','Condition','Branch','State','Raw','Global','Gap'];
  const body = rows.map((row) => {{
    const branchBadge = `<span class="badge branch-${{esc(row.branch_label)}}">${{esc(row.branch_label)}}</span>`;
    const cells = [
      row.__fold_index,
      row.__holdout,
      row.condition_group,
      branchBadge,
      row.pred_state,
      Number(row.pred_aggregation_prob).toFixed(4),
      Number(row.pred_aggregation_risk_global).toFixed(4),
      Number(row.risk_gap).toFixed(4),
    ];
    return '<tr>' + cells.map((x, i) => i === 3 ? `<td>${{x}}</td>` : `<td>${{esc(x)}}</td>`).join('') + '</tr>';
  }}).join('');
  return '<table><thead><tr>' + header.map((x) => `<th>${{esc(x)}}</th>`).join('') + '</tr></thead><tbody>' + body + '</tbody></table>';
}}

function renderHoldoutTable(rows) {{
  const header = ['Holdout','Rows','Positives','Mean Raw','Mean Global','Mean Gap'];
  const bar = (v, positive='#2563eb', negative='#dc2626', scale=100.0) => {{
    const num = Number(v ?? 0);
    const mag = Math.max(0, Math.min(Math.abs(num) * scale, 100));
    const color = num >= 0 ? positive : negative;
    return `<div style="display:flex; align-items:center; gap:10px;"><span style="min-width:58px;">${{num.toFixed(4)}}</span><div style="flex:1; height:10px; background:#eef2f6; border-radius:999px; overflow:hidden;"><div style="width:${{mag}}%; height:100%; background:${{color}};"></div></div></div>`;
  }};
  const body = rows.map((row) => {{
    const cells = [
      row.__holdout,
      row.rows,
      row.positives,
      bar(row.mean_raw_prob, '#7c3aed', '#7c3aed', 100),
      bar(row.mean_global_risk, '#2563eb', '#2563eb', 100),
      bar(row.mean_risk_gap, '#059669', '#dc2626', 160),
    ];
    return '<tr>' + cells.map((x, i) => i >= 3 ? `<td>${{x}}</td>` : `<td>${{esc(x)}}</td>`).join('') + '</tr>';
  }}).join('');
  return '<table><thead><tr>' + header.map((x) => `<th>${{esc(x)}}</th>`).join('') + '</tr></thead><tbody>' + body + '</tbody></table>';
}}

function applyFilters() {{
  const q = document.getElementById('searchInput').value.trim().toLowerCase();
  const branch = document.getElementById('branchFilter').value;
  const holdout = document.getElementById('holdoutFilter').value;
  const rowSort = document.getElementById('rowSort').value;
  const holdoutSort = document.getElementById('holdoutSort').value;
  const [rowSortKey, rowSortDir] = rowSort.split(':');
  const [holdoutSortKey, holdoutSortDir] = holdoutSort.split(':');
  const rows = allRows.filter((row) => {{
    if (branch && row.branch_label !== branch) return false;
    if (holdout && row.__holdout !== holdout) return false;
    if (!q) return true;
    const hay = [row.__holdout, row.target, row.condition_group, row.branch_label, row.pred_state].join(' ').toLowerCase();
    return hay.includes(q);
  }});
  rows.sort((a, b) => {{
    const av = Number(a[rowSortKey] ?? 0);
    const bv = Number(b[rowSortKey] ?? 0);
    return rowSortDir === 'asc' ? av - bv : bv - av;
  }});
  document.getElementById('rowsTable').innerHTML = renderTable(rows.slice(0, 50));
  const holdouts = allHoldouts.filter((row) => (!holdout || row.__holdout === holdout) && (!q || String(row.__holdout).toLowerCase().includes(q)));
  holdouts.sort((a, b) => {{
    const av = Number(a[holdoutSortKey] ?? 0);
    const bv = Number(b[holdoutSortKey] ?? 0);
    return holdoutSortDir === 'asc' ? av - bv : bv - av;
  }});
  document.getElementById('holdoutTable').innerHTML = renderHoldoutTable(holdouts.slice(0, 20));
}}

document.getElementById('searchInput').addEventListener('input', applyFilters);
document.getElementById('branchFilter').addEventListener('change', applyFilters);
document.getElementById('holdoutFilter').addEventListener('change', applyFilters);
document.getElementById('rowSort').addEventListener('change', applyFilters);
document.getElementById('holdoutSort').addEventListener('change', applyFilters);
document.getElementById('resetFilters').addEventListener('click', () => {{
  document.getElementById('searchInput').value = '';
  document.getElementById('branchFilter').value = '';
  document.getElementById('holdoutFilter').value = '';
  document.getElementById('rowSort').value = 'pred_aggregation_risk_global:desc';
  document.getElementById('holdoutSort').value = 'mean_global_risk:desc';
  applyFilters();
}});
document.querySelectorAll('.risky-card').forEach((node) => {{
  node.addEventListener('click', () => {{
    const holdout = node.dataset.holdout || '';
    document.getElementById('holdoutFilter').value = holdout;
    applyFilters();
    document.getElementById('rowsTable').scrollIntoView({{ behavior: 'smooth', block: 'start' }});
  }});
}});
applyFilters();
</script>
</body>
</html>
'''


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = argparse.ArgumentParser(description='Build a simple HTML dashboard for IDP global aggregation diagnostics.')
    p.add_argument('--manifest-json', required=True)
    p.add_argument('--compare-json', default='')
    p.add_argument('--top-k', type=int, default=20)
    p.add_argument('--out-html', required=True)
    p.add_argument('--out-json', default='')
    args = p.parse_args(argv)

    payload = build_payload(str(args.manifest_json), str(args.compare_json), int(args.top_k))
    _ensure_parent(str(args.out_html))
    Path(str(args.out_html)).write_text(render_html(payload), encoding='utf-8')
    out_json = str(args.out_json).strip()
    if out_json:
        _ensure_parent(out_json)
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    print(str(args.out_html))


if __name__ == '__main__':
    main()
