from __future__ import annotations

import ast
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path

import pytest

import betelgeuze_engine_v2 as package_root
import betelgeuze_engine_v2.forcefield as forcefield_api
from betelgeuze_engine_v2.forcefield import (
    spice_graph_family_disjoint_population_preflight as module,
)
from betelgeuze_engine_v2.forcefield.spice_graph_family_disjoint_population_preflight import (
    SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_CLAIM_SCOPE,
    SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_PROTOCOL_ID,
    SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_PROTOCOL_SHA256,
    SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_SCHEMA_ID,
    SpiceGraphFamilyDisjointPopulationPreflightReport,
    analyze_spice_graph_family_disjoint_population_preflight,
    serialize_spice_graph_family_disjoint_population_preflight_report,
    spice_graph_family_disjoint_population_preflight_protocol_bytes,
    spice_graph_family_disjoint_population_preflight_protocol_document,
)
from betelgeuze_engine_v2.forcefield.spice_c1c4_quantum_reference import (
    load_spice_c1c4_quantum_reference_evidence,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = (
    REPOSITORY_ROOT
    / "config"
    / "independent_engine_v2_v2_2_spice_c1c4_quantum_reference_evidence.json"
)
PACKET_PATH = (
    REPOSITORY_ROOT
    / "config"
    / "independent_engine_v2_v2_2_spice_c1c4_source_review_packet.json"
)
MODULE_PATH = (
    REPOSITORY_ROOT
    / "betelgeuze_engine_v2"
    / "forcefield"
    / "spice_graph_family_disjoint_population_preflight.py"
)


def _source_bytes() -> bytes:
    return SOURCE_PATH.read_bytes()


def _packet_bytes() -> bytes:
    return PACKET_PATH.read_bytes()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )


@pytest.fixture(scope="module")
def report() -> SpiceGraphFamilyDisjointPopulationPreflightReport:
    return analyze_spice_graph_family_disjoint_population_preflight(
        _source_bytes(),
        _packet_bytes(),
    )


def test_protocol_is_canonical_detached_and_hash_frozen(report) -> None:
    protocol_bytes = spice_graph_family_disjoint_population_preflight_protocol_bytes()
    assert hashlib.sha256(protocol_bytes).hexdigest() == (
        SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_PROTOCOL_SHA256
    )
    assert SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_PROTOCOL_SHA256 == (
        "57482f6a531b068c3589c7820025ed52e4af0cb3bde482180f8e9d08ba877415"
    )
    document = spice_graph_family_disjoint_population_preflight_protocol_document()
    assert document == module._PROTOCOL_DOCUMENT
    assert document["protocol_id"] == (
        SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_PROTOCOL_ID
    )
    assert document["claim_scope"] == (
        SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_CLAIM_SCOPE
    )
    document["claim_scope"] = "mutated"
    assert (
        spice_graph_family_disjoint_population_preflight_protocol_document()[
            "claim_scope"
        ]
        == SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_CLAIM_SCOPE
    )

    assert report.schema_id == (
        SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_SCHEMA_ID
    )
    assert report.protocol_sha256 == (
        SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_PROTOCOL_SHA256
    )


def test_private_nested_protocol_mutation_cannot_change_frozen_bytes_or_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen_bytes = spice_graph_family_disjoint_population_preflight_protocol_bytes()
    frozen_sha256 = hashlib.sha256(frozen_bytes).hexdigest()
    monkeypatch.setitem(module._PROTOCOL_DOCUMENT["nonpromotion"], "claim_safe", True)

    assert spice_graph_family_disjoint_population_preflight_protocol_bytes() == (
        frozen_bytes
    )
    assert (
        spice_graph_family_disjoint_population_preflight_protocol_document()[
            "nonpromotion"
        ]["claim_safe"]
        is False
    )
    mutated_process_report = analyze_spice_graph_family_disjoint_population_preflight(
        _source_bytes(), _packet_bytes()
    )
    assert mutated_process_report.protocol_sha256 == frozen_sha256


def test_factory_only_report_and_deterministic_serializer(report) -> None:
    assert isinstance(report, SpiceGraphFamilyDisjointPopulationPreflightReport)
    with pytest.raises(TypeError, match="factory-only"):
        replace(report, _factory_token=object())
    serialized = serialize_spice_graph_family_disjoint_population_preflight_report(
        _source_bytes(),
        _packet_bytes(),
    )
    assert serialized == _canonical_bytes(asdict(report))
    assert serialized == (
        serialize_spice_graph_family_disjoint_population_preflight_report(
            _source_bytes(),
            _packet_bytes(),
        )
    )


def test_public_protocol_alias_mutation_cannot_redefine_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module,
        "SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_SCHEMA_ID",
        "mutated.schema",
    )
    monkeypatch.setattr(
        module,
        "SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_PROTOCOL_ID",
        "mutated.protocol",
    )
    monkeypatch.setattr(
        module,
        "SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_PROTOCOL_SHA256",
        "0" * 64,
    )
    monkeypatch.setattr(
        module,
        "SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_CLAIM_SCOPE",
        "mutated.claim",
    )
    report = analyze_spice_graph_family_disjoint_population_preflight(
        _source_bytes(), _packet_bytes()
    )
    assert report.schema_id == (
        "betelgeuze.spice_graph_family_disjoint_population_preflight/1.0.0"
    )
    assert report.protocol_id == (
        "spice_hydrocarbon_target_independent_hierarchical_graph_family_split_"
        "preflight/1.0.0"
    )
    assert report.protocol_sha256 == (
        "57482f6a531b068c3589c7820025ed52e4af0cb3bde482180f8e9d08ba877415"
    )
    assert report.claim_scope == (
        "prospective_metadata_only_graph_family_split_requirements_no_"
        "scientific_evidence"
    )


def test_current_c1_c4_is_same_graph_and_same_family_across_partitions(
    report,
) -> None:
    assert report.source_review_packet_integrity_bound is True
    assert report.current_group_order == ("c", "cc", "ccc", "cccc")
    assert report.current_graph_count == 4
    assert report.current_family_count == 1
    assert report.current_family_ids == ("neutral_singlet_explicit_h_linear_alkane",)
    assert report.current_graph_overlap_count == 4
    assert report.current_family_overlap_count == 1
    assert report.current_canonical_graph_sha256 == (
        ("c", "aba02557b2c9cb089288307c7ceb2dbfafb65d3f1cf4e43b3cd60193b5474c20"),
        ("cc", "1dd4a184939eb977a437b6e760eae448aef2a3990f09fe51bc04eb927f149293"),
        ("ccc", "e9c44323a148dd0bbe9cd9cc559ca6ae97e98a585bb92d8b7a16cfca6bcc2fd0"),
        (
            "cccc",
            "c35a8d7eae753900b4ee0b86669c5b047359122aa7ed8122f612362ae00e19f9",
        ),
    )
    assert report.current_topology_receipt_sha256 == (
        "560e0331afad68873a6d62fb2577f9af6ee7434b656e24c4231811f82238d805"
    )
    assert report.current_graph_disjoint is False
    assert report.current_family_disjoint is False
    assert report.current_time_disjoint is False
    assert report.current_release_disjoint is False
    assert report.current_public_holdout_blind_to_humans is False
    assert (
        report.current_bond_environment_key_count,
        report.current_angle_environment_key_count,
        report.current_proper_environment_key_count,
    ) == (6, 9, 7)


def test_canonical_graph_hash_is_permutation_invariant_and_label_sensitive() -> None:
    corpus = load_spice_c1c4_quantum_reference_evidence(_source_bytes())
    group = next(row for row in corpus.groups if row.group_id == "ccc")
    original = module._canonical_graph_sha256(
        group.atomic_numbers,
        group.connectivity,
        molecular_charge=group.molecular_charge,
        molecular_multiplicity=group.molecular_multiplicity,
    )
    permutation = tuple(reversed(range(group.atom_count)))
    permuted_atoms = [0] * group.atom_count
    for old_index, new_index in enumerate(permutation):
        permuted_atoms[new_index] = group.atomic_numbers[old_index]
    permuted_connectivity = tuple(
        (permutation[atom_i], permutation[atom_j], order)
        for atom_i, atom_j, order in reversed(group.connectivity)
    )
    assert (
        module._canonical_graph_sha256(
            tuple(permuted_atoms),
            permuted_connectivity,
            molecular_charge=0.0,
            molecular_multiplicity=1,
        )
        == original
    )

    changed_bond_order = list(group.connectivity)
    atom_i, atom_j, _ = changed_bond_order[0]
    changed_bond_order[0] = (atom_i, atom_j, 2.0)
    assert (
        module._canonical_graph_sha256(
            group.atomic_numbers,
            tuple(changed_bond_order),
            molecular_charge=0.0,
            molecular_multiplicity=1,
        )
        != original
    )
    assert (
        module._canonical_graph_sha256(
            group.atomic_numbers,
            group.connectivity,
            molecular_charge=1.0,
            molecular_multiplicity=1,
        )
        != original
    )
    assert (
        module._canonical_graph_sha256(
            group.atomic_numbers,
            group.connectivity,
            molecular_charge=0.0,
            molecular_multiplicity=2,
        )
        != original
    )
    assert (
        module._canonical_graph_sha256(
            group.atomic_numbers,
            group.connectivity,
            molecular_charge=-0.0,
            molecular_multiplicity=1,
        )
        == original
    )
    for invalid_charge in (float("nan"), float("inf"), 0.5):
        with pytest.raises(
            module.SpiceGraphFamilyDisjointPopulationPreflightContractError,
            match="integer-valued",
        ):
            module._canonical_graph_sha256(
                group.atomic_numbers,
                group.connectivity,
                molecular_charge=invalid_charge,
                molecular_multiplicity=1,
            )
    for state_field in ("isotope_state", "stereo_state"):
        with pytest.raises(
            module.SpiceGraphFamilyDisjointPopulationPreflightContractError,
            match="new atom-labeled isotope/stereo identity schema",
        ):
            module._canonical_graph_sha256(
                group.atomic_numbers,
                group.connectivity,
                molecular_charge=0.0,
                molecular_multiplicity=1,
                **{state_field: "explicitly_present"},
            )


def test_c5_c6_are_exact_versioned_coverage_expansions_not_holdouts(report) -> None:
    assert (
        report.c5_delta_bond_key_count,
        report.c5_delta_angle_key_count,
        report.c5_delta_proper_key_count,
    ) == (0, 1, 2)
    assert report.c5_new_angle_keys == (
        (
            "c_single_valence4_c2_h2",
            "c_single_valence4_c2_h2",
            "c_single_valence4_c2_h2",
        ),
    )
    assert report.c5_new_proper_keys == (
        (
            "c_single_valence4_c1_h3",
            "c_single_valence4_c2_h2",
            "c_single_valence4_c2_h2",
            "c_single_valence4_c2_h2",
        ),
        (
            "c_single_valence4_c2_h2",
            "c_single_valence4_c2_h2",
            "c_single_valence4_c2_h2",
            "h_attached_c_single_valence4_c2_h2",
        ),
    )
    assert (
        report.c6_vs_c1_c4_delta_bond_key_count,
        report.c6_vs_c1_c4_delta_angle_key_count,
        report.c6_vs_c1_c4_delta_proper_key_count,
    ) == (0, 1, 3)
    assert (
        report.c6_vs_c5_delta_bond_key_count,
        report.c6_vs_c5_delta_angle_key_count,
        report.c6_vs_c5_delta_proper_key_count,
    ) == (0, 0, 1)
    assert report.c6_only_new_proper_keys == (
        (
            "c_single_valence4_c2_h2",
            "c_single_valence4_c2_h2",
            "c_single_valence4_c2_h2",
            "c_single_valence4_c2_h2",
        ),
    )
    assert report.c7_plus_no_new_local_keys_after_c1_c6 is True
    assert report.c5_c6_accuracy_holdout_eligible is False
    assert report.c5_c6_ood_or_coverage_expansion_only is True
    assert report.versioned_coverage_expansion_required is True


def test_independent_topology_projection_reproduces_all_declared_key_deltas() -> None:
    c1_c4 = module._linear_alkane_key_universe(4)
    c1_c5 = module._linear_alkane_key_universe(5)
    c1_c6 = module._linear_alkane_key_universe(6)
    assert tuple(map(len, c1_c4)) == (6, 9, 7)
    assert tuple(len(c1_c5[index] - c1_c4[index]) for index in range(3)) == (
        0,
        1,
        2,
    )
    assert tuple(len(c1_c6[index] - c1_c4[index]) for index in range(3)) == (
        0,
        1,
        3,
    )
    assert tuple(len(c1_c6[index] - c1_c5[index]) for index in range(3)) == (
        0,
        0,
        1,
    )
    for carbon_count in (7, 8, 9, 12):
        assert module._linear_alkane_key_universe(carbon_count) == c1_c6


def test_protocol_freezes_hierarchy_semantics_metrics_and_sequencing() -> None:
    document = spice_graph_family_disjoint_population_preflight_protocol_document()
    assert document["current_baseline"]["canonical_graph_sha256_by_group"] == [
        ["c", "aba02557b2c9cb089288307c7ceb2dbfafb65d3f1cf4e43b3cd60193b5474c20"],
        ["cc", "1dd4a184939eb977a437b6e760eae448aef2a3990f09fe51bc04eb927f149293"],
        ["ccc", "e9c44323a148dd0bbe9cd9cc559ca6ae97e98a585bb92d8b7a16cfca6bcc2fd0"],
        [
            "cccc",
            "c35a8d7eae753900b4ee0b86669c5b047359122aa7ed8122f612362ae00e19f9",
        ],
    ]
    assert document["current_baseline"]["topology_receipt_sha256"] == (
        "560e0331afad68873a6d62fb2577f9af6ee7434b656e24c4231811f82238d805"
    )
    assert document["identity"]["isotope_stereo_scope"] == ("explicitly_absent_only")
    assert (
        document["identity"][
            "isotope_or_stereo_present_requires_new_atom_labeled_identity_schema"
        ]
        is True
    )
    assert document["identity"]["canonical_graph_sha256_recipe"]["domain_hex"] == (
        module._GRAPH_HASH_DOMAIN.hex()
    )
    assert (
        document["identity"]["topology_receipt_sha256_recipe"]["domain_hex"]
        == module._TOPOLOGY_RECEIPT_HASH_DOMAIN.hex()
    )
    assert document["split_hierarchy"] == [
        "release",
        "chemistry_family",
        "parent_or_scaffold",
        "exact_molecular_graph",
        "source_related_conformer_or_geometry_cluster",
        "record",
    ]
    assert document["split_units"]["graph_disjoint_lane"] == (
        "entire_exact_molecular_graph"
    )
    assert document["split_units"]["family_disjoint_lane"] == (
        "entire_chemistry_family"
    )
    assert (
        document["target_semantics"]["shared_cross_molecule_absolute_energy_offset"]
        is False
    )
    assert document["target_semantics"]["source_gradient"] == "dE_dR_not_force"
    assert document["target_semantics"]["force_target"] == ("negative_source_gradient")
    assert (
        document["target_semantics"][
            "source_integrity_replay_decodes_and_validates_target_values"
        ]
        is True
    )
    assert (
        document["target_semantics"]["population_or_split_decision_uses_target_values"]
        is False
    )
    assert document["metrics"]["uncertainty_resampling_unit"] == (
        "outer_graph_or_family_with_source_pair_blocks_nested_within_graph"
    )
    assert document["metrics"]["source_pair_blocks_are_outer_independent_units"] is (
        False
    )
    assert document["metrics"]["force_scalars_are_independent_samples"] is False
    assert (
        document["metrics"]["threshold_manifest_sha256_frozen_before_candidate_fit"]
        is True
    )
    assert document["candidate_sequence"][0] == (
        "source_receipts_and_independent_license_review"
    )
    assert document["candidate_sequence"][-1] == (
        "separate_externally_sealed_blind_evaluation"
    )


def test_pending_receipts_and_all_science_runtime_claims_remain_false(report) -> None:
    false_fields = (
        "whole_file_stream_receipt_available",
        "subset_extraction_receipt_available",
        "license_human_reviewed",
        "prerequisite_receipts_satisfied",
        "expanded_source_data_acquired",
        "expanded_target_view_available",
        "split_manifest_available",
        "threshold_manifest_available",
        "candidate_fitting_performed",
        "candidate_parameter_set_available",
        "parameter_family_sufficiency_assessed",
        "scientific_validation_performed",
        "reference_validation_performed",
        "transferability_established",
        "parameterability_assessed",
        "parameterizable",
        "production_parameters_available",
        "physics_ready",
        "runtime_eligible",
        "execution_authorized",
        "claim_safe",
    )
    assert all(getattr(report, field) is False for field in false_fields)


def test_population_module_has_no_target_fit_parameter_or_runtime_dependency() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    accessed_attributes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module or "")
        elif isinstance(node, ast.Attribute):
            accessed_attributes.add(node.attr)

    forbidden_import_fragments = (
        "spice_c1c4_force_matching_targets",
        "spice_c1c4_bonded_basis_observability",
        "fitting",
        "parameters",
        "assignment",
        "kernel",
        "runtime",
    )
    assert not any(
        fragment in imported
        for imported in imported_modules
        for fragment in forbidden_import_fragments
    )
    assert (
        not {
            "energy_binary64_be_hex",
            "gradient_binary32_be_hex",
            "force_kj_per_mol_per_angstrom_binary64_be_hex",
        }
        & accessed_attributes
    )
    assert "candidate_fitting_performed=True" not in source
    assert "claim_safe=True" not in source


def test_population_preflight_api_is_forcefield_only() -> None:
    exported_names = (
        "SPICE_GRAPH_FAMILY_DISJOINT_POPULATION_PREFLIGHT_SCHEMA_ID",
        "SpiceGraphFamilyDisjointPopulationPreflightReport",
        "analyze_spice_graph_family_disjoint_population_preflight",
        "serialize_spice_graph_family_disjoint_population_preflight_report",
        "spice_graph_family_disjoint_population_preflight_protocol_bytes",
    )
    for name in exported_names:
        assert name in forcefield_api.__all__
        assert hasattr(forcefield_api, name)
        assert name not in package_root.__all__
        assert not hasattr(package_root, name)
