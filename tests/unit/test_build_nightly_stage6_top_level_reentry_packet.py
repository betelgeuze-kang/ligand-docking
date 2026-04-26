from __future__ import annotations

from tools import build_nightly_stage6_top_level_reentry_packet as mod


def _top_level_stage6_failure() -> dict[str, object]:
    return {
        "pass": False,
        "failed_stage": "stage6_operational_gate",
        "service_result": {"error_code": "HTVS_GATE_FAILED"},
        "stages": {
            "stage6_operational_gate": {
                "pass": False,
                "failed_metrics": [
                    {
                        "metric": "mean_min_distance_A",
                        "value": 2.655165582969785,
                        "threshold": 2.5,
                    }
                ],
                "mean_min_distance_A": 2.655165582969785,
                "mean_min_distance_A_source": "eval_unique_topk",
            }
        },
    }


def _execute_result_packet() -> dict[str, object]:
    return {
        "summary": {
            "packet_artifact": "runs/nightly_stage6_execute_result_packet_current.md",
            "execute_pass": True,
            "execute_payload_pass": True,
            "execute_gate_pass": True,
            "execute_matches_rescored_gate": True,
            "stage6_gate_pass": True,
            "stage6_override_csv_artifact": "runs/nightly_stage6_downstream_rerun_gate_override_current.csv",
            "stage6_override_row_count": 1,
            "target_subset": "HIV1_PROTEASE",
            "run_scope": "smoke",
        }
    }


def _strict_base_profile() -> dict[str, object]:
    return {
        "version": "ligand_htvs_nightly_strict_v1",
        "targets": "KRAS_G12D,EGFR_KINASE,HIV1_PROTEASE",
        "run_scope": "smoke_then_full",
        "require_ood_eval": True,
        "gate": {
            "enforce_operational_gate": True,
            "strict_fail_fast": True,
            "max_mean_min_distance_A": 2.5,
        },
        "retry": {"max_attempts": 3, "sleep_sec": 20},
    }


def test_top_level_reentry_packet_is_ready_without_fake_promotion() -> None:
    payload = mod.build_payload(
        top_level_payload=_top_level_stage6_failure(),
        top_level_summary_artifact="runs/ligand_htvs_nightly_2026-04-26_summary.json",
        base_profile_payload=_strict_base_profile(),
        base_profile_artifact="config/ligand_htvs_nightly_strict_v1.json",
        nightly_gate_burndown_payload={
            "summary": {
                "packet_artifact": "runs/nightly_gate_burndown_packet_current.md",
                "latest_failed_stage": "stage6_operational_gate",
                "primary_burndown_metric": "mean_min_distance_A",
                "primary_burndown_value": 2.655165582969785,
                "primary_burndown_threshold": 2.5,
                "primary_burndown_delta": 0.155165582969785,
            }
        },
        downstream_rerun_payload={
            "summary": {
                "packet_artifact": "runs/nightly_stage6_downstream_rerun_packet_current.md",
                "downstream_profile_json_artifact": "runs/nightly_stage6_downstream_rerun_profile_current.json",
                "gate_distance_override_csv_artifact": "runs/nightly_stage6_downstream_rerun_gate_override_current.csv",
                "gate_distance_override_row_count": 1,
                "target_subset": "HIV1_PROTEASE",
                "downstream_rerun_ready": True,
            }
        },
        downstream_profile_payload={
            "version": "strict_v1_stage6_downstream_rerun_v1",
            "targets": "HIV1_PROTEASE",
            "require_ood_eval": False,
            "gate_distance_override_csv": "runs/nightly_stage6_downstream_rerun_gate_override_current.csv",
        },
        execute_result_payload=_execute_result_packet(),
        gate_distance_override_rows=[
            {
                "row_key": "HIV1_PROTEASE::imatinib",
                "target": "HIV1_PROTEASE",
                "ligand_id": "imatinib",
                "override_mean_min_distance_A": 2.2689,
            }
        ],
        downstream_profile_artifact="runs/nightly_stage6_downstream_rerun_profile_current.json",
        gate_distance_override_csv_artifact="runs/nightly_stage6_downstream_rerun_gate_override_current.csv",
        date_tag="2026-04-26_stage6_top_level_reentry",
    )

    summary = payload["summary"]
    profile = payload["top_level_reentry_profile"]

    assert summary["ready_for_top_level_reentry"] is True
    assert summary["promotion_allowed"] is False
    assert summary["delivery_ready"] is False
    assert summary["pass"] is False
    assert summary["top_level_pass"] is False
    assert summary["source_top_level_summary_path"] == "runs/ligand_htvs_nightly_2026-04-26_summary.json"
    assert summary["source_failed_stage"] == "stage6_operational_gate"
    assert summary["source_metric"] == "mean_min_distance_A"
    assert summary["source_metric_value"] == 2.655165582969785
    assert summary["source_metric_threshold"] == 2.5
    assert round(summary["source_metric_delta"], 3) == 0.155
    assert summary["downstream_profile_path"] == "runs/nightly_stage6_downstream_rerun_profile_current.json"
    assert summary["gate_distance_override_csv_path"] == "runs/nightly_stage6_downstream_rerun_gate_override_current.csv"
    assert summary["gate_distance_override_csv_row_count"] == 1
    assert summary["execute_evidence_pass_flags"]["execute_pass"] is True
    assert summary["execute_evidence_pass_flags"]["execute_gate_pass"] is True
    assert summary["downstream_evidence_scope"] == "supporting_only"
    assert summary["downstream_evidence_supporting_only"] is True
    assert summary["base_profile_path"] == "config/ligand_htvs_nightly_strict_v1.json"
    assert summary["top_level_targets"] == "KRAS_G12D,EGFR_KINASE,HIV1_PROTEASE"
    assert summary["top_level_run_scope"] == "smoke_then_full"
    assert summary["top_level_require_ood_eval"] is True
    assert summary["top_level_gate_threshold"] == 2.5
    assert summary["top_level_gate_threshold_unchanged"] is True
    assert summary["top_level_strict_fail_fast"] is True
    assert summary["top_level_enforce_operational_gate"] is True
    assert summary["target_subset"] == "HIV1_PROTEASE"
    assert summary["downstream_target_subset"] == "HIV1_PROTEASE"
    assert summary["downstream_target_subset_is_top_level_subset"] is True
    assert summary["require_ood_eval"] is True

    assert profile["gate_distance_override_csv"] == "runs/nightly_stage6_downstream_rerun_gate_override_current.csv"
    assert profile["targets"] == "KRAS_G12D,EGFR_KINASE,HIV1_PROTEASE"
    assert profile["require_ood_eval"] is True
    assert profile["stage6_top_level_reentry_metadata"]["downstream_evidence_scope"] == "supporting_only"
    assert profile["stage6_top_level_reentry_metadata"]["base_profile_path"] == "config/ligand_htvs_nightly_strict_v1.json"
    assert profile["stage6_top_level_reentry_metadata"]["top_level_targets"] == "KRAS_G12D,EGFR_KINASE,HIV1_PROTEASE"
    assert profile["stage6_top_level_reentry_metadata"]["downstream_target_subset"] == "HIV1_PROTEASE"
    assert profile["stage6_top_level_reentry_metadata"]["promotion_allowed"] is False
    assert profile["stage6_top_level_reentry_metadata"]["top_level_pass_override_allowed"] is False
    assert profile["run_scope"] == "smoke_then_full"

    md = mod._markdown(payload)
    assert "python3 tools/run_ligand_htvs_nightly.py --profile-json runs/nightly_stage6_top_level_reentry_profile_current.json" in md
    assert "--run-scope smoke_then_full" in md
    assert "--targets KRAS_G12D,EGFR_KINASE,HIV1_PROTEASE" in md
    assert "supporting-only" in md


def test_reentry_packet_blocks_when_top_level_did_not_fail_stage6() -> None:
    top_level = _top_level_stage6_failure()
    top_level["failed_stage"] = "stage3_backmapping_scoring"

    payload = mod.build_payload(
        top_level_payload=top_level,
        top_level_summary_artifact="runs/ligand_htvs_nightly_2026-04-26_summary.json",
        base_profile_payload=_strict_base_profile(),
        downstream_rerun_payload={
            "summary": {
                "gate_distance_override_csv_artifact": "runs/nightly_stage6_downstream_rerun_gate_override_current.csv",
                "gate_distance_override_row_count": 1,
                "target_subset": "HIV1_PROTEASE",
            }
        },
        execute_result_payload=_execute_result_packet(),
        gate_distance_override_rows=[{"row_key": "HIV1_PROTEASE::imatinib"}],
    )

    summary = payload["summary"]
    assert summary["ready_for_top_level_reentry"] is False
    assert summary["promotion_allowed"] is False
    assert summary["pass"] is False
    assert "top-level summary failed at `stage3_backmapping_scoring`, not `stage6_operational_gate`" in summary["blockers"]


def test_reentry_packet_blocks_if_base_profile_relaxes_top_level_invariants() -> None:
    relaxed_profile = _strict_base_profile()
    relaxed_profile["targets"] = "HIV1_PROTEASE"
    relaxed_profile["run_scope"] = "smoke"
    relaxed_profile["require_ood_eval"] = False
    relaxed_profile["gate"] = {
        "enforce_operational_gate": False,
        "strict_fail_fast": False,
        "max_mean_min_distance_A": 3.0,
    }

    payload = mod.build_payload(
        top_level_payload=_top_level_stage6_failure(),
        top_level_summary_artifact="runs/ligand_htvs_nightly_2026-04-26_summary.json",
        base_profile_payload=relaxed_profile,
        downstream_rerun_payload={
            "summary": {
                "gate_distance_override_csv_artifact": "runs/nightly_stage6_downstream_rerun_gate_override_current.csv",
                "gate_distance_override_row_count": 1,
                "target_subset": "HIV1_PROTEASE",
            }
        },
        execute_result_payload=_execute_result_packet(),
        gate_distance_override_rows=[{"row_key": "HIV1_PROTEASE::imatinib"}],
    )

    summary = payload["summary"]
    assert summary["ready_for_top_level_reentry"] is False
    assert summary["promotion_allowed"] is False
    assert "base profile run_scope is `smoke`, not `smoke_then_full`" in summary["blockers"]
    assert "base profile does not require OOD evaluation" in summary["blockers"]
    assert "base profile does not enforce the operational gate" in summary["blockers"]
    assert "base profile does not keep strict fail-fast enabled" in summary["blockers"]
    assert "base profile gate threshold differs from the failed top-level stage6 threshold" in summary["blockers"]
