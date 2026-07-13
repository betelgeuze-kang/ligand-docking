from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

import betelgeuze_engine_v2.molecular.mmcif_unobserved_atoms as atom_module
from betelgeuze_engine_v2.molecular.mmcif_unobserved_atoms import (
    MAX_MMCIF_UNOBSERVED_ATOM_ROWS,
    MAX_MMCIF_UNOBSERVED_ATOM_TOKEN_CHARS,
    MMCIF_UNOBSERVED_ATOM_ENVELOPE_VERSION,
    MMCIF_UNOBSERVED_ATOM_HEADERS,
    MMCIF_UNOBSERVED_ATOM_PROJECTION_SCOPE,
    MmcifUnobservedAtomError,
    MmcifUnobservedAtomIngestResult,
    MmcifUnobservedAtomRoundTripReport,
    MmcifUnobservedAtomRow,
    MmcifUnobservedAtomWriteReceipt,
    emit_mmcif_unobserved_atoms,
    parse_mmcif_unobserved_atoms,
    round_trip_mmcif_unobserved_atoms_source,
    serialize_mmcif_unobserved_atoms,
)


FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "v2_1_mmcif_unobserved_atoms"
)
SINGLE = FIXTURES / "single_atom_claim.cif"
MULTIPLE = FIXTURES / "multiple_ordered_claims.cif"
INSERTION = FIXTURES / "insertion_and_alt_markers.cif"
SHARED = FIXTURES / "shared_entity_multiple_asym.cif"
COMPOSED = FIXTURES / "composed_nonpoly_carrier.cif"
CATEGORY_ORDER = FIXTURES / "category_order_variant.cif"

_SINGLE_ROW = b"1 Y 1 1 AX ALA AUTH-1 ? CB ? A ALA 1 CB"
_SINGLE_COORDINATE = b"ATOM 1 N N . ALA A 1 1 ? 0 0 0 1.0 20.0 ? AUTH-1 ALA AX N 1"
_FALSE_GATES = (
    "source_authenticated",
    "auth_label_equivalence_inferred",
    "reference_sequence_equivalence_assessed",
    "coordinate_observation_completeness_assessed",
    "missing_atom_fact_claimed",
    "sequence_completeness_claimed",
    "modeled_atom_presence_assessed",
    "residue_template_consulted",
    "atom_name_dictionary_validated",
    "completion_attempted",
    "completion_applied",
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


def _assert_error(source: bytes, code: str) -> MmcifUnobservedAtomError:
    with pytest.raises(MmcifUnobservedAtomError) as exc_info:
        parse_mmcif_unobserved_atoms(source)
    assert exc_info.value.code == code
    return exc_info.value


def _assert_false_claims(document: dict[str, object]) -> None:
    assert document["source_reported_unobserved_atom_claims_preserved"] is True
    for field_name in _FALSE_GATES:
        assert document[field_name] is False


def _rows_payload(row_count: int) -> bytes:
    source = SINGLE.read_bytes()
    rows = b"\n".join(
        (f"{index} Y 1 1 AX ALA AUTH-1 ? M{index} ? A ALA 1 M{index}").encode("ascii")
        for index in range(1, row_count + 1)
    )
    return _replace_once(source, _SINGLE_ROW, rows)


def _long_token_source() -> bytes:
    x = "X" * MAX_MMCIF_UNOBSERVED_ATOM_TOKEN_CHARS
    asym = "A" * MAX_MMCIF_UNOBSERVED_ATOM_TOKEN_CHARS
    comp = "C" * MAX_MMCIF_UNOBSERVED_ATOM_TOKEN_CHARS
    insertion = "I" * MAX_MMCIF_UNOBSERVED_ATOM_TOKEN_CHARS
    missing_atom = "M" * MAX_MMCIF_UNOBSERVED_ATOM_TOKEN_CHARS
    atom_headers = (
        "_atom_site.group_pdb",
        "_atom_site.id",
        "_atom_site.type_symbol",
        "_atom_site.label_atom_id",
        "_atom_site.label_alt_id",
        "_atom_site.label_comp_id",
        "_atom_site.label_asym_id",
        "_atom_site.label_entity_id",
        "_atom_site.label_seq_id",
        "_atom_site.pdbx_pdb_ins_code",
        "_atom_site.cartn_x",
        "_atom_site.cartn_y",
        "_atom_site.cartn_z",
        "_atom_site.occupancy",
        "_atom_site.b_iso_or_equiv",
        "_atom_site.pdbx_formal_charge",
        "_atom_site.auth_seq_id",
        "_atom_site.auth_comp_id",
        "_atom_site.auth_asym_id",
        "_atom_site.auth_atom_id",
        "_atom_site.pdbx_pdb_model_num",
    )
    lines = [
        "data_long_tokens",
        "#",
        "loop_",
        "_entity.id",
        "_entity.type",
        "E polymer",
        "#",
        "loop_",
        "_struct_asym.id",
        "_struct_asym.entity_id",
        f"{asym} E",
        "#",
        "loop_",
        "_entity_poly_seq.entity_id",
        "_entity_poly_seq.num",
        "_entity_poly_seq.mon_id",
        "_entity_poly_seq.hetero",
        f"E 1 {comp} n",
        "#",
        "loop_",
        *MMCIF_UNOBSERVED_ATOM_HEADERS,
        *map(
            str,
            (
                1,
                "Y",
                1,
                1,
                x,
                x,
                x,
                insertion,
                x,
                "?",
                asym,
                comp,
                1,
                missing_atom,
            ),
        ),
        "#",
        "loop_",
        *atom_headers,
        *map(
            str,
            (
                "ATOM",
                1,
                "N",
                "N",
                ".",
                comp,
                asym,
                "E",
                1,
                insertion,
                0,
                0,
                0,
                1,
                20,
                "?",
                x,
                x,
                x,
                "N",
                1,
            ),
        ),
        "#",
        "",
    ]
    return "\n".join(lines).encode("ascii")


def test_single_atom_claim_round_trip_and_base_claim_binding() -> None:
    source = SINGLE.read_bytes()
    ingest = parse_mmcif_unobserved_atoms(source, source_id="single-atom")
    result = round_trip_mmcif_unobserved_atoms_source(source, source_id="single-atom")
    row = ingest.unobserved_atom_rows[0]
    report = ingest.missingness_report

    assert MMCIF_UNOBSERVED_ATOM_ENVELOPE_VERSION == "1.0.0"
    assert MMCIF_UNOBSERVED_ATOM_PROJECTION_SCOPE == (
        "source_reported_unobserved_polymer_atom_claims_only"
    )
    assert len(MMCIF_UNOBSERVED_ATOM_HEADERS) == 14
    assert MAX_MMCIF_UNOBSERVED_ATOM_ROWS == 2_857
    assert (
        row.auth_atom_id,
        row.label_alt_id,
        row.label_asym_id,
        row.label_comp_id,
        row.label_seq_id,
        row.label_atom_id,
    ) == ("CB", "?", "A", "ALA", 1, "CB")
    assert report.source_reported_missing_residue_count == 0
    assert report.source_reported_missing_atom_count == 1
    claim = report.missing_atom_claims[0]
    assert claim.source_ordinal == 1
    assert claim.source_category == "_pdbx_unobs_or_zero_occ_atoms"
    assert claim.source_insertion_code == ""
    assert claim.source_altloc_id == ""
    assert claim.source_atom_name == "CB"
    assert claim.raw_payload["source_row_id"] == 1
    assert claim.raw_payload["tokens"][
        "_pdbx_unobs_or_zero_occ_atoms.label_alt_id"
    ] == {"value": "?", "quoted": False, "multiline": False}

    assert serialize_mmcif_unobserved_atoms(ingest) == result.write_result.payload
    assert result.source_ingest.unobserved_atom_rows == (
        result.reparsed_ingest.unobserved_atom_rows
    )
    assert result.report.unobserved_atom_projection_sha256_equal is True
    assert result.report.record_state_sha256_equal is True
    assert result.report.second_emission_byte_stable is True
    assert result.write_result.payload == result.reemitted_write_result.payload
    assert _SINGLE_ROW + b"\n" in result.write_result.payload
    for artifact in (
        ingest.to_dict(),
        result.write_result.receipt.to_dict(),
        result.report.to_dict(),
        result.to_dict(),
    ):
        _assert_false_claims(artifact)


def test_order_instance_composition_and_source_binding_behaviors() -> None:
    multiple = round_trip_mmcif_unobserved_atoms_source(MULTIPLE.read_bytes())
    assert [row.source_id for row in multiple.source_ingest.unobserved_atom_rows] == [
        2,
        7,
    ]
    assert multiple.write_result.payload.index(b"2 Y 1 1") < (
        multiple.write_result.payload.index(b"7 Y 1 1")
    )

    shared = round_trip_mmcif_unobserved_atoms_source(SHARED.read_bytes())
    assert [
        (row.label_asym_id, row.label_atom_id)
        for row in shared.source_ingest.unobserved_atom_rows
    ] == [("A", "CB"), ("B", "CB")]

    composed = round_trip_mmcif_unobserved_atoms_source(COMPOSED.read_bytes())
    assert composed.source_ingest.has_nonpoly_identity is True
    assert (
        composed.source_ingest.carrier_kind == "mmcif_polymer_sequence_nonpoly_identity"
    )
    assert composed.report.nonpoly_identity_projection_sha256_equal is True

    canonical = round_trip_mmcif_unobserved_atoms_source(SINGLE.read_bytes())
    reordered = round_trip_mmcif_unobserved_atoms_source(CATEGORY_ORDER.read_bytes())
    assert canonical.write_result.payload == reordered.write_result.payload
    assert canonical.source_ingest.record_state_sha256 == (
        reordered.source_ingest.record_state_sha256
    )
    assert canonical.source_ingest.source_binding_sha256 != (
        reordered.source_ingest.source_binding_sha256
    )


def test_insertion_and_marker_state_is_raw_distinct_but_semantically_normalized() -> (
    None
):
    insertion = round_trip_mmcif_unobserved_atoms_source(INSERTION.read_bytes())
    row = insertion.source_ingest.unobserved_atom_rows[0]
    assert row.source_id == (1 << 53) - 1
    assert (row.pdb_ins_code, row.label_alt_id) == ("B", ".")
    assert (
        insertion.source_ingest.missingness_report.missing_atom_claims[
            0
        ].source_insertion_code
        == "B"
    )

    question = parse_mmcif_unobserved_atoms(SINGLE.read_bytes())
    dot_source = _replace_once(
        SINGLE.read_bytes(),
        _SINGLE_ROW,
        b"1 Y 1 1 AX ALA AUTH-1 . CB . A ALA 1 CB",
    )
    dot = parse_mmcif_unobserved_atoms(dot_source)
    assert question.unobserved_atom_projection_sha256 != (
        dot.unobserved_atom_projection_sha256
    )
    assert dot.unobserved_atom_rows[0].pdb_ins_code == "."
    assert dot.unobserved_atom_rows[0].label_alt_id == "."


def test_semantic_duplicate_normalizes_dot_and_question_mark() -> None:
    rows = b"\n".join(
        (
            _SINGLE_ROW,
            b"2 Y 1 1 AX ALA AUTH-1 . CB . A ALA 1 CB",
        )
    )
    _assert_error(
        _replace_once(SINGLE.read_bytes(), _SINGLE_ROW, rows),
        "duplicate_unobserved_atom_identity",
    )


def test_insertion_aware_parent_presence_and_exact_atom_absence() -> None:
    mismatched_insertion = _replace_once(
        SINGLE.read_bytes(),
        _SINGLE_ROW,
        b"1 Y 1 1 AX ALA AUTH-1 B CB ? A ALA 1 CB",
    )
    _assert_error(mismatched_insertion, "unobserved_atom_residue_absent")

    present_atom = _replace_once(
        SINGLE.read_bytes(),
        _SINGLE_COORDINATE,
        b"ATOM 1 C CB . ALA A 1 1 ? 0 0 0 1.0 20.0 ? AUTH-1 ALA AX CB 1",
    )
    _assert_error(present_atom, "unobserved_atom_present_in_coordinates")


@pytest.mark.parametrize(
    ("replacement", "code"),
    (
        (
            b"1 N 1 1 AX ALA AUTH-1 ? CB ? A ALA 1 CB",
            "unsupported_unobserved_atom_polymer_flag",
        ),
        (
            b"1 Y 0 1 AX ALA AUTH-1 ? CB ? A ALA 1 CB",
            "unsupported_unobserved_atom_occupancy_flag",
        ),
        (
            b"1 Y 1 2 AX ALA AUTH-1 ? CB ? A ALA 1 CB",
            "unsupported_unobserved_atom_model",
        ),
        (
            b"1 Y 1 1 AX ALA AUTH-1 ? CB A A ALA 1 CB",
            "unsupported_unobserved_atom_altloc",
        ),
        (
            b"1 Y 1 1 AX ALA AUTH-1 ? CB ? Z ALA 1 CB",
            "unknown_unobserved_atom_asym_id",
        ),
        (
            b"1 Y 1 1 AX ALA AUTH-1 ? CB ? A SER 1 CB",
            "unobserved_atom_sequence_join_mismatch",
        ),
        (
            b"9007199254740992 Y 1 1 AX ALA AUTH-1 ? CB ? A ALA 1 CB",
            "duplicate_or_invalid_unobserved_atom_id",
        ),
    ),
)
def test_control_identity_and_row_id_failures_are_typed(
    replacement: bytes, code: str
) -> None:
    _assert_error(_replace_once(SINGLE.read_bytes(), _SINGLE_ROW, replacement), code)


def test_mixed_residue_missingness_and_header_extension_fail_closed() -> None:
    residue_loop = b"""loop_
_pdbx_unobs_or_zero_occ_residues.id
_pdbx_unobs_or_zero_occ_residues.polymer_flag
_pdbx_unobs_or_zero_occ_residues.occupancy_flag
_pdbx_unobs_or_zero_occ_residues.pdb_model_num
_pdbx_unobs_or_zero_occ_residues.auth_asym_id
_pdbx_unobs_or_zero_occ_residues.auth_comp_id
_pdbx_unobs_or_zero_occ_residues.auth_seq_id
_pdbx_unobs_or_zero_occ_residues.pdb_ins_code
_pdbx_unobs_or_zero_occ_residues.label_asym_id
_pdbx_unobs_or_zero_occ_residues.label_comp_id
_pdbx_unobs_or_zero_occ_residues.label_seq_id
9 Y 1 1 AX ALA AUTH-1 ? A ALA 1
#
"""
    mixed = _replace_once(
        SINGLE.read_bytes(),
        b"loop_\n_atom_site.group_pdb",
        residue_loop + b"loop_\n_atom_site.group_pdb",
    )
    _assert_error(mixed, "mixed_residue_missingness_unsupported")

    extended = _replace_once(
        SINGLE.read_bytes(),
        b"_pdbx_unobs_or_zero_occ_atoms.label_atom_id\n",
        b"_pdbx_unobs_or_zero_occ_atoms.label_atom_id\n"
        b"_pdbx_unobs_or_zero_occ_atoms.details\n",
    )
    extended = _replace_once(extended, _SINGLE_ROW, _SINGLE_ROW + b" OPAQUE")
    _assert_error(extended, "unsupported_category_headers")


def test_additional_selected_surface_failures_are_typed() -> None:
    source = SINGLE.read_bytes()
    loop_block = (
        b"loop_\n"
        + b"\n".join(header.encode("ascii") for header in MMCIF_UNOBSERVED_ATOM_HEADERS)
        + b"\n"
        + _SINGLE_ROW
        + b"\n#\n"
    )
    scalar_values = _SINGLE_ROW.split()
    scalar_block = (
        b"\n".join(
            header.encode("ascii") + b" " + value
            for header, value in zip(
                MMCIF_UNOBSERVED_ATOM_HEADERS, scalar_values, strict=True
            )
        )
        + b"\n#\n"
    )
    cases = (
        (
            _replace_once(source, b"1 polymer\n", b"1 non-polymer\n"),
            "unobserved_atom_nonpolymer_entity",
        ),
        (
            _replace_once(
                source, _SINGLE_ROW, b"1 Y 1 1 AX ALA AUTH-1 ? CB ? A ALA 0 CB"
            ),
            "invalid_label_seq_id",
        ),
        (
            _replace_once(
                source,
                _SINGLE_ROW,
                _SINGLE_ROW + b"\n1 Y 1 1 AX ALA AUTH-1 ? OG ? A ALA 1 OG",
            ),
            "duplicate_or_invalid_unobserved_atom_id",
        ),
        (
            _replace_once(
                source,
                _SINGLE_ROW,
                b"1 Y 1 1 'AX' ALA AUTH-1 ? CB ? A ALA 1 CB",
            ),
            "invalid_unobserved_atom_token",
        ),
        (
            _replace_once(source, _SINGLE_ROW + b"\n", b""),
            "invalid_cif_syntax",
        ),
        (
            _replace_once(
                source,
                b"loop_\n_atom_site.group_pdb",
                b"loop_\n_chem_comp.id\nALA\n#\nloop_\n_atom_site.group_pdb",
            ),
            "unsupported_category_surface",
        ),
        (
            _replace_once(source, loop_block, scalar_block),
            "unsupported_category_representation",
        ),
    )
    for mutated, code in cases:
        _assert_error(mutated, code)


def test_row_cap_boundary_and_overflow_are_owned_by_envelope() -> None:
    accepted = parse_mmcif_unobserved_atoms(
        _rows_payload(MAX_MMCIF_UNOBSERVED_ATOM_ROWS)
    )
    assert len(accepted.unobserved_atom_rows) == MAX_MMCIF_UNOBSERVED_ATOM_ROWS
    _assert_error(
        _rows_payload(MAX_MMCIF_UNOBSERVED_ATOM_ROWS + 1),
        "too_many_unobserved_atom_rows",
    )


def test_long_tokens_split_physical_lines_and_round_trip_stably() -> None:
    source = _long_token_source()
    assert max(map(len, source.splitlines())) <= 2_048
    result = round_trip_mmcif_unobserved_atoms_source(source)
    output_lines = result.write_result.payload.splitlines()
    assert max(map(len, output_lines)) <= 2_048
    assert b"X" * MAX_MMCIF_UNOBSERVED_ATOM_TOKEN_CHARS in output_lines
    assert result.write_result.payload == result.reemitted_write_result.payload


def test_base_claim_rows_are_not_accepted_by_counts_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parse = atom_module.parse_mmcif

    def forged_parse(*args, **kwargs):
        result = real_parse(*args, **kwargs)
        report = result.missingness_evidence
        if report.source_reported_missing_atom_count != 1:
            return result
        claim = replace(report.missing_atom_claims[0], source_atom_name="FORGED")
        forged_report = replace(report, missing_atom_claims=(claim,))
        return replace(result, missingness_evidence=forged_report)

    monkeypatch.setattr(atom_module, "parse_mmcif", forged_parse)
    _assert_error(SINGLE.read_bytes(), "missingness_report_mismatch")


def test_factory_only_artifacts_and_tamper_fail_closed() -> None:
    source = SINGLE.read_bytes()
    ingest = parse_mmcif_unobserved_atoms(source)
    write = emit_mmcif_unobserved_atoms(ingest)
    result = round_trip_mmcif_unobserved_atoms_source(source)

    with pytest.raises(TypeError):
        MmcifUnobservedAtomRow()
    with pytest.raises(TypeError):
        MmcifUnobservedAtomIngestResult(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        MmcifUnobservedAtomWriteReceipt(ingest, write.payload)
    with pytest.raises(TypeError):
        MmcifUnobservedAtomRoundTripReport()
    with pytest.raises(FrozenInstanceError):
        ingest.record_state_sha256 = "0" * 64  # type: ignore[misc]

    object.__setattr__(ingest, "record_state_sha256", "0" * 64)
    with pytest.raises(MmcifUnobservedAtomError) as ingest_exc:
        ingest.to_dict()
    assert ingest_exc.value.code == "stale_ingest_binding"

    object.__setattr__(write.receipt, "_payload", write.payload + b"#\n")
    with pytest.raises(MmcifUnobservedAtomError) as receipt_exc:
        write.receipt.to_dict()
    assert receipt_exc.value.code == "stale_write_receipt"

    other = round_trip_mmcif_unobserved_atoms_source(source, source_id="other")
    object.__setattr__(result, "report", other.report)
    with pytest.raises(MmcifUnobservedAtomError) as crosswire_exc:
        result.to_dict()
    assert crosswire_exc.value.code == "crosswired_round_trip_artifacts"


def test_row_carrier_and_snapshot_ingest_crosswires_fail_closed() -> None:
    source = SINGLE.read_bytes()
    other = round_trip_mmcif_unobserved_atoms_source(MULTIPLE.read_bytes())
    for field_name, replacement in (
        ("unobserved_atom_rows", other.source_ingest.unobserved_atom_rows),
        ("_carrier_source_bytes", other.source_ingest._carrier_source_bytes),
        ("_system_snapshot_payload", other.source_ingest._system_snapshot_payload),
    ):
        ingest = parse_mmcif_unobserved_atoms(source)
        object.__setattr__(ingest, field_name, replacement)
        with pytest.raises(MmcifUnobservedAtomError) as exc_info:
            ingest.to_dict()
        assert exc_info.value.code == "stale_ingest_binding"


def test_repr_does_not_include_source_identity() -> None:
    result = round_trip_mmcif_unobserved_atoms_source(
        SINGLE.read_bytes(), source_id="private-source-identity"
    )
    for artifact in (
        result.source_ingest,
        result.source_ingest.unobserved_atom_rows[0],
        result.write_result,
        result.write_result.receipt,
        result.report,
        result,
    ):
        assert "private-source-identity" not in repr(artifact)
        assert "AUTH-1" not in repr(artifact)


def test_input_types_non_ascii_tokens_and_resource_caps_are_strict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = SINGLE.read_bytes()
    for value in (bytearray(source), memoryview(source), source.decode("ascii")):
        with pytest.raises(TypeError):
            parse_mmcif_unobserved_atoms(value)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        parse_mmcif_unobserved_atoms(source, source_id=1)  # type: ignore[arg-type]
    _assert_error(b"", "empty_input")

    non_ascii = _replace_once(
        source,
        _SINGLE_ROW,
        b"1 Y 1 1 AX ALA PRIVATE-\xff ? CB ? A ALA 1 CB",
    )
    error = _assert_error(non_ascii, "non_ascii_input")
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "PRIVATE" not in str(error)
    assert "PRIVATE" not in repr(error)

    too_long = b"X" * (MAX_MMCIF_UNOBSERVED_ATOM_TOKEN_CHARS + 1)
    _assert_error(
        _replace_once(
            source,
            _SINGLE_ROW,
            b"1 Y 1 1 AX ALA " + too_long + b" ? CB ? A ALA 1 CB",
        ),
        "invalid_identity_token",
    )

    monkeypatch.setattr(atom_module, "MAX_MMCIF_UNOBSERVED_ATOM_ROWS", 0)
    _assert_error(source, "too_many_unobserved_atom_rows")
    monkeypatch.setattr(
        atom_module,
        "MAX_MMCIF_UNOBSERVED_ATOM_ROWS",
        MAX_MMCIF_UNOBSERVED_ATOM_ROWS,
    )
    monkeypatch.setattr(
        atom_module, "MAX_MMCIF_UNOBSERVED_ATOM_INPUT_BYTES", len(source) - 1
    )
    _assert_error(source, "input_too_large")


@pytest.mark.parametrize(
    ("source_id", "code"),
    (
        (
            "x" * (atom_module.MAX_MMCIF_UNOBSERVED_ATOM_SOURCE_ID_BYTES + 1),
            "source_id_too_large",
        ),
        ("\ud800", "invalid_source_id"),
    ),
)
def test_source_id_is_resource_bounded_and_unicode_scalar_safe(
    source_id: str, code: str
) -> None:
    with pytest.raises(MmcifUnobservedAtomError) as exc_info:
        parse_mmcif_unobserved_atoms(SINGLE.read_bytes(), source_id=source_id)
    assert exc_info.value.code == code


def test_public_system_is_detached_and_nested_type_tamper_is_typed() -> None:
    result = round_trip_mmcif_unobserved_atoms_source(SINGLE.read_bytes())
    system = result.source_ingest.system
    original = float(result.source_ingest.system.coordinates[0, 0, 0])
    system.coordinates[0, 0, 0] = original + 100.0
    assert float(result.source_ingest.system.coordinates[0, 0, 0]) == original

    object.__setattr__(result, "write_result", None)
    with pytest.raises(MmcifUnobservedAtomError) as aggregate_exc:
        result.to_dict()
    assert aggregate_exc.value.code == "crosswired_round_trip_artifacts"

    result = round_trip_mmcif_unobserved_atoms_source(SINGLE.read_bytes())
    object.__setattr__(result.write_result, "receipt", None)
    with pytest.raises(MmcifUnobservedAtomError) as write_exc:
        result.write_result.to_dict()
    assert write_exc.value.code == "stale_write_result"

    result = round_trip_mmcif_unobserved_atoms_source(SINGLE.read_bytes())
    object.__setattr__(result.report, "_source", None)
    with pytest.raises(MmcifUnobservedAtomError) as report_exc:
        result.report.to_dict()
    assert report_exc.value.code == "stale_round_trip_report"


def test_noncanonical_evidence_and_coherent_payload_rewrite_fail_closed() -> None:
    result = round_trip_mmcif_unobserved_atoms_source(SINGLE.read_bytes())
    receipt = result.write_result.receipt
    object.__setattr__(receipt, "_document_bytes", b" " + receipt._document_bytes)
    with pytest.raises(MmcifUnobservedAtomError) as receipt_exc:
        _ = receipt.receipt_sha256
    assert receipt_exc.value.code == "invalid_write_receipt"

    result = round_trip_mmcif_unobserved_atoms_source(SINGLE.read_bytes())
    object.__setattr__(
        result.report,
        "_document_bytes",
        b'{"round_trip_report_sha256":NaN}',
    )
    with pytest.raises(MmcifUnobservedAtomError) as report_exc:
        _ = result.report.round_trip_report_sha256
    assert report_exc.value.code == "invalid_round_trip_report"

    result = round_trip_mmcif_unobserved_atoms_source(SINGLE.read_bytes())
    write_result = result.write_result
    receipt = write_result.receipt
    evil_payload = b"data_evil\n#\n"
    evil_document = atom_module._receipt_document(receipt._ingest, evil_payload)
    object.__setattr__(receipt, "_payload", evil_payload)
    object.__setattr__(
        receipt,
        "_document_bytes",
        atom_module._canonical_json_bytes(evil_document),
    )
    object.__setattr__(write_result, "payload", evil_payload)
    with pytest.raises(MmcifUnobservedAtomError) as rewrite_exc:
        write_result.to_dict()
    assert rewrite_exc.value.code == "stale_write_receipt"


def test_same_payload_crosswires_remain_source_binding_sensitive() -> None:
    source = SINGLE.read_bytes()
    left = round_trip_mmcif_unobserved_atoms_source(source, source_id="left")
    right = round_trip_mmcif_unobserved_atoms_source(source, source_id="right")
    assert left.write_result.payload == right.write_result.payload
    object.__setattr__(left, "reparsed_ingest", right.reparsed_ingest)
    object.__setattr__(left, "reemitted_write_result", right.reemitted_write_result)
    with pytest.raises(MmcifUnobservedAtomError) as source_id_exc:
        left.to_dict()
    assert source_id_exc.value.code == "crosswired_round_trip_artifacts"

    canonical = round_trip_mmcif_unobserved_atoms_source(source)
    reordered = round_trip_mmcif_unobserved_atoms_source(CATEGORY_ORDER.read_bytes())
    assert canonical.write_result.payload == reordered.write_result.payload
    object.__setattr__(canonical, "write_result", reordered.write_result)
    with pytest.raises(MmcifUnobservedAtomError) as layout_exc:
        canonical.to_dict()
    assert layout_exc.value.code == "crosswired_round_trip_artifacts"
