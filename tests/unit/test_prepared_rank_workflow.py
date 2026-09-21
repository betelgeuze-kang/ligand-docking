"""Real existing CPU arms, prespecified comparisons and post-freeze outcomes."""
from copy import deepcopy
import hashlib

import pytest

from tools.product import compare_prepared_candidate_ranks as rank
from tools.product import compare_prepared_candidate_policies as runner
from tests.unit.test_prepared_candidate_comparison import _protocol, _ref
from tests.unit import test_public_chembl_staged_intake as native


def plan(assays=None, target="synthetic-target"):
    return {"schema_version": rank.PLAN_SCHEMA, "target_annotation": target,
            "endpoint": "IC50", "domain_id": "catalogue_development_not_physical_state",
            "unit": "nM", "assay_ids": ["synthetic-one-assay"] if assays is None else assays,
            "comparisons": [["engine", "ai_engine"], ["similarity_engine", "ai_engine"]],
            "score_directions": dict(rank.DIRECTIONS), "max_pair_work": 100000}


def endpoints(tmp_path, p):
    return _ref(tmp_path / "endpoints.json", {"schema_version": "synthetic_rank_endpoints_v1",
        "plan_sha256": runner.sha(p), "endpoints": {"a": {"relation": "=", "value": 1.},
        "b": {"relation": ">", "value": 2.}, "c": None, "d": {"relation": "=", "value": 3.}}})


@pytest.fixture(scope="module")
def actual(tmp_path_factory):
    root = tmp_path_factory.mktemp("actual-ranks")
    protocol = _protocol(root / "input", seconds=30)
    p = plan()
    ready = rank.run(protocol, p, root / "run")
    return root, protocol, p, ready


def test_four_real_arms_and_common_pairs(actual):
    root, protocol, p, ready = actual
    result = runner.read(root / "run/execution/comparison.json")
    assert result["evaluation_labels_read"] == 0
    assert all(data["cost"]["status"] == "complete" for data in result["arms"].values())
    assert result["arms"]["engine"]["denominator"] == {"requested": 4, "evaluated": 2, "failed": 1, "unsupported": 1}
    ep = endpoints(root, p)
    report = rank.evaluate(ready, root / "metrics", synthetic_ref=ep, details=True)
    summary = report["metrics_by_assay"]["synthetic-one-assay"]["summary"]
    assert summary["candidate_denominator"] == 4
    assert summary["full_coverage"]["engine"]["scores_available"] == 2
    assert summary["full_coverage"]["engine"]["counts"]["endpoint_missing"] == 3
    for common in summary["common_coverage"]:
        assert common["common_candidate_ids"] == ["a", "b"]
        assert common["second_minus_first_on_common_pairs"] == 0
    assert report["arm_denominators"]["engine"]["failed"] == 1
    assert not report["ai_advantage_claimed"] and not report["same_wall_time_guaranteed"]
    assert report["labels_read_after_frozen_predictions"]
    assert (root / "metrics/complete.json").exists()
    assert rank.run(protocol, p, root / "run", resume=True) == ready
    changed = deepcopy(p)
    changed["comparisons"].reverse()
    with pytest.raises(ValueError, match="rank_resume_plan"):
        rank.run(protocol, changed, root / "run", resume=True)


@pytest.mark.parametrize("change", ["plan", "comparison", "frozen", "committed_row"])
def test_prediction_drift_rejected_before_any_endpoint_read(actual, tmp_path, monkeypatch, change):
    root, _, p, ready = actual
    ep = endpoints(tmp_path, p)
    if change == "plan":
        path = root / "run/rank-plan.json"
    elif change == "comparison":
        path = root / "run/execution/comparison.json"
    elif change == "frozen":
        path = root / "run/execution/frozen.json"
    else:
        path = root / "run/execution/engine" / (runner.sha("a") + ".row.json")
    original = path.read_bytes()
    path.write_bytes(original + b" ")
    # For committed rows, change the actual payload (outer source hash isn't stored).
    if change == "committed_row":
        row = runner.read(path)
        row["payload"]["score"] = 999
        path.write_text(runner.canonical(row))
    bound = runner.bound
    seen = []
    def guard(ref):
        if ref["path"] == ep["path"]:
            seen.append("endpoint_read")
            pytest.fail("outcomes accessed before prediction verification")
        return bound(ref)
    monkeypatch.setattr(runner, "bound", guard)
    try:
        with pytest.raises(ValueError):
            rank.evaluate(ready, tmp_path / "out", synthetic_ref=ep)
        assert seen == []
    finally:
        path.write_bytes(original)


@pytest.mark.parametrize("change", ["unit", "direction", "assay", "pairs", "limit", "extra"])
def test_bad_plan_rejected_before_engine(monkeypatch, tmp_path, change):
    protocol = _protocol(tmp_path / "input")
    p = plan()
    if change == "unit":
        p["unit"] = "uM"
    elif change == "direction":
        p["score_directions"]["engine"] = "higher_is_better"
    elif change == "assay":
        p["assay_ids"] = []
    elif change == "pairs":
        p["comparisons"] = [["unknown", "engine"]]
    elif change == "limit":
        p["max_pair_work"] = True
    else:
        p["labels"] = []
    def forbidden(*args, **kwargs):
        pytest.fail("engine invoked before plan admission")
    monkeypatch.setattr(runner, "run", forbidden)
    with pytest.raises(ValueError):
        rank.run(protocol, p, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_budget_exhaustion_keeps_missing_scores(tmp_path):
    protocol = _protocol(tmp_path / "input", seconds=.03)
    p = plan()
    ready = rank.run(protocol, p, tmp_path / "run")
    report = rank.evaluate(ready, tmp_path / "out", synthetic_ref=endpoints(tmp_path, p))
    for arm in report["metrics_by_assay"]["synthetic-one-assay"]["summary"]["full_coverage"].values():
        assert arm["candidate_denominator"] == 4 and arm["scores_available"] == 0
        assert arm["concordance"] is None


def test_native_shaped_actual_intake_without_unbound_label_override(tmp_path):
    source = native.source.__wrapped__(tmp_path)
    native.build(source, native.capture(source))
    fit_dir = tmp_path / "fit-intake"
    source_ref = {"kind": "chembl_fit_intake", "input_dir": str(fit_dir),
                  "summary_sha256": hashlib.sha256((fit_dir / "summary.json").read_bytes()).hexdigest()}
    rows, _ = runner.load_rows(source_ref)
    pool = [r["record_id"] for r in rows if r["role"] == "development_test"]
    p = plan(sorted({r["assay_id"] for r in rows if r["record_id"] in pool}), "CHEMBL3038469")
    protocol = {"schema_version": runner.SCHEMA, "source": source_ref, "requests": dict.fromkeys(pool),
                "budget_seconds_per_arm": 30., "max_engine_calls_per_arm": 2, "top_k": 2}
    ready = rank.run(protocol, p, tmp_path / "run")
    model = runner.file_ref(tmp_path / "run/execution/ai_engine/model/frozen-fit.json")
    capture = native.capture(source, "evaluation", model)
    # New synthetic strict-bound native observation; no source/role gate changed.
    def change(response):
        for row in response["activities"]:
            row["relation"] = row["standard_relation"] = ">"
    capture = native.rewrite_capture_response(capture, change)
    native.build(source, capture, "evaluation")
    evaluation_dir = tmp_path / "evaluation-intake"
    report = rank.evaluate(ready, tmp_path / "metrics", evaluation_dir=evaluation_dir,
        summary_sha256=hashlib.sha256((evaluation_dir / "summary.json").read_bytes()).hexdigest())
    assert report["full_candidate_denominator"] == len(pool)
    assert sum(v["endpoint_status_counts"].get("strict_right_censored", 0) for v in report["metrics_by_assay"].values()) == len(pool)
    for row in report["metrics_by_assay"].values():
        # Two strict lower bounds give no known ordering.
        assert row["summary"]["full_coverage"]["similarity"]["concordance"] is None
    with pytest.raises(ValueError, match="source_kind"):
        rank.evaluate(ready, tmp_path / "bad", synthetic_ref={"path": "/not-read", "sha256": "a" * 64})


@pytest.mark.parametrize("issue", ["reserved_identity_component", "assay_method_or_primary_document_unresolved", "chemical_state_missing", "standard_flag_not_confirmed"])
def test_native_nonmeasurement_gates_are_not_relaxed(issue):
    row = {"observation": {"endpoint": "IC50", "status": "censored", "relation": ">", "value_nm": 1.,
        "upper_value_nm": None, "issues": []}, "admission_issues": ["measurement_not_exact", issue]}
    value, reason = rank._native_endpoint(row, "IC50")
    assert value is None and reason == "source_or_identity_not_admitted"
