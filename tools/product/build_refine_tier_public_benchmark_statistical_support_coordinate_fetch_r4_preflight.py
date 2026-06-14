#!/usr/bin/env python3
"""Build R4/operator preflight for R9 statistical-support coordinate fetch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan import (
    DEFAULT_OUT_JSON as DEFAULT_FETCH_APPLY_JSON,
)
from tools.product.build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan import (
    DEFAULT_OUT_JSON as DEFAULT_FETCH_PLAN_JSON,
)
from tools.product.fetch_public_benchmark_native_structure import APPROVAL_TOKEN

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_current.json"
)
DEFAULT_OUT_CSV = (
    "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_current.csv"
)
DEFAULT_OUT_MD = (
    "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_current.md"
)

EXECUTE_COMMAND = (
    "python3 tools/product/apply_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan.py "
    "--mode execute --run-post-fetch-validation "
    f"--approval-token {APPROVAL_TOKEN}"
)
REQUIRED_R4_FIELDS = ["target", "action", "impact", "risk", "rollback", "verification"]
CLAIM_BOUNDARY = (
    "Refine-tier public-benchmark statistical-support coordinate fetch R4 preflight only; it compiles "
    "operator-reviewable Target/Action/Impact/Risk/Rollback/Verification rows for the 17 public RCSB "
    "coordinate fetches and points to the approved execute+validation command. It does not download "
    "coordinates, run docking or MD, compute metrics, write canonical intake, approve receipts, promote "
    "claims, upload, email, delete, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _r4_values(row: dict[str, Any]) -> dict[str, str]:
    target_id = _text(row.get("target_id")).lower()
    pose_id = _text(row.get("pose_id"))
    destination = _text(row.get("staging_destination_path"))
    source_url = _text(row.get("source_url_primary"))
    return {
        "target": f"R9 statistical-support public coordinate fetch for {target_id}/{pose_id}",
        "action": (
            f"Download the public RCSB coordinate file from {source_url} into {destination}, "
            "then run post-fetch coordinate intake validation."
        ),
        "impact": (
            "Adds a local reviewed receptor/complex coordinate artifact for one R9 statistical-support "
            "benchmark candidate; it may move that candidate from coordinate-missing to validation-ready, "
            "but it does not promote claims or write canonical intake."
        ),
        "risk": (
            "Wrong biological assembly, ligand-only file, license/source mismatch, network/download failure, "
            "or target/pose mismatch could contaminate public benchmark evidence if not revalidated."
        ),
        "rollback": f"Remove the staged local coordinate file at {destination} and rerun the preview apply and coordinate intake builders.",
        "verification": (
            "Run the execute command with --run-post-fetch-validation, then require coordinate validation pass "
            "rows before metric source materialization."
        ),
    }


def _preflight_row(row: dict[str, Any], *, index: int) -> dict[str, Any]:
    values = _r4_values(row)
    blockers: list[str] = []
    if not _text(row.get("target_id")):
        blockers.append("target_id_missing")
    if not _text(row.get("pose_id")):
        blockers.append("pose_id_missing")
    if not _text(row.get("source_url_primary")):
        blockers.append("source_url_primary_missing")
    if not _text(row.get("staging_destination_path")):
        blockers.append("staging_destination_path_missing")
    missing_r4_fields = [field for field in REQUIRED_R4_FIELDS if not values[field]]
    blockers.extend(f"r4_{field}_missing" for field in missing_r4_fields)
    status = "ready_for_r4_operator_confirmation" if not blockers else "blocked_r4_preflight_row"
    return {
        "r4_review_id": f"r9_statistical_support_coordinate_fetch_{index:03d}",
        "candidate_queue_id": _text(row.get("candidate_queue_id")),
        "expansion_slot_id": _text(row.get("expansion_slot_id")),
        "suggested_work_order_id": _text(row.get("suggested_work_order_id")),
        "target_id": _text(row.get("target_id")).lower(),
        "pose_id": _text(row.get("pose_id")),
        "required_split": _text(row.get("required_split")),
        "source_url_primary": _text(row.get("source_url_primary")),
        "staging_destination_path": _text(row.get("staging_destination_path")),
        "execute_command": EXECUTE_COMMAND,
        "approval_token_required": APPROVAL_TOKEN,
        "operator_confirmation_required": True,
        "target": values["target"],
        "action": values["action"],
        "impact": values["impact"],
        "risk": values["risk"],
        "rollback": values["rollback"],
        "verification": values["verification"],
        "required_r4_fields": ";".join(REQUIRED_R4_FIELDS),
        "missing_r4_fields": ";".join(missing_r4_fields),
        "r4_preflight_status": status,
        "row_blockers": ";".join(blockers),
        "download_executed": False,
        "canonical_intake_promotion_allowed": False,
        "external_state_mutated": False,
    }


def build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight(
    *,
    fetch_plan_json: str | Path = DEFAULT_FETCH_PLAN_JSON,
    fetch_apply_json: str | Path = DEFAULT_FETCH_APPLY_JSON,
    root: Path = ROOT,
) -> dict[str, Any]:
    plan_payload, plan_present = _read_json(fetch_plan_json, root=root)
    apply_payload, apply_present = _read_json(fetch_apply_json, root=root)
    plan_summary = _summary(plan_payload)
    apply_summary = _summary(apply_payload)
    plan_rows = _rows(plan_payload)
    rows = [_preflight_row(row, index=index) for index, row in enumerate(plan_rows, start=1)]

    blockers: list[str] = []
    if not plan_present:
        blockers.append("coordinate_fetch_plan_missing")
    if not apply_present:
        blockers.append("coordinate_fetch_apply_missing")
    if plan_summary.get("status") != "refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_ready":
        blockers.append("coordinate_fetch_plan_not_ready")
    if apply_summary.get("status") != "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_apply":
        blockers.append("coordinate_fetch_apply_not_in_preview_blocked_posture")
    if not _bool(apply_summary.get("coordinate_fetch_apply_preview_ready")):
        blockers.append("coordinate_fetch_apply_preview_not_ready")
    if not _bool(apply_summary.get("post_fetch_validation_supported")):
        blockers.append("post_fetch_validation_not_supported")
    blocked_rows = [row for row in rows if _text(row.get("r4_preflight_status")).startswith("blocked")]
    if blocked_rows:
        blockers.append("blocked_r4_preflight_rows_present")

    ready = bool(plan_present and apply_present and rows and not blockers)
    summary = {
        "packet_type": "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight",
        "status": (
            "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
            if ready
            else "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight"
        ),
        "r4_preflight_ready": ready,
        "operator_approval_required": True,
        "operator_confirmation_required": True,
        "authorized_for_external_download": False,
        "fetch_plan": _display(fetch_plan_json, root=root),
        "fetch_plan_present": plan_present,
        "fetch_plan_ready": bool(
            plan_summary.get("status")
            == "refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_ready"
        ),
        "fetch_apply": _display(fetch_apply_json, root=root),
        "fetch_apply_present": apply_present,
        "fetch_apply_preview_ready": _bool(apply_summary.get("coordinate_fetch_apply_preview_ready")),
        "post_fetch_validation_supported": _bool(apply_summary.get("post_fetch_validation_supported")),
        "approval_token_required": APPROVAL_TOKEN,
        "approval_token_present": False,
        "approval_token_accepted": False,
        "execute_command": EXECUTE_COMMAND,
        "execute_command_count": 1,
        "required_r4_fields": ";".join(REQUIRED_R4_FIELDS),
        "required_r4_field_count": len(REQUIRED_R4_FIELDS),
        "required_r4_fields_present": all(
            all(_text(row.get(field)) for field in REQUIRED_R4_FIELDS) for row in rows
        ),
        "r4_row_count": len(rows),
        "ready_for_r4_review_row_count": len(rows) - len(blocked_rows),
        "blocked_r4_row_count": len(blocked_rows),
        "target_row_count": sum(1 for row in rows if _text(row.get("target_id"))),
        "source_url_primary_row_count": sum(1 for row in rows if _text(row.get("source_url_primary"))),
        "staging_destination_row_count": sum(1 for row in rows if _text(row.get("staging_destination_path"))),
        "missing_r4_field_row_count": sum(1 for row in rows if _text(row.get("missing_r4_fields"))),
        "download_executed": False,
        "canonical_intake_promotion_allowed": False,
        "external_state_mutated": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Present Target/Action/Impact/Risk/Rollback/Verification for the 17 public coordinate "
            f"fetches to the operator; only after explicit approval run `{EXECUTE_COMMAND}`, then "
            "review coordinate validation before metric source materialization."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# R9 Statistical Support Coordinate Fetch R4 Preflight",
        "",
        f"- status: `{summary['status']}`",
        f"- r4_preflight_ready: `{summary['r4_preflight_ready']}`",
        f"- r4_row_count: `{summary['r4_row_count']}`",
        f"- ready_for_r4_review_row_count: `{summary['ready_for_r4_review_row_count']}`",
        f"- blocked_r4_row_count: `{summary['blocked_r4_row_count']}`",
        f"- approval_token_required: `{summary['approval_token_required']}`",
        f"- execute_command: `{summary['execute_command']}`",
        "",
        "## Rows",
        "",
        "| review_id | target | pose | status | source_url | destination |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['r4_review_id']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['r4_preflight_status']}` | `{row['source_url_primary']}` | "
            f"`{row['staging_destination_path']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], "", "## Next Required Step", "", summary["next_required_step"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description="Build read-only R4 preflight rows for R9 statistical-support coordinate fetch."
    )
    parser.add_argument("--fetch-plan-json", default=DEFAULT_FETCH_PLAN_JSON)
    parser.add_argument("--fetch-apply-json", default=DEFAULT_FETCH_APPLY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight(
        fetch_plan_json=args.fetch_plan_json,
        fetch_apply_json=args.fetch_apply_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
