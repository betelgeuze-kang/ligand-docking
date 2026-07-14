from __future__ import annotations

from pathlib import Path

import pytest

import betelgeuze_engine_v2.molecular.mmcif_polymer_sequence_nonpoly_component_topology as composition_module
from betelgeuze_engine_v2.molecular.mmcif_polymer_sequence_nonpoly_component_topology import (
    MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID,
    MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID,
    MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_STATE_SCHEMA_ID,
    MmcifPolymerSequenceNonpolyComponentTopologyError,
    MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
    MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport,
    MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult,
    MmcifPolymerSequenceNonpolyComponentTopologyWriteReceipt,
    MmcifPolymerSequenceNonpolyComponentTopologyWriteResult,
    mmcif_polymer_sequence_nonpoly_component_topology_record_state_sha256,
    mmcif_polymer_sequence_nonpoly_component_topology_state_sha256,
    parse_mmcif_polymer_sequence_nonpoly_component_topology,
    round_trip_mmcif_polymer_sequence_nonpoly_component_topology_source,
    serialize_mmcif_polymer_sequence_nonpoly_component_topology,
    write_mmcif_polymer_sequence_nonpoly_component_topology,
)


_ROOT = Path(__file__).resolve().parents[2]
_COMPONENT_FIXTURE = (
    _ROOT
    / "tests"
    / "fixtures"
    / "v2_1_mmcif_nonpoly_component_topology"
    / "mixed_polymer_methane_complete.cif"
)
_FIXED_COMPOSITION_FIXTURES = (
    _ROOT
    / "tests"
    / "fixtures"
    / "v2_1_mmcif_polymer_sequence_nonpoly_component_topology_composition"
)
_SEQUENCE_LOOP = b"""loop_
_entity_poly_seq.entity_id
_entity_poly_seq.num
_entity_poly_seq.mon_id
_entity_poly_seq.hetero
1 1 GLY n
#
"""
_CHEM_COMP_MARKER = b"""loop_
_chem_comp.id
"""


def _source() -> bytes:
    source = _COMPONENT_FIXTURE.read_bytes()
    assert source.count(_CHEM_COMP_MARKER) == 1
    return source.replace(
        _CHEM_COMP_MARKER,
        _SEQUENCE_LOOP + _CHEM_COMP_MARKER,
        1,
    )


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    assert source.count(old) == 1
    return source.replace(old, new, 1)


def _assert_code(source: bytes, code: str) -> None:
    with pytest.raises(MmcifPolymerSequenceNonpolyComponentTopologyError) as exc:
        parse_mmcif_polymer_sequence_nonpoly_component_topology(
            source, source_id="PRIVATE-COMPOSITION-ID"
        )
    assert exc.value.code == code
    assert exc.value.__cause__ is None
    assert "PRIVATE-COMPOSITION-ID" not in str(exc.value)


@pytest.fixture(scope="module")
def ingest() -> MmcifPolymerSequenceNonpolyComponentTopologyIngestResult:
    return parse_mmcif_polymer_sequence_nonpoly_component_topology(
        _source(), source_id="composition-core"
    )


@pytest.fixture(scope="module")
def round_trip() -> MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult:
    return round_trip_mmcif_polymer_sequence_nonpoly_component_topology_source(
        _source(), source_id="composition-core"
    )


def test_exact_children_are_cross_bound_and_component_child_owns_system(
    ingest: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
) -> None:
    component = ingest.component_ingest
    polymer = ingest.polymer_ingest
    nonpoly = polymer.nonpoly_ingest
    assert nonpoly is not None
    assert component.carrier_ingest.identity_projection_sha256 == (
        nonpoly.identity_projection_sha256
    )
    assert component.carrier_ingest.record_state_sha256 == nonpoly.record_state_sha256
    assert component.carrier_ingest.base_topology_sha256 == nonpoly.base_topology_sha256
    assert component.carrier_ingest.base_representable_state_sha256 == (
        nonpoly.base_representable_state_sha256
    )
    assert len(ingest.system.atoms) == 6
    assert len(ingest.system.bonds) == 4
    assert [(row.mon_id, row.coordinate_observed) for row in ingest.sequence_rows] == [
        ("GLY", True)
    ]
    assert "mmcif_polymer_sequence" not in ingest.system.metadata

    document = ingest.to_dict()
    assert document["profile_id"] == (
        MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_PROFILE_ID
    )
    assert document["schema_id"] == (
        MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_STATE_SCHEMA_ID
    )
    assert document["source_binding_schema_id"] == (
        MMCIF_POLYMER_SEQUENCE_NONPOLY_COMPONENT_TOPOLOGY_SOURCE_BINDING_SCHEMA_ID
    )
    assert document["component_child_and_polymer_child_cross_bound"] is True
    assert document["canonical_shared_loops_byte_equal"] is True
    assert document["system_owner"] == "mmcif_nonpoly_component_topology_child"
    assert document["polymer_sequence_semantics"] == "source_evidence_only"
    for field_name in (
        "polymer_templates_supported",
        "reference_sequence_equivalence_assessed",
        "coordinate_observation_completeness_assessed",
        "generic_chemistry_supported",
        "generic_molecular_preparation_ready",
        "general_mmcif_topology_complete",
        "v2_1_complete",
    ):
        assert document[field_name] is False


def test_canonical_order_exact_reparse_and_stable_second_emission(
    ingest: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
    round_trip: MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult,
) -> None:
    payload = serialize_mmcif_polymer_sequence_nonpoly_component_topology(ingest)
    text = payload.decode("ascii")
    headers = (
        "_entity.id",
        "_struct_asym.id",
        "_entity_poly_seq.entity_id",
        "_chem_comp.id",
        "_chem_comp_atom.comp_id",
        "_chem_comp_bond.comp_id",
        "_pdbx_entity_nonpoly.entity_id",
        "_pdbx_nonpoly_scheme.asym_id",
        "_atom_site.group_pdb",
    )
    positions = tuple(text.index(header) for header in headers)
    assert positions == tuple(sorted(positions))
    reparsed = parse_mmcif_polymer_sequence_nonpoly_component_topology(
        payload, source_id="composition-core"
    )
    assert reparsed.record_state_sha256 == ingest.record_state_sha256
    assert mmcif_polymer_sequence_nonpoly_component_topology_state_sha256(
        ingest
    ) == mmcif_polymer_sequence_nonpoly_component_topology_record_state_sha256(ingest)
    assert round_trip._write_result._payload == round_trip._second._payload
    report = round_trip._report.to_dict()
    assert report["composition_round_trip_preserved"] is True
    assert report["emitted_source_reparsed_exact"] is True
    assert report["second_emission_byte_stable"] is True


def test_category_order_variant_has_identical_semantic_state_and_output() -> None:
    canonical = parse_mmcif_polymer_sequence_nonpoly_component_topology(
        (
            _FIXED_COMPOSITION_FIXTURES / "mixed_polymer_methane_sequence_complete.cif"
        ).read_bytes(),
        source_id="order-normalization",
    )
    variant = parse_mmcif_polymer_sequence_nonpoly_component_topology(
        (_FIXED_COMPOSITION_FIXTURES / "category_order_variant.cif").read_bytes(),
        source_id="order-normalization",
    )
    assert canonical.record_state_sha256 == variant.record_state_sha256
    assert (
        write_mmcif_polymer_sequence_nonpoly_component_topology(canonical).payload
        == write_mmcif_polymer_sequence_nonpoly_component_topology(variant).payload
    )
    assert canonical.full_source_sha256 != variant.full_source_sha256


def test_source_id_is_source_binding_only_not_semantic_record_state() -> None:
    source = _source()
    first = parse_mmcif_polymer_sequence_nonpoly_component_topology(
        source, source_id="source-binding-a"
    )
    second = parse_mmcif_polymer_sequence_nonpoly_component_topology(
        source, source_id="source-binding-b"
    )
    assert first.record_state_sha256 == second.record_state_sha256
    assert first.component_topology_state_sha256 == (
        second.component_topology_state_sha256
    )
    assert first.polymer_sequence_record_state_sha256 == (
        second.polymer_sequence_record_state_sha256
    )
    assert first.nonpoly_identity_record_state_sha256 == (
        second.nonpoly_identity_record_state_sha256
    )
    assert first.source_binding_sha256 != second.source_binding_sha256
    assert first.source_id_sha256 != second.source_id_sha256
    assert "source_id_sha256" not in first.to_dict()["shared_nonpoly_base"]


def test_category_surface_representation_and_header_fail_closed() -> None:
    source = _source()
    _assert_code(source.replace(_SEQUENCE_LOOP, b"", 1), "unsupported_category_surface")
    extra = b"loop_\n_audit_author.name\nCodex\n#\n"
    _assert_code(
        source.replace(_CHEM_COMP_MARKER, extra + _CHEM_COMP_MARKER, 1),
        "unsupported_category_surface",
    )
    scalar = b"""_entity_poly_seq.entity_id 1
_entity_poly_seq.num 1
_entity_poly_seq.mon_id GLY
_entity_poly_seq.hetero n
#
"""
    _assert_code(
        source.replace(_SEQUENCE_LOOP, scalar, 1),
        "unsupported_category_representation",
    )
    wrong_headers = _replace_once(
        source,
        b"_entity_poly_seq.entity_id\n_entity_poly_seq.num\n",
        b"_entity_poly_seq.num\n_entity_poly_seq.entity_id\n",
    )
    _assert_code(wrong_headers, "unsupported_category_headers")


def test_sequence_and_component_chemistry_child_failures_remain_typed() -> None:
    source = _source()
    _assert_code(
        _replace_once(source, b"1 1 GLY n\n", b"1 0 GLY n\n"),
        "polymer_child_rejected",
    )
    _assert_code(
        _replace_once(source, b"MET C H1 SING N N 1\n", b"MET C H1 QUAD N N 1\n"),
        "component_child_rejected",
    )


def test_crosswired_child_base_state_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = composition_module.parse_mmcif_polymer_sequence

    def parse_crosswired(data: bytes, *, source_id: str = ""):
        assert data.count(b"-2.000") == 1
        return original(data.replace(b"-2.000", b"-3.000", 1), source_id=source_id)

    monkeypatch.setattr(
        composition_module, "parse_mmcif_polymer_sequence", parse_crosswired
    )
    _assert_code(_source(), "crosswired_child_carrier")


def test_ingest_anchor_rejects_tamper_and_coherent_field_copy() -> None:
    first = parse_mmcif_polymer_sequence_nonpoly_component_topology(
        _source(), source_id="anchor-a"
    )
    second = parse_mmcif_polymer_sequence_nonpoly_component_topology(
        _source(), source_id="anchor-b"
    )
    object.__setattr__(first, "_record_state_bytes", second._record_state_bytes)
    object.__setattr__(first, "_source_binding_bytes", second._source_binding_bytes)
    object.__setattr__(first, "_source_id", second._source_id)
    object.__setattr__(first, "_access_binding_bytes", second._access_binding_bytes)
    with pytest.raises(MmcifPolymerSequenceNonpolyComponentTopologyError) as exc:
        first.to_dict()
    assert exc.value.code == "stale_ingest_binding"


def test_public_child_rows_system_and_receipt_are_detached(
    ingest: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult,
) -> None:
    component = ingest.component_ingest
    object.__setattr__(component, "_full_source", b"poison")
    assert len(ingest.component_ingest.system.bonds) == 4

    rows = ingest.sequence_rows
    object.__setattr__(rows[0], "mon_id", "POISON")
    assert ingest.sequence_rows[0].mon_id == "GLY"

    system = ingest.system
    object.__setattr__(system.atoms[0], "name", "POISON")
    assert ingest.system.atoms[0].name == "CA"

    write_result = write_mmcif_polymer_sequence_nonpoly_component_topology(ingest)
    receipt = write_result.receipt
    assert receipt._ingest is not write_result._ingest
    object.__setattr__(receipt._ingest, "_full_source", b"poison")
    object.__setattr__(receipt, "_document_bytes", b"{}")
    assert write_result.payload.startswith(b"data_")
    assert write_result.receipt.receipt_sha256


def test_round_trip_public_nested_artifacts_are_detached_and_crosswire_fails(
    round_trip: MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult,
) -> None:
    detached_source = round_trip.source_ingest
    object.__setattr__(detached_source, "_full_source", b"poison")
    assert round_trip.source_ingest.record_state_sha256 == (
        round_trip._source.record_state_sha256
    )

    detached_report = round_trip.report
    object.__setattr__(detached_report, "_document_bytes", b"{}")
    assert round_trip.report.to_dict()["composition_round_trip_preserved"] is True

    other = round_trip_mmcif_polymer_sequence_nonpoly_component_topology_source(
        _source(), source_id="crosswire-other"
    )
    object.__setattr__(round_trip, "_write_result", other._write_result)
    with pytest.raises(MmcifPolymerSequenceNonpolyComponentTopologyError) as exc:
        round_trip.to_dict()
    assert exc.value.code == "crosswired_round_trip_artifacts"


def test_semantically_equal_category_order_variant_cannot_crosswire_artifacts() -> None:
    source_id = "semantic-crosswire"
    canonical_source = (
        _FIXED_COMPOSITION_FIXTURES / "mixed_polymer_methane_sequence_complete.cif"
    ).read_bytes()
    variant_source = (
        _FIXED_COMPOSITION_FIXTURES / "category_order_variant.cif"
    ).read_bytes()
    canonical = round_trip_mmcif_polymer_sequence_nonpoly_component_topology_source(
        canonical_source, source_id=source_id
    )
    variant = parse_mmcif_polymer_sequence_nonpoly_component_topology(
        variant_source, source_id=source_id
    )
    assert variant.record_state_sha256 == canonical._source.record_state_sha256

    with pytest.raises(MmcifPolymerSequenceNonpolyComponentTopologyError) as exc:
        MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport(
            variant,
            canonical._write_result,
            canonical._reparsed,
            canonical._second,
            _factory_token=composition_module._FACTORY_TOKEN,
        )
    assert exc.value.code == "crosswired_round_trip_artifacts"

    with pytest.raises(MmcifPolymerSequenceNonpolyComponentTopologyError) as exc:
        MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult(
            variant,
            canonical._write_result,
            canonical._reparsed,
            canonical._second,
            canonical._report,
            _factory_token=composition_module._FACTORY_TOKEN,
        )
    assert exc.value.code == "crosswired_round_trip_artifacts"


def test_all_public_artifacts_are_factory_only() -> None:
    constructors = (
        lambda: MmcifPolymerSequenceNonpolyComponentTopologyIngestResult(None),
        lambda: MmcifPolymerSequenceNonpolyComponentTopologyWriteReceipt(None, b""),
        lambda: MmcifPolymerSequenceNonpolyComponentTopologyWriteResult(
            None, b"", None
        ),
        lambda: MmcifPolymerSequenceNonpolyComponentTopologyRoundTripReport(
            None, None, None, None
        ),
        lambda: MmcifPolymerSequenceNonpolyComponentTopologyRoundTripResult(
            None, None, None, None, None
        ),
    )
    for construct in constructors:
        with pytest.raises(TypeError, match="factory-only"):
            construct()


def test_input_type_is_exact() -> None:
    with pytest.raises(TypeError, match="must be bytes"):
        parse_mmcif_polymer_sequence_nonpoly_component_topology("not bytes")  # type: ignore[arg-type]
    with pytest.raises(MmcifPolymerSequenceNonpolyComponentTopologyError) as exc:
        parse_mmcif_polymer_sequence_nonpoly_component_topology(
            _source(), source_id="\ud800"
        )
    assert exc.value.code == "invalid_source_id"
    assert exc.value.__cause__ is None
