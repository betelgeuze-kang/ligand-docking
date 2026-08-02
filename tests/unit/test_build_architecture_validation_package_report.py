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
    assert payload["summary"]["cameo_official_intake_gate_status"] == (
        "blocked_cameo_official_results_intake"
    )
    assert payload["summary"]["cameo_official_intake_gate_ready"] is False
    assert payload["summary"]["cameo_official_result_intake_status"] == (
        "blocked_cameo_official_results_intake"
    )
    assert payload["summary"]["cameo_official_result_intake_ready"] is False
    assert payload["summary"]["cameo_official_result_intake_claim_allowed"] is False
    assert payload["summary"]["cameo_official_result_intake_fetch_enabled"] is False
    assert payload["summary"]["cameo_official_result_intake_external_state_mutated"] is False
    assert payload["summary"]["cameo_official_result_intake_local_native_accuracy_used"] is False
    assert payload["summary"]["cameo_official_result_row_count"] == 0
    assert payload["summary"]["cameo_official_accepted_result_count"] == 0
    assert payload["summary"]["cameo_official_blocker_count"] == 2
    assert payload["summary"]["cameo_official_operator_action_required_count"] == 2
    assert payload["summary"]["cameo_official_operator_action_required_row_count"] == 0
    assert payload["summary"]["cameo_official_primary_blocker_code"] == (
        "official_result_rows_missing"
    )
    assert payload["summary"]["cameo_official_primary_required_action"] == (
        "Fill at least one official CAMEO result row in the operator intake CSV."
    )
    assert payload["summary"]["cameo_official_missing_required_column_count"] == 8
    assert "official_result_rows_missing" in payload["summary"]["cameo_official_blocker_codes"]
    assert "official_cameo" in payload["summary"]["cameo_official_allowed_result_source_kinds"]
    assert payload["summary"]["cameo_official_source_provenance_ready_row_count"] == 0
    assert payload["summary"]["cameo_official_metric_ready_row_count"] == 0
    assert payload["summary"]["cameo_official_local_native_accuracy_blocker_count"] == 0
    assert payload["cameo_official_intake_gate_blockers"][0]["code"] == (
        "official_result_rows_missing"
    )
    assert payload["summary"]["casp16_ligand_source_manifest_ready"] is False
    assert payload["summary"]["casp16_ligand_competition_credibility_ready"] is False
    assert payload["summary"]["bm5_complex_benchmark_ready"] is False
    assert payload["summary"]["bm5_capri_complex_competition_credibility_ready"] is False
    assert payload["summary"]["competition_credibility_extension_ready"] is False
    assert payload["summary"]["competition_credibility_extension_blockers"] == [
        "casp16_ligand_source_manifest_not_ready",
        "casp16_ligand_materialization_not_ready",
        "casp16_ligand_scorecard_not_ready",
        "bm5_complex_benchmark_not_ready",
        "capri_score_set_not_ready",
    ]
    assert payload["summary"]["competition_credibility_extension_primary_blocker"] == (
        "casp16_ligand_source_manifest_not_ready"
    )
    assert payload["summary"]["competition_benchmark_custody_work_order_status"] == ""
    assert payload["summary"]["competition_benchmark_custody_work_order_ready"] is False
    assert payload["summary"]["competition_benchmark_custody_work_order_action_count"] == 0
    assert payload["summary"]["package_b_required_for_ligand_commercial_claims"] is True
    assert payload["summary"]["package_b_ligand_public_benchmark_foundation_ready"] is False
    assert payload["summary"]["package_b_claim_grade_public_benchmark_ready"] is False
    assert payload["summary"]["competition_ligand_commercial_claim_allowed"] is False
    assert payload["summary"]["competition_ligand_claim_blockers"] == [
        "casp16_ligand_competition_credibility_not_ready",
        "package_b_ligand_public_benchmark_foundation_not_ready",
        "package_b_claim_grade_public_benchmark_not_ready",
    ]
    rendered = competition_mod._render_status_markdown(payload)
    assert "Competition Benchmark Status" in rendered
    assert "CASP16 Ligand" in rendered
    assert "BM5/CAPRI Complex" in rendered
    assert "Package B Bridge" in rendered
    assert "Competition credibility evidence only" not in rendered
    assert "competition credibility evidence only" in rendered.lower()


def test_competition_rollup_computes_cameo_official_intake_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(competition_mod, "ROOT", tmp_path)
    intake = tmp_path / "runs/cameo_official_results_operator_intake.csv"
    intake.parent.mkdir(parents=True)
    intake.write_text(
        "target_id,candidate_id,cameo_model_rank,result_source_kind,result_source_url,result_record_id,retrieved_at_utc,assessment_date,lddt,tm_score,qs_score,rmsd_A\n"
        "CAMEO100,model1,1,official_cameo,https://cameo3d.org/modeling/CAMEO100,CAMEO100:model1,2026-06-03T00:00:00Z,2026-06-03,0.72,,,,\n",
        encoding="utf-8",
    )
    (tmp_path / "runs/product_public_benchmark_contract_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_public_benchmark_contract_ready",
                    "public_benchmark_validation_ready": True,
                    "required_suite_count": 5,
                    "ready_required_suite_count": 5,
                    "blocked_suite_count": 0,
                    "phase2_pdbbind_casf_pose_success_harness_ready": True,
                    "phase2_posebusters_style_validity_checks_ready": True,
                    "phase2_symmetry_aware_ligand_rmsd_ready": True,
                    "phase2_dude_or_lit_pcba_enrichment_ready": True,
                    "phase2_enrichment_ready_sources": (
                        "lit_pcba_virtual_screening;dude_z_decoy_smoke"
                    ),
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "runs/refine_tier_public_benchmark_readiness_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_refine_tier_public_benchmark_readiness",
                    "claim_grade_public_benchmark_ready": False,
                    "blocker_count": 6,
                    "blockers": ["insufficient_total_rows"],
                    "row_count": 0,
                    "valid_row_count": 0,
                    "pose_metric_pass_count": 0,
                    "free_energy_pair_count": 0,
                    "min_total_rows_required": 8,
                    "min_pose_rows_required": 5,
                    "min_free_energy_pairs_required": 5,
                    "external_state_mutated": False,
                    "next_required_step": "Fill Package B refine-tier evidence.",
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "runs/refine_tier_public_benchmark_work_order_apply_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_refine_tier_public_benchmark_work_order_apply",
                    "apply_ready": False,
                    "blocked_row_count": 8,
                    "metric_evidence_pass_row_count": 0,
                    "metric_evidence_blocked_row_count": 8,
                    "receptor_coordinate_validation_pass_row_count": 8,
                    "external_state_mutated": False,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = competition_mod.build_competition_benchmark_rollup(intake_csv=str(intake))
    summary = payload["summary"]

    assert summary["cameo_official_results_used"] is True
    assert summary["cameo_official_intake_gate_status"] == "cameo_official_results_intake_ready"
    assert summary["cameo_official_intake_gate_ready"] is True
    assert summary["cameo_official_result_intake_status"] == (
        "cameo_official_results_intake_ready"
    )
    assert summary["cameo_official_result_intake_ready"] is True
    assert summary["cameo_official_result_intake_claim_allowed"] is False
    assert summary["cameo_official_result_intake_fetch_enabled"] is False
    assert summary["cameo_official_result_intake_external_state_mutated"] is False
    assert summary["cameo_official_result_intake_local_native_accuracy_used"] is False
    assert summary["cameo_official_operator_intake_csv"] == str(intake)
    assert summary["cameo_official_result_row_count"] == 1
    assert summary["cameo_official_accepted_result_count"] == 1
    assert summary["cameo_official_rejected_result_count"] == 0
    assert summary["cameo_official_model1_result_ready"] is True
    assert summary["cameo_official_blocker_count"] == 0
    assert summary["cameo_official_blocker_codes"] == []
    assert summary["cameo_official_operator_action_required_count"] == 0
    assert summary["cameo_official_operator_action_required_row_count"] == 0
    assert summary["cameo_official_primary_blocker_code"] == ""
    assert summary["cameo_official_primary_required_action"] == ""
    assert summary["cameo_official_missing_required_columns"] == []
    assert "official_cameo" in summary["cameo_official_allowed_result_source_kinds"]
    assert summary["cameo_official_source_provenance_ready_row_count"] == 1
    assert summary["cameo_official_metric_ready_row_count"] == 1
    assert summary["cameo_official_local_native_accuracy_blocker_count"] == 0
    assert summary["cameo_official_native_local_accuracy_used"] is False
    assert summary["cameo_official_external_state_mutated"] is False
    assert summary["package_b_public_benchmark_contract_status"] == (
        "product_public_benchmark_contract_ready"
    )
    assert summary["package_b_ligand_public_benchmark_foundation_ready"] is True
    assert summary["package_b_enrichment_ready_sources"] == [
        "lit_pcba_virtual_screening",
        "dude_z_decoy_smoke",
    ]
    assert summary["package_b_refine_tier_public_benchmark_status"] == (
        "blocked_refine_tier_public_benchmark_readiness"
    )
    assert summary["package_b_claim_grade_public_benchmark_ready"] is False
    assert summary["competition_ligand_commercial_claim_allowed"] is False
    assert summary["competition_ligand_claim_package_b_dependency_ready"] is False
    assert summary["competition_ligand_claim_blockers"] == [
        "casp16_ligand_competition_credibility_not_ready",
        "package_b_claim_grade_public_benchmark_not_ready"
    ]


def test_competition_rollup_cli_writes_json_and_status_md(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(competition_mod, "ROOT", tmp_path)
    intake = tmp_path / "runs/cameo_official_results_operator_intake.csv"
    out_json = tmp_path / "runs/competition_benchmark_rollup_current.json"
    out_md = tmp_path / "docs/competition_benchmark_status_current.md"

    competition_mod.main(
        [
            "--intake-csv",
            str(intake),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_type"] == "competition_benchmark_rollup"
    text = out_md.read_text(encoding="utf-8")
    assert "Competition Benchmark Status" in text
    assert "CAMEO Official Intake" in text
    assert "CASP16 Ligand" in text
    assert "BM5/CAPRI Complex" in text
    assert "Package B Bridge" in text
    assert "Ligand commercial claim allowed by competition rollup" in text


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
                "cameo_official_intake_gate_status": "blocked_cameo_official_results_intake",
                "cameo_official_intake_gate_ready": False,
                "cameo_official_result_intake_ready": False,
                "cameo_official_intake_gate_artifact_path": (
                    "runs/cameo_official_results_intake_gate_current.json"
                ),
                "cameo_official_operator_intake_csv": (
                    "runs/cameo_official_results_operator_intake.csv"
                ),
                "cameo_official_operator_template_csv": (
                    "runs/cameo_official_results_operator_template_current.csv"
                ),
                "cameo_official_result_row_count": 0,
                "cameo_official_accepted_result_count": 0,
                "cameo_official_rejected_result_count": 0,
                "cameo_official_model1_result_ready": False,
                "cameo_official_blocker_count": 2,
                "cameo_official_blocker_codes": [
                    "official_result_required_columns_missing",
                    "official_result_rows_missing",
                ],
                "cameo_official_operator_action_required_count": 2,
                "cameo_official_operator_action_required_row_count": 0,
                "cameo_official_primary_blocker_code": "official_result_rows_missing",
                "cameo_official_primary_required_action": (
                    "Fill at least one official CAMEO result row in the operator intake CSV."
                ),
                "cameo_official_required_column_count": 8,
                "cameo_official_missing_required_column_count": 8,
                "cameo_official_missing_required_columns": ["target_id"],
                "cameo_official_allowed_result_source_kinds": [
                    "cameo_assessment",
                    "cameo_official",
                    "official_cameo",
                ],
                "cameo_official_source_provenance_ready_row_count": 0,
                "cameo_official_metric_ready_row_count": 0,
                "cameo_official_local_native_accuracy_blocker_count": 0,
                "cameo_official_native_local_accuracy_used": False,
                "cameo_official_external_state_mutated": False,
                "casp16_ligand_source_manifest_status": (
                    "blocked_casp16_ligand_competition_credibility"
                ),
                "casp16_ligand_source_manifest_ready": True,
                "casp16_ligand_materialization_ready": False,
                "casp16_ligand_scorecard_ready": False,
                "casp16_ligand_competition_credibility_ready": False,
                "casp16_ligand_pose_target_count": 233,
                "casp16_ligand_affinity_target_count": 140,
                "casp16_ligand_next_action": "Attach local CASP16 ligand receipts.",
                "bm5_capri_complex_source_manifest_status": (
                    "blocked_bm5_capri_complex_competition_credibility"
                ),
                "bm5_complex_benchmark_ready": True,
                "capri_score_set_ready": False,
                "bm5_capri_complex_competition_credibility_ready": False,
                "bm5_capri_complex_primary_metric": "CAPRI quality category",
                "bm5_capri_complex_next_action": "Attach CAPRI score_set receipts.",
                "competition_credibility_extension_ready": False,
                "competition_credibility_extension_blocker_count": 3,
                "competition_credibility_extension_blockers": [
                    "casp16_ligand_materialization_not_ready",
                    "casp16_ligand_scorecard_not_ready",
                    "capri_score_set_not_ready",
                ],
                "competition_credibility_extension_primary_blocker": (
                    "casp16_ligand_materialization_not_ready"
                ),
                "competition_credibility_extension_next_actions": [
                    "Attach local CASP16 ligand receipts.",
                    "Attach CAPRI score_set receipts.",
                ],
                "competition_credibility_extension_primary_next_action": (
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
                "package_b_required_for_ligand_commercial_claims": True,
                "package_b_public_benchmark_contract_status": (
                    "product_public_benchmark_contract_ready"
                ),
                "package_b_public_benchmark_validation_ready": True,
                "package_b_ligand_public_benchmark_foundation_ready": True,
                "package_b_ligand_suite_ids": [
                    "pdbbind_casf_pose_affinity",
                    "lit_pcba_virtual_screening",
                    "dude_z_decoy_smoke",
                ],
                "package_b_refine_tier_public_benchmark_status": (
                    "blocked_refine_tier_public_benchmark_readiness"
                ),
                "package_b_claim_grade_public_benchmark_ready": False,
                "package_b_claim_grade_blocker_count": 6,
                "package_b_claim_grade_blockers": ["insufficient_total_rows"],
                "package_b_refine_tier_work_order_apply_status": (
                    "blocked_refine_tier_public_benchmark_work_order_apply"
                ),
                "package_b_refine_tier_work_order_apply_ready": False,
                "competition_evidence_role": "competition_credibility_evidence_only",
                "competition_ligand_commercial_claim_allowed": False,
                "competition_ligand_claim_package_b_dependency_ready": False,
                "competition_ligand_claim_blocker_count": 2,
                "competition_ligand_claim_blockers": [
                    "casp16_ligand_competition_credibility_not_ready",
                    "package_b_claim_grade_public_benchmark_not_ready"
                ],
                "package_b_bridge_next_action": "Fill Package B refine-tier evidence.",
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
    assert summary["competition_benchmark_cameo_official_intake_gate_status"] == (
        "blocked_cameo_official_results_intake"
    )
    assert summary["competition_benchmark_cameo_official_result_intake_status"] == (
        "blocked_cameo_official_results_intake"
    )
    assert summary["competition_benchmark_cameo_official_result_intake_ready"] is False
    assert summary["competition_benchmark_cameo_official_result_intake_claim_allowed"] is False
    assert summary["competition_benchmark_cameo_official_result_intake_fetch_enabled"] is False
    assert (
        summary[
            "competition_benchmark_cameo_official_result_intake_external_state_mutated"
        ]
        is False
    )
    assert (
        summary[
            "competition_benchmark_cameo_official_result_intake_local_native_accuracy_used"
        ]
        is False
    )
    assert summary["competition_benchmark_cameo_official_blocker_count"] == 2
    assert summary["competition_benchmark_cameo_official_operator_action_required_count"] == 2
    assert summary["competition_benchmark_cameo_official_operator_action_required_row_count"] == 0
    assert summary["competition_benchmark_cameo_official_primary_blocker_code"] == (
        "official_result_rows_missing"
    )
    assert summary["competition_benchmark_cameo_official_primary_required_action"] == (
        "Fill at least one official CAMEO result row in the operator intake CSV."
    )
    assert summary["competition_benchmark_cameo_official_missing_required_columns"] == [
        "target_id"
    ]
    assert "official_cameo" in summary[
        "competition_benchmark_cameo_official_allowed_result_source_kinds"
    ]
    assert summary["competition_benchmark_cameo_official_source_provenance_ready_row_count"] == 0
    assert summary["competition_benchmark_cameo_official_metric_ready_row_count"] == 0
    assert summary["competition_benchmark_cameo_official_local_native_accuracy_blocker_count"] == 0
    assert summary["competition_benchmark_casp16_ligand_source_manifest_status"] == (
        "blocked_casp16_ligand_competition_credibility"
    )
    assert summary["competition_benchmark_casp16_ligand_source_manifest_ready"] is True
    assert summary["competition_benchmark_casp16_ligand_competition_credibility_ready"] is False
    assert summary["competition_benchmark_casp16_ligand_pose_target_count"] == 233
    assert summary["competition_benchmark_casp16_ligand_affinity_target_count"] == 140
    assert summary["competition_benchmark_bm5_capri_complex_source_manifest_status"] == (
        "blocked_bm5_capri_complex_competition_credibility"
    )
    assert summary["competition_benchmark_bm5_complex_benchmark_ready"] is True
    assert summary["competition_benchmark_capri_score_set_ready"] is False
    assert (
        summary["competition_benchmark_bm5_capri_complex_competition_credibility_ready"]
        is False
    )
    assert summary["competition_benchmark_competition_credibility_extension_ready"] is False
    assert summary["competition_benchmark_competition_credibility_extension_blockers"] == [
        "casp16_ligand_materialization_not_ready",
        "casp16_ligand_scorecard_not_ready",
        "capri_score_set_not_ready",
    ]
    assert summary["competition_benchmark_competition_credibility_extension_primary_blocker"] == (
        "casp16_ligand_materialization_not_ready"
    )
    assert summary["competition_benchmark_custody_work_order_status"] == (
        "blocked_competition_benchmark_custody_work_order"
    )
    assert summary["competition_benchmark_custody_work_order_action_count"] == 3
    assert summary["competition_benchmark_custody_work_order_raw_data_blocked_row_count"] == 1
    assert summary["competition_benchmark_custody_work_order_primary_work_order_id"] == (
        "casp16_ligand_operator_receipts_missing"
    )
    assert summary["competition_benchmark_package_b_public_benchmark_validation_ready"] is True
    assert (
        summary["competition_benchmark_package_b_ligand_public_benchmark_foundation_ready"]
        is True
    )
    assert summary["competition_benchmark_package_b_claim_grade_public_benchmark_ready"] is False
    assert summary["competition_benchmark_competition_ligand_commercial_claim_allowed"] is False
    assert summary["competition_benchmark_competition_ligand_claim_blockers"] == [
        "casp16_ligand_competition_credibility_not_ready",
        "package_b_claim_grade_public_benchmark_not_ready"
    ]
