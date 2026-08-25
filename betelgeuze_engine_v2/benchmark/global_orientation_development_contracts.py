"""Failure-complete evidence contracts for global-orientation development.

These types seal already-observed, private development evidence.  They do not
load molecular inputs, run a proposal generator or scorer, evaluate a protocol
decision, or grant execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from typing import Iterable, Sequence

from .source_paired_clearance_activation import (
    SourcePairedClearanceCandidateEvidenceV1,
)


GLOBAL_ORIENTATION_DEVELOPMENT_CASE_SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_development_case_source/1.0.0"
)
GLOBAL_ORIENTATION_DEVELOPMENT_PREPARATION_FAILURE_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_development_preparation_failure/1.0.0"
)
GLOBAL_ORIENTATION_DEVELOPMENT_LINEAGE_SLOT_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_development_lineage_slot/1.0.0"
)
GLOBAL_ORIENTATION_DEVELOPMENT_ARM_LINEAGE_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_development_arm_lineage/1.0.0"
)
GLOBAL_ORIENTATION_DEVELOPMENT_OBSERVATION_SLOT_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_development_observation_slot/1.0.0"
)
GLOBAL_ORIENTATION_DEVELOPMENT_ARM_OBSERVATIONS_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_development_arm_observations/1.0.0"
)
GLOBAL_ORIENTATION_DEVELOPMENT_RUNTIME_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_generator_runtime/1.0.0"
)
GLOBAL_ORIENTATION_DEVELOPMENT_COORDINATES_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_source_coordinates/1.0.0"
)
POSE_VALIDITY_CONFIG_SCHEMA_ID = "betelgeuze.engine_v2_pose_validity_config/3.0.0"
PUBLIC_REDOCKING_POSE_VALIDITY_POLICY_ID = (
    "betelgeuze.engine_v2_pose_validity_policy/public-redocking/1.0.0"
)
GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR = 64
GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS = (
    "5SD5_HWI",
    "5SIS_JSM",
    "6M2B_EZO",
    "6T88_MWQ",
    "6TW5_9M2",
    "6TW7_NZB",
    "6VTA_AKN",
    "6WTN_RXT",
)
GLOBAL_ORIENTATION_DEVELOPMENT_PREPARATION_FAILURE_CASE_ID = "6M73_FNR"
GLOBAL_ORIENTATION_DEVELOPMENT_ARM_IDS = (
    "baseline_current_v7",
    "experimental_global_orientation_v1",
)
MAX_SOURCE_ATOMS = 1_000_000
_DIGEST_RE = re.compile(r"[0-9a-f]{64}")

Vector3 = tuple[float, float, float]
Coordinates = tuple[Vector3, ...]


class GlobalOrientationDevelopmentContractError(ValueError):
    """Raised when development evidence is incomplete or cross-wired."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise GlobalOrientationDevelopmentContractError(
            "development evidence is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise GlobalOrientationDevelopmentContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return value


def _optional_digest(value: object, *, name: str) -> str | None:
    return None if value is None else _digest(value, name=name)


def _text(value: object, *, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GlobalOrientationDevelopmentContractError(
            f"{name} must be non-empty text"
        )
    return value.strip()


def _finite(value: object, *, name: str, minimum: float | None = None) -> float:
    if type(value) not in {int, float}:
        raise GlobalOrientationDevelopmentContractError(
            f"{name} must be a finite number"
        )
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise GlobalOrientationDevelopmentContractError(f"{name} is invalid")
    return result


def _vector(value: Sequence[float], *, name: str) -> Vector3:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise GlobalOrientationDevelopmentContractError(
            f"{name} must be a three-value sequence"
        )
    if len(value) != 3:
        raise GlobalOrientationDevelopmentContractError(
            f"{name} must contain exactly three values"
        )
    result = tuple(
        _finite(component, name=f"{name}[{index}]")
        for index, component in enumerate(value)
    )
    return result  # type: ignore[return-value]


def _coordinates(value: Iterable[Sequence[float]], *, name: str) -> Coordinates:
    if isinstance(value, (str, bytes)):
        raise GlobalOrientationDevelopmentContractError(
            f"{name} must be a coordinate sequence"
        )
    result = tuple(
        _vector(point, name=f"{name}[{index}]") for index, point in enumerate(value)
    )
    if not result or len(result) > MAX_SOURCE_ATOMS:
        raise GlobalOrientationDevelopmentContractError(
            f"{name} has an invalid bounded atom count"
        )
    return result


def _coordinates_projection(value: Coordinates) -> list[list[str]]:
    return [[component.hex() for component in point] for point in value]


def derive_global_orientation_source_coordinates_sha256(
    coordinates: Iterable[Sequence[float]],
) -> str:
    """Derive a canonical identity without importing a molecular runtime."""

    rows = _coordinates(coordinates, name="coordinates")
    return _sha256(
        {
            "schema_id": GLOBAL_ORIENTATION_DEVELOPMENT_COORDINATES_SCHEMA_ID,
            "coordinates_binary64_hex": _coordinates_projection(rows),
        }
    )


def derive_global_orientation_pose_validity_config_fingerprint(
    pocket_radius_angstrom: float,
) -> str:
    """Rederive the exact public-redocking validity config identity."""

    radius = _finite(
        pocket_radius_angstrom,
        name="pocket_radius_angstrom",
        minimum=0.0,
    )
    if radius == 0.0:
        raise GlobalOrientationDevelopmentContractError(
            "pocket_radius_angstrom must be positive"
        )
    return _sha256(
        {
            "schema_id": POSE_VALIDITY_CONFIG_SCHEMA_ID,
            "policy_id": PUBLIC_REDOCKING_POSE_VALIDITY_POLICY_ID,
            "bond_length_tolerance_angstrom": 0.15,
            "ligand_self_clash_angstrom": 0.75,
            "receptor_ligand_clash_angstrom": 0.8,
            "rotation_tolerance": 1.0e-6,
            "chirality_volume_tolerance": 1.0e-8,
            "pocket_radius_angstrom": radius,
            "max_pair_checks": 250_000,
            "max_cross_checks": 1_000_000,
        }
    )


def derive_global_orientation_generator_runtime_fingerprint(
    *,
    python_executable_sha256: str,
    python_shared_library_sha256: str,
    libm_sha256: str,
) -> str:
    """Bind the three executable payloads used by Python binary64 generation."""

    return _sha256(
        {
            "schema_id": GLOBAL_ORIENTATION_DEVELOPMENT_RUNTIME_SCHEMA_ID,
            "python_executable_sha256": _digest(
                python_executable_sha256,
                name="python_executable_sha256",
            ),
            "python_shared_library_sha256": _digest(
                python_shared_library_sha256,
                name="python_shared_library_sha256",
            ),
            "libm_sha256": _digest(libm_sha256, name="libm_sha256"),
        }
    )


def _authority_projection() -> dict[str, bool]:
    return {
        "historical_development_execution_authorized": False,
        "fresh_holdout_execution_authorized": False,
        "stage0_admission_authority": False,
        "profile_promotion_authority": False,
        "product_execution_authorized": False,
        "customer_pose_emission_authorized": False,
        "public_or_scientific_claim_authorized": False,
    }


@dataclass(frozen=True, slots=True)
class GlobalOrientationDevelopmentCaseSourceReceiptV1:
    """Prepared-case source identity with rederived surface and runtime bindings."""

    case_id: str
    source_case_member_receipt_sha256: str
    authenticated_input_receipt_sha256: str
    receptor_coordinates: Coordinates
    receptor_coordinate_sha256: str
    ligand_coordinates: Coordinates
    ligand_coordinate_sha256: str
    ligand_topology_sha256: str
    pocket_declaration_sha256: str
    pocket_center: Vector3
    pocket_normal: Vector3
    pocket_radius_angstrom: float
    pose_validity_config_fingerprint_sha256: str
    preparation_policy_sha256: str
    evaluation_pipeline_sha256: str
    scorer_native_extension_sha256: str
    scorer_backend_receipt_sha256: str
    generator_python_executable_sha256: str
    generator_python_shared_library_sha256: str
    generator_libm_sha256: str
    generator_runtime_fingerprint_sha256: str
    receptor_surface_atom_indices: tuple[int, ...]
    surface_extraction_procedure_id: str = (
        "authenticated_receptor_coordinate_index_projection_v1"
    )
    schema_id: str = GLOBAL_ORIENTATION_DEVELOPMENT_CASE_SOURCE_SCHEMA_ID
    _receptor_surface_points: Coordinates = field(init=False, repr=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != GLOBAL_ORIENTATION_DEVELOPMENT_CASE_SOURCE_SCHEMA_ID:
            raise GlobalOrientationDevelopmentContractError(
                "case-source schema_id is invalid"
            )
        if self.case_id not in GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS:
            raise GlobalOrientationDevelopmentContractError(
                "case source is outside the frozen scored cohort"
            )
        receptor = _coordinates(
            self.receptor_coordinates,
            name="receptor_coordinates",
        )
        ligand = _coordinates(self.ligand_coordinates, name="ligand_coordinates")
        object.__setattr__(self, "receptor_coordinates", receptor)
        object.__setattr__(self, "ligand_coordinates", ligand)
        if derive_global_orientation_source_coordinates_sha256(receptor) != _digest(
            self.receptor_coordinate_sha256,
            name="receptor_coordinate_sha256",
        ) or derive_global_orientation_source_coordinates_sha256(ligand) != _digest(
            self.ligand_coordinate_sha256,
            name="ligand_coordinate_sha256",
        ):
            raise GlobalOrientationDevelopmentContractError(
                "source coordinate identity does not rederive"
            )
        for name in (
            "source_case_member_receipt_sha256",
            "authenticated_input_receipt_sha256",
            "ligand_topology_sha256",
            "pocket_declaration_sha256",
            "preparation_policy_sha256",
            "evaluation_pipeline_sha256",
            "scorer_native_extension_sha256",
            "scorer_backend_receipt_sha256",
            "generator_python_executable_sha256",
            "generator_python_shared_library_sha256",
            "generator_libm_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        center = _vector(self.pocket_center, name="pocket_center")
        normal = _vector(self.pocket_normal, name="pocket_normal")
        if math.sqrt(sum(component * component for component in normal)) == 0.0:
            raise GlobalOrientationDevelopmentContractError(
                "pocket_normal must be non-zero"
            )
        object.__setattr__(self, "pocket_center", center)
        object.__setattr__(self, "pocket_normal", normal)
        radius = _finite(
            self.pocket_radius_angstrom,
            name="pocket_radius_angstrom",
            minimum=0.0,
        )
        if radius == 0.0:
            raise GlobalOrientationDevelopmentContractError(
                "pocket_radius_angstrom must be positive"
            )
        object.__setattr__(self, "pocket_radius_angstrom", radius)
        expected_validity = derive_global_orientation_pose_validity_config_fingerprint(
            radius
        )
        if (
            _digest(
                self.pose_validity_config_fingerprint_sha256,
                name="pose_validity_config_fingerprint_sha256",
            )
            != expected_validity
        ):
            raise GlobalOrientationDevelopmentContractError(
                "pose-validity config identity does not rederive from pocket radius"
            )
        expected_runtime = derive_global_orientation_generator_runtime_fingerprint(
            python_executable_sha256=self.generator_python_executable_sha256,
            python_shared_library_sha256=(self.generator_python_shared_library_sha256),
            libm_sha256=self.generator_libm_sha256,
        )
        if (
            _digest(
                self.generator_runtime_fingerprint_sha256,
                name="generator_runtime_fingerprint_sha256",
            )
            != expected_runtime
        ):
            raise GlobalOrientationDevelopmentContractError(
                "generator runtime identity does not rederive"
            )
        if (
            self.surface_extraction_procedure_id
            != "authenticated_receptor_coordinate_index_projection_v1"
        ):
            raise GlobalOrientationDevelopmentContractError(
                "surface extraction procedure is not frozen"
            )
        indices = tuple(self.receptor_surface_atom_indices)
        if (
            not indices
            or any(type(value) is not int for value in indices)
            or tuple(sorted(set(indices))) != indices
            or indices[-1] >= len(receptor)
            or indices[0] < 0
        ):
            raise GlobalOrientationDevelopmentContractError(
                "receptor surface indices are invalid or non-canonical"
            )
        surface = tuple(receptor[index] for index in indices)
        object.__setattr__(self, "receptor_surface_atom_indices", indices)
        object.__setattr__(self, "_receptor_surface_points", surface)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def receptor_surface_points(self) -> Coordinates:
        return tuple(self._receptor_surface_points)

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "source_case_member_receipt_sha256": (
                self.source_case_member_receipt_sha256
            ),
            "authenticated_input_receipt_sha256": (
                self.authenticated_input_receipt_sha256
            ),
            "receptor_coordinates_binary64_hex": _coordinates_projection(
                self.receptor_coordinates
            ),
            "receptor_coordinate_sha256": self.receptor_coordinate_sha256,
            "ligand_coordinates_binary64_hex": _coordinates_projection(
                self.ligand_coordinates
            ),
            "ligand_coordinate_sha256": self.ligand_coordinate_sha256,
            "ligand_topology_sha256": self.ligand_topology_sha256,
            "pocket_declaration_sha256": self.pocket_declaration_sha256,
            "pocket_center_binary64_hex": [value.hex() for value in self.pocket_center],
            "pocket_normal_binary64_hex": [value.hex() for value in self.pocket_normal],
            "pocket_radius_angstrom_binary64_hex": self.pocket_radius_angstrom.hex(),
            "pose_validity_config_fingerprint_sha256": (
                self.pose_validity_config_fingerprint_sha256
            ),
            "preparation_policy_sha256": self.preparation_policy_sha256,
            "evaluation_pipeline_sha256": self.evaluation_pipeline_sha256,
            "scorer_native_extension_sha256": self.scorer_native_extension_sha256,
            "scorer_backend_receipt_sha256": self.scorer_backend_receipt_sha256,
            "generator_python_executable_sha256": (
                self.generator_python_executable_sha256
            ),
            "generator_python_shared_library_sha256": (
                self.generator_python_shared_library_sha256
            ),
            "generator_libm_sha256": self.generator_libm_sha256,
            "generator_runtime_fingerprint_sha256": (
                self.generator_runtime_fingerprint_sha256
            ),
            "surface_extraction_procedure_id": self.surface_extraction_procedure_id,
            "receptor_surface_atom_indices": list(self.receptor_surface_atom_indices),
            "receptor_surface_points_binary64_hex": _coordinates_projection(
                self._receptor_surface_points
            ),
            "receptor_surface_points_rederived": True,
            **_authority_projection(),
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationDevelopmentContractError(
                "case-source receipt changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class GlobalOrientationDevelopmentPreparationFailureReceiptV1:
    """Retain the ninth cohort member as a typed preparation failure."""

    case_id: str
    source_case_member_receipt_sha256: str
    authenticated_input_receipt_sha256: str
    preparation_policy_sha256: str
    failure_code: str
    schema_id: str = GLOBAL_ORIENTATION_DEVELOPMENT_PREPARATION_FAILURE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if (
            self.schema_id
            != GLOBAL_ORIENTATION_DEVELOPMENT_PREPARATION_FAILURE_SCHEMA_ID
            or self.case_id
            != GLOBAL_ORIENTATION_DEVELOPMENT_PREPARATION_FAILURE_CASE_ID
        ):
            raise GlobalOrientationDevelopmentContractError(
                "preparation-failure row is outside the frozen cohort"
            )
        for name in (
            "source_case_member_receipt_sha256",
            "authenticated_input_receipt_sha256",
            "preparation_policy_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        object.__setattr__(
            self, "failure_code", _text(self.failure_code, name="failure_code")
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "source_case_member_receipt_sha256": (
                self.source_case_member_receipt_sha256
            ),
            "authenticated_input_receipt_sha256": (
                self.authenticated_input_receipt_sha256
            ),
            "preparation_policy_sha256": self.preparation_policy_sha256,
            "preparation_status": "failed",
            "failure_code": self.failure_code,
            "candidate_denominator": 0,
            **_authority_projection(),
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationDevelopmentContractError(
                "preparation-failure receipt changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class GlobalOrientationDevelopmentLineageSlotV1:
    case_source_receipt_sha256: str
    arm_id: str
    proposal_index: int
    candidate_id: str
    generation_status: str
    proposal_fingerprint_sha256: str | None
    coordinate_sha256: str | None
    generation_receipt_sha256: str | None
    failure_code: str | None
    schema_id: str = GLOBAL_ORIENTATION_DEVELOPMENT_LINEAGE_SLOT_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != GLOBAL_ORIENTATION_DEVELOPMENT_LINEAGE_SLOT_SCHEMA_ID:
            raise GlobalOrientationDevelopmentContractError(
                "lineage-slot schema_id is invalid"
            )
        object.__setattr__(
            self,
            "case_source_receipt_sha256",
            _digest(
                self.case_source_receipt_sha256,
                name="case_source_receipt_sha256",
            ),
        )
        if self.arm_id not in GLOBAL_ORIENTATION_DEVELOPMENT_ARM_IDS:
            raise GlobalOrientationDevelopmentContractError("arm_id is invalid")
        if (
            type(self.proposal_index) is not int
            or not 0
            <= self.proposal_index
            < GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR
        ):
            raise GlobalOrientationDevelopmentContractError(
                "proposal_index is outside the fixed denominator"
            )
        object.__setattr__(
            self, "candidate_id", _text(self.candidate_id, name="candidate_id")
        )
        if self.generation_status not in {"generated", "failed"}:
            raise GlobalOrientationDevelopmentContractError(
                "generation_status is invalid"
            )
        for name in (
            "proposal_fingerprint_sha256",
            "coordinate_sha256",
            "generation_receipt_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _optional_digest(getattr(self, name), name=name),
            )
        failure = (
            None
            if self.failure_code is None
            else _text(
                self.failure_code,
                name="failure_code",
            )
        )
        object.__setattr__(self, "failure_code", failure)
        generated_values = (
            self.proposal_fingerprint_sha256,
            self.coordinate_sha256,
            self.generation_receipt_sha256,
        )
        if self.generation_status == "generated":
            if any(value is None for value in generated_values) or failure is not None:
                raise GlobalOrientationDevelopmentContractError(
                    "generated lineage must retain all identities and no failure"
                )
        elif any(value is not None for value in generated_values) or failure is None:
            raise GlobalOrientationDevelopmentContractError(
                "failed lineage must retain only its typed failure"
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_source_receipt_sha256": self.case_source_receipt_sha256,
            "arm_id": self.arm_id,
            "proposal_index": self.proposal_index,
            "candidate_id": self.candidate_id,
            "generation_status": self.generation_status,
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "coordinate_sha256": self.coordinate_sha256,
            "generation_receipt_sha256": self.generation_receipt_sha256,
            "failure_code": self.failure_code,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationDevelopmentContractError("lineage slot changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class GlobalOrientationDevelopmentArmLineageReceiptV1:
    case_source: GlobalOrientationDevelopmentCaseSourceReceiptV1
    arm_id: str
    arm_authority_sha256: str
    slots: tuple[GlobalOrientationDevelopmentLineageSlotV1, ...]
    schema_id: str = GLOBAL_ORIENTATION_DEVELOPMENT_ARM_LINEAGE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != GLOBAL_ORIENTATION_DEVELOPMENT_ARM_LINEAGE_SCHEMA_ID:
            raise GlobalOrientationDevelopmentContractError(
                "arm-lineage schema_id is invalid"
            )
        if (
            type(self.case_source)
            is not GlobalOrientationDevelopmentCaseSourceReceiptV1
        ):
            raise TypeError("case_source must be an exact prepared-case source receipt")
        case_source = self.case_source.receipt_sha256
        arm_authority = _digest(
            self.arm_authority_sha256,
            name="arm_authority_sha256",
        )
        object.__setattr__(self, "arm_authority_sha256", arm_authority)
        if self.arm_id not in GLOBAL_ORIENTATION_DEVELOPMENT_ARM_IDS:
            raise GlobalOrientationDevelopmentContractError("arm_id is invalid")
        slots = tuple(self.slots)
        if (
            len(slots) != GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR
            or any(
                type(slot) is not GlobalOrientationDevelopmentLineageSlotV1
                for slot in slots
            )
            or tuple(slot.proposal_index for slot in slots)
            != tuple(range(GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR))
            or len({slot.candidate_id for slot in slots}) != len(slots)
            or any(
                slot.case_source_receipt_sha256 != case_source
                or slot.arm_id != self.arm_id
                for slot in slots
            )
        ):
            raise GlobalOrientationDevelopmentContractError(
                "arm lineage is not an exact ordered 64-slot binding"
            )
        object.__setattr__(self, "slots", slots)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_source.case_id,
            "case_source": self.case_source.to_dict(),
            "case_source_receipt_sha256": self.case_source.receipt_sha256,
            "arm_id": self.arm_id,
            "arm_authority_sha256": self.arm_authority_sha256,
            "candidate_denominator": len(self.slots),
            "slots": [slot.to_dict() for slot in self.slots],
            "failure_complete_generation_denominator": True,
            **_authority_projection(),
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationDevelopmentContractError(
                "arm-lineage receipt changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class GlobalOrientationDevelopmentObservationSlotV1:
    lineage_slot_receipt_sha256: str
    case_source_receipt_sha256: str
    arm_id: str
    proposal_index: int
    candidate_id: str
    generation_status: str
    proposal_fingerprint_sha256: str | None
    coordinate_sha256: str | None
    score_status: str
    validity_status: str
    rmsd_status: str
    candidate_evidence: SourcePairedClearanceCandidateEvidenceV1 | None
    failure_code: str | None
    schema_id: str = GLOBAL_ORIENTATION_DEVELOPMENT_OBSERVATION_SLOT_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != GLOBAL_ORIENTATION_DEVELOPMENT_OBSERVATION_SLOT_SCHEMA_ID:
            raise GlobalOrientationDevelopmentContractError(
                "observation-slot schema_id is invalid"
            )
        for name in (
            "lineage_slot_receipt_sha256",
            "case_source_receipt_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        if self.arm_id not in GLOBAL_ORIENTATION_DEVELOPMENT_ARM_IDS:
            raise GlobalOrientationDevelopmentContractError("arm_id is invalid")
        if (
            type(self.proposal_index) is not int
            or not 0
            <= self.proposal_index
            < GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR
        ):
            raise GlobalOrientationDevelopmentContractError(
                "proposal_index is outside the fixed denominator"
            )
        object.__setattr__(
            self, "candidate_id", _text(self.candidate_id, name="candidate_id")
        )
        if self.generation_status not in {"generated", "failed"}:
            raise GlobalOrientationDevelopmentContractError(
                "generation_status is invalid"
            )
        for name in (
            "proposal_fingerprint_sha256",
            "coordinate_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _optional_digest(getattr(self, name), name=name),
            )
        if self.score_status not in {"scored", "unscored"}:
            raise GlobalOrientationDevelopmentContractError("score_status is invalid")
        if self.validity_status not in {"evaluated", "not_evaluated"}:
            raise GlobalOrientationDevelopmentContractError(
                "validity_status is invalid"
            )
        if self.rmsd_status not in {"evaluated", "not_evaluated"}:
            raise GlobalOrientationDevelopmentContractError("rmsd_status is invalid")
        failure = (
            None
            if self.failure_code is None
            else _text(
                self.failure_code,
                name="failure_code",
            )
        )
        object.__setattr__(self, "failure_code", failure)
        evidence = self.candidate_evidence
        if (
            evidence is not None
            and type(evidence) is not SourcePairedClearanceCandidateEvidenceV1
        ):
            raise TypeError(
                "candidate_evidence must be exact full source-paired candidate evidence"
            )
        complete_success = evidence is not None
        if self.generation_status == "failed":
            if (
                self.proposal_fingerprint_sha256 is not None
                or self.coordinate_sha256 is not None
            ):
                raise GlobalOrientationDevelopmentContractError(
                    "failed generation observation carries downstream evidence"
                )
        elif self.proposal_fingerprint_sha256 is None or self.coordinate_sha256 is None:
            raise GlobalOrientationDevelopmentContractError(
                "generated observation lacks proposal or coordinate identity"
            )
        if complete_success:
            assert evidence is not None
            if (
                self.generation_status != "generated"
                or self.score_status != "scored"
                or self.validity_status != "evaluated"
                or self.rmsd_status != "evaluated"
                or evidence.proposal_index != self.proposal_index
                or evidence.candidate_id != self.candidate_id
                or evidence.candidate_proposal_fingerprint_sha256
                != self.proposal_fingerprint_sha256
                or evidence.coordinate_sha256 != self.coordinate_sha256
            ):
                raise GlobalOrientationDevelopmentContractError(
                    "full candidate evidence is cross-wired or incomplete"
                )
            evidence.receipt_sha256
        elif (
            self.score_status != "unscored"
            or self.validity_status != "not_evaluated"
            or self.rmsd_status != "not_evaluated"
        ):
            raise GlobalOrientationDevelopmentContractError(
                "missing candidate evidence must remain explicitly unscored"
            )
        if (complete_success and failure is not None) or (
            not complete_success and failure is None
        ):
            raise GlobalOrientationDevelopmentContractError(
                "observation success/failure state is contradictory"
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "lineage_slot_receipt_sha256": self.lineage_slot_receipt_sha256,
            "case_source_receipt_sha256": self.case_source_receipt_sha256,
            "arm_id": self.arm_id,
            "proposal_index": self.proposal_index,
            "candidate_id": self.candidate_id,
            "generation_status": self.generation_status,
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "coordinate_sha256": self.coordinate_sha256,
            "score_status": self.score_status,
            "validity_status": self.validity_status,
            "rmsd_status": self.rmsd_status,
            "candidate_evidence": (
                None
                if self.candidate_evidence is None
                else self.candidate_evidence.to_dict()
            ),
            "score_binary64_hex": (
                None
                if self.candidate_evidence is None
                else self.candidate_evidence.scorer_terms.total_score.hex()
            ),
            "internal_valid": (
                None
                if self.candidate_evidence is None
                else self.candidate_evidence.internal_validity.valid
            ),
            "posebusters_valid": (
                None
                if self.candidate_evidence is None
                else self.candidate_evidence.posebusters.valid
            ),
            "rmsd_angstrom_binary64_hex": (
                None
                if self.candidate_evidence is None
                else self.candidate_evidence.rmsd.rmsd_angstrom.hex()
            ),
            "failure_code": self.failure_code,
            "explicit_unscored_state": self.score_status == "unscored",
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationDevelopmentContractError("observation slot changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class GlobalOrientationDevelopmentArmObservationsV1:
    lineage: GlobalOrientationDevelopmentArmLineageReceiptV1
    observations: tuple[GlobalOrientationDevelopmentObservationSlotV1, ...]
    schema_id: str = GLOBAL_ORIENTATION_DEVELOPMENT_ARM_OBSERVATIONS_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if (
            self.schema_id != GLOBAL_ORIENTATION_DEVELOPMENT_ARM_OBSERVATIONS_SCHEMA_ID
            or type(self.lineage) is not GlobalOrientationDevelopmentArmLineageReceiptV1
        ):
            raise GlobalOrientationDevelopmentContractError(
                "arm-observations schema or lineage type is invalid"
            )
        observations = tuple(self.observations)
        if len(
            observations
        ) != GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR or any(
            type(value) is not GlobalOrientationDevelopmentObservationSlotV1
            for value in observations
        ):
            raise GlobalOrientationDevelopmentContractError(
                "observations do not retain the exact 64-slot denominator"
            )
        for lineage_slot, observation in zip(
            self.lineage.slots,
            observations,
            strict=True,
        ):
            if (
                observation.lineage_slot_receipt_sha256 != lineage_slot.receipt_sha256
                or observation.case_source_receipt_sha256
                != lineage_slot.case_source_receipt_sha256
                or observation.arm_id != lineage_slot.arm_id
                or observation.proposal_index != lineage_slot.proposal_index
                or observation.candidate_id != lineage_slot.candidate_id
                or observation.generation_status != lineage_slot.generation_status
                or observation.proposal_fingerprint_sha256
                != lineage_slot.proposal_fingerprint_sha256
                or observation.coordinate_sha256 != lineage_slot.coordinate_sha256
                or (
                    lineage_slot.generation_status == "failed"
                    and observation.failure_code != lineage_slot.failure_code
                )
            ):
                raise GlobalOrientationDevelopmentContractError(
                    "observation is cross-wired to another lineage slot"
                )
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "lineage_receipt_sha256": self.lineage.receipt_sha256,
            "lineage": self.lineage.to_dict(),
            "case_id": self.lineage.case_source.case_id,
            "case_source_receipt_sha256": (self.lineage.case_source.receipt_sha256),
            "arm_id": self.lineage.arm_id,
            "candidate_denominator": len(self.observations),
            "generated_candidate_count": sum(
                value.generation_status == "generated" for value in self.observations
            ),
            "scored_candidate_count": sum(
                value.score_status == "scored" for value in self.observations
            ),
            "unscored_candidate_count": sum(
                value.score_status == "unscored" for value in self.observations
            ),
            "observations": [value.to_dict() for value in self.observations],
            "lineage_bound_to_every_observation": True,
            "failure_complete_observation_denominator": True,
            "decision_evaluator_implemented": False,
            "go_receipt_emission_authorized": False,
            **_authority_projection(),
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationDevelopmentContractError(
                "arm-observations receipt changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


__all__ = [
    "GLOBAL_ORIENTATION_DEVELOPMENT_ARM_IDS",
    "GLOBAL_ORIENTATION_DEVELOPMENT_CANDIDATE_DENOMINATOR",
    "GLOBAL_ORIENTATION_DEVELOPMENT_PREPARATION_FAILURE_CASE_ID",
    "GLOBAL_ORIENTATION_DEVELOPMENT_SCORED_CASE_IDS",
    "GlobalOrientationDevelopmentArmLineageReceiptV1",
    "GlobalOrientationDevelopmentArmObservationsV1",
    "GlobalOrientationDevelopmentCaseSourceReceiptV1",
    "GlobalOrientationDevelopmentContractError",
    "GlobalOrientationDevelopmentLineageSlotV1",
    "GlobalOrientationDevelopmentObservationSlotV1",
    "GlobalOrientationDevelopmentPreparationFailureReceiptV1",
    "derive_global_orientation_generator_runtime_fingerprint",
    "derive_global_orientation_pose_validity_config_fingerprint",
    "derive_global_orientation_source_coordinates_sha256",
]
