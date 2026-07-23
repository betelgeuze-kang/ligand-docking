"""Materialize failure-inclusive PoseBusters ranking test partitions.

This module closes the mechanical identity gap between the frozen
Vina/GNINA/Smina ranking intake and ``PoseRankingCalibrationPartition``.  It
binds successful rows to exact pose-coordinate identities and failure rows to
domain-separated failure-observation identities, then assigns every case to
the complete observed-sequence proxy stratum.

The proxy is not a biological target family.  RCSB/Pfam annotations remain a
separate, incomplete annotation surface.  The resulting partitions are
``split_role=test`` only: this module never constructs a fit partition, calls a
fitting API, or authorizes a calibrated-scoring claim.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile
from typing import Any

import betelgeuze_engine_v2.docking.calibration as calibration_module
from betelgeuze_engine_v2.docking.calibration import (
    PoseRankingCalibrationPartition,
    PoseRankingCalibrationRow,
)

from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _source_file_sha256,
)
from .public_posebusters_intake import (
    PoseBustersArchiveIntakeError,
    _read_exact_regular_file,
)
from .public_posebusters_pose_ranking_intake import (
    POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR,
    POSEBUSTERS_POSE_RANKING_INTAKE_CONFIGURATION_SHA256,
    POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES,
    POSEBUSTERS_POSE_RANKING_INTAKE_METRIC_SCHEMA_ID,
    POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID,
    PoseBustersPoseRankingIntakeError,
    _LoadedReceipt,
    _load_receipt,
)
from .public_posebusters_pose_scaffold_identity import (
    POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_CONFIGURATION_SHA256,
    POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_RECEIPT_SCHEMA_ID,
)
from .public_posebusters_rcsb_target_family_binding import (
    POSEBUSTERS_RCSB_TARGET_FAMILY_CONFIGURATION_SHA256,
    POSEBUSTERS_RCSB_TARGET_FAMILY_RECEIPT_SCHEMA_ID,
    POSEBUSTERS_RCSB_TARGET_METRIC_SCHEMA_ID,
)
from .public_posebusters_target_cluster_binding import (
    POSEBUSTERS_TARGET_CLUSTER_CONFIGURATION_SHA256,
    POSEBUSTERS_TARGET_CLUSTER_METRIC_SCHEMA_ID,
    POSEBUSTERS_TARGET_CLUSTER_RECEIPT_SCHEMA_ID,
)


POSEBUSTERS_POSE_RANKING_TEST_PARTITION_INPUT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_ranking_test_partition_input/1.0.0"
)
POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_ranking_test_partition_case/1.0.0"
)
POSEBUSTERS_POSE_RANKING_TEST_PARTITION_ENGINE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_ranking_test_partition_engine/1.0.0"
)
POSEBUSTERS_FAILED_POSE_OBSERVATION_IDENTITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_failed_pose_observation_identity/1.0.0"
)
POSEBUSTERS_POSE_RANKING_TEST_PARTITION_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_ranking_test_partitions/1.0.0"
)

POSEBUSTERS_POSE_RANKING_TEST_PARTITION_MAX_INPUT_BYTES = 64 * 1024 * 1024
POSEBUSTERS_POSE_RANKING_TEST_PARTITION_MAX_RECEIPT_BYTES = 32 * 1024 * 1024
POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_POSE_RANKING_TEST_PARTITION_Z = 1.959963984540054

POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CONFIGURATION = {
    "biological_annotation": "separate_incomplete_rcsb_pfam_observation",
    "calibration_fit": "forbidden",
    "failure_pose_sha256_semantics": (
        "domain_separated_failure_observation_identity_not_coordinates"
    ),
    "partition_count": 3,
    "partition_policy": "one_failure_inclusive_partition_per_engine",
    "split_role": "test",
    "successful_pose_sha256_semantics": "exact_pose_coordinate_identity",
    "target_family_field_semantics": (
        "observed_receptor_sequence_proxy_not_biological_family"
    ),
    "test_label_fit_policy": "forbidden",
}
POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CONFIGURATION_SHA256 = _canonical_sha256(
    POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CONFIGURATION
)

POSEBUSTERS_POSE_RANKING_TEST_PARTITION_SCIENTIFIC_BLOCKERS = (
    "observed_sequence_proxy_is_not_a_biological_target_family",
    "pfam_annotation_is_incomplete_for_the_all_case_denominator",
    "failure_observation_identities_are_not_pose_coordinates",
    "calibration_fit_partition_manifest_missing",
    "fit_to_test_target_sequence_leakage_audit_missing",
    "fit_to_test_ligand_scaffold_leakage_audit_missing",
    "only_strictly_prepared_chemistry_subset_has_scored_poses",
    "independent_external_rerun_missing",
    "independent_scientific_review_missing",
    "public_pose_ranking_calibration_claim_not_authorized",
)

_SHA256_CHARACTERS = frozenset("0123456789abcdef")
_MAPPING_FAILURE_STATUSES = {
    "pocket_chain_unmapped",
    "pocket_chain_ambiguous",
}


class PoseBustersPoseRankingTestPartitionError(ValueError):
    """A test-partition identity, denominator, or claim boundary failed."""


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PoseBustersPoseRankingTestPartitionError(f"{name} must be a mapping")
    return dict(value)


def _list(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PoseBustersPoseRankingTestPartitionError(f"{name} must be a list")
    return value


def _text(
    value: object,
    *,
    name: str,
    maximum: int = 512,
    allow_empty: bool = False,
) -> str:
    if (
        not isinstance(value, str)
        or (not value and not allow_empty)
        or len(value.encode("utf-8")) > maximum
        or any(character in "\r\n\x00" for character in value)
    ):
        raise PoseBustersPoseRankingTestPartitionError(
            f"{name} must be bounded single-line text"
        )
    return value


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_CHARACTERS for character in value)
    ):
        raise PoseBustersPoseRankingTestPartitionError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _integer(
    value: object,
    *,
    name: str,
    minimum: int = 0,
) -> int:
    if type(value) is not int or value < minimum:
        raise PoseBustersPoseRankingTestPartitionError(
            f"{name} must be an integer >= {minimum}"
        )
    return value


def _boolean(value: object, *, name: str) -> bool:
    if type(value) is not bool:
        raise PoseBustersPoseRankingTestPartitionError(f"{name} must be boolean")
    return value


def _engine(value: object) -> str:
    engine = _text(value, name="engine ID")
    if engine not in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
        raise PoseBustersPoseRankingTestPartitionError(
            "engine ID must be vina, gnina, or smina"
        )
    return engine


def _case_id(value: object) -> str:
    case = _text(value, name="case ID", maximum=64)
    if (
        case.count("_") != 1
        or case != case.upper()
        or any(
            character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
            for character in case
        )
    ):
        raise PoseBustersPoseRankingTestPartitionError("PoseBusters case ID is invalid")
    return case


def _binary64(value: object, *, name: str) -> float:
    text = _text(value, name=name, maximum=128)
    try:
        number = float.fromhex(text)
    except ValueError as exc:
        raise PoseBustersPoseRankingTestPartitionError(
            f"{name} is not binary64 hexadecimal"
        ) from exc
    if not math.isfinite(number) or number.hex() != text:
        raise PoseBustersPoseRankingTestPartitionError(
            f"{name} is not canonical finite binary64 hexadecimal"
        )
    return number


def _load_source(
    receipt_path: str | os.PathLike[str],
    *,
    expected_schema_id: str,
    expected_receipt_sha256: str,
    role: str,
) -> _LoadedReceipt:
    try:
        return _load_receipt(
            receipt_path,
            expected_schema_id=expected_schema_id,
            expected_receipt_sha256=expected_receipt_sha256,
        )
    except PoseBustersPoseRankingIntakeError as exc:
        raise PoseBustersPoseRankingTestPartitionError(
            f"{role} source receipt is invalid"
        ) from exc


def _input_map(
    receipt: _LoadedReceipt,
    *,
    name: str,
) -> dict[str, dict[str, Any]]:
    rows = _list(receipt.payload.get("input_receipts"), name=f"{name} inputs")
    result: dict[str, dict[str, Any]] = {}
    for raw in rows:
        row = _mapping(raw, name=f"{name} input")
        role = _text(row.get("role"), name=f"{name} input role")
        if role in result:
            raise PoseBustersPoseRankingTestPartitionError(
                f"{name} input roles must be unique"
            )
        _text(row.get("source_schema_id"), name=f"{name} source schema")
        _digest(row.get("source_receipt_sha256"), name=f"{name} source receipt")
        _digest(row.get("source_file_sha256"), name=f"{name} source file")
        result[role] = row
    return result


def _require_input(
    inputs: Mapping[str, Mapping[str, Any]],
    role: str,
    source: _LoadedReceipt,
    *,
    name: str,
) -> None:
    row = inputs.get(role)
    if (
        row is None
        or row.get("source_schema_id") != source.schema_id
        or row.get("source_receipt_sha256") != source.receipt_sha256
        or row.get("source_file_sha256") != source.file_sha256
    ):
        raise PoseBustersPoseRankingTestPartitionError(
            f"{name} does not bind the exact {role} source"
        )


def _case_map(
    value: object,
    *,
    name: str,
) -> tuple[tuple[str, ...], dict[str, dict[str, Any]]]:
    rows = _list(value, name=f"{name} case rows")
    if len(rows) != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR:
        raise PoseBustersPoseRankingTestPartitionError(
            f"{name} must retain the exact 308-case denominator"
        )
    parsed = [
        (_case_id(row.get("case_id")), row)
        for row in (_mapping(item, name=f"{name} case row") for item in rows)
    ]
    case_ids = tuple(case for case, _ in parsed)
    if case_ids != tuple(sorted(case_ids)) or len(set(case_ids)) != len(case_ids):
        raise PoseBustersPoseRankingTestPartitionError(
            f"{name} case IDs must be unique and sorted"
        )
    return case_ids, dict(parsed)


def _atomic_write_new(
    output_path: str | os.PathLike[str],
    source: bytes,
) -> Path:
    if len(source) > POSEBUSTERS_POSE_RANKING_TEST_PARTITION_MAX_RECEIPT_BYTES:
        raise PoseBustersPoseRankingTestPartitionError(
            "test-partition receipt exceeds its byte bound"
        )
    output = Path(output_path)
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
            raise PoseBustersPoseRankingTestPartitionError(
                "test-partition output already exists"
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


def _wilson_interval(numerator: int, denominator: int) -> tuple[float, float]:
    if denominator <= 0 or numerator < 0 or numerator > denominator:
        raise PoseBustersPoseRankingTestPartitionError(
            "metric numerator/denominator is invalid"
        )
    estimate = numerator / denominator
    z = POSEBUSTERS_POSE_RANKING_TEST_PARTITION_Z
    z_squared = z * z
    scale = 1.0 + z_squared / denominator
    center = (estimate + z_squared / (2.0 * denominator)) / scale
    margin = (
        z
        * math.sqrt(
            (estimate * (1.0 - estimate) + z_squared / (4.0 * denominator))
            / denominator
        )
        / scale
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _validated_metric_rows(
    value: object,
    *,
    name: str,
    schema_id: str,
) -> tuple[list[dict[str, Any]], str]:
    rows = [
        _mapping(item, name=f"{name} metric")
        for item in _list(value, name=f"{name} metrics")
    ]
    if not rows:
        raise PoseBustersPoseRankingTestPartitionError(
            f"{name} metrics cannot be empty"
        )
    for row in rows:
        if row.get("schema_id") != schema_id:
            raise PoseBustersPoseRankingTestPartitionError(
                f"{name} metric schema is invalid"
            )
        numerator = _integer(row.get("numerator"), name=f"{name} numerator")
        denominator = _integer(
            row.get("denominator"),
            name=f"{name} denominator",
            minimum=1,
        )
        if numerator > denominator:
            raise PoseBustersPoseRankingTestPartitionError(
                f"{name} metric numerator exceeds denominator"
            )
        estimate = row.get("estimate")
        low = row.get("confidence_interval_low")
        high = row.get("confidence_interval_high")
        if any(
            type(item) not in (int, float) or not math.isfinite(float(item))
            for item in (estimate, low, high)
        ):
            raise PoseBustersPoseRankingTestPartitionError(
                f"{name} metric values must be finite"
            )
        expected_low, expected_high = _wilson_interval(numerator, denominator)
        expected_estimate = numerator / denominator
        if (
            row.get("confidence_interval_method") != "wilson_score_binomial"
            or row.get("confidence_level")
            != POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CONFIDENCE_LEVEL
            or not math.isclose(
                float(estimate),
                expected_estimate,
                rel_tol=0.0,
                abs_tol=1.0e-15,
            )
            or not math.isclose(
                float(low),
                expected_low,
                rel_tol=0.0,
                abs_tol=1.0e-15,
            )
            or not math.isclose(
                float(high),
                expected_high,
                rel_tol=0.0,
                abs_tol=1.0e-15,
            )
        ):
            raise PoseBustersPoseRankingTestPartitionError(
                f"{name} metric estimate or Wilson interval is invalid"
            )
    return rows, _canonical_sha256(rows)


def _metric_index(
    rows: Sequence[Mapping[str, Any]],
    *,
    key_fields: Sequence[str],
    name: str,
) -> dict[tuple[object, ...], Mapping[str, Any]]:
    result: dict[tuple[object, ...], Mapping[str, Any]] = {}
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        if key in result:
            raise PoseBustersPoseRankingTestPartitionError(
                f"{name} metric keys must be unique"
            )
        result[key] = row
    return result


def _expect_metric(
    metrics: Mapping[tuple[object, ...], Mapping[str, Any]],
    key: tuple[object, ...],
    *,
    numerator: int,
    denominator: int,
    name: str,
) -> None:
    row = metrics.get(key)
    if (
        row is None
        or row.get("numerator") != numerator
        or row.get("denominator") != denominator
    ):
        raise PoseBustersPoseRankingTestPartitionError(
            f"{name} metric numerator or denominator is inconsistent"
        )


def _validate_ranking_metrics(
    ranking: _LoadedReceipt,
    rows_by_engine: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    rows, root = _validated_metric_rows(
        ranking.payload.get("metrics"),
        name="pose-ranking all-case",
        schema_id=POSEBUSTERS_POSE_RANKING_INTAKE_METRIC_SCHEMA_ID,
    )
    if len(rows) != 7 * len(POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES):
        raise PoseBustersPoseRankingTestPartitionError(
            "pose-ranking metric row count is incomplete"
        )
    metrics = _metric_index(
        rows,
        key_fields=("engine_id", "metric_id"),
        name="pose-ranking",
    )
    engine_summaries = {
        _engine(row.get("engine_id")): row
        for row in (
            _mapping(item, name="pose-ranking engine summary")
            for item in _list(
                ranking.payload.get("engine_summaries"),
                name="pose-ranking engine summaries",
            )
        )
    }
    if set(engine_summaries) != set(POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES):
        raise PoseBustersPoseRankingTestPartitionError(
            "pose-ranking engine summaries are incomplete"
        )
    summaries: list[dict[str, Any]] = []
    for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
        engine_rows = rows_by_engine[engine]
        success_rows = [row for row in engine_rows if row.get("status") == "success"]
        failure_rows = [row for row in engine_rows if row.get("status") == "failure"]
        by_case: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in success_rows:
            by_case[_case_id(row.get("case_id"))].append(row)
        evaluated_cases = len(by_case)
        top_1 = sum(
            any(
                row.get("pose_rank") == 1 and row.get("native_like") is True
                for row in case_rows
            )
            for case_rows in by_case.values()
        )
        top_5 = sum(
            any(
                _integer(row.get("pose_rank"), name="pose rank", minimum=1) <= 5
                and row.get("native_like") is True
                for row in case_rows
            )
            for case_rows in by_case.values()
        )
        top_1_valid = sum(
            any(
                row.get("pose_rank") == 1
                and row.get("native_like") is True
                and row.get("physically_valid") is True
                for row in case_rows
            )
            for case_rows in by_case.values()
        )
        top_5_valid = sum(
            any(
                _integer(row.get("pose_rank"), name="pose rank", minimum=1) <= 5
                and row.get("native_like") is True
                and row.get("physically_valid") is True
                for row in case_rows
            )
            for case_rows in by_case.values()
        )
        native_like_poses = sum(row.get("native_like") is True for row in success_rows)
        physically_valid_poses = sum(
            row.get("physically_valid") is True for row in success_rows
        )
        expected = {
            "evaluated_case_rate": (
                evaluated_cases,
                POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR,
            ),
            "top_1_native_like_case_rate": (
                top_1,
                POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR,
            ),
            "top_5_native_like_case_rate": (
                top_5,
                POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR,
            ),
            "top_1_valid_native_like_case_rate": (
                top_1_valid,
                POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR,
            ),
            "top_5_valid_native_like_case_rate": (
                top_5_valid,
                POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR,
            ),
            "native_like_pose_rate": (native_like_poses, len(success_rows)),
            "physically_valid_pose_rate": (physically_valid_poses, len(success_rows)),
        }
        for metric_id, (numerator, denominator) in expected.items():
            _expect_metric(
                metrics,
                (engine, metric_id),
                numerator=numerator,
                denominator=denominator,
                name=f"{engine} {metric_id}",
            )
        summary = engine_summaries[engine]
        expected_summary = {
            "evaluated_case_count": evaluated_cases,
            "failure_row_count": len(failure_rows),
            "native_like_pose_count": native_like_poses,
            "physically_valid_pose_count": physically_valid_poses,
            "successful_pose_row_count": len(success_rows),
            "top_1_native_like_case_count": top_1,
            "top_1_valid_native_like_case_count": top_1_valid,
            "top_5_native_like_case_count": top_5,
            "top_5_valid_native_like_case_count": top_5_valid,
        }
        if any(summary.get(key) != value for key, value in expected_summary.items()):
            raise PoseBustersPoseRankingTestPartitionError(
                f"{engine} pose-ranking engine summary is inconsistent"
            )
        summaries.append(
            {
                "engine_id": engine,
                **expected_summary,
            }
        )
    return {
        "source_metric_row_count": len(rows),
        "source_metric_root_sha256": root,
        "all_case_denominator": (POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR),
        "confidence_interval_method": "wilson_score_binomial",
        "confidence_level": POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CONFIDENCE_LEVEL,
        "engine_summaries": summaries,
        "validated": True,
    }


def _validate_cluster_metrics(
    cluster: _LoadedReceipt,
    case_ids: Sequence[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    cluster_case_ids, cluster_cases = _case_map(
        cluster.payload.get("case_rows"),
        name="observed-sequence proxy",
    )
    if tuple(case_ids) != cluster_case_ids:
        raise PoseBustersPoseRankingTestPartitionError(
            "observed-sequence proxy case denominator differs"
        )
    family_rows = [
        _mapping(item, name="observed-sequence proxy family")
        for item in _list(
            cluster.payload.get("family_rows"),
            name="observed-sequence proxy families",
        )
    ]
    family_members: dict[str, tuple[str, ...]] = {}
    for row in family_rows:
        family_id = _text(row.get("family_id"), name="proxy family ID")
        members = tuple(
            _case_id(value)
            for value in _list(
                row.get("member_case_ids"),
                name="proxy family members",
            )
        )
        if (
            family_id in family_members
            or members != tuple(sorted(members))
            or not members
            or row.get("member_case_count") != len(members)
        ):
            raise PoseBustersPoseRankingTestPartitionError(
                "observed-sequence proxy family membership is invalid"
            )
        family_members[family_id] = members
    assigned = [case for members in family_members.values() for case in members]
    if sorted(assigned) != list(case_ids) or len(assigned) != len(set(assigned)):
        raise PoseBustersPoseRankingTestPartitionError(
            "observed-sequence proxy families must partition all 308 cases"
        )
    for case_id, row in cluster_cases.items():
        family_id = _text(row.get("family_id"), name="case proxy family")
        if case_id not in family_members.get(family_id, ()):
            raise PoseBustersPoseRankingTestPartitionError(
                "case proxy family assignment is inconsistent"
            )
        _digest(
            row.get("target_sequence_set_sha256"),
            name="target sequence-set identity",
        )
        chains = _list(row.get("chains"), name="target sequence chains")
        if not chains:
            raise PoseBustersPoseRankingTestPartitionError(
                "target sequence proxy requires at least one observed chain"
            )
        for raw_chain in chains:
            chain = _mapping(raw_chain, name="target sequence chain")
            _text(chain.get("chain_id"), name="target sequence chain ID")
            _digest(
                chain.get("residue_label_sequence_sha256"),
                name="target chain sequence identity",
            )

    engine_case_rows = [
        _mapping(item, name="proxy engine case")
        for item in _list(
            cluster.payload.get("engine_case_rows"),
            name="proxy engine cases",
        )
    ]
    engine_cases: dict[tuple[str, str], dict[str, Any]] = {}
    for row in engine_case_rows:
        key = (_engine(row.get("engine_id")), _case_id(row.get("case_id")))
        if key in engine_cases or row.get("family_id") != cluster_cases[key[1]].get(
            "family_id"
        ):
            raise PoseBustersPoseRankingTestPartitionError(
                "proxy engine-case assignment is invalid"
            )
        engine_cases[key] = row
    expected_engine_case_keys = {
        (engine, case_id)
        for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
        for case_id in case_ids
    }
    if set(engine_cases) != expected_engine_case_keys:
        raise PoseBustersPoseRankingTestPartitionError(
            "proxy engine-case denominator is incomplete"
        )

    source_engine_families = [
        _mapping(item, name="proxy engine family")
        for item in _list(
            cluster.payload.get("engine_family_rows"),
            name="proxy engine families",
        )
    ]
    engine_families: dict[tuple[str, str], dict[str, Any]] = {}
    count_fields = (
        "execution_success_case_count",
        "top_1_physically_valid_case_count",
        "top_1_rmsd_hit_case_count",
        "top_1_valid_rmsd_hit_case_count",
        "top_5_physically_valid_case_count",
        "top_5_rmsd_hit_case_count",
        "top_5_valid_rmsd_hit_case_count",
    )
    source_field = {
        "execution_success_case_count": "execution_status",
        "top_1_physically_valid_case_count": "top_1_physically_valid",
        "top_1_rmsd_hit_case_count": "top_1_rmsd_hit",
        "top_1_valid_rmsd_hit_case_count": "top_1_valid_rmsd_hit",
        "top_5_physically_valid_case_count": "top_5_physically_valid",
        "top_5_rmsd_hit_case_count": "top_5_rmsd_hit",
        "top_5_valid_rmsd_hit_case_count": "top_5_valid_rmsd_hit",
    }
    for row in source_engine_families:
        engine = _engine(row.get("engine_id"))
        family_id = _text(row.get("family_id"), name="proxy engine family ID")
        key = (engine, family_id)
        if key in engine_families or family_id not in family_members:
            raise PoseBustersPoseRankingTestPartitionError(
                "proxy engine-family key is invalid"
            )
        members = family_members[family_id]
        case_rows = [engine_cases[(engine, case_id)] for case_id in members]
        expected_counts = {
            field: sum(
                (
                    source.get(source_field[field]) == "success"
                    if field == "execution_success_case_count"
                    else source.get(source_field[field]) is True
                )
                for source in case_rows
            )
            for field in count_fields
        }
        if (
            row.get("member_case_count") != len(members)
            or any(row.get(field) != count for field, count in expected_counts.items())
            or row.get("covered")
            != (expected_counts["execution_success_case_count"] > 0)
            or row.get("completely_covered")
            != (expected_counts["execution_success_case_count"] == len(members))
        ):
            raise PoseBustersPoseRankingTestPartitionError(
                "proxy engine-family aggregation is inconsistent"
            )
        engine_families[key] = row
    expected_family_keys = {
        (engine, family_id)
        for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
        for family_id in family_members
    }
    if set(engine_families) != expected_family_keys:
        raise PoseBustersPoseRankingTestPartitionError(
            "proxy engine-family denominator is incomplete"
        )

    metric_rows, metric_root = _validated_metric_rows(
        cluster.payload.get("metrics"),
        name="observed-sequence proxy",
        schema_id=POSEBUSTERS_TARGET_CLUSTER_METRIC_SCHEMA_ID,
    )
    if len(metric_rows) != 12 * len(POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES):
        raise PoseBustersPoseRankingTestPartitionError(
            "observed-sequence proxy metric row count is incomplete"
        )
    metrics = _metric_index(
        metric_rows,
        key_fields=("engine_id", "metric_id"),
        name="observed-sequence proxy",
    )
    family_count = len(family_members)
    for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
        rows = [engine_families[(engine, family_id)] for family_id in family_members]
        covered = [row for row in rows if row.get("covered") is True]
        all_metrics = {
            "target_cluster_coverage_rate": sum(
                row.get("covered") is True for row in rows
            ),
            "complete_target_cluster_coverage_rate": sum(
                row.get("completely_covered") is True for row in rows
            ),
            "target_cluster_with_any_top_1_rmsd_hit_rate": sum(
                _integer(
                    row.get("top_1_rmsd_hit_case_count"),
                    name="proxy top-1 count",
                )
                > 0
                for row in rows
            ),
            "target_cluster_with_any_top_5_rmsd_hit_rate": sum(
                _integer(
                    row.get("top_5_rmsd_hit_case_count"),
                    name="proxy top-5 count",
                )
                > 0
                for row in rows
            ),
            "target_cluster_with_any_top_1_valid_rmsd_hit_rate": sum(
                _integer(
                    row.get("top_1_valid_rmsd_hit_case_count"),
                    name="proxy valid top-1 count",
                )
                > 0
                for row in rows
            ),
            "target_cluster_with_any_top_5_valid_rmsd_hit_rate": sum(
                _integer(
                    row.get("top_5_valid_rmsd_hit_case_count"),
                    name="proxy valid top-5 count",
                )
                > 0
                for row in rows
            ),
        }
        covered_fields = {
            "covered_target_cluster_with_any_top_1_physically_valid_rate": (
                "top_1_physically_valid_case_count"
            ),
            "covered_target_cluster_with_any_top_5_physically_valid_rate": (
                "top_5_physically_valid_case_count"
            ),
            "covered_target_cluster_with_any_top_1_rmsd_hit_rate": (
                "top_1_rmsd_hit_case_count"
            ),
            "covered_target_cluster_with_any_top_5_rmsd_hit_rate": (
                "top_5_rmsd_hit_case_count"
            ),
            "covered_target_cluster_with_any_top_1_valid_rmsd_hit_rate": (
                "top_1_valid_rmsd_hit_case_count"
            ),
            "covered_target_cluster_with_any_top_5_valid_rmsd_hit_rate": (
                "top_5_valid_rmsd_hit_case_count"
            ),
        }
        for metric_id, numerator in all_metrics.items():
            _expect_metric(
                metrics,
                (engine, metric_id),
                numerator=numerator,
                denominator=family_count,
                name=f"{engine} {metric_id}",
            )
        for metric_id, field in covered_fields.items():
            _expect_metric(
                metrics,
                (engine, metric_id),
                numerator=sum(
                    _integer(row.get(field), name=f"proxy {field}") > 0
                    for row in covered
                ),
                denominator=len(covered),
                name=f"{engine} {metric_id}",
            )
    return cluster_cases, {
        "source_metric_row_count": len(metric_rows),
        "source_metric_root_sha256": metric_root,
        "observed_sequence_proxy_count": family_count,
        "multi_case_proxy_count": sum(
            len(members) > 1 for members in family_members.values()
        ),
        "maximum_proxy_size": max(map(len, family_members.values())),
        "all_case_denominator": len(case_ids),
        "proxy_semantics": "observed_sequence_proxy_not_biological_family",
        "confidence_interval_method": "wilson_score_binomial",
        "confidence_level": POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CONFIDENCE_LEVEL,
        "validated": True,
    }


def _validate_pfam_metrics(
    target_family: _LoadedReceipt,
    case_ids: Sequence[str],
    engine_cases: Mapping[tuple[str, str], Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    target_case_ids, target_cases = _case_map(
        target_family.payload.get("case_rows"),
        name="RCSB/Pfam target annotation",
    )
    if tuple(case_ids) != target_case_ids:
        raise PoseBustersPoseRankingTestPartitionError(
            "RCSB/Pfam case denominator differs"
        )
    pfam_members: dict[tuple[str, str], tuple[str, ...]] = {}
    for raw in _list(
        target_family.payload.get("pfam_family_rows"),
        name="Pfam family rows",
    ):
        row = _mapping(raw, name="Pfam family row")
        family_id = _text(row.get("pfam_id"), name="Pfam ID")
        members = tuple(
            _case_id(value)
            for value in _list(row.get("member_case_ids"), name="Pfam members")
        )
        expected = tuple(
            case_id
            for case_id in case_ids
            if family_id in target_cases[case_id].get("pfam_ids", [])
        )
        if (
            members != expected
            or row.get("member_case_count") != len(members)
            or not members
        ):
            raise PoseBustersPoseRankingTestPartitionError(
                "Pfam family membership is inconsistent"
            )
        pfam_members[("pfam_multi_label", family_id)] = members
    for raw in _list(
        target_family.payload.get("pfam_set_rows"),
        name="Pfam-set rows",
    ):
        row = _mapping(raw, name="Pfam-set row")
        family_id = _text(row.get("pfam_set_id"), name="Pfam-set ID")
        members = tuple(
            _case_id(value)
            for value in _list(row.get("member_case_ids"), name="Pfam-set members")
        )
        expected = tuple(
            case_id
            for case_id in case_ids
            if target_cases[case_id].get("pfam_set_id") == family_id
        )
        if (
            members != expected
            or row.get("member_case_count") != len(members)
            or not members
        ):
            raise PoseBustersPoseRankingTestPartitionError(
                "Pfam-set membership is inconsistent"
            )
        pfam_members[("pfam_set_partition", family_id)] = members
    if not pfam_members:
        raise PoseBustersPoseRankingTestPartitionError(
            "RCSB/Pfam receipt has no annotated families"
        )

    source_engine_families = [
        _mapping(item, name="Pfam engine family")
        for item in _list(
            target_family.payload.get("engine_family_rows"),
            name="Pfam engine families",
        )
    ]
    engine_families: dict[tuple[str, str, str], dict[str, Any]] = {}
    count_to_case_field = {
        "execution_success_case_count": "execution_status",
        "top_1_rmsd_hit_case_count": "top_1_rmsd_hit",
        "top_1_valid_rmsd_hit_case_count": "top_1_valid_rmsd_hit",
        "top_5_rmsd_hit_case_count": "top_5_rmsd_hit",
        "top_5_valid_rmsd_hit_case_count": "top_5_valid_rmsd_hit",
    }
    for row in source_engine_families:
        engine = _engine(row.get("engine_id"))
        kind = _text(row.get("family_kind"), name="Pfam family kind")
        family_id = _text(row.get("family_id"), name="Pfam engine family ID")
        members = pfam_members.get((kind, family_id))
        key = (engine, kind, family_id)
        if members is None or key in engine_families:
            raise PoseBustersPoseRankingTestPartitionError(
                "Pfam engine-family key is invalid"
            )
        case_rows = [engine_cases[(engine, case_id)] for case_id in members]
        expected_counts = {
            count_field: sum(
                (
                    case_row.get(case_field) == "success"
                    if count_field == "execution_success_case_count"
                    else case_row.get(case_field) is True
                )
                for case_row in case_rows
            )
            for count_field, case_field in count_to_case_field.items()
        }
        if row.get("member_case_count") != len(members) or any(
            row.get(field) != count for field, count in expected_counts.items()
        ):
            raise PoseBustersPoseRankingTestPartitionError(
                "Pfam engine-family aggregation is inconsistent"
            )
        engine_families[key] = row
    expected_keys = {
        (engine, kind, family_id)
        for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
        for kind, family_id in pfam_members
    }
    if set(engine_families) != expected_keys:
        raise PoseBustersPoseRankingTestPartitionError(
            "Pfam engine-family denominator is incomplete"
        )

    metric_rows, metric_root = _validated_metric_rows(
        target_family.payload.get("metrics"),
        name="RCSB/Pfam target-family",
        schema_id=POSEBUSTERS_RCSB_TARGET_METRIC_SCHEMA_ID,
    )
    expected_metric_count = 6 + 5 * len(engine_families)
    if len(metric_rows) != expected_metric_count:
        raise PoseBustersPoseRankingTestPartitionError(
            "RCSB/Pfam metric row count is incomplete"
        )
    metrics = _metric_index(
        metric_rows,
        key_fields=("engine_id", "family_kind", "family_id", "metric_id"),
        name="RCSB/Pfam",
    )
    annotated_count = sum(
        row.get("annotation_status") == "pfam_annotated"
        for row in target_cases.values()
    )
    mapping_complete_count = sum(
        row.get("mapping_status") == "complete" for row in target_cases.values()
    )
    uniprot_count = sum(bool(row.get("uniprot_ids")) for row in target_cases.values())
    removed_count = sum(
        row.get("mapping_status") == "rcsb_entry_removed"
        for row in target_cases.values()
    )
    mapping_failure_count = sum(
        row.get("mapping_status") in _MAPPING_FAILURE_STATUSES
        for row in target_cases.values()
    )
    global_expected = {
        "pocket_chain_mapping_complete_rate": (
            mapping_complete_count,
            len(case_ids),
            "all_cases",
        ),
        "uniprot_annotation_case_rate": (
            uniprot_count,
            len(case_ids),
            "all_cases",
        ),
        "pfam_annotation_case_rate": (
            annotated_count,
            len(case_ids),
            "all_cases",
        ),
        "removed_rcsb_entry_rate": (
            removed_count,
            len(case_ids),
            "all_cases",
        ),
        "pocket_chain_mapping_failure_rate": (
            mapping_failure_count,
            len(case_ids),
            "all_cases",
        ),
        "pfam_annotation_rate_among_mapping_complete_cases": (
            annotated_count,
            mapping_complete_count,
            "mapping_complete_cases",
        ),
    }
    for metric_id, (numerator, denominator, scope) in global_expected.items():
        row = metrics.get((None, "all_case_annotation", "all_cases", metric_id))
        if row is None or row.get("denominator_scope") != scope:
            raise PoseBustersPoseRankingTestPartitionError(
                f"global {metric_id} metric is missing"
            )
        _expect_metric(
            metrics,
            (None, "all_case_annotation", "all_cases", metric_id),
            numerator=numerator,
            denominator=denominator,
            name=metric_id,
        )
    family_metric_to_field = {
        "execution_coverage_rate": "execution_success_case_count",
        "top_1_rmsd_hit_rate_all_family_members": "top_1_rmsd_hit_case_count",
        "top_5_rmsd_hit_rate_all_family_members": "top_5_rmsd_hit_case_count",
        "top_1_valid_rmsd_hit_rate_all_family_members": (
            "top_1_valid_rmsd_hit_case_count"
        ),
        "top_5_valid_rmsd_hit_rate_all_family_members": (
            "top_5_valid_rmsd_hit_case_count"
        ),
    }
    for (engine, kind, family_id), row in engine_families.items():
        denominator = _integer(
            row.get("member_case_count"),
            name="Pfam family denominator",
            minimum=1,
        )
        for metric_id, field in family_metric_to_field.items():
            _expect_metric(
                metrics,
                (engine, kind, family_id, metric_id),
                numerator=_integer(row.get(field), name=f"Pfam {field}"),
                denominator=denominator,
                name=f"{engine} {kind} {family_id} {metric_id}",
            )
    if (
        target_family.payload.get("pfam_annotated_case_count") != annotated_count
        or target_family.payload.get("mapping_complete_case_count")
        != mapping_complete_count
        or target_family.payload.get("uniprot_annotated_case_count") != uniprot_count
        or target_family.payload.get("rcsb_removed_case_count") != removed_count
        or target_family.payload.get("pocket_chain_mapping_failure_case_count")
        != mapping_failure_count
    ):
        raise PoseBustersPoseRankingTestPartitionError(
            "RCSB/Pfam annotation summary is inconsistent"
        )
    status_counts = Counter(
        _text(row.get("annotation_status"), name="annotation status")
        for row in target_cases.values()
    )
    return target_cases, {
        "source_metric_row_count": len(metric_rows),
        "source_metric_root_sha256": metric_root,
        "all_case_denominator": len(case_ids),
        "pfam_annotated_case_count": annotated_count,
        "pfam_missing_case_count": len(case_ids) - annotated_count,
        "pfam_family_count": len(
            [key for key in pfam_members if key[0] == "pfam_multi_label"]
        ),
        "exact_pfam_set_count": len(
            [key for key in pfam_members if key[0] == "pfam_set_partition"]
        ),
        "annotation_status_counts": dict(sorted(status_counts.items())),
        "biological_annotation_complete": annotated_count == len(case_ids),
        "confidence_interval_method": "wilson_score_binomial",
        "confidence_level": POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CONFIDENCE_LEVEL,
        "validated": True,
    }


def _failure_observation_identity(
    *,
    engine_id: str,
    case_id: str,
    source_ranking_row_id: str,
    source_ranking_row_sha256: str,
    failure_code: str,
) -> str:
    return _canonical_sha256(
        {
            "schema_id": POSEBUSTERS_FAILED_POSE_OBSERVATION_IDENTITY_SCHEMA_ID,
            "engine_id": engine_id,
            "case_id": case_id,
            "source_ranking_row_id": source_ranking_row_id,
            "source_ranking_row_sha256": source_ranking_row_sha256,
            "failure_code": failure_code,
        }
    )


def _implementation_source_members() -> tuple[tuple[str, str], ...]:
    calibration_path = getattr(calibration_module, "__file__", None)
    if not isinstance(calibration_path, str):
        raise PoseBustersPoseRankingTestPartitionError(
            "calibration implementation source is unavailable"
        )
    return (
        (
            "posebusters_pose_ranking_test_partition",
            _source_file_sha256(Path(__file__).resolve()),
        ),
        (
            "pose_ranking_calibration_contract",
            _source_file_sha256(Path(calibration_path).resolve()),
        ),
    )


class PoseBustersPoseRankingTestPartitionReceipt:
    """Canonical three-engine test-partition evidence receipt."""

    __slots__ = ("_payload_bytes",)

    def __init__(self, payload: Mapping[str, Any]) -> None:
        candidate = dict(payload)
        if "receipt_sha256" in candidate:
            raise PoseBustersPoseRankingTestPartitionError(
                "test-partition payload must not contain its own digest"
            )
        source = _canonical_bytes(candidate)
        normalized = json.loads(source)
        if (
            normalized.get("schema_id")
            != POSEBUSTERS_POSE_RANKING_TEST_PARTITION_RECEIPT_SCHEMA_ID
            or normalized.get("all_case_denominator")
            != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
            or normalized.get("engine_count")
            != len(POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES)
            or normalized.get("split_role") != "test"
            or normalized.get("test_partition_materialized") is not True
            or normalized.get("calibration_partition_materialized") is not True
            or normalized.get("fit_partition_present") is not False
            or normalized.get("calibration_fit_performed") is not False
            or normalized.get("test_labels_used_for_fit") is not False
            or normalized.get("leakage_audit_present") is not False
            or normalized.get("leakage_control_passed") is not False
            or normalized.get("scientifically_validated") is not False
            or normalized.get("claim_safe") is not False
        ):
            raise PoseBustersPoseRankingTestPartitionError(
                "test-partition payload violates its holdout contract"
            )
        self._payload_bytes = source

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
        return _atomic_write_new(output_path, self.canonical_bytes())


def _build_posebusters_pose_ranking_test_partitions(
    ranking_intake_receipt_path: str | os.PathLike[str],
    pose_scaffold_identity_receipt_path: str | os.PathLike[str],
    target_cluster_receipt_path: str | os.PathLike[str],
    target_family_receipt_path: str | os.PathLike[str],
    *,
    expected_ranking_intake_receipt_sha256: str,
    expected_pose_scaffold_identity_receipt_sha256: str,
    expected_target_cluster_receipt_sha256: str,
    expected_target_family_receipt_sha256: str,
) -> PoseBustersPoseRankingTestPartitionReceipt:
    ranking = _load_source(
        ranking_intake_receipt_path,
        expected_schema_id=POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID,
        expected_receipt_sha256=expected_ranking_intake_receipt_sha256,
        role="pose-ranking intake",
    )
    identity = _load_source(
        pose_scaffold_identity_receipt_path,
        expected_schema_id=(POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_RECEIPT_SCHEMA_ID),
        expected_receipt_sha256=(expected_pose_scaffold_identity_receipt_sha256),
        role="pose/scaffold identity",
    )
    cluster = _load_source(
        target_cluster_receipt_path,
        expected_schema_id=POSEBUSTERS_TARGET_CLUSTER_RECEIPT_SCHEMA_ID,
        expected_receipt_sha256=expected_target_cluster_receipt_sha256,
        role="observed-sequence proxy",
    )
    target_family = _load_source(
        target_family_receipt_path,
        expected_schema_id=POSEBUSTERS_RCSB_TARGET_FAMILY_RECEIPT_SCHEMA_ID,
        expected_receipt_sha256=expected_target_family_receipt_sha256,
        role="RCSB/Pfam target-family",
    )

    expected_configurations = (
        (
            ranking,
            POSEBUSTERS_POSE_RANKING_INTAKE_CONFIGURATION_SHA256,
            "pose-ranking intake",
        ),
        (
            identity,
            POSEBUSTERS_POSE_SCAFFOLD_IDENTITY_CONFIGURATION_SHA256,
            "pose/scaffold identity",
        ),
        (
            cluster,
            POSEBUSTERS_TARGET_CLUSTER_CONFIGURATION_SHA256,
            "observed-sequence proxy",
        ),
        (
            target_family,
            POSEBUSTERS_RCSB_TARGET_FAMILY_CONFIGURATION_SHA256,
            "RCSB/Pfam target-family",
        ),
    )
    for receipt, configuration_sha256, name in expected_configurations:
        if (
            receipt.payload.get("configuration_sha256") != configuration_sha256
            or receipt.payload.get("all_case_denominator")
            != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
        ):
            raise PoseBustersPoseRankingTestPartitionError(
                f"{name} configuration or denominator is invalid"
            )
    if (
        ranking.payload.get("split_role") != "test"
        or ranking.payload.get("test_labels_used_for_fit") is not False
        or ranking.payload.get("calibration_fit_performed") is not False
        or identity.payload.get("split_role") != "test"
        or identity.payload.get("test_labels_used_for_fit") is not False
        or identity.payload.get("pose_coordinate_identity_complete") is not True
        or identity.payload.get("scaffold_identity_complete") is not True
        or identity.payload.get("ranking_intake_identity_binding_complete") is not True
    ):
        raise PoseBustersPoseRankingTestPartitionError(
            "source holdout or identity-completeness contract is invalid"
        )

    ranking_inputs = _input_map(ranking, name="pose-ranking intake")
    identity_inputs = _input_map(identity, name="pose/scaffold identity")
    _require_input(
        identity_inputs,
        "pose_ranking_intake",
        ranking,
        name="pose/scaffold identity",
    )
    _require_input(
        ranking_inputs,
        "rcsb_pfam_target_family",
        target_family,
        name="pose-ranking intake",
    )
    if (
        target_family.payload.get("target_cluster_receipt_sha256")
        != cluster.receipt_sha256
        or cluster.payload.get("archive_intake_receipt_sha256")
        != ranking_inputs.get("archive_intake", {}).get("source_receipt_sha256")
        or target_family.payload.get("archive_intake_receipt_sha256")
        != ranking_inputs.get("archive_intake", {}).get("source_receipt_sha256")
        or cluster.payload.get("preparation_receipt_sha256")
        != ranking_inputs.get("external_preparation", {}).get("source_receipt_sha256")
    ):
        raise PoseBustersPoseRankingTestPartitionError(
            "target proxy/family source chain is inconsistent"
        )
    evaluation_inputs = {
        _engine(row.get("engine_id")): row
        for row in (
            _mapping(item, name="proxy evaluation input")
            for item in _list(
                cluster.payload.get("evaluation_inputs"),
                name="proxy evaluation inputs",
            )
        )
    }
    if set(evaluation_inputs) != set(POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES):
        raise PoseBustersPoseRankingTestPartitionError(
            "proxy evaluation inputs are incomplete"
        )
    for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
        source = evaluation_inputs[engine]
        if (
            source.get("execution_receipt_sha256")
            != ranking_inputs.get(f"{engine}_execution", {}).get(
                "source_receipt_sha256"
            )
            or source.get("evaluation_receipt_sha256")
            != ranking_inputs.get(f"{engine}_evaluation", {}).get(
                "source_receipt_sha256"
            )
            or source.get("evaluation_receipt_file_sha256")
            != ranking_inputs.get(f"{engine}_evaluation", {}).get("source_file_sha256")
        ):
            raise PoseBustersPoseRankingTestPartitionError(
                f"{engine} target-proxy evaluation identity is inconsistent"
            )

    identity_case_ids, identity_cases = _case_map(
        identity.payload.get("case_rows"),
        name="pose/scaffold identity",
    )
    cluster_cases, proxy_metric_validation = _validate_cluster_metrics(
        cluster,
        identity_case_ids,
    )
    cluster_engine_cases = {
        (_engine(row.get("engine_id")), _case_id(row.get("case_id"))): row
        for row in (
            _mapping(item, name="proxy engine case")
            for item in _list(
                cluster.payload.get("engine_case_rows"),
                name="proxy engine cases",
            )
        )
    }
    target_cases, pfam_metric_validation = _validate_pfam_metrics(
        target_family,
        identity_case_ids,
        cluster_engine_cases,
    )

    identity_rows = [
        _mapping(item, name="pose/scaffold identity row")
        for item in _list(
            identity.payload.get("identity_rows"),
            name="pose/scaffold identity rows",
        )
    ]
    identity_by_source: dict[str, dict[str, Any]] = {}
    for row in identity_rows:
        source_id = _text(
            row.get("source_ranking_row_id"),
            name="source ranking row ID",
        )
        if source_id in identity_by_source:
            raise PoseBustersPoseRankingTestPartitionError(
                "pose/scaffold identity source row IDs must be unique"
            )
        identity_by_source[source_id] = row

    ranking_rows = [
        _mapping(item, name="pose-ranking intake row")
        for item in _list(
            ranking.payload.get("intake_rows"),
            name="pose-ranking intake rows",
        )
    ]
    if (
        len(ranking_rows) != len(identity_rows)
        or ranking.payload.get("intake_row_count") != len(ranking_rows)
        or identity.payload.get("identity_row_count") != len(identity_rows)
    ):
        raise PoseBustersPoseRankingTestPartitionError(
            "ranking and identity row denominators differ"
        )
    rows_by_engine: dict[str, list[dict[str, Any]]] = {
        engine: [] for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
    }
    source_row_ids: set[str] = set()
    for row in ranking_rows:
        row_id = _text(row.get("row_id"), name="ranking row ID")
        if row_id in source_row_ids:
            raise PoseBustersPoseRankingTestPartitionError(
                "ranking row IDs must be unique"
            )
        source_row_ids.add(row_id)
        engine = _engine(row.get("engine_id"))
        case_id = _case_id(row.get("case_id"))
        if case_id not in identity_cases:
            raise PoseBustersPoseRankingTestPartitionError(
                "ranking row case is outside the 308-case denominator"
            )
        if row.get("split_role") != "test":
            raise PoseBustersPoseRankingTestPartitionError(
                "every ranking row must remain split_role=test"
            )
        identity_row = identity_by_source.get(row_id)
        source_row_sha = _canonical_sha256(row)
        scaffold_sha = _digest(
            identity_cases[case_id].get("accepted_scaffold_sha256"),
            name="accepted scaffold identity",
        )
        cluster_case = cluster_cases[case_id]
        target_case = target_cases[case_id]
        if (
            identity_row is None
            or identity_row.get("source_ranking_row_sha256") != source_row_sha
            or identity_row.get("engine_id") != engine
            or identity_row.get("case_id") != case_id
            or identity_row.get("accepted_scaffold_sha256") != scaffold_sha
            or row.get("receptor_sha256") != cluster_case.get("receptor_sha256")
            or row.get("receptor_sha256") != target_case.get("receptor_sha256")
            or row.get("reference_ligand_sha256")
            != target_case.get("reference_ligand_sha256")
            or row.get("ligand_start_conformer_sha256")
            != identity_cases[case_id].get("start_ligand_sdf_sha256")
            or row.get("target_id") != target_case.get("pdb_id")
            or row.get("target_family_annotation_status")
            != target_case.get("annotation_status")
            or row.get("target_family_id") != target_case.get("pfam_set_id")
            or row.get("pfam_ids") != target_case.get("pfam_ids")
        ):
            raise PoseBustersPoseRankingTestPartitionError(
                "ranking row identity or target annotation binding is invalid"
            )
        status = _text(row.get("status"), name="ranking row status")
        if status == "success":
            if (
                identity_row.get("status") != "identified_pose"
                or identity_row.get("coordinate_identity_applicable") is not True
                or identity_row.get("pose_rank") != row.get("pose_rank")
                or identity_row.get("pose_artifact_sha256")
                != row.get("pose_artifact_sha256")
                or row.get("native_like") not in (True, False)
                or row.get("failure_code") not in ("", None)
            ):
                raise PoseBustersPoseRankingTestPartitionError(
                    "successful ranking row lacks exact pose identity"
                )
            pose_sha = _digest(
                identity_row.get("pose_coordinate_sha256"),
                name="successful pose-coordinate identity",
            )
            term_ids = [
                _text(value, name="score component ID")
                for value in _list(
                    row.get("score_component_order"),
                    name="score component order",
                )
            ]
            term_values_hex = _list(
                row.get("score_components_binary64_hex"),
                name="score component values",
            )
            if not term_ids or len(term_ids) != len(term_values_hex):
                raise PoseBustersPoseRankingTestPartitionError(
                    "successful score-term projection is incomplete"
                )
            term_values = {
                term_id: _binary64(value, name=f"{term_id} value")
                for term_id, value in zip(term_ids, term_values_hex, strict=True)
            }
            native_like = _boolean(
                row.get("native_like"),
                name="native-like label",
            )
            error_code = ""
        elif status == "failure":
            failure_code = _text(row.get("failure_code"), name="failure code")
            if (
                identity_row.get("status") != "upstream_failure"
                or identity_row.get("coordinate_identity_applicable") is not False
                or identity_row.get("pose_coordinate_sha256") is not None
                or identity_row.get("failure_code") != failure_code
                or row.get("pose_rank") is not None
                or row.get("score_component_order") != []
                or row.get("score_components_binary64_hex") != []
                or row.get("native_like") is not None
            ):
                raise PoseBustersPoseRankingTestPartitionError(
                    "failure row identity or empty-label contract is invalid"
                )
            pose_sha = _failure_observation_identity(
                engine_id=engine,
                case_id=case_id,
                source_ranking_row_id=row_id,
                source_ranking_row_sha256=source_row_sha,
                failure_code=failure_code,
            )
            term_values = {}
            native_like = None
            error_code = failure_code
        else:
            raise PoseBustersPoseRankingTestPartitionError(
                "ranking row status must be success or failure"
            )
        calibration_row = PoseRankingCalibrationRow(
            suite_id=_text(
                ranking.payload.get("dataset_id"),
                name="ranking dataset ID",
            ),
            case_id=case_id,
            pose_id=row_id,
            target_id=_text(row.get("target_id"), name="target ID"),
            target_family=_text(
                cluster_case.get("family_id"),
                name="observed-sequence proxy ID",
            ),
            split_role="test",
            scoring_protocol_sha256=_digest(
                row.get("scoring_protocol_sha256"),
                name="scoring protocol identity",
            ),
            preparation_profile_sha256=_digest(
                row.get("preparation_profile_sha256"),
                name="preparation profile identity",
            ),
            receptor_sha256=_digest(
                row.get("receptor_sha256"),
                name="receptor identity",
            ),
            ligand_sha256=_digest(
                row.get("ligand_start_conformer_sha256"),
                name="ligand identity",
            ),
            scaffold_sha256=scaffold_sha,
            pose_sha256=pose_sha,
            status=status,
            term_values=term_values,
            native_like=native_like,
            error_code=error_code,
        )
        materialized = row.copy()
        materialized["_calibration_row"] = calibration_row
        materialized["_source_row_sha256"] = source_row_sha
        rows_by_engine[engine].append(materialized)
    if set(identity_by_source) != source_row_ids:
        raise PoseBustersPoseRankingTestPartitionError(
            "pose/scaffold identity has rows outside ranking intake"
        )

    ranking_metric_validation = _validate_ranking_metrics(
        ranking,
        rows_by_engine,
    )
    engine_receipts: list[dict[str, Any]] = []
    total_success = 0
    total_failure = 0
    failure_identities: set[str] = set()
    for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
        source_rows = sorted(
            rows_by_engine[engine],
            key=lambda row: (
                _case_id(row.get("case_id")),
                row.get("pose_rank") is None,
                row.get("pose_rank") or 0,
                _text(row.get("row_id"), name="ranking row ID"),
            ),
        )
        calibration_rows = tuple(row["_calibration_row"] for row in source_rows)
        partition = PoseRankingCalibrationPartition(
            dataset_id=(
                f"{_text(ranking.payload.get('dataset_id'), name='dataset ID')}:"
                f"{engine}:failure_inclusive_test"
            ),
            dataset_version=_text(
                ranking.payload.get("dataset_version"),
                name="dataset version",
            ),
            split_role="test",
            rows=calibration_rows,
        )
        if (
            len(partition.case_ids)
            != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
            or partition.case_ids != tuple(identity_case_ids)
        ):
            raise PoseBustersPoseRankingTestPartitionError(
                f"{engine} partition does not retain all 308 cases"
            )
        success_count = sum(row.status == "success" for row in calibration_rows)
        failure_count = sum(row.status == "failure" for row in calibration_rows)
        total_success += success_count
        total_failure += failure_count
        for row in calibration_rows:
            if row.status == "failure":
                if row.pose_sha256 in failure_identities:
                    raise PoseBustersPoseRankingTestPartitionError(
                        "failure observation identities must be globally unique"
                    )
                failure_identities.add(row.pose_sha256)
        engine_receipts.append(
            {
                "schema_id": (POSEBUSTERS_POSE_RANKING_TEST_PARTITION_ENGINE_SCHEMA_ID),
                "engine_id": engine,
                "all_case_denominator": len(partition.case_ids),
                "partition_row_count": len(calibration_rows),
                "successful_pose_row_count": success_count,
                "failure_observation_row_count": failure_count,
                "failure_pose_sha256_semantics": (
                    "domain_separated_failure_observation_identity_not_coordinates"
                ),
                "scoring_protocol_sha256": calibration_rows[0].scoring_protocol_sha256,
                "preparation_profile_sha256": calibration_rows[
                    0
                ].preparation_profile_sha256,
                "source_term_order": _list(
                    next(
                        row for row in source_rows if row.get("status") == "success"
                    ).get("score_component_order"),
                    name="source term order",
                ),
                "partition_fingerprint_sha256": partition.fingerprint_sha256,
                "partition_identity_fingerprint_sha256": (
                    partition.identity_fingerprint_sha256
                ),
                "partition": partition.to_dict(),
                "split_role": "test",
                "test_labels_used_for_fit": False,
                "calibration_fit_performed": False,
            }
        )

    family_member_counts = Counter(
        _text(row.get("family_id"), name="proxy family")
        for row in cluster_cases.values()
    )
    case_rows: list[dict[str, Any]] = []
    for case_id in identity_case_ids:
        identity_case = identity_cases[case_id]
        cluster_case = cluster_cases[case_id]
        target_case = target_cases[case_id]
        proxy_id = _text(
            cluster_case.get("family_id"),
            name="observed-sequence proxy ID",
        )
        case_rows.append(
            {
                "schema_id": (POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CASE_SCHEMA_ID),
                "case_id": case_id,
                "target_id": _text(target_case.get("pdb_id"), name="target ID"),
                "receptor_sha256": _digest(
                    target_case.get("receptor_sha256"),
                    name="receptor identity",
                ),
                "ligand_sha256": _digest(
                    identity_case.get("start_ligand_sdf_sha256"),
                    name="ligand identity",
                ),
                "scaffold_sha256": _digest(
                    identity_case.get("accepted_scaffold_sha256"),
                    name="scaffold identity",
                ),
                "observed_sequence_proxy_id": proxy_id,
                "observed_sequence_proxy_member_case_count": (
                    family_member_counts[proxy_id]
                ),
                "observed_sequence_proxy_semantics": ("not_a_biological_target_family"),
                "target_sequence_set_sha256": _digest(
                    cluster_case.get("target_sequence_set_sha256"),
                    name="target sequence-set identity",
                ),
                "target_chain_sequence_identities": [
                    {
                        "chain_id": _text(
                            chain.get("chain_id"),
                            name="target chain ID",
                        ),
                        "residue_label_sequence_sha256": _digest(
                            chain.get("residue_label_sequence_sha256"),
                            name="target chain sequence identity",
                        ),
                    }
                    for chain in (
                        _mapping(item, name="target chain")
                        for item in _list(
                            cluster_case.get("chains"),
                            name="target chains",
                        )
                    )
                ],
                "biological_annotation_status": _text(
                    target_case.get("annotation_status"),
                    name="biological annotation status",
                ),
                "mapping_status": _text(
                    target_case.get("mapping_status"),
                    name="target mapping status",
                ),
                "pfam_ids": [
                    _text(value, name="Pfam ID")
                    for value in _list(
                        target_case.get("pfam_ids"),
                        name="Pfam IDs",
                    )
                ],
                "pfam_set_id": target_case.get("pfam_set_id"),
                "uniprot_ids": [
                    _text(value, name="UniProt ID")
                    for value in _list(
                        target_case.get("uniprot_ids"),
                        name="UniProt IDs",
                    )
                ],
                "split_role": "test",
            }
        )

    source_members = _implementation_source_members()
    input_receipts = [
        {
            "schema_id": (POSEBUSTERS_POSE_RANKING_TEST_PARTITION_INPUT_SCHEMA_ID),
            "role": role,
            "source_schema_id": receipt.schema_id,
            "source_receipt_sha256": receipt.receipt_sha256,
            "source_file_sha256": receipt.file_sha256,
        }
        for role, receipt in (
            ("pose_ranking_intake", ranking),
            ("pose_scaffold_identity", identity),
            ("observed_sequence_proxy", cluster),
            ("rcsb_pfam_target_family", target_family),
        )
    ]
    payload = {
        "schema_id": (POSEBUSTERS_POSE_RANKING_TEST_PARTITION_RECEIPT_SCHEMA_ID),
        "dataset_id": _text(
            ranking.payload.get("dataset_id"),
            name="dataset ID",
        ),
        "dataset_version": _text(
            ranking.payload.get("dataset_version"),
            name="dataset version",
        ),
        "configuration": POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CONFIGURATION,
        "configuration_sha256": (
            POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CONFIGURATION_SHA256
        ),
        "implementation_source_members": [
            {"role": role, "sha256": digest} for role, digest in source_members
        ],
        "implementation_source_sha256": _canonical_sha256(source_members),
        "input_receipts": input_receipts,
        "all_case_denominator": (POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR),
        "engine_count": len(POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES),
        "split_role": "test",
        "case_rows": case_rows,
        "engine_partitions": engine_receipts,
        "partition_row_count": total_success + total_failure,
        "successful_pose_row_count": total_success,
        "failure_observation_row_count": total_failure,
        "unique_failure_observation_identity_count": len(failure_identities),
        "ranking_metric_validation": ranking_metric_validation,
        "observed_sequence_proxy_metric_validation": proxy_metric_validation,
        "rcsb_pfam_metric_validation": pfam_metric_validation,
        "test_partition_materialized": True,
        "calibration_partition_materialized": True,
        "fit_partition_present": False,
        "fit_or_training_manifest_present": False,
        "calibration_fit_performed": False,
        "test_labels_used_for_fit": False,
        "leakage_audit_present": False,
        "leakage_control_passed": False,
        "independent_external_rerun_present": False,
        "independent_scientific_review_present": False,
        "biological_target_family_annotation_complete": (
            pfam_metric_validation["biological_annotation_complete"]
        ),
        "scientific_blockers": list(
            POSEBUSTERS_POSE_RANKING_TEST_PARTITION_SCIENTIFIC_BLOCKERS
        ),
        "public_pose_ranking_calibration_claim_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return PoseBustersPoseRankingTestPartitionReceipt(payload)


def materialize_posebusters_pose_ranking_test_partitions(
    ranking_intake_receipt_path: str | os.PathLike[str],
    pose_scaffold_identity_receipt_path: str | os.PathLike[str],
    target_cluster_receipt_path: str | os.PathLike[str],
    target_family_receipt_path: str | os.PathLike[str],
    *,
    expected_ranking_intake_receipt_sha256: str,
    expected_pose_scaffold_identity_receipt_sha256: str,
    expected_target_cluster_receipt_sha256: str,
    expected_target_family_receipt_sha256: str,
) -> PoseBustersPoseRankingTestPartitionReceipt:
    """Build exact three-engine, failure-inclusive test partitions."""

    return _build_posebusters_pose_ranking_test_partitions(
        ranking_intake_receipt_path,
        pose_scaffold_identity_receipt_path,
        target_cluster_receipt_path,
        target_family_receipt_path,
        expected_ranking_intake_receipt_sha256=(expected_ranking_intake_receipt_sha256),
        expected_pose_scaffold_identity_receipt_sha256=(
            expected_pose_scaffold_identity_receipt_sha256
        ),
        expected_target_cluster_receipt_sha256=(expected_target_cluster_receipt_sha256),
        expected_target_family_receipt_sha256=(expected_target_family_receipt_sha256),
    )


def verify_posebusters_pose_ranking_test_partition_receipt(
    test_partition_receipt_path: str | os.PathLike[str],
    ranking_intake_receipt_path: str | os.PathLike[str],
    pose_scaffold_identity_receipt_path: str | os.PathLike[str],
    target_cluster_receipt_path: str | os.PathLike[str],
    target_family_receipt_path: str | os.PathLike[str],
    *,
    expected_ranking_intake_receipt_sha256: str,
    expected_pose_scaffold_identity_receipt_sha256: str,
    expected_target_cluster_receipt_sha256: str,
    expected_target_family_receipt_sha256: str,
) -> PoseBustersPoseRankingTestPartitionReceipt:
    """Require byte equality with an exact reconstruction of every source."""

    try:
        source = _read_exact_regular_file(
            test_partition_receipt_path,
            maximum_bytes=(POSEBUSTERS_POSE_RANKING_TEST_PARTITION_MAX_RECEIPT_BYTES),
        )
        metadata = Path(test_partition_receipt_path).stat(follow_symlinks=False)
    except (OSError, PoseBustersArchiveIntakeError) as exc:
        raise PoseBustersPoseRankingTestPartitionError(
            "test-partition output could not be read securely"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersPoseRankingTestPartitionError(
            "test-partition output must be a bounded mode-0600 regular file"
        )
    expected = _build_posebusters_pose_ranking_test_partitions(
        ranking_intake_receipt_path,
        pose_scaffold_identity_receipt_path,
        target_cluster_receipt_path,
        target_family_receipt_path,
        expected_ranking_intake_receipt_sha256=(expected_ranking_intake_receipt_sha256),
        expected_pose_scaffold_identity_receipt_sha256=(
            expected_pose_scaffold_identity_receipt_sha256
        ),
        expected_target_cluster_receipt_sha256=(expected_target_cluster_receipt_sha256),
        expected_target_family_receipt_sha256=(expected_target_family_receipt_sha256),
    )
    if source != expected.canonical_bytes():
        raise PoseBustersPoseRankingTestPartitionError(
            "test-partition output differs from exact reconstruction"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-ranking-test-partitions",
        description=(
            "Materialize exact failure-inclusive Vina/GNINA/Smina "
            "PoseBusters split_role=test calibration partitions without "
            "fitting a scorer."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--ranking-intake-receipt", required=True)
        subparser.add_argument(
            "--expected-ranking-intake-receipt-sha256",
            required=True,
        )
        subparser.add_argument("--pose-scaffold-identity-receipt", required=True)
        subparser.add_argument(
            "--expected-pose-scaffold-identity-receipt-sha256",
            required=True,
        )
        subparser.add_argument("--target-cluster-receipt", required=True)
        subparser.add_argument(
            "--expected-target-cluster-receipt-sha256",
            required=True,
        )
        subparser.add_argument("--target-family-receipt", required=True)
        subparser.add_argument(
            "--expected-target-family-receipt-sha256",
            required=True,
        )
    subparsers.choices["materialize"].add_argument("--output", required=True)
    subparsers.choices["verify"].add_argument(
        "--test-partition-receipt",
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = {
        "ranking_intake_receipt_path": args.ranking_intake_receipt,
        "pose_scaffold_identity_receipt_path": (args.pose_scaffold_identity_receipt),
        "target_cluster_receipt_path": args.target_cluster_receipt,
        "target_family_receipt_path": args.target_family_receipt,
        "expected_ranking_intake_receipt_sha256": (
            args.expected_ranking_intake_receipt_sha256
        ),
        "expected_pose_scaffold_identity_receipt_sha256": (
            args.expected_pose_scaffold_identity_receipt_sha256
        ),
        "expected_target_cluster_receipt_sha256": (
            args.expected_target_cluster_receipt_sha256
        ),
        "expected_target_family_receipt_sha256": (
            args.expected_target_family_receipt_sha256
        ),
    }
    if args.command == "materialize":
        receipt = materialize_posebusters_pose_ranking_test_partitions(**common)
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_pose_ranking_test_partition_receipt(
            test_partition_receipt_path=args.test_partition_receipt,
            **common,
        )
    payload = receipt.to_dict()
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": payload["all_case_denominator"],
                "engine_count": payload["engine_count"],
                "partition_row_count": payload["partition_row_count"],
                "successful_pose_row_count": payload["successful_pose_row_count"],
                "failure_observation_row_count": payload[
                    "failure_observation_row_count"
                ],
                "test_partition_materialized": True,
                "calibration_fit_performed": False,
                "test_labels_used_for_fit": False,
                "leakage_control_passed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_FAILED_POSE_OBSERVATION_IDENTITY_SCHEMA_ID",
    "POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CASE_SCHEMA_ID",
    "POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CONFIGURATION",
    "POSEBUSTERS_POSE_RANKING_TEST_PARTITION_CONFIGURATION_SHA256",
    "POSEBUSTERS_POSE_RANKING_TEST_PARTITION_ENGINE_SCHEMA_ID",
    "POSEBUSTERS_POSE_RANKING_TEST_PARTITION_INPUT_SCHEMA_ID",
    "POSEBUSTERS_POSE_RANKING_TEST_PARTITION_RECEIPT_SCHEMA_ID",
    "POSEBUSTERS_POSE_RANKING_TEST_PARTITION_SCIENTIFIC_BLOCKERS",
    "PoseBustersPoseRankingTestPartitionError",
    "PoseBustersPoseRankingTestPartitionReceipt",
    "main",
    "materialize_posebusters_pose_ranking_test_partitions",
    "verify_posebusters_pose_ranking_test_partition_receipt",
]


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
