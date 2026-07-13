from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest
import torch

from betelgeuze_engine_v2.molecular import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    MAX_PREPARATION_AUDIT_ATOMS,
    MAX_PREPARATION_AUDIT_BONDS,
    MAX_PREPARATION_AUDIT_CHAINS,
    MAX_PREPARATION_AUDIT_RESIDUES,
    PARSER_OBSERVATION_SCHEMA_ID,
    PREPARATION_POLICY_ID,
    PREPARATION_REPORT_SCHEMA_VERSION,
    PREPARATION_UNASSESSED_ASPECTS,
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    PreparationCoverageError,
    PreparationCoverageLimitError,
    Residue,
    StructureProvenance,
    UnitCell,
    analyze_molecular_preparation,
    attached_canonical_topology_sha256_matches,
    attached_parser_observation_sha256_matches,
    canonical_topology_sha256,
    deserialize_all_atom_system,
    parse_mmcif,
    parse_pdb,
    parse_sdf_v2000,
    parse_smiles,
    require_supported_preparation,
    serialize_all_atom_system,
)
from betelgeuze_engine_v2.molecular import preparation as preparation_module
from betelgeuze_engine_v2.molecular import smiles as smiles_module
from betelgeuze_engine_v2.molecular.observation import (
    attach_parser_observation_digest,
)


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tier_beta"


def _system() -> AllAtomSystem:
    return AllAtomSystem(
        system_id="preparation-inventory",
        atoms=(
            Atom(index=0, name="C1", element="C", atomic_number=6, residue_index=0),
            Atom(index=1, name="O1", element="O", atomic_number=8, residue_index=0),
            Atom(index=2, name="H1", element="H", atomic_number=1, residue_index=0),
        ),
        bonds=(
            Bond(index=0, atom_i=0, atom_j=1, order=1.0),
            Bond(index=1, atom_i=1, atom_j=2, order=1.0),
        ),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=(0, 1, 2),
                entity_type="non_polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.zeros((1, 3, 3), dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit"),
    )


def _mixed_roles_system() -> AllAtomSystem:
    atoms = (
        Atom(index=0, name="O", element="O", atomic_number=8, residue_index=0),
        Atom(index=1, name="H1", element="H", atomic_number=1, residue_index=0),
        Atom(
            index=2,
            name="NA",
            element="Na",
            atomic_number=11,
            residue_index=1,
            formal_charge=1,
        ),
        Atom(index=3, name="C1", element="C", atomic_number=6, residue_index=2),
        Atom(index=4, name="C2", element="C", atomic_number=6, residue_index=3),
        Atom(index=5, name="N1", element="N", atomic_number=7, residue_index=4),
    )
    residues = (
        Residue(0, "HOH", 0, 1, (0, 1), entity_type="water", hetero=True),
        Residue(1, "NA", 0, 2, (2,), entity_type="non_polymer", hetero=True),
        Residue(2, "MSE", 0, 3, (3,), entity_type="polymer", hetero=True),
        Residue(3, "BRN", 0, 4, (4,), entity_type="branched", hetero=True),
        Residue(4, "UNK", 0, 5, (5,), entity_type="unknown", hetero=True),
    )
    return AllAtomSystem(
        system_id="mixed-roles",
        atoms=atoms,
        bonds=(Bond(index=0, atom_i=0, atom_j=1, order=1.0),),
        residues=residues,
        chains=(Chain(index=0, chain_id="A", residue_indices=(0, 1, 2, 3, 4)),),
        coordinates=torch.zeros((1, 6, 3), dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit"),
    )


@pytest.fixture
def supported_local_rdkit(monkeypatch: pytest.MonkeyPatch) -> None:
    try:
        _, rd_base = smiles_module._import_rdkit()
    except (ImportError, ModuleNotFoundError):
        pytest.skip("RDKit is unavailable in this test environment")
    monkeypatch.setattr(
        smiles_module,
        "_SUPPORTED_RDKIT_VERSIONS",
        frozenset({rd_base.rdkitVersion}),
    )


def test_report_is_deterministic_topology_bound_json_and_never_promotes() -> None:
    source = _system()
    report = analyze_molecular_preparation(source)
    payload = report.to_dict()

    assert payload["schema_version"] == PREPARATION_REPORT_SCHEMA_VERSION == "1.4.0"
    assert report.policy_id == PREPARATION_POLICY_ID
    assert report.canonical_topology_schema_id == CANONICAL_TOPOLOGY_SCHEMA_ID
    assert report.canonical_topology_sha256 == canonical_topology_sha256(source)
    assert report.canonical_topology_digest_available is True
    assert report.source_sha256 is None
    assert report.source_digest_available is False
    assert report.parser_pedigree_id == "unrecognized"
    assert report.parser_observation_self_consistent is False
    assert report.bond_count == 2
    assert report.preparation_assessed is False
    assert report.preparation_ready is False
    assert report.claim_safe is False
    assert report.missing_atom_count is None
    assert report.missing_residue_count is None
    assert report.unassessed_aspects == PREPARATION_UNASSESSED_ASPECTS
    assert report.hydrogen_origin_counts == (("unknown", 1),)
    assert report.unknown_hydrogen_origin_count == 1
    assert report.formal_charge_origin_counts == (("unclassified_known", 3),)
    assert report.hydrogen_completeness_assessed is False
    assert report.protonation_assessed is False
    assert report.tautomer_assessed is False
    assert report.aromaticity_perception_assessed is False
    assert report.formal_charge_assignment_assessed is False
    assert report.report_state_normalization_attempted is False
    assert report.report_state_normalization_applied is False
    assert "preparation_not_assessed" in report.blockers
    assert "hydrogen_origin_unknown_for_some_atoms" in report.blockers
    assert "chemical_state_normalization_not_attempted" in report.blockers
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert (
        analyze_molecular_preparation(_system()).report_sha256 == report.report_sha256
    )


def test_preparation_audit_public_resource_contract_and_equality_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert MAX_PREPARATION_AUDIT_ATOMS == 100_000
    assert MAX_PREPARATION_AUDIT_BONDS == 200_000
    assert MAX_PREPARATION_AUDIT_RESIDUES == 100_000
    assert MAX_PREPARATION_AUDIT_CHAINS == 100_000

    source = _system()
    baseline = analyze_molecular_preparation(source)
    for limit_name, boundary in (
        ("MAX_PREPARATION_AUDIT_ATOMS", len(source.atoms)),
        ("MAX_PREPARATION_AUDIT_BONDS", len(source.bonds)),
        ("MAX_PREPARATION_AUDIT_RESIDUES", len(source.residues)),
        ("MAX_PREPARATION_AUDIT_CHAINS", len(source.chains)),
    ):
        with monkeypatch.context() as scoped:
            scoped.setattr(preparation_module, limit_name, boundary)
            report = analyze_molecular_preparation(source)
        assert report.to_dict() == baseline.to_dict()
        assert report.report_sha256 == baseline.report_sha256
        assert report.preparation_assessed is False
        assert report.preparation_ready is False
        assert report.claim_safe is False


@pytest.mark.parametrize(
    ("limit_name", "count_attribute", "expected_code"),
    [
        ("MAX_PREPARATION_AUDIT_ATOMS", "atoms", "atom_limit_exceeded"),
        ("MAX_PREPARATION_AUDIT_BONDS", "bonds", "bond_limit_exceeded"),
        (
            "MAX_PREPARATION_AUDIT_RESIDUES",
            "residues",
            "residue_limit_exceeded",
        ),
        ("MAX_PREPARATION_AUDIT_CHAINS", "chains", "chain_limit_exceeded"),
    ],
)
def test_preparation_audit_limits_fail_before_validation_and_topology_hashing(
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
    count_attribute: str,
    expected_code: str,
) -> None:
    source = _system()
    count = len(getattr(source, count_attribute))
    monkeypatch.setattr(preparation_module, limit_name, count - 1)

    def forbidden_work(*args: object, **kwargs: object) -> object:
        pytest.fail("resource preflight must run before validation or hash work")

    monkeypatch.setattr(
        preparation_module,
        "validate_all_atom_system",
        forbidden_work,
    )
    monkeypatch.setattr(
        preparation_module,
        "canonical_topology_sha256",
        forbidden_work,
    )

    with pytest.raises(PreparationCoverageLimitError) as exc_info:
        analyze_molecular_preparation(source)
    assert exc_info.value.code == expected_code


def test_observed_hydrogen_charge_aromatic_and_entity_values_are_not_completion_claims() -> (
    None
):
    source = _system()
    observed = replace(
        source,
        atoms=(
            replace(source.atoms[0], aromatic=True),
            replace(source.atoms[1], formal_charge_known=False),
            source.atoms[2],
        ),
        bonds=(
            replace(source.bonds[0], order=1.5, aromatic=True),
            source.bonds[1],
        ),
    )
    report = analyze_molecular_preparation(observed)
    assert report.explicit_hydrogen_count == 1
    assert report.unknown_formal_charge_count == 1
    assert report.net_formal_charge is None
    assert report.observed_aromatic_atom_count == 1
    assert report.observed_aromatic_bond_count == 1
    assert report.aromatic_annotation_origin == "unclassified_present"
    assert report.entity_type_counts == (("non_polymer", 1),)
    assert "hydrogen_completeness_not_assessed" in report.blockers
    assert "formal_charge_assignment_not_assessed" in report.blockers
    assert "aromaticity_perception_not_assessed" in report.blockers
    assert (
        "aromaticity_source_or_adapter_state_not_independently_perceived"
        in report.blockers
    )


def test_typed_residue_inventory_does_not_guess_chemical_roles() -> None:
    report = analyze_molecular_preparation(_mixed_roles_system())
    assert report.element_counts == (
        ("C", 2),
        ("H", 1),
        ("N", 1),
        ("Na", 1),
        ("O", 1),
    )
    assert report.entity_type_counts == (
        ("branched", 1),
        ("non_polymer", 1),
        ("polymer", 1),
        ("unknown", 1),
        ("water", 1),
    )
    assert report.canonical_water_entity_type_residue_count == 1
    assert report.single_atom_residue_count == 4
    assert report.polymer_hetero_residue_count == 1
    assert report.non_polymer_like_residue_count == 2
    assert report.explicit_unknown_entity_type_residue_count == 1
    assert report.net_formal_charge == 1
    assert "ion_roles_not_assessed" in report.blockers
    assert "water_roles_not_assessed" in report.blockers
    assert "metal_roles_and_coordination_not_assessed" in report.blockers
    assert "cofactor_roles_not_assessed" in report.blockers
    assert "modified_residue_identity_not_assessed" in report.blockers
    with pytest.raises(ValueError, match="must match entity_type_counts"):
        replace(report, canonical_water_entity_type_residue_count=0)


def test_metadata_and_caller_preparation_boolean_cannot_promote_or_change_report() -> (
    None
):
    source = _system()
    forged = replace(
        source,
        metadata={"preparation_ready": True, "missing_atom_count": 0},
        provenance=replace(
            source.provenance,
            preparation_ready=True,
            claim_safe=True,
            metadata={
                "canonical_topology_sha256": "0" * 64,
                "coverage": {"preparation_ready": True, "blockers": []},
            },
        ),
    )
    baseline = analyze_molecular_preparation(source)
    report = analyze_molecular_preparation(forged)
    assert report.report_sha256 == baseline.report_sha256
    assert report.preparation_assessed is False
    assert report.preparation_ready is False
    assert report.claim_safe is False

    with pytest.raises(ValueError, match="cannot promote"):
        replace(report, preparation_assessed=True, preparation_ready=True)
    with pytest.raises(ValueError, match="cannot promote"):
        replace(report, protonation_assessed=True)
    with pytest.raises(ValueError, match="cannot promote"):
        replace(report, report_state_normalization_attempted=True)
    with pytest.raises(ValueError, match="not assessed"):
        replace(report, missing_atom_count=0)
    with pytest.raises(
        ValueError,
        match="canonical_topology_digest_available must match",
    ):
        replace(report, canonical_topology_sha256=None)
    with pytest.raises(ValueError, match="element_counts must sum"):
        replace(report, atom_count=999)
    with pytest.raises(ValueError, match="hydrogen_origin_counts must sum"):
        replace(report, hydrogen_origin_counts=())
    with pytest.raises(ValueError, match="formal_charge_origin_counts must sum"):
        replace(report, formal_charge_origin_counts=(("unclassified_known", 2),))
    with pytest.raises(TypeError, match="positive integer pairs"):
        replace(report, element_counts=(("C", 0), ("H", 1), ("O", 1)))
    with pytest.raises(ValueError, match="canonical ordered blocker set"):
        replace(report, blockers=())
    with pytest.raises(ValueError, match="canonical ordered blocker set"):
        replace(report, blockers=tuple(reversed(report.blockers)))
    with pytest.raises(ValueError, match="canonical ordered blocker set"):
        replace(report, blockers=(*report.blockers, "caller_added"))
    with pytest.raises(TypeError, match="system_schema_id"):
        replace(report, system_schema_id=7)  # type: ignore[arg-type]

    forged_atom_metadata = replace(
        source,
        atoms=(
            replace(
                source.atoms[0],
                metadata={"formal_charge_source": "pdb_columns_79_80"},
            ),
            source.atoms[1],
            replace(
                source.atoms[2],
                metadata={"hydrogen_origin": "source"},
            ),
        ),
    )
    forged_report = analyze_molecular_preparation(forged_atom_metadata)
    assert forged_report.hydrogen_origin_counts == (("unknown", 1),)
    assert forged_report.formal_charge_origin_counts == (("unclassified_known", 3),)

    unhashable_metadata = replace(
        source,
        atoms=(
            replace(
                source.atoms[0],
                metadata={"formal_charge_source": {"nested": "value"}},
            ),
            source.atoms[1],
            replace(
                source.atoms[2],
                metadata={"hydrogen_origin": []},
            ),
        ),
    )
    unhashable_report = analyze_molecular_preparation(unhashable_metadata)
    assert unhashable_report.hydrogen_origin_counts == (("unknown", 1),)
    assert unhashable_report.formal_charge_origin_counts == (("unclassified_known", 3),)


def test_unknown_entity_count_names_only_the_explicit_canonical_marker() -> None:
    source = _system()
    mystery = replace(
        source,
        residues=(replace(source.residues[0], entity_type="mystery"),),
    )
    report = analyze_molecular_preparation(mystery)
    assert report.entity_type_counts == (("mystery", 1),)
    assert report.explicit_unknown_entity_type_residue_count == 0


def test_invalid_canonical_system_reports_digest_unavailable_without_crashing() -> None:
    source = _system()
    invalid = replace(
        source,
        coordinates=torch.tensor(
            [[[float("nan"), 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]],
            dtype=torch.float64,
        ),
    )
    report = analyze_molecular_preparation(invalid)
    assert report.canonical_validation_valid is False
    assert report.canonical_topology_digest_available is False
    assert report.canonical_topology_sha256 is None
    assert "nonfinite_coordinates" in report.validation_error_codes
    assert "canonical_topology_digest_unavailable" in report.blockers


def test_snapshot_round_trip_preserves_preparation_report() -> None:
    source = _mixed_roles_system()
    restored = deserialize_all_atom_system(serialize_all_atom_system(source))
    assert analyze_molecular_preparation(restored).to_dict() == (
        analyze_molecular_preparation(source).to_dict()
    )


def test_coordinate_ingest_reports_remain_fail_closed() -> None:
    systems = (
        parse_pdb((FIXTURES / "mini_protein.pdb").read_bytes()).system,
        parse_mmcif((FIXTURES / "mini_protein.cif").read_bytes()).system,
        parse_sdf_v2000((FIXTURES / "ethanol.sdf").read_bytes()).system,
    )
    for system in systems:
        report = analyze_molecular_preparation(system)
        assert report.preparation_assessed is False
        assert report.preparation_ready is False
        assert report.source_digest_available is True
        assert report.source_sha256 == system.provenance.source_sha256
        assert report.parser_observation_self_consistent is True
        assert system.provenance.metadata["parser_observation_schema_id"] == (
            PARSER_OBSERVATION_SCHEMA_ID
        )
        assert attached_parser_observation_sha256_matches(system)
        assert report.missing_atom_count is None
        formal_charge_origins = dict(report.formal_charge_origin_counts)
        assert "unclassified_known" not in formal_charge_origins
        assert "unclassified_unknown" not in formal_charge_origins
        with pytest.raises(PreparationCoverageError):
            require_supported_preparation(system)


def test_mmcif_marker_shape_tamper_invalidates_parser_observation() -> None:
    source = parse_mmcif((FIXTURES / "mini_protein.cif").read_bytes()).system
    atom_metadata = dict(source.atoms[0].metadata)
    mmcif_metadata = dict(atom_metadata["mmcif"])
    mmcif_metadata["atom_site"] = "forged"
    atom_metadata["mmcif"] = mmcif_metadata
    forged = replace(
        source,
        atoms=(replace(source.atoms[0], metadata=atom_metadata), *source.atoms[1:]),
    )
    assert attached_parser_observation_sha256_matches(forged) is False
    report = analyze_molecular_preparation(forged)
    assert report.parser_observation_self_consistent is False
    assert report.formal_charge_origin_counts == (
        ("unclassified_unknown", report.atom_count),
    )


def test_smiles_ingest_report_remains_topology_only_and_fail_closed(
    supported_local_rdkit: None,
) -> None:
    system = parse_smiles(b"CCO").system
    report = analyze_molecular_preparation(system)
    assert report.coordinates_present is False
    assert report.canonical_topology_digest_available is True
    assert "coordinates_missing" in report.blockers
    assert report.hydrogen_origin_counts == (
        ("metadata_observed_adapter_implicit_expanded", 6),
    )
    assert report.adapter_generated_hydrogen_count == 6
    assert report.unknown_hydrogen_origin_count == 0
    assert report.formal_charge_origin_counts == (
        ("metadata_observed_adapter_generated_hydrogen", 6),
        ("metadata_observed_smiles_source_adapter", 3),
    )
    assert (
        "adapter_expanded_hydrogens_not_independently_valence_verified"
        in report.blockers
    )
    with pytest.raises(PreparationCoverageError):
        require_supported_preparation(system)


def test_protonation_and_tautomer_pairs_remain_distinct_but_unassessed(
    supported_local_rdkit: None,
) -> None:
    neutral = parse_smiles(b"N").system
    protonated = parse_smiles(b"[NH4+]").system
    keto = parse_smiles(b"CC(=O)C").system
    enol = parse_smiles(b"CC(O)=C").system

    assert canonical_topology_sha256(neutral) != canonical_topology_sha256(protonated)
    assert canonical_topology_sha256(keto) != canonical_topology_sha256(enol)
    for system in (neutral, protonated, keto, enol):
        report = analyze_molecular_preparation(system)
        assert report.protonation_assessed is False
        assert report.tautomer_assessed is False
        assert "protonation_not_assessed" in report.blockers
        assert "tautomer_not_assessed" in report.blockers


def test_smiles_aromatic_state_is_adapter_observed_not_perception_claim(
    supported_local_rdkit: None,
) -> None:
    report = analyze_molecular_preparation(parse_smiles(b"c1ccccc1").system)
    assert report.observed_aromatic_atom_count == 6
    assert report.observed_aromatic_bond_count == 6
    assert (
        report.aromatic_annotation_origin == "metadata_observed_smiles_adapter_aromatic"
    )
    assert report.aromaticity_perception_assessed is False
    assert "aromaticity_perception_not_assessed" in report.blockers


def test_parser_marker_origins_require_self_consistent_observation_and_roles() -> None:
    source = _system()
    pdb_shaped_without_pedigree = replace(
        source,
        atoms=(
            replace(
                source.atoms[0],
                metadata={
                    "source_record": "HETATM",
                    "formal_charge_source": "pdb_columns_79_80",
                    "formal_charge_interpretation": "explicit",
                },
            ),
            source.atoms[1],
            replace(
                source.atoms[2],
                serial=3,
                metadata={
                    "source_record": "HETATM",
                    "hydrogen_origin": "source",
                    "formal_charge_source": "pdb_columns_79_80",
                    "formal_charge_interpretation": "explicit",
                },
            ),
        ),
        provenance=StructureProvenance(source_format="pdb"),
    )
    report = analyze_molecular_preparation(pdb_shaped_without_pedigree)
    assert report.parser_observation_self_consistent is False
    assert report.hydrogen_origin_counts == (("unknown", 1),)
    assert report.formal_charge_origin_counts == (("unclassified_known", 3),)


def test_smiles_same_format_marker_conflicts_are_downgraded(
    supported_local_rdkit: None,
) -> None:
    source = parse_smiles(b"C").system
    carbon = source.atoms[0]
    hydrogen = source.atoms[1]
    forged = replace(
        source,
        atoms=(
            replace(
                carbon,
                metadata={
                    **dict(carbon.metadata),
                    "formal_charge_source": "manual_hydrogen_expansion_neutral",
                },
            ),
            replace(
                hydrogen,
                metadata={
                    **dict(hydrogen.metadata),
                    "hydrogen_origin": "source",
                },
            ),
            *source.atoms[2:],
        ),
    )
    report = analyze_molecular_preparation(forged)
    assert report.parser_observation_self_consistent is False
    assert report.hydrogen_origin_counts == (("unknown", 4),)
    assert report.formal_charge_origin_counts == (("unclassified_known", 5),)

    nested_marker = replace(
        source,
        atoms=(
            source.atoms[0],
            replace(
                hydrogen,
                metadata={
                    **dict(hydrogen.metadata),
                    "hydrogen_origin": [],
                },
            ),
            *source.atoms[2:],
        ),
    )
    nested_report = analyze_molecular_preparation(nested_marker)
    assert nested_report.parser_observation_self_consistent is False
    assert nested_report.hydrogen_origin_counts == (("unknown", 4),)
    assert nested_report.formal_charge_origin_counts == (("unclassified_known", 5),)

    forged_source_hydrogen = replace(
        source,
        atoms=(
            source.atoms[0],
            replace(
                hydrogen,
                metadata={
                    "source_atom_index": 1,
                    "source_atom_order_preserved": True,
                    "hydrogen_origin": "source",
                    "formal_charge_source": ("smiles_source_via_pinned_rdkit"),
                    "rdkit_chiral_tag": "CHI_UNSPECIFIED",
                },
            ),
            *source.atoms[2:],
        ),
    )
    forged_source_report = analyze_molecular_preparation(forged_source_hydrogen)
    assert forged_source_report.parser_observation_self_consistent is False
    assert forged_source_report.hydrogen_origin_counts == (("unknown", 4),)
    assert forged_source_report.formal_charge_origin_counts == (
        ("unclassified_known", 5),
    )

    bracket_marker_tamper = replace(
        source,
        atoms=(
            source.atoms[0],
            replace(
                hydrogen,
                metadata={
                    **dict(hydrogen.metadata),
                    "hydrogen_origin": "bracket_explicit",
                },
            ),
            *source.atoms[2:],
        ),
        bonds=(
            replace(
                source.bonds[0],
                metadata={
                    **dict(source.bonds[0].metadata),
                    "hydrogen_origin": "bracket_explicit",
                },
            ),
            *source.bonds[1:],
        ),
    )
    bracket_report = analyze_molecular_preparation(bracket_marker_tamper)
    assert attached_parser_observation_sha256_matches(bracket_marker_tamper) is False
    assert bracket_report.parser_observation_self_consistent is False
    assert bracket_report.hydrogen_origin_counts == (("unknown", 4),)

    topology_tamper = replace(
        source,
        atoms=(replace(source.atoms[0], formal_charge=1), *source.atoms[1:]),
    )
    topology_report = analyze_molecular_preparation(topology_tamper)
    assert attached_canonical_topology_sha256_matches(topology_tamper) is False
    assert attached_parser_observation_sha256_matches(topology_tamper) is False
    assert topology_report.parser_observation_self_consistent is False
    assert topology_report.net_formal_charge == 1
    assert topology_report.formal_charge_origin_counts == (("unclassified_known", 5),)

    coverage = dict(source.provenance.metadata["coverage"])
    coverage["generated_hydrogen_count"] = 3
    provenance_metadata = dict(source.provenance.metadata)
    provenance_metadata["coverage"] = coverage
    coverage_tamper = replace(
        source,
        provenance=replace(
            source.provenance,
            metadata=provenance_metadata,
        ),
    )
    assert attached_parser_observation_sha256_matches(coverage_tamper) is False
    assert (
        analyze_molecular_preparation(
            coverage_tamper
        ).parser_observation_self_consistent
        is False
    )

    operations_tamper = replace(
        source,
        provenance=replace(source.provenance, operations=()),
    )
    assert attached_parser_observation_sha256_matches(operations_tamper) is False
    assert (
        analyze_molecular_preparation(
            operations_tamper
        ).parser_observation_self_consistent
        is False
    )

    dependency_metadata = dict(source.provenance.metadata)
    dependency_metadata["rdkit_version"] = "0.0.0"
    dependency_tamper = replace(
        source,
        provenance=replace(
            source.provenance,
            metadata=dependency_metadata,
        ),
    )
    assert attached_parser_observation_sha256_matches(dependency_tamper) is False
    dependency_report = analyze_molecular_preparation(dependency_tamper)
    assert dependency_report.parser_observation_self_consistent is False
    assert dependency_report.hydrogen_origin_counts == (("unknown", 4),)

    float_coverage = dict(source.provenance.metadata["coverage"])
    float_coverage["source_atom_count"] = 1.0
    float_coverage["expanded_atom_count"] = 5.0
    float_coverage["generated_hydrogen_count"] = 4.0
    float_coverage_metadata = dict(source.provenance.metadata)
    float_coverage_metadata["coverage"] = float_coverage
    sealed_float_coverage = attach_parser_observation_digest(
        replace(
            source,
            provenance=replace(
                source.provenance,
                metadata=float_coverage_metadata,
            ),
        )
    )
    float_coverage_report = analyze_molecular_preparation(sealed_float_coverage)
    assert float_coverage_report.parser_observation_self_consistent is True
    assert float_coverage_report.hydrogen_origin_counts == (("unknown", 4),)
    assert float_coverage_report.formal_charge_origin_counts == (
        ("unclassified_known", 5),
    )

    float_bond_ordinals = attach_parser_observation_digest(
        replace(
            source,
            bonds=tuple(
                replace(
                    bond,
                    metadata={
                        **dict(bond.metadata),
                        "hydrogen_ordinal": float(bond.metadata["hydrogen_ordinal"]),
                    },
                )
                if bond.source == "manual_hydrogen_expansion"
                else bond
                for bond in source.bonds
            ),
        )
    )
    float_ordinal_report = analyze_molecular_preparation(float_bond_ordinals)
    assert float_ordinal_report.parser_observation_self_consistent is True
    assert float_ordinal_report.hydrogen_origin_counts == (("unknown", 4),)
    assert float_ordinal_report.formal_charge_origin_counts == (
        ("metadata_observed_smiles_source_adapter", 1),
        ("unclassified_known", 4),
    )


def test_aromatic_metadata_conflicts_are_unclassified_without_crashing(
    supported_local_rdkit: None,
) -> None:
    sdf = parse_sdf_v2000(
        b"aromatic\n  test\n\n  2  1  0  0  0  0  0  0  0  0999 V2000\n"
        b"    0.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        b"    1.4000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
        b"  1  2  4  0  0  0  0\nM  END\n$$$$\n"
    ).system
    inconsistent_sdf = replace(
        sdf,
        bonds=(replace(sdf.bonds[0], order=1.0),),
    )
    assert (
        analyze_molecular_preparation(inconsistent_sdf).aromatic_annotation_origin
        == "unclassified_present"
    )

    smiles = parse_smiles(b"c1ccccc1").system
    inconsistent_smiles = replace(
        smiles,
        atoms=tuple(
            replace(
                atom,
                metadata={**dict(atom.metadata), "source_atom_index": 0},
            )
            if atom.aromatic
            else atom
            for atom in smiles.atoms
        ),
    )
    assert (
        analyze_molecular_preparation(inconsistent_smiles).aromatic_annotation_origin
        == "unclassified_present"
    )

    source = _system()
    invalid_indices = replace(
        source,
        atoms=(
            replace(source.atoms[0], index=5, aromatic=True),
            replace(source.atoms[1], index=6, aromatic=True),
            replace(source.atoms[2], index=7),
        ),
        bonds=(
            replace(
                source.bonds[0],
                atom_i=5,
                atom_j=6,
                order=1.5,
                aromatic=True,
                source="smiles_source",
                metadata={"source_bond_index": 0},
            ),
        ),
        provenance=StructureProvenance(
            source_format="smiles",
            source_sha256="0" * 64,
            parser_name="betelgeuze_strict_smiles",
            parser_version="1.4.0",
        ),
    )
    invalid_report = analyze_molecular_preparation(invalid_indices)
    assert invalid_report.canonical_validation_valid is False
    assert invalid_report.canonical_topology_digest_available is False
    assert invalid_report.aromatic_annotation_origin == "unclassified_present"


def test_report_constructor_rejects_cross_format_origin_tables() -> None:
    sdf = parse_sdf_v2000((FIXTURES / "ethanol.sdf").read_bytes()).system
    report = analyze_molecular_preparation(sdf)
    with pytest.raises(ValueError, match="valid digested canonical state"):
        replace(
            report,
            canonical_topology_sha256=None,
            canonical_topology_digest_available=False,
        )
    with pytest.raises(ValueError, match="incompatible with source_format"):
        replace(
            report,
            formal_charge_origin_counts=(
                ("metadata_observed_pdb_atom_field", report.atom_count),
            ),
        )

    invalid = replace(
        sdf,
        coordinates=torch.full_like(sdf.coordinates, float("nan")),
    )
    invalid_report = analyze_molecular_preparation(invalid)
    with pytest.raises(ValueError, match="valid canonical state"):
        replace(
            invalid_report,
            formal_charge_origin_counts=(
                (
                    "metadata_observed_sdf_v2000_atom_block",
                    invalid_report.atom_count,
                ),
            ),
        )


def test_canonical_model_rejects_non_interoperable_integers_before_hashing() -> None:
    source = _system()
    report = analyze_molecular_preparation(source)
    huge = 10**5000
    with pytest.raises(ValueError, match="formal_charge"):
        replace(source.atoms[0], formal_charge=huge)
    with pytest.raises(ValueError, match="interoperable JSON integer range"):
        replace(source.atoms[0], atom_map=huge)
    with pytest.raises(ValueError, match="interoperable JSON integer range"):
        replace(source.residues[0], sequence_number=huge)
    with pytest.raises(ValueError, match="interoperable JSON integer range"):
        replace(source, metadata={"huge": huge})
    with pytest.raises(ValueError, match="interoperable JSON integer range"):
        replace(report, net_formal_charge=huge)
    with pytest.raises(ValueError, match="interoperable JSON integer range"):
        replace(report, atom_count=huge)


def test_public_api_requires_exact_all_atom_system() -> None:
    with pytest.raises(TypeError, match="system must be an AllAtomSystem"):
        analyze_molecular_preparation(object())  # type: ignore[arg-type]


def test_canonical_tensor_contract_rejects_sparse_and_meta_storage_early() -> None:
    source = _system()
    with pytest.raises(TypeError, match="strided tensor layout"):
        replace(source, coordinates=source.coordinates.to_sparse())
    with pytest.raises(ValueError, match="materialized"):
        replace(
            source,
            coordinates=torch.empty(source.coordinates.shape, device="meta"),
        )
    with pytest.raises(TypeError, match="strided tensor layout"):
        UnitCell(vectors=torch.eye(3).to_sparse())
    with pytest.raises(ValueError, match="materialized"):
        UnitCell(vectors=torch.empty((3, 3), device="meta"))
    with pytest.raises(TypeError, match="exact torch.Tensor"):
        replace(
            source,
            coordinates=torch.nn.Parameter(source.coordinates.clone()),
        )
    with pytest.raises(TypeError, match="float32 or float64"):
        replace(source, coordinates=source.coordinates.to(dtype=torch.float16))
    with pytest.raises(TypeError, match="float32 or float64"):
        UnitCell(vectors=torch.eye(3, dtype=torch.bfloat16))
