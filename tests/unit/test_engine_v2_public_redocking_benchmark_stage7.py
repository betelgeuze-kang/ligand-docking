from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
import hashlib
import json
from pathlib import Path

import pytest

import betelgeuze_engine_v2.benchmark.public_redocking_benchmark as benchmark_contract
from betelgeuze_engine_v2.benchmark import (
    FROZEN_PUBLIC_REDOCKING_CASE_IDS,
    PUBLIC_REDOCKING_ARCHIVE_SHA256,
    PUBLIC_REDOCKING_CASE_SEED_BASE,
    PUBLIC_REDOCKING_COHORT_COUNT,
    PUBLIC_REDOCKING_CONTAMINATION_REGISTRY_SHA256,
    PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS,
    PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS,
    PUBLIC_REDOCKING_PRIMARY_ENGINES,
    PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
    FrozenPublicRedockingCohort,
    PublicRedockingBenchmarkError,
    PublicRedockingCaseProfile,
    PublicRedockingCaseResult,
    PublicRedockingEngineV2CandidateDiagnostic,
    PublicRedockingEngineV2Diagnostics,
    PublicRedockingEngineIdentity,
    PublicRedockingEvaluationPolicy,
    VerifiedCaseMaterialization,
    VerifiedPublicRedockingCaseExecution,
    build_public_redocking_benchmark_report as _build_public_redocking_benchmark_report,
    frozen_public_redocking_case_seed,
    frozen_public_redocking_cohort,
    frozen_public_redocking_profiles,
    require_public_redocking_contamination_registry,
    verify_public_redocking_source_identifiers,
)
from betelgeuze_engine_v2.docking import (
    GuidedPlacementReceipt,
    SourcePairedTorsionRescueAllocation,
    SourcePairedTorsionRescuePolicy,
    SourcePairedTorsionRescueProposalReceipt,
)


_EXCLUDED_SOURCE_IDS = (
    "7KQU_YOF",
    "7OEO_V9Z",
    "7UJ4_OQ4",
    "7USH_82V",
    "7V14_ORU",
    "7VBU_6I4",
    "7VYJ_CA0",
    "7ZDY_6MJ",
)


_RUN_ROOT = Path("/tmp/betelgeuze-public-redocking-unit-run")


def _engine_v2_execution_policy(**changes: object) -> tuple[str, ...]:
    policy: dict[str, object] = {
        "algorithm_profile_id": (
            benchmark_contract.PUBLIC_REDOCKING_ENGINE_V2_ALGORITHM_PROFILE_ID
        ),
        "candidate_schema_id": (
            benchmark_contract.PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID
        ),
        "cpu_count": 1,
        "interaction_refinement_steps": (
            benchmark_contract.PUBLIC_REDOCKING_ENGINE_V2_REFINEMENT_STEPS
        ),
        "interaction_refiner": (
            benchmark_contract.PUBLIC_REDOCKING_ENGINE_V2_REFINER_POLICY_ID
        ),
        "interaction_refiner_config_sha256": (
            benchmark_contract.PUBLIC_REDOCKING_ENGINE_V2_REFINER_CONFIG_SHA256
        ),
        "runner_id": benchmark_contract.PUBLIC_REDOCKING_RUNNER_ID,
        "scorer_backend": "python_reference",
        "scorer_thread_count": 1,
        "torch_interop_threads": 1,
        "torch_intraop_threads": 1,
        "torch_version": "2.6.0",
    }
    policy.update(changes)
    return tuple(
        f"{key}={json.dumps(value, allow_nan=False, separators=(',', ':'))}"
        for key, value in sorted(policy.items())
    )


def _python_backend_receipt() -> dict[str, object]:
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
    payload["receipt_sha256"] = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    return payload


def _zero_score_terms() -> dict[str, str]:
    return {
        name: (0.0).hex()
        for name in (
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
    }


def _torsion_rescue_proposal_receipt() -> dict[str, object]:
    policy = SourcePairedTorsionRescuePolicy()
    authority_sha256 = "a" * 64
    budget_sha256 = "b" * 64
    all_pairs = ((5, 6), (7, 8), (9, 10), (11, 12), (13, 14))
    rescue_pairs = ((5, 6), (7, 8), (11, 12), (13, 14))
    v3_pairs = ((9, 10),)
    allocation = SourcePairedTorsionRescueAllocation(
        authenticated_input_receipt_sha256=authority_sha256,
        guidance_context_sha256="c" * 64,
        budget_sha256=budget_sha256,
        rescue_policy_sha256=policy.fingerprint_sha256,
        base_guided_policy_sha256=(policy.base_guided_policy.fingerprint_sha256),
        candidate_count=64,
        authority_rotor_count=1,
        v3_target_parent_pairs=v3_pairs,
        rescue_target_parent_pairs=rescue_pairs,
    )
    fingerprints = tuple(
        hashlib.sha256(f"rescue-proposal:{index}".encode("ascii")).hexdigest()
        for index in range(64)
    )
    baseline_modes = ["uniform_fallback"] * 64
    baseline_sources: list[int | None] = [None] * 64
    for target, parent in all_pairs:
        baseline_modes[target] = "uniform_v3_rigid_ensemble"
        baseline_sources[target] = parent
    baseline = GuidedPlacementReceipt(
        authenticated_input_receipt_sha256=authority_sha256,
        guidance_context_sha256="c" * 64,
        guided_policy_sha256=policy.base_guided_policy.fingerprint_sha256,
        budget_sha256=budget_sha256,
        proposal_fingerprint_sha256s=fingerprints,
        proposal_modes=tuple(baseline_modes),
        ligand_anchor_atom_indices=((),) * 64,
        receptor_anchor_atom_indices=((),) * 64,
        requested_anchor_distance_angstroms=(None,) * 64,
        observed_anchor_distance_angstroms=(None,) * 64,
        feature_counts={},
        ensemble_source_proposal_indices=tuple(baseline_sources),
    )
    guided_modes = list(baseline_modes)
    guided_sources = list(baseline_sources)
    rescue_parents: list[int | None] = [None] * 64
    for target, parent in rescue_pairs:
        guided_modes[target] = "uniform_torsion_rescue_variant"
        guided_sources[target] = None
        rescue_parents[target] = parent
    guided = GuidedPlacementReceipt(
        authenticated_input_receipt_sha256=authority_sha256,
        guidance_context_sha256="c" * 64,
        guided_policy_sha256=policy.fingerprint_sha256,
        budget_sha256=budget_sha256,
        proposal_fingerprint_sha256s=fingerprints,
        proposal_modes=tuple(guided_modes),
        ligand_anchor_atom_indices=((),) * 64,
        receptor_anchor_atom_indices=((),) * 64,
        requested_anchor_distance_angstroms=(None,) * 64,
        observed_anchor_distance_angstroms=(None,) * 64,
        feature_counts={},
        ensemble_source_proposal_indices=tuple(guided_sources),
        torsion_rescue_parent_proposal_indices=tuple(rescue_parents),
        source_paired_torsion_rescue_profile=True,
        baseline_guided_receipt_sha256=baseline.receipt_sha256,
        torsion_rescue_allocation_sha256=allocation.allocation_sha256,
    )
    receipt = SourcePairedTorsionRescueProposalReceipt(
        authenticated_input_receipt_sha256=authority_sha256,
        budget_sha256=budget_sha256,
        source_ligand_system_sha256="d" * 64,
        source_ligand_topology_sha256="e" * 64,
        rescue_policy_sha256=policy.fingerprint_sha256,
        allocation=allocation,
        baseline_guided_receipt=baseline,
        guided_receipt=guided,
        candidate_ids=tuple(f"rescue-candidate-{index}" for index in range(64)),
        proposal_fingerprint_sha256s=fingerprints,
        proposal_coordinate_fingerprint_sha256s=tuple(
            hashlib.sha256(f"rescue-coordinate:{index}".encode("ascii")).hexdigest()
            for index in range(64)
        ),
        proposal_torsion_metadata_sha256s=tuple(
            hashlib.sha256(f"rescue-torsion:{index}".encode("ascii")).hexdigest()
            for index in range(64)
        ),
    )
    return receipt.to_dict()


def test_candidate_score_terms_accept_json_key_order_and_recanonicalize() -> None:
    score_terms = dict(reversed(tuple(_zero_score_terms().items())))
    candidate = PublicRedockingEngineV2CandidateDiagnostic(
        proposal_index=0,
        status="success",
        proposal_mode="uniform_fallback",
        proposal_fingerprint_sha256="1" * 64,
        coordinate_fingerprint_sha256="4" * 64,
        score=0.0,
        rmsd_angstrom=0.0,
        geometric_valid=True,
        chemical_valid=True,
        pose_artifact_sha256="2" * 64,
        score_terms_receipt_sha256="3" * 64,
        hbond_count=0,
        selection_eligible=True,
        score_term_binary64_hex=score_terms,
    )

    assert tuple(candidate.score_term_binary64_hex) == tuple(_zero_score_terms())


def test_candidate_uniform_v3_ensemble_requires_exact_source_lineage() -> None:
    candidate = PublicRedockingEngineV2CandidateDiagnostic(
        proposal_index=0,
        status="success",
        proposal_mode="uniform_v3_rigid_ensemble",
        ensemble_source_proposal_index=1,
        proposal_fingerprint_sha256="1" * 64,
        coordinate_fingerprint_sha256="4" * 64,
        score=0.0,
        rmsd_angstrom=0.0,
        geometric_valid=True,
        chemical_valid=True,
        pose_artifact_sha256="2" * 64,
        score_terms_receipt_sha256="3" * 64,
        hbond_count=0,
        selection_eligible=True,
        score_term_binary64_hex=_zero_score_terms(),
    )

    assert candidate.to_dict()["ensemble_source_proposal_index"] == 1
    with pytest.raises(PublicRedockingBenchmarkError, match="source index"):
        replace(candidate, ensemble_source_proposal_index=0)
    with pytest.raises(PublicRedockingBenchmarkError, match="source index"):
        replace(candidate, ensemble_source_proposal_index=None)
    with pytest.raises(PublicRedockingBenchmarkError, match="non-ensemble"):
        replace(candidate, proposal_mode="uniform_fallback")


def test_candidate_torsion_rescue_requires_distinct_schema_and_parent() -> None:
    candidate = PublicRedockingEngineV2CandidateDiagnostic(
        proposal_index=0,
        status="failure",
        proposal_mode="uniform_torsion_rescue_variant",
        torsion_rescue_parent_proposal_index=1,
        error_code="synthetic_candidate_failure",
        schema_id=(
            benchmark_contract.PUBLIC_REDOCKING_ENGINE_V2_TORSION_RESCUE_CANDIDATE_SCHEMA_ID
        ),
    )

    assert candidate.to_dict()["torsion_rescue_parent_proposal_index"] == 1
    with pytest.raises(PublicRedockingBenchmarkError, match="parent index"):
        replace(candidate, torsion_rescue_parent_proposal_index=0)
    with pytest.raises(PublicRedockingBenchmarkError, match="parent index"):
        replace(
            candidate,
            schema_id=benchmark_contract.PUBLIC_REDOCKING_ENGINE_V2_CANDIDATE_SCHEMA_ID,
        )


def _source_identifier_bytes() -> bytes:
    source_ids = sorted((*FROZEN_PUBLIC_REDOCKING_CASE_IDS, *_EXCLUDED_SOURCE_IDS))
    return ("\n".join(source_ids) + "\n").encode("ascii")


def _profiles() -> tuple[PublicRedockingCaseProfile, ...]:
    return frozen_public_redocking_profiles()


@lru_cache(maxsize=None)
def _materialization(case_id: str) -> VerifiedCaseMaterialization:
    profile = next(
        row for row in frozen_public_redocking_profiles() if row.case_id == case_id
    )

    def digest(role: str) -> str:
        return hashlib.sha256(f"{case_id}:{role}".encode("ascii")).hexdigest()

    return VerifiedCaseMaterialization._from_verified_archive(
        case_id=case_id,
        artifact_sha256s={
            "receptor": digest("receptor"),
            "reference": digest("reference"),
            "native": profile.ligand_artifact_sha256,
            "seed": digest("seed"),
        },
        archive_member_names=tuple(
            (f"posebusters_benchmark_set/{case_id}/{case_id}_{filename}")
            for filename in (
                "protein.pdb",
                "ligands.sdf",
                "ligand.sdf",
                "ligand_start_conf.sdf",
            )
        ),
        verification_authority=benchmark_contract._VERIFIED_ARCHIVE_AUTHORITY,
    )


def _materializations() -> tuple[VerifiedCaseMaterialization, ...]:
    return tuple(
        _materialization(case_id) for case_id in FROZEN_PUBLIC_REDOCKING_CASE_IDS
    )


_REAL_MATERIALIZATION_RECEIPTS = dict(
    benchmark_contract._FROZEN_MATERIALIZATION_RECEIPT_SHA256_BY_CASE
)
_REAL_MATERIALIZATION_RECEIPTS_SHA256 = (
    benchmark_contract.PUBLIC_REDOCKING_MATERIALIZATION_RECEIPTS_SHA256
)
_REAL_MATERIALIZATIONS_SHA256 = (
    benchmark_contract.PUBLIC_REDOCKING_MATERIALIZATIONS_SHA256
)


@pytest.fixture(autouse=True)
def _synthetic_materialization_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    materializations = _materializations()
    monkeypatch.setattr(
        benchmark_contract,
        "_FROZEN_MATERIALIZATION_RECEIPT_SHA256_BY_CASE",
        {row.case_id: row.receipt_sha256 for row in materializations},
    )
    monkeypatch.setattr(
        benchmark_contract,
        "PUBLIC_REDOCKING_MATERIALIZATIONS_SHA256",
        benchmark_contract._sha256([row.to_dict() for row in materializations]),
    )


def _verified_executions(
    rows,
    identities,
) -> tuple[VerifiedPublicRedockingCaseExecution, ...]:
    identity_map = {identity.engine_id: identity for identity in identities}
    materialization_map = {
        materialization.case_id: materialization
        for materialization in _materializations()
    }
    return tuple(
        VerifiedPublicRedockingCaseExecution._from_fresh_execution(
            result=row,
            materialization_receipt_sha256=(
                materialization_map[row.case_id].receipt_sha256
            ),
            implementation_sha256=identity_map[row.engine_id].implementation_sha256,
            evaluation_pipeline_sha256=(
                identity_map[row.engine_id].evaluation_pipeline_sha256
            ),
            execution_environment_sha256="8" * 64,
            verification_authority=(benchmark_contract._VERIFIED_EXECUTION_AUTHORITY),
        )
        for row in rows
    )


def _executions(
    rows=None,
    identities=None,
) -> tuple[VerifiedPublicRedockingCaseExecution, ...]:
    active_rows = _rows() if rows is None else rows
    active_identities = _identities() if identities is None else identities
    return _verified_executions(active_rows, active_identities)


def build_public_redocking_benchmark_report(*args, **kwargs):
    kwargs.setdefault("materializations", _materializations())
    positional = list(args)
    positional[2] = _verified_executions(positional[2], positional[1])
    return _build_public_redocking_benchmark_report(*positional, **kwargs)


def _identities() -> tuple[PublicRedockingEngineIdentity, ...]:
    external_binaries = {
        "vina": str(_RUN_ROOT / "private-external-binary" / ("2" * 64)),
        "gnina": str(_RUN_ROOT / "private-external-binary" / ("2" * 64)),
    }
    commands = {
        "engine_v2": (
            benchmark_contract.PUBLIC_REDOCKING_RUNNER_ID,
            "engine_v2",
            "--candidate-count",
            "64",
            "--cpu",
            "1",
            "--torch-version",
            "2.6.0",
        ),
        "vina": (
            external_binaries["vina"],
            "--scoring",
            "vina",
            "--cnn_scoring",
            "none",
            "--cpu",
            "1",
            "--no_gpu",
            "--timeout-seconds",
            "300",
        ),
        "gnina": (
            external_binaries["gnina"],
            "--scoring",
            "vina",
            "--cnn_scoring",
            "rescore",
            "--cnn",
            "crossdock_default2018",
            "--cpu",
            "1",
            "--no_gpu",
            "--timeout-seconds",
            "300",
        ),
    }
    return tuple(
        PublicRedockingEngineIdentity(
            engine_id=engine_id,
            version="unit-1.0",
            implementation_sha256=("1" * 64 if engine_id == "engine_v2" else "2" * 64),
            evaluation_pipeline_sha256="e" * 64,
            command=commands[engine_id],
        )
        for index, engine_id in enumerate(PUBLIC_REDOCKING_PRIMARY_ENGINES)
    )


def _input_fields(
    case_id: str,
    engine_id: str = "engine_v2",
) -> dict[str, object]:
    materialization = _materialization(case_id)

    execution_policy = (
        _engine_v2_execution_policy()
        if engine_id == "engine_v2"
        else ("cpu_count=1", "timeout_seconds=300")
    )
    case_directory = _RUN_ROOT / "inputs" / case_id
    execution_command = (
        (
            benchmark_contract.PUBLIC_REDOCKING_RUNNER_ID,
            "engine_v2",
            "--case-id",
            case_id,
            "--receptor",
            str(case_directory / f"{case_id}_protein.pdb"),
            "--ligand",
            str(case_directory / f"{case_id}_ligand_start_conf.sdf"),
            "--pocket-source",
            str(case_directory / f"{case_id}_ligand.sdf"),
            "--candidate-count",
            "64",
            "--cpu",
            "1",
            "--seed",
            str(materialization.frozen_case_seed),
            "--out",
            str(_RUN_ROOT / "poses" / "engine_v2" / f"{case_id}.sdf"),
        )
        if engine_id == "engine_v2"
        else (
            str(_RUN_ROOT / "private-external-binary" / ("2" * 64)),
            "--receptor",
            str(case_directory / f"{case_id}_protein.pdb"),
            "--ligand",
            str(case_directory / f"{case_id}_ligand_start_conf.sdf"),
            "--autobox_ligand",
            str(case_directory / f"{case_id}_ligand.sdf"),
            "--autobox_add",
            "4",
            "--num_modes",
            "5",
            "--exhaustiveness",
            "1",
            "--cpu",
            "1",
            "--no_gpu",
            "--seed",
            str(materialization.frozen_case_seed),
            "--out",
            str(_RUN_ROOT / "poses" / engine_id / f"{case_id}.sdf"),
            "--scoring",
            "vina",
            "--cnn_scoring",
            "none" if engine_id == "vina" else "rescore",
            *(() if engine_id == "vina" else ("--cnn", "crossdock_default2018")),
        )
    )
    return {
        "receptor_artifact_sha256": (materialization.receptor_artifact_sha256),
        "reference_artifact_sha256": (materialization.reference_artifact_sha256),
        "native_artifact_sha256": materialization.native_artifact_sha256,
        "seed_artifact_sha256": materialization.seed_artifact_sha256,
        "execution_command": execution_command,
        "execution_policy": execution_policy,
    }


def _success(
    case_id: str,
    engine_id: str,
    *,
    top1: float,
    top2: float,
    top3: float,
    runtime: float,
) -> PublicRedockingCaseResult:
    rmsds = (top1, top2, top3, 4.0, 5.0)
    geometric = (True, True, True, False, False)
    chemical = (True, True, True, False, False)
    artifacts = tuple(str(index + 4) * 64 for index in range(5))
    diagnostics = None
    if engine_id == "engine_v2":
        diagnostics = PublicRedockingEngineV2Diagnostics(
            preparation_status="success",
            scorer_backend_receipt=_python_backend_receipt(),
            receptor_atom_count=2,
            ligand_atom_count=1,
            receptor_partial_charge_count=2,
            ligand_partial_charge_count=1,
            receptor_donor_count=1,
            receptor_acceptor_count=1,
            ligand_donor_count=1,
            ligand_acceptor_count=1,
            candidates=tuple(
                (
                    PublicRedockingEngineV2CandidateDiagnostic(
                        proposal_index=index,
                        status="success",
                        proposal_mode="uniform_fallback",
                        proposal_fingerprint_sha256=hashlib.sha256(
                            f"{case_id}:proposal:{index}".encode("ascii")
                        ).hexdigest(),
                        coordinate_fingerprint_sha256=hashlib.sha256(
                            f"{case_id}:coordinates:{index}".encode("ascii")
                        ).hexdigest(),
                        score=float(index),
                        rmsd_angstrom=rmsds[index],
                        geometric_valid=geometric[index],
                        chemical_valid=chemical[index],
                        pose_artifact_sha256=artifacts[index],
                        score_terms_receipt_sha256=hashlib.sha256(
                            f"{case_id}:terms:{index}".encode("ascii")
                        ).hexdigest(),
                        hbond_count=int(index == 0),
                        selection_eligible=True,
                        posebusters_failed_check_ids=(
                            ()
                            if geometric[index] and chemical[index]
                            else (
                                "internal_steric_clash",
                                "minimum_distance_to_protein",
                            )
                        ),
                        score_term_binary64_hex=_zero_score_terms(),
                    )
                    if index < 5
                    else PublicRedockingEngineV2CandidateDiagnostic(
                        proposal_index=index,
                        status="failure",
                        error_code="synthetic_candidate_failure",
                    )
                )
                for index in range(64)
            ),
        )
    return PublicRedockingCaseResult(
        case_id=case_id,
        engine_id=engine_id,
        status="success",
        runtime_seconds=runtime,
        **_input_fields(case_id, engine_id),
        rmsd_angstroms=rmsds,
        geometric_valid=geometric,
        chemical_valid=chemical,
        pose_artifact_sha256s=artifacts,
        engine_v2_diagnostics=diagnostics,
    )


def _rows() -> tuple[PublicRedockingCaseResult, ...]:
    rows = []
    for engine_id in PUBLIC_REDOCKING_PRIMARY_ENGINES:
        for index, case_id in enumerate(FROZEN_PUBLIC_REDOCKING_CASE_IDS):
            if index % 10 == 0:
                rows.append(
                    PublicRedockingCaseResult(
                        case_id=case_id,
                        engine_id=engine_id,
                        status="failure",
                        runtime_seconds=1.0 + index / 100.0,
                        **_input_fields(case_id, engine_id),
                        failure_code=(
                            "engine_v2_case_failed"
                            if engine_id == "engine_v2"
                            else "external_process_failed"
                        ),
                        engine_v2_diagnostics=(
                            PublicRedockingEngineV2Diagnostics(
                                preparation_status="failure",
                                preparation_failure_code=(
                                    "unclassified_engine_v2_case_failure"
                                ),
                                receptor_atom_count=0,
                                ligand_atom_count=0,
                                receptor_partial_charge_count=0,
                                ligand_partial_charge_count=0,
                                receptor_donor_count=0,
                                receptor_acceptor_count=0,
                                ligand_donor_count=0,
                                ligand_acceptor_count=0,
                            )
                            if engine_id == "engine_v2"
                            else None
                        ),
                    )
                )
                continue
            if engine_id == "engine_v2":
                rows.append(
                    _success(
                        case_id,
                        engine_id,
                        top1=1.0 if index % 2 else 3.0,
                        top2=1.5,
                        top3=1.8,
                        runtime=2.0 + index / 100.0,
                    )
                )
            elif engine_id == "vina":
                rows.append(
                    _success(
                        case_id,
                        engine_id,
                        top1=1.0 if index % 3 else 3.0,
                        top2=2.5,
                        top3=1.8,
                        runtime=3.0 + index / 100.0,
                    )
                )
            else:
                rows.append(
                    _success(
                        case_id,
                        engine_id,
                        top1=1.0 if index % 4 else 3.0,
                        top2=2.5,
                        top3=1.8,
                        runtime=4.0 + index / 100.0,
                    )
                )
    return tuple(rows)


def _policy() -> PublicRedockingEvaluationPolicy:
    return PublicRedockingEvaluationPolicy(
        bootstrap_samples=100,
        bootstrap_seed=17,
    )


def _metric(
    report,
    engine_id,
    metric_id,
    subgroup="all",
    baseline="",
    analysis_scope="supplementary_descriptive",
):
    return next(
        metric
        for metric in report.metrics
        if metric.engine_id == engine_id
        and metric.metric_id == metric_id
        and metric.analysis_scope == analysis_scope
        and metric.subgroup == subgroup
        and metric.paired_baseline_engine_id == baseline
    )


def test_frozen_cohort_binds_exact_300_cases_and_public_source() -> None:
    cohort = frozen_public_redocking_cohort()

    assert len(cohort.case_ids) == PUBLIC_REDOCKING_COHORT_COUNT == 300
    assert cohort.case_ids == tuple(sorted(cohort.case_ids))
    assert len(set(cohort.case_ids)) == 300
    assert len(cohort.fingerprint_sha256) == 64
    document = cohort.to_dict()
    assert document["source"]["archive_sha256"] == PUBLIC_REDOCKING_ARCHIVE_SHA256
    assert document["source"]["source_ids_sha256"] == (
        PUBLIC_REDOCKING_SOURCE_IDS_SHA256
    )
    assert document["selection"]["selected_before_results"] is True
    assert document["case_seed_policy"]["base_seed"] == (
        PUBLIC_REDOCKING_CASE_SEED_BASE
    )
    assert document["analysis_partitions"]["engineering_smoke"]["case_ids"] == list(
        PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS
    )
    assert document["analysis_partitions"]["primary_blind_holdout"]["case_count"] == 298
    assert (
        document["analysis_partitions"]["contaminated_development"]["case_count"] == 300
    )
    assert document["raw_structure_data_bundled"] is False
    assert document["benchmark_executed"] is False
    assert document["claim_safe"] is False


def test_contamination_registry_invalidates_old_298_claim_before_values() -> None:
    path = Path("config/engine_v2_public_redocking_contamination_registry.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    registry = require_public_redocking_contamination_registry(payload)

    assert registry["registry_sha256"] == (
        PUBLIC_REDOCKING_CONTAMINATION_REGISTRY_SHA256
    )
    assert registry["contaminated_development_case_count"] == 300
    assert registry["fresh_internal_blind_candidate_count"] == 128
    assert registry["result_values_inspected_before_reclassification"] is False
    assert registry["old_298_holdout_claim_invalidated"] is True


def test_published_308_identifier_document_reproduces_selection() -> None:
    source = _source_identifier_bytes()
    assert len(source) == 2_772
    assert verify_public_redocking_source_identifiers(source) == (
        FROZEN_PUBLIC_REDOCKING_CASE_IDS
    )

    tampered = bytearray(source)
    tampered[0] = ord("9")
    with pytest.raises(PublicRedockingBenchmarkError, match="hash mismatch"):
        verify_public_redocking_source_identifiers(bytes(tampered))


def test_frozen_cohort_rejects_case_drift() -> None:
    case_ids = list(FROZEN_PUBLIC_REDOCKING_CASE_IDS)
    case_ids[0] = "5SAA_ZZZ"
    with pytest.raises(PublicRedockingBenchmarkError, match="drifted"):
        FrozenPublicRedockingCohort(case_ids=tuple(case_ids))


def test_frozen_profiles_bind_ligand_artifacts_and_cover_all_subgroups() -> None:
    profiles = frozen_public_redocking_profiles()
    assert len(profiles) == 300
    assert {profile.size_subgroup for profile in profiles} == {
        "size_small_1_20",
        "size_medium_21_40",
        "size_large_41_plus",
    }
    assert {profile.rotor_subgroup for profile in profiles} == {
        "rotor_rigid_0",
        "rotor_low_1_4",
        "rotor_flexible_5_plus",
    }
    assert {profile.ring_subgroup for profile in profiles} == {
        "ring_acyclic_0",
        "ring_single_1",
        "ring_multi_2_plus",
    }
    assert all(len(profile.ligand_artifact_sha256) == 64 for profile in profiles)


def test_verified_materializations_bind_four_archive_inputs_and_frozen_seed() -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    materialization = _materialization(case_id)
    payload = materialization.to_dict()

    assert materialization.frozen_case_seed == (
        frozen_public_redocking_case_seed(case_id)
    )
    assert materialization.frozen_case_seed == PUBLIC_REDOCKING_CASE_SEED_BASE
    assert tuple(payload["artifact_sha256s"]) == (
        "protein.pdb",
        "ligands.sdf",
        "ligand.sdf",
        "ligand_start_conf.sdf",
    )
    assert payload["source_archive_sha256"] == PUBLIC_REDOCKING_ARCHIVE_SHA256
    assert payload["hash_verified_archive"] is True
    assert len(materialization.receipt_sha256) == 64


def test_real_archive_materialization_receipt_manifest_is_complete() -> None:
    assert tuple(_REAL_MATERIALIZATION_RECEIPTS) == FROZEN_PUBLIC_REDOCKING_CASE_IDS
    assert (
        benchmark_contract._sha256(list(_REAL_MATERIALIZATION_RECEIPTS.values()))
        == _REAL_MATERIALIZATION_RECEIPTS_SHA256
    )
    assert _REAL_MATERIALIZATIONS_SHA256 == (
        "94bb879b181ec3de581f3f098aff2bd50b9f988fd1d4eb0c3c46cc673cfd640a"
    )
    assert _REAL_MATERIALIZATION_RECEIPTS["5SAK_ZRY"] == (
        "179800efd20944bc9ab41a479a9f9b586698419455971438cdc42006c572f99d"
    )
    assert _REAL_MATERIALIZATION_RECEIPTS["8SLG_G5A"] == (
        "ad96c797101a65e45e4274dbca6462cb41d0f902a810225a5a187abd173e6722"
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"ranked_pose_count": 3}, "ranked_pose_count"),
        ({"top_ks": (1, 5)}, "top_ks"),
        ({"rmsd_threshold_angstrom": 2.1}, "threshold"),
        ({"bootstrap_samples": 99}, "bootstrap_samples"),
        ({"external_timeout_seconds": 0}, "external_timeout_seconds"),
        ({"cpu_count": 2}, "cpu_count"),
    ),
)
def test_equal_budget_policy_fails_closed(changes, message) -> None:
    with pytest.raises(PublicRedockingBenchmarkError, match=message):
        PublicRedockingEvaluationPolicy(**changes)


def test_result_rows_require_five_ranked_poses_or_failure_only() -> None:
    case_id = FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    with pytest.raises(PublicRedockingBenchmarkError, match="five"):
        PublicRedockingCaseResult(
            case_id=case_id,
            engine_id="engine_v2",
            status="success",
            runtime_seconds=1.0,
            **_input_fields(case_id),
            rmsd_angstroms=(1.0,),
            geometric_valid=(True,),
            chemical_valid=(True,),
            pose_artifact_sha256s=("4" * 64,),
        )
    with pytest.raises(PublicRedockingBenchmarkError, match="only"):
        PublicRedockingCaseResult(
            case_id=case_id,
            engine_id="engine_v2",
            status="failure",
            runtime_seconds=1.0,
            **_input_fields(case_id),
            rmsd_angstroms=(1.0,),
            pose_artifact_sha256s=("4" * 64,),
            failure_code="failed",
        )


def test_report_emits_required_metrics_subgroups_and_paired_deltas() -> None:
    report = build_public_redocking_benchmark_report(
        _profiles(),
        _identities(),
        _rows(),
        policy=_policy(),
    )

    assert len(report.rows) == 900
    assert len(report.executions) == 900
    assert len(report.to_dict()["execution_receipts"]) == 900
    assert report.to_dict()["full_failure_denominator_retained"] is True
    assert report.to_dict()["same_ranked_pose_count"] is True
    assert report.to_dict()["exact_case_commands_bound"] is True
    assert report.to_dict()["same_pocket_source"] is True
    assert report.to_dict()["same_pocket_geometry"] is False
    assert report.to_dict()["same_search_effort_budget"] is False
    assert report.to_dict()["search_effort_comparable"] is False
    assert report.to_dict()["runtime_boundary_comparable"] is False
    assert report.to_dict()["cpu_limit_comparable"] is True
    assert report.to_dict()["policy"]["external_timeout_seconds"] == 300
    assert report.to_dict()["policy"]["cpu_count"] == 1
    assert report.to_dict()["policy"]["engine_v2_candidate_budget"] == 64
    assert (
        report.to_dict()["policy"]["proposal_oracle_definition"]
        == "minimum_posebusters_symmetry_aware_rmsd_across_all_successful_engine_v2_candidates"
    )
    assert report.to_dict()["benchmark_executed"] is True
    assert report.to_dict()["bootstrap_confidence_intervals"] is True
    assert report.to_dict()["engineering_smoke_case_count"] == 2
    assert report.to_dict()["primary_blind_holdout_case_count"] == 298
    assert report.to_dict()["contaminated_development_case_count"] == 300
    assert report.to_dict()["supplementary_descriptive_case_count"] == 300
    assert report.to_dict()["primary_metrics_exclude_engineering_smoke"] is True
    assert _metric(
        report,
        "engine_v2",
        "full_case_failure_rate",
    ).value == pytest.approx(0.1)
    assert _metric(
        report,
        "engine_v2",
        "top3_rmsd_success_rate",
    ).value == pytest.approx(0.9)
    assert _metric(
        report,
        "engine_v2",
        "top5_valid_pose_success_rate",
    ).value == pytest.approx(0.9)
    assert _metric(
        report,
        "engine_v2",
        "top1_geometric_validity_rate",
    ).value == pytest.approx(0.9)
    assert _metric(
        report,
        "engine_v2",
        "preparation_success_rate",
    ).value == pytest.approx(0.9)
    assert _metric(
        report,
        "engine_v2",
        "complete_partial_charge_coverage_rate",
    ).value == pytest.approx(0.9)
    assert _metric(
        report,
        "engine_v2",
        "hbond_feature_coverage_rate",
    ).value == pytest.approx(0.9)
    assert _metric(
        report,
        "engine_v2",
        "candidate_generation_coverage_rate",
    ).value == pytest.approx(0.9 * 5.0 / 64.0)
    assert _metric(
        report,
        "engine_v2",
        "proposal_oracle_recovery_rate",
    ).value == pytest.approx(0.9)
    assert _metric(
        report,
        "engine_v2",
        "top1_scoring_regret_event_rate",
    ).value == pytest.approx(0.4)
    assert _metric(
        report,
        "engine_v2",
        "top5_selection_regret_event_rate",
    ).value == pytest.approx(0.0)
    assert _metric(
        report,
        "engine_v2",
        "top1_rmsd_success_rate",
        subgroup="size_small_1_20",
        analysis_scope="primary_blind_holdout",
    ).case_count == sum(
        profile.case_id in PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS
        and profile.size_subgroup == "size_small_1_20"
        for profile in _profiles()
    )
    assert _metric(
        report,
        "engine_v2",
        "top1_rmsd_success_rate",
        subgroup="rotor_flexible_5_plus",
        analysis_scope="primary_blind_holdout",
    ).case_count == sum(
        profile.case_id in PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS
        and profile.rotor_subgroup == "rotor_flexible_5_plus"
        for profile in _profiles()
    )
    ring_case_count = sum(
        profile.case_id in PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS
        and profile.ring_subgroup == "ring_acyclic_0"
        for profile in _profiles()
    )
    assert (
        _metric(
            report,
            "engine_v2",
            "proposal_oracle_recovery_rate",
            subgroup="ring_acyclic_0",
            analysis_scope="primary_blind_holdout",
        ).case_count
        == ring_case_count
    )
    paired = _metric(
        report,
        "engine_v2",
        "top1_rmsd_success_rate_paired_delta",
        baseline="vina",
    )
    assert paired.case_count == 300
    assert paired.confidence_interval_low <= paired.value
    assert paired.value <= paired.confidence_interval_high
    valid_paired = _metric(
        report,
        "engine_v2",
        "top5_valid_pose_success_rate_paired_delta",
        baseline="gnina",
    )
    assert valid_paired.case_count == 300
    assert _metric(
        report,
        "engine_v2",
        "full_case_failure_rate_paired_delta",
        baseline="vina",
    ).value == pytest.approx(0.0)
    assert _metric(
        report,
        "engine_v2",
        "runtime_seconds_paired_median_delta",
        baseline="vina",
    ).value == pytest.approx(-1.0)
    assert report.to_dict()["scientifically_validated"] is False
    assert report.to_dict()["claim_safe"] is False
    assert _metric(
        report,
        "engine_v2",
        "full_case_failure_rate",
        analysis_scope="primary_blind_holdout",
    ).case_count == len(PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS)
    assert _metric(
        report,
        "engine_v2",
        "full_case_failure_rate",
        analysis_scope="engineering_smoke",
    ).case_count == len(PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS)


def test_report_is_deterministic_and_binds_engine_identity() -> None:
    first = build_public_redocking_benchmark_report(
        _profiles(),
        _identities(),
        _rows(),
        policy=_policy(),
    )
    second = build_public_redocking_benchmark_report(
        _profiles(),
        _identities(),
        _rows(),
        policy=_policy(),
    )
    assert first.fingerprint_sha256 == second.fingerprint_sha256
    assert first.to_dict() == second.to_dict()

    changed_identities = list(_identities())
    changed_identities[0] = replace(
        changed_identities[0],
        implementation_sha256="f" * 64,
    )
    changed = build_public_redocking_benchmark_report(
        _profiles(),
        changed_identities,
        _rows(),
        policy=_policy(),
    )
    assert changed.fingerprint_sha256 != first.fingerprint_sha256


def test_report_rejects_cross_engine_input_or_evaluator_drift() -> None:
    rows = list(_rows())
    vina_first = len(FROZEN_PUBLIC_REDOCKING_CASE_IDS)
    rows[vina_first] = replace(
        rows[vina_first],
        receptor_artifact_sha256="f" * 64,
    )
    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="identical source artifacts",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            rows,
            policy=_policy(),
        )

    identities = list(_identities())
    identities[-1] = replace(
        identities[-1],
        evaluation_pipeline_sha256="f" * 64,
    )
    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="one evaluation pipeline",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            identities,
            _rows(),
            policy=_policy(),
        )


def test_public_report_builder_requires_verified_materialization_types() -> None:
    with pytest.raises(TypeError, match="materializations"):
        _build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            _executions(),
            policy=_policy(),
        )

    with pytest.raises(TypeError, match="VerifiedCaseMaterialization"):
        _build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            _executions(),
            materializations=tuple(
                materialization.to_dict() for materialization in _materializations()
            ),
            policy=_policy(),
        )

    class MaterializationSubclass(VerifiedCaseMaterialization):
        pass

    forged_subclass = object.__new__(MaterializationSubclass)
    with pytest.raises(TypeError, match="VerifiedCaseMaterialization"):
        _build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            _executions(),
            materializations=(forged_subclass, *_materializations()[1:]),
            policy=_policy(),
        )


def test_public_report_builder_rejects_raw_or_tampered_result_rows() -> None:
    with pytest.raises(
        TypeError,
        match="VerifiedPublicRedockingCaseExecution",
    ):
        _build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            _rows(),
            materializations=_materializations(),
            policy=_policy(),
        )

    executions = list(_executions())
    original = executions[0]
    forged = object.__new__(VerifiedPublicRedockingCaseExecution)
    for field_name in (
        "result",
        "materialization_receipt_sha256",
        "implementation_sha256",
        "evaluation_pipeline_sha256",
        "execution_environment_sha256",
        "schema_id",
        "_receipt_sha256",
        "_verification_authority",
    ):
        object.__setattr__(forged, field_name, getattr(original, field_name))
    object.__setattr__(
        forged,
        "result",
        replace(original.result, runtime_seconds=0.0),
    )
    executions[0] = forged

    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="execution receipt changed",
    ):
        _build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(executions),
            materializations=_materializations(),
            policy=_policy(),
        )


def test_verified_execution_requires_fresh_run_authority() -> None:
    row = _rows()[0]
    identity = _identities()[0]
    with pytest.raises(TypeError, match="fresh-run authority"):
        VerifiedPublicRedockingCaseExecution._from_fresh_execution(
            result=row,
            materialization_receipt_sha256=(
                _materialization(row.case_id).receipt_sha256
            ),
            implementation_sha256=identity.implementation_sha256,
            evaluation_pipeline_sha256=identity.evaluation_pipeline_sha256,
            execution_environment_sha256="8" * 64,
            verification_authority=object(),
        )


@pytest.mark.parametrize(
    ("field_name", "replacement", "message"),
    (
        (
            "materialization_receipt_sha256",
            "f" * 64,
            "verified materialization",
        ),
        ("implementation_sha256", "f" * 64, "implementation contradicts"),
        ("evaluation_pipeline_sha256", "f" * 64, "evaluator contradicts"),
        (
            "execution_environment_sha256",
            "f" * 64,
            "one execution environment",
        ),
    ),
)
def test_report_rejects_execution_receipt_identity_drift(
    field_name,
    replacement,
    message,
) -> None:
    executions = list(_executions())
    original = executions[0]
    evidence = {
        "materialization_receipt_sha256": (original.materialization_receipt_sha256),
        "implementation_sha256": original.implementation_sha256,
        "evaluation_pipeline_sha256": original.evaluation_pipeline_sha256,
        "execution_environment_sha256": original.execution_environment_sha256,
    }
    evidence[field_name] = replacement
    executions[0] = VerifiedPublicRedockingCaseExecution._from_fresh_execution(
        result=original.result,
        **evidence,
        verification_authority=benchmark_contract._VERIFIED_EXECUTION_AUTHORITY,
    )

    with pytest.raises(PublicRedockingBenchmarkError, match=message):
        _build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(executions),
            materializations=_materializations(),
            policy=_policy(),
        )


def test_report_rejects_forged_exact_materialization_type() -> None:
    original = _materializations()[0]
    forged = object.__new__(VerifiedCaseMaterialization)
    for field_name in (
        "case_id",
        "frozen_case_seed",
        "receptor_artifact_sha256",
        "reference_artifact_sha256",
        "native_artifact_sha256",
        "seed_artifact_sha256",
        "source_archive_sha256",
        "archive_member_names",
        "schema_id",
        "_receipt_sha256",
    ):
        object.__setattr__(forged, field_name, getattr(original, field_name))
    object.__setattr__(forged, "receptor_artifact_sha256", "f" * 64)
    object.__setattr__(
        forged,
        "_receipt_sha256",
        benchmark_contract._sha256(forged._projection()),
    )

    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="per-case frozen receipts",
    ):
        _build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            _executions(),
            materializations=(forged, *_materializations()[1:]),
            policy=_policy(),
        )


def test_report_rejects_shared_but_unverified_case_inputs() -> None:
    rows = list(_rows())
    case_count = len(FROZEN_PUBLIC_REDOCKING_CASE_IDS)
    for index in (0, case_count, case_count * 2):
        rows[index] = replace(
            rows[index],
            receptor_artifact_sha256="f" * 64,
        )

    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="verified case materialization",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(rows),
            policy=_policy(),
        )


def test_report_rejects_cross_engine_or_unfrozen_case_seed() -> None:
    rows = list(_rows())
    vina_index = len(FROZEN_PUBLIC_REDOCKING_CASE_IDS)
    command = list(rows[vina_index].execution_command)
    seed_index = command.index("--seed") + 1
    command[seed_index] = str(int(command[seed_index]) + 1)
    rows[vina_index] = replace(
        rows[vina_index],
        execution_command=tuple(command),
    )

    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="frozen grammar",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(rows),
            policy=_policy(),
        )

    rows = list(_rows())
    for index in (
        0,
        len(FROZEN_PUBLIC_REDOCKING_CASE_IDS),
        len(FROZEN_PUBLIC_REDOCKING_CASE_IDS) * 2,
    ):
        command = list(rows[index].execution_command)
        seed_index = command.index("--seed") + 1
        command[seed_index] = str(int(command[seed_index]) + 7)
        rows[index] = replace(
            rows[index],
            execution_command=tuple(command),
        )
    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="frozen grammar",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(rows),
            policy=_policy(),
        )


def test_report_rejects_row_execution_policy_drift() -> None:
    rows = list(_rows())
    vina_index = len(FROZEN_PUBLIC_REDOCKING_CASE_IDS)
    rows[vina_index] = replace(
        rows[vina_index],
        execution_policy=("cpu_count=8", "timeout_seconds=10"),
    )

    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="vina row policy contradicts",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(rows),
            policy=_policy(),
        )


def test_report_rejects_boolean_or_unsupported_torch_policy_values() -> None:
    rows = list(_rows())
    boolean_policy = _engine_v2_execution_policy(cpu_count=True)
    for index in range(len(FROZEN_PUBLIC_REDOCKING_CASE_IDS)):
        rows[index] = replace(
            rows[index],
            execution_policy=boolean_policy,
        )
    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="integer fields must be integers",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(rows),
            policy=_policy(),
        )

    rows = list(_rows())
    engine_v2_policy = _engine_v2_execution_policy(torch_version="2.7.0+cpu")
    for index in range(len(FROZEN_PUBLIC_REDOCKING_CASE_IDS)):
        rows[index] = replace(rows[index], execution_policy=engine_v2_policy)
    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="Engine V2 row policy contradicts",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(rows),
            policy=_policy(),
        )

    rows = list(_rows())
    allowed_but_mismatched_policy = _engine_v2_execution_policy(
        torch_version="2.6.0+cpu"
    )
    for index in range(len(FROZEN_PUBLIC_REDOCKING_CASE_IDS)):
        rows[index] = replace(
            rows[index],
            execution_policy=allowed_but_mismatched_policy,
        )
    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="Torch policy contradicts its identity",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(rows),
            policy=_policy(),
        )

    rows = list(_rows())
    vina_start = len(FROZEN_PUBLIC_REDOCKING_CASE_IDS)
    vina_end = vina_start * 2
    for index in range(vina_start, vina_end):
        rows[index] = replace(
            rows[index],
            execution_policy=("cpu_count=true", "timeout_seconds=300"),
        )
    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="vina row policy contradicts",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(rows),
            policy=_policy(),
        )


def test_report_rejects_row_command_cross_wired_to_another_engine() -> None:
    rows = list(_rows())
    vina_index = len(FROZEN_PUBLIC_REDOCKING_CASE_IDS)
    rows[vina_index] = replace(
        rows[vina_index],
        execution_command=_input_fields(
            rows[vina_index].case_id,
            "gnina",
        )["execution_command"],
    )

    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="vina command --out is outside the canonical run path",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(rows),
            policy=_policy(),
        )


def test_report_requires_vina_and_gnina_to_share_one_staged_binary() -> None:
    identities = list(_identities())
    gnina = identities[2]
    different_digest = "f" * 64
    different_binary = str(_RUN_ROOT / "private-external-binary" / different_digest)
    identities[2] = replace(
        gnina,
        implementation_sha256=different_digest,
        command=(different_binary, *gnina.command[1:]),
    )

    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="one identical staged binary",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            tuple(identities),
            _rows(),
            policy=_policy(),
        )


def test_report_rejects_non_engine_derived_failure_code() -> None:
    rows = list(_rows())
    rows[0] = replace(rows[0], failure_code="attacker_supplied_failure")

    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="engine-derived frozen failure code",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(rows),
            policy=_policy(),
        )


def test_report_accepts_typed_engine_v2_input_failure_code() -> None:
    rows = list(_rows())
    diagnostics = rows[0].engine_v2_diagnostics
    assert diagnostics is not None
    rows[0] = replace(
        rows[0],
        failure_code="engine_v2_input_unsupported",
        engine_v2_diagnostics=replace(
            diagnostics,
            preparation_failure_code="input_parse_unsupported",
        ),
    )

    report = build_public_redocking_benchmark_report(
        _profiles(),
        _identities(),
        tuple(rows),
        policy=_policy(),
    )

    assert report.rows[0].failure_code == "engine_v2_input_unsupported"


def test_report_rejects_engine_v2_input_failure_code_receipt_mismatch() -> None:
    rows = list(_rows())
    rows[0] = replace(rows[0], failure_code="engine_v2_input_unsupported")

    with pytest.raises(
        ValueError,
        match="input failure contradicts preparation diagnostics",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(rows),
            policy=_policy(),
        )


def test_report_rejects_engine_v2_input_path_cross_wired_to_another_case() -> None:
    rows = list(_rows())
    command = list(rows[0].execution_command)
    receptor_index = command.index("--receptor") + 1
    command[receptor_index] = f"/tmp/{FROZEN_PUBLIC_REDOCKING_CASE_IDS[1]}_protein.pdb"
    rows[0] = replace(rows[0], execution_command=tuple(command))

    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="Engine V2 row command does not match the frozen grammar",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(rows),
            policy=_policy(),
        )


@pytest.mark.parametrize(
    "mutate",
    (
        lambda command, case_id: (
            *command,
            "--unfrozen-option",
            "attacker-controlled",
        ),
        lambda command, case_id: tuple(
            (
                f"/attacker-controlled/{case_id}_protein.pdb"
                if index == command.index("--receptor") + 1
                else token
            )
            for index, token in enumerate(command)
        ),
    ),
)
def test_report_rejects_unknown_options_and_same_basename_input_substitution(
    mutate,
) -> None:
    rows = list(_rows())
    original = rows[0]
    rows[0] = replace(
        original,
        execution_command=mutate(original.execution_command, original.case_id),
    )

    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="frozen grammar",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(rows),
            policy=_policy(),
        )


def test_report_rejects_metrics_forged_independently_of_rows() -> None:
    report = build_public_redocking_benchmark_report(
        _profiles(),
        _identities(),
        _rows(),
        policy=_policy(),
    )
    forged = list(report.metrics)
    forged[0] = replace(forged[0], value=forged[0].value + 0.1)

    with pytest.raises(PublicRedockingBenchmarkError, match="do not match"):
        replace(report, metrics=tuple(forged))


def test_report_rejects_engine_v2_candidate_diagnostic_substitution() -> None:
    rows = list(_rows())
    original = rows[1]
    diagnostics = original.engine_v2_diagnostics
    assert diagnostics is not None
    candidates = list(diagnostics.candidates)
    candidates[0] = replace(candidates[0], rmsd_angstrom=9.0)
    rows[1] = replace(
        original,
        engine_v2_diagnostics=replace(
            diagnostics,
            candidates=tuple(candidates),
        ),
    )

    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="contradicts candidate diagnostics",
    ):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            tuple(rows),
            policy=_policy(),
        )


def test_engine_v2_diagnostics_validate_uniform_v3_ensemble_lineage() -> None:
    row = _success(
        FROZEN_PUBLIC_REDOCKING_CASE_IDS[0],
        "engine_v2",
        top1=1.0,
        top2=2.0,
        top3=3.0,
        runtime=1.0,
    )
    diagnostics = row.engine_v2_diagnostics
    assert diagnostics is not None
    candidates = list(diagnostics.candidates)
    candidates[0] = replace(
        candidates[0],
        proposal_mode="uniform_v3_rigid_ensemble",
        ensemble_source_proposal_index=1,
    )
    validated = replace(diagnostics, candidates=tuple(candidates))
    assert validated.candidates[0].ensemble_source_proposal_index == 1

    candidates[2] = replace(
        candidates[2],
        proposal_mode="uniform_v3_rigid_ensemble",
        ensemble_source_proposal_index=1,
    )
    with pytest.raises(PublicRedockingBenchmarkError, match="lineage"):
        replace(diagnostics, candidates=tuple(candidates))

    invalid_source = list(diagnostics.candidates)
    invalid_source[0] = replace(
        invalid_source[0],
        proposal_mode="uniform_v3_rigid_ensemble",
        ensemble_source_proposal_index=5,
    )
    with pytest.raises(PublicRedockingBenchmarkError, match="lineage"):
        replace(diagnostics, candidates=tuple(invalid_source))


def test_engine_v2_diagnostics_validate_torsion_rescue_lineage() -> None:
    row = _success(
        FROZEN_PUBLIC_REDOCKING_CASE_IDS[0],
        "engine_v2",
        top1=1.0,
        top2=2.0,
        top3=3.0,
        runtime=1.0,
    )
    diagnostics = row.engine_v2_diagnostics
    assert diagnostics is not None
    candidate_schema = (
        benchmark_contract.PUBLIC_REDOCKING_ENGINE_V2_TORSION_RESCUE_CANDIDATE_SCHEMA_ID
    )
    candidates = [
        PublicRedockingEngineV2CandidateDiagnostic(
            proposal_index=index,
            status="failure",
            proposal_mode="uniform_fallback",
            error_code="synthetic_candidate_failure",
            schema_id=candidate_schema,
        )
        for index in range(64)
    ]
    proposal_receipt = _torsion_rescue_proposal_receipt()
    allocation_rows = proposal_receipt["allocation"]
    for pair in allocation_rows["v3_target_parent_pairs"]:
        target = pair["target_proposal_index"]
        candidates[target] = replace(
            candidates[target],
            proposal_mode="uniform_v3_rigid_ensemble",
            ensemble_source_proposal_index=pair["parent_proposal_index"],
        )
    for pair in allocation_rows["rescue_target_parent_pairs"]:
        target = pair["target_proposal_index"]
        candidates[target] = replace(
            candidates[target],
            proposal_mode="uniform_torsion_rescue_variant",
            torsion_rescue_parent_proposal_index=pair["parent_proposal_index"],
        )
    validated = replace(
        diagnostics,
        schema_id=(
            benchmark_contract.PUBLIC_REDOCKING_ENGINE_V2_TORSION_RESCUE_DIAGNOSTIC_SCHEMA_ID
        ),
        candidates=tuple(candidates),
        source_paired_torsion_rescue_proposal_receipt=proposal_receipt,
    )
    assert validated.candidates[5].torsion_rescue_parent_proposal_index == 6

    tampered_evidence = validated.to_dict()[
        "source_paired_torsion_rescue_proposal_receipt"
    ]
    tampered_evidence["allocation"]["result_dependent_allocation"] = True

    def rehash(document: dict[str, object], field_name: str) -> None:
        projection = dict(document)
        projection.pop(field_name)
        document[field_name] = hashlib.sha256(
            json.dumps(
                projection,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
        ).hexdigest()

    rehash(tampered_evidence["allocation"], "allocation_sha256")
    tampered_evidence["guided_placement"]["torsion_rescue_allocation_sha256"] = (
        tampered_evidence["allocation"]["allocation_sha256"]
    )
    rehash(tampered_evidence["guided_placement"], "receipt_sha256")
    rehash(tampered_evidence, "receipt_sha256")
    with pytest.raises(PublicRedockingBenchmarkError, match="allocation lanes"):
        replace(
            validated,
            source_paired_torsion_rescue_proposal_receipt=tampered_evidence,
        )

    truncated_evidence = validated.to_dict()[
        "source_paired_torsion_rescue_proposal_receipt"
    ]
    truncated_evidence["allocation"]["v3_target_parent_pairs"] = []
    rehash(truncated_evidence["allocation"], "allocation_sha256")
    truncated_evidence["guided_placement"]["torsion_rescue_allocation_sha256"] = (
        truncated_evidence["allocation"]["allocation_sha256"]
    )
    rehash(truncated_evidence["guided_placement"], "receipt_sha256")
    rehash(truncated_evidence, "receipt_sha256")
    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="exhaustive baseline partition",
    ):
        replace(
            validated,
            source_paired_torsion_rescue_proposal_receipt=truncated_evidence,
        )

    with pytest.raises(TypeError):
        validated.source_paired_torsion_rescue_proposal_receipt["allocation"][
            "authority_rotor_count"
        ] = 2

    serialized_evidence = validated.to_dict()[
        "source_paired_torsion_rescue_proposal_receipt"
    ]
    allocation_evidence = serialized_evidence["allocation"]
    source_coordinate_sha256 = serialized_evidence["candidate_slots"][0][
        "coordinate_fingerprint_sha256"
    ]
    final_coordinate_sha256 = "2" * 64
    initial_penalty = (1.0).hex()
    final_penalty = (0.0).hex()
    accepted_steps = 1
    accepted_rotation_steps = 0
    original_pose_valid = False
    translation = ((0.0).hex(),) * 3
    rotation = ((0.0).hex(),) * 3
    refinement_payload: dict[str, object] = {
        name: None
        for name in (
            benchmark_contract._SOURCE_PAIRED_TORSION_RESCUE_REFINEMENT_RECEIPT_FIELDS
            - {"receipt_sha256"}
        )
    }
    refinement_payload.update(
        {
            "schema_id": (
                "betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.1.0"
            ),
            "legacy_v7_receipt_schema_id": (
                "betelgeuze.engine_v2_interaction_aware_torsion_contact_receipt/7.0.0"
            ),
            "source_proposal_sha256": serialized_evidence["candidate_slots"][0][
                "proposal_fingerprint_sha256"
            ],
            "pre_coordinates_sha256": source_coordinate_sha256,
            "post_coordinates_sha256": final_coordinate_sha256,
            "initial_penalty_binary64_hex": initial_penalty,
            "final_penalty_binary64_hex": final_penalty,
            "accepted_steps": accepted_steps,
            "accepted_rotation_steps": accepted_rotation_steps,
            "original_pose_valid": original_pose_valid,
            "total_translation_binary64_hex": list(translation),
            "total_rotation_vector_binary64_hex": list(rotation),
            "config_sha256": "5" * 64,
            "v3_proposal_indices": [
                pair["target_proposal_index"]
                for pair in allocation_evidence["v3_target_parent_pairs"]
            ],
            "proposal_torsion_eligibility_lane": "ineligible_source_or_other_lane",
            "source_paired_parent_proposal_index": None,
            "source_paired_torsion_rescue_pairs": allocation_evidence[
                "rescue_target_parent_pairs"
            ],
            "source_paired_torsion_rescue_allocation_sha256": allocation_evidence[
                "allocation_sha256"
            ],
            "source_paired_torsion_rescue_policy_sha256": serialized_evidence[
                "rescue_policy_sha256"
            ],
            "source_paired_torsion_rescue_guidance_context_sha256": (
                allocation_evidence["guidance_context_sha256"]
            ),
            "source_paired_torsion_rescue_budget_sha256": allocation_evidence[
                "budget_sha256"
            ],
            "source_paired_torsion_rescue_profile": True,
            "source_paired_torsion_rescue_variant_cap": 4,
            "nested_v6_treated_proposal_as_v3_variant": False,
            "rescue_target_excluded_from_nested_v3_indices": False,
            "result_dependent_eligibility": False,
            "clearance_measurement_evaluated": False,
            "clearance_measurement_unavailable_reason": (
                "not_source_paired_rescue_target"
            ),
            "clearance_radii_policy_sha256": "",
            "baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex": "",
            "optimized_minimum_vdw_surface_gap_angstrom_binary64_hex": "",
            "optimized_coordinates_sha256": "",
            "development_only": True,
            "stage0_eligible": False,
            "fresh_execution_authorized": False,
            "claim_safe": False,
            "source_lane_retained": True,
            "scientifically_validated": False,
            "ranking_score_reused_as_physical_energy": False,
            "posebusters_or_rmsd_used_for_selection": False,
            "accepted_rotation_steps_include_torsion": True,
            "generic_penalty_scope": (
                "source_proposal_to_final_coordinates_v7_objective"
            ),
            "baseline_v6_penalty_scope": "post_v6_coordinates_v7_objective",
        }
    )
    refinement_payload["receipt_sha256"] = hashlib.sha256(
        json.dumps(
            refinement_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    successful_fallback = PublicRedockingEngineV2CandidateDiagnostic(
        proposal_index=0,
        status="success",
        proposal_mode="uniform_fallback",
        proposal_fingerprint_sha256="1" * 64,
        coordinate_fingerprint_sha256=final_coordinate_sha256,
        score=0.0,
        rmsd_angstrom=0.0,
        geometric_valid=True,
        chemical_valid=True,
        pose_artifact_sha256="3" * 64,
        score_terms_receipt_sha256="4" * 64,
        hbond_count=0,
        selection_eligible=True,
        refinement_receipt_sha256=refinement_payload["receipt_sha256"],
        refinement_initial_penalty_binary64_hex=initial_penalty,
        refinement_final_penalty_binary64_hex=final_penalty,
        refinement_accepted_steps=accepted_steps,
        refinement_accepted_rotation_steps=accepted_rotation_steps,
        refinement_original_pose_valid=original_pose_valid,
        refinement_total_translation_binary64_hex=translation,
        refinement_total_rotation_vector_binary64_hex=rotation,
        refinement_receipt_payload=refinement_payload,
        score_term_binary64_hex=_zero_score_terms(),
        schema_id=candidate_schema,
    )
    successful_rows = list(validated.candidates)
    successful_rows[0] = successful_fallback
    successful_diagnostics = replace(
        validated,
        candidates=tuple(successful_rows),
    )
    assert successful_diagnostics.candidates[0].status == "success"

    rescue_pair = allocation_evidence["rescue_target_parent_pairs"][0]
    rescue_target = rescue_pair["target_proposal_index"]
    rescue_parent = rescue_pair["parent_proposal_index"]
    rescue_final_coordinate_sha256 = "6" * 64
    rescue_baseline_coordinate_sha256 = "a" * 64
    rescue_refinement_payload = successful_fallback.to_dict()[
        "refinement_receipt_payload"
    ]
    rescue_refinement_payload.update(
        {
            "source_proposal_sha256": serialized_evidence["candidate_slots"][
                rescue_target
            ]["proposal_fingerprint_sha256"],
            "pre_coordinates_sha256": serialized_evidence["candidate_slots"][
                rescue_target
            ]["coordinate_fingerprint_sha256"],
            "post_coordinates_sha256": rescue_final_coordinate_sha256,
            "proposal_torsion_eligibility_lane": (
                "source_paired_torsion_rescue_variant"
            ),
            "source_paired_parent_proposal_index": rescue_parent,
            "nested_v6_treated_proposal_as_v3_variant": False,
            "rescue_target_excluded_from_nested_v3_indices": True,
            "torsion_variant_available": True,
            "torsion_selected": True,
            "baseline_coordinates_sha256": rescue_baseline_coordinate_sha256,
            "clearance_measurement_evaluated": True,
            "clearance_measurement_unavailable_reason": "none",
            "clearance_radii_policy_sha256": (
                benchmark_contract._SOURCE_PAIRED_TORSION_RESCUE_VDW_CONTACT_POLICY_SHA256
            ),
            "baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex": ((-1.0).hex()),
            "optimized_minimum_vdw_surface_gap_angstrom_binary64_hex": ((-0.5).hex()),
            "optimized_coordinates_sha256": rescue_final_coordinate_sha256,
        }
    )
    rehash(rescue_refinement_payload, "receipt_sha256")
    successful_rescue = replace(
        successful_fallback,
        proposal_index=rescue_target,
        proposal_mode="uniform_torsion_rescue_variant",
        torsion_rescue_parent_proposal_index=rescue_parent,
        proposal_fingerprint_sha256="7" * 64,
        coordinate_fingerprint_sha256=rescue_final_coordinate_sha256,
        pose_artifact_sha256="8" * 64,
        score_terms_receipt_sha256="9" * 64,
        refinement_receipt_sha256=rescue_refinement_payload["receipt_sha256"],
        refinement_receipt_payload=rescue_refinement_payload,
    )
    successful_rows = list(successful_diagnostics.candidates)
    successful_rows[rescue_target] = successful_rescue
    successful_diagnostics = replace(
        successful_diagnostics,
        candidates=tuple(successful_rows),
    )
    assert successful_diagnostics.candidates[rescue_target].status == "success"

    legacy_rescue_payload = successful_rescue.to_dict()["refinement_receipt_payload"]
    legacy_rescue_payload["schema_id"] = (
        "betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.0.0"
    )
    for (
        field_name
    ) in benchmark_contract._SOURCE_PAIRED_TORSION_RESCUE_CLEARANCE_TELEMETRY_FIELDS:
        legacy_rescue_payload.pop(field_name)
    rehash(legacy_rescue_payload, "receipt_sha256")
    legacy_rescue = replace(
        successful_rescue,
        refinement_receipt_sha256=legacy_rescue_payload["receipt_sha256"],
        refinement_receipt_payload=legacy_rescue_payload,
    )
    legacy_rows = list(successful_diagnostics.candidates)
    legacy_rows[rescue_target] = legacy_rescue
    with pytest.raises(PublicRedockingBenchmarkError, match="refinement receipt"):
        replace(
            successful_diagnostics,
            candidates=tuple(legacy_rows),
        )

    telemetry_substitutions = {
        "clearance_measurement_evaluated": False,
        "baseline_v6_minimum_vdw_surface_gap_angstrom_binary64_hex": "nan",
        "optimized_minimum_vdw_surface_gap_angstrom_binary64_hex": "0x1p+0",
        "optimized_coordinates_sha256": "c" * 64,
        "clearance_radii_policy_sha256": "d" * 64,
    }
    for field_name, substituted_value in telemetry_substitutions.items():
        substituted_payload = successful_rescue.to_dict()["refinement_receipt_payload"]
        substituted_payload[field_name] = substituted_value
        rehash(substituted_payload, "receipt_sha256")
        substituted_candidate = replace(
            successful_rescue,
            refinement_receipt_sha256=substituted_payload["receipt_sha256"],
            refinement_receipt_payload=substituted_payload,
        )
        substituted_rows = list(successful_diagnostics.candidates)
        substituted_rows[rescue_target] = substituted_candidate
        with pytest.raises(
            PublicRedockingBenchmarkError,
            match="clearance|source-paired|surface gap",
        ):
            replace(successful_diagnostics, candidates=tuple(substituted_rows))

    receipt_substitutions = {
        "pre_coordinates_sha256": "8" * 64,
        "post_coordinates_sha256": "9" * 64,
        "initial_penalty_binary64_hex": (2.0).hex(),
        "final_penalty_binary64_hex": (0.5).hex(),
        "accepted_steps": 2,
        "accepted_rotation_steps": 1,
        "original_pose_valid": True,
        "total_translation_binary64_hex": [(1.0).hex(), (0.0).hex(), (0.0).hex()],
        "total_rotation_vector_binary64_hex": [
            (0.0).hex(),
            (1.0).hex(),
            (0.0).hex(),
        ],
    }
    for field_name, substituted_value in receipt_substitutions.items():
        substituted_payload = successful_fallback.to_dict()[
            "refinement_receipt_payload"
        ]
        substituted_payload[field_name] = substituted_value
        rehash(substituted_payload, "receipt_sha256")
        substituted_candidate = replace(
            successful_fallback,
            refinement_receipt_sha256=substituted_payload["receipt_sha256"],
            refinement_receipt_payload=substituted_payload,
        )
        substituted_rows = list(successful_diagnostics.candidates)
        substituted_rows[0] = substituted_candidate
        with pytest.raises(PublicRedockingBenchmarkError, match="refinement receipt"):
            replace(successful_diagnostics, candidates=tuple(substituted_rows))

    contradictory_payload = successful_fallback.to_dict()["refinement_receipt_payload"]
    contradictory_payload["result_dependent_eligibility"] = True
    rehash(contradictory_payload, "receipt_sha256")
    contradictory_candidate = replace(
        successful_fallback,
        refinement_receipt_sha256=contradictory_payload["receipt_sha256"],
        refinement_receipt_payload=contradictory_payload,
    )
    contradictory_rows = list(successful_diagnostics.candidates)
    contradictory_rows[0] = contradictory_candidate
    with pytest.raises(PublicRedockingBenchmarkError, match="refinement receipt"):
        replace(successful_diagnostics, candidates=tuple(contradictory_rows))

    duplicate_parent = list(candidates)
    duplicate_parent[7] = replace(
        duplicate_parent[7],
        proposal_mode="uniform_torsion_rescue_variant",
        torsion_rescue_parent_proposal_index=6,
    )
    with pytest.raises(PublicRedockingBenchmarkError, match="lineage"):
        replace(
            validated,
            candidates=tuple(duplicate_parent),
        )

    non_fallback_parent = list(candidates)
    non_fallback_parent[6] = replace(
        non_fallback_parent[6],
        proposal_mode="pocket_center_baseline",
    )
    with pytest.raises(PublicRedockingBenchmarkError, match="lineage"):
        replace(
            validated,
            candidates=tuple(non_fallback_parent),
        )


def test_engine_v2_diagnostics_bind_complete_backend_receipt() -> None:
    row = _success(
        FROZEN_PUBLIC_REDOCKING_CASE_IDS[0],
        "engine_v2",
        top1=1.0,
        top2=2.0,
        top3=3.0,
        runtime=1.0,
    )
    diagnostics = row.engine_v2_diagnostics
    assert diagnostics is not None
    serialized = diagnostics.to_dict()["scorer_backend_receipt"]
    assert isinstance(serialized, dict)
    assert serialized["backend"] == "python_reference"
    assert serialized["implicit_fallback_allowed"] is False

    substituted = dict(serialized)
    substituted["backend_version"] = "changed-after-scoring"
    with pytest.raises(
        PublicRedockingBenchmarkError,
        match="backend receipt hash mismatch",
    ):
        replace(diagnostics, scorer_backend_receipt=substituted)


def test_missing_case_or_engine_row_cannot_drop_the_denominator() -> None:
    with pytest.raises(PublicRedockingBenchmarkError, match="every engine/case"):
        build_public_redocking_benchmark_report(
            _profiles(),
            _identities(),
            _rows()[:-1],
            policy=_policy(),
        )


def test_profile_order_and_identity_order_are_exact() -> None:
    with pytest.raises(PublicRedockingBenchmarkError, match="profiles"):
        build_public_redocking_benchmark_report(
            tuple(reversed(_profiles())),
            _identities(),
            _rows(),
            policy=_policy(),
        )


def test_frozen_size_rotor_and_ring_profiles_cannot_be_rewritten() -> None:
    profiles = tuple(
        replace(profile, heavy_atom_count=10, rotor_count=0, ring_count=0)
        for profile in _profiles()
    )
    with pytest.raises(PublicRedockingBenchmarkError, match="source-derived"):
        build_public_redocking_benchmark_report(
            profiles,
            _identities(),
            _rows(),
            policy=_policy(),
        )
    with pytest.raises(PublicRedockingBenchmarkError, match="engine identities"):
        build_public_redocking_benchmark_report(
            _profiles(),
            tuple(reversed(_identities())),
            _rows(),
            policy=_policy(),
        )
