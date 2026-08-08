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
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    canonical_system_json_bytes,
    canonical_system_sha256,
)
from betelgeuze_engine_v2.standalone_cli import (  # noqa: E402
    LIGAND_MANIFEST_SCHEMA_ID,
    StandaloneDockCliError,
    define_explicit_pocket,
    dock,
    prepare_ligands,
    prepare_receptor,
    report_pipeline_result,
    verify_pipeline_result,
)


def _provenance(name: str, digest: str) -> StructureProvenance:
    return StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="standalone-cli-fixture",
        parser_version="1.0.0",
    )


def _system(*, receptor: bool) -> AllAtomSystem:
    elements = ("O", "N", "H", "C", "H") if receptor else ("C", "N", "H", "O", "H")
    charges = (-0.4, -0.2, 0.2, 0.0, 0.4) if receptor else (0.0, -0.2, 0.2, -0.4, 0.4)
    coordinates = (
        ([2.0, 0.0, 0.0], [3.0, 3.0, 0.0], [2.5, 2.5, 0.0], [-2.0, 3.0, 0.0], [6.0, 6.0, 0.0])
        if receptor
        else ([-2.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [-2.0, 0.0, 0.0], [-3.0, 0.0, 0.0])
    )
    role = "receptor" if receptor else "ligand"
    return AllAtomSystem(
        system_id=f"standalone-cli-{role}",
        atoms=tuple(
            Atom(
                index=index,
                name=f"{role[0].upper()}{index}",
                element=element,
                atomic_number={"C": 6, "N": 7, "H": 1, "O": 8}[element],
                residue_index=0,
                partial_charge_e=charges[index],
            )
            for index, element in enumerate(elements)
        ),
        bonds=(Bond(index=0, atom_i=1, atom_j=2),)
        if receptor
        else (
            Bond(index=0, atom_i=0, atom_j=1),
            Bond(index=1, atom_i=1, atom_j=2),
            Bond(index=2, atom_i=0, atom_j=3),
            Bond(index=3, atom_i=3, atom_j=4),
        ),
        residues=(
            Residue(
                index=0,
                name="REC" if receptor else "LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(5)),
                entity_type="polymer" if receptor else "non-polymer",
                hetero=not receptor,
            ),
        ),
        chains=(Chain(index=0, chain_id="A" if receptor else "L", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance(role, ("b" if receptor else "a") * 64),
    )


def _write_system(path: Path, system: AllAtomSystem) -> None:
    path.write_bytes(canonical_system_json_bytes(system) + b"\n")


def _write_document(path: Path, document: dict[str, object]) -> None:
    path.write_text(
        json.dumps(document, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="ascii",
    )


def test_prepare_commands_only_admit_canonical_prepared_systems(tmp_path: Path) -> None:
    receptor = _system(receptor=True)
    ligand = _system(receptor=False)
    receptor_input = tmp_path / "receptor.json"
    ligand_input = tmp_path / "ligand.json"
    _write_system(receptor_input, receptor)
    _write_system(ligand_input, ligand)

    receipt = prepare_receptor(receptor_input, tmp_path / "prepared-receptor.json")
    manifest = prepare_ligands(
        [ligand_input],
        tmp_path / "ligands",
        tmp_path / "ligands" / "manifest.json",
    )

    assert receipt["system_sha256"] == canonical_system_sha256(receptor)
    assert manifest["schema_id"] == LIGAND_MANIFEST_SCHEMA_ID
    assert manifest["system_count"] == 1
    assert manifest["chemistry_inference_performed"] is False
    assert (tmp_path / "ligands" / f"{canonical_system_sha256(ligand)}.json").is_file()


def test_synthetic_cli_flow_is_verifiable_reportable_and_claim_blocked(tmp_path: Path) -> None:
    receptor_path = tmp_path / "receptor.json"
    ligand_path = tmp_path / "ligand.json"
    _write_system(receptor_path, _system(receptor=True))
    _write_system(ligand_path, _system(receptor=False))
    pocket = define_explicit_pocket(
        center_angstrom=(0.0, 0.0, 0.0),
        radius_angstrom=10.0,
        coordinate_frame_id="prepared-receptor-frame-v1",
        source_artifact=receptor_path,
    )
    pocket_path = tmp_path / "pocket.json"
    _write_document(pocket_path, pocket)

    result = dock(
        receptor_path=receptor_path,
        ligand_path=ligand_path,
        pocket_path=pocket_path,
        seed=4301,
        synthetic_candidate_count=2,
        synthetic_top_k=1,
        synthetic_acknowledged=True,
    )
    verification = verify_pipeline_result(result)
    report = report_pipeline_result(result)

    assert verification["valid"] is True
    assert verification["claim_safe"] is False
    assert result["candidate_count"] == 2
    assert result["external_reservation_requested"] is False
    assert result["product_execution_authorized"] is False
    assert report["customer_pose_emission_authorized"] is False
    assert report["public_or_scientific_claim_authorized"] is False


def test_small_denominator_requires_explicit_synthetic_acknowledgement(tmp_path: Path) -> None:
    receptor_path = tmp_path / "receptor.json"
    ligand_path = tmp_path / "ligand.json"
    _write_system(receptor_path, _system(receptor=True))
    _write_system(ligand_path, _system(receptor=False))
    pocket = define_explicit_pocket(
        center_angstrom=(0.0, 0.0, 0.0),
        radius_angstrom=10.0,
        coordinate_frame_id="prepared-receptor-frame-v1",
        source_artifact=receptor_path,
    )
    pocket_path = tmp_path / "pocket.json"
    _write_document(pocket_path, pocket)

    with pytest.raises(StandaloneDockCliError, match="--test-only-synthetic"):
        dock(
            receptor_path=receptor_path,
            ligand_path=ligand_path,
            pocket_path=pocket_path,
            seed=4301,
            synthetic_candidate_count=2,
        )


def test_verifier_rejects_authority_escalation(tmp_path: Path) -> None:
    receptor_path = tmp_path / "receptor.json"
    ligand_path = tmp_path / "ligand.json"
    _write_system(receptor_path, _system(receptor=True))
    _write_system(ligand_path, _system(receptor=False))
    pocket = define_explicit_pocket(
        center_angstrom=(0.0, 0.0, 0.0),
        radius_angstrom=10.0,
        coordinate_frame_id="prepared-receptor-frame-v1",
        source_artifact=receptor_path,
    )
    pocket_path = tmp_path / "pocket.json"
    _write_document(pocket_path, pocket)
    result = dock(
        receptor_path=receptor_path,
        ligand_path=ligand_path,
        pocket_path=pocket_path,
        seed=7,
        synthetic_candidate_count=1,
        synthetic_top_k=1,
        synthetic_acknowledged=True,
    )
    result["product_execution_authorized"] = True

    with pytest.raises(StandaloneDockCliError, match="receipt_sha256 mismatch"):
        verify_pipeline_result(result)
