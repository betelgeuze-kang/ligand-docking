from __future__ import annotations

from pathlib import Path

from betelgeuze_product.structure_analysis import analyze_structure_source


PDB_TEXT = """\
ATOM      1  N   GLY A   1      11.104  13.207  14.321  1.00 10.00           N
ATOM      2  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C
ATOM      3  C   GLY A   1      12.904  14.207  14.321  1.00 10.00           C
HETATM    4  O   HOH A 101      15.104  16.207  17.321  1.00 10.00           O
HETATM    5  C1  LIG B 201      18.104  19.207  20.321  1.00 10.00           C
HETATM    6  O1  LIG B 201      18.804  19.907  20.921  1.00 10.00           O
"""


MMCIF_TEXT = """\
loop_
_atom_site.group_PDB
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_seq_id
ATOM C CA ALA A 1
HETATM C C1 DRG B 5
#
"""


def test_analyze_structure_source_summarizes_pdb_content_without_execution() -> None:
    payload = analyze_structure_source({"pdb_content": PDB_TEXT})

    assert payload["status"] == "structure_analysis_ready"
    assert payload["parser"] == "pdb"
    assert payload["atom_count"] == 6
    assert payload["chain_count"] == 2
    assert payload["polymer_residue_count"] == 1
    assert payload["water_residue_count"] == 1
    assert payload["ligand_like_residue_count"] == 1
    assert payload["ligand_like_residues"] == [{"chain_id": "B", "resname": "LIG", "residue_id": "201"}]
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False


def test_analyze_structure_source_reads_local_mmcif_file(tmp_path: Path) -> None:
    path = tmp_path / "target.cif"
    path.write_text(MMCIF_TEXT, encoding="utf-8")

    payload = analyze_structure_source({"mmcif_path": str(path)})

    assert payload["status"] == "structure_analysis_ready"
    assert payload["parser"] == "mmcif"
    assert payload["atom_count"] == 2
    assert payload["ligand_like_residue_count"] == 1


def test_analyze_structure_source_records_pdb_id_without_fetching() -> None:
    payload = analyze_structure_source({"pdb_id": "2RH1"})

    assert payload["status"] == "structure_reference_recorded"
    assert payload["source_kind"] == "pdb_id"
    assert payload["source_available"] is False
    assert payload["atom_count"] == 0
    assert payload["external_state_mutated"] is False


def test_analyze_structure_source_blocks_missing_file() -> None:
    payload = analyze_structure_source({"pdb_path": "missing.pdb"})

    assert payload["status"] == "blocked_structure_analysis"
    assert payload["blocker_count"] == 1
    assert payload["blockers"][0]["code"] == "structure_file_missing"
