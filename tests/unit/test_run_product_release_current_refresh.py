from __future__ import annotations

import json
from pathlib import Path

from tools.product import run_product_release_current_refresh as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _source_of_truth_ready() -> dict:
    return {
        "summary": {
            "status": "product_release_source_of_truth_gate_ready",
            "release_source_of_truth_ready": True,
            "blocker_count": 0,
            "stale_artifact_count": 0,
            "readme_drift_count": 0,
        }
    }


def _goal_release_decision_spec() -> dict:
    return next(
        spec for spec in mod.FINAL_GATE_SPECS if spec["gate_id"] == "goal_release_decision_gate"
    )


def _release_decision_ready(*, bottleneck_recorded: bool = True) -> dict:
    spec = _goal_release_decision_spec()
    summary = {
        "status": spec["required_status"],
        **{field: True for field in spec.get("required_true_fields", [])},
        **{field: 0 for field in spec.get("required_zero_fields", [])},
        **dict(spec.get("required_int_exact_fields", {})),
        **dict(spec.get("required_text_exact_fields", {})),
    }
    summary["goal_bottleneck_briefing_full_commercial_receipts_recorded"] = bottleneck_recorded
    return {
        "summary": summary
    }


def test_refresh_final_gate_requires_release_decision_bottleneck_receipt_linkage(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        _release_decision_ready(),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    decision_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert summary["status"] == "product_release_current_refresh_verified"
    assert summary["final_gate_verification_ready"] is True
    assert summary["final_gate_blocker_count"] == 0
    assert decision_row["status"] == "pass"
    assert "goal_bottleneck_briefing_full_commercial_receipts_recorded" in decision_row[
        "required_true_fields"
    ]
    assert decision_row["required_int_exact_fields"][
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_entry_count"
    ] == 2
    assert decision_row["required_text_exact_fields"][
        "goal_bottleneck_briefing_full_commercial_evidence_receipt_required_inputs"
    ] == (
        "config/product_scope_breadth_evidence_receipt_current.csv;"
        "config/engine_refinement_claim_promotion_evidence_receipt_current.csv"
    )


def test_refresh_final_gate_blocks_missing_release_decision_bottleneck_receipt_linkage(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "runs" / "product_release_source_of_truth_gate_current.json",
        _source_of_truth_ready(),
    )
    _write_json(
        tmp_path / "runs" / "goal_release_decision_gate_current.json",
        _release_decision_ready(bottleneck_recorded=False),
    )

    payload = mod.run_product_release_current_refresh(
        execute=True,
        root=tmp_path,
        commands=[],
    )

    summary = payload["summary"]
    decision_row = next(
        row for row in payload["verification_rows"] if row["gate_id"] == "goal_release_decision_gate"
    )
    assert summary["status"] == "blocked_product_release_current_refresh"
    assert summary["final_gate_verification_ready"] is False
    assert summary["final_gate_blocker_count"] == 1
    assert decision_row["status"] == "fail"
    assert "goal_bottleneck_briefing_full_commercial_receipts_recorded" in decision_row[
        "missing_true_fields"
    ]
