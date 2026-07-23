from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.offline.openmm_force_double_rattle_oracle import (
    DoubleRattleDistanceConstraint,
    OPENMM_FORCE_DOUBLE_RATTLE_ALGORITHM_ID,
    OpenMMForceDoubleRattleCheckpoint,
    OpenMMForceDoubleRattleConfig,
    OpenMMForceDoubleRattleError,
    resume_openmm_force_double_rattle,
    run_openmm_force_double_rattle,
)


SYSTEM_SHA256 = hashlib.sha256(b"double-rattle-system").hexdigest()
FORCE_SHA256 = hashlib.sha256(b"double-rattle-force").hexdigest()


def _zero_force(coordinates):
    return 0.0, tuple((0.0, 0.0, 0.0) for _ in coordinates)


def _config(**changes) -> OpenMMForceDoubleRattleConfig:
    values = {
        "timestep_ps": 1.0e-3,
        "box_lengths_angstrom": (10.0, 10.0, 10.0),
        "position_tolerance_angstrom": 1.0e-12,
        "velocity_tolerance_angstrom_per_ps": 1.0e-12,
        "max_position_sweeps": 500,
        "max_velocity_sweeps": 500,
    }
    values.update(changes)
    return OpenMMForceDoubleRattleConfig(**values)


def _constraint() -> tuple[DoubleRattleDistanceConstraint, ...]:
    return (DoubleRattleDistanceConstraint(0, 1, 1.0),)


def _run(*, steps: int):
    return run_openmm_force_double_rattle(
        system_sha256=SYSTEM_SHA256,
        force_configuration_sha256=FORCE_SHA256,
        coordinates=((1.0, 1.0, 1.0), (2.0, 1.0, 1.0)),
        velocities_angstrom_per_ps=(
            (0.0, 0.1, 0.0),
            (0.0, -0.1, 0.0),
        ),
        masses_da=(1.0, 1.0),
        constraints=_constraint(),
        config=_config(),
        steps=steps,
        evaluator=_zero_force,
    )


def _canonical_sha256(value: object) -> str:
    payload = (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def test_oracle_source_is_stdlib_only_and_import_separated() -> None:
    source = Path(
        "betelgeuze_engine_v2/offline/openmm_force_double_rattle_oracle.py"
    ).read_text(encoding="utf-8")

    assert "betelgeuze_engine_v2.physics" not in source
    assert "import torch" not in source
    assert "import openmm" not in source
    assert "run_reference_nve" not in source
    assert "project_reference_shake" not in source

    oracle_path = str(
        Path(
            "betelgeuze_engine_v2/offline/"
            "openmm_force_double_rattle_oracle.py"
        ).resolve()
    )
    command = (
        "import importlib.util,sys;"
        f"spec=importlib.util.spec_from_file_location('standalone_oracle',{oracle_path!r});"
        "module=importlib.util.module_from_spec(spec);"
        "sys.modules[spec.name]=module;"
        "spec.loader.exec_module(module);"
        "print(module.OPENMM_FORCE_DOUBLE_RATTLE_ALGORITHM_ID);"
        "print(int('torch' in sys.modules),int('openmm' in sys.modules))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", command],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.splitlines() == [
        OPENMM_FORCE_DOUBLE_RATTLE_ALGORITHM_ID,
        "0 0",
    ]


def test_config_constraint_and_checkpoint_round_trip_are_canonical() -> None:
    config = _config()
    constraint = _constraint()[0]
    result = _run(steps=2)

    assert OpenMMForceDoubleRattleConfig.from_dict(config.to_dict()) == config
    assert DoubleRattleDistanceConstraint.from_dict(
        constraint.to_dict()
    ) == constraint
    parsed = OpenMMForceDoubleRattleCheckpoint.from_dict(
        result.checkpoint.to_dict()
    )
    assert parsed == result.checkpoint
    assert parsed.checkpoint_sha256 == result.checkpoint.checkpoint_sha256

    with pytest.raises(
        OpenMMForceDoubleRattleError,
        match="canonical and distinct",
    ):
        DoubleRattleDistanceConstraint(1, 0, 1.0)
    with pytest.raises(
        OpenMMForceDoubleRattleError,
        match="internal tolerance",
    ):
        _config(position_tolerance_angstrom=1.0e-5)


def test_trajectory_constraints_and_exact_checkpoint_restart() -> None:
    full = _run(steps=4)
    paused = _run(steps=2)
    resumed = resume_openmm_force_double_rattle(
        system_sha256=SYSTEM_SHA256,
        force_configuration_sha256=FORCE_SHA256,
        masses_da=(1.0, 1.0),
        constraints=_constraint(),
        config=_config(),
        checkpoint=paused.checkpoint.to_dict(),
        additional_steps=2,
        evaluator=_zero_force,
    )

    assert len(full.frames) == 5
    assert full.checkpoint.step == 4
    assert full.checkpoint.evaluated_frame_count == 5
    assert full.checkpoint.to_dict() == resumed.checkpoint.to_dict()
    assert full.frames[-1] == resumed.frames[-1]
    assert (
        full.checkpoint.max_abs_position_constraint_residual_angstrom
        <= 1.0e-12
    )
    assert (
        full.checkpoint.max_abs_velocity_constraint_residual_angstrom_per_ps
        <= 1.0e-12
    )
    assert all(
        len(frame["frame_sha256"]) == 64 for frame in full.frames
    )
    assert full.checkpoint.cumulative_position_sweeps > 0
    assert full.checkpoint.cumulative_velocity_sweeps > 0


def test_projection_exhaustion_and_evaluator_failure_fail_closed() -> None:
    triangle = (
        DoubleRattleDistanceConstraint(0, 1, 1.0),
        DoubleRattleDistanceConstraint(0, 2, 1.0),
        DoubleRattleDistanceConstraint(1, 2, 1.0),
    )
    with pytest.raises(
        OpenMMForceDoubleRattleError,
        match="exhausted the sweep budget",
    ):
        run_openmm_force_double_rattle(
            system_sha256=SYSTEM_SHA256,
            force_configuration_sha256=FORCE_SHA256,
            coordinates=(
                (1.0, 1.0, 1.0),
                (2.01, 1.0, 1.0),
                (1.5, 1.87, 1.0),
            ),
            velocities_angstrom_per_ps=((0.0, 0.0, 0.0),) * 3,
            masses_da=(1.0, 1.0, 1.0),
            constraints=triangle,
            config=_config(
                position_tolerance_angstrom=1.0e-14,
                max_position_sweeps=1,
            ),
            steps=0,
            evaluator=_zero_force,
        )

    def broken(_coordinates):
        raise RuntimeError("private diagnostic")

    with pytest.raises(
        OpenMMForceDoubleRattleError,
        match="force evaluator failed",
    ):
        run_openmm_force_double_rattle(
            system_sha256=SYSTEM_SHA256,
            force_configuration_sha256=FORCE_SHA256,
            coordinates=((1.0, 1.0, 1.0), (2.0, 1.0, 1.0)),
            velocities_angstrom_per_ps=((0.0, 0.0, 0.0),) * 2,
            masses_da=(1.0, 1.0),
            constraints=_constraint(),
            config=_config(),
            steps=0,
            evaluator=broken,
        )


def test_checkpoint_digest_identity_force_and_invariants_fail_closed() -> None:
    paused = _run(steps=2)
    payload = paused.checkpoint.to_dict()

    digest_tamper = deepcopy(payload)
    digest_tamper["step"] = 1
    with pytest.raises(
        OpenMMForceDoubleRattleError,
        match="digest mismatch",
    ):
        OpenMMForceDoubleRattleCheckpoint.from_dict(digest_tamper)

    invariant_tamper = deepcopy(payload)
    invariant_tamper["evaluated_frame_count"] = 1
    projection = {
        key: value
        for key, value in invariant_tamper.items()
        if key != "checkpoint_sha256"
    }
    invariant_tamper["checkpoint_sha256"] = _canonical_sha256(projection)
    with pytest.raises(
        OpenMMForceDoubleRattleError,
        match="frame count",
    ):
        OpenMMForceDoubleRattleCheckpoint.from_dict(invariant_tamper)

    with pytest.raises(
        OpenMMForceDoubleRattleError,
        match="identity mismatch",
    ):
        resume_openmm_force_double_rattle(
            system_sha256=SYSTEM_SHA256,
            force_configuration_sha256=hashlib.sha256(b"other").hexdigest(),
            masses_da=(1.0, 1.0),
            constraints=_constraint(),
            config=_config(),
            checkpoint=payload,
            additional_steps=1,
            evaluator=_zero_force,
        )

    def changed_force(coordinates):
        return 1.0, tuple((0.0, 0.0, 0.0) for _ in coordinates)

    with pytest.raises(
        OpenMMForceDoubleRattleError,
        match="force state does not reproduce",
    ):
        resume_openmm_force_double_rattle(
            system_sha256=SYSTEM_SHA256,
            force_configuration_sha256=FORCE_SHA256,
            masses_da=(1.0, 1.0),
            constraints=_constraint(),
            config=_config(),
            checkpoint=payload,
            additional_steps=1,
            evaluator=changed_force,
        )
