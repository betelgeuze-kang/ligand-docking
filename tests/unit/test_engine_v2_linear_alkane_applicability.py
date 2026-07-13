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

from betelgeuze_engine_v2.molecular import alkane_forcefield_applicability as module
from betelgeuze_engine_v2.molecular.alkane_forcefield_applicability import (
    LINEAR_ALKANE_C1_C4_CARBON_CHAIN_ORIENTATION_POLICY_ID,
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_CLAIM_SCOPE,
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_CONSTRAINT_CODES,
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_PROFILE_ID,
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_ID,
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_VERSION,
    LinearAlkaneC1C4ForceFieldApplicabilityReport,
    analyze_linear_alkane_c1_c4_force_field_applicability,
)
from betelgeuze_engine_v2.molecular.observation import (
    attach_parser_observation_digest,
)
from betelgeuze_engine_v2.molecular.sdf_v2000 import parse_sdf_v2000
from betelgeuze_engine_v2.molecular.serialization import (
    MolecularSerializationError,
    deserialize_all_atom_system,
    serialize_all_atom_system,
)
from betelgeuze_engine_v2.molecular.topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    canonical_topology_sha256,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures"
ALKANES = FIXTURES / "v2_2_linear_alkane"
METHANE = FIXTURES / "v2_1_ingest_corpus" / "methane_explicit_h.sdf"


def _system(path: Path, *, source_id: str | None = None):
    return parse_sdf_v2000(
        path.read_bytes(),
        source_id=path.stem if source_id is None else source_id,
    ).system


def _refresh_unkeyed_parser_bindings(system):
    metadata = dict(system.provenance.metadata)
    metadata["canonical_topology_schema_id"] = CANONICAL_TOPOLOGY_SCHEMA_ID
    metadata["canonical_topology_sha256"] = canonical_topology_sha256(system)
    rebound = replace(
        system,
        provenance=replace(system.provenance, metadata=metadata),
    )
    return attach_parser_observation_digest(rebound)


def _permuted_sdf_source(path: Path, permutation: tuple[int, ...]) -> bytes:
    lines = path.read_text(encoding="ascii").splitlines()
    atom_count = int(lines[3][:3])
    bond_count = int(lines[3][3:6])
    assert tuple(sorted(permutation)) == tuple(range(atom_count))
    old_to_new = {old: new for new, old in enumerate(permutation)}
    atom_lines = [lines[4 + old] for old in permutation]
    remapped_bonds = []
    for line in reversed(lines[4 + atom_count : 4 + atom_count + bond_count]):
        old_i = int(line[:3]) - 1
        old_j = int(line[3:6]) - 1
        new_i = old_to_new[old_i] + 1
        new_j = old_to_new[old_j] + 1
        remapped_bonds.append(
            f"{new_i:3d}{new_j:3d}{int(line[6:9]):3d}{0:3d}"
        )
    return (
        "\n".join(
            (
                *lines[:4],
                *atom_lines,
                *remapped_bonds,
                *lines[4 + atom_count + bond_count :],
            )
        )
        + "\n"
    ).encode("ascii")


@pytest.mark.parametrize(
    (
        "path",
        "carbon_count",
        "hydrogen_count",
        "bond_count",
        "label",
        "formula",
        "chain",
    ),
    [
        (METHANE, 1, 4, 4, "methane", "C1H4", (0,)),
        (ALKANES / "ethane_explicit_h.sdf", 2, 6, 7, "ethane", "C2H6", (0, 1)),
        (ALKANES / "propane_explicit_h.sdf", 3, 8, 10, "propane", "C3H8", (0, 1, 2)),
        (
            ALKANES / "n_butane_explicit_h.sdf",
            4,
            10,
            13,
            "n_butane",
            "C4H10",
            (0, 1, 2, 3),
        ),
    ],
)
def test_source_bound_linear_alkanes_c1_c4_are_available_only_topologically(
    path: Path,
    carbon_count: int,
    hydrogen_count: int,
    bond_count: int,
    label: str,
    formula: str,
    chain: tuple[int, ...],
) -> None:
    report = analyze_linear_alkane_c1_c4_force_field_applicability(_system(path))
    payload = report.to_dict()

    assert payload["schema_id"] == (
        LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_ID
    )
    assert payload["schema_version"] == (
        LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_VERSION
    ) == "1.0.0"
    assert report.profile_id == (
        LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_PROFILE_ID
    )
    assert report.claim_scope == (
        LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_CLAIM_SCOPE
    )
    assert report.constraint_results == tuple(
        (code, True)
        for code in LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_CONSTRAINT_CODES
    )
    assert report.failed_constraint_codes == ()
    assert report.applicability_status == report.status == "available"
    assert report.applicable is True
    assert report.canonical_ingest_status == "supported"
    assert report.profile_local_evidence_status == "satisfied"
    assert report.carbon_atom_count == carbon_count
    assert report.hydrogen_atom_count == hydrogen_count
    assert report.atom_count == carbon_count + hydrogen_count
    assert report.bond_count == bond_count
    assert report.residue_count == report.component_count == 1
    assert report.carbon_atom_indices == tuple(range(carbon_count))
    assert len(report.hydrogen_atom_indices) == hydrogen_count
    assert report.canonical_carbon_chain == chain
    assert report.carbon_chain_orientation_policy_id == (
        LINEAR_ALKANE_C1_C4_CARBON_CHAIN_ORIENTATION_POLICY_ID
    )
    assert report.molecule_label == label
    assert report.molecular_formula == formula
    assert report.observed_partial_charge_count == 0
    assert report.source_format == "sdf_v2000"
    assert report.source_digest_available is True
    assert report.parser_observation_self_consistent is True
    assert report.source_authentication_status == "digest_bound_not_authenticated"
    assert report.source_authenticated is False
    assert report.parameter_set_id is None
    assert report.parameter_assignment_sha256 is None
    assert report.parameterability_status == (
        "not_assessed_topological_applicability_only"
    )
    assert report.atom_typing_status == "not_assigned"
    assert report.partial_charge_assignment_status == "not_assigned"
    false_gates = (
        "preparation_ready",
        "parameterability_assessed",
        "parameterizable",
        "atom_types_assigned",
        "partial_charges_assigned",
        "force_field_parameters_assigned",
        "global_parameter_coverage_complete",
        "physics_supported",
        "scientific_validity_green",
        "runtime_eligible",
        "execution_authorized",
        "energy_evaluation_authorized",
        "force_evaluation_authorized",
        "virial_evaluation_authorized",
        "minimization_authorized",
        "simulation_ready",
        "claim_safe",
    )
    assert all(payload[name] is False for name in false_gates)
    assert all(getattr(report, name) is False for name in false_gates)
    assert "source_digest_is_not_authentication" in report.blockers
    assert "bounded_profile_is_not_general_alkane_support" in report.blockers
    assert len(report.report_sha256) == 64
    assert payload["report_sha256"] == report.report_sha256
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload


def test_report_owns_canonical_bytes_and_recomputes_after_original_tensor_mutation() -> None:
    system = _system(ALKANES / "n_butane_explicit_h.sdf")
    report = analyze_linear_alkane_c1_c4_force_field_applicability(system)
    baseline = report.to_dict()
    baseline_coordinates = report.system.coordinates.clone()

    system.coordinates.add_(37.0)

    assert report.to_dict() == baseline
    assert torch.equal(report.system.coordinates, baseline_coordinates)
    assert report.matches_system(system) is False
    shifted = analyze_linear_alkane_c1_c4_force_field_applicability(system)
    assert shifted.status == "available"
    assert shifted.canonical_carbon_chain == report.canonical_carbon_chain
    assert shifted.report_sha256 != report.report_sha256

    restored = deserialize_all_atom_system(serialize_all_atom_system(report.system))
    assert report.matches_system(restored) is True


def test_coordinates_names_and_nonchemical_residue_labels_do_not_change_classification() -> None:
    baseline_system = _system(ALKANES / "propane_explicit_h.sdf")
    baseline = analyze_linear_alkane_c1_c4_force_field_applicability(
        baseline_system
    )
    renamed = replace(
        baseline_system,
        system_id="renamed-propane",
        atoms=tuple(
            replace(atom, name=f"SOURCE_LABEL_{atom.index}")
            for atom in baseline_system.atoms
        ),
        residues=(
            replace(
                baseline_system.residues[0],
                name="ALT",
                sequence_number=913,
                hetero=False,
            ),
        ),
        chains=(
            replace(
                baseline_system.chains[0],
                chain_id="Q",
                entity_id="renamed-source-entity",
            ),
        ),
        coordinates=baseline_system.coordinates + 11.0,
    )
    renamed = _refresh_unkeyed_parser_bindings(renamed)
    changed = analyze_linear_alkane_c1_c4_force_field_applicability(renamed)

    assert changed.status == baseline.status == "available"
    assert changed.constraint_results == baseline.constraint_results
    assert changed.canonical_carbon_chain == baseline.canonical_carbon_chain
    assert changed.molecule_label == baseline.molecule_label == "propane"
    assert changed.source_sha256 == baseline.source_sha256
    assert changed.canonical_system_snapshot_sha256 != (
        baseline.canonical_system_snapshot_sha256
    )
    assert changed.report_sha256 != baseline.report_sha256


@pytest.mark.parametrize(
    ("filename", "required_failures"),
    [
        (
            "isobutane_branched_explicit_h.sdf",
            {
                "carbon_subgraph_simple_path",
                "exact_carbon_hydrogen_degrees",
            },
        ),
        (
            "cyclobutane_explicit_h.sdf",
            {
                "canonical_ingest_supported",
                "profile_local_evidence_satisfied",
                "carbon_subgraph_simple_path",
            },
        ),
        (
            "ethane_missing_h.sdf",
            {
                "canonical_ingest_supported",
                "profile_local_evidence_satisfied",
                "exact_linear_alkane_formula",
                "exact_carbon_hydrogen_degrees",
            },
        ),
    ],
)
def test_branch_cycle_and_missing_hydrogen_fail_closed(
    filename: str,
    required_failures: set[str],
) -> None:
    report = analyze_linear_alkane_c1_c4_force_field_applicability(
        _system(ALKANES / filename)
    )

    assert report.status == "unsupported"
    assert required_failures <= set(report.failed_constraint_codes)
    assert report.applicable is False
    assert report.carbon_atom_indices == ()
    assert report.hydrogen_atom_indices == ()
    assert report.canonical_carbon_chain == ()
    assert report.molecule_label is None
    assert report.molecular_formula is None
    assert report.claim_safe is False


@pytest.mark.parametrize(
    ("property_line", "required_failure"),
    [
        (b"M  CHG  1   1   1\n", "formal_charges_known_zero"),
        (b"M  ISO  1   1  13\n", "isotopes_absent"),
    ],
)
def test_nonzero_charge_and_isotope_fail_closed(
    property_line: bytes,
    required_failure: str,
) -> None:
    source = (ALKANES / "ethane_explicit_h.sdf").read_bytes().replace(
        b"M  END\n",
        property_line + b"M  END\n",
        1,
    )
    system = parse_sdf_v2000(source, source_id=required_failure).system
    report = analyze_linear_alkane_c1_c4_force_field_applicability(system)

    assert report.status == "unsupported"
    assert required_failure in report.failed_constraint_codes
    assert "canonical_ingest_supported" in report.failed_constraint_codes
    assert "profile_local_evidence_satisfied" in report.failed_constraint_codes
    assert report.claim_safe is False


def test_source_partial_charge_is_never_treated_as_force_field_charge() -> None:
    system = _system(ALKANES / "ethane_explicit_h.sdf")
    atoms = list(system.atoms)
    atoms[0] = replace(atoms[0], partial_charge_e=0.0)
    with_source_partial_charge = replace(system, atoms=tuple(atoms))
    report = analyze_linear_alkane_c1_c4_force_field_applicability(
        with_source_partial_charge
    )

    assert report.canonical_ingest_status == "supported"
    assert report.profile_local_evidence_status == "satisfied"
    assert report.status == "unsupported"
    assert report.failed_constraint_codes == ("source_partial_charges_absent",)
    assert report.observed_partial_charge_count == 1
    assert report.partial_charge_assignment_status == "not_assigned"
    assert report.partial_charges_assigned is False
    assert report.parameterizable is False


def test_generated_or_unknown_hydrogen_origin_fails_closed() -> None:
    system = _system(ALKANES / "ethane_explicit_h.sdf")
    atoms = list(system.atoms)
    metadata = dict(atoms[2].metadata)
    metadata["hydrogen_origin"] = "adapter_generated"
    atoms[2] = replace(atoms[2], metadata=metadata)
    changed = attach_parser_observation_digest(replace(system, atoms=tuple(atoms)))
    report = analyze_linear_alkane_c1_c4_force_field_applicability(changed)

    assert report.status == "unsupported"
    assert "canonical_ingest_supported" in report.failed_constraint_codes
    assert "profile_local_evidence_satisfied" in report.failed_constraint_codes
    assert "exact_source_observed_hydrogen_inventory" in (
        report.failed_constraint_codes
    )


def test_wrong_parser_pedigree_and_nonpolymer_residue_fail_closed() -> None:
    system = _system(ALKANES / "ethane_explicit_h.sdf")
    wrong_parser = attach_parser_observation_digest(
        replace(
            system,
            provenance=replace(
                system.provenance,
                parser_name="unreviewed.sdf.parser",
                parser_version="99.0.0",
            ),
        )
    )
    invalid = analyze_linear_alkane_c1_c4_force_field_applicability(
        wrong_parser
    )
    assert invalid.status == "invalid"
    assert "upstream_applicability_valid" in invalid.failed_constraint_codes
    assert "sdf_v2000_source_pedigree" in invalid.failed_constraint_codes
    assert "source_binding_self_consistent" in invalid.failed_constraint_codes

    polymer = replace(
        system,
        residues=(replace(system.residues[0], entity_type="polymer"),),
    )
    polymer = _refresh_unkeyed_parser_bindings(polymer)
    unsupported = analyze_linear_alkane_c1_c4_force_field_applicability(polymer)
    assert unsupported.status == "unsupported"
    assert unsupported.failed_constraint_codes == (
        "single_nonpolymer_residue",
    )


def test_arbitrary_reindexing_and_bond_row_order_preserve_chemical_decision() -> None:
    path = ALKANES / "n_butane_explicit_h.sdf"
    baseline = analyze_linear_alkane_c1_c4_force_field_applicability(
        _system(path)
    )
    source = _permuted_sdf_source(path, tuple(reversed(range(14))))
    permuted_system = parse_sdf_v2000(
        source,
        source_id="reverse-index-and-bond-order-n-butane",
    ).system
    permuted = analyze_linear_alkane_c1_c4_force_field_applicability(
        permuted_system
    )

    assert baseline.status == permuted.status == "available"
    assert permuted.carbon_atom_indices == (10, 11, 12, 13)
    assert permuted.canonical_carbon_chain == (10, 11, 12, 13)
    assert permuted.molecule_label == baseline.molecule_label == "n_butane"
    assert permuted.molecular_formula == baseline.molecular_formula == "C4H10"
    assert permuted.constraint_results == baseline.constraint_results
    assert permuted.source_sha256 != baseline.source_sha256


def test_report_is_slotted_frozen_and_public_constant_monkeypatches_are_nonsemantic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = analyze_linear_alkane_c1_c4_force_field_applicability(
        _system(ALKANES / "ethane_explicit_h.sdf")
    )
    baseline = report.to_dict()

    assert not hasattr(report, "__dict__")
    with pytest.raises(FrozenInstanceError):
        report._canonical_system_bytes = b"changed"  # type: ignore[misc]

    monkeypatch.setattr(
        module,
        "LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_ID",
        "mutated-public-schema",
    )
    monkeypatch.setattr(
        module,
        "LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_PROFILE_ID",
        "mutated-public-profile",
    )
    monkeypatch.setattr(
        module,
        "LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_CONSTRAINT_CODES",
        ("mutated",),
    )
    assert report.to_dict() == baseline

    object.__setattr__(report, "_canonical_system_bytes", b"{}")
    with pytest.raises((MolecularSerializationError, ValueError)):
        _ = report.claim_safe


def test_report_digest_is_hashseed_independent() -> None:
    script = """
from pathlib import Path
from betelgeuze_engine_v2.molecular.alkane_forcefield_applicability import analyze_linear_alkane_c1_c4_force_field_applicability
from betelgeuze_engine_v2.molecular.sdf_v2000 import parse_sdf_v2000
p = Path('tests/fixtures/v2_2_linear_alkane/n_butane_explicit_h.sdf')
s = parse_sdf_v2000(p.read_bytes(), source_id='hashseed-n-butane').system
print(analyze_linear_alkane_c1_c4_force_field_applicability(s).report_sha256)
"""
    digests = []
    for seed in ("1", "8675309"):
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = seed
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPOSITORY_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        digests.append(completed.stdout.strip())
    assert digests[0] == digests[1]
    assert len(digests[0]) == hashlib.sha256().digest_size * 2


def test_factory_rejects_nonexact_system_type() -> None:
    with pytest.raises(TypeError, match="AllAtomSystem"):
        analyze_linear_alkane_c1_c4_force_field_applicability(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="AllAtomSystem"):
        LinearAlkaneC1C4ForceFieldApplicabilityReport(object())  # type: ignore[arg-type]
