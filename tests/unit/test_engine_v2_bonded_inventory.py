from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.molecular import (
    EXACT_METHANE_BOND_ANGLE_CLAIM_SCOPE,
    EXACT_METHANE_BOND_ANGLE_CONSTRAINT_CODES,
    EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_ID,
    EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_VERSION,
    EXACT_METHANE_BOND_ANGLE_PROFILE_ID,
    CanonicalAngleIdentity,
    CanonicalBondIdentity,
    ExactMethaneBondAngleInventoryReport,
    analyze_exact_methane_bond_angle_inventory,
    canonical_all_atom_systems_equal,
    deserialize_all_atom_system,
    parse_sdf_v2000,
    parse_smiles,
    serialize_all_atom_system,
)
from betelgeuze_engine_v2.molecular import smiles as smiles_module


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "v2_1_ingest_corpus"
METHANE = FIXTURES / "methane_explicit_h.sdf"
C13_METHANE = FIXTURES / "methane_c13_explicit_h.sdf"


def _methane_system(source: bytes | None = None, *, source_id: str = "exact-methane"):
    return parse_sdf_v2000(
        METHANE.read_bytes() if source is None else source,
        source_id=source_id,
    ).system


def _atom_line(element: str) -> str:
    return (
        f"{0.0:10.4f}{0.0:10.4f}{0.0:10.4f} {element:<3}"
        f"{0:2d}{0:3d}{0:3d}{0:3d}{0:3d}{0:3d}"
        f"{0:3d}{0:3d}{0:3d}{0:3d}{0:3d}{0:3d}"
    )


def _bond_line(atom_i: int, atom_j: int) -> str:
    return f"{atom_i:3d}{atom_j:3d}{1:3d}{0:3d}"


def _sdf_record(
    elements: tuple[str, ...],
    bonds: tuple[tuple[int, int], ...],
    *,
    properties: tuple[str, ...] = (),
) -> bytes:
    lines = [
        "exact-identity-fixture",
        "betelgeuze-v2",
        "contract-only",
        f"{len(elements):3d}{len(bonds):3d}  0  0  0  0  0  0  0  0999 V2000",
        *(_atom_line(element) for element in elements),
        *(_bond_line(atom_i, atom_j) for atom_i, atom_j in bonds),
        *properties,
        "M  END",
        "$$$$",
    ]
    return ("\n".join(lines) + "\n").encode("ascii")


def _ethane_source() -> bytes:
    return _sdf_record(
        ("C", "C", "H", "H", "H", "H", "H", "H"),
        (
            (1, 2),
            (1, 3),
            (1, 4),
            (1, 5),
            (2, 6),
            (2, 7),
            (2, 8),
        ),
    )


def test_exact_methane_enumerates_only_canonical_bond_and_angle_identities() -> None:
    report = analyze_exact_methane_bond_angle_inventory(_methane_system())
    payload = report.to_dict()

    assert payload["schema_id"] == EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_ID
    assert (
        payload["schema_version"]
        == EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_VERSION
        == "1.0.0"
    )
    assert report.profile_id == EXACT_METHANE_BOND_ANGLE_PROFILE_ID
    assert report.claim_scope == EXACT_METHANE_BOND_ANGLE_CLAIM_SCOPE
    assert report.constraint_results == tuple(
        (code, True) for code in EXACT_METHANE_BOND_ANGLE_CONSTRAINT_CODES
    )
    assert report.failed_constraint_codes == ()
    assert report.inventory_status == "available"
    assert report.carbon_atom_index == 0
    assert report.hydrogen_atom_indices == (1, 2, 3, 4)
    assert report.bond_identities == (
        CanonicalBondIdentity(0, 1),
        CanonicalBondIdentity(0, 2),
        CanonicalBondIdentity(0, 3),
        CanonicalBondIdentity(0, 4),
    )
    assert report.angle_identities == (
        CanonicalAngleIdentity(1, 0, 2),
        CanonicalAngleIdentity(1, 0, 3),
        CanonicalAngleIdentity(1, 0, 4),
        CanonicalAngleIdentity(2, 0, 3),
        CanonicalAngleIdentity(2, 0, 4),
        CanonicalAngleIdentity(3, 0, 4),
    )
    assert report.bond_identity_status == "enumerated_from_canonical_graph"
    assert report.angle_identity_status == "enumerated_from_canonical_graph"
    assert report.proper_torsion_identity_status == "not_assessed"
    assert report.improper_identity_status == "not_assessed"
    assert report.constraint_identity_status == "not_assessed"
    assert report.report_sha256 == (
        "02f3931e1b6272e83bf5ca2c08333a9d3c1219470f7c0cd6089828fb081957b8"
    )
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload


def test_inventory_is_repeatable_and_bound_across_snapshot_round_trip() -> None:
    system = _methane_system()
    restored = deserialize_all_atom_system(serialize_all_atom_system(system))
    first = analyze_exact_methane_bond_angle_inventory(system)
    repeated = analyze_exact_methane_bond_angle_inventory(system)
    round_tripped = analyze_exact_methane_bond_angle_inventory(restored)

    assert canonical_all_atom_systems_equal(system, restored)
    assert first.to_dict() == repeated.to_dict() == round_tripped.to_dict()
    assert first.matches_system(system) is True
    assert first.matches_system(restored) is True
    assert first.canonical_topology_sha256 is not None
    assert first.source_sha256 is not None
    assert len(first.applicability_report_sha256) == 64
    assert len(first.profile_local_preparation_report_sha256) == 64


def test_term_order_is_independent_of_source_bond_order_and_carbon_position() -> None:
    lines = METHANE.read_text(encoding="ascii").splitlines()
    shuffled_source = ("\n".join((*lines[:9], *reversed(lines[9:13]), *lines[13:])) + "\n").encode(
        "ascii"
    )
    baseline = analyze_exact_methane_bond_angle_inventory(_methane_system())
    shuffled = analyze_exact_methane_bond_angle_inventory(
        _methane_system(shuffled_source, source_id="shuffled-bonds")
    )

    assert shuffled.inventory_status == "available"
    assert shuffled.bond_identities == baseline.bond_identities
    assert shuffled.angle_identities == baseline.angle_identities
    assert shuffled.canonical_topology_sha256 == baseline.canonical_topology_sha256
    assert shuffled.source_sha256 != baseline.source_sha256

    carbon_second_source = _sdf_record(
        ("H", "C", "H", "H", "H"),
        ((2, 1), (2, 3), (2, 4), (2, 5)),
    )
    carbon_second = analyze_exact_methane_bond_angle_inventory(
        _methane_system(carbon_second_source, source_id="carbon-second")
    )
    assert carbon_second.inventory_status == "available"
    assert carbon_second.carbon_atom_index == 1
    assert carbon_second.hydrogen_atom_indices == (0, 2, 3, 4)
    assert carbon_second.bond_identities == (
        CanonicalBondIdentity(0, 1),
        CanonicalBondIdentity(1, 2),
        CanonicalBondIdentity(1, 3),
        CanonicalBondIdentity(1, 4),
    )
    assert len(carbon_second.angle_identities) == 6
    assert all(term.center_atom == 1 for term in carbon_second.angle_identities)


def test_exact_layer_rejects_supported_hydrocarbon_profile_widening() -> None:
    ethane = parse_sdf_v2000(_ethane_source(), source_id="explicit-h-ethane").system
    report = analyze_exact_methane_bond_angle_inventory(ethane)

    assert report.profile_local_preparation_report.canonical_ingest_supported is True
    assert report.profile_local_preparation_report.profile_local_evidence_satisfied is True
    assert report.inventory_status == "unsupported"
    assert report.failed_constraint_codes == (
        "exact_atom_count",
        "exact_bond_count",
        "exact_element_counts",
        "exact_source_observed_hydrogen_inventory",
        "exact_methane_graph",
    )
    assert report.carbon_atom_index is None
    assert report.hydrogen_atom_indices == ()
    assert report.bond_identities == ()
    assert report.angle_identities == ()


@pytest.mark.parametrize(
    ("source", "source_id", "failed_constraint_codes"),
    [
        (
            C13_METHANE.read_bytes(),
            "c13-methane",
            (
                "canonical_ingest_supported",
                "profile_local_evidence_satisfied",
                "isotopes_absent",
            ),
        ),
        (
            METHANE.read_bytes().replace(
                b"M  END\n",
                b"M  CHG  1   1   1\nM  END\n",
                1,
            ),
            "charged-methane",
            (
                "canonical_ingest_supported",
                "profile_local_evidence_satisfied",
                "formal_charges_known_zero",
            ),
        ),
    ],
)
def test_isotope_and_charge_variants_expose_no_terms(
    source: bytes,
    source_id: str,
    failed_constraint_codes: tuple[str, ...],
) -> None:
    report = analyze_exact_methane_bond_angle_inventory(
        _methane_system(source, source_id=source_id)
    )

    assert report.inventory_status == "unsupported"
    assert report.failed_constraint_codes == failed_constraint_codes
    assert report.bond_identities == ()
    assert report.angle_identities == ()


def test_generated_hydrogen_smiles_methane_exposes_no_terms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        _, rd_base = smiles_module._import_rdkit()
    except (ImportError, ModuleNotFoundError):
        pytest.skip("RDKit is unavailable")
    monkeypatch.setattr(
        smiles_module,
        "_SUPPORTED_RDKIT_VERSIONS",
        frozenset({rd_base.rdkitVersion}),
    )
    system = parse_smiles(b"C", source_id="generated-h-methane").system
    report = analyze_exact_methane_bond_angle_inventory(system)

    assert report.inventory_status == "unsupported"
    assert report.failed_constraint_codes == (
        "canonical_ingest_supported",
        "profile_local_evidence_satisfied",
        "sdf_v2000_source_pedigree",
        "formal_charges_known_zero",
        "exact_source_observed_hydrogen_inventory",
    )
    assert report.bond_identities == ()
    assert report.angle_identities == ()


def test_source_and_topology_tampering_cannot_inherit_term_inventory() -> None:
    system = _methane_system()
    baseline = analyze_exact_methane_bond_angle_inventory(system)
    forged_source = replace(
        system,
        provenance=replace(system.provenance, source_sha256="0" * 64),
    )
    source_report = analyze_exact_methane_bond_angle_inventory(forged_source)
    forged_bond = replace(system.bonds[0], order=2.0)
    forged_topology = replace(
        system,
        bonds=(forged_bond, *system.bonds[1:]),
    )
    topology_report = analyze_exact_methane_bond_angle_inventory(forged_topology)

    assert source_report.inventory_status == "invalid"
    assert topology_report.inventory_status == "invalid"
    assert source_report.bond_identities == topology_report.bond_identities == ()
    assert source_report.angle_identities == topology_report.angle_identities == ()
    assert baseline.matches_system(forged_source) is False
    assert baseline.matches_system(forged_topology) is False
    assert source_report.report_sha256 != baseline.report_sha256
    assert topology_report.report_sha256 != baseline.report_sha256


def test_report_is_factory_only_and_all_downstream_authority_remains_false() -> None:
    system = _methane_system()
    report = ExactMethaneBondAngleInventoryReport(system)

    with pytest.raises(TypeError):
        ExactMethaneBondAngleInventoryReport()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        ExactMethaneBondAngleInventoryReport(  # type: ignore[call-arg]
            system,
            bond_identities=(),
        )
    with pytest.raises(TypeError):
        replace(report, inventory_status="available")
    with pytest.raises(ValueError):
        CanonicalBondIdentity(2, 1)
    with pytest.raises(ValueError):
        CanonicalAngleIdentity(2, 1, 0)

    assert report.preparation_ready is False
    assert report.parameter_set_id is None
    assert report.parameter_assignment_sha256 is None
    assert report.parameterability_assessed is False
    assert report.parameterizable is False
    assert report.physics_supported is False
    assert report.energy_evaluation_authorized is False
    assert report.force_evaluation_authorized is False
    assert report.minimization_authorized is False
    assert report.simulation_ready is False
    assert report.claim_safe is False
    assert report.blockers == (
        "source_digest_is_not_authentication",
        "bond_parameters_not_assigned",
        "angle_parameters_not_assigned",
        "proper_torsion_identity_not_assessed",
        "improper_identity_not_assessed",
        "constraint_identity_not_assessed",
        "preparation_not_ready",
        "parameterability_not_assessed",
        "energy_evaluation_not_authorized",
        "force_evaluation_not_authorized",
        "minimization_not_authorized",
        "simulation_not_authorized",
        "claim_not_authorized",
    )
    assert set(report.bond_identities[0].to_dict()) == {"atom_i", "atom_j"}
    assert set(report.angle_identities[0].to_dict()) == {
        "outer_atom_i",
        "center_atom",
        "outer_atom_k",
    }
