"""Fail-closed PoseBusters pose-ranking calibration intake.

This module joins the exact 308-case Vina, GNINA, and Smina execution and
PoseBusters evaluation receipts to the archive, preparation, and RCSB/Pfam
target-family receipts.  It exposes engine-specific decomposed score terms and
holdout labels while retaining one explicit failure row for every case without
an evaluated pose.

The resulting receipt is deliberately *not* a
``PoseRankingCalibrationPartition``.  The current evidence chain does not carry
an accepted scaffold identity or one coordinate digest per generated pose, and
Pfam annotation is incomplete.  It also has no fit manifest or leakage audit.
Those omissions remain machine-readable blockers rather than being replaced by
synthetic hashes.  PoseBusters labels are fixed to ``split_role=test`` and this
module never calls a fitting API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Mapping, Sequence

from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _source_file_sha256,
)
from .public_posebusters_external_binary_execution import (
    POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID,
)
from .public_posebusters_external_generated_pose_evaluation import (
    POSEBUSTERS_EXTERNAL_GENERATED_POSE_EVALUATION_SCHEMA_ID,
)
from .public_posebusters_external_preparation import (
    POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID,
)
from .public_posebusters_generated_pose_evaluation import (
    POSEBUSTERS_GENERATED_POSE_EVALUATION_SCHEMA_ID,
)
from .public_posebusters_intake import (
    POSEBUSTERS_ARCHIVE_INTAKE_SCHEMA_ID,
    POSEBUSTERS_ARCHIVE_MEMBER_ROLES,
    PoseBustersArchiveIntakeError,
    _read_exact_regular_file,
)
from .public_posebusters_rcsb_target_family_binding import (
    POSEBUSTERS_RCSB_TARGET_FAMILY_RECEIPT_SCHEMA_ID,
)
from .public_posebusters_vina_execution import (
    POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID,
)


POSEBUSTERS_POSE_RANKING_INTAKE_ROW_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_ranking_intake_row/1.0.0"
)
POSEBUSTERS_POSE_RANKING_INTAKE_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_ranking_intake_case/1.0.0"
)
POSEBUSTERS_POSE_RANKING_INTAKE_ENGINE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_ranking_intake_engine/1.0.0"
)
POSEBUSTERS_POSE_RANKING_INTAKE_METRIC_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_ranking_intake_metric/1.0.0"
)
POSEBUSTERS_POSE_RANKING_INTAKE_INPUT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_ranking_intake_input/1.0.0"
)
POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_pose_ranking_intake/1.0.0"
)

POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES = ("vina", "gnina", "smina")
POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR = 308
POSEBUSTERS_POSE_RANKING_INTAKE_MAX_INPUT_BYTES = 64 * 1024 * 1024
POSEBUSTERS_POSE_RANKING_INTAKE_MAX_RECEIPT_BYTES = 32 * 1024 * 1024
POSEBUSTERS_POSE_RANKING_INTAKE_CONFIDENCE_LEVEL = 0.95
POSEBUSTERS_POSE_RANKING_INTAKE_Z = 1.959963984540054

POSEBUSTERS_POSE_RANKING_INTAKE_TERM_ORDERS = {
    "vina": ("total", "inter", "intra", "torsions", "intra_best_pose"),
    "gnina": (
        "minimized_affinity_kcal_per_mol",
        "cnn_pose_score",
        "cnn_affinity",
    ),
    "smina": ("minimized_affinity_kcal_per_mol",),
}

POSEBUSTERS_POSE_RANKING_INTAKE_CONFIGURATION = {
    "case_denominator": "all_308_cases_per_engine",
    "case_without_evaluated_pose": "one_explicit_failure_row",
    "component_namespace": "engine_id_dot_source_component_id",
    "failure_row_terms": "empty",
    "native_like_label": "posebusters_direct_rmsd_within_2_angstrom",
    "partition_policy": "do_not_materialize_until_all_identity_blockers_close",
    "physical_validity_label": "all_non_rmsd_binary_tests_pass",
    "pose_identity_policy": "do_not_derive_pose_coordinate_sha256_from_rank_or_artifact",
    "scaffold_identity_policy": "do_not_alias_ligand_file_sha256_as_scaffold_sha256",
    "split_role": "test",
    "target_family_policy": "exact_rcsb_pfam_set_or_explicit_missing",
    "test_label_fit_policy": "forbidden",
}
POSEBUSTERS_POSE_RANKING_INTAKE_CONFIGURATION_SHA256 = _canonical_sha256(
    POSEBUSTERS_POSE_RANKING_INTAKE_CONFIGURATION
)

POSEBUSTERS_POSE_RANKING_INTAKE_PARTITION_BLOCKERS = (
    "per_pose_coordinate_sha256_missing",
    "accepted_ligand_scaffold_sha256_missing",
    "complete_target_family_assignment_missing",
)
POSEBUSTERS_POSE_RANKING_INTAKE_EVALUATION_LINK_BLOCKERS = (
    "calibration_fit_partition_manifest_missing",
    "fit_to_test_target_sequence_leakage_audit_missing",
    "fit_to_test_ligand_scaffold_leakage_audit_missing",
)
POSEBUSTERS_POSE_RANKING_INTAKE_SCIENTIFIC_BLOCKERS = (
    *POSEBUSTERS_POSE_RANKING_INTAKE_PARTITION_BLOCKERS,
    *POSEBUSTERS_POSE_RANKING_INTAKE_EVALUATION_LINK_BLOCKERS,
    "only_strictly_prepared_chemistry_subset_has_scored_poses",
    "independent_external_rerun_missing",
    "independent_scientific_review_missing",
    "public_pose_ranking_calibration_claim_not_authorized",
)

_SHA256_CHARACTERS = frozenset("0123456789abcdef")
_EXECUTION_STATUSES = {
    "success",
    "engine_failure",
    "blocked_preparation_failure",
    "blocked_upstream_failure",
    "abstain_chemistry_scope",
}
_EVALUATION_STATUSES = {
    "evaluated",
    "partial_evaluation",
    "evaluation_failure",
    "blocked_engine_failure",
    "blocked_vina_engine_failure",
    "blocked_preparation_failure",
    "blocked_upstream_failure",
    "abstain_chemistry_scope",
}
_POSE_STATUSES = {"evaluated", "evaluation_failure"}


class PoseBustersPoseRankingIntakeError(ValueError):
    """A receipt identity, score projection, or holdout boundary failed closed."""


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_CHARACTERS for character in value)
    ):
        raise PoseBustersPoseRankingIntakeError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _optional_digest(value: object, *, name: str) -> str | None:
    if value in (None, ""):
        return None
    return _digest(value, name=name)


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PoseBustersPoseRankingIntakeError(f"{name} must be an object")
    return value


def _list(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PoseBustersPoseRankingIntakeError(f"{name} must be a list")
    return value


def _text(value: object, *, name: str, allow_empty: bool = False) -> str:
    if (
        not isinstance(value, str)
        or (not value and not allow_empty)
        or len(value.encode("utf-8")) > 512
        or any(character in "\r\n\x00" for character in value)
    ):
        raise PoseBustersPoseRankingIntakeError(
            f"{name} must be bounded text"
        )
    return value


def _boolean(value: object, *, name: str) -> bool:
    if type(value) is not bool:
        raise PoseBustersPoseRankingIntakeError(f"{name} must be boolean")
    return value


def _nonnegative_int(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PoseBustersPoseRankingIntakeError(
            f"{name} must be a non-negative integer"
        )
    return value


def _positive_int(value: object, *, name: str) -> int:
    result = _nonnegative_int(value, name=name)
    if result == 0:
        raise PoseBustersPoseRankingIntakeError(
            f"{name} must be a positive integer"
        )
    return result


def _binary64_hex(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise PoseBustersPoseRankingIntakeError(
            f"{name} must be canonical binary64 text"
        )
    try:
        number = float.fromhex(value)
    except ValueError as exc:
        raise PoseBustersPoseRankingIntakeError(
            f"{name} must be canonical binary64 text"
        ) from exc
    if not math.isfinite(number) or number.hex() != value:
        raise PoseBustersPoseRankingIntakeError(
            f"{name} must be canonical finite binary64"
        )
    return value


def _case_id(value: object) -> str:
    case = _text(value, name="PoseBusters case ID")
    parts = case.split("_")
    if (
        len(parts) != 2
        or len(parts[0]) != 4
        or not all(part.isalnum() and part.upper() == part for part in parts)
    ):
        raise PoseBustersPoseRankingIntakeError(
            "PoseBusters case ID is invalid"
        )
    return case


def _engine_mapping(
    value: Mapping[str, Any],
    *,
    name: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(
        POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
    ):
        raise PoseBustersPoseRankingIntakeError(
            f"{name} must contain exactly vina, gnina, and smina"
        )
    return {engine: value[engine] for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES}


class _LoadedReceipt:
    __slots__ = ("file_sha256", "payload", "receipt_sha256", "schema_id")

    def __init__(
        self,
        *,
        payload: dict[str, Any],
        receipt_sha256: str,
        file_sha256: str,
        schema_id: str,
    ) -> None:
        self.payload = payload
        self.receipt_sha256 = receipt_sha256
        self.file_sha256 = file_sha256
        self.schema_id = schema_id


def _load_receipt(
    receipt_path: str | os.PathLike[str],
    *,
    expected_schema_id: str,
    expected_receipt_sha256: str | None = None,
) -> _LoadedReceipt:
    try:
        source = _read_exact_regular_file(
            receipt_path,
            maximum_bytes=POSEBUSTERS_POSE_RANKING_INTAKE_MAX_INPUT_BYTES,
        )
        metadata = Path(receipt_path).stat(follow_symlinks=False)
    except (PoseBustersArchiveIntakeError, OSError) as exc:
        raise PoseBustersPoseRankingIntakeError(
            "pose-ranking intake receipt could not be read securely"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersPoseRankingIntakeError(
            "pose-ranking intake receipts must remain mode 0600"
        )
    try:
        raw = json.loads(source)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersPoseRankingIntakeError(
            "pose-ranking intake receipt is not canonical JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersPoseRankingIntakeError(
            "pose-ranking intake receipt bytes are not canonical"
        )
    payload = dict(raw)
    receipt_sha = _digest(
        payload.pop("receipt_sha256", None),
        name="source receipt",
    )
    if (
        raw.get("schema_id") != expected_schema_id
        or _canonical_sha256(payload) != receipt_sha
        or (
            expected_receipt_sha256 is not None
            and receipt_sha
            != _digest(
                expected_receipt_sha256,
                name="expected source receipt",
            )
        )
        or raw.get("scientifically_validated") is not False
        or raw.get("claim_safe") is not False
    ):
        raise PoseBustersPoseRankingIntakeError(
            "pose-ranking intake source receipt identity is invalid"
        )
    return _LoadedReceipt(
        payload=raw,
        receipt_sha256=receipt_sha,
        file_sha256=hashlib.sha256(source).hexdigest(),
        schema_id=expected_schema_id,
    )


def _case_map(
    receipt: _LoadedReceipt,
    *,
    name: str,
) -> tuple[tuple[str, ...], dict[str, dict[str, Any]]]:
    rows = _list(receipt.payload.get("case_rows"), name=f"{name} case rows")
    if (
        len(rows) != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
        or receipt.payload.get("all_case_denominator", len(rows)) != len(rows)
    ):
        raise PoseBustersPoseRankingIntakeError(
            f"{name} must retain the exact 308-case denominator"
        )
    parsed: list[tuple[str, dict[str, Any]]] = []
    for raw in rows:
        row = _mapping(raw, name=f"{name} case row")
        parsed.append((_case_id(row.get("case_id")), row))
    case_ids = tuple(case for case, _ in parsed)
    if case_ids != tuple(sorted(case_ids)) or len(set(case_ids)) != len(case_ids):
        raise PoseBustersPoseRankingIntakeError(
            f"{name} case IDs must be unique and canonically ordered"
        )
    return case_ids, dict(parsed)


def _archive_artifacts(
    row: Mapping[str, Any],
) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for raw in _list(row.get("artifacts"), name="archive case artifacts"):
        artifact = _mapping(raw, name="archive artifact")
        role = _text(artifact.get("role"), name="archive artifact role")
        if role in artifacts:
            raise PoseBustersPoseRankingIntakeError(
                "archive artifact roles must be unique"
            )
        artifacts[role] = _digest(
            artifact.get("sha256"),
            name=f"archive {role}",
        )
    if set(artifacts) != set(POSEBUSTERS_ARCHIVE_MEMBER_ROLES):
        raise PoseBustersPoseRankingIntakeError(
            "archive case does not expose the exact input artifact roles"
        )
    return artifacts


def _prepared_artifacts(
    row: Mapping[str, Any],
    archive: Mapping[str, str],
) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for raw in _list(row.get("artifacts"), name="preparation case artifacts"):
        artifact = _mapping(raw, name="preparation artifact")
        role = _text(artifact.get("role"), name="preparation artifact role")
        if role in artifacts:
            raise PoseBustersPoseRankingIntakeError(
                "prepared artifact roles must be unique"
            )
        digest = _digest(artifact.get("sha256"), name=f"prepared {role}")
        source_role = _text(
            artifact.get("source_role"),
            name="prepared artifact source role",
        )
        source_sha = _digest(
            artifact.get("source_sha256"),
            name="prepared artifact source",
        )
        if archive.get(source_role) != source_sha:
            raise PoseBustersPoseRankingIntakeError(
                "prepared artifact source is cross-wired"
            )
        artifacts[role] = digest
    status = _text(row.get("status"), name="preparation status")
    expected = {"prepared_ligand_pdbqt", "prepared_receptor_pdbqt"}
    if (status == "prepared") != (set(artifacts) == expected):
        raise PoseBustersPoseRankingIntakeError(
            "preparation status and artifacts are inconsistent"
        )
    if status != "prepared" and artifacts:
        raise PoseBustersPoseRankingIntakeError(
            "non-prepared cases cannot expose prepared artifacts"
        )
    return artifacts


def _metric(
    engine_id: str,
    metric_id: str,
    numerator: int,
    denominator: int,
    denominator_scope: str,
) -> dict[str, Any]:
    if denominator <= 0 or not 0 <= numerator <= denominator:
        raise PoseBustersPoseRankingIntakeError(
            "pose-ranking intake metric counts are invalid"
        )
    estimate = numerator / denominator
    z2 = POSEBUSTERS_POSE_RANKING_INTAKE_Z**2
    scale = 1.0 + z2 / denominator
    center = (estimate + z2 / (2.0 * denominator)) / scale
    radius = (
        POSEBUSTERS_POSE_RANKING_INTAKE_Z
        * math.sqrt(
            estimate * (1.0 - estimate) / denominator
            + z2 / (4.0 * denominator**2)
        )
        / scale
    )
    return {
        "schema_id": POSEBUSTERS_POSE_RANKING_INTAKE_METRIC_SCHEMA_ID,
        "engine_id": engine_id,
        "metric_id": metric_id,
        "denominator_scope": denominator_scope,
        "numerator": numerator,
        "denominator": denominator,
        "estimate": estimate,
        "confidence_level": POSEBUSTERS_POSE_RANKING_INTAKE_CONFIDENCE_LEVEL,
        "confidence_interval_method": "wilson_score_binomial",
        "confidence_interval_low": min(
            estimate,
            max(0.0, center - radius),
        ),
        "confidence_interval_high": max(
            estimate,
            min(1.0, center + radius),
        ),
    }


def _source_input(
    role: str,
    receipt: _LoadedReceipt,
) -> dict[str, Any]:
    return {
        "schema_id": POSEBUSTERS_POSE_RANKING_INTAKE_INPUT_SCHEMA_ID,
        "role": role,
        "source_schema_id": receipt.schema_id,
        "source_receipt_sha256": receipt.receipt_sha256,
        "source_file_sha256": receipt.file_sha256,
    }


def _pose_artifact(
    engine: str,
    execution_case: Mapping[str, Any],
    prepared: Mapping[str, str],
) -> tuple[str | None, str | None, str | None]:
    raw = execution_case.get("pose_artifact")
    if raw is None:
        return None, None, None
    artifact = _mapping(raw, name=f"{engine} pose artifact")
    digest = _digest(artifact.get("sha256"), name=f"{engine} pose artifact")
    prepared_ligand = _digest(
        artifact.get("prepared_ligand_sha256"),
        name=f"{engine} prepared ligand",
    )
    prepared_receptor = _digest(
        artifact.get("prepared_receptor_sha256"),
        name=f"{engine} prepared receptor",
    )
    if (
        prepared.get("prepared_ligand_pdbqt") != prepared_ligand
        or prepared.get("prepared_receptor_pdbqt") != prepared_receptor
    ):
        raise PoseBustersPoseRankingIntakeError(
            f"{engine} pose artifact is not bound to the prepared input pair"
        )
    return digest, prepared_ligand, prepared_receptor


def _source_components(
    engine: str,
    execution_case: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    expected_order = POSEBUSTERS_POSE_RANKING_INTAKE_TERM_ORDERS[engine]
    if engine == "vina":
        order = tuple(
            _text(value, name="Vina energy component")
            for value in _list(
                execution_case.get("energy_component_order"),
                name="Vina energy component order",
            )
        )
        raw_rows = _list(
            execution_case.get("energies_binary64_hex"),
            name="Vina energy rows",
        )
        rows = tuple(
            tuple(
                _binary64_hex(value, name="Vina energy")
                for value in _list(raw, name="Vina energy row")
            )
            for raw in raw_rows
        )
    else:
        order = tuple(
            _text(value, name=f"{engine} score component")
            for value in _list(
                execution_case.get("score_component_order"),
                name=f"{engine} score component order",
            )
        )
        rows_list: list[tuple[str, ...]] = []
        for expected_rank, raw in enumerate(
            _list(
                execution_case.get("pose_scores"),
                name=f"{engine} pose scores",
            ),
            start=1,
        ):
            score = _mapping(raw, name=f"{engine} pose score")
            if score.get("pose_rank") != expected_rank:
                raise PoseBustersPoseRankingIntakeError(
                    f"{engine} pose score ranks are not contiguous"
                )
            score_order = tuple(
                _text(value, name=f"{engine} score component")
                for value in _list(
                    score.get("score_component_order"),
                    name=f"{engine} pose score order",
                )
            )
            components = tuple(
                _binary64_hex(value, name=f"{engine} score")
                for value in _list(
                    score.get("components_binary64_hex"),
                    name=f"{engine} score components",
                )
            )
            component_map = _mapping(
                score.get("components"),
                name=f"{engine} score component map",
            )
            if score_order != order or component_map != dict(
                zip(order, components)
            ):
                raise PoseBustersPoseRankingIntakeError(
                    f"{engine} score component projection is inconsistent"
                )
            rows_list.append(components)
        rows = tuple(rows_list)
    if order != expected_order or any(len(row) != len(order) for row in rows):
        raise PoseBustersPoseRankingIntakeError(
            f"{engine} score term schema is not the frozen schema"
        )
    return order, rows


def _evaluation_components(
    engine: str,
    pose: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if engine == "vina":
        order_key = "vina_energy_component_order"
        values_key = "vina_energy_components_binary64_hex"
    else:
        order_key = "score_component_order"
        values_key = "score_components_binary64_hex"
    order = tuple(
        _text(value, name=f"{engine} evaluation component")
        for value in _list(
            pose.get(order_key),
            name=f"{engine} evaluation component order",
        )
    )
    values = tuple(
        _binary64_hex(value, name=f"{engine} evaluation score")
        for value in _list(
            pose.get(values_key),
            name=f"{engine} evaluation score components",
        )
    )
    if (
        order != POSEBUSTERS_POSE_RANKING_INTAKE_TERM_ORDERS[engine]
        or len(values) != len(order)
    ):
        raise PoseBustersPoseRankingIntakeError(
            f"{engine} evaluated pose term schema is invalid"
        )
    return order, values


def _failure_code(
    evaluation_case: Mapping[str, Any],
    execution_case: Mapping[str, Any],
) -> str:
    for key, source in (
        ("error_code", evaluation_case),
        ("disposition_code", evaluation_case),
        ("error_code", execution_case),
        ("disposition_code", execution_case),
        ("status", evaluation_case),
    ):
        value = source.get(key)
        if isinstance(value, str) and value:
            return _text(value, name="failure disposition")
    raise PoseBustersPoseRankingIntakeError(
        "failure row has no source disposition"
    )


def _source_error_evidence(
    *sources: Mapping[str, Any],
) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for key in ("disposition_code", "error_stage", "error_type"):
        selected = ""
        for source in sources:
            value = source.get(key)
            if isinstance(value, str) and value:
                selected = _text(value, name=f"source {key}")
                break
        result[f"source_{key}"] = selected
    message_sha: str | None = None
    for source in sources:
        value = source.get("error_message_sha256")
        if value not in (None, ""):
            message_sha = _digest(value, name="source error message")
            break
    result["source_error_message_sha256"] = message_sha
    return result


def _atomic_write_new(
    output_path: str | os.PathLike[str],
    source: bytes,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if len(source) > POSEBUSTERS_POSE_RANKING_INTAKE_MAX_RECEIPT_BYTES:
        raise PoseBustersPoseRankingIntakeError(
            "pose-ranking intake receipt exceeds its byte bound"
        )
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
            raise PoseBustersPoseRankingIntakeError(
                "pose-ranking intake output already exists"
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


class PoseBustersPoseRankingIntakeReceipt:
    """Immutable canonical receipt assembled only by exact input reconstruction."""

    __slots__ = ("_payload_bytes",)

    def __init__(self, payload: Mapping[str, Any]) -> None:
        candidate = dict(payload)
        if "receipt_sha256" in candidate:
            raise PoseBustersPoseRankingIntakeError(
                "receipt payload must not contain its own digest"
            )
        source = _canonical_bytes(candidate)
        try:
            normalized = json.loads(source)
        except json.JSONDecodeError as exc:  # pragma: no cover - canonical helper
            raise PoseBustersPoseRankingIntakeError(
                "pose-ranking intake payload is invalid"
            ) from exc
        if (
            normalized.get("schema_id")
            != POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID
            or normalized.get("all_case_denominator")
            != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
            or normalized.get("engine_case_row_count")
            != POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR
            * len(POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES)
            or normalized.get("split_role") != "test"
            or normalized.get("test_labels_used_for_fit") is not False
            or normalized.get("calibration_fit_performed") is not False
            or normalized.get("calibration_partition_materialized") is not False
            or normalized.get("leakage_control_passed") is not False
            or normalized.get("scientifically_validated") is not False
            or normalized.get("claim_safe") is not False
        ):
            raise PoseBustersPoseRankingIntakeError(
                "pose-ranking intake payload violates the holdout contract"
            )
        self._payload_bytes = source

    @property
    def fingerprint_sha256(self) -> str:
        return hashlib.sha256(self._payload_bytes).hexdigest()

    @property
    def all_case_denominator(self) -> int:
        return POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR

    def to_dict(self) -> dict[str, Any]:
        payload = json.loads(self._payload_bytes)
        payload["receipt_sha256"] = self.fingerprint_sha256
        return payload

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict()) + b"\n"

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        return _atomic_write_new(output_path, self.canonical_bytes())


def _build_posebusters_pose_ranking_intake(
    archive_intake_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    execution_receipt_paths: Mapping[str, str | os.PathLike[str]],
    evaluation_receipt_paths: Mapping[str, str | os.PathLike[str]],
    target_family_receipt_path: str | os.PathLike[str],
    *,
    expected_evaluation_receipt_sha256s: Mapping[str, str],
    expected_target_family_receipt_sha256: str,
) -> PoseBustersPoseRankingIntakeReceipt:
    execution_paths = _engine_mapping(
        execution_receipt_paths,
        name="execution receipt paths",
    )
    evaluation_paths = _engine_mapping(
        evaluation_receipt_paths,
        name="evaluation receipt paths",
    )
    expected_evaluations = _engine_mapping(
        expected_evaluation_receipt_sha256s,
        name="expected evaluation receipt SHA-256s",
    )
    archive_receipt = _load_receipt(
        archive_intake_receipt_path,
        expected_schema_id=POSEBUSTERS_ARCHIVE_INTAKE_SCHEMA_ID,
    )
    preparation_receipt = _load_receipt(
        preparation_receipt_path,
        expected_schema_id=POSEBUSTERS_EXTERNAL_PREPARATION_SCHEMA_ID,
    )
    target_receipt = _load_receipt(
        target_family_receipt_path,
        expected_schema_id=POSEBUSTERS_RCSB_TARGET_FAMILY_RECEIPT_SCHEMA_ID,
        expected_receipt_sha256=expected_target_family_receipt_sha256,
    )
    execution_receipts: dict[str, _LoadedReceipt] = {}
    evaluation_receipts: dict[str, _LoadedReceipt] = {}
    for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
        execution_schema = (
            POSEBUSTERS_VINA_EXECUTION_SCHEMA_ID
            if engine == "vina"
            else POSEBUSTERS_EXTERNAL_BINARY_EXECUTION_SCHEMA_ID
        )
        evaluation_schema = (
            POSEBUSTERS_GENERATED_POSE_EVALUATION_SCHEMA_ID
            if engine == "vina"
            else POSEBUSTERS_EXTERNAL_GENERATED_POSE_EVALUATION_SCHEMA_ID
        )
        execution_receipts[engine] = _load_receipt(
            execution_paths[engine],
            expected_schema_id=execution_schema,
        )
        evaluation_receipts[engine] = _load_receipt(
            evaluation_paths[engine],
            expected_schema_id=evaluation_schema,
            expected_receipt_sha256=expected_evaluations[engine],
        )

    archive_ids, archive_cases = _case_map(
        archive_receipt,
        name="archive intake",
    )
    preparation_ids, preparation_cases = _case_map(
        preparation_receipt,
        name="preparation",
    )
    target_ids, target_cases = _case_map(
        target_receipt,
        name="target-family",
    )
    if not (
        archive_ids == preparation_ids == target_ids
        and preparation_receipt.payload.get("archive_intake_receipt_sha256")
        == archive_receipt.receipt_sha256
        and target_receipt.payload.get("archive_intake_receipt_sha256")
        == archive_receipt.receipt_sha256
        and target_receipt.payload.get("target_family_metrics_present") is True
        and target_receipt.payload.get(
            "complete_target_family_annotation_coverage"
        )
        is False
        and target_receipt.payload.get(
            "external_fit_training_leakage_audit_present"
        )
        is False
        and target_receipt.payload.get("leakage_control_passed") is False
    ):
        raise PoseBustersPoseRankingIntakeError(
            "archive, preparation, and target-family receipts are not one chain"
        )

    archive_by_case: dict[str, dict[str, str]] = {}
    prepared_by_case: dict[str, dict[str, str]] = {}
    target_by_case: dict[str, dict[str, Any]] = {}
    for case in archive_ids:
        archive_artifacts = _archive_artifacts(archive_cases[case])
        prepared_artifacts = _prepared_artifacts(
            preparation_cases[case],
            archive_artifacts,
        )
        target = target_cases[case]
        pdb_id = _text(target.get("pdb_id"), name="target PDB ID")
        if (
            case.split("_", 1)[0] != pdb_id
            or _digest(
                target.get("receptor_sha256"),
                name="target receptor",
            )
            != archive_artifacts["receptor_pdb"]
            or _digest(
                target.get("reference_ligand_sha256"),
                name="target reference ligand",
            )
            != archive_artifacts["reference_ligand_sdf"]
        ):
            raise PoseBustersPoseRankingIntakeError(
                "target-family case identity is cross-wired"
            )
        annotation_status = _text(
            target.get("annotation_status"),
            name="target-family annotation status",
        )
        pfam_ids = tuple(
            _text(value, name="Pfam ID")
            for value in _list(target.get("pfam_ids"), name="target Pfam IDs")
        )
        if tuple(sorted(pfam_ids)) != pfam_ids or len(set(pfam_ids)) != len(
            pfam_ids
        ):
            raise PoseBustersPoseRankingIntakeError(
                "target Pfam IDs must be unique and ordered"
            )
        pfam_set_id_raw = target.get("pfam_set_id")
        pfam_set_id = (
            None
            if pfam_set_id_raw is None
            else _text(pfam_set_id_raw, name="Pfam-set ID")
        )
        if bool(pfam_ids) != (pfam_set_id is not None):
            raise PoseBustersPoseRankingIntakeError(
                "Pfam IDs and exact Pfam-set identity disagree"
            )
        archive_by_case[case] = archive_artifacts
        prepared_by_case[case] = prepared_artifacts
        target_by_case[case] = {
            "pdb_id": pdb_id,
            "annotation_status": annotation_status,
            "pfam_ids": pfam_ids,
            "pfam_set_id": pfam_set_id,
        }

    input_receipts = [
        _source_input("archive_intake", archive_receipt),
        _source_input("external_preparation", preparation_receipt),
        _source_input("rcsb_pfam_target_family", target_receipt),
    ]
    case_rows: list[dict[str, Any]] = []
    intake_rows: list[dict[str, Any]] = []
    engine_summaries: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []

    for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
        execution_receipt = execution_receipts[engine]
        evaluation_receipt = evaluation_receipts[engine]
        execution_ids, execution_cases = _case_map(
            execution_receipt,
            name=f"{engine} execution",
        )
        evaluation_ids, evaluation_cases = _case_map(
            evaluation_receipt,
            name=f"{engine} evaluation",
        )
        if execution_ids != archive_ids or evaluation_ids != archive_ids:
            raise PoseBustersPoseRankingIntakeError(
                f"{engine} receipts do not retain the exact case identities"
            )
        execution_link_key = (
            "vina_receipt_sha256"
            if engine == "vina"
            else "execution_receipt_sha256"
        )
        execution_file_link_key = (
            "vina_receipt_file_sha256"
            if engine == "vina"
            else "execution_receipt_file_sha256"
        )
        if (
            evaluation_receipt.payload.get(execution_link_key)
            != execution_receipt.receipt_sha256
            or evaluation_receipt.payload.get(execution_file_link_key)
            != execution_receipt.file_sha256
            or execution_receipt.payload.get("preparation_receipt_sha256")
            != preparation_receipt.receipt_sha256
            or execution_receipt.payload.get("preparation_receipt_file_sha256")
            != preparation_receipt.file_sha256
            or evaluation_receipt.payload.get("preparation_receipt_sha256")
            != preparation_receipt.receipt_sha256
            or evaluation_receipt.payload.get(
                "preparation_receipt_file_sha256"
            )
            != preparation_receipt.file_sha256
            or evaluation_receipt.payload.get(
                "archive_intake_receipt_sha256"
            )
            != archive_receipt.receipt_sha256
            or (
                engine != "vina"
                and execution_receipt.payload.get("engine_id") != engine
            )
            or (
                engine != "vina"
                and evaluation_receipt.payload.get("engine_id") != engine
            )
        ):
            raise PoseBustersPoseRankingIntakeError(
                f"{engine} execution/evaluation receipt chain is invalid"
            )
        input_receipts.extend(
            (
                _source_input(f"{engine}_execution", execution_receipt),
                _source_input(f"{engine}_evaluation", evaluation_receipt),
            )
        )
        execution_configuration_sha256 = _digest(
            execution_receipt.payload.get("configuration_sha256"),
            name=f"{engine} execution configuration",
        )
        evaluation_configuration_sha256 = _digest(
            evaluation_receipt.payload.get(
                "configuration_sha256"
                if engine == "vina"
                else "evaluation_configuration_sha256"
            ),
            name=f"{engine} evaluation configuration",
        )
        runtime_sha256 = _digest(
            execution_receipt.payload.get(
                "engine_identity_sha256"
                if engine == "vina"
                else "runtime_identity_sha256"
            ),
            name=f"{engine} runtime identity",
        )
        evaluation_runtime_sha256 = _digest(
            evaluation_receipt.payload.get("runtime_identity_sha256"),
            name=f"{engine} evaluation runtime identity",
        )
        term_order = POSEBUSTERS_POSE_RANKING_INTAKE_TERM_ORDERS[engine]
        scoring_protocol_sha256 = _canonical_sha256(
            {
                "engine_id": engine,
                "execution_configuration_sha256": (
                    execution_configuration_sha256
                ),
                "execution_runtime_identity_sha256": runtime_sha256,
                "evaluation_configuration_sha256": (
                    evaluation_configuration_sha256
                ),
                "evaluation_runtime_identity_sha256": (
                    evaluation_runtime_sha256
                ),
                "score_component_order": list(term_order),
            }
        )

        engine_success_rows = 0
        engine_failure_rows = 0
        engine_evaluated_cases = 0
        engine_native_like_rows = 0
        engine_valid_rows = 0
        engine_top_1_hits = 0
        engine_top_5_hits = 0
        engine_top_1_valid_hits = 0
        engine_top_5_valid_hits = 0
        for case in archive_ids:
            execution_case = execution_cases[case]
            evaluation_case = evaluation_cases[case]
            execution_status = _text(
                execution_case.get("status"),
                name=f"{engine} execution status",
            )
            evaluation_status = _text(
                evaluation_case.get("status"),
                name=f"{engine} evaluation status",
            )
            if (
                execution_status not in _EXECUTION_STATUSES
                or evaluation_status not in _EVALUATION_STATUSES
            ):
                raise PoseBustersPoseRankingIntakeError(
                    f"{engine} case disposition is invalid"
                )
            if engine != "vina" and execution_case.get("engine_id") != engine:
                raise PoseBustersPoseRankingIntakeError(
                    f"{engine} execution case is cross-wired"
                )
            prepared = prepared_by_case[case]
            artifact_sha, prepared_ligand_sha, prepared_receptor_sha = (
                _pose_artifact(engine, execution_case, prepared)
            )
            if (execution_status == "success") != (artifact_sha is not None):
                raise PoseBustersPoseRankingIntakeError(
                    f"{engine} execution status and pose artifact disagree"
                )
            order, execution_components = _source_components(
                engine,
                execution_case,
            )
            execution_pose_count = _nonnegative_int(
                execution_case.get("pose_count"),
                name=f"{engine} execution pose count",
            )
            if (
                execution_pose_count != len(execution_components)
                or (execution_status == "success")
                != (execution_pose_count > 0)
            ):
                raise PoseBustersPoseRankingIntakeError(
                    f"{engine} execution pose count is inconsistent"
                )
            raw_poses = _list(
                evaluation_case.get("pose_results"),
                name=f"{engine} evaluated pose rows",
            )
            if len(raw_poses) != execution_pose_count:
                raise PoseBustersPoseRankingIntakeError(
                    f"{engine} evaluation does not cover every generated pose"
                )
            if execution_status == "success":
                if evaluation_status not in {
                    "evaluated",
                    "partial_evaluation",
                    "evaluation_failure",
                }:
                    raise PoseBustersPoseRankingIntakeError(
                        f"{engine} successful execution has a blocked evaluation"
                    )
            elif raw_poses:
                raise PoseBustersPoseRankingIntakeError(
                    f"{engine} failed execution cannot expose evaluated poses"
                )

            target = target_by_case[case]
            archive_artifacts = archive_by_case[case]
            common = {
                "engine_id": engine,
                "case_id": case,
                "split_role": "test",
                "target_id": target["pdb_id"],
                "target_family_id": target["pfam_set_id"],
                "target_family_annotation_status": target[
                    "annotation_status"
                ],
                "pfam_ids": list(target["pfam_ids"]),
                "receptor_sha256": archive_artifacts["receptor_pdb"],
                "ligand_start_conformer_sha256": archive_artifacts[
                    "ligand_start_conformer_sdf"
                ],
                "reference_ligand_sha256": archive_artifacts[
                    "reference_ligand_sdf"
                ],
                "prepared_ligand_sha256": prepared_ligand_sha,
                "prepared_receptor_sha256": prepared_receptor_sha,
                "pose_artifact_sha256": artifact_sha,
                "pose_coordinate_sha256": None,
                "scaffold_sha256": None,
                "scoring_protocol_sha256": scoring_protocol_sha256,
                "preparation_profile_sha256": _digest(
                    preparation_receipt.payload.get("configuration_sha256"),
                    name="preparation configuration",
                ),
                "source_execution_status": execution_status,
                "calibration_row_materializable": False,
            }
            case_success_rows = 0
            case_failure_rows = 0
            case_native_like_rows = 0
            case_valid_rows = 0
            for expected_rank, raw_pose in enumerate(raw_poses, start=1):
                pose = _mapping(raw_pose, name=f"{engine} evaluated pose")
                if pose.get("pose_rank") != expected_rank:
                    raise PoseBustersPoseRankingIntakeError(
                        f"{engine} evaluated pose ranks are not contiguous"
                    )
                pose_status = _text(
                    pose.get("status"),
                    name=f"{engine} pose evaluation status",
                )
                if pose_status not in _POSE_STATUSES:
                    raise PoseBustersPoseRankingIntakeError(
                        f"{engine} pose evaluation status is invalid"
                    )
                pose_order, pose_components = _evaluation_components(
                    engine,
                    pose,
                )
                if pose_order != order or pose_components != execution_components[
                    expected_rank - 1
                ]:
                    raise PoseBustersPoseRankingIntakeError(
                        f"{engine} evaluation score differs from execution"
                    )
                row: dict[str, Any] = {
                    "schema_id": (
                        POSEBUSTERS_POSE_RANKING_INTAKE_ROW_SCHEMA_ID
                    ),
                    **common,
                    "row_id": f"{engine}:{case}:pose:{expected_rank}",
                    "pose_rank": expected_rank,
                    "source_pose_status": pose_status,
                    "source_evaluation_status": evaluation_status,
                    **_source_error_evidence(
                        pose,
                        evaluation_case,
                        execution_case,
                    ),
                }
                if pose_status == "evaluated":
                    rmsd_evaluated = _boolean(
                        pose.get("rmsd_evaluated"),
                        name=f"{engine} RMSD-evaluated flag",
                    )
                    if not rmsd_evaluated:
                        raise PoseBustersPoseRankingIntakeError(
                            "evaluated pose lacks its holdout RMSD label"
                        )
                    native_like = _boolean(
                        pose.get("rmsd_within_2_angstrom"),
                        name=f"{engine} native-like label",
                    )
                    physically_valid = _boolean(
                        pose.get("all_non_rmsd_binary_tests_pass"),
                        name=f"{engine} physical-validity label",
                    )
                    direct_rmsd = _binary64_hex(
                        pose.get(
                            "direct_rmsd_angstrom_binary64_hex"
                        ),
                        name=f"{engine} direct RMSD",
                    )
                    row.update(
                        {
                            "status": "success",
                            "failure_code": "",
                            "score_component_order": [
                                f"{engine}.{term}" for term in pose_order
                            ],
                            "score_components_binary64_hex": list(
                                pose_components
                            ),
                            "native_like": native_like,
                            "physically_valid": physically_valid,
                            "valid_and_native_like": (
                                native_like and physically_valid
                            ),
                            "direct_rmsd_angstrom_binary64_hex": direct_rmsd,
                        }
                    )
                    case_success_rows += 1
                    case_native_like_rows += int(native_like)
                    case_valid_rows += int(physically_valid)
                else:
                    row.update(
                        {
                            "status": "failure",
                            "failure_code": _failure_code(
                                pose,
                                execution_case,
                            ),
                            "score_component_order": [],
                            "score_components_binary64_hex": [],
                            "native_like": None,
                            "physically_valid": None,
                            "valid_and_native_like": None,
                            "direct_rmsd_angstrom_binary64_hex": None,
                        }
                    )
                    case_failure_rows += 1
                row["report_sha256"] = _optional_digest(
                    pose.get("report_sha256"),
                    name=f"{engine} PoseBusters report",
                )
                row["diagnostic_sha256"] = _optional_digest(
                    pose.get("diagnostic_sha256"),
                    name=f"{engine} pose diagnostic",
                )
                row["missing_identity_codes"] = [
                    "per_pose_coordinate_sha256_missing",
                    "accepted_ligand_scaffold_sha256_missing",
                    *(
                        []
                        if target["pfam_set_id"] is not None
                        else ["complete_target_family_assignment_missing"]
                    ),
                ]
                intake_rows.append(row)
            if not raw_poses:
                row = {
                    "schema_id": (
                        POSEBUSTERS_POSE_RANKING_INTAKE_ROW_SCHEMA_ID
                    ),
                    **common,
                    "row_id": f"{engine}:{case}:case_failure",
                    "pose_rank": None,
                    "source_pose_status": None,
                    "source_evaluation_status": evaluation_status,
                    **_source_error_evidence(
                        evaluation_case,
                        execution_case,
                    ),
                    "status": "failure",
                    "failure_code": _failure_code(
                        evaluation_case,
                        execution_case,
                    ),
                    "score_component_order": [],
                    "score_components_binary64_hex": [],
                    "native_like": None,
                    "physically_valid": None,
                    "valid_and_native_like": None,
                    "direct_rmsd_angstrom_binary64_hex": None,
                    "report_sha256": None,
                    "diagnostic_sha256": _optional_digest(
                        evaluation_case.get("diagnostic_sha256"),
                        name=f"{engine} case diagnostic",
                    ),
                    "missing_identity_codes": [
                        "per_pose_coordinate_sha256_missing",
                        "accepted_ligand_scaffold_sha256_missing",
                        *(
                            []
                            if target["pfam_set_id"] is not None
                            else [
                                "complete_target_family_assignment_missing"
                            ]
                        ),
                    ],
                }
                intake_rows.append(row)
                case_failure_rows = 1
            if not case_success_rows and not case_failure_rows:
                raise PoseBustersPoseRankingIntakeError(
                    f"{engine} case produced no intake row"
                )
            engine_success_rows += case_success_rows
            engine_failure_rows += case_failure_rows
            engine_evaluated_cases += int(case_success_rows > 0)
            engine_native_like_rows += case_native_like_rows
            engine_valid_rows += case_valid_rows
            top_1 = any(
                row["status"] == "success"
                and row["case_id"] == case
                and row["engine_id"] == engine
                and row["pose_rank"] == 1
                and row["native_like"] is True
                for row in intake_rows[-max(1, len(raw_poses)) :]
            )
            top_5 = any(
                row["status"] == "success"
                and row["case_id"] == case
                and row["engine_id"] == engine
                and isinstance(row["pose_rank"], int)
                and row["pose_rank"] <= 5
                and row["native_like"] is True
                for row in intake_rows[-max(1, len(raw_poses)) :]
            )
            valid_top_1 = any(
                row["status"] == "success"
                and row["case_id"] == case
                and row["engine_id"] == engine
                and row["pose_rank"] == 1
                and row["valid_and_native_like"] is True
                for row in intake_rows[-max(1, len(raw_poses)) :]
            )
            valid_top_5 = any(
                row["status"] == "success"
                and row["case_id"] == case
                and row["engine_id"] == engine
                and isinstance(row["pose_rank"], int)
                and row["pose_rank"] <= 5
                and row["valid_and_native_like"] is True
                for row in intake_rows[-max(1, len(raw_poses)) :]
            )
            engine_top_1_hits += int(top_1)
            engine_top_5_hits += int(top_5)
            engine_top_1_valid_hits += int(valid_top_1)
            engine_top_5_valid_hits += int(valid_top_5)
            case_rows.append(
                {
                    "schema_id": (
                        POSEBUSTERS_POSE_RANKING_INTAKE_CASE_SCHEMA_ID
                    ),
                    "engine_id": engine,
                    "case_id": case,
                    "target_id": target["pdb_id"],
                    "target_family_id": target["pfam_set_id"],
                    "target_family_annotation_status": target[
                        "annotation_status"
                    ],
                    "execution_status": execution_status,
                    "evaluation_status": evaluation_status,
                    "execution_pose_count": execution_pose_count,
                    "intake_success_row_count": case_success_rows,
                    "intake_failure_row_count": case_failure_rows,
                    "native_like_pose_count": case_native_like_rows,
                    "physically_valid_pose_count": case_valid_rows,
                    "top_1_native_like": top_1,
                    "top_5_native_like": top_5,
                    "top_1_valid_and_native_like": valid_top_1,
                    "top_5_valid_and_native_like": valid_top_5,
                }
            )

        if evaluation_receipt.payload.get("evaluated_pose_count") != (
            engine_success_rows
        ) or evaluation_receipt.payload.get("physically_valid_pose_count") != (
            engine_valid_rows
        ):
            raise PoseBustersPoseRankingIntakeError(
                f"{engine} intake counts disagree with the evaluation receipt"
            )
        engine_summary = {
            "schema_id": POSEBUSTERS_POSE_RANKING_INTAKE_ENGINE_SCHEMA_ID,
            "engine_id": engine,
            "split_role": "test",
            "scoring_protocol_sha256": scoring_protocol_sha256,
            "score_component_order": [
                f"{engine}.{term}" for term in term_order
            ],
            "all_case_denominator": len(archive_ids),
            "evaluated_case_count": engine_evaluated_cases,
            "successful_pose_row_count": engine_success_rows,
            "failure_row_count": engine_failure_rows,
            "native_like_pose_count": engine_native_like_rows,
            "physically_valid_pose_count": engine_valid_rows,
            "top_1_native_like_case_count": engine_top_1_hits,
            "top_5_native_like_case_count": engine_top_5_hits,
            "top_1_valid_native_like_case_count": engine_top_1_valid_hits,
            "top_5_valid_native_like_case_count": engine_top_5_valid_hits,
            "calibration_partition_materialized": False,
            "test_labels_used_for_fit": False,
        }
        engine_summaries.append(engine_summary)
        metrics.extend(
            (
                _metric(
                    engine,
                    "evaluated_case_rate",
                    engine_evaluated_cases,
                    len(archive_ids),
                    "all_cases",
                ),
                _metric(
                    engine,
                    "top_1_native_like_case_rate",
                    engine_top_1_hits,
                    len(archive_ids),
                    "all_cases",
                ),
                _metric(
                    engine,
                    "top_5_native_like_case_rate",
                    engine_top_5_hits,
                    len(archive_ids),
                    "all_cases",
                ),
                _metric(
                    engine,
                    "top_1_valid_native_like_case_rate",
                    engine_top_1_valid_hits,
                    len(archive_ids),
                    "all_cases",
                ),
                _metric(
                    engine,
                    "top_5_valid_native_like_case_rate",
                    engine_top_5_valid_hits,
                    len(archive_ids),
                    "all_cases",
                ),
                _metric(
                    engine,
                    "native_like_pose_rate",
                    engine_native_like_rows,
                    engine_success_rows,
                    "successfully_evaluated_poses",
                ),
                _metric(
                    engine,
                    "physically_valid_pose_rate",
                    engine_valid_rows,
                    engine_success_rows,
                    "successfully_evaluated_poses",
                ),
            )
        )

    implementation_source_members = {
        "pose_ranking_calibration": _source_file_sha256(
            Path(__file__).parents[1] / "docking" / "calibration.py"
        ),
        "pose_ranking_intake": _source_file_sha256(__file__),
        "public_split_provenance": _source_file_sha256(
            Path(__file__).with_name("public_split_provenance.py")
        ),
    }
    annotated_case_count = sum(
        target_by_case[case]["pfam_set_id"] is not None for case in archive_ids
    )
    payload = {
        "schema_id": POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID,
        "dataset_id": "posebusters_benchmark_2023_308",
        "dataset_version": "zenodo-8278563-v1-journal-308",
        "split_role": "test",
        "configuration": POSEBUSTERS_POSE_RANKING_INTAKE_CONFIGURATION,
        "configuration_sha256": (
            POSEBUSTERS_POSE_RANKING_INTAKE_CONFIGURATION_SHA256
        ),
        "implementation_source_members": implementation_source_members,
        "implementation_source_sha256": _canonical_sha256(
            implementation_source_members
        ),
        "input_receipts": input_receipts,
        "all_case_denominator": len(archive_ids),
        "engine_count": len(POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES),
        "engine_case_row_count": len(case_rows),
        "intake_row_count": len(intake_rows),
        "successful_pose_row_count": sum(
            row["status"] == "success" for row in intake_rows
        ),
        "failure_row_count": sum(
            row["status"] == "failure" for row in intake_rows
        ),
        "pfam_annotated_case_count": annotated_case_count,
        "target_family_annotation_complete": (
            annotated_case_count == len(archive_ids)
        ),
        "engine_summaries": engine_summaries,
        "metrics": metrics,
        "case_rows": case_rows,
        "intake_rows": intake_rows,
        "partition_materialization_blockers": list(
            POSEBUSTERS_POSE_RANKING_INTAKE_PARTITION_BLOCKERS
        ),
        "evaluation_link_blockers": list(
            POSEBUSTERS_POSE_RANKING_INTAKE_EVALUATION_LINK_BLOCKERS
        ),
        "test_labels_used_for_fit": False,
        "calibration_fit_performed": False,
        "calibration_partition_materialized": False,
        "fit_or_training_manifest_present": False,
        "leakage_audit_present": False,
        "leakage_control_passed": False,
        "independent_external_rerun_present": False,
        "independent_scientific_review_present": False,
        "public_pose_ranking_claim_authorized": False,
        "scientific_blockers": list(
            POSEBUSTERS_POSE_RANKING_INTAKE_SCIENTIFIC_BLOCKERS
        ),
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return PoseBustersPoseRankingIntakeReceipt(payload)


def materialize_posebusters_pose_ranking_intake(
    archive_intake_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    execution_receipt_paths: Mapping[str, str | os.PathLike[str]],
    evaluation_receipt_paths: Mapping[str, str | os.PathLike[str]],
    target_family_receipt_path: str | os.PathLike[str],
    *,
    expected_evaluation_receipt_sha256s: Mapping[str, str],
    expected_target_family_receipt_sha256: str,
) -> PoseBustersPoseRankingIntakeReceipt:
    """Build test-only calibration intake from exact caller-pinned receipts."""

    return _build_posebusters_pose_ranking_intake(
        archive_intake_receipt_path,
        preparation_receipt_path,
        execution_receipt_paths,
        evaluation_receipt_paths,
        target_family_receipt_path,
        expected_evaluation_receipt_sha256s=(
            expected_evaluation_receipt_sha256s
        ),
        expected_target_family_receipt_sha256=(
            expected_target_family_receipt_sha256
        ),
    )


def verify_posebusters_pose_ranking_intake_receipt(
    intake_receipt_path: str | os.PathLike[str],
    archive_intake_receipt_path: str | os.PathLike[str],
    preparation_receipt_path: str | os.PathLike[str],
    execution_receipt_paths: Mapping[str, str | os.PathLike[str]],
    evaluation_receipt_paths: Mapping[str, str | os.PathLike[str]],
    target_family_receipt_path: str | os.PathLike[str],
    *,
    expected_evaluation_receipt_sha256s: Mapping[str, str],
    expected_target_family_receipt_sha256: str,
) -> PoseBustersPoseRankingIntakeReceipt:
    """Require byte equality with an exact reconstruction of every input."""

    try:
        source = _read_exact_regular_file(
            intake_receipt_path,
            maximum_bytes=POSEBUSTERS_POSE_RANKING_INTAKE_MAX_RECEIPT_BYTES,
        )
        metadata = Path(intake_receipt_path).stat(follow_symlinks=False)
    except (PoseBustersArchiveIntakeError, OSError) as exc:
        raise PoseBustersPoseRankingIntakeError(
            "pose-ranking intake output could not be read securely"
        ) from exc
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersPoseRankingIntakeError(
            "pose-ranking intake output must remain mode 0600"
        )
    expected = _build_posebusters_pose_ranking_intake(
        archive_intake_receipt_path,
        preparation_receipt_path,
        execution_receipt_paths,
        evaluation_receipt_paths,
        target_family_receipt_path,
        expected_evaluation_receipt_sha256s=(
            expected_evaluation_receipt_sha256s
        ),
        expected_target_family_receipt_sha256=(
            expected_target_family_receipt_sha256
        ),
    )
    if source != expected.canonical_bytes():
        raise PoseBustersPoseRankingIntakeError(
            "pose-ranking intake output differs from exact reconstruction"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-ranking-intake",
        description=(
            "Join exact Vina/GNINA/Smina PoseBusters score terms and "
            "RCSB/Pfam target families as test-only, failure-inclusive "
            "calibration intake."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("materialize", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--archive-intake-receipt", required=True)
        subparser.add_argument("--preparation-receipt", required=True)
        subparser.add_argument("--target-family-receipt", required=True)
        subparser.add_argument(
            "--expected-target-family-receipt-sha256",
            required=True,
        )
        for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES:
            subparser.add_argument(
                f"--{engine}-execution-receipt",
                required=True,
            )
            subparser.add_argument(
                f"--{engine}-evaluation-receipt",
                required=True,
            )
            subparser.add_argument(
                f"--expected-{engine}-evaluation-receipt-sha256",
                required=True,
            )
    subparsers.choices["materialize"].add_argument("--output", required=True)
    subparsers.choices["verify"].add_argument(
        "--intake-receipt",
        required=True,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    execution_paths = {
        engine: getattr(args, f"{engine}_execution_receipt")
        for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
    }
    evaluation_paths = {
        engine: getattr(args, f"{engine}_evaluation_receipt")
        for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
    }
    expected_evaluations = {
        engine: getattr(
            args,
            f"expected_{engine}_evaluation_receipt_sha256",
        )
        for engine in POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES
    }
    common = {
        "archive_intake_receipt_path": args.archive_intake_receipt,
        "preparation_receipt_path": args.preparation_receipt,
        "execution_receipt_paths": execution_paths,
        "evaluation_receipt_paths": evaluation_paths,
        "target_family_receipt_path": args.target_family_receipt,
        "expected_evaluation_receipt_sha256s": expected_evaluations,
        "expected_target_family_receipt_sha256": (
            args.expected_target_family_receipt_sha256
        ),
    }
    if args.command == "materialize":
        receipt = materialize_posebusters_pose_ranking_intake(**common)
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_pose_ranking_intake_receipt(
            intake_receipt_path=args.intake_receipt,
            **common,
        )
    payload = receipt.to_dict()
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "all_case_denominator": payload["all_case_denominator"],
                "engine_case_row_count": payload["engine_case_row_count"],
                "intake_row_count": payload["intake_row_count"],
                "successful_pose_row_count": payload[
                    "successful_pose_row_count"
                ],
                "failure_row_count": payload["failure_row_count"],
                "pfam_annotated_case_count": payload[
                    "pfam_annotated_case_count"
                ],
                "split_role": "test",
                "calibration_partition_materialized": False,
                "test_labels_used_for_fit": False,
                "leakage_control_passed": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "POSEBUSTERS_POSE_RANKING_INTAKE_ALL_CASE_DENOMINATOR",
    "POSEBUSTERS_POSE_RANKING_INTAKE_CASE_SCHEMA_ID",
    "POSEBUSTERS_POSE_RANKING_INTAKE_CONFIGURATION",
    "POSEBUSTERS_POSE_RANKING_INTAKE_CONFIGURATION_SHA256",
    "POSEBUSTERS_POSE_RANKING_INTAKE_ENGINE_SCHEMA_ID",
    "POSEBUSTERS_POSE_RANKING_INTAKE_ENGINES",
    "POSEBUSTERS_POSE_RANKING_INTAKE_EVALUATION_LINK_BLOCKERS",
    "POSEBUSTERS_POSE_RANKING_INTAKE_INPUT_SCHEMA_ID",
    "POSEBUSTERS_POSE_RANKING_INTAKE_METRIC_SCHEMA_ID",
    "POSEBUSTERS_POSE_RANKING_INTAKE_PARTITION_BLOCKERS",
    "POSEBUSTERS_POSE_RANKING_INTAKE_RECEIPT_SCHEMA_ID",
    "POSEBUSTERS_POSE_RANKING_INTAKE_ROW_SCHEMA_ID",
    "POSEBUSTERS_POSE_RANKING_INTAKE_SCIENTIFIC_BLOCKERS",
    "POSEBUSTERS_POSE_RANKING_INTAKE_TERM_ORDERS",
    "PoseBustersPoseRankingIntakeError",
    "PoseBustersPoseRankingIntakeReceipt",
    "main",
    "materialize_posebusters_pose_ranking_intake",
    "verify_posebusters_pose_ranking_intake_receipt",
]


if __name__ == "__main__":  # pragma: no cover - exercised through packaged CLI
    raise SystemExit(main())
