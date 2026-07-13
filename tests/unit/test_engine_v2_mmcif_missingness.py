from __future__ import annotations

import builtins
import inspect

import pytest

import betelgeuze_engine_v2.molecular.pdb_mmcif as pdb_mmcif
from betelgeuze_engine_v2.molecular import (
    StructureParseError,
    analyze_molecular_preparation,
    attached_canonical_topology_sha256_matches,
    deserialize_all_atom_system,
    parse_mmcif,
    serialize_all_atom_system,
)


ATOM_HEADERS = (
    "_atom_site.group_PDB",
    "_atom_site.id",
    "_atom_site.type_symbol",
    "_atom_site.label_atom_id",
    "_atom_site.label_comp_id",
    "_atom_site.label_asym_id",
    "_atom_site.label_seq_id",
    "_atom_site.Cartn_x",
    "_atom_site.Cartn_y",
    "_atom_site.Cartn_z",
    "_atom_site.pdbx_PDB_model_num",
)

RESIDUE_HEADERS = (
    "_pdbx_unobs_or_zero_occ_residues.id",
    "_pdbx_unobs_or_zero_occ_residues.polymer_flag",
    "_pdbx_unobs_or_zero_occ_residues.occupancy_flag",
    "_pdbx_unobs_or_zero_occ_residues.PDB_model_num",
    "_pdbx_unobs_or_zero_occ_residues.auth_asym_id",
    "_pdbx_unobs_or_zero_occ_residues.auth_comp_id",
    "_pdbx_unobs_or_zero_occ_residues.auth_seq_id",
    "_pdbx_unobs_or_zero_occ_residues.PDB_ins_code",
    "_pdbx_unobs_or_zero_occ_residues.label_asym_id",
    "_pdbx_unobs_or_zero_occ_residues.label_comp_id",
    "_pdbx_unobs_or_zero_occ_residues.label_seq_id",
)

ATOM_MISSING_HEADERS = (
    "_pdbx_unobs_or_zero_occ_atoms.id",
    "_pdbx_unobs_or_zero_occ_atoms.polymer_flag",
    "_pdbx_unobs_or_zero_occ_atoms.occupancy_flag",
    "_pdbx_unobs_or_zero_occ_atoms.PDB_model_num",
    "_pdbx_unobs_or_zero_occ_atoms.auth_asym_id",
    "_pdbx_unobs_or_zero_occ_atoms.auth_comp_id",
    "_pdbx_unobs_or_zero_occ_atoms.auth_seq_id",
    "_pdbx_unobs_or_zero_occ_atoms.PDB_ins_code",
    "_pdbx_unobs_or_zero_occ_atoms.auth_atom_id",
    "_pdbx_unobs_or_zero_occ_atoms.label_alt_id",
    "_pdbx_unobs_or_zero_occ_atoms.label_asym_id",
    "_pdbx_unobs_or_zero_occ_atoms.label_comp_id",
    "_pdbx_unobs_or_zero_occ_atoms.label_seq_id",
    "_pdbx_unobs_or_zero_occ_atoms.label_atom_id",
)


def _loop(headers: tuple[str, ...], rows: tuple[str, ...]) -> str:
    return "\n".join(("loop_", *headers, *rows, "#"))


def _document(
    *sections: str,
    atom_headers: tuple[str, ...] = ATOM_HEADERS,
    atom_rows: tuple[str, ...] = ("ATOM 1 C CA GLY A 1 0 0 0 1",),
) -> bytes:
    atom_site = _loop(atom_headers, atom_rows)
    return ("\n".join(("data_missingness", "#", *sections, atom_site)) + "\n").encode(
        "ascii"
    )


def _residue_row(
    *,
    source_id: int = 1,
    occupancy_flag: int = 1,
    model_id: int = 1,
    polymer_flag: str = "Y",
    insertion_code: str = "?",
    labels: tuple[str, str, str] = ("A", "GLY", "2"),
) -> str:
    return " ".join(
        (
            str(source_id),
            polymer_flag,
            str(occupancy_flag),
            str(model_id),
            "X",
            "GLY",
            "2",
            insertion_code,
            *labels,
        )
    )


def _atom_missing_row(
    *,
    source_id: int = 1,
    occupancy_flag: int = 1,
    model_id: int = 1,
    polymer_flag: str = "Y",
    insertion_code: str = "?",
    label_alt_id: str = "?",
) -> str:
    return " ".join(
        (
            str(source_id),
            polymer_flag,
            str(occupancy_flag),
            str(model_id),
            "X",
            "GLY",
            "2",
            insertion_code,
            "CB",
            label_alt_id,
            "A",
            "GLY",
            "2",
            "CB",
        )
    )


def _assert_code(payload: bytes, code: str) -> None:
    with pytest.raises(StructureParseError) as exc_info:
        parse_mmcif(payload)
    assert exc_info.value.code == code


def test_mmcif_unobserved_rows_are_topology_bound_preserve_only_claims() -> None:
    result = parse_mmcif(
        _document(
            _loop(RESIDUE_HEADERS, (_residue_row(),)),
            _loop(ATOM_MISSING_HEADERS, (_atom_missing_row(),)),
        )
    )
    report = result.missingness_evidence

    assert report.source_reported_missing_residue_count == 1
    assert report.source_reported_missing_atom_count == 1
    residue_claim = report.missing_residue_claims[0]
    atom_claim = report.missing_atom_claims[0]
    assert (residue_claim.source_chain_id, residue_claim.source_residue_id) == (
        "A",
        "2",
    )
    assert atom_claim.source_atom_name == "CB"
    assert residue_claim.raw_payload["identity_basis"] == "label"
    assert residue_claim.raw_payload["tokens"][
        "_pdbx_unobs_or_zero_occ_residues.pdb_ins_code"
    ] == {"value": "?", "quoted": False, "multiline": False}
    assert report.canonical_topology_sha256 == result.coverage.canonical_topology_sha256
    assert result.coverage.missingness_evidence_status == "present_fully_preserved"
    assert result.coverage.source_reported_missing_residue_claim_count == 1
    assert result.coverage.source_reported_missing_atom_claim_count == 1
    assert "source_reports_missing_residues" in result.coverage.blockers
    assert "source_reports_missing_atoms" in result.coverage.blockers
    assert "missing_atom_and_residue_completion_not_assessed" in (
        result.coverage.blockers
    )
    assert result.system.provenance.preparation_ready is False
    assert result.system.provenance.claim_safe is False
    preparation = analyze_molecular_preparation(result.system)
    assert preparation.missing_atom_count is None
    assert preparation.missing_residue_count is None
    assert attached_canonical_topology_sha256_matches(result.system)

    snapshot = serialize_all_atom_system(result.system)
    restored = deserialize_all_atom_system(snapshot)
    assert serialize_all_atom_system(restored) == snapshot
    assert restored.metadata["mmcif"]["source_reported_missingness"] == (
        report.to_dict()
    )
    with pytest.raises(TypeError):
        restored.metadata["mmcif"]["source_reported_missingness"]["policy_id"] = (
            "forged"  # type: ignore[index]
        )


def test_zero_occupancy_rows_are_preserved_but_not_mislabeled_as_missing() -> None:
    atom_headers = ATOM_HEADERS + ("_atom_site.occupancy",)
    atom_rows = ("ATOM 1 C CB GLY A 2 0 0 0 1 0",)
    result = parse_mmcif(
        _document(
            _loop(
                RESIDUE_HEADERS,
                (_residue_row(occupancy_flag=0),),
            ),
            _loop(
                ATOM_MISSING_HEADERS,
                (_atom_missing_row(occupancy_flag=0),),
            ),
            atom_headers=atom_headers,
            atom_rows=atom_rows,
        )
    )
    report = result.missingness_evidence
    summary = result.system.metadata["mmcif"]["source_missingness"]

    assert report.source_reported_missing_residue_count == 0
    assert report.source_reported_missing_atom_count == 0
    assert summary["zero_occupancy_residue_row_count"] == 1
    assert summary["zero_occupancy_atom_row_count"] == 1
    assert "source_reports_zero_occupancy_residues" in result.coverage.blockers
    assert "source_reports_zero_occupancy_atoms" in result.coverage.blockers
    assert "source_reports_missing_residues" not in result.coverage.blockers
    assert "source_reports_missing_atoms" not in result.coverage.blockers
    assert result.coverage.missingness_evidence_status == "present_fully_preserved"


def test_duplicate_zero_occupancy_residue_checks_remain_linear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row_count = 48
    residue_rows = tuple(
        _residue_row(
            source_id=index,
            occupancy_flag=0,
            labels=("A", "GLY", "1"),
        )
        for index in range(1, row_count + 1)
    )
    atom_headers = ATOM_HEADERS + ("_atom_site.occupancy",)
    atom_rows = tuple(
        f"ATOM {index} C C{index} GLY A 1 {index}.0 0 0 1 0"
        for index in range(1, row_count + 1)
    )
    payload = _document(
        _loop(RESIDUE_HEADERS, residue_rows),
        atom_headers=atom_headers,
        atom_rows=atom_rows,
    )
    consumed_items = 0

    def counting_any(values) -> bool:
        nonlocal consumed_items

        frame = inspect.currentframe()
        caller = None if frame is None else frame.f_back
        is_missingness_scan = (
            caller is not None
            and caller.f_code.co_name == "_parse_mmcif_source_missingness"
        )
        del caller
        del frame
        if not is_missingness_scan:
            return builtins.any(values)
        for value in values:
            consumed_items += 1
            if value:
                return True
        return False

    monkeypatch.setattr(pdb_mmcif, "any", counting_any, raising=False)
    result = parse_mmcif(payload)
    report = result.missingness_evidence
    summary = result.system.metadata["mmcif"]["source_missingness"]

    assert consumed_items <= 8 * row_count
    assert report.source_reported_missing_residue_count == 0
    assert report.source_reported_missing_atom_count == 0
    assert summary["residue_row_count"] == row_count
    assert summary["zero_occupancy_residue_row_count"] == row_count
    assert summary["unobserved_residue_claim_count"] == 0
    assert result.coverage.missingness_evidence_status == "present_fully_preserved"
    assert result.coverage.blockers.count("source_reports_zero_occupancy_residues") == 1
    assert "duplicate_missing_residue_claims_preserved" not in (
        result.coverage.blockers
    )


@pytest.mark.parametrize(
    ("section", "atom_rows", "code"),
    [
        (
            _loop(
                RESIDUE_HEADERS,
                (_residue_row(labels=("A", "GLY", "+1")),),
            ),
            ("ATOM 1 C CA GLY A 1 0 0 0 1 1",),
            "missing_residue_present_in_coordinates",
        ),
        (
            _loop(ATOM_MISSING_HEADERS, (_atom_missing_row(),)),
            ("ATOM 1 C CB GLY A 2 0 0 0 1 1",),
            "declared_missing_atom_present",
        ),
        (
            _loop(
                RESIDUE_HEADERS,
                (_residue_row(occupancy_flag=0),),
            ),
            ("ATOM 1 C CA GLY A 2 0 0 0 1 1",),
            "zero_occupancy_residue_value_conflict",
        ),
        (
            _loop(
                ATOM_MISSING_HEADERS,
                (_atom_missing_row(occupancy_flag=0),),
            ),
            ("ATOM 1 C CB GLY A 2 0 0 0 1 1",),
            "zero_occupancy_atom_value_conflict",
        ),
    ],
)
def test_mmcif_source_missingness_coordinate_contradictions_fail_closed(
    section: str,
    atom_rows: tuple[str, ...],
    code: str,
) -> None:
    _assert_code(
        _document(
            section,
            atom_headers=ATOM_HEADERS + ("_atom_site.occupancy",),
            atom_rows=atom_rows,
        ),
        code,
    )


def test_zero_occupancy_label_sequence_pointer_is_canonicalized() -> None:
    result = parse_mmcif(
        _document(
            _loop(
                RESIDUE_HEADERS,
                (
                    _residue_row(
                        occupancy_flag=0,
                        labels=("A", "GLY", "01"),
                    ),
                ),
            ),
            atom_headers=ATOM_HEADERS + ("_atom_site.occupancy",),
            atom_rows=("ATOM 1 C CA GLY A 1 0 0 0 1 0",),
        )
    )
    assert result.coverage.missingness_evidence_status == "present_fully_preserved"
    assert (
        result.system.metadata["mmcif"]["source_missingness"][
            "zero_occupancy_residue_row_count"
        ]
        == 1
    )


def test_quoted_missing_marker_remains_a_literal_insertion_code() -> None:
    result = parse_mmcif(
        _document(
            _loop(
                RESIDUE_HEADERS,
                (_residue_row(insertion_code="'.'"),),
            )
        )
    )
    claim = result.missingness_evidence.missing_residue_claims[0]
    assert claim.source_insertion_code == "."
    token = claim.raw_payload["tokens"]["_pdbx_unobs_or_zero_occ_residues.pdb_ins_code"]
    assert token == {"value": ".", "quoted": True, "multiline": False}


def test_extension_and_partial_label_identity_are_preserved_with_blockers() -> None:
    headers = RESIDUE_HEADERS + ("_pdbx_unobs_or_zero_occ_residues.local_extension",)
    row = _residue_row(labels=("A", "?", "?")) + " note"
    result = parse_mmcif(_document(_loop(headers, (row,))))

    assert result.coverage.missingness_evidence_status == (
        "present_partially_interpreted"
    )
    assert "source_missingness_evidence_partially_interpreted" in (
        result.coverage.blockers
    )
    assert "partial_label_identity_in_missingness_evidence" in (
        result.coverage.blockers
    )
    assert "missingness_extension_items_uninterpreted" in result.coverage.blockers
    claim = result.missingness_evidence.missing_residue_claims[0]
    assert claim.source_chain_id == "X"
    assert (
        claim.raw_payload["tokens"]["_pdbx_unobs_or_zero_occ_residues.local_extension"][
            "value"
        ]
        == "note"
    )


def test_atom_label_identity_is_assessed_as_a_four_field_namespace() -> None:
    headers = tuple(
        header
        for header in ATOM_MISSING_HEADERS
        if not header.endswith(("label_asym_id", "label_comp_id", "label_seq_id"))
    )
    values = _atom_missing_row().split()
    row = " ".join((*values[:10], values[13]))
    result = parse_mmcif(_document(_loop(headers, (row,))))

    assert result.coverage.missingness_evidence_status == (
        "present_partially_interpreted"
    )
    assert "partial_label_identity_in_missingness_evidence" in (
        result.coverage.blockers
    )
    claim = result.missingness_evidence.missing_atom_claims[0]
    assert claim.source_atom_name == "CB"
    assert claim.raw_payload["identity_basis"] == (
        "mixed_auth_residue_label_atom_ignored"
    )


def test_auth_coordinate_absence_is_partial_when_model_auth_is_incomplete() -> None:
    auth_only_headers = tuple(
        header
        for header in RESIDUE_HEADERS
        if not header.endswith(("label_asym_id", "label_comp_id", "label_seq_id"))
    )
    auth_only_row = " ".join(_residue_row().split()[:8])
    atom_headers = ATOM_HEADERS + (
        "_atom_site.auth_atom_id",
        "_atom_site.auth_comp_id",
        "_atom_site.auth_asym_id",
        "_atom_site.auth_seq_id",
    )
    result = parse_mmcif(
        _document(
            _loop(auth_only_headers, (auth_only_row,)),
            atom_headers=atom_headers,
            atom_rows=(
                "ATOM 1 C CA GLY A 1 0 0 0 1 ? ? ? ?",
                "ATOM 2 C CA GLY B 1 1 0 0 1 CA GLY B 1",
            ),
        )
    )
    assert result.coverage.missingness_evidence_status == (
        "present_partially_interpreted"
    )
    assert "source_missingness_coordinate_consistency_partially_assessed" in (
        result.coverage.blockers
    )


@pytest.mark.parametrize(
    ("row", "code"),
    [
        (_residue_row(occupancy_flag=2), "invalid_missingness_occupancy_flag"),
        (_residue_row(polymer_flag="Q"), "invalid_missingness_polymer_flag"),
        (_residue_row(model_id=2), "unknown_missingness_model_id"),
    ],
)
def test_invalid_missingness_control_fields_fail_closed(row: str, code: str) -> None:
    _assert_code(_document(_loop(RESIDUE_HEADERS, (row,))), code)


def test_duplicate_source_id_and_missing_required_identity_fail_closed() -> None:
    duplicate = _loop(
        RESIDUE_HEADERS,
        (_residue_row(source_id=1), _residue_row(source_id=1)),
    )
    _assert_code(
        _document(duplicate),
        "duplicate_or_invalid_missingness_source_id",
    )

    missing_auth_headers = tuple(
        header for header in RESIDUE_HEADERS if not header.endswith("auth_asym_id")
    )
    missing_auth_row = " ".join(_residue_row().split()[:4] + _residue_row().split()[5:])
    _assert_code(
        _document(_loop(missing_auth_headers, (missing_auth_row,))),
        "incomplete_missingness_evidence",
    )


def test_missingness_row_cap_runs_before_preservation_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _document(_loop(RESIDUE_HEADERS, (_residue_row(),)))
    monkeypatch.setattr(pdb_mmcif, "MAX_MISSING_RESIDUE_CLAIMS", 0)

    def forbidden_preservation(*args: object, **kwargs: object) -> object:
        pytest.fail("row cap must run before preservation projection")

    monkeypatch.setattr(
        pdb_mmcif,
        "_mmcif_preserved_category_payloads",
        forbidden_preservation,
    )
    _assert_code(payload, "missing_residue_evidence_limit_exceeded")


def test_combined_missingness_row_cap_runs_before_preservation_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _document(
        _loop(RESIDUE_HEADERS, (_residue_row(),)),
        _loop(ATOM_MISSING_HEADERS, (_atom_missing_row(),)),
    )
    monkeypatch.setattr(pdb_mmcif, "MAX_TOTAL_MISSINGNESS_CLAIMS", 1)

    def forbidden_preservation(*args: object, **kwargs: object) -> object:
        pytest.fail("combined row cap must run before preservation projection")

    monkeypatch.setattr(
        pdb_mmcif,
        "_mmcif_preserved_category_payloads",
        forbidden_preservation,
    )
    _assert_code(payload, "combined_missingness_evidence_limit_exceeded")


def test_missingness_token_cap_runs_before_preservation_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = RESIDUE_HEADERS + ("_pdbx_unobs_or_zero_occ_residues.local_extension",)
    payload = _document(_loop(headers, (_residue_row() + " oversized",)))
    monkeypatch.setattr(pdb_mmcif, "_MAX_MMCIF_MISSINGNESS_TOKEN_CHARS", 3)

    def forbidden_preservation(*args: object, **kwargs: object) -> object:
        pytest.fail("token cap must run before preservation projection")

    monkeypatch.setattr(
        pdb_mmcif,
        "_mmcif_preserved_category_payloads",
        forbidden_preservation,
    )
    _assert_code(payload, "missingness_token_limit_exceeded")


def test_missingness_preservation_item_cap_runs_before_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _document(_loop(ATOM_MISSING_HEADERS, (_atom_missing_row(),)))
    monkeypatch.setattr(
        pdb_mmcif,
        "_MAX_MMCIF_MISSINGNESS_PRESERVED_ITEMS",
        len(ATOM_MISSING_HEADERS) - 1,
    )

    def forbidden_preservation(*args: object, **kwargs: object) -> object:
        pytest.fail("item cap must run before preservation projection")

    monkeypatch.setattr(
        pdb_mmcif,
        "_mmcif_preserved_category_payloads",
        forbidden_preservation,
    )
    _assert_code(payload, "missingness_preservation_item_limit_exceeded")


def test_missingness_preservation_byte_cap_runs_before_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _document(_loop(RESIDUE_HEADERS, (_residue_row(),)))
    monkeypatch.setattr(
        pdb_mmcif,
        "_MAX_MMCIF_MISSINGNESS_PRESERVED_UTF8_BYTES",
        1,
    )

    def forbidden_preservation(*args: object, **kwargs: object) -> object:
        pytest.fail("byte cap must run before preservation projection")

    monkeypatch.setattr(
        pdb_mmcif,
        "_mmcif_preserved_category_payloads",
        forbidden_preservation,
    )
    _assert_code(payload, "missingness_preservation_byte_limit_exceeded")


def test_aggregate_claim_payload_limit_is_normalized() -> None:
    extension_headers = tuple(
        f"_pdbx_unobs_or_zero_occ_residues.local_extension_{index}"
        for index in range(48)
    )
    extension_values = "\n".join("x" * 1_500 for _ in extension_headers)
    payload = _document(
        _loop(
            RESIDUE_HEADERS + extension_headers,
            (f"{_residue_row()}\n{extension_values}",),
        )
    )
    _assert_code(payload, "invalid_missingness_evidence")


def test_absent_source_evidence_is_not_interpreted_as_completeness() -> None:
    result = parse_mmcif(_document())
    assert result.coverage.missingness_evidence_status == "not_present"
    assert result.missingness_evidence.source_reported_missing_residue_count == 0
    assert result.missingness_evidence.source_reported_missing_atom_count == 0
    assert "missing_atom_and_residue_completion_not_assessed" in (
        result.coverage.blockers
    )
    preparation = analyze_molecular_preparation(result.system)
    assert preparation.missing_atom_count is None
    assert preparation.missing_residue_count is None


def test_absent_source_evidence_does_not_scan_raw_models() -> None:
    class ExplodingModel(list[object]):
        def __iter__(self):  # type: ignore[override]
            raise AssertionError("raw models must not be scanned without evidence")

    parsed = pdb_mmcif.parse_cif_block("data_no_missingness\n#\n")
    result = pdb_mmcif._parse_mmcif_source_missingness(
        parsed,
        model_ids=[1],
        raw_models=[ExplodingModel()],  # type: ignore[list-item]
    )
    assert result[:5] == ((), (), False, False, ())


def test_altloc_and_assembly_bindings_do_not_duplicate_or_drop_source_claims() -> None:
    residue_section = _loop(RESIDUE_HEADERS, (_residue_row(),))
    altloc_headers = ATOM_HEADERS + ("_atom_site.label_alt_id",)
    altloc_rows = (
        "ATOM 1 C CA GLY A 1 0 0 0 1 A",
        "ATOM 2 C CA GLY A 1 1 0 0 1 B",
    )
    altloc_source = _document(
        residue_section,
        atom_headers=altloc_headers,
        atom_rows=altloc_rows,
    )
    selected_a = parse_mmcif(altloc_source, altloc_id="A")
    selected_b = parse_mmcif(altloc_source, altloc_id="B")
    assert selected_a.missingness_evidence.missing_residue_claims == (
        selected_b.missingness_evidence.missing_residue_claims
    )
    assert selected_a.missingness_evidence.requested_altloc_id == "A"
    assert selected_b.missingness_evidence.requested_altloc_id == "B"
    assert selected_a.missingness_evidence.report_sha256 != (
        selected_b.missingness_evidence.report_sha256
    )

    assembly_definition = _loop(("_pdbx_struct_assembly.id",), ("1",))
    assembly_generator = _loop(
        (
            "_pdbx_struct_assembly_gen.assembly_id",
            "_pdbx_struct_assembly_gen.oper_expression",
            "_pdbx_struct_assembly_gen.asym_id_list",
        ),
        ("1 1 A",),
    )
    assembly_operator = _loop(
        (
            "_pdbx_struct_oper_list.id",
            "_pdbx_struct_oper_list.matrix[1][1]",
            "_pdbx_struct_oper_list.matrix[1][2]",
            "_pdbx_struct_oper_list.matrix[1][3]",
            "_pdbx_struct_oper_list.matrix[2][1]",
            "_pdbx_struct_oper_list.matrix[2][2]",
            "_pdbx_struct_oper_list.matrix[2][3]",
            "_pdbx_struct_oper_list.matrix[3][1]",
            "_pdbx_struct_oper_list.matrix[3][2]",
            "_pdbx_struct_oper_list.matrix[3][3]",
            "_pdbx_struct_oper_list.vector[1]",
            "_pdbx_struct_oper_list.vector[2]",
            "_pdbx_struct_oper_list.vector[3]",
        ),
        ("1 1 0 0 0 1 0 0 0 1 0 0 0",),
    )
    assembly_source = _document(
        residue_section,
        assembly_definition,
        assembly_generator,
        assembly_operator,
    )
    deposited = parse_mmcif(assembly_source)
    expanded = parse_mmcif(assembly_source, assembly_id="1")
    assert deposited.missingness_evidence.source_reported_missing_residue_count == 1
    assert expanded.missingness_evidence.source_reported_missing_residue_count == 1
    assert expanded.missingness_evidence.missing_residue_claims[0].source_chain_id == (
        "A"
    )
    assert expanded.missingness_evidence.assembly_status == "explicit_id_applied"
    assert expanded.missingness_evidence.requested_assembly_id == "1"
    assert deposited.missingness_evidence.report_sha256 != (
        expanded.missingness_evidence.report_sha256
    )
