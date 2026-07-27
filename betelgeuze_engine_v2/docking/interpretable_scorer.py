"""Uncalibrated, term-decomposed pose-ordering scorer for Engine v2.

This scorer is intentionally limited to an authenticated known-pocket problem
whose validity context already binds explicit ligand/receptor elements and a
versioned vdW contact policy. It computes a deterministic dimensionless proxy:

* ligand nonbonded overlap penalty;
* receptor-ligand overlap penalty;
* bounded near-contact reward;
* pocket-centroid displacement penalty;
* normalized torsion-magnitude penalty.

All receptor contact enumeration is sparse and capacity-bounded. No element,
charge, hydrogen-bond, protonation, desolvation, or chemistry state is inferred.
The score is not calibrated, is not an affinity/free-energy estimate, and is not
validated for docking ranking or any product claim.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from types import MappingProxyType

import torch

from .authority import AuthenticatedDockingProblem, DockingAuthorityError
from .contact_validity import ElementAwarePoseValidityContext
from .proposals import DockingProposal
from .scoring import (
    DockingScoreDescriptor,
    ScoreDirection,
    component_contract_fingerprint,
)


INTERPRETABLE_POSE_SCORE_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_interpretable_pose_score_config/1.0.0"
)
INTERPRETABLE_POSE_SCORE_TERMS_SCHEMA_ID = (
    "betelgeuze.engine_v2_interpretable_pose_score_terms/1.0.0"
)
INTERPRETABLE_POSE_SCORER_ID = (
    "betelgeuze.engine_v2_interpretable_pose_proxy"
)
INTERPRETABLE_POSE_SCORER_VERSION = "0.1.0"
INTERPRETABLE_POSE_SCORE_ID = (
    "betelgeuze.engine_v2_interpretable_pose_proxy/0.1.0"
)
INTERPRETABLE_POSE_APPLICABILITY_DOMAIN_ID = (
    "authenticated_known_pocket_acyclic_common_element_subset_v0"
)
INTERPRETABLE_POSE_SCORE_ALGORITHM_ID = (
    "betelgeuze.engine_v2_sparse_vdw_contact_pocket_torsion_proxy/1.0.0"
)
MAX_INTERPRETABLE_SCORER_RECEPTOR_CANDIDATE_PAIRS = 4_000_000
MAX_INTERPRETABLE_SCORER_LIGAND_PAIR_CHECKS = 2_000_000

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class InterpretablePoseScorerError(DockingAuthorityError):
    """The interpretable scorer cannot satisfy its bounded contract."""


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
        raise InterpretablePoseScorerError(
            "interpretable score state is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    text = str(value or "").strip().lower()
    if _SHA256_RE.fullmatch(text) is None:
        raise InterpretablePoseScorerError(
            f"{name} must be a lowercase SHA-256"
        )
    return text


def _finite_nonnegative(value: object, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise InterpretablePoseScorerError(
            f"{name} must be finite and non-negative"
        )
    return result


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise InterpretablePoseScorerError(
            f"{name} must be an integer in [{minimum},{maximum}]"
        )
    return value


def _cell_key(
    coordinate: torch.Tensor,
    cell_size: float,
) -> tuple[int, int, int]:
    return tuple(
        int(math.floor(float(value) / cell_size))
        for value in coordinate.tolist()
    )


def _float_projection(value: float) -> str:
    if not math.isfinite(value):
        raise InterpretablePoseScorerError(
            "score terms must contain finite values"
        )
    return value.hex()


@dataclass(frozen=True, slots=True)
class InterpretablePoseScoreConfig:
    receptor_overlap_weight: float = 25.0
    ligand_overlap_weight: float = 25.0
    contact_reward_weight: float = 1.0
    pocket_center_weight: float = 0.5
    torsion_weight: float = 0.05
    overlap_onset_ratio: float = 1.0
    contact_ratio_maximum: float = 1.25
    max_ligand_pair_checks: int = 250_000
    max_receptor_candidate_pairs: int = 1_000_000
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for name in (
            "receptor_overlap_weight",
            "ligand_overlap_weight",
            "contact_reward_weight",
            "pocket_center_weight",
            "torsion_weight",
        ):
            object.__setattr__(
                self,
                name,
                _finite_nonnegative(getattr(self, name), name=name),
            )
        overlap = float(self.overlap_onset_ratio)
        contact_maximum = float(self.contact_ratio_maximum)
        if not math.isfinite(overlap) or not 0.25 <= overlap <= 1.25:
            raise InterpretablePoseScorerError(
                "overlap_onset_ratio must be finite and in [0.25,1.25]"
            )
        if (
            not math.isfinite(contact_maximum)
            or contact_maximum <= overlap
            or contact_maximum > 2.0
        ):
            raise InterpretablePoseScorerError(
                "contact_ratio_maximum must be greater than overlap onset and <= 2"
            )
        object.__setattr__(self, "overlap_onset_ratio", overlap)
        object.__setattr__(self, "contact_ratio_maximum", contact_maximum)
        object.__setattr__(
            self,
            "max_ligand_pair_checks",
            _exact_int(
                self.max_ligand_pair_checks,
                name="max_ligand_pair_checks",
                minimum=0,
                maximum=MAX_INTERPRETABLE_SCORER_LIGAND_PAIR_CHECKS,
            ),
        )
        object.__setattr__(
            self,
            "max_receptor_candidate_pairs",
            _exact_int(
                self.max_receptor_candidate_pairs,
                name="max_receptor_candidate_pairs",
                minimum=0,
                maximum=MAX_INTERPRETABLE_SCORER_RECEPTOR_CANDIDATE_PAIRS,
            ),
        )
        object.__setattr__(
            self,
            "_fingerprint_sha256",
            _sha256(self._projection()),
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": INTERPRETABLE_POSE_SCORE_CONFIG_SCHEMA_ID,
            "algorithm_id": INTERPRETABLE_POSE_SCORE_ALGORITHM_ID,
            "receptor_overlap_weight_hex": self.receptor_overlap_weight.hex(),
            "ligand_overlap_weight_hex": self.ligand_overlap_weight.hex(),
            "contact_reward_weight_hex": self.contact_reward_weight.hex(),
            "pocket_center_weight_hex": self.pocket_center_weight.hex(),
            "torsion_weight_hex": self.torsion_weight.hex(),
            "overlap_onset_ratio_hex": self.overlap_onset_ratio.hex(),
            "contact_ratio_maximum_hex": self.contact_ratio_maximum.hex(),
            "max_ligand_pair_checks": self.max_ligand_pair_checks,
            "max_receptor_candidate_pairs": self.max_receptor_candidate_pairs,
            "score_unit": None,
            "calibrated": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise InterpretablePoseScorerError(
                "interpretable score config changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "fingerprint_sha256": self.fingerprint_sha256,
        }


@dataclass(frozen=True, slots=True)
class InterpretablePoseScoreTerms:
    proposal_fingerprint_sha256: str
    authority_input_receipt_sha256: str
    config_fingerprint_sha256: str
    ligand_overlap_penalty: float
    receptor_overlap_penalty: float
    contact_reward: float
    pocket_center_penalty: float
    torsion_penalty: float
    total_score: float
    ligand_pair_count: int
    receptor_candidate_pair_count: int
    favorable_contact_count: int
    minimum_ligand_vdw_ratio: float
    minimum_receptor_vdw_ratio: float
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for name in (
            "proposal_fingerprint_sha256",
            "authority_input_receipt_sha256",
            "config_fingerprint_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        for name in (
            "ligand_overlap_penalty",
            "receptor_overlap_penalty",
            "contact_reward",
            "pocket_center_penalty",
            "torsion_penalty",
            "total_score",
            "minimum_ligand_vdw_ratio",
            "minimum_receptor_vdw_ratio",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise InterpretablePoseScorerError(
                    f"{name} must be finite"
                )
            object.__setattr__(self, name, value)
        for name in (
            "ligand_pair_count",
            "receptor_candidate_pair_count",
            "favorable_contact_count",
        ):
            value = int(getattr(self, name))
            if value < 0:
                raise InterpretablePoseScorerError(
                    f"{name} must be non-negative"
                )
            object.__setattr__(self, name, value)
        object.__setattr__(
            self,
            "_receipt_sha256",
            _sha256(self._projection()),
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": INTERPRETABLE_POSE_SCORE_TERMS_SCHEMA_ID,
            "score_id": INTERPRETABLE_POSE_SCORE_ID,
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "authority_input_receipt_sha256": (
                self.authority_input_receipt_sha256
            ),
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "ligand_overlap_penalty_hex": _float_projection(
                self.ligand_overlap_penalty
            ),
            "receptor_overlap_penalty_hex": _float_projection(
                self.receptor_overlap_penalty
            ),
            "contact_reward_hex": _float_projection(self.contact_reward),
            "pocket_center_penalty_hex": _float_projection(
                self.pocket_center_penalty
            ),
            "torsion_penalty_hex": _float_projection(self.torsion_penalty),
            "total_score_hex": _float_projection(self.total_score),
            "ligand_pair_count": self.ligand_pair_count,
            "receptor_candidate_pair_count": (
                self.receptor_candidate_pair_count
            ),
            "favorable_contact_count": self.favorable_contact_count,
            "minimum_ligand_vdw_ratio_hex": _float_projection(
                self.minimum_ligand_vdw_ratio
            ),
            "minimum_receptor_vdw_ratio_hex": _float_projection(
                self.minimum_receptor_vdw_ratio
            ),
            "calibrated": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise InterpretablePoseScorerError(
                "interpretable score terms changed after construction"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
        }


class InterpretablePoseScorerV0:
    scorer_id = INTERPRETABLE_POSE_SCORER_ID
    scorer_version = INTERPRETABLE_POSE_SCORER_VERSION
    validated_for_docking_ranking = False

    def __init__(
        self,
        authority: AuthenticatedDockingProblem,
        *,
        implementation_source_sha256: str,
        config: InterpretablePoseScoreConfig | None = None,
    ) -> None:
        if not isinstance(authority, AuthenticatedDockingProblem):
            raise TypeError("authority must be AuthenticatedDockingProblem")
        if not isinstance(
            authority.validity_context,
            ElementAwarePoseValidityContext,
        ):
            raise InterpretablePoseScorerError(
                "interpretable scorer requires element-aware authority"
            )
        selected_config = config or InterpretablePoseScoreConfig()
        if not isinstance(selected_config, InterpretablePoseScoreConfig):
            raise TypeError("config must be InterpretablePoseScoreConfig")
        authority.input_receipt_sha256
        authority.validity_context.assert_integrity()
        self._authority = authority
        self._context = authority.validity_context
        self._config = selected_config
        self.problem_fingerprint_sha256 = (
            authority.problem.fingerprint_sha256
        )
        self.implementation_source_sha256 = _digest(
            implementation_source_sha256,
            name="implementation_source_sha256",
        )
        self.config_fingerprint_sha256 = selected_config.fingerprint_sha256
        self.score_descriptor = DockingScoreDescriptor(
            score_id=INTERPRETABLE_POSE_SCORE_ID,
            direction=ScoreDirection.MINIMIZE,
            unit=None,
            semantics=(
                "uncalibrated_dimensionless_sparse_vdw_contact_pocket_"
                "and_torsion_pose_ordering_proxy"
            ),
            calibrated=False,
            applicability_domain_id=(
                INTERPRETABLE_POSE_APPLICABILITY_DOMAIN_ID
            ),
        )
        self._receptor_cells = self._build_receptor_cells()

    @property
    def authority_input_receipt_sha256(self) -> str:
        return self._authority.input_receipt_sha256

    @property
    def config(self) -> InterpretablePoseScoreConfig:
        return self._config

    @property
    def contract_fingerprint_sha256(self) -> str:
        return component_contract_fingerprint(
            self,
            kind="scorer",
            expected_problem_fingerprint_sha256=(
                self.problem_fingerprint_sha256
            ),
        )

    def _build_receptor_cells(
        self,
    ) -> Mapping[tuple[int, int, int], tuple[int, ...]]:
        cell_size = self._context.contact_policy.cell_size_angstrom
        rows: dict[tuple[int, int, int], list[int]] = defaultdict(list)
        receptor = self._context.receptor_coordinates
        for index in range(len(self._context.receptor_elements)):
            rows[_cell_key(receptor[index], cell_size)].append(index)
        return MappingProxyType(
            {
                key: tuple(values)
                for key, values in sorted(rows.items())
            }
        )

    def _assert_proposal(self, proposal: DockingProposal) -> None:
        if not isinstance(proposal, DockingProposal):
            raise TypeError("proposal must be DockingProposal")
        self._authority.input_receipt_sha256
        self._context.assert_integrity()
        proposal.assert_integrity()
        if (
            proposal.problem_fingerprint_sha256
            != self.problem_fingerprint_sha256
        ):
            raise InterpretablePoseScorerError(
                "proposal is cross-wired to another docking problem"
            )
        if (
            proposal.search_space_fingerprint_sha256
            != self._authority.search_space.fingerprint_sha256
        ):
            raise InterpretablePoseScorerError(
                "proposal is cross-wired to another search space"
            )

    def score_terms(
        self,
        proposal: DockingProposal,
    ) -> InterpretablePoseScoreTerms:
        self._assert_proposal(proposal)
        config = self._config
        context = self._context
        policy = context.contact_policy
        pose = proposal.coordinates.detach().to(
            dtype=torch.float64,
            device="cpu",
        )
        exclusions = set(context.excluded_nonbonded_pairs)

        ligand_overlap = 0.0
        ligand_pair_count = 0
        minimum_ligand_ratio = 999.0
        for first in range(len(context.ligand_elements)):
            first_radius = policy.radius(context.ligand_elements[first])
            for second in range(first + 1, len(context.ligand_elements)):
                if (first, second) in exclusions:
                    continue
                ligand_pair_count += 1
                if ligand_pair_count > config.max_ligand_pair_checks:
                    raise InterpretablePoseScorerError(
                        "interpretable ligand pair capacity exceeded"
                    )
                second_radius = policy.radius(context.ligand_elements[second])
                distance = float(
                    torch.linalg.vector_norm(
                        pose[first] - pose[second]
                    ).item()
                )
                ratio = distance / (first_radius + second_radius)
                minimum_ligand_ratio = min(minimum_ligand_ratio, ratio)
                if ratio < config.overlap_onset_ratio:
                    normalized = (
                        config.overlap_onset_ratio - ratio
                    ) / config.overlap_onset_ratio
                    ligand_overlap += normalized * normalized

        receptor_overlap = 0.0
        contact_reward = 0.0
        favorable_contact_count = 0
        receptor_candidate_pair_count = 0
        minimum_receptor_ratio = 999.0
        cell_size = policy.cell_size_angstrom
        maximum_radius = max(policy.radii_angstrom.values())
        maximum_cutoff = (
            maximum_radius + maximum_radius
        ) * config.contact_ratio_maximum
        cell_radius = max(1, int(math.ceil(maximum_cutoff / cell_size)))
        receptor = context.receptor_coordinates
        for ligand_index, ligand_element in enumerate(
            context.ligand_elements
        ):
            ligand_radius = policy.radius(ligand_element)
            center = _cell_key(pose[ligand_index], cell_size)
            for offset_x in range(-cell_radius, cell_radius + 1):
                for offset_y in range(-cell_radius, cell_radius + 1):
                    for offset_z in range(-cell_radius, cell_radius + 1):
                        key = (
                            center[0] + offset_x,
                            center[1] + offset_y,
                            center[2] + offset_z,
                        )
                        for receptor_index in self._receptor_cells.get(key, ()):
                            receptor_candidate_pair_count += 1
                            if (
                                receptor_candidate_pair_count
                                > config.max_receptor_candidate_pairs
                            ):
                                raise InterpretablePoseScorerError(
                                    "interpretable receptor candidate-pair capacity exceeded"
                                )
                            receptor_radius = policy.radius(
                                context.receptor_elements[receptor_index]
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
                            if ratio > config.contact_ratio_maximum:
                                continue
                            minimum_receptor_ratio = min(
                                minimum_receptor_ratio,
                                ratio,
                            )
                            if ratio < config.overlap_onset_ratio:
                                normalized = (
                                    config.overlap_onset_ratio - ratio
                                ) / config.overlap_onset_ratio
                                receptor_overlap += normalized * normalized
                            else:
                                favorable_contact_count += 1
                                contact_reward += (
                                    config.contact_ratio_maximum - ratio
                                ) / (
                                    config.contact_ratio_maximum
                                    - config.overlap_onset_ratio
                                )

        centroid_distance = float(
            torch.linalg.vector_norm(
                pose.mean(dim=0) - self._authority.pocket.center
            ).item()
        )
        normalized_centroid = (
            centroid_distance / self._authority.pocket.radius_angstrom
        )
        pocket_center_penalty = normalized_centroid * normalized_centroid
        rotatable_mask = self._authority.search_space.rotatable_mask
        normalized_torsions = (
            proposal.torsion_angles[rotatable_mask] / math.pi
        )
        torsion_penalty = float(
            normalized_torsions.square().sum().item()
        )

        weighted_ligand_overlap = (
            config.ligand_overlap_weight * ligand_overlap
        )
        weighted_receptor_overlap = (
            config.receptor_overlap_weight * receptor_overlap
        )
        weighted_contact_reward = (
            config.contact_reward_weight * contact_reward
        )
        weighted_pocket = (
            config.pocket_center_weight * pocket_center_penalty
        )
        weighted_torsion = config.torsion_weight * torsion_penalty
        total = (
            weighted_ligand_overlap
            + weighted_receptor_overlap
            - weighted_contact_reward
            + weighted_pocket
            + weighted_torsion
        )
        if not math.isfinite(total):
            raise InterpretablePoseScorerError(
                "interpretable pose score is non-finite"
            )
        terms = InterpretablePoseScoreTerms(
            proposal_fingerprint_sha256=proposal.fingerprint_sha256,
            authority_input_receipt_sha256=(
                self._authority.input_receipt_sha256
            ),
            config_fingerprint_sha256=config.fingerprint_sha256,
            ligand_overlap_penalty=weighted_ligand_overlap,
            receptor_overlap_penalty=weighted_receptor_overlap,
            contact_reward=weighted_contact_reward,
            pocket_center_penalty=weighted_pocket,
            torsion_penalty=weighted_torsion,
            total_score=total,
            ligand_pair_count=ligand_pair_count,
            receptor_candidate_pair_count=(
                receptor_candidate_pair_count
            ),
            favorable_contact_count=favorable_contact_count,
            minimum_ligand_vdw_ratio=minimum_ligand_ratio,
            minimum_receptor_vdw_ratio=minimum_receptor_ratio,
        )
        self._assert_proposal(proposal)
        return terms

    def score(self, proposal: DockingProposal) -> float:
        return self.score_terms(proposal).total_score

    def qualification_document(self) -> dict[str, object]:
        projection = {
            "schema_id": (
                "betelgeuze.engine_v2_interpretable_pose_scorer_status/1.0.0"
            ),
            "scorer_id": self.scorer_id,
            "scorer_version": self.scorer_version,
            "score_descriptor": self.score_descriptor.to_dict(),
            "problem_fingerprint_sha256": (
                self.problem_fingerprint_sha256
            ),
            "authority_input_receipt_sha256": (
                self.authority_input_receipt_sha256
            ),
            "implementation_source_sha256": (
                self.implementation_source_sha256
            ),
            "config_fingerprint_sha256": (
                self.config_fingerprint_sha256
            ),
            "component_contract_fingerprint_sha256": (
                self.contract_fingerprint_sha256
            ),
            "validated_for_docking_ranking": False,
            "affinity_estimate": False,
            "free_energy_estimate": False,
            "calibrated": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "product_qualified": False,
            "claim_safe": False,
        }
        projection["document_sha256"] = _sha256(projection)
        return projection


__all__ = [
    "INTERPRETABLE_POSE_APPLICABILITY_DOMAIN_ID",
    "INTERPRETABLE_POSE_SCORE_ALGORITHM_ID",
    "INTERPRETABLE_POSE_SCORE_CONFIG_SCHEMA_ID",
    "INTERPRETABLE_POSE_SCORE_ID",
    "INTERPRETABLE_POSE_SCORE_TERMS_SCHEMA_ID",
    "INTERPRETABLE_POSE_SCORER_ID",
    "INTERPRETABLE_POSE_SCORER_VERSION",
    "MAX_INTERPRETABLE_SCORER_LIGAND_PAIR_CHECKS",
    "MAX_INTERPRETABLE_SCORER_RECEPTOR_CANDIDATE_PAIRS",
    "InterpretablePoseScoreConfig",
    "InterpretablePoseScoreTerms",
    "InterpretablePoseScorerError",
    "InterpretablePoseScorerV0",
]
