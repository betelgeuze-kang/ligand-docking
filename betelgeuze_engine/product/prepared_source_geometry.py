"""Bounded source-coordinate observations, separate from physical admission.

A one-angstrom search radius describes unusually short source separations. It
is not a calibrated clash criterion, bond-length model, or validity threshold.
Only supplied direct bonds are classified; no chemical connectivity is inferred.
Supplied direct-bond lengths are observed at every distance, separately from
the one-angstrom search, without inferring acceptable length ranges.
"""
from __future__ import annotations

import hashlib
import heapq
import math
from pathlib import Path
import re
import time

import torch

from betelgeuze_engine_v2.geometry.neighbors import (
    NeighborOverflowError, RadiusGraphConfig, build_compact_radius_graph,
)
from betelgeuze_engine_v2.molecular import AllAtomSystem
from betelgeuze_engine.product.prepared_validation import require_valid_prepared_system

SCHEMA = "prepared_source_geometry_observation_v1"
_COMPILED_SCHEMAS = {"compiled_gromacs_cross_particles_v1", "compiled_gromacs_cross_particles_v2"}


def _compiled_profile(provenance):
    schema = provenance.get("schema_version")
    return type(schema) is str and schema in _COMPILED_SCHEMAS
SEARCH_RADIUS_ANGSTROM = 1.0
MAX_DISPLAYED_PAIRS = 16
MAX_COMPONENT_ATOMS = {"receptor": 10000, "ligand": 256}


def _bond_context(provenance, side, system):
    count = system.atom_count
    if _compiled_profile(provenance):
        sections = provenance.get("selected_molecule_bond_section_presence")
        entry = sections.get(side) if isinstance(sections, dict) else None
        if (not isinstance(entry, dict) or type(entry.get("present")) is not bool
                or entry.get("source_molecule") != system.provenance.source_id):
            return None, "source_bond_section_presence_unavailable"
        if not entry["present"]:
            return None, "missing_in_one_or_more_source_molecules"
    else:
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


def _source_bond_equilibria(provenance, side, system, bonds):
    """Bind explicit source bond rows to canonical indices, without inference."""
    if bonds is None or _compiled_profile(provenance):
        return {}
    topologies, sources = provenance.get("original_topologies"), provenance.get("sources")
    if not isinstance(topologies, dict) or not isinstance(sources, dict):
        return {}
    canonical_by_source = {}
    for index, atom in enumerate(system.atoms):
        origin = atom.metadata.get("prepared_gromacs_source", {})
        source_index = origin.get("source_atom_index") if isinstance(origin, dict) else None
        if type(source_index) is not int or source_index < 1:
            return {}
        if side == "ligand":
            label = "ligand_itp"
        else:
            chain = system.chains[system.residues[atom.residue_index].chain_index]
            label = origin.get("source_molecule_label", "protein_chain_" + chain.chain_id)
        if not isinstance(label, str) or label not in topologies or label not in sources:
            return {}
        key = (label, source_index)
        if key in canonical_by_source:
            raise ValueError("duplicate source atom identity in bond observation")
        canonical_by_source[key] = index

    records = {}
    for label in {key[0] for key in canonical_by_source}:
        source = sources[label]
        if not isinstance(source, dict) or not isinstance(source.get("sha256"), str):
            raise ValueError("source bond hash unavailable")
        rows = topologies[label].get("sections", {}).get("bonds", [])
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("tokens"), list):
                raise ValueError("invalid source bond row")
            tokens = row["tokens"]
            if len(tokens) not in (3, 5):
                raise ValueError("invalid source bond parameter width")
            first = canonical_by_source.get((label, int(tokens[0])))
            second = canonical_by_source.get((label, int(tokens[1])))
            if first is None or second is None:
                raise ValueError("source bond atom missing from canonical component")
            pair = tuple(sorted((first, second)))
            if pair not in bonds or pair in records:
                raise ValueError("source bond row and canonical adjacency differ")
            equilibrium = float(tokens[3]) * 10.0 if len(tokens) == 5 else None
            if equilibrium is not None and not math.isfinite(equilibrium):
                raise ValueError("nonfinite converted source bond equilibrium length")
            records[pair] = {
                "status": "explicit" if equilibrium is not None else "inherited_unknown",
                "equilibrium_length_nm_token": tokens[3] if len(tokens) == 5 else None,
                "equilibrium_length_angstrom": equilibrium,
                "source_topology": label,
                "source_line": row["line"],
                "source_sha256": source["sha256"],
            }
    if set(records) != bonds:
        raise ValueError("source bond row coverage differs from canonical adjacency")
    return records


def _direct_bond_lengths(system, side, bonds, source_equilibria):
    """Describe every supplied direct bond without a length/validity threshold."""
    if bonds is None:
        return None
    coordinates = system.coordinates.detach()[0].tolist()
    shortest, longest = [], []
    minimum = maximum = largest_absolute_deviation = None
    explicit_count = 0
    for first, second in sorted(bonds):
        distance = math.dist(coordinates[first], coordinates[second])
        if not math.isfinite(distance):
            raise ValueError("nonfinite supplied direct bond distance")
        minimum = distance if minimum is None else min(minimum, distance)
        maximum = distance if maximum is None else max(maximum, distance)
        reference = source_equilibria.get((first, second))
        if reference is not None and reference["status"] == "explicit":
            explicit_count += 1
            signed_deviation = distance - reference["equilibrium_length_angstrom"]
            if not math.isfinite(signed_deviation):
                raise ValueError("nonfinite source bond length difference")
            deviation = abs(signed_deviation)
            largest_absolute_deviation = (deviation if largest_absolute_deviation is None
                                          else max(largest_absolute_deviation, deviation))
        _remember(shortest, distance, first, second)
        # The minimum heap entry is the least preferred longest pair. For ties,
        # lower source atom indices remain in the bounded display.
        item = (distance, -first, -second)
        if len(longest) < MAX_DISPLAYED_PAIRS:
            heapq.heappush(longest, item)
        elif item > longest[0]:
            heapq.heapreplace(longest, item)

    def row(distance, first, second):
        source = source_equilibria.get((first, second))
        if source is None:
            source = {"status": "source_parameter_unavailable", "equilibrium_length_nm_token": None,
                      "equilibrium_length_angstrom": None,
                      "source_topology": None, "source_line": None, "source_sha256": None}
        equilibrium = source["equilibrium_length_angstrom"]
        return {"distance_angstrom": distance,
                "atoms": [_atom(system, side, first), _atom(system, side, second)],
                "source_equilibrium": {**source,
                    "measured_minus_source_angstrom": (
                        distance - equilibrium if equilibrium is not None else None)}}

    return {
        "bond_count": len(bonds),
        "minimum_angstrom": minimum,
        "maximum_angstrom": maximum,
        "shortest_pairs": [row(d, a, b) for d, a, b in sorted(
            (-d, -a, -b) for d, a, b in shortest)],
        "longest_pairs": [row(d, a, b) for d, a, b in sorted(
            ((d, -a, -b) for d, a, b in longest),
            key=lambda item: (-item[0], item[1], item[2]))],
        "unlisted_pair_count": max(0, len(bonds) - MAX_DISPLAYED_PAIRS),
        "explicit_source_equilibrium_count": explicit_count,
        "unknown_source_equilibrium_count": len(bonds) - explicit_count,
        "largest_absolute_measured_minus_source_angstrom": largest_absolute_deviation,
        "length_validity_assessed": False,
    }


def _source_angle_rows(provenance, side, system):
    """Resolve original angle rows without inferring missing bonded parameters."""
    if _compiled_profile(provenance):
        return None, "compiled_source_angle_mapping_unavailable"
    topologies, sources = provenance.get("original_topologies"), provenance.get("sources")
    if not isinstance(topologies, dict):
        return None, "source_angle_topologies_unavailable"
    labels = {"ligand_itp"} if side == "ligand" else {
        name for name in topologies if name.startswith("protein_chain_")}
    for atom in system.atoms:
        if side == "ligand":
            continue
        chain = system.chains[system.residues[atom.residue_index].chain_index]
        base = "protein_chain_" + chain.chain_id
        origin = atom.metadata.get("prepared_gromacs_source", {})
        label = origin.get("source_molecule_label", base) if isinstance(origin, dict) else base
        if not isinstance(label, str) or not (label == base or label.startswith(base + "_molecule_")):
            return None, "source_angle_molecule_label_unavailable"
        labels.add(label)
    if not labels or any(label not in topologies or
                         "angles" not in topologies[label].get("sections", {}) for label in labels):
        return None, "missing_in_one_or_more_source_molecules"
    if not isinstance(sources, dict):
        return None, "source_angle_identity_unavailable"
    if provenance.get("source_hashes_postflight_verified") is not True:
        return None, "source_angle_identity_unverified"
    ordered_labels = sorted(labels)
    for label in ordered_labels:
        source = sources.get(label)
        digest = source.get("sha256") if isinstance(source, dict) else None
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            return None, "source_angle_identity_unavailable"

    canonical_by_source = {}
    for index, atom in enumerate(system.atoms):
        origin = atom.metadata.get("prepared_gromacs_source", {})
        source_index = origin.get("source_atom_index") if isinstance(origin, dict) else None
        if type(source_index) is not int or source_index < 1:
            return None, "source_angle_atom_index_unavailable"
        if side == "ligand":
            label = "ligand_itp"
        else:
            chain = system.chains[system.residues[atom.residue_index].chain_index]
            label = origin.get("source_molecule_label", "protein_chain_" + chain.chain_id)
        if label not in labels:
            return None, "source_angle_molecule_label_unavailable"
        key = (label, source_index)
        if key in canonical_by_source:
            return None, "duplicate_source_angle_atom_identity"
        canonical_by_source[key] = index

    if any(not isinstance(topologies[label]["sections"]["angles"], list)
           for label in ordered_labels):
        return None, "invalid_source_angle_section"
    if all(not topologies[label]["sections"]["angles"] for label in ordered_labels):
        return ((), 0), "present_empty_in_all_source_molecules"
    angle_count = 0
    for label in ordered_labels:
        for row in topologies[label]["sections"]["angles"]:
            if not isinstance(row, dict) or not isinstance(row.get("tokens"), list):
                return None, "invalid_source_angle_row"
            tokens = row["tokens"]
            if len(tokens) < 4:
                return None, "invalid_source_angle_row"
            try:
                indices = [canonical_by_source[(label, int(token))] for token in tokens[:3]]
            except (KeyError, ValueError):
                return None, "source_angle_atom_mapping_unavailable"
            if len(set(indices)) != 3:
                return None, "invalid_source_angle_triplet"
            angle_count += 1

    def bound_rows():
        for label in ordered_labels:
            source_hash = sources[label]["sha256"]
            for row in topologies[label]["sections"]["angles"]:
                indices = [canonical_by_source[(label, int(token))]
                           for token in row["tokens"][:3]]
                yield label, row, source_hash, indices

    return (bound_rows(), angle_count), "present_in_all_source_molecules_not_chemical_completeness"


def _source_angles(system, side, bound_rows):
    """Observe source-listed triplets and explicit function-1 equilibria."""
    if bound_rows is None:
        return None
    bound_rows, angle_count = bound_rows
    coordinates = system.coordinates.detach()[0].tolist() if angle_count else ()
    measured_count = explicit_count = inherited_count = unsupported_count = undefined_count = 0
    largest_difference = None
    displayed = []
    for ordinal, (label, source_row, source_hash, indices) in enumerate(bound_rows):
        first, center, last = indices
        left = [coordinates[first][axis] - coordinates[center][axis] for axis in range(3)]
        right = [coordinates[last][axis] - coordinates[center][axis] for axis in range(3)]
        left_norm, right_norm = math.hypot(*left), math.hypot(*right)
        if left_norm == 0.0 or right_norm == 0.0:
            measured, geometry_status = None, "undefined_zero_vector"
            undefined_count += 1
        else:
            cross = (left[1] * right[2] - left[2] * right[1],
                     left[2] * right[0] - left[0] * right[2],
                     left[0] * right[1] - left[1] * right[0])
            dot = sum(a * b for a, b in zip(left, right))
            measured = math.degrees(math.atan2(math.hypot(*cross), dot))
            if not math.isfinite(measured):
                raise ValueError("nonfinite source angle measurement")
            geometry_status = "defined"
            measured_count += 1

        tokens = source_row["tokens"]
        equilibrium = None
        try:
            function = int(tokens[3])
        except ValueError:
            function = None
        if function == 1 and len(tokens) == 4:
            parameter_status = "inherited_unknown"
            inherited_count += 1
        elif function == 1 and len(tokens) == 6:
            try:
                equilibrium, force_constant = float(tokens[4]), float(tokens[5])
            except ValueError:
                equilibrium = force_constant = None
            if (equilibrium is not None and force_constant is not None
                    and math.isfinite(equilibrium) and math.isfinite(force_constant)):
                parameter_status = "explicit"
                explicit_count += 1
            else:
                equilibrium = None
                parameter_status = "unsupported_source_parameters"
                unsupported_count += 1
        else:
            parameter_status = "unsupported_source_parameters"
            unsupported_count += 1
        difference = measured - equilibrium if measured is not None and equilibrium is not None else None
        if difference is not None:
            absolute = abs(difference)
            largest_difference = absolute if largest_difference is None else max(largest_difference, absolute)
        # Keep only the largest explicit discrepancies. Source-row ordinal
        # breaks ties without comparing or retaining unbounded atom records.
        item = (abs(difference) if difference is not None else -1.0, -ordinal,
                (label, source_row, source_hash, indices, measured,
                 geometry_status, parameter_status, equilibrium, difference))
        if len(displayed) < MAX_DISPLAYED_PAIRS:
            heapq.heappush(displayed, item)
        elif item[:2] > displayed[0][:2]:
            heapq.heapreplace(displayed, item)

    def display_row(record):
        label, source_row, source_hash, indices, measured, geometry_status, parameter_status, equilibrium, difference = record
        return {
            "measured_angle_degrees": measured,
            "geometry_status": geometry_status,
            "atoms": [_atom(system, side, index) for index in indices],
            "source_equilibrium": {
                "status": parameter_status,
                "equilibrium_angle_degrees_token": (
                    source_row["tokens"][4] if parameter_status == "explicit" else None),
                "equilibrium_angle_degrees": equilibrium,
                "source_topology": label,
                "source_line": source_row["line"],
                "source_sha256": source_hash,
                "measured_minus_source_degrees": difference,
            },
        }

    return {
        "angle_count": angle_count,
        "measured_angle_count": measured_count,
        "undefined_geometry_count": undefined_count,
        "explicit_source_equilibrium_count": explicit_count,
        "unknown_source_equilibrium_count": angle_count - explicit_count,
        "inherited_source_equilibrium_count": inherited_count,
        "unsupported_source_parameters_count": unsupported_count,
        "largest_absolute_measured_minus_source_degrees": largest_difference,
        "displayed_angles": [display_row(item[2]) for item in sorted(
            displayed, key=lambda item: (-item[0], -item[1]))],
        "unlisted_angle_count": max(0, angle_count - MAX_DISPLAYED_PAIRS),
        "angle_validity_assessed": False,
    }


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
            identities[side] = require_valid_prepared_system(system).system_sha256
            bonds[side], availability = _bond_context(preparation_provenance, side, system)
            equilibria = _source_bond_equilibria(preparation_provenance, side, system, bonds[side])
            source_angle_rows, angle_status = _source_angle_rows(preparation_provenance, side, system)
            groups[side] = {"source_atom_count": system.atom_count,
                            "possible_unique_pairs": system.atom_count * (system.atom_count - 1) // 2,
                            "direct_bond_table_status": availability,
                            "supplied_direct_bond_lengths": _direct_bond_lengths(
                                system, side, bonds[side], equilibria),
                            "source_angle_table_status": angle_status,
                            "supplied_source_angles": _source_angles(system, side, source_angle_rows)}
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
