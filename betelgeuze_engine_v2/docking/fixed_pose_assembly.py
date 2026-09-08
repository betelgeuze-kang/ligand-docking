"""Join two explicit same-frame canonical inputs without preparing chemistry.

Only canonical indices and source-qualified chain IDs change. Coordinates,
chemical records, and numerical parameter values are preserved. Cross pairs use
the reference evaluator's full, unscaled nonbonded rule; no cross bonds or pair
exceptions are inferred. The frame declaration is a caller assertion.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
import math
from typing import Any

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    StructureProvenance,
    all_atom_system_from_canonical_json,
    canonical_coordinates_sha256,
    canonical_system_document,
    canonical_system_json_bytes,
    canonical_system_sha256,
    canonical_topology_sha256,
    require_valid_all_atom_system,
)
from betelgeuze_engine_v2.molecular.serialization import canonical_json_value, sha256_canonical
from betelgeuze_engine_v2.physics.reference_forcefield import (
    _bonded_topology_paths,
    _validate_indices,
)
from betelgeuze_engine_v2.physics.reference_parameters import ReferenceForceFieldParameters

from .authority import DockingScope, PocketDefinition
from .fixed_pose import MAX_FIXED_POSE_ATOMS, SUPPORTED_ELEMENTS, evaluate_fixed_pose


FIXED_POSE_ASSEMBLY_SCHEMA_ID = "betelgeuze.engine_v2_fixed_pose_assembly/1.0.0"
_FRAME_FIELDS = frozenset({
    "coordinate_frame_id", "receptor_coordinates_sha256", "ligand_coordinates_sha256",
})
_SHARED_FIELDS = (
    "parameter_set_id", "parameter_set_version", "cutoff_angstrom",
    "switch_start_angstrom", "dielectric", "screening_kappa_per_angstrom",
    "applicability_domain",
)


class FixedPoseAssemblyError(ValueError):
    """Explicit component inputs cannot be joined within this development scope."""


@dataclass(frozen=True)
class FixedPoseAssemblyV1:
    system: AllAtomSystem
    parameters: ReferenceForceFieldParameters
    receptor_atom_indices: tuple[int, ...]
    ligand_atom_indices: tuple[int, ...]
    frame_declaration: Mapping[str, str]
    source_identity: Mapping[str, Any]
    index_maps: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": FIXED_POSE_ASSEMBLY_SCHEMA_ID,
            "status": "assembled",
            "system_sha256": canonical_system_sha256(self.system),
            "topology_sha256": canonical_topology_sha256(self.system),
            "parameter_fingerprint_sha256": self.parameters.fingerprint_sha256,
            "frame_declaration": dict(self.frame_declaration),
            "same_frame_status": "caller_assertion_not_verified_no_registration",
            "source_identity": canonical_json_value(self.source_identity),
            "index_maps": canonical_json_value(self.index_maps),
            "receptor_atom_indices": list(self.receptor_atom_indices),
            "ligand_atom_indices": list(self.ligand_atom_indices),
            "cross_pair_policy": "full_unscaled_reference_nonbonded_no_cross_exceptions",
            "coordinates_transformed": False,
            "chemistry_inferred": False,
            "parameters_inferred": False,
            "scientifically_validated": False,
            "product_qualified": False,
        }


def _source(system: AllAtomSystem, parameters: ReferenceForceFieldParameters, side: str) -> AllAtomSystem:
    if type(system) is not AllAtomSystem or type(parameters) is not ReferenceForceFieldParameters:
        raise FixedPoseAssemblyError(f"{side} requires exact canonical system and reference parameters")
    if not 1 <= system.atom_count <= MAX_FIXED_POSE_ATOMS:
        raise FixedPoseAssemblyError(f"{side} atom count is outside [1,256]")
    if system.coordinates.device.type != "cpu" or system.coordinates.dtype != torch.float64:
        raise FixedPoseAssemblyError(f"{side} requires CPU float64 coordinates")
    if tuple(system.coordinates.shape) != (1, system.atom_count, 3) or system.cell is not None:
        raise FixedPoseAssemblyError(f"{side} requires one nonperiodic coordinate model")
    require_valid_all_atom_system(system)
    if any(atom.element not in SUPPORTED_ELEMENTS for atom in system.atoms):
        raise FixedPoseAssemblyError(f"{side} supports only explicit H/C/N/O atoms")
    if parameters.topology_sha256 != canonical_topology_sha256(system):
        raise FixedPoseAssemblyError(f"{side} source parameter topology SHA mismatch")
    # Reuse the frozen evaluator's pure index/topology checks before rebinding.
    # In particular, a parent-invalid exclusion must not become a valid cross pair.
    blockers = _validate_indices(parameters, system.atom_count)
    if blockers:
        raise FixedPoseAssemblyError(f"{side} source parameters: {', '.join(blockers)}")
    pairs = [(bond.atom_i, bond.atom_j) for bond in system.bonds]
    if set(pairs) != {(row.atom_i, row.atom_j) for row in parameters.bonds}:
        raise FixedPoseAssemblyError(f"{side} bond parameters do not exactly cover source topology")
    expected_angles, expected_torsions = _bonded_topology_paths(system.atom_count, pairs)
    angles = {(min(row.atom_i, row.atom_k), row.atom_j, max(row.atom_i, row.atom_k)) for row in parameters.angles}
    torsions = {min((row.atom_i, row.atom_j, row.atom_k, row.atom_l),
                    (row.atom_l, row.atom_k, row.atom_j, row.atom_i)) for row in parameters.torsions}
    if angles != expected_angles or torsions != expected_torsions:
        raise FixedPoseAssemblyError(f"{side} angle/torsion parameters do not exactly cover source topology")
    atom_parameter_map = parameters.atom_parameter_map
    for atom in system.atoms:
        charge = atom.partial_charge_e
        if charge is None or not math.isfinite(charge):
            raise FixedPoseAssemblyError(f"{side} requires explicit finite canonical partial charges")
        if charge != atom_parameter_map[atom.index].charge_e:
            raise FixedPoseAssemblyError(f"{side} canonical and parameter charges disagree")
    # This is a lossless canonical snapshot, not atom or charge preparation.
    return all_atom_system_from_canonical_json(canonical_system_json_bytes(system), device="cpu")


def _identity(system: AllAtomSystem, parameters: ReferenceForceFieldParameters) -> dict[str, Any]:
    return {
        "system_sha256": canonical_system_sha256(system),
        "topology_sha256": canonical_topology_sha256(system),
        "coordinates_sha256": canonical_coordinates_sha256(system),
        "parameter_fingerprint_sha256": parameters.fingerprint_sha256,
        "system_document": canonical_json_value(canonical_system_document(system)),
        "parameter_document": parameters.to_dict(),
    }


def assemble_fixed_pose_inputs(
    receptor_system: AllAtomSystem,
    receptor_parameters: ReferenceForceFieldParameters,
    ligand_system: AllAtomSystem,
    ligand_parameters: ReferenceForceFieldParameters,
    *,
    pocket: PocketDefinition,
    frame_declaration: Mapping[str, str],
) -> FixedPoseAssemblyV1:
    """Join R then L without moving coordinates or assigning missing parameters.

    Both parameter sets must have the same family/version and global settings.
    Separate inputs cannot declare cross covalent bonds or cross pair exceptions;
    this version explicitly evaluates all cross nonbonded pairs at unit scaling.
    No energy evaluation is performed by this assembly function.
    """
    try:
        return _assemble(receptor_system, receptor_parameters, ligand_system, ligand_parameters,
                         pocket=pocket, frame_declaration=frame_declaration)
    except FixedPoseAssemblyError:
        raise
    except (TypeError, ValueError, RuntimeError, OverflowError, KeyError) as exc:
        raise FixedPoseAssemblyError(str(exc)) from exc


def _assemble(receptor_system: AllAtomSystem, receptor_parameters: ReferenceForceFieldParameters,
              ligand_system: AllAtomSystem, ligand_parameters: ReferenceForceFieldParameters,
              *, pocket: PocketDefinition, frame_declaration: Mapping[str, str]) -> FixedPoseAssemblyV1:
    receptor = _source(receptor_system, receptor_parameters, "receptor")
    ligand = _source(ligand_system, ligand_parameters, "ligand")
    total_atoms = receptor.atom_count + ligand.atom_count
    if total_atoms > MAX_FIXED_POSE_ATOMS:
        raise FixedPoseAssemblyError("combined atom count exceeds 256")
    if type(pocket) is not PocketDefinition or pocket.scope is not DockingScope.KNOWN_POCKET:
        raise FixedPoseAssemblyError("a known-pocket PocketDefinition is required")
    pocket_sha = pocket.fingerprint_sha256
    if not isinstance(frame_declaration, Mapping) or set(frame_declaration) != _FRAME_FIELDS:
        raise FixedPoseAssemblyError("frame_declaration requires exactly the frame ID and two coordinate SHA fields")
    if any(type(value) is not str or not value.strip() for value in frame_declaration.values()):
        raise FixedPoseAssemblyError("frame_declaration values must be nonblank strings")
    frame = dict(frame_declaration)
    if frame["coordinate_frame_id"] != pocket.coordinate_frame_id:
        raise FixedPoseAssemblyError("declared coordinate frame differs from pocket frame")
    for side, system in (("receptor", receptor), ("ligand", ligand)):
        if frame[f"{side}_coordinates_sha256"] != canonical_coordinates_sha256(system):
            raise FixedPoseAssemblyError(f"{side} frame declaration coordinate SHA mismatch")
        source_frame = system.metadata.get("coordinate_frame_id")
        if source_frame is not None and source_frame != frame["coordinate_frame_id"]:
            raise FixedPoseAssemblyError(f"{side} source metadata declares a different coordinate frame")
    shared_receptor, shared_ligand = receptor_parameters.to_dict(), ligand_parameters.to_dict()
    for field in _SHARED_FIELDS:
        if shared_receptor[field] != shared_ligand[field]:
            raise FixedPoseAssemblyError(f"component parameter setting {field} differs")
    domain = receptor_parameters.applicability_domain
    counts = {"max_atoms": total_atoms, "max_bonds": len(receptor.bonds) + len(ligand.bonds),
              "max_angles": len(receptor_parameters.angles) + len(ligand_parameters.angles),
              "max_torsions": len(receptor_parameters.torsions) + len(ligand_parameters.torsions)}
    if any(count > getattr(domain, field) for field, count in counts.items()):
        raise FixedPoseAssemblyError("combined topology exceeds unchanged parameter applicability bounds")
    if receptor_parameters.cutoff_angstrom < domain.minimum_pair_distance_angstrom:
        raise FixedPoseAssemblyError("cutoff must cover the declared minimum pair distance")
    ligand_distance = torch.linalg.vector_norm(ligand.coordinates[0] - pocket.center, dim=-1)
    if bool((ligand_distance > pocket.radius_angstrom).any().item()):
        raise FixedPoseAssemblyError("ligand atoms lie outside the declared pocket sphere")

    sources = {"receptor": _identity(receptor, receptor_parameters), "ligand": _identity(ligand, ligand_parameters)}
    atoms, bonds, residues, chains = [], [], [], []
    atom_parameters, bond_parameters, angles, torsions, excluded, scaled = [], [], [], [], [], []
    index_maps: dict[str, Any] = {}
    for side, prefix, system, parameters in (
        ("receptor", "R:", receptor, receptor_parameters),
        ("ligand", "L:", ligand, ligand_parameters),
    ):
        atom_map = {row.index: len(atoms) + row.index for row in system.atoms}
        bond_map = {row.index: len(bonds) + row.index for row in system.bonds}
        residue_map = {row.index: len(residues) + row.index for row in system.residues}
        chain_map = {row.index: len(chains) + row.index for row in system.chains}
        index_maps[side] = {
            "atoms": {str(old): new for old, new in atom_map.items()},
            "bonds": {str(old): new for old, new in bond_map.items()},
            "residues": {str(old): new for old, new in residue_map.items()},
            "chains": {str(old): new for old, new in chain_map.items()},
            "chain_ids": {str(row.index): {"source": row.chain_id, "combined": prefix + row.chain_id} for row in system.chains},
        }
        atoms.extend(replace(row, index=atom_map[row.index], residue_index=residue_map[row.residue_index]) for row in system.atoms)
        bonds.extend(replace(row, index=bond_map[row.index], atom_i=atom_map[row.atom_i], atom_j=atom_map[row.atom_j]) for row in system.bonds)
        residues.extend(replace(row, index=residue_map[row.index], chain_index=chain_map[row.chain_index],
                                atom_indices=tuple(atom_map[i] for i in row.atom_indices)) for row in system.residues)
        chains.extend(replace(row, index=chain_map[row.index], chain_id=prefix + row.chain_id,
                              residue_indices=tuple(residue_map[i] for i in row.residue_indices)) for row in system.chains)
        atom_parameters.extend(replace(row, atom_index=atom_map[row.atom_index]) for row in parameters.atom_parameters)
        bond_parameters.extend(replace(row, atom_i=atom_map[row.atom_i], atom_j=atom_map[row.atom_j]) for row in parameters.bonds)
        angles.extend(replace(row, atom_i=atom_map[row.atom_i], atom_j=atom_map[row.atom_j], atom_k=atom_map[row.atom_k]) for row in parameters.angles)
        torsions.extend(replace(row, atom_i=atom_map[row.atom_i], atom_j=atom_map[row.atom_j],
                                atom_k=atom_map[row.atom_k], atom_l=atom_map[row.atom_l]) for row in parameters.torsions)
        excluded.extend((atom_map[first], atom_map[second]) for first, second in parameters.excluded_pairs)
        scaled.extend(replace(row, atom_i=atom_map[row.atom_i], atom_j=atom_map[row.atom_j]) for row in parameters.scaled_pairs)

    assembly_identity = {
        "schema_id": FIXED_POSE_ASSEMBLY_SCHEMA_ID,
        "parent_system_sha256": [sources[side]["system_sha256"] for side in ("receptor", "ligand")],
        "parent_parameter_sha256": [sources[side]["parameter_fingerprint_sha256"] for side in ("receptor", "ligand")],
        "frame_declaration": frame, "pocket_definition_sha256": pocket_sha,
        "cross_pair_policy": "full_unscaled_reference_nonbonded_no_cross_exceptions",
    }
    identity_sha = sha256_canonical(assembly_identity)
    combined = AllAtomSystem(
        system_id=f"fixed-pose-assembly:{identity_sha}", atoms=tuple(atoms), bonds=tuple(bonds),
        residues=tuple(residues), chains=tuple(chains),
        coordinates=torch.cat((receptor.coordinates, ligand.coordinates), dim=1),
        provenance=StructureProvenance(
            source_format="canonical_pair_assembly", source_id=identity_sha,
            parser_name="fixed_pose_assembly", parser_version="1.0.0",
            operations=("concatenate_explicit_same_frame_components",),
            parent_sha256=tuple(assembly_identity["parent_system_sha256"]),
            metadata={"component_provenance": {"receptor": receptor.provenance, "ligand": ligand.provenance}},
        ),
        metadata={"assembly_identity": assembly_identity, "coordinate_frame_id": frame["coordinate_frame_id"],
                  "component_metadata": {"receptor": receptor.metadata, "ligand": ligand.metadata}},
    )
    require_valid_all_atom_system(combined)
    combined_parameters = replace(
        receptor_parameters, topology_sha256=canonical_topology_sha256(combined),
        atom_parameters=tuple(atom_parameters), bonds=tuple(bond_parameters),
        angles=tuple(angles), torsions=tuple(torsions), excluded_pairs=tuple(excluded), scaled_pairs=tuple(scaled),
        metadata={"assembly_identity": assembly_identity,
                  "component_metadata": {"receptor": shared_receptor["metadata"], "ligand": shared_ligand["metadata"]}},
    )
    # Detect mutable source tensors/metadata changing while the snapshot is made.
    for side, original, parameters in (("receptor", receptor_system, receptor_parameters),
                                       ("ligand", ligand_system, ligand_parameters)):
        if canonical_system_sha256(original) != sources[side]["system_sha256"] or parameters.fingerprint_sha256 != sources[side]["parameter_fingerprint_sha256"]:
            raise FixedPoseAssemblyError(f"{side} input changed during assembly")
    if pocket.fingerprint_sha256 != pocket_sha:
        raise FixedPoseAssemblyError("pocket changed during assembly")
    return FixedPoseAssemblyV1(combined, combined_parameters, tuple(range(receptor.atom_count)),
                               tuple(range(receptor.atom_count, total_atoms)), frame, sources, index_maps)


def evaluate_fixed_components(
    receptor_system: AllAtomSystem,
    receptor_parameters: ReferenceForceFieldParameters,
    ligand_system: AllAtomSystem,
    ligand_parameters: ReferenceForceFieldParameters,
    *,
    pocket: PocketDefinition,
    frame_declaration: Mapping[str, str],
    state_declarations: Mapping[str, str],
) -> dict[str, Any]:
    """Assemble explicit components, then use the existing fixed-pose evaluator."""
    assembly = assemble_fixed_pose_inputs(receptor_system, receptor_parameters, ligand_system, ligand_parameters,
                                          pocket=pocket, frame_declaration=frame_declaration)
    result = evaluate_fixed_pose(assembly.system, assembly.parameters,
                                 receptor_atom_indices=assembly.receptor_atom_indices,
                                 ligand_atom_indices=assembly.ligand_atom_indices,
                                 pocket=pocket, state_declarations=state_declarations)
    result["assembly"] = assembly.to_dict()
    result["evaluated_system"] = canonical_json_value(canonical_system_document(assembly.system))
    result["evaluated_parameters"] = assembly.parameters.to_dict()
    return result


__all__ = ["FIXED_POSE_ASSEMBLY_SCHEMA_ID", "FixedPoseAssemblyError", "FixedPoseAssemblyV1",
           "assemble_fixed_pose_inputs", "evaluate_fixed_components"]
