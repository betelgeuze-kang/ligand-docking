#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence

from evaluate_idp_global_aggregation_calibrator import evaluate as evaluate_calibrator


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object: {path}")
    return payload


def _ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _default_md_path(out_json: str) -> str:
    if out_json.endswith(".json"):
        return out_json[:-5] + ".md"
    return out_json + ".md"


def _default_html_path(out_json: str) -> str:
    if out_json.endswith(".json"):
        return out_json[:-5] + ".html"
    return out_json + ".html"


def _derive_calibrator_json(manifest_json: str) -> str:
    base = os.path.basename(manifest_json)
    if "release_manifest" in base:
        derived = base.replace("release_manifest", "global_aggregation_calibrator")
        return os.path.join(os.path.dirname(manifest_json), derived)
    if manifest_json.endswith(".json"):
        return manifest_json[:-5] + "_global_aggregation_calibrator.json"
    return manifest_json + "_global_aggregation_calibrator.json"


def _derive_candidate_eval_json(manifest: Dict[str, Any], manifest_json: str) -> str:
    prefix = str(manifest.get("release_prefix", "")).strip()
    if prefix:
        return f"{prefix}_release_candidate_eval.json"
    if manifest_json.endswith("_release_manifest.json"):
        return manifest_json[: -len("_release_manifest.json")] + "_release_candidate_eval.json"
    if manifest_json.endswith(".json"):
        return manifest_json[:-5] + "_release_candidate_eval.json"
    return manifest_json + "_release_candidate_eval.json"


def _derive_calibrator_md(calibrator_json: str) -> str:
    return calibrator_json[:-5] + ".md" if calibrator_json.endswith(".json") else calibrator_json + ".md"


def _derive_predictions_csv(calibrator_json: str) -> str:
    return (
        calibrator_json[:-5] + "_predictions.csv"
        if calibrator_json.endswith(".json")
        else calibrator_json + "_predictions.csv"
    )


def _infer_current_release_label(path: str) -> str:
    candidate = str(path).strip()
    if not candidate or not os.path.exists(candidate):
        return ""
    payload = _load_json(candidate)
    return str(payload.get("release_label", "")).strip()


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    return f"{float(v):.4f}"


def _delta_cell(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    cls = "delta-pos" if float(v) >= 0.0 else "delta-neg"
    return f"<span class='{cls}'>{_fmt(v)}</span>"


def _gate_badge(v: Any) -> str:
    if v is None:
        return "n/a"
    passed = bool(v)
    cls = "gate-pass" if passed else "gate-fail"
    label = "true" if passed else "false"
    return f"<span class='{cls}'>{label}</span>"


def _render_html(payload: Dict[str, Any], *, current_release_label: str = "") -> str:
    rows = list(payload.get("comparison", []) or [])
    top_non_current = next((row for row in rows if str(row.get("release_label", "")) != current_release_label), rows[0] if rows else {})
    current_row = next((row for row in rows if str(row.get("release_label", "")) == current_release_label), rows[0] if rows else {})
    cards = [
        ("Candidates", len(rows), "historical releases compared"),
        ("Best Calibrated Global AP", _fmt(top_non_current.get("calibrated_global_aggregation_pr_auc")), str(top_non_current.get("release_label", ""))),
        ("Best Improvement", _fmt(max((float(r.get("improvement_vs_raw_global_pr_auc") or 0.0) for r in rows), default=0.0)), "calibrated - raw"),
    ]
    card_html = "".join(
        '<div class="card">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f'<div class="sub">{sub}</div>'
        '</div>'
        for label, value, sub in cards
    )
    body_rows = []
    for row in rows:
        release_label = str(row.get("release_label", ""))
        release_cell = release_label
        if current_release_label and release_label == current_release_label:
            release_cell = f"{release_label} <span class='badge'>current</span>"
        body_rows.append(
            "<tr>"
            + f"<td>{release_cell}</td>"
            + f"<td>{_fmt(row.get('raw_global_aggregation_pr_auc'))}</td>"
            + f"<td>{_fmt(row.get('calibrated_global_aggregation_pr_auc'))}</td>"
            + f"<td>{_delta_cell(row.get('delta_vs_current_raw_global_ap'))}</td>"
            + f"<td>{_delta_cell(row.get('delta_vs_current_calibrated_global_ap'))}</td>"
            + f"<td>{_fmt(row.get('improvement_vs_raw_global_pr_auc'))}</td>"
            + f"<td>{_fmt(row.get('oof_aggregation_prone_ap'))}</td>"
            + f"<td>{_fmt(row.get('oof_llps_lcd_ap'))}</td>"
            + f"<td>{_fmt(row.get('oof_helix_tad_ap'))}</td>"
            + f"<td>{row.get('all_fold_pass', 'n/a')}</td>"
            + f"<td>{row.get('corrected_pass_folds', 'n/a')}/{row.get('fold_count', 'n/a')}</td>"
            + f"<td>{_gate_badge(row.get('combined_gate_pass'))}</td>"
            + f"<td>{_delta_cell(row.get('train_eval_speedup_frac'))}</td>"
            + f"<td>{_delta_cell(row.get('eval_corrected_speedup_frac'))}</td>"
            + "</tr>"
        )
    table_html = (
        "<table><thead><tr>"
        "<th>Release</th><th>Raw Global AP</th><th>Calibrated Global AP</th><th>Δ Raw vs Current</th><th>Δ Calibrated vs Current</th><th>Improvement</th>"
        "<th>Agg OOF</th><th>LLPS OOF</th><th>Helix OOF</th><th>All Fold Pass</th><th>Corrected</th><th>Combined Gate</th><th>Train Eval Δ</th><th>Eval Corrected Δ</th>"
        "</tr></thead><tbody>"
        + "".join(body_rows)
        + "</tbody></table>"
    )
    return f"""<!doctype html>
<html lang=\"ko\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>IDP Global Aggregation Comparison</title>
<style>
body {{ font-family: -apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif; margin:24px; background:#f6f8fb; color:#16202a; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin:16px 0 24px; }}
.card {{ background:#fff; border:1px solid #dbe2ea; border-radius:14px; padding:16px; }}
.label {{ font-size:12px; color:#5f6b7a; text-transform:uppercase; }}
.value {{ font-size:28px; font-weight:700; margin-top:8px; }}
.sub {{ font-size:12px; color:#6a7685; margin-top:6px; }}
table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid #dbe2ea; }}
th,td {{ padding:10px 12px; border-bottom:1px solid #eef2f6; text-align:left; }}
th {{ background:#eef4fb; }}
.badge {{ display:inline-block; margin-left:8px; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:700; background:#dcfce7; color:#166534; vertical-align:middle; }}
.delta-pos {{ color:#166534; font-weight:700; }}
.delta-neg {{ color:#b91c1c; font-weight:700; }}
.gate-pass {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:700; background:#dcfce7; color:#166534; }}
.gate-fail {{ display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:700; background:#fee2e2; color:#991b1b; }}
</style>
</head>
<body>
<h1>IDP Global Aggregation Comparison</h1>
<p>Historical calibrated global aggregation diagnostic comparison across release candidates.</p>
<p>{('Current baseline: <strong>' + current_release_label + '</strong>') if current_release_label else 'Current baseline label unavailable.'}</p>
<p class="sub">`Δ Raw vs Current`와 `Δ Calibrated vs Current`는 현재 baseline 기준의 직접 비교값입니다. `Train Eval Δ`와 `Eval Corrected Δ`는 각 후보가 생성될 당시 candidate eval 기준값이라, historical runtime 비교는 보조 신호로만 보세요.</p>
<div class=\"grid\">{card_html}</div>
{table_html}
</body>
</html>
"""


def compare(args: argparse.Namespace) -> Dict[str, Any]:
    manifests = [str(x) for x in list(args.manifest_jsons)]
    if not manifests:
        raise ValueError("at least one --manifest-json is required")
    current_release_label = _infer_current_release_label(str(getattr(args, "current_manifest_json", "")).strip())

    rows: List[Dict[str, Any]] = []
    for manifest_json in manifests:
        manifest = _load_json(manifest_json)
        calibrator_json = str(args.calibrator_json_prefix).strip()
        if calibrator_json:
            raise ValueError("calibrator_json_prefix override is not supported in compare mode")
        calibrator_json = _derive_calibrator_json(manifest_json)
        if not os.path.exists(calibrator_json) or bool(int(args.refresh_missing)):
            evaluate_calibrator(
                SimpleNamespace(
                    manifest_json=manifest_json,
                    out_json=calibrator_json,
                    out_md=_derive_calibrator_md(calibrator_json),
                    out_predictions_csv=_derive_predictions_csv(calibrator_json),
                    l2=float(args.l2),
                    iters=int(args.iters),
                    lr=float(args.lr),
                    top_k=int(args.top_k),
                    min_improvement=float(args.min_improvement),
                )
            )
        calibrator = _load_json(calibrator_json)
        baseline_metrics = dict(calibrator.get("baseline_metrics", {}) or {})
        calibrated_metrics = dict(calibrator.get("calibrated_metrics", {}) or {})
        accept = dict(manifest.get("acceptance", {}) or {})
        candidate_eval_json = _derive_candidate_eval_json(manifest, manifest_json)
        candidate_eval = _load_json(candidate_eval_json) if os.path.exists(candidate_eval_json) else {}
        runtime = dict(candidate_eval.get("runtime_comparison", {}) or {})
        row = {
            "release_label": manifest.get("release_label"),
            "manifest_json": manifest_json,
            "calibrator_json": calibrator_json,
            "raw_global_aggregation_pr_auc": baseline_metrics.get("raw_global_aggregation_pr_auc"),
            "calibrated_global_aggregation_pr_auc": calibrated_metrics.get("oof_global_aggregation_pr_auc"),
            "improvement_vs_raw_global_pr_auc": calibrated_metrics.get("improvement_vs_raw_global_pr_auc"),
            "raw_aggregation_prone_ap": (baseline_metrics.get("raw_branch_aggregation_pr_auc", {}) or {}).get("aggregation_prone"),
            "raw_llps_lcd_ap": (baseline_metrics.get("raw_branch_aggregation_pr_auc", {}) or {}).get("llps_lcd"),
            "raw_helix_tad_ap": (baseline_metrics.get("raw_branch_aggregation_pr_auc", {}) or {}).get("helix_tad"),
            "oof_aggregation_prone_ap": (calibrated_metrics.get("oof_branch_aggregation_pr_auc", {}) or {}).get("aggregation_prone"),
            "oof_llps_lcd_ap": (calibrated_metrics.get("oof_branch_aggregation_pr_auc", {}) or {}).get("llps_lcd"),
            "oof_helix_tad_ap": (calibrated_metrics.get("oof_branch_aggregation_pr_auc", {}) or {}).get("helix_tad"),
            "all_fold_pass": accept.get("all_fold_pass"),
            "fold_count": accept.get("fold_count"),
            "corrected_pass_folds": accept.get("corrected_pass_folds"),
            "combined_gate_pass": accept.get("combined_gate_pass"),
            "candidate_eval_json": candidate_eval_json if candidate_eval else "",
            "train_eval_speedup_frac": runtime.get("train_eval_speedup_frac"),
            "eval_corrected_speedup_frac": runtime.get("eval_corrected_speedup_frac"),
        }
        rows.append(row)

    def _sort_key(x: Dict[str, Any]) -> tuple:
        is_current = 0 if (current_release_label and str(x.get("release_label", "")) == current_release_label) else 1
        return (
            is_current,
            -float(x.get("calibrated_global_aggregation_pr_auc") or 0.0),
            -float(x.get("improvement_vs_raw_global_pr_auc") or 0.0),
        )

    rows.sort(key=_sort_key)
    current_row = next((row for row in rows if current_release_label and str(row.get("release_label", "")) == current_release_label), rows[0] if rows else {})
    current_raw = current_row.get("raw_global_aggregation_pr_auc")
    current_cal = current_row.get("calibrated_global_aggregation_pr_auc")
    for row in rows:
        raw_v = row.get("raw_global_aggregation_pr_auc")
        cal_v = row.get("calibrated_global_aggregation_pr_auc")
        row["delta_vs_current_raw_global_ap"] = (
            float(raw_v) - float(current_raw)
            if raw_v is not None and current_raw is not None
            else None
        )
        row["delta_vs_current_calibrated_global_ap"] = (
            float(cal_v) - float(current_cal)
            if cal_v is not None and current_cal is not None
            else None
        )
    payload: Dict[str, Any] = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "manifests": manifests,
        "current_release_label": current_release_label,
        "comparison": rows,
    }

    out_json = str(args.out_json)
    out_md = str(args.out_md).strip() or _default_md_path(out_json)
    out_html = str(args.out_html).strip() or _default_html_path(out_json)
    _ensure_parent(out_json)
    _ensure_parent(out_md)
    _ensure_parent(out_html)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# IDP Global Aggregation Calibrator Comparison\n\n")
        if current_release_label:
            f.write(f"Current baseline: `{current_release_label}`\n\n")
        f.write("> `Δ Raw vs Current`와 `Δ Calibrated vs Current`는 현재 baseline 기준 직접 비교값입니다. `Train Eval Δ`와 `Eval Corrected Δ`는 각 후보가 생성될 당시 candidate eval 기준값이라 historical runtime 비교는 보조 신호로만 봅니다.\n\n")
        f.write("| Release | Raw Global AP | Calibrated Global AP | Δ Raw vs Current | Δ Calibrated vs Current | Improvement | Agg Branch | LLPS Branch | Helix Branch | All Fold Pass | Corrected | Combined Gate | Train Eval Δ | Eval Corrected Δ |\n")
        f.write("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: | ---: |\n")
        for row in rows:
            f.write(
                "| "
                + f"`{row['release_label']}` | "
                + f"`{_fmt(row['raw_global_aggregation_pr_auc'])}` | "
                + f"`{_fmt(row['calibrated_global_aggregation_pr_auc'])}` | "
                + f"`{_fmt(row['delta_vs_current_raw_global_ap'])}` | "
                + f"`{_fmt(row['delta_vs_current_calibrated_global_ap'])}` | "
                + f"`{_fmt(row['improvement_vs_raw_global_pr_auc'])}` | "
                + f"`{_fmt(row['oof_aggregation_prone_ap'])}` | "
                + f"`{_fmt(row['oof_llps_lcd_ap'])}` | "
                + f"`{_fmt(row['oof_helix_tad_ap'])}` | "
                + f"`{row.get('all_fold_pass')}` | "
                + f"`{row.get('corrected_pass_folds')}/{row.get('fold_count')}` | "
                + f"`{row.get('combined_gate_pass')}` | "
                + f"`{_fmt(row.get('train_eval_speedup_frac'))}` | "
                + f"`{_fmt(row.get('eval_corrected_speedup_frac'))}` |\n"
            )
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(_render_html(payload, current_release_label=current_release_label))
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Compare diagnostic global aggregation calibrators across release manifests.")
    p.add_argument("--manifest-json", dest="manifest_jsons", action="append", required=True)
    p.add_argument("--out-json", required=True)
    p.add_argument("--out-md", default="")
    p.add_argument("--out-html", default="")
    p.add_argument("--current-manifest-json", default="runs/idp_3bead_release_manifest_current.json")
    p.add_argument("--refresh-missing", type=int, default=1)
    p.add_argument("--calibrator-json-prefix", default="")
    p.add_argument("--l2", type=float, default=0.05)
    p.add_argument("--iters", type=int, default=4000)
    p.add_argument("--lr", type=float, default=0.03)
    p.add_argument("--top-k", type=int, default=8)
    p.add_argument("--min-improvement", type=float, default=0.05)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = compare(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
