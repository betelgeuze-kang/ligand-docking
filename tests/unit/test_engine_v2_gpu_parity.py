from __future__ import annotations

from dataclasses import replace

import pytest

from betelgeuze_engine_v2.docking.backend_abi import EngineV2Backend
from betelgeuze_engine_v2.docking.gpu_parity import (
    FailClosedProbeEvidence,
    FailClosedProbeKind,
    GATE_DENOMINATOR,
    GATE_FAILURE_CODES,
    GATE_HIP_SAFE_PRECEDENT,
    GATE_OOM_FAIL_CLOSED,
    GATE_OVERFLOW_FAIL_CLOSED,
    GATE_REPEATED_RANK,
    GATE_SCORER_TERMS,
    GATE_TOP1,
    GATE_TOP5,
    GATE_V7_DECISION,
    GATE_VALIDITY,
    GPUArchitectureParityEvidence,
    GPUParityError,
    GPU_OOM_FAILURE_CODE,
    GPU_PAIR_LIST_OVERFLOW_FAILURE_CODE,
    ParityCandidateEvidence,
    ParityProbeExecutionReceipt,
    ParityRunEvidence,
    SCORER_V1_TERM_NAMES,
    ScorerV1TermTolerance,
    verify_gpu_architecture_qualification,
    verify_gpu_claim_qualification,
)
from tests.unit.test_engine_v2_backend_abi import backend_receipt


def _terms(candidate_index: int, delta: float = 0.0) -> dict[str, float]:
    return {
        name: float(candidate_index * 10 + term_index) + delta
        for term_index, name in enumerate(SCORER_V1_TERM_NAMES)
    }


def _candidates(
    *,
    term_delta: dict[str, float] | None = None,
    validity_override: dict[str, bool | None] | None = None,
    decision_override: dict[str, str] | None = None,
    failure_override: dict[str, str] | None = None,
) -> tuple[ParityCandidateEvidence, ...]:
    term_delta = term_delta or {}
    validity_override = validity_override or {}
    decision_override = decision_override or {}
    failure_override = failure_override or {}
    rows: list[ParityCandidateEvidence] = []
    for index in range(6):
        candidate_id = f"candidate-{index}"
        default_failure = "proposal_failed" if index == 5 else ""
        failure = failure_override.get(candidate_id, default_failure)
        succeeded = not failure
        pose_valid = validity_override.get(candidate_id, index % 2 == 0)
        rows.append(
            ParityCandidateEvidence(
                candidate_id=candidate_id,
                failure_code=failure,
                scorer_terms=(
                    _terms(index, term_delta.get(candidate_id, 0.0))
                    if succeeded
                    else None
                ),
                pose_valid=(pose_valid if succeeded else None),
                validity_flags=(
                    {
                        "chemical_valid": pose_valid,
                        "geometric_valid": pose_valid,
                        "posebusters_valid": pose_valid,
                        "selection_eligible": pose_valid,
                    }
                    if succeeded
                    else None
                ),
                validity_reason_codes=(
                    (() if pose_valid else ("fixture_pose_invalid",))
                    if succeeded
                    else None
                ),
                v7_decision=decision_override.get(
                    candidate_id,
                    "selected"
                    if index == 0
                    else ("not_scored" if failure else "retained"),
                ),
            )
        )
    return tuple(rows)


def _execution(
    receipt,
    *,
    input_digest: str = "5",
    runner_digest: str = "6",
) -> ParityProbeExecutionReceipt:
    return ParityProbeExecutionReceipt(
        backend_receipt=receipt,
        input_candidate_set_receipt_sha256=input_digest * 64,
        runner_execution_receipt_sha256=runner_digest * 64,
    )


def _run(
    run_id: str,
    *,
    receipt,
    candidates: tuple[ParityCandidateEvidence, ...] | None = None,
    ranked: tuple[str, ...] = (
        "candidate-0",
        "candidate-1",
        "candidate-2",
        "candidate-3",
        "candidate-4",
    ),
    input_digest: str = "5",
    runner_digest: str = "6",
) -> ParityRunEvidence:
    return ParityRunEvidence(
        run_id=run_id,
        probe_execution=_execution(
            receipt,
            input_digest=input_digest,
            runner_digest=runner_digest,
        ),
        candidates=candidates or _candidates(),
        ranked_candidate_ids=ranked,
    )


def _probe(
    kind: FailClosedProbeKind,
    *,
    receipt,
    passing: bool = True,
) -> FailClosedProbeEvidence:
    failure_code = {
        FailClosedProbeKind.OOM: GPU_OOM_FAILURE_CODE,
        FailClosedProbeKind.PAIR_LIST_OVERFLOW: GPU_PAIR_LIST_OVERFLOW_FAILURE_CODE,
    }[kind]
    return FailClosedProbeEvidence(
        kind=kind,
        probe_execution=_execution(
            receipt,
            input_digest=("7" if kind is FailClosedProbeKind.OOM else "8"),
            runner_digest=("9" if kind is FailClosedProbeKind.OOM else "a"),
        ),
        trigger_observed=True,
        failure_code=failure_code,
        partial_results_emitted=not passing,
        implicit_fallback_used=False,
    )


def _evidence(
    *,
    backend: EngineV2Backend = EngineV2Backend.HIP_SAFE,
    architecture: str = "gfx1030",
    expected_denominator: int = 6,
    gpu_runs: tuple[ParityRunEvidence, ...] | None = None,
    oom_probe: FailClosedProbeEvidence | None = None,
    overflow_probe: FailClosedProbeEvidence | None = None,
    safe_receipt: str | None = None,
) -> GPUArchitectureParityEvidence:
    gpu_receipt = (
        gpu_runs[0].backend_receipt
        if gpu_runs
        else backend_receipt(backend, architecture=architecture)
    )
    if gpu_runs is None:
        gpu_runs = (
            _run(
                "gpu-repeat-1",
                receipt=gpu_receipt,
                candidates=_candidates(term_delta={"candidate-2": 2.0e-13}),
                runner_digest="6",
            ),
            _run(
                "gpu-repeat-2",
                receipt=gpu_receipt,
                candidates=_candidates(term_delta={"candidate-2": -2.0e-13}),
                runner_digest="b",
            ),
        )
    source = gpu_receipt.source_binding
    reference_receipt = backend_receipt(
        EngineV2Backend.RUST_CPU,
        exact_source=source.exact_source_receipt_sha256[0],
        algorithm_profile=source.algorithm_profile_sha256[0],
        execution_profile=source.execution_profile_sha256[0],
    )
    return GPUArchitectureParityEvidence(
        expected_candidate_denominator=expected_denominator,
        reference_run=_run(
            "rust-reference",
            receipt=reference_receipt,
            runner_digest="c",
        ),
        gpu_runs=gpu_runs,
        term_tolerance=ScorerV1TermTolerance.frozen(),
        oom_probe=oom_probe or _probe(FailClosedProbeKind.OOM, receipt=gpu_receipt),
        overflow_probe=overflow_probe
        or _probe(FailClosedProbeKind.PAIR_LIST_OVERFLOW, receipt=gpu_receipt),
        hip_safe_qualification_receipt_sha256=(
            gpu_receipt.hip_safe_qualification_receipt_sha256
            if safe_receipt is None
            else safe_receipt
        ),
    )


def _gates(evidence: GPUArchitectureParityEvidence) -> dict[str, bool]:
    return dict(verify_gpu_architecture_qualification(evidence).gate_results)


def test_all_machine_parity_gates_can_pass_without_enabling_hip_or_claims() -> None:
    receipt = verify_gpu_architecture_qualification(_evidence())

    assert receipt.parity_qualified is False
    assert all(dict(receipt.gate_results).values())
    assert receipt.to_dict()["parity_gates_passed"] is True
    assert receipt.backend_execution_available is False
    assert receipt.acceleration_claim_allowed is False

    claim = verify_gpu_claim_qualification(
        backend=EngineV2Backend.HIP_SAFE,
        required_architectures=("gfx1030",),
        architecture_receipts=(receipt,),
    )
    assert claim.all_architectures_parity_qualified is False
    assert claim.backend_execution_available is False
    assert claim.acceleration_claim_allowed is False


def test_term_tolerance_cannot_be_widened_after_results() -> None:
    with pytest.raises(GPUParityError, match="frozen pre-result authority"):
        ScorerV1TermTolerance.uniform(1.0e12)


def test_denominator_failure_code_terms_validity_and_v7_gates_fail_closed() -> None:
    assert _gates(_evidence(expected_denominator=7))[GATE_DENOMINATOR] is False
    receipt = backend_receipt(EngineV2Backend.HIP_SAFE)

    failed_candidates = _candidates(failure_override={"candidate-4": "hip_failure"})
    failed_runs = tuple(
        _run(
            f"failed-{index}",
            receipt=receipt,
            candidates=failed_candidates,
            ranked=("candidate-0", "candidate-1", "candidate-2", "candidate-3"),
            runner_digest=str(index + 1),
        )
        for index in range(2)
    )
    assert _gates(_evidence(gpu_runs=failed_runs))[GATE_FAILURE_CODES] is False

    terms_runs = tuple(
        _run(
            f"terms-{index}",
            receipt=receipt,
            candidates=_candidates(term_delta={"candidate-2": 1.0e-5}),
            runner_digest=str(index + 1),
        )
        for index in range(2)
    )
    assert _gates(_evidence(gpu_runs=terms_runs))[GATE_SCORER_TERMS] is False

    validity_runs = tuple(
        _run(
            f"validity-{index}",
            receipt=receipt,
            candidates=_candidates(validity_override={"candidate-2": False}),
            runner_digest=str(index + 1),
        )
        for index in range(2)
    )
    assert _gates(_evidence(gpu_runs=validity_runs))[GATE_VALIDITY] is False

    detailed_validity = list(_candidates())
    detailed_validity[1] = replace(
        detailed_validity[1],
        validity_flags={
            "chemical_valid": False,
            "geometric_valid": True,
            "posebusters_valid": False,
            "selection_eligible": True,
        },
        validity_reason_codes=("chemical_invalid",),
    )
    detailed_runs = tuple(
        _run(
            f"validity-detail-{index}",
            receipt=receipt,
            candidates=tuple(detailed_validity),
            runner_digest=str(index + 3),
        )
        for index in range(2)
    )
    assert _gates(_evidence(gpu_runs=detailed_runs))[GATE_VALIDITY] is False

    v7_runs = tuple(
        _run(
            f"v7-{index}",
            receipt=receipt,
            candidates=_candidates(decision_override={"candidate-2": "rejected"}),
            runner_digest=str(index + 1),
        )
        for index in range(2)
    )
    assert _gates(_evidence(gpu_runs=v7_runs))[GATE_V7_DECISION] is False


def test_top1_top5_and_repeated_run_rank_stability_are_independent_gates() -> None:
    receipt = backend_receipt(EngineV2Backend.HIP_SAFE)
    top1_rank = (
        "candidate-1",
        "candidate-0",
        "candidate-2",
        "candidate-3",
        "candidate-4",
    )
    top1_runs = tuple(
        _run(
            f"top1-{index}",
            receipt=receipt,
            ranked=top1_rank,
            runner_digest=str(index + 1),
        )
        for index in range(2)
    )
    top1_gates = _gates(_evidence(gpu_runs=top1_runs))
    assert top1_gates[GATE_TOP1] is False
    assert top1_gates[GATE_REPEATED_RANK] is True

    top5_rank = (
        "candidate-0",
        "candidate-1",
        "candidate-2",
        "candidate-4",
        "candidate-3",
    )
    top5_runs = tuple(
        _run(
            f"top5-{index}",
            receipt=receipt,
            ranked=top5_rank,
            runner_digest=str(index + 1),
        )
        for index in range(2)
    )
    top5_gates = _gates(_evidence(gpu_runs=top5_runs))
    assert top5_gates[GATE_TOP1] is True
    assert top5_gates[GATE_TOP5] is False

    unstable_runs = (
        _run("unstable-1", receipt=receipt, runner_digest="1"),
        _run(
            "unstable-2",
            receipt=receipt,
            ranked=top5_rank,
            runner_digest="2",
        ),
    )
    assert _gates(_evidence(gpu_runs=unstable_runs))[GATE_REPEATED_RANK] is False

    replayed_execution_runs = (
        _run("replay-label-1", receipt=receipt, runner_digest="d"),
        _run("replay-label-2", receipt=receipt, runner_digest="d"),
    )
    with pytest.raises(GPUParityError, match="distinct executions"):
        _evidence(gpu_runs=replayed_execution_runs)


def test_oom_overflow_and_safe_precedent_fail_closed() -> None:
    receipt = backend_receipt(EngineV2Backend.HIP_SAFE)
    assert (
        _gates(
            _evidence(
                oom_probe=_probe(
                    FailClosedProbeKind.OOM,
                    receipt=receipt,
                    passing=False,
                )
            )
        )[GATE_OOM_FAIL_CLOSED]
        is False
    )
    assert (
        _gates(
            _evidence(
                overflow_probe=_probe(
                    FailClosedProbeKind.PAIR_LIST_OVERFLOW,
                    receipt=receipt,
                    passing=False,
                )
            )
        )[GATE_OVERFLOW_FAIL_CLOSED]
        is False
    )

    fast_receipt = backend_receipt(EngineV2Backend.HIP_FAST)
    hip_fast_runs = (
        _run("hip-fast-1", receipt=fast_receipt, runner_digest="1"),
        _run("hip-fast-2", receipt=fast_receipt, runner_digest="2"),
    )
    with pytest.raises(GPUParityError, match="backend receipt safe precedent"):
        _evidence(gpu_runs=hip_fast_runs, safe_receipt="e" * 64)
    assert _gates(_evidence(gpu_runs=hip_fast_runs))[GATE_HIP_SAFE_PRECEDENT] is False


def test_fail_closed_probes_require_distinct_execution_receipts() -> None:
    receipt = backend_receipt(EngineV2Backend.HIP_SAFE)
    replayed = _probe(FailClosedProbeKind.OOM, receipt=receipt)
    overflow = replace(
        _probe(FailClosedProbeKind.PAIR_LIST_OVERFLOW, receipt=receipt),
        probe_execution=replayed.probe_execution,
    )

    with pytest.raises(GPUParityError, match="distinct executions"):
        _evidence(oom_probe=replayed, overflow_probe=overflow)


def test_typed_runs_reject_cross_source_profile_input_backend_and_probe_drift() -> None:
    gpu_receipt = backend_receipt(EngineV2Backend.HIP_SAFE)
    gpu_runs = (
        _run("gpu-1", receipt=gpu_receipt, runner_digest="1"),
        _run("gpu-2", receipt=gpu_receipt, runner_digest="2"),
    )
    reference = backend_receipt(EngineV2Backend.RUST_CPU)
    common = {
        "expected_candidate_denominator": 6,
        "gpu_runs": gpu_runs,
        "term_tolerance": ScorerV1TermTolerance.frozen(),
        "oom_probe": _probe(FailClosedProbeKind.OOM, receipt=gpu_receipt),
        "overflow_probe": _probe(
            FailClosedProbeKind.PAIR_LIST_OVERFLOW, receipt=gpu_receipt
        ),
    }

    wrong_source = backend_receipt(EngineV2Backend.RUST_CPU, exact_source="d")
    with pytest.raises(GPUParityError, match="exact source and profiles"):
        GPUArchitectureParityEvidence(
            reference_run=_run("reference", receipt=wrong_source), **common
        )
    wrong_profile = backend_receipt(EngineV2Backend.RUST_CPU, algorithm_profile="d")
    with pytest.raises(GPUParityError, match="exact source and profiles"):
        GPUArchitectureParityEvidence(
            reference_run=_run("reference", receipt=wrong_profile), **common
        )
    with pytest.raises(GPUParityError, match="one input candidate set"):
        GPUArchitectureParityEvidence(
            reference_run=_run("reference", receipt=reference, input_digest="d"),
            **common,
        )

    other_arch = backend_receipt(EngineV2Backend.HIP_SAFE, architecture="gfx1100")
    mixed_arch_runs = (
        gpu_runs[0],
        _run("gpu-other-arch", receipt=other_arch, runner_digest="2"),
    )
    with pytest.raises(GPUParityError, match="one exact architecture"):
        GPUArchitectureParityEvidence(
            reference_run=_run("reference", receipt=reference),
            **{**common, "gpu_runs": mixed_arch_runs},
        )

    wrong_probe_receipt = backend_receipt(
        EngineV2Backend.HIP_SAFE, architecture="gfx1100"
    )
    with pytest.raises(GPUParityError, match="exact GPU backend/source/profile"):
        GPUArchitectureParityEvidence(
            reference_run=_run("reference", receipt=reference),
            **{
                **common,
                "oom_probe": _probe(
                    FailClosedProbeKind.OOM, receipt=wrong_probe_receipt
                ),
            },
        )


def test_probe_receipt_forbids_customer_production_or_result_authority() -> None:
    receipt = backend_receipt(EngineV2Backend.HIP_SAFE)
    for field_name in (
        "customer_execution_allowed",
        "production_execution_allowed",
        "result_substitution_allowed",
    ):
        with pytest.raises(GPUParityError, match="cannot authorize"):
            replace(_execution(receipt), **{field_name: True})

    payload = _execution(receipt).to_dict()
    assert payload["backend_receipt"]["native_abi"]["device"]["architecture"] == (
        "gfx1030"
    )
    assert payload["purpose"] == "qualification_probe_only"


def test_per_architecture_claim_coverage_rejects_missing_or_duplicate_receipts() -> (
    None
):
    gfx1030 = verify_gpu_architecture_qualification(_evidence())
    missing = verify_gpu_claim_qualification(
        backend=EngineV2Backend.HIP_SAFE,
        required_architectures=("gfx1030", "gfx1100"),
        architecture_receipts=(gfx1030,),
    )
    assert missing.all_architectures_parity_qualified is False
    assert "gpu_architecture_qualification_missing:gfx1100" in missing.blockers
    assert missing.acceleration_claim_allowed is False

    duplicate = verify_gpu_claim_qualification(
        backend=EngineV2Backend.HIP_SAFE,
        required_architectures=("gfx1030",),
        architecture_receipts=(gfx1030, gfx1030),
    )
    assert duplicate.all_architectures_parity_qualified is False
    assert "duplicate_gpu_architecture_qualification" in duplicate.blockers


def test_evidence_schema_requires_exact_eight_term_receipts() -> None:
    incomplete = _terms(0)
    incomplete.pop("weak_pocket_prior")
    with pytest.raises(GPUParityError, match="exactly eight"):
        ParityCandidateEvidence(
            candidate_id="candidate-0",
            failure_code="",
            scorer_terms=incomplete,
            pose_valid=True,
            v7_decision="selected",
            validity_flags={
                "chemical_valid": True,
                "geometric_valid": True,
                "posebusters_valid": True,
                "selection_eligible": True,
            },
            validity_reason_codes=(),
        )
