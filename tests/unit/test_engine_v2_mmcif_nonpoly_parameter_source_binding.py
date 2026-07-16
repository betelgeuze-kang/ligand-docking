from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import stat

import pytest

from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_parameter_source_binding import (
    MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_DOCUMENT_SCHEMA_ID,
    MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_LIMITATIONS,
    MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROFILE_ID,
    bind_reviewed_parameter_source_to_all_atom_snapshot,
    mmcif_nonpoly_parameter_source_binding_document,
    mmcif_nonpoly_parameter_source_binding_json_bytes,
    parse_mmcif_nonpoly_parameter_source_bindings,
    require_mmcif_nonpoly_parameter_source_binding_document,
    write_mmcif_nonpoly_parameter_source_binding_json,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_all_atom_systems import (
    parse_mmcif_nonpoly_all_atom_systems,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_preparation_corpus import (
    mmcif_nonpoly_preparation_corpus_cases,
)
from betelgeuze_engine_v2.parameter_source_provenance import (
    PARAMETER_SOURCE_ARTIFACT_SHA256,
    PARAMETER_SOURCE_LICENSE_SPDX_ID,
    reviewed_parameter_source_provenance,
)


def _case_source(case_id: str) -> str:
    return next(
        row.source_text
        for row in mmcif_nonpoly_preparation_corpus_cases()
        if row.case_id == case_id
    )


def test_reviewed_source_identity_is_bound_without_parameter_assignment() -> None:
    snapshot = parse_mmcif_nonpoly_parameter_source_bindings(
        _case_source("supported_single_coh")
    )

    assert snapshot.bound_system_count == 2
    assert snapshot.unbound_system_count == 0
    provenance = reviewed_parameter_source_provenance()
    for report in snapshot.instance_reports:
        assert report.binding_status == (
            "reviewed_parameter_source_identity_bound_to_system"
        )
        assert report.binding_blockers == ()
        assert report.limitations == MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_LIMITATIONS
        system = report.bound_system
        assert system is not None
        binding = system.metadata["parameter_source_binding"]
        assert binding["parameter_source_id"] == provenance.source_id
        assert binding["parameter_source_version"] == provenance.source_version
        assert binding["parameter_source_artifact_sha256"] == (
            PARAMETER_SOURCE_ARTIFACT_SHA256
        )
        assert binding["parameter_source_license_spdx_id"] == (
            PARAMETER_SOURCE_LICENSE_SPDX_ID
        )
        assert binding["candidate_scope"] == (
            "neutral_acyclic_coh_preparation_graph_only"
        )
        assert binding["parameter_assignment_status"] == "not_implemented"
        assert binding["partial_charge_assignment_status"] == "not_implemented"
        assert system.provenance.metadata["parameter_source_bound"] is True
        assert system.provenance.metadata["parameter_assignment_implemented"] is False
        assert system.provenance.chemistry_validated is False
        assert system.provenance.scientifically_validated is False
        assert all(atom.partial_charge_e is None for atom in system.atoms)
        assert all(atom.mass_da is None for atom in system.atoms)
        assert report.bound_system_sha256 == canonical_system_sha256(system)
        assert report.source_system_sha256 != report.bound_system_sha256


def test_unavailable_systems_remain_failure_complete() -> None:
    snapshot = parse_mmcif_nonpoly_parameter_source_bindings(
        _case_source("unprepared_intercomponent_covalent")
    )

    assert snapshot.bound_system_count == 0
    assert snapshot.unbound_system_count == 2
    for report in snapshot.instance_reports:
        assert report.binding_status == "not_bound_canonical_system_unavailable"
        assert report.binding_blockers
        assert report.limitations == ()
        assert report.source_system_sha256 == ""
        assert report.binding_sha256 == ""
        assert report.bound_system is None


def test_candidate_scope_check_fails_closed_before_binding() -> None:
    parent = parse_mmcif_nonpoly_all_atom_systems(
        _case_source("supported_single_coh")
    )
    first = parent.instance_reports[0]
    assert first.system is not None
    atoms = list(first.system.atoms)
    atoms[0] = replace(atoms[0], element="N", atomic_number=7)
    outside_scope_system = replace(first.system, atoms=tuple(atoms))
    changed_report = replace(first, system=outside_scope_system)
    changed_parent = replace(
        parent,
        instance_reports=(changed_report, *parent.instance_reports[1:]),
    )

    snapshot = bind_reviewed_parameter_source_to_all_atom_snapshot(changed_parent)
    report = snapshot.instance_reports[0]
    assert report.binding_status == "not_bound_outside_reviewed_candidate_scope"
    assert report.binding_blockers == ("element_outside_reviewed_candidate_scope",)
    assert report.bound_system is None
    assert report.source_system_sha256 == canonical_system_sha256(outside_scope_system)


def test_canonical_document_verifies_parent_evidence_and_rejects_tampering() -> None:
    snapshot = parse_mmcif_nonpoly_parameter_source_bindings(
        _case_source("supported_source_hydrogen")
    )
    document = mmcif_nonpoly_parameter_source_binding_document(snapshot)

    assert document["schema_id"] == (
        MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_DOCUMENT_SCHEMA_ID
    )
    assert document["profile_id"] == MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROFILE_ID
    assert json.loads(mmcif_nonpoly_parameter_source_binding_json_bytes(snapshot)) == document
    assert require_mmcif_nonpoly_parameter_source_binding_document(document) is document

    tampered = deepcopy(document)
    tampered["binding_projection"]["instance_reports"][0][
        "binding_status"
    ] = "parameter_assignment_complete"
    with pytest.raises(ValueError, match="identity|digest|status"):
        require_mmcif_nonpoly_parameter_source_binding_document(tampered)

    promoted = deepcopy(document)
    promoted["parameter_assignment_implemented"] = True
    with pytest.raises(ValueError, match="claim boundary"):
        require_mmcif_nonpoly_parameter_source_binding_document(promoted)


def test_private_atomic_writer_round_trips(tmp_path: Path) -> None:
    snapshot = parse_mmcif_nonpoly_parameter_source_bindings(
        _case_source("supported_single_coh")
    )
    path = write_mmcif_nonpoly_parameter_source_binding_json(
        tmp_path / "nested" / "binding.json", snapshot
    )

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    payload = json.loads(path.read_text(encoding="ascii"))
    assert require_mmcif_nonpoly_parameter_source_binding_document(payload) is payload


def test_public_export_and_workflow_integration() -> None:
    from betelgeuze_engine_v2 import molecular

    assert molecular.MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROFILE_ID == (
        MMCIF_NONPOLY_PARAMETER_SOURCE_BINDING_PROFILE_ID
    )
    assert molecular.parse_mmcif_nonpoly_parameter_source_bindings is (
        parse_mmcif_nonpoly_parameter_source_bindings
    )

    root = Path(__file__).resolve().parents[2]
    dedicated = (
        root
        / ".github/workflows/ci-engine-v2-mmcif-nonpoly-parameter-source-binding.yml"
    ).read_text(encoding="utf-8")
    for workflow in (
        ".github/workflows/ci-engine-v2-main.yml",
        ".github/workflows/ci-engine-v2-mmcif-nonpoly-all-atom-systems.yml",
        ".github/workflows/ci-engine-v2-mmcif-nonpoly-preparation-corpus.yml",
        ".github/workflows/ci-engine-v2-parameter-source-provenance.yml",
    ):
        text = (root / workflow).read_text(encoding="utf-8")
        assert "mmcif_nonpoly_parameter_source_binding.py" in text
        assert "test_engine_v2_mmcif_nonpoly_parameter_source_binding.py" in text
    assert "test_engine_v2_mmcif_nonpoly_parameter_source_binding.py" in dedicated
    assert "tools/check_engine_v2_architecture.py" in dedicated
