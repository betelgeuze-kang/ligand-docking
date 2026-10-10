"""Pure, source-row-preserving geometry diagnostics for explicit prepared models.

These measurements do not evaluate energy, qualify chemistry, or change geometry.
All floating-point values are finite binary64 hex strings. Torsion signs and
absolute degeneracy tolerance match the owning reference evaluator; unavailable
measurements remain present rather than being dropped or assigned zero.
"""
from __future__ import annotations

import math

import torch

from betelgeuze_engine_v2.molecular import canonical_system_sha256, canonical_topology_sha256
from betelgeuze_engine_v2.physics.reference_forcefield import (
    ReferencePhysicsApplicabilityError, _torsion_angle,
)
from betelgeuze_product.cpu_refinement_fourier_v1.parameters import FourierParameters
from betelgeuze_product.cpu_refinement_linear_angle_v1.parameters import LinearAngleParameters
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import require_system
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, finite

GEOMETRY_SCHEMA = "cpu_refinement_diagnostic_geometry/1.0.0"


def _hex(value):
    return finite(value).hex()


def _source(row):
    return {key: _hex(value) if type(value) is float else value
            for key, value in row.to_dict().items()}


def _measurement(value=None, reason=None):
    return {"available": reason is None, "value_hex": None if reason else _hex(value),
            "unavailable_reason": reason}


def _norm(vector):
    result = torch.linalg.vector_norm(vector)
    if not bool(torch.isfinite(result)):
        raise ResearchError("nonfinite diagnostic geometry arithmetic")
    return float(result)


def _measure(system, indices, kind):
    xyz = system.coordinates.detach()[0]
    if kind == "bond":
        return _measurement(_norm(xyz[indices[0]] - xyz[indices[1]]))
    if kind == "angle":
        first, second = xyz[indices[0]] - xyz[indices[1]], xyz[indices[2]] - xyz[indices[1]]
        a, b = _norm(first), _norm(second)
        if min(a, b) <= 1.e-12:
            return _measurement(reason="zero_length_angle_vector")
        # atan2 preserves exact parallel/antiparallel endpoints without the
        # energy evaluator's interior acos clamp or any geometry adjustment.
        left, right = first/a, second/b
        return _measurement(math.atan2(_norm(torch.linalg.cross(left, right)),
                                       float((left*right).sum())))
    # The evaluator guards degeneracy but does not separately reject all
    # intermediate overflow. A diagnostic must not turn atan2(inf, inf) into
    # an apparently available finite measurement.
    b0 = xyz[indices[0]] - xyz[indices[1]]
    b1 = xyz[indices[2]] - xyz[indices[1]]
    b2 = xyz[indices[3]] - xyz[indices[2]]
    central_norm = _norm(b1)
    if central_norm <= 1.e-12:
        return _measurement(reason="degenerate_torsion_geometry")
    axis = b1 / central_norm
    v = b0 - (b0 * axis).sum() * axis
    w = b2 - (b2 * axis).sum() * axis
    if min(_norm(v), _norm(w)) <= 1.e-12:
        return _measurement(reason="degenerate_torsion_geometry")
    finite(float((v * w).sum()))
    finite(float((torch.linalg.cross(axis, v) * w).sum()))
    try:
        value = _torsion_angle(system.coordinates.detach(), system, *indices).item()
    except ReferencePhysicsApplicabilityError:
        return _measurement(reason="degenerate_torsion_geometry")
    return _measurement(value)


def _row(original, trial, source, index, collection, kind, equilibrium=None):
    names = ("atom_i", "atom_j", "atom_k", "atom_l")[:{"bond": 2, "angle": 3, "torsion": 4}[kind]]
    indices = [getattr(source, name) for name in names]
    if any(i < 0 or i >= original.atom_count for i in indices):
        raise ResearchError("diagnostic source row index outside system")
    parent_value = _measure(original, indices, kind)
    trial_value = _measure(trial, indices, kind)
    available = parent_value["available"] and trial_value["available"]
    change = None
    if available:
        delta = float.fromhex(trial_value["value_hex"]) - float.fromhex(parent_value["value_hex"])
        if kind == "torsion":
            delta = math.atan2(math.sin(delta), math.cos(delta))
        change = _hex(delta)
    result = {"source_collection": collection, "source_row_index": index,
              "atom_indices": indices, "source_parameter_row": _source(source),
              "parent": parent_value, "trial": trial_value,
              "change_from_parent_hex": change,
              "change_available": available,
              "change_unavailable_reason": None if available else "parent_or_trial_geometry_unavailable"}
    if equilibrium is not None:
        result["equilibrium_hex"] = _hex(equilibrium)
        for label, value in (("parent", parent_value), ("trial", trial_value)):
            result[f"{label}_deviation_from_equilibrium_hex"] = (
                _hex(float.fromhex(value["value_hex"])-equilibrium) if value["available"] else None)
    return result


def geometry_changes(original_system, trial_system, parameters):
    """Measure every declared source row in order, relative to the parent.

    Accept only explicit Fourier/linear-angle models bound to the identical
    topology. No force-field applicability, chemistry, torsion equilibrium, or
    planarity inference is made. Coordinates and parameter rows are read only.
    """
    if type(parameters) not in (FourierParameters, LinearAngleParameters):
        raise ResearchError("explicit Fourier or linear angle diagnostic parameters required")
    require_system(original_system, 256)
    require_system(trial_system, 256)
    topology = canonical_topology_sha256(original_system)
    if (canonical_topology_sha256(trial_system) != topology
            or parameters.topology_sha256 != topology
            or len(parameters.atom_parameters) != original_system.atom_count):
        raise ResearchError("diagnostic system and parameter topology mismatch")
    base = parameters.base_parameters if type(parameters) is LinearAngleParameters else parameters
    groups = (("bonds", base.bonds, "bond", "equilibrium_angstrom"),
              ("ordinary_angles", base.angles, "angle", "equilibrium_radians"),
              ("linear_angles", parameters.linear_angles if type(parameters) is LinearAngleParameters else (),
               "angle", "equilibrium_radians"),
              ("proper_torsions", base.torsions, "torsion", None),
              ("periodic_impropers", base.periodic_impropers, "torsion", None))
    source_names = {"ordinary_angles": "angles", "proper_torsions": "torsions"}
    result = {"schema_id": GEOMETRY_SCHEMA,
              "parent_system_sha256": canonical_system_sha256(original_system),
              "trial_system_sha256": canonical_system_sha256(trial_system),
              "topology_sha256": topology,
              "parameter_fingerprint_sha256": parameters.fingerprint_sha256,
              "length_unit": "angstrom", "angle_unit": "radian",
              "torsion_change_convention": "atan2(sin(trial-parent),cos(trial-parent))",
              "torsion_absolute_convention": "reference_forcefield_signed_ordered_dihedral",
              "degeneracy_tolerance_angstrom_hex": _hex(1.e-12)}
    for name, rows, kind, equilibrium_name in groups:
        result[name] = [_row(original_system, trial_system, row, index,
                             source_names.get(name, name), kind,
                             getattr(row, equilibrium_name) if equilibrium_name else None)
                        for index, row in enumerate(rows)]
    return result
