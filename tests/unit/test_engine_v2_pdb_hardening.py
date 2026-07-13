from __future__ import annotations

import pytest

import betelgeuze_engine_v2.molecular.pdb_mmcif as pdb_mmcif
from betelgeuze_engine_v2.molecular import StructureParseError, parse_pdb


def _atom(
    serial: int,
    *,
    record: str = "ATOM",
    name: str = "CA",
    residue: str = "GLY",
    chain: str = "A",
    residue_number: int = 1,
    insertion_code: str = " ",
    x: float = 0.0,
    element: str = "C",
    charge: str = "",
    segment_id: str = "",
) -> str:
    return (
        f"{record:<6}{serial:5d} {name:<4} {residue:>3} {chain:1}"
        f"{residue_number:4d}{insertion_code:1}   {x:8.3f}{0.0:8.3f}{0.0:8.3f}"
        f"{1.0:6.2f}{20.0:6.2f}{'':6}{segment_id:<4}{element:>2}{charge:>2}"
    )


def _ter(
    serial: int,
    *,
    residue: str = "GLY",
    chain: str = "A",
    residue_number: int = 1,
    insertion_code: str = " ",
) -> str:
    return (
        f"{'TER':<6}{serial:5d}{'':6}{residue:>3} {chain:1}"
        f"{residue_number:4d}{insertion_code:1}"
    )


def _conect(source: int, *targets: int) -> str:
    return f"CONECT{source:5d}" + "".join(f"{target:5d}" for target in targets)


def _cryst1(
    a: float = 20.0,
    b: float = 21.0,
    c: float = 22.0,
    alpha: float = 90.0,
    beta: float = 90.0,
    gamma: float = 90.0,
    space_group: str = "P 1",
) -> str:
    return (
        f"CRYST1{a:9.3f}{b:9.3f}{c:9.3f}{alpha:7.2f}{beta:7.2f}{gamma:7.2f} "
        f"{space_group:<11}{1:4d}"
    )


def _pdb(*lines: str) -> bytes:
    return ("\n".join(lines) + "\n").encode("utf-8")


def _assert_parse_code(payload: bytes, code: str) -> None:
    with pytest.raises(StructureParseError) as exc_info:
        parse_pdb(payload)
    assert exc_info.value.source_format == "pdb"
    assert exc_info.value.code == code


def test_contradictory_bidirectional_conect_multiplicities_fail_closed() -> None:
    payload = _pdb(
        _atom(1),
        _atom(2, name="CB", x=1.4),
        _conect(1, 2, 2),
        _conect(2, 1),
        "END",
    )
    _assert_parse_code(payload, "contradictory_conect_multiplicity")


def test_valid_conect_multiplicity_still_requires_chemical_context() -> None:
    payload = _pdb(
        _atom(1),
        _atom(2, name="CB", x=1.4),
        _conect(1, 2, 2),
        _conect(2, 1, 1),
        "END",
    )
    _assert_parse_code(payload, "unsupported_contextual_conect_semantics")


@pytest.mark.parametrize(
    "atoms",
    (
        (
            _atom(1),
            _atom(2, name="CB", x=1.4),
        ),
        (
            _atom(1, record="HETATM", name="C1", residue="LIG"),
            _atom(2, record="HETATM", name="C2", residue="LIG", x=1.4),
        ),
        (
            _atom(1, name="SG", residue="CYS", residue_number=1, element="S"),
            _atom(
                2,
                name="SG",
                residue="CYS",
                residue_number=2,
                x=2.0,
                element="S",
            ),
        ),
        (
            _atom(
                1,
                record="HETATM",
                name="ZN",
                residue="ZN",
                residue_number=101,
                element="Zn",
                charge="2+",
            ),
            _atom(
                2,
                name="ND1",
                residue="HIS",
                residue_number=10,
                x=2.1,
                element="N",
            ),
        ),
        (
            _atom(1, name="ZN", residue="LIG", element="Zn"),
            _atom(2, name="N1", residue="LIG", x=2.1, element="N"),
        ),
    ),
)
def test_contextual_conect_semantics_fail_closed(
    atoms: tuple[str, str],
) -> None:
    payload = _pdb(
        *atoms,
        _conect(1, 2),
        _conect(2, 1),
        "END",
    )

    with pytest.raises(StructureParseError) as exc_info:
        parse_pdb(payload)
    assert exc_info.value.source_format == "pdb"
    assert exc_info.value.code == "unsupported_contextual_conect_semantics"
    assert exc_info.value.line_number is None


def test_all_conect_references_are_validated_before_context_rejection() -> None:
    payload = _pdb(
        _atom(1),
        _atom(2, name="CB", x=1.4),
        _conect(1, 2),
        _conect(2, 1),
        _conect(2, 9),
        "END",
    )
    _assert_parse_code(payload, "conect_atom_out_of_range")


def test_ter_identity_and_matching_model_placement_are_preserved() -> None:
    result = parse_pdb(
        _pdb(
            "MODEL        1",
            _atom(1),
            _ter(2),
            "ENDMDL",
            "MODEL        2",
            _atom(1, x=0.2),
            _ter(2),
            "ENDMDL",
            "END",
        )
    )
    pdb_metadata = result.system.metadata["pdb"]
    assert pdb_metadata["ter_count"] == 2
    assert [entry["model_id"] for entry in pdb_metadata["ter_records_by_model"]] == [1, 2]
    for entry in pdb_metadata["ter_records_by_model"]:
        assert entry["records"][0]["serial"] == 2
        assert entry["records"][0]["after_atom_index"] == 0
        assert entry["records"][0]["after_atom_serial"] == 1
        assert entry["records"][0]["residue_name"] == "GLY"
        assert entry["records"][0]["chain_id"] == "A"


@pytest.mark.parametrize(
    ("ter_line", "code"),
    [
        (_ter(3), "ter_identity_mismatch"),
        (_ter(2, residue="ALA"), "ter_identity_mismatch"),
        (_ter(2, chain="B"), "ter_identity_mismatch"),
        (_ter(2, residue_number=2), "ter_identity_mismatch"),
        ("TER", "invalid_ter"),
        (_ter(2) + "X", "invalid_ter"),
    ],
)
def test_ter_requires_exact_fixed_column_identity(ter_line: str, code: str) -> None:
    _assert_parse_code(_pdb(_atom(1), ter_line, "END"), code)


def test_ter_outside_model_fails_closed() -> None:
    _assert_parse_code(
        _pdb("MODEL        1", _atom(1), "ENDMDL", _ter(2), "END"),
        "invalid_ter",
    )


def test_models_must_have_identical_ter_layouts() -> None:
    _assert_parse_code(
        _pdb(
            "MODEL        1",
            _atom(1),
            _ter(2),
            "ENDMDL",
            "MODEL        2",
            _atom(1, x=0.2),
            "ENDMDL",
            "END",
        ),
        "model_ter_layout_mismatch",
    )


def test_dummy_cryst1_placeholder_is_not_promoted_to_periodic_cell() -> None:
    _assert_parse_code(
        _pdb(_cryst1(a=1.0, b=1.0, c=1.0), _atom(1), "END"),
        "dummy_cryst1",
    )


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (_pdb(_atom(1)), "missing_end"),
        (_pdb("MODEL        1X", _atom(1), "ENDMDL", "END"), "invalid_model_line"),
        (_pdb("MODEL        1", _atom(1), "ENDMDL X", "END"), "invalid_endmdl_line"),
        (_pdb(_atom(1), "END   X"), "invalid_end_line"),
    ],
)
def test_control_records_have_strict_width_and_trailing_content(payload: bytes, code: str) -> None:
    _assert_parse_code(payload, code)


@pytest.mark.parametrize("reserved_index", [11, 20, 27, 28, 29])
def test_atom_reserved_columns_must_be_blank(reserved_index: int) -> None:
    malformed = list(_atom(1))
    malformed[reserved_index] = "X"
    _assert_parse_code(_pdb("".join(malformed), "END"), "invalid_atom_reserved_columns")


def test_blank_formal_charge_is_explicitly_unknown_and_blocks_coverage() -> None:
    result = parse_pdb(_pdb(_atom(1), "END"))
    atom = result.system.atoms[0]
    assert atom.formal_charge == 0
    assert atom.formal_charge_known is False
    assert atom.metadata["formal_charge_known"] is False
    assert atom.metadata["formal_charge_source"] == "missing_in_pdb"
    assert atom.metadata["formal_charge_interpretation"] == "placeholder_zero_unknown"
    assert result.coverage.unknown_formal_charge_count == 1
    assert "formal_charge_unknown_for_some_atoms" in result.coverage.blockers


def test_explicit_charge_is_known_and_hetero_entity_type_remains_unresolved() -> None:
    result = parse_pdb(_pdb(_atom(7, record="HETATM", name="ZN", residue="ZN", element="Zn", charge="2+"), "END"))
    atom = result.system.atoms[0]
    residue = result.system.residues[0]
    assert atom.formal_charge == 2
    assert atom.formal_charge_known is True
    assert atom.metadata["formal_charge_known"] is True
    assert result.coverage.unknown_formal_charge_count == 0
    assert "formal_charge_unknown_for_some_atoms" not in result.coverage.blockers
    assert residue.hetero is True
    assert residue.entity_type == "unknown"
    assert residue.metadata["entity_type_basis"] == "unresolved_from_hetero_record"


def test_valid_utf8_multibyte_text_is_rejected_for_fixed_column_pdb() -> None:
    payload = _pdb(_atom(1), "END").replace(b"GLY", "GLÝ".encode("utf-8"))
    _assert_parse_code(payload, "invalid_ascii")


def test_conflicting_pdb_segment_ids_cannot_merge_into_one_residue() -> None:
    _assert_parse_code(
        _pdb(
            _atom(1, name="N", element="N", segment_id="S1"),
            _atom(2, name="CA", x=1.4, segment_id="S2"),
            "END",
        ),
        "conflicting_residue_identity",
    )


def test_pdb_resource_caps_fail_before_unbounded_atom_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _pdb(_atom(1), "END")
    monkeypatch.setattr(pdb_mmcif, "_MAX_PDB_INPUT_BYTES", len(payload) - 1)
    _assert_parse_code(payload, "input_too_large")

    monkeypatch.setattr(pdb_mmcif, "_MAX_PDB_INPUT_BYTES", len(payload) * 10)
    monkeypatch.setattr(pdb_mmcif, "_MAX_PDB_LINE_COUNT", 2)
    _assert_parse_code(payload, "too_many_lines")

    monkeypatch.setattr(pdb_mmcif, "_MAX_PDB_LINE_COUNT", 100)
    monkeypatch.setattr(pdb_mmcif, "_MAX_PDB_ATOM_ROWS", 1)
    _assert_parse_code(
        _pdb(
            _atom(1, name="N", element="N"),
            _atom(2, name="CA", x=1.0),
            "END",
        ),
        "too_many_atom_rows",
    )
