from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools import capture_engine_v2_sampling_pool_cpu_observation_v1 as evidence


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "config/engine_v2_sampling_pool_cpu_observation_evidence_v1.json"


def _reseal(value: dict[str, object]) -> dict[str, object]:
    projection = copy.deepcopy(value)
    projection.pop("receipt_sha256", None)
    return {
        **projection,
        "receipt_sha256": evidence._receipt_sha256(projection),
    }


def test_committed_source_binary_host_bound_observation_verifies() -> None:
    value = evidence.load_and_verify(EVIDENCE)
    assert value["receipt_sha256"] == (
        "18474af83f0969f158c83b610e8fde61aa80d3a6682d75e4d32100cd86d98538"
    )
    assert value["source"]["merged_main_commit"] == evidence.SOURCE_BASELINE_COMMIT
    assert value["source"]["merged_main_tree"] == evidence.SOURCE_BASELINE_TREE
    assert value["observation"]["sample_count"] == evidence.SAMPLE_COUNT
    assert all(item is False for item in value["authority"].values())


def test_resealed_semantic_cross_wiring_fails_closed() -> None:
    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["observation"]["fixtures"][0]["wall_time_ns_samples"][0] = 0
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="timing or memory",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    del value["authority"]["reservation_authorized"]
    value["observation"]["authority"] = copy.deepcopy(value["authority"])
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="authority",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["source"]["unreviewed_source"] = "0" * 64
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="source binding keys",
    ):
        evidence.verify(_reseal(value))


def test_capture_is_blocked_in_github_actions_before_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(
        evidence.observer,
        "_build_library",
        lambda: (_ for _ in ()).throw(AssertionError("build must not run")),
    )
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="cannot capture timing",
    ):
        evidence.capture()


def test_evidence_write_is_exclusive(tmp_path: Path) -> None:
    destination = tmp_path / "evidence.json"
    evidence._write_exclusive(destination, b"{}\n")
    assert destination.read_bytes() == b"{}\n"
    with pytest.raises(FileExistsError):
        evidence._write_exclusive(destination, b"changed\n")
