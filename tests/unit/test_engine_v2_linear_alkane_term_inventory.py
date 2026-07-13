from __future__ import annotations

from collections import Counter, deque
from dataclasses import FrozenInstanceError, replace
import base64
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_engine_v2.forcefield import term_inventory as inventory_module
from betelgeuze_engine_v2.forcefield.term_inventory import (
    CanonicalPairClassification,
    CanonicalPairIdentity,
    CanonicalProperTorsionIdentity,
    LINEAR_ALKANE_CONSTRAINT_SELECTION_POLICY_ID,
    LINEAR_ALKANE_IMPROPER_SELECTION_POLICY_ID,
    LINEAR_ALKANE_PAIR_CLASSIFICATION_POLICY_ID,
    LINEAR_ALKANE_TERM_PAIR_INVENTORY_SCHEMA_ID,
    LINEAR_ALKANE_TERM_PAIR_INVENTORY_SCHEMA_VERSION,
    LinearAlkaneTermPairInventoryReport,
    analyze_linear_alkane_term_pair_inventory,
)
from betelgeuze_engine_v2.molecular.bonded_inventory import (
    CanonicalAngleIdentity,
    CanonicalBondIdentity,
)
from betelgeuze_engine_v2.molecular.models import AllAtomSystem
from betelgeuze_engine_v2.molecular.sdf_v2000 import parse_sdf_v2000


REPO_ROOT = Path(__file__).resolve().parents[2]


def _atom_line(index: int, element: str, *, coordinate_offset: float) -> str:
    x = float(index) * 1.137 + coordinate_offset
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
    reverse_bond_rows: bool = False,
) -> bytes:
    if carbon_count < 1 or carbon_count > 4:
        raise ValueError("test helper supports C1-C4 only")
    elements = ["C"] * carbon_count
    bonds = [(index, index + 1) for index in range(carbon_count - 1)]
    for carbon_index in range(carbon_count):
        hydrogen_count = (
            4
            if carbon_count == 1
            else 3
            if carbon_index in {0, carbon_count - 1}
            else 2
        )
        for _ in range(hydrogen_count):
            hydrogen_index = len(elements)
            elements.append("H")
            bonds.append((carbon_index, hydrogen_index))

    atom_count = len(elements)
    permutation = (
        tuple(range(atom_count))
        if new_index_for_old_index is None
        else new_index_for_old_index
    )
    if tuple(sorted(permutation)) != tuple(range(atom_count)):
        raise ValueError("new_index_for_old_index must be a permutation")
    reordered_elements = [""] * atom_count
    for old_index, new_index in enumerate(permutation):
        reordered_elements[new_index] = elements[old_index]
    reordered_bonds = [
        (permutation[atom_i], permutation[atom_j])
        for atom_i, atom_j in bonds
    ]
    if reverse_bond_rows:
        reordered_bonds.reverse()
    lines = [
        f"linear-alkane-c{carbon_count}",
        "betelgeuze-v2-term-inventory-test",
        "source-bound-contract-only",
        f"{atom_count:3d}{len(reordered_bonds):3d}  0  0  0  0  0  0  0  0999 V2000",
        *(
            _atom_line(
                index,
                element,
                coordinate_offset=coordinate_offset,
            )
            for index, element in enumerate(reordered_elements)
        ),
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
    reverse_bond_rows: bool = False,
) -> AllAtomSystem:
    return parse_sdf_v2000(
        _linear_alkane_source(
            carbon_count,
            new_index_for_old_index=new_index_for_old_index,
            coordinate_offset=coordinate_offset,
            reverse_bond_rows=reverse_bond_rows,
        ),
        source_id=f"term-inventory-c{carbon_count}",
    ).system


EXPECTED_COUNTS = {
    1: {
        "atoms": 5,
        "bonds": 4,
        "angles": 6,
        "propers": 0,
        "excluded_1_2": 4,
        "excluded_1_3": 6,
        "one_four_separate": 0,
        "full_nonbonded": 0,
    },
    2: {
        "atoms": 8,
        "bonds": 7,
        "angles": 12,
        "propers": 9,
        "excluded_1_2": 7,
        "excluded_1_3": 12,
        "one_four_separate": 9,
        "full_nonbonded": 0,
    },
    3: {
        "atoms": 11,
        "bonds": 10,
        "angles": 18,
        "propers": 18,
        "excluded_1_2": 10,
        "excluded_1_3": 18,
        "one_four_separate": 18,
        "full_nonbonded": 9,
    },
    4: {
        "atoms": 14,
        "bonds": 13,
        "angles": 24,
        "propers": 27,
        "excluded_1_2": 13,
        "excluded_1_3": 24,
        "one_four_separate": 27,
        "full_nonbonded": 27,
    },
}


@pytest.mark.parametrize("carbon_count", (1, 2, 3, 4))
def test_exact_c1_c4_term_and_pair_counts_without_physics_promotion(
    carbon_count: int,
) -> None:
    system = _system(carbon_count)
    report = analyze_linear_alkane_term_pair_inventory(system)
    payload = report.to_dict()
    expected = EXPECTED_COUNTS[carbon_count]

    assert payload["schema_id"] == LINEAR_ALKANE_TERM_PAIR_INVENTORY_SCHEMA_ID
    assert payload["schema_version"] == (
        LINEAR_ALKANE_TERM_PAIR_INVENTORY_SCHEMA_VERSION
    )
    assert payload["inventory_status"] == "available"
    assert payload["atom_count"] == expected["atoms"] == system.atom_count
    assert len(payload["bond_terms"]) == expected["bonds"]
    assert len(payload["angle_terms"]) == expected["angles"]
    assert len(payload["proper_terms"]) == expected["propers"]
    assert payload["pair_class_counts"] == {
        key: expected[key]
        for key in (
            "excluded_1_2",
            "excluded_1_3",
            "one_four_separate",
            "full_nonbonded",
        )
    }
    assert len(payload["pair_classifications"]) == (
        system.atom_count * (system.atom_count - 1) // 2
    )
    assert sum(payload["pair_class_counts"].values()) == len(
        payload["pair_classifications"]
    )
    assert payload["improper_selection_policy_id"] == (
        LINEAR_ALKANE_IMPROPER_SELECTION_POLICY_ID
    )
    assert payload["improper_identity_status"] == "enumerated_empty_by_policy"
    assert payload["improper_identities"] == []
    assert payload["constraint_selection_policy_id"] == (
        LINEAR_ALKANE_CONSTRAINT_SELECTION_POLICY_ID
    )
    assert payload["constraint_identity_status"] == "enumerated_empty_by_policy"
    assert payload["constraint_identities"] == []
    assert payload["pair_classification_policy_id"] == (
        LINEAR_ALKANE_PAIR_CLASSIFICATION_POLICY_ID
    )
    assert payload["one_four_lj_scale"] is None
    assert payload["one_four_coulomb_scale"] is None
    assert payload["topological_term_and_pair_classification_complete"] is True
    assert payload["preparation_ready"] is False
    assert payload["parameter_assignment_complete"] is False
    assert payload["parameterability_assessed"] is False
    assert payload["global_parameter_coverage_complete"] is False
    assert payload["force_field_atom_typing_complete"] is False
    assert payload["partial_charge_assignment_complete"] is False
    assert payload["physics_supported"] is False
    assert payload["scientific_validity_green"] is False
    assert payload["energy_evaluation_authorized"] is False
    assert payload["force_evaluation_authorized"] is False
    assert payload["virial_evaluation_authorized"] is False
    assert payload["minimization_authorized"] is False
    assert payload["runtime_eligible"] is False
    assert payload["execution_authorized"] is False
    assert payload["simulation_ready"] is False
    assert payload["claim_safe"] is False
    assert all(
        term["parameter_id"] is None
        for group in ("bond_terms", "angle_terms", "proper_terms")
        for term in payload[group]
    )
    assert all(
        pair["lj_scale"] is None and pair["coulomb_scale"] is None
        for pair in payload["pair_classifications"]
    )
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload


def _adjacency(system: AllAtomSystem) -> tuple[tuple[int, ...], ...]:
    neighbors = [set() for _ in system.atoms]
    for bond in system.bonds:
        neighbors[bond.atom_i].add(bond.atom_j)
        neighbors[bond.atom_j].add(bond.atom_i)
    return tuple(tuple(sorted(row)) for row in neighbors)


def _distance(
    adjacency: tuple[tuple[int, ...], ...],
    atom_i: int,
    atom_j: int,
) -> int | None:
    queue: deque[tuple[int, int]] = deque([(atom_i, 0)])
    visited = {atom_i}
    while queue:
        atom, distance = queue.popleft()
        if atom == atom_j:
            return distance
        for neighbor in adjacency[atom]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, distance + 1))
    return None


def test_n_butane_exact_identity_sets_and_shortest_path_policy() -> None:
    system = _system(4)
    adjacency = _adjacency(system)
    report = analyze_linear_alkane_term_pair_inventory(system)

    expected_bonds = {
        CanonicalBondIdentity(
            min(bond.atom_i, bond.atom_j),
            max(bond.atom_i, bond.atom_j),
        )
        for bond in system.bonds
    }
    expected_angles = {
        CanonicalAngleIdentity(outer_i, center, outer_k)
        for center, neighbors in enumerate(adjacency)
        for position, outer_i in enumerate(neighbors)
        for outer_k in neighbors[position + 1 :]
    }
    expected_propers = {
        CanonicalProperTorsionIdentity.from_path(
            atom_i,
            atom_j,
            atom_k,
            atom_l,
        )
        for atom_j, neighbors_j in enumerate(adjacency)
        for atom_k in neighbors_j
        if atom_j < atom_k
        for atom_i in neighbors_j
        if atom_i != atom_k
        for atom_l in adjacency[atom_k]
        if atom_l not in {atom_i, atom_j}
    }

    assert set(report.bond_identities) == expected_bonds
    assert set(report.angle_identities) == expected_angles
    assert set(report.proper_identities) == expected_propers
    assert len(report.improper_identities) == 0
    assert len(report.constraint_identities) == 0
    for pair in report.pair_classifications:
        expected_distance = _distance(
            adjacency,
            pair.identity.atom_i,
            pair.identity.atom_j,
        )
        expected_class = {
            1: "excluded_1_2",
            2: "excluded_1_3",
            3: "one_four_separate",
        }.get(expected_distance, "full_nonbonded")
        assert pair.shortest_graph_distance == expected_distance
        assert pair.interaction_class == expected_class


def test_proper_and_pair_identity_canonicalization_is_strict() -> None:
    assert CanonicalProperTorsionIdentity.from_path(3, 2, 1, 0) == (
        CanonicalProperTorsionIdentity(0, 1, 2, 3)
    )
    assert CanonicalProperTorsionIdentity.from_path(0, 2, 1, 3) == (
        CanonicalProperTorsionIdentity(0, 2, 1, 3)
    )
    with pytest.raises(ValueError, match="normalized"):
        CanonicalProperTorsionIdentity(3, 2, 1, 0)
    with pytest.raises(ValueError, match="four atoms"):
        CanonicalProperTorsionIdentity.from_path(0, 1, 1, 2)
    with pytest.raises(ValueError, match="atom_i < atom_j"):
        CanonicalPairIdentity(2, 1)

    class _StringSubclass(str):
        pass

    with pytest.raises(TypeError, match="exact string"):
        CanonicalPairClassification(
            identity=CanonicalPairIdentity(0, 1),
            shortest_graph_distance=1,
            interaction_class=_StringSubclass("excluded_1_2"),
        )


def _mapped_bond(
    identity: CanonicalBondIdentity,
    new_index_for_old: tuple[int, ...],
) -> CanonicalBondIdentity:
    atom_i, atom_j = sorted(
        (
            new_index_for_old[identity.atom_i],
            new_index_for_old[identity.atom_j],
        )
    )
    return CanonicalBondIdentity(atom_i, atom_j)


def _mapped_angle(
    identity: CanonicalAngleIdentity,
    new_index_for_old: tuple[int, ...],
) -> CanonicalAngleIdentity:
    outer_i, outer_k = sorted(
        (
            new_index_for_old[identity.outer_atom_i],
            new_index_for_old[identity.outer_atom_k],
        )
    )
    return CanonicalAngleIdentity(
        outer_i,
        new_index_for_old[identity.center_atom],
        outer_k,
    )


def _mapped_proper(
    identity: CanonicalProperTorsionIdentity,
    new_index_for_old: tuple[int, ...],
) -> CanonicalProperTorsionIdentity:
    return CanonicalProperTorsionIdentity.from_path(
        new_index_for_old[identity.atom_i],
        new_index_for_old[identity.atom_j],
        new_index_for_old[identity.atom_k],
        new_index_for_old[identity.atom_l],
    )


def test_reindex_permutation_is_equivariant_and_match_keys_are_invariant() -> None:
    baseline = analyze_linear_alkane_term_pair_inventory(_system(4))
    atom_count = EXPECTED_COUNTS[4]["atoms"]
    permutation = tuple(reversed(range(atom_count)))
    permuted = analyze_linear_alkane_term_pair_inventory(
        _system(4, new_index_for_old_index=permutation, coordinate_offset=9.0)
    )

    assert {_mapped_bond(item, permutation) for item in baseline.bond_identities} == (
        set(permuted.bond_identities)
    )
    assert {_mapped_angle(item, permutation) for item in baseline.angle_identities} == (
        set(permuted.angle_identities)
    )
    assert {
        _mapped_proper(item, permutation) for item in baseline.proper_identities
    } == set(permuted.proper_identities)
    assert Counter(term.match_key for term in baseline.bond_terms) == Counter(
        term.match_key for term in permuted.bond_terms
    )
    assert Counter(term.match_key for term in baseline.angle_terms) == Counter(
        term.match_key for term in permuted.angle_terms
    )
    assert Counter(term.match_key for term in baseline.proper_terms) == Counter(
        term.match_key for term in permuted.proper_terms
    )
    mapped_pair_classes = {
        (
            CanonicalPairIdentity(
                *sorted(
                    (
                        permutation[pair.identity.atom_i],
                        permutation[pair.identity.atom_j],
                    )
                )
            ),
            pair.shortest_graph_distance,
            pair.interaction_class,
        )
        for pair in baseline.pair_classifications
    }
    assert mapped_pair_classes == {
        (
            pair.identity,
            pair.shortest_graph_distance,
            pair.interaction_class,
        )
        for pair in permuted.pair_classifications
    }
    assert baseline.report_sha256 != permuted.report_sha256


def test_source_bond_row_order_and_coordinates_do_not_change_topology_semantics() -> None:
    baseline = analyze_linear_alkane_term_pair_inventory(_system(4))
    changed_source = analyze_linear_alkane_term_pair_inventory(
        _system(4, coordinate_offset=17.0, reverse_bond_rows=True)
    )

    assert baseline.bond_terms == changed_source.bond_terms
    assert baseline.angle_terms == changed_source.angle_terms
    assert baseline.proper_terms == changed_source.proper_terms
    assert baseline.pair_classifications == changed_source.pair_classifications
    assert baseline.report_sha256 != changed_source.report_sha256


def test_upstream_fail_closed_state_exposes_no_term_or_pair_claim() -> None:
    system = _system(2)
    changed_atoms = (
        replace(system.atoms[0], partial_charge_e=0.125),
        *system.atoms[1:],
    )
    unsupported = replace(system, atoms=changed_atoms)
    report = analyze_linear_alkane_term_pair_inventory(unsupported)
    payload = report.to_dict()

    assert report.inventory_status == "unsupported"
    assert report.bond_terms == ()
    assert report.angle_terms == ()
    assert report.proper_terms == ()
    assert report.pair_classifications == ()
    assert payload["atom_count"] is None
    assert payload["topological_term_and_pair_classification_complete"] is False
    assert "bounded_linear_alkane_applicability_or_typing_unavailable" in (
        payload["blockers"]
    )


def test_report_is_slotted_snapshot_bound_and_different_systems_are_unequal() -> None:
    methane = analyze_linear_alkane_term_pair_inventory(_system(1))
    ethane = analyze_linear_alkane_term_pair_inventory(_system(2))
    assert isinstance(methane, LinearAlkaneTermPairInventoryReport)
    assert not hasattr(methane, "__dict__")
    assert methane != ethane
    assert hash(methane) != hash(ethane)
    assert methane.matches_system(_system(1)) is True
    assert methane.matches_system(_system(2)) is False
    with pytest.raises(FrozenInstanceError):
        methane._canonical_system_snapshot = b"forged"  # type: ignore[misc]

    object.__setattr__(
        ethane,
        "_canonical_system_snapshot",
        methane._canonical_system_snapshot,
    )
    with pytest.raises(ValueError, match="digest binding"):
        ethane.to_dict()

    object.__setattr__(methane, "_canonical_system_snapshot", b"{}")
    with pytest.raises(ValueError, match="digest binding"):
        methane.to_dict()

    fresh = analyze_linear_alkane_term_pair_inventory(_system(1))
    object.__setattr__(
        fresh,
        "_canonical_system_snapshot",
        bytearray(fresh._canonical_system_snapshot),
    )
    with pytest.raises(TypeError, match="canonical bytes"):
        fresh.matches_system(_system(1))


def test_internal_validation_requires_exact_fresh_enumeration() -> None:
    report = analyze_linear_alkane_term_pair_inventory(_system(1))
    analysis = inventory_module._compute(report._canonical_system_snapshot)
    forged = replace(
        analysis,
        pair_classifications=(
            analysis.pair_classifications[0],
        )
        * len(analysis.pair_classifications),
    )
    with pytest.raises(ValueError, match="exactly equal"):
        report._validate(forged)

    other = analyze_linear_alkane_term_pair_inventory(_system(2))
    cross_system = inventory_module._compute(other._canonical_system_snapshot)
    with pytest.raises(ValueError, match="report's exact"):
        report._validate(cross_system)


def test_cross_system_dependency_report_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrong_typing_report = (
        inventory_module.analyze_linear_alkane_topological_environment_typing(
            _system(2)
        )
    )
    monkeypatch.setattr(
        inventory_module,
        "analyze_linear_alkane_topological_environment_typing",
        lambda _system: wrong_typing_report,
    )
    with pytest.raises(ValueError, match="exact system snapshot"):
        analyze_linear_alkane_term_pair_inventory(_system(1))


def test_public_label_mutation_cannot_redefine_frozen_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = analyze_linear_alkane_term_pair_inventory(_system(3))
    baseline = report.to_dict()
    for name in (
        "LINEAR_ALKANE_TERM_PAIR_INVENTORY_SCHEMA_VERSION",
        "LINEAR_ALKANE_TERM_PAIR_INVENTORY_SCHEMA_ID",
        "LINEAR_ALKANE_TERM_PAIR_INVENTORY_PROFILE_ID",
        "LINEAR_ALKANE_TERM_PAIR_INVENTORY_CLAIM_SCOPE",
        "LINEAR_ALKANE_ENVIRONMENT_MATCH_POLICY_ID",
        "LINEAR_ALKANE_PAIR_CLASSIFICATION_POLICY_ID",
        "LINEAR_ALKANE_IMPROPER_SELECTION_POLICY_ID",
        "LINEAR_ALKANE_CONSTRAINT_SELECTION_POLICY_ID",
    ):
        monkeypatch.setattr(inventory_module, name, "forged")
    monkeypatch.setattr(
        inventory_module,
        "LINEAR_ALKANE_PAIR_INTERACTION_CLASSES",
        ("forged",),
    )
    assert report.to_dict() == baseline


def test_report_hash_is_stable_across_python_hash_seeds() -> None:
    encoded_source = base64.b64encode(_linear_alkane_source(4)).decode("ascii")
    script = f"""
import base64
from betelgeuze_engine_v2.forcefield.term_inventory import analyze_linear_alkane_term_pair_inventory
from betelgeuze_engine_v2.molecular.sdf_v2000 import parse_sdf_v2000
source = base64.b64decode({encoded_source!r})
system = parse_sdf_v2000(source, source_id="hashseed-c4").system
print(analyze_linear_alkane_term_pair_inventory(system).report_sha256)
"""
    hashes = []
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
        hashes.append(result.stdout.strip())
    assert len(set(hashes)) == 1
    assert len(hashes[0]) == 64
