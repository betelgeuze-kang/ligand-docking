from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import betelgeuze_engine_v2.molecular.mmcif_zero_occupancy_residues as residue_module
from betelgeuze_engine_v2.molecular.mmcif_zero_occupancy_residues import (
    MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_ROWS,
    MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_SOURCE_ID_BYTES,
    MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_TOKEN_CHARS,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_PROFILE_ID,
    MMCIF_ZERO_OCCUPANCY_RESIDUE_PROJECTION_SCOPE,
    MmcifZeroOccupancyResidueError,
    MmcifZeroOccupancyResidueIngestResult,
    MmcifZeroOccupancyResidueRoundTripReport,
    MmcifZeroOccupancyResidueRoundTripResult,
    MmcifZeroOccupancyResidueRow,
    MmcifZeroOccupancyResidueWriteReceipt,
    MmcifZeroOccupancyResidueWriteResult,
    emit_mmcif_zero_occupancy_residues,
    mmcif_zero_occupancy_residue_projection_sha256,
    mmcif_zero_occupancy_residue_record_state_sha256,
    parse_mmcif_zero_occupancy_residues,
    round_trip_mmcif_zero_occupancy_residues_source,
    serialize_mmcif_zero_occupancy_residues,
)


FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "v2_1_mmcif_unobserved_residues"
)

_SINGLE_DECLARATION = b"1 Y 0 1 X ALA 102 ? A ALA 2"
_SINGLE_COORDINATE = b"ATOM 2 C CA . ALA A 1 2 ? 1 0 0 0.0 20.0 ? 102 ALA X CA 1"
_FALSE_GATES = (
    "source_authenticated",
    "auth_label_equivalence_inferred",
    "reference_sequence_equivalence_assessed",
    "coordinate_observation_completeness_assessed",
    "missing_residue_fact_claimed",
    "zero_occupancy_missingness_inferred",
    "occupancy_population_interpreted",
    "occupancy_weighting_applied",
    "refinement_validity_assessed",
    "altloc_population_interpreted",
    "sequence_completeness_claimed",
    "modeled_residue_presence_assessed",
    "modified_residue_identity_assessed",
    "polymer_chemistry_interpreted",
    "microheterogeneity_interpreted",
    "chemistry_interpreted",
    "role_assignment_interpreted",
    "bond_topology_interpreted",
    "bond_order_interpreted",
    "coordination_interpreted",
    "charge_interpreted",
    "protonation_interpreted",
    "preparation_ready",
    "parameterability_assessed",
    "physics_supported",
    "runtime_eligible",
    "simulation_ready",
    "execution_authorized",
    "claim_safe",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
)


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    assert source.count(old) == 1
    return source.replace(old, new, 1)


def _fixture(name: str) -> bytes:
    source = (FIXTURES / name).read_bytes().replace(b" Y 1 1 ", b" Y 0 1 ")
    replacements: dict[str, tuple[tuple[bytes, bytes], ...]] = {
        "single_unobserved_member.cif": (
            (
                b"ATOM 2 O OG . SER A 1 3 ? 2 0 0 1.0 20.0 ? 103 SER X OG 1",
                _SINGLE_COORDINATE
                + b"\nATOM 3 O OG . SER A 1 3 ? 2 0 0 1.0 20.0 ? 103 SER X OG 1",
            ),
        ),
        "multiple_ordered_claims.cif": (
            (
                b"ATOM 2 O OG1 . THR A 1 4 ? 3 0 0 1.0 20.0 ? 104 THR X OG1 1",
                b"ATOM 2 C CA . ALA A 1 2 ? 1 0 0 -0.0 20.0 ? 102 ALA X CA 1\n"
                b"ATOM 3 O OG . SER A 1 3 ? 2 0 0 0e0 20.0 ? 103 SER X OG 1\n"
                b"ATOM 4 O OG1 . THR A 1 4 ? 3 0 0 1.0 20.0 ? 104 THR X OG1 1",
            ),
        ),
        "insertion_marker_auth_alias.cif": (
            (
                b"ATOM 2 O OG . SER A 1 3 ? 2 0 0 1.0 20.0 ? AUTH-43 SER AUTH-A OG 1",
                b"ATOM 2 C CA . ALA A 1 2 B 1 0 0 .0 20.0 ? AUTH-42 ALA AUTH-A CA 1\n"
                b"ATOM 3 O OG . SER A 1 3 ? 2 0 0 1.0 20.0 ? AUTH-43 SER AUTH-A OG 1",
            ),
        ),
        "shared_entity_multiple_asym.cif": (
            (
                b"ATOM 2 O OG . SER A 1 3 ? 2 0 0 1.0 20.0 ? 103 SER AX OG 1",
                b"ATOM 2 C CA . ALA A 1 2 ? 1 0 0 0 20.0 ? 102 ALA AX CA 1\n"
                b"ATOM 5 O OG . SER A 1 3 ? 2 0 0 1.0 20.0 ? 103 SER AX OG 1",
            ),
            (
                b"ATOM 4 C CA . ALA B 1 2 ? 1 1 0 1.0 20.0 ? 202 ALA BX CA 1",
                b"ATOM 4 O OG . SER B 1 3 ? 2 1 0 0.00 20.0 ? 203 SER BX OG 1",
            ),
        ),
        "composed_nonpoly_carrier.cif": (
            (
                b"ATOM 1 C CA . GLY A 1 1 ? 0.0 0.0 0.0 1.0 20.0 ? 101 GLY AX CA 1",
                b"ATOM 1 C CA . GLY A 1 1 ? 0.0 0.0 0.0 1.0 20.0 ? 101 GLY AX CA 1\n"
                b"ATOM 3 C CA . ALA A 1 2 ? 0.5 0.0 0.0 0.0 20.0 ? 102 ALA AX CA 1",
            ),
        ),
        "category_order_variant.cif": (
            (
                b"ATOM 2 O OG . SER A 1 3 ? 2 0 0 1.0 20.0 ? 103 SER X OG 1",
                _SINGLE_COORDINATE
                + b"\nATOM 3 O OG . SER A 1 3 ? 2 0 0 1.0 20.0 ? 103 SER X OG 1",
            ),
        ),
    }
    for old, new in replacements[name]:
        source = _replace_once(source, old, new)
    return source


SINGLE = _fixture("single_unobserved_member.cif")
MULTIPLE = _fixture("multiple_ordered_claims.cif")
INSERTION = _fixture("insertion_marker_auth_alias.cif")
SHARED = _fixture("shared_entity_multiple_asym.cif")
COMPOSED = _fixture("composed_nonpoly_carrier.cif")
CATEGORY_ORDER = _fixture("category_order_variant.cif")


def _assert_error(source: bytes, code: str) -> MmcifZeroOccupancyResidueError:
    with pytest.raises(MmcifZeroOccupancyResidueError) as exc_info:
        parse_mmcif_zero_occupancy_residues(source)
    assert exc_info.value.code == code
    return exc_info.value


def _assert_false_authority(document: dict[str, object]) -> None:
    assert (
        document["source_reported_zero_occupancy_residue_declarations_preserved"]
        is True
    )
    for field_name in _FALSE_GATES:
        assert document[field_name] is False


def test_parse_preserves_ordered_declarations_and_base_zero_metadata() -> None:
    ingest = parse_mmcif_zero_occupancy_residues(MULTIPLE, source_id="fixture://two")

    assert [row.source_id for row in ingest.zero_occupancy_residue_rows] == [1, 2]
    assert [row.label_comp_id for row in ingest.zero_occupancy_residue_rows] == [
        "ALA",
        "SER",
    ]
    assert ingest.carrier_kind == "mmcif_polymer_sequence"
    assert ingest.has_nonpoly_identity is False
    assert len(ingest.base_missingness_metadata_sha256) == 64
    assert ingest.missingness_report.source_reported_missing_residue_count == 0
    assert ingest.missingness_report.source_reported_missing_atom_count == 0
    summary = ingest.base_ingest.system.metadata["mmcif"]["source_missingness"]
    assert summary["residue_row_count"] == 2
    assert summary["atom_row_count"] == 0
    assert summary["zero_occupancy_residue_row_count"] == 2
    assert summary["zero_occupancy_atom_row_count"] == 0
    assert summary["unobserved_residue_claim_count"] == 0
    assert summary["unobserved_atom_claim_count"] == 0
    assert summary["extension_item_count"] == 0
    document = ingest.to_dict()
    assert document["profile_id"] == MMCIF_ZERO_OCCUPANCY_RESIDUE_PROFILE_ID
    assert document["source_reported_missing_residue_claim_count"] == 0
    assert document["source_reported_missing_atom_claim_count"] == 0
    assert document["source_reported_zero_occupancy_residue_declaration_count"] == 2
    _assert_false_authority(document)


def test_projection_contract_is_exact_zero_declaration_only() -> None:
    ingest = parse_mmcif_zero_occupancy_residues(SINGLE)

    assert MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS[2].endswith(".occupancy_flag")
    assert "exact_selected_coordinate_zero_crosscheck_only" in (
        MMCIF_ZERO_OCCUPANCY_RESIDUE_PROJECTION_SCOPE
    )
    assert (
        mmcif_zero_occupancy_residue_projection_sha256(ingest)
        == ingest.zero_occupancy_residue_projection_sha256
    )
    assert mmcif_zero_occupancy_residue_record_state_sha256(ingest) == (
        ingest.record_state_sha256
    )


@pytest.mark.parametrize("source", [SINGLE, MULTIPLE, INSERTION, SHARED, COMPOSED])
def test_canonical_round_trip_is_stable_and_non_promoting(source: bytes) -> None:
    result = round_trip_mmcif_zero_occupancy_residues_source(
        source, source_id="fixture://stable"
    )

    assert result.write_result.payload == result.reemitted_write_result.payload
    assert b" Y 0 1 " in result.write_result.payload
    assert serialize_mmcif_zero_occupancy_residues(result.source_ingest) == (
        result.write_result.payload
    )
    report = result.report.to_dict()
    assert report["projection_sha256_equal"] is True
    assert report["record_state_sha256_equal"] is True
    assert report["base_missingness_metadata_sha256_equal"] is True
    assert report["second_emission_byte_stable"] is True
    assert report["missingness_report_sha256_equality_claimed"] is False
    _assert_false_authority(report)
    _assert_false_authority(result.to_dict())


def test_composed_nonpoly_carrier_is_preserved_without_nonpoly_promotion() -> None:
    result = round_trip_mmcif_zero_occupancy_residues_source(COMPOSED)

    assert result.source_ingest.has_nonpoly_identity is True
    assert result.source_ingest.carrier_kind == (
        "mmcif_polymer_sequence_nonpoly_identity"
    )
    assert result.source_ingest.nonpoly_identity_projection_sha256 is not None
    assert b"_pdbx_entity_nonpoly.entity_id" in result.write_result.payload
    assert result.report.nonpoly_identity_projection_sha256_equal is True
    assert result.report.nonpoly_identity_record_state_sha256_equal is True


def test_category_order_variant_canonicalizes_to_official_order() -> None:
    emitted = emit_mmcif_zero_occupancy_residues(
        parse_mmcif_zero_occupancy_residues(CATEGORY_ORDER)
    ).payload

    assert emitted.index(b"_entity.id") < emitted.index(b"_struct_asym.id")
    assert emitted.index(b"_entity_poly_seq.entity_id") < emitted.index(
        b"_pdbx_unobs_or_zero_occ_residues.id"
    )
    assert emitted.index(b"_pdbx_unobs_or_zero_occ_residues.id") < emitted.index(
        b"_atom_site.group_pdb"
    )


@pytest.mark.parametrize(
    ("old", "new", "code"),
    [
        (
            b"1 Y 0 1 X ALA 102 ? A ALA 2",
            b"1 Y 1 1 X ALA 102 ? A ALA 2",
            "unsupported_zero_occupancy_residue_occupancy_flag",
        ),
        (
            b"1 Y 0 1 X ALA 102 ? A ALA 2",
            b"1 N 0 1 X ALA 102 ? A ALA 2",
            "unsupported_zero_occupancy_residue_polymer_flag",
        ),
        (
            b"1 Y 0 1 X ALA 102 ? A ALA 2",
            b"1 Y 0 2 X ALA 102 ? A ALA 2",
            "unsupported_zero_occupancy_residue_model",
        ),
        (
            _SINGLE_COORDINATE,
            _SINGLE_COORDINATE.replace(b" 0.0 20.0 ", b" 0.5 20.0 "),
            "zero_occupancy_residue_value_conflict",
        ),
        (
            _SINGLE_COORDINATE,
            _SINGLE_COORDINATE.replace(b" 0.0 20.0 ", b" . 20.0 "),
            "zero_occupancy_residue_value_conflict",
        ),
        (
            _SINGLE_COORDINATE,
            _SINGLE_COORDINATE.replace(b" 0.0 20.0 ", b" 0.0(1) 20.0 "),
            "zero_occupancy_residue_value_conflict",
        ),
    ],
)
def test_flags_and_matching_coordinate_occupancy_fail_closed(
    old: bytes, new: bytes, code: str
) -> None:
    _assert_error(_replace_once(SINGLE, old, new), code)


def test_declared_residue_must_be_present_in_selected_atom_site() -> None:
    _assert_error(
        _replace_once(SINGLE, _SINGLE_COORDINATE + b"\n", b""),
        "zero_occupancy_residue_not_present",
    )


def test_every_matching_atom_occupancy_must_be_exact_numeric_zero() -> None:
    conflicting = _replace_once(
        SINGLE,
        _SINGLE_COORDINATE,
        _SINGLE_COORDINATE
        + b"\nATOM 4 O O . ALA A 1 2 ? 1 1 0 1.0 20.0 ? 102 ALA X O 1",
    )
    _assert_error(conflicting, "zero_occupancy_residue_value_conflict")


def test_duplicate_source_id_and_semantic_identity_are_rejected() -> None:
    duplicate_id = _replace_once(
        SINGLE,
        _SINGLE_DECLARATION,
        _SINGLE_DECLARATION + b"\n" + _SINGLE_DECLARATION,
    )
    _assert_error(duplicate_id, "duplicate_or_invalid_zero_occupancy_residue_id")

    duplicate_identity = _replace_once(
        SINGLE,
        _SINGLE_DECLARATION,
        _SINGLE_DECLARATION + b"\n2 Y 0 1 X ALA 102 ? A ALA 2",
    )
    _assert_error(duplicate_identity, "duplicate_zero_occupancy_residue_identity")


def test_atom_only_and_mixed_zero_occupancy_categories_fail_closed() -> None:
    atom_only = SINGLE.replace(
        b"_pdbx_unobs_or_zero_occ_residues.",
        b"_pdbx_unobs_or_zero_occ_atoms.",
    )
    _assert_error(atom_only, "atom_zero_occupancy_category_unsupported")

    marker = b"loop_\n_atom_site.group_PDB"
    mixed = _replace_once(
        SINGLE,
        marker,
        b"loop_\n_pdbx_unobs_or_zero_occ_atoms.id\n1\n#\n" + marker,
    )
    _assert_error(mixed, "mixed_zero_occupancy_categories_unsupported")


def test_exact_headers_category_surface_and_identity_joins_are_enforced() -> None:
    reordered = _replace_once(
        SINGLE,
        b"_pdbx_unobs_or_zero_occ_residues.id\n"
        b"_pdbx_unobs_or_zero_occ_residues.polymer_flag",
        b"_pdbx_unobs_or_zero_occ_residues.polymer_flag\n"
        b"_pdbx_unobs_or_zero_occ_residues.id",
    )
    _assert_error(reordered, "unsupported_category_headers")

    unknown_asym = _replace_once(
        SINGLE, _SINGLE_DECLARATION, b"1 Y 0 1 X ALA 102 ? Z ALA 2"
    )
    _assert_error(unknown_asym, "unknown_zero_occupancy_residue_asym_id")

    bad_member = _replace_once(
        SINGLE, _SINGLE_DECLARATION, b"1 Y 0 1 X THR 102 ? A THR 2"
    )
    _assert_error(bad_member, "zero_occupancy_residue_sequence_join_mismatch")


def test_source_id_token_and_row_resource_caps_are_bound() -> None:
    with pytest.raises(MmcifZeroOccupancyResidueError) as too_large:
        parse_mmcif_zero_occupancy_residues(
            SINGLE,
            source_id="x" * (MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_SOURCE_ID_BYTES + 1),
        )
    assert too_large.value.code == "source_id_too_large"

    with pytest.raises(MmcifZeroOccupancyResidueError) as invalid_unicode:
        parse_mmcif_zero_occupancy_residues(SINGLE, source_id="\ud800")
    assert invalid_unicode.value.code == "invalid_source_id"

    long_token = b"X" * (MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_TOKEN_CHARS + 1)
    _assert_error(
        _replace_once(
            SINGLE,
            _SINGLE_DECLARATION,
            b"1 Y 0 1 " + long_token + b" ALA 102 ? A ALA 2",
        ),
        "invalid_identity_token",
    )

    excess_rows = b"\n".join(
        _SINGLE_DECLARATION for _ in range(MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_ROWS + 1)
    )
    _assert_error(
        _replace_once(SINGLE, _SINGLE_DECLARATION, excess_rows),
        "too_many_zero_occupancy_residue_rows",
    )


def test_source_id_is_bound_but_never_exposed() -> None:
    first = parse_mmcif_zero_occupancy_residues(SINGLE, source_id="secret-A")
    second = parse_mmcif_zero_occupancy_residues(SINGLE, source_id="secret-B")

    assert first.source_id_sha256 != second.source_id_sha256
    assert first.source_binding_sha256 != second.source_binding_sha256
    assert first.record_state_sha256 == second.record_state_sha256
    assert "secret-A" not in repr(first)
    assert "secret-A" not in str(first.to_dict())


def test_artifacts_are_factory_only_and_frozen() -> None:
    for constructor in (
        MmcifZeroOccupancyResidueRow,
        MmcifZeroOccupancyResidueIngestResult,
        MmcifZeroOccupancyResidueWriteReceipt,
        MmcifZeroOccupancyResidueWriteResult,
        MmcifZeroOccupancyResidueRoundTripReport,
        MmcifZeroOccupancyResidueRoundTripResult,
    ):
        with pytest.raises(TypeError):
            constructor()  # type: ignore[call-arg]

    ingest = parse_mmcif_zero_occupancy_residues(SINGLE)
    with pytest.raises(FrozenInstanceError):
        ingest.record_state_sha256 = "0" * 64  # type: ignore[misc]


def test_nested_mutation_and_crosswire_fail_with_typed_errors() -> None:
    ingest = parse_mmcif_zero_occupancy_residues(SINGLE)
    object.__setattr__(ingest, "record_state_sha256", "0" * 64)
    with pytest.raises(MmcifZeroOccupancyResidueError) as stale_ingest:
        emit_mmcif_zero_occupancy_residues(ingest)
    assert stale_ingest.value.code == "stale_ingest_binding"

    result = round_trip_mmcif_zero_occupancy_residues_source(
        SINGLE, source_id="binding-A"
    )
    object.__setattr__(result.write_result.receipt, "_document_bytes", b"{}")
    with pytest.raises(MmcifZeroOccupancyResidueError):
        result.to_dict()

    first = round_trip_mmcif_zero_occupancy_residues_source(
        SINGLE, source_id="binding-A"
    )
    second = round_trip_mmcif_zero_occupancy_residues_source(
        SINGLE, source_id="binding-B"
    )
    target_name = (
        "_source_ingest" if hasattr(first, "_source_ingest") else "source_ingest"
    )
    object.__setattr__(first, target_name, second.source_ingest)
    with pytest.raises(MmcifZeroOccupancyResidueError) as crosswired:
        first.to_dict()
    assert crosswired.value.code == "crosswired_round_trip_artifacts"


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    (
        ("source_id", True),
        ("source_id", 1.0),
        ("label_seq_id", True),
        ("label_seq_id", 1.0),
    ),
)
def test_row_integer_type_equality_collisions_fail_closed(
    field_name: str, replacement: object
) -> None:
    ingest = parse_mmcif_zero_occupancy_residues(SINGLE)
    object.__setattr__(ingest.zero_occupancy_residue_rows[0], field_name, replacement)

    with pytest.raises(MmcifZeroOccupancyResidueError) as document_exc:
        ingest.to_dict()
    assert document_exc.value.code == "stale_ingest_binding"
    with pytest.raises(MmcifZeroOccupancyResidueError) as emit_exc:
        emit_mmcif_zero_occupancy_residues(ingest)
    assert emit_exc.value.code == "stale_ingest_binding"


@pytest.mark.parametrize("receipt_kind", ("write", "reemitted"))
def test_aggregate_accessors_reject_receipt_ingest_mutation(
    receipt_kind: str,
) -> None:
    result = round_trip_mmcif_zero_occupancy_residues_source(SINGLE)
    write_result = (
        result._write_result
        if receipt_kind == "write"
        else result._reemitted_write_result
    )
    object.__setattr__(
        write_result.receipt._ingest,
        "record_state_sha256",
        "0" * 64,
    )
    for accessor_name in (
        "source_ingest",
        "write_result",
        "reparsed_ingest",
        "reemitted_write_result",
        "report",
    ):
        with pytest.raises(MmcifZeroOccupancyResidueError) as accessor_exc:
            getattr(result, accessor_name)
        assert accessor_exc.value.code == "crosswired_round_trip_artifacts"
    with pytest.raises(MmcifZeroOccupancyResidueError) as document_exc:
        result.to_dict()
    assert document_exc.value.code == "crosswired_round_trip_artifacts"


def test_aggregate_accessors_reject_row_container_mutation() -> None:
    result = round_trip_mmcif_zero_occupancy_residues_source(SINGLE)
    object.__setattr__(
        result._source_ingest,
        "zero_occupancy_residue_rows",
        list(result._source_ingest.zero_occupancy_residue_rows),
    )
    for accessor_name in (
        "source_ingest",
        "write_result",
        "reparsed_ingest",
        "reemitted_write_result",
        "report",
    ):
        with pytest.raises(MmcifZeroOccupancyResidueError) as accessor_exc:
            getattr(result, accessor_name)
        assert accessor_exc.value.code == "crosswired_round_trip_artifacts"
    with pytest.raises(MmcifZeroOccupancyResidueError) as document_exc:
        result.to_dict()
    assert document_exc.value.code == "crosswired_round_trip_artifacts"


def test_input_types_remain_strict() -> None:
    with pytest.raises(TypeError):
        parse_mmcif_zero_occupancy_residues("not-bytes")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        parse_mmcif_zero_occupancy_residues(SINGLE, source_id=b"not-text")  # type: ignore[arg-type]
    _assert_error(SINGLE + "한".encode(), "non_ascii_input")


def test_resource_constant_matches_base_preserved_item_cap() -> None:
    assert MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_ROWS == 40_000 // len(
        MMCIF_ZERO_OCCUPANCY_RESIDUE_HEADERS
    )
    assert residue_module.MAX_MMCIF_ZERO_OCCUPANCY_RESIDUE_INPUT_BYTES == (
        64 * 1024 * 1024
    )
