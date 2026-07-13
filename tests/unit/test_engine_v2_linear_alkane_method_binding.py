from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import torch

from betelgeuze_engine_v2.forcefield import linear_alkane_method_binding as module
from betelgeuze_engine_v2.forcefield.linear_alkane_assignment import (
    analyze_linear_alkane_c1_c4_parameter_assignment,
)
from betelgeuze_engine_v2.forcefield.linear_alkane_evaluation_method import (
    LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SHA256,
)
from betelgeuze_engine_v2.forcefield.linear_alkane_method_binding import (
    LINEAR_ALKANE_EVALUATION_METHOD_BINDING_CLAIM_SCOPE,
    LINEAR_ALKANE_EVALUATION_METHOD_BINDING_POLICY_ID,
    LINEAR_ALKANE_EVALUATION_METHOD_BINDING_SCHEMA_ID,
    LinearAlkaneC1C4EvaluationMethodBindingReport,
    analyze_linear_alkane_c1_c4_evaluation_method_binding,
    serialize_linear_alkane_c1_c4_evaluation_method_binding_report,
)
from betelgeuze_engine_v2.forcefield.linear_alkane_parameters import (
    LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256,
)
from betelgeuze_engine_v2.molecular import parse_sdf_v2000
from betelgeuze_engine_v2.molecular.models import UnitCell
from betelgeuze_engine_v2.molecular.observation import (
    attach_parser_observation_digest,
)
from betelgeuze_engine_v2.molecular.validation import MolecularValidationError
from tests.unit.test_engine_v2_linear_alkane_evaluation_method import _method
from tests.unit.test_engine_v2_linear_alkane_parameters import _parameter_set


REPO_ROOT = Path(__file__).resolve().parents[2]
METHANE = REPO_ROOT / "tests/fixtures/v2_1_ingest_corpus/methane_explicit_h.sdf"
ALKANES = REPO_ROOT / "tests/fixtures/v2_2_linear_alkane"

POSITIVE_CASES = (
    (METHANE, False, 5, 4, 6, 0, 10, 10, 0),
    (ALKANES / "ethane_explicit_h.sdf", False, 8, 7, 12, 9, 28, 19, 9),
    (
        ALKANES / "propane_explicit_h.sdf",
        False,
        11,
        10,
        18,
        18,
        55,
        28,
        27,
    ),
    (
        ALKANES / "n_butane_explicit_h.sdf",
        True,
        14,
        13,
        24,
        27,
        91,
        37,
        54,
    ),
)

GLOBAL_FALSE_GATES = (
    "evaluation_executed",
    "energy_evaluated",
    "forces_evaluated",
    "virial_evaluated",
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
    "minimization_authorized",
    "simulation_ready",
    "claim_safe",
)


def _system(path: Path):
    return parse_sdf_v2000(path.read_bytes(), source_id=path.stem).system


def _with_fresh_observation(system, **changes):
    return attach_parser_observation_digest(replace(system, **changes))


def _method_compatible_butane():
    system = _system(ALKANES / "n_butane_explicit_h.sdf")
    coordinates = system.coordinates.clone()
    # The source fixture deliberately contains one exactly opposed H-C-H pair.
    # Move one hydrogen by an exact dyadic amount for method-domain evidence.
    coordinates[0, 10, 0] += 0.125
    return _with_fresh_observation(system, coordinates=coordinates)


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


@pytest.mark.parametrize(
    (
        "path",
        "adjust_butane",
        "atom_count",
        "bond_count",
        "angle_count",
        "proper_count",
        "pair_count",
        "excluded_count",
        "selected_count",
    ),
    POSITIVE_CASES,
    ids=("methane", "ethane", "propane", "n_butane_valid_geometry"),
)
def test_c1_c4_bind_fresh_assignment_and_method_without_evaluation(
    path: Path,
    adjust_butane: bool,
    atom_count: int,
    bond_count: int,
    angle_count: int,
    proper_count: int,
    pair_count: int,
    excluded_count: int,
    selected_count: int,
) -> None:
    system = _method_compatible_butane() if adjust_butane else _system(path)
    parameter_set = _parameter_set()
    method = _method()
    report = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        system,
        parameter_set,
        method,
    )
    document = report.to_dict()

    assert document["schema_id"] == (
        LINEAR_ALKANE_EVALUATION_METHOD_BINDING_SCHEMA_ID
    )
    assert document["binding_policy_id"] == (
        LINEAR_ALKANE_EVALUATION_METHOD_BINDING_POLICY_ID
    )
    assert document["claim_scope"] == (
        LINEAR_ALKANE_EVALUATION_METHOD_BINDING_CLAIM_SCOPE
    )
    assert document["assignment_status"] == "contract_fixture_mapped"
    assert document["method_binding_status"] == "contract_fixture_method_bound"
    assert document["geometry_domain_assessment_status"] == (
        "passed_bounded_domain_check_no_evaluation"
    )
    assert document["failed_compatibility_codes"] == []
    assert all(row["passed"] for row in document["compatibility_results"])
    assert document["atom_assignment_count"] == atom_count
    assert document["bond_assignment_count"] == bond_count
    assert document["angle_assignment_count"] == angle_count
    assert document["proper_assignment_count"] == proper_count
    assert document["pair_assignment_count"] == pair_count
    assert document["excluded_pair_count"] == excluded_count
    assert document["mapped_nonexcluded_pair_count"] == selected_count
    assert document["method_covered_nonexcluded_pair_count"] == selected_count
    assert document["parameter_protocol_sha256"] == (
        LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256
    )
    assert document["method_protocol_sha256"] == (
        LINEAR_ALKANE_EVALUATION_METHOD_PROTOCOL_SHA256
    )
    assert document["parameter_set_sha256"] == parameter_set.parameter_set_sha256
    assert document["method_payload_sha256"] == method.method_payload_sha256
    assert document["evaluation_method_sha256"] == method.method_sha256
    fresh_assignment = analyze_linear_alkane_c1_c4_parameter_assignment(
        system,
        parameter_set,
    ).to_dict()
    assert document["assignment_report_sha256"] == fresh_assignment["report_sha256"]
    assert document["parameter_assignment_sha256"] == fresh_assignment[
        "parameter_assignment_sha256"
    ]
    assert document["bounded_nonphysical_evaluation_method_contract_complete"]
    assert document["bounded_contract_fixture_assignment_complete"]
    assert document["bounded_contract_fixture_geometry_domain_assessed"]
    assert document[
        "bounded_contract_fixture_method_assignment_binding_complete"
    ]
    assert all(document[name] is False for name in GLOBAL_FALSE_GATES)
    assert len(document["method_binding_sha256"]) == 64
    assert len(document["report_sha256"]) == 64
    assert report.matches(system, parameter_set, method) is True
    if adjust_butane:
        serialized = (
            serialize_linear_alkane_c1_c4_evaluation_method_binding_report(
                report
            )
        )
        assert len(serialized) == 7291
        assert hashlib.sha256(serialized).hexdigest() == (
            "c1082da0ae06be87e22c510c5f6f5b93cc21acdb1740150474eca81795a3e7e8"
        )
        assert document["method_binding_sha256"] == (
            "e8b709107b59ea6f11b2f1fa90fa288d56be23a884d6dc3a532476bbf0ee1801"
        )
        assert document["report_sha256"] == (
            "11b4886ce33bb3b2cc6cdf35cfb0d30d49156db4c160c0ffa23a07f61edb7c8b"
        )


def test_c1_empty_selected_subset_is_bound_only_with_exact_full_pair_inventory() -> None:
    document = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        _system(METHANE),
        _parameter_set(),
        _method(),
    ).to_dict()
    results = {
        row["code"]: row["passed"] for row in document["compatibility_results"]
    }

    assert document["pair_assignment_count"] == 10
    assert document["pair_class_counts"] == {
        "excluded_1_2": 4,
        "excluded_1_3": 6,
        "one_four_separate": 0,
        "full_nonbonded": 0,
    }
    assert document["mapped_nonexcluded_pair_count"] == 0
    assert document["method_covered_nonexcluded_pair_count"] == 0
    assert results["exact_all_pair_inventory_bound"] is True
    assert results["exact_nonexcluded_pair_subset_covered"] is True


def test_original_butane_geometry_fails_closed_at_exact_angle_singularity() -> None:
    document = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        _system(ALKANES / "n_butane_explicit_h.sdf"),
        _parameter_set(),
        _method(),
    ).to_dict()

    assert document["assignment_status"] == "contract_fixture_mapped"
    assert document["method_binding_status"] == "method_incompatible"
    assert document["geometry_domain_assessment_status"] == (
        "failed_singularity_threshold"
    )
    assert document["failed_compatibility_codes"] == [
        "angle_legs_and_sines_above_method_minimum"
    ]
    assert document["method_binding_sha256"] is None
    assert document["bounded_contract_fixture_geometry_domain_assessed"] is True
    assert document[
        "bounded_contract_fixture_method_assignment_binding_complete"
    ] is False


@pytest.mark.parametrize(
    ("variant", "failed_code"),
    (
        ("float32", "coordinate_dtype_float64"),
        ("two_models", "single_coordinate_model"),
        ("cell", "cell_free_nonperiodic_input"),
        ("requires_grad", "coordinates_require_no_grad"),
    ),
)
def test_valid_assignment_with_incompatible_execution_interface_fails_closed(
    variant: str,
    failed_code: str,
) -> None:
    baseline = _system(METHANE)
    if variant == "float32":
        system = _with_fresh_observation(
            baseline,
            coordinates=baseline.coordinates.to(torch.float32),
        )
    elif variant == "two_models":
        system = _with_fresh_observation(
            baseline,
            coordinates=baseline.coordinates.repeat(2, 1, 1),
        )
    elif variant == "cell":
        system = _with_fresh_observation(
            baseline,
            cell=UnitCell.orthorhombic(
                torch.tensor([20.0, 20.0, 20.0], dtype=torch.float64),
                periodic=(False, False, False),
            ),
        )
    else:
        coordinates = baseline.coordinates.clone().requires_grad_(True)
        system = _with_fresh_observation(baseline, coordinates=coordinates)
    document = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        system,
        _parameter_set(),
        _method(),
    ).to_dict()

    assert document["assignment_status"] == "contract_fixture_mapped"
    assert document["method_binding_status"] == "method_incompatible"
    assert failed_code in document["failed_compatibility_codes"]
    assert document["geometry_domain_assessment_status"] == (
        "not_assessed_upstream_or_interface_incompatible"
    )
    assert document["method_binding_sha256"] is None
    assert document["bounded_contract_fixture_assignment_complete"] is True
    assert document[
        "bounded_contract_fixture_method_assignment_binding_complete"
    ] is False
    assert all(document[name] is False for name in GLOBAL_FALSE_GATES)


@pytest.mark.parametrize("bond_distance", (0.0, 1.0e-8))
def test_bond_distance_at_or_below_threshold_is_rejected_without_partial_results(
    bond_distance: float,
) -> None:
    baseline = _system(METHANE)
    coordinates = baseline.coordinates.clone()
    coordinates[0, 1] = coordinates[0, 0]
    coordinates[0, 1, 0] += bond_distance
    system = _with_fresh_observation(baseline, coordinates=coordinates)
    document = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        system,
        _parameter_set(),
        _method(),
    ).to_dict()

    assert document["assignment_status"] == "contract_fixture_mapped"
    assert document["method_binding_status"] == "method_incompatible"
    assert document["geometry_domain_assessment_status"] == (
        "failed_singularity_threshold"
    )
    assert "bond_distances_above_method_minimum" in document[
        "failed_compatibility_codes"
    ]
    assert "angle_legs_and_sines_above_method_minimum" in document[
        "failed_compatibility_codes"
    ]
    assert document["method_binding_sha256"] is None
    forbidden = {
        "energy_value",
        "force_values",
        "virial_value",
        "per_term_energies",
        "charge_products",
    }
    assert forbidden.isdisjoint(_all_keys(document))


@pytest.mark.parametrize(
    ("kind", "expected_status"),
    (("unsupported", "unsupported_system"), ("invalid", "invalid_system")),
)
def test_unavailable_upstream_assignments_preserve_status_precedence(
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
    document = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        system,
        _parameter_set(),
        _method(),
    ).to_dict()

    assert document["assignment_status"] == expected_status
    assert document["method_binding_status"] == expected_status
    assert document["atom_assignment_count"] == 0
    assert document["bond_assignment_count"] == 0
    assert document["angle_assignment_count"] == 0
    assert document["proper_assignment_count"] == 0
    assert document["pair_assignment_count"] == 0
    assert document["method_covered_nonexcluded_pair_count"] == 0
    assert document["parameter_assignment_sha256"] is None
    assert document["method_binding_sha256"] is None
    assert document["bounded_contract_fixture_assignment_complete"] is False
    assert document[
        "bounded_contract_fixture_method_assignment_binding_complete"
    ] is False
    assert all(document[name] is False for name in GLOBAL_FALSE_GATES)


def test_noncanonical_coordinate_unit_fails_before_report_status() -> None:
    system = replace(_system(METHANE), coordinate_unit="nanometer")
    with pytest.raises(
        MolecularValidationError,
        match="unsupported_coordinate_unit@coordinate_unit",
    ):
        analyze_linear_alkane_c1_c4_evaluation_method_binding(
            system,
            _parameter_set(),
            _method(),
        )


def test_report_serialization_and_hash_dag_are_canonical() -> None:
    system = _system(METHANE)
    parameter_set = _parameter_set()
    method = _method()
    report = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        system,
        parameter_set,
        method,
    )
    document = report.to_dict()
    serialized = serialize_linear_alkane_c1_c4_evaluation_method_binding_report(
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
        json.dumps(
            core,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest() == report_sha256
    assert document["input_execution_envelope_sha256"] == hashlib.sha256(
        report._input_execution_envelope_snapshot
    ).hexdigest()
    assert document["canonical_system_snapshot_sha256"] == hashlib.sha256(
        report._canonical_system_snapshot
    ).hexdigest()
    assert document["canonical_parameter_artifact_sha256"] == hashlib.sha256(
        report._canonical_parameter_snapshot
    ).hexdigest()
    assert document["canonical_method_artifact_sha256"] == hashlib.sha256(
        report._canonical_method_snapshot
    ).hexdigest()
    assert len(serialized) == 7280
    assert hashlib.sha256(serialized).hexdigest() == (
        "f99d813bb21765b6b061158ae4a468527647df6fbab582b8e6c0b024aa94353b"
    )
    assert document["method_binding_sha256"] == (
        "1dfb927580502a370758f267e8817f1604360daf497220c1c173ec219cbb3cd2"
    )
    assert document["report_sha256"] == (
        "ef328e64906606f7ae1e9ef8366f72320c0d5ffb40ed58b1b3990f89dffd9917"
    )


def test_all_four_stored_artifacts_detect_digest_and_canonical_tampering() -> None:
    report = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        _system(METHANE),
        _parameter_set(),
        _method(),
    )
    fields = (
        ("_canonical_system_snapshot", "_canonical_system_snapshot_sha256"),
        (
            "_canonical_parameter_snapshot",
            "_canonical_parameter_snapshot_sha256",
        ),
        ("_canonical_method_snapshot", "_canonical_method_snapshot_sha256"),
        (
            "_input_execution_envelope_snapshot",
            "_input_execution_envelope_snapshot_sha256",
        ),
    )
    for snapshot_name, digest_name in fields:
        original_snapshot = getattr(report, snapshot_name)
        original_digest = getattr(report, digest_name)
        forged_snapshot = original_snapshot + b" "
        object.__setattr__(report, snapshot_name, forged_snapshot)
        with pytest.raises(ValueError, match="digest binding"):
            report.to_dict()
        object.__setattr__(
            report,
            digest_name,
            hashlib.sha256(forged_snapshot).hexdigest(),
        )
        with pytest.raises((ValueError, json.JSONDecodeError)):
            report.to_dict()
        object.__setattr__(report, snapshot_name, original_snapshot)
        object.__setattr__(report, digest_name, original_digest)
    assert report.method_binding_status == "contract_fixture_method_bound"


def test_changed_valid_method_and_parameter_artifacts_change_only_bound_dags() -> None:
    system = _system(METHANE)
    parameter_set = _parameter_set()
    method = _method()
    baseline = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        system,
        parameter_set,
        method,
    ).to_dict()

    changed_method = _method(relative_dielectric=2.0)
    method_changed = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        system,
        parameter_set,
        changed_method,
    ).to_dict()
    assert method_changed["parameter_assignment_sha256"] == baseline[
        "parameter_assignment_sha256"
    ]
    assert method_changed["evaluation_method_sha256"] != baseline[
        "evaluation_method_sha256"
    ]
    assert method_changed["method_binding_sha256"] != baseline[
        "method_binding_sha256"
    ]

    changed_lj = (
        replace(
            parameter_set.lj_type_parameters[0],
            sigma_angstrom=parameter_set.lj_type_parameters[0].sigma_angstrom
            + 0.125,
        ),
        *parameter_set.lj_type_parameters[1:],
    )
    changed_parameter_set = replace(
        parameter_set,
        lj_type_parameters=changed_lj,
    )
    parameter_changed = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        system,
        changed_parameter_set,
        method,
    ).to_dict()
    assert parameter_changed["evaluation_method_sha256"] == baseline[
        "evaluation_method_sha256"
    ]
    assert parameter_changed["parameter_assignment_sha256"] != baseline[
        "parameter_assignment_sha256"
    ]
    assert parameter_changed["method_binding_sha256"] != baseline[
        "method_binding_sha256"
    ]


def test_matches_binds_live_execution_envelope_not_only_cpu_snapshot() -> None:
    system = _system(METHANE)
    parameter_set = _parameter_set()
    method = _method()
    report = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        system,
        parameter_set,
        method,
    )
    requires_grad = replace(
        system,
        coordinates=system.coordinates.clone().requires_grad_(True),
    )

    assert report._canonical_system_snapshot == module.serialize_all_atom_system(
        requires_grad
    )
    assert report.matches(requires_grad, parameter_set, method) is False
    assert report.matches(system, parameter_set, _method(relative_dielectric=2.0)) is (
        False
    )


def test_report_is_slotted_frozen_and_public_aliases_are_nonsemantic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = analyze_linear_alkane_c1_c4_evaluation_method_binding(
        _system(METHANE),
        _parameter_set(),
        _method(),
    )
    baseline = serialize_linear_alkane_c1_c4_evaluation_method_binding_report(
        report
    )
    assert not hasattr(report, "__dict__")
    with pytest.raises(FrozenInstanceError):
        report._canonical_system_snapshot = b"forged"  # type: ignore[misc]
    for name in (
        "LINEAR_ALKANE_EVALUATION_METHOD_BINDING_SCHEMA_ID",
        "LINEAR_ALKANE_EVALUATION_METHOD_BINDING_POLICY_ID",
        "LINEAR_ALKANE_EVALUATION_METHOD_BINDING_CLAIM_SCOPE",
        "LINEAR_ALKANE_EVALUATION_METHOD_BINDING_STATUSES",
    ):
        monkeypatch.setattr(module, name, "forged")
    assert serialize_linear_alkane_c1_c4_evaluation_method_binding_report(
        report
    ) == baseline


def test_factory_and_serializer_require_exact_public_types() -> None:
    with pytest.raises(TypeError):
        analyze_linear_alkane_c1_c4_evaluation_method_binding(
            object(),  # type: ignore[arg-type]
            _parameter_set(),
            _method(),
        )
    with pytest.raises(TypeError):
        serialize_linear_alkane_c1_c4_evaluation_method_binding_report(
            object()  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        LinearAlkaneC1C4EvaluationMethodBindingReport(
            _system(METHANE),
            object(),  # type: ignore[arg-type]
            _method(),
        )


@pytest.mark.parametrize("seed", ("0", "42"))
def test_full_binding_report_is_hashseed_stable(seed: str) -> None:
    script = """
import hashlib
from pathlib import Path
from betelgeuze_engine_v2.molecular import parse_sdf_v2000
from tests.unit.test_engine_v2_linear_alkane_parameters import _parameter_set
from tests.unit.test_engine_v2_linear_alkane_evaluation_method import _method
from betelgeuze_engine_v2.forcefield.linear_alkane_method_binding import (
    analyze_linear_alkane_c1_c4_evaluation_method_binding,
    serialize_linear_alkane_c1_c4_evaluation_method_binding_report,
)
p = Path('tests/fixtures/v2_1_ingest_corpus/methane_explicit_h.sdf')
s = parse_sdf_v2000(p.read_bytes(), source_id=p.stem).system
r = analyze_linear_alkane_c1_c4_evaluation_method_binding(s, _parameter_set(), _method())
print(hashlib.sha256(serialize_linear_alkane_c1_c4_evaluation_method_binding_report(r)).hexdigest())
"""
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == hashlib.sha256(
        serialize_linear_alkane_c1_c4_evaluation_method_binding_report(
            analyze_linear_alkane_c1_c4_evaluation_method_binding(
                _system(METHANE),
                _parameter_set(),
                _method(),
            )
        )
    ).hexdigest()
