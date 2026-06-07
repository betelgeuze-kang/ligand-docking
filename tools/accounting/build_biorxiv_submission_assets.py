#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _copy(src: Path, dst: Path) -> dict[str, Any]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return {
        "src": str(src.resolve()),
        "dst": str(dst.resolve()),
        "size_bytes": dst.stat().st_size,
    }


def _bundle_name(label: str) -> str:
    return f"biorxiv_submission_assets_{label}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a submission-assets bundle for the accepted bioRxiv validation package.")
    ap.add_argument("--label", default="current")
    ap.add_argument("--out-root", default="runs")
    ap.add_argument("--current-package-meta-json", default="runs/biorxiv_external_validation_package_current.json")
    ap.add_argument("--manuscript-md", default="docs/biorxiv_manuscript_submission_ready.md")
    ap.add_argument("--author-metadata-md", default="docs/biorxiv_author_metadata_template.md")
    ap.add_argument("--cover-letter-md", default="docs/biorxiv_cover_letter_draft.md")
    ap.add_argument("--submission-summary-md", default="docs/biorxiv_submission_summary_onepager.md")
    ap.add_argument("--introduction-md", default="docs/biorxiv_introduction_draft.md")
    ap.add_argument("--methods-md", default="docs/biorxiv_methods_submission_ready.md")
    ap.add_argument("--abstract-md", default="docs/biorxiv_abstract_draft.md")
    ap.add_argument("--results-md", default="docs/biorxiv_results_manuscript_ready.md")
    ap.add_argument("--discussion-md", default="docs/biorxiv_discussion_draft.md")
    ap.add_argument("--figure-caption-md", default="docs/biorxiv_figure_caption_submission_ready.md")
    ap.add_argument("--baseline-notes-md", default="docs/biorxiv_baseline_gauntlet_notes.md")
    ap.add_argument("--claim-scope-note-md", default="docs/biorxiv_claim_scope_note.md")
    ap.add_argument("--upload-checklist-md", default="docs/biorxiv_upload_checklist.md")
    ap.add_argument("--ligand-scaleup-benchmark-plan-md", default="docs/ligand_scaleup_benchmark_plan.md")
    ap.add_argument("--failure-taxonomy-md", default="docs/biorxiv_failure_taxonomy.md")
    ap.add_argument("--robustness-note-md", default="docs/biorxiv_robustness_note.md")
    ap.add_argument("--external-governance-note-md", default="docs/biorxiv_external_governance_note.md")
    ap.add_argument("--temporal-scaffold-note-md", default="docs/biorxiv_temporal_scaffold_note.md")
    ap.add_argument("--baseline-main-table-md", default="runs/biorxiv_baseline_gauntlet_main_table_current.md")
    ap.add_argument("--baseline-results-paragraph-md", default="runs/biorxiv_baseline_gauntlet_results_paragraph_current.md")
    ap.add_argument("--temporal-plan-md", default="docs/biorxiv_temporal_validation_plan.md")
    ap.add_argument("--temporal-spec-json", default="config/external_validation_biorxiv_temporal_sets_v1_provisional.json")
    ap.add_argument("--temporal-provenance-md", default="runs/biorxiv_temporal_provenance_inventory_current.md")
    ap.add_argument("--temporal-provenance-csv", default="runs/biorxiv_temporal_provenance_inventory_current.csv")
    ap.add_argument("--temporal-provenance-json", default="runs/biorxiv_temporal_provenance_inventory_current.json")
    ap.add_argument("--temporal-ligand-map-csv", default="config/biorxiv_temporal_ligand_provenance_v1.csv")
    ap.add_argument("--temporal-idp-map-csv", default="config/biorxiv_temporal_idp_provenance_v1.csv")
    ap.add_argument("--temporal-local-release-facts-csv", default="config/biorxiv_temporal_local_release_facts_v1.csv")
    ap.add_argument("--temporal-idp-local-release-facts-csv", default="config/biorxiv_temporal_idp_local_release_facts_v1.csv")
    ap.add_argument("--temporal-chembl-item-provenance-csv", default="runs/biorxiv_temporal_chembl_item_provenance_current.csv")
    ap.add_argument("--temporal-chembl-item-provenance-json", default="runs/biorxiv_temporal_chembl_item_provenance_current.json")
    ap.add_argument("--temporal-chembl-item-provenance-md", default="runs/biorxiv_temporal_chembl_item_provenance_current.md")
    ap.add_argument("--temporal-named-item-provenance-csv", default="runs/biorxiv_temporal_named_ligand_item_provenance_current.csv")
    ap.add_argument("--temporal-named-item-provenance-json", default="runs/biorxiv_temporal_named_ligand_item_provenance_current.json")
    ap.add_argument("--temporal-named-item-provenance-md", default="runs/biorxiv_temporal_named_ligand_item_provenance_current.md")
    ap.add_argument("--temporal-idp-item-helpers-csv", default="runs/biorxiv_temporal_idp_item_helpers_current.csv")
    ap.add_argument("--temporal-idp-item-helpers-json", default="runs/biorxiv_temporal_idp_item_helpers_current.json")
    ap.add_argument("--temporal-idp-item-helpers-md", default="runs/biorxiv_temporal_idp_item_helpers_current.md")
    ap.add_argument("--temporal-idp-item-facts-csv", default="runs/biorxiv_temporal_idp_item_provenance_facts_current.csv")
    ap.add_argument("--temporal-idp-item-facts-json", default="runs/biorxiv_temporal_idp_item_provenance_facts_current.json")
    ap.add_argument("--temporal-idp-item-facts-md", default="runs/biorxiv_temporal_idp_item_provenance_facts_current.md")
    ap.add_argument("--temporal-idp-synthetic-progress-csv", default="runs/biorxiv_temporal_idp_synthetic_progress_current.csv")
    ap.add_argument("--temporal-idp-synthetic-progress-json", default="runs/biorxiv_temporal_idp_synthetic_progress_current.json")
    ap.add_argument("--temporal-idp-synthetic-progress-md", default="runs/biorxiv_temporal_idp_synthetic_progress_current.md")
    ap.add_argument("--temporal-idp-remaining-policy-csv", default="runs/biorxiv_temporal_idp_remaining_policy_current.csv")
    ap.add_argument("--temporal-idp-remaining-policy-json", default="runs/biorxiv_temporal_idp_remaining_policy_current.json")
    ap.add_argument("--temporal-idp-remaining-policy-md", default="runs/biorxiv_temporal_idp_remaining_policy_current.md")
    ap.add_argument("--temporal-submission-baseline-json", default="runs/biorxiv_temporal_submission_baseline_current.json")
    ap.add_argument("--temporal-submission-baseline-md", default="runs/biorxiv_temporal_submission_baseline_current.md")
    ap.add_argument("--temporal-coverage-md", default="runs/biorxiv_temporal_provenance_mapping_coverage_current.md")
    ap.add_argument("--temporal-coverage-json", default="runs/biorxiv_temporal_provenance_mapping_coverage_current.json")
    ap.add_argument("--temporal-local-release-apply-md", default="runs/biorxiv_temporal_local_release_facts_apply_current.md")
    ap.add_argument("--temporal-local-release-apply-json", default="runs/biorxiv_temporal_local_release_facts_apply_current.json")
    ap.add_argument("--temporal-idp-local-release-apply-md", default="runs/biorxiv_temporal_idp_local_release_facts_apply_current.md")
    ap.add_argument("--temporal-idp-local-release-apply-json", default="runs/biorxiv_temporal_idp_local_release_facts_apply_current.json")
    ap.add_argument("--temporal-item-provenance-apply-md", default="runs/biorxiv_temporal_item_provenance_apply_current.md")
    ap.add_argument("--temporal-item-provenance-apply-json", default="runs/biorxiv_temporal_item_provenance_apply_current.json")
    ap.add_argument("--temporal-idp-item-provenance-apply-md", default="runs/biorxiv_temporal_idp_item_provenance_apply_current.md")
    ap.add_argument("--temporal-idp-item-provenance-apply-json", default="runs/biorxiv_temporal_idp_item_provenance_apply_current.json")
    ap.add_argument("--temporal-item-gap-report-md", default="runs/biorxiv_temporal_item_gap_report_current.md")
    ap.add_argument("--temporal-item-gap-report-csv", default="runs/biorxiv_temporal_item_gap_report_current.csv")
    ap.add_argument("--temporal-item-gap-report-json", default="runs/biorxiv_temporal_item_gap_report_current.json")
    ap.add_argument("--temporal-priority-md", default="runs/biorxiv_temporal_curation_priority_current.md")
    ap.add_argument("--temporal-priority-csv", default="runs/biorxiv_temporal_curation_priority_current.csv")
    ap.add_argument("--temporal-priority-json", default="runs/biorxiv_temporal_curation_priority_current.json")
    ap.add_argument("--temporal-source-normalization-csv", default="config/biorxiv_temporal_source_normalization_v1.csv")
    ap.add_argument("--temporal-source-normalization-md", default="runs/biorxiv_temporal_source_normalization_current.md")
    ap.add_argument("--temporal-source-normalization-json", default="runs/biorxiv_temporal_source_normalization_current.json")
    ap.add_argument("--temporal-source-pool-sanity-md", default="runs/biorxiv_temporal_source_pool_sanity_check_current.md")
    ap.add_argument("--temporal-family-helpers-dir", default="runs/biorxiv_temporal_family_helpers_current")
    ap.add_argument("--temporal-idp-manual-curation-dir", default="runs/biorxiv_temporal_idp_manual_curation_current")
    ap.add_argument("--figure-svg", default="docs/figures/biorxiv_revision_timeline_camera_ready.svg")
    ap.add_argument("--main-table-md", default="runs/biorxiv_external_validation_main_table_current.md")
    ap.add_argument("--supp-table-md", default="runs/biorxiv_external_validation_supplementary_task_table_current.md")
    ap.add_argument("--reviewer-summary-md", default="runs/biorxiv_external_validation_reviewer_summary_current.md")
    ap.add_argument("--baseline-summary-md", default="runs/biorxiv_baseline_comparison_current/summary.md")
    ap.add_argument("--baseline-score-csv", default="runs/biorxiv_baseline_comparison_current/score_leaderboard.csv")
    ap.add_argument("--baseline-winner-csv", default="runs/biorxiv_baseline_comparison_current/task_winners.csv")
    ap.add_argument("--ablation-json", default="runs/biorxiv_ablation_table_current.json")
    ap.add_argument("--ablation-csv", default="runs/biorxiv_ablation_table_current.csv")
    ap.add_argument("--ablation-md", default="runs/biorxiv_ablation_table_current.md")
    ap.add_argument("--robustness-json", default="runs/biorxiv_robustness_matrix_current.json")
    ap.add_argument("--robustness-csv", default="runs/biorxiv_robustness_matrix_current.csv")
    ap.add_argument("--robustness-md", default="runs/biorxiv_robustness_matrix_current.md")
    ap.add_argument("--robustness-comparison-json", default="runs/biorxiv_robustness_comparison_summary_current.json")
    ap.add_argument("--robustness-comparison-csv", default="runs/biorxiv_robustness_comparison_summary_current.csv")
    ap.add_argument("--robustness-comparison-md", default="runs/biorxiv_robustness_comparison_summary_current.md")
    ap.add_argument("--robustness-results-paragraph-md", default="runs/biorxiv_robustness_results_paragraph_current.md")
    ap.add_argument("--governance-seal-json", default="runs/biorxiv_external_validation_governance_seal_current.json")
    ap.add_argument("--governance-seal-md", default="runs/biorxiv_external_validation_governance_seal_current.md")
    ap.add_argument("--submission-freeze-json", default="runs/biorxiv_submission_freeze_current.json")
    ap.add_argument("--submission-freeze-md", default="runs/biorxiv_submission_freeze_current.md")
    ap.add_argument("--robustness-battery-json", default="runs/biorxiv_robustness_battery_current.json")
    ap.add_argument("--robustness-battery-csv", default="runs/biorxiv_robustness_battery_current.csv")
    ap.add_argument("--robustness-battery-md", default="runs/biorxiv_robustness_battery_current.md")
    ap.add_argument("--robustness-battery-execution-json", default="runs/biorxiv_robustness_battery_execution_current.json")
    ap.add_argument("--robustness-battery-execution-md", default="runs/biorxiv_robustness_battery_execution_current.md")
    ap.add_argument("--ligand-scaleup-kpi-json", default="runs/ligand_scaleup_kpi_current.json")
    ap.add_argument("--ligand-scaleup-kpi-csv", default="runs/ligand_scaleup_kpi_current.csv")
    ap.add_argument("--ligand-scaleup-kpi-md", default="runs/ligand_scaleup_kpi_current.md")
    ap.add_argument("--ligand-scaleup-100k-pilot-json", default="runs/ligand_scaleup_100k_pilot_current.json")
    ap.add_argument("--ligand-scaleup-100k-pilot-md", default="runs/ligand_scaleup_100k_pilot_current.md")
    ap.add_argument("--ligand-scaleup-100k-pilot-dryrun-json", default="runs/ligand_scaleup_100k_pilot_dryrun_current.json")
    ap.add_argument("--ligand-scaleup-100k-pilot-dryrun-md", default="runs/ligand_scaleup_100k_pilot_dryrun_current.md")
    ap.add_argument("--ligand-scaleup-1m-pilot-json", default="runs/ligand_scaleup_1m_pilot_current.json")
    ap.add_argument("--ligand-scaleup-1m-pilot-md", default="runs/ligand_scaleup_1m_pilot_current.md")
    ap.add_argument("--ligand-scaleup-suite-dryrun-json", default="runs/ligand_scaleup_suite_dryrun_current.json")
    ap.add_argument("--ligand-scaleup-suite-dryrun-md", default="runs/ligand_scaleup_suite_dryrun_current.md")
    ap.add_argument("--ligand-scaleup-suite-execution-json", default="runs/ligand_scaleup_suite_execution_current.json")
    ap.add_argument("--ligand-scaleup-suite-execution-md", default="runs/ligand_scaleup_suite_execution_current.md")
    ap.add_argument("--ligand-scaleup-suite-status-json", default="runs/ligand_scaleup_suite_status_current.json")
    ap.add_argument("--ligand-scaleup-suite-status-csv", default="runs/ligand_scaleup_suite_status_current.csv")
    ap.add_argument("--ligand-scaleup-suite-status-md", default="runs/ligand_scaleup_suite_status_current.md")
    ap.add_argument("--ligand-scaleup-benchmark-summary-json", default="runs/ligand_scaleup_benchmark_summary_current.json")
    ap.add_argument("--ligand-scaleup-benchmark-summary-csv", default="runs/ligand_scaleup_benchmark_summary_current.csv")
    ap.add_argument("--ligand-scaleup-benchmark-summary-md", default="runs/ligand_scaleup_benchmark_summary_current.md")
    args = ap.parse_args()

    out_root = (ROOT / args.out_root).resolve()
    bundle_root = out_root / _bundle_name(args.label)
    docs_dir = bundle_root / "docs"
    figures_dir = bundle_root / "figures"
    tables_dir = bundle_root / "tables"
    package_dir = bundle_root / "package"
    bundle_root.mkdir(parents=True, exist_ok=True)

    current_meta = _read_json((ROOT / args.current_package_meta_json).resolve())
    current_files = {}
    if isinstance(current_meta.get("current_files"), dict):
        current_files = current_meta.get("current_files", {})
    elif isinstance(current_meta.get("convenience_artifacts"), dict):
        current_files = current_meta.get("convenience_artifacts", {})

    copied: list[dict[str, Any]] = []
    explicit_files = [
        (ROOT / args.manuscript_md).resolve(),
        (ROOT / args.author_metadata_md).resolve(),
        (ROOT / args.cover_letter_md).resolve(),
        (ROOT / args.submission_summary_md).resolve(),
        (ROOT / args.introduction_md).resolve(),
        (ROOT / args.methods_md).resolve(),
        (ROOT / args.abstract_md).resolve(),
        (ROOT / args.results_md).resolve(),
        (ROOT / args.discussion_md).resolve(),
        (ROOT / args.figure_caption_md).resolve(),
        (ROOT / args.baseline_notes_md).resolve(),
        (ROOT / args.claim_scope_note_md).resolve(),
        (ROOT / args.upload_checklist_md).resolve(),
        (ROOT / args.ligand_scaleup_benchmark_plan_md).resolve(),
        (ROOT / args.failure_taxonomy_md).resolve(),
        (ROOT / args.robustness_note_md).resolve(),
        (ROOT / args.external_governance_note_md).resolve(),
        (ROOT / args.temporal_scaffold_note_md).resolve(),
        (ROOT / args.temporal_plan_md).resolve(),
        (ROOT / args.temporal_spec_json).resolve(),
        (ROOT / args.temporal_provenance_md).resolve(),
        (ROOT / args.temporal_provenance_csv).resolve(),
        (ROOT / args.temporal_provenance_json).resolve(),
        (ROOT / args.temporal_ligand_map_csv).resolve(),
        (ROOT / args.temporal_idp_map_csv).resolve(),
        (ROOT / args.temporal_local_release_facts_csv).resolve(),
        (ROOT / args.temporal_idp_local_release_facts_csv).resolve(),
        (ROOT / args.temporal_chembl_item_provenance_csv).resolve(),
        (ROOT / args.temporal_chembl_item_provenance_json).resolve(),
        (ROOT / args.temporal_chembl_item_provenance_md).resolve(),
        (ROOT / args.temporal_named_item_provenance_csv).resolve(),
        (ROOT / args.temporal_named_item_provenance_json).resolve(),
        (ROOT / args.temporal_named_item_provenance_md).resolve(),
        (ROOT / args.temporal_idp_item_helpers_csv).resolve(),
        (ROOT / args.temporal_idp_item_helpers_json).resolve(),
        (ROOT / args.temporal_idp_item_helpers_md).resolve(),
        (ROOT / args.temporal_idp_item_facts_csv).resolve(),
        (ROOT / args.temporal_idp_item_facts_json).resolve(),
        (ROOT / args.temporal_idp_item_facts_md).resolve(),
        (ROOT / args.temporal_idp_synthetic_progress_csv).resolve(),
        (ROOT / args.temporal_idp_synthetic_progress_json).resolve(),
        (ROOT / args.temporal_idp_synthetic_progress_md).resolve(),
        (ROOT / args.temporal_idp_remaining_policy_csv).resolve(),
        (ROOT / args.temporal_idp_remaining_policy_json).resolve(),
        (ROOT / args.temporal_idp_remaining_policy_md).resolve(),
        (ROOT / args.temporal_submission_baseline_json).resolve(),
        (ROOT / args.temporal_submission_baseline_md).resolve(),
        (ROOT / args.temporal_coverage_md).resolve(),
        (ROOT / args.temporal_coverage_json).resolve(),
        (ROOT / args.temporal_local_release_apply_md).resolve(),
        (ROOT / args.temporal_local_release_apply_json).resolve(),
        (ROOT / args.temporal_idp_local_release_apply_md).resolve(),
        (ROOT / args.temporal_idp_local_release_apply_json).resolve(),
        (ROOT / args.temporal_item_provenance_apply_md).resolve(),
        (ROOT / args.temporal_item_provenance_apply_json).resolve(),
        (ROOT / args.temporal_idp_item_provenance_apply_md).resolve(),
        (ROOT / args.temporal_idp_item_provenance_apply_json).resolve(),
        (ROOT / args.temporal_item_gap_report_md).resolve(),
        (ROOT / args.temporal_item_gap_report_csv).resolve(),
        (ROOT / args.temporal_item_gap_report_json).resolve(),
        (ROOT / args.temporal_priority_md).resolve(),
        (ROOT / args.temporal_priority_csv).resolve(),
        (ROOT / args.temporal_priority_json).resolve(),
        (ROOT / args.temporal_source_normalization_csv).resolve(),
        (ROOT / args.temporal_source_normalization_md).resolve(),
        (ROOT / args.temporal_source_normalization_json).resolve(),
        (ROOT / args.temporal_source_pool_sanity_md).resolve(),
        (ROOT / args.ablation_json).resolve(),
        (ROOT / args.ablation_csv).resolve(),
        (ROOT / args.ablation_md).resolve(),
        (ROOT / args.robustness_json).resolve(),
        (ROOT / args.robustness_csv).resolve(),
        (ROOT / args.robustness_md).resolve(),
        (ROOT / args.robustness_comparison_json).resolve(),
        (ROOT / args.robustness_comparison_csv).resolve(),
        (ROOT / args.robustness_comparison_md).resolve(),
        (ROOT / args.robustness_results_paragraph_md).resolve(),
        (ROOT / args.governance_seal_json).resolve(),
        (ROOT / args.governance_seal_md).resolve(),
        (ROOT / args.submission_freeze_json).resolve(),
        (ROOT / args.submission_freeze_md).resolve(),
        (ROOT / args.robustness_battery_json).resolve(),
        (ROOT / args.robustness_battery_csv).resolve(),
        (ROOT / args.robustness_battery_md).resolve(),
        (ROOT / args.robustness_battery_execution_json).resolve(),
        (ROOT / args.robustness_battery_execution_md).resolve(),
    ]
    for src in explicit_files:
        if not src.exists():
            continue
        copied.append(_copy(src, docs_dir / src.name))

    family_helpers_dir = (ROOT / args.temporal_family_helpers_dir).resolve()
    if family_helpers_dir.exists():
        for src in sorted(family_helpers_dir.rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(family_helpers_dir)
            copied.append(_copy(src, docs_dir / "family_helpers" / rel))

    idp_manual_curation_dir = (ROOT / args.temporal_idp_manual_curation_dir).resolve()
    if idp_manual_curation_dir.exists():
        for src in sorted(idp_manual_curation_dir.rglob("*")):
            if not src.is_file():
                continue
            rel = src.relative_to(idp_manual_curation_dir)
            copied.append(_copy(src, docs_dir / "idp_manual_curation" / rel))

    figure_src = (ROOT / args.figure_svg).resolve()
    copied.append(_copy(figure_src, figures_dir / figure_src.name))

    for rel in [
        args.main_table_md,
        args.supp_table_md,
        args.reviewer_summary_md,
        args.baseline_summary_md,
        args.baseline_main_table_md,
        args.baseline_results_paragraph_md,
        args.baseline_score_csv,
        args.baseline_winner_csv,
        args.ligand_scaleup_kpi_json,
        args.ligand_scaleup_kpi_csv,
        args.ligand_scaleup_kpi_md,
        args.ligand_scaleup_100k_pilot_json,
        args.ligand_scaleup_100k_pilot_md,
        args.ligand_scaleup_100k_pilot_dryrun_json,
        args.ligand_scaleup_100k_pilot_dryrun_md,
        args.ligand_scaleup_1m_pilot_json,
        args.ligand_scaleup_1m_pilot_md,
        args.ligand_scaleup_suite_dryrun_json,
        args.ligand_scaleup_suite_dryrun_md,
        args.ligand_scaleup_suite_execution_json,
        args.ligand_scaleup_suite_execution_md,
        args.ligand_scaleup_suite_status_json,
        args.ligand_scaleup_suite_status_csv,
        args.ligand_scaleup_suite_status_md,
        args.ligand_scaleup_benchmark_summary_json,
        args.ligand_scaleup_benchmark_summary_csv,
        args.ligand_scaleup_benchmark_summary_md,
    ]:
        src = (ROOT / rel).resolve()
        if not src.exists():
            continue
        copied.append(_copy(src, tables_dir / src.name))

    package_files = {
        "package_zip": current_files.get("archive_zip", ""),
        "package_meta_json": str((ROOT / args.current_package_meta_json).resolve()),
        "reviewer_index_html": current_files.get("reviewer_index_html", ""),
        "claim_matrix_md": current_files.get("claim_matrix_md", ""),
        "audit_json": current_files.get("audit_json", ""),
        "audit_md": current_files.get("audit_md", ""),
        "reviewer_summary_md": current_files.get("reviewer_summary_md", ""),
    }
    packaged: dict[str, dict[str, Any]] = {}
    for key, src_str in package_files.items():
        if not src_str:
            continue
        src = Path(src_str).resolve()
        if not src.exists():
            continue
        rec = _copy(src, package_dir / src.name)
        copied.append(rec)
        packaged[key] = rec

    manifest = {
        "label": args.label,
        "bundle_root": str(bundle_root.resolve()),
        "source_current_package_meta_json": str((ROOT / args.current_package_meta_json).resolve()),
        "copied_files": copied,
        "package_files": packaged,
    }
    manifest_json = bundle_root / "submission_assets_manifest.json"
    manifest_md = bundle_root / "submission_assets_manifest.md"
    _write_json(manifest_json, manifest)

    md_lines = [
        "# bioRxiv Submission Assets Bundle",
        "",
        f"- label: `{args.label}`",
        f"- bundle_root: `{bundle_root}`",
        f"- source_current_package_meta_json: `{(ROOT / args.current_package_meta_json).resolve()}`",
        "",
        "## Included Files",
        "",
    ]
    for rec in copied:
        md_lines.append(f"- `{Path(rec['dst']).name}`")
    md_lines.append("")
    md_lines.append("## Package Files")
    md_lines.append("")
    for key, rec in packaged.items():
        md_lines.append(f"- `{key}`: `{Path(rec['dst']).name}`")
    _write_text(manifest_md, "\n".join(md_lines) + "\n")

    zip_path = bundle_root.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(bundle_root.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(bundle_root))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
