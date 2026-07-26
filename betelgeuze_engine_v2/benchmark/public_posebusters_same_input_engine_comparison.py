"""Same-input internal-oracle versus Vina/GNINA/Smina comparison.

The internal PoseBusters oracle and the three external engine evaluations are
separate receipts over the same frozen archive intake.  This module binds all
four by exact receipt identity, requires that they name the same intake, and
then compares every case under one all-case denominator.

Only outcomes the upstream receipts already recorded are compared: evaluated
status, physical validity, and symmetry-aware RMSD threshold hits.  No pose is
regenerated, no score is recalibrated, and no engine is executed.  Wilson 95%
intervals are reported for every rate, and failure, blocked, abstention, and
no-pose rows stay in every denominator.

A passing comparison is not a docking benchmark.  The external receipts cover
only the strictly prepared chemistry subset, the internal engine remains
uncalibrated, and no independent rerun or scientific review exists, so every
result stays claim-closed.
"""

from __future__ import annotations

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

from . import public_posebusters_external_generated_pose_evaluation as external_module
from . import public_posebusters_generated_pose_evaluation as vina_module
from . import public_posebusters_internal_oracle_evaluation as oracle_module
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


POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_same_input_engine_comparison/1.0.0"
)
POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_same_input_engine_comparison_case/1.0.0"
)
POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_same_input_engine_comparison_metric/1.0.0"
)
POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_MAX_INPUT_BYTES = 64 * 1024 * 1024
POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_MAX_RECEIPT_BYTES = 64 * 1024 * 1024
POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_MAX_CASES = 308
POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_Z = 1.959963984540054

POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_ENGINE_IDS = (
    "internal",
    "vina",
    "gnina",
    "smina",
)
POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_METRIC_IDS = (
    "evaluated_case_rate",
    "any_physically_valid_pose_rate",
    "top_1_valid_pose_rate",
    "top_1_rmsd_hit_rate",
    "top_5_rmsd_hit_rate",
    "top_1_valid_rmsd_hit_rate",
)

POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_CONFIGURATION = {
    "schema_id": (
        "betelgeuze.engine_v2_posebusters_same_input_engine_comparison_configuration/1.0.0"
    ),
    "shared_input_policy": "identical_archive_intake_receipt_sha256_required",
    "denominator_policy": "union_of_every_case_in_any_bound_receipt",
    "failure_policy": (
        "failure_blocked_abstention_and_no_pose_rows_retained_in_every_denominator"
    ),
    "outcome_source_policy": "upstream_receipt_recorded_outcomes_only",
    "rmsd_threshold_angstrom": 2.0,
    "top_k": 5,
    "confidence_interval_method": "two_sided_wilson_score",
    "confidence_level": (
        POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_CONFIDENCE_LEVEL
    ),
    "engine_ids": list(POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_ENGINE_IDS),
    "metric_ids": list(POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_METRIC_IDS),
    "pose_generation_performed": False,
    "engine_executed_by_this_module": False,
    "score_recalibrated": False,
    "external_engines_are_offline_reference_only": True,
}
POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_CONFIGURATION_SHA256 = _canonical_sha256(
    POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_CONFIGURATION
)

POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_BLOCKERS = (
    "external_receipts_cover_only_the_strictly_prepared_chemistry_subset",
    "internal_pose_generation_and_scoring_not_scientifically_validated",
    "supported_subset_selection_bias_not_resolved",
    "target_family_and_chemistry_stratified_comparison_missing",
    "independent_second_host_comparison_rerun_missing",
    "public_result_bundle_validator_missing",
    "independent_scientific_review_missing",
    "public_docking_benchmark_claim_not_authorized",
)

_RESULT_FLAGS = {
    "same_input_binding_verified": True,
    "all_failure_rows_retained": True,
    "pose_generation_performed": False,
    "engine_executed_by_this_module": False,
    "target_family_stratified": False,
    "chemistry_stratified": False,
    "independent_external_rerun_present": False,
    "public_result_bundle_validated": False,
    "benchmark_executed": False,
    "scientifically_validated": False,
    "claim_safe": False,
}

_LOWERCASE_SHA256 = frozenset("0123456789abcdef")
_EVALUATED_STATUSES = frozenset({"evaluated", "partial_evaluation"})


class PoseBustersSameInputEngineComparisonError(ValueError):
    """A bound receipt, shared input, or comparison projection is invalid."""


class _LoadedReceipt:
    __slots__ = ("file_sha256", "payload", "receipt_sha256")

    def __init__(
        self,
        *,
        payload: dict[str, Any],
        receipt_sha256: str,
        file_sha256: str,
    ) -> None:
        self.payload = payload
        self.receipt_sha256 = receipt_sha256
        self.file_sha256 = file_sha256


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PoseBustersSameInputEngineComparisonError(f"{name} must be a mapping")
    return dict(value)


def _list(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PoseBustersSameInputEngineComparisonError(f"{name} must be a list")
    return value


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _LOWERCASE_SHA256 for character in value)
    ):
        raise PoseBustersSameInputEngineComparisonError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _boolean(value: object, *, name: str) -> bool:
    if type(value) is not bool:
        raise PoseBustersSameInputEngineComparisonError(f"{name} must be boolean")
    return value


def _integer(value: object, *, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise PoseBustersSameInputEngineComparisonError(
            f"{name} must be an integer >= {minimum}"
        )
    return value


def _text(value: object, *, name: str, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > maximum
        or any(character in "\r\n\x00" for character in value)
    ):
        raise PoseBustersSameInputEngineComparisonError(
            f"{name} must be bounded single-line text"
        )
    return value


def _json_object_pairs(pairs: Sequence[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PoseBustersSameInputEngineComparisonError(
                "receipt contains a duplicate JSON key"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise PoseBustersSameInputEngineComparisonError(
        f"receipt contains forbidden JSON constant {value}"
    )


def _load_receipt(
    path: str | os.PathLike[str],
    *,
    expected_schema_id: str,
    expected_receipt_sha256: str,
) -> _LoadedReceipt:
    expected = _digest(expected_receipt_sha256, name="expected receipt")
    try:
        source = _read_exact_regular_file(
            path,
            maximum_bytes=POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_MAX_INPUT_BYTES,
        )
        metadata = Path(path).stat(follow_symlinks=False)
    except (OSError, PoseBustersArchiveIntakeError) as exc:
        raise PoseBustersSameInputEngineComparisonError(
            "receipt could not be read securely"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersSameInputEngineComparisonError(
            "receipt must be a bounded mode-0600 regular file"
        )
    try:
        raw = json.loads(
            source.decode("ascii"),
            object_pairs_hook=_json_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except PoseBustersSameInputEngineComparisonError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersSameInputEngineComparisonError(
            "receipt is not canonical ASCII JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersSameInputEngineComparisonError(
            "receipt bytes are not canonical"
        )
    payload = dict(raw)
    receipt_sha = _digest(payload.pop("receipt_sha256", None), name="receipt")
    if (
        raw.get("schema_id") != expected_schema_id
        or _canonical_sha256(payload) != receipt_sha
        or receipt_sha != expected
    ):
        raise PoseBustersSameInputEngineComparisonError(
            "receipt schema, digest, or pin is invalid"
        )
    for field in ("benchmark_executed", "scientifically_validated", "claim_safe"):
        if raw.get(field) is not False:
            raise PoseBustersSameInputEngineComparisonError(
                f"bound receipt must keep {field}=false"
            )
    return _LoadedReceipt(
        payload=raw,
        receipt_sha256=receipt_sha,
        file_sha256=hashlib.sha256(source).hexdigest(),
    )


def _wilson_interval(numerator: int, denominator: int) -> tuple[float, float]:
    if denominator <= 0 or numerator < 0 or numerator > denominator:
        raise PoseBustersSameInputEngineComparisonError(
            "Wilson interval counts are invalid"
        )
    estimate = numerator / denominator
    z = POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_Z
    adjustment = 1.0 + z * z / denominator
    center = (estimate + z * z / (2.0 * denominator)) / adjustment
    margin = (
        z
        * math.sqrt(
            estimate * (1.0 - estimate) / denominator
            + z * z / (4.0 * denominator * denominator)
        )
        / adjustment
    )
    low = min(max(0.0, center - margin), estimate)
    high = max(min(1.0, center + margin), estimate)
    return low, high


def _pose_outcome(row: Mapping[str, Any], *, name: str) -> dict[str, Any]:
    return {
        "pose_rank": _integer(row.get("pose_rank"), name=f"{name} pose rank", minimum=1),
        "status": _text(row.get("status"), name=f"{name} pose status"),
        "all_non_rmsd_binary_tests_pass": _boolean(
            row.get("all_non_rmsd_binary_tests_pass"),
            name=f"{name} pose validity",
        ),
        "rmsd_evaluated": _boolean(
            row.get("rmsd_evaluated"),
            name=f"{name} pose RMSD evaluation",
        ),
        "rmsd_within_2_angstrom": _boolean(
            row.get("rmsd_within_2_angstrom"),
            name=f"{name} pose RMSD hit",
        ),
    }


def _engine_case_projection(
    payload: Mapping[str, Any],
    *,
    engine_id: str,
) -> dict[str, dict[str, Any]]:
    rows = _list(payload.get("case_rows"), name=f"{engine_id} case rows")
    if (
        not rows
        or len(rows) > POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_MAX_CASES
        or payload.get("all_case_denominator") != len(rows)
    ):
        raise PoseBustersSameInputEngineComparisonError(
            f"{engine_id} case projection is invalid"
        )
    projection: dict[str, dict[str, Any]] = {}
    for item in rows:
        row = _mapping(item, name=f"{engine_id} case row")
        case = _case_id(row.get("case_id"))
        if case in projection:
            raise PoseBustersSameInputEngineComparisonError(
                f"{engine_id} case rows must be unique"
            )
        poses = tuple(
            _pose_outcome(
                _mapping(pose, name=f"{engine_id} pose row"),
                name=engine_id,
            )
            for pose in _list(
                row.get("pose_results", []),
                name=f"{engine_id} pose results",
            )
        )
        status = _text(row.get("status"), name=f"{engine_id} case status")
        ranked = sorted(poses, key=lambda pose: pose["pose_rank"])
        top_1 = ranked[0] if ranked else None
        top_5 = ranked[:5]
        projection[case] = {
            "case_id": case,
            "status": status,
            "case_evaluated": status in _EVALUATED_STATUSES,
            "pose_count": len(ranked),
            "any_physically_valid_pose": any(
                pose["all_non_rmsd_binary_tests_pass"] for pose in ranked
            ),
            "top_1_valid_pose": bool(
                top_1 is not None and top_1["all_non_rmsd_binary_tests_pass"]
            ),
            "top_1_rmsd_hit": bool(
                top_1 is not None
                and top_1["rmsd_evaluated"]
                and top_1["rmsd_within_2_angstrom"]
            ),
            "top_5_rmsd_hit": any(
                pose["rmsd_evaluated"] and pose["rmsd_within_2_angstrom"]
                for pose in top_5
            ),
            "top_1_valid_rmsd_hit": bool(
                top_1 is not None
                and top_1["all_non_rmsd_binary_tests_pass"]
                and top_1["rmsd_evaluated"]
                and top_1["rmsd_within_2_angstrom"]
            ),
        }
    return projection


_METRIC_FIELDS = {
    "evaluated_case_rate": "case_evaluated",
    "any_physically_valid_pose_rate": "any_physically_valid_pose",
    "top_1_valid_pose_rate": "top_1_valid_pose",
    "top_1_rmsd_hit_rate": "top_1_rmsd_hit",
    "top_5_rmsd_hit_rate": "top_5_rmsd_hit",
    "top_1_valid_rmsd_hit_rate": "top_1_valid_rmsd_hit",
}


def _engine_metrics(
    engine_id: str,
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    denominator = len(rows)
    for metric_id in POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_METRIC_IDS:
        field = _METRIC_FIELDS[metric_id]
        numerator = sum(bool(row[engine_id][field]) for row in rows)
        low, high = _wilson_interval(numerator, denominator)
        metrics.append(
            {
                "schema_id": (
                    POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_METRIC_SCHEMA_ID
                ),
                "engine_id": engine_id,
                "metric_id": metric_id,
                "numerator": numerator,
                "denominator": denominator,
                "denominator_scope": "all_shared_cases",
                "estimate_binary64_hex": (numerator / denominator).hex(),
                "confidence_level_binary64_hex": (
                    POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_CONFIDENCE_LEVEL.hex()
                ),
                "confidence_interval_low_binary64_hex": low.hex(),
                "confidence_interval_high_binary64_hex": high.hex(),
                "confidence_interval_method": "two_sided_wilson_score",
            }
        )
    return metrics


def _pairwise_agreement(
    rows: Sequence[Mapping[str, Any]],
    *,
    external_engine_id: str,
) -> dict[str, Any]:
    denominator = len(rows)
    both = sum(
        row["internal"]["top_1_rmsd_hit"] and row[external_engine_id]["top_1_rmsd_hit"]
        for row in rows
    )
    internal_only = sum(
        row["internal"]["top_1_rmsd_hit"]
        and not row[external_engine_id]["top_1_rmsd_hit"]
        for row in rows
    )
    external_only = sum(
        row[external_engine_id]["top_1_rmsd_hit"]
        and not row["internal"]["top_1_rmsd_hit"]
        for row in rows
    )
    neither = denominator - both - internal_only - external_only
    agreement = both + neither
    low, high = _wilson_interval(agreement, denominator)
    return {
        "external_engine_id": external_engine_id,
        "denominator": denominator,
        "both_top_1_rmsd_hit_case_count": both,
        "internal_only_top_1_rmsd_hit_case_count": internal_only,
        "external_only_top_1_rmsd_hit_case_count": external_only,
        "neither_top_1_rmsd_hit_case_count": neither,
        "top_1_rmsd_hit_agreement_case_count": agreement,
        "top_1_rmsd_hit_agreement_rate_binary64_hex": (
            agreement / denominator
        ).hex(),
        "top_1_rmsd_hit_agreement_confidence_interval_low_binary64_hex": low.hex(),
        "top_1_rmsd_hit_agreement_confidence_interval_high_binary64_hex": high.hex(),
        "both_engines_evaluated_case_count": sum(
            row["internal"]["case_evaluated"]
            and row[external_engine_id]["case_evaluated"]
            for row in rows
        ),
    }


def _source_members() -> tuple[tuple[str, str], ...]:
    paths = (
        (
            "posebusters_same_input_engine_comparison",
            Path(__file__).resolve(),
        ),
        (
            "posebusters_internal_oracle_evaluation",
            Path(oracle_module.__file__).resolve(),
        ),
        (
            "posebusters_generated_pose_evaluation",
            Path(vina_module.__file__).resolve(),
        ),
        (
            "posebusters_external_generated_pose_evaluation",
            Path(external_module.__file__).resolve(),
        ),
    )
    return tuple((role, _source_file_sha256(path)) for role, path in paths)


def _atomic_write_new(path: str | os.PathLike[str], source: bytes) -> Path:
    if len(source) > POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_MAX_RECEIPT_BYTES:
        raise PoseBustersSameInputEngineComparisonError(
            "comparison receipt exceeds its byte bound"
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
            raise PoseBustersSameInputEngineComparisonError(
                "comparison output already exists"
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


class PoseBustersSameInputEngineComparisonReceipt:
    """Canonical, claim-closed same-input engine comparison."""

    __slots__ = ("_payload_bytes",)

    def __init__(self, payload: Mapping[str, Any]) -> None:
        if "receipt_sha256" in payload:
            raise PoseBustersSameInputEngineComparisonError(
                "receipt payload cannot predefine its digest"
            )
        self._payload_bytes = _canonical_bytes(dict(payload))

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


def _receipt_binding(loaded: _LoadedReceipt, *, engine_id: str) -> dict[str, Any]:
    return {
        "engine_id": engine_id,
        "schema_id": loaded.payload["schema_id"],
        "receipt_sha256": loaded.receipt_sha256,
        "file_sha256": loaded.file_sha256,
        "archive_intake_receipt_sha256": _digest(
            loaded.payload.get("archive_intake_receipt_sha256"),
            name=f"{engine_id} archive intake",
        ),
        "all_case_denominator": _integer(
            loaded.payload.get("all_case_denominator"),
            name=f"{engine_id} all-case denominator",
            minimum=1,
        ),
    }


def _build_comparison(
    internal_oracle_receipt_path: str | os.PathLike[str],
    vina_evaluation_receipt_path: str | os.PathLike[str],
    gnina_evaluation_receipt_path: str | os.PathLike[str],
    smina_evaluation_receipt_path: str | os.PathLike[str],
    *,
    expected_internal_oracle_receipt_sha256: str,
    expected_vina_evaluation_receipt_sha256: str,
    expected_gnina_evaluation_receipt_sha256: str,
    expected_smina_evaluation_receipt_sha256: str,
) -> PoseBustersSameInputEngineComparisonReceipt:
    internal = _load_receipt(
        internal_oracle_receipt_path,
        expected_schema_id=(
            oracle_module.POSEBUSTERS_INTERNAL_ORACLE_EVALUATION_SCHEMA_ID
        ),
        expected_receipt_sha256=expected_internal_oracle_receipt_sha256,
    )
    vina = _load_receipt(
        vina_evaluation_receipt_path,
        expected_schema_id=(
            vina_module.POSEBUSTERS_GENERATED_POSE_EVALUATION_SCHEMA_ID
        ),
        expected_receipt_sha256=expected_vina_evaluation_receipt_sha256,
    )
    external_schema = (
        external_module.POSEBUSTERS_EXTERNAL_GENERATED_POSE_EVALUATION_SCHEMA_ID
    )
    gnina = _load_receipt(
        gnina_evaluation_receipt_path,
        expected_schema_id=external_schema,
        expected_receipt_sha256=expected_gnina_evaluation_receipt_sha256,
    )
    smina = _load_receipt(
        smina_evaluation_receipt_path,
        expected_schema_id=external_schema,
        expected_receipt_sha256=expected_smina_evaluation_receipt_sha256,
    )
    for loaded, engine_id in ((gnina, "gnina"), (smina, "smina")):
        if loaded.payload.get("engine_id") != engine_id:
            raise PoseBustersSameInputEngineComparisonError(
                "external evaluation receipt does not name its expected engine"
            )
    bindings = [
        _receipt_binding(internal, engine_id="internal"),
        _receipt_binding(vina, engine_id="vina"),
        _receipt_binding(gnina, engine_id="gnina"),
        _receipt_binding(smina, engine_id="smina"),
    ]
    intake_digests = {row["archive_intake_receipt_sha256"] for row in bindings}
    if len(intake_digests) != 1:
        raise PoseBustersSameInputEngineComparisonError(
            "bound receipts do not name the same archive intake"
        )
    receipt_digests = {row["receipt_sha256"] for row in bindings}
    if len(receipt_digests) != len(bindings):
        raise PoseBustersSameInputEngineComparisonError(
            "bound receipts must be four distinct receipts"
        )
    projections = {
        "internal": _engine_case_projection(internal.payload, engine_id="internal"),
        "vina": _engine_case_projection(vina.payload, engine_id="vina"),
        "gnina": _engine_case_projection(gnina.payload, engine_id="gnina"),
        "smina": _engine_case_projection(smina.payload, engine_id="smina"),
    }
    case_ids = tuple(
        sorted(
            {
                case
                for projection in projections.values()
                for case in projection
            }
        )
    )
    if not case_ids or len(case_ids) > (
        POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_MAX_CASES
    ):
        raise PoseBustersSameInputEngineComparisonError(
            "shared case denominator is invalid"
        )
    absent = {
        "case_id": "",
        "status": "absent_from_receipt",
        "case_evaluated": False,
        "pose_count": 0,
        "any_physically_valid_pose": False,
        "top_1_valid_pose": False,
        "top_1_rmsd_hit": False,
        "top_5_rmsd_hit": False,
        "top_1_valid_rmsd_hit": False,
    }
    case_rows: list[dict[str, Any]] = []
    for case in case_ids:
        row: dict[str, Any] = {
            "schema_id": (
                POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_CASE_SCHEMA_ID
            ),
            "case_id": case,
        }
        for engine_id in POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_ENGINE_IDS:
            outcome = projections[engine_id].get(case)
            row[engine_id] = (
                dict(outcome) if outcome is not None else {**absent, "case_id": case}
            )
        row["engine_ids_present"] = [
            engine_id
            for engine_id in POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_ENGINE_IDS
            if case in projections[engine_id]
        ]
        row["present_in_every_receipt"] = len(row["engine_ids_present"]) == len(
            POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_ENGINE_IDS
        )
        case_rows.append(row)
    metrics = [
        metric
        for engine_id in POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_ENGINE_IDS
        for metric in _engine_metrics(engine_id, case_rows)
    ]
    agreements = [
        _pairwise_agreement(case_rows, external_engine_id=engine_id)
        for engine_id in ("vina", "gnina", "smina")
    ]
    source_members = _source_members()
    payload = {
        "schema_id": POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_SCHEMA_ID,
        "archive_intake_receipt_sha256": next(iter(intake_digests)),
        "bound_receipts": bindings,
        "all_case_denominator": len(case_rows),
        "cases_present_in_every_receipt": sum(
            row["present_in_every_receipt"] for row in case_rows
        ),
        "case_id_projection_sha256": _canonical_sha256(list(case_ids)),
        "case_rows": case_rows,
        "metrics": metrics,
        "internal_versus_external_top_1_agreement": agreements,
        "implementation_source_members": dict(source_members),
        "implementation_source_sha256": _canonical_sha256(dict(source_members)),
        "configuration": POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_CONFIGURATION,
        "configuration_sha256": (
            POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_CONFIGURATION_SHA256
        ),
        "scientific_blockers": list(
            POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_BLOCKERS
        ),
        **_RESULT_FLAGS,
    }
    return PoseBustersSameInputEngineComparisonReceipt(payload)


def materialize_posebusters_same_input_engine_comparison(
    internal_oracle_receipt_path: str | os.PathLike[str],
    vina_evaluation_receipt_path: str | os.PathLike[str],
    gnina_evaluation_receipt_path: str | os.PathLike[str],
    smina_evaluation_receipt_path: str | os.PathLike[str],
    *,
    expected_internal_oracle_receipt_sha256: str,
    expected_vina_evaluation_receipt_sha256: str,
    expected_gnina_evaluation_receipt_sha256: str,
    expected_smina_evaluation_receipt_sha256: str,
) -> PoseBustersSameInputEngineComparisonReceipt:
    """Compare the internal oracle with Vina/GNINA/Smina over one shared intake."""

    return _build_comparison(
        internal_oracle_receipt_path,
        vina_evaluation_receipt_path,
        gnina_evaluation_receipt_path,
        smina_evaluation_receipt_path,
        expected_internal_oracle_receipt_sha256=(
            expected_internal_oracle_receipt_sha256
        ),
        expected_vina_evaluation_receipt_sha256=(
            expected_vina_evaluation_receipt_sha256
        ),
        expected_gnina_evaluation_receipt_sha256=(
            expected_gnina_evaluation_receipt_sha256
        ),
        expected_smina_evaluation_receipt_sha256=(
            expected_smina_evaluation_receipt_sha256
        ),
    )


def verify_posebusters_same_input_engine_comparison_receipt(
    comparison_receipt_path: str | os.PathLike[str],
    internal_oracle_receipt_path: str | os.PathLike[str],
    vina_evaluation_receipt_path: str | os.PathLike[str],
    gnina_evaluation_receipt_path: str | os.PathLike[str],
    smina_evaluation_receipt_path: str | os.PathLike[str],
    *,
    expected_comparison_receipt_sha256: str,
    expected_internal_oracle_receipt_sha256: str,
    expected_vina_evaluation_receipt_sha256: str,
    expected_gnina_evaluation_receipt_sha256: str,
    expected_smina_evaluation_receipt_sha256: str,
) -> PoseBustersSameInputEngineComparisonReceipt:
    """Recompute the comparison and require byte-exact reconstruction."""

    loaded = _load_receipt(
        comparison_receipt_path,
        expected_schema_id=POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_SCHEMA_ID,
        expected_receipt_sha256=expected_comparison_receipt_sha256,
    )
    expected = _build_comparison(
        internal_oracle_receipt_path,
        vina_evaluation_receipt_path,
        gnina_evaluation_receipt_path,
        smina_evaluation_receipt_path,
        expected_internal_oracle_receipt_sha256=(
            expected_internal_oracle_receipt_sha256
        ),
        expected_vina_evaluation_receipt_sha256=(
            expected_vina_evaluation_receipt_sha256
        ),
        expected_gnina_evaluation_receipt_sha256=(
            expected_gnina_evaluation_receipt_sha256
        ),
        expected_smina_evaluation_receipt_sha256=(
            expected_smina_evaluation_receipt_sha256
        ),
    )
    if loaded.receipt_sha256 != expected.fingerprint_sha256:
        raise PoseBustersSameInputEngineComparisonError(
            "comparison receipt failed exact reconstruction"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-same-input-compare",
        description=(
            "Compare the internal PoseBusters oracle with same-input "
            "Vina/GNINA/Smina evaluations while keeping every docking claim "
            "closed."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    materialize = subparsers.add_parser("materialize")
    verify = subparsers.add_parser("verify")
    for command in (materialize, verify):
        command.add_argument("--internal-oracle-receipt", required=True)
        command.add_argument("--vina-evaluation-receipt", required=True)
        command.add_argument("--gnina-evaluation-receipt", required=True)
        command.add_argument("--smina-evaluation-receipt", required=True)
        command.add_argument(
            "--expected-internal-oracle-receipt-sha256",
            required=True,
        )
        command.add_argument(
            "--expected-vina-evaluation-receipt-sha256",
            required=True,
        )
        command.add_argument(
            "--expected-gnina-evaluation-receipt-sha256",
            required=True,
        )
        command.add_argument(
            "--expected-smina-evaluation-receipt-sha256",
            required=True,
        )
    materialize.add_argument("--output", required=True)
    verify.add_argument("--receipt", required=True)
    verify.add_argument("--expected-comparison-receipt-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    common = {
        "internal_oracle_receipt_path": args.internal_oracle_receipt,
        "vina_evaluation_receipt_path": args.vina_evaluation_receipt,
        "gnina_evaluation_receipt_path": args.gnina_evaluation_receipt,
        "smina_evaluation_receipt_path": args.smina_evaluation_receipt,
        "expected_internal_oracle_receipt_sha256": (
            args.expected_internal_oracle_receipt_sha256
        ),
        "expected_vina_evaluation_receipt_sha256": (
            args.expected_vina_evaluation_receipt_sha256
        ),
        "expected_gnina_evaluation_receipt_sha256": (
            args.expected_gnina_evaluation_receipt_sha256
        ),
        "expected_smina_evaluation_receipt_sha256": (
            args.expected_smina_evaluation_receipt_sha256
        ),
    }
    if args.command == "materialize":
        receipt = materialize_posebusters_same_input_engine_comparison(**common)
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_same_input_engine_comparison_receipt(
            comparison_receipt_path=args.receipt,
            expected_comparison_receipt_sha256=(
                args.expected_comparison_receipt_sha256
            ),
            **common,
        )
    payload = receipt.to_dict()
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": payload["all_case_denominator"],
                "cases_present_in_every_receipt": payload[
                    "cases_present_in_every_receipt"
                ],
                "same_input_binding_verified": True,
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
    "POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_BLOCKERS",
    "POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_CASE_SCHEMA_ID",
    "POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_CONFIDENCE_LEVEL",
    "POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_CONFIGURATION",
    "POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_CONFIGURATION_SHA256",
    "POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_ENGINE_IDS",
    "POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_MAX_CASES",
    "POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_MAX_INPUT_BYTES",
    "POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_MAX_RECEIPT_BYTES",
    "POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_METRIC_IDS",
    "POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_METRIC_SCHEMA_ID",
    "POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_SCHEMA_ID",
    "PoseBustersSameInputEngineComparisonError",
    "PoseBustersSameInputEngineComparisonReceipt",
    "main",
    "materialize_posebusters_same_input_engine_comparison",
    "verify_posebusters_same_input_engine_comparison_receipt",
]
