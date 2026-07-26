from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib
import importlib.util
import os
from pathlib import Path
import stat

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.molecular import (  # noqa: E402
    AllAtomSystem,
    Atom,
    Chain,
    OpenFFAdmission,
    Residue,
    RdkitOpenffPreparationConfig,
    RdkitOpenffPreparationError,
    StructureProvenance,
    all_atom_system_from_canonical_json,
    canonical_system_json_bytes,
    prepare_ligand_with_rdkit_openff,
    verify_rdkit_openff_prepared_system,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    rdkit_openff_preparation as preparation,
)
from betelgeuze_engine_v2.benchmark.redocking_cli import (  # noqa: E402
    RedockingDiagnosticConfig,
    run_prepared_redocking_diagnostic,
)


RDKIT_AVAILABLE = importlib.util.find_spec("rdkit") is not None
requires_rdkit = pytest.mark.skipif(
    not RDKIT_AVAILABLE,
    reason="RDKit is an optional chemistry capability",
)


class _UnavailableOpenFF:
    def admit(
        self,
        molecule: object,
        *,
        allow_undefined_stereo: bool,
        rdkit_modules: dict[str, object],
    ) -> OpenFFAdmission:
        del molecule, allow_undefined_stereo, rdkit_modules
        return OpenFFAdmission(
            status="unavailable",
            adapter_id="unit_test_unavailable/1.0.0",
            error_code="openff_toolkit_unavailable",
        )


class _MatchingOpenFF:
    def admit(
        self,
        molecule: object,
        *,
        allow_undefined_stereo: bool,
        rdkit_modules: dict[str, object],
    ) -> OpenFFAdmission:
        del allow_undefined_stereo
        chem = rdkit_modules["Chem"]
        heavy = chem.RemoveHs(chem.Mol(molecule), sanitize=True)
        smiles = chem.MolToSmiles(
            heavy,
            canonical=True,
            isomericSmiles=True,
        )
        return OpenFFAdmission(
            status="admitted",
            adapter_id="unit_test_matching_roundtrip/1.0.0",
            toolkit_distribution_name="openff-toolkit",
            toolkit_distribution_version="test",
            toolkit_version="test",
            input_atom_count=molecule.GetNumAtoms(),
            roundtrip_atom_count=molecule.GetNumAtoms(),
            input_bond_count=molecule.GetNumBonds(),
            roundtrip_bond_count=molecule.GetNumBonds(),
            roundtrip_canonical_smiles=smiles,
            graph_identity_match=True,
        )


class _MismatchingOpenFF(_MatchingOpenFF):
    def admit(
        self,
        molecule: object,
        *,
        allow_undefined_stereo: bool,
        rdkit_modules: dict[str, object],
    ) -> OpenFFAdmission:
        matching = super().admit(
            molecule,
            allow_undefined_stereo=allow_undefined_stereo,
            rdkit_modules=rdkit_modules,
        )
        return replace(matching, roundtrip_atom_count=matching.roundtrip_atom_count + 1)


def test_preparation_module_is_importable_when_rdkit_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import_module = importlib.import_module

    def missing_rdkit(name: str, package: str | None = None) -> object:
        if name == "rdkit":
            raise ModuleNotFoundError("synthetic missing RDKit")
        return real_import_module(name, package)

    monkeypatch.setattr(preparation, "import_module", missing_rdkit)
    with pytest.raises(
        RdkitOpenffPreparationError,
        match="RDKit runtime is unavailable",
    ):
        prepare_ligand_with_rdkit_openff("CC", source_format="smiles")


@requires_rdkit
def test_aromatic_ring_preparation_is_deterministic_and_canonical() -> None:
    first = prepare_ligand_with_rdkit_openff(
        "c1ccncc1",
        source_format="smiles",
        source_id="pyridine",
        openff_adapter=_UnavailableOpenFF(),
    )
    second = prepare_ligand_with_rdkit_openff(
        "c1ccncc1",
        source_format="smiles",
        source_id="pyridine",
        openff_adapter=_UnavailableOpenFF(),
    )

    assert canonical_system_json_bytes(first) == canonical_system_json_bytes(second)
    receipt = verify_rdkit_openff_prepared_system(first)
    assert receipt["chemistry"]["aromatic_atom_count"] == 6
    assert receipt["chemistry"]["aromatic_bond_count"] == 6
    assert receipt["chemistry"]["ring_count"] == 1
    assert receipt["chemistry"]["ring_sizes"] == (6,)
    assert receipt["chemistry"]["heavy_atom_count"] == 6
    assert receipt["coordinates"]["coordinate_generation_method"] == "rdkit_etkdgv3"
    assert receipt["runtime"]["openff"]["status"] == "unavailable"
    assert receipt["claims"]["chemistry_validated"] is False
    assert first.provenance.chemistry_validated is False
    assert all(atom.metadata["is_in_ring"] for atom in first.atoms if atom.atomic_number != 1)

    roundtrip = all_atom_system_from_canonical_json(canonical_system_json_bytes(first))
    assert verify_rdkit_openff_prepared_system(roundtrip)["receipt_sha256"] == receipt["receipt_sha256"]


@requires_rdkit
def test_tetrahedral_and_double_bond_stereo_are_fail_closed() -> None:
    chiral = prepare_ligand_with_rdkit_openff(
        "C[C@H](O)C(=O)O",
        source_format="smiles",
        openff_adapter=_UnavailableOpenFF(),
    )
    alkene = prepare_ligand_with_rdkit_openff(
        "C/C=C/C",
        source_format="smiles",
        openff_adapter=_UnavailableOpenFF(),
    )

    assert any(atom.stereo in {"R", "S"} for atom in chiral.atoms)
    assert any(bond.stereo in {"E", "Z"} for bond in alkene.bonds)
    assert verify_rdkit_openff_prepared_system(chiral)["readiness"]["diagnostic_redocking_ready"] is True

    for smiles in ("CC(O)C(=O)O", "CC=CC"):
        with pytest.raises(
            RdkitOpenffPreparationError,
            match="undefined",
        ):
            prepare_ligand_with_rdkit_openff(
                smiles,
                source_format="smiles",
                openff_adapter=_UnavailableOpenFF(),
            )

    admitted = prepare_ligand_with_rdkit_openff(
        "CC=CC",
        source_format="smiles",
        config=RdkitOpenffPreparationConfig(require_defined_stereo=False),
        openff_adapter=_UnavailableOpenFF(),
    )
    admitted_receipt = verify_rdkit_openff_prepared_system(admitted)
    assert admitted_receipt["stereochemistry"]["prepared"]["undefined_count"] == 1
    assert admitted_receipt["readiness"]["diagnostic_redocking_ready"] is False
    assert "undefined_stereochemistry_allowed_diagnostic_only" in admitted_receipt["scientific_blockers"]


@requires_rdkit
def test_bounded_protonation_and_tautomer_candidates_remain_claim_blocked() -> None:
    amine = prepare_ligand_with_rdkit_openff(
        "CN",
        source_format="smiles",
        config=RdkitOpenffPreparationConfig(target_ph=7.4),
        openff_adapter=_UnavailableOpenFF(),
    )
    diketone = prepare_ligand_with_rdkit_openff(
        "CC(=O)CC(=O)C",
        source_format="smiles",
        openff_adapter=_UnavailableOpenFF(),
    )
    amine_states = verify_rdkit_openff_prepared_system(amine)["state_enumeration"]
    tautomer_states = verify_rdkit_openff_prepared_system(diketone)["state_enumeration"]

    assert amine_states["protonation_candidate_count"] >= 2
    assert {row["formal_charge"] for row in amine_states["protonation_candidates"]} >= {
        0,
        1,
    }
    assert amine_states["target_ph_interpreted"] is False
    assert tautomer_states["tautomer_candidate_count"] >= 2
    assert all(
        row["scientifically_validated"] is False and row["product_safe"] is False
        for row in (
            *amine_states["protonation_candidates"],
            *tautomer_states["tautomer_candidates"],
        )
    )


@requires_rdkit
def test_halogen_phosphate_and_sulfate_like_inputs_are_in_profile() -> None:
    examples = (
        "Clc1ccccc1Br",
        "OP(=O)(O)O",
        "OS(=O)(=O)O",
    )
    systems = [
        prepare_ligand_with_rdkit_openff(
            smiles,
            source_format="smiles",
            openff_adapter=_UnavailableOpenFF(),
        )
        for smiles in examples
    ]

    assert {atom.element for atom in systems[0].atoms} >= {"Cl", "Br"}
    assert any(atom.element == "P" for atom in systems[1].atoms)
    assert any(atom.element == "S" for atom in systems[2].atoms)
    for system in systems[1:]:
        receipt = verify_rdkit_openff_prepared_system(system)
        assert receipt["readiness"]["diagnostic_redocking_ready"] is True
        assert receipt["stereochemistry"]["prepared"]["unscoped_undefined_count"] >= 1
        assert "non_tetrahedral_stereo_perception_recorded_not_admission_gated" in receipt["scientific_blockers"]


@requires_rdkit
@pytest.mark.parametrize(
    ("smiles", "message"),
    (
        ("[Na+]", "unsupported ligand atomic numbers"),
        ("CC.[Cl-]", "multiple ligand fragments"),
        ("[CH3]", "radical atoms"),
        ("B", "unsupported ligand atomic numbers"),
    ),
)
def test_unsupported_chemistry_abstains(
    smiles: str,
    message: str,
) -> None:
    with pytest.raises(RdkitOpenffPreparationError, match=message):
        prepare_ligand_with_rdkit_openff(
            smiles,
            source_format="smiles",
            openff_adapter=_UnavailableOpenFF(),
        )


@requires_rdkit
def test_openff_admission_is_optional_but_exact_when_required() -> None:
    admitted = prepare_ligand_with_rdkit_openff(
        "c1ccncc1",
        source_format="smiles",
        config=RdkitOpenffPreparationConfig(require_openff=True),
        openff_adapter=_MatchingOpenFF(),
    )
    receipt = verify_rdkit_openff_prepared_system(admitted)
    assert receipt["runtime"]["openff"]["status"] == "admitted"
    assert receipt["readiness"]["openff_molecule_admitted"] is True
    assert receipt["readiness"]["openff_parameterization_ready"] is False

    with pytest.raises(
        RdkitOpenffPreparationError,
        match="required",
    ):
        prepare_ligand_with_rdkit_openff(
            "CC",
            source_format="smiles",
            config=RdkitOpenffPreparationConfig(require_openff=True),
            openff_adapter=_UnavailableOpenFF(),
        )

    with pytest.raises(
        RdkitOpenffPreparationError,
        match="changed the prepared molecular graph",
    ):
        prepare_ligand_with_rdkit_openff(
            "CC",
            source_format="smiles",
            openff_adapter=_MismatchingOpenFF(),
        )


@requires_rdkit
def test_sdf_coordinates_are_preserved_and_multi_record_input_is_rejected() -> None:
    from rdkit import Chem
    from rdkit.Chem import AllChem

    molecule = Chem.AddHs(Chem.MolFromSmiles("C[C@H](O)C"))
    parameters = AllChem.ETKDGv3()
    parameters.randomSeed = 91
    assert AllChem.EmbedMolecule(molecule, parameters) == 0
    block = Chem.MolToMolBlock(molecule, forceV3000=False)
    system = prepare_ligand_with_rdkit_openff(
        block + "\n$$$$\n",
        source_format="sdf-v2000",
        openff_adapter=_UnavailableOpenFF(),
    )
    receipt = verify_rdkit_openff_prepared_system(system)

    assert receipt["coordinates"]["input_conformer_preserved"] is True
    assert receipt["coordinates"]["coordinate_generation_method"] == "input_conformer"
    assert receipt["coordinates"]["uff_status"] == ("not_run_input_coordinates_preserved")

    with pytest.raises(
        RdkitOpenffPreparationError,
        match="exactly one molecule record",
    ):
        prepare_ligand_with_rdkit_openff(
            block + "\n$$$$\n" + block + "\n$$$$\n",
            source_format="sdf-v2000",
            openff_adapter=_UnavailableOpenFF(),
        )


@requires_rdkit
def test_cli_output_is_private_no_overwrite_and_redocking_compatible(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "prepared-ligand.json"
    arguments = [
        "--smiles",
        "c1ccncc1",
        "--source-id",
        "pyridine",
        "--output",
        str(output),
    ]

    assert preparation.main(arguments) == 0
    captured = capsys.readouterr()
    assert '"status":"prepared_diagnostic"' in captured.out
    original = output.read_bytes()
    system = all_atom_system_from_canonical_json(original)
    assert verify_rdkit_openff_prepared_system(system)["readiness"]["diagnostic_redocking_ready"] is True
    assert stat.S_IMODE(output.stat().st_mode) == 0o600

    assert preparation.main(arguments) == 1
    captured = capsys.readouterr()
    assert "no output path was replaced" in captured.err
    assert output.read_bytes() == original


@requires_rdkit
def test_redocking_receipt_verifies_embedded_preparation_contract() -> None:
    ligand = prepare_ligand_with_rdkit_openff(
        "c1ccncc1",
        source_format="smiles",
        openff_adapter=_UnavailableOpenFF(),
    )
    receptor_coordinates = (
        (3.0, 0.0, 0.0),
        (-3.0, 0.0, 0.0),
        (0.0, 3.0, 0.0),
        (0.0, -3.0, 0.0),
        (0.0, 0.0, 3.0),
    )
    receptor = AllAtomSystem(
        system_id="receptor",
        atoms=tuple(
            Atom(
                index=index,
                name=f"C{index + 1}",
                element="C",
                atomic_number=6,
                residue_index=0,
            )
            for index in range(len(receptor_coordinates))
        ),
        bonds=(),
        residues=(
            Residue(
                index=0,
                name="REC",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(len(receptor_coordinates))),
            ),
        ),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor((receptor_coordinates,), dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit-test"),
    )
    receptor_source = canonical_system_json_bytes(receptor)
    ligand_source = canonical_system_json_bytes(ligand)
    report = run_prepared_redocking_diagnostic(
        receptor,
        ligand,
        receptor_artifact_sha256=hashlib.sha256(receptor_source).hexdigest(),
        ligand_artifact_sha256=hashlib.sha256(ligand_source).hexdigest(),
        pocket_center_angstrom=(0.0, 0.0, 0.0),
        pocket_radius_angstrom=6.0,
        config=RedockingDiagnosticConfig(
            candidate_count=2,
            top_k=1,
            translation_radius_angstrom=1.0,
            seed=73,
        ),
    )

    assert report["input_contract"]["chemistry_preparation_performed"] is True
    assert report["input_contract"]["rdkit_openff_preparation_receipt_verified"] is True
    assert report["ligand_preparation"]["verified"] is True
    assert (
        report["source_artifacts"]["ligand_preparation_receipt_sha256"]
        == report["ligand_preparation"]["receipt_sha256"]
    )
    assert "rdkit_openff_preparation_receipt_missing" not in report["scientific_blockers"]
    assert "rdkit_chemistry_perception_not_independently_verified" in report["scientific_blockers"]


@requires_rdkit
def test_embedded_receipt_rejects_claim_promotion() -> None:
    system = prepare_ligand_with_rdkit_openff(
        "CC",
        source_format="smiles",
        openff_adapter=_UnavailableOpenFF(),
    )
    receipt = dict(system.metadata["rdkit_openff_preparation_receipt"])
    receipt["claims"] = {
        **dict(receipt["claims"]),
        "scientifically_validated": True,
    }
    tampered = replace(
        system,
        metadata={
            **dict(system.metadata),
            "rdkit_openff_preparation_receipt": receipt,
        },
    )

    with pytest.raises(
        RdkitOpenffPreparationError,
        match="claim flags cannot be promoted",
    ):
        verify_rdkit_openff_prepared_system(tampered)


@requires_rdkit
@pytest.mark.skipif(
    not hasattr(os, "O_NOFOLLOW"),
    reason="symlink-open rejection requires O_NOFOLLOW",
)
def test_cli_rejects_symlink_input(
    tmp_path: Path,
) -> None:
    real_input = tmp_path / "ligand.smi"
    linked_input = tmp_path / "ligand-link.smi"
    output = tmp_path / "prepared.json"
    real_input.write_text("CC", encoding="utf-8")
    linked_input.symlink_to(real_input)

    assert (
        preparation.main(
            [
                "--input",
                str(linked_input),
                "--input-format",
                "smiles",
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert not output.exists()
