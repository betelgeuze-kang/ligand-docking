"""Deterministic conformer ensemble tests (P1-4)."""

from __future__ import annotations

import pytest

from betelgeuze_engine.chemistry.conformer_ensemble import (
    CONFORMER_ENSEMBLE_SCHEMA_VERSION,
    ENSEMBLE_METHOD,
    STATUS_BLOCKED_INVALID,
    STATUS_READY,
    STATUS_UNSUPPORTED_MACROCYCLE_LANE,
    generate_conformer_ensemble,
)

pytest.importorskip("rdkit")

FLEXIBLE = "CCCCCCO"


def test_ensemble_is_ready_and_reports_schema() -> None:
    ensemble = generate_conformer_ensemble(FLEXIBLE, max_conformers=6, seed=11)
    payload = ensemble.to_dict()

    assert ensemble.ready is True
    assert payload["status"] == STATUS_READY
    assert payload["schema_version"] == CONFORMER_ENSEMBLE_SCHEMA_VERSION
    assert payload["generated_conformer_count"] >= 1
    assert payload["retained_conformer_count"] >= 1


def test_same_inputs_produce_identical_conformer_ids() -> None:
    first = generate_conformer_ensemble(FLEXIBLE, max_conformers=6, seed=11)
    second = generate_conformer_ensemble(FLEXIBLE, max_conformers=6, seed=11)

    assert first.conformer_ids == second.conformer_ids
    assert first.conformer_ids


def test_different_seed_changes_the_ensemble_identity() -> None:
    first = generate_conformer_ensemble(FLEXIBLE, max_conformers=6, seed=11)
    second = generate_conformer_ensemble(FLEXIBLE, max_conformers=6, seed=12)

    assert first.conformer_ids != second.conformer_ids
    assert first.provenance["parameter_digest"] != second.provenance["parameter_digest"]


def test_conformer_ids_are_unique_within_an_ensemble() -> None:
    ensemble = generate_conformer_ensemble(FLEXIBLE, max_conformers=8, seed=5)
    ids = [record.conformer_id for record in ensemble.records]

    assert len(ids) == len(set(ids))


def test_provenance_records_generation_parameters() -> None:
    ensemble = generate_conformer_ensemble(
        FLEXIBLE,
        max_conformers=6,
        seed=11,
        energy_window_kcal_mol=7.5,
        rmsd_diversity_a=0.75,
    )
    provenance = ensemble.provenance

    assert provenance["method"] == ENSEMBLE_METHOD
    assert provenance["seed"] == 11
    assert provenance["max_conformers"] == 6
    assert provenance["energy_window_kcal_mol"] == 7.5
    assert provenance["rmsd_diversity_a"] == 0.75
    assert provenance["deterministic"] is True
    assert provenance["rdkit_version"]
    assert provenance["force_field"] in {"mmff94", "uff", ""}


def test_every_retained_conformer_carries_an_energy() -> None:
    ensemble = generate_conformer_ensemble(FLEXIBLE, max_conformers=6, seed=11)

    for record in ensemble.retained_records:
        assert record.energy_kcal_mol is not None
        assert record.relative_energy_kcal_mol is not None
        assert record.relative_energy_kcal_mol >= -1e-6


def test_retained_conformers_are_ordered_lowest_energy_first() -> None:
    ensemble = generate_conformer_ensemble(FLEXIBLE, max_conformers=8, seed=5)
    energies = [
        record.energy_kcal_mol
        for record in ensemble.retained_records
        if record.energy_kcal_mol is not None
    ]

    assert energies == sorted(energies)


def test_energy_window_rejects_high_energy_conformers() -> None:
    tight = generate_conformer_ensemble(
        FLEXIBLE, max_conformers=8, seed=5, energy_window_kcal_mol=0.0, rmsd_diversity_a=0.0
    )

    assert "energy_window_exceeded" in tight.to_dict()["rejection_reasons"]
    assert len(tight.retained_records) < len(tight.records)


def test_rmsd_diversity_filter_removes_near_duplicates() -> None:
    loose = generate_conformer_ensemble(FLEXIBLE, max_conformers=8, seed=5, rmsd_diversity_a=0.0)
    strict = generate_conformer_ensemble(FLEXIBLE, max_conformers=8, seed=5, rmsd_diversity_a=3.0)

    assert len(strict.retained_records) < len(loose.retained_records)
    assert "rmsd_duplicate_of_retained_conformer" in strict.to_dict()["rejection_reasons"]


def test_rejected_conformers_are_reported_not_dropped() -> None:
    ensemble = generate_conformer_ensemble(FLEXIBLE, max_conformers=8, seed=5, rmsd_diversity_a=3.0)
    payload = ensemble.to_dict()

    assert payload["rejected_conformer_count"] > 0
    assert payload["generated_conformer_count"] == (
        payload["retained_conformer_count"] + payload["rejected_conformer_count"]
    )
    rejected = [record for record in ensemble.records if not record.retained]
    assert all(record.rejection_reason for record in rejected)


def test_coordinates_match_retained_conformer_count() -> None:
    ensemble = generate_conformer_ensemble(FLEXIBLE, max_conformers=6, seed=11)

    assert ensemble.coordinates is not None
    assert ensemble.coordinates.shape[0] == len(ensemble.retained_records)
    assert ensemble.coordinates.shape[2] == 3


def test_rigid_ligand_yields_a_single_conformer() -> None:
    ensemble = generate_conformer_ensemble("c1ccccc1", max_conformers=8, seed=3)

    assert ensemble.ready is True
    assert len(ensemble.retained_records) == 1


def test_macrocycle_routes_to_unsupported_lane() -> None:
    ensemble = generate_conformer_ensemble("C1CCCCCCCCCCCC1")

    assert ensemble.status == STATUS_UNSUPPORTED_MACROCYCLE_LANE
    assert ensemble.ready is False
    assert ensemble.records == ()
    assert ensemble.coordinates is None
    assert "macrocycle_requires_ring_closure_sampling" in ensemble.blockers


def test_macrocycle_can_be_generated_only_with_explicit_opt_in() -> None:
    ensemble = generate_conformer_ensemble(
        "C1CCCCCCCCCCCC1", max_conformers=4, seed=2, allow_macrocycle=True
    )

    assert ensemble.status == STATUS_READY
    assert len(ensemble.retained_records) >= 1


def test_invalid_and_empty_smiles_block() -> None:
    assert generate_conformer_ensemble("").status == STATUS_BLOCKED_INVALID
    assert generate_conformer_ensemble("not_a_molecule[").status == STATUS_BLOCKED_INVALID


def test_payload_states_uncalibrated_claim_boundary() -> None:
    payload = generate_conformer_ensemble(FLEXIBLE, max_conformers=4, seed=1).to_dict()

    assert "uncalibrated" in payload["claim_boundary"]
    assert "not a benchmarked" in payload["claim_boundary"]
