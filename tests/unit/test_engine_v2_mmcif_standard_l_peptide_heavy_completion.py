from __future__ import annotations

from dataclasses import replace
import math

import pytest
import torch

from betelgeuze_engine_v2.molecular.mmcif_standard_l_peptide_heavy_completion import (
    MmcifStandardLPeptideHeavyCompletionError,
    MmcifStandardLPeptideHeavyCompletionReport,
    MmcifStandardLPeptideHeavyCompletionResult,
    complete_mmcif_standard_l_peptide_heavy_neutral_microstate,
    require_mmcif_standard_l_peptide_heavy_completion,
)
from betelgeuze_engine_v2.molecular.standard_l_peptide_completion_rules import (
    standard_l_peptide_completion_component_rule,
    standard_l_peptide_completion_role_rule,
)


def _role(position: int, length: int) -> str:
    if length == 1:
        return "singleton"
    if position == 0:
        return "n_sequence_boundary"
    if position == length - 1:
        return "c_sequence_boundary"
    return "internal"


def _ideal_coordinates(component_id: str) -> dict[str, torch.Tensor]:
    return {
        atom.atom_id: torch.tensor(atom.ideal_coordinate, dtype=torch.float64)
        for atom in standard_l_peptide_completion_component_rule(component_id).atoms
    }


def _source(
    chains: tuple[tuple[str, tuple[str, ...]], ...],
    *,
    link_distance: float = 1.33,
    transform: torch.Tensor | None = None,
    translation: torch.Tensor | None = None,
    reverse_atom_rows: bool = False,
    overrides: dict[tuple[str, int, str], torch.Tensor] | None = None,
) -> bytes:
    rotation = (
        torch.eye(3, dtype=torch.float64)
        if transform is None
        else transform.to(dtype=torch.float64).clone()
    )
    shift_after = (
        torch.zeros(3, dtype=torch.float64)
        if translation is None
        else translation.clone()
    )
    overrides = {} if overrides is None else overrides
    entity_rows: list[str] = []
    entity_poly_rows: list[str] = []
    asym_rows: list[str] = []
    sequence_rows: list[str] = []
    atom_rows: list[str] = []
    serial = 1
    for chain_position, (asym_id, sequence) in enumerate(chains, start=1):
        entity_id = str(chain_position)
        entity_rows.append(f"{entity_id} polymer")
        entity_poly_rows.append(f"{entity_id} polypeptide(L) no no no")
        asym_rows.append(f"{asym_id} {entity_id}")
        previous_c: torch.Tensor | None = None
        for sequence_position, component_id in enumerate(sequence, start=1):
            sequence_rows.append(f"{entity_id} {sequence_position} {component_id} n")
            role = _role(sequence_position - 1, len(sequence))
            role_rule = standard_l_peptide_completion_role_rule(component_id, role)
            component = standard_l_peptide_completion_component_rule(component_id)
            ideal = _ideal_coordinates(component_id)
            if previous_c is None:
                residue_shift = torch.tensor(
                    (0.0, 20.0 * (chain_position - 1), 0.0),
                    dtype=torch.float64,
                )
            else:
                residue_shift = (
                    previous_c
                    + torch.tensor((link_distance, 0.0, 0.0), dtype=torch.float64)
                    - ideal["N"]
                )
            local_coordinates = {
                atom_id: ideal[atom_id] + residue_shift
                for atom_id in role_rule.required_source_heavy_atom_ids
            }
            previous_c = local_coordinates["C"]
            for key, coordinate in tuple(local_coordinates.items()):
                local_coordinates[key] = rotation @ coordinate + shift_after
            for atom_rule in sorted(component.atoms, key=lambda atom: atom.ccd_ordinal):
                atom_id = atom_rule.atom_id
                if atom_id not in role_rule.required_source_heavy_atom_ids:
                    continue
                coordinate = overrides.get(
                    (asym_id, sequence_position, atom_id),
                    local_coordinates[atom_id],
                )
                xyz = " ".join(f"{float(value):.17g}" for value in coordinate)
                atom_rows.append(
                    " ".join(
                        (
                            "ATOM",
                            str(serial),
                            atom_rule.element,
                            atom_id,
                            ".",
                            component_id,
                            asym_id,
                            entity_id,
                            str(sequence_position),
                            "?",
                            xyz,
                            "1",
                            "10",
                            "?",
                            str(sequence_position),
                            component_id,
                            f"AUTH{asym_id}",
                            atom_id,
                            "1",
                        )
                    )
                )
                serial += 1
    if reverse_atom_rows:
        atom_rows.reverse()
    return (
        "data_completion\n"
        "#\n"
        "loop_\n"
        "_entity.id\n"
        "_entity.type\n" + "\n".join(entity_rows) + "\n#\n"
        "loop_\n"
        "_entity_poly.entity_id\n"
        "_entity_poly.type\n"
        "_entity_poly.nstd_chirality\n"
        "_entity_poly.nstd_linkage\n"
        "_entity_poly.nstd_monomer\n" + "\n".join(entity_poly_rows) + "\n#\n"
        "loop_\n"
        "_struct_asym.id\n"
        "_struct_asym.entity_id\n" + "\n".join(asym_rows) + "\n#\n"
        "loop_\n"
        "_entity_poly_seq.entity_id\n"
        "_entity_poly_seq.num\n"
        "_entity_poly_seq.mon_id\n"
        "_entity_poly_seq.hetero\n" + "\n".join(sequence_rows) + "\n#\n"
        "loop_\n"
        "_atom_site.group_PDB\n"
        "_atom_site.id\n"
        "_atom_site.type_symbol\n"
        "_atom_site.label_atom_id\n"
        "_atom_site.label_alt_id\n"
        "_atom_site.label_comp_id\n"
        "_atom_site.label_asym_id\n"
        "_atom_site.label_entity_id\n"
        "_atom_site.label_seq_id\n"
        "_atom_site.pdbx_PDB_ins_code\n"
        "_atom_site.Cartn_x\n"
        "_atom_site.Cartn_y\n"
        "_atom_site.Cartn_z\n"
        "_atom_site.occupancy\n"
        "_atom_site.B_iso_or_equiv\n"
        "_atom_site.pdbx_formal_charge\n"
        "_atom_site.auth_seq_id\n"
        "_atom_site.auth_comp_id\n"
        "_atom_site.auth_asym_id\n"
        "_atom_site.auth_atom_id\n"
        "_atom_site.pdbx_PDB_model_num\n" + "\n".join(atom_rows) + "\n#\n"
    ).encode("ascii")


@pytest.mark.parametrize(
    "component_id,expected_atoms,expected_bonds,expected_hydrogens",
    (("ALA", 13, 12, 7), ("GLY", 10, 9, 5)),
)
def test_singletons_complete_exact_fixed_neutral_inventory(
    component_id: str,
    expected_atoms: int,
    expected_bonds: int,
    expected_hydrogens: int,
) -> None:
    result = complete_mmcif_standard_l_peptide_heavy_neutral_microstate(
        _source((("A", (component_id,)),)), source_id=f"single-{component_id}"
    )
    system = result.system

    assert system.atom_count == expected_atoms
    assert len(system.bonds) == expected_bonds
    assert sum(atom.element == "H" for atom in system.atoms) == expected_hydrogens
    assert all(
        atom.formal_charge_known
        and atom.formal_charge == 0
        and atom.partial_charge_e is None
        for atom in system.atoms
    )
    assert system.provenance.preparation_ready is False
    assert system.provenance.claim_safe is False
    assert result.verify_replay() is True


def test_ala_gly_ala_roles_counts_stereo_mapping_and_parameter_paths() -> None:
    source = _source((("A", ("ALA", "GLY", "ALA")),))
    result = complete_mmcif_standard_l_peptide_heavy_neutral_microstate(source)
    system = result.system
    mapping = result.atom_mapping
    inventory = result.parameter_requirement_inventory

    assert system.atom_count == 30
    assert len(system.bonds) == 29
    assert sum(atom.element == "H" for atom in system.atoms) == 15
    assert [
        residue.metadata["mmcif_standard_l_peptide_heavy_completion"]["sequence_role"]
        for residue in system.residues
    ] == ["n_sequence_boundary", "internal", "c_sequence_boundary"]
    assert [atom.stereo for atom in system.atoms if atom.name == "CA"] == [
        "S",
        "unspecified",
        "S",
    ]
    assert {row["status"] for row in mapping} == {
        "source_retained",
        "profile_generated",
    }
    assert sum(row["status"] == "source_retained" for row in mapping) == 15
    assert sum(row["status"] == "profile_generated" for row in mapping) == 15
    assert len({row["prepared_index"] for row in mapping}) == system.atom_count

    assert len(inventory["angle_requirements"]) == 49
    assert len(inventory["proper_torsion_requirements"]) == 64
    angles = {
        (row["atom_i"], row["atom_j"], row["atom_k"])
        for row in inventory["angle_requirements"]
    }
    propers = {
        (row["atom_i"], row["atom_j"], row["atom_k"], row["atom_l"])
        for row in inventory["proper_torsion_requirements"]
    }
    assert len(angles) == 49
    assert len(propers) == 64
    assert all(path <= tuple(reversed(path)) for path in propers)
    assert inventory["improper_torsions_enumerated"] is False
    assert inventory["cmap_terms_enumerated"] is False
    assert inventory["production_parameter_set_status"] == "missing"
    assert inventory["parameterability_assessed"] is False


def test_heavy_coordinates_are_bit_exact_and_generated_parent_lengths_match_rule() -> (
    None
):
    result = complete_mmcif_standard_l_peptide_heavy_neutral_microstate(
        _source((("A", ("ALA", "GLY", "ALA")),))
    )
    source_system = result.archive_heavy_ingest.system
    completed = result.system
    mapping = result.atom_mapping

    for row in mapping:
        if row["status"] == "source_retained":
            assert torch.equal(
                completed.coordinates[0, row["prepared_index"]],
                source_system.coordinates[0, row["source_index"]],
            )
            continue
        prepared_index = row["prepared_index"]
        generated = completed.atoms[prepared_index]
        residue = completed.residues[generated.residue_index]
        parent_index = next(
            index
            for index in residue.atom_indices
            if completed.atoms[index].name == row["generation_parent_atom_id"]
        )
        component = standard_l_peptide_completion_component_rule(row["component_id"])
        atom_by_id = {atom.atom_id: atom for atom in component.atoms}
        generated_rule = atom_by_id[row["atom_id"]]
        parent_rule = atom_by_id[row["generation_parent_atom_id"]]
        ideal_length = math.dist(
            generated_rule.ideal_coordinate, parent_rule.ideal_coordinate
        )
        observed_length = float(
            torch.linalg.vector_norm(
                completed.coordinates[0, prepared_index]
                - completed.coordinates[0, parent_index]
            ).item()
        )
        assert observed_length == pytest.approx(ideal_length, abs=1e-12)


def test_two_asym_chains_complete_without_cross_chain_links() -> None:
    system = complete_mmcif_standard_l_peptide_heavy_neutral_microstate(
        _source((("B", ("GLY", "ALA")), ("A", ("ALA", "GLY"))))
    ).system

    assert [chain.chain_id for chain in system.chains] == ["B", "A"]
    assert len(system.chains) == 2
    assert sum(atom.element == "H" for atom in system.atoms) == 20
    for bond in system.bonds:
        left_residue = system.residues[system.atoms[bond.atom_i].residue_index]
        right_residue = system.residues[system.atoms[bond.atom_j].residue_index]
        assert left_residue.chain_index == right_residue.chain_index


@pytest.mark.parametrize(
    "label,source,code",
    (
        (
            "short link",
            _source((("A", ("ALA", "GLY")),), link_distance=1.14),
            "source_peptide_c_n_distance_out_of_range",
        ),
        (
            "long link",
            _source((("A", ("ALA", "GLY")),), link_distance=1.56),
            "source_peptide_c_n_distance_out_of_range",
        ),
        (
            "reflected ALA",
            _source(
                (("A", ("ALA",)),),
                transform=torch.diag(torch.tensor((-1.0, 1.0, 1.0))),
            ),
            "ala_orientation_mismatch",
        ),
    ),
)
def test_geometry_admission_rejects_chain_breaks_and_reflection(
    label: str, source: bytes, code: str
) -> None:
    with pytest.raises(MmcifStandardLPeptideHeavyCompletionError) as exc_info:
        complete_mmcif_standard_l_peptide_heavy_neutral_microstate(source)
    assert exc_info.value.code == code, label


def test_geometry_admission_rejects_collinear_frame_and_heavy_bond_stretch() -> None:
    ideal = _ideal_coordinates("ALA")
    ca = ideal["CA"]
    ca_to_n = ideal["N"] - ca
    collinear_c = ca + (
        ca_to_n
        / torch.linalg.vector_norm(ca_to_n)
        * torch.linalg.vector_norm(ideal["C"] - ca)
    )
    collinear = _source((("A", ("ALA",)),), overrides={("A", 1, "C"): collinear_c})
    with pytest.raises(MmcifStandardLPeptideHeavyCompletionError) as exc_info:
        complete_mmcif_standard_l_peptide_heavy_neutral_microstate(collinear)
    assert exc_info.value.code == "source_frame_degenerate"

    c_to_o = ideal["O"] - ideal["C"]
    stretched_o = ideal["C"] + c_to_o * (
        (torch.linalg.vector_norm(c_to_o) + 0.201) / torch.linalg.vector_norm(c_to_o)
    )
    stretched = _source((("A", ("ALA",)),), overrides={("A", 1, "O"): stretched_o})
    with pytest.raises(MmcifStandardLPeptideHeavyCompletionError) as exc_info:
        complete_mmcif_standard_l_peptide_heavy_neutral_microstate(stretched)
    assert exc_info.value.code == "source_heavy_bond_distance_out_of_range"


def test_completion_is_proper_rigid_equivariant_and_atom_row_order_deterministic() -> (
    None
):
    canonical_source = _source((("A", ("ALA", "GLY")),))
    canonical = complete_mmcif_standard_l_peptide_heavy_neutral_microstate(
        canonical_source
    ).system
    rotation = torch.tensor(
        ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        dtype=torch.float64,
    )
    translation = torch.tensor((8.0, -3.0, 2.5), dtype=torch.float64)
    moved = complete_mmcif_standard_l_peptide_heavy_neutral_microstate(
        _source(
            (("A", ("ALA", "GLY")),),
            transform=rotation,
            translation=translation,
        )
    ).system
    expected = canonical.coordinates @ rotation.transpose(0, 1) + translation
    assert torch.allclose(moved.coordinates, expected, rtol=0.0, atol=2e-15)

    reordered = complete_mmcif_standard_l_peptide_heavy_neutral_microstate(
        _source((("A", ("ALA", "GLY")),), reverse_atom_rows=True)
    ).system
    assert [
        (atom.residue_index, atom.name, atom.element) for atom in reordered.atoms
    ] == [(atom.residue_index, atom.name, atom.element) for atom in canonical.atoms]
    assert torch.equal(reordered.coordinates, canonical.coordinates)
    assert [(bond.atom_i, bond.atom_j, bond.order) for bond in reordered.bonds] == [
        (bond.atom_i, bond.atom_j, bond.order) for bond in canonical.bonds
    ]


def test_factory_artifacts_are_detached_factory_only_and_tamper_evident() -> None:
    source = _source((("A", ("GLY",)),))
    result = complete_mmcif_standard_l_peptide_heavy_neutral_microstate(source)
    with pytest.raises(TypeError):
        MmcifStandardLPeptideHeavyCompletionResult(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        MmcifStandardLPeptideHeavyCompletionReport(source, "", b"{}")

    detached_system = result.system
    detached_system.coordinates[0, 0, 0] += 100.0
    assert not torch.equal(detached_system.coordinates, result.system.coordinates)
    detached_mapping = result.atom_mapping
    detached_mapping[0]["status"] = "forged"
    assert result.atom_mapping[0]["status"] != "forged"
    detached_report = result.report.to_dict()
    detached_report["claim_safe"] = True
    assert result.report.to_dict()["claim_safe"] is False

    original_state = result._state
    object.__setattr__(
        result, "_state", replace(original_state, mapping_bytes=b'{"forged":true}')
    )
    with pytest.raises(MmcifStandardLPeptideHeavyCompletionError):
        _ = result.atom_mapping

    fresh = complete_mmcif_standard_l_peptide_heavy_neutral_microstate(source)
    report = fresh.report
    object.__setattr__(report, "_report_bytes", b'{"claim_safe":true}')
    with pytest.raises(MmcifStandardLPeptideHeavyCompletionError):
        report.to_dict()


def test_require_reports_only_profile_readiness_without_broad_authority() -> None:
    result = require_mmcif_standard_l_peptide_heavy_completion(
        _source((("A", ("ALA",)),))
    )
    report = result.to_dict()

    assert report["profile_heavy_completion_ready"] is True
    assert report["profile_molecular_preparation_ready"] is True
    for field in (
        "preparation_ready",
        "generic_preparation_ready",
        "global_preparation_ready",
        "environmental_ph_assessed",
        "environmental_protonation_correctness_assessed",
        "scientific_geometry_validated",
        "parameterability_assessed",
        "parameterizable",
        "production_parameter_set_available",
        "physics_supported",
        "runtime_eligible",
        "minimization_supported",
        "simulation_ready",
        "execution_authorized",
        "claim_safe",
        "outer_source_writer_available",
        "general_mmcif_round_trip_evidence_ready",
        "all_format_round_trip_evidence_ready",
        "v2_1_complete",
    ):
        assert report[field] is False
