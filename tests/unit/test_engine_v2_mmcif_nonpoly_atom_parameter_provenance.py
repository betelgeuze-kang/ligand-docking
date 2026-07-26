from __future__ import annotations

import json
from pathlib import Path
import stat

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.molecular import (  # noqa: E402
    mmcif_nonpoly_atom_parameter_provenance as provenance,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    mmcif_nonpoly_preparation_corpus as corpus_module,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_atom_parameter_provenance import (  # noqa: E402
    MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_BLOCKERS,
    MMCIF_NONPOLY_ATOM_PARAMETER_VALUE_IDS,
    MmcifNonpolyAtomParameterProvenanceError,
    parse_mmcif_nonpoly_atom_parameter_provenance,
    require_mmcif_nonpoly_atom_parameter_provenance_document,
    trace_mmcif_nonpoly_atom_parameter_provenance,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_parameter_source_binding import (  # noqa: E402
    parse_mmcif_nonpoly_parameter_source_bindings,
)
from betelgeuze_engine_v2.parameter_source_provenance import (  # noqa: E402
    PARAMETER_SOURCE_ARTIFACT_SHA256,
    PARAMETER_SOURCE_ID,
    PARAMETER_SOURCE_VERSION,
)


def _bound_case_source() -> str:
    for case in corpus_module.mmcif_nonpoly_preparation_corpus_cases():
        binding = parse_mmcif_nonpoly_parameter_source_bindings(case.source_text)
        if any(row.source_bound for row in binding.instance_reports):
            return case.source_text
    raise AssertionError("corpus has no source-bound case")


@pytest.fixture(scope="module")
def snapshot() -> object:
    return parse_mmcif_nonpoly_atom_parameter_provenance(_bound_case_source())


def test_every_atom_carries_declared_provenance_and_stays_claim_closed(
    snapshot: object,
) -> None:
    payload = snapshot.to_dict()  # type: ignore[attr-defined]

    assert payload["instance_count"] >= 1
    assert payload["traced_instance_count"] >= 1
    assert payload["atom_count"] >= 1
    assert payload["declared_provenance_atom_count"] == payload["atom_count"]
    assert payload["per_atom_declared_provenance_complete"] is True
    assert payload["per_atom_absence_ledger_complete"] is True
    assert payload["smirnoff_semantics_parsed"] is False
    assert payload["parameter_values_assigned"] is False
    assert payload["partial_charges_assigned"] is False
    assert payload["atom_masses_assigned"] is False
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False
    assert list(payload["scientific_blockers"]) == list(
        MMCIF_NONPOLY_ATOM_PARAMETER_PROVENANCE_BLOCKERS
    )


def test_absence_ledger_names_every_missing_per_atom_value(
    snapshot: object,
) -> None:
    payload = snapshot.to_dict()  # type: ignore[attr-defined]
    atom_rows = [
        row
        for instance in payload["instance_reports"]
        for row in instance["atom_rows"]
    ]
    assert atom_rows
    assert payload["assigned_value_atom_count"] == 0
    assert payload["fully_absent_value_atom_count"] == payload["atom_count"]

    for row in atom_rows:
        assert row["declared_provenance_present"] is True
        assert row["declared_parameter_source_id"] == PARAMETER_SOURCE_ID
        assert row["declared_parameter_source_version"] == PARAMETER_SOURCE_VERSION
        assert row["declared_parameter_source_artifact_sha256"] == (
            PARAMETER_SOURCE_ARTIFACT_SHA256
        )
        assert row["assigned_parameter_value_ids"] == []
        assert row["absent_parameter_value_ids"] == sorted(
            MMCIF_NONPOLY_ATOM_PARAMETER_VALUE_IDS
        )
        assert row["every_parameter_value_absent"] is True
        assert row["any_parameter_value_assigned"] is False
        assert row["partial_charge_e_binary64_hex"] is None
        assert row["mass_da_binary64_hex"] is None
        assert len(row["atom_provenance_sha256"]) == 64


def test_atom_rows_are_a_contiguous_projection_of_the_bound_system(
    snapshot: object,
) -> None:
    payload = snapshot.to_dict()  # type: ignore[attr-defined]
    for instance in payload["instance_reports"]:
        if instance["trace_status"] != "traced":
            continue
        indices = [row["atom_index"] for row in instance["atom_rows"]]
        assert indices == list(range(len(indices)))
        assert instance["atom_count"] == len(indices)
        assert len(instance["bound_system_sha256"]) == 64
        assert len(instance["parameter_source_binding_sha256"]) == 64
        assert instance["trace_blockers"] == []
        for bond in instance["bond_rows"]:
            assert bond["atom_i"] in indices
            assert bond["atom_j"] in indices
            assert bond["bonded_parameters_assigned"] is False
            assert bond["derivation_source"]


def test_unbound_instances_are_retained_with_explicit_blockers() -> None:
    for case in corpus_module.mmcif_nonpoly_preparation_corpus_cases():
        binding = parse_mmcif_nonpoly_parameter_source_bindings(case.source_text)
        if all(row.source_bound for row in binding.instance_reports):
            continue
        traced = trace_mmcif_nonpoly_atom_parameter_provenance(binding)
        payload = traced.to_dict()
        assert payload["instance_count"] == len(binding.instance_reports)
        untraced = [
            row
            for row in payload["instance_reports"]
            if row["trace_status"] == "untraced_source_not_bound"
        ]
        assert untraced
        for row in untraced:
            assert row["atom_rows"] == []
            assert row["bound_system_sha256"] == ""
            assert row["parameter_source_binding_sha256"] == ""
        assert payload["untraced_instance_count"] == len(untraced)
        assert payload["unbound_instances_retained"] is True
        return
    pytest.skip("corpus has no partially bound case")


def test_document_is_deterministic_and_self_authenticating(
    snapshot: object,
) -> None:
    again = parse_mmcif_nonpoly_atom_parameter_provenance(_bound_case_source())
    assert again.canonical_bytes() == snapshot.canonical_bytes()  # type: ignore[attr-defined]

    payload = snapshot.to_dict()  # type: ignore[attr-defined]
    validated = require_mmcif_nonpoly_atom_parameter_provenance_document(payload)
    assert validated["snapshot_sha256"] == payload["snapshot_sha256"]


def test_document_validator_rejects_digest_and_claim_tamper(
    snapshot: object,
) -> None:
    payload = snapshot.to_dict()  # type: ignore[attr-defined]

    tampered = json.loads(json.dumps(payload))
    tampered["atom_count"] += 1
    with pytest.raises(
        MmcifNonpolyAtomParameterProvenanceError,
        match="digest is invalid",
    ):
        require_mmcif_nonpoly_atom_parameter_provenance_document(tampered)

    instance_tamper = json.loads(json.dumps(payload))
    instance_tamper["instance_reports"][0]["atom_count"] += 1
    with pytest.raises(MmcifNonpolyAtomParameterProvenanceError):
        require_mmcif_nonpoly_atom_parameter_provenance_document(instance_tamper)


def test_claim_open_document_is_rejected(snapshot: object) -> None:
    payload = json.loads(json.dumps(snapshot.to_dict()))  # type: ignore[attr-defined]
    payload.pop("snapshot_sha256")
    payload["claim_safe"] = True
    payload["snapshot_sha256"] = provenance._sha256(payload)
    with pytest.raises(
        MmcifNonpolyAtomParameterProvenanceError,
        match="must keep claim_safe=false",
    ):
        require_mmcif_nonpoly_atom_parameter_provenance_document(payload)


def test_write_json_is_private_and_refuses_overwrite(
    tmp_path: Path,
    snapshot: object,
) -> None:
    output = tmp_path / "receipts" / "atom-provenance.json"
    snapshot.write_json(output)  # type: ignore[attr-defined]
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert output.read_bytes() == snapshot.canonical_bytes()  # type: ignore[attr-defined]

    with pytest.raises(
        MmcifNonpolyAtomParameterProvenanceError,
        match="already exists",
    ):
        snapshot.write_json(output)  # type: ignore[attr-defined]


def test_binding_digest_mismatch_fails_closed() -> None:
    binding = parse_mmcif_nonpoly_parameter_source_bindings(_bound_case_source())
    bound = next(row for row in binding.instance_reports if row.source_bound)
    crosswired = type(bound)(
        instance_identity_sha256=bound.instance_identity_sha256,
        component_id=bound.component_id,
        binding_status=bound.binding_status,
        binding_blockers=bound.binding_blockers,
        limitations=bound.limitations,
        source_system_sha256=bound.source_system_sha256,
        binding_sha256="0" * 64,
        bound_system=bound.bound_system,
    )
    snapshot = type(binding)(
        all_atom_snapshot=binding.all_atom_snapshot,
        parameter_source_snapshot=binding.parameter_source_snapshot,
        instance_reports=(crosswired,),
    )
    with pytest.raises(
        MmcifNonpolyAtomParameterProvenanceError,
        match="does not carry its parameter-source binding digest",
    ):
        trace_mmcif_nonpoly_atom_parameter_provenance(snapshot)
