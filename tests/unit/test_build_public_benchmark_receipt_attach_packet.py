from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_public_benchmark_receipt_attach_packet as mod


def _write_summary(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"summary": summary}, indent=2) + "\n", encoding="utf-8")


def _write_payload(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_inputs(tmp_path: Path, *, ready: bool) -> dict[str, Path]:
    paths = {
        "audit": tmp_path / "runs/public_benchmark_external_receipts_audit_current.json",
        "work_order": tmp_path / "runs/public_benchmark_vina_gnina_comparison_work_order_current.json",
        "score_receipt": tmp_path / "runs/public_benchmark_vina_gnina_score_template_receipt_current.json",
        "score_csv": tmp_path / "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv",
        "receipt": (
            tmp_path
            / "runs/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.json"
        ),
        "receipt_csv": (
            tmp_path
            / "config/refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_current.csv"
        ),
    }
    _write_summary(
        paths["audit"],
        {
            "status": "public_benchmark_external_receipts_audit_ready"
            if ready
            else "blocked_public_benchmark_external_receipts_audit",
            "external_benchmark_receipts_ready": ready,
            "blocker_count": 0 if ready else 2,
        },
    )
    _write_summary(
        paths["work_order"],
        {
            "status": "public_benchmark_vina_gnina_comparison_work_order_ready",
            "score_template_validation_ready": ready,
            "score_template_row_count": 2,
            "score_value_pending_count": 0 if ready else 4,
            "operator_metadata_pending_count": 0 if ready else 16,
            "operator_placeholder_pending_count": 0 if ready else 16,
            "license_ok_pending_count": 0 if ready else 2,
            "approval_token_pending_count": 0 if ready else 2,
            "score_template_blocker_count": 0 if ready else 5,
            "approval_token_required": mod.VINA_GNINA_APPROVAL_TOKEN,
            "next_required_step": "Fill every Vina/GNINA same-input score row.",
        },
    )
    _write_csv(
        paths["score_csv"],
        ["pose_id", "vina_score", "gnina_score"],
        [
            {"pose_id": "1abc_pose_001", "vina_score": "-7.1" if ready else "", "gnina_score": "-8.2" if ready else ""},
            {"pose_id": "2def_pose_001", "vina_score": "-6.4" if ready else "", "gnina_score": "-7.0" if ready else ""},
        ],
    )
    score_row_work_order_rows = []
    if not ready:
        score_row_work_order_rows = [
            {
                "work_order_id": "vina_gnina_same_input_score_row:1abc_pose_001",
                "status": "blocked",
                "pose_id": "1abc_pose_001",
                "complex_id": "1abc",
                "operator_csv": "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv",
                "missing_field_count": 4,
                "missing_fields": ["approval_token", "gnina_score", "operator_id", "vina_score"],
                "primary_missing_field": "approval_token",
                "primary_required_action": (
                    f"Fill approval_token with {mod.VINA_GNINA_APPROVAL_TOKEN} after operator review."
                ),
                "required_action": (
                    "Fill the missing same-input score, metadata, license, and approval fields "
                    "for this pose row, then rebuild the receipt."
                ),
                "blocker_count": 4,
                "blockers": [
                    "score_values_missing_or_invalid",
                    "operator_metadata_missing_or_placeholder",
                    "license_ok_pending",
                    "approval_token_pending",
                ],
                "score_values_ready": False,
                "metadata_ready": False,
                "license_ok": False,
                "approval_token_ok": False,
                "approval_token_required": mod.VINA_GNINA_APPROVAL_TOKEN,
                "operator_action_required": True,
                "execution_enabled": True,
                "external_state_mutated": True,
                "claim_promotion_allowed": True,
                "claim_boundary": "same-input Vina/GNINA score receipt only",
            },
            {
                "work_order_id": "vina_gnina_same_input_score_row:2def_pose_001",
                "status": "blocked",
                "pose_id": "2def_pose_001",
                "complex_id": "2def",
                "operator_csv": "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv",
                "missing_field_count": 4,
                "missing_fields": ["approval_token", "gnina_score", "operator_id", "vina_score"],
                "primary_missing_field": "approval_token",
                "primary_required_action": (
                    f"Fill approval_token with {mod.VINA_GNINA_APPROVAL_TOKEN} after operator review."
                ),
                "required_action": (
                    "Fill the missing same-input score, metadata, license, and approval fields "
                    "for this pose row, then rebuild the receipt."
                ),
                "blocker_count": 4,
                "blockers": [
                    "score_values_missing_or_invalid",
                    "operator_metadata_missing_or_placeholder",
                    "license_ok_pending",
                    "approval_token_pending",
                ],
                "score_values_ready": False,
                "metadata_ready": False,
                "license_ok": False,
                "approval_token_ok": False,
                "approval_token_required": mod.VINA_GNINA_APPROVAL_TOKEN,
                "operator_action_required": True,
                "execution_enabled": True,
                "external_state_mutated": True,
                "claim_promotion_allowed": True,
                "claim_boundary": "same-input Vina/GNINA score receipt only",
            },
        ]
    _write_payload(
        paths["score_receipt"],
        {
            "summary": {
                "status": "public_benchmark_vina_gnina_score_template_receipt_ready"
                if ready
                else "blocked_public_benchmark_vina_gnina_score_template_receipt",
                "score_template_receipt_ready": ready,
                "score_template_validation_ready": ready,
                "score_template_row_count": 2,
                "score_value_pending_count": 0 if ready else 4,
                "operator_metadata_pending_count": 0 if ready else 16,
                "operator_placeholder_pending_count": 0 if ready else 16,
                "license_ok_pending_count": 0 if ready else 2,
                "approval_token_pending_count": 0 if ready else 2,
                "pending_field_counts": {}
                if ready
                else {
                    "approval_token": 2,
                    "gnina_score": 2,
                    "operator_id": 2,
                    "vina_score": 2,
                },
                "score_template_blocker_count": 0 if ready else 5,
                "score_template_csv": "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv",
                "approval_token_required": mod.VINA_GNINA_APPROVAL_TOKEN,
                "next_required_step": "Fill every Vina/GNINA same-input score row.",
                "score_evidence_row_work_order_ready": ready,
                "score_evidence_row_work_order_row_count": 0 if ready else 2,
                "score_evidence_row_work_order_primary_pose_id": "" if ready else "1abc_pose_001",
                "score_evidence_row_work_order_primary_complex_id": "" if ready else "1abc",
                "score_evidence_row_work_order_primary_missing_field_count": 0 if ready else 4,
                "score_evidence_row_work_order_primary_missing_fields": []
                if ready
                else ["approval_token", "gnina_score", "operator_id", "vina_score"],
                "score_evidence_row_work_order_primary_required_action": ""
                if ready
                else (
                    "Fill the missing same-input score, metadata, license, and approval fields "
                    "for this pose row, then rebuild the receipt."
                ),
            },
            "score_evidence_row_work_order_rows": score_row_work_order_rows,
        },
    )
    _write_summary(
        paths["receipt"],
        {
            "status": "refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt_ready"
            if ready
            else "blocked_refine_tier_public_benchmark_statistical_support_metric_source_payload_operator_receipt",
            "row_count": 3,
            "blocked_row_count": 0 if ready else 3,
            "receipt_manual_field_pending_count": 0 if ready else 30,
            "receipt_metric_value_pending_count": 0 if ready else 3,
            "receipt_method_pending_count": 0 if ready else 3,
            "receipt_input_artifacts_reviewed_pending_count": 0 if ready else 3,
            "receipt_input_artifact_sha256s_reviewed_pending_count": 0 if ready else 3,
            "receipt_metric_source_artifact_reviewed_pending_count": 0 if ready else 3,
            "receipt_payload_schema_reviewed_pending_count": 0 if ready else 3,
            "receipt_license_ok_pending_count": 0 if ready else 3,
            "receipt_operator_id_pending_count": 0 if ready else 3,
            "receipt_reviewed_at_utc_pending_count": 0 if ready else 3,
            "receipt_approval_token_pending_count": 0 if ready else 3,
            "claim_promotion_allowed": ready,
            "approval_token_required": "APPROVE_REFINE_TIER_PUBLIC_BENCHMARK_METRIC_SOURCE_PAYLOAD",
        },
    )
    _write_csv(
        paths["receipt_csv"],
        ["template_id", "metric_value"],
        [
            {"template_id": "dockq", "metric_value": "0.5" if ready else ""},
            {"template_id": "lddt_pli", "metric_value": "0.6" if ready else ""},
            {"template_id": "delta_g", "metric_value": "-8.1" if ready else ""},
        ],
    )
    return paths


def _build(tmp_path: Path, *, ready: bool) -> dict:
    paths = _write_inputs(tmp_path, ready=ready)
    return mod.build_public_benchmark_receipt_attach_packet(
        external_receipts_audit_json=paths["audit"],
        vina_gnina_work_order_json=paths["work_order"],
        vina_gnina_score_template_receipt_json=paths["score_receipt"],
        vina_gnina_score_template_csv=paths["score_csv"],
        metric_source_receipt_json=paths["receipt"],
        metric_source_receipt_csv=paths["receipt_csv"],
        root=tmp_path,
    )


def test_public_benchmark_receipt_attach_packet_blocks_pending_operator_fields(tmp_path: Path) -> None:
    payload = _build(tmp_path, ready=False)
    summary = payload["summary"]
    rows = {row["lane_id"]: row for row in payload["rows"]}

    assert summary["status"] == "blocked_public_benchmark_receipt_attach_packet"
    assert summary["receipt_attach_packet_ready"] is False
    assert summary["external_benchmark_receipts_ready"] is False
    assert summary["ready_lane_count"] == 0
    assert summary["blocked_lane_count"] == 2
    assert summary["primary_blocker_id"] == "vina_gnina_same_input_scores"
    assert summary["claim_promotion_allowed"] is False
    assert summary["vina_gnina_score_template_receipt_present"] is True
    assert summary["field_work_order_ready"] is False
    assert summary["field_work_order_row_count"] == 14
    assert summary["field_work_order_pending_field_count"] == 38
    assert summary["field_work_order_primary_lane_id"] == "vina_gnina_same_input_scores"
    assert summary["field_work_order_primary_field_name"] == "approval_token"
    assert summary["field_work_order_primary_pending_row_count"] == 2
    assert summary["field_work_order_primary_required_value"] == (
        f"{mod.VINA_GNINA_APPROVAL_TOKEN} for approval_token"
    )
    assert summary["field_work_order_primary_approval_token_required"] == (
        mod.VINA_GNINA_APPROVAL_TOKEN
    )
    assert summary["field_work_order_primary_required_action"] == (
        f"Fill approval_token with {mod.VINA_GNINA_APPROVAL_TOKEN} after operator review."
    )
    assert summary["field_work_order_primary_operator_csv"] == (
        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    )
    assert summary["field_work_order_primary_source_artifact"] == (
        "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
    )
    assert summary["score_evidence_row_work_order_ready"] is False
    assert summary["score_evidence_row_work_order_row_count"] == 2
    assert summary["score_evidence_row_work_order_pending_field_count"] == 8
    assert summary["score_evidence_row_work_order_primary_work_order_id"] == (
        "vina_gnina_same_input_score_row:1abc_pose_001"
    )
    assert summary["score_evidence_row_work_order_primary_pose_id"] == "1abc_pose_001"
    assert summary["score_evidence_row_work_order_primary_complex_id"] == "1abc"
    assert summary["score_evidence_row_work_order_primary_missing_field_count"] == 4
    assert summary["score_evidence_row_work_order_primary_missing_fields"] == [
        "approval_token",
        "gnina_score",
        "operator_id",
        "vina_score",
    ]
    assert summary["score_evidence_row_work_order_primary_missing_field"] == "approval_token"
    assert summary["score_evidence_row_work_order_primary_required_action"] == (
        "Fill the missing same-input score, metadata, license, and approval fields "
        "for this pose row, then rebuild the receipt."
    )
    assert summary["score_evidence_row_work_order_primary_field_required_action"] == (
        f"Fill approval_token with {mod.VINA_GNINA_APPROVAL_TOKEN} after operator review."
    )
    assert summary["score_evidence_row_work_order_primary_operator_csv"] == (
        "runs/public_benchmark_vina_gnina_same_input_scores_template_current.csv"
    )
    assert summary["score_evidence_row_work_order_primary_source_artifact"] == (
        "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
    )
    assert rows["vina_gnina_same_input_scores"]["pending_value_count"] == 4
    assert rows["vina_gnina_same_input_scores"]["pending_metadata_count"] == 32
    assert rows["vina_gnina_same_input_scores"]["pending_approval_token_count"] == 2
    assert rows["metric_source_receipt_rows"]["pending_value_count"] == 30
    assert rows["metric_source_receipt_rows"]["pending_approval_token_count"] == 3
    field_rows = {
        (row["lane_id"], row["field_name"]): row for row in payload["field_work_order_rows"]
    }
    assert field_rows[("vina_gnina_same_input_scores", "vina_score")]["pending_row_count"] == 2
    assert field_rows[("vina_gnina_same_input_scores", "approval_token")]["required_action"] == (
        f"Fill approval_token with {mod.VINA_GNINA_APPROVAL_TOKEN} after operator review."
    )
    assert field_rows[("metric_source_receipt_rows", "metric_value")]["pending_row_count"] == 3
    assert field_rows[("metric_source_receipt_rows", "approval_token")]["pending_row_count"] == 3
    score_row = payload["score_evidence_row_work_order_rows"][0]
    assert score_row["work_order_id"] == "vina_gnina_same_input_score_row:1abc_pose_001"
    assert score_row["source_artifact"] == (
        "runs/public_benchmark_vina_gnina_score_template_receipt_current.json"
    )
    assert score_row["execution_enabled"] is False
    assert score_row["external_state_mutated"] is False
    assert score_row["claim_promotion_allowed"] is False
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False


def test_public_benchmark_receipt_attach_packet_ready_when_lanes_are_filled(tmp_path: Path) -> None:
    payload = _build(tmp_path, ready=True)
    summary = payload["summary"]

    assert summary["status"] == "public_benchmark_receipt_attach_packet_ready"
    assert summary["receipt_attach_packet_ready"] is True
    assert summary["external_benchmark_receipts_ready"] is True
    assert summary["ready_lane_count"] == 2
    assert summary["blocked_lane_count"] == 0
    assert summary["blockers"] == []
    assert summary["field_work_order_ready"] is True
    assert summary["field_work_order_row_count"] == 0
    assert payload["field_work_order_rows"] == []
    assert summary["score_evidence_row_work_order_ready"] is True
    assert summary["score_evidence_row_work_order_row_count"] == 0
    assert payload["score_evidence_row_work_order_rows"] == []
    assert summary["claim_promotion_allowed"] is False


def test_public_benchmark_receipt_attach_packet_cli_writes_outputs(tmp_path: Path) -> None:
    paths = _write_inputs(tmp_path, ready=False)
    out_json = tmp_path / "runs/public_benchmark_receipt_attach_packet_current.json"
    out_csv = tmp_path / "runs/public_benchmark_receipt_attach_packet_current.csv"
    out_md = tmp_path / "runs/public_benchmark_receipt_attach_packet_current.md"

    assert mod.main(
        [
            "--external-receipts-audit-json",
            str(paths["audit"]),
            "--vina-gnina-work-order-json",
            str(paths["work_order"]),
            "--vina-gnina-score-template-receipt-json",
            str(paths["score_receipt"]),
            "--vina-gnina-score-template-csv",
            str(paths["score_csv"]),
            "--metric-source-receipt-json",
            str(paths["receipt"]),
            "--metric-source-receipt-csv",
            str(paths["receipt_csv"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    ) == 0

    written = json.loads(out_json.read_text(encoding="utf-8"))
    assert written["summary"]["packet_type"] == "public_benchmark_receipt_attach_packet"
    assert written["summary"]["field_work_order_row_count"] == 14
    assert written["summary"]["score_evidence_row_work_order_row_count"] == 2
    assert "vina_gnina_same_input_scores" in out_csv.read_text(encoding="utf-8")
    md = out_md.read_text(encoding="utf-8")
    assert "Public Benchmark Receipt Attach Packet" in md
    assert "Field Work Order" in md
    assert "Score Evidence Row Work Order" in md
    assert "1abc_pose_001" in md
    assert "metric_value" in md
    assert "Fill approval_token with" in md
