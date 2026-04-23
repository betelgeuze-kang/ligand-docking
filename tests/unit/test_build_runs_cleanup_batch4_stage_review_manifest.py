from __future__ import annotations

import json
from pathlib import Path

from tools import build_runs_cleanup_batch4_stage_review_manifest as mod


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_runs_cleanup_batch4_stage_review_manifest(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()

    families = [
        ("ligand_blind_gpcr", "Blind GPCR screening", "ADRB2_GPCR_BLIND"),
        ("ligand_blind_trpv1", "Blind TRPV1 screening", "TRPV1_ION_CHANNEL_BLIND"),
        ("ligand_stress_commercial", "Commercial ligand stress runs", "KRAS_G12D|EGFR_KINASE|HIV1_PROTEASE"),
    ]
    rows: list[dict[str, object]] = []

    for family_id, family_label, target_preview in families:
        stage1_artifacts = [
            f"{family_id}_sample_stage1_ligands.json",
            f"{family_id}_sample_stage1_queue.csv",
            f"{family_id}_sample_stage1_summary.json",
        ]
        _write(runs / stage1_artifacts[0], json.dumps({"source": "csv", "count": 4, "rows": [1, 2, 3, 4]}))
        _write(runs / stage1_artifacts[1], "queue_id,target,ligand_id\nq1,T1,L1\nq2,T1,L2\n")
        _write(
            runs / stage1_artifacts[2],
            json.dumps(
                {
                    "generated_at_local": "2026-03-29T09:00:00",
                    "targets": 1,
                    "target_list": [target_preview],
                    "ligands": 4,
                    "queue_rows": 2,
                    "queue_policy": "round_robin",
                }
            ),
        )
        rows.append(
            {
                "family_id": family_id,
                "family_label": family_label,
                "subgroup_id": "stage1_queue_inputs",
                "match_count": 12,
                "size_mb": 1.5,
                "recommended_disposition": "review_for_archive_after_sampling",
                "sample_artifacts": "; ".join(stage1_artifacts),
            }
        )

        stage2_artifacts = [
            f"{family_id}_sample_stage2_active_learning_hard_scores.csv",
            f"{family_id}_sample_stage2_active_learning_hard_summary.json",
            f"{family_id}_sample_stage2_active_learning_summary.json",
        ]
        _write(runs / stage2_artifacts[0], "target,paired,ood_reason\nT1,1,none\n")
        _write(
            runs / stage2_artifacts[1],
            json.dumps(
                {
                    "summary": {
                        "targets_total": 3,
                        "selected_targets_count": 1,
                        "max_hard_score": 0.75,
                        "mean_hard_score": 0.5,
                    }
                }
            ),
        )
        _write(
            runs / stage2_artifacts[2],
            json.dumps(
                {
                    "pass": True,
                    "summary": {
                        "hard_mining_selected_targets_count": 1,
                        "hard_mining_priority_targets_matched": 1,
                    },
                }
            ),
        )
        rows.append(
            {
                "family_id": family_id,
                "family_label": family_label,
                "subgroup_id": "stage2_active_learning",
                "match_count": 24,
                "size_mb": 2.5,
                "recommended_disposition": "review_for_archive_after_sampling",
                "sample_artifacts": "; ".join(stage2_artifacts),
            }
        )

        stage3_artifacts = [
            f"{family_id}_sample_stage3_scores.csv",
            f"{family_id}_sample_stage3_summary.json",
            f"{family_id}_sample_stage3_summary.md",
        ]
        _write(runs / stage3_artifacts[0], "queue_id,target,binding_energy_proxy\nq1,T1,-0.3\nq2,T1,-0.2\n")
        _write(
            runs / stage3_artifacts[1],
            json.dumps(
                {
                    "queue_rows": 2,
                    "processed_jobs": 2,
                    "parallel_enabled": family_id != "ligand_stress_commercial",
                    "avg_binding_energy_proxy": -0.25,
                    "avg_stability_score": 0.01,
                    "priority_sampling": {
                        "applied": True,
                        "priority_rows_selected": 2,
                        "priority_rows_in_queue": 2,
                        "fallback_rows_selected": 0,
                    },
                }
            ),
        )
        _write(
            runs / stage3_artifacts[2],
            "\n".join(
                [
                    "# Ligand Backmapping + Scoring",
                    "",
                    "- generated_at_local: 2026-03-29T09:10:00",
                    "- queue_rows: 2",
                    "- processed_jobs: 2",
                    "- avg_binding_energy_proxy: -0.25",
                    "- avg_stability_score: 0.01",
                    "",
                ]
            ),
        )
        rows.append(
            {
                "family_id": family_id,
                "family_label": family_label,
                "subgroup_id": "stage3_delivery_scores",
                "match_count": 8,
                "size_mb": 3.25,
                "recommended_disposition": "review_for_archive_after_sampling",
                "sample_artifacts": "; ".join(stage3_artifacts),
            }
        )

    source_manifest = tmp_path / "runs_cleanup_batch3_review_manifest_current.json"
    source_manifest.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "runs_cleanup_batch3_review_manifest_ready",
                    "runs_dir": str(runs),
                },
                "rows": rows
                + [
                    {
                        "family_id": "unrelated_family",
                        "family_label": "ignore me",
                        "subgroup_id": "stage1_queue_inputs",
                        "match_count": 99,
                        "size_mb": 9.9,
                        "recommended_disposition": "ignore",
                        "sample_artifacts": "ignore.json",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = mod.build_payload(str(runs), str(source_manifest))

    assert payload["summary"]["status"] == "runs_cleanup_batch4_stage_review_manifest_ready"
    assert payload["summary"]["family_count"] == 3
    assert payload["summary"]["stage_review_count"] == 9
    assert payload["summary"]["sampled_artifact_count"] == 27
    assert payload["summary"]["missing_artifact_count"] == 0

    families_by_id = {row["family_id"]: row for row in payload["families"]}
    assert families_by_id["ligand_blind_gpcr"]["stage_review_count"] == 3
    assert families_by_id["ligand_blind_trpv1"]["source_match_count"] == 44
    assert families_by_id["ligand_stress_commercial"]["sampled_artifact_count"] == 9

    stage_reviews = {(row["family_id"], row["stage_id"]): row for row in payload["stage_reviews"]}
    gpcr_stage1 = stage_reviews[("ligand_blind_gpcr", "stage1")]
    assert gpcr_stage1["sampled_artifact_count"] == 3
    assert "count=4" in gpcr_stage1["sample_highlights"]
    assert "rows=2, columns=3, targets=1" in gpcr_stage1["sample_highlights"]
    assert "targets=1" in gpcr_stage1["sample_highlights"]

    trpv1_stage2 = stage_reviews[("ligand_blind_trpv1", "stage2")]
    assert "selected_targets_count=1" in trpv1_stage2["sample_highlights"]
    assert "pass=true" in trpv1_stage2["sample_highlights"]

    stress_stage3 = stage_reviews[("ligand_stress_commercial", "stage3")]
    assert "avg_binding_energy_proxy=-0.25" in stress_stage3["sample_highlights"]
    assert "title=Ligand Backmapping + Scoring" in stress_stage3["sample_highlights"]

    sample_details = {
        (row["family_id"], row["stage_id"], row["artifact_name"]): row for row in payload["sample_details"]
    }
    detail = sample_details[
        (
            "ligand_blind_gpcr",
            "stage2",
            "ligand_blind_gpcr_sample_stage2_active_learning_hard_scores.csv",
        )
    ]
    assert detail["artifact_kind"] == "scores_csv"
    assert detail["summary_excerpt"] == "rows=1, columns=3, targets=1, header=target|paired|ood_reason"


def test_build_runs_cleanup_batch4_stage_review_manifest_marks_missing_samples(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()

    existing = "ligand_blind_gpcr_sample_stage3_summary.md"
    _write(
        runs / existing,
        "\n".join(
            [
                "# Ligand Backmapping + Scoring",
                "",
                "- queue_rows: 4",
                "- processed_jobs: 4",
            ]
        ),
    )
    source_manifest = tmp_path / "runs_cleanup_batch3_review_manifest_current.json"
    source_manifest.write_text(
        json.dumps(
            {
                "summary": {"status": "runs_cleanup_batch3_review_manifest_ready", "runs_dir": str(runs)},
                "rows": [
                    {
                        "family_id": "ligand_blind_gpcr",
                        "family_label": "Blind GPCR screening",
                        "subgroup_id": "stage3_delivery_scores",
                        "match_count": 3,
                        "size_mb": 0.4,
                        "recommended_disposition": "review_for_archive_after_sampling",
                        "sample_artifacts": "; ".join(
                            [
                                "missing_stage3_scores.csv",
                                "missing_stage3_summary.json",
                                existing,
                            ]
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_payload(str(runs), str(source_manifest))

    assert payload["summary"]["family_count"] == 1
    assert payload["summary"]["stage_review_count"] == 1
    assert payload["summary"]["missing_artifact_count"] == 2
    assert payload["stage_reviews"][0]["missing_artifact_count"] == 2
    missing_rows = [row for row in payload["sample_details"] if not row["exists"]]
    assert len(missing_rows) == 2
    assert all(row["summary_excerpt"] == "missing" for row in missing_rows)
