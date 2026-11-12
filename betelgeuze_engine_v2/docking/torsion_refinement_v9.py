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

from .proposals import DockingProposal
from .refinement_work import refinement_work_records
from .torsion_contact_refinement import (
    InteractionAwareTorsionContactConfigV7,
    InteractionAwareTorsionContactEnsembleRefinerV7,
    TorsionContactRefinementError,
    _sha256,
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
        # Only movement/objective bounds are shared. V9 overrides all window
        # decisions rather than installing a very large fictitious window.
        return InteractionAwareTorsionContactConfigV7(**asdict(self))

    @property
    def fingerprint_sha256(self):
        return _sha256({"policy_id": POLICY_ID, "bounds": asdict(self)})


class InteractionAwareTorsionContactEnsembleRefinerV9(
    InteractionAwareTorsionContactEnsembleRefinerV7
):
    refiner_id = "betelgeuze.engine_v2_monotone_retained_torsion_refiner"
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

    def _selection_window_reachable(self, receptor: float, remaining: int) -> bool:
        return True

    def _stop_torsion_search(self, receptor: float, remaining: int) -> bool:
        return False

    def _select_torsion_variant(self, available: bool, receptor: float) -> bool:
        return available

    def refine(self, proposal: DockingProposal, *, max_steps: int) -> DockingProposal:
        if (
            self._v9_bounds.fingerprint_sha256 != self._v9_bounds_sha256
            or self._config.fingerprint_sha256
            != self._v9_bounds.kernel_bounds().fingerprint_sha256
        ):
            raise TorsionContactRefinementError("V9 movement bounds changed")
        if type(max_steps) is not int or not 1 <= max_steps <= 128:
            raise TorsionContactRefinementError("V9 max_steps must be in [1,128]")
        refined = super().refine(proposal, max_steps=max_steps)
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
