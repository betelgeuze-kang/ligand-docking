"""Research-only reuse of the authenticated product geometry gates.

This adapter binds supplied coordinates to the exact registered parent and an
actual caller-supplied research receipt digest. It never constructs a scorer or
claims score, optimizer convergence, strain admission, or physical validation.
The product's signed-volume subset is not comprehensive stereochemistry.
"""
from __future__ import annotations

import torch

from betelgeuze_engine_v2.docking.authority import AuthenticatedDockingProblem
from betelgeuze_engine_v2.docking.contact_validity import ElementAwarePoseValidityContext
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, require_digest
from betelgeuze_product.cpu_refinement_v1_2.registered_pose import generate_registered_pose


SCHEMA_ID = "pr49_research_product_geometry_audit/1.0.0"
REQUIRED_CHECKS = frozenset({
    "proper_rotation", "bond_lengths_preserved", "ligand_self_clash_free",
    "receptor_ligand_clash_free", "declared_chirality_preserved",
    "inside_declared_pocket", "element_vdw_ligand_overlap_free",
    "element_vdw_receptor_overlap_free",
})


class ProductGeometryAudit:
    """Evaluate the retained initial and supplied final coordinates, without scoring.

    ``authority``, ``budget`` and ``ligand`` are the already loaded registered
    request objects. The caller remains responsible for input/source byte guards
    and for supplying a digest of the real coordinate-producing research record.
    """

    def __init__(self, authority, budget, ligand):
        if (not isinstance(authority, AuthenticatedDockingProblem)
                or not isinstance(authority.validity_context, ElementAwarePoseValidityContext)):
            raise ResearchError("complete element-aware authenticated authority required")
        proposals, receipt = generate_registered_pose(authority, budget, ligand)
        self._authority = authority
        self._ligand = ligand
        self._baseline = proposals[0]
        self._registered_receipt = receipt
        self._authority_digest = authority.input_receipt_sha256
        self._context_digest = authority.validity_context.fingerprint_sha256
        self._ligand_digest = canonical_system_sha256(ligand)
        self._assert_integrity()

    @property
    def baseline_proposal(self):
        self._assert_integrity()
        return self._baseline

    def _assert_integrity(self):
        self._baseline.assert_integrity()
        if (self._authority.input_receipt_sha256 != self._authority_digest
                or self._authority.validity_context.fingerprint_sha256 != self._context_digest
                or canonical_system_sha256(self._ligand) != self._ligand_digest):
            raise ResearchError("research geometry audit source changed")

    def criteria(self):
        self._assert_integrity()
        context = self._authority.validity_context
        return {
            "pose_validity_config": context.config.to_dict(),
            "element_contact_policy": context.contact_policy.to_dict(),
            "required_checks": sorted(REQUIRED_CHECKS),
            "chirality_scope": "nondegenerate_degree_four_reference_signed_volume_subset",
            "reference_bond_count": len(context.bond_pairs),
            "excluded_ligand_pair_count": len(context.excluded_nonbonded_pairs),
            "declared_chirality_center_count": len(context.chirality_centers),
            "receptor_subset_atom_count": int(context.receptor_coordinates.shape[0]),
            "comprehensive_stereochemistry_checked": False,
        }

    def _evaluate(self, proposal, role):
        self._assert_integrity()
        result = self._authority.validity_context.evaluate(proposal)
        if (set(result.checks) != REQUIRED_CHECKS
                or set(result.evaluated_checks) != REQUIRED_CHECKS
                or not result.complete or not all(result.evaluated_checks.values())):
            raise ResearchError("product geometry audit did not evaluate all required checks")
        self._assert_integrity()
        return {
            "schema_id": SCHEMA_ID,
            "role": role,
            "authority_input_receipt_sha256": self._authority_digest,
            "validity_context_fingerprint_sha256": self._context_digest,
            "registered_proposal_receipt_sha256": self._registered_receipt.receipt_sha256,
            "registered_coordinate_fingerprint_sha256": self._baseline.coordinate_fingerprint_sha256,
            "coordinate_fingerprint_sha256": proposal.coordinate_fingerprint_sha256,
            "proposal_fingerprint_sha256": proposal.fingerprint_sha256,
            "parent_proposal_fingerprint_sha256": proposal.parent_proposal_fingerprint_sha256,
            "research_refiner_id": proposal.refiner_id,
            "research_refiner_version": proposal.refiner_version,
            "research_receipt_sha256": proposal.refinement_receipt_sha256,
            "criteria": self.criteria(),
            "pose_validity": result.to_dict(),
            "valid": result.valid,
            "complete": result.complete,
            "scorer_evaluated": False,
            "force_evaluations": 0,
            "scientifically_validated": False,
            "product_admitted": False,
        }

    def baseline_report(self):
        """Return complete product geometry checks on the exact retained input."""
        result = self._evaluate(self._baseline, "unchanged_registered_baseline")
        result["passed"] = result["valid"]
        return result

    def evaluate_coordinates(self, coordinates, *, refiner_id, refiner_version,
                             refinement_receipt_sha256):
        """Audit both endpoints; invalid geometry returns ``passed=False``.

        No casting, centering, repair, or replacement of reference geometry is
        allowed. The supplied digest binds the actual research record, not a
        fabricated product minimizer or scorer receipt.
        """
        if (not isinstance(coordinates, torch.Tensor)
                or coordinates.dtype is not torch.float64 or coordinates.device.type != "cpu"
                or coordinates.shape != self._baseline.coordinates.shape
                or not bool(torch.isfinite(coordinates).all())):
            raise ResearchError("final coordinates require finite CPU float64 exact shape [N,3]")
        require_digest(refinement_receipt_sha256)
        baseline = self.baseline_report()
        proposal = self._baseline.with_refined_coordinates(
            coordinates, refiner_id=refiner_id, refiner_version=refiner_version,
            refinement_receipt_sha256=refinement_receipt_sha256,
        )
        result = self._evaluate(proposal, "research_final_coordinates")
        result["baseline_pose_validity"] = baseline["pose_validity"]
        result["baseline_unchanged"] = True
        result["passed"] = baseline["valid"] and result["valid"]
        self._assert_integrity()
        return result
