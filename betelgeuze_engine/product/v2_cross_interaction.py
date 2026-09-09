"""Versioned prepared-state adapter to the unchanged Engine V2 physics kernel.

Only cross Lennard-Jones and switched screened-Coulomb terms are evaluated.
Internal energy, strain, solvation and affinity are not evaluated. Source atom
parameters, coordinates and canonical systems are retained without preparation.
The bounded bondless tiles are mathematical projections, not molecular states.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import math
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem, Chain, Residue, StructureProvenance,
    canonical_coordinates_sha256, canonical_system_document,
    canonical_topology_sha256, require_valid_all_atom_system,
)
from betelgeuze_engine_v2.molecular.serialization import canonical_json_value, sha256_canonical
from betelgeuze_engine_v2.geometry.neighbors import (
    _cell_key, _neighbor_cell_keys, _minimum_image_squared_distance,
)
from betelgeuze_engine_v2.physics.reference_forcefield import evaluate_reference_force_field
from betelgeuze_engine_v2.physics.reference_parameters import (
    AtomNonbondedParameter, ReferenceApplicabilityDomain, ReferenceForceFieldParameters,
)

SCHEMA_ID = "betelgeuze.prepared_v2_cross_interaction/1.0.0"
MAX_RECEPTOR_ATOMS = 10000
MAX_LIGAND_ATOMS = 256
TILE_ATOMS_PER_COMPONENT = 64
MINIMUM_PAIR_DISTANCE_ANGSTROM = ReferenceApplicabilityDomain().minimum_pair_distance_angstrom
SUPPORTED_ELEMENTS = frozenset({"H", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"})


class PreparedInteractionError(ValueError):
    """A supplied state is outside the explicit cross-interaction contract."""


def _finite(value: Any, label: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PreparedInteractionError(f"{label} must be an explicit real number")
    number = float(value)
    if not math.isfinite(number) or (minimum is not None and number < minimum):
        raise PreparedInteractionError(f"{label} is nonfinite or outside its domain")
    return number


def _component(system: AllAtomSystem, rows: Sequence[Mapping[str, Any]], limit: int, side: str):
    if type(system) is not AllAtomSystem or not 1 <= system.atom_count <= limit:
        raise PreparedInteractionError(f"{side} requires a bounded canonical AllAtomSystem")
    validation = require_valid_all_atom_system(system)
    if (system.cell is not None or system.coordinates.dtype != torch.float64
            or system.coordinates.device.type != "cpu"
            or tuple(system.coordinates.shape) != (1, system.atom_count, 3)):
        raise PreparedInteractionError(f"{side} requires one nonperiodic CPU float64 coordinate model")
    if any(a.element not in SUPPORTED_ELEMENTS for a in system.atoms):
        raise PreparedInteractionError(f"{side} has an unsupported element")
    if not isinstance(rows, (list, tuple)) or len(rows) != system.atom_count:
        raise PreparedInteractionError(f"{side} parameters must cover every atom in source order")
    clean = []
    for index, (atom, row) in enumerate(zip(system.atoms, rows)):
        fields = {"atom_index", "charge_e", "sigma_angstrom", "epsilon_kcal_per_mol"}
        if not isinstance(row, Mapping) or set(row) != fields:
            raise PreparedInteractionError(f"{side} atom parameter fields differ from the contract")
        if type(row["atom_index"]) is not int or row["atom_index"] != index:
            raise PreparedInteractionError(f"{side} atom order or duplicate parameter index")
        charge = _finite(row["charge_e"], "charge_e")
        sigma = _finite(row["sigma_angstrom"], "sigma_angstrom", 0.0)
        epsilon = _finite(row["epsilon_kcal_per_mol"], "epsilon_kcal_per_mol", 0.0)
        if atom.partial_charge_e is None or atom.partial_charge_e != charge:
            raise PreparedInteractionError(f"{side} canonical partial charge missing or mismatched")
        if sigma == 0.0 and epsilon != 0.0:
            raise PreparedInteractionError("zero sigma with nonzero epsilon is outside the V1 projection domain")
        clean.append({"atom_index": index, "charge_e": charge,
                      "sigma_angstrom": sigma, "epsilon_kcal_per_mol": epsilon})
    # Successful canonical validation already serialized and hashed this exact
    # system. Retain its digest only for this call; integrity is checked again
    # at the original pre/post-evaluation boundaries below.
    if type(validation.system_sha256) is not str:
        raise PreparedInteractionError(f"{side} canonical validation did not return an identity")
    return clean, validation.system_sha256



def _validate_component_minimum_distance(system: AllAtomSystem, side: str) -> None:
    """Apply the frozen kernel's admission distance independently of tile order.

    V1 checks even excluded neighbors. Validate each full component once, using
    V2's existing nonperiodic cell helpers, so projection boundaries cannot hide
    a rejected pair. The exact acceptance comparison uses the same tensor norm.
    """
    minimum = MINIMUM_PAIR_DISTANCE_ANGSTROM
    periodic = (False, False, False)
    cells = {}
    points = system.coordinates[0].detach().tolist()
    for index, point in enumerate(points):
        key = _cell_key(tuple(point), periodic=periodic, grid_dims=None,
                        cell_widths=(minimum, minimum, minimum))
        for neighbor in _neighbor_cell_keys(key, periodic=periodic, grid_dims=None):
            for previous in cells.get(neighbor, ()):
                squared = _minimum_image_squared_distance(
                    point, points[previous], lengths=None, periodic=periodic)
                if squared <= minimum * minimum * (1.0 + 1e-12):
                    distance = torch.linalg.vector_norm(
                        system.coordinates[0, index] - system.coordinates[0, previous])
                    if float(distance) < minimum:
                        raise PreparedInteractionError(
                            f"{side} pair {previous},{index} is below minimum_pair_distance_angstrom")
        cells.setdefault(key, []).append(index)


def _tile(receptor, ligand, ri, li, rpars, lpars, config):
    # The original complete canonical states remain in the result. A tile has no
    # chemical topology: it evaluates cross pairs only and preserves source maps.
    selected = [(receptor, i, rpars[i], "receptor") for i in ri]
    selected += [(ligand, i, lpars[i], "ligand") for i in li]
    # Source metadata remains in the complete validated parent states/result.
    # Pair-only projections need source maps, not copies of raw source records.
    # Full parent integrity guards still execute before and after every evaluation.
    atoms = tuple(replace(system.atoms[i], index=j, residue_index=j,
                          metadata={"projection_source_side": side, "projection_source_atom": i})
                  for j, (system, i, _, side) in enumerate(selected))
    coordinates = torch.cat((receptor.coordinates[:, ri], ligand.coordinates[:, li]), dim=1).clone()
    system = AllAtomSystem(
        system_id="prepared-cross-pair-mathematical-projection", atoms=atoms, bonds=(),
        residues=tuple(Residue(i, "PRJ", i, 1, (i,), entity_type="non_polymer", hetero=True)
                       for i in range(len(atoms))),
        chains=tuple(Chain(i, str(i), (i,)) for i in range(len(atoms))),
        coordinates=coordinates,
        provenance=StructureProvenance(source_format="mathematical_projection",
            source_id="existing-v2-cross-pair-kernel", parser_name=SCHEMA_ID, parser_version="1"),
        metadata={"is_prepared_molecular_state": False, "cross_projection_only": True},
    )
    params = []
    for index, (_, _, raw, _) in enumerate(selected):
        # Epsilon is EXPLICITLY zero here. LJ and every coordinate derivative are
        # identically zero for this atom, for every partner. V1 requires sigma>0;
        # 1 A is an unused kernel placeholder, never an assigned source parameter.
        # Missing sigma/epsilon/charge is rejected above and cannot take this path.
        sigma = 1.0 if raw["sigma_angstrom"] == 0.0 else raw["sigma_angstrom"]
        params.append(AtomNonbondedParameter(index, sigma, raw["epsilon_kcal_per_mol"], raw["charge_e"]))
    nr, count = len(ri), len(atoms)
    excluded = tuple((i, j) for i in range(count) for j in range(i+1, count)
                     if (i < nr) == (j < nr))
    parameters = ReferenceForceFieldParameters(
        parameter_set_id="source-preserved-prepared-cross-projection", parameter_set_version="1",
        topology_sha256=canonical_topology_sha256(system), atom_parameters=tuple(params),
        excluded_pairs=excluded, cutoff_angstrom=config["cutoff_angstrom"],
        switch_start_angstrom=config["switch_start_angstrom"], dielectric=config["dielectric"],
        screening_kappa_per_angstrom=config["screening_kappa_per_angstrom"],
        applicability_domain=ReferenceApplicabilityDomain(max_atoms=128, max_nonbonded_pairs=16384,
            periodic_orthorhombic_supported=False),
        metadata={"is_prepared_molecular_state": False, "source_parameters_in_parent_result": True},
    )
    graph = build_compact_radius_graph(system.coordinates,
        RadiusGraphConfig(config["cutoff_angstrom"], max_neighbors=count-1, max_atoms_per_cell=count))
    evaluation = evaluate_reference_force_field(system, graph, parameters)
    if not evaluation.execution_complete:
        raise PreparedInteractionError("unchanged V2 evaluator did not complete")
    tensors = [evaluation.term.forces, *evaluation.component_energies.values()]
    if any(not bool(torch.isfinite(t).all()) for t in tensors):
        raise PreparedInteractionError("unchanged V2 evaluator returned a nonfinite quantity")
    pairs = graph.edge_triplets(upper_only=True)
    cross = pairs[:, (pairs[1] < nr) & (pairs[2] >= nr)]
    pair_ids = [(ri[int(i)], li[int(j)-nr]) for i, j in zip(cross[1], cross[2])]
    energies = {name:float(evaluation.component_energies[name][0])
                for name in ("lennard_jones", "screened_coulomb")}
    return energies, evaluation.term.forces[0].detach(), pair_ids


@torch.inference_mode(False)
def evaluate_prepared_cross_interaction(
    receptor: AllAtomSystem, ligand: AllAtomSystem,
    receptor_parameters: Sequence[Mapping[str, Any]], ligand_parameters: Sequence[Mapping[str, Any]],
    *, source_declarations: Mapping[str, str], pocket_center_angstrom: Sequence[float],
    pocket_radius_angstrom: float, cutoff_angstrom: float = 10.0,
    switch_start_angstrom: float = 8.0, dielectric: float = 1.0,
    screening_kappa_per_angstrom: float = 0.0,
) -> dict[str, Any]:
    """Evaluate every receptor-ligand pair under the declared switched model.

    This is not the complete source simulation Hamiltonian: PME, solvent,
    bonded/internal energies and long-range terms are deliberately not evaluated.
    Source topology defaults are not merged; cross pairs have full unit scaling.
    """
    start, cpu = time.perf_counter(), time.process_time()
    fields = {"coordinate_frame_id", "prepared_state_id", "parameter_source_id", "charge_source_id"}
    if (not isinstance(source_declarations, Mapping) or set(source_declarations) != fields
            or any(type(v) is not str or not v.strip() for v in source_declarations.values())):
        raise PreparedInteractionError("complete explicit source declarations are required")
    rp, receptor_sha256 = _component(receptor, receptor_parameters, MAX_RECEPTOR_ATOMS, "receptor")
    lp, ligand_sha256 = _component(ligand, ligand_parameters, MAX_LIGAND_ATOMS, "ligand")
    config = {"cutoff_angstrom": _finite(cutoff_angstrom, "cutoff", 0.0),
              "switch_start_angstrom": _finite(switch_start_angstrom, "switch start", 0.0),
              "dielectric": _finite(dielectric, "dielectric", 0.0),
              "screening_kappa_per_angstrom": _finite(screening_kappa_per_angstrom, "kappa", 0.0)}
    if (not 0.0 < config["switch_start_angstrom"] < config["cutoff_angstrom"] <= 20.0
            or config["cutoff_angstrom"] < MINIMUM_PAIR_DISTANCE_ANGSTROM
            or config["dielectric"] <= 0):
        raise PreparedInteractionError("invalid switch, cutoff or dielectric")
    if not isinstance(pocket_center_angstrom, (tuple, list)) or len(pocket_center_angstrom) != 3:
        raise PreparedInteractionError("explicit three-coordinate pocket center is required")
    center = torch.tensor([_finite(v, "pocket center") for v in pocket_center_angstrom], dtype=torch.float64, device="cpu")
    radius = _finite(pocket_radius_angstrom, "pocket radius", 0.0)
    if radius <= 0 or bool((torch.linalg.vector_norm(ligand.coordinates[0]-center,dim=-1) > radius).any()):
        raise PreparedInteractionError("ligand is outside the explicit pocket")
    _validate_component_minimum_distance(receptor, "receptor")
    _validate_component_minimum_distance(ligand, "ligand")
    # Keep the full protected mutation guards at both original boundaries.
    # An unchanged object has the canonical digest obtained during validation;
    # recomputing its canonical serialization here adds no new identity.
    AllAtomSystem.assert_integrity(receptor)
    AllAtomSystem.assert_integrity(ligand)
    before = (receptor_sha256, ligand_sha256)
    rforces = torch.zeros((receptor.atom_count,3),dtype=torch.float64,device="cpu")
    lforces = torch.zeros((ligand.atom_count,3),dtype=torch.float64,device="cpu")
    values = {"lennard_jones":[], "screened_coulomb":[]}
    pairs = []
    blocks = 0
    outside = 0
    original_projection_slots = 0
    compact_projection_slots = 0
    # The original kernel also computes masked/excluded intermediate terms.
    # Keep the original full projections for numerically extreme inputs: removing
    # an irrelevant atom must not hide an existing nonfinite-intermediate error.
    # The coordinate bound also preserves the original zero-term coordinate-sum
    # overflow rejection. These bounds affect optimization, not input admission.
    compact_enabled = (bool((receptor.coordinates.abs() <= 1e6).all())
                       and bool((ligand.coordinates.abs() <= 1e6).all())
                       and 1e-3 <= config["dielectric"] <= 1e3
                       and config["screening_kappa_per_angstrom"] <= 1e3
                       and all(abs(p["charge_e"]) <= 100.0 and p["sigma_angstrom"] <= 100.0
                               and p["epsilon_kcal_per_mol"] <= 100.0 for p in (*rp, *lp)))
    with torch.inference_mode(False), torch.enable_grad(), torch.autocast(device_type="cpu",enabled=False):
        for rstart in range(0,receptor.atom_count,TILE_ATOMS_PER_COMPONENT):
            ri=list(range(rstart,min(receptor.atom_count,rstart+TILE_ATOMS_PER_COMPONENT)))
            for lstart in range(0,ligand.atom_count,TILE_ATOMS_PER_COMPONENT):
                li=list(range(lstart,min(ligand.atom_count,lstart+TILE_ATOMS_PER_COMPONENT)))
                # Exact bounded distance cull, not a candidate omission. Cutoff is
                # part of the declared physics model; at cutoff the switch is zero.
                offsets = receptor.coordinates[0,ri,None]-ligand.coordinates[0,None,li]
                distances = torch.linalg.vector_norm(offsets, dim=-1)
                if not bool((distances <= config["cutoff_angstrom"]).any()):
                    outside += 1
                    continue
                # Full states passed admission above. Within this mathematical
                # tile, an atom outside every opposite-side cutoff cube cannot
                # contribute a cross pair. Keep a conservative rounding margin;
                # the unchanged V2 graph still decides the exact spherical set.
                active_ri, active_li = ri, li
                if compact_enabled:
                    cube = (offsets.abs() <= config["cutoff_angstrom"] * (1.0 + 1e-12)).all(dim=-1)
                    active_ri = [i for i, keep in zip(ri, cube.any(dim=1).tolist()) if keep]
                    active_li = [i for i, keep in zip(li, cube.any(dim=0).tolist()) if keep]
                    if not active_ri or not active_li:
                        raise PreparedInteractionError("surviving cross tile has no conservative projection")
                original_projection_slots += len(ri) + len(li)
                compact_projection_slots += len(active_ri) + len(active_li)
                energy,force,ids=_tile(receptor,ligand,active_ri,active_li,rp,lp,config)
                blocks += 1
                pairs.extend(ids)
                for name in values:
                    values[name].append(energy[name])
                rforces[active_ri] += force[:len(active_ri)]
                lforces[active_li] += force[len(active_ri):]
    AllAtomSystem.assert_integrity(receptor)
    AllAtomSystem.assert_integrity(ligand)
    if len(pairs) != len(set(pairs)):
        raise PreparedInteractionError("cross pair evaluated more than once")
    if not bool(torch.isfinite(rforces).all()) or not bool(torch.isfinite(lforces).all()):
        raise PreparedInteractionError("cross-force accumulation returned a nonfinite quantity")
    energy={k:math.fsum(v) for k,v in values.items()}
    if any(not math.isfinite(value) for value in energy.values()):
        raise PreparedInteractionError("cross-energy accumulation returned a nonfinite quantity")
    zero_sigma=[{"side":side,"atom_index":r["atom_index"],"source_sigma_angstrom":0.0,
                  "source_epsilon_kcal_per_mol":0.0,"unused_kernel_sigma_angstrom":1.0}
                 for side,rows in (("receptor",rp),("ligand",lp)) for r in rows if r["sigma_angstrom"]==0.0]
    return {"schema_id":SCHEMA_ID,"status":"evaluated", "source_declarations":dict(source_declarations),
        "model":{"id":"existing_v2_switched_cross_lj_screened_coulomb_v1",**config,
                 "mixing":"Lorentz-Berthelot","cross_pair_scaling":1.0,"periodic":False,
                 "source_full_simulation_hamiltonian_reproduced":False,
                 "minimum_pair_distance_angstrom":MINIMUM_PAIR_DISTANCE_ANGSTROM,
                 "minimum_distance_scope":"all source atoms; admission independent of tile order"},
        "sources":{"receptor":{"system_sha256":before[0],"coordinates_sha256":canonical_coordinates_sha256(receptor),
                    "system":canonical_json_value(canonical_system_document(receptor)),"nonbonded_parameters":rp},
                   "ligand":{"system_sha256":before[1],"coordinates_sha256":canonical_coordinates_sha256(ligand),
                    "system":canonical_json_value(canonical_system_document(ligand)),"nonbonded_parameters":lp}},
        "pocket":{"center_angstrom":list(pocket_center_angstrom),"radius_angstrom":radius},
        "quantities":{"cross_lennard_jones_kcal_per_mol":energy["lennard_jones"],
                      "cross_screened_coulomb_kcal_per_mol":energy["screened_coulomb"],
                      "cross_total_kcal_per_mol":math.fsum(energy.values()),
                      "receptor_cross_forces_kcal_per_mol_angstrom":rforces.tolist(),
                      "ligand_cross_forces_kcal_per_mol_angstrom":lforces.tolist(),
                      "internal_energy":None,"strain":None,"solvation":None,"residual":None,"affinity":None},
        "unevaluated_reason":"cross-component evaluation only; no internal, solvent or learned terms",
        "source_zero_sigma_projection":zero_sigma,
        "zero_sigma_projection_reason":"source sigma=epsilon=0 retained; positive V1 kernel sigma is unused because LJ and its coordinate derivative vanish identically",
        "pair_accounting":{"requested_cross_pairs":receptor.atom_count*ligand.atom_count,
                           "within_declared_cutoff":len(pairs),"cross_pair_indices":sorted(pairs),
                           "pair_indices_sha256":sha256_canonical(sorted(pairs)),
                           "kernel_tiles":blocks,"exact_outside_cutoff_tiles":outside,
                           "projection_compaction": {"algorithm": "conservative_cross_cube_v1",
                               "enabled": compact_enabled,
                               "eligibility_scope": "optimization only: abs(coordinates)<=1e6 Angstrom; abs(charge),sigma,epsilon<=100; 1e-3<=dielectric<=1e3; kappa<=1e3",
                               "fallback": None if compact_enabled else "original_full_tiles_preserve_numeric_guards",
                               "original_atom_slots": original_projection_slots,
                               "projected_atom_slots": compact_projection_slots,
                               "omitted_outside_cube_atom_slots": original_projection_slots-compact_projection_slots,
                               "scope": "mathematical projection work only; full sources and requested cross pairs retained"},
                           "receptor_atoms":receptor.atom_count,"ligand_atoms":ligand.atom_count},
        "cost":{"wall_seconds":time.perf_counter()-start,"cpu_seconds":time.process_time()-cpu,
                "scope":"validation, canonical identity, bounded projection and V2 cross evaluation; startup/import/output excluded"},
        "adapter_source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "uncertainty":None,"uncertainty_calibrated":False,"scientifically_validated":False,
        "customer_execution":False,"external_solver_called":False}
