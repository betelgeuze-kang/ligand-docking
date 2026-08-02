"""Legacy / V2 / oracle executed on one prepared packet (P1-1, P1-9).

The schemas for a canonical packet, a common result bundle, and a shadow record
already existed, but nothing ran all three engine surfaces over one prepared
input. These tests exercise that execution path end to end so a legacy-vs-V2
delta is backed by an actual run rather than by schema presence.
"""

from __future__ import annotations

import pytest

from betelgeuze_product.engine_adapters import (
    EXTERNAL_ORACLE_ADAPTER_VERSION,
    EXTERNAL_ORACLE_BINARIES,
    available_external_oracle_binaries,
    run_engine_v2_adapter,
    run_external_oracle_adapter,
    run_legacy_adapter,
)
from betelgeuze_product.preparation_packet import (
    ENGINE_SURFACE_ENGINE_V2,
    ENGINE_SURFACE_EXTERNAL_ORACLE,
    ENGINE_SURFACE_LEGACY_PRODUCT,
)
from betelgeuze_product.preparation_service import build_preparation_packet
from betelgeuze_product.shadow_execution import (
    ACTIVE_SURFACE,
    build_shadow_execution_record,
)

pytest.importorskip("rdkit")


def _receptor_pdb(atom_count: int = 40) -> str:
    return "".join(
        "ATOM  %5d  CA  ALA A%4d    %8.3f%8.3f%8.3f  1.00  0.00           C\n"
        % (index, index, float(index % 9), float(index % 5), float(index % 3))
        for index in range(1, atom_count + 1)
    )


@pytest.fixture(scope="module")
def packet():
    return build_preparation_packet(
        receptor_payload={"pdb_content": _receptor_pdb(), "target_id": "T1"},
        ligand_smiles="CCCCCCO",
        target_id="T1",
        ligand_id="L1",
        max_conformers=6,
        seed=7,
    )


@pytest.fixture(scope="module")
def three_surface_record(packet):
    return build_shadow_execution_record(
        packet=packet,
        bundles=[
            run_legacy_adapter(packet),
            run_engine_v2_adapter(packet),
            run_external_oracle_adapter(packet),
        ],
    )


def test_packet_carries_conformer_coordinates_so_no_engine_re_embeds(packet) -> None:
    ligand = packet.ligand

    assert packet.ready is True
    assert ligand.atom_elements
    assert len(ligand.atom_elements) == ligand.atom_count
    assert len(ligand.conformer_coordinates) == len(ligand.conformer_ids)
    for conformer in ligand.conformer_coordinates:
        assert len(conformer) == len(ligand.atom_elements)


def test_adapter_view_hands_every_surface_the_same_coordinates(packet) -> None:
    legacy_view = packet.adapter_input(ENGINE_SURFACE_LEGACY_PRODUCT)
    v2_view = packet.adapter_input(ENGINE_SURFACE_ENGINE_V2)
    oracle_view = packet.adapter_input(ENGINE_SURFACE_EXTERNAL_ORACLE)

    assert legacy_view["ligand_conformer_coordinates"]
    assert legacy_view["ligand_conformer_coordinates"] == v2_view["ligand_conformer_coordinates"]
    assert legacy_view["ligand_conformer_coordinates"] == oracle_view["ligand_conformer_coordinates"]
    assert legacy_view["ligand_atom_elements"] == v2_view["ligand_atom_elements"]


def test_ligand_input_hash_tracks_the_frozen_coordinates(packet) -> None:
    from dataclasses import replace

    shifted = tuple(
        tuple((x + 1.0, y, z) for (x, y, z) in conformer)
        for conformer in packet.ligand.conformer_coordinates
    )
    moved = replace(packet.ligand, conformer_coordinates=shifted)

    assert moved.input_hash != packet.ligand.input_hash


def test_three_surfaces_run_on_one_prepared_input(three_surface_record, packet) -> None:
    payload = three_surface_record.to_dict()
    surfaces = sorted(payload["results"])

    assert payload["status"] == "shadow_execution_ready"
    assert payload["violations"] == []
    assert surfaces == sorted(
        [
            ENGINE_SURFACE_ENGINE_V2,
            ENGINE_SURFACE_EXTERNAL_ORACLE,
            ENGINE_SURFACE_LEGACY_PRODUCT,
        ]
    )
    assert {
        bundle.prepared_input_hash for bundle in three_surface_record.bundles
    } == {packet.prepared_input_hash}


def test_three_surfaces_produce_three_pairwise_deltas(three_surface_record) -> None:
    payload = three_surface_record.to_dict()

    assert payload["comparison"]["comparable"] is True
    assert len(payload["pairwise_deltas"]) == 3


def test_active_surface_is_legacy_and_shadows_are_never_promoted(
    three_surface_record,
) -> None:
    payload = three_surface_record.to_dict()

    assert payload["active_engine_surface"] == ACTIVE_SURFACE == ENGINE_SURFACE_LEGACY_PRODUCT
    assert payload["claim_promotion_allowed"] is False
    assert sorted(payload["shadow_result_surfaces"]) == sorted(
        [ENGINE_SURFACE_ENGINE_V2, ENGINE_SURFACE_EXTERNAL_ORACLE]
    )


def test_oracle_abstains_when_no_baseline_binary_is_installed(packet) -> None:
    bundle = run_external_oracle_adapter(packet)
    present = available_external_oracle_binaries()

    assert bundle.engine_version == EXTERNAL_ORACLE_ADAPTER_VERSION
    assert bundle.evidence_receipts["offline_only"] is True
    assert bundle.evidence_receipts["installs_binaries"] is False
    assert bundle.uncertainty["required_binaries"] == list(EXTERNAL_ORACLE_BINARIES)
    if present:
        assert bundle.uncertainty["available_binaries"] == list(present)
    else:
        assert bundle.abstained is True
        assert bundle.poses == ()
        assert "external_oracle_binary_unavailable_offline" in bundle.blockers
        assert bundle.failure_denominator.abstained_case_count == 1
        assert bundle.failure_denominator.accounted is True


def test_oracle_abstention_is_visible_in_the_pairwise_deltas(three_surface_record) -> None:
    deltas = three_surface_record.to_dict()["pairwise_deltas"]
    oracle_pairs = [
        delta
        for delta in deltas
        if ENGINE_SURFACE_EXTERNAL_ORACLE
        in (delta["left_engine_surface"], delta["right_engine_surface"])
    ]

    assert len(oracle_pairs) == 2
    for delta in oracle_pairs:
        # An abstaining oracle must not contribute a fabricated score delta.
        assert delta["top_score_delta"] is None
        assert delta["left_abstained"] or delta["right_abstained"]


def test_serving_a_shadow_surface_is_a_violation(packet) -> None:
    record = build_shadow_execution_record(
        packet=packet,
        bundles=[
            run_legacy_adapter(packet),
            run_engine_v2_adapter(packet),
            run_external_oracle_adapter(packet),
        ],
        served_engine_surface=ENGINE_SURFACE_ENGINE_V2,
    )

    assert record.ready is False
    assert (
        f"shadow_surface_cannot_be_served:{ENGINE_SURFACE_ENGINE_V2}" in record.violations
    )


def test_run_is_deterministic_across_repeated_executions(packet) -> None:
    first = build_shadow_execution_record(
        packet=packet,
        bundles=[
            run_legacy_adapter(packet),
            run_engine_v2_adapter(packet),
            run_external_oracle_adapter(packet),
        ],
    ).to_dict()
    second = build_shadow_execution_record(
        packet=packet,
        bundles=[
            run_legacy_adapter(packet),
            run_engine_v2_adapter(packet),
            run_external_oracle_adapter(packet),
        ],
    ).to_dict()

    assert first["pairwise_deltas"] == second["pairwise_deltas"]
