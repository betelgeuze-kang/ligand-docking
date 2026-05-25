#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OPERATOR_TEMPLATE_CSV = "runs/casp17_win_tier_benchmark_operator_template_current.csv"
DEFAULT_OPERATOR_DASHBOARD_JSON = "runs/casp17_win_tier_benchmark_operator_dashboard_current.json"
DEFAULT_HISTORICAL_BENCHMARK_JSON = "runs/casp17_historical_benchmark_packet_current.json"
DEFAULT_OUT_JSON = "runs/casp17_win_tier_benchmark_evidence_fill_kit_current.json"
DEFAULT_OUT_CSV = "runs/casp17_win_tier_benchmark_evidence_fill_kit_current.csv"
DEFAULT_OUT_MD = "runs/casp17_win_tier_benchmark_evidence_fill_kit_current.md"
DEFAULT_OUT_HTML = "runs/casp17_win_tier_benchmark_evidence_fill_kit_current.html"

ABLATION_LAYER_NAMES = [
    "recursive",
    "scored",
    "sidechain_scaffold",
    "sidechain_repacked",
    "sidechain_completed",
    "steric_relaxed",
    "rotamer_minimized",
    "polar_refined",
    "forcefield_minimized",
    "statistical_rotamer",
]
ABLATION_COLUMNS = [f"{layer}_prediction_pdb" for layer in ABLATION_LAYER_NAMES]
PROVENANCE_EXPECTATIONS = {
    "leakage_clearance": "no_leak",
    "prediction_method": "internal method identifier",
    "prediction_created_at": "YYYY-MM-DD before native release",
    "native_release_date": "YYYY-MM-DD after prediction",
    "prediction_generated_before_native_release": "true",
    "public_template_or_native_used_for_prediction": "false",
    "other_team_model_used": "false",
    "post_release_information_used": "false",
    "current_casp17_target": "false",
    "operator_clearance": "no_leak",
}
CALIBRATION_EXPECTATIONS = {
    "selected_model_rank": "integer 1..5",
    "best_model_rank": "integer 1..5",
    "selected_native_metric": "numeric native metric for selected model",
    "best_native_metric": "numeric native metric for oracle/best model",
    "selected_score": "numeric internal score for selected model",
    "best_score": "numeric internal score for best model",
}
TRUE_VALUES = {"1", "true", "yes", "y"}
FALSE_VALUES = {"0", "false", "no", "n"}
CLEAR_VALUES = {"no_leak", "cleared", "true", "yes", "internal_no_leak"}

MONOMER_METRIC_REQUIREMENTS = [
    ("monomer_tm_score_proxy", "tm_score_proxy", "monomer_tm"),
    ("monomer_gdt_ts_proxy", "gdt_ts_proxy", "monomer_gdt_ts"),
    ("monomer_ca_lddt_proxy", "ca_lddt_proxy", "monomer_lddt"),
]
COMPLEX_METRIC_REQUIREMENTS = [
    ("complex_tm_score_proxy", "tm_score_proxy", "complex_tm"),
    ("complex_interface_f1_proxy", "interface_contact_f1_proxy", "complex_interface_f1"),
    ("complex_dockq_proxy", "dockq_proxy", "complex_dockq"),
    ("complex_qsbest_proxy", "interface_qsbest_proxy", ""),
    ("complex_ips_proxy", "interface_patch_jaccard_proxy", ""),
]


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


def _json_rows_by_benchmark(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict):
            benchmark_id = _text(row.get("benchmark_id"))
            if benchmark_id:
                result[benchmark_id] = row
    return result


def _read_csv(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], ["operator_template_csv_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return rows, [] if rows else ["operator_template_csv_empty"]


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
        fieldnames = ["row_rank", "benchmark_id", "evidence_class", "evidence_item"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _is_placeholder(value: Any) -> bool:
    text = _text(value)
    return not text or text.upper().startswith("REQUIRED_") or "YYYY-MM-DD" in text.upper()


def _date_ok(value: Any) -> bool:
    text = _text(value)
    if not text or _is_placeholder(text):
        return False
    try:
        dt.date.fromisoformat(text[:10])
    except ValueError:
        return False
    return True


def _numeric_ok(value: Any) -> bool:
    try:
        float(str(value).strip())
    except (TypeError, ValueError):
        return False
    return True


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _rank_ok(value: Any) -> bool:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return False
    return 1 <= parsed <= 5


def _field_status(column: str, value: Any) -> tuple[str, str]:
    lower = _text(value).lower()
    if column in {"leakage_clearance", "operator_clearance"}:
        return ("filled", "") if lower in CLEAR_VALUES else ("missing", f"{column}_requires_no_leak_clearance")
    if column == "prediction_method":
        return ("filled", "") if not _is_placeholder(value) else ("missing", "prediction_method_required")
    if column in {"prediction_created_at", "native_release_date"}:
        return ("filled", "") if _date_ok(value) else ("missing", f"{column}_requires_iso_date")
    if column == "prediction_generated_before_native_release":
        return ("filled", "") if lower in TRUE_VALUES else ("missing", "prediction_before_native_release_confirmation_required")
    if column in {
        "public_template_or_native_used_for_prediction",
        "other_team_model_used",
        "post_release_information_used",
        "current_casp17_target",
    }:
        return ("filled", "") if lower in FALSE_VALUES else ("missing", f"{column}_must_be_false")
    if column in {"selected_model_rank", "best_model_rank"}:
        return ("filled", "") if _rank_ok(value) else ("missing", f"{column}_requires_rank_1_to_5")
    if column in {"selected_native_metric", "best_native_metric", "selected_score", "best_score"}:
        return ("filled", "") if _numeric_ok(value) else ("missing", f"{column}_requires_numeric_value")
    return ("filled", "") if not _is_placeholder(value) else ("missing", f"{column}_required")


def _file_status(path_text: str, *, missing_reason: str) -> tuple[str, str]:
    if not path_text or _is_placeholder(path_text):
        return "missing", missing_reason
    return ("filled", "") if _resolve(path_text).exists() else ("missing", f"{missing_reason}_not_found")


def _make_row(
    *,
    template_row: dict[str, str],
    row_rank: int,
    evidence_class: str,
    evidence_item: str,
    template_column: str,
    expected_value: str,
    current_value: str,
    status: str,
    blocker: str,
) -> dict[str, Any]:
    return {
        "row_rank": row_rank,
        "benchmark_id": _text(template_row.get("benchmark_id")),
        "target_id": _text(template_row.get("target_id")).upper(),
        "scope": _text(template_row.get("scope")).lower(),
        "split": _text(template_row.get("split")) or "historical",
        "evidence_class": evidence_class,
        "evidence_item": evidence_item,
        "template_column": template_column,
        "expected_value": expected_value,
        "current_value": current_value,
        "completion_status": status,
        "blocker": blocker,
    }


def _metric_requirements(scope: str) -> list[tuple[str, str, str]]:
    return COMPLEX_METRIC_REQUIREMENTS if scope == "complex" else MONOMER_METRIC_REQUIREMENTS


def _metric_status(
    benchmark_row: dict[str, Any] | None,
    metric_key: str,
    threshold_key: str,
    thresholds: dict[str, Any],
) -> tuple[str, str, str, str]:
    threshold_values = thresholds.get(threshold_key) if threshold_key else None
    threshold = None
    if isinstance(threshold_values, dict):
        threshold = _float_or_none(threshold_values.get("win"))
    expected = f">= {threshold} ({threshold_key})" if threshold is not None else "scored numeric proxy"
    if not benchmark_row:
        return "missing", expected, "", "historical_benchmark_row_not_scored"
    if _text(benchmark_row.get("benchmark_status")) != "pass":
        return "missing", expected, _text(benchmark_row.get(metric_key)), "historical_benchmark_row_not_pass"
    value = _float_or_none(benchmark_row.get(metric_key))
    if value is None:
        return "missing", expected, _text(benchmark_row.get(metric_key)), f"{metric_key}_missing"
    if threshold is not None and value < threshold:
        return "missing", expected, str(value), f"{metric_key}_below_win_threshold"
    return "filled", expected, str(value), ""


def _rows_for_template_row(
    template_row: dict[str, str],
    row_rank: int,
    *,
    historical_rows_by_benchmark: dict[str, dict[str, Any]],
    historical_thresholds: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    target_id = _text(template_row.get("target_id"))
    target_status = "missing" if target_id.upper().startswith("REQUIRED_") or not target_id else "filled"
    rows.append(
        _make_row(
            template_row=template_row,
            row_rank=row_rank,
            evidence_class="target_identity",
            evidence_item="historical_non_current_target_id",
            template_column="target_id",
            expected_value="cleared historical non-CASP17 protein target ID",
            current_value=target_id,
            status=target_status,
            blocker="" if target_status == "filled" else "placeholder_target_id",
        )
    )
    for column, item, expected in [
        ("prediction_pdb", "internal_prediction_pdb", "local PDB generated by internal method before native release"),
        ("native_pdb", "historical_native_pdb", "local historical native PDB not from current CASP17 target"),
    ]:
        current = _text(template_row.get(column))
        status, blocker = _file_status(current, missing_reason=f"{column}_required")
        rows.append(
            _make_row(
                template_row=template_row,
                row_rank=row_rank,
                evidence_class="core_file",
                evidence_item=item,
                template_column=column,
                expected_value=expected,
                current_value=current,
                status=status,
                blocker=blocker,
            )
        )
    for layer, column in zip(ABLATION_LAYER_NAMES, ABLATION_COLUMNS):
        current = _text(template_row.get(column))
        status, blocker = _file_status(current, missing_reason=f"{layer}_prediction_pdb_required")
        rows.append(
            _make_row(
                template_row=template_row,
                row_rank=row_rank,
                evidence_class="ablation_layer_file",
                evidence_item=layer,
                template_column=column,
                expected_value=f"local {layer} layer prediction PDB for ablation scoring",
                current_value=current,
                status=status,
                blocker=blocker,
            )
        )
    for column, expected in PROVENANCE_EXPECTATIONS.items():
        current = _text(template_row.get(column))
        status, blocker = _field_status(column, current)
        rows.append(
            _make_row(
                template_row=template_row,
                row_rank=row_rank,
                evidence_class="provenance_field",
                evidence_item=column,
                template_column=column,
                expected_value=expected,
                current_value=current,
                status=status,
                blocker=blocker,
            )
        )
    for column, expected in CALIBRATION_EXPECTATIONS.items():
        current = _text(template_row.get(column))
        status, blocker = _field_status(column, current)
        rows.append(
            _make_row(
                template_row=template_row,
                row_rank=row_rank,
                evidence_class="calibration_field",
                evidence_item=column,
                template_column=column,
                expected_value=expected,
                current_value=current,
                status=status,
                blocker=blocker,
            )
        )
    benchmark_id = _text(template_row.get("benchmark_id"))
    benchmark_row = historical_rows_by_benchmark.get(benchmark_id)
    scope = _text(template_row.get("scope")).lower()
    for evidence_item, metric_key, threshold_key in _metric_requirements(scope):
        status, expected, current, blocker = _metric_status(
            benchmark_row,
            metric_key,
            threshold_key,
            historical_thresholds,
        )
        rows.append(
            _make_row(
                template_row=template_row,
                row_rank=row_rank,
                evidence_class="native_metric_gate",
                evidence_item=evidence_item,
                template_column=metric_key,
                expected_value=expected,
                current_value=current,
                status=status,
                blocker=blocker,
            )
        )
    return rows


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    class_counts = summary["missing_by_class"]
    lines = [
        "# CASP17 Win Tier Benchmark Evidence Fill Kit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- fill_kit_status: `{summary['fill_kit_status']}`",
        f"- dashboard_status: `{summary['dashboard_status']}`",
        f"- benchmark rows: `{summary['benchmark_row_count']}`",
        f"- evidence items: `{summary['evidence_item_count']}`",
        f"- missing evidence items: `{summary['missing_evidence_item_count']}`",
        f"- missing by class: target/core/ablation/provenance/calibration/metrics `{class_counts['target_identity']}/{class_counts['core_file']}/{class_counts['ablation_layer_file']}/{class_counts['provenance_field']}/{class_counts['calibration_field']}/{class_counts['native_metric_gate']}`",
        f"- html: `{summary['fill_kit_html_path']}`",
        "",
        "## Required Evidence Totals",
        "",
        f"- target identity rows: `{summary['required_target_identity_count']}`",
        f"- core prediction/native files: `{summary['required_core_file_count']}`",
        f"- ablation layer files: `{summary['required_ablation_layer_file_count']}`",
        f"- provenance fields: `{summary['required_provenance_field_count']}`",
        f"- calibration fields: `{summary['required_calibration_field_count']}`",
        f"- native metric gates: `{summary['required_native_metric_gate_count']}`",
        "",
        "## First Missing Items",
        "",
        "| rank | benchmark | target | class | item | expected | current | blocker |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in [item for item in payload["rows"] if item["completion_status"] != "filled"][:40]:
        lines.append(
            f"| {row['row_rank']} | `{row['benchmark_id']}` | `{row['target_id']}` | `{row['evidence_class']}` | "
            f"`{row['evidence_item']}` | {row['expected_value']} | `{row['current_value'] or '-'}` | `{row['blocker']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_html(path_like: str | Path, payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    rows = payload["rows"]
    cards: list[str] = []
    for row in rows[:240]:
        status_class = "filled" if row["completion_status"] == "filled" else "missing"
        cards.append(
            "\n".join(
                [
                    f'<article class="item {status_class}">',
                    f'  <strong>{html.escape(str(row["benchmark_id"]))}</strong>',
                    f'  <span>{html.escape(str(row["target_id"]))} · {html.escape(str(row["evidence_class"]))}</span>',
                    f'  <h2>{html.escape(str(row["evidence_item"]))}</h2>',
                    f'  <p>{html.escape(str(row["expected_value"]))}</p>',
                    f'  <code>{html.escape(str(row["current_value"]) or "-")}</code>',
                    f'  <em>{html.escape(str(row["blocker"]) or "filled")}</em>',
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
            "<title>CASP17 Benchmark Evidence Fill Kit</title>",
            "<style>",
            ":root{color-scheme:dark;--bg:#020617;--panel:#07111f;--line:#1e293b;--text:#f8fafc;--muted:#94a3b8;--ok:#86efac;--bad:#fca5a5;--accent:#38bdf8}",
            "*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}header{padding:18px 22px;background:#020617;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:2}h1{margin:0;font-size:22px}.summary{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.pill{padding:6px 10px;border:1px solid var(--line);border-radius:999px;color:var(--muted);background:#0f172a}main{padding:18px;display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}.item{border:1px solid var(--line);border-radius:8px;background:var(--panel);padding:12px}.item.missing{border-color:#4c1d1d}.item.filled{border-color:#14532d}.item span{display:block;color:var(--muted);margin-top:3px}.item h2{font-size:16px;margin:10px 0 6px}.item p{color:#dbeafe;margin:0 0 8px}.item code{display:block;color:var(--muted);overflow-wrap:anywhere;background:#0b1220;border:1px solid var(--line);padding:8px;border-radius:6px}.item em{display:block;color:var(--bad);font-style:normal;margin-top:8px;overflow-wrap:anywhere}.item.filled em{color:var(--ok)}",
            "</style>",
            "</head>",
            "<body>",
            "<header>",
            "<h1>CASP17 Benchmark Evidence Fill Kit</h1>",
            '<div class="summary">',
            f'<span class="pill">status: {html.escape(str(summary["fill_kit_status"]))}</span>',
            f'<span class="pill">benchmark rows: {summary["benchmark_row_count"]}</span>',
            f'<span class="pill">missing evidence: {summary["missing_evidence_item_count"]}/{summary["evidence_item_count"]}</span>',
            f'<span class="pill">showing first {min(240, len(rows))} items</span>',
            "</div>",
            "</header>",
            "<main>",
            *cards,
            "</main>",
            '<footer style="padding:20px 22px;color:#94a3b8;border-top:1px solid #1e293b">Local fill kit only. It does not fetch natives, clear provenance, score accuracy, use external predictors, or submit to CASP.</footer>',
            "</body>",
            "</html>",
        ]
    )
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text + "\n", encoding="utf-8")
    return _artifact(path)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    template_rows, source_blockers = _read_csv(args.operator_template_csv)
    dashboard = _summary(_read_json(args.operator_dashboard_json))
    historical_payload = _read_json(args.historical_benchmark_json)
    historical_summary = _summary(historical_payload)
    historical_rows_by_benchmark = _json_rows_by_benchmark(historical_payload)
    historical_thresholds = historical_summary.get("thresholds")
    if not isinstance(historical_thresholds, dict):
        historical_thresholds = {}
    rows: list[dict[str, Any]] = []
    for row_rank, template_row in enumerate(template_rows, start=1):
        rows.extend(
            _rows_for_template_row(
                template_row,
                row_rank,
                historical_rows_by_benchmark=historical_rows_by_benchmark,
                historical_thresholds=historical_thresholds,
            )
        )

    missing_rows = [row for row in rows if row["completion_status"] != "filled"]
    classes = [
        "target_identity",
        "core_file",
        "ablation_layer_file",
        "provenance_field",
        "calibration_field",
        "native_metric_gate",
    ]
    missing_by_class = {
        klass: sum(1 for row in missing_rows if row["evidence_class"] == klass)
        for klass in classes
    }
    required_by_class = {
        klass: sum(1 for row in rows if row["evidence_class"] == klass)
        for klass in classes
    }
    summary = {
        "packet_type": "casp17_win_tier_benchmark_evidence_fill_kit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "fill_kit_status": "ready" if rows and not source_blockers else "blocked",
        "operator_template_csv": _artifact(args.operator_template_csv),
        "operator_dashboard_json": _artifact(args.operator_dashboard_json),
        "historical_benchmark_json": _artifact(args.historical_benchmark_json),
        "historical_benchmark_status": str(historical_summary.get("historical_benchmark_status") or "missing"),
        "dashboard_status": str(dashboard.get("dashboard_status") or "missing"),
        "dashboard_ready_count": int(dashboard.get("ready_count") or 0),
        "dashboard_blocked_count": int(dashboard.get("blocked_count") or 0),
        "benchmark_row_count": len(template_rows),
        "evidence_item_count": len(rows),
        "filled_evidence_item_count": len(rows) - len(missing_rows),
        "missing_evidence_item_count": len(missing_rows),
        "required_target_identity_count": required_by_class["target_identity"],
        "required_core_file_count": required_by_class["core_file"],
        "required_ablation_layer_file_count": required_by_class["ablation_layer_file"],
        "required_provenance_field_count": required_by_class["provenance_field"],
        "required_calibration_field_count": required_by_class["calibration_field"],
        "required_native_metric_gate_count": required_by_class["native_metric_gate"],
        "missing_by_class": missing_by_class,
        "source_blockers": ",".join(source_blockers),
        "claim_boundary": (
            "Local evidence fill kit only. It enumerates no-leak historical benchmark evidence to provide; "
            "it does not fetch natives, clear provenance, score accuracy, use external predictors, or submit to CASP."
        ),
    }
    payload = {"summary": summary, "rows": rows}
    summary["fill_kit_html_path"] = _write_html(args.out_html, payload)
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 win-tier benchmark evidence fill kit.")
    parser.add_argument("--operator-template-csv", default=DEFAULT_OPERATOR_TEMPLATE_CSV)
    parser.add_argument("--operator-dashboard-json", default=DEFAULT_OPERATOR_DASHBOARD_JSON)
    parser.add_argument("--historical-benchmark-json", default=DEFAULT_HISTORICAL_BENCHMARK_JSON)
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
