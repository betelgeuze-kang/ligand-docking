"""Published prepared-pose reports retain the old JSON and numeric contracts."""

import hashlib
import json

import pytest

from betelgeuze_engine.product.prepared_rigid_poses import evaluate_rigid_pose_request
from tests.unit.test_prepared_rigid_poses import _request
from tools.product import compare_prepared_candidate_policies as comparison
from tools.product.verify_prepared_cross_numerics import check_report


@pytest.mark.parametrize("failed_pose", [False, True])
def test_real_pose_report_reuses_encoding_without_changing_bytes_or_check(
    tmp_path, monkeypatch, failed_pose
):
    request = _request(tmp_path / "source")
    if failed_pose:
        request["poses"][0]["translation_angstrom"][0] = 1000.0
    raw = evaluate_rigid_pose_request(request)
    old_normalized = json.loads(comparison.canonical(raw))
    old_bytes = (comparison.canonical(old_normalized) + "\n").encode()
    old_checked = check_report(old_normalized)
    assert comparison._has_stable_mapping_keys(raw, old_normalized)

    original = comparison.canonical
    calls = []

    def counted(value):
        calls.append(value)
        return original(value)

    monkeypatch.setattr(comparison, "canonical", counted)
    path = tmp_path / "report.json"
    normalized, checked = comparison._checked_pose_report(path, raw, check_report)

    assert len(calls) == 1
    assert normalized == old_normalized
    assert checked == old_checked
    assert normalized["denominator"] == raw["denominator"]
    assert [row["status"] for row in normalized["rows"]] == [
        row["status"] for row in raw["rows"]
    ]
    assert path.read_bytes() == old_bytes
    assert comparison.file_ref(path)["sha256"] == hashlib.sha256(old_bytes).hexdigest()


def test_non_string_nested_mapping_keys_keep_second_encoding(tmp_path, monkeypatch):
    raw = {"rows": [{"status": "failed", "source_metadata": {2: "two", 10: "ten"}}]}
    old_normalized = json.loads(comparison.canonical(raw))
    old_bytes = (comparison.canonical(old_normalized) + "\n").encode()
    seen = []

    def checker(value):
        seen.append(value)
        return {"status": "not_passed", "denominator": {"failed": 1}}

    original = comparison.canonical
    calls = []

    def counted(value):
        calls.append(value)
        return original(value)

    monkeypatch.setattr(comparison, "canonical", counted)
    path = tmp_path / "exceptional.json"
    normalized, checked = comparison._checked_pose_report(path, raw, checker)

    assert len(calls) == 2
    assert seen == [old_normalized]
    assert normalized == old_normalized
    assert checked["status"] == "not_passed"
    assert path.read_bytes() == old_bytes
    assert path.read_bytes() != (original(raw) + "\n").encode()


def test_colliding_mixed_mapping_keys_fail_before_publication(tmp_path):
    raw = {"source_metadata": {1: "numeric", "1": "string"}}
    path = tmp_path / "collision.json"
    with pytest.raises(TypeError):
        comparison._checked_pose_report(path, raw, lambda _: None)
    assert not path.exists()
