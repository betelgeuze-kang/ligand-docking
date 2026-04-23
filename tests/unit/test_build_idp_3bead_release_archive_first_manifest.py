from __future__ import annotations

import json
from pathlib import Path

from tools.build_idp_3bead_release_archive_first_manifest import build_payload


def test_build_idp_3bead_release_archive_first_manifest(tmp_path: Path) -> None:
    review_json = tmp_path / "review.json"
    review_json.write_text(
        json.dumps(
            {
                "summary": {"status": "idp_3bead_release_cleanup_review_manifest_ready"},
                "rows": [
                    {
                        "prefix": "idp_3bead_release_smoke_current_2026-03-22_external-foo",
                        "classification": "historical_release_smoke_candidate",
                        "recommended_disposition": "review_for_archive_after_prefix_signoff",
                        "file_count": 12,
                        "size_mb": 3.5,
                        "sample_artifacts": "a; b",
                        "reason": "stale",
                    },
                    {
                        "prefix": "idp_3bead_release_smoke_current_2026-03-20_speedopt3full",
                        "classification": "review_hold_current_reference",
                        "recommended_disposition": "review_only_keep_until_reference_replaced",
                        "file_count": 10,
                        "size_mb": 1.1,
                        "sample_artifacts": "c",
                        "reason": "keep",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    payload = build_payload(str(review_json))
    assert payload["summary"]["status"] == "idp_3bead_release_archive_first_manifest_ready"
    assert payload["summary"]["archive_candidate_prefix_count"] == 1
    assert payload["rows"][0]["prefix"] == "idp_3bead_release_smoke_current_2026-03-22_external-foo"
