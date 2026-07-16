from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import stat

import pytest

import betelgeuze_engine_v2.molecular.mmcif_nonpoly_atom_site_observations as module
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_atom_site_observations import (
    MMCIF_NONPOLY_ATOM_SITE_HEADERS,
    MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_DOCUMENT_SCHEMA_ID,
    MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PROFILE_ID,
    MmcifNonpolyAtomSiteObservationError,
    NONPOLY_ATOM_SITE_CATEGORY,
    mmcif_nonpoly_atom_site_observation_document,
    mmcif_nonpoly_atom_site_observation_json_bytes,
    parse_mmcif_nonpoly_atom_site_observations,
    require_mmcif_nonpoly_atom_site_observation_document,
    write_mmcif_nonpoly_atom_site_observation_json,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_component_declarations import (
    MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS,
    MMCIF_NONPOLY_COMPONENT_BOND_HEADERS,
)
from betelgeuze_engine_v2.molecular.mmcif_struct_conn_declarations import (
    MMCIF_STRUCT_CONN_HEADERS,
)


ENTITY_HEADERS = ("_entity.id", "_entity.type")
ASYM_HEADERS = ("_struct_asym.id", "_struct_asym.entity_id")
CHEM_COMP_HEADERS = (
    "_chem_comp.id",
    "_chem_comp.type",
    "_chem_comp.pdbx_formal_charge",
)
ENTITY_NONPOLY_HEADERS = (
    "_pdbx_entity_nonpoly.entity_id",
    "_pdbx_entity_nonpoly.name",
    "_pdbx_entity_nonpoly.comp_id",
)
SCHEME_HEADERS = (
    "_pdbx_nonpoly_scheme.asym_id",
    "_pdbx_nonpoly_scheme.entity_id",
    "_pdbx_nonpoly_scheme.mon_id",
    "_pdbx_nonpoly_scheme.ndb_seq_num",
    "_pdbx_nonpoly_scheme.pdb_seq_num",
    "_pdbx_nonpoly_scheme.auth_seq_num",
    "_pdbx_nonpoly_scheme.pdb_mon_id",
    "_pdbx_nonpoly_scheme.auth_mon_id",
    "_pdbx_nonpoly_scheme.pdb_strand_id",
    "_pdbx_nonpoly_scheme.pdb_ins_code",
)

ENTITY_ROWS = (
    {"_entity.id": "1", "_entity.type": "non-polymer"},
    {"_entity.id": "2", "_entity.type": "water"},
    {"_entity.id": "3", "_entity.type": "polymer"},
)
ASYM_ROWS = (
    {"_struct_asym.id": "L", "_struct_asym.entity_id": "1"},
    {"_struct_asym.id": "W", "_struct_asym.entity_id": "2"},
    {"_struct_asym.id": "A", "_struct_asym.entity_id": "3"},
)
CHEM_COMP_ROWS = (
    {
        "_chem_comp.id": "LIG",
        "_chem_comp.type": "non-polymer",
        "_chem_comp.pdbx_formal_charge": "0",
    },
    {
        "_chem_comp.id": "HOH",
        "_chem_comp.type": "water",
        "_chem_comp.pdbx_formal_charge": "0",
    },
    {
        "_chem_comp.id": "ALA",
        "_chem_comp.type": "'L-peptide linking'",
        "_chem_comp.pdbx_formal_charge": "0",
    },
)
ENTITY_NONPOLY_ROWS = (
    {
        "_pdbx_entity_nonpoly.entity_id": "1",
        "_pdbx_entity_nonpoly.name": "'Opaque ligand source name'",
        "_pdbx_entity_nonpoly.comp_id": "LIG",
    },
    {
        "_pdbx_entity_nonpoly.entity_id": "2",
        "_pdbx_entity_nonpoly.name": "water",
        "_pdbx_entity_nonpoly.comp_id": "HOH",
    },
)
SCHEME_ROWS = (
    {
        "_pdbx_nonpoly_scheme.asym_id": "L",
        "_pdbx_nonpoly_scheme.entity_id": "1",
        "_pdbx_nonpoly_scheme.mon_id": "LIG",
        "_pdbx_nonpoly_scheme.ndb_seq_num": "1",
        "_pdbx_nonpoly_scheme.pdb_seq_num": "501",
        "_pdbx_nonpoly_scheme.auth_seq_num": "AUTH-L",
        "_pdbx_nonpoly_scheme.pdb_mon_id": "LIG",
        "_pdbx_nonpoly_scheme.auth_mon_id": "AUTHL",
        "_pdbx_nonpoly_scheme.pdb_strand_id": "LX",
        "_pdbx_nonpoly_scheme.pdb_ins_code": ".",
    },
    {
        "_pdbx_nonpoly_scheme.asym_id": "W",
        "_pdbx_nonpoly_scheme.entity_id": "2",
        "_pdbx_nonpoly_scheme.mon_id": "HOH",
        "_pdbx_nonpoly_scheme.ndb_seq_num": "1",
        "_pdbx_nonpoly_scheme.pdb_seq_num": "601",
        "_pdbx_nonpoly_scheme.auth_seq_num": "AUTH-W",
        "_pdbx_nonpoly_scheme.pdb_mon_id": "HOH",
        "_pdbx_nonpoly_scheme.auth_mon_id": "AUTHW",
        "_pdbx_nonpoly_scheme.pdb_strand_id": "WX",
        "_pdbx_nonpoly_scheme.pdb_ins_code": "?",
    },
)
ATOM_DECLARATIONS = (
    {
        "_chem_comp_atom.comp_id": "LIG",
        "_chem_comp_atom.atom_id": "C1",
        "_chem_comp_atom.type_symbol": "C",
        "_chem_comp_atom.charge": "0",
        "_chem_comp_atom.pdbx_aromatic_flag": "N",
        "_chem_comp_atom.pdbx_stereo_config": "N",
        "_chem_comp_atom.pdbx_ordinal": "1",
    },
    {
        "_chem_comp_atom.comp_id": "LIG",
        "_chem_comp_atom.atom_id": "O1",
        "_chem_comp_atom.type_symbol": "O",
        "_chem_comp_atom.charge": "0",
        "_chem_comp_atom.pdbx_aromatic_flag": "N",
        "_chem_comp_atom.pdbx_stereo_config": "N",
        "_chem_comp_atom.pdbx_ordinal": "2",
    },
    {
        "_chem_comp_atom.comp_id": "HOH",
        "_chem_comp_atom.atom_id": "O",
        "_chem_comp_atom.type_symbol": "O",
        "_chem_comp_atom.charge": "0",
        "_chem_comp_atom.pdbx_aromatic_flag": "N",
        "_chem_comp_atom.pdbx_stereo_config": "N",
        "_chem_comp_atom.pdbx_ordinal": "1",
    },
    {
        "_chem_comp_atom.comp_id": "ALA",
        "_chem_comp_atom.atom_id": "CA",
        "_chem_comp_atom.type_symbol": "C",
        "_chem_comp_atom.charge": "0",
        "_chem_comp_atom.pdbx_aromatic_flag": "N",
        "_chem_comp_atom.pdbx_stereo_config": "N",
        "_chem_comp_atom.pdbx_ordinal": "1",
    },
)
BOND_DECLARATIONS = (
    {
        "_chem_comp_bond.comp_id": "LIG",
        "_chem_comp_bond.atom_id_1": "C1",
        "_chem_comp_bond.atom_id_2": "O1",
        "_chem_comp_bond.value_order": "DOUB",
        "_chem_comp_bond.pdbx_aromatic_flag": "N",
        "_chem_comp_bond.pdbx_stereo_config": "N",
        "_chem_comp_bond.pdbx_ordinal": "1",
    },
)
STRUCT_CONN_ROWS = (
    {
        "_struct_conn.id": "conn-1",
        "_struct_conn.conn_type_id": "metalc",
        "_struct_conn.ptnr1_label_asym_id": "L",
        "_struct_conn.ptnr1_label_comp_id": "LIG",
        "_struct_conn.ptnr1_label_seq_id": ".",
        "_struct_conn.ptnr1_label_atom_id": "C1",
        "_struct_conn.pdbx_ptnr1_label_alt_id": ".",
        "_struct_conn.pdbx_ptnr1_pdb_ins_code": ".",
        "_struct_conn.ptnr1_symmetry": "1_555",
        "_struct_conn.ptnr2_label_asym_id": "W",
        "_struct_conn.ptnr2_label_comp_id": "HOH",
        "_struct_conn.ptnr2_label_seq_id": "?",
        "_struct_conn.ptnr2_label_atom_id": "O",
        "_struct_conn.pdbx_ptnr2_label_alt_id": "?",
        "_struct_conn.pdbx_ptnr2_pdb_ins_code": "?",
        "_struct_conn.ptnr1_auth_asym_id": "LX",
        "_struct_conn.ptnr1_auth_comp_id": "AUTHL",
        "_struct_conn.ptnr1_auth_seq_id": "AUTH-L",
        "_struct_conn.ptnr2_auth_asym_id": "WX",
        "_struct_conn.ptnr2_auth_comp_id": "AUTHW",
        "_struct_conn.ptnr2_auth_seq_id": "AUTH-W",
        "_struct_conn.ptnr2_symmetry": "1_555",
        "_struct_conn.pdbx_value_order": "?",
    },
)

ATOM_SITE_ROWS = (
    {
        "_atom_site.group_pdb": "ATOM",
        "_atom_site.id": "1",
        "_atom_site.type_symbol": "C",
        "_atom_site.label_atom_id": "CA",
        "_atom_site.label_alt_id": ".",
        "_atom_site.label_comp_id": "ALA",
        "_atom_site.label_asym_id": "A",
        "_atom_site.label_entity_id": "3",
        "_atom_site.label_seq_id": "1",
        "_atom_site.cartn_x": "0.0",
        "_atom_site.cartn_y": "0.0",
        "_atom_site.cartn_z": "0.0",
        "_atom_site.occupancy": "1.0",
        "_atom_site.b_iso_or_equiv": "20.0",
        "_atom_site.pdbx_formal_charge": "?",
        "_atom_site.auth_seq_id": "1",
        "_atom_site.auth_comp_id": "ALA",
        "_atom_site.auth_asym_id": "A",
        "_atom_site.auth_atom_id": "CA",
        "_atom_site.pdbx_pdb_model_num": "1",
        "_atom_site.pdbx_pdb_ins_code": "?",
    },
    {
        "_atom_site.group_pdb": "HETATM",
        "_atom_site.id": "2",
        "_atom_site.type_symbol": "C",
        "_atom_site.label_atom_id": "C1",
        "_atom_site.label_alt_id": ".",
        "_atom_site.label_comp_id": "LIG",
        "_atom_site.label_asym_id": "L",
        "_atom_site.label_entity_id": "1",
        "_atom_site.label_seq_id": ".",
        "_atom_site.cartn_x": "1.000",
        "_atom_site.cartn_y": "2.000",
        "_atom_site.cartn_z": "3.000",
        "_atom_site.occupancy": "0.50",
        "_atom_site.b_iso_or_equiv": "?",
        "_atom_site.pdbx_formal_charge": "0",
        "_atom_site.auth_seq_id": "AUTH-L",
        "_atom_site.auth_comp_id": "AUTHL",
        "_atom_site.auth_asym_id": "LX",
        "_atom_site.auth_atom_id": "AC1",
        "_atom_site.pdbx_pdb_model_num": "1",
        "_atom_site.pdbx_pdb_ins_code": ".",
    },
    {
        "_atom_site.group_pdb": "HETATM",
        "_atom_site.id": "3",
        "_atom_site.type_symbol": "'O'",
        "_atom_site.label_atom_id": "O1",
        "_atom_site.label_alt_id": "?",
        "_atom_site.label_comp_id": "LIG",
        "_atom_site.label_asym_id": "L",
        "_atom_site.label_entity_id": "1",
        "_atom_site.label_seq_id": ".",
        "_atom_site.cartn_x": "'1.250'",
        "_atom_site.cartn_y": "2.250",
        "_atom_site.cartn_z": "3.250",
        "_atom_site.occupancy": ".",
        "_atom_site.b_iso_or_equiv": "-1.0",
        "_atom_site.pdbx_formal_charge": "?",
        "_atom_site.auth_seq_id": "AUTH-L",
        "_atom_site.auth_comp_id": "AUTHL",
        "_atom_site.auth_asym_id": "LX",
        "_atom_site.auth_atom_id": "AO1",
        "_atom_site.pdbx_pdb_model_num": "1",
        "_atom_site.pdbx_pdb_ins_code": ".",
    },
    {
        "_atom_site.group_pdb": "HETATM",
        "_atom_site.id": "4",
        "_atom_site.type_symbol": "O",
        "_atom_site.label_atom_id": "O",
        "_atom_site.label_alt_id": "?",
        "_atom_site.label_comp_id": "HOH",
        "_atom_site.label_asym_id": "W",
        "_atom_site.label_entity_id": "2",
        "_atom_site.label_seq_id": "?",
        "_atom_site.cartn_x": "4.000",
        "_atom_site.cartn_y": "5.000",
        "_atom_site.cartn_z": "6.000",
        "_atom_site.occupancy": "1.0",
        "_atom_site.b_iso_or_equiv": "10.0",
        "_atom_site.pdbx_formal_charge": "?",
        "_atom_site.auth_seq_id": "AUTH-W",
        "_atom_site.auth_comp_id": "AUTHW",
        "_atom_site.auth_asym_id": "WX",
        "_atom_site.auth_atom_id": "OW",
        "_atom_site.pdbx_pdb_model_num": "1",
        "_atom_site.pdbx_pdb_ins_code": "?",
    },
)

UNINTERPRETED_TAIL = "_audit_conform.dict_name SOURCE_ONLY\n"


def _loop(headers: tuple[str, ...], rows: tuple[dict[str, str], ...]) -> str:
    assert rows
    lines = ["loop_", *headers]
    lines.extend(" ".join(row[header] for header in headers) for row in rows)
    lines.append("#")
    return "\n".join(lines) + "\n"


def _source(
    *,
    atom_site_rows: tuple[dict[str, str], ...] | None = ATOM_SITE_ROWS,
    atom_site_headers: tuple[str, ...] = MMCIF_NONPOLY_ATOM_SITE_HEADERS,
    tail: str = UNINTERPRETED_TAIL,
) -> str:
    source = (
        "data_nonpoly_observations\n#\n"
        + _loop(ENTITY_HEADERS, ENTITY_ROWS)
        + _loop(ASYM_HEADERS, ASYM_ROWS)
        + _loop(CHEM_COMP_HEADERS, CHEM_COMP_ROWS)
        + _loop(ENTITY_NONPOLY_HEADERS, ENTITY_NONPOLY_ROWS)
        + _loop(SCHEME_HEADERS, SCHEME_ROWS)
        + _loop(MMCIF_NONPOLY_COMPONENT_ATOM_HEADERS, ATOM_DECLARATIONS)
        + _loop(MMCIF_NONPOLY_COMPONENT_BOND_HEADERS, BOND_DECLARATIONS)
        + _loop(MMCIF_STRUCT_CONN_HEADERS, STRUCT_CONN_ROWS)
    )
    if atom_site_rows is not None:
        source += _loop(atom_site_headers, atom_site_rows)
    return source + tail


def _updated(
    rows: tuple[dict[str, str], ...],
    row_index: int,
    field: str,
    value: str,
) -> tuple[dict[str, str], ...]:
    copied = [dict(row) for row in rows]
    copied[row_index][field] = value
    return tuple(copied)


def _error(source: str, code: str) -> MmcifNonpolyAtomSiteObservationError:
    with pytest.raises(MmcifNonpolyAtomSiteObservationError) as exc_info:
        parse_mmcif_nonpoly_atom_site_observations(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_projection_binds_selected_rows_instances_atoms_and_connection_endpoints() -> None:
    source = _source()
    snapshot = parse_mmcif_nonpoly_atom_site_observations(source)

    assert snapshot.source_sha256 == hashlib.sha256(source.encode("ascii")).hexdigest()
    assert [row.source_atom_id for row in snapshot.observations] == [2, 3, 4]
    assert [row.label_atom_id for row in snapshot.observations] == ["C1", "O1", "O"]
    assert snapshot.category_binding.row_count == 4
    assert snapshot.category_binding.selected_row_count == 3
    assert snapshot.category_binding.category == NONPOLY_ATOM_SITE_CATEGORY
    assert snapshot.category_binding.preserved_uninterpreted_headers == (
        "_atom_site.type_symbol",
        "_atom_site.cartn_x",
        "_atom_site.cartn_y",
        "_atom_site.cartn_z",
        "_atom_site.occupancy",
        "_atom_site.b_iso_or_equiv",
        "_atom_site.pdbx_formal_charge",
    )
    assert snapshot.uninterpreted_categories == ("_audit_conform",)
    oxygen = snapshot.observations[1]
    assert oxygen.type_symbol.value == "O"
    assert oxygen.type_symbol.quoted is True
    assert oxygen.cartn_x.value == "1.250"
    assert oxygen.cartn_x.quoted is True
    assert oxygen.occupancy.state == "not_applicable"
    assert oxygen.b_iso_or_equiv.value == "-1.0"
    assert len(oxygen.instance_identity_sha256) == 64
    assert len(oxygen.component_atom_identity_sha256) == 64
    assert len(oxygen.site_identity_sha256) == 64

    assert len(snapshot.endpoint_bindings) == 1
    endpoint = snapshot.endpoint_bindings[0]
    assert endpoint.connection_id == "conn-1"
    assert endpoint.partner_1_site_identity_sha256 == snapshot.observations[0].site_identity_sha256
    assert endpoint.partner_2_site_identity_sha256 == snapshot.observations[2].site_identity_sha256

    payload = snapshot.to_dict()
    for flag in (
        "source_atom_site_observations_preserved",
        "atom_site_identity_joined",
        "nonpoly_instance_identity_references_verified",
        "component_atom_identity_references_verified",
        "struct_conn_endpoint_observation_references_verified",
        "selected_instance_component_atom_coverage_verified",
        "single_model_identity_verified",
        "source_row_order_preserved",
        "source_category_headers_bound",
    ):
        assert payload[flag] is True
    for flag in (
        "source_authenticated",
        "coordinate_values_interpreted",
        "coordinate_observation_scientifically_assessed",
        "occupancy_values_interpreted",
        "b_factor_interpreted",
        "formal_charge_interpreted",
        "type_symbol_interpreted",
        "auth_label_semantic_equivalence_interpreted",
        "altloc_population_interpreted",
        "missingness_inferred",
        "connection_type_interpreted",
        "symmetry_interpreted",
        "bond_order_interpreted",
        "covalence_interpreted",
        "coordination_interpreted",
        "topology_interpreted",
        "chemistry_interpreted",
        "preparation_ready",
        "parameterability_assessed",
        "physics_supported",
        "runtime_eligible",
        "scientifically_validated",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert payload[flag] is False


def test_header_order_changes_binding_not_observation_projection() -> None:
    canonical = parse_mmcif_nonpoly_atom_site_observations(_source())
    reordered = parse_mmcif_nonpoly_atom_site_observations(
        _source(atom_site_headers=tuple(reversed(MMCIF_NONPOLY_ATOM_SITE_HEADERS)))
    )

    assert canonical.observation_projection_sha256 == reordered.observation_projection_sha256
    assert canonical.source_binding_sha256 != reordered.source_binding_sha256
    assert canonical.snapshot_sha256 != reordered.snapshot_sha256


def test_selected_and_unselected_token_changes_have_separate_projection_effects() -> None:
    canonical = parse_mmcif_nonpoly_atom_site_observations(_source())
    selected = parse_mmcif_nonpoly_atom_site_observations(
        _source(atom_site_rows=_updated(ATOM_SITE_ROWS, 1, "_atom_site.cartn_x", "9.5"))
    )
    unselected = parse_mmcif_nonpoly_atom_site_observations(
        _source(atom_site_rows=_updated(ATOM_SITE_ROWS, 0, "_atom_site.cartn_x", "9.5"))
    )

    assert canonical.observation_projection_sha256 != selected.observation_projection_sha256
    assert canonical.observation_projection_sha256 == unselected.observation_projection_sha256
    assert canonical.source_binding_sha256 != unselected.source_binding_sha256


def test_selected_source_row_order_is_preserved() -> None:
    canonical = parse_mmcif_nonpoly_atom_site_observations(_source())
    reordered_rows = (
        ATOM_SITE_ROWS[0],
        ATOM_SITE_ROWS[3],
        ATOM_SITE_ROWS[1],
        ATOM_SITE_ROWS[2],
    )
    reordered = parse_mmcif_nonpoly_atom_site_observations(
        _source(atom_site_rows=reordered_rows)
    )

    assert [row.source_atom_id for row in reordered.observations] == [4, 2, 3]
    assert canonical.observation_projection_sha256 != reordered.observation_projection_sha256


def test_document_is_canonical_self_verifying_and_written_private(tmp_path: Path) -> None:
    snapshot = parse_mmcif_nonpoly_atom_site_observations(_source())
    document = mmcif_nonpoly_atom_site_observation_document(snapshot)

    assert document["schema_id"] == MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_DOCUMENT_SCHEMA_ID
    assert document["profile_id"] == MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_PROFILE_ID
    assert require_mmcif_nonpoly_atom_site_observation_document(document) == document
    encoded = mmcif_nonpoly_atom_site_observation_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_mmcif_nonpoly_atom_site_observation_json(
        tmp_path / "nonpoly-atom-site-observations.json",
        snapshot,
    )
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".nonpoly-atom-site-observations.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["observation_projection"]["observations"][0]["label_atom_id"] = "PRIVATE"
    with pytest.raises(ValueError, match="projection digest mismatch"):
        require_mmcif_nonpoly_atom_site_observation_document(tampered)


def test_missing_scalar_mixed_and_header_surfaces_fail_closed() -> None:
    _error(_source(atom_site_rows=None), "atom_site_missing")

    scalar = _source(atom_site_rows=None) + "_atom_site.id 1\n"
    _error(scalar, "atom_site_must_be_loop")

    mixed_headers = MMCIF_NONPOLY_ATOM_SITE_HEADERS + ("_custom.value",)
    mixed_rows = tuple({**row, "_custom.value": "x"} for row in ATOM_SITE_ROWS)
    _error(
        _source(atom_site_rows=mixed_rows, atom_site_headers=mixed_headers),
        "mixed_atom_site_loop",
    )

    missing_header = tuple(
        header
        for header in MMCIF_NONPOLY_ATOM_SITE_HEADERS
        if header != "_atom_site.occupancy"
    )
    _error(_source(atom_site_headers=missing_header), "unsupported_atom_site_headers")


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        (
            "_atom_site.auth_seq_id",
            "PRIVATE-AUTH",
            "atom_site_instance_identity_join_failed",
        ),
        (
            "_atom_site.pdbx_pdb_ins_code",
            "?",
            "atom_site_instance_identity_join_failed",
        ),
        (
            "_atom_site.label_entity_id",
            "2",
            "atom_site_label_entity_join_failed",
        ),
        (
            "_atom_site.label_atom_id",
            "PRIVATE-ATOM",
            "atom_site_component_atom_identity_missing",
        ),
        (
            "_atom_site.label_seq_id",
            "501",
            "nonblank_atom_site_marker_not_supported",
        ),
        (
            "_atom_site.label_alt_id",
            "A",
            "nonblank_atom_site_marker_not_supported",
        ),
        (
            "_atom_site.group_pdb",
            "ATOM",
            "selected_nonpoly_record_kind_mismatch",
        ),
        (
            "_atom_site.pdbx_pdb_model_num",
            "2",
            "selected_model_not_supported",
        ),
        (
            "_atom_site.cartn_x",
            "?",
            "coordinate_token_unavailable",
        ),
    ),
)
def test_selected_atom_site_join_and_observation_failures(
    field: str,
    value: str,
    code: str,
) -> None:
    rows = _updated(ATOM_SITE_ROWS, 1, field, value)
    _error(_source(atom_site_rows=rows), code)


def test_exact_instance_component_atom_coverage_and_uniqueness_are_required() -> None:
    missing = tuple(row for index, row in enumerate(ATOM_SITE_ROWS) if index != 2)
    _error(
        _source(atom_site_rows=missing),
        "selected_instance_atom_coverage_mismatch",
    )

    duplicate = dict(ATOM_SITE_ROWS[1])
    duplicate["_atom_site.id"] = "5"
    _error(
        _source(atom_site_rows=ATOM_SITE_ROWS + (duplicate,)),
        "duplicate_atom_site_observation",
    )

    duplicate_source = _updated(ATOM_SITE_ROWS, 1, "_atom_site.id", "1")
    _error(_source(atom_site_rows=duplicate_source), "duplicate_source_atom_id")


def test_identity_integer_row_and_token_bounds_are_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quoted_identity = _updated(
        ATOM_SITE_ROWS,
        1,
        "_atom_site.label_atom_id",
        "'C1'",
    )
    _error(_source(atom_site_rows=quoted_identity), "invalid_identity_token")

    invalid_integer = _updated(ATOM_SITE_ROWS, 1, "_atom_site.id", "02")
    _error(_source(atom_site_rows=invalid_integer), "invalid_positive_integer")

    oversized = _updated(
        ATOM_SITE_ROWS,
        0,
        "_atom_site.cartn_x",
        "'" + ("X" * 257) + "'",
    )
    _error(_source(atom_site_rows=oversized), "source_token_out_of_bounds")

    monkeypatch.setattr(module, "MAX_MMCIF_NONPOLY_ATOM_SITE_OBSERVATION_ROWS", 3)
    _error(_source(), "too_many_atom_site_rows")


def test_errors_do_not_echo_private_identity_values() -> None:
    private = _updated(
        ATOM_SITE_ROWS,
        1,
        "_atom_site.auth_seq_id",
        "PRIVATE-SEQUENCE-IDENTITY",
    )
    error = _error(_source(atom_site_rows=private), "atom_site_instance_identity_join_failed")

    assert "PRIVATE-SEQUENCE-IDENTITY" not in str(error)
    assert "PRIVATE-SEQUENCE-IDENTITY" not in error.detail


def test_input_type_is_strict() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_nonpoly_atom_site_observations(b"data_x")  # type: ignore[arg-type]
