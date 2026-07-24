from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib
import json
from pathlib import Path
import stat

import pytest

from betelgeuze_engine_v2.offline.reference_minimization_stationarity_successor import (
    FROZEN_LEGACY_REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SHA256_V1,
    FROZEN_LEGACY_REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SHA256_V1_1,
    FROZEN_LEGACY_REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SHA256_V1_2,
    FROZEN_REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SHA256,
    REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_MAX_OBSERVATION_BYTES,
    ReferenceMinimizationStationaritySuccessorError,
    build_reference_minimization_stationarity_successor_observation,
    main,
    read_reference_minimization_stationarity_successor_observation,
    reference_minimization_stationarity_successor_configuration_document,
    require_reference_minimization_stationarity_successor_observation,
    write_reference_minimization_stationarity_successor_observation,
)
from betelgeuze_engine_v2.physics.reference_constraint_stationarity import (
    REFERENCE_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256,
)
from betelgeuze_engine_v2.physics.reference_constraint_stationarity_independent_oracle import (
    INDEPENDENT_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256,
    IndependentConstraintStationarityConfig,
    evaluate_independent_constraint_stationarity,
    independent_constraint_stationarity_default_configuration_document,
)
from betelgeuze_engine_v2.physics.reference_minimization_validation_materializer import (
    materialize_frozen_cpu_minimization_validation_case,
)


def _sha256(value: object) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


@pytest.fixture(scope="module")
def successor_observation() -> dict[str, object]:
    return build_reference_minimization_stationarity_successor_observation()


def test_successor_and_independent_configs_are_frozen() -> None:
    successor = (
        reference_minimization_stationarity_successor_configuration_document()
    )
    independent = (
        independent_constraint_stationarity_default_configuration_document()
    )
    assert (
        successor["configuration_sha256"]
        == FROZEN_REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SHA256
        == "edae2c0ff83761426185e5eb269b1e30ea5dd5446c93121eef94163af284c237"
    )
    assert (
        successor["superseded_configuration_sha256"]
        == FROZEN_LEGACY_REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SHA256_V1_2
        == "d3e1b7500dce799c96713a7d782bb4a17a7866e3c36358f27490b03f036ab6d6"
    )
    assert successor["legacy_configuration_chain_sha256s"] == [
        FROZEN_LEGACY_REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SHA256_V1_1,
        FROZEN_LEGACY_REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SHA256_V1,
    ]
    assert (
        FROZEN_LEGACY_REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SHA256_V1_1
        == "fa9ea4e4c04f99d80d8fecb78fdf7326c7303b98a29ec7e783afba57ed0a8165"
    )
    assert (
        FROZEN_LEGACY_REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_CONFIG_SHA256_V1
        == "5c39aa346531d8f3cff378361367f7ff236f2c94c0c4bb3db66a28ec8e27d4f5"
    )
    assert (
        successor["operational_stationarity_config_sha256"]
        == REFERENCE_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256
    )
    assert (
        successor["independent_stationarity_config_sha256"]
        == INDEPENDENT_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256
        == "fccc490f763d28f7c20491ac07313a409fee388a066a9c6c1c917e5f36ef0ab7"
    )
    assert independent["configuration_sha256"] == (
        INDEPENDENT_CONSTRAINT_STATIONARITY_DEFAULT_CONFIG_SHA256
    )
    assert successor["case_count"] == 14
    assert successor["claim_policy"]["claim_safe"] is False


def test_independent_oracle_has_no_torch_numpy_or_operational_import() -> None:
    module = importlib.import_module(
        "betelgeuze_engine_v2.physics."
        "reference_constraint_stationarity_independent_oracle"
    )
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not any(name == "torch" or name.startswith("torch.") for name in imports)
    assert not any(name == "numpy" or name.startswith("numpy.") for name in imports)
    assert not any(
        name.endswith("reference_constraint_stationarity")
        for name in imports
    )


@pytest.mark.parametrize(
    "case_id,expected_iterations,expected_polish",
    (
        ("v2_constrained_angle_energy_decrease", 181, 0),
        ("v2_fixed_born_constrained_energy_decrease", 122, 8),
    ),
)
def test_independent_stationarity_converges_and_restarts_exactly(
    case_id: str,
    expected_iterations: int,
    expected_polish: int,
) -> None:
    case = materialize_frozen_cpu_minimization_validation_case(case_id)
    source = replace(
        case.independent_oracle_input,
        pause_after_accepted_iterations=None,
    )
    config = IndependentConstraintStationarityConfig()
    uninterrupted = evaluate_independent_constraint_stationarity(source, config)
    paused = evaluate_independent_constraint_stationarity(
        source,
        config,
        pause_after_accepted_iterations=3,
    )
    resumed = evaluate_independent_constraint_stationarity(
        source,
        config,
        checkpoint=paused.checkpoint,
    )
    assert uninterrupted.status == "converged"
    assert uninterrupted.accepted_iterations == expected_iterations
    assert (
        uninterrupted.accepted_stationarity_polish_iterations
        == expected_polish
    )
    assert (
        uninterrupted.final_max_tangent_force_kcal_per_mol_angstrom <= 1.0e-8
    )
    assert uninterrupted.final_max_constraint_residual_angstrom <= 1.0e-10
    assert paused.status == "checkpointed"
    assert resumed.to_dict() == uninterrupted.to_dict()
    assert resumed.checkpoint.to_dict() == uninterrupted.checkpoint.to_dict()


def test_successor_executes_and_retains_all_14_rows(
    successor_observation: dict[str, object],
) -> None:
    verified = require_reference_minimization_stationarity_successor_observation(
        successor_observation
    )
    summary = verified["summary"]
    assert summary["case_denominator"] == 14
    assert summary["case_passed_count"] == 14
    assert summary["expected_pass_passed_count"] == 8
    assert summary["expected_fail_closed_exact_disposition_count"] == 6
    assert summary["checkpoint_exact_count"] == 3
    assert summary["all_failure_rows_retained"] is True
    assert summary["openmm_candidate_case_passed_count"] == 4
    assert summary["native_openmm_lbfgs_status"] == "unchanged_rejected_6_of_8"
    assert summary["s0_complete"] is False
    rows = verified["case_rows"]
    assert len(rows) == 14
    assert all(row["case_passed"] for row in rows)
    constrained = [
        row
        for row in rows
        if row["lane"] == "constraint_stationarity_successor"
    ]
    assert len(constrained) == 4
    assert all(
        row["metrics"][
            "absolute_operational_final_force_or_tangent_kcal_per_mol_angstrom"
        ]
        <= 1.0e-8
        and row["metrics"]["constraint_max_abs_residual_angstrom"] <= 1.0e-10
        and row["trajectory_comparison"]["passed"]
        for row in constrained
    )
    fixed_born = [
        row
        for row in constrained
        if "fixed_born" in row["case_id"]
    ]
    assert {
        row["trajectory_comparison"][
            "accepted_phase_boundary_label_disagreement_count"
        ]
        for row in fixed_born
    } == {2}
    assert verified["validation_receipt"] is False
    assert verified["scientifically_validated"] is False
    assert verified["claim_safe"] is False


def test_successor_observation_is_tamper_evident_and_securely_written(
    tmp_path: Path,
    successor_observation: dict[str, object],
    capsys: pytest.CaptureFixture[str],
) -> None:
    tampered = deepcopy(successor_observation)
    tampered["summary"]["case_passed_count"] = 13
    with pytest.raises(
        ReferenceMinimizationStationaritySuccessorError,
        match="digest mismatch",
    ):
        require_reference_minimization_stationarity_successor_observation(
            tampered
        )
    path = tmp_path / "successor-observation.json"
    written = write_reference_minimization_stationarity_successor_observation(
        path,
        successor_observation,
    )
    assert written == path
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert (
        read_reference_minimization_stationarity_successor_observation(path)
        ["observation_sha256"]
        == successor_observation["observation_sha256"]
    )
    assert main(["--verify", str(path)]) == 0
    assert "successor_observation_verified" in capsys.readouterr().out
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        ReferenceMinimizationStationaritySuccessorError,
        match="refusing to overwrite",
    ):
        write_reference_minimization_stationarity_successor_observation(
            path,
            successor_observation,
        )
    oversized = tmp_path / "oversized-observation.json"
    with oversized.open("wb") as handle:
        handle.truncate(
            REFERENCE_MINIMIZATION_STATIONARITY_SUCCESSOR_MAX_OBSERVATION_BYTES
            + 1
        )
    oversized.chmod(0o600)
    with pytest.raises(
        ReferenceMinimizationStationaritySuccessorError,
        match="bounded file size",
    ):
        read_reference_minimization_stationarity_successor_observation(
            oversized
        )


def test_successor_verifier_recomputes_metrics_after_digest_rewrite(
    successor_observation: dict[str, object],
) -> None:
    tampered = deepcopy(successor_observation)
    case = tampered["case_rows"][4]
    case["metrics"][
        "absolute_operational_final_force_or_tangent_kcal_per_mol_angstrom"
    ] = 99.0
    case_projection = {
        key: value
        for key, value in case.items()
        if key != "case_observation_sha256"
    }
    case["case_observation_sha256"] = _sha256(case_projection)
    observation_projection = {
        key: value
        for key, value in tampered.items()
        if key != "observation_sha256"
    }
    tampered["observation_sha256"] = _sha256(observation_projection)
    with pytest.raises(
        ReferenceMinimizationStationaritySuccessorError,
        match="passing successor row is inconsistent",
    ):
        require_reference_minimization_stationarity_successor_observation(
            tampered
        )
