from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from tools.product import build_engine_refinement_claim_evidence_operator_staging_apply as mod
from tools.product import build_refine_tier_public_benchmark_readiness as readiness
from tools.product.build_engine_refinement_claim_evidence_receipt import (
    APPROVAL_TOKEN,
    EXPECTED_EVIDENCE,
    REQUIRED_BLOCKERS,
    REQUIRED_COLUMNS,
)
from tools.product.build_refine_tier_public_benchmark_readiness import (
    METRIC_EVIDENCE_COLUMNS,
    REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN,
    RECEPTOR_COORDINATE_VALIDATION_COLUMNS,
    WORK_ORDER_COLUMNS,
)


def _pdb_atom_lines(count: int) -> str:
    return "".join(
        f"ATOM  {idx:5d}  CA  ALA A{idx:4d}    {float(idx):8.3f}{0.0:8.3f}{0.0:8.3f}  1.00  0.00           C\n"
        for idx in range(1, count + 1)
    )


def _metric_source_payload(
    metric_name: str,
    *,
    target_id: str,
    pose_id: str,
    value: object,
    input_artifacts: list[str],
) -> dict[str, object]:
    return {
        "metric_name": metric_name,
        "target_id": target_id,
        "pose_id": pose_id,
        "value": value,
        "method": "fixture_reviewed_local_metric",
        "input_artifacts": input_artifacts,
        "input_artifact_sha256s": [
            hashlib.sha256(Path(artifact).read_bytes()).hexdigest() for artifact in input_artifacts
        ],
        "operator_id": "fixture_operator",
        "reviewed_at_utc": "2026-06-14T00:00:00Z",
        "license_ok": True,
        "external_engine_calls": 0,
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def _action_board(path: Path) -> None:
    _write_csv(path, [{"blocker_id": blocker_id} for blocker_id in REQUIRED_BLOCKERS], ["blocker_id"])


def _receipt_rows(tmp_path: Path, *, filled: bool = False) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for blocker_id in REQUIRED_BLOCKERS:
        expected = EXPECTED_EVIDENCE[blocker_id]
        evidence_artifact = "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
        if filled:
            evidence_path = tmp_path / "runs" / "evidence" / f"{blocker_id}.json"
            _write_json(
                evidence_path,
                {
                    "summary": {
                        "status": expected["status"],
                        **{field: True for field in expected["true_fields"]},
                    }
                },
            )
            evidence_artifact = evidence_path.relative_to(tmp_path).as_posix()
        rows.append(
            {
                "blocker_id": blocker_id,
                "evidence_artifact": evidence_artifact,
                "evidence_status": expected["status"],
                "claim_ready": "true" if filled else "OPERATOR_CONFIRM_TRUE",
                "reviewer": "operator" if filled else "OPERATOR_FILL_REVIEWER",
                "reviewed_at_utc": "2026-06-13T00:00:00Z" if filled else "OPERATOR_FILL_REVIEWED_AT_UTC",
                "provenance_kind": "operator_curated_public",
                "license_ok": "true" if filled else "OPERATOR_CONFIRM_TRUE",
                "external_engine_calls": "0",
                "approval_token": APPROVAL_TOKEN if filled else "OPERATOR_FILL_APPROVAL_TOKEN",
                "operator_attestation": "reviewed_for_claim_promotion",
                "notes": "unit-test",
            }
        )
    return rows


def _work_order_rows(tmp_path: Path, *, filled: bool = False) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    metric_source_dir = tmp_path / "runs" / "metric_sources"
    metric_source_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, 9):
        row = {
            "work_order_id": f"refine_tier_public_benchmark_fill_{index:03d}",
            "target_input_csv": "",
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
            target_id = f"target_{index:03d}"
            pose_id = f"{target_id}_pose"
            dockq_source = metric_source_dir / f"target_{index:03d}_dockq.json"
            lddt_source = metric_source_dir / f"target_{index:03d}_lddt_pli.json"
            internal_delta_g_source = metric_source_dir / f"target_{index:03d}_internal_deltaG.json"
            input_artifact = metric_source_dir / f"{target_id}_{pose_id}_inputs.pdb"
            input_artifact.write_text(_pdb_atom_lines(40), encoding="utf-8")
            row["_fixture_metric_input_artifact"] = str(input_artifact)
            input_artifacts = [str(input_artifact)]
            row.update(
                {
                    "benchmark_id": f"bench_{index:03d}",
                    "target_id": target_id,
                    "provenance_id": f"PDBBind/CASF:{target_id}:{pose_id}",
                    "license_ok": "true",
                    "pose_rmsd_A": "1.2",
                    "dockq": "0.4",
                    "lddt_pli": "0.7",
                    "deltaG_mm_gbsa_kcal_mol": "-8.1",
                    "dockq_source_artifact": str(dockq_source),
                    "lddt_pli_source_artifact": str(lddt_source),
                    "internal_deltaG_source_artifact": str(internal_delta_g_source),
                    "deltaG_experimental_kcal_mol": "-7.9",
                }
            )
            _write_json(
                dockq_source,
                _metric_source_payload(
                    "dockq",
                    target_id=target_id,
                    pose_id=pose_id,
                    value=row["dockq"],
                    input_artifacts=input_artifacts,
                ),
            )
            _write_json(
                lddt_source,
                _metric_source_payload(
                    "lddt_pli",
                    target_id=target_id,
                    pose_id=pose_id,
                    value=row["lddt_pli"],
                    input_artifacts=input_artifacts,
                ),
            )
            _write_json(
                internal_delta_g_source,
                _metric_source_payload(
                    "internal_deltaG",
                    target_id=target_id,
                    pose_id=pose_id,
                    value=row["deltaG_mm_gbsa_kcal_mol"],
                    input_artifacts=input_artifacts,
                ),
            )
        rows.append(row)
    return rows


def _validation_rows(
    tmp_path: Path,
    work_order_rows: list[dict[str, object]],
    *,
    filled: bool = False,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in work_order_rows:
        pose_id = readiness._pose_id_from_work_order_row(row)
        receptor_artifact = tmp_path / "runs" / "receptors" / f"{row['target_id']}_{pose_id}_protein.pdb"
        if filled:
            receptor_artifact.parent.mkdir(parents=True, exist_ok=True)
            receptor_artifact.write_text(_pdb_atom_lines(40), encoding="utf-8")
            row["_fixture_receptor_coordinate_artifact"] = str(receptor_artifact)
        rows.append(
            {
                "work_order_id": row["work_order_id"],
                "target_id": row["target_id"],
                "pose_id": pose_id,
                "receptor_coordinate_artifact": str(receptor_artifact) if filled else "",
                "receptor_coordinate_artifact_present": filled,
                "receptor_coordinate_artifact_sha256": (
                    hashlib.sha256(receptor_artifact.read_bytes()).hexdigest()
                    if receptor_artifact.is_file()
                    else ""
                ),
                "coordinate_source_kind": "local_file" if filled else "missing",
                "coordinate_parse_status": "parsed_coordinate_records" if filled else "missing",
                "coordinate_atom_record_count": 40 if filled else 0,
                "coordinate_pdb_atom_record_count": 40 if filled else 0,
                "coordinate_pdb_hetatm_record_count": 0,
                "coordinate_mol2_atom_record_count": 0,
                "coordinate_macromolecule_atom_record_count": 40 if filled else 0,
                "coordinate_distinct_residue_count": 10 if filled else 0,
                "coordinate_protein_like_atom_record_count": 40 if filled else 0,
                "coordinate_protein_like_residue_count": 10 if filled else 0,
                "coordinate_model_record_count": 0,
                "coordinate_validation_status": "pass" if filled else "blocked",
                "blockers": "" if filled else "receptor_coordinate_missing",
                "next_required_science_input": (
                    "none" if filled else "validated_native_receptor_or_complex_coordinate"
                ),
            }
        )
    return rows


def _metric_evidence_rows(work_order_rows: list[dict[str, object]], *, filled: bool = False) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in work_order_rows:
        pose_id = readiness._pose_id_from_work_order_row(row)
        required_input_artifacts: list[str] = []
        if filled:
            required_input_artifacts = [
                str(row["_fixture_metric_input_artifact"]),
                str(row["_fixture_receptor_coordinate_artifact"]),
            ]
            for field, metric_name, value_field in [
                ("dockq_source_artifact", "dockq", "dockq"),
                ("lddt_pli_source_artifact", "lddt_pli", "lddt_pli"),
                ("internal_deltaG_source_artifact", "internal_deltaG", "deltaG_mm_gbsa_kcal_mol"),
            ]:
                _write_json(
                    Path(str(row[field])),
                    _metric_source_payload(
                        metric_name,
                        target_id=str(row["target_id"]),
                        pose_id=pose_id,
                        value=row[value_field],
                        input_artifacts=required_input_artifacts,
                    ),
                )
        required_input_hashes = [
            hashlib.sha256(Path(artifact).read_bytes()).hexdigest()
            if Path(artifact).is_file()
            else ""
            for artifact in required_input_artifacts
        ]
        rows.append(
            {
                "work_order_id": row["work_order_id"],
                "target_id": row["target_id"],
                "pose_id": pose_id,
                "dockq": row["dockq"],
                "lddt_pli": row["lddt_pli"],
                "deltaG_mm_gbsa_kcal_mol": row["deltaG_mm_gbsa_kcal_mol"],
                "dockq_source_artifact": row["dockq_source_artifact"],
                "lddt_pli_source_artifact": row["lddt_pli_source_artifact"],
                "internal_deltaG_source_artifact": row["internal_deltaG_source_artifact"],
                "required_metric_input_artifacts": ";".join(required_input_artifacts),
                "required_metric_input_artifact_sha256s": ";".join(required_input_hashes),
                "missing_required_metric_input_artifacts": (
                    "" if filled else "ligand_pose_artifact;receptor_coordinate_artifact"
                ),
                "required_metric_source_payload_fields": (
                    "metric_name;target_id;pose_id;value;method;input_artifacts;"
                    "input_artifact_sha256s;operator_id;reviewed_at_utc;license_ok;external_engine_calls"
                ),
                "dockq_source_artifact_present": filled,
                "lddt_pli_source_artifact_present": filled,
                "internal_deltaG_source_artifact_present": filled,
                "dockq_source_payload_valid": filled,
                "lddt_pli_source_payload_valid": filled,
                "internal_deltaG_source_payload_valid": filled,
                "dockq_source_payload_blockers": "" if filled else "source_artifact_missing",
                "lddt_pli_source_payload_blockers": "" if filled else "source_artifact_missing",
                "internal_deltaG_source_payload_blockers": "" if filled else "source_artifact_missing",
                "metric_evidence_status": "pass" if filled else "blocked",
                "blockers": "" if filled else "dockq_source_artifact_missing",
                "next_required_science_input": (
                    "none" if filled else "reviewed_local_metric_evidence_artifacts"
                ),
            }
        )
    return rows


def _worksheet(path: Path, *, filled: bool = False) -> None:
    _write_json(
        path,
        {
            "summary": {
                "status": "engine_refinement_claim_evidence_operator_field_worksheet_ready",
                "operator_fill_pending_field_count": 0 if filled else 132,
                "receipt_operator_fill_pending_field_count": 0 if filled else 36,
                "public_benchmark_work_order_pending_field_count": 0 if filled else 96,
                "top_blocker_id": "public_benchmark_gate_not_ready",
                "top_priority_bucket": "claim_receipt_attestation_required"
                if filled
                else "public_benchmark_work_order_apply_required",
                "top_blocker_pending_field_count": 0 if filled else 102,
                "public_benchmark_statistical_support_metric_source_templates_artifact": (
                    "runs/refine_tier_public_benchmark_statistical_support_metric_source_templates_current.json"
                ),
                "public_benchmark_statistical_support_metric_source_templates_artifact_present": True,
                "public_benchmark_statistical_support_metric_source_templates_ready": True,
                "public_benchmark_statistical_support_metric_source_templates_status": (
                    "refine_tier_public_benchmark_statistical_support_metric_source_templates_ready"
                ),
                "public_benchmark_statistical_support_metric_source_templates_template_row_count": 51,
                "public_benchmark_statistical_support_metric_source_templates_template_candidate_row_count": 17,
                "public_benchmark_statistical_support_metric_source_templates_template_metric_name_count": 3,
                "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count": 0,
                "public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count": 51,
                "public_benchmark_statistical_support_metric_source_templates_existing_metric_source_payload_present_row_count": 0,
                "public_benchmark_statistical_support_metric_source_templates_external_engine_calls_total": 0,
                "public_benchmark_statistical_support_coordinate_intake_artifact": (
                    "runs/refine_tier_public_benchmark_statistical_support_coordinate_intake_current.json"
                ),
                "public_benchmark_statistical_support_coordinate_intake_artifact_present": True,
                "public_benchmark_statistical_support_coordinate_intake_ready": True,
                "public_benchmark_statistical_support_coordinate_intake_status": (
                    "refine_tier_public_benchmark_statistical_support_coordinate_intake_ready"
                ),
                "public_benchmark_statistical_support_coordinate_intake_row_count": 17,
                "public_benchmark_statistical_support_coordinate_intake_artifact_present_row_count": 0,
                "public_benchmark_statistical_support_coordinate_intake_missing_row_count": 17,
                "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count": 136,
                "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_count": 0,
                "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count": 0,
                "public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count": 17,
                "public_benchmark_statistical_support_coordinate_intake_expected_archive_member_example_count": 51,
                "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_pass_row_count": 0,
                "public_benchmark_statistical_support_coordinate_intake_coordinate_validation_blocked_row_count": 17,
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_artifact": (
                    "runs/refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_current.json"
                ),
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_artifact_present": True,
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready": False,
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_status": (
                    "blocked_refine_tier_public_benchmark_statistical_support_coordinate_fetch_operator_receipt"
                ),
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count": 17,
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_required_r4_review_count": 17,
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_pass_row_count": 0,
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count": 17,
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approved_fetch_count": 0,
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_required": True,
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count": 17,
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count": 0,
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_authorized_for_external_download": False,
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_download_executed": False,
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_review_id": (
                    "r9_statistical_support_coordinate_fetch_001"
                ),
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_target_id": "4ivc",
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_first_blocked_pose_id": "4ivc_20",
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_most_common_row_blocker": (
                    "operator_placeholders_unfilled"
                ),
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required": (
                    "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
                ),
                "public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocker_count": 1,
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_artifact": (
                    "runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.json"
                ),
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_artifact_present": True,
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready": False,
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_status": (
                    "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt"
                ),
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count": 51,
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_required_template_count": 51,
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_pass_row_count": 0,
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count": 51,
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approved_payload_count": 0,
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_pass_payload_row_count": 0,
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_coordinate_validation_blocked_payload_row_count": 51,
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_required": True,
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count": 51,
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count": 0,
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_payload_write_allowed": False,
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_template_id": (
                    "r9_statistical_support_metric_source_template_001"
                ),
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_first_blocked_metric_name": "dockq",
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_most_common_row_blocker": (
                    "operator_placeholders_unfilled"
                ),
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required": (
                    "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
                ),
                "public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocker_count": 1,
            }
        },
    )


def _write_sources(tmp_path: Path, *, filled: bool = False) -> dict[str, Path]:
    receipt_csv = tmp_path / "config" / "engine_receipt.csv"
    action_board_csv = tmp_path / "runs" / "action_board.csv"
    work_order_csv = tmp_path / "runs" / "work_order.csv"
    validation_csv = tmp_path / "runs" / "refine_tier_public_benchmark_receptor_coordinate_validation_current.csv"
    metric_evidence_csv = tmp_path / "runs" / "refine_tier_public_benchmark_metric_evidence_current.csv"
    target_intake_csv = tmp_path / "config" / "target_intake.csv"
    worksheet_json = tmp_path / "runs" / "worksheet.json"
    existing_apply_json = tmp_path / "runs" / "refine_tier_public_benchmark_work_order_apply_current.json"
    _write_csv(receipt_csv, _receipt_rows(tmp_path, filled=filled), REQUIRED_COLUMNS)
    _action_board(action_board_csv)
    work_order_rows = _work_order_rows(tmp_path, filled=filled)
    _write_csv(work_order_csv, work_order_rows, WORK_ORDER_COLUMNS)
    _write_csv(
        validation_csv,
        _validation_rows(tmp_path, work_order_rows, filled=filled),
        RECEPTOR_COORDINATE_VALIDATION_COLUMNS,
    )
    _write_csv(metric_evidence_csv, _metric_evidence_rows(work_order_rows, filled=filled), METRIC_EVIDENCE_COLUMNS)
    _write_csv(target_intake_csv, [], WORK_ORDER_COLUMNS)
    _worksheet(worksheet_json, filled=filled)
    _write_json(
        existing_apply_json,
        {
            "summary": {
                "status": "refine_tier_public_benchmark_work_order_apply_ready"
                if filled
                else "blocked_refine_tier_public_benchmark_work_order_apply",
                "apply_ready": filled,
                "blocked_row_count": 0 if filled else 8,
            }
        },
    )
    return {
        "receipt_csv": receipt_csv,
        "action_board_csv": action_board_csv,
        "work_order_csv": work_order_csv,
        "validation_csv": validation_csv,
        "metric_evidence_csv": metric_evidence_csv,
        "target_intake_csv": target_intake_csv,
        "worksheet_json": worksheet_json,
    }


def test_blocks_placeholder_receipt_and_public_benchmark_work_order(tmp_path: Path) -> None:
    paths = _write_sources(tmp_path, filled=False)

    payload = mod.build_engine_refinement_claim_evidence_operator_staging_apply(
        staging_receipt_csv=paths["receipt_csv"],
        live_receipt_csv=paths["receipt_csv"],
        action_board_csv=paths["action_board_csv"],
        field_worksheet_json=paths["worksheet_json"],
        staging_public_benchmark_work_order_csv=paths["work_order_csv"],
        target_public_benchmark_intake_csv=paths["target_intake_csv"],
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_engine_refinement_claim_evidence_operator_staging_apply"
    assert summary["candidate_receipt_ready"] is False
    assert summary["candidate_receipt_blocked_row_count"] == 6
    assert summary["candidate_public_benchmark_work_order_ready"] is False
    assert summary["candidate_public_benchmark_blocked_row_count"] == 8
    assert summary["candidate_public_benchmark_receptor_coordinate_validation_contract_blocked_row_count"] == 8
    assert summary["candidate_public_benchmark_metric_evidence_contract_blocked_row_count"] == 8
    assert summary["candidate_public_benchmark_metric_evidence_missing_required_input_artifact_row_count"] == 8
    assert summary["candidate_public_benchmark_metric_evidence_missing_required_receptor_input_row_count"] == 0
    assert summary["candidate_public_benchmark_metric_evidence_required_input_sha256_blocked_row_count"] == 0
    assert summary["materialized_public_benchmark_metric_ready"] is False
    assert summary["materialized_public_benchmark_apply_ready"] is False
    assert summary["materialized_public_benchmark_candidate_ready"] is False
    assert summary["materialized_public_benchmark_work_order_row_count"] == 0
    assert summary["staging_receipt_placeholder_row_count"] == 6
    assert summary["staging_public_benchmark_work_order_placeholder_row_count"] == 8
    assert summary["field_worksheet_pending_field_count"] == 132
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_ready"
        ]
        is True
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count"
        ]
        == 51
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_ready_row_count"
        ]
        == 0
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count"
        ]
        == 51
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_intake_ready"
        ]
        is True
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_intake_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count"
        ]
        == 136
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count"
        ]
        == 0
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count"
        ]
        == 17
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready"
        ]
        is False
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count"
        ]
        == 17
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count"
        ]
        == 0
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required"
        ]
        == "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready"
        ]
        is False
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count"
        ]
        == 51
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count"
        ]
        == 51
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count"
        ]
        == 51
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count"
        ]
        == 0
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required"
        ]
        == "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
    )
    assert summary["live_copy_allowed"] is False
    assert summary["public_benchmark_intake_write_allowed"] is False
    assert summary["canonical_receipt_written"] is False
    assert summary["public_benchmark_intake_written"] is False
    assert summary["external_state_mutated"] is False
    assert "candidate_receipt_not_ready" in summary["blockers"]
    assert "candidate_public_benchmark_work_order_not_ready" in summary["blockers"]
    assert len(payload["rows"]) == 14


def test_writes_candidate_receipt_when_receipt_passes(tmp_path: Path) -> None:
    paths = _write_sources(tmp_path, filled=True)
    candidate_receipt_csv = tmp_path / "runs" / "candidate_receipt.csv"

    payload = mod.build_engine_refinement_claim_evidence_operator_staging_apply(
        staging_receipt_csv=paths["receipt_csv"],
        live_receipt_csv=paths["receipt_csv"],
        action_board_csv=paths["action_board_csv"],
        field_worksheet_json=paths["worksheet_json"],
        staging_public_benchmark_work_order_csv=paths["work_order_csv"],
        target_public_benchmark_intake_csv=paths["target_intake_csv"],
        candidate_receipt_csv=candidate_receipt_csv,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["candidate_receipt_ready"] is True
    assert summary["candidate_receipt_written"] is True
    assert candidate_receipt_csv.is_file()
    assert summary["candidate_public_benchmark_work_order_ready"] is True
    assert summary["candidate_public_benchmark_candidate_intake_written"] is True
    assert summary["candidate_public_benchmark_receptor_coordinate_validation_contract_blocked_row_count"] == 0
    assert summary["candidate_public_benchmark_metric_evidence_contract_blocked_row_count"] == 0
    assert summary["candidate_public_benchmark_metric_evidence_missing_required_input_artifact_row_count"] == 0
    assert summary["candidate_public_benchmark_metric_evidence_missing_required_receptor_input_row_count"] == 0
    assert summary["candidate_public_benchmark_metric_evidence_required_input_sha256_blocked_row_count"] == 0
    assert summary["materialized_public_benchmark_candidate_ready"] is False
    assert summary["canonical_receipt_written"] is False
    assert summary["public_benchmark_intake_written"] is False


def test_live_writes_require_matching_approval_tokens(tmp_path: Path) -> None:
    paths = _write_sources(tmp_path, filled=True)
    live_receipt_csv = tmp_path / "config" / "live_receipt.csv"
    target_intake_csv = tmp_path / "config" / "target_intake.csv"

    blocked = mod.build_engine_refinement_claim_evidence_operator_staging_apply(
        staging_receipt_csv=paths["receipt_csv"],
        live_receipt_csv=live_receipt_csv,
        action_board_csv=paths["action_board_csv"],
        field_worksheet_json=paths["worksheet_json"],
        staging_public_benchmark_work_order_csv=paths["work_order_csv"],
        target_public_benchmark_intake_csv=target_intake_csv,
        mode="live_apply",
        write_canonical_receipt=True,
        write_public_benchmark_intake=True,
        approval_token="WRONG",
        public_benchmark_approval_token="WRONG",
        root=tmp_path,
    )
    assert blocked["summary"]["canonical_receipt_written"] is False
    assert blocked["summary"]["public_benchmark_intake_written"] is False
    assert "write_canonical_receipt_approval_token_missing_or_invalid" in blocked["summary"]["blockers"]
    assert "write_public_benchmark_intake_approval_token_missing_or_invalid" in blocked["summary"]["blockers"]

    allowed = mod.build_engine_refinement_claim_evidence_operator_staging_apply(
        staging_receipt_csv=paths["receipt_csv"],
        live_receipt_csv=live_receipt_csv,
        action_board_csv=paths["action_board_csv"],
        field_worksheet_json=paths["worksheet_json"],
        staging_public_benchmark_work_order_csv=paths["work_order_csv"],
        target_public_benchmark_intake_csv=target_intake_csv,
        mode="live_apply",
        write_canonical_receipt=True,
        write_public_benchmark_intake=True,
        approval_token=APPROVAL_TOKEN,
        public_benchmark_approval_token=REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN,
        root=tmp_path,
    )
    assert allowed["summary"]["canonical_receipt_written"] is True
    assert allowed["summary"]["public_benchmark_intake_written"] is True
    assert live_receipt_csv.is_file()
    assert target_intake_csv.is_file()


def test_current_staging_apply_surfaces_materialized_public_benchmark_candidate() -> None:
    payload = mod.build_engine_refinement_claim_evidence_operator_staging_apply()
    summary = payload["summary"]

    assert summary["status"] == "blocked_engine_refinement_claim_evidence_operator_staging_apply"
    assert summary["candidate_receipt_ready"] is False
    assert summary["candidate_public_benchmark_work_order_ready"] is False
    assert summary["materialized_public_benchmark_metric_ready"] is True
    assert summary["materialized_public_benchmark_apply_ready"] is True
    assert summary["materialized_public_benchmark_candidate_ready"] is True
    assert summary["materialized_public_benchmark_work_order_row_count"] == 8
    assert summary["materialized_public_benchmark_metric_evidence_pass_row_count"] == 8
    assert summary["materialized_public_benchmark_metric_evidence_blocked_row_count"] == 0
    assert summary["materialized_public_benchmark_free_energy_pair_count"] == 8
    assert summary["materialized_public_benchmark_free_energy_spearman"] == 0.6190476190476191
    assert summary["materialized_public_benchmark_free_energy_spearman_gate_ready"] is True
    assert summary["materialized_public_benchmark_free_energy_spearman_bootstrap_p05"] == -0.14285714285714285
    assert summary["materialized_public_benchmark_claim_grade_statistical_support_ready"] is False
    assert summary["materialized_public_benchmark_claim_grade_statistical_support_blocker_count"] == 3
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_template_row_count"
        ]
        == 51
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_templates_metric_source_payload_fill_blocked_row_count"
        ]
        == 51
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_intake_ready"
        ]
        is True
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_intake_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_candidate_count"
        ]
        == 136
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_present_target_count"
        ]
        == 0
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_intake_suggested_local_path_missing_target_count"
        ]
        == 17
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_ready"
        ]
        is False
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_blocked_row_count"
        ]
        == 17
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_verified_count"
        ]
        == 17
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_r4_preflight_row_fingerprint_mismatch_count"
        ]
        == 0
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_coordinate_fetch_operator_receipt_approval_token_required"
        ]
        == "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready"
        ]
        is False
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_row_count"
        ]
        == 51
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count"
        ]
        == 51
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_verified_count"
        ]
        == 51
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_template_row_fingerprint_mismatch_count"
        ]
        == 0
    )
    assert (
        summary[
            "field_worksheet_public_benchmark_statistical_support_metric_source_payload_operator_receipt_approval_token_required"
        ]
        == "APPROVE_R9_STATISTICAL_SUPPORT_METRIC_SOURCE_PAYLOADS"
    )
    assert "fill/approve 17 coordinate fetch receipt rows" in summary["next_required_step"]
    assert "validate the 17 statistical-support coordinates" in summary["next_required_step"]
    assert "replace 51 blocked metric source template placeholders" in summary["next_required_step"]
    assert "fill/approve 51 metric payload receipt rows" in summary["next_required_step"]
