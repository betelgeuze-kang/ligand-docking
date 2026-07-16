from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat
import struct

import pytest

import betelgeuze_engine_v2.molecular.mmcif_nonpoly_all_atom_round_trip as module
from betelgeuze_engine_v2.molecular import (
    all_atom_system_from_canonical_json,
    canonical_coordinates_sha256,
    canonical_system_json_bytes,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_all_atom_round_trip import (
    MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_DOCUMENT_SCHEMA_ID,
    MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_LIMITATIONS,
    MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_PROFILE_ID,
    mmcif_nonpoly_all_atom_round_trip_document,
    mmcif_nonpoly_all_atom_round_trip_json_bytes,
    require_mmcif_nonpoly_all_atom_round_trip_document,
    verify_mmcif_nonpoly_all_atom_round_trips,
    write_mmcif_nonpoly_all_atom_round_trip_json,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_parameter_source_binding import (
    parse_mmcif_nonpoly_parameter_source_bindings,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_partial_charge_assignments import (
    MmcifNonpolyPartialChargeAssignmentInput,
    apply_explicit_mmcif_nonpoly_partial_charge_assignments,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_preparation_corpus import (
    mmcif_nonpoly_preparation_corpus_cases,
)


_METHOD_DIGEST = hashlib.sha256(b"round-trip-charge-fixture-v1\n").hexdigest()


def _case_source(case_id: str) -> str:
    return next(
        row.source_text
        for row in mmcif_nonpoly_preparation_corpus_cases()
        if row.case_id == case_id
    )


def _charged_snapshot(case_id: str, *, nonzero: bool = False):
    binding = parse_mmcif_nonpoly_parameter_source_bindings(_case_source(case_id))
    records = []
    for report in binding.instance_reports:
        system = report.bound_system
        if system is None:
            continue
        charges = [0.0] * system.atom_count
        if nonzero and system.atom_count >= 2:
            charges[0] = 0.375
            charges[1] = -0.375
        records.append(
            MmcifNonpolyPartialChargeAssignmentInput(
                instance_identity_sha256=report.instance_identity_sha256,
                source_system_sha256=canonical_system_sha256(system),
                method_id="round_trip_explicit_charge_fixture",
                method_version="1.0.0",
                method_provenance_sha256=_METHOD_DIGEST,
                charges_e=tuple(charges),
                expected_total_charge_e=0.0,
            )
        )
    return apply_explicit_mmcif_nonpoly_partial_charge_assignments(binding, records)


def _bits(value: float) -> str:
    return struct.pack(">d", value).hex()


def test_canonical_encode_decode_reencode_preserves_all_identity_hashes() -> None:
    charged = _charged_snapshot("supported_single_coh", nonzero=True)
    snapshot = verify_mmcif_nonpoly_all_atom_round_trips(charged)

    assert snapshot.verified_system_count == 2
    assert snapshot.unavailable_system_count == 0
    for parent, report in zip(
        charged.instance_reports, snapshot.instance_reports, strict=True
    ):
        system = parent.assigned_system
        assert system is not None
        encoded = canonical_system_json_bytes(system)
        decoded = all_atom_system_from_canonical_json(encoded.decode("ascii"))
        assert canonical_system_json_bytes(decoded) == encoded
        assert report.round_trip_status == (
            "canonical_all_atom_identity_round_trip_verified"
        )
        assert report.round_trip_blockers == ()
        assert report.limitations == MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_LIMITATIONS
        assert report.source_system_sha256 == canonical_system_sha256(system)
        assert report.round_trip_system_sha256 == canonical_system_sha256(decoded)
        assert report.canonical_json_sha256 == hashlib.sha256(encoded).hexdigest()
        assert report.round_trip_json_sha256 == report.canonical_json_sha256
        assert report.canonical_json_byte_count == len(encoded)
        assert report.topology_sha256 == canonical_topology_sha256(system)
        assert report.coordinates_sha256 == canonical_coordinates_sha256(system)
        assert report.canonical_reencoding_byte_identical is True
        assert report.identity_projection_sha256


def test_source_lineage_parameter_binding_and_charge_bits_survive_round_trip() -> None:
    charged = _charged_snapshot("supported_source_hydrogen", nonzero=True)
    system = next(
        report.assigned_system
        for report in charged.instance_reports
        if report.component_id == "LIG"
    )
    assert system is not None
    decoded = all_atom_system_from_canonical_json(
        canonical_system_json_bytes(system).decode("ascii")
    )

    assert decoded.metadata["instance_identity_sha256"] == (
        system.metadata["instance_identity_sha256"]
    )
    assert decoded.metadata["parameter_source_binding_sha256"] == (
        system.metadata["parameter_source_binding_sha256"]
    )
    assert decoded.metadata["partial_charge_assignment_input_sha256"] == (
        system.metadata["partial_charge_assignment_input_sha256"]
    )
    for source_atom, round_tripped_atom in zip(
        system.atoms, decoded.atoms, strict=True
    ):
        assert round_tripped_atom.metadata == source_atom.metadata
        assert _bits(round_tripped_atom.partial_charge_e) == _bits(
            source_atom.partial_charge_e
        )
        assert round_tripped_atom.metadata["prepared_atom_identity_sha256"]
        assert round_tripped_atom.metadata["coordinate_identity_sha256"]


def test_unavailable_charge_assigned_systems_remain_failure_complete() -> None:
    charged = _charged_snapshot("unprepared_intercomponent_covalent")
    snapshot = verify_mmcif_nonpoly_all_atom_round_trips(charged)

    assert snapshot.verified_system_count == 0
    assert snapshot.unavailable_system_count == 2
    for report in snapshot.instance_reports:
        assert report.round_trip_status == (
            "not_round_tripped_charge_assigned_system_unavailable"
        )
        assert report.round_trip_blockers
        assert report.limitations == ()
        assert report.canonical_json_byte_count == 0
        assert report.source_system_sha256 == ""
        assert report.canonical_reencoding_byte_identical is False
    assert require_mmcif_nonpoly_all_atom_round_trip_document(
        mmcif_nonpoly_all_atom_round_trip_document(snapshot)
    )


def test_receipt_round_trips_and_rejects_hash_or_claim_tampering() -> None:
    snapshot = verify_mmcif_nonpoly_all_atom_round_trips(
        _charged_snapshot("supported_single_coh", nonzero=True)
    )
    document = mmcif_nonpoly_all_atom_round_trip_document(snapshot)

    assert document["schema_id"] == (
        MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_DOCUMENT_SCHEMA_ID
    )
    assert document["profile_id"] == MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_PROFILE_ID
    assert json.loads(mmcif_nonpoly_all_atom_round_trip_json_bytes(snapshot)) == document
    assert require_mmcif_nonpoly_all_atom_round_trip_document(document) is document

    tampered = deepcopy(document)
    tampered["round_trip_projection"]["instance_reports"][0][
        "topology_sha256"
    ] = "0" * 64
    with pytest.raises(ValueError, match="identity|receipt"):
        require_mmcif_nonpoly_all_atom_round_trip_document(tampered)

    resealed = deepcopy(document)
    resealed["round_trip_projection"]["instance_reports"][0][
        "topology_sha256"
    ] = "0" * 64
    resealed["round_trip_projection_sha256"] = module._sha256(
        resealed["round_trip_projection"]
    )
    resealed["snapshot_sha256"] = module._sha256(
        {
            "schema_id": MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_DOCUMENT_SCHEMA_ID,
            "partial_charge_assignment_snapshot_sha256": resealed[
                "partial_charge_assignment_snapshot_sha256"
            ],
            "round_trip_projection_sha256": resealed[
                "round_trip_projection_sha256"
            ],
            "claim_policy": module._claim_policy(),
        }
    )
    with pytest.raises(ValueError, match="receipt mismatch"):
        require_mmcif_nonpoly_all_atom_round_trip_document(resealed)

    promoted = deepcopy(document)
    promoted["original_mmcif_text_re_emitted"] = True
    with pytest.raises(ValueError, match="claim boundary"):
        require_mmcif_nonpoly_all_atom_round_trip_document(promoted)


def test_private_atomic_writer_round_trips(tmp_path: Path) -> None:
    snapshot = verify_mmcif_nonpoly_all_atom_round_trips(
        _charged_snapshot("supported_single_coh")
    )
    path = write_mmcif_nonpoly_all_atom_round_trip_json(
        tmp_path / "nested" / "round-trip.json", snapshot
    )

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    payload = json.loads(path.read_text(encoding="ascii"))
    assert require_mmcif_nonpoly_all_atom_round_trip_document(payload) is payload


def test_public_export_and_workflow_integration() -> None:
    from betelgeuze_engine_v2 import molecular

    assert molecular.MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_PROFILE_ID == (
        MMCIF_NONPOLY_ALL_ATOM_ROUND_TRIP_PROFILE_ID
    )
    assert molecular.verify_mmcif_nonpoly_all_atom_round_trips is (
        verify_mmcif_nonpoly_all_atom_round_trips
    )

    root = Path(__file__).resolve().parents[2]
    dedicated = (
        root / ".github/workflows/ci-engine-v2-mmcif-nonpoly-all-atom-round-trip.yml"
    ).read_text(encoding="utf-8")
    for workflow in (
        ".github/workflows/ci-engine-v2-main.yml",
        ".github/workflows/ci-engine-v2-mmcif-nonpoly-partial-charges.yml",
        ".github/workflows/ci-engine-v2-mmcif-nonpoly-preparation-corpus.yml",
    ):
        text = (root / workflow).read_text(encoding="utf-8")
        assert "mmcif_nonpoly_all_atom_round_trip.py" in text
        assert "test_engine_v2_mmcif_nonpoly_all_atom_round_trip.py" in text
    assert "test_engine_v2_mmcif_nonpoly_all_atom_round_trip.py" in dedicated
    assert "tools/check_engine_v2_architecture.py" in dedicated
