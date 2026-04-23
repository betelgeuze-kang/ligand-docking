from __future__ import annotations

import json
from pathlib import Path

from tools.build_runs_cleanup_batch5_family_signoff_note import build_payload


def test_build_runs_cleanup_batch5_family_signoff_note(tmp_path: Path) -> None:
    source_json = tmp_path / "batch5_manifest.json"
    source_json.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "runs_cleanup_batch5_stage_heavy_review_manifest_ready",
                    "remaining_heavy_size_gb": 0.13,
                },
                "families": [
                    {
                        "family_id": "ligand_blind_gpcr",
                        "remaining_heavy_group_count": 2,
                        "remaining_heavy_match_count": 14,
                        "remaining_heavy_size_mb": 59.84,
                    }
                ],
                "rows": [
                    {"family_id": "ligand_blind_gpcr", "group_id": "stage2_traj_manifest_bundle"},
                    {"family_id": "ligand_blind_gpcr", "group_id": "stage3_scores_bundle"},
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = build_payload(str(source_json))

    assert payload["summary"]["status"] == "runs_cleanup_batch5_family_signoff_note_ready"
    assert payload["summary"]["family_count"] == 1
    assert payload["summary"]["recommended_approve_count"] == 1
    row = payload["rows"][0]
    assert row["family_id"] == "ligand_blind_gpcr"
    assert row["groups_under_review"] == "stage2_traj_manifest_bundle; stage3_scores_bundle"
    assert row["signoff_recommendation"] == "approve_archive_after_sampling"
