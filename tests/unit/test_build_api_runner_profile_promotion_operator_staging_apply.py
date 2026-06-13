from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_api_runner_profile_promotion_operator_staging_apply as mod
from tools.product.build_api_runner_profile_promotion_operator_receipt import APPROVAL_TOKEN


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=mod.REQUIRED_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in mod.REQUIRED_COLUMNS})


def _readiness(path: Path, *, ready: bool = True) -> None:
    _write_json(
        path,
        {
            "summary": {
                "status": "api_runner_profile_promotion_ready" if ready else "blocked_api_runner_profile_promotion_readiness",
                "profile_count": 2,
                "promotion_ready_count": 2 if ready else 1,
                "blocked_profile_count": 0 if ready else 1,
            },
            "rows": [
                {
                    "profile_id": "profile_a",
                    "profile_path": "profiles/profile_a.json",
                    "enabled": False,
                    "promotion_ready": ready,
                },
                {
                    "profile_id": "profile_b",
                    "profile_path": "profiles/profile_b.json",
                    "enabled": True,
                    "promotion_ready": True,
                },
            ],
        },
    )


def _accuracy(path: Path, *, ready: bool) -> None:
    _write_json(
        path,
        {
            "summary": {
                "status": "accuracy_parity_ready" if ready else "blocked_accuracy_parity",
                "overall_commercial_tool_accuracy_parity_allowed": ready,
                "schrodinger_class_claim_allowed": ready,
            }
        },
    )


def _science(path: Path, *, ready: bool) -> None:
    _write_json(
        path,
        {
            "summary": {
                "status": "science_claim_promotion_gap_closure_complete"
                if ready
                else "blocked_science_claim_promotion_gap_closure",
                "claim_promotion_allowed": ready,
                "all_gaps_closed": ready,
                "open_gap_count": 0 if ready else 2,
                "open_gap_ids": [] if ready else ["SCI-GPCR", "SCI-OPENMM"],
            }
        },
    )


def _filled_rows(tmp_path: Path) -> tuple[list[dict[str, object]], Path]:
    gate_json = tmp_path / "runs" / "api_runner_profile_promotion_readiness_current.json"
    _write_json(gate_json, {"summary": {"status": "api_runner_profile_promotion_ready"}})
    base = {
        "approval_token": APPROVAL_TOKEN,
        "input_contract_reviewed": "true",
        "output_contract_reviewed": "true",
        "claim_boundary_reviewed": "true",
        "gate_policy_reviewed": "true",
        "fake_result_emission_forbidden": "true",
        "gate_policy_artifact": gate_json.relative_to(tmp_path).as_posix(),
        "reviewer": "operator-a",
        "reviewed_at_utc": "2026-06-13T00:00:00+00:00",
        "operator_note": "reviewed",
    }
    return [
        {"profile_id": "profile_a", "operator_decision": "promote", **base},
        {"profile_id": "profile_b", "operator_decision": "keep_enabled", **base},
    ], gate_json


def test_blocks_unfilled_staging_template(tmp_path: Path) -> None:
    readiness_json = tmp_path / "runs" / "readiness.json"
    template_csv = tmp_path / "runs" / "operator_template.csv"
    accuracy_json = tmp_path / "runs" / "accuracy.json"
    science_json = tmp_path / "runs" / "science.json"
    _readiness(readiness_json)
    _accuracy(accuracy_json, ready=False)
    _science(science_json, ready=False)
    _write_csv(
        template_csv,
        [
            {"profile_id": "profile_a"},
            {"profile_id": "profile_b"},
        ],
    )

    payload = mod.build_api_runner_profile_promotion_operator_staging_apply(
        staging_operator_template_csv=template_csv,
        live_operator_template_csv=template_csv,
        readiness_json=readiness_json,
        accuracy_parity_json=accuracy_json,
        science_claim_json=science_json,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_api_runner_profile_promotion_operator_staging_apply"
    assert summary["candidate_operator_receipt_ready"] is False
    assert summary["candidate_blocked_row_count"] == 2
    assert summary["candidate_first_blocked_profile_id"] == "profile_a"
    assert summary["candidate_first_blocked_row_blocker"] == "operator_decision_missing"
    assert summary["accuracy_parity_gate_ready"] is False
    assert summary["science_claim_gate_ready"] is False
    assert summary["broad_promotion_gate_required"] is False
    assert summary["live_copy_allowed"] is False
    assert summary["canonical_operator_template_written"] is False
    assert summary["profile_enabled_by_this_tool"] is False
    assert summary["runner_executed"] is False
    assert summary["external_state_mutated"] is False
    assert "candidate_operator_receipt_not_ready" in summary["blockers"]


def test_blocks_promote_decision_when_broad_science_gates_are_not_ready(tmp_path: Path) -> None:
    readiness_json = tmp_path / "runs" / "readiness.json"
    template_csv = tmp_path / "runs" / "operator_template.csv"
    accuracy_json = tmp_path / "runs" / "accuracy.json"
    science_json = tmp_path / "runs" / "science.json"
    candidate_csv = tmp_path / "runs" / "candidate.csv"
    _readiness(readiness_json)
    _accuracy(accuracy_json, ready=False)
    _science(science_json, ready=False)
    rows, _ = _filled_rows(tmp_path)
    _write_csv(template_csv, rows)

    payload = mod.build_api_runner_profile_promotion_operator_staging_apply(
        staging_operator_template_csv=template_csv,
        live_operator_template_csv=template_csv,
        readiness_json=readiness_json,
        accuracy_parity_json=accuracy_json,
        science_claim_json=science_json,
        candidate_operator_template_csv=candidate_csv,
        root=tmp_path,
    )
    summary = payload["summary"]

    assert summary["status"] == "blocked_api_runner_profile_promotion_operator_staging_apply"
    assert summary["candidate_operator_receipt_ready"] is True
    assert summary["candidate_operator_template_written"] is True
    assert candidate_csv.is_file()
    assert summary["candidate_promote_decision_count"] == 1
    assert summary["broad_promotion_gate_required"] is True
    assert summary["broad_promotion_gate_ready"] is False
    assert summary["live_copy_allowed"] is False
    assert "broad_promotion_accuracy_parity_gate_not_ready" in summary["blockers"]
    assert "broad_promotion_science_claim_gate_not_ready" in summary["blockers"]


def test_live_copy_requires_matching_approval_token_and_ready_broad_gates(tmp_path: Path) -> None:
    readiness_json = tmp_path / "runs" / "readiness.json"
    staging_csv = tmp_path / "runs" / "operator_template.csv"
    live_csv = tmp_path / "config" / "operator_template.csv"
    accuracy_json = tmp_path / "runs" / "accuracy.json"
    science_json = tmp_path / "runs" / "science.json"
    _readiness(readiness_json)
    _accuracy(accuracy_json, ready=True)
    _science(science_json, ready=True)
    rows, _ = _filled_rows(tmp_path)
    _write_csv(staging_csv, rows)

    blocked = mod.build_api_runner_profile_promotion_operator_staging_apply(
        staging_operator_template_csv=staging_csv,
        live_operator_template_csv=live_csv,
        readiness_json=readiness_json,
        accuracy_parity_json=accuracy_json,
        science_claim_json=science_json,
        mode="live_apply",
        write_canonical_operator_template=True,
        approval_token="WRONG",
        root=tmp_path,
    )
    assert blocked["summary"]["canonical_operator_template_written"] is False
    assert "write_canonical_operator_template_approval_token_missing_or_invalid" in blocked["summary"]["blockers"]

    allowed = mod.build_api_runner_profile_promotion_operator_staging_apply(
        staging_operator_template_csv=staging_csv,
        live_operator_template_csv=live_csv,
        readiness_json=readiness_json,
        accuracy_parity_json=accuracy_json,
        science_claim_json=science_json,
        mode="live_apply",
        write_canonical_operator_template=True,
        approval_token=APPROVAL_TOKEN,
        root=tmp_path,
    )
    assert allowed["summary"]["canonical_operator_template_written"] is True
    assert allowed["summary"]["live_copy_allowed"] is True
    assert live_csv.is_file()
