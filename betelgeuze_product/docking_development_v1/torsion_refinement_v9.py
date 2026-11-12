"""Explicit V9 contact refinement; frozen V7/V8 policy remains unchanged.

V9 searches the same bounded rigid/torsion coordinates without the historical
receptor-penalty window. It retains a V6 baseline and one improving endpoint.
Both still require independent validity and scoring in the consuming pipeline.
This contact objective is neither a force field nor an accuracy qualification.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from types import MappingProxyType

import torch

from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint
from betelgeuze_engine_v2.docking.proposals import DockingProposal
from betelgeuze_engine_v2.docking.torsion_contact_refinement import (
    InteractionAwareTorsionContactConfigV7,
    InteractionAwareTorsionContactEnsembleRefinerV7,
    TorsionContactRefinementError,
    _TorsionOptimizedState,
    _sha256,
)
from .observed_rigid_refinement import ObservedRigidEnsembleV6
from .refinement_work import (
    accepted_refinement_step,
    count_objective,
    refinement_work_records,
    track_refinement,
    trial_objective_attempt,
)

POLICY_ID = "betelgeuze.monotone_retained_torsion_refinement/9.0.0"
RECEIPT_SCHEMA = "betelgeuze.monotone_retained_torsion_receipt/9.0.0"


@dataclass(frozen=True)
class TorsionRefinementBoundsV9:
    receptor_overlap_scale: float = 1.0
    internal_overlap_scale: float = 0.80
    internal_overlap_weight: float = 1.0
    maximum_baseline_v6_steps: int = 20
    maximum_torsions_evaluated: int = 4
    maximum_torsion_steps: int = 4
    maximum_backtracking_evaluations: int = 3
    maximum_torsion_step_radians: float = math.pi / 8.0
    minimum_torsion_step_radians: float = math.pi / 32.0
    maximum_total_torsion_path_radians: float = math.pi / 2.0
    maximum_centroid_offset_angstrom: float = 4.0
    penalty_tolerance: float = 1.0e-18
    epsilon_angstrom: float = 1.0e-9

    def __post_init__(self):
        self.kernel_bounds()

    def kernel_bounds(self):
        # Only movement/objective bounds are shared. The product V9 search owns
        # its selection policy and never consults the historical window fields.
        return InteractionAwareTorsionContactConfigV7(**asdict(self))

    @property
    def fingerprint_sha256(self):
        return _sha256({"policy_id": POLICY_ID, "bounds": asdict(self)})


class InteractionAwareTorsionContactEnsembleRefinerV9(
    InteractionAwareTorsionContactEnsembleRefinerV7
):
    refiner_id = "betelgeuze.product_monotone_retained_torsion_refiner"
    refiner_version = "9.0.0"
    max_retained_candidates_per_source = 2

    def __init__(
        self,
        authority,
        receptor_system,
        ligand_system,
        *,
        implementation_source_sha256,
        v3_proposal_indices,
        bounds=None,
        v2_config=None,
        v3_config=None,
        clearance_config=None,
        radii_policy=None,
    ):
        selected = TorsionRefinementBoundsV9() if bounds is None else bounds
        if type(selected) is not TorsionRefinementBoundsV9:
            raise TypeError("exact V9 refinement bounds required")
        super().__init__(
            authority,
            receptor_system,
            ligand_system,
            implementation_source_sha256=implementation_source_sha256,
            v3_proposal_indices=v3_proposal_indices,
            torsion_config=selected.kernel_bounds(),
            v2_config=v2_config,
            v3_config=v3_config,
            clearance_config=clearance_config,
            radii_policy=radii_policy,
        )
        observed = ObservedRigidEnsembleV6(
            authority,
            receptor_system,
            ligand_system,
            implementation_source_sha256=implementation_source_sha256,
            v3_proposal_indices=v3_proposal_indices,
            v2_config=v2_config,
            v3_config=v3_config,
            clearance_config=clearance_config,
            radii_policy=radii_policy,
        )
        if observed.config_fingerprint_sha256 != self._v6.config_fingerprint_sha256:
            raise TorsionContactRefinementError(
                "observed baseline configuration changed"
            )
        self._v6 = observed
        self._v9_bounds = selected
        self._v9_bounds_sha256 = selected.fingerprint_sha256
        self._component_config_fingerprint_sha256 = _sha256(
            {
                "policy_id": POLICY_ID,
                "bounded_kernel_config_sha256": self._component_config_fingerprint_sha256,
                "bounds_sha256": self._v9_bounds_sha256,
                "eligible_proposal_indices": list(v3_proposal_indices),
                "maximum_retained_candidates_per_source": 2,
                "historical_receptor_penalty_window_enabled": False,
                "selection": "retain_baseline_and_strict_combined_improvement_receptor_nonincrease",
                "scientifically_validated": False,
            }
        )
        self._retained_candidates = {}

    @count_objective
    def _objective(self, coordinates):
        return super()._objective(coordinates)

    @track_refinement
    def _refine_kernel(
        self, proposal: DockingProposal, *, max_steps: int
    ) -> DockingProposal:
        """Product-owned bounded search; no historical V7 window is consulted."""
        proposal.assert_integrity()
        source = proposal.fingerprint_sha256
        if source in self._receipts:
            raise TorsionContactRefinementError("proposal was already refined")
        self._search_space.assert_integrity()
        if (
            proposal.search_space_fingerprint_sha256
            != self._search_space.fingerprint_sha256
        ):
            raise TorsionContactRefinementError(
                "proposal is cross-wired to a different torsion search space"
            )
        baseline_limit = min(max_steps, self._config.maximum_baseline_v6_steps)
        baseline = self._v6.refine(proposal, max_steps=baseline_limit)
        baseline_receipt = dict(self._v6.receipts[source])
        self._baseline_states[source] = _TorsionOptimizedState(
            coordinates=baseline.coordinates.clone(),
            torsion_angles=baseline.torsion_angles.clone(),
        )
        source_receptor, source_internal, source_combined, _, _ = self._objective(
            proposal.coordinates.to(dtype=torch.float64, device="cpu")
        )
        coordinates = baseline.coordinates.to(dtype=torch.float64, device="cpu")
        torsion_angles = baseline.torsion_angles.clone().to(
            dtype=torch.float64, device="cpu"
        )
        (
            baseline_receptor,
            baseline_internal,
            baseline_combined,
            receptor_by_atom,
            internal_by_pair,
        ) = self._objective(coordinates)
        current_receptor, current_internal, current_combined = (
            baseline_receptor,
            baseline_internal,
            baseline_combined,
        )
        baseline_steps = int(baseline_receipt["accepted_steps"])
        torsion_budget = min(
            self._config.maximum_torsion_steps, max(0, max_steps - baseline_steps)
        )
        if proposal.proposal_index not in self._torsion_eligible_proposal_index_set:
            skip_reason = "not_v3_variant"
        elif not self._rotor_indices:
            skip_reason = "no_authority_rotor"
        elif torsion_budget == 0:
            skip_reason = "no_remaining_torsion_step_budget"
        elif current_combined <= self._config.penalty_tolerance:
            skip_reason = "objective_at_or_below_tolerance"
        else:
            skip_reason = "none"
        moves = []
        trial_count = 0
        total_path = 0.0
        for _ in range(torsion_budget if skip_reason == "none" else 0):
            prioritized = sorted(
                (
                    (
                        -self._rotor_priority(
                            rotor, receptor_by_atom, internal_by_pair
                        ),
                        rotor,
                    )
                    for rotor in self._rotor_indices
                ),
                key=lambda row: (row[0], row[1]),
            )[: self._config.maximum_torsions_evaluated]
            best = None
            step = self._config.maximum_torsion_step_radians
            for _backtracking in range(self._config.maximum_backtracking_evaluations):
                if (
                    step + self._config.penalty_tolerance
                    < self._config.minimum_torsion_step_radians
                ):
                    break
                if total_path + step > (
                    self._config.maximum_total_torsion_path_radians
                    + self._config.penalty_tolerance
                ):
                    step *= 0.5
                    continue
                for _, rotor in prioritized:
                    for sign_order, sign in enumerate((-1.0, 1.0)):
                        delta = sign * step
                        candidate = self._rotated_subtree(
                            coordinates, rotor=rotor, delta_radians=delta
                        )
                        centroid_offset = float(
                            torch.linalg.vector_norm(
                                candidate.mean(dim=0) - self._authority.pocket.center
                            ).item()
                        )
                        if centroid_offset > (
                            self._config.maximum_centroid_offset_angstrom
                            + self._config.penalty_tolerance
                        ):
                            continue
                        trial_objective_attempt()
                        (
                            receptor,
                            internal,
                            combined,
                            candidate_receptor,
                            candidate_internal,
                        ) = self._objective(candidate)
                        trial_count += 1
                        if (
                            receptor > current_receptor + self._config.penalty_tolerance
                            or (
                                combined
                                >= current_combined - self._config.penalty_tolerance
                            )
                        ):
                            continue
                        key = (combined, receptor, internal, rotor, sign_order)
                        if best is None or key < best[:5]:
                            angles = torsion_angles.clone()
                            angles[rotor] = self._normalized_angle(
                                float(torsion_angles[rotor].item()) + delta
                            )
                            best = (
                                *key,
                                delta,
                                candidate,
                                angles,
                                candidate_receptor,
                                candidate_internal,
                            )
                if best is not None:
                    break
                step *= 0.5
            if best is None:
                break
            (
                current_combined,
                current_receptor,
                current_internal,
                rotor,
                _,
                delta,
                coordinates,
                torsion_angles,
                receptor_by_atom,
                internal_by_pair,
            ) = best
            total_path += abs(delta)
            accepted_refinement_step()
            moves.append(
                {
                    "rotatable_child_atom_index": rotor,
                    "delta_radians_binary64_hex": delta.hex(),
                    "receptor_penalty_binary64_hex": current_receptor.hex(),
                    "internal_penalty_binary64_hex": current_internal.hex(),
                    "combined_penalty_binary64_hex": current_combined.hex(),
                }
            )
        final_coordinates = coordinates.to(dtype=proposal.coordinates.dtype)
        final_angles = torsion_angles.to(dtype=proposal.torsion_angles.dtype)
        self._optimized_states[source] = _TorsionOptimizedState(
            coordinates=final_coordinates.clone(), torsion_angles=final_angles.clone()
        )
        receipt = {
            "schema_id": RECEIPT_SCHEMA,
            "source_proposal_sha256": source,
            "config_sha256": self.config_fingerprint_sha256,
            "baseline_v6_receipt_sha256": baseline_receipt["receipt_sha256"],
            "baseline_v6_receipt_payload": baseline_receipt,
            "baseline_v6_max_steps": baseline_limit,
            "v3_proposal_indices": list(self._v3_proposal_indices),
            "rotatable_child_atom_indices": list(self._rotor_indices),
            "torsion_step_budget": torsion_budget,
            "torsion_evaluation_skip_reason": skip_reason,
            "torsion_evaluated": skip_reason == "none",
            "torsion_variant_available": bool(moves),
            "torsion_selected": bool(moves),
            "evaluated_torsion_steps": len(moves),
            "evaluated_torsion_moves": moves,
            "evaluated_total_torsion_path_radians_binary64_hex": total_path.hex(),
            "accepted_torsion_steps": len(moves),
            "accepted_torsion_moves": moves,
            "objective_evaluation_count": 2 + trial_count,
            "fixed_objective_evaluation_count": 2,
            "torsion_trial_objective_evaluation_count": trial_count,
            "initial_receptor_penalty_binary64_hex": source_receptor.hex(),
            "baseline_v6_receptor_penalty_binary64_hex": baseline_receptor.hex(),
            "optimized_receptor_penalty_binary64_hex": current_receptor.hex(),
            "final_receptor_penalty_binary64_hex": current_receptor.hex(),
            "initial_internal_penalty_binary64_hex": source_internal.hex(),
            "baseline_v6_internal_penalty_binary64_hex": baseline_internal.hex(),
            "optimized_internal_penalty_binary64_hex": current_internal.hex(),
            "final_internal_penalty_binary64_hex": current_internal.hex(),
            "initial_combined_penalty_binary64_hex": source_combined.hex(),
            "baseline_v6_combined_penalty_binary64_hex": baseline_combined.hex(),
            "optimized_combined_penalty_binary64_hex": current_combined.hex(),
            "final_combined_penalty_binary64_hex": current_combined.hex(),
            "initial_penalty_binary64_hex": source_combined.hex(),
            "final_penalty_binary64_hex": current_combined.hex(),
            "generic_penalty_scope": "source_proposal_to_final_coordinates_product_v9_objective",
            "baseline_v6_penalty_scope": "post_v6_coordinates_product_v9_objective",
            "total_torsion_path_radians_binary64_hex": total_path.hex(),
            "accepted_steps": baseline_steps + len(moves),
            "accepted_translation_steps": baseline_receipt.get(
                "accepted_translation_steps", baseline_steps
            ),
            "accepted_rigid_rotation_steps": baseline_receipt.get(
                "accepted_rotation_steps", 0
            ),
            "accepted_rotation_steps": int(
                baseline_receipt.get("accepted_rotation_steps", 0)
            )
            + len(moves),
            "accepted_rotation_steps_include_torsion": True,
            "line_search_evaluation_count": int(
                baseline_receipt.get("line_search_evaluation_count", 0)
            )
            + trial_count,
            "fallback_direction_step_count": baseline_receipt.get(
                "fallback_direction_step_count", 0
            ),
            "original_pose_valid": baseline_receipt["original_pose_valid"],
            "total_translation_binary64_hex": baseline_receipt[
                "total_translation_binary64_hex"
            ],
            "total_rotation_vector_binary64_hex": baseline_receipt[
                "total_rotation_vector_binary64_hex"
            ],
            "pre_coordinates_sha256": baseline_receipt["pre_coordinates_sha256"],
            "baseline_coordinates_sha256": coordinate_fingerprint(baseline.coordinates),
            "post_coordinates_sha256": coordinate_fingerprint(final_coordinates),
            "ranking_score_reused_as_physical_energy": False,
            "posebusters_or_rmsd_used_for_selection": False,
            "source_lane_retained": True,
            "scientifically_validated": False,
        }
        receipt["receipt_sha256"] = _sha256(receipt)
        self._receipts[source] = MappingProxyType(receipt)
        return proposal.with_refined_coordinates(
            final_coordinates,
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256=receipt["receipt_sha256"],
            torsion_angles=final_angles,
        )

    def refine(self, proposal: DockingProposal, *, max_steps: int) -> DockingProposal:
        if (
            self._v9_bounds.fingerprint_sha256 != self._v9_bounds_sha256
            or self._config.fingerprint_sha256
            != self._v9_bounds.kernel_bounds().fingerprint_sha256
        ):
            raise TorsionContactRefinementError("V9 movement bounds changed")
        if type(max_steps) is not int or not 1 <= max_steps <= 128:
            raise TorsionContactRefinementError("V9 max_steps must be in [1,128]")
        refined = self._refine_kernel(proposal, max_steps=max_steps)
        source = proposal.fingerprint_sha256
        receipt = dict(self._receipts[source])
        receipt.pop("receipt_sha256")
        # Do not export V7 window fields as if they had governed a V9 decision.
        for key in tuple(receipt):
            if "selection_window" in key or "selected_final_receptor_penalty" in key:
                receipt.pop(key)
        receipt.update(
            {
                "schema_id": RECEIPT_SCHEMA,
                "policy_id": POLICY_ID,
                "lane": "monotone_torsion_v9"
                if receipt["torsion_selected"]
                else "rigid_v6_retained",
                "selection_reason": (
                    "strict_combined_improvement_retained"
                    if receipt["torsion_selected"]
                    else "baseline_retained_no_torsion_improvement"
                ),
                "historical_receptor_penalty_window_enabled": False,
                "maximum_retained_candidates_per_source": 2,
                "retained_baseline_coordinates_sha256": receipt[
                    "baseline_coordinates_sha256"
                ],
                "refinement_work": refinement_work_records(self)[-1].to_dict(),
                "refinement_work_sha256": refinement_work_records(self)[
                    -1
                ].receipt_sha256,
                "development_only": True,
                "scientifically_validated": False,
            }
        )
        digest = _sha256(receipt)
        receipt["receipt_sha256"] = digest
        self._receipts[source] = MappingProxyType(receipt)
        refined = proposal.with_refined_coordinates(
            refined.coordinates,
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256=digest,
            torsion_angles=refined.torsion_angles,
        )
        state = self._baseline_states[source]
        baseline = proposal.with_refined_coordinates(
            state.coordinates,
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256=digest,
            torsion_angles=state.torsion_angles,
        )
        candidates = (baseline,)
        if not (
            torch.equal(baseline.coordinates, refined.coordinates)
            and torch.equal(baseline.torsion_angles, refined.torsion_angles)
        ):
            candidates += (refined,)
        self._retained_candidates[source] = candidates
        return refined

    def retained_candidates(
        self, source: DockingProposal
    ) -> tuple[DockingProposal, ...]:
        """Return fresh bounded copies: baseline first, then improving endpoint."""
        source.assert_integrity()
        try:
            candidates = self._retained_candidates[source.fingerprint_sha256]
        except KeyError as exc:
            raise TorsionContactRefinementError("source was not refined by V9") from exc
        result = []
        for candidate in candidates:
            candidate.assert_integrity()
            result.append(
                source.with_refined_coordinates(
                    candidate.coordinates,
                    refiner_id=self.refiner_id,
                    refiner_version=self.refiner_version,
                    refinement_receipt_sha256=candidate.refinement_receipt_sha256,
                    torsion_angles=candidate.torsion_angles,
                )
            )
        return tuple(result)
