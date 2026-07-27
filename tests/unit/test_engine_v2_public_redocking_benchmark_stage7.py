from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest

from betelgeuze_engine_v2.benchmark import (
    FROZEN_PUBLIC_REDOCKING_CASE_IDS,
    PUBLIC_REDOCKING_ARCHIVE_SHA256,
    PUBLIC_REDOCKING_COHORT_COUNT,
    PUBLIC_REDOCKING_PRIMARY_ENGINES,
    PUBLIC_REDOCKING_SOURCE_IDS_SHA256,
    FrozenPublicRedockingCohort,
    PublicRedockingBenchmarkError,
    PublicRedockingCaseProfile,
    PublicRedockingCaseResult,
    PublicRedockingEngineIdentity,
    PublicRedockingEvaluationPolicy,
    build_public_redocking_benchmark_report,
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


def _source_identifier_bytes() -> bytes:
    source_ids = sorted((*FROZEN_PUBLIC_REDOCKING_CASE_IDS, *_EXCLUDED_SOURCE_IDS))
    return ("\n".join(source_ids) + "\n").encode("ascii")


def _profiles() -> tuple[PublicRedockingCaseProfile, ...]:
    return frozen_public_redocking_profiles()


def _identities() -> tuple[PublicRedockingEngineIdentity, ...]:
    commands = {
        "engine_v2": (
            "fixture-engine",
            "engine_v2",
            "--candidate-count",
            "64",
            "--cpu",
            "1",
            "--torch-version",
            "2.6.0",
        ),
        "vina": (
            "fixture-engine",
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
            "fixture-engine",
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
            implementation_sha256=str(index + 1) * 64,
            evaluation_pipeline_sha256="e" * 64,
            command=commands[engine_id],
        )
        for index, engine_id in enumerate(PUBLIC_REDOCKING_PRIMARY_ENGINES)
    )


def _input_fields(
    case_id: str,
    engine_id: str = "engine_v2",
) -> dict[str, object]:
    profile = next(
        row for row in frozen_public_redocking_profiles() if row.case_id == case_id
    )

    def digest(role: str) -> str:
        return hashlib.sha256(f"{case_id}:{role}".encode("ascii")).hexdigest()

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
    execution_command = (
        (
            "fixture-engine",
            "engine_v2",
            "--case-id",
            case_id,
            "--receptor",
            f"{case_id}-receptor.pdb",
            "--ligand",
            f"{case_id}-seed.sdf",
            "--pocket-source",
            f"{case_id}-native.sdf",
            "--candidate-count",
            "64",
            "--cpu",
            "1",
            "--seed",
            "17",
            "--out",
            f"{case_id}-engine-v2.sdf",
        )
        if engine_id == "engine_v2"
        else (
            "fixture-engine",
            "--receptor",
            f"{case_id}-receptor.pdb",
            "--ligand",
            f"{case_id}-seed.sdf",
            "--autobox_ligand",
            f"{case_id}-native.sdf",
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
            "17",
            "--out",
            f"{case_id}-{engine_id}.sdf",
            "--scoring",
            "vina",
            "--cnn_scoring",
            "none" if engine_id == "vina" else "rescore",
            *(
                ()
                if engine_id == "vina"
                else ("--cnn", "crossdock_default2018")
            ),
        )
    )
    return {
        "receptor_artifact_sha256": digest("receptor"),
        "reference_artifact_sha256": digest("reference"),
        "native_artifact_sha256": profile.ligand_artifact_sha256,
        "seed_artifact_sha256": digest("seed"),
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
                        failure_code="fixture_failure",
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


def _metric(report, engine_id, metric_id, subgroup="all", baseline=""):
    return next(
        metric
        for metric in report.metrics
        if metric.engine_id == engine_id
        and metric.metric_id == metric_id
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
        ).case_count
        == 117
    )
    assert (
        _metric(
            report,
            "engine_v2",
            "top1_rmsd_success_rate",
            subgroup="rotor_flexible_5_plus",
        ).case_count
        == 157
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
        match="vina command contradicts frozen --cnn_scoring",
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
