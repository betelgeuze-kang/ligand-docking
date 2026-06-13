from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_engine_refinement_claim_evidence_operator_staging_apply as mod
from tools.product.build_engine_refinement_claim_evidence_receipt import (
    APPROVAL_TOKEN,
    EXPECTED_EVIDENCE,
    REQUIRED_BLOCKERS,
    REQUIRED_COLUMNS,
)
from tools.product.build_refine_tier_public_benchmark_readiness import (
    REFINE_TIER_PUBLIC_BENCHMARK_INTAKE_APPROVAL_TOKEN,
    WORK_ORDER_COLUMNS,
)


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


def _work_order_rows(*, filled: bool = False) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
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


def _worksheet(path: Path, *, filled: bool = False) -> None:
    _write_json(
        path,
        {
            "summary": {
                "status": "engine_refinement_claim_evidence_operator_field_worksheet_ready",
                "operator_fill_pending_field_count": 0 if filled else 108,
                "receipt_operator_fill_pending_field_count": 0 if filled else 36,
                "public_benchmark_work_order_pending_field_count": 0 if filled else 72,
                "top_blocker_id": "public_benchmark_gate_not_ready",
                "top_priority_bucket": "claim_receipt_attestation_required"
                if filled
                else "public_benchmark_work_order_apply_required",
                "top_blocker_pending_field_count": 0 if filled else 78,
            }
        },
    )


def _write_sources(tmp_path: Path, *, filled: bool = False) -> dict[str, Path]:
    receipt_csv = tmp_path / "config" / "engine_receipt.csv"
    action_board_csv = tmp_path / "runs" / "action_board.csv"
    work_order_csv = tmp_path / "runs" / "work_order.csv"
    target_intake_csv = tmp_path / "config" / "target_intake.csv"
    worksheet_json = tmp_path / "runs" / "worksheet.json"
    existing_apply_json = tmp_path / "runs" / "refine_tier_public_benchmark_work_order_apply_current.json"
    _write_csv(receipt_csv, _receipt_rows(tmp_path, filled=filled), REQUIRED_COLUMNS)
    _action_board(action_board_csv)
    _write_csv(work_order_csv, _work_order_rows(filled=filled), WORK_ORDER_COLUMNS)
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
    assert summary["staging_receipt_placeholder_row_count"] == 6
    assert summary["staging_public_benchmark_work_order_placeholder_row_count"] == 8
    assert summary["field_worksheet_pending_field_count"] == 108
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
