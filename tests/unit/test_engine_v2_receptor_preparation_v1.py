from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import math

import pytest
import torch

from betelgeuze_engine_v2.docking import (
    ChemistryPoseScorerV1,
    DockingBudget,
    DockingScope,
    PocketDefinition,
    build_element_aware_authenticated_known_pocket_docking_problem,
    build_guided_placement_context,
    generate_pocket_centered_docking_proposals,
)
from betelgeuze_engine_v2.docking.chemistry_features import (
    FEATURE_POLICY_METADATA_KEY,
    FULL_TOPOLOGY_FEATURE_POLICY_ID,
    perceive_full_topology_features,
)
from betelgeuze_engine_v2.docking.guided_placement import _feature_indices
from betelgeuze_engine_v2.docking.receptor_preparation import (
    ChemistryPreparationError,
    prepare_ligand_v1,
    prepare_receptor_v1,
)
from betelgeuze_engine_v2.docking.scorer_v1 import _features
from betelgeuze_engine_v2.io import PDBParseError, parse_pdb, pdb_string
from tools.run_engine_v2_prepared_receptor_development import main
import tools.run_engine_v2_prepared_receptor_development as development_runner

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "prepared_peptide_v1"


def _key(system, atom):
    residue = system.residues[atom.residue_index]
    return (
        system.chains[residue.chain_index].chain_id,
        residue.sequence_number,
        atom.name,
    )


def _pocket():
    return PocketDefinition(
        scope=DockingScope.KNOWN_POCKET,
        method_id="reviewed_test_pocket",
        method_version="1.0.0",
        coordinate_frame_id="source_frame",
        center=torch.zeros(3, dtype=torch.float64),
        radius_angstrom=12.0,
        source_artifact_sha256="a" * 64,
        implementation_source_sha256="b" * 64,
    )


def _context(receptor, ligand):
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor, ligand, _pocket()
    )
    scorer = ChemistryPoseScorerV1(
        authority, receptor, ligand, implementation_source_sha256="c" * 64
    )
    guidance = build_guided_placement_context(authority, receptor, ligand)
    return authority, scorer, guidance


def test_real_format_peptide_without_conect_recovers_graph_and_hbond_chemistry():
    payload = (FIXTURES / "asg_heavy.pdb").read_bytes()
    raw = parse_pdb(payload)
    assert not raw.bonds
    prepared = prepare_receptor_v1(payload)
    system = prepared.system
    assert system.atom_count > raw.atom_count
    assert torch.equal(system.coordinates[:, : raw.atom_count], raw.coordinates)
    features = perceive_full_topology_features(system)
    donors = {i for i, _ in features.donor_pairs}
    for atom in system.atoms:
        if atom.name == "N":
            assert atom.index in donors
            assert atom.index not in features.acceptors
        if atom.name in {"O", "OXT"}:
            assert atom.index in features.acceptors
    assert any(b.order == 2.0 for b in system.bonds)
    assert prepared.receipt["heavy_coordinates_preserved"] is True
    assert not system.provenance.chemistry_validated
    assert not prepared.receipt["scientifically_validated"]


def test_named_microstates_and_features_are_atom_order_invariant():
    payload = (FIXTURES / "charged_heavy.pdb").read_text()
    rows = [r for r in payload.splitlines() if r.startswith("ATOM")]
    first = prepare_receptor_v1(payload).system
    second = prepare_receptor_v1("\n".join(reversed(rows)) + "\nEND\n").system

    def by_key(s):
        return {
            _key(s, a): (a.formal_charge, a.partial_charge_e, a.aromatic)
            for a in s.atoms
        }

    assert by_key(first) == by_key(second)
    for system in (first, second):
        features = perceive_full_topology_features(system)
        for atom in system.atoms:
            residue = system.residues[atom.residue_index]
            if residue.name == "ARG" and atom.name in {"NE", "NH1", "NH2"}:
                assert atom.index not in features.acceptors
            if residue.name == "ASP" and atom.name == "OD2":
                assert atom.formal_charge == -1
            if residue.name == "LYS" and atom.name == "NZ":
                assert atom.formal_charge == 1
    ligand = prepare_ligand_v1((FIXTURES / "ethanol_explicit.sdf").read_bytes()).system
    scores = []
    for system in (first, second):
        authority, scorer, guidance = _context(system, ligand)
        assert (
            scorer.context.feature_policy_id
            == guidance.feature_policy_id
            == FULL_TOPOLOGY_FEATURE_POLICY_ID
        )
        proposals, _ = generate_pocket_centered_docking_proposals(
            authority,
            DockingBudget(candidate_count=1, top_k=1, max_torsions=32, seed=13),
        )
        scores.append(scorer.score(proposals[0]))
    assert scores[0] == pytest.approx(scores[1], rel=1e-12, abs=1e-10)


def test_complete_explicit_hydrogens_preserve_coordinates_and_partial_h_is_typed():
    prepared = prepare_receptor_v1((FIXTURES / "asg_heavy.pdb").read_bytes()).system
    # A protein PDB need not carry standard residue CONECT records or bond
    # orders; this deliberately exercises the named-template ingest boundary.
    text, _ = pdb_string(replace(prepared, bonds=()))
    second = prepare_receptor_v1(text)
    parsed = parse_pdb(text)
    assert second.receipt["added_hydrogen_count"] == 0
    assert torch.equal(second.system.coordinates, parsed.coordinates)
    lines = text.splitlines()
    removed_serial = None
    kept = []
    for line in lines:
        if (
            line.startswith(("ATOM", "HETATM"))
            and line[76:78].strip() == "H"
            and removed_serial is None
        ):
            removed_serial = int(line[6:11])
        elif not line.startswith("CONECT"):
            kept.append(line)
    with pytest.raises(
        ChemistryPreparationError, match="partial_hydrogen_set_unsupported"
    ):
        prepare_receptor_v1("\n".join(kept) + "\n")


def test_boundary_h_cannot_turn_pyrrolic_n_into_acceptor_and_consumers_agree():
    system = prepare_receptor_v1((FIXTURES / "charged_heavy.pdb").read_bytes()).system
    features = perceive_full_topology_features(system)
    ni = next(
        a.index
        for a in system.atoms
        if system.residues[a.residue_index].name == "HIE" and a.name == "NE2"
    )
    hi = next(h for n, h in features.donor_pairs if n == ni)
    allowed = set(range(system.atom_count)) - {hi}
    donor_pairs, acceptors, _ = _features(system, allowed)
    guided = _feature_indices(system, allowed_indices=allowed)
    assert ni not in acceptors and ni not in guided["acceptor"]
    assert {n for n, _ in donor_pairs} == set(guided["donor"])
    assert (
        ni not in guided["donor"]
    )  # unavailable interaction, unchanged chemical identity
    assert ni not in _features(system, set(range(system.atom_count)))[1]


@pytest.mark.parametrize(
    "smiles,sulfur_acceptor",
    [("CS(C)=O", False), ("CS(C)(=O)=O", False), ("CSC", True)],
)
def test_explicit_ligand_sulfur_oxidation_features_agree_in_both_consumers(
    smiles, sulfur_acceptor
):
    from rdkit import Chem
    from rdkit.Chem import AllChem

    molecule = Chem.AddHs(Chem.MolFromSmiles(smiles))
    parameters = AllChem.ETKDGv3()
    parameters.randomSeed = 1701
    parameters.numThreads = 1
    assert AllChem.EmbedMolecule(molecule, parameters) == 0
    prepared = prepare_ligand_v1(Chem.MolToMolBlock(molecule)).system
    allowed = set(range(prepared.atom_count))
    scored_acceptors = set(_features(prepared, allowed)[1])
    guided_acceptors = set(_feature_indices(prepared)["acceptor"])
    assert scored_acceptors == guided_acceptors
    for atom in prepared.atoms:
        if atom.element == "S":
            assert (atom.index in scored_acceptors) is sulfur_acceptor
        if atom.element == "O":
            assert atom.index in scored_acceptors


@pytest.mark.parametrize("angle,tolerance", [(math.pi / 2, 1e-10), (0.73, 0.005)])
def test_new_hydrogen_geometry_is_rigid_transform_equivariant(angle, tolerance):
    payload = (FIXTURES / "asg_heavy.pdb").read_text()
    original = prepare_receptor_v1(payload).system
    c, s = math.cos(angle), math.sin(angle)
    rotation = torch.tensor(
        [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]], dtype=torch.float64
    )
    shift = torch.tensor([2.0, -3.0, 4.0], dtype=torch.float64)
    rows = []
    for row in payload.splitlines():
        if row.startswith("ATOM"):
            xyz = torch.tensor(
                [float(row[a:b]) for a, b in ((30, 38), (38, 46), (46, 54))],
                dtype=torch.float64,
            )
            xyz = xyz @ rotation.T + shift
            row = row[:30] + "".join(f"{v:8.3f}" for v in xyz.tolist()) + row[54:]
        rows.append(row)
    moved_payload = "\n".join(rows) + "\n"
    moved = prepare_receptor_v1(moved_payload).system
    expected = original.coordinates @ rotation.T + shift
    # Arbitrary rotations round the input PDB to 0.001 A; the 90-degree case
    # preserves its decimal coordinates exactly and has a much stricter gate.
    assert torch.allclose(moved.coordinates, expected, atol=tolerance, rtol=0)
    parsed = parse_pdb(moved_payload)
    assert torch.equal(moved.coordinates[:, : parsed.atom_count], parsed.coordinates)


def test_underdetermined_hydrogen_frame_is_rejected_without_global_axis_fallback():
    names = [
        ("N", "N", 0.0),
        ("CA", "C", 1.4),
        ("C", "C", 2.8),
        ("O", "O", 4.0),
        ("OXT", "O", 1.5),
    ]
    payload = (
        "\n".join(
            f"ATOM  {i:5d} {name:<4} GLY A   1    {x:8.3f}{0.0:8.3f}{0.0:8.3f}{1.0:6.2f}{10.0:6.2f}          {element:>2}  "
            for i, (name, element, x) in enumerate(names, 1)
        )
        + "\nEND\n"
    )
    with pytest.raises(ChemistryPreparationError) as error:
        prepare_receptor_v1(payload)
    assert error.value.code == "hydrogen_local_frame_underdetermined"


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda s: s.replace("HIE", "HIS"), "histidine_microstate_required"),
        (
            lambda s: "\n".join(r for r in s.splitlines() if r[12:16].strip() != "OXT")
            + "\n",
            "incomplete_heavy_atoms",
        ),
        (lambda s: s.replace("ATOM  ", "HETATM", 1), "unsupported_nonpolymer"),
    ],
)
def test_unsupported_preparation_is_typed(mutation, code):
    payload = (FIXTURES / "charged_heavy.pdb").read_text()
    with pytest.raises(ChemistryPreparationError) as error:
        prepare_receptor_v1(mutation(payload))
    assert error.value.code == code


def _atom(serial, name, element, x):
    return f"HETATM{serial:5d} {name:<4} LIG A   1    {x:8.3f}{0.0:8.3f}{0.0:8.3f}{1.0:6.2f}{10.0:6.2f}          {element:>2}  "


@pytest.mark.parametrize("serials", [(9999, 10000), (10000, 10001), (1, 10001)])
def test_conect_fixed_width_serial_boundaries_and_bidirectional_deduplication(serials):
    first, second = serials
    payload = "\n".join(
        [
            _atom(first, "C1", "C", 0),
            _atom(second, "O1", "O", 1.3),
            f"CONECT{first:5d}{second:5d}",
            f"CONECT{second:5d}{first:5d}",
            "END",
        ]
    )
    system = parse_pdb(payload)
    assert [(b.atom_i, b.atom_j) for b in system.bonds] == [(0, 1)]


@pytest.mark.parametrize(
    "record",
    ["CONECT10000", "CONECT10000  BAD", "CONECT10000    0", "CONECT1000099999"],
)
def test_conect_invalid_fields_fail_closed(record):
    payload = "\n".join(
        [_atom(10000, "C1", "C", 0), _atom(10001, "O1", "O", 1.3), record, "END"]
    )
    with pytest.raises(PDBParseError):
        parse_pdb(payload)


def test_new_cli_consumes_both_policies_in_real_bounded_search(tmp_path):
    output = tmp_path / "report.json"
    code = main(
        [
            "--receptor",
            str(FIXTURES / "asg_heavy.pdb"),
            "--ligand",
            str(FIXTURES / "ethanol_explicit.sdf"),
            "--center",
            "0",
            "0",
            "0",
            "--radius",
            "8",
            "--candidates",
            "2",
            "--refinement-steps",
            "1",
            "--output",
            str(output),
        ]
    )
    assert code == 0
    report = json.loads(output.read_text())
    assert (
        report["scorer_feature_policy_id"]
        == report["guidance_feature_policy_id"]
        == FULL_TOPOLOGY_FEATURE_POLICY_ID
    )
    assert len(report["candidates"]) == 2
    assert report["search"]["success_count"] > 0
    assert not report["posebusters_measured"] and not report["native_recovery_measured"]
    assert not report["claim_safe"]
    sources = report["implementation_sources"]
    for name in (
        "betelgeuze_engine_v2/docking/receptor_preparation.py",
        "betelgeuze_engine_v2/docking/chemistry_features.py",
        "betelgeuze_engine_v2/docking/scorer_v1.py",
        "betelgeuze_engine_v2/docking/guided_placement.py",
        "betelgeuze_engine_v2/docking/search.py",
        "tools/run_engine_v2_prepared_receptor_development.py",
    ):
        source = Path(development_runner.__file__).resolve().parents[1] / name
        assert sources[name] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert (
        report["implementation_source_sha256"]
        == hashlib.sha256(
            json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def test_changed_implementation_cannot_produce_a_successful_report(monkeypatch):
    calls = 0

    def changing_sources():
        nonlocal calls
        calls += 1
        return {"betelgeuze_engine_v2/docking/chemistry_features.py": str(calls) * 64}

    monkeypatch.setattr(development_runner, "_implementation_sources", changing_sources)
    with pytest.raises(ChemistryPreparationError) as error:
        development_runner.run_prepared_receptor_development(
            (FIXTURES / "asg_heavy.pdb").read_bytes(),
            (FIXTURES / "ethanol_explicit.sdf").read_bytes(),
            center=(0.0, 0.0, 0.0),
            radius=8.0,
            candidate_count=1,
            refinement_steps=0,
        )
    assert error.value.code == "implementation_source_changed"


def test_cli_unsupported_chemistry_retains_typed_failure(tmp_path):
    receptor = tmp_path / "unsupported.pdb"
    receptor.write_text(
        (FIXTURES / "asg_heavy.pdb").read_text().replace("ALA", "FAD", 1)
    )
    output = tmp_path / "failed.json"
    code = main(
        [
            "--receptor",
            str(receptor),
            "--ligand",
            str(FIXTURES / "ethanol_explicit.sdf"),
            "--center",
            "0",
            "0",
            "0",
            "--radius",
            "8",
            "--output",
            str(output),
        ]
    )
    assert code == 2
    report = json.loads(output.read_text())
    assert (
        report["status"] == "failed" and report["failure_code"] == "unsupported_residue"
    )
    assert not report["claim_safe"]


def test_legacy_unmarked_inputs_keep_the_original_feature_policy():
    system = prepare_receptor_v1((FIXTURES / "asg_heavy.pdb").read_bytes()).system
    ligand = prepare_ligand_v1((FIXTURES / "ethanol_explicit.sdf").read_bytes()).system

    def legacy(s):
        return replace(
            s,
            metadata={
                k: v for k, v in s.metadata.items() if k != FEATURE_POLICY_METADATA_KEY
            },
        )

    _, scorer, guidance = _context(legacy(system), legacy(ligand))
    assert scorer.context.feature_policy_id == "legacy_scorer_features_v1"
    assert guidance.feature_policy_id != FULL_TOPOLOGY_FEATURE_POLICY_ID
    with pytest.raises(ValueError, match="policies differ"):
        _context(system, legacy(ligand))
