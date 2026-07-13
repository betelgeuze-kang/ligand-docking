from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import pytest
import torch

from betelgeuze_engine_v2.forcefield import linear_alkane_parameters as module
from betelgeuze_engine_v2.forcefield.linear_alkane_parameters import (
    LINEAR_ALKANE_CHARGE_BALANCE_TOLERANCE_E,
    LINEAR_ALKANE_LJ_COMBINING_RULE_ID,
    LINEAR_ALKANE_PARAMETER_ANGLE_KEYS,
    LINEAR_ALKANE_PARAMETER_BOND_KEYS,
    LINEAR_ALKANE_PARAMETER_ENVIRONMENT_IDS,
    LINEAR_ALKANE_PARAMETER_PROPER_KEYS,
    LINEAR_ALKANE_PARAMETER_PROTOCOL_SCHEMA_ID,
    LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256,
    LINEAR_ALKANE_PARAMETER_SET_SCHEMA_ID,
    LinearAlkaneAngleParameterRule,
    LinearAlkaneBondParameterRule,
    LinearAlkaneC1C4ParameterSet,
    LinearAlkaneEnvironmentParameterMapping,
    LinearAlkaneLennardJonesPairOverride,
    LinearAlkaneLennardJonesTypeParameter,
    LinearAlkaneParameterContractError,
    LinearAlkaneParameterSerializationError,
    LinearAlkanePartialChargeParameter,
    LinearAlkaneProperParameterRule,
    LinearAlkaneProperTorsionComponent,
    deserialize_linear_alkane_c1_c4_parameter_set,
    linear_alkane_parameter_protocol_bytes,
    linear_alkane_parameter_protocol_document,
    resolve_linear_alkane_lj_pair,
    serialize_linear_alkane_c1_c4_parameter_set,
)
from betelgeuze_engine_v2.forcefield.term_inventory import (
    CanonicalAngleEnvironmentMatchKey,
    CanonicalBondEnvironmentMatchKey,
    CanonicalProperEnvironmentMatchKey,
    analyze_linear_alkane_term_pair_inventory,
)
from betelgeuze_engine_v2.molecular import parse_sdf_v2000


REPO_ROOT = Path(__file__).resolve().parents[2]
METHANE = REPO_ROOT / "tests/fixtures/v2_1_ingest_corpus/methane_explicit_h.sdf"
ALKANES = REPO_ROOT / "tests/fixtures/v2_2_linear_alkane"

CM = "c_single_valence4_c0_h4"
HM = "h_attached_c_single_valence4_c0_h4"
CT = "c_single_valence4_c1_h3"
HT = "h_attached_c_single_valence4_c1_h3"
CI = "c_single_valence4_c2_h2"
HI = "h_attached_c_single_valence4_c2_h2"


def _parameter_set() -> LinearAlkaneC1C4ParameterSet:
    mapping_data = {
        CM: ("ff.c_methane", "charge.c_methane"),
        CT: ("ff.c_terminal", "charge.c_terminal"),
        CI: ("ff.c_internal", "charge.c_internal"),
        HM: ("ff.h_methane", "charge.h"),
        HT: ("ff.h_terminal", "charge.h"),
        HI: ("ff.h_internal", "charge.h"),
    }
    mappings = tuple(
        sorted(
            LinearAlkaneEnvironmentParameterMapping(
                environment_id,
                *mapping_data[environment_id],
            )
            for environment_id in LINEAR_ALKANE_PARAMETER_ENVIRONMENT_IDS
        )
    )
    type_ids = sorted(row.force_field_type_id for row in mappings)
    lj_parameters = tuple(
        sorted(
            LinearAlkaneLennardJonesTypeParameter(
                force_field_type_id,
                2.0 + 0.125 * index,
                0.125 + 0.015625 * index,
            )
            for index, force_field_type_id in enumerate(type_ids)
        )
    )
    charges = tuple(
        sorted(
            (
                LinearAlkanePartialChargeParameter(
                    "charge.c_internal",
                    -0.125,
                ),
                LinearAlkanePartialChargeParameter(
                    "charge.c_methane",
                    -0.25,
                ),
                LinearAlkanePartialChargeParameter(
                    "charge.c_terminal",
                    -0.1875,
                ),
                LinearAlkanePartialChargeParameter("charge.h", 0.0625),
            )
        )
    )
    overrides = (
        LinearAlkaneLennardJonesPairOverride(
            "ff.c_internal",
            "ff.h_terminal",
            2.75,
            0.2,
            "override.ci_ht",
        ),
    )
    bond_rules = tuple(
        sorted(
            LinearAlkaneBondParameterRule(
                CanonicalBondEnvironmentMatchKey.from_environments(*key),
                f"bond.contract.{index}",
                1.0 + 0.015625 * index,
                100.0 + float(index),
            )
            for index, key in enumerate(LINEAR_ALKANE_PARAMETER_BOND_KEYS)
        )
    )
    angle_rules = tuple(
        sorted(
            LinearAlkaneAngleParameterRule(
                CanonicalAngleEnvironmentMatchKey.from_environments(*key),
                f"angle.contract.{index}",
                1.75 + 0.015625 * index,
                50.0 + float(index),
            )
            for index, key in enumerate(LINEAR_ALKANE_PARAMETER_ANGLE_KEYS)
        )
    )
    proper_rules = tuple(
        sorted(
            LinearAlkaneProperParameterRule(
                CanonicalProperEnvironmentMatchKey.from_environments(*key),
                f"proper.contract.{index}",
                (
                    LinearAlkaneProperTorsionComponent(
                        1 + index % 3,
                        0.125 * index,
                        1.0 + 0.125 * index,
                    ),
                ),
            )
            for index, key in enumerate(LINEAR_ALKANE_PARAMETER_PROPER_KEYS)
        )
    )
    return LinearAlkaneC1C4ParameterSet(
        parameter_set_id="nonphysical.linear_alkane_c1_c4.contract",
        parameter_set_version="1.0.0",
        charge_model_id="nonphysical.dyadic_environment_lookup",
        environment_mappings=mappings,
        lj_type_parameters=lj_parameters,
        charge_parameters=charges,
        lj_pair_overrides=overrides,
        bond_rules=bond_rules,
        angle_rules=angle_rules,
        proper_rules=proper_rules,
        one_four_lj_energy_scale=0.5,
        one_four_coulomb_energy_scale=0.75,
    )


def test_protocol_is_frozen_and_covers_the_exact_full_domain() -> None:
    document = linear_alkane_parameter_protocol_document()
    payload = linear_alkane_parameter_protocol_bytes()

    assert document["schema_id"] == LINEAR_ALKANE_PARAMETER_PROTOCOL_SCHEMA_ID
    assert len(payload) == 8664
    assert LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256 == (
        "28219cd1492b31f3d151048e7ad9db297fe7a896d081b098e901f142f6d4602a"
    )
    assert hashlib.sha256(payload).hexdigest() == (
        LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256
    )
    assert json.loads(payload) == document
    assert tuple(document["environment_ids"]) == (
        LINEAR_ALKANE_PARAMETER_ENVIRONMENT_IDS
    )
    assert tuple(tuple(row) for row in document["bond_keys"]) == (
        LINEAR_ALKANE_PARAMETER_BOND_KEYS
    )
    assert tuple(tuple(row) for row in document["angle_keys"]) == (
        LINEAR_ALKANE_PARAMETER_ANGLE_KEYS
    )
    assert tuple(tuple(row) for row in document["proper_keys"]) == (
        LINEAR_ALKANE_PARAMETER_PROPER_KEYS
    )
    assert len(document["environment_ids"]) == 6
    assert len(document["bond_keys"]) == 6
    assert len(document["angle_keys"]) == 9
    assert len(document["proper_keys"]) == 7
    assert document["applicability_schema_id"] == (
        "betelgeuze.linear_alkane_c1_c4_force_field_applicability/1.0.0"
    )
    assert document["applicability_profile_id"] == (
        "source_bound_sdf_v2000_explicit_h_neutral_linear_alkane_c1_c4/"
        "1.0.0"
    )
    assert document["lj_combining_rule_id"] == LINEAR_ALKANE_LJ_COMBINING_RULE_ID
    forms = document["functional_form_definitions"]
    assert forms["bond"]["energy"] == "E_b=0.5*k_b*(r-r0)^2"
    assert forms["angle"]["coordinate"] == (
        "theta=atan2(norm(cross(u,v)),dot(u,v))"
    )
    assert forms["proper"]["energy"] == (
        "E_p(phi)=sum_m(k_m*(1+cos(n_m*phi-delta_m)))"
    )
    assert forms["lennard_jones"]["energy"] == (
        "U_lj=4*epsilon_ij*((sigma_ij/r)^12-(sigma_ij/r)^6)"
    )
    assert forms["coulomb_base"]["energy"] == "U_q=k_e*q_i*q_j/r"
    convention = document["proper_coordinate_convention"]
    assert convention["coordinate"] == "phi=atan2(y,x)"
    assert convention["range"] == "-pi<=phi<=pi"
    assert convention["full_path_reversal"] == (
        "phi(r_i,r_j,r_k,r_l)=phi(r_l,r_k,r_j,r_i)"
    )
    assert document["lj_resolution_semantics"] == {
        "sigma_combining": "sigma_ij=(sigma_i+sigma_j)/2",
        "epsilon_combining": "epsilon_ij=sqrt(epsilon_i*epsilon_j)",
        "override_precedence": (
            "exact_full_sigma_epsilon_pair_override_before_1_4_scale"
        ),
        "partial_override": "prohibited",
    }
    assert document["pair_scaling_semantics"]["one_four"] == (
        "U_1_4=s_lj*U_lj+s_q*U_q"
    )
    assert document["charge_semantics"]["neutral_to_zero_inference"] == (
        "prohibited"
    )
    assert document["unit_system"]["energy_scale"] == "dimensionless"
    deferred = set(document["deferred_evaluation_method_fields"])
    assert {
        "coulomb_coefficient",
        "relative_dielectric",
        "r_switch",
        "r_cut",
        "periodic_boundary_conditions",
        "long_range_method",
        "dtype",
        "device",
    } <= deferred


def test_parameter_artifact_is_complete_exact_neutral_and_nonpromoting() -> None:
    parameter_set = _parameter_set()
    document = parameter_set.to_dict()

    assert document["schema_id"] == LINEAR_ALKANE_PARAMETER_SET_SCHEMA_ID
    assert len(parameter_set.environment_mappings) == 6
    assert len(parameter_set.lj_type_parameters) == 6
    assert len(parameter_set.charge_parameters) == 4
    assert len(parameter_set.lj_pair_overrides) == 1
    assert len(parameter_set.bond_rules) == 6
    assert len(parameter_set.angle_rules) == 9
    assert len(parameter_set.proper_rules) == 7
    assert parameter_set.component_charge_sums_e == (
        ("methane_c1", 0.0),
        ("ethane_c2", 0.0),
        ("propane_c3", 0.0),
        ("n_butane_c4", 0.0),
    )
    assert LINEAR_ALKANE_CHARGE_BALANCE_TOLERANCE_E == 1.0e-12
    assert parameter_set.contract_key_universe_complete is True
    assert parameter_set.artifact_purpose == "contract_fixture_only"
    assert parameter_set.derivation_status == "declared_contract_fixture"
    assert document["charge_assignment_status"] == (
        "nonphysical_contract_fixture_explicit_lookup"
    )
    assert document["parameter_source_sha256"] is None
    assert document["dataset_manifest_sha256"] is None
    assert document["scientific_review_sha256"] is None
    assert document["license_review_sha256"] is None
    assert document["release_attestation_sha256"] is None
    for gate in (
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
        "minimization_authorized",
        "simulation_ready",
        "claim_safe",
    ):
        assert document[gate] is False
    assert len(parameter_set.parameter_payload_sha256) == 64
    assert len(parameter_set.parameter_set_sha256) == 64
    assert parameter_set.parameter_payload_sha256 == (
        "ef3a4514b3e19ab0e38e57191498bc1ec7ddf43c4984d652e8524826671a721d"
    )
    assert parameter_set.parameter_set_sha256 == (
        "b62a32f50d7a0f73a1ae82fdb54b90715252d1d49613634d345c475cc98fbe22"
    )
    assert document["parameter_set_sha256"] == parameter_set.parameter_set_sha256
    payload_text = json.dumps(document["parameter_payload"], sort_keys=True)
    assert "Atom.partial_charge_e" not in payload_text
    assert "formal_charge" not in payload_text


def test_strict_serialization_round_trip_and_hashes() -> None:
    parameter_set = _parameter_set()
    serialized = serialize_linear_alkane_c1_c4_parameter_set(parameter_set)
    restored = deserialize_linear_alkane_c1_c4_parameter_set(serialized)

    assert len(serialized) == 14805
    assert hashlib.sha256(serialized).hexdigest() == (
        "e2ae7fba6794c7f58dbc0940b0558a12daed728191cc54c8c03d999d0828e4a5"
    )
    assert restored == parameter_set
    assert serialize_linear_alkane_c1_c4_parameter_set(restored) == serialized
    assert restored.parameter_payload_sha256 == parameter_set.parameter_payload_sha256
    assert restored.parameter_set_sha256 == parameter_set.parameter_set_sha256
    assert serialized == json.dumps(
        json.loads(serialized),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def test_lj_exact_override_precedes_lorentz_berthelot() -> None:
    parameter_set = _parameter_set()
    overridden = resolve_linear_alkane_lj_pair(
        parameter_set,
        "ff.h_terminal",
        "ff.c_internal",
    )
    assert overridden.resolution_status == "exact_pair_override"
    assert overridden.override_id == "override.ci_ht"
    assert overridden.sigma_angstrom == 2.75
    assert overridden.epsilon_kilojoule_per_mole == 0.2

    combined = resolve_linear_alkane_lj_pair(
        parameter_set,
        "ff.c_methane",
        "ff.h_internal",
    )
    by_type = {
        row.force_field_type_id: row
        for row in parameter_set.lj_type_parameters
    }
    first = by_type["ff.c_methane"]
    second = by_type["ff.h_internal"]
    assert combined.resolution_status == "lorentz_berthelot"
    assert combined.override_id is None
    assert combined.sigma_angstrom == pytest.approx(
        0.5 * (first.sigma_angstrom + second.sigma_angstrom),
        rel=0.0,
        abs=0.0,
    )
    assert combined.epsilon_kilojoule_per_mole == pytest.approx(
        math.sqrt(
            first.epsilon_kilojoule_per_mole
            * second.epsilon_kilojoule_per_mole
        ),
        rel=0.0,
        abs=0.0,
    )
    with pytest.raises(LinearAlkaneParameterContractError, match="known"):
        resolve_linear_alkane_lj_pair(parameter_set, "ff.unknown", "ff.h_internal")


def test_lj_combining_is_safe_at_binary64_extremes() -> None:
    parameter_set = _parameter_set()
    maximum = sys.float_info.max
    minimum = math.nextafter(0.0, 1.0)
    maximum_rows = tuple(
        replace(row, sigma_angstrom=maximum, epsilon_kilojoule_per_mole=maximum)
        for row in parameter_set.lj_type_parameters
    )
    maximum_set = replace(parameter_set, lj_type_parameters=maximum_rows)
    maximum_pair = resolve_linear_alkane_lj_pair(
        maximum_set,
        "ff.c_methane",
        "ff.h_internal",
    )
    assert maximum_pair.sigma_angstrom == maximum
    assert maximum_pair.epsilon_kilojoule_per_mole == pytest.approx(
        maximum,
        rel=2.0e-16,
    )

    minimum_rows = tuple(
        replace(row, sigma_angstrom=minimum, epsilon_kilojoule_per_mole=minimum)
        for row in parameter_set.lj_type_parameters
    )
    minimum_set = replace(parameter_set, lj_type_parameters=minimum_rows)
    minimum_pair = resolve_linear_alkane_lj_pair(
        minimum_set,
        "ff.c_methane",
        "ff.h_internal",
    )
    assert minimum_pair.sigma_angstrom == minimum
    assert minimum_pair.epsilon_kilojoule_per_mole == minimum


def test_charge_balance_is_explicit_nonzero_and_fail_closed() -> None:
    parameter_set = _parameter_set()
    charge_by_id = {
        row.charge_parameter_id: row.partial_charge_e
        for row in parameter_set.charge_parameters
    }
    assert charge_by_id == {
        "charge.c_internal": -0.125,
        "charge.c_methane": -0.25,
        "charge.c_terminal": -0.1875,
        "charge.h": 0.0625,
    }

    changed = tuple(
        replace(row, partial_charge_e=0.0626)
        if row.charge_parameter_id == "charge.h"
        else row
        for row in parameter_set.charge_parameters
    )
    with pytest.raises(ValueError, match="do not sum"):
        replace(parameter_set, charge_parameters=changed)

    zeroed = tuple(
        replace(row, partial_charge_e=0.0)
        for row in parameter_set.charge_parameters
    )
    with pytest.raises(ValueError, match="positive and negative"):
        replace(parameter_set, charge_parameters=zeroed)

    overflowed = tuple(
        replace(row, partial_charge_e=sys.float_info.max)
        if row.charge_parameter_id in {"charge.c_methane", "charge.h"}
        else row
        for row in parameter_set.charge_parameters
    )
    with pytest.raises(ValueError, match="summation overflowed"):
        replace(parameter_set, charge_parameters=overflowed)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("environment_mappings", lambda p: p.environment_mappings[:-1], "environment"),
        ("lj_type_parameters", lambda p: p.lj_type_parameters[:-1], "LJ rows"),
        ("bond_rules", lambda p: p.bond_rules[:-1], "six-key"),
        ("angle_rules", lambda p: p.angle_rules[:-1], "nine-key"),
        ("proper_rules", lambda p: p.proper_rules[:-1], "seven-key"),
    ],
)
def test_missing_exact_domain_rows_are_rejected(
    field: str,
    value,
    message: str,
) -> None:
    parameter_set = _parameter_set()
    with pytest.raises((TypeError, ValueError), match=message):
        replace(parameter_set, **{field: value(parameter_set)})


def test_mapping_reference_duplicate_and_override_failures() -> None:
    parameter_set = _parameter_set()
    first, second, *rest = parameter_set.environment_mappings
    duplicated_type = tuple(
        sorted(
            (
                first,
                replace(second, force_field_type_id=first.force_field_type_id),
                *rest,
            )
        )
    )
    with pytest.raises(ValueError, match="one-to-one"):
        replace(parameter_set, environment_mappings=duplicated_type)

    unknown_charge = tuple(
        sorted(
            (
                replace(first, charge_parameter_id="charge.unknown"),
                second,
                *rest,
            )
        )
    )
    with pytest.raises(ValueError, match="charge rows"):
        replace(parameter_set, environment_mappings=unknown_charge)

    bad_override = (
        replace(
            parameter_set.lj_pair_overrides[0],
            force_field_type_j="ff.z_unknown",
        ),
    )
    with pytest.raises(ValueError, match="known types"):
        replace(parameter_set, lj_pair_overrides=bad_override)

    duplicate_parameter_id = (
        parameter_set.bond_rules[0],
        replace(
            parameter_set.bond_rules[1],
            parameter_id=parameter_set.bond_rules[0].parameter_id,
        ),
        *parameter_set.bond_rules[2:],
    )
    with pytest.raises(ValueError, match="globally unique"):
        replace(parameter_set, bond_rules=tuple(sorted(duplicate_parameter_id)))


def test_numeric_domains_and_exact_builtin_types_are_enforced() -> None:
    with pytest.raises(ValueError, match="negative zero"):
        LinearAlkanePartialChargeParameter("charge.test", -0.0)
    with pytest.raises(ValueError, match="finite"):
        LinearAlkanePartialChargeParameter("charge.test", float("nan"))
    with pytest.raises(ValueError, match="positive"):
        LinearAlkaneLennardJonesTypeParameter("ff.test", 0.0, 1.0)
    with pytest.raises(TypeError, match="exact integer"):
        LinearAlkaneProperTorsionComponent(True, 0.0, 1.0)
    with pytest.raises(ValueError, match=r"\[1, 6\]"):
        LinearAlkaneProperTorsionComponent(7, 0.0, 1.0)
    with pytest.raises(ValueError, match=r"\[0, 2\*pi\)"):
        LinearAlkaneProperTorsionComponent(1, math.tau, 1.0)
    with pytest.raises(ValueError, match="exceed one"):
        replace(_parameter_set(), one_four_lj_energy_scale=1.0001)
    with pytest.raises(ValueError, match="non-negative"):
        replace(_parameter_set(), one_four_coulomb_energy_scale=-0.125)

    class _StringSubclass(str):
        def __hash__(self) -> int:
            raise RuntimeError("forged hash invoked")

    with pytest.raises(TypeError, match="exact string"):
        module.ResolvedLinearAlkaneLennardJonesPair(
            "ff.a",
            "ff.b",
            1.0,
            1.0,
            _StringSubclass("lorentz_berthelot"),
            None,
        )


def test_forged_rows_are_revalidated_before_ordering_or_serialization() -> None:
    parameter_set = _parameter_set()

    class _ExplosiveStringSubclass(str):
        def __lt__(self, other: object) -> bool:
            raise RuntimeError("forged comparison invoked")

    for row in parameter_set.environment_mappings:
        object.__setattr__(
            row,
            "topological_environment_id",
            _ExplosiveStringSubclass(row.topological_environment_id),
        )
    with pytest.raises(TypeError, match="exact string"):
        serialize_linear_alkane_c1_c4_parameter_set(parameter_set)

    numeric_parameter_set = _parameter_set()
    object.__setattr__(
        numeric_parameter_set.lj_type_parameters[0],
        "sigma_angstrom",
        float("nan"),
    )
    with pytest.raises(ValueError, match="finite"):
        serialize_linear_alkane_c1_c4_parameter_set(numeric_parameter_set)


def _signed_dihedral(points: torch.Tensor) -> float:
    atom_i, atom_j, atom_k, atom_l = points
    bond_1 = atom_j - atom_i
    bond_2 = atom_k - atom_j
    bond_3 = atom_l - atom_k
    normal_1 = torch.linalg.cross(bond_1, bond_2)
    normal_2 = torch.linalg.cross(bond_2, bond_3)
    middle_hat = bond_2 / torch.linalg.vector_norm(bond_2)
    return math.atan2(
        float(torch.dot(torch.linalg.cross(normal_1, normal_2), middle_hat)),
        float(torch.dot(normal_1, normal_2)),
    )


def test_signed_dihedral_and_proper_energy_are_full_reversal_invariant() -> None:
    generator = torch.Generator().manual_seed(20260711)
    component = LinearAlkaneProperTorsionComponent(3, 0.73, 1.25)
    for _ in range(64):
        points = torch.randn((4, 3), generator=generator, dtype=torch.float64)
        forward = _signed_dihedral(points)
        reverse = _signed_dihedral(torch.flip(points, dims=(0,)))
        assert reverse == pytest.approx(forward, rel=0.0, abs=1.0e-14)
        forward_energy = component.amplitude_kilojoule_per_mole * (
            1.0
            + math.cos(
                component.periodicity * forward - component.phase_radian
            )
        )
        reverse_energy = component.amplitude_kilojoule_per_mole * (
            1.0
            + math.cos(
                component.periodicity * reverse - component.phase_radian
            )
        )
        assert reverse_energy == pytest.approx(
            forward_energy,
            rel=0.0,
            abs=1.0e-14,
        )


def test_protocol_universe_equals_live_c1_c4_inventory_union() -> None:
    sources = (
        METHANE,
        ALKANES / "ethane_explicit_h.sdf",
        ALKANES / "propane_explicit_h.sdf",
        ALKANES / "n_butane_explicit_h.sdf",
    )
    environments: set[str] = set()
    bond_keys: set[tuple[str, str]] = set()
    angle_keys: set[tuple[str, str, str]] = set()
    proper_keys: set[tuple[str, str, str, str]] = set()
    for source in sources:
        system = parse_sdf_v2000(
            source.read_bytes(),
            source_id=source.stem,
        ).system
        report = analyze_linear_alkane_term_pair_inventory(system)
        for term in report.bond_terms:
            bond_keys.add(tuple(term.match_key.to_dict().values()))
        for term in report.angle_terms:
            angle_keys.add(tuple(term.match_key.to_dict().values()))
        for term in report.proper_terms:
            proper_keys.add(tuple(term.match_key.to_dict().values()))
        for term in (*report.bond_terms, *report.angle_terms, *report.proper_terms):
            environments.update(term.match_key.to_dict().values())
        if not report.proper_terms and not report.angle_terms:
            environments.update(
                assignment.topological_environment_id
                for assignment in (
                    report._analysis().typing_report.environment_assignments
                )
            )
        else:
            environments.update(
                assignment.topological_environment_id
                for assignment in (
                    report._analysis().typing_report.environment_assignments
                )
            )

    assert tuple(sorted(environments)) == LINEAR_ALKANE_PARAMETER_ENVIRONMENT_IDS
    assert tuple(sorted(bond_keys)) == LINEAR_ALKANE_PARAMETER_BOND_KEYS
    assert tuple(sorted(angle_keys)) == LINEAR_ALKANE_PARAMETER_ANGLE_KEYS
    assert tuple(sorted(proper_keys)) == LINEAR_ALKANE_PARAMETER_PROPER_KEYS


def test_strict_deserializer_rejects_tamper_duplicates_and_noncanonical_json() -> None:
    serialized = serialize_linear_alkane_c1_c4_parameter_set(_parameter_set())
    document = json.loads(serialized)

    stale = dict(document)
    stale["parameter_payload_sha256"] = "0" * 64
    stale_bytes = json.dumps(
        stale,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    with pytest.raises(
        LinearAlkaneParameterSerializationError,
        match="noncanonical|stale|tampered",
    ):
        deserialize_linear_alkane_c1_c4_parameter_set(stale_bytes)

    unknown = json.loads(serialized)
    unknown["parameter_payload"]["unknown"] = False
    unknown_bytes = json.dumps(
        unknown,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    with pytest.raises(LinearAlkaneParameterSerializationError, match="keys"):
        deserialize_linear_alkane_c1_c4_parameter_set(unknown_bytes)

    duplicate = serialized.replace(
        b'{"artifact_purpose":',
        b'{"artifact_purpose":"forged","artifact_purpose":',
        1,
    )
    with pytest.raises(LinearAlkaneParameterSerializationError, match="duplicate"):
        deserialize_linear_alkane_c1_c4_parameter_set(duplicate)

    with pytest.raises(LinearAlkaneParameterSerializationError, match="noncanonical"):
        deserialize_linear_alkane_c1_c4_parameter_set(b" " + serialized)
    with pytest.raises(LinearAlkaneParameterSerializationError, match="exact bytes"):
        deserialize_linear_alkane_c1_c4_parameter_set(
            bytearray(serialized)  # type: ignore[arg-type]
        )
    with pytest.raises(LinearAlkaneParameterSerializationError, match="one-megabyte"):
        deserialize_linear_alkane_c1_c4_parameter_set(b" " * (1024 * 1024 + 1))

    overflow = json.loads(serialized)
    for row in overflow["parameter_payload"]["charge_parameters"]:
        if row["charge_parameter_id"] in {
            "charge.c_methane",
            "charge.h",
        }:
            row["partial_charge_e_binary64"] = "7fefffffffffffff"
    overflow_bytes = json.dumps(
        overflow,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    with pytest.raises(
        LinearAlkaneParameterSerializationError,
        match="summation overflowed",
    ):
        deserialize_linear_alkane_c1_c4_parameter_set(overflow_bytes)


def test_slotted_frozen_and_public_label_mutation_is_nonsemantic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parameter_set = _parameter_set()
    baseline = serialize_linear_alkane_c1_c4_parameter_set(parameter_set)
    assert not hasattr(parameter_set, "__dict__")
    assert all(not hasattr(row, "__dict__") for row in parameter_set.bond_rules)
    with pytest.raises(FrozenInstanceError):
        parameter_set.one_four_lj_energy_scale = 0.25  # type: ignore[misc]

    for name in (
        "LINEAR_ALKANE_PARAMETER_PROTOCOL_SCHEMA_ID",
        "LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256",
        "LINEAR_ALKANE_PARAMETER_SET_SCHEMA_ID",
        "LINEAR_ALKANE_PARAMETER_SCOPE",
        "LINEAR_ALKANE_LJ_COMBINING_RULE_ID",
        "LINEAR_ALKANE_PROPER_FUNCTIONAL_FORM_ID",
    ):
        monkeypatch.setattr(module, name, "forged")
    assert serialize_linear_alkane_c1_c4_parameter_set(parameter_set) == baseline

    object.__setattr__(parameter_set, "one_four_lj_energy_scale", 2.0)
    with pytest.raises(ValueError, match="exceed one"):
        _ = parameter_set.claim_safe


def test_nested_match_key_object_tamper_is_detected_before_serialization() -> None:
    parameter_set = _parameter_set()

    class _StringSubclass(str):
        pass

    match_key = parameter_set.bond_rules[0].match_key
    object.__setattr__(
        match_key,
        "environment_i",
        _StringSubclass(match_key.environment_i),
    )
    with pytest.raises(TypeError, match="must be a string"):
        serialize_linear_alkane_c1_c4_parameter_set(parameter_set)


def test_protocol_and_artifact_hashes_are_stable_across_hash_seeds() -> None:
    script = """
from tests.unit.test_engine_v2_linear_alkane_parameters import _parameter_set
from betelgeuze_engine_v2.forcefield.linear_alkane_parameters import (
    LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256,
)
p = _parameter_set()
print(LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256)
print(p.parameter_payload_sha256)
print(p.parameter_set_sha256)
"""
    outputs = []
    for seed in ("0", "1", "97"):
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = seed
        environment["PYTHONPATH"] = str(REPO_ROOT)
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(result.stdout)
    assert len(set(outputs)) == 1


def test_protocol_is_stable_when_upstream_public_aliases_are_forged_preimport() -> None:
    clean_script = """
from betelgeuze_engine_v2.forcefield.linear_alkane_parameters import (
    LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256,
    linear_alkane_parameter_protocol_document,
)
print(LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256)
print(linear_alkane_parameter_protocol_document()['bond_angle_functional_form_id'])
"""
    forged_script = """
from betelgeuze_engine_v2.forcefield import parameters, term_inventory, typing
parameters.EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID = 'forged.form/9.9.9'
typing.LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_ID = 'forged.typing/9.9.9'
typing.LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_ASSIGNMENT_POLICY_ID = 'forged.typing.policy/9.9.9'
term_inventory.LINEAR_ALKANE_TERM_PAIR_INVENTORY_SCHEMA_ID = 'forged.inventory/9.9.9'
term_inventory.LINEAR_ALKANE_PAIR_CLASSIFICATION_POLICY_ID = 'forged.pairs/9.9.9'
from betelgeuze_engine_v2.forcefield.linear_alkane_parameters import (
    LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256,
    linear_alkane_parameter_protocol_document,
)
print(LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256)
print(linear_alkane_parameter_protocol_document()['bond_angle_functional_form_id'])
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(REPO_ROOT)
    clean = subprocess.run(
        [sys.executable, "-c", clean_script],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    forged = subprocess.run(
        [sys.executable, "-c", forged_script],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert forged == clean
