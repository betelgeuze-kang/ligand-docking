"""F1: no pair work in plan validation; completed output can be finalized safely."""
from copy import deepcopy
from pathlib import Path

import pytest

from betelgeuze_engine.product import paired_rank_metrics as metric
from tools.product import compare_prepared_candidate_ranks as rank
from tools.product import compare_prepared_candidate_policies as runner
from tools.product import rank_publication as publication
from tests.unit.test_prepared_candidate_comparison import _protocol
from tests.unit.test_prepared_rank_workflow import plan, endpoints


@pytest.mark.parametrize("count", [2, 64, 256, 512])
def test_plan_validation_never_enumerates_pairs(monkeypatch, count):
    def forbidden(*args, **kwargs):
        pytest.fail("plan validation enumerated candidate pairs")
    monkeypatch.setattr(metric, "combinations", forbidden)
    outcomes = {str(i): None for i in range(count)}
    result = metric.validate_cohort(outcomes, {"a": {}, "b": {}}, [["a", "b"]])
    assert result["pair_arm_work_reserved"] == count * (count - 1) // 2 * 4


@pytest.mark.parametrize("change", ["unknown", "duplicate", "budget", "score", "endpoint"])
def test_plan_and_computation_share_rejection(change):
    endpoints, arms, comparisons, kwargs = {"a": {"value": 1, "relation": "="}, "b": None}, {"x": {}, "y": {}}, [["x", "y"]], {}
    if change == "unknown":
        comparisons = [["x", "other"]]
    elif change == "duplicate":
        comparisons *= 2
    elif change == "budget":
        kwargs["max_pair_work"] = 1
    elif change == "score":
        arms["x"]["a"] = True
    else:
        endpoints["a"]["relation"] = ">="
    for function in (metric.validate_cohort, metric.compare_cohort):
        with pytest.raises(ValueError):
            function(endpoints, arms, comparisons, **kwargs)


@pytest.fixture(scope="module")
def execution(tmp_path_factory):
    root = tmp_path_factory.mktemp("rank-f1")
    protocol = _protocol(root / "input", seconds=45)
    p = plan()
    ready = rank.run(protocol, p, root / "run")
    return root, protocol, p, ready


def test_ready_binds_observed_cost(execution):
    root, _, p, ready = execution
    receipt = runner.bound(ready)
    assert receipt["schema_version"] == "prepared_rank_ready_v2"
    cost = runner.bound(receipt["cost"])
    assert cost["prior_invocation_cost_unknown"] is False
    publication.validate_run_cost(cost, runner.bound(receipt["comparison"])["binding"], runner.sha(p))
    assert (root / "run/run-cost.json").exists()


@pytest.mark.parametrize("failed_file", ["run-cost.json", "ready.json"])
def test_run_finalization_failure_does_not_repeat_engine(tmp_path, monkeypatch, failed_file):
    protocol = _protocol(tmp_path / "input", seconds=45)
    p, out = plan(), tmp_path / "run"
    original = runner.publish
    def publish(path, value, **kwargs):
        if Path(path).name == failed_file:
            raise OSError("synthetic publication failure")
        return original(path, value, **kwargs)
    monkeypatch.setattr(runner, "publish", publish)
    with pytest.raises(OSError):
        rank.run(protocol, p, out)
    assert (out / "execution/comparison.json").exists()
    assert not (out / "ready.json").exists()
    committed = {str(path.relative_to(out)): path.read_bytes() for path in (out / "execution").rglob("*") if path.is_file()}
    monkeypatch.setattr(runner, "publish", original)
    def forbidden(*args, **kwargs):
        pytest.fail("completed workers were launched again")
    monkeypatch.setattr(runner.subprocess, "Popen", forbidden)
    ready = rank.run(protocol, p, out, resume=True)
    assert committed == {str(path.relative_to(out)): path.read_bytes() for path in (out / "execution").rglob("*") if path.is_file()}
    cost = runner.bound(runner.bound(ready)["cost"])
    assert cost["prior_invocation_cost_unknown"] is (failed_file == "run-cost.json")


@pytest.mark.parametrize("failed_file", ["report.json", "complete.json"])
def test_resume_publication_does_not_recompute_metrics(execution, tmp_path, monkeypatch, failed_file):
    _, _, p, ready = execution
    ep = endpoints(tmp_path, p)
    out = tmp_path / "metrics"
    publish = runner.publish
    def fail(path, value, **kwargs):
        if Path(path).name == failed_file:
            raise OSError("synthetic finalization interruption")
        return publish(path, value, **kwargs)
    monkeypatch.setattr(runner, "publish", fail)
    with pytest.raises(OSError):
        rank.evaluate(ready, out, synthetic_ref=ep, details=True)
    assert (out / "staged-report.json").exists()
    assert not (out / "complete.json").exists()
    retained = runner.read(out / "staged-report.json")["report"]
    monkeypatch.setattr(runner, "publish", publish)
    def forbidden(*args, **kwargs):
        pytest.fail("committed metrics were recomputed")
    monkeypatch.setattr(metric, "compare_cohort", forbidden)
    recovered = rank.evaluate(ready, out, synthetic_ref=ep, details=True, resume=True)
    assert recovered == retained
    assert (out / "complete.json").exists()
    before = {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}
    assert rank.evaluate(ready, out, synthetic_ref=ep, details=True, resume=True) == retained
    assert before == {p.name: p.read_bytes() for p in out.iterdir() if p.is_file()}


@pytest.mark.parametrize("change", ["details", "endpoint", "stage", "chunk", "report"])
def test_resume_rejects_changed_or_damaged_evidence(execution, tmp_path, change):
    _, _, p, ready = execution
    ep = endpoints(tmp_path, p)
    out = tmp_path / "metrics"
    rank.evaluate(ready, out, synthetic_ref=ep, details=True)
    detail = True
    if change == "details":
        detail = False
    elif change == "endpoint":
        Path(ep["path"]).write_text("{}")
    elif change == "stage":
        (out / "staged-report.json").write_text("{}")
    elif change == "report":
        (out / "report.json").write_text("{}")
    else:
        chunk = next(out.glob("*-000000.json"))
        chunk.write_text("[]")
    with pytest.raises((ValueError, KeyError)):
        rank.evaluate(ready, out, synthetic_ref=ep, details=detail, resume=True)


def test_original_failure_and_missingness_are_preserved(execution, tmp_path):
    _, _, p, ready = execution
    report = rank.evaluate(ready, tmp_path / "metrics", synthetic_ref=endpoints(tmp_path, p))
    assert report["arm_denominators"]["engine"] == {"requested": 4, "evaluated": 2, "failed": 1, "unsupported": 1}
    assert report["full_candidate_denominator"] == 4
    assert not report["run_cost"]["prior_invocation_cost_unknown"]


def test_cost_corruption_rejects_before_outcome_read(execution, tmp_path, monkeypatch):
    root, _, p, ready = execution
    file = root / "run/run-cost.json"
    original = file.read_bytes()
    file.write_bytes(b"{}")
    ep = endpoints(tmp_path, p)
    real = runner.bound
    def bound(ref):
        if ref == ep:
            pytest.fail("labels read before cost validation")
        return real(ref)
    monkeypatch.setattr(runner, "bound", bound)
    try:
        with pytest.raises(ValueError):
            rank.evaluate(ready, tmp_path / "metrics", synthetic_ref=ep)
    finally:
        file.write_bytes(original)


def test_changed_plan_cannot_resume(execution, monkeypatch):
    root, protocol, p, _ = execution
    changed = deepcopy(p)
    changed["comparisons"].reverse()
    with pytest.raises(ValueError, match="rank_resume_plan"):
        rank.run(protocol, changed, root / "run", resume=True)
