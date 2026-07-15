from __future__ import annotations

from collections.abc import Mapping

import pytest

from betelgeuze_engine_v2.molecular import (
    mmcif_standard_l_peptide_neutral_preparation as preparation,
)
from betelgeuze_engine_v2.molecular.standard_l_peptide_preparation_rules import (
    STANDARD_L_PEPTIDE_PREPARATION_COMPONENT_RULES,
)
from betelgeuze_engine_v2.molecular.topology import canonical_topology_sha256


def _loop(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    return "\n".join(("loop_", *headers, *(" ".join(row) for row in rows), "#"))


def _source(
    chains: Mapping[str, tuple[str, ...]], *, reverse_atoms: bool = False
) -> bytes:
    rules = {
        rule.component_id: rule
        for rule in STANDARD_L_PEPTIDE_PREPARATION_COMPONENT_RULES
    }
    entity_rows: list[tuple[str, ...]] = []
    entity_poly_rows: list[tuple[str, ...]] = []
    struct_asym_rows: list[tuple[str, ...]] = []
    sequence_rows: list[tuple[str, ...]] = []
    entity_by_asym: dict[str, str] = {}
    for ordinal, (asym_id, sequence) in enumerate(sorted(chains.items()), start=1):
        entity_id = str(ordinal)
        entity_by_asym[asym_id] = entity_id
        entity_rows.append((entity_id, "polymer"))
        entity_poly_rows.append((entity_id, "polypeptide(L)", "no", "no", "no"))
        struct_asym_rows.append((asym_id, entity_id))
        sequence_rows.extend(
            (entity_id, str(number), component_id, "n")
            for number, component_id in enumerate(sequence, start=1)
        )

    used_components = sorted(
        {component for values in chains.values() for component in values}
    )
    component_rows = [
        (component_id, "'L-peptide linking'", "0") for component_id in used_components
    ]
    component_atom_rows: list[tuple[str, ...]] = []
    component_bond_rows: list[tuple[str, ...]] = []
    for component_id in used_components:
        rule = rules[component_id]
        component_atom_rows.extend(
            (
                component_id,
                atom.atom_id,
                atom.element,
                str(atom.formal_charge),
                atom.aromatic_flag,
                atom.leaving_atom_flag,
                atom.stereo_config,
                atom.backbone_atom_flag,
                atom.n_terminal_atom_flag,
                atom.c_terminal_atom_flag,
                str(atom.ccd_ordinal),
            )
            for atom in rule.atoms
        )
        component_bond_rows.extend(
            (
                component_id,
                bond.atom_id_1,
                bond.atom_id_2,
                bond.value_order,
                bond.aromatic_flag,
                bond.stereo_config,
                str(bond.ccd_ordinal),
            )
            for bond in rule.bonds
        )

    atom_rows: list[tuple[str, ...]] = []
    atom_site_id = 1
    for asym_id, sequence in sorted(chains.items()):
        entity_id = entity_by_asym[asym_id]
        for sequence_number, component_id in enumerate(sequence, start=1):
            for atom in rules[component_id].atoms:
                coordinate_seed = atom_site_id * 0.125
                atom_rows.append(
                    (
                        "ATOM",
                        str(atom_site_id),
                        atom.element,
                        atom.atom_id,
                        ".",
                        component_id,
                        asym_id,
                        entity_id,
                        str(sequence_number),
                        "?",
                        f"{coordinate_seed:.3f}",
                        f"{-coordinate_seed:.3f}",
                        f"{coordinate_seed + 1.0:.3f}",
                        "1.00",
                        "10.00",
                        "?",
                        str(900 + sequence_number),
                        component_id,
                        f"AUTH{asym_id}",
                        f"AUTH_{atom.atom_id}",
                        "1",
                    )
                )
                atom_site_id += 1
    if reverse_atoms:
        atom_rows.reverse()

    sections = [
        "data_exact_ala_gly_preparation",
        "#",
        _loop(("_entity.id", "_entity.type"), entity_rows),
        _loop(
            (
                "_entity_poly.entity_id",
                "_entity_poly.type",
                "_entity_poly.nstd_chirality",
                "_entity_poly.nstd_linkage",
                "_entity_poly.nstd_monomer",
            ),
            entity_poly_rows,
        ),
        _loop(("_struct_asym.id", "_struct_asym.entity_id"), struct_asym_rows),
        _loop(
            (
                "_entity_poly_seq.entity_id",
                "_entity_poly_seq.num",
                "_entity_poly_seq.mon_id",
                "_entity_poly_seq.hetero",
            ),
            sequence_rows,
        ),
        _loop(
            (
                "_chem_comp.id",
                "_chem_comp.type",
                "_chem_comp.pdbx_formal_charge",
            ),
            component_rows,
        ),
        _loop(
            (
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
            ),
            component_atom_rows,
        ),
        _loop(
            (
                "_chem_comp_bond.comp_id",
                "_chem_comp_bond.atom_id_1",
                "_chem_comp_bond.atom_id_2",
                "_chem_comp_bond.value_order",
                "_chem_comp_bond.pdbx_aromatic_flag",
                "_chem_comp_bond.pdbx_stereo_config",
                "_chem_comp_bond.pdbx_ordinal",
            ),
            component_bond_rows,
        ),
        _loop(
            (
                "_atom_site.group_PDB",
                "_atom_site.id",
                "_atom_site.type_symbol",
                "_atom_site.label_atom_id",
                "_atom_site.label_alt_id",
                "_atom_site.label_comp_id",
                "_atom_site.label_asym_id",
                "_atom_site.label_entity_id",
                "_atom_site.label_seq_id",
                "_atom_site.pdbx_PDB_ins_code",
                "_atom_site.Cartn_x",
                "_atom_site.Cartn_y",
                "_atom_site.Cartn_z",
                "_atom_site.occupancy",
                "_atom_site.B_iso_or_equiv",
                "_atom_site.pdbx_formal_charge",
                "_atom_site.auth_seq_id",
                "_atom_site.auth_comp_id",
                "_atom_site.auth_asym_id",
                "_atom_site.auth_atom_id",
                "_atom_site.pdbx_PDB_model_num",
            ),
            atom_rows,
        ),
    ]
    return ("\n".join(sections) + "\n").encode("ascii")


def _replace_once(source: bytes, old: bytes, new: bytes) -> bytes:
    assert source.count(old) == 1
    return source.replace(old, new, 1)


def test_singleton_ala_is_profile_prepared_without_generic_promotion() -> None:
    result = preparation.prepare_mmcif_standard_l_peptide_neutral_linkage(
        _source({"A": ("ALA",)}), source_id="unit:single-ala"
    )
    system = result.system
    report = result.report.to_dict()

    assert system.atom_count == 13
    assert len(system.bonds) == 12
    assert [atom.name for atom in system.atoms] == [
        "N",
        "CA",
        "C",
        "O",
        "CB",
        "OXT",
        "H",
        "H2",
        "HA",
        "HB1",
        "HB2",
        "HB3",
        "HXT",
    ]
    assert report["profile_molecular_preparation_ready"] is True
    assert report["preparation_ready"] is False
    assert report["generic_preparation_ready"] is False
    assert report["parameterability_assessed"] is False
    assert report["runtime_eligible"] is False
    assert report["claim_safe"] is False
    assert system.provenance.preparation_ready is False
    assert report["generated_hydrogen_count"] == 0
    assert report["all_prepared_formal_charges_known_zero"] is True
    assert result.transformed_topology_sha256 == canonical_topology_sha256(system)
    assert result.verify_replay() is True


def test_gly_ala_link_applies_exact_atom_and_bond_partitions() -> None:
    result = preparation.require_mmcif_standard_l_peptide_neutral_preparation(
        _source({"A": ("GLY", "ALA")}), source_id="unit:gly-ala"
    )
    system = result.system
    report = result.report.to_dict()
    deleted = [row for row in result.atom_mapping if row["status"] == "policy_deleted"]

    assert system.atom_count == 20
    assert len(system.bonds) == 19
    assert report["source_atom_count"] == 23
    assert report["policy_deleted_source_atom_count"] == 3
    assert report["source_bond_count"] == 21
    assert report["policy_deleted_input_bond_count"] == 3
    assert report["materialized_peptide_bond_count"] == 1
    assert [(row["sequence_number"], row["atom_id"]) for row in deleted] == [
        (1, "OXT"),
        (1, "HXT"),
        (2, "H2"),
    ]
    inter = [
        bond
        for bond in system.bonds
        if bond.metadata[
            preparation.MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MARKER_KEY
        ]["bond_kind"]
        == "sequence_adjacent_peptide_bond"
    ]
    assert len(inter) == 1
    assert (system.atoms[inter[0].atom_i].name, system.atoms[inter[0].atom_j].name) == (
        "C",
        "N",
    )
    assert result.archive_heavy_ingest.system.atom_count == 10


def test_three_residue_roles_and_parameter_inventory_are_complete() -> None:
    result = preparation.prepare_mmcif_standard_l_peptide_neutral_linkage(
        _source({"A": ("ALA", "GLY", "ALA")}), source_id="unit:tripeptide"
    )
    report = result.report.to_dict()
    inventory = result.parameter_requirement_inventory

    assert report["materialized_peptide_bond_count"] == 2
    assert report["policy_deleted_source_atom_count"] == 6
    assert report["sequence_role_counts"] == [
        ["c_sequence_boundary", 1],
        ["internal", 1],
        ["n_sequence_boundary", 1],
    ]
    assert len(inventory["atom_requirements"]) == result.system.atom_count
    assert len(inventory["bond_requirements"]) == len(result.system.bonds)
    assert len(inventory["proper_torsion_requirements"]) == 64
    assert inventory["production_parameter_set_status"] == "missing"
    assert inventory["parameterability_assessed"] is False


def test_multi_asym_has_independent_links_and_no_cross_asym_bond() -> None:
    result = preparation.prepare_mmcif_standard_l_peptide_neutral_linkage(
        _source({"B": ("GLY", "ALA"), "A": ("ALA", "GLY")}),
        source_id="unit:multi-asym",
    )
    system = result.system
    inter = [
        bond
        for bond in system.bonds
        if bond.metadata[
            preparation.MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_MARKER_KEY
        ]["bond_kind"]
        == "sequence_adjacent_peptide_bond"
    ]
    assert len(inter) == 2
    assert all(
        system.residues[system.atoms[bond.atom_i].residue_index].chain_index
        == system.residues[system.atoms[bond.atom_j].residue_index].chain_index
        for bond in inter
    )


def test_moderate_chain_uses_linear_source_bond_partition() -> None:
    sequence = tuple("ALA" if index % 2 == 0 else "GLY" for index in range(8))
    result = preparation.prepare_mmcif_standard_l_peptide_neutral_linkage(
        _source({"A": sequence}), source_id="unit:moderate-chain"
    )
    report = result.report.to_dict()

    assert report["residue_count"] == 8
    assert report["materialized_peptide_bond_count"] == 7
    assert report["policy_deleted_source_atom_count"] == 21
    assert report["policy_deleted_input_bond_count"] == 21


def test_atom_site_row_order_does_not_change_prepared_topology() -> None:
    ordered = preparation.prepare_mmcif_standard_l_peptide_neutral_linkage(
        _source({"A": ("ALA", "GLY", "ALA")}), source_id="unit:order"
    )
    reversed_rows = preparation.prepare_mmcif_standard_l_peptide_neutral_linkage(
        _source({"A": ("ALA", "GLY", "ALA")}, reverse_atoms=True),
        source_id="unit:order",
    )
    assert ordered.transformed_topology_sha256 == (
        reversed_rows.transformed_topology_sha256
    )
    assert [atom.name for atom in ordered.system.atoms] == [
        atom.name for atom in reversed_rows.system.atoms
    ]


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (
        (
            lambda source: _replace_once(
                source, b"ALA OXT O 0 N Y", b"ALA OXT O 0 N N"
            ),
            "terminal_annotation_policy_mismatch",
        ),
        (
            lambda source: _replace_once(
                source, b"ALA CA C 0 N N S", b"ALA CA C 0 N N N"
            ),
            "component_atom_policy_mismatch",
        ),
        (
            lambda source: _replace_once(
                source, b"ALA H H 0 N N N", b"ALA H H 1 N N N"
            ),
            "terminal_component_child_rejected",
        ),
        (
            lambda source: _replace_once(source, b"ALA N H SING", b"ALA CA H SING"),
            "component_bond_policy_mismatch",
        ),
        (
            lambda source: source.replace(
                b"loop_\n_entity_poly.entity_id\n_entity_poly.type\n_entity_poly.nstd_chirality\n_entity_poly.nstd_linkage\n_entity_poly.nstd_monomer\n1 polypeptide(L) no no no\n#\n",
                b"",
                1,
            ),
            "unsupported_category_surface",
        ),
    ),
)
def test_source_policy_failures_are_typed(mutation, expected_code: str) -> None:
    with pytest.raises(
        preparation.MmcifStandardLPeptideNeutralPreparationError
    ) as captured:
        preparation.prepare_mmcif_standard_l_peptide_neutral_linkage(
            mutation(_source({"A": ("ALA",)})), source_id="unit:failure"
        )
    assert captured.value.code == expected_code


def test_unknown_policy_id_and_stale_result_fail_closed() -> None:
    source = _source({"A": ("ALA",)})
    with pytest.raises(
        preparation.MmcifStandardLPeptideNeutralPreparationError
    ) as captured:
        preparation.prepare_mmcif_standard_l_peptide_neutral_linkage(
            source, policy_id="unknown-policy"
        )
    assert captured.value.code == "unsupported_policy_id"

    result = preparation.prepare_mmcif_standard_l_peptide_neutral_linkage(source)
    report = result.report
    object.__setattr__(report, "_report_bytes", b"{}")
    with pytest.raises(preparation.MmcifStandardLPeptideNeutralPreparationError):
        _ = report.to_dict()

    object.__setattr__(result._state, "mapping_bytes", b"{}")
    with pytest.raises(preparation.MmcifStandardLPeptideNeutralPreparationError):
        _ = result.system


def test_every_stored_state_component_is_access_bound_and_views_are_detached() -> None:
    result = preparation.prepare_mmcif_standard_l_peptide_neutral_linkage(
        _source({"A": ("ALA", "GLY")}), source_id="unit:tamper-matrix"
    )
    state = result._state
    mutations = {
        "outer_source": state.outer_source + b"#\n",
        "source_id": state.source_id + ":forged",
        "block_name": state.block_name + "_forged",
        "terminal_source": state.terminal_source + b"#\n",
        "archive_source": state.archive_source + b"#\n",
        "prepared_snapshot": state.prepared_snapshot + b"0",
        "mapping_bytes": state.mapping_bytes + b" ",
        "parameter_inventory_bytes": state.parameter_inventory_bytes + b" ",
        "heavy_crosscheck_bytes": state.heavy_crosscheck_bytes + b" ",
        "source_binding_bytes": state.source_binding_bytes + b" ",
        "report_bytes": state.report_bytes + b" ",
    }
    assert len(mutations) == 11
    for field_name, forged in mutations.items():
        original = getattr(state, field_name)
        object.__setattr__(state, field_name, forged)
        with pytest.raises(preparation.MmcifStandardLPeptideNeutralPreparationError):
            _ = result.system
        object.__setattr__(state, field_name, original)
        assert result.system.atom_count == 20

    mapping = result.atom_mapping
    mapping[0]["status"] = "forged"
    assert result.atom_mapping[0]["status"] != "forged"
    inventory = result.parameter_requirement_inventory
    inventory["atom_requirements"].clear()
    assert result.parameter_requirement_inventory["atom_requirements"]


def test_source_id_limit_and_factory_only_artifacts() -> None:
    with pytest.raises(
        preparation.MmcifStandardLPeptideNeutralPreparationError
    ) as captured:
        preparation.prepare_mmcif_standard_l_peptide_neutral_linkage(
            _source({"A": ("GLY",)}),
            source_id="x"
            * (
                preparation.MAX_MMCIF_STANDARD_L_PEPTIDE_NEUTRAL_PREPARATION_SOURCE_ID_BYTES
                + 1
            ),
        )
    assert captured.value.code == "source_id_too_large"
    with pytest.raises(TypeError):
        preparation.MmcifStandardLPeptideNeutralPreparationResult(None)
    with pytest.raises(TypeError):
        preparation.MmcifStandardLPeptideNeutralPreparationReport(b"{}")
