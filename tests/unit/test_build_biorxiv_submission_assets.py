from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_submission_assets(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    figs = docs / "figures"
    runs = tmp_path / "runs"
    docs.mkdir()
    figs.mkdir(parents=True)
    runs.mkdir()

    (docs / "biorxiv_manuscript_submission_ready.md").write_text("manuscript\n", encoding="utf-8")
    (docs / "biorxiv_author_metadata_template.md").write_text("author metadata\n", encoding="utf-8")
    (docs / "biorxiv_cover_letter_draft.md").write_text("cover letter\n", encoding="utf-8")
    (docs / "biorxiv_submission_summary_onepager.md").write_text("submission summary\n", encoding="utf-8")
    (docs / "biorxiv_introduction_draft.md").write_text("introduction\n", encoding="utf-8")
    (docs / "biorxiv_methods_submission_ready.md").write_text("methods\n", encoding="utf-8")
    (docs / "biorxiv_abstract_draft.md").write_text("abstract\n", encoding="utf-8")
    (docs / "biorxiv_results_manuscript_ready.md").write_text("results\n", encoding="utf-8")
    (docs / "biorxiv_discussion_draft.md").write_text("discussion\n", encoding="utf-8")
    (docs / "biorxiv_figure_caption_submission_ready.md").write_text("caption\n", encoding="utf-8")
    (docs / "biorxiv_baseline_gauntlet_notes.md").write_text("baseline notes\n", encoding="utf-8")
    (docs / "biorxiv_claim_scope_note.md").write_text("claim scope note\n", encoding="utf-8")
    (docs / "biorxiv_upload_checklist.md").write_text("upload checklist\n", encoding="utf-8")
    (docs / "ligand_scaleup_benchmark_plan.md").write_text("scaleup benchmark plan\n", encoding="utf-8")
    (docs / "biorxiv_failure_taxonomy.md").write_text("failure taxonomy\n", encoding="utf-8")
    (docs / "biorxiv_robustness_note.md").write_text("robustness note\n", encoding="utf-8")
    (docs / "biorxiv_external_governance_note.md").write_text("external governance note\n", encoding="utf-8")
    (docs / "biorxiv_temporal_scaffold_note.md").write_text("temporal scaffold note\n", encoding="utf-8")
    (docs / "biorxiv_temporal_validation_plan.md").write_text("temporal plan\n", encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config/external_validation_biorxiv_temporal_sets_v1_provisional.json").write_text("{\"status\": \"provisional\"}\n", encoding="utf-8")
    (tmp_path / "config/biorxiv_temporal_ligand_provenance_v1.csv").write_text("ligand_id,source_release\nL1,\n", encoding="utf-8")
    (tmp_path / "config/biorxiv_temporal_idp_provenance_v1.csv").write_text("holdout_name,provenance_source\nalpha,\n", encoding="utf-8")
    (tmp_path / "config/biorxiv_temporal_local_release_facts_v1.csv").write_text("source_release,release_date\nchembl,2026-03-10\n", encoding="utf-8")
    (tmp_path / "config/biorxiv_temporal_idp_local_release_facts_v1.csv").write_text("source_kind,benchmark_inclusion_date\nsynthetic,2026-03-21\n", encoding="utf-8")
    (tmp_path / "config/biorxiv_temporal_source_normalization_v1.csv").write_text("source_family,normalized_source_release\nchembl,chembl\n", encoding="utf-8")
    (figs / "biorxiv_revision_timeline_camera_ready.svg").write_text("<svg/>\n", encoding="utf-8")

    (runs / "biorxiv_external_validation_main_table_current.md").write_text("main table\n", encoding="utf-8")
    (runs / "biorxiv_external_validation_supplementary_task_table_current.md").write_text("supp table\n", encoding="utf-8")
    (runs / "biorxiv_external_validation_reviewer_summary_current.md").write_text("reviewer summary\n", encoding="utf-8")
    baseline_dir = runs / "biorxiv_baseline_comparison_current"
    baseline_dir.mkdir()
    (baseline_dir / "summary.md").write_text("baseline summary\n", encoding="utf-8")
    (runs / "biorxiv_baseline_gauntlet_main_table_current.md").write_text("baseline main table\n", encoding="utf-8")
    (runs / "biorxiv_baseline_gauntlet_results_paragraph_current.md").write_text("baseline paragraph\n", encoding="utf-8")
    (runs / "biorxiv_temporal_provenance_inventory_current.md").write_text("temporal inventory md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_provenance_inventory_current.csv").write_text("path,readiness\nconfig/foo.csv,dataset_level_only\n", encoding="utf-8")
    (runs / "biorxiv_temporal_provenance_inventory_current.json").write_text("{\"summary\": {\"inspected_file_count\": 1}}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_provenance_mapping_coverage_current.md").write_text("coverage md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_provenance_mapping_coverage_current.json").write_text("{\"ligand\": {\"row_count\": 1}}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_local_release_facts_apply_current.md").write_text("local release apply md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_local_release_facts_apply_current.json").write_text("{\"matched_row_count\": 1}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_local_release_facts_apply_current.md").write_text("idp local release apply md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_local_release_facts_apply_current.json").write_text("{\"matched_row_count\": 1}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_chembl_item_provenance_current.csv").write_text("source_release,ligand_id,publication_year\nchembl_blind_adrb2_v1,CHEMBL1,2012\n", encoding="utf-8")
    (runs / "biorxiv_temporal_chembl_item_provenance_current.json").write_text("{\"fetched_rows\": 1}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_chembl_item_provenance_current.md").write_text("chembl item md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_named_ligand_item_provenance_current.csv").write_text("source_release,ligand_id,publication_year\ngpcr_blind_proxy_v1,carazolol,1976\n", encoding="utf-8")
    (runs / "biorxiv_temporal_named_ligand_item_provenance_current.json").write_text("{\"fetched_rows\": 1}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_named_ligand_item_provenance_current.md").write_text("named item md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_item_helpers_current.csv").write_text("holdout_name,citation_publication_year\nalpha_synuclein_full,2024\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_item_helpers_current.json").write_text("{\"holdout_count\": 1}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_item_helpers_current.md").write_text("idp helper md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_item_provenance_facts_current.csv").write_text("holdout_name,publication_year\nalpha_synuclein_full,2024\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_item_provenance_facts_current.json").write_text("{\"fact_row_count\": 1}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_item_provenance_facts_current.md").write_text("idp facts md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_synthetic_progress_current.csv").write_text("status,holdout_name\nitem_ready,ddx4_n1\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_synthetic_progress_current.json").write_text("{\"synthetic_row_count\": 1}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_synthetic_progress_current.md").write_text("idp synthetic progress md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_remaining_policy_current.csv").write_text("holdout_name,policy_label\ntau_2n4r_fragment,fragment_anchor_missing\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_remaining_policy_current.json").write_text("{\"remaining_count\": 1}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_remaining_policy_current.md").write_text("idp remaining policy md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_submission_baseline_current.json").write_text("{\"overall_item_ready_count\": 202}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_submission_baseline_current.md").write_text("temporal baseline md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_item_provenance_apply_current.md").write_text("item apply md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_item_provenance_apply_current.json").write_text("{\"matched_row_count\": 1}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_item_provenance_apply_current.md").write_text("idp item apply md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_idp_item_provenance_apply_current.json").write_text("{\"matched_row_count\": 1}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_item_gap_report_current.md").write_text("item gap md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_item_gap_report_current.csv").write_text("kind,group_key\nligand,gpcr_blind_proxy_v1\n", encoding="utf-8")
    (runs / "biorxiv_temporal_item_gap_report_current.json").write_text("{\"group_count\": 1}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_curation_priority_current.md").write_text("priority md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_curation_priority_current.csv").write_text("source_family,priority\nchembl,high\n", encoding="utf-8")
    (runs / "biorxiv_temporal_curation_priority_current.json").write_text("{\"summary\": {\"group_count\": 1}}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_source_normalization_current.md").write_text("normalization md\n", encoding="utf-8")
    (runs / "biorxiv_temporal_source_normalization_current.json").write_text("{\"group_count\": 1}\n", encoding="utf-8")
    (runs / "biorxiv_temporal_source_pool_sanity_check_current.md").write_text("sanity md\n", encoding="utf-8")
    (runs / "biorxiv_ablation_table_current.json").write_text("{\"rows\": [{\"transition_id\": \"v3r1_to_v4r1\"}]}\n", encoding="utf-8")
    (runs / "biorxiv_ablation_table_current.csv").write_text("transition_id\nv3r1_to_v4r1\n", encoding="utf-8")
    (runs / "biorxiv_ablation_table_current.md").write_text("ablation md\n", encoding="utf-8")
    (runs / "biorxiv_robustness_matrix_current.json").write_text("{\"rows\": [{\"dimension\": \"primary_blind_claim\"}]}\n", encoding="utf-8")
    (runs / "biorxiv_robustness_matrix_current.csv").write_text("dimension\nprimary_blind_claim\n", encoding="utf-8")
    (runs / "biorxiv_robustness_matrix_current.md").write_text("robustness md\n", encoding="utf-8")
    (runs / "biorxiv_robustness_comparison_summary_current.json").write_text("{\"ligand_task_count\": 9}\n", encoding="utf-8")
    (runs / "biorxiv_robustness_comparison_summary_current.csv").write_text("task_id,delta_pr_auc\ngpcr_core_full,-0.15\n", encoding="utf-8")
    (runs / "biorxiv_robustness_comparison_summary_current.md").write_text("robustness comparison md\n", encoding="utf-8")
    (runs / "biorxiv_robustness_results_paragraph_current.md").write_text("robustness paragraph md\n", encoding="utf-8")
    (runs / "biorxiv_submission_freeze_current.json").write_text("{\"bundle_tag\": \"v7r1\"}\n", encoding="utf-8")
    (runs / "biorxiv_submission_freeze_current.md").write_text("submission freeze md\n", encoding="utf-8")
    (runs / "biorxiv_robustness_battery_current.json").write_text("{\"scenario_count\": 4}\n", encoding="utf-8")
    (runs / "biorxiv_robustness_battery_current.csv").write_text("scenario_id\nembed_seed_shift1\n", encoding="utf-8")
    (runs / "biorxiv_robustness_battery_current.md").write_text("robustness battery md\n", encoding="utf-8")
    (runs / "biorxiv_robustness_battery_execution_current.json").write_text("{\"row_count\": 2}\n", encoding="utf-8")
    (runs / "biorxiv_robustness_battery_execution_current.md").write_text("robustness battery execution md\n", encoding="utf-8")
    (runs / "biorxiv_external_validation_governance_seal_current.json").write_text("{\"sealed_file_count\": 1}\n", encoding="utf-8")
    (runs / "biorxiv_external_validation_governance_seal_current.md").write_text("governance seal md\n", encoding="utf-8")
    (runs / "ligand_scaleup_kpi_current.json").write_text("{\"summary\": {\"slowest_task_at_1m\": {\"task_id\": \"ion_trpv1_chembl50_full\"}}}\n", encoding="utf-8")
    (runs / "ligand_scaleup_kpi_current.csv").write_text("task_id,projected_1m_wall_hr\nion_trpv1_chembl50_full,16.2\n", encoding="utf-8")
    (runs / "ligand_scaleup_kpi_current.md").write_text("scaleup kpi md\n", encoding="utf-8")
    (runs / "ligand_scaleup_100k_pilot_current.json").write_text("{\"comparison_kind\": \"size_shift_operational_regression\"}\n", encoding="utf-8")
    (runs / "ligand_scaleup_100k_pilot_current.md").write_text("100k pilot md\n", encoding="utf-8")
    (runs / "ligand_scaleup_100k_pilot_dryrun_current.json").write_text("{\"launch_readiness\": {\"ready\": true}}\n", encoding="utf-8")
    (runs / "ligand_scaleup_100k_pilot_dryrun_current.md").write_text("100k pilot dryrun md\n", encoding="utf-8")
    (runs / "ligand_scaleup_1m_pilot_current.json").write_text("{\"target_scale_label\": \"1M\"}\n", encoding="utf-8")
    (runs / "ligand_scaleup_1m_pilot_current.md").write_text("1m pilot md\n", encoding="utf-8")
    (runs / "ligand_scaleup_suite_dryrun_current.json").write_text("{\"enabled_stage_count\": 3}\n", encoding="utf-8")
    (runs / "ligand_scaleup_suite_dryrun_current.md").write_text("suite dryrun md\n", encoding="utf-8")
    (runs / "ligand_scaleup_suite_execution_current.json").write_text("{\"completed_stage_count\": 2}\n", encoding="utf-8")
    (runs / "ligand_scaleup_suite_execution_current.md").write_text("suite execution md\n", encoding="utf-8")
    (runs / "ligand_scaleup_suite_status_current.json").write_text("{\"stage_count\": 3}\n", encoding="utf-8")
    (runs / "ligand_scaleup_suite_status_current.csv").write_text("stage_id,status\npilot_100k,prelaunch_ready\n", encoding="utf-8")
    (runs / "ligand_scaleup_suite_status_current.md").write_text("suite status md\n", encoding="utf-8")
    (runs / "ligand_scaleup_benchmark_summary_current.json").write_text("{\"claim_safe_status\": \"claim_safe_pending_speed_evidence\"}\n", encoding="utf-8")
    (runs / "ligand_scaleup_benchmark_summary_current.csv").write_text("guardrail_id,pass\nno_pass_to_fail,True\n", encoding="utf-8")
    (runs / "ligand_scaleup_benchmark_summary_current.md").write_text("scaleup benchmark summary md\n", encoding="utf-8")
    idp_manual_dir = runs / "biorxiv_temporal_idp_manual_curation_current"
    idp_manual_dir.mkdir()
    (idp_manual_dir / "README.md").write_text("idp manual bundle\n", encoding="utf-8")
    (idp_manual_dir / "biorxiv_temporal_idp_pdb_manual_facts_current.csv").write_text("holdout_name\nfus_lcd\n", encoding="utf-8")
    (baseline_dir / "score_leaderboard.csv").write_text("score_alias,wins_pr_auc\ncomposite_v7,3\n", encoding="utf-8")
    (baseline_dir / "task_winners.csv").write_text("task_id,winner_score_col\ngpcr_core_full,binding_score_composite_v7\n", encoding="utf-8")
    (runs / "biorxiv_external_validation_package_current.zip").write_text("zipstub\n", encoding="utf-8")
    (runs / "biorxiv_external_validation_reviewer_index_current.html").write_text("<html></html>\n", encoding="utf-8")
    (runs / "biorxiv_external_validation_claim_matrix_current.md").write_text("claim matrix\n", encoding="utf-8")
    (runs / "biorxiv_external_validation_audit_current.json").write_text("{}", encoding="utf-8")
    (runs / "biorxiv_external_validation_audit_current.md").write_text("audit\n", encoding="utf-8")

    current_meta = {
        "current_files": {
            "archive_zip": str((runs / "biorxiv_external_validation_package_current.zip").resolve()),
            "reviewer_index_html": str((runs / "biorxiv_external_validation_reviewer_index_current.html").resolve()),
            "claim_matrix_md": str((runs / "biorxiv_external_validation_claim_matrix_current.md").resolve()),
            "audit_json": str((runs / "biorxiv_external_validation_audit_current.json").resolve()),
            "audit_md": str((runs / "biorxiv_external_validation_audit_current.md").resolve()),
            "reviewer_summary_md": str((runs / "biorxiv_external_validation_reviewer_summary_current.md").resolve()),
        }
    }
    (runs / "biorxiv_external_validation_package_current.json").write_text(
        json.dumps(current_meta), encoding="utf-8"
    )

    cmd = [
        "python3",
        str(ROOT / "tools/build_biorxiv_submission_assets.py"),
        "--label",
        "test",
        "--out-root",
        str(runs),
        "--current-package-meta-json",
        str(runs / "biorxiv_external_validation_package_current.json"),
        "--manuscript-md",
        str(docs / "biorxiv_manuscript_submission_ready.md"),
        "--introduction-md",
        str(docs / "biorxiv_introduction_draft.md"),
        "--methods-md",
        str(docs / "biorxiv_methods_submission_ready.md"),
        "--abstract-md",
        str(docs / "biorxiv_abstract_draft.md"),
        "--results-md",
        str(docs / "biorxiv_results_manuscript_ready.md"),
        "--discussion-md",
        str(docs / "biorxiv_discussion_draft.md"),
        "--figure-caption-md",
        str(docs / "biorxiv_figure_caption_submission_ready.md"),
        "--temporal-spec-json",
        str(tmp_path / "config/external_validation_biorxiv_temporal_sets_v1_provisional.json"),
        "--temporal-chembl-item-provenance-csv",
        str(runs / "biorxiv_temporal_chembl_item_provenance_current.csv"),
        "--temporal-chembl-item-provenance-json",
        str(runs / "biorxiv_temporal_chembl_item_provenance_current.json"),
        "--temporal-chembl-item-provenance-md",
        str(runs / "biorxiv_temporal_chembl_item_provenance_current.md"),
        "--temporal-named-item-provenance-csv",
        str(runs / "biorxiv_temporal_named_ligand_item_provenance_current.csv"),
        "--temporal-named-item-provenance-json",
        str(runs / "biorxiv_temporal_named_ligand_item_provenance_current.json"),
        "--temporal-named-item-provenance-md",
        str(runs / "biorxiv_temporal_named_ligand_item_provenance_current.md"),
        "--temporal-idp-item-helpers-csv",
        str(runs / "biorxiv_temporal_idp_item_helpers_current.csv"),
        "--temporal-idp-item-helpers-json",
        str(runs / "biorxiv_temporal_idp_item_helpers_current.json"),
        "--temporal-idp-item-helpers-md",
        str(runs / "biorxiv_temporal_idp_item_helpers_current.md"),
        "--temporal-idp-item-facts-csv",
        str(runs / "biorxiv_temporal_idp_item_provenance_facts_current.csv"),
        "--temporal-idp-item-facts-json",
        str(runs / "biorxiv_temporal_idp_item_provenance_facts_current.json"),
        "--temporal-idp-item-facts-md",
        str(runs / "biorxiv_temporal_idp_item_provenance_facts_current.md"),
        "--temporal-idp-synthetic-progress-csv",
        str(runs / "biorxiv_temporal_idp_synthetic_progress_current.csv"),
        "--temporal-idp-synthetic-progress-json",
        str(runs / "biorxiv_temporal_idp_synthetic_progress_current.json"),
        "--temporal-idp-synthetic-progress-md",
        str(runs / "biorxiv_temporal_idp_synthetic_progress_current.md"),
        "--temporal-idp-remaining-policy-csv",
        str(runs / "biorxiv_temporal_idp_remaining_policy_current.csv"),
        "--temporal-idp-remaining-policy-json",
        str(runs / "biorxiv_temporal_idp_remaining_policy_current.json"),
        "--temporal-idp-remaining-policy-md",
        str(runs / "biorxiv_temporal_idp_remaining_policy_current.md"),
        "--temporal-submission-baseline-json",
        str(runs / "biorxiv_temporal_submission_baseline_current.json"),
        "--temporal-submission-baseline-md",
        str(runs / "biorxiv_temporal_submission_baseline_current.md"),
        "--temporal-item-provenance-apply-md",
        str(runs / "biorxiv_temporal_item_provenance_apply_current.md"),
        "--temporal-item-provenance-apply-json",
        str(runs / "biorxiv_temporal_item_provenance_apply_current.json"),
        "--temporal-idp-item-provenance-apply-md",
        str(runs / "biorxiv_temporal_idp_item_provenance_apply_current.md"),
        "--temporal-idp-item-provenance-apply-json",
        str(runs / "biorxiv_temporal_idp_item_provenance_apply_current.json"),
        "--temporal-item-gap-report-md",
        str(runs / "biorxiv_temporal_item_gap_report_current.md"),
        "--temporal-item-gap-report-csv",
        str(runs / "biorxiv_temporal_item_gap_report_current.csv"),
        "--temporal-item-gap-report-json",
        str(runs / "biorxiv_temporal_item_gap_report_current.json"),
        "--figure-svg",
        str(figs / "biorxiv_revision_timeline_camera_ready.svg"),
        "--ligand-scaleup-benchmark-plan-md",
        str(docs / "ligand_scaleup_benchmark_plan.md"),
        "--ligand-scaleup-kpi-json",
        str(runs / "ligand_scaleup_kpi_current.json"),
        "--ligand-scaleup-kpi-csv",
        str(runs / "ligand_scaleup_kpi_current.csv"),
        "--ligand-scaleup-kpi-md",
        str(runs / "ligand_scaleup_kpi_current.md"),
        "--ligand-scaleup-100k-pilot-json",
        str(runs / "ligand_scaleup_100k_pilot_current.json"),
        "--ligand-scaleup-100k-pilot-md",
        str(runs / "ligand_scaleup_100k_pilot_current.md"),
        "--ligand-scaleup-100k-pilot-dryrun-json",
        str(runs / "ligand_scaleup_100k_pilot_dryrun_current.json"),
        "--ligand-scaleup-100k-pilot-dryrun-md",
        str(runs / "ligand_scaleup_100k_pilot_dryrun_current.md"),
        "--ligand-scaleup-1m-pilot-json",
        str(runs / "ligand_scaleup_1m_pilot_current.json"),
        "--ligand-scaleup-1m-pilot-md",
        str(runs / "ligand_scaleup_1m_pilot_current.md"),
        "--ligand-scaleup-suite-dryrun-json",
        str(runs / "ligand_scaleup_suite_dryrun_current.json"),
        "--ligand-scaleup-suite-execution-json",
        str(runs / "ligand_scaleup_suite_execution_current.json"),
        "--ligand-scaleup-suite-status-json",
        str(runs / "ligand_scaleup_suite_status_current.json"),
        "--ligand-scaleup-suite-status-csv",
        str(runs / "ligand_scaleup_suite_status_current.csv"),
        "--ligand-scaleup-suite-status-md",
        str(runs / "ligand_scaleup_suite_status_current.md"),
        "--ligand-scaleup-benchmark-summary-json",
        str(runs / "ligand_scaleup_benchmark_summary_current.json"),
        "--ligand-scaleup-benchmark-summary-csv",
        str(runs / "ligand_scaleup_benchmark_summary_current.csv"),
        "--ligand-scaleup-benchmark-summary-md",
        str(runs / "ligand_scaleup_benchmark_summary_current.md"),
        "--main-table-md",
        str(runs / "biorxiv_external_validation_main_table_current.md"),
        "--supp-table-md",
        str(runs / "biorxiv_external_validation_supplementary_task_table_current.md"),
        "--reviewer-summary-md",
        str(runs / "biorxiv_external_validation_reviewer_summary_current.md"),
        "--baseline-main-table-md",
        str(runs / "biorxiv_baseline_gauntlet_main_table_current.md"),
        "--baseline-results-paragraph-md",
        str(runs / "biorxiv_baseline_gauntlet_results_paragraph_current.md"),
    ]
    subprocess.run(cmd, check=True)

    bundle_root = runs / "biorxiv_submission_assets_test"
    assert (bundle_root / "submission_assets_manifest.json").exists()
    assert (bundle_root / "docs/biorxiv_manuscript_submission_ready.md").exists()
    assert (bundle_root / "docs/biorxiv_author_metadata_template.md").exists()
    assert (bundle_root / "docs/biorxiv_cover_letter_draft.md").exists()
    assert (bundle_root / "docs/biorxiv_submission_summary_onepager.md").exists()
    assert (bundle_root / "docs/biorxiv_introduction_draft.md").exists()
    assert (bundle_root / "docs/biorxiv_methods_submission_ready.md").exists()
    assert (bundle_root / "docs/biorxiv_baseline_gauntlet_notes.md").exists()
    assert (bundle_root / "docs/biorxiv_claim_scope_note.md").exists()
    assert (bundle_root / "docs/biorxiv_upload_checklist.md").exists()
    assert (bundle_root / "docs/ligand_scaleup_benchmark_plan.md").exists()
    assert (bundle_root / "docs/biorxiv_failure_taxonomy.md").exists()
    assert (bundle_root / "docs/biorxiv_robustness_note.md").exists()
    assert (bundle_root / "docs/biorxiv_external_governance_note.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_scaffold_note.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_validation_plan.md").exists()
    assert (bundle_root / "docs/external_validation_biorxiv_temporal_sets_v1_provisional.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_provenance_inventory_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_provenance_inventory_current.csv").exists()
    assert (bundle_root / "docs/biorxiv_temporal_provenance_inventory_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_ligand_provenance_v1.csv").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_provenance_v1.csv").exists()
    assert (bundle_root / "docs/biorxiv_temporal_local_release_facts_v1.csv").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_local_release_facts_v1.csv").exists()
    assert (bundle_root / "docs/biorxiv_temporal_chembl_item_provenance_current.csv").exists()
    assert (bundle_root / "docs/biorxiv_temporal_chembl_item_provenance_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_chembl_item_provenance_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_named_ligand_item_provenance_current.csv").exists()
    assert (bundle_root / "docs/biorxiv_temporal_named_ligand_item_provenance_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_named_ligand_item_provenance_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_item_helpers_current.csv").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_item_helpers_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_item_helpers_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_item_provenance_facts_current.csv").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_item_provenance_facts_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_item_provenance_facts_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_synthetic_progress_current.csv").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_synthetic_progress_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_synthetic_progress_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_remaining_policy_current.csv").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_remaining_policy_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_remaining_policy_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_submission_baseline_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_submission_baseline_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_provenance_mapping_coverage_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_provenance_mapping_coverage_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_local_release_facts_apply_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_local_release_facts_apply_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_local_release_facts_apply_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_local_release_facts_apply_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_item_provenance_apply_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_item_provenance_apply_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_item_provenance_apply_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_idp_item_provenance_apply_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_item_gap_report_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_item_gap_report_current.csv").exists()
    assert (bundle_root / "docs/biorxiv_temporal_item_gap_report_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_curation_priority_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_curation_priority_current.csv").exists()
    assert (bundle_root / "docs/biorxiv_temporal_curation_priority_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_source_normalization_v1.csv").exists()
    assert (bundle_root / "docs/biorxiv_temporal_source_normalization_current.md").exists()
    assert (bundle_root / "docs/biorxiv_temporal_source_normalization_current.json").exists()
    assert (bundle_root / "docs/biorxiv_temporal_source_pool_sanity_check_current.md").exists()
    assert (bundle_root / "docs/biorxiv_ablation_table_current.json").exists()
    assert (bundle_root / "docs/biorxiv_ablation_table_current.csv").exists()
    assert (bundle_root / "docs/biorxiv_ablation_table_current.md").exists()
    assert (bundle_root / "docs/biorxiv_robustness_matrix_current.json").exists()
    assert (bundle_root / "docs/biorxiv_robustness_matrix_current.csv").exists()
    assert (bundle_root / "docs/biorxiv_robustness_matrix_current.md").exists()
    assert (bundle_root / "docs/biorxiv_submission_freeze_current.json").exists()
    assert (bundle_root / "docs/biorxiv_submission_freeze_current.md").exists()
    assert (bundle_root / "docs/biorxiv_robustness_battery_current.json").exists()
    assert (bundle_root / "docs/biorxiv_robustness_battery_current.csv").exists()
    assert (bundle_root / "docs/biorxiv_robustness_battery_current.md").exists()
    assert (bundle_root / "docs/biorxiv_robustness_battery_execution_current.json").exists()
    assert (bundle_root / "docs/biorxiv_robustness_battery_execution_current.md").exists()
    assert (bundle_root / "docs/biorxiv_external_validation_governance_seal_current.json").exists()
    assert (bundle_root / "docs/biorxiv_external_validation_governance_seal_current.md").exists()
    assert (bundle_root / "docs/idp_manual_curation/README.md").exists()
    assert (bundle_root / "docs/idp_manual_curation/biorxiv_temporal_idp_pdb_manual_facts_current.csv").exists()
    assert (bundle_root / "figures/biorxiv_revision_timeline_camera_ready.svg").exists()
    assert (bundle_root / "tables/biorxiv_external_validation_main_table_current.md").exists()
    assert (bundle_root / "tables/summary.md").exists()
    assert (bundle_root / "tables/biorxiv_baseline_gauntlet_main_table_current.md").exists()
    assert (bundle_root / "tables/biorxiv_baseline_gauntlet_results_paragraph_current.md").exists()
    assert (bundle_root / "tables/ligand_scaleup_kpi_current.json").exists()
    assert (bundle_root / "tables/ligand_scaleup_kpi_current.csv").exists()
    assert (bundle_root / "tables/ligand_scaleup_kpi_current.md").exists()
    assert (bundle_root / "tables/ligand_scaleup_100k_pilot_current.json").exists()
    assert (bundle_root / "tables/ligand_scaleup_100k_pilot_current.md").exists()
    assert (bundle_root / "tables/ligand_scaleup_100k_pilot_dryrun_current.json").exists()
    assert (bundle_root / "tables/ligand_scaleup_100k_pilot_dryrun_current.md").exists()
    assert (bundle_root / "tables/ligand_scaleup_1m_pilot_current.json").exists()
    assert (bundle_root / "tables/ligand_scaleup_1m_pilot_current.md").exists()
    assert (bundle_root / "tables/ligand_scaleup_suite_dryrun_current.json").exists()
    assert (bundle_root / "tables/ligand_scaleup_suite_dryrun_current.md").exists()
    assert (bundle_root / "tables/ligand_scaleup_suite_execution_current.json").exists()
    assert (bundle_root / "tables/ligand_scaleup_suite_execution_current.md").exists()
    assert (bundle_root / "tables/ligand_scaleup_suite_status_current.json").exists()
    assert (bundle_root / "tables/ligand_scaleup_suite_status_current.csv").exists()
    assert (bundle_root / "tables/ligand_scaleup_suite_status_current.md").exists()
    assert (bundle_root / "tables/ligand_scaleup_benchmark_summary_current.json").exists()
    assert (bundle_root / "tables/ligand_scaleup_benchmark_summary_current.csv").exists()
    assert (bundle_root / "tables/ligand_scaleup_benchmark_summary_current.md").exists()
    assert (bundle_root / "tables/score_leaderboard.csv").exists()
    assert (bundle_root / "tables/task_winners.csv").exists()
    assert (bundle_root / "package/biorxiv_external_validation_package_current.zip").exists()
    assert (runs / "biorxiv_submission_assets_test.zip").exists()
