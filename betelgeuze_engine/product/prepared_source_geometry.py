"""Bounded source-coordinate observations, separate from physical admission.

A one-angstrom search radius describes unusually short source separations. It
is not a calibrated clash criterion, bond-length model, or validity threshold.
Only supplied direct bonds are classified; no chemical connectivity is inferred.
"""
from __future__ import annotations

import hashlib
import heapq
from pathlib import Path
import time

import torch

from betelgeuze_engine_v2.geometry.neighbors import (
    NeighborOverflowError, RadiusGraphConfig, build_compact_radius_graph,
)
from betelgeuze_engine_v2.molecular import AllAtomSystem, require_valid_all_atom_system

SCHEMA = "prepared_source_geometry_observation_v1"
SEARCH_RADIUS_ANGSTROM = 1.0
MAX_DISPLAYED_PAIRS = 16
MAX_COMPONENT_ATOMS = {"receptor": 10000, "ligand": 256}


def _bond_context(provenance, side, system):
    count = system.atom_count
    topologies = provenance.get("original_topologies", {})
    labels = {"ligand_itp"}
    if side == "receptor":
        # Inspect expected sources as well as present sources. Otherwise a
        # wholly missing chain/molecule can look like complete bond coverage.
        labels = {name for name in topologies if name.startswith("protein_chain_")}
        for atom in system.atoms:
            chain = system.chains[system.residues[atom.residue_index].chain_index]
            base = "protein_chain_" + chain.chain_id
            source = atom.metadata.get("prepared_gromacs_source", {})
            label = source.get("source_molecule_label", base)
            if not isinstance(label, str) or not (label == base or label.startswith(base + "_molecule_")):
                raise ValueError("source molecule label does not match canonical chain")
            labels.add(label)
    if not labels or any("bonds" not in topologies.get(label, {}).get("sections", {})
                         for label in labels):
        return None, "missing_in_one_or_more_source_molecules"
    rows = provenance.get(side + "_source_bond_adjacency")
    if not isinstance(rows, list):
        return None, "source_adjacency_unavailable"
    bonds = set()
    for row in rows:
        if (not isinstance(row, (list, tuple)) or len(row) != 2
                or any(type(i) is not int or not 0 <= i < count for i in row)
                or row[0] == row[1]):
            raise ValueError("invalid explicit source bond adjacency")
        pair = tuple(sorted(row))
        if pair in bonds:
            raise ValueError("duplicate explicit source bond adjacency")
        bonds.add(pair)
    return bonds, "present_in_all_source_molecules_not_chemical_completeness"


def _atom(system, side, index):
    atom = system.atoms[index]
    residue = system.residues[atom.residue_index]
    chain = system.chains[residue.chain_index]
    return {"component": side, "atom_index": index, "name": atom.name,
            "element": atom.element, "chain_id": chain.chain_id,
            "residue_number": residue.sequence_number, "residue_name": residue.name,
            "insertion_code": residue.insertion_code, "source_serial": atom.serial}


def _remember(heap, distance, first, second):
    # A bounded heap keeps the smallest distance/index tuples without storing
    # every observation. Counts below always cover the complete returned graph.
    item = (-distance, -first, -second)
    if len(heap) < MAX_DISPLAYED_PAIRS:
        heapq.heappush(heap, item)
    elif item > heap[0]:
        heapq.heapreplace(heap, item)


def observe_prepared_source_geometry(receptor: AllAtomSystem, ligand: AllAtomSystem,
                                     preparation_provenance: dict) -> dict:
    """Observe unchanged canonical source coordinates before cross evaluation.

    Unavailable geometry returns null counts, including graph capacity overflow.
    This helper cannot authorize, reject, modify or rescore a molecular state.
    The consumer separately retains any diagnostic exception and still invokes
    the unchanged physical evaluator.
    """
    started, cpu = time.perf_counter(), time.process_time()
    answer = {"schema_version": SCHEMA, "status": "unavailable", "groups": None,
              "search_radius_angstrom": SEARCH_RADIUS_ANGSTROM,
              "comparison": "distance <= search radius",
              "scope": "all supplied source atoms; no pocket filtering; one nonperiodic frame",
              "direct_bond_policy": "classify only supplied direct adjacency; no inferred or 1-3/1-4 exclusions",
              "display_limit_per_list": MAX_DISPLAYED_PAIRS,
              "scientifically_validated": False, "physical_validity_assessed": False,
              "affects_score_or_admission": False, "coordinates_changed": False,
              "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        systems = {"receptor": receptor, "ligand": ligand}
        identities, bonds, groups = {}, {}, {}
        for side, system in systems.items():
            if type(system) is not AllAtomSystem or not 1 <= system.atom_count <= MAX_COMPONENT_ATOMS[side]:
                raise ValueError("source geometry requires bounded canonical components")
            if (system.cell is not None or system.coordinates.dtype != torch.float64
                    or system.coordinates.device.type != "cpu"
                    or tuple(system.coordinates.shape) != (1, system.atom_count, 3)):
                raise ValueError("source geometry requires one nonperiodic CPU float64 frame")
            identities[side] = require_valid_all_atom_system(system).system_sha256
            bonds[side], availability = _bond_context(preparation_provenance, side, system)
            groups[side] = {"source_atom_count": system.atom_count,
                            "possible_unique_pairs": system.atom_count * (system.atom_count - 1) // 2,
                            "direct_bond_table_status": availability}
        groups["cross"] = {"source_atom_counts": {s: x.atom_count for s, x in systems.items()},
                           "possible_unique_pairs": receptor.atom_count * ligand.atom_count,
                           "direct_bond_table_status": "not_classified_between_supplied_components"}
        answer["source_system_sha256"] = identities
        heaps, non_direct_heaps = {}, {}
        for name, group in groups.items():
            available = name in bonds and bonds[name] is not None
            group.update(pair_count_within_radius=0,
                         direct_bond_pair_count=0 if available else None,
                         non_direct_bond_pair_count=0 if available else None)
            heaps[name], non_direct_heaps[name] = [], []
        # This is only a geometric tensor projection, not a third molecular
        # state. Canonical owners, atom indices and supplied coordinates remain.
        with torch.no_grad():
            coordinates = torch.cat((receptor.coordinates.detach(), ligand.coordinates.detach()), dim=1)
            graph = build_compact_radius_graph(coordinates,
                RadiusGraphConfig(SEARCH_RADIUS_ANGSTROM, max_neighbors=64, max_atoms_per_cell=64))
            batch, source, slot = torch.nonzero(graph.upper_mask(), as_tuple=True)
            target = graph.indices[batch, source, slot]
            distances = graph.distances[batch, source, slot]
            for first, second, distance in zip(source.tolist(), target.tolist(), distances.tolist()):
                if second < receptor.atom_count:
                    name, a, b = "receptor", first, second
                elif first >= receptor.atom_count:
                    name, a, b = "ligand", first - receptor.atom_count, second - receptor.atom_count
                else:
                    name, a, b = "cross", first, second - receptor.atom_count
                group = groups[name]
                group["pair_count_within_radius"] += 1
                _remember(heaps[name], distance, a, b)
                if name in bonds and bonds[name] is not None:
                    if (a, b) in bonds[name]:
                        group["direct_bond_pair_count"] += 1
                    else:
                        group["non_direct_bond_pair_count"] += 1
                        _remember(non_direct_heaps[name], distance, a, b)
        def rows(name, heap):
            first_side, second_side = ("receptor", "ligand") if name == "cross" else (name, name)
            return [{"distance_angstrom": distance,
                     "atoms": [_atom(systems[first_side], first_side, a),
                               _atom(systems[second_side], second_side, b)]}
                    for distance, a, b in sorted((-d, -a, -b) for d, a, b in heap)]
        for name, group in groups.items():
            group["closest_pairs"] = rows(name, heaps[name])
            group["unlisted_pair_count"] = group["pair_count_within_radius"] - len(heaps[name])
            available = group["non_direct_bond_pair_count"] is not None
            group["closest_non_direct_bond_pairs"] = rows(name, non_direct_heaps[name]) if available else None
            group["unlisted_non_direct_bond_pair_count"] = (
                group["non_direct_bond_pair_count"] - len(non_direct_heaps[name]) if available else None)
        answer.update(status="observed", groups=groups, graph_diagnostics=graph.diagnostics.to_dict())
    except NeighborOverflowError as exc:
        answer.update(reason="bounded_neighbor_capacity_exceeded",
                      graph_diagnostics=exc.diagnostics.to_dict())
    except Exception as exc:
        answer.update(reason=str(exc), error_type=type(exc).__name__)
    answer["cost"] = {"wall_seconds": time.perf_counter() - started,
                      "cpu_seconds": time.process_time() - cpu,
                      "scope": "source validation, bounded geometric observation and summary"}
    return answer
