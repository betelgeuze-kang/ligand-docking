from __future__ import annotations

from pathlib import Path

from tools import build_runs_cleanup_batch3_review_manifest as mod


def test_build_runs_cleanup_batch3_review_manifest(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()

    sample_files = [
        "ligand_blind_gpcr_full_2026-03-11_r1_state.json",
        "ligand_blind_gpcr_full_2026-03-11_r1_p0_stage1_queue.csv",
        "ligand_blind_gpcr_full_2026-03-11_r1_p0_stage2_summary.json",
        "ligand_blind_gpcr_full_2026-03-11_r1_p0_stage3_scores.csv",
        "ligand_blind_gpcr_full_2026-03-11_r1_p0_stage45_integrity_summary.md",
        "ligand_blind_trpv1_full_2026-03-11_r1_hard_decoy_split.csv",
        "ligand_blind_trpv1_full_2026-03-11_r1_summary.md",
        "ligand_stress_commercial_full_2026-03-11_r1_rows.npz",
        "ligand_stress_commercial_full_2026-03-11_r1_runs.csv",
    ]
    for name in sample_files:
        (runs / name).write_text("x", encoding="utf-8")

    payload = mod.build_payload(str(runs))
    summary = payload["summary"]
    families = {row["family_id"]: row for row in payload["families"]}
    rows = {(row["family_id"], row["subgroup_id"]): row for row in payload["rows"]}

    assert summary["status"] == "runs_cleanup_batch3_review_manifest_ready"
    assert summary["family_count"] == 3
    assert families["ligand_blind_gpcr"]["file_count"] >= 5
    assert ("ligand_blind_gpcr", "stage1_queue_inputs") in rows
    assert rows[("ligand_blind_gpcr", "stage1_queue_inputs")]["recommended_disposition"] == "review_for_archive_after_sampling"
    assert ("ligand_blind_trpv1", "hard_decoy_artifacts") in rows
    assert rows[("ligand_blind_trpv1", "hard_decoy_artifacts")]["recommended_disposition"] == "archive_after_family_signoff"
    assert ("ligand_stress_commercial", "row_bundles") in rows
    assert rows[("ligand_stress_commercial", "row_bundles")]["recommended_disposition"] == "manual_review_heavy_bundle"
