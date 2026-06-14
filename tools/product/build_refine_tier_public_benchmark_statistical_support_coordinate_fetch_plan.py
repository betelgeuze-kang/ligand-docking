#!/usr/bin/env python3
"""Build a fetch/staging plan for R9 statistical-support coordinate artifacts."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_statistical_support_coordinate_intake import (
    DEFAULT_OUT_JSON as DEFAULT_COORDINATE_INTAKE_JSON,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_current.csv"
DEFAULT_OUT_MD = "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_current.md"

CLAIM_BOUNDARY = (
    "Refine-tier public-benchmark statistical-support coordinate fetch plan only; it reads the local "
    "coordinate intake and emits operator-reviewable public coordinate staging rows. It does not download "
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


def _list(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _split(value: Any) -> list[str]:
    out: list[str] = []
    for part in _text(value).split(";"):
        item = part.strip()
        if item and item not in out:
            out.append(item)
    return out


def _path_present(path_like: str, *, root: Path) -> bool:
    path_like = _text(path_like)
    if not path_like or "::" in path_like:
        return False
    return _resolve(path_like, root=root).is_file()


def _primary_public_url(row: dict[str, Any]) -> str:
    urls = _split(row.get("suggested_public_coordinate_urls"))
    return next((url for url in urls if url.lower().endswith(".pdb")), urls[0] if urls else "")


def _staging_destination(row: dict[str, Any]) -> str:
    target_id = _text(row.get("target_id")).lower()
    paths = _split(row.get("suggested_local_coordinate_paths"))
    complex_path = next((path for path in paths if path.lower().endswith("_complex.pdb")), "")
    if complex_path:
        return complex_path
    pdb_path = next((path for path in paths if path.lower().endswith(".pdb")), "")
    if pdb_path:
        return pdb_path
    return f"data/public_benchmarks/pdbbind_casf_pose_affinity/{target_id}/{target_id}_complex.pdb"


def _validation_key(row: dict[str, Any]) -> tuple[str, str]:
    return (_text(row.get("candidate_queue_id")), _text(row.get("target_id")).lower())


def _fetch_row(
    row: dict[str, Any],
    *,
    validation_by_key: dict[tuple[str, str], dict[str, Any]],
    root: Path,
) -> dict[str, Any]:
    validation = validation_by_key.get(_validation_key(row), {})
    current_artifact = _text(row.get("current_receptor_coordinate_artifact"))
    current_present = _bool(row.get("receptor_coordinate_artifact_present"))
    validation_status = _text(validation.get("coordinate_validation_status")) or "not_run"
    primary_url = _primary_public_url(row)
    destination = _staging_destination(row)
    destination_present = _path_present(destination, root=root)
    fetch_required = not current_present and not destination_present
    blockers: list[str] = []
    if not primary_url:
        blockers.append("public_coordinate_url_missing")
    if not destination:
        blockers.append("coordinate_staging_destination_missing")
    if fetch_required:
        blockers.append("operator_approved_coordinate_fetch_not_executed")
    if current_present and validation_status == "pass":
        status = "coordinate_artifact_already_validated"
    elif destination_present:
        status = "staged_coordinate_ready_for_validation"
    elif blockers:
        status = "blocked_coordinate_fetch_pending"
    else:
        status = "coordinate_fetch_plan_ready"
    return {
        "candidate_queue_id": _text(row.get("candidate_queue_id")),
        "expansion_slot_id": _text(row.get("expansion_slot_id")),
        "suggested_work_order_id": _text(row.get("suggested_work_order_id")),
        "target_id": _text(row.get("target_id")).lower(),
        "pose_id": _text(row.get("pose_id")),
        "required_split": _text(row.get("required_split")),
        "suggested_split": _text(row.get("suggested_split")),
        "current_coordinate_artifact": current_artifact,
        "current_coordinate_artifact_present": current_present,
        "coordinate_validation_status": validation_status,
        "source_url_primary": primary_url,
        "source_url_alternates": ";".join(_split(row.get("suggested_public_coordinate_urls"))),
        "staging_destination_path": destination,
        "staging_destination_present": destination_present,
        "fetch_required": fetch_required,
        "operator_coordinate_source_review_required": _text(
            row.get("operator_coordinate_source_review_required")
        ),
        "coordinate_fetch_status": status,
        "coordinate_fetch_blockers": ";".join(blockers),
        "download_command_template": (
            "operator-approved curl -L --fail --show-error --output "
            "{staging_destination_path} {source_url_primary}"
        ),
        "post_fetch_validation_command": (
            "python3 tools/product/build_refine_tier_public_benchmark_statistical_support_coordinate_intake.py"
        ),
        "canonical_intake_promotion_allowed": False,
        "external_state_mutated": False,
    }


def build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan(
    *,
    coordinate_intake_json: str | Path = DEFAULT_COORDINATE_INTAKE_JSON,
    root: Path = ROOT,
) -> dict[str, Any]:
    coordinate_payload, coordinate_present = _read_json(coordinate_intake_json, root=root)
    coordinate_summary = _summary(coordinate_payload)
    intake_rows = _list(coordinate_payload, "intake_rows")
    validation_rows = _list(coordinate_payload, "validation_rows")
    validation_by_key = {_validation_key(row): row for row in validation_rows}
    rows = [_fetch_row(row, validation_by_key=validation_by_key, root=root) for row in intake_rows]
    blockers: list[str] = []
    if not coordinate_present:
        blockers.append("coordinate_intake_missing")
    if coordinate_summary.get("status") != "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready":
        blockers.append("coordinate_intake_not_ready")
    fetch_plan_ready = bool(coordinate_present and not blockers and rows)
    fetch_required_count = sum(1 for row in rows if row["fetch_required"] is True)
    destination_present_count = sum(1 for row in rows if row["staging_destination_present"] is True)
    current_present_count = sum(1 for row in rows if row["current_coordinate_artifact_present"] is True)
    ready_for_validation_count = sum(
        1
        for row in rows
        if row["current_coordinate_artifact_present"] is True or row["staging_destination_present"] is True
    )
    summary = {
        "packet_type": "refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan",
        "status": (
            "refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan_ready"
            if fetch_plan_ready
            else "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan"
        ),
        "coordinate_fetch_plan_ready": fetch_plan_ready,
        "coordinate_intake": _display(coordinate_intake_json, root=root),
        "coordinate_intake_present": coordinate_present,
        "coordinate_intake_ready": bool(
            coordinate_summary.get("status")
            == "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready"
        ),
        "coordinate_intake_row_count": int(coordinate_summary.get("coordinate_intake_row_count") or 0),
        "coordinate_validation_pass_row_count": int(
            coordinate_summary.get("coordinate_validation_pass_row_count") or 0
        ),
        "coordinate_validation_blocked_row_count": int(
            coordinate_summary.get("coordinate_validation_blocked_row_count") or 0
        ),
        "coordinate_fetch_row_count": len(rows),
        "coordinate_fetch_required_row_count": fetch_required_count,
        "coordinate_fetch_blocked_row_count": sum(
            1 for row in rows if _text(row.get("coordinate_fetch_status")).startswith("blocked_")
        ),
        "coordinate_fetch_primary_url_row_count": sum(1 for row in rows if _text(row.get("source_url_primary"))),
        "coordinate_fetch_staging_destination_row_count": sum(
            1 for row in rows if _text(row.get("staging_destination_path"))
        ),
        "coordinate_fetch_destination_present_row_count": destination_present_count,
        "coordinate_fetch_current_artifact_present_row_count": current_present_count,
        "coordinate_fetch_ready_for_validation_row_count": ready_for_validation_count,
        "coordinate_fetch_operator_review_required_row_count": sum(
            1 for row in rows if _text(row.get("operator_coordinate_source_review_required"))
        ),
        "coordinate_fetch_external_download_executed": False,
        "canonical_intake_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run an operator-approved public coordinate fetch/staging step for the 17 R9 statistical-support "
            "targets, then rerun coordinate intake validation before metric source materialization."
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
    path.write_text(
        "\n".join(
            [
                "# R9 Statistical Support Coordinate Fetch Plan",
                "",
                f"- status: `{summary['status']}`",
                f"- coordinate_fetch_row_count: `{summary['coordinate_fetch_row_count']}`",
                f"- coordinate_fetch_required_row_count: `{summary['coordinate_fetch_required_row_count']}`",
                f"- coordinate_fetch_primary_url_row_count: "
                f"`{summary['coordinate_fetch_primary_url_row_count']}`",
                f"- coordinate_fetch_staging_destination_row_count: "
                f"`{summary['coordinate_fetch_staging_destination_row_count']}`",
                f"- coordinate_fetch_ready_for_validation_row_count: "
                f"`{summary['coordinate_fetch_ready_for_validation_row_count']}`",
                "",
                "## Claim Boundary",
                "",
                summary["claim_boundary"],
                "",
                "## Next Required Step",
                "",
                summary["next_required_step"],
                "",
            ]
        ),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description="Build a local public coordinate fetch/staging plan for R9 statistical-support candidates."
    )
    parser.add_argument("--coordinate-intake-json", default=DEFAULT_COORDINATE_INTAKE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_refine_tier_public_benchmark_statistical_support_coordinate_fetch_plan(
        coordinate_intake_json=args.coordinate_intake_json
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
