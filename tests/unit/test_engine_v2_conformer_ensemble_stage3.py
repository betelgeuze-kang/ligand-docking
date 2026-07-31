from __future__ import annotations

from dataclasses import replace
import pytest


torch = pytest.importorskip("torch")
pytest.importorskip("rdkit")
from rdkit import Chem  # noqa: E402
from rdkit.Chem import AllChem  # noqa: E402

from betelgeuze_engine_v2.docking import (  # noqa: E402
    CONFORMER_ENSEMBLE_SCHEMA_ID,
    SOURCE_BOUND_CONFORMER_ENSEMBLE_SCHEMA_ID,
    SOURCE_BOUND_CONFORMER_SOURCE_INDEX_MAPPING_SCHEMA_ID,
    ConformerPreparationConfig,
    ConformerPreparationError,
    prepare_deterministic_conformer_ensemble,
    prepare_source_bound_conformer_ensemble,
)
from betelgeuze_engine_v2.docking import conformers  # noqa: E402
from betelgeuze_engine_v2.io import parse_sdf_v2000  # noqa: E402
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    canonical_coordinates_sha256,
    canonical_system_sha256,
    canonical_topology_sha256,
)


def _config() -> ConformerPreparationConfig:
    return ConformerPreparationConfig(
        candidate_count=8,
        selected_count=4,
        random_seed=12345,
        max_optimization_iterations=200,
        energy_window_kcal_mol=20.0,
        diversity_rmsd_angstrom=0.25,
    )


def _source_sdf_bytes(
    smiles: str = "CCCCCC",
    *,
    explicit_hydrogens: bool = True,
) -> bytes:
    molecule = Chem.MolFromSmiles(smiles)
    assert molecule is not None
    if explicit_hydrogens:
        molecule = Chem.AddHs(molecule)
        parameters = AllChem.ETKDGv3()
        parameters.randomSeed = 918273
        parameters.numThreads = 1
        assert AllChem.EmbedMolecule(molecule, parameters) == 0
        if AllChem.MMFFHasAllMoleculeParams(molecule):
            AllChem.MMFFOptimizeMolecule(molecule, maxIters=200)
        else:
            AllChem.UFFOptimizeMolecule(molecule, maxIters=200)
    else:
        AllChem.Compute2DCoords(molecule)
    block = Chem.MolToMolBlock(molecule, includeStereo=True)
    return (block.rstrip() + "\n$$$$\n").encode("ascii")


def _source_config() -> ConformerPreparationConfig:
    return ConformerPreparationConfig(
        candidate_count=12,
        selected_count=4,
        random_seed=24680,
        max_optimization_iterations=200,
        energy_window_kcal_mol=20.0,
        diversity_rmsd_angstrom=0.1,
    )


def test_etkdg_ensemble_is_deterministic_and_identity_bound() -> None:
    first = prepare_deterministic_conformer_ensemble(
        "CCCC",
        config=_config(),
    )
    second = prepare_deterministic_conformer_ensemble(
        "CCCC",
        config=_config(),
    )

    assert first.receipt_sha256 == second.receipt_sha256
    assert canonical_system_sha256(first.system) == canonical_system_sha256(
        second.system
    )
    assert canonical_coordinates_sha256(first.system) == canonical_coordinates_sha256(
        second.system
    )
    assert torch.equal(first.system.coordinates, second.system.coordinates)
    assert [row.conformer_id for row in first.records] == [
        row.conformer_id for row in second.records
    ]
    assert first.system.model_count == len(first.records)
    assert first.system.model_count >= 2


def test_energy_window_and_heavy_atom_rmsd_diversity_are_enforced() -> None:
    config = _config()
    ensemble = prepare_deterministic_conformer_ensemble(
        "CCCCC",
        config=config,
    )
    energies = [row.energy_kcal_mol for row in ensemble.records]
    assert energies == sorted(energies)
    assert max(energies) <= min(energies) + config.energy_window_kcal_mol

    heavy_indices = tuple(
        atom.index for atom in ensemble.system.atoms if atom.atomic_number > 1
    )
    for first in range(ensemble.system.model_count):
        for second in range(first):
            rmsd = conformers._heavy_atom_rmsd(
                ensemble.system.coordinates[first],
                ensemble.system.coordinates[second],
                heavy_indices,
            )
            assert rmsd + 1.0e-12 >= config.diversity_rmsd_angstrom


def test_prepared_state_receipt_records_exact_denominators_and_provenance() -> None:
    ensemble = prepare_deterministic_conformer_ensemble(
        "CCCO",
        config=_config(),
    )
    document = ensemble.to_dict()

    assert document["schema_id"] == CONFORMER_ENSEMBLE_SCHEMA_ID
    assert document["etkdg_variant"] == "ETKDGv3"
    assert document["requested_candidate_count"] == 8
    assert document["input_atom_count"] > 0
    assert document["prepared_atom_count"] == ensemble.system.atom_count
    assert document["connected_component_policy"] == "exactly_one"
    assert document["unspecified_potential_stereochemistry_allowed"] is False
    assert document["embedded_candidate_count"] == len(document["optimization_rows"])
    assert document["selected_conformer_count"] == len(ensemble.records)
    assert document["selected_conformer_ids"] == [
        row.conformer_id for row in ensemble.records
    ]
    assert document["selected_conformer_records"] == [
        row.to_dict() for row in ensemble.records
    ]
    assert document["preparation_bounds"]["maximum_input_atoms"] == 256
    assert document["prepared_system_sha256"] == canonical_system_sha256(
        ensemble.system
    )
    assert document["prepared_coordinates_sha256"] == (
        canonical_coordinates_sha256(ensemble.system)
    )
    assert all(row.coordinates_sha256 for row in ensemble.records)
    assert ensemble.system.provenance.parser_name == (
        "rdkit_etkdgv3_conformer_preparation"
    )
    assert ensemble.system.provenance.chemistry_validated is False
    assert document["scientifically_validated"] is False
    assert document["claim_safe"] is False


def test_prepared_state_receipt_rejects_mutation() -> None:
    ensemble = prepare_deterministic_conformer_ensemble(
        "CCCC",
        config=_config(),
    )
    mutated = dict(ensemble.receipt)
    mutated["selected_conformer_ids"] = list(
        reversed(mutated["selected_conformer_ids"])
    )
    with pytest.raises(
        ConformerPreparationError,
        match="prepared-state receipt changed",
    ):
        replace(ensemble, receipt=mutated)

    with pytest.raises(TypeError):
        ensemble.receipt["selected_conformer_ids"][0] = "0" * 64

    ensemble.system.coordinates[0, 0, 0] += 1.0
    with pytest.raises(
        ConformerPreparationError,
        match="prepared system changed",
    ):
        ensemble.to_dict()


def test_conformer_record_fields_are_bound_to_the_receipt() -> None:
    ensemble = prepare_deterministic_conformer_ensemble(
        "CCCC",
        config=_config(),
    )
    changed_record = replace(
        ensemble.records[0],
        energy_kcal_mol=ensemble.records[0].energy_kcal_mol + 1.0,
    )
    with pytest.raises(
        ConformerPreparationError,
        match="conformer records are cross-wired",
    ):
        replace(
            ensemble,
            records=(changed_record, *ensemble.records[1:]),
        )


def test_equivalent_smiles_are_rebuilt_in_canonical_atom_order() -> None:
    first = prepare_deterministic_conformer_ensemble(
        "CO",
        config=_config(),
    )
    second = prepare_deterministic_conformer_ensemble(
        "OC",
        config=_config(),
    )
    assert canonical_system_sha256(first.system) == canonical_system_sha256(
        second.system
    )
    assert torch.equal(first.system.coordinates, second.system.coordinates)
    assert [row.conformer_id for row in first.records] == [
        row.conformer_id for row in second.records
    ]
    assert (
        first.receipt["input_smiles_sha256"] != (second.receipt["input_smiles_sha256"])
    )


def test_disconnected_ligand_fails_closed() -> None:
    with pytest.raises(
        ConformerPreparationError,
        match="one connected ligand component",
    ):
        prepare_deterministic_conformer_ensemble(
            "CC.[Na+]",
            config=_config(),
        )


def test_oversized_ligand_fails_before_embedding() -> None:
    with pytest.raises(
        ConformerPreparationError,
        match="atom count exceeds",
    ):
        prepare_deterministic_conformer_ensemble(
            "C" * 257,
            config=_config(),
        )


@pytest.mark.parametrize("smiles", ["CC(F)Cl", "CC=CC"])
def test_unspecified_potential_stereochemistry_fails_closed(
    smiles: str,
) -> None:
    with pytest.raises(
        ConformerPreparationError,
        match="stereochemistry must be explicitly assigned",
    ):
        prepare_deterministic_conformer_ensemble(
            smiles,
            config=_config(),
        )


def test_explicit_stereochemistry_is_retained() -> None:
    ensemble = prepare_deterministic_conformer_ensemble(
        "C[C@H](F)Cl",
        config=_config(),
    )
    assert any(atom.stereo in {"R", "S"} for atom in ensemble.system.atoms)


@pytest.mark.parametrize("smiles", ["", "not-a-smiles"])
def test_invalid_smiles_fail_closed(smiles: str) -> None:
    with pytest.raises(ConformerPreparationError):
        prepare_deterministic_conformer_ensemble(smiles, config=_config())


def test_macrocycle_lane_fails_closed() -> None:
    with pytest.raises(
        ConformerPreparationError,
        match="macrocycle",
    ):
        prepare_deterministic_conformer_ensemble(
            "C1CCCCCCCCCCC1",
            config=_config(),
        )


def test_source_bound_ensemble_is_exact_deterministic_and_nonclaiming() -> None:
    source_bytes = _source_sdf_bytes()
    source = parse_sdf_v2000(
        source_bytes,
        source_id="source-bound-fixture",
        dtype=torch.float64,
        device="cpu",
    )
    charged_source = replace(
        source,
        atoms=tuple(
            replace(atom, partial_charge_e=(atom.index + 1) * 0.001)
            for atom in source.atoms
        ),
    )
    config = _source_config()
    first = prepare_source_bound_conformer_ensemble(
        charged_source,
        source_bytes,
        config=config,
    )
    second = prepare_source_bound_conformer_ensemble(
        charged_source,
        source_bytes,
        config=config,
    )

    assert first.receipt_sha256 == second.receipt_sha256
    assert torch.equal(first.system.coordinates, second.system.coordinates)
    assert canonical_topology_sha256(first.system) == (
        canonical_topology_sha256(charged_source)
    )
    assert [atom.partial_charge_e for atom in first.system.atoms] == [
        atom.partial_charge_e for atom in charged_source.atoms
    ]
    assert first.system.provenance.parent_sha256[-1] == (
        canonical_system_sha256(charged_source)
    )
    document = first.to_dict()
    assert document["schema_id"] == (SOURCE_BOUND_CONFORMER_ENSEMBLE_SCHEMA_ID)
    assert document["development_only"] is True
    assert document["stage0_eligible"] is False
    assert document["fresh_execution_authorized"] is False
    assert document["claim_safe"] is False
    assert document["derivation_evidence_sha256"] != first.receipt_sha256
    assert (
        first.system.provenance.metadata["last_operation_evidence_sha256"]
        == document["derivation_evidence_sha256"]
    )
    assert (
        first.system.provenance.metadata["source_bound_conformer_development_only"]
        is True
    )
    assert (
        first.system.provenance.metadata["source_bound_conformer_stage0_eligible"]
        is False
    )
    assert (
        first.system.provenance.metadata[
            "source_bound_conformer_fresh_execution_authorized"
        ]
        is False
    )
    derivation = document["derivation_evidence"]
    assert derivation["source_sdf_rdkit_atom_order_verified"] is True
    source_index_mapping = derivation["source_index_mapping"]
    assert source_index_mapping["schema_id"] == (
        SOURCE_BOUND_CONFORMER_SOURCE_INDEX_MAPPING_SCHEMA_ID
    )
    assert source_index_mapping["normalized_source_index_by_rdkit_index"] == list(
        range(charged_source.atom_count)
    )
    assert source_index_mapping["source_coordinates_preserved_after_normalization"]
    assert derivation["source_index_mapping_sha256"] == conformers._sha256(
        source_index_mapping
    )
    assert (
        derivation["generated_conformer_stereo_verified_count"]
        == (derivation["embedded_candidate_count"])
    )
    assert first.system.model_count == len(first.records)
    assert first.raw_coordinates.shape == first.system.coordinates.shape
    heavy_indices = tuple(
        atom.index for atom in charged_source.atoms if atom.atomic_number > 1
    )
    source_centroid = charged_source.coordinates[0][list(heavy_indices)].mean(dim=0)
    for model_index, record in enumerate(first.records):
        assert (
            record.source_pose_rmsd_angstrom + 1.0e-12 >= config.diversity_rmsd_angstrom
        )
        assert torch.allclose(
            first.system.coordinates[model_index][list(heavy_indices)].mean(dim=0),
            source_centroid,
            atol=1.0e-10,
            rtol=0.0,
        )
        rotation = torch.tensor(
            record.alignment_rotation,
            dtype=torch.float64,
        )
        assert float(torch.linalg.det(rotation).item()) == pytest.approx(1.0)


def test_source_bound_aromatic_perception_preserves_source_topology_authority() -> None:
    source_bytes = _source_sdf_bytes("c1ccccc1")
    source = parse_sdf_v2000(
        source_bytes,
        source_id="aromatic-source-index-fixture",
    )
    ensemble = prepare_source_bound_conformer_ensemble(
        source,
        source_bytes,
        config=replace(
            _source_config(),
            candidate_count=4,
            selected_count=1,
            diversity_rmsd_angstrom=0.0,
        ),
    )

    assert canonical_topology_sha256(ensemble.system) == canonical_topology_sha256(
        source
    )
    derivation = ensemble.to_dict()["derivation_evidence"]
    mapping = derivation["source_index_mapping"]
    assert mapping["raw_source_projection_exact_before_sanitization"] is True
    assert mapping["post_sanitize_bond_order_aromaticity_policy"] == (
        "exact_or_kekule_ring_to_rdkit_aromatic"
    )
    assert mapping["normalized_source_index_by_rdkit_index"] == list(
        range(source.atom_count)
    )
    assert any(
        not row["aromatic"]
        for row in derivation["source_raw_rdkit_projection"]["bonds"]
    )
    post_sanitize_bonds = mapping["post_sanitize_bond_projection"]
    assert mapping["post_sanitize_bond_projection_sha256"] == conformers._sha256(
        post_sanitize_bonds
    )
    assert any(
        row["equivalence"] == "kekule_ring_to_rdkit_aromatic"
        for row in post_sanitize_bonds
    )
    assert all(
        row["equivalence"] in {"exact", "kekule_ring_to_rdkit_aromatic"}
        for row in post_sanitize_bonds
    )

    tampered_receipt = conformers._thaw_json(ensemble.receipt)
    tampered_mapping = tampered_receipt["derivation_evidence"][
        "source_index_mapping"
    ]
    aromatic_row = next(
        row
        for row in tampered_mapping["post_sanitize_bond_projection"]
        if row["equivalence"] == "kekule_ring_to_rdkit_aromatic"
    )
    aromatic_row["equivalence"] = "exact"
    tampered_mapping["post_sanitize_bond_projection_sha256"] = conformers._sha256(
        tampered_mapping["post_sanitize_bond_projection"]
    )
    tampered_receipt["derivation_evidence"][
        "source_index_mapping_sha256"
    ] = conformers._sha256(tampered_mapping)
    tampered_receipt["derivation_evidence_sha256"] = conformers._sha256(
        tampered_receipt["derivation_evidence"]
    )
    with pytest.raises(
        ConformerPreparationError,
        match="post-sanitize bond equivalence is invalid",
    ):
        replace(
            ensemble,
            receipt=tampered_receipt,
            receipt_sha256=conformers._sha256(tampered_receipt),
        )


def test_source_index_mapping_normalizes_and_rejects_non_bijections() -> None:
    source_bytes = _source_sdf_bytes("CCCC")
    source = parse_sdf_v2000(
        source_bytes,
        source_id="renumbered-source-index-fixture",
    )
    mol_block = source_bytes.decode("ascii").split("$$$$", 1)[0]
    molecule = Chem.MolFromMolBlock(
        mol_block,
        sanitize=False,
        removeHs=False,
        strictParsing=True,
    )
    assert molecule is not None
    conformers._bind_rdkit_source_atom_indices(
        molecule,
        source_atom_count=source.atom_count,
    )
    Chem.SanitizeMol(molecule)
    reversed_order = list(reversed(range(source.atom_count)))
    renumbered = Chem.RenumberAtoms(molecule, reversed_order)

    normalized, mapping = conformers._normalize_rdkit_source_atom_order(
        renumbered,
        source,
        chemistry=Chem,
    )
    assert mapping["post_sanitize_source_index_by_rdkit_index"] == reversed_order
    assert mapping["normalized_source_index_by_rdkit_index"] == list(
        range(source.atom_count)
    )
    assert mapping["renumbered_to_source_order"] is True
    assert torch.equal(conformers._coordinates(normalized, 0), source.coordinates[0])

    changed_order = Chem.Mol(normalized)
    changed_order.GetBondWithIdx(0).SetBondType(Chem.BondType.DOUBLE)
    with pytest.raises(
        ConformerPreparationError,
        match="outside the allowed aromatic equivalence",
    ):
        conformers._normalize_rdkit_source_atom_order(
            changed_order,
            source,
            chemistry=Chem,
        )

    normalized.GetAtomWithIdx(1).SetIntProp(
        conformers._SOURCE_ATOM_INDEX_PROPERTY,
        0,
    )
    with pytest.raises(
        ConformerPreparationError,
        match="invalidated the source atom-index mapping",
    ):
        conformers._normalize_rdkit_source_atom_order(
            normalized,
            source,
            chemistry=Chem,
        )


def test_source_bound_input_cross_wires_and_implicit_hydrogens_fail_closed() -> None:
    source_bytes = _source_sdf_bytes()
    source = parse_sdf_v2000(source_bytes, source_id="source-bound-fixture")
    with pytest.raises(
        ConformerPreparationError,
        match="digest does not match",
    ):
        prepare_source_bound_conformer_ensemble(
            source,
            source_bytes + b"\n",
            config=_source_config(),
        )

    changed_coordinates = source.coordinates.clone()
    changed_coordinates[0, 0, 0] = torch.nextafter(
        changed_coordinates[0, 0, 0],
        torch.tensor(float("inf"), dtype=torch.float64),
    )
    with pytest.raises(
        ConformerPreparationError,
        match="do not match the source SDF",
    ):
        prepare_source_bound_conformer_ensemble(
            replace(source, coordinates=changed_coordinates),
            source_bytes,
            config=_source_config(),
        )

    changed_atom = replace(
        source,
        atoms=(
            replace(source.atoms[0], formal_charge=1),
            *source.atoms[1:],
        ),
    )
    changed_bond = replace(
        source,
        bonds=(replace(source.bonds[0], order=2.0), *source.bonds[1:]),
    )
    for changed_source in (changed_atom, changed_bond):
        with pytest.raises(
            ConformerPreparationError,
            match="do not match the source SDF",
        ):
            prepare_source_bound_conformer_ensemble(
                changed_source,
                source_bytes,
                config=_source_config(),
            )

    unsupported_lines = source_bytes.decode("ascii").splitlines()
    unsupported_atom_line = unsupported_lines[4].ljust(69)
    unsupported_lines[4] = (
        unsupported_atom_line[:42] + f"{1:3d}" + unsupported_atom_line[45:]
    )
    unsupported_bytes = ("\n".join(unsupported_lines) + "\n").encode("ascii")
    unsupported_source = parse_sdf_v2000(
        unsupported_bytes,
        source_id="unsupported-molfile-fixture",
    )
    with pytest.raises(
        ConformerPreparationError,
        match="unsupported non-default atom fields",
    ):
        prepare_source_bound_conformer_ensemble(
            unsupported_source,
            unsupported_bytes,
            config=_source_config(),
        )

    implicit_hydrogen_bytes = _source_sdf_bytes(
        "CCCC",
        explicit_hydrogens=False,
    )
    implicit_hydrogen_source = parse_sdf_v2000(
        implicit_hydrogen_bytes,
        source_id="implicit-hydrogen-fixture",
    )
    with pytest.raises(
        ConformerPreparationError,
        match="requires explicit hydrogens",
    ):
        prepare_source_bound_conformer_ensemble(
            implicit_hydrogen_source,
            implicit_hydrogen_bytes,
            config=_source_config(),
        )

    with pytest.raises(
        ConformerPreparationError,
        match="moving alignment requires non-collinear heavy atoms",
    ):
        conformers._aligned_to_reference(
            torch.tensor(
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
                dtype=torch.float64,
            ),
            torch.tensor(
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                dtype=torch.float64,
            ),
            (0, 1, 2),
        )


def test_source_bound_receipt_and_raw_coordinates_are_anti_tamper() -> None:
    source_bytes = _source_sdf_bytes("CC[C@H](F)Cl")
    source = parse_sdf_v2000(source_bytes, source_id="stereo-fixture")
    config = replace(
        _source_config(),
        candidate_count=4,
        selected_count=1,
        diversity_rmsd_angstrom=0.0,
    )
    ensemble = prepare_source_bound_conformer_ensemble(
        source,
        source_bytes,
        config=config,
    )
    stereo_projection = ensemble.receipt["derivation_evidence"][
        "source_stereo_projection"
    ]
    assert stereo_projection["atoms"]
    assert any(row["molfile_stereo_code"] != 0 for row in stereo_projection["bonds"])
    derivation = ensemble.receipt["derivation_evidence"]
    assert all(
        row["stereo_projection_sha256"] == derivation["source_stereo_projection_sha256"]
        for row in derivation["generated_conformer_stereo_verifications"]
    )

    mutated_receipt = conformers._thaw_json(ensemble.receipt)
    mutated_receipt["derivation_evidence"]["selected_conformer_count"] += 1
    with pytest.raises(
        ConformerPreparationError,
        match="receipt changed",
    ):
        replace(ensemble, receipt=mutated_receipt)

    ensemble.raw_coordinates[0, 0, 0] += 1.0
    with pytest.raises(
        ConformerPreparationError,
        match="coordinates are cross-wired",
    ):
        ensemble.to_dict()


def test_source_bound_double_bond_stereo_is_verified_per_conformer() -> None:
    source_bytes = _source_sdf_bytes("CC/C=C/CC")
    source = parse_sdf_v2000(source_bytes, source_id="double-bond-fixture")
    ensemble = prepare_source_bound_conformer_ensemble(
        source,
        source_bytes,
        config=replace(
            _source_config(),
            candidate_count=4,
            selected_count=1,
            diversity_rmsd_angstrom=0.0,
        ),
    )
    derivation = ensemble.receipt["derivation_evidence"]
    assert any(
        row["stereo"] in {"STEREOE", "STEREOZ"}
        for row in derivation["source_stereo_projection"]["bonds"]
    )
    assert len(derivation["generated_conformer_stereo_verifications"]) == 4


def test_missing_rdkit_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable():
        raise ConformerPreparationError(
            "RDKit is required for deterministic ETKDG preparation"
        )

    monkeypatch.setattr(conformers, "_load_rdkit", unavailable)
    with pytest.raises(
        ConformerPreparationError,
        match="RDKit is required",
    ):
        prepare_deterministic_conformer_ensemble(
            "CCCC",
            config=_config(),
        )
