from __future__ import annotations

import ast
import base64
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys

import pytest
import torch

from betelgeuze_engine_v2.forcefield import (
    EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID,
    EXACT_METHANE_HARMONIC_MINIMIZATION_ALGORITHM_PROTOCOL_ID,
    EXACT_METHANE_HARMONIC_MINIMIZATION_CHECKPOINT_SCHEMA_ID,
    EXACT_METHANE_HARMONIC_MINIMIZATION_CLAIM_SCOPE,
    EXACT_METHANE_HARMONIC_MINIMIZATION_DIAGNOSTIC_SCHEMA_ID,
    ExactMethaneBondAngleParameterSet,
    ExactMethaneHarmonicMinimizationCheckpoint,
    ExactMethaneHarmonicMinimizationConfig,
    ExactMethaneHarmonicMinimizationError,
    ExactMethaneHarmonicMinimizationReport,
    HarmonicAngleParameter,
    HarmonicBondParameter,
    deserialize_exact_methane_harmonic_minimization_checkpoint,
    resume_exact_methane_harmonic_minimization_diagnostic,
    run_exact_methane_harmonic_minimization_diagnostic,
    serialize_exact_methane_harmonic_minimization_checkpoint,
)
from betelgeuze_engine_v2.forcefield import harmonic_minimization as module
from betelgeuze_engine_v2.molecular import UnitCell, parse_sdf_v2000
from betelgeuze_engine_v2.molecular.observation import attach_parser_observation_digest
from betelgeuze_engine_v2.molecular.serialization import (
    deserialize_all_atom_system,
    serialize_all_atom_system,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
METHANE = (
    REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "v2_1_ingest_corpus"
    / "methane_explicit_h.sdf"
)
EXPECTED_FOUR_STEP_REPORT_SHA256 = (
    "29e68ef6e0376b5637e3983de79d4b9c7c9761b1a5ee473f80e79c5a1a86ffbb"
)
EXPECTED_FOUR_STEP_REPORT_BYTES_SHA256 = (
    "a08a802d4df121494833552ce9762df036d34d3832e762bb893f394826bf09c4"
)
EXPECTED_TWO_STEP_CHECKPOINT_SHA256 = (
    "79d28bac5da4d205a2d5d7e956b49c4e0f7c0030267f7034dabe7ee419b01a4d"
)
EXPECTED_TWO_STEP_CHECKPOINT_BYTES_SHA256 = (
    "58bb87429be45beb30114342734e10d19d4129b5f36497594e1e9b99993911d3"
)
EXPECTED_ALGORITHM_PROTOCOL_SHA256 = (
    "ba8dcfba6c647751cf9d34039b0deb4d06d2992278b8d5f6755ec97e99f54fba"
)


def _system(source: bytes | None = None, *, source_id: str = "minimizer-methane"):
    return parse_sdf_v2000(
        METHANE.read_bytes() if source is None else source,
        source_id=source_id,
    ).system


def _parameter_set(
    *,
    form_bound: bool = True,
    bond_equilibrium: float = 1.0,
    bond_force_constant: float = 2.0,
    angle_equilibrium: float = 1.0,
    angle_force_constant: float = 4.0,
) -> ExactMethaneBondAngleParameterSet:
    return ExactMethaneBondAngleParameterSet(
        parameter_set_id="nonphysical_harmonic_minimizer_fixture",
        parameter_set_version="1.0.0",
        derivation_status="declared_contract_fixture",
        bond_parameter=HarmonicBondParameter(
            parameter_id="minimizer_ch_bond",
            equilibrium_length_angstrom=bond_equilibrium,
            force_constant_kj_mol_angstrom2=bond_force_constant,
        ),
        angle_parameter=HarmonicAngleParameter(
            parameter_id="minimizer_hch_angle",
            equilibrium_angle_radian=angle_equilibrium,
            force_constant_kj_mol_radian2=angle_force_constant,
        ),
        artifact_schema_version="1.1.0" if form_bound else "1.0.0",
        functional_form_id=(
            EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID if form_bound else None
        ),
    )


def _config(**changes) -> ExactMethaneHarmonicMinimizationConfig:
    values = {
        "max_accepted_steps": 1,
        "max_line_search_trials": 4,
        "initial_step_size": 0.1,
        "backtracking_factor": 0.5,
        "armijo_coefficient": 1.0e-4,
        "force_tolerance": 1.0e-8,
    }
    values.update(changes)
    return ExactMethaneHarmonicMinimizationConfig(**values)


def _report(*, system=None, parameter_set=None, config=None):
    return run_exact_methane_harmonic_minimization_diagnostic(
        _system() if system is None else system,
        _parameter_set() if parameter_set is None else parameter_set,
        config=_config() if config is None else config,
    )


def _float_from_binary64(value: str) -> float:
    return struct.unpack(">d", bytes.fromhex(value))[0]


def _canonical_json(document: object) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _rehashed_checkpoint(document: dict[str, object]) -> bytes:
    core = {key: value for key, value in document.items() if key != "checkpoint_sha256"}
    document["checkpoint_sha256"] = hashlib.sha256(_canonical_json(core)).hexdigest()
    return _canonical_json(document)


def _permuted_methane_source(permutation: tuple[int, ...]) -> bytes:
    lines = METHANE.read_text(encoding="ascii").splitlines()
    old_to_new = {old: new for new, old in enumerate(permutation)}
    old_bonds = ((0, 1), (0, 2), (0, 3), (0, 4))
    bond_lines = [
        f"{old_to_new[atom_i] + 1:3d}{old_to_new[atom_j] + 1:3d}{1:3d}{0:3d}"
        for atom_i, atom_j in reversed(old_bonds)
    ]
    return (
        "\n".join(
            (
                *lines[:4],
                *(lines[4 + old] for old in permutation),
                *bond_lines,
                *lines[13:],
            )
        )
        + "\n"
    ).encode("ascii")


def _equilibrium_system_and_parameters():
    system = _system(source_id="equilibrium-minimizer-methane")
    scale = 1.0 / math.sqrt(3.0)
    coordinates = torch.zeros_like(system.coordinates)
    coordinates[0, 1:] = scale * torch.tensor(
        [
            [1.0, 1.0, 1.0],
            [1.0, -1.0, -1.0],
            [-1.0, 1.0, -1.0],
            [-1.0, -1.0, 1.0],
        ],
        dtype=torch.float64,
    )
    return (
        system.with_coordinates(coordinates),
        _parameter_set(
            bond_equilibrium=1.0,
            angle_equilibrium=math.acos(-1.0 / 3.0),
        ),
    )


def test_strict_armijo_descent_and_nonpromotion_contract() -> None:
    report = _report(config=_config(max_accepted_steps=4))
    payload = report.to_dict()

    assert payload["schema_id"] == (
        EXACT_METHANE_HARMONIC_MINIMIZATION_DIAGNOSTIC_SCHEMA_ID
    )
    assert payload["claim_scope"] == (EXACT_METHANE_HARMONIC_MINIMIZATION_CLAIM_SCOPE)
    assert payload["algorithm_protocol"]["protocol_id"] == (
        EXACT_METHANE_HARMONIC_MINIMIZATION_ALGORITHM_PROTOCOL_ID
    )
    assert payload["algorithm_protocol_sha256"] == (EXPECTED_ALGORITHM_PROTOCOL_SHA256)
    assert payload["algorithm_protocol"]["armijo_rhs"] == (
        "E_trial<=E_current-c1*alpha*sum_over_atoms_and_axes(F_component^2)"
    )
    assert payload["algorithm_protocol"]["armijo_descent_norm_unit"] == (
        "kilojoule_squared_per_mole_squared_per_angstrom_squared"
    )
    assert payload["algorithm_protocol"]["termination_force_metric"] == (
        "maximum_per_atom_l2_norm"
    )
    assert payload["algorithm_protocol"]["max_accepted_steps_hard_cap"] == 256
    assert payload["algorithm_protocol"]["max_line_search_trials_hard_cap"] == 64
    assert payload["parameter_artifact_schema_version"] == "1.1.0"
    assert payload["functional_form_binding_status"] == (
        "parameter_payload_bound_match"
    )
    assert payload["termination_code"] == "accepted_step_limit_reached"
    assert payload["termination_status"] == "nonconverged"
    assert payload["accepted_step_count"] == 4
    assert payload["strict_energy_decrease_for_every_accepted_step"] is True
    assert payload["report_sha256"] == EXPECTED_FOUR_STEP_REPORT_SHA256
    assert hashlib.sha256(_canonical_json(payload)).hexdigest() == (
        EXPECTED_FOUR_STEP_REPORT_BYTES_SHA256
    )
    assert _float_from_binary64(
        payload["final_energy_ieee754_binary64_be"]
    ) < _float_from_binary64(payload["initial_energy_ieee754_binary64_be"])

    previous_trace = None
    for index, step in enumerate(payload["accepted_steps"], start=1):
        energy_before = _float_from_binary64(step["energy_before_ieee754_binary64_be"])
        energy_after = _float_from_binary64(step["energy_after_ieee754_binary64_be"])
        armijo_rhs = _float_from_binary64(step["armijo_rhs_ieee754_binary64_be"])
        assert step["accepted_step_index"] == index
        assert energy_after < energy_before
        assert energy_after <= armijo_rhs
        assert step["strict_energy_decrease"] is True
        assert step["armijo_satisfied"] is True
        assert step["total_rejected_trial_count"] == (step["total_trial_count"] - index)
        assert step["transcript_sha256"] != previous_trace
        previous_trace = step["transcript_sha256"]
    assert previous_trace == payload["accepted_trajectory_sha256"]

    false_fields = (
        "physics_supported",
        "scientific_validity_green",
        "parameterability_assessed",
        "parameterizable",
        "global_parameter_coverage_complete",
        "preparation_ready",
        "runtime_eligible",
        "execution_authorized",
        "energy_evaluation_authorized",
        "force_evaluation_authorized",
        "virial_evaluation_authorized",
        "minimization_authorized",
        "simulation_ready",
        "claim_safe",
    )
    assert all(payload[name] is False for name in false_fields)
    assert "diagnostic_descent_not_runtime_minimization" in payload["blockers"]
    assert "first_order_stationarity_not_minimum" in payload["blockers"]

    core = {key: value for key, value in payload.items() if key != "report_sha256"}
    assert payload["report_sha256"] == hashlib.sha256(_canonical_json(core)).hexdigest()


def test_stationarity_observation_is_not_a_minimum_attestation() -> None:
    system, parameter_set = _equilibrium_system_and_parameters()
    payload = _report(
        system=system,
        parameter_set=parameter_set,
        config=_config(max_accepted_steps=2),
    ).to_dict()

    assert payload["termination_code"] == "stationarity_tolerance_met"
    assert payload["termination_status"] == "stationarity_observed"
    assert payload["accepted_step_count"] == 0
    assert payload["diagnostic_minimization_performed"] is False
    assert payload["scoped_first_order_stationarity_observed"] is True
    assert payload["stationarity_is_not_a_minimum_attestation"] is True
    assert payload["minimization_authorized"] is False
    assert "global_optimum_not_assessed" in payload["blockers"]


def test_stagnation_and_line_search_budget_are_distinct() -> None:
    smallest_positive = float.fromhex("0x0.0000000000001p-1022")
    stagnated = _report(
        config=_config(
            max_line_search_trials=1,
            initial_step_size=smallest_positive,
        )
    ).to_dict()
    assert stagnated["termination_code"] == ("no_representable_coordinate_change")
    assert stagnated["termination_status"] == "stagnated"
    assert stagnated["total_trial_count"] == 1
    assert stagnated["rejected_trial_count"] == 1

    limited_energy_change = _report(
        config=_config(
            max_line_search_trials=1,
            initial_step_size=2.0**-50,
        )
    ).to_dict()
    assert limited_energy_change["termination_code"] == "line_search_exhausted"
    assert limited_energy_change["last_trial_rejection_code"] == (
        "strict_energy_decrease_not_observed_within_trial_limit"
    )

    energy_stagnated = _report(
        config=_config(
            max_line_search_trials=64,
            initial_step_size=2.0**-50,
        )
    ).to_dict()
    assert energy_stagnated["termination_code"] == (
        "no_representable_energy_decrease_on_configured_backtracking_path"
    )
    assert energy_stagnated["termination_status"] == "stagnated"

    exhausted = _report(
        config=_config(max_line_search_trials=1, initial_step_size=1.0)
    ).to_dict()
    assert exhausted["termination_code"] == "line_search_exhausted"
    assert exhausted["termination_status"] == "failed"
    assert exhausted["last_trial_rejection_code"] == (
        "strict_energy_decrease_not_observed_within_trial_limit"
    )

    invalid_candidates = _report(
        config=_config(max_line_search_trials=1, initial_step_size=1.0e308)
    ).to_dict()
    assert invalid_candidates["termination_code"] == "line_search_exhausted"
    assert invalid_candidates["last_trial_rejection_code"] == (
        "candidate_evaluation_exhausted"
    )


def test_checkpoint_round_trip_prefix_replay_and_resume_equivalence() -> None:
    config = _config(max_accepted_steps=4)
    report = _report(config=config)
    expected = report.to_dict()
    initial_checkpoint_object = run_exact_methane_harmonic_minimization_diagnostic(
        _system(),
        _parameter_set(),
        config=config,
        pause_after_accepted_steps=0,
    )
    paused_checkpoint_object = run_exact_methane_harmonic_minimization_diagnostic(
        _system(),
        _parameter_set(),
        config=config,
        pause_after_accepted_steps=2,
    )
    assert type(initial_checkpoint_object) is ExactMethaneHarmonicMinimizationCheckpoint
    assert type(paused_checkpoint_object) is ExactMethaneHarmonicMinimizationCheckpoint
    initial_checkpoint = serialize_exact_methane_harmonic_minimization_checkpoint(
        initial_checkpoint_object
    )
    final_checkpoint = serialize_exact_methane_harmonic_minimization_checkpoint(
        paused_checkpoint_object
    )
    assert json.loads(final_checkpoint)["checkpoint_sha256"] == (
        EXPECTED_TWO_STEP_CHECKPOINT_SHA256
    )
    assert hashlib.sha256(final_checkpoint).hexdigest() == (
        EXPECTED_TWO_STEP_CHECKPOINT_BYTES_SHA256
    )
    continued_checkpoint_object = resume_exact_methane_harmonic_minimization_diagnostic(
        initial_checkpoint,
        pause_after_additional_accepted_steps=2,
    )
    assert type(continued_checkpoint_object) is (
        ExactMethaneHarmonicMinimizationCheckpoint
    )
    assert (
        serialize_exact_methane_harmonic_minimization_checkpoint(
            continued_checkpoint_object
        )
        == final_checkpoint
    )

    restored = deserialize_exact_methane_harmonic_minimization_checkpoint(
        final_checkpoint
    )
    assert restored.accepted_step_count == 2
    assert serialize_exact_methane_harmonic_minimization_checkpoint(restored) == (
        final_checkpoint
    )
    assert (
        resume_exact_methane_harmonic_minimization_diagnostic(
            initial_checkpoint
        ).to_dict()
        == expected
    )
    resumed = resume_exact_methane_harmonic_minimization_diagnostic(final_checkpoint)
    assert type(resumed) is ExactMethaneHarmonicMinimizationReport
    assert resumed.to_dict() == expected
    assert resumed == report

    document = restored.to_dict()
    assert document["schema_id"] == (
        EXACT_METHANE_HARMONIC_MINIMIZATION_CHECKPOINT_SCHEMA_ID
    )
    assert document["accepted_step_boundary"] is True
    assert all(
        document[name] is False
        for name in (
            "physics_supported",
            "scientific_validity_green",
            "parameterability_assessed",
            "parameterizable",
            "global_parameter_coverage_complete",
            "preparation_ready",
            "runtime_eligible",
            "execution_authorized",
            "energy_evaluation_authorized",
            "force_evaluation_authorized",
            "virial_evaluation_authorized",
            "minimization_authorized",
            "simulation_ready",
            "claim_safe",
        )
    )


def test_derived_system_provenance_is_demoted_and_lineage_bound() -> None:
    source = _system()
    promoted_source = replace(
        source,
        provenance=replace(
            source.provenance,
            preparation_ready=True,
            claim_safe=True,
        ),
    )
    source_sha256 = hashlib.sha256(
        serialize_all_atom_system(promoted_source)
    ).hexdigest()
    report = _report(system=promoted_source)
    payload = report.to_dict()
    final_system = report.final_system

    assert payload["source_input_system_snapshot_sha256"] == source_sha256
    assert payload["derived_system_provenance_status"] == (
        "diagnostic_nonpromoted_lineage_bound"
    )
    assert payload["final_system_provenance_preparation_ready"] is False
    assert payload["final_system_provenance_claim_safe"] is False
    assert final_system.provenance.preparation_ready is False
    assert final_system.provenance.claim_safe is False
    assert final_system.provenance.operations[-1] == (
        "exact_methane_harmonic_minimization_diagnostic_coordinate_trial/1.0.0"
    )
    assert source_sha256 in final_system.provenance.parent_sha256


def test_checkpoint_tampering_duplicate_keys_and_noncanonical_json_reject() -> None:
    checkpoint_bytes = _report().checkpoint_bytes(1)
    document = json.loads(checkpoint_bytes)

    counter_tamper = dict(document)
    counter_tamper["total_trial_count"] += 1
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        deserialize_exact_methane_harmonic_minimization_checkpoint(
            _rehashed_checkpoint(counter_tamper)
        )
    assert exc_info.value.code == "checkpoint_replay_mismatch"

    state_tamper = dict(document)
    state_tamper["current_system_snapshot_base64"] = state_tamper[
        "initial_system_snapshot_base64"
    ]
    state_tamper["current_system_snapshot_sha256"] = state_tamper[
        "initial_system_snapshot_sha256"
    ]
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        deserialize_exact_methane_harmonic_minimization_checkpoint(
            _rehashed_checkpoint(state_tamper)
        )
    assert exc_info.value.code == "checkpoint_replay_mismatch"

    authority_tamper = dict(document)
    authority_tamper["minimization_authorized"] = True
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        deserialize_exact_methane_harmonic_minimization_checkpoint(
            _rehashed_checkpoint(authority_tamper)
        )
    assert exc_info.value.code == "checkpoint_authority_mismatch"

    embedded_authority_tamper = json.loads(checkpoint_bytes)
    embedded_system_bytes = base64.b64decode(
        embedded_authority_tamper["current_system_snapshot_base64"]
    )
    embedded_system = json.loads(embedded_system_bytes)
    embedded_system["provenance"]["claim_safe"] = True
    embedded_system_bytes = _canonical_json(embedded_system)
    embedded_authority_tamper["current_system_snapshot_base64"] = base64.b64encode(
        embedded_system_bytes
    ).decode("ascii")
    embedded_authority_tamper["current_system_snapshot_sha256"] = hashlib.sha256(
        embedded_system_bytes
    ).hexdigest()
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        deserialize_exact_methane_harmonic_minimization_checkpoint(
            _rehashed_checkpoint(embedded_authority_tamper)
        )
    assert exc_info.value.code == "checkpoint_embedded_authority_mismatch"

    config_tamper = json.loads(checkpoint_bytes)
    config_tamper["config"]["max_accepted_steps"] = True
    config_core = {
        key: value
        for key, value in config_tamper["config"].items()
        if key != "config_sha256"
    }
    config_tamper["config"]["config_sha256"] = hashlib.sha256(
        _canonical_json(config_core)
    ).hexdigest()
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        deserialize_exact_methane_harmonic_minimization_checkpoint(
            _rehashed_checkpoint(config_tamper)
        )
    assert exc_info.value.code == "invalid_config"

    duplicate = b'{"schema_id":"duplicate",' + checkpoint_bytes[1:]
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        deserialize_exact_methane_harmonic_minimization_checkpoint(duplicate)
    assert exc_info.value.code == "duplicate_json_key"

    pretty = json.dumps(json.loads(checkpoint_bytes), indent=2).encode("ascii")
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        deserialize_exact_methane_harmonic_minimization_checkpoint(pretty)
    assert exc_info.value.code == "noncanonical_checkpoint"


def test_input_profile_form_binding_and_negative_zero_fail_closed() -> None:
    legacy = _parameter_set(form_bound=False)
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        _report(parameter_set=legacy)
    assert exc_info.value.code == "legacy_parameter_schema_not_supported"

    wrong_form = _parameter_set()
    object.__setattr__(wrong_form, "functional_form_id", "forged_form/9.0.0")
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        _report(parameter_set=wrong_form)
    assert exc_info.value.code == "functional_form_mismatch"

    unit_tampered = _parameter_set()
    object.__setattr__(
        unit_tampered,
        "_unit_system_items",
        (("unit_system_id", "forged"),),
    )
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        _report(parameter_set=unit_tampered)
    assert exc_info.value.code == "parameter_snapshot_failed"

    coordinates = _system().coordinates.clone()
    coordinates[0, 0, 0] = -0.0
    assert math.copysign(1.0, float(coordinates[0, 0, 0])) < 0.0
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        _report(system=_system().with_coordinates(coordinates))
    assert exc_info.value.code == "negative_zero_coordinate_not_supported"


@pytest.mark.parametrize(
    ("invalid_system", "expected_code"),
    [
        (
            lambda system: system.with_coordinates(
                system.coordinates.to(torch.float32)
            ),
            "coordinates_not_float64",
        ),
        (
            lambda system: system.with_coordinates(system.coordinates.repeat(2, 1, 1)),
            "coordinate_model_count_not_one",
        ),
        (
            lambda system: replace(
                system,
                cell=UnitCell.orthorhombic(
                    (20.0, 20.0, 20.0),
                    dtype=torch.float64,
                    periodic=(False, False, False),
                ),
            ),
            "cell_not_supported",
        ),
        (
            lambda system: system.with_coordinates(
                torch.full_like(system.coordinates, float("nan"))
            ),
            "nonfinite_coordinates",
        ),
    ],
)
def test_invalid_system_contracts_are_typed(invalid_system, expected_code) -> None:
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        _report(system=invalid_system(_system()))
    assert exc_info.value.code == expected_code


def test_singular_initial_geometry_is_rejected() -> None:
    system = _system()
    coordinates = system.coordinates.clone()
    coordinates[0, 1] = coordinates[0, 0]
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        _report(system=system.with_coordinates(coordinates))
    assert exc_info.value.code == "singular_bond_geometry"


def test_config_step_and_report_artifacts_are_structurally_hardened() -> None:
    with pytest.raises(TypeError):
        _config(max_accepted_steps=True)
    with pytest.raises(TypeError):
        _config(max_accepted_steps=257)
    with pytest.raises(TypeError):
        _config(max_line_search_trials=65)
    with pytest.raises(ValueError):
        _config(initial_step_size=0.0)
    with pytest.raises(ValueError):
        _config(backtracking_factor=1.0)
    with pytest.raises(ValueError):
        _config(armijo_coefficient=0.5)
    with pytest.raises(ValueError):
        _config(force_tolerance=0.0)
    with pytest.raises(ValueError):
        _config(force_tolerance=1.0e-5)
    with pytest.raises(TypeError):
        run_exact_methane_harmonic_minimization_diagnostic(
            _system(),
            _parameter_set(),
            config=_config(),
            pause_after_accepted_steps=True,
        )
    checkpoint_zero = run_exact_methane_harmonic_minimization_diagnostic(
        _system(),
        _parameter_set(),
        config=_config(),
        pause_after_accepted_steps=0,
    )
    assert type(checkpoint_zero) is ExactMethaneHarmonicMinimizationCheckpoint
    with pytest.raises(TypeError):
        resume_exact_methane_harmonic_minimization_diagnostic(
            serialize_exact_methane_harmonic_minimization_checkpoint(checkpoint_zero),
            pause_after_additional_accepted_steps=True,
        )
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        run_exact_methane_harmonic_minimization_diagnostic(
            _system(),
            _parameter_set(),
            config=_config(),
            pause_after_accepted_steps=2,
        )
    assert exc_info.value.code == "invalid_checkpoint_boundary"

    equilibrium_system, equilibrium_parameters = _equilibrium_system_and_parameters()
    terminal_before_pause = run_exact_methane_harmonic_minimization_diagnostic(
        equilibrium_system,
        equilibrium_parameters,
        config=_config(),
        pause_after_accepted_steps=1,
    )
    assert type(terminal_before_pause) is ExactMethaneHarmonicMinimizationReport
    assert terminal_before_pause.termination_code == "stationarity_tolerance_met"

    report = _report()
    assert not hasattr(report, "__dict__")
    step = report.accepted_steps[0]
    assert not hasattr(step, "__dict__")
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        replace(step, energy_after=step.energy_before)
    assert exc_info.value.code == "invalid_step_record"

    object.__setattr__(report, "_config_bytes", b"{}")
    with pytest.raises(ExactMethaneHarmonicMinimizationError):
        report.to_dict()

    provenance_tampered = _report()
    initial_system = deserialize_all_atom_system(
        provenance_tampered._initial_system_bytes
    )
    promoted_initial = attach_parser_observation_digest(
        replace(
            initial_system,
            provenance=replace(
                initial_system.provenance,
                preparation_ready=True,
                claim_safe=True,
            ),
        )
    )
    object.__setattr__(
        provenance_tampered,
        "_initial_system_bytes",
        serialize_all_atom_system(promoted_initial),
    )
    with pytest.raises(ExactMethaneHarmonicMinimizationError) as exc_info:
        _ = provenance_tampered.final_system
    assert exc_info.value.code == "derived_provenance_mismatch"
    with pytest.raises(ExactMethaneHarmonicMinimizationError):
        provenance_tampered.to_dict()


def test_translation_rotation_and_atom_permutation_equivariance() -> None:
    config = _config()
    system = _system()
    parameter_set = _parameter_set()
    baseline = _report(
        system=system,
        parameter_set=parameter_set,
        config=config,
    ).final_system.coordinates

    translation = torch.tensor([2.5, -3.0, 4.25], dtype=torch.float64)
    translated = _report(
        system=system.with_coordinates(system.coordinates + translation),
        parameter_set=parameter_set,
        config=config,
    ).final_system.coordinates
    assert torch.allclose(
        translated,
        baseline + translation,
        atol=2.0e-13,
        rtol=0.0,
    )

    rotation = torch.tensor(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=torch.float64,
    )
    rotated_coordinates = system.coordinates @ rotation.T
    rotated_coordinates = torch.where(
        rotated_coordinates == 0.0,
        torch.zeros_like(rotated_coordinates),
        rotated_coordinates,
    )
    rotated = _report(
        system=system.with_coordinates(rotated_coordinates),
        parameter_set=parameter_set,
        config=config,
    ).final_system.coordinates
    assert torch.allclose(
        rotated,
        baseline @ rotation.T,
        atol=2.0e-13,
        rtol=0.0,
    )

    permutation = (1, 0, 4, 2, 3)
    permuted = _report(
        system=_system(
            _permuted_methane_source(permutation),
            source_id="permuted-minimizer-methane",
        ),
        parameter_set=parameter_set,
        config=config,
    ).final_system.coordinates
    assert torch.allclose(
        permuted,
        baseline[:, list(permutation), :],
        atol=2.0e-13,
        rtol=0.0,
    )


def test_public_label_redefinition_cannot_change_artifact_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module,
        "EXACT_METHANE_HARMONIC_MINIMIZATION_DIAGNOSTIC_SCHEMA_ID",
        "forged.report/9.0.0",
    )
    monkeypatch.setattr(
        module,
        "EXACT_METHANE_HARMONIC_MINIMIZATION_CHECKPOINT_SCHEMA_ID",
        "forged.checkpoint/9.0.0",
    )
    monkeypatch.setattr(
        module,
        "EXACT_METHANE_HARMONIC_MINIMIZATION_ALGORITHM_PROTOCOL_ID",
        "forged.algorithm/9.0.0",
    )
    report = _report()
    assert report.to_dict()["schema_id"] == (
        "betelgeuze.exact_methane_harmonic_minimization_diagnostic/1.0.0"
    )
    checkpoint = json.loads(report.checkpoint_bytes(1))
    assert checkpoint["schema_id"] == (
        "betelgeuze.exact_methane_harmonic_minimization_checkpoint/1.0.0"
    )
    assert checkpoint["algorithm_protocol"]["protocol_id"] == (
        "exact_methane_cartesian_steepest_descent_strict_armijo/1.0.0"
    )


def test_same_runtime_result_is_hashseed_independent() -> None:
    script = f"""
from pathlib import Path
from betelgeuze_engine_v2.forcefield import *
from betelgeuze_engine_v2.molecular import parse_sdf_v2000
s = parse_sdf_v2000(Path({str(METHANE)!r}).read_bytes(), source_id='seed').system
p = ExactMethaneBondAngleParameterSet(
    parameter_set_id='seed_fixture', parameter_set_version='1.0.0',
    derivation_status='declared_contract_fixture',
    bond_parameter=HarmonicBondParameter(
        parameter_id='b', equilibrium_length_angstrom=1.0,
        force_constant_kj_mol_angstrom2=2.0),
    angle_parameter=HarmonicAngleParameter(
        parameter_id='a', equilibrium_angle_radian=1.0,
        force_constant_kj_mol_radian2=4.0),
    artifact_schema_version='1.1.0',
    functional_form_id=EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID)
c = ExactMethaneHarmonicMinimizationConfig(max_accepted_steps=1)
r = run_exact_methane_harmonic_minimization_diagnostic(s, p, config=c)
print(r.report_sha256)
"""
    results = []
    for seed in ("1", "8675309"):
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = seed
        environment["PYTHONPATH"] = str(REPOSITORY_ROOT)
        results.append(
            subprocess.check_output(
                [sys.executable, "-c", script],
                cwd=REPOSITORY_ROOT,
                env=environment,
                text=True,
            ).strip()
        )
    assert results[0] == results[1]


def test_module_has_no_engine_or_orchestrator_dispatch() -> None:
    source_path = (
        REPOSITORY_ROOT
        / "betelgeuze_engine_v2"
        / "forcefield"
        / "harmonic_minimization.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "betelgeuze_engine_v2.engine" not in imported_modules
    assert all("orchestrat" not in name for name in imported_modules)

    engine_source = (REPOSITORY_ROOT / "betelgeuze_engine_v2" / "engine.py").read_text(
        encoding="utf-8"
    )
    for forbidden_token in (
        "harmonic_minimization",
        "run_exact_methane_harmonic_minimization_diagnostic",
        "resume_exact_methane_harmonic_minimization_diagnostic",
    ):
        assert forbidden_token not in engine_source
