from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
from pathlib import Path

import pytest

from betelgeuze_engine_v2.molecular import StructureParseError, parse_mmcif
from betelgeuze_engine_v2.molecular import mmcif_altloc_selection as altloc_module
from betelgeuze_engine_v2.molecular.mmcif_altloc_selection import (
    MMCIF_ALTLOC_SELECTION_ENVELOPE_VERSION,
    MMCIF_ALTLOC_SELECTION_PARSER_VERSION,
    MMCIF_ALTLOC_SELECTION_PROFILE_ID,
    MMCIF_ALTLOC_SELECTION_PROJECTION_SCOPE,
    MMCIF_ALTLOC_SELECTION_WRITER_VERSION,
    MmcifAltlocSelectionError,
    MmcifAltlocSelectionIngestResult,
    MmcifAltlocSelectionRoundTripReport,
    MmcifAltlocSelectionRoundTripResult,
    MmcifAltlocSelectionWriteReceipt,
    MmcifAltlocSelectionWriteResult,
    emit_mmcif_altloc_selection,
    mmcif_altloc_record_state_sha256,
    mmcif_altloc_selected_state_sha256,
    mmcif_altloc_source_projection_sha256,
    parse_mmcif_altloc_selection,
    round_trip_mmcif_altloc_selection_source,
    serialize_mmcif_altloc_selection,
)


FIXTURES = (
    Path(__file__).resolve().parents[1] / "fixtures" / "v2_1_mmcif_altloc_selection"
)
SELECT_A = FIXTURES / "select_a_with_blank.cif"
SELECT_B = FIXTURES / "select_b_with_blank.cif"
MULTI_ID = FIXTURES / "multi_character_ids.cif"
MULTI_RESIDUE = FIXTURES / "multiple_affected_residues.cif"
MIXED_ENTITY = FIXTURES / "mixed_entity_types.cif"
ORDER_NUMERIC = FIXTURES / "category_order_numeric_markers.cif"

_POSITIVE_CASES = (
    (SELECT_A, "A", 4, 3, 1, 1, ("", "A", "")),
    (SELECT_B, "B", 4, 3, 1, 1, ("", "B", "")),
    (MULTI_ID, "conf-A", 5, 3, 2, 1, ("", "conf-A", "conf-A")),
    (MULTI_RESIDUE, "A", 6, 4, 2, 2, ("", "A", "", "A")),
    (MIXED_ENTITY, "A", 7, 4, 3, 3, ("", "A", "A", "A")),
    (ORDER_NUMERIC, "alpha", 4, 3, 1, 1, ("", "", "alpha")),
)


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    assert old and source.count(old) == 1
    return source.replace(old, new, 1)


def _atom_rows(source: bytes) -> tuple[bytes, ...]:
    return tuple(
        line for line in source.splitlines() if line.startswith((b"ATOM ", b"HETATM "))
    )


def _drop_rows_with_ids(source: bytes, *source_ids: bytes) -> bytes:
    prefixes = tuple(b"ATOM " + source_id + b" " for source_id in source_ids)
    return (
        b"\n".join(
            line for line in source.splitlines() if not line.startswith(prefixes)
        )
        + b"\n"
    )


def _inject_before_atom_site(source: bytes, section: bytes) -> bytes:
    marker = b"loop_\n_atom_site.group_PDB"
    assert source.count(marker) == 1
    return source.replace(marker, section + marker, 1)


def _with_second_model(source: bytes) -> bytes:
    rows = _atom_rows(source)
    second_rows = []
    for ordinal, row in enumerate(rows, start=101):
        fields = row.split()
        fields[1] = str(ordinal).encode("ascii")
        fields[-1] = b"2"
        second_rows.append(b" ".join(fields))
    block = b"\n".join(rows)
    assert source.count(block) == 1
    return source.replace(block, block + b"\n" + b"\n".join(second_rows), 1)


def _with_split_long_auth_tokens(source: bytes) -> tuple[bytes, tuple[bytes, ...]]:
    long_tokens = tuple(character * 600 for character in (b"1", b"G", b"X", b"A"))
    lines: list[bytes] = []
    for line in source.splitlines():
        if not line.startswith((b"ATOM ", b"HETATM ")):
            lines.append(line)
            continue
        fields = line.split()
        fields[16:20] = long_tokens
        lines.extend(fields)
    return b"\n".join(lines) + b"\n", long_tokens


def _assert_error(
    source: bytes,
    altloc_id: str,
    code: str,
    *,
    source_id: str = "failure-source",
) -> MmcifAltlocSelectionError:
    with pytest.raises(MmcifAltlocSelectionError) as exc_info:
        parse_mmcif_altloc_selection(
            source,
            altloc_id=altloc_id,
            source_id=source_id,
        )
    assert exc_info.value.code == code
    return exc_info.value


def test_public_contract_versions_profile_and_exact_headers() -> None:
    assert MMCIF_ALTLOC_SELECTION_ENVELOPE_VERSION == "1.0.0"
    assert MMCIF_ALTLOC_SELECTION_PARSER_VERSION == "1.0.0"
    assert MMCIF_ALTLOC_SELECTION_WRITER_VERSION == "1.0.0"
    assert MMCIF_ALTLOC_SELECTION_PROFILE_ID == (
        "strict_mmcif_single_model_common_core21_explicit_altloc_selection_"
        "envelope/1.0.0"
    )
    assert MMCIF_ALTLOC_SELECTION_PROJECTION_SCOPE == (
        "source_reported_label_alt_id_rows_and_explicit_selected_coordinate_"
        "projection_only"
    )
    assert altloc_module.MMCIF_ALTLOC_SELECTION_ENTITY_HEADERS == (
        "_entity.id",
        "_entity.type",
    )
    assert altloc_module.MMCIF_ALTLOC_SELECTION_STRUCT_ASYM_HEADERS == (
        "_struct_asym.id",
        "_struct_asym.entity_id",
    )
    assert len(altloc_module.MMCIF_ALTLOC_SELECTION_ATOM_SITE_HEADERS) == 21
    assert (
        altloc_module.MMCIF_ALTLOC_SELECTION_ATOM_SITE_HEADERS[4]
        == "_atom_site.label_alt_id"
    )
    assert altloc_module.MAX_MMCIF_ALTLOC_SELECTION_ALTLOC_ID_CHARS == 256


@pytest.mark.parametrize(
    (
        "path",
        "altloc_id",
        "source_rows",
        "selected_rows",
        "discarded_rows",
        "affected_residues",
        "selected_altlocs",
    ),
    _POSITIVE_CASES,
)
def test_six_positive_profiles_bind_selected_and_discarded_source_rows(
    path: Path,
    altloc_id: str,
    source_rows: int,
    selected_rows: int,
    discarded_rows: int,
    affected_residues: int,
    selected_altlocs: tuple[str, ...],
) -> None:
    source = path.read_bytes()
    result = round_trip_mmcif_altloc_selection_source(
        source,
        altloc_id=altloc_id,
        source_id=path.stem,
    )
    ingest = result.source_ingest

    assert ingest.altloc_id == altloc_id
    assert ingest.source_atom_row_count == source_rows
    assert ingest.selected_atom_row_count == selected_rows
    assert ingest.discarded_atom_row_count == discarded_rows
    assert ingest.affected_residue_count == affected_residues
    assert ingest.entity_row_count in {1, 3}
    assert ingest.struct_asym_row_count in {1, 3}
    assert tuple(atom.altloc for atom in ingest.system.atoms) == selected_altlocs
    assert ingest.full_source_sha256 == hashlib.sha256(source).hexdigest()
    assert mmcif_altloc_source_projection_sha256(ingest) == (
        ingest.source_projection_sha256
    )
    assert mmcif_altloc_selected_state_sha256(ingest) == (ingest.selected_state_sha256)
    assert mmcif_altloc_record_state_sha256(ingest) == ingest.record_state_sha256
    assert serialize_mmcif_altloc_selection(ingest) == result.write_result.payload
    assert result.write_result.payload == result.reemitted_write_result.payload
    assert result.report.second_emission_byte_stable is True
    assert result.report.source_projection_equal is True
    assert result.report.selected_state_equal is True
    assert result.report.topology_equal is True
    assert result.report.emitted_source_reparsed_exact is True


def test_opt_in_envelope_preserves_all_rows_while_base_writer_remains_unchanged() -> (
    None
):
    source = SELECT_A.read_bytes()
    ingest = parse_mmcif_altloc_selection(source, altloc_id="A")
    output = emit_mmcif_altloc_selection(ingest).payload

    assert len(_atom_rows(output)) == 4
    assert any(b" CA A GLY " in row for row in _atom_rows(output))
    assert any(b" CA B GLY " in row for row in _atom_rows(output))
    assert ingest.system.atom_count == 3
    with pytest.raises(StructureParseError) as base_error:
        parse_mmcif(source)
    assert base_error.value.code == "unsupported_altloc"


def test_category_layout_normalizes_and_raw_marker_numeric_spelling_is_bound() -> None:
    result = round_trip_mmcif_altloc_selection_source(
        ORDER_NUMERIC.read_bytes(), altloc_id="alpha"
    )
    payload = result.write_result.payload
    lowered = payload.lower()

    assert lowered.index(b"_entity.id") < lowered.index(b"_struct_asym.id")
    assert lowered.index(b"_struct_asym.id") < lowered.index(b"_atom_site.group_pdb")
    assert b" 001 " in payload
    assert b" N . GLY " in payload
    assert b" C ? GLY " in payload
    assert b" CA alpha GLY " in payload
    assert b" CA beta GLY " in payload
    assert b" +0 -0 .25 01.000 -0 +0 " in payload
    assert result.source_ingest.source_projection_document == (
        result.reparsed_ingest.source_projection_document
    )


def test_canonical_output_splits_bounded_long_logical_rows() -> None:
    source, long_tokens = _with_split_long_auth_tokens(SELECT_A.read_bytes())
    result = round_trip_mmcif_altloc_selection_source(source, altloc_id="A")
    payload = result.write_result.payload

    assert max(map(len, payload.splitlines())) <= (
        altloc_module.MAX_MMCIF_ALTLOC_SELECTION_OUTPUT_LINE_CHARS
    )
    assert all(token in payload for token in long_tokens)
    assert result.source_ingest.source_atom_row_count == 4
    assert result.report.second_emission_byte_stable is True


def test_selecting_different_ids_changes_only_the_selected_state_projection() -> None:
    source = SELECT_A.read_bytes()
    selected_a = round_trip_mmcif_altloc_selection_source(source, altloc_id="A")
    selected_b = round_trip_mmcif_altloc_selection_source(source, altloc_id="B")

    assert selected_a.source_ingest.source_projection_sha256 == (
        selected_b.source_ingest.source_projection_sha256
    )
    assert selected_a.source_ingest.selected_state_sha256 != (
        selected_b.source_ingest.selected_state_sha256
    )
    assert selected_a.source_ingest.record_state_sha256 != (
        selected_b.source_ingest.record_state_sha256
    )
    assert selected_a.write_result.payload == selected_b.write_result.payload
    assert selected_a.source_ingest.system.atoms[1].altloc == "A"
    assert selected_b.source_ingest.system.atoms[1].altloc == "B"


@pytest.mark.parametrize(
    ("source", "altloc_id", "code"),
    (
        (
            _drop_rows_with_ids(SELECT_A.read_bytes(), b"2", b"3"),
            "A",
            "requested_altloc_not_present",
        ),
        (
            SELECT_A.read_bytes(),
            "C",
            "requested_altloc_missing_for_residue",
        ),
        (
            _replace_once(
                MULTI_RESIDUE.read_bytes(),
                b"ATOM 6 C CA B SER",
                b"ATOM 6 C CA C SER",
            ),
            "B",
            "requested_altloc_missing_for_residue",
        ),
        (
            _replace_once(
                SELECT_A.read_bytes(),
                b"ATOM 3 C CA B GLY A 1 1 ? 2.0 0.0 0.0 0.4 12.0 ? 10 GLY X CA 1\n",
                b"ATOM 3 C CB B GLY A 1 1 ? 2.0 0.0 0.0 0.4 12.0 ? 10 GLY X CB 1\n",
            ),
            "A",
            "inconsistent_altloc_atom_identity",
        ),
        (
            _replace_once(
                SELECT_A.read_bytes(),
                b"ATOM 3 C CA B GLY",
                b"ATOM 3 N CA B GLY",
            ),
            "A",
            "inconsistent_altloc_atom_identity",
        ),
        (
            _replace_once(
                SELECT_A.read_bytes(),
                b"ATOM 3 C CA B GLY",
                b"ATOM 3 C CA . GLY",
            ),
            "A",
            "altloc_blank_collision",
        ),
        (
            _replace_once(
                SELECT_A.read_bytes(),
                b"ATOM 3 C CA B GLY",
                b"ATOM 22 C CA A GLY A 1 1 ? 1.0 0.0 0.0 0.6 11.0 ? 10 GLY X CA 1\n"
                b"ATOM 3 C CA B GLY",
            ),
            "A",
            "duplicate_altloc_atom_identity",
        ),
        (
            _replace_once(
                SELECT_A.read_bytes(),
                b"ATOM 3 C CA B GLY",
                b"ATOM 2 C CA B GLY",
            ),
            "A",
            "duplicate_atom_site_id",
        ),
        (
            _with_second_model(SELECT_A.read_bytes()),
            "A",
            "unsupported_model_id",
        ),
    ),
)
def test_altloc_selection_identity_and_single_model_failures_are_typed(
    source: bytes,
    altloc_id: str,
    code: str,
) -> None:
    _assert_error(source, altloc_id, code)


def test_base_atom_source_row_order_is_independently_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = SELECT_A.read_bytes()
    base = parse_mmcif(source, altloc_id="A", source_id="bound-source")
    atoms = list(base.system.atoms)
    source_ids = [atom.metadata["mmcif"]["source_atom_site_id"] for atom in atoms]
    forged_atoms = []
    for index, atom in enumerate(atoms):
        metadata = dict(atom.metadata)
        mmcif = dict(metadata["mmcif"])
        mmcif["source_atom_site_id"] = source_ids[(index + 1) % len(source_ids)]
        metadata["mmcif"] = mmcif
        forged_atoms.append(replace(atom, metadata=metadata))
    forged = replace(
        base,
        system=replace(base.system, atoms=tuple(forged_atoms)),
    )
    monkeypatch.setattr(altloc_module, "parse_mmcif", lambda *_args, **_kwargs: forged)

    _assert_error(
        source,
        "A",
        "base_mmcif_semantic_mismatch",
        source_id="bound-source",
    )


def test_base_count_types_reject_float_and_bool_equality_collisions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = SELECT_A.read_bytes()
    base = parse_mmcif(source, altloc_id="A", source_id="bound-source")
    forged_coverage = replace(
        base.coverage,
        source_atom_row_count=4.0,
        altloc_kept_row_count=3.0,
        altloc_discarded_row_count=1.0,
        altloc_affected_residue_count=True,
    )
    forged = replace(base, coverage=forged_coverage)
    monkeypatch.setattr(altloc_module, "parse_mmcif", lambda *_args, **_kwargs: forged)

    _assert_error(
        source,
        "A",
        "base_mmcif_semantic_mismatch",
        source_id="bound-source",
    )


@pytest.mark.parametrize(
    ("source", "altloc_id", "code"),
    (
        (
            _replace_once(
                SELECT_A.read_bytes(),
                b" CA A GLY ",
                b" CA 'A' GLY ",
            ),
            "A",
            "unsafe_cif_token",
        ),
        (
            _replace_once(
                SELECT_A.read_bytes(),
                b" 1.0 0.0 0.0 0.6 ",
                b" 1.0(1) 0.0 0.0 0.6 ",
            ),
            "A",
            "numeric_uncertainty_unsupported",
        ),
        (
            _replace_once(
                SELECT_A.read_bytes(),
                b"1 polymer\n#",
                b"1 branched\n#",
            ),
            "A",
            "unsupported_category_representation",
        ),
        (
            _replace_once(
                SELECT_A.read_bytes(),
                b"_entity.id\n_entity.type",
                b"_entity.type\n_entity.id",
            ),
            "A",
            "unsupported_category_headers",
        ),
        (
            _replace_once(
                SELECT_A.read_bytes(),
                b"ATOM 2 C CA A GLY A 1 1 ? 1.0 0.0 0.0 0.6 11.0 ? 10 GLY X CA 1\n",
                b"ATOM 2 C CA A GLY A 1 1 ? 1.0 0.0 0.0 0.6 11.0 ? 10 GLY X ? 1\n",
            ),
            "A",
            "unsupported_category_representation",
        ),
    ),
)
def test_exact_common_core21_representation_failures_are_typed(
    source: bytes,
    altloc_id: str,
    code: str,
) -> None:
    _assert_error(source, altloc_id, code)


_UNSUPPORTED_SECTIONS = (
    b"_pdbx_struct_assembly.id 1\n#\n",
    b"loop_\n_entity_poly_seq.entity_id\n_entity_poly_seq.num\n"
    b"_entity_poly_seq.mon_id\n_entity_poly_seq.hetero\n1 1 GLY n\n#\n",
    b"loop_\n_pdbx_entity_nonpoly.entity_id\n_pdbx_entity_nonpoly.comp_id\n2 LIG\n#\n",
    b"loop_\n_pdbx_unobs_or_zero_occ_residues.id\n"
    b"_pdbx_unobs_or_zero_occ_residues.polymer_flag\n"
    b"_pdbx_unobs_or_zero_occ_residues.occupancy_flag\n"
    b"_pdbx_unobs_or_zero_occ_residues.PDB_model_num\n"
    b"_pdbx_unobs_or_zero_occ_residues.auth_asym_id\n"
    b"_pdbx_unobs_or_zero_occ_residues.auth_comp_id\n"
    b"_pdbx_unobs_or_zero_occ_residues.auth_seq_id\n"
    b"_pdbx_unobs_or_zero_occ_residues.PDB_ins_code\n"
    b"_pdbx_unobs_or_zero_occ_residues.label_asym_id\n"
    b"_pdbx_unobs_or_zero_occ_residues.label_comp_id\n"
    b"_pdbx_unobs_or_zero_occ_residues.label_seq_id\n"
    b"1 Y 1 1 X GLY 2 ? A GLY 2\n#\n",
    b"loop_\n_pdbx_unobs_or_zero_occ_atoms.id\n"
    b"_pdbx_unobs_or_zero_occ_atoms.polymer_flag\n"
    b"_pdbx_unobs_or_zero_occ_atoms.occupancy_flag\n"
    b"_pdbx_unobs_or_zero_occ_atoms.PDB_model_num\n"
    b"_pdbx_unobs_or_zero_occ_atoms.auth_asym_id\n"
    b"_pdbx_unobs_or_zero_occ_atoms.auth_comp_id\n"
    b"_pdbx_unobs_or_zero_occ_atoms.auth_seq_id\n"
    b"_pdbx_unobs_or_zero_occ_atoms.PDB_ins_code\n"
    b"_pdbx_unobs_or_zero_occ_atoms.auth_atom_id\n"
    b"_pdbx_unobs_or_zero_occ_atoms.label_alt_id\n"
    b"_pdbx_unobs_or_zero_occ_atoms.label_asym_id\n"
    b"_pdbx_unobs_or_zero_occ_atoms.label_comp_id\n"
    b"_pdbx_unobs_or_zero_occ_atoms.label_seq_id\n"
    b"_pdbx_unobs_or_zero_occ_atoms.label_atom_id\n"
    b"1 Y 0 1 X GLY 1 ? CA A A GLY 1 CA\n#\n",
    b"_cell.length_a 10.0\n_cell.length_b 11.0\n_cell.length_c 12.0\n"
    b"_cell.angle_alpha 90.0\n_cell.angle_beta 90.0\n"
    b"_cell.angle_gamma 90.0\n#\n",
)


@pytest.mark.parametrize("section", _UNSUPPORTED_SECTIONS)
def test_unselected_category_surfaces_fail_before_any_projection(
    section: bytes,
) -> None:
    source = _inject_before_atom_site(SELECT_A.read_bytes(), section)
    _assert_error(source, "A", "unsupported_category_surface")


def test_factory_only_immutability_and_stale_ingest_binding() -> None:
    ingest = parse_mmcif_altloc_selection(SELECT_A.read_bytes(), altloc_id="A")

    for factory_type in (
        MmcifAltlocSelectionIngestResult,
        MmcifAltlocSelectionWriteReceipt,
        MmcifAltlocSelectionWriteResult,
        MmcifAltlocSelectionRoundTripReport,
        MmcifAltlocSelectionRoundTripResult,
    ):
        with pytest.raises(TypeError):
            factory_type()  # type: ignore[call-arg]
    with pytest.raises(FrozenInstanceError):
        ingest._full_source = b"data_forged\n#\n"  # type: ignore[misc]

    object.__setattr__(ingest, "_source_projection_bytes", b"{}")
    with pytest.raises(MmcifAltlocSelectionError) as document_error:
        ingest.to_dict()
    assert document_error.value.code == "stale_ingest_binding"
    with pytest.raises(MmcifAltlocSelectionError) as emit_error:
        emit_mmcif_altloc_selection(ingest)
    assert emit_error.value.code == "stale_ingest_binding"


def test_round_trip_validation_has_a_fixed_parse_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = altloc_module._parse_state
    calls = 0

    def counted_parse(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(altloc_module, "_parse_state", counted_parse)
    result = round_trip_mmcif_altloc_selection_source(
        SELECT_A.read_bytes(), altloc_id="A"
    )
    assert calls == 4
    result.to_dict()
    assert calls == 4


@pytest.mark.parametrize(
    ("hidden_field", "replacement"),
    (
        ("_full_source", b"data_forged\n#\n"),
        ("_source_id", "forged-source"),
        ("_altloc_id", "B"),
        ("_source_projection_bytes", b"{}"),
        ("_selected_state_bytes", b"{}"),
        ("_system_snapshot", b"{}"),
        ("_canonical_output", b"data_forged\n#\n"),
        ("_category_rows", ()),
    ),
)
def test_source_snapshot_row_and_container_tamper_fail_closed(
    hidden_field: str,
    replacement: object,
) -> None:
    ingest = parse_mmcif_altloc_selection(SELECT_A.read_bytes(), altloc_id="A")
    object.__setattr__(ingest, hidden_field, replacement)
    with pytest.raises(MmcifAltlocSelectionError) as exc_info:
        ingest.to_dict()
    assert exc_info.value.code == "stale_ingest_binding"


def test_coherent_access_binding_rewrite_cannot_replace_selected_snapshot() -> None:
    source = SELECT_A.read_bytes()
    result = round_trip_mmcif_altloc_selection_source(source, altloc_id="A")
    selected_b = parse_mmcif_altloc_selection(source, altloc_id="B")
    source_ingest = result._source_ingest

    object.__setattr__(
        source_ingest,
        "_system_snapshot",
        selected_b._system_snapshot,
    )
    forged_state = altloc_module._state_from_ingest(source_ingest)
    object.__setattr__(
        source_ingest,
        "_access_binding_bytes",
        altloc_module._canonical_json_bytes(
            altloc_module._state_access_binding_document(forged_state)
        ),
    )

    for operation in (
        source_ingest.to_dict,
        lambda: emit_mmcif_altloc_selection(source_ingest),
    ):
        with pytest.raises(MmcifAltlocSelectionError) as exc_info:
            operation()
        assert exc_info.value.code == "stale_ingest_binding"
    with pytest.raises(MmcifAltlocSelectionError) as aggregate_error:
        result.to_dict()
    assert aggregate_error.value.code == "crosswired_round_trip_artifacts"


@pytest.mark.parametrize("forged_count", (True, 1.0))
def test_bool_and_float_count_equality_collisions_are_not_admitted(
    forged_count: object,
) -> None:
    ingest = parse_mmcif_altloc_selection(SELECT_A.read_bytes(), altloc_id="A")
    document = ingest.source_projection_document
    document["source_atom_row_count"] = forged_count
    forged_bytes = altloc_module._canonical_json_bytes(document)
    object.__setattr__(ingest, "_source_projection_bytes", forged_bytes)

    with pytest.raises(MmcifAltlocSelectionError) as exc_info:
        ingest.to_dict()
    assert exc_info.value.code == "stale_ingest_binding"


@pytest.mark.parametrize(
    "tamper",
    (
        "source_full_source",
        "source_projection",
        "source_snapshot",
        "source_rows_container",
        "write_payload",
        "write_receipt",
        "write_receipt_ingest",
        "reparsed_source",
        "reemitted_receipt_ingest",
        "round_trip_report",
    ),
)
def test_nested_receipt_reparse_and_aggregate_crosswires_fail_closed(
    tamper: str,
) -> None:
    result = round_trip_mmcif_altloc_selection_source(
        SELECT_A.read_bytes(), altloc_id="A"
    )
    if tamper == "source_full_source":
        object.__setattr__(
            result._source_ingest,
            "_full_source",
            result._source_ingest._full_source + b"#\n",
        )
    elif tamper == "source_projection":
        object.__setattr__(
            result._source_ingest,
            "_source_projection_bytes",
            b"{}",
        )
    elif tamper == "source_snapshot":
        object.__setattr__(result._source_ingest, "_system_snapshot", b"{}")
    elif tamper == "source_rows_container":
        object.__setattr__(result._source_ingest, "_category_rows", ())
    elif tamper == "write_payload":
        object.__setattr__(
            result._write_result,
            "_payload",
            result._write_result._payload + b"#\n",
        )
    elif tamper == "write_receipt":
        object.__setattr__(
            result._write_result._receipt,
            "_document_bytes",
            b"{}",
        )
    elif tamper == "write_receipt_ingest":
        object.__setattr__(
            result._write_result._receipt._ingest,
            "_source_projection_bytes",
            b"{}",
        )
    elif tamper == "reparsed_source":
        object.__setattr__(result._reparsed_ingest, "_full_source", b"data_x\n#\n")
    elif tamper == "reemitted_receipt_ingest":
        object.__setattr__(
            result._reemitted_write_result._receipt._ingest,
            "_selected_state_bytes",
            b"{}",
        )
    elif tamper == "round_trip_report":
        object.__setattr__(result._report, "_document_bytes", b"{}")
    else:
        raise AssertionError(f"unknown tamper: {tamper}")

    for accessor in (
        "source_ingest",
        "write_result",
        "reparsed_ingest",
        "reemitted_write_result",
        "report",
    ):
        with pytest.raises(MmcifAltlocSelectionError) as accessor_error:
            getattr(result, accessor)
        assert accessor_error.value.code == "crosswired_round_trip_artifacts"
    with pytest.raises(MmcifAltlocSelectionError) as document_error:
        result.to_dict()
    assert document_error.value.code == "crosswired_round_trip_artifacts"


def test_same_source_and_same_payload_crosswires_remain_source_id_sensitive() -> None:
    source = SELECT_A.read_bytes()
    left = round_trip_mmcif_altloc_selection_source(
        source, altloc_id="A", source_id="left"
    )
    right = round_trip_mmcif_altloc_selection_source(
        source, altloc_id="A", source_id="right"
    )
    assert left.write_result.payload == right.write_result.payload
    object.__setattr__(left, "_reparsed_ingest", right.reparsed_ingest)
    object.__setattr__(
        left,
        "_reemitted_write_result",
        right.reemitted_write_result,
    )
    with pytest.raises(MmcifAltlocSelectionError) as exc_info:
        left.to_dict()
    assert exc_info.value.code == "crosswired_round_trip_artifacts"


def test_identical_semantic_chain_replacement_remains_object_bound() -> None:
    source = SELECT_A.read_bytes()
    left = round_trip_mmcif_altloc_selection_source(
        source, altloc_id="A", source_id="same-source"
    )
    right = round_trip_mmcif_altloc_selection_source(
        source, altloc_id="A", source_id="same-source"
    )

    for field in (
        "_source_ingest",
        "_write_result",
        "_reparsed_ingest",
        "_reemitted_write_result",
        "_report",
    ):
        object.__setattr__(left, field, getattr(right, field))

    with pytest.raises(MmcifAltlocSelectionError) as exc_info:
        left.to_dict()
    assert exc_info.value.code == "crosswired_round_trip_artifacts"


def test_public_system_is_detached_and_repr_hides_source_identity() -> None:
    result = round_trip_mmcif_altloc_selection_source(
        MULTI_ID.read_bytes(),
        altloc_id="conf-A",
        source_id="private-altloc-source",
    )
    detached = result.source_ingest.system
    original = float(result.source_ingest.system.coordinates[0, 0, 0])
    detached.coordinates[0, 0, 0] = original + 100.0
    assert float(result.source_ingest.system.coordinates[0, 0, 0]) == original

    for artifact in (
        result.source_ingest,
        result.write_result,
        result.write_result.receipt,
        result.report,
        result,
    ):
        assert "private-altloc-source" not in repr(artifact)
        assert "AUTH-1" not in repr(artifact)


def test_input_types_are_exact_and_error_text_does_not_echo_private_tokens() -> None:
    source = SELECT_A.read_bytes()
    for value in (bytearray(source), memoryview(source), source.decode("ascii")):
        with pytest.raises(TypeError):
            parse_mmcif_altloc_selection(  # type: ignore[arg-type]
                value,
                altloc_id="A",
            )
    for value in (None, 1, True, 1.0, b"A"):
        with pytest.raises(TypeError):
            parse_mmcif_altloc_selection(  # type: ignore[arg-type]
                source,
                altloc_id=value,
            )
    for value in (1, True, 1.0, b"source"):
        with pytest.raises(TypeError):
            parse_mmcif_altloc_selection(  # type: ignore[arg-type]
                source,
                altloc_id="A",
                source_id=value,
            )

    private = _replace_once(
        source,
        b" CA A GLY ",
        b" CA 'PRIVATE-ALT' GLY ",
    )
    error = _assert_error(private, "PRIVATE-ALT", "unsafe_cif_token")
    assert "PRIVATE-ALT" not in str(error)
    assert "PRIVATE-ALT" not in repr(error)

    with pytest.raises(MmcifAltlocSelectionError) as source_id_error:
        parse_mmcif_altloc_selection(
            source,
            altloc_id="A",
            source_id="private-\ud800-token",
        )
    assert source_id_error.value.code == "invalid_source_id"
    assert "private" not in str(source_id_error.value).lower()


def test_unexpected_base_integration_errors_are_generic_and_source_private(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_base(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("PRIVATE-BASE-DETAIL")

    monkeypatch.setattr(altloc_module, "parse_mmcif", fail_base)
    error = _assert_error(
        SELECT_A.read_bytes(),
        "A",
        "base_mmcif_integration_failed",
        source_id="PRIVATE-SOURCE-ID",
    )
    assert "PRIVATE" not in str(error)


def test_resource_caps_fail_closed_without_partial_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = SELECT_A.read_bytes()

    monkeypatch.setattr(
        altloc_module,
        "MAX_MMCIF_ALTLOC_SELECTION_INPUT_BYTES",
        len(source) - 1,
    )
    _assert_error(source, "A", "input_limit_exceeded")
    monkeypatch.setattr(
        altloc_module,
        "MAX_MMCIF_ALTLOC_SELECTION_INPUT_BYTES",
        len(source),
    )
    monkeypatch.setattr(altloc_module, "MAX_MMCIF_ALTLOC_SELECTION_ATOM_ROWS", 3)
    _assert_error(source, "A", "atom_row_limit_exceeded")


@pytest.mark.parametrize(
    ("constant_name", "limit", "code"),
    (
        ("MAX_MMCIF_ALTLOC_SELECTION_ENTITY_ROWS", 0, "entity_row_limit_exceeded"),
        (
            "MAX_MMCIF_ALTLOC_SELECTION_STRUCT_ASYM_ROWS",
            0,
            "struct_asym_row_limit_exceeded",
        ),
        (
            "MAX_MMCIF_ALTLOC_SELECTION_OUTPUT_BYTES",
            1,
            "output_limit_exceeded",
        ),
        (
            "MAX_MMCIF_ALTLOC_SELECTION_PROJECTION_BYTES",
            1,
            "projection_limit_exceeded",
        ),
    ),
)
def test_category_output_and_projection_caps_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    constant_name: str,
    limit: int,
    code: str,
) -> None:
    monkeypatch.setattr(altloc_module, constant_name, limit)
    _assert_error(SELECT_A.read_bytes(), "A", code)


def test_source_id_and_selected_token_caps_are_utf8_and_character_bounded() -> None:
    source = SELECT_A.read_bytes()
    too_long_source_id = "x" * (
        altloc_module.MAX_MMCIF_ALTLOC_SELECTION_SOURCE_ID_BYTES + 1
    )
    _assert_error(
        source,
        "A",
        "source_id_limit_exceeded",
        source_id=too_long_source_id,
    )

    long_id = b"x" * (altloc_module.MAX_MMCIF_ALTLOC_SELECTION_TOKEN_CHARS + 1)
    payload = _replace_once(source, b" CA A GLY ", b" CA " + long_id + b" GLY ")
    _assert_error(
        payload,
        long_id.decode("ascii"),
        "unsafe_cif_token",
    )

    oversized_altloc = b"x" * (
        altloc_module.MAX_MMCIF_ALTLOC_SELECTION_ALTLOC_ID_CHARS + 1
    )
    payload = _replace_once(
        source,
        b" CA A GLY ",
        b" CA " + oversized_altloc + b" GLY ",
    )
    _assert_error(
        payload,
        oversized_altloc.decode("ascii"),
        "invalid_altloc_id",
    )

    exact_utf8_source_id = "é" * (
        altloc_module.MAX_MMCIF_ALTLOC_SELECTION_SOURCE_ID_BYTES // 2
    )
    exact = parse_mmcif_altloc_selection(
        source,
        altloc_id="A",
        source_id=exact_utf8_source_id,
    )
    assert (
        exact.source_id_sha256
        == hashlib.sha256(exact_utf8_source_id.encode("utf-8")).hexdigest()
    )
    _assert_error(
        source,
        "A",
        "source_id_limit_exceeded",
        source_id=exact_utf8_source_id + "é",
    )
