from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

import betelgeuze_engine_v2.molecular.mmcif_zero_occupancy_atoms as atom_module
from betelgeuze_engine_v2.molecular.mmcif_zero_occupancy_atoms import (
    MAX_MMCIF_ZERO_OCCUPANCY_ATOM_ROWS,
    MAX_MMCIF_ZERO_OCCUPANCY_ATOM_TOKEN_CHARS,
    MMCIF_ZERO_OCCUPANCY_ATOM_ENVELOPE_VERSION,
    MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS,
    MMCIF_ZERO_OCCUPANCY_ATOM_PROJECTION_SCOPE,
    MmcifZeroOccupancyAtomError,
    MmcifZeroOccupancyAtomIngestResult,
    MmcifZeroOccupancyAtomRoundTripReport,
    MmcifZeroOccupancyAtomRow,
    MmcifZeroOccupancyAtomWriteReceipt,
    emit_mmcif_zero_occupancy_atoms,
    parse_mmcif_zero_occupancy_atoms,
    round_trip_mmcif_zero_occupancy_atoms_source,
    serialize_mmcif_zero_occupancy_atoms,
)


FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / ("v2_1_mmcif_unobserved_atoms")
)

_SINGLE_ROW = b"1 Y 0 1 AX ALA AUTH-1 ? CB ? A ALA 1 CB"
_SINGLE_COORDINATE = b"ATOM 1 C CB . ALA A 1 1 ? 0 0 0 0.0 20.0 ? AUTH-1 ALA AX CB 1"


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    assert source.count(old) == 1
    return source.replace(old, new, 1)


def _fixture(name: str) -> bytes:
    source = (FIXTURES / name).read_bytes().replace(b" Y 1 1 ", b" Y 0 1 ")
    replacements: dict[str, tuple[tuple[bytes, bytes], ...]] = {
        "single_atom_claim.cif": (
            (
                b"ATOM 1 N N . ALA A 1 1 ? 0 0 0 1.0 20.0 ? AUTH-1 ALA AX N 1",
                _SINGLE_COORDINATE,
            ),
        ),
        "category_order_variant.cif": (
            (
                b"ATOM 1 N N . ALA A 1 1 ? 0 0 0 1.0 20.0 ? AUTH-1 ALA AX N 1",
                _SINGLE_COORDINATE,
            ),
        ),
        "multiple_ordered_claims.cif": (
            (
                b"ATOM 1 N N . ALA A 1 1 ? 0 0 0 1.0 20.0 ? AUTH-1 ALA AX N 1",
                b"ATOM 1 C CB . ALA A 1 1 ? 0 0 0 0 20.0 ? AUTH-1 ALA AX CB 1",
            ),
            (
                b"ATOM 2 C CA . SER A 1 2 ? 1 0 0 1.0 20.0 ? AUTH-2 SER AX CA 1",
                b"ATOM 2 O OG . SER A 1 2 ? 1 0 0 0.00 20.0 ? AUTH-2 SER AX OG 1",
            ),
        ),
        "insertion_and_alt_markers.cif": (
            (
                b"ATOM 1 N N . ALA A 1 1 B 0 0 0 1.0 20.0 ? AUTH-42 ALA AUTH-A N 1",
                b"ATOM 1 C CB . ALA A 1 1 B 0 0 0 0e0 20.0 ? AUTH-42 ALA AUTH-A AUTH-CB 1",
            ),
        ),
        "shared_entity_multiple_asym.cif": (
            (
                b"ATOM 1 N N . ALA A 1 1 ? 0 0 0 1.0 20.0 ? 101 ALA AX N 1",
                b"ATOM 1 C CB . ALA A 1 1 ? 0 0 0 0 20.0 ? 101 ALA AX CB 1",
            ),
            (
                b"ATOM 2 N N . ALA B 1 1 ? 0 1 0 1.0 20.0 ? 201 ALA BX N 1",
                b"ATOM 2 C CB . ALA B 1 1 ? 0 1 0 0 20.0 ? 201 ALA BX CB 1",
            ),
        ),
        "composed_nonpoly_carrier.cif": (
            (
                b"ATOM 1 N N . ALA A 1 1 ? 0 0 0 1.0 20.0 ? 101 ALA AX N 1",
                b"ATOM 1 C CB . ALA A 1 1 ? 0 0 0 0 20.0 ? 101 ALA AX CB 1",
            ),
        ),
    }
    for old, new in replacements[name]:
        source = _replace_once(source, old, new)
    return source


class _FixtureBytes(bytes):
    def read_bytes(self) -> bytes:
        return bytes(self)


SINGLE = _FixtureBytes(_fixture("single_atom_claim.cif"))
MULTIPLE = _FixtureBytes(_fixture("multiple_ordered_claims.cif"))
INSERTION = _FixtureBytes(_fixture("insertion_and_alt_markers.cif"))
SHARED = _FixtureBytes(_fixture("shared_entity_multiple_asym.cif"))
COMPOSED = _FixtureBytes(_fixture("composed_nonpoly_carrier.cif"))
CATEGORY_ORDER = _FixtureBytes(_fixture("category_order_variant.cif"))
_FALSE_GATES = (
    "source_authenticated",
    "auth_label_equivalence_inferred",
    "reference_sequence_equivalence_assessed",
    "coordinate_observation_completeness_assessed",
    "missing_atom_fact_claimed",
    "zero_occupancy_atom_fact_claimed",
    "occupancy_population_interpreted",
    "occupancy_weighting_applied",
    "refinement_validity_assessed",
    "altloc_population_interpreted",
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


def _assert_error(source: bytes, code: str) -> MmcifZeroOccupancyAtomError:
    with pytest.raises(MmcifZeroOccupancyAtomError) as exc_info:
        parse_mmcif_zero_occupancy_atoms(source)
    assert exc_info.value.code == code
    return exc_info.value


def _assert_false_claims(document: dict[str, object]) -> None:
    assert (
        document["source_reported_zero_occupancy_atom_declarations_preserved"] is True
    )
    for field_name in _FALSE_GATES:
        assert document[field_name] is False


def _rows_payload(row_count: int) -> bytes:
    source = SINGLE.read_bytes()
    rows = b"\n".join(
        (f"{index} Y 0 1 AX ALA AUTH-1 ? M{index} ? A ALA 1 M{index}").encode("ascii")
        for index in range(1, row_count + 1)
    )
    atoms = b"\n".join(
        (
            f"ATOM {index} C M{index} . ALA A 1 1 ? {index} 0 0 "
            f"0 20 ? AUTH-1 ALA AX M{index} 1"
        ).encode("ascii")
        for index in range(1, row_count + 1)
    )
    return _replace_once(
        _replace_once(source, _SINGLE_ROW, rows),
        _SINGLE_COORDINATE,
        atoms,
    )


def _long_token_source() -> bytes:
    x = "X" * MAX_MMCIF_ZERO_OCCUPANCY_ATOM_TOKEN_CHARS
    asym = "A" * MAX_MMCIF_ZERO_OCCUPANCY_ATOM_TOKEN_CHARS
    comp = "C" * MAX_MMCIF_ZERO_OCCUPANCY_ATOM_TOKEN_CHARS
    insertion = "I" * MAX_MMCIF_ZERO_OCCUPANCY_ATOM_TOKEN_CHARS
    missing_atom = "M" * MAX_MMCIF_ZERO_OCCUPANCY_ATOM_TOKEN_CHARS
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
        *MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS,
        *map(
            str,
            (
                1,
                "Y",
                0,
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
                "C",
                missing_atom,
                ".",
                comp,
                asym,
                "E",
                1,
                insertion,
                0,
                0,
                0,
                0,
                20,
                "?",
                "AUTH-1",
                "ALA",
                "AX",
                "CB",
                1,
            ),
        ),
        "#",
        "",
    ]
    return "\n".join(lines).encode("ascii")


def test_single_atom_declaration_round_trip_and_base_metadata_binding() -> None:
    source = SINGLE.read_bytes()
    ingest = parse_mmcif_zero_occupancy_atoms(source, source_id="single-atom")
    result = round_trip_mmcif_zero_occupancy_atoms_source(
        source, source_id="single-atom"
    )
    row = ingest.zero_occupancy_atom_rows[0]
    report = ingest.missingness_report

    assert MMCIF_ZERO_OCCUPANCY_ATOM_ENVELOPE_VERSION == "1.0.0"
    assert MMCIF_ZERO_OCCUPANCY_ATOM_PROJECTION_SCOPE == (
        "source_reported_zero_occupancy_polymer_atom_declarations_and_exact_selected_"
        "coordinate_zero_crosscheck_only"
    )
    assert len(MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS) == 14
    assert MAX_MMCIF_ZERO_OCCUPANCY_ATOM_ROWS == 2_857
    assert (
        row.auth_atom_id,
        row.label_alt_id,
        row.label_asym_id,
        row.label_comp_id,
        row.label_seq_id,
        row.label_atom_id,
    ) == ("CB", "?", "A", "ALA", 1, "CB")
    assert report.source_reported_missing_residue_count == 0
    assert report.source_reported_missing_atom_count == 0
    assert report.missing_residue_claims == ()
    assert report.missing_atom_claims == ()
    summary = ingest.base_ingest.system.metadata["mmcif"]["source_missingness"]
    assert summary["zero_occupancy_atom_row_count"] == 1
    assert summary["zero_occupancy_residue_row_count"] == 0
    assert summary["unobserved_residue_claim_count"] == 0
    assert summary["unobserved_atom_claim_count"] == 0

    assert serialize_mmcif_zero_occupancy_atoms(ingest) == result.write_result.payload
    assert result.source_ingest.zero_occupancy_atom_rows == (
        result.reparsed_ingest.zero_occupancy_atom_rows
    )
    assert result.report.zero_occupancy_atom_projection_sha256_equal is True
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
    multiple = round_trip_mmcif_zero_occupancy_atoms_source(MULTIPLE.read_bytes())
    assert [
        row.source_id for row in multiple.source_ingest.zero_occupancy_atom_rows
    ] == [
        2,
        7,
    ]
    assert multiple.write_result.payload.index(b"2 Y 0 1") < (
        multiple.write_result.payload.index(b"7 Y 0 1")
    )

    shared = round_trip_mmcif_zero_occupancy_atoms_source(SHARED.read_bytes())
    assert [
        (row.label_asym_id, row.label_atom_id)
        for row in shared.source_ingest.zero_occupancy_atom_rows
    ] == [("A", "CB"), ("B", "CB")]

    composed = round_trip_mmcif_zero_occupancy_atoms_source(COMPOSED.read_bytes())
    assert composed.source_ingest.has_nonpoly_identity is True
    assert (
        composed.source_ingest.carrier_kind == "mmcif_polymer_sequence_nonpoly_identity"
    )
    assert composed.report.nonpoly_identity_projection_sha256_equal is True

    canonical = round_trip_mmcif_zero_occupancy_atoms_source(SINGLE.read_bytes())
    reordered = round_trip_mmcif_zero_occupancy_atoms_source(
        CATEGORY_ORDER.read_bytes()
    )
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
    insertion = round_trip_mmcif_zero_occupancy_atoms_source(INSERTION.read_bytes())
    row = insertion.source_ingest.zero_occupancy_atom_rows[0]
    assert row.source_id == (1 << 53) - 1
    assert (row.pdb_ins_code, row.label_alt_id) == ("B", ".")
    assert row.auth_atom_id == "AUTH-CB"
    assert (
        insertion.source_ingest.base_ingest.system.metadata["mmcif"][
            "source_missingness"
        ]["zero_occupancy_atom_row_count"]
        == 1
    )

    question = parse_mmcif_zero_occupancy_atoms(SINGLE.read_bytes())
    dot_source = _replace_once(
        SINGLE.read_bytes(),
        _SINGLE_ROW,
        b"1 Y 0 1 AX ALA AUTH-1 . CB . A ALA 1 CB",
    )
    dot = parse_mmcif_zero_occupancy_atoms(dot_source)
    assert question.zero_occupancy_atom_projection_sha256 != (
        dot.zero_occupancy_atom_projection_sha256
    )
    assert dot.zero_occupancy_atom_rows[0].pdb_ins_code == "."
    assert dot.zero_occupancy_atom_rows[0].label_alt_id == "."


def test_semantic_duplicate_normalizes_dot_and_question_mark() -> None:
    rows = b"\n".join(
        (
            _SINGLE_ROW,
            b"2 Y 0 1 AX ALA AUTH-1 . CB . A ALA 1 CB",
        )
    )
    _assert_error(
        _replace_once(SINGLE.read_bytes(), _SINGLE_ROW, rows),
        "duplicate_zero_occupancy_atom_identity",
    )


def test_insertion_parent_exact_atom_and_occupancy_fail_closed() -> None:
    mismatched_insertion = _replace_once(
        SINGLE.read_bytes(),
        _SINGLE_ROW,
        b"1 Y 0 1 AX ALA AUTH-1 B CB ? A ALA 1 CB",
    )
    _assert_error(mismatched_insertion, "zero_occupancy_atom_residue_absent")

    absent_atom = _replace_once(
        SINGLE.read_bytes(),
        _SINGLE_COORDINATE,
        b"ATOM 1 N N . ALA A 1 1 ? 0 0 0 0.0 20.0 ? AUTH-1 ALA AX N 1",
    )
    _assert_error(absent_atom, "zero_occupancy_atom_atom_absent")

    nonzero = _replace_once(_SINGLE_COORDINATE, b" 0.0 20.0 ", b" 1.0 20.0 ")
    _assert_error(
        _replace_once(SINGLE.read_bytes(), _SINGLE_COORDINATE, nonzero),
        "zero_occupancy_atom_occupancy_nonzero",
    )

    unavailable = _replace_once(_SINGLE_COORDINATE, b" 0.0 20.0 ", b" . 20.0 ")
    _assert_error(
        _replace_once(SINGLE.read_bytes(), _SINGLE_COORDINATE, unavailable),
        "zero_occupancy_atom_occupancy_unavailable",
    )


def test_all_matching_atom_site_occupancies_must_be_exact_numeric_zero() -> None:
    duplicate_zero = (
        _SINGLE_COORDINATE
        + b"\nATOM 2 C CB . ALA A 1 1 ? 1 0 0 -0e5 20.0 ? AUTH-1 ALA AX CB 1"
    )
    accepted = _replace_once(SINGLE.read_bytes(), _SINGLE_COORDINATE, duplicate_zero)
    # The existing common-core21 carrier rejects duplicate semantic atom identities,
    # but only after this envelope has accepted every matching occupancy as zero.
    _assert_error(accepted, "invalid_polymer_carrier")

    _assert_error(
        _replace_once(accepted, b" -0e5 20.0 ", b" 0.5 20.0 "),
        "zero_occupancy_atom_occupancy_nonzero",
    )
    _assert_error(
        _replace_once(accepted, b" -0e5 20.0 ", b" ? 20.0 "),
        "zero_occupancy_atom_occupancy_unavailable",
    )
    _assert_error(
        _replace_once(SINGLE.read_bytes(), b" 0.0 20.0 ", b" 0_0 20.0 "),
        "zero_occupancy_atom_occupancy_unavailable",
    )


@pytest.mark.parametrize(
    ("replacement", "code"),
    (
        (
            b"1 N 0 1 AX ALA AUTH-1 ? CB ? A ALA 1 CB",
            "unsupported_zero_occupancy_atom_polymer_flag",
        ),
        (
            b"1 Y 1 1 AX ALA AUTH-1 ? CB ? A ALA 1 CB",
            "unsupported_zero_occupancy_atom_occupancy_flag",
        ),
        (
            b"1 Y 0 2 AX ALA AUTH-1 ? CB ? A ALA 1 CB",
            "unsupported_zero_occupancy_atom_model",
        ),
        (
            b"1 Y 0 1 AX ALA AUTH-1 ? CB A A ALA 1 CB",
            "unsupported_zero_occupancy_atom_altloc",
        ),
        (
            b"1 Y 0 1 AX ALA AUTH-1 ? CB ? Z ALA 1 CB",
            "unknown_zero_occupancy_atom_asym_id",
        ),
        (
            b"1 Y 0 1 AX ALA AUTH-1 ? CB ? A SER 1 CB",
            "zero_occupancy_atom_sequence_join_mismatch",
        ),
        (
            b"9007199254740992 Y 0 1 AX ALA AUTH-1 ? CB ? A ALA 1 CB",
            "duplicate_or_invalid_zero_occupancy_atom_id",
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
9 Y 0 1 AX ALA AUTH-1 ? A ALA 1
#
"""
    mixed = _replace_once(
        SINGLE.read_bytes(),
        b"loop_\n_atom_site.group_pdb",
        residue_loop + b"loop_\n_atom_site.group_pdb",
    )
    _assert_error(mixed, "mixed_residue_zero_occupancy_unsupported")

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
        + b"\n".join(
            header.encode("ascii") for header in MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS
        )
        + b"\n"
        + _SINGLE_ROW
        + b"\n#\n"
    )
    scalar_values = _SINGLE_ROW.split()
    scalar_block = (
        b"\n".join(
            header.encode("ascii") + b" " + value
            for header, value in zip(
                MMCIF_ZERO_OCCUPANCY_ATOM_HEADERS, scalar_values, strict=True
            )
        )
        + b"\n#\n"
    )
    cases = (
        (
            _replace_once(source, b"1 polymer\n", b"1 non-polymer\n"),
            "zero_occupancy_atom_nonpolymer_entity",
        ),
        (
            _replace_once(
                source, _SINGLE_ROW, b"1 Y 0 1 AX ALA AUTH-1 ? CB ? A ALA 0 CB"
            ),
            "invalid_label_seq_id",
        ),
        (
            _replace_once(
                source,
                _SINGLE_ROW,
                _SINGLE_ROW + b"\n1 Y 0 1 AX ALA AUTH-1 ? OG ? A ALA 1 OG",
            ),
            "duplicate_or_invalid_zero_occupancy_atom_id",
        ),
        (
            _replace_once(
                source,
                _SINGLE_ROW,
                b"1 Y 0 1 'AX' ALA AUTH-1 ? CB ? A ALA 1 CB",
            ),
            "invalid_zero_occupancy_atom_token",
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
    accepted = parse_mmcif_zero_occupancy_atoms(
        _rows_payload(MAX_MMCIF_ZERO_OCCUPANCY_ATOM_ROWS)
    )
    assert len(accepted.zero_occupancy_atom_rows) == MAX_MMCIF_ZERO_OCCUPANCY_ATOM_ROWS
    _assert_error(
        _rows_payload(MAX_MMCIF_ZERO_OCCUPANCY_ATOM_ROWS + 1),
        "too_many_zero_occupancy_atom_rows",
    )


def test_long_tokens_split_physical_lines_and_round_trip_stably() -> None:
    source = _long_token_source()
    assert max(map(len, source.splitlines())) <= 2_048
    result = round_trip_mmcif_zero_occupancy_atoms_source(source)
    output_lines = result.write_result.payload.splitlines()
    assert max(map(len, output_lines)) <= 2_048
    assert b"X" * MAX_MMCIF_ZERO_OCCUPANCY_ATOM_TOKEN_CHARS in (
        result.write_result.payload
    )
    assert result.write_result.payload == result.reemitted_write_result.payload


def test_base_preserve_only_metadata_is_not_accepted_by_counts_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parse = atom_module.parse_mmcif

    def forged_parse(*args, **kwargs):
        result = real_parse(*args, **kwargs)
        metadata = dict(result.system.metadata)
        mmcif = dict(metadata["mmcif"])
        summary = dict(mmcif["source_missingness"])
        if summary["zero_occupancy_atom_row_count"] != 1:
            return result
        summary["zero_occupancy_atom_row_count"] = 0
        mmcif["source_missingness"] = summary
        metadata["mmcif"] = mmcif
        forged_system = replace(result.system, metadata=metadata)
        return replace(result, system=forged_system)

    monkeypatch.setattr(atom_module, "parse_mmcif", forged_parse)
    _assert_error(SINGLE.read_bytes(), "missingness_report_mismatch")


def test_base_preserve_only_coverage_and_provenance_are_crosschecked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parse = atom_module.parse_mmcif

    def forged_parse(*args, **kwargs):
        result = real_parse(*args, **kwargs)
        summary = result.system.metadata["mmcif"]["source_missingness"]
        if summary["zero_occupancy_atom_row_count"] != 1:
            return result
        provenance_metadata = dict(result.system.provenance.metadata)
        coverage = dict(provenance_metadata["coverage"])
        coverage["claim_safe"] = True
        provenance_metadata["coverage"] = coverage
        forged_system = replace(
            result.system,
            provenance=replace(
                result.system.provenance,
                metadata=provenance_metadata,
            ),
        )
        return replace(result, system=forged_system)

    monkeypatch.setattr(atom_module, "parse_mmcif", forged_parse)
    _assert_error(SINGLE.read_bytes(), "missingness_report_mismatch")


def test_factory_only_artifacts_and_tamper_fail_closed() -> None:
    source = SINGLE.read_bytes()
    ingest = parse_mmcif_zero_occupancy_atoms(source)
    write = emit_mmcif_zero_occupancy_atoms(ingest)
    result = round_trip_mmcif_zero_occupancy_atoms_source(source)

    with pytest.raises(TypeError):
        MmcifZeroOccupancyAtomRow()
    with pytest.raises(TypeError):
        MmcifZeroOccupancyAtomIngestResult(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        MmcifZeroOccupancyAtomWriteReceipt(ingest, write.payload)
    with pytest.raises(TypeError):
        MmcifZeroOccupancyAtomRoundTripReport()
    with pytest.raises(FrozenInstanceError):
        ingest.record_state_sha256 = "0" * 64  # type: ignore[misc]

    object.__setattr__(ingest, "record_state_sha256", "0" * 64)
    with pytest.raises(MmcifZeroOccupancyAtomError) as ingest_exc:
        ingest.to_dict()
    assert ingest_exc.value.code == "stale_ingest_binding"

    object.__setattr__(write.receipt, "_payload", write.payload + b"#\n")
    with pytest.raises(MmcifZeroOccupancyAtomError) as receipt_exc:
        write.receipt.to_dict()
    assert receipt_exc.value.code == "stale_write_receipt"

    other = round_trip_mmcif_zero_occupancy_atoms_source(source, source_id="other")
    object.__setattr__(result, "_report", other.report)
    with pytest.raises(MmcifZeroOccupancyAtomError) as crosswire_exc:
        result.to_dict()
    assert crosswire_exc.value.code == "crosswired_round_trip_artifacts"


def test_row_carrier_and_snapshot_ingest_crosswires_fail_closed() -> None:
    source = SINGLE.read_bytes()
    other = round_trip_mmcif_zero_occupancy_atoms_source(MULTIPLE.read_bytes())
    for field_name, replacement in (
        ("zero_occupancy_atom_rows", other.source_ingest.zero_occupancy_atom_rows),
        ("_carrier_source_bytes", other.source_ingest._carrier_source_bytes),
        ("_system_snapshot_payload", other.source_ingest._system_snapshot_payload),
    ):
        ingest = parse_mmcif_zero_occupancy_atoms(source)
        object.__setattr__(ingest, field_name, replacement)
        with pytest.raises(MmcifZeroOccupancyAtomError) as exc_info:
            ingest.to_dict()
        assert exc_info.value.code == "stale_ingest_binding"


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
    ingest = parse_mmcif_zero_occupancy_atoms(SINGLE.read_bytes())
    object.__setattr__(ingest.zero_occupancy_atom_rows[0], field_name, replacement)

    with pytest.raises(MmcifZeroOccupancyAtomError) as document_exc:
        ingest.to_dict()
    assert document_exc.value.code == "stale_ingest_binding"
    with pytest.raises(MmcifZeroOccupancyAtomError) as emit_exc:
        emit_mmcif_zero_occupancy_atoms(ingest)
    assert emit_exc.value.code == "stale_ingest_binding"


def test_repr_does_not_include_source_identity() -> None:
    result = round_trip_mmcif_zero_occupancy_atoms_source(
        SINGLE.read_bytes(), source_id="private-source-identity"
    )
    for artifact in (
        result.source_ingest,
        result.source_ingest.zero_occupancy_atom_rows[0],
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
            parse_mmcif_zero_occupancy_atoms(value)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        parse_mmcif_zero_occupancy_atoms(source, source_id=1)  # type: ignore[arg-type]
    _assert_error(b"", "empty_input")

    non_ascii = _replace_once(
        source,
        _SINGLE_ROW,
        b"1 Y 0 1 AX ALA PRIVATE-\xff ? CB ? A ALA 1 CB",
    )
    error = _assert_error(non_ascii, "non_ascii_input")
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "PRIVATE" not in str(error)
    assert "PRIVATE" not in repr(error)

    too_long = b"X" * (MAX_MMCIF_ZERO_OCCUPANCY_ATOM_TOKEN_CHARS + 1)
    _assert_error(
        _replace_once(
            source,
            _SINGLE_ROW,
            b"1 Y 0 1 AX ALA " + too_long + b" ? CB ? A ALA 1 CB",
        ),
        "invalid_identity_token",
    )

    monkeypatch.setattr(atom_module, "MAX_MMCIF_ZERO_OCCUPANCY_ATOM_ROWS", 0)
    _assert_error(source, "too_many_zero_occupancy_atom_rows")
    monkeypatch.setattr(
        atom_module,
        "MAX_MMCIF_ZERO_OCCUPANCY_ATOM_ROWS",
        MAX_MMCIF_ZERO_OCCUPANCY_ATOM_ROWS,
    )
    monkeypatch.setattr(
        atom_module, "MAX_MMCIF_ZERO_OCCUPANCY_ATOM_INPUT_BYTES", len(source) - 1
    )
    _assert_error(source, "input_too_large")


@pytest.mark.parametrize(
    ("source_id", "code"),
    (
        (
            "x" * (atom_module.MAX_MMCIF_ZERO_OCCUPANCY_ATOM_SOURCE_ID_BYTES + 1),
            "source_id_too_large",
        ),
        ("\ud800", "invalid_source_id"),
    ),
)
def test_source_id_is_resource_bounded_and_unicode_scalar_safe(
    source_id: str, code: str
) -> None:
    with pytest.raises(MmcifZeroOccupancyAtomError) as exc_info:
        parse_mmcif_zero_occupancy_atoms(SINGLE.read_bytes(), source_id=source_id)
    assert exc_info.value.code == code


def test_public_system_is_detached_and_nested_type_tamper_is_typed() -> None:
    result = round_trip_mmcif_zero_occupancy_atoms_source(SINGLE.read_bytes())
    system = result.source_ingest.system
    original = float(result.source_ingest.system.coordinates[0, 0, 0])
    system.coordinates[0, 0, 0] = original + 100.0
    assert float(result.source_ingest.system.coordinates[0, 0, 0]) == original

    object.__setattr__(result, "_write_result", None)
    with pytest.raises(MmcifZeroOccupancyAtomError) as aggregate_exc:
        result.to_dict()
    assert aggregate_exc.value.code == "crosswired_round_trip_artifacts"

    result = round_trip_mmcif_zero_occupancy_atoms_source(SINGLE.read_bytes())
    write_result = result.write_result
    object.__setattr__(write_result, "receipt", None)
    with pytest.raises(MmcifZeroOccupancyAtomError) as write_exc:
        write_result.to_dict()
    assert write_exc.value.code == "stale_write_result"

    result = round_trip_mmcif_zero_occupancy_atoms_source(SINGLE.read_bytes())
    report = result.report
    object.__setattr__(report, "_source", None)
    with pytest.raises(MmcifZeroOccupancyAtomError) as report_exc:
        report.to_dict()
    assert report_exc.value.code == "stale_round_trip_report"


@pytest.mark.parametrize(
    "tamper",
    (
        "source_full_source",
        "source_carrier_component",
        "source_missingness_component",
        "source_snapshot_component",
        "source_rows_container",
        "reparsed_full_source",
        "write_payload",
        "write_receipt",
        "write_receipt_ingest",
        "reemitted_receipt_ingest",
        "round_trip_report",
    ),
)
def test_round_trip_chain_accessors_and_document_fail_after_nested_tamper(
    tamper: str,
) -> None:
    result = round_trip_mmcif_zero_occupancy_atoms_source(SINGLE.read_bytes())

    if tamper == "source_full_source":
        object.__setattr__(
            result._source_ingest,
            "_full_source",
            result._source_ingest._full_source + b"#\n",
        )
    elif tamper == "source_carrier_component":
        object.__setattr__(
            result._source_ingest,
            "_carrier_source_bytes",
            result._source_ingest._carrier_source_bytes + b"#\n",
        )
    elif tamper == "source_missingness_component":
        object.__setattr__(
            result._source_ingest,
            "_missingness_source_bytes",
            result._source_ingest._missingness_source_bytes + b"#\n",
        )
    elif tamper == "source_snapshot_component":
        object.__setattr__(
            result._source_ingest,
            "_system_snapshot_payload",
            result._source_ingest._system_snapshot_payload + b"\x00",
        )
    elif tamper == "source_rows_container":
        object.__setattr__(
            result._source_ingest,
            "zero_occupancy_atom_rows",
            list(result._source_ingest.zero_occupancy_atom_rows),
        )
    elif tamper == "reparsed_full_source":
        object.__setattr__(
            result._reparsed_ingest,
            "_full_source",
            result._reparsed_ingest._full_source + b"#\n",
        )
    elif tamper == "write_payload":
        object.__setattr__(
            result._write_result,
            "payload",
            result._write_result.payload + b"#\n",
        )
    elif tamper == "write_receipt":
        receipt = result._write_result.receipt
        object.__setattr__(receipt, "_document_bytes", b" " + receipt._document_bytes)
    elif tamper == "write_receipt_ingest":
        object.__setattr__(
            result._write_result.receipt._ingest,
            "record_state_sha256",
            "0" * 64,
        )
    elif tamper == "reemitted_receipt_ingest":
        object.__setattr__(
            result._reemitted_write_result.receipt._ingest,
            "record_state_sha256",
            "0" * 64,
        )
    elif tamper == "round_trip_report":
        object.__setattr__(
            result._report,
            "_document_bytes",
            b" " + result._report._document_bytes,
        )
    else:
        raise AssertionError(f"unknown tamper case: {tamper}")

    for accessor_name in (
        "source_ingest",
        "write_result",
        "reparsed_ingest",
        "reemitted_write_result",
        "report",
    ):
        with pytest.raises(MmcifZeroOccupancyAtomError) as accessor_exc:
            getattr(result, accessor_name)
        assert accessor_exc.value.code == "crosswired_round_trip_artifacts"
    with pytest.raises(MmcifZeroOccupancyAtomError) as document_exc:
        result.to_dict()
    assert document_exc.value.code == "crosswired_round_trip_artifacts"


def test_noncanonical_evidence_and_coherent_payload_rewrite_fail_closed() -> None:
    result = round_trip_mmcif_zero_occupancy_atoms_source(SINGLE.read_bytes())
    receipt = result.write_result.receipt
    object.__setattr__(receipt, "_document_bytes", b" " + receipt._document_bytes)
    with pytest.raises(MmcifZeroOccupancyAtomError) as receipt_exc:
        _ = receipt.receipt_sha256
    assert receipt_exc.value.code == "invalid_write_receipt"

    result = round_trip_mmcif_zero_occupancy_atoms_source(SINGLE.read_bytes())
    report = result.report
    object.__setattr__(
        report,
        "_document_bytes",
        b'{"round_trip_report_sha256":NaN}',
    )
    with pytest.raises(MmcifZeroOccupancyAtomError) as report_exc:
        _ = report.round_trip_report_sha256
    assert report_exc.value.code == "invalid_round_trip_report"

    result = round_trip_mmcif_zero_occupancy_atoms_source(SINGLE.read_bytes())
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
    with pytest.raises(MmcifZeroOccupancyAtomError) as rewrite_exc:
        write_result.to_dict()
    assert rewrite_exc.value.code == "stale_write_receipt"


def test_same_payload_crosswires_remain_source_binding_sensitive() -> None:
    source = SINGLE.read_bytes()
    left = round_trip_mmcif_zero_occupancy_atoms_source(source, source_id="left")
    right = round_trip_mmcif_zero_occupancy_atoms_source(source, source_id="right")
    assert left.write_result.payload == right.write_result.payload
    object.__setattr__(left, "_reparsed_ingest", right.reparsed_ingest)
    object.__setattr__(left, "_reemitted_write_result", right.reemitted_write_result)
    with pytest.raises(MmcifZeroOccupancyAtomError) as source_id_exc:
        left.to_dict()
    assert source_id_exc.value.code == "crosswired_round_trip_artifacts"

    canonical = round_trip_mmcif_zero_occupancy_atoms_source(source)
    reordered = round_trip_mmcif_zero_occupancy_atoms_source(
        CATEGORY_ORDER.read_bytes()
    )
    assert canonical.write_result.payload == reordered.write_result.payload
    object.__setattr__(canonical, "_write_result", reordered.write_result)
    with pytest.raises(MmcifZeroOccupancyAtomError) as layout_exc:
        canonical.to_dict()
    assert layout_exc.value.code == "crosswired_round_trip_artifacts"
