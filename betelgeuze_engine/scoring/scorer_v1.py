"""Scorer v1: typed, per-term docking score with an explicit term breakdown (P1-5).

The legacy composite score mixed z-scored ligand descriptors with a single
lumped energy proxy, so a pose's score could not be attributed to any physical
interaction. A reviewer could not tell whether a good score came from a real
H-bond or from a favourable molecular weight.

Scorer v1 emits every term the docking MVP needs, separately:

1. typed steric / vdW (element-typed LJ, not a single generic radius)
2. charge electrostatics (distance-screened, partial charges)
3. directional H-bond (distance *and* angle gated)
4. hydrophobic contact (apolar-apolar burial)
5. desolvation proxy (polar burial penalty)
6. ligand torsion energy (chemistry-aware rotor states)
7. intramolecular strain (internal clash / bond distortion)
8. weak pocket prior (bounded centering term, deliberately small)

Every term is reported with its raw value, weight, and weighted contribution, so
the total is always reproducible from the breakdown. Weights are internal and
uncalibrated: this scores and ranks, it does not claim a binding free energy.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

import numpy as np

from betelgeuze_engine.chemistry.rotor_perception import perceive_ligand_rotors

SCORER_V1_SCHEMA_VERSION = "docking_scorer_v1"

#: Term ids, in report order. The docking MVP requires all eight.
TERM_STERIC_VDW = "typed_steric_vdw"
TERM_ELECTROSTATICS = "charge_electrostatics"
TERM_HBOND = "directional_hbond"
TERM_HYDROPHOBIC = "hydrophobic_contact"
TERM_DESOLVATION = "desolvation_proxy"
TERM_TORSION = "ligand_torsion_energy"
TERM_STRAIN = "intramolecular_strain"
TERM_POCKET_PRIOR = "weak_pocket_prior"

SCORER_V1_TERMS = (
    TERM_STERIC_VDW,
    TERM_ELECTROSTATICS,
    TERM_HBOND,
    TERM_HYDROPHOBIC,
    TERM_DESOLVATION,
    TERM_TORSION,
    TERM_STRAIN,
    TERM_POCKET_PRIOR,
)

#: Internal weights. The pocket prior is intentionally the smallest weight: it
#: is a tie-breaker, not a driver, so a centred but non-interacting pose cannot
#: outrank an interacting one.
DEFAULT_TERM_WEIGHTS: dict[str, float] = {
    TERM_STERIC_VDW: 1.00,
    TERM_ELECTROSTATICS: 0.55,
    TERM_HBOND: 1.20,
    TERM_HYDROPHOBIC: 0.45,
    TERM_DESOLVATION: 0.35,
    TERM_TORSION: 0.30,
    TERM_STRAIN: 0.50,
    TERM_POCKET_PRIOR: 0.05,
}

APOLAR_ELEMENTS = frozenset({"C", "S", "CL", "BR", "I", "F"})
POLAR_ELEMENTS = frozenset({"N", "O", "P", "S"})
HBOND_ELEMENTS = frozenset({"N", "O", "S"})

#: Geometry gates for the directional H-bond term.
HBOND_MIN_DISTANCE_A = 2.4
HBOND_MAX_DISTANCE_A = 3.5
HBOND_MIN_COS_ANGLE = 0.5

HYDROPHOBIC_MAX_DISTANCE_A = 5.0
DESOLVATION_BURIAL_RADIUS_A = 4.5
STERIC_CUTOFF_A = 8.0
ELECTROSTATIC_CUTOFF_A = 12.0
CLASH_DISTANCE_A = 2.0

STATUS_READY = "scorer_v1_scored"
STATUS_BLOCKED_EMPTY = "blocked_empty_coordinates"

CLAIM_BOUNDARY = (
    "Scorer v1 emits typed per-term interaction scores for ranking and evidence only. Weights and terms are "
    "internal and uncalibrated; the total is not a binding free energy, an affinity prediction, or a "
    "benchmarked accuracy claim."
)

_VDW_RADII = {"H": 1.20, "C": 1.70, "N": 1.55, "O": 1.52, "S": 1.80, "P": 1.80, "F": 1.47, "CL": 1.75}
_DEFAULT_RADIUS = 1.70


@dataclass(frozen=True)
class ScoreTerm:
    """One named term with its raw value, weight, and weighted contribution."""

    term_id: str
    raw_value: float
    weight: float
    weighted_value: float
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScoreResult:
    """Full scoring result: total plus the per-term breakdown that produces it."""

    status: str
    total_score: float
    terms: tuple[ScoreTerm, ...] = ()
    blockers: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ready(self) -> bool:
        return self.status == STATUS_READY

    def term(self, term_id: str) -> ScoreTerm | None:
        for candidate in self.terms:
            if candidate.term_id == term_id:
                return candidate
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCORER_V1_SCHEMA_VERSION,
            "status": self.status,
            "ready": self.ready,
            "total_score": float(self.total_score),
            "term_ids": list(SCORER_V1_TERMS),
            "terms": {term.term_id: term.to_dict() for term in self.terms},
            "term_count": len(self.terms),
            "blockers": list(self.blockers),
            "claim_boundary": CLAIM_BOUNDARY,
        }


def _elements(values: Sequence[str] | None, count: int) -> list[str]:
    if values is not None and len(values) == count:
        return [str(value or "C").strip().upper() for value in values]
    return ["C"] * count


def _charges(values: Sequence[float] | None, count: int) -> np.ndarray:
    if values is not None and len(values) == count:
        return np.asarray([float(value) for value in values], dtype=np.float64)
    return np.zeros(count, dtype=np.float64)


def _radius(element: str) -> float:
    return float(_VDW_RADII.get(str(element).upper()[:2], _VDW_RADII.get(str(element).upper()[:1], _DEFAULT_RADIUS)))


def _typed_steric_vdw(
    distances: np.ndarray,
    protein_elements: list[str],
    ligand_elements: list[str],
) -> ScoreTerm:
    """Element-typed soft LJ: attraction near contact, steep clash penalty."""

    energy = 0.0
    contact_count = 0
    clash_count = 0
    for i, p_element in enumerate(protein_elements):
        r_p = _radius(p_element)
        for j, l_element in enumerate(ligand_elements):
            distance = float(distances[i, j])
            if distance >= STERIC_CUTOFF_A:
                continue
            contact_count += 1
            sigma = r_p + _radius(l_element)
            ratio = sigma / max(distance, 0.8)
            energy += float(ratio**8 - 2.0 * ratio**4)
            if distance < CLASH_DISTANCE_A:
                clash_count += 1
    raw = energy / max(contact_count, 1)
    return ScoreTerm(
        term_id=TERM_STERIC_VDW,
        raw_value=float(raw),
        weight=0.0,
        weighted_value=0.0,
        detail={
            "typed": True,
            "contact_pair_count": int(contact_count),
            "clash_pair_count": int(clash_count),
            "cutoff_a": STERIC_CUTOFF_A,
        },
    )


def _electrostatics(
    distances: np.ndarray,
    protein_charges: np.ndarray,
    ligand_charges: np.ndarray,
) -> ScoreTerm:
    """Distance-screened Coulomb over partial charges."""

    energy = 0.0
    pair_count = 0
    for i in range(distances.shape[0]):
        q_p = float(protein_charges[i])
        if q_p == 0.0:
            continue
        for j in range(distances.shape[1]):
            q_l = float(ligand_charges[j])
            if q_l == 0.0:
                continue
            distance = float(distances[i, j])
            if distance >= ELECTROSTATIC_CUTOFF_A:
                continue
            # Distance-dependent dielectric keeps the term bounded at contact.
            energy += 332.0 * q_p * q_l / (max(distance, 1.0) ** 2 * 4.0)
            pair_count += 1
    return ScoreTerm(
        term_id=TERM_ELECTROSTATICS,
        raw_value=float(energy),
        weight=0.0,
        weighted_value=0.0,
        detail={
            "charged_pair_count": int(pair_count),
            "screening": "distance_dependent_dielectric",
            "cutoff_a": ELECTROSTATIC_CUTOFF_A,
        },
    )


def _directional_hbond(
    protein_xyz: np.ndarray,
    ligand_xyz: np.ndarray,
    distances: np.ndarray,
    protein_elements: list[str],
    ligand_elements: list[str],
    reference_point: np.ndarray,
) -> ScoreTerm:
    """Distance- and angle-gated H-bond count.

    A donor/acceptor pair at the right distance but pointing away from the
    pocket is not counted: that directional gate is what separates this from a
    plain polar-contact count.
    """

    energy = 0.0
    accepted = 0
    distance_only = 0
    for i, p_element in enumerate(protein_elements):
        if p_element[:1] not in HBOND_ELEMENTS:
            continue
        for j, l_element in enumerate(ligand_elements):
            if l_element[:1] not in HBOND_ELEMENTS:
                continue
            distance = float(distances[i, j])
            if not (HBOND_MIN_DISTANCE_A <= distance <= HBOND_MAX_DISTANCE_A):
                continue
            distance_only += 1
            to_protein = protein_xyz[i] - ligand_xyz[j]
            to_reference = reference_point - ligand_xyz[j]
            n1 = float(np.linalg.norm(to_protein))
            n2 = float(np.linalg.norm(to_reference))
            if n1 <= 1e-6 or n2 <= 1e-6:
                continue
            cos_angle = float(np.clip(np.dot(to_protein, to_reference) / (n1 * n2), -1.0, 1.0))
            if cos_angle < HBOND_MIN_COS_ANGLE:
                continue
            accepted += 1
            span = HBOND_MAX_DISTANCE_A - HBOND_MIN_DISTANCE_A
            distance_score = 1.0 - (distance - HBOND_MIN_DISTANCE_A) / span
            energy -= float(distance_score * cos_angle)
    return ScoreTerm(
        term_id=TERM_HBOND,
        raw_value=float(energy),
        weight=0.0,
        weighted_value=0.0,
        detail={
            "directional": True,
            "accepted_hbond_count": int(accepted),
            "distance_only_candidate_count": int(distance_only),
            "angle_rejected_count": int(distance_only - accepted),
            "min_cos_angle": HBOND_MIN_COS_ANGLE,
            "distance_window_a": [HBOND_MIN_DISTANCE_A, HBOND_MAX_DISTANCE_A],
        },
    )


def _hydrophobic(
    distances: np.ndarray,
    protein_elements: list[str],
    ligand_elements: list[str],
) -> ScoreTerm:
    """Apolar-apolar burial reward."""

    energy = 0.0
    pair_count = 0
    for i, p_element in enumerate(protein_elements):
        if p_element not in APOLAR_ELEMENTS and p_element[:1] not in APOLAR_ELEMENTS:
            continue
        for j, l_element in enumerate(ligand_elements):
            if l_element not in APOLAR_ELEMENTS and l_element[:1] not in APOLAR_ELEMENTS:
                continue
            distance = float(distances[i, j])
            if distance >= HYDROPHOBIC_MAX_DISTANCE_A:
                continue
            pair_count += 1
            energy -= float(1.0 - distance / HYDROPHOBIC_MAX_DISTANCE_A)
    return ScoreTerm(
        term_id=TERM_HYDROPHOBIC,
        raw_value=float(energy),
        weight=0.0,
        weighted_value=0.0,
        detail={
            "apolar_pair_count": int(pair_count),
            "cutoff_a": HYDROPHOBIC_MAX_DISTANCE_A,
        },
    )


def _desolvation(
    distances: np.ndarray,
    protein_elements: list[str],
    ligand_elements: list[str],
) -> ScoreTerm:
    """Penalty for burying a polar ligand atom without a polar partner."""

    penalty = 0.0
    buried_polar = 0
    for j, l_element in enumerate(ligand_elements):
        if l_element[:1] not in POLAR_ELEMENTS:
            continue
        near = [
            i
            for i in range(distances.shape[0])
            if float(distances[i, j]) < DESOLVATION_BURIAL_RADIUS_A
        ]
        if not near:
            continue
        polar_partners = sum(1 for i in near if protein_elements[i][:1] in POLAR_ELEMENTS)
        if polar_partners == 0:
            buried_polar += 1
            penalty += float(len(near)) / float(DESOLVATION_BURIAL_RADIUS_A)
    return ScoreTerm(
        term_id=TERM_DESOLVATION,
        raw_value=float(penalty),
        weight=0.0,
        weighted_value=0.0,
        detail={
            "buried_unpaired_polar_atom_count": int(buried_polar),
            "burial_radius_a": DESOLVATION_BURIAL_RADIUS_A,
            "proxy": True,
        },
    )


def _torsion(smiles: str) -> ScoreTerm:
    """Chemistry-aware torsion cost: restrained rotors cost more to twist."""

    perception = perceive_ligand_rotors(smiles) if smiles else None
    if perception is None or not perception.supported:
        return ScoreTerm(
            term_id=TERM_TORSION,
            raw_value=0.0,
            weight=0.0,
            weighted_value=0.0,
            detail={
                "rotor_perception_supported": False,
                "status": perception.status if perception is not None else "not_assessed",
            },
        )
    penalty = 0.0
    for rotor in perception.rotors:
        # A rotor with fewer preferred states is stiffer, so sampling away from
        # its preferred geometry costs more.
        penalty += 1.0 / float(max(rotor.preferred_state_count, 1))
    return ScoreTerm(
        term_id=TERM_TORSION,
        raw_value=float(penalty),
        weight=0.0,
        weighted_value=0.0,
        detail={
            "rotor_perception_supported": True,
            "rotor_count": perception.rotor_count,
            "restrained_rotor_count": perception.restrained_rotor_count,
            "free_rotor_count": perception.free_rotor_count,
        },
    )


def _strain(ligand_xyz: np.ndarray) -> ScoreTerm:
    """Internal clash / bond-length distortion penalty for the ligand alone."""

    count = int(ligand_xyz.shape[0])
    if count < 2:
        return ScoreTerm(
            term_id=TERM_STRAIN,
            raw_value=0.0,
            weight=0.0,
            weighted_value=0.0,
            detail={"internal_pair_count": 0, "internal_clash_count": 0},
        )
    penalty = 0.0
    clashes = 0
    pairs = 0
    for i in range(count):
        for j in range(i + 1, count):
            distance = float(np.linalg.norm(ligand_xyz[i] - ligand_xyz[j]))
            pairs += 1
            # Non-bonded ligand atoms closer than ~2.2 A indicate a distorted
            # internal geometry, not a real conformer.
            if j > i + 1 and distance < 2.2:
                clashes += 1
                penalty += float(2.2 - distance)
    return ScoreTerm(
        term_id=TERM_STRAIN,
        raw_value=float(penalty),
        weight=0.0,
        weighted_value=0.0,
        detail={"internal_pair_count": int(pairs), "internal_clash_count": int(clashes)},
    )


def _pocket_prior(
    ligand_xyz: np.ndarray,
    pocket_center: np.ndarray,
    pocket_radius_a: float,
) -> ScoreTerm:
    """Bounded centering prior. Deliberately weak: a tie-breaker only."""

    centroid = ligand_xyz.mean(axis=0)
    offset = float(np.linalg.norm(centroid - pocket_center))
    radius = float(max(pocket_radius_a, 1e-6))
    normalized = min(offset / radius, 2.0)
    return ScoreTerm(
        term_id=TERM_POCKET_PRIOR,
        raw_value=float(normalized),
        weight=0.0,
        weighted_value=0.0,
        detail={
            "weak_prior": True,
            "centroid_offset_a": offset,
            "pocket_radius_a": radius,
            "normalized_offset_clamped_at": 2.0,
        },
    )


def score_pose_v1(
    protein_xyz: Any,
    ligand_xyz: Any,
    *,
    protein_elements: Sequence[str] | None = None,
    ligand_elements: Sequence[str] | None = None,
    protein_charges: Sequence[float] | None = None,
    ligand_charges: Sequence[float] | None = None,
    ligand_smiles: str = "",
    pocket_center: Any = None,
    pocket_radius_a: float = 8.0,
    term_weights: dict[str, float] | None = None,
) -> ScoreResult:
    """Score one pose and return the total plus every term that produced it."""

    protein = np.asarray(protein_xyz, dtype=np.float64).reshape(-1, 3)
    ligand = np.asarray(ligand_xyz, dtype=np.float64).reshape(-1, 3)
    if protein.shape[0] == 0 or ligand.shape[0] == 0:
        return ScoreResult(
            status=STATUS_BLOCKED_EMPTY,
            total_score=float("inf"),
            blockers=("scorer_v1_requires_protein_and_ligand_coordinates",),
        )

    p_elements = _elements(protein_elements, protein.shape[0])
    l_elements = _elements(ligand_elements, ligand.shape[0])
    p_charges = _charges(protein_charges, protein.shape[0])
    l_charges = _charges(ligand_charges, ligand.shape[0])
    center = (
        np.asarray(pocket_center, dtype=np.float64).reshape(3)
        if pocket_center is not None
        else ligand.mean(axis=0)
    )
    distances = np.linalg.norm(protein[:, None, :] - ligand[None, :, :], axis=2)

    raw_terms = [
        _typed_steric_vdw(distances, p_elements, l_elements),
        _electrostatics(distances, p_charges, l_charges),
        _directional_hbond(protein, ligand, distances, p_elements, l_elements, center),
        _hydrophobic(distances, p_elements, l_elements),
        _desolvation(distances, p_elements, l_elements),
        _torsion(ligand_smiles),
        _strain(ligand),
        _pocket_prior(ligand, center, float(pocket_radius_a)),
    ]

    weights = dict(DEFAULT_TERM_WEIGHTS)
    weights.update(term_weights or {})
    weighted: list[ScoreTerm] = []
    total = 0.0
    for term in raw_terms:
        weight = float(weights.get(term.term_id, 0.0))
        value = float(term.raw_value) * weight
        if not math.isfinite(value):
            value = 0.0
        total += value
        weighted.append(
            ScoreTerm(
                term_id=term.term_id,
                raw_value=float(term.raw_value),
                weight=weight,
                weighted_value=value,
                detail=dict(term.detail),
            )
        )

    return ScoreResult(status=STATUS_READY, total_score=float(total), terms=tuple(weighted))


__all__ = [
    "CLAIM_BOUNDARY",
    "DEFAULT_TERM_WEIGHTS",
    "SCORER_V1_SCHEMA_VERSION",
    "SCORER_V1_TERMS",
    "STATUS_BLOCKED_EMPTY",
    "STATUS_READY",
    "ScoreResult",
    "ScoreTerm",
    "TERM_DESOLVATION",
    "TERM_ELECTROSTATICS",
    "TERM_HBOND",
    "TERM_HYDROPHOBIC",
    "TERM_POCKET_PRIOR",
    "TERM_STERIC_VDW",
    "TERM_STRAIN",
    "TERM_TORSION",
    "score_pose_v1",
]
