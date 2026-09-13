"""Policy, budget and durable-result contracts with separate synthetic labels."""

import copy
import fcntl
import hashlib
import json
from pathlib import Path
import time

import pytest

from tools.product import compare_prepared_candidate_policies as comparison
from tests.unit.test_prepared_rigid_poses import _request
from tests.unit import test_public_chembl_staged_intake as native_fixture


@pytest.fixture
def native_source(tmp_path):
    return native_fixture.source.__wrapped__(tmp_path)


def _ref(path, value):
    path.write_text(json.dumps(value))
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _protocol(tmp_path, *, seconds=20.0, calls=10):
    tmp_path.mkdir(exist_ok=True, parents=True)
    rows = []
    for rid, role, smiles, label in [
        ("fit-a", "fit", "CCCC", 5.0),
        ("fit-b", "fit", "CCNCC", 7.0),
        ("fit-c", "fit", "CCCCCO", 6.0),
        ("cal-a", "calibration", "c1ccccc1", None),
        ("a", "development_test", "CCCCN", None),
        ("b", "development_test", "CCCCCC", None),
        ("c", "development_test", "CCCCS", None),
        ("d", "development_test", None, None),
    ]:
        rows.append(
            {
                "record_id": rid,
                "role": role,
                "component_id": rid + "-component",
                "smiles": smiles,
                "fit_value": label,
                "assay_id": "synthetic-one-assay",
            }
        )
    request = _request(tmp_path / "prepared")
    refs = {}
    for rid in "abc":
        value = copy.deepcopy(request)
        if rid == "b":
            value["poses"][0]["translation_angstrom"][0] = 0.8
        if rid == "c":
            value["poses"][0]["translation_angstrom"][0] = 1000.0
        refs[rid] = _ref(tmp_path / (rid + ".request.json"), value)
    refs["d"] = None
    return {
        "schema_version": comparison.SCHEMA,
        "source": {"kind": "synthetic_constants", "rows": rows},
        "requests": refs,
        "budget_seconds_per_arm": seconds,
        "max_engine_calls_per_arm": calls,
        "top_k": 2,
    }


@pytest.mark.parametrize(
    "change",
    [
        "evaluation_label",
        "component",
        "chemical_identity",
        "missing_candidate",
        "extra_field",
    ],
)
def test_leakage_or_denominator_change_rejected_before_run(tmp_path, change):
    protocol = _protocol(tmp_path)
    rows = protocol["source"]["rows"]
    if change == "evaluation_label":
        rows[-2]["fit_value"] = 8.0
    elif change == "component":
        rows[-2]["component_id"] = rows[0]["component_id"]
    elif change == "chemical_identity":
        rows[-2]["smiles"] = rows[0]["smiles"]
    elif change == "missing_candidate":
        protocol["requests"].pop("d")
    else:
        rows[-2]["experimental_value"] = 8.0
    with pytest.raises(ValueError):
        comparison.run(protocol, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_four_real_cpu_arms_failure_denominator_and_resume(tmp_path):
    protocol = _protocol(tmp_path)
    before = copy.deepcopy(protocol)
    output = tmp_path / "run"
    result = comparison.run(protocol, output)
    assert set(result["arms"]) == set(comparison.ARMS)
    assert result["pool"] == list("abcd")
    for name, arm in result["arms"].items():
        assert arm["cost"]["status"] == "complete", (
            name,
            (output / name / "worker.log").read_text(),
        )
        assert arm["denominator"]["requested"] == 4
        assert set(r["record_id"] for r in arm["rows"]) == set("abcd")
        assert (
            sum(n for key, n in arm["denominator"].items() if key != "requested") == 4
        )
        assert arm["combined_assay_energy_score"] is None
        assert (
            arm["worker_observations"]["priority.json"]["evaluation_labels_read"] == 0
        )
        assert (
            arm["worker_observations"]["worker-complete.json"]["process_peak_rss_kib"]
            > 0
        )
    assert result["arms"]["similarity"]["denominator"] == {
        "requested": 4,
        "evaluated": 3,
        "unsupported": 1,
    }
    assert result["arms"]["engine"]["denominator"] == {
        "requested": 4,
        "evaluated": 2,
        "failed": 1,
        "unsupported": 1,
    }
    engine = {r["record_id"]: r for r in result["arms"]["engine"]["rows"]}
    assert engine["c"]["pose_denominator"]["failed"] == 1
    for arm in ("ai_engine", "similarity_engine"):
        other = {r["record_id"]: r for r in result["arms"][arm]["rows"]}
        assert (
            other["a"]["score"] == engine["a"]["score"]
            and other["b"]["score"] == engine["b"]["score"]
        )
    assert (
        result["evaluation_labels_read"] == 0 and not result["scientifically_validated"]
    )
    original_files = {
        str(p.relative_to(output)): p.read_bytes()
        for p in output.rglob("*")
        if p.is_file()
    }
    assert comparison.run(protocol, output, resume=True) == result
    assert original_files == {
        str(p.relative_to(output)): p.read_bytes()
        for p in output.rglob("*")
        if p.is_file()
    }
    assert protocol == before
    committed = output / "engine" / (comparison.sha("a") + ".row.json")
    saved = committed.read_bytes()
    tampered = json.loads(saved)
    tampered["payload"]["score"] = -999.0
    committed.write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match="committed_comparison_row_mismatch"):
        comparison.run(protocol, output, resume=True)
    committed.write_bytes(saved)
    reuse_protocol = copy.deepcopy(protocol)
    reuse_protocol["reuse_ai_from"] = comparison.file_ref(output / "comparison.json")
    reuse_dir = tmp_path / "reuse-run"
    reused = comparison.run(reuse_protocol, reuse_dir)
    prior_setup = result["arms"]["ai_engine"]["worker_observations"]["priority.json"]
    reuse_setup = reused["arms"]["ai_engine"]["worker_observations"]["priority.json"]
    assert reuse_setup["predictions"] == prior_setup["predictions"]
    assert (
        reuse_setup["setup_cost"]["model_reference"]
        == prior_setup["setup_cost"]["model_reference"]
    )
    assert reuse_setup["setup_cost"]["mode"] == "model_reuse"
    assert not (reuse_dir / "ai_engine/synthetic-model.json").exists()
    altered = copy.deepcopy(reuse_protocol)
    altered["source"]["rows"][0]["fit_value"] += 1.0
    with pytest.raises(ValueError, match="reused_model_source_or_protocol_changed"):
        comparison.freeze(altered)
    model_path = Path(prior_setup["setup_cost"]["model_reference"]["path"])
    original_model = model_path.read_bytes()
    model_path.write_bytes(original_model + b" ")
    with pytest.raises(ValueError, match="comparison_source_hash_mismatch"):
        comparison.run(reuse_protocol, reuse_dir, resume=True)
    model_path.write_bytes(original_model)
    labels = _ref(
        tmp_path / "evaluation-labels.json",
        {"a": True, "b": False, "c": None, "d": True},
    )
    metrics = comparison.evaluate_synthetic(
        {
            "path": str(output / "comparison.json"),
            "sha256": hashlib.sha256(
                (output / "comparison.json").read_bytes()
            ).hexdigest(),
        },
        {
            "path": str(output / "frozen.json"),
            "sha256": hashlib.sha256((output / "frozen.json").read_bytes()).hexdigest(),
        },
        labels,
        tmp_path / "metrics.json",
    )
    assert metrics["metrics"]["engine"]["full_pool_coverage"] == 0.5
    assert metrics["metrics"]["engine"]["tie_expected_known_active_hits"] == 1
    assert not metrics["ai_advantage_claimed"]
    # Mutation cannot masquerade as reuse, even when a request's declared hash is unchanged.
    source = Path(
        comparison.bound(protocol["requests"]["a"])["prepared_input"]["protein_pdb"][
            "path"
        ]
    )
    source.write_text(source.read_text() + "REMARK changed\n")
    with pytest.raises(ValueError, match="resume_input_or_runtime_changed"):
        comparison.run(protocol, output, resume=True)


def test_hard_time_budget_keeps_all_candidates_and_has_no_free_retry(tmp_path):
    protocol = _protocol(tmp_path, seconds=0.03)
    output = tmp_path / "run"
    result = comparison.run(protocol, output)
    for arm in result["arms"].values():
        assert arm["cost"]["status"] == "budget_exhausted"
        assert arm["denominator"] == {"requested": 4, "not_processed": 4}
        assert arm["cost"]["measured_process_wall_seconds"] >= 0.03
    assert comparison.run(protocol, output, resume=True) == result


def test_engine_call_cap_keeps_failures_and_remaining_denominator(tmp_path):
    protocol = _protocol(tmp_path, calls=1)
    result = comparison.run(protocol, tmp_path / "run")
    for name in ("engine", "ai_engine", "similarity_engine"):
        assert (
            result["arms"][name]["worker_observations"]["worker-complete.json"][
                "engine_calls"
            ]
            == 1
        )
        assert result["arms"][name]["denominator"]["requested"] == 4
    assert result["arms"]["similarity"]["denominator"]["evaluated"] == 3


def test_interrupted_attempt_forfeits_budget_and_does_not_rerun(tmp_path):
    protocol = _protocol(tmp_path)
    frozen, _ = comparison.freeze(protocol)
    directory = tmp_path / "run"
    directory.mkdir()
    binding = comparison.sha(frozen)
    comparison.publish(
        directory / "frozen.json", {"payload": frozen, "sha256": binding}
    )
    for arm in comparison.ARMS:
        (directory / arm).mkdir()
        comparison.publish(
            directory / arm / "attempt.json",
            {
                "binding": binding,
                "started_monotonic": time.monotonic() - 20,
                "deadline": time.monotonic() - 1,
            },
        )
    retained = {
        "record_id": "a",
        "arm": "similarity",
        "binding": binding,
        "score": 1.0,
        "status": "evaluated",
        "completed_monotonic": time.monotonic() - 10,
    }
    comparison.publish(
        directory / "similarity" / (comparison.sha("a") + ".row.json"),
        {"payload": retained, "sha256": comparison.sha(retained)},
    )
    with (directory / "similarity/worker.lock").open("a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="comparison_worker_still_running"):
            comparison.run(protocol, directory, resume=True)
    result = comparison.run(protocol, directory, resume=True)
    assert all(
        a["cost"]["status"] == "interrupted_budget_forfeited"
        for a in result["arms"].values()
    )
    assert result["arms"]["similarity"]["denominator"] == {
        "requested": 4,
        "evaluated": 1,
        "not_processed": 3,
    }
    assert all(
        a["denominator"] == {"requested": 4, "not_processed": 4}
        for arm, a in result["arms"].items()
        if arm != "similarity"
    )


def test_boundary_ties_and_unknowns_have_independent_expected_counts():
    result = {
        "pool": list("abcd"),
        "arms": {
            "similarity": {
                "rows": [{"record_id": rid, "score": 10.0} for rid in "abc"],
                "ranked_record_ids": list("abc"),
            }
        },
    }
    metric = comparison._label_metrics(
        result,
        {"protocol": {"top_k": 2}},
        {"a": True, "b": False, "c": None, "d": True},
    )["similarity"]
    assert metric["tie_expected_known_active_hits"] == pytest.approx(2 / 3)
    assert metric["tie_expected_unknown_labels"] == pytest.approx(2 / 3)
    assert metric["tie_expected_known_labels"] == pytest.approx(4 / 3)
    assert metric["known_positive_recall"] == pytest.approx(1 / 3)
    assert metric["full_pool_coverage"] == 0.75


def test_native_adapter_uses_existing_preassignment_loader(monkeypatch):
    from tools.product import train_public_chembl_selector as existing

    calls = []

    def rejected(*args):
        calls.append(args)
        raise ValueError("reserved_metadata_component")

    monkeypatch.setattr(existing, "load_intake", rejected)
    with pytest.raises(ValueError, match="reserved_metadata_component"):
        comparison.load_rows(
            {
                "kind": "chembl_fit_intake",
                "input_dir": "/unused",
                "summary_sha256": "a" * 64,
            }
        )
    assert calls == [(Path("/unused"), "a" * 64, "fit")]


def test_native_shaped_synthetic_intake_preserves_roles_and_reuses_actual_trainer(
    native_source,
):
    source = native_source
    native_fixture.build(source, native_fixture.capture(source))
    fit_dir = source["root"] / "fit-intake"
    ref = {
        "kind": "chembl_fit_intake",
        "input_dir": str(fit_dir),
        "summary_sha256": hashlib.sha256(
            (fit_dir / "summary.json").read_bytes()
        ).hexdigest(),
    }
    rows, provenance = comparison.load_rows(ref)
    assert len(rows) == 40
    assert all(r["fit_value"] is None for r in rows if r["role"] != "fit")
    assert (
        sum(r["fit_value"] is not None for r in rows) == source["plan"]["counts"]["fit"]
    )
    assert provenance["split_plan_sha256"] == source["manifest"]["split_plan"]["sha256"]
    pool = [r["record_id"] for r in rows if r["role"] == "development_test"]
    protocol = {
        "schema_version": comparison.SCHEMA,
        "source": ref,
        "requests": dict.fromkeys(pool),
        "budget_seconds_per_arm": 20.0,
        "max_engine_calls_per_arm": 2,
        "top_k": 2,
    }
    frozen, _ = comparison.freeze(protocol)
    directory = source["root"] / "native-arm"
    directory.mkdir()
    order, predicted, cost = comparison._priority(frozen, "ai_engine", directory)
    assert set(order) == set(pool) == set(predicted)
    saved = comparison.read(directory / "model/frozen-fit.json")
    assert saved["evaluation_values_read"] == 0
    assert saved["split_plan_sha256"] == provenance["split_plan_sha256"]
    assert cost["mode"] == "cold_fit_included"
    # Exercise the complete native-shaped route with synthetic API data only.
    run_dir = source["root"] / "native-run"
    result = comparison.run(protocol, run_dir)
    frozen_fit_path = run_dir / "ai_engine/model/frozen-fit.json"
    frozen_fit = {
        "path": str(frozen_fit_path),
        "sha256": hashlib.sha256(frozen_fit_path.read_bytes()).hexdigest(),
    }
    native_fixture.build(
        source, native_fixture.capture(source, "evaluation", frozen_fit), "evaluation"
    )
    eval_dir = source["root"] / "evaluation-intake"
    result_ref = {
        "path": str(run_dir / "comparison.json"),
        "sha256": hashlib.sha256(
            (run_dir / "comparison.json").read_bytes()
        ).hexdigest(),
    }
    frozen_ref = {
        "path": str(run_dir / "frozen.json"),
        "sha256": hashlib.sha256((run_dir / "frozen.json").read_bytes()).hexdigest(),
    }
    evaluated = comparison.evaluate_native(
        result_ref,
        frozen_ref,
        eval_dir,
        hashlib.sha256((eval_dir / "summary.json").read_bytes()).hexdigest(),
        source["root"] / "native-metrics.json",
    )
    assert evaluated["requested"] == len(pool) and evaluated["known"] == len(pool)
    assert sum(
        item["similarity"]["requested"]
        for item in evaluated["metrics_by_assay"].values()
    ) == len(pool)
    assert evaluated["scientifically_validated"] is False
    assert evaluated["same_prepared_assay_state_verified"] is False
    assert result["evaluation_labels_read"] == 0
    reuse_protocol = copy.deepcopy(protocol)
    reuse_protocol["reuse_ai_from"] = result_ref
    reused = comparison.run(reuse_protocol, source["root"] / "native-reuse-run")
    cold_priority = result["arms"]["ai_engine"]["worker_observations"]["priority.json"]
    reuse_priority = reused["arms"]["ai_engine"]["worker_observations"]["priority.json"]
    assert reuse_priority["predictions"] == cold_priority["predictions"]
    assert reuse_priority["setup_cost"]["mode"] == "model_reuse"
    assert not (source["root"] / "native-reuse-run/ai_engine/model").exists()
    bad_dir = source["root"] / "foreign-evaluation"
    bad_dir.mkdir()
    foreign = _ref(bad_dir / "summary.json", {"split_plan_sha256": "wrong"})
    with pytest.raises(ValueError, match="native_evaluation_role_scope_mismatch"):
        comparison.evaluate_native(
            result_ref,
            frozen_ref,
            bad_dir,
            foreign["sha256"],
            source["root"] / "must-not-exist.json",
        )
    assert not (source["root"] / "must-not-exist.json").exists()


def test_synthetic_labels_cannot_be_read_before_frozen_result_validation(
    tmp_path, monkeypatch
):
    reads = []
    original = comparison.bound

    def track(ref):
        reads.append(ref["path"])
        return original(ref)

    monkeypatch.setattr(comparison, "bound", track)
    result = _ref(tmp_path / "result.json", {"binding": "wrong"})
    frozen = _ref(tmp_path / "frozen.json", {"sha256": "wrong", "payload": {}})
    labels = {"path": str(tmp_path / "labels-must-not-exist.json"), "sha256": "a" * 64}
    with pytest.raises(ValueError, match="synthetic_evaluation_freeze_mismatch"):
        comparison.evaluate_synthetic(result, frozen, labels, tmp_path / "metrics.json")
    assert labels["path"] not in reads
