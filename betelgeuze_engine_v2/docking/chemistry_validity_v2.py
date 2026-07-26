"""Preparation-bound, chemistry-aware pose-validity diagnostics v2.

The v1 chemistry-aware validity contract is intentionally coupled to explicit
force-field parameters and partial charges.  This v2 contract serves the
earlier RDKit/OpenFF-preparation and interpretable-scorer lane without claiming
that those missing parameters exist.  It binds the verified preparation
receipt and transformed canonical topology, then evaluates element-scaled
penetration, ligand self-clash, reference-relative bonded geometry, and declared
stereochemistry.  Thresholds remain hand-fixed diagnostics, not validated
chemical applicability policy.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Integral, Real
from types import MappingProxyType
from typing import Sequence

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    canonical_topology_sha256,
    require_valid_all_atom_system,
    verify_rdkit_openff_prepared_system,
)

from .geometric_scoring import (
    GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM,
    GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256,
)
from .identity import DockingProblemIdentity
from .proposals import DockingProposal
from .validity import (
    PoseValidityConfig,
    PoseValidityContext,
    PoseValidityError,
    PoseValidityResult,
)


CHEMISTRY_AWARE_POSE_VALIDITY_V2_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_chemistry_aware_pose_validity_v2_config/1.0.0"
)
CHEMISTRY_AWARE_POSE_VALIDITY_V2_CONTEXT_SCHEMA_ID = (
    "betelgeuze.engine_v2_chemistry_aware_pose_validity_v2_context/1.0.0"
)
CHEMISTRY_AWARE_POSE_VALIDITY_V2_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_chemistry_aware_pose_validity_v2_result/1.0.0"
)
CHEMISTRY_AWARE_POSE_VALIDITY_V2_PROFILE_ID = (
    "engine_v2_preparation_bound_heuristic_pose_validity/1.0.0"
)
CHEMISTRY_AWARE_POSE_VALIDITY_V2_BLOCKERS = (
    "chemistry_aware_pose_validity_v2_thresholds_heuristic_uncalibrated",
    "element_radius_profile_not_force_field_parameterization",
    "receptor_chemistry_preparation_receipt_missing",
    "partial_charge_electrostatic_validity_not_evaluated",
    "protonation_and_tautomer_validity_not_independently_validated",
    "absolute_stereo_label_assignment_not_independently_recomputed",
    "aromatic_planarity_validity_not_independently_validated",
    "public_pose_validity_validation_missing",
    "independent_scientific_review_missing",
)
_DECLARED_ATOM_STEREO = {"R", "S"}
_DECLARED_BOND_STEREO = {"E", "Z", "CIS", "TRANS"}


class ChemistryAwarePoseValidityV2Error(PoseValidityError):
    """A v2 context, pose, or result violates its bounded evidence contract."""


def _canonical_sha256(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ChemistryAwarePoseValidityV2Error(
            "chemistry-aware validity value is not canonical JSON"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ChemistryAwarePoseValidityV2Error(f"{name} must be a lowercase SHA-256")
    return value


def _finite(
    value: object,
    *,
    name: str,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ChemistryAwarePoseValidityV2Error(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ChemistryAwarePoseValidityV2Error(f"{name} must be finite")
    if positive and result <= 0.0:
        raise ChemistryAwarePoseValidityV2Error(f"{name} must be positive")
    if nonnegative and result < 0.0:
        raise ChemistryAwarePoseValidityV2Error(f"{name} must be non-negative")
    return result


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ChemistryAwarePoseValidityV2Error(f"{name} must be an integer")
    result = int(value)
    if not minimum <= result <= maximum:
        raise ChemistryAwarePoseValidityV2Error(
            f"{name} is outside its integer capacity"
        )
    return result


def _coordinates(
    value: torch.Tensor,
    *,
    name: str,
    atom_count: int | None = None,
) -> torch.Tensor:
    if (
        not isinstance(value, torch.Tensor)
        or value.ndim != 2
        or value.shape[1] != 3
        or value.dtype != torch.float64
        or value.device.type != "cpu"
        or not bool(torch.isfinite(value).all().item())
        or (atom_count is not None and value.shape != (atom_count, 3))
    ):
        expected = "[N,3]" if atom_count is None else f"[{atom_count},3]"
        raise ChemistryAwarePoseValidityV2Error(
            f"{name} must be CPU float64 with shape {expected}"
        )
    return value.detach()


def chemistry_aware_pose_validity_v2_profile_document() -> dict[str, object]:
    return {
        "profile_id": CHEMISTRY_AWARE_POSE_VALIDITY_V2_PROFILE_ID,
        "radius_profile_sha256": GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256,
        "supported_atomic_numbers": sorted(GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM),
        "ligand_self_exclusions": "one_two_and_one_three_topology_pairs",
        "cross_penetration": "distance_over_fixed_element_radius_sum",
        "bond_geometry": "reference_relative_absolute_length_delta",
        "angle_geometry": "reference_relative_absolute_angle_delta",
        "atom_stereo": "reference_relative_signed_volume_for_declared_R_S",
        "bond_stereo": (
            "reference_relative_wrapped_dihedral_for_declared_E_Z_CIS_TRANS"
        ),
        "absolute_stereo_assignment_recomputed": False,
        "partial_charges_used": False,
        "force_field_parameters_used": False,
        "calibrated": False,
    }


CHEMISTRY_AWARE_POSE_VALIDITY_V2_PROFILE_SHA256 = _canonical_sha256(
    chemistry_aware_pose_validity_v2_profile_document()
)


@dataclass(frozen=True, slots=True)
class ChemistryAwarePoseValidityV2Config:
    maximum_bond_length_delta_angstrom: float = 0.15
    maximum_angle_delta_degrees: float = 15.0
    maximum_double_bond_dihedral_delta_degrees: float = 20.0
    minimum_ligand_self_contact_scale: float = 0.58
    minimum_receptor_ligand_contact_scale: float = 0.58
    receptor_shell_radius_angstrom: float = 18.0
    maximum_absolute_formal_charge: int = 2
    chirality_volume_tolerance: float = 1.0e-8
    rotation_tolerance: float = 1.0e-6
    max_bonds: int = 8_192
    max_angles: int = 32_768
    max_ligand_pair_checks: int = 500_000
    max_receptor_ligand_pair_checks: int = 1_000_000
    schema_id: str = CHEMISTRY_AWARE_POSE_VALIDITY_V2_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != CHEMISTRY_AWARE_POSE_VALIDITY_V2_CONFIG_SCHEMA_ID:
            raise ChemistryAwarePoseValidityV2Error(
                "unsupported chemistry-aware validity v2 config schema"
            )
        for name in (
            "maximum_bond_length_delta_angstrom",
            "maximum_angle_delta_degrees",
            "maximum_double_bond_dihedral_delta_degrees",
            "chirality_volume_tolerance",
            "rotation_tolerance",
        ):
            object.__setattr__(
                self,
                name,
                _finite(getattr(self, name), name=name, nonnegative=True),
            )
        for name in (
            "minimum_ligand_self_contact_scale",
            "minimum_receptor_ligand_contact_scale",
        ):
            scale = _finite(getattr(self, name), name=name, positive=True)
            if scale >= 1.0:
                raise ChemistryAwarePoseValidityV2Error(f"{name} must be less than one")
            object.__setattr__(self, name, scale)
        object.__setattr__(
            self,
            "receptor_shell_radius_angstrom",
            _finite(
                self.receptor_shell_radius_angstrom,
                name="receptor_shell_radius_angstrom",
                positive=True,
            ),
        )
        object.__setattr__(
            self,
            "maximum_absolute_formal_charge",
            _exact_int(
                self.maximum_absolute_formal_charge,
                name="maximum_absolute_formal_charge",
                minimum=0,
                maximum=8,
            ),
        )
        for name, maximum in (
            ("max_bonds", 100_000),
            ("max_angles", 500_000),
            ("max_ligand_pair_checks", 2_000_000),
            ("max_receptor_ligand_pair_checks", 2_000_000),
        ):
            object.__setattr__(
                self,
                name,
                _exact_int(
                    getattr(self, name),
                    name=name,
                    minimum=1,
                    maximum=maximum,
                ),
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "maximum_bond_length_delta_angstrom": (
                self.maximum_bond_length_delta_angstrom
            ),
            "maximum_angle_delta_degrees": self.maximum_angle_delta_degrees,
            "maximum_double_bond_dihedral_delta_degrees": (
                self.maximum_double_bond_dihedral_delta_degrees
            ),
            "minimum_ligand_self_contact_scale": (
                self.minimum_ligand_self_contact_scale
            ),
            "minimum_receptor_ligand_contact_scale": (
                self.minimum_receptor_ligand_contact_scale
            ),
            "receptor_shell_radius_angstrom": (self.receptor_shell_radius_angstrom),
            "maximum_absolute_formal_charge": self.maximum_absolute_formal_charge,
            "chirality_volume_tolerance": self.chirality_volume_tolerance,
            "rotation_tolerance": self.rotation_tolerance,
            "max_bonds": self.max_bonds,
            "max_angles": self.max_angles,
            "max_ligand_pair_checks": self.max_ligand_pair_checks,
            "max_receptor_ligand_pair_checks": (self.max_receptor_ligand_pair_checks),
            "profile_sha256": CHEMISTRY_AWARE_POSE_VALIDITY_V2_PROFILE_SHA256,
            "threshold_source": "hand_fixed_unvalidated_diagnostic_policy",
            "calibrated": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


def _adjacency(system: AllAtomSystem) -> tuple[tuple[int, ...], ...]:
    rows: list[set[int]] = [set() for _ in range(system.atom_count)]
    for bond in system.bonds:
        rows[bond.atom_i].add(bond.atom_j)
        rows[bond.atom_j].add(bond.atom_i)
    return tuple(tuple(sorted(row)) for row in rows)


def _angle_triplets(
    adjacency: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        (first, center, second)
        for center, neighbors in enumerate(adjacency)
        for position, first in enumerate(neighbors)
        for second in neighbors[position + 1 :]
    )


def _declared_atom_stereo_rows(
    system: AllAtomSystem,
    adjacency: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, int, int, int, str], ...]:
    rows: list[tuple[int, int, int, int, str]] = []
    for atom in system.atoms:
        label = atom.stereo.strip().upper()
        if label not in _DECLARED_ATOM_STEREO:
            continue
        neighbors = adjacency[atom.index]
        if len(neighbors) not in {3, 4}:
            raise ChemistryAwarePoseValidityV2Error(
                "declared tetrahedral stereo requires three or four explicit neighbors"
            )
        rows.append(
            (
                atom.index,
                neighbors[0],
                neighbors[1],
                neighbors[2],
                label,
            )
        )
    return tuple(rows)


def _declared_bond_stereo_rows(
    system: AllAtomSystem,
    adjacency: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, int, int, int, str], ...]:
    rows: list[tuple[int, int, int, int, str]] = []
    for bond in system.bonds:
        label = bond.stereo.strip().upper()
        if label not in _DECLARED_BOND_STEREO:
            continue
        first_neighbors = tuple(
            index for index in adjacency[bond.atom_i] if index != bond.atom_j
        )
        second_neighbors = tuple(
            index for index in adjacency[bond.atom_j] if index != bond.atom_i
        )
        if not first_neighbors or not second_neighbors:
            raise ChemistryAwarePoseValidityV2Error(
                "declared double-bond stereo requires an explicit substituent on each side"
            )
        rows.append(
            (
                min(first_neighbors),
                bond.atom_i,
                bond.atom_j,
                min(second_neighbors),
                label,
            )
        )
    return tuple(rows)


def _angles(
    coordinates: torch.Tensor,
    rows: tuple[tuple[int, int, int], ...],
) -> tuple[torch.Tensor, bool]:
    if not rows:
        return torch.empty(0, dtype=torch.float64), False
    indices = torch.tensor(rows, dtype=torch.long)
    first = coordinates.index_select(0, indices[:, 0])
    center = coordinates.index_select(0, indices[:, 1])
    second = coordinates.index_select(0, indices[:, 2])
    first_vector = first - center
    second_vector = second - center
    denominator = torch.linalg.vector_norm(
        first_vector,
        dim=1,
    ) * torch.linalg.vector_norm(second_vector, dim=1)
    collapsed = bool((denominator <= 1.0e-12).any().item())
    safe = torch.clamp(denominator, min=1.0e-12)
    cosine = torch.sum(first_vector * second_vector, dim=1) / safe
    return torch.acos(torch.clamp(cosine, min=-1.0, max=1.0)), collapsed


def _dihedrals(
    coordinates: torch.Tensor,
    rows: tuple[tuple[int, int, int, int, str], ...],
) -> tuple[torch.Tensor, bool]:
    if not rows:
        return torch.empty(0, dtype=torch.float64), False
    indices = torch.tensor([row[:4] for row in rows], dtype=torch.long)
    p0 = coordinates.index_select(0, indices[:, 0])
    p1 = coordinates.index_select(0, indices[:, 1])
    p2 = coordinates.index_select(0, indices[:, 2])
    p3 = coordinates.index_select(0, indices[:, 3])
    b0 = p0 - p1
    b1 = p2 - p1
    b2 = p3 - p2
    b1_norm = torch.linalg.vector_norm(b1, dim=1)
    safe_b1 = torch.clamp(b1_norm, min=1.0e-12)
    axis = b1 / safe_b1[:, None]
    v = b0 - torch.sum(b0 * axis, dim=1)[:, None] * axis
    w = b2 - torch.sum(b2 * axis, dim=1)[:, None] * axis
    v_norm = torch.linalg.vector_norm(v, dim=1)
    w_norm = torch.linalg.vector_norm(w, dim=1)
    collapsed = bool(
        ((b1_norm <= 1.0e-12) | (v_norm <= 1.0e-12) | (w_norm <= 1.0e-12)).any().item()
    )
    v = v / torch.clamp(v_norm, min=1.0e-12)[:, None]
    w = w / torch.clamp(w_norm, min=1.0e-12)[:, None]
    x = torch.sum(v * w, dim=1)
    y = torch.sum(torch.cross(axis, v, dim=1) * w, dim=1)
    return torch.atan2(y, x), collapsed


def _contact_observation(
    distances: torch.Tensor,
    radius_sums: torch.Tensor,
    *,
    minimum_scale: float,
) -> tuple[float, int, float]:
    if distances.numel() == 0:
        return 999.0, 0, 0.0
    ratios = distances / radius_sums
    minimum_ratio = float(torch.min(ratios).item())
    penetration_mask = ratios < minimum_scale
    penetration_count = int(penetration_mask.sum().item())
    overlap = torch.clamp(minimum_scale * radius_sums - distances, min=0.0)
    maximum_overlap = float(torch.max(overlap).item())
    return minimum_ratio, penetration_count, maximum_overlap


@dataclass(frozen=True)
class ChemistryAwarePoseValidityV2Result(PoseValidityResult):
    validity_context_fingerprint_sha256: str
    problem_fingerprint_sha256: str
    proposal_fingerprint_sha256: str
    receptor_system_sha256: str
    ligand_system_sha256: str
    ligand_preparation_receipt_sha256: str
    validity_config_fingerprint_sha256: str
    parameter_source_sha256: str = GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256
    schema_id: str = CHEMISTRY_AWARE_POSE_VALIDITY_V2_RESULT_SCHEMA_ID

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.schema_id != CHEMISTRY_AWARE_POSE_VALIDITY_V2_RESULT_SCHEMA_ID:
            raise ChemistryAwarePoseValidityV2Error(
                "unsupported chemistry-aware validity v2 result schema"
            )
        checks = dict(self.checks)
        evaluated = dict(self.evaluated_checks)
        if not checks or set(checks) != set(evaluated):
            raise ChemistryAwarePoseValidityV2Error(
                "v2 checks and evaluated checks must share non-empty keys"
            )
        if not all(
            isinstance(value, bool) for value in (*checks.values(), *evaluated.values())
        ):
            raise ChemistryAwarePoseValidityV2Error(
                "v2 validity checks must contain booleans"
            )
        expected_complete = all(evaluated.values())
        expected_valid = all(
            checks[name] for name, admitted in evaluated.items() if admitted
        )
        if self.complete is not expected_complete:
            raise ChemistryAwarePoseValidityV2Error(
                "v2 completeness does not match evaluated checks"
            )
        if self.valid_within_evaluated_scope is not expected_valid:
            raise ChemistryAwarePoseValidityV2Error(
                "v2 validity does not match evaluated checks"
            )
        reasons = dict(self.not_evaluated_reasons)
        if set(reasons) != {
            name for name, admitted in evaluated.items() if not admitted
        } or any(
            not isinstance(name, str)
            or not name
            or not isinstance(reason, str)
            or not reason
            for name, reason in reasons.items()
        ):
            raise ChemistryAwarePoseValidityV2Error(
                "v2 unevaluated checks require exact reason rows"
            )
        for name, value in self.measurements.items():
            if (
                not isinstance(name, str)
                or not name
                or isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(float(value))
            ):
                raise ChemistryAwarePoseValidityV2Error(
                    "v2 measurements must contain finite numeric values"
                )
        blockers = tuple(self.blockers)
        if (
            any(not isinstance(value, str) or not value for value in blockers)
            or len(blockers) != len(set(blockers))
            or not set(CHEMISTRY_AWARE_POSE_VALIDITY_V2_BLOCKERS).issubset(blockers)
        ):
            raise ChemistryAwarePoseValidityV2Error(
                "v2 blockers must be unique non-empty strings"
            )
        for name in (
            "validity_context_fingerprint_sha256",
            "problem_fingerprint_sha256",
            "proposal_fingerprint_sha256",
            "receptor_system_sha256",
            "ligand_system_sha256",
            "ligand_preparation_receipt_sha256",
            "validity_config_fingerprint_sha256",
            "parameter_source_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        if self.parameter_source_sha256 != (GEOMETRY_DIAGNOSTIC_RADIUS_PROFILE_SHA256):
            raise ChemistryAwarePoseValidityV2Error(
                "v2 result parameter source is not the frozen radius profile"
            )

    def to_dict(self) -> dict[str, object]:
        payload = super().to_dict()
        payload.update(
            {
                "schema_id": self.schema_id,
                "validity_context_fingerprint_sha256": (
                    self.validity_context_fingerprint_sha256
                ),
                "problem_fingerprint_sha256": self.problem_fingerprint_sha256,
                "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
                "receptor_system_sha256": self.receptor_system_sha256,
                "ligand_system_sha256": self.ligand_system_sha256,
                "ligand_preparation_receipt_sha256": (
                    self.ligand_preparation_receipt_sha256
                ),
                "validity_config_fingerprint_sha256": (
                    self.validity_config_fingerprint_sha256
                ),
                "parameter_source_sha256": self.parameter_source_sha256,
                "profile_sha256": (CHEMISTRY_AWARE_POSE_VALIDITY_V2_PROFILE_SHA256),
                "thresholds_calibrated": False,
                "scientifically_validated": False,
                "claim_safe": False,
            }
        )
        return payload


@dataclass(frozen=True)
class ChemistryAwarePoseValidityV2Context(PoseValidityContext):
    chemistry_config: ChemistryAwarePoseValidityV2Config
    receptor_system_sha256: str
    ligand_system_sha256: str
    ligand_topology_sha256: str
    ligand_preparation_receipt_sha256: str
    receptor_atomic_numbers: tuple[int, ...]
    ligand_atomic_numbers: tuple[int, ...]
    receptor_formal_charges: tuple[int, ...]
    ligand_formal_charges: tuple[int, ...]
    ligand_bond_rows: tuple[tuple[int, int, float], ...]
    angle_triplets: tuple[tuple[int, int, int], ...]
    declared_atom_stereo_rows: tuple[tuple[int, int, int, int, str], ...]
    declared_bond_stereo_rows: tuple[tuple[int, int, int, int, str], ...]
    aromatic_atom_indices: tuple[int, ...]
    ring_atom_indices: tuple[int, ...]
    context_blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.chemistry_config, ChemistryAwarePoseValidityV2Config):
            raise ChemistryAwarePoseValidityV2Error(
                "chemistry_config must be ChemistryAwarePoseValidityV2Config"
            )
        for name in (
            "receptor_system_sha256",
            "ligand_system_sha256",
            "ligand_topology_sha256",
            "ligand_preparation_receipt_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        for name in (
            "receptor_atomic_numbers",
            "ligand_atomic_numbers",
            "receptor_formal_charges",
            "ligand_formal_charges",
            "aromatic_atom_indices",
            "ring_atom_indices",
        ):
            values = tuple(int(value) for value in getattr(self, name))
            object.__setattr__(self, name, values)
        unsupported = sorted(
            set((*self.receptor_atomic_numbers, *self.ligand_atomic_numbers))
            - set(GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM)
        )
        if unsupported:
            raise ChemistryAwarePoseValidityV2Error(
                f"validity context contains unsupported atomic numbers {unsupported}"
            )
        bond_rows = tuple(
            (int(first), int(second), _finite(order, name="bond order", positive=True))
            for first, second, order in self.ligand_bond_rows
        )
        angle_rows = tuple(
            (int(first), int(center), int(second))
            for first, center, second in self.angle_triplets
        )
        atom_stereo_rows = tuple(
            (int(center), int(first), int(second), int(third), str(label))
            for center, first, second, third, label in self.declared_atom_stereo_rows
        )
        bond_stereo_rows = tuple(
            (int(first), int(center_i), int(center_j), int(second), str(label))
            for first, center_i, center_j, second, label in self.declared_bond_stereo_rows
        )
        object.__setattr__(self, "ligand_bond_rows", bond_rows)
        object.__setattr__(self, "angle_triplets", angle_rows)
        object.__setattr__(self, "declared_atom_stereo_rows", atom_stereo_rows)
        object.__setattr__(self, "declared_bond_stereo_rows", bond_stereo_rows)
        ligand_count = len(self.ligand_atomic_numbers)
        if any(
            first < 0 or second >= ligand_count or first >= second
            for first, second, _order in bond_rows
        ) or len({(first, second) for first, second, _order in bond_rows}) != len(
            bond_rows
        ):
            raise ChemistryAwarePoseValidityV2Error(
                "ligand bond rows contain invalid or duplicate indices"
            )
        if any(
            min(row) < 0 or max(row) >= ligand_count or len(set(row)) != 3
            for row in angle_rows
        ) or len(set(angle_rows)) != len(angle_rows):
            raise ChemistryAwarePoseValidityV2Error(
                "ligand angle rows contain invalid or duplicate indices"
            )
        if any(
            min(row[:4]) < 0
            or max(row[:4]) >= ligand_count
            or len(set(row[:4])) != 4
            or row[4] not in _DECLARED_ATOM_STEREO
            for row in atom_stereo_rows
        ) or len(set(atom_stereo_rows)) != len(atom_stereo_rows):
            raise ChemistryAwarePoseValidityV2Error(
                "declared atom stereo rows are invalid or duplicated"
            )
        if any(
            min(row[:4]) < 0
            or max(row[:4]) >= ligand_count
            or len(set(row[:4])) != 4
            or row[4] not in _DECLARED_BOND_STEREO
            for row in bond_stereo_rows
        ) or len(set(bond_stereo_rows)) != len(bond_stereo_rows):
            raise ChemistryAwarePoseValidityV2Error(
                "declared bond stereo rows are invalid or duplicated"
            )
        for name in ("aromatic_atom_indices", "ring_atom_indices"):
            values = getattr(self, name)
            if values != tuple(sorted(set(values))) or any(
                value < 0 or value >= ligand_count for value in values
            ):
                raise ChemistryAwarePoseValidityV2Error(
                    f"{name} must be unique sorted ligand indices"
                )
        blockers = tuple(str(value or "").strip() for value in self.context_blockers)
        if (
            any(not value for value in blockers)
            or len(blockers) != len(set(blockers))
            or not set(CHEMISTRY_AWARE_POSE_VALIDITY_V2_BLOCKERS).issubset(blockers)
        ):
            raise ChemistryAwarePoseValidityV2Error(
                "context blockers must be unique non-empty strings"
            )
        object.__setattr__(self, "context_blockers", blockers)
        super().__post_init__()
        ligand_count = int(self.reference_coordinates.shape[0])
        receptor_count = int(self.receptor_coordinates.shape[0])
        if (
            len(self.ligand_atomic_numbers) != ligand_count
            or len(self.ligand_formal_charges) != ligand_count
            or len(self.receptor_atomic_numbers) != receptor_count
            or len(self.receptor_formal_charges) != receptor_count
        ):
            raise ChemistryAwarePoseValidityV2Error(
                "validity atom identities and coordinates disagree"
            )
        if tuple((first, second) for first, second, _order in bond_rows) != (
            self.bond_pairs
        ):
            raise ChemistryAwarePoseValidityV2Error(
                "validity bond rows disagree with the base context"
            )

    @classmethod
    def from_prepared_systems(
        cls,
        receptor: AllAtomSystem,
        ligand: AllAtomSystem,
        ligand_preparation_source: AllAtomSystem,
        problem: DockingProblemIdentity,
        *,
        pocket_center: Sequence[float] | torch.Tensor,
        pocket_radius_angstrom: float,
        chemistry_config: ChemistryAwarePoseValidityV2Config | None = None,
    ) -> "ChemistryAwarePoseValidityV2Context":
        active = (
            ChemistryAwarePoseValidityV2Config()
            if chemistry_config is None
            else chemistry_config
        )
        if not isinstance(active, ChemistryAwarePoseValidityV2Config):
            raise ChemistryAwarePoseValidityV2Error(
                "chemistry_config must be ChemistryAwarePoseValidityV2Config"
            )
        if not isinstance(problem, DockingProblemIdentity) or not problem.bound:
            raise ChemistryAwarePoseValidityV2Error(
                "a bound docking problem identity is required"
            )
        for system, role in (
            (receptor, "receptor"),
            (ligand, "ligand"),
            (ligand_preparation_source, "ligand preparation source"),
        ):
            if not isinstance(system, AllAtomSystem):
                raise TypeError(f"{role} must be AllAtomSystem")
            require_valid_all_atom_system(system)
            if system.model_count != 1 or system.coordinate_unit != "angstrom":
                raise ChemistryAwarePoseValidityV2Error(
                    f"{role} must contain one Angstrom coordinate model"
                )
            _coordinates(
                system.coordinates[0],
                name=f"{role} coordinates",
                atom_count=system.atom_count,
            )
        receptor_sha256 = canonical_system_sha256(receptor)
        ligand_sha256 = canonical_system_sha256(ligand)
        if (
            problem.receptor_system_sha256 != receptor_sha256
            or problem.ligand_system_sha256 != ligand_sha256
        ):
            raise ChemistryAwarePoseValidityV2Error(
                "validity systems do not match the docking problem identity"
            )
        source_topology_sha256 = canonical_topology_sha256(ligand_preparation_source)
        ligand_topology_sha256 = canonical_topology_sha256(ligand)
        if source_topology_sha256 != ligand_topology_sha256:
            raise ChemistryAwarePoseValidityV2Error(
                "transformed ligand topology differs from the verified preparation source"
            )
        preparation = verify_rdkit_openff_prepared_system(ligand_preparation_source)
        preparation_receipt_sha256 = _digest(
            preparation.get("receipt_sha256"),
            name="ligand_preparation_receipt_sha256",
        )
        raw_preparation_blockers = preparation.get("scientific_blockers")
        if (
            isinstance(raw_preparation_blockers, (str, bytes))
            or not isinstance(raw_preparation_blockers, Sequence)
            or any(
                not isinstance(value, str) or not value
                for value in raw_preparation_blockers
            )
        ):
            raise ChemistryAwarePoseValidityV2Error(
                "verified ligand preparation blockers are incomplete"
            )
        radius = _finite(
            pocket_radius_angstrom,
            name="pocket_radius_angstrom",
            positive=True,
        )
        if active.receptor_shell_radius_angstrom <= radius:
            raise ChemistryAwarePoseValidityV2Error(
                "receptor shell radius must exceed the pocket radius"
            )
        center = torch.as_tensor(
            pocket_center,
            dtype=torch.float64,
            device="cpu",
        ).reshape(-1)
        if center.shape != (3,) or not bool(torch.isfinite(center).all().item()):
            raise ChemistryAwarePoseValidityV2Error(
                "pocket_center must contain three finite coordinates"
            )
        receptor_coordinates = receptor.coordinates[0]
        shell_mask = (
            torch.linalg.vector_norm(
                receptor_coordinates - center,
                dim=1,
            )
            <= active.receptor_shell_radius_angstrom
        )
        shell_indices = tuple(
            int(value)
            for value in torch.nonzero(
                shell_mask,
                as_tuple=False,
            )
            .reshape(-1)
            .tolist()
        )
        if not shell_indices:
            raise ChemistryAwarePoseValidityV2Error(
                "receptor validity shell contains no atoms"
            )
        if len(shell_indices) * ligand.atom_count > (
            active.max_receptor_ligand_pair_checks
        ):
            raise ChemistryAwarePoseValidityV2Error(
                "receptor-ligand validity pair capacity exceeded"
            )
        unsupported = sorted(
            {
                atom.atomic_number
                for system in (receptor, ligand)
                for atom in system.atoms
                if atom.atomic_number not in GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM
            }
        )
        if unsupported:
            raise ChemistryAwarePoseValidityV2Error(
                f"validity systems contain unsupported atomic numbers {unsupported}"
            )
        if len(ligand.bonds) > active.max_bonds:
            raise ChemistryAwarePoseValidityV2Error(
                "ligand validity bond capacity exceeded"
            )
        if any(
            not isinstance(atom.metadata.get("is_in_ring"), bool)
            for atom in ligand.atoms
        ) or any(
            not isinstance(bond.metadata.get("is_in_ring"), bool)
            for bond in ligand.bonds
        ):
            raise ChemistryAwarePoseValidityV2Error(
                "prepared ligand must declare boolean atom and bond ring metadata"
            )
        adjacency = _adjacency(ligand)
        angle_count = sum(
            len(neighbors) * (len(neighbors) - 1) // 2 for neighbors in adjacency
        )
        if angle_count > active.max_angles:
            raise ChemistryAwarePoseValidityV2Error(
                "ligand validity angle capacity exceeded"
            )
        angle_rows = _angle_triplets(adjacency)
        if len(angle_rows) != angle_count:
            raise ChemistryAwarePoseValidityV2Error(
                "ligand validity angle materialization is inconsistent"
            )
        atom_stereo_rows = _declared_atom_stereo_rows(ligand, adjacency)
        bond_stereo_rows = _declared_bond_stereo_rows(ligand, adjacency)
        bond_pairs = tuple((bond.atom_i, bond.atom_j) for bond in ligand.bonds)
        exclusions = set(bond_pairs)
        exclusions.update(
            (min(first, second), max(first, second))
            for first, _center, second in angle_rows
        )
        ligand_pair_count = ligand.atom_count * (ligand.atom_count - 1) // 2
        if ligand_pair_count > active.max_ligand_pair_checks:
            raise ChemistryAwarePoseValidityV2Error(
                "ligand validity pair capacity exceeded"
            )
        base_config = PoseValidityConfig(
            bond_length_tolerance_angstrom=(active.maximum_bond_length_delta_angstrom),
            ligand_self_clash_angstrom=0.75,
            receptor_ligand_clash_angstrom=0.8,
            rotation_tolerance=active.rotation_tolerance,
            chirality_volume_tolerance=active.chirality_volume_tolerance,
            pocket_radius_angstrom=radius,
            max_pair_checks=active.max_ligand_pair_checks,
            max_cross_checks=active.max_receptor_ligand_pair_checks,
        )
        context_blockers = tuple(
            dict.fromkeys(
                (
                    *CHEMISTRY_AWARE_POSE_VALIDITY_V2_BLOCKERS,
                    *tuple(str(value) for value in raw_preparation_blockers),
                )
            )
        )
        return cls(
            problem_fingerprint_sha256=problem.fingerprint_sha256,
            reference_coordinates=ligand.coordinates[0],
            bond_pairs=bond_pairs,
            excluded_nonbonded_pairs=tuple(sorted(exclusions)),
            receptor_coordinates=receptor_coordinates.index_select(
                0,
                torch.tensor(shell_indices, dtype=torch.long),
            ),
            pocket_center=center,
            chirality_centers=tuple(row[:4] for row in atom_stereo_rows),
            config=base_config,
            chemistry_config=active,
            receptor_system_sha256=receptor_sha256,
            ligand_system_sha256=ligand_sha256,
            ligand_topology_sha256=ligand_topology_sha256,
            ligand_preparation_receipt_sha256=preparation_receipt_sha256,
            receptor_atomic_numbers=tuple(
                receptor.atoms[index].atomic_number for index in shell_indices
            ),
            ligand_atomic_numbers=tuple(atom.atomic_number for atom in ligand.atoms),
            receptor_formal_charges=tuple(
                receptor.atoms[index].formal_charge for index in shell_indices
            ),
            ligand_formal_charges=tuple(atom.formal_charge for atom in ligand.atoms),
            ligand_bond_rows=tuple(
                (bond.atom_i, bond.atom_j, bond.order) for bond in ligand.bonds
            ),
            angle_triplets=angle_rows,
            declared_atom_stereo_rows=atom_stereo_rows,
            declared_bond_stereo_rows=bond_stereo_rows,
            aromatic_atom_indices=tuple(
                atom.index for atom in ligand.atoms if atom.aromatic
            ),
            ring_atom_indices=tuple(
                atom.index for atom in ligand.atoms if bool(atom.metadata["is_in_ring"])
            ),
            context_blockers=context_blockers,
        )

    def to_dict(self) -> dict[str, object]:
        payload = super().to_dict()
        payload.update(
            {
                "schema_id": CHEMISTRY_AWARE_POSE_VALIDITY_V2_CONTEXT_SCHEMA_ID,
                "chemistry_config": self.chemistry_config.to_dict(),
                "chemistry_config_fingerprint_sha256": (
                    self.chemistry_config.fingerprint_sha256
                ),
                "profile_sha256": (CHEMISTRY_AWARE_POSE_VALIDITY_V2_PROFILE_SHA256),
                "receptor_system_sha256": self.receptor_system_sha256,
                "ligand_system_sha256": self.ligand_system_sha256,
                "ligand_topology_sha256": self.ligand_topology_sha256,
                "ligand_preparation_receipt_sha256": (
                    self.ligand_preparation_receipt_sha256
                ),
                "receptor_atomic_numbers": list(self.receptor_atomic_numbers),
                "ligand_atomic_numbers": list(self.ligand_atomic_numbers),
                "receptor_formal_charges": list(self.receptor_formal_charges),
                "ligand_formal_charges": list(self.ligand_formal_charges),
                "ligand_bond_rows": [
                    {
                        "atom_i": first,
                        "atom_j": second,
                        "order_hex": order.hex(),
                    }
                    for first, second, order in self.ligand_bond_rows
                ],
                "angle_triplets": [list(row) for row in self.angle_triplets],
                "declared_atom_stereo_rows": [
                    {
                        "center": row[0],
                        "neighbors": list(row[1:4]),
                        "label": row[4],
                    }
                    for row in self.declared_atom_stereo_rows
                ],
                "declared_bond_stereo_rows": [
                    {
                        "indices": list(row[:4]),
                        "label": row[4],
                    }
                    for row in self.declared_bond_stereo_rows
                ],
                "aromatic_atom_indices": list(self.aromatic_atom_indices),
                "ring_atom_indices": list(self.ring_atom_indices),
                "context_blockers": list(self.context_blockers),
                "partial_charges_used": False,
                "force_field_parameters_used": False,
                "scientifically_validated": False,
                "claim_safe": False,
            }
        )
        return payload

    def evaluate(
        self,
        proposal: DockingProposal,
    ) -> ChemistryAwarePoseValidityV2Result:
        base = super().evaluate(proposal)
        self.assert_integrity()
        proposal.assert_integrity()
        reference = _coordinates(
            self.reference_coordinates,
            name="reference ligand coordinates",
            atom_count=len(self.ligand_atomic_numbers),
        )
        pose = _coordinates(
            proposal.coordinates,
            name="proposal coordinates",
            atom_count=len(self.ligand_atomic_numbers),
        )
        bond_deltas: list[float] = []
        for first, second, _order in self.ligand_bond_rows:
            reference_length = float(
                torch.linalg.vector_norm(reference[first] - reference[second]).item()
            )
            pose_length = float(
                torch.linalg.vector_norm(pose[first] - pose[second]).item()
            )
            bond_deltas.append(abs(pose_length - reference_length))
        maximum_bond_delta = max(bond_deltas, default=0.0)
        reference_angles, reference_angle_collapsed = _angles(
            reference,
            self.angle_triplets,
        )
        pose_angles, pose_angle_collapsed = _angles(
            pose,
            self.angle_triplets,
        )
        maximum_angle_delta_degrees = (
            180.0
            if reference_angle_collapsed or pose_angle_collapsed
            else float(
                torch.rad2deg(
                    torch.max(torch.abs(pose_angles - reference_angles))
                ).item()
            )
            if pose_angles.numel()
            else 0.0
        )
        reference_dihedrals, reference_dihedral_collapsed = _dihedrals(
            reference,
            self.declared_bond_stereo_rows,
        )
        pose_dihedrals, pose_dihedral_collapsed = _dihedrals(
            pose,
            self.declared_bond_stereo_rows,
        )
        if reference_dihedral_collapsed or pose_dihedral_collapsed:
            maximum_double_bond_delta_degrees = 180.0
        elif pose_dihedrals.numel():
            delta = torch.atan2(
                torch.sin(pose_dihedrals - reference_dihedrals),
                torch.cos(pose_dihedrals - reference_dihedrals),
            )
            maximum_double_bond_delta_degrees = float(
                torch.rad2deg(torch.max(torch.abs(delta))).item()
            )
        else:
            maximum_double_bond_delta_degrees = 0.0

        exclusion_set = set(self.excluded_nonbonded_pairs)
        internal_pairs = tuple(
            (first, second)
            for first in range(len(self.ligand_atomic_numbers))
            for second in range(first + 1, len(self.ligand_atomic_numbers))
            if (first, second) not in exclusion_set
        )
        if internal_pairs:
            internal_indices = torch.tensor(internal_pairs, dtype=torch.long)
            internal_distances = torch.linalg.vector_norm(
                pose.index_select(0, internal_indices[:, 0])
                - pose.index_select(0, internal_indices[:, 1]),
                dim=1,
            )
            internal_radius_sums = torch.tensor(
                [
                    GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[
                        self.ligand_atomic_numbers[first]
                    ]
                    + GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[
                        self.ligand_atomic_numbers[second]
                    ]
                    for first, second in internal_pairs
                ],
                dtype=torch.float64,
            )
        else:
            internal_distances = torch.empty(0, dtype=torch.float64)
            internal_radius_sums = torch.empty(0, dtype=torch.float64)
        (
            minimum_internal_ratio,
            internal_penetration_count,
            maximum_internal_overlap,
        ) = _contact_observation(
            internal_distances,
            internal_radius_sums,
            minimum_scale=self.chemistry_config.minimum_ligand_self_contact_scale,
        )
        receptor = _coordinates(
            self.receptor_coordinates,
            name="receptor shell coordinates",
            atom_count=len(self.receptor_atomic_numbers),
        )
        cross_distances = torch.linalg.vector_norm(
            receptor[:, None, :] - pose[None, :, :],
            dim=2,
        ).reshape(-1)
        receptor_radii = torch.tensor(
            [
                GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[value]
                for value in self.receptor_atomic_numbers
            ],
            dtype=torch.float64,
        )
        ligand_radii = torch.tensor(
            [
                GEOMETRY_DIAGNOSTIC_RADII_ANGSTROM[value]
                for value in self.ligand_atomic_numbers
            ],
            dtype=torch.float64,
        )
        cross_radius_sums = (receptor_radii[:, None] + ligand_radii[None, :]).reshape(
            -1
        )
        (
            minimum_cross_ratio,
            cross_penetration_count,
            maximum_cross_overlap,
        ) = _contact_observation(
            cross_distances,
            cross_radius_sums,
            minimum_scale=(self.chemistry_config.minimum_receptor_ligand_contact_scale),
        )
        formal_charge_in_scope = all(
            abs(value) <= self.chemistry_config.maximum_absolute_formal_charge
            for value in (*self.receptor_formal_charges, *self.ligand_formal_charges)
        )
        checks = dict(base.checks)
        checks.update(
            {
                "verified_ligand_preparation_bound": True,
                "supported_atomic_number_scope": True,
                "formal_charge_within_supported_range": formal_charge_in_scope,
                "reference_relative_bond_geometry_within_limit": (
                    maximum_bond_delta
                    <= self.chemistry_config.maximum_bond_length_delta_angstrom
                ),
                "reference_relative_angle_geometry_within_limit": (
                    maximum_angle_delta_degrees
                    <= self.chemistry_config.maximum_angle_delta_degrees
                ),
                "declared_double_bond_stereo_preserved": (
                    maximum_double_bond_delta_degrees
                    <= self.chemistry_config.maximum_double_bond_dihedral_delta_degrees
                ),
                "ligand_element_scaled_self_clash_free": (
                    internal_penetration_count == 0
                ),
                "receptor_ligand_element_scaled_penetration_free": (
                    cross_penetration_count == 0
                ),
            }
        )
        evaluated = dict(base.evaluated_checks)
        evaluated.update({name: True for name in checks if name not in evaluated})
        measurements: dict[str, float | int] = dict(base.measurements)
        measurements.update(
            {
                "maximum_reference_relative_bond_delta_angstrom": (maximum_bond_delta),
                "maximum_reference_relative_angle_delta_degrees": (
                    maximum_angle_delta_degrees
                ),
                "maximum_declared_double_bond_dihedral_delta_degrees": (
                    maximum_double_bond_delta_degrees
                ),
                "declared_atom_stereo_count": len(self.declared_atom_stereo_rows),
                "declared_bond_stereo_count": len(self.declared_bond_stereo_rows),
                "aromatic_atom_count": len(self.aromatic_atom_indices),
                "ring_atom_count": len(self.ring_atom_indices),
                "ligand_element_scaled_pair_count": len(internal_pairs),
                "ligand_element_scaled_penetration_count": (internal_penetration_count),
                "ligand_minimum_element_contact_ratio": minimum_internal_ratio,
                "ligand_maximum_element_overlap_angstrom": (maximum_internal_overlap),
                "receptor_ligand_element_scaled_pair_count": int(
                    cross_distances.numel()
                ),
                "receptor_ligand_element_scaled_penetration_count": (
                    cross_penetration_count
                ),
                "receptor_ligand_minimum_element_contact_ratio": (minimum_cross_ratio),
                "receptor_ligand_maximum_element_overlap_angstrom": (
                    maximum_cross_overlap
                ),
                "receptor_net_formal_charge_e": sum(self.receptor_formal_charges),
                "ligand_net_formal_charge_e": sum(self.ligand_formal_charges),
            }
        )
        blockers = list(dict.fromkeys((*base.blockers, *self.context_blockers)))
        failure_blockers = {
            "formal_charge_within_supported_range": (
                "formal_charge_outside_validity_v2_profile"
            ),
            "reference_relative_bond_geometry_within_limit": (
                "reference_relative_bond_geometry_failed"
            ),
            "reference_relative_angle_geometry_within_limit": (
                "reference_relative_angle_geometry_failed"
            ),
            "declared_chirality_preserved": ("declared_atom_stereo_geometry_failed"),
            "declared_double_bond_stereo_preserved": (
                "declared_double_bond_stereo_geometry_failed"
            ),
            "ligand_element_scaled_self_clash_free": (
                "ligand_element_scaled_self_clash_detected"
            ),
            "receptor_ligand_element_scaled_penetration_free": (
                "receptor_ligand_element_scaled_penetration_detected"
            ),
        }
        for check_name, blocker in failure_blockers.items():
            if evaluated.get(check_name) is True and checks.get(check_name) is False:
                blockers.append(blocker)
        reasons = dict(base.not_evaluated_reasons)
        complete = all(evaluated.values())
        valid_within_scope = all(
            checks[name] for name, was_evaluated in evaluated.items() if was_evaluated
        )
        result = ChemistryAwarePoseValidityV2Result(
            checks=MappingProxyType(checks),
            evaluated_checks=MappingProxyType(evaluated),
            complete=complete,
            valid_within_evaluated_scope=valid_within_scope,
            measurements=MappingProxyType(measurements),
            blockers=tuple(dict.fromkeys(blockers)),
            not_evaluated_reasons=MappingProxyType(reasons),
            validity_context_fingerprint_sha256=self.fingerprint_sha256,
            problem_fingerprint_sha256=self.problem_fingerprint_sha256,
            proposal_fingerprint_sha256=proposal.fingerprint_sha256,
            receptor_system_sha256=self.receptor_system_sha256,
            ligand_system_sha256=self.ligand_system_sha256,
            ligand_preparation_receipt_sha256=(self.ligand_preparation_receipt_sha256),
            validity_config_fingerprint_sha256=(
                self.chemistry_config.fingerprint_sha256
            ),
        )
        self.assert_integrity()
        proposal.assert_integrity()
        return result


__all__ = [
    "CHEMISTRY_AWARE_POSE_VALIDITY_V2_BLOCKERS",
    "CHEMISTRY_AWARE_POSE_VALIDITY_V2_CONFIG_SCHEMA_ID",
    "CHEMISTRY_AWARE_POSE_VALIDITY_V2_CONTEXT_SCHEMA_ID",
    "CHEMISTRY_AWARE_POSE_VALIDITY_V2_PROFILE_ID",
    "CHEMISTRY_AWARE_POSE_VALIDITY_V2_PROFILE_SHA256",
    "CHEMISTRY_AWARE_POSE_VALIDITY_V2_RESULT_SCHEMA_ID",
    "ChemistryAwarePoseValidityV2Config",
    "ChemistryAwarePoseValidityV2Context",
    "ChemistryAwarePoseValidityV2Error",
    "ChemistryAwarePoseValidityV2Result",
    "chemistry_aware_pose_validity_v2_profile_document",
]
