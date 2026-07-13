from __future__ import annotations

from dataclasses import replace
import hashlib
import math

import pytest

from betelgeuze_engine_v2.molecular import (
    TERMINAL_MONOALKENE_C2_C8_AUDIT_CONSUMER_IDS,
    TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS,
    TERMINAL_MONOALKENE_C2_C8_PREPARATION_SCOPE,
    TERMINAL_MONOALKENE_C2_C8_PROFILE_ID,
    TERMINAL_MONOALKENE_C2_C8_PROFILE_SCHEMA_ID,
    TERMINAL_MONOALKENE_C2_C8_RULE_SET_SHA256,
    TerminalMonoalkeneC2C8ConsumerError,
    TerminalMonoalkeneC2C8ProfileError,
    TerminalMonoalkeneC2C8ProfileReport,
    analyze_canonical_chemistry,
    analyze_canonical_ingest_applicability,
    analyze_linear_alkane_c1_c4_force_field_applicability,
    analyze_molecular_preparation,
    analyze_terminal_monoalkene_c2_c8_profile,
    parse_sdf_v2000,
    parse_smiles,
    require_terminal_monoalkene_c2_c8_graph_profile,
    round_trip_sdf_v2000_source,
    serialize_sdf_v2000,
    terminal_monoalkene_c2_c8_rule_set_bytes,
)
from betelgeuze_engine_v2.molecular.observation import (
    attach_parser_observation_digest,
)


def _sdf_from_carbon_graph(
    carbon_count: int,
    carbon_edges: tuple[tuple[int, int, int], ...],
    *,
    data_name: str = "terminal-monoalkene-profile",
    hydrogen_counts: tuple[int, ...] | None = None,
    atom_order: tuple[int, ...] | None = None,
    remove_last_hydrogen: bool = False,
    add_extra_hydrogen: bool = False,
    hetero_carbon_index: int | None = None,
    charge_codes: tuple[int, ...] | None = None,
    first_carbon_hydrogen_bond_type: int = 1,
    z_scale: float = 0.1,
) -> bytes:
    assert carbon_count >= 1
    assert all(
        0 <= atom_i < atom_j < carbon_count and bond_type in {1, 2, 3, 4}
        for atom_i, atom_j, bond_type in carbon_edges
    )
    if hydrogen_counts is None:
        integer_valence = [0] * carbon_count
        for atom_i, atom_j, bond_type in carbon_edges:
            assert bond_type in {1, 2, 3}
            integer_valence[atom_i] += bond_type
            integer_valence[atom_j] += bond_type
        hydrogen_counts = tuple(max(0, 4 - value) for value in integer_valence)
    assert len(hydrogen_counts) == carbon_count
    elements = ["C"] * carbon_count
    edges = list(carbon_edges)
    first_ch_edge: tuple[int, int] | None = None
    for carbon_index, count in enumerate(hydrogen_counts):
        for _ in range(count):
            elements.append("H")
            edge = (carbon_index, len(elements) - 1)
            first_ch_edge = edge if first_ch_edge is None else first_ch_edge
            edges.append((edge[0], edge[1], 1))
    if remove_last_hydrogen:
        removed = len(elements) - 1
        elements.pop()
        edges = [edge for edge in edges if removed not in edge[:2]]
    if add_extra_hydrogen:
        elements.append("H")
        edges.append((0, len(elements) - 1, 1))
    if hetero_carbon_index is not None:
        elements[hetero_carbon_index] = "O"
    if first_ch_edge is not None and first_carbon_hydrogen_bond_type != 1:
        edges = [
            (
                atom_i,
                atom_j,
                first_carbon_hydrogen_bond_type
                if (atom_i, atom_j) == first_ch_edge
                else bond_type,
            )
            for atom_i, atom_j, bond_type in edges
        ]

    natural_order = tuple(range(len(elements)))
    order = natural_order if atom_order is None else atom_order
    assert tuple(sorted(order)) == natural_order
    new_index = {old: new for new, old in enumerate(order)}
    ordered_elements = [elements[old] for old in order]
    ordered_edges = [
        (*sorted((new_index[atom_i], new_index[atom_j])), bond_type)
        for atom_i, atom_j, bond_type in edges
    ]
    charges = (0,) * carbon_count if charge_codes is None else charge_codes
    assert len(charges) == carbon_count

    atom_lines: list[str] = []
    for output_index, old_index in enumerate(order):
        angle = 2.0 * math.pi * output_index / max(1, len(order))
        radius = 1.5 if old_index < carbon_count else 2.4
        element = ordered_elements[output_index]
        charge_code = charges[old_index] if old_index < carbon_count else 0
        atom_lines.append(
            f"{radius * math.cos(angle):10.4f}"
            f"{radius * math.sin(angle):10.4f}"
            f"{(z_scale * ((output_index % 3) - 1)):10.4f} "
            f"{element:<3}{0:2d}{charge_code:3d}" + "  0" * 10
        )
    bond_lines = [
        f"{atom_i + 1:3d}{atom_j + 1:3d}{bond_type:3d}{0:3d}"
        for atom_i, atom_j, bond_type in sorted(ordered_edges)
    ]
    counts = (
        f"{len(ordered_elements):3d}{len(ordered_edges):3d}"
        "  0  0  0  0  0  0  0  0999 V2000"
    )
    return (
        "\n".join(
            (
                data_name,
                "betelgeuze-v2",
                "graph-local terminal monoalkene profile fixture",
                counts,
                *atom_lines,
                *bond_lines,
                "M  END",
                "$$$$",
                "",
            )
        )
    ).encode("ascii")


def _terminal_edges(carbon_count: int) -> tuple[tuple[int, int, int], ...]:
    if carbon_count == 1:
        return ()
    return tuple(
        (index, index + 1, 2 if index == 0 else 1) for index in range(carbon_count - 1)
    )


def _terminal_source(carbon_count: int, **kwargs: object) -> bytes:
    return _sdf_from_carbon_graph(
        carbon_count,
        _terminal_edges(carbon_count),
        data_name=f"terminal-monoalkene-c{carbon_count}",
        **kwargs,
    )


@pytest.mark.parametrize("carbon_count", range(2, 9))
def test_c2_c8_terminal_monoalkene_profiles_are_available(
    carbon_count: int,
) -> None:
    system = parse_sdf_v2000(_terminal_source(carbon_count)).system
    report = analyze_terminal_monoalkene_c2_c8_profile(system)
    document = report.to_dict()

    assert report.status == "available"
    assert report.profile_chemistry_supported is True
    assert report.profile_graph_preparation_ready is True
    assert report.failed_constraint_codes == ()
    assert report.matches_system(system) is True
    assert document["schema_id"] == TERMINAL_MONOALKENE_C2_C8_PROFILE_SCHEMA_ID
    assert document["profile_id"] == TERMINAL_MONOALKENE_C2_C8_PROFILE_ID
    assert document["profile_preparation_scope"] == (
        TERMINAL_MONOALKENE_C2_C8_PREPARATION_SCOPE
    )
    assert document["eligible_consumer_ids"] == list(
        TERMINAL_MONOALKENE_C2_C8_AUDIT_CONSUMER_IDS
    )
    assert document["carbon_atom_count"] == carbon_count
    assert document["hydrogen_atom_count"] == 2 * carbon_count
    assert document["molecular_formula"] == f"C{carbon_count}H{2 * carbon_count}"
    assert document["graph_projection"]["carbon_path_exact"] is True
    assert document["graph_projection"]["terminal_double_exact"] is True
    assert document["source_bond_order_ledger_closed"] is True
    assert document["source_atom_marker_ledger_closed"] is True
    assert document["atom_bond_order_valence_ledger_closed"] is True
    assert type(document["double_bond_index"]) is int
    assert type(document["double_bond_source_index"]) is int
    assert document["terminal_double_endpoint_count"] == (2 if carbon_count == 2 else 1)
    assert document["generic_chemistry_supported"] is False
    for field in (
        "generic_molecular_preparation_ready",
        "global_molecular_preparation_ready",
        "e_z_assessed",
        "cip_assessed",
        "stereochemistry_applicability_assessed",
        "source_bond_order_independently_validated",
        "electronic_structure_assessed",
        "coordinate_linearity_assessed",
        "protonation_assessed",
        "tautomer_assessed",
        "geometry_quality_assessed",
        "parameterability_assessed",
        "parameterizable",
        "physics_supported",
        "runtime_eligible",
        "execution_authorized",
        "energy_evaluation_authorized",
        "force_evaluation_authorized",
        "minimization_authorized",
        "simulation_ready",
        "claim_safe",
    ):
        assert document[field] is False
    gated = require_terminal_monoalkene_c2_c8_graph_profile(
        system,
        consumer_id=TERMINAL_MONOALKENE_C2_C8_AUDIT_CONSUMER_IDS[0],
    )
    assert gated.report_sha256 == report.report_sha256


def test_rule_generic_report_parser_and_projection_bindings_are_explicit() -> None:
    system = parse_sdf_v2000(_terminal_source(4)).system
    document = analyze_terminal_monoalkene_c2_c8_profile(system).to_dict()

    assert TERMINAL_MONOALKENE_C2_C8_PROFILE_ID == (
        "source_observed_explicit_h_neutral_unbranched_terminal_monoalkene_c2_c8/1.0.0"
    )
    assert TERMINAL_MONOALKENE_C2_C8_PREPARATION_SCOPE == (
        "source_observed_graph_local_unbranched_terminal_monoalkene_identity_"
        "and_bond_order_valence_ledger_only"
    )
    assert (
        hashlib.sha256(terminal_monoalkene_c2_c8_rule_set_bytes()).hexdigest()
        == TERMINAL_MONOALKENE_C2_C8_RULE_SET_SHA256
    )
    assert document["rule_set_sha256"] == (TERMINAL_MONOALKENE_C2_C8_RULE_SET_SHA256)
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
        TERMINAL_MONOALKENE_C2_C8_GRAPH_PROJECTION_IDENTITY_SEMANTICS
    )
    assert len(document["graph_projection_sha256"]) == 64
    assert len(document["report_sha256"]) == 64


def test_atom_order_changes_admission_but_not_source_indexed_identity_semantics() -> (
    None
):
    first_system = parse_sdf_v2000(_terminal_source(5)).system
    second_source = _terminal_source(5, atom_order=tuple(reversed(range(15))))
    second_system = parse_sdf_v2000(second_source).system
    first = analyze_terminal_monoalkene_c2_c8_profile(first_system)
    second = analyze_terminal_monoalkene_c2_c8_profile(second_system)

    assert first.status == second.status == "available"
    assert first.to_dict()["molecular_formula"] == second.to_dict()["molecular_formula"]
    assert first.graph_projection_sha256 != second.graph_projection_sha256
    assert first.report_sha256 != second.report_sha256


def test_unbranched_path_is_not_coordinate_linearity() -> None:
    first = analyze_terminal_monoalkene_c2_c8_profile(
        parse_sdf_v2000(_terminal_source(4, z_scale=0.0)).system
    )
    second = analyze_terminal_monoalkene_c2_c8_profile(
        parse_sdf_v2000(_terminal_source(4, z_scale=3.0)).system
    )

    assert first.status == second.status == "available"
    assert first.to_dict()["unbranched_path_definition"].endswith(
        "not_coordinate_geometry"
    )
    assert first.report_sha256 != second.report_sha256
    assert first.to_dict()["coordinate_linearity_assessed"] is False
    assert second.to_dict()["coordinate_linearity_assessed"] is False


def test_product_size_bounds_are_explicit_and_c9_fails_only_the_bound() -> None:
    c1 = analyze_terminal_monoalkene_c2_c8_profile(
        parse_sdf_v2000(_sdf_from_carbon_graph(1, (), hydrogen_counts=(2,))).system
    )
    c9 = analyze_terminal_monoalkene_c2_c8_profile(
        parse_sdf_v2000(_terminal_source(9)).system
    )

    assert c1.status == "unsupported"
    assert "carbon_count_c2_c8" in c1.failed_constraint_codes
    assert c9.status == "unsupported"
    assert c9.failed_constraint_codes == ("carbon_count_c2_c8",)
    assert (
        "profile_bound_c2_c8_is_not_general_alkene_support_or_c9_chemistry_rejection"
        in c9.blockers
    )


@pytest.mark.parametrize(
    ("source", "failed_code"),
    [
        (
            _sdf_from_carbon_graph(
                4,
                ((0, 1, 1), (1, 2, 2), (2, 3, 1)),
                data_name="internal-two-butene",
            ),
            "exact_one_terminal_carbon_double_bond",
        ),
        (
            _sdf_from_carbon_graph(
                4,
                ((0, 1, 2), (1, 2, 1), (1, 3, 1)),
                data_name="branched-isobutene",
            ),
            "carbon_subgraph_connected_simple_path",
        ),
        (
            _sdf_from_carbon_graph(2, ((0, 1, 1),), data_name="ethane"),
            "exact_terminal_monoalkene_formula_c_n_h_2n",
        ),
        (
            _sdf_from_carbon_graph(
                2,
                ((0, 1, 1),),
                hydrogen_counts=(2, 2),
                data_name="all-single-c2h4",
            ),
            "exact_one_terminal_carbon_double_bond",
        ),
        (
            _sdf_from_carbon_graph(
                4,
                ((0, 1, 2), (1, 2, 1), (2, 3, 2)),
                data_name="butadiene",
            ),
            "exact_terminal_monoalkene_formula_c_n_h_2n",
        ),
        (
            _sdf_from_carbon_graph(
                3,
                ((0, 1, 3), (1, 2, 1)),
                data_name="propyne",
            ),
            "source_sdf_bond_order_ledger_exact",
        ),
        (
            _sdf_from_carbon_graph(
                4,
                ((0, 1, 2), (1, 2, 1), (2, 3, 1), (0, 3, 1)),
                data_name="cyclobutene",
            ),
            "carbon_subgraph_connected_simple_path",
        ),
        (
            _sdf_from_carbon_graph(
                3,
                ((0, 1, 2),),
                hydrogen_counts=(2, 1, 3),
                data_name="disconnected-propene",
            ),
            "single_component",
        ),
        (
            _terminal_source(3, first_carbon_hydrogen_bond_type=2),
            "source_sdf_bond_order_ledger_exact",
        ),
        (
            _sdf_from_carbon_graph(
                4,
                _terminal_edges(4),
                hydrogen_counts=(1, 2, 2, 3),
                data_name="same-formula-hydrogen-redistribution",
            ),
            "exact_atom_bond_order_valence_ledger",
        ),
    ],
)
def test_outside_profile_graphs_fail_closed(source: bytes, failed_code: str) -> None:
    system = parse_sdf_v2000(source).system
    report = analyze_terminal_monoalkene_c2_c8_profile(system)

    assert report.status == "unsupported"
    assert report.profile_chemistry_supported is False
    assert report.profile_graph_preparation_ready is False
    assert failed_code in report.failed_constraint_codes
    with pytest.raises(TerminalMonoalkeneC2C8ProfileError) as exc_info:
        require_terminal_monoalkene_c2_c8_graph_profile(
            system,
            consumer_id=TERMINAL_MONOALKENE_C2_C8_AUDIT_CONSUMER_IDS[0],
        )
    assert exc_info.value.report.report_sha256 == report.report_sha256


@pytest.mark.parametrize(
    ("source", "failed_code"),
    [
        (
            _terminal_source(3, remove_last_hydrogen=True),
            "exact_terminal_monoalkene_formula_c_n_h_2n",
        ),
        (
            _terminal_source(3, add_extra_hydrogen=True),
            "exact_terminal_monoalkene_formula_c_n_h_2n",
        ),
        (_terminal_source(3, hetero_carbon_index=2), "elements_h_c_only"),
        (
            _terminal_source(3, charge_codes=(3, 0, 0)),
            "formal_charges_source_observed_known_zero",
        ),
        (
            _terminal_source(3, charge_codes=(3, 5, 0)),
            "formal_charges_source_observed_known_zero",
        ),
    ],
)
def test_source_state_boundaries_fail_closed(source: bytes, failed_code: str) -> None:
    report = analyze_terminal_monoalkene_c2_c8_profile(parse_sdf_v2000(source).system)

    assert report.status == "unsupported"
    assert failed_code in report.failed_constraint_codes


def test_isotope_map_partial_charge_stereo_and_charge_origin_tamper_fail_closed() -> (
    None
):
    system = parse_sdf_v2000(_terminal_source(3)).system
    mutations: list[tuple[object, str]] = []

    atoms = list(system.atoms)
    atoms[0] = replace(atoms[0], isotope_mass_number=13)
    mutations.append((replace(system, atoms=tuple(atoms)), "isotopes_absent"))

    atoms = list(system.atoms)
    atoms[0] = replace(atoms[0], atom_map=1)
    mutations.append((replace(system, atoms=tuple(atoms)), "atom_maps_absent"))

    atoms = list(system.atoms)
    atoms[0] = replace(atoms[0], partial_charge_e=0.0)
    mutations.append((replace(system, atoms=tuple(atoms)), "partial_charges_absent"))

    bonds = list(system.bonds)
    bonds[0] = replace(bonds[0], stereo="E")
    mutations.append((replace(system, bonds=tuple(bonds)), "typed_stereo_absent"))

    atoms = list(system.atoms)
    metadata = dict(atoms[0].metadata)
    metadata["formal_charge_source"] = "sdf_v2000_m_chg"
    atoms[0] = replace(atoms[0], metadata=metadata)
    mutations.append(
        (
            replace(system, atoms=tuple(atoms)),
            "formal_charges_source_observed_known_zero",
        )
    )

    hydrogen_index = next(atom.index for atom in system.atoms if atom.element == "H")
    atoms = list(system.atoms)
    metadata = dict(atoms[hydrogen_index].metadata)
    metadata["hydrogen_origin"] = "implicit"
    atoms[hydrogen_index] = replace(atoms[hydrogen_index], metadata=metadata)
    mutations.append(
        (
            replace(system, atoms=tuple(atoms)),
            "source_observed_hydrogens_only",
        )
    )

    for mutated, failed_code in mutations:
        rebound = attach_parser_observation_digest(mutated)
        report = analyze_terminal_monoalkene_c2_c8_profile(rebound)
        assert report.status in {"invalid", "unsupported"}
        assert report.profile_graph_preparation_ready is False
        assert failed_code in report.failed_constraint_codes


def test_aromatic_and_source_bond_metadata_tamper_fail_closed() -> None:
    system = parse_sdf_v2000(_terminal_source(3)).system
    atoms = list(system.atoms)
    bonds = list(system.bonds)
    atoms[0] = replace(atoms[0], aromatic=True)
    atoms[1] = replace(atoms[1], aromatic=True)
    bonds[0] = replace(bonds[0], order=1.5, aromatic=True)
    aromatic = attach_parser_observation_digest(
        replace(system, atoms=tuple(atoms), bonds=tuple(bonds))
    )
    aromatic_report = analyze_terminal_monoalkene_c2_c8_profile(aromatic)
    assert "aromaticity_absent" in aromatic_report.failed_constraint_codes
    assert (
        "source_sdf_bond_order_ledger_exact" in aromatic_report.failed_constraint_codes
    )

    bonds = list(system.bonds)
    metadata = dict(bonds[0].metadata)
    metadata["sdf_bond_type"] = 1
    bonds[0] = replace(bonds[0], metadata=metadata)
    metadata_tamper = attach_parser_observation_digest(
        replace(system, bonds=tuple(bonds))
    )
    metadata_report = analyze_terminal_monoalkene_c2_c8_profile(metadata_tamper)
    assert (
        "source_sdf_bond_order_ledger_exact" in metadata_report.failed_constraint_codes
    )

    atoms = list(system.atoms)
    metadata = dict(atoms[0].metadata)
    metadata["sdf_source_atom_index"] = 99
    atoms[0] = replace(atoms[0], metadata=metadata)
    atom_metadata_tamper = attach_parser_observation_digest(
        replace(system, atoms=tuple(atoms))
    )
    atom_metadata_report = analyze_terminal_monoalkene_c2_c8_profile(
        atom_metadata_tamper
    )
    assert (
        "source_sdf_atom_marker_ledger_exact"
        in atom_metadata_report.failed_constraint_codes
    )


def test_source_metadata_exact_types_and_key_sets_fail_closed() -> None:
    system = parse_sdf_v2000(_terminal_source(3)).system

    atom_metadata_variants: list[dict[str, object]] = []
    metadata = dict(system.atoms[0].metadata)
    metadata["sdf_source_atom_index"] = True
    atom_metadata_variants.append(metadata)
    metadata = dict(system.atoms[0].metadata)
    metadata["sdf_atom_map"] = False
    atom_metadata_variants.append(metadata)
    metadata = dict(system.atoms[0].metadata)
    metadata["hidden_unreviewed_marker"] = "value"
    atom_metadata_variants.append(metadata)
    for atom_metadata in atom_metadata_variants:
        atoms = list(system.atoms)
        atoms[0] = replace(atoms[0], metadata=atom_metadata)
        mutated = attach_parser_observation_digest(replace(system, atoms=tuple(atoms)))
        report = analyze_terminal_monoalkene_c2_c8_profile(mutated)
        assert report.profile_graph_preparation_ready is False
        assert "source_sdf_atom_marker_ledger_exact" in report.failed_constraint_codes

    atoms = list(system.atoms)
    atoms[0] = replace(atoms[0], serial=99)
    serial_tamper = attach_parser_observation_digest(
        replace(system, atoms=tuple(atoms))
    )
    serial_report = analyze_terminal_monoalkene_c2_c8_profile(serial_tamper)
    assert (
        "source_sdf_atom_marker_ledger_exact" in serial_report.failed_constraint_codes
    )

    single_index = next(
        index for index, bond in enumerate(system.bonds) if bond.order == 1.0
    )
    bond_variants: list[tuple[int, dict[str, object]]] = []
    metadata = dict(system.bonds[single_index].metadata)
    metadata["sdf_bond_type"] = True
    bond_variants.append((single_index, metadata))
    metadata = dict(system.bonds[0].metadata)
    metadata["sdf_source_bond_index"] = True
    bond_variants.append((0, metadata))
    metadata = dict(system.bonds[0].metadata)
    metadata["hidden_unreviewed_marker"] = "value"
    bond_variants.append((0, metadata))
    for bond_index, bond_metadata in bond_variants:
        bonds = list(system.bonds)
        bonds[bond_index] = replace(bonds[bond_index], metadata=bond_metadata)
        mutated = attach_parser_observation_digest(replace(system, bonds=tuple(bonds)))
        report = analyze_terminal_monoalkene_c2_c8_profile(mutated)
        assert report.profile_graph_preparation_ready is False
        assert "source_sdf_bond_order_ledger_exact" in report.failed_constraint_codes

    bonds = list(system.bonds)
    bonds[0] = replace(bonds[0], source="manual")
    source_tamper = attach_parser_observation_digest(
        replace(system, bonds=tuple(bonds))
    )
    source_report = analyze_terminal_monoalkene_c2_c8_profile(source_tamper)
    assert "source_sdf_bond_order_ledger_exact" in source_report.failed_constraint_codes

    bonds = list(system.bonds)
    metadata = dict(bonds[0].metadata)
    metadata["sdf_source_atom_i"] = True
    bonds[0] = replace(bonds[0], metadata=metadata)
    endpoint_tamper = attach_parser_observation_digest(
        replace(system, bonds=tuple(bonds))
    )
    endpoint_report = analyze_terminal_monoalkene_c2_c8_profile(endpoint_tamper)
    assert (
        "source_sdf_bond_order_ledger_exact" in endpoint_report.failed_constraint_codes
    )


def test_synthesized_sdf_residue_and_chain_context_is_exact() -> None:
    system = parse_sdf_v2000(_terminal_source(3)).system
    residues = list(system.residues)
    residues[0] = replace(residues[0], sequence_number=2)
    residue_tamper = attach_parser_observation_digest(
        replace(system, residues=tuple(residues))
    )
    residue_report = analyze_terminal_monoalkene_c2_c8_profile(residue_tamper)
    assert "single_nonpolymer_residue" in residue_report.failed_constraint_codes

    chains = list(system.chains)
    chains[0] = replace(chains[0], chain_id="X")
    chain_tamper = attach_parser_observation_digest(
        replace(system, chains=tuple(chains))
    )
    chain_report = analyze_terminal_monoalkene_c2_c8_profile(chain_tamper)
    assert "single_nonpolymer_residue" in chain_report.failed_constraint_codes


def test_smiles_generated_hydrogens_and_wrong_pedigree_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rdkit import rdBase

    from betelgeuze_engine_v2.molecular import smiles as smiles_module

    monkeypatch.setattr(
        smiles_module,
        "_SUPPORTED_RDKIT_VERSIONS",
        frozenset({rdBase.rdkitVersion}),
    )
    system = parse_smiles(b"C=C").system
    report = analyze_terminal_monoalkene_c2_c8_profile(system)

    assert report.status == "unsupported"
    assert "sdf_v2000_source_pedigree" in report.failed_constraint_codes
    assert "source_observed_hydrogens_only" in report.failed_constraint_codes


def test_existing_saturated_and_linear_force_field_profiles_remain_negative() -> None:
    system = parse_sdf_v2000(_terminal_source(3)).system
    saturated = analyze_canonical_ingest_applicability(system)
    force_field = analyze_linear_alkane_c1_c4_force_field_applicability(system)
    additive = analyze_terminal_monoalkene_c2_c8_profile(system)

    assert saturated.canonical_ingest_supported is False
    assert "single_bonds_only" in saturated.failed_constraint_codes
    assert force_field.status == "unsupported"
    assert additive.status == "available"


def test_sdf_writer_round_trip_preserves_profile_evidence() -> None:
    result = round_trip_sdf_v2000_source(
        _terminal_source(4),
        source_id="terminal-monoalkene-round-trip",
    )
    before = analyze_terminal_monoalkene_c2_c8_profile(result.source_ingest.system)
    after = analyze_terminal_monoalkene_c2_c8_profile(result.reparsed_ingest.system)

    assert before.status == after.status == "available"
    assert before.to_dict()["molecular_formula"] == "C4H8"
    assert after.to_dict()["molecular_formula"] == "C4H8"
    assert result.write_result.payload == serialize_sdf_v2000(
        result.reparsed_ingest.system
    )


def test_consumer_allowlist_is_enforced() -> None:
    system = parse_sdf_v2000(_terminal_source(2)).system

    with pytest.raises(TypeError, match="consumer_id"):
        require_terminal_monoalkene_c2_c8_graph_profile(  # type: ignore[call-arg]
            system
        )
    with pytest.raises(TypeError, match="exact string"):
        require_terminal_monoalkene_c2_c8_graph_profile(
            system,
            consumer_id=1,  # type: ignore[arg-type]
        )
    with pytest.raises(TerminalMonoalkeneC2C8ConsumerError) as exc_info:
        require_terminal_monoalkene_c2_c8_graph_profile(
            system,
            consumer_id="runtime_force_field",
        )
    assert exc_info.value.consumer_id == "runtime_force_field"
    assert exc_info.value.eligible_consumer_ids == (
        TERMINAL_MONOALKENE_C2_C8_AUDIT_CONSUMER_IDS
    )


def test_parser_observation_crosswire_is_invalid() -> None:
    c2 = parse_sdf_v2000(_terminal_source(2)).system
    c3 = parse_sdf_v2000(_terminal_source(3)).system
    metadata = dict(c3.provenance.metadata)
    metadata["parser_observation_sha256"] = c2.provenance.metadata[
        "parser_observation_sha256"
    ]
    crosswired = replace(c3, provenance=replace(c3.provenance, metadata=metadata))
    document = analyze_terminal_monoalkene_c2_c8_profile(crosswired).to_dict()

    assert document["status"] == "invalid"
    assert document["parser_observation_self_consistent"] is False
    assert document["parser_observation_sha256_equal"] is False
    assert "parser_observation_digest_bound" in document["failed_constraint_codes"]


def test_report_factory_snapshot_returned_document_and_live_tamper_boundaries() -> None:
    system = parse_sdf_v2000(_terminal_source(4)).system
    report = analyze_terminal_monoalkene_c2_c8_profile(system)
    original = report.to_dict()

    with pytest.raises(TypeError, match="factory-only"):
        TerminalMonoalkeneC2C8ProfileReport(
            canonical_system_bytes=b"x",
            canonical_system_sha256=hashlib.sha256(b"x").hexdigest(),
        )
    returned = report.to_dict()
    returned["status"] = "unsupported"
    returned["graph_projection"]["terminal_double_exact"] = False
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


def test_same_count_terminal_and_internal_double_reports_cannot_crosswire() -> None:
    terminal_system = parse_sdf_v2000(_terminal_source(4)).system
    internal_system = parse_sdf_v2000(
        _sdf_from_carbon_graph(4, ((0, 1, 1), (1, 2, 2), (2, 3, 1)))
    ).system
    terminal = analyze_terminal_monoalkene_c2_c8_profile(terminal_system)
    internal = analyze_terminal_monoalkene_c2_c8_profile(internal_system)

    assert terminal.status == "available"
    assert internal.status == "unsupported"
    assert terminal.report_sha256 != internal.report_sha256
    assert terminal.graph_projection_sha256 != internal.graph_projection_sha256
    assert terminal.matches_system(internal_system) is False


def test_rule_set_bytes_are_immutable_and_sha_stable() -> None:
    original = terminal_monoalkene_c2_c8_rule_set_bytes()
    local_copy = bytearray(original)
    local_copy[-2] = ord("X")

    assert bytes(local_copy) != terminal_monoalkene_c2_c8_rule_set_bytes()
    assert (
        hashlib.sha256(terminal_monoalkene_c2_c8_rule_set_bytes()).hexdigest()
        == TERMINAL_MONOALKENE_C2_C8_RULE_SET_SHA256
    )
