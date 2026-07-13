from __future__ import annotations

from dataclasses import replace
import hashlib
import math

import pytest

from betelgeuze_engine_v2.molecular import (
    EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS,
    EXACT_H2O_GRAPH_PREPARATION_SCOPE,
    EXACT_H2O_GRAPH_PROFILE_ID,
    EXACT_H2O_GRAPH_PROFILE_SCHEMA_ID,
    EXACT_H2O_GRAPH_PROJECTION_IDENTITY_SEMANTICS,
    EXACT_H2O_GRAPH_PROJECTION_SCHEMA_ID,
    EXACT_H2O_GRAPH_RULE_SET_SCHEMA_ID,
    EXACT_H2O_GRAPH_RULE_SET_SHA256,
    ExactH2OGraphConsumerError,
    ExactH2OGraphProfileError,
    ExactH2OGraphProfileReport,
    analyze_canonical_ingest_applicability,
    analyze_exact_h2o_graph_profile,
    exact_h2o_graph_rule_set_bytes,
    parse_sdf_v2000,
    parse_smiles,
    require_exact_h2o_graph_profile,
    round_trip_sdf_v2000_source,
)
from betelgeuze_engine_v2.molecular.observation import (
    attach_parser_observation_digest,
)


def _sdf(
    elements: tuple[str, ...],
    edges: tuple[tuple[int, int, int], ...],
    *,
    atom_order: tuple[int, ...] | None = None,
    charge_codes: tuple[int, ...] | None = None,
    z_scale: float = 0.1,
    collinear: bool = False,
    name: str = "exact-h2o-graph",
) -> bytes:
    natural_order = tuple(range(len(elements)))
    order = natural_order if atom_order is None else atom_order
    assert tuple(sorted(order)) == natural_order
    assert all(
        0 <= atom_i < atom_j < len(elements) and bond_type in {1, 2, 3, 4}
        for atom_i, atom_j, bond_type in edges
    )
    charges = (0,) * len(elements) if charge_codes is None else charge_codes
    assert len(charges) == len(elements)
    new_index = {old: new for new, old in enumerate(order)}
    ordered_edges = [
        (*sorted((new_index[atom_i], new_index[atom_j])), bond_type)
        for atom_i, atom_j, bond_type in edges
    ]
    atom_lines: list[str] = []
    for output_index, old_index in enumerate(order):
        angle = 2.0 * math.pi * output_index / max(1, len(order))
        x = float(output_index) if collinear else math.cos(angle)
        y = 0.0 if collinear else math.sin(angle)
        z = 0.0 if collinear else z_scale * ((output_index % 3) - 1)
        atom_lines.append(
            f"{x:10.4f}"
            f"{y:10.4f}"
            f"{z:10.4f} "
            f"{elements[old_index]:<3}{0:2d}{charges[old_index]:3d}" + "  0" * 10
        )
    bond_lines = [
        f"{atom_i + 1:3d}{atom_j + 1:3d}{bond_type:3d}{0:3d}"
        for atom_i, atom_j, bond_type in sorted(ordered_edges)
    ]
    counts = f"{len(elements):3d}{len(edges):3d}  0  0  0  0  0  0  0  0999 V2000"
    return (
        "\n".join(
            (
                name,
                "betelgeuze-v2",
                "source-observed exact H2O graph fixture",
                counts,
                *atom_lines,
                *bond_lines,
                "M  END",
                "$$$$",
                "",
            )
        )
    ).encode("ascii")


def _h2o_source(**kwargs: object) -> bytes:
    return _sdf(("O", "H", "H"), ((0, 1, 1), (0, 2, 1)), **kwargs)


_FALSE_GATES = (
    "source_authenticated",
    "generic_chemistry_supported",
    "generic_molecular_preparation_ready",
    "global_molecular_preparation_ready",
    "water_role_assessed",
    "solvent_role_assessed",
    "hydration_state_assessed",
    "ph_assessed",
    "protonation_correctness_assessed",
    "autoionization_assessed",
    "hydrogen_bonding_assessed",
    "source_bond_order_independently_validated",
    "valence_independently_validated",
    "electronic_structure_assessed",
    "geometry_quality_assessed",
    "bond_lengths_assessed",
    "bond_angle_assessed",
    "conformation_assessed",
    "isotope_speciation_assessed",
    "parameterability_assessed",
    "parameterizable",
    "atom_types_assigned",
    "partial_charges_assigned",
    "force_field_parameters_assigned",
    "water_model_assigned",
    "constraints_assigned",
    "pbc_assessed",
    "periodicity_assessed",
    "physics_supported",
    "runtime_eligible",
    "execution_authorized",
    "energy_evaluation_authorized",
    "force_evaluation_authorized",
    "minimization_authorized",
    "simulation_ready",
    "claim_safe",
)


def test_exact_source_observed_h2o_graph_profile_is_available() -> None:
    system = parse_sdf_v2000(_h2o_source()).system
    report = analyze_exact_h2o_graph_profile(system)
    document = report.to_dict()

    assert report.status == "available"
    assert report.profile_chemistry_supported is True
    assert report.profile_graph_preparation_ready is True
    assert report.failed_constraint_codes == ()
    assert report.matches_system(system) is True
    assert document["schema_id"] == EXACT_H2O_GRAPH_PROFILE_SCHEMA_ID
    assert document["profile_id"] == EXACT_H2O_GRAPH_PROFILE_ID
    assert document["profile_preparation_scope"] == EXACT_H2O_GRAPH_PREPARATION_SCOPE
    assert document["eligible_consumer_ids"] == list(EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS)
    assert document["oxygen_atom_count"] == 1
    assert document["hydrogen_atom_count"] == 2
    assert document["molecular_formula"] == "H2O"
    assert document["molecule_label"] == "source_observed_h2o_graph"
    assert document["canonical_water_entity_marker_observed"] is False
    assert len(document["oxygen_hydrogen_edges"]) == 2
    assert document["source_bond_order_ledger_closed"] is True
    assert document["source_atom_marker_ledger_closed"] is True
    assert document["atom_bond_order_valence_ledger_closed"] is True
    assert document["h2o_graph_identity_semantics"].endswith(
        "not_water_or_solvent_role_evidence"
    )
    for field in _FALSE_GATES:
        assert document[field] is False
    gated = require_exact_h2o_graph_profile(
        system,
        consumer_id=EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS[0],
    )
    assert gated.report_sha256 == report.report_sha256


def test_rule_generic_reports_parser_and_projection_bindings_are_explicit() -> None:
    document = analyze_exact_h2o_graph_profile(
        parse_sdf_v2000(_h2o_source()).system
    ).to_dict()

    assert document["rule_set_sha256"] == EXACT_H2O_GRAPH_RULE_SET_SHA256
    assert EXACT_H2O_GRAPH_PROFILE_SCHEMA_ID == (
        "betelgeuze.exact_h2o_graph_profile/1.0.0"
    )
    assert EXACT_H2O_GRAPH_PROFILE_ID == (
        "source_observed_explicit_h_neutral_h2o_graph/1.0.0"
    )
    assert EXACT_H2O_GRAPH_PROJECTION_SCHEMA_ID == (
        "betelgeuze.exact_h2o_graph_projection/1.0.0"
    )
    assert EXACT_H2O_GRAPH_RULE_SET_SCHEMA_ID == (
        "betelgeuze.exact_h2o_graph_rules/1.0.0"
    )
    assert EXACT_H2O_GRAPH_PREPARATION_SCOPE == (
        "source_observed_graph_local_h2o_identity_and_bond_order_valence_ledger_only"
    )
    assert EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS == ("exact_h2o_graph_profile_audit",)
    assert document["source_format"] == "sdf_v2000"
    assert document["parser_pedigree_id"] == "betelgeuze.sdf_v2000_parser/1.5.0"
    assert document["parser_observation_self_consistent"] is True
    assert document["parser_observation_sha256_equal"] is True
    assert document["canonical_topology_sha256"]
    assert document["chemistry_report_sha256"]
    assert document["preparation_report_sha256"]
    assert document["graph_projection_sha256"]
    assert document["report_sha256"]
    assert document["graph_projection_identity_semantics"] == (
        EXACT_H2O_GRAPH_PROJECTION_IDENTITY_SEMANTICS
    )
    assert document["bond_order_valence_ledger_semantics"].endswith(
        "not_independent_bond_order_valence_protonation_or_electronic_structure_validation"
    )


def test_atom_order_is_admitted_but_source_indexed_identity_changes() -> None:
    first = analyze_exact_h2o_graph_profile(parse_sdf_v2000(_h2o_source()).system)
    second = analyze_exact_h2o_graph_profile(
        parse_sdf_v2000(_h2o_source(atom_order=(1, 0, 2))).system
    )

    assert first.status == second.status == "available"
    assert first.graph_projection_sha256 != second.graph_projection_sha256
    assert first.report_sha256 != second.report_sha256


def test_coordinates_do_not_control_graph_admission() -> None:
    bent = analyze_exact_h2o_graph_profile(
        parse_sdf_v2000(_h2o_source(z_scale=0.7)).system
    )
    collinear = analyze_exact_h2o_graph_profile(
        parse_sdf_v2000(_h2o_source(collinear=True)).system
    )

    assert bent.status == collinear.status == "available"
    assert bent.graph_projection_sha256 == collinear.graph_projection_sha256
    assert bent.report_sha256 != collinear.report_sha256
    assert bent.to_dict()["geometry_quality_assessed"] is False


@pytest.mark.parametrize(
    ("source", "failed_code"),
    [
        (_sdf(("O", "H"), ((0, 1, 1),)), "exact_atom_inventory_o1_h2"),
        (
            _sdf(("O", "H", "H", "H"), ((0, 1, 1), (0, 2, 1), (0, 3, 1))),
            "exact_atom_inventory_o1_h2",
        ),
        (
            _sdf(("O", "H", "H"), ((1, 2, 1),)),
            "single_component",
        ),
        (
            _sdf(("O", "H", "H"), ((0, 1, 1),)),
            "single_component",
        ),
        (
            _sdf(("O", "O", "H", "H"), ((0, 1, 1), (0, 2, 1), (1, 3, 1))),
            "exact_atom_inventory_o1_h2",
        ),
        (
            _sdf(("O", "H", "H"), ((0, 1, 2), (0, 2, 1))),
            "exact_two_single_oxygen_hydrogen_bonds",
        ),
        (
            _sdf(("C", "H", "H"), ((0, 1, 1), (0, 2, 1))),
            "exact_atom_inventory_o1_h2",
        ),
    ],
)
def test_wrong_inventory_connectivity_or_bond_order_fails_closed(
    source: bytes,
    failed_code: str,
) -> None:
    report = analyze_exact_h2o_graph_profile(parse_sdf_v2000(source).system)

    assert report.status == "unsupported"
    assert report.profile_graph_preparation_ready is False
    assert failed_code in report.failed_constraint_codes
    with pytest.raises(ExactH2OGraphProfileError) as exc_info:
        require_exact_h2o_graph_profile(
            parse_sdf_v2000(source).system,
            consumer_id=EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS[0],
        )
    assert failed_code in exc_info.value.failed_constraint_codes


@pytest.mark.parametrize("charge_codes", [(5, 0, 0), (3, 5, 0)])
def test_nonzero_per_atom_charge_fails_even_when_net_zero(
    charge_codes: tuple[int, int, int],
) -> None:
    report = analyze_exact_h2o_graph_profile(
        parse_sdf_v2000(_h2o_source(charge_codes=charge_codes)).system
    )

    assert report.status == "unsupported"
    assert "formal_charges_source_observed_known_zero" in report.failed_constraint_codes


def test_isotope_map_partial_charge_stereo_and_aromatic_tamper_fail_closed() -> None:
    system = parse_sdf_v2000(_h2o_source()).system
    atom_mutations = [
        (replace(system.atoms[1], isotope_mass_number=2), "isotopes_absent"),
        (replace(system.atoms[0], atom_map=1), "atom_maps_absent"),
        (replace(system.atoms[0], partial_charge_e=-0.8), "partial_charges_absent"),
        (replace(system.atoms[0], stereo="R"), "typed_stereo_absent"),
        (replace(system.atoms[0], aromatic=True), "aromaticity_absent"),
    ]
    for changed_atom, failed_code in atom_mutations:
        atoms = list(system.atoms)
        atoms[changed_atom.index] = changed_atom
        changed = attach_parser_observation_digest(replace(system, atoms=tuple(atoms)))
        report = analyze_exact_h2o_graph_profile(changed)
        assert report.status in {"invalid", "unsupported"}
        assert failed_code in report.failed_constraint_codes

    bonds = list(system.bonds)
    bonds[0] = replace(bonds[0], stereo="up")
    stereo_bond = attach_parser_observation_digest(replace(system, bonds=tuple(bonds)))
    assert (
        "typed_stereo_absent"
        in analyze_exact_h2o_graph_profile(stereo_bond).failed_constraint_codes
    )


def test_atom_marker_metadata_exact_types_keys_serial_and_charge_origin() -> None:
    system = parse_sdf_v2000(_h2o_source()).system
    variants: list[tuple[int, object, str]] = []
    metadata = dict(system.atoms[0].metadata)
    metadata["sdf_source_atom_index"] = True
    variants.append((0, metadata, "source_sdf_atom_marker_ledger_exact"))
    metadata = dict(system.atoms[1].metadata)
    metadata["sdf_atom_map"] = False
    variants.append((1, metadata, "source_sdf_atom_marker_ledger_exact"))
    metadata = dict(system.atoms[0].metadata)
    metadata["hidden_marker"] = "value"
    variants.append((0, metadata, "source_sdf_atom_marker_ledger_exact"))
    metadata = dict(system.atoms[0].metadata)
    metadata["formal_charge_source"] = "sdf_v2000_m_chg"
    variants.append((0, metadata, "formal_charges_source_observed_known_zero"))
    metadata = dict(system.atoms[1].metadata)
    metadata["hydrogen_origin"] = "generated"
    variants.append((1, metadata, "source_observed_hydrogens_only"))
    for atom_index, replacement_metadata, failed_code in variants:
        atoms = list(system.atoms)
        atoms[atom_index] = replace(
            atoms[atom_index],
            metadata=replacement_metadata,  # type: ignore[arg-type]
        )
        changed = attach_parser_observation_digest(replace(system, atoms=tuple(atoms)))
        assert (
            failed_code
            in analyze_exact_h2o_graph_profile(changed).failed_constraint_codes
        )

    atoms = list(system.atoms)
    atoms[0] = replace(atoms[0], serial=99)
    changed = attach_parser_observation_digest(replace(system, atoms=tuple(atoms)))
    assert (
        "source_sdf_atom_marker_ledger_exact"
        in analyze_exact_h2o_graph_profile(changed).failed_constraint_codes
    )


def test_bond_metadata_source_indices_endpoints_types_and_keys_fail_closed() -> None:
    system = parse_sdf_v2000(_h2o_source()).system
    variants: list[object] = []
    variants.append(replace(system.bonds[0], source="manual"))
    for key, value in (
        ("sdf_source_bond_index", True),
        ("sdf_source_atom_i", True),
        ("sdf_source_atom_j", 99),
        ("sdf_bond_type", True),
        ("hidden_marker", "value"),
    ):
        metadata = dict(system.bonds[0].metadata)
        metadata[key] = value
        variants.append(replace(system.bonds[0], metadata=metadata))
    for changed_bond in variants:
        bonds = list(system.bonds)
        bonds[0] = changed_bond  # type: ignore[assignment]
        changed = attach_parser_observation_digest(replace(system, bonds=tuple(bonds)))
        report = analyze_exact_h2o_graph_profile(changed)
        assert "source_sdf_bond_order_ledger_exact" in report.failed_constraint_codes


def test_forged_water_residue_or_solvent_metadata_is_not_admitted() -> None:
    system = parse_sdf_v2000(_h2o_source()).system
    residue = replace(
        system.residues[0],
        name="HOH",
        entity_type="water",
        metadata={"water_role": "solvent"},
    )
    chain = replace(system.chains[0], entity_id="water")
    changed = attach_parser_observation_digest(
        replace(system, residues=(residue,), chains=(chain,))
    )
    report = analyze_exact_h2o_graph_profile(changed)

    assert report.status in {"invalid", "unsupported"}
    assert "single_nonpolymer_residue" in report.failed_constraint_codes
    assert report.to_dict()["canonical_water_entity_marker_observed"] is True
    assert report.to_dict()["water_role_assessed"] is False
    assert report.to_dict()["solvent_role_assessed"] is False


def test_all_synthesized_sdf_residue_and_chain_context_is_exact() -> None:
    system = parse_sdf_v2000(_h2o_source()).system
    residue_variants = [
        replace(system.residues[0], sequence_number=2),
        replace(system.residues[0], insertion_code="A"),
        replace(system.residues[0], hetero=False),
        replace(system.residues[0], metadata={"source": "other"}),
    ]
    chain_variants = [
        replace(system.chains[0], chain_id="W"),
        replace(system.chains[0], entity_id="water"),
        replace(system.chains[0], metadata={"source": "other"}),
    ]
    for residue in residue_variants:
        changed = attach_parser_observation_digest(replace(system, residues=(residue,)))
        assert (
            "single_nonpolymer_residue"
            in analyze_exact_h2o_graph_profile(changed).failed_constraint_codes
        )
    for chain in chain_variants:
        changed = attach_parser_observation_digest(replace(system, chains=(chain,)))
        assert (
            "single_nonpolymer_residue"
            in analyze_exact_h2o_graph_profile(changed).failed_constraint_codes
        )


def test_smiles_generated_hydrogens_and_wrong_pedigree_remain_negative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rdkit import rdBase

    from betelgeuze_engine_v2.molecular import smiles as smiles_module

    monkeypatch.setattr(
        smiles_module,
        "_SUPPORTED_RDKIT_VERSIONS",
        frozenset({rdBase.rdkitVersion}),
    )
    report = analyze_exact_h2o_graph_profile(parse_smiles(b"O").system)

    assert report.status == "unsupported"
    assert "sdf_v2000_source_pedigree" in report.failed_constraint_codes
    assert "source_observed_hydrogens_only" in report.failed_constraint_codes


def test_existing_hydrocarbon_applicability_remains_negative() -> None:
    system = parse_sdf_v2000(_h2o_source()).system
    existing = analyze_canonical_ingest_applicability(system)
    additive = analyze_exact_h2o_graph_profile(system)

    assert existing.canonical_ingest_status == "unsupported"
    assert "elements_h_c_only" in existing.failed_constraint_codes
    assert additive.status == "available"


def test_sdf_round_trip_preserves_exact_graph_evidence() -> None:
    result = round_trip_sdf_v2000_source(
        _h2o_source(),
        source_id="exact-h2o-round-trip",
    )
    before = analyze_exact_h2o_graph_profile(result.source_ingest.system)
    after = analyze_exact_h2o_graph_profile(result.reparsed_ingest.system)

    assert before.status == after.status == "available"
    assert before.graph_projection_sha256 == after.graph_projection_sha256


def test_consumer_allowlist_and_unavailable_profile_errors_are_typed() -> None:
    system = parse_sdf_v2000(_h2o_source()).system
    with pytest.raises(TypeError, match="consumer_id"):
        require_exact_h2o_graph_profile(system)  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="exact string"):
        require_exact_h2o_graph_profile(
            system,
            consumer_id=1,  # type: ignore[arg-type]
        )
    with pytest.raises(ExactH2OGraphConsumerError) as exc_info:
        require_exact_h2o_graph_profile(
            system,
            consumer_id="runtime_force_field",
        )
    assert exc_info.value.eligible_consumer_ids == EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS


def test_parser_observation_crosswire_is_invalid() -> None:
    first = parse_sdf_v2000(_h2o_source()).system
    second = parse_sdf_v2000(_h2o_source(z_scale=0.9)).system
    metadata = dict(second.provenance.metadata)
    metadata["parser_observation_sha256"] = first.provenance.metadata[
        "parser_observation_sha256"
    ]
    crosswired = replace(
        second,
        provenance=replace(second.provenance, metadata=metadata),
    )
    document = analyze_exact_h2o_graph_profile(crosswired).to_dict()

    assert document["status"] == "invalid"
    assert document["parser_observation_self_consistent"] is False
    assert document["parser_observation_sha256_equal"] is False
    assert "parser_observation_digest_bound" in document["failed_constraint_codes"]


def test_report_factory_document_live_state_and_snapshot_tamper_boundaries() -> None:
    system = parse_sdf_v2000(_h2o_source()).system
    report = analyze_exact_h2o_graph_profile(system)
    original = report.to_dict()
    with pytest.raises(TypeError, match="factory-only"):
        ExactH2OGraphProfileReport(
            canonical_system_bytes=b"x",
            canonical_system_sha256=hashlib.sha256(b"x").hexdigest(),
        )
    returned = report.to_dict()
    returned["status"] = "unsupported"
    returned["graph_projection"]["atom_inventory_exact"] = False
    returned["blockers"].clear()
    assert report.to_dict() == original

    atoms = list(system.atoms)
    atoms[0] = replace(atoms[0], atom_map=7)
    live_mutation = attach_parser_observation_digest(
        replace(system, atoms=tuple(atoms))
    )
    assert report.status == "available"
    assert report.matches_system(live_mutation) is False

    object.__setattr__(report, "_canonical_system_sha256", "0" * 64)
    with pytest.raises(ValueError, match="snapshot digest"):
        _ = report.status


def test_rule_set_bytes_are_immutable_and_sha_stable() -> None:
    original = exact_h2o_graph_rule_set_bytes()
    local_copy = bytearray(original)
    local_copy[-2] = ord("X")

    assert bytes(local_copy) != exact_h2o_graph_rule_set_bytes()
    assert (
        hashlib.sha256(exact_h2o_graph_rule_set_bytes()).hexdigest()
        == EXACT_H2O_GRAPH_RULE_SET_SHA256
    )


def test_module_public_surface_is_explicit() -> None:
    from betelgeuze_engine_v2.molecular import exact_h2o_profile as module

    assert set(module.__all__) == {
        "EXACT_H2O_GRAPH_AUDIT_CONSUMER_IDS",
        "EXACT_H2O_GRAPH_CONSTRAINT_CODES",
        "EXACT_H2O_GRAPH_PREPARATION_SCOPE",
        "EXACT_H2O_GRAPH_PROFILE_ID",
        "EXACT_H2O_GRAPH_PROFILE_SCHEMA_ID",
        "EXACT_H2O_GRAPH_PROFILE_SCHEMA_VERSION",
        "EXACT_H2O_GRAPH_PROFILE_STATUSES",
        "EXACT_H2O_GRAPH_PROJECTION_IDENTITY_SEMANTICS",
        "EXACT_H2O_GRAPH_PROJECTION_SCHEMA_ID",
        "EXACT_H2O_GRAPH_RULE_SET_SCHEMA_ID",
        "EXACT_H2O_GRAPH_RULE_SET_SHA256",
        "ExactH2OGraphConsumerError",
        "ExactH2OGraphProfileError",
        "ExactH2OGraphProfileReport",
        "analyze_exact_h2o_graph_profile",
        "exact_h2o_graph_rule_set_bytes",
        "require_exact_h2o_graph_profile",
    }
