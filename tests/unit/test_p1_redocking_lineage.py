from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.docking.development_lineage import emit_coordinate_snapshot  # noqa: E402
from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint  # noqa: E402
from tools.redocking_development_p1 import DevelopmentObservation  # noqa: E402


def _fixture_module(filename):
    spec = importlib.util.spec_from_file_location(
        "p1_fixture_" + filename, Path(__file__).with_name(filename + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_coordinate_snapshots_have_no_mutable_tensor_alias():
    coordinates = torch.tensor([[1.0, -0.0, 3.0]], dtype=torch.float64)
    proposal = SimpleNamespace(
        coordinates=coordinates,
        proposal_index=2,
        candidate_id="p2",
        fingerprint_sha256="b" * 64,
    )
    events = []
    emit_coordinate_snapshot(
        lambda *args: events.append(args), "proposal_generated", proposal
    )
    payload = events[0][2]
    assert payload["coordinate_fingerprint_sha256"] == coordinate_fingerprint(
        coordinates
    )
    coordinates.add_(100)
    assert payload["coordinates_binary64"]["values_hex"] == [
        (1.0).hex(),
        (-0.0).hex(),
        (3.0).hex(),
    ]
    payload["coordinates_binary64"]["values_hex"][0] = "0x0.0p+0"
    assert coordinates[0, 0] == 101


def test_v7_observation_preserves_coordinates_and_original_receipts():
    f = _fixture_module("test_engine_v2_element_contact_round8")
    receptor, ligand = f._receptor(overlapping=True), f._ligand()
    authority = f.build_element_aware_authenticated_known_pocket_docking_problem(
        receptor, ligand, f._pocket()
    )
    proposal = f._baseline(authority)
    original = proposal.coordinates.clone()
    kwargs = dict(implementation_source_sha256="b" * 64, v3_proposal_indices=(0,))
    baseline = f.InteractionAwareTorsionContactEnsembleRefinerV7(
        authority, receptor, ligand, **kwargs
    )
    events = []
    observer = DevelopmentObservation(
        "fixture", event_sink=events.append, evaluator_identity="a" * 64
    )
    observed = f.InteractionAwareTorsionContactEnsembleRefinerV7(
        authority, receptor, ligand, development_observer=observer.core_event, **kwargs
    )
    expected = baseline.refine(proposal, max_steps=2)
    actual = observed.refine(proposal, max_steps=2)
    assert torch.equal(expected.coordinates, actual.coordinates)
    assert torch.equal(expected.torsion_angles, actual.torsion_angles)
    assert expected.fingerprint_sha256 == actual.fingerprint_sha256
    assert dict(baseline.receipts[proposal.fingerprint_sha256]) == dict(
        observed.receipts[proposal.fingerprint_sha256]
    )
    assert torch.equal(proposal.coordinates, original)
    snapshots = {e["stage"]: e["details"] for e in events if e["phase"] == "snapshot"}
    assert set(snapshots) == {"post_v6", "post_v7_optimization", "refinement_selected"}
    assert (
        snapshots["refinement_selected"]["coordinate_fingerprint_sha256"]
        == actual.coordinate_fingerprint_sha256
    )
    assert snapshots["post_v7_optimization"]["objective_unit"] == "angstrom^4"
    observer.assert_healthy()


def test_guided_generation_observation_preserves_scores_and_order():
    f = _fixture_module("test_engine_v2_scorer_v1_stage5")
    authority, receptor, ligand = f._authority()
    context = f.build_guided_placement_context(authority, receptor, ligand)
    events = []
    observer = DevelopmentObservation(
        "fixture", event_sink=events.append, evaluator_identity="a" * 64
    )
    kwargs = dict(
        receptor_system=receptor, ligand_system=ligand, diversity_rmsd_angstrom=0.0
    )
    before = f.run_authenticated_scorer_v1_guided_search(
        authority,
        f._budget(),
        f._scorer(authority, receptor, ligand),
        context,
        **kwargs,
    )
    after = f.run_authenticated_scorer_v1_guided_search(
        authority,
        f._budget(),
        f._scorer(authority, receptor, ligand),
        context,
        development_observer=observer.core_event,
        **kwargs,
    )
    assert before.to_dict() == after.to_dict()
    generated = [e for e in events if e["stage"] == "proposal_generated"]
    assert len(generated) == f._budget().candidate_count
    assert [e["details"]["proposal_index"] for e in generated] == list(
        range(len(generated))
    )
    assert events[0]["phase"] == "start" and events[-1]["phase"] == "complete"
