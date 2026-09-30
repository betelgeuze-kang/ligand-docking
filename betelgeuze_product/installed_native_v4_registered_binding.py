"""Source-bound identity of one registered canonical D3 pose, without scoring.

Charge provenance records the original OpenMM XML decimal tokens and a complete
index-preserving ligand atom map. This checks representation and source binding;
it never establishes that the prepared charge state was the assayed state.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, Inexact, localcontext
from pathlib import Path
import hashlib
import re
import xml.etree.ElementTree as ET

from rdkit import Chem

from . import native_v4_chemical_identity as chemical
from . import public_assay_components as components

SCHEMA = "native_v4_candidate_registered_structural_binding_v1"
REQUEST_SCHEMA = "cpu_registered_pose_fixed_receptor_request/1.0.0"
COHORT_SCHEMA = "native_v4_registered_prepared_cohort_v1"
CHARGE_ORIGIN_SCHEMA = "native_v4_registered_openmm_charge_origin_v1"
CHARGE_POLICY = "openmm_xml_decimal_charge_sum_v1"
SOURCE_FIELD = "prepared_state_origin"
SOURCE_FILES = {"receptor", "ligand", "parameters", "extensions", "cross_parameters"}
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_DECIMAL = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z")
_COHORT = {
    "schema_version", "target_chembl_id", "receptor_source_sha256",
    "receptor_system_sha256", "receptor_coordinates_sha256", "receptor_construct_sha256",
    "receptor_cross_parameters_sha256", "cross_model_sha256", "pocket_sha256",
    "coordinate_frame_id", "protocol_settings_sha256",
}


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _sha(value):
    return components.digest(components.canonical(value))


def _fields(value, names, reason="registered_binding_exact_metadata_fields_required"):
    _require(type(value) is dict and set(value) == set(names), reason)


def _digest(value):
    _require(type(value) is str and _HEX.fullmatch(value) is not None,
             "registered_binding_sha256_required")


def _text(value):
    _require(type(value) is str and bool(value.strip()) and len(value) <= 2048,
             "registered_binding_bounded_text_required")


def _ref(ref):
    _fields(ref, {"path", "sha256"})
    _text(ref["path"])
    _require(Path(ref["path"]).is_absolute(), "registered_binding_absolute_path_required")
    _digest(ref["sha256"])


def _raw(ref):
    from .reference_minimization_workflow import _read

    _ref(ref)
    path = Path(ref["path"])
    _require(str(path.resolve()) == ref["path"], "registered_binding_canonical_path_required")
    raw = _read(path)
    _require(hashlib.sha256(raw).hexdigest() == ref["sha256"], "registered_binding_source_sha256_mismatch")
    return raw


def _json(ref):
    return components.loads(_raw(ref))


def validate_descriptor(descriptor):
    """Validate only strict metadata shape; never open source or outcome files."""
    _fields(descriptor, {
        "schema_version", "record_id", "assay_id", "metadata_origin_sha256",
        "method_origin_sha256", "target_annotation_sha256", "target_chembl_id",
        "request_schema", "request_sha256", "source_files", "ligand", "receptor",
        "coordinate_frame_id", "pocket_sha256", "charge_origin", "charge_policy", "cohort",
        "same_prepared_assay_state_verified", "source_authenticated", "scientifically_validated",
    })
    _require(descriptor["schema_version"] == SCHEMA
             and descriptor["request_schema"] == REQUEST_SCHEMA
             and descriptor["charge_policy"] == CHARGE_POLICY,
             "registered_binding_schema_or_charge_policy_mismatch")
    for key in ("same_prepared_assay_state_verified", "source_authenticated", "scientifically_validated"):
        _require(descriptor[key] is False, "registered_binding_unsupported_evidence_promotion")
    for key in ("record_id", "assay_id", "target_chembl_id", "coordinate_frame_id"):
        _text(descriptor[key])
    for key in ("metadata_origin_sha256", "method_origin_sha256", "target_annotation_sha256",
                "request_sha256", "pocket_sha256"):
        _digest(descriptor[key])
    _fields(descriptor["source_files"], SOURCE_FILES)
    for value in descriptor["source_files"].values():
        _ref(value)
    _ref(descriptor["charge_origin"])
    ligand, receptor = descriptor["ligand"], descriptor["receptor"]
    _fields(ligand, {"system_sha256", "coordinates_sha256", "atom_graph_sha256",
                     "canonical_isomeric_smiles_sha256", "formal_charge", "atom_count"})
    _fields(receptor, {"system_sha256", "coordinates_sha256", "construct_sha256", "atom_count"})
    for part, maximum in ((ligand, 256), (receptor, 8192)):
        for key, value in part.items():
            if key.endswith("sha256"):
                _digest(value)
        _require(type(part["atom_count"]) is int and 1 <= part["atom_count"] <= maximum,
                 "registered_binding_atom_count_invalid")
    _require(type(ligand["formal_charge"]) is int and abs(ligand["formal_charge"]) <= 1024,
             "registered_binding_formal_charge_invalid")
    cohort = descriptor["cohort"]
    _fields(cohort, _COHORT)
    _require(cohort["schema_version"] == COHORT_SCHEMA, "registered_binding_cohort_schema_mismatch")
    for key, value in cohort.items():
        if key.endswith("sha256"):
            _digest(value)
    expected = {
        "target_chembl_id": descriptor["target_chembl_id"],
        "coordinate_frame_id": descriptor["coordinate_frame_id"],
        "pocket_sha256": descriptor["pocket_sha256"],
        "receptor_source_sha256": descriptor["source_files"]["receptor"]["sha256"],
        **{"receptor_" + key: receptor[key] for key in
           ("system_sha256", "coordinates_sha256", "construct_sha256")},
    }
    _require(all(cohort[key] == value for key, value in expected.items()),
             "registered_binding_cohort_descriptor_mismatch")


def _construct(receptor):
    return [{"chain_id": chain.chain_id, "residues": [
        {"name": receptor.residues[i].name, "sequence_number": receptor.residues[i].sequence_number,
         "insertion_code": receptor.residues[i].insertion_code}
        for i in chain.residue_indices]} for chain in receptor.chains]


def _check_aromatic_representations(ligand):
    """Require each connected aromatic edge set to use one complete encoding."""
    neighbors = {}
    for bond in ligand.bonds:
        if not bond.aromatic:
            _require(bond.order != 1.5, "registered_ligand_changed_bond_graph")
            continue
        _require(bond.order in {1., 1.5, 2.}
                 and ligand.atoms[bond.atom_i].aromatic and ligand.atoms[bond.atom_j].aromatic,
                 "registered_ligand_unsupported_bond_graph")
        for left, right in ((bond.atom_i, bond.atom_j), (bond.atom_j, bond.atom_i)):
            neighbors.setdefault(left, []).append((right, bond.order == 1.5))
    remaining = set(neighbors)
    while remaining:
        pending, encodings = [remaining.pop()], set()
        while pending:
            for neighbor, fractional in neighbors[pending.pop()]:
                encodings.add(fractional)
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    pending.append(neighbor)
        _require(len(encodings) == 1, "registered_ligand_mixed_aromatic_representation")


def _ordinary_sulfonyl_potential_stereo(molecule, info):
    """Recognize only RDKit's untagged potential square-planar sulfonyl S.

    Identical ligands do not generally remove square-planar stereochemistry.
    This exception is confined to neutral S(VI) with two equivalent terminal
    oxo atoms and two single bonds; it never changes the recorded identity.
    """
    if (str(info.type) != "Atom_SquarePlanar" or str(info.specified) != "Unspecified"
            or str(info.descriptor) != "NoValue"):
        return False
    atom = molecule.GetAtomWithIdx(info.centeredOn)
    if (atom.GetAtomicNum() != 16 or atom.GetFormalCharge() != 0
            or atom.GetNumRadicalElectrons() != 0 or atom.GetIsAromatic()
            or atom.GetDegree() != 4 or atom.GetTotalValence() != 6
            or atom.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED
            or atom.HasProp("_chiralPermutation") or atom.HasProp("_UnknownStereo")):
        return False
    bonds = list(atom.GetBonds())
    if (any(bond.GetIsAromatic() for bond in bonds)
            or sorted(bond.GetBondTypeAsDouble() for bond in bonds) != [1., 1., 2., 2.]):
        return False
    oxygens = [bond.GetOtherAtom(atom) for bond in bonds
               if bond.GetBondType() == Chem.BondType.DOUBLE]
    return (len(oxygens) == 2 and oxygens[0].GetIsotope() == oxygens[1].GetIsotope()
            and all(oxygen.GetAtomicNum() == 8 and oxygen.GetFormalCharge() == 0
                    and oxygen.GetNumRadicalElectrons() == 0 and not oxygen.GetIsAromatic()
                    and oxygen.GetDegree() == 1 and oxygen.GetTotalNumHs(includeNeighbors=True) == 0
                    and oxygen.GetChiralTag() == Chem.ChiralType.CHI_UNSPECIFIED
                    and not oxygen.HasProp("_UnknownStereo")
                    for oxygen in oxygens))


def _supported_stereo(molecule, potential):
    """Use the same supported stereo policy for source and coordinate graphs."""
    if any(atom.GetChiralTag() not in {
            Chem.ChiralType.CHI_UNSPECIFIED, Chem.ChiralType.CHI_TETRAHEDRAL_CW,
            Chem.ChiralType.CHI_TETRAHEDRAL_CCW} for atom in molecule.GetAtoms()):
        return False
    return all(_ordinary_sulfonyl_potential_stereo(molecule, info)
               or (str(info.type) in {"Atom_Tetrahedral", "Bond_Double"}
                   and str(info.specified) == "Specified")
               for info in potential)


def _ligand_identity(ligand, identity):
    """Rebuild the explicit graph and derive R/S and E/Z from actual coordinates."""
    from betelgeuze_engine_v2.molecular.serialization import (
        canonical_coordinates_sha256, canonical_system_sha256,
    )

    _require(type(identity) is dict and not identity.get("unresolved_stereochemistry"),
             "registered_ligand_chemical_identity_unresolved")
    source_smiles = identity.get("canonical_isomeric_smiles")
    source = Chem.MolFromSmiles(source_smiles) if type(source_smiles) is str else None
    _require(source is not None, "registered_ligand_chemical_identity_unresolved")
    potential = list(Chem.FindPotentialStereo(source))
    _require(type(identity.get("stereo_unspecified_count")) is int
             and identity["stereo_unspecified_count"] == sum(
                 str(info.specified) == "Unspecified" for info in potential)
             and _supported_stereo(source, potential),
             "registered_ligand_chemical_identity_unresolved")
    _check_aromatic_representations(ligand)
    molecule = Chem.RWMol()
    atom_rows, bond_rows = [], []
    for atom in ligand.atoms:
        _require(atom.stereo in {"unspecified", "none", "R", "S"},
                 "registered_ligand_unsupported_atom_stereo")
        rd_atom = Chem.Atom(atom.atomic_number)
        _require(rd_atom.GetSymbol() == atom.element, "registered_ligand_element_identity_mismatch")
        rd_atom.SetFormalCharge(atom.formal_charge)
        rd_atom.SetIsotope(atom.isotope_mass_number or 0)
        # Perceive aromaticity from the encoded bonds. Trusting aromatic flags
        # here can let sanitization repair an invalid integer Kekule assignment.
        rd_atom.SetNoImplicit(True)
        molecule.AddAtom(rd_atom)
        atom_rows.append({"atomic_number": atom.atomic_number, "isotope": atom.isotope_mass_number or 0,
                          "formal_charge": atom.formal_charge, "aromatic": atom.aromatic,
                          "stereo": atom.stereo})
    bond_types = {1.: Chem.BondType.SINGLE, 1.5: Chem.BondType.AROMATIC,
                  2.: Chem.BondType.DOUBLE, 3.: Chem.BondType.TRIPLE}
    for bond in ligand.bonds:
        _require(bond.order in bond_types and bond.stereo in {"none", "NONE", "unspecified", "E", "Z"},
                 "registered_ligand_unsupported_bond_graph")
        molecule.AddBond(bond.atom_i, bond.atom_j, bond_types[bond.order])
        bond_rows.append({"atom_i": bond.atom_i, "atom_j": bond.atom_j,
                          "order": bond.order, "aromatic": bond.aromatic, "stereo": bond.stereo})
    molecule = molecule.GetMol()
    try:
        Chem.SanitizeMol(molecule)
    except Exception as exc:
        raise ValueError("registered_ligand_atom_graph_invalid") from exc
    _require(all(a.GetNumRadicalElectrons() == 0 and a.GetNumImplicitHs() == 0
                 and a.GetNumExplicitHs() == 0
                 and a.GetAtomicNum() == declared.atomic_number
                 and a.GetFormalCharge() == declared.formal_charge
                 and a.GetIsotope() == (declared.isotope_mass_number or 0)
                 and a.GetIsAromatic() == declared.aromatic
                 for a, declared in zip(molecule.GetAtoms(), ligand.atoms)),
             "registered_ligand_incomplete_or_changed_explicit_graph")
    _require(all(molecule.GetBondBetweenAtoms(b.atom_i, b.atom_j).GetBondTypeAsDouble()
                 == (1.5 if b.aromatic else b.order)
                 and molecule.GetBondBetweenAtoms(b.atom_i, b.atom_j).GetIsAromatic() == b.aromatic
                 for b in ligand.bonds), "registered_ligand_changed_bond_graph")
    conformer = Chem.Conformer(ligand.atom_count)
    conformer.Set3D(True)
    for i, xyz in enumerate(ligand.coordinates[0].tolist()):
        conformer.SetAtomPosition(i, xyz)
    molecule.AddConformer(conformer, assignId=True)
    Chem.RemoveStereochemistry(molecule)
    Chem.AssignStereochemistryFrom3D(molecule, replaceExistingTags=True)
    Chem.AssignStereochemistry(molecule, cleanIt=True, force=True)
    for atom, declared in zip(molecule.GetAtoms(), ligand.atoms):
        observed = atom.GetProp("_CIPCode") if atom.HasProp("_CIPCode") else None
        _require((observed is None and declared.stereo in {"none", "unspecified"})
                 or observed == declared.stereo, "registered_ligand_geometry_stereochemistry_mismatch")
    for bond in ligand.bonds:
        observed = str(molecule.GetBondBetweenAtoms(bond.atom_i, bond.atom_j).GetStereo())
        observed = {"STEREOE": "E", "STEREOZ": "Z", "STEREOTRANS": "E", "STEREOCIS": "Z"}.get(observed)
        _require((observed is None and bond.stereo in {"none", "NONE", "unspecified"})
                 or observed == bond.stereo, "registered_ligand_geometry_stereochemistry_mismatch")
    normalized = Chem.RemoveHs(molecule, sanitize=True)
    _require(_supported_stereo(normalized, list(Chem.FindPotentialStereo(normalized))),
             "registered_ligand_geometry_stereochemistry_unresolved")
    smiles = Chem.MolToSmiles(normalized, canonical=True, isomericSmiles=True)
    _require(chemical.chemical_identity(smiles) == identity,
             "registered_ligand_chemical_identity_mismatch")
    return {"system_sha256": canonical_system_sha256(ligand),
            "coordinates_sha256": canonical_coordinates_sha256(ligand),
            "atom_graph_sha256": _sha({"atoms": atom_rows, "bonds": bond_rows}),
            "canonical_isomeric_smiles_sha256": chemical.digest(smiles),
            "formal_charge": Chem.GetFormalCharge(normalized), "atom_count": ligand.atom_count}


def _charge_screen(origin_ref, request, ligand, base):
    from betelgeuze_engine_v2.molecular.serialization import canonical_system_sha256

    provenance = _json(origin_ref)
    _fields(provenance, {"schema_version", "openmm_system", "ligand_source_sha256",
                         "ligand_system_sha256", "atom_mapping"})
    _require(provenance["schema_version"] == CHARGE_ORIGIN_SCHEMA
             and provenance["ligand_source_sha256"] == request["ligand"]["sha256"]
             and provenance["ligand_system_sha256"] == canonical_system_sha256(ligand),
             "registered_charge_origin_ligand_binding_mismatch")
    mapping = provenance["atom_mapping"]
    _require(type(mapping) is list and len(mapping) == ligand.atom_count,
             "registered_charge_complete_atom_mapping_required")
    for i, (entry, atom) in enumerate(zip(mapping, ligand.atoms)):
        expected = {"particle_index": i, "ligand_atom_index": i, "atom_name": atom.name,
                    "element": atom.element, "atomic_number": atom.atomic_number,
                    "isotope_mass_number": atom.isotope_mass_number, "formal_charge": atom.formal_charge}
        _fields(entry, expected)
        _require(components.canonical(entry) == components.canonical(expected),
                 "registered_charge_atom_mapping_mismatch")
    xml_ref = provenance["openmm_system"]
    raw = _raw(xml_ref)
    # Restrict the original representation to literal UTF-8 XML decimals.
    # Entity expansion and alternate byte encodings cannot manufacture q tokens.
    _require(b"<!" not in raw and b"&" not in raw and b"\x00" not in raw,
             "registered_charge_xml_declarations_unsupported")
    try:
        root = ET.fromstring(raw.decode("utf-8"))
    except (ET.ParseError, UnicodeDecodeError) as exc:
        raise ValueError("registered_charge_invalid_xml") from exc
    _require(root.tag == "System" and not any("}" in item.tag for item in root.iter()),
             "registered_charge_xml_system_required")
    systems = root.findall("Particles")
    forces = root.findall("Forces")
    _require(len(systems) == len(forces) == 1
             and len(systems[0]) == ligand.atom_count
             and all(item.tag == "Particle" for item in systems[0])
             and not any(len(item) for item in root.findall("VirtualSites")),
             "registered_charge_xml_particle_layout_unsupported")
    nonbonded = [force for force in forces[0] if force.tag == "Force" and force.get("type") == "NonbondedForce"]
    _require(len(nonbonded) == 1, "registered_charge_unique_nonbonded_force_required")
    force = nonbonded[0]
    _require(all(item.tag in {"Particles", "Exceptions", "GlobalParameters", "ParticleOffsets", "ExceptionOffsets"}
                 for item in force)
             and not any(len(item) for item in force if item.tag in {"GlobalParameters", "ParticleOffsets", "ExceptionOffsets"}),
             "registered_charge_xml_offsets_unsupported")
    particle_sections = force.findall("Particles")
    _require(len(particle_sections) == 1 and len(particle_sections[0]) == ligand.atom_count,
             "registered_charge_xml_complete_particles_required")
    tokens = []
    parameters = sorted(base.atom_parameters, key=lambda item: item.atom_index)
    _require([item.atom_index for item in parameters] == list(range(ligand.atom_count)),
             "registered_charge_complete_parameter_mapping_required")
    for particle, atom, parameter in zip(particle_sections[0], ligand.atoms, parameters):
        token = particle.get("q")
        _require(particle.tag == "Particle" and type(token) is str and len(token) <= 128
                 and _DECIMAL.fullmatch(token), "registered_charge_original_decimal_token_required")
        number = Decimal(token)
        _require(number.is_finite() and abs(number.as_tuple().exponent) <= 64
                 and abs(number) <= Decimal(1024), "registered_charge_decimal_capacity_exceeded")
        _require(atom.partial_charge_e is not None
                 and float(token).hex() == float(atom.partial_charge_e).hex()
                 and float(token).hex() == float(parameter.charge_e).hex(),
                 "registered_charge_xml_canonical_binary64_mismatch")
        tokens.append(token)
    formal = sum(atom.formal_charge for atom in ligand.atoms)
    with localcontext() as context:
        context.prec = 256
        context.traps[Inexact] = True
        total = sum((Decimal(token) for token in tokens), Decimal(0))
        # One original-token decimal ULP per atom is conservative for either
        # rounded or truncated serialization. It is not a force-field tolerance.
        resolution = sum((Decimal(1).scaleb(Decimal(token).as_tuple().exponent)
                          for token in tokens), Decimal(0))
        difference = total - formal
        if resolution >= Decimal("0.5"):
            status = "insufficient_print_resolution"
        elif abs(difference) >= Decimal("0.5"):
            status = "different_integral_state_range"
        elif difference == 0:
            status = "equal_as_encoded"
        elif abs(difference) <= resolution:
            status = "within_print_resolution"
        else:
            status = "difference_exceeds_print_resolution"
    result = {"schema_version": "registered_openmm_ligand_net_charge_screen_v1",
              "profile": "openmm_system_xml_nonbonded_charge_tokens_v1",
              "status": status, "rank_eligible": status in {"equal_as_encoded", "within_print_resolution"},
              "canonical_formal_charge_sum_e": formal,
              "openmm_printed_partial_charge_sum_e": str(total), "difference_e": str(difference),
              "print_resolution_bound_e": str(resolution), "maximum_rank_difference_e": "0.5",
              "charge_tokens_sha256": _sha(tokens), "mapping_sha256": _sha(mapping),
              "xml_sha256": xml_ref["sha256"],
              "scope": "original_xml_token_arithmetic_and_complete_index_map_only_not_assayed_state"}
    _raw(xml_ref)
    return result


def _derive(row, request, charge_origin):
    from betelgeuze_engine_v2.molecular.serialization import (
        all_atom_system_from_canonical_json, canonical_coordinates_sha256,
        canonical_system_sha256, canonical_topology_sha256,
    )
    from .cpu_refinement_v1_2.evidence_contracts import request_binding
    from .cpu_refinement_v1_2.fixed_receptor import (
        CrossParameters, FixedReceptorEnvironment, require_system,
    )
    from .cpu_refinement_v1_2.workflow import _extension
    from .reference_minimization_workflow import _parameters

    _require(row["assigned_role"] == "development_test" and row["chemical_identity"] is not None
             and not row["prediction_issues"], "registered_candidate_not_prediction_eligible")
    _require(type(request) is dict and request.get("schema_id") == REQUEST_SCHEMA,
             "registered_canonical_d3_request_required")
    request_binding(request)
    sources = {key: deepcopy(request[key]) for key in SOURCE_FILES}
    # Parse through the existing canonical loader; strict JSON rejects duplicate
    # keys before the molecular loader is allowed to reconstruct canonical state.
    raw_systems = {key: _raw(sources[key]) for key in ("receptor", "ligand")}
    for raw in raw_systems.values():
        components.loads(raw)
    receptor, ligand = (all_atom_system_from_canonical_json(raw_systems[key]) for key in ("receptor", "ligand"))
    require_system(receptor, 8192)
    require_system(ligand, 256)
    base = _parameters(_json(sources["parameters"]))
    _require(base.topology_sha256 == canonical_topology_sha256(ligand),
             "registered_parameter_ligand_topology_mismatch")
    _extension(_json(sources["extensions"]), base)
    cross_doc = _json(sources["cross_parameters"])
    cross = CrossParameters.from_dict(cross_doc)
    FixedReceptorEnvironment(receptor, cross).validate_ligand(ligand, base)
    _require(cross.coordinate_frame_id == request["pocket"]["coordinate_frame_id"],
             "registered_coordinate_frame_mismatch")
    identity = _ligand_identity(ligand, row["chemical_identity"])
    screen = _charge_screen(charge_origin, request, ligand, base)
    target = row["target_annotation"]["chembl_target_id"]
    _require(target == row["native_metadata"]["target_chembl_id"]
             and row["assay_id"] == "chembl:assay:" + row["native_metadata"]["assay_chembl_id"],
             "registered_assay_target_mismatch")
    receptor_doc = {"system_sha256": canonical_system_sha256(receptor),
                    "coordinates_sha256": canonical_coordinates_sha256(receptor),
                    "construct_sha256": _sha(_construct(receptor)), "atom_count": receptor.atom_count}
    frame, pocket = request["pocket"]["coordinate_frame_id"], _sha(request["pocket"])
    cohort = {"schema_version": COHORT_SCHEMA, "target_chembl_id": target,
              "receptor_source_sha256": sources["receptor"]["sha256"],
              **{"receptor_" + key: receptor_doc[key] for key in
                 ("system_sha256", "coordinates_sha256", "construct_sha256")},
              "receptor_cross_parameters_sha256": _sha(cross_doc["receptor_atoms"]),
              "cross_model_sha256": _sha({key: value for key, value in cross_doc.items() if key not in {
                  "receptor_atoms", "ligand_topology_sha256", "ligand_base_parameters_sha256",
                  "receptor_system_sha256", "parameter_source_sha256", "parameter_set_id"}}),
              "pocket_sha256": pocket, "coordinate_frame_id": frame,
              "protocol_settings_sha256": _sha({key: request[key] for key in (
                  "schema_id", "backend", "receptor_margin_angstrom", "budget", "solver", "comparison", "selection")})}
    descriptor = {"schema_version": SCHEMA, "record_id": row["record_id"], "assay_id": row["assay_id"],
                  "metadata_origin_sha256": row["source_origins"]["metadata_origin"]["sha256"],
                  "method_origin_sha256": row["source_origins"]["method_origin"]["sha256"],
                  "target_annotation_sha256": row["target_annotation_sha256"], "target_chembl_id": target,
                  "request_schema": REQUEST_SCHEMA, "request_sha256": _sha(request), "source_files": sources,
                  "ligand": identity, "receptor": receptor_doc, "coordinate_frame_id": frame,
                  "pocket_sha256": pocket, "charge_origin": deepcopy(charge_origin), "charge_policy": CHARGE_POLICY,
                  "cohort": cohort, "same_prepared_assay_state_verified": False,
                  "source_authenticated": False, "scientifically_validated": False}
    validate_descriptor(descriptor)
    for ref in [*sources.values(), charge_origin]:
        _raw(ref)
    return descriptor, receptor, ligand, screen


def derive_observation(row, request, *, charge_origin):
    """Return source-checked metadata, without changing a role or running physics."""
    return _derive(row, request, charge_origin)[0]


def _pose_geometry_status(receptor, ligand, request):
    from betelgeuze_engine.product.prepared_rigid_poses import _inside_declared_pocket
    from .prepared_hard_overlap_screen import (
        HARD_OVERLAP_DISTANCE_ANGSTROM, minimum_cross_distance_angstrom,
    )

    pocket = request["pocket"]
    inside = int(_inside_declared_pocket(ligand.coordinates, pocket["center_angstrom"], pocket["radius_angstrom"]))
    minimum = (minimum_cross_distance_angstrom(receptor.coordinates[0].numpy(), ligand.coordinates[0].numpy())
               if inside else None)
    return {"requested": 1, "inside_declared_pocket": inside,
            "rank_eligible_inside_pocket": int(bool(inside) and minimum is not None
                                                and minimum >= HARD_OVERLAP_DISTANCE_ANGSTROM),
            "cross_distance_unavailable_inside_pocket": int(bool(inside) and minimum is None),
            "scope": "single_unmodified_registered_pose_all_atoms_pocket_and_1_angstrom_cross_overlap_only"}


def check_source_binding(row, request, *, inspect_pose_geometry=False):
    """Match a retained descriptor to sources re-opened through their bound refs."""
    _require(type(inspect_pose_geometry) is bool, "registered_geometry_flag_must_be_boolean")
    origin = row["source_origins"].get(SOURCE_FIELD)
    _require(type(origin) is dict, "registered_prepared_source_link_missing")
    supplied = _json(origin)
    validate_descriptor(supplied)
    expected, receptor, ligand, screen = _derive(row, request, supplied["charge_origin"])
    _require(components.canonical(supplied) == components.canonical(expected),
             "registered_prepared_source_link_mismatch")
    _raw(origin)
    result = {"schema_version": SCHEMA, "origin_sha256": origin["sha256"],
              "observation_sha256": _sha(expected), "candidate_prepared_identity_bound": True,
              "same_prepared_assay_state_verified": False, "cohort": expected["cohort"]}
    if inspect_pose_geometry:
        result["ligand_net_charge_screen"] = screen
        result["pose_geometry_status"] = _pose_geometry_status(receptor, ligand, request)
    return result


def cohort_binding(row, request, receipt=None):
    """Rederive common receptor/protocol binding, excluding ligand-specific values."""
    checked = check_source_binding(row, request)
    if receipt is not None:
        _require(type(receipt) is dict and all(receipt.get(key) == value for key, value in checked.items()),
                 "registered_binding_receipt_mismatch")
    return checked["cohort"]
