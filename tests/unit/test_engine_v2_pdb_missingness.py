from __future__ import annotations

import pytest

import betelgeuze_engine_v2.molecular.pdb_mmcif as pdb_mmcif
from betelgeuze_engine_v2.molecular import (
    StructureParseError,
    analyze_molecular_preparation,
    deserialize_all_atom_system,
    parse_pdb,
    serialize_all_atom_system,
)


def _atom(
    serial: int,
    name: str,
    residue: str,
    chain: str,
    residue_number: int,
    *,
    insertion_code: str = " ",
    altloc: str = " ",
    x: float = 0.0,
) -> str:
    return (
        f"{'ATOM':<6}{serial:5d} {name:<4}{altloc:1}{residue:>3} {chain:1}"
        f"{residue_number:4d}{insertion_code:1}   {x:8.3f}{0.0:8.3f}{0.0:8.3f}"
        f"{1.0:6.2f}{10.0:6.2f}{'':10}{name[0]:>2}{'':2}"
    )


def _model(model_id: int) -> str:
    return f"MODEL     {model_id:4d}"


def _remark_header(number: int, text: str = "") -> str:
    return f"REMARK {number:3d} {text}".rstrip()


def _remark_models(number: int, start: int, end: int) -> str:
    return f"REMARK {number:3d}   MODELS {start}-{end}"


def _remark_465(
    residue: str,
    chain: str,
    residue_number: int,
    *,
    model_id: int | None = None,
    insertion_code: str = " ",
) -> str:
    line = [" "] * 80
    line[0:6] = "REMARK"
    line[7:10] = "465"
    if model_id is not None:
        line[11:14] = f"{model_id:3d}"
    line[15:18] = f"{residue:>3}"
    line[19] = chain or " "
    line[21:26] = f"{residue_number:5d}"
    line[26] = insertion_code
    return "".join(line).rstrip()


def _remark_470(
    residue: str,
    chain: str,
    residue_number: int,
    atoms: tuple[str, ...],
    *,
    model_id: int | None = None,
    insertion_code: str = " ",
) -> str:
    line = [" "] * 80
    line[0:6] = "REMARK"
    line[7:10] = "470"
    if model_id is not None:
        line[11:14] = f"{model_id:3d}"
    line[15:18] = f"{residue:>3}"
    line[20] = chain or " "
    line[21:25] = f"{residue_number:4d}"
    line[25] = insertion_code
    atom_text = " ".join(atoms)
    line[28 : 28 + len(atom_text)] = atom_text
    return "".join(line).rstrip()


def _remark_470_nmr(
    residue: str,
    chain: str,
    residue_number: int,
    atoms: tuple[str, ...],
    *,
    insertion_code: str = " ",
) -> str:
    line = [" "] * 80
    line[0:6] = "REMARK"
    line[7:10] = "470"
    line[15:18] = f"{residue:>3}"
    line[19] = chain or " "
    line[20:24] = f"{residue_number:4d}"
    line[24] = insertion_code
    atom_text = " ".join(atoms)
    line[27 : 27 + len(atom_text)] = atom_text
    return "".join(line).rstrip()


def _remark_465_table_header(*, nmr: bool = False) -> str:
    line = [" "] * 80
    line[0:6] = "REMARK"
    line[7:10] = "465"
    if not nmr:
        line[11:14] = "  M"
    line[15:18] = "RES"
    line[19] = "C"
    line[21:26] = "SSSEQ"
    line[26] = "I"
    return "".join(line).rstrip()


def _remark_470_table_header(*, nmr: bool = False) -> str:
    line = [" "] * 80
    line[0:6] = "REMARK"
    line[7:10] = "470"
    if nmr:
        line[15:18] = "RES"
        line[19] = "C"
        line[20:24] = "SSEQ"
        line[24] = "I"
        line[27:32] = "ATOMS"
    else:
        line[11:14] = "  M"
        line[15:18] = "RES"
        line[20] = "C"
        line[21:25] = "SSEQ"
        line[25] = "I"
        line[28:33] = "ATOMS"
    return "".join(line).rstrip()


def _pdb(*lines: str) -> bytes:
    return ("\n".join((*lines, "END")) + "\n").encode("ascii")


def _assert_code(payload: bytes, code: str) -> None:
    with pytest.raises(StructureParseError) as exc_info:
        parse_pdb(payload)
    assert exc_info.value.code == code


def test_pdb_remark_465_470_are_preserved_without_completion() -> None:
    source = _pdb(
        _remark_header(465),
        _remark_header(465, "MISSING RESIDUES"),
        _remark_465_table_header(),
        _remark_465("GLY", "A", 2),
        _remark_header(470, "MISSING ATOM"),
        _remark_470_table_header(),
        _remark_470("GLY", "A", 1, ("CB", "O")),
        _atom(1, "CA", "GLY", "A", 1),
    )
    result = parse_pdb(source)
    report = result.missingness_evidence

    assert report.source_reported_missing_residue_count == 1
    assert report.source_reported_missing_atom_count == 2
    assert report.missing_residue_claims[0].source_residue_id == "2"
    assert [claim.source_atom_name for claim in report.missing_atom_claims] == [
        "CB",
        "O",
    ]
    assert report.coordinate_scope == "deposited_coordinates"
    assert report.assembly_status == "not_supported_for_pdb"
    assert result.coverage.missingness_evidence_status == "present_fully_preserved"
    assert "source_reports_missing_residues" in result.coverage.blockers
    assert "source_reports_missing_atoms" in result.coverage.blockers
    assert "source_missingness_seqres_membership_not_assessed" in (
        result.coverage.blockers
    )
    assert result.system.atom_count == 1
    assert len(result.system.residues) == 1
    preparation = analyze_molecular_preparation(result.system)
    assert preparation.missing_atom_count is None
    assert preparation.missing_residue_count is None
    raw_records = result.system.metadata["pdb"]["source_missingness"][
        "raw_records"
    ]
    assert len(raw_records) == 7

    snapshot = serialize_all_atom_system(result.system)
    restored = deserialize_all_atom_system(snapshot)
    assert serialize_all_atom_system(restored) == snapshot
    assert restored.metadata["pdb"]["source_reported_missingness"] == (
        report.to_dict()
    )


def test_pdb_nmr_model_ranges_bind_without_expanding_claim_counts() -> None:
    source = _pdb(
        _remark_models(465, 1, 2),
        _remark_465_table_header(nmr=True),
        _remark_465("GLY", "A", 2),
        _remark_models(470, 1, 2),
        _remark_470_table_header(nmr=True),
        _remark_470_nmr("GLY", "A", 1, ("CB",)),
        _model(1),
        _atom(1, "CA", "GLY", "A", 1),
        "ENDMDL",
        _model(2),
        _atom(1, "CA", "GLY", "A", 1, x=0.1),
        "ENDMDL",
    )
    result = parse_pdb(source)
    report = result.missingness_evidence

    assert report.source_reported_missing_residue_count == 1
    assert report.source_reported_missing_atom_count == 1
    assert report.missing_residue_claims[0].source_model_id == "1-2"
    assert report.missing_atom_claims[0].source_model_id == "1-2"
    assert report.missing_atom_claims[0].raw_payload["target_model_scope"] == {
        "kind": "inclusive_model_range",
        "start": 1,
        "end": 2,
        "count": 2,
    }


def test_pdb_missingness_preserves_negative_sequence_and_insertion_code() -> None:
    result = parse_pdb(
        _pdb(
            _remark_465("GLY", "", -2, insertion_code="A"),
            _atom(1, "CA", "GLY", "A", 1),
        )
    )
    claim = result.missingness_evidence.missing_residue_claims[0]
    assert claim.source_chain_id == ""
    assert claim.source_residue_id == "-2"
    assert claim.source_insertion_code == "A"


@pytest.mark.parametrize(
    ("remarks", "coordinate", "code"),
    [
        (
            (_remark_465("GLY", "A", 1),),
            _atom(1, "CA", "GLY", "A", 1),
            "missing_residue_present_in_coordinates",
        ),
        (
            (_remark_470("GLY", "A", 2, ("CB",)),),
            _atom(1, "CA", "GLY", "A", 1),
            "missing_atom_residue_absent",
        ),
        (
            (_remark_470("GLY", "A", 1, ("CA",)),),
            _atom(1, "CA", "GLY", "A", 1),
            "declared_missing_atom_present",
        ),
    ],
)
def test_pdb_source_claims_conflicting_with_raw_coordinates_fail_closed(
    remarks: tuple[str, ...],
    coordinate: str,
    code: str,
) -> None:
    _assert_code(_pdb(*remarks, coordinate), code)


def test_pdb_range_conflict_reports_the_source_claim_line() -> None:
    source = _pdb(
        _remark_models(465, 1, 3),
        _remark_465("GLY", "A", 2),
        _model(1),
        _atom(1, "CA", "GLY", "A", 1),
        "ENDMDL",
        _model(2),
        _atom(1, "CA", "GLY", "A", 1),
        _atom(2, "CA", "GLY", "A", 2),
        "ENDMDL",
        _model(3),
        _atom(1, "CA", "GLY", "A", 1),
        "ENDMDL",
    )
    with pytest.raises(StructureParseError) as exc_info:
        parse_pdb(source)
    assert exc_info.value.code == "missing_residue_present_in_coordinates"
    assert exc_info.value.line_number == 2


def test_pdb_missingness_duplicate_continuation_and_layout_failures_are_stable() -> None:
    duplicate = _pdb(
        _remark_465("GLY", "A", 2),
        _remark_465("GLY", "A", 2),
        _atom(1, "CA", "GLY", "A", 1),
    )
    _assert_code(duplicate, "duplicate_missingness_record")

    continuation = [" "] * 80
    continuation[0:6] = "REMARK"
    continuation[7:10] = "470"
    continuation[28:30] = "CB"
    _assert_code(
        _pdb("".join(continuation).rstrip(), _atom(1, "CA", "GLY", "A", 1)),
        "unsupported_missing_atom_continuation",
    )

    malformed = list(_remark_465("GLY", "A", 2).ljust(80))
    malformed[20] = "X"
    _assert_code(
        _pdb("".join(malformed).rstrip(), _atom(1, "CA", "GLY", "A", 1)),
        "invalid_remark_465_layout",
    )

    invalid_residue_465 = list(_remark_465("GLY", "A", 2).ljust(80))
    invalid_residue_465[21:26] = " ABCD"
    _assert_code(
        _pdb(
            "".join(invalid_residue_465).rstrip(),
            _atom(1, "CA", "GLY", "A", 1),
        ),
        "missing_residue_identity",
    )

    invalid_residue_470 = list(
        _remark_470("GLY", "A", 1, ("CB",)).ljust(80)
    )
    invalid_residue_470[21:25] = "ABCD"
    _assert_code(
        _pdb(
            "".join(invalid_residue_470).rstrip(),
            _atom(1, "CA", "GLY", "A", 1),
        ),
        "missing_atom_identity",
    )

    multiply_malformed_465 = list(_remark_465("GLY", "A", 2).ljust(80))
    multiply_malformed_465[14] = "X"
    multiply_malformed_465[18] = "X"
    multiply_malformed_465[21:26] = "ABCDE"
    _assert_code(
        _pdb(
            "".join(multiply_malformed_465).rstrip(),
            _atom(1, "CA", "GLY", "A", 1),
        ),
        "invalid_remark_465_layout",
    )

    multiply_malformed_470 = list(
        _remark_470("GLY", "A", 1, ("CB",)).ljust(80)
    )
    multiply_malformed_470[14] = "X"
    multiply_malformed_470[18] = "X"
    multiply_malformed_470[21:25] = "ABCD"
    _assert_code(
        _pdb(
            "".join(multiply_malformed_470).rstrip(),
            _atom(1, "CA", "GLY", "A", 1),
        ),
        "invalid_remark_470_layout",
    )

    missing_name_465 = list(_remark_465("GLY", "A", 2).ljust(80))
    missing_name_465[15:18] = "   "
    _assert_code(
        _pdb(
            "".join(missing_name_465).rstrip(),
            _atom(1, "CA", "GLY", "A", 1),
        ),
        "missing_residue_identity",
    )

    missing_name_470 = list(
        _remark_470("GLY", "A", 1, ("CB",)).ljust(80)
    )
    missing_name_470[15:18] = "   "
    _assert_code(
        _pdb(
            "".join(missing_name_470).rstrip(),
            _atom(1, "CA", "GLY", "A", 1),
        ),
        "missing_atom_identity",
    )

    model_only_465 = [" "] * 80
    model_only_465[0:6] = "REMARK"
    model_only_465[7:10] = "465"
    model_only_465[11:14] = "  1"
    _assert_code(
        _pdb(
            "".join(model_only_465).rstrip(),
            _model(1),
            _atom(1, "CA", "GLY", "A", 1),
            "ENDMDL",
        ),
        "missing_residue_identity",
    )

    model_only_470 = [" "] * 80
    model_only_470[0:6] = "REMARK"
    model_only_470[7:10] = "470"
    model_only_470[11:14] = "  1"
    _assert_code(
        _pdb(
            "".join(model_only_470).rstrip(),
            _model(1),
            _atom(1, "CA", "GLY", "A", 1),
            "ENDMDL",
        ),
        "missing_atom_identity",
    )


def test_pdb_res_component_id_is_not_mistaken_for_a_table_header() -> None:
    result = parse_pdb(
        _pdb(
            _remark_465("RES", "A", 2),
            _remark_470("RES", "A", 1, ("CB",)),
            _atom(1, "CA", "RES", "A", 1),
        )
    )
    assert result.missingness_evidence.missing_residue_claims[
        0
    ].source_residue_name == "RES"
    assert result.missingness_evidence.missing_atom_claims[
        0
    ].source_residue_name == "RES"


def test_pdb_missingness_model_scope_failures_are_stable() -> None:
    out_of_range = _pdb(
        _remark_models(465, 1, 3),
        _remark_465("GLY", "A", 2),
        _model(1),
        _atom(1, "CA", "GLY", "A", 1),
        "ENDMDL",
        _model(2),
        _atom(1, "CA", "GLY", "A", 1, x=0.1),
        "ENDMDL",
    )
    _assert_code(out_of_range, "missingness_model_out_of_range")

    mixed = _pdb(
        _remark_models(465, 1, 2),
        _remark_465("GLY", "A", 2, model_id=1),
        _model(1),
        _atom(1, "CA", "GLY", "A", 1),
        "ENDMDL",
        _model(2),
        _atom(1, "CA", "GLY", "A", 1, x=0.1),
        "ENDMDL",
    )
    _assert_code(mixed, "mixed_missingness_model_scope")

    invalid_row_model = list(_remark_465("GLY", "A", 2, model_id=1).ljust(80))
    invalid_row_model[11:14] = "ABC"
    malformed_model = _pdb(
        "".join(invalid_row_model).rstrip(),
        _model(1),
        _atom(1, "CA", "GLY", "A", 1),
        "ENDMDL",
        _model(2),
        _atom(1, "CA", "GLY", "A", 1, x=0.1),
        "ENDMDL",
    )
    _assert_code(malformed_model, "invalid_missingness_model")

    noncanonical_spacing = _pdb(
        "REMARK 465 MODELS 1-2",
        _remark_465("GLY", "A", 2),
        _model(1),
        _atom(1, "CA", "GLY", "A", 1),
        "ENDMDL",
        _model(2),
        _atom(1, "CA", "GLY", "A", 1, x=0.1),
        "ENDMDL",
    )
    _assert_code(noncanonical_spacing, "invalid_missingness_model_range")


def test_pdb_per_row_model_bindings_are_preserved() -> None:
    result = parse_pdb(
        _pdb(
            _remark_465("GLY", "A", 2, model_id=1),
            _remark_470("GLY", "A", 1, ("CB",), model_id=2),
            _model(1),
            _atom(1, "CA", "GLY", "A", 1),
            "ENDMDL",
            _model(2),
            _atom(1, "CA", "GLY", "A", 1, x=0.1),
            "ENDMDL",
        )
    )
    residue_claim = result.missingness_evidence.missing_residue_claims[0]
    atom_claim = result.missingness_evidence.missing_atom_claims[0]
    assert residue_claim.source_model_id == "1"
    assert residue_claim.raw_payload["target_model_scope"] == {
        "kind": "explicit_model_ids",
        "model_ids": [1],
        "count": 1,
    }
    assert atom_claim.source_model_id == "2"
    assert atom_claim.raw_payload["target_model_scope"] == {
        "kind": "explicit_model_ids",
        "model_ids": [2],
        "count": 1,
    }


def test_pdb_large_nmr_range_uses_compact_model_scope() -> None:
    model_count = 4_100
    lines = [
        _remark_models(465, 1, model_count),
        _remark_465("GLY", "A", 2),
    ]
    for model_id in range(1, model_count + 1):
        lines.extend(
            (
                _model(model_id),
                _atom(1, "CA", "GLY", "A", 1),
                "ENDMDL",
            )
        )
    result = parse_pdb(_pdb(*lines))
    scope = result.missingness_evidence.missing_residue_claims[0].raw_payload[
        "target_model_scope"
    ]
    assert scope == {
        "kind": "inclusive_model_range",
        "start": 1,
        "end": model_count,
        "count": model_count,
    }


def test_pdb_claim_limits_run_before_claim_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pdb_mmcif, "MAX_MISSING_RESIDUE_CLAIMS", 0)

    def forbidden_claim(*args: object, **kwargs: object) -> object:
        pytest.fail("claim limit must run before claim materialization")

    monkeypatch.setattr(
        pdb_mmcif,
        "SourceReportedMissingResidueClaim",
        forbidden_claim,
    )
    _assert_code(
        _pdb(_remark_465("GLY", "A", 2), _atom(1, "CA", "GLY", "A", 1)),
        "missing_residue_evidence_limit_exceeded",
    )


def test_pdb_combined_claim_limit_is_stable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pdb_mmcif, "MAX_TOTAL_MISSINGNESS_CLAIMS", 1)
    _assert_code(
        _pdb(
            _remark_465("GLY", "A", 2),
            _remark_470("GLY", "A", 1, ("CB",)),
            _atom(1, "CA", "GLY", "A", 1),
        ),
        "combined_missingness_evidence_limit_exceeded",
    )


def test_pdb_metadata_projection_claim_limit_is_incremental(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pdb_mmcif,
        "_MAX_PDB_MISSINGNESS_PROJECTED_CLAIMS",
        1,
    )
    _assert_code(
        _pdb(
            _remark_470("GLY", "A", 1, ("CB", "CG")),
            _atom(1, "CA", "GLY", "A", 1),
        ),
        "missingness_metadata_projection_limit_exceeded",
    )


def test_pdb_missingness_contract_failures_are_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid_report(*args: object, **kwargs: object) -> object:
        raise ValueError("synthetic contract failure")

    monkeypatch.setattr(
        pdb_mmcif,
        "build_source_reported_missingness_report",
        invalid_report,
    )
    _assert_code(
        _pdb(_atom(1, "CA", "GLY", "A", 1)),
        "invalid_missingness_evidence",
    )


def test_pdb_claim_constructor_failures_are_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid_claim(*args: object, **kwargs: object) -> object:
        raise ValueError("synthetic claim failure")

    monkeypatch.setattr(
        pdb_mmcif,
        "SourceReportedMissingAtomClaim",
        invalid_claim,
    )
    _assert_code(
        _pdb(
            _remark_470("GLY", "A", 1, ("CB",)),
            _atom(1, "CA", "GLY", "A", 1),
        ),
        "invalid_missingness_evidence",
    )


def test_pdb_missingness_must_precede_coordinates_and_respects_line_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    misplaced = _pdb(
        _atom(1, "CA", "GLY", "A", 1),
        _remark_465("GLY", "A", 2),
    )
    _assert_code(misplaced, "misplaced_missingness_remark")

    monkeypatch.setattr(pdb_mmcif, "_MAX_PDB_MISSINGNESS_REMARK_LINES", 0)
    _assert_code(
        _pdb(_remark_header(465), _atom(1, "CA", "GLY", "A", 1)),
        "missingness_remark_line_limit_exceeded",
    )


def test_pdb_altloc_selection_does_not_turn_discarded_atoms_into_missing_atoms() -> None:
    source = _pdb(
        _remark_470("GLY", "A", 1, ("CB",)),
        _atom(1, "CA", "GLY", "A", 1, altloc="A"),
        _atom(2, "CB", "GLY", "A", 1, altloc="B"),
    )
    _assert_code(source, "declared_missing_atom_present")


def test_pdb_header_only_evidence_is_preserved_but_never_means_complete() -> None:
    result = parse_pdb(
        _pdb(
            _remark_header(465),
            _remark_header(465, "MISSING RESIDUES"),
            _atom(1, "CA", "GLY", "A", 1),
        )
    )
    assert result.coverage.missingness_evidence_status == "present_fully_preserved"
    assert result.missingness_evidence.source_reported_missing_residue_count == 0
    assert result.missingness_evidence.source_reported_missing_atom_count == 0
    assert "missing_atom_and_residue_completion_not_assessed" in (
        result.coverage.blockers
    )
