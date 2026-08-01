from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat

import pytest

from betelgeuze_engine_v2.benchmark.blind_stage0 import (
    STAGE0_DEVELOPMENT_ANALYSIS_SCHEMA_ID,
    STAGE0_DEVELOPMENT_GATE_DENOMINATORS,
    STAGE0_DEVELOPMENT_GATE_OPERATORS,
    STAGE0_DIAGNOSTIC_CONTRACT_ID,
)
from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    FROZEN_PUBLIC_REDOCKING_CASE_IDS,
    PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS,
    PUBLIC_REDOCKING_RUNNER_ID,
    PublicRedockingCaseResult,
    PublicRedockingEngineV2CandidateDiagnostic,
    PublicRedockingEngineV2Diagnostics,
)
import tools.build_engine_v2_stage0_development_gate_ledger as ledger_builder


_CASE_IDS = FROZEN_PUBLIC_REDOCKING_CASE_IDS[2:10]
_TERM_NAMES = (
    "typed_vdw",
    "electrostatics",
    "directional_hbond",
    "hydrophobic_contact",
    "desolvation_proxy",
    "torsion_energy",
    "ligand_strain",
    "weak_pocket_prior",
    "total_score",
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(*parts: object) -> str:
    return hashlib.sha256(":".join(map(str, parts)).encode("ascii")).hexdigest()


def _backend_receipt() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_id": "betelgeuze.engine_v2_scorer_v1_backend_receipt/1.0.0",
        "backend": "python_reference",
        "backend_version": "1.0.0",
        "implementation_source_sha256": "e" * 64,
        "options_fingerprint_sha256": "f" * 64,
        "extension_sha256": "",
        "cargo_lock_sha256": "",
        "rustc_version": "",
        "target_triple": "",
        "build_flags": [],
        "implicit_fallback_allowed": False,
    }
    payload["receipt_sha256"] = _sha256(payload)
    return payload


def _score_terms(score: float) -> dict[str, str]:
    terms = {name: (0.0).hex() for name in _TERM_NAMES}
    terms["typed_vdw"] = score.hex()
    terms["total_score"] = score.hex()
    return terms


def _candidate(
    case_id: str,
    index: int,
    *,
    rmsd: float,
    valid: bool,
    refined: bool = False,
) -> PublicRedockingEngineV2CandidateDiagnostic:
    score = float(index)
    refinement: dict[str, object] = {}
    if refined:
        refinement = {
            "refinement_receipt_sha256": _digest(case_id, index, "refinement"),
            "refinement_initial_penalty_binary64_hex": (4.0).hex(),
            "refinement_final_penalty_binary64_hex": (3.0).hex(),
            "refinement_accepted_steps": 1,
            "refinement_accepted_rotation_steps": 0,
            "refinement_original_pose_valid": valid,
            "refinement_total_translation_binary64_hex": ((0.0).hex(),) * 3,
            "refinement_total_rotation_vector_binary64_hex": ((0.0).hex(),) * 3,
        }
    failed_checks = (
        ()
        if valid
        else (PUBLIC_REDOCKING_POSEBUSTERS_GEOMETRIC_CHECK_IDS[1],)
    )
    return PublicRedockingEngineV2CandidateDiagnostic(
        proposal_index=index,
        status="success",
        proposal_mode="uniform_fallback",
        proposal_fingerprint_sha256=_digest(case_id, index, "proposal"),
        coordinate_fingerprint_sha256=_digest(case_id, index, "coordinate"),
        score=score,
        rmsd_angstrom=rmsd,
        geometric_valid=valid,
        chemical_valid=True,
        pose_artifact_sha256=_digest(case_id, index, "pose"),
        score_terms_receipt_sha256=_digest(case_id, index, "terms"),
        hbond_count=0,
        selection_eligible=True,
        posebusters_failed_check_ids=failed_checks,
        score_term_binary64_hex=_score_terms(score),
        **refinement,
    )


def _result(case_id: str, behavior: str) -> PublicRedockingCaseResult:
    policy = ('scorer_backend="python_reference"', "scorer_thread_count=1")
    artifacts = {
        role: _digest(case_id, role)
        for role in ("receptor", "reference", "native", "seed")
    }
    if behavior == "preparation_failure":
        diagnostics = PublicRedockingEngineV2Diagnostics(
            preparation_status="failure",
            preparation_failure_code="input_parse_unsupported",
            receptor_atom_count=0,
            ligand_atom_count=0,
            receptor_partial_charge_count=0,
            ligand_partial_charge_count=0,
            receptor_donor_count=0,
            receptor_acceptor_count=0,
            ligand_donor_count=0,
            ligand_acceptor_count=0,
        )
        return PublicRedockingCaseResult(
            case_id=case_id,
            engine_id="engine_v2",
            status="failure",
            runtime_seconds=1.0,
            receptor_artifact_sha256=artifacts["receptor"],
            reference_artifact_sha256=artifacts["reference"],
            native_artifact_sha256=artifacts["native"],
            seed_artifact_sha256=artifacts["seed"],
            execution_command=("fixture", case_id),
            execution_policy=policy,
            failure_code="engine_v2_input_unsupported",
            engine_v2_diagnostics=diagnostics,
        )
    candidates: list[PublicRedockingEngineV2CandidateDiagnostic] = []
    for index in range(64):
        if (behavior == "candidate_incomplete" and index >= 59) or (
            behavior in {"pose_count_incomplete", "pose_count_incomplete_oracle"}
            and index >= 4
        ):
            candidates.append(
                PublicRedockingEngineV2CandidateDiagnostic(
                    proposal_index=index,
                    status="failure",
                    error_code="fixture_candidate_failure",
                )
            )
            continue
        rmsd = 3.0
        if behavior == "oracle_top5_miss" and index == 6:
            rmsd = 1.0
        elif behavior == "top5_top1_miss" and index == 1:
            rmsd = 1.0
        elif behavior in {"top1_invalid", "top1_valid"} and index == 0:
            rmsd = 1.0
        elif behavior == "pose_count_incomplete_oracle" and index == 1:
            rmsd = 1.0
        valid = behavior != "no_oracle_no_valid" and not (
            behavior == "top1_invalid" and index == 0
        )
        candidates.append(
            _candidate(
                case_id,
                index,
                rmsd=rmsd,
                valid=valid,
                refined=behavior == "top1_valid" and index == 10,
            )
        )
    diagnostics = PublicRedockingEngineV2Diagnostics(
        preparation_status="success",
        scorer_backend_receipt=_backend_receipt(),
        receptor_atom_count=1,
        ligand_atom_count=1,
        receptor_partial_charge_count=1,
        ligand_partial_charge_count=1,
        receptor_donor_count=1,
        receptor_acceptor_count=1,
        ligand_donor_count=1,
        ligand_acceptor_count=1,
        candidates=tuple(candidates),
    )
    ranked = diagnostics.score_ranked_candidates[:5]
    if behavior in {"pose_count_incomplete", "pose_count_incomplete_oracle"}:
        return PublicRedockingCaseResult(
            case_id=case_id,
            engine_id="engine_v2",
            status="failure",
            runtime_seconds=1.0,
            receptor_artifact_sha256=artifacts["receptor"],
            reference_artifact_sha256=artifacts["reference"],
            native_artifact_sha256=artifacts["native"],
            seed_artifact_sha256=artifacts["seed"],
            execution_command=("fixture", case_id),
            execution_policy=policy,
            failure_code="engine_v2_pose_count_incomplete",
            engine_v2_diagnostics=diagnostics,
        )
    return PublicRedockingCaseResult(
        case_id=case_id,
        engine_id="engine_v2",
        status="success",
        runtime_seconds=1.0,
        receptor_artifact_sha256=artifacts["receptor"],
        reference_artifact_sha256=artifacts["reference"],
        native_artifact_sha256=artifacts["native"],
        seed_artifact_sha256=artifacts["seed"],
        execution_command=("fixture", case_id),
        execution_policy=policy,
        rmsd_angstroms=tuple(float(candidate.rmsd_angstrom) for candidate in ranked),
        geometric_valid=tuple(bool(candidate.geometric_valid) for candidate in ranked),
        chemical_valid=tuple(bool(candidate.chemical_valid) for candidate in ranked),
        pose_artifact_sha256s=tuple(candidate.pose_artifact_sha256 for candidate in ranked),
        engine_v2_diagnostics=diagnostics,
    )


def _results() -> tuple[PublicRedockingCaseResult, ...]:
    behaviors = (
        "preparation_failure",
        "no_oracle_no_valid",
        "oracle_top5_miss",
        "top5_top1_miss",
        "top1_invalid",
        "top1_valid",
        "top1_valid",
        "top1_valid",
    )
    return tuple(
        _result(case_id, behavior)
        for case_id, behavior in zip(_CASE_IDS, behaviors, strict=True)
    )


def _report(results: tuple[PublicRedockingCaseResult, ...]) -> dict[str, object]:
    scored = tuple(result for result in results if result.status == "success")
    preparation_success = tuple(
        result
        for result in results
        if result.engine_v2_diagnostics is not None
        and result.engine_v2_diagnostics.preparation_status == "success"
    )
    payload: dict[str, object] = {
        "schema_id": STAGE0_DEVELOPMENT_ANALYSIS_SCHEMA_ID,
        "analysis_scope": "historical_contaminated_development_only",
        "claimable": False,
        "contains_fresh_internal_blind_holdout": False,
        "case_count": len(results),
        "scored_case_count": len(scored),
        "preparation_excluded_case_count": len(results) - len(preparation_success),
        "case_ids": sorted(result.case_id for result in results),
        "candidate_count": sum(
            len(result.engine_v2_diagnostics.successful_candidates)
            for result in preparation_success
            if result.engine_v2_diagnostics is not None
        ),
        "sufficient_for_track_decision": True,
    }
    payload["report_sha256"] = _sha256(payload)
    return payload


def _threshold_source_reports(
    case_ids: tuple[str, ...] = _CASE_IDS,
) -> dict[str, str]:
    return {
        f"/historical-fixture/{case_id}/receipts/{engine}/{case_id}.json": _digest(
            "threshold-source",
            engine,
            case_id,
        )
        for case_id in case_ids
        for engine in ledger_builder._THRESHOLD_SOURCE_ENGINES
    }


def _threshold_evidence() -> dict[str, object]:
    thresholds = {
        "preparation_input_unsupported_rate": 0.20,
        "candidate_generation_coverage": 0.90,
        "proposal_oracle_2a_recovery": 0.40,
        "top1_selection_failure_given_oracle": 0.50,
        "top5_selection_failure_given_oracle": 0.20,
        "invalid_top1_pose_rate": 0.20,
        "case_level_failure_rate": 0.20,
    }
    payload: dict[str, object] = {
        "schema_id": ledger_builder.THRESHOLD_SCHEMA_ID,
        "derivation_policy_id": ledger_builder.THRESHOLD_DERIVATION_POLICY_ID,
        "corpus_id": "historical_development_fixture",
        "case_count": 8,
        "case_ids_sha256": _sha256(list(_CASE_IDS)),
        "contains_engineering_smoke": False,
        "contains_primary_holdout": False,
        "contains_fresh_internal_blind_holdout": False,
        "diagnostic_contract_id": STAGE0_DIAGNOSTIC_CONTRACT_ID,
        "sample_size_justification": "fixed eight-case unit fixture",
        "metric_denominator_policy": dict(STAGE0_DEVELOPMENT_GATE_DENOMINATORS),
        "preparation_success_case_count": 8,
        "source_reports_sha256": _threshold_source_reports(),
        "oracle_success_case_count": 4,
        "metrics": {
            metric: {
                "operator": operator,
                "observed_estimate": 0.5,
                "proposed_threshold": thresholds[metric],
                "derivation_rule": f"fixture:{metric}",
            }
            for metric, operator in STAGE0_DEVELOPMENT_GATE_OPERATORS.items()
        },
        "paired_baseline_engines": ["vina", "gnina"],
        "baseline_observed": {
            "failure_rates": {"vina": 0.1, "gnina": 0.1},
            "top1_2a_recovery_rates": {"vina": 0.3, "gnina": 0.4},
            "top5_2a_recovery_rates": {"vina": 0.4, "gnina": 0.5},
        },
        "baseline_noninferiority_margins": {
            "top1_2a_recovery_delta": -0.1,
            "top5_2a_recovery_delta": -0.1,
        },
        "runtime_role": "descriptive_only",
        "scientific_validation_claimed": False,
        "public_claim_eligible": False,
    }
    payload["evidence_sha256"] = _sha256(payload)
    return payload


@pytest.fixture(autouse=True)
def _frozen_threshold_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    threshold = _threshold_evidence()
    monkeypatch.setattr(
        ledger_builder,
        "STAGE0_FROZEN_THRESHOLD_EVIDENCE_PATH",
        "config/engine_v2_public_redocking_stage0_threshold_evidence.json",
    )
    monkeypatch.setattr(
        ledger_builder,
        "STAGE0_FROZEN_THRESHOLD_EVIDENCE_FILE_SHA256",
        "e" * 64,
    )
    monkeypatch.setattr(
        ledger_builder,
        "STAGE0_FROZEN_THRESHOLD_EVIDENCE_SHA256",
        threshold["evidence_sha256"],
    )


def _binding(case_count: int) -> dict[str, object]:
    return {
        "development_engine_implementation_sha256": "b" * 64,
        "development_runner_id": PUBLIC_REDOCKING_RUNNER_ID,
        "development_source_receipt_count": case_count,
        "development_source_receipts_sha256": "c" * 64,
    }


def _build(
    results: tuple[PublicRedockingCaseResult, ...] | None = None,
    threshold: dict[str, object] | None = None,
) -> dict[str, object]:
    selected_results = _results() if results is None else results
    report = _report(selected_results)
    return ledger_builder.build_development_gate_ledger(
        development_report=report,
        threshold_evidence=_threshold_evidence() if threshold is None else threshold,
        authenticated_results=selected_results,
        source_receipt_binding=_binding(len(selected_results)),
        development_report_path=".betelgeuze/development-report.json",
        development_report_file_sha256="d" * 64,
        threshold_evidence_path=(
            "config/engine_v2_public_redocking_stage0_threshold_evidence.json"
        ),
        threshold_evidence_file_sha256="e" * 64,
    )


def test_gate_ledger_records_exact_denominators_and_observed_blockers() -> None:
    payload = _build()

    assert payload["summary"]["case_count"] == 8
    assert payload["summary"]["preparation_success_case_count"] == 7
    assert payload["summary"]["oracle_2a_recovery_case_count"] == 6
    assert payload["summary"]["candidate_success_count"] == 448
    assert payload["summary"]["any_valid_candidate_case_count"] == 6
    gates = payload["development_gates"]
    assert (gates["preparation_input_unsupported_rate"]["numerator"], gates["preparation_input_unsupported_rate"]["denominator"]) == (1, 8)
    assert (gates["candidate_generation_coverage"]["numerator"], gates["candidate_generation_coverage"]["denominator"]) == (448, 448)
    assert (gates["proposal_oracle_2a_recovery"]["numerator"], gates["proposal_oracle_2a_recovery"]["denominator"]) == (6, 7)
    assert (gates["top1_selection_failure_given_oracle"]["numerator"], gates["top1_selection_failure_given_oracle"]["denominator"]) == (2, 6)
    assert (gates["top5_selection_failure_given_oracle"]["numerator"], gates["top5_selection_failure_given_oracle"]["denominator"]) == (1, 6)
    assert (gates["invalid_top1_pose_rate"]["numerator"], gates["invalid_top1_pose_rate"]["denominator"]) == (2, 7)
    assert gates["invalid_top1_pose_rate"]["passed"] is False
    assert payload["all_development_gates_passed"] is False
    blockers = payload["case_ids_by_observed_blocker"]
    assert blockers["preparation_failure"] == [_CASE_IDS[0]]
    assert blockers["no_oracle_candidate"] == [_CASE_IDS[1]]
    assert blockers["oracle_but_top5_miss"] == [_CASE_IDS[2]]
    assert blockers["top5_but_top1_miss"] == [_CASE_IDS[3]]
    assert blockers["top1_invalid"] == [_CASE_IDS[1], _CASE_IDS[4]]
    assert blockers["no_valid_candidate"] == [_CASE_IDS[1]]
    refined = next(row for row in payload["cases"] if row["case_id"] == _CASE_IDS[5])
    assert refined["lineage_summary"]["refinement_lineage_count"] == 1
    assert len(refined["lineage_summary"]["refinement_lineage_sha256"]) == 64
    projection = dict(payload)
    observed = projection.pop("ledger_sha256")
    assert observed == _sha256(projection)


def test_gate_ledger_is_order_stable_and_omits_bulky_candidate_payloads() -> None:
    results = _results()
    forward = _build(results)
    reverse = _build(tuple(reversed(results)))

    assert forward == reverse
    encoded = _canonical_bytes(forward)
    assert b"refinement_receipt_payload" not in encoded
    assert b"score_term_binary64_hex" not in encoded
    assert len(encoded) < 30_000


@pytest.mark.parametrize(
    "mutation",
    (
        lambda payload: payload.__setitem__(
            "contains_fresh_internal_blind_holdout", True
        ),
        lambda payload: payload.__setitem__("unexpected", "field"),
    ),
)
def test_gate_ledger_rejects_resealed_threshold_scope_or_schema_drift(mutation) -> None:
    threshold = deepcopy(_threshold_evidence())
    threshold.pop("evidence_sha256")
    mutation(threshold)
    threshold["evidence_sha256"] = _sha256(threshold)

    with pytest.raises(ValueError, match="threshold"):
        _build(threshold=threshold)


def test_threshold_source_report_identity_reconciles_exact_case_set() -> None:
    threshold = _threshold_evidence()

    assert ledger_builder._threshold_source_case_ids(
        threshold["source_reports_sha256"],
        case_count=threshold["case_count"],
        expected_case_ids_sha256=threshold["case_ids_sha256"],
    ) == tuple(sorted(_CASE_IDS))


@pytest.mark.parametrize(
    "drift",
    ("missing_pair", "duplicate_pair", "count", "digest", "smoke_case"),
)
def test_threshold_source_report_identity_rejects_drift(drift: str) -> None:
    threshold = _threshold_evidence()
    source_reports = dict(threshold["source_reports_sha256"])
    case_count = int(threshold["case_count"])
    case_ids_sha256 = str(threshold["case_ids_sha256"])
    if drift == "missing_pair":
        source_reports.pop(next(iter(source_reports)))
    elif drift == "duplicate_pair":
        case_id = _CASE_IDS[0]
        source_reports[f"/duplicate/receipts/engine_v2/{case_id}.json"] = _digest(
            "duplicate", case_id
        )
    elif drift == "count":
        case_count += 1
    elif drift == "digest":
        case_ids_sha256 = "0" * 64
    else:
        original_case_id = _CASE_IDS[0]
        smoke_case_id = ledger_builder.PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS[0]
        for engine in ledger_builder._THRESHOLD_SOURCE_ENGINES:
            original_path = (
                f"/historical-fixture/{original_case_id}/receipts/"
                f"{engine}/{original_case_id}.json"
            )
            source_reports.pop(original_path)
            source_reports[
                f"/historical-fixture/{smoke_case_id}/receipts/"
                f"{engine}/{smoke_case_id}.json"
            ] = _digest("threshold-source", engine, smoke_case_id)
        case_ids_sha256 = _sha256(sorted({*_CASE_IDS[1:], smoke_case_id}))

    with pytest.raises(ValueError, match="threshold evidence source report"):
        ledger_builder._threshold_source_case_ids(
            source_reports,
            case_count=case_count,
            expected_case_ids_sha256=case_ids_sha256,
        )


def test_gate_ledger_fails_closed_when_oracle_denominator_is_empty() -> None:
    results = tuple(
        _result(case_id, "preparation_failure" if index == 0 else "no_oracle_no_valid")
        for index, case_id in enumerate(_CASE_IDS)
    )

    payload = _build(results)

    for metric in (
        "top1_selection_failure_given_oracle",
        "top5_selection_failure_given_oracle",
    ):
        row = payload["development_gates"][metric]
        assert row["denominator"] == 0
        assert row["observed_estimate"] is None
        assert row["evaluation_status"] == "empty_denominator"
        assert row["passed"] is False


def test_gate_ledger_classifies_incomplete_candidates_and_case_failure() -> None:
    results = list(_results())
    results[-1] = _result(_CASE_IDS[-1], "pose_count_incomplete_oracle")

    payload = _build(tuple(results))

    coverage = payload["development_gates"]["candidate_generation_coverage"]
    case_failure = payload["development_gates"]["case_level_failure_rate"]
    assert (coverage["numerator"], coverage["denominator"]) == (388, 448)
    assert (case_failure["numerator"], case_failure["denominator"]) == (2, 8)
    top5_failure = payload["development_gates"][
        "top5_selection_failure_given_oracle"
    ]
    assert (top5_failure["numerator"], top5_failure["denominator"]) == (2, 6)
    blockers = payload["case_ids_by_observed_blocker"]
    assert blockers["candidate_generation_incomplete"] == [_CASE_IDS[-1]]
    assert blockers["case_execution_failure"] == [_CASE_IDS[-1]]
    case = next(row for row in payload["cases"] if row["case_id"] == _CASE_IDS[-1])
    assert case["oracle_2a_recovery"] is True
    assert case["top5_2a_recovery"] is False


def test_gate_ledger_rejects_resealed_relaxed_threshold_authority() -> None:
    threshold = deepcopy(_threshold_evidence())
    threshold.pop("evidence_sha256")
    for metric, row in threshold["metrics"].items():
        row["proposed_threshold"] = (
            1.0
            if STAGE0_DEVELOPMENT_GATE_OPERATORS[metric] == "max"
            else 0.0
        )
    threshold["evidence_sha256"] = _sha256(threshold)

    with pytest.raises(ValueError, match="frozen authority"):
        _build(threshold=threshold)


def test_gate_ledger_rejects_fresh_case_in_pure_builder() -> None:
    fresh_result = _result(
        ledger_builder.FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS[0],
        "top1_valid",
    )

    with pytest.raises(ValueError, match="cross-wired"):
        _build((fresh_result,))


def test_ledger_output_rejects_symlink_parent(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".betelgeuze").symlink_to(outside, target_is_directory=True)
    relative = ledger_builder._output_relative_path(
        tmp_path,
        Path(".betelgeuze/ledger.json"),
    )

    with pytest.raises((OSError, ValueError)):
        ledger_builder._write_exclusive(tmp_path, relative, b"{}\n")

    assert not (outside / "ledger.json").exists()


def test_ledger_output_normalizes_owned_parent_permissions(tmp_path: Path) -> None:
    mutable_root = tmp_path / ".betelgeuze"
    mutable_root.mkdir(mode=0o775)
    os.chmod(mutable_root, 0o775)
    relative = ledger_builder._output_relative_path(
        tmp_path,
        Path(".betelgeuze/stage0-development/ledger.json"),
    )

    ledger_builder._write_exclusive(tmp_path, relative, b"{}\n")

    output = tmp_path / relative
    assert output.read_bytes() == b"{}\n"
    assert stat.S_IMODE(mutable_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(output.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(output.stat().st_mode) == 0o600


def test_authenticated_builder_requires_canonical_repo_bound_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    results = _results()
    report = _report(results)
    threshold = _threshold_evidence()
    report_path = tmp_path / ".betelgeuze/development-report.json"
    threshold_path = (
        tmp_path
        / "config/engine_v2_public_redocking_stage0_threshold_evidence.json"
    )
    report_path.parent.mkdir(parents=True)
    threshold_path.parent.mkdir(parents=True)
    report_path.write_bytes(_canonical_bytes(report) + b"\n")
    threshold_path.write_bytes(_canonical_bytes(threshold) + b"\n")
    monkeypatch.setattr(
        ledger_builder,
        "STAGE0_FROZEN_THRESHOLD_EVIDENCE_FILE_SHA256",
        hashlib.sha256(threshold_path.read_bytes()).hexdigest(),
    )
    monkeypatch.setattr(
        ledger_builder,
        "stage0_authenticated_development_evidence",
        lambda *_args, **_kwargs: (_binding(len(results)), results),
    )

    payload = ledger_builder.build_authenticated_development_gate_ledger(
        repo_root=tmp_path,
        development_report_path=report_path,
        threshold_evidence_path=threshold_path,
        expected_development_report_sha256=str(report["report_sha256"]),
        expected_threshold_evidence_sha256=str(threshold["evidence_sha256"]),
    )

    assert payload["source_evidence"]["development_report_path"] == (
        ".betelgeuze/development-report.json"
    )
    with pytest.raises(ValueError, match="reviewed SHA-256"):
        ledger_builder.build_authenticated_development_gate_ledger(
            repo_root=tmp_path,
            development_report_path=report_path,
            threshold_evidence_path=threshold_path,
            expected_development_report_sha256=str(report["report_sha256"]),
            expected_threshold_evidence_sha256="0" * 64,
        )
    report_path.write_bytes(json.dumps(report).encode("ascii"))
    with pytest.raises(ValueError, match="canonical JSON"):
        ledger_builder.build_authenticated_development_gate_ledger(
            repo_root=tmp_path,
            development_report_path=report_path,
            threshold_evidence_path=threshold_path,
            expected_development_report_sha256=str(report["report_sha256"]),
            expected_threshold_evidence_sha256=str(threshold["evidence_sha256"]),
        )
