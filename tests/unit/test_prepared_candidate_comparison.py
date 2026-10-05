"""Policy, budget and durable-result contracts with separate synthetic labels."""

import copy
import fcntl
import hashlib
import json
from pathlib import Path
import time

import pytest

from tools.product import compare_prepared_candidate_policies as comparison
from tools.product.comparison_morgan_features import features as comparison_features
from tools.product.train_public_assay_selector import features as training_features
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


def test_comparison_morgan_features_match_training_definition():
    import numpy as np

    smiles = [
        "CCCC", "c1ccccc1", "C[C@H](N)O", "F/C=C/F", "[NH4+]",
        "[13CH3]C(=O)O", "C1CCCCC1", "N#N", "O=C([O-])C",
    ]
    expected = training_features(smiles)
    actual = comparison_features(smiles)
    assert expected.shape == actual.shape == (len(smiles), 1024)
    assert np.array_equal(actual, expected)
    assert actual.dtype == expected.dtype
    for bad in ("not_a_smiles", "C(C)(C)(C)(C)C"):
        with pytest.raises(ValueError, match="invalid_inference_smiles"):
            comparison_features([bad])


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
    verification = result["receipt_verification_cost"]
    assert set(verification["arm_wall_seconds"]) == set(comparison.ARMS)
    assert verification["completed_run_only"] is True
    assert all(value >= 0 for value in verification["arm_wall_seconds"].values())
    assert verification["final_source_recheck_wall_seconds"] >= 0
    assert (
        sum(verification["arm_wall_seconds"].values())
        + verification["final_source_recheck_wall_seconds"]
        + result["common_validation_seconds"]
        <= result["orchestrator_wall_seconds"]
    )
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


@pytest.fixture(scope="module")
def integrity_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("comparison-score-integrity")
    result = comparison.run(_protocol(root / "input"), root / "run")
    frozen = comparison.read(root / "run/frozen.json")["payload"]
    return root / "run", frozen, result


@pytest.mark.parametrize(
    "arm,rid,change,error",
    [
        ("similarity", "a", "score", "similarity_score_prediction_mismatch"),
        ("engine", "a", "score", "pose_report_score_mismatch"),
        ("engine", "c", "failed_score", "unscored_comparison_row_has_score"),
        ("engine", "a", "missing_report", "evaluated_rigid_row_missing_pose_report"),
        ("engine", "a", "numeric_denominator", "pose_report_denominator_mismatch"),
        ("engine", "a", "pose_denominator", "pose_report_denominator_mismatch"),
        ("engine", "a", "boolean_score", "invalid_comparison_number"),
        ("engine", "a", "empty_report", "unsupported_report"),
        ("engine", "a", "nonfinite_report", "nonfinite_identity_json"),
    ],
)
def test_resealed_row_cannot_detach_score_from_prediction_or_pose(
    integrity_run, arm, rid, change, error
):
    root, frozen, result = integrity_run
    directory = root / arm
    row_path = directory / (comparison.sha(rid) + ".row.json")
    original_row = row_path.read_bytes()
    wrapped = comparison.read(row_path)
    row = wrapped["payload"]
    report_path = Path(row["pose_report"]["path"]) if row.get("pose_report") else None
    original_report = report_path.read_bytes() if report_path else None
    try:
        if change == "score":
            row["score"] += 1.0
        elif change == "failed_score":
            row["score"] = 1.0
        elif change == "missing_report":
            row.pop("pose_report")
        elif change == "boolean_score":
            row["score"] = True
        elif change == "pose_denominator":
            row["pose_denominator"]["evaluated"] += 1
        elif change == "numeric_denominator":
            row["numeric_denominator"]["passed"] += 1
        else:
            assert report_path is not None
            report_path.write_text(
                '{"schema_version":"prepared_rigid_pose_cross_report_v1","rows":[]}'
                if change == "empty_report" else '{"rows":[NaN]}'
            )
            row["pose_report"]["sha256"] = hashlib.sha256(report_path.read_bytes()).hexdigest()
        row_path.write_text(comparison.canonical({"payload": row, "sha256": comparison.sha(row)}))
        with pytest.raises(ValueError, match=error):
            comparison._arm_summary(directory, frozen, result["binding"], result["arms"][arm]["cost"])
    finally:
        row_path.write_bytes(original_row)
        if report_path is not None:
            report_path.write_bytes(original_report)


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
    order, predictions, setup = comparison._priority(
        frozen, "similarity", directory / "similarity"
    )
    rid = order[0]
    retained = {
        "record_id": rid,
        "arm": "similarity",
        "binding": binding,
        "score": predictions[rid],
        "prediction": predictions[rid],
        "status": "evaluated",
        "completed_monotonic": time.monotonic() - 10,
    }
    comparison.publish(
        directory / "similarity" / (comparison.sha(rid) + ".row.json"),
        {"payload": retained, "sha256": comparison.sha(retained)},
    )
    comparison.publish(
        directory / "similarity/priority.json",
        {"binding": binding, "arm": "similarity", "order": order,
         "predictions": predictions, "setup_cost": setup,
         "evaluation_labels_read": 0},
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
        "not_processed": 2,
        "unsupported": 1,
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
    priority = {"setup_cost": copy.deepcopy(cost)}
    replayed = comparison._replayed_priority_predictions(frozen, "ai_engine", priority)
    assert set(replayed) == set(predicted)
    checkpoint_path = directory / "model/selector.json"
    frozen_fit_path = directory / "model/frozen-fit.json"
    saved_checkpoint = checkpoint_path.read_bytes()
    saved_frozen_fit = frozen_fit_path.read_bytes()
    try:
        checkpoint = comparison.read(checkpoint_path)
        checkpoint["intercept"] += 0.25
        checkpoint_path.write_text(comparison.canonical(checkpoint) + "\n")
        frozen_fit = comparison.read(frozen_fit_path)
        frozen_fit["checkpoint"] = comparison.file_ref(checkpoint_path)
        frozen_fit_path.write_text(comparison.canonical(frozen_fit) + "\n")
        priority["setup_cost"]["model_reference"] = comparison.file_ref(frozen_fit_path)
        with pytest.raises(ValueError, match="priority_model_fit_mismatch"):
            comparison._replayed_priority_predictions(frozen, "ai_engine", priority)
    finally:
        checkpoint_path.write_bytes(saved_checkpoint)
        frozen_fit_path.write_bytes(saved_frozen_fit)
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


@pytest.mark.parametrize(
    "change,error",
    [
        ("missing", "committed_row_without_priority"),
        ("binding", "worker_observation_binding_mismatch"),
        ("arm", "priority_binding_mismatch"),
        ("prediction", "priority_prediction_pool_mismatch"),
    ],
)
def test_evaluated_similarity_rows_require_bound_priority(integrity_run, change, error):
    root, frozen, result = integrity_run
    directory = root / "similarity"
    path = directory / "priority.json"
    original = path.read_bytes()
    priority = comparison.read(path)
    try:
        if change == "missing":
            path.unlink()
        else:
            if change == "binding":
                priority["binding"] = "wrong"
            elif change == "arm":
                priority["arm"] = "engine"
            else:
                priority["predictions"].pop("a")
            path.write_text(comparison.canonical(priority))
        with pytest.raises(ValueError, match=error):
            comparison._arm_summary(
                directory, frozen, result["binding"], result["arms"]["similarity"]["cost"]
            )
    finally:
        path.write_bytes(original)


@pytest.mark.parametrize(
    "change,error",
    [
        ("order", "priority_order_prediction_mismatch"),
        ("prediction", "priority_model_prediction_mismatch"),
    ],
)
def test_resealed_priority_and_comparison_cannot_forge_selector_order(
    integrity_run, change, error
):
    root, frozen, result = integrity_run
    priority_path = root / "ai_engine/priority.json"
    comparison_path = root / "comparison.json"
    original_priority = priority_path.read_bytes()
    original_comparison = comparison_path.read_bytes()
    try:
        priority = comparison.read(priority_path)
        if change == "order":
            assert len(priority["order"]) >= 2
            priority["order"][:2] = reversed(priority["order"][:2])
        else:
            priority["predictions"][priority["order"][-1]] += 10.0
            priority["order"] = comparison._prediction_order(
                frozen, priority["predictions"]
            )
        priority_path.write_text(comparison.canonical(priority) + "\n")
        resealed = copy.deepcopy(result)
        resealed["arms"]["ai_engine"]["worker_observations"]["priority.json"] = priority
        comparison_path.write_text(comparison.canonical(resealed) + "\n")
        with pytest.raises(ValueError, match=error):
            comparison.run(frozen["protocol"], root, resume=True)
    finally:
        priority_path.write_bytes(original_priority)
        comparison_path.write_bytes(original_comparison)


def test_resealed_model_priority_rows_and_comparison_cannot_forge_fit(integrity_run):
    root, frozen, result = integrity_run
    directory = root / "ai_engine"
    priority_path = directory / "priority.json"
    comparison_path = root / "comparison.json"
    priority = comparison.read(priority_path)
    model_path = Path(priority["setup_cost"]["model_reference"]["path"])
    rows = [directory / (comparison.sha(rid) + ".row.json") for rid in frozen["pool"]]
    paths = [model_path, priority_path, comparison_path, *rows]
    original = {path: path.read_bytes() for path in paths if path.exists()}
    try:
        model = comparison.read(model_path)
        model["intercept"] += 0.25
        model_path.write_text(comparison.canonical(model) + "\n")
        priority["setup_cost"]["model_reference"] = comparison.file_ref(model_path)
        priority["predictions"] = {
            rid: value + 0.25 for rid, value in priority["predictions"].items()
        }
        assert priority["order"] == comparison._prediction_order(
            frozen, priority["predictions"]
        )
        priority_path.write_text(comparison.canonical(priority) + "\n")
        resealed = copy.deepcopy(result)
        arm = resealed["arms"]["ai_engine"]
        arm["worker_observations"]["priority.json"] = priority
        for path in rows:
            if not path.exists():
                continue
            wrapped = comparison.read(path)
            item = wrapped["payload"]
            if item["record_id"] in priority["predictions"]:
                item["prediction"] = priority["predictions"][item["record_id"]]
            wrapped["sha256"] = comparison.sha(item)
            path.write_text(comparison.canonical(wrapped) + "\n")
            for summary_row in arm["rows"]:
                if summary_row["record_id"] == item["record_id"]:
                    summary_row["prediction"] = item["prediction"]
        comparison_path.write_text(comparison.canonical(resealed) + "\n")
        with pytest.raises(ValueError, match="priority_model_fit_mismatch"):
            comparison.run(frozen["protocol"], root, resume=True)
    finally:
        for path, content in original.items():
            path.write_bytes(content)


@pytest.mark.parametrize("missing", [None, "scikit-learn", "scipy"])
def test_selector_dependency_versions_bind_missing_without_importing(monkeypatch, missing):
    observed = []

    def version(name):
        observed.append(name)
        if name == missing:
            raise comparison.importlib.metadata.PackageNotFoundError(name)
        return {"scikit-learn": "test-sklearn", "scipy": "test-scipy"}[name]

    monkeypatch.setattr(comparison.importlib.metadata, "version", version)
    assert comparison._selector_dependency_versions() == {
        "scikit-learn": None if missing == "scikit-learn" else "test-sklearn",
        "scipy": None if missing == "scipy" else "test-scipy",
    }
    assert observed == ["scikit-learn", "scipy"]


@pytest.mark.parametrize("dependency", ["scikit-learn", "scipy"])
@pytest.mark.parametrize("replacement", [None, "different-installed-version"])
def test_selector_dependency_change_rejects_resume_before_receipt_replay(
    integrity_run, monkeypatch, dependency, replacement
):
    root, frozen, _ = integrity_run
    versions = copy.deepcopy(frozen["runtime"]["comparison_selector_dependencies"])
    assert versions[dependency] is not None
    versions[dependency] = replacement
    monkeypatch.setattr(comparison, "_selector_dependency_versions", lambda: versions)

    def unexpected_replay(*args):
        raise AssertionError("receipt replay before runtime binding check")

    monkeypatch.setattr(comparison, "_arm_summary", unexpected_replay)
    with pytest.raises(ValueError, match="resume_input_or_runtime_changed"):
        comparison.run(frozen["protocol"], root, resume=True)


@pytest.mark.parametrize(
    "change,error",
    [
        ("row_prediction", "committed_row_prediction_mismatch"),
        ("missing_first_row", "committed_row_priority_sequence_mismatch"),
        ("reordered_completion", "committed_row_priority_sequence_mismatch"),
    ],
)
def test_committed_rows_remain_bound_to_priority_prefix(integrity_run, change, error):
    root, frozen, result = integrity_run
    directory = root / "ai_engine"
    priority = comparison.read(directory / "priority.json")
    assert len(priority["order"]) >= 2
    paths = [directory / (comparison.sha(rid) + ".row.json")
             for rid in priority["order"][:2]]
    original = {path: path.read_bytes() for path in paths}
    try:
        if change == "missing_first_row":
            paths[0].unlink()
        else:
            wrapped = comparison.read(paths[0])
            if change == "row_prediction":
                wrapped["payload"]["prediction"] += 0.25
            else:
                second = comparison.read(paths[1])
                wrapped["payload"]["completed_monotonic"] = (
                    second["payload"]["completed_monotonic"] + 1.0
                )
            wrapped["sha256"] = comparison.sha(wrapped["payload"])
            paths[0].write_text(comparison.canonical(wrapped) + "\n")
        with pytest.raises(ValueError, match=error):
            comparison._arm_summary(
                directory, frozen, result["binding"], result["arms"]["ai_engine"]["cost"]
            )
    finally:
        for path, content in original.items():
            path.write_bytes(content)


def test_reused_selector_reference_cannot_be_replaced(integrity_run, tmp_path):
    root, frozen, _ = integrity_run
    priority = comparison.read(root / "ai_engine/priority.json")
    reference = priority["setup_cost"]["model_reference"]
    reused = copy.deepcopy(frozen)
    reused["reused_ai_model"] = {"reference": reference}
    replacement = tmp_path / "same-model-different-reference.json"
    replacement.write_bytes(Path(reference["path"]).read_bytes())
    priority["setup_cost"]["model_reference"] = comparison.file_ref(replacement)
    with pytest.raises(ValueError, match="priority_model_source_mismatch"):
        comparison._replayed_priority_predictions(reused, "ai_engine", priority)


def test_empty_prediction_pool_still_checks_ai_fit(tmp_path):
    protocol = _protocol(tmp_path / "input")
    for row in protocol["source"]["rows"]:
        if row["role"] == "development_test":
            row["smiles"] = None
    frozen, _ = comparison.freeze(protocol)
    directory = tmp_path / "ai_engine"
    directory.mkdir()
    order, predictions, setup = comparison._priority(frozen, "ai_engine", directory)
    assert order == [] and predictions == {}
    priority = {"setup_cost": setup}
    assert comparison._replayed_priority_predictions(frozen, "ai_engine", priority) == {}
    assert comparison._replayed_priority_predictions(frozen, "similarity", {}) == {}
    model_path = Path(setup["model_reference"]["path"])
    model = comparison.read(model_path)
    model["intercept"] += 0.25
    model_path.write_text(comparison.canonical(model) + "\n")
    priority["setup_cost"]["model_reference"] = comparison.file_ref(model_path)
    with pytest.raises(ValueError, match="priority_model_fit_mismatch"):
        comparison._replayed_priority_predictions(frozen, "ai_engine", priority)


def test_seeded_tied_priority_is_replayed_without_record_id_tiebreak(tmp_path):
    protocol = _protocol(tmp_path / "input")
    protocol.update(schema_version=comparison.ORDERED_SCHEMA, selection_seed=17,
                    tie_policy="seeded_pool_order", arm_order=list(comparison.ARMS))
    for row in protocol["source"]["rows"]:
        if row["role"] == "fit":
            row["fit_value"] = 6.0
    frozen, _ = comparison.freeze(protocol)
    directory = tmp_path / "similarity"
    directory.mkdir()
    order, predictions, setup = comparison._priority(frozen, "similarity", directory)
    ordinal = {rid: index for index, rid in enumerate(frozen["pool"])}
    expected = sorted(predictions, key=lambda rid: (
        comparison.sha({"seed": 17, "pool_index": ordinal[rid]}), ordinal[rid]
    ))
    assert set(predictions.values()) == {6.0}
    assert order == expected
    replayed = comparison._replayed_priority_predictions(
        frozen, "similarity", {"setup_cost": setup}
    )
    assert replayed == predictions
    assert comparison._prediction_order(frozen, replayed) == expected


@pytest.fixture
def v4_cross_assay_duplicate_source(tmp_path):
    """Synthetic V4 sources: duplicate structure, distinct assays, one component."""
    import gzip
    from tools.product import public_assay_components as components
    from tools.product import public_assay_dataset as common
    from tools.product import public_chembl_assay_dataset as intake
    from tools.product import public_chembl_receptor_intake as receptor
    from tests.unit import test_public_chembl_receptor_intake as receptor_fixture

    root = tmp_path / "v4-synthetic-source"
    root.mkdir()
    manifest_ref, entries = receptor_fixture.synthetic_intake.__wrapped__(root)
    first = comparison.bound(entries[0]["metadata_origin"])
    entry = entries[1]
    metadata = comparison.bound(entry["metadata_origin"])
    metadata.update(canonical_smiles=first["canonical_smiles"],
                    assay_chembl_id="CHEMBL99992")

    def rewrite(reference, payload):
        path = Path(reference["path"])
        path.write_text(comparison.canonical(payload) + "\n")
        return comparison.file_ref(path)

    entry["metadata_origin"] = rewrite(entry["metadata_origin"], metadata)
    native = comparison.bound(entry["activity_origin"])
    native.update(canonical_smiles=metadata["canonical_smiles"],
                  assay_chembl_id=metadata["assay_chembl_id"])
    entry["activity_origin"] = rewrite(entry["activity_origin"], native)
    method = comparison.bound(entry["method_origin"])
    method["assay_chembl_id"] = metadata["assay_chembl_id"]
    entry["method_origin"] = rewrite(entry["method_origin"], method)
    primary = comparison.bound(entry["primary_origin"])
    primary["native_activity"] = native
    entry["primary_origin"] = rewrite(entry["primary_origin"], primary)

    # Rebuild the identity node from the changed source metadata rather than
    # overriding a derived component assignment or cached intake row.
    manifest = comparison.bound(manifest_ref)
    context_path = Path(manifest["identity_context"]["path"])
    nodes = [json.loads(line) for line in gzip.decompress(context_path.read_bytes()).decode().splitlines()]
    role = comparison.bound(entry["role_origin"])
    node = components.node_from_raw(
        {"ChEMBL Assay ID": metadata["assay_chembl_id"],
         "ChEMBL Document ID": metadata["document_chembl_id"]},
        common.chemical_identity(metadata["canonical_smiles"]),
        node_id=entry["node_id"], record_id=role["record_id"],
        ligand_id="chembl:molecule:" + metadata["molecule_chembl_id"],
        extra_declarations=[{"role": role["assigned_role"]}],
    )
    nodes = [node if old["node_id"] == node["node_id"] else old for old in nodes]
    context_path.write_bytes(gzip.compress(
        "".join(comparison.canonical(item) + "\n" for item in nodes).encode(), mtime=0
    ))
    manifest["identity_context"] = comparison.file_ref(context_path)
    metadata_path = Path(manifest["metadata_records"]["path"])
    metadata_path.write_text("".join(comparison.canonical(item) + "\n" for item in entries))
    manifest["metadata_records"] = comparison.file_ref(metadata_path)
    manifest_ref = rewrite(manifest_ref, manifest)
    output = tmp_path / "v4-fit-intake"
    summary = receptor.build(manifest_ref["path"], manifest_ref["sha256"], output)
    assert summary["schema_version"] == intake.SCHEMA_V4
    assert summary["point_eligible"] == 6
    return {"kind": "chembl_fit_intake", "input_dir": str(output),
            "summary_sha256": comparison.file_ref(output / "summary.json")["sha256"]}


def test_v4_replay_uses_component_weights_across_assays(
    v4_cross_assay_duplicate_source, tmp_path
):
    import numpy as np
    from sklearn.linear_model import Ridge

    source = v4_cross_assay_duplicate_source
    rows, _ = comparison.load_rows(source)
    pool = [row["record_id"] for row in rows if row["role"] == "development_test"]
    protocol = {
        "schema_version": comparison.SCHEMA, "source": source,
        "requests": dict.fromkeys(pool), "budget_seconds_per_arm": 20.0,
        "max_engine_calls_per_arm": 2, "top_k": 1,
    }
    frozen, _ = comparison.freeze(protocol)
    selected = [row for row in frozen["rows"]
                if row["role"] == "fit" and row["fit_value"] is not None and row["smiles"]]
    assert [row["record_id"] for row in selected] == [f"chembl:activity:{i}" for i in range(1, 7)]
    assert selected[0]["smiles"] == selected[1]["smiles"]
    assert selected[0]["component_id"] == selected[1]["component_id"]
    assert selected[0]["assay_id"] != selected[1]["assay_id"]
    assert len({row["component_id"] for row in selected}) == 2
    assert all(row["fit_value"] is None for row in frozen["rows"] if row["role"] != "fit")
    matrix = comparison_features([row["smiles"] for row in selected])
    observed = np.asarray([row["fit_value"] for row in selected], dtype=np.float64)
    # The two cross-assay repeats share a component/structure and total weight 1.
    expected = Ridge(alpha=10.0, solver="cholesky").fit(
        matrix, observed, sample_weight=np.asarray([0.5, 0.5, 1.0, 1.0, 1.0, 1.0])
    )
    # Every assay/structure pair is unique; the incorrect legacy weighting is 1.
    assert len({(row["assay_id"], row["smiles"]) for row in selected}) == len(selected)
    wrong = Ridge(alpha=10.0, solver="cholesky").fit(
        matrix, observed, sample_weight=np.ones(len(selected))
    )
    assert (not np.allclose(expected.coef_, wrong.coef_, rtol=1e-12, atol=1e-12)
            or not np.isclose(expected.intercept_, wrong.intercept_, rtol=1e-12, atol=1e-12))
    directory = tmp_path / "v4-ai-arm"
    directory.mkdir()
    _, predictions, setup = comparison._priority(frozen, "ai_engine", directory)
    priority = {"setup_cost": copy.deepcopy(setup)}
    payload = comparison.bound(priority["setup_cost"]["model_reference"])
    training = comparison.bound(payload["protocol"])
    checkpoint = comparison.bound(payload["checkpoint"])
    assert training["fit_replicate_weighting"] == (
        "inverse_count_per_connected_source_component_and_canonical_isomeric_structure"
    )
    assert np.allclose(checkpoint["coefficients"], expected.coef_, rtol=1e-12, atol=1e-12)
    assert np.isclose(checkpoint["intercept"], expected.intercept_, rtol=1e-12, atol=1e-12)
    assert checkpoint["product_ranking_enabled"] is False
    assert checkpoint["physical_energy"] is False
    assert frozen["scientifically_validated"] is False
    replayed = comparison._replayed_priority_predictions(frozen, "ai_engine", priority)
    assert set(replayed) == set(predictions) == set(pool)
    assert all(np.isclose(replayed[rid], predictions[rid], rtol=1e-12, atol=1e-12) for rid in pool)

    # Reseal the checkpoint and its wrapper with an assay-weighted fit, keeping
    # valid source/protocol references. Fit replay must detect the substitution.
    checkpoint["coefficients"] = wrong.coef_.tolist()
    checkpoint["intercept"] = float(wrong.intercept_)
    checkpoint_path = Path(payload["checkpoint"]["path"])
    checkpoint_path.write_text(comparison.canonical(checkpoint) + "\n")
    payload["checkpoint"] = comparison.file_ref(checkpoint_path)
    payload_path = Path(priority["setup_cost"]["model_reference"]["path"])
    payload_path.write_text(comparison.canonical(payload) + "\n")
    priority["setup_cost"]["model_reference"] = comparison.file_ref(payload_path)
    with pytest.raises(ValueError, match="priority_model_fit_mismatch"):
        comparison._replayed_priority_predictions(frozen, "ai_engine", priority)
