"""Sparse base receptor-clash evaluation for element-aware docking validity.

The original element-aware context called ``PoseValidityContext.evaluate`` first,
which materialized a Python nested receptor-by-ligand traversal before the sparse
vdW cell map ran. This compatibility installer keeps every public check and
blocker name while evaluating both the legacy absolute-distance clash threshold
and the radius-normalized vdW threshold from one bounded pocket-local candidate
set.

No chemistry or scientific claim is added. The legacy geometric threshold and
the vdW engineering baseline remain independently identified conjunctive gates.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys


SPARSE_BASE_RECEPTOR_CLASH_ALGORITHM_ID = (
    "betelgeuze.engine_v2_sparse_base_receptor_clash_from_vdw_cells/1.0.0"
)
SPARSE_BASE_VALIDITY_INSTALLER_SCHEMA_ID = (
    "betelgeuze.engine_v2_sparse_base_validity_installer/1.0.0"
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


def install_sparse_element_aware_base_validity() -> str:
    marker = "_betelgeuze_sparse_element_aware_base_validity_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing

    from . import contact_validity as contact_module
    from . import validity as validity_module

    context_class = contact_module.ElementAwarePoseValidityContext
    if getattr(context_class, "_betelgeuze_sparse_base_installed", False):
        return str(getattr(sys, marker))

    original_to_dict = context_class.to_dict

    def to_dict(self) -> dict[str, object]:
        document = dict(original_to_dict(self))
        document["base_receptor_clash_algorithm_id"] = (
            SPARSE_BASE_RECEPTOR_CLASH_ALGORITHM_ID
        )
        document["dense_receptor_cartesian_traversal_performed"] = False
        return document

    def evaluate(self, proposal):
        self.assert_integrity()
        proposal.assert_integrity()
        if proposal.problem_fingerprint_sha256 != self.problem_fingerprint_sha256:
            raise contact_module.ElementAwareValidityError(
                "pose validity context is cross-wired to another docking problem"
            )
        if (
            self.contact_policy.cell_size_angstrom + 1.0e-12
            < self.config.receptor_ligand_clash_angstrom
        ):
            raise contact_module.ElementAwareValidityError(
                "contact cell size does not cover the base receptor clash threshold"
            )

        # Deliberately omit receptor_coordinates here. Every other historical
        # check is evaluated by the canonical implementation; the receptor check
        # is filled below from the sparse candidate map.
        base = validity_module.evaluate_pose_validity(
            proposal,
            self.reference_coordinates,
            bond_pairs=self.bond_pairs,
            excluded_nonbonded_pairs=self.excluded_nonbonded_pairs,
            receptor_coordinates=None,
            pocket_center=self.pocket_center,
            chirality_centers=self.chirality_centers,
            config=self.config,
        )
        ligand = self._element_ligand_contacts(proposal)
        receptor = self._element_receptor_contacts(proposal)

        checks = dict(base.checks)
        evaluated_checks = dict(base.evaluated_checks)
        measurements = dict(base.measurements)
        blockers = list(base.blockers)
        not_evaluated = dict(base.not_evaluated_reasons)

        minimum_receptor_distance = float(
            receptor["minimum_distance_angstrom"]
        )
        base_receptor_valid = bool(
            minimum_receptor_distance
            >= self.config.receptor_ligand_clash_angstrom
        )
        checks["receptor_ligand_clash_free"] = base_receptor_valid
        evaluated_checks["receptor_ligand_clash_free"] = True
        not_evaluated.pop("receptor_ligand_clash_free", None)
        measurements["minimum_receptor_ligand_distance_angstrom"] = (
            minimum_receptor_distance
        )
        measurements["evaluated_receptor_ligand_pair_count"] = int(
            receptor["evaluated_candidate_pair_count"]
        )
        measurements["full_cartesian_receptor_ligand_pair_count"] = int(
            receptor["full_cartesian_pair_count"]
        )
        measurements["sparse_receptor_cell_count"] = int(
            receptor["occupied_receptor_cell_count"]
        )
        if not base_receptor_valid:
            blockers.append("receptor_ligand_clash_detected")

        checks["element_vdw_ligand_overlap_free"] = bool(ligand["valid"])
        checks["element_vdw_receptor_overlap_free"] = bool(receptor["valid"])
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
                "element_vdw_receptor_minimum_distance_angstrom": (
                    minimum_receptor_distance
                ),
                "element_vdw_receptor_minimum_ratio": float(
                    receptor["minimum_vdw_distance_ratio"]
                ),
            }
        )
        if not checks["element_vdw_ligand_overlap_free"]:
            blockers.append("element_vdw_ligand_severe_overlap_detected")
        if not checks["element_vdw_receptor_overlap_free"]:
            blockers.append("element_vdw_receptor_severe_overlap_detected")

        complete = all(evaluated_checks.values())
        valid = all(
            checks[name]
            for name, evaluated in evaluated_checks.items()
            if evaluated
        )
        if not math.isfinite(minimum_receptor_distance):
            raise contact_module.ElementAwareValidityError(
                "sparse receptor minimum distance is non-finite"
            )
        proposal.assert_integrity()
        self.assert_integrity()
        return validity_module.PoseValidityResult(
            checks=checks,
            evaluated_checks=evaluated_checks,
            complete=complete,
            valid_within_evaluated_scope=valid,
            measurements=measurements,
            blockers=tuple(blockers),
            not_evaluated_reasons=not_evaluated,
        )

    context_class.to_dict = to_dict
    context_class.evaluate = evaluate
    context_class._betelgeuze_sparse_base_installed = True

    receipt = _sha256(
        {
            "schema_id": SPARSE_BASE_VALIDITY_INSTALLER_SCHEMA_ID,
            "algorithm_id": SPARSE_BASE_RECEPTOR_CLASH_ALGORITHM_ID,
            "legacy_check_name_preserved": "receptor_ligand_clash_free",
            "legacy_blocker_preserved": "receptor_ligand_clash_detected",
            "dense_receptor_cartesian_traversal_performed": False,
            "same_candidate_set_used_for_base_and_vdw_checks": True,
            "chemically_validated": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }
    )
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "SPARSE_BASE_RECEPTOR_CLASH_ALGORITHM_ID",
    "SPARSE_BASE_VALIDITY_INSTALLER_SCHEMA_ID",
    "install_sparse_element_aware_base_validity",
]
