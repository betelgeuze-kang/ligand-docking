"""First-round correctness hardening for the Engine v2 stacked development head.

This module is intentionally installed from :mod:`betelgeuze_engine_v2` after
all existing public subpackages have loaded.  It closes four compatibility gaps
without promoting any scientific or product claim:

* minimization defaults are constrained by the actual compact-neighbor caps;
* proposal identifiers and floating-point fingerprints have one deterministic
  cross-language policy;
* docked-pose diversity supports symmetry-aware direct receptor-frame RMSD;
* pose-validity capacities are hard-bounded and public benchmark policy values
  are immutable.

The compatibility installer is idempotent.  A future API-major release should
move these definitions into their owning modules directly.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import json
import math
import sys
from typing import Sequence

import torch

from betelgeuze_engine_v2.geometry import (
    MAX_COMPACT_ATOMS_PER_CELL,
    MAX_COMPACT_NEIGHBORS,
)


STACK_ROUND1_HARDENING_SCHEMA_ID = (
    "betelgeuze.engine_v2_stack_round1_hardening/1.0.0"
)
PROPOSAL_NUMERIC_POLICY_ID = (
    "betelgeuze.engine_v2_proposal_numeric_identity/1.0.0"
)
RESEARCH_POSE_VALIDITY_POLICY_ID = (
    "betelgeuze.engine_v2_pose_validity_policy/research-custom/1.0.0"
)
PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID = (
    "betelgeuze.engine_v2_pose_validity_policy/public-redocking/1.0.0"
)
MAX_POSE_VALIDITY_PAIR_CHECKS = 2_000_000
MAX_POSE_VALIDITY_CROSS_CHECKS = 4_000_000

_DIRECT_SYMMETRY_MODE: ContextVar[bool] = ContextVar(
    "betelgeuze_direct_symmetry_mode",
    default=False,
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _tensor_identity_payload(value: torch.Tensor) -> dict[str, object]:
    tensor = value.detach().to(device="cpu").contiguous()
    return {
        "dtype": str(tensor.dtype).removeprefix("torch."),
        "shape": [int(size) for size in tensor.shape],
        "values_binary64_hex": [
            float(item).hex() for item in tensor.reshape(-1).tolist()
        ],
    }


def _stable_candidate_id(
    *,
    proposal_index: int,
    seed: int,
    problem_fingerprint_sha256: str,
    search_space_fingerprint_sha256: str,
) -> str:
    identity = _sha256(
        {
            "schema_id": "betelgeuze.engine_v2_docking_candidate_identity/1.0.0",
            "proposal_index": int(proposal_index),
            "seed": int(seed),
            "problem_fingerprint_sha256": problem_fingerprint_sha256,
            "search_space_fingerprint_sha256": search_space_fingerprint_sha256,
        }
    )
    return f"pose-{int(proposal_index):05d}-{identity[:12]}"


def _replace_reference_minimization_config() -> None:
    from betelgeuze_engine_v2 import physics as physics_package
    from betelgeuze_engine_v2.physics import reference_minimization as module

    old_class = module.ReferenceMinimizationConfig
    if getattr(old_class, "_betelgeuze_round1_hardened", False):
        return

    @dataclass(frozen=True)
    class ReferenceMinimizationConfig:
        """Numerical and capacity bounds aligned with compact-neighbor limits."""

        max_iterations: int = 100
        max_backtracks: int = 16
        initial_step_size_angstrom2_mol_per_kcal: float = 1.0e-3
        backtrack_factor: float = 0.5
        armijo_constant: float = 1.0e-4
        maximum_atom_displacement_angstrom: float = 0.05
        force_tolerance_kcal_per_mol_angstrom: float = 1.0e-3
        max_neighbors: int = MAX_COMPACT_NEIGHBORS
        max_atoms_per_cell: int = MAX_COMPACT_ATOMS_PER_CELL
        schema_id: str = module.REFERENCE_MINIMIZATION_CONFIG_SCHEMA_ID

        _betelgeuze_round1_hardened = True

        def __post_init__(self) -> None:
            if self.schema_id != module.REFERENCE_MINIMIZATION_CONFIG_SCHEMA_ID:
                raise module.ReferenceMinimizationError(
                    "unsupported minimization config schema"
                )
            object.__setattr__(
                self,
                "max_iterations",
                module._exact_int(
                    self.max_iterations,
                    name="max_iterations",
                    minimum=1,
                    maximum=module.REFERENCE_MINIMIZATION_MAX_ITERATIONS,
                ),
            )
            object.__setattr__(
                self,
                "max_backtracks",
                module._exact_int(
                    self.max_backtracks,
                    name="max_backtracks",
                    minimum=0,
                    maximum=module.REFERENCE_MINIMIZATION_MAX_BACKTRACKS,
                ),
            )
            object.__setattr__(
                self,
                "max_neighbors",
                module._exact_int(
                    self.max_neighbors,
                    name="max_neighbors",
                    minimum=1,
                    maximum=MAX_COMPACT_NEIGHBORS,
                ),
            )
            object.__setattr__(
                self,
                "max_atoms_per_cell",
                module._exact_int(
                    self.max_atoms_per_cell,
                    name="max_atoms_per_cell",
                    minimum=1,
                    maximum=MAX_COMPACT_ATOMS_PER_CELL,
                ),
            )
            for name in (
                "initial_step_size_angstrom2_mol_per_kcal",
                "maximum_atom_displacement_angstrom",
                "force_tolerance_kcal_per_mol_angstrom",
            ):
                object.__setattr__(
                    self,
                    name,
                    module._finite_float(
                        getattr(self, name),
                        name=name,
                        minimum=0.0,
                    ),
                )
            object.__setattr__(
                self,
                "backtrack_factor",
                module._finite_float(
                    self.backtrack_factor,
                    name="backtrack_factor",
                    minimum=0.0,
                    maximum=1.0,
                ),
            )
            if self.backtrack_factor >= 1.0:
                raise module.ReferenceMinimizationError(
                    "backtrack_factor must be < 1"
                )
            object.__setattr__(
                self,
                "armijo_constant",
                module._finite_float(
                    self.armijo_constant,
                    name="armijo_constant",
                    minimum=0.0,
                    maximum=1.0,
                ),
            )
            if self.armijo_constant >= 1.0:
                raise module.ReferenceMinimizationError(
                    "armijo_constant must be < 1"
                )

        def to_dict(self) -> dict[str, object]:
            return {
                "schema_id": self.schema_id,
                "algorithm_id": module.REFERENCE_MINIMIZATION_ALGORITHM_ID,
                "max_iterations": self.max_iterations,
                "max_backtracks": self.max_backtracks,
                "initial_step_size_angstrom2_mol_per_kcal": (
                    self.initial_step_size_angstrom2_mol_per_kcal
                ),
                "backtrack_factor": self.backtrack_factor,
                "armijo_constant": self.armijo_constant,
                "maximum_atom_displacement_angstrom": (
                    self.maximum_atom_displacement_angstrom
                ),
                "force_tolerance_kcal_per_mol_angstrom": (
                    self.force_tolerance_kcal_per_mol_angstrom
                ),
                "max_neighbors": self.max_neighbors,
                "max_atoms_per_cell": self.max_atoms_per_cell,
            }

        @property
        def fingerprint_sha256(self) -> str:
            return module._sha256(self.to_dict())

    module.ReferenceMinimizationConfig = ReferenceMinimizationConfig
    physics_package.ReferenceMinimizationConfig = ReferenceMinimizationConfig
    for loaded in tuple(sys.modules.values()):
        if loaded is not None and getattr(
            loaded, "ReferenceMinimizationConfig", None
        ) is old_class:
            setattr(loaded, "ReferenceMinimizationConfig", ReferenceMinimizationConfig)


def _harden_docking_proposals() -> None:
    from betelgeuze_engine_v2 import docking as docking_package
    from betelgeuze_engine_v2.docking import proposals as module

    if getattr(module, "_BETELGEUZE_ROUND1_PROPOSALS", False):
        return

    original_post_init = module.DockingProposal.__post_init__
    original_assert_integrity = module.DockingProposal.assert_integrity

    def proposal_fingerprint(
        *,
        proposal_index: int,
        seed: int,
        torsion_angles: torch.Tensor,
        rotation: torch.Tensor,
        translation: torch.Tensor,
        problem_fingerprint_sha256: str,
        search_space_fingerprint_sha256: str,
        coordinate_fingerprint_sha256: str,
        parent_proposal_fingerprint_sha256: str = "",
        refiner_id: str = "",
        refiner_version: str = "",
        refinement_receipt_sha256: str = "",
    ) -> str:
        return _sha256(
            {
                "schema_id": "betelgeuze.engine_v2_docking_proposal/3.0.0",
                "numeric_policy_id": PROPOSAL_NUMERIC_POLICY_ID,
                "proposal_index": int(proposal_index),
                "seed": int(seed),
                "problem_fingerprint_sha256": problem_fingerprint_sha256,
                "search_space_fingerprint_sha256": (
                    search_space_fingerprint_sha256
                ),
                "coordinate_fingerprint_sha256": coordinate_fingerprint_sha256,
                "parent_proposal_fingerprint_sha256": (
                    parent_proposal_fingerprint_sha256
                ),
                "refiner_id": refiner_id,
                "refiner_version": refiner_version,
                "refinement_receipt_sha256": refinement_receipt_sha256,
                "torsion_angles": _tensor_identity_payload(torsion_angles),
                "rotation": _tensor_identity_payload(rotation),
                "translation": _tensor_identity_payload(translation),
            }
        )

    def proposal_post_init(self: object) -> None:
        original_post_init(self)
        expected_id = _stable_candidate_id(
            proposal_index=self.proposal_index,
            seed=self.seed,
            problem_fingerprint_sha256=self.problem_fingerprint_sha256,
            search_space_fingerprint_sha256=(
                self.search_space_fingerprint_sha256
            ),
        )
        generated_compatibility_id = (
            f"pose-{self.proposal_index:05d}-{self.fingerprint_sha256[:12]}"
        )
        if self.candidate_id not in {expected_id, generated_compatibility_id}:
            raise module.DockingProposalError(
                "candidate_id is not derived from the immutable proposal identity"
            )
        object.__setattr__(self, "candidate_id", expected_id)

    def proposal_assert_integrity(self: object) -> None:
        original_assert_integrity(self)
        expected_id = _stable_candidate_id(
            proposal_index=self.proposal_index,
            seed=self.seed,
            problem_fingerprint_sha256=self.problem_fingerprint_sha256,
            search_space_fingerprint_sha256=(
                self.search_space_fingerprint_sha256
            ),
        )
        if self.candidate_id != expected_id:
            raise module.DockingProposalError(
                "proposal candidate_id changed after construction"
            )

    module._proposal_fingerprint = proposal_fingerprint
    module.DockingProposal.__post_init__ = proposal_post_init
    module.DockingProposal.assert_integrity = proposal_assert_integrity
    module.PROPOSAL_NUMERIC_POLICY_ID = PROPOSAL_NUMERIC_POLICY_ID
    docking_package.PROPOSAL_NUMERIC_POLICY_ID = PROPOSAL_NUMERIC_POLICY_ID
    module._BETELGEUZE_ROUND1_PROPOSALS = True


def _replace_pose_validity_config() -> None:
    from betelgeuze_engine_v2 import docking as docking_package
    from betelgeuze_engine_v2.docking import validity as module

    old_class = module.PoseValidityConfig
    if getattr(old_class, "_betelgeuze_round1_hardened", False):
        return

    @dataclass(frozen=True)
    class PoseValidityConfig:
        bond_length_tolerance_angstrom: float = 0.15
        ligand_self_clash_angstrom: float = 0.75
        receptor_ligand_clash_angstrom: float = 0.8
        rotation_tolerance: float = 1.0e-6
        chirality_volume_tolerance: float = 1.0e-8
        pocket_radius_angstrom: float | None = None
        max_pair_checks: int = 250_000
        max_cross_checks: int = 1_000_000
        policy_id: str = RESEARCH_POSE_VALIDITY_POLICY_ID

        _betelgeuze_round1_hardened = True

        def __post_init__(self) -> None:
            policy = str(self.policy_id or "").strip()
            if policy not in {
                RESEARCH_POSE_VALIDITY_POLICY_ID,
                PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID,
            }:
                raise module.PoseValidityError(
                    "unsupported pose-validity policy"
                )
            object.__setattr__(self, "policy_id", policy)
            for name in (
                "bond_length_tolerance_angstrom",
                "ligand_self_clash_angstrom",
                "receptor_ligand_clash_angstrom",
                "rotation_tolerance",
                "chirality_volume_tolerance",
            ):
                value = float(getattr(self, name))
                if not math.isfinite(value) or value < 0.0:
                    raise module.PoseValidityError(
                        f"{name} must be finite and non-negative"
                    )
                object.__setattr__(self, name, value)
            if self.pocket_radius_angstrom is not None:
                radius = float(self.pocket_radius_angstrom)
                if not math.isfinite(radius) or radius <= 0.0:
                    raise module.PoseValidityError(
                        "pocket_radius_angstrom must be positive and finite"
                    )
                object.__setattr__(self, "pocket_radius_angstrom", radius)
            pair_checks = int(self.max_pair_checks)
            cross_checks = int(self.max_cross_checks)
            if not 0 <= pair_checks <= MAX_POSE_VALIDITY_PAIR_CHECKS:
                raise module.PoseValidityError(
                    "max_pair_checks exceeds the hard validity capacity"
                )
            if not 0 <= cross_checks <= MAX_POSE_VALIDITY_CROSS_CHECKS:
                raise module.PoseValidityError(
                    "max_cross_checks exceeds the hard validity capacity"
                )
            object.__setattr__(self, "max_pair_checks", pair_checks)
            object.__setattr__(self, "max_cross_checks", cross_checks)
            if policy == PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID:
                expected = {
                    "bond_length_tolerance_angstrom": 0.15,
                    "ligand_self_clash_angstrom": 0.75,
                    "receptor_ligand_clash_angstrom": 0.8,
                    "rotation_tolerance": 1.0e-6,
                    "chirality_volume_tolerance": 1.0e-8,
                    "max_pair_checks": 250_000,
                    "max_cross_checks": 1_000_000,
                }
                for name, expected_value in expected.items():
                    if getattr(self, name) != expected_value:
                        raise module.PoseValidityError(
                            "public benchmark pose-validity policy is immutable"
                        )

        def to_dict(self) -> dict[str, object]:
            return {
                "policy_id": self.policy_id,
                "bond_length_tolerance_angstrom": (
                    self.bond_length_tolerance_angstrom
                ),
                "ligand_self_clash_angstrom": (
                    self.ligand_self_clash_angstrom
                ),
                "receptor_ligand_clash_angstrom": (
                    self.receptor_ligand_clash_angstrom
                ),
                "rotation_tolerance": self.rotation_tolerance,
                "chirality_volume_tolerance": (
                    self.chirality_volume_tolerance
                ),
                "pocket_radius_angstrom": self.pocket_radius_angstrom,
                "max_pair_checks": self.max_pair_checks,
                "max_cross_checks": self.max_cross_checks,
            }

        @property
        def fingerprint_sha256(self) -> str:
            return _sha256(
                {
                    "schema_id": (
                        "betelgeuze.engine_v2_pose_validity_config/3.0.0"
                    ),
                    **self.to_dict(),
                }
            )

    module.PoseValidityConfig = PoseValidityConfig
    module.MAX_POSE_VALIDITY_PAIR_CHECKS = MAX_POSE_VALIDITY_PAIR_CHECKS
    module.MAX_POSE_VALIDITY_CROSS_CHECKS = MAX_POSE_VALIDITY_CROSS_CHECKS
    module.RESEARCH_POSE_VALIDITY_POLICY_ID = RESEARCH_POSE_VALIDITY_POLICY_ID
    module.PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID = (
        PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID
    )
    docking_package.PoseValidityConfig = PoseValidityConfig
    docking_package.MAX_POSE_VALIDITY_PAIR_CHECKS = (
        MAX_POSE_VALIDITY_PAIR_CHECKS
    )
    docking_package.MAX_POSE_VALIDITY_CROSS_CHECKS = (
        MAX_POSE_VALIDITY_CROSS_CHECKS
    )
    docking_package.RESEARCH_POSE_VALIDITY_POLICY_ID = (
        RESEARCH_POSE_VALIDITY_POLICY_ID
    )
    docking_package.PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID = (
        PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID
    )
    for loaded in tuple(sys.modules.values()):
        if loaded is not None and getattr(loaded, "PoseValidityConfig", None) is old_class:
            setattr(loaded, "PoseValidityConfig", PoseValidityConfig)


def _install_symmetry_aware_direct_diversity() -> None:
    from betelgeuze_engine_v2 import docking as docking_package
    from betelgeuze_engine_v2.docking import search as module

    if getattr(module, "_BETELGEUZE_ROUND1_DIRECT_DIVERSITY", False):
        return

    original_pose_distance = module._pose_distance
    original_run = module.run_bounded_docking_search

    def pose_distance(
        first: object,
        second: object,
        *,
        metric: str,
        symmetry_permutations: Sequence[Sequence[int] | torch.Tensor] | None,
    ) -> float:
        if metric == "symmetry_aware_direct_rmsd" or (
            metric == "symmetry_aware_kabsch_rmsd"
            and _DIRECT_SYMMETRY_MODE.get()
        ):
            first.assert_integrity()
            second.assert_integrity()
            return module.symmetry_aware_rmsd(
                first.coordinates,
                second.coordinates,
                permutations=symmetry_permutations,
                align=False,
            ).rmsd_angstrom
        return original_pose_distance(
            first,
            second,
            metric=metric,
            symmetry_permutations=symmetry_permutations,
        )

    def run_bounded_docking_search(
        search_space: object,
        budget: object,
        scorer: object,
        *,
        refiner: object | None = None,
        validity_context: object | None = None,
        diversity_rmsd_angstrom: float = 0.5,
        diversity_metric: str = "direct_rmsd",
        symmetry_permutations: Sequence[Sequence[int] | torch.Tensor] | None = None,
        problem: object | None = None,
        placement_center: torch.Tensor | None = None,
    ) -> object:
        if diversity_metric != "symmetry_aware_direct_rmsd":
            return original_run(
                search_space,
                budget,
                scorer,
                refiner=refiner,
                validity_context=validity_context,
                diversity_rmsd_angstrom=diversity_rmsd_angstrom,
                diversity_metric=diversity_metric,
                symmetry_permutations=symmetry_permutations,
                problem=problem,
                placement_center=placement_center,
            )
        if symmetry_permutations is None:
            raise ValueError(
                "symmetry-aware direct diversity requires explicit permutations"
            )
        token = _DIRECT_SYMMETRY_MODE.set(True)
        try:
            result = original_run(
                search_space,
                budget,
                scorer,
                refiner=refiner,
                validity_context=validity_context,
                diversity_rmsd_angstrom=diversity_rmsd_angstrom,
                diversity_metric="symmetry_aware_kabsch_rmsd",
                symmetry_permutations=symmetry_permutations,
                problem=problem,
                placement_center=placement_center,
            )
        finally:
            _DIRECT_SYMMETRY_MODE.reset(token)
        canonical_permutations = module._canonicalize_symmetry_permutations(
            symmetry_permutations,
            atom_count=search_space.atom_count,
        )
        problem_identity = problem or module.DockingProblemIdentity.unbound()
        unbound_compatibility = (
            validity_context is None and not problem_identity.bound
        )
        search_fingerprint = _sha256(
            {
                "schema_id": "betelgeuze.engine_v2_docking_search/5.0.0",
                "budget": budget.to_dict(),
                "scorer_contract_fingerprint_sha256": (
                    result.scorer_contract_fingerprint_sha256
                ),
                "refiner_contract_fingerprint_sha256": (
                    result.refiner_contract_fingerprint_sha256
                ),
                "score_descriptor": result.score_descriptor.to_dict(),
                "validity_context_fingerprint_sha256": (
                    result.validity_context_fingerprint_sha256
                ),
                "unbound_validity_compatibility": unbound_compatibility,
                "diversity_metric": "symmetry_aware_direct_rmsd",
                "symmetry_permutation_count": len(canonical_permutations),
                "symmetry_permutations": {
                    "atom_count": int(search_space.atom_count),
                    "mappings": [
                        list(permutation)
                        for permutation in canonical_permutations
                    ],
                },
                "problem_fingerprint_sha256": (
                    problem_identity.fingerprint_sha256
                ),
                "search_space_fingerprint_sha256": (
                    search_space.fingerprint_sha256
                ),
                "proposal_fingerprints": [
                    row.proposal_fingerprint_sha256 for row in result.rows
                ],
            }
        )
        object.__setattr__(
            result,
            "diversity_metric",
            "symmetry_aware_direct_rmsd",
        )
        object.__setattr__(
            result,
            "search_fingerprint_sha256",
            search_fingerprint,
        )
        return result

    module._pose_distance = pose_distance
    module.run_bounded_docking_search = run_bounded_docking_search
    docking_package.run_bounded_docking_search = run_bounded_docking_search
    module._BETELGEUZE_ROUND1_DIRECT_DIVERSITY = True


def install_stack_round1_hardening() -> str:
    marker = "_betelgeuze_stack_round1_hardening_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing
    _replace_reference_minimization_config()
    _harden_docking_proposals()
    _replace_pose_validity_config()
    _install_symmetry_aware_direct_diversity()
    receipt = _sha256(
        {
            "schema_id": STACK_ROUND1_HARDENING_SCHEMA_ID,
            "minimization_caps_aligned": True,
            "proposal_numeric_policy_id": PROPOSAL_NUMERIC_POLICY_ID,
            "candidate_id_derived_from_stable_identity": True,
            "symmetry_aware_direct_diversity": True,
            "validity_capacities_hard_bounded": True,
            "public_validity_policy_immutable": True,
            "scientifically_validated": False,
            "claim_safe": False,
        }
    )
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "MAX_POSE_VALIDITY_CROSS_CHECKS",
    "MAX_POSE_VALIDITY_PAIR_CHECKS",
    "PROPOSAL_NUMERIC_POLICY_ID",
    "PUBLIC_BENCHMARK_POSE_VALIDITY_POLICY_ID",
    "RESEARCH_POSE_VALIDITY_POLICY_ID",
    "STACK_ROUND1_HARDENING_SCHEMA_ID",
    "install_stack_round1_hardening",
]
