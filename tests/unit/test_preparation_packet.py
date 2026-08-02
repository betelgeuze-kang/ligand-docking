"""Unified preparation packet tests (P1-1)."""

from __future__ import annotations

import pytest

from betelgeuze_product.preparation_packet import (
    ENGINE_SURFACE_ENGINE_V2,
    ENGINE_SURFACE_EXTERNAL_ORACLE,
    ENGINE_SURFACE_LEGACY_PRODUCT,
    ENGINE_SURFACES,
    PREPARATION_PACKET_SCHEMA_VERSION,
    STATUS_LIGAND_BLOCKED,
    STATUS_LIGAND_READY,
    STATUS_RECEPTOR_READY,
)
from betelgeuze_product.preparation_service import (
    build_preparation_packet,
    prepare_ligand,
    prepare_receptor,
)

pytest.importorskip("rdkit")

FLEXIBLE_LIGAND = "CCCCCCO"
MACROCYCLE = "C1CCCCCCCCCCCC1"


def _receptor_pdb(atom_count: int = 30) -> str:
    return "".join(
        "ATOM  %5d  CA  ALA A%4d    %8.3f%8.3f%8.3f  1.00  0.00           C\n"
        % (index, index, float(index), float(index % 3), 0.0)
        for index in range(1, atom_count + 1)
    )


def _packet(**overrides):
    kwargs = {
        "receptor_payload": {"pdb_content": _receptor_pdb(), "target_id": "T1"},
        "ligand_smiles": FLEXIBLE_LIGAND,
        "target_id": "T1",
        "ligand_id": "L1",
        "max_conformers": 4,
        "seed": 7,
    }
    kwargs.update(overrides)
    return build_preparation_packet(**kwargs)


def test_packet_is_ready_for_valid_receptor_and_ligand() -> None:
    packet = _packet()
    payload = packet.to_dict()

    assert packet.ready is True
    assert payload["status"] == "preparation_packet_ready"
    assert payload["schema_version"] == PREPARATION_PACKET_SCHEMA_VERSION
    assert payload["receptor"]["status"] == STATUS_RECEPTOR_READY
    assert payload["ligand"]["status"] == STATUS_LIGAND_READY
    assert payload["blockers"] == []


def test_every_engine_surface_receives_identical_prepared_input() -> None:
    packet = _packet()
    views = {surface: packet.adapter_input(surface) for surface in ENGINE_SURFACES}

    hashes = {view["prepared_input_hash"] for view in views.values()}
    assert len(hashes) == 1

    # Only the surface label may differ between adapter views.
    reference = dict(views[ENGINE_SURFACE_LEGACY_PRODUCT])
    for surface, view in views.items():
        candidate = dict(view)
        assert candidate.pop("engine_surface") == surface
        assert candidate == {k: v for k, v in reference.items() if k != "engine_surface"}


def test_adapter_input_rejects_unknown_engine_surface() -> None:
    packet = _packet()

    with pytest.raises(ValueError) as excinfo:
        packet.adapter_input("some_other_engine")

    assert "unsupported_engine_surface" in str(excinfo.value)


def test_supported_surfaces_cover_legacy_v2_and_oracle() -> None:
    assert ENGINE_SURFACES == (
        ENGINE_SURFACE_LEGACY_PRODUCT,
        ENGINE_SURFACE_ENGINE_V2,
        ENGINE_SURFACE_EXTERNAL_ORACLE,
    )


def test_prepared_input_hash_is_deterministic() -> None:
    assert _packet().prepared_input_hash == _packet().prepared_input_hash


def test_prepared_input_hash_changes_with_ligand() -> None:
    first = _packet()
    second = _packet(ligand_smiles="CCCCCCCO")

    assert first.prepared_input_hash != second.prepared_input_hash


def test_prepared_input_hash_changes_with_receptor() -> None:
    first = _packet()
    second = _packet(
        receptor_payload={"pdb_content": _receptor_pdb(atom_count=25), "target_id": "T1"}
    )

    assert first.prepared_input_hash != second.prepared_input_hash


def test_receptor_packet_carries_pocket_identity_and_contract_receipt() -> None:
    receptor = prepare_receptor({"pdb_content": _receptor_pdb(), "target_id": "T1"})
    payload = receptor.to_dict()

    assert receptor.ready is True
    assert payload["pocket"]["ready"] is True
    assert payload["pocket"]["radius_a"] > 0.0
    assert payload["pocket_hash"]
    assert payload["legacy_input_contract"]["fail_closed"] is True
    assert payload["atom_count"] == 30


def test_receptor_without_coordinates_fails_closed() -> None:
    receptor = prepare_receptor({"pdb_content": "HEADER only\n", "target_id": "T1"})

    assert receptor.ready is False
    assert "prepared_receptor_has_no_coordinates" in receptor.blockers


def test_receptor_with_invalid_coordinate_fails_closed() -> None:
    bad = "ATOM      1  CA  ALA A   1        nope  0.000   0.000  1.00  0.00           C\n"
    receptor = prepare_receptor({"pdb_content": bad, "target_id": "T1"})

    assert receptor.ready is False
    assert receptor.blockers


def test_ligand_packet_carries_rotor_and_conformer_identity() -> None:
    ligand = prepare_ligand(FLEXIBLE_LIGAND, ligand_id="L1", max_conformers=4, seed=7)
    payload = ligand.to_dict()

    assert ligand.ready is True
    assert payload["flexibility_lane"] == "rigid_component_plus_rotor"
    assert payload["rotor_count"] >= 1
    assert payload["retained_conformer_count"] >= 1
    assert payload["conformer_ids"]
    assert len(payload["conformer_ids"]) == payload["retained_conformer_count"]


def test_macrocycle_ligand_blocks_the_packet() -> None:
    packet = _packet(ligand_smiles=MACROCYCLE)
    payload = packet.to_dict()

    assert packet.ready is False
    assert payload["ligand"]["status"] == STATUS_LIGAND_BLOCKED
    assert payload["ligand"]["flexibility_lane"] == "macrocycle_unsupported"
    assert "macrocycle_ligand_unsupported_lane" in payload["blockers"]
    # A blocked packet still reaches the adapter view, flagged not-ready.
    assert packet.adapter_input(ENGINE_SURFACE_ENGINE_V2)["ready"] is False


def test_invalid_ligand_blocks_the_packet() -> None:
    packet = _packet(ligand_smiles="not_a_molecule[")

    assert packet.ready is False
    assert packet.blockers


def test_ligand_input_hash_tracks_conformer_ensemble_parameters() -> None:
    first = prepare_ligand(FLEXIBLE_LIGAND, ligand_id="L1", max_conformers=4, seed=7)
    same = prepare_ligand(FLEXIBLE_LIGAND, ligand_id="L1", max_conformers=4, seed=7)
    reseeded = prepare_ligand(FLEXIBLE_LIGAND, ligand_id="L1", max_conformers=4, seed=8)

    assert first.input_hash == same.input_hash
    assert first.input_hash != reseeded.input_hash


def test_packet_payload_states_no_scoring_claim() -> None:
    payload = _packet().to_dict()

    assert "does not dock, score, rank" in payload["claim_boundary"]
