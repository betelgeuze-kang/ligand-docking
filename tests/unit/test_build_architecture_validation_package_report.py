from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_architecture_validation_package_report as report_mod
from tools.product import build_architecture_validation_public_benchmark_subset_manifests as subset_mod
from tools.product import build_architecture_validation_speedpack_ab_retrospective as speedpack_mod
from tools.product import build_competition_benchmark_rollup as competition_mod


def test_subset_manifest_builder_ready(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(subset_mod, "ROOT", tmp_path)
    full = tmp_path / "runs/pdbbind_casf_pose_affinity_benchmark_results_current.csv"
    bm5 = tmp_path / "runs/protein_protein_docking_benchmark_v5_benchmark_results_current.csv"
    full.parent.mkdir(parents=True)
    full.write_text("suite_id,target_id,pass\npdbbind,T1,1\n", encoding="utf-8")
    bm5.write_text("suite_id,target_id,pass\nbm5,T1,1\n", encoding="utf-8")
    payload = subset_mod.build_public_benchmark_subset_manifests(subset_size=1)
    assert payload["summary"]["pdbbind_casf_subset_ready"] is True
    assert payload["summary"]["bm5_subset_ready"] is True


def test_speedpack_retrospective_claim_safe_when_artifacts_present(monkeypatch) -> None:
    payload = speedpack_mod.build_architecture_validation_speedpack_ab_retrospective()
    summary = payload["summary"]
    assert summary["task_count"] == 2
    assert summary["claim_safe"] is True


def test_competition_rollup_creates_intake_template(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(competition_mod, "ROOT", tmp_path)
    intake = tmp_path / "runs/cameo_official_results_operator_intake.csv"
    payload = competition_mod.build_competition_benchmark_rollup(intake_csv=str(intake))
    assert intake.exists()
    assert payload["summary"]["cameo_official_intake_row_count"] == 0


def test_package_report_marks_a_complete_when_fixtures_green(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(report_mod, "ROOT", tmp_path)
    runs = tmp_path / "runs"
    runs.mkdir()
    bundle = tmp_path / "runs/local_delivery/bundle_product_gpcr_adrb2"
    bundle.mkdir(parents=True)
    (bundle / "validation.json").write_text(
        json.dumps({"overall_ok": True, "delivery_ready_policy_ok": True}) + "\n",
        encoding="utf-8",
    )

    fixtures = {
        "product_gpcr_adrb2_after_approval_summary.json": {"pass": True},
        "gpcr_a1_independent_repeat_packet_current.json": {
            "summary": {
                "independent_repeat_result_passed": True,
                "ranking_pr_auc_ci_low": 0.76,
                "ranking_pr_auc": 0.87,
            }
        },
        "external_validation_2026-05-11_ligand_speedpack_ab_v4_set1_core_blind_ion_trpv1_chembl20_full_p0_n10000_r1_stage5_ranking_summary.json": {
            "pass": True,
            "metrics": {"pr_auc": 0.94},
        },
        "external_validation_2026-05-12_scaleup_1m_pilot_v1_ligandonly_enum4_csvfast_gpu_set1_core_blind_kinase_core_full_p0_n1000000_r1_stage5_ranking_summary.json": {
            "pass": True,
            "metrics": {"pr_auc": 1.0},
        },
        "product_public_benchmark_contract_current.json": {
            "summary": {"ready_required_suite_count": 5, "required_suite_count": 5, "public_benchmark_validation_ready": True},
            "rows": [{"status": "ready"}] * 5,
        },
        "public_benchmark_residual_assist_comparison_gate_current.json": {
            "summary": {"assist_comparison_gate_ready": True}
        },
        "residual_energy_force_label_validation_current.json": {
            "summary": {"status": "residual_energy_force_label_validation_ready", "spearman_reference_vs_energy_proxy": 0.39}
        },
        "residual_shadow_ab_current.json": {"summary": {"no_customer_facing_ranking_change": True}},
        "api_docking_dispatch_e2e_evidence_current.json": {"ledger_worker_state": "completed_fail_closed"},
        "local_delivery_verdict_gate_current.json": {"summary": {"delivery_ready": True, "verdict": "delivery_ready"}},
        "architecture_validation_public_benchmark_subset_manifests_current.json": {
            "summary": {"pdbbind_casf_subset_ready": True, "bm5_subset_ready": True, "pdbbind_casf_subset_row_count": 1, "bm5_subset_row_count": 1, "bm5_proxy_disclaimer_present": True}
        },
        "architecture_validation_speedpack_ab_retrospective_current.json": {"summary": {"claim_safe": True}},
        "accuracy_parity_scorecard_current.json": {"summary": {"status": "green"}},
        "biorxiv_external_validation_audit_current.json": {"pass": True},
        "competition_benchmark_rollup_current.json": {
            "summary": {
                "cameo_api_dependency_ready": True,
                "cameo_receiver_smoke_ready": True,
                "cameo_format_validation_ready": True,
                "cameo_model1_selection_ready": True,
                "cameo_dry_run_handoff_ready": True,
                "cameo_official_results_used": False,
                "cameo_official_intake_row_count": 0,
                "cameo_validation_status": "cameo_validation_pending_official_results",
                "casp_strict_blind_first_slot_ready": False,
                "casp_strict_blind_blocked_check_count": 3,
            }
        },
    }
    for name, payload in fixtures.items():
        (runs / name).write_text(json.dumps(payload) + "\n", encoding="utf-8")

    casp = tmp_path / "casp17"
    casp.mkdir()
    (casp / "casp17_historical_winner_normalized_bands_current.json").write_text(
        json.dumps({"rows": [{"band_status": "blocked_input"}]}) + "\n",
        encoding="utf-8",
    )

    report = report_mod.build_architecture_validation_package_report()
    summary = report["summary"]
    assert summary["package_a_complete"] is True
    assert summary["package_b_complete"] is True
    assert summary["package_c_complete"] is True
