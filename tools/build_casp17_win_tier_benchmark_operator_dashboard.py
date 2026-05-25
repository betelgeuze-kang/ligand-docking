#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OPERATOR_TEMPLATE_CSV = "runs/casp17_win_tier_benchmark_operator_template_current.csv"
DEFAULT_OPERATOR_PREFLIGHT_JSON = "runs/casp17_win_tier_benchmark_operator_preflight_current.json"
DEFAULT_OPERATOR_PREFLIGHT_CSV = "runs/casp17_win_tier_benchmark_operator_preflight_current.csv"
DEFAULT_OPERATOR_IMPORT_JSON = "runs/casp17_win_tier_benchmark_operator_import_packet_current.json"
DEFAULT_CLOSURE_JSON = "runs/casp17_win_gap_closure_packet_current.json"
DEFAULT_OUT_JSON = "runs/casp17_win_tier_benchmark_operator_dashboard_current.json"
DEFAULT_OUT_CSV = "runs/casp17_win_tier_benchmark_operator_dashboard_current.csv"
DEFAULT_OUT_MD = "runs/casp17_win_tier_benchmark_operator_dashboard_current.md"
DEFAULT_OUT_HTML = "runs/casp17_win_tier_benchmark_operator_dashboard_current.html"

CORE_FILE_BLOCKERS = {"prediction_pdb_not_found", "prediction_pdb_missing", "native_pdb_not_found", "native_pdb_missing"}
PROVENANCE_BLOCKERS = {
    "placeholder_target_id",
    "leakage_clearance_required",
    "prediction_method_required",
    "prediction_created_at_required_iso_date",
    "native_release_date_required_iso_date",
    "prediction_date_not_before_native_release",
    "prediction_generated_before_native_release_required",
    "public_template_or_native_used_for_prediction_must_be_false",
    "other_team_model_used_must_be_false",
    "post_release_information_used_must_be_false",
    "current_casp17_target_must_be_false",
    "operator_clearance_required",
    "current_casp17_target_not_allowed",
}
CALIBRATION_PREFIXES = (
    "selected_model_rank",
    "best_model_rank",
    "selected_native_metric",
    "best_native_metric",
    "selected_score",
    "best_score",
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], [f"{path.name}_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    if not rows:
        return rows, [f"{path.name}_empty"]
    if not fieldnames:
        return rows, [f"{path.name}_header_missing"]
    return rows, []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["row_rank", "benchmark_id", "operator_row_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _bool_text(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _blockers(row: dict[str, str]) -> list[str]:
    return [item for item in str(row.get("blockers", "")).split(",") if item]


def _has_calibration_blocker(blockers: list[str]) -> bool:
    return any(blocker.startswith(CALIBRATION_PREFIXES) for blocker in blockers)


def _next_action(blockers: list[str]) -> str:
    blocker_set = set(blockers)
    if "placeholder_target_id" in blocker_set:
        return "Replace placeholder target/benchmark IDs with a cleared historical non-CASP17 protein target."
    if blocker_set & CORE_FILE_BLOCKERS:
        return "Add local internal prediction PDB and local historical native PDB paths for this benchmark row."
    if "ablation_layer_prediction_pdb_missing" in blocker_set:
        return "Populate all 10 refinement-layer prediction PDB paths for ablation evidence."
    if _has_calibration_blocker(blockers):
        return "Fill selected/best top-5 rank, native metric, and internal score calibration fields."
    if blocker_set & PROVENANCE_BLOCKERS:
        return "Complete no-leak provenance fields and operator clearance."
    if blockers:
        return "Resolve row blockers before import."
    return "Ready for fail-closed import after threshold counts are satisfied."


def _metric_profile(scope: str) -> str:
    if scope == "complex":
        return "TM,interface_F1,DockQ,QSbest,IPS"
    return "TM,GDT_TS,CA_lDDT"


def _classify_blockers(blockers: list[str]) -> dict[str, bool]:
    blocker_set = set(blockers)
    return {
        "needs_target_replacement": "placeholder_target_id" in blocker_set,
        "needs_core_files": bool(blocker_set & CORE_FILE_BLOCKERS),
        "needs_ablation_layers": "ablation_layer_prediction_pdb_missing" in blocker_set,
        "needs_calibration": _has_calibration_blocker(blockers),
        "needs_provenance": bool(blocker_set & PROVENANCE_BLOCKERS),
    }


def _merge_rows(template_rows: list[dict[str, str]], preflight_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_rank = {str(row.get("row_rank", "")).strip(): row for row in preflight_rows}
    by_benchmark = {str(row.get("benchmark_id", "")).strip(): row for row in preflight_rows}
    merged: list[dict[str, Any]] = []
    for index, template in enumerate(template_rows, start=1):
        benchmark_id = str(template.get("benchmark_id", "")).strip()
        preflight = by_rank.get(str(index)) or by_benchmark.get(benchmark_id) or {}
        blockers = _blockers(preflight)
        classes = _classify_blockers(blockers)
        scope = str(template.get("scope", preflight.get("scope", ""))).strip().lower()
        metric_profile = _metric_profile(scope)
        merged.append(
            {
                "row_rank": _int(preflight.get("row_rank") or index),
                "benchmark_id": benchmark_id,
                "target_id": str(template.get("target_id", preflight.get("target_id", ""))).strip().upper(),
                "scope": scope,
                "split": str(template.get("split", "")).strip() or "historical",
                "metric_profile": metric_profile,
                "required_metric_profile": metric_profile,
                "operator_row_status": str(preflight.get("operator_row_status", "blocked") or "blocked"),
                "core_ready": _bool_text(preflight.get("core_ready")),
                "ablation_ready": _bool_text(preflight.get("ablation_ready")),
                "calibration_ready": _bool_text(preflight.get("calibration_ready")),
                "prediction_pdb": str(template.get("prediction_pdb", "")).strip(),
                "native_pdb": str(template.get("native_pdb", "")).strip(),
                "prediction_pdb_exists": _bool_text(preflight.get("prediction_pdb_exists")),
                "native_pdb_exists": _bool_text(preflight.get("native_pdb_exists")),
                "ablation_layer_present_count": _int(preflight.get("ablation_layer_present_count")),
                "ablation_layer_required_count": _int(preflight.get("ablation_layer_required_count")),
                "missing_ablation_layers": str(preflight.get("missing_ablation_layers", "")).strip(),
                "calibration_blockers": str(preflight.get("calibration_blockers", "")).strip(),
                "needs_target_replacement": classes["needs_target_replacement"],
                "needs_core_files": classes["needs_core_files"],
                "needs_ablation_layers": classes["needs_ablation_layers"],
                "needs_calibration": classes["needs_calibration"],
                "needs_provenance": classes["needs_provenance"],
                "next_action": _next_action(blockers),
                "blockers": ",".join(blockers),
            }
        )
    return sorted(merged, key=lambda row: int(row["row_rank"] or 999999))


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Win Tier Benchmark Operator Dashboard",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- dashboard_status: `{summary['dashboard_status']}`",
        f"- closure: `{summary['closure_status']}` proven `{summary['current_proven_level']}` next `{summary['next_unclosed_level']}`",
        f"- operator_preflight: `{summary['operator_preflight_status']}` ready/blocked `{summary['ready_count']}/{summary['blocked_count']}`",
        f"- operator_import: `{summary['operator_import_status']}` candidate rows `{summary['historical_candidate_rows']}/{summary['calibration_candidate_rows']}`",
        f"- row counts monomer/complex: `{summary['monomer_row_count']}/{summary['complex_row_count']}`",
        f"- needs target/core/ablation/calibration/provenance: `{summary['needs_target_replacement_count']}/{summary['needs_core_file_count']}/{summary['needs_ablation_layer_count']}/{summary['needs_calibration_count']}/{summary['needs_provenance_count']}`",
        f"- html: `{summary['dashboard_html_path']}`",
        "",
        "## Rows",
        "",
        "| rank | benchmark | target | scope | metrics | status | core | ablation | calibration | next action | blockers |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['row_rank']} | `{row['benchmark_id']}` | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['required_metric_profile']}` | "
            f"`{row['operator_row_status']}` | `{row['core_ready']}` | `{row['ablation_ready']}` | "
            f"`{row['calibration_ready']}` | {row['next_action']} | `{row['blockers'] or '-'}` |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_html(path_like: str | Path, payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    rows = payload["rows"]
    cards: list[str] = []
    for row in rows:
        status_class = "ready" if row["operator_row_status"] == "ready" else "blocked"
        blockers = html.escape(row["blockers"] or "-")
        cards.append(
            "\n".join(
                [
                    f'<article class="card {status_class}">',
                    '  <div class="card-head">',
                    f'    <div><strong>{html.escape(str(row["benchmark_id"]))}</strong><span>{html.escape(str(row["target_id"]))} · {html.escape(str(row["scope"]))}</span></div>',
                    f'    <b>{html.escape(str(row["operator_row_status"]))}</b>',
                    "  </div>",
                    '  <div class="grid">',
                    f'    <div><label>core</label><strong>{row["core_ready"]}</strong></div>',
                    f'    <div><label>ablation</label><strong>{row["ablation_ready"]}</strong></div>',
                    f'    <div><label>calibration</label><strong>{row["calibration_ready"]}</strong></div>',
                    f'    <div><label>layers</label><strong>{row["ablation_layer_present_count"]}/{row["ablation_layer_required_count"]}</strong></div>',
                    "  </div>",
                    f'  <p class="path">metrics: {html.escape(str(row["required_metric_profile"]))}</p>',
                    f'  <p class="action">{html.escape(str(row["next_action"]))}</p>',
                    f'  <p class="path">prediction: {html.escape(str(row["prediction_pdb"]))}</p>',
                    f'  <p class="path">native: {html.escape(str(row["native_pdb"]))}</p>',
                    f'  <details><summary>blockers</summary><code>{blockers}</code></details>',
                    "</article>",
                ]
            )
        )
    html_text = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>CASP17 Win Tier Operator Dashboard</title>",
            "<style>",
            ":root{color-scheme:dark;--bg:#020617;--panel:#07111f;--line:#1e293b;--text:#f8fafc;--muted:#94a3b8;--ok:#86efac;--bad:#fca5a5;--accent:#38bdf8}",
            "*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}",
            "header{position:sticky;top:0;z-index:2;padding:18px 22px;background:rgba(2,6,23,.95);border-bottom:1px solid var(--line)}h1{font-size:22px;margin:0}.summary{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.pill{padding:6px 10px;border:1px solid var(--line);border-radius:999px;color:var(--muted);background:#0f172a}",
            "main{padding:18px;display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:14px}.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow:hidden}.card.ready{border-color:#14532d}.card.blocked{border-color:#4c1d1d}.card-head{display:flex;justify-content:space-between;gap:12px;align-items:start;padding:12px 14px;border-bottom:1px solid var(--line)}.card-head span{display:block;color:var(--muted);margin-top:3px}.card-head b{color:var(--bad)}.card.ready .card-head b{color:var(--ok)}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:12px}.grid div{background:#0b1220;border:1px solid var(--line);border-radius:6px;padding:8px;min-width:0}.grid label{display:block;color:var(--muted);font-size:12px}.grid strong{display:block;margin-top:4px}.action{padding:0 12px;color:#e0f2fe}.path{padding:0 12px;color:var(--muted);overflow-wrap:anywhere}details{padding:0 12px 12px}summary{cursor:pointer;color:var(--accent)}code{display:block;white-space:pre-wrap;overflow-wrap:anywhere;color:#fecaca;margin-top:8px}",
            "</style>",
            "</head>",
            "<body>",
            "<header>",
            "<h1>CASP17 Win Tier Benchmark Operator Dashboard</h1>",
            '<div class="summary">',
            f'<span class="pill">status: {html.escape(str(summary["dashboard_status"]))}</span>',
            f'<span class="pill">proven: {html.escape(str(summary["current_proven_level"]))}</span>',
            f'<span class="pill">next: {html.escape(str(summary["next_unclosed_level"]))}</span>',
            f'<span class="pill">ready/blocked: {summary["ready_count"]}/{summary["blocked_count"]}</span>',
            f'<span class="pill">import: {html.escape(str(summary["operator_import_status"]))}</span>',
            "</div>",
            "</header>",
            "<main>",
            *cards,
            "</main>",
            '<footer style="padding:20px 22px;color:#94a3b8;border-top:1px solid #1e293b">Local dashboard only. It does not fetch natives, clear provenance, score accuracy, use external predictors, or submit to CASP.</footer>',
            "</body>",
            "</html>",
        ]
    )
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text + "\n", encoding="utf-8")
    return _artifact(path)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    template_rows, template_blockers = _read_csv(args.operator_template_csv)
    preflight_rows, preflight_csv_blockers = _read_csv(args.operator_preflight_csv)
    preflight_summary = _summary(_read_json(args.operator_preflight_json))
    import_summary = _summary(_read_json(args.operator_import_json))
    closure_summary = _summary(_read_json(args.closure_json))
    rows = _merge_rows(template_rows, preflight_rows)

    ready_count = sum(1 for row in rows if row["operator_row_status"] == "ready")
    blocked_count = len(rows) - ready_count
    monomer_row_count = sum(1 for row in rows if row["scope"] == "monomer")
    complex_row_count = sum(1 for row in rows if row["scope"] == "complex")
    source_blockers = sorted(set(template_blockers + preflight_csv_blockers))
    summary = {
        "packet_type": "casp17_win_tier_benchmark_operator_dashboard",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "dashboard_status": "ready" if rows and not source_blockers else "blocked",
        "operator_template_csv": _artifact(args.operator_template_csv),
        "operator_preflight_json": _artifact(args.operator_preflight_json),
        "operator_preflight_csv": _artifact(args.operator_preflight_csv),
        "operator_import_json": _artifact(args.operator_import_json),
        "closure_json": _artifact(args.closure_json),
        "operator_preflight_status": str(preflight_summary.get("operator_preflight_status") or "missing"),
        "operator_import_status": str(import_summary.get("import_status") or "missing"),
        "closure_status": str(closure_summary.get("closure_status") or "missing"),
        "current_proven_level": str(closure_summary.get("current_proven_level") or "missing"),
        "next_unclosed_level": str(closure_summary.get("next_unclosed_level") or "missing"),
        "row_count": len(rows),
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "monomer_row_count": monomer_row_count,
        "complex_row_count": complex_row_count,
        "monomer_metric_profile": _metric_profile("monomer"),
        "complex_metric_profile": _metric_profile("complex"),
        "metric_profiles": f"monomer={_metric_profile('monomer')};complex={_metric_profile('complex')}",
        "needs_target_replacement_count": sum(1 for row in rows if row["needs_target_replacement"]),
        "needs_core_file_count": sum(1 for row in rows if row["needs_core_files"]),
        "needs_ablation_layer_count": sum(1 for row in rows if row["needs_ablation_layers"]),
        "needs_calibration_count": sum(1 for row in rows if row["needs_calibration"]),
        "needs_provenance_count": sum(1 for row in rows if row["needs_provenance"]),
        "historical_candidate_rows": int(import_summary.get("historical_manifest_candidate_row_count") or 0),
        "calibration_candidate_rows": int(import_summary.get("model_selection_calibration_candidate_row_count") or 0),
        "source_blockers": ",".join(source_blockers),
        "claim_boundary": (
            "Local operator dashboard only. It organizes fail-closed no-leak historical benchmark intake work; "
            "it does not fetch natives, clear provenance, score accuracy, use external predictors, or submit to CASP."
        ),
    }
    payload = {"summary": summary, "rows": rows}
    summary["dashboard_html_path"] = _write_html(args.out_html, payload)
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 win-tier benchmark operator dashboard.")
    parser.add_argument("--operator-template-csv", default=DEFAULT_OPERATOR_TEMPLATE_CSV)
    parser.add_argument("--operator-preflight-json", default=DEFAULT_OPERATOR_PREFLIGHT_JSON)
    parser.add_argument("--operator-preflight-csv", default=DEFAULT_OPERATOR_PREFLIGHT_CSV)
    parser.add_argument("--operator-import-json", default=DEFAULT_OPERATOR_IMPORT_JSON)
    parser.add_argument("--closure-json", default=DEFAULT_CLOSURE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-html", default=DEFAULT_OUT_HTML)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
