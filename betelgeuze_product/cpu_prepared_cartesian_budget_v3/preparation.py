"""Force-free admission for explicitly prepared research inputs.

Source hashes establish byte identity, not source authenticity or a reproduced
simulation Hamiltonian. No parameter inference or coordinate transform occurs.
"""

import torch
from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.physics.reference_forcefield import _torsion_angle, _vector
from betelgeuze_product.comparison_receipts import _json
from betelgeuze_product.cpu_refinement.reference_forcefield_v1_1 import _angle
from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import _require_fourier_topology
from betelgeuze_product.cpu_refinement_fourier_v1.workflow import _bound
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, exact_fields


def _require(condition, message):
    if not condition:
        raise ResearchError(message)


def _source_evidence(raw, evidence_kind):
    evidence = _json(raw)
    exact_fields(evidence, {
        "schema_version", "evidence_kind", "source_files", "source_authenticated",
        "original_simulation_hamiltonian_reproduced",
    })
    _require(
        evidence["schema_version"] == "declared_prepared_source_evidence/1.0.0"
        and evidence["evidence_kind"] == evidence_kind
        and evidence["source_authenticated"] is False
        and evidence["original_simulation_hamiltonian_reproduced"] is False,
        "source evidence boundary mismatch",
    )
    refs = evidence["source_files"]
    _require(type(refs) is list and len(refs) <= 32
             and (refs or evidence_kind == "synthetic_control"),
             "bounded original source references required")
    for ref in refs:
        _bound(ref)


def _geometry(ligand, parameters, config, model):
    """Force-free admission; graph and vector operations are preparation work."""
    graph = build_compact_radius_graph(ligand.coordinates, RadiusGraphConfig(
        cutoff_angstrom=parameters.cutoff_angstrom,
        max_neighbors=config.max_neighbors, max_atoms_per_cell=config.max_atoms_per_cell,
    ))
    _require_fourier_topology(ligand, graph, parameters)
    base = parameters.base_parameters if model == "linear_angle" else parameters
    xyz = ligand.coordinates
    for row in base.angles:
        _angle(_vector(xyz, ligand, row.atom_i, row.atom_j),
               _vector(xyz, ligand, row.atom_k, row.atom_j))
    linear = []
    if model == "linear_angle":
        for row in parameters.linear_angles:
            left = _vector(xyz, ligand, row.atom_i, row.atom_j)
            right = _vector(xyz, ligand, row.atom_k, row.atom_j)
            norms = [torch.linalg.vector_norm(v, dim=-1, keepdim=True) for v in (left, right)]
            _require(all(bool(torch.isfinite(n).all()) and bool((n > 1.e-12).all())
                         for n in norms), "linear angle contains an invalid vector norm")
            left, right = left / norms[0], right / norms[1]
            sine = torch.linalg.vector_norm(torch.linalg.cross(left, right, dim=-1), dim=-1)
            cosine = (left * right).sum(dim=-1)
            _require(not bool(((cosine >= 0) & (sine <= 8 * torch.finfo(sine.dtype).eps)).any()),
                     "linear-equilibrium angle has incompatible parallel vectors")
            linear.append({"atoms": [row.atom_i, row.atom_j, row.atom_k],
                           "equilibrium_radians": row.equilibrium_radians,
                           "initial_radians": float(torch.atan2(sine, cosine)[0])})
    for row in (*parameters.torsions, *parameters.periodic_impropers):
        _torsion_angle(xyz, ligand, row.atom_i, row.atom_j, row.atom_k, row.atom_l)
    return {
        "complete_bond_angle_proper_topology_coverage": True,
        "ordinary_angle_count": len(base.angles), "linear_angles": linear,
        "proper_term_count": len(parameters.torsions),
        "ordered_improper_term_count": len(parameters.periodic_impropers),
        "declared_angle_and_dihedral_geometry_admitted": True,
        "preparation_graph_calls": 1, "force_calls": 0, "energy_calls": 0,
        "nonbonded_distance_checks_deferred_to_journaled_objective": True,
    }


