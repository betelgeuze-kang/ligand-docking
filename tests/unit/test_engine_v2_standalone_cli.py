from __future__ import annotations

import json
from pathlib import Path

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
)
from betelgeuze_engine_v2.io import pdb_string, sdf_v2000_string  # noqa: E402
from betelgeuze_engine_v2.standalone_cli import main  # noqa: E402


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="standalone-cli-fixture",
        parser_version="1.0.0",
    )


def _system(*, receptor: bool) -> AllAtomSystem:
    if receptor:
        elements = ("C", "N", "O", "C")
        coordinates = (
            (-3.0, 0.0, 0.0),
            (3.0, 0.0, 0.0),
            (0.0, 4.0, 0.0),
            (0.0, -4.0, 0.0),
        )
        bonds: tuple[Bond, ...] = ()
        residue_name = "REC"
        chain_id = "A"
        digest = "a" * 64
    else:
        elements = ("C", "N", "C", "O")
        coordinates = (
            (0.0, 0.0, 0.0),
            (1.4, 0.0, 0.0),
            (2.8, 0.3, 0.0),
            (4.1, 1.0, 0.2),
        )
        bonds = (
            Bond(index=0, atom_i=0, atom_j=1, order=1.0),
            Bond(index=1, atom_i=1, atom_j=2, order=1.0),
            Bond(index=2, atom_i=2, atom_j=3, order=1.0),
        )
        residue_name = "LIG"
        chain_id = "L"
        digest = "b" * 64
    atomic_numbers = {"C": 6, "N": 7, "O": 8}
    return AllAtomSystem(
        system_id="receptor" if receptor else "ligand",
        atoms=tuple(
            Atom(
                index=index,
                name=f"{element}{index + 1}",
                element=element,
                atomic_number=atomic_numbers[element],
                residue_index=0,
            )
            for index, element in enumerate(elements)
        ),
        bonds=bonds,
        residues=(
            Residue(
                index=0,
                name=residue_name,
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(elements))),
                hetero=not receptor,
                entity_type="non-polymer" if not receptor else "polymer",
            ),
        ),
        chains=(Chain(index=0, chain_id=chain_id, residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance(
            "standalone-receptor" if receptor else "standalone-ligand",
            digest,
        ),
    )


def test_standalone_cli_six_command_vertical_slice(tmp_path: Path) -> None:
    receptor_pdb = tmp_path / "receptor.pdb"
    ligand_sdf = tmp_path / "ligand.sdf"
    receptor_pdb.write_text(pdb_string(_system(receptor=True))[0], encoding="utf-8")
    ligand_sdf.write_text(
        sdf_v2000_string(_system(receptor=False))[0], encoding="utf-8"
    )
    receptor_json = tmp_path / "receptor.canonical.json"
    ligand_dir = tmp_path / "ligands"
    receptor_receipt = tmp_path / "receptor-receipt.json"
    ligand_receipt = tmp_path / "ligand-receipt.json"

    assert (
        main(
            [
                "prepare-receptor",
                "--input",
                str(receptor_pdb),
                "--output",
                str(receptor_json),
                "--receipt-output",
                str(receptor_receipt),
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "prepare-ligands",
                "--input",
                str(ligand_sdf),
                "--output-dir",
                str(ligand_dir),
                "--receipt-output",
                str(ligand_receipt),
            ]
        )
        == 0
    )
    ligand_json = ligand_dir / "0000-ligand.canonical.json"
    pocket_json = tmp_path / "pocket.json"
    assert (
        main(
            [
                "define-pocket",
                "--ligand",
                str(ligand_json),
                "--coordinate-frame-id",
                "prepared-receptor-frame-v1",
                "--output",
                str(pocket_json),
            ]
        )
        == 0
    )
    result_json = tmp_path / "result.json"
    assert (
        main(
            [
                "dock",
                "--receptor",
                str(receptor_json),
                "--ligand",
                str(ligand_json),
                "--pocket",
                str(pocket_json),
                "--candidate-count",
                "4",
                "--top-k",
                "2",
                "--max-torsions",
                "1",
                "--translation-radius-angstrom",
                "2.0",
                "--seed",
                "131",
                "--output",
                str(result_json),
            ]
        )
        == 0
    )
    verification_json = tmp_path / "verification.json"
    assert (
        main(
            [
                "verify",
                "--result",
                str(result_json),
                "--receptor",
                str(receptor_json),
                "--ligand",
                str(ligand_json),
                "--pocket",
                str(pocket_json),
                "--output",
                str(verification_json),
            ]
        )
        == 0
    )
    report_json = tmp_path / "report.json"
    assert (
        main(
            [
                "report",
                "--result",
                str(result_json),
                "--output",
                str(report_json),
            ]
        )
        == 0
    )

    result = json.loads(result_json.read_text(encoding="ascii"))
    verification = json.loads(verification_json.read_text(encoding="ascii"))
    report = json.loads(report_json.read_text(encoding="ascii"))
    assert result["pipeline_evidence"]["failure_complete"] is True
    assert result["pipeline_evidence"]["candidate_denominator_preserved"] is True
    assert verification["verification_kind"] == "input_bound_bundle"
    assert report["rendered_without_rescoring"] is True
    assert report["pose_coordinates_emitted"] is False
    assert report["customer_execution_enabled"] is False
    assert report["claim_safe"] is False


def test_engine_v2_wheel_declares_standalone_entrypoint() -> None:
    pyproject = Path("packaging/engine-v2/pyproject.toml").read_text(encoding="utf-8")

    assert 'betelgeuze-dock = "betelgeuze_engine_v2.standalone_cli:main"' in pyproject
