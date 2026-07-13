from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest
import torch

from betelgeuze_engine_v2.molecular import (
    CANONICAL_INGEST_APPLICABILITY_SCHEMA_ID,
    CANONICAL_INGEST_APPLICABILITY_SCHEMA_VERSION,
    CANONICAL_INGEST_CLAIM_SCOPE,
    CANONICAL_INGEST_CONSTRAINT_CODES,
    EXPLICIT_NEUTRAL_ACYCLIC_SATURATED_HYDROCARBON_PROFILE_ID,
    PARAMETERABILITY_STATUS,
    SOURCE_AUTHENTICATION_STATUS,
    CanonicalIngestApplicabilityError,
    ChemistryCoverageLimitError,
    PreparationCoverageLimitError,
    analyze_canonical_ingest_applicability,
    canonical_all_atom_systems_equal,
    deserialize_all_atom_system,
    parse_pdb,
    parse_sdf_v2000,
    parse_smiles,
    require_canonical_ingest_applicable,
    serialize_all_atom_system,
)
from betelgeuze_engine_v2.molecular import chemistry as chemistry_module
from betelgeuze_engine_v2.molecular import applicability as applicability_module
from betelgeuze_engine_v2.molecular import preparation as preparation_module
from betelgeuze_engine_v2.molecular import smiles as smiles_module


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
METHANE = FIXTURES / "v2_1_ingest_corpus" / "methane_explicit_h.sdf"
ETHANOL = FIXTURES / "tier_beta" / "ethanol.sdf"
MINI_PDB = FIXTURES / "tier_beta" / "mini_protein.pdb"


def _methane_system():
    return parse_sdf_v2000(
        METHANE.read_bytes(),
        source_id="sdf_v2000_methane_explicit_h",
    ).system


def _methane_sdf_variant(
    *,
    property_line: bytes | None = None,
    first_bond_type: int = 1,
    add_hydrogen_cycle_edge: bool = False,
) -> bytes:
    data = METHANE.read_bytes()
    if first_bond_type != 1:
        data = data.replace(
            b"  1  2  1  0\n",
            f"  1  2{first_bond_type:3d}  0\n".encode("ascii"),
            1,
        )
    if add_hydrogen_cycle_edge:
        data = data.replace(
            b"  5  4  0  0  0  0  0  0  0  0999 V2000\n",
            b"  5  5  0  0  0  0  0  0  0  0999 V2000\n",
            1,
        )
        data = data.replace(b"M  END\n", b"  2  3  1  0\nM  END\n", 1)
    if property_line is not None:
        data = data.replace(b"M  END\n", property_line + b"\nM  END\n", 1)
    return data


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


def test_explicit_methane_is_supported_for_canonical_ingest_only() -> None:
    system = _methane_system()
    report = analyze_canonical_ingest_applicability(system)
    payload = report.to_dict()

    assert payload["schema_id"] == CANONICAL_INGEST_APPLICABILITY_SCHEMA_ID
    assert (
        payload["schema_version"]
        == (CANONICAL_INGEST_APPLICABILITY_SCHEMA_VERSION)
        == "1.0.0"
    )
    assert report.profile_id == (
        EXPLICIT_NEUTRAL_ACYCLIC_SATURATED_HYDROCARBON_PROFILE_ID
    )
    assert report.claim_scope == CANONICAL_INGEST_CLAIM_SCOPE
    assert report.source_authentication_status == SOURCE_AUTHENTICATION_STATUS
    assert report.canonical_state_valid is True
    assert report.graph_representable is True
    assert report.atom_count == 5
    assert report.bond_count == 4
    assert report.component_count == 1
    assert report.carbon_atom_count == 1
    assert report.hydrogen_atom_count == 4
    assert report.source_observed_hydrogen_count == 4
    assert report.adapter_generated_hydrogen_count == 0
    assert report.unknown_hydrogen_origin_count == 0
    assert report.unknown_formal_charge_count == 0
    assert report.nonzero_formal_charge_count == 0
    assert report.isotope_count == 0
    assert report.aromatic_atom_count == 0
    assert report.aromatic_bond_count == 0
    assert report.non_single_bond_count == 0
    assert report.stereo_labeled_atom_count == 0
    assert report.stereo_labeled_bond_count == 0
    assert report.valence_violation_count == 0
    assert report.constraint_results == tuple(
        (code, True) for code in CANONICAL_INGEST_CONSTRAINT_CODES
    )
    assert report.failed_constraint_codes == ()
    assert report.canonical_ingest_status == "supported"
    assert report.canonical_ingest_supported is True
    assert report.preparation_status == "incomplete"
    assert report.preparation_ready is False
    assert report.parameterability_status == PARAMETERABILITY_STATUS
    assert report.parameter_set_id is None
    assert report.parameter_assignment_sha256 is None
    assert report.parameterability_assessed is False
    assert report.parameterizable is False
    assert report.simulation_ready is False
    assert report.claim_safe is False
    assert report.blockers == (
        "preparation_not_ready",
        "source_digest_is_not_authentication",
        "electronic_state_not_typed",
        "parameter_set_not_declared",
        "parameterability_not_assessed",
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
    assert report.report_sha256 == (
        "45d4ba5326a7d65eaecbc834c5002aa93aac7c4c860cbf55e70ea7f8fa5bb32c"
    )
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert report.matches_system(system) is True
    assert require_canonical_ingest_applicable(system) == report


def test_snapshot_round_trip_preserves_applicability_report() -> None:
    source = _methane_system()
    restored = deserialize_all_atom_system(serialize_all_atom_system(source))

    assert canonical_all_atom_systems_equal(source, restored)
    assert analyze_canonical_ingest_applicability(restored).to_dict() == (
        analyze_canonical_ingest_applicability(source).to_dict()
    )


def test_valid_but_out_of_profile_inputs_return_exact_unsupported_constraints() -> None:
    ethanol = parse_sdf_v2000(
        ETHANOL.read_bytes(),
        source_id="sdf_v2000_ethanol",
    ).system
    ethanol_report = analyze_canonical_ingest_applicability(ethanol)
    assert ethanol_report.canonical_ingest_status == "unsupported"
    assert ethanol_report.canonical_ingest_supported is False
    assert ethanol_report.failed_constraint_codes == (
        "elements_h_c_only",
        "explicit_valence_closed",
    )
    assert ethanol_report.valence_violation_count == 3
    assert ethanol_report.parameterability_assessed is False
    assert ethanol_report.parameterizable is False

    pdb = parse_pdb(MINI_PDB.read_bytes(), source_id="pdb_mini_protein").system
    pdb_report = analyze_canonical_ingest_applicability(pdb)
    assert pdb_report.canonical_ingest_status == "unsupported"
    assert pdb_report.failed_constraint_codes == (
        "single_component",
        "formal_charges_known_zero",
        "acyclic_graph",
        "explicit_valence_closed",
    )
    with pytest.raises(CanonicalIngestApplicabilityError) as exc_info:
        require_canonical_ingest_applicable(pdb)
    assert exc_info.value.report == pdb_report
    assert exc_info.value.failed_constraint_codes == pdb_report.failed_constraint_codes


def test_tampering_never_inherits_a_supported_source_bound_decision() -> None:
    source = _methane_system()
    baseline = analyze_canonical_ingest_applicability(source)
    forged_metadata = replace(
        source,
        metadata={
            **source.metadata,
            "canonical_ingest_supported": True,
            "parameterizable": True,
            "claim_safe": True,
        },
    )
    metadata_report = analyze_canonical_ingest_applicability(forged_metadata)
    assert metadata_report.to_dict() == baseline.to_dict()

    changed_atom = replace(source.atoms[1], element="C", atomic_number=6)
    forged_topology = replace(
        source,
        atoms=(source.atoms[0], changed_atom, *source.atoms[2:]),
    )
    forged_report = analyze_canonical_ingest_applicability(forged_topology)
    assert forged_report.canonical_ingest_status == "invalid"
    assert forged_report.canonical_ingest_supported is False
    assert "parser_observation_self_consistent" in (
        forged_report.failed_constraint_codes
    )
    assert forged_report.report_sha256 != baseline.report_sha256

    hydrogen_metadata = dict(source.atoms[1].metadata)
    hydrogen_metadata["hydrogen_origin"] = "unknown-forged-origin"
    forged_hydrogen_origin = replace(
        source,
        atoms=(
            source.atoms[0],
            replace(source.atoms[1], metadata=hydrogen_metadata),
            *source.atoms[2:],
        ),
    )
    hydrogen_report = analyze_canonical_ingest_applicability(forged_hydrogen_origin)
    assert hydrogen_report.canonical_ingest_status == "invalid"
    assert hydrogen_report.unknown_hydrogen_origin_count == 4
    assert "hydrogens_source_observed" in hydrogen_report.failed_constraint_codes


def test_invalid_excluded_state_is_invalid_even_when_topology_digest_exists() -> None:
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
    report = analyze_canonical_ingest_applicability(invalid)

    assert report.canonical_topology_digest_available is True
    assert report.canonical_ingest_status == "invalid"
    assert "canonical_state_valid" in report.failed_constraint_codes
    assert report.preparation_status == "invalid"
    assert report.preparation_ready is False


def test_profile_constraints_reject_each_declared_out_of_scope_feature() -> None:
    source = _methane_system()
    variants = {
        "formal_charges_known_zero": replace(
            source,
            atoms=(
                replace(source.atoms[0], formal_charge=1),
                *source.atoms[1:],
            ),
        ),
        "isotopes_absent": replace(
            source,
            atoms=(
                source.atoms[0],
                replace(source.atoms[1], isotope_mass_number=2),
                *source.atoms[2:],
            ),
        ),
        "aromaticity_absent": replace(
            source,
            atoms=(
                replace(source.atoms[0], aromatic=True),
                replace(source.atoms[1], aromatic=True),
                *source.atoms[2:],
            ),
            bonds=(
                replace(source.bonds[0], order=1.5, aromatic=True),
                *source.bonds[1:],
            ),
        ),
        "single_bonds_only": replace(
            source,
            bonds=(replace(source.bonds[0], order=2.0), *source.bonds[1:]),
        ),
        "stereo_absent": replace(
            source,
            atoms=(replace(source.atoms[0], stereo="R"), *source.atoms[1:]),
        ),
        "acyclic_graph": replace(
            source,
            bonds=(
                *source.bonds,
                replace(source.bonds[0], index=4, atom_i=1, atom_j=2),
            ),
        ),
    }

    for expected_code, variant in variants.items():
        report = analyze_canonical_ingest_applicability(variant)
        assert report.canonical_ingest_supported is False
        assert expected_code in report.failed_constraint_codes


@pytest.mark.parametrize(
    ("payload", "expected_codes"),
    [
        (
            _methane_sdf_variant(property_line=b"M  CHG  1   1   1"),
            ("formal_charges_known_zero",),
        ),
        (
            _methane_sdf_variant(property_line=b"M  ISO  1   2   2"),
            ("isotopes_absent",),
        ),
        (
            _methane_sdf_variant(first_bond_type=2),
            ("single_bonds_only", "explicit_valence_closed"),
        ),
        (
            _methane_sdf_variant(add_hydrogen_cycle_edge=True),
            ("acyclic_graph", "explicit_valence_closed"),
        ),
    ],
)
def test_self_consistent_sdf_sources_are_unsupported_not_invalid(
    payload: bytes,
    expected_codes: tuple[str, ...],
) -> None:
    system = parse_sdf_v2000(payload, source_id="profile-negative").system
    report = analyze_canonical_ingest_applicability(system)

    assert report.canonical_ingest_status == "unsupported"
    assert report.canonical_ingest_supported is False
    assert report.failed_constraint_codes == expected_codes
    assert report.parser_observation_self_consistent is True
    assert report.canonical_state_valid is True
    assert report.graph_representable is True


def test_adapter_generated_hydrogens_and_stereo_are_cleanly_unsupported(
    supported_local_rdkit: None,
) -> None:
    methane = parse_smiles(b"C", source_id="adapter-methane").system
    methane_report = analyze_canonical_ingest_applicability(methane)
    assert methane_report.canonical_ingest_status == "unsupported"
    assert methane_report.failed_constraint_codes == ("hydrogens_source_observed",)
    assert methane_report.adapter_generated_hydrogen_count == 4
    assert methane_report.parser_observation_self_consistent is True

    chiral = parse_smiles(b"C[C@H](CC)CCC", source_id="adapter-chiral").system
    chiral_report = analyze_canonical_ingest_applicability(chiral)
    assert chiral_report.canonical_ingest_status == "unsupported"
    assert chiral_report.failed_constraint_codes == (
        "stereo_absent",
        "hydrogens_source_observed",
    )
    assert chiral_report.parser_observation_self_consistent is True


def test_invalid_bond_endpoint_returns_invalid_report_instead_of_raising() -> None:
    source = _methane_system()
    invalid = replace(
        source,
        bonds=(
            *source.bonds,
            replace(source.bonds[0], index=4, atom_i=0, atom_j=99),
        ),
    )
    report = analyze_canonical_ingest_applicability(invalid)

    assert report.canonical_ingest_status == "invalid"
    assert report.canonical_ingest_supported is False
    assert "graph_representable" in report.failed_constraint_codes
    assert "explicit_valence_closed" in report.failed_constraint_codes


def test_report_invariants_reject_forged_promotion_and_reordered_evidence() -> None:
    report = analyze_canonical_ingest_applicability(_methane_system())

    with pytest.raises(ValueError, match="cannot promote"):
        replace(report, parameterability_assessed=True)
    with pytest.raises(ValueError, match="cannot promote"):
        replace(report, parameterizable=True)
    with pytest.raises(ValueError, match="cannot promote"):
        replace(report, simulation_ready=True)
    with pytest.raises(ValueError, match="cannot promote"):
        replace(report, claim_safe=True)
    with pytest.raises(ValueError, match="parameter_set_id"):
        replace(report, parameter_set_id="forged")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="preparation_status"):
        replace(report, preparation_status="attested", preparation_ready=True)
    with pytest.raises(ValueError, match="constraint_results"):
        replace(report, constraint_results=tuple(reversed(report.constraint_results)))
    with pytest.raises(ValueError, match="failed_constraint_codes"):
        replace(report, failed_constraint_codes=("contains_carbon",))
    with pytest.raises(ValueError, match="identity or counts"):
        replace(
            report,
            source_sha256=None,
            source_digest_available=False,
        )
    with pytest.raises(ValueError, match="identity or counts"):
        replace(report, parser_pedigree_id="arbitrary-parser/9.9.9")
    with pytest.raises(TypeError, match="immutable string/boolean pairs"):
        replace(
            report,
            constraint_results=tuple(
                [code, passed]  # type: ignore[misc]
                for code, passed in report.constraint_results
            ),
        )
    with pytest.raises(ValueError, match="degree sum"):
        replace(
            report,
            atom_count=1,
            bond_count=0,
            component_count=1,
            carbon_atom_count=1,
            hydrogen_atom_count=0,
            source_observed_hydrogen_count=0,
            adapter_generated_hydrogen_count=0,
            unknown_hydrogen_origin_count=0,
            valence_violation_count=0,
        )
    with pytest.raises(ValueError, match="ordered v1 blockers"):
        replace(report, blockers=())
    with pytest.raises(ValueError, match="aromatic_bond_count"):
        replace(report, aromatic_bond_count=1)
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        replace(report, chemistry_coverage_report_sha256="0" * 63)
    with pytest.raises(TypeError, match="atom_count"):
        replace(report, atom_count=True)


def test_applicability_inherits_the_chemistry_audit_resource_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chemistry_module, "MAX_CHEMISTRY_AUDIT_ATOMS", 4)
    with pytest.raises(ChemistryCoverageLimitError) as exc_info:
        analyze_canonical_ingest_applicability(_methane_system())
    assert exc_info.value.code == "atom_limit_exceeded"


def test_applicability_inherits_the_chemistry_bond_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(chemistry_module, "MAX_CHEMISTRY_AUDIT_BONDS", 3)
    with pytest.raises(ChemistryCoverageLimitError) as exc_info:
        analyze_canonical_ingest_applicability(_methane_system())
    assert exc_info.value.code == "bond_limit_exceeded"


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
def test_applicability_propagates_preparation_resource_limits(
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
        analyze_canonical_ingest_applicability(system)
    assert exc_info.value.code == expected_code


def test_applicability_wrong_input_remains_a_type_error() -> None:
    with pytest.raises(TypeError, match="system must be an AllAtomSystem"):
        analyze_canonical_ingest_applicability(object())  # type: ignore[arg-type]
