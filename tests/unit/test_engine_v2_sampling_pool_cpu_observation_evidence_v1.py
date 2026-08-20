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
        "eafcf3a7ebfe80c7f5b777d0a526a1fa7cd4ae8c5b6f01da74d4393d6b904cc5"
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

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["observation"]["performance_claim_authorized"] = True
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="observation keys",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["observation"]["fixtures"][0]["unreviewed_metric"] = 1
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="fixture keys",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["observation"]["fixtures"][0]["peak_rss_delta_kib"] = (
        value["observation"]["fixtures"][0]["peak_rss_kib"] + 1
    )
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="delta exceeds",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["build"]["build_environment"]["RUSTFLAGS"] = {
        "set": True,
        "value_sha256": int("1" * 64),
    }
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="build environment metadata",
    ):
        evidence.verify(_reseal(value))

    value = json.loads(EVIDENCE.read_text(encoding="ascii"))
    value["host"]["system"] = "OtherOS"
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="host identity",
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


def test_affinity_and_imported_runner_binding_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="affinity changed",
    ):
        evidence._require_stable_affinity([0, 1], [0])

    replacement = tmp_path / "run_engine_v2_sampling_pool_cpu_observation_v1.py"
    replacement.write_text("# changed\n", encoding="ascii")
    monkeypatch.setattr(evidence.observer, "__file__", str(replacement))
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="imported observation runner differs",
    ):
        evidence._verify_imported_observer_binding()


def test_effective_affinity_cpu_models_are_complete_and_homogeneous() -> None:
    cpuinfo = """\
processor : 0
model name : Example CPU A

processor : 1
model name : Example CPU A
"""
    assert evidence._affinity_cpu_models_from(cpuinfo, [0, 1]) == {
        "0": "Example CPU A",
        "1": "Example CPU A",
    }
    with pytest.raises(
        evidence.SamplingPoolCPUObservationEvidenceError,
        match="unavailable for effective affinity",
    ):
        evidence._affinity_cpu_models_from(cpuinfo, [0, 2])
