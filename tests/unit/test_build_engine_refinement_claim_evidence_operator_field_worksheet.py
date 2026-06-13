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


def _write_sources(tmp_path: Path, *, filled: bool = False) -> None:
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
        _work_order_rows(filled=filled),
        [
            "work_order_id",
            "target_input_csv",
            "template_row_index",
            "benchmark_id",
            "target_id",
            "benchmark_family",
            "split",
            "provenance_kind",
            "provenance_id",
            "license_ok",
            "external_engine_calls",
            "pose_rmsd_A",
            "dockq",
            "lddt_pli",
            "deltaG_mm_gbsa_kcal_mol",
            "deltaG_experimental_kcal_mol",
            "operator_action",
            "acceptance_rule",
            "external_state_mutated",
        ],
    )
    _write_json(tmp_path / mod.DEFAULT_PUBLIC_BENCHMARK_WORK_ORDER_APPLY_JSON, _apply_packet(ready=filled))


def test_engine_refinement_claim_evidence_operator_field_worksheet_flags_pending_fields(
    tmp_path: Path,
) -> None:
    _write_sources(tmp_path, filled=False)

    payload = mod.build_engine_refinement_claim_evidence_operator_field_worksheet(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "engine_refinement_claim_evidence_operator_field_worksheet_ready"
    assert summary["field_worksheet_ready"] is True
    assert summary["operator_fill_complete"] is False
    assert summary["worksheet_field_row_count"] == 144
    assert summary["required_receipt_field_count"] == 66
    assert summary["receipt_operator_fill_pending_field_count"] == 36
    assert summary["public_benchmark_work_order_field_count"] == 72
    assert summary["public_benchmark_work_order_pending_field_count"] == 72
    assert summary["operator_fill_pending_field_count"] == 108
    assert summary["top_blocker_id"] == "public_benchmark_gate_not_ready"
    assert summary["top_priority_bucket"] == "public_benchmark_work_order_apply_required"
    assert summary["top_blocker_pending_field_count"] == 78
    assert summary["public_benchmark_work_order_apply_blocked_row_count"] == 8
    assert summary["approval_token_required"] == APPROVAL_TOKEN
    assert summary["claim_promoted"] is False
    assert summary["external_engine_calls_executed"] is False
    assert summary["external_state_mutated"] is False


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
    assert all(row["operator_input_required"] is False for row in payload["rows"])


def test_engine_refinement_claim_evidence_operator_field_worksheet_cli_writes_outputs(
    tmp_path: Path,
) -> None:
    out_json = tmp_path / "worksheet.json"
    out_csv = tmp_path / "worksheet.csv"
    out_md = tmp_path / "worksheet.md"

    mod.main(["--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "engine_refinement_claim_evidence_operator_field_worksheet_ready"
    assert "worksheet_section" in out_csv.read_text(encoding="utf-8")
    assert "Engine Refinement Claim Evidence Operator Field Worksheet" in out_md.read_text(
        encoding="utf-8"
    )
