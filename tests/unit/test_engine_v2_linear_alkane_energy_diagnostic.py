from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys

import pytest

from betelgeuze_engine_v2 import forcefield
from betelgeuze_engine_v2.forcefield import linear_alkane_energy_diagnostic as module
from betelgeuze_engine_v2.forcefield.linear_alkane_assignment import (
    analyze_linear_alkane_c1_c4_parameter_assignment,
)
from betelgeuze_engine_v2.forcefield.linear_alkane_energy_diagnostic import (
    LINEAR_ALKANE_SCALAR_ENERGY_ALGORITHM_ID,
    LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_CLAIM_SCOPE,
    LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_POLICY_ID,
    LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_PROTOCOL_SCHEMA_ID,
    LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_PROTOCOL_SHA256,
    LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_SCHEMA_ID,
    LinearAlkaneC1C4ScalarEnergyDiagnosticReport,
    LinearAlkaneScalarEnergyDiagnosticError,
    analyze_linear_alkane_c1_c4_scalar_energy_diagnostic,
    linear_alkane_scalar_energy_diagnostic_protocol_bytes,
    linear_alkane_scalar_energy_diagnostic_protocol_document,
    serialize_linear_alkane_c1_c4_scalar_energy_diagnostic_report,
)
from betelgeuze_engine_v2.forcefield.linear_alkane_method_binding import (
    LinearAlkaneC1C4EvaluationMethodBindingReport,
    analyze_linear_alkane_c1_c4_evaluation_method_binding,
)
from betelgeuze_engine_v2.forcefield.linear_alkane_parameters import (
    LinearAlkaneLennardJonesPairOverride,
    LinearAlkaneProperTorsionComponent,
)
from betelgeuze_engine_v2.molecular import parse_sdf_v2000
from betelgeuze_engine_v2.molecular.observation import (
    attach_parser_observation_digest,
)
from tests.unit.test_engine_v2_linear_alkane_evaluation_method import _method
from tests.unit.test_engine_v2_linear_alkane_parameters import _parameter_set


REPO_ROOT = Path(__file__).resolve().parents[2]
METHANE = REPO_ROOT / "tests/fixtures/v2_1_ingest_corpus/methane_explicit_h.sdf"
ALKANES = REPO_ROOT / "tests/fixtures/v2_2_linear_alkane"

GLOBAL_FALSE_GATES = (
    "method_owned_energy_kernel_available",
    "production_runtime_energy_kernel_available",
    "evaluation_executed",
    "energy_evaluated",
    "forces_evaluated",
    "virial_evaluated",
    "gradient_evaluated",
    "production_evaluation_method_defined",
    "production_parameter_assignment_complete",
    "parameterability_assessed",
    "parameterizable",
    "global_parameter_coverage_complete",
    "physics_supported",
    "scientifically_validated",
    "runtime_eligible",
    "execution_authorized",
    "energy_evaluation_authorized",
    "force_evaluation_authorized",
    "virial_evaluation_authorized",
    "gradient_evaluation_authorized",
    "minimization_authorized",
    "simulation_ready",
    "claim_safe",
    "runtime_dispatch_registered",
)


def _system(path: Path):
    return parse_sdf_v2000(path.read_bytes(), source_id=path.stem).system


def _compatible_butane():
    system = _system(ALKANES / "n_butane_explicit_h.sdf")
    coordinates = system.coordinates.clone()
    coordinates[0, 10, 0] += 0.125
    return attach_parser_observation_digest(replace(system, coordinates=coordinates))


def _binding(system, *, parameter_set=None, method=None):
    return analyze_linear_alkane_c1_c4_evaluation_method_binding(
        system,
        _parameter_set() if parameter_set is None else parameter_set,
        _method() if method is None else method,
    )


def _binary64_hex(value: float) -> str:
    return struct.pack(">d", 0.0 if value == 0.0 else value).hex()


def _decode(value: str) -> float:
    return struct.unpack(">d", bytes.fromhex(value))[0]


def _subtract(left: tuple[float, float, float], right: tuple[float, float, float]):
    return tuple(right[index] - left[index] for index in range(3))


def _cross(left: tuple[float, float, float], right: tuple[float, float, float]):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _dot(left: tuple[float, float, float], right: tuple[float, float, float]):
    return math.fsum(left[index] * right[index] for index in range(3))


def _unit(vector: tuple[float, float, float], length: float):
    return tuple(value / length for value in vector)


def _independent_oracle(system, parameter_set, method):
    """Literal stdlib oracle; it does not import diagnostic implementation helpers."""

    assignment = analyze_linear_alkane_c1_c4_parameter_assignment(
        system,
        parameter_set,
    ).to_dict()
    assert assignment["assignment_status"] == "contract_fixture_mapped"
    coordinates = tuple(
        tuple(float(system.coordinates[0, atom_index, axis].item()) for axis in range(3))
        for atom_index in range(len(system.atoms))
    )
    bond_rows = []
    for row in assignment["bond_assignments"]:
        identity = row["identity"]
        vector = _subtract(
            coordinates[identity["atom_i"]],
            coordinates[identity["atom_j"]],
        )
        distance = math.hypot(*vector)
        displacement = distance - _decode(
            row["equilibrium_length_angstrom_binary64"]
        )
        half_k = 0.5 * _decode(
            row["force_constant_kilojoule_per_mole_per_angstrom2_binary64"]
        )
        energy = (half_k * displacement) * displacement
        bond_rows.append((identity, distance, displacement, energy))

    angle_rows = []
    for row in assignment["angle_assignments"]:
        identity = row["identity"]
        center = coordinates[identity["center_atom"]]
        vector_u = _subtract(center, coordinates[identity["outer_atom_i"]])
        vector_v = _subtract(center, coordinates[identity["outer_atom_k"]])
        angle = math.atan2(math.hypot(*_cross(vector_u, vector_v)), _dot(vector_u, vector_v))
        displacement = angle - _decode(row["equilibrium_angle_radian_binary64"])
        half_k = 0.5 * _decode(
            row["force_constant_kilojoule_per_mole_per_radian2_binary64"]
        )
        energy = (half_k * displacement) * displacement
        angle_rows.append((identity, angle, displacement, energy))

    proper_rows = []
    for row in assignment["proper_assignments"]:
        identity = row["identity"]
        bond_1 = _subtract(
            coordinates[identity["atom_i"]],
            coordinates[identity["atom_j"]],
        )
        bond_2 = _subtract(
            coordinates[identity["atom_j"]],
            coordinates[identity["atom_k"]],
        )
        bond_3 = _subtract(
            coordinates[identity["atom_k"]],
            coordinates[identity["atom_l"]],
        )
        normal_1 = _cross(bond_1, bond_2)
        normal_2 = _cross(bond_2, bond_3)
        middle_hat = _unit(bond_2, math.hypot(*bond_2))
        dihedral = math.atan2(
            _dot(_cross(normal_1, normal_2), middle_hat),
            _dot(normal_1, normal_2),
        )
        component_energies = []
        for component in row["components"]:
            n_phi = float(component["periodicity"]) * dihedral
            argument = n_phi - _decode(component["phase_radian_binary64"])
            one_plus = 1.0 + math.cos(argument)
            component_energies.append(
                _decode(component["amplitude_kilojoule_per_mole_binary64"])
                * one_plus
            )
        proper_rows.append(
            (identity, dihedral, tuple(component_energies), math.fsum(component_energies))
        )

    effective_coulomb = (
        method.coulomb_coefficient_kilojoule_angstrom_per_mole_e2
        / method.relative_dielectric
    )
    pair_rows = []
    for row in assignment["pair_assignments"]:
        if row["interaction_class"] not in {
            "one_four_separate",
            "full_nonbonded",
        }:
            continue
        identity = row["identity"]
        vector = _subtract(
            coordinates[identity["atom_i"]],
            coordinates[identity["atom_j"]],
        )
        distance = math.hypot(*vector)
        ratio = _decode(row["lj_sigma_angstrom_binary64"]) / distance
        ratio_2 = ratio * ratio
        ratio_4 = ratio_2 * ratio_2
        ratio_6 = ratio_4 * ratio_2
        ratio_12 = ratio_6 * ratio_6
        shape = ratio_12 - ratio_6
        lj_base = (
            4.0 * _decode(row["lj_epsilon_kilojoule_per_mole_binary64"])
        ) * shape
        coulomb_temporary_1 = effective_coulomb * _decode(
            row["atom_i_partial_charge_e_binary64"]
        )
        coulomb_temporary_2 = coulomb_temporary_1 * _decode(
            row["atom_j_partial_charge_e_binary64"]
        )
        coulomb_base = coulomb_temporary_2 / distance
        if row["interaction_class"] == "one_four_separate":
            lj_energy = _decode(row["lj_energy_scale_binary64"]) * lj_base
            coulomb_energy = (
                _decode(row["coulomb_energy_scale_binary64"]) * coulomb_base
            )
        else:
            lj_energy = lj_base
            coulomb_energy = coulomb_base
        pair_rows.append(
            (
                identity,
                distance,
                lj_base,
                coulomb_base,
                lj_energy,
                coulomb_energy,
                math.fsum((lj_energy, coulomb_energy)),
            )
        )

    bond_energy = math.fsum(row[3] for row in bond_rows)
    angle_energy = math.fsum(row[3] for row in angle_rows)
    proper_energy = math.fsum(row[3] for row in proper_rows)
    pair_energy = math.fsum(row[6] for row in pair_rows)
    lj_energy = math.fsum(row[4] for row in pair_rows)
    coulomb_energy = math.fsum(row[5] for row in pair_rows)
    total_energy = math.fsum(
        (
            *(row[3] for row in bond_rows),
            *(row[3] for row in angle_rows),
            *(row[3] for row in proper_rows),
            *(row[6] for row in pair_rows),
        )
    )
    return {
        "assignment": assignment,
        "bond_rows": tuple(bond_rows),
        "angle_rows": tuple(angle_rows),
        "proper_rows": tuple(proper_rows),
        "pair_rows": tuple(pair_rows),
        "totals": (
            bond_energy,
            angle_energy,
            proper_energy,
            pair_energy,
            lj_energy,
            coulomb_energy,
            total_energy,
        ),
    }


def _all_keys(value: object) -> set[str]:
    if type(value) is dict:
        result = set(value)
        for nested in value.values():
            result.update(_all_keys(nested))
        return result
    if type(value) is list:
        result: set[str] = set()
        for nested in value:
            result.update(_all_keys(nested))
        return result
    return set()


def test_protocol_freezes_literal_scalar_algorithm_and_diagnostic_ownership() -> None:
    document = linear_alkane_scalar_energy_diagnostic_protocol_document()
    payload = linear_alkane_scalar_energy_diagnostic_protocol_bytes()

    assert document["schema_id"] == (
        LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_PROTOCOL_SCHEMA_ID
    )
    assert document["report_schema_id"] == (
        LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_SCHEMA_ID
    )
    assert document["diagnostic_policy_id"] == (
        LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_POLICY_ID
    )
    assert document["scalar_energy_algorithm_id"] == (
        LINEAR_ALKANE_SCALAR_ENERGY_ALGORITHM_ID
    )
    assert document["claim_scope"] == (
        LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_CLAIM_SCOPE
    )
    assert len(payload) == 5061
    assert LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_PROTOCOL_SHA256 == (
        "d749376664b1624ba53257378ef1e7c052e7a784a4e36393fa5874a007ad8f11"
    )
    assert hashlib.sha256(payload).hexdigest() == (
        LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_PROTOCOL_SHA256
    )
    assert json.loads(payload) == document
    assert document["evaluator_ownership"] == {
        "owner": "diagnostic_schema_owned_scalar_evaluator",
        "bound_method_artifact_energy_kernel_status": "missing",
        "bounded_diagnostic_scalar_evaluator_available": True,
        "method_owned_energy_kernel_available": False,
        "production_runtime_energy_kernel_available": False,
    }
    assert document["input_replay"]["raw_system_parameter_method_api"] == (
        "prohibited"
    )
    assert document["accumulation"]["total"] == (
        "one_math_fsum_over_flat_term_energy_sequence"
    )
    assert document["numeric_primitives"]["rounding_mode"] == (
        "round_to_nearest_ties_to_even_required"
    )
    assert document["numeric_primitives"]["rounding_mode_guard"] == (
        "binary64_tie_sensitive_preflight_and_postflight"
    )
    assert document["output"]["force"] == "not_defined"
    assert document["output"]["virial"] == "not_defined"
    assert document["output"]["gradient"] == "not_defined"


@pytest.mark.parametrize(
    ("case", "expected_counts", "expected_totals"),
    (
        (
            "c1",
            (4, 6, 0, 0),
            (
                "3ff9b589b5b18f2f",
                "3fe80c7fa29664b5",
                "0000000000000000",
                "0000000000000000",
                "0000000000000000",
                "0000000000000000",
                "4002dde4c37e60c5",
            ),
        ),
        (
            "c2",
            (7, 12, 9, 9),
            (
                "402c83072057e042",
                "401138567aa253d8",
                "402b00000f407602",
                "3ff1db3b331b547c",
                "3ff1b25deaa00700",
                "3f846ea43da6be1e",
                "404096a674d33ab0",
            ),
        ),
        (
            "c3",
            (10, 18, 18, 27),
            (
                "4038debb80e2523f",
                "40417da3afe515f8",
                "403f11f3df977c69",
                "bfcddd79234d656d",
                "bfcead966d48c5dd",
                "3f7a03a93f6c0e02",
                "4056ac0ef37f57f3",
            ),
        ),
        (
            "c4",
            (13, 24, 27, 54),
            (
                "404208fc6f52f5ff",
                "405a8bb2829a5632",
                "40490af7220cdfe4",
                "40a5e286778d609b",
                "40a5e2818bd1267f",
                "3f83aef0e8705d5a",
                "40a76333d9e7b2a4",
            ),
        ),
    ),
)
def test_c1_c4_scalar_diagnostic_matches_independent_literal_oracle(
    case: str,
    expected_counts: tuple[int, int, int, int],
    expected_totals: tuple[str, ...],
) -> None:
    paths = {
        "c1": METHANE,
        "c2": ALKANES / "ethane_explicit_h.sdf",
        "c3": ALKANES / "propane_explicit_h.sdf",
    }
    system = _compatible_butane() if case == "c4" else _system(paths[case])
    parameter_set = _parameter_set()
    method = _method()
    oracle = _independent_oracle(system, parameter_set, method)
    binding = _binding(system, parameter_set=parameter_set, method=method)
    report = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(binding)
    document = report.to_dict()

    assert document["diagnostic_status"] == (
        "contract_fixture_scalar_energy_evaluated"
    )
    assert oracle["assignment"]["report_sha256"] == document[
        "assignment_report_sha256"
    ]
    assert document["bound_method_artifact_energy_kernel_status"] == "missing"
    assert (
        document["evaluated_bond_count"],
        document["evaluated_angle_count"],
        document["evaluated_proper_count"],
        document["evaluated_selected_pair_count"],
    ) == expected_counts
    fields = (
        "bond_energy_kilojoule_per_mole_binary64",
        "angle_energy_kilojoule_per_mole_binary64",
        "proper_energy_kilojoule_per_mole_binary64",
        "selected_pair_energy_kilojoule_per_mole_binary64",
        "applied_lj_energy_kilojoule_per_mole_binary64",
        "applied_coulomb_energy_kilojoule_per_mole_binary64",
        "total_energy_kilojoule_per_mole_binary64",
    )
    oracle_hex = tuple(_binary64_hex(value) for value in oracle["totals"])
    assert oracle_hex == expected_totals
    assert tuple(document[name] for name in fields) == oracle_hex
    assert document["diagnostic_schema_owned_scalar_evaluator"] is True
    assert document[
        "bounded_nonphysical_diagnostic_scalar_evaluation_authorized"
    ] is True
    assert document[
        "bounded_nonphysical_diagnostic_scalar_energy_evaluated"
    ] is True
    assert document["diagnostic_evaluation_performed"] is True
    assert all(document[name] is False for name in GLOBAL_FALSE_GATES)
    assert len(document["canonical_term_energy_sequence_sha256"]) == 64
    assert len(document["scalar_energy_evaluation_sha256"]) == 64
    assert len(document["report_sha256"]) == 64
    if case == "c1":
        assert report.matches(binding) is True


def test_ethane_term_rows_lock_atan2_dihedral_lj_coulomb_and_scaling_bits() -> None:
    system = _system(ALKANES / "ethane_explicit_h.sdf")
    report = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(_binding(system))
    analysis = report._analysis()
    assert analysis.angle_terms is not None
    assert analysis.proper_terms is not None
    assert analysis.pair_terms is not None
    angles = {
        (
            value.identity.outer_atom_i,
            value.identity.center_atom,
            value.identity.outer_atom_k,
        ): value
        for value in analysis.angle_terms
    }
    propers = {
        (
            value.identity.atom_i,
            value.identity.atom_j,
            value.identity.atom_k,
            value.identity.atom_l,
        ): value
        for value in analysis.proper_terms
    }
    pairs = {
        (value.identity.atom_i, value.identity.atom_j): value
        for value in analysis.pair_terms
    }

    assert _binary64_hex(angles[(0, 1, 5)].angle_radian) == (
        "3ffe8fb96bf1d8f5"
    )
    vector_u = _subtract(
        tuple(float(value) for value in system.coordinates[0, 1]),
        tuple(float(value) for value in system.coordinates[0, 0]),
    )
    vector_v = _subtract(
        tuple(float(value) for value in system.coordinates[0, 1]),
        tuple(float(value) for value in system.coordinates[0, 5]),
    )
    acos_route = math.acos(
        _dot(vector_u, vector_v)
        / (math.hypot(*vector_u) * math.hypot(*vector_v))
    )
    assert _binary64_hex(acos_route) == "3ffe8fb96bf1d8f4"
    assert _binary64_hex(propers[(2, 0, 1, 6)].dihedral_radian) == (
        "3ff0c0a05da529c8"
    )
    assert _binary64_hex(propers[(2, 0, 1, 7)].dihedral_radian) == (
        "bff0c0a05da529c8"
    )
    pair = pairs[(2, 5)]
    assert pair.interaction_class == "one_four_separate"
    assert pair.shortest_graph_distance == 3
    assert _binary64_hex(pair.lj_base_energy_kilojoule_per_mole) == (
        "bfc92c3f07c38ce5"
    )
    assert pair.lj_energy_kilojoule_per_mole == (
        pair.lj_energy_scale * pair.lj_base_energy_kilojoule_per_mole
    )
    assert pair.coulomb_energy_kilojoule_per_mole == (
        pair.coulomb_energy_scale
        * pair.coulomb_base_energy_kilojoule_per_mole
    )
    assert pair.pair_energy_kilojoule_per_mole == math.fsum(
        (
            pair.lj_energy_kilojoule_per_mole,
            pair.coulomb_energy_kilojoule_per_mole,
        )
    )


def test_coulomb_operation_order_and_flat_total_fsum_are_bit_locked() -> None:
    ethane = _system(ALKANES / "ethane_explicit_h.sdf")
    epsilon_three = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(
        _binding(ethane, method=_method(relative_dielectric=3.0))
    )._analysis()
    assert epsilon_three.pair_terms is not None
    pair = next(
        value
        for value in epsilon_three.pair_terms
        if (value.identity.atom_i, value.identity.atom_j) == (2, 5)
    )
    assert _binary64_hex(pair.coulomb_base_energy_kilojoule_per_mole) == (
        "3f3c07422a730b27"
    )

    butane = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(
        _binding(_compatible_butane(), method=_method(relative_dielectric=7.0))
    )._analysis()
    assert butane.total_energy is not None
    assert _binary64_hex(butane.total_energy) == "40a7632fa221c9fa"
    class_subtotal_route = math.fsum(
        (
            butane.bond_energy,
            butane.angle_energy,
            butane.proper_energy,
            butane.selected_pair_energy,
        )
    )
    assert _binary64_hex(class_subtotal_route) == "40a7632fa221c9f9"


def test_one_four_scaling_and_exact_full_pair_override_are_not_reapplied() -> None:
    parameter_set = _parameter_set()
    full_override = LinearAlkaneLennardJonesPairOverride(
        "ff.h_terminal",
        "ff.h_terminal",
        3.0,
        0.25,
        "override.ht_ht",
    )
    overridden_set = replace(
        parameter_set,
        lj_pair_overrides=tuple(
            sorted((*parameter_set.lj_pair_overrides, full_override))
        ),
    )
    analysis = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(
        _binding(_compatible_butane(), parameter_set=overridden_set)
    )._analysis()
    assert analysis.pair_terms is not None

    one_four = next(
        value
        for value in analysis.pair_terms
        if value.interaction_class == "one_four_separate"
    )
    assert one_four.lj_energy_scale == parameter_set.one_four_lj_energy_scale
    assert one_four.coulomb_energy_scale == (
        parameter_set.one_four_coulomb_energy_scale
    )
    assert one_four.lj_energy_kilojoule_per_mole == (
        one_four.lj_energy_scale
        * one_four.lj_base_energy_kilojoule_per_mole
    )
    assert one_four.coulomb_energy_kilojoule_per_mole == (
        one_four.coulomb_energy_scale
        * one_four.coulomb_base_energy_kilojoule_per_mole
    )

    exact_full = tuple(
        value
        for value in analysis.pair_terms
        if value.lj_override_id == "override.ht_ht"
    )
    assert len(exact_full) == 9
    assert all(value.interaction_class == "full_nonbonded" for value in exact_full)
    assert all(value.lj_resolution_status == "exact_pair_override" for value in exact_full)
    assert all(value.lj_energy_scale is None for value in exact_full)
    assert all(value.coulomb_energy_scale is None for value in exact_full)
    assert all(
        value.lj_energy_kilojoule_per_mole
        == value.lj_base_energy_kilojoule_per_mole
        for value in exact_full
    )
    assert all(
        value.coulomb_energy_kilojoule_per_mole
        == value.coulomb_base_energy_kilojoule_per_mole
        for value in exact_full
    )
    pair_4_11 = next(
        value
        for value in exact_full
        if (value.identity.atom_i, value.identity.atom_j) == (4, 11)
    )
    ratio = 3.0 / pair_4_11.distance_angstrom
    ratio_2 = ratio * ratio
    ratio_4 = ratio_2 * ratio_2
    ratio_6 = ratio_4 * ratio_2
    expected_lj = (4.0 * 0.25) * (ratio_6 * ratio_6 - ratio_6)
    assert pair_4_11.lj_base_energy_kilojoule_per_mole == expected_lj


def test_scalar_energy_is_translation_and_proper_rotation_invariant() -> None:
    baseline = _system(ALKANES / "ethane_explicit_h.sdf")
    transformed_coordinates = baseline.coordinates[..., [1, 2, 0]].clone()
    transformed_coordinates += transformed_coordinates.new_tensor([8.0, -4.0, 2.0])
    transformed = attach_parser_observation_digest(
        replace(baseline, coordinates=transformed_coordinates)
    )
    baseline_report = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(
        _binding(baseline)
    )
    transformed_report = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(
        _binding(transformed)
    )
    baseline_analysis = baseline_report._analysis()
    transformed_analysis = transformed_report._analysis()

    for first, second in zip(
        (
            baseline_analysis.bond_energy,
            baseline_analysis.angle_energy,
            baseline_analysis.proper_energy,
            baseline_analysis.selected_pair_energy,
            baseline_analysis.total_energy,
        ),
        (
            transformed_analysis.bond_energy,
            transformed_analysis.angle_energy,
            transformed_analysis.proper_energy,
            transformed_analysis.selected_pair_energy,
            transformed_analysis.total_energy,
        ),
        strict=True,
    ):
        assert second == pytest.approx(first, rel=0.0, abs=1.0e-11)
    baseline_binding = json.loads(baseline_report._binding_report_snapshot)
    transformed_binding = json.loads(transformed_report._binding_report_snapshot)
    assert baseline_binding["canonical_system_snapshot_sha256"] != (
        transformed_binding["canonical_system_snapshot_sha256"]
    )


def test_proper_component_reduction_uses_math_fsum_not_builtin_sum() -> None:
    parameter_set = _parameter_set()
    dihedral = _decode("3ff0c0a05da529c8")
    components = (
        LinearAlkaneProperTorsionComponent(1, dihedral, 5.0e15),
        LinearAlkaneProperTorsionComponent(2, 2.0 * dihedral, 0.5),
        LinearAlkaneProperTorsionComponent(3, 3.0 * dihedral, 0.5),
    )
    changed_rules = tuple(
        replace(row, components=components)
        if row.parameter_id == "proper.contract.4"
        else row
        for row in parameter_set.proper_rules
    )
    changed_set = replace(parameter_set, proper_rules=changed_rules)
    analysis = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(
        _binding(
            _system(ALKANES / "ethane_explicit_h.sdf"),
            parameter_set=changed_set,
        )
    )._analysis()
    assert analysis.proper_terms is not None
    target = next(
        value
        for value in analysis.proper_terms
        if (
            value.identity.atom_i,
            value.identity.atom_j,
            value.identity.atom_k,
            value.identity.atom_l,
        )
        == (2, 0, 1, 6)
    )
    component_energies = tuple(
        value.energy_kilojoule_per_mole for value in target.components
    )
    assert component_energies == (1.0e16, 1.0, 1.0)
    assert _binary64_hex(sum(component_energies)) == "4341c37937e08000"
    assert _binary64_hex(math.fsum(component_energies)) == "4341c37937e08001"
    assert target.energy_kilojoule_per_mole == math.fsum(component_energies)


@pytest.mark.parametrize(
    ("kind", "expected_status"),
    (
        ("invalid", "invalid_system"),
        ("unsupported", "unsupported_system"),
        ("method_incompatible", "method_incompatible"),
    ),
)
def test_unavailable_bindings_return_no_partial_diagnostic_results(
    kind: str,
    expected_status: str,
) -> None:
    if kind == "unsupported":
        system = _system(ALKANES / "isobutane_branched_explicit_h.sdf")
    elif kind == "method_incompatible":
        system = _system(ALKANES / "n_butane_explicit_h.sdf")
    else:
        baseline = _system(ALKANES / "ethane_explicit_h.sdf")
        system = attach_parser_observation_digest(
            replace(
                baseline,
                provenance=replace(
                    baseline.provenance,
                    parser_name="unreviewed.sdf.parser",
                    parser_version="99.0.0",
                ),
            )
        )
    report = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(_binding(system))
    document = report.to_dict()

    assert document["diagnostic_status"] == expected_status
    assert document["scalar_energy_evaluation_sha256"] is None
    assert document["canonical_term_energy_sequence_sha256"] is None
    assert document["diagnostic_schema_owned_scalar_evaluator"] is False
    assert document[
        "bounded_nonphysical_diagnostic_scalar_evaluation_authorized"
    ] is False
    assert document[
        "bounded_nonphysical_diagnostic_scalar_energy_evaluated"
    ] is False
    assert document["diagnostic_evaluation_performed"] is False
    assert (
        document["evaluated_bond_count"],
        document["evaluated_angle_count"],
        document["evaluated_proper_count"],
        document["evaluated_selected_pair_count"],
    ) == (0, 0, 0, 0)
    energy_fields = tuple(
        name for name in document if name.endswith("energy_kilojoule_per_mole_binary64")
    )
    assert energy_fields
    assert all(document[name] is None for name in energy_fields)
    analysis = report._analysis()
    assert analysis.bond_terms is None
    assert analysis.angle_terms is None
    assert analysis.proper_terms is None
    assert analysis.pair_terms is None
    assert all(document[name] is False for name in GLOBAL_FALSE_GATES)


def test_c1_empty_pair_subset_is_successful_positive_zero_not_missing() -> None:
    report = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(
        _binding(_system(METHANE))
    )
    analysis = report._analysis()
    document = report.to_dict()

    assert analysis.pair_terms == ()
    assert document["pair_assignment_count"] == 10
    assert document["mapped_nonexcluded_pair_count"] == 0
    assert document["evaluated_selected_pair_count"] == 0
    for name in (
        "selected_pair_energy_kilojoule_per_mole_binary64",
        "applied_lj_energy_kilojoule_per_mole_binary64",
        "applied_coulomb_energy_kilojoule_per_mole_binary64",
    ):
        assert document[name] == "0000000000000000"


def test_report_serialization_binds_hidden_terms_but_omits_term_rows() -> None:
    binding = _binding(_system(METHANE))
    report = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(binding)
    document = report.to_dict()
    serialized = serialize_linear_alkane_c1_c4_scalar_energy_diagnostic_report(
        report
    )

    assert json.loads(serialized) == document
    assert serialized == json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    core = dict(document)
    report_sha256 = core.pop("report_sha256")
    assert hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest() == report_sha256
    assert document["method_binding_report_bytes_sha256"] == hashlib.sha256(
        report._binding_report_snapshot
    ).hexdigest()
    forbidden = {
        "bond_terms",
        "angle_terms",
        "proper_terms",
        "selected_pair_terms",
        "components",
        "distance_angstrom_binary64",
        "dihedral_radian_binary64",
    }
    assert forbidden.isdisjoint(_all_keys(document))
    analysis = report._analysis()
    evaluation_document = report._evaluation_document(analysis)
    assert evaluation_document is not None
    assert analysis.bond_terms is not None
    assert analysis.angle_terms is not None
    assert analysis.proper_terms is not None
    assert analysis.pair_terms is not None
    sequence = [
        {
            "term_class": term_class,
            "identity": value.identity.to_dict(),
            "energy_kilojoule_per_mole_binary64": _binary64_hex(energy),
        }
        for term_class, value, energy in (
            *(
                ("bond", value, value.energy_kilojoule_per_mole)
                for value in analysis.bond_terms
            ),
            *(
                ("angle", value, value.energy_kilojoule_per_mole)
                for value in analysis.angle_terms
            ),
            *(
                ("proper", value, value.energy_kilojoule_per_mole)
                for value in analysis.proper_terms
            ),
            *(
                ("selected_pair", value, value.pair_energy_kilojoule_per_mole)
                for value in analysis.pair_terms
            ),
        )
    ]
    assert document["canonical_term_energy_sequence_sha256"] == hashlib.sha256(
        json.dumps(sequence, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    assert document["scalar_energy_evaluation_sha256"] == hashlib.sha256(
        json.dumps(
            evaluation_document,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()
    assert len(serialized) == 5590
    assert hashlib.sha256(serialized).hexdigest() == (
        "3ba0b3dd03e41862512cf3843dcf023e6608aec4645d7b710cac970de88be825"
    )
    assert document["report_sha256"] == (
        "b0f49b7a4d5120b768ba66550bb4137555d802271db259b73452e268364b12fe"
    )
    assert document["scalar_energy_evaluation_sha256"] == (
        "53f516e7b93ee4a7c00a8583ef18bcdea65b533f45fc06abe11f6858bbd831bb"
    )
    assert document["canonical_term_energy_sequence_sha256"] == (
        "e603066a1039a18ede97659bf0b49101d2109fc0135e09417ad2988e80182aa8"
    )


def test_binding_snapshot_isolated_from_live_tensor_and_tamper_fails_closed() -> None:
    system = _system(METHANE)
    binding = _binding(system)
    report = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(binding)
    baseline = serialize_linear_alkane_c1_c4_scalar_energy_diagnostic_report(report)

    system.coordinates.add_(1024.0)
    assert serialize_linear_alkane_c1_c4_scalar_energy_diagnostic_report(report) == (
        baseline
    )

    snapshot = report._binding_report_snapshot
    digest = report._binding_report_snapshot_sha256
    object.__setattr__(report, "_binding_report_snapshot", snapshot + b" ")
    with pytest.raises(LinearAlkaneScalarEnergyDiagnosticError) as caught:
        report.to_dict()
    assert caught.value.code == "binding_snapshot_tampered"
    object.__setattr__(
        report,
        "_binding_report_snapshot_sha256",
        hashlib.sha256(snapshot + b" ").hexdigest(),
    )
    with pytest.raises(LinearAlkaneScalarEnergyDiagnosticError) as caught:
        report.to_dict()
    assert caught.value.code == "binding_snapshot_changed"
    object.__setattr__(report, "_binding_report_snapshot", snapshot)
    object.__setattr__(report, "_binding_report_snapshot_sha256", digest)
    assert serialize_linear_alkane_c1_c4_scalar_energy_diagnostic_report(report) == (
        baseline
    )


@pytest.mark.parametrize(
    ("field_name", "forged_value"),
    (
        ("method_binding_sha256", None),
        ("assignment_schema_id", "forged.assignment/9.9.9"),
    ),
)
def test_private_replay_rejects_self_rehashed_binding_root_forgery(
    field_name: str,
    forged_value: object,
) -> None:
    replay = _binding(
        _system(METHANE)
    )._replay_for_bounded_scalar_energy_diagnostic()
    document = json.loads(replay.binding_report_bytes)
    document[field_name] = forged_value
    document.pop("report_sha256")
    core_bytes = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    document["report_sha256"] = hashlib.sha256(core_bytes).hexdigest()
    forged_bytes = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    forged_replay = replace(replay, binding_report_bytes=forged_bytes)

    with pytest.raises(LinearAlkaneScalarEnergyDiagnosticError) as caught:
        module._compute_scalar_energy(forged_replay)
    assert caught.value.code == "dependency_inconsistent"


def test_each_public_analysis_uses_exactly_one_same_binding_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _binding(_system(METHANE))
    replay_name = "_replay_for_bounded_scalar_energy_diagnostic"
    original = getattr(LinearAlkaneC1C4EvaluationMethodBindingReport, replay_name)
    calls = 0

    def counted_replay(self):
        nonlocal calls
        calls += 1
        return original(self)

    monkeypatch.setattr(
        LinearAlkaneC1C4EvaluationMethodBindingReport,
        replay_name,
        counted_replay,
    )
    report = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(binding)
    assert calls == 1
    calls = 0
    report.to_dict()
    assert calls == 1
    calls = 0
    serialize_linear_alkane_c1_c4_scalar_energy_diagnostic_report(report)
    assert calls == 1


def test_nonfinite_energy_arithmetic_raises_typed_error_without_report() -> None:
    parameter_set = _parameter_set()
    lj_rows = tuple(
        replace(
            row,
            epsilon_kilojoule_per_mole=sys.float_info.max,
        )
        for row in parameter_set.lj_type_parameters
    )
    extreme = replace(parameter_set, lj_type_parameters=lj_rows)
    binding = _binding(
        _system(ALKANES / "ethane_explicit_h.sdf"),
        parameter_set=extreme,
    )
    assert binding.method_binding_status == "contract_fixture_method_bound"
    with pytest.raises(LinearAlkaneScalarEnergyDiagnosticError) as caught:
        analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(binding)
    assert caught.value.code == "nonfinite_result"


def test_nonrepresentable_raw_angle_cross_raises_typed_error_without_report() -> None:
    baseline = _system(ALKANES / "ethane_explicit_h.sdf")
    coordinates = baseline.coordinates.clone() * 1.0e-200
    tiny_system = attach_parser_observation_digest(
        replace(baseline, coordinates=coordinates)
    )
    smallest_positive = math.nextafter(0.0, 1.0)
    binding = _binding(
        tiny_system,
        method=_method(minimum_distance=smallest_positive),
    )
    assert binding.method_binding_status == "contract_fixture_method_bound"
    with pytest.raises(LinearAlkaneScalarEnergyDiagnosticError) as caught:
        analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(binding)
    assert caught.value.code == "nonrepresentable_coordinate_intermediate"


def test_non_nearest_binary64_rounding_modes_fail_closed_without_report() -> None:
    libc = ctypes.CDLL(None)
    if not hasattr(libc, "fegetround") or not hasattr(libc, "fesetround"):
        pytest.skip("platform C runtime does not expose floating-point rounding mode")
    libc.fegetround.argtypes = []
    libc.fegetround.restype = ctypes.c_int
    libc.fesetround.argtypes = [ctypes.c_int]
    libc.fesetround.restype = ctypes.c_int
    original_mode = libc.fegetround()
    binding = _binding(_system(METHANE))
    non_nearest_modes = (0x400, 0x800, 0xC00)
    try:
        for mode in non_nearest_modes:
            if libc.fesetround(mode) != 0:
                pytest.skip(f"platform rejected floating-point mode {mode:#x}")
            with pytest.raises(LinearAlkaneScalarEnergyDiagnosticError) as caught:
                analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(binding)
            assert caught.value.code == "rounding_mode_incompatible"
            assert libc.fesetround(original_mode) == 0
    finally:
        assert libc.fesetround(original_mode) == 0


def test_exact_input_types_private_replay_and_public_exports() -> None:
    binding = _binding(_system(METHANE))
    report = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(binding)
    assert type(report) is LinearAlkaneC1C4ScalarEnergyDiagnosticReport
    with pytest.raises(TypeError, match="exact C1-C4 method-binding report"):
        analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(  # type: ignore[arg-type]
            _system(METHANE)
        )
    with pytest.raises(TypeError, match="exact C1-C4 scalar diagnostic report"):
        serialize_linear_alkane_c1_c4_scalar_energy_diagnostic_report(  # type: ignore[arg-type]
            binding
        )

    class BindingSubclass(LinearAlkaneC1C4EvaluationMethodBindingReport):
        pass

    forged = object.__new__(BindingSubclass)
    with pytest.raises(TypeError, match="exact C1-C4 method-binding report"):
        analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(forged)
    assert "LinearAlkaneC1C4ScalarEnergyDiagnosticReplay" not in forcefield.__all__
    assert not hasattr(forcefield, "LinearAlkaneC1C4ScalarEnergyDiagnosticReplay")
    assert "LinearAlkaneC1C4ScalarEnergyDiagnosticReport" in forcefield.__all__


def test_frozen_slotted_report_and_public_label_mutation_are_nonsemantic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(
        _binding(_system(METHANE))
    )
    protocol = linear_alkane_scalar_energy_diagnostic_protocol_bytes()
    baseline = serialize_linear_alkane_c1_c4_scalar_energy_diagnostic_report(report)
    assert not hasattr(report, "__dict__")
    with pytest.raises(FrozenInstanceError):
        report._binding_report_snapshot = b"forged"  # type: ignore[misc]

    for name in (
        "LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_PROTOCOL_SCHEMA_ID",
        "LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_PROTOCOL_SHA256",
        "LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_SCHEMA_ID",
        "LINEAR_ALKANE_SCALAR_ENERGY_DIAGNOSTIC_POLICY_ID",
        "LINEAR_ALKANE_SCALAR_ENERGY_ALGORITHM_ID",
    ):
        monkeypatch.setattr(module, name, "forged")
    assert linear_alkane_scalar_energy_diagnostic_protocol_bytes() == protocol
    assert serialize_linear_alkane_c1_c4_scalar_energy_diagnostic_report(report) == (
        baseline
    )


def test_scalar_diagnostic_report_is_hashseed_stable() -> None:
    script = """
import hashlib
from tests.unit.test_engine_v2_linear_alkane_energy_diagnostic import METHANE, _binding, _system
from betelgeuze_engine_v2.forcefield.linear_alkane_energy_diagnostic import analyze_linear_alkane_c1_c4_scalar_energy_diagnostic, serialize_linear_alkane_c1_c4_scalar_energy_diagnostic_report
report = analyze_linear_alkane_c1_c4_scalar_energy_diagnostic(_binding(_system(METHANE)))
print(hashlib.sha256(serialize_linear_alkane_c1_c4_scalar_energy_diagnostic_report(report)).hexdigest())
"""
    results = []
    for seed in ("0", "42"):
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONHASHSEED": seed},
            check=True,
            capture_output=True,
            text=True,
        )
        results.append(completed.stdout.strip())
    assert results == [
        "3ba0b3dd03e41862512cf3843dcf023e6608aec4645d7b710cac970de88be825",
        "3ba0b3dd03e41862512cf3843dcf023e6608aec4645d7b710cac970de88be825",
    ]
