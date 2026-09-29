"""Policy, budget and durable-result contracts with separate synthetic labels."""

import copy
from dataclasses import replace
import fcntl
import hashlib
import json
from pathlib import Path
import time

import pytest

from tools.product import compare_prepared_candidate_policies as comparison
from tools.product.comparison_morgan_features import features as comparison_features
from tools.product.train_public_assay_selector import features as training_features
from tests.unit.test_prepared_rigid_poses import _pose, _request
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
    _comparison_charge_source(request)
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


def _comparison_charge_source(request, token="-0.1"):
    """Use a comparison-only ITP within its one-decimal print resolution."""
    source = request["prepared_input"]["ligand_itp"]
    path = Path(source["path"])
    original = path.read_text()
    assert "C1 1 -0.3 12.011" in original
    path.write_text(original.replace("C1 1 -0.3 12.011", f"C1 1 {token} 12.011"))
    source["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def _zero_lj_source(request):
    _comparison_charge_source(request)
    for name in ("protein_atomtypes", "ligand_atomtypes"):
        source = request["prepared_input"][name]
        path = Path(source["path"])
        path.write_text(path.read_text().replace("0.300000 0.836800", "0.300000 0.000000"))
        source["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def test_hard_overlap_screen_excludes_numerically_passing_attractive_pose(tmp_path):
    from tools.product.verify_prepared_cross_numerics import check_report

    protocol = _protocol(tmp_path / "input")
    mixed = _request(tmp_path / "mixed-source")
    _zero_lj_source(mixed)
    mixed["poses"] = [_pose("near", -3.2), _pose("far")]
    protocol["requests"]["a"] = _ref(tmp_path / "mixed.request.json", mixed)
    overlap_only = _request(tmp_path / "overlap-source")
    _zero_lj_source(overlap_only)
    overlap_only["poses"] = [_pose("near-only", -3.2)]
    protocol["requests"]["b"] = _ref(tmp_path / "overlap.request.json", overlap_only)

    output = tmp_path / "run"
    result = comparison.run(protocol, output)
    engine = {row["record_id"]: row for row in result["arms"]["engine"]["rows"]}
    mixed_row = engine["a"]
    report = comparison.read(mixed_row["pose_report"]["path"])
    assert report["denominator"]["evaluated"] == 2
    assert check_report(report)["status"] == "passed"
    near_energy, far_energy = [
        row["result"]["quantities"]["cross_total_kcal_per_mol"] for row in report["rows"]
    ]
    assert near_energy < far_energy
    assert [pose["status"] for pose in mixed_row["hard_overlap_screen"]["poses"]] == [
        "hard_overlap", "eligible"
    ]
    assert mixed_row["hard_overlap_screen"]["poses"][0]["minimum_cross_distance_angstrom"] == pytest.approx(0.8)
    assert mixed_row["selected_pose"] == {"request_index": 1, "pose_id": "far", "score": far_energy}
    assert mixed_row["status"] == "evaluated" and mixed_row["score"] == far_energy

    blocked = engine["b"]
    blocked_report = comparison.read(blocked["pose_report"]["path"])
    assert blocked_report["denominator"]["evaluated"] == 1
    assert check_report(blocked_report)["status"] == "passed"
    assert blocked["status"] == "failed" and blocked["score"] is None
    assert blocked["reason"] == "no_hard_overlap_screen_eligible_pose"
    assert blocked["selected_pose"] is None

    row_path = output / "engine" / (comparison.sha("a") + ".row.json")
    saved = row_path.read_bytes()
    try:
        wrapped = comparison.read(row_path)
        tampered = wrapped["payload"]
        tampered["hard_overlap_screen"]["poses"][0]["status"] = "eligible"
        tampered["hard_overlap_screen"]["eligible_pose_count"] = 2
        tampered["selected_pose"] = {"request_index": 0, "pose_id": "near", "score": near_energy}
        tampered["score"] = near_energy
        row_path.write_text(comparison.canonical({"payload": tampered, "sha256": comparison.sha(tampered)}))
        with pytest.raises(ValueError, match="pose_report_hard_overlap_screen_mismatch"):
            comparison._arm_summary(
                output / "engine", comparison.read(output / "frozen.json")["payload"],
                result["binding"], result["arms"]["engine"]["cost"],
            )
    finally:
        row_path.write_bytes(saved)


def test_hard_overlap_screen_fails_closed_on_unavailable_coordinates():
    report = {"preparation": {"source_receptor_coordinates_angstrom": [[0.0, 0.0, 0.0]]},
              "rows": [{"case_id": "near", "evaluated_ligand_coordinates_angstrom": [[0.8, 0.0, 0.0]]},
                       {"case_id": "edge", "evaluated_ligand_coordinates_angstrom": [[1.0, 0.0, 0.0]]}]}
    screen = comparison._hard_overlap_screen(report)
    assert [row["status"] for row in screen["poses"]] == ["hard_overlap", "eligible"]
    report["rows"][1]["evaluated_ligand_coordinates_angstrom"][0][0] = float("nan")
    screen = comparison._hard_overlap_screen(report)
    assert [row["status"] for row in screen["poses"]] == ["hard_overlap", "unavailable"]
    assert screen["eligible_pose_count"] == 0
    report["preparation"]["source_receptor_coordinates_angstrom"] = None
    screen = comparison._hard_overlap_screen(report)
    assert [row["status"] for row in screen["poses"]] == ["unavailable", "unavailable"]


def test_charge_rank_screen_excludes_inconsistent_state_but_retains_numeric_evidence(tmp_path):
    from tools.product.verify_prepared_cross_numerics import check_report

    protocol = _protocol(tmp_path / "input")
    conflict = _request(tmp_path / "conflict")
    sdf = conflict["prepared_input"]["ligand_sdf"]
    sdf_path = Path(sdf["path"])
    sdf_path.write_text(sdf_path.read_text().replace(
        "M  END\n", "M  CHG  1   1   1\nM  END\n"))
    sdf["sha256"] = hashlib.sha256(sdf_path.read_bytes()).hexdigest()
    protocol["requests"]["a"] = _ref(tmp_path / "conflict.request.json", conflict)

    exact = _request(tmp_path / "exact")
    _comparison_charge_source(exact, token="0.0")
    protocol["requests"]["b"] = _ref(tmp_path / "exact.request.json", exact)

    output = tmp_path / "run"
    result = comparison.run(protocol, output)
    rows = {row["record_id"]: row for row in result["arms"]["engine"]["rows"]}
    rejected = rows["a"]
    report = comparison.read(rejected["pose_report"]["path"])
    assert report["denominator"]["evaluated"] == 2
    assert check_report(report)["status"] == "passed"
    assert rejected["numeric_denominator"]["passed"] == 2
    assert [pose["status"] for pose in rejected["hard_overlap_screen"]["poses"]] == [
        "eligible", "eligible"]
    charge = rejected["ligand_net_charge_screen"]
    assert charge["sdf_formal_charge_sum_e"] == 1
    assert charge["itp_printed_partial_charge_sum_e"] == "-0.3"
    assert charge["difference_e"] == "-1.3"
    assert charge["status"] == "different_integral_state_range"
    assert charge["rank_eligible"] is False
    assert rejected["status"] == "failed" and rejected["score"] is None
    assert rejected["reason"] == "ligand_net_charge_rank_ineligible"
    assert rejected["selected_pose"] is None
    matched = rows["b"]
    assert matched["ligand_net_charge_screen"]["status"] == "equal_as_encoded"
    assert matched["status"] == "evaluated" and matched["selected_pose"] is not None

    row_path = output / "engine" / (comparison.sha("a") + ".row.json")
    saved = row_path.read_bytes()
    try:
        wrapped = comparison.read(row_path)
        tampered = wrapped["payload"]
        tampered["ligand_net_charge_screen"]["rank_eligible"] = True
        row_path.write_text(comparison.canonical({"payload": tampered,
                                                 "sha256": comparison.sha(tampered)}))
        with pytest.raises(ValueError, match="pose_report_charge_screen_mismatch"):
            comparison._arm_summary(
                output / "engine", comparison.read(output / "frozen.json")["payload"],
                result["binding"], result["arms"]["engine"]["cost"],
            )
    finally:
        row_path.write_bytes(saved)


def test_charge_rank_screen_uses_print_resolution_and_abstains_when_unreadable(tmp_path):
    from betelgeuze_engine.product.prepared_rigid_poses import evaluate_rigid_pose_request
    from betelgeuze_product.prepared_net_charge_screen import ligand_net_charge_screen

    within = _request(tmp_path / "within")
    _comparison_charge_source(within, token="-0.1")
    screen = ligand_net_charge_screen(evaluate_rigid_pose_request(within))
    assert screen["difference_e"] == "-0.1"
    assert screen["print_resolution_bound_e"] == "0.1"
    assert screen["status"] == "within_print_resolution"
    assert screen["rank_eligible"] is True

    coarse = _request(tmp_path / "coarse")
    sdf = coarse["prepared_input"]["ligand_sdf"]
    sdf_path = Path(sdf["path"])
    sdf_path.write_text(sdf_path.read_text().replace(
        "M  END\n", "M  CHG  1   1   1\nM  END\n"))
    sdf["sha256"] = hashlib.sha256(sdf_path.read_bytes()).hexdigest()
    _comparison_charge_source(coarse, token="0")
    screen = ligand_net_charge_screen(evaluate_rigid_pose_request(coarse))
    assert screen["difference_e"] == "-1"
    assert screen["print_resolution_bound_e"] == "1"
    assert screen["status"] == "different_integral_state_range"
    assert screen["rank_eligible"] is False

    unreadable = _request(tmp_path / "unreadable")
    _comparison_charge_source(unreadable, token="1e-4096")
    screen = ligand_net_charge_screen(evaluate_rigid_pose_request(unreadable))
    assert screen["status"] == "indeterminate"
    assert screen["rank_eligible"] is False


def test_prepared_source_receipt_reuses_canonical_document_without_changing_identity(tmp_path):
    from betelgeuze_engine.product.prepared_gromacs_input import load_prepared_gromacs_components
    from betelgeuze_engine.product.prepared_validation import prepared_validation_scope
    from betelgeuze_engine_v2.molecular import (
        MolecularIntegrityError, canonical_coordinates_sha256, canonical_system_sha256,
    )
    from betelgeuze_engine_v2.molecular.serialization import (
        CanonicalSerializationError, canonical_json_value, canonical_system_document,
    )

    request = _request(tmp_path)
    with prepared_validation_scope():
        receptor, ligand, receptor_parameters, ligand_parameters, _ = (
            load_prepared_gromacs_components(request["prepared_input"])
        )
    for system, parameters in (
        (receptor, receptor_parameters),
        (ligand, ligand_parameters),
    ):
        expected = {
            "system_sha256": canonical_system_sha256(system),
            "coordinates_sha256": canonical_coordinates_sha256(system),
            "system": canonical_json_value(canonical_system_document(system)),
            "nonbonded_parameters": parameters,
        }
        assert comparison._canonical_prepared_system_source(system, parameters) == expected

    receptor.coordinates[0, 0, 0] += 0.25
    with pytest.raises(MolecularIntegrityError, match="changed after construction"):
        comparison._canonical_prepared_system_source(receptor, receptor_parameters)

    colliding = replace(ligand, metadata={1: "number", "1": "string"})
    with pytest.raises(CanonicalSerializationError, match="mapping keys collide"):
        comparison._canonical_prepared_system_source(colliding, ligand_parameters)


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


def test_four_real_cpu_arms_failure_denominator_and_resume(tmp_path, monkeypatch):
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
    dependencies = comparison.read(output / "frozen.json")["payload"]["runtime"][
        "comparison_selector_dependencies"
    ]
    assert dependencies == {
        name: comparison.importlib.metadata.version(name) for name in ("scikit-learn", "scipy")
    }
    installed_version = comparison.importlib.metadata.version
    for changed_name in ("scikit-learn", "scipy"):
        with monkeypatch.context() as changed:
            def drifted_version(name):
                version = installed_version(name)
                return version + ".drift" if name == changed_name else version

            changed.setattr(comparison.importlib.metadata, "version", drifted_version)
            with pytest.raises(ValueError, match="resume_input_or_runtime_changed"):
                comparison.run(protocol, output, resume=True)
    # Resume's source/runtime preflight rejects drift without any endpoint input.
    assert comparison.run(protocol, output, resume=True) == result
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


@pytest.mark.parametrize("measure,error", [
    ("wall_seconds", "comparison_row_wall_exceeds_arm_wall"),
    ("cpu_seconds", "comparison_row_cpu_exceeds_worker_cpu"),
])
def test_resealed_candidate_cost_cannot_exceed_worker_total(integrity_run, measure, error):
    root, frozen, result = integrity_run
    arm, rid = "similarity", "a"
    row_path = root / arm / (comparison.sha(rid) + ".row.json")
    result_path = root / "comparison.json"
    original_row, original_result = row_path.read_bytes(), result_path.read_bytes()
    try:
        wrapped = comparison.read(row_path)
        observed = (result["arms"][arm]["cost"]["measured_process_wall_seconds"]
                    if measure == "wall_seconds" else
                    result["arms"][arm]["worker_observations"]["worker-complete.json"]["process_cpu_seconds"])
        wrapped["payload"]["cost"][measure] = observed + 10.0
        wrapped["sha256"] = comparison.sha(wrapped["payload"])
        row_path.write_text(comparison.canonical(wrapped) + "\n")
        resealed = copy.deepcopy(result)
        resealed["arms"][arm]["rows"] = [
            wrapped["payload"] if row["record_id"] == rid else row
            for row in resealed["arms"][arm]["rows"]]
        result_path.write_text(comparison.canonical(resealed) + "\n")
        with pytest.raises(ValueError, match=error):
            comparison.run(frozen["protocol"], root, resume=True)
    finally:
        row_path.write_bytes(original_row)
        result_path.write_bytes(original_result)


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


@pytest.mark.parametrize(
    "arm,rid,change,error",
    [
        ("similarity", "a", "score", "similarity_score_prediction_mismatch"),
        ("engine", "a", "score", "pose_report_score_mismatch"),
        ("engine", "c", "failed_score", "unscored_comparison_row_has_score"),
        ("engine", "a", "missing_report", "evaluated_rigid_row_missing_pose_report"),
        ("engine", "a", "numeric_denominator", "pose_report_denominator_mismatch"),
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


def test_resealed_candidate_cannot_borrow_another_valid_pose_report(integrity_run):
    root, frozen, result = integrity_run
    directory = root / "engine"
    source = comparison.read(directory / (comparison.sha("a") + ".row.json"))["payload"]
    target_path = directory / (comparison.sha("b") + ".row.json")
    original_target = target_path.read_bytes()
    target = comparison.read(target_path)["payload"]
    assert source["score"] != target["score"]
    try:
        target.update(
            score=source["score"],
            pose_report=source["pose_report"],
            pose_denominator=source["pose_denominator"],
            numeric_denominator=source["numeric_denominator"],
        )
        target_path.write_text(
            comparison.canonical({"payload": target, "sha256": comparison.sha(target)})
        )
        with pytest.raises(ValueError, match="pose_report_request_mismatch"):
            comparison._arm_summary(
                directory, frozen, result["binding"], result["arms"]["engine"]["cost"]
            )
    finally:
        target_path.write_bytes(original_target)


def test_valid_pose_report_cannot_borrow_another_prepared_source(integrity_run):
    from betelgeuze_engine.product.prepared_pose_journal import _input_binding

    root, _, _ = integrity_run
    row = comparison.read(root / "engine" / (comparison.sha("a") + ".row.json"))[
        "payload"
    ]
    report = comparison.read(row["pose_report"]["path"])
    other_request = _request(root / "other-input")
    with pytest.raises(ValueError, match="pose_report_request_mismatch"):
        comparison._check_pose_report_request(
            report, other_request, _input_binding(other_request)
        )


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
    output = tmp_path / "run"
    result = comparison.run(protocol, output)
    for name in ("engine", "ai_engine", "similarity_engine"):
        arm = result["arms"][name]
        assert arm["cost"]["status"] == "complete"
        assert arm["worker_observations"]["worker-complete.json"]["engine_calls"] == 1
        assert (
            arm["worker_observations"]["worker-complete.json"]["stop_reason"]
            == "engine_call_cap"
        )
        assert arm["denominator"]["requested"] == 4
        ordered = arm["worker_observations"]["priority.json"]["order"]
        unprocessed = [row for row in arm["rows"] if row["status"] == "not_processed"]
        assert {row["record_id"] for row in unprocessed} == set(ordered[1:])
        assert all(row["reason"] == "engine_call_cap" for row in unprocessed)
        assert sum(
            count for status, count in arm["denominator"].items() if status != "requested"
        ) == 4
    assert result["arms"]["similarity"]["denominator"]["evaluated"] == 3
    assert (
        result["arms"]["similarity"]["worker_observations"]["worker-complete.json"][
            "stop_reason"
        ]
        == "order_exhausted"
    )
    # The worker can observe its deadline and exit before the parent marks the
    # arm budget exhausted. Preserve that observed reason for ordered skips.
    worker_path = output / "engine/worker-complete.json"
    worker_bytes = worker_path.read_bytes()
    try:
        worker = comparison.read(worker_path)
        worker["stop_reason"] = "deadline"
        worker_path.write_text(comparison.canonical(worker))
        frozen = comparison.read(output / "frozen.json")["payload"]
        replay = comparison._arm_summary(
            output / "engine", frozen, result["binding"], result["arms"]["engine"]["cost"]
        )
        assert all(
            row["reason"] == "deadline"
            for row in replay["rows"]
            if row["status"] == "not_processed"
        )
    finally:
        worker_path.write_bytes(worker_bytes)


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
        "cost": {"wall_seconds": 0.0, "cpu_seconds": 0.0},
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
    development_ids = sorted(a["activity_id"] for a in source["plan"]["assignments"]
                             if a["role"] == "development_test")
    assert len(development_ids) >= 4

    def censor_synthetic_outcomes(response):
        for activity in response["activities"]:
            if activity["activity_id"] in development_ids[:4]:
                position = development_ids.index(activity["activity_id"])
                relation = (">", ">=", "<", ">")[position]
                published = "999.999" if position == 3 else "1000"
                activity.update(value=published, standard_value="1000",
                                relation=relation, standard_relation=relation)

    evaluation_capture = native_fixture.rewrite_capture_response(
        native_fixture.capture(source, "evaluation", frozen_fit), censor_synthetic_outcomes
    )
    native_fixture.build(source, evaluation_capture, "evaluation")
    eval_dir = source["root"] / "evaluation-intake"
    evaluated_records = [json.loads(line) for line in (eval_dir / "records.jsonl").read_text().splitlines()]
    by_activity = {r["activity_id"]: r for r in evaluated_records}
    for activity_id in development_ids[:4]:
        row = by_activity[activity_id]
        assert row["eligible_for_point_model"] is False
        assert row["eligible_for_threshold_classification"] is True
        assert row["threshold_classification_issues"] == []
        assert row["observation"]["source_activity"]["relation"] in {">", ">=", "<"}
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
    assert evaluated["requested"] == len(pool) and evaluated["known"] == len(pool) - 2
    assert evaluated["unknown"] == 2
    assert evaluated["classification_basis_counts"] == {
        "censored_bound_overlaps_threshold": 1,
        "exact_point": len(pool) - 4,
        "left_censored_bound_proves_active": 1,
        "right_censored_bound_proves_inactive": 1,
        "source_bound_not_jointly_proven": 1,
    }
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
