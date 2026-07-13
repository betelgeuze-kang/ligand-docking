from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import pytest
import torch

from betelgeuze_engine_v2.forcefield import (
    DIAGNOSTIC_VIRIAL_DEFINITION,
    EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID,
    EXACT_METHANE_HARMONIC_VIRIAL_CONVENTION_ID,
    EXACT_METHANE_HARMONIC_VIRIAL_DIAGNOSTIC_CLAIM_SCOPE,
    EXACT_METHANE_HARMONIC_VIRIAL_DIAGNOSTIC_SCHEMA_ID,
    ExactMethaneBondAngleParameterSet,
    ExactMethaneHarmonicVirialDiagnosticError,
    ExactMethaneHarmonicVirialDiagnosticReport,
    HarmonicAngleParameter,
    HarmonicBondParameter,
    analyze_exact_methane_harmonic_diagnostic,
    analyze_exact_methane_harmonic_virial_diagnostic,
    serialize_exact_methane_bond_angle_parameter_set,
)
from betelgeuze_engine_v2.forcefield import (
    harmonic_virial_diagnostics as virial_module,
)
from betelgeuze_engine_v2.molecular import UnitCell, parse_sdf_v2000


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "v2_1_ingest_corpus"
METHANE = FIXTURES / "methane_explicit_h.sdf"
C13_METHANE = FIXTURES / "methane_c13_explicit_h.sdf"
EXPECTED_REPORT_KEYS = frozenset(
    {
        "angle_anchor_policy",
        "angle_term_count",
        "angle_terms",
        "angle_virial_tensor_ieee754_binary64_be",
        "blockers",
        "bond_anchor_policy",
        "bond_term_count",
        "bond_terms",
        "bond_virial_tensor_ieee754_binary64_be",
        "canonical_topology_sha256",
        "claim_safe",
        "claim_scope",
        "complete_virial_assessed",
        "coordinate_unit",
        "diagnostic_evaluation_performed",
        "diagnostic_status",
        "energy_evaluation_authorized",
        "execution_authorized",
        "force_evaluation_authorized",
        "force_unit",
        "functional_form_binding_status",
        "functional_form_id",
        "global_parameter_coverage_complete",
        "input_snapshot_sha256",
        "inventory_report_sha256",
        "minimization_authorized",
        "nonbonded_status",
        "numeric_encoding",
        "parameter_artifact_bytes_sha256",
        "parameter_artifact_schema_version",
        "parameter_assignment_report_sha256",
        "parameter_assignment_sha256",
        "parameter_derivation_status",
        "parameter_functional_form_id",
        "parameter_payload_sha256",
        "parameter_set_sha256",
        "parameterability_assessed",
        "parameterizable",
        "periodic_status",
        "physics_supported",
        "preparation_ready",
        "pressure_status",
        "report_sha256",
        "runtime_eligible",
        "schema_id",
        "schema_version",
        "scientific_validation_status",
        "scientific_validity_green",
        "scoped_bonded_virial_assessed",
        "simulation_ready",
        "stress_status",
        "tensor_index_order",
        "total_virial_tensor_ieee754_binary64_be",
        "total_virial_trace_ieee754_binary64_be",
        "virial_convention_id",
        "virial_definition",
        "virial_evaluation_authorized",
        "virial_status",
        "virial_unit",
        "volume_status",
    }
)


def _system(source: bytes | None = None, *, source_id: str = "virial-methane"):
    return parse_sdf_v2000(
        METHANE.read_bytes() if source is None else source,
        source_id=source_id,
    ).system


def _parameter_set(
    *,
    bond_equilibrium: float = 1.0,
    bond_force_constant: float = 2.0,
    angle_equilibrium: float = 1.0,
    angle_force_constant: float = 4.0,
    form_bound: bool = True,
) -> ExactMethaneBondAngleParameterSet:
    return ExactMethaneBondAngleParameterSet(
        parameter_set_id="nonphysical_harmonic_virial_fixture",
        parameter_set_version="1.0.0",
        derivation_status="declared_contract_fixture",
        bond_parameter=HarmonicBondParameter(
            parameter_id="virial_ch_bond",
            equilibrium_length_angstrom=bond_equilibrium,
            force_constant_kj_mol_angstrom2=bond_force_constant,
        ),
        angle_parameter=HarmonicAngleParameter(
            parameter_id="virial_hch_angle",
            equilibrium_angle_radian=angle_equilibrium,
            force_constant_kj_mol_radian2=angle_force_constant,
        ),
        artifact_schema_version="1.1.0" if form_bound else "1.0.0",
        functional_form_id=(
            EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID if form_bound else None
        ),
    )


def _report(system=None, parameter_set=None):
    return analyze_exact_methane_harmonic_virial_diagnostic(
        _system() if system is None else system,
        _parameter_set() if parameter_set is None else parameter_set,
    )


def _tensor(matrix) -> torch.Tensor:
    return torch.tensor(matrix, dtype=torch.float64)


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


def test_contract_term_decomposition_hash_and_canonical_binary64() -> None:
    report = _report()
    repeated = _report()
    payload = report.to_dict()

    assert frozenset(payload) == EXPECTED_REPORT_KEYS

    assert payload["schema_id"] == (
        EXACT_METHANE_HARMONIC_VIRIAL_DIAGNOSTIC_SCHEMA_ID
    )
    assert payload["claim_scope"] == (
        EXACT_METHANE_HARMONIC_VIRIAL_DIAGNOSTIC_CLAIM_SCOPE
    )
    assert payload["virial_convention_id"] == (
        EXACT_METHANE_HARMONIC_VIRIAL_CONVENTION_ID
    )
    assert payload["virial_definition"] == DIAGNOSTIC_VIRIAL_DEFINITION
    assert payload["tensor_index_order"] == [
        "force_axis",
        "displacement_axis",
    ]
    assert payload["parameter_artifact_schema_version"] == "1.1.0"
    assert payload["parameter_functional_form_id"] == (
        EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
    )
    assert payload["functional_form_binding_status"] == (
        "parameter_payload_bound_match"
    )
    assert len(report.bond_terms) == payload["bond_term_count"] == 4
    assert len(report.angle_terms) == payload["angle_term_count"] == 6
    assert all(
        term.anchor_atom == term.identity.atom_j for term in report.bond_terms
    )
    assert all(
        term.anchor_atom == term.identity.center_atom
        for term in report.angle_terms
    )

    bond_sum = torch.stack(
        [_tensor(term.virial_kj_mol) for term in report.bond_terms]
    ).sum(dim=0)
    angle_sum = torch.stack(
        [_tensor(term.virial_kj_mol) for term in report.angle_terms]
    ).sum(dim=0)
    assert torch.allclose(
        bond_sum,
        _tensor(report.bond_virial_kj_mol),
        atol=2.0e-15,
        rtol=0.0,
    )
    assert torch.allclose(
        angle_sum,
        _tensor(report.angle_virial_kj_mol),
        atol=2.0e-15,
        rtol=0.0,
    )
    assert torch.allclose(
        bond_sum + angle_sum,
        report.virial_tensor(),
        atol=2.0e-15,
        rtol=0.0,
    )
    assert report.total_virial_trace_kj_mol == pytest.approx(
        torch.trace(report.virial_tensor()).item(),
        abs=2.0e-15,
    )
    assert report.to_dict() == repeated.to_dict()
    assert report == repeated
    assert report.matches(_system(), _parameter_set()) is True
    assert report.virial_tensor().shape == (3, 3)
    assert report.virial_tensor().dtype is torch.float64
    assert report.virial_tensor().device.type == "cpu"

    core = {key: value for key, value in payload.items() if key != "report_sha256"}
    assert payload["report_sha256"] == hashlib.sha256(
        json.dumps(
            core,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    canonical_bytes = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    assert report.report_sha256 == (
        "08a4e81049c7fa1d3902b26c47c83df830ba6c93e371adcc47ecd1b4eeb52305"
    )
    assert len(canonical_bytes) == 7945
    assert hashlib.sha256(canonical_bytes).hexdigest() == (
        "23edd5cbb71f18b1483a005e42322dcec89da166518da08e634b76277ed8c8c2"
    )
    encoded_values = (
        *(
            value
            for row in payload["total_virial_tensor_ieee754_binary64_be"]
            for value in row
        ),
        payload["total_virial_trace_ieee754_binary64_be"],
    )
    assert all(len(value) == 16 and value == value.lower() for value in encoded_values)
    assert "8000000000000000" not in encoded_values


def test_all_nine_affine_components_and_isotropic_trace_match_energy_fd() -> None:
    system = _system()
    parameter_set = _parameter_set()
    report = _report(system, parameter_set)
    analytic = report.virial_tensor()
    finite_difference = torch.empty_like(analytic)
    identity = torch.eye(3, dtype=torch.float64)
    step = 1.0e-6

    for force_axis in range(3):
        for displacement_axis in range(3):
            strain = torch.zeros((3, 3), dtype=torch.float64)
            strain[force_axis, displacement_axis] = step
            plus = system.with_coordinates(
                system.coordinates @ (identity + strain).T
            )
            minus = system.with_coordinates(
                system.coordinates @ (identity - strain).T
            )
            plus_energy = analyze_exact_methane_harmonic_diagnostic(
                plus,
                parameter_set,
            ).total_energy_kj_mol
            minus_energy = analyze_exact_methane_harmonic_diagnostic(
                minus,
                parameter_set,
            ).total_energy_kj_mol
            finite_difference[force_axis, displacement_axis] = -(
                plus_energy - minus_energy
            ) / (2.0 * step)

    assert torch.allclose(
        analytic,
        finite_difference,
        atol=2.0e-9,
        rtol=2.0e-8,
    )

    isotropic_step = 1.0e-5
    plus_energy = analyze_exact_methane_harmonic_diagnostic(
        system.with_coordinates(system.coordinates * (1.0 + isotropic_step)),
        parameter_set,
    ).total_energy_kj_mol
    minus_energy = analyze_exact_methane_harmonic_diagnostic(
        system.with_coordinates(system.coordinates * (1.0 - isotropic_step)),
        parameter_set,
    ).total_energy_kj_mol
    isotropic_derivative = -(plus_energy - minus_energy) / (
        2.0 * isotropic_step
    )
    assert report.total_virial_trace_kj_mol == pytest.approx(
        isotropic_derivative,
        abs=2.0e-9,
        rel=2.0e-8,
    )


def test_translation_and_rotation_covariance() -> None:
    system = _system()
    coordinates = system.coordinates.clone()
    coordinates[0, 1] += torch.tensor(
        [0.07, -0.03, 0.02],
        dtype=torch.float64,
    )
    system = system.with_coordinates(coordinates)
    parameter_set = _parameter_set()
    baseline = _report(system, parameter_set).virial_tensor()
    translation = torch.tensor([2.5, -3.0, 4.25], dtype=torch.float64)
    translated = _report(
        system.with_coordinates(system.coordinates + translation),
        parameter_set,
    ).virial_tensor()
    rotation = torch.tensor(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=torch.float64,
    )
    rotated = _report(
        system.with_coordinates(system.coordinates @ rotation.T),
        parameter_set,
    ).virial_tensor()

    assert torch.allclose(translated, baseline, atol=2.0e-14, rtol=2.0e-14)
    assert torch.allclose(
        rotated,
        rotation @ baseline @ rotation.T,
        atol=2.0e-14,
        rtol=2.0e-14,
    )


def test_atom_permutation_invariance_on_distorted_geometry() -> None:
    permutation = (1, 0, 4, 2, 3)
    old_to_new = {old: new for new, old in enumerate(permutation)}
    baseline_system = _system()
    baseline_coordinates = baseline_system.coordinates.clone()
    displacement = torch.tensor([0.05, -0.02, 0.03], dtype=torch.float64)
    baseline_coordinates[0, 1] += displacement
    baseline_system = baseline_system.with_coordinates(baseline_coordinates)

    permuted_system = _system(
        _permuted_methane_source(permutation),
        source_id="permuted-virial-methane",
    )
    permuted_coordinates = permuted_system.coordinates.clone()
    permuted_coordinates[0, old_to_new[1]] += displacement
    permuted_system = permuted_system.with_coordinates(permuted_coordinates)

    baseline = _report(baseline_system, _parameter_set())
    permuted = _report(permuted_system, _parameter_set())
    assert torch.allclose(
        permuted.virial_tensor(),
        baseline.virial_tensor(),
        atol=2.0e-14,
        rtol=2.0e-14,
    )
    assert permuted.total_virial_trace_kj_mol == pytest.approx(
        baseline.total_virial_trace_kj_mol,
        abs=2.0e-14,
    )
    assert permuted.input_snapshot_sha256 != baseline.input_snapshot_sha256


def test_zero_torque_implies_symmetric_total_virial() -> None:
    system = _system()
    coordinates = system.coordinates.clone()
    coordinates[0, 2] += torch.tensor(
        [-0.04, 0.06, 0.01],
        dtype=torch.float64,
    )
    system = system.with_coordinates(coordinates)
    parameter_set = _parameter_set()
    harmonic = analyze_exact_methane_harmonic_diagnostic(system, parameter_set)
    virial = _report(system, parameter_set).virial_tensor()
    torque = torch.cross(
        system.coordinates[0],
        harmonic.forces_tensor()[0],
        dim=-1,
    ).sum(dim=0)

    assert torch.allclose(
        torque,
        torch.zeros(3, dtype=torch.float64),
        atol=2.0e-13,
        rtol=0.0,
    )
    assert torch.allclose(
        virial - virial.T,
        torch.zeros((3, 3), dtype=torch.float64),
        atol=2.0e-13,
        rtol=0.0,
    )


def test_equilibrium_geometry_has_zero_term_and_total_virials() -> None:
    system = _system()
    coordinates = system.coordinates[0]
    bond_equilibrium = float(torch.linalg.vector_norm(coordinates[1]).item())
    angle_equilibrium = math.atan2(
        float(
            torch.linalg.vector_norm(
                torch.cross(coordinates[1], coordinates[2], dim=0)
            ).item()
        ),
        float(torch.dot(coordinates[1], coordinates[2]).item()),
    )
    report = _report(
        system,
        _parameter_set(
            bond_equilibrium=bond_equilibrium,
            angle_equilibrium=angle_equilibrium,
        ),
    )

    assert torch.allclose(
        report.virial_tensor(),
        torch.zeros((3, 3), dtype=torch.float64),
        atol=2.0e-13,
        rtol=0.0,
    )
    assert all(
        torch.allclose(
            _tensor(term.virial_kj_mol),
            torch.zeros((3, 3), dtype=torch.float64),
            atol=2.0e-13,
            rtol=0.0,
        )
        for term in (*report.bond_terms, *report.angle_terms)
    )
    assert report.to_dict()["total_virial_trace_ieee754_binary64_be"] == (
        "0000000000000000"
    )


@pytest.mark.parametrize(
    ("kind", "expected_code"),
    [
        ("coincident", "singular_bond_geometry"),
        ("collinear", "singular_angle_geometry"),
    ],
)
def test_singular_geometries_fail_closed(kind: str, expected_code: str) -> None:
    system = _system()
    coordinates = system.coordinates.clone()
    if kind == "coincident":
        coordinates[0, 1] = coordinates[0, 0]
    else:
        coordinates[0, 1] = torch.tensor([1.0, 0.0, 0.0])
        coordinates[0, 2] = torch.tensor([2.0, 0.0, 0.0])

    with pytest.raises(ExactMethaneHarmonicVirialDiagnosticError) as exc_info:
        _report(system.with_coordinates(coordinates), _parameter_set())
    assert exc_info.value.code == expected_code
    assert exc_info.value.blockers == (
        f"harmonic_virial_diagnostic_{expected_code}",
    )


def test_input_profile_dtype_cell_and_overflow_fail_closed() -> None:
    system = _system()
    cases = (
        (
            system.with_coordinates(system.coordinates.to(torch.float32)),
            _parameter_set(),
            "coordinates_not_float64",
        ),
        (
            replace(
                system,
                cell=UnitCell.orthorhombic(
                    (20.0, 20.0, 20.0),
                    dtype=torch.float64,
                    periodic=(False, False, False),
                ),
            ),
            _parameter_set(),
            "cell_not_supported",
        ),
        (
            system.with_coordinates(system.coordinates.repeat(2, 1, 1)),
            _parameter_set(),
            "coordinate_model_count_not_one",
        ),
        (
            system.with_coordinates(
                torch.full_like(system.coordinates, float("nan"))
            ),
            _parameter_set(),
            "nonfinite_coordinates",
        ),
        (
            replace(system, coordinate_unit="nanometer"),
            _parameter_set(),
            "unsupported_coordinate_unit",
        ),
        (
            _system(C13_METHANE.read_bytes(), source_id="c13-virial"),
            _parameter_set(),
            "assignment_unavailable",
        ),
        (
            system,
            _parameter_set(
                bond_equilibrium=0.1,
                bond_force_constant=1.0e308,
            ),
            "nonfinite_result",
        ),
    )
    for invalid_system, parameter_set, expected_code in cases:
        with pytest.raises(
            ExactMethaneHarmonicVirialDiagnosticError
        ) as exc_info:
            _report(invalid_system, parameter_set)
        assert exc_info.value.code == expected_code


def test_legacy_wrong_form_and_mutated_parameters_are_typed_rejections() -> None:
    legacy = _parameter_set(form_bound=False)
    with pytest.raises(ExactMethaneHarmonicVirialDiagnosticError) as exc_info:
        _report(parameter_set=legacy)
    assert exc_info.value.code == "legacy_parameter_schema_not_supported"

    wrong_form = _parameter_set()
    object.__setattr__(wrong_form, "functional_form_id", "wrong_form/1.0.0")
    with pytest.raises(ExactMethaneHarmonicVirialDiagnosticError) as exc_info:
        _report(parameter_set=wrong_form)
    assert exc_info.value.code == "functional_form_mismatch"

    mutated = _parameter_set()
    object.__setattr__(mutated.bond_parameter, "force_constant_kj_mol_angstrom2", 0.0)
    with pytest.raises(ExactMethaneHarmonicVirialDiagnosticError) as exc_info:
        _report(parameter_set=mutated)
    assert exc_info.value.code == "parameter_snapshot_failed"

    unit_tampered = _parameter_set()
    object.__setattr__(
        unit_tampered,
        "_unit_system_items",
        (("unit_system_id", "forged"),),
    )
    with pytest.raises(ExactMethaneHarmonicVirialDiagnosticError) as exc_info:
        _report(parameter_set=unit_tampered)
    assert exc_info.value.code == "parameter_snapshot_failed"


def test_report_is_slots_factory_only_and_recomputes_tampered_snapshots() -> None:
    report = _report()
    with pytest.raises(TypeError):
        ExactMethaneHarmonicVirialDiagnosticReport()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        ExactMethaneHarmonicVirialDiagnosticReport(  # type: ignore[call-arg]
            _system(),
            _parameter_set(),
            total_virial_kj_mol=((0.0, 0.0, 0.0),) * 3,
        )
    assert not hasattr(report, "__dict__")
    with pytest.raises(AttributeError):
        object.__setattr__(report, "_derive", lambda: None)
    with pytest.raises(AttributeError):
        object.__setattr__(report, "total_virial_kj_mol", ((0.0,) * 3,) * 3)

    object.__setattr__(report, "_system_snapshot_bytes", b"{}")
    with pytest.raises(ExactMethaneHarmonicVirialDiagnosticError) as exc_info:
        report.to_dict()
    assert exc_info.value.code == "snapshot_recomputation_failed"
    with pytest.raises(ExactMethaneHarmonicVirialDiagnosticError) as exc_info:
        _ = report.physics_supported
    assert exc_info.value.code == "snapshot_recomputation_failed"

    noncanonical = _report()
    parameter_document = json.loads(noncanonical._parameter_snapshot_bytes)
    pretty_bytes = json.dumps(
        parameter_document,
        indent=2,
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    assert pretty_bytes != noncanonical._parameter_snapshot_bytes
    object.__setattr__(noncanonical, "_parameter_snapshot_bytes", pretty_bytes)
    with pytest.raises(ExactMethaneHarmonicVirialDiagnosticError) as exc_info:
        noncanonical.report_sha256
    assert exc_info.value.code == "snapshot_recomputation_failed"


def test_versioned_labels_and_form_binding_use_frozen_literals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _report().to_dict()
    monkeypatch.setattr(
        virial_module,
        "EXACT_METHANE_HARMONIC_VIRIAL_DIAGNOSTIC_SCHEMA_ID",
        "forged.schema/9.0.0",
    )
    monkeypatch.setattr(
        virial_module,
        "EXACT_METHANE_HARMONIC_VIRIAL_DIAGNOSTIC_SCHEMA_VERSION",
        "9.0.0",
    )
    monkeypatch.setattr(
        virial_module,
        "EXACT_METHANE_HARMONIC_VIRIAL_CONVENTION_ID",
        "forged_convention/9.0.0",
    )
    monkeypatch.setattr(
        virial_module,
        "EXACT_METHANE_HARMONIC_VIRIAL_DIAGNOSTIC_CLAIM_SCOPE",
        "forged_claim_scope",
    )
    monkeypatch.setattr(
        virial_module,
        "DIAGNOSTIC_VIRIAL_DEFINITION",
        "forged definition",
    )

    assert _report().to_dict() == baseline


def test_parameter_and_coordinate_changes_bind_distinct_hashes() -> None:
    system = _system()
    baseline_parameters = _parameter_set()
    baseline = _report(system, baseline_parameters)
    moved_coordinates = system.coordinates.clone()
    moved_coordinates[0, 1, 0] += 0.05
    moved = _report(
        system.with_coordinates(moved_coordinates),
        baseline_parameters,
    )
    changed_parameters = _parameter_set(bond_force_constant=3.0)
    changed = _report(system, changed_parameters)

    assert moved.input_snapshot_sha256 != baseline.input_snapshot_sha256
    assert moved.report_sha256 != baseline.report_sha256
    assert not torch.equal(moved.virial_tensor(), baseline.virial_tensor())
    assert changed.parameter_artifact_bytes_sha256 == hashlib.sha256(
        serialize_exact_methane_bond_angle_parameter_set(changed_parameters)
    ).hexdigest()
    assert changed.parameter_artifact_bytes_sha256 != (
        baseline.parameter_artifact_bytes_sha256
    )
    assert changed.report_sha256 != baseline.report_sha256


def test_hash_is_deterministic_across_python_hash_seeds() -> None:
    script = f"""
from pathlib import Path
from betelgeuze_engine_v2.forcefield import *
from betelgeuze_engine_v2.molecular import parse_sdf_v2000
system = parse_sdf_v2000(Path({str(METHANE)!r}).read_bytes(), source_id='virial-methane').system
parameters = ExactMethaneBondAngleParameterSet(
    parameter_set_id='nonphysical_harmonic_virial_fixture',
    parameter_set_version='1.0.0',
    derivation_status='declared_contract_fixture',
    bond_parameter=HarmonicBondParameter('virial_ch_bond', 1.0, 2.0),
    angle_parameter=HarmonicAngleParameter('virial_hch_angle', 1.0, 4.0),
    artifact_schema_version='1.1.0',
    functional_form_id=EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID,
)
print(analyze_exact_methane_harmonic_virial_diagnostic(system, parameters).report_sha256)
"""
    outputs = []
    for seed in ("1", "777"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        outputs.append(
            subprocess.run(
                [sys.executable, "-c", script],
                cwd=REPOSITORY_ROOT,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    assert outputs[0] == outputs[1] == _report().report_sha256


def test_nonpromotion_statuses_are_explicit_and_all_gates_remain_false() -> None:
    report = _report()
    payload = report.to_dict()

    assert report.diagnostic_evaluation_performed is True
    assert report.scoped_bonded_virial_assessed is True
    assert report.complete_virial_assessed is False
    assert report.physics_supported is False
    assert report.scientific_validity_green is False
    assert report.parameterability_assessed is False
    assert report.parameterizable is False
    assert report.global_parameter_coverage_complete is False
    assert report.preparation_ready is False
    assert report.runtime_eligible is False
    assert report.execution_authorized is False
    assert report.energy_evaluation_authorized is False
    assert report.force_evaluation_authorized is False
    assert report.virial_evaluation_authorized is False
    assert report.minimization_authorized is False
    assert report.simulation_ready is False
    assert report.claim_safe is False
    assert payload["virial_status"] == (
        "scoped_nonperiodic_bonded_virial_evaluated"
    )
    assert payload["scoped_bonded_virial_assessed"] is True
    assert payload["complete_virial_assessed"] is False
    for status in (
        "pressure_status",
        "stress_status",
        "volume_status",
        "periodic_status",
        "nonbonded_status",
    ):
        assert payload[status] == "not_assessed"
    assert "nonbonded_terms_not_evaluated" in report.blockers
    assert "complete_virial_not_assessed" in report.blockers
    assert "runtime_virial_evaluation_not_authorized" in report.blockers


def test_module_has_no_engine_or_orchestrator_dispatch() -> None:
    module_path = Path(virial_module.__file__).resolve()
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "betelgeuze_engine_v2.engine" not in imported_modules
    engine_source = (
        REPOSITORY_ROOT / "betelgeuze_engine_v2" / "engine.py"
    ).read_text(encoding="utf-8")
    for forbidden_token in (
        "harmonic_virial_diagnostics",
        "analyze_exact_methane_harmonic_virial_diagnostic",
        "ExactMethaneHarmonicVirialDiagnosticReport",
    ):
        assert forbidden_token not in engine_source
