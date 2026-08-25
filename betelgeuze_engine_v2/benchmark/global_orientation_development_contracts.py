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
    SourcePairedClearanceCaseSourceReceiptV1,
    SourcePairedClearanceCandidateEvidenceV1,
    SourcePairedClearanceCurrentV7LineageReceiptV1,
    SourcePairedClearanceInternalValidityEvidenceV1,
    SourcePairedClearancePoseBustersEvidenceV1,
    SourcePairedClearanceRmsdEvidenceV1,
)
from betelgeuze_engine_v2 import AllAtomSystem
from betelgeuze_engine_v2.docking import (
    AuthenticatedDockingProblem,
    ScorerV1Context,
    ScorerV1Terms,
)
from betelgeuze_engine_v2.docking.global_orientation import GlobalOrientationBatch
from betelgeuze_engine_v2.molecular import (
    canonical_system_sha256,
    canonical_topology_sha256,
)


GLOBAL_ORIENTATION_DEVELOPMENT_CASE_SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_development_case_source/1.0.0"
)
GLOBAL_ORIENTATION_DEVELOPMENT_PREPARATION_FAILURE_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_development_preparation_failure/1.0.0"
)
GLOBAL_ORIENTATION_DEVELOPMENT_HISTORICAL_FAILURE_AUTHORITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_historical_failure_authority/1.0.0"
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
GLOBAL_ORIENTATION_DEVELOPMENT_PARTIAL_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_development_partial_evidence/1.0.0"
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
GLOBAL_ORIENTATION_HISTORICAL_ARCHIVE_SHA256 = (
    "8bef33eba296989b795a11fd05a7e119124b066d91bec28a8b910d38a083fbcc"
)
GLOBAL_ORIENTATION_HISTORICAL_MEMBER_MANIFEST_SHA256 = (
    "7f7f5273362a9457b022bc9b2b95c75625cdd259b1b1685aeb4b57d41d985e21"
)
GLOBAL_ORIENTATION_HISTORICAL_BUNDLE_CHECKSUM_SHA256 = (
    "6ee04e23e01a73bb643bb4d1fde240e06fd2916ea085e3652c11e2428bd432a9"
)
GLOBAL_ORIENTATION_HISTORICAL_CASE_IDS_SHA256 = (
    "cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1"
)
GLOBAL_ORIENTATION_PHASE25_POLICY_SHA256 = (
    "b4c5530dc4766500dbbc854875cfb39baadad94196c63be6150514879993d211"
)
GLOBAL_ORIENTATION_6M73_HISTORICAL_ENGINE_RECEIPT_SHA256 = (
    "0cd0c48c10032757f48a45e7721704fb096c1756f59a86b03fa0513a1c5e8dfb"
)
GLOBAL_ORIENTATION_EXPECTED_EVALUATION_PIPELINE_SHA256 = (
    "40530119249b792728a70cb5ba65cc9c60cf834e1a744d6987dae75046459922"
)
GLOBAL_ORIENTATION_SCORER_CONFIG_SHA256 = (
    "f6592bb681ae1dfad2700291013e04a239c5961687386582ac7c009c5a7de783"
)
GLOBAL_ORIENTATION_INTERNAL_VALIDITY_IMPLEMENTATION_SHA256 = (
    "5b1263ddf83deee0c46142be9e8d973bc9af6710d197f20451ab4d5ee996a619"
)
GLOBAL_ORIENTATION_POSEBUSTERS_IMPLEMENTATION_SHA256 = (
    "a6d1437d0eb3e0fe13ad73b5c4efdc8c0914ceadd904cde55b2a9835bf591a9d"
)
GLOBAL_ORIENTATION_POSEBUSTERS_CONFIG_SHA256 = (
    "1e2013837fc3fbb3334ff5b2e94f029c65f1203f2a2a2abbd7f7d01c008c5533"
)
GLOBAL_ORIENTATION_RMSD_ATOM_MAPPING_SHA256 = (
    "0ab5a381924ae5a4ab08ca0dd6a0af58b8637d83927c88f04c8c82b2d7ce328c"
)
GLOBAL_ORIENTATION_RMSD_SYMMETRY_POLICY_SHA256 = (
    "e29f135b0809fd4fc417899ceaff71b766beb939291a52af06435957e4da833b"
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


def derive_global_orientation_pocket_declaration_sha256(
    *,
    case_id: str,
    historical_case_source_receipt_sha256: str,
    pocket_center: Sequence[float],
    pocket_normal: Sequence[float],
    pocket_radius_angstrom: float,
) -> str:
    """Bind the concrete pocket vectors and radius to one authenticated case."""

    center = _vector(pocket_center, name="pocket_center")
    normal = _vector(pocket_normal, name="pocket_normal")
    length = math.sqrt(sum(component * component for component in normal))
    if length == 0.0:
        raise GlobalOrientationDevelopmentContractError(
            "pocket_normal must be non-zero"
        )
    unit_normal = tuple(component / length for component in normal)
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
            "schema_id": "betelgeuze.engine_v2_global_orientation_pocket_declaration/1.0.0",
            "case_id": _text(case_id, name="case_id"),
            "historical_case_source_receipt_sha256": _digest(
                historical_case_source_receipt_sha256,
                name="historical_case_source_receipt_sha256",
            ),
            "pocket_center_binary64_hex": [value.hex() for value in center],
            "pocket_normal_binary64_hex": [value.hex() for value in unit_normal],
            "pocket_radius_angstrom_binary64_hex": radius.hex(),
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
    historical_case_source: SourcePairedClearanceCaseSourceReceiptV1
    authenticated_problem: AuthenticatedDockingProblem
    receptor_system: AllAtomSystem
    ligand_system: AllAtomSystem
    scorer_context: ScorerV1Context
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
    historical_archive_sha256: str = GLOBAL_ORIENTATION_HISTORICAL_ARCHIVE_SHA256
    historical_member_manifest_sha256: str = (
        GLOBAL_ORIENTATION_HISTORICAL_MEMBER_MANIFEST_SHA256
    )
    historical_bundle_checksum_sha256: str = (
        GLOBAL_ORIENTATION_HISTORICAL_BUNDLE_CHECKSUM_SHA256
    )
    surface_extraction_procedure_id: str = (
        "authenticated_validity_receptor_subset_projection_v1"
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
        if (
            type(self.historical_case_source)
            is not SourcePairedClearanceCaseSourceReceiptV1
            or self.historical_case_source.case_id != self.case_id
        ):
            raise GlobalOrientationDevelopmentContractError(
                "case source is not bound to its authenticated historical member"
            )
        historical_receipt_sha256 = self.historical_case_source.receipt_sha256
        if (
            type(self.authenticated_problem) is not AuthenticatedDockingProblem
            or type(self.receptor_system) is not AllAtomSystem
            or type(self.ligand_system) is not AllAtomSystem
            or type(self.scorer_context) is not ScorerV1Context
        ):
            raise TypeError(
                "case source requires exact authenticated problem, molecular systems, and scorer context"
            )
        authenticated = self.authenticated_problem
        receptor_system_sha256 = canonical_system_sha256(self.receptor_system)
        ligand_system_sha256 = canonical_system_sha256(self.ligand_system)
        if (
            authenticated.input_receipt_sha256
            != self.historical_case_source.authenticated_input_receipt_sha256
            or authenticated.problem.fingerprint_sha256
            != self.historical_case_source.problem_fingerprint_sha256
            or authenticated.receptor_system_sha256 != receptor_system_sha256
            or authenticated.ligand_system_sha256 != ligand_system_sha256
            or self.scorer_context.authority_input_receipt_sha256
            != authenticated.input_receipt_sha256
            or self.scorer_context.receptor_system_sha256 != receptor_system_sha256
            or self.scorer_context.ligand_system_sha256 != ligand_system_sha256
            or self.scorer_context.receptor_atom_indices
            != authenticated.receptor_atom_indices
        ):
            raise GlobalOrientationDevelopmentContractError(
                "prepared molecular systems or scorer context contradict the authenticated historical member"
            )
        if (
            self.source_case_member_receipt_sha256
            != self.historical_case_source.source_case_member_receipt_sha256
            or self.authenticated_input_receipt_sha256
            != self.historical_case_source.authenticated_input_receipt_sha256
        ):
            raise GlobalOrientationDevelopmentContractError(
                "case source identities contradict the authenticated historical member"
            )
        receptor = _coordinates(
            self.receptor_coordinates,
            name="receptor_coordinates",
        )
        ligand = _coordinates(self.ligand_coordinates, name="ligand_coordinates")
        authenticated_receptor = _coordinates(
            self.receptor_system.coordinates[authenticated.receptor_model_index]
            .detach()
            .cpu()
            .tolist(),
            name="authenticated_receptor_coordinates",
        )
        authenticated_ligand = _coordinates(
            self.ligand_system.coordinates[authenticated.ligand_model_index]
            .detach()
            .cpu()
            .tolist(),
            name="authenticated_ligand_coordinates",
        )
        if receptor != authenticated_receptor or ligand != authenticated_ligand:
            raise GlobalOrientationDevelopmentContractError(
                "retained coordinates do not match the authenticated molecular systems"
            )
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
            "historical_archive_sha256",
            "historical_member_manifest_sha256",
            "historical_bundle_checksum_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        if self.ligand_topology_sha256 != canonical_topology_sha256(self.ligand_system):
            raise GlobalOrientationDevelopmentContractError(
                "ligand topology does not match the authenticated molecular system"
            )
        center = _vector(self.pocket_center, name="pocket_center")
        normal = _vector(self.pocket_normal, name="pocket_normal")
        if math.sqrt(sum(component * component for component in normal)) == 0.0:
            raise GlobalOrientationDevelopmentContractError(
                "pocket_normal must be non-zero"
            )
        object.__setattr__(self, "pocket_center", center)
        normal_length = math.sqrt(sum(component * component for component in normal))
        object.__setattr__(
            self,
            "pocket_normal",
            tuple(component / normal_length for component in normal),
        )
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
        if (
            self.historical_archive_sha256
            != GLOBAL_ORIENTATION_HISTORICAL_ARCHIVE_SHA256
            or self.historical_member_manifest_sha256
            != GLOBAL_ORIENTATION_HISTORICAL_MEMBER_MANIFEST_SHA256
            or self.historical_bundle_checksum_sha256
            != GLOBAL_ORIENTATION_HISTORICAL_BUNDLE_CHECKSUM_SHA256
        ):
            raise GlobalOrientationDevelopmentContractError(
                "case source is not bound to the frozen historical archive authority"
            )
        expected_pocket = derive_global_orientation_pocket_declaration_sha256(
            case_id=self.case_id,
            historical_case_source_receipt_sha256=historical_receipt_sha256,
            pocket_center=center,
            pocket_normal=self.pocket_normal,
            pocket_radius_angstrom=radius,
        )
        if self.pocket_declaration_sha256 != expected_pocket:
            raise GlobalOrientationDevelopmentContractError(
                "pocket geometry does not match its authenticated declaration"
            )
        if (
            self.evaluation_pipeline_sha256
            != GLOBAL_ORIENTATION_EXPECTED_EVALUATION_PIPELINE_SHA256
        ):
            raise GlobalOrientationDevelopmentContractError(
                "evaluation pipeline does not match the frozen protocol"
            )
        if (
            authenticated.pocket.center.detach().cpu().tolist() != list(center)
            or authenticated.pocket.radius_angstrom != radius
            or authenticated.validity_context.config.fingerprint_sha256
            != self.pose_validity_config_fingerprint_sha256
        ):
            raise GlobalOrientationDevelopmentContractError(
                "pocket or validity configuration contradicts the authenticated problem"
            )
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
            != "authenticated_validity_receptor_subset_projection_v1"
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
            or indices != authenticated.receptor_atom_indices
        ):
            raise GlobalOrientationDevelopmentContractError(
                "receptor surface indices do not match the authenticated receptor subset"
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
            "historical_case_source": self.historical_case_source.to_dict(),
            "historical_case_source_receipt_sha256": (
                self.historical_case_source.receipt_sha256
            ),
            "historical_archive_sha256": self.historical_archive_sha256,
            "historical_member_manifest_sha256": (
                self.historical_member_manifest_sha256
            ),
            "historical_bundle_checksum_sha256": (
                self.historical_bundle_checksum_sha256
            ),
            "authenticated_problem": self.authenticated_problem.to_dict(),
            "receptor_system_sha256": canonical_system_sha256(self.receptor_system),
            "ligand_system_sha256": canonical_system_sha256(self.ligand_system),
            "scorer_context": self.scorer_context.to_dict(),
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
class GlobalOrientationDevelopmentHistoricalFailureAuthorityV1:
    """Pinned historical authority for the sole 6M73 preparation failure."""

    case_id: str = GLOBAL_ORIENTATION_DEVELOPMENT_PREPARATION_FAILURE_CASE_ID
    historical_archive_sha256: str = GLOBAL_ORIENTATION_HISTORICAL_ARCHIVE_SHA256
    historical_member_manifest_sha256: str = (
        GLOBAL_ORIENTATION_HISTORICAL_MEMBER_MANIFEST_SHA256
    )
    historical_bundle_checksum_sha256: str = (
        GLOBAL_ORIENTATION_HISTORICAL_BUNDLE_CHECKSUM_SHA256
    )
    historical_case_ids_sha256: str = GLOBAL_ORIENTATION_HISTORICAL_CASE_IDS_SHA256
    phase25_policy_sha256: str = GLOBAL_ORIENTATION_PHASE25_POLICY_SHA256
    historical_engine_receipt_sha256: str = (
        GLOBAL_ORIENTATION_6M73_HISTORICAL_ENGINE_RECEIPT_SHA256
    )
    schema_id: str = (
        GLOBAL_ORIENTATION_DEVELOPMENT_HISTORICAL_FAILURE_AUTHORITY_SCHEMA_ID
    )
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        expected = {
            "case_id": GLOBAL_ORIENTATION_DEVELOPMENT_PREPARATION_FAILURE_CASE_ID,
            "historical_archive_sha256": GLOBAL_ORIENTATION_HISTORICAL_ARCHIVE_SHA256,
            "historical_member_manifest_sha256": (
                GLOBAL_ORIENTATION_HISTORICAL_MEMBER_MANIFEST_SHA256
            ),
            "historical_bundle_checksum_sha256": (
                GLOBAL_ORIENTATION_HISTORICAL_BUNDLE_CHECKSUM_SHA256
            ),
            "historical_case_ids_sha256": GLOBAL_ORIENTATION_HISTORICAL_CASE_IDS_SHA256,
            "phase25_policy_sha256": GLOBAL_ORIENTATION_PHASE25_POLICY_SHA256,
            "historical_engine_receipt_sha256": (
                GLOBAL_ORIENTATION_6M73_HISTORICAL_ENGINE_RECEIPT_SHA256
            ),
            "schema_id": (
                GLOBAL_ORIENTATION_DEVELOPMENT_HISTORICAL_FAILURE_AUTHORITY_SCHEMA_ID
            ),
        }
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise GlobalOrientationDevelopmentContractError(
                "preparation-failure authority does not match the pinned historical member"
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.case_id,
            "historical_archive_sha256": self.historical_archive_sha256,
            "historical_member_manifest_sha256": (
                self.historical_member_manifest_sha256
            ),
            "historical_bundle_checksum_sha256": (
                self.historical_bundle_checksum_sha256
            ),
            "historical_case_ids_sha256": self.historical_case_ids_sha256,
            "phase25_policy_sha256": self.phase25_policy_sha256,
            "historical_engine_receipt_sha256": (self.historical_engine_receipt_sha256),
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationDevelopmentContractError(
                "historical preparation-failure authority changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class GlobalOrientationDevelopmentPreparationFailureReceiptV1:
    """Retain the ninth cohort member as a typed preparation failure."""

    historical_authority: GlobalOrientationDevelopmentHistoricalFailureAuthorityV1
    failure_code: str
    schema_id: str = GLOBAL_ORIENTATION_DEVELOPMENT_PREPARATION_FAILURE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if (
            self.schema_id
            != GLOBAL_ORIENTATION_DEVELOPMENT_PREPARATION_FAILURE_SCHEMA_ID
        ):
            raise GlobalOrientationDevelopmentContractError(
                "preparation-failure row is outside the frozen cohort"
            )
        if (
            type(self.historical_authority)
            is not GlobalOrientationDevelopmentHistoricalFailureAuthorityV1
        ):
            raise TypeError(
                "preparation failure requires the exact historical failure authority"
            )
        self.historical_authority.receipt_sha256
        object.__setattr__(
            self, "failure_code", _text(self.failure_code, name="failure_code")
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "case_id": self.historical_authority.case_id,
            "historical_authority": self.historical_authority.to_dict(),
            "historical_authority_receipt_sha256": (
                self.historical_authority.receipt_sha256
            ),
            "preparation_policy_sha256": (
                self.historical_authority.phase25_policy_sha256
            ),
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
    arm_authority_receipt: (
        SourcePairedClearanceCurrentV7LineageReceiptV1 | GlobalOrientationBatch
    )
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
        authority_receipt = self.arm_authority_receipt
        historical = self.case_source.historical_case_source
        if self.arm_id == "baseline_current_v7":
            if (
                type(authority_receipt)
                is not SourcePairedClearanceCurrentV7LineageReceiptV1
            ):
                raise TypeError(
                    "baseline arm requires the exact current-V7 lineage receipt"
                )
            assert isinstance(
                authority_receipt,
                SourcePairedClearanceCurrentV7LineageReceiptV1,
            )
            expected_slots = tuple(
                (
                    proposal.proposal_index,
                    proposal.candidate_id,
                    proposal.fingerprint_sha256,
                    proposal.coordinate_fingerprint_sha256,
                )
                for proposal in authority_receipt.current_v7_proposals
            )
            observed_slots = tuple(
                (
                    slot.proposal_index,
                    slot.candidate_id,
                    slot.proposal_fingerprint_sha256,
                    slot.coordinate_sha256,
                )
                for slot in slots
            )
            if (
                arm_authority != authority_receipt.lineage_identity_sha256
                or arm_authority != historical.current_v7_candidate_lineage_sha256
                or authority_receipt.source_proposal_receipt.receipt_sha256
                != historical.source_proposal_receipt_sha256
                or authority_receipt.source_proposal_receipt.authenticated_input_receipt_sha256
                != historical.authenticated_input_receipt_sha256
                or any(slot.generation_status != "generated" for slot in slots)
                or any(
                    slot.generation_receipt_sha256 != authority_receipt.receipt_sha256
                    for slot in slots
                )
                or observed_slots != expected_slots
            ):
                raise GlobalOrientationDevelopmentContractError(
                    "baseline lineage does not match its concrete current-V7 authority"
                )
        else:
            if type(authority_receipt) is not GlobalOrientationBatch:
                raise TypeError(
                    "experimental arm requires the exact global-orientation batch"
                )
            assert isinstance(authority_receipt, GlobalOrientationBatch)
            expected_config = (
                authority_receipt.config.orientation_count == 8
                and authority_receipt.config.translation_shell_radii == (1.5,)
                and authority_receipt.config.translation_points_per_shell == 7
                and authority_receipt.config.minimum_receptor_distance == 1.1
            )
            expected_surface_sha256 = _sha256(
                _coordinates_projection(self.case_source.receptor_surface_points)
            )
            expected_slots = tuple(
                (
                    source_slot.proposal_index,
                    f"{self.case_source.case_id}:{self.arm_id}:{source_slot.proposal_index:02d}",
                    "generated" if source_slot.accepted else "failed",
                    source_slot.receipt_sha256 if source_slot.accepted else None,
                    source_slot.coordinate_sha256 if source_slot.accepted else None,
                    source_slot.receipt_sha256 if source_slot.accepted else None,
                    None if source_slot.accepted else source_slot.rejection_code,
                )
                for source_slot in authority_receipt.slots
            )
            observed_slots = tuple(
                (
                    slot.proposal_index,
                    slot.candidate_id,
                    slot.generation_status,
                    slot.proposal_fingerprint_sha256,
                    slot.coordinate_sha256,
                    slot.generation_receipt_sha256,
                    slot.failure_code,
                )
                for slot in slots
            )
            if (
                arm_authority != authority_receipt.receipt_sha256
                or authority_receipt.profile_id
                != "deterministic_surface_aware_rigid_v2"
                or authority_receipt.source_receipt_sha256 != case_source
                or authority_receipt.ligand_input_sha256
                != _sha256(_coordinates_projection(self.case_source.ligand_coordinates))
                or authority_receipt.receptor_surface_input_sha256
                != expected_surface_sha256
                or authority_receipt.pocket_center != self.case_source.pocket_center
                or authority_receipt.pocket_normal != self.case_source.pocket_normal
                or not expected_config
                or observed_slots != expected_slots
            ):
                raise GlobalOrientationDevelopmentContractError(
                    "experimental lineage does not rederive from its concrete generator batch"
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
            "arm_authority_receipt": self.arm_authority_receipt.to_dict(),
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
class GlobalOrientationDevelopmentPartialCandidateEvidenceV1:
    """Retain completed scoring/evaluation stages when a later stage fails."""

    candidate_id: str
    proposal_index: int
    proposal_fingerprint_sha256: str
    coordinate_sha256: str
    scorer_terms: ScorerV1Terms | None
    internal_validity: SourcePairedClearanceInternalValidityEvidenceV1 | None
    posebusters: SourcePairedClearancePoseBustersEvidenceV1 | None
    rmsd: SourcePairedClearanceRmsdEvidenceV1 | None
    raw_score_rank: int | None
    schema_id: str = GLOBAL_ORIENTATION_DEVELOPMENT_PARTIAL_EVIDENCE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != GLOBAL_ORIENTATION_DEVELOPMENT_PARTIAL_EVIDENCE_SCHEMA_ID:
            raise GlobalOrientationDevelopmentContractError(
                "partial-evidence schema_id is invalid"
            )
        object.__setattr__(
            self,
            "candidate_id",
            _text(self.candidate_id, name="candidate_id"),
        )
        if type(self.proposal_index) is not int or self.proposal_index < 0:
            raise GlobalOrientationDevelopmentContractError(
                "partial-evidence proposal_index is invalid"
            )
        for name in ("proposal_fingerprint_sha256", "coordinate_sha256"):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        expected_types = (
            (self.scorer_terms, ScorerV1Terms, "scorer_terms"),
            (
                self.internal_validity,
                SourcePairedClearanceInternalValidityEvidenceV1,
                "internal_validity",
            ),
            (
                self.posebusters,
                SourcePairedClearancePoseBustersEvidenceV1,
                "posebusters",
            ),
            (self.rmsd, SourcePairedClearanceRmsdEvidenceV1, "rmsd"),
        )
        for value, expected_type, name in expected_types:
            if value is not None and type(value) is not expected_type:
                raise TypeError(f"{name} has an invalid evidence type")
        if self.scorer_terms is None:
            raise GlobalOrientationDevelopmentContractError(
                "partial evidence must retain at least the completed score stage"
            )
        if (self.internal_validity is None) != (self.posebusters is None):
            raise GlobalOrientationDevelopmentContractError(
                "partial validity evidence must retain both evaluators"
            )
        if self.rmsd is not None and self.posebusters is None:
            raise GlobalOrientationDevelopmentContractError(
                "partial RMSD evidence requires completed validity evidence"
            )
        if type(self.raw_score_rank) is not int or self.raw_score_rank < 1:
            raise GlobalOrientationDevelopmentContractError(
                "partial scored evidence requires a positive raw score rank"
            )
        linked_values = tuple(
            value
            for value in (
                self.scorer_terms,
                self.internal_validity,
                self.posebusters,
                self.rmsd,
            )
            if value is not None
        )
        if any(
            value.proposal_fingerprint_sha256 != self.proposal_fingerprint_sha256
            for value in linked_values
        ) or any(
            value.coordinate_sha256 != self.coordinate_sha256
            for value in linked_values
            if not isinstance(value, ScorerV1Terms)
        ):
            raise GlobalOrientationDevelopmentContractError(
                "partial evidence stages are cross-wired"
            )
        pose_evidence = tuple(
            value
            for value in (self.internal_validity, self.posebusters, self.rmsd)
            if value is not None
        )
        if len({value.pose_artifact_sha256 for value in pose_evidence}) > 1:
            raise GlobalOrientationDevelopmentContractError(
                "partial evidence stages do not describe one pose artifact"
            )
        if (
            self.posebusters is not None
            and self.rmsd is not None
            and (
                self.posebusters.report_artifact_sha256
                != self.rmsd.report_artifact_sha256
                or self.posebusters.native_pose_artifact_sha256
                != self.rmsd.native_pose_artifact_sha256
                or self.posebusters.receptor_artifact_sha256
                != self.rmsd.receptor_artifact_sha256
                or self.posebusters.implementation_sha256
                != self.rmsd.implementation_sha256
                or self.posebusters.config_sha256 != self.rmsd.config_sha256
            )
        ):
            raise GlobalOrientationDevelopmentContractError(
                "partial PoseBusters and RMSD evidence do not share one report"
            )
        for value in linked_values:
            value.receipt_sha256
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "candidate_id": self.candidate_id,
            "proposal_index": self.proposal_index,
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "coordinate_sha256": self.coordinate_sha256,
            "scorer_terms": self.scorer_terms.to_dict(),
            "internal_validity": (
                None
                if self.internal_validity is None
                else self.internal_validity.to_dict()
            ),
            "posebusters": (
                None if self.posebusters is None else self.posebusters.to_dict()
            ),
            "rmsd": None if self.rmsd is None else self.rmsd.to_dict(),
            "raw_score_rank": self.raw_score_rank,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationDevelopmentContractError(
                "partial candidate evidence changed"
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
    partial_evidence: GlobalOrientationDevelopmentPartialCandidateEvidenceV1 | None = (
        None
    )
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
        partial = self.partial_evidence
        if (
            partial is not None
            and type(partial)
            is not GlobalOrientationDevelopmentPartialCandidateEvidenceV1
        ):
            raise TypeError("partial_evidence has an invalid evidence type")
        if evidence is not None and partial is not None:
            raise GlobalOrientationDevelopmentContractError(
                "observation cannot carry full and partial evidence together"
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
        elif partial is not None:
            if (
                self.generation_status != "generated"
                or partial.proposal_index != self.proposal_index
                or partial.candidate_id != self.candidate_id
                or partial.proposal_fingerprint_sha256
                != self.proposal_fingerprint_sha256
                or partial.coordinate_sha256 != self.coordinate_sha256
                or self.score_status != "scored"
                or self.validity_status
                != ("evaluated" if partial.posebusters is not None else "not_evaluated")
                or self.rmsd_status
                != ("evaluated" if partial.rmsd is not None else "not_evaluated")
            ):
                raise GlobalOrientationDevelopmentContractError(
                    "partial candidate evidence is cross-wired or contradicts stage state"
                )
            partial.receipt_sha256
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
            "partial_evidence": (
                None
                if self.partial_evidence is None
                else self.partial_evidence.to_dict()
            ),
            "score_binary64_hex": (
                None
                if self.candidate_evidence is None and self.partial_evidence is None
                else (
                    self.candidate_evidence.scorer_terms.total_score.hex()
                    if self.candidate_evidence is not None
                    else self.partial_evidence.scorer_terms.total_score.hex()
                )
            ),
            "internal_valid": (
                None
                if self.candidate_evidence is None
                and (
                    self.partial_evidence is None
                    or self.partial_evidence.internal_validity is None
                )
                else (
                    self.candidate_evidence.internal_validity.valid
                    if self.candidate_evidence is not None
                    else self.partial_evidence.internal_validity.valid
                )
            ),
            "posebusters_valid": (
                None
                if self.candidate_evidence is None
                and (
                    self.partial_evidence is None
                    or self.partial_evidence.posebusters is None
                )
                else (
                    self.candidate_evidence.posebusters.valid
                    if self.candidate_evidence is not None
                    else self.partial_evidence.posebusters.valid
                )
            ),
            "rmsd_angstrom_binary64_hex": (
                None
                if self.candidate_evidence is None
                and (
                    self.partial_evidence is None or self.partial_evidence.rmsd is None
                )
                else (
                    self.candidate_evidence.rmsd.rmsd_angstrom.hex()
                    if self.candidate_evidence is not None
                    else self.partial_evidence.rmsd.rmsd_angstrom.hex()
                )
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


def _observation_evidence_components(
    observation: GlobalOrientationDevelopmentObservationSlotV1,
) -> tuple[
    ScorerV1Terms | None,
    SourcePairedClearanceInternalValidityEvidenceV1 | None,
    SourcePairedClearancePoseBustersEvidenceV1 | None,
    SourcePairedClearanceRmsdEvidenceV1 | None,
    int | None,
]:
    if observation.candidate_evidence is not None:
        evidence = observation.candidate_evidence
        return (
            evidence.scorer_terms,
            evidence.internal_validity,
            evidence.posebusters,
            evidence.rmsd,
            evidence.raw_score_rank,
        )
    if observation.partial_evidence is not None:
        partial = observation.partial_evidence
        return (
            partial.scorer_terms,
            partial.internal_validity,
            partial.posebusters,
            partial.rmsd,
            partial.raw_score_rank,
        )
    return (None, None, None, None, None)


def _validate_observation_authority(
    *,
    case_source: GlobalOrientationDevelopmentCaseSourceReceiptV1,
    lineage: GlobalOrientationDevelopmentArmLineageReceiptV1,
    observation: GlobalOrientationDevelopmentObservationSlotV1,
) -> None:
    scorer, internal, posebusters, rmsd, _ = _observation_evidence_components(
        observation
    )
    historical = case_source.historical_case_source
    full_evidence = observation.candidate_evidence
    if full_evidence is not None:
        expected_source_proposal = (
            observation.proposal_fingerprint_sha256
            if lineage.arm_id == "experimental_global_orientation_v1"
            else lineage.arm_authority_receipt.source_proposal_fingerprint_sha256(
                observation.proposal_index
            )
        )
        if full_evidence.source_proposal_fingerprint_sha256 != expected_source_proposal:
            raise GlobalOrientationDevelopmentContractError(
                "candidate evidence contradicts the concrete arm source lineage"
            )
    if scorer is not None and (
        scorer.authority_input_receipt_sha256
        != historical.authenticated_input_receipt_sha256
        or scorer.context_fingerprint_sha256
        != case_source.scorer_context.fingerprint_sha256
        or scorer.config_fingerprint_sha256 != GLOBAL_ORIENTATION_SCORER_CONFIG_SHA256
        or scorer.backend_receipt_sha256 != case_source.scorer_backend_receipt_sha256
    ):
        raise GlobalOrientationDevelopmentContractError(
            "candidate score evidence contradicts the frozen case/scorer authority"
        )
    if internal is not None and (
        internal.authority_input_receipt_sha256
        != historical.authenticated_input_receipt_sha256
        or internal.problem_fingerprint_sha256 != historical.problem_fingerprint_sha256
        or internal.context_fingerprint_sha256
        != case_source.authenticated_problem.validity_context.fingerprint_sha256
        or internal.config_fingerprint_sha256
        != case_source.pose_validity_config_fingerprint_sha256
        or internal.evaluator_implementation_sha256
        != GLOBAL_ORIENTATION_INTERNAL_VALIDITY_IMPLEMENTATION_SHA256
    ):
        raise GlobalOrientationDevelopmentContractError(
            "internal-validity evidence contradicts the frozen case authority"
        )
    if posebusters is not None and (
        posebusters.implementation_sha256
        != GLOBAL_ORIENTATION_POSEBUSTERS_IMPLEMENTATION_SHA256
        or posebusters.config_sha256 != GLOBAL_ORIENTATION_POSEBUSTERS_CONFIG_SHA256
        or posebusters.native_pose_artifact_sha256
        != historical.native_pose_artifact_sha256
        or posebusters.receptor_artifact_sha256 != historical.receptor_artifact_sha256
    ):
        raise GlobalOrientationDevelopmentContractError(
            "PoseBusters evidence contradicts the frozen case/evaluator authority"
        )
    if rmsd is not None and (
        rmsd.implementation_sha256
        != GLOBAL_ORIENTATION_POSEBUSTERS_IMPLEMENTATION_SHA256
        or rmsd.config_sha256 != GLOBAL_ORIENTATION_POSEBUSTERS_CONFIG_SHA256
        or rmsd.native_pose_artifact_sha256 != historical.native_pose_artifact_sha256
        or rmsd.receptor_artifact_sha256 != historical.receptor_artifact_sha256
        or rmsd.atom_mapping_sha256 != GLOBAL_ORIENTATION_RMSD_ATOM_MAPPING_SHA256
        or rmsd.symmetry_policy_sha256 != GLOBAL_ORIENTATION_RMSD_SYMMETRY_POLICY_SHA256
    ):
        raise GlobalOrientationDevelopmentContractError(
            "RMSD evidence contradicts the frozen case/evaluator authority"
        )


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
            _validate_observation_authority(
                case_source=self.lineage.case_source,
                lineage=self.lineage,
                observation=observation,
            )
        scored_rows = []
        for observation in observations:
            scorer, _, _, _, raw_rank = _observation_evidence_components(observation)
            if scorer is not None:
                scored_rows.append(
                    (scorer.total_score, observation.proposal_index, raw_rank)
                )
        expected_order = sorted(
            scored_rows,
            key=lambda value: (value[0], value[1]),
        )
        if any(
            raw_rank != expected_rank
            for expected_rank, (_, _, raw_rank) in enumerate(expected_order, start=1)
        ):
            raise GlobalOrientationDevelopmentContractError(
                "raw score ranks do not rederive from deterministic score ordering"
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
