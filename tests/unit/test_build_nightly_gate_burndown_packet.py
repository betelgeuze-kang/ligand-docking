from __future__ import annotations

import json
from pathlib import Path

from tools import build_nightly_gate_burndown_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_nightly_gate_burndown_packet() -> None:
    payload = mod.build_payload(
        latest_nightly_payload={
            "pass": False,
            "failed_stage": "stage6_operational_gate",
            "service_result": {"error_code": "HTVS_GATE_FAILED"},
            "stages": {
                "stage6_operational_gate": {
                    "failed_metrics": [
                        {
                            "metric": "mean_min_distance_A",
                            "value": 2.655165582969785,
                            "threshold": 2.5,
                        }
                    ],
                    "mean_min_distance_A_source": "eval_unique_topk",
                    "mean_min_distance_A_topk_k": 4,
                    "min_frames_observed": 100,
                    "ranking_auc": 1.0,
                    "ranking_pr_auc": 1.0,
                    "ranking_ef1": 2.0,
                    "ranking_bedroc": 1.0,
                    "ranking_ece": 0.2486282314925614,
                    "ranking_topk_hit_rate": 0.5,
                    "ranking_positive_count": 2,
                    "ranking_ood_positive_count": 3,
                }
            },
        },
        latest_nightly_artifact="runs/ligand_htvs_nightly_2026-04-21_summary.json",
        stage2_payload={
            "queue_rows": 72,
            "ok_rows": 72,
            "failed_rows": 0,
            "aborted_early": False,
            "writer_backpressure_count": 1,
            "backend_counts": {"rust_hip_rollout": 72},
        },
        stage2_artifact="runs/ligand_htvs_nightly_2026-04-21_stage2_traj_summary.json",
        stage5_payload={
            "score_col": "binding_energy_mmpbsa_kcal_mol_proxy",
            "probability_score_col": "binding_energy_mmpbsa_kcal_mol_calibrated",
            "lower_better": True,
            "distance_topk_k": 4,
        },
        stage5_artifact="runs/ligand_htvs_nightly_2026-04-21_stage5_ranking_summary.json",
        recent_nightly_payloads=[
            {"failed_stage": "stage2_trajectory_generation"},
            {"failed_stage": "stage2_trajectory_generation"},
            {"failed_stage": "stage6_operational_gate"},
        ],
        recent_nightly_artifacts=[
            "runs/ligand_htvs_nightly_2026-04-19_summary.json",
            "runs/ligand_htvs_nightly_2026-04-20_summary.json",
            "runs/ligand_htvs_nightly_2026-04-21_summary.json",
        ],
        stage4_score_rows=[
            {
                "queue_id": "HIV1_PROTEASE__rep0022__imatinib",
                "target": "HIV1_PROTEASE",
                "ligand_id": "imatinib",
                "mean_min_distance_A": "2.854198453426361",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-1.963563206411144",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-4.969062505780706",
            },
            {
                "queue_id": "HIV1_PROTEASE__rep0004__imatinib",
                "target": "HIV1_PROTEASE",
                "ligand_id": "imatinib",
                "mean_min_distance_A": "2.356958012580872",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-1.5880179996348098",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-7.011881868916186",
            },
            {
                "queue_id": "EGFR_KINASE__rep0014__imatinib",
                "target": "EGFR_KINASE",
                "ligand_id": "imatinib",
                "mean_min_distance_A": "2.346887",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-1.700000",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-8.000000",
            },
            {
                "queue_id": "EGFR_KINASE__rep0008__aspirin",
                "target": "EGFR_KINASE",
                "ligand_id": "aspirin",
                "mean_min_distance_A": "2.911203",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.800000",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-2.900000",
            },
            {
                "queue_id": "HIV1_PROTEASE__rep0012__aspirin",
                "target": "HIV1_PROTEASE",
                "ligand_id": "aspirin",
                "mean_min_distance_A": "2.880313",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.950000",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-0.780000",
            },
        ],
        stage5_unique_rows=[
            {
                "target": "HIV1_PROTEASE",
                "ligand_id": "imatinib",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-1.7507244479484407",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-6.391578484779369",
                "is_binder": "1",
                "mean_min_distance_A": "2.70565606713295",
                "reference_binding_kcal_mol": "-5.4",
            },
            {
                "target": "EGFR_KINASE",
                "ligand_id": "imatinib",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-1.6939277539930357",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-8.043462065672518",
                "is_binder": "1",
                "mean_min_distance_A": "2.352404837012291",
                "reference_binding_kcal_mol": "-7.4",
            },
            {
                "target": "HIV1_PROTEASE",
                "ligand_id": "aspirin",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.9406890113751696",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-0.7818180237087484",
                "is_binder": "0",
                "mean_min_distance_A": "2.658669866025448",
                "reference_binding_kcal_mol": "-1.0",
            },
            {
                "target": "EGFR_KINASE",
                "ligand_id": "aspirin",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.8100479932772944",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-2.944735548293929",
                "is_binder": "0",
                "mean_min_distance_A": "2.9039315617084505",
                "reference_binding_kcal_mol": "-1.1",
            },
        ],
    )

    summary = payload["summary"]
    assert summary["packet_ready"] is True
    assert summary["status"] == "nightly_gate_burndown_ready"
    assert summary["stage2_recovered"] is True
    assert summary["stage6_gate_failed"] is True
    assert summary["primary_gate_metric"] == "mean_min_distance_A"
    assert round(summary["primary_gate_delta"], 3) == 0.155
    assert summary["primary_gate_source"] == "eval_unique_topk"
    assert summary["primary_gate_topk_k"] == 4
    assert summary["recent_stage6_fail_count"] == 1
    assert "stage2 is recovered" in summary["status_line"]
    assert "nightly_gate_burndown_packet_current.md" in summary["next_required_step"]
    assert summary["reentry_blocker_stage"] == "stage6_operational_gate"
    assert "reached stage6" in summary["reentry_reason"]
    assert "failed the operational gate" in summary["reentry_reason"]
    assert "reduce the failed gate metrics" in summary["reentry_action"]
    assert "before the canonical top-level nightly reached stage6" not in summary["reentry_reason"]
    assert "2026-04-19:stage2_trajectory_generation" in summary["recent_transition_line"]
    assert "2026-04-21:stage6_operational_gate" in summary["recent_transition_line"]
    assert payload["rows"][0]["metric"] == "mean_min_distance_A"
    assert round(payload["rows"][0]["delta_over_threshold"], 3) == 0.155
    assert summary["culprit_band_source_label"] == "eval_unique_topk(4)"
    assert summary["culprit_band_row_count"] == 4
    assert summary["culprit_band_member_pass_count_at_current_gate"] == 1
    assert summary["culprit_band_worst_key"] == "EGFR_KINASE::aspirin"
    assert "EGFR_KINASE/aspirin" in summary["execution_recommendation"]
    assert "HIV1_PROTEASE/imatinib" in summary["execution_recommendation"]
    culprit_rows = [row for row in payload["rows"] if row.get("row_kind") == "culprit_band_member"]
    assert len(culprit_rows) == 4
    assert culprit_rows[0]["band_key"] == "HIV1_PROTEASE::imatinib"
    assert culprit_rows[-1]["band_key"] == "EGFR_KINASE::aspirin"
    candidate_rows = [row for row in payload["rows"] if row.get("row_kind") == "threshold_candidate"]
    assert any(row["candidate_label"] == "current_gate" for row in candidate_rows)
    assert any(row["candidate_label"] == "band_mean_step_0.05" for row in candidate_rows)


def test_build_nightly_gate_burndown_packet_reads_stage6_from_smoke_scope() -> None:
    payload = mod.build_payload(
        latest_nightly_payload={
            "pass": False,
            "failed_stage": "smoke",
            "service_result": {"error_code": "HTVS_SMOKE_FAILED"},
            "stages": {
                "smoke": {
                    "failed_stage": "stage6_operational_gate",
                    "stages": {
                        "stage2_trajectory_generation": {
                            "queue_rows": 72,
                            "ok_rows": 72,
                            "failed_rows": 0,
                            "aborted_early": False,
                            "writer_backpressure_count": 1,
                        },
                        "stage6_operational_gate": {
                            "failed_metrics": [
                                {
                                    "metric": "mean_min_distance_A",
                                    "value": 2.655771412402392,
                                    "threshold": 2.5,
                                }
                            ],
                            "mean_min_distance_A_source": "eval_unique_topk",
                            "mean_min_distance_A_topk_k": 4,
                            "min_frames_observed": 100,
                            "ranking_auc": 1.0,
                            "ranking_pr_auc": 1.0,
                            "ranking_ef1": 2.0,
                            "ranking_bedroc": 1.0,
                            "ranking_ece": 0.2576421265845267,
                            "ranking_topk_hit_rate": 0.5,
                            "ranking_positive_count": 2,
                            "ranking_ood_positive_count": 3,
                        },
                    },
                }
            },
        },
        latest_nightly_artifact="runs/ligand_htvs_nightly_2026-04-22_summary.json",
        stage2_payload={},
        stage2_artifact="runs/ligand_htvs_nightly_2026-04-22_smoke_stage2_traj_summary.json",
        stage5_payload={
            "score_col": "binding_energy_mmpbsa_kcal_mol_proxy",
            "probability_score_col": "binding_energy_mmpbsa_kcal_mol_calibrated",
            "lower_better": True,
            "distance_topk_k": 4,
        },
        stage5_artifact="runs/ligand_htvs_nightly_2026-04-22_smoke_stage5_ranking_summary.json",
        recent_nightly_payloads=[
            {"failed_stage": "stage2_trajectory_generation"},
            {"failed_stage": "stage6_operational_gate"},
            {"failed_stage": "smoke", "stages": {"smoke": {"failed_stage": "stage6_operational_gate"}}},
        ],
        recent_nightly_artifacts=[
            "runs/ligand_htvs_nightly_2026-04-20_summary.json",
            "runs/ligand_htvs_nightly_2026-04-21_summary.json",
            "runs/ligand_htvs_nightly_2026-04-22_summary.json",
        ],
        stage4_score_rows=[
            {
                "queue_id": "HIV1_PROTEASE__rep0022__imatinib",
                "target": "HIV1_PROTEASE",
                "ligand_id": "imatinib",
                "mean_min_distance_A": "2.854198453426361",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-1.963563206411144",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-4.969062505780706",
            },
            {
                "queue_id": "HIV1_PROTEASE__rep0004__imatinib",
                "target": "HIV1_PROTEASE",
                "ligand_id": "imatinib",
                "mean_min_distance_A": "2.356958012580872",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-1.5880179996348098",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-7.011881868916186",
            },
            {
                "queue_id": "EGFR_KINASE__rep0014__imatinib",
                "target": "EGFR_KINASE",
                "ligand_id": "imatinib",
                "mean_min_distance_A": "2.346887",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-1.700000",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-8.000000",
            },
            {
                "queue_id": "EGFR_KINASE__rep0008__aspirin",
                "target": "EGFR_KINASE",
                "ligand_id": "aspirin",
                "mean_min_distance_A": "2.911203",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.800000",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-2.900000",
            },
            {
                "queue_id": "HIV1_PROTEASE__rep0012__aspirin",
                "target": "HIV1_PROTEASE",
                "ligand_id": "aspirin",
                "mean_min_distance_A": "2.880313",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.950000",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-0.780000",
            },
        ],
        stage5_unique_rows=[
            {
                "target": "HIV1_PROTEASE",
                "ligand_id": "imatinib",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-1.7507244479484407",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-6.391578484779369",
                "is_binder": "1",
                "mean_min_distance_A": "2.70565606713295",
                "reference_binding_kcal_mol": "-5.4",
            },
            {
                "target": "EGFR_KINASE",
                "ligand_id": "imatinib",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-1.6939277539930357",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-8.043462065672518",
                "is_binder": "1",
                "mean_min_distance_A": "2.352404837012291",
                "reference_binding_kcal_mol": "-7.4",
            },
            {
                "target": "HIV1_PROTEASE",
                "ligand_id": "aspirin",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.9406890113751696",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-0.7818180237087484",
                "is_binder": "0",
                "mean_min_distance_A": "2.658669866025448",
                "reference_binding_kcal_mol": "-1.0",
            },
            {
                "target": "EGFR_KINASE",
                "ligand_id": "aspirin",
                "binding_energy_mmpbsa_kcal_mol_proxy": "-0.8100479932772944",
                "binding_energy_mmpbsa_kcal_mol_calibrated": "-2.944735548293929",
                "is_binder": "0",
                "mean_min_distance_A": "2.9039315617084505",
                "reference_binding_kcal_mol": "-1.1",
            },
        ],
    )

    summary = payload["summary"]
    assert summary["status"] == "nightly_gate_burndown_ready"
    assert summary["stage2_recovered"] is True
    assert summary["primary_gate_metric"] == "mean_min_distance_A"
    assert round(summary["primary_gate_value"], 3) == 2.656
    assert round(summary["primary_gate_delta"], 3) == 0.156
    assert summary["recent_stage6_fail_count"] == 2


def test_build_nightly_gate_burndown_packet_keeps_top_level_fail_with_downstream_execute_pass() -> None:
    payload = mod.build_payload(
        latest_nightly_payload={
            "pass": False,
            "failed_stage": "stage6_operational_gate",
            "service_result": {"error_code": "HTVS_GATE_FAILED"},
            "stages": {
                "stage6_operational_gate": {
                    "failed_metrics": [
                        {
                            "metric": "mean_min_distance_A",
                            "value": 2.7,
                            "threshold": 2.5,
                        }
                    ],
                    "mean_min_distance_A_source": "eval_unique_topk",
                    "mean_min_distance_A_topk_k": 4,
                },
                "stage6_downstream_execute": {
                    "summary": {
                        "packet_artifact": "runs/nightly_stage6_execute_result_packet_current.md",
                        "execute_status_json_artifact": "runs/nightly_stage6_downstream_execute_current_status.json",
                        "execute_pipeline_summary_json_artifact": "runs/nightly_stage6_downstream_execute_current_summary.json",
                        "execute_gate_pass": True,
                        "execute_payload_pass": True,
                        "execute_matches_rescored_gate": True,
                    }
                },
            },
        },
        latest_nightly_artifact="runs/ligand_htvs_nightly_2026-04-23_summary.json",
        stage2_payload={
            "queue_rows": 72,
            "ok_rows": 72,
            "failed_rows": 0,
            "aborted_early": False,
        },
        stage2_artifact="runs/ligand_htvs_nightly_2026-04-23_stage2_traj_summary.json",
        stage5_payload={},
        stage5_artifact="runs/ligand_htvs_nightly_2026-04-23_stage5_ranking_summary.json",
        recent_nightly_payloads=[{"pass": False, "failed_stage": "stage6_operational_gate"}],
        recent_nightly_artifacts=["runs/ligand_htvs_nightly_2026-04-23_summary.json"],
        stage4_score_rows=[],
        stage5_unique_rows=[],
    )

    summary = payload["summary"]
    assert summary["status"] == "nightly_gate_burndown_ready"
    assert summary["downstream_execute_pass_evidence"] is True
    assert summary["downstream_execute_payload_pass"] is True
    assert summary["downstream_execute_gate_pass"] is True
    assert summary["downstream_execute_matches_rescored_gate"] is True
    assert summary["downstream_execute_packet_artifact"] == "runs/nightly_stage6_execute_result_packet_current.md"
    assert "scoped follow-on evidence" in summary["top_level_failure_explanation"]
    assert "latest_nightly.pass is false" in summary["top_level_failure_explanation"]
    assert "do not promote" in summary["next_required_step"]


def test_build_nightly_gate_burndown_packet_reads_queue_downstream_evidence_without_promoting_top_level() -> None:
    payload = mod.build_payload(
        latest_nightly_payload={
            "pass": False,
            "failed_stage": "stage3_backmapping_scoring",
            "service_result": {"error_code": "HTVS_SMOKE_FAILED"},
            "stages": {},
        },
        latest_nightly_artifact="runs/ligand_htvs_nightly_2026-04-25_summary.json",
        stage2_payload={
            "queue_rows": 72,
            "ok_rows": 72,
            "failed_rows": 0,
            "aborted_early": False,
        },
        stage2_artifact="runs/ligand_htvs_nightly_2026-04-25_stage2_traj_summary.json",
        stage5_payload={},
        stage5_artifact="runs/ligand_htvs_nightly_2026-04-25_stage5_ranking_summary.json",
        recent_nightly_payloads=[{"pass": False, "failed_stage": "stage3_backmapping_scoring"}],
        recent_nightly_artifacts=["runs/ligand_htvs_nightly_2026-04-25_summary.json"],
        stage4_score_rows=[],
        stage5_unique_rows=[],
        supporting_evidence_payloads=[
            (
                "runs/local_engine_commercialization_queue_current.json",
                {
                    "summary": {
                        "nightly_stage6_execute_gate_pass": True,
                        "nightly_stage6_execute_payload_pass": True,
                        "nightly_stage6_execute_matches_rescored_gate": True,
                        "nightly_stage6_execute_gate_mean_min_distance_A": "2.268931970372796",
                        "nightly_stage6_execute_artifact": "runs/nightly_stage6_execute_result_packet_current.md",
                        "nightly_stage6_execute_status_json_artifact": (
                            "runs/nightly_stage6_downstream_execute_current_status.json"
                        ),
                    }
                },
            )
        ],
    )

    summary = payload["summary"]
    assert summary["status"] == "waiting_for_stage6_reentry"
    assert summary["downstream_execute_pass_evidence"] is True
    assert summary["downstream_execute_gate_pass"] is True
    assert summary["downstream_execute_metric"] == "2.268931970372796"
    assert summary["downstream_execute_source_artifact"] == "runs/local_engine_commercialization_queue_current.json"
    assert summary["downstream_execute_packet_artifact"] == "runs/nightly_stage6_execute_result_packet_current.md"
    assert "scoped follow-on evidence" in summary["top_level_failure_explanation"]
    assert "Recover `stage3_backmapping_scoring`" in summary["next_required_step"]
    assert "do not promote" in summary["next_required_step"]
    assert summary["reentry_blocker_stage"] == "stage3_backmapping_scoring"
    assert "stage3_backmapping_scoring" in summary["reentry_reason"]
    assert "canonical top-level nightly" in summary["reentry_action"]
    assert summary["reentry_evidence_artifact"] == "runs/ligand_htvs_nightly_2026-04-25_summary.json"
    assert "runs/local_engine_commercialization_queue_current.json" in payload["structured"]["source_artifacts"]


def test_build_nightly_gate_burndown_packet_surfaces_stage3_reentry_import_failure(tmp_path: Path) -> None:
    latest = tmp_path / "ligand_htvs_nightly_2026-04-26_summary.json"
    latest.write_text("{}", encoding="utf-8")

    payload = mod.build_payload(
        latest_nightly_payload={
            "pass": False,
            "failed_stage": "smoke",
            "service_result": {"error_code": "HTVS_SMOKE_FAILED"},
            "stages": {
                "smoke": {
                    "failed_stage": "stage3_backmapping_scoring",
                    "stages": {
                        "stage2_trajectory_generation": {
                            "queue_rows": 72,
                            "ok_rows": 72,
                            "failed_rows": 0,
                            "aborted_early": False,
                        },
                        "stage3_backmapping_scoring": {
                            "ok": False,
                            "returncode": 1,
                            "cmd_str": "python3 tools/run_ligand_backmapping_scoring.py --score-only",
                            "stderr_tail": "ModuleNotFoundError: No module named 'tools'",
                        },
                    },
                }
            },
        },
        latest_nightly_artifact=str(latest),
        stage2_payload={},
        stage2_artifact=str(tmp_path / "ligand_htvs_nightly_2026-04-26_smoke_stage2_traj_summary.json"),
        stage5_payload={},
        stage5_artifact=str(tmp_path / "ligand_htvs_nightly_2026-04-26_stage5_ranking_summary.json"),
        recent_nightly_payloads=[{"pass": False, "failed_stage": "smoke", "stages": {"smoke": {"failed_stage": "stage3_backmapping_scoring"}}}],
        recent_nightly_artifacts=[str(latest)],
        stage4_score_rows=[],
        stage5_unique_rows=[],
    )

    summary = payload["summary"]
    assert summary["status"] == "waiting_for_stage6_reentry"
    assert summary["stage2_recovered"] is True
    assert summary["reentry_blocker_stage"] == "stage3_backmapping_scoring"
    assert "import bootstrap failed" in summary["reentry_reason"]
    assert "stage3 backmapping/scoring" in summary["reentry_action"]
    assert "supporting-only" in summary["reentry_action"]
    assert "run_ligand_backmapping_scoring.py" in summary["reentry_command"]
    assert "No module named 'tools'" in summary["reentry_stderr_tail"]
    assert "stage3_backmapping_scoring" in summary["status_line"]
    assert "stage reentry evidence" in summary["next_required_step"]


def test_build_nightly_gate_burndown_packet_marks_existing_stage3_reentry_artifact_as_rerun_needed(
    tmp_path: Path,
) -> None:
    latest = tmp_path / "ligand_htvs_nightly_2026-04-26_summary.json"
    latest.write_text("{}", encoding="utf-8")
    stage3 = tmp_path / "ligand_htvs_nightly_2026-04-26_smoke_stage3_summary.json"
    stage3.write_text('{"score_only": true}', encoding="utf-8")

    payload = mod.build_payload(
        latest_nightly_payload={
            "pass": False,
            "failed_stage": "smoke",
            "service_result": {"error_code": "HTVS_SMOKE_FAILED"},
            "stages": {
                "smoke": {
                    "failed_stage": "stage3_backmapping_scoring",
                    "stages": {
                        "stage3_backmapping_scoring": {
                            "ok": False,
                            "returncode": 1,
                            "stderr_tail": "ModuleNotFoundError: No module named 'tools'",
                        },
                    },
                }
            },
        },
        latest_nightly_artifact=str(latest),
        stage2_payload={},
        stage2_artifact=str(tmp_path / "ligand_htvs_nightly_2026-04-26_smoke_stage2_traj_summary.json"),
        stage5_payload={},
        stage5_artifact=str(tmp_path / "ligand_htvs_nightly_2026-04-26_stage5_ranking_summary.json"),
        recent_nightly_payloads=[
            {"pass": False, "failed_stage": "smoke", "stages": {"smoke": {"failed_stage": "stage3_backmapping_scoring"}}}
        ],
        recent_nightly_artifacts=[str(latest)],
        stage4_score_rows=[],
        stage5_unique_rows=[],
    )

    summary = payload["summary"]
    assert summary["status"] == "waiting_for_stage6_reentry"
    assert summary["reentry_evidence_artifact"] == str(stage3)
    assert "fresh stage3 reentry artifact now exists" in summary["reentry_reason"]
    assert "Rerun the canonical top-level smoke/full nightly" in summary["reentry_action"]
    assert "stage reentry evidence" in summary["next_required_step"]
    assert "promotion blocker" in summary["next_required_step"]


def test_discovers_suffixed_top_level_reentry_summary_without_child_summaries(tmp_path: Path, monkeypatch) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setattr(mod, "RUNS", runs)

    old_top = runs / "ligand_htvs_nightly_2026-04-26_summary.json"
    strict_reentry = runs / "ligand_htvs_nightly_2026-04-26_stage6_top_level_reentry_summary.json"
    smoke_child = runs / "ligand_htvs_nightly_2026-04-26_stage6_top_level_reentry_smoke_summary.json"
    full_child = runs / "ligand_htvs_nightly_2026-04-26_stage6_top_level_reentry_full_summary.json"
    attempt_child = runs / "ligand_htvs_nightly_2026-04-26_stage6_top_level_reentry_attempt1_summary.json"
    stage_child = runs / "ligand_htvs_nightly_2026-04-26_smoke_stage3_summary.json"
    tagged_gpu_rerun = runs / "ligand_htvs_nightly_2026-04-26_goal_closure_summary.json"

    _write_json(
        old_top,
        {
            "generated_at_local": "2026-04-26T04:30:33",
            "run_scope": "smoke_then_full",
            "pass": False,
            "failed_stage": "smoke",
            "stages": {"smoke": {"failed_stage": "stage6_operational_gate"}},
            "artifacts": {"smoke_summary_json": "runs/old_smoke.json", "full_summary_json": "runs/old_full.json"},
        },
    )
    _write_json(
        strict_reentry,
        {
            "generated_at_local": "2026-04-26T04:48:47",
            "run_scope": "smoke_then_full",
            "pass": True,
            "failed_stage": None,
            "stages": {"smoke": {"pass": True}, "full": {"pass": True}},
            "artifacts": {"smoke_summary_json": "runs/reentry_smoke.json", "full_summary_json": "runs/reentry_full.json"},
        },
    )
    for child in (smoke_child, full_child, attempt_child, stage_child):
        _write_json(
            child,
            {
                "generated_at_local": "2026-04-26T05:00:00",
                "run_scope": "smoke",
                "pass": True,
                "stages": {"stage6_operational_gate": {"pass": True}},
            },
        )
    _write_json(
        tagged_gpu_rerun,
        {
            "generated_at_local": "2026-04-26T05:15:00",
            "run_scope": "smoke",
            "pass": True,
            "failed_stage": None,
            "service_result": {"status": "ok", "error_code": "HTVS_OK"},
            "stages": {
                "stage2_trajectory_generation": {"pass": True},
                "stage6_operational_gate": {"pass": True},
            },
        },
    )

    assert mod._discover_latest_top_nightly() == tagged_gpu_rerun
    assert [path.name for path in mod._recent_top_nightly_paths(limit=5)] == [
        old_top.name,
        strict_reentry.name,
        tagged_gpu_rerun.name,
    ]
