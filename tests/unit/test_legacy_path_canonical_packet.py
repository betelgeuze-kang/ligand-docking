"""The active legacy path must consume the canonical preparation packet (P1-1).

Before this was pinned, the legacy product path parsed the receptor and detected
the pocket itself, while the engine adapters used the canonical preparation
service. Any legacy-vs-V2 difference could therefore be explained by the two
surfaces having been handed different atoms or a different pocket, which is
exactly the ambiguity the packet exists to remove.
"""

from __future__ import annotations

import pytest

from betelgeuze_product.docking_request import _pose_generation_contract
from betelgeuze_product.legacy_input_contract import (
    REASON_INVALID_COORDINATE,
    LegacyInputPolicy,
)
from betelgeuze_product.preparation_service import prepare_receptor

STRICT = LegacyInputPolicy()
COMPAT = LegacyInputPolicy(compatibility_mode=True)

PDB_TEXT_CA_GRID = "".join(
    "ATOM  {index:5d}  CA  ALA A{resid:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C\n".format(
        index=i + 1,
        resid=i + 1,
        x=(i % 4) * 3.8,
        y=(i // 4) * 3.8,
        z=0.0,
    )
    for i in range(12)
)

PDB_TEXT_CA_GRID_MALFORMED = PDB_TEXT_CA_GRID + (
    "ATOM     13  CA  ALA A  13        nope   1.000   2.000  1.00  0.00           C\n"
)


def _contract(pdb_text: str, policy: LegacyInputPolicy = STRICT) -> dict:
    return _pose_generation_contract(
        {"pdb_content": pdb_text}, {}, legacy_input_policy=policy
    )


def test_legacy_contract_declares_canonical_packet_use() -> None:
    contract = _contract(PDB_TEXT_CA_GRID)

    assert contract["canonical_preparation_packet_used"] is True
    assert contract["prepared_receptor_status"] == "prepared_receptor_ready"
    assert contract["prepared_receptor_atom_count"] == 12
    assert contract["prepared_receptor_blockers"] == []


def test_legacy_pocket_matches_the_canonical_receptor_packet() -> None:
    contract = _contract(PDB_TEXT_CA_GRID)
    receptor = prepare_receptor({"pdb_content": PDB_TEXT_CA_GRID})
    pocket = receptor.pocket

    assert contract["pocket_detection_available"] is pocket.ready
    assert contract["pocket_method"] == pocket.method
    assert contract["pocket_center"] == [float(value) for value in pocket.center]
    assert contract["pocket_radius_a"] == pytest.approx(float(pocket.radius_a))


def test_legacy_contract_reports_the_prepared_input_hash() -> None:
    contract = _contract(PDB_TEXT_CA_GRID)
    receptor = prepare_receptor({"pdb_content": PDB_TEXT_CA_GRID})

    # The hash is what ties a served legacy result back to a specific prepared
    # input, so it must be the adapters' hash rather than a private one.
    assert contract["prepared_receptor_input_hash"] == receptor.input_hash


def test_malformed_intake_still_fails_closed_through_the_packet() -> None:
    contract = _contract(PDB_TEXT_CA_GRID_MALFORMED)

    assert contract["legacy_input_blocked"] is True
    assert contract["legacy_input_reason_code"] == REASON_INVALID_COORDINATE
    assert contract["legacy_input_reason"]
    assert contract["pocket_detection_available"] is False
    assert contract["pocket_method"] == ""
    assert contract["prepared_receptor_status"] == "blocked_prepared_receptor"


def test_compatibility_mode_reaches_the_same_packet_as_the_adapters() -> None:
    contract = _contract(PDB_TEXT_CA_GRID_MALFORMED, COMPAT)
    receptor = prepare_receptor(
        {"pdb_content": PDB_TEXT_CA_GRID_MALFORMED},
        legacy_input_compatibility_mode=True,
    )

    assert contract["legacy_input_blocked"] is False
    assert contract["pocket_detection_available"] is True
    assert contract["prepared_receptor_input_hash"] == receptor.input_hash


def test_absent_structure_is_a_preview_state_not_a_failure() -> None:
    contract = _pose_generation_contract({}, {}, legacy_input_policy=STRICT)

    assert contract["legacy_input_blocked"] is False
    assert contract["pocket_detection_available"] is False
    assert contract["prepared_receptor_status"] == ""
    assert contract["prepared_receptor_input_hash"] == ""


def test_unreadable_structure_path_does_not_fabricate_a_pocket() -> None:
    contract = _pose_generation_contract(
        {"pdb_path": "does/not/exist.pdb"}, {}, legacy_input_policy=STRICT
    )

    assert contract["pocket_detection_available"] is False
    assert contract["prepared_receptor_status"] == ""


def test_contract_keeps_execution_disabled_regardless_of_preparation() -> None:
    for text in (PDB_TEXT_CA_GRID, PDB_TEXT_CA_GRID_MALFORMED, ""):
        contract = _pose_generation_contract(
            {"pdb_content": text}, {}, legacy_input_policy=STRICT
        )

        assert contract["execution_enabled"] is False
        assert contract["docking_results_emitted"] is False
