#!/usr/bin/env python3
"""Build the PocketMD Lite top-k refinement evidence work order.

Read-only: this tool does not run local-min, micro-MD, docking, or external
mutation. It inspects the current PocketMD Lite report and lists the exact
top-k rows whose refinement evidence must be supplied before the report can
move out of abstain/review.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REPORT_JSON = "runs/pocketmd_lite_report_current.json"
DEFAULT_CANDIDATE_CSV = "config/pocketmd_lite_candidates_current.csv"
DEFAULT_OUT_JSON = "runs/pocketmd_lite_refinement_work_order_current.json"
DEFAULT_OUT_MD = "runs/pocketmd_lite_refinement_work_order_current.md"
DEFAULT_OUT_CSV = "runs/pocketmd_lite_refinement_work_order_current.csv"

PACKET_TYPE = "pocketmd_lite_refinement_work_order"
SCHEMA_VERSION = "pocketmd_lite_refinement_work_order_v1"

REQUIRED_METRICS = (
    "local_min_ligand_rmsd_a",
    "hbond_persistence",
    "contact_persistence",
    "initial_clash_count",
    "clash_count",
)
REFRESH_REPORT_COMMAND = "python3 tools/product/build_pocketmd_lite_report.py"
WORK_ORDER_COMMAND = "python3 tools/product/build_pocketmd_lite_refinement_work_order.py"
NEXT_COMMAND = f"{REFRESH_REPORT_COMMAND} && {WORK_ORDER_COMMAND}"

CLAIM_BOUNDARY = (
    "PocketMD Lite refinement work order only; it records missing top-k refinement evidence, including "
    "baseline/final clash counts for clash-relief reporting, and next local commands. It does not run "
    "local-min, micro-MD, docking, generate scientific results, promote a binding-affinity claim, or mutate "
    "external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "refinement_execution_enabled": False,
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _is_present(value: Any) -> bool:
    return value is not None and _text(value) != ""


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_candidate_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _candidate_by_entry(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_text(row.get("entry_id")): row for row in rows if _text(row.get("entry_id"))}


def _metric_value(report_row: dict[str, Any], candidate_row: dict[str, Any], metric: str) -> Any:
    if _is_present(report_row.get(metric)):
        return report_row.get(metric)
    if metric == "initial_clash_count" and _is_present(report_row.get("pre_refine_clash_count")):
        return report_row.get("pre_refine_clash_count")
    if metric == "initial_clash_count" and _is_present(candidate_row.get("pre_refine_clash_count")):
        return candidate_row.get("pre_refine_clash_count")
    return candidate_row.get(metric)


def _ordered_rows(report_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if report_rows:
        return report_rows
    return [
        {
            "entry_id": _text(row.get("entry_id")),
            "family": _text(row.get("family")),
            "selected_for_refine": _bool(row.get("selected_for_refine")) if _text(row.get("selected_for_refine")) else True,
            "band": "",
            "reason_code": "missing_report_row",
        }
        for row in candidate_rows
    ]


def build_pocketmd_lite_refinement_work_order(
    *,
    report_json: str | Path = DEFAULT_REPORT_JSON,
    candidate_csv: str | Path = DEFAULT_CANDIDATE_CSV,
) -> dict[str, Any]:
    report_path = _resolve(report_json)
    candidate_path = _resolve(candidate_csv)
    report = _read_json(report_path)
    candidate_rows = _read_candidate_rows(candidate_path)
    candidate_lookup = _candidate_by_entry(candidate_rows)

    report_summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    report_rows = [row for row in report.get("rows", []) or [] if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []

    for source_row in _ordered_rows(report_rows, candidate_rows):
        entry_id = _text(source_row.get("entry_id"))
        candidate_row = candidate_lookup.get(entry_id, {})
        selected = _bool(source_row.get("selected_for_refine"))
        missing_metrics = [
            metric
            for metric in REQUIRED_METRICS
            if selected and not _is_present(_metric_value(source_row, candidate_row, metric))
        ]
        band = _text(source_row.get("band"))
        if not selected:
            action_type = "coarse_only"
            evidence_status = "coarse_only"
            required_input = ""
        elif missing_metrics:
            action_type = "fill_refinement_evidence"
            evidence_status = "missing_refinement_evidence"
            required_input = "Fill " + ";".join(missing_metrics)
        elif band and band != "green":
            action_type = "review_uncertainty_band"
            evidence_status = "review_required"
            required_input = f"Review non-green PocketMD Lite band: {band}"
        else:
            action_type = "no_action_required"
            evidence_status = "complete"
            required_input = ""

        row = {
            "entry_id": entry_id,
            "family": _text(source_row.get("family") or candidate_row.get("family")),
            "selected_for_refine": selected,
            "band": band,
            "reason_code": _text(source_row.get("reason_code")),
            "evidence_status": evidence_status,
            "action_type": action_type,
            "required_metrics": ";".join(REQUIRED_METRICS),
            "missing_metrics": ";".join(missing_metrics),
            "required_input": required_input,
            "recommended_command_after_fill": NEXT_COMMAND if action_type != "coarse_only" else "",
            "report_json": str(report_path),
            "candidate_csv": str(candidate_path),
            **{metric: _metric_value(source_row, candidate_row, metric) for metric in REQUIRED_METRICS},
            **_READ_ONLY_FLAGS,
        }
        rows.append(row)

    selected_rows = [row for row in rows if row["selected_for_refine"]]
    missing_rows = [row for row in selected_rows if row["missing_metrics"]]
    review_rows = [row for row in selected_rows if not row["missing_metrics"] and row["band"] and row["band"] != "green"]
    missing_metric_count = sum(len(row["missing_metrics"].split(";")) for row in missing_rows if row["missing_metrics"])
    missing_metric_names = sorted(
        {
            metric
            for row in missing_rows
            for metric in row["missing_metrics"].split(";")
            if metric
        }
    )

    materializer_status = "materialized"
    if not report_path.exists():
        status = "blocked_missing_pocketmd_lite_report"
        materializer_status = "blocked_missing_report_json"
    elif not report_rows:
        status = "blocked_empty_pocketmd_lite_report"
        materializer_status = "blocked_empty_report_rows"
    elif not selected_rows:
        status = "blocked_no_pocketmd_lite_top_k_candidates"
    elif missing_rows:
        status = "blocked_pocketmd_lite_refinement_evidence_missing"
    elif review_rows:
        status = "blocked_pocketmd_lite_refinement_review_required"
    else:
        status = "pocketmd_lite_refinement_work_order_ready"
    if status == "pocketmd_lite_refinement_work_order_ready":
        next_required_step = "PocketMD Lite top-k refinement evidence is complete; review the report uncertainty bands."
    elif missing_metric_names:
        next_required_step = (
            f"Supply PocketMD Lite top-k missing evidence: {', '.join(missing_metric_names)}; "
            "then rerun the report and this work order."
        )
    else:
        next_required_step = "Restore PocketMD Lite report rows/candidates, then rerun the report and this work order."

    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "materializer_status": materializer_status,
        "report_status": _text(report_summary.get("status")),
        "report_claim_safe": bool(report_summary.get("pocketmd_lite_claim_safe") is True),
        "candidate_count": len(rows),
        "selected_top_k_count": len(selected_rows),
        "missing_evidence_candidate_count": len(missing_rows),
        "review_required_candidate_count": len(review_rows),
        "required_metric_count": len(REQUIRED_METRICS),
        "missing_required_metric_count": missing_metric_count,
        "missing_metric_names": missing_metric_names,
        "top_k_only_policy_enforced": bool(report_summary.get("top_k_only_policy_enforced") is True),
        "required_metrics": list(REQUIRED_METRICS),
        "report_json": str(report_path),
        "candidate_csv": str(candidate_path),
        "refresh_report_command": REFRESH_REPORT_COMMAND,
        "work_order_command": WORK_ORDER_COMMAND,
        "next_required_step": next_required_step,
        "claim_boundary": CLAIM_BOUNDARY,
        **_READ_ONLY_FLAGS,
    }

    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "rows": rows,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


_CSV_COLUMNS = [
    "entry_id",
    "family",
    "selected_for_refine",
    "band",
    "reason_code",
    "evidence_status",
    "action_type",
    "required_metrics",
    "missing_metrics",
    "required_input",
    "recommended_command_after_fill",
    *REQUIRED_METRICS,
    "execution_enabled",
    "external_state_mutated",
    "refinement_execution_enabled",
]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _fmt(row.get(column)) for column in _CSV_COLUMNS})


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# PocketMD Lite Refinement Work Order (current)",
        "",
        "Read-only work order for top-k PocketMD Lite evidence collection.",
        "",
        f"- status: `{summary['status']}`",
        f"- report_status: `{summary['report_status']}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- selected_top_k_count: `{summary['selected_top_k_count']}`",
        f"- missing_evidence_candidate_count: `{summary['missing_evidence_candidate_count']}`",
        f"- missing_required_metric_count: `{summary['missing_required_metric_count']}`",
        f"- refresh_report_command: `{summary['refresh_report_command']}`",
        f"- work_order_command: `{summary['work_order_command']}`",
        "",
        "## Rows",
        "",
        "| entry | band | action | missing metrics | command |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{entry}` | `{band}` | `{action}` | `{missing}` | `{command}` |".format(
                entry=row["entry_id"],
                band=row["band"] or "(none)",
                action=row["action_type"],
                missing=row["missing_metrics"] or "(none)",
                command=row["recommended_command_after_fill"] or "(none)",
            )
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a PocketMD Lite refinement evidence work order.")
    parser.add_argument("--report-json", default=DEFAULT_REPORT_JSON)
    parser.add_argument("--candidate-csv", default=DEFAULT_CANDIDATE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    payload = build_pocketmd_lite_refinement_work_order(
        report_json=args.report_json,
        candidate_csv=args.candidate_csv,
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_csv = _resolve(args.out_csv)
    for path in (out_json, out_md, out_csv):
        path.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
