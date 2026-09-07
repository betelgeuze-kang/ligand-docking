"""Small synthetic runtime contracts, not molecular qualification evidence."""
from __future__ import annotations

import builtins
import hashlib
import json

import numpy as np
import pytest

from betelgeuze_engine.biodiscovery import screening
from betelgeuze_engine.biodiscovery.manifest import verify_screening_manifest
from betelgeuze_engine.biodiscovery.scoring import single_pose_score
from tests.unit.test_biodiscovery_screening import MINI_PDB


def service():
    return screening.TierBetaScreening(pose_count=2, top_k=2, stability_steps=0, seed=0)


def run(instance=None, **kwargs):
    return (instance or service()).screen(protein_input=MINI_PDB, ligand_input="CCO", **kwargs)


def stage(result, name):
    return next(row["diagnostics"] for row in result.result_manifest["stage_records"] if row["stage_id"] == name)


def test_static_score_contains_only_nonperiodic_cross_lj_pairs():
    protein = np.array([[0., 0., 0.], [0.01, 0., 0.]])
    ligand = np.array([[5., 0., 0.], [5.01, 0., 0.]])
    value, diagnostic = single_pose_score(protein, ligand)
    distance = np.linalg.norm(protein[:, None] - ligand[None, :], axis=-1)
    expected = (4. * 0.2 * ((3.8 / distance)**12 - (3.8 / distance)**6)).sum()
    assert value == pytest.approx(expected, rel=1e-5)
    assert diagnostic["internal_energies_included"] is False
    assert diagnostic["pbc_enabled"] is False
    assert set(diagnostic["terms"]) == {"legacy_lj"}
    assert diagnostic["not_evaluated"]["ligand_strain"] == {"status": "not_evaluated", "value": None}
    distant, _ = single_pose_score(protein, ligand + [80., 0., 0.])
    assert distant == 0.


@pytest.mark.parametrize("key,value", [
    ("pose_count", 0), ("pose_count", 1.5), ("top_k", True), ("stability_steps", -1),
    ("stability_steps", "1"), ("seed", None), ("seed", 2**31), ("seed", False),
    ("pocket_cutoff_a", float("nan")), ("stability_dt", 0), ("stability_temp_k", -1),
])
def test_constructor_rejects_malformed_execution_parameters(key, value):
    with pytest.raises(ValueError):
        screening.TierBetaScreening(**{key: value})


def test_no_pocket_is_unlocalized_whole_receptor(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("origin-based pocket selection must not run")
    monkeypatch.setattr(screening, "_resolve_pocket_indices", forbidden)
    result = run()
    assert result.ok, result.blocked_reason
    pocket = stage(result, "pocket_resolution")
    assert pocket["pocket_discovery_performed"] is False
    assert pocket["selection_mode"] == "unlocalized_whole_small_receptor_diagnostic"
    assert result.pocket_residue_indices == list(range(result.protein_residue_count))
    assert result.diagnostics["receptor_proxy"]["dense_diagnostic_cap"] == 512


@pytest.mark.parametrize("broken", [
    np.zeros((2, 3)), np.ones((3, 3), dtype=bool), np.full((3, 3), "1"),
    np.ones((3, 3), dtype=complex), np.ma.array(np.ones((3, 3)), mask=True),
    np.full((3, 3), np.nan), np.full((3, 3), 1e300),
])
def test_rejected_candidate_preserves_successes(monkeypatch, broken):
    original = screening._pose_search_candidates
    def altered(*args, **kwargs):
        candidates, diagnostics = original(*args, **kwargs)
        assert len(candidates) >= 2
        candidates[0] = {**candidates[0], "coords": broken}
        return candidates, diagnostics
    monkeypatch.setattr(screening, "_pose_search_candidates", altered)
    result = run()
    assert result.ok, result.blocked_reason
    ledger = stage(result, "scoring_ranking")
    assert ledger["candidate_accounting"]["input_rejected"] == 1
    assert ledger["candidate_accounting"]["scored_successfully"] == result.poses_scored
    assert all(row["pose_index"] != 0 for row in result.pose_scores)
    assert verify_screening_manifest(json.loads(json.dumps(result.result_manifest, allow_nan=False)))


@pytest.mark.parametrize("name", ["_single_pose_score", "_chemistry_validity_summary"])
def test_partial_evaluation_failure_continues(monkeypatch, name):
    original = getattr(screening, name)
    calls = 0
    def faulty(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("synthetic_candidate_failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(screening, name, faulty)
    result = run()
    assert result.ok, result.blocked_reason
    assert stage(result, "scoring_ranking")["candidate_accounting"]["evaluation_failed"] == 1
    assert all(row["pose_index"] != 0 for row in result.pose_scores)


def test_all_nonfinite_scores_have_signed_failure(monkeypatch):
    monkeypatch.setattr(screening, "_single_pose_score", lambda *args, **kwargs: (float("nan"), {}))
    result = run()
    assert not result.ok
    assert result.poses_scored == 0 and result.pose_scores == []
    assert result.best_score is None
    ledger = stage(result, "scoring_ranking")
    assert ledger["candidate_accounting"]["evaluation_failed"] == 2
    assert all(row["reason"] == "nonfinite_score_component" for row in ledger["candidates"])
    assert result.result_manifest["ranking"]["best_score"] is None
    assert verify_screening_manifest(json.loads(json.dumps(result.result_manifest, allow_nan=False)))


@pytest.mark.parametrize("name", ["_generate_conformers", "_pose_search_candidates"])
def test_early_stage_exception_retains_signed_diagnostics(monkeypatch, name):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic_stage_failure")
    monkeypatch.setattr(screening, name, fail)
    result = run()
    assert not result.ok
    assert "synthetic_stage_failure" in json.dumps(result.result_manifest)
    assert verify_screening_manifest(result.result_manifest)


def test_actual_scored_topk_coordinates_and_order_are_hashed(monkeypatch):
    observed = []
    original = screening._single_pose_score
    def record(protein, ligand, *args, **kwargs):
        observed.append(ligand.copy())
        return original(protein, ligand, *args, **kwargs)
    monkeypatch.setattr(screening, "_single_pose_score", record)
    result = run()
    assert result.ok, result.blocked_reason
    for row in result.pose_scores:
        pose = dict(row["scored_pose"])
        digest = pose.pop("sha256")
        assert digest == hashlib.sha256(json.dumps(pose, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        assert np.asarray(pose["coords_a"]).shape == (3, 3)
        np.testing.assert_array_equal(pose["coords_a"], observed[row["pose_index"]])
        assert pose["ligand_topology"]["coordinate_smiles"] == pose["coordinate_smiles"]
        assert row["ranking_metric"]["name"] == "restricted_cross_component_composite_v2"
        assert row["ligand_topology"]["atom_order_sha256"]


def test_single_read_snapshot_hashes_bytes_not_paths(tmp_path, monkeypatch):
    protein, ligand = tmp_path / "protein.pdb", tmp_path / "ligand.smi"
    protein.write_bytes(MINI_PDB.encode())
    ligand.write_bytes(b"CCO\n")
    original = builtins.open
    reads = {str(protein): 0, str(ligand): 0}
    def counted(path, *args, **kwargs):
        if str(path) in reads:
            reads[str(path)] += 1
        return original(path, *args, **kwargs)
    monkeypatch.setattr(builtins, "open", counted)
    result = service().screen(protein_input=str(protein), ligand_input=str(ligand))
    assert result.ok, result.blocked_reason
    assert reads == {str(protein): 1, str(ligand): 1}
    assert stage(result, "protein_preparation")["protein_input_snapshot"]["sha256"] == hashlib.sha256(MINI_PDB.encode()).hexdigest()
    assert stage(result, "ligand_preparation")["ligand_input_snapshot"]["sha256"] == hashlib.sha256(b"CCO\n").hexdigest()


def test_batch_reuses_receptor_and_evaluator_without_changing_replay(monkeypatch):
    calls = {"parse": 0, "prepare": 0, "field": 0}
    for name, label in (("_resolve_protein_input", "parse"), ("prepare_receptor_proxy", "prepare"), ("make_static_pose_field", "field")):
        original = getattr(screening, name)
        def counted(*args, _original=original, _label=label, **kwargs):
            calls[_label] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(screening, name, counted)
    instance = service()
    results = instance.screen_many(protein_input=MINI_PDB, ligand_inputs=["CCO", "CCO"])
    assert calls == {"parse": 1, "prepare": 1, "field": 1}
    separate = run(instance)
    assert all(item.ok for item in results), [item.blocked_reason for item in results]
    assert all(item.result_manifest["replay_hash"] == separate.result_manifest["replay_hash"] for item in results)
    assert all(item.pose_scores == separate.pose_scores for item in results)
    for item in [*results, separate]:
        elapsed = item.result_manifest["execution_observations"]["elapsed_seconds"]
        assert set(elapsed) == {"preparation", "conformer", "search", "scoring", "total"}
        assert all(value >= 0 for value in elapsed.values())
        assert item.typed_input["seed"] == 0


def test_batch_cache_enforces_larger_ligand_cap(monkeypatch):
    original = screening.prepare_receptor_proxy
    def restricted(*args, **kwargs):
        beads, center, context = original(*args, **kwargs)
        return beads, center, {**context, "dense_diagnostic_cap": len(beads) + 3}
    monkeypatch.setattr(screening, "prepare_receptor_proxy", restricted)
    first, second = service().screen_many(protein_input=MINI_PDB, ligand_inputs=["CCO", "CCCC"])
    assert first.ok
    assert not second.ok and "dense_diagnostic_blocked" in second.blocked_reason
    assert verify_screening_manifest(second.result_manifest)


@pytest.mark.parametrize("kind", ["protein", "ligand"])
def test_invalid_utf8_failure_keeps_consumed_byte_hash(tmp_path, kind):
    path = tmp_path / "invalid_input"
    data = b"invalid\xffinput"
    path.write_bytes(data)
    arguments = {"protein_input": MINI_PDB, "ligand_input": "CCO"}
    arguments[f"{kind}_input"] = str(path)
    result = service().screen(**arguments)
    assert not result.ok
    snapshot = stage(result, f"{kind}_preparation")[f"{kind}_input_snapshot"]
    assert snapshot["sha256"] == hashlib.sha256(data).hexdigest()
    assert snapshot["byte_count"] == len(data)
    assert verify_screening_manifest(result.result_manifest)


@pytest.mark.parametrize("protein,ligand", [("garbage", "CCO"), (MINI_PDB, "")])
def test_preparation_rejection_without_bytes_still_publishes_failure(tmp_path, protein, ligand):
    from betelgeuze_product.tier_beta_vertical_slice import run_tier_beta_vertical_slice_job
    with pytest.raises(RuntimeError):
        run_tier_beta_vertical_slice_job(job_id="synthetic-rejection", results_dir=tmp_path,
                                        request_data={"runner_profile_params": {
                                            "protein_input": protein, "ligand_input": ligand,
                                            "pose_count": 1, "stability_steps": 0}})
    payload = json.loads((tmp_path / "tier_beta_result.json").read_text())
    assert verify_screening_manifest(payload["result_manifest"])
    assert payload["result_manifest"]["status"] == "failed"
    missing_kind = "protein" if protein == "garbage" else "ligand"
    assert payload["request"][f"{missing_kind}_input_sha256"] is None
