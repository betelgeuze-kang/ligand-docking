from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest
import torch

from betelgeuze_engine_v2.molecular import chemistry as chemistry_module
from betelgeuze_engine_v2.molecular import applicability as applicability_module
from betelgeuze_engine_v2.molecular import (
    profile_preparation as profile_preparation_module,
)
from betelgeuze_engine_v2.molecular.applicability import (
    CANONICAL_INGEST_APPLICABILITY_SCHEMA_ID,
    CANONICAL_INGEST_CONSTRAINT_CODES,
    EXPLICIT_NEUTRAL_ACYCLIC_SATURATED_HYDROCARBON_PROFILE_ID,
    PARAMETERABILITY_STATUS,
    SOURCE_AUTHENTICATION_STATUS,
    analyze_canonical_ingest_applicability,
)
from betelgeuze_engine_v2.molecular.chemistry import (
    CHEMISTRY_COVERAGE_SCHEMA_VERSION,
    ChemistryCoverageLimitError,
)
from betelgeuze_engine_v2.molecular.pdb_mmcif import parse_pdb
from betelgeuze_engine_v2.molecular.preparation import (
    PREPARATION_POLICY_ID,
    PREPARATION_REPORT_SCHEMA_VERSION,
    PreparationCoverageLimitError,
)
from betelgeuze_engine_v2.molecular import preparation as preparation_module
from betelgeuze_engine_v2.molecular.profile_preparation import (
    PROFILE_LOCAL_PREPARATION_CLAIM_SCOPE,
    PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_ID,
    PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_VERSION,
    ProfileLocalPreparationEvidenceError,
    ProfileLocalPreparationEvidenceReport,
    analyze_profile_local_preparation_evidence,
    require_profile_local_preparation_evidence,
)
from betelgeuze_engine_v2.molecular.sdf_v2000 import parse_sdf_v2000
from betelgeuze_engine_v2.molecular.serialization import (
    canonical_all_atom_systems_equal,
    deserialize_all_atom_system,
    serialize_all_atom_system,
)
from betelgeuze_engine_v2.molecular.topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
)
from betelgeuze_engine_v2.molecular import smiles as smiles_module
from betelgeuze_engine_v2.molecular.smiles import parse_smiles
from betelgeuze_engine_v2.molecular.models import AllAtomSystem


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
METHANE = FIXTURES / "v2_1_ingest_corpus" / "methane_explicit_h.sdf"
C13_METHANE = FIXTURES / "v2_1_ingest_corpus" / "methane_c13_explicit_h.sdf"
ETHANOL = FIXTURES / "tier_beta" / "ethanol.sdf"
LINEAR_ALKANE_FIXTURES = FIXTURES / "v2_2_linear_alkane"
ETHANE = LINEAR_ALKANE_FIXTURES / "ethane_explicit_h.sdf"
PROPANE = LINEAR_ALKANE_FIXTURES / "propane_explicit_h.sdf"
N_BUTANE = LINEAR_ALKANE_FIXTURES / "n_butane_explicit_h.sdf"
ISOBUTANE = LINEAR_ALKANE_FIXTURES / "isobutane_branched_explicit_h.sdf"
CYCLOBUTANE = LINEAR_ALKANE_FIXTURES / "cyclobutane_explicit_h.sdf"
ETHANE_MISSING_H = LINEAR_ALKANE_FIXTURES / "ethane_missing_h.sdf"
MINI_PDB = FIXTURES / "tier_beta" / "mini_protein.pdb"

SELECTED_SUPPORTED_PROFILE_SOURCES = (
    (METHANE, "sdf_v2000_methane_explicit_h"),
    (ETHANE, "sdf_v2000_ethane_explicit_h"),
    (PROPANE, "sdf_v2000_propane_explicit_h"),
    (N_BUTANE, "sdf_v2000_n_butane_explicit_h"),
    (ISOBUTANE, "sdf_v2000_isobutane_branched_explicit_h"),
)
SELECTED_PROFILE_BOUNDARY_SOURCES = (
    (
        CYCLOBUTANE,
        "sdf_v2000_cyclobutane_explicit_h",
        ("acyclic_graph",),
        "satisfied_for_declared_canonical_graph",
        "profile_requirements_not_satisfied",
        "aromaticity_profile_requirement_not_satisfied",
    ),
    (
        ETHANE_MISSING_H,
        "sdf_v2000_ethane_missing_h",
        ("explicit_valence_closed",),
        "not_satisfied",
        "not_applicable_to_acyclic_single_bond_profile",
        "profile_hydrogen_valence_not_satisfied",
    ),
)
PROFILE_LOCAL_NONPROMOTION_BLOCKER_TAIL = (
    "profile_local_evidence_is_not_global_preparation",
    "whole_molecule_atom_completeness_unassessed",
    "hydrogen_completeness_unassessed",
    "polymer_missing_residue_completeness_unassessed",
    "protonation_environment_unassessed",
    "formal_charge_assignment_unassessed",
    "tautomer_selection_unassessed",
    "aromaticity_perception_unassessed",
    "stereochemistry_assignment_unassessed",
    "electronic_state_unassessed",
    "geometry_quality_unassessed",
    "contextual_roles_unassessed",
    "source_digest_is_not_authentication",
    "normalization_not_attempted",
    "completion_not_attempted",
    "parameterability_not_assessed",
    "preparation_assessment_incomplete",
    "preparation_not_ready",
    "simulation_not_authorized",
    "claim_not_authorized",
)


def _methane_system():
    return parse_sdf_v2000(
        METHANE.read_bytes(),
        source_id="sdf_v2000_methane_explicit_h",
    ).system


def _assert_no_global_preparation_promotion(
    report: ProfileLocalPreparationEvidenceReport,
) -> None:
    assert (
        report.normalization_attempted,
        report.completion_attempted,
        report.preparation_assessment_complete,
        report.preparation_assessed,
        report.preparation_ready,
        report.parameterability_assessed,
        report.parameterizable,
        report.simulation_ready,
        report.claim_safe,
    ) == (False,) * 9


def _assert_required_evidence_rejection_preserves_report(
    system: AllAtomSystem,
    monkeypatch: pytest.MonkeyPatch,
) -> ProfileLocalPreparationEvidenceError:
    expected = analyze_profile_local_preparation_evidence(system)
    serialized_before = serialize_all_atom_system(system)
    captured_reports: list[ProfileLocalPreparationEvidenceReport] = []
    original_analyze = (
        profile_preparation_module.analyze_profile_local_preparation_evidence
    )

    def capture_report(
        candidate: AllAtomSystem,
    ) -> ProfileLocalPreparationEvidenceReport:
        report = original_analyze(candidate)
        captured_reports.append(report)
        return report

    monkeypatch.setattr(
        profile_preparation_module,
        "analyze_profile_local_preparation_evidence",
        capture_report,
    )

    with pytest.raises(ProfileLocalPreparationEvidenceError) as exc_info:
        require_profile_local_preparation_evidence(system)

    error = exc_info.value
    assert len(captured_reports) == 1
    assert error.report is captured_reports[0]
    assert type(error.report) is ProfileLocalPreparationEvidenceReport
    assert error.report.to_dict() == expected.to_dict()
    assert error.report.report_sha256 == expected.report_sha256
    assert error.status == error.report.profile_local_evidence_status
    assert error.status == expected.profile_local_evidence_status == "not_satisfied"
    assert error.blockers == expected.blockers
    assert error.report.profile_local_evidence_satisfied is False
    _assert_no_global_preparation_promotion(error.report)
    assert serialize_all_atom_system(system) == serialized_before
    return error


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


def test_explicit_h_methane_satisfies_only_profile_local_evidence() -> None:
    system = _methane_system()
    report = analyze_profile_local_preparation_evidence(system)
    payload = report.to_dict()

    assert payload["schema_id"] == (PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_ID)
    assert (
        payload["schema_version"]
        == (PROFILE_LOCAL_PREPARATION_EVIDENCE_SCHEMA_VERSION)
        == "1.0.0"
    )
    assert report.profile_id == (
        EXPLICIT_NEUTRAL_ACYCLIC_SATURATED_HYDROCARBON_PROFILE_ID
    )
    assert report.claim_scope == PROFILE_LOCAL_PREPARATION_CLAIM_SCOPE
    assert report.canonical_topology_schema_id == CANONICAL_TOPOLOGY_SCHEMA_ID
    assert report.chemistry_coverage_schema_version == (
        CHEMISTRY_COVERAGE_SCHEMA_VERSION
    )
    assert report.preparation_report_schema_version == (
        PREPARATION_REPORT_SCHEMA_VERSION
    )
    assert report.preparation_policy_id == PREPARATION_POLICY_ID
    assert report.applicability_schema_id == (CANONICAL_INGEST_APPLICABILITY_SCHEMA_ID)
    assert report.source_authentication_status == SOURCE_AUTHENTICATION_STATUS

    assert report.canonical_ingest_status == "supported"
    assert report.canonical_ingest_supported is True
    assert report.applicability_constraint_results == tuple(
        (code, True) for code in CANONICAL_INGEST_CONSTRAINT_CODES
    )
    assert report.applicability_failed_constraint_codes == ()
    assert report.atom_count == 5
    assert report.residue_count == 1
    assert report.formal_charge_origin_counts == (
        ("metadata_observed_sdf_v2000_atom_block", 5),
    )
    assert report.source_observed_formal_charge_count == 5
    assert report.entity_type_counts == (("non_polymer", 1),)
    assert report.source_hydrogen_inventory_status == (
        "complete_relative_to_parsed_source"
    )
    assert report.profile_hydrogen_valence_status == (
        "satisfied_for_declared_canonical_graph"
    )
    assert report.formal_charge_observation_status == (
        "source_observed_known_zero_not_assigned"
    )
    assert report.aromaticity_requirement_status == (
        "not_applicable_to_acyclic_single_bond_profile"
    )
    assert report.polymer_missing_residue_status == (
        "not_applicable_to_single_nonpolymer_source"
    )
    assert report.profile_local_evidence_status == "satisfied"
    assert report.profile_local_evidence_satisfied is True

    assert report.normalization_action == "none"
    assert report.whole_molecule_atom_completeness_status == "unassessed"
    assert report.hydrogen_completeness_status == "unassessed"
    assert report.protonation_status == "unassessed"
    assert report.formal_charge_assignment_status == "unassessed"
    assert report.tautomer_status == "unassessed"
    assert report.aromaticity_perception_status == "unassessed"
    assert report.stereochemistry_assignment_status == "unassessed"
    assert report.electronic_state_status == "unassessed"
    assert report.geometry_quality_status == "unassessed"
    assert report.contextual_role_status == "unassessed"
    assert report.parameterability_status == PARAMETERABILITY_STATUS
    assert report.normalization_attempted is False
    assert report.completion_attempted is False
    assert report.preparation_assessment_complete is False
    assert report.preparation_assessed is False
    assert report.preparation_ready is False
    assert report.parameterability_assessed is False
    assert report.parameterizable is False
    assert report.simulation_ready is False
    assert report.claim_safe is False
    assert report.blockers == (
        "profile_local_evidence_is_not_global_preparation",
        "whole_molecule_atom_completeness_unassessed",
        "hydrogen_completeness_unassessed",
        "protonation_environment_unassessed",
        "formal_charge_assignment_unassessed",
        "tautomer_selection_unassessed",
        "aromaticity_perception_unassessed",
        "stereochemistry_assignment_unassessed",
        "electronic_state_unassessed",
        "geometry_quality_unassessed",
        "contextual_roles_unassessed",
        "source_digest_is_not_authentication",
        "normalization_not_attempted",
        "completion_not_attempted",
        "parameterability_not_assessed",
        "preparation_assessment_incomplete",
        "preparation_not_ready",
        "simulation_not_authorized",
        "claim_not_authorized",
    )

    assert report.canonical_topology_sha256 == (
        "cb851cc2c410436f6e21127666a69c54020335ddb988570d667744e07f0604dc"
    )
    assert report.chemistry_coverage_report_sha256 == (
        "e22dc5b37884345e3c631c3a3e15efad81f19a28610df2012ba882fa13b58cb7"
    )
    assert report.preparation_report_sha256 == (
        "c224375eb262323318af3719dad6a64b09c39033d93d9a580e43a228300ecb34"
    )
    assert report.applicability_report_sha256 == (
        "45d4ba5326a7d65eaecbc834c5002aa93aac7c4c860cbf55e70ea7f8fa5bb32c"
    )
    assert report.report_sha256 == (
        "703d68f480d87b828463777342b9cfdf895983f2bddeb8b64f30237afc27acdc"
    )
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert report.matches_system(system) is True


def test_snapshot_round_trip_preserves_report_and_hash_deterministically() -> None:
    source = _methane_system()
    restored = deserialize_all_atom_system(serialize_all_atom_system(source))

    assert canonical_all_atom_systems_equal(source, restored)
    source_report = analyze_profile_local_preparation_evidence(source)
    restored_report = analyze_profile_local_preparation_evidence(restored)
    repeated_report = analyze_profile_local_preparation_evidence(source)
    assert restored_report.to_dict() == source_report.to_dict()
    assert repeated_report.to_dict() == source_report.to_dict()
    assert restored_report.report_sha256 == source_report.report_sha256


def test_valid_out_of_profile_sources_remain_not_satisfied_and_unassessed() -> None:
    ethanol = parse_sdf_v2000(
        ETHANOL.read_bytes(),
        source_id="sdf_v2000_ethanol",
    ).system
    ethanol_report = analyze_profile_local_preparation_evidence(ethanol)

    assert ethanol_report.canonical_ingest_status == "unsupported"
    assert ethanol_report.canonical_ingest_supported is False
    assert ethanol_report.applicability_failed_constraint_codes == (
        "elements_h_c_only",
        "explicit_valence_closed",
    )
    assert ethanol_report.source_hydrogen_inventory_status == (
        "complete_relative_to_parsed_source"
    )
    assert ethanol_report.profile_hydrogen_valence_status == "not_satisfied"
    assert ethanol_report.formal_charge_observation_status == (
        "source_observed_known_zero_not_assigned"
    )
    assert ethanol_report.profile_local_evidence_status == "not_satisfied"
    assert ethanol_report.profile_local_evidence_satisfied is False
    assert ethanol_report.polymer_missing_residue_status == "unassessed"
    assert ethanol_report.whole_molecule_atom_completeness_status == "unassessed"
    assert ethanol_report.preparation_ready is False
    assert "profile_local_preparation_evidence_not_satisfied" in (
        ethanol_report.blockers
    )
    assert "polymer_missing_residue_completeness_unassessed" in (
        ethanol_report.blockers
    )

    pdb = parse_pdb(
        MINI_PDB.read_bytes(),
        source_id="pdb_mini_protein",
    ).system
    pdb_report = analyze_profile_local_preparation_evidence(pdb)
    assert pdb_report.canonical_ingest_status == "unsupported"
    assert pdb_report.profile_local_evidence_status == "not_satisfied"
    assert pdb_report.formal_charge_observation_status == "not_satisfied"
    assert pdb_report.aromaticity_requirement_status == (
        "profile_requirements_not_satisfied"
    )
    assert pdb_report.source_observed_formal_charge_count == 0
    assert pdb_report.preparation_assessed is False
    assert pdb_report.claim_safe is False


def test_source_observed_nonzero_charge_is_not_a_charge_assignment() -> None:
    charged_bytes = METHANE.read_bytes().replace(
        b"M  END\n",
        b"M  CHG  1   1   1\nM  END\n",
        1,
    )
    charged = parse_sdf_v2000(
        charged_bytes,
        source_id="source-charged-methane",
    ).system
    report = analyze_profile_local_preparation_evidence(charged)

    assert report.parser_observation_self_consistent is True
    assert report.canonical_ingest_status == "unsupported"
    assert report.applicability_failed_constraint_codes == (
        "formal_charges_known_zero",
    )
    assert report.source_observed_formal_charge_count == report.atom_count - 1
    assert report.formal_charge_origin_counts == (
        ("metadata_observed_sdf_v2000_atom_block", 4),
        ("metadata_observed_sdf_v2000_m_chg", 1),
    )
    assert report.formal_charge_observation_status == "not_satisfied"
    assert report.formal_charge_assignment_status == "unassessed"
    assert report.profile_local_evidence_satisfied is False
    assert report.preparation_ready is False


def test_smiles_adapter_hydrogen_and_charge_origins_do_not_promote_evidence(
    supported_local_rdkit: None,
) -> None:
    system = parse_smiles(b"C", source_id="adapter-methane").system
    report = analyze_profile_local_preparation_evidence(system)

    assert report.canonical_ingest_status == "unsupported"
    assert report.applicability_failed_constraint_codes == (
        "hydrogens_source_observed",
    )
    assert report.source_observed_hydrogen_count == 0
    assert report.adapter_generated_hydrogen_count == 4
    assert report.source_hydrogen_inventory_status == "not_satisfied"
    assert report.profile_hydrogen_valence_status == (
        "satisfied_for_declared_canonical_graph"
    )
    assert report.formal_charge_observation_status == (
        "known_zero_origin_not_source_observed"
    )
    assert report.profile_local_evidence_satisfied is False
    assert report.hydrogen_completeness_status == "unassessed"


def test_invalid_canonical_state_yields_invalid_local_evidence() -> None:
    source = _methane_system()
    invalid = replace(
        source,
        coordinates=torch.tensor(
            [
                [
                    [float("nan"), 0.0, 0.0],
                    *([[0.0, 0.0, 0.0]] * 4),
                ]
            ],
            dtype=torch.float64,
        ),
    )
    report = analyze_profile_local_preparation_evidence(invalid)

    assert report.canonical_ingest_status == "invalid"
    assert report.canonical_ingest_supported is False
    assert "canonical_state_valid" in report.applicability_failed_constraint_codes
    assert report.profile_local_evidence_status == "invalid"
    assert report.profile_local_evidence_satisfied is False
    assert report.source_hydrogen_inventory_status == "invalid_source_binding"
    assert report.profile_hydrogen_valence_status == "invalid_canonical_state"
    assert report.formal_charge_observation_status == "invalid_source_binding"
    assert report.aromaticity_requirement_status == "invalid_canonical_state"
    assert report.preparation_ready is False
    assert report.simulation_ready is False
    assert report.blockers[0] == "profile_local_preparation_evidence_invalid"


def test_invalid_stereo_labels_return_invalid_evidence_instead_of_raising() -> None:
    source = _methane_system()
    variants = (
        replace(
            source,
            atoms=(replace(source.atoms[0], stereo="BOGUS"), *source.atoms[1:]),
        ),
        replace(
            source,
            bonds=(replace(source.bonds[0], stereo="BOGUS"), *source.bonds[1:]),
        ),
    )

    for invalid in variants:
        report = analyze_profile_local_preparation_evidence(invalid)
        assert report.canonical_state_valid is False
        assert report.canonical_ingest_status == "invalid"
        assert report.profile_local_evidence_status == "invalid"
        assert report.profile_local_evidence_satisfied is False


def test_report_is_source_and_topology_bound_but_ignores_claim_metadata() -> None:
    source = _methane_system()
    baseline = analyze_profile_local_preparation_evidence(source)

    forged_claim_metadata = replace(
        source,
        metadata={
            **source.metadata,
            "profile_local_evidence_satisfied": True,
            "preparation_ready": True,
            "claim_safe": True,
        },
    )
    assert (
        analyze_profile_local_preparation_evidence(forged_claim_metadata).to_dict()
        == baseline.to_dict()
    )
    assert baseline.matches_system(forged_claim_metadata) is True

    changed_source = replace(
        source,
        provenance=replace(source.provenance, source_sha256="0" * 64),
    )
    changed_source_report = analyze_profile_local_preparation_evidence(changed_source)
    assert baseline.matches_system(changed_source) is False
    assert changed_source_report.source_sha256 == "0" * 64
    assert changed_source_report.applicability_report_sha256 != (
        baseline.applicability_report_sha256
    )
    assert changed_source_report.report_sha256 != baseline.report_sha256
    assert changed_source_report.canonical_ingest_status == "invalid"

    changed_topology = replace(
        source,
        atoms=(replace(source.atoms[0], formal_charge=1), *source.atoms[1:]),
    )
    changed_topology_report = analyze_profile_local_preparation_evidence(
        changed_topology
    )
    assert baseline.matches_system(changed_topology) is False
    assert changed_topology_report.canonical_topology_sha256 != (
        baseline.canonical_topology_sha256
    )
    assert changed_topology_report.report_sha256 != baseline.report_sha256
    assert changed_topology_report.canonical_ingest_status == "invalid"

    malformed_source_digest = replace(
        source,
        provenance=replace(source.provenance, source_sha256="NOT-A-SHA256"),
    )
    malformed_report = analyze_profile_local_preparation_evidence(
        malformed_source_digest
    )
    assert malformed_report.canonical_ingest_status == "invalid"
    assert malformed_report.profile_local_evidence_status == "invalid"
    assert malformed_report.source_sha256 is None
    assert malformed_report.source_digest_available is False


def test_constructor_invariants_reject_forged_evidence_and_promotions() -> None:
    report = analyze_profile_local_preparation_evidence(_methane_system())

    with pytest.raises(TypeError, match="unexpected keyword"):
        replace(report, preparation_ready=True)
    with pytest.raises(TypeError, match="unexpected keyword"):
        replace(report, parameterability_assessed=True)
    with pytest.raises(TypeError, match="unexpected keyword"):
        replace(report, simulation_ready=True)
    with pytest.raises(TypeError, match="unexpected keyword"):
        replace(report, claim_safe=True)
    with pytest.raises(TypeError, match="unexpected keyword"):
        replace(report, profile_local_evidence_satisfied=False)
    with pytest.raises(TypeError, match="unexpected keyword"):
        replace(report, blockers=())

    assert ProfileLocalPreparationEvidenceReport(_methane_system()).to_dict() == (
        report.to_dict()
    )
    with pytest.raises(TypeError, match="system must be an AllAtomSystem"):
        ProfileLocalPreparationEvidenceReport("not-a-system")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="unexpected keyword"):
        ProfileLocalPreparationEvidenceReport(
            applicability_report=report.applicability_report,
            preparation_report=report.preparation_report,
        )

    with pytest.raises(ValueError, match="identity or counts"):
        replace(
            report.applicability_report,
            system_schema_id="bogus.schema/9.9.9",
        )
    with pytest.raises(ValueError, match="identity or counts"):
        replace(
            report.applicability_report,
            canonical_topology_sha256=None,
            canonical_topology_digest_available=False,
        )
    with pytest.raises(ValueError, match="element counts.*atom_count"):
        replace(report.applicability_report, atom_count=0)
    with pytest.raises(ValueError, match="incompatible with source_format"):
        replace(
            report.preparation_report,
            formal_charge_origin_counts=(("metadata_observed_pdb_atom_field", 5),),
        )
    forged_digest = replace(
        report.applicability_report,
        canonical_topology_sha256="0" * 64,
    )
    with pytest.raises(TypeError, match="unexpected keyword"):
        replace(report, applicability_report=forged_digest)

    assert analyze_canonical_ingest_applicability(_methane_system()) == (
        report.applicability_report
    )


@pytest.mark.parametrize(
    ("limit_name", "limit", "expected_code"),
    [
        ("MAX_CHEMISTRY_AUDIT_ATOMS", 4, "atom_limit_exceeded"),
        ("MAX_CHEMISTRY_AUDIT_BONDS", 3, "bond_limit_exceeded"),
    ],
)
def test_profile_evidence_inherits_chemistry_resource_caps(
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
    limit: int,
    expected_code: str,
) -> None:
    monkeypatch.setattr(chemistry_module, limit_name, limit)

    with pytest.raises(ChemistryCoverageLimitError) as exc_info:
        analyze_profile_local_preparation_evidence(_methane_system())
    assert exc_info.value.code == expected_code


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
def test_profile_evidence_propagates_preparation_resource_limits(
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
    count_attribute: str,
    expected_code: str,
) -> None:
    system = _methane_system()
    monkeypatch.setattr(
        preparation_module,
        limit_name,
        len(getattr(system, count_attribute)) - 1,
    )

    def forbidden_chemistry_work(*args: object, **kwargs: object) -> object:
        pytest.fail("preparation resource preflight must run before chemistry audit")

    monkeypatch.setattr(
        applicability_module,
        "analyze_canonical_chemistry",
        forbidden_chemistry_work,
    )

    with pytest.raises(PreparationCoverageLimitError) as exc_info:
        analyze_profile_local_preparation_evidence(system)
    assert exc_info.value.code == expected_code


def test_require_profile_local_evidence_returns_fresh_exact_satisfied_report() -> None:
    system = _methane_system()
    serialized_before = serialize_all_atom_system(system)
    expected = analyze_profile_local_preparation_evidence(system)

    first = require_profile_local_preparation_evidence(system)
    second = require_profile_local_preparation_evidence(system)

    assert type(first) is ProfileLocalPreparationEvidenceReport
    assert type(second) is ProfileLocalPreparationEvidenceReport
    assert first is not expected
    assert second is not first
    assert first.to_dict() == second.to_dict() == expected.to_dict()
    assert first.report_sha256 == second.report_sha256 == expected.report_sha256
    assert first.profile_local_evidence_status == "satisfied"
    assert first.profile_local_evidence_satisfied is True
    _assert_no_global_preparation_promotion(first)
    _assert_no_global_preparation_promotion(second)
    assert serialize_all_atom_system(system) == serialized_before


@pytest.mark.parametrize(("path", "source_id"), SELECTED_SUPPORTED_PROFILE_SOURCES)
def test_require_profile_local_evidence_accepts_selected_supported_rows(
    path: Path,
    source_id: str,
) -> None:
    system = parse_sdf_v2000(path.read_bytes(), source_id=source_id).system

    report = require_profile_local_preparation_evidence(system)

    assert type(report) is ProfileLocalPreparationEvidenceReport
    assert report.canonical_ingest_status == "supported"
    assert report.canonical_ingest_supported is True
    assert report.applicability_failed_constraint_codes == ()
    assert report.profile_local_evidence_status == "satisfied"
    assert report.profile_local_evidence_satisfied is True
    _assert_no_global_preparation_promotion(report)


@pytest.mark.parametrize(
    ("path", "source_id"),
    [
        (ETHANOL, "sdf_v2000_ethanol"),
        (C13_METHANE, "sdf_v2000_methane_c13_explicit_h"),
    ],
)
def test_require_profile_local_evidence_rejects_out_of_profile_sdf_sources(
    monkeypatch: pytest.MonkeyPatch,
    path: Path,
    source_id: str,
) -> None:
    system = parse_sdf_v2000(path.read_bytes(), source_id=source_id).system

    _assert_required_evidence_rejection_preserves_report(system, monkeypatch)


@pytest.mark.parametrize(
    (
        "path",
        "source_id",
        "failed_constraints",
        "valence_status",
        "aromaticity_status",
        "profile_blocker",
    ),
    SELECTED_PROFILE_BOUNDARY_SOURCES,
)
def test_require_profile_local_evidence_rejects_selected_boundary_rows_exactly(
    monkeypatch: pytest.MonkeyPatch,
    path: Path,
    source_id: str,
    failed_constraints: tuple[str, ...],
    valence_status: str,
    aromaticity_status: str,
    profile_blocker: str,
) -> None:
    system = parse_sdf_v2000(path.read_bytes(), source_id=source_id).system

    error = _assert_required_evidence_rejection_preserves_report(
        system,
        monkeypatch,
    )

    assert error.report.applicability_failed_constraint_codes == (failed_constraints)
    assert error.report.source_hydrogen_inventory_status == (
        "complete_relative_to_parsed_source"
    )
    assert error.report.profile_hydrogen_valence_status == valence_status
    assert error.report.aromaticity_requirement_status == aromaticity_status
    assert error.blockers == (
        "profile_local_preparation_evidence_not_satisfied",
        profile_blocker,
        *PROFILE_LOCAL_NONPROMOTION_BLOCKER_TAIL,
    )


def test_require_profile_local_evidence_rejects_smiles_adapter_hydrogens(
    monkeypatch: pytest.MonkeyPatch,
    supported_local_rdkit: None,
) -> None:
    system = parse_smiles(b"C", source_id="adapter-generated-hydrogen-methane").system

    error = _assert_required_evidence_rejection_preserves_report(
        system,
        monkeypatch,
    )
    assert error.report.source_observed_hydrogen_count == 0
    assert error.report.adapter_generated_hydrogen_count == 4
    assert "hydrogens_source_observed" in (
        error.report.applicability_failed_constraint_codes
    )


def test_profile_local_evidence_error_message_is_bounded_and_source_free() -> None:
    raw_marker = "RAW-SOURCE-MARKER-MUST-NOT-LEAK"
    source_id = "SOURCE-ID-MARKER-MUST-NOT-LEAK"
    raw_source = ETHANOL.read_bytes().replace(
        b"ethanol",
        raw_marker.encode("ascii"),
        1,
    )
    system = parse_sdf_v2000(raw_source, source_id=source_id).system

    with pytest.raises(ProfileLocalPreparationEvidenceError) as exc_info:
        require_profile_local_preparation_evidence(system)

    message = str(exc_info.value)
    rendered = f"{type(exc_info.value).__name__}: {message}"
    assert len(message.encode("utf-8")) <= 512
    assert raw_marker not in rendered
    assert source_id not in rendered
    assert raw_source.decode("ascii") not in rendered


def test_require_profile_local_evidence_rejects_wrong_input_type() -> None:
    with pytest.raises(TypeError, match="system must be an AllAtomSystem"):
        require_profile_local_preparation_evidence(object())  # type: ignore[arg-type]


def test_require_profile_local_evidence_propagates_preparation_limit_before_chemistry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system = _methane_system()
    monkeypatch.setattr(
        preparation_module,
        "MAX_PREPARATION_AUDIT_ATOMS",
        len(system.atoms) - 1,
    )

    def forbidden_chemistry_work(*args: object, **kwargs: object) -> object:
        pytest.fail("preparation resource preflight must run before chemistry audit")

    monkeypatch.setattr(
        applicability_module,
        "analyze_canonical_chemistry",
        forbidden_chemistry_work,
    )

    with pytest.raises(PreparationCoverageLimitError) as exc_info:
        require_profile_local_preparation_evidence(system)
    assert type(exc_info.value) is PreparationCoverageLimitError
    assert exc_info.value.code == "atom_limit_exceeded"


def test_profile_local_evidence_error_requires_an_exact_report() -> None:
    class DerivedReport(ProfileLocalPreparationEvidenceReport):
        pass

    derived = DerivedReport(_methane_system())

    with pytest.raises(
        TypeError,
        match="report must be a ProfileLocalPreparationEvidenceReport",
    ):
        ProfileLocalPreparationEvidenceError(derived)
    with pytest.raises(
        TypeError,
        match="report must be a ProfileLocalPreparationEvidenceReport",
    ):
        ProfileLocalPreparationEvidenceError(object())  # type: ignore[arg-type]


def test_profile_local_evidence_error_rejects_a_satisfied_report() -> None:
    report = analyze_profile_local_preparation_evidence(_methane_system())
    assert report.profile_local_evidence_satisfied is True

    with pytest.raises(
        ValueError,
        match="report must not have satisfied profile-local evidence",
    ):
        ProfileLocalPreparationEvidenceError(report)


@pytest.mark.parametrize("analyzer_result_kind", ["object", "derived"])
def test_require_profile_local_evidence_rejects_nonexact_analyzer_result(
    monkeypatch: pytest.MonkeyPatch,
    analyzer_result_kind: str,
) -> None:
    class DerivedReport(ProfileLocalPreparationEvidenceReport):
        pass

    analyzer_result = (
        object()
        if analyzer_result_kind == "object"
        else DerivedReport(_methane_system())
    )
    monkeypatch.setattr(
        profile_preparation_module,
        "analyze_profile_local_preparation_evidence",
        lambda system: analyzer_result,
    )

    with pytest.raises(
        TypeError,
        match="analyzer must return a ProfileLocalPreparationEvidenceReport",
    ):
        require_profile_local_preparation_evidence(_methane_system())
