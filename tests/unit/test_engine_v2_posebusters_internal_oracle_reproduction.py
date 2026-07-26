from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
import zipfile

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_posebusters_internal_oracle_evaluation as oracle_module,
)
from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_posebusters_internal_oracle_reproduction as reproduction,
)
from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_posebusters_internal_oracle_runtime_observation as runtime_module,
)
from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_posebusters_internal_oracle_stratification as strata_module,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_internal_oracle_reproduction import (  # noqa: E402
    PoseBustersInternalOracleChainTrustAnchor,
    PoseBustersInternalOracleReproductionError,
    materialize_posebusters_internal_oracle_reproduction_result,
    materialize_posebusters_internal_oracle_reproduction_work_order,
    posebusters_internal_oracle_chain_signing_bytes,
    posebusters_internal_oracle_chain_signing_payload,
    verify_posebusters_internal_oracle_reproduction_result,
    verify_posebusters_internal_oracle_reproduction_work_order,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_ed25519 import (  # noqa: E402
    ed25519_public_key_bytes,
    sign_ed25519,
)


_CASE_IDS = ("1ABC_AAA", "2DEF_BBB")
_BASELINE_HOST = hashlib.sha256(b"baseline-host").hexdigest()
_EXTERNAL_HOST = hashlib.sha256(b"external-host").hexdigest()
_WORK_ORDER_OPERATOR = hashlib.sha256(b"work-order-operator").hexdigest()
_EXTERNAL_EXECUTOR = hashlib.sha256(b"external-executor").hexdigest()
_EXECUTION_NONCE = hashlib.sha256(b"single-use-execution-nonce").hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _canonical_sha(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _attestation(
    *,
    host: str = _EXTERNAL_HOST,
    executor: str = _EXTERNAL_EXECUTOR,
    nonce: str = _EXECUTION_NONCE,
    observed_utc: str = "2026-07-26T02:00:00Z",
) -> dict[str, object]:
    return {
        "schema_id": (
            "betelgeuze.engine_v2_posebusters_internal_oracle_runtime_attestation/1.0.0"
        ),
        "host_identity_sha256": host,
        "execution_operator_identity_sha256": executor,
        "execution_nonce_sha256": nonce,
        "observed_utc": observed_utc,
        "host_identity_cryptographically_proven": False,
        "nonce_single_use_registry_reviewed": False,
    }


def _write_receipt(path: Path, payload: dict[str, object]) -> tuple[str, str]:
    receipt_sha = _canonical_sha(payload)
    document = {**payload, "receipt_sha256": receipt_sha}
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(document) + b"\n")
    path.chmod(0o600)
    return receipt_sha, _file_sha(path)


def _wheel(
    root: Path, *, include_reproduction_entrypoint: bool = True
) -> tuple[Path, str]:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "betelgeuze_engine_v2-0.3.0a1-py3-none-any.whl"
    repository_root = Path(reproduction.__file__).resolve().parents[2]
    entrypoints = {
        "betelgeuze-engine-v2-posebusters-internal-oracle": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_internal_oracle_evaluation:main"
        ),
        "betelgeuze-engine-v2-posebusters-internal-oracle-runtime": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_internal_oracle_runtime_observation:main"
        ),
        "betelgeuze-engine-v2-posebusters-internal-oracle-strata": (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_internal_oracle_stratification:main"
        ),
    }
    if include_reproduction_entrypoint:
        entrypoints["betelgeuze-engine-v2-posebusters-internal-oracle-reproduce"] = (
            "betelgeuze_engine_v2.benchmark."
            "public_posebusters_internal_oracle_reproduction:main"
        )
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for _role, _digest, member_path in reproduction._source_members():
            archive.writestr(member_path, (repository_root / member_path).read_bytes())
        archive.writestr(
            "betelgeuze_engine_v2-0.3.0a1.dist-info/entry_points.txt",
            "[console_scripts]\n"
            + "".join(
                f"{name} = {target}\n" for name, target in sorted(entrypoints.items())
            ),
        )
    return path, _file_sha(path)


def _oracle_payload() -> dict[str, object]:
    return {
        "schema_id": oracle_module.POSEBUSTERS_INTERNAL_ORACLE_EVALUATION_SCHEMA_ID,
        "runtime_identity_sha256": _canonical_sha("oracle-runtime-identity"),
        "all_case_denominator": len(_CASE_IDS),
        "case_rows": [
            {
                "case_id": _CASE_IDS[0],
                "status": "evaluated",
                "selected_pose_count": 1,
                "oracle_attempted": True,
            },
            {
                "case_id": _CASE_IDS[1],
                "status": "blocked_upstream",
                "selected_pose_count": 0,
                "oracle_attempted": False,
            },
        ],
        "benchmark_executed": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def _runtime_payload(
    *,
    oracle_sha: str,
    oracle_file_sha: str,
    wheel_sha: str,
    tag: str,
    scale: int,
    attestation: dict[str, object] | None = None,
) -> dict[str, object]:
    wheel_binding = {"sha256": wheel_sha, "fixture_role": "engine-wheel"}
    case_rows = [
        {
            "case_id": _CASE_IDS[0],
            "oracle_status": "evaluated",
            "selected_pose_count": 1,
            "oracle_attempted": True,
            "wall_duration_ns": 100 * scale,
            "rss_start_bytes": 1_000 * scale,
            "rss_end_bytes": 1_100 * scale,
            "sampled_peak_rss_bytes": 1_200 * scale,
            "rss_sample_count": 3,
        },
        {
            "case_id": _CASE_IDS[1],
            "oracle_status": "blocked_upstream",
            "selected_pose_count": 0,
            "oracle_attempted": False,
            "wall_duration_ns": 200 * scale,
            "rss_start_bytes": 1_100 * scale,
            "rss_end_bytes": 1_150 * scale,
            "sampled_peak_rss_bytes": 1_250 * scale,
            "rss_sample_count": 3,
        },
    ]
    return {
        "schema_id": (
            runtime_module.POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_OBSERVATION_SCHEMA_ID
        ),
        "oracle_receipt_sha256": oracle_sha,
        "oracle_receipt_file_sha256": oracle_file_sha,
        "oracle_runtime_identity_sha256": _canonical_sha("oracle-runtime-identity"),
        "oracle_case_projection_sha256": _canonical_sha(list(_CASE_IDS)),
        "engine_wheel_binding": wheel_binding,
        "engine_wheel_binding_sha256": _canonical_sha(wheel_binding),
        "runtime_environment_sha256": _canonical_sha(f"runtime-environment:{tag}"),
        "all_case_denominator": len(_CASE_IDS),
        "batch_wall_duration_ns": 1_000 * scale,
        "batch_sampled_peak_rss_bytes": 1_300 * scale,
        "batch_rss_sample_count": 10,
        "case_rows": case_rows,
        "execution_attestation": attestation,
        "execution_attestation_sha256": (
            None if attestation is None else _canonical_sha(attestation)
        ),
        "execution_attestation_payload_bound": attestation is not None,
        "benchmark_executed": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def _stratification_payload(
    *,
    oracle_sha: str,
    oracle_file_sha: str,
    runtime_sha: str,
    runtime_file_sha: str,
    runtime_payload: dict[str, object],
    scale: int,
) -> dict[str, object]:
    fixed = {
        "source_dataset_id": "synthetic-posebusters-reproduction",
        "official_cohort_bound": True,
        "archive_intake_receipt_sha256": _canonical_sha("archive-intake"),
        "corpus_audit_receipt_sha256": _canonical_sha("corpus-audit"),
        "preparation_receipt_sha256": _canonical_sha("preparation"),
        "preparation_artifact_set_sha256": _canonical_sha("artifacts"),
        "oracle_receipt_sha256": oracle_sha,
        "oracle_receipt_file_sha256": oracle_file_sha,
        "oracle_runtime_identity_sha256": _canonical_sha("oracle-runtime-identity"),
        "target_cluster_receipt_sha256": _canonical_sha("target-clusters"),
        "target_family_receipt_sha256": _canonical_sha("target-families"),
        "annotation_snapshot_sha256": _canonical_sha("annotation-snapshot"),
        "configuration_sha256": _canonical_sha("strata-configuration"),
        "implementation_source_sha256": _canonical_sha("strata-source"),
    }
    cases = [
        {
            "case_id": _CASE_IDS[0],
            "oracle_status": "evaluated",
            "selected_pose_count": 1,
            "oracle_attempted": True,
            "target_stratum_id": "pfam_set::PF00001",
            "chemistry_stratum_id": "chemistry::neutral-small",
            "target_ood_status": "unknown_no_internal_fit_or_training_manifest",
            "chemistry_ood_status": "admitted_profile_unvalidated",
            "wall_duration_ns": 100 * scale,
            "rss_start_bytes": 1_000 * scale,
            "rss_end_bytes": 1_100 * scale,
            "sampled_peak_rss_bytes": 1_200 * scale,
            "rss_sample_count": 3,
        },
        {
            "case_id": _CASE_IDS[1],
            "oracle_status": "blocked_upstream",
            "selected_pose_count": 0,
            "oracle_attempted": False,
            "target_stratum_id": "pfam_set::PF00001",
            "chemistry_stratum_id": "chemistry::unsupported",
            "target_ood_status": "unknown_no_internal_fit_or_training_manifest",
            "chemistry_ood_status": "unsupported_scope",
            "wall_duration_ns": 200 * scale,
            "rss_start_bytes": 1_100 * scale,
            "rss_end_bytes": 1_150 * scale,
            "sampled_peak_rss_bytes": 1_250 * scale,
            "rss_sample_count": 3,
        },
    ]
    strata = [
        {
            "dimension": "target",
            "stratum_id": "pfam_set::PF00001",
            "stratum_kind": "pfam_set",
            "member_case_count": 2,
            "member_case_ids": list(_CASE_IDS),
            "wall_duration_total_ns": 300 * scale,
            "wall_duration_min_ns": 100 * scale,
            "wall_duration_max_ns": 200 * scale,
            "sampled_peak_rss_max_bytes": 1_250 * scale,
            "rss_sample_count_total": 6,
            "runtime_scope": "downstream_posebusters_oracle_loop_only",
            "sampled_peak_rss_is_additive": False,
        },
        {
            "dimension": "chemistry",
            "stratum_id": "chemistry::neutral-small",
            "stratum_kind": "chemistry_profile",
            "member_case_count": 1,
            "member_case_ids": [_CASE_IDS[0]],
            "wall_duration_total_ns": 100 * scale,
            "wall_duration_min_ns": 100 * scale,
            "wall_duration_max_ns": 100 * scale,
            "sampled_peak_rss_max_bytes": 1_200 * scale,
            "rss_sample_count_total": 3,
            "runtime_scope": "downstream_posebusters_oracle_loop_only",
            "sampled_peak_rss_is_additive": False,
        },
        {
            "dimension": "chemistry",
            "stratum_id": "chemistry::unsupported",
            "stratum_kind": "chemistry_profile",
            "member_case_count": 1,
            "member_case_ids": [_CASE_IDS[1]],
            "wall_duration_total_ns": 200 * scale,
            "wall_duration_min_ns": 200 * scale,
            "wall_duration_max_ns": 200 * scale,
            "sampled_peak_rss_max_bytes": 1_250 * scale,
            "rss_sample_count_total": 3,
            "runtime_scope": "downstream_posebusters_oracle_loop_only",
            "sampled_peak_rss_is_additive": False,
        },
    ]
    metrics = [
        {
            "dimension": row[0],
            "stratum_id": row[1],
            "metric_id": "oracle_complete_case_rate",
            "numerator": row[2],
            "denominator": row[3],
        }
        for row in (
            ("target", "pfam_set::PF00001", 1, 2),
            ("chemistry", "chemistry::neutral-small", 1, 1),
            ("chemistry", "chemistry::unsupported", 0, 1),
        )
    ]
    return {
        "schema_id": (
            strata_module.POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_SCHEMA_ID
        ),
        **fixed,
        "runtime_observation_receipt_sha256": runtime_sha,
        "runtime_observation_receipt_file_sha256": runtime_file_sha,
        "runtime_environment_sha256": runtime_payload["runtime_environment_sha256"],
        "runtime_engine_wheel_binding_sha256": runtime_payload[
            "engine_wheel_binding_sha256"
        ],
        "all_case_denominator": len(_CASE_IDS),
        "case_rows": cases,
        "stratum_rows": strata,
        "metrics": metrics,
        "all_failure_blocked_abstention_rows_retained": True,
        "every_case_has_one_primary_target_stratum": True,
        "every_case_has_one_primary_chemistry_stratum": True,
        "benchmark_executed": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }


def _write_chain(
    root: Path,
    *,
    oracle_source: Path,
    oracle_sha: str,
    oracle_file_sha: str,
    wheel_sha: str,
    tag: str,
    scale: int,
    mutate_strata: bool = False,
    attestation: dict[str, object] | None = None,
) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    oracle_path = root / "oracle.json"
    oracle_path.write_bytes(oracle_source.read_bytes())
    oracle_path.chmod(0o600)
    assert _file_sha(oracle_path) == oracle_file_sha
    runtime_payload = _runtime_payload(
        oracle_sha=oracle_sha,
        oracle_file_sha=oracle_file_sha,
        wheel_sha=wheel_sha,
        tag=tag,
        scale=scale,
        attestation=attestation,
    )
    runtime_path = root / "runtime.json"
    runtime_sha, runtime_file_sha = _write_receipt(runtime_path, runtime_payload)
    strata_payload = _stratification_payload(
        oracle_sha=oracle_sha,
        oracle_file_sha=oracle_file_sha,
        runtime_sha=runtime_sha,
        runtime_file_sha=runtime_file_sha,
        runtime_payload=runtime_payload,
        scale=scale,
    )
    if mutate_strata:
        case_rows = strata_payload["case_rows"]
        assert isinstance(case_rows, list)
        first = case_rows[0]
        assert isinstance(first, dict)
        first["target_stratum_id"] = "pfam_set::PF99999"
    strata_path = root / "strata.json"
    strata_sha, _strata_file_sha = _write_receipt(strata_path, strata_payload)
    return {
        "oracle_receipt_path": oracle_path,
        "runtime_observation_receipt_path": runtime_path,
        "stratification_receipt_path": strata_path,
        "expected_oracle_receipt_sha256": oracle_sha,
        "expected_runtime_observation_receipt_sha256": runtime_sha,
        "expected_stratification_receipt_sha256": strata_sha,
    }


def _fixture(tmp_path: Path) -> dict[str, object]:
    wheel_path, wheel_sha = _wheel(tmp_path / "wheel")
    oracle_path = tmp_path / "source-oracle.json"
    oracle_sha, oracle_file_sha = _write_receipt(oracle_path, _oracle_payload())
    baseline = _write_chain(
        tmp_path / "baseline",
        oracle_source=oracle_path,
        oracle_sha=oracle_sha,
        oracle_file_sha=oracle_file_sha,
        wheel_sha=wheel_sha,
        tag="baseline",
        scale=1,
    )
    external = _write_chain(
        tmp_path / "external",
        oracle_source=oracle_path,
        oracle_sha=oracle_sha,
        oracle_file_sha=oracle_file_sha,
        wheel_sha=wheel_sha,
        tag="external",
        scale=2,
        attestation=_attestation(),
    )
    mismatch = _write_chain(
        tmp_path / "mismatch",
        oracle_source=oracle_path,
        oracle_sha=oracle_sha,
        oracle_file_sha=oracle_file_sha,
        wheel_sha=wheel_sha,
        tag="mismatch",
        scale=3,
        mutate_strata=True,
        attestation=_attestation(),
    )
    unattested = _write_chain(
        tmp_path / "unattested",
        oracle_source=oracle_path,
        oracle_sha=oracle_sha,
        oracle_file_sha=oracle_file_sha,
        wheel_sha=wheel_sha,
        tag="unattested",
        scale=4,
    )
    wrong_nonce = _write_chain(
        tmp_path / "wrong-nonce",
        oracle_source=oracle_path,
        oracle_sha=oracle_sha,
        oracle_file_sha=oracle_file_sha,
        wheel_sha=wheel_sha,
        tag="wrong-nonce",
        scale=5,
        attestation=_attestation(nonce=_canonical_sha("replayed-nonce")),
    )
    return {
        "wheel_path": wheel_path,
        "wheel_sha": wheel_sha,
        "baseline": baseline,
        "external": external,
        "mismatch": mismatch,
        "unattested": unattested,
        "wrong_nonce": wrong_nonce,
    }


def _baseline_arguments(fixture: dict[str, object]) -> dict[str, object]:
    baseline = fixture["baseline"]
    assert isinstance(baseline, dict)
    return {
        "baseline_oracle_receipt_path": baseline["oracle_receipt_path"],
        "baseline_runtime_observation_receipt_path": baseline[
            "runtime_observation_receipt_path"
        ],
        "baseline_stratification_receipt_path": baseline["stratification_receipt_path"],
        "engine_wheel_path": fixture["wheel_path"],
        "expected_baseline_oracle_receipt_sha256": baseline[
            "expected_oracle_receipt_sha256"
        ],
        "expected_baseline_runtime_observation_receipt_sha256": baseline[
            "expected_runtime_observation_receipt_sha256"
        ],
        "expected_baseline_stratification_receipt_sha256": baseline[
            "expected_stratification_receipt_sha256"
        ],
        "expected_engine_wheel_sha256": fixture["wheel_sha"],
    }


def _external_arguments(
    fixture: dict[str, object],
    *,
    name: str = "external",
) -> dict[str, object]:
    external = fixture[name]
    assert isinstance(external, dict)
    return {
        "external_oracle_receipt_path": external["oracle_receipt_path"],
        "external_runtime_observation_receipt_path": external[
            "runtime_observation_receipt_path"
        ],
        "external_stratification_receipt_path": external["stratification_receipt_path"],
        "expected_external_oracle_receipt_sha256": external[
            "expected_oracle_receipt_sha256"
        ],
        "expected_external_runtime_observation_receipt_sha256": external[
            "expected_runtime_observation_receipt_sha256"
        ],
        "expected_external_stratification_receipt_sha256": external[
            "expected_stratification_receipt_sha256"
        ],
    }


def _work_order(
    fixture: dict[str, object],
) -> tuple[object, Path]:
    receipt = materialize_posebusters_internal_oracle_reproduction_work_order(
        **_baseline_arguments(fixture),  # type: ignore[arg-type]
        baseline_host_identity_sha256=_BASELINE_HOST,
        expected_external_host_identity_sha256=_EXTERNAL_HOST,
        work_order_operator_identity_sha256=_WORK_ORDER_OPERATOR,
        external_execution_operator_identity_sha256=_EXTERNAL_EXECUTOR,
        external_execution_nonce_sha256=_EXECUTION_NONCE,
        registered_utc="2026-07-26T01:00:00Z",
    )
    output = Path(fixture["wheel_path"]).parent.parent / "work-order.json"
    receipt.write_json(output)
    return receipt, output


def test_work_order_and_passing_result_reconstruct_exactly_and_stay_claim_closed(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    work_order, work_order_path = _work_order(fixture)
    assert stat.S_IMODE(work_order_path.stat().st_mode) == 0o600
    verified_work_order = verify_posebusters_internal_oracle_reproduction_work_order(
        work_order_path=work_order_path,
        expected_work_order_receipt_sha256=work_order.fingerprint_sha256,
        **_baseline_arguments(fixture),  # type: ignore[arg-type]
    )
    assert verified_work_order.canonical_bytes() == work_order.canonical_bytes()

    result = materialize_posebusters_internal_oracle_reproduction_result(
        work_order_path=work_order_path,
        expected_work_order_receipt_sha256=work_order.fingerprint_sha256,
        **_baseline_arguments(fixture),  # type: ignore[arg-type]
        **_external_arguments(fixture),  # type: ignore[arg-type]
        observed_external_host_identity_sha256=_EXTERNAL_HOST,
        observed_external_execution_operator_identity_sha256=_EXTERNAL_EXECUTOR,
        external_observed_utc="2026-07-26T02:00:00Z",
    )
    payload = result.to_dict()
    assert payload["status"] == "comparison_passed"
    assert payload["cross_host_deterministic_reproduction_pass"] is True
    deterministic = payload["deterministic_comparison"]
    assert isinstance(deterministic, dict)
    assert deterministic["oracle_receipt_exact_match"] is True
    assert deterministic["deterministic_projection_exact_match"] is True
    assert deterministic["all_failure_rows_compared"] is True
    runtime = payload["runtime_comparison"]
    assert isinstance(runtime, dict)
    assert runtime["runtime_observation_receipts_distinct"] is True
    assert runtime["runtime_measurement_values_exact_match"] is False
    assert runtime["runtime_measurement_values_exact_match_required"] is False
    assert runtime["runtime_performance_equivalence_threshold_defined"] is False
    assert (
        runtime["batch_wall_duration_ratio_external_over_baseline_binary64_hex"]
        == float(2.0).hex()
    )
    assert payload["runtime_observation_nonce_payload_bound"] is True
    assert payload["external_observation_time_payload_bound"] is True
    assert payload["upstream_receipt_signatures_verified"] is False
    assert payload["physical_host_independence_reviewed"] is False
    assert payload["independent_external_rerun_present"] is False
    assert payload["benchmark_executed"] is False
    assert payload["claim_safe"] is False

    result_path = tmp_path / "result.json"
    result.write_json(result_path)
    verified_result = verify_posebusters_internal_oracle_reproduction_result(
        result_path=result_path,
        expected_result_receipt_sha256=result.fingerprint_sha256,
        work_order_path=work_order_path,
        expected_work_order_receipt_sha256=work_order.fingerprint_sha256,
        **_baseline_arguments(fixture),  # type: ignore[arg-type]
        **_external_arguments(fixture),  # type: ignore[arg-type]
    )
    assert verified_result.canonical_bytes() == result.canonical_bytes()
    with pytest.raises(
        PoseBustersInternalOracleReproductionError,
        match="already exists",
    ):
        result.write_json(result_path)


def test_deterministic_case_mismatch_is_failure_inclusive(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    work_order, work_order_path = _work_order(fixture)
    result = materialize_posebusters_internal_oracle_reproduction_result(
        work_order_path=work_order_path,
        expected_work_order_receipt_sha256=work_order.fingerprint_sha256,
        **_baseline_arguments(fixture),  # type: ignore[arg-type]
        **_external_arguments(fixture, name="mismatch"),  # type: ignore[arg-type]
        observed_external_host_identity_sha256=_EXTERNAL_HOST,
        observed_external_execution_operator_identity_sha256=_EXTERNAL_EXECUTOR,
        external_observed_utc="2026-07-26T02:00:00Z",
    ).to_dict()
    assert result["status"] == "comparison_failed"
    assert result["cross_host_deterministic_reproduction_pass"] is False
    comparison = result["deterministic_comparison"]
    assert isinstance(comparison, dict)
    assert comparison["mismatched_case_ids"] == [_CASE_IDS[0]]
    assert comparison["all_failure_rows_compared"] is True


def test_baseline_runtime_replay_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    work_order, work_order_path = _work_order(fixture)
    baseline = fixture["baseline"]
    assert isinstance(baseline, dict)
    replay = {
        "external_oracle_receipt_path": baseline["oracle_receipt_path"],
        "external_runtime_observation_receipt_path": baseline[
            "runtime_observation_receipt_path"
        ],
        "external_stratification_receipt_path": baseline["stratification_receipt_path"],
        "expected_external_oracle_receipt_sha256": baseline[
            "expected_oracle_receipt_sha256"
        ],
        "expected_external_runtime_observation_receipt_sha256": baseline[
            "expected_runtime_observation_receipt_sha256"
        ],
        "expected_external_stratification_receipt_sha256": baseline[
            "expected_stratification_receipt_sha256"
        ],
    }
    with pytest.raises(
        PoseBustersInternalOracleReproductionError,
        match="reuses the baseline receipt",
    ):
        materialize_posebusters_internal_oracle_reproduction_result(
            work_order_path=work_order_path,
            expected_work_order_receipt_sha256=work_order.fingerprint_sha256,
            **_baseline_arguments(fixture),  # type: ignore[arg-type]
            **replay,  # type: ignore[arg-type]
            observed_external_host_identity_sha256=_EXTERNAL_HOST,
            observed_external_execution_operator_identity_sha256=(_EXTERNAL_EXECUTOR),
            external_observed_utc="2026-07-26T02:00:00Z",
        )


def test_unattested_external_runtime_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    work_order, work_order_path = _work_order(fixture)
    with pytest.raises(
        PoseBustersInternalOracleReproductionError,
        match="does not payload-bind an execution attestation",
    ):
        materialize_posebusters_internal_oracle_reproduction_result(
            work_order_path=work_order_path,
            expected_work_order_receipt_sha256=work_order.fingerprint_sha256,
            **_baseline_arguments(fixture),  # type: ignore[arg-type]
            **_external_arguments(fixture, name="unattested"),  # type: ignore[arg-type]
            observed_external_host_identity_sha256=_EXTERNAL_HOST,
            observed_external_execution_operator_identity_sha256=(_EXTERNAL_EXECUTOR),
            external_observed_utc="2026-07-26T02:00:00Z",
        )


def test_replayed_attestation_nonce_is_rejected(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    work_order, work_order_path = _work_order(fixture)
    with pytest.raises(
        PoseBustersInternalOracleReproductionError,
        match="does not bind the preregistered",
    ):
        materialize_posebusters_internal_oracle_reproduction_result(
            work_order_path=work_order_path,
            expected_work_order_receipt_sha256=work_order.fingerprint_sha256,
            **_baseline_arguments(fixture),  # type: ignore[arg-type]
            **_external_arguments(fixture, name="wrong_nonce"),  # type: ignore[arg-type]
            observed_external_host_identity_sha256=_EXTERNAL_HOST,
            observed_external_execution_operator_identity_sha256=(_EXTERNAL_EXECUTOR),
            external_observed_utc="2026-07-26T02:00:00Z",
        )


@pytest.mark.parametrize(
    ("host", "executor", "observed_utc", "message"),
    (
        (
            _canonical_sha("wrong-host"),
            _EXTERNAL_EXECUTOR,
            "2026-07-26T02:00:00Z",
            "not preregistered",
        ),
        (
            _EXTERNAL_HOST,
            _canonical_sha("wrong-executor"),
            "2026-07-26T02:00:00Z",
            "not preregistered",
        ),
        (_EXTERNAL_HOST, _EXTERNAL_EXECUTOR, "2026-07-26T01:00:00Z", "must follow"),
    ),
)
def test_result_requires_preregistered_roles_and_later_observation(
    tmp_path: Path,
    host: str,
    executor: str,
    observed_utc: str,
    message: str,
) -> None:
    fixture = _fixture(tmp_path)
    work_order, work_order_path = _work_order(fixture)
    with pytest.raises(PoseBustersInternalOracleReproductionError, match=message):
        materialize_posebusters_internal_oracle_reproduction_result(
            work_order_path=work_order_path,
            expected_work_order_receipt_sha256=work_order.fingerprint_sha256,
            **_baseline_arguments(fixture),  # type: ignore[arg-type]
            **_external_arguments(fixture),  # type: ignore[arg-type]
            observed_external_host_identity_sha256=host,
            observed_external_execution_operator_identity_sha256=executor,
            external_observed_utc=observed_utc,
        )


def test_work_order_rejects_identity_role_reuse(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    with pytest.raises(
        PoseBustersInternalOracleReproductionError,
        match="role-separated",
    ):
        materialize_posebusters_internal_oracle_reproduction_work_order(
            **_baseline_arguments(fixture),  # type: ignore[arg-type]
            baseline_host_identity_sha256=_BASELINE_HOST,
            expected_external_host_identity_sha256=_BASELINE_HOST,
            work_order_operator_identity_sha256=_WORK_ORDER_OPERATOR,
            external_execution_operator_identity_sha256=_EXTERNAL_EXECUTOR,
            external_execution_nonce_sha256=_EXECUTION_NONCE,
            registered_utc="2026-07-26T01:00:00Z",
        )


def test_wheel_requires_reproduction_entrypoint(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    wheel_path, wheel_sha = _wheel(
        tmp_path / "missing-entrypoint",
        include_reproduction_entrypoint=False,
    )
    arguments = _baseline_arguments(fixture)
    arguments["engine_wheel_path"] = wheel_path
    arguments["expected_engine_wheel_sha256"] = wheel_sha
    with pytest.raises(
        PoseBustersInternalOracleReproductionError,
        match="missing a required reproduction entry point",
    ):
        materialize_posebusters_internal_oracle_reproduction_work_order(
            **arguments,  # type: ignore[arg-type]
            baseline_host_identity_sha256=_BASELINE_HOST,
            expected_external_host_identity_sha256=_EXTERNAL_HOST,
            work_order_operator_identity_sha256=_WORK_ORDER_OPERATOR,
            external_execution_operator_identity_sha256=_EXTERNAL_EXECUTOR,
            external_execution_nonce_sha256=_EXECUTION_NONCE,
            registered_utc="2026-07-26T01:00:00Z",
        )


def _chain_signature(
    chain: dict[str, object],
    *,
    signing_key: bytes,
    signer_identity: str,
    signed_at_utc: str = "2026-07-26T03:00:00Z",
) -> dict[str, object]:
    payload = posebusters_internal_oracle_chain_signing_payload(
        oracle_receipt_sha256=chain["expected_oracle_receipt_sha256"],  # type: ignore[arg-type]
        runtime_observation_receipt_sha256=chain[  # type: ignore[arg-type]
            "expected_runtime_observation_receipt_sha256"
        ],
        stratification_receipt_sha256=chain[  # type: ignore[arg-type]
            "expected_stratification_receipt_sha256"
        ],
        signer_identity_sha256=signer_identity,
        signed_at_utc=signed_at_utc,
    )
    return {
        "signed_at_utc": signed_at_utc,
        "signed_payload": payload,
        "signature": {
            "algorithm": "ed25519",
            "value": sign_ed25519(
                posebusters_internal_oracle_chain_signing_bytes(payload),
                signing_key,
            ),
        },
    }


def test_verified_chain_signatures_close_the_signature_blocker(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    work_order, work_order_path = _work_order(fixture)
    signing_key = hashlib.sha256(b"chain-custodian-signing-key").digest()
    signer_identity = _canonical_sha("chain-custodian")
    anchor = PoseBustersInternalOracleChainTrustAnchor(
        signer_identity_sha256=signer_identity,
        verification_key=ed25519_public_key_bytes(signing_key),
    )
    baseline = fixture["baseline"]
    external = fixture["external"]
    assert isinstance(baseline, dict)
    assert isinstance(external, dict)
    signatures = {
        "baseline_chain_signature": _chain_signature(
            baseline,
            signing_key=signing_key,
            signer_identity=signer_identity,
        ),
        "external_chain_signature": _chain_signature(
            external,
            signing_key=signing_key,
            signer_identity=signer_identity,
        ),
        "chain_trust_anchor": anchor,
    }
    result = materialize_posebusters_internal_oracle_reproduction_result(
        work_order_path=work_order_path,
        expected_work_order_receipt_sha256=work_order.fingerprint_sha256,
        **_baseline_arguments(fixture),  # type: ignore[arg-type]
        **_external_arguments(fixture),  # type: ignore[arg-type]
        observed_external_host_identity_sha256=_EXTERNAL_HOST,
        observed_external_execution_operator_identity_sha256=(_EXTERNAL_EXECUTOR),
        external_observed_utc="2026-07-26T02:00:00Z",
        **signatures,  # type: ignore[arg-type]
    )
    payload = result.to_dict()
    assert payload["upstream_receipt_signatures_verified"] is True
    blockers = payload["scientific_blockers"]
    assert isinstance(blockers, list)
    assert (
        "upstream_runtime_and_stratification_receipts_are_unsigned_self_hash_only"
        not in blockers
    )
    assert "physical_host_identity_is_not_cryptographically_proven" in blockers
    baseline_signature = payload["baseline_chain_signature"]
    assert isinstance(baseline_signature, dict)
    assert baseline_signature["signature_verified"] is True
    assert baseline_signature["signer_custody_independently_reviewed"] is False
    assert payload["physical_host_independence_reviewed"] is False
    assert payload["independent_external_rerun_present"] is False
    assert payload["benchmark_executed"] is False
    assert payload["claim_safe"] is False

    result_path = tmp_path / "signed-result.json"
    result.write_json(result_path)
    verified = verify_posebusters_internal_oracle_reproduction_result(
        result_path=result_path,
        expected_result_receipt_sha256=result.fingerprint_sha256,
        work_order_path=work_order_path,
        expected_work_order_receipt_sha256=work_order.fingerprint_sha256,
        **_baseline_arguments(fixture),  # type: ignore[arg-type]
        **_external_arguments(fixture),  # type: ignore[arg-type]
        chain_trust_anchor=anchor,
    )
    assert verified.canonical_bytes() == result.canonical_bytes()


def test_chain_signature_from_untrusted_key_fails_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    work_order, work_order_path = _work_order(fixture)
    signing_key = hashlib.sha256(b"attacker-signing-key").digest()
    signer_identity = _canonical_sha("chain-custodian")
    anchor = PoseBustersInternalOracleChainTrustAnchor(
        signer_identity_sha256=signer_identity,
        verification_key=ed25519_public_key_bytes(
            hashlib.sha256(b"chain-custodian-signing-key").digest()
        ),
    )
    baseline = fixture["baseline"]
    external = fixture["external"]
    assert isinstance(baseline, dict)
    assert isinstance(external, dict)
    with pytest.raises(
        PoseBustersInternalOracleReproductionError,
        match="chain signature verification failed",
    ):
        materialize_posebusters_internal_oracle_reproduction_result(
            work_order_path=work_order_path,
            expected_work_order_receipt_sha256=work_order.fingerprint_sha256,
            **_baseline_arguments(fixture),  # type: ignore[arg-type]
            **_external_arguments(fixture),  # type: ignore[arg-type]
            observed_external_host_identity_sha256=_EXTERNAL_HOST,
            observed_external_execution_operator_identity_sha256=(
                _EXTERNAL_EXECUTOR
            ),
            external_observed_utc="2026-07-26T02:00:00Z",
            baseline_chain_signature=_chain_signature(
                baseline,
                signing_key=signing_key,
                signer_identity=signer_identity,
            ),
            external_chain_signature=_chain_signature(
                external,
                signing_key=signing_key,
                signer_identity=signer_identity,
            ),
            chain_trust_anchor=anchor,
        )


def test_chain_signature_requires_a_trust_anchor(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    work_order, work_order_path = _work_order(fixture)
    baseline = fixture["baseline"]
    assert isinstance(baseline, dict)
    with pytest.raises(
        PoseBustersInternalOracleReproductionError,
        match="requires both signatures and a trust anchor",
    ):
        materialize_posebusters_internal_oracle_reproduction_result(
            work_order_path=work_order_path,
            expected_work_order_receipt_sha256=work_order.fingerprint_sha256,
            **_baseline_arguments(fixture),  # type: ignore[arg-type]
            **_external_arguments(fixture),  # type: ignore[arg-type]
            observed_external_host_identity_sha256=_EXTERNAL_HOST,
            observed_external_execution_operator_identity_sha256=(
                _EXTERNAL_EXECUTOR
            ),
            external_observed_utc="2026-07-26T02:00:00Z",
            baseline_chain_signature=_chain_signature(
                baseline,
                signing_key=hashlib.sha256(b"chain-custodian-signing-key").digest(),
                signer_identity=_canonical_sha("chain-custodian"),
            ),
        )


def test_cli_help_describes_second_host_claim_boundary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="0"):
        reproduction.main(["--help"])
    output = capsys.readouterr().out
    assert "second-host internal PoseBusters-oracle" in output
    assert "physical-host independence claim-closed" in output
