from __future__ import annotations

import json
from pathlib import Path

from tools.build_idp_3bead_holdout_archive_first_manifest import build_payload


def test_build_idp_3bead_holdout_archive_first_manifest(tmp_path: Path) -> None:
    review_json = tmp_path / "review.json"
    review_json.write_text(
        json.dumps(
            {
                "summary": {"status": "idp_3bead_holdout_cleanup_review_manifest_ready"},
                "rows": [
                    {
                        "prefix": "idp_3bead_holdout_v7_fastpair_2026-03-16_r1",
                        "classification": "legacy_branch_candidate",
                        "recommended_disposition": "review_for_archive_after_prefix_signoff",
                        "file_count": 474,
                        "size_mb": 29.39,
                        "sample_artifacts": "a; b",
                        "reason": "legacy",
                    },
                    {
                        "prefix": "idp_3bead_holdout_v7_anchor_commercial_pretest_r1",
                        "classification": "protected_current_lane",
                        "recommended_disposition": "keep_in_active_root",
                        "file_count": 178,
                        "size_mb": 6.16,
                        "sample_artifacts": "c; d",
                        "reason": "protected",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = build_payload(str(review_json))

    assert payload["summary"]["status"] == "idp_3bead_holdout_archive_first_manifest_ready"
    assert payload["summary"]["archive_candidate_prefix_count"] == 1
    assert payload["rows"][0]["prefix"] == "idp_3bead_holdout_v7_fastpair_2026-03-16_r1"
