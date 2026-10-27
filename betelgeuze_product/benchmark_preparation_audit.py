"""Coordinate-free preparation-demand diagnostics, not preparation or admission.

A graph observation may be incomplete (notably implicit hydrogen atoms). Its
paths describe only the supplied graph. Parameter inventory matching checks
indices only, never numerical values, chemistry, source validity or a model.
"""
from __future__ import annotations

import hashlib
import json
import re
from itertools import combinations

TOPOLOGY_SCHEMA = "benchmark_ligand_topology_observation/1.0.0"
REPORT_SCHEMA = "benchmark_preparation_demand_audit/1.0.0"
MAX_ATOMS = 256
MAX_PATHS = 20000


class PreparationAuditError(ValueError):
    """Malformed or unsupported diagnostic input; no calculation was attempted."""


def _require(value, message):
    if not value:
        raise PreparationAuditError(message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _index(value, count):
    _require(type(value) is int and 0 <= value < count, "atom index outside supplied graph")
    return value


def _path(row, count, size):
    _require(type(row) in (list, tuple) and len(row) == size, "exact atom path required")
    result = tuple(_index(value, count) for value in row)
    _require(len(set(result)) == size, "path repeats an atom")
    return min(result, result[::-1])


def graph_demands(topology):
    """Return graph-implied paths; no bond order, stereo or H perception occurs."""
    _require(type(topology) is dict and set(topology) == {
        "schema_id", "source_sha256", "elements", "bonds", "hydrogen_state"
    }, "exact topology observation required")
    _require(topology["schema_id"] == TOPOLOGY_SCHEMA, "unsupported topology schema")
    source = topology["source_sha256"]
    _require(type(source) is str and re.fullmatch(r"[0-9a-f]{64}", source) is not None,
             "source byte SHA256 required")
    elements = topology["elements"]
    _require(type(elements) is list and 1 <= len(elements) <= MAX_ATOMS,
             "bounded explicit element list required")
    _require(all(type(e) is str and re.fullmatch(r"[A-Z][a-z]?", e) for e in elements),
             "explicit element symbols required")
    _require(topology["hydrogen_state"] in ("unverified", "declared_all_explicit"),
             "explicit hydrogen observation state required")
    rows = topology["bonds"]
    n = len(elements)
    _require(type(rows) is list and len(rows) <= 2048, "bounded bond list required")
    bonds = {_path(row, n, 2) for row in rows}
    _require(len(bonds) == len(rows), "duplicate or reversed bond")
    adjacency = [set() for _ in range(n)]
    for i, j in bonds:
        adjacency[i].add(j)
        adjacency[j].add(i)
    _require(all(len(a) <= 12 for a in adjacency), "graph degree exceeds diagnostic bound")
    reached, pending = set(), [0]
    while pending:
        i = pending.pop()
        if i not in reached:
            reached.add(i)
            pending.extend(adjacency[i] - reached)
    _require(len(reached) == n, "one connected ligand graph required")
    angles = {(i, j, k) for j, neighbors in enumerate(adjacency)
              for i, k in combinations(sorted(neighbors), 2)}
    proper = set()
    for j, k in bonds:
        for i in adjacency[j] - {k}:
            for l in adjacency[k] - {j}:
                if len({i, j, k, l}) == 4:
                    path = (i, j, k, l)
                    proper.add(min(path, path[::-1]))
        _require(len(proper) <= MAX_PATHS, "proper-path capacity exceeded")
    _require(len(angles) <= MAX_PATHS, "angle-path capacity exceeded")
    # These are graph distances, not a force-field exclusion/scaling policy.
    separation = {1: set(), 2: set(), 3: set()}
    for start in range(n):
        seen, frontier = {start}, {start}
        for distance in (1, 2, 3):
            frontier = {j for i in frontier for j in adjacency[i]} - seen
            seen.update(frontier)
            separation[distance].update((start, j) for j in frontier if start < j)
    normalized = {**topology, "bonds": [list(p) for p in sorted(bonds)]}
    return {
        "source_sha256": source,
        "observation_sha256": hashlib.sha256(_canonical(normalized).encode()).hexdigest(),
        "atom_count": n,
        "explicit_hydrogen_count": elements.count("H"),
        "hydrogen_state": topology["hydrogen_state"],
        "hydrogen_completeness_verified": False,
        "demand_scope": "supplied_graph_only_not_implicit_hydrogens",
        "atom_indices": list(range(n)),
        "bond_paths": [list(p) for p in sorted(bonds)],
        "angle_paths": [list(p) for p in sorted(angles)],
        "proper_paths": [list(p) for p in sorted(proper)],
        "shortest_path_pair_counts": {str(k): len(v) for k, v in separation.items()},
    }


def _coverage(expected, rows, count, keys, *, multiple_terms_per_path=False):
    duplicates = set()
    if rows is None:
        supplied, term_count = set(), 0
        status = "not_supplied"
    else:
        _require(type(rows) is list and len(rows) <= MAX_PATHS, "bounded parameter rows required")
        supplied = set()
        for row in rows:
            _require(type(row) is dict and set(keys) <= set(row), "parameter atom fields missing")
            raw = tuple(_index(row[k], count) for k in keys)
            if len(keys) > 1:
                raw = _path(raw, count, len(keys))
            if raw in supplied:
                duplicates.add(raw)
            supplied.add(raw)
        term_count = len(rows)
        status = "indices_match" if supplied == expected and (not duplicates or multiple_terms_per_path) else "indices_mismatch"
    return {"status": status, "observed_graph_unique_count": len(expected),
            "supplied_term_count": term_count, "supplied_unique_count": len(supplied),
            "missing": [list(p) for p in sorted(expected - supplied)],
            "unexpected": [list(p) for p in sorted(supplied - expected)],
            "repeated_index_paths": [list(p) for p in sorted(duplicates)],
            "multiple_terms_per_path_allowed": multiple_terms_per_path}


def audit_preparation(topology, *, receptor_atom_count, base_parameters=None,
                      receptor_parameters=None):
    """Inventory supplied term indices and unresolved preparation work.

    Omitted arrays mean not supplied, empty arrays mean supplied but empty.
    Multiple proper Fourier terms per path are permitted in this index audit.
    A missing graph path is not proof of a missing physical interaction: the
    force-field zero-term policy and model coverage must be checked separately.
    Even all matching inventories never authorize execution or certify chemistry.
    """
    demands = graph_demands(topology)
    _require(type(receptor_atom_count) is int and 1 <= receptor_atom_count <= 8192,
             "bounded observed receptor atom count required")
    _require(base_parameters is None or type(base_parameters) is dict,
             "parameter document must be dictionary or absent")
    base = {} if base_parameters is None else base_parameters
    n = demands["atom_count"]
    coverage = {}
    groups = (("atom_parameters", "atom_indices", ("atom_index",)),
              ("bonds", "bond_paths", ("atom_i", "atom_j")),
              ("angles", "angle_paths", ("atom_i", "atom_j", "atom_k")),
              ("torsions", "proper_paths", ("atom_i", "atom_j", "atom_k", "atom_l")))
    for name, demand, keys in groups:
        expected = {(i,) for i in demands[demand]} if name == "atom_parameters" else {
            tuple(p) for p in demands[demand]}
        coverage[name] = _coverage(expected, base.get(name), n, keys,
                                   multiple_terms_per_path=name == "torsions")
    coverage["receptor_atom_parameters"] = _coverage(
        {(i,) for i in range(receptor_atom_count)}, receptor_parameters,
        receptor_atom_count, ("atom_index",))
    return {
        "schema_id": REPORT_SCHEMA,
        "topology": demands,
        "receptor_atom_count": receptor_atom_count,
        "index_coverage": coverage,
        "coverage_basis": "supplied_atom_indices_and_graph_paths_not_parameter_assignment",
        "missing_indices_do_not_prove_missing_physics": True,
        "unverified_requirements": [
            "ligand_chemical_state_and_complete_hydrogens",
            "receptor_preparation_and_atom_mapping",
            "parameter_values_units_and_source_model",
            "proper_and_improper_conventions_and_full_source_term_coverage",
            "nonbonded_exclusions_scaling_and_listed_pairs",
            "cross_interaction_policy_and_coordinate_frame",
            "independent_start_provenance",
            "engine_input_and_runtime_admission",
        ],
        "parameterization_performed": False,
        "parameter_value_validation_performed": False,
        "engine_admission_performed": False,
        "energy_force_evaluations": 0,
        "scientifically_validated": False,
    }
