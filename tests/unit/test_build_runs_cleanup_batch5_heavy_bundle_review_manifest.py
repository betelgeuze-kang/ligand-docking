from __future__ import annotations

import json
from pathlib import Path

from tools import build_runs_cleanup_batch5_heavy_bundle_review_manifest as mod


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_bytes(path: Path, size_bytes: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"0" * size_bytes)


def test_build_runs_cleanup_batch5_heavy_bundle_review_manifest(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()

    stage2_dir = runs / "external_validation_2026-03-29_set1_core_blind_kinase_core_full_p0_n10000_r1_stage2_traj_manifest_chunks"
    for idx in range(10):
        _write_bytes(stage2_dir / f"chunk_{idx:05d}.csv", 420_000)

    gpcr_stage3 = runs / "ligand_blind_gpcr_sample_stage3_scores.csv"
    _write_bytes(gpcr_stage3, 3_400_000)

    stage3_delivery = runs / "stage3_inline_consume_smoke_2026-03-12_delivery"
    _write_bytes(stage3_delivery / "delivery_part_000.npz", 3_300_000)

    _write_bytes(runs / "ligand_blind_trpv1_small_stage3_scores.csv", 1_000_000)

    source_stage_review = tmp_path / "runs_cleanup_batch4_stage_review_manifest_current.json"
    source_stage_review.write_text(
        json.dumps(
            {
                "summary": {"status": "runs_cleanup_batch4_stage_review_manifest_ready"},
                "families": [],
                "stage_reviews": [
                    {
                        "family_id": "ligand_blind_gpcr",
                        "family_label": "Blind GPCR screening",
                        "stage_id": "stage3",
                        "stage_label": "stage3 delivery and score artifacts",
                        "subgroup_id": "stage3_delivery_scores",
                        "source_match_count": 27,
                        "source_size_mb": 35.93,
                        "sampled_artifact_count": 3,
                    }
                ],
                "sample_details": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    source_audit = tmp_path / "runs_cleanup_audit_current.json"
    source_audit.write_text(
        json.dumps(
            {
                "summary": {
                    "runs_dir": str(runs),
                    "total_size_gb": 0.01,
                    "archive_only_cleanup_recommended": True,
                },
                "rows": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = mod.build_payload(
        runs_dir=str(runs),
        source_stage_review_manifest=str(source_stage_review),
        source_audit_artifact=str(source_audit),
        min_size_mb=3.0,
    )

    assert payload["summary"]["status"] == "runs_cleanup_batch5_heavy_bundle_review_manifest_ready"
    assert payload["summary"]["group_count"] == 3
    assert payload["summary"]["bundle_count"] == 3
    assert payload["summary"]["stage2_bundle_count"] == 1
    assert payload["summary"]["stage3_bundle_count"] == 2
    assert payload["summary"]["linked_stage_review_bundle_count"] == 1

    groups = {row["group_id"]: row for row in payload["groups"]}
    assert groups["stage2_kinase_heavy_bundle"]["bundle_count"] == 1
    assert groups["stage2_kinase_heavy_bundle"]["review_priority"] == "high"
    assert groups["stage3_gpcr_heavy_bundle"]["linked_stage_review_count"] == 1
    assert groups["stage3_misc_heavy_bundle"]["bundle_count"] == 1

    bundles = {row["bundle_name"]: row for row in payload["bundles"]}
    assert bundles[stage2_dir.name]["bundle_kind"] == "stage2_manifest_chunk_dir"
    assert bundles[stage2_dir.name]["recommended_disposition"] == "manual_review_heavy_bundle"
    assert bundles[gpcr_stage3.name]["source_stage_review_linked"] is True
    assert bundles[gpcr_stage3.name]["recommended_disposition"] == "review_for_archive_after_stage_review"
    assert bundles[stage3_delivery.name]["bundle_kind"] == "stage3_delivery_dir"


def test_build_runs_cleanup_batch5_heavy_bundle_review_manifest_filters_small_entries(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    _write_bytes(runs / "ligand_blind_gpcr_small_stage3_scores.csv", 500_000)

    source_stage_review = tmp_path / "runs_cleanup_batch4_stage_review_manifest_current.json"
    source_stage_review.write_text(
        json.dumps({"summary": {"status": "runs_cleanup_batch4_stage_review_manifest_ready"}, "families": [], "stage_reviews": [], "sample_details": []}),
        encoding="utf-8",
    )
    source_audit = tmp_path / "runs_cleanup_audit_current.json"
    source_audit.write_text(json.dumps({"summary": {"runs_dir": str(runs)}}), encoding="utf-8")

    payload = mod.build_payload(
        runs_dir=str(runs),
        source_stage_review_manifest=str(source_stage_review),
        source_audit_artifact=str(source_audit),
        min_size_mb=3.0,
    )

    assert payload["summary"]["bundle_count"] == 0
    assert payload["groups"] == []
    assert payload["bundles"] == []
