from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_engine_refinement_claim_evidence_operator_field_worksheet as mod
from tools.product.build_engine_refinement_claim_evidence_receipt import (
    APPROVAL_TOKEN,
    EXPECTED_EVIDENCE,
    REQUIRED_BLOCKERS,
    REQUIRED_COLUMNS,
)
from tools.product.build_refine_tier_public_benchmark_readiness import WORK_ORDER_COLUMNS
from tools.product.build_refine_tier_public_benchmark_readiness import METRIC_EVIDENCE_COLUMNS
from tools.product.build_refine_tier_public_benchmark_readiness import RECEPTOR_COORDINATE_INTAKE_COLUMNS
from tools.product.build_refine_tier_public_benchmark_readiness import RECEPTOR_COORDINATE_VALIDATION_COLUMNS


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def _receipt_rows(*, filled: bool = False) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for blocker_id in REQUIRED_BLOCKERS:
        expected = EXPECTED_EVIDENCE[blocker_id]
        row = {
            "blocker_id": blocker_id,
            "evidence_artifact": "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
            "evidence_status": str(expected["status"]),
            "claim_ready": "OPERATOR_CONFIRM_TRUE",
            "reviewer": "OPERATOR_FILL_REVIEWER",
            "reviewed_at_utc": "OPERATOR_FILL_REVIEWED_AT_UTC",
            "provenance_kind": "operator_curated_public",
            "license_ok": "OPERATOR_CONFIRM_TRUE",
            "external_engine_calls": "0",
            "approval_token": "OPERATOR_FILL_APPROVAL_TOKEN",
            "operator_attestation": "reviewed_for_claim_promotion",
            "notes": "pending",
        }
        if filled:
            row.update(
                {
                    "evidence_artifact": f"runs/evidence/{blocker_id}.json",
                    "claim_ready": "true",
                    "reviewer": "operator",
                    "reviewed_at_utc": "2026-06-13T00:00:00Z",
                    "license_ok": "true",
                    "approval_token": APPROVAL_TOKEN,
                }
            )
        rows.append(row)
    return rows


def _receipt_packet(*, ready: bool = False) -> dict:
    rows = []
    for row in _receipt_rows(filled=ready):
        rows.append(
            {
                **row,
                "row_status": "pass" if ready else "blocked",
                "observed_evidence_status": row["evidence_status"] if ready else "missing",
                "missing_true_fields": "" if ready else "claim_grade_public_benchmark_ready",
            }
        )
    return {
        "summary": {
            "status": (
                "engine_refinement_claim_evidence_receipt_ready"
                if ready
                else "blocked_engine_refinement_claim_evidence_receipt"
            ),
            "claim_promotion_evidence_receipt_ready": ready,
            "external_state_mutated": False,
        },
        "rows": rows,
    }


def _priority_packet(*, ready: bool = False) -> dict:
    return {
        "summary": {
            "status": (
                "engine_refinement_claim_evidence_priority_packet_ready"
                if ready
                else "blocked_engine_refinement_claim_evidence_priority_packet"
            ),
            "top_blocker_id": "public_benchmark_gate_not_ready",
            "top_priority_bucket": (
                "claim_receipt_attestation_required"
                if ready
                else "public_benchmark_work_order_apply_required"
            ),
            "top_required_input": "runs/refine_tier_public_benchmark_work_order_current.csv",
            "top_acceptance_artifact": "runs/refine_tier_public_benchmark_readiness_current.json",
            "top_next_operator_step": "Fill and validate 8 public benchmark work-order rows.",
            "top_verification_command": "python3 tools/product/apply_refine_tier_public_benchmark_work_order.py",
            "external_state_mutated": False,
        }
    }


def _work_order_rows(*, filled: bool = False) -> list[dict[str, str]]:
    rows = []
    for index in range(1, 9):
        row = {
            "work_order_id": f"refine_tier_public_benchmark_fill_{index:03d}",
            "target_input_csv": "config/refine_tier_public_benchmark_intake_current.csv",
            "template_row_index": str(index),
            "benchmark_id": f"OPERATOR_FILL_PUBLIC_BENCHMARK_{index:03d}",
            "target_id": "OPERATOR_FILL_TARGET_OR_COMPLEX_ID",
            "benchmark_family": "pdbbind_or_casf_refine_tier_public",
            "split": "fit" if index <= 5 else "holdout",
            "provenance_kind": "operator_curated_public",
            "provenance_id": "OPERATOR_FILL_PUBLIC_SOURCE_ID",
            "license_ok": "OPERATOR_CONFIRM_TRUE",
            "external_engine_calls": "0",
            "pose_rmsd_A": "OPERATOR_FILL_POSE_RMSD_A",
            "dockq": "OPERATOR_FILL_DOCKQ",
            "lddt_pli": "OPERATOR_FILL_LDDT_PLI",
            "deltaG_mm_gbsa_kcal_mol": "OPERATOR_FILL_INTERNAL_REFINE_DG",
            "dockq_source_artifact": "OPERATOR_FILL_DOCKQ_SOURCE_ARTIFACT",
            "lddt_pli_source_artifact": "OPERATOR_FILL_LDDT_PLI_SOURCE_ARTIFACT",
            "internal_deltaG_source_artifact": "OPERATOR_FILL_INTERNAL_DELTAG_SOURCE_ARTIFACT",
            "deltaG_experimental_kcal_mol": "OPERATOR_FILL_PUBLIC_EXPERIMENTAL_DG",
            "operator_action": "append_validated_public_benchmark_row",
            "acceptance_rule": "fill all required columns",
            "external_state_mutated": "False",
        }
        if filled:
            row.update(
                {
                    "benchmark_id": f"bench_{index:03d}",
                    "target_id": f"target_{index:03d}",
                    "provenance_id": f"PMID{index:08d}",
                    "license_ok": "true",
                    "pose_rmsd_A": "1.2",
                    "dockq": "0.4",
                    "lddt_pli": "0.7",
                    "deltaG_mm_gbsa_kcal_mol": "-8.1",
                    "dockq_source_artifact": f"runs/metric_sources/target_{index:03d}_dockq.json",
                    "lddt_pli_source_artifact": f"runs/metric_sources/target_{index:03d}_lddt_pli.json",
                    "internal_deltaG_source_artifact": f"runs/metric_sources/target_{index:03d}_internal_deltaG.json",
                    "deltaG_experimental_kcal_mol": "-7.9",
                }
            )
        rows.append(row)
    return rows


def _apply_packet(*, ready: bool = False) -> dict:
    rows = []
    for index, row in enumerate(_work_order_rows(filled=ready), start=1):
        rows.append(
            {
                **row,
                "row_index": index,
                "row_status": "pass" if ready else "blocked",
                "blockers": "" if ready else "operator_placeholders_unfilled",
            }
        )
    return {
        "summary": {
            "status": (
                "refine_tier_public_benchmark_work_order_apply_ready"
                if ready
                else "blocked_refine_tier_public_benchmark_work_order_apply"
            ),
            "apply_ready": ready,
            "blocked_row_count": 0 if ready else 8,
            "intake_written": False,
            "external_state_mutated": False,
        },
        "rows": rows,
    }


def _receptor_coordinate_intake_rows(work_order_rows: list[dict[str, str]], *, ready: bool) -> list[dict[str, str]]:
    rows = []
    for index, row in enumerate(work_order_rows, start=1):
        target_id = row["target_id"] if ready else f"pending_target_{index:03d}"
        rows.append(
            {
                "work_order_id": row["work_order_id"],
                "target_id": target_id,
                "pose_id": f"pose_{index:03d}",
                "current_receptor_coordinate_artifact": (
                    f"runs/receptor_coordinates/{target_id}.pdb" if ready else ""
                ),
                "receptor_coordinate_artifact_present": "true" if ready else "false",
                "accepted_offline_coordinate_patterns": (
                    f"{target_id}_protein.pdb;{target_id}_receptor.cif;{target_id}_complex.pdb"
                ),
                "expected_archive_member_examples": (
                    f"pdbbind/{target_id}/{target_id}_protein.pdb;"
                    f"pdbbind/{target_id}/{target_id}_receptor.cif;"
                    f"casf/{target_id}/{target_id}_complex.pdb"
                ),
                "suggested_public_coordinate_urls": (
                    f"https://files.rcsb.org/download/{target_id.upper()}.cif;"
                    f"https://files.rcsb.org/download/{target_id.upper()}.pdb"
                ),
                "suggested_local_coordinate_paths": (
                    f"data/public_benchmarks/pdbbind_casf_pose_affinity/{target_id}_protein.pdb;"
                    f"data/public_benchmarks/pdbbind_casf_pose_affinity/{target_id}/{target_id}_protein.pdb"
                ),
                "operator_coordinate_source_review_required": (
                    "confirm_public_coordinate_source_license_and_native_receptor_or_complex_chain_assembly_matches_pose_target"
                ),
                "next_operator_action": (
                    ""
                    if ready
                    else "place_reviewed_public_receptor_or_complex_coordinate_in_dataset_dir_or_tar_archive"
                ),
            }
        )
    return rows


def _receptor_coordinate_validation_rows(work_order_rows: list[dict[str, str]], *, ready: bool) -> list[dict[str, str]]:
    rows = []
    for index, row in enumerate(work_order_rows, start=1):
        target_id = row["target_id"] if ready else f"pending_target_{index:03d}"
        rows.append(
            {
                "work_order_id": row["work_order_id"],
                "target_id": target_id,
                "pose_id": f"pose_{index:03d}",
                "receptor_coordinate_artifact": (
                    f"runs/receptor_coordinates/{target_id}.pdb"
                    if ready
                    else "OPERATOR_FILL_RECEPTOR_COORDINATE_ARTIFACT"
                ),
                "receptor_coordinate_artifact_present": "true" if ready else "false",
                "coordinate_source_kind": "public_pdb" if ready else "",
                "coordinate_parse_status": "parsed" if ready else "missing",
                "coordinate_atom_record_count": "2400" if ready else "0",
                "coordinate_pdb_atom_record_count": "2400" if ready else "0",
                "coordinate_pdb_hetatm_record_count": "64" if ready else "0",
                "coordinate_mol2_atom_record_count": "0",
                "coordinate_macromolecule_atom_record_count": "2336" if ready else "0",
                "coordinate_distinct_residue_count": "280" if ready else "0",
                "coordinate_protein_like_atom_record_count": "2336" if ready else "0",
                "coordinate_protein_like_residue_count": "280" if ready else "0",
                "coordinate_model_record_count": "1" if ready else "0",
                "coordinate_validation_status": "pass" if ready else "blocked",
                "blockers": "" if ready else "receptor_coordinate_missing",
                "next_required_science_input": (
                    ""
                    if ready
                    else "validated_native_receptor_or_complex_coordinate"
                ),
            }
        )
    return rows


def _metric_evidence_rows(work_order_rows: list[dict[str, str]], *, ready: bool) -> list[dict[str, str]]:
    rows = []
    for index, row in enumerate(work_order_rows, start=1):
        rows.append(
            {
                "work_order_id": row["work_order_id"],
                "target_id": row["target_id"] if ready else f"pending_target_{index:03d}",
                "pose_id": f"pose_{index:03d}",
                "dockq": row["dockq"] if ready else "OPERATOR_FILL_DOCKQ",
                "lddt_pli": row["lddt_pli"] if ready else "OPERATOR_FILL_LDDT_PLI",
                "deltaG_mm_gbsa_kcal_mol": (
                    row["deltaG_mm_gbsa_kcal_mol"] if ready else "OPERATOR_FILL_INTERNAL_REFINE_DG"
                ),
                "dockq_source_artifact": (
                    row["dockq_source_artifact"] if ready else "OPERATOR_FILL_DOCKQ_SOURCE_ARTIFACT"
                ),
                "lddt_pli_source_artifact": (
                    row["lddt_pli_source_artifact"] if ready else "OPERATOR_FILL_LDDT_PLI_SOURCE_ARTIFACT"
                ),
                "internal_deltaG_source_artifact": (
                    row["internal_deltaG_source_artifact"]
                    if ready
                    else "OPERATOR_FILL_INTERNAL_DELTAG_SOURCE_ARTIFACT"
                ),
                "expected_dockq_source_artifact": (
                    f"runs/refine_tier_public_benchmark_metric_sources/{row['work_order_id']}_dockq.json"
                ),
                "expected_lddt_pli_source_artifact": (
                    f"runs/refine_tier_public_benchmark_metric_sources/{row['work_order_id']}_lddt_pli.json"
                ),
                "expected_internal_deltaG_source_artifact": (
                    f"runs/refine_tier_public_benchmark_metric_sources/{row['work_order_id']}_internal_deltaG.json"
                ),
                "required_metric_input_artifacts": (
                    f"runs/metric_inputs/target_{index:03d}_ligand_pose.sdf;"
                    f"runs/receptor_coordinates/target_{index:03d}.pdb"
                    if ready
                    else f"runs/metric_inputs/pending_target_{index:03d}_ligand_pose.sdf"
                ),
                "required_metric_input_artifact_sha256s": (
                    f"fixture_ligand_pose_sha256_{index:03d};fixture_receptor_sha256_{index:03d}"
                    if ready
                    else f"fixture_ligand_pose_sha256_{index:03d}"
                ),
                "missing_required_metric_input_artifacts": (
                    "" if ready else "receptor_coordinate_artifact"
                ),
                "required_metric_source_payload_fields": (
                    "metric_name;target_id;pose_id;value;method;input_artifacts;"
                    "input_artifact_sha256s;operator_id;reviewed_at_utc;license_ok;external_engine_calls"
                ),
                "dockq_source_artifact_present": "true" if ready else "false",
                "lddt_pli_source_artifact_present": "true" if ready else "false",
                "internal_deltaG_source_artifact_present": "true" if ready else "false",
                "dockq_source_payload_valid": "true" if ready else "false",
                "lddt_pli_source_payload_valid": "true" if ready else "false",
                "internal_deltaG_source_payload_valid": "true" if ready else "false",
                "dockq_source_payload_blockers": "" if ready else "source_artifact_missing",
                "lddt_pli_source_payload_blockers": "" if ready else "source_artifact_missing",
                "internal_deltaG_source_payload_blockers": "" if ready else "source_artifact_missing",
                "metric_evidence_status": "pass" if ready else "blocked",
                "blockers": (
                    ""
                    if ready
                    else "dockq_source_artifact_missing;lddt_pli_source_artifact_missing;"
                    "internal_deltaG_source_artifact_missing"
                ),
                "next_required_science_input": (
                    ""
                    if ready
                    else "reviewed_metric_source_artifacts_for_pose_and_internal_deltaG"
                ),
                "metric_evidence_next_operator_action": (
                    "none"
                    if ready
                    else "place_reviewed_local_metric_evidence_artifacts_and_copy_paths_into_work_order"
                ),
            }
        )
    return rows


def _write_sources(tmp_path: Path, *, filled: bool = False) -> None:
    work_order_rows = _work_order_rows(filled=filled)
    _write_csv(tmp_path / mod.DEFAULT_RECEIPT_CSV, _receipt_rows(filled=filled), REQUIRED_COLUMNS)
    _write_json(tmp_path / mod.DEFAULT_RECEIPT_JSON, _receipt_packet(ready=filled))
    _write_json(tmp_path / mod.DEFAULT_PRIORITY_PACKET_JSON, _priority_packet(ready=filled))
    _write_json(
        tmp_path / mod.DEFAULT_PUBLIC_BENCHMARK_READINESS_JSON,
        {
            "summary": {
                "status": (
                    "refine_tier_public_benchmark_ready"
                    if filled
                    else "blocked_refine_tier_public_benchmark_readiness"
                ),
                "claim_grade_public_benchmark_ready": filled,
                "external_state_mutated": False,
            }
        },
    )
    _write_csv(
        tmp_path / mod.DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_CSV,
        work_order_rows,
        WORK_ORDER_COLUMNS,
    )
    _write_json(tmp_path / mod.DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON, _apply_packet(ready=filled))
    _write_csv(
        tmp_path / mod.DEFAULT_PUBLIC_BENCHMARK_RECEPTOR_COORDINATE_INTAKE_CSV,
        _receptor_coordinate_intake_rows(work_order_rows, ready=filled),
        RECEPTOR_COORDINATE_INTAKE_COLUMNS,
    )
    _write_csv(
        tmp_path / mod.DEFAULT_PUBLIC_BENCHMARK_RECEPTOR_COORDINATE_VALIDATION_CSV,
        _receptor_coordinate_validation_rows(work_order_rows, ready=filled),
        RECEPTOR_COORDINATE_VALIDATION_COLUMNS,
    )
    _write_csv(
        tmp_path / mod.DEFAULT_PUBLIC_BENCHMARK_METRIC_EVIDENCE_CSV,
        _metric_evidence_rows(work_order_rows, ready=filled),
        METRIC_EVIDENCE_COLUMNS,
    )


def test_engine_refinement_claim_evidence_operator_field_worksheet_flags_pending_fields(
    tmp_path: Path,
) -> None:
    _write_sources(tmp_path, filled=False)

    payload = mod.build_engine_refinement_claim_evidence_operator_field_worksheet(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "engine_refinement_claim_evidence_operator_field_worksheet_ready"
    assert summary["field_worksheet_ready"] is True
    assert summary["operator_fill_complete"] is False
    assert summary["worksheet_field_row_count"] == 168
    assert summary["required_receipt_field_count"] == 66
    assert summary["receipt_operator_fill_pending_field_count"] == 36
    assert summary["public_benchmark_work_order_field_count"] == 96
    assert summary["public_benchmark_work_order_pending_field_count"] == 96
    assert summary["public_benchmark_receptor_coordinate_intake_row_count"] == 8
    assert summary["public_benchmark_receptor_coordinate_intake_artifact_present_row_count"] == 0
    assert summary["public_benchmark_receptor_coordinate_intake_missing_work_order_row_count"] == 0
    assert summary["public_benchmark_receptor_coordinate_validation_row_count"] == 8
    assert summary["public_benchmark_receptor_coordinate_validation_blocked_row_count"] == 8
    assert summary["public_benchmark_receptor_coordinate_validation_missing_work_order_row_count"] == 0
    assert summary["public_benchmark_metric_evidence_row_count"] == 8
    assert summary["public_benchmark_metric_evidence_blocked_row_count"] == 8
    assert summary["public_benchmark_metric_evidence_missing_work_order_row_count"] == 0
    assert summary["public_benchmark_metric_evidence_missing_dockq_source_row_count"] == 8
    assert summary["public_benchmark_metric_evidence_missing_lddt_pli_source_row_count"] == 8
    assert summary["public_benchmark_metric_evidence_missing_internal_deltaG_source_row_count"] == 8
    assert summary["public_benchmark_metric_evidence_missing_required_input_artifact_row_count"] == 8
    assert summary["public_benchmark_metric_evidence_missing_required_input_artifact_sha256_row_count"] == 0
    assert summary["public_benchmark_metric_evidence_invalid_dockq_source_payload_row_count"] == 0
    assert summary["public_benchmark_metric_evidence_invalid_lddt_pli_source_payload_row_count"] == 0
    assert summary["public_benchmark_metric_evidence_invalid_internal_deltaG_source_payload_row_count"] == 0
    assert summary["public_benchmark_science_evidence_complete"] is False
    assert summary["public_benchmark_materialized_metric_ready"] is False
    assert summary["public_benchmark_materialized_apply_ready"] is False
    assert summary["public_benchmark_materialized_science_evidence_complete"] is False
    assert summary["public_benchmark_materialized_work_order_row_count"] == 0
    assert summary["operator_fill_pending_field_count"] == 132
    assert summary["top_blocker_id"] == "public_benchmark_gate_not_ready"
    assert summary["top_priority_bucket"] == "public_benchmark_work_order_apply_required"
    assert summary["top_blocker_pending_field_count"] == 102
    assert summary["public_benchmark_work_order_apply_blocked_row_count"] == 8
    assert summary["approval_token_required"] == APPROVAL_TOKEN
    assert summary["claim_promoted"] is False
    assert summary["external_engine_calls_executed"] is False
    assert summary["external_state_mutated"] is False
    dockq_source_row = next(
        row
        for row in payload["rows"]
        if row["source_row_id"] == "refine_tier_public_benchmark_fill_001"
        and row["field_name"] == "dockq_source_artifact"
    )
    assert dockq_source_row["receptor_coordinate_validation_status"] == "blocked"
    assert dockq_source_row["receptor_coordinate_validation_blockers"] == "receptor_coordinate_missing"
    assert "pending_target_001_protein.pdb" in dockq_source_row[
        "receptor_coordinate_accepted_offline_coordinate_patterns"
    ]
    assert "pdbbind/pending_target_001/pending_target_001_receptor.cif" in dockq_source_row[
        "receptor_coordinate_expected_archive_member_examples"
    ]
    assert dockq_source_row["receptor_coordinate_suggested_public_coordinate_urls"] == (
        "https://files.rcsb.org/download/PENDING_TARGET_001.cif;"
        "https://files.rcsb.org/download/PENDING_TARGET_001.pdb"
    )
    assert "pending_target_001_protein.pdb" in dockq_source_row[
        "receptor_coordinate_suggested_local_coordinate_paths"
    ]
    assert dockq_source_row["receptor_coordinate_operator_source_review_required"] == (
        "confirm_public_coordinate_source_license_and_native_receptor_or_complex_chain_assembly_matches_pose_target"
    )
    assert dockq_source_row["receptor_coordinate_intake_next_operator_action"] == (
        "place_reviewed_public_receptor_or_complex_coordinate_in_dataset_dir_or_tar_archive"
    )
    assert dockq_source_row["metric_evidence_status"] == "blocked"
    assert "dockq_source_artifact_missing" in dockq_source_row["metric_evidence_blockers"]
    assert dockq_source_row["metric_expected_dockq_source_artifact"] == (
        "runs/refine_tier_public_benchmark_metric_sources/"
        "refine_tier_public_benchmark_fill_001_dockq.json"
    )
    assert "reviewed_at_utc" in dockq_source_row["metric_required_source_payload_fields"]
    assert "input_artifact_sha256s" in dockq_source_row["metric_required_source_payload_fields"]
    assert dockq_source_row["metric_required_input_artifacts"] == (
        "runs/metric_inputs/pending_target_001_ligand_pose.sdf"
    )
    assert dockq_source_row["metric_required_input_artifact_sha256s"] == (
        "fixture_ligand_pose_sha256_001"
    )
    assert dockq_source_row["metric_missing_required_input_artifacts"] == (
        "receptor_coordinate_artifact"
    )
    assert dockq_source_row["metric_evidence_next_operator_action"] == (
        "place_reviewed_local_metric_evidence_artifacts_and_copy_paths_into_work_order"
    )
    assert dockq_source_row["metric_dockq_source_payload_valid"] is False
    assert dockq_source_row["metric_dockq_source_payload_blockers"] == "source_artifact_missing"
    assert dockq_source_row["metric_dockq_source_artifact_present"] is False


def test_engine_refinement_claim_evidence_operator_field_worksheet_can_be_fill_complete(
    tmp_path: Path,
) -> None:
    _write_sources(tmp_path, filled=True)

    payload = mod.build_engine_refinement_claim_evidence_operator_field_worksheet(root=tmp_path)
    summary = payload["summary"]

    assert summary["operator_fill_complete"] is True
    assert summary["operator_fill_pending_field_count"] == 0
    assert summary["invalid_field_count"] == 0
    assert summary["public_benchmark_gate_ready"] is True
    assert summary["public_benchmark_work_order_apply_ready"] is True
    assert summary["public_benchmark_materialized_science_evidence_complete"] is False
    assert summary["public_benchmark_receptor_coordinate_intake_artifact_present_row_count"] == 8
    assert summary["public_benchmark_receptor_coordinate_validation_pass_row_count"] == 8
    assert summary["public_benchmark_metric_evidence_pass_row_count"] == 8
    assert summary["public_benchmark_metric_evidence_missing_required_input_artifact_row_count"] == 0
    assert summary["public_benchmark_metric_evidence_missing_required_input_artifact_sha256_row_count"] == 0
    assert summary["public_benchmark_science_evidence_complete"] is True
    assert all(row["operator_input_required"] is False for row in payload["rows"])
    work_order_rows = [
        row for row in payload["rows"] if row["worksheet_section"] == "public_benchmark_work_order"
    ]
    assert all(row["receptor_coordinate_validation_status"] == "pass" for row in work_order_rows)
    assert all(row["metric_evidence_status"] == "pass" for row in work_order_rows)


def test_engine_refinement_claim_evidence_operator_field_worksheet_surfaces_current_materialized_candidate() -> None:
    payload = mod.build_engine_refinement_claim_evidence_operator_field_worksheet()
    summary = payload["summary"]

    assert summary["public_benchmark_science_evidence_complete"] is False
    assert summary["public_benchmark_materialized_metric_ready"] is True
    assert summary["public_benchmark_materialized_apply_ready"] is True
    assert summary["public_benchmark_materialized_science_evidence_complete"] is True
    assert summary["public_benchmark_materialized_work_order_row_count"] == 8
    assert summary["public_benchmark_materialized_metric_evidence_pass_row_count"] == 8
    assert summary["public_benchmark_materialized_metric_evidence_blocked_row_count"] == 0
    assert summary["public_benchmark_materialized_free_energy_pair_count"] == 8
    assert summary["public_benchmark_materialized_free_energy_spearman"] == 0.6190476190476191
    assert summary["public_benchmark_materialized_free_energy_spearman_gate_ready"] is True
    assert summary["public_benchmark_materialized_free_energy_spearman_bootstrap_p05"] == -0.14285714285714285
    assert summary["public_benchmark_materialized_claim_grade_statistical_support_ready"] is False
    assert summary["public_benchmark_materialized_claim_grade_statistical_support_blocker_count"] == 3
    assert summary["public_benchmark_statistical_support_work_order_artifact_present"] is True
    assert summary["public_benchmark_statistical_support_work_order_ready"] is True
    assert summary["public_benchmark_statistical_support_work_order_status"] == (
        "refine_tier_public_benchmark_statistical_support_work_order_ready"
    )
    assert summary["public_benchmark_statistical_support_work_order_expansion_slot_count"] == 17
    assert summary["public_benchmark_statistical_support_work_order_minimum_new_pair_count"] == 17
    assert summary["public_benchmark_statistical_support_work_order_minimum_new_holdout_pair_count"] == 5
    assert summary["public_benchmark_statistical_support_work_order_minimum_new_fit_or_holdout_pair_count"] == 12
    assert summary["public_benchmark_statistical_support_work_order_bootstrap_spearman_p05_deficit"] == (
        0.6428571428571428
    )
    assert summary["public_benchmark_statistical_support_work_order_bootstrap_retest_required"] is True
    assert (
        summary["public_benchmark_statistical_support_work_order_canonical_intake_promotion_allowed"]
        is False
    )
    assert summary["public_benchmark_statistical_support_metric_materialization_readiness_artifact_present"] is True
    assert summary["public_benchmark_statistical_support_metric_materialization_readiness_ready"] is True
    assert summary["public_benchmark_statistical_support_metric_materialization_status"] == (
        "refine_tier_public_benchmark_statistical_support_metric_materialization_readiness_ready"
    )
    assert summary["public_benchmark_statistical_support_metric_materialization_row_count"] == 17
    assert summary["public_benchmark_statistical_support_metric_materialization_candidate_ready_count"] == 0
    assert summary["public_benchmark_statistical_support_metric_materialization_candidate_blocked_count"] == 17
    assert summary["public_benchmark_statistical_support_metric_materialization_input_artifact_contract_ready"] is False
    assert summary["public_benchmark_statistical_support_metric_materialization_required_input_artifact_count"] == 34
    assert summary["public_benchmark_statistical_support_metric_materialization_present_required_input_artifact_count"] == 17
    assert summary["public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_count"] == 17
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_missing_required_input_artifact_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_coordinate_validation_pass_row_count"
        ]
        == 0
    )
    assert (
        summary[
            "public_benchmark_statistical_support_metric_materialization_coordinate_validation_blocked_row_count"
        ]
        == 17
    )
    assert summary[
        "public_benchmark_statistical_support_metric_materialization_planned_metric_source_payload_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_metric_materialization_existing_metric_source_payload_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_metric_materialization_required_metric_source_payloads"
    ] == "dockq;lddt_pli;internal_deltaG"
    assert summary[
        "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_field_count"
    ] == 11
    assert summary[
        "public_benchmark_statistical_support_metric_materialization_required_metric_source_payload_fields"
    ] == (
        "metric_name;target_id;pose_id;value;method;input_artifacts;input_artifact_sha256s;"
        "operator_id;reviewed_at_utc;license_ok;external_engine_calls"
    )
    assert summary["public_benchmark_statistical_support_coordinate_intake_artifact_present"] is True
    assert summary["public_benchmark_statistical_support_coordinate_intake_ready"] is True
    assert summary["public_benchmark_statistical_support_coordinate_intake_status"] == (
        "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready"
    )
    assert summary["public_benchmark_statistical_support_coordinate_intake_row_count"] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_artifact_present_row_count"
    ] == 0
    assert summary["public_benchmark_statistical_support_coordinate_intake_missing_row_count"] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count"
    ] == 136
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_expected_archive_member_example_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_pass_row_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_blocked_row_count"
    ] == 17
    assert (
        mod.DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_INTAKE_JSON
        in summary["source_artifacts"]
    )
    assert summary[
        "public_benchmark_statistical_support_metric_source_templates_artifact_present"
    ] is True
    assert summary["public_benchmark_statistical_support_metric_source_templates_ready"] is True
    assert summary["public_benchmark_statistical_support_metric_source_templates_status"] == (
        "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
    )
    assert summary["public_benchmark_statistical_support_metric_source_templates_template_row_count"] == 51
    assert summary[
        "public_benchmark_statistical_support_metric_source_templates_template_candidate_row_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_metric_source_templates_template_metric_name_count"
    ] == 3
    assert summary[
        "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_metric_source_templates_existing_metric_source_payload_present_row_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_metric_source_templates_external_engine_calls_total"
    ] == 0
    assert (
        mod.DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_TEMPLATES_JSON
        in summary["source_artifacts"]
    )
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_artifact_present"
    ] is True
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready"
    ] is False
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_status"
    ] == (
        "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
    )
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_template_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_pass_row_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approved_payload_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_blocked_payload_row_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_required"
    ] is True
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count"
    ] == 51
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_payload_write_allowed"
    ] is False
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_template_id"
    ] == "r9_statistical_support_metric_source_template_001"
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_metric_name"
    ] == "dockq"
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_most_common_row_blocker"
    ] == "operator_placeholders_unfilled"
    assert summary[
        "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required"
    ] == "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
    assert (
        mod.DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOAD_OPERATOR_RECEIPT_JSON
        in summary["source_artifacts"]
    )
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_r4_preflight_artifact_present"
    ] is True
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"] is True
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_preflight_status"] == (
        "refine_tier_public_benchmark_statistical_support_coordinate_fetch_r4_preflight_ready"
    )
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_row_count"] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_r4_ready_for_review_row_count"
    ] == 17
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_blocked_row_count"] == 0
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_r4_fetch_required_row_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_r4_metric_materialization_blocked_row_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_r4_planned_metric_source_payload_count"
    ] == 51
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_download_executed"] is False
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_external_state_mutated"] is False
    assert summary["public_benchmark_statistical_support_coordinate_fetch_r4_approval_token_required"] == (
        "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
    )
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_artifact_present"
    ] is True
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready"
    ] is False
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_status"
    ] == (
        "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt"
    )
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_required_r4_review_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_pass_row_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approved_fetch_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_required"
    ] is True
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count"
    ] == 17
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count"
    ] == 0
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_authorized_for_external_download"
    ] is False
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_download_executed"
    ] is False
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_review_id"
    ] == "r9_statistical_support_coordinate_fetch_001"
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_target_id"
    ] == "4ivc"
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_pose_id"
    ] == "4ivc_20"
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_most_common_row_blocker"
    ] == "operator_placeholders_unfilled"
    assert summary[
        "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required"
    ] == "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
    assert (
        mod.DEFAULT_PUBLIC_BENCHMARK_STATISTICAL_SUPPORT_COORDINATE_FETCH_OPERATOR_RECEIPT_JSON
        in summary["source_artifacts"]
    )
    assert "required_input_artifacts=34/17/17" in summary["next_required_step"]
    assert "local_coordinate_path_candidates=136" in summary["next_required_step"]
    assert "local_coordinate_present_targets=0" in summary["next_required_step"]
    assert "local_coordinate_missing_targets=17" in summary["next_required_step"]
    assert "r4_ready_for_review_row_count=17" in summary["next_required_step"]
    assert "fill/approve the 17-row coordinate fetch operator receipt" in summary["next_required_step"]
    assert "fill/approve the 51-row metric payload operator receipt" in summary["next_required_step"]
    assert "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS" in summary["next_required_step"]
    assert "approval_token_required=APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD" in summary[
        "next_required_step"
    ]
    assert "required_input_artifacts=34/17/17" in summary["top_next_operator_step"]
    assert "local_coordinate_path_candidates=136" in summary["top_next_operator_step"]
    assert summary["worksheet_field_row_count"] == 389
    assert summary["operator_fill_pending_field_count"] == 296
    assert summary["top_blocker_field_count"] == 329
    assert summary["top_blocker_pending_field_count"] == 266
    assert summary["public_benchmark_statistical_support_expansion_slot_row_count"] == 17
    assert summary["public_benchmark_statistical_support_expansion_holdout_slot_count"] == 5
    assert summary["public_benchmark_statistical_support_expansion_fit_or_holdout_slot_count"] == 12
    assert summary["public_benchmark_statistical_support_expansion_field_count"] == 221
    assert summary["public_benchmark_statistical_support_expansion_pending_field_count"] == 204
    assert summary["public_benchmark_statistical_support_expansion_ready_field_count"] == 17
    holdout_split_row = next(
        row
        for row in payload["rows"]
        if row["source_row_id"] == "refine_tier_public_benchmark_stat_support_expansion_001"
        and row["field_name"] == "split"
    )
    assert holdout_split_row["worksheet_section"] == "public_benchmark_statistical_support_expansion"
    assert holdout_split_row["current_value"] == "holdout"
    assert holdout_split_row["field_status"] == "ready"
    assert holdout_split_row["required_holdout_pair_count_credit"] == 1
    assert holdout_split_row["operator_input_required"] is False
    holdout_benchmark_row = next(
        row
        for row in payload["rows"]
        if row["source_row_id"] == "refine_tier_public_benchmark_stat_support_expansion_001"
        and row["field_name"] == "benchmark_id"
    )
    assert holdout_benchmark_row["field_status"] == "operator_fill_pending"
    assert holdout_benchmark_row["required_split"] == "holdout"
    assert (
        holdout_benchmark_row["expected_true_fields"]
        == "claim_grade_public_benchmark_statistical_support_ready"
    )
    fit_or_holdout_split_row = next(
        row
        for row in payload["rows"]
        if row["source_row_id"] == "refine_tier_public_benchmark_stat_support_expansion_006"
        and row["field_name"] == "split"
    )
    assert fit_or_holdout_split_row["current_value"] == "fit_or_holdout"
    assert fit_or_holdout_split_row["field_status"] == "ready"
    assert fit_or_holdout_split_row["required_holdout_pair_count_credit"] == 0
    assert "Review the R4 coordinate-fetch preflight" in summary["next_required_step"]
    assert "planned_metric_source_payload_count=51" in summary["next_required_step"]


def test_engine_refinement_claim_evidence_operator_field_worksheet_cli_writes_outputs(
    tmp_path: Path,
) -> None:
    _write_sources(tmp_path, filled=False)
    out_json = tmp_path / "worksheet.json"
    out_csv = tmp_path / "worksheet.csv"
    out_md = tmp_path / "worksheet.md"

    mod.main(
        [
            "--root",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "engine_refinement_claim_evidence_operator_field_worksheet_ready"
    assert "worksheet_section" in out_csv.read_text(encoding="utf-8")
    assert "Engine Refinement Claim Evidence Operator Field Worksheet" in out_md.read_text(
        encoding="utf-8"
    )
