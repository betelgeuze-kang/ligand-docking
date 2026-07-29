from __future__ import annotations

import hashlib
from pathlib import Path

from tools.classify_engine_v2_stage0_full_suite import build_classification


def test_full_suite_classifier_is_complete_and_failure_text_safe(tmp_path: Path) -> None:
    junit = tmp_path / "suite.xml"
    junit.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="stage0" tests="6" failures="5" errors="1">
  <testcase classname="tests.unit.test_engine_v2_public_redocking_runner_stage7" name="inotify">
    <failure message="pinned inputs could not be monitored for mutation">detail</failure>
  </testcase>
  <testcase classname="tests.validation.test_accuracy_vs_experimental" name="native">
    <failure message="Native structure missing">detail</failure>
  </testcase>
  <testcase classname="tests.unit.test_build_wetlab_packet" name="product_fixture">
    <failure message="FileNotFoundError: runs/current.json">detail</failure>
  </testcase>
  <testcase classname="tests.unit.test_plain_fixture" name="fixture">
    <failure message="FileNotFoundError: data/current.json">detail</failure>
  </testcase>
  <testcase classname="tests.unit.test_abcd_product_capabilities" name="legacy">
    <failure message="old id != new id">detail</failure>
  </testcase>
  <testcase classname="tests.unit.test_contract" name="regression">
    <error message="AssertionError: mismatch">sensitive detail</error>
  </testcase>
</testsuite></testsuites>
""",
        encoding="utf-8",
    )

    payload = build_classification(junit)

    assert payload["current_reproduction"] == {
        "failed": 5,
        "errors": 1,
        "nonpassing_total": 6,
    }
    assert payload["category_counts"] == {
        "actual_regression": 1,
        "fixture_dependent": 1,
        "host_capability_missing": 1,
        "local_evidence_required": 1,
        "legacy_deterministic": 1,
        "product_fixture_dependent": 1,
    }
    assert payload["all_outcomes_classified"] is True
    assert payload["source_junit_sha256"] == hashlib.sha256(junit.read_bytes()).hexdigest()
    assert "message" not in payload["rows"][0]
    assert all(len(row["message_sha256"]) == 64 for row in payload["rows"])
