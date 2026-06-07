from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_gpcr_residual_proof_breadth_gate as mod


def _gpcr_proof() -> dict[str, object]:
    return {
        "summary": {
            "status": "gpcr_hard_decoy_residual_proof_ready",
            "gpcr_hard_decoy_residual_proof_ready": True,
            "task_count": 2,
            "intrusion_reduction_task_count": 1,
            "pass_to_fail_regression_count": 0,
            "binder_retention_fail_count": 0,
        }
    }


def _assist_selection() -> dict[str, object]:
    return {
        "summary": {
            "status": "gpcr_residual_assist_candidate_selection_ready",
            "assist_candidate_ready": True,
            "task_count": 2,
            "residual_applied_task_count": 1,
            "pr_auc_regression_warning_count": 0,
            "pass_to_fail_regression_count": 0,
        }
    }


def _heldout() -> dict[str, object]:
    return {
        "summary": {
            "acceptance_overall_pass": True,
            "scorecard_level_status": "pass",
            "blocker_count": 0,
            "gpcr_distinct_positive_target_count": 7,
            "gpcr_positive_count": 12,
        }
    }


def _guardrail() -> dict[str, object]:
    return {
        "summary": {
            "status": "green",
            "acceptance_overall_pass": True,
            "blocker_count": 0,
            "blocking_warning_present": False,
        }
    }


def _ci_low() -> dict[str, object]:
    return {
        "summary": {
            "pass": True,
            "ci_low_blocker": False,
            "ranking_pr_auc_ci_low": 0.67,
            "threshold": 0.45,
            "ranking_positive_count": 13,
        }
    }


def _scaleup() -> dict[str, object]:
    return {
        "summary": {
            "candidate_count": 1,
            "guardrail_fail_count": 0,
            "rejected_candidate_count": 0,
            "claim_safe": False,
        }
    }


def _guarded() -> dict[str, object]:
    return {
        "summary": {
            "status": "eligible",
            "launch_eligible": True,
            "blocker_count": 0,
            "launch_blocker_count": 0,
        }
    }


def _build(**overrides: dict[str, object]) -> dict[str, object]:
    packets = {
        "gpcr_proof_packet": _gpcr_proof(),
        "gpcr_assist_selection_packet": _assist_selection(),
        "heldout_scorecard_packet": _heldout(),
        "heldout_guardrail_packet": _guardrail(),
        "ci_low_recovery_packet": _ci_low(),
        "scaleup_triage_packet": _scaleup(),
        "guarded_rerun_packet": _guarded(),
    }
    packets.update(overrides)
    return mod.build_gpcr_residual_proof_breadth_gate(**packets)  # type: ignore[arg-type]


def test_gpcr_residual_proof_breadth_gate_ready() -> None:
    payload = _build()

    summary = payload["summary"]
    assert summary["status"] == "gpcr_residual_proof_breadth_gate_ready"
    assert summary["gpcr_residual_proof_breadth_gate_ready"] is True
    assert summary["production_promotion_allowed"] is False
    assert summary["effective_gpcr_breadth_count"] == 7
    assert summary["pr_auc_regression_warning_count"] == 0


def test_gpcr_residual_proof_breadth_gate_blocks_missing_breadth() -> None:
    heldout = _heldout()
    heldout["summary"]["gpcr_distinct_positive_target_count"] = 4  # type: ignore[index]
    payload = _build(heldout_scorecard_packet=heldout)

    summary = payload["summary"]
    assert summary["status"] == "blocked_gpcr_residual_proof_breadth_gate"
    assert summary["gpcr_residual_proof_breadth_gate_ready"] is False
    assert "family_heldout_target_breadth" in summary["failed_check_ids"]


def test_gpcr_residual_proof_breadth_gate_blocks_pr_auc_warning() -> None:
    assist = _assist_selection()
    assist["summary"]["pr_auc_regression_warning_count"] = 1  # type: ignore[index]
    payload = _build(gpcr_assist_selection_packet=assist)

    summary = payload["summary"]
    assert summary["status"] == "blocked_gpcr_residual_proof_breadth_gate"
    assert summary["pr_auc_regression_warning_count"] == 1
    assert "clean_per_task_assist_selection" in summary["failed_check_ids"]


def test_gpcr_residual_proof_breadth_gate_cli_writes_outputs(tmp_path: Path) -> None:
    packet_paths: dict[str, Path] = {}
    for name, packet in {
        "gpcr": _gpcr_proof(),
        "assist": _assist_selection(),
        "heldout": _heldout(),
        "guardrail": _guardrail(),
        "ci": _ci_low(),
        "scaleup": _scaleup(),
        "guarded": _guarded(),
    }.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(packet) + "\n", encoding="utf-8")
        packet_paths[name] = path

    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"
    mod.main(
        [
            "--gpcr-proof-json",
            str(packet_paths["gpcr"]),
            "--gpcr-assist-selection-json",
            str(packet_paths["assist"]),
            "--heldout-scorecard-json",
            str(packet_paths["heldout"]),
            "--heldout-guardrail-json",
            str(packet_paths["guardrail"]),
            "--ci-low-recovery-json",
            str(packet_paths["ci"]),
            "--scaleup-triage-json",
            str(packet_paths["scaleup"]),
            "--guarded-rerun-json",
            str(packet_paths["guarded"]),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["gpcr_residual_proof_breadth_gate_ready"] is True
    assert "check_id" in out_csv.read_text(encoding="utf-8")
    assert "GPCR Residual Proof Breadth Gate" in out_md.read_text(encoding="utf-8")
