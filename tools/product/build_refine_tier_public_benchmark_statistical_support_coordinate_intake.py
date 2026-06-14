#!/usr/bin/env python3
"""Build coordinate intake/validation packet for R9 statistical-support candidates."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.product.build_refine_tier_public_benchmark_readiness import (
    MIN_RECEPTOR_COORDINATE_ATOM_RECORDS,
    MIN_RECEPTOR_COORDINATE_DISTINCT_RESIDUES,
    MIN_RECEPTOR_COORDINATE_MACROMOLECULE_ATOM_RECORDS,
    MIN_RECEPTOR_COORDINATE_PROTEIN_LIKE_RESIDUES,
    _accepted_receptor_coordinate_patterns,
    _coordinate_record_counts,
    _expected_receptor_archive_member_examples,
    _input_artifact_sha256,
    _matches_target_receptor_coordinate,
    _read_coordinate_artifact_text,
)
from tools.product.build_refine_tier_public_benchmark_statistical_support_candidate_queue import (
    DEFAULT_OUT_JSON as DEFAULT_CANDIDATE_QUEUE_JSON,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.json"
DEFAULT_OUT_INTAKE_CSV = "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.csv"
DEFAULT_OUT_VALIDATION_CSV = (
    "runs/refine_tier_public_benchmark_statistical_support_coordinate_validation_current.csv"
)
DEFAULT_OUT_MD = "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.md"

CLAIM_BOUNDARY = (
    "Refine-tier public-benchmark statistical-support coordinate intake only; it reads the local R9 "
    "statistical-support candidate queue and validates whether reviewed receptor/complex coordinate "
    "artifacts are already local. It does not download coordinates, extract archives, run docking or MD, "
    "compute metrics, write canonical intake, approve receipts, promote claims, upload, email, delete, "
    "commit, push, or mutate external state."
)

ZERO_COORDINATE_COUNTS = {
    "coordinate_atom_record_count": 0,
    "coordinate_pdb_atom_record_count": 0,
    "coordinate_pdb_hetatm_record_count": 0,
    "coordinate_mol2_atom_record_count": 0,
    "coordinate_macromolecule_atom_record_count": 0,
    "coordinate_distinct_residue_count": 0,
    "coordinate_protein_like_atom_record_count": 0,
    "coordinate_protein_like_residue_count": 0,
    "coordinate_model_record_count": 0,
}


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


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _path_present(reference: str, *, root: Path = ROOT) -> bool:
    reference = _text(reference)
    if not reference:
        return False
    if "::" in reference:
        archive_name, member_name = reference.split("::", 1)
        if not archive_name or not member_name:
            return False
        archive = _resolve(archive_name, root=root)
        if not archive.is_file():
            return False
        text, _kind, read_status = _read_coordinate_artifact_text(reference)
        return bool(text) and read_status == "read"
    return _resolve(reference, root=root).is_file()


def _first_path(value: Any) -> str:
    return next((part.strip() for part in _text(value).split(";") if part.strip()), "")


def _candidate_receptor_artifact(row: dict[str, Any], *, root: Path) -> str:
    current = _text(row.get("receptor_coordinate_artifact"))
    if current:
        return current
    return _first_path(row.get("suggested_local_coordinate_paths"))


def _intake_row(row: dict[str, Any], *, root: Path) -> dict[str, Any]:
    target_id = _text(row.get("target_id")).lower()
    artifact = _candidate_receptor_artifact(row, root=root)
    present = _path_present(artifact, root=root)
    blockers = [] if present else ["receptor_coordinate_artifact_missing"]
    return {
        "candidate_queue_id": _text(row.get("candidate_queue_id")),
        "expansion_slot_id": _text(row.get("expansion_slot_id")),
        "suggested_work_order_id": _text(row.get("suggested_work_order_id")),
        "target_id": target_id,
        "pose_id": _text(row.get("pose_id")),
        "required_split": _text(row.get("required_split")),
        "suggested_split": _text(row.get("suggested_split")),
        "ligand_pose_artifact": _text(row.get("ligand_pose_artifact")),
        "ligand_pose_artifact_present": _bool(row.get("ligand_pose_artifact_present")),
        "current_receptor_coordinate_artifact": artifact,
        "receptor_coordinate_artifact_present": present,
        "accepted_offline_coordinate_patterns": _accepted_receptor_coordinate_patterns(target_id),
        "expected_archive_member_examples": (
            _text(row.get("expected_archive_member_examples"))
            or _expected_receptor_archive_member_examples(target_id)
        ),
        "suggested_public_coordinate_urls": _text(row.get("suggested_public_coordinate_urls")),
        "suggested_local_coordinate_paths": _text(row.get("suggested_local_coordinate_paths")),
        "operator_coordinate_source_review_required": (
            "confirm_public_coordinate_source_license_and_native_receptor_or_complex_chain_assembly_matches_pose_target"
            if target_id
            else ""
        ),
        "coordinate_intake_status": "coordinate_artifact_local" if present else "blocked_coordinate_artifact_missing",
        "coordinate_intake_blockers": ";".join(blockers),
        "next_operator_action": (
            "validate_coordinate_artifact_then_materialize_metric_sources"
            if present
            else "place_reviewed_public_receptor_or_complex_coordinate_for_statistical_support_candidate"
        ),
        "canonical_intake_promotion_allowed": False,
        "external_state_mutated": False,
    }


def _validation_row(row: dict[str, Any], *, root: Path) -> dict[str, Any]:
    target_id = _text(row.get("target_id")).lower()
    pose_id = _text(row.get("pose_id"))
    artifact = _text(row.get("current_receptor_coordinate_artifact"))
    present = _bool(row.get("receptor_coordinate_artifact_present"))
    text, source_kind, read_status = _read_coordinate_artifact_text(artifact)
    counts = _coordinate_record_counts(text) if present and read_status == "read" else dict(ZERO_COORDINATE_COUNTS)
    blockers: list[str] = []
    if not present:
        blockers.append("receptor_coordinate_missing")
        parse_status = "missing"
        source_kind = "missing"
    elif read_status != "read":
        blockers.append(f"receptor_coordinate_{read_status}")
        parse_status = read_status
    else:
        parse_status = "parsed_coordinate_records"
        candidate_name = artifact.split("::", 1)[1] if "::" in artifact else artifact
        if not _matches_target_receptor_coordinate(candidate_name, target_id):
            blockers.append("receptor_coordinate_target_mismatch")
        if counts["coordinate_atom_record_count"] < MIN_RECEPTOR_COORDINATE_ATOM_RECORDS:
            blockers.append("receptor_coordinate_atom_record_count_below_min")
        if (
            counts["coordinate_macromolecule_atom_record_count"]
            < MIN_RECEPTOR_COORDINATE_MACROMOLECULE_ATOM_RECORDS
            or counts["coordinate_distinct_residue_count"] < MIN_RECEPTOR_COORDINATE_DISTINCT_RESIDUES
        ):
            blockers.append("receptor_coordinate_macromolecule_record_count_below_min")
        if counts["coordinate_protein_like_residue_count"] < MIN_RECEPTOR_COORDINATE_PROTEIN_LIKE_RESIDUES:
            blockers.append("receptor_coordinate_protein_like_residue_count_below_min")
    validation_status = "pass" if not blockers else "blocked"
    return {
        "candidate_queue_id": _text(row.get("candidate_queue_id")),
        "expansion_slot_id": _text(row.get("expansion_slot_id")),
        "suggested_work_order_id": _text(row.get("suggested_work_order_id")),
        "target_id": target_id,
        "pose_id": pose_id,
        "receptor_coordinate_artifact": artifact,
        "receptor_coordinate_artifact_present": present,
        "receptor_coordinate_artifact_sha256": _input_artifact_sha256(artifact) if present else "",
        "coordinate_source_kind": source_kind,
        "coordinate_parse_status": parse_status,
        **counts,
        "coordinate_validation_status": validation_status,
        "blockers": ";".join(blockers),
        "next_required_science_input": (
            "none" if validation_status == "pass" else "validated_native_receptor_or_complex_coordinate"
        ),
        "canonical_intake_promotion_allowed": False,
        "external_state_mutated": False,
    }


def build_refine_tier_public_benchmark_statistical_support_coordinate_intake(
    *,
    candidate_queue_json: str | Path = DEFAULT_CANDIDATE_QUEUE_JSON,
    root: Path = ROOT,
) -> dict[str, Any]:
    candidate_payload, candidate_present = _read_json(candidate_queue_json, root=root)
    candidate_summary = _summary(candidate_payload)
    candidate_rows = _rows(candidate_payload)
    intake_rows = [_intake_row(row, root=root) for row in candidate_rows]
    validation_rows = [_validation_row(row, root=root) for row in intake_rows]
    blockers: list[str] = []
    if not candidate_present:
        blockers.append("candidate_queue_missing")
    if candidate_summary.get("status") != "refine_tier_public_benchmark_statistical_support_candidate_queue_ready":
        blockers.append("candidate_queue_not_ready")

    artifact_present_count = sum(1 for row in intake_rows if row["receptor_coordinate_artifact_present"] is True)
    validation_pass_count = sum(
        1 for row in validation_rows if row["coordinate_validation_status"] == "pass"
    )
    ligand_present_count = sum(1 for row in intake_rows if row["ligand_pose_artifact_present"] is True)
    suggested_public_url_count = sum(
        1 for row in intake_rows if _text(row.get("suggested_public_coordinate_urls"))
    )
    suggested_local_path_count = sum(
        1 for row in intake_rows if _text(row.get("suggested_local_coordinate_paths"))
    )
    operator_review_count = sum(
        1 for row in intake_rows if _text(row.get("operator_coordinate_source_review_required"))
    )
    coordinate_intake_ready = bool(candidate_present and not blockers and candidate_rows)
    summary = {
        "packet_type": "refine_tier_public_benchmark_statistical_support_coordinate_intake",
        "status": (
            "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready"
            if coordinate_intake_ready
            else "blocked_refine_tier_public_benchmark_statistical_support_coordinate_intake"
        ),
        "coordinate_intake_ready": coordinate_intake_ready,
        "candidate_queue": _display(candidate_queue_json, root=root),
        "candidate_queue_present": candidate_present,
        "candidate_queue_ready": bool(
            candidate_summary.get("status")
            == "refine_tier_public_benchmark_statistical_support_candidate_queue_ready"
        ),
        "candidate_queue_selected_candidate_count": int(
            candidate_summary.get("selected_candidate_count") or len(candidate_rows)
        ),
        "coordinate_intake_row_count": len(intake_rows),
        "coordinate_intake_artifact_present_row_count": artifact_present_count,
        "coordinate_intake_missing_row_count": len(intake_rows) - artifact_present_count,
        "coordinate_intake_suggested_public_url_row_count": suggested_public_url_count,
        "coordinate_intake_suggested_local_path_row_count": suggested_local_path_count,
        "coordinate_intake_operator_review_required_row_count": operator_review_count,
        "coordinate_validation_row_count": len(validation_rows),
        "coordinate_validation_pass_row_count": validation_pass_count,
        "coordinate_validation_blocked_row_count": len(validation_rows) - validation_pass_count,
        "coordinate_validation_missing_row_count": sum(
            1
            for row in validation_rows
            if "receptor_coordinate_missing" in _text(row.get("blockers")).split(";")
        ),
        "coordinate_validation_below_min_atom_row_count": sum(
            1
            for row in validation_rows
            if "receptor_coordinate_atom_record_count_below_min" in _text(row.get("blockers")).split(";")
        ),
        "coordinate_validation_below_min_macromolecule_row_count": sum(
            1
            for row in validation_rows
            if "receptor_coordinate_macromolecule_record_count_below_min" in _text(row.get("blockers")).split(";")
        ),
        "coordinate_validation_below_min_protein_like_row_count": sum(
            1
            for row in validation_rows
            if "receptor_coordinate_protein_like_residue_count_below_min" in _text(row.get("blockers")).split(";")
        ),
        "coordinate_validation_min_atom_records": MIN_RECEPTOR_COORDINATE_ATOM_RECORDS,
        "coordinate_validation_min_macromolecule_atom_records": (
            MIN_RECEPTOR_COORDINATE_MACROMOLECULE_ATOM_RECORDS
        ),
        "coordinate_validation_min_distinct_residues": MIN_RECEPTOR_COORDINATE_DISTINCT_RESIDUES,
        "coordinate_validation_min_protein_like_residues": MIN_RECEPTOR_COORDINATE_PROTEIN_LIKE_RESIDUES,
        "ligand_pose_artifact_present_count": ligand_present_count,
        "experimental_deltaG_prefilled_count": int(
            candidate_summary.get("experimental_deltaG_prefilled_count") or 0
        ),
        "candidate_ready_for_metric_materialization_count": validation_pass_count,
        "candidate_ready_for_canonical_intake_count": 0,
        "canonical_intake_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Place and review receptor/complex coordinate artifacts for the 17 selected "
            "statistical-support candidates, then rerun coordinate validation before metric "
            "source materialization or claim receipt promotion."
        ),
    }
    return {"summary": summary, "intake_rows": intake_rows, "validation_rows": validation_rows}


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
                "# R9 Statistical Support Coordinate Intake",
                "",
                f"- status: `{summary['status']}`",
                f"- coordinate_intake_row_count: `{summary['coordinate_intake_row_count']}`",
                f"- coordinate_intake_missing_row_count: `{summary['coordinate_intake_missing_row_count']}`",
                f"- coordinate_validation_pass_row_count: `{summary['coordinate_validation_pass_row_count']}`",
                f"- coordinate_validation_blocked_row_count: `{summary['coordinate_validation_blocked_row_count']}`",
                f"- candidate_ready_for_metric_materialization_count: "
                f"`{summary['candidate_ready_for_metric_materialization_count']}`",
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
        description="Build coordinate intake/validation for R9 statistical-support candidates."
    )
    parser.add_argument("--candidate-queue-json", default=DEFAULT_CANDIDATE_QUEUE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-intake-csv", default=DEFAULT_OUT_INTAKE_CSV)
    parser.add_argument("--out-validation-csv", default=DEFAULT_OUT_VALIDATION_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_refine_tier_public_benchmark_statistical_support_coordinate_intake(
        candidate_queue_json=args.candidate_queue_json
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_intake_csv), payload["intake_rows"])
    write_csv_rows(_resolve(args.out_validation_csv), payload["validation_rows"])
    _write_md(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
