"""Deterministic chemistry-aware, term-decomposed docking scorer v1.

The scorer is a bounded uncalibrated pose-ordering contract. It requires
authenticated source systems with complete explicit partial charges and keeps
all eight requested terms separate. It is not an affinity/free-energy model or
scientific validation claim.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from types import MappingProxyType

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    require_valid_all_atom_system,
)

from .authority import AuthenticatedDockingProblem, DockingAuthorityError
from .contact_validity import ElementAwarePoseValidityContext
from .guided_placement import (
    GuidedPlacementContext,
    GuidedPlacementSearchResult,
    run_authenticated_guided_placement_search,
)
from .proposals import DockingBudget, DockingProposal
from .scoring import (
    DockingScoreDescriptor,
    ScoreDirection,
    component_contract_fingerprint,
)
from .search import DockingSearchRow


SCORER_V1_CONTEXT_SCHEMA_ID = "betelgeuze.engine_v2_scorer_v1_context/1.0.0"
SCORER_V1_CONFIG_SCHEMA_ID = "betelgeuze.engine_v2_scorer_v1_config/1.0.0"
SCORER_V1_TERMS_SCHEMA_ID = "betelgeuze.engine_v2_scorer_v1_terms/1.0.0"
SCORER_V1_TERM_ROW_SCHEMA_ID = "betelgeuze.engine_v2_scorer_v1_search_term_row/1.0.0"
SCORER_V1_SEARCH_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_scorer_v1_guided_search_result/1.0.0"
)
SCORER_V1_ID = "betelgeuze.engine_v2_chemistry_pose_scorer"
SCORER_V1_VERSION = "1.0.0"
SCORER_V1_SCORE_ID = f"{SCORER_V1_ID}/{SCORER_V1_VERSION}"
SCORER_V1_ALGORITHM_ID = (
    "sparse_typed_lj_charge_hbond_hydrophobic_geometry_torsion_strain/1.0.0"
)
SCORER_V1_APPLICABILITY_DOMAIN_ID = (
    "authenticated_known_pocket_complete_explicit_partial_charge_v1"
)
MAX_SCORER_V1_RECEPTOR_BONDS_SCANNED = 1_000_000
MAX_SCORER_V1_RECEPTOR_CANDIDATE_PAIRS = 4_000_000
MAX_SCORER_V1_LIGAND_PAIR_CHECKS = 250_000
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_POLAR_ELEMENTS = frozenset({"N", "O", "S"})
_HYDROPHOBIC_ELEMENTS = frozenset({"C", "S", "F", "Cl", "Br", "I"})
_EPSILON_BY_ELEMENT = MappingProxyType(
    {
        "H": 0.02,
        "C": 0.12,
        "N": 0.17,
        "O": 0.20,
        "F": 0.06,
        "P": 0.20,
        "S": 0.25,
        "Cl": 0.15,
        "Br": 0.18,
        "I": 0.22,
    }
)


class ScorerV1Error(DockingAuthorityError):
    """Scorer v1 cannot satisfy its bounded chemistry contract."""


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
        raise ScorerV1Error("scorer v1 state is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    text = str(value or "").strip().lower()
    if _SHA256_RE.fullmatch(text) is None:
        raise ScorerV1Error(f"{name} must be a lowercase SHA-256")
    return text


def _finite(value: object, *, name: str, minimum: float, maximum: float) -> float:
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ScorerV1Error(f"{name} must be finite in [{minimum},{maximum}]")
    return result


def _exact_int(value: object, *, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ScorerV1Error(f"{name} must be an integer in [{minimum},{maximum}]")
    return value


def _float_hex(value: float) -> str:
    if not math.isfinite(value):
        raise ScorerV1Error("score term is not finite")
    return value.hex()


def _adjacency(system: AllAtomSystem) -> tuple[tuple[int, ...], ...]:
    rows = [set() for _ in range(system.atom_count)]
    for bond in system.bonds:
        first, second = int(bond.atom_i), int(bond.atom_j)
        rows[first].add(second)
        rows[second].add(first)
    return tuple(tuple(sorted(row)) for row in rows)


def _cell_key(coordinate: torch.Tensor, cell_size: float) -> tuple[int, int, int]:
    return tuple(
        int(math.floor(float(value))) for value in (coordinate / cell_size).tolist()
    )


def _atom_type(element: str, aromatic: bool, charge: int) -> str:
    charge_class = "positive" if charge > 0 else "negative" if charge < 0 else "neutral"
    geometry = "aromatic" if aromatic else "aliphatic"
    return f"{element}:{geometry}:{charge_class}"


def _complete_charges(system: AllAtomSystem) -> tuple[float, ...]:
    result = []
    for atom in system.atoms:
        if atom.partial_charge_e is None or not math.isfinite(
            float(atom.partial_charge_e)
        ):
            raise ScorerV1Error("scorer v1 requires complete finite partial charges")
        result.append(float(atom.partial_charge_e))
    if not math.isclose(
        sum(result),
        float(sum(atom.formal_charge for atom in system.atoms)),
        abs_tol=1.0e-4,
    ):
        raise ScorerV1Error("partial charges do not conserve the formal total charge")
    return tuple(result)


def _dihedral_angle(
    coordinates: torch.Tensor,
    atoms: tuple[int, int, int, int],
) -> float:
    first, second, third, fourth = (coordinates[index] for index in atoms)
    middle = third - second
    middle_norm = float(torch.linalg.vector_norm(middle).item())
    if middle_norm <= 1.0e-12:
        raise ScorerV1Error("rotor geometry contains a degenerate central bond")
    axis = middle / middle_norm
    left = first - second
    right = fourth - third
    left = left - torch.dot(left, axis) * axis
    right = right - torch.dot(right, axis) * axis
    left_norm = float(torch.linalg.vector_norm(left).item())
    right_norm = float(torch.linalg.vector_norm(right).item())
    if min(left_norm, right_norm) <= 1.0e-12:
        raise ScorerV1Error("rotor geometry lacks a stable dihedral anchor")
    left = left / left_norm
    right = right / right_norm
    sine = float(torch.dot(torch.cross(left, right, dim=0), axis).item())
    cosine = float(torch.dot(left, right).item())
    return math.atan2(sine, cosine)


def _features(
    system: AllAtomSystem,
    allowed: set[int],
) -> tuple[tuple[tuple[int, int], ...], tuple[int, ...], tuple[int, ...]]:
    adjacency = _adjacency(system)
    bonds = {
        tuple(sorted((int(bond.atom_i), int(bond.atom_j)))): bond
        for bond in system.bonds
    }

    def restricted_nitrogen(index: int) -> bool:
        if system.atoms[index].element != "N":
            return False
        for center in adjacency[index]:
            center_element = system.atoms[center].element
            if center_element not in {"C", "S"}:
                continue
            oxygen_equivalents = sum(
                system.atoms[other].element == "O"
                and (
                    math.isclose(
                        float(bonds[tuple(sorted((center, other)))].order),
                        2.0,
                        abs_tol=1.0e-6,
                    )
                    or (
                        center_element == "S"
                        and system.atoms[center].formal_charge > 0
                        and system.atoms[other].formal_charge < 0
                    )
                )
                for other in adjacency[center]
                if other != index
            )
            if center_element == "C" and oxygen_equivalents >= 1:
                return True
            if center_element == "S" and oxygen_equivalents >= 2:
                return True
        return False

    donors: list[tuple[int, int]] = []
    acceptors: list[int] = []
    hydrophobic: list[int] = []
    for index in sorted(allowed):
        atom = system.atoms[index]
        element = atom.element
        attached_hydrogens = tuple(
            neighbor
            for neighbor in adjacency[index]
            if neighbor in allowed and system.atoms[neighbor].element == "H"
        )
        if element in _POLAR_ELEMENTS:
            donors.extend((index, hydrogen) for hydrogen in attached_hydrogens)
            pyrrolic = element == "N" and atom.aromatic and bool(attached_hydrogens)
            if (
                atom.formal_charge <= 0
                and not pyrrolic
                and not restricted_nitrogen(index)
            ):
                acceptors.append(index)
        if (
            element in _HYDROPHOBIC_ELEMENTS
            and atom.formal_charge == 0
            and abs(float(atom.partial_charge_e or 0.0)) <= 0.35
        ):
            hydrophobic.append(index)
    return tuple(donors), tuple(acceptors), tuple(hydrophobic)


@dataclass(frozen=True, slots=True)
class ScorerV1Config:
    typed_vdw_weight: float = 1.0
    electrostatics_weight: float = 0.35
    directional_hbond_weight: float = 1.5
    hydrophobic_contact_weight: float = 0.6
    desolvation_weight: float = 0.4
    torsion_energy_weight: float = 0.15
    ligand_strain_weight: float = 0.5
    weak_pocket_prior_weight: float = 0.05
    electrostatic_dielectric: float = 4.0
    pair_cutoff_angstrom: float = 8.0
    hbond_distance_max_angstrom: float = 3.0
    polar_burial_distance_angstrom: float = 4.5
    max_receptor_candidate_pairs: int = 1_000_000
    max_ligand_pair_checks: int = 250_000
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for name in (
            "typed_vdw_weight",
            "electrostatics_weight",
            "directional_hbond_weight",
            "hydrophobic_contact_weight",
            "desolvation_weight",
            "torsion_energy_weight",
            "ligand_strain_weight",
            "weak_pocket_prior_weight",
        ):
            object.__setattr__(
                self,
                name,
                _finite(getattr(self, name), name=name, minimum=0.0, maximum=100.0),
            )
        object.__setattr__(
            self,
            "electrostatic_dielectric",
            _finite(
                self.electrostatic_dielectric,
                name="electrostatic_dielectric",
                minimum=1.0,
                maximum=100.0,
            ),
        )
        object.__setattr__(
            self,
            "pair_cutoff_angstrom",
            _finite(
                self.pair_cutoff_angstrom,
                name="pair_cutoff_angstrom",
                minimum=3.0,
                maximum=20.0,
            ),
        )
        object.__setattr__(
            self,
            "hbond_distance_max_angstrom",
            _finite(
                self.hbond_distance_max_angstrom,
                name="hbond_distance_max_angstrom",
                minimum=2.0,
                maximum=4.0,
            ),
        )
        object.__setattr__(
            self,
            "polar_burial_distance_angstrom",
            _finite(
                self.polar_burial_distance_angstrom,
                name="polar_burial_distance_angstrom",
                minimum=3.0,
                maximum=8.0,
            ),
        )
        if self.pair_cutoff_angstrom < max(
            self.hbond_distance_max_angstrom,
            self.polar_burial_distance_angstrom,
        ):
            raise ScorerV1Error(
                "pair_cutoff_angstrom must cover hydrogen-bond and polar-burial ranges"
            )
        object.__setattr__(
            self,
            "max_receptor_candidate_pairs",
            _exact_int(
                self.max_receptor_candidate_pairs,
                name="max_receptor_candidate_pairs",
                minimum=1,
                maximum=MAX_SCORER_V1_RECEPTOR_CANDIDATE_PAIRS,
            ),
        )
        object.__setattr__(
            self,
            "max_ligand_pair_checks",
            _exact_int(
                self.max_ligand_pair_checks,
                name="max_ligand_pair_checks",
                minimum=1,
                maximum=MAX_SCORER_V1_LIGAND_PAIR_CHECKS,
            ),
        )
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": SCORER_V1_CONFIG_SCHEMA_ID,
            "algorithm_id": SCORER_V1_ALGORITHM_ID,
            **{
                f"{name}_binary64_hex": float(getattr(self, name)).hex()
                for name in (
                    "typed_vdw_weight",
                    "electrostatics_weight",
                    "directional_hbond_weight",
                    "hydrophobic_contact_weight",
                    "desolvation_weight",
                    "torsion_energy_weight",
                    "ligand_strain_weight",
                    "weak_pocket_prior_weight",
                    "electrostatic_dielectric",
                    "pair_cutoff_angstrom",
                    "hbond_distance_max_angstrom",
                    "polar_burial_distance_angstrom",
                )
            },
            "max_receptor_candidate_pairs": self.max_receptor_candidate_pairs,
            "max_ligand_pair_checks": self.max_ligand_pair_checks,
            "calibrated": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise ScorerV1Error("scorer v1 config changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "fingerprint_sha256": self.fingerprint_sha256}


@dataclass(frozen=True, slots=True)
class ScorerV1Context:
    authority_input_receipt_sha256: str
    receptor_system_sha256: str
    ligand_system_sha256: str
    receptor_atom_indices: tuple[int, ...]
    receptor_atom_types: tuple[str, ...]
    ligand_atom_types: tuple[str, ...]
    receptor_partial_charges_e: tuple[float, ...]
    ligand_partial_charges_e: tuple[float, ...]
    receptor_donors: tuple[tuple[int, int], ...]
    ligand_donors: tuple[tuple[int, int], ...]
    receptor_acceptors: tuple[int, ...]
    ligand_acceptors: tuple[int, ...]
    receptor_hydrophobic: tuple[int, ...]
    ligand_hydrophobic: tuple[int, ...]
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for name in (
            "authority_input_receipt_sha256",
            "receptor_system_sha256",
            "ligand_system_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        receptor_atom_indices = tuple(
            int(value) for value in self.receptor_atom_indices
        )
        receptor_atom_types = tuple(str(value) for value in self.receptor_atom_types)
        ligand_atom_types = tuple(str(value) for value in self.ligand_atom_types)
        receptor_charges = tuple(
            float(value) for value in self.receptor_partial_charges_e
        )
        ligand_charges = tuple(float(value) for value in self.ligand_partial_charges_e)
        if (
            not receptor_atom_indices
            or receptor_atom_indices != tuple(sorted(set(receptor_atom_indices)))
            or any(value < 0 for value in receptor_atom_indices)
            or len(receptor_atom_indices) != len(receptor_atom_types)
            or len(receptor_atom_types) != len(receptor_charges)
        ):
            raise ScorerV1Error("scorer v1 receptor context dimensions are invalid")
        if not ligand_atom_types or len(ligand_atom_types) != len(ligand_charges):
            raise ScorerV1Error("scorer v1 ligand context dimensions are invalid")
        if any(
            re.fullmatch(
                r"(?:H|C|N|O|F|P|S|Cl|Br|I):(?:aromatic|aliphatic):(?:positive|negative|neutral)",
                value,
            )
            is None
            for value in (*receptor_atom_types, *ligand_atom_types)
        ):
            raise ScorerV1Error("scorer v1 atom type is invalid")
        if any(
            not math.isfinite(value) for value in (*receptor_charges, *ligand_charges)
        ):
            raise ScorerV1Error("scorer v1 context charges must be finite")

        def donor_rows(value, *, atom_count: int, name: str):
            rows = tuple((int(donor), int(hydrogen)) for donor, hydrogen in value)
            if len(rows) != len(set(rows)) or any(
                donor == hydrogen
                or not 0 <= donor < atom_count
                or not 0 <= hydrogen < atom_count
                for donor, hydrogen in rows
            ):
                raise ScorerV1Error(f"scorer v1 {name} donors are invalid")
            return rows

        def index_rows(value, *, atom_count: int, name: str):
            rows = tuple(int(index) for index in value)
            if rows != tuple(sorted(set(rows))) or any(
                not 0 <= index < atom_count for index in rows
            ):
                raise ScorerV1Error(f"scorer v1 {name} indices are invalid")
            return rows

        receptor_donors = donor_rows(
            self.receptor_donors,
            atom_count=len(receptor_atom_types),
            name="receptor",
        )
        ligand_donors = donor_rows(
            self.ligand_donors,
            atom_count=len(ligand_atom_types),
            name="ligand",
        )
        receptor_acceptors = index_rows(
            self.receptor_acceptors,
            atom_count=len(receptor_atom_types),
            name="receptor acceptor",
        )
        ligand_acceptors = index_rows(
            self.ligand_acceptors,
            atom_count=len(ligand_atom_types),
            name="ligand acceptor",
        )
        receptor_hydrophobic = index_rows(
            self.receptor_hydrophobic,
            atom_count=len(receptor_atom_types),
            name="receptor hydrophobic",
        )
        ligand_hydrophobic = index_rows(
            self.ligand_hydrophobic,
            atom_count=len(ligand_atom_types),
            name="ligand hydrophobic",
        )
        object.__setattr__(self, "receptor_atom_indices", receptor_atom_indices)
        object.__setattr__(self, "receptor_atom_types", receptor_atom_types)
        object.__setattr__(self, "ligand_atom_types", ligand_atom_types)
        object.__setattr__(self, "receptor_partial_charges_e", receptor_charges)
        object.__setattr__(self, "ligand_partial_charges_e", ligand_charges)
        object.__setattr__(self, "receptor_donors", receptor_donors)
        object.__setattr__(self, "ligand_donors", ligand_donors)
        object.__setattr__(self, "receptor_acceptors", receptor_acceptors)
        object.__setattr__(self, "ligand_acceptors", ligand_acceptors)
        object.__setattr__(self, "receptor_hydrophobic", receptor_hydrophobic)
        object.__setattr__(self, "ligand_hydrophobic", ligand_hydrophobic)
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": SCORER_V1_CONTEXT_SCHEMA_ID,
            "authority_input_receipt_sha256": self.authority_input_receipt_sha256,
            "receptor_system_sha256": self.receptor_system_sha256,
            "ligand_system_sha256": self.ligand_system_sha256,
            "receptor_atom_indices": list(self.receptor_atom_indices),
            "receptor_atom_types": list(self.receptor_atom_types),
            "ligand_atom_types": list(self.ligand_atom_types),
            "receptor_partial_charges_e_binary64_hex": [
                value.hex() for value in self.receptor_partial_charges_e
            ],
            "ligand_partial_charges_e_binary64_hex": [
                value.hex() for value in self.ligand_partial_charges_e
            ],
            "receptor_donors": [list(row) for row in self.receptor_donors],
            "ligand_donors": [list(row) for row in self.ligand_donors],
            "receptor_acceptors": list(self.receptor_acceptors),
            "ligand_acceptors": list(self.ligand_acceptors),
            "receptor_hydrophobic": list(self.receptor_hydrophobic),
            "ligand_hydrophobic": list(self.ligand_hydrophobic),
            "partial_charge_policy": "complete_explicit_atom_partial_charge_e",
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise ScorerV1Error("scorer v1 context changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "fingerprint_sha256": self.fingerprint_sha256}


@dataclass(frozen=True, slots=True)
class ScorerV1Terms:
    proposal_fingerprint_sha256: str
    authority_input_receipt_sha256: str
    context_fingerprint_sha256: str
    config_fingerprint_sha256: str
    typed_vdw: float
    electrostatics: float
    directional_hbond: float
    hydrophobic_contact: float
    desolvation_proxy: float
    torsion_energy: float
    ligand_strain: float
    weak_pocket_prior: float
    total_score: float
    receptor_candidate_pair_count: int
    ligand_pair_count: int
    hbond_count: int
    hydrophobic_contact_count: int
    buried_polar_count: int
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for name in (
            "proposal_fingerprint_sha256",
            "authority_input_receipt_sha256",
            "context_fingerprint_sha256",
            "config_fingerprint_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        for name in (
            "typed_vdw",
            "electrostatics",
            "directional_hbond",
            "hydrophobic_contact",
            "desolvation_proxy",
            "torsion_energy",
            "ligand_strain",
            "weak_pocket_prior",
            "total_score",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ScorerV1Error(f"{name} must be finite")
            object.__setattr__(self, name, value)
        for name in (
            "receptor_candidate_pair_count",
            "ligand_pair_count",
            "hbond_count",
            "hydrophobic_contact_count",
            "buried_polar_count",
        ):
            value = int(getattr(self, name))
            if value < 0:
                raise ScorerV1Error(f"{name} must be non-negative")
            object.__setattr__(self, name, value)
        expected = sum(
            float(getattr(self, name))
            for name in (
                "typed_vdw",
                "electrostatics",
                "directional_hbond",
                "hydrophobic_contact",
                "desolvation_proxy",
                "torsion_energy",
                "ligand_strain",
                "weak_pocket_prior",
            )
        )
        if not math.isclose(self.total_score, expected, rel_tol=0.0, abs_tol=1.0e-12):
            raise ScorerV1Error("scorer v1 total does not equal its term decomposition")
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": SCORER_V1_TERMS_SCHEMA_ID,
            "score_id": SCORER_V1_SCORE_ID,
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "authority_input_receipt_sha256": self.authority_input_receipt_sha256,
            "context_fingerprint_sha256": self.context_fingerprint_sha256,
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            **{
                f"{name}_binary64_hex": _float_hex(float(getattr(self, name)))
                for name in (
                    "typed_vdw",
                    "electrostatics",
                    "directional_hbond",
                    "hydrophobic_contact",
                    "desolvation_proxy",
                    "torsion_energy",
                    "ligand_strain",
                    "weak_pocket_prior",
                    "total_score",
                )
            },
            "receptor_candidate_pair_count": self.receptor_candidate_pair_count,
            "ligand_pair_count": self.ligand_pair_count,
            "hbond_count": self.hbond_count,
            "hydrophobic_contact_count": self.hydrophobic_contact_count,
            "buried_polar_count": self.buried_polar_count,
            "calibrated": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise ScorerV1Error("scorer v1 terms changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


class ChemistryPoseScorerV1:
    scorer_id = SCORER_V1_ID
    scorer_version = SCORER_V1_VERSION
    validated_for_docking_ranking = False

    def __init__(
        self,
        authority: AuthenticatedDockingProblem,
        receptor_system: AllAtomSystem,
        ligand_system: AllAtomSystem,
        *,
        implementation_source_sha256: str,
        config: ScorerV1Config | None = None,
    ) -> None:
        if not isinstance(authority, AuthenticatedDockingProblem):
            raise TypeError("authority must be AuthenticatedDockingProblem")
        if not isinstance(authority.validity_context, ElementAwarePoseValidityContext):
            raise ScorerV1Error("scorer v1 requires element-aware authority")
        for name, system in (
            ("receptor_system", receptor_system),
            ("ligand_system", ligand_system),
        ):
            if not isinstance(system, AllAtomSystem):
                raise TypeError(f"{name} must be AllAtomSystem")
            require_valid_all_atom_system(system)
        if len(receptor_system.bonds) > MAX_SCORER_V1_RECEPTOR_BONDS_SCANNED:
            raise ScorerV1Error("receptor bond count exceeds scorer v1 hard bound")
        if (
            canonical_system_sha256(receptor_system) != authority.receptor_system_sha256
            or canonical_system_sha256(ligand_system) != authority.ligand_system_sha256
        ):
            raise ScorerV1Error("scorer v1 systems are cross-wired")
        selected_config = ScorerV1Config() if config is None else config
        if not isinstance(selected_config, ScorerV1Config):
            raise TypeError("config must be ScorerV1Config")
        receptor_indices = authority.receptor_atom_indices
        receptor_allowed = set(receptor_indices)
        ligand_allowed = set(range(ligand_system.atom_count))
        receptor_charges_full = _complete_charges(receptor_system)
        ligand_charges = _complete_charges(ligand_system)
        receptor_donors_full, receptor_acceptors_full, receptor_hydrophobic_full = (
            _features(receptor_system, receptor_allowed)
        )
        ligand_donors, ligand_acceptors, ligand_hydrophobic = _features(
            ligand_system, ligand_allowed
        )
        receptor_position = {
            atom_index: position for position, atom_index in enumerate(receptor_indices)
        }
        receptor_donors = tuple(
            (receptor_position[donor], receptor_position[hydrogen])
            for donor, hydrogen in receptor_donors_full
            if donor in receptor_position and hydrogen in receptor_position
        )
        self._context = ScorerV1Context(
            authority_input_receipt_sha256=authority.input_receipt_sha256,
            receptor_system_sha256=authority.receptor_system_sha256,
            ligand_system_sha256=authority.ligand_system_sha256,
            receptor_atom_indices=receptor_indices,
            receptor_atom_types=tuple(
                _atom_type(
                    receptor_system.atoms[index].element,
                    receptor_system.atoms[index].aromatic,
                    receptor_system.atoms[index].formal_charge,
                )
                for index in receptor_indices
            ),
            ligand_atom_types=tuple(
                _atom_type(atom.element, atom.aromatic, atom.formal_charge)
                for atom in ligand_system.atoms
            ),
            receptor_partial_charges_e=tuple(
                receptor_charges_full[index] for index in receptor_indices
            ),
            ligand_partial_charges_e=ligand_charges,
            receptor_donors=receptor_donors,
            ligand_donors=ligand_donors,
            receptor_acceptors=tuple(
                receptor_position[index] for index in receptor_acceptors_full
            ),
            ligand_acceptors=ligand_acceptors,
            receptor_hydrophobic=tuple(
                receptor_position[index] for index in receptor_hydrophobic_full
            ),
            ligand_hydrophobic=ligand_hydrophobic,
        )
        self._authority = authority
        self._validity = authority.validity_context
        self._config = selected_config
        self._ligand_reference = (
            ligand_system.coordinates[authority.ligand_model_index]
            .detach()
            .to(dtype=torch.float64, device="cpu")
            .clone()
            .contiguous()
        )
        self.problem_fingerprint_sha256 = authority.problem.fingerprint_sha256
        self.implementation_source_sha256 = _digest(
            implementation_source_sha256, name="implementation_source_sha256"
        )
        self.config_fingerprint_sha256 = selected_config.fingerprint_sha256
        self.score_descriptor = DockingScoreDescriptor(
            score_id=SCORER_V1_SCORE_ID,
            direction=ScoreDirection.MINIMIZE,
            unit=None,
            semantics="uncalibrated_dimensionless_chemistry_pose_ordering_score",
            calibrated=False,
            applicability_domain_id=SCORER_V1_APPLICABILITY_DOMAIN_ID,
        )
        self._receptor_cells = self._build_receptor_cells()
        self._receptor_hydrophobic = frozenset(self._context.receptor_hydrophobic)
        self._ligand_hydrophobic = frozenset(self._context.ligand_hydrophobic)
        self._ligand_acceptors = frozenset(self._context.ligand_acceptors)
        self._ligand_donor_heavy = frozenset(
            donor for donor, _ in self._context.ligand_donors
        )
        ligand_adjacency = _adjacency(ligand_system)

        def anchor(index: int, excluded: int) -> int:
            candidates = [
                neighbor for neighbor in ligand_adjacency[index] if neighbor != excluded
            ]
            if not candidates:
                raise ScorerV1Error("rotatable bond lacks a dihedral anchor")
            return min(
                candidates,
                key=lambda value: (
                    ligand_system.atoms[value].element == "H",
                    value,
                ),
            )

        rotor_quads: list[tuple[int, int, int, int]] = []
        for child in (
            torch.nonzero(
                authority.search_space.rotatable_mask,
                as_tuple=False,
            )
            .reshape(-1)
            .tolist()
        ):
            child = int(child)
            parent = int(authority.search_space.parent[child].item())
            rotor_quads.append(
                (
                    anchor(parent, child),
                    parent,
                    child,
                    anchor(child, parent),
                )
            )
        self._rotor_quads = tuple(rotor_quads)
        self._reference_dihedrals = tuple(
            _dihedral_angle(self._ligand_reference, quad) for quad in self._rotor_quads
        )
        self._reference_internal_vdw, self._reference_ligand_pair_count = (
            self._ligand_internal_vdw(self._ligand_reference)
        )

    @property
    def context(self) -> ScorerV1Context:
        return self._context

    @property
    def config(self) -> ScorerV1Config:
        return self._config

    @property
    def authority_input_receipt_sha256(self) -> str:
        return self._authority.input_receipt_sha256

    @property
    def contract_fingerprint_sha256(self) -> str:
        return component_contract_fingerprint(
            self,
            kind="scorer",
            expected_problem_fingerprint_sha256=self.problem_fingerprint_sha256,
        )

    def _build_receptor_cells(self) -> Mapping[tuple[int, int, int], tuple[int, ...]]:
        rows: dict[tuple[int, int, int], list[int]] = defaultdict(list)
        coordinates = self._validity.receptor_coordinates
        for index in range(len(coordinates)):
            rows[
                _cell_key(coordinates[index], self._config.pair_cutoff_angstrom)
            ].append(index)
        return MappingProxyType(
            {key: tuple(value) for key, value in sorted(rows.items())}
        )

    def _assert_proposal(self, proposal: DockingProposal) -> None:
        if not isinstance(proposal, DockingProposal):
            raise TypeError("proposal must be DockingProposal")
        # Re-evaluate every bound identity before and after scoring so callers
        # cannot obtain a receipt from a scorer whose authenticated inputs were
        # mutated after construction.
        authority_receipt = self._authority.input_receipt_sha256
        if authority_receipt != self._context.authority_input_receipt_sha256:
            raise ScorerV1Error("scorer v1 authority changed")
        self._validity.fingerprint_sha256
        self._config.fingerprint_sha256
        proposal.assert_integrity()
        if (
            proposal.problem_fingerprint_sha256 != self.problem_fingerprint_sha256
            or proposal.search_space_fingerprint_sha256
            != self._authority.search_space.fingerprint_sha256
        ):
            raise ScorerV1Error("proposal is cross-wired")
        self._context.fingerprint_sha256

    def _epsilon(self, atom_type: str) -> float:
        element, geometry, charge_class = atom_type.split(":")
        try:
            base = _EPSILON_BY_ELEMENT[element]
        except KeyError as exc:
            raise ScorerV1Error(f"unsupported typed vdW element {element}") from exc
        geometry_scale = 1.05 if geometry == "aromatic" else 1.0
        charge_scale = 0.9 if charge_class != "neutral" else 1.0
        return base * geometry_scale * charge_scale

    def _lj(
        self, first_type: str, second_type: str, sigma: float, distance: float
    ) -> float:
        if distance <= 1.0e-8:
            return 1.0e6
        ratio = min(2.0, sigma / distance)
        sixth = ratio**6
        return math.sqrt(self._epsilon(first_type) * self._epsilon(second_type)) * (
            sixth * sixth - 2.0 * sixth
        )

    def _ligand_internal_vdw(self, coordinates: torch.Tensor) -> tuple[float, int]:
        exclusions = set(self._validity.excluded_nonbonded_pairs)
        value = 0.0
        count = 0
        policy = self._validity.contact_policy
        for first in range(len(coordinates)):
            for second in range(first + 1, len(coordinates)):
                if (first, second) in exclusions:
                    continue
                count += 1
                if count > self._config.max_ligand_pair_checks:
                    raise ScorerV1Error("ligand pair capacity exceeded")
                distance = float(
                    torch.linalg.vector_norm(
                        coordinates[first] - coordinates[second]
                    ).item()
                )
                sigma = policy.radius(
                    self._validity.ligand_elements[first]
                ) + policy.radius(self._validity.ligand_elements[second])
                value += self._lj(
                    self._context.ligand_atom_types[first],
                    self._context.ligand_atom_types[second],
                    sigma,
                    distance,
                )
        return value, count

    def score_terms(self, proposal: DockingProposal) -> ScorerV1Terms:
        self._assert_proposal(proposal)
        pose = proposal.coordinates.detach().to(dtype=torch.float64, device="cpu")
        receptor = self._validity.receptor_coordinates
        policy = self._validity.contact_policy
        config = self._config
        typed_vdw_raw = 0.0
        electro_raw = 0.0
        hydrophobic_raw = 0.0
        hydrophobic_count = 0
        candidate_count = 0
        polar_buried: set[int] = set()
        polar_satisfied: set[int] = set()
        ligand_hydrophobic = self._ligand_hydrophobic
        receptor_hydrophobic = self._receptor_hydrophobic
        ligand_polar = self._ligand_acceptors | self._ligand_donor_heavy
        pair_rows: dict[tuple[int, int], float] = {}
        for ligand_index, coordinate in enumerate(pose):
            center = _cell_key(coordinate, config.pair_cutoff_angstrom)
            for x in range(center[0] - 1, center[0] + 2):
                for y in range(center[1] - 1, center[1] + 2):
                    for z in range(center[2] - 1, center[2] + 2):
                        for receptor_index in self._receptor_cells.get((x, y, z), ()):
                            candidate_count += 1
                            if candidate_count > config.max_receptor_candidate_pairs:
                                raise ScorerV1Error(
                                    "receptor candidate-pair capacity exceeded"
                                )
                            distance = float(
                                torch.linalg.vector_norm(
                                    coordinate - receptor[receptor_index]
                                ).item()
                            )
                            if distance > config.pair_cutoff_angstrom:
                                continue
                            pair_rows[(ligand_index, receptor_index)] = distance
                            sigma = policy.radius(
                                self._validity.ligand_elements[ligand_index]
                            ) + policy.radius(
                                self._validity.receptor_elements[receptor_index]
                            )
                            typed_vdw_raw += self._lj(
                                self._context.ligand_atom_types[ligand_index],
                                self._context.receptor_atom_types[receptor_index],
                                sigma,
                                distance,
                            )
                            electro_raw += (
                                self._context.ligand_partial_charges_e[ligand_index]
                                * self._context.receptor_partial_charges_e[
                                    receptor_index
                                ]
                            ) / (config.electrostatic_dielectric * max(distance, 0.5))
                            if (
                                ligand_index in ligand_hydrophobic
                                and receptor_index in receptor_hydrophobic
                                and distance <= 1.25 * sigma
                            ):
                                hydrophobic_count += 1
                                hydrophobic_raw += max(
                                    0.0, 1.0 - distance / (1.25 * sigma)
                                )
                            if ligand_index in ligand_polar:
                                if distance <= config.polar_burial_distance_angstrom:
                                    polar_buried.add(ligand_index)

        hbond_raw = 0.0
        hbond_count = 0

        def hbond_reward(
            donor: torch.Tensor, hydrogen: torch.Tensor, acceptor: torch.Tensor
        ) -> float:
            distance = float(torch.linalg.vector_norm(hydrogen - acceptor).item())
            if distance > config.hbond_distance_max_angstrom or distance <= 1.0e-8:
                return 0.0
            first = donor - hydrogen
            second = acceptor - hydrogen
            denom = float(
                torch.linalg.vector_norm(first).item()
                * torch.linalg.vector_norm(second).item()
            )
            if denom <= 1.0e-12:
                return 0.0
            cosine = float(torch.dot(first, second).item()) / denom
            angular = max(0.0, min(1.0, (-cosine - 0.5) / 0.5))
            radial = max(0.0, 1.0 - distance / config.hbond_distance_max_angstrom)
            return angular * radial

        ligand_donor_by_hydrogen = {
            hydrogen: donor for donor, hydrogen in self._context.ligand_donors
        }
        receptor_donor_by_hydrogen = {
            hydrogen: donor for donor, hydrogen in self._context.receptor_donors
        }
        receptor_acceptors = set(self._context.receptor_acceptors)
        ligand_acceptors = set(self._context.ligand_acceptors)
        for (ligand_index, receptor_index), _ in pair_rows.items():
            ligand_donor = ligand_donor_by_hydrogen.get(ligand_index)
            if ligand_donor is not None and receptor_index in receptor_acceptors:
                reward = hbond_reward(
                    pose[ligand_donor],
                    pose[ligand_index],
                    receptor[receptor_index],
                )
                if reward > 0.0:
                    hbond_raw += reward
                    hbond_count += 1
                    polar_satisfied.add(ligand_donor)
            receptor_donor = receptor_donor_by_hydrogen.get(receptor_index)
            if receptor_donor is not None and ligand_index in ligand_acceptors:
                reward = hbond_reward(
                    receptor[receptor_donor],
                    receptor[receptor_index],
                    pose[ligand_index],
                )
                if reward > 0.0:
                    hbond_raw += reward
                    hbond_count += 1
                    polar_satisfied.add(ligand_index)

        current_internal, ligand_pair_count = self._ligand_internal_vdw(pose)
        strain_raw = max(0.0, current_internal - self._reference_internal_vdw)
        pose_dihedrals = (_dihedral_angle(pose, quad) for quad in self._rotor_quads)
        torsion_raw = math.fsum(
            0.5
            * (
                1.0
                - math.cos(
                    3.0
                    * math.atan2(
                        math.sin(observed - reference),
                        math.cos(observed - reference),
                    )
                )
            )
            for observed, reference in zip(
                pose_dihedrals,
                self._reference_dihedrals,
                strict=True,
            )
        )
        centroid_distance = float(
            torch.linalg.vector_norm(
                pose.mean(dim=0) - self._authority.pocket.center
            ).item()
        )
        pocket_raw = (centroid_distance / self._authority.pocket.radius_angstrom) ** 2
        desolvation_raw = float(len(polar_buried - polar_satisfied))
        terms = {
            "typed_vdw": config.typed_vdw_weight * typed_vdw_raw,
            "electrostatics": config.electrostatics_weight * electro_raw,
            "directional_hbond": -config.directional_hbond_weight * hbond_raw,
            "hydrophobic_contact": -config.hydrophobic_contact_weight * hydrophobic_raw,
            "desolvation_proxy": config.desolvation_weight * desolvation_raw,
            "torsion_energy": config.torsion_energy_weight * torsion_raw,
            "ligand_strain": config.ligand_strain_weight * strain_raw,
            "weak_pocket_prior": config.weak_pocket_prior_weight * pocket_raw,
        }
        total = sum(terms.values())
        result = ScorerV1Terms(
            proposal_fingerprint_sha256=proposal.fingerprint_sha256,
            authority_input_receipt_sha256=self._authority.input_receipt_sha256,
            context_fingerprint_sha256=self._context.fingerprint_sha256,
            config_fingerprint_sha256=config.fingerprint_sha256,
            total_score=total,
            receptor_candidate_pair_count=candidate_count,
            ligand_pair_count=ligand_pair_count,
            hbond_count=hbond_count,
            hydrophobic_contact_count=hydrophobic_count,
            buried_polar_count=len(polar_buried),
            **terms,
        )
        self._assert_proposal(proposal)
        return result

    def score(self, proposal: DockingProposal) -> float:
        return self.score_terms(proposal).total_score

    def qualification_document(self) -> dict[str, object]:
        projection = {
            "schema_id": "betelgeuze.engine_v2_scorer_v1_status/1.0.0",
            "scorer_id": self.scorer_id,
            "scorer_version": self.scorer_version,
            "score_descriptor": self.score_descriptor.to_dict(),
            "authority_input_receipt_sha256": self._authority.input_receipt_sha256,
            "context_fingerprint_sha256": self._context.fingerprint_sha256,
            "config_fingerprint_sha256": self._config.fingerprint_sha256,
            "component_contract_fingerprint_sha256": self.contract_fingerprint_sha256,
            "term_names": [
                "typed_vdw",
                "electrostatics",
                "directional_hbond",
                "hydrophobic_contact",
                "desolvation_proxy",
                "torsion_energy",
                "ligand_strain",
                "weak_pocket_prior",
            ],
            "validated_for_docking_ranking": False,
            "affinity_estimate": False,
            "free_energy_estimate": False,
            "calibrated": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "claim_safe": False,
        }
        return {**projection, "document_sha256": _sha256(projection)}


def _row_sha256(row: DockingSearchRow) -> str:
    return _sha256(row.to_dict())


@dataclass(frozen=True, slots=True)
class ScorerV1SearchTermRow:
    candidate_id: str
    proposal_index: int
    search_status: str
    search_row_sha256: str
    score: float | None
    selection_eligible: bool
    terms: ScorerV1Terms | None
    error_code: str = ""
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        candidate_id = str(self.candidate_id or "").strip()
        if not candidate_id:
            raise ScorerV1Error("scorer v1 term row candidate ID is empty")
        if type(self.proposal_index) is not int or self.proposal_index < 0:
            raise ScorerV1Error("scorer v1 term row index is invalid")
        status = str(self.search_status or "").strip()
        if status not in {"success", "failure"}:
            raise ScorerV1Error("scorer v1 term row status is invalid")
        search_row_sha256 = _digest(
            self.search_row_sha256,
            name="search_row_sha256",
        )
        error_code = str(self.error_code or "").strip()
        if status == "success":
            if self.score is None or not isinstance(self.terms, ScorerV1Terms):
                raise ScorerV1Error(
                    "successful scorer v1 rows require scalar and terms"
                )
            score = float(self.score)
            if not math.isfinite(score):
                raise ScorerV1Error("successful scorer v1 score is not finite")
            if score.hex() != self.terms.total_score.hex():
                raise ScorerV1Error(
                    "scorer v1 retained terms disagree with search scalar"
                )
            if error_code:
                raise ScorerV1Error("successful scorer v1 rows cannot contain an error")
            object.__setattr__(self, "score", score)
        elif (
            self.score is not None or self.terms is not None or self.selection_eligible
        ):
            raise ScorerV1Error("failed scorer v1 rows cannot fabricate score evidence")
        elif not error_code:
            raise ScorerV1Error("failed scorer v1 rows require an error code")
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "search_status", status)
        object.__setattr__(self, "search_row_sha256", search_row_sha256)
        object.__setattr__(self, "error_code", error_code)
        object.__setattr__(
            self,
            "_receipt_sha256",
            _sha256(self._projection()),
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": SCORER_V1_TERM_ROW_SCHEMA_ID,
            "candidate_id": self.candidate_id,
            "proposal_index": self.proposal_index,
            "search_status": self.search_status,
            "search_row_sha256": self.search_row_sha256,
            "score_binary64_hex": (None if self.score is None else self.score.hex()),
            "selection_eligible": bool(self.selection_eligible),
            "terms_receipt_sha256": (
                "" if self.terms is None else self.terms.receipt_sha256
            ),
            "error_code": self.error_code,
            "failure_row_retained": self.search_status == "failure",
            "calibrated": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise ScorerV1Error("scorer v1 search term row changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
            "terms": None if self.terms is None else self.terms.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ScorerV1GuidedSearchResult:
    guided_search_result: GuidedPlacementSearchResult
    scorer: ChemistryPoseScorerV1 = field(repr=False, compare=False)
    scorer_contract_fingerprint_sha256: str
    scorer_authority_input_receipt_sha256: str
    scorer_context_fingerprint_sha256: str
    scorer_config_fingerprint_sha256: str
    rows: tuple[ScorerV1SearchTermRow, ...]
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.guided_search_result,
            GuidedPlacementSearchResult,
        ):
            raise TypeError("guided_search_result must be GuidedPlacementSearchResult")
        if not isinstance(self.scorer, ChemistryPoseScorerV1):
            raise TypeError("scorer must be ChemistryPoseScorerV1")
        scorer_contract = _digest(
            self.scorer_contract_fingerprint_sha256,
            name="scorer_contract_fingerprint_sha256",
        )
        scorer_authority = _digest(
            self.scorer_authority_input_receipt_sha256,
            name="scorer_authority_input_receipt_sha256",
        )
        scorer_context = _digest(
            self.scorer_context_fingerprint_sha256,
            name="scorer_context_fingerprint_sha256",
        )
        scorer_config = _digest(
            self.scorer_config_fingerprint_sha256,
            name="scorer_config_fingerprint_sha256",
        )
        search = self.guided_search_result.authenticated_search_result
        if search.authenticated_input_receipt_sha256 != scorer_authority:
            raise ScorerV1Error("scorer v1 search authority is cross-wired")
        if search.search_result.scorer_contract_fingerprint_sha256 != scorer_contract:
            raise ScorerV1Error("scorer v1 search contract is cross-wired")
        if (
            self.scorer.contract_fingerprint_sha256 != scorer_contract
            or self.scorer.authority_input_receipt_sha256 != scorer_authority
            or self.scorer.context.fingerprint_sha256 != scorer_context
            or self.scorer.config.fingerprint_sha256 != scorer_config
        ):
            raise ScorerV1Error("scorer v1 result scorer is cross-wired")
        rows = tuple(self.rows)
        source_rows = search.search_result.rows
        if len(rows) != len(source_rows):
            raise ScorerV1Error("scorer v1 rows do not preserve the search denominator")
        for retained, source in zip(rows, source_rows, strict=True):
            if (
                retained.candidate_id != source.candidate_id
                or retained.proposal_index != source.proposal_index
                or retained.search_status != source.status
                or retained.search_row_sha256 != _row_sha256(source)
            ):
                raise ScorerV1Error("scorer v1 search row is cross-wired")
            if retained.terms is not None and (
                source.proposal is None
                or retained.terms.proposal_fingerprint_sha256
                != source.proposal.fingerprint_sha256
                or retained.terms.authority_input_receipt_sha256 != scorer_authority
                or retained.terms.context_fingerprint_sha256 != scorer_context
                or retained.terms.config_fingerprint_sha256 != scorer_config
            ):
                raise ScorerV1Error("scorer v1 row terms are cross-wired")
            if retained.terms is not None:
                assert source.proposal is not None
                expected_terms = self.scorer.score_terms(source.proposal)
                if retained.terms.receipt_sha256 != expected_terms.receipt_sha256:
                    raise ScorerV1Error("scorer v1 row terms are not the scorer output")
            if (
                retained.selection_eligible != source.selection_eligible
                or retained.error_code != source.error_code
            ):
                raise ScorerV1Error("scorer v1 row outcome is cross-wired")
            if source.score is None:
                if retained.score is not None:
                    raise ScorerV1Error("scorer v1 row fabricated a source score")
            elif (
                retained.score is None
                or retained.score.hex() != float(source.score).hex()
            ):
                raise ScorerV1Error("scorer v1 row score is cross-wired")
        object.__setattr__(self, "rows", rows)
        object.__setattr__(
            self,
            "scorer_contract_fingerprint_sha256",
            scorer_contract,
        )
        object.__setattr__(
            self,
            "scorer_authority_input_receipt_sha256",
            scorer_authority,
        )
        object.__setattr__(
            self,
            "scorer_context_fingerprint_sha256",
            scorer_context,
        )
        object.__setattr__(
            self,
            "scorer_config_fingerprint_sha256",
            scorer_config,
        )
        object.__setattr__(
            self,
            "_receipt_sha256",
            _sha256(self._projection()),
        )

    @property
    def success_count(self) -> int:
        return sum(row.search_status == "success" for row in self.rows)

    @property
    def failure_count(self) -> int:
        return len(self.rows) - self.success_count

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": SCORER_V1_SEARCH_RESULT_SCHEMA_ID,
            "guided_search_receipt_sha256": (self.guided_search_result.receipt_sha256),
            "authenticated_search_receipt_sha256": (
                self.guided_search_result.authenticated_search_result.receipt_sha256
            ),
            "scorer_contract_fingerprint_sha256": (
                self.scorer_contract_fingerprint_sha256
            ),
            "scorer_authority_input_receipt_sha256": (
                self.scorer_authority_input_receipt_sha256
            ),
            "scorer_context_fingerprint_sha256": (
                self.scorer_context_fingerprint_sha256
            ),
            "scorer_config_fingerprint_sha256": (self.scorer_config_fingerprint_sha256),
            "candidate_count": len(self.rows),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "row_receipt_sha256s": [row.receipt_sha256 for row in self.rows],
            "term_decomposition_retained": True,
            "failure_rows_retained": True,
            "calibrated": False,
            "validated_for_docking_ranking": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise ScorerV1Error("scorer v1 guided search result changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
            "rows": [row.to_dict() for row in self.rows],
            "guided_search_result": self.guided_search_result.to_dict(),
        }


def run_authenticated_scorer_v1_guided_search(
    authenticated_problem: AuthenticatedDockingProblem,
    budget: DockingBudget,
    scorer: ChemistryPoseScorerV1,
    guided_context: GuidedPlacementContext,
    *,
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
    refiner=None,
    diversity_rmsd_angstrom: float = 0.5,
    diversity_metric: str = "direct_rmsd",
    symmetry_permutations: Sequence[Sequence[int] | torch.Tensor] | None = None,
) -> ScorerV1GuidedSearchResult:
    if not isinstance(scorer, ChemistryPoseScorerV1):
        raise TypeError("scorer must be ChemistryPoseScorerV1")
    if scorer.authority_input_receipt_sha256 != (
        authenticated_problem.input_receipt_sha256
    ):
        raise ScorerV1Error("scorer v1 authority is cross-wired")
    guided = run_authenticated_guided_placement_search(
        authenticated_problem,
        budget,
        scorer,
        guided_context,
        receptor_system=receptor_system,
        ligand_system=ligand_system,
        refiner=refiner,
        diversity_rmsd_angstrom=diversity_rmsd_angstrom,
        diversity_metric=diversity_metric,
        symmetry_permutations=symmetry_permutations,
    )
    retained: list[ScorerV1SearchTermRow] = []
    for row in guided.authenticated_search_result.search_result.rows:
        if row.succeeded:
            if row.proposal is None or row.score is None:
                raise ScorerV1Error("successful scorer v1 row lacks score evidence")
            terms = scorer.score_terms(row.proposal)
            retained.append(
                ScorerV1SearchTermRow(
                    candidate_id=row.candidate_id,
                    proposal_index=row.proposal_index,
                    search_status=row.status,
                    search_row_sha256=_row_sha256(row),
                    score=float(row.score),
                    selection_eligible=row.selection_eligible,
                    terms=terms,
                )
            )
        else:
            retained.append(
                ScorerV1SearchTermRow(
                    candidate_id=row.candidate_id,
                    proposal_index=row.proposal_index,
                    search_status=row.status,
                    search_row_sha256=_row_sha256(row),
                    score=None,
                    selection_eligible=False,
                    terms=None,
                    error_code=row.error_code,
                )
            )
    return ScorerV1GuidedSearchResult(
        guided_search_result=guided,
        scorer=scorer,
        scorer_contract_fingerprint_sha256=(scorer.contract_fingerprint_sha256),
        scorer_authority_input_receipt_sha256=(scorer.authority_input_receipt_sha256),
        scorer_context_fingerprint_sha256=(scorer.context.fingerprint_sha256),
        scorer_config_fingerprint_sha256=(scorer.config.fingerprint_sha256),
        rows=tuple(retained),
    )


PoseScorerV1 = ChemistryPoseScorerV1


__all__ = [
    "MAX_SCORER_V1_LIGAND_PAIR_CHECKS",
    "MAX_SCORER_V1_RECEPTOR_BONDS_SCANNED",
    "MAX_SCORER_V1_RECEPTOR_CANDIDATE_PAIRS",
    "SCORER_V1_ALGORITHM_ID",
    "SCORER_V1_APPLICABILITY_DOMAIN_ID",
    "SCORER_V1_CONFIG_SCHEMA_ID",
    "SCORER_V1_CONTEXT_SCHEMA_ID",
    "SCORER_V1_ID",
    "SCORER_V1_SCORE_ID",
    "SCORER_V1_SEARCH_RESULT_SCHEMA_ID",
    "SCORER_V1_TERMS_SCHEMA_ID",
    "SCORER_V1_TERM_ROW_SCHEMA_ID",
    "SCORER_V1_VERSION",
    "ChemistryPoseScorerV1",
    "PoseScorerV1",
    "ScorerV1Config",
    "ScorerV1Context",
    "ScorerV1Error",
    "ScorerV1GuidedSearchResult",
    "ScorerV1SearchTermRow",
    "ScorerV1Terms",
    "run_authenticated_scorer_v1_guided_search",
]
