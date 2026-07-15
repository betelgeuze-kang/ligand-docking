from __future__ import annotations

import ast
import copy
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
import pytest

import betelgeuze_engine_v2 as package_root
import betelgeuze_engine_v2.forcefield as forcefield_package
from betelgeuze_engine_v2.forcefield import (
    spice_c1c4_bonded_basis_observability as module,
)
from betelgeuze_engine_v2.forcefield.spice_c1c4_bonded_basis_observability import (
    SPICE_C1C4_BONDED_BASIS_ENERGY_TARGET_RMS_BINARY64_BE_HEX,
    SPICE_C1C4_BONDED_BASIS_FORCE_TARGET_RMS_BINARY64_BE_HEX,
    SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_CLAIM_SCOPE,
    SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_PROTOCOL_SHA256,
    SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_SCHEMA_ID,
    SPICE_C1C4_BONDED_BASIS_PRIMARY_VARIANT_ID,
    SpiceC1C4BondedBasisObservabilityReport,
    analyze_spice_c1c4_bonded_basis_observability,
    derive_spice_c1c4_bonded_basis_observability,
    serialize_spice_c1c4_bonded_basis_observability_report,
    spice_c1c4_bonded_basis_observability_protocol_bytes,
    spice_c1c4_bonded_basis_observability_protocol_document,
)
from betelgeuze_engine_v2.forcefield.spice_c1c4_force_matching_targets import (
    derive_spice_c1c4_force_matching_targets,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = (
    REPOSITORY_ROOT
    / "config"
    / "independent_engine_v2_v2_2_spice_c1c4_quantum_reference_evidence.json"
)
MODULE_PATH = (
    REPOSITORY_ROOT
    / "betelgeuze_engine_v2"
    / "forcefield"
    / "spice_c1c4_bonded_basis_observability.py"
)


def _source_bytes() -> bytes:
    return SOURCE_PATH.read_bytes()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )


@pytest.fixture(scope="module")
def targets():
    return derive_spice_c1c4_force_matching_targets(_source_bytes())


@pytest.fixture(scope="module")
def bundle(targets):
    return module._build_fit_design(targets)


@pytest.fixture(scope="module")
def report():
    return analyze_spice_c1c4_bonded_basis_observability(_source_bytes())


def test_protocol_report_factory_and_canonical_serialization_are_bound(report) -> None:
    protocol_bytes = spice_c1c4_bonded_basis_observability_protocol_bytes()
    assert hashlib.sha256(protocol_bytes).hexdigest() == (
        SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_PROTOCOL_SHA256
    )
    assert SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_PROTOCOL_SHA256 == (
        "063bbbea6d97ddc6f65242e70898442ae6514838c5acc02c9e2d57562089af93"
    )
    assert spice_c1c4_bonded_basis_observability_protocol_document() == (
        module._PROTOCOL_DOCUMENT
    )
    detached = spice_c1c4_bonded_basis_observability_protocol_document()
    detached["protocol_id"] = "mutated"
    assert (
        spice_c1c4_bonded_basis_observability_protocol_document()["protocol_id"]
        == module.SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_PROTOCOL_ID
    )

    assert isinstance(report, SpiceC1C4BondedBasisObservabilityReport)
    assert report.schema_id == SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_SCHEMA_ID
    assert report.claim_scope == SPICE_C1C4_BONDED_BASIS_OBSERVABILITY_CLAIM_SCOPE
    assert report.primary_variant_id == SPICE_C1C4_BONDED_BASIS_PRIMARY_VARIANT_ID
    with pytest.raises(TypeError, match="factory-only"):
        replace(report, _factory_token=object())
    serialized = serialize_spice_c1c4_bonded_basis_observability_report(_source_bytes())
    assert serialized == _canonical_bytes(asdict(report))
    assert serialized == serialize_spice_c1c4_bonded_basis_observability_report(
        _source_bytes()
    )
    assert derive_spice_c1c4_bonded_basis_observability(_source_bytes()) == report


def test_topology_key_universe_term_counts_and_fit_row_contract_are_exact(
    targets, bundle, report
) -> None:
    assert tuple(row.group_id for row in bundle.topologies) == (
        "c",
        "cc",
        "ccc",
        "cccc",
    )
    assert report.term_counts_by_group == (
        ("c", 4, 6, 0),
        ("cc", 7, 12, 9),
        ("ccc", 10, 18, 18),
        ("cccc", 13, 24, 27),
    )
    assert (
        report.bond_environment_key_count,
        report.angle_environment_key_count,
        report.proper_environment_key_count,
    ) == (6, 9, 7)
    assert bundle.matrix.shape == (3480, 114)
    assert bundle.targets.shape == (3480,)
    assert len(bundle.row_metadata) == 3480
    assert report.fit_pair_count == 60
    assert report.fit_force_record_count == 120
    assert (
        report.fit_energy_row_count,
        report.fit_force_row_count,
        report.fit_total_row_count,
    ) == (60, 3420, 3480)
    assert {row["kind"] for row in bundle.row_metadata} == {
        "relative_energy",
        "force",
    }
    assert all(
        (metadata["group_id"], metadata["source_pair_id"])
        in {
            (row.group_id, row.source_pair_id)
            for row in targets.relative_energy_targets
            if row.partition == "fit"
        }
        for metadata in bundle.row_metadata
    )

    energy_metadata = [
        row for row in bundle.row_metadata if row["kind"] == "relative_energy"
    ]
    assert len(energy_metadata) == 60
    assert [
        (row["group_id"], row["source_pair_id"]) for row in energy_metadata
    ] == sorted(
        (row.group_id, row.source_pair_id)
        for row in targets.relative_energy_targets
        if row.partition == "fit"
    )


def test_fit_only_target_scales_and_graph_modality_weights_are_exact(
    bundle, report
) -> None:
    assert report.energy_target_rms_kj_per_mol == 42.65680130781243
    assert report.force_target_rms_kj_per_mol_per_angstrom == 69.42751524726391
    assert report.energy_target_rms_binary64_be_hex == (
        SPICE_C1C4_BONDED_BASIS_ENERGY_TARGET_RMS_BINARY64_BE_HEX
    )
    assert report.force_target_rms_binary64_be_hex == (
        SPICE_C1C4_BONDED_BASIS_FORCE_TARGET_RMS_BINARY64_BE_HEX
    )
    assert struct.pack(">d", bundle.energy_scale).hex() == "4045541210b48320"
    assert struct.pack(">d", bundle.force_scale).hex() == "40515b5c68e9628d"

    for group_id in ("c", "cc", "ccc", "cccc"):
        energy_indices = [
            index
            for index, row in enumerate(bundle.row_metadata)
            if row["group_id"] == group_id and row["kind"] == "relative_energy"
        ]
        force_indices = [
            index
            for index, row in enumerate(bundle.row_metadata)
            if row["group_id"] == group_id and row["kind"] == "force"
        ]
        energy_weight_mass = sum(
            (bundle.row_weights[index] * bundle.energy_scale) ** 2
            for index in energy_indices
        )
        force_weight_mass = sum(
            (bundle.row_weights[index] * bundle.force_scale) ** 2
            for index in force_indices
        )
        assert energy_weight_mass == pytest.approx(0.125, abs=1.0e-15)
        assert force_weight_mass == pytest.approx(0.125, abs=1.0e-14)


def test_all_four_predeclared_variants_are_full_rank_without_model_selection(
    report,
) -> None:
    rows = {row.variant_id: row for row in report.variant_reports}
    assert tuple(rows) == (
        "parity_even_low_order_n1_3",
        "phase_complete_low_order_n1_3",
        "parity_even_full_allowed_n1_6",
        "phase_complete_full_allowed_n1_6",
    )
    assert [row.column_count for row in rows.values()] == [51, 72, 72, 114]
    assert [row.numerical_rank for row in rows.values()] == [51, 72, 72, 114]
    assert all(row.nullity == 0 for row in rows.values())
    assert all(row.row_count == 3480 for row in rows.values())
    assert all(row.rank_margin > 1.0e8 for row in rows.values())
    assert all(row.conditional_fit_design_full_column_rank for row in rows.values())
    assert 150.0 < rows["parity_even_low_order_n1_3"].condition_number < 220.0
    assert 170.0 < rows["phase_complete_low_order_n1_3"].condition_number < 240.0
    assert 190.0 < rows["parity_even_full_allowed_n1_6"].condition_number < 260.0
    assert 300.0 < rows["phase_complete_full_allowed_n1_6"].condition_number < 450.0
    assert rows[SPICE_C1C4_BONDED_BASIS_PRIMARY_VARIANT_ID].primary is True
    assert sum(row.primary for row in rows.values()) == 1
    assert rows["phase_complete_low_order_n1_3"].parity_even is False
    assert rows["phase_complete_full_allowed_n1_6"].includes_sine is True
    assert report.cross_platform_bitwise_svd_assessed is False


def test_force_columns_are_the_negative_derivative_of_the_same_scalar_basis(
    targets,
) -> None:
    topology_row = next(row for row in targets.topologies if row.group_id == "cccc")
    topology = module._compile_topology(topology_row)
    columns = module._column_descriptors(
        tuple(module._compile_topology(row) for row in targets.topologies)
    )
    force_row = next(
        row
        for row in targets.force_targets
        if row.group_id == "cccc" and row.partition == "fit" and row.role == "seed"
    )
    coordinates = module._coordinates_from_target(
        force_row.geometry_angstrom_binary64_be_hex,
        len(topology.atomic_numbers),
    )
    values, forces = module._feature_value_and_force(topology, coordinates, columns)
    step = 1.0e-6
    for atom_index in range(coordinates.shape[0]):
        for axis in range(3):
            plus = coordinates.copy()
            minus = coordinates.copy()
            plus[atom_index, axis] += step
            minus[atom_index, axis] -= step
            plus_values, _ = module._feature_value_and_force(topology, plus, columns)
            minus_values, _ = module._feature_value_and_force(topology, minus, columns)
            finite_difference_force = -(plus_values - minus_values) / (2.0 * step)
            assert forces[atom_index, axis, :] == pytest.approx(
                finite_difference_force,
                abs=3.0e-7,
                rel=3.0e-7,
            )
    assert np.max(np.abs(forces.sum(axis=0))) < 2.0e-13
    torques = np.zeros((3, forces.shape[2]), dtype=np.float64)
    for atom_index in range(coordinates.shape[0]):
        torques += np.cross(coordinates[atom_index][None, :], forces[atom_index].T).T
    assert np.max(np.abs(torques)) < 2.0e-12
    shifted_values, shifted_forces = module._feature_value_and_force(
        topology,
        coordinates + np.asarray([3.25, -7.5, 1.125]),
        columns,
    )
    assert shifted_values == pytest.approx(values, abs=2.0e-13)
    assert shifted_forces == pytest.approx(forces, abs=2.0e-13)


def test_reflection_preserves_primary_cosines_and_flips_sine_audit_columns(
    targets,
) -> None:
    topology_row = next(row for row in targets.topologies if row.group_id == "cccc")
    compiled_all = tuple(module._compile_topology(row) for row in targets.topologies)
    topology = next(row for row in compiled_all if row.group_id == "cccc")
    columns = module._column_descriptors(compiled_all)
    force_row = next(
        row
        for row in targets.force_targets
        if row.group_id == "cccc" and row.partition == "fit" and row.role == "seed"
    )
    coordinates = module._coordinates_from_target(
        force_row.geometry_angstrom_binary64_be_hex,
        len(topology_row.atomic_numbers),
    )
    reflected = coordinates.copy()
    reflected[:, 0] *= -1.0
    values, _ = module._feature_value_and_force(topology, coordinates, columns)
    reflected_values, _ = module._feature_value_and_force(topology, reflected, columns)
    even_indices = [index for index, row in enumerate(columns) if row.feature != "sine"]
    sine_indices = [index for index, row in enumerate(columns) if row.feature == "sine"]
    assert reflected_values[even_indices] == pytest.approx(
        values[even_indices], abs=3.0e-14
    )
    assert reflected_values[sine_indices] == pytest.approx(
        -values[sine_indices], abs=3.0e-14
    )


def test_selection_and_holdout_rows_cannot_affect_the_private_fit_design(
    targets, bundle
) -> None:
    mutated = copy.copy(targets)
    mutated_energy = tuple(
        replace(row, relative_energy_kj_per_mol_binary64_be_hex="7ff0000000000000")
        if row.partition != "fit"
        else row
        for row in targets.relative_energy_targets
    )
    mutated_force = tuple(
        replace(
            row,
            geometry_angstrom_binary64_be_hex="00",
            force_kj_per_mol_per_angstrom_binary64_be_hex="00",
        )
        if row.partition != "fit"
        else row
        for row in targets.force_targets
    )
    object.__setattr__(mutated, "relative_energy_targets", mutated_energy)
    object.__setattr__(mutated, "force_targets", mutated_force)
    replay = module._build_fit_design(mutated)
    assert replay.matrix.tobytes() == bundle.matrix.tobytes()
    assert replay.targets.tobytes() == bundle.targets.tobytes()
    assert replay.row_weights.tobytes() == bundle.row_weights.tobytes()
    assert replay.row_metadata == bundle.row_metadata


def test_malformed_topology_and_singular_geometry_fail_closed(targets) -> None:
    topology = targets.topologies[-1]
    with pytest.raises(module.SpiceC1C4BondedBasisObservabilityContractError):
        module._compile_topology(
            replace(
                topology,
                connectivity=topology.connectivity + (topology.connectivity[0],),
            )
        )
    compiled_all = tuple(module._compile_topology(row) for row in targets.topologies)
    compiled = compiled_all[-1]
    columns = module._column_descriptors(compiled_all)
    force_row = next(
        row
        for row in targets.force_targets
        if row.group_id == "cccc" and row.partition == "fit" and row.role == "seed"
    )
    coordinates = module._coordinates_from_target(
        force_row.geometry_angstrom_binary64_be_hex,
        len(compiled.atomic_numbers),
    )
    atom_i, atom_j, _key = compiled.bonds[0]
    coordinates[atom_j] = coordinates[atom_i]
    with pytest.raises(module.SpiceC1C4BondedBasisObservabilityContractError):
        module._feature_value_and_force(compiled, coordinates, columns)


def test_nonpromotion_fields_import_boundary_and_no_committed_report_artifact(
    report,
) -> None:
    false_fields = (
        "selection_or_holdout_used",
        "target_centering_applied",
        "regularization_applied",
        "cross_platform_bitwise_svd_assessed",
        "coefficient_fit_performed",
        "predictions_computed",
        "candidate_fitting_performed",
        "candidate_parameter_set_available",
        "bonded_parameter_identifiability_established",
        "physical_parameter_identifiability_established",
        "parameter_family_sufficiency_assessed",
        "transferability_established",
        "reference_validation_performed",
        "parameterability_assessed",
        "parameterizable",
        "production_parameters_available",
        "physics_ready",
        "runtime_eligible",
        "execution_authorized",
        "claim_safe",
    )
    assert all(getattr(report, field) is False for field in false_fields)
    assert report.conditional_fit_design_full_column_rank is True
    for exported_name in module.__all__:
        assert getattr(forcefield_package, exported_name) is getattr(
            module, exported_name
        )
        assert not hasattr(package_root, exported_name)

    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    assert not any(
        forbidden in imported
        for imported in imported_modules
        for forbidden in (
            "fitting",
            "linear_alkane_parameters",
            "linear_alkane_assignment",
            "linear_alkane_reference_kernel",
            "runtime",
        )
    )
    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden_call in ("lstsq", "pinv", "optimizer", "least_squares"):
        assert forbidden_call not in source
    assert not list(
        REPOSITORY_ROOT.glob("**/*spice_c1c4_bonded_basis_observability*.json")
    )
