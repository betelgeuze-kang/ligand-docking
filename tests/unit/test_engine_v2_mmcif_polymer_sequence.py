from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
from pathlib import Path

import pytest

import betelgeuze_engine_v2.molecular.mmcif_polymer_sequence as polymer_sequence_module
from betelgeuze_engine_v2.molecular import (
    MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION,
    SourceReportedMissingResidueClaim,
    StructureParseError,
    build_source_reported_missingness_report,
    emit_mmcif_polymer_sequence,
    parse_mmcif,
    parse_mmcif_nonpoly_identity,
    parse_mmcif_polymer_sequence,
    round_trip_mmcif_polymer_sequence_source,
)
from betelgeuze_engine_v2.molecular.mmcif_polymer_sequence import (
    MAX_MMCIF_POLYMER_SEQUENCE_INPUT_BYTES,
    MAX_MMCIF_POLYMER_SEQUENCE_ROWS,
    MAX_MMCIF_POLYMER_SEQUENCE_TOKEN_CHARS,
    MmcifPolymerSequenceError,
    _report_payload,
    _receipt_payload,
    _sha256_document,
    mmcif_polymer_sequence_projection_sha256,
    mmcif_polymer_sequence_record_state_sha256,
    serialize_mmcif_polymer_sequence,
)


FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "v2_1_mmcif_polymer_sequence"
)
SINGLE = FIXTURES / "single_polymer_complete.cif"
CATEGORY_ORDER = FIXTURES / "category_order_variant.cif"
UNOBSERVED = FIXTURES / "unobserved_source_member.cif"
SHARED_ASYM = FIXTURES / "shared_entity_multiple_asym.cif"
INTERLEAVED = FIXTURES / "interleaved_two_polymer_entities.cif"
OPAQUE = FIXTURES / "opaque_nonstandard_monomer.cif"
MIXED = FIXTURES / "mixed_polymer_nonpoly_water.cif"


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    assert source.count(old) == 1
    return source.replace(old, new, 1)


def _assert_error(source: bytes, code: str) -> MmcifPolymerSequenceError:
    with pytest.raises(MmcifPolymerSequenceError) as exc_info:
        parse_mmcif_polymer_sequence(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_single_polymer_round_trip_and_base_parser_default_are_exact() -> None:
    source = SINGLE.read_bytes()
    ingest = parse_mmcif_polymer_sequence(source, source_id="single-polymer")
    write_result = emit_mmcif_polymer_sequence(ingest)

    assert MMCIF_POLYMER_SEQUENCE_ENVELOPE_VERSION == "1.0.0"
    assert ingest.full_source_sha256 == hashlib.sha256(source).hexdigest()
    assert ingest.carrier_kind == "common_core21"
    assert ingest.has_nonpoly_identity is False
    assert [
        (row.entity_id, row.num, row.mon_id, row.hetero) for row in ingest.sequence_rows
    ] == [
        ("1", 1, "GLY", "n"),
        ("1", 2, "ALA", "n"),
    ]
    assert serialize_mmcif_polymer_sequence(ingest) == write_result.payload
    assert mmcif_polymer_sequence_projection_sha256(ingest) == (
        ingest.polymer_sequence_projection_sha256
    )
    assert mmcif_polymer_sequence_record_state_sha256(ingest) == (
        ingest.record_state_sha256
    )
    assert b"1 2 ALA n\n" in write_result.payload

    with pytest.raises(StructureParseError) as exc_info:
        parse_mmcif(source, source_id="single-polymer")
    assert exc_info.value.code == "unsupported_context_category"


def test_unobserved_source_member_is_preserved_without_missingness_claim() -> None:
    result = round_trip_mmcif_polymer_sequence_source(
        UNOBSERVED.read_bytes(), source_id="unobserved-member"
    )
    rows = result.source_ingest.sequence_rows

    assert [
        (row.num, row.coordinate_observed, row.observed_asym_ids) for row in rows
    ] == [
        (1, True, ("A",)),
        (2, False, ()),
        (3, True, ("A",)),
    ]
    evidence = result.source_ingest.to_dict()
    assert evidence["coordinate_observed_sequence_row_count"] == 2
    assert evidence["coordinate_unobserved_sequence_row_count"] == 1
    assert (
        evidence["coordinate_absent_rows_preserved_without_missingness_claim"] is True
    )
    assert evidence["missing_residue_fact_claimed"] is False
    assert evidence["sequence_completeness_claimed"] is False
    missingness = result.source_ingest.base_ingest.missingness_evidence
    assert missingness.source_reported_missing_residue_count == 0
    assert missingness.source_reported_missing_atom_count == 0


def test_shared_entity_multiple_asym_is_entity_level_membership() -> None:
    ingest = parse_mmcif_polymer_sequence(SHARED_ASYM.read_bytes())

    assert len(ingest.sequence_rows) == 2
    assert [row.observed_asym_ids for row in ingest.sequence_rows] == [
        ("A", "B"),
        ("A", "B"),
    ]
    assert len(ingest.system.residues) == 4
    assert [chain.entity_id for chain in ingest.system.chains] == ["1", "1"]


def test_interleaved_entities_preserve_source_row_order() -> None:
    result = round_trip_mmcif_polymer_sequence_source(INTERLEAVED.read_bytes())
    expected = [("1", 1), ("2", 1), ("1", 2), ("2", 2)]

    assert [
        (row.entity_id, row.num) for row in result.source_ingest.sequence_rows
    ] == expected
    assert [
        (row.entity_id, row.num) for row in result.reparsed_ingest.sequence_rows
    ] == expected
    emitted_rows = [
        b"1 1 GLY n",
        b"2 1 ALA n",
        b"1 2 SER n",
        b"2 2 THR n",
    ]
    offsets = [result.write_result.payload.index(row) for row in emitted_rows]
    assert offsets == sorted(offsets)


def test_category_order_normalizes_without_crosswiring_source_binding() -> None:
    canonical = round_trip_mmcif_polymer_sequence_source(SINGLE.read_bytes())
    reordered = round_trip_mmcif_polymer_sequence_source(CATEGORY_ORDER.read_bytes())

    assert canonical.write_result.payload == reordered.write_result.payload
    assert canonical.source_ingest.polymer_sequence_projection_sha256 == (
        reordered.source_ingest.polymer_sequence_projection_sha256
    )
    assert canonical.source_ingest.record_state_sha256 == (
        reordered.source_ingest.record_state_sha256
    )
    assert canonical.source_ingest.source_binding_sha256 != (
        reordered.source_ingest.source_binding_sha256
    )
    assert canonical.write_result.receipt.receipt_sha256 != (
        reordered.write_result.receipt.receipt_sha256
    )
    text = canonical.write_result.payload.decode("ascii").lower()
    assert text.index("_entity.id") < text.index("_struct_asym.id")
    assert text.index("_struct_asym.id") < text.index("_entity_poly_seq.entity_id")
    assert text.index("_entity_poly_seq.entity_id") < text.index("_atom_site.group_pdb")


def test_composed_nonpoly_carrier_binds_existing_identity_state() -> None:
    result = round_trip_mmcif_polymer_sequence_source(
        MIXED.read_bytes(), source_id="mixed-carrier"
    )
    ingest = result.source_ingest

    assert ingest.carrier_kind == "mmcif_nonpoly_identity"
    assert ingest.has_nonpoly_identity is True
    assert ingest.nonpoly_ingest is not None
    assert ingest.nonpoly_identity_projection_sha256 == (
        ingest.nonpoly_ingest.identity_projection_sha256
    )
    assert ingest.nonpoly_identity_record_state_sha256 == (
        ingest.nonpoly_ingest.record_state_sha256
    )
    assert result.report.nonpoly_identity_projection_sha256_equal is True
    assert result.report.nonpoly_identity_record_state_sha256_equal is True
    text = result.write_result.payload.decode("ascii").lower()
    categories = (
        "_entity.id",
        "_struct_asym.id",
        "_entity_poly_seq.entity_id",
        "_pdbx_entity_nonpoly.entity_id",
        "_pdbx_nonpoly_scheme.asym_id",
        "_atom_site.group_pdb",
    )
    offsets = [text.index(category) for category in categories]
    assert offsets == sorted(offsets)
    lower = ingest.nonpoly_ingest
    assert lower is not None
    lower_false = {key for key, value in lower.to_dict().items() if value is False}
    upper_false = {key for key, value in ingest.to_dict().items() if value is False}
    assert lower_false <= upper_false
    for artifact in (
        ingest.to_dict(),
        result.write_result.receipt.to_dict(),
        result.report.to_dict(),
        result.to_dict(),
    ):
        assert artifact["polymer_chemistry_interpreted"] is False
        assert artifact["microheterogeneity_interpreted"] is False
        assert artifact["preparation_ready"] is False
        assert artifact["parameterability_assessed"] is False
        assert artifact["runtime_eligible"] is False
        assert artifact["claim_safe"] is False


def test_opaque_nonstandard_monomer_is_preserved_without_interpretation() -> None:
    result = round_trip_mmcif_polymer_sequence_source(OPAQUE.read_bytes())

    assert result.source_ingest.sequence_rows[0].mon_id == "MSE"
    assert b"1 1 MSE n" in result.write_result.payload
    assert result.source_ingest.to_dict()["polymer_chemistry_interpreted"] is False
    assert "MSE" not in repr(result.source_ingest.sequence_rows[0])
    assert "MSE" not in repr(result.source_ingest)


@pytest.mark.parametrize(
    ("source", "code"),
    [
        (
            _replace_once(SINGLE.read_bytes(), b"1 2 ALA no\n", b"1 2 ALA y\n"),
            "microheterogeneity_not_supported",
        ),
        (
            _replace_once(
                SINGLE.read_bytes(),
                b"1 2 ALA no\n",
                b"1 1 ALA no\n",
            ),
            "duplicate_sequence_position",
        ),
        (
            _replace_once(SINGLE.read_bytes(), b"1 2 ALA no\n", b"1 3 ALA no\n"),
            "noncontiguous_sequence_positions",
        ),
        (
            _replace_once(
                SINGLE.read_bytes(),
                b"1 1 GLY n\n1 2 ALA no\n",
                b"1 2 ALA no\n1 1 GLY n\n",
            ),
            "noncontiguous_sequence_positions",
        ),
        (
            _replace_once(SINGLE.read_bytes(), b"1 1 GLY n\n", b"1 01 GLY n\n"),
            "invalid_sequence_num",
        ),
        (
            _replace_once(SINGLE.read_bytes(), b"1 1 GLY n\n", b"1 1 GLY Y\n"),
            "invalid_sequence_hetero",
        ),
        (
            _replace_once(SINGLE.read_bytes(), b"1 polymer\n", b"1 non-polymer\n"),
            "nonpolymer_sequence_entity",
        ),
        (
            _replace_once(
                SINGLE.read_bytes(),
                b"1 polymer\n#\nloop_\n_struct_asym.id",
                b"1 polymer\n2 polymer\n#\nloop_\n_struct_asym.id",
            ),
            "polymer_entity_sequence_coverage_mismatch",
        ),
        (
            _replace_once(
                SINGLE.read_bytes(),
                b"ATOM 2 C CA . ALA A 1 2 ?",
                b"ATOM 2 C CA . VAL A 1 2 ?",
            ),
            "polymer_atom_sequence_join_mismatch",
        ),
        (
            _replace_once(
                SINGLE.read_bytes(),
                b"_entity_poly_seq.entity_id\n_entity_poly_seq.num\n",
                b"_entity_poly_seq.num\n_entity_poly_seq.entity_id\n",
            ),
            "unsupported_category_headers",
        ),
        (
            _replace_once(
                SINGLE.read_bytes(),
                b"loop_\n_atom_site.group_PDB\n",
                b"_chem_comp.id GLY\n#\nloop_\n_atom_site.group_PDB\n",
            ),
            "unsupported_category_surface",
        ),
    ],
)
def test_contract_boundaries_fail_closed(source: bytes, code: str) -> None:
    _assert_error(source, code)


def test_non_ascii_and_semantic_errors_do_not_echo_opaque_values() -> None:
    non_ascii = _replace_once(
        SINGLE.read_bytes(),
        b"1 2 ALA no\n",
        b"1 2 " + "비밀표식".encode() + b" no\n",
    )
    error = _assert_error(non_ascii, "non_ascii_input")
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "비밀표식" not in str(error)
    assert "비밀표식" not in repr(error)
    assert "비밀표식" not in error.detail

    private = _replace_once(
        SINGLE.read_bytes(),
        b"ATOM 2 C CA . ALA A 1 2 ?",
        b"ATOM 2 C CA . PRIVATE-MON-ID A 1 2 ?",
    )
    semantic_error = _assert_error(private, "polymer_atom_sequence_join_mismatch")
    assert "PRIVATE-MON-ID" not in str(semantic_error)
    assert "PRIVATE-MON-ID" not in repr(semantic_error)


def test_input_types_and_resource_caps_are_strict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = SINGLE.read_bytes()
    for value in (bytearray(source), memoryview(source), source.decode("ascii")):
        with pytest.raises(TypeError):
            parse_mmcif_polymer_sequence(value)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        parse_mmcif_polymer_sequence(source, source_id=1)  # type: ignore[arg-type]

    import betelgeuze_engine_v2.molecular.mmcif_polymer_sequence as module

    monkeypatch.setattr(module, "MAX_MMCIF_POLYMER_SEQUENCE_ROWS", 1)
    _assert_error(source, "too_many_sequence_rows")
    monkeypatch.setattr(
        module, "MAX_MMCIF_POLYMER_SEQUENCE_ROWS", MAX_MMCIF_POLYMER_SEQUENCE_ROWS
    )
    monkeypatch.setattr(
        module, "MAX_MMCIF_POLYMER_SEQUENCE_INPUT_BYTES", len(source) - 1
    )
    _assert_error(source, "input_too_large")
    assert MAX_MMCIF_POLYMER_SEQUENCE_INPUT_BYTES == 64 * 1024 * 1024


def test_artifacts_are_factory_only_frozen_repr_hidden_and_detached() -> None:
    ingest = parse_mmcif_polymer_sequence(OPAQUE.read_bytes())
    result = round_trip_mmcif_polymer_sequence_source(OPAQUE.read_bytes())
    row = ingest.sequence_rows[0]

    for artifact in (
        row,
        ingest,
        result.write_result.receipt,
        result.write_result,
        result.report,
        result,
    ):
        assert "MSE" not in repr(artifact)
    with pytest.raises(TypeError, match="factory-only"):
        type(row)(
            entity_id="1",
            num=1,
            mon_id="MSE",
            hetero="n",
            coordinate_observed=True,
            observed_asym_ids=("A",),
        )
    with pytest.raises(TypeError, match="factory-only"):
        type(result.write_result.receipt)()
    with pytest.raises(TypeError, match="factory-only"):
        type(result.report)()
    with pytest.raises(FrozenInstanceError):
        row.mon_id = "CHANGED"  # type: ignore[misc]

    first = ingest.system
    original = float(ingest.system.coordinates[0, 0, 0])
    first.coordinates[0, 0, 0] = original + 100.0
    assert float(ingest.system.coordinates[0, 0, 0]) == original
    assert emit_mmcif_polymer_sequence(ingest).payload == (
        emit_mmcif_polymer_sequence(
            parse_mmcif_polymer_sequence(OPAQUE.read_bytes())
        ).payload
    )


def test_stale_ingest_source_and_projection_bindings_are_rejected() -> None:
    ingest = parse_mmcif_polymer_sequence(SINGLE.read_bytes())
    object.__setattr__(ingest, "polymer_sequence_projection_sha256", "0" * 64)
    with pytest.raises(MmcifPolymerSequenceError) as exc_info:
        emit_mmcif_polymer_sequence(ingest)
    assert exc_info.value.code == "stale_ingest_binding"

    ingest = parse_mmcif_polymer_sequence(SINGLE.read_bytes())
    object.__setattr__(ingest, "_full_source_bytes", ingest._full_source_bytes + b"#\n")
    with pytest.raises(MmcifPolymerSequenceError) as exc_info:
        emit_mmcif_polymer_sequence(ingest)
    assert exc_info.value.code == "stale_ingest_binding"


def test_base_evidence_and_composed_carrier_are_fresh_source_bound() -> None:
    ingest = parse_mmcif_polymer_sequence(SINGLE.read_bytes())
    foreign = parse_mmcif_polymer_sequence(SHARED_ASYM.read_bytes())
    object.__setattr__(ingest, "_base_coverage", foreign.base_ingest.coverage)
    with pytest.raises(ValueError, match="source artifacts"):
        ingest.__post_init__()
    with pytest.raises(MmcifPolymerSequenceError) as exc_info:
        emit_mmcif_polymer_sequence(ingest)
    assert exc_info.value.code == "stale_ingest_binding"

    result = round_trip_mmcif_polymer_sequence_source(SINGLE.read_bytes())
    coverage = result.source_ingest.base_ingest.coverage
    claim = SourceReportedMissingResidueClaim(
        source_ordinal=1,
        source_category="audit",
        source_model_id="1",
        source_chain_id="A",
        source_residue_id="2",
        source_residue_name="ALA",
        raw_payload={"reported": True},
    )
    foreign_missingness = build_source_reported_missingness_report(
        source_format="mmcif",
        source_sha256=hashlib.sha256(b"foreign-source").hexdigest(),
        canonical_topology_sha256=coverage.canonical_topology_sha256,
        coordinate_scope=coverage.coordinate_scope,
        altloc_status=coverage.altloc_status,
        requested_altloc_id=coverage.requested_altloc_id,
        assembly_status=coverage.assembly_status,
        requested_assembly_id=coverage.requested_assembly_id,
        missing_residue_claims=(claim,),
    )
    object.__setattr__(
        result.source_ingest,
        "_base_missingness_evidence",
        foreign_missingness,
    )
    with pytest.raises(ValueError, match="stale nested artifact"):
        result.__post_init__()

    mixed = parse_mmcif_polymer_sequence(MIXED.read_bytes())
    foreign_nonpoly = parse_mmcif_nonpoly_identity(mixed._carrier_source_bytes + b"#\n")
    assert foreign_nonpoly.record_state_sha256 == (
        mixed.nonpoly_identity_record_state_sha256
    )
    assert foreign_nonpoly._full_source_bytes != mixed._carrier_source_bytes
    object.__setattr__(mixed, "_nonpoly_ingest", foreign_nonpoly)
    with pytest.raises(ValueError, match="source artifacts"):
        mixed.__post_init__()


def test_public_nested_views_are_detached_from_bound_artifacts() -> None:
    ingest = parse_mmcif_polymer_sequence(MIXED.read_bytes())
    base_view = ingest.base_ingest
    original_atom_count = base_view.coverage.atom_count
    object.__setattr__(base_view.coverage, "atom_count", original_atom_count + 100)
    assert ingest.base_ingest.coverage.atom_count == original_atom_count

    nonpoly_view = ingest.nonpoly_ingest
    assert nonpoly_view is not None
    original_state = nonpoly_view.record_state_sha256
    object.__setattr__(nonpoly_view, "record_state_sha256", "0" * 64)
    assert ingest.nonpoly_ingest is not None
    assert ingest.nonpoly_ingest.record_state_sha256 == original_state


def test_source_binding_blocks_semantic_crosswire() -> None:
    ala = parse_mmcif_polymer_sequence(UNOBSERVED.read_bytes())
    val_source = _replace_once(UNOBSERVED.read_bytes(), b"1 2 ALA n\n", b"1 2 VAL n\n")
    val = parse_mmcif_polymer_sequence(val_source)
    assert ala.base_topology_sha256 == val.base_topology_sha256
    assert (
        ala.polymer_sequence_projection_sha256 != val.polymer_sequence_projection_sha256
    )

    object.__setattr__(ala, "sequence_rows", val.sequence_rows)
    object.__setattr__(
        ala,
        "polymer_sequence_projection_sha256",
        val.polymer_sequence_projection_sha256,
    )
    object.__setattr__(ala, "record_state_sha256", val.record_state_sha256)
    object.__setattr__(ala, "source_binding_sha256", val.source_binding_sha256)
    with pytest.raises(MmcifPolymerSequenceError) as exc_info:
        emit_mmcif_polymer_sequence(ala)
    assert exc_info.value.code == "stale_ingest_binding"


@pytest.mark.parametrize(
    "field_name",
    (
        "reparsed_polymer_sequence_projection_sha256",
        "reparsed_record_state_sha256",
        "reemitted_source_sha256",
    ),
)
def test_report_recomputes_declared_equality_invariants(field_name: str) -> None:
    report = round_trip_mmcif_polymer_sequence_source(SINGLE.read_bytes()).report
    object.__setattr__(report, field_name, "0" * 64)
    object.__setattr__(
        report, "report_sha256", _sha256_document(_report_payload(report))
    )
    with pytest.raises(ValueError, match="equality evidence"):
        report.__post_init__()


def test_nested_receipt_report_and_aggregate_tamper_are_rejected() -> None:
    result = round_trip_mmcif_polymer_sequence_source(SINGLE.read_bytes())
    object.__setattr__(result.write_result.receipt, "receipt_sha256", "0" * 64)
    with pytest.raises(ValueError):
        result.__post_init__()

    result = round_trip_mmcif_polymer_sequence_source(SINGLE.read_bytes())
    object.__setattr__(
        result.write_result.receipt,
        "coordinate_observed_sequence_row_count",
        True,
    )
    with pytest.raises(ValueError):
        result.__post_init__()

    result = round_trip_mmcif_polymer_sequence_source(SINGLE.read_bytes())
    object.__setattr__(result.report, "report_sha256", "0" * 64)
    with pytest.raises(ValueError):
        result.__post_init__()


def test_same_output_receipt_crosswire_is_rejected_by_aggregate() -> None:
    canonical = round_trip_mmcif_polymer_sequence_source(SINGLE.read_bytes())
    reordered = round_trip_mmcif_polymer_sequence_source(CATEGORY_ORDER.read_bytes())
    assert canonical.write_result.payload == reordered.write_result.payload

    object.__setattr__(canonical, "write_result", reordered.write_result)
    with pytest.raises(ValueError, match="cross-consistent"):
        canonical.__post_init__()


@pytest.mark.parametrize(
    "source_path,old,new",
    (
        (UNOBSERVED, b"1 2 ALA n\n", b"1 2 VAL n\n"),
        (SINGLE, b"? 0.0 0.0 0.0 1.0", b"? 9.0 0.0 0.0 1.0"),
        (MIXED, b"3 water HOH\n", b"3 WATER HOH\n"),
    ),
    ids=("sequence_projection", "base_state", "nonpoly_projection"),
)
def test_standalone_write_result_binds_payload_semantics_to_receipt_input(
    source_path: Path,
    old: bytes,
    new: bytes,
) -> None:
    result = round_trip_mmcif_polymer_sequence_source(source_path.read_bytes())
    tampered = _replace_once(result.write_result.payload, old, new)
    object.__setattr__(result.write_result, "payload", tampered)
    object.__setattr__(
        result.write_result.receipt,
        "output_source_sha256",
        hashlib.sha256(tampered).hexdigest(),
    )
    object.__setattr__(
        result.write_result.receipt,
        "output_byte_count",
        len(tampered),
    )
    object.__setattr__(
        result.write_result.receipt,
        "receipt_sha256",
        _sha256_document(_receipt_payload(result.write_result.receipt)),
    )
    with pytest.raises(ValueError, match="state binding"):
        result.write_result.__post_init__()


def test_standalone_write_result_requires_a_canonical_payload_fixed_point() -> None:
    result = round_trip_mmcif_polymer_sequence_source(SINGLE.read_bytes())
    tampered = _replace_once(
        result.write_result.payload, b"1 2 ALA n\n", b"1 2 ALA no\n"
    )
    object.__setattr__(result.write_result, "payload", tampered)
    object.__setattr__(
        result.write_result.receipt,
        "output_source_sha256",
        hashlib.sha256(tampered).hexdigest(),
    )
    object.__setattr__(result.write_result.receipt, "output_byte_count", len(tampered))
    object.__setattr__(
        result.write_result.receipt,
        "receipt_sha256",
        _sha256_document(_receipt_payload(result.write_result.receipt)),
    )
    with pytest.raises(ValueError, match="state binding"):
        result.write_result.__post_init__()


@pytest.mark.parametrize(
    "field_name,value",
    (
        ("entity_id", ""),
        ("mon_id", "비공개"),
        ("mon_id", "X" * (MAX_MMCIF_POLYMER_SEQUENCE_TOKEN_CHARS + 1)),
        ("num", MAX_MMCIF_POLYMER_SEQUENCE_ROWS + 1),
        ("observed_asym_ids", ("A", "비공개")),
    ),
)
def test_sequence_row_revalidation_rejects_out_of_contract_values(
    field_name: str,
    value: object,
) -> None:
    row = parse_mmcif_polymer_sequence(SINGLE.read_bytes()).sequence_rows[0]
    object.__setattr__(row, field_name, value)
    with pytest.raises((TypeError, ValueError)):
        row.__post_init__()


def test_public_attestation_serializers_revalidate_before_claiming_success() -> None:
    ingest = parse_mmcif_polymer_sequence(SINGLE.read_bytes())
    object.__setattr__(ingest, "polymer_sequence_projection_sha256", "0" * 64)
    with pytest.raises(ValueError):
        ingest.to_dict()

    result = round_trip_mmcif_polymer_sequence_source(SINGLE.read_bytes())
    object.__setattr__(result.write_result.receipt, "receipt_sha256", "0" * 64)
    with pytest.raises(ValueError):
        result.write_result.receipt.to_dict()

    result = round_trip_mmcif_polymer_sequence_source(SINGLE.read_bytes())
    object.__setattr__(result.report, "report_sha256", "0" * 64)
    with pytest.raises(ValueError):
        result.report.to_dict()
    with pytest.raises(ValueError, match="stale nested artifact"):
        result.to_dict()


def test_factory_reuses_validated_components_but_public_paths_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = polymer_sequence_module._parse_components
    call_count = 0

    def counted(*args: object, **kwargs: object):
        nonlocal call_count
        call_count += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(polymer_sequence_module, "_parse_components", counted)
    result = polymer_sequence_module.round_trip_mmcif_polymer_sequence_source(
        SINGLE.read_bytes()
    )
    assert call_count == 6

    result.source_ingest.to_dict()
    assert call_count == 7
    result.to_dict()
    assert call_count == 11


def test_data_block_name_tamper_is_typed_and_does_not_echo_unicode() -> None:
    ingest = parse_mmcif_polymer_sequence(SINGLE.read_bytes())
    object.__setattr__(ingest, "data_block_name", 123)
    with pytest.raises(TypeError, match="data_block_name"):
        ingest.__post_init__()

    ingest = parse_mmcif_polymer_sequence(SINGLE.read_bytes())
    object.__setattr__(ingest, "data_block_name", "PRIVATE-\udcff-NAME")
    with pytest.raises(TypeError, match="ASCII") as exc_info:
        ingest.__post_init__()
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert "PRIVATE" not in str(exc_info.value)

    ingest = parse_mmcif_polymer_sequence(SINGLE.read_bytes())
    object.__setattr__(ingest, "data_block_name", "PRIVATE-\udcff-NAME")
    with pytest.raises(MmcifPolymerSequenceError) as public_exc_info:
        emit_mmcif_polymer_sequence(ingest)
    assert public_exc_info.value.code == "stale_ingest_binding"
    assert public_exc_info.value.__cause__ is None
    assert public_exc_info.value.__context__ is None
    assert "PRIVATE" not in str(public_exc_info.value)


@pytest.mark.parametrize(
    "path",
    sorted(FIXTURES.glob("*.cif")),
    ids=lambda path: path.stem,
)
def test_every_positive_fixture_has_stable_second_emission(path: Path) -> None:
    result = round_trip_mmcif_polymer_sequence_source(
        path.read_bytes(), source_id=path.stem
    )
    assert result.write_result.payload == result.reemitted_write_result.payload
    assert result.report.second_emission_byte_stable is True
    assert result.report.polymer_sequence_projection_sha256_equal is True
    assert result.report.record_state_sha256_equal is True
