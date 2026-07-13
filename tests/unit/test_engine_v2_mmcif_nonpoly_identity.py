from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
from pathlib import Path

import pytest

from betelgeuze_engine_v2.molecular import StructureParseError, parse_mmcif
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_identity import (
    MAX_MMCIF_NONPOLY_ENTITY_ROWS,
    MAX_MMCIF_NONPOLY_IDENTITY_INPUT_BYTES,
    MmcifNonpolyIdentityError,
    _report_payload,
    _sha256_document,
    mmcif_nonpoly_identity_projection_sha256,
    mmcif_nonpoly_identity_record_state_sha256,
    parse_mmcif_nonpoly_identity,
    round_trip_mmcif_nonpoly_identity_source,
    serialize_mmcif_nonpoly_identity,
    write_mmcif_nonpoly_identity,
)


FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "v2_1_mmcif_nonpoly_identity"
)
SINGLE_HEM = FIXTURES / "single_hem_complete.cif"
QUOTED_NAME = FIXTURES / "quoted_name_multiword.cif"
MIXED = FIXTURES / "mixed_polymer_nonpoly_water.cif"
MULTI_INSTANCE = FIXTURES / "same_comp_multiple_instances.cif"
CATEGORY_ORDER_VARIANT = FIXTURES / "category_order_variant.cif"


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    assert source.count(old) == 1
    return source.replace(old, new, 1)


def _loop_span(source: bytes, category: bytes) -> tuple[int, int]:
    marker = b"loop_\n" + category + b"."
    start = source.index(marker)
    end = source.index(b"#\n", start) + 2
    return start, end


def _replace_loop(source: bytes, category: bytes, replacement: bytes) -> bytes:
    start, end = _loop_span(source, category)
    return source[:start] + replacement + source[end:]


def _inject_before_atom_site(source: bytes, section: bytes) -> bytes:
    start, _ = _loop_span(source, b"_atom_site")
    return source[:start] + section + source[start:]


def _assert_error(source: bytes, code: str) -> MmcifNonpolyIdentityError:
    with pytest.raises(MmcifNonpolyIdentityError) as exc_info:
        parse_mmcif_nonpoly_identity(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_single_hem_complete_join_and_base_parser_is_unchanged() -> None:
    source = SINGLE_HEM.read_bytes()
    ingest = parse_mmcif_nonpoly_identity(source, source_id="single-hem")
    write_result = write_mmcif_nonpoly_identity(ingest)

    assert ingest.full_source_sha256 == hashlib.sha256(source).hexdigest()
    assert ingest.system.system_id == "single-hem"
    assert [(chain.chain_id, chain.entity_id) for chain in ingest.system.chains] == [
        ("L", "1")
    ]
    assert [
        (residue.name, residue.entity_type) for residue in ingest.system.residues
    ] == [("HEM", "non_polymer")]
    assert [(row.entity_id, row.comp_id, row.name) for row in ingest.entity_rows] == [
        ("1", "HEM", None)
    ]
    assert [
        (
            row.asym_id,
            row.entity_id,
            row.mon_id,
            row.ndb_seq_num,
            row.pdb_seq_num,
            row.auth_seq_num,
            row.pdb_mon_id,
            row.auth_mon_id,
            row.pdb_strand_id,
            row.pdb_ins_code,
        )
        for row in ingest.scheme_rows
    ] == [("L", "1", "HEM", "1", "501", "501", "HEM", "HEM", "X", ".")]
    assert write_result.payload.startswith(b"data_single_hem_complete\n")
    assert b"_pdbx_entity_nonpoly.entity_id" in write_result.payload
    assert b"_pdbx_nonpoly_scheme.ndb_seq_num" in write_result.payload
    assert serialize_mmcif_nonpoly_identity(ingest) == write_result.payload
    assert mmcif_nonpoly_identity_projection_sha256(ingest) == (
        ingest.identity_projection_sha256
    )
    assert mmcif_nonpoly_identity_record_state_sha256(ingest) == (
        ingest.record_state_sha256
    )

    with pytest.raises(StructureParseError) as exc_info:
        parse_mmcif(source, source_id="single-hem")
    assert exc_info.value.code == "unsupported_context_category"


def test_quoted_multiword_name_is_preserved_but_repr_hidden() -> None:
    source = QUOTED_NAME.read_bytes()
    ingest = parse_mmcif_nonpoly_identity(source)
    output = write_mmcif_nonpoly_identity(ingest).payload

    assert ingest.entity_rows[0].name == "Heme cofactor alpha"
    assert ingest.scheme_rows[0].auth_seq_num == "A-7"
    assert ingest.scheme_rows[0].pdb_mon_id == "PHEM"
    assert ingest.scheme_rows[0].auth_mon_id == "AHEM"
    assert b"'Heme cofactor alpha'" in output
    assert "Heme cofactor alpha" not in repr(ingest)
    assert "A-7" not in repr(ingest)
    assert "PHEM" not in repr(ingest)
    assert "AHEM" not in repr(ingest)
    assert "Heme cofactor alpha" not in repr(ingest.entity_rows[0])
    assert "A-7" not in repr(ingest.scheme_rows[0])


def test_dot_and_question_name_markers_are_distinct_opaque_values() -> None:
    source = QUOTED_NAME.read_bytes()
    dot = parse_mmcif_nonpoly_identity(
        _replace_once(source, b"'Heme cofactor alpha'", b".")
    )
    question = parse_mmcif_nonpoly_identity(
        _replace_once(source, b"'Heme cofactor alpha'", b"?")
    )

    assert dot.entity_rows[0].name == "."
    assert question.entity_rows[0].name == "?"
    assert dot.identity_projection_sha256 != question.identity_projection_sha256
    assert b"9 . HEM" in write_mmcif_nonpoly_identity(dot).payload
    assert b"9 ? HEM" in write_mmcif_nonpoly_identity(question).payload


def test_quoted_identifiers_and_multiline_names_fail_without_echo() -> None:
    source = QUOTED_NAME.read_bytes()
    quoted_identifier = _replace_once(
        source,
        b"Z 9 HEM 1 7 A-7 PHEM AHEM AUTHZ ?\n",
        b"'Z' 9 HEM 1 7 A-7 PHEM AHEM AUTHZ ?\n",
    )
    multiline_name = _replace_once(
        source,
        b"9 'Heme cofactor alpha' HEM\n",
        b"9\n;PRIVATE-NAME\nSECOND-LINE\n;\nHEM\n",
    )

    _assert_error(quoted_identifier, "invalid_identity_token")
    error = _assert_error(multiline_name, "invalid_nonpoly_name")
    assert "PRIVATE-NAME" not in str(error)
    assert "SECOND-LINE" not in repr(error)


def test_mixed_polymer_nonpoly_and_water_identity_does_not_promote_roles() -> None:
    result = round_trip_mmcif_nonpoly_identity_source(MIXED.read_bytes())
    system = result.source_ingest.system

    assert [(chain.chain_id, chain.entity_id) for chain in system.chains] == [
        ("A", "1"),
        ("L", "2"),
        ("W", "3"),
    ]
    assert [residue.entity_type for residue in system.residues] == [
        "polymer",
        "non_polymer",
        "water",
    ]

    for artifact in (
        result.source_ingest.to_dict(),
        result.write_result.receipt.to_dict(),
        result.report.to_dict(),
    ):
        assert artifact["source_authenticated"] is False
        assert artifact["chemistry_interpreted"] is False
        assert artifact["role_assignment_interpreted"] is False
        assert artifact["bond_topology_interpreted"] is False
        assert artifact["preparation_ready"] is False
        assert artifact["parameterability_assessed"] is False
        assert artifact["simulation_ready"] is False
        assert artifact["runtime_eligible"] is False
        assert artifact["claim_safe"] is False
        assert artifact["general_mmcif_round_trip_evidence_ready"] is False
        assert artifact["all_format_round_trip_evidence_ready"] is False


def test_same_component_multiple_instances_preserve_row_order_and_aliases() -> None:
    source = MULTI_INSTANCE.read_bytes()
    result = round_trip_mmcif_nonpoly_identity_source(source)
    output = result.write_result.payload

    assert [row.ndb_seq_num for row in result.source_ingest.scheme_rows] == ["2", "1"]
    assert [row.pdb_seq_num for row in result.source_ingest.scheme_rows] == [
        "9002",
        "9001",
    ]
    assert [row.auth_seq_num for row in result.source_ingest.scheme_rows] == [
        "AUTH-B",
        "AUTH-A",
    ]
    assert [row.pdb_mon_id for row in result.source_ingest.scheme_rows] == [
        "PHEM-B",
        "PHEM-A",
    ]
    assert [row.auth_mon_id for row in result.source_ingest.scheme_rows] == [
        "AHEM-B",
        "AHEM-A",
    ]
    second_row = b"L 1 HEM 2 9002 AUTH-B PHEM-B AHEM-B PDB-B ?"
    first_row = b"L 1 HEM 1 9001 AUTH-A PHEM-A AHEM-A PDB-A ."
    assert output.index(second_row) < output.index(first_row)
    assert result.report.input_identity_projection_sha256 == (
        result.report.reparsed_identity_projection_sha256
    )

    reversed_source = _replace_once(
        source,
        second_row + b"\n" + first_row + b"\n",
        first_row + b"\n" + second_row + b"\n",
    )
    reversed_result = round_trip_mmcif_nonpoly_identity_source(reversed_source)
    assert reversed_result.write_result.payload != output
    assert reversed_result.source_ingest.identity_projection_sha256 != (
        result.source_ingest.identity_projection_sha256
    )


def test_category_order_normalizes_and_second_emission_is_stable() -> None:
    canonical = round_trip_mmcif_nonpoly_identity_source(SINGLE_HEM.read_bytes())
    reordered = round_trip_mmcif_nonpoly_identity_source(
        CATEGORY_ORDER_VARIANT.read_bytes()
    )

    assert canonical.write_result.payload == reordered.write_result.payload
    assert canonical.report.input_identity_projection_sha256 == (
        reordered.report.input_identity_projection_sha256
    )
    assert canonical.report.emitted_source_sha256 == (
        canonical.report.reemitted_source_sha256
    )
    assert (
        canonical.write_result.payload
        == write_mmcif_nonpoly_identity(canonical.reparsed_ingest).payload
    )

    text = canonical.write_result.payload.decode("ascii").lower()
    assert text.index("_entity.id") < text.index("_struct_asym.id")
    assert text.index("_struct_asym.id") < text.index("_pdbx_entity_nonpoly.entity_id")
    assert text.index("_pdbx_entity_nonpoly.entity_id") < text.index(
        "_pdbx_nonpoly_scheme.asym_id"
    )
    assert text.index("_pdbx_nonpoly_scheme.asym_id") < text.index(
        "_atom_site.group_pdb"
    )


def test_stale_projection_and_same_output_receipt_crosswire_are_rejected() -> None:
    stale = parse_mmcif_nonpoly_identity(SINGLE_HEM.read_bytes())
    object.__setattr__(stale, "identity_projection_sha256", "0" * 64)
    with pytest.raises(MmcifNonpolyIdentityError) as stale_error:
        write_mmcif_nonpoly_identity(stale)
    assert stale_error.value.code == "stale_identity_projection"

    canonical = round_trip_mmcif_nonpoly_identity_source(SINGLE_HEM.read_bytes())
    reordered = round_trip_mmcif_nonpoly_identity_source(
        CATEGORY_ORDER_VARIANT.read_bytes()
    )
    assert canonical.write_result.payload == reordered.write_result.payload
    assert canonical.write_result.receipt.receipt_sha256 != (
        reordered.write_result.receipt.receipt_sha256
    )

    object.__setattr__(canonical, "write_result", reordered.write_result)
    with pytest.raises(ValueError, match="cross-consistent"):
        canonical.__post_init__()


def test_artifacts_are_factory_only_frozen_and_receipt_report_tamper_evident() -> None:
    result = round_trip_mmcif_nonpoly_identity_source(QUOTED_NAME.read_bytes())
    entity_row = result.source_ingest.entity_rows[0]
    scheme_row = result.source_ingest.scheme_rows[0]

    for artifact in (
        entity_row,
        scheme_row,
        result.source_ingest,
        result.write_result.receipt,
        result.write_result,
        result.report,
        result,
    ):
        assert "Heme cofactor alpha" not in repr(artifact)
        assert "A-7" not in repr(artifact)
        assert "PHEM" not in repr(artifact)

    with pytest.raises(TypeError, match="factory-only"):
        type(entity_row)(entity_id="9", comp_id="HEM", name="opaque")
    with pytest.raises(TypeError, match="factory-only"):
        type(scheme_row)(
            asym_id="Z",
            entity_id="9",
            mon_id="HEM",
            ndb_seq_num="1",
            pdb_seq_num="7",
            auth_seq_num="A-7",
            pdb_mon_id="PHEM",
            auth_mon_id="AHEM",
            pdb_strand_id="AUTHZ",
            pdb_ins_code="?",
        )
    with pytest.raises(TypeError):
        type(result.source_ingest)()
    with pytest.raises(TypeError, match="factory-only"):
        type(result.write_result.receipt)()
    with pytest.raises(TypeError, match="factory-only"):
        type(result.write_result)(payload=b"", receipt=None)
    with pytest.raises(TypeError, match="factory-only"):
        type(result.report)()
    with pytest.raises(TypeError):
        type(result)()

    with pytest.raises(FrozenInstanceError):
        entity_row.name = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.write_result.receipt.output_byte_count = 0  # type: ignore[misc]

    object.__setattr__(result.write_result.receipt, "receipt_sha256", "0" * 64)
    with pytest.raises(ValueError):
        result.write_result.receipt.__post_init__()

    fresh = round_trip_mmcif_nonpoly_identity_source(QUOTED_NAME.read_bytes())
    object.__setattr__(fresh.report, "report_sha256", "0" * 64)
    with pytest.raises(ValueError):
        fresh.report.__post_init__()


@pytest.mark.parametrize(
    "field_name",
    (
        "reparsed_identity_projection_sha256",
        "reparsed_record_state_sha256",
        "reemitted_source_sha256",
    ),
)
def test_standalone_report_recomputes_declared_equality_invariants(
    field_name: str,
) -> None:
    report = round_trip_mmcif_nonpoly_identity_source(SINGLE_HEM.read_bytes()).report
    object.__setattr__(report, field_name, "0" * 64)
    object.__setattr__(
        report, "report_sha256", _sha256_document(_report_payload(report))
    )

    with pytest.raises(ValueError, match="invariant is inconsistent"):
        report.__post_init__()


def test_ingest_data_block_name_is_typed_and_bound_to_normalized_source() -> None:
    ingest = parse_mmcif_nonpoly_identity(SINGLE_HEM.read_bytes())
    object.__setattr__(ingest, "data_block_name", 123)
    with pytest.raises(TypeError, match="data_block_name"):
        ingest.__post_init__()

    ingest = parse_mmcif_nonpoly_identity(SINGLE_HEM.read_bytes())
    object.__setattr__(ingest, "data_block_name", "different_block")
    with pytest.raises(ValueError, match="data-block binding"):
        ingest.__post_init__()


def test_ingest_non_ascii_data_block_tamper_has_no_raw_exception_context() -> None:
    ingest = parse_mmcif_nonpoly_identity(SINGLE_HEM.read_bytes())
    object.__setattr__(ingest, "data_block_name", "PRIVATE-\udcff-NAME")

    with pytest.raises(ValueError, match="must be ASCII") as exc_info:
        ingest.__post_init__()

    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None
    assert "PRIVATE" not in str(exc_info.value)
    assert "PRIVATE" not in repr(exc_info.value)


def test_aggregate_revalidates_reparsed_data_block_binding() -> None:
    result = round_trip_mmcif_nonpoly_identity_source(SINGLE_HEM.read_bytes())
    object.__setattr__(result.reparsed_ingest, "data_block_name", "different_block")

    with pytest.raises(ValueError, match="data-block binding"):
        result.__post_init__()


def test_missing_duplicate_or_polymer_entity_rows_fail_closed() -> None:
    source = SINGLE_HEM.read_bytes()
    missing = _replace_once(
        MIXED.read_bytes(),
        b"2 'Opaque compound identity' LIG\n",
        b"",
    )
    duplicate = _replace_once(
        source,
        b"1 HEM\n#\nloop_\n_pdbx_nonpoly_scheme.asym_id",
        b"1 HEM\n1 HEM\n#\nloop_\n_pdbx_nonpoly_scheme.asym_id",
    )
    polymer = _replace_once(source, b"1 non-polymer\n", b"1 polymer\n")

    _assert_error(missing, "nonpoly_entity_selection_mismatch")
    _assert_error(duplicate, "duplicate_nonpoly_entity_id")
    _assert_error(polymer, "nonpoly_entity_selection_mismatch")


def test_unknown_asym_and_scheme_entity_join_mismatch_fail_closed() -> None:
    source = SINGLE_HEM.read_bytes()
    unknown_asym = _replace_once(
        source,
        b"L 1 HEM 1 501 501 HEM HEM X .\n",
        b"Z 1 HEM 1 501 501 HEM HEM X .\n",
    )
    mixed = MIXED.read_bytes()
    entity_mismatch = _replace_once(
        mixed,
        b"L 2 LIG 1 10 AUTH-L LIG AUTHL LX .\n",
        b"L 3 LIG 1 10 AUTH-L LIG AUTHL LX .\n",
    )

    _assert_error(unknown_asym, "nonpoly_scheme_join_mismatch")
    _assert_error(entity_mismatch, "nonpoly_scheme_join_mismatch")


@pytest.mark.parametrize(
    ("old", "new", "code"),
    [
        (
            b"1 HEM\n#\nloop_\n_pdbx_nonpoly_scheme.asym_id",
            b"1 LIG\n#\nloop_\n_pdbx_nonpoly_scheme.asym_id",
            "nonpoly_component_join_mismatch",
        ),
        (
            b"L 1 HEM 1 501 501 HEM HEM X .\n",
            b"L 1 LIG 1 501 501 HEM HEM X .\n",
            "nonpoly_component_join_mismatch",
        ),
        (
            b"HETATM 1 Fe FE . HEM L 1 . ?",
            b"HETATM 1 Fe FE . LIG L 1 . ?",
            "nonpoly_component_join_mismatch",
        ),
    ],
)
def test_entity_scheme_and_atom_component_mismatches_fail_closed(
    old: bytes,
    new: bytes,
    code: str,
) -> None:
    _assert_error(_replace_once(SINGLE_HEM.read_bytes(), old, new), code)


def test_duplicate_instance_key_and_missing_instance_row_fail_closed() -> None:
    source = MULTI_INSTANCE.read_bytes()
    duplicate = _replace_once(
        source,
        b"L 1 HEM 1 9001 AUTH-A PHEM-A AHEM-A PDB-A .\n",
        b"L 1 HEM 2 9001 AUTH-A PHEM-A AHEM-A PDB-A .\n",
    )
    missing = _replace_once(
        source,
        b"L 1 HEM 2 9002 AUTH-B PHEM-B AHEM-B PDB-B ?\n",
        b"",
    )

    _assert_error(duplicate, "duplicate_nonpoly_scheme_key")
    _assert_error(missing, "nonpoly_residue_count_mismatch")


@pytest.mark.parametrize(
    ("category", "replacement", "code"),
    [
        (
            b"_pdbx_entity_nonpoly",
            b"loop_\n_pdbx_entity_nonpoly.comp_id\n_pdbx_entity_nonpoly.entity_id\nHEM 1\n#\n",
            "unsupported_category_headers",
        ),
        (
            b"_pdbx_entity_nonpoly",
            b"loop_\n_pdbx_entity_nonpoly.entity_id\n1\n#\n",
            "unsupported_category_headers",
        ),
        (
            b"_pdbx_entity_nonpoly",
            b"loop_\n_pdbx_entity_nonpoly.entity_id\n_pdbx_entity_nonpoly.comp_id\n_pdbx_entity_nonpoly.details\n1 HEM opaque\n#\n",
            "unsupported_category_headers",
        ),
        (
            b"_pdbx_nonpoly_scheme",
            b"loop_\n_pdbx_nonpoly_scheme.entity_id\n_pdbx_nonpoly_scheme.asym_id\n1 L\n#\n",
            "unsupported_category_headers",
        ),
        (
            b"_pdbx_nonpoly_scheme",
            b"loop_\n_pdbx_nonpoly_scheme.asym_id\n_pdbx_nonpoly_scheme.entity_id\nL 1\n#\n",
            "unsupported_category_headers",
        ),
        (
            b"_pdbx_nonpoly_scheme",
            b"loop_\n_pdbx_nonpoly_scheme.asym_id\n_pdbx_nonpoly_scheme.entity_id\n_pdbx_nonpoly_scheme.mon_id\n_pdbx_nonpoly_scheme.ndb_seq_num\n_pdbx_nonpoly_scheme.pdb_seq_num\n_pdbx_nonpoly_scheme.auth_seq_num\n_pdbx_nonpoly_scheme.pdb_mon_id\n_pdbx_nonpoly_scheme.auth_mon_id\n_pdbx_nonpoly_scheme.pdb_strand_id\n_pdbx_nonpoly_scheme.pdb_ins_code\n_pdbx_nonpoly_scheme.details\nL 1 HEM 1 501 501 HEM HEM X . opaque\n#\n",
            "unsupported_category_headers",
        ),
    ],
)
def test_partial_reversed_and_extra_headers_fail_closed(
    category: bytes,
    replacement: bytes,
    code: str,
) -> None:
    source = _replace_loop(SINGLE_HEM.read_bytes(), category, replacement)
    _assert_error(source, code)


def test_scalar_mixed_and_multiple_selected_category_forms_fail_closed() -> None:
    source = SINGLE_HEM.read_bytes()
    scalar = _replace_loop(
        source,
        b"_pdbx_entity_nonpoly",
        b"_pdbx_entity_nonpoly.entity_id 1\n_pdbx_entity_nonpoly.comp_id HEM\n#\n",
    )
    entity_start, entity_end = _loop_span(source, b"_pdbx_entity_nonpoly")
    entity_loop = source[entity_start:entity_end]
    mixed = (
        source[:entity_start]
        + b"_pdbx_entity_nonpoly.name opaque\n#\n"
        + source[entity_start:]
    )
    multiple = source[:entity_end] + entity_loop + source[entity_end:]
    mixed_category_loop = _replace_loop(
        source,
        b"_pdbx_entity_nonpoly",
        b"loop_\n_pdbx_entity_nonpoly.entity_id\n_pdbx_entity_nonpoly.comp_id\n_entity.id\n1 HEM 1\n#\n",
    )

    _assert_error(scalar, "unsupported_category_representation")
    _assert_error(mixed, "unsupported_category_representation")
    _assert_error(multiple, "unsupported_category_representation")
    _assert_error(mixed_category_loop, "unsupported_category_representation")


@pytest.mark.parametrize(
    ("section", "code"),
    [
        (b"_struct_conn.id conn-private\n#\n", "unsupported_category_surface"),
        (b"_chem_comp_atom.comp_id HEM\n#\n", "unsupported_category_surface"),
        (b"_chem_comp_bond.comp_id HEM\n#\n", "unsupported_category_surface"),
        (b"_pdbx_ion_info.id ion-private\n#\n", "unsupported_category_surface"),
    ],
)
def test_unreviewed_topology_and_context_categories_remain_rejected(
    section: bytes,
    code: str,
) -> None:
    _assert_error(_inject_before_atom_site(SINGLE_HEM.read_bytes(), section), code)


def test_non_ascii_failure_has_no_raw_exception_or_secret_echo() -> None:
    source = _replace_once(
        QUOTED_NAME.read_bytes(),
        b"Heme cofactor alpha",
        b"PRIVATE-MARKER-\xff",
    )
    error = _assert_error(source, "non_ascii_input")

    assert error.__cause__ is None
    assert error.__context__ is None
    assert "PRIVATE-MARKER" not in str(error)
    assert "PRIVATE-MARKER" not in repr(error)


def test_sensitive_aliases_are_not_echoed_by_join_errors() -> None:
    source = _replace_once(
        SINGLE_HEM.read_bytes(),
        b"L 1 HEM 1 501 501 HEM HEM X .\n",
        b"UNKNOWN-PRIVATE 1 HEM 1 501 501 HEM HEM X .\n",
    )
    error = _assert_error(source, "nonpoly_scheme_join_mismatch")

    assert "UNKNOWN-PRIVATE" not in str(error)
    assert "UNKNOWN-PRIVATE" not in repr(error)


def test_source_bytes_and_hashes_remain_cross_bound() -> None:
    ingest = parse_mmcif_nonpoly_identity(SINGLE_HEM.read_bytes())
    object.__setattr__(ingest, "full_source_sha256", "1" * 64)
    with pytest.raises(MmcifNonpolyIdentityError) as exc_info:
        write_mmcif_nonpoly_identity(ingest)
    assert exc_info.value.code == "stale_source_binding"

    fresh = parse_mmcif_nonpoly_identity(SINGLE_HEM.read_bytes())
    object.__setattr__(fresh, "_normalized_base_source_bytes", b"forged")
    with pytest.raises(MmcifNonpolyIdentityError) as exc_info:
        write_mmcif_nonpoly_identity(fresh)
    assert exc_info.value.code == "stale_source_binding"


def test_system_property_is_detached_from_the_bound_snapshot() -> None:
    ingest = parse_mmcif_nonpoly_identity(SINGLE_HEM.read_bytes())
    first = ingest.system
    original = float(first.coordinates[0, 0, 0])
    first.coordinates[0, 0, 0] = original + 99.0

    assert float(ingest.system.coordinates[0, 0, 0]) == original
    write_mmcif_nonpoly_identity(ingest)


def test_dot_and_question_insertion_markers_do_not_create_two_residues() -> None:
    source = SINGLE_HEM.read_bytes()
    source = _replace_once(
        source,
        b"L 1 HEM 1 501 501 HEM HEM X .\n",
        (b"L 1 HEM 1 501 501 HEM HEM X .\nL 1 HEM 2 502 502 HEM HEM X ?\n"),
    )
    source = _replace_once(
        source,
        b"HETATM 2 N NA . HEM L 1 . ?",
        b"HETATM 2 N NA . HEM L 1 . .",
    )

    _assert_error(source, "nonpoly_residue_count_mismatch")


def test_base_parser_failure_has_no_raw_exception_context() -> None:
    source = _replace_once(
        SINGLE_HEM.read_bytes(),
        b"0.000 0.000 0.000",
        b"PRIVATE-COORD 0.000 0.000",
    )
    error = _assert_error(source, "base_parser_rejected")

    assert error.__cause__ is None
    assert error.__context__ is None
    assert "PRIVATE-COORD" not in str(error)
    assert "PRIVATE-COORD" not in repr(error)


def test_long_scheme_alias_row_is_wrapped_into_valid_cif() -> None:
    aliases = [f"A{index}-" + "x" * 390 for index in range(6)]
    replacement = ("L\n1\nHEM\n1\n" + "\n".join(aliases) + "\n").encode("ascii")
    source = _replace_once(
        SINGLE_HEM.read_bytes(),
        b"L 1 HEM 1 501 501 HEM HEM X .\n",
        replacement,
    )
    result = round_trip_mmcif_nonpoly_identity_source(source)

    assert max(map(len, result.write_result.payload.splitlines())) <= 2_048
    assert result.report.second_emission_byte_stable is True


def test_reemitted_receipt_crosswire_is_rejected_even_for_same_bytes() -> None:
    left = round_trip_mmcif_nonpoly_identity_source(
        SINGLE_HEM.read_bytes(), source_id="left"
    )
    right = round_trip_mmcif_nonpoly_identity_source(
        SINGLE_HEM.read_bytes(), source_id="right"
    )
    assert left.reemitted_write_result.payload == right.reemitted_write_result.payload

    object.__setattr__(left, "reemitted_write_result", right.reemitted_write_result)
    with pytest.raises(ValueError, match="cross-consistent"):
        left.__post_init__()


def test_aggregate_revalidates_every_nested_artifact() -> None:
    result = round_trip_mmcif_nonpoly_identity_source(SINGLE_HEM.read_bytes())
    object.__setattr__(result.write_result, "payload", b"CORRUPTED")
    with pytest.raises(ValueError):
        result.__post_init__()

    result = round_trip_mmcif_nonpoly_identity_source(SINGLE_HEM.read_bytes())
    object.__setattr__(result.reemitted_write_result, "payload", b"CORRUPTED")
    with pytest.raises(ValueError):
        result.__post_init__()

    result = round_trip_mmcif_nonpoly_identity_source(SINGLE_HEM.read_bytes())
    object.__setattr__(result.report, "second_emission_byte_stable", False)
    with pytest.raises(ValueError):
        result.__post_init__()

    result = round_trip_mmcif_nonpoly_identity_source(SINGLE_HEM.read_bytes())
    object.__setattr__(result.source_ingest, "_full_source_bytes", b"CORRUPTED")
    with pytest.raises(ValueError):
        result.__post_init__()

    result = round_trip_mmcif_nonpoly_identity_source(SINGLE_HEM.read_bytes())
    object.__setattr__(result.write_result.receipt, "output_byte_count", 0)
    with pytest.raises(ValueError):
        result.__post_init__()


def test_name_with_both_quote_characters_is_rejected_during_parse() -> None:
    source = _replace_once(
        QUOTED_NAME.read_bytes(),
        b"'Heme cofactor alpha'",
        b"'both\"and'quotes'",
    )
    _assert_error(source, "invalid_nonpoly_name")


def test_public_entity_row_cap_is_enforced_before_semantic_duplicates() -> None:
    source = SINGLE_HEM.read_bytes()
    marker = b"1 HEM\n#\nloop_\n_pdbx_nonpoly_scheme.asym_id"

    at_limit = _replace_once(
        source,
        marker,
        b"1 HEM\n" * MAX_MMCIF_NONPOLY_ENTITY_ROWS
        + b"#\nloop_\n_pdbx_nonpoly_scheme.asym_id",
    )
    over_limit = _replace_once(
        source,
        marker,
        b"1 HEM\n" * (MAX_MMCIF_NONPOLY_ENTITY_ROWS + 1)
        + b"#\nloop_\n_pdbx_nonpoly_scheme.asym_id",
    )

    _assert_error(at_limit, "duplicate_nonpoly_entity_id")
    _assert_error(over_limit, "too_many_nonpoly_entity_rows")


def test_public_input_byte_cap_fails_before_decode_or_syntax() -> None:
    _assert_error(
        b"\xff" * (MAX_MMCIF_NONPOLY_IDENTITY_INPUT_BYTES + 1),
        "input_too_large",
    )
