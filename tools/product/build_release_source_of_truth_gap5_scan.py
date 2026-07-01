#!/usr/bin/env python3
"""Build the remaining source-of-truth gap-5 scan.

Read-only: this materializes the five explicitly requested post-#37
source-of-truth candidates as a small classification ledger. It does not mark
the broader release source-of-truth gate ready and does not promote claims.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SOURCE_OF_TRUTH_JSON = "runs/product_release_source_of_truth_gate_current.json"
DEFAULT_OUT_JSON = "runs/release_source_of_truth_gap5_scan_current.json"
DEFAULT_OUT_MD = "runs/release_source_of_truth_gap5_scan_current.md"
DEFAULT_OUT_CSV = "runs/release_source_of_truth_gap5_scan_current.csv"

PACKET_TYPE = "release_source_of_truth_gap5_scan"
SCHEMA_VERSION = "release_source_of_truth_gap5_scan_v1"

CLAIM_BOUNDARY = (
    "Remaining source-of-truth gap-5 scan only; it classifies the five requested post-#37 "
    "candidate artifacts from local current source-of-truth rows and local current artifact summaries. "
    "It does not mark the full release source-of-truth gate ready, run docking, execute operators, "
    "promote production AI, promote broad scientific claims, deploy, submit, upload, or mutate external state."
)

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "claim_promotion_allowed": False,
}

_CANDIDATES = [
    {
        "artifact_id": "accuracy_parity_scorecard",
        "artifact_path": "runs/accuracy_parity_scorecard_current.json",
        "requested_classification": "fix",
        "secondary_classification": "",
        "review_priority": "science_scorecard_priority",
        "expected_current_status": "blocked_accuracy_parity",
        "basis": (
            "Science scorecard source-of-truth row is fresh and metric evidence is separated from broad "
            "GPCR/Schrodinger-class claim lock."
        ),
    },
    {
        "artifact_id": "product_production_ai_checkpoint_readiness",
        "artifact_path": "runs/product_production_ai_checkpoint_readiness_current.json",
        "requested_classification": "fix",
        "secondary_classification": "aggregator-review",
        "review_priority": "product_ai_checkpoint_readiness",
        "expected_current_status": "blocked_product_production_ai_checkpoint_readiness",
        "basis": (
            "Source-of-truth freshness is fixed; the artifact remains intentionally blocked for guarded "
            "production-inference acceptance and should stay visible in aggregator review."
        ),
    },
    {
        "artifact_id": "goal_readiness_rollup",
        "artifact_path": "runs/goal_readiness_rollup_current.json",
        "requested_classification": "fix",
        "secondary_classification": "",
        "review_priority": "goal_rollup_readiness",
        "expected_current_status": "blocked_goal_readiness",
        "basis": (
            "Rollup source-of-truth freshness is fixed while the rollup honestly reports blocked "
            "operator/external lanes."
        ),
    },
    {
        "artifact_id": "product_goal_completion_audit",
        "artifact_path": "runs/product_goal_completion_audit_current.json",
        "requested_classification": "aggregator-review",
        "secondary_classification": "",
        "review_priority": "goal_completion_release_blocker_visibility",
        "expected_current_status": "blocked_product_goal_completion_audit",
        "basis": (
            "Freshness is pass, but the audit is the aggregator-facing release blocker surface for incomplete "
            "product/full-commercial goal closure."
        ),
    },
    {
        "artifact_id": "goal_operator_action_board",
        "artifact_path": "runs/goal_operator_action_board_current.json",
        "requested_classification": "aggregator-review",
        "secondary_classification": "",
        "review_priority": "operator_action_visibility",
        "expected_current_status": "operator_actions_required",
        "basis": (
            "Freshness is pass, and the board is an operator-facing aggregator surface rather than a stale "
            "source-of-truth defect."
        ),
    },
]

_CSV_COLUMNS = [
    "artifact_id",
    "requested_classification",
    "secondary_classification",
    "review_priority",
    "source_of_truth_row_status",
    "source_of_truth_release_blocker",
    "source_of_truth_artifact_path",
    "current_artifact_status",
    "expected_current_status",
    "current_artifact_status_matches_expected",
    "artifact_present",
    "classification_status",
    "downstream_stale_blocker_count",
    "downstream_stale_artifact_ids",
    "downstream_refresh_required",
    "basis",
    "execution_enabled",
    "external_state_mutated",
    "claim_promotion_allowed",
]


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _source_rows_by_artifact(source_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = source_payload.get("rows") if isinstance(source_payload.get("rows"), list) else []
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("row_type") == "artifact_freshness":
            artifact_id = _text(row.get("artifact_id"))
            if artifact_id and artifact_id not in by_id:
                by_id[artifact_id] = row
    return by_id


def _source_rows(source_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = source_payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _downstream_stale_rows_by_dependency(source_payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_dependency: dict[str, list[dict[str, Any]]] = {}
    for row in _source_rows(source_payload):
        if row.get("row_type") != "artifact_freshness" or not _bool(row.get("release_blocker")):
            continue
        stale_paths = row.get("stale_dependency_paths")
        if not isinstance(stale_paths, list):
            continue
        for stale_path in stale_paths:
            dependency = _text(stale_path)
            if dependency:
                by_dependency.setdefault(dependency, []).append(row)
    return by_dependency


def build_release_source_of_truth_gap5_scan(
    *,
    source_of_truth_json: str | Path = DEFAULT_SOURCE_OF_TRUTH_JSON,
    root: str | Path = ROOT,
) -> dict[str, Any]:
    root_path = Path(root)
    source_path = _resolve(source_of_truth_json, root=root_path)
    source_payload = _read_json(source_path, root=root_path)
    source_summary = _summary(source_payload)
    source_rows = _source_rows_by_artifact(source_payload)
    downstream_by_dependency = _downstream_stale_rows_by_dependency(source_payload)
    rows: list[dict[str, Any]] = []

    for spec in _CANDIDATES:
        artifact_path = _resolve(spec["artifact_path"], root=root_path)
        artifact_payload = _read_json(artifact_path, root=root_path)
        artifact_summary = _summary(artifact_payload)
        source_row = source_rows.get(spec["artifact_id"], {})
        source_status = _text(source_row.get("status"))
        artifact_status = _text(artifact_summary.get("status"))
        expected_status = _text(spec["expected_current_status"])
        source_release_blocker = _bool(source_row.get("release_blocker"))
        artifact_present = artifact_path.exists()
        status_matches = bool(artifact_status and artifact_status == expected_status)
        downstream_rows = downstream_by_dependency.get(spec["artifact_path"], [])
        downstream_artifact_ids = [_text(row.get("artifact_id")) for row in downstream_rows if _text(row.get("artifact_id"))]
        classification_ready = (
            source_status == "pass"
            and not source_release_blocker
            and artifact_present
            and status_matches
            and spec["requested_classification"] in {"fix", "no-op", "aggregator-review"}
        )
        rows.append(
            {
                "artifact_id": spec["artifact_id"],
                "requested_classification": spec["requested_classification"],
                "secondary_classification": spec["secondary_classification"],
                "review_priority": spec["review_priority"],
                "source_of_truth_row_status": source_status or "missing",
                "source_of_truth_release_blocker": source_release_blocker,
                "source_of_truth_artifact_path": _text(source_row.get("artifact_path")) or spec["artifact_path"],
                "current_artifact_status": artifact_status or "missing",
                "expected_current_status": expected_status,
                "current_artifact_status_matches_expected": status_matches,
                "artifact_present": artifact_present,
                "classification_status": "classified" if classification_ready else "needs_review",
                "downstream_stale_blocker_count": len(downstream_artifact_ids),
                "downstream_stale_artifact_ids": downstream_artifact_ids,
                "downstream_refresh_required": bool(downstream_artifact_ids),
                "basis": spec["basis"],
                **_READ_ONLY_FLAGS,
            }
        )

    classified_rows = [row for row in rows if row["classification_status"] == "classified"]
    needs_review_rows = [row for row in rows if row["classification_status"] != "classified"]
    classification_counts = {
        classification: sum(1 for row in rows if row["requested_classification"] == classification)
        for classification in ("fix", "no-op", "aggregator-review")
    }
    ready = len(classified_rows) == len(rows)
    downstream_stale_count = sum(int(row["downstream_stale_blocker_count"]) for row in rows)
    downstream_refresh_candidates = [
        row["artifact_id"] for row in rows if int(row["downstream_stale_blocker_count"]) > 0
    ]
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "release_source_of_truth_gap5_scan_ready" if ready else "blocked_release_source_of_truth_gap5_scan",
        "gap5_scan_ready": ready,
        "candidate_count": len(rows),
        "classified_count": len(classified_rows),
        "needs_review_count": len(needs_review_rows),
        "source_of_truth_json": str(source_path),
        "source_of_truth_status": _text(source_summary.get("status")),
        "source_of_truth_ready": bool(source_summary.get("release_source_of_truth_ready") is True),
        "source_of_truth_blocker_count": int(source_summary.get("blocker_count") or 0),
        "source_of_truth_stale_artifact_count": int(source_summary.get("stale_artifact_count") or 0),
        "classification_counts": classification_counts,
        "fix_count": classification_counts["fix"],
        "no_op_count": classification_counts["no-op"],
        "aggregator_review_count": classification_counts["aggregator-review"],
        "secondary_aggregator_review_count": sum(
            1 for row in rows if row["secondary_classification"] == "aggregator-review"
        ),
        "downstream_stale_blocker_count": downstream_stale_count,
        "downstream_refresh_candidate_count": len(downstream_refresh_candidates),
        "downstream_refresh_candidate_artifact_ids": downstream_refresh_candidates,
        "science_scorecard_reviewed": any(
            row["artifact_id"] == "accuracy_parity_scorecard"
            and row["classification_status"] == "classified"
            and row["requested_classification"] == "fix"
            for row in rows
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Gap-5 source-of-truth scan is classified; refresh downstream stale fanout artifacts before rerunning "
            "the broader source-of-truth gate."
            if ready and downstream_stale_count
            else "Gap-5 source-of-truth scan is classified; continue the broader release refresh/source-of-truth blockers."
            if ready
            else "Inspect the needs_review rows, rebuild their current artifacts, and rerun this scan."
        ),
        **_READ_ONLY_FLAGS,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in _CSV_COLUMNS})


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Release Source-Of-Truth Gap-5 Scan",
        "",
        f"- status: `{s['status']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- classified_count: `{s['classified_count']}`",
        f"- fix_count: `{s['fix_count']}`",
        f"- no_op_count: `{s['no_op_count']}`",
        f"- aggregator_review_count: `{s['aggregator_review_count']}`",
        f"- secondary_aggregator_review_count: `{s['secondary_aggregator_review_count']}`",
        f"- source_of_truth_status: `{s['source_of_truth_status']}`",
        f"- source_of_truth_blocker_count: `{s['source_of_truth_blocker_count']}`",
        f"- downstream_stale_blocker_count: `{s['downstream_stale_blocker_count']}`",
        "",
        "| artifact | classification | secondary | source row | artifact status | downstream stale | classification status |",
        "| --- | --- | --- | --- | --- | --: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{artifact}` | `{classification}` | `{secondary}` | `{source}` | `{artifact_status}` | {downstream} | `{class_status}` |".format(
                artifact=row["artifact_id"],
                classification=row["requested_classification"],
                secondary=row["secondary_classification"] or "",
                source=row["source_of_truth_row_status"],
                artifact_status=row["current_artifact_status"],
                downstream=row["downstream_stale_blocker_count"],
                class_status=row["classification_status"],
            )
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the release source-of-truth gap-5 scan.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--source-of-truth-json", default=DEFAULT_SOURCE_OF_TRUTH_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)
    root = Path(args.root)
    payload = build_release_source_of_truth_gap5_scan(
        source_of_truth_json=args.source_of_truth_json,
        root=root,
    )
    _write_json(args.out_json, payload, root=root)
    _write_csv(args.out_csv, payload["rows"], root=root)
    _write_md(args.out_md, payload, root=root)
    return 0 if payload["summary"]["gap5_scan_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
