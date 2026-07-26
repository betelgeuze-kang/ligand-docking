"""Preregister and compare a second-host internal-oracle rerun.

The deterministic internal PoseBusters oracle should be byte-identical across
hosts.  Runtime and sampled RSS values deliberately are not.  This module
therefore compares an exact oracle identity and a runtime-free projection of
the target/chemistry stratification receipt while retaining the two measured
runtime receipts as distinct observations.

Host/operator identities and a single-use nonce are preregistered, but the
current upstream runtime receipt does not cryptographically bind that nonce or
prove a physical host.  A passing comparison consequently remains claim-closed
until an independent reviewer validates custody, host independence, and nonce
single use.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import argparse
import configparser
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from typing import Any
import zipfile

from . import public_posebusters_internal_oracle_evaluation as oracle_module
from . import public_posebusters_internal_oracle_runtime_observation as runtime_module
from . import public_posebusters_internal_oracle_stratification as strata_module
from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _source_file_sha256,
)
from .public_posebusters_generated_pose_evaluation import _case_id
from .public_posebusters_intake import (
    PoseBustersArchiveIntakeError,
    _read_exact_regular_file,
)


POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_WORK_ORDER_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_oracle_reproduction_work_order/1.0.0"
)
POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_DETERMINISTIC_COMPARISON_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_oracle_deterministic_comparison/1.0.0"
)
POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_RUNTIME_COMPARISON_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_oracle_runtime_comparison/1.0.0"
)
POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_internal_oracle_reproduction_result/1.0.0"
)

POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_INPUT_BYTES = 64 * 1024 * 1024
POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_WORK_ORDER_BYTES = 8 * 1024 * 1024
POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_RESULT_BYTES = 32 * 1024 * 1024
POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_WHEEL_BYTES = 16 * 1024 * 1024
POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_WHEEL_MEMBERS = 4096

_REQUIRED_ENTRYPOINTS = (
    "betelgeuze-engine-v2-posebusters-internal-oracle",
    "betelgeuze-engine-v2-posebusters-internal-oracle-runtime",
    "betelgeuze-engine-v2-posebusters-internal-oracle-strata",
    "betelgeuze-engine-v2-posebusters-internal-oracle-reproduce",
)
_FIXED_STRATA_BINDING_FIELDS = (
    "source_dataset_id",
    "official_cohort_bound",
    "archive_intake_receipt_sha256",
    "corpus_audit_receipt_sha256",
    "preparation_receipt_sha256",
    "preparation_artifact_set_sha256",
    "oracle_receipt_sha256",
    "oracle_receipt_file_sha256",
    "oracle_runtime_identity_sha256",
    "target_cluster_receipt_sha256",
    "target_family_receipt_sha256",
    "annotation_snapshot_sha256",
    "configuration_sha256",
    "implementation_source_sha256",
)
_CASE_RUNTIME_FIELDS = frozenset(
    {
        "wall_duration_ns",
        "rss_start_bytes",
        "rss_end_bytes",
        "sampled_peak_rss_bytes",
        "rss_sample_count",
    }
)
_STRATUM_RUNTIME_FIELDS = frozenset(
    {
        "wall_duration_total_ns",
        "wall_duration_min_ns",
        "wall_duration_max_ns",
        "sampled_peak_rss_max_bytes",
        "rss_sample_count_total",
        "runtime_scope",
        "sampled_peak_rss_is_additive",
    }
)

POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_CONFIGURATION = {
    "deterministic_oracle_policy": "exact_receipt_sha256_equality",
    "deterministic_stratification_policy": (
        "exact_runtime_free_case_stratum_metric_projection_equality"
    ),
    "failure_policy": "compare_every_case_including_failure_blocked_abstention",
    "fresh_runtime_policy": "external_runtime_and_strata_receipt_roots_distinct",
    "upstream_receipt_policy": "canonical_self_hash_only_review_required",
    "host_policy": {
        "baseline_and_external_host_identities_preregistered": True,
        "baseline_and_external_host_identities_distinct": True,
        "operator_and_executor_identities_role_separated": True,
        "single_use_external_execution_nonce_preregistered": True,
        "external_observation_time_payload_bound": False,
        "physical_host_independence_requires_external_review": True,
        "nonce_single_use_requires_external_registry_review": True,
    },
    "runtime_policy": {
        "batch_duration_and_sampled_rss_ratios_reported": True,
        "exact_runtime_value_equality_required": False,
        "performance_equivalence_threshold_defined": False,
        "per_case_scope": "downstream_posebusters_oracle_loop_only",
    },
    "claim_policy": {
        "same_host_exact_verification_is_independent_rerun": False,
        "passing_unreviewed_comparison_authorizes_claim": False,
    },
    "required_entrypoints": list(_REQUIRED_ENTRYPOINTS),
}
POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_CONFIGURATION_SHA256 = _canonical_sha256(
    POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_CONFIGURATION
)

POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_SCIENTIFIC_BLOCKERS = (
    "upstream_runtime_and_stratification_receipts_are_unsigned_self_hash_only",
    "runtime_observation_nonce_is_not_payload_bound",
    "external_observation_time_is_not_runtime_payload_bound",
    "physical_host_identity_is_not_cryptographically_proven",
    "physical_host_independence_review_missing",
    "external_execution_nonce_single_use_registry_review_missing",
    "runtime_measurements_are_not_byte_reproducible",
    "runtime_performance_equivalence_threshold_not_defined",
    "independent_scientific_review_missing",
    "public_result_bundle_validation_missing",
    "public_docking_benchmark_claim_not_authorized",
)

_WORK_ORDER_FLAGS = {
    "external_execution_observed": False,
    "cross_host_comparison_present": False,
    "runtime_observation_nonce_payload_bound": False,
    "external_observation_time_payload_bound": False,
    "upstream_receipt_signatures_verified": False,
    "physical_host_independence_reviewed": False,
    "independent_external_rerun_present": False,
    "independent_reviewer_receipt_approved": False,
    "benchmark_executed": False,
    "scientifically_validated": False,
    "claim_safe": False,
}
_RESULT_FLAGS = {
    "external_execution_observed": True,
    "cross_host_comparison_present": True,
    "runtime_observation_nonce_payload_bound": False,
    "external_observation_time_payload_bound": False,
    "upstream_receipt_signatures_verified": False,
    "physical_host_independence_reviewed": False,
    "independent_external_rerun_present": False,
    "independent_reviewer_receipt_approved": False,
    "benchmark_executed": False,
    "scientifically_validated": False,
    "claim_safe": False,
}
_LOWERCASE_SHA256 = frozenset("0123456789abcdef")


class PoseBustersInternalOracleReproductionError(ValueError):
    """A work order, source chain, comparison, or result is invalid."""


class _LoadedReceipt:
    __slots__ = ("file_sha256", "payload", "receipt_sha256", "source")

    def __init__(
        self,
        *,
        payload: dict[str, Any],
        receipt_sha256: str,
        file_sha256: str,
        source: bytes,
    ) -> None:
        self.payload = payload
        self.receipt_sha256 = receipt_sha256
        self.file_sha256 = file_sha256
        self.source = source


class _InternalOracleChain:
    __slots__ = ("case_ids", "oracle", "runtime", "strata")

    def __init__(
        self,
        *,
        oracle: _LoadedReceipt,
        runtime: _LoadedReceipt,
        strata: _LoadedReceipt,
        case_ids: tuple[str, ...],
    ) -> None:
        self.oracle = oracle
        self.runtime = runtime
        self.strata = strata
        self.case_ids = case_ids


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PoseBustersInternalOracleReproductionError(f"{name} must be a mapping")
    return dict(value)


def _list(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PoseBustersInternalOracleReproductionError(f"{name} must be a list")
    return value


def _text(value: object, *, name: str, maximum: int = 512) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > maximum
        or any(character in "\r\n\x00" for character in value)
    ):
        raise PoseBustersInternalOracleReproductionError(
            f"{name} must be bounded single-line text"
        )
    return value


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _LOWERCASE_SHA256 for character in value)
    ):
        raise PoseBustersInternalOracleReproductionError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _integer(value: object, *, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise PoseBustersInternalOracleReproductionError(
            f"{name} must be an integer >= {minimum}"
        )
    return value


def _boolean(value: object, *, name: str) -> bool:
    if type(value) is not bool:
        raise PoseBustersInternalOracleReproductionError(f"{name} must be boolean")
    return value


def _utc(value: object, *, name: str) -> str:
    text = _text(value, name=name, maximum=32)
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise PoseBustersInternalOracleReproductionError(
            f"{name} must use canonical UTC seconds"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != text:
        raise PoseBustersInternalOracleReproductionError(
            f"{name} must use canonical UTC seconds"
        )
    return text


def _utc_datetime(value: object, *, name: str) -> datetime:
    return datetime.strptime(_utc(value, name=name), "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )


def _json_object_pairs(pairs: Sequence[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PoseBustersInternalOracleReproductionError(
                "receipt contains a duplicate JSON key"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise PoseBustersInternalOracleReproductionError(
        f"receipt contains forbidden JSON constant {value}"
    )


def _load_receipt(
    path: str | os.PathLike[str],
    *,
    expected_schema_id: str,
    expected_receipt_sha256: str,
    maximum_bytes: int = POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_INPUT_BYTES,
) -> _LoadedReceipt:
    expected = _digest(expected_receipt_sha256, name="expected receipt")
    try:
        source = _read_exact_regular_file(path, maximum_bytes=maximum_bytes)
        metadata = Path(path).stat(follow_symlinks=False)
    except (OSError, PoseBustersArchiveIntakeError) as exc:
        raise PoseBustersInternalOracleReproductionError(
            "receipt could not be read securely"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersInternalOracleReproductionError(
            "receipt must be a bounded mode-0600 regular file"
        )
    try:
        raw = json.loads(
            source.decode("ascii"),
            object_pairs_hook=_json_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except PoseBustersInternalOracleReproductionError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersInternalOracleReproductionError(
            "receipt is not canonical ASCII JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersInternalOracleReproductionError(
            "receipt bytes are not canonical"
        )
    payload = dict(raw)
    receipt_sha = _digest(payload.pop("receipt_sha256", None), name="receipt")
    if (
        raw.get("schema_id") != expected_schema_id
        or _canonical_sha256(payload) != receipt_sha
        or receipt_sha != expected
    ):
        raise PoseBustersInternalOracleReproductionError(
            "receipt schema, digest, or pin is invalid"
        )
    return _LoadedReceipt(
        payload=raw,
        receipt_sha256=receipt_sha,
        file_sha256=hashlib.sha256(source).hexdigest(),
        source=source,
    )


def _claim_closed(payload: Mapping[str, Any], *, name: str) -> None:
    for field in ("benchmark_executed", "scientifically_validated", "claim_safe"):
        if payload.get(field) is not False:
            raise PoseBustersInternalOracleReproductionError(
                f"{name} must keep {field}=false"
            )


def _case_rows(payload: Mapping[str, Any], *, name: str) -> tuple[dict[str, Any], ...]:
    rows = tuple(
        _mapping(item, name=f"{name} case row")
        for item in _list(payload.get("case_rows"), name=f"{name} case rows")
    )
    case_ids = tuple(_case_id(row.get("case_id")) for row in rows)
    if (
        not rows
        or len(rows)
        > strata_module.POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_MAX_CASES
        or case_ids != tuple(sorted(case_ids))
        or len(set(case_ids)) != len(case_ids)
        or payload.get("all_case_denominator") != len(rows)
    ):
        raise PoseBustersInternalOracleReproductionError(
            f"{name} case projection is invalid"
        )
    return rows


def _load_internal_chain(
    oracle_receipt_path: str | os.PathLike[str],
    runtime_observation_receipt_path: str | os.PathLike[str],
    stratification_receipt_path: str | os.PathLike[str],
    *,
    expected_oracle_receipt_sha256: str,
    expected_runtime_observation_receipt_sha256: str,
    expected_stratification_receipt_sha256: str,
) -> _InternalOracleChain:
    oracle = _load_receipt(
        oracle_receipt_path,
        expected_schema_id=oracle_module.POSEBUSTERS_INTERNAL_ORACLE_EVALUATION_SCHEMA_ID,
        expected_receipt_sha256=expected_oracle_receipt_sha256,
        maximum_bytes=oracle_module.POSEBUSTERS_INTERNAL_ORACLE_MAX_RECEIPT_BYTES,
    )
    runtime = _load_receipt(
        runtime_observation_receipt_path,
        expected_schema_id=(
            runtime_module.POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_OBSERVATION_SCHEMA_ID
        ),
        expected_receipt_sha256=expected_runtime_observation_receipt_sha256,
        maximum_bytes=runtime_module.POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_MAX_RECEIPT_BYTES,
    )
    strata = _load_receipt(
        stratification_receipt_path,
        expected_schema_id=(
            strata_module.POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_SCHEMA_ID
        ),
        expected_receipt_sha256=expected_stratification_receipt_sha256,
        maximum_bytes=(
            strata_module.POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_MAX_RECEIPT_BYTES
        ),
    )
    _claim_closed(oracle.payload, name="oracle receipt")
    _claim_closed(runtime.payload, name="runtime receipt")
    _claim_closed(strata.payload, name="stratification receipt")
    oracle_rows = _case_rows(oracle.payload, name="oracle")
    runtime_rows = _case_rows(runtime.payload, name="runtime")
    strata_rows = _case_rows(strata.payload, name="stratification")
    oracle_projection = tuple(
        (
            row["case_id"],
            row.get("status"),
            row.get("selected_pose_count"),
            row.get("oracle_attempted"),
        )
        for row in oracle_rows
    )
    runtime_projection = tuple(
        (
            row["case_id"],
            row.get("oracle_status"),
            row.get("selected_pose_count"),
            row.get("oracle_attempted"),
        )
        for row in runtime_rows
    )
    strata_projection = tuple(
        (
            row["case_id"],
            row.get("oracle_status"),
            row.get("selected_pose_count"),
            row.get("oracle_attempted"),
        )
        for row in strata_rows
    )
    case_ids = tuple(row[0] for row in oracle_projection)
    wheel_binding = _mapping(
        runtime.payload.get("engine_wheel_binding"),
        name="runtime wheel binding",
    )
    if (
        runtime_projection != oracle_projection
        or strata_projection != oracle_projection
        or runtime.payload.get("oracle_receipt_sha256") != oracle.receipt_sha256
        or runtime.payload.get("oracle_receipt_file_sha256") != oracle.file_sha256
        or runtime.payload.get("oracle_runtime_identity_sha256")
        != oracle.payload.get("runtime_identity_sha256")
        or runtime.payload.get("oracle_case_projection_sha256")
        != _canonical_sha256(list(case_ids))
        or strata.payload.get("oracle_receipt_sha256") != oracle.receipt_sha256
        or strata.payload.get("oracle_receipt_file_sha256") != oracle.file_sha256
        or strata.payload.get("runtime_observation_receipt_sha256")
        != runtime.receipt_sha256
        or strata.payload.get("runtime_observation_receipt_file_sha256")
        != runtime.file_sha256
        or strata.payload.get("runtime_environment_sha256")
        != runtime.payload.get("runtime_environment_sha256")
        or strata.payload.get("runtime_engine_wheel_binding_sha256")
        != runtime.payload.get("engine_wheel_binding_sha256")
        or strata.payload.get("oracle_runtime_identity_sha256")
        != runtime.payload.get("oracle_runtime_identity_sha256")
        or wheel_binding.get("sha256") is None
    ):
        raise PoseBustersInternalOracleReproductionError(
            "oracle, runtime, and stratification receipts are cross-wired"
        )
    return _InternalOracleChain(
        oracle=oracle,
        runtime=runtime,
        strata=strata,
        case_ids=case_ids,
    )


def _case_semantic_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in _CASE_RUNTIME_FIELDS}


def _stratum_semantic_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in row.items() if key not in _STRATUM_RUNTIME_FIELDS
    }


def _deterministic_projection(strata: Mapping[str, Any]) -> dict[str, Any]:
    cases = [
        _case_semantic_projection(_mapping(row, name="stratification case"))
        for row in _list(strata.get("case_rows"), name="stratification cases")
    ]
    stratum_rows = [
        _stratum_semantic_projection(_mapping(row, name="stratum row"))
        for row in _list(strata.get("stratum_rows"), name="stratum rows")
    ]
    metrics = [
        _mapping(row, name="stratum metric")
        for row in _list(strata.get("metrics"), name="stratification metrics")
    ]
    return {
        "fixed_bindings": {
            field: strata.get(field) for field in _FIXED_STRATA_BINDING_FIELDS
        },
        "all_case_denominator": strata.get("all_case_denominator"),
        "case_rows": cases,
        "stratum_rows": stratum_rows,
        "metrics": metrics,
        "all_failure_blocked_abstention_rows_retained": strata.get(
            "all_failure_blocked_abstention_rows_retained"
        ),
        "every_case_has_one_primary_target_stratum": strata.get(
            "every_case_has_one_primary_target_stratum"
        ),
        "every_case_has_one_primary_chemistry_stratum": strata.get(
            "every_case_has_one_primary_chemistry_stratum"
        ),
    }


def _chain_binding(chain: _InternalOracleChain) -> dict[str, Any]:
    projection = _deterministic_projection(chain.strata.payload)
    return {
        "oracle_receipt": {
            "schema_id": chain.oracle.payload["schema_id"],
            "receipt_sha256": chain.oracle.receipt_sha256,
            "file_sha256": chain.oracle.file_sha256,
        },
        "runtime_observation_receipt": {
            "schema_id": chain.runtime.payload["schema_id"],
            "receipt_sha256": chain.runtime.receipt_sha256,
            "file_sha256": chain.runtime.file_sha256,
        },
        "stratification_receipt": {
            "schema_id": chain.strata.payload["schema_id"],
            "receipt_sha256": chain.strata.receipt_sha256,
            "file_sha256": chain.strata.file_sha256,
        },
        "deterministic_projection_sha256": _canonical_sha256(projection),
        "all_case_denominator": len(chain.case_ids),
        "case_id_projection_sha256": _canonical_sha256(list(chain.case_ids)),
        "runtime_environment_sha256": chain.runtime.payload[
            "runtime_environment_sha256"
        ],
        "runtime_engine_wheel_binding_sha256": chain.runtime.payload[
            "engine_wheel_binding_sha256"
        ],
    }


def _source_members() -> tuple[tuple[str, str, str], ...]:
    paths = (
        (
            "posebusters_internal_oracle_reproduction",
            Path(__file__).resolve(),
            "betelgeuze_engine_v2/benchmark/"
            "public_posebusters_internal_oracle_reproduction.py",
        ),
        (
            "posebusters_internal_oracle_evaluation",
            Path(oracle_module.__file__).resolve(),
            "betelgeuze_engine_v2/benchmark/"
            "public_posebusters_internal_oracle_evaluation.py",
        ),
        (
            "posebusters_internal_oracle_runtime_observation",
            Path(runtime_module.__file__).resolve(),
            "betelgeuze_engine_v2/benchmark/"
            "public_posebusters_internal_oracle_runtime_observation.py",
        ),
        (
            "posebusters_internal_oracle_stratification",
            Path(strata_module.__file__).resolve(),
            "betelgeuze_engine_v2/benchmark/"
            "public_posebusters_internal_oracle_stratification.py",
        ),
    )
    return tuple(
        (role, _source_file_sha256(path), wheel_path)
        for role, path, wheel_path in paths
    )


def _regular_file(
    path: str | os.PathLike[str],
    *,
    maximum_bytes: int,
    name: str,
) -> tuple[Path, bytes, str]:
    candidate = Path(path)
    try:
        metadata = candidate.stat(follow_symlinks=False)
    except OSError as exc:
        raise PoseBustersInternalOracleReproductionError(
            f"{name} cannot be inspected"
        ) from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_size <= 0
        or metadata.st_size > maximum_bytes
    ):
        raise PoseBustersInternalOracleReproductionError(
            f"{name} must be a bounded non-empty regular file"
        )
    try:
        source = candidate.read_bytes()
    except OSError as exc:
        raise PoseBustersInternalOracleReproductionError(
            f"{name} cannot be read"
        ) from exc
    if len(source) != metadata.st_size:
        raise PoseBustersInternalOracleReproductionError(
            f"{name} changed while being read"
        )
    return candidate, source, hashlib.sha256(source).hexdigest()


def _wheel_binding(
    wheel_path: str | os.PathLike[str],
    *,
    expected_wheel_sha256: str,
) -> dict[str, Any]:
    candidate, source, observed_sha = _regular_file(
        wheel_path,
        maximum_bytes=POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_WHEEL_BYTES,
        name="Engine v2 wheel",
    )
    if observed_sha != _digest(expected_wheel_sha256, name="expected wheel"):
        raise PoseBustersInternalOracleReproductionError(
            "Engine v2 wheel digest changed"
        )
    expected_members = _source_members()
    try:
        with zipfile.ZipFile(candidate) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len(
                members
            ) > POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_WHEEL_MEMBERS or len(
                names
            ) != len(set(names)):
                raise PoseBustersInternalOracleReproductionError(
                    "Engine v2 wheel member ledger is invalid"
                )
            for name in names:
                pure = PurePosixPath(name)
                if pure.is_absolute() or ".." in pure.parts:
                    raise PoseBustersInternalOracleReproductionError(
                        "Engine v2 wheel contains an unsafe member path"
                    )
            bound_members = []
            for role, expected_sha, member_path in expected_members:
                try:
                    member_source = archive.read(member_path)
                except KeyError as exc:
                    raise PoseBustersInternalOracleReproductionError(
                        "Engine v2 wheel is missing a reproduction source member"
                    ) from exc
                member_sha = hashlib.sha256(member_source).hexdigest()
                if member_sha != expected_sha:
                    raise PoseBustersInternalOracleReproductionError(
                        "Engine v2 wheel source differs from active implementation"
                    )
                bound_members.append(
                    {
                        "role": role,
                        "wheel_member_path": member_path,
                        "sha256": member_sha,
                        "size_bytes": len(member_source),
                    }
                )
            entrypoint_paths = [
                name for name in names if name.endswith(".dist-info/entry_points.txt")
            ]
            if len(entrypoint_paths) != 1:
                raise PoseBustersInternalOracleReproductionError(
                    "Engine v2 wheel entry-point ledger is invalid"
                )
            entrypoint_source = archive.read(entrypoint_paths[0])
    except (OSError, zipfile.BadZipFile) as exc:
        raise PoseBustersInternalOracleReproductionError(
            "Engine v2 wheel is not a readable ZIP archive"
        ) from exc
    try:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_file(io.StringIO(entrypoint_source.decode("utf-8")))
        scripts = dict(parser["console_scripts"])
    except (UnicodeDecodeError, configparser.Error, KeyError) as exc:
        raise PoseBustersInternalOracleReproductionError(
            "Engine v2 wheel entry points are invalid"
        ) from exc
    if any(name not in scripts for name in _REQUIRED_ENTRYPOINTS):
        raise PoseBustersInternalOracleReproductionError(
            "Engine v2 wheel is missing a required reproduction entry point"
        )
    return {
        "filename": candidate.name,
        "sha256": observed_sha,
        "size_bytes": len(source),
        "bound_source_members": bound_members,
        "bound_source_member_count": len(bound_members),
        "entry_points_sha256": hashlib.sha256(entrypoint_source).hexdigest(),
        "required_entrypoints": list(_REQUIRED_ENTRYPOINTS),
    }


def _atomic_write_new(
    path: str | os.PathLike[str],
    source: bytes,
    *,
    maximum_bytes: int,
) -> Path:
    if len(source) > maximum_bytes:
        raise PoseBustersInternalOracleReproductionError(
            "reproduction receipt exceeds its byte bound"
        )
    output = Path(path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(source)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise PoseBustersInternalOracleReproductionError(
                "reproduction output already exists"
            ) from exc
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


class _CanonicalReceipt:
    __slots__ = ("_maximum_bytes", "_payload_bytes")

    def __init__(self, payload: Mapping[str, Any], *, maximum_bytes: int) -> None:
        if "receipt_sha256" in payload:
            raise PoseBustersInternalOracleReproductionError(
                "receipt payload cannot predefine its digest"
            )
        self._payload_bytes = _canonical_bytes(dict(payload))
        self._maximum_bytes = maximum_bytes

    @property
    def fingerprint_sha256(self) -> str:
        return hashlib.sha256(self._payload_bytes).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        payload = json.loads(self._payload_bytes)
        payload["receipt_sha256"] = self.fingerprint_sha256
        return payload

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict()) + b"\n"

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        return _atomic_write_new(
            output_path,
            self.canonical_bytes(),
            maximum_bytes=self._maximum_bytes,
        )


class PoseBustersInternalOracleReproductionWorkOrder(_CanonicalReceipt):
    """Canonical preregistration for one role-separated external execution."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        super().__init__(
            payload,
            maximum_bytes=(
                POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_WORK_ORDER_BYTES
            ),
        )


class PoseBustersInternalOracleReproductionResult(_CanonicalReceipt):
    """Claim-closed comparison of baseline and external observations."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        super().__init__(
            payload,
            maximum_bytes=POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_RESULT_BYTES,
        )


def _runtime_summary(runtime: Mapping[str, Any]) -> dict[str, Any]:
    case_rows = _case_rows(runtime, name="runtime summary")
    return {
        "all_case_denominator": len(case_rows),
        "batch_wall_duration_ns": _integer(
            runtime.get("batch_wall_duration_ns"),
            name="batch wall duration",
        ),
        "batch_sampled_peak_rss_bytes": _integer(
            runtime.get("batch_sampled_peak_rss_bytes"),
            name="batch sampled peak RSS",
            minimum=1,
        ),
        "batch_rss_sample_count": _integer(
            runtime.get("batch_rss_sample_count"),
            name="batch RSS sample count",
            minimum=1,
        ),
        "case_wall_duration_total_ns": sum(
            _integer(row.get("wall_duration_ns"), name="case wall duration")
            for row in case_rows
        ),
        "case_sampled_peak_rss_max_bytes": max(
            _integer(
                row.get("sampled_peak_rss_bytes"),
                name="case sampled peak RSS",
                minimum=1,
            )
            for row in case_rows
        ),
        "runtime_environment_sha256": _digest(
            runtime.get("runtime_environment_sha256"),
            name="runtime environment",
        ),
        "engine_wheel_binding_sha256": _digest(
            runtime.get("engine_wheel_binding_sha256"),
            name="runtime wheel binding",
        ),
    }


def materialize_posebusters_internal_oracle_reproduction_work_order(
    baseline_oracle_receipt_path: str | os.PathLike[str],
    baseline_runtime_observation_receipt_path: str | os.PathLike[str],
    baseline_stratification_receipt_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    *,
    expected_baseline_oracle_receipt_sha256: str,
    expected_baseline_runtime_observation_receipt_sha256: str,
    expected_baseline_stratification_receipt_sha256: str,
    expected_engine_wheel_sha256: str,
    baseline_host_identity_sha256: str,
    expected_external_host_identity_sha256: str,
    work_order_operator_identity_sha256: str,
    external_execution_operator_identity_sha256: str,
    external_execution_nonce_sha256: str,
    registered_utc: str,
) -> PoseBustersInternalOracleReproductionWorkOrder:
    """Preregister one claim-closed second-host oracle observation."""

    baseline = _load_internal_chain(
        baseline_oracle_receipt_path,
        baseline_runtime_observation_receipt_path,
        baseline_stratification_receipt_path,
        expected_oracle_receipt_sha256=(expected_baseline_oracle_receipt_sha256),
        expected_runtime_observation_receipt_sha256=(
            expected_baseline_runtime_observation_receipt_sha256
        ),
        expected_stratification_receipt_sha256=(
            expected_baseline_stratification_receipt_sha256
        ),
    )
    identities = (
        _digest(baseline_host_identity_sha256, name="baseline host identity"),
        _digest(
            expected_external_host_identity_sha256,
            name="expected external host identity",
        ),
        _digest(
            work_order_operator_identity_sha256,
            name="work-order operator identity",
        ),
        _digest(
            external_execution_operator_identity_sha256,
            name="external execution operator identity",
        ),
    )
    if len(set(identities)) != len(identities):
        raise PoseBustersInternalOracleReproductionError(
            "host and operator identities must be role-separated"
        )
    nonce = _digest(external_execution_nonce_sha256, name="execution nonce")
    if nonce in identities:
        raise PoseBustersInternalOracleReproductionError(
            "external execution nonce must not reuse an identity"
        )
    wheel = _wheel_binding(
        engine_wheel_path,
        expected_wheel_sha256=expected_engine_wheel_sha256,
    )
    runtime_wheel = _mapping(
        baseline.runtime.payload.get("engine_wheel_binding"),
        name="baseline runtime wheel",
    )
    if runtime_wheel.get("sha256") != wheel["sha256"]:
        raise PoseBustersInternalOracleReproductionError(
            "baseline runtime did not execute the preregistered wheel"
        )
    source_members = _source_members()
    payload = {
        "schema_id": POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_WORK_ORDER_SCHEMA_ID,
        "registered_utc": _utc(registered_utc, name="registration UTC"),
        "baseline_chain": _chain_binding(baseline),
        "baseline_runtime_summary": _runtime_summary(baseline.runtime.payload),
        "baseline_host_identity_sha256": identities[0],
        "expected_external_host_identity_sha256": identities[1],
        "work_order_operator_identity_sha256": identities[2],
        "external_execution_operator_identity_sha256": identities[3],
        "external_execution_nonce_sha256": nonce,
        "engine_wheel_binding": wheel,
        "required_entrypoints": list(_REQUIRED_ENTRYPOINTS),
        "implementation_source_members": [
            {
                "role": role,
                "sha256": digest,
                "wheel_member_path": member_path,
            }
            for role, digest, member_path in source_members
        ],
        "implementation_source_sha256": _canonical_sha256(source_members),
        "configuration": POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_CONFIGURATION,
        "configuration_sha256": (
            POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_CONFIGURATION_SHA256
        ),
        "all_case_denominator": len(baseline.case_ids),
        "same_deterministic_inputs_required": True,
        "distinct_runtime_observation_required": True,
        "runtime_performance_equivalence_threshold_defined": False,
        "scientific_blockers": list(
            POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_SCIENTIFIC_BLOCKERS
        ),
        **_WORK_ORDER_FLAGS,
    }
    return PoseBustersInternalOracleReproductionWorkOrder(payload)


def verify_posebusters_internal_oracle_reproduction_work_order(
    work_order_path: str | os.PathLike[str],
    baseline_oracle_receipt_path: str | os.PathLike[str],
    baseline_runtime_observation_receipt_path: str | os.PathLike[str],
    baseline_stratification_receipt_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    *,
    expected_work_order_receipt_sha256: str,
    expected_baseline_oracle_receipt_sha256: str,
    expected_baseline_runtime_observation_receipt_sha256: str,
    expected_baseline_stratification_receipt_sha256: str,
    expected_engine_wheel_sha256: str,
) -> PoseBustersInternalOracleReproductionWorkOrder:
    """Reconstruct a work order and require byte-exact equality."""

    loaded = _load_receipt(
        work_order_path,
        expected_schema_id=(
            POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_WORK_ORDER_SCHEMA_ID
        ),
        expected_receipt_sha256=expected_work_order_receipt_sha256,
        maximum_bytes=(POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_WORK_ORDER_BYTES),
    )
    raw = loaded.payload
    expected = materialize_posebusters_internal_oracle_reproduction_work_order(
        baseline_oracle_receipt_path,
        baseline_runtime_observation_receipt_path,
        baseline_stratification_receipt_path,
        engine_wheel_path,
        expected_baseline_oracle_receipt_sha256=(
            expected_baseline_oracle_receipt_sha256
        ),
        expected_baseline_runtime_observation_receipt_sha256=(
            expected_baseline_runtime_observation_receipt_sha256
        ),
        expected_baseline_stratification_receipt_sha256=(
            expected_baseline_stratification_receipt_sha256
        ),
        expected_engine_wheel_sha256=expected_engine_wheel_sha256,
        baseline_host_identity_sha256=_digest(
            raw.get("baseline_host_identity_sha256"),
            name="baseline host identity",
        ),
        expected_external_host_identity_sha256=_digest(
            raw.get("expected_external_host_identity_sha256"),
            name="expected external host identity",
        ),
        work_order_operator_identity_sha256=_digest(
            raw.get("work_order_operator_identity_sha256"),
            name="work-order operator identity",
        ),
        external_execution_operator_identity_sha256=_digest(
            raw.get("external_execution_operator_identity_sha256"),
            name="external execution operator identity",
        ),
        external_execution_nonce_sha256=_digest(
            raw.get("external_execution_nonce_sha256"),
            name="external execution nonce",
        ),
        registered_utc=_utc(raw.get("registered_utc"), name="registration UTC"),
    )
    if loaded.source != expected.canonical_bytes():
        raise PoseBustersInternalOracleReproductionError(
            "work order failed exact reconstruction"
        )
    return expected


def _row_map(
    rows: Sequence[Mapping[str, Any]],
    *,
    key_fields: tuple[str, ...],
    name: str,
) -> dict[tuple[str, ...], dict[str, Any]]:
    result: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(
            _text(row.get(field), name=f"{name} {field}") for field in key_fields
        )
        if key in result:
            raise PoseBustersInternalOracleReproductionError(
                f"{name} keys must be unique"
            )
        result[key] = dict(row)
    return result


def _mismatched_keys(
    baseline: Mapping[tuple[str, ...], Mapping[str, Any]],
    external: Mapping[tuple[str, ...], Mapping[str, Any]],
) -> list[str]:
    mismatches = []
    for key in sorted(set(baseline) | set(external)):
        if key not in baseline or key not in external or baseline[key] != external[key]:
            mismatches.append("|".join(key))
    return mismatches


def compare_posebusters_internal_oracle_reproduction(
    baseline: _InternalOracleChain,
    external: _InternalOracleChain,
) -> dict[str, Any]:
    """Compare every deterministic case/stratum/metric field exactly."""

    baseline_projection = _deterministic_projection(baseline.strata.payload)
    external_projection = _deterministic_projection(external.strata.payload)
    baseline_cases = _row_map(
        [
            _case_semantic_projection(row)
            for row in _case_rows(baseline.strata.payload, name="baseline strata")
        ],
        key_fields=("case_id",),
        name="case",
    )
    external_cases = _row_map(
        [
            _case_semantic_projection(row)
            for row in _case_rows(external.strata.payload, name="external strata")
        ],
        key_fields=("case_id",),
        name="case",
    )
    baseline_strata = _row_map(
        [
            _stratum_semantic_projection(_mapping(row, name="baseline stratum"))
            for row in _list(
                baseline.strata.payload.get("stratum_rows"),
                name="baseline stratum rows",
            )
        ],
        key_fields=("dimension", "stratum_id"),
        name="stratum",
    )
    external_strata = _row_map(
        [
            _stratum_semantic_projection(_mapping(row, name="external stratum"))
            for row in _list(
                external.strata.payload.get("stratum_rows"),
                name="external stratum rows",
            )
        ],
        key_fields=("dimension", "stratum_id"),
        name="stratum",
    )
    baseline_metrics = _row_map(
        [
            _mapping(row, name="baseline metric")
            for row in _list(
                baseline.strata.payload.get("metrics"),
                name="baseline metrics",
            )
        ],
        key_fields=("dimension", "stratum_id", "metric_id"),
        name="metric",
    )
    external_metrics = _row_map(
        [
            _mapping(row, name="external metric")
            for row in _list(
                external.strata.payload.get("metrics"),
                name="external metrics",
            )
        ],
        key_fields=("dimension", "stratum_id", "metric_id"),
        name="metric",
    )
    binding_mismatches = [
        field
        for field in _FIXED_STRATA_BINDING_FIELDS
        if baseline.strata.payload.get(field) != external.strata.payload.get(field)
    ]
    case_mismatches = _mismatched_keys(baseline_cases, external_cases)
    stratum_mismatches = _mismatched_keys(baseline_strata, external_strata)
    metric_mismatches = _mismatched_keys(baseline_metrics, external_metrics)
    oracle_exact = baseline.oracle.receipt_sha256 == external.oracle.receipt_sha256
    projection_exact = baseline_projection == external_projection
    reproduced = (
        oracle_exact
        and projection_exact
        and not binding_mismatches
        and not case_mismatches
        and not stratum_mismatches
        and not metric_mismatches
    )
    payload = {
        "schema_id": (
            POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_DETERMINISTIC_COMPARISON_SCHEMA_ID
        ),
        "baseline_oracle_receipt_sha256": baseline.oracle.receipt_sha256,
        "external_oracle_receipt_sha256": external.oracle.receipt_sha256,
        "oracle_receipt_exact_match": oracle_exact,
        "baseline_deterministic_projection_sha256": _canonical_sha256(
            baseline_projection
        ),
        "external_deterministic_projection_sha256": _canonical_sha256(
            external_projection
        ),
        "deterministic_projection_exact_match": projection_exact,
        "baseline_case_count": len(baseline_cases),
        "external_case_count": len(external_cases),
        "compared_case_count": len(set(baseline_cases) & set(external_cases)),
        "mismatched_case_ids": case_mismatches,
        "mismatched_fixed_binding_fields": binding_mismatches,
        "mismatched_stratum_ids": stratum_mismatches,
        "mismatched_metric_ids": metric_mismatches,
        "all_failure_rows_compared": (tuple(baseline_cases) == tuple(external_cases)),
        "cross_host_deterministic_reproduction_pass": reproduced,
    }
    return {**payload, "comparison_sha256": _canonical_sha256(payload)}


def _ratio_hex(numerator: int, denominator: int) -> str | None:
    if denominator == 0:
        return None
    return (numerator / denominator).hex()


def _runtime_case_measurement_projection(
    runtime: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "case_id": row["case_id"],
            "wall_duration_ns": _integer(
                row.get("wall_duration_ns"),
                name="case wall duration",
            ),
            "rss_start_bytes": _integer(
                row.get("rss_start_bytes"),
                name="case start RSS",
                minimum=1,
            ),
            "rss_end_bytes": _integer(
                row.get("rss_end_bytes"),
                name="case end RSS",
                minimum=1,
            ),
            "sampled_peak_rss_bytes": _integer(
                row.get("sampled_peak_rss_bytes"),
                name="case sampled peak RSS",
                minimum=1,
            ),
            "rss_sample_count": _integer(
                row.get("rss_sample_count"),
                name="case RSS sample count",
                minimum=2,
            ),
        }
        for row in _case_rows(runtime, name="runtime measurement")
    )


def compare_posebusters_internal_oracle_runtime_observations(
    baseline: _InternalOracleChain,
    external: _InternalOracleChain,
) -> dict[str, Any]:
    """Report runtime/RSS differences without inventing an equality gate."""

    baseline_summary = _runtime_summary(baseline.runtime.payload)
    external_summary = _runtime_summary(external.runtime.payload)
    baseline_cases = _runtime_case_measurement_projection(baseline.runtime.payload)
    external_cases = _runtime_case_measurement_projection(external.runtime.payload)
    case_ids_exact = tuple(row["case_id"] for row in baseline_cases) == tuple(
        row["case_id"] for row in external_cases
    )
    values_exact = baseline_cases == external_cases and all(
        baseline_summary[field] == external_summary[field]
        for field in (
            "batch_wall_duration_ns",
            "batch_sampled_peak_rss_bytes",
            "batch_rss_sample_count",
        )
    )
    payload = {
        "schema_id": (
            POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_RUNTIME_COMPARISON_SCHEMA_ID
        ),
        "baseline_runtime_observation_receipt_sha256": (
            baseline.runtime.receipt_sha256
        ),
        "external_runtime_observation_receipt_sha256": (
            external.runtime.receipt_sha256
        ),
        "runtime_observation_receipts_distinct": (
            baseline.runtime.receipt_sha256 != external.runtime.receipt_sha256
        ),
        "case_identity_projection_exact_match": case_ids_exact,
        "baseline_runtime_summary": baseline_summary,
        "external_runtime_summary": external_summary,
        "batch_wall_duration_ratio_external_over_baseline_binary64_hex": (
            _ratio_hex(
                external_summary["batch_wall_duration_ns"],
                baseline_summary["batch_wall_duration_ns"],
            )
        ),
        "batch_sampled_peak_rss_ratio_external_over_baseline_binary64_hex": (
            _ratio_hex(
                external_summary["batch_sampled_peak_rss_bytes"],
                baseline_summary["batch_sampled_peak_rss_bytes"],
            )
        ),
        "runtime_environment_identity_exact_match": (
            baseline_summary["runtime_environment_sha256"]
            == external_summary["runtime_environment_sha256"]
        ),
        "runtime_measurement_values_exact_match": values_exact,
        "runtime_measurement_values_exact_match_required": False,
        "runtime_performance_equivalence_threshold_defined": False,
        "runtime_performance_equivalence_evaluated": False,
        "per_case_runtime_scope": "downstream_posebusters_oracle_loop_only",
        "sampled_rss_is_kernel_enforced": False,
    }
    return {**payload, "comparison_sha256": _canonical_sha256(payload)}


def _load_work_order_and_baseline(
    work_order_path: str | os.PathLike[str],
    baseline_oracle_receipt_path: str | os.PathLike[str],
    baseline_runtime_observation_receipt_path: str | os.PathLike[str],
    baseline_stratification_receipt_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    *,
    expected_work_order_receipt_sha256: str,
    expected_baseline_oracle_receipt_sha256: str,
    expected_baseline_runtime_observation_receipt_sha256: str,
    expected_baseline_stratification_receipt_sha256: str,
    expected_engine_wheel_sha256: str,
) -> tuple[_LoadedReceipt, _InternalOracleChain]:
    verified = verify_posebusters_internal_oracle_reproduction_work_order(
        work_order_path,
        baseline_oracle_receipt_path,
        baseline_runtime_observation_receipt_path,
        baseline_stratification_receipt_path,
        engine_wheel_path,
        expected_work_order_receipt_sha256=expected_work_order_receipt_sha256,
        expected_baseline_oracle_receipt_sha256=(
            expected_baseline_oracle_receipt_sha256
        ),
        expected_baseline_runtime_observation_receipt_sha256=(
            expected_baseline_runtime_observation_receipt_sha256
        ),
        expected_baseline_stratification_receipt_sha256=(
            expected_baseline_stratification_receipt_sha256
        ),
        expected_engine_wheel_sha256=expected_engine_wheel_sha256,
    )
    loaded = _load_receipt(
        work_order_path,
        expected_schema_id=(
            POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_WORK_ORDER_SCHEMA_ID
        ),
        expected_receipt_sha256=verified.fingerprint_sha256,
        maximum_bytes=(POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_WORK_ORDER_BYTES),
    )
    baseline = _load_internal_chain(
        baseline_oracle_receipt_path,
        baseline_runtime_observation_receipt_path,
        baseline_stratification_receipt_path,
        expected_oracle_receipt_sha256=(expected_baseline_oracle_receipt_sha256),
        expected_runtime_observation_receipt_sha256=(
            expected_baseline_runtime_observation_receipt_sha256
        ),
        expected_stratification_receipt_sha256=(
            expected_baseline_stratification_receipt_sha256
        ),
    )
    return loaded, baseline


def _build_reproduction_result(
    work_order_path: str | os.PathLike[str],
    baseline_oracle_receipt_path: str | os.PathLike[str],
    baseline_runtime_observation_receipt_path: str | os.PathLike[str],
    baseline_stratification_receipt_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    external_oracle_receipt_path: str | os.PathLike[str],
    external_runtime_observation_receipt_path: str | os.PathLike[str],
    external_stratification_receipt_path: str | os.PathLike[str],
    *,
    expected_work_order_receipt_sha256: str,
    expected_baseline_oracle_receipt_sha256: str,
    expected_baseline_runtime_observation_receipt_sha256: str,
    expected_baseline_stratification_receipt_sha256: str,
    expected_engine_wheel_sha256: str,
    expected_external_oracle_receipt_sha256: str,
    expected_external_runtime_observation_receipt_sha256: str,
    expected_external_stratification_receipt_sha256: str,
    observed_external_host_identity_sha256: str,
    observed_external_execution_operator_identity_sha256: str,
    external_observed_utc: str,
) -> PoseBustersInternalOracleReproductionResult:
    work_order, baseline = _load_work_order_and_baseline(
        work_order_path,
        baseline_oracle_receipt_path,
        baseline_runtime_observation_receipt_path,
        baseline_stratification_receipt_path,
        engine_wheel_path,
        expected_work_order_receipt_sha256=expected_work_order_receipt_sha256,
        expected_baseline_oracle_receipt_sha256=(
            expected_baseline_oracle_receipt_sha256
        ),
        expected_baseline_runtime_observation_receipt_sha256=(
            expected_baseline_runtime_observation_receipt_sha256
        ),
        expected_baseline_stratification_receipt_sha256=(
            expected_baseline_stratification_receipt_sha256
        ),
        expected_engine_wheel_sha256=expected_engine_wheel_sha256,
    )
    external = _load_internal_chain(
        external_oracle_receipt_path,
        external_runtime_observation_receipt_path,
        external_stratification_receipt_path,
        expected_oracle_receipt_sha256=expected_external_oracle_receipt_sha256,
        expected_runtime_observation_receipt_sha256=(
            expected_external_runtime_observation_receipt_sha256
        ),
        expected_stratification_receipt_sha256=(
            expected_external_stratification_receipt_sha256
        ),
    )
    host = _digest(
        observed_external_host_identity_sha256,
        name="observed external host identity",
    )
    executor = _digest(
        observed_external_execution_operator_identity_sha256,
        name="observed external execution operator identity",
    )
    if host != work_order.payload.get(
        "expected_external_host_identity_sha256"
    ) or executor != work_order.payload.get(
        "external_execution_operator_identity_sha256"
    ):
        raise PoseBustersInternalOracleReproductionError(
            "external host or execution operator was not preregistered"
        )
    observed = _utc_datetime(external_observed_utc, name="external observation UTC")
    registered = _utc_datetime(
        work_order.payload.get("registered_utc"),
        name="work-order registration UTC",
    )
    if observed <= registered:
        raise PoseBustersInternalOracleReproductionError(
            "external observation must follow work-order registration"
        )
    if baseline.runtime.receipt_sha256 == external.runtime.receipt_sha256:
        raise PoseBustersInternalOracleReproductionError(
            "external runtime observation reuses the baseline receipt"
        )
    if baseline.strata.receipt_sha256 == external.strata.receipt_sha256:
        raise PoseBustersInternalOracleReproductionError(
            "external stratification reuses the baseline receipt"
        )
    expected_wheel = _mapping(
        work_order.payload.get("engine_wheel_binding"),
        name="work-order wheel binding",
    )
    external_runtime_wheel = _mapping(
        external.runtime.payload.get("engine_wheel_binding"),
        name="external runtime wheel binding",
    )
    if external_runtime_wheel.get("sha256") != expected_wheel.get("sha256"):
        raise PoseBustersInternalOracleReproductionError(
            "external runtime did not execute the preregistered wheel"
        )
    deterministic = compare_posebusters_internal_oracle_reproduction(
        baseline,
        external,
    )
    runtime_comparison = compare_posebusters_internal_oracle_runtime_observations(
        baseline,
        external,
    )
    reproduced = (
        deterministic["cross_host_deterministic_reproduction_pass"] is True
        and runtime_comparison["runtime_observation_receipts_distinct"] is True
        and runtime_comparison["case_identity_projection_exact_match"] is True
    )
    source_members = _source_members()
    payload = {
        "schema_id": POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_RESULT_SCHEMA_ID,
        "status": "comparison_passed" if reproduced else "comparison_failed",
        "work_order_receipt_sha256": work_order.receipt_sha256,
        "work_order_receipt_file_sha256": work_order.file_sha256,
        "baseline_chain": _chain_binding(baseline),
        "external_chain": _chain_binding(external),
        "baseline_host_identity_sha256": work_order.payload[
            "baseline_host_identity_sha256"
        ],
        "external_host_identity_sha256": host,
        "work_order_operator_identity_sha256": work_order.payload[
            "work_order_operator_identity_sha256"
        ],
        "external_execution_operator_identity_sha256": executor,
        "external_execution_nonce_sha256": work_order.payload[
            "external_execution_nonce_sha256"
        ],
        "external_observed_utc": observed.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "deterministic_comparison": deterministic,
        "runtime_comparison": runtime_comparison,
        "cross_host_deterministic_reproduction_pass": reproduced,
        "all_failure_rows_compared": deterministic["all_failure_rows_compared"],
        "runtime_measurements_compared_without_equality_threshold": True,
        "engine_wheel_binding": expected_wheel,
        "implementation_source_members": [
            {
                "role": role,
                "sha256": digest,
                "wheel_member_path": member_path,
            }
            for role, digest, member_path in source_members
        ],
        "implementation_source_sha256": _canonical_sha256(source_members),
        "configuration": POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_CONFIGURATION,
        "configuration_sha256": (
            POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_CONFIGURATION_SHA256
        ),
        "scientific_blockers": list(
            POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_SCIENTIFIC_BLOCKERS
        ),
        **_RESULT_FLAGS,
    }
    return PoseBustersInternalOracleReproductionResult(payload)


def materialize_posebusters_internal_oracle_reproduction_result(
    work_order_path: str | os.PathLike[str],
    baseline_oracle_receipt_path: str | os.PathLike[str],
    baseline_runtime_observation_receipt_path: str | os.PathLike[str],
    baseline_stratification_receipt_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    external_oracle_receipt_path: str | os.PathLike[str],
    external_runtime_observation_receipt_path: str | os.PathLike[str],
    external_stratification_receipt_path: str | os.PathLike[str],
    *,
    expected_work_order_receipt_sha256: str,
    expected_baseline_oracle_receipt_sha256: str,
    expected_baseline_runtime_observation_receipt_sha256: str,
    expected_baseline_stratification_receipt_sha256: str,
    expected_engine_wheel_sha256: str,
    expected_external_oracle_receipt_sha256: str,
    expected_external_runtime_observation_receipt_sha256: str,
    expected_external_stratification_receipt_sha256: str,
    observed_external_host_identity_sha256: str,
    observed_external_execution_operator_identity_sha256: str,
    external_observed_utc: str,
) -> PoseBustersInternalOracleReproductionResult:
    """Compare one preregistered external observation with the baseline."""

    return _build_reproduction_result(
        work_order_path,
        baseline_oracle_receipt_path,
        baseline_runtime_observation_receipt_path,
        baseline_stratification_receipt_path,
        engine_wheel_path,
        external_oracle_receipt_path,
        external_runtime_observation_receipt_path,
        external_stratification_receipt_path,
        expected_work_order_receipt_sha256=expected_work_order_receipt_sha256,
        expected_baseline_oracle_receipt_sha256=(
            expected_baseline_oracle_receipt_sha256
        ),
        expected_baseline_runtime_observation_receipt_sha256=(
            expected_baseline_runtime_observation_receipt_sha256
        ),
        expected_baseline_stratification_receipt_sha256=(
            expected_baseline_stratification_receipt_sha256
        ),
        expected_engine_wheel_sha256=expected_engine_wheel_sha256,
        expected_external_oracle_receipt_sha256=(
            expected_external_oracle_receipt_sha256
        ),
        expected_external_runtime_observation_receipt_sha256=(
            expected_external_runtime_observation_receipt_sha256
        ),
        expected_external_stratification_receipt_sha256=(
            expected_external_stratification_receipt_sha256
        ),
        observed_external_host_identity_sha256=(observed_external_host_identity_sha256),
        observed_external_execution_operator_identity_sha256=(
            observed_external_execution_operator_identity_sha256
        ),
        external_observed_utc=external_observed_utc,
    )


def verify_posebusters_internal_oracle_reproduction_result(
    result_path: str | os.PathLike[str],
    work_order_path: str | os.PathLike[str],
    baseline_oracle_receipt_path: str | os.PathLike[str],
    baseline_runtime_observation_receipt_path: str | os.PathLike[str],
    baseline_stratification_receipt_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    external_oracle_receipt_path: str | os.PathLike[str],
    external_runtime_observation_receipt_path: str | os.PathLike[str],
    external_stratification_receipt_path: str | os.PathLike[str],
    *,
    expected_result_receipt_sha256: str,
    expected_work_order_receipt_sha256: str,
    expected_baseline_oracle_receipt_sha256: str,
    expected_baseline_runtime_observation_receipt_sha256: str,
    expected_baseline_stratification_receipt_sha256: str,
    expected_engine_wheel_sha256: str,
    expected_external_oracle_receipt_sha256: str,
    expected_external_runtime_observation_receipt_sha256: str,
    expected_external_stratification_receipt_sha256: str,
) -> PoseBustersInternalOracleReproductionResult:
    """Reconstruct a result from both receipt chains and require equality."""

    loaded = _load_receipt(
        result_path,
        expected_schema_id=POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_RESULT_SCHEMA_ID,
        expected_receipt_sha256=expected_result_receipt_sha256,
        maximum_bytes=POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_RESULT_BYTES,
    )
    raw = loaded.payload
    expected = _build_reproduction_result(
        work_order_path,
        baseline_oracle_receipt_path,
        baseline_runtime_observation_receipt_path,
        baseline_stratification_receipt_path,
        engine_wheel_path,
        external_oracle_receipt_path,
        external_runtime_observation_receipt_path,
        external_stratification_receipt_path,
        expected_work_order_receipt_sha256=expected_work_order_receipt_sha256,
        expected_baseline_oracle_receipt_sha256=(
            expected_baseline_oracle_receipt_sha256
        ),
        expected_baseline_runtime_observation_receipt_sha256=(
            expected_baseline_runtime_observation_receipt_sha256
        ),
        expected_baseline_stratification_receipt_sha256=(
            expected_baseline_stratification_receipt_sha256
        ),
        expected_engine_wheel_sha256=expected_engine_wheel_sha256,
        expected_external_oracle_receipt_sha256=(
            expected_external_oracle_receipt_sha256
        ),
        expected_external_runtime_observation_receipt_sha256=(
            expected_external_runtime_observation_receipt_sha256
        ),
        expected_external_stratification_receipt_sha256=(
            expected_external_stratification_receipt_sha256
        ),
        observed_external_host_identity_sha256=_digest(
            raw.get("external_host_identity_sha256"),
            name="external host identity",
        ),
        observed_external_execution_operator_identity_sha256=_digest(
            raw.get("external_execution_operator_identity_sha256"),
            name="external execution operator identity",
        ),
        external_observed_utc=_utc(
            raw.get("external_observed_utc"),
            name="external observation UTC",
        ),
    )
    if loaded.source != expected.canonical_bytes():
        raise PoseBustersInternalOracleReproductionError(
            "reproduction result failed exact reconstruction"
        )
    return expected


def _add_baseline_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--baseline-oracle-receipt", required=True)
    parser.add_argument("--baseline-runtime-observation-receipt", required=True)
    parser.add_argument("--baseline-stratification-receipt", required=True)
    parser.add_argument("--engine-wheel", required=True)
    parser.add_argument(
        "--expected-baseline-oracle-receipt-sha256",
        required=True,
    )
    parser.add_argument(
        "--expected-baseline-runtime-observation-receipt-sha256",
        required=True,
    )
    parser.add_argument(
        "--expected-baseline-stratification-receipt-sha256",
        required=True,
    )
    parser.add_argument("--expected-engine-wheel-sha256", required=True)


def _add_work_order_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--work-order", required=True)
    parser.add_argument("--expected-work-order-receipt-sha256", required=True)


def _add_external_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--external-oracle-receipt", required=True)
    parser.add_argument("--external-runtime-observation-receipt", required=True)
    parser.add_argument("--external-stratification-receipt", required=True)
    parser.add_argument(
        "--expected-external-oracle-receipt-sha256",
        required=True,
    )
    parser.add_argument(
        "--expected-external-runtime-observation-receipt-sha256",
        required=True,
    )
    parser.add_argument(
        "--expected-external-stratification-receipt-sha256",
        required=True,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-internal-oracle-reproduce",
        description=(
            "Preregister and compare a second-host internal PoseBusters-oracle "
            "rerun while keeping physical-host independence claim-closed."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize_work_order = subparsers.add_parser("materialize-work-order")
    verify_work_order = subparsers.add_parser("verify-work-order")
    materialize_result = subparsers.add_parser("materialize-result")
    verify_result = subparsers.add_parser("verify-result")
    for command in (
        materialize_work_order,
        verify_work_order,
        materialize_result,
        verify_result,
    ):
        _add_baseline_arguments(command)
    materialize_work_order.add_argument("--output", required=True)
    materialize_work_order.add_argument(
        "--baseline-host-identity-sha256",
        required=True,
    )
    materialize_work_order.add_argument(
        "--expected-external-host-identity-sha256",
        required=True,
    )
    materialize_work_order.add_argument(
        "--work-order-operator-identity-sha256",
        required=True,
    )
    materialize_work_order.add_argument(
        "--external-execution-operator-identity-sha256",
        required=True,
    )
    materialize_work_order.add_argument(
        "--external-execution-nonce-sha256",
        required=True,
    )
    materialize_work_order.add_argument("--registered-utc", required=True)
    _add_work_order_arguments(verify_work_order)
    for command in (materialize_result, verify_result):
        _add_work_order_arguments(command)
        _add_external_arguments(command)
    materialize_result.add_argument("--output", required=True)
    materialize_result.add_argument(
        "--observed-external-host-identity-sha256",
        required=True,
    )
    materialize_result.add_argument(
        "--observed-external-execution-operator-identity-sha256",
        required=True,
    )
    materialize_result.add_argument("--external-observed-utc", required=True)
    verify_result.add_argument("--result", required=True)
    verify_result.add_argument("--expected-result-receipt-sha256", required=True)
    return parser


def _baseline_cli_arguments(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "baseline_oracle_receipt_path": args.baseline_oracle_receipt,
        "baseline_runtime_observation_receipt_path": (
            args.baseline_runtime_observation_receipt
        ),
        "baseline_stratification_receipt_path": (args.baseline_stratification_receipt),
        "engine_wheel_path": args.engine_wheel,
        "expected_baseline_oracle_receipt_sha256": (
            args.expected_baseline_oracle_receipt_sha256
        ),
        "expected_baseline_runtime_observation_receipt_sha256": (
            args.expected_baseline_runtime_observation_receipt_sha256
        ),
        "expected_baseline_stratification_receipt_sha256": (
            args.expected_baseline_stratification_receipt_sha256
        ),
        "expected_engine_wheel_sha256": args.expected_engine_wheel_sha256,
    }


def _external_cli_arguments(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "external_oracle_receipt_path": args.external_oracle_receipt,
        "external_runtime_observation_receipt_path": (
            args.external_runtime_observation_receipt
        ),
        "external_stratification_receipt_path": args.external_stratification_receipt,
        "expected_external_oracle_receipt_sha256": (
            args.expected_external_oracle_receipt_sha256
        ),
        "expected_external_runtime_observation_receipt_sha256": (
            args.expected_external_runtime_observation_receipt_sha256
        ),
        "expected_external_stratification_receipt_sha256": (
            args.expected_external_stratification_receipt_sha256
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    baseline = _baseline_cli_arguments(args)
    if args.command == "materialize-work-order":
        receipt: _CanonicalReceipt = (
            materialize_posebusters_internal_oracle_reproduction_work_order(
                **baseline,
                baseline_host_identity_sha256=(args.baseline_host_identity_sha256),
                expected_external_host_identity_sha256=(
                    args.expected_external_host_identity_sha256
                ),
                work_order_operator_identity_sha256=(
                    args.work_order_operator_identity_sha256
                ),
                external_execution_operator_identity_sha256=(
                    args.external_execution_operator_identity_sha256
                ),
                external_execution_nonce_sha256=(args.external_execution_nonce_sha256),
                registered_utc=args.registered_utc,
            )
        )
        receipt.write_json(args.output)
    elif args.command == "verify-work-order":
        receipt = verify_posebusters_internal_oracle_reproduction_work_order(
            work_order_path=args.work_order,
            expected_work_order_receipt_sha256=(
                args.expected_work_order_receipt_sha256
            ),
            **baseline,
        )
    elif args.command == "materialize-result":
        receipt = materialize_posebusters_internal_oracle_reproduction_result(
            work_order_path=args.work_order,
            expected_work_order_receipt_sha256=(
                args.expected_work_order_receipt_sha256
            ),
            **baseline,
            **_external_cli_arguments(args),
            observed_external_host_identity_sha256=(
                args.observed_external_host_identity_sha256
            ),
            observed_external_execution_operator_identity_sha256=(
                args.observed_external_execution_operator_identity_sha256
            ),
            external_observed_utc=args.external_observed_utc,
        )
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_internal_oracle_reproduction_result(
            result_path=args.result,
            expected_result_receipt_sha256=args.expected_result_receipt_sha256,
            work_order_path=args.work_order,
            expected_work_order_receipt_sha256=(
                args.expected_work_order_receipt_sha256
            ),
            **baseline,
            **_external_cli_arguments(args),
        )
    payload = receipt.to_dict()
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "status": payload.get("status", "work_order_registered"),
                "cross_host_deterministic_reproduction_pass": payload.get(
                    "cross_host_deterministic_reproduction_pass",
                    False,
                ),
                "physical_host_independence_reviewed": False,
                "independent_external_rerun_present": False,
                "benchmark_executed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_CONFIGURATION",
    "POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_CONFIGURATION_SHA256",
    "POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_DETERMINISTIC_COMPARISON_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_INPUT_BYTES",
    "POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_RESULT_BYTES",
    "POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_WHEEL_BYTES",
    "POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_MAX_WORK_ORDER_BYTES",
    "POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_RESULT_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_RUNTIME_COMPARISON_SCHEMA_ID",
    "POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_SCIENTIFIC_BLOCKERS",
    "POSEBUSTERS_INTERNAL_ORACLE_REPRODUCTION_WORK_ORDER_SCHEMA_ID",
    "PoseBustersInternalOracleReproductionError",
    "PoseBustersInternalOracleReproductionResult",
    "PoseBustersInternalOracleReproductionWorkOrder",
    "compare_posebusters_internal_oracle_reproduction",
    "compare_posebusters_internal_oracle_runtime_observations",
    "main",
    "materialize_posebusters_internal_oracle_reproduction_result",
    "materialize_posebusters_internal_oracle_reproduction_work_order",
    "verify_posebusters_internal_oracle_reproduction_result",
    "verify_posebusters_internal_oracle_reproduction_work_order",
]
