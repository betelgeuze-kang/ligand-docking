from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.reconcile_engine_v2_stage0_full_suites import (
    DECLARED_PR_COUNTS,
    SCHEMA_ID,
    build_reconciliation,
)


def _write_junit(path: Path, extra_failure: str = "") -> None:
    path.write_text(
        f"""<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="stage0">
  <testcase classname="tests.unit.test_a" name="failure">
    <failure message="failure">detail</failure>
  </testcase>
  <testcase classname="tests.unit.test_b" name="error">
    <error message="error">detail</error>
  </testcase>
  {extra_failure}
</testsuite></testsuites>
""",
        encoding="utf-8",
    )


def test_reconciliation_binds_equal_nonpassing_row_multisets(tmp_path: Path) -> None:
    historical = tmp_path / "historical.xml"
    current = tmp_path / "current.xml"
    _write_junit(historical)
    _write_junit(current)

    payload = build_reconciliation(
        historical,
        current,
        historical_source_commit_sha="a" * 40,
    )

    assert payload["schema_id"] == SCHEMA_ID
    assert payload["declared_pr_counts"] == DECLARED_PR_COUNTS
    assert payload["historical_reproduction"] == {"failed": 1, "errors": 1}
    assert payload["current_reproduction"] == {"failed": 1, "errors": 1}
    assert payload["historical_and_current_row_multisets_equal"] is True
    assert payload["only_historical_rows"] == []
    assert payload["only_current_rows"] == []
    unhashed = dict(payload)
    receipt_sha256 = unhashed.pop("receipt_sha256")
    assert receipt_sha256 == hashlib.sha256(
        json.dumps(
            unhashed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def test_reconciliation_preserves_duplicate_row_occurrences(tmp_path: Path) -> None:
    historical = tmp_path / "historical.xml"
    current = tmp_path / "current.xml"
    duplicate = """
  <testcase classname="tests.unit.test_a" name="failure">
    <failure message="failure">detail</failure>
  </testcase>"""
    _write_junit(historical, duplicate)
    _write_junit(current)

    payload = build_reconciliation(
        historical,
        current,
        historical_source_commit_sha="b" * 40,
    )

    assert payload["historical_reproduction"] == {"failed": 2, "errors": 1}
    assert payload["historical_and_current_row_multisets_equal"] is False
    assert payload["only_historical_rows"] == [
        ["tests.unit.test_a", "failure", "failure", 1]
    ]
