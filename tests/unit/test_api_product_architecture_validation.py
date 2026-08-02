from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path

import pytest


def test_get_product_architecture_validation_read_only(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("fastapi")
    product = importlib.import_module("api.product_architecture")
    report_path = tmp_path / "runs" / "architecture_validation_package_report_current.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "architecture_validation_packages_in_progress",
                    "package_a_complete": True,
                    "package_b_complete": True,
                    "package_c_complete": False,
                    "open_required_test_ids": ["C-25"],
                    "overclaim_open_test_ids": [],
                    "evidence_depth_tier": "row_evidence_partial",
                    "overclaim_warning_count": 1,
                    "overclaim_hard_warning_count": 0,
                    "competition_benchmark_cameo_official_intake_gate_status": (
                        "blocked_cameo_official_results_intake"
                    ),
                    "competition_benchmark_cameo_official_intake_gate_ready": False,
                    "competition_benchmark_cameo_official_result_intake_ready": False,
                    "competition_benchmark_cameo_official_result_row_count": 0,
                    "competition_benchmark_cameo_official_accepted_result_count": 0,
                    "competition_benchmark_cameo_official_rejected_result_count": 0,
                    "competition_benchmark_cameo_official_model1_result_ready": False,
                    "competition_benchmark_cameo_official_blocker_count": 2,
                    "competition_benchmark_cameo_official_blocker_codes": [
                        "official_result_required_columns_missing",
                        "official_result_rows_missing",
                    ],
                    "competition_benchmark_cameo_official_operator_action_required_count": 2,
                    "competition_benchmark_cameo_official_operator_action_required_row_count": 0,
                    "competition_benchmark_cameo_official_primary_blocker_code": (
                        "official_result_rows_missing"
                    ),
                    "competition_benchmark_cameo_official_primary_required_action": (
                        "Fill at least one official CAMEO result row in the operator intake CSV."
                    ),
                    "competition_benchmark_cameo_official_allowed_result_source_kinds": [
                        "cameo_assessment",
                        "cameo_official",
                        "official_cameo",
                    ],
                    "competition_benchmark_cameo_official_source_provenance_ready_row_count": 0,
                    "competition_benchmark_cameo_official_metric_ready_row_count": 0,
                    "competition_benchmark_cameo_official_local_native_accuracy_blocker_count": 0,
                    "competition_benchmark_cameo_official_native_local_accuracy_used": False,
                    "competition_benchmark_cameo_official_external_state_mutated": False,
                    "competition_benchmark_competition_credibility_extension_ready": False,
                    "competition_benchmark_competition_credibility_extension_blocker_count": 3,
                    "competition_benchmark_competition_credibility_extension_blockers": [
                        "casp16_ligand_materialization_not_ready",
                        "casp16_ligand_scorecard_not_ready",
                        "capri_score_set_not_ready",
                    ],
                    "competition_benchmark_competition_credibility_extension_primary_blocker": (
                        "casp16_ligand_materialization_not_ready"
                    ),
                    "competition_benchmark_competition_credibility_extension_next_actions": [
                        "Attach local CASP16 ligand receipts.",
                        "Attach CAPRI score_set receipts.",
                    ],
                    "competition_benchmark_competition_credibility_extension_primary_next_action": (
                        "Attach local CASP16 ligand receipts."
                    ),
                    "competition_benchmark_custody_work_order_status": (
                        "blocked_competition_benchmark_custody_work_order"
                    ),
                    "competition_benchmark_custody_work_order_ready": False,
                    "competition_benchmark_custody_work_order_action_count": 3,
                    "competition_benchmark_custody_work_order_raw_data_blocked_row_count": 1,
                    "competition_benchmark_custody_work_order_missing_receipt_row_count": 2,
                    "competition_benchmark_custody_work_order_primary_work_order_id": (
                        "casp16_ligand_operator_receipts_missing"
                    ),
                    "competition_benchmark_custody_work_order_primary_required_action": (
                        "Place reviewed CASP16 ligand source/checksum/materialization/scorecard receipts."
                    ),
                    "competition_benchmark_custody_work_order_primary_verification_command": (
                        "python3 tools/build_casp16_ligand_materialization_manifest.py "
                        "--source-manifest-csv OPERATOR_LOCAL_SOURCE_MANIFEST "
                        "--checksum-manifest OPERATOR_LOCAL_CHECKSUMS "
                        "--out-json runs/casp16_ligand_materialization_manifest_current.json "
                        "--out-csv runs/casp16_ligand_materialization_manifest_current.csv "
                        "--out-md runs/casp16_ligand_materialization_manifest_current.md && "
                        "python3 tools/build_casp16_ligand_scorecard.py "
                        "--materialization-json runs/casp16_ligand_materialization_manifest_current.json "
                        "--scorecard-rows-csv OPERATOR_REVIEWED_SCORECARD_ROWS_CSV "
                        "--out-json runs/casp16_ligand_scorecard_current.json && "
                        "python3 tools/build_casp16_ligand_source_manifest.py && "
                        "python3 tools/build_competition_benchmark_custody_work_order.py"
                    ),
                    "claim_boundary": "read-only",
                },
                "rows": [],
                "overclaim_warnings": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    external_path = tmp_path / "runs" / "competition_external_operator_track_current.json"
    external_path.write_text(
        json.dumps({"summary": {"status": "operator_pending", "blocked_track_count": 2}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(product, "ROOT", tmp_path)
    monkeypatch.setattr(product, "ARCHITECTURE_VALIDATION_REPORT_ARTIFACT", report_path)
    monkeypatch.setattr(product, "COMPETITION_EXTERNAL_OPERATOR_TRACK_ARTIFACT", external_path)

    payload = asyncio.run(product.get_product_architecture_validation())
    assert payload["architecture_validation_all_packages_complete"] is False
    assert payload["package_a_complete"] is True
    assert payload["evidence_depth_tier"] == "row_evidence_partial"
    assert payload["claim_promotion_allowed"] is False
    assert payload["execution_enabled"] is False
    assert payload["competition_external_blocked_track_count"] == 2
    assert payload["competition_benchmark_cameo_official_result_intake_ready"] is False
    assert payload["competition_benchmark_cameo_official_operator_action_required_count"] == 2
    assert payload["competition_benchmark_cameo_official_operator_action_required_row_count"] == 0
    assert payload["competition_benchmark_cameo_official_primary_blocker_code"] == (
        "official_result_rows_missing"
    )
    assert payload["competition_benchmark_cameo_official_primary_required_action"] == (
        "Fill at least one official CAMEO result row in the operator intake CSV."
    )
    assert "official_cameo" in payload[
        "competition_benchmark_cameo_official_allowed_result_source_kinds"
    ]
    assert payload["competition_benchmark_cameo_official_source_provenance_ready_row_count"] == 0
    assert payload["competition_benchmark_cameo_official_metric_ready_row_count"] == 0
    assert payload["competition_benchmark_cameo_official_local_native_accuracy_blocker_count"] == 0
    assert payload["competition_benchmark_competition_credibility_extension_ready"] is False
    assert payload["competition_benchmark_competition_credibility_extension_blocker_count"] == 3
    assert payload["competition_benchmark_competition_credibility_extension_blockers"] == [
        "casp16_ligand_materialization_not_ready",
        "casp16_ligand_scorecard_not_ready",
        "capri_score_set_not_ready",
    ]
    assert payload["competition_benchmark_competition_credibility_extension_primary_blocker"] == (
        "casp16_ligand_materialization_not_ready"
    )
    assert payload["competition_benchmark_competition_credibility_extension_primary_next_action"] == (
        "Attach local CASP16 ligand receipts."
    )
    assert payload["competition_benchmark_custody_work_order_status"] == (
        "blocked_competition_benchmark_custody_work_order"
    )
    assert payload["competition_benchmark_custody_work_order_action_count"] == 3
    assert payload["competition_benchmark_custody_work_order_raw_data_blocked_row_count"] == 1
    assert payload["competition_benchmark_custody_work_order_primary_work_order_id"] == (
        "casp16_ligand_operator_receipts_missing"
    )
