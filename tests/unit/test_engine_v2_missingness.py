from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json

import pytest

import betelgeuze_engine_v2.molecular.missingness as missingness
from betelgeuze_engine_v2.molecular.missingness import (
    MISSINGNESS_PRESERVATION_POLICY_ID,
    MISSINGNESS_REPORT_SCHEMA_ID,
    SourceReportedMissingAtomClaim,
    SourceReportedMissingResidueClaim,
    build_source_reported_missingness_report,
)
from betelgeuze_engine_v2.molecular.topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
)


SOURCE_SHA256 = "a" * 64
TOPOLOGY_SHA256 = "b" * 64


def _residue_claim(
    ordinal: int = 2,
    *,
    raw_payload: object | None = None,
) -> SourceReportedMissingResidueClaim:
    return SourceReportedMissingResidueClaim(
        source_ordinal=ordinal,
        source_category="_pdbx_unobs_or_zero_occ_residues",
        source_model_id="1",
        source_chain_id="A",
        source_residue_id="42",
        source_residue_name="GLY",
        source_insertion_code="B",
        raw_payload=(
            {
                "PDB_model_num": "1",
                "auth_asym_id": "A",
                "auth_seq_id": "42",
                "details": ["zero occupancy", {"source_token": "?"}],
            }
            if raw_payload is None
            else raw_payload
        ),
    )


def _atom_claim(
    ordinal: int = 5,
    *,
    raw_payload: object | None = None,
) -> SourceReportedMissingAtomClaim:
    return SourceReportedMissingAtomClaim(
        source_ordinal=ordinal,
        source_category="_pdbx_unobs_or_zero_occ_atoms",
        source_model_id="1",
        source_chain_id="A",
        source_residue_id="43",
        source_residue_name="SER",
        source_insertion_code="",
        source_atom_name="OG",
        source_altloc_id="",
        raw_payload=(
            {
                "auth_atom_id": "OG",
                "occupancy_flag": 0,
                "original_unknown": None,
            }
            if raw_payload is None
            else raw_payload
        ),
    )


def _report(
    *,
    source_format: str = "mmcif",
    coordinate_scope: str = "deposited_asymmetric_unit",
    altloc_status: str = "not_present",
    requested_altloc_id: str = "",
    assembly_status: str = "present_not_requested",
    requested_assembly_id: str = "",
    residue_claims: tuple[SourceReportedMissingResidueClaim, ...] | None = None,
    atom_claims: tuple[SourceReportedMissingAtomClaim, ...] | None = None,
):
    return build_source_reported_missingness_report(
        source_format=source_format,
        source_sha256=SOURCE_SHA256,
        canonical_topology_sha256=TOPOLOGY_SHA256,
        coordinate_scope=coordinate_scope,
        altloc_status=altloc_status,
        requested_altloc_id=requested_altloc_id,
        assembly_status=assembly_status,
        requested_assembly_id=requested_assembly_id,
        missing_residue_claims=(
            (_residue_claim(),) if residue_claims is None else residue_claims
        ),
        missing_atom_claims=(
            (_atom_claim(),) if atom_claims is None else atom_claims
        ),
    )


def test_report_preserves_claims_and_all_required_bindings_without_promotion() -> None:
    report = _report(
        altloc_status="explicit_id_selected",
        requested_altloc_id="A",
        coordinate_scope="explicit_biological_assembly",
        assembly_status="explicit_id_applied",
        requested_assembly_id="1",
    )

    assert report.policy_id == MISSINGNESS_PRESERVATION_POLICY_ID
    assert report.source_format == "mmcif"
    assert report.source_sha256 == SOURCE_SHA256
    assert report.canonical_topology_schema_id == CANONICAL_TOPOLOGY_SCHEMA_ID
    assert report.canonical_topology_sha256 == TOPOLOGY_SHA256
    assert report.coordinate_scope == "explicit_biological_assembly"
    assert report.altloc_status == "explicit_id_selected"
    assert report.requested_altloc_id == "A"
    assert report.assembly_status == "explicit_id_applied"
    assert report.requested_assembly_id == "1"
    assert report.source_reported_missing_residue_count == 1
    assert report.source_reported_missing_atom_count == 1
    assert report.completion_attempted is False
    assert report.completion_applied is False
    assert report.preparation_ready is False
    assert report.claim_safe is False
    assert report.blockers == (
        "source_reported_missingness_preserved_only",
        "source_reported_missingness_not_completeness_evidence",
        "reference_chemistry_not_consulted",
        "completion_not_attempted",
        "preparation_not_assessed",
        "source_reports_missing_residues",
        "source_reports_missing_atoms",
    )


def test_report_sha256_is_over_deterministic_canonical_utf8_json() -> None:
    first = _report()
    second = _report()

    assert first.canonical_bytes == second.canonical_bytes
    assert first.report_sha256 == second.report_sha256
    assert first.report_sha256 == hashlib.sha256(first.canonical_bytes).hexdigest()
    document = json.loads(first.canonical_bytes.decode("utf-8"))
    assert document["schema_id"] == MISSINGNESS_REPORT_SCHEMA_ID
    assert "report_sha256" not in document
    assert first.to_dict()["report_sha256"] == first.report_sha256
    assert len(first.report_sha256) == 64
    int(first.report_sha256, 16)


def test_digest_changes_with_raw_evidence_claim_order_and_selection_binding() -> None:
    baseline = _report()
    raw_change = _report(
        atom_claims=(_atom_claim(raw_payload={"auth_atom_id": "CB"}),)
    )
    first = _atom_claim(4, raw_payload={"row": "first"})
    second = _atom_claim(8, raw_payload={"row": "second"})
    reordered_content = _report(
        atom_claims=(
            replace(second, source_ordinal=4),
            replace(first, source_ordinal=8),
        )
    )
    ordered_content = _report(atom_claims=(first, second))
    selected = _report(
        altloc_status="explicit_id_selected",
        requested_altloc_id="A",
    )

    assert raw_change.report_sha256 != baseline.report_sha256
    assert reordered_content.report_sha256 != ordered_content.report_sha256
    assert selected.report_sha256 != baseline.report_sha256


def test_raw_payload_participates_in_claim_and_report_equality() -> None:
    left = _atom_claim(raw_payload={"row": "left"})
    right = _atom_claim(raw_payload={"row": "right"})

    assert left != right
    assert _report(atom_claims=(left,)) != _report(atom_claims=(right,))


def test_claim_and_nested_raw_payload_are_defensively_immutable() -> None:
    source = {"row": ["ATOM", {"flag": True}]}
    claim = _atom_claim(raw_payload=source)
    source["row"][0] = "MUTATED"
    source["row"][1]["flag"] = False

    assert claim.raw_payload == {"row": ["ATOM", {"flag": True}]}
    with pytest.raises(FrozenInstanceError):
        claim.source_atom_name = "CB"  # type: ignore[misc]
    with pytest.raises(TypeError):
        claim.raw_payload["new"] = "value"  # type: ignore[index]
    with pytest.raises(TypeError):
        claim.raw_payload["row"][1]["flag"] = False  # type: ignore[index]
    with pytest.raises(AttributeError):
        claim.raw_payload["row"].append("extra")  # type: ignore[union-attr]


def test_to_dict_returns_detached_mutable_json_data() -> None:
    report = _report()
    payload = report.to_dict()
    payload["missing_atom_claims"][0]["raw_payload"]["auth_atom_id"] = "CHANGED"
    payload["blockers"].append("forged")

    assert report.missing_atom_claims[0].raw_payload["auth_atom_id"] == "OG"
    assert "forged" not in report.blockers
    assert report.to_dict()["report_sha256"] == report.report_sha256


def test_empty_source_claim_inventory_is_not_promoted_to_completeness() -> None:
    report = _report(residue_claims=(), atom_claims=())

    assert report.source_reported_missing_residue_count == 0
    assert report.source_reported_missing_atom_count == 0
    assert report.blockers == (
        "source_reported_missingness_preserved_only",
        "source_reported_missingness_not_completeness_evidence",
        "reference_chemistry_not_consulted",
        "completion_not_attempted",
        "preparation_not_assessed",
    )
    assert report.preparation_ready is False
    assert report.claim_safe is False


def test_raw_payload_is_never_used_to_infer_claims_or_counts() -> None:
    claim = _atom_claim(
        raw_payload={
            "source_reported_missing_atom_count": 999,
            "invented_other_atoms": ["CB", "CA"],
        }
    )
    report = _report(residue_claims=(), atom_claims=(claim,))

    assert report.source_reported_missing_residue_count == 0
    assert report.source_reported_missing_atom_count == 1
    assert tuple(item.source_atom_name for item in report.missing_atom_claims) == (
        "OG",
    )


@pytest.mark.parametrize(
    ("source_format", "scope", "assembly_status"),
    (
        ("pdb", "deposited_coordinates", "not_supported_for_pdb"),
        ("mmcif", "deposited_asymmetric_unit", "not_present"),
        ("mmcif", "deposited_asymmetric_unit", "present_not_requested"),
    ),
)
def test_supported_unexpanded_coordinate_scope_bindings(
    source_format: str,
    scope: str,
    assembly_status: str,
) -> None:
    report = _report(
        source_format=source_format,
        coordinate_scope=scope,
        assembly_status=assembly_status,
    )
    assert report.coordinate_scope == scope
    assert report.requested_assembly_id == ""


@pytest.mark.parametrize(
    "overrides",
    (
        {"source_format": "sdf"},
        {"source_format": "PDB"},
        {"source_format": 1},
        {"source_format": "pdb", "coordinate_scope": "deposited_asymmetric_unit"},
        {"source_format": "pdb", "assembly_status": "not_present"},
        {"coordinate_scope": "unknown"},
        {"coordinate_scope": "explicit_biological_assembly"},
        {"assembly_status": "explicit_id_applied"},
        {"requested_assembly_id": "1"},
        {"coordinate_scope": "explicit_biological_assembly", "assembly_status": "present_not_requested", "requested_assembly_id": "1"},
        {"coordinate_scope": "explicit_biological_assembly", "assembly_status": "explicit_id_applied", "requested_assembly_id": ""},
    ),
)
def test_invalid_source_and_assembly_bindings_fail_closed(
    overrides: dict[str, object],
) -> None:
    arguments: dict[str, object] = {
        "source_format": "mmcif",
        "coordinate_scope": "deposited_asymmetric_unit",
        "assembly_status": "present_not_requested",
        "requested_assembly_id": "",
    }
    arguments.update(overrides)
    with pytest.raises((TypeError, ValueError)):
        _report(**arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    (
        {"altloc_status": "unsupported"},
        {"altloc_status": "not_present", "requested_altloc_id": "A"},
        {"altloc_status": "explicit_id_selected", "requested_altloc_id": ""},
        {"altloc_status": 1},
        {"altloc_status": "explicit_id_selected", "requested_altloc_id": 1},
    ),
)
def test_invalid_altloc_bindings_fail_closed(overrides: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        _report(**overrides)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("source_sha256", "A" * 64),
        ("source_sha256", "a" * 63),
        ("source_sha256", "٠" * 64),
        ("source_sha256", 1),
        ("canonical_topology_sha256", "g" * 64),
        ("canonical_topology_sha256", None),
    ),
)
def test_source_and_topology_digests_require_lowercase_ascii_sha256(
    field_name: str,
    value: object,
) -> None:
    report = _report()
    with pytest.raises(ValueError, match="lowercase ASCII SHA-256"):
        replace(report, **{field_name: value})


def test_topology_schema_is_pinned() -> None:
    report = _report()
    with pytest.raises(ValueError, match="fixed canonical topology schema"):
        replace(report, canonical_topology_schema_id="forged/9.9.9")


@pytest.mark.parametrize(
    ("field_name", "value", "error_type"),
    (
        ("source_reported_missing_residue_count", 0, ValueError),
        ("source_reported_missing_atom_count", 0, ValueError),
        ("source_reported_missing_atom_count", True, TypeError),
        ("source_reported_missing_atom_count", -1, ValueError),
    ),
)
def test_source_reported_counts_exactly_match_ordered_claims(
    field_name: str,
    value: object,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        replace(_report(), **{field_name: value})


def test_claim_collections_must_be_exact_tuples_of_exact_claim_types() -> None:
    residue = _residue_claim()
    atom = _atom_claim()
    with pytest.raises(TypeError, match="must be a tuple"):
        build_source_reported_missingness_report(
            source_format="mmcif",
            source_sha256=SOURCE_SHA256,
            canonical_topology_sha256=TOPOLOGY_SHA256,
            coordinate_scope="deposited_asymmetric_unit",
            altloc_status="not_present",
            requested_altloc_id="",
            assembly_status="not_present",
            requested_assembly_id="",
            missing_residue_claims=[residue],  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="exact SourceReportedMissingResidueClaim"):
        replace(
            _report(),
            missing_residue_claims=(atom,),  # type: ignore[arg-type]
        )


def test_claim_ordinals_must_be_positive_and_strictly_increasing() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        _atom_claim(0)
    with pytest.raises(TypeError, match="must be an integer"):
        _atom_claim(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="signed 64-bit range"):
        _atom_claim(10**5000)
    with pytest.raises(ValueError, match="strictly increasing"):
        _report(atom_claims=(_atom_claim(5), _atom_claim(4)))
    with pytest.raises(ValueError, match="strictly increasing"):
        _report(atom_claims=(_atom_claim(5), _atom_claim(5)))


@pytest.mark.parametrize(
    "replacement",
    (
        {"source_category": ""},
        {"source_model_id": 1},
        {"source_chain_id": None},
        {"source_residue_id": ""},
        {"source_residue_name": ""},
        {"source_insertion_code": 1},
        {"source_atom_name": ""},
        {"source_altloc_id": 1},
    ),
)
def test_claim_identity_fields_are_strict_and_not_normalized(
    replacement: dict[str, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        replace(_atom_claim(), **replacement)

    preserved = replace(
        _atom_claim(),
        source_residue_name="gly",
        source_atom_name=" og ",
    )
    assert preserved.source_residue_name == "gly"
    assert preserved.source_atom_name == " og "


def test_claim_strings_reject_non_scalar_unicode_and_length_overflow() -> None:
    with pytest.raises(ValueError, match="Unicode scalar"):
        replace(_atom_claim(), source_atom_name="\ud800")
    with pytest.raises(ValueError, match="character limit"):
        replace(_atom_claim(), source_atom_name="X" * 4_097)


@pytest.mark.parametrize(
    "raw_payload",
    (
        [],
        {},
        {1: "non-string key"},
        {"tuple": (1, 2)},
        {"nan": float("nan")},
        {"infinity": float("inf")},
        {"integer": 1 << 63},
        {"surrogate": "\ud800"},
        {"unsupported": object()},
    ),
)
def test_raw_payload_accepts_only_bounded_canonical_json(
    raw_payload: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        _atom_claim(raw_payload=raw_payload)


def test_raw_payload_rejects_reference_cycles() -> None:
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    with pytest.raises(ValueError, match="reference cycle"):
        _atom_claim(raw_payload=cyclic)


def test_raw_payload_depth_node_and_byte_limits_are_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(missingness, "MAX_RAW_PAYLOAD_DEPTH", 1)
    with pytest.raises(ValueError, match="depth limit"):
        _atom_claim(raw_payload={"a": [{"b": 1}]})

    monkeypatch.setattr(missingness, "MAX_RAW_PAYLOAD_DEPTH", 16)
    monkeypatch.setattr(missingness, "MAX_RAW_PAYLOAD_NODES", 2)
    with pytest.raises(ValueError, match="node safety limit"):
        _atom_claim(raw_payload={"a": [1, 2]})

    monkeypatch.setattr(missingness, "MAX_RAW_PAYLOAD_NODES", 4_096)
    monkeypatch.setattr(missingness, "MAX_RAW_PAYLOAD_BYTES", 8)
    with pytest.raises(ValueError, match="canonical limit"):
        _atom_claim(raw_payload={"long": "payload"})


def test_claim_and_report_resource_limits_are_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(missingness, "MAX_MISSING_ATOM_CLAIMS", 0)
    with pytest.raises(ValueError, match="claim limit"):
        _report()

    monkeypatch.setattr(missingness, "MAX_MISSING_ATOM_CLAIMS", 100_000)
    monkeypatch.setattr(missingness, "MAX_TOTAL_MISSINGNESS_CLAIMS", 1)
    with pytest.raises(ValueError, match="combined missingness claims"):
        _report()

    monkeypatch.setattr(missingness, "MAX_TOTAL_MISSINGNESS_CLAIMS", 100_000)
    monkeypatch.setattr(missingness, "MAX_REPORT_CANONICAL_BYTES", 1)
    with pytest.raises(ValueError, match="canonical limit"):
        _report()


def test_blockers_must_be_the_exact_ordered_preserve_only_set() -> None:
    report = _report()
    with pytest.raises(ValueError, match="exactly match"):
        replace(report, blockers=report.blockers[:-1])
    with pytest.raises(ValueError, match="exactly match"):
        replace(report, blockers=tuple(reversed(report.blockers)))
    with pytest.raises(TypeError, match="tuple"):
        replace(report, blockers=list(report.blockers))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field_name",
    (
        "completion_attempted",
        "completion_applied",
        "preparation_ready",
        "claim_safe",
    ),
)
def test_completion_and_claim_flags_can_never_be_promoted(field_name: str) -> None:
    report = _report()
    with pytest.raises(ValueError, match="must remain false"):
        replace(report, **{field_name: True})
    with pytest.raises(TypeError, match="must be a boolean"):
        replace(report, **{field_name: 0})


def test_policy_id_is_fixed() -> None:
    with pytest.raises(ValueError, match="fixed policy"):
        replace(_report(), policy_id="promoting_policy")
