"""Preregister and compare a second-host PoseBusters ranking rerun.

Same-host exact reconstruction is useful protocol evidence, but it is not an
independent rerun.  This module binds the accepted 308-case baseline, an exact
Engine v2 wheel, role-separated host/operator identities, and a single-use
nonce before an external observation.  A result must be reconstructed from a
new ranking-intake/test-partition/evaluation chain that reuses the fixed public
inputs while replacing every engine execution and evaluation evidence root.

The comparison retains all 924 engine/case outcomes and all failed cases.
Physical-host independence and nonce single-use remain reviewer attestations;
therefore even a passing cross-host comparison is claim-closed until a
separate trusted review is attached.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import stat
import sys
import tempfile
from typing import Any
import zipfile

import betelgeuze_engine_v2.docking.calibration as calibration_module

from . import public_posebusters_external_ranking_evaluation as evaluation_module
from . import public_posebusters_pose_ranking_test_partition as partition_module
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
    POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID,
)
from .public_posebusters_pose_ranking_test_partition import (
    POSEBUSTERS_POSE_RANKING_TEST_PARTITION_RECEIPT_SCHEMA_ID,
)


POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_WORK_ORDER_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_ranking_reproduction_work_order/1.0.0"
)
POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_RUNTIME_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_ranking_reproduction_runtime/1.0.0"
)
POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_ranking_reproduction_case/1.0.0"
)
POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_ENGINE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_ranking_reproduction_engine/1.0.0"
)
POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_COMPARISON_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_ranking_cross_host_comparison/1.0.0"
)
POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_external_ranking_reproduction_result/1.0.0"
)

POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_INPUT_BYTES = 64 * 1024 * 1024
POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_WORK_ORDER_BYTES = 8 * 1024 * 1024
POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_RESULT_BYTES = 32 * 1024 * 1024
POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_WHEEL_BYTES = 16 * 1024 * 1024
POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_WHEEL_MEMBERS = 4096

_ENGINES = ("vina", "gnina", "smina")
_FIXED_INPUT_ROLES = (
    "archive_intake",
    "external_preparation",
    "rcsb_pfam_target_family",
)
_ENGINE_EVIDENCE_ROLES = (
    "vina_execution",
    "vina_evaluation",
    "gnina_execution",
    "gnina_evaluation",
    "smina_execution",
    "smina_evaluation",
)
_REQUIRED_ENTRYPOINTS = (
    "betelgeuze-engine-v2-posebusters-vina-execute",
    "betelgeuze-engine-v2-posebusters-external-execute",
    "betelgeuze-engine-v2-posebusters-evaluate-generated",
    "betelgeuze-engine-v2-posebusters-external-evaluate-generated",
    "betelgeuze-engine-v2-posebusters-ranking-intake",
    "betelgeuze-engine-v2-posebusters-ranking-test-partitions",
    "betelgeuze-engine-v2-posebusters-external-ranking-evaluate",
)

POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CONFIGURATION = {
    "all_case_denominator": 308,
    "engine_count": 3,
    "case_comparison_count": 924,
    "split_role": "test",
    "fixed_input_roles": list(_FIXED_INPUT_ROLES),
    "engine_evidence_roles_requiring_new_receipt_roots": list(_ENGINE_EVIDENCE_ROLES),
    "required_entrypoints": list(_REQUIRED_ENTRYPOINTS),
    "score_absolute_tolerances": {
        "vina": float(1.0e-4).hex(),
        "gnina": float(1.0e-6).hex(),
        "smina": float(1.0e-4).hex(),
    },
    "average_precision_absolute_tolerance": float(1.0e-8).hex(),
    "exact_case_invariants": [
        "ordered_case_identity_and_family_annotation",
        "case_status_and_all_failure_codes",
        "successful_pose_count_and_source_rank_sequence",
        "native_like_label_sequence",
        "top1_and_top5_tie_inclusive_outcomes",
        "ratio_metric_numerators_and_denominators",
        "source_bound_physical_validity_counts",
        "family_membership_and_ratio_metric_counts",
    ],
    "host_policy": {
        "baseline_and_external_host_identities_preregistered": True,
        "baseline_and_external_host_identities_distinct": True,
        "operator_and_executor_identities_role_separated": True,
        "single_use_external_execution_nonce_preregistered": True,
        "physical_host_independence_requires_external_review": True,
        "nonce_single_use_requires_external_registry_review": True,
    },
    "claim_policy": {
        "same_host_exact_verify_is_independent_rerun": False,
        "passing_unreviewed_comparison_authorizes_claim": False,
        "test_label_fit_or_policy_selection_allowed": False,
    },
}
POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CONFIGURATION_SHA256 = _canonical_sha256(
    POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CONFIGURATION
)

POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_SCIENTIFIC_BLOCKERS = (
    "physical_host_independence_review_missing",
    "external_execution_nonce_single_use_registry_review_missing",
    "external_executor_and_host_custody_review_missing",
    "external_model_training_overlap_audit_missing",
    "only_strictly_prepared_chemistry_subset_has_scored_poses",
    "all_case_execution_coverage_is_incomplete",
    "internal_product_scorer_not_evaluated",
    "independent_scientific_review_missing",
    "public_docking_product_claim_not_authorized",
)

_LOWERCASE_SHA256 = frozenset("0123456789abcdef")
_WORK_ORDER_FLAGS = {
    "external_execution_performed": False,
    "cross_host_comparison_present": False,
    "physical_host_independence_reviewed": False,
    "independent_external_rerun_present": False,
    "independent_reviewer_receipt_approved": False,
    "scientifically_validated": False,
    "public_docking_claim_authorized": False,
    "claim_safe": False,
}
_RESULT_FLAGS = {
    "external_execution_performed": True,
    "cross_host_comparison_present": True,
    "physical_host_independence_reviewed": False,
    "independent_external_rerun_present": False,
    "independent_reviewer_receipt_approved": False,
    "scientifically_validated": False,
    "public_docking_claim_authorized": False,
    "claim_safe": False,
}


class PoseBustersExternalRankingReproductionError(ValueError):
    """The rerun work order, source chain, comparison, or result is invalid."""


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


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PoseBustersExternalRankingReproductionError(f"{name} must be a mapping")
    return dict(value)


def _list(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PoseBustersExternalRankingReproductionError(f"{name} must be a list")
    return value


def _text(
    value: object,
    *,
    name: str,
    maximum: int = 512,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > maximum
        or any(character in "\r\n\x00" for character in value)
    ):
        raise PoseBustersExternalRankingReproductionError(
            f"{name} must be bounded single-line text"
        )
    return value


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _LOWERCASE_SHA256 for character in value)
    ):
        raise PoseBustersExternalRankingReproductionError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _integer(value: object, *, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise PoseBustersExternalRankingReproductionError(
            f"{name} must be an integer >= {minimum}"
        )
    return value


def _boolean(value: object, *, name: str) -> bool:
    if type(value) is not bool:
        raise PoseBustersExternalRankingReproductionError(f"{name} must be boolean")
    return value


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PoseBustersExternalRankingReproductionError(
            f"{name} must be a finite number"
        )
    number = float(value)
    if not math.isfinite(number):
        raise PoseBustersExternalRankingReproductionError(
            f"{name} must be a finite number"
        )
    return number


def _hex_float(value: object, *, name: str) -> float:
    text = _text(value, name=name, maximum=128)
    try:
        number = float.fromhex(text)
    except ValueError as exc:
        raise PoseBustersExternalRankingReproductionError(
            f"{name} must be binary64 hexadecimal"
        ) from exc
    if not math.isfinite(number) or number.hex() != text:
        raise PoseBustersExternalRankingReproductionError(
            f"{name} must be canonical finite binary64 hexadecimal"
        )
    return number


def _utc(value: object, *, name: str) -> str:
    text = _text(value, name=name, maximum=32)
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise PoseBustersExternalRankingReproductionError(
            f"{name} must use canonical UTC seconds"
        ) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != text:
        raise PoseBustersExternalRankingReproductionError(
            f"{name} must use canonical UTC seconds"
        )
    return text


def _utc_datetime(value: object, *, name: str) -> datetime:
    return datetime.strptime(_utc(value, name=name), "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )


def _load_receipt(
    path: str | os.PathLike[str],
    *,
    expected_schema_id: str,
    expected_receipt_sha256: str,
    maximum_bytes: int = (POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_INPUT_BYTES),
) -> _LoadedReceipt:
    expected = _digest(expected_receipt_sha256, name="expected receipt")
    try:
        source = _read_exact_regular_file(path, maximum_bytes=maximum_bytes)
        metadata = Path(path).stat(follow_symlinks=False)
    except (OSError, PoseBustersArchiveIntakeError) as exc:
        raise PoseBustersExternalRankingReproductionError(
            "receipt could not be read securely"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersExternalRankingReproductionError(
            "receipt must be a bounded mode-0600 regular file"
        )
    try:
        raw = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersExternalRankingReproductionError(
            "receipt is not canonical JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersExternalRankingReproductionError(
            "receipt bytes are not canonical"
        )
    payload = dict(raw)
    receipt_sha = _digest(payload.pop("receipt_sha256", None), name="receipt")
    if (
        raw.get("schema_id") != expected_schema_id
        or _canonical_sha256(payload) != receipt_sha
        or receipt_sha != expected
    ):
        raise PoseBustersExternalRankingReproductionError(
            "receipt schema, digest, or pin is invalid"
        )
    return _LoadedReceipt(
        payload=raw,
        receipt_sha256=receipt_sha,
        file_sha256=hashlib.sha256(source).hexdigest(),
        source=source,
    )


def _source_members() -> tuple[tuple[str, str, str], ...]:
    paths = (
        (
            "posebusters_external_ranking_reproduction",
            Path(__file__).resolve(),
            "betelgeuze_engine_v2/benchmark/"
            "public_posebusters_external_ranking_reproduction.py",
        ),
        (
            "posebusters_external_ranking_evaluation",
            Path(evaluation_module.__file__).resolve(),
            "betelgeuze_engine_v2/benchmark/"
            "public_posebusters_external_ranking_evaluation.py",
        ),
        (
            "posebusters_pose_ranking_test_partition",
            Path(partition_module.__file__).resolve(),
            "betelgeuze_engine_v2/benchmark/"
            "public_posebusters_pose_ranking_test_partition.py",
        ),
        (
            "pose_ranking_calibration_contract",
            Path(calibration_module.__file__).resolve(),
            "betelgeuze_engine_v2/docking/calibration.py",
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
        raise PoseBustersExternalRankingReproductionError(
            f"{name} cannot be inspected"
        ) from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_size <= 0
        or metadata.st_size > maximum_bytes
    ):
        raise PoseBustersExternalRankingReproductionError(
            f"{name} must be a bounded non-empty regular file"
        )
    try:
        source = candidate.read_bytes()
    except OSError as exc:
        raise PoseBustersExternalRankingReproductionError(
            f"{name} cannot be read"
        ) from exc
    if len(source) != metadata.st_size:
        raise PoseBustersExternalRankingReproductionError(
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
        maximum_bytes=POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_WHEEL_BYTES,
        name="Engine v2 wheel",
    )
    if observed_sha != _digest(expected_wheel_sha256, name="expected wheel"):
        raise PoseBustersExternalRankingReproductionError(
            "Engine v2 wheel digest changed"
        )
    expected_members = _source_members()
    try:
        with zipfile.ZipFile(candidate) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len(
                members
            ) > POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_WHEEL_MEMBERS or len(
                names
            ) != len(set(names)):
                raise PoseBustersExternalRankingReproductionError(
                    "Engine v2 wheel member ledger is invalid"
                )
            for name in names:
                pure = PurePosixPath(name)
                if pure.is_absolute() or ".." in pure.parts:
                    raise PoseBustersExternalRankingReproductionError(
                        "Engine v2 wheel contains an unsafe member path"
                    )
            bound_members = []
            for role, expected_sha, member_path in expected_members:
                try:
                    member_source = archive.read(member_path)
                except KeyError as exc:
                    raise PoseBustersExternalRankingReproductionError(
                        "Engine v2 wheel is missing a reproduction source member"
                    ) from exc
                member_sha = hashlib.sha256(member_source).hexdigest()
                if member_sha != expected_sha:
                    raise PoseBustersExternalRankingReproductionError(
                        "Engine v2 wheel source differs from the active implementation"
                    )
                bound_members.append(
                    {
                        "role": role,
                        "wheel_member_path": member_path,
                        "sha256": member_sha,
                        "size_bytes": len(member_source),
                    }
                )
    except (OSError, zipfile.BadZipFile) as exc:
        raise PoseBustersExternalRankingReproductionError(
            "Engine v2 wheel is not a readable ZIP archive"
        ) from exc
    return {
        "filename": candidate.name,
        "sha256": observed_sha,
        "size_bytes": len(source),
        "bound_source_members": bound_members,
        "bound_source_member_count": len(bound_members),
    }


def _atomic_write_new(
    path: str | os.PathLike[str],
    source: bytes,
    *,
    maximum_bytes: int,
) -> Path:
    if len(source) > maximum_bytes:
        raise PoseBustersExternalRankingReproductionError(
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
            raise PoseBustersExternalRankingReproductionError(
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


def _input_receipt_rows(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for value in _list(payload.get("input_receipts"), name="input receipts"):
        row = _mapping(value, name="input receipt")
        role = _text(row.get("role"), name="input receipt role")
        if role in rows:
            raise PoseBustersExternalRankingReproductionError(
                "input receipt roles must be unique"
            )
        rows[role] = {
            "role": role,
            "source_schema_id": _text(
                row.get("source_schema_id"),
                name=f"{role} source schema",
            ),
            "source_receipt_sha256": _digest(
                row.get("source_receipt_sha256"),
                name=f"{role} source receipt",
            ),
            "source_file_sha256": _digest(
                row.get("source_file_sha256"),
                name=f"{role} source file",
            ),
        }
    expected = set(_FIXED_INPUT_ROLES) | set(_ENGINE_EVIDENCE_ROLES)
    if set(rows) != expected:
        raise PoseBustersExternalRankingReproductionError(
            "ranking intake input receipt roles are incomplete"
        )
    return rows


def _partition_input_rows(
    payload: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for value in _list(payload.get("input_receipts"), name="partition inputs"):
        row = _mapping(value, name="partition input")
        role = _text(row.get("role"), name="partition input role")
        if role in rows:
            raise PoseBustersExternalRankingReproductionError(
                "partition input roles must be unique"
            )
        rows[role] = {
            "role": role,
            "source_schema_id": _text(
                row.get("source_schema_id"),
                name=f"{role} source schema",
            ),
            "source_receipt_sha256": _digest(
                row.get("source_receipt_sha256"),
                name=f"{role} source receipt",
            ),
            "source_file_sha256": _digest(
                row.get("source_file_sha256"),
                name=f"{role} source file",
            ),
        }
    return rows


def _ranking_chain(
    evaluation_receipt_path: str | os.PathLike[str],
    test_partition_receipt_path: str | os.PathLike[str],
    ranking_intake_receipt_path: str | os.PathLike[str],
    *,
    expected_evaluation_receipt_sha256: str,
    expected_test_partition_receipt_sha256: str,
    expected_ranking_intake_receipt_sha256: str,
) -> dict[str, Any]:
    evaluation_loaded = _load_receipt(
        evaluation_receipt_path,
        expected_schema_id=(
            evaluation_module.POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_RECEIPT_SCHEMA_ID
        ),
        expected_receipt_sha256=expected_evaluation_receipt_sha256,
    )
    try:
        verified = (
            evaluation_module.verify_posebusters_external_ranking_evaluation_receipt(
                evaluation_receipt_path,
                test_partition_receipt_path,
                expected_test_partition_receipt_sha256=(
                    expected_test_partition_receipt_sha256
                ),
            )
        )
    except evaluation_module.PoseBustersExternalRankingEvaluationError as exc:
        raise PoseBustersExternalRankingReproductionError(
            "external ranking evaluation failed exact reconstruction"
        ) from exc
    if verified.fingerprint_sha256 != evaluation_loaded.receipt_sha256:
        raise PoseBustersExternalRankingReproductionError(
            "external ranking evaluation pin is inconsistent"
        )
    partition = _load_receipt(
        test_partition_receipt_path,
        expected_schema_id=(POSEBUSTERS_POSE_RANKING_TEST_PARTITION_RECEIPT_SCHEMA_ID),
        expected_receipt_sha256=expected_test_partition_receipt_sha256,
    )
    intake = _load_receipt(
        ranking_intake_receipt_path,
        expected_schema_id=POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID,
        expected_receipt_sha256=expected_ranking_intake_receipt_sha256,
    )
    partition_inputs = _partition_input_rows(partition.payload)
    ranking_input = partition_inputs.get("pose_ranking_intake")
    if (
        ranking_input is None
        or ranking_input["source_receipt_sha256"] != intake.receipt_sha256
        or ranking_input["source_file_sha256"] != intake.file_sha256
    ):
        raise PoseBustersExternalRankingReproductionError(
            "test partition is not bound to the supplied ranking intake"
        )
    evaluation_input = _mapping(
        evaluation_loaded.payload.get("input_receipt"),
        name="evaluation input receipt",
    )
    if (
        evaluation_input.get("source_receipt_sha256") != partition.receipt_sha256
        or evaluation_input.get("source_file_sha256") != partition.file_sha256
    ):
        raise PoseBustersExternalRankingReproductionError(
            "ranking evaluation is not bound to the supplied test partition"
        )
    if (
        evaluation_loaded.payload.get("all_case_denominator") != 308
        or evaluation_loaded.payload.get("engine_count") != 3
        or evaluation_loaded.payload.get("split_role") != "test"
        or evaluation_loaded.payload.get("claim_safe") is not False
        or partition.payload.get("all_case_denominator") != 308
        or partition.payload.get("split_role") != "test"
        or partition.payload.get("claim_safe") is not False
        or intake.payload.get("all_case_denominator") != 308
        or intake.payload.get("split_role") != "test"
        or intake.payload.get("claim_safe") is not False
    ):
        raise PoseBustersExternalRankingReproductionError(
            "ranking chain violates the claim-closed 308-case test boundary"
        )
    intake_inputs = _input_receipt_rows(intake.payload)
    return {
        "evaluation": evaluation_loaded,
        "partition": partition,
        "intake": intake,
        "intake_inputs": intake_inputs,
    }


def _chain_binding(chain: Mapping[str, Any]) -> dict[str, Any]:
    evaluation = chain["evaluation"]
    partition = chain["partition"]
    intake = chain["intake"]
    return {
        "ranking_intake_receipt_sha256": intake.receipt_sha256,
        "ranking_intake_file_sha256": intake.file_sha256,
        "ranking_intake_configuration_sha256": _digest(
            intake.payload.get("configuration_sha256"),
            name="ranking intake configuration",
        ),
        "ranking_intake_implementation_sha256": _digest(
            intake.payload.get("implementation_source_sha256"),
            name="ranking intake implementation",
        ),
        "test_partition_receipt_sha256": partition.receipt_sha256,
        "test_partition_file_sha256": partition.file_sha256,
        "test_partition_configuration_sha256": _digest(
            partition.payload.get("configuration_sha256"),
            name="test partition configuration",
        ),
        "test_partition_implementation_sha256": _digest(
            partition.payload.get("implementation_source_sha256"),
            name="test partition implementation",
        ),
        "evaluation_receipt_sha256": evaluation.receipt_sha256,
        "evaluation_file_sha256": evaluation.file_sha256,
        "evaluation_configuration_sha256": _digest(
            evaluation.payload.get("configuration_sha256"),
            name="ranking evaluation configuration",
        ),
        "evaluation_implementation_sha256": _digest(
            evaluation.payload.get("implementation_source_sha256"),
            name="ranking evaluation implementation",
        ),
    }


def _baseline_summary(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    results = {
        _text(row.get("engine_id"), name="engine ID"): row
        for row in (
            _mapping(item, name="engine result")
            for item in _list(
                evaluation.get("engine_results"),
                name="engine results",
            )
        )
    }
    if tuple(results) != _ENGINES:
        raise PoseBustersExternalRankingReproductionError(
            "engine results must retain canonical order"
        )
    return {
        "all_case_denominator": 308,
        "engine_count": 3,
        "total_successful_pose_count": _integer(
            evaluation.get("total_successful_pose_count"),
            name="total successful pose count",
        ),
        "total_failure_observation_count": _integer(
            evaluation.get("total_failure_observation_count"),
            name="total failure observation count",
        ),
        "engine_rows": [
            {
                "engine_id": engine,
                "scored_case_count": _integer(
                    results[engine].get("scored_case_count"),
                    name=f"{engine} scored cases",
                ),
                "failure_case_count": _integer(
                    results[engine].get("failure_case_count"),
                    name=f"{engine} failure cases",
                ),
                "successful_pose_count": _integer(
                    results[engine].get("successful_pose_count"),
                    name=f"{engine} successful poses",
                ),
                "failure_observation_count": _integer(
                    results[engine].get("failure_observation_count"),
                    name=f"{engine} failure observations",
                ),
            }
            for engine in _ENGINES
        ],
    }


class PoseBustersExternalRankingReproductionWorkOrder:
    """Canonical preregistration for one external-host ranking rerun."""

    __slots__ = ("_payload_bytes",)

    def __init__(self, payload: Mapping[str, Any]) -> None:
        candidate = dict(payload)
        if "receipt_sha256" in candidate:
            raise PoseBustersExternalRankingReproductionError(
                "work-order payload must not contain its own digest"
            )
        source = _canonical_bytes(candidate)
        normalized = json.loads(source)
        if (
            normalized.get("schema_id")
            != POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_WORK_ORDER_SCHEMA_ID
            or normalized.get("configuration_sha256")
            != POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CONFIGURATION_SHA256
            or normalized.get("all_case_denominator") != 308
            or normalized.get("engine_count") != 3
            or normalized.get("split_role") != "test"
            or any(
                normalized.get(key) is not expected
                for key, expected in _WORK_ORDER_FLAGS.items()
            )
        ):
            raise PoseBustersExternalRankingReproductionError(
                "work-order payload violates its preregistration boundary"
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
        return _atomic_write_new(
            output_path,
            self.canonical_bytes(),
            maximum_bytes=(
                POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_WORK_ORDER_BYTES
            ),
        )


def materialize_posebusters_external_ranking_reproduction_work_order(
    baseline_evaluation_receipt_path: str | os.PathLike[str],
    baseline_test_partition_receipt_path: str | os.PathLike[str],
    baseline_ranking_intake_receipt_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    *,
    expected_baseline_evaluation_receipt_sha256: str,
    expected_baseline_test_partition_receipt_sha256: str,
    expected_baseline_ranking_intake_receipt_sha256: str,
    expected_engine_wheel_sha256: str,
    baseline_host_identity_sha256: str,
    expected_external_host_identity_sha256: str,
    work_order_operator_identity_sha256: str,
    external_execution_operator_identity_sha256: str,
    external_execution_nonce_sha256: str,
    registered_utc: str,
) -> PoseBustersExternalRankingReproductionWorkOrder:
    """Preregister one role-separated second-host rerun without executing it."""

    chain = _ranking_chain(
        baseline_evaluation_receipt_path,
        baseline_test_partition_receipt_path,
        baseline_ranking_intake_receipt_path,
        expected_evaluation_receipt_sha256=(
            expected_baseline_evaluation_receipt_sha256
        ),
        expected_test_partition_receipt_sha256=(
            expected_baseline_test_partition_receipt_sha256
        ),
        expected_ranking_intake_receipt_sha256=(
            expected_baseline_ranking_intake_receipt_sha256
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
        raise PoseBustersExternalRankingReproductionError(
            "host and operator identities must be role-separated"
        )
    nonce = _digest(
        external_execution_nonce_sha256,
        name="external execution nonce",
    )
    if nonce in identities:
        raise PoseBustersExternalRankingReproductionError(
            "external execution nonce must not reuse an identity"
        )
    source_members = _source_members()
    payload = {
        "schema_id": (POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_WORK_ORDER_SCHEMA_ID),
        "registered_utc": _utc(
            registered_utc,
            name="work-order registration UTC",
        ),
        "baseline_chain": _chain_binding(chain),
        "fixed_input_receipts": [
            dict(chain["intake_inputs"][role]) for role in _FIXED_INPUT_ROLES
        ],
        "baseline_engine_evidence_receipts": [
            dict(chain["intake_inputs"][role]) for role in _ENGINE_EVIDENCE_ROLES
        ],
        "baseline_summary": _baseline_summary(chain["evaluation"].payload),
        "baseline_host_identity_sha256": identities[0],
        "expected_external_host_identity_sha256": identities[1],
        "work_order_operator_identity_sha256": identities[2],
        "external_execution_operator_identity_sha256": identities[3],
        "external_execution_nonce_sha256": nonce,
        "engine_wheel_binding": _wheel_binding(
            engine_wheel_path,
            expected_wheel_sha256=expected_engine_wheel_sha256,
        ),
        "required_entrypoints": list(_REQUIRED_ENTRYPOINTS),
        "implementation_source_members": [
            {
                "role": role,
                "sha256": digest,
                "wheel_member_path": wheel_member_path,
            }
            for role, digest, wheel_member_path in source_members
        ],
        "implementation_source_sha256": _canonical_sha256(source_members),
        "configuration": (POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CONFIGURATION),
        "configuration_sha256": (
            POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CONFIGURATION_SHA256
        ),
        "all_case_denominator": 308,
        "engine_count": 3,
        "split_role": "test",
        "same_public_input_receipts_required": True,
        "new_engine_evidence_receipt_roots_required": True,
        "test_label_fit_or_policy_selection_allowed": False,
        **_WORK_ORDER_FLAGS,
    }
    return PoseBustersExternalRankingReproductionWorkOrder(payload)


def verify_posebusters_external_ranking_reproduction_work_order(
    work_order_path: str | os.PathLike[str],
    baseline_evaluation_receipt_path: str | os.PathLike[str],
    baseline_test_partition_receipt_path: str | os.PathLike[str],
    baseline_ranking_intake_receipt_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    *,
    expected_work_order_receipt_sha256: str,
    expected_baseline_evaluation_receipt_sha256: str,
    expected_baseline_test_partition_receipt_sha256: str,
    expected_baseline_ranking_intake_receipt_sha256: str,
    expected_engine_wheel_sha256: str,
) -> PoseBustersExternalRankingReproductionWorkOrder:
    """Require byte equality with a fresh reconstruction of the work order."""

    loaded = _load_receipt(
        work_order_path,
        expected_schema_id=(
            POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_WORK_ORDER_SCHEMA_ID
        ),
        expected_receipt_sha256=expected_work_order_receipt_sha256,
        maximum_bytes=(POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_WORK_ORDER_BYTES),
    )
    raw = loaded.payload
    expected = materialize_posebusters_external_ranking_reproduction_work_order(
        baseline_evaluation_receipt_path,
        baseline_test_partition_receipt_path,
        baseline_ranking_intake_receipt_path,
        engine_wheel_path,
        expected_baseline_evaluation_receipt_sha256=(
            expected_baseline_evaluation_receipt_sha256
        ),
        expected_baseline_test_partition_receipt_sha256=(
            expected_baseline_test_partition_receipt_sha256
        ),
        expected_baseline_ranking_intake_receipt_sha256=(
            expected_baseline_ranking_intake_receipt_sha256
        ),
        expected_engine_wheel_sha256=expected_engine_wheel_sha256,
        baseline_host_identity_sha256=raw.get("baseline_host_identity_sha256"),
        expected_external_host_identity_sha256=raw.get(
            "expected_external_host_identity_sha256"
        ),
        work_order_operator_identity_sha256=raw.get(
            "work_order_operator_identity_sha256"
        ),
        external_execution_operator_identity_sha256=raw.get(
            "external_execution_operator_identity_sha256"
        ),
        external_execution_nonce_sha256=raw.get("external_execution_nonce_sha256"),
        registered_utc=raw.get("registered_utc"),
    )
    if loaded.source != expected.canonical_bytes():
        raise PoseBustersExternalRankingReproductionError(
            "work order failed exact reconstruction"
        )
    return expected


def _metric_map(value: object, *, name: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in _list(value, name=name):
        row = _mapping(item, name=f"{name} row")
        metric_id = _text(row.get("metric_id"), name=f"{name} metric ID")
        if metric_id in result:
            raise PoseBustersExternalRankingReproductionError(
                f"{name} metric IDs must be unique"
            )
        result[metric_id] = row
    return result


def _ratio_metric_counts_equal(
    baseline: object,
    external: object,
    *,
    name: str,
) -> tuple[bool, list[str]]:
    baseline_rows = _metric_map(baseline, name=f"baseline {name}")
    external_rows = _metric_map(external, name=f"external {name}")
    mismatches: list[str] = []
    for metric_id in sorted(set(baseline_rows) | set(external_rows)):
        left = baseline_rows.get(metric_id)
        right = external_rows.get(metric_id)
        if (
            left is None
            or right is None
            or left.get("numerator") != right.get("numerator")
            or left.get("denominator") != right.get("denominator")
            or left.get("denominator_scope") != right.get("denominator_scope")
            or left.get("available") is not right.get("available")
        ):
            mismatches.append(metric_id)
    return not mismatches, mismatches


def _curve_comparison(
    baseline: object,
    external: object,
    *,
    scope: str,
) -> dict[str, Any]:
    left = _mapping(baseline, name=f"{scope} baseline curve metric")
    right = _mapping(external, name=f"{scope} external curve metric")
    exact_fields = (
        "metric_id",
        "all_case_denominator",
        "all_pose_observation_denominator",
        "successful_labeled_pose_count",
        "positive_pose_count",
        "negative_pose_count",
        "failure_observation_count",
        "bootstrap_unit",
        "bootstrap_requested_sample_count",
        "bootstrap_valid_sample_count",
        "tie_policy",
        "available",
    )
    exact_equal = all(left.get(key) == right.get(key) for key in exact_fields)
    tolerance = _hex_float(
        POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CONFIGURATION[
            "average_precision_absolute_tolerance"
        ],
        name="average precision tolerance",
    )
    numeric_deltas: dict[str, float | None] = {}
    numeric_pass = True
    for key in (
        "value",
        "confidence_interval_low",
        "confidence_interval_high",
    ):
        left_value = left.get(key)
        right_value = right.get(key)
        if left_value is None and right_value is None:
            numeric_deltas[key] = None
            continue
        if left_value is None or right_value is None:
            numeric_deltas[key] = None
            numeric_pass = False
            continue
        delta = abs(
            _finite(left_value, name=f"{scope} baseline {key}")
            - _finite(right_value, name=f"{scope} external {key}")
        )
        numeric_deltas[key] = delta
        numeric_pass = numeric_pass and delta <= tolerance
    return {
        "scope": scope,
        "exact_count_and_class_fields_equal": exact_equal,
        "numeric_absolute_deltas": numeric_deltas,
        "numeric_absolute_tolerance": tolerance,
        "numeric_tolerance_pass": numeric_pass,
        "curve_metric_reproduced": exact_equal and numeric_pass,
    }


def _ranked_pose_projection(
    case: Mapping[str, Any],
    *,
    name: str,
) -> list[tuple[int, bool, float]]:
    rows: list[tuple[int, bool, float]] = []
    for item in _list(case.get("ranked_pose_rows"), name=f"{name} ranked poses"):
        row = _mapping(item, name=f"{name} ranked pose")
        rows.append(
            (
                _integer(
                    row.get("source_pose_rank"),
                    name=f"{name} source pose rank",
                    minimum=1,
                ),
                _boolean(row.get("native_like"), name=f"{name} native label"),
                _hex_float(
                    row.get("source_score_binary64_hex"),
                    name=f"{name} source score",
                ),
            )
        )
    return rows


def _case_comparison(
    engine: str,
    baseline: Mapping[str, Any],
    external: Mapping[str, Any],
) -> dict[str, Any]:
    case_id = _text(baseline.get("case_id"), name="baseline case ID")
    if external.get("case_id") != case_id:
        raise PoseBustersExternalRankingReproductionError(
            "case comparison identity changed"
        )
    baseline_rows = _ranked_pose_projection(
        baseline,
        name=f"{engine} {case_id} baseline",
    )
    external_rows = _ranked_pose_projection(
        external,
        name=f"{engine} {case_id} external",
    )
    baseline_ranks = tuple(row[0] for row in baseline_rows)
    external_ranks = tuple(row[0] for row in external_rows)
    rank_sequence_equal = baseline_ranks == external_ranks
    native_label_sequence_equal = tuple(row[1] for row in baseline_rows) == tuple(
        row[1] for row in external_rows
    )
    score_shape_equal = len(baseline_rows) == len(external_rows)
    score_deltas: list[float] = []
    if score_shape_equal and rank_sequence_equal:
        score_deltas = [
            abs(left[2] - right[2])
            for left, right in zip(baseline_rows, external_rows, strict=True)
        ]
    score_max = max(score_deltas, default=0.0)
    score_rms = (
        math.sqrt(sum(delta * delta for delta in score_deltas) / len(score_deltas))
        if score_deltas
        else 0.0
    )
    score_tolerance = _hex_float(
        POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CONFIGURATION[
            "score_absolute_tolerances"
        ][engine],
        name=f"{engine} score tolerance",
    )
    score_tolerance_pass = (
        score_shape_equal and rank_sequence_equal and score_max <= score_tolerance
    )
    family_fields = (
        "target_id",
        "observed_sequence_proxy_id",
        "pfam_ids",
        "pfam_set_id",
        "biological_annotation_status",
    )
    family_identity_equal = all(
        baseline.get(key) == external.get(key) for key in family_fields
    )
    failure_codes_equal = baseline.get("failure_codes") == external.get("failure_codes")
    status_equal = baseline.get("status") == external.get("status")
    pose_counts_equal = all(
        baseline.get(key) == external.get(key)
        for key in (
            "pose_observation_count",
            "successful_pose_count",
            "failure_observation_count",
        )
    )
    top_k_equal = all(
        baseline.get(key) == external.get(key)
        for key in (
            "top1_tie_inclusive_pose_count",
            "top5_tie_inclusive_pose_count",
            "top1_native_like",
            "top5_native_like",
        )
    )
    reproduced = (
        family_identity_equal
        and failure_codes_equal
        and status_equal
        and pose_counts_equal
        and rank_sequence_equal
        and native_label_sequence_equal
        and top_k_equal
        and score_tolerance_pass
    )
    return {
        "schema_id": (POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CASE_SCHEMA_ID),
        "engine_id": engine,
        "case_id": case_id,
        "baseline_status": baseline.get("status"),
        "external_status": external.get("status"),
        "family_identity_equal": family_identity_equal,
        "status_equal": status_equal,
        "failure_codes_equal": failure_codes_equal,
        "pose_counts_equal": pose_counts_equal,
        "source_rank_sequence_equal": rank_sequence_equal,
        "native_label_sequence_equal": native_label_sequence_equal,
        "top_k_outcomes_equal": top_k_equal,
        "compared_score_count": len(score_deltas),
        "source_score_max_absolute_error": score_max,
        "source_score_max_absolute_error_binary64_hex": score_max.hex(),
        "source_score_rms_error": score_rms,
        "source_score_rms_error_binary64_hex": score_rms.hex(),
        "source_score_absolute_tolerance": score_tolerance,
        "source_score_absolute_tolerance_binary64_hex": score_tolerance.hex(),
        "source_score_tolerance_pass": score_tolerance_pass,
        "case_reproduced": reproduced,
    }


def _family_scope_comparison(
    baseline: object,
    external: object,
    *,
    engine: str,
) -> dict[str, Any]:
    baseline_scopes = {
        _text(row.get("family_kind"), name="baseline family kind"): row
        for row in (
            _mapping(item, name="baseline family scope")
            for item in _list(baseline, name="baseline family scopes")
        )
    }
    external_scopes = {
        _text(row.get("family_kind"), name="external family kind"): row
        for row in (
            _mapping(item, name="external family scope")
            for item in _list(external, name="external family scopes")
        )
    }
    scope_rows: list[dict[str, Any]] = []
    for kind in sorted(set(baseline_scopes) | set(external_scopes)):
        left_scope = baseline_scopes.get(kind)
        right_scope = external_scopes.get(kind)
        if left_scope is None or right_scope is None:
            scope_rows.append(
                {
                    "family_kind": kind,
                    "family_id_set_equal": False,
                    "reproduced_family_count": 0,
                    "family_count": 0,
                    "family_scope_reproduced": False,
                }
            )
            continue
        left_rows = {
            _text(row.get("family_id"), name="baseline family ID"): row
            for row in (
                _mapping(item, name="baseline family row")
                for item in _list(
                    left_scope.get("family_rows"),
                    name="baseline family rows",
                )
            )
        }
        right_rows = {
            _text(row.get("family_id"), name="external family ID"): row
            for row in (
                _mapping(item, name="external family row")
                for item in _list(
                    right_scope.get("family_rows"),
                    name="external family rows",
                )
            )
        }
        family_id_set_equal = set(left_rows) == set(right_rows)
        reproduced_count = 0
        for family_id in sorted(set(left_rows) & set(right_rows)):
            left = left_rows[family_id]
            right = right_rows[family_id]
            metrics_equal, _mismatches = _ratio_metric_counts_equal(
                left.get("metrics"),
                right.get("metrics"),
                name=f"{engine} {kind} {family_id} metrics",
            )
            curve = _curve_comparison(
                left.get("pose_curve_metric"),
                right.get("pose_curve_metric"),
                scope=f"{engine}:{kind}:{family_id}",
            )
            if (
                left.get("family_semantics") == right.get("family_semantics")
                and left.get("member_case_count") == right.get("member_case_count")
                and left.get("case_ids") == right.get("case_ids")
                and metrics_equal
                and curve["curve_metric_reproduced"]
            ):
                reproduced_count += 1
        family_count = len(left_rows)
        scope_metadata_equal = all(
            left_scope.get(key) == right_scope.get(key)
            for key in (
                "family_count",
                "all_case_membership_complete",
                "memberships_are_disjoint",
                "biological_annotation_complete",
            )
        )
        scope_rows.append(
            {
                "family_kind": kind,
                "family_id_set_equal": family_id_set_equal,
                "scope_metadata_equal": scope_metadata_equal,
                "reproduced_family_count": reproduced_count,
                "family_count": family_count,
                "family_scope_reproduced": (
                    family_id_set_equal
                    and scope_metadata_equal
                    and reproduced_count == family_count
                ),
            }
        )
    return {
        "scope_rows": scope_rows,
        "family_scope_count": len(scope_rows),
        "family_scopes_reproduced": (
            len(scope_rows) == 3
            and all(row["family_scope_reproduced"] for row in scope_rows)
        ),
    }


def _source_validity_counts(value: object) -> dict[str, Any]:
    row = _mapping(value, name="source physical validity evidence")
    return {
        key: row.get(key)
        for key in (
            "successful_pose_row_count",
            "failure_row_count",
            "evaluated_case_count",
            "physically_valid_pose_count",
            "top_1_valid_native_like_case_count",
            "top_5_valid_native_like_case_count",
        )
    }


def _engine_comparison(
    engine: str,
    baseline: Mapping[str, Any],
    external: Mapping[str, Any],
) -> dict[str, Any]:
    if baseline.get("engine_id") != engine or external.get("engine_id") != engine:
        raise PoseBustersExternalRankingReproductionError(
            "engine comparison identity changed"
        )
    baseline_cases = {
        _text(row.get("case_id"), name="baseline case ID"): row
        for row in (
            _mapping(item, name="baseline case")
            for item in _list(
                baseline.get("case_rows"),
                name="baseline case rows",
            )
        )
    }
    external_cases = {
        _text(row.get("case_id"), name="external case ID"): row
        for row in (
            _mapping(item, name="external case")
            for item in _list(
                external.get("case_rows"),
                name="external case rows",
            )
        )
    }
    case_id_set_equal = (
        set(baseline_cases) == set(external_cases) and len(baseline_cases) == 308
    )
    case_rows = [
        _case_comparison(
            engine,
            baseline_cases[case_id],
            external_cases[case_id],
        )
        for case_id in sorted(set(baseline_cases) & set(external_cases))
    ]
    metrics_equal, metric_mismatches = _ratio_metric_counts_equal(
        baseline.get("metrics"),
        external.get("metrics"),
        name=f"{engine} overall metrics",
    )
    curve = _curve_comparison(
        baseline.get("pose_curve_metric"),
        external.get("pose_curve_metric"),
        scope=f"{engine}:overall",
    )
    families = _family_scope_comparison(
        baseline.get("family_scopes"),
        external.get("family_scopes"),
        engine=engine,
    )
    summary_counts_equal = all(
        baseline.get(key) == external.get(key)
        for key in (
            "all_case_denominator",
            "scored_case_count",
            "failure_case_count",
            "successful_pose_count",
            "failure_observation_count",
            "source_order_reproduced_case_count",
        )
    )
    score_policy_equal = baseline.get("score_policy") == external.get("score_policy")
    source_validity_counts_equal = _source_validity_counts(
        baseline.get("source_physical_validity_evidence")
    ) == _source_validity_counts(external.get("source_physical_validity_evidence"))
    reproduced_case_count = sum(row["case_reproduced"] for row in case_rows)
    reproduced = (
        case_id_set_equal
        and len(case_rows) == 308
        and reproduced_case_count == 308
        and metrics_equal
        and curve["curve_metric_reproduced"]
        and families["family_scopes_reproduced"]
        and summary_counts_equal
        and score_policy_equal
        and source_validity_counts_equal
    )
    return {
        "schema_id": (POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_ENGINE_SCHEMA_ID),
        "engine_id": engine,
        "case_id_set_equal": case_id_set_equal,
        "case_comparison_count": len(case_rows),
        "reproduced_case_count": reproduced_case_count,
        "failed_case_comparison_count": len(case_rows) - reproduced_case_count,
        "summary_counts_equal": summary_counts_equal,
        "score_policy_equal": score_policy_equal,
        "ratio_metric_counts_equal": metrics_equal,
        "ratio_metric_mismatch_ids": metric_mismatches,
        "pose_curve_comparison": curve,
        "family_scope_comparison": families,
        "source_physical_validity_counts_equal": (source_validity_counts_equal),
        "case_rows": case_rows,
        "engine_reproduced": reproduced,
    }


def compare_posebusters_external_ranking_evaluations(
    baseline: Mapping[str, Any],
    external: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare every case, failure, fixed-policy score, metric, and family row."""

    baseline_payload = _mapping(baseline, name="baseline evaluation")
    external_payload = _mapping(external, name="external evaluation")
    for name, payload in (
        ("baseline", baseline_payload),
        ("external", external_payload),
    ):
        if (
            payload.get("schema_id")
            != evaluation_module.POSEBUSTERS_EXTERNAL_RANKING_EVALUATION_RECEIPT_SCHEMA_ID
            or payload.get("all_case_denominator") != 308
            or payload.get("engine_count") != 3
            or payload.get("split_role") != "test"
            or payload.get("score_policy_fit_performed") is not False
            or payload.get("test_labels_used_to_select_score_policy") is not False
            or payload.get("claim_safe") is not False
        ):
            raise PoseBustersExternalRankingReproductionError(
                f"{name} evaluation violates the fixed test-only boundary"
            )
    baseline_sha = _digest(
        baseline_payload.get("receipt_sha256"),
        name="baseline evaluation receipt",
    )
    external_sha = _digest(
        external_payload.get("receipt_sha256"),
        name="external evaluation receipt",
    )
    if baseline_sha == external_sha:
        raise PoseBustersExternalRankingReproductionError(
            "copied baseline evaluation cannot serve as an external rerun"
        )
    baseline_results = {
        _text(row.get("engine_id"), name="baseline engine ID"): row
        for row in (
            _mapping(item, name="baseline engine result")
            for item in _list(
                baseline_payload.get("engine_results"),
                name="baseline engine results",
            )
        )
    }
    external_results = {
        _text(row.get("engine_id"), name="external engine ID"): row
        for row in (
            _mapping(item, name="external engine result")
            for item in _list(
                external_payload.get("engine_results"),
                name="external engine results",
            )
        )
    }
    if set(baseline_results) != set(_ENGINES) or set(external_results) != set(_ENGINES):
        raise PoseBustersExternalRankingReproductionError(
            "evaluation engine sets are incomplete"
        )
    engine_rows = [
        _engine_comparison(
            engine,
            baseline_results[engine],
            external_results[engine],
        )
        for engine in _ENGINES
    ]
    reproduced_case_count = sum(row["reproduced_case_count"] for row in engine_rows)
    payload = {
        "schema_id": (POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_COMPARISON_SCHEMA_ID),
        "configuration_sha256": (
            POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CONFIGURATION_SHA256
        ),
        "baseline_evaluation_receipt_sha256": baseline_sha,
        "external_evaluation_receipt_sha256": external_sha,
        "all_case_denominator": 308,
        "engine_count": 3,
        "case_comparison_count": sum(
            row["case_comparison_count"] for row in engine_rows
        ),
        "reproduced_case_count": reproduced_case_count,
        "failed_case_comparison_count": 924 - reproduced_case_count,
        "engine_rows": engine_rows,
        "cross_host_numerical_reproduction_pass": (
            reproduced_case_count == 924
            and all(row["engine_reproduced"] for row in engine_rows)
        ),
    }
    return {**payload, "comparison_sha256": _canonical_sha256(payload)}


def _distribution_versions() -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for distribution in (
        "betelgeuze-engine-v2",
        "numpy",
        "torch",
        "rdkit",
        "posebusters",
    ):
        try:
            result[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            result[distribution] = None
    return result


def observe_posebusters_external_ranking_reproduction_runtime(
    engine_wheel_path: str | os.PathLike[str],
    *,
    expected_engine_wheel_sha256: str,
) -> dict[str, Any]:
    """Observe a non-unique runtime projection on the executing host."""

    executable = Path(sys.executable).resolve()
    _path, executable_source, executable_sha = _regular_file(
        executable,
        maximum_bytes=128 * 1024 * 1024,
        name="Python executable",
    )
    wheel = _wheel_binding(
        engine_wheel_path,
        expected_wheel_sha256=expected_engine_wheel_sha256,
    )
    processor = platform.processor() or platform.machine()
    cpu_projection = {
        "platform_machine": platform.machine().lower(),
        "processor": processor,
        "platform_system": platform.system(),
        "platform_release": platform.release(),
    }
    payload = {
        "schema_id": (POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_RUNTIME_SCHEMA_ID),
        "platform_system": _text(
            platform.system(),
            name="platform system",
        ),
        "platform_release": _text(
            platform.release(),
            name="platform release",
        ),
        "platform_machine": _text(
            platform.machine().lower(),
            name="platform machine",
        ),
        "processor": _text(processor, name="processor"),
        "cpu_projection_sha256": _canonical_sha256(cpu_projection),
        "python_implementation": _text(
            platform.python_implementation(),
            name="Python implementation",
        ),
        "python_version": _text(
            platform.python_version(),
            name="Python version",
        ),
        "python_executable_sha256": executable_sha,
        "python_executable_size_bytes": len(executable_source),
        "distribution_versions": _distribution_versions(),
        "engine_wheel_binding": wheel,
        "physical_host_identity_proven": False,
    }
    return {**payload, "runtime_identity_sha256": _canonical_sha256(payload)}


def _validated_runtime_identity(
    value: object,
    *,
    work_order: Mapping[str, Any],
) -> dict[str, Any]:
    runtime = _mapping(value, name="external runtime identity")
    if (
        runtime.get("schema_id")
        != POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_RUNTIME_SCHEMA_ID
        or runtime.get("physical_host_identity_proven") is not False
    ):
        raise PoseBustersExternalRankingReproductionError(
            "external runtime identity boundary is invalid"
        )
    digest = _digest(
        runtime.get("runtime_identity_sha256"),
        name="external runtime identity",
    )
    payload = dict(runtime)
    payload.pop("runtime_identity_sha256")
    if _canonical_sha256(payload) != digest:
        raise PoseBustersExternalRankingReproductionError(
            "external runtime identity digest is invalid"
        )
    if runtime.get("engine_wheel_binding") != work_order.get("engine_wheel_binding"):
        raise PoseBustersExternalRankingReproductionError(
            "external runtime does not bind the preregistered wheel"
        )
    for field in (
        "platform_system",
        "platform_release",
        "platform_machine",
        "processor",
        "python_implementation",
        "python_version",
    ):
        _text(runtime.get(field), name=f"external runtime {field}")
    _digest(
        runtime.get("cpu_projection_sha256"),
        name="external runtime CPU projection",
    )
    _digest(
        runtime.get("python_executable_sha256"),
        name="external Python executable",
    )
    _integer(
        runtime.get("python_executable_size_bytes"),
        name="external Python executable size",
        minimum=1,
    )
    versions = _mapping(
        runtime.get("distribution_versions"),
        name="external distribution versions",
    )
    if set(versions) != {
        "betelgeuze-engine-v2",
        "numpy",
        "torch",
        "rdkit",
        "posebusters",
    } or any(
        value is not None and not isinstance(value, str) for value in versions.values()
    ):
        raise PoseBustersExternalRankingReproductionError(
            "external distribution version projection is invalid"
        )
    return runtime


def _work_order_and_loaded(
    work_order_path: str | os.PathLike[str],
    baseline_evaluation_receipt_path: str | os.PathLike[str],
    baseline_test_partition_receipt_path: str | os.PathLike[str],
    baseline_ranking_intake_receipt_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    *,
    expected_work_order_receipt_sha256: str,
    expected_baseline_evaluation_receipt_sha256: str,
    expected_baseline_test_partition_receipt_sha256: str,
    expected_baseline_ranking_intake_receipt_sha256: str,
    expected_engine_wheel_sha256: str,
) -> tuple[dict[str, Any], _LoadedReceipt]:
    verified = verify_posebusters_external_ranking_reproduction_work_order(
        work_order_path,
        baseline_evaluation_receipt_path,
        baseline_test_partition_receipt_path,
        baseline_ranking_intake_receipt_path,
        engine_wheel_path,
        expected_work_order_receipt_sha256=(expected_work_order_receipt_sha256),
        expected_baseline_evaluation_receipt_sha256=(
            expected_baseline_evaluation_receipt_sha256
        ),
        expected_baseline_test_partition_receipt_sha256=(
            expected_baseline_test_partition_receipt_sha256
        ),
        expected_baseline_ranking_intake_receipt_sha256=(
            expected_baseline_ranking_intake_receipt_sha256
        ),
        expected_engine_wheel_sha256=expected_engine_wheel_sha256,
    )
    loaded = _load_receipt(
        work_order_path,
        expected_schema_id=(
            POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_WORK_ORDER_SCHEMA_ID
        ),
        expected_receipt_sha256=expected_work_order_receipt_sha256,
        maximum_bytes=(POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_WORK_ORDER_BYTES),
    )
    if verified.to_dict() != loaded.payload:
        raise PoseBustersExternalRankingReproductionError(
            "verified work order and loaded payload disagree"
        )
    return verified.to_dict(), loaded


def _require_external_chain_distinct(
    baseline: Mapping[str, Any],
    external: Mapping[str, Any],
) -> None:
    baseline_binding = _chain_binding(baseline)
    external_binding = _chain_binding(external)
    for key in (
        "ranking_intake_receipt_sha256",
        "ranking_intake_file_sha256",
        "test_partition_receipt_sha256",
        "test_partition_file_sha256",
        "evaluation_receipt_sha256",
        "evaluation_file_sha256",
    ):
        if baseline_binding[key] == external_binding[key]:
            raise PoseBustersExternalRankingReproductionError(
                "external chain reuses a baseline result receipt"
            )
    for key in (
        "ranking_intake_configuration_sha256",
        "ranking_intake_implementation_sha256",
        "test_partition_configuration_sha256",
        "test_partition_implementation_sha256",
        "evaluation_configuration_sha256",
        "evaluation_implementation_sha256",
    ):
        if baseline_binding[key] != external_binding[key]:
            raise PoseBustersExternalRankingReproductionError(
                "external chain changed the frozen implementation or configuration"
            )
    for role in _FIXED_INPUT_ROLES:
        if baseline["intake_inputs"][role] != external["intake_inputs"][role]:
            raise PoseBustersExternalRankingReproductionError(
                "external chain changed a fixed same-input public root"
            )
    for role in _ENGINE_EVIDENCE_ROLES:
        left = baseline["intake_inputs"][role]
        right = external["intake_inputs"][role]
        if (
            left["source_receipt_sha256"] == right["source_receipt_sha256"]
            or left["source_file_sha256"] == right["source_file_sha256"]
        ):
            raise PoseBustersExternalRankingReproductionError(
                "external chain reuses a baseline engine evidence root"
            )


class PoseBustersExternalRankingReproductionResult:
    """Canonical unreviewed cross-host comparison result."""

    __slots__ = ("_payload_bytes",)

    def __init__(self, payload: Mapping[str, Any]) -> None:
        candidate = dict(payload)
        if "receipt_sha256" in candidate:
            raise PoseBustersExternalRankingReproductionError(
                "result payload must not contain its own digest"
            )
        source = _canonical_bytes(candidate)
        normalized = json.loads(source)
        if (
            normalized.get("schema_id")
            != POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_RESULT_SCHEMA_ID
            or normalized.get("configuration_sha256")
            != POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CONFIGURATION_SHA256
            or normalized.get("all_case_denominator") != 308
            or normalized.get("engine_count") != 3
            or normalized.get("split_role") != "test"
            or normalized.get("status")
            not in {"comparison_passed", "comparison_failed"}
            or any(
                normalized.get(key) is not expected
                for key, expected in _RESULT_FLAGS.items()
            )
        ):
            raise PoseBustersExternalRankingReproductionError(
                "result payload violates its unreviewed comparison boundary"
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
        return _atomic_write_new(
            output_path,
            self.canonical_bytes(),
            maximum_bytes=(POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_RESULT_BYTES),
        )


def _build_reproduction_result(
    work_order_path: str | os.PathLike[str],
    baseline_evaluation_receipt_path: str | os.PathLike[str],
    baseline_test_partition_receipt_path: str | os.PathLike[str],
    baseline_ranking_intake_receipt_path: str | os.PathLike[str],
    external_evaluation_receipt_path: str | os.PathLike[str],
    external_test_partition_receipt_path: str | os.PathLike[str],
    external_ranking_intake_receipt_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    *,
    expected_work_order_receipt_sha256: str,
    expected_baseline_evaluation_receipt_sha256: str,
    expected_baseline_test_partition_receipt_sha256: str,
    expected_baseline_ranking_intake_receipt_sha256: str,
    expected_external_evaluation_receipt_sha256: str,
    expected_external_test_partition_receipt_sha256: str,
    expected_external_ranking_intake_receipt_sha256: str,
    expected_engine_wheel_sha256: str,
    observed_external_host_identity_sha256: str,
    observed_external_execution_operator_identity_sha256: str,
    external_observed_utc: str,
    external_runtime_identity: Mapping[str, Any],
) -> PoseBustersExternalRankingReproductionResult:
    work_order, work_order_loaded = _work_order_and_loaded(
        work_order_path,
        baseline_evaluation_receipt_path,
        baseline_test_partition_receipt_path,
        baseline_ranking_intake_receipt_path,
        engine_wheel_path,
        expected_work_order_receipt_sha256=(expected_work_order_receipt_sha256),
        expected_baseline_evaluation_receipt_sha256=(
            expected_baseline_evaluation_receipt_sha256
        ),
        expected_baseline_test_partition_receipt_sha256=(
            expected_baseline_test_partition_receipt_sha256
        ),
        expected_baseline_ranking_intake_receipt_sha256=(
            expected_baseline_ranking_intake_receipt_sha256
        ),
        expected_engine_wheel_sha256=expected_engine_wheel_sha256,
    )
    observed_host = _digest(
        observed_external_host_identity_sha256,
        name="observed external host identity",
    )
    observed_operator = _digest(
        observed_external_execution_operator_identity_sha256,
        name="observed external execution operator identity",
    )
    if (
        observed_host != work_order["expected_external_host_identity_sha256"]
        or observed_operator
        != work_order["external_execution_operator_identity_sha256"]
    ):
        raise PoseBustersExternalRankingReproductionError(
            "external host or execution operator was not preregistered"
        )
    observed_utc = _utc(external_observed_utc, name="external observation UTC")
    if _utc_datetime(
        observed_utc,
        name="external observation UTC",
    ) <= _utc_datetime(
        work_order["registered_utc"],
        name="work-order registration UTC",
    ):
        raise PoseBustersExternalRankingReproductionError(
            "external observation must follow work-order registration"
        )
    runtime = _validated_runtime_identity(
        external_runtime_identity,
        work_order=work_order,
    )
    baseline_chain = _ranking_chain(
        baseline_evaluation_receipt_path,
        baseline_test_partition_receipt_path,
        baseline_ranking_intake_receipt_path,
        expected_evaluation_receipt_sha256=(
            expected_baseline_evaluation_receipt_sha256
        ),
        expected_test_partition_receipt_sha256=(
            expected_baseline_test_partition_receipt_sha256
        ),
        expected_ranking_intake_receipt_sha256=(
            expected_baseline_ranking_intake_receipt_sha256
        ),
    )
    external_chain = _ranking_chain(
        external_evaluation_receipt_path,
        external_test_partition_receipt_path,
        external_ranking_intake_receipt_path,
        expected_evaluation_receipt_sha256=(
            expected_external_evaluation_receipt_sha256
        ),
        expected_test_partition_receipt_sha256=(
            expected_external_test_partition_receipt_sha256
        ),
        expected_ranking_intake_receipt_sha256=(
            expected_external_ranking_intake_receipt_sha256
        ),
    )
    _require_external_chain_distinct(baseline_chain, external_chain)
    comparison = compare_posebusters_external_ranking_evaluations(
        baseline_chain["evaluation"].payload,
        external_chain["evaluation"].payload,
    )
    reproduced = comparison["cross_host_numerical_reproduction_pass"] is True
    payload = {
        "schema_id": (POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_RESULT_SCHEMA_ID),
        "observed_utc": observed_utc,
        "work_order_receipt_sha256": work_order_loaded.receipt_sha256,
        "work_order_file_sha256": work_order_loaded.file_sha256,
        "baseline_chain": _chain_binding(baseline_chain),
        "external_chain": _chain_binding(external_chain),
        "fixed_input_receipts": [
            dict(external_chain["intake_inputs"][role]) for role in _FIXED_INPUT_ROLES
        ],
        "external_engine_evidence_receipts": [
            dict(external_chain["intake_inputs"][role])
            for role in _ENGINE_EVIDENCE_ROLES
        ],
        "baseline_host_identity_sha256": work_order["baseline_host_identity_sha256"],
        "external_host_identity_sha256": observed_host,
        "external_execution_operator_identity_sha256": observed_operator,
        "external_execution_nonce_sha256": work_order[
            "external_execution_nonce_sha256"
        ],
        "external_runtime_identity": runtime,
        "external_runtime_identity_sha256": runtime["runtime_identity_sha256"],
        "external_evaluation": dict(external_chain["evaluation"].payload),
        "comparison": comparison,
        "status": "comparison_passed" if reproduced else "comparison_failed",
        "cross_host_numerical_reproduction_pass": reproduced,
        "all_case_denominator": 308,
        "engine_count": 3,
        "split_role": "test",
        "all_failure_rows_compared": (comparison["case_comparison_count"] == 924),
        "source_binary_environment_dependency_identity_bound": True,
        "execution_nonce_single_use_operator_attestation_required": True,
        "scientific_blockers": list(
            POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_SCIENTIFIC_BLOCKERS
        ),
        "configuration": (POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CONFIGURATION),
        "configuration_sha256": (
            POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CONFIGURATION_SHA256
        ),
        "implementation_source_sha256": work_order["implementation_source_sha256"],
        **_RESULT_FLAGS,
    }
    return PoseBustersExternalRankingReproductionResult(payload)


def materialize_posebusters_external_ranking_reproduction_result(
    work_order_path: str | os.PathLike[str],
    baseline_evaluation_receipt_path: str | os.PathLike[str],
    baseline_test_partition_receipt_path: str | os.PathLike[str],
    baseline_ranking_intake_receipt_path: str | os.PathLike[str],
    external_evaluation_receipt_path: str | os.PathLike[str],
    external_test_partition_receipt_path: str | os.PathLike[str],
    external_ranking_intake_receipt_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    *,
    expected_work_order_receipt_sha256: str,
    expected_baseline_evaluation_receipt_sha256: str,
    expected_baseline_test_partition_receipt_sha256: str,
    expected_baseline_ranking_intake_receipt_sha256: str,
    expected_external_evaluation_receipt_sha256: str,
    expected_external_test_partition_receipt_sha256: str,
    expected_external_ranking_intake_receipt_sha256: str,
    expected_engine_wheel_sha256: str,
    observed_external_host_identity_sha256: str,
    observed_external_execution_operator_identity_sha256: str,
    external_observed_utc: str,
) -> PoseBustersExternalRankingReproductionResult:
    """Package and compare a new external chain on its executing host."""

    runtime = observe_posebusters_external_ranking_reproduction_runtime(
        engine_wheel_path,
        expected_engine_wheel_sha256=expected_engine_wheel_sha256,
    )
    return _build_reproduction_result(
        work_order_path,
        baseline_evaluation_receipt_path,
        baseline_test_partition_receipt_path,
        baseline_ranking_intake_receipt_path,
        external_evaluation_receipt_path,
        external_test_partition_receipt_path,
        external_ranking_intake_receipt_path,
        engine_wheel_path,
        expected_work_order_receipt_sha256=(expected_work_order_receipt_sha256),
        expected_baseline_evaluation_receipt_sha256=(
            expected_baseline_evaluation_receipt_sha256
        ),
        expected_baseline_test_partition_receipt_sha256=(
            expected_baseline_test_partition_receipt_sha256
        ),
        expected_baseline_ranking_intake_receipt_sha256=(
            expected_baseline_ranking_intake_receipt_sha256
        ),
        expected_external_evaluation_receipt_sha256=(
            expected_external_evaluation_receipt_sha256
        ),
        expected_external_test_partition_receipt_sha256=(
            expected_external_test_partition_receipt_sha256
        ),
        expected_external_ranking_intake_receipt_sha256=(
            expected_external_ranking_intake_receipt_sha256
        ),
        expected_engine_wheel_sha256=expected_engine_wheel_sha256,
        observed_external_host_identity_sha256=(observed_external_host_identity_sha256),
        observed_external_execution_operator_identity_sha256=(
            observed_external_execution_operator_identity_sha256
        ),
        external_observed_utc=external_observed_utc,
        external_runtime_identity=runtime,
    )


def verify_posebusters_external_ranking_reproduction_result(
    result_path: str | os.PathLike[str],
    work_order_path: str | os.PathLike[str],
    baseline_evaluation_receipt_path: str | os.PathLike[str],
    baseline_test_partition_receipt_path: str | os.PathLike[str],
    baseline_ranking_intake_receipt_path: str | os.PathLike[str],
    external_evaluation_receipt_path: str | os.PathLike[str],
    external_test_partition_receipt_path: str | os.PathLike[str],
    external_ranking_intake_receipt_path: str | os.PathLike[str],
    engine_wheel_path: str | os.PathLike[str],
    *,
    expected_result_receipt_sha256: str,
    expected_work_order_receipt_sha256: str,
    expected_baseline_evaluation_receipt_sha256: str,
    expected_baseline_test_partition_receipt_sha256: str,
    expected_baseline_ranking_intake_receipt_sha256: str,
    expected_external_evaluation_receipt_sha256: str,
    expected_external_test_partition_receipt_sha256: str,
    expected_external_ranking_intake_receipt_sha256: str,
    expected_engine_wheel_sha256: str,
) -> PoseBustersExternalRankingReproductionResult:
    """Verify custody and rederive the complete external comparison."""

    loaded = _load_receipt(
        result_path,
        expected_schema_id=(POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_RESULT_SCHEMA_ID),
        expected_receipt_sha256=expected_result_receipt_sha256,
        maximum_bytes=POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_RESULT_BYTES,
    )
    raw = loaded.payload
    expected = _build_reproduction_result(
        work_order_path,
        baseline_evaluation_receipt_path,
        baseline_test_partition_receipt_path,
        baseline_ranking_intake_receipt_path,
        external_evaluation_receipt_path,
        external_test_partition_receipt_path,
        external_ranking_intake_receipt_path,
        engine_wheel_path,
        expected_work_order_receipt_sha256=(expected_work_order_receipt_sha256),
        expected_baseline_evaluation_receipt_sha256=(
            expected_baseline_evaluation_receipt_sha256
        ),
        expected_baseline_test_partition_receipt_sha256=(
            expected_baseline_test_partition_receipt_sha256
        ),
        expected_baseline_ranking_intake_receipt_sha256=(
            expected_baseline_ranking_intake_receipt_sha256
        ),
        expected_external_evaluation_receipt_sha256=(
            expected_external_evaluation_receipt_sha256
        ),
        expected_external_test_partition_receipt_sha256=(
            expected_external_test_partition_receipt_sha256
        ),
        expected_external_ranking_intake_receipt_sha256=(
            expected_external_ranking_intake_receipt_sha256
        ),
        expected_engine_wheel_sha256=expected_engine_wheel_sha256,
        observed_external_host_identity_sha256=raw.get("external_host_identity_sha256"),
        observed_external_execution_operator_identity_sha256=raw.get(
            "external_execution_operator_identity_sha256"
        ),
        external_observed_utc=raw.get("observed_utc"),
        external_runtime_identity=_mapping(
            raw.get("external_runtime_identity"),
            name="embedded external runtime identity",
        ),
    )
    if loaded.source != expected.canonical_bytes():
        raise PoseBustersExternalRankingReproductionError(
            "external reproduction result failed exact reconstruction"
        )
    return expected


def _add_baseline_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--baseline-evaluation-receipt", required=True)
    parser.add_argument(
        "--expected-baseline-evaluation-receipt-sha256",
        required=True,
    )
    parser.add_argument("--baseline-test-partition-receipt", required=True)
    parser.add_argument(
        "--expected-baseline-test-partition-receipt-sha256",
        required=True,
    )
    parser.add_argument("--baseline-ranking-intake-receipt", required=True)
    parser.add_argument(
        "--expected-baseline-ranking-intake-receipt-sha256",
        required=True,
    )
    parser.add_argument("--engine-wheel", required=True)
    parser.add_argument("--expected-engine-wheel-sha256", required=True)


def _add_work_order_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--work-order", required=True)
    parser.add_argument("--expected-work-order-receipt-sha256", required=True)


def _add_external_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--external-evaluation-receipt", required=True)
    parser.add_argument(
        "--expected-external-evaluation-receipt-sha256",
        required=True,
    )
    parser.add_argument("--external-test-partition-receipt", required=True)
    parser.add_argument(
        "--expected-external-test-partition-receipt-sha256",
        required=True,
    )
    parser.add_argument("--external-ranking-intake-receipt", required=True)
    parser.add_argument(
        "--expected-external-ranking-intake-receipt-sha256",
        required=True,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-external-ranking-reproduce",
        description=(
            "Preregister and compare a second-host, failure-inclusive "
            "PoseBusters Vina/GNINA/Smina ranking rerun."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize_work_order = subparsers.add_parser("materialize-work-order")
    verify_work_order = subparsers.add_parser("verify-work-order")
    materialize_result = subparsers.add_parser("materialize-result")
    verify_result = subparsers.add_parser("verify-result")
    for subparser in (
        materialize_work_order,
        verify_work_order,
        materialize_result,
        verify_result,
    ):
        _add_baseline_arguments(subparser)
    for subparser in (verify_work_order, materialize_result, verify_result):
        _add_work_order_arguments(subparser)
    for subparser in (materialize_result, verify_result):
        _add_external_arguments(subparser)
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
    materialize_work_order.add_argument("--output", required=True)
    materialize_result.add_argument(
        "--observed-external-host-identity-sha256",
        required=True,
    )
    materialize_result.add_argument(
        "--observed-external-execution-operator-identity-sha256",
        required=True,
    )
    materialize_result.add_argument("--external-observed-utc", required=True)
    materialize_result.add_argument("--output", required=True)
    verify_result.add_argument("--result", required=True)
    verify_result.add_argument(
        "--expected-result-receipt-sha256",
        required=True,
    )
    return parser


def _baseline_cli_arguments(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "baseline_evaluation_receipt_path": args.baseline_evaluation_receipt,
        "baseline_test_partition_receipt_path": (args.baseline_test_partition_receipt),
        "baseline_ranking_intake_receipt_path": (args.baseline_ranking_intake_receipt),
        "engine_wheel_path": args.engine_wheel,
        "expected_baseline_evaluation_receipt_sha256": (
            args.expected_baseline_evaluation_receipt_sha256
        ),
        "expected_baseline_test_partition_receipt_sha256": (
            args.expected_baseline_test_partition_receipt_sha256
        ),
        "expected_baseline_ranking_intake_receipt_sha256": (
            args.expected_baseline_ranking_intake_receipt_sha256
        ),
        "expected_engine_wheel_sha256": args.expected_engine_wheel_sha256,
    }


def _external_cli_arguments(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "external_evaluation_receipt_path": args.external_evaluation_receipt,
        "external_test_partition_receipt_path": (args.external_test_partition_receipt),
        "external_ranking_intake_receipt_path": (args.external_ranking_intake_receipt),
        "expected_external_evaluation_receipt_sha256": (
            args.expected_external_evaluation_receipt_sha256
        ),
        "expected_external_test_partition_receipt_sha256": (
            args.expected_external_test_partition_receipt_sha256
        ),
        "expected_external_ranking_intake_receipt_sha256": (
            args.expected_external_ranking_intake_receipt_sha256
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    baseline = _baseline_cli_arguments(args)
    if args.command == "materialize-work-order":
        receipt: (
            PoseBustersExternalRankingReproductionWorkOrder
            | PoseBustersExternalRankingReproductionResult
        ) = materialize_posebusters_external_ranking_reproduction_work_order(
            **baseline,
            baseline_host_identity_sha256=args.baseline_host_identity_sha256,
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
        receipt.write_json(args.output)
    elif args.command == "verify-work-order":
        receipt = verify_posebusters_external_ranking_reproduction_work_order(
            work_order_path=args.work_order,
            expected_work_order_receipt_sha256=(
                args.expected_work_order_receipt_sha256
            ),
            **baseline,
        )
    elif args.command == "materialize-result":
        receipt = materialize_posebusters_external_ranking_reproduction_result(
            work_order_path=args.work_order,
            expected_work_order_receipt_sha256=(
                args.expected_work_order_receipt_sha256
            ),
            observed_external_host_identity_sha256=(
                args.observed_external_host_identity_sha256
            ),
            observed_external_execution_operator_identity_sha256=(
                args.observed_external_execution_operator_identity_sha256
            ),
            external_observed_utc=args.external_observed_utc,
            **baseline,
            **_external_cli_arguments(args),
        )
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_external_ranking_reproduction_result(
            result_path=args.result,
            expected_result_receipt_sha256=(args.expected_result_receipt_sha256),
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
                "schema_id": payload["schema_id"],
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": payload["all_case_denominator"],
                "engine_count": payload["engine_count"],
                "external_execution_performed": payload["external_execution_performed"],
                "cross_host_numerical_reproduction_pass": payload.get(
                    "cross_host_numerical_reproduction_pass",
                    False,
                ),
                "physical_host_independence_reviewed": False,
                "independent_external_rerun_present": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CASE_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_COMPARISON_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CONFIGURATION",
    "POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_CONFIGURATION_SHA256",
    "POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_ENGINE_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_INPUT_BYTES",
    "POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_RESULT_BYTES",
    "POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_WHEEL_BYTES",
    "POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_MAX_WORK_ORDER_BYTES",
    "POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_RESULT_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_RUNTIME_SCHEMA_ID",
    "POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_SCIENTIFIC_BLOCKERS",
    "POSEBUSTERS_EXTERNAL_RANKING_REPRODUCTION_WORK_ORDER_SCHEMA_ID",
    "PoseBustersExternalRankingReproductionError",
    "PoseBustersExternalRankingReproductionResult",
    "PoseBustersExternalRankingReproductionWorkOrder",
    "compare_posebusters_external_ranking_evaluations",
    "main",
    "materialize_posebusters_external_ranking_reproduction_result",
    "materialize_posebusters_external_ranking_reproduction_work_order",
    "observe_posebusters_external_ranking_reproduction_runtime",
    "verify_posebusters_external_ranking_reproduction_result",
    "verify_posebusters_external_ranking_reproduction_work_order",
]


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
