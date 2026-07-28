from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
import hashlib
from pathlib import Path

import pytest

import betelgeuze_engine_v2.benchmark.public_redocking_benchmark as benchmark_contract
from betelgeuze_engine_v2.benchmark import (
    FROZEN_PUBLIC_REDOCKING_CASE_IDS,
    PUBLIC_REDOCKING_ARCHIVE_SHA256,
    PUBLIC_REDOCKING_CASE_SEED_BASE,
    PUBLIC_REDOCKING_COHORT_COUNT,
    PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS,
    PUBLIC_REDOCKING_PRIMARY_BLIND_HOLDOUT_CASE_IDS,
    PUBLIC_REDOCKING_PRIMARY_ENGINES,
    PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
    FrozenPublicRedockingCohort,
    PublicRedockingBenchmarkError,
    PublicRedockingCaseProfile,
    PublicRedockingCaseResult,
    PublicRedockingEngineIdentity,
    PublicRedockingEvaluationPolicy,
    VerifiedCaseMaterialization,
    VerifiedPublicRedockingCaseExecution,
    build_public_redocking_benchmark_report as _build_public_redocking_benchmark_report,
    frozen_public_redocking_case_seed,
    frozen_public_redocking_cohort,
    frozen_public_redocking_profiles,
    verify_public_redocking_source_identifiers,
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
            verification_authority=(
                benchmark_contract._VERIFIED_EXECUTION_AUTHORITY
            ),
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
        (
            "cpu_count=1",
            "torch_interop_threads=1",
            "torch_intraop_threads=1",
            'torch_version="2.6.0"',
        )
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
    return PublicRedockingCaseResult(
        case_id=case_id,
        engine_id=engine_id,
        status="success",
        runtime_seconds=runtime,
        **_input_fields(case_id, engine_id),
        rmsd_angstroms=(top1, top2, top3, 4.0, 5.0),
        geometric_valid=(True, True, True, False, False),
        chemical_valid=(True, True, True, False, False),
        pose_artifact_sha256s=tuple(str(index + 4) * 64 for index in range(5)),
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
    assert document["raw_structure_data_bundled"] is False
    assert document["benchmark_executed"] is False
    assert document["claim_safe"] is False


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
    assert report.to_dict()["benchmark_executed"] is True
    assert report.to_dict()["bootstrap_confidence_intervals"] is True
    assert report.to_dict()["engineering_smoke_case_count"] == 2
    assert report.to_dict()["primary_blind_holdout_case_count"] == 298
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
    assert (
        _metric(
            report,
            "engine_v2",
            "top1_rmsd_success_rate",
            subgroup="size_small_1_20",
            analysis_scope="primary_blind_holdout",
        ).case_count
        == 116
    )
    assert (
        _metric(
            report,
            "engine_v2",
            "top1_rmsd_success_rate",
            subgroup="rotor_flexible_5_plus",
            analysis_scope="primary_blind_holdout",
        ).case_count
        == 156
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
        "materialization_receipt_sha256": (
            original.materialization_receipt_sha256
        ),
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
    boolean_policy = (
        "cpu_count=true",
        "torch_interop_threads=1",
        "torch_intraop_threads=1",
        'torch_version="2.6.0"',
    )
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
    engine_v2_policy = (
        "cpu_count=1",
        "torch_interop_threads=1",
        "torch_intraop_threads=1",
        'torch_version="2.7.0+cpu"',
    )
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
    allowed_but_mismatched_policy = (
        "cpu_count=1",
        "torch_interop_threads=1",
        "torch_intraop_threads=1",
        'torch_version="2.6.0+cpu"',
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
    rows[0] = replace(rows[0], failure_code="engine_v2_input_unsupported")

    report = build_public_redocking_benchmark_report(
        _profiles(),
        _identities(),
        tuple(rows),
        policy=_policy(),
    )

    assert report.rows[0].failure_code == "engine_v2_input_unsupported"


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


def test_frozen_size_and_rotor_profiles_cannot_be_rewritten() -> None:
    profiles = tuple(
        replace(profile, heavy_atom_count=10, rotor_count=0) for profile in _profiles()
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
