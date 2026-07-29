"""Element-aware severe-overlap validity for authenticated docking.

The existing pose-validity contract deliberately uses simple absolute distance
thresholds. This module adds a stricter, separately identified contact layer:

* ligand and receptor elements are bound to the validity context;
* supported van-der-Waals radii are frozen in the policy receipt;
* non-excluded ligand pairs are checked by radius-normalized distance;
* receptor contacts are enumerated through a bounded pocket-local cell map;
* unsupported elements and candidate-pair overflow fail closed;
* the existing geometric validity result remains intact and every new check is
  conjunctive rather than replacing earlier checks.

The radii and overlap scale are an explicit engineering baseline. They are not a
chemically or scientifically validated interaction model, docking score, or
product qualification.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
import hashlib
import json
import math
from types import MappingProxyType

import torch

from betelgeuze_engine_v2.molecular import AllAtomSystem

from .authority import (
    AuthenticatedDockingProblem,
    PocketDefinition,
    build_authenticated_known_pocket_docking_problem,
)
from .proposals import DockingProposal
from .validity import (
    PoseValidityContext,
    PoseValidityError,
    PoseValidityResult,
)


VDW_CONTACT_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_vdw_contact_policy/1.0.0"
)
ELEMENT_AWARE_VALIDITY_CONTEXT_SCHEMA_ID = (
    "betelgeuze.engine_v2_element_aware_pose_validity_context/1.0.0"
)
ELEMENT_AWARE_AUTHORITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_element_aware_docking_authority/1.0.0"
)
VDW_CONTACT_POLICY_ID = (
    "betelgeuze.engine_v2_severe_overlap_vdw_baseline/1.0.0"
)
VDW_RADII_TABLE_ID = "bondi_alvarez_common_elements_subset/1.0.0"
SPARSE_CONTACT_ALGORITHM_ID = (
    "betelgeuze.engine_v2_pocket_local_vdw_cell_map/1.0.0"
)
MAX_ELEMENT_AWARE_LIGAND_ATOMS = 512
MAX_ELEMENT_AWARE_RECEPTOR_ATOMS = 100_000
MAX_ELEMENT_AWARE_LIGAND_PAIR_CHECKS = 2_000_000
MAX_ELEMENT_AWARE_RECEPTOR_CANDIDATE_PAIRS = 4_000_000

# Common-element subset in Å. Values are frozen software inputs, not a claim of
# universally correct chemistry or an applicability guarantee.
_DEFAULT_VDW_RADII = {
    "H": 1.20,
    "C": 1.70,
    "N": 1.55,
    "O": 1.52,
    "F": 1.47,
    "P": 1.80,
    "S": 1.80,
    "CL": 1.75,
    "BR": 1.85,
    "I": 1.98,
}


class ElementAwareValidityError(PoseValidityError):
    """Element-aware contact validity failed closed."""


class UnsupportedVdwElementError(ElementAwareValidityError):
    """The frozen validity table does not cover an observed element."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ElementAwareValidityError(
            "element-aware validity state is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _normalized_element(value: object) -> str:
    text = str(value or "").strip().upper()
    if not text or len(text) > 3 or not text.isalpha():
        raise ElementAwareValidityError("element symbol is invalid")
    return text


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ElementAwareValidityError(
            f"{name} must be an integer in [{minimum},{maximum}]"
        )
    return value


def _frozen_radii(value: Mapping[str, float]) -> Mapping[str, float]:
    normalized: dict[str, float] = {}
    for raw_element, raw_radius in value.items():
        element = _normalized_element(raw_element)
        radius = float(raw_radius)
        if not math.isfinite(radius) or not 0.5 <= radius <= 3.0:
            raise ElementAwareValidityError(
                "van-der-Waals radii must be finite and in [0.5,3.0] Å"
            )
        if element in normalized:
            raise ElementAwareValidityError(
                "van-der-Waals element is duplicated"
            )
        normalized[element] = radius
    if not normalized:
        raise ElementAwareValidityError("van-der-Waals radii table is empty")
    return MappingProxyType(dict(sorted(normalized.items())))


def _cell_key(
    coordinate: torch.Tensor,
    cell_size: float,
) -> tuple[int, int, int]:
    return tuple(
        int(math.floor(float(value) / cell_size))
        for value in coordinate.tolist()
    )


def _minimum_or_sentinel(value: float) -> float:
    return value if math.isfinite(value) else 999.0


@dataclass(frozen=True, slots=True)
class VdwContactPolicy:
    policy_id: str = VDW_CONTACT_POLICY_ID
    radii_table_id: str = VDW_RADII_TABLE_ID
    sparse_algorithm_id: str = SPARSE_CONTACT_ALGORITHM_ID
    severe_overlap_scale: float = 0.55
    cell_size_angstrom: float = 2.5
    max_ligand_pair_checks: int = 250_000
    max_receptor_candidate_pairs: int = 1_000_000
    radii_angstrom: Mapping[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_VDW_RADII)
    )
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if str(self.policy_id) != VDW_CONTACT_POLICY_ID:
            raise ElementAwareValidityError("unsupported vdW contact policy")
        if str(self.radii_table_id) != VDW_RADII_TABLE_ID:
            raise ElementAwareValidityError("unsupported vdW radii table")
        if str(self.sparse_algorithm_id) != SPARSE_CONTACT_ALGORITHM_ID:
            raise ElementAwareValidityError(
                "unsupported sparse contact algorithm"
            )
        scale = float(self.severe_overlap_scale)
        if not math.isfinite(scale) or not 0.1 <= scale <= 1.0:
            raise ElementAwareValidityError(
                "severe_overlap_scale must be finite and in [0.1,1.0]"
            )
        cell_size = float(self.cell_size_angstrom)
        if not math.isfinite(cell_size) or not 0.5 <= cell_size <= 10.0:
            raise ElementAwareValidityError(
                "cell_size_angstrom must be finite and in [0.5,10.0]"
            )
        radii = _frozen_radii(self.radii_angstrom)
        maximum_cutoff = max(radii.values()) * 2.0 * scale
        if cell_size + 1.0e-12 < maximum_cutoff:
            raise ElementAwareValidityError(
                "cell_size_angstrom must cover the maximum severe-overlap cutoff"
            )
        ligand_capacity = _exact_int(
            self.max_ligand_pair_checks,
            name="max_ligand_pair_checks",
            minimum=0,
            maximum=MAX_ELEMENT_AWARE_LIGAND_PAIR_CHECKS,
        )
        receptor_capacity = _exact_int(
            self.max_receptor_candidate_pairs,
            name="max_receptor_candidate_pairs",
            minimum=0,
            maximum=MAX_ELEMENT_AWARE_RECEPTOR_CANDIDATE_PAIRS,
        )
        object.__setattr__(self, "severe_overlap_scale", scale)
        object.__setattr__(self, "cell_size_angstrom", cell_size)
        object.__setattr__(self, "max_ligand_pair_checks", ligand_capacity)
        object.__setattr__(
            self,
            "max_receptor_candidate_pairs",
            receptor_capacity,
        )
        object.__setattr__(self, "radii_angstrom", radii)
        object.__setattr__(
            self,
            "_fingerprint_sha256",
            _sha256(self._projection()),
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": VDW_CONTACT_POLICY_SCHEMA_ID,
            "policy_id": self.policy_id,
            "radii_table_id": self.radii_table_id,
            "sparse_algorithm_id": self.sparse_algorithm_id,
            "severe_overlap_scale_binary64_hex": (
                self.severe_overlap_scale.hex()
            ),
            "cell_size_angstrom_binary64_hex": (
                self.cell_size_angstrom.hex()
            ),
            "max_ligand_pair_checks": self.max_ligand_pair_checks,
            "max_receptor_candidate_pairs": (
                self.max_receptor_candidate_pairs
            ),
            "radii_angstrom_binary64_hex": {
                element: radius.hex()
                for element, radius in self.radii_angstrom.items()
            },
            "unsupported_element_policy": "reject",
            "chemically_validated": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise ElementAwareValidityError(
                "vdW contact policy changed after construction"
            )
        return observed

    def radius(self, element: str) -> float:
        symbol = _normalized_element(element)
        try:
            return float(self.radii_angstrom[symbol])
        except KeyError as exc:
            raise UnsupportedVdwElementError(
                f"unsupported vdW element {symbol!r}"
            ) from exc

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "fingerprint_sha256": self.fingerprint_sha256,
        }


@dataclass(frozen=True)
class ElementAwarePoseValidityContext(PoseValidityContext):
    ligand_elements: tuple[str, ...] = ()
    receptor_elements: tuple[str, ...] = ()
    contact_policy: VdwContactPolicy = field(default_factory=VdwContactPolicy)

    def __post_init__(self) -> None:
        ligand = tuple(
            _normalized_element(value) for value in self.ligand_elements
        )
        receptor = tuple(
            _normalized_element(value) for value in self.receptor_elements
        )
        if not isinstance(self.contact_policy, VdwContactPolicy):
            raise ElementAwareValidityError(
                "contact_policy must be VdwContactPolicy"
            )
        if len(ligand) > MAX_ELEMENT_AWARE_LIGAND_ATOMS:
            raise ElementAwareValidityError(
                "ligand element count exceeds the hard bound"
            )
        if len(receptor) > MAX_ELEMENT_AWARE_RECEPTOR_ATOMS:
            raise ElementAwareValidityError(
                "receptor element count exceeds the hard bound"
            )
        for element in (*ligand, *receptor):
            self.contact_policy.radius(element)
        object.__setattr__(self, "ligand_elements", ligand)
        object.__setattr__(self, "receptor_elements", receptor)
        super().__post_init__()
        if len(self.ligand_elements) != int(
            self.reference_coordinates.shape[0]
        ):
            raise ElementAwareValidityError(
                "ligand elements do not match reference coordinates"
            )
        if len(self.receptor_elements) != int(
            self.receptor_coordinates.shape[0]
        ):
            raise ElementAwareValidityError(
                "receptor elements do not match receptor coordinates"
            )

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        return {
            **base,
            "schema_id": ELEMENT_AWARE_VALIDITY_CONTEXT_SCHEMA_ID,
            "ligand_elements": list(self.ligand_elements),
            "receptor_elements": list(self.receptor_elements),
            "contact_policy_sha256": (
                self.contact_policy.fingerprint_sha256
            ),
            "contact_policy": self.contact_policy.to_dict(),
            "element_inference_performed": False,
            "chemically_validated": False,
            "claim_safe": False,
        }

    def _element_ligand_contacts(
        self,
        proposal: DockingProposal,
    ) -> dict[str, float | int | bool]:
        pose = proposal.coordinates.detach().to(
            dtype=torch.float64,
            device="cpu",
        )
        exclusions = set(self.excluded_nonbonded_pairs)
        pair_capacity = self.contact_policy.max_ligand_pair_checks
        evaluated = 0
        severe = 0
        minimum_ratio = float("inf")
        minimum_distance = float("inf")
        for first in range(len(self.ligand_elements)):
            first_radius = self.contact_policy.radius(
                self.ligand_elements[first]
            )
            for second in range(first + 1, len(self.ligand_elements)):
                if (first, second) in exclusions:
                    continue
                evaluated += 1
                if evaluated > pair_capacity:
                    raise ElementAwareValidityError(
                        "element-aware ligand pair capacity exceeded"
                    )
                second_radius = self.contact_policy.radius(
                    self.ligand_elements[second]
                )
                distance = float(
                    torch.linalg.vector_norm(
                        pose[first] - pose[second]
                    ).item()
                )
                ratio = distance / (first_radius + second_radius)
                minimum_distance = min(minimum_distance, distance)
                minimum_ratio = min(minimum_ratio, ratio)
                if ratio < self.contact_policy.severe_overlap_scale:
                    severe += 1
        return {
            "valid": severe == 0,
            "evaluated_pair_count": evaluated,
            "severe_overlap_count": severe,
            "minimum_distance_angstrom": (
                _minimum_or_sentinel(minimum_distance)
            ),
            "minimum_vdw_distance_ratio": (
                _minimum_or_sentinel(minimum_ratio)
            ),
        }

    def _element_receptor_contacts(
        self,
        proposal: DockingProposal,
    ) -> dict[str, float | int | bool]:
        receptor = self.receptor_coordinates.detach().to(
            dtype=torch.float64,
            device="cpu",
        )
        pose = proposal.coordinates.detach().to(
            dtype=torch.float64,
            device="cpu",
        )
        cell_size = self.contact_policy.cell_size_angstrom
        cells: dict[tuple[int, int, int], list[int]] = defaultdict(list)
        for receptor_index in range(len(self.receptor_elements)):
            cells[_cell_key(receptor[receptor_index], cell_size)].append(
                receptor_index
            )
        evaluated = 0
        severe = 0
        minimum_ratio = float("inf")
        minimum_distance = float("inf")
        for ligand_index, ligand_element in enumerate(self.ligand_elements):
            ligand_radius = self.contact_policy.radius(ligand_element)
            center = _cell_key(pose[ligand_index], cell_size)
            for offset_x in (-1, 0, 1):
                for offset_y in (-1, 0, 1):
                    for offset_z in (-1, 0, 1):
                        key = (
                            center[0] + offset_x,
                            center[1] + offset_y,
                            center[2] + offset_z,
                        )
                        for receptor_index in cells.get(key, ()):
                            evaluated += 1
                            if (
                                evaluated
                                > self.contact_policy.max_receptor_candidate_pairs
                            ):
                                raise ElementAwareValidityError(
                                    "element-aware receptor candidate-pair capacity exceeded"
                                )
                            receptor_radius = self.contact_policy.radius(
                                self.receptor_elements[receptor_index]
                            )
                            distance = float(
                                torch.linalg.vector_norm(
                                    pose[ligand_index]
                                    - receptor[receptor_index]
                                ).item()
                            )
                            ratio = distance / (
                                ligand_radius + receptor_radius
                            )
                            minimum_distance = min(
                                minimum_distance,
                                distance,
                            )
                            minimum_ratio = min(minimum_ratio, ratio)
                            if (
                                ratio
                                < self.contact_policy.severe_overlap_scale
                            ):
                                severe += 1
        return {
            "valid": severe == 0,
            "evaluated_candidate_pair_count": evaluated,
            "full_cartesian_pair_count": (
                len(self.ligand_elements) * len(self.receptor_elements)
            ),
            "occupied_receptor_cell_count": len(cells),
            "severe_overlap_count": severe,
            "minimum_distance_angstrom": (
                _minimum_or_sentinel(minimum_distance)
            ),
            "minimum_vdw_distance_ratio": (
                _minimum_or_sentinel(minimum_ratio)
            ),
        }

    def evaluate(self, proposal: DockingProposal) -> PoseValidityResult:
        self.assert_integrity()
        base = super().evaluate(proposal)
        ligand = self._element_ligand_contacts(proposal)
        receptor = self._element_receptor_contacts(proposal)
        checks = dict(base.checks)
        evaluated_checks = dict(base.evaluated_checks)
        measurements = dict(base.measurements)
        blockers = list(base.blockers)
        not_evaluated = dict(base.not_evaluated_reasons)
        checks["element_vdw_ligand_overlap_free"] = bool(ligand["valid"])
        checks["element_vdw_receptor_overlap_free"] = bool(
            receptor["valid"]
        )
        evaluated_checks["element_vdw_ligand_overlap_free"] = True
        evaluated_checks["element_vdw_receptor_overlap_free"] = True
        measurements.update(
            {
                "element_vdw_ligand_pair_count": int(
                    ligand["evaluated_pair_count"]
                ),
                "element_vdw_ligand_severe_overlap_count": int(
                    ligand["severe_overlap_count"]
                ),
                "element_vdw_ligand_minimum_distance_angstrom": float(
                    ligand["minimum_distance_angstrom"]
                ),
                "element_vdw_ligand_minimum_ratio": float(
                    ligand["minimum_vdw_distance_ratio"]
                ),
                "element_vdw_receptor_candidate_pair_count": int(
                    receptor["evaluated_candidate_pair_count"]
                ),
                "element_vdw_receptor_full_cartesian_pair_count": int(
                    receptor["full_cartesian_pair_count"]
                ),
                "element_vdw_receptor_cell_count": int(
                    receptor["occupied_receptor_cell_count"]
                ),
                "element_vdw_receptor_severe_overlap_count": int(
                    receptor["severe_overlap_count"]
                ),
                "element_vdw_receptor_minimum_distance_angstrom": float(
                    receptor["minimum_distance_angstrom"]
                ),
                "element_vdw_receptor_minimum_ratio": float(
                    receptor["minimum_vdw_distance_ratio"]
                ),
            }
        )
        if not checks["element_vdw_ligand_overlap_free"]:
            blockers.append(
                "element_vdw_ligand_severe_overlap_detected"
            )
        if not checks["element_vdw_receptor_overlap_free"]:
            blockers.append(
                "element_vdw_receptor_severe_overlap_detected"
            )
        complete = bool(base.complete and all(evaluated_checks.values()))
        valid = bool(
            base.valid_within_evaluated_scope
            and checks["element_vdw_ligand_overlap_free"]
            and checks["element_vdw_receptor_overlap_free"]
        )
        proposal.assert_integrity()
        self.assert_integrity()
        return PoseValidityResult(
            checks=checks,
            evaluated_checks=evaluated_checks,
            complete=complete,
            valid_within_evaluated_scope=valid,
            measurements=measurements,
            blockers=tuple(blockers),
            not_evaluated_reasons=not_evaluated,
        )


def build_element_aware_authenticated_known_pocket_docking_problem(
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
    pocket: PocketDefinition,
    *,
    receptor_model_index: int = 0,
    ligand_model_index: int = 0,
    receptor_margin_angstrom: float = 4.0,
    contact_policy: VdwContactPolicy | None = None,
) -> AuthenticatedDockingProblem:
    authority = build_authenticated_known_pocket_docking_problem(
        receptor_system,
        ligand_system,
        pocket,
        receptor_model_index=receptor_model_index,
        ligand_model_index=ligand_model_index,
        receptor_margin_angstrom=receptor_margin_angstrom,
    )
    policy = contact_policy or VdwContactPolicy()
    if not isinstance(policy, VdwContactPolicy):
        raise TypeError("contact_policy must be VdwContactPolicy")
    base = authority.validity_context
    context = ElementAwarePoseValidityContext(
        problem_fingerprint_sha256=base.problem_fingerprint_sha256,
        reference_coordinates=base.reference_coordinates,
        bond_pairs=base.bond_pairs,
        excluded_nonbonded_pairs=base.excluded_nonbonded_pairs,
        receptor_coordinates=base.receptor_coordinates,
        pocket_center=base.pocket_center,
        chirality_centers=base.chirality_centers,
        config=base.config,
        ligand_elements=tuple(atom.element for atom in ligand_system.atoms),
        receptor_elements=tuple(
            receptor_system.atoms[index].element
            for index in authority.receptor_atom_indices
        ),
        contact_policy=policy,
    )
    enhanced = replace(authority, validity_context=context)
    enhanced.input_receipt_sha256
    return enhanced


def element_aware_authority_document(
    authority: AuthenticatedDockingProblem,
) -> dict[str, object]:
    if not isinstance(
        authority.validity_context,
        ElementAwarePoseValidityContext,
    ):
        raise ElementAwareValidityError(
            "authority does not use element-aware validity"
        )
    projection = {
        "schema_id": ELEMENT_AWARE_AUTHORITY_SCHEMA_ID,
        "authenticated_input_receipt_sha256": (
            authority.input_receipt_sha256
        ),
        "validity_context_fingerprint_sha256": (
            authority.validity_context.fingerprint_sha256
        ),
        "contact_policy_sha256": (
            authority.validity_context.contact_policy.fingerprint_sha256
        ),
        "supported_elements": sorted(
            authority.validity_context.contact_policy.radii_angstrom
        ),
        "receptor_contact_algorithm": SPARSE_CONTACT_ALGORITHM_ID,
        "element_inference_performed": False,
        "chemically_validated": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    projection["document_sha256"] = _sha256(projection)
    return projection


__all__ = [
    "ELEMENT_AWARE_AUTHORITY_SCHEMA_ID",
    "ELEMENT_AWARE_VALIDITY_CONTEXT_SCHEMA_ID",
    "MAX_ELEMENT_AWARE_LIGAND_ATOMS",
    "MAX_ELEMENT_AWARE_LIGAND_PAIR_CHECKS",
    "MAX_ELEMENT_AWARE_RECEPTOR_ATOMS",
    "MAX_ELEMENT_AWARE_RECEPTOR_CANDIDATE_PAIRS",
    "SPARSE_CONTACT_ALGORITHM_ID",
    "VDW_CONTACT_POLICY_ID",
    "VDW_CONTACT_POLICY_SCHEMA_ID",
    "VDW_RADII_TABLE_ID",
    "ElementAwarePoseValidityContext",
    "ElementAwareValidityError",
    "UnsupportedVdwElementError",
    "VdwContactPolicy",
    "build_element_aware_authenticated_known_pocket_docking_problem",
    "element_aware_authority_document",
]
