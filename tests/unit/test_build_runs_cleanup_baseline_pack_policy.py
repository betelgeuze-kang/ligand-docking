from __future__ import annotations

import json
from pathlib import Path

from tools.build_runs_cleanup_baseline_pack_policy import build_payload


def test_build_runs_cleanup_baseline_pack_policy(tmp_path: Path) -> None:
    holdout_json = tmp_path / "holdout.json"
    audit_json = tmp_path / "audit.json"
    holdout_json.write_text(
        json.dumps(
            {
                "summary": {
                    "protected_prefix_count": 7,
                    "review_hold_reference_prefix_count": 7,
                    "stale_candidate_prefix_count": 69,
                }
            }
        ),
        encoding="utf-8",
    )
    audit_json.write_text(
        json.dumps({"summary": {"current_artifact_file_count": 100, "archive_only_cleanup_recommended": True}}),
        encoding="utf-8",
    )

    payload = build_payload(str(holdout_json), str(audit_json))

    assert payload["summary"]["status"] == "runs_cleanup_baseline_pack_policy_ready"
    assert payload["summary"]["idp_stale_candidate_prefix_count"] == 69
    assert any(row["retention_group"] == "idp_stale_historical_holdouts" for row in payload["rows"])
