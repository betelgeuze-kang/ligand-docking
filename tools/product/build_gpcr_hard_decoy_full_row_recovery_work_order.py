#!/usr/bin/env python3
"""Build the GPCR hard-decoy full-row recovery work order.

Read-only: this tool does not run scoring, regenerate rankings, relax
thresholds, or mutate external state. It records the exact missing full ranking
rows required to close the current GPCR hard-decoy gate from complete evidence
instead of retained-top-k evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PROVENANCE_JSON = "runs/gpcr_hard_decoy_suite_current_input_provenance.json"
DEFAULT_SUITE_JSON = "runs/gpcr_hard_decoy_suite_current.json"
DEFAULT_RANKING_SUMMARY_JSON = (
    "runs/gpcr_coverage_v2_crossfit_rank_rescue_repeat_r1_shadow_replay_ranking_summary_current.json"
)
DEFAULT_OUT_JSON = "runs/gpcr_hard_decoy_full_row_recovery_work_order_current.json"
DEFAULT_OUT_MD = "runs/gpcr_hard_decoy_full_row_recovery_work_order_current.md"
DEFAULT_OUT_CSV = "runs/gpcr_hard_decoy_full_row_recovery_work_order_current.csv"

PACKET_TYPE = "gpcr_hard_decoy_full_row_recovery_work_order"
SCHEMA_VERSION = "gpcr_hard_decoy_full_row_recovery_work_order_v1"

REFRESH_COMMAND = (
    "python3 tools/product/build_gpcr_hard_decoy_suite_current_input.py && "
    "python3 tools/product/build_gpcr_hard_decoy_suite_report.py && "
    "python3 tools/product/build_gpcr_hard_decoy_full_row_recovery_work_order.py"
)

CLAIM_BOUNDARY = (
    "GPCR hard-decoy full-row recovery work order only; it records missing full ranking-row "
    "inputs and current blocker evidence. It does not run scoring, regenerate decoys, relax "
    "thresholds, promote a broad-GPCR claim, fetch external data, or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "scoring_execution_enabled": False,
    "threshold_relaxation_enabled": False,
    "external_fetch_enabled": False,
}

_CSV_COLUMNS = [
    "row_type",
    "row_id",
    "status",
    "path",
    "exists",
    "target_id",
    "blockers",
    "root_cause_tags",
    "ranking_pr_auc_ci_low",
    "top20_hit_rate",
    "decoys_above_positive_count",
    "positive_target_rank",
    "positive_anchor_distance_a",
    "top_decoy_anchor_distance_a",
    "anchor_margin_a",
    "retained_target_row_count",
    "retained_positive_count",
    "top_decoy_retained_count",
    "recommended_next_local_action",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _path_row(artifact_key: str, raw_path: Any) -> dict[str, Any]:
    text = _text(raw_path)
    path = _resolve(text) if text else Path("")
    exists = bool(text and path.exists())
    return {
        "artifact_key": artifact_key,
        "path": "" if not text else str(path),
        "exists": exists,
        "status": "available" if exists else "missing",
        "required_for": "complete_target_internal_anchor_separation",
    }


def _expected_full_rows(ranking_summary: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = ranking_summary.get("artifacts") if isinstance(ranking_summary.get("artifacts"), dict) else {}
    rows = []
    for key in ("detail_csv", "unique_csv"):
        row = _path_row(key, artifacts.get(key))
        if row["path"]:
            rows.append(row)
    return rows


def _ranking_input_rows(ranking_summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key in ("expected_keys_csv", "split_csv"):
        row = _path_row(key, ranking_summary.get(key))
        if row["path"]:
            row["required_for"] = "full_ranking_row_regeneration"
            rows.append(row)
    return rows


def _target_blocker_rows(suite: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for target in suite.get("targets", []) or []:
        if not isinstance(target, dict):
            continue
        if target.get("claim_safe") is True and not target.get("blockers"):
            continue
        rows.append(
            {
                "target_id": _text(target.get("target_id")),
                "gate_status": _text(target.get("gate_status")),
                "claim_safe": bool(target.get("claim_safe") is True),
                "blockers": list(target.get("blockers") or []),
                "root_cause_tags": list(target.get("root_cause_tags") or []),
                "ranking_pr_auc_ci_low": target.get("ranking_pr_auc_ci_low"),
                "top20_hit_rate": target.get("top20_hit_rate"),
                "decoys_above_positive_count": target.get("decoys_above_positive_count"),
                "positive_target_rank": target.get("positive_target_rank"),
                "positive_anchor_distance_a": target.get("positive_anchor_distance_a"),
                "top_decoy_anchor_distance_a": target.get("top_decoy_anchor_distance_a"),
                "anchor_margin_a": target.get("anchor_margin_a"),
                "retained_target_row_count": target.get("retained_target_row_count"),
                "retained_positive_count": target.get("retained_positive_count"),
                "top_decoy_retained_count": target.get("top_decoy_retained_count"),
            }
        )
    return rows


def build_gpcr_hard_decoy_full_row_recovery_work_order(
    *,
    provenance_json: str | Path = DEFAULT_PROVENANCE_JSON,
    suite_json: str | Path = DEFAULT_SUITE_JSON,
    ranking_summary_json: str | Path = DEFAULT_RANKING_SUMMARY_JSON,
) -> dict[str, Any]:
    provenance_path = _resolve(provenance_json)
    suite_path = _resolve(suite_json)
    provenance = _read_json(provenance_path)
    suite = _read_json(suite_path)

    ranking_summary_source = _text(provenance.get("ranking_summary_json")) or str(_resolve(ranking_summary_json))
    ranking_summary_path = _resolve(ranking_summary_source)
    ranking_summary = _read_json(ranking_summary_path)

    expected_full_rows = _expected_full_rows(ranking_summary)
    missing_full_rows = [row for row in expected_full_rows if not row["exists"]]
    ranking_inputs = _ranking_input_rows(ranking_summary)
    missing_ranking_inputs = [row for row in ranking_inputs if not row["exists"]]
    retained_evidence = _path_row("retained_evidence_csv", provenance.get("ranking_rows_csv"))
    target_blockers = _target_blocker_rows(suite)

    if not provenance_path.exists():
        status = "blocked_missing_gpcr_hard_decoy_input_provenance"
        materializer_status = "blocked_missing_provenance_json"
    elif not suite_path.exists():
        status = "blocked_missing_gpcr_hard_decoy_suite_report"
        materializer_status = "blocked_missing_suite_json"
    elif not ranking_summary_path.exists():
        status = "blocked_missing_gpcr_ranking_summary"
        materializer_status = "blocked_missing_ranking_summary_json"
    elif missing_full_rows:
        status = "blocked_gpcr_hard_decoy_full_row_recovery_required"
        materializer_status = "materialized"
    elif target_blockers:
        status = "blocked_gpcr_hard_decoy_evidence_replay_required"
        materializer_status = "materialized"
    else:
        status = "gpcr_hard_decoy_full_row_recovery_work_order_ready"
        materializer_status = "materialized"

    next_action = (
        "Restore or regenerate the exact full GPCR ranking rows, then rerun "
        "build_gpcr_hard_decoy_suite_current_input.py and build_gpcr_hard_decoy_suite_report.py."
    )
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "materializer_status": materializer_status,
        "provenance_json": str(provenance_path),
        "suite_json": str(suite_path),
        "ranking_summary_json": str(ranking_summary_path),
        "expected_full_row_artifact_count": len(expected_full_rows),
        "missing_full_row_artifact_count": len(missing_full_rows),
        "ranking_input_artifact_count": len(ranking_inputs),
        "missing_ranking_input_artifact_count": len(missing_ranking_inputs),
        "retained_evidence_available": bool(retained_evidence["exists"]),
        "retained_evidence_path": retained_evidence["path"],
        "rank_evidence_mode": _text(provenance.get("rank_evidence_mode")),
        "ranking_rows_complete": bool(provenance.get("ranking_rows_complete") is True),
        "blocked_target_count": len(target_blockers),
        "blocked_target_ids": [row["target_id"] for row in target_blockers],
        "current_suite_status": _text((suite.get("summary") or {}).get("status")),
        "current_family_claim_safe": bool((suite.get("summary") or {}).get("family_claim_safe") is True),
        "recommended_next_local_action": next_action,
        "recommended_command_after_restore": REFRESH_COMMAND,
        "claim_boundary": CLAIM_BOUNDARY,
        **_READ_ONLY_FLAGS,
    }

    return {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "expected_full_rows": expected_full_rows,
        "missing_full_rows": missing_full_rows,
        "ranking_inputs": ranking_inputs,
        "missing_ranking_inputs": missing_ranking_inputs,
        "retained_evidence": retained_evidence,
        "target_blockers": target_blockers,
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR Hard-Decoy Full-Row Recovery Work Order",
        "",
        "Read-only recovery queue for the current GPCR hard-decoy gate. It records",
        "the full ranking rows needed to re-evaluate target-internal anchor",
        "separation from complete evidence.",
        "",
        f"- status: `{summary['status']}`",
        f"- missing_full_row_artifact_count: `{summary['missing_full_row_artifact_count']}`",
        f"- missing_ranking_input_artifact_count: `{summary['missing_ranking_input_artifact_count']}`",
        f"- retained_evidence_available: `{str(summary['retained_evidence_available']).lower()}`",
        f"- rank_evidence_mode: `{summary['rank_evidence_mode'] or '(none)'}`",
        f"- blocked_target_ids: `{', '.join(summary['blocked_target_ids']) or '(none)'}`",
        f"- execution_enabled: `{str(summary['execution_enabled']).lower()}`",
        f"- external_state_mutated: `{str(summary['external_state_mutated']).lower()}`",
        "",
        "## Missing Full Rows",
        "",
        "| artifact_key | status | path |",
        "| --- | --- | --- |",
    ]
    for row in payload["expected_full_rows"]:
        lines.append(f"| `{row['artifact_key']}` | `{row['status']}` | `{row['path']}` |")

    lines.extend(
        [
            "",
            "## Ranking Inputs",
            "",
            "| artifact_key | status | path |",
            "| --- | --- | --- |",
        ]
    )
    for row in payload["ranking_inputs"]:
        lines.append(f"| `{row['artifact_key']}` | `{row['status']}` | `{row['path']}` |")

    lines.extend(
        [
            "",
            "## Current Blockers",
            "",
            "| target | blockers | anchor_margin | retained_decoys |",
            "| --- | --- | --: | --: |",
        ]
    )
    for row in payload["target_blockers"]:
        lines.append(
            "| `{target}` | {blockers} | {anchor_margin} | {retained_decoys} |".format(
                target=row["target_id"],
                blockers=", ".join(row["blockers"]) or "(none)",
                anchor_margin="" if row.get("anchor_margin_a") is None else row["anchor_margin_a"],
                retained_decoys=(
                    "" if row.get("top_decoy_retained_count") is None else row["top_decoy_retained_count"]
                ),
            )
        )
    lines.extend(["", f"Next: {summary['recommended_next_local_action']}", ""])
    return "\n".join(lines)


def _csv_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    action = payload["summary"]["recommended_next_local_action"]
    for row in payload["expected_full_rows"]:
        rows.append(
            {
                "row_type": "full_row_artifact",
                "row_id": row["artifact_key"],
                "status": row["status"],
                "path": row["path"],
                "exists": str(row["exists"]).lower(),
                "recommended_next_local_action": action if not row["exists"] else "",
            }
        )
    for row in payload["ranking_inputs"]:
        rows.append(
            {
                "row_type": "ranking_input_artifact",
                "row_id": row["artifact_key"],
                "status": row["status"],
                "path": row["path"],
                "exists": str(row["exists"]).lower(),
                "recommended_next_local_action": action if not row["exists"] else "",
            }
        )
    retained = payload["retained_evidence"]
    rows.append(
        {
            "row_type": "retained_evidence_artifact",
            "row_id": retained["artifact_key"],
            "status": retained["status"],
            "path": retained["path"],
            "exists": str(retained["exists"]).lower(),
            "recommended_next_local_action": "",
        }
    )
    for row in payload["target_blockers"]:
        rows.append(
            {
                "row_type": "target_blocker",
                "row_id": row["target_id"],
                "status": row["gate_status"],
                "target_id": row["target_id"],
                "blockers": ";".join(row["blockers"]),
                "root_cause_tags": ";".join(row["root_cause_tags"]),
                "ranking_pr_auc_ci_low": row["ranking_pr_auc_ci_low"],
                "top20_hit_rate": row["top20_hit_rate"],
                "decoys_above_positive_count": row["decoys_above_positive_count"],
                "positive_target_rank": row["positive_target_rank"],
                "positive_anchor_distance_a": row["positive_anchor_distance_a"],
                "top_decoy_anchor_distance_a": row["top_decoy_anchor_distance_a"],
                "anchor_margin_a": row["anchor_margin_a"],
                "retained_target_row_count": row["retained_target_row_count"],
                "retained_positive_count": row["retained_positive_count"],
                "top_decoy_retained_count": row["top_decoy_retained_count"],
                "recommended_next_local_action": action,
            }
        )
    return rows


def write_artifacts(payload: dict[str, Any], *, out_json: str | Path, out_md: str | Path, out_csv: str | Path) -> None:
    json_path = _resolve(out_json)
    md_path = _resolve(out_md)
    csv_path = _resolve(out_csv)
    for path in (json_path, md_path, csv_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for row in _csv_rows(payload):
            writer.writerow({column: row.get(column, "") for column in _CSV_COLUMNS})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the GPCR full-row recovery work order (read-only).")
    parser.add_argument("--provenance-json", default=DEFAULT_PROVENANCE_JSON)
    parser.add_argument("--suite-json", default=DEFAULT_SUITE_JSON)
    parser.add_argument("--ranking-summary-json", default=DEFAULT_RANKING_SUMMARY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    payload = build_gpcr_hard_decoy_full_row_recovery_work_order(
        provenance_json=args.provenance_json,
        suite_json=args.suite_json,
        ranking_summary_json=args.ranking_summary_json,
    )
    write_artifacts(payload, out_json=args.out_json, out_md=args.out_md, out_csv=args.out_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
