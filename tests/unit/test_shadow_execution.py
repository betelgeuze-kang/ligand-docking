"""Legacy / V2 / oracle shadow execution tests (P1-9)."""

from __future__ import annotations

import pytest

from betelgeuze_product.docking_result_bundle import (
    DockingResultBundle,
    FailureDenominator,
    PoseRecord,
)
from betelgeuze_product.preparation_packet import (
    ENGINE_SURFACE_ENGINE_V2,
    ENGINE_SURFACE_EXTERNAL_ORACLE,
    ENGINE_SURFACE_LEGACY_PRODUCT,
)
from betelgeuze_product.preparation_service import build_preparation_packet
from betelgeuze_product.shadow_execution import (
    ACTIVE_SURFACE,
    SHADOW_EXECUTION_SCHEMA_VERSION,
    SHADOW_ONLY_SURFACES,
    STATUS_BLOCKED,
    STATUS_READY,
    build_shadow_execution_record,
)

pytest.importorskip("rdkit")


def _receptor_pdb(atom_count: int = 30) -> str:
    return "".join(
        "ATOM  %5d  CA  ALA A%4d    %8.3f%8.3f%8.3f  1.00  0.00           C\n"
        % (index, index, float(index), float(index % 3), 0.0)
        for index in range(1, atom_count + 1)
    )


@pytest.fixture(scope="module")
def packet():
    return build_preparation_packet(
        receptor_payload={"pdb_content": _receptor_pdb(), "target_id": "T1"},
        ligand_smiles="CCCCCCO",
        target_id="T1",
        ligand_id="L1",
        max_conformers=4,
        seed=7,
    )


def _bundle(packet, surface: str, score: float = -5.0, **overrides) -> DockingResultBundle:
    kwargs = {
        "engine_surface": surface,
        "engine_version": "1.0.0",
        "prepared_input_hash": packet.prepared_input_hash,
        "receptor_input_hash": packet.receptor.input_hash,
        "ligand_input_hash": packet.ligand.input_hash,
        "pocket_identity": packet.receptor.pocket.as_dict(),
        "poses": (
            PoseRecord(
                pose_id="pose_1",
                rank=1,
                conformer_id="conf_1",
                cluster_id=0,
                total_score=score,
                per_term_score={"typed_steric_vdw": score},
                geometric_valid=True,
                chemistry_valid=True,
            ),
        ),
        "failure_denominator": FailureDenominator(10, 8, 1, 1),
        "runtime_seconds": 1.0,
        "candidate_budget": 100,
        "benchmark_profile": "frozen_profile_v1",
        "claim_scope": "restricted_internal",
    }
    kwargs.update(overrides)
    return DockingResultBundle(**kwargs)


def _record(packet, **overrides):
    bundles = overrides.pop(
        "bundles",
        [
            _bundle(packet, ENGINE_SURFACE_LEGACY_PRODUCT, -5.0),
            _bundle(packet, ENGINE_SURFACE_ENGINE_V2, -6.5),
            _bundle(packet, ENGINE_SURFACE_EXTERNAL_ORACLE, -7.0),
        ],
    )
    return build_shadow_execution_record(packet=packet, bundles=bundles, **overrides)


def test_shadow_run_over_three_surfaces_is_ready(packet) -> None:
    payload = _record(packet).to_dict()

    assert payload["schema_version"] == SHADOW_EXECUTION_SCHEMA_VERSION
    assert payload["status"] == STATUS_READY
    assert payload["executed_surface_count"] == 3
    assert payload["violations"] == []


def test_legacy_is_active_and_the_others_are_shadow_only(packet) -> None:
    record = _record(packet)
    payload = record.to_dict()

    assert payload["active_engine_surface"] == ACTIVE_SURFACE == ENGINE_SURFACE_LEGACY_PRODUCT
    assert payload["active_result_present"] is True
    assert payload["shadow_only_surfaces"] == list(SHADOW_ONLY_SURFACES)
    assert set(payload["shadow_result_surfaces"]) == set(SHADOW_ONLY_SURFACES)
    assert record.active_bundle is not None
    assert record.active_bundle.engine_surface == ENGINE_SURFACE_LEGACY_PRODUCT


def test_a_better_scoring_shadow_result_is_never_promoted(packet) -> None:
    # V2 and the oracle both score better than legacy here.
    payload = _record(packet).to_dict()

    assert payload["claim_promotion_allowed"] is False
    assert payload["shadow_only_locked"] is True
    assert payload["active_engine_surface"] == ENGINE_SURFACE_LEGACY_PRODUCT


@pytest.mark.parametrize("surface", list(SHADOW_ONLY_SURFACES))
def test_serving_a_shadow_surface_is_a_violation(packet, surface: str) -> None:
    record = _record(packet, served_engine_surface=surface)

    assert record.status == STATUS_BLOCKED
    assert f"shadow_surface_cannot_be_served:{surface}" in record.violations


def test_pairwise_deltas_cover_every_surface_pair(packet) -> None:
    payload = _record(packet).to_dict()

    assert payload["comparison"]["comparable"] is True
    assert len(payload["pairwise_deltas"]) == 3


def test_all_surfaces_must_share_the_prepared_input(packet) -> None:
    record = _record(
        packet,
        bundles=[
            _bundle(packet, ENGINE_SURFACE_LEGACY_PRODUCT),
            _bundle(packet, ENGINE_SURFACE_ENGINE_V2, prepared_input_hash="other_hash"),
        ],
    )

    assert record.status == STATUS_BLOCKED
    assert f"prepared_input_hash_mismatch:{ENGINE_SURFACE_ENGINE_V2}" in record.violations


def test_missing_v2_shadow_surface_is_a_violation(packet) -> None:
    record = _record(packet, bundles=[_bundle(packet, ENGINE_SURFACE_LEGACY_PRODUCT)])

    assert record.status == STATUS_BLOCKED
    assert "v2_shadow_surface_missing" in record.violations


def test_missing_active_legacy_surface_is_a_violation(packet) -> None:
    record = _record(
        packet,
        bundles=[
            _bundle(packet, ENGINE_SURFACE_ENGINE_V2),
            _bundle(packet, ENGINE_SURFACE_EXTERNAL_ORACLE),
        ],
    )

    assert record.status == STATUS_BLOCKED
    assert "active_legacy_surface_missing" in record.violations
    assert record.active_bundle is None


def test_mismatched_candidate_budget_is_a_violation(packet) -> None:
    record = _record(
        packet,
        bundles=[
            _bundle(packet, ENGINE_SURFACE_LEGACY_PRODUCT),
            _bundle(packet, ENGINE_SURFACE_ENGINE_V2, candidate_budget=9000),
        ],
    )

    assert "mismatched_candidate_budget" in record.violations


def test_blocked_preparation_blocks_the_shadow_run() -> None:
    blocked_packet = build_preparation_packet(
        receptor_payload={"pdb_content": _receptor_pdb(), "target_id": "T1"},
        ligand_smiles="C1CCCCCCCCCCCC1",
        ligand_id="macro",
    )
    record = build_shadow_execution_record(
        packet=blocked_packet,
        bundles=[
            _bundle(blocked_packet, ENGINE_SURFACE_LEGACY_PRODUCT),
            _bundle(blocked_packet, ENGINE_SURFACE_ENGINE_V2),
        ],
    )

    assert record.status == STATUS_BLOCKED
    assert "prepared_input_not_ready" in record.violations


def test_duplicate_surface_is_a_violation(packet) -> None:
    record = _record(
        packet,
        bundles=[
            _bundle(packet, ENGINE_SURFACE_LEGACY_PRODUCT),
            _bundle(packet, ENGINE_SURFACE_LEGACY_PRODUCT),
            _bundle(packet, ENGINE_SURFACE_ENGINE_V2),
        ],
    )

    assert "duplicate_engine_surface" in record.violations


def test_payload_states_no_winner_declaration(packet) -> None:
    payload = _record(packet).to_dict()

    assert "never be promoted" in payload["claim_boundary"]
    assert "not a benchmark claim or a winner declaration" in payload["claim_boundary"]
