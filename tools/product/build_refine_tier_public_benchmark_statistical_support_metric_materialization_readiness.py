#!/usr/bin/env python3
"""Build R9 statistical-support metric materialization readiness packet."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_statistical_support_candidate_queue import (
    DEFAULT_OUT_JSON as DEFAULT_CANDIDATE_QUEUE_JSON,
)
from tools.product.build_refine_tier_public_benchmark_statistical_support_coordinate_intake import (
    DEFAULT_OUT_JSON as DEFAULT_COORDINATE_INTAKE_JSON,
    DEFAULT_OUT_VALIDATION_CSV as DEFAULT_COORDINATE_VALIDATION_CSV,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.json"
)
DEFAULT_OUT_CSV = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.csv"
)
DEFAULT_OUT_MD = (
    "runs/refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_current.md"
)

REQUIRED_METRIC_SOURCE_PAYLOADS = ["dockq", "lddt_pli", "internal_deltaG"]
CLAIM_BOUNDARY = (
    "Refine-tier public-benchmark statistical-support metric materialization readiness only; it reads "
    "local candidate queue and coordinate validation artifacts to determine whether the 17 R9 "
    "statistical-support candidates are ready for deterministic local DockQ/lDDT-PLI/internal DeltaG "
    "source materialization. It does not download coordinates, run docking or MD, compute metrics, write "
    "metric payloads, write canonical intake, approve receipts, promote claims, upload, email, delete, "
    "commit, push, or mutate external state."
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


def _read_csv(path_like: str | Path, *, root: Path = ROOT) -> tuple[list[dict[str, Any]], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return [], False
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)], True


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _rows(payload: dict[str, Any], key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _path_present(path_like: str | Path, *, root: Path = ROOT) -> bool:
    value = _text(path_like)
    if not value:
        return False
    return _resolve(value, root=root).is_file()


def _validation_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _text(row.get("candidate_queue_id")),
        _text(row.get("target_id")).lower(),
        _text(row.get("pose_id")),
    )


def _metric_source_paths(row: dict[str, Any]) -> list[str]:
    return [
        _text(row.get("dockq_source_artifact")),
        _text(row.get("lddt_pli_source_artifact")),
        _text(row.get("internal_deltaG_source_artifact")),
    ]


def _readiness_row(
    candidate: dict[str, Any],
    validation_by_key: dict[tuple[str, str, str], dict[str, Any]],
    *,
    root: Path,
) -> dict[str, Any]:
    target_id = _text(candidate.get("target_id")).lower()
    pose_id = _text(candidate.get("pose_id"))
    candidate_key = (_text(candidate.get("candidate_queue_id")), target_id, pose_id)
    validation = validation_by_key.get(candidate_key, {})
    validation_status = _text(validation.get("coordinate_validation_status")) or "missing"
    coordinate_pass = validation_status == "pass"
    ligand_pose = _text(candidate.get("ligand_pose_artifact"))
    ligand_present = _bool(candidate.get("ligand_pose_artifact_present")) and _path_present(
        ligand_pose,
        root=root,
    )
    delta_g = _text(candidate.get("deltaG_experimental_kcal_mol"))
    metric_paths = _metric_source_paths(candidate)
    metric_paths_present = all(metric_paths)
    existing_metric_source_count = sum(1 for path in metric_paths if _path_present(path, root=root))

    blockers: list[str] = []
    if not validation:
        blockers.append("coordinate_validation_row_missing")
    elif not coordinate_pass:
        blockers.append("coordinate_validation_not_pass")
    if not ligand_present:
        blockers.append("ligand_pose_artifact_missing")
    if not delta_g:
        blockers.append("experimental_deltaG_missing")
    if not metric_paths_present:
        blockers.append("metric_source_artifact_paths_missing")

    ready = not blockers
    return {
        "candidate_queue_id": _text(candidate.get("candidate_queue_id")),
        "expansion_slot_id": _text(candidate.get("expansion_slot_id")),
        "suggested_work_order_id": _text(candidate.get("suggested_work_order_id")),
        "target_id": target_id,
        "pose_id": pose_id,
        "required_split": _text(candidate.get("required_split")),
        "suggested_split": _text(candidate.get("suggested_split")),
        "ligand_pose_artifact": ligand_pose,
        "ligand_pose_artifact_present": ligand_present,
        "deltaG_experimental_kcal_mol": delta_g,
        "experimental_deltaG_present": bool(delta_g),
        "receptor_coordinate_artifact": _text(validation.get("receptor_coordinate_artifact")),
        "coordinate_validation_status": validation_status,
        "coordinate_validation_blockers": _text(validation.get("blockers")),
        "coordinate_validation_pass": coordinate_pass,
        "dockq_source_artifact": metric_paths[0],
        "lddt_pli_source_artifact": metric_paths[1],
        "internal_deltaG_source_artifact": metric_paths[2],
        "required_metric_source_payloads": ";".join(REQUIRED_METRIC_SOURCE_PAYLOADS),
        "required_metric_source_payload_count": len(REQUIRED_METRIC_SOURCE_PAYLOADS),
        "planned_metric_source_payload_count": len([path for path in metric_paths if path]),
        "existing_metric_source_payload_count": existing_metric_source_count,
        "metric_source_artifact_paths_present": metric_paths_present,
        "metric_materialization_candidate_ready": ready,
        "metric_materialization_status": (
            "ready_for_metric_source_materialization"
            if ready
            else "blocked_metric_source_materialization_inputs"
        ),
        "metric_materialization_blockers": ";".join(blockers),
        "next_required_step": (
            "materialize_statistical_support_metric_sources"
            if ready
            else "pass_coordinate_validation_before_metric_source_materialization"
        ),
        "canonical_intake_promotion_allowed": False,
        "external_state_mutated": False,
    }


def build_refine_tier_public_benchmark_statistical_support_metric_materialization_readiness(
    *,
    candidate_queue_json: str | Path = DEFAULT_CANDIDATE_QUEUE_JSON,
    coordinate_intake_json: str | Path = DEFAULT_COORDINATE_INTAKE_JSON,
    coordinate_validation_csv: str | Path = DEFAULT_COORDINATE_VALIDATION_CSV,
    root: Path = ROOT,
) -> dict[str, Any]:
    candidate_payload, candidate_present = _read_json(candidate_queue_json, root=root)
    coordinate_payload, coordinate_present = _read_json(coordinate_intake_json, root=root)
    validation_csv_rows, validation_csv_present = _read_csv(coordinate_validation_csv, root=root)
    candidate_summary = _summary(candidate_payload)
    coordinate_summary = _summary(coordinate_payload)
    candidate_rows = _rows(candidate_payload)
    validation_rows = _rows(coordinate_payload, "validation_rows") or validation_csv_rows
    validation_by_key = {_validation_key(row): row for row in validation_rows}
    rows = [_readiness_row(candidate, validation_by_key, root=root) for candidate in candidate_rows]

    blockers: list[str] = []
    if not candidate_present:
        blockers.append("candidate_queue_missing")
    if not coordinate_present:
        blockers.append("coordinate_intake_missing")
    if not validation_csv_present:
        blockers.append("coordinate_validation_csv_missing")
    if candidate_summary.get("status") != "refine_tier_public_benchmark_statistical_support_candidate_queue_ready":
        blockers.append("candidate_queue_not_ready")
    if coordinate_summary.get("status") != "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready":
        blockers.append("coordinate_intake_not_ready")

    ready_rows = [row for row in rows if row["metric_materialization_candidate_ready"] is True]
    blocked_rows = [row for row in rows if row["metric_materialization_candidate_ready"] is not True]
    row_count = len(rows)
    planned_metric_source_payload_count = sum(
        int(row.get("planned_metric_source_payload_count") or 0) for row in rows
    )
    existing_metric_source_payload_count = sum(
        int(row.get("existing_metric_source_payload_count") or 0) for row in rows
    )
    readiness_ready = bool(candidate_present and coordinate_present and validation_csv_present and row_count and not blockers)
    summary = {
        "packet_type": "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness",
        "status": (
            "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready"
            if readiness_ready
            else "blocked_refine_tier_public_benchmark_statistical_support_metric_materialization_readiness"
        ),
        "metric_materialization_readiness_ready": readiness_ready,
        "metric_materialization_all_candidates_ready": bool(row_count and len(ready_rows) == row_count),
        "candidate_queue": _display(candidate_queue_json, root=root),
        "candidate_queue_present": candidate_present,
        "candidate_queue_ready": bool(
            candidate_summary.get("status")
            == "refine_tier_public_benchmark_statistical_support_candidate_queue_ready"
        ),
        "candidate_queue_selected_candidate_count": int(
            candidate_summary.get("selected_candidate_count") or row_count
        ),
        "coordinate_intake": _display(coordinate_intake_json, root=root),
        "coordinate_intake_present": coordinate_present,
        "coordinate_intake_ready": bool(
            coordinate_summary.get("status")
            == "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready"
        ),
        "coordinate_validation_csv": _display(coordinate_validation_csv, root=root),
        "coordinate_validation_csv_present": validation_csv_present,
        "coordinate_validation_row_count": len(validation_rows),
        "coordinate_validation_pass_row_count": sum(
            1 for row in rows if row["coordinate_validation_status"] == "pass"
        ),
        "coordinate_validation_blocked_row_count": sum(
            1 for row in rows if row["coordinate_validation_status"] != "pass"
        ),
        "metric_materialization_row_count": row_count,
        "metric_materialization_candidate_ready_count": len(ready_rows),
        "metric_materialization_candidate_blocked_count": len(blocked_rows),
        "required_metric_source_payloads": ";".join(REQUIRED_METRIC_SOURCE_PAYLOADS),
        "required_metric_source_payload_count": len(REQUIRED_METRIC_SOURCE_PAYLOADS),
        "metric_source_path_row_count": sum(
            1 for row in rows if row["metric_source_artifact_paths_present"] is True
        ),
        "planned_metric_source_payload_count": planned_metric_source_payload_count,
        "existing_metric_source_payload_count": existing_metric_source_payload_count,
        "ligand_pose_artifact_present_count": sum(
            1 for row in rows if row["ligand_pose_artifact_present"] is True
        ),
        "experimental_deltaG_prefilled_count": sum(
            1 for row in rows if row["experimental_deltaG_present"] is True
        ),
        "candidate_ready_for_canonical_intake_count": 0,
        "claim_grade_statistical_support_ready": False,
        "canonical_intake_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "After operator-approved coordinate fetch and post-fetch validation, require all 17 "
            "statistical-support candidates to pass coordinate validation before materializing DockQ, "
            "lDDT-PLI, and internal DeltaG source payloads and rerunning bootstrap Spearman p05."
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
        "# R9 Statistical Support Metric Materialization Readiness",
        "",
        f"- status: `{summary['status']}`",
        f"- metric_materialization_row_count: `{summary['metric_materialization_row_count']}`",
        f"- metric_materialization_candidate_ready_count: `{summary['metric_materialization_candidate_ready_count']}`",
        f"- metric_materialization_candidate_blocked_count: `{summary['metric_materialization_candidate_blocked_count']}`",
        f"- coordinate_validation_pass_row_count: `{summary['coordinate_validation_pass_row_count']}`",
        f"- planned_metric_source_payload_count: `{summary['planned_metric_source_payload_count']}`",
        f"- existing_metric_source_payload_count: `{summary['existing_metric_source_payload_count']}`",
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
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(
        description="Build read-only readiness for R9 statistical-support metric materialization."
    )
    parser.add_argument("--candidate-queue-json", default=DEFAULT_CANDIDATE_QUEUE_JSON)
    parser.add_argument("--coordinate-intake-json", default=DEFAULT_COORDINATE_INTAKE_JSON)
    parser.add_argument("--coordinate-validation-csv", default=DEFAULT_COORDINATE_VALIDATION_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_refine_tier_public_benchmark_statistical_support_metric_materialization_readiness(
        candidate_queue_json=args.candidate_queue_json,
        coordinate_intake_json=args.coordinate_intake_json,
        coordinate_validation_csv=args.coordinate_validation_csv,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
