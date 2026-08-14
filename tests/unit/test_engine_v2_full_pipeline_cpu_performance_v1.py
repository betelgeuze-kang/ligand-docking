from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from betelgeuze_engine_v2.docking import full_pipeline_cpu_performance_v1 as profile
from tools import run_engine_v2_full_pipeline_cpu_performance_v1 as runner


def _digest(marker: int) -> str:
    return f"{marker:02x}" * 32


def _session_authority_false() -> dict[str, bool]:
    return {field: False for field in profile.EXPECTED_SESSION_AUTHORITY_FALSE_FIELDS}


def _evidence_authority_false() -> dict[str, bool]:
    return {field: False for field in profile.EXPECTED_EVIDENCE_AUTHORITY_FALSE_FIELDS}


def _metadata(backend: str) -> dict[str, object]:
    return {
        "backend": backend,
        "candidate_denominator": 64,
        "persistent_native_context": True,
        "context_reused_across_runs": True,
        "scientific_result_cached": False,
        "result_dependent_input_consumed": False,
        "caller_science_transport_consumed": False,
        "synthetic_only_acknowledgment": profile.SYNTHETIC_ONLY_ACKNOWLEDGMENT,
        **_session_authority_false(),
    }


def _document(
    backend: str, *, pipeline_receipt: str | None = None
) -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    for index in range(64):
        terms = [float(index + term) for term in range(8)]
        candidates.append(
            {
                "slot_index": index,
                "scorer_v1": {
                    "status": 0,
                    "failure_code": 0,
                    "weighted_terms": terms,
                    "total_score": float(sum(terms)),
                    "receptor_candidate_pair_count": 0,
                    "ligand_pair_count": 0,
                    "hbond_count": 0,
                    "hydrophobic_contact_count": 0,
                    "buried_polar_count": 0,
                },
                "validity": {
                    field: (
                        0.0 if field in profile.EXPECTED_VALIDITY_FLOAT_FIELDS else 0
                    )
                    for field in profile.EXPECTED_VALIDITY_FIELDS
                },
                "ranking": {
                    "rank_eligible": True,
                    "valid_rank_eligible": True,
                    "stable_rank": index,
                    "stable_valid_rank": index,
                    "total_score": float(sum(terms)),
                    "coordinate_sha256": _digest(3),
                },
                "lineage": {
                    field: _digest(4)
                    for field in profile.REQUIRED_LINEAGE_DIGEST_FIELDS
                },
                **{
                    field: _digest(7)
                    for field in profile.REQUIRED_EXACT_CANDIDATE_SOURCE_DIGEST_FIELDS
                },
                "numeric_projection": [float(index)] * 243,
            }
        )
    return {
        "backend": backend,
        "consumer": "benchmark",
        "candidate_denominator": 64,
        "candidates": candidates,
        "repository_scientific_decision_sha256": profile.EXPECTED_DECISION_SHA256,
        "scientific_projection_sha256": _digest(
            5 if backend == "cpp_cpu_reference" else 6
        ),
        "pipeline_receipt_sha256": pipeline_receipt
        or _digest(1 if backend == "cpp_cpu_reference" else 2),
        "denominator_preserved": True,
        "result_dependent_input_consumed": False,
        "operator_second_opinion_authorized": False,
        **profile.EXPECTED_STAGE_COUNTS,
        **{
            field: list(value)
            for field, value in profile.EXPECTED_RANK_SELECTION.items()
        },
        **profile.EXPECTED_SOURCE_IDENTITIES,
        **_evidence_authority_false(),
    }


class _Evidence:
    def __init__(self, document: dict[str, object]) -> None:
        self._document = deepcopy(document)

    def to_dict(self) -> dict[str, object]:
        return deepcopy(self._document)


class _Session:
    def __init__(self, backend: str) -> None:
        self.backend = backend
        self.run_count = 0
        self._metadata = _metadata(backend)
        self._document = _document(backend)

    def describe(self) -> dict[str, object]:
        return deepcopy(self._metadata)

    def run(self, *, surface: str) -> _Evidence:
        assert surface == "benchmark"
        self.run_count += 1
        return _Evidence(self._document)


class _Clock:
    def __init__(self, step: int) -> None:
        self.value = 0
        self.step = step

    def __call__(self) -> int:
        self.value += self.step
        return self.value


def test_injected_full_pipeline_measurement_uses_fixed_paired_schedule() -> None:
    sessions: dict[str, _Session] = {}

    def factory(backend: str) -> _Session:
        assert backend not in sessions
        session = _Session(backend)
        sessions[backend] = session
        return session

    receipt = profile._run_injected_test_double(
        session_factory=factory,
        wall_clock_ns=_Clock(100),
        process_clock_ns=_Clock(40),
    )
    document = receipt.to_dict()

    assert set(sessions) == {"cpp_cpu_reference", "rust_cpu"}
    assert all(
        session.run_count == profile.WARMUP_COUNT + profile.SAMPLE_COUNT
        for session in sessions.values()
    )
    assert len(document["observations"]) == 2 * profile.SAMPLE_COUNT
    assert [row["backend"] for row in document["observations"][:6]] == [
        "cpp_cpu_reference",
        "rust_cpu",
        "rust_cpu",
        "cpp_cpu_reference",
        "cpp_cpu_reference",
        "rust_cpu",
    ]
    assert document["summaries"] == {
        "cpp_cpu_reference": {
            "wall_p50_ns": 100,
            "wall_p95_ns": 100,
            "process_p50_ns": 40,
            "process_p95_ns": 40,
        },
        "rust_cpu": {
            "wall_p50_ns": 100,
            "wall_p95_ns": 100,
            "process_p50_ns": 40,
            "process_p95_ns": 40,
        },
    }
    assert document["test_double_only"] is True
    assert document["full_numeric_parity_passed"] is True
    assert document["parity_pair_count"] == (
        profile.WARMUP_COUNT + profile.SAMPLE_COUNT
    )
    assert all(
        row["compared_f64_count"] == profile.EXPECTED_PARITY_F64_COUNT
        and row["maximum_absolute_difference"] == 0.0
        and row["full_numeric_parity"] is True
        for row in document["parity_observations"]
    )
    assert document["parity_observations"][0][
        "baseline_scientific_projection_sha256"
    ] == _digest(5)
    assert document["parity_observations"][0][
        "experimental_scientific_projection_sha256"
    ] == _digest(6)
    assert document["live_qualification_authority"] is False
    assert document["qualification_consumed"] is False
    assert document["reservation_created"] is False


def test_injected_measurement_rejects_incomplete_scorer_receipt() -> None:
    sessions: dict[str, _Session] = {}

    def factory(backend: str) -> _Session:
        session = _Session(backend)
        sessions[backend] = session
        if backend == "rust_cpu":
            candidates = session._document["candidates"]
            assert isinstance(candidates, list)
            candidates[0]["scorer_v1"]["weighted_terms"].pop()
        return session

    with pytest.raises(
        profile.FullPipelineCPUPerformanceV1Error,
        match="complete ScorerV1 term receipt",
    ):
        profile._run_injected_test_double(
            session_factory=factory,
            wall_clock_ns=_Clock(100),
            process_clock_ns=_Clock(40),
        )


def test_injected_measurement_rejects_authority_drift_before_timing() -> None:
    wall_clock = _Clock(100)

    def factory(backend: str) -> _Session:
        session = _Session(backend)
        if backend == "rust_cpu":
            session._metadata["molecular_execution_authorized"] = True
        return session

    with pytest.raises(
        profile.FullPipelineCPUPerformanceV1Error,
        match="granted molecular_execution_authorized",
    ):
        profile._run_injected_test_double(
            session_factory=factory,
            wall_clock_ns=wall_clock,
            process_clock_ns=_Clock(40),
        )
    assert wall_clock.value == 0


def test_injected_measurement_rejects_candidate_source_cross_wiring() -> None:
    wall_clock = _Clock(100)

    def factory(backend: str) -> _Session:
        session = _Session(backend)
        if backend == "rust_cpu":
            candidates = session._document["candidates"]
            assert isinstance(candidates, list)
            candidates[0]["source_proposal_sha256"] = _digest(8)
        return session

    with pytest.raises(
        profile.FullPipelineCPUPerformanceV1Error,
        match="cross-backend scientific parity",
    ):
        profile._run_injected_test_double(
            session_factory=factory,
            wall_clock_ns=wall_clock,
            process_clock_ns=_Clock(40),
        )
    assert wall_clock.value == 0


def test_injected_measurement_rejects_evidence_authority_drift_before_timing() -> None:
    wall_clock = _Clock(100)

    def factory(backend: str) -> _Session:
        session = _Session(backend)
        if backend == "rust_cpu":
            session._document["public_benchmark_authorized"] = True
        return session

    with pytest.raises(
        profile.FullPipelineCPUPerformanceV1Error,
        match="granted public_benchmark_authorized",
    ):
        profile._run_injected_test_double(
            session_factory=factory,
            wall_clock_ns=wall_clock,
            process_clock_ns=_Clock(40),
        )
    assert wall_clock.value == 0


def test_injected_measurement_rejects_score_rank_semantic_drift() -> None:
    def factory(backend: str) -> _Session:
        session = _Session(backend)
        if backend == "rust_cpu":
            candidates = session._document["candidates"]
            assert isinstance(candidates, list)
            candidates[0]["ranking"]["total_score"] += 1.0
        return session

    with pytest.raises(
        profile.FullPipelineCPUPerformanceV1Error,
        match="ScorerV1 or ranking semantics changed",
    ):
        profile._run_injected_test_double(
            session_factory=factory,
            wall_clock_ns=_Clock(100),
            process_clock_ns=_Clock(40),
        )


def test_injected_measurement_rejects_cross_backend_numeric_drift() -> None:
    wall_clock = _Clock(100)

    def factory(backend: str) -> _Session:
        session = _Session(backend)
        if backend == "rust_cpu":
            candidates = session._document["candidates"]
            assert isinstance(candidates, list)
            scorer = candidates[0]["scorer_v1"]
            ranking = candidates[0]["ranking"]
            scorer["weighted_terms"][0] += 1.0e-4
            scorer["total_score"] += 1.0e-4
            ranking["total_score"] += 1.0e-4
        return session

    with pytest.raises(
        profile.FullPipelineCPUPerformanceV1Error,
        match="cross-backend scientific parity changed",
    ):
        profile._run_injected_test_double(
            session_factory=factory,
            wall_clock_ns=wall_clock,
            process_clock_ns=_Clock(40),
        )
    assert wall_clock.value == 0


def test_injected_measurement_rejects_receipt_instability() -> None:
    class _DriftingSession(_Session):
        def run(self, *, surface: str) -> _Evidence:
            evidence = super().run(surface=surface)
            document = evidence.to_dict()
            document["pipeline_receipt_sha256"] = _digest(self.run_count)
            return _Evidence(document)

    with pytest.raises(
        profile.FullPipelineCPUPerformanceV1Error,
        match="not repeat-stable",
    ):
        profile._run_injected_test_double(
            session_factory=_DriftingSession,
            wall_clock_ns=_Clock(100),
            process_clock_ns=_Clock(40),
        )


def test_injected_measurement_rejects_nonpositive_clock_duration() -> None:
    with pytest.raises(
        profile.FullPipelineCPUPerformanceV1Error,
        match="duration is not positive",
    ):
        profile._run_injected_test_double(
            session_factory=_Session,
            wall_clock_ns=lambda: 1,
            process_clock_ns=lambda: 1,
        )


def test_live_full_pipeline_measurement_is_not_activated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "must-not-exist.json"

    with pytest.raises(
        profile.FullPipelineCPUPerformanceV1Error,
        match="execution is not activated",
    ):
        profile.run_live_full_pipeline_cpu_performance_v1(output)
    assert not output.exists()

    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(
        profile.FullPipelineCPUPerformanceV1Error,
        match="execution is not activated",
    ):
        runner.main(["--run-output", str(output)])
    assert not output.exists()


def test_github_actions_live_path_fails_before_output(
    monkeypatch, tmp_path: Path
) -> None:
    output = tmp_path / "must-not-exist.json"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    with pytest.raises(
        profile.FullPipelineCPUPerformanceV1Error,
        match="GitHub Actions cannot execute",
    ):
        runner.main(["--run-output", str(output)])
    assert not output.exists()
