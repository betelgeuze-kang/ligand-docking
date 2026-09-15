"""Bounded fixed-coordinate CPU evaluation with caller-supplied parameters.

This development adapter evaluates a small explicit pocket fragment. It neither
prepares chemistry nor establishes a binding free energy or production authority.
The reference evaluator is reused unchanged, including its scientific blockers.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
import math
import time
from typing import Any

import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_coordinates_sha256,
    canonical_system_sha256,
    canonical_topology_sha256,
    require_valid_all_atom_system,
)
from betelgeuze_engine_v2.molecular.serialization import canonical_json_value, sha256_canonical
from betelgeuze_engine_v2.physics.reference_forcefield import (
    ReferencePhysicsEvaluation,
    evaluate_reference_force_field,
)
from betelgeuze_engine_v2.physics.reference_parameters import ReferenceForceFieldParameters

from .authority import DockingScope, PocketDefinition


FIXED_POSE_SCHEMA_ID = "betelgeuze.engine_v2_fixed_pose_evaluation/1.0.0"
MAX_FIXED_POSE_ATOMS = 256
SUPPORTED_ELEMENTS = frozenset({"H", "C", "N", "O"})
_REFERENCE_ANGLE_COSINE_MARGIN = 1.0e-12
_DECLARATIONS = frozenset({
    "chemical_state_id", "hydrogen_state", "charge_source", "parameter_source",
})
_COMPONENTS = (
    "harmonic_bond", "harmonic_angle", "periodic_torsion",
    "lennard_jones", "screened_coulomb",
)


class FixedPoseError(ValueError):
    """Input is outside this adapter's explicit numerical development scope."""


def _partition(values: Sequence[int], *, label: str, atom_count: int) -> tuple[int, ...]:
    if not isinstance(values, (list, tuple)) or not values:
        raise FixedPoseError(f"{label} must be a nonempty list or tuple of atom indices")
    if any(type(index) is not int or not 0 <= index < atom_count for index in values):
        raise FixedPoseError(f"{label} requires integer atom indices within the system")
    if len(set(values)) != len(values):
        raise FixedPoseError(f"{label} contains duplicate atom indices")
    return tuple(values)


def _declarations(values: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(values, Mapping) or set(values) != _DECLARATIONS:
        raise FixedPoseError("state_declarations requires exactly " + ", ".join(sorted(_DECLARATIONS)))
    if any(type(value) is not str or not value.strip() for value in values.values()):
        raise FixedPoseError("state_declarations values must be nonblank strings")
    # Preserve the caller's original text; the declarations are not authenticated.
    return {key: values[key] for key in sorted(values)}


def _check_evaluation(evaluation: ReferencePhysicsEvaluation, atom_count: int) -> None:
    if not evaluation.execution_complete:
        raise FixedPoseError("reference evaluation is incomplete")
    if evaluation.term.energy.shape != (1,) or evaluation.term.forces.shape != (1, atom_count, 3):
        raise FixedPoseError("reference evaluation returned an invalid output shape")
    if evaluation.term.energy_descriptor.unit != "kcal/mol" or evaluation.term.force_descriptor.unit != "kcal/mol/angstrom":
        raise FixedPoseError("reference evaluation returned incompatible units")
    if set(evaluation.component_energies) != set(_COMPONENTS):
        raise FixedPoseError("reference evaluation component contract changed")
    tensors = [evaluation.term.energy, evaluation.term.forces, *evaluation.component_energies.values()]
    if any(not bool(torch.isfinite(value).all().item()) for value in tensors):
        raise FixedPoseError("reference evaluation returned nonfinite quantities")
    if any(value.shape != (1,) for value in evaluation.component_energies.values()):
        raise FixedPoseError("reference evaluation returned invalid component shapes")


def _quantity(value: Any, unit: str, semantics: str) -> dict[str, Any]:
    return {"value": value, "unit": unit, "status": "evaluated", "semantics": semantics}


def _require_unclamped_angles(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
) -> None:
    """Reject the frozen evaluator's angle clamp region before force evaluation."""
    for row in parameters.angles:
        indices = (row.atom_i, row.atom_j, row.atom_k)
        if any(not 0 <= index < system.atom_count for index in indices):
            raise FixedPoseError("angle parameter index is outside the canonical topology")
        first = system.coordinates[:, row.atom_i] - system.coordinates[:, row.atom_j]
        second = system.coordinates[:, row.atom_k] - system.coordinates[:, row.atom_j]
        first_norm = torch.linalg.vector_norm(first, dim=-1)
        second_norm = torch.linalg.vector_norm(second, dim=-1)
        if bool((first_norm <= 1.0e-12).any().item()) or bool((second_norm <= 1.0e-12).any().item()):
            raise FixedPoseError("angle contains a zero-length vector")
        cosine = (first * second).sum(dim=-1) / (first_norm * second_norm)
        # Keep the same cosine calculation and bounds as reference_forcefield._angle.
        # Its acos clamp is constant outside these bounds and suppresses real forces.
        if (
            not bool(torch.isfinite(cosine).all().item())
            or bool((cosine <= -1.0 + _REFERENCE_ANGLE_COSINE_MARGIN).any().item())
            or bool((cosine >= 1.0 - _REFERENCE_ANGLE_COSINE_MARGIN).any().item())
        ):
            raise FixedPoseError("harmonic angle geometry is outside the unclamped cosine domain")


def evaluate_fixed_pose(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    *,
    receptor_atom_indices: Sequence[int],
    ligand_atom_indices: Sequence[int],
    state_declarations: Mapping[str, str],
    pocket: PocketDefinition,
) -> dict[str, Any]:
    """Evaluate one unchanged, explicitly parameterized pocket-fragment pose.

    Energy values are scalars and force values retain canonical atom order as
    [N, 3]. A separate bondless mathematical projection evaluates cross pairs
    directly, avoiding subtraction of large internal energies. The projection
    is not a prepared molecular state. No optimizer, sampler, or model is called.
    """
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    try:
        # Force evaluation needs coordinate gradients even in an inference caller.
        with torch.inference_mode(False), torch.enable_grad():
            return _evaluate_fixed_pose(
                system, parameters,
                receptor_atom_indices=receptor_atom_indices,
                ligand_atom_indices=ligand_atom_indices,
                state_declarations=state_declarations,
                pocket=pocket,
                wall_start=wall_start, cpu_start=cpu_start,
            )
    except FixedPoseError:
        raise
    except (TypeError, ValueError, RuntimeError, OverflowError) as exc:
        raise FixedPoseError(str(exc)) from exc


def _evaluate_fixed_pose(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    *,
    receptor_atom_indices: Sequence[int],
    ligand_atom_indices: Sequence[int],
    state_declarations: Mapping[str, str],
    pocket: PocketDefinition,
    wall_start: float,
    cpu_start: float,
) -> dict[str, Any]:
    if type(system) is not AllAtomSystem or type(parameters) is not ReferenceForceFieldParameters:
        raise FixedPoseError("exact AllAtomSystem and ReferenceForceFieldParameters are required")
    if not 2 <= system.atom_count <= MAX_FIXED_POSE_ATOMS:
        raise FixedPoseError("fixed pose requires between 2 and 256 atoms")
    if system.coordinates.device.type != "cpu" or system.coordinates.dtype != torch.float64:
        raise FixedPoseError("fixed pose requires CPU float64 coordinates")
    if tuple(system.coordinates.shape) != (1, system.atom_count, 3):
        raise FixedPoseError("fixed pose coordinates must have shape [1, N, 3]")
    if system.cell is not None:
        raise FixedPoseError("periodic systems are unsupported by fixed pose")
    if parameters.cutoff_angstrom < parameters.applicability_domain.minimum_pair_distance_angstrom:
        raise FixedPoseError("cutoff must cover the declared minimum pair distance")
    require_valid_all_atom_system(system)
    if any(atom.element not in SUPPORTED_ELEMENTS for atom in system.atoms):
        raise FixedPoseError("fixed pose supports only explicitly parameterized H/C/N/O atoms")
    declarations = _declarations(state_declarations)
    receptor = _partition(receptor_atom_indices, label="receptor_atom_indices", atom_count=system.atom_count)
    ligand = _partition(ligand_atom_indices, label="ligand_atom_indices", atom_count=system.atom_count)
    receptor_set, ligand_set = set(receptor), set(ligand)
    if receptor_set & ligand_set or receptor_set | ligand_set != set(range(system.atom_count)):
        raise FixedPoseError("receptor/ligand partition must be disjoint and exhaustive")
    for residue in system.residues:
        indices = set(residue.atom_indices)
        if indices & receptor_set and indices & ligand_set:
            raise FixedPoseError("a residue cannot straddle the receptor/ligand partition")
    if any((bond.atom_i in receptor_set) != (bond.atom_j in receptor_set) for bond in system.bonds):
        raise FixedPoseError("cross receptor/ligand bonds are unsupported")
    atom_parameters = parameters.atom_parameter_map
    if set(atom_parameters) != set(range(system.atom_count)):
        raise FixedPoseError("nonbonded parameters must cover every canonical atom exactly")
    for atom in system.atoms:
        charge = atom.partial_charge_e
        if charge is None or not math.isfinite(charge):
            raise FixedPoseError("every atom requires an explicit finite canonical partial charge")
        if charge != atom_parameters[atom.index].charge_e:
            raise FixedPoseError("canonical partial charge and parameter charge disagree")
    if type(pocket) is not PocketDefinition or pocket.scope is not DockingScope.KNOWN_POCKET:
        raise FixedPoseError("fixed pose requires a known-pocket PocketDefinition")
    if pocket.center.device.type != "cpu" or pocket.center.dtype != torch.float64:
        raise FixedPoseError("pocket center must use CPU float64")
    pocket_sha256 = pocket.fingerprint_sha256
    ligand_distances = torch.linalg.vector_norm(system.coordinates[0, list(ligand)] - pocket.center, dim=-1)
    if not bool(torch.isfinite(ligand_distances).all().item()) or bool((ligand_distances > pocket.radius_angstrom).any().item()):
        raise FixedPoseError("ligand atoms lie outside the declared pocket sphere")

    system_sha256 = canonical_system_sha256(system)
    coordinates_sha256 = canonical_coordinates_sha256(system)
    partition = {"receptor_atom_indices": list(receptor), "ligand_atom_indices": list(ligand)}
    # A private coordinate snapshot keeps both evaluations bound to the same pose.
    snapshot = replace(system, coordinates=system.coordinates.detach().clone())
    _require_unclamped_angles(snapshot, parameters)
    neighbors = build_compact_radius_graph(
        snapshot.coordinates,
        RadiusGraphConfig(parameters.cutoff_angstrom, max_neighbors=system.atom_count - 1,
                          max_atoms_per_cell=system.atom_count),
        cell=None,
    )
    # Run the full frozen evaluator first: all original topology/parameter coverage,
    # distances, capacities and identity gates must pass before any projection.
    full = evaluate_reference_force_field(snapshot, neighbors, parameters)
    _check_evaluation(full, system.atom_count)
    def is_cross(first: int, second: int) -> bool:
        return (first in receptor_set) != (second in receptor_set)

    internal_pairs = {
        (first, second)
        for first in range(system.atom_count)
        for second in range(first + 1, system.atom_count)
        if not is_cross(first, second)
    }
    projected = replace(snapshot, bonds=())
    projected_parameters = replace(
        parameters,
        topology_sha256=canonical_topology_sha256(projected),
        bonds=(), angles=(), torsions=(),
        excluded_pairs=tuple(sorted(internal_pairs | set(parameters.excluded_pairs))),
        scaled_pairs=tuple(row for row in parameters.scaled_pairs if is_cross(row.atom_i, row.atom_j)),
    )
    cross = evaluate_reference_force_field(projected, neighbors, projected_parameters)
    _check_evaluation(cross, system.atom_count)
    components: dict[str, Any] = {}
    for name in _COMPONENTS:
        total_value = float(full.component_energies[name].item())
        cross_value = float(cross.component_energies[name].item())
        internal_value = total_value - cross_value
        if not math.isfinite(internal_value):
            raise FixedPoseError("internal component difference is nonfinite")
        components[name] = {"total": total_value, "cross": cross_value,
                            "internal": internal_value, "unit": "kcal/mol"}
    if canonical_system_sha256(system) != system_sha256 or pocket.fingerprint_sha256 != pocket_sha256:
        raise FixedPoseError("input state changed during fixed-pose evaluation")
    result = {
        "schema_id": FIXED_POSE_SCHEMA_ID,
        "status": "evaluated",
        "scope": "explicit_parameter_pocket_fragment_numerical_development",
        "applicability_domain": {
            "device": "cpu", "dtype": "float64", "coordinate_shape": [1, system.atom_count, 3],
            "max_atoms": MAX_FIXED_POSE_ATOMS, "supported_elements": sorted(SUPPORTED_ELEMENTS),
            "periodic": False, "cross_covalent_bonds_supported": False,
            "harmonic_angle_cosine_open_interval": [
                -1.0 + _REFERENCE_ANGLE_COSINE_MARGIN,
                1.0 - _REFERENCE_ANGLE_COSINE_MARGIN,
            ],
            "chemical_state_mode": "caller_supplied_not_inferred",
            "parameter_assignment_performed": False,
        },
        "coordinate_frame_id": pocket.coordinate_frame_id,
        "coordinate_frame_status": "caller_declared_no_registration_performed",
        "input_identity": {
            "system_sha256": system_sha256,
            "topology_sha256": parameters.topology_sha256,
            "coordinates_sha256": coordinates_sha256,
            "parameter_fingerprint_sha256": parameters.fingerprint_sha256,
            "partition_sha256": sha256_canonical(partition),
            "pocket_definition_sha256": pocket_sha256,
            "state_declarations_sha256": sha256_canonical(declarations),
        },
        "atom_mapping": partition,
        "coordinates": snapshot.coordinates.tolist(),
        "coordinate_unit": "angstrom",
        "input_provenance": canonical_json_value(system.provenance),
        "state_declarations": declarations,
        "state_declarations_verified": False,
        "pocket": pocket.to_dict(),
        "projection_identity": {
            "kind": "bondless_cross_pair_projection_not_prepared_molecule",
            "parent_system_sha256": system_sha256,
            "system_sha256": canonical_system_sha256(projected),
            "topology_sha256": projected_parameters.topology_sha256,
            "coordinates_sha256": canonical_coordinates_sha256(projected),
            "parameter_fingerprint_sha256": projected_parameters.fingerprint_sha256,
            "excluded_pair_count": len(projected_parameters.excluded_pairs),
            "scaled_pair_count": len(projected_parameters.scaled_pairs),
        },
        "quantities": {
            "total_energy": _quantity(float(full.term.energy.item()), "kcal/mol",
                                      "explicit_reference_potential_at_fixed_coordinates"),
            "cross_energy": _quantity(float(cross.term.energy.item()), "kcal/mol",
                                      "direct_cross_pair_lj_screened_coulomb_potential"),
            "total_forces": _quantity(full.term.forces[0].tolist(), "kcal/mol/angstrom",
                                      "negative_coordinate_gradient_of_evaluated_total_potential"),
            "cross_forces": _quantity(cross.term.forces[0].tolist(), "kcal/mol/angstrom",
                                      "negative_coordinate_gradient_of_evaluated_cross_potential"),
        },
        "component_energies": components,
        "internal_energy_semantics": "total_minus_direct_cross_at_identical_coordinates_not_strain",
        "cross_energy_semantics": "direct_cross_pair_lj_screened_coulomb_not_binding_free_energy",
        "component_forces": None,
        "not_evaluated": {name: None for name in (
            "strain", "solvation", "ai_correction", "uncertainty", "pose_retention",
            "improper", "entropy",
        )},
        "scientific_blockers": list(dict.fromkeys((
            *full.scientific_blockers, *cross.scientific_blockers,
            "chemical_state_and_parameter_sources_are_caller_assertions",
            "fixed_pose_does_not_establish_binding_affinity_or_pose_retention",
            "pocket_frame_alignment_not_independently_verified",
        ))),
        "claim_policy": {name: False for name in (
            "scientifically_validated", "validated_for_composition", "production_claim_allowed",
            "product_qualified",
        )},
    }
    result["cost"] = {
        "wall_seconds": time.perf_counter() - wall_start,
        "cpu_seconds": time.process_time() - cpu_start,
        "evaluation_count": 2,
        "timing_evidence": "single_call_observation",
        "speedup": None,
    }
    return result


__all__ = ["FIXED_POSE_SCHEMA_ID", "FixedPoseError", "evaluate_fixed_pose"]
