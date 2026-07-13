from __future__ import annotations

from dataclasses import replace
import ctypes
import hashlib
import inspect
import json
import math
from pathlib import Path
import struct
import sys

import pytest
import torch

from betelgeuze_engine_v2.forcefield.linear_alkane_energy_diagnostic import (
    LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_PROTOCOL_SHA256,
    analyze_linear_alkane_c1_c4_scalar_energy_diagnostic,
)
from betelgeuze_engine_v2.forcefield.linear_alkane_evaluation_method import (
    LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SHA256,
)
from betelgeuze_engine_v2.forcefield.linear_alkane_method_binding import (
    LinearAlkaneC1C4EvaluationMethodBindingReport,
    analyze_linear_alkane_c1_c4_evaluation_method_binding,
)
from betelgeuze_engine_v2.molecular import parse_sdf_v2000
from betelgeuze_engine_v2.molecular.observation import (
    attach_parser_observation_digest,
)
from betelgeuze_engine_v2.physics import (
    LINEAR_ALKANE_METHOD_KERNEL_PROTOCOL_SCHEMA_ID,
    LINEAR_ALKANE_METHOD_KERNEL_PROTOCOL_SHA256,
    LINEAR_ALKANE_REFERENCE_KERNEL_RESULT_SCHEMA_ID,
    LinearAlkaneC1C4ReferenceKernelResult,
    LinearAlkaneC1C4ReferencePotential,
    LinearAlkaneReferenceKernelError,
    compile_linear_alkane_c1_c4_reference_potential,
    evaluate_linear_alkane_c1_c4_reference_kernel,
    linear_alkane_method_kernel_protocol_bytes,
    linear_alkane_method_kernel_protocol_document,
    serialize_linear_alkane_c1_c4_reference_kernel_result,
)
from betelgeuze_engine_v2.physics import linear_alkane_reference_kernel as module
from tests.unit.test_engine_v2_linear_alkane_applicability import (
    _permuted_sdf_source,
)
from tests.unit.test_engine_v2_linear_alkane_evaluation_method import _method
from tests.unit.test_engine_v2_linear_alkane_parameters import _parameter_set


REPO_ROOT = Path(__file__).resolve().parents[2]
METHANE = REPO_ROOT / "tests/fixtures/v2_1_ingest_corpus/methane_explicit_h.sdf"
ALKANES = REPO_ROOT / "tests/fixtures/v2_2_linear_alkane"
EXPECTED_COUNTS = {
    "c1": (4, 6, 0, 0),
    "c2": (7, 12, 9, 9),
    "c3": (10, 18, 18, 27),
    "c4": (13, 24, 27, 54),
}
EXPECTED_TOTAL_HEX = {
    "c1": "4002dde4c37e60c5",
    "c2": "404096a674d33ab0",
    "c3": "4056ac0ef37f57f3",
    "c4": "40a76333d9e7b2a4",
}


def _hex(value: float) -> str:
    return struct.pack(">d", value).hex()


def _system(case: str):
    path = {
        "c1": METHANE,
        "c2": ALKANES / "ethane_explicit_h.sdf",
        "c3": ALKANES / "propane_explicit_h.sdf",
        "c4": ALKANES / "n_butane_explicit_h.sdf",
    }[case]
    system = parse_sdf_v2000(path.read_bytes(), source_id=path.stem).system
    if case == "c4":
        coordinates = system.coordinates.clone()
        coordinates[0, 10, 0] += 0.125
        system = attach_parser_observation_digest(
            replace(system, coordinates=coordinates)
        )
    return system


@pytest.fixture(scope="module")
def compiled_cases():
    rows = {}
    for case in ("c1", "c2", "c3", "c4"):
        system = _system(case)
        binding = analyze_linear_alkane_c1_c4_evaluation_method_binding(
            system,
            _parameter_set(),
            _method(),
        )
        assert binding.method_binding_status == "contract_fixture_method_bound"
        rows[case] = (
            system,
            binding,
            compile_linear_alkane_c1_c4_reference_potential(binding),
        )
    return rows


def _torch_energy(potential: LinearAlkaneC1C4ReferencePotential, x: torch.Tensor):
    """Independent torch graph using only the immutable compiled numeric plan."""

    spec = potential._spec
    terms = []
    for row in spec.bonds:
        distance = torch.linalg.vector_norm(x[row.atom_j] - x[row.atom_i])
        terms.append(0.5 * row.force_constant * (distance - row.equilibrium) ** 2)
    for row in spec.angles:
        u = x[row.atom_i] - x[row.center]
        v = x[row.atom_k] - x[row.center]
        theta = torch.atan2(
            torch.linalg.vector_norm(torch.cross(u, v, dim=0)),
            torch.dot(u, v),
        )
        terms.append(0.5 * row.force_constant * (theta - row.equilibrium) ** 2)
    for row in spec.propers:
        b1 = x[row.atom_j] - x[row.atom_i]
        b2 = x[row.atom_k] - x[row.atom_j]
        b3 = x[row.atom_l] - x[row.atom_k]
        n1 = torch.cross(b1, b2, dim=0)
        n2 = torch.cross(b2, b3, dim=0)
        phi = torch.atan2(
            torch.dot(
                torch.cross(n1, n2, dim=0),
                b2 / torch.linalg.vector_norm(b2),
            ),
            torch.dot(n1, n2),
        )
        component_terms = [
            amplitude * (1.0 + torch.cos(float(periodicity) * phi - phase))
            for periodicity, phase, amplitude in row.components
        ]
        terms.append(torch.stack(component_terms).sum())
    for row in spec.pairs:
        distance = torch.linalg.vector_norm(x[row.atom_j] - x[row.atom_i])
        ratio_6 = (row.sigma / distance) ** 6
        lj = 4.0 * row.epsilon * (ratio_6 * ratio_6 - ratio_6)
        coulomb = (
            spec.effective_coulomb_coefficient * row.charge_i * row.charge_j
        ) / distance
        if row.interaction_class == "one_four_separate":
            lj = row.lj_scale * lj
            coulomb = row.coulomb_scale * coulomb
        terms.extend((lj, coulomb))
    return torch.stack(terms).sum()


def test_protocol_is_frozen_separate_overlay_and_v1_stays_frozen() -> None:
    payload = linear_alkane_method_kernel_protocol_bytes()
    document = linear_alkane_method_kernel_protocol_document()
    assert LINEAR_ALKANE_METHOD_KERNEL_PROTOCOL_SCHEMA_ID == (
        "betelgeuze.linear_alkane_c1_c4_method_kernel_protocol/1.0.0"
    )
    assert LINEAR_ALKANE_REFERENCE_KERNEL_RESULT_SCHEMA_ID == (
        "betelgeuze.linear_alkane_c1_c4_reference_kernel_result/1.0.0"
    )
    assert hashlib.sha256(payload).hexdigest() == (
        LINEAR_ALKANE_METHOD_KERNEL_PROTOCOL_SHA256
    )
    assert len(payload) == 5519
    assert LINEAR_ALKANE_METHOD_KERNEL_PROTOCOL_SHA256 == (
        "c402308fbec145137a69917102c8539c224e6393567dc30fcc64496724359cad"
    )
    assert json.loads(payload.decode("ascii")) == document
    assert document["ownership"] == {
        "base_v1_method_energy_kernel_status": "missing_unchanged",
        "overlay_method_kernel_status": "available_bounded_nonphysical",
        "production_runtime_kernel_status": "unavailable",
    }
    assert document["force"]["definition"].startswith("force_i_axis=-d_total")
    assert document["virial"]["pressure_stress_volume_pbc_semantics"] == (
        "not_defined"
    )
    assert document["promotion"] == {
        "scientific_parameters": False,
        "scientifically_validated": False,
        "physics_supported": False,
        "runtime_eligible": False,
        "engine_dispatch_registered": False,
        "minimization_authorized": False,
        "simulation_ready": False,
        "claim_safe": False,
    }
    assert LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SHA256 == (
        "7a8416632d83cab3e32ebbbdc43549d59b5a4efb472283d07f773ad66de461da"
    )
    assert LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_PROTOCOL_SHA256 == (
        "d749376664b1624ba53257378ef1e7c052e7a784a4e36393fa5874a007ad8f11"
    )
    source = inspect.getsource(module)
    assert "linear_alkane_energy_diagnostic" not in source


def test_c1_c4_energy_is_bit_exact_with_independent_scalar_diagnostic(
    compiled_cases,
) -> None:
    for case, (system, binding, potential) in compiled_cases.items():
        result = potential.evaluate(system.coordinates[0])
        diagnostic = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(binding)
        assert _hex(result.total_energy_kilojoule_per_mole) == EXPECTED_TOTAL_HEX[case]
        assert _hex(result.total_energy_kilojoule_per_mole) == _hex(
            diagnostic.total_energy_kilojoule_per_mole
        )
        bond_count, angle_count, proper_count, pair_count = EXPECTED_COUNTS[case]
        counts = {row.term_class: row.term_count for row in result.class_results}
        assert counts == {
            "bond": bond_count,
            "angle": angle_count,
            "proper": proper_count,
            "lennard_jones": pair_count,
            "coulomb": pair_count,
        }
        assert potential.atom_count == len(system.atoms)
        assert potential.to_dict()["base_v1_method_energy_kernel_status"] == (
            "missing_unchanged"
        )
        report = result.to_dict()
        assert report["status"] == (
            "bounded_nonphysical_energy_force_virial_evaluated"
        )
        assert report["bounded_nonphysical_method_owned_reference_kernel_complete"]
        assert report["method_owned_energy_kernel_available"] is True
        assert report["method_owned_force_kernel_available"] is True
        assert report["method_owned_virial_kernel_available"] is True
        for gate in (
            "production_runtime_energy_kernel_available",
            "production_runtime_force_kernel_available",
            "production_runtime_virial_kernel_available",
            "production_evaluation_method_defined",
            "production_parameter_assignment_complete",
            "parameterability_assessed",
            "parameterizable",
            "global_parameter_coverage_complete",
            "scientific_parameters",
            "scientifically_validated",
            "physics_supported",
            "runtime_eligible",
            "engine_dispatch_registered",
            "execution_authorized",
            "energy_evaluation_authorized",
            "force_evaluation_authorized",
            "virial_evaluation_authorized",
            "minimization_authorized",
            "simulation_ready",
            "claim_safe",
        ):
            assert report[gate] is False
        if case == "c1":
            payload = serialize_linear_alkane_c1_c4_reference_kernel_result(
                result
            )
            assert potential.compiled_plan_sha256 == (
                "e1107d0182ccc50e0bcc301d72d3f73cd143b06bc06fd7a47568ff26f7c55f62"
            )
            assert len(payload) == 14655
            assert hashlib.sha256(payload).hexdigest() == (
                "9d72ddf1b55b7f029a6cac5349576373e6f71621a201460d8fa80bfd80799d50"
            )
            assert result.evaluation_sha256 == (
                "70e0af0e6b12fe8b1fb70bf72c7b29561a2a9723c728bf73bef89a5228eaaa1d"
            )
            assert result.report_sha256 == (
                "0879f6ce803ec6a0a3271c5dd56bdd85fceedcd3c7ac353abb4700c6eb177b6e"
            )


def test_force_matches_all_coordinate_finite_differences(compiled_cases) -> None:
    step = 1.0e-6
    for case, (system, _binding, potential) in compiled_cases.items():
        coordinates = system.coordinates[0]
        force = potential.evaluate(coordinates).forces_tensor()[0]
        for atom_index in range(coordinates.shape[0]):
            for axis in range(3):
                plus = coordinates.clone()
                minus = coordinates.clone()
                plus[atom_index, axis] += step
                minus[atom_index, axis] -= step
                finite_difference = -(
                    potential.evaluate(plus).total_energy_kilojoule_per_mole
                    - potential.evaluate(minus).total_energy_kilojoule_per_mole
                ) / (2.0 * step)
                assert force[atom_index, axis].item() == pytest.approx(
                    finite_difference,
                    rel=2.0e-6,
                    abs=2.0e-4 if case == "c4" else 2.0e-7,
                )


def test_force_matches_independent_torch_autograd_for_all_terms(compiled_cases) -> None:
    for case in ("c2", "c3", "c4"):
        system, _binding, potential = compiled_cases[case]
        coordinates = system.coordinates[0].detach().clone().requires_grad_(True)
        energy = _torch_energy(potential, coordinates)
        expected = -torch.autograd.grad(energy, coordinates)[0]
        actual = potential.evaluate(coordinates.detach()).forces_tensor()[0]
        assert torch.allclose(actual, expected, rtol=2.0e-11, atol=2.0e-9)


def test_complete_nonperiodic_virial_matches_nine_affine_differences(
    compiled_cases,
) -> None:
    step = 1.0e-6
    identity = torch.eye(3, dtype=torch.float64)
    for case, (system, _binding, potential) in compiled_cases.items():
        coordinates = system.coordinates[0]
        virial = potential.evaluate(coordinates).virial_tensor()
        for force_axis in range(3):
            for coordinate_axis in range(3):
                strain = torch.zeros((3, 3), dtype=torch.float64)
                strain[force_axis, coordinate_axis] = step
                plus = coordinates @ (identity + strain).T
                minus = coordinates @ (identity - strain).T
                finite_difference = -(
                    potential.evaluate(plus).total_energy_kilojoule_per_mole
                    - potential.evaluate(minus).total_energy_kilojoule_per_mole
                ) / (2.0 * step)
                assert virial[force_axis, coordinate_axis].item() == pytest.approx(
                    finite_difference,
                    rel=2.0e-6,
                    abs=3.0e-4 if case == "c4" else 2.0e-7,
                )


def test_translation_rotation_conservation_and_class_decomposition(
    compiled_cases,
) -> None:
    rotation = torch.tensor(
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=torch.float64,
    )
    translation = torch.tensor([8.0, -4.0, 2.0], dtype=torch.float64)
    for case, (system, _binding, potential) in compiled_cases.items():
        coordinates = system.coordinates[0]
        result = potential.evaluate(coordinates)
        translated = potential.evaluate(coordinates + translation)
        rotated = potential.evaluate(coordinates @ rotation.T)
        force = result.forces_tensor()[0]
        virial = result.virial_tensor()
        assert translated.total_energy_kilojoule_per_mole == pytest.approx(
            result.total_energy_kilojoule_per_mole,
            rel=2.0e-13,
            abs=2.0e-10,
        )
        assert torch.allclose(
            translated.forces_tensor()[0], force, rtol=2.0e-13, atol=2.0e-10
        )
        assert torch.allclose(
            translated.virial_tensor(), virial, rtol=2.0e-13, atol=2.0e-9
        )
        assert rotated.total_energy_kilojoule_per_mole == pytest.approx(
            result.total_energy_kilojoule_per_mole,
            rel=2.0e-13,
            abs=2.0e-10,
        )
        assert torch.allclose(
            rotated.forces_tensor()[0],
            force @ rotation.T,
            rtol=2.0e-13,
            atol=2.0e-9,
        )
        assert torch.allclose(
            rotated.virial_tensor(),
            rotation @ virial @ rotation.T,
            rtol=2.0e-13,
            atol=2.0e-8,
        )
        assert torch.allclose(
            force.sum(dim=0), torch.zeros(3, dtype=torch.float64), atol=2.0e-9
        )
        anchor = coordinates[0]
        torque = torch.cross(coordinates - anchor, force, dim=1).sum(dim=0)
        assert torch.allclose(
            torque, torch.zeros(3, dtype=torch.float64), atol=2.0e-8
        )
        class_force_sum = torch.stack(
            [result.class_forces_tensor(row.term_class)[0] for row in result.class_results]
        ).sum(dim=0)
        class_virial_sum = torch.stack(
            [result.class_virial_tensor(row.term_class) for row in result.class_results]
        ).sum(dim=0)
        class_energy_sum = math.fsum(
            row.energy_kilojoule_per_mole for row in result.class_results
        )
        assert class_energy_sum == pytest.approx(
            result.total_energy_kilojoule_per_mole,
            rel=2.0e-15,
            abs=2.0e-12,
        )
        assert torch.allclose(class_force_sum, force, rtol=2.0e-13, atol=2.0e-9)
        assert torch.allclose(
            class_virial_sum, virial, rtol=2.0e-13, atol=2.0e-8
        )


def test_atom_reindexing_is_energy_virial_invariant_and_force_equivariant(
    compiled_cases,
) -> None:
    baseline_system, _binding, baseline_potential = compiled_cases["c2"]
    baseline = baseline_potential.evaluate(baseline_system.coordinates[0])
    atom_count = len(baseline_system.atoms)
    new_to_old = tuple(reversed(range(atom_count)))
    source = _permuted_sdf_source(
        ALKANES / "ethane_explicit_h.sdf",
        new_to_old,
    )
    permuted_system = parse_sdf_v2000(
        source,
        source_id="ethane_explicit_h_reindexed",
    ).system
    permuted_binding = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        permuted_system,
        _parameter_set(),
        _method(),
    )
    permuted_potential = compile_linear_alkane_c1_c4_reference_potential(
        permuted_binding
    )
    permuted = permuted_potential.evaluate(permuted_system.coordinates[0])
    assert permuted.total_energy_kilojoule_per_mole == pytest.approx(
        baseline.total_energy_kilojoule_per_mole,
        rel=2.0e-15,
        abs=2.0e-12,
    )
    baseline_force = baseline.forces_tensor()[0]
    permuted_force = permuted.forces_tensor()[0]
    expected_permuted_force = torch.stack(
        [baseline_force[old_index] for old_index in new_to_old]
    )
    assert torch.allclose(
        permuted_force,
        expected_permuted_force,
        rtol=2.0e-13,
        atol=2.0e-9,
    )
    assert torch.allclose(
        permuted.virial_tensor(),
        baseline.virial_tensor(),
        rtol=2.0e-13,
        atol=2.0e-9,
    )


def test_repeated_evaluation_is_snapshot_bound_and_tensor_accessors_are_copies(
    compiled_cases,
) -> None:
    system, _binding, potential = compiled_cases["c3"]
    first = potential.evaluate(system.coordinates[0])
    changed_coordinates = system.coordinates[0].clone()
    changed_coordinates[0, 0] += 0.03125
    second = evaluate_linear_alkane_c1_c4_reference_kernel(
        potential,
        changed_coordinates,
    )
    assert type(first) is LinearAlkaneC1C4ReferenceKernelResult
    assert first.coordinate_snapshot_sha256 != second.coordinate_snapshot_sha256
    assert first.evaluation_sha256 != second.evaluation_sha256
    assert first.total_energy_kilojoule_per_mole != (
        second.total_energy_kilojoule_per_mole
    )
    force_copy = first.forces_tensor()
    virial_copy = first.virial_tensor()
    force_copy.fill_(123.0)
    virial_copy.fill_(456.0)
    assert not bool(torch.all(first.forces_tensor() == 123.0).item())
    assert not bool(torch.all(first.virial_tensor() == 456.0).item())
    serialized = serialize_linear_alkane_c1_c4_reference_kernel_result(first)
    assert json.loads(serialized.decode("ascii")) == first.to_dict()
    assert hashlib.sha256(serialized).hexdigest() == hashlib.sha256(
        serialize_linear_alkane_c1_c4_reference_kernel_result(first)
    ).hexdigest()


def test_compile_and_coordinate_boundaries_fail_closed(compiled_cases) -> None:
    with pytest.raises(TypeError, match="exact C1-C4 binding report"):
        compile_linear_alkane_c1_c4_reference_potential(object())
    with pytest.raises(TypeError, match="exact C1-C4 reference potential"):
        evaluate_linear_alkane_c1_c4_reference_kernel(object(), torch.zeros(1))

    class BindingSubclass(LinearAlkaneC1C4EvaluationMethodBindingReport):
        pass

    with pytest.raises(TypeError, match="exact C1-C4 binding report"):
        compile_linear_alkane_c1_c4_reference_potential(BindingSubclass.__new__(BindingSubclass))

    raw_butane = parse_sdf_v2000(
        (ALKANES / "n_butane_explicit_h.sdf").read_bytes(),
        source_id="n_butane_explicit_h",
    ).system
    incompatible = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        raw_butane,
        _parameter_set(),
        _method(),
    )
    assert incompatible.method_binding_status == "method_incompatible"
    with pytest.raises(LinearAlkaneReferenceKernelError) as caught:
        compile_linear_alkane_c1_c4_reference_potential(incompatible)
    assert caught.value.code == "binding_not_executable"

    system, _binding, potential = compiled_cases["c1"]
    coordinates = system.coordinates[0]
    invalid_inputs = (
        coordinates.tolist(),
        coordinates.to(torch.float32),
        coordinates[:, :2],
        coordinates.unsqueeze(0),
        coordinates.detach().clone().requires_grad_(True),
    )
    for invalid in invalid_inputs:
        with pytest.raises((TypeError, LinearAlkaneReferenceKernelError)):
            potential.evaluate(invalid)
    nonfinite = coordinates.clone()
    nonfinite[0, 0] = float("nan")
    with pytest.raises(LinearAlkaneReferenceKernelError) as caught:
        potential.evaluate(nonfinite)
    assert caught.value.code == "nonfinite_coordinate"
    coincident = coordinates.clone()
    coincident[1] = coincident[0]
    with pytest.raises(LinearAlkaneReferenceKernelError) as caught:
        potential.evaluate(coincident)
    assert caught.value.code == "singular_geometry"


def test_compiled_plan_and_result_tampering_fail_closed(compiled_cases) -> None:
    system, binding, potential = compiled_cases["c1"]
    tampered_potential = compile_linear_alkane_c1_c4_reference_potential(binding)
    object.__setattr__(
        tampered_potential,
        "_binding_report_snapshot",
        tampered_potential._binding_report_snapshot + b" ",
    )
    with pytest.raises(LinearAlkaneReferenceKernelError) as caught:
        tampered_potential.evaluate(system.coordinates[0])
    assert caught.value.code == "compiled_potential_tampered"

    result = potential.evaluate(system.coordinates[0])
    object.__setattr__(result, "_total_energy", result._total_energy + 1.0)
    with pytest.raises(LinearAlkaneReferenceKernelError) as caught:
        _ = result.total_energy_kilojoule_per_mole
    assert caught.value.code == "result_tampered"


def test_non_nearest_rounding_modes_fail_closed_without_result(compiled_cases) -> None:
    libc = ctypes.CDLL(None)
    if not hasattr(libc, "fegetround") or not hasattr(libc, "fesetround"):
        pytest.skip("platform C runtime does not expose floating-point rounding mode")
    libc.fegetround.argtypes = []
    libc.fegetround.restype = ctypes.c_int
    libc.fesetround.argtypes = [ctypes.c_int]
    libc.fesetround.restype = ctypes.c_int
    original_mode = libc.fegetround()
    system, _binding, potential = compiled_cases["c1"]
    try:
        for mode in (0x400, 0x800, 0xC00):
            if libc.fesetround(mode) != 0:
                pytest.skip(f"platform rejected floating-point mode {mode:#x}")
            with pytest.raises(LinearAlkaneReferenceKernelError) as caught:
                potential.evaluate(system.coordinates[0])
            assert caught.value.code == "rounding_mode_incompatible"
            assert libc.fesetround(original_mode) == 0
    finally:
        assert libc.fesetround(original_mode) == 0


def test_nonfinite_energy_arithmetic_fails_without_partial_result() -> None:
    parameter_set = _parameter_set()
    extreme = replace(
        parameter_set,
        lj_type_parameters=tuple(
            replace(row, epsilon_kilojoule_per_mole=sys.float_info.max)
            for row in parameter_set.lj_type_parameters
        ),
    )
    system = _system("c2")
    binding = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        system,
        extreme,
        _method(),
    )
    assert binding.method_binding_status == "contract_fixture_method_bound"
    potential = compile_linear_alkane_c1_c4_reference_potential(binding)
    with pytest.raises(LinearAlkaneReferenceKernelError) as caught:
        potential.evaluate(system.coordinates[0])
    assert caught.value.code == "nonfinite_result"


def test_term_classes_cover_override_one_four_and_full_pairs(compiled_cases) -> None:
    _system_c4, _binding, potential = compiled_cases["c4"]
    spec = potential._spec
    assert any(row.interaction_class == "one_four_separate" for row in spec.pairs)
    assert any(row.interaction_class == "full_nonbonded" for row in spec.pairs)
    assert any(row.parameter_id.startswith("override.") for row in spec.pairs)
    for row in spec.pairs:
        if row.interaction_class == "one_four_separate":
            assert type(row.lj_scale) is float
            assert type(row.coulomb_scale) is float
        else:
            assert row.lj_scale is None
            assert row.coulomb_scale is None


def test_public_exports_do_not_expose_compiled_private_specs() -> None:
    assert type(LinearAlkaneC1C4ReferencePotential) is type
    assert "_CompiledSpec" not in module.__all__
    assert "_BondSpec" not in module.__all__
    with pytest.raises(TypeError):
        serialize_linear_alkane_c1_c4_reference_kernel_result(object())
    with pytest.raises(TypeError, match="exact 3x3 tuple matrix"):
        module.LinearAlkaneReferenceKernelTermResult(
            term_class="bond",
            identity=(0, 1),
            parameter_id="fixture",
            energy_kilojoule_per_mole=0.0,
            local_forces=((0, (0.0, 0.0, 0.0)), (1, (0.0, 0.0, 0.0))),
            virial_kilojoule_per_mole=((0.0, 0.0, 0.0),),
        )
