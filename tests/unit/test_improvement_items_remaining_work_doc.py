from __future__ import annotations

from pathlib import Path

from deploy import product_release_bundle
from tools.product import build_product_release_source_of_truth_gate as source_of_truth


ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = ROOT / "docs" / "improvement_items_remaining_work.md"


def _doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_remaining_work_doc_tracks_current_release_metrics() -> None:
    text = _doc_text()
    bundle = product_release_bundle.build_release_bundle(release_id="doc-metric-check")
    command_count = len(source_of_truth.RELEASE_REFRESH_COMMANDS)

    assert f"`artifact_count={bundle['artifact_count']}`" in text
    assert f"`check_count={bundle['check_count']}`" in text
    assert f"`pass_count={bundle['pass_count']}`" in text
    assert f"`product_release_current_refresh_verified`, `command_count={command_count}`" in text
    assert f"`executed_count={command_count}`" in text
    assert f"`release_refresh_command_count={command_count}`" in text

    assert "`artifact_count=28`" not in text
    assert "`check_count=21`" not in text
    assert "`pass_count=21`" not in text
    assert "`command_count=76`" not in text
    assert "`executed_count=76`" not in text
    assert "`release_refresh_command_count=79`" not in text


def test_remaining_work_doc_tracks_current_third_party_license_review_gate() -> None:
    text = _doc_text()

    assert "`third_party_license_review_gate_ready`, `expected_review_asset_count=1`" in text
    assert "`review_csv_present=true`, `approved_review_asset_count=1`" in text
    assert "`missing_review_asset_count=0`, `blocker_count=0`" in text

    assert "`blocked_third_party_license_review_gate`" not in text
    assert "`review_csv_present=false`" not in text
    assert "`missing_review_asset_count=1`" not in text
