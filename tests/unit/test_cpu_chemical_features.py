"""Synthetic declared chemical states, independent comparator disagreements.

No activity/affinity labels or protected evaluation structures are used.
"""
from dataclasses import replace
import math
from pathlib import Path

import pytest
import torch

from betelgeuze_engine_v2 import AllAtomSystem, Atom, Bond, Chain, Residue, StructureProvenance
from betelgeuze_engine_v2.docking import (
    DockingBudget, DockingScope, PocketDefinition,
    build_element_aware_authenticated_known_pocket_docking_problem,
    generate_pocket_centered_docking_proposals,
)
from betelgeuze_engine_v2.docking.scorer_v1 import ChemistryPoseScorerV1, ScorerV1Error, _features
from betelgeuze_product.cpu_refinement_v1_2.chemical_features import (
    EXPLICIT_CHEMICAL_FEATURE_MODEL_ID, EXPLICIT_GRAPH_CONTEXT_SCHEMA,
    EXPLICIT_GRAPH_SCORE_ID, ExplicitGraphScorer, ExplicitGraphTerms,
    derive_explicit_chemical_features, explicit_graph_score_descriptor,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest
from betelgeuze_product.cpu_refinement_v1_2.score_replay import restore_score_terms


def molecule(smiles, *, name="fixture", offset=0.0):
    Chem = pytest.importorskip("rdkit.Chem")
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    atoms = tuple(Atom(index=a.GetIdx(), name=f"{a.GetSymbol()}{a.GetIdx()}",
                       element=a.GetSymbol(), atomic_number=a.GetAtomicNum(), residue_index=0,
                       formal_charge=a.GetFormalCharge(), partial_charge_e=float(a.GetFormalCharge()),
                       aromatic=a.GetIsAromatic()) for a in mol.GetAtoms())
    bonds = tuple(Bond(index=i, atom_i=min(b.GetBeginAtomIdx(), b.GetEndAtomIdx()),
                       atom_j=max(b.GetBeginAtomIdx(), b.GetEndAtomIdx()),
                       order=b.GetBondTypeAsDouble(), aromatic=b.GetIsAromatic())
                  for i, b in enumerate(mol.GetBonds()))
    return AllAtomSystem(
        system_id=name, atoms=atoms, bonds=bonds,
        residues=(Residue(index=0, name="SYN", chain_index=0, sequence_number=1,
                          atom_indices=tuple(range(len(atoms))), entity_type="non-polymer", hetero=True),),
        chains=(Chain(index=0, chain_id="S", residue_indices=(0,)),),
        coordinates=torch.tensor([[[offset + math.sin(i), math.cos(i), .3*i]
                                  for i in range(len(atoms))]], dtype=torch.float64),
        provenance=StructureProvenance(source_format="synthetic", source_id=name,
            source_sha256=digest([name, smiles]), parser_name="synthetic_rdkit_graph", parser_version="1.0.0"),
    )


@pytest.mark.parametrize("name,smiles,acceptors,donor_heavy", [
    ("peptide", "CC(=O)NCC(=O)N(C)C", (2, 6), 1),
    ("HIE_sidechain", "Cc1c[nH]cn1", (5,), 1),
    ("HIP_sidechain", "Cc1c[nH]c[nH+]1", (), 2),
    ("ARG_sidechain", "CCCNC(N)=[NH2+]", (), 3),
    ("LYS_sidechain", "CCCC[NH3+]", (), 1),
    ("LYN_sidechain", "CCCCN", (4,), 1),
    ("TRP_sidechain", "Cc1c[nH]c2ccccc12", (), 1),
    ("carboxylate", "CC(=O)[O-]", (2, 3), 0),
    ("N_terminal", "[NH3+]CC(=O)NC", (3,), 2),
    ("C_terminal", "CC(=O)NCC(=O)[O-]", (2, 6, 7), 1),
    ("carboxylic_acid", "CC(=O)O", (2,), 1),
    ("neutral_guanidine", "NC(=N)N", (2,), 3),
    ("neutral_amidine", "CC(=N)N", (2,), 2),
    ("amidinium", "CC(=[NH2+])N", (), 2),
    ("sulfonamide", "CS(=O)(=O)N", (2, 3), 1),
    ("thioamide", "CC(=S)N", (2,), 1),
    ("hydronium", "[OH3+]", (), 1),
    ("hydroxide", "[OH-]", (0,), 0),
])
def test_declared_group_roles(name, smiles, acceptors, donor_heavy):
    system = molecule(smiles, name=name)
    before = [(a.formal_charge, a.aromatic) for a in system.atoms]
    observed = derive_explicit_chemical_features(system)
    assert observed.acceptors == acceptors
    assert len({d for d, _ in observed.donors}) == donor_heavy
    assert before == [(a.formal_charge, a.aromatic) for a in system.atoms]


@pytest.mark.parametrize("smiles,center,nitrogens", [
    ("NC(=[NH2+])N", 1, (0, 2, 3)),
    ("CC(=[NH2+])N", 1, (2, 3)),
])
def test_cationic_group_is_independent_of_resonance_placement(smiles, center, nitrogens):
    source = molecule(smiles)
    donor_rows = derive_explicit_chemical_features(source).donors
    for positive in (*nitrogens, center):
        atoms = tuple(replace(a, formal_charge=int(a.index == positive),
                              partial_charge_e=float(a.index == positive))
                      if a.index in (*nitrogens, center) else a for a in source.atoms)
        bonds = tuple(replace(b, order=2.0 if positive in nitrogens and
                              {b.atom_i, b.atom_j} == {center, positive} else 1.0)
                      if center in {b.atom_i, b.atom_j} else b for b in source.bonds)
        features = derive_explicit_chemical_features(replace(source, atoms=atoms, bonds=bonds))
        assert features.acceptors == ()
        assert features.donors == donor_rows


def test_boundary_selection_uses_full_hydrogen_and_group_graph():
    indole = molecule("c1ccc2[nH]ccc2c1")
    n = next(a.index for a in indole.atoms if a.element == "N")
    # Hydrogen outside selected subset still determines pyrrolic identity.
    assert derive_explicit_chemical_features(indole, {n}).acceptors == ()
    assert derive_explicit_chemical_features(indole, {n}).donors == ()
    peptide = molecule("CC(=O)NC")
    assert derive_explicit_chemical_features(peptide, {3}).acceptors == ()


def test_incomplete_hydrogen_and_flattened_bond_order_graphs_reject():
    acid = molecule("CC(=O)O")
    flattened = replace(acid, bonds=tuple(replace(b, order=1.0) for b in acid.bonds))
    with pytest.raises(ScorerV1Error, match="valence"):
        derive_explicit_chemical_features(flattened)
    n = molecule("CN")
    h = next(b for b in n.bonds if n.atoms[b.atom_j].element == "H")
    missing_bond = tuple(replace(b, index=i) for i, b in enumerate(b for b in n.bonds if b != h))
    with pytest.raises(ScorerV1Error, match="valence"):
        derive_explicit_chemical_features(replace(n, bonds=missing_bond))


@pytest.mark.parametrize("smiles", ["c1ccncc1", "Cc1c[nH]cn1", "Cc1c[nH]c2ccccc12", "c1ccn2cccc2c1"])
def test_aromatic_and_kekule_encodings_agree_but_flattened_aromatic_graph_rejects(smiles):
    Chem = pytest.importorskip("rdkit.Chem")
    source = molecule(smiles)
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    Chem.Kekulize(mol, clearAromaticFlags=False)
    kekule = replace(source, bonds=tuple(replace(b, order=mol.GetBondWithIdx(b.index).GetBondTypeAsDouble())
                                        for b in source.bonds))
    assert derive_explicit_chemical_features(source) == derive_explicit_chemical_features(kekule)
    flattened = replace(source, bonds=tuple(replace(b, order=1.0) if b.aromatic else b for b in source.bonds))
    with pytest.raises(ScorerV1Error, match="valence"):
        derive_explicit_chemical_features(flattened)
    first = next(b.index for b in source.bonds if b.aromatic)
    mixed = replace(source, bonds=tuple(replace(b, order=1.0) if b.index == first else b for b in source.bonds))
    with pytest.raises(ScorerV1Error, match="mixed aromatic"):
        derive_explicit_chemical_features(mixed)


@pytest.mark.parametrize("smiles,ours,base,lipinski", [
    ("NC(=N)N", (2,), (), (2,)),
    ("NC(=[NH2+])N", (), (), ()),
    ("CN", (1,), (), (1,)),
    ("CC(=O)O", (2,), (2, 3), (2,)),
    ("CC(=O)[O-]", (2, 3), (2,), (2, 3)),
    ("Cc1c[nH]cn1", (5,), (5,), (5,)),
])
def test_independent_rdkit_definitions_are_comparators_not_ground_truth(smiles, ours, base, lipinski):
    Chem = pytest.importorskip("rdkit.Chem")
    from rdkit import RDConfig
    from rdkit.Chem import ChemicalFeatures as RDFeatures, Lipinski
    implicit = Chem.MolFromSmiles(smiles)
    factory = RDFeatures.BuildFeatureFactory(str(Path(RDConfig.RDDataDir) / "BaseFeatures.fdef"))
    base_observed = tuple(sorted(i for f in factory.GetFeaturesForMol(implicit)
                                 if f.GetFamily() == "Acceptor" for i in f.GetAtomIds()))
    lipinski_observed = tuple(i for (i,) in Lipinski._HAcceptors(implicit))
    assert derive_explicit_chemical_features(molecule(smiles)).acceptors == ours
    assert base_observed == base
    assert lipinski_observed == lipinski


def scorer_fixture():
    receptor, ligand = molecule("O", name="receptor", offset=4), molecule("NC(=[NH2+])N", name="ligand")
    pocket = PocketDefinition(scope=DockingScope.KNOWN_POCKET,
        method_id="synthetic_explicit_graph", method_version="1.0.0",
        coordinate_frame_id="synthetic_frame", center=torch.zeros(3, dtype=torch.float64),
        radius_angstrom=10, source_artifact_sha256="a"*64, implementation_source_sha256="b"*64)
    authority = build_element_aware_authenticated_known_pocket_docking_problem(receptor, ligand, pocket,
        receptor_margin_angstrom=4.0)
    scorer = ExplicitGraphScorer(authority, receptor, ligand, implementation_source_sha256="c"*64)
    budget = DockingBudget(candidate_count=1, top_k=1, max_torsions=0,
                          translation_radius_angstrom=0, seed=171)
    proposal = generate_pocket_centered_docking_proposals(authority, budget)[0][0]
    return scorer, proposal, receptor, ligand


def test_opt_in_scorer_context_cache_descriptor_terms_and_replay_are_bound(monkeypatch):
    scorer, proposal, receptor, ligand = scorer_fixture()
    legacy = ChemistryPoseScorerV1(scorer._authority, receptor, ligand, implementation_source_sha256="c"*64)
    assert legacy.context.ligand_acceptors == (0, 3)
    assert scorer.context.ligand_acceptors == ()
    assert scorer._ligand_acceptors == frozenset()
    assert scorer.config.to_dict() == legacy.config.to_dict()
    assert scorer.context.to_dict()["chemical_feature_model_id"] == EXPLICIT_CHEMICAL_FEATURE_MODEL_ID
    assert scorer.context.to_dict()["schema_id"] == EXPLICIT_GRAPH_CONTEXT_SCHEMA
    assert scorer.context.fingerprint_sha256 != legacy.context.fingerprint_sha256
    assert scorer.score_descriptor == explicit_graph_score_descriptor()
    terms = scorer.score_terms(proposal)
    assert isinstance(terms, ExplicitGraphTerms)
    assert terms.to_dict()["score_id"] == EXPLICIT_GRAPH_SCORE_ID
    assert terms.context_fingerprint_sha256 == scorer.context.fingerprint_sha256
    monkeypatch.setattr(scorer, "score_terms", lambda *_: pytest.fail("replay cannot recompute"))
    assert restore_score_terms(scorer, proposal, terms.to_dict()).to_dict() == terms.to_dict()
    with pytest.raises(ResearchError):
        restore_score_terms(legacy, proposal, terms.to_dict())
    corrupted = terms.to_dict()
    corrupted["score_id"] = legacy.score_descriptor.score_id
    corrupted["receipt_sha256"] = digest({k: v for k, v in corrupted.items() if k != "receipt_sha256"})
    with pytest.raises(ResearchError):
        restore_score_terms(scorer, proposal, corrupted)


def test_legacy_feature_path_retains_its_original_classification():
    system = molecule("NC(=[NH2+])N")
    _, old_acceptors, _ = _features(system, set(range(system.atom_count)))
    assert old_acceptors == (0, 3)
    assert derive_explicit_chemical_features(system).acceptors == ()
