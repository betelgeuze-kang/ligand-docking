from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from betelgeuze_engine_v2.molecular import preparation as preparation_module
from betelgeuze_engine_v2.molecular.applicability import (
    CanonicalIngestApplicabilityError,
    analyze_canonical_ingest_applicability,
    require_canonical_ingest_applicable,
)
from betelgeuze_engine_v2.molecular.mmcif_nonpoly_component_topology import (
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_NAME,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID,
    MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_VERSION,
    parse_mmcif_nonpoly_component_topology,
)
from betelgeuze_engine_v2.molecular.observation import (
    attach_parser_observation_digest,
    attached_parser_observation_sha256_matches,
)
from betelgeuze_engine_v2.molecular.preparation import (
    analyze_molecular_preparation,
)
from betelgeuze_engine_v2.molecular.profile_preparation import (
    ProfileLocalPreparationEvidenceError,
    analyze_profile_local_preparation_evidence,
    require_profile_local_preparation_evidence,
)
from betelgeuze_engine_v2.molecular.topology import (
    attached_canonical_topology_sha256_matches,
)


FIXTURES = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "v2_1_mmcif_nonpoly_component_topology"
)


def _system(fixture_name: str):
    return parse_mmcif_nonpoly_component_topology(
        (FIXTURES / fixture_name).read_bytes(),
        source_id=fixture_name,
    ).system


def test_single_methane_reaches_existing_local_hydrocarbon_gates() -> None:
    ingest = parse_mmcif_nonpoly_component_topology(
        (FIXTURES / "single_methane_complete.cif").read_bytes(),
        source_id="single_methane_complete",
    )
    system = ingest.system
    preparation = analyze_molecular_preparation(system)
    applicability = require_canonical_ingest_applicable(system)
    local = require_profile_local_preparation_evidence(system)

    assert MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID == (
        "betelgeuze.mmcif_nonpoly_component_topology_parser/1.0.0"
    )
    assert preparation_module._MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_NAME == (
        MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_NAME
    )
    assert preparation_module._MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_VERSION == (
        MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_VERSION
    )
    assert (
        preparation_module._MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID
        == MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    assert attached_canonical_topology_sha256_matches(system) is True
    assert attached_parser_observation_sha256_matches(system) is True
    assert preparation.parser_pedigree_id == (
        MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    assert preparation.parser_observation_self_consistent is True
    assert preparation.hydrogen_origin_counts == (
        ("metadata_observed_parser_source", 4),
    )
    assert preparation.formal_charge_origin_counts == (
        ("metadata_observed_mmcif_chem_comp_atom", 5),
    )
    assert applicability.canonical_ingest_status == "supported"
    assert applicability.failed_constraint_codes == ()
    assert local.profile_local_evidence_status == "satisfied"
    assert local.formal_charge_observation_status == (
        "source_observed_known_zero_not_assigned"
    )
    assert local.source_observed_formal_charge_count == 5
    assert local.preparation_ready is False
    assert local.parameterability_assessed is False
    assert local.parameterizable is False
    assert local.simulation_ready is False
    assert local.claim_safe is False

    document = ingest.to_dict()
    assert document["parser_pedigree_id"] == (
        MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    assert document["attached_canonical_topology_digest_self_consistent"] is True
    assert document["attached_parser_observation_digest_self_consistent"] is True
    assert (
        document["augmented_system_parser_observation_sha256"]
        == (system.provenance.metadata["parser_observation_sha256"])
    )
    assert "coverage" not in system.provenance.metadata
    carrier_coverage = system.provenance.metadata["carrier_coverage"]
    assert carrier_coverage["bond_count"] == 0
    assert carrier_coverage["canonical_topology_sha256"] == (
        ingest.carrier_ingest.base_topology_sha256
    )
    mmcif_metadata = system.metadata["mmcif"]
    assert "source_missingness" not in mmcif_metadata
    assert "source_reported_missingness" not in mmcif_metadata
    assert mmcif_metadata["carrier_evidence_semantics"] == (
        "preserved_identity_carrier_only_not_augmented_topology_evidence"
    )


@pytest.mark.parametrize(
    ("fixture_name", "expected_failed_constraint"),
    [
        ("aromatic_benzene_complete.cif", "aromaticity_absent"),
        ("charged_ammonium_complete.cif", "formal_charges_known_zero"),
        ("two_water_instances_complete.cif", "single_component"),
        ("mixed_polymer_methane_complete.cif", "single_component"),
    ],
)
def test_other_component_topology_fixtures_remain_profile_nonpositive(
    fixture_name: str,
    expected_failed_constraint: str,
) -> None:
    system = _system(fixture_name)
    preparation = analyze_molecular_preparation(system)
    applicability = analyze_canonical_ingest_applicability(system)
    local = analyze_profile_local_preparation_evidence(system)

    assert preparation.parser_pedigree_id == (
        MMCIF_NONPOLY_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    assert preparation.parser_observation_self_consistent is True
    assert applicability.canonical_ingest_status == "unsupported"
    assert expected_failed_constraint in applicability.failed_constraint_codes
    assert local.profile_local_evidence_status == "not_satisfied"
    assert local.profile_local_evidence_satisfied is False
    with pytest.raises(CanonicalIngestApplicabilityError):
        require_canonical_ingest_applicable(system)
    with pytest.raises(ProfileLocalPreparationEvidenceError):
        require_profile_local_preparation_evidence(system)


def test_atom_site_charge_crosscheck_uses_the_same_exact_template_origin() -> None:
    source = (FIXTURES / "single_methane_complete.cif").read_bytes()
    marker = b" 10.00 ? 1 MET"
    assert source.count(marker) == 5
    source = source.replace(marker, b" 10.00 0 1 MET")
    system = parse_mmcif_nonpoly_component_topology(
        source,
        source_id="single_methane_crosschecked",
    ).system

    assert {atom.metadata["formal_charge_source"] for atom in system.atoms} == {
        "cross_checked_atom_site_and_chem_comp_atom"
    }
    preparation = analyze_molecular_preparation(system)
    assert preparation.formal_charge_origin_counts == (
        ("metadata_observed_mmcif_chem_comp_atom", 5),
    )
    assert (
        require_canonical_ingest_applicable(system).canonical_ingest_supported is True
    )
    assert (
        require_profile_local_preparation_evidence(
            system
        ).profile_local_evidence_satisfied
        is True
    )


def test_crosscheck_marker_cannot_be_forged_over_unknown_atom_site_charge() -> None:
    system = _system("single_methane_complete.cif")
    metadata = dict(system.atoms[0].metadata)
    metadata["formal_charge_source"] = "cross_checked_atom_site_and_chem_comp_atom"
    forged = replace(
        system,
        atoms=(replace(system.atoms[0], metadata=metadata), *system.atoms[1:]),
    )
    forged = attach_parser_observation_digest(forged)

    assert attached_canonical_topology_sha256_matches(forged) is True
    assert attached_parser_observation_sha256_matches(forged) is True
    preparation = analyze_molecular_preparation(forged)
    assert preparation.parser_observation_self_consistent is True
    assert preparation.formal_charge_origin_counts == (
        ("metadata_observed_mmcif_chem_comp_atom", 4),
        ("unclassified_known", 1),
    )
    assert (
        analyze_canonical_ingest_applicability(forged).canonical_ingest_supported
        is True
    )
    local = analyze_profile_local_preparation_evidence(forged)
    assert local.profile_local_evidence_status == "not_satisfied"
    assert local.source_observed_formal_charge_count == 4


def test_component_atom_marker_tamper_loses_source_hydrogen_evidence() -> None:
    system = _system("single_methane_complete.cif")
    metadata = dict(system.atoms[1].metadata)
    component_marker = dict(metadata["mmcif_nonpoly_component_topology"])
    component_marker["template_atom_id"] = "WRONG"
    metadata["mmcif_nonpoly_component_topology"] = component_marker
    forged = replace(
        system,
        atoms=(
            system.atoms[0],
            replace(system.atoms[1], metadata=metadata),
            *system.atoms[2:],
        ),
    )
    forged = attach_parser_observation_digest(forged)

    assert attached_parser_observation_sha256_matches(forged) is True
    preparation = analyze_molecular_preparation(forged)
    assert preparation.parser_observation_self_consistent is True
    assert preparation.unknown_hydrogen_origin_count == 1
    applicability = analyze_canonical_ingest_applicability(forged)
    assert applicability.canonical_ingest_status == "unsupported"
    assert "hydrogens_source_observed" in applicability.failed_constraint_codes


def test_component_marker_tamper_without_rehash_breaks_observation_digest() -> None:
    system = _system("single_methane_complete.cif")
    metadata = dict(system.atoms[1].metadata)
    component_marker = dict(metadata["mmcif_nonpoly_component_topology"])
    component_marker["template_ordinal"] = 999
    metadata["mmcif_nonpoly_component_topology"] = component_marker
    forged = replace(
        system,
        atoms=(
            system.atoms[0],
            replace(system.atoms[1], metadata=metadata),
            *system.atoms[2:],
        ),
    )

    assert attached_canonical_topology_sha256_matches(forged) is True
    assert attached_parser_observation_sha256_matches(forged) is False
    preparation = analyze_molecular_preparation(forged)
    assert preparation.parser_observation_self_consistent is False
    assert preparation.hydrogen_origin_counts == (("unknown", 4),)
    assert preparation.formal_charge_origin_counts == (("unclassified_known", 5),)
    assert analyze_canonical_ingest_applicability(forged).canonical_ingest_status == (
        "invalid"
    )
    assert (
        analyze_profile_local_preparation_evidence(
            forged
        ).profile_local_evidence_satisfied
        is False
    )


def test_rehashed_noncontiguous_component_atom_ordinals_fail_closed() -> None:
    system = _system("single_methane_complete.cif")
    metadata = dict(system.atoms[1].metadata)
    component_marker = dict(metadata["mmcif_nonpoly_component_topology"])
    component_marker["template_ordinal"] = 999
    metadata["mmcif_nonpoly_component_topology"] = component_marker
    forged = replace(
        system,
        atoms=(
            system.atoms[0],
            replace(system.atoms[1], metadata=metadata),
            *system.atoms[2:],
        ),
    )
    forged = attach_parser_observation_digest(forged)

    assert attached_parser_observation_sha256_matches(forged) is True
    preparation = analyze_molecular_preparation(forged)
    assert preparation.parser_observation_self_consistent is True
    assert preparation.hydrogen_origin_counts == (("unknown", 4),)
    assert preparation.formal_charge_origin_counts == (("unclassified_known", 5),)
    applicability = analyze_canonical_ingest_applicability(forged)
    assert applicability.canonical_ingest_status == "unsupported"
    assert "hydrogens_source_observed" in applicability.failed_constraint_codes
    assert (
        analyze_profile_local_preparation_evidence(
            forged
        ).profile_local_evidence_satisfied
        is False
    )


def test_stale_topology_and_observation_attachments_fail_identity_closed() -> None:
    system = _system("single_methane_complete.cif")
    forged = replace(
        system,
        bonds=(replace(system.bonds[0], order=2.0), *system.bonds[1:]),
    )

    assert attached_canonical_topology_sha256_matches(forged) is False
    assert attached_parser_observation_sha256_matches(forged) is False
    preparation = analyze_molecular_preparation(forged)
    assert preparation.parser_pedigree_id == "unrecognized"
    assert preparation.parser_observation_self_consistent is False
    assert analyze_canonical_ingest_applicability(forged).canonical_ingest_status == (
        "invalid"
    )


def test_coherently_rehashed_wrong_parser_version_remains_unrecognized() -> None:
    system = _system("single_methane_complete.cif")
    forged = replace(
        system,
        provenance=replace(system.provenance, parser_version="9.9.9"),
    )
    forged = attach_parser_observation_digest(forged)

    assert attached_parser_observation_sha256_matches(forged) is True
    preparation = analyze_molecular_preparation(forged)
    assert preparation.parser_pedigree_id == "unrecognized"
    assert preparation.parser_observation_self_consistent is False
    applicability = analyze_canonical_ingest_applicability(forged)
    assert applicability.canonical_ingest_status == "invalid"
    assert "recognized_parser_pedigree" in applicability.failed_constraint_codes


def test_base_mmcif_preparation_digest_and_pedigree_are_unchanged() -> None:
    from betelgeuze_engine_v2.molecular.pdb_mmcif import parse_mmcif

    source = parse_mmcif(
        (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "tier_beta"
            / "mini_protein.cif"
        ).read_bytes()
    ).system
    preparation = analyze_molecular_preparation(source)

    assert preparation.parser_pedigree_id == "betelgeuze.mmcif_parser/1.9.0"
    assert preparation.parser_observation_self_consistent is True
    assert source.provenance.metadata["parser_observation_sha256"] == (
        "6ae65e62430f508a6dd9a4a52fc30efc0cf0e5b9345d8de055e13f88f1fc84d1"
    )
    assert preparation.report_sha256 == (
        "a5a9c188b0d5be29461c302b122c5db94e0f54799908b500e361195dfcfa24c1"
    )
