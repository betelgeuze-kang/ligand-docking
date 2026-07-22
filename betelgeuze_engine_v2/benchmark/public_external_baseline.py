"""Failure-inclusive same-input work orders for public external baselines.

The module binds exact prepared PDBQT receptor/ligand bytes, a frozen native-
reference pocket definition, one search box, and exact Vina/GNINA/Smina binary
identities before producing non-executing :mod:`external_baseline` work orders.
Raw PDB/SDF identity alone is intentionally insufficient: preparation bytes and
their tool/configuration provenance are required and verified from disk.

No external binary is launched here.  Native ligand coordinates may define the
redocking box but are forbidden as ligand-preparation coordinates.  The
four-case cohort remains a development contract, not a statistical benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Sequence

from .external_baseline import (
    SUPPORTED_EXTERNAL_ENGINES,
    ExternalBaselineCase,
    ExternalBaselineContractError,
    ExternalBaselineEngine,
    ExternalBaselineWorkOrder,
    _confined_file,
)
from .public_protocol import (
    FrozenPublicBenchmarkProtocol,
    PublicBenchmarkCaseDefinition,
)
from .public_suite_materialization import (
    PublicBenchmarkSuiteCaseMaterialization,
    PublicBenchmarkSuiteMaterializationReceipt,
)


PUBLIC_EXTERNAL_BASELINE_PREPARATION_TOOL_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_external_preparation_tool/1.0.0"
)
PUBLIC_EXTERNAL_BASELINE_PREPARED_ARTIFACT_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_external_prepared_artifact/1.0.0"
)
PUBLIC_EXTERNAL_BASELINE_PREPARED_CASE_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_external_prepared_case/1.0.0"
)
PUBLIC_EXTERNAL_BASELINE_CASE_VERIFICATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_external_case_verification/1.0.0"
)
PUBLIC_EXTERNAL_BASELINE_WORK_ORDER_BUNDLE_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_external_work_order_bundle/1.0.0"
)
PUBLIC_EXTERNAL_BASELINE_BOX_SIZE_ANGSTROM = (22.5, 22.5, 22.5)
PUBLIC_EXTERNAL_BASELINE_SEED = 20260723
PUBLIC_EXTERNAL_BASELINE_EXHAUSTIVENESS = 32
PUBLIC_EXTERNAL_BASELINE_NUM_MODES = 20
PUBLIC_EXTERNAL_BASELINE_CPU_COUNT = 1
PUBLIC_EXTERNAL_BASELINE_ENERGY_RANGE_KCAL_PER_MOL = 20
PUBLIC_EXTERNAL_BASELINE_BLOCKERS = (
    "four_case_contract_cohort_not_statistically_representative",
    "scientific_holdout_status_not_established",
    "prepared_input_generation_not_independently_audited",
    "external_engine_execution_results_missing",
    "external_pose_validity_and_symmetry_rmsd_receipts_missing",
    "target_family_metrics_and_confidence_intervals_missing",
    "independent_external_rerun_missing",
)

_PREPARED_ROLES = frozenset({"prepared_receptor_pdbqt", "prepared_ligand_pdbqt"})
_LOWERCASE_SHA256 = frozenset("0123456789abcdef")


class PublicExternalBaselineError(ValueError):
    """Prepared input, suite binding, or work-order evidence is invalid."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise PublicExternalBaselineError(
            "public external-baseline value is not canonical JSON"
        ) from exc


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in _LOWERCASE_SHA256 for character in value
    ):
        raise PublicExternalBaselineError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _text(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicExternalBaselineError(f"{name} must be non-empty text")
    return value.strip()


def _container_digest(value: object) -> str:
    if value == "":
        return ""
    text = _text(value, name="preparation container image digest").lower()
    if not text.startswith("sha256:"):
        raise PublicExternalBaselineError(
            "preparation container image digest must use sha256:<digest>"
        )
    _sha256(text.removeprefix("sha256:"), name="preparation container image")
    return text


def _relative_path(value: object) -> str:
    text = _text(value, name="prepared artifact relative path")
    path = Path(text)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise PublicExternalBaselineError(
            "prepared artifact path must remain below artifact_root"
        )
    return path.as_posix()


def _positive_size(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PublicExternalBaselineError(
            "prepared artifact size must be a positive integer"
        )
    return value


def _vector3(
    value: Sequence[float],
    *,
    name: str,
    positive: bool = False,
) -> tuple[float, float, float]:
    if isinstance(value, (str, bytes)):
        raise PublicExternalBaselineError(f"{name} must contain three values")
    try:
        vector = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise PublicExternalBaselineError(
            f"{name} must contain finite numeric values"
        ) from exc
    if len(vector) != 3 or any(not math.isfinite(item) for item in vector):
        raise PublicExternalBaselineError(
            f"{name} must contain three finite numeric values"
        )
    if positive and any(item <= 0.0 or item > 30.0 for item in vector):
        raise PublicExternalBaselineError(
            f"{name} values must be positive and at most 30 angstrom"
        )
    return vector  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class PublicExternalPreparationTool:
    tool_id: str
    tool_version: str
    executable_sha256: str
    configuration_sha256: str
    container_image_digest: str = ""
    schema_id: str = PUBLIC_EXTERNAL_BASELINE_PREPARATION_TOOL_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_EXTERNAL_BASELINE_PREPARATION_TOOL_SCHEMA_ID:
            raise PublicExternalBaselineError(
                "unsupported external preparation tool schema"
            )
        object.__setattr__(self, "tool_id", _text(self.tool_id, name="tool_id"))
        object.__setattr__(
            self,
            "tool_version",
            _text(self.tool_version, name="tool_version"),
        )
        object.__setattr__(
            self,
            "executable_sha256",
            _sha256(self.executable_sha256, name="preparation executable"),
        )
        object.__setattr__(
            self,
            "configuration_sha256",
            _sha256(self.configuration_sha256, name="preparation configuration"),
        )
        object.__setattr__(
            self,
            "container_image_digest",
            _container_digest(self.container_image_digest),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "schema_id": self.schema_id,
            "tool_id": self.tool_id,
            "tool_version": self.tool_version,
            "executable_sha256": self.executable_sha256,
            "configuration_sha256": self.configuration_sha256,
            "container_image_digest": self.container_image_digest,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _digest(self.to_dict())


@dataclass(frozen=True, slots=True)
class PublicExternalPreparedArtifact:
    role: str
    relative_path: str
    sha256: str
    size_bytes: int
    source_artifact_sha256: str
    preparation_tool: PublicExternalPreparationTool
    schema_id: str = PUBLIC_EXTERNAL_BASELINE_PREPARED_ARTIFACT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_EXTERNAL_BASELINE_PREPARED_ARTIFACT_SCHEMA_ID:
            raise PublicExternalBaselineError(
                "unsupported external prepared-artifact schema"
            )
        if self.role not in _PREPARED_ROLES:
            raise PublicExternalBaselineError("prepared artifact role is invalid")
        if not isinstance(self.preparation_tool, PublicExternalPreparationTool):
            raise PublicExternalBaselineError(
                "prepared artifact requires exact preparation-tool identity"
            )
        object.__setattr__(self, "relative_path", _relative_path(self.relative_path))
        object.__setattr__(
            self,
            "sha256",
            _sha256(self.sha256, name="prepared artifact"),
        )
        object.__setattr__(self, "size_bytes", _positive_size(self.size_bytes))
        object.__setattr__(
            self,
            "source_artifact_sha256",
            _sha256(self.source_artifact_sha256, name="source artifact"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "role": self.role,
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": "chemical/x-pdbqt",
            "source_artifact_sha256": self.source_artifact_sha256,
            "preparation_tool": self.preparation_tool.to_dict(),
            "prepared_artifact_verified": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _digest(self.to_dict())


@dataclass(frozen=True, slots=True)
class PublicExternalPreparedCase:
    case_id: str
    target_id: str
    receptor: PublicExternalPreparedArtifact
    ligand: PublicExternalPreparedArtifact
    pocket_center_receptor_frame_angstrom: tuple[float, float, float]
    pocket_definition_sha256: str
    box_size_angstrom: tuple[float, float, float] = (
        PUBLIC_EXTERNAL_BASELINE_BOX_SIZE_ANGSTROM
    )
    ligand_identity_seed_coordinates_used: bool = False
    native_reference_coordinates_used_for_ligand_preparation: bool = False
    native_reference_used_for_box_center_only: bool = True
    preparation_independently_audited: bool = False
    schema_id: str = PUBLIC_EXTERNAL_BASELINE_PREPARED_CASE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_EXTERNAL_BASELINE_PREPARED_CASE_SCHEMA_ID:
            raise PublicExternalBaselineError("unsupported prepared-case schema")
        case_id = _text(self.case_id, name="case_id")
        target_id = _text(self.target_id, name="target_id")
        if (
            not isinstance(self.receptor, PublicExternalPreparedArtifact)
            or self.receptor.role != "prepared_receptor_pdbqt"
            or not isinstance(self.ligand, PublicExternalPreparedArtifact)
            or self.ligand.role != "prepared_ligand_pdbqt"
        ):
            raise PublicExternalBaselineError(
                "prepared case requires receptor and ligand PDBQT roles"
            )
        center = _vector3(
            self.pocket_center_receptor_frame_angstrom,
            name="pocket center",
        )
        size = _vector3(self.box_size_angstrom, name="box size", positive=True)
        if size != PUBLIC_EXTERNAL_BASELINE_BOX_SIZE_ANGSTROM:
            raise PublicExternalBaselineError(
                "public external baseline box size must use the frozen 22.5-A cube"
            )
        if (
            self.ligand_identity_seed_coordinates_used is not False
            or self.native_reference_coordinates_used_for_ligand_preparation
            is not False
            or self.native_reference_used_for_box_center_only is not True
            or self.preparation_independently_audited is not False
        ):
            raise PublicExternalBaselineError(
                "prepared case violates the frozen no-native-pose-leak boundary"
            )
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "target_id", target_id)
        object.__setattr__(
            self, "pocket_center_receptor_frame_angstrom", center
        )
        object.__setattr__(self, "box_size_angstrom", size)
        object.__setattr__(
            self,
            "pocket_definition_sha256",
            _sha256(self.pocket_definition_sha256, name="pocket definition"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "target_id": self.target_id,
            "receptor": self.receptor.to_dict(),
            "ligand": self.ligand.to_dict(),
            "pocket_center_receptor_frame_angstrom": list(
                self.pocket_center_receptor_frame_angstrom
            ),
            "pocket_definition_sha256": self.pocket_definition_sha256,
            "box_size_angstrom": list(self.box_size_angstrom),
            "ligand_identity_seed_coordinates_used": False,
            "native_reference_coordinates_used_for_ligand_preparation": False,
            "native_reference_used_for_box_center_only": True,
            "preparation_independently_audited": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _digest(self.to_dict())


@dataclass(frozen=True, slots=True)
class PublicExternalCaseVerification:
    preparation: PublicExternalPreparedCase
    receptor_verified: bool
    ligand_verified: bool
    error_codes: tuple[str, ...]
    schema_id: str = PUBLIC_EXTERNAL_BASELINE_CASE_VERIFICATION_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_EXTERNAL_BASELINE_CASE_VERIFICATION_SCHEMA_ID:
            raise PublicExternalBaselineError(
                "unsupported external case-verification schema"
            )
        errors = tuple(self.error_codes)
        if self.receptor_verified and self.ligand_verified:
            valid = not errors
        else:
            valid = bool(errors)
        if not valid:
            raise PublicExternalBaselineError(
                "prepared case verification status is inconsistent"
            )
        object.__setattr__(self, "error_codes", errors)

    @property
    def ready(self) -> bool:
        return self.receptor_verified and self.ligand_verified

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.preparation.case_id,
            "preparation": self.preparation.to_dict(),
            "preparation_sha256": self.preparation.fingerprint_sha256,
            "receptor_verified": self.receptor_verified,
            "ligand_verified": self.ligand_verified,
            "status": "prepared_inputs_verified" if self.ready else "failure",
            "error_codes": list(self.error_codes),
        }


def public_external_baseline_pocket_definition(
    case: PublicBenchmarkCaseDefinition,
    row: PublicBenchmarkSuiteCaseMaterialization,
) -> tuple[tuple[float, float, float], str]:
    """Derive the exact raw-receptor-frame redocking center and its digest."""

    if row.materialization is None or not row.ready_for_rmsd:
        raise PublicExternalBaselineError(
            "public suite case is not ready for a redocking pocket"
        )
    materialization = row.materialization
    first = min(materialization.reference_poses, key=lambda pose: pose.record_index)
    coordinates = first.reference_coordinates_seed_heavy_order
    center = tuple(
        float(value)
        for value in coordinates.mean(dim=0).to(dtype=coordinates.dtype).tolist()
    )
    center3 = _vector3(center, name="derived pocket center")
    projection = {
        "case_input_sha256": case.input_sha256,
        "materialization_sha256": materialization.fingerprint_sha256,
        "center_policy": (
            "centroid_of_lowest_record_index_graph_matched_native_reference"
        ),
        "center_binary64_hex": [value.hex() for value in center3],
        "coordinate_frame": "raw_receptor_input_frame",
    }
    return center3, _digest(projection)


def _verify_prepared_case(
    preparation: PublicExternalPreparedCase,
    *,
    artifact_root: Path,
) -> PublicExternalCaseVerification:
    receptor_verified = False
    ligand_verified = False
    errors: list[str] = []
    try:
        size, _ = _confined_file(
            artifact_root,
            preparation.receptor.relative_path,
            preparation.receptor.sha256,
        )
        if size != preparation.receptor.size_bytes:
            raise PublicExternalBaselineError("prepared receptor size mismatch")
        receptor_verified = True
    except (ExternalBaselineContractError, PublicExternalBaselineError):
        errors.append("prepared_receptor_artifact_verification_failed")
    try:
        size, _ = _confined_file(
            artifact_root,
            preparation.ligand.relative_path,
            preparation.ligand.sha256,
        )
        if size != preparation.ligand.size_bytes:
            raise PublicExternalBaselineError("prepared ligand size mismatch")
        ligand_verified = True
    except (ExternalBaselineContractError, PublicExternalBaselineError):
        errors.append("prepared_ligand_artifact_verification_failed")
    return PublicExternalCaseVerification(
        preparation=preparation,
        receptor_verified=receptor_verified,
        ligand_verified=ligand_verified,
        error_codes=tuple(errors),
    )


def _command_template(engine_id: str) -> tuple[str, ...]:
    command = (
        "{engine_executable}",
        "--receptor",
        "{receptor_path}",
        "--ligand",
        "{ligand_path}",
        "--center_x",
        "{center_x}",
        "--center_y",
        "{center_y}",
        "--center_z",
        "{center_z}",
        "--size_x",
        "{size_x}",
        "--size_y",
        "{size_y}",
        "--size_z",
        "{size_z}",
        "--seed",
        "{seed}",
        "--exhaustiveness",
        "{exhaustiveness}",
        "--num_modes",
        "{num_modes}",
        "--cpu",
        "{cpu_count}",
    )
    if engine_id in {"vina", "smina"}:
        command += (
            "--energy_range",
            "{energy_range_kcal_per_mol}",
        )
    if engine_id == "gnina":
        command += ("--no_gpu",)
    return command + ("--out", "{output_path}")


def _score_contract(engine_id: str) -> tuple[str, str, str]:
    if engine_id == "gnina":
        return "maximize", "dimensionless", "gnina_default_cnnscore"
    return "minimize", "kcal/mol", f"{engine_id}_native_affinity"


def _work_order_case_metadata(
    preparation: PublicExternalPreparedCase,
    *,
    engine_id: str,
) -> dict[str, Any]:
    return {
        "prepared_case_sha256": preparation.fingerprint_sha256,
        "prepared_receptor_path": preparation.receptor.relative_path,
        "prepared_ligand_path": preparation.ligand.relative_path,
        "pocket_center_receptor_frame_angstrom": list(
            preparation.pocket_center_receptor_frame_angstrom
        ),
        "pocket_definition_sha256": preparation.pocket_definition_sha256,
        "box_size_angstrom": list(preparation.box_size_angstrom),
        "seed": PUBLIC_EXTERNAL_BASELINE_SEED,
        "exhaustiveness": PUBLIC_EXTERNAL_BASELINE_EXHAUSTIVENESS,
        "num_modes": PUBLIC_EXTERNAL_BASELINE_NUM_MODES,
        "cpu_count": PUBLIC_EXTERNAL_BASELINE_CPU_COUNT,
        "energy_range_kcal_per_mol": (
            PUBLIC_EXTERNAL_BASELINE_ENERGY_RANGE_KCAL_PER_MOL
        ),
        "ligand_identity_seed_coordinates_used": False,
        "native_reference_used_for_box_center_only": True,
        "engine_score_field": "CNNscore" if engine_id == "gnina" else "affinity",
    }


@dataclass(frozen=True, slots=True)
class PublicExternalBaselineWorkOrderBundle:
    protocol_sha256: str
    suite_materialization_sha256: str
    case_rows: tuple[PublicExternalCaseVerification, ...]
    engines: tuple[ExternalBaselineEngine, ...]
    work_orders: tuple[ExternalBaselineWorkOrder, ...]
    schema_id: str = PUBLIC_EXTERNAL_BASELINE_WORK_ORDER_BUNDLE_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PUBLIC_EXTERNAL_BASELINE_WORK_ORDER_BUNDLE_SCHEMA_ID:
            raise PublicExternalBaselineError(
                "unsupported external work-order bundle schema"
            )
        _sha256(self.protocol_sha256, name="public protocol")
        _sha256(self.suite_materialization_sha256, name="suite materialization")
        rows = tuple(self.case_rows)
        engines = tuple(self.engines)
        work_orders = tuple(self.work_orders)
        if any(not isinstance(row, PublicExternalCaseVerification) for row in rows):
            raise PublicExternalBaselineError(
                "external bundle case rows have the wrong type"
            )
        if any(not isinstance(engine, ExternalBaselineEngine) for engine in engines):
            raise PublicExternalBaselineError(
                "external bundle engine rows have the wrong type"
            )
        if len(rows) != 4 or tuple(row.preparation.case_id for row in rows) != tuple(
            sorted({row.preparation.case_id for row in rows})
        ):
            raise PublicExternalBaselineError(
                "external bundle must retain four uniquely sorted case rows"
            )
        engine_ids = tuple(engine.engine_id for engine in engines)
        if engine_ids != tuple(sorted(SUPPORTED_EXTERNAL_ENGINES)):
            raise PublicExternalBaselineError(
                "external bundle requires exact Vina/GNINA/Smina identities"
            )
        ready = all(row.ready for row in rows)
        if ready:
            preparation_bundle_sha256 = _digest([row.to_dict() for row in rows])
            valid_work_orders = (
                len(work_orders) == 3
                and tuple(order.engine.engine_id for order in work_orders) == engine_ids
                and all(
                    tuple(case.case_id for case in order.cases)
                    == tuple(row.preparation.case_id for row in rows)
                    for order in work_orders
                )
            )
            target_vectors: list[tuple[str, ...]] = []
            if valid_work_orders:
                for engine, order in zip(engines, work_orders, strict=True):
                    score_direction, score_unit, score_semantics = _score_contract(
                        engine.engine_id
                    )
                    valid_work_orders = valid_work_orders and (
                        order.engine.fingerprint_sha256 == engine.fingerprint_sha256
                        and order.work_order_id
                        == (
                            "posebusters-contract-cohort-"
                            f"{engine.engine_id}-{preparation_bundle_sha256[:16]}"
                        )
                        and order.command_template == _command_template(engine.engine_id)
                        and order.score_direction == score_direction
                        and order.score_unit == score_unit
                        and order.score_semantics == score_semantics
                    )
                    target_vectors.append(tuple(case.target_id for case in order.cases))
                    for row, case in zip(rows, order.cases, strict=True):
                        valid_work_orders = valid_work_orders and (
                            case.case_id == row.preparation.case_id
                            and case.target_id == row.preparation.target_id
                            and case.ligand_id == row.preparation.case_id
                            and case.receptor_sha256
                            == row.preparation.receptor.sha256
                            and case.ligand_sha256 == row.preparation.ligand.sha256
                            and case.to_dict()["metadata"]
                            == _work_order_case_metadata(
                                row.preparation,
                                engine_id=engine.engine_id,
                            )
                        )
                valid_work_orders = valid_work_orders and len(set(target_vectors)) == 1
        else:
            valid_work_orders = not work_orders
        if not valid_work_orders:
            raise PublicExternalBaselineError(
                "external work orders disagree with prepared-input readiness"
            )
        object.__setattr__(self, "case_rows", rows)
        object.__setattr__(self, "engines", engines)
        object.__setattr__(self, "work_orders", work_orders)

    @property
    def prepared_input_ready(self) -> bool:
        return all(row.ready for row in self.case_rows)

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "protocol_sha256": self.protocol_sha256,
            "suite_materialization_sha256": self.suite_materialization_sha256,
            "case_rows": [row.to_dict() for row in self.case_rows],
            "engines": [engine.to_dict() for engine in self.engines],
            "work_orders": [order.to_dict() for order in self.work_orders],
            "case_count": len(self.case_rows),
            "engine_count": len(self.engines),
            "work_order_count": len(self.work_orders),
            "prepared_input_verified_case_count": sum(
                row.ready for row in self.case_rows
            ),
            "all_case_denominator_retained": True,
            "same_prepared_input_identity_across_engines": self.prepared_input_ready,
            "prepared_input_ready": self.prepared_input_ready,
            "status": (
                "ready_for_offline_operator_execution"
                if self.prepared_input_ready
                else "blocked_prepared_input_verification"
            ),
            "search_parameters": {
                "box_size_angstrom": list(
                    PUBLIC_EXTERNAL_BASELINE_BOX_SIZE_ANGSTROM
                ),
                "seed": PUBLIC_EXTERNAL_BASELINE_SEED,
                "exhaustiveness": PUBLIC_EXTERNAL_BASELINE_EXHAUSTIVENESS,
                "num_modes": PUBLIC_EXTERNAL_BASELINE_NUM_MODES,
                "cpu_count": PUBLIC_EXTERNAL_BASELINE_CPU_COUNT,
                "energy_range_kcal_per_mol": (
                    PUBLIC_EXTERNAL_BASELINE_ENERGY_RANGE_KCAL_PER_MOL
                ),
            },
            "scientific_blockers": list(PUBLIC_EXTERNAL_BASELINE_BLOCKERS),
            "external_engine_launched": False,
            "results_present": False,
            "benchmark_executed": False,
            "independent_rerun_complete": False,
            "scientifically_validated": False,
            "customer_execution_enabled": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _digest(self._payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self._payload(), "bundle_sha256": self.fingerprint_sha256}

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        output = Path(output_path)
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = _canonical_bytes(self.to_dict()) + b"\n"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.name}.", suffix=".tmp", dir=str(output.parent)
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_name, output, follow_symlinks=False)
            except FileExistsError as exc:
                raise PublicExternalBaselineError(
                    "external work-order bundle output already exists"
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


def build_public_external_baseline_work_order_bundle(
    protocol: FrozenPublicBenchmarkProtocol,
    suite_receipt: PublicBenchmarkSuiteMaterializationReceipt,
    prepared_cases: Sequence[PublicExternalPreparedCase],
    engines: Sequence[ExternalBaselineEngine],
    *,
    artifact_root: str | os.PathLike[str],
) -> PublicExternalBaselineWorkOrderBundle:
    """Verify four prepared inputs and create three exact non-executing orders."""

    if not isinstance(protocol, FrozenPublicBenchmarkProtocol):
        raise PublicExternalBaselineError("protocol has the wrong type")
    if not isinstance(suite_receipt, PublicBenchmarkSuiteMaterializationReceipt):
        raise PublicExternalBaselineError("suite receipt has the wrong type")
    try:
        suite_receipt.require_protocol(protocol)
    except (TypeError, ValueError) as exc:
        raise PublicExternalBaselineError(
            "suite receipt does not match the external baseline protocol"
        ) from exc
    preparations = tuple(prepared_cases)
    if tuple(item.case_id for item in preparations) != tuple(
        case.case_id for case in protocol.cases
    ):
        raise PublicExternalBaselineError(
            "prepared cases must exactly cover the ordered protocol cases"
        )
    engine_rows = tuple(sorted(tuple(engines), key=lambda item: item.engine_id))
    if tuple(engine.engine_id for engine in engine_rows) != tuple(
        sorted(SUPPORTED_EXTERNAL_ENGINES)
    ):
        raise PublicExternalBaselineError(
            "engine identities must exactly cover Vina, GNINA, and Smina"
        )
    suite_rows = {row.case_id: row for row in suite_receipt.case_rows}
    protocol_cases = {case.case_id: case for case in protocol.cases}
    for preparation in preparations:
        case = protocol_cases[preparation.case_id]
        row = suite_rows[preparation.case_id]
        center, pocket_sha256 = public_external_baseline_pocket_definition(case, row)
        if (
            preparation.target_id != case.pdb_id
            or preparation.receptor.source_artifact_sha256 != case.receptor.sha256
            or preparation.ligand.source_artifact_sha256
            != case.ligand_identity_seed.sha256
            or preparation.pocket_center_receptor_frame_angstrom != center
            or preparation.pocket_definition_sha256 != pocket_sha256
        ):
            raise PublicExternalBaselineError(
                "prepared case source or pocket identity is cross-wired"
            )
    verification_rows = tuple(
        _verify_prepared_case(item, artifact_root=Path(artifact_root))
        for item in preparations
    )
    work_orders: list[ExternalBaselineWorkOrder] = []
    if all(row.ready for row in verification_rows):
        preparation_bundle_sha256 = _digest(
            [row.to_dict() for row in verification_rows]
        )
        for engine in engine_rows:
            score_direction, score_unit, score_semantics = _score_contract(
                engine.engine_id
            )
            cases = tuple(
                ExternalBaselineCase(
                    case_id=row.preparation.case_id,
                    target_id=row.preparation.target_id,
                    ligand_id=row.preparation.case_id,
                    receptor_sha256=row.preparation.receptor.sha256,
                    ligand_sha256=row.preparation.ligand.sha256,
                    metadata=_work_order_case_metadata(
                        row.preparation,
                        engine_id=engine.engine_id,
                    ),
                )
                for row in verification_rows
            )
            work_orders.append(
                ExternalBaselineWorkOrder(
                    work_order_id=(
                        "posebusters-contract-cohort-"
                        f"{engine.engine_id}-{preparation_bundle_sha256[:16]}"
                    ),
                    engine=engine,
                    cases=cases,
                    command_template=_command_template(engine.engine_id),
                    score_direction=score_direction,
                    score_unit=score_unit,
                    score_semantics=score_semantics,
                )
            )
    return PublicExternalBaselineWorkOrderBundle(
        protocol_sha256=protocol.protocol_sha256,
        suite_materialization_sha256=suite_receipt.fingerprint_sha256,
        case_rows=verification_rows,
        engines=engine_rows,
        work_orders=tuple(work_orders),
    )


__all__ = [
    "PUBLIC_EXTERNAL_BASELINE_BLOCKERS",
    "PUBLIC_EXTERNAL_BASELINE_BOX_SIZE_ANGSTROM",
    "PUBLIC_EXTERNAL_BASELINE_CASE_VERIFICATION_SCHEMA_ID",
    "PUBLIC_EXTERNAL_BASELINE_CPU_COUNT",
    "PUBLIC_EXTERNAL_BASELINE_ENERGY_RANGE_KCAL_PER_MOL",
    "PUBLIC_EXTERNAL_BASELINE_EXHAUSTIVENESS",
    "PUBLIC_EXTERNAL_BASELINE_NUM_MODES",
    "PUBLIC_EXTERNAL_BASELINE_PREPARATION_TOOL_SCHEMA_ID",
    "PUBLIC_EXTERNAL_BASELINE_PREPARED_ARTIFACT_SCHEMA_ID",
    "PUBLIC_EXTERNAL_BASELINE_PREPARED_CASE_SCHEMA_ID",
    "PUBLIC_EXTERNAL_BASELINE_SEED",
    "PUBLIC_EXTERNAL_BASELINE_WORK_ORDER_BUNDLE_SCHEMA_ID",
    "PublicExternalBaselineError",
    "PublicExternalBaselineWorkOrderBundle",
    "PublicExternalCaseVerification",
    "PublicExternalPreparationTool",
    "PublicExternalPreparedArtifact",
    "PublicExternalPreparedCase",
    "build_public_external_baseline_work_order_bundle",
    "public_external_baseline_pocket_definition",
]
