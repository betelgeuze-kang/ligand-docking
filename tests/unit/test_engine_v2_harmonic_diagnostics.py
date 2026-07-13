from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

import pytest
import torch

from betelgeuze_engine_v2.forcefield import harmonic_diagnostics as diagnostic_module
from betelgeuze_engine_v2.forcefield import parameters as parameter_module
from betelgeuze_engine_v2.forcefield import (
    EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1,
    EXACT_METHANE_HARMONIC_DIAGNOSTIC_CLAIM_SCOPE,
    EXACT_METHANE_HARMONIC_DIAGNOSTIC_SCHEMA_ID,
    EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID,
    ExactMethaneHarmonicDiagnosticError,
    ExactMethaneHarmonicDiagnosticReport,
    analyze_exact_methane_bond_angle_parameter_assignment,
    analyze_exact_methane_harmonic_diagnostic,
    serialize_exact_methane_bond_angle_parameter_set,
)
from betelgeuze_engine_v2.forcefield.parameters import (
    ExactMethaneBondAngleParameterSet,
    HarmonicAngleParameter,
    HarmonicBondParameter,
)
from betelgeuze_engine_v2.molecular import (
    UnitCell,
    parse_sdf_v2000,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "v2_1_ingest_corpus"
METHANE = FIXTURES / "methane_explicit_h.sdf"
C13_METHANE = FIXTURES / "methane_c13_explicit_h.sdf"


def _system(source: bytes | None = None, *, source_id: str = "diagnostic-methane"):
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
    artifact_schema_version: str = "1.0.0",
    functional_form_id: str | None = None,
) -> ExactMethaneBondAngleParameterSet:
    return ExactMethaneBondAngleParameterSet(
        parameter_set_id="nonphysical_harmonic_diagnostic_fixture",
        parameter_set_version="1.0.0",
        derivation_status="declared_contract_fixture",
        bond_parameter=HarmonicBondParameter(
            parameter_id="diagnostic_ch_bond",
            equilibrium_length_angstrom=bond_equilibrium,
            force_constant_kj_mol_angstrom2=bond_force_constant,
        ),
        angle_parameter=HarmonicAngleParameter(
            parameter_id="diagnostic_hch_angle",
            equilibrium_angle_radian=angle_equilibrium,
            force_constant_kj_mol_radian2=angle_force_constant,
        ),
        artifact_schema_version=artifact_schema_version,
        functional_form_id=functional_form_id,
    )


def _form_bound_parameter_set() -> ExactMethaneBondAngleParameterSet:
    return _parameter_set(
        artifact_schema_version=(
            EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1
        ),
        functional_form_id=EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID,
    )


def _report(system=None, parameter_set=None):
    return analyze_exact_methane_harmonic_diagnostic(
        _system() if system is None else system,
        _parameter_set() if parameter_set is None else parameter_set,
    )


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


def test_exact_term_decomposition_snapshot_binding_and_canonical_encoding() -> None:
    report = _report()
    repeated = _report()
    payload = report.to_dict()

    assert payload["schema_id"] == EXACT_METHANE_HARMONIC_DIAGNOSTIC_SCHEMA_ID
    assert payload["claim_scope"] == (
        EXACT_METHANE_HARMONIC_DIAGNOSTIC_CLAIM_SCOPE
    )
    assert payload["functional_form_id"] == (
        EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
    )
    assert payload["energy_convention"] == "E(q)=0.5*k*(q-q0)^2"
    assert payload["bond_term_count"] == len(report.bond_terms) == 4
    assert payload["angle_term_count"] == len(report.angle_terms) == 6
    assert report.bond_energy_kj_mol == pytest.approx(
        math.fsum(term.energy_kj_mol for term in report.bond_terms),
        abs=0.0,
    )
    assert report.angle_energy_kj_mol == pytest.approx(
        math.fsum(term.energy_kj_mol for term in report.angle_terms),
        abs=0.0,
    )
    assert report.total_energy_kj_mol == pytest.approx(
        report.bond_energy_kj_mol + report.angle_energy_kj_mol,
        abs=0.0,
    )
    assert report.assignment_report.parameter_assignment_sha256 is not None
    assert len(report.input_snapshot_sha256) == 64
    assert len(report.parameter_artifact_bytes_sha256) == 64
    assert report.to_dict() == repeated.to_dict()
    assert report == repeated
    assert report.matches(_system(), _parameter_set()) is True
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
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
    assert all(
        len(payload[key]) == 16
        and payload[key] == payload[key].lower()
        for key in (
            "bond_energy_ieee754_binary64_be",
            "angle_energy_ieee754_binary64_be",
            "total_energy_ieee754_binary64_be",
        )
    )
    assert report.forces_tensor().shape == (1, 5, 3)
    assert report.forces_tensor().dtype is torch.float64


def test_analytic_force_matches_central_finite_difference_for_all_dofs() -> None:
    system = _system()
    parameter_set = _parameter_set()
    analytic = _report(system, parameter_set).forces_tensor()
    finite_difference = torch.empty_like(analytic)
    step = 1.0e-6

    for atom_index in range(system.atom_count):
        for axis in range(3):
            plus_coordinates = system.coordinates.clone()
            minus_coordinates = system.coordinates.clone()
            plus_coordinates[0, atom_index, axis] += step
            minus_coordinates[0, atom_index, axis] -= step
            plus_energy = _report(
                system.with_coordinates(plus_coordinates),
                parameter_set,
            ).total_energy_kj_mol
            minus_energy = _report(
                system.with_coordinates(minus_coordinates),
                parameter_set,
            ).total_energy_kj_mol
            finite_difference[0, atom_index, axis] = -(
                plus_energy - minus_energy
            ) / (2.0 * step)

    assert torch.allclose(
        analytic,
        finite_difference,
        atol=1.0e-7,
        rtol=1.0e-6,
    )

    reference_coordinates = system.coordinates.detach().clone().requires_grad_(True)
    assignment = analyze_exact_methane_bond_angle_parameter_assignment(
        system,
        parameter_set,
    )
    reference_energy = torch.zeros((), dtype=torch.float64)
    for term in assignment.bond_assignments:
        atom_i, atom_j = term.identity.atom_i, term.identity.atom_j
        distance = torch.linalg.vector_norm(
            reference_coordinates[0, atom_i]
            - reference_coordinates[0, atom_j]
        )
        reference_energy = reference_energy + (distance - 1.0).square()
    for term in assignment.angle_assignments:
        atom_i = term.identity.outer_atom_i
        center = term.identity.center_atom
        atom_k = term.identity.outer_atom_k
        vector_i = (
            reference_coordinates[0, atom_i]
            - reference_coordinates[0, center]
        )
        vector_k = (
            reference_coordinates[0, atom_k]
            - reference_coordinates[0, center]
        )
        angle = torch.atan2(
            torch.linalg.vector_norm(torch.cross(vector_i, vector_k, dim=0)),
            torch.dot(vector_i, vector_k),
        )
        reference_energy = reference_energy + 2.0 * (angle - 1.0).square()
    (reference_gradient,) = torch.autograd.grad(
        reference_energy,
        reference_coordinates,
    )
    assert reference_energy.item() == pytest.approx(
        _report(system, parameter_set).total_energy_kj_mol,
        abs=1.0e-12,
    )
    assert torch.allclose(
        analytic,
        -reference_gradient,
        atol=2.0e-14,
        rtol=2.0e-14,
    )


def test_translation_rotation_net_force_and_torque_contracts() -> None:
    system = _system()
    parameter_set = _parameter_set()
    baseline = _report(system, parameter_set)
    baseline_forces = baseline.forces_tensor()
    translation = torch.tensor(
        [2.5, -3.0, 4.25],
        dtype=torch.float64,
    )
    translated = _report(
        system.with_coordinates(system.coordinates + translation),
        parameter_set,
    )
    rotation = torch.tensor(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=torch.float64,
    )
    assert torch.linalg.det(rotation).item() == pytest.approx(1.0)
    rotated = _report(
        system.with_coordinates(system.coordinates @ rotation.T),
        parameter_set,
    )

    assert translated.total_energy_kj_mol == pytest.approx(
        baseline.total_energy_kj_mol,
        abs=1.0e-12,
    )
    assert torch.allclose(
        translated.forces_tensor(),
        baseline_forces,
        atol=1.0e-12,
        rtol=1.0e-12,
    )
    assert rotated.total_energy_kj_mol == pytest.approx(
        baseline.total_energy_kj_mol,
        abs=1.0e-12,
    )
    assert torch.allclose(
        rotated.forces_tensor(),
        baseline_forces @ rotation.T,
        atol=1.0e-12,
        rtol=1.0e-12,
    )
    assert torch.allclose(
        baseline_forces.sum(dim=1),
        torch.zeros((1, 3), dtype=torch.float64),
        atol=1.0e-12,
        rtol=0.0,
    )
    torque = torch.cross(
        system.coordinates[0],
        baseline_forces[0],
        dim=-1,
    ).sum(dim=0)
    assert torch.allclose(
        torque,
        torch.zeros(3, dtype=torch.float64),
        atol=1.0e-12,
        rtol=0.0,
    )


def test_atom_permutation_is_energy_invariant_and_force_equivariant() -> None:
    permutation = (1, 0, 4, 2, 3)
    baseline = _report()
    permuted_system = _system(
        _permuted_methane_source(permutation),
        source_id="permuted-diagnostic-methane",
    )
    permuted = _report(permuted_system, _parameter_set())

    assert permuted.total_energy_kj_mol == pytest.approx(
        baseline.total_energy_kj_mol,
        abs=1.0e-12,
    )
    assert torch.allclose(
        permuted.forces_tensor()[0],
        baseline.forces_tensor()[0, list(permutation)],
        atol=1.0e-12,
        rtol=1.0e-12,
    )
    assert permuted.input_snapshot_sha256 != baseline.input_snapshot_sha256
    assert (
        permuted.assignment_report.parameter_assignment_sha256
        != baseline.assignment_report.parameter_assignment_sha256
    )


def test_equilibrium_geometry_has_zero_diagnostic_energy_and_force() -> None:
    system = _system()
    coordinates = system.coordinates[0]
    bond_equilibrium = float(torch.linalg.vector_norm(coordinates[1]).item())
    first = coordinates[1]
    second = coordinates[2]
    angle_equilibrium = math.atan2(
        float(torch.linalg.vector_norm(torch.cross(first, second, dim=0)).item()),
        float(torch.dot(first, second).item()),
    )
    report = _report(
        system,
        _parameter_set(
            bond_equilibrium=bond_equilibrium,
            angle_equilibrium=angle_equilibrium,
        ),
    )

    assert report.total_energy_kj_mol == pytest.approx(0.0, abs=1.0e-28)
    assert torch.allclose(
        report.forces_tensor(),
        torch.zeros((1, 5, 3), dtype=torch.float64),
        atol=1.0e-13,
        rtol=0.0,
    )
    payload = report.to_dict()
    assert payload["total_energy_ieee754_binary64_be"] == "0000000000000000"
    assert all(
        component != "8000000000000000"
        for force in payload["atom_forces_ieee754_binary64_be"]
        for component in force.values()
    )


@pytest.mark.parametrize(
    ("kind", "expected_code"),
    [
        ("coincident", "singular_bond_geometry"),
        ("collinear", "singular_angle_geometry"),
    ],
)
def test_singular_bond_and_angle_geometry_fail_without_partial_result(
    kind: str,
    expected_code: str,
) -> None:
    system = _system()
    coordinates = system.coordinates.clone()
    if kind == "coincident":
        coordinates[0, 1] = coordinates[0, 0]
    else:
        coordinates[0, 1] = torch.tensor([1.0, 0.0, 0.0])
        coordinates[0, 2] = torch.tensor([2.0, 0.0, 0.0])

    with pytest.raises(ExactMethaneHarmonicDiagnosticError) as exc_info:
        _report(system.with_coordinates(coordinates), _parameter_set())
    assert exc_info.value.code == expected_code
    assert exc_info.value.blockers == (
        f"harmonic_diagnostic_{expected_code}",
    )


def test_input_dtype_model_cell_unit_and_finiteness_fail_closed() -> None:
    system = _system()
    cases = (
        (
            system.with_coordinates(system.coordinates.to(torch.float32)),
            "coordinates_not_float64",
        ),
        (
            system.with_coordinates(system.coordinates.repeat(2, 1, 1)),
            "coordinate_model_count_not_one",
        ),
        (
            system.with_coordinates(system.coordinates[:0]),
            "coordinate_model_count_not_one",
        ),
        (
            system.with_coordinates(
                torch.full_like(system.coordinates, float("nan"))
            ),
            "nonfinite_coordinates",
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
            "cell_not_supported",
        ),
        (replace(system, coordinate_unit="nanometer"), "unsupported_coordinate_unit"),
    )

    for invalid, expected_code in cases:
        with pytest.raises(ExactMethaneHarmonicDiagnosticError) as exc_info:
            _report(invalid, _parameter_set())
        assert exc_info.value.code == expected_code


@pytest.mark.parametrize("term_kind", ["bond", "angle"])
def test_finite_parameters_that_overflow_aggregate_fail_with_typed_error(
    term_kind: str,
) -> None:
    parameter_set = (
        _parameter_set(
            bond_equilibrium=0.1,
            bond_force_constant=1.0e308,
        )
        if term_kind == "bond"
        else _parameter_set(
            angle_equilibrium=0.1,
            angle_force_constant=2.0e307,
        )
    )
    with pytest.raises(ExactMethaneHarmonicDiagnosticError) as exc_info:
        _report(parameter_set=parameter_set)
    assert exc_info.value.code == "nonfinite_result"


def test_out_of_profile_system_and_constructor_injection_fail_closed() -> None:
    isotope = _system(C13_METHANE.read_bytes(), source_id="c13-diagnostic")
    parameter_set = _parameter_set()
    with pytest.raises(ExactMethaneHarmonicDiagnosticError) as exc_info:
        _report(isotope, parameter_set)
    assert exc_info.value.code == "assignment_unavailable"

    report = _report()
    with pytest.raises(TypeError):
        ExactMethaneHarmonicDiagnosticReport()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        ExactMethaneHarmonicDiagnosticReport(  # type: ignore[call-arg]
            _system(),
            parameter_set,
            total_energy_kj_mol=0.0,
        )
    with pytest.raises(TypeError):
        replace(report, total_energy_kj_mol=0.0)

    assert not hasattr(report, "__dict__")
    with pytest.raises(AttributeError):
        object.__setattr__(report, "_derive", lambda: None)
    with pytest.raises(AttributeError):
        object.__setattr__(report, "total_energy_kj_mol", 0.0)

    invalidated = _report()
    object.__setattr__(invalidated, "_system_snapshot_bytes", b"{}")
    with pytest.raises(ExactMethaneHarmonicDiagnosticError) as exc_info:
        invalidated.to_dict()
    assert exc_info.value.code == "snapshot_recomputation_failed"

    noncanonical = _report()
    system_document = json.loads(noncanonical._system_snapshot_bytes)
    pretty_system_bytes = json.dumps(
        system_document,
        indent=2,
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    assert pretty_system_bytes != noncanonical._system_snapshot_bytes
    object.__setattr__(
        noncanonical,
        "_system_snapshot_bytes",
        pretty_system_bytes,
    )
    with pytest.raises(ExactMethaneHarmonicDiagnosticError) as exc_info:
        noncanonical.to_dict()
    assert exc_info.value.code == "snapshot_recomputation_failed"


def test_parameter_snapshot_uses_validated_fields_not_injected_methods() -> None:
    parameter_set = _parameter_set()
    baseline = _report(_system(), parameter_set).to_dict()
    with pytest.raises(AttributeError):
        object.__setattr__(parameter_set, "to_dict", lambda: {"forged": True})
    with pytest.raises(AttributeError):
        object.__setattr__(
            parameter_set,
            "_core_dict",
            lambda: {"forged": True},
        )

    assert _report(_system(), parameter_set).to_dict() == baseline


def test_parameter_snapshot_rejects_tampered_unit_contract() -> None:
    parameter_set = _form_bound_parameter_set()
    object.__setattr__(
        parameter_set,
        "_unit_system_items",
        (("unit_system_id", "forged"),),
    )

    with pytest.raises(ExactMethaneHarmonicDiagnosticError) as exc_info:
        _report(_system(), parameter_set)
    assert exc_info.value.code == "parameter_snapshot_failed"


def test_coordinate_and_parameter_changes_are_bound_to_distinct_digests() -> None:
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
    assert moved != baseline
    assert moved.report_sha256 != baseline.report_sha256
    assert moved.total_energy_kj_mol != baseline.total_energy_kj_mol
    assert (
        changed.assignment_report.parameter_assignment_sha256
        != baseline.assignment_report.parameter_assignment_sha256
    )
    assert changed.parameter_artifact_bytes_sha256 != (
        baseline.parameter_artifact_bytes_sha256
    )
    assert changed.report_sha256 != baseline.report_sha256
    assert changed != baseline


def test_form_bound_1_1_parameters_preserve_math_and_bind_diagnostics() -> None:
    system = _system()
    legacy_parameters = _parameter_set()
    bound_parameters = _form_bound_parameter_set()
    legacy = _report(system, legacy_parameters)
    bound = _report(system, bound_parameters)
    legacy_payload = legacy.to_dict()
    bound_payload = bound.to_dict()

    assert bound.total_energy_kj_mol == legacy.total_energy_kj_mol
    assert torch.equal(bound.forces_tensor(), legacy.forces_tensor())
    assert bound.input_snapshot_sha256 == legacy.input_snapshot_sha256
    assert bound_payload["functional_form_id"] == (
        EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
    )
    assert bound_payload["parameter_functional_form_id"] == (
        EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
    )
    assert bound_payload["functional_form_binding_status"] == (
        "parameter_payload_bound_match"
    )
    assert legacy_payload["parameter_functional_form_id"] is None
    assert legacy_payload["functional_form_binding_status"] == (
        "diagnostic_owned_legacy_parameter_schema_1_0"
    )
    assert "parameter_functional_form_not_embedded_in_parameter_set_v1" in (
        legacy.blockers
    )
    assert "parameter_functional_form_not_embedded_in_parameter_set_v1" not in (
        bound.blockers
    )
    assert bound.parameter_artifact_bytes_sha256 == hashlib.sha256(
        serialize_exact_methane_bond_angle_parameter_set(bound_parameters)
    ).hexdigest()
    assert (
        bound.assignment_report.parameter_assignment_sha256
        != legacy.assignment_report.parameter_assignment_sha256
    )
    assert bound.report_sha256 != legacy.report_sha256
    assert bound.physics_supported is False
    assert bound.runtime_eligible is False
    assert bound.energy_evaluation_authorized is False
    assert bound.force_evaluation_authorized is False
    assert bound.minimization_authorized is False
    assert bound.simulation_ready is False
    assert bound.claim_safe is False

    object.__setattr__(
        bound_parameters,
        "functional_form_id",
        "harmonic_half_k_delta_squared_bond_angle/2.0.0",
    )
    with pytest.raises(ExactMethaneHarmonicDiagnosticError) as exc_info:
        _report(system, bound_parameters)
    assert exc_info.value.code == "parameter_snapshot_failed"


def test_diagnostic_form_binding_uses_frozen_canonical_identifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = _report(
        _system(),
        _form_bound_parameter_set(),
    ).to_dict()
    monkeypatch.setattr(
        parameter_module,
        "EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID",
        "forged_harmonic_form/9.0.0",
    )
    monkeypatch.setattr(
        diagnostic_module,
        "EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID",
        "forged_harmonic_form/9.0.0",
    )
    monkeypatch.setattr(
        diagnostic_module,
        "EXACT_METHANE_HARMONIC_DIAGNOSTIC_SCHEMA_VERSION",
        "9.0.0",
    )
    monkeypatch.setattr(
        diagnostic_module,
        "EXACT_METHANE_HARMONIC_DIAGNOSTIC_SCHEMA_ID",
        "forged.diagnostic/9.0.0",
    )
    monkeypatch.setattr(
        diagnostic_module,
        "EXACT_METHANE_HARMONIC_DIAGNOSTIC_CLAIM_SCOPE",
        "forged_claim_scope",
    )
    monkeypatch.setattr(
        diagnostic_module,
        "EXACT_METHANE_HARMONIC_SINGULARITY_POLICY_ID",
        "forged_singularity_policy/9.0.0",
    )
    monkeypatch.setattr(
        diagnostic_module,
        "DIAGNOSTIC_FORCE_DEFINITION",
        "forged_force_definition",
    )
    monkeypatch.setattr(
        diagnostic_module,
        "MIN_DIAGNOSTIC_BOND_LENGTH_ANGSTROM",
        100.0,
    )
    monkeypatch.setattr(
        diagnostic_module,
        "MIN_DIAGNOSTIC_ANGLE_SINE",
        1.0,
    )

    report = _report(_system(), _form_bound_parameter_set())
    payload = report.to_dict()
    assert payload == baseline
    assert payload["functional_form_id"] == (
        "harmonic_half_k_delta_squared_bond_angle/1.0.0"
    )
    assert payload["parameter_functional_form_id"] == (
        "harmonic_half_k_delta_squared_bond_angle/1.0.0"
    )
    assert payload["functional_form_binding_status"] == (
        "parameter_payload_bound_match"
    )
    assert "parameter_functional_form_not_embedded_in_parameter_set_v1" not in (
        report.blockers
    )


def test_diagnostic_result_never_promotes_runtime_science_or_claim_authority() -> None:
    report = _report()
    payload = report.to_dict()

    assert report.diagnostic_evaluation_performed is True
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
    assert report.minimization_authorized is False
    assert report.simulation_ready is False
    assert report.claim_safe is False
    assert payload["scientific_validation_status"] == "missing"
    assert payload["virial_status"] == "not_assessed"
    assert "nonbonded_terms_not_evaluated" in report.blockers
    assert "parameter_functional_form_not_embedded_in_parameter_set_v1" in (
        report.blockers
    )

    fit_candidate = replace(
        _parameter_set(),
        derivation_status="declared_fit_candidate_unverified",
        dataset_manifest_sha256="1" * 64,
        split_manifest_sha256="2" * 64,
        fit_protocol_id="unverified_diagnostic_fit_protocol_v1",
        fit_receipt_sha256="3" * 64,
    )
    fit_report = _report(parameter_set=fit_candidate)
    fit_payload = fit_report.to_dict()
    assert fit_payload["parameter_derivation_status"] == (
        "declared_fit_candidate_unverified"
    )
    assert fit_report.diagnostic_evaluation_performed is True
    assert fit_report.runtime_eligible is False
    assert fit_report.energy_evaluation_authorized is False
    assert fit_report.force_evaluation_authorized is False
    assert fit_report.claim_safe is False


def test_diagnostic_module_has_no_engine_or_orchestrator_integration() -> None:
    module_path = Path(diagnostic_module.__file__).resolve()
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
    assert "harmonic_diagnostics" not in engine_source
