"""Research geometry audits retain product rejection and exact source binding."""
import hashlib

import pytest
import torch

from betelgeuze_engine_v2 import AllAtomSystem, Atom, Bond, Chain, Residue, StructureProvenance
from betelgeuze_engine_v2.docking import DockingBudget, DockingScope, PocketDefinition
from betelgeuze_engine_v2.docking.contact_validity import build_element_aware_authenticated_known_pocket_docking_problem
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, coordinates_hex
from docs.research.human_5ht6_d3_complex.product_geometry_audit import ProductGeometryAudit, REQUIRED_CHECKS


def system(name, coordinates, pairs):
    count = len(coordinates)
    return AllAtomSystem(
        system_id=name,
        atoms=tuple(Atom(index=i, name=f"C{i}", element="C", atomic_number=6, residue_index=0)
                    for i in range(count)),
        bonds=tuple(Bond(index=i, atom_i=a, atom_j=b, order=1.) for i, (a, b) in enumerate(pairs)),
        residues=(Residue(index=0, name="LIG", chain_index=0, sequence_number=1,
                          atom_indices=tuple(range(count))),),
        chains=(Chain(index=0, chain_id="A", residue_indices=(0,)),),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit", source_id=name,
            source_sha256=hashlib.sha256(name.encode()).hexdigest(), parser_name="geometry-fixture",
            parser_version="1"),
    )


@pytest.fixture
def audit():
    # One nondegenerate degree-four center plus a nonexcluded terminal atom.
    ligand = system("geometry-ligand", [[0., 0., 0.], [1., 1., 1.], [-1., -1., 1.],
        [-1., 1., -1.], [1., -1., -1.], [2., 2., 2.]], [(0, i) for i in range(1, 5)] + [(1, 5)])
    receptor = system("geometry-receptor", [[0., 0., 7.]], [])
    pocket = PocketDefinition(scope=DockingScope.KNOWN_POCKET, center=torch.zeros(3, dtype=torch.float64),
        radius_angstrom=10., coordinate_frame_id="unit-frame", method_id="unit-pocket", method_version="1",
        source_artifact_sha256="a"*64, implementation_source_sha256="b"*64)
    authority = build_element_aware_authenticated_known_pocket_docking_problem(receptor, ligand, pocket)
    budget = DockingBudget(candidate_count=1, top_k=1, max_torsions=0, translation_radius_angstrom=0.)
    return ProductGeometryAudit(authority, budget, ligand)


def evaluate(audit, xyz):
    return audit.evaluate_coordinates(xyz, refiner_id="synthetic_geometry_perturbation", refiner_version="1",
        refinement_receipt_sha256=hashlib.sha256(repr(coordinates_hex(xyz)).encode()).hexdigest())


def test_baseline_is_exact_and_all_product_checks_run_without_scorer(audit, monkeypatch):
    import betelgeuze_engine_v2.docking.scorer_v1 as scoring

    def forbidden(*args, **kwargs):
        raise AssertionError("geometry audit must not construct or invoke a scorer")

    monkeypatch.setattr(scoring.ChemistryPoseScorerV1, "__init__", forbidden)
    before = coordinates_hex(audit.baseline_proposal.coordinates)
    original = audit.baseline_report()
    final = evaluate(audit, audit.baseline_proposal.coordinates.clone())
    assert original["passed"] and final["passed"]
    assert coordinates_hex(audit.baseline_proposal.coordinates) == before
    assert original["coordinate_fingerprint_sha256"] == final["coordinate_fingerprint_sha256"]
    assert final["parent_proposal_fingerprint_sha256"] == original["proposal_fingerprint_sha256"]
    assert final["pose_validity"] == original["pose_validity"] == final["baseline_pose_validity"]
    assert set(final["pose_validity"]["checks"]) == REQUIRED_CHECKS
    assert final["criteria"]["pose_validity_config"]["bond_length_tolerance_angstrom"] == .15
    assert final["criteria"]["declared_chirality_center_count"] == 1
    assert not final["scorer_evaluated"] and final["force_evaluations"] == 0
    assert not final["product_admitted"]


@pytest.mark.parametrize("kind,blocker", [
    ("bond", "bond_length_preservation_failed"),
    ("reflection", "declared_chirality_not_preserved"),
    ("self_clash", "ligand_self_clash_detected"),
    ("receptor", "receptor_ligand_clash_detected"),
    ("pocket", "pose_outside_declared_pocket"),
])
def test_real_product_failures_cannot_pass_research_audit(audit, kind, blocker):
    xyz = audit.baseline_proposal.coordinates.clone()
    if kind == "bond":
        xyz[5] += .2 * (xyz[5] - xyz[1]) / torch.linalg.vector_norm(xyz[5] - xyz[1])
    elif kind == "reflection":
        xyz[:, 2] *= -1
    elif kind == "self_clash":
        xyz[5] = xyz[2]
    elif kind == "receptor":
        xyz += torch.tensor([0., 0., 7.], dtype=torch.float64)
    else:
        xyz += 30.
    result = evaluate(audit, xyz)
    assert result["complete"] and not result["valid"] and not result["passed"]
    assert blocker in result["pose_validity"]["blockers"]
    assert result["baseline_pose_validity"]["valid"]
    if kind == "reflection":
        assert result["pose_validity"]["checks"]["bond_lengths_preserved"]
        assert result["pose_validity"]["checks"]["proper_rotation"]


@pytest.mark.parametrize("kind", ["float32", "nan", "infinity", "wrong_atoms", "batched", "list"])
def test_final_coordinate_contract_rejects_before_validation(audit, kind):
    xyz = audit.baseline_proposal.coordinates.clone()
    if kind == "float32":
        xyz = xyz.float()
    elif kind in ("nan", "infinity"):
        xyz[0, 0] = float("nan" if kind == "nan" else "inf")
    elif kind == "wrong_atoms":
        xyz = xyz[:-1]
    elif kind == "batched":
        xyz = xyz[None]
    else:
        xyz = xyz.tolist()
    with pytest.raises(ResearchError, match="finite CPU float64 exact shape"):
        audit.evaluate_coordinates(xyz, refiner_id="test", refiner_version="1", refinement_receipt_sha256="c"*64)


@pytest.mark.parametrize("digest", ["", "false", "G"*64])
def test_final_requires_real_digest_shape(audit, digest):
    with pytest.raises(ResearchError):
        audit.evaluate_coordinates(audit.baseline_proposal.coordinates.clone(), refiner_id="test",
            refiner_version="1", refinement_receipt_sha256=digest)


def test_changed_baseline_fails_closed(audit):
    audit.baseline_proposal.coordinates[0, 0] += .01
    with pytest.raises(ValueError, match="changed"):
        audit.baseline_report()


def test_changed_authority_reference_fails_closed(audit):
    audit._authority.validity_context.reference_coordinates[0, 0] += .01
    with pytest.raises(ValueError, match="changed"):
        audit.baseline_report()


def test_exported_report_cannot_change_retained_reference_or_policy(audit):
    original = audit.baseline_report()
    original["criteria"]["pose_validity_config"]["bond_length_tolerance_angstrom"] = 10.
    original["pose_validity"]["checks"]["bond_lengths_preserved"] = False
    unchanged = audit.baseline_report()
    assert unchanged["criteria"]["pose_validity_config"]["bond_length_tolerance_angstrom"] == .15
    assert unchanged["pose_validity"]["checks"]["bond_lengths_preserved"]
