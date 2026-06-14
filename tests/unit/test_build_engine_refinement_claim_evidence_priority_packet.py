from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_engine_refinement_claim_evidence_priority_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _action_board(path: Path) -> None:
    rows = [
        {
            "blocker_id": blocker_id,
            "current_status": "blocked",
            "required_evidence": f"required evidence for {blocker_id}",
            "owner_action": f"operator action for {blocker_id}",
            "gate_or_artifact": "runs/engine_refinement_tier_readiness_current.json",
            "external_dependency": "operator curated evidence",
            "claim_boundary": "claim remains blocked",
            "blocking_signals": "unit_blocker",
            "next_required_step": f"next step for {blocker_id}",
        }
        for blocker_id in mod.REQUIRED_BLOCKERS
    ]
    _write_csv(
        path,
        rows,
        [
            "blocker_id",
            "current_status",
            "required_evidence",
            "owner_action",
            "gate_or_artifact",
            "external_dependency",
            "claim_boundary",
            "blocking_signals",
            "next_required_step",
        ],
    )


def _receipt(path: Path, *, ready: bool) -> None:
    rows = []
    for blocker_id in mod.REQUIRED_BLOCKERS:
        expected = mod.EXPECTED_EVIDENCE[blocker_id]
        rows.append(
            {
                "blocker_id": blocker_id,
                "row_status": "pass" if ready else "blocked",
                "blockers": "" if ready else "operator_placeholders_unfilled",
                "evidence_artifact": f"runs/{blocker_id}.json" if ready else "OPERATOR_FILL_LOCAL_EVIDENCE_JSON",
                "expected_evidence_status": expected["status"],
                "observed_evidence_status": expected["status"] if ready else "missing",
                "missing_true_fields": "" if ready else ";".join(expected["true_fields"]),
                "external_state_mutated": False,
            }
        )
    _write_json(
        path,
        {
            "summary": {
                "status": (
                    "engine_refinement_claim_evidence_receipt_ready"
                    if ready
                    else "blocked_engine_refinement_claim_evidence_receipt"
                ),
                "claim_promotion_evidence_receipt_ready": ready,
                "blocked_row_count": 0 if ready else 6,
            },
            "rows": rows,
        },
    )


def _work_order(path: Path) -> None:
    rows = [
        {
            "work_order_id": f"refine_tier_public_benchmark_fill_{index:03d}",
            "target_input_csv": "config/refine_tier_public_benchmark_intake_current.csv",
            "template_row_index": index,
        }
        for index in range(1, 9)
    ]
    _write_csv(path, rows, ["work_order_id", "target_input_csv", "template_row_index"])


def test_engine_refinement_claim_evidence_priority_packet_blocks_current_r9_work() -> None:
    payload = mod.build_engine_refinement_claim_evidence_priority_packet()
    summary = payload["summary"]

    assert summary["status"] == "blocked_engine_refinement_claim_evidence_priority_packet"
    assert summary["priority_packet_ready"] is True
    assert summary["claim_promotion_allowed"] is False
    assert summary["priority_item_count"] == 6
    assert summary["operator_input_required_count"] == 6
    assert summary["blocked_priority_item_count"] == 6
    assert summary["public_benchmark_gate_ready"] is False
    assert summary["public_benchmark_work_order_present"] is True
    assert summary["public_benchmark_work_order_row_count"] == 8
    assert summary["public_benchmark_work_order_apply_ready"] is False
    assert summary["public_benchmark_work_order_apply_blocked_row_count"] == 8
    assert summary["public_benchmark_materialized_metric_ready"] is True
    assert summary["public_benchmark_materialized_apply_ready"] is True
    assert summary["public_benchmark_materialized_candidate_ready"] is True
    assert summary["public_benchmark_materialized_work_order_row_count"] == 8
    assert summary["public_benchmark_materialized_metric_evidence_pass_row_count"] == 8
    assert summary["public_benchmark_materialized_metric_evidence_blocked_row_count"] == 0
    assert summary["public_benchmark_materialized_free_energy_pair_count"] == 8
    assert summary["public_benchmark_materialized_free_energy_spearman"] == 0.6190476190476191
    assert summary["public_benchmark_materialized_free_energy_spearman_gate_ready"] is True
    assert summary["public_benchmark_materialized_free_energy_spearman_bootstrap_p05"] == -0.14285714285714285
    assert summary["public_benchmark_materialized_claim_grade_statistical_support_ready"] is False
    assert summary["public_benchmark_materialized_claim_grade_statistical_support_blocker_count"] == 3
    assert summary["top_blocker_id"] == "public_benchmark_gate_not_ready"
    assert summary["top_priority_bucket"] == "public_benchmark_work_order_apply_required"
    assert summary["top_required_input"] == "runs/refine_tier_public_benchmark_work_order_current.csv"
    assert "apply_refine_tier_public_benchmark_work_order.py" in summary["top_verification_command"]
    assert summary["approval_token_required"] == mod.APPROVAL_TOKEN
    assert "operator_evidence_rows_pending" in summary["blockers"]
    assert payload["rows"][0]["blocker_id"] == "public_benchmark_gate_not_ready"
    assert payload["rows"][0]["operator_input_required"] is True
    assert payload["rows"][0]["public_benchmark_materialized_candidate_ready"] is True
    assert payload["rows"][0]["public_benchmark_materialized_claim_grade_statistical_support_ready"] is False
    assert "Materialized public benchmark candidate is apply-ready" in payload["rows"][0]["next_operator_step"]
    assert payload["rows"][1]["priority_bucket"] == "blocked_until_public_benchmark_ready"
    assert payload["rows"][1]["prerequisite_blocker_id"] == "public_benchmark_gate_not_ready"
    assert all(row["external_state_mutated"] is False for row in payload["rows"])


def test_engine_refinement_claim_evidence_priority_packet_ready_with_verified_local_receipts(
    tmp_path: Path,
) -> None:
    action_board = tmp_path / "runs" / "action_board.csv"
    receipt = tmp_path / "runs" / "receipt.json"
    public_readiness = tmp_path / "runs" / "public_readiness.json"
    work_order = tmp_path / "runs" / "work_order.csv"
    work_order_apply = tmp_path / "runs" / "work_order_apply.json"
    _action_board(action_board)
    _receipt(receipt, ready=True)
    _write_json(
        public_readiness,
        {
            "summary": {
                "status": "refine_tier_public_benchmark_ready",
                "claim_grade_public_benchmark_ready": True,
            }
        },
    )
    _work_order(work_order)
    _write_json(
        work_order_apply,
        {
            "summary": {
                "status": "refine_tier_public_benchmark_work_order_apply_ready",
                "apply_ready": True,
                "blocked_row_count": 0,
            }
        },
    )

    payload = mod.build_engine_refinement_claim_evidence_priority_packet(
        action_board_csv=action_board.relative_to(tmp_path),
        receipt_json=receipt.relative_to(tmp_path),
        public_benchmark_readiness_json=public_readiness.relative_to(tmp_path),
        public_benchmark_work_order_csv=work_order.relative_to(tmp_path),
        public_benchmark_work_order_apply_json=work_order_apply.relative_to(tmp_path),
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "engine_refinement_claim_evidence_priority_packet_ready"
    assert summary["priority_packet_ready"] is True
    assert summary["claim_evidence_receipt_ready"] is True
    assert summary["operator_input_required_count"] == 0
    assert summary["blocked_priority_item_count"] == 0
    assert summary["public_benchmark_gate_ready"] is True
    assert summary["public_benchmark_work_order_apply_ready"] is True
    assert summary["top_priority_bucket"] == "receipt_verified"
    assert summary["blockers"] == []
    assert all(row["priority_bucket"] == "receipt_verified" for row in payload["rows"])


def test_engine_refinement_claim_evidence_priority_packet_cli_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "priority.json"
    out_csv = tmp_path / "priority.csv"
    out_md = tmp_path / "priority.md"

    mod.main(["--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_engine_refinement_claim_evidence_priority_packet"
    assert "priority_bucket" in out_csv.read_text(encoding="utf-8")
    assert "Engine Refinement Claim Evidence Priority Packet" in out_md.read_text(encoding="utf-8")
