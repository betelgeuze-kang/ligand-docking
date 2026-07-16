from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import stat

import pytest

import betelgeuze_engine_v2.molecular.mmcif_nonpoly_canonical_topology as module
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_canonical_topology import (
    MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DICTIONARY_ITEMS,
    MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DOCUMENT_SCHEMA_ID,
    MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PROFILE_ID,
    MmcifNonpolyCanonicalTopologyError,
    mmcif_nonpoly_canonical_topology_document,
    mmcif_nonpoly_canonical_topology_json_bytes,
    parse_mmcif_nonpoly_canonical_topology,
    require_mmcif_nonpoly_canonical_topology_document,
    write_mmcif_nonpoly_canonical_topology_json,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_component_declarations import (
    MMCIF_NONPOLY_COMPONENT_BOND_HEADERS,
)
from betelgeuze_engine_v2.molecular.mmcif_struct_conn_declarations import (
    MMCIF_STRUCT_CONN_HEADERS,
)
from betelgeuze_engine_v2.molecular.models import Bond
from tests.unit.test_engine_v2_mmcif_nonpoly_atom_site_observations import (
    ATOM_SITE_ROWS,
    BOND_DECLARATIONS,
    STRUCT_CONN_ROWS,
    _source,
)


def _replace_row(
    source: str,
    headers: tuple[str, ...],
    original: dict[str, str],
    updated: dict[str, str],
) -> str:
    old_row = " ".join(original[header] for header in headers)
    new_row = " ".join(updated[header] for header in headers)
    assert source.count(old_row) == 1
    return source.replace(old_row, new_row, 1)


def _topology_source(
    *,
    bond_updates: dict[str, str] | None = None,
    connection_updates: dict[str, str] | None = None,
    atom_site_rows: tuple[dict[str, str], ...] = ATOM_SITE_ROWS,
) -> str:
    source = _source(atom_site_rows=atom_site_rows)
    if bond_updates:
        original = dict(BOND_DECLARATIONS[0])
        updated = {**original, **bond_updates}
        source = _replace_row(
            source,
            MMCIF_NONPOLY_COMPONENT_BOND_HEADERS,
            original,
            updated,
        )
    if connection_updates:
        original = dict(STRUCT_CONN_ROWS[0])
        updated = {**original, **connection_updates}
        source = _replace_row(
            source,
            MMCIF_STRUCT_CONN_HEADERS,
            original,
            updated,
        )
    return source


def _topology_error(source: str, code: str) -> MmcifNonpolyCanonicalTopologyError:
    with pytest.raises(MmcifNonpolyCanonicalTopologyError) as exc_info:
        parse_mmcif_nonpoly_canonical_topology(source)
    assert exc_info.value.code == code
    return exc_info.value


def test_component_bond_and_metal_coordination_are_structurally_separate() -> None:
    snapshot = parse_mmcif_nonpoly_canonical_topology(_topology_source())

    assert [row.atom_index for row in snapshot.atoms] == [0, 1, 2]
    assert [row.source_atom_id for row in snapshot.atoms] == [2, 3, 4]
    assert [(row.component_id, row.atom_id) for row in snapshot.atoms] == [
        ("LIG", "C1"),
        ("LIG", "O1"),
        ("HOH", "O"),
    ]
    assert snapshot.component_bond_count == 1
    assert snapshot.struct_covalent_bond_count == 0
    assert len(snapshot.bonds) == 1
    bond = snapshot.bonds[0]
    assert (bond.atom_i, bond.atom_j, bond.order) == (0, 1, 2.0)
    assert bond.aromatic is False
    assert bond.stereo == "none"
    assert bond.source_kind == "mmcif_chem_comp_bond"
    assert len(snapshot.coordination_edges) == 1
    edge = snapshot.coordination_edges[0]
    assert (edge.atom_i, edge.atom_j) == (0, 2)
    assert edge.to_dict()["connection_type"] == "metalc"
    assert edge.to_dict()["partner_1_symmetry"] == "1_555"
    assert len(snapshot.topology_sha256) == 64

    canonical_bonds = snapshot.canonical_bonds
    assert len(canonical_bonds) == 1
    assert isinstance(canonical_bonds[0], Bond)
    assert canonical_bonds[0].order == 2.0
    assert canonical_bonds[0].source == "mmcif_chem_comp_bond"

    payload = snapshot.to_dict()
    for flag in (
        "source_declarations_bound",
        "atom_site_identity_joined",
        "component_bond_order_interpreted",
        "component_bond_aromaticity_interpreted",
        "component_bond_stereo_interpreted",
        "connection_type_interpreted",
        "identity_symmetry_interpreted",
        "covalence_interpreted",
        "coordination_interpreted",
        "coordination_edges_separate_from_bonds",
        "topology_interpreted",
        "canonical_bond_records_created",
    ):
        assert payload[flag] is True
    for flag in (
        "source_authenticated",
        "non_identity_symmetry_supported",
        "hydrogen_connection_supported",
        "disulfide_connection_supported",
        "delocalized_pi_polymeric_bond_orders_supported",
        "atom_element_interpreted",
        "atom_formal_charge_crosschecked",
        "atom_aromaticity_crosschecked",
        "coordinate_geometry_interpreted",
        "bond_distance_assessed",
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


@pytest.mark.parametrize(
    ("order_code", "aromatic_flag", "expected_order", "expected_aromatic"),
    (
        ("SING", "N", 1.0, False),
        ("DOUB", "N", 2.0, False),
        ("TRIP", "N", 3.0, False),
        ("QUAD", "N", 4.0, False),
        ("AROM", "Y", 1.5, True),
        ("sing", "n", 1.0, False),
    ),
)
def test_supported_component_bond_orders_are_explicitly_mapped(
    order_code: str,
    aromatic_flag: str,
    expected_order: float,
    expected_aromatic: bool,
) -> None:
    snapshot = parse_mmcif_nonpoly_canonical_topology(
        _topology_source(
            bond_updates={
                "_chem_comp_bond.value_order": order_code,
                "_chem_comp_bond.pdbx_aromatic_flag": aromatic_flag,
            }
        )
    )

    assert snapshot.bonds[0].order == expected_order
    assert snapshot.bonds[0].aromatic is expected_aromatic


def test_double_bond_stereo_is_bounded_to_e_z_or_none() -> None:
    e_bond = parse_mmcif_nonpoly_canonical_topology(
        _topology_source(
            bond_updates={"_chem_comp_bond.pdbx_stereo_config": "E"}
        )
    )
    z_bond = parse_mmcif_nonpoly_canonical_topology(
        _topology_source(
            bond_updates={"_chem_comp_bond.pdbx_stereo_config": "z"}
        )
    )

    assert e_bond.bonds[0].stereo == "E"
    assert z_bond.bonds[0].stereo == "Z"

    _topology_error(
        _topology_source(
            bond_updates={
                "_chem_comp_bond.value_order": "SING",
                "_chem_comp_bond.pdbx_stereo_config": "E",
            }
        ),
        "component_bond_stereo_order_mismatch",
    )


@pytest.mark.parametrize("order_code", ("DELO", "PI", "POLY", "PRIVATE-ORDER"))
def test_unmapped_component_orders_fail_closed_without_echo(order_code: str) -> None:
    error = _topology_error(
        _topology_source(
            bond_updates={"_chem_comp_bond.value_order": order_code}
        ),
        "unsupported_component_bond_order",
    )

    assert order_code not in str(error)
    assert order_code not in error.detail


def test_component_aromatic_flag_must_agree_with_order() -> None:
    _topology_error(
        _topology_source(
            bond_updates={
                "_chem_comp_bond.value_order": "AROM",
                "_chem_comp_bond.pdbx_aromatic_flag": "N",
            }
        ),
        "component_bond_aromaticity_mismatch",
    )
    _topology_error(
        _topology_source(
            bond_updates={"_chem_comp_bond.pdbx_aromatic_flag": "Y"}
        ),
        "component_bond_aromaticity_mismatch",
    )


def test_identity_symmetry_covale_connection_creates_a_bond() -> None:
    snapshot = parse_mmcif_nonpoly_canonical_topology(
        _topology_source(
            connection_updates={
                "_struct_conn.conn_type_id": "CoVaLe",
                "_struct_conn.pdbx_value_order": "sing",
            }
        )
    )

    assert len(snapshot.bonds) == 2
    assert snapshot.component_bond_count == 1
    assert snapshot.struct_covalent_bond_count == 1
    assert len(snapshot.coordination_edges) == 0
    covalent = snapshot.bonds[1]
    assert (covalent.atom_i, covalent.atom_j, covalent.order) == (0, 2, 1.0)
    assert covalent.source_kind == "mmcif_struct_conn_covale"


def test_covalent_connection_requires_explicit_supported_order() -> None:
    _topology_error(
        _topology_source(
            connection_updates={"_struct_conn.conn_type_id": "covale"}
        ),
        "required_topology_code_missing",
    )
    _topology_error(
        _topology_source(
            connection_updates={
                "_struct_conn.conn_type_id": "covale",
                "_struct_conn.pdbx_value_order": "AROM",
            }
        ),
        "unsupported_struct_covalent_bond_order",
    )


def test_metal_coordination_never_accepts_a_bond_order() -> None:
    _topology_error(
        _topology_source(
            connection_updates={"_struct_conn.pdbx_value_order": "SING"}
        ),
        "coordination_bond_order_not_supported",
    )


@pytest.mark.parametrize("connection_type", ("hydrog", "disulf", "PRIVATE-CONN"))
def test_unsupported_connection_types_fail_without_becoming_bonds(
    connection_type: str,
) -> None:
    error = _topology_error(
        _topology_source(
            connection_updates={"_struct_conn.conn_type_id": connection_type}
        ),
        "unsupported_connection_type",
    )

    assert connection_type not in str(error)
    assert connection_type not in error.detail


@pytest.mark.parametrize("field", ("_struct_conn.ptnr1_symmetry", "_struct_conn.ptnr2_symmetry"))
def test_non_identity_or_unknown_symmetry_fails_before_edge_creation(field: str) -> None:
    _topology_error(
        _topology_source(connection_updates={field: "2_555"}),
        "non_identity_symmetry_not_supported",
    )
    _topology_error(
        _topology_source(connection_updates={field: "?"}),
        "non_identity_symmetry_not_supported",
    )


def test_struct_connection_cannot_duplicate_a_component_bond() -> None:
    _topology_error(
        _topology_source(
            connection_updates={
                "_struct_conn.conn_type_id": "covale",
                "_struct_conn.ptnr2_label_asym_id": "L",
                "_struct_conn.ptnr2_label_comp_id": "LIG",
                "_struct_conn.ptnr2_label_seq_id": ".",
                "_struct_conn.ptnr2_label_atom_id": "O1",
                "_struct_conn.pdbx_ptnr2_pdb_ins_code": ".",
                "_struct_conn.ptnr2_auth_asym_id": "LX",
                "_struct_conn.ptnr2_auth_comp_id": "AUTHL",
                "_struct_conn.ptnr2_auth_seq_id": "AUTH-L",
                "_struct_conn.pdbx_value_order": "SING",
            }
        ),
        "duplicate_or_self_connection_pair",
    )


def test_document_is_canonical_self_verifying_and_written_private(tmp_path: Path) -> None:
    snapshot = parse_mmcif_nonpoly_canonical_topology(_topology_source())
    document = mmcif_nonpoly_canonical_topology_document(snapshot)

    assert document["schema_id"] == MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DOCUMENT_SCHEMA_ID
    assert document["profile_id"] == MMCIF_NONPOLY_CANONICAL_TOPOLOGY_PROFILE_ID
    assert document["source_binding"]["dictionary_items"] == (
        MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DICTIONARY_ITEMS
    )
    assert require_mmcif_nonpoly_canonical_topology_document(document) == document
    encoded = mmcif_nonpoly_canonical_topology_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_mmcif_nonpoly_canonical_topology_json(
        tmp_path / "canonical-topology.json", snapshot
    )
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".canonical-topology.json.*.tmp"))

    tampered = deepcopy(document)
    tampered["topology_projection"]["topology"]["bonds"][0]["order"] = 3.0
    projection_digest = module._sha256(tampered["topology_projection"])
    tampered["topology_projection_sha256"] = projection_digest
    tampered["snapshot_sha256"] = module._sha256(
        {
            "schema_id": MMCIF_NONPOLY_CANONICAL_TOPOLOGY_DOCUMENT_SCHEMA_ID,
            "topology_projection_sha256": projection_digest,
            "source_binding_sha256": tampered["source_binding_sha256"],
            "claim_policy": module._claim_policy(),
        }
    )
    with pytest.raises(ValueError, match="bond identity mismatch"):
        require_mmcif_nonpoly_canonical_topology_document(tampered)


def test_selected_source_order_is_bound_into_canonical_atom_indices() -> None:
    canonical = parse_mmcif_nonpoly_canonical_topology(_topology_source())
    reordered_rows = (
        ATOM_SITE_ROWS[0],
        ATOM_SITE_ROWS[3],
        ATOM_SITE_ROWS[1],
        ATOM_SITE_ROWS[2],
    )
    reordered = parse_mmcif_nonpoly_canonical_topology(
        _topology_source(atom_site_rows=reordered_rows)
    )

    assert [row.source_atom_id for row in reordered.atoms] == [4, 2, 3]
    assert (reordered.bonds[0].atom_i, reordered.bonds[0].atom_j) == (1, 2)
    assert (reordered.coordination_edges[0].atom_i, reordered.coordination_edges[0].atom_j) == (0, 1)
    assert canonical.topology_sha256 != reordered.topology_sha256


def test_input_type_is_strict() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_nonpoly_canonical_topology(b"data_x")  # type: ignore[arg-type]
