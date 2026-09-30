"""Synthetic source representation checks; no solver, model or assay outcomes."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest
from rdkit import Chem
from rdkit.Chem import rdDepictor
import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem, Atom, Bond, Chain, Residue, StructureProvenance,
    canonical_system_sha256, canonical_topology_sha256,
)
from betelgeuze_engine_v2.molecular.serialization import (
    all_atom_system_from_canonical_json, canonical_coordinates_sha256, canonical_system_json_bytes,
)
from betelgeuze_product import installed_native_v4_registered_binding as binding
from betelgeuze_product.native_v4_chemical_identity import chemical_identity
from betelgeuze_product.cpu_refinement_v1_2.openmm_periodic_extension import OpenMMPeriodicParameters
from betelgeuze_product.reference_minimization_workflow import _parameters
from tests.unit.test_cpu_registered_pose_workflow import request_fixture


def _write(path, value):
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    path.write_bytes(raw)
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest()}


def _row(smiles="O"):
    return {"record_id": "synthetic:development:1", "assay_id": "chembl:assay:CHEMBL123",
            "assigned_role": "development_test", "prediction_issues": [],
            "chemical_identity": chemical_identity(smiles),
            "target_annotation": {"chembl_target_id": "CHEMBL3371"},
            "target_annotation_sha256": "a" * 64,
            "native_metadata": {"target_chembl_id": "CHEMBL3371", "assay_chembl_id": "CHEMBL123"},
            "source_origins": {"metadata_origin": {"sha256": "b" * 64},
                               "method_origin": {"sha256": "c" * 64}}}


def _fixture(directory, tokens=("-0.800000", "0.400000", "0.400000")):
    request, ligand = request_fixture(directory)
    ligand = replace(ligand, atoms=tuple(replace(atom, partial_charge_e=float(token))
                                        for atom, token in zip(ligand.atoms, tokens)))
    request["ligand"] = _write(Path(request["ligand"]["path"]), canonical_system_json_bytes(ligand))
    base = _parameters(json.loads(Path(request["parameters"]["path"]).read_bytes()))
    base = replace(base, topology_sha256=canonical_topology_sha256(ligand),
                   atom_parameters=tuple(replace(p, charge_e=float(token))
                                         for p, token in zip(base.atom_parameters, tokens)))
    request["parameters"] = _write(Path(request["parameters"]["path"]), base.to_dict())
    request["extensions"] = _write(Path(request["extensions"]["path"]), OpenMMPeriodicParameters(base).to_dict())
    cross = json.loads(Path(request["cross_parameters"]["path"]).read_bytes())
    cross.update(ligand_topology_sha256=canonical_topology_sha256(ligand),
                 ligand_base_parameters_sha256=base.fingerprint_sha256)
    request["cross_parameters"] = _write(Path(request["cross_parameters"]["path"]), cross)
    xml = ET.Element("System")
    particles = ET.SubElement(xml, "Particles")
    force = ET.SubElement(ET.SubElement(xml, "Forces"), "Force", type="NonbondedForce")
    charges = ET.SubElement(force, "Particles")
    for token in tokens:
        ET.SubElement(particles, "Particle", mass="1")
        ET.SubElement(charges, "Particle", q=token, sig="1", eps="0")
    xml_ref = _write(directory / "charges.xml", ET.tostring(xml))
    provenance = {"schema_version": binding.CHARGE_ORIGIN_SCHEMA, "openmm_system": xml_ref,
                  "ligand_source_sha256": request["ligand"]["sha256"],
                  "ligand_system_sha256": canonical_system_sha256(ligand),
                  "atom_mapping": [
                      {"particle_index": i, "ligand_atom_index": i, "atom_name": atom.name,
                       "element": atom.element, "atomic_number": atom.atomic_number,
                       "isotope_mass_number": atom.isotope_mass_number, "formal_charge": atom.formal_charge}
                      for i, atom in enumerate(ligand.atoms)]}
    origin = _write(directory / "charge-origin.json", provenance)
    return _row(), request, origin, ligand


def _bind(directory, row, request, charge):
    descriptor = binding.derive_observation(row, request, charge_origin=charge)
    row["source_origins"][binding.SOURCE_FIELD] = _write(directory / "binding.json", descriptor)
    return descriptor


def test_roundtrip_binds_original_coordinates_and_complete_sources_without_physics(tmp_path, monkeypatch):
    from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import FixedReceptorEnvironment
    monkeypatch.setattr(FixedReceptorEnvironment, "evaluate_cross", lambda *_: pytest.fail("physics invoked"))
    row, request, charge, ligand = _fixture(tmp_path)
    descriptor = _bind(tmp_path, row, request, charge)
    binding.validate_descriptor(descriptor)
    receipt = binding.check_source_binding(row, request, inspect_pose_geometry=True)
    assert receipt["candidate_prepared_identity_bound"] is True
    assert not receipt["same_prepared_assay_state_verified"]
    assert descriptor["ligand"]["coordinates_sha256"] == canonical_coordinates_sha256(ligand)
    assert receipt["cohort"] == descriptor["cohort"] == binding.cohort_binding(row, request, receipt)
    assert receipt["ligand_net_charge_screen"]["status"] == "equal_as_encoded"
    assert receipt["pose_geometry_status"]["rank_eligible_inside_pocket"] == 1
    assert set(binding.check_source_binding(row, request)) == {
        "schema_version", "origin_sha256", "observation_sha256", "candidate_prepared_identity_bound",
        "same_prepared_assay_state_verified", "cohort"}


@pytest.mark.parametrize("tokens,status,difference", [
    (("-0.8000001", "0.400000", "0.400000"), "within_print_resolution", "-1E-7"),
    (("-0.800100", "0.400000", "0.400000"), "difference_exceeds_print_resolution", "-0.000100"),
    (("-0.200000", "0.400000", "0.400000"), "different_integral_state_range", "0.600000"),
    (("-0.8", "0.4", "0.4"), "equal_as_encoded", "0.0"),
    (("0", "0", "0"), "insufficient_print_resolution", "0"),
])
def test_original_decimal_tokens_determine_signed_sum_and_print_resolution(tmp_path, tokens, status, difference):
    row, request, charge, _ = _fixture(tmp_path, tokens)
    _bind(tmp_path, row, request, charge)
    screen = binding.check_source_binding(row, request, inspect_pose_geometry=True)["ligand_net_charge_screen"]
    assert screen["status"] == status
    assert screen["difference_e"] == difference
    assert screen["rank_eligible"] == (status in {"equal_as_encoded", "within_print_resolution"})


def test_resealed_xml_token_change_cannot_hide_binary64_mismatch(tmp_path):
    row, request, charge, _ = _fixture(tmp_path)
    provenance = json.loads(Path(charge["path"]).read_bytes())
    xml_path = Path(provenance["openmm_system"]["path"])
    provenance["openmm_system"] = _write(xml_path, xml_path.read_bytes().replace(b'-0.800000', b'-0.800001'))
    charge = _write(Path(charge["path"]), provenance)
    with pytest.raises(ValueError, match="binary64_mismatch"):
        binding.derive_observation(row, request, charge_origin=charge)


@pytest.mark.parametrize("change", ["swap", "missing", "identity", "float_tokens", "offset"])
def test_atom_mapping_and_original_xml_policy_fail_closed(tmp_path, change):
    row, request, charge, _ = _fixture(tmp_path)
    provenance = json.loads(Path(charge["path"]).read_bytes())
    if change == "swap":
        provenance["atom_mapping"][1], provenance["atom_mapping"][2] = provenance["atom_mapping"][2], provenance["atom_mapping"][1]
    elif change == "missing":
        provenance["atom_mapping"].pop()
    elif change == "identity":
        provenance["atom_mapping"][0]["element"] = "N"
    elif change == "float_tokens":
        provenance["charge_tokens"] = [-.8, .4, .4]
    else:
        xml_path = Path(provenance["openmm_system"]["path"])
        xml = ET.fromstring(xml_path.read_bytes())
        ET.SubElement(ET.SubElement(xml.find("Forces/Force"), "ParticleOffsets"), "Offset", parameter="x")
        provenance["openmm_system"] = _write(xml_path, ET.tostring(xml))
    charge = _write(Path(charge["path"]), provenance)
    with pytest.raises(ValueError, match="registered_"):
        binding.derive_observation(row, request, charge_origin=charge)


def test_identity_swap_cannot_be_accepted_after_resealing_descriptor(tmp_path):
    row, request, charge, _ = _fixture(tmp_path)
    descriptor = _bind(tmp_path, row, request, charge)
    row["chemical_identity"] = chemical_identity("N")
    descriptor["ligand"]["canonical_isomeric_smiles_sha256"] = row["chemical_identity"]["canonical_isomeric_smiles_sha256"]
    row["source_origins"][binding.SOURCE_FIELD] = _write(tmp_path / "binding.json", descriptor)
    with pytest.raises(ValueError, match="chemical_identity_mismatch"):
        binding.check_source_binding(row, request)


@pytest.mark.parametrize("section", [None, "ligand", "receptor", "charge_origin", "cohort"])
def test_descriptor_strictly_rejects_outcome_fields(tmp_path, section):
    row, request, charge, _ = _fixture(tmp_path)
    descriptor = binding.derive_observation(row, request, charge_origin=charge)
    (descriptor if section is None else descriptor[section])["pchembl_value"] = 9.
    with pytest.raises(ValueError, match="exact_metadata_fields"):
        binding.validate_descriptor(descriptor)


def test_request_and_source_changes_fail_after_descriptor_reseal(tmp_path):
    row, request, charge, _ = _fixture(tmp_path)
    descriptor = _bind(tmp_path, row, request, charge)
    request["pocket"]["radius_angstrom"] += 1.
    descriptor["request_sha256"] = binding._sha(request)
    row["source_origins"][binding.SOURCE_FIELD] = _write(tmp_path / "binding.json", descriptor)
    with pytest.raises(ValueError, match="source_link_mismatch"):
        binding.check_source_binding(row, request)
    request["charge_origin"] = charge
    with pytest.raises(ValueError):
        binding.derive_observation(row, request, charge_origin=charge)


def _stereo_system(smiles, xyz):
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    conformer = Chem.Conformer(mol.GetNumAtoms())
    conformer.Set3D(True)
    for i, point in enumerate(xyz):
        conformer.SetAtomPosition(i, point)
    mol.AddConformer(conformer)
    Chem.RemoveStereochemistry(mol)
    Chem.AssignStereochemistryFrom3D(mol)
    Chem.AssignStereochemistry(mol, force=True, cleanIt=True)
    observed = Chem.MolToSmiles(Chem.RemoveHs(mol), isomericSmiles=True)
    atoms = tuple(Atom(i, f"{a.GetSymbol()}{i}", a.GetSymbol(), a.GetAtomicNum(), 0,
                       formal_charge=a.GetFormalCharge(), partial_charge_e=0.,
                       isotope_mass_number=a.GetIsotope() or None, aromatic=a.GetIsAromatic(),
                       stereo=a.GetProp("_CIPCode") if a.HasProp("_CIPCode") else "unspecified")
                  for i, a in enumerate(mol.GetAtoms()))
    bonds = tuple(Bond(i, min(b.GetBeginAtomIdx(), b.GetEndAtomIdx()), max(b.GetBeginAtomIdx(), b.GetEndAtomIdx()),
                       b.GetBondTypeAsDouble(), aromatic=b.GetIsAromatic(),
                       stereo={"STEREOE": "E", "STEREOZ": "Z"}.get(str(b.GetStereo()), "none"))
                  for i, b in enumerate(mol.GetBonds()))
    return AllAtomSystem("synthetic-stereo", atoms, bonds,
                         (Residue(0, "SYN", 0, 1, tuple(range(len(atoms)))),), (Chain(0, "A", (0,)),),
                         torch.tensor([xyz], dtype=torch.float64),
                         StructureProvenance(source_format="synthetic", source_id="stereo", source_sha256="d" * 64,
                                             parser_name="synthetic", parser_version="1")), chemical_identity(observed)


def _aromatic_system(smiles, *, kekule=False):
    molecule = Chem.AddHs(Chem.MolFromSmiles(smiles))
    rdDepictor.Compute2DCoords(molecule)
    xyz = molecule.GetConformer().GetPositions().tolist()
    ligand, identity = _stereo_system(smiles, xyz)
    if kekule:
        Chem.Kekulize(molecule, clearAromaticFlags=False)
        ligand = replace(ligand, bonds=tuple(
            replace(bond, order=molecule.GetBondBetweenAtoms(bond.atom_i, bond.atom_j).GetBondTypeAsDouble())
            for bond in ligand.bonds))
    return ligand, identity


@pytest.mark.parametrize("smiles", ["c1ccccc1", "c1ccncc1", "c1cc[nH]c1", "c1ccoc1",
                                   "c1ncc[nH]1", "c1ccc2[nH]ccc2c1", "c1cc[nH+]cc1"])
def test_aromatic_and_kekule_graphs_bind_same_identity_but_keep_original_hashes(smiles):
    fractional, identity = _aromatic_system(smiles)
    integer, integer_identity = _aromatic_system(smiles, kekule=True)
    assert identity == integer_identity
    original = canonical_system_json_bytes(integer)
    left = binding._ligand_identity(fractional, identity)
    right = binding._ligand_identity(integer, identity)
    assert left["canonical_isomeric_smiles_sha256"] == right["canonical_isomeric_smiles_sha256"]
    assert left["coordinates_sha256"] == right["coordinates_sha256"]
    assert left["atom_graph_sha256"] != right["atom_graph_sha256"]
    assert left["system_sha256"] != right["system_sha256"]
    assert canonical_system_json_bytes(integer) == original


def test_alternate_benzene_kekule_assignment_keeps_distinct_raw_graph():
    ligand, identity = _aromatic_system("c1ccccc1", kekule=True)
    alternative = replace(ligand, bonds=tuple(
        replace(bond, order=3. - bond.order) if bond.aromatic else bond for bond in ligand.bonds))
    first = binding._ligand_identity(ligand, identity)
    second = binding._ligand_identity(alternative, identity)
    assert first["atom_graph_sha256"] != second["atom_graph_sha256"]
    assert first["canonical_isomeric_smiles_sha256"] == second["canonical_isomeric_smiles_sha256"]


@pytest.mark.parametrize("change", ["all_single", "extra_double", "missing_double", "mixed_encoding",
                                    "triple", "edge_flag", "atom_flag", "hydrogen_flag",
                                    "missing_hydrogen", "isotope", "formal_charge"])
def test_aromatic_normalization_cannot_repair_invalid_or_changed_raw_graph(change):
    ligand, identity = _aromatic_system("c1ccccc1", kekule=True)
    binding._ligand_identity(ligand, identity)
    atoms, bonds = list(ligand.atoms), list(ligand.bonds)
    single = next(i for i, bond in enumerate(bonds) if bond.aromatic and bond.order == 1.)
    double = next(i for i, bond in enumerate(bonds) if bond.aromatic and bond.order == 2.)
    if change == "all_single":
        bonds = [replace(bond, order=1.) if bond.aromatic else bond for bond in bonds]
    elif change == "extra_double":
        bonds[single] = replace(bonds[single], order=2.)
    elif change == "missing_double":
        bonds[double] = replace(bonds[double], order=1.)
    elif change == "mixed_encoding":
        bonds[single] = replace(bonds[single], order=1.5)
    elif change == "triple":
        bonds[single] = replace(bonds[single], order=3.)
    elif change == "edge_flag":
        bonds[single] = replace(bonds[single], aromatic=False)
    elif change == "atom_flag":
        atoms[0] = replace(atoms[0], aromatic=False)
    elif change == "hydrogen_flag":
        atoms[-1] = replace(atoms[-1], aromatic=True)
    elif change == "missing_hydrogen":
        bonds = [bond for bond in bonds if bond.atom_i != len(atoms) - 1 and bond.atom_j != len(atoms) - 1]
    elif change == "isotope":
        atoms[0] = replace(atoms[0], isotope_mass_number=13)
    else:
        atoms[0] = replace(atoms[0], formal_charge=1)
    with pytest.raises(ValueError, match="registered_ligand_"):
        binding._ligand_identity(replace(ligand, atoms=tuple(atoms), bonds=tuple(bonds)), identity)


def test_disconnected_aromatic_edge_sets_can_use_different_complete_encodings():
    ligand, identity = _aromatic_system("c1ccccc1-c2ccccc2", kekule=True)
    ligand = replace(ligand, bonds=tuple(
        replace(bond, order=1.5) if bond.aromatic and bond.atom_i < 6 and bond.atom_j < 6 else bond
        for bond in ligand.bonds))
    binding._ligand_identity(ligand, identity)


def test_sanitization_must_not_repair_neutral_nitro_formal_charges():
    ligand, identity = _aromatic_system("[O-][N+](=O)c1ccccc1", kekule=True)
    binding._ligand_identity(ligand, identity)
    atoms = tuple(replace(atom, formal_charge=0) if i in {0, 1} else atom
                  for i, atom in enumerate(ligand.atoms))
    bonds = tuple(replace(bond, order=2.) if {bond.atom_i, bond.atom_j} == {0, 1} else bond
                  for bond in ligand.bonds)
    with pytest.raises(ValueError, match="registered_ligand_"):
        binding._ligand_identity(replace(ligand, atoms=atoms, bonds=bonds), identity)


def _sulfonyl_system(smiles="CS(=O)(=O)N"):
    molecule = Chem.AddHs(Chem.MolFromSmiles(smiles))
    rdDepictor.Compute2DCoords(molecule)
    xyz = molecule.GetConformer().GetPositions().tolist()
    sulfur = next(atom for atom in molecule.GetAtoms() if atom.GetAtomicNum() == 16)
    xyz[sulfur.GetIdx()] = [0., 0., 0.]
    for atom, point in zip(sulfur.GetNeighbors(), [
            [1., 1., 1.], [1., -1., -1.], [-1., 1., -1.], [-1., -1., 1.]]):
        xyz[atom.GetIdx()] = point
    ligand, _ = _stereo_system(smiles, xyz)
    return ligand, chemical_identity(smiles)


@pytest.mark.parametrize("smiles", ["CS(=O)(=O)N", "CS(=O)(=O)C",
                                   "CS(=[18O])(=[18O])N", "CS(=[16O])(=[16O])N"])
def test_ordinary_sulfonyl_potential_stereo_preserves_raw_identity_and_graph(smiles):
    ligand, identity = _sulfonyl_system(smiles)
    source, encoded = deepcopy(identity), canonical_system_json_bytes(ligand)
    flags = (Chem.GetAllowNontetrahedralChirality(), Chem.GetUseLegacyStereoPerception())
    assert identity["stereo_unspecified_count"] == 1
    observed = binding._ligand_identity(ligand, identity)
    assert observed["canonical_isomeric_smiles_sha256"] == identity["canonical_isomeric_smiles_sha256"]
    assert identity == source and canonical_system_json_bytes(ligand) == encoded
    assert flags == (Chem.GetAllowNontetrahedralChirality(), Chem.GetUseLegacyStereoPerception())


@pytest.mark.parametrize("smiles", [
    "CS(=[18O])(=O)N", "CS(=[16O])(=O)N",  # distinct exact oxo isotopes
    "CS(=O)N", "CS(=O)(=N)N", "CS(=[O+]C)(=O)N",  # sulfoxide/imino/nonterminal oxo
    "C[S+](=O)(=O)N", "C[S](=O)(O)N",  # different charge/valence state
    "CS(=O)(=O)NC(F)(Cl)Br", "CS(=O)(=O)NC=C(F)Cl",  # other unresolved stereo
    "F[Pt](F)(Cl)Br", "FP(F)(F)(Cl)Br", "F[Co](F)(F)(F)(Cl)Br",
    "C[S@SP1](=O)(=O)N", "C[S@SP0](=O)(=O)N", "C[S@SP](=O)(=O)N",
    "C[S@TB1](=O)(=O)N", "C[S@OH1](=O)(=O)N", "N[Pt@SP1](Cl)(F)Br",
])
def test_sulfonyl_exception_cannot_clear_unsupported_source_stereo(smiles):
    # The source gate must reject before opening or reconstructing any ligand.
    identity = chemical_identity(smiles)
    original = deepcopy(identity)
    with pytest.raises(ValueError, match="chemical_identity_unresolved"):
        binding._ligand_identity(None, identity)
    assert identity == original


@pytest.mark.parametrize("count", [0, 2, True, 1.0, "1"])
def test_sulfonyl_exception_does_not_rewrite_or_trust_unspecified_count(count):
    ligand, identity = _sulfonyl_system()
    identity["stereo_unspecified_count"] = count
    with pytest.raises(ValueError, match="chemical_identity_unresolved"):
        binding._ligand_identity(ligand, identity)


@pytest.mark.parametrize("property_name", ["_UnknownStereo", "_chiralPermutation"])
def test_explicit_unknown_sulfur_marker_is_not_an_ordinary_untagged_center(property_name):
    molecule = Chem.MolFromSmiles("CS(=O)(=O)N")
    potential = list(Chem.FindPotentialStereo(molecule))
    assert binding._supported_stereo(molecule, potential)
    molecule.GetAtomWithIdx(potential[0].centeredOn).SetIntProp(property_name, 0)
    assert not binding._supported_stereo(molecule, potential)


def test_coordinates_assigning_actual_square_planar_sulfur_remain_unsupported():
    ligand, source = _sulfonyl_system()
    binding._ligand_identity(ligand, source)
    # Identical oxo ligands do not erase a coordinate-perceived SP assignment.
    planar, declared = _aromatic_system("CS(=O)(=O)N")
    assert "@SP" in declared["canonical_isomeric_smiles"]
    with pytest.raises(ValueError, match="geometry_stereochemistry_unresolved"):
        binding._ligand_identity(planar, source)


def test_sulfonyl_exception_cannot_hide_changed_isotope_in_registered_graph():
    ligand, identity = _sulfonyl_system()
    oxygen = next(atom.index for atom in ligand.atoms if atom.element == "O")
    atoms = tuple(replace(atom, isotope_mass_number=18) if i == oxygen else atom
                  for i, atom in enumerate(ligand.atoms))
    with pytest.raises(ValueError, match="registered_ligand_"):
        binding._ligand_identity(replace(ligand, atoms=atoms), identity)


def test_actual_registered_coordinates_determine_tetrahedral_stereo():
    ligand, identity = _stereo_system("FC(Cl)(Br)I", [(1.,1.,1.), (0.,0.,0.), (1.,-1.,-1.),
                                                    (-1.,1.,-1.), (-1.,-1.,1.)])
    binding._ligand_identity(ligand, identity)
    mirrored = ligand.coordinates.clone()
    mirrored[:, :, 0] *= -1
    with pytest.raises(ValueError, match="geometry_stereochemistry"):
        binding._ligand_identity(ligand.with_coordinates(mirrored, operation="synthetic_mirror"), identity)


def test_actual_registered_coordinates_determine_double_bond_stereo():
    ligand, identity = _stereo_system("F/C=C/F", [(-2.,1.,0.), (-1.,0.,0.), (1.,0.,0.),
                                                 (2.,-1.,0.), (-1.,-1.,0.), (1.,1.,0.)])
    binding._ligand_identity(ligand, identity)
    changed = ligand.coordinates.clone()
    changed[:, [3, 5], 1] *= -1
    with pytest.raises(ValueError, match="geometry_stereochemistry"):
        binding._ligand_identity(ligand.with_coordinates(changed, operation="synthetic_EZ_swap"), identity)


@pytest.mark.parametrize("change", ["isotope", "charge", "bond", "aromatic", "missing_hydrogen"])
def test_resealed_graph_cannot_change_source_identity(tmp_path, change):
    _, ligand = request_fixture(tmp_path)
    atoms, bonds = list(ligand.atoms), list(ligand.bonds)
    if change == "isotope":
        atoms[0] = replace(atoms[0], isotope_mass_number=18)
    elif change == "charge":
        atoms[0] = replace(atoms[0], formal_charge=1)
    elif change == "bond":
        bonds[0] = replace(bonds[0], order=2.)
    elif change == "aromatic":
        atoms[0] = replace(atoms[0], aromatic=True)
    else:
        bonds.pop()
    altered = replace(ligand, atoms=tuple(atoms), bonds=tuple(bonds))
    with pytest.raises(ValueError, match="registered_ligand_"):
        binding._ligand_identity(altered, chemical_identity("O"))


def test_single_registered_geometry_blocks_outside_pocket_and_hard_overlap(tmp_path):
    row, request, charge, ligand = _fixture(tmp_path)
    receptor = all_atom_system_from_canonical_json(Path(request["receptor"]["path"]).read_bytes())
    assert binding._pose_geometry_status(ligand, ligand, request)["rank_eligible_inside_pocket"] == 0
    outside = deepcopy(request)
    outside["pocket"]["radius_angstrom"] = .01
    assert binding._pose_geometry_status(receptor, ligand, outside)["inside_declared_pocket"] == 0


def test_common_cohort_excludes_ligand_specific_parameter_provenance(tmp_path):
    row, request, charge, _ = _fixture(tmp_path)
    before = binding.derive_observation(row, request, charge_origin=charge)
    cross_path = Path(request["cross_parameters"]["path"])
    cross = json.loads(cross_path.read_bytes())
    cross.update(parameter_set_id="second-ligand-source", parameter_source_sha256="f" * 64)
    request["cross_parameters"] = _write(cross_path, cross)
    after = binding.derive_observation(row, request, charge_origin=charge)
    assert after["cohort"] == before["cohort"]
    assert after["request_sha256"] != before["request_sha256"]
    cross["dielectric"] *= 2
    request["cross_parameters"] = _write(cross_path, cross)
    assert binding.derive_observation(row, request, charge_origin=charge)["cohort"] != before["cohort"]


def test_descriptor_validation_does_not_import_torch_or_open_sources(tmp_path):
    row, request, charge, _ = _fixture(tmp_path)
    descriptor = binding.derive_observation(row, request, charge_origin=charge)
    code = '''
import importlib.abc, json, sys
class NoPhysics(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "torch" or fullname.startswith(("torch.", "betelgeuze_engine_v2.", "betelgeuze_engine.")):
            raise AssertionError("metadata validator imported physics: " + fullname)
sys.meta_path.insert(0, NoPhysics())
from betelgeuze_product.installed_native_v4_registered_binding import validate_descriptor
validate_descriptor(json.loads(sys.stdin.read()))
assert "torch" not in sys.modules
'''
    completed = subprocess.run([sys.executable, "-c", code], input=json.dumps(descriptor),
                               text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("replacement", [b'&#48;.400000', b'0.400000&x;'])
def test_xml_entity_spelling_is_not_treated_as_an_original_decimal_token(tmp_path, replacement):
    row, request, charge, _ = _fixture(tmp_path)
    provenance = json.loads(Path(charge["path"]).read_bytes())
    xml_path = Path(provenance["openmm_system"]["path"])
    provenance["openmm_system"] = _write(xml_path, xml_path.read_bytes().replace(b'0.400000', replacement, 1))
    charge = _write(Path(charge["path"]), provenance)
    with pytest.raises(ValueError, match="xml_declarations_unsupported"):
        binding.derive_observation(row, request, charge_origin=charge)


def test_resealed_base_and_cross_cannot_hide_parameter_topology_mismatch(tmp_path):
    row, request, charge, _ = _fixture(tmp_path)
    path = Path(request["parameters"]["path"])
    base = replace(_parameters(json.loads(path.read_bytes())), topology_sha256="f" * 64)
    request["parameters"] = _write(path, base.to_dict())
    request["extensions"] = _write(Path(request["extensions"]["path"]), OpenMMPeriodicParameters(base).to_dict())
    cross_path = Path(request["cross_parameters"]["path"])
    cross = json.loads(cross_path.read_bytes())
    cross["ligand_base_parameters_sha256"] = base.fingerprint_sha256
    request["cross_parameters"] = _write(cross_path, cross)
    with pytest.raises(ValueError, match="parameter_ligand_topology_mismatch"):
        binding.derive_observation(row, request, charge_origin=charge)
