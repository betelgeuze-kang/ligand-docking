"""Strict, source-bound translation of a small unconstrained OpenMM System.

This is a fixed-coordinate potential/force conversion, not a general OpenMM
importer or a simulation equivalence claim. NoCutoff is admitted only with the
runtime guard in OpenMMPeriodicParameters: every intraligand distance must stay
strictly below the declared switch start at every evaluation. Source XML bytes
are never changed. An atom mapping must be established by the caller; System
XML itself has no chemical atom identifiers.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from xml.etree import ElementTree as ET

import torch

from betelgeuze_engine_v2.molecular import AllAtomSystem, canonical_topology_sha256
from betelgeuze_engine_v2.physics.reference_forcefield import _bonded_topology_paths
from betelgeuze_engine_v2.physics.reference_parameters import (
    AtomNonbondedParameter, HarmonicAngleParameter, HarmonicBondParameter,
    PairScalingParameter, PeriodicTorsionParameter, ReferenceApplicabilityDomain,
    ReferenceForceFieldParameters,
)
from betelgeuze_product.cpu_refinement_v1_2.openmm_periodic_extension import (
    OpenMMPeriodicParameters, PeriodicImproperParameter,
)


class OpenMMD3TranslationError(ValueError):
    """A typed refusal; the input has not been partially translated."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(code + (": " + detail if detail else ""))


@dataclass(frozen=True)
class TranslationSettings:
    parameter_set_id: str
    cutoff_angstrom: float
    switch_start_angstrom: float
    minimum_pair_distance_angstrom: float = 0.35

    def __post_init__(self):
        if type(self.parameter_set_id) is not str or not self.parameter_set_id.strip():
            raise OpenMMD3TranslationError("explicit_parameter_set_id_required")
        numbers = (self.minimum_pair_distance_angstrom, self.switch_start_angstrom,
                   self.cutoff_angstrom)
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in numbers):
            raise OpenMMD3TranslationError("invalid_translation_distance_settings")
        if not 0 < numbers[0] < numbers[1] < numbers[2] <= 1000:
            raise OpenMMD3TranslationError("invalid_translation_distance_settings")


@dataclass(frozen=True)
class OpenMMD3Conversion:
    base_parameters: ReferenceForceFieldParameters
    parameters: OpenMMPeriodicParameters
    inventory: dict


def _fail(code, detail=""):
    raise OpenMMD3TranslationError(code, detail)


def _attrs(node, names):
    if set(node.attrib) != set(names):
        _fail("unsupported_xml_attributes", node.tag + ": " + str(sorted(node.attrib)))


def _children(node, names):
    children = list(node)
    if len(children) != len(names) or {x.tag for x in children} != set(names):
        _fail("unsupported_xml_children", node.tag)
    return {x.tag: x for x in children}


def _number(node, key):
    try:
        value = float(node.attrib[key])
    except (ValueError, KeyError, OverflowError):
        _fail("invalid_xml_number", key)
    if not math.isfinite(value):
        _fail("nonfinite_xml_number", key)
    return value


def _integer(node, key):
    try:
        value = int(node.attrib[key])
    except (ValueError, KeyError, OverflowError):
        _fail("invalid_xml_integer", key)
    if str(value) != node.attrib[key]:
        _fail("noncanonical_xml_integer", key)
    return value


def _indices(node, count, atom_count):
    result = tuple(_integer(node, "p" + str(i)) for i in range(1, count + 1))
    if len(set(result)) != count or any(i < 0 or i >= atom_count for i in result):
        _fail("invalid_force_atom_indices")
    return result


def _rows(container, tag, attrs):
    if container.attrib:
        _fail("unsupported_xml_attributes", container.tag)
    for row in container:
        if row.tag != tag or len(row):
            _fail("unsupported_xml_record", container.tag)
        _attrs(row, attrs)
        yield row


def _force_table(force, container, record, attrs):
    _attrs(force, {"forceGroup", "name", "type", "usesPeriodic", "version"})
    if force.attrib["usesPeriodic"] != "0":
        _fail("periodic_bonded_force_unsupported")
    if force.attrib["version"] != "2":
        _fail("unsupported_force_serialization_version")
    return list(_rows(_children(force, {container})[container], record, attrs))


def _convert_openmm_system(
    xml_bytes: bytes, ligand: AllAtomSystem, settings: TranslationSettings,
) -> OpenMMD3Conversion:
    """Translate every supported source term or reject the entire conversion.

    Units: nm -> A; kJ/mol -> kcal/mol; bond k -> k/418.4. Zero
    torsion amplitudes are retained for graph-path coverage. Negative proper
    amplitudes use a pi phase shift AND the exact constant offset 2*k.
    """
    if type(xml_bytes) is not bytes or not 0 < len(xml_bytes) <= 16 * 1024 * 1024:
        _fail("bounded_xml_bytes_required")
    # OpenMM's supported serializer produces ASCII. Reject encodings that can
    # hide DTD markers behind interleaved NULs before ElementTree sees them.
    try:
        xml_bytes.decode("ascii")
    except UnicodeDecodeError:
        _fail("only_ascii_openmm_serialization_supported")
    if b"\x00" in xml_bytes:
        _fail("only_ascii_openmm_serialization_supported")
    if b"<!DOCTYPE" in xml_bytes.upper() or b"<!ENTITY" in xml_bytes.upper():
        _fail("xml_dtd_or_entities_unsupported")
    if type(settings) is not TranslationSettings:
        _fail("explicit_translation_settings_required")
    if (not isinstance(ligand, AllAtomSystem) or ligand.model_count != 1
            or not 1 <= ligand.atom_count <= 256 or ligand.cell is not None
            or ligand.coordinate_unit != "angstrom" or ligand.coordinates.dtype != torch.float64
            or ligand.coordinates.device.type != "cpu"
            or [a.index for a in ligand.atoms] != list(range(ligand.atom_count))
            or not bool(torch.isfinite(ligand.coordinates).all())):
        _fail("bounded_nonperiodic_binary64_ligand_required")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        _fail("invalid_system_xml", str(exc))
    _attrs(root, {"type", "version", "openmmVersion"})
    if root.tag != "System" or root.attrib["type"] != "System" or root.attrib["version"] != "1":
        _fail("unsupported_system_serialization")
    top = _children(root, {"PeriodicBoxVectors", "Particles", "Constraints", "Forces"})
    if top["PeriodicBoxVectors"].attrib:
        _fail("unsupported_xml_attributes", "PeriodicBoxVectors")
    box = _children(top["PeriodicBoxVectors"], {"A", "B", "C"})
    for row in box.values():
        _attrs(row, {"x", "y", "z"})
        if len(row):
            _fail("unsupported_box_record")
        for axis in ("x", "y", "z"):
            _number(row, axis)
    particles = list(_rows(top["Particles"], "Particle", {"mass"}))
    if len(particles) != ligand.atom_count:
        _fail("particle_count_mismatch")
    for source, atom in zip(particles, ligand.atoms, strict=True):
        mass = _number(source, "mass")
        if mass <= 0:
            _fail("zero_or_negative_mass_particle_unsupported")
        if atom.mass_da is None or not math.isclose(mass, atom.mass_da, rel_tol=1e-10, abs_tol=1e-10):
            _fail("source_particle_mass_order_mismatch", str(atom.index))
    constraints = list(_rows(top["Constraints"], "Constraint", {"d", "p1", "p2"}))
    for row in constraints:
        _indices(row, 2, ligand.atom_count)
        if _number(row, "d") <= 0:
            _fail("invalid_source_constraint_distance")
    if top["Forces"].attrib:
        _fail("unsupported_xml_attributes", "Forces")
    forces = {}
    supported = {"HarmonicBondForce", "HarmonicAngleForce", "PeriodicTorsionForce", "NonbondedForce", "CMMotionRemover"}
    for force in top["Forces"]:
        kind = force.attrib.get("type")
        if force.tag != "Force" or kind not in supported:
            _fail("unsupported_force_class", str(kind))
        if kind in forces:
            _fail("duplicate_force_class", kind)
        if not 0 <= _integer(force, "forceGroup") <= 31:
            _fail("invalid_force_group")
        forces[kind] = force
    if not supported - {"CMMotionRemover"} <= set(forces):
        _fail("required_force_classes_missing")
    if "CMMotionRemover" in forces:
        cm = forces["CMMotionRemover"]
        _attrs(cm, {"forceGroup", "name", "type", "frequency", "version"})
        if cm.attrib["version"] != "1" or _integer(cm, "frequency") <= 0 or len(cm):
            _fail("unsupported_center_of_mass_remover")

    source_bonds = _force_table(forces["HarmonicBondForce"], "Bonds", "Bond", {"d", "k", "p1", "p2"})
    source_angles = _force_table(forces["HarmonicAngleForce"], "Angles", "Angle", {"a", "k", "p1", "p2", "p3"})
    source_torsions = _force_table(forces["PeriodicTorsionForce"], "Torsions", "Torsion", {"k", "p1", "p2", "p3", "p4", "periodicity", "phase"})
    graph = {tuple(sorted((b.atom_i, b.atom_j))) for b in ligand.bonds}
    energetic_bonds = {tuple(sorted(_indices(b, 2, ligand.atom_count))) for b in source_bonds}
    if constraints and energetic_bonds != graph:
        _fail("constrained_bond_terms_missing")
    if constraints:
        _fail("constrained_system_unsupported")
    if energetic_bonds != graph or len(energetic_bonds) != len(source_bonds):
        _fail("harmonic_bond_coverage_mismatch")
    bonds = tuple(HarmonicBondParameter(*_indices(row, 2, ligand.atom_count),
        _number(row, "d") * 10, _number(row, "k") / 418.4) for row in source_bonds)
    angles = tuple(HarmonicAngleParameter(*_indices(row, 3, ligand.atom_count),
        _number(row, "a"), _number(row, "k") / 4.184) for row in source_angles)
    expected_angles, expected_propers = _bonded_topology_paths(ligand.atom_count, sorted(graph))
    angle_paths = {(min(a.atom_i, a.atom_k), a.atom_j, max(a.atom_i, a.atom_k)) for a in angles}
    if angle_paths != expected_angles or len(angle_paths) != len(angles):
        _fail("harmonic_angle_coverage_mismatch")

    proper, improper, offsets, negative_proper_count = [], [], [], 0
    for row in source_torsions:
        indices = _indices(row, 4, ligand.atom_count)
        phase, amplitude = _number(row, "phase"), _number(row, "k") / 4.184
        periodicity = _integer(row, "periodicity")
        if not 1 <= periodicity <= 12:
            _fail("torsion_periodicity_unsupported")
        path = min(indices, tuple(reversed(indices)))
        if path in expected_propers:
            if amplitude < 0:
                offsets.append(2 * amplitude)
                phase += math.pi
                amplitude = -amplitude
                negative_proper_count += 1
            proper.append(PeriodicTorsionParameter(*indices, periodicity, phase, amplitude))
        else:
            centers = [center for center in indices if all(
                tuple(sorted((center, other))) in graph for other in indices if center != other)]
            if len(centers) != 1:
                _fail("torsion_neither_supported_proper_nor_unique_star")
            improper.append(PeriodicImproperParameter(*indices, centers[0], periodicity, phase, amplitude))
    actual_propers = {min((t.atom_i, t.atom_j, t.atom_k, t.atom_l),
        (t.atom_l, t.atom_k, t.atom_j, t.atom_i)) for t in proper}
    if actual_propers != expected_propers:
        _fail("periodic_proper_coverage_mismatch")

    nb = forces["NonbondedForce"]
    _attrs(nb, {"alpha", "cutoff", "dispersionCorrection", "ewaldTolerance", "exceptionsUsePeriodic",
        "forceGroup", "includeDirectSpace", "ljAlpha", "ljnx", "ljny", "ljnz", "method", "name",
        "nx", "ny", "nz", "recipForceGroup", "rfDielectric", "switchingDistance", "type", "useSwitchingFunction", "version"})
    if nb.attrib["version"] != "4":
        _fail("unsupported_nonbonded_serialization_version")
    if _integer(nb, "method") != 0 or nb.attrib["exceptionsUsePeriodic"] != "0":
        _fail("only_nonperiodic_nocutoff_source_supported")
    if nb.attrib["includeDirectSpace"] != "1":
        _fail("nonbonded_direct_space_required")
    for key in ("alpha", "ljAlpha", "nx", "ny", "nz", "ljnx", "ljny", "ljnz"):
        if _number(nb, key) != 0:
            _fail("inactive_ewald_settings_must_be_default", key)
    for key in ("cutoff", "ewaldTolerance", "rfDielectric"):
        if _number(nb, key) <= 0:
            _fail("invalid_source_nonbonded_setting", key)
    _number(nb, "switchingDistance")
    if any(nb.attrib[key] not in ("0", "1") for key in ("dispersionCorrection", "useSwitchingFunction")):
        _fail("invalid_source_nonbonded_flag")
    if not -1 <= _integer(nb, "recipForceGroup") <= 31:
        _fail("invalid_reciprocal_force_group")
    nb_children = _children(nb, {"GlobalParameters", "ParticleOffsets", "ExceptionOffsets", "Particles", "Exceptions"})
    for key in ("GlobalParameters", "ParticleOffsets", "ExceptionOffsets"):
        if len(nb_children[key]) or nb_children[key].attrib:
            _fail("nonbonded_offsets_or_global_parameters_unsupported", key)
    nb_atoms = list(_rows(nb_children["Particles"], "Particle", {"eps", "q", "sig"}))
    if len(nb_atoms) != ligand.atom_count:
        _fail("nonbonded_particle_count_mismatch")
    atoms = []
    for index, (row, atom) in enumerate(zip(nb_atoms, ligand.atoms, strict=True)):
        q = _number(row, "q")
        if atom.partial_charge_e is None or not math.isclose(q, atom.partial_charge_e, rel_tol=1e-12, abs_tol=1e-12):
            _fail("source_particle_charge_order_mismatch", str(index))
        atoms.append(AtomNonbondedParameter(index, _number(row, "sig") * 10, _number(row, "eps") / 4.184, q))
    excluded, scaled, seen = [], [], set()
    exceptions = list(_rows(nb_children["Exceptions"], "Exception", {"eps", "p1", "p2", "q", "sig"}))
    for row in exceptions:
        i, j = sorted(_indices(row, 2, ligand.atom_count))
        if (i, j) in seen:
            _fail("duplicate_nonbonded_exception")
        seen.add((i, j))
        q, epsilon, sigma = _number(row, "q"), _number(row, "eps") / 4.184, _number(row, "sig") * 10
        if epsilon < 0 or sigma <= 0:
            _fail("unsupported_exception_parameters")
        if q == 0 and epsilon == 0:
            excluded.append((i, j))
            continue
        a, b = atoms[i], atoms[j]
        mixed_sigma = (a.sigma_angstrom + b.sigma_angstrom) / 2
        mixed_epsilon = math.sqrt(a.epsilon_kcal_per_mol * b.epsilon_kcal_per_mol)
        mixed_q = a.charge_e * b.charge_e
        if epsilon and not math.isclose(sigma, mixed_sigma, rel_tol=1e-12, abs_tol=1e-12):
            _fail("non_lorentz_berthelot_exception_sigma")
        if (mixed_epsilon == 0 and epsilon != 0) or (mixed_q == 0 and q != 0):
            _fail("non_scalable_exception")
        lj_scale = epsilon / mixed_epsilon if mixed_epsilon else 0.
        q_scale = q / mixed_q if mixed_q else 0.
        if not (0 <= lj_scale <= 1 and 0 <= q_scale <= 1):
            _fail("exception_scaling_outside_supported_interval")
        scaled.append(PairScalingParameter(i, j, lj_scale, q_scale))
    max_distance = float(torch.pdist(ligand.coordinates[0]).max()) if ligand.atom_count > 1 else 0.
    if max_distance >= settings.switch_start_angstrom:
        _fail("nocutoff_equivalence_domain_exceeded")
    source_sha = hashlib.sha256(xml_bytes).hexdigest()
    inventory = {
        "schema_id": "openmm_d3_translation_inventory/1.0.0",
        "source_xml_sha256": source_sha, "source_openmm_version": root.attrib["openmmVersion"],
        "source_force_attributes": {name: dict(force.attrib) for name, force in sorted(forces.items())},
        "particle_count": ligand.atom_count, "harmonic_bond_count": len(bonds),
        "harmonic_angle_count": len(angles), "source_periodic_torsion_count": len(source_torsions),
        "proper_periodic_torsion_count": len(proper), "periodic_improper_count": len(improper),
        "negative_proper_count": negative_proper_count,
        "constant_energy_offset_kcal_per_mol": math.fsum(offsets),
        "source_constraint_count": len(constraints), "source_exception_count": len(exceptions),
        "excluded_pair_count": len(excluded), "scaled_pair_count": len(scaled),
        "source_units": "nm,kJ/mol,elementary_charge,radians",
        "destination_units": "angstrom,kcal/mol,elementary_charge,radians",
        "length_multiplier": 10., "energy_divisor": 4.184, "bond_constant_divisor": 418.4,
        "source_nonbonded_model": "NoCutoff",
        "runtime_nonbonded_domain": "all_ligand_pair_distances_strictly_below_switch_start_at_every_evaluation",
        "initial_maximum_pair_distance_angstrom": max_distance,
        "switch_start_angstrom": settings.switch_start_angstrom,
        "cutoff_angstrom": settings.cutoff_angstrom,
        "inactive_source_settings": ["periodic_box", "nonbonded_cutoff", "lj_switch", "reaction_field_dielectric", "dispersion_correction"],
        "cmmotion_remover_scope": "zero_potential_and_force_at_fixed_coordinates_no_dynamics_equivalence",
        "atom_order_evidence": "caller_bound_mapping_required_xml_mass_and_charge_order_cross_checked",
        "scientifically_validated": False, "product_qualified": False,
    }
    try:
        base = ReferenceForceFieldParameters(
            parameter_set_id=settings.parameter_set_id, parameter_set_version="openmm-d3-1.0.0",
            topology_sha256=canonical_topology_sha256(ligand), atom_parameters=tuple(atoms),
            bonds=bonds, angles=angles, torsions=tuple(proper), excluded_pairs=tuple(excluded), scaled_pairs=tuple(scaled),
            cutoff_angstrom=settings.cutoff_angstrom, switch_start_angstrom=settings.switch_start_angstrom,
            dielectric=1., screening_kappa_per_angstrom=0.,
            applicability_domain=ReferenceApplicabilityDomain(max_atoms=256,
                minimum_pair_distance_angstrom=settings.minimum_pair_distance_angstrom),
            metadata={"openmm_translation": inventory},
        )
        parameters = OpenMMPeriodicParameters(base,
            periodic_impropers=tuple(improper), constant_energy_offset_kcal_per_mol=math.fsum(offsets),
            metadata={"source_xml_sha256": source_sha, "openmm_xml_sha256": source_sha,
                      "translation_inventory": inventory})
    except ValueError as exc:
        _fail("unsupported_destination_parameter_contract", str(exc))
    return OpenMMD3Conversion(base, parameters, inventory)


def convert_openmm_system(
    xml_bytes: bytes, ligand: AllAtomSystem, settings: TranslationSettings,
) -> OpenMMD3Conversion:
    """Return a complete conversion or a typed refusal, never partial output."""
    try:
        return _convert_openmm_system(xml_bytes, ligand, settings)
    except OpenMMD3TranslationError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise OpenMMD3TranslationError("unsupported_destination_parameter_contract", str(exc)) from exc
