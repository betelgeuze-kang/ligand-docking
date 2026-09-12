"""Synthetic source-integrity checks; no energies, preparation or solver runs."""

from __future__ import annotations

import copy
import hashlib
import json
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


def _ordered_molecule_request(request_doc, chain_id=""):
    refs = [entry["molecule_itp"] for entry in request_doc["protein_chains"]]
    _change(refs[1], lambda text: text.replace("1 N 1 SYN", "1 N 2 SYN"))

    def project(text):
        lines = []
        for line in text.splitlines(keepends=True):
            if line.startswith("ATOM  "):
                residue = 2 if int(line[6:11]) == 4 else 1
                line = line[:21] + (chain_id or " ") + f"{residue:4d}" + line[26:]
            lines.append(line)
        return "".join(lines)

    _change(request_doc["protein_pdb"], project)
    request_doc["schema_version"] = "prepared_gromacs_components_v2"
    request_doc["protein_chains"] = [{"chain_id": chain_id, "molecule_itps": refs}]
    return request_doc


def _ordered_bonded_molecules(request_doc, chain_id=""):
    request = _ordered_molecule_request(request_doc, chain_id)
    second = request["protein_chains"][0]["molecule_itps"][1]
    _change(second, lambda text: text + "2 H 2 SYN H2 2 0.125 1.008\n[ bonds ]\n1 2 1\n")
    atom = _pdb_atom(5, "H2", "H", chain_id or " ", 5.)
    atom = atom[:22] + f"{2:4d}" + atom[26:]
    _change(request["protein_pdb"], lambda text: text.replace("END\n", atom + "END\n"))
    return request


@pytest.mark.parametrize("chain_id", ["", "A"])
def test_v2_ordered_molecules_preserve_original_atoms_and_source_indices(request_doc, chain_id):
    request = _ordered_bonded_molecules(request_doc, chain_id)
    before = copy.deepcopy(request)
    raw_pdb = Path(request["protein_pdb"]["path"]).read_bytes()
    receptor, _, params, _, evidence = parser.load_prepared_gromacs_components(request)
    assert request == before and Path(request["protein_pdb"]["path"]).read_bytes() == raw_pdb
    assert [chain.chain_id for chain in receptor.chains] == [chain_id]
    assert receptor.atom_count == 5
    assert receptor.coordinates.tolist() == [[[0., 0., 0.], [1., 0., 0.], [2., 0., 0.], [4., 0., 0.], [5., 0., 0.]]]
    assert [row["charge_e"] for row in params] == [0., .25, -.25, -0., .125]
    origins = [atom.metadata["prepared_gromacs_source"] for atom in receptor.atoms]
    assert [row["source_atom_index"] for row in origins] == [1, 2, 3, 1, 2]
    assert [row["chain_molecule_index"] for row in origins] == [0, 0, 0, 1, 1]
    assert origins[0]["source_molecule_label"] != origins[3]["source_molecule_label"]
    assert all(row["source_molecule_label"] in evidence["sources"] for row in origins)
    assert evidence["receptor_source_bond_adjacency"] == [[0, 1], [1, 2], [3, 4]]
    assert evidence["schema_version"] == "prepared_gromacs_components_v2"
    assert not evidence["coordinates_generated"] and not any(evidence["claim_policy"].values())


def test_v2_blank_element_transfer_resolves_original_molecule_source(request_doc):
    request = _ordered_bonded_molecules(request_doc)
    request["pdb_element_policy"] = "pdb_blank_element_from_matching_topology_atomic_number"
    _change(request["protein_pdb"], lambda text: "".join(
        line[:76] + "  " + line[78:] if line.startswith("ATOM  ") else line
        for line in text.splitlines(keepends=True)))
    receptor, _, _, _, evidence = parser.load_prepared_gromacs_components(request)
    transfers = evidence["pdb_element_projection"]["transfers"]
    assert len(transfers) == 5
    for transfer, atom in zip(transfers, receptor.atoms):
        origin = atom.metadata["prepared_gromacs_source"]
        assert transfer["molecule_source"] in evidence["sources"]
        assert transfer["molecule_source"] in evidence["original_topologies"]
        assert transfer["molecule_source"] == origin["source_molecule_label"]
        assert transfer["source_atom_index"] == origin["source_atom_index"]


@pytest.mark.parametrize("bad_chain", [" ", "AA", None, 0])
def test_v2_chain_field_cannot_invent_or_normalize_a_pdb_identifier(request_doc, bad_chain):
    request = _ordered_molecule_request(request_doc)
    request["protein_chains"][0]["chain_id"] = bad_chain
    with pytest.raises(parser.PreparedGromacsInputError, match="exact PDB character"):
        parser.load_prepared_gromacs_components(request)


@pytest.mark.parametrize("change,match", [
    ("empty", "ordered protein molecule"),
    ("reverse", "residue identity mismatch"),
    ("omit", "atom count mismatch"),
    ("repeat", "atom count mismatch"),
    ("stale", "SHA-256 mismatch"),
])
def test_v2_ordered_molecule_sources_require_exact_complete_binding(request_doc, change, match):
    request = _ordered_molecule_request(request_doc)
    refs = request["protein_chains"][0]["molecule_itps"]
    if change == "empty":
        refs.clear()
    elif change == "reverse":
        refs.reverse()
    elif change == "omit":
        refs.pop()
    elif change == "repeat":
        refs.append(copy.deepcopy(refs[0]))
    else:
        refs[1]["sha256"] = "0" * 64
    with pytest.raises(parser.PreparedGromacsInputError, match=match):
        parser.load_prepared_gromacs_components(request)


def test_v1_still_requires_single_nonblank_chain_molecule(request_doc):
    request_doc["protein_chains"][0]["chain_id"] = ""
    with pytest.raises(parser.PreparedGromacsInputError, match="nonblank string"):
        parser.load_prepared_gromacs_components(request_doc)


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


# Captured from the exact parent synthetic reader, with only temporary source paths
# normalized to filenames for the evidence hash. No physical result is involved.
_LEGACY_HASHES = {'v1': {'ligand_sha256': '25ceffb61e2f4f6a2d082857e9854bc97459e02200ada0dc18bdde14b915bf41', 'lparams_sha256': '47fb12fba5f5242891acb4a50b9658c4bdc13f551841ee19342eb3056819347d', 'normalized_provenance_sha256': 'cd93021607d9c80f6ea5038a45033d980ecd6c4d047b5cb46c89753585051a54', 'receptor_sha256': '3daf09cf7efbc6b5a04e1c46381036f74e5b6c64d4ede9b372d51e02031deb0d', 'rparams_sha256': '97cc50485e59db0920a655d164be9ccb7adb5e658099463519d31fb0e05ee77c'}, 'v2_A': {'ligand_sha256': '130568cdef74933d4068dc514bac38905e23b498d41726575a12ccb3b900e17b', 'lparams_sha256': '47fb12fba5f5242891acb4a50b9658c4bdc13f551841ee19342eb3056819347d', 'normalized_provenance_sha256': 'af5fec38ac62465fa0bbd3f3478885058cf5d69745d0e1d197b48be2841257d4', 'receptor_sha256': '68b64152a9230407e7d99e7614599031ef453e06d77cd02ca6101205efa6b5a5', 'rparams_sha256': 'c596b3414b35cddd183316a8660709a81427c40326d515a465089dbcd24eedd4'}, 'v2_blank': {'ligand_sha256': '80c5980514a399d228551adb8afba3d8c7ae203b838c86bc1078175d73dc51fb', 'lparams_sha256': '47fb12fba5f5242891acb4a50b9658c4bdc13f551841ee19342eb3056819347d', 'normalized_provenance_sha256': 'b78ef03e115fa76377b96ba7d887688f44e42001924393f1afcb87a8fd3f8160', 'receptor_sha256': 'b2cc41481417b18f7b3d4f64c85e6b17e8ef96deae3d5a5a000d95fb4508307a', 'rparams_sha256': 'c596b3414b35cddd183316a8660709a81427c40326d515a465089dbcd24eedd4'}}


def _json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@pytest.mark.parametrize("version", ["v1", "v2_blank", "v2_A"])
def test_legacy_reader_canonical_and_evidence_hashes_unchanged(request_doc, version):
    request = request_doc if version == "v1" else _ordered_bonded_molecules(request_doc, "" if version == "v2_blank" else "A")
    receptor, ligand, rparams, lparams, evidence = parser.load_prepared_gromacs_components(request)
    normalized = copy.deepcopy(evidence)
    for source in normalized["sources"].values():
        source["path"] = Path(source["path"]).name
    actual = {
        "receptor_sha256": parser.canonical_system_sha256(receptor),
        "ligand_sha256": parser.canonical_system_sha256(ligand),
        "rparams_sha256": _json_hash(rparams),
        "lparams_sha256": _json_hash(lparams),
        "normalized_provenance_sha256": _json_hash(normalized),
    }
    assert actual == _LEGACY_HASHES[version]
    assert "protein_residue_identifier_policy" not in evidence
    assert all("insertion_code" not in atom.metadata["prepared_gromacs_source"]
               and "residue_number_token" not in atom.metadata["prepared_gromacs_source"] for atom in receptor.atoms)


def _insertion_request(request_doc, chain_id="", suffix="A"):
    request = _ordered_bonded_molecules(request_doc, chain_id)
    second = request["protein_chains"][0]["molecule_itps"][1]
    _change(second, lambda text: text.replace("1 N 2 SYN N", f"1 N 1{suffix} NME N")
            .replace("2 H 2 SYN H2", f"2 H 1{suffix} NME H11"))

    def project(text):
        lines = []
        for line in text.splitlines(keepends=True):
            if line.startswith("ATOM  ") and int(line[6:11]) in (4, 5):
                name = "N" if int(line[6:11]) == 4 else "1H1"
                line = line[:12] + f"{name:>4s}" + line[16:17] + "NME" + line[20:22] + f"{1:4d}" + suffix + line[27:]
            lines.append(line)
        return "".join(lines)

    _change(request["protein_pdb"], project)
    request["schema_version"] = "prepared_gromacs_components_v3"
    return request


@pytest.mark.parametrize("schema", ["prepared_gromacs_components_v1", "prepared_gromacs_components_v2"])
def test_legacy_schemas_still_reject_noninteger_residue_tokens(request_doc, schema):
    request = _insertion_request(request_doc, "A")
    request["schema_version"] = schema
    if schema.endswith("v1"):
        # One topology still carries the insertion token, without any v2 request key.
        first, second = request["protein_chains"][0]["molecule_itps"]
        _change(first, lambda text: Path(second["path"]).read_text())
        request["protein_chains"] = [{"chain_id": "A", "molecule_itp": first}]
    with pytest.raises(parser.PreparedGromacsInputError, match="integer required"):
        parser.load_prepared_gromacs_components(request)


@pytest.mark.parametrize("chain_id", ["", "A"])
@pytest.mark.parametrize("suffix", ["A", "z"])
def test_v3_distinct_insertion_residue_preserves_all_source_state(request_doc, chain_id, suffix):
    request = _insertion_request(request_doc, chain_id, suffix)
    before = copy.deepcopy(request)
    raw_sources = {ref["path"]: Path(ref["path"]).read_bytes() for ref in request["protein_chains"][0]["molecule_itps"]}
    pdb_before = Path(request["protein_pdb"]["path"]).read_bytes()
    receptor, ligand, rparams, _, evidence = parser.load_prepared_gromacs_components(request)
    assert request == before and Path(request["protein_pdb"]["path"]).read_bytes() == pdb_before
    assert all(Path(path).read_bytes() == raw for path, raw in raw_sources.items())
    assert [(r.sequence_number, r.insertion_code, r.name) for r in receptor.residues] == [(1, "", "SYN"), (1, suffix, "NME")]
    assert [atom.name for atom in receptor.atoms] == ["1H1", "C", "O", "N", "1H1"]
    assert receptor.coordinates.tolist() == [[[0., 0., 0.], [1., 0., 0.], [2., 0., 0.], [4., 0., 0.], [5., 0., 0.]]]
    assert [row["charge_e"] for row in rparams] == [0., .25, -.25, -0., .125]
    assert rparams[0]["sigma_angstrom"] == rparams[0]["epsilon_kcal_per_mol"] == 0.
    origins = [atom.metadata["prepared_gromacs_source"] for atom in receptor.atoms]
    assert [x["residue_number_token"] for x in origins] == ["1"] * 3 + ["1" + suffix] * 2
    assert [x["insertion_code"] for x in origins] == [""] * 3 + [suffix] * 2
    assert [x["source_atom_index"] for x in origins] == [1, 2, 3, 1, 2]
    assert [x["chain_molecule_index"] for x in origins] == [0, 0, 0, 1, 1]
    assert all(x["source_molecule_label"] in evidence["original_topologies"] for x in origins)
    assert evidence["receptor_source_bond_adjacency"] == [[0, 1], [1, 2], [3, 4]]
    assert ligand.atom_count == 3 and receptor.cell is ligand.cell is None
    assert evidence["protein_residue_identifier_policy"]["noninteger_tokens_claimed_standard_gromacs"] is False
    assert evidence["protein_residue_identifier_policy"]["residue_renumbering_performed"] is False
    assert evidence["source_hashes_postflight_verified"] and not evidence["coordinates_generated"]
    assert not any(evidence["claim_policy"].values())


def test_v3_blank_element_projection_requires_and_preserves_insertion_identity(request_doc):
    request = _insertion_request(request_doc)
    request["pdb_element_policy"] = "pdb_blank_element_from_matching_topology_atomic_number"
    _change(request["protein_pdb"], lambda text: "".join(line[:76] + "  " + line[78:] if line.startswith("ATOM  ") else line for line in text.splitlines(keepends=True)))
    receptor, _, _, _, evidence = parser.load_prepared_gromacs_components(request)
    assert receptor.residues[1].insertion_code == "A"
    assert len(evidence["pdb_element_projection"]["transfers"]) == 5
    assert evidence["pdb_element_projection"]["coordinate_bytes_unchanged"]
    assert all(row["molecule_source"] in evidence["original_topologies"] for row in evidence["pdb_element_projection"]["transfers"])


@pytest.mark.parametrize("policy", ["reject_missing", "pdb_blank_element_from_matching_topology_atomic_number"])
@pytest.mark.parametrize("change", ["drop_itp", "drop_pdb", "wrong_suffix", "wrong_case", "wrong_number", "wrong_residue"])
def test_v3_insertion_tuple_mismatch_rejects_in_both_binding_paths(request_doc, policy, change):
    request = _insertion_request(request_doc)
    request["pdb_element_policy"] = policy
    second = request["protein_chains"][0]["molecule_itps"][1]
    replacement = {"drop_itp": "1", "wrong_suffix": "1B", "wrong_case": "1a", "wrong_number": "2A"}
    if change in replacement:
        _change(second, lambda text: text.replace(" 1A NME ", " " + replacement[change] + " NME "))
    elif change == "wrong_residue":
        _change(second, lambda text: text.replace(" NME ", " CAP "))
    else:
        _change(request["protein_pdb"], lambda text: "".join(line[:26] + " " + line[27:] if line.startswith("ATOM  ") and int(line[6:11]) in (4, 5) else line for line in text.splitlines(keepends=True)))
    with pytest.raises(parser.PreparedGromacsInputError, match="residue identity"):
        parser.load_prepared_gromacs_components(request)


@pytest.mark.parametrize("token", ["0A", "-1A", "+1A", "1AA", "1.0A", "1_A", "A1", "1é", "1:"])
def test_v3_protein_residue_token_grammar_is_narrow(request_doc, token):
    request = _insertion_request(request_doc)
    _change(request["protein_chains"][0]["molecule_itps"][1], lambda text: text.replace(" 1A NME ", " " + token + " NME "))
    with pytest.raises(parser.PreparedGromacsInputError, match="protein residue token"):
        parser.load_prepared_gromacs_components(request)


@pytest.mark.parametrize("field", ["ligand_itp", "ligand_gro", "protein_atom_index", "protein_charge_group", "protein_bond_index"])
def test_v3_insertion_support_does_not_relax_other_integer_fields(request_doc, field):
    request = _insertion_request(request_doc)
    if field == "ligand_itp":
        _change(request[field], lambda text: text.replace("CL 1 MOL", "CL 1A MOL"))
    elif field == "ligand_gro":
        _change(request[field], lambda text: "".join("   1A" + line[5:] if len(line) > 20 and line[:5].strip() == "1" else line for line in text.splitlines(keepends=True)))
    else:
        second = request["protein_chains"][0]["molecule_itps"][1]
        old, new = {"protein_atom_index": ("1 N 1A", "1A N 1A"), "protein_charge_group": ("NME N 1 ", "NME N 1A "), "protein_bond_index": ("1 2 1", "1A 2 1")}[field]
        _change(second, lambda text: text.replace(old, new))
    with pytest.raises(parser.PreparedGromacsInputError, match="integer required"):
        parser.load_prepared_gromacs_components(request)


def test_v3_same_tuple_cannot_have_conflicting_residue_names(request_doc):
    request = _insertion_request(request_doc)
    _change(request["protein_chains"][0]["molecule_itps"][1], lambda text: text.replace("1A NME H11", "1A CAP H11"))
    with pytest.raises(parser.PreparedGromacsInputError, match="inconsistent residue name"):
        parser.load_prepared_gromacs_components(request)


def test_v3_same_tuple_cannot_repeat_an_atom_name(request_doc):
    request = _insertion_request(request_doc)
    _change(request["protein_chains"][0]["molecule_itps"][1], lambda text: text.replace("1A NME H11", "1A NME N"))
    with pytest.raises(parser.PreparedGromacsInputError, match="duplicate atom name"):
        parser.load_prepared_gromacs_components(request)


def test_v3_same_residue_tuple_cannot_be_split_between_molecule_sources(request_doc):
    request = _ordered_molecule_request(request_doc)
    request["schema_version"] = "prepared_gromacs_components_v3"
    _change(request["protein_chains"][0]["molecule_itps"][1], lambda text: text.replace("1 N 2 SYN", "1 N 1 SYN"))
    with pytest.raises(parser.PreparedGromacsInputError, match="residue identity.*multiple molecule"):
        parser.load_prepared_gromacs_components(request)


@pytest.mark.parametrize("name", ["IC50[uM]", "assay Ki[nM]"])
def test_sdf_unit_extension_v3_preserves_inert_original_metadata(request_doc, name):
    request = _insertion_request(request_doc)
    header = f">  <{name}>  (1) "
    _change(request["ligand_sdf"], lambda text: text.replace("> <source_identity>", header))
    before = copy.deepcopy(request)
    raw = Path(request["ligand_sdf"]["path"]).read_bytes()
    mol_block = raw[:raw.index(b"M  END\n") + len(b"M  END\n")]
    _, ligand, _, _, evidence = parser.load_prepared_gromacs_components(request)
    projection = evidence["sdf_data_field_projection"]
    assert ligand.atom_count == 3 and request == before
    assert Path(request["ligand_sdf"]["path"]).read_bytes() == raw
    assert projection["source_data_tail"].encode() == raw[len(mol_block):]
    assert projection["data_fields"] == {name: ["synthetic-001"]}
    assert projection["original_sha256"] == hashlib.sha256(raw).hexdigest()
    assert projection["mol_block_sha256"] == hashlib.sha256(mol_block).hexdigest()
    assert projection["mol_block_bytes_unchanged"] is True
    assert projection["data_fields_interpreted_as_chemistry"] is False
    assert not any(evidence["claim_policy"].values())


def test_sdf_unit_extension_label_strings_do_not_change_kernel_inputs(request_doc):
    request = _insertion_request(request_doc)
    original = Path(request["ligand_sdf"]["path"]).read_bytes()
    mol_block = original[:original.index(b"M  END\n") + len(b"M  END\n")]
    outputs, raw_inputs = [], []
    for value in ("-1", "0", "error-1"):
        tail = f">  <IC50[uM]>  (1) \n{value}\n\n$$$$\n"
        _change(request["ligand_sdf"], lambda _, tail=tail: mol_block.decode() + tail)
        raw = Path(request["ligand_sdf"]["path"]).read_bytes()
        outputs.append(parser.load_prepared_gromacs_components(request))
        raw_inputs.append(raw)
        assert Path(request["ligand_sdf"]["path"]).read_bytes() == raw
        projection = outputs[-1][-1]["sdf_data_field_projection"]
        assert projection["data_fields"] == {"IC50[uM]": [value]}
        assert projection["source_data_tail"] == tail
        assert parser._sdf_projection(raw, bracketed_unit_headers=True)[0] == mol_block
    first_receptor, first_ligand, rparams, lparams, _ = outputs[0]
    for receptor, ligand, actual_rparams, actual_lparams, evidence in outputs[1:]:
        assert torch.equal(receptor.coordinates, first_receptor.coordinates)
        assert torch.equal(ligand.coordinates, first_ligand.coordinates)
        assert receptor.atoms == first_receptor.atoms and ligand.atoms == first_ligand.atoms
        assert receptor.bonds == first_receptor.bonds and ligand.bonds == first_ligand.bonds
        assert receptor.residues == first_receptor.residues and ligand.residues == first_ligand.residues
        assert actual_rparams == rparams and actual_lparams == lparams
        assert evidence["sdf_data_field_projection"]["mol_block_sha256"] == hashlib.sha256(mol_block).hexdigest()
    assert len({item[-1]["sdf_data_field_projection"]["original_sha256"] for item in outputs}) == 3
    assert len({item[-1]["sdf_data_field_projection"]["source_data_tail"] for item in outputs}) == 3
    assert [item[-1]["sources"]["ligand_sdf"]["sha256"] for item in outputs] == [hashlib.sha256(raw).hexdigest() for raw in raw_inputs]
    # Canonical hashes include changed source provenance; they are not falsely held fixed.
    assert len({item[-1]["ligand_system_sha256"] for item in outputs}) == 3


@pytest.mark.parametrize("schema", ["prepared_gromacs_components_v1", "prepared_gromacs_components_v2"])
def test_sdf_unit_extension_is_not_enabled_for_legacy_schemas(request_doc, schema):
    request = request_doc if schema.endswith("v1") else _ordered_molecule_request(request_doc)
    _change(request["ligand_sdf"], lambda text: text.replace("source_identity", "IC50[uM]"))
    with pytest.raises(parser.PreparedGromacsInputError, match="data header"):
        parser.load_prepared_gromacs_components(request)


def test_sdf_unit_extension_requires_explicit_projection_opt_in():
    raw = _sdf().replace("source_identity", "IC50[uM]").encode()
    with pytest.raises(parser.PreparedGromacsInputError, match="data header"):
        parser._sdf_projection(raw)


@pytest.mark.parametrize("name", [
    "IC50[]", "IC50[uM", "IC50uM]", "IC50[[uM]]", "IC50[uM][nM]",
    "[uM]", "IC50[u M]", "IC50[u\tM]", "IC50[u\x00M]", "IC50[u\x7fM]",
    "IC50[μM]", "IC50[1M]", "IC50[uM]suffix", " IC50[uM]", "IC50 [uM]",
])
def test_sdf_unit_extension_malformed_or_non_ascii_unit_rejects(request_doc, name):
    request = _ordered_molecule_request(request_doc)
    request["schema_version"] = "prepared_gromacs_components_v3"
    _change(request["ligand_sdf"], lambda text: text.replace("source_identity", name))
    with pytest.raises(parser.PreparedGromacsInputError, match="data header"):
        parser.load_prepared_gromacs_components(request)


@pytest.mark.parametrize("tail,match", [
    ("> <IC50[uM]>\nfirst\n\n> <IC50[uM]>\nsecond\n\n$$$$\n", "duplicate ligand SDF data field"),
    ("> <IC50[uM]>\nfirst\n\nunbound\n$$$$\n", "unbound ligand SDF metadata"),
    ("> <IC50[uM]>\nfirst\n\n$$$$\n> <other>\nsecond\n", "content after record terminator"),
    ("> <IC50[uM]> (2)\nfirst\n\n$$$$\n", "data header"),
])
def test_sdf_unit_extension_keeps_data_tail_guards(request_doc, tail, match):
    request = _ordered_molecule_request(request_doc)
    request["schema_version"] = "prepared_gromacs_components_v3"
    _change(request["ligand_sdf"], lambda text: text[:text.index("M  END\n") + len("M  END\n")] + tail)
    with pytest.raises(parser.PreparedGromacsInputError, match=match):
        parser.load_prepared_gromacs_components(request)


def test_sdf_unit_extension_keeps_multirecord_guard(request_doc):
    request = _ordered_molecule_request(request_doc)
    request["schema_version"] = "prepared_gromacs_components_v3"
    _change(request["ligand_sdf"], lambda text: text.replace("source_identity", "IC50[uM]") + text)
    with pytest.raises(parser.PreparedGromacsInputError, match="one mol block"):
        parser.load_prepared_gromacs_components(request)
