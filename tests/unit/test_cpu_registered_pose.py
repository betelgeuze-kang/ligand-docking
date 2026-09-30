"""Exact-source registered pose generation and portable identity rejection."""
from dataclasses import replace

import pytest
import torch

from betelgeuze_engine_v2.docking.contact_validity import build_element_aware_authenticated_known_pocket_docking_problem
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, coordinates_hex, digest, source_manifest
from betelgeuze_product.cpu_refinement_v1_2.registered_pose import generate_registered_pose, require_registered_receipt
from betelgeuze_product.cpu_refinement_v1_2.workflow import load_request, REQUEST_SCHEMA
from tests.unit.test_cpu_explicit_chemistry_workflow import request_fixture


@pytest.fixture
def registered(tmp_path):
    request = request_fixture(tmp_path)
    request['budget'].update(candidate_count=1, top_k=1, max_torsions=0, translation_radius_angstrom=0.)
    prepared = {k: v for k, v in request.items() if k != 'cross_parameters'}
    prepared['schema_id'] = REQUEST_SCHEMA
    authority, receptor, ligand, parameters, budget, *_ = load_request(prepared, digest(source_manifest()))
    return authority, receptor, ligand, budget


def _rehash(row):
    row['receipt_sha256'] = digest({k: v for k, v in row.items() if k != 'receipt_sha256'})
    return row


def test_registered_coordinates_are_bit_exact_without_recentering(registered, monkeypatch):
    authority, _, ligand, budget = registered
    import betelgeuze_engine_v2.docking.guided_placement as guided
    import betelgeuze_engine_v2.docking.placement as placement

    def forbidden(*args, **kwargs):
        raise AssertionError('registered policy invoked fresh placement/conformer rebuilding')

    monkeypatch.setattr(guided, 'generate_guided_docking_proposals', forbidden)
    monkeypatch.setattr(placement, 'generate_pocket_centered_docking_proposals', forbidden)
    monkeypatch.setattr(placement, 'torsion_tree_forward_kinematics', forbidden)
    proposals, receipt = generate_registered_pose(authority, budget, ligand)
    assert len(proposals) == 1
    proposal = proposals[0]
    assert coordinates_hex(proposal.coordinates) == coordinates_hex(ligand.coordinates[0])
    assert not torch.equal(proposal.coordinates.mean(0), authority.pocket.center)
    assert torch.equal(proposal.rotation, torch.eye(3, dtype=torch.float64))
    assert torch.count_nonzero(proposal.translation) == torch.count_nonzero(proposal.torsion_angles) == 0
    assert proposal.proposal_index == 0 and not proposal.refined
    row = receipt.to_dict()
    assert row['initial_coordinates_binary64_hex'] == coordinates_hex(ligand.coordinates[0])
    assert row['proposal_fingerprint_sha256'] == proposal.fingerprint_sha256
    assert row['initial_coordinate_fingerprint_sha256'] == proposal.coordinate_fingerprint_sha256
    assert digest(row['authority_binding']) == authority.input_receipt_sha256
    assert require_registered_receipt(row) == row
    # Exported mutable dictionaries cannot mutate the retained receipt.
    row['initial_coordinates_binary64_hex'][0][0] = float(999).hex()
    assert receipt.to_dict()['initial_coordinates_binary64_hex'] == coordinates_hex(ligand.coordinates[0])


def test_baseline_and_refined_budgets_retain_identical_initial_receipts(registered):
    authority, _, ligand, budget = registered
    baseline, first = generate_registered_pose(authority, replace(budget, max_refinement_steps=0), ligand)
    refined, second = generate_registered_pose(authority, budget, ligand)
    assert baseline[0].fingerprint_sha256 == refined[0].fingerprint_sha256
    assert first.to_dict() == second.to_dict()
    assert first.receipt_sha256 == second.receipt_sha256


@pytest.mark.parametrize('changes', [
    {'candidate_count': 2}, {'candidate_count': 2, 'top_k': 2},
    {'max_torsions': 1}, {'translation_radius_angstrom': .01},
])
def test_registered_generation_rejects_placement_budget_expansion(registered, changes):
    authority, _, ligand, budget = registered
    with pytest.raises(ResearchError, match='one candidate'):
        generate_registered_pose(authority, replace(budget, **changes), ligand)


def test_registered_ligand_source_cannot_be_cross_wired(registered):
    authority, _, ligand, budget = registered
    different = ligand.with_coordinates(ligand.coordinates + .1, operation='different')
    with pytest.raises(ResearchError, match='source identity'):
        generate_registered_pose(authority, budget, different)


@pytest.mark.parametrize('kind', ['float32', 'multiple_models'])
def test_unsupported_coordinate_storage_is_rejected_without_casting(registered, kind):
    authority, receptor, ligand, budget = registered
    xyz = ligand.coordinates.to(torch.float32) if kind == 'float32' else torch.cat((ligand.coordinates, ligand.coordinates), 0)
    changed = replace(ligand, coordinates=xyz)
    # Existing authenticated authority already rejects float32 without casting;
    # the registered adapter additionally rejects multiple coordinate models.
    with pytest.raises(ValueError, match='float64'):
        fresh = build_element_aware_authenticated_known_pocket_docking_problem(receptor, changed, authority.pocket)
        generate_registered_pose(fresh, budget, changed)


def test_signed_zero_coordinates_survive_exact_copy(registered):
    authority, receptor, ligand, budget = registered
    xyz = ligand.coordinates.clone()
    xyz[0, 0, 0] = -0.0
    changed = replace(ligand, coordinates=xyz)
    fresh = build_element_aware_authenticated_known_pocket_docking_problem(receptor, changed, authority.pocket)
    proposals, receipt = generate_registered_pose(fresh, budget, changed)
    assert coordinates_hex(proposals[0].coordinates)[0][0] == '-0x0.0p+0'
    assert require_registered_receipt(receipt.to_dict())['initial_coordinates_binary64_hex'][0][0] == '-0x0.0p+0'


@pytest.mark.parametrize('field,value', [
    ('schema_id', 'unknown/1'), ('policy_id', 'pocket_centered_guided/1.0.0'),
    ('coordinate_dtype', 'float32'), ('source_ligand_system_sha256', '0'*64),
    ('authority_input_receipt_sha256', '0'*64), ('problem_fingerprint_sha256', '0'*64),
    ('search_space_fingerprint_sha256', '0'*64), ('initial_coordinate_fingerprint_sha256', '0'*64),
    ('proposal_fingerprint_sha256', '0'*64), ('candidate_id', 'forged'),
    ('candidate_count', True), ('top_k', 2), ('max_torsions', 1),
    ('translation_radius_angstrom', -0.0), ('seed', True), ('proposal_index', 1),
])
def test_rehashed_inconsistent_receipts_fail_closed(registered, field, value):
    authority, _, ligand, budget = registered
    _, receipt = generate_registered_pose(authority, budget, ligand)
    row = receipt.to_dict()
    row[field] = value
    with pytest.raises(ResearchError):
        require_registered_receipt(_rehash(row))


def test_changed_initial_coordinates_reject_with_rehashed_receipt(registered):
    authority, _, ligand, budget = registered
    _, receipt = generate_registered_pose(authority, budget, ligand)
    row = receipt.to_dict()
    row['initial_coordinates_binary64_hex'][0][0] = float(.01).hex()
    with pytest.raises(ResearchError, match='coordinate fingerprint'):
        require_registered_receipt(_rehash(row))


def test_unchanged_coordinates_with_bad_receipt_digest_reject(registered):
    authority, _, ligand, budget = registered
    _, receipt = generate_registered_pose(authority, budget, ligand)
    row = receipt.to_dict()
    row['receipt_sha256'] = '0'*64
    with pytest.raises(ResearchError, match='receipt digest'):
        require_registered_receipt(row)


def test_rehashed_authority_flags_cannot_claim_external_coordinates(registered):
    authority, _, ligand, budget = registered
    _, receipt = generate_registered_pose(authority, budget, ligand)
    row = receipt.to_dict()
    row['authority_binding']['caller_supplied_ligand_reference_coordinates_allowed'] = True
    row['authority_input_receipt_sha256'] = digest(row['authority_binding'])
    with pytest.raises(ResearchError, match='authority declaration'):
        require_registered_receipt(_rehash(row))
