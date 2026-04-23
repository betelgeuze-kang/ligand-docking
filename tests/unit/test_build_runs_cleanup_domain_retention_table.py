from __future__ import annotations

import json
from pathlib import Path

from tools.build_runs_cleanup_domain_retention_table import build_payload


def test_build_runs_cleanup_domain_retention_table(tmp_path: Path) -> None:
    holdout_json = tmp_path / "holdout.json"
    audit_json = tmp_path / "audit.json"
    holdout_json.write_text(
        json.dumps({"summary": {"protected_prefix_count": 7, "review_hold_reference_prefix_count": 7}}),
        encoding="utf-8",
    )
    audit_json.write_text(
        json.dumps({"summary": {"top_size_prefix": "idp_3bead_holdout", "top_size_prefix_size_mb": 529.73}}),
        encoding="utf-8",
    )

    payload = build_payload(str(holdout_json), str(audit_json))

    assert payload["summary"]["status"] == "runs_cleanup_domain_retention_table_ready"
    rows = {row["domain_id"]: row for row in payload["rows"]}
    assert rows["idp_holdout"]["keep_policy"] == "keep_current_plus_minimal_baseline_reference_pack"
    assert rows["external_validation"]["archive_policy"] == "do not expand back into active root"
