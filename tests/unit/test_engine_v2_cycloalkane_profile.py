from __future__ import annotations

from dataclasses import replace
import hashlib
import math
from pathlib import Path

import pytest

from betelgeuze_engine_v2.molecular import (
    CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS,
    CYCLOALKANE_C3_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS,
    CYCLOALKANE_C3_C8_PREPARATION_SCOPE,
    CYCLOALKANE_C3_C8_PROFILE_ID,
    CYCLOALKANE_C3_C8_PROFILE_SCHEMA_ID,
    CYCLOALKANE_C3_C8_RULE_SET_SHA256,
    CycloalkaneC3C8ConsumerError,
    CycloalkaneC3C8ProfileError,
    CycloalkaneC3C8ProfileReport,
    analyze_canonical_ingest_applicability,
    analyze_canonical_chemistry,
    analyze_cycloalkane_c3_c8_profile,
    analyze_molecular_preparation,
    cycloalkane_c3_c8_rule_set_bytes,
    parse_sdf_v2000,
    parse_smiles,
    require_cycloalkane_c3_c8_graph_profile,
    round_trip_sdf_v2000_source,
    serialize_sdf_v2000,
)
from betelgeuze_engine_v2.molecular.observation import (
    attach_parser_observation_digest,
)


def _sdf_from_carbon_graph(
    carbon_count: int,
    carbon_edges: tuple[tuple[int, int], ...],
    *,
    data_name: str = "cycloalkane-profile",
    atom_order: tuple[int, ...] | None = None,
    remove_last_hydrogen: bool = False,
    add_extra_hydrogen: bool = False,
    hetero_carbon_index: int | None = None,
    carbon_charge_code: int = 0,
    carbon_mass_difference: int = 0,
    first_carbon_bond_order: int = 1,
) -> bytes:
    carbon_degree = [0] * carbon_count
    for atom_i, atom_j in carbon_edges:
        carbon_degree[atom_i] += 1
        carbon_degree[atom_j] += 1
    elements = ["C"] * carbon_count
    edges = list(carbon_edges)
    hydrogen_parent: list[int] = []
    for carbon_index, degree in enumerate(carbon_degree):
        for _ in range(max(0, 4 - degree)):
            hydrogen_parent.append(carbon_index)
            elements.append("H")
            edges.append((carbon_index, len(elements) - 1))
    if remove_last_hydrogen:
        removed = len(elements) - 1
        elements.pop()
        edges = [edge for edge in edges if removed not in edge]
        hydrogen_parent.pop()
    if add_extra_hydrogen:
        elements.append("H")
        edges.append((0, len(elements) - 1))
        hydrogen_parent.append(0)
    if hetero_carbon_index is not None:
        elements[hetero_carbon_index] = "O"

    natural_order = tuple(range(len(elements)))
    order = natural_order if atom_order is None else atom_order
    assert tuple(sorted(order)) == natural_order
    new_index = {old: new for new, old in enumerate(order)}
    ordered_elements = [elements[old] for old in order]
    ordered_edges = [
        tuple(sorted((new_index[atom_i], new_index[atom_j])))
        for atom_i, atom_j in edges
    ]

    atom_lines: list[str] = []
    for output_index, old_index in enumerate(order):
        angle = 2.0 * math.pi * output_index / max(1, len(order))
        radius = 1.4 if old_index < carbon_count else 2.2
        element = ordered_elements[output_index]
        mass_difference = (
            carbon_mass_difference if old_index == 0 and element == "C" else 0
        )
        charge_code = carbon_charge_code if old_index == 0 else 0
        atom_lines.append(
            f"{radius * math.cos(angle):10.4f}"
            f"{radius * math.sin(angle):10.4f}"
            f"{(0.1 if output_index % 2 else -0.1):10.4f} "
            f"{element:<3}{mass_difference:2d}{charge_code:3d}" + "  0" * 10
        )
    bond_lines: list[str] = []
    carbon_edge_set = {
        tuple(sorted((new_index[atom_i], new_index[atom_j])))
        for atom_i, atom_j in carbon_edges
    }
    first_carbon_edge = min(carbon_edge_set) if carbon_edge_set else None
    for atom_i, atom_j in sorted(ordered_edges):
        order_code = (
            first_carbon_bond_order
            if first_carbon_edge is not None and (atom_i, atom_j) == first_carbon_edge
            else 1
        )
        bond_lines.append(f"{atom_i + 1:3d}{atom_j + 1:3d}{order_code:3d}{0:3d}")
    counts = (
        f"{len(ordered_elements):3d}{len(ordered_edges):3d}"
        "  0  0  0  0  0  0  0  0999 V2000"
    )
    return (
        "\n".join(
            (
                data_name,
                "betelgeuze-v2",
                "graph-local cycloalkane profile fixture",
                counts,
                *atom_lines,
                *bond_lines,
                "M  END",
                "$$$$",
                "",
            )
        )
    ).encode("ascii")


def _ring_edges(carbon_count: int) -> tuple[tuple[int, int], ...]:
    return tuple(
        sorted(
            {
                tuple(sorted((index, (index + 1) % carbon_count)))
                for index in range(carbon_count)
            }
        )
    )


def _ring_source(carbon_count: int, **kwargs: object) -> bytes:
    return _sdf_from_carbon_graph(
        carbon_count,
        _ring_edges(carbon_count),
        data_name=f"cycloalkane-c{carbon_count}",
        **kwargs,
    )


@pytest.mark.parametrize("carbon_count", range(3, 9))
def test_c3_c8_exact_graph_profiles_are_available(carbon_count: int) -> None:
    system = parse_sdf_v2000(_ring_source(carbon_count)).system
    report = analyze_cycloalkane_c3_c8_profile(system)
    document = report.to_dict()

    assert report.status == "available"
    assert report.profile_chemistry_supported is True
    assert report.profile_graph_preparation_ready is True
    assert report.failed_constraint_codes == ()
    assert report.matches_system(system) is True
    assert document["schema_id"] == CYCLOALKANE_C3_C8_PROFILE_SCHEMA_ID
    assert document["profile_id"] == CYCLOALKANE_C3_C8_PROFILE_ID
    assert document["profile_preparation_scope"] == (
        CYCLOALKANE_C3_C8_PREPARATION_SCOPE
    )
    assert tuple(document["eligible_consumer_ids"]) == (
        CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS
    )
    assert document["carbon_atom_count"] == carbon_count
    assert document["hydrogen_atom_count"] == 2 * carbon_count
    assert document["molecular_formula"] == f"C{carbon_count}H{2 * carbon_count}"
    assert document["graph_projection"]["carbon_cycle_exact"] is True
    assert document["graph_projection"]["degrees_exact"] is True
    assert type(document["profile_chemistry_supported"]) is bool
    assert type(document["profile_graph_preparation_ready"]) is bool
    assert document["global_molecular_preparation_ready"] is False
    assert document["parameterability_assessed"] is False
    assert document["parameterizable"] is False
    assert document["physics_supported"] is False
    assert document["runtime_eligible"] is False
    assert document["execution_authorized"] is False
    assert document["energy_evaluation_authorized"] is False
    assert document["force_evaluation_authorized"] is False
    assert document["minimization_authorized"] is False
    assert document["simulation_ready"] is False
    assert document["claim_safe"] is False
    assert (
        "profile_graph_preparation_is_not_global_molecular_preparation"
        in (document["blockers"])
    )
    assert (
        require_cycloalkane_c3_c8_graph_profile(
            system,
            consumer_id=CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS[0],
        ).to_dict()
        == document
    )


def test_rule_set_and_graph_digests_are_bound() -> None:
    system = parse_sdf_v2000(_ring_source(4)).system
    report = analyze_cycloalkane_c3_c8_profile(system)
    document = report.to_dict()

    assert hashlib.sha256(cycloalkane_c3_c8_rule_set_bytes()).hexdigest() == (
        CYCLOALKANE_C3_C8_RULE_SET_SHA256
    )
    assert document["rule_set_sha256"] == CYCLOALKANE_C3_C8_RULE_SET_SHA256
    assert document["chemistry_report_sha256"] == (
        document["chemistry_report_sha256"].lower()
    )
    assert document["preparation_report_sha256"] == (
        document["preparation_report_sha256"].lower()
    )
    assert len(document["graph_projection_sha256"]) == 64
    assert len(document["report_sha256"]) == 64
    assert document["chemistry_report_schema_version"] == "1.2.0"
    assert document["preparation_report_schema_version"] == "1.4.0"
    assert document["chemistry_report_sha256"] == (
        analyze_canonical_chemistry(system).report_sha256
    )
    assert document["preparation_report_sha256"] == (
        analyze_molecular_preparation(system).report_sha256
    )
    assert document["parser_observation_schema_id"] == (
        "betelgeuze.parser_chemical_state_observation/1.0.0"
    )
    assert document["parser_observation_sha256_equal"] is True
    assert (
        document["attached_parser_observation_sha256"]
        == (document["recomputed_parser_observation_sha256"])
    )
    assert document["graph_projection_identity_semantics"] == (
        CYCLOALKANE_C3_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS
    )


def test_atom_order_changes_do_not_change_profile_admission() -> None:
    canonical = parse_sdf_v2000(_ring_source(5)).system
    reversed_source = _ring_source(5, atom_order=tuple(reversed(range(15))))
    reversed_system = parse_sdf_v2000(reversed_source).system
    first = analyze_cycloalkane_c3_c8_profile(canonical)
    second = analyze_cycloalkane_c3_c8_profile(reversed_system)

    assert first.status == second.status == "available"
    assert first.to_dict()["molecular_formula"] == second.to_dict()["molecular_formula"]
    assert first.graph_projection_sha256 != second.graph_projection_sha256
    assert first.to_dict()["graph_projection_identity_semantics"].startswith(
        "source_indexed_exact_projection"
    )


@pytest.mark.parametrize(
    ("source", "failed_code"),
    [
        (_ring_source(2), "carbon_count_c3_c8"),
        (_ring_source(9), "carbon_count_c3_c8"),
        (
            _sdf_from_carbon_graph(4, ((0, 1), (1, 2), (0, 2), (0, 3))),
            "carbon_subgraph_connected_simple_cycle",
        ),
        (
            _sdf_from_carbon_graph(
                5,
                ((0, 1), (1, 2), (0, 2), (0, 3), (3, 4), (0, 4)),
            ),
            "exact_cycloalkane_formula_c_n_h_2n",
        ),
        (_ring_source(4, first_carbon_bond_order=2), "single_bonds_only"),
        (
            _ring_source(4, remove_last_hydrogen=True),
            "exact_cycloalkane_formula_c_n_h_2n",
        ),
        (
            _ring_source(4, add_extra_hydrogen=True),
            "exact_cycloalkane_formula_c_n_h_2n",
        ),
        (_ring_source(4, hetero_carbon_index=0), "elements_h_c_only"),
        (
            _ring_source(4, carbon_charge_code=3),
            "formal_charges_source_observed_known_zero",
        ),
        (
            _sdf_from_carbon_graph(4, ((0, 1), (1, 2), (0, 2))),
            "single_component",
        ),
    ],
)
def test_outside_profile_graphs_fail_closed(source: bytes, failed_code: str) -> None:
    system = parse_sdf_v2000(source).system
    report = analyze_cycloalkane_c3_c8_profile(system)

    assert report.status == "unsupported"
    assert report.profile_chemistry_supported is False
    assert report.profile_graph_preparation_ready is False
    assert failed_code in report.failed_constraint_codes
    with pytest.raises(CycloalkaneC3C8ProfileError) as exc_info:
        require_cycloalkane_c3_c8_graph_profile(
            system,
            consumer_id=CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS[0],
        )
    assert exc_info.value.report.to_dict() == report.to_dict()


def test_isotope_state_is_outside_the_profile() -> None:
    system = parse_sdf_v2000(_ring_source(4)).system
    atoms = list(system.atoms)
    atoms[0] = replace(atoms[0], isotope_mass_number=13)
    report = analyze_cycloalkane_c3_c8_profile(replace(system, atoms=tuple(atoms)))

    assert report.profile_graph_preparation_ready is False
    assert "isotopes_absent" in report.failed_constraint_codes


def test_declared_atom_state_and_residue_mutations_fail_closed() -> None:
    system = parse_sdf_v2000(_ring_source(4)).system

    mutations: list[tuple[object, str]] = []

    atoms = list(system.atoms)
    atoms[0] = replace(atoms[0], atom_map=1)
    mutations.append((replace(system, atoms=tuple(atoms)), "atom_maps_absent"))

    atoms = list(system.atoms)
    atoms[0] = replace(atoms[0], partial_charge_e=0.0)
    mutations.append((replace(system, atoms=tuple(atoms)), "partial_charges_absent"))

    atoms = list(system.atoms)
    atoms[0] = replace(atoms[0], stereo="R")
    mutations.append((replace(system, atoms=tuple(atoms)), "typed_stereo_absent"))

    atoms = list(system.atoms)
    metadata = dict(atoms[0].metadata)
    metadata["formal_charge_source"] = "forged_zero_charge_marker"
    atoms[0] = replace(atoms[0], metadata=metadata)
    mutations.append(
        (
            replace(system, atoms=tuple(atoms)),
            "formal_charges_source_observed_known_zero",
        )
    )

    residues = list(system.residues)
    residues[0] = replace(residues[0], name="MOL")
    mutations.append(
        (replace(system, residues=tuple(residues)), "single_nonpolymer_residue")
    )

    for mutated, failed_code in mutations:
        rebound = attach_parser_observation_digest(mutated)
        report = analyze_cycloalkane_c3_c8_profile(rebound)
        assert report.status in {"invalid", "unsupported"}
        assert report.profile_graph_preparation_ready is False
        assert failed_code in report.failed_constraint_codes


def test_aromatic_state_is_outside_the_nonaromatic_profile() -> None:
    system = parse_sdf_v2000(_ring_source(4)).system
    atoms = tuple(
        replace(atom, aromatic=True) if atom.element == "C" else atom
        for atom in system.atoms
    )
    bonds = tuple(
        replace(bond, order=1.5, aromatic=True)
        if system.atoms[bond.atom_i].element == "C"
        and system.atoms[bond.atom_j].element == "C"
        else bond
        for bond in system.bonds
    )
    mutated = attach_parser_observation_digest(
        replace(system, atoms=atoms, bonds=bonds)
    )
    report = analyze_cycloalkane_c3_c8_profile(mutated)

    assert report.status in {"invalid", "unsupported"}
    assert report.profile_graph_preparation_ready is False
    assert "aromaticity_absent" in report.failed_constraint_codes
    assert "single_bonds_only" in report.failed_constraint_codes


def test_fused_bicyclic_graph_is_outside_the_profile() -> None:
    source = _sdf_from_carbon_graph(
        4,
        ((0, 1), (0, 2), (1, 2), (0, 3), (1, 3)),
    )
    report = analyze_cycloalkane_c3_c8_profile(parse_sdf_v2000(source).system)

    assert report.status == "unsupported"
    assert "carbon_subgraph_connected_simple_cycle" in report.failed_constraint_codes


def test_consumer_allowlist_is_enforced_by_the_typed_gate() -> None:
    system = parse_sdf_v2000(_ring_source(3)).system

    with pytest.raises(TypeError, match="consumer_id"):
        require_cycloalkane_c3_c8_graph_profile(system)  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="exact string"):
        require_cycloalkane_c3_c8_graph_profile(
            system,
            consumer_id=1,  # type: ignore[arg-type]
        )
    with pytest.raises(CycloalkaneC3C8ConsumerError) as exc_info:
        require_cycloalkane_c3_c8_graph_profile(
            system,
            consumer_id="runtime_force_field",
        )
    assert exc_info.value.consumer_id == "runtime_force_field"
    assert exc_info.value.eligible_consumer_ids == (
        CYCLOALKANE_C3_C8_AUDIT_CONSUMER_IDS
    )


def test_parser_observation_crosswire_is_explicitly_invalid() -> None:
    c3 = parse_sdf_v2000(_ring_source(3)).system
    c4 = parse_sdf_v2000(_ring_source(4)).system
    metadata = dict(c4.provenance.metadata)
    metadata["parser_observation_sha256"] = c3.provenance.metadata[
        "parser_observation_sha256"
    ]
    crosswired = replace(c4, provenance=replace(c4.provenance, metadata=metadata))
    document = analyze_cycloalkane_c3_c8_profile(crosswired).to_dict()

    assert document["status"] == "invalid"
    assert document["parser_observation_self_consistent"] is False
    assert document["parser_observation_sha256_equal"] is False
    assert (
        document["attached_parser_observation_sha256"]
        != (document["recomputed_parser_observation_sha256"])
    )
    assert "parser_observation_digest_bound" in document["failed_constraint_codes"]


def test_smiles_adapter_hydrogens_are_not_source_observed_profile_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rdkit import rdBase

    from betelgeuze_engine_v2.molecular import smiles as smiles_module

    monkeypatch.setattr(
        smiles_module,
        "_SUPPORTED_RDKIT_VERSIONS",
        frozenset({rdBase.rdkitVersion}),
    )
    system = parse_smiles(b"C1CC1").system
    report = analyze_cycloalkane_c3_c8_profile(system)

    assert report.status == "unsupported"
    assert "sdf_v2000_source_pedigree" in report.failed_constraint_codes
    assert "source_observed_hydrogens_only" in report.failed_constraint_codes


def test_existing_cyclobutane_boundary_remains_negative_for_acyclic_profile() -> None:
    source = Path(
        "tests/fixtures/v2_2_linear_alkane/cyclobutane_explicit_h.sdf"
    ).read_bytes()
    system = parse_sdf_v2000(source).system
    existing = analyze_canonical_ingest_applicability(system)
    additive = analyze_cycloalkane_c3_c8_profile(system)

    assert existing.canonical_ingest_supported is False
    assert existing.failed_constraint_codes == ("acyclic_graph",)
    assert additive.status == "available"
    assert additive.profile_graph_preparation_ready is True


def test_sdf_writer_round_trip_preserves_cyclobutane_profile_evidence() -> None:
    source = Path(
        "tests/fixtures/v2_2_linear_alkane/cyclobutane_explicit_h.sdf"
    ).read_bytes()
    result = round_trip_sdf_v2000_source(source, source_id="cyclobutane-profile")
    before = analyze_cycloalkane_c3_c8_profile(result.source_ingest.system)
    after = analyze_cycloalkane_c3_c8_profile(result.reparsed_ingest.system)

    assert before.status == after.status == "available"
    assert before.to_dict()["molecular_formula"] == "C4H8"
    assert after.to_dict()["molecular_formula"] == "C4H8"
    assert result.write_result.payload == serialize_sdf_v2000(
        result.reparsed_ingest.system
    )


def test_hydrogen_origin_and_provenance_tamper_fail_closed() -> None:
    system = parse_sdf_v2000(_ring_source(4)).system
    hydrogen_index = next(atom.index for atom in system.atoms if atom.element == "H")
    metadata = dict(system.atoms[hydrogen_index].metadata)
    metadata["hydrogen_origin"] = "implicit"
    atoms = list(system.atoms)
    atoms[hydrogen_index] = replace(atoms[hydrogen_index], metadata=metadata)
    hydrogen_tampered = replace(system, atoms=tuple(atoms))
    hydrogen_report = analyze_cycloalkane_c3_c8_profile(hydrogen_tampered)
    assert hydrogen_report.profile_graph_preparation_ready is False
    assert "source_observed_hydrogens_only" in hydrogen_report.failed_constraint_codes

    provenance = replace(system.provenance, source_sha256="0" * 64)
    provenance_tampered = replace(system, provenance=provenance)
    provenance_report = analyze_cycloalkane_c3_c8_profile(provenance_tampered)
    assert provenance_report.status == "invalid"
    assert provenance_report.profile_graph_preparation_ready is False


def test_report_is_factory_only_snapshot_bound_and_exact_type_checked() -> None:
    system = parse_sdf_v2000(_ring_source(3)).system
    report = analyze_cycloalkane_c3_c8_profile(system)

    with pytest.raises(TypeError, match="factory-only"):
        CycloalkaneC3C8ProfileReport(
            canonical_system_bytes=b"x",
            canonical_system_sha256=hashlib.sha256(b"x").hexdigest(),
        )
    assert report.matches_system(system) is True
    object.__setattr__(report, "_canonical_system_sha256", "0" * 64)
    with pytest.raises(ValueError, match="snapshot digest"):
        _ = report.status


def test_report_snapshot_and_returned_documents_resist_live_tamper() -> None:
    system = parse_sdf_v2000(_ring_source(4)).system
    report = analyze_cycloalkane_c3_c8_profile(system)
    original = report.to_dict()

    returned = report.to_dict()
    returned["status"] = "unsupported"
    returned["graph_projection"]["carbon_cycle_exact"] = False
    returned["blockers"].clear()
    assert report.to_dict() == original

    atoms = list(system.atoms)
    atoms[0] = replace(atoms[0], atom_map=7)
    live_mutation = attach_parser_observation_digest(
        replace(system, atoms=tuple(atoms))
    )
    assert report.status == "available"
    assert report.matches_system(live_mutation) is False


def test_same_count_source_order_crosswire_is_distinct() -> None:
    first_system = parse_sdf_v2000(_ring_source(4)).system
    second_system = parse_sdf_v2000(
        _ring_source(4, atom_order=tuple(reversed(range(12))))
    ).system
    first = analyze_cycloalkane_c3_c8_profile(first_system)
    second = analyze_cycloalkane_c3_c8_profile(second_system)

    assert first.status == second.status == "available"
    assert first.report_sha256 != second.report_sha256
    assert first.graph_projection_sha256 != second.graph_projection_sha256
    assert first.matches_system(second_system) is False


def test_rule_set_bytes_are_immutable_and_sha_stable() -> None:
    original = cycloalkane_c3_c8_rule_set_bytes()
    local_copy = bytearray(original)
    local_copy[-2] = ord("X")

    assert bytes(local_copy) != cycloalkane_c3_c8_rule_set_bytes()
    assert hashlib.sha256(cycloalkane_c3_c8_rule_set_bytes()).hexdigest() == (
        CYCLOALKANE_C3_C8_RULE_SET_SHA256
    )
