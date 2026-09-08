"""Synthetic source-integrity checks; no energies, preparation or solver runs."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest
import torch

from betelgeuze_engine.product import prepared_gromacs_input as parser


def _pdb_atom(serial, name, element, chain, x, *, formal=""):
    return f"ATOM  {serial:5d} {name:>4s} SYN {chain}   1    {x:8.3f}{0.:8.3f}{0.:8.3f}{1.:6.2f}{0.:6.2f}          {element:>2s}{formal:>2s}\n"


def _sdf():
    result = "synthetic prepared ligand\nsynthetic\n\n  3  2  0  0  0  0            999 V2000\n"
    for element, (x, y, z) in zip(("C", "C", "H"), ((2., 1., 0.), (3., 1., 0.), (3., 2., 0.))):
        result += f"{x:10.4f}{y:10.4f}{z:10.4f} {element:3s} 0  0  0  0  0  0  0  0  0  0  0  0\n"
    return result + "  1  2  1  0  0  0\n  2  3  1  0  0  0\nM  END\n> <source_identity>\nsynthetic-001\n\n$$$$\n"


def _gro():
    result = "synthetic\n3\n"
    for index, (name, xyz) in enumerate(zip(("C0", "C1", "H2"), ((.2, .1, 0.), (.3, .1, 0.), (.3, .2, 0.))), 1):
        result += f"{1:5d}{'LIG':<5s}{name:>5s}{index:5d}" + " ".join(f"{value:.8f}" for value in xyz) + "\n"
    return result + "1.0 1.0 1.0\n"


@pytest.fixture
def request_doc(tmp_path):
    def source(name, content):
        path = tmp_path / name
        path.write_text(content)
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "source_id": "synthetic:" + name}

    return {
        "schema_version": parser.SCHEMA_VERSION,
        "protein_pdb": source("protein.pdb", _pdb_atom(1, "1H1", "H", "A", 0.) + _pdb_atom(2, "C", "C", "A", 1.) + _pdb_atom(3, "O", "O", "A", 2., formal="1-") + _pdb_atom(4, "N", "N", "B", 4.) + "END\n"),
        "protein_chains": [
            {"chain_id": "A", "molecule_itp": source("chain_A.itp", "[ moleculetype ]\nA 3\n[ atoms ]\n1 H 1 SYN H11 1 0 1.008\n2 C 1 SYN C 2 0.25 12.01\n3 O 1 SYN O 3 -0.25 16.00\n[ bonds ]\n1 2 1\n2 3 1\n[ pairs ]\n1 3 1\n[ angles ]\n1 2 3 1\n#ifdef POSRES\n#include \"posre_A.itp\"\n#endif\n")},
            {"chain_id": "B", "molecule_itp": source("chain_B.itp", "[ moleculetype ]\nB 3\n[ atoms ]\n1 N 1 SYN N 1 -0.0 14.01\n")},
        ],
        "protein_atomtypes": source("protein_types.itp", "[ atomtypes ]\nH 1 1.008 0 A 0 0\nC 6 12.01 0 A 0.34 0.42\nO 8 16.00 0 A 0.30 0.71\nN 7 14.01 0 A 0.32 0.71\n"),
        "protein_defaults": source("forcefield.itp", '#define _FF_AMBER\n[ defaults ]\n1 2 yes 0.5 0.8333\n#include "ffnonbonded.itp"\n'),
        "ligand_sdf": source("ligand.sdf", _sdf()),
        "ligand_gro": source("ligand.gro", _gro()),
        "ligand_itp": source("ligand.itp", "[ moleculetype ]\nMOL 3\n[ atoms ]\n1 CL 1 MOL C0 1 0.0 12.01\n2 CL 1 MOL C1 2 -0.2 12.01\n3 HL 1 MOL H2 3 0.2 1.008\n[ bonds ]\n1 2 1\n2 3 1\n[ angles ]\n1 2 3 1 109.5 100\n"),
        "ligand_atomtypes": source("ligand_types.itp", "[ atomtypes ]\nCL 12.01 0 A 0.340000 0.420000\nHL 1.008 0 A 0.000000 0.000000\n"),
        "ligand_defaults": source("ligand.top", "[ defaults ]\n1 2 no 1 0.83333\n[ atomtypes ]\nC 6 12.01 0 A 0.34 0.42\nH 1 1.008 0 A 0 0\n"),
        "ligand_atomtype_name_mapping": {"CL": "C", "HL": "H"},
        "ligand_residue_name_mapping": {"gro": "LIG", "itp": "MOL"},
        "naming_convention": "pdb_leading_digit_to_gromacs_suffix",
        "pdb_element_policy": "reject_missing",
        "source_declarations": {key: "synthetic-caller-assertion" for key in ("coordinate_frame_id", "prepared_state_id", "parameter_source_id", "charge_source_id")},
        "source_relationship": "Independent synthetic compiled topology and lookup table; coevality not verified.",
    }


def _change(ref, transform):
    path = Path(ref["path"])
    path.write_text(transform(path.read_text()))
    ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def test_explicit_units_zeros_coordinates_and_provenance(request_doc):
    receptor, ligand, rparams, lparams, provenance = parser.load_prepared_gromacs_components(request_doc)
    assert receptor.atom_count == 4 and ligand.atom_count == 3
    assert receptor.coordinates.dtype == ligand.coordinates.dtype == torch.float64
    assert receptor.coordinates.device.type == ligand.coordinates.device.type == "cpu"
    assert receptor.cell is ligand.cell is None
    assert receptor.coordinates.tolist() == [[[0., 0., 0.], [1., 0., 0.], [2., 0., 0.], [4., 0., 0.]]]
    assert ligand.coordinates.tolist() == [[[2., 1., 0.], [3., 1., 0.], [3., 2., 0.]]]
    assert rparams[0] == {"atom_index": 0, "charge_e": 0., "sigma_angstrom": 0., "epsilon_kcal_per_mol": 0.}
    assert rparams[1]["sigma_angstrom"] == 0.34 * 10
    assert lparams[1]["epsilon_kcal_per_mol"] == .42 / 4.184
    assert receptor.atoms[0].partial_charge_e == 0. and receptor.atoms[0].name == "1H1"
    assert receptor.atoms[0].metadata["prepared_gromacs_source"]["formal_charge_annotation_status"].startswith("missing_pdb_annotation")
    assert receptor.atoms[2].formal_charge == -1
    assert receptor.atoms[2].metadata["prepared_gromacs_source"]["formal_charge_annotation_status"] == "explicit_pdb_annotation"
    assert receptor.bonds == ()  # No chemical order invented from GROMACS.
    assert provenance["receptor_source_bond_adjacency"] == [[0, 1], [1, 2]]
    assert provenance["protein_name_mapping"] == [{"atom_index": 0, "pdb": "1H1", "itp": "H11"}]
    assert provenance["source_hashes_postflight_verified"]
    assert not provenance["source_coevality_verified"] and not provenance["declarations_verified"]
    assert not any(provenance["claim_policy"].values())
    assert provenance["defaults_by_source"]["protein_defaults"]["fudge_lj"] == .5
    assert provenance["defaults_by_source"]["ligand_defaults"]["fudge_lj"] == 1.
    assert provenance["cross_lennard_jones_scale"] == 1.
    assert not provenance["within_molecule_gen_pairs_and_fudge_values_applied"]
    assert provenance["sdf_data_field_projection"]["data_fields"] == {"source_identity": ["synthetic-001"]}
    assert provenance["sdf_data_field_projection"]["original_sha256"] == request_doc["ligand_sdf"]["sha256"]
    assert "#ifdef POSRES" in provenance["original_topologies"]["protein_chain_A"]["source_text"]
    assert not provenance["posres_enabled"]


@pytest.mark.parametrize("key", ["protein_pdb", "protein_atomtypes", "protein_defaults", "ligand_sdf", "ligand_gro", "ligand_itp", "ligand_atomtypes", "ligand_defaults"])
def test_hash_is_required_for_every_source(request_doc, key):
    request_doc[key]["sha256"] = "0" * 64
    with pytest.raises(parser.PreparedGromacsInputError, match="SHA-256 mismatch"):
        parser.load_prepared_gromacs_components(request_doc)


@pytest.mark.parametrize("replacement", ["", "nan", "inf", "no-charge"])
def test_missing_or_nonfinite_charge_is_not_zero(request_doc, replacement):
    _change(request_doc["ligand_itp"], lambda value: value.replace("C0 1 0.0", "C0 1 " + replacement))
    with pytest.raises(parser.PreparedGromacsInputError):
        parser.load_prepared_gromacs_components(request_doc)


@pytest.mark.parametrize(("old", "new", "message"), [
    ("2 CL 1 MOL C1", "1 CL 1 MOL C1", "indices"),
    ("3 HL 1 MOL H2", "4 HL 1 MOL H2", "indices"),
    ("2 CL 1 MOL C1", "2 CL 1 MOL C0", "duplicate atom name"),
    ("1 CL 1 MOL C0", "1 MISSING 1 MOL C0", "missing atomtype"),
    ("0.0 12.01", "0.0 0", "mass"),
    ("1 2 1\n2 3 1", "1 2 1\n1 3 1", "adjacency"),
    ("1 2 1\n2 3 1", "1 2 1\n1 2 1", "duplicate bond"),
    ("1 2 1\n2 3 1", "1 2 1\n2 4 1", "indices"),
    ("1 2 3 1", "1 2 4 1", "indices"),
])
def test_topology_identity_and_coverage_fail_closed(request_doc, old, new, message):
    _change(request_doc["ligand_itp"], lambda value: value.replace(old, new))
    with pytest.raises(parser.PreparedGromacsInputError, match=message):
        parser.load_prepared_gromacs_components(request_doc)


@pytest.mark.parametrize("extra", [
    "[ virtual_sites2 ]\n1 2 3 1 .5\n", "[ nonbond_params ]\nCL HL 1 1 1\n",
    "[ constraints ]\n1 2 1 .1\n", "#define POSRES\n", "#ifdef SOMETHING\n#endif\n",
    "#include \"other.itp\"\n", "#ifdef POSRES\n#else\n#endif\n", "#ifdef POSRES\n",
])
def test_unknown_active_topology_or_preprocessor_rejects(request_doc, extra):
    _change(request_doc["ligand_itp"], lambda value: value + extra)
    with pytest.raises(parser.PreparedGromacsInputError):
        parser.load_prepared_gromacs_components(request_doc)


def test_same_element_coordinate_permutation_is_detected(request_doc):
    def swap(value):
        lines = value.splitlines()
        lines[2], lines[3] = lines[2][:20] + lines[3][20:], lines[3][:20] + lines[2][20:]
        return "\n".join(lines) + "\n"
    _change(request_doc["ligand_gro"], swap)
    with pytest.raises(parser.PreparedGromacsInputError, match="same-index"):
        parser.load_prepared_gromacs_components(request_doc)


def test_same_coordinate_wrong_element_rejects(request_doc):
    _change(request_doc["ligand_sdf"], lambda value: value.replace(" C   0", " N   0", 1))
    with pytest.raises(parser.PreparedGromacsInputError, match="element"):
        parser.load_prepared_gromacs_components(request_doc)


@pytest.mark.parametrize("key", ["protein_defaults", "ligand_defaults"])
def test_non_lorentz_berthelot_defaults_reject(request_doc, key):
    _change(request_doc[key], lambda value: value.replace("1 2 ", "1 3 "))
    with pytest.raises(parser.PreparedGromacsInputError, match="combination rule 2"):
        parser.load_prepared_gromacs_components(request_doc)


@pytest.mark.parametrize(("old", "new", "message"), [
    ("0.340000 0.420000", "-0.340000 0.420000", "negative"),
    ("0.340000 0.420000", "0.340000 nan", "finite"),
    ("0.340000 0.420000", "0.340000", "row width"),
    ("0.340000 0.420000", "0.440000 0.420000", "printing precision"),
    ("CL 12.01", "HL 12.01", "duplicate atomtype"),
])
def test_atomtype_tables_never_fill_missing_parameters(request_doc, old, new, message):
    _change(request_doc["ligand_atomtypes"], lambda value: value.replace(old, new))
    with pytest.raises(parser.PreparedGromacsInputError, match=message):
        parser.load_prepared_gromacs_components(request_doc)


def test_unknown_request_keys_reject(request_doc):
    request_doc["guess_hydrogens"] = True
    with pytest.raises(parser.PreparedGromacsInputError, match="exact keys"):
        parser.load_prepared_gromacs_components(request_doc)


def test_explicit_protein_chain_coverage_required(request_doc):
    request_doc["protein_chains"] = request_doc["protein_chains"][:1]
    with pytest.raises(parser.PreparedGromacsInputError, match="chain order and coverage"):
        parser.load_prepared_gromacs_components(request_doc)


def test_name_convention_must_be_explicit(request_doc):
    request_doc["naming_convention"] = "exact"
    with pytest.raises(parser.PreparedGromacsInputError, match="name/order"):
        parser.load_prepared_gromacs_components(request_doc)


def test_inconsistent_declared_ligand_residue_rejects(request_doc):
    request_doc["ligand_residue_name_mapping"]["gro"] = "OTHER"
    with pytest.raises(parser.PreparedGromacsInputError, match="residue alias"):
        parser.load_prepared_gromacs_components(request_doc)


def test_blank_state_declaration_rejects(request_doc):
    request_doc["source_declarations"]["prepared_state_id"] = " "
    with pytest.raises(parser.PreparedGromacsInputError, match="nonblank"):
        parser.load_prepared_gromacs_components(request_doc)


def test_multiple_sdf_records_reject(request_doc):
    _change(request_doc["ligand_sdf"], lambda value: value + value)
    with pytest.raises(parser.PreparedGromacsInputError, match="one mol block"):
        parser.load_prepared_gromacs_components(request_doc)


def test_postflight_detects_mutated_original_source(request_doc, monkeypatch):
    original = parser._bound_system
    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        path = Path(request_doc["protein_pdb"]["path"])
        path.write_bytes(path.read_bytes() + b"REMARK changed\n")
        return result
    monkeypatch.setattr(parser, "_bound_system", mutate)
    with pytest.raises(parser.PreparedGromacsInputError, match="changed during parsing"):
        parser.load_prepared_gromacs_components(request_doc)


def test_input_request_remains_unchanged(request_doc):
    before = copy.deepcopy(request_doc)
    parser.load_prepared_gromacs_components(request_doc)
    assert request_doc == before


def _blank_first_element(value):
    lines = value.splitlines(keepends=True)
    lines[0] = lines[0][:76] + "  " + lines[0][78:]
    return "".join(lines)


def test_missing_pdb_element_rejects_without_opt_in(request_doc):
    _change(request_doc["protein_pdb"], _blank_first_element)
    with pytest.raises(ValueError, match="element"):
        parser.load_prepared_gromacs_components(request_doc)


def test_explicit_source_element_transfer_preserves_original(request_doc):
    _change(request_doc["protein_pdb"], _blank_first_element)
    before = Path(request_doc["protein_pdb"]["path"]).read_bytes()
    request_doc["pdb_element_policy"] = "pdb_blank_element_from_matching_topology_atomic_number"
    receptor, _, _, _, provenance = parser.load_prepared_gromacs_components(request_doc)
    assert Path(request_doc["protein_pdb"]["path"]).read_bytes() == before
    assert receptor.atoms[0].element == "H"
    assert receptor.coordinates[0, 0].tolist() == [0., 0., 0.]
    projection = provenance["pdb_element_projection"]
    assert projection["original_sha256"] == hashlib.sha256(before).hexdigest()
    assert projection["original_sha256"] != projection["projected_sha256"]
    assert projection["transferred_from_explicit_source"] and not projection["element_inferred"]
    assert len(projection["transfers"]) == 1
    assert projection["transfers"][0]["original_element_annotation"] == ""
    assert projection["transfers"][0]["atomic_number"] == 1


def test_explicit_element_transfer_requires_matching_name(request_doc):
    _change(request_doc["protein_pdb"], _blank_first_element)
    request_doc["pdb_element_policy"] = "pdb_blank_element_from_matching_topology_atomic_number"
    _change(request_doc["protein_chains"][0]["molecule_itp"], lambda value: value.replace("H11", "H99"))
    with pytest.raises(parser.PreparedGromacsInputError, match="name/order"):
        parser.load_prepared_gromacs_components(request_doc)


def test_element_transfer_never_overrides_nonblank_annotation(request_doc):
    request_doc["pdb_element_policy"] = "pdb_blank_element_from_matching_topology_atomic_number"
    _change(request_doc["protein_pdb"], lambda value: value.replace("           H", "           N", 1))
    with pytest.raises(parser.PreparedGromacsInputError, match="nonblank PDB element"):
        parser.load_prepared_gromacs_components(request_doc)


def test_malformed_atomtype_mapping_is_a_contract_error(request_doc):
    request_doc["ligand_atomtype_name_mapping"]["CL"] = []
    with pytest.raises(parser.PreparedGromacsInputError, match="nonblank string"):
        parser.load_prepared_gromacs_components(request_doc)


def test_unit_conversion_overflow_rejects(request_doc):
    _change(request_doc["protein_atomtypes"], lambda value: value.replace("0.34 0.42", "1e308 0.42"))
    with pytest.raises(parser.PreparedGromacsInputError, match="converted parameter"):
        parser.load_prepared_gromacs_components(request_doc)


def test_chain_itp_source_hash_is_required(request_doc):
    request_doc["protein_chains"][1]["molecule_itp"]["sha256"] = "0" * 64
    with pytest.raises(parser.PreparedGromacsInputError, match="SHA-256 mismatch"):
        parser.load_prepared_gromacs_components(request_doc)


@pytest.mark.parametrize(("offset_nm", "accepted"), [(0.001, True), (0.00101, False)])
def test_gro_rounding_tolerance_is_bounded(request_doc, offset_nm, accepted):
    def shifted(value):
        lines = value.splitlines()
        tokens = lines[2][20:].split()
        tokens[0] = str(float(tokens[0]) + offset_nm)
        lines[2] = lines[2][:20] + " ".join(tokens)
        return "\n".join(lines) + "\n"
    _change(request_doc["ligand_gro"], shifted)
    if accepted:
        *_, provenance = parser.load_prepared_gromacs_components(request_doc)
        assert provenance["gro_sdf_max_same_index_coordinate_difference_angstrom"] == pytest.approx(.01)
    else:
        with pytest.raises(parser.PreparedGromacsInputError, match="0.01 angstrom"):
            parser.load_prepared_gromacs_components(request_doc)


def test_unknown_defaults_include_is_never_silently_skipped(request_doc):
    _change(request_doc["protein_defaults"], lambda value: value + '#include "custom_nonbonded.itp"\n')
    with pytest.raises(parser.PreparedGromacsInputError, match="unsupported preprocessor"):
        parser.load_prepared_gromacs_components(request_doc)


@pytest.mark.parametrize("header", [">  <source_identity>  (1) ", ">  <chiral flag>  (1) "])
def test_published_sdf_inert_header_variants_preserved(request_doc, header):
    _change(request_doc["ligand_sdf"], lambda value: value.replace("> <source_identity>", header))
    _, ligand, _, _, provenance = parser.load_prepared_gromacs_components(request_doc)
    assert ligand.atom_count == 3
    projection = provenance["sdf_data_field_projection"]
    assert header in projection["source_data_tail"]
    assert list(projection["data_fields"].values()) == [["synthetic-001"]]
    assert not projection["data_fields_interpreted_as_chemistry"]


def test_sdf_metadata_cannot_declare_a_second_record(request_doc):
    _change(request_doc["ligand_sdf"], lambda value: value.replace("> <source_identity>", "> <source_identity> (2)"))
    with pytest.raises(parser.PreparedGromacsInputError, match="data header"):
        parser.load_prepared_gromacs_components(request_doc)
