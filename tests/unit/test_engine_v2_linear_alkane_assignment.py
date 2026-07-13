from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.forcefield import linear_alkane_assignment as module
from betelgeuze_engine_v2.forcefield.linear_alkane_assignment import (
    LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_CLAIM_SCOPE,
    LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_POLICY_ID,
    LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_SCHEMA_ID,
    LinearAlkaneC1C4ParameterAssignmentReport,
    LinearAlkanePairParameterAssignment,
    LinearAlkaneParameterAssignmentContractError,
    analyze_linear_alkane_c1_c4_parameter_assignment,
    serialize_linear_alkane_c1_c4_parameter_assignment_report,
)
from betelgeuze_engine_v2.forcefield.linear_alkane_parameters import (
    LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256,
    LinearAlkaneC1C4ParameterSet,
    LinearAlkanePartialChargeParameter,
    resolve_linear_alkane_lj_pair,
)
from betelgeuze_engine_v2.molecular import parse_sdf_v2000
from betelgeuze_engine_v2.molecular.observation import (
    attach_parser_observation_digest,
)
from tests.unit.test_engine_v2_linear_alkane_parameters import _parameter_set


REPO_ROOT = Path(__file__).resolve().parents[2]
METHANE = REPO_ROOT / "tests/fixtures/v2_1_ingest_corpus/methane_explicit_h.sdf"
ALKANES = REPO_ROOT / "tests/fixtures/v2_2_linear_alkane"

POSITIVE_CASES = (
    (
        METHANE,
        5,
        4,
        6,
        0,
        10,
        {"excluded_1_2": 4, "excluded_1_3": 6, "one_four_separate": 0, "full_nonbonded": 0},
        0,
        0,
    ),
    (
        ALKANES / "ethane_explicit_h.sdf",
        8,
        7,
        12,
        9,
        28,
        {"excluded_1_2": 7, "excluded_1_3": 12, "one_four_separate": 9, "full_nonbonded": 0},
        0,
        9,
    ),
    (
        ALKANES / "propane_explicit_h.sdf",
        11,
        10,
        18,
        18,
        55,
        {"excluded_1_2": 10, "excluded_1_3": 18, "one_four_separate": 18, "full_nonbonded": 9},
        0,
        27,
    ),
    (
        ALKANES / "n_butane_explicit_h.sdf",
        14,
        13,
        24,
        27,
        91,
        {"excluded_1_2": 13, "excluded_1_3": 24, "one_four_separate": 27, "full_nonbonded": 27},
        6,
        48,
    ),
)

GLOBAL_FALSE_GATES = (
    "evaluation_method_defined",
    "production_parameter_assignment_complete",
    "parameterability_assessed",
    "parameterizable",
    "production_force_field_atom_types_assigned",
    "production_partial_charges_assigned",
    "production_force_field_parameters_assigned",
    "global_parameter_coverage_complete",
    "preparation_ready",
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
)


def _system(path: Path):
    return parse_sdf_v2000(path.read_bytes(), source_id=path.stem).system


@pytest.mark.parametrize(
    (
        "path",
        "atom_count",
        "bond_count",
        "angle_count",
        "proper_count",
        "pair_count",
        "pair_counts",
        "override_count",
        "combined_count",
    ),
    POSITIVE_CASES,
    ids=("methane", "ethane", "propane", "n_butane"),
)
def test_positive_c1_c4_assignments_cover_exact_inventory_and_stay_nonpromoting(
    path: Path,
    atom_count: int,
    bond_count: int,
    angle_count: int,
    proper_count: int,
    pair_count: int,
    pair_counts: dict[str, int],
    override_count: int,
    combined_count: int,
) -> None:
    parameter_set = _parameter_set()
    system = _system(path)
    report = analyze_linear_alkane_c1_c4_parameter_assignment(
        system,
        parameter_set,
    )
    document = report.to_dict()

    assert document["schema_id"] == (
        LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_SCHEMA_ID
    )
    assert document["assignment_policy_id"] == (
        LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_POLICY_ID
    )
    assert document["claim_scope"] == (
        LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_CLAIM_SCOPE
    )
    assert document["assignment_status"] == "contract_fixture_mapped"
    assert document["atom_count"] == atom_count
    assert document["bond_assignment_count"] == bond_count
    assert document["angle_assignment_count"] == angle_count
    assert document["proper_assignment_count"] == proper_count
    assert document["pair_assignment_count"] == pair_count
    assert document["pair_class_counts"] == pair_counts
    assert document["excluded_pair_count"] == (
        pair_counts["excluded_1_2"] + pair_counts["excluded_1_3"]
    )
    assert document["mapped_nonexcluded_pair_count"] == (
        pair_counts["one_four_separate"] + pair_counts["full_nonbonded"]
    )
    assert document["exact_pair_override_count"] == override_count
    assert document["lorentz_berthelot_pair_count"] == combined_count
    assert document["component_partial_charge_sum_e_binary64"] == (
        "0000000000000000"
    )
    assert document["component_charge_balance_status"] == (
        "balanced_contract_fixture"
    )
    assert document["failed_constraint_codes"] == []
    assert all(row["passed"] for row in document["constraint_results"])
    for name in (
        "bounded_contract_fixture_atom_mapping_complete",
        "bounded_contract_fixture_bonded_mapping_complete",
        "bounded_contract_fixture_pair_mapping_complete",
        "bounded_contract_fixture_charge_balance_complete",
        "bounded_contract_fixture_assignment_complete",
    ):
        assert document[name] is True
    for name in GLOBAL_FALSE_GATES:
        assert document[name] is False
    assert document["parameter_protocol_sha256"] == (
        LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256
    )
    assert document["parameter_payload_sha256"] == (
        parameter_set.parameter_payload_sha256
    )
    assert document["parameter_set_sha256"] == parameter_set.parameter_set_sha256
    assert document["parameter_scope"] == (
        "bounded_c1_c4_full_parameter_contract_fixture_only"
    )
    assert document["parameter_domain_id"] == (
        "source_explicit_h_sdf_v2000_linear_alkane_c1_c4_exact_keys/1.0.0"
    )
    assert document["parameter_artifact_authentication_status"] == (
        "not_authenticated"
    )
    assert document["deferred_evaluation_method_status"] == "not_defined"
    assert all(
        row["value_source"] == "declared_nonphysical_contract_fixture_row"
        for row in document["atom_assignments"]
    )
    assert len(document["parameter_assignment_sha256"]) == 64
    assert len(document["report_sha256"]) == 64
    if path.name == "n_butane_explicit_h.sdf":
        serialized = serialize_linear_alkane_c1_c4_parameter_assignment_report(
            report
        )
        assert len(serialized) == 102721
        assert hashlib.sha256(serialized).hexdigest() == (
            "a45f6eefe72e774c90da7a7665d2c000142be7d4ec6409ec3914e87cf14db25e"
        )
        assert document["parameter_assignment_sha256"] == (
            "f8ae5b5ad1285c78847244702a67e53cec21291e3986473ad6e6f95f5aecd737"
        )
        assert document["report_sha256"] == (
            "4f59e523913670752e843a0aa9c813f0f2a25bc9422744b4a8aaeb9214f2a698"
        )


def test_atom_and_bonded_rows_resolve_only_from_bound_parameter_tables() -> None:
    parameter_set = _parameter_set()
    report = analyze_linear_alkane_c1_c4_parameter_assignment(
        _system(ALKANES / "n_butane_explicit_h.sdf"),
        parameter_set,
    )
    analysis = report._analysis()
    mapping_by_environment = {
        row.topological_environment_id: row
        for row in parameter_set.environment_mappings
    }
    charge_by_id = {
        row.charge_parameter_id: row for row in parameter_set.charge_parameters
    }
    lj_by_type = {
        row.force_field_type_id: row for row in parameter_set.lj_type_parameters
    }
    for row in analysis.atom_assignments:
        mapping = mapping_by_environment[row.topological_environment_id]
        assert row.force_field_type_id == mapping.force_field_type_id
        assert row.charge_parameter_id == mapping.charge_parameter_id
        assert row.partial_charge_e == charge_by_id[
            mapping.charge_parameter_id
        ].partial_charge_e
        assert row.lj_sigma_angstrom == lj_by_type[
            mapping.force_field_type_id
        ].sigma_angstrom

    bond_by_key = {row.match_key: row for row in parameter_set.bond_rules}
    angle_by_key = {row.match_key: row for row in parameter_set.angle_rules}
    proper_by_key = {row.match_key: row for row in parameter_set.proper_rules}
    assert all(
        row.parameter_id == bond_by_key[row.match_key].parameter_id
        for row in analysis.bond_assignments
    )
    assert all(
        row.parameter_id == angle_by_key[row.match_key].parameter_id
        for row in analysis.angle_assignments
    )
    assert all(
        row.parameter_id == proper_by_key[row.match_key].parameter_id
        and row.components == proper_by_key[row.match_key].components
        for row in analysis.proper_assignments
    )


def test_component_charge_uses_frozen_environment_order_not_atom_order() -> None:
    parameter_set = _parameter_set()
    charge_values = {
        "c_single_valence4_c0_h4": -4.0,
        "h_attached_c_single_valence4_c0_h4": 1.0,
        "c_single_valence4_c1_h3": -3.0,
        "h_attached_c_single_valence4_c1_h3": 1.0,
        "c_single_valence4_c2_h2": -2.0e16,
        "h_attached_c_single_valence4_c2_h2": 1.0e16,
    }
    mappings = tuple(
        sorted(
            replace(
                row,
                charge_parameter_id=(
                    f"charge.order_sensitive.{row.topological_environment_id}"
                ),
            )
            for row in parameter_set.environment_mappings
        )
    )
    charges = tuple(
        sorted(
            LinearAlkanePartialChargeParameter(
                f"charge.order_sensitive.{environment_id}",
                value,
            )
            for environment_id, value in charge_values.items()
        )
    )
    order_sensitive_set = replace(
        parameter_set,
        environment_mappings=mappings,
        charge_parameters=charges,
    )
    report = analyze_linear_alkane_c1_c4_parameter_assignment(
        _system(ALKANES / "propane_explicit_h.sdf"),
        order_sensitive_set,
    )
    analysis = report._analysis()

    assert sum(row.partial_charge_e for row in analysis.atom_assignments) != 0.0
    assert analysis.component_partial_charge_sum_e == 0.0


def test_pair_rows_keep_endpoint_identity_override_precedence_and_scale_scope() -> None:
    parameter_set = _parameter_set()
    report = analyze_linear_alkane_c1_c4_parameter_assignment(
        _system(ALKANES / "n_butane_explicit_h.sdf"),
        parameter_set,
    )
    analysis = report._analysis()
    atoms = {row.atom_index: row for row in analysis.atom_assignments}
    pairs = analysis.pair_assignments
    for row in pairs:
        if row.interaction_class in {"excluded_1_2", "excluded_1_3"}:
            assert row.parameter_status == "excluded_no_parameter_mapping"
            assert row.lj_resolution_status is None
            assert row.lj_energy_scale is None
            assert row.coulomb_energy_scale is None
            continue
        atom_i = atoms[row.identity.atom_i]
        atom_j = atoms[row.identity.atom_j]
        assert row.parameter_status == (
            "mapped_nonphysical_contract_fixture_method_deferred"
        )
        assert row.atom_i_force_field_type_id == atom_i.force_field_type_id
        assert row.atom_j_force_field_type_id == atom_j.force_field_type_id
        assert row.atom_i_charge_parameter_id == atom_i.charge_parameter_id
        assert row.atom_j_charge_parameter_id == atom_j.charge_parameter_id
        resolved = resolve_linear_alkane_lj_pair(
            parameter_set,
            atom_i.force_field_type_id,
            atom_j.force_field_type_id,
        )
        assert (row.resolved_lj_type_i, row.resolved_lj_type_j) == (
            resolved.force_field_type_i,
            resolved.force_field_type_j,
        )
        assert row.lj_resolution_status == resolved.resolution_status
        assert row.lj_override_id == resolved.override_id
        assert row.lj_sigma_angstrom == resolved.sigma_angstrom
        assert row.lj_epsilon_kilojoule_per_mole == (
            resolved.epsilon_kilojoule_per_mole
        )
        if row.interaction_class == "one_four_separate":
            assert row.lj_energy_scale == parameter_set.one_four_lj_energy_scale
            assert row.coulomb_energy_scale == (
                parameter_set.one_four_coulomb_energy_scale
            )
        else:
            assert row.lj_energy_scale is None
            assert row.coulomb_energy_scale is None

    assert sum(row.lj_resolution_status == "exact_pair_override" for row in pairs) == 6
    document_text = json.dumps(report.to_dict(), sort_keys=True)
    for forbidden in (
        "coulomb_coefficient",
        "charge_product",
        "pair_energy",
        "force_vector",
        "virial_tensor",
    ):
        assert forbidden not in document_text


@pytest.mark.parametrize(
    ("kind", "expected_status"),
    (("unsupported", "unsupported_system"), ("invalid", "invalid_system")),
)
def test_unavailable_systems_return_empty_fail_closed_reports(
    kind: str,
    expected_status: str,
) -> None:
    if kind == "unsupported":
        system = _system(ALKANES / "isobutane_branched_explicit_h.sdf")
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
    report = analyze_linear_alkane_c1_c4_parameter_assignment(
        system,
        _parameter_set(),
    )
    document = report.to_dict()

    assert document["assignment_status"] == expected_status
    assert document["atom_assignments"] == []
    assert document["bond_assignments"] == []
    assert document["angle_assignments"] == []
    assert document["proper_assignments"] == []
    assert document["pair_assignments"] == []
    assert document["parameter_assignment_sha256"] is None
    assert document["bounded_contract_fixture_assignment_complete"] is False
    assert document["failed_constraint_codes"]
    assert all(document[name] is False for name in GLOBAL_FALSE_GATES)


def test_report_binds_fresh_upstream_hash_dag_and_canonical_bytes() -> None:
    parameter_set = _parameter_set()
    system = _system(METHANE)
    report = analyze_linear_alkane_c1_c4_parameter_assignment(
        system,
        parameter_set,
    )
    analysis = report._analysis()
    document = report.to_dict()
    serialized = serialize_linear_alkane_c1_c4_parameter_assignment_report(report)

    assert len(serialized) == 18220
    assert hashlib.sha256(serialized).hexdigest() == (
        "7a2e37b34ac6e29903cef2638f4638147449b373a7a3fa4c664093f976070987"
    )
    assert document["parameter_assignment_sha256"] == (
        "8bce98549a7d055c63c777f3a3745e2f4ea73b990c570c16e91fabc7bac07c17"
    )
    assert document["report_sha256"] == (
        "3fb851f5ffec11532f5046d5903b17eafcfb0a9cca5591a3276adfd4afe42a45"
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
        json.dumps(
            core,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest() == report_sha256
    assert document["applicability_report_sha256"] == (
        analysis.applicability.report_sha256
    )
    assert document["typing_report_sha256"] == (
        analysis.typing_report.report_sha256
    )
    assert document["inventory_report_sha256"] == (
        analysis.inventory.report_sha256
    )
    assert report.matches(system, parameter_set) is True
    assert report.matches(
        _system(ALKANES / "ethane_explicit_h.sdf"),
        parameter_set,
    ) is False
    changed_lj_rows = (
        replace(
            parameter_set.lj_type_parameters[0],
            sigma_angstrom=(
                parameter_set.lj_type_parameters[0].sigma_angstrom + 0.125
            ),
        ),
        *parameter_set.lj_type_parameters[1:],
    )
    changed_parameter_set = replace(
        parameter_set,
        lj_type_parameters=changed_lj_rows,
    )
    assert report.matches(system, changed_parameter_set) is False


def test_snapshot_and_digest_tampering_is_detected_before_use() -> None:
    report = analyze_linear_alkane_c1_c4_parameter_assignment(
        _system(METHANE),
        _parameter_set(),
    )
    original_parameter_snapshot = report._canonical_parameter_snapshot
    object.__setattr__(
        report,
        "_canonical_parameter_snapshot",
        original_parameter_snapshot + b" ",
    )
    with pytest.raises(ValueError, match="digest binding"):
        report.to_dict()

    object.__setattr__(
        report,
        "_canonical_parameter_snapshot_sha256",
        hashlib.sha256(report._canonical_parameter_snapshot).hexdigest(),
    )
    with pytest.raises(ValueError, match="noncanonical|stale|tampered"):
        report.to_dict()

    system_report = analyze_linear_alkane_c1_c4_parameter_assignment(
        _system(METHANE),
        _parameter_set(),
    )
    object.__setattr__(
        system_report,
        "_canonical_system_snapshot",
        system_report._canonical_system_snapshot + b" ",
    )
    with pytest.raises(ValueError, match="digest binding"):
        system_report.to_dict()
    object.__setattr__(
        system_report,
        "_canonical_system_snapshot_sha256",
        hashlib.sha256(system_report._canonical_system_snapshot).hexdigest(),
    )
    with pytest.raises(ValueError, match="not canonical"):
        system_report.to_dict()


def test_forged_computed_rows_must_equal_a_fresh_cross_artifact_mapping() -> None:
    report = analyze_linear_alkane_c1_c4_parameter_assignment(
        _system(ALKANES / "n_butane_explicit_h.sdf"),
        _parameter_set(),
    )
    analysis = report._analysis()

    atom_rows = list(analysis.atom_assignments)
    atom_rows[0] = replace(
        atom_rows[0],
        partial_charge_e=atom_rows[0].partial_charge_e + 0.01,
    )
    bond_rows = list(analysis.bond_assignments)
    bond_rows[0] = replace(
        bond_rows[0],
        equilibrium_length_angstrom=(
            bond_rows[0].equilibrium_length_angstrom + 0.01
        ),
    )
    pair_rows = list(analysis.pair_assignments)
    pair_index = next(
        index
        for index, row in enumerate(pair_rows)
        if row.interaction_class == "one_four_separate"
    )
    pair_rows[pair_index] = replace(
        pair_rows[pair_index],
        atom_i_charge_parameter_id="charge.forged",
    )
    forged_analyses = (
        replace(analysis, atom_assignments=tuple(atom_rows)),
        replace(analysis, bond_assignments=tuple(bond_rows)),
        replace(analysis, pair_assignments=tuple(pair_rows)),
        replace(analysis, component_partial_charge_sum_e=5.0e-13),
    )
    for forged in forged_analyses:
        with pytest.raises(
            LinearAlkaneParameterAssignmentContractError,
            match="fresh parameter mapping",
        ):
            report._validate(forged)

def test_report_is_slotted_frozen_and_public_labels_are_nonsemantic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = analyze_linear_alkane_c1_c4_parameter_assignment(
        _system(METHANE),
        _parameter_set(),
    )
    baseline = serialize_linear_alkane_c1_c4_parameter_assignment_report(report)
    assert not hasattr(report, "__dict__")
    with pytest.raises(FrozenInstanceError):
        report._canonical_system_snapshot = b"forged"  # type: ignore[misc]
    for name in (
        "LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_SCHEMA_ID",
        "LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_POLICY_ID",
        "LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_CLAIM_SCOPE",
        "LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_STATUSES",
    ):
        monkeypatch.setattr(module, name, "forged")
    assert serialize_linear_alkane_c1_c4_parameter_assignment_report(report) == (
        baseline
    )


def test_pair_assignment_rejects_string_subclass_before_membership() -> None:
    report = analyze_linear_alkane_c1_c4_parameter_assignment(
        _system(ALKANES / "ethane_explicit_h.sdf"),
        _parameter_set(),
    )
    analysis = report._analysis()
    row = next(
        item
        for item in analysis.pair_assignments
        if item.interaction_class == "one_four_separate"
    )

    class _ExplosiveStringSubclass(str):
        def __hash__(self) -> int:
            raise RuntimeError("forged hash invoked")

    with pytest.raises(TypeError, match="exact string"):
        LinearAlkanePairParameterAssignment(
            identity=row.identity,
            shortest_graph_distance=row.shortest_graph_distance,
            interaction_class=_ExplosiveStringSubclass(row.interaction_class),
            parameter_status=row.parameter_status,
            atom_i_force_field_type_id=row.atom_i_force_field_type_id,
            atom_j_force_field_type_id=row.atom_j_force_field_type_id,
            atom_i_charge_parameter_id=row.atom_i_charge_parameter_id,
            atom_j_charge_parameter_id=row.atom_j_charge_parameter_id,
            atom_i_partial_charge_e=row.atom_i_partial_charge_e,
            atom_j_partial_charge_e=row.atom_j_partial_charge_e,
            resolved_lj_type_i=row.resolved_lj_type_i,
            resolved_lj_type_j=row.resolved_lj_type_j,
            lj_sigma_angstrom=row.lj_sigma_angstrom,
            lj_epsilon_kilojoule_per_mole=(
                row.lj_epsilon_kilojoule_per_mole
            ),
            lj_resolution_status=row.lj_resolution_status,
            lj_override_id=row.lj_override_id,
            lj_energy_scale=row.lj_energy_scale,
            coulomb_energy_scale=row.coulomb_energy_scale,
        )


def test_report_hash_is_stable_across_hash_seeds() -> None:
    script = """
from pathlib import Path
from tests.unit.test_engine_v2_linear_alkane_parameters import _parameter_set
from betelgeuze_engine_v2.molecular import parse_sdf_v2000
from betelgeuze_engine_v2.forcefield.linear_alkane_assignment import analyze_linear_alkane_c1_c4_parameter_assignment
path = Path('tests/fixtures/v2_2_linear_alkane/n_butane_explicit_h.sdf')
system = parse_sdf_v2000(path.read_bytes(), source_id=path.stem).system
report = analyze_linear_alkane_c1_c4_parameter_assignment(system, _parameter_set())
document = report.to_dict()
print(document['parameter_assignment_sha256'])
print(document['report_sha256'])
"""
    outputs = []
    for seed in ("0", "97"):
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


def test_exact_input_types_are_required() -> None:
    system = _system(METHANE)
    parameter_set = _parameter_set()
    with pytest.raises(TypeError, match="AllAtomSystem"):
        analyze_linear_alkane_c1_c4_parameter_assignment(
            object(),  # type: ignore[arg-type]
            parameter_set,
        )
    with pytest.raises(TypeError, match="parameter set"):
        analyze_linear_alkane_c1_c4_parameter_assignment(
            system,
            object(),  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="assignment report"):
        serialize_linear_alkane_c1_c4_parameter_assignment_report(
            object(),  # type: ignore[arg-type]
        )
    assert type(parameter_set) is LinearAlkaneC1C4ParameterSet
    assert type(
        analyze_linear_alkane_c1_c4_parameter_assignment(system, parameter_set)
    ) is LinearAlkaneC1C4ParameterAssignmentReport
