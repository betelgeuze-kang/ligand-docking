from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import stat

import pytest

import betelgeuze_engine_v2.molecular.mmcif_nonpoly_hydrogen_coordinates as module
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_coordinate_values import (
    parse_mmcif_nonpoly_coordinate_values,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_hydrogen_coordinates import (
    MMCIF_HYDROGEN_COORDINATE_BOND_LENGTH_ANGSTROM,
    MMCIF_HYDROGEN_COORDINATE_GEOMETRY_LIMITATIONS,
    MMCIF_NONPOLY_HYDROGEN_COORDINATE_DICTIONARY_ITEMS,
    MMCIF_NONPOLY_HYDROGEN_COORDINATE_DOCUMENT_SCHEMA_ID,
    MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROFILE_ID,
    mmcif_nonpoly_hydrogen_coordinate_document,
    mmcif_nonpoly_hydrogen_coordinate_json_bytes,
    parse_mmcif_nonpoly_hydrogen_coordinates,
    require_mmcif_nonpoly_hydrogen_coordinate_document,
    write_mmcif_nonpoly_hydrogen_coordinate_json,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_preparation_corpus import (
    mmcif_nonpoly_preparation_corpus_cases,
)


def _case_source(case_id: str) -> str:
    return next(
        row.source_text
        for row in mmcif_nonpoly_preparation_corpus_cases()
        if row.case_id == case_id
    )


def test_supported_graphs_receive_deterministic_coordinate_bearing_hydrogens() -> None:
    source = _case_source("supported_carbonyl")
    snapshot = parse_mmcif_nonpoly_hydrogen_coordinates(source)

    assert snapshot.generated_instance_count == 2
    assert snapshot.unavailable_instance_count == 0
    assert snapshot.added_hydrogen_coordinate_count == 4
    assert snapshot.all_prepared_graphs_coordinate_bearing is True
    ligand, water = snapshot.instance_reports
    assert ligand.coordinate_status == "coordinate_bearing_prepared_graph"
    assert water.coordinate_status == "coordinate_bearing_prepared_graph"
    assert ligand.added_hydrogen_coordinate_count == 2
    assert water.added_hydrogen_coordinate_count == 2
    assert ligand.geometry_limitations == (
        MMCIF_HYDROGEN_COORDINATE_GEOMETRY_LIMITATIONS
    )
    assert ligand.coordinate_blockers == ()

    source_values = {
        row.source_atom_id: row
        for row in parse_mmcif_nonpoly_coordinate_values(source).coordinates
    }
    source_coordinate = ligand.atom_coordinates[0]
    expected = source_values[1]
    assert source_coordinate.generation_method == "source_atom_site_coordinate"
    assert source_coordinate.source_coordinate_value_identity_sha256 == (
        expected.coordinate_value_identity_sha256
    )
    assert (
        source_coordinate.x_angstrom,
        source_coordinate.y_angstrom,
        source_coordinate.z_angstrom,
    ) == (
        expected.cartn_x.numeric_value,
        expected.cartn_y.numeric_value,
        expected.cartn_z.numeric_value,
    )

    for report in snapshot.instance_reports:
        for coordinate in report.atom_coordinates:
            if coordinate.origin != "added_hydrogen":
                continue
            parent = report.atom_coordinates[coordinate.parent_atom_index]
            distance = math.sqrt(
                (coordinate.x_angstrom - parent.x_angstrom) ** 2
                + (coordinate.y_angstrom - parent.y_angstrom) ** 2
                + (coordinate.z_angstrom - parent.z_angstrom) ** 2
            )
            assert math.isclose(
                distance,
                MMCIF_HYDROGEN_COORDINATE_BOND_LENGTH_ANGSTROM,
                rel_tol=0.0,
                abs_tol=1e-15,
            )

    payload = snapshot.to_dict()
    for flag in (
        "prepared_graph_bound",
        "source_cartesian_coordinates_bound",
        "source_cartesian_angstrom_unit_interpreted",
        "source_atom_coordinates_preserved",
        "added_hydrogen_coordinates_generated",
        "fixed_parent_offset_geometry_applied",
        "failure_complete_instance_reports",
    ):
        assert payload[flag] is True
    for flag in (
        "neighbor_geometry_interpreted",
        "stereochemistry_interpreted",
        "protonation_state_interpreted",
        "tautomer_selected",
        "hydrogen_bond_length_calibrated",
        "steric_clash_assessed",
        "coordinate_geometry_validated",
        "coordinate_minimized",
        "partial_charge_assigned",
        "reviewed_parameter_source_bound",
        "all_atom_system_created",
        "scientifically_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert payload[flag] is False


def test_source_hydrogen_coordinates_are_preserved_not_regenerated() -> None:
    snapshot = parse_mmcif_nonpoly_hydrogen_coordinates(
        _case_source("supported_source_hydrogen")
    )

    source_hydrogens = [
        coordinate
        for report in snapshot.instance_reports
        for coordinate in report.atom_coordinates
        if coordinate.origin == "source_atom"
        and coordinate.element == "H"
        and coordinate.generation_method == "source_atom_site_coordinate"
    ]
    assert source_hydrogens
    assert all(
        row.source_coordinate_value_identity_sha256 for row in source_hydrogens
    )
    assert snapshot.added_hydrogen_coordinate_count == 5


def test_unsupported_chemistry_retains_failure_complete_instance_report() -> None:
    snapshot = parse_mmcif_nonpoly_hydrogen_coordinates(
        _case_source("unsupported_extended_element")
    )

    unsupported, water = snapshot.instance_reports
    assert unsupported.coordinate_status == (
        "not_generated_preparation_graph_unavailable"
    )
    assert unsupported.atom_coordinates == ()
    assert unsupported.coordinate_set_sha256 == ""
    assert "element_outside_neutral_coh_scope" in unsupported.coordinate_blockers
    assert water.coordinate_status == "coordinate_bearing_prepared_graph"
    assert snapshot.generated_instance_count == 1
    assert snapshot.unavailable_instance_count == 1


def test_generation_is_byte_stable_for_identical_source() -> None:
    source = _case_source("supported_carbonyl")
    first = parse_mmcif_nonpoly_hydrogen_coordinates(source)
    second = parse_mmcif_nonpoly_hydrogen_coordinates(source)

    assert first.snapshot_sha256 == second.snapshot_sha256
    assert mmcif_nonpoly_hydrogen_coordinate_json_bytes(first) == (
        mmcif_nonpoly_hydrogen_coordinate_json_bytes(second)
    )


def test_document_is_canonical_self_verifying_and_written_private(
    tmp_path: Path,
) -> None:
    snapshot = parse_mmcif_nonpoly_hydrogen_coordinates(
        _case_source("supported_carbonyl")
    )
    document = mmcif_nonpoly_hydrogen_coordinate_document(snapshot)

    assert document["schema_id"] == (
        MMCIF_NONPOLY_HYDROGEN_COORDINATE_DOCUMENT_SCHEMA_ID
    )
    assert document["profile_id"] == MMCIF_NONPOLY_HYDROGEN_COORDINATE_PROFILE_ID
    assert document["source_binding"]["dictionary_items"] == (
        MMCIF_NONPOLY_HYDROGEN_COORDINATE_DICTIONARY_ITEMS
    )
    assert require_mmcif_nonpoly_hydrogen_coordinate_document(document) == document
    encoded = mmcif_nonpoly_hydrogen_coordinate_json_bytes(snapshot)
    assert json.loads(encoded) == document

    destination = write_mmcif_nonpoly_hydrogen_coordinate_json(
        tmp_path / "hydrogen-coordinates.json", snapshot
    )
    assert destination.read_bytes() == encoded + b"\n"
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".hydrogen-coordinates.json.*.tmp"))

    tampered = deepcopy(document)
    tampered_report = tampered["coordinate_projection"]["instance_reports"][0]
    tampered_report["coordinate_status"] = (
        "not_generated_preparation_graph_unavailable"
    )
    projection_digest = module._sha256(tampered["coordinate_projection"])
    tampered["coordinate_projection_sha256"] = projection_digest
    tampered["snapshot_sha256"] = module._sha256(
        {
            "schema_id": MMCIF_NONPOLY_HYDROGEN_COORDINATE_DOCUMENT_SCHEMA_ID,
            "coordinate_projection_sha256": projection_digest,
            "source_binding_sha256": tampered["source_binding_sha256"],
            "claim_policy": module._claim_policy(),
        }
    )
    with pytest.raises(ValueError, match="unavailable report invalid"):
        require_mmcif_nonpoly_hydrogen_coordinate_document(tampered)


def test_input_type_is_strict() -> None:
    with pytest.raises(TypeError, match="must be a string"):
        parse_mmcif_nonpoly_hydrogen_coordinates(b"data_x")  # type: ignore[arg-type]


def test_dedicated_workflow_covers_supported_python_matrix() -> None:
    source = Path(
        ".github/workflows/ci-engine-v2-mmcif-nonpoly-hydrogen-coordinates.yml"
    ).read_text(encoding="utf-8")

    assert 'branches: ["main"]' in source
    assert 'python-version: ["3.10", "3.11", "3.12"]' in source
    assert "mmcif_nonpoly_hydrogen_coordinates.py" in source
    assert "test_engine_v2_mmcif_nonpoly_hydrogen_coordinates.py" in source
    assert "test_engine_v2_mmcif_nonpoly_preparation.py" in source
    assert "test_engine_v2_mmcif_nonpoly_preparation_corpus.py" in source
    assert "test_engine_v2_post_merge_state.py" in source
    assert "permissions:\n  contents: read" in source
