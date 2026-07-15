from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import betelgeuze_engine_v2.molecular as molecular
from betelgeuze_engine_v2.molecular import (
    mmcif_polymer_component_terminal_leaving_policy as policy,
)
from betelgeuze_engine_v2.molecular.applicability import (
    analyze_canonical_ingest_applicability,
)
from betelgeuze_engine_v2.molecular.mmcif_polymer_component_topology import (
    MAX_MMCIF_POLYMER_COMPONENT_ATOM_ROWS,
    MAX_MMCIF_POLYMER_COMPONENT_BOND_ROWS,
    MAX_MMCIF_POLYMER_COMPONENT_MATERIALIZED_BONDS,
    MAX_MMCIF_POLYMER_COMPONENT_ROWS,
    MAX_MMCIF_POLYMER_COMPONENT_SEQUENCE_ROWS,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_NAME,
    MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID,
    parse_mmcif_polymer_component_topology,
    write_mmcif_polymer_component_topology,
)
from betelgeuze_engine_v2.molecular.observation import (
    mmcif_polymer_component_topology_preparation_inventory_sha256,
)
from betelgeuze_engine_v2.molecular.preparation import analyze_molecular_preparation
from betelgeuze_engine_v2.molecular.profile_preparation import (
    analyze_profile_local_preparation_evidence,
)
from betelgeuze_engine_v2.molecular.serialization import serialize_all_atom_system


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = (
    ROOT / "tests" / "fixtures" / "v2_1_mmcif_polymer_component_terminal_leaving_policy"
)


def _fixture(name: str = "single_xaa.cif") -> bytes:
    return (FIXTURE_ROOT / name).read_bytes()


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    assert old and source.count(old) == 1
    return source.replace(old, new, 1)


def _error_code(source: bytes, *, source_id: str = "failure") -> str:
    with pytest.raises(
        policy.MmcifPolymerComponentTerminalLeavingPolicyError
    ) as captured:
        policy.parse_mmcif_polymer_component_terminal_leaving_policy(
            source, source_id=source_id
        )
    return captured.value.code


def _three_xaa_source() -> bytes:
    source = _replace_once(
        _fixture(),
        b"1 1 XAA n\n",
        b"1 1 XAA n\n1 2 XAA n\n1 3 XAA n\n",
    )
    lines = source.splitlines(keepends=True)
    atom_rows = [line for line in lines if line.startswith(b"ATOM ")]
    assert len(atom_rows) == 3
    repeated: list[bytes] = []
    next_id = 1
    for sequence_number in (1, 2, 3):
        for row in atom_rows:
            fields = row.decode("ascii").split()
            fields[1] = str(next_id)
            fields[8] = str(sequence_number)
            fields[16] = str(900 + sequence_number)
            repeated.append((" ".join(fields) + "\n").encode("ascii"))
            next_id += 1
    start = source.index(atom_rows[0])
    end = source.index(b"#\n", start)
    return source[:start] + b"".join(repeated) + source[end:]


def _reverse_atom_site_rows(source: bytes) -> bytes:
    lines = source.splitlines(keepends=True)
    indices = [index for index, line in enumerate(lines) if line.startswith(b"ATOM ")]
    assert indices
    rows = [lines[index] for index in indices]
    for index, row in zip(indices, reversed(rows), strict=True):
        lines[index] = row
    return b"".join(lines)


def _conventional_terminal_names_source() -> bytes:
    source = _three_xaa_source()
    for old, new in ((b"Q1", b"N"), (b"Q2", b"C"), (b"Q3", b"OXT")):
        source = source.replace(old, new)
    source = _replace_once(
        source,
        b"XAA OXT O 0 N Y N Y N Y 3\n#\nloop_\n_chem_comp_bond.comp_id",
        (
            b"XAA OXT O 0 N Y N Y N Y 3\n"
            b"XAA H H 0 N Y N N Y N 4\n"
            b"XAA H2 H 0 N Y N N Y N 5\n"
            b"#\nloop_\n_chem_comp_bond.comp_id"
        ),
    )
    source = _replace_once(
        source,
        b"XAA C OXT DOUB N N 2\n#\nloop_\n_atom_site.group_PDB",
        (
            b"XAA C OXT DOUB N N 2\n"
            b"XAA N H SING N N 3\n"
            b"XAA N H2 SING N N 4\n"
            b"#\nloop_\n_atom_site.group_PDB"
        ),
    )
    extra_rows = []
    atom_id = 10
    for sequence_number in (1, 2, 3):
        for atom_name, x in (("H", "-20.000"), ("H2", "120.000")):
            extra_rows.append(
                (
                    f"ATOM {atom_id} H {atom_name} . XAA A 1 {sequence_number} ? "
                    f"{x} {sequence_number}.000 6.000 1.00 19.00 ? "
                    f"{900 + sequence_number} AX Z {atom_name} 1\n"
                ).encode("ascii")
            )
            atom_id += 1
    final_marker = source.rfind(b"#\n")
    assert final_marker > 0
    return source[:final_marker] + b"".join(extra_rows) + source[final_marker:]


def test_contract_ids_headers_rules_and_inherited_caps_are_exact() -> None:
    assert policy.MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROFILE_ID == (
        "strict_mmcif_polymer_component_terminal_leaving_annotation_envelope/1.0.0"
    )
    assert policy.MMCIF_POLYMER_TERMINAL_LEAVING_RULES_SCHEMA_ID == (
        "betelgeuze.mmcif_polymer_terminal_leaving_rules/1.0.0"
    )
    assert policy.MMCIF_POLYMER_TERMINAL_LEAVING_POLICY_SCHEMA_ID == (
        "betelgeuze.mmcif_polymer_terminal_leaving_policy/1.0.0"
    )
    assert (
        policy.MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_CHEM_COMP_ATOM_HEADERS
        == (
            "_chem_comp_atom.comp_id",
            "_chem_comp_atom.atom_id",
            "_chem_comp_atom.type_symbol",
            "_chem_comp_atom.charge",
            "_chem_comp_atom.pdbx_aromatic_flag",
            "_chem_comp_atom.pdbx_leaving_atom_flag",
            "_chem_comp_atom.pdbx_stereo_config",
            "_chem_comp_atom.pdbx_backbone_atom_flag",
            "_chem_comp_atom.pdbx_n_terminal_atom_flag",
            "_chem_comp_atom.pdbx_c_terminal_atom_flag",
            "_chem_comp_atom.pdbx_ordinal",
        )
    )
    rules = policy.mmcif_polymer_terminal_leaving_rules_bytes()
    assert hashlib.sha256(rules).hexdigest() == (
        policy.MMCIF_POLYMER_TERMINAL_LEAVING_RULES_SHA256
    )
    assert policy.MMCIF_POLYMER_TERMINAL_LEAVING_RULES_SHA256 == (
        "9235a365be1ee9f0189f94f37ed3317ff14903f0469d41f6fea2a6d2678f92b1"
    )
    assert (
        policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SEQUENCE_ROWS
        == MAX_MMCIF_POLYMER_COMPONENT_SEQUENCE_ROWS
    )
    assert (
        policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_ROWS
        == MAX_MMCIF_POLYMER_COMPONENT_ROWS
    )
    assert (
        policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_ATOM_ROWS
        == MAX_MMCIF_POLYMER_COMPONENT_ATOM_ROWS
    )
    assert (
        policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_COMPONENT_BOND_ROWS
        == MAX_MMCIF_POLYMER_COMPONENT_BOND_ROWS
    )
    assert (
        policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_CHILD_MATERIALIZED_BONDS
        == MAX_MMCIF_POLYMER_COMPONENT_MATERIALIZED_BONDS
    )


def test_public_module_surface_is_exported_through_molecular_facade() -> None:
    assert all(hasattr(molecular, name) for name in policy.__all__)
    assert molecular.parse_mmcif_polymer_component_terminal_leaving_policy is (
        policy.parse_mmcif_polymer_component_terminal_leaving_policy
    )


@pytest.mark.parametrize(
    ("fixture_name", "atom_count", "bond_count", "roles"),
    (
        ("single_xaa.cif", 3, 2, ("singleton",)),
        (
            "xaa_mid_xaa.cif",
            8,
            5,
            ("n_sequence_boundary", "internal", "c_sequence_boundary"),
        ),
        ("multi_asym_category_order.cif", 6, 4, ("singleton", "singleton")),
    ),
)
def test_positive_fixtures_return_the_byte_exact_unchanged_child(
    fixture_name: str,
    atom_count: int,
    bond_count: int,
    roles: tuple[str, ...],
) -> None:
    source_id = f"fixture:{fixture_name}"
    ingest = policy.parse_mmcif_polymer_component_terminal_leaving_policy(
        _fixture(fixture_name), source_id=source_id
    )
    direct_child = parse_mmcif_polymer_component_topology(
        ingest._state.child_source, source_id=source_id
    )
    wrapper_child = ingest.child_ingest
    wrapper_system = ingest.system

    assert serialize_all_atom_system(wrapper_system) == serialize_all_atom_system(
        direct_child.system
    )
    assert wrapper_child.component_projection_sha256 == (
        direct_child.component_projection_sha256
    )
    assert wrapper_child.topology_state_sha256 == direct_child.topology_state_sha256
    assert wrapper_child.augmented_topology_sha256 == (
        direct_child.augmented_topology_sha256
    )
    assert wrapper_child.source_binding_sha256 == direct_child.source_binding_sha256
    assert wrapper_child.augmented_system_snapshot_sha256 == (
        direct_child.augmented_system_snapshot_sha256
    )
    assert (
        wrapper_child.to_dict()["augmented_system_parser_observation_sha256"]
        == direct_child.to_dict()["augmented_system_parser_observation_sha256"]
    )
    assert write_mmcif_polymer_component_topology(wrapper_child).payload == (
        write_mmcif_polymer_component_topology(direct_child).payload
    )
    assert wrapper_system.provenance.parser_name == (
        MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_NAME
    )
    assert (
        wrapper_system.provenance.metadata["mmcif_polymer_component_topology"][
            "parser_pedigree_id"
        ]
        == MMCIF_POLYMER_COMPONENT_TOPOLOGY_PARSER_PEDIGREE_ID
    )
    marker = wrapper_system.provenance.metadata["mmcif_polymer_component_topology"]
    assert marker["preparation_inventory_commitment_sha256"] == (
        mmcif_polymer_component_topology_preparation_inventory_sha256(wrapper_system)
    )
    assert wrapper_system.atom_count == atom_count
    assert len(wrapper_system.bonds) == bond_count
    assert tuple(row.position_role for row in ingest.sequence_boundaries) == roles
    assert all(
        wrapper_system.atoms[bond.atom_i].residue_index
        == wrapper_system.atoms[bond.atom_j].residue_index
        for bond in wrapper_system.bonds
    )
    assert "terminal_leaving" not in serialize_all_atom_system(wrapper_system).decode(
        "ascii"
    )


def test_annotations_and_sequence_positions_are_inventory_only() -> None:
    ingest = policy.parse_mmcif_polymer_component_terminal_leaving_policy(
        _fixture("xaa_mid_xaa.cif"), source_id="fixture:inventory"
    )
    annotations = tuple(row.to_dict() for row in ingest.atom_annotations)
    boundaries = tuple(row.to_dict() for row in ingest.sequence_boundaries)
    report = policy.analyze_mmcif_polymer_terminal_leaving_policy(ingest).to_dict()
    ingest_document = ingest.to_dict()

    assert [row["atom_id"] for row in annotations] == ["Q1", "Q2", "Q3", "Z9", "Y8"]
    assert [row["position_role"] for row in boundaries] == [
        "n_sequence_boundary",
        "internal",
        "c_sequence_boundary",
    ]
    assert report["component_atom_annotation_count"] == 5
    assert report["sequence_boundary_count"] == 3
    assert report["materialized_inter_residue_bond_count"] == 0
    assert report["system_unchanged_from_child"] is True
    assert report["wrapper_evidence_factory_only"] is True
    assert report["bare_system_retains_wrapper_evidence"] is False
    for computed_gate in (
        "child_stage_local_validation_passed",
        "child_stage_local_parser_pedigree_equal",
        "child_stage_local_component_projection_equal",
        "child_stage_local_topology_state_equal",
        "child_stage_local_augmented_topology_equal",
        "child_stage_local_source_binding_equal",
        "child_stage_local_system_byte_exact",
        "child_stage_local_snapshot_equal",
        "child_stage_local_parser_observation_equal",
        "child_stage_local_preparation_commitment_equal",
        "child_stage_local_canonical_emission_byte_exact",
    ):
        assert ingest_document[computed_gate] is True
        assert report[computed_gate] is True
    for false_gate in (
        "atom_names_used_to_infer_links",
        "auth_identity_used_for_policy",
        "coordinate_geometry_used",
        "role_assignment_interpreted",
        "chemical_terminal_state_assessed",
        "leaving_atom_policy_applied",
        "leaving_atoms_removed",
        "peptide_bonds_inferred",
        "inter_residue_bonds_materialized",
        "preparation_ready",
        "parameterability_assessed",
        "runtime_eligible",
        "claim_safe",
    ):
        assert report[false_gate] is False


def test_one_xaa_template_reused_at_all_sequence_roles_never_links_or_deletes() -> None:
    ingest = policy.parse_mmcif_polymer_component_terminal_leaving_policy(
        _three_xaa_source(), source_id="fixture:three-xaa"
    )
    child = parse_mmcif_polymer_component_topology(
        ingest._state.child_source, source_id="fixture:three-xaa"
    )
    system = ingest.system
    report = policy.analyze_mmcif_polymer_terminal_leaving_policy(ingest).to_dict()

    assert [row.position_role for row in ingest.sequence_boundaries] == [
        "n_sequence_boundary",
        "internal",
        "c_sequence_boundary",
    ]
    assert len(ingest.atom_annotations) == 3
    assert system.atom_count == child.system.atom_count == 9
    assert len(system.bonds) == len(child.system.bonds) == 6
    assert serialize_all_atom_system(system) == serialize_all_atom_system(child.system)
    assert ingest.child_ingest.augmented_system_snapshot_sha256 == (
        child.augmented_system_snapshot_sha256
    )
    assert all(
        system.atoms[bond.atom_i].residue_index
        == system.atoms[bond.atom_j].residue_index
        for bond in system.bonds
    )
    assert report["materialized_inter_residue_bond_count"] == 0
    assert report["leaving_atoms_removed"] is False
    assert report["peptide_bonds_inferred"] is False


def test_conventional_n_c_h_h2_oxt_names_are_never_linked_or_deleted() -> None:
    ingest = policy.parse_mmcif_polymer_component_terminal_leaving_policy(
        _conventional_terminal_names_source(), source_id="fixture:conventional-names"
    )
    direct_child = parse_mmcif_polymer_component_topology(
        ingest._state.child_source, source_id="fixture:conventional-names"
    )
    system = ingest.system
    names = [atom.name for atom in system.atoms]
    report = policy.analyze_mmcif_polymer_terminal_leaving_policy(ingest).to_dict()

    assert system.atom_count == direct_child.system.atom_count == 15
    assert len(system.bonds) == len(direct_child.system.bonds) == 12
    assert {"N", "C", "OXT", "H", "H2"}.issubset(names)
    assert names.count("OXT") == names.count("H") == names.count("H2") == 3
    assert serialize_all_atom_system(system) == serialize_all_atom_system(
        direct_child.system
    )
    assert ingest.child_ingest.augmented_system_snapshot_sha256 == (
        direct_child.augmented_system_snapshot_sha256
    )
    assert all(
        system.atoms[bond.atom_i].residue_index
        == system.atoms[bond.atom_j].residue_index
        for bond in system.bonds
    )
    assert report["materialized_inter_residue_bond_count"] == 0
    assert report["atom_names_used_to_infer_links"] is False
    assert report["leaving_atoms_removed"] is False


def test_policy_decision_is_independent_of_coordinates_auth_ids_and_atom_site_order() -> (
    None
):
    baseline_source = _fixture("xaa_mid_xaa.cif")
    auth_variant = baseline_source.replace(b"? 103 AX U R", b"? 999 AX V R").replace(
        b" AX U R", b" AX V R"
    )
    auth_variant = auth_variant.replace(b" MX U M", b" MX V M")
    assert baseline_source.count(b" U ") == 8
    assert auth_variant.count(b" V ") == 8
    variants = (
        _replace_once(baseline_source, b"-500.000", b"-555.000"),
        auth_variant,
        _reverse_atom_site_rows(baseline_source),
    )
    baseline = policy.parse_mmcif_polymer_component_terminal_leaving_policy(
        baseline_source, source_id="same"
    )
    expected_annotations = tuple(row.to_dict() for row in baseline.atom_annotations)
    expected_boundaries = tuple(row.to_dict() for row in baseline.sequence_boundaries)

    for source in variants:
        ingest = policy.parse_mmcif_polymer_component_terminal_leaving_policy(
            source, source_id="same"
        )
        direct_child = parse_mmcif_polymer_component_topology(
            ingest._state.child_source, source_id="same"
        )
        system = ingest.system
        assert ingest.projection_sha256 == baseline.projection_sha256
        assert tuple(row.to_dict() for row in ingest.atom_annotations) == (
            expected_annotations
        )
        assert tuple(row.to_dict() for row in ingest.sequence_boundaries) == (
            expected_boundaries
        )
        assert serialize_all_atom_system(system) == serialize_all_atom_system(
            direct_child.system
        )
        assert write_mmcif_polymer_component_topology(ingest.child_ingest).payload == (
            write_mmcif_polymer_component_topology(direct_child).payload
        )
        assert all(
            system.atoms[bond.atom_i].residue_index
            == system.atoms[bond.atom_j].residue_index
            for bond in system.bonds
        )
        report = policy.analyze_mmcif_polymer_terminal_leaving_policy(ingest).to_dict()
        assert report["coordinate_geometry_used"] is False
        assert report["auth_identity_used_for_policy"] is False
        assert report["materialized_inter_residue_bond_count"] == 0


def test_downstream_preparation_consumers_see_exact_child_and_no_promotion() -> None:
    ingest = policy.parse_mmcif_polymer_component_terminal_leaving_policy(
        _fixture("xaa_mid_xaa.cif"), source_id="fixture:consumers"
    )
    wrapper_system = ingest.system
    child_system = ingest.child_ingest.system

    wrapper_preparation = analyze_molecular_preparation(wrapper_system)
    child_preparation = analyze_molecular_preparation(child_system)
    wrapper_applicability = analyze_canonical_ingest_applicability(wrapper_system)
    child_applicability = analyze_canonical_ingest_applicability(child_system)
    wrapper_local = analyze_profile_local_preparation_evidence(wrapper_system)
    child_local = analyze_profile_local_preparation_evidence(child_system)

    assert wrapper_preparation.to_dict() == child_preparation.to_dict()
    assert wrapper_applicability.to_dict() == child_applicability.to_dict()
    assert wrapper_local.to_dict() == child_local.to_dict()
    assert wrapper_preparation.preparation_assessed is False
    assert wrapper_preparation.preparation_ready is False
    assert wrapper_preparation.claim_safe is False
    assert wrapper_applicability.canonical_ingest_supported is False
    assert wrapper_applicability.preparation_ready is False
    assert wrapper_applicability.parameterability_assessed is False
    assert wrapper_applicability.simulation_ready is False
    assert wrapper_applicability.claim_safe is False
    assert wrapper_local.profile_local_evidence_status == "not_satisfied"
    assert wrapper_local.preparation_assessed is False
    assert wrapper_local.preparation_ready is False
    assert wrapper_local.parameterability_assessed is False
    assert wrapper_local.simulation_ready is False
    assert wrapper_local.claim_safe is False


def test_flag_only_change_changes_wrapper_evidence_but_not_child() -> None:
    source = _fixture()
    changed = _replace_once(
        source,
        b"XAA Q1 N 0 N Y N Y Y N 1",
        b"XAA Q1 N 0 N N N Y Y N 1",
    )
    first = policy.parse_mmcif_polymer_component_terminal_leaving_policy(
        source, source_id="same"
    )
    second = policy.parse_mmcif_polymer_component_terminal_leaving_policy(
        changed, source_id="same"
    )
    first_child = first.child_ingest
    second_child = second.child_ingest

    assert first.projection_sha256 != second.projection_sha256
    assert first.state_sha256 != second.state_sha256
    assert first.canonical_output_sha256 != second.canonical_output_sha256
    assert first_child.component_projection_sha256 == (
        second_child.component_projection_sha256
    )
    assert first_child.topology_state_sha256 == second_child.topology_state_sha256
    assert first_child.source_binding_sha256 == second_child.source_binding_sha256
    assert serialize_all_atom_system(first.system) == serialize_all_atom_system(
        second.system
    )
    assert write_mmcif_polymer_component_topology(first_child).payload == (
        write_mmcif_polymer_component_topology(second_child).payload
    )


def test_source_identity_is_bound_outside_semantic_projection_and_state() -> None:
    source = _fixture()
    first = policy.parse_mmcif_polymer_component_terminal_leaving_policy(
        source, source_id="source:a"
    )
    second = policy.parse_mmcif_polymer_component_terminal_leaving_policy(
        source, source_id="source:b"
    )

    assert first.projection_sha256 == second.projection_sha256
    assert first.state_sha256 == second.state_sha256
    assert first.source_binding_sha256 != second.source_binding_sha256


def test_round_trip_requires_stable_wrapper_state_not_cross_source_child_provenance() -> (
    None
):
    result = policy.round_trip_mmcif_polymer_component_terminal_leaving_policy_source(
        _fixture(), source_id="same"
    )
    source_ingest = result.source_ingest
    reparsed_ingest = result.reparsed_ingest
    source_document = source_ingest.to_dict()
    reparsed_document = reparsed_ingest.to_dict()
    policy_document = policy.analyze_mmcif_polymer_terminal_leaving_policy(
        source_ingest
    ).to_dict()
    report = result.report.to_dict()

    for stage, document in (
        (source_ingest, source_document),
        (reparsed_ingest, reparsed_document),
    ):
        binding = policy._source_binding_document(stage._state)
        assert (
            binding["child_stage_proof_sha256"] == document["child_stage_proof_sha256"]
        )
        assert binding["child_stage_local_gate_results"] == {
            field: document[field] for field in policy._CHILD_STAGE_GATE_FIELDS
        }
    assert (
        policy_document["child_stage_proof_sha256"]
        == source_document["child_stage_proof_sha256"]
    )
    assert (
        report["input_child_stage_proof_sha256"]
        == source_document["child_stage_proof_sha256"]
    )
    assert (
        report["reparsed_child_stage_proof_sha256"]
        == reparsed_document["child_stage_proof_sha256"]
    )

    assert report["round_trip_preserved"] is True
    assert report["projection_equal"] is True
    assert report["state_equal"] is True
    assert report["emitted_source_reparsed_exact"] is True
    assert report["second_emission_byte_stable"] is True
    assert report["child_source_binding_equal"] is False
    assert report["child_snapshot_equal"] is False
    assert report["child_preparation_inventory_commitment_equal"] is False
    for stage_gate in (
        "input_child_stage_local_independent_projection_validated",
        "reparsed_child_stage_local_independent_projection_validated",
        "input_child_stage_local_system_byte_exact",
        "reparsed_child_stage_local_system_byte_exact",
        "input_child_stage_local_canonical_emission_byte_exact",
        "reparsed_child_stage_local_canonical_emission_byte_exact",
    ):
        assert report[stage_gate] is True
    assert result.write_result.payload == reparsed_ingest._state.full_source
    assert result.write_result.payload == result.reemitted_write_result.payload


@pytest.mark.parametrize(
    ("old", "new", "expected_code"),
    (
        (
            b"XAA Q1 N 0 N Y N Y Y N 1",
            b"XAA Q1 N 0 N 'Y' N Y Y N 1",
            "invalid_leaving_atom_flag",
        ),
        (
            b"XAA Q1 N 0 N Y N Y Y N 1",
            b"XAA Q1 N 0 N Y N . Y N 1",
            "invalid_backbone_atom_flag",
        ),
        (
            b"XAA Q1 N 0 N Y N Y Y N 1",
            b"XAA Q1 N 0 N Y N Y ? N 1",
            "invalid_n_terminal_atom_flag",
        ),
        (
            b"XAA Q2 C 0 N N N Y N Y 2",
            b"XAA Q2 C 0 N N N Y N y 2",
            "invalid_c_terminal_atom_flag",
        ),
    ),
)
def test_four_source_annotation_fields_require_bare_uppercase_y_or_n(
    old: bytes, new: bytes, expected_code: str
) -> None:
    assert _error_code(_replace_once(_fixture(), old, new)) == expected_code


def test_factory_evidence_and_stale_artifacts_are_fail_closed() -> None:
    source = _fixture()
    ingest = policy.parse_mmcif_polymer_component_terminal_leaving_policy(source)
    with pytest.raises(TypeError, match="factory-only"):
        policy.MmcifPolymerComponentTerminalLeavingPolicyIngestResult(object())
    with pytest.raises(TypeError, match="factory-only"):
        policy.MmcifPolymerComponentTerminalLeavingAtomAnnotation(object())
    with pytest.raises(TypeError, match="factory-only"):
        policy.MmcifPolymerSequenceBoundary(object())

    stale_ingest = policy.parse_mmcif_polymer_component_terminal_leaving_policy(source)
    object.__setattr__(stale_ingest._state, "annotations", ())
    with pytest.raises(
        policy.MmcifPolymerComponentTerminalLeavingPolicyError,
        match="stale_ingest_binding",
    ):
        stale_ingest.to_dict()

    stale_proof = policy.parse_mmcif_polymer_component_terminal_leaving_policy(source)
    object.__setattr__(stale_proof._state, "child_stage_proof_bytes", b"{}")
    with pytest.raises(
        policy.MmcifPolymerComponentTerminalLeavingPolicyError,
        match="stale_ingest_binding",
    ):
        stale_proof.to_dict()

    write_result = policy.write_mmcif_polymer_component_terminal_leaving_policy(ingest)
    object.__setattr__(write_result, "_payload", write_result._payload + b"#\n")
    with pytest.raises(
        policy.MmcifPolymerComponentTerminalLeavingPolicyError,
        match="stale_write_result_binding",
    ):
        _ = write_result.payload

    stale_report = policy.analyze_mmcif_polymer_terminal_leaving_policy(ingest)
    object.__setattr__(stale_report, "_document_bytes", b"{}")
    with pytest.raises(
        policy.MmcifPolymerComponentTerminalLeavingPolicyError,
        match="stale_policy_report_binding",
    ):
        stale_report.to_dict()


def test_second_child_parse_divergence_is_typed_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = policy.parse_mmcif_polymer_component_topology
    call_count = 0

    def divergent_child_parse(data: bytes, *, source_id: str = ""):
        nonlocal call_count
        call_count += 1
        effective_source_id = source_id if call_count == 1 else f"{source_id}:divergent"
        return original(data, source_id=effective_source_id)

    monkeypatch.setattr(
        policy, "parse_mmcif_polymer_component_topology", divergent_child_parse
    )
    with pytest.raises(
        policy.MmcifPolymerComponentTerminalLeavingPolicyError
    ) as captured:
        policy.parse_mmcif_polymer_component_terminal_leaving_policy(
            _fixture(), source_id="same"
        )
    assert captured.value.code == "stage_local_child_mismatch"
    assert call_count == 2


def test_crosswired_round_trip_artifacts_are_rejected() -> None:
    result = policy.round_trip_mmcif_polymer_component_terminal_leaving_policy_source(
        _fixture(), source_id="crosswire"
    )
    object.__setattr__(result, "_first", result._second)
    with pytest.raises(
        policy.MmcifPolymerComponentTerminalLeavingPolicyError,
        match="crosswired_round_trip_artifacts",
    ):
        result.to_dict()


def test_resource_limits_fail_before_promotion(monkeypatch: pytest.MonkeyPatch) -> None:
    source = _fixture()
    assert _error_code(b"") == "empty_input"
    assert _error_code(source + b"\xff") == "non_ascii_input"

    monkeypatch.setattr(
        policy,
        "MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_INPUT_BYTES",
        len(source) - 1,
    )
    assert _error_code(source) == "input_too_large"
    monkeypatch.undo()

    monkeypatch.setattr(
        policy,
        "MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_PROJECTION_BYTES",
        1,
    )
    assert _error_code(source) == "projection_too_large"
    monkeypatch.undo()

    with pytest.raises(
        policy.MmcifPolymerComponentTerminalLeavingPolicyError
    ) as captured:
        policy.parse_mmcif_polymer_component_terminal_leaving_policy(
            source,
            source_id="x"
            * (
                policy.MAX_MMCIF_POLYMER_COMPONENT_TERMINAL_LEAVING_POLICY_SOURCE_ID_BYTES
                + 1
            ),
        )
    assert captured.value.code == "source_id_too_large"
