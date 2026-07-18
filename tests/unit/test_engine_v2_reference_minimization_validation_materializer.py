from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.physics.reference_minimization_validation_materializer import (  # noqa: E402
    CPU_MINIMIZATION_VALIDATION_MATERIALIZER_ID,
    CPU_MINIMIZATION_VALIDATION_MATERIALIZER_SCHEMA_ID,
    CPUMinimizationValidationMaterializationError,
    cpu_minimization_validation_materialization_manifest_document,
    cpu_minimization_validation_materialization_manifest_json_bytes,
    cpu_minimization_validation_materializer_source_sha256,
    materialize_frozen_cpu_minimization_validation_case,
    write_cpu_minimization_validation_materialization_manifest_json,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_protocol import (  # noqa: E402
    FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
    cpu_minimization_validation_protocol_document,
)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()


def test_manifest_materializes_every_frozen_case_without_results() -> None:
    manifest = cpu_minimization_validation_materialization_manifest_document()
    protocol = cpu_minimization_validation_protocol_document()

    assert manifest["schema_id"] == (
        CPU_MINIMIZATION_VALIDATION_MATERIALIZER_SCHEMA_ID
    )
    assert manifest["materializer_id"] == CPU_MINIMIZATION_VALIDATION_MATERIALIZER_ID
    assert manifest["protocol_sha256"] == (
        FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256
    )
    assert manifest["materializer_source_sha256"] == (
        cpu_minimization_validation_materializer_source_sha256()
    )
    assert manifest["materializer_source_sha256"] == (
        "add96991d96255280f6ba0fe5158a7b6a9971333494b34d36809769689b78f58"
    )
    assert len(manifest["materializer_source_sha256"]) == 64
    assert manifest["coverage"] == {
        "fixture_count": 11,
        "case_count": 14,
        "expected_pass_case_count": 8,
        "expected_fail_closed_case_count": 6,
        "unconstrained_v1_case_count": 4,
        "v2_runtime_case_count": 7,
        "fixed_born_case_count": 4,
    }
    assert len({row["case_id"] for row in manifest["cases"]}) == 14
    assert len({row["runtime_input_sha256"] for row in manifest["cases"]}) == 14
    assert all(len(row["runtime_input_sha256"]) == 64 for row in manifest["cases"])
    assert manifest["fixture_materializer_implemented"] is True
    assert protocol["claim_policy"]["fixture_materializer_implemented"] is False
    assert "fixture_materializer_not_implemented" in protocol[
        "authorization_gate"
    ]["current_blockers"]
    for key in (
        "independent_minimization_reference_implemented",
        "minimization_executed",
        "checkpoint_created",
        "energy_or_force_values_present",
        "metric_values_present",
        "validation_result_collected",
        "validation_execution_authorized",
        "parameter_fitting_authorized",
        "scientifically_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
    ):
        assert manifest[key] is False
    projection = {
        key: value
        for key, value in manifest.items()
        if key != "materialization_manifest_sha256"
    }
    assert manifest["materialization_manifest_sha256"] == _canonical_sha256(
        projection
    )
    assert manifest["materialization_manifest_sha256"] == (
        "3857ad25e1004a36b3543bc1f01dbf91498a840efc531ea64a47a5e340adf480"
    )


def test_exact_v1_and_mixed_term_payloads_map_to_runtime_contracts() -> None:
    bond = materialize_frozen_cpu_minimization_validation_case(
        "v1_bonded_energy_decrease"
    )
    assert bond.system.coordinates.dtype == torch.float64
    assert bond.system.coordinates.device.type == "cpu"
    assert bond.system.atom_count == 2
    assert bond.v2_parameters is None
    assert bond.constrained_config is None
    assert bond.base_parameters.bonds[0].equilibrium_angstrom == 1.0
    assert (
        bond.base_parameters.bonds[0].force_constant_kcal_per_mol_angstrom2
        == 100.0
    )
    assert bond.minimization_config.max_iterations == 64
    assert bond.minimization_config.max_backtracks == 16
    assert (
        bond.minimization_config.initial_step_size_angstrom2_mol_per_kcal
        == 1.0e-3
    )

    mixed = materialize_frozen_cpu_minimization_validation_case(
        "v1_mixed_term_energy_decrease"
    )
    torsion = mixed.base_parameters.torsions[0]
    assert torsion.periodicity == 2
    assert torsion.phase_radians == 0.25
    assert torsion.amplitude_kcal_per_mol == 1.5
    assert mixed.base_parameters.excluded_pairs == (
        (0, 1),
        (0, 2),
        (1, 2),
        (1, 3),
        (2, 3),
    )
    assert mixed.base_parameters.scaled_pairs[0].to_dict() == {
        "atom_i": 0,
        "atom_j": 3,
        "lj_scale": 0.5,
        "electrostatic_scale": 0.8333333333333334,
    }


def test_constrained_fixed_born_and_budget_inputs_are_exact() -> None:
    constrained = materialize_frozen_cpu_minimization_validation_case(
        "v2_constrained_angle_energy_decrease"
    )
    assert constrained.v2_parameters is not None
    assert constrained.constrained_config is not None
    assert len(constrained.v2_parameters.constraints) == 2
    assert {
        row.target_distance_angstrom for row in constrained.v2_parameters.constraints
    } == {1.0}
    assert all(
        row.tolerance_angstrom == 1.0e-10
        for row in constrained.v2_parameters.constraints
    )

    solvated = materialize_frozen_cpu_minimization_validation_case(
        "v2_fixed_born_constrained_energy_decrease"
    )
    assert solvated.v2_parameters is not None
    assert solvated.solvation_parameters is not None
    assert [
        row.effective_born_radius_angstrom
        for row in solvated.solvation_parameters.atom_parameters
    ] == [1.5, 1.6, 1.7]
    assert [
        row.charge_e for row in solvated.base_parameters.atom_parameters
    ] == [0.8, -0.4, -0.4]

    line_search = materialize_frozen_cpu_minimization_validation_case(
        "line_search_budget_exhausted"
    )
    assert line_search.v2_parameters is None
    assert line_search.minimization_config.max_backtracks == 1
    assert (
        line_search.minimization_config.initial_step_size_angstrom2_mol_per_kcal
        == 1_000_000.0
    )

    projection = materialize_frozen_cpu_minimization_validation_case(
        "constraint_projection_budget_exhausted"
    )
    assert projection.v2_parameters is not None
    assert projection.constrained_config is not None
    assert projection.constrained_config.constraint_projection.max_iterations == 1
    assert [
        row.target_distance_angstrom for row in projection.v2_parameters.constraints
    ] == [1.0, 1.0, 3.0]


def test_checkpoint_and_periodic_failure_inputs_resolve_base_fixtures() -> None:
    topology = materialize_frozen_cpu_minimization_validation_case(
        "checkpoint_topology_crosswire"
    )
    assert topology.fixture_resolution_chain == (
        "four_atom_mixed_terms",
        "checkpoint_topology_crosswire",
    )
    assert topology.v2_parameters is None
    assert topology.failure_injection == {
        "checkpoint_topology_sha256": "a" * 64,
        "runtime_topology_sha256": "b" * 64,
    }
    with pytest.raises(TypeError):
        topology.failure_injection["new"] = "x"

    solvation = materialize_frozen_cpu_minimization_validation_case(
        "checkpoint_solvation_crosswire"
    )
    assert solvation.fixture_resolution_chain == (
        "three_atom_charged_constrained_angle",
        "checkpoint_solvation_crosswire",
    )
    assert solvation.solvation_parameters is not None
    assert solvation.failure_injection == {
        "checkpoint_solvation_sha256": "e" * 64,
        "runtime_solvation_sha256": "f" * 64,
    }

    periodic = materialize_frozen_cpu_minimization_validation_case(
        "fixed_born_periodic_cell_rejected"
    )
    assert periodic.system.cell is not None
    assert periodic.system.cell.periodic == (True, True, True)
    assert periodic.solvation_parameters is not None
    assert periodic.expected_error_code == "periodic_fixed_born_not_supported"


def test_checkpoint_cases_bind_pause_without_creating_checkpoint() -> None:
    manifest = cpu_minimization_validation_materialization_manifest_document()
    rows = {row["case_id"]: row for row in manifest["cases"]}
    for case_id in (
        "v1_checkpoint_restart_exact",
        "v2_constrained_checkpoint_restart_exact",
        "v2_fixed_born_checkpoint_restart_exact",
    ):
        assert rows[case_id]["pause_after_accepted_iterations"] == 3
        assert rows[case_id]["checkpoint_created"] is False
        assert rows[case_id]["minimization_executed"] is False


def test_materializer_rejects_unknown_case_and_protocol_drift() -> None:
    with pytest.raises(
        CPUMinimizationValidationMaterializationError,
        match="unknown frozen minimization case",
    ):
        materialize_frozen_cpu_minimization_validation_case("not_frozen")

    tampered = deepcopy(cpu_minimization_validation_protocol_document())
    tampered["fixture_manifest"]["fixtures"][0]["payload"][
        "runtime_parameter_sha256"
    ] = "0" * 64
    with pytest.raises(ValueError, match="digest mismatch"):
        cpu_minimization_validation_materialization_manifest_document(tampered)


def test_materializer_import_boundary_excludes_evaluators_and_minimizers() -> None:
    source_path = Path(
        __import__(
            "betelgeuze_engine_v2.physics.reference_minimization_validation_materializer",
            fromlist=["__file__"],
        ).__file__
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "minimize_reference_force_field" not in imported_names
    assert "minimize_reference_force_field_v2_constrained" not in imported_names
    assert "evaluate_reference_force_field" not in imported_names
    assert "evaluate_reference_force_field_v2" not in imported_names
    assert "evaluate_fixed_born_polar_solvation" not in imported_names


def test_canonical_manifest_json_and_atomic_writer_round_trip(tmp_path: Path) -> None:
    payload = cpu_minimization_validation_materialization_manifest_json_bytes()
    assert payload.endswith(b"\n")
    assert json.loads(payload) == (
        cpu_minimization_validation_materialization_manifest_document()
    )
    destination = write_cpu_minimization_validation_materialization_manifest_json(
        tmp_path / "nested" / "materialization.json"
    )
    assert destination.read_bytes() == payload
    assert os.stat(destination).st_mode & 0o777 == 0o644
