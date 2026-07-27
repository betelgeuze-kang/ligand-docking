from __future__ import annotations

from dataclasses import replace
import pytest


torch = pytest.importorskip("torch")
pytest.importorskip("rdkit")

from betelgeuze_engine_v2.docking import (  # noqa: E402
    CONFORMER_ENSEMBLE_SCHEMA_ID,
    ConformerPreparationConfig,
    ConformerPreparationError,
    prepare_deterministic_conformer_ensemble,
)
from betelgeuze_engine_v2.docking import conformers  # noqa: E402
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    canonical_coordinates_sha256,
    canonical_system_sha256,
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
    assert canonical_coordinates_sha256(
        first.system
    ) == canonical_coordinates_sha256(second.system)
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
        atom.index
        for atom in ensemble.system.atoms
        if atom.atomic_number > 1
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
    assert document["embedded_candidate_count"] == len(
        document["optimization_rows"]
    )
    assert document["selected_conformer_count"] == len(ensemble.records)
    assert document["selected_conformer_ids"] == [
        row.conformer_id for row in ensemble.records
    ]
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
