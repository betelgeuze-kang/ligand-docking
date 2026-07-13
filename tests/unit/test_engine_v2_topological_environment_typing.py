from __future__ import annotations

from collections import Counter
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import torch

from betelgeuze_engine_v2.forcefield import typing as typing_module
from betelgeuze_engine_v2.forcefield.typing import (
    LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_ASSIGNMENT_POLICY_ID,
    LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_CLAIM_SCOPE,
    LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_ID,
    LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_VERSION,
    LinearAlkaneTopologicalEnvironmentTypingReport,
    TopologicalEnvironmentTypingContractError,
    analyze_linear_alkane_topological_environment_typing,
)
from betelgeuze_engine_v2.molecular.models import AllAtomSystem
from betelgeuze_engine_v2.molecular.sdf_v2000 import parse_sdf_v2000


REPO_ROOT = Path(__file__).resolve().parents[2]


def _atom_line(index: int, element: str) -> str:
    x = float(index) * 1.137
    y = float((index % 3) - 1) * 0.719
    z = float((index % 5) - 2) * 0.413
    return (
        f"{x:10.4f}{y:10.4f}{z:10.4f} {element:<3}"
        f"{0:2d}{0:3d}{0:3d}{0:3d}{0:3d}{0:3d}"
        f"{0:3d}{0:3d}{0:3d}{0:3d}{0:3d}{0:3d}"
    )


def _bond_line(atom_i: int, atom_j: int) -> str:
    return f"{atom_i + 1:3d}{atom_j + 1:3d}{1:3d}{0:3d}"


def _linear_alkane_source(
    carbon_count: int,
    *,
    new_index_for_old_index: tuple[int, ...] | None = None,
    coordinate_offset: float = 0.0,
) -> bytes:
    if carbon_count < 1 or carbon_count > 4:
        raise ValueError("test helper supports C1-C4 only")
    elements = ["C"] * carbon_count
    bonds = [(index, index + 1) for index in range(carbon_count - 1)]
    for carbon_index in range(carbon_count):
        hydrogen_count = 4 if carbon_count == 1 else 3 if carbon_index in {
            0,
            carbon_count - 1,
        } else 2
        for _ in range(hydrogen_count):
            hydrogen_index = len(elements)
            elements.append("H")
            bonds.append((carbon_index, hydrogen_index))

    atom_count = len(elements)
    if new_index_for_old_index is None:
        new_index_for_old_index = tuple(range(atom_count))
    if tuple(sorted(new_index_for_old_index)) != tuple(range(atom_count)):
        raise ValueError("new_index_for_old_index must be a permutation")
    reordered_elements = [""] * atom_count
    for old_index, new_index in enumerate(new_index_for_old_index):
        reordered_elements[new_index] = elements[old_index]
    reordered_bonds = tuple(
        (
            new_index_for_old_index[atom_i],
            new_index_for_old_index[atom_j],
        )
        for atom_i, atom_j in bonds
    )
    atom_lines = []
    for index, element in enumerate(reordered_elements):
        line = _atom_line(index, element)
        if coordinate_offset:
            x = float(index) * 1.137 + coordinate_offset
            line = f"{x:10.4f}{line[10:]}"
        atom_lines.append(line)
    lines = [
        f"linear-alkane-c{carbon_count}",
        "betelgeuze-v2-topological-environment-test",
        "source-bound-contract-only",
        f"{atom_count:3d}{len(reordered_bonds):3d}  0  0  0  0  0  0  0  0999 V2000",
        *atom_lines,
        *(_bond_line(atom_i, atom_j) for atom_i, atom_j in reordered_bonds),
        "M  END",
        "$$$$",
    ]
    return ("\n".join(lines) + "\n").encode("ascii")


def _system(
    carbon_count: int,
    *,
    new_index_for_old_index: tuple[int, ...] | None = None,
    coordinate_offset: float = 0.0,
) -> AllAtomSystem:
    return parse_sdf_v2000(
        _linear_alkane_source(
            carbon_count,
            new_index_for_old_index=new_index_for_old_index,
            coordinate_offset=coordinate_offset,
        ),
        source_id=f"typing-c{carbon_count}",
    ).system


EXPECTED_ENVIRONMENTS = {
    1: Counter(
        {
            "c_single_valence4_c0_h4": 1,
            "h_attached_c_single_valence4_c0_h4": 4,
        }
    ),
    2: Counter(
        {
            "c_single_valence4_c1_h3": 2,
            "h_attached_c_single_valence4_c1_h3": 6,
        }
    ),
    3: Counter(
        {
            "c_single_valence4_c1_h3": 2,
            "c_single_valence4_c2_h2": 1,
            "h_attached_c_single_valence4_c1_h3": 6,
            "h_attached_c_single_valence4_c2_h2": 2,
        }
    ),
    4: Counter(
        {
            "c_single_valence4_c1_h3": 2,
            "c_single_valence4_c2_h2": 2,
            "h_attached_c_single_valence4_c1_h3": 6,
            "h_attached_c_single_valence4_c2_h2": 4,
        }
    ),
}


@pytest.mark.parametrize("carbon_count", (1, 2, 3, 4))
def test_exact_c1_c4_topological_environments_only(carbon_count: int) -> None:
    system = _system(carbon_count)
    report = analyze_linear_alkane_topological_environment_typing(system)
    payload = report.to_dict()

    observed = Counter(
        assignment.topological_environment_id
        for assignment in report.environment_assignments
    )
    assert observed == EXPECTED_ENVIRONMENTS[carbon_count]
    assert len(report.environment_assignments) == system.atom_count
    assert tuple(
        assignment.atom_index for assignment in report.environment_assignments
    ) == tuple(range(system.atom_count))
    assert report.typing_status == "environments_available"
    assert report.topological_environment_coverage_complete is True
    assert report.topological_environment_coverage_status == (
        "complete_for_bounded_c1_c4_linear_alkane_profile"
    )
    assert report.force_field_atom_typing_status == (
        "not_assigned_topological_environment_only"
    )
    assert report.partial_charge_assignment_status == "not_assigned"
    assert report.formal_charge_observation_status == (
        "source_observed_known_zero_not_partial_charge_assignment"
    )
    assert report.source_partial_charge_count == 0
    assert report.source_partial_charge_status == (
        "absent_required_by_applicability_profile"
    )
    assert all(
        assignment.formal_charge_known is True
        and assignment.observed_formal_charge == 0
        and assignment.force_field_type_id is None
        and assignment.assigned_partial_charge_e is None
        for assignment in report.environment_assignments
    )
    assert payload["schema_id"] == (
        LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_ID
    )
    assert payload["schema_version"] == (
        LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_VERSION
    ) == "1.0.0"
    assert payload["assignment_policy_id"] == (
        LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_ASSIGNMENT_POLICY_ID
    )
    assert payload["claim_scope"] == (
        LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_CLAIM_SCOPE
    )
    assert len(payload["canonical_system_snapshot_sha256"]) == 64
    assert len(payload["applicability_report_sha256"]) == 64
    assert len(payload["report_sha256"]) == 64
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload


def _semantic_environment_rows(
    report: LinearAlkaneTopologicalEnvironmentTypingReport,
) -> Counter[tuple[object, ...]]:
    return _semantic_assignment_rows(report.environment_assignments)


def _semantic_assignment_rows(
    assignments: tuple[typing_module.LinearAlkaneTopologicalEnvironmentAssignment, ...],
) -> Counter[tuple[object, ...]]:
    return Counter(
        (
            assignment.element,
            assignment.local_carbon_neighbor_count,
            assignment.local_hydrogen_neighbor_count,
            assignment.environment_center_carbon_neighbor_count,
            assignment.environment_center_hydrogen_neighbor_count,
            assignment.topological_environment_id,
        )
        for assignment in assignments
    )


def test_environment_keys_are_graph_only_while_report_preserves_source_binding() -> None:
    baseline_system = _system(4)
    baseline = analyze_linear_alkane_topological_environment_typing(
        baseline_system
    )
    coordinate_only = replace(
        baseline_system,
        coordinates=baseline_system.coordinates
        + torch.tensor([[[7.25, -3.5, 1.0]]], dtype=torch.float64),
    )
    coordinate_report = analyze_linear_alkane_topological_environment_typing(
        coordinate_only
    )
    relabeled = replace(
        baseline_system,
        atoms=tuple(
            replace(atom, name=f"IGNORED_{atom.index}")
            for atom in baseline_system.atoms
        ),
        residues=(replace(baseline_system.residues[0], name="ALT"),),
    )
    relabeled_assignments = typing_module._derive_environment_assignments(
        relabeled
    )
    relabeled_report = analyze_linear_alkane_topological_environment_typing(
        relabeled
    )
    atom_count = baseline_system.atom_count
    permutation = tuple(reversed(range(atom_count)))
    permuted_report = analyze_linear_alkane_topological_environment_typing(
        _system(4, new_index_for_old_index=permutation, coordinate_offset=9.0)
    )

    assert coordinate_report.typing_status == "environments_available"
    assert permuted_report.typing_status == "environments_available"
    assert _semantic_environment_rows(coordinate_report) == (
        _semantic_environment_rows(baseline)
    )
    assert _semantic_assignment_rows(relabeled_assignments) == (
        _semantic_environment_rows(baseline)
    )
    assert _semantic_environment_rows(permuted_report) == (
        _semantic_environment_rows(baseline)
    )
    # Relabeling parser-synthesized names/residue state invalidates its source
    # pedigree.  The graph-only helper still yields identical keys, while the
    # public source-bound report correctly fails closed.
    assert relabeled_report.typing_status == "invalid_system"
    assert relabeled_report.environment_assignments == ()
    assert coordinate_report.canonical_system_snapshot_sha256 != (
        baseline.canonical_system_snapshot_sha256
    )
    assert permuted_report.canonical_system_snapshot_sha256 != (
        baseline.canonical_system_snapshot_sha256
    )


def test_source_partial_charge_is_never_treated_as_force_field_charge() -> None:
    system = _system(2)
    charged_atom = replace(system.atoms[0], partial_charge_e=0.125)
    source_partial_charge = replace(
        system,
        atoms=(charged_atom, *system.atoms[1:]),
    )
    report = analyze_linear_alkane_topological_environment_typing(
        source_partial_charge
    )

    assert report.applicability_report.applicable is False
    assert report.typing_status == "unsupported_system"
    assert report.environment_assignments == ()
    assert report.source_partial_charge_count == 1
    assert report.source_partial_charge_status == (
        "present_not_used_and_profile_rejected"
    )
    assert report.formal_charge_observation_status == "not_available_for_typing"
    assert report.partial_charge_assignment_status == "not_assigned"
    assert report.partial_charges_assigned is False
    assert report.charge_model_id is None


def test_source_binding_tamper_fails_closed_without_environment_rows() -> None:
    system = _system(3)
    forged = replace(
        system,
        provenance=replace(system.provenance, source_sha256="0" * 64),
    )
    report = analyze_linear_alkane_topological_environment_typing(forged)

    assert report.typing_status == "invalid_system"
    assert report.topological_environment_coverage_complete is False
    assert report.environment_assignments == ()
    assert report.blockers[0] == "linear_alkane_typing_system_invalid"


def test_report_snapshot_is_read_only_replayed_and_bound_to_input() -> None:
    system = _system(3)
    report = LinearAlkaneTopologicalEnvironmentTypingReport(system)
    restored = report.system
    baseline_payload = report.to_dict()

    restored.coordinates.add_(100.0)

    assert report.to_dict() == baseline_payload
    assert report.matches_system(system) is True
    assert report.matches_system(_system(2)) is False
    assert report.canonical_system_snapshot_bytes.startswith(b"{")
    assert report.report_sha256 == report.to_dict()["report_sha256"]


def test_rows_and_report_are_slotted_strict_and_all_authority_is_false() -> None:
    report = analyze_linear_alkane_topological_environment_typing(_system(1))
    assignment = report.environment_assignments[0]

    assert not hasattr(report, "__dict__")
    assert not hasattr(assignment, "__dict__")
    with pytest.raises(TypeError):
        replace(report)
    with pytest.raises(ValueError, match="cannot carry a force-field type"):
        replace(assignment, force_field_type_id="production-c")
    with pytest.raises(ValueError, match="cannot carry a partial charge"):
        replace(assignment, assigned_partial_charge_e=0.0)
    with pytest.raises(ValueError, match="frozen graph policy"):
        replace(assignment, topological_environment_id="c")

    assert report.force_field_atom_types_assigned is False
    assert report.partial_charges_assigned is False
    assert report.parameter_set_id is None
    assert report.parameter_assignment_sha256 is None
    assert report.parameterability_assessed is False
    assert report.parameterizable is False
    assert report.physics_supported is False
    assert report.scientifically_validated is False
    assert report.energy_evaluation_authorized is False
    assert report.force_evaluation_authorized is False
    assert report.virial_evaluation_authorized is False
    assert report.minimization_authorized is False
    assert report.runtime_ready is False
    assert report.simulation_ready is False
    assert report.authority_granted is False
    assert report.claim_safe is False


def test_private_snapshot_and_upstream_digest_tamper_are_detected() -> None:
    snapshot_tamper = analyze_linear_alkane_topological_environment_typing(
        _system(2)
    )
    object.__setattr__(
        snapshot_tamper,
        "_canonical_system_snapshot_bytes",
        b"{}",
    )
    with pytest.raises(
        TopologicalEnvironmentTypingContractError,
        match="snapshot binding is invalid",
    ):
        snapshot_tamper.to_dict()

    digest_tamper = analyze_linear_alkane_topological_environment_typing(
        _system(2)
    )
    object.__setattr__(
        digest_tamper,
        "_applicability_report_sha256",
        "0" * 64,
    )
    with pytest.raises(
        TopologicalEnvironmentTypingContractError,
        match="applicability report binding is inconsistent",
    ):
        digest_tamper.to_dict()


def test_public_labels_cannot_redefine_frozen_report_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = analyze_linear_alkane_topological_environment_typing(_system(2))
    baseline = report.to_dict()

    monkeypatch.setattr(
        typing_module,
        "LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_ID",
        "forged",
    )
    monkeypatch.setattr(
        typing_module,
        "LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_ASSIGNMENT_POLICY_ID",
        "forged",
    )

    assert report.to_dict() == baseline


def test_report_digest_is_hashseed_independent() -> None:
    code = """
from tests.unit.test_engine_v2_topological_environment_typing import _system
from betelgeuze_engine_v2.forcefield.typing import analyze_linear_alkane_topological_environment_typing
print(analyze_linear_alkane_topological_environment_typing(_system(4)).report_sha256)
"""
    hashes = []
    for seed in ("1", "4294967295"):
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = seed
        environment["PYTHONPATH"] = str(REPO_ROOT)
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        hashes.append(completed.stdout.strip())
    assert hashes[0] == hashes[1]
