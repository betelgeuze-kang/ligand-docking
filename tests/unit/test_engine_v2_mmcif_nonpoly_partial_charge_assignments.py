from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import stat
import struct

import pytest

from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_parameter_source_binding import (
    parse_mmcif_nonpoly_parameter_source_bindings,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_partial_charge_assignments import (
    MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_DOCUMENT_SCHEMA_ID,
    MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_LIMITATIONS,
    MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROFILE_ID,
    MmcifNonpolyPartialChargeAssignmentError,
    MmcifNonpolyPartialChargeAssignmentInput,
    apply_explicit_mmcif_nonpoly_partial_charge_assignments,
    mmcif_nonpoly_partial_charge_assignment_document,
    mmcif_nonpoly_partial_charge_assignment_json_bytes,
    require_mmcif_nonpoly_partial_charge_assignment_document,
    write_mmcif_nonpoly_partial_charge_assignment_json,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_preparation_corpus import (
    mmcif_nonpoly_preparation_corpus_cases,
)


_METHOD_DIGEST = hashlib.sha256(
    b"synthetic-neutral-explicit-charge-contract-fixture-v1\n"
).hexdigest()


def _case_source(case_id: str) -> str:
    return next(
        row.source_text
        for row in mmcif_nonpoly_preparation_corpus_cases()
        if row.case_id == case_id
    )


def _records(binding, *, nonzero_first: bool = False):
    records = []
    for report in binding.instance_reports:
        system = report.bound_system
        if system is None:
            continue
        charges = [0.0] * system.atom_count
        if nonzero_first and system.atom_count >= 2:
            charges[0] = 0.125
            charges[1] = -0.125
        records.append(
            MmcifNonpolyPartialChargeAssignmentInput(
                instance_identity_sha256=report.instance_identity_sha256,
                source_system_sha256=canonical_system_sha256(system),
                method_id="synthetic_explicit_charge_contract_fixture",
                method_version="1.0.0",
                method_provenance_sha256=_METHOD_DIGEST,
                charges_e=tuple(charges),
                expected_total_charge_e=0.0,
            )
        )
    return tuple(records)


def _bits(value: float) -> str:
    return struct.pack(">d", value).hex()


def test_explicit_vectors_are_applied_in_exact_atom_order_without_promotion() -> None:
    binding = parse_mmcif_nonpoly_parameter_source_bindings(
        _case_source("supported_single_coh")
    )
    snapshot = apply_explicit_mmcif_nonpoly_partial_charge_assignments(
        binding, _records(binding, nonzero_first=True)
    )

    assert snapshot.assigned_system_count == 2
    assert snapshot.unassigned_system_count == 0
    for report in snapshot.instance_reports:
        assert report.assignment_status == "explicit_partial_charge_vector_assigned"
        assert report.assignment_blockers == ()
        assert report.limitations == MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_LIMITATIONS
        record = report.assignment_input
        system = report.assigned_system
        assert record is not None
        assert system is not None
        assert math.fsum(atom.partial_charge_e for atom in system.atoms) == pytest.approx(
            0.0, abs=1.0e-12
        )
        assert tuple(atom.partial_charge_e for atom in system.atoms) == record.charges_e
        for atom, charge in zip(system.atoms, record.charges_e, strict=True):
            assert atom.metadata["partial_charge_binary64_bits_hex"] == _bits(charge)
            assert atom.metadata["partial_charge_assignment_input_sha256"] == (
                record.assignment_input_sha256
            )
            assert atom.metadata["partial_charge_scientifically_validated"] is False
        assert system.provenance.metadata["partial_charge_assigned"] is True
        assert system.provenance.metadata["partial_charge_values_calibrated"] is False
        assert system.provenance.chemistry_validated is False
        assert system.provenance.scientifically_validated is False
        assert all(atom.mass_da is None for atom in system.atoms)
        assert report.source_system_sha256 != report.assigned_system_sha256


def test_missing_and_unavailable_records_are_failure_complete() -> None:
    supported_binding = parse_mmcif_nonpoly_parameter_source_bindings(
        _case_source("supported_single_coh")
    )
    missing = apply_explicit_mmcif_nonpoly_partial_charge_assignments(
        supported_binding, ()
    )
    assert missing.assigned_system_count == 0
    assert all(
        report.assignment_status == "not_assigned_explicit_charge_record_missing"
        for report in missing.instance_reports
    )
    assert all(
        report.assignment_blockers == ("explicit_partial_charge_record_missing",)
        for report in missing.instance_reports
    )
    assert require_mmcif_nonpoly_partial_charge_assignment_document(
        mmcif_nonpoly_partial_charge_assignment_document(missing)
    )

    unavailable_binding = parse_mmcif_nonpoly_parameter_source_bindings(
        _case_source("unprepared_intercomponent_covalent")
    )
    unavailable = apply_explicit_mmcif_nonpoly_partial_charge_assignments(
        unavailable_binding, ()
    )
    assert unavailable.assigned_system_count == 0
    assert all(
        report.assignment_status
        == "not_assigned_parameter_bound_system_unavailable"
        for report in unavailable.instance_reports
    )
    assert all(report.assignment_blockers for report in unavailable.instance_reports)
    assert require_mmcif_nonpoly_partial_charge_assignment_document(
        mmcif_nonpoly_partial_charge_assignment_document(unavailable)
    )


def test_vector_length_total_and_system_crosswires_fail_closed() -> None:
    binding = parse_mmcif_nonpoly_parameter_source_bindings(
        _case_source("supported_source_hydrogen")
    )
    record = _records(binding)[0]

    with pytest.raises(
        MmcifNonpolyPartialChargeAssignmentError,
        match="charge_vector_length_mismatch",
    ):
        apply_explicit_mmcif_nonpoly_partial_charge_assignments(
            binding, (replace(record, charges_e=record.charges_e[:-1]),)
        )

    unbalanced = list(record.charges_e)
    unbalanced[0] = 0.25
    with pytest.raises(
        MmcifNonpolyPartialChargeAssignmentError,
        match="partial_charge_total_mismatch",
    ):
        apply_explicit_mmcif_nonpoly_partial_charge_assignments(
            binding, (replace(record, charges_e=tuple(unbalanced)),)
        )

    with pytest.raises(
        MmcifNonpolyPartialChargeAssignmentError,
        match="source_system_crosswire",
    ):
        apply_explicit_mmcif_nonpoly_partial_charge_assignments(
            binding, (replace(record, source_system_sha256="0" * 64),)
        )

    with pytest.raises(
        MmcifNonpolyPartialChargeAssignmentError,
        match="nonfinite_charge_value",
    ):
        replace(record, charges_e=(float("nan"), *record.charges_e[1:]))


def test_document_round_trips_and_rejects_value_or_claim_tampering() -> None:
    binding = parse_mmcif_nonpoly_parameter_source_bindings(
        _case_source("supported_single_coh")
    )
    snapshot = apply_explicit_mmcif_nonpoly_partial_charge_assignments(
        binding, _records(binding, nonzero_first=True)
    )
    document = mmcif_nonpoly_partial_charge_assignment_document(snapshot)

    assert document["schema_id"] == (
        MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_DOCUMENT_SCHEMA_ID
    )
    assert document["profile_id"] == MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROFILE_ID
    assert json.loads(mmcif_nonpoly_partial_charge_assignment_json_bytes(snapshot)) == document
    assert require_mmcif_nonpoly_partial_charge_assignment_document(document) is document

    tampered = deepcopy(document)
    tampered["assignment_projection"]["instance_reports"][0]["assignment_input"][
        "charges_e"
    ][0] = 0.5
    with pytest.raises(ValueError, match="identity|evidence"):
        require_mmcif_nonpoly_partial_charge_assignment_document(tampered)

    promoted = deepcopy(document)
    promoted["scientifically_validated"] = True
    with pytest.raises(ValueError, match="claim boundary"):
        require_mmcif_nonpoly_partial_charge_assignment_document(promoted)


def test_private_atomic_writer_round_trips(tmp_path: Path) -> None:
    binding = parse_mmcif_nonpoly_parameter_source_bindings(
        _case_source("supported_single_coh")
    )
    snapshot = apply_explicit_mmcif_nonpoly_partial_charge_assignments(
        binding, _records(binding)
    )
    path = write_mmcif_nonpoly_partial_charge_assignment_json(
        tmp_path / "nested" / "charges.json", snapshot
    )

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    payload = json.loads(path.read_text(encoding="ascii"))
    assert require_mmcif_nonpoly_partial_charge_assignment_document(payload) is payload


def test_public_export_and_workflow_integration() -> None:
    from betelgeuze_engine_v2 import molecular

    assert molecular.MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROFILE_ID == (
        MMCIF_NONPOLY_PARTIAL_CHARGE_ASSIGNMENT_PROFILE_ID
    )
    assert molecular.apply_explicit_mmcif_nonpoly_partial_charge_assignments is (
        apply_explicit_mmcif_nonpoly_partial_charge_assignments
    )

    root = Path(__file__).resolve().parents[2]
    dedicated = (
        root / ".github/workflows/ci-engine-v2-mmcif-nonpoly-partial-charges.yml"
    ).read_text(encoding="utf-8")
    for workflow in (
        ".github/workflows/ci-engine-v2-main.yml",
        ".github/workflows/ci-engine-v2-mmcif-nonpoly-parameter-source-binding.yml",
        ".github/workflows/ci-engine-v2-mmcif-nonpoly-preparation-corpus.yml",
    ):
        text = (root / workflow).read_text(encoding="utf-8")
        assert "mmcif_nonpoly_partial_charge_assignments.py" in text
        assert "test_engine_v2_mmcif_nonpoly_partial_charge_assignments.py" in text
    assert "test_engine_v2_mmcif_nonpoly_partial_charge_assignments.py" in dedicated
    assert "tools/check_engine_v2_architecture.py" in dedicated
