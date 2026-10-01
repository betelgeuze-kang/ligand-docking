"""F2: real existing D3 and scoring behind a prespecified four-arm policy run."""
from copy import deepcopy
from pathlib import Path

import pytest

from betelgeuze_product.cpu_refinement_v1_2 import policy_adapter as backend
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import FixedReceptorEnvironment, ReferencePhysicsApplicabilityError
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError
from tools.product import compare_prepared_candidate_policies as runner
from tools.product import compare_prepared_candidate_ranks as rank
from tests.unit.test_prepared_candidate_comparison import _protocol, _ref
from tests.unit.test_prepared_rank_workflow import plan, endpoints
from tests.unit.test_cpu_fixed_receptor_pipeline import request_fixture


def protocol_fixture(root, seconds=60):
    base = _protocol(root, seconds=seconds)
    prepared = root / "d3"
    prepared.mkdir()
    request = request_fixture(prepared)
    base.update(schema_version=runner.D3_SCHEMA, calculation={"backend": backend.BACKEND, "score_quantity": backend.SCORE_QUANTITY},
                selection_seed=17, tie_policy="seeded_pool_order", arm_order=list(runner.ARMS))
    base["requests"] = {rid: _ref(root / (rid + ".d3.json"), request) if rid in "ab" else None for rid in "abcd"}
    return base, request


@pytest.fixture(scope="module")
def actual(tmp_path_factory):
    root = tmp_path_factory.mktemp("policy-d3")
    protocol, request = protocol_fixture(root / "input")
    p = plan()
    ready = rank.run(protocol, p, root / "run")
    return root, protocol, request, p, ready


def test_real_D3_called_by_existing_four_arm_runner(actual):
    root, _, _, p, ready = actual
    comparison = runner.read(root / "run/execution/comparison.json")
    for arm in runner.ARMS:
        result = comparison["arms"][arm]
        assert result["cost"]["status"] == "complete", (root / "run/execution" / arm / "worker.log").read_text()
        if arm == "similarity":
            continue
        assert result["score_quantity"] == backend.SCORE_QUANTITY
        assert result["denominator"] == {"requested": 4, "evaluated": 2, "unsupported": 2}
        for row in result["rows"]:
            if row["status"] != "evaluated":
                continue
            evidence = runner.bound(row["d3_report"])
            report = evidence["comparison"]
            assert report["receptor_ligand_interaction_energy_minimized"] is True
            assert row["score"] == row["d3_summary"]["score"]
            assert row["d3_summary"]["work"]["actual_force_evaluation_calls"] > 0
            assert row["d3_summary"]["work"]["score_evaluation_calls"] == 8
            assert any(a["pre_coordinates_sha256"] != a["post_coordinates_sha256"] for a in report["attempts"])
            for attempt in report["attempts"]:
                assert attempt["energy_delta"] <= 0
                assert set(attempt["final_components"]) == {"ligand_internal", "cross_lennard_jones", "cross_screened_coulomb", "total"}
            before = {x["candidate_id"]: x for x in report["arms"]["baseline"]["rows"]}
            for pair, post in zip(report["attempts"], report["arms"]["refined"]["rows"], strict=True):
                assert pair["pre_coordinates_sha256"] == before[pair["candidate_id"]]["coordinates_sha256"]
                assert pair["post_coordinates_sha256"] == post["coordinates_sha256"]
    report = rank.evaluate(ready, root / "metrics", synthetic_ref=endpoints(root, p))
    assert report["calculation"]["backend"] == backend.BACKEND
    assert report["score_quantities"]["engine"] == backend.SCORE_QUANTITY
    assert report["candidate_calculation_observations"]["engine"][0]["d3_summary"]["work"]["actual_force_evaluation_calls"] > 0
    assert report["arm_denominators"]["engine"]["requested"] == 4
    assert not report["ai_advantage_claimed"]


def test_completed_D3_reuse_never_relaunches_worker(actual, monkeypatch):
    root, protocol, _, p, ready = actual
    def forbidden(*args, **kwargs):
        pytest.fail("completed D3 worker launched again")
    monkeypatch.setattr(runner.subprocess, "Popen", forbidden)
    assert rank.run(protocol, p, root / "run", resume=True) == ready


@pytest.mark.parametrize("change", ["backend", "quantity", "schema", "parameters", "frame", "mode", "solvation"])
def test_D3_input_rejected_before_worker(tmp_path, monkeypatch, change):
    protocol, request = protocol_fixture(tmp_path / "input")
    if change in {"backend", "quantity"}:
        protocol["calculation"]["backend" if change == "backend" else "score_quantity"] = "wrong"
    else:
        if change == "schema":
            request["schema_id"] = "prepared_rigid_pose_cross_request_v1"
        elif change == "parameters":
            request["parameters"]["sha256"] = "0" * 64
        elif change == "frame":
            request["pocket"]["coordinate_frame_id"] = "wrong"
        elif change == "mode":
            request["comparison"].update(mode="equal_work_budget", work_units_per_arm=1000)
        else:
            request["solvation"] = request["parameters"]
        protocol["requests"]["a"] = _ref(tmp_path / "changed.json", request)
    def forbidden(*args, **kwargs):
        pytest.fail("worker ran with invalid D3 preparation")
    monkeypatch.setattr(runner.subprocess, "Popen", forbidden)
    with pytest.raises((ValueError, KeyError)):
        runner.run(protocol, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_failed_refinement_preserves_original_candidate_and_work(tmp_path, monkeypatch):
    request = request_fixture(tmp_path)
    def fail(*args):
        raise ReferencePhysicsApplicabilityError("synthetic force failure")
    monkeypatch.setattr(FixedReceptorEnvironment, "evaluate_cross", fail)
    result = backend.evaluate(request)
    summary = backend.summarize(result)
    assert summary["status"] == "evaluated"
    assert summary["refinement_failures"] == 4
    assert summary["refined_selected_count"] == 0
    assert summary["original_selected_count"] > 0
    assert summary["work"]["failed_force_evaluation_calls"] == 4


def test_report_coordinate_or_score_tampering_rejected(actual):
    root, _, request, _, _ = actual
    row = runner.read(root / "run/execution/comparison.json")["arms"]["engine"]["rows"][0]
    evidence = deepcopy(runner.bound(row["d3_report"]))
    evidence["comparison"]["final_selection"]["selected_candidates"][0]["score"] += 1
    with pytest.raises(ResearchError):
        backend.summarize(evidence, request=request)


def test_changed_D3_source_prevents_reuse(actual):
    root, protocol, request, p, _ = actual
    source = Path(request["cross_parameters"]["path"])
    original = source.read_bytes()
    source.write_bytes(original + b"\n")
    try:
        with pytest.raises(ValueError):
            rank.run(protocol, p, root / "run", resume=True)
    finally:
        source.write_bytes(original)


def test_D3_timeout_preserves_unprocessed_denominator(tmp_path):
    protocol, _ = protocol_fixture(tmp_path / "input", seconds=.03)
    result = runner.run(protocol, tmp_path / "run")
    for arm in result["arms"].values():
        assert arm["denominator"]["requested"] == 4
        assert not arm["ranked_record_ids"]
        assert arm["cost"]["status"] in {"budget_exhausted", "worker_failed"}
