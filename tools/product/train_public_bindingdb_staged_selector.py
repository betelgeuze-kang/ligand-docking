"""Fit-only BindingDB selector, frozen metadata predictions, then evaluation."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import time

import numpy as np
from rdkit import rdBase
from sklearn.linear_model import Ridge

from tools.product import public_assay_dataset as common
from tools.product import public_chembl_assay_dataset as bound
from tools.product import public_bindingdb_staged_intake as intake
from tools.product import train_public_assay_selector as existing

MODEL_SCHEMA = "public_bindingdb_preassigned_ridge_v1"
FROZEN_SCHEMA = "public_bindingdb_predictions_before_evaluation_v1"
FEATURES = {**existing.FEATURES, "target_encoding": "one_catalogue_target_annotation_per_model_not_physical_state"}


def implementation_hashes():
    return {**intake.implementation_hashes(), "staged_trainer": common.file_sha(Path(__file__))}


def model_payload(path, expected_sha, target_annotation_sha256, endpoint):
    payload = bound.bound_json({"path": str(path), "sha256": expected_sha})
    if (payload.get("schema_version") != MODEL_SCHEMA or payload.get("features") != FEATURES
            or payload.get("implementation_hashes") != implementation_hashes() or payload.get("rdkit_version") != rdBase.rdkitVersion
            or payload.get("target_annotation_sha256") != target_annotation_sha256 or endpoint not in {"Ki", "IC50"}
            or payload.get("endpoint") != endpoint or payload.get("prediction_quantity") != "negative_log10_molar_" + endpoint
            or payload.get("product_ranking_enabled") is not False or payload.get("customer_execution") is not False
            or payload.get("uncertainty_calibrated") is not False):
        raise ValueError("incompatible_bindingdb_staged_checkpoint")
    coefficients = payload.get("coefficients")
    if (not isinstance(coefficients, list) or len(coefficients) != 1024
            or any(type(value) not in (int, float) for value in coefficients)
            or type(payload.get("intercept")) not in (int, float)
            or type(payload.get("mean_baseline")) not in (int, float)):
        raise ValueError("invalid_bindingdb_model_weights")
    if not np.isfinite(coefficients).all() or not np.isfinite([payload["intercept"], payload["mean_baseline"]]).all():
        raise ValueError("nonfinite_bindingdb_model_weights")
    return payload


def predict_checkpoint(path, expected_sha, smiles, target_annotation_sha256, endpoint):
    payload = model_payload(path, expected_sha, target_annotation_sha256, endpoint)
    return existing.features(smiles) @ np.asarray(payload["coefficients"], dtype=np.float64) + payload["intercept"]


def metadata_predictions(checkpoint, checkpoint_sha, selected, manifest, plan):
    scope = manifest["scope"]
    payload = model_payload(checkpoint, checkpoint_sha, scope["target_annotation_sha256"], scope["endpoint"])
    assignments = bound.unique_index(plan["assignments"], "record_id")
    supported = [row for row in selected if not intake.chemistry_issues(row["chemical_identity"], scope)]
    scores = predict_checkpoint(checkpoint, checkpoint_sha,
        [row["chemical_identity"]["canonical_isomeric_smiles"] for row in supported], scope["target_annotation_sha256"], scope["endpoint"])
    values = {row["record_id"]: float(value) for row, value in zip(supported, scores)}
    result = []
    for row in selected:
        assignment = assignments[row["record_id"]]
        issues = intake.chemistry_issues(row["chemical_identity"], scope)
        result.append({"record_id": row["record_id"], "assigned_role": assignment["role"],
            "component_id": assignment["component_id"], "predicted": values.get(row["record_id"]),
            "mean_baseline": payload["mean_baseline"], "prediction_quantity": payload["prediction_quantity"],
            "status": "abstained" if issues else "predicted", "reason": issues, "observed_label_included": False})
    return result


def validate_frozen(path, expected_sha, manifest_sha, manifest, plan, selected):
    """Reproduce all predictions from metadata before evaluation label decoding."""
    frozen = bound.bound_json({"path": str(path), "sha256": expected_sha})
    if (frozen.get("schema_version") != FROZEN_SCHEMA or frozen.get("training_executed") is not True
            or frozen.get("evaluation_values_read") != 0 or frozen.get("manifest_sha256") != manifest_sha
            or frozen.get("split_plan_sha256") != manifest["split_plan"]["sha256"]
            or frozen.get("implementation_hashes") != implementation_hashes()):
        raise ValueError("incompatible_frozen_bindingdb_fit")
    protocol = bound.bound_json(frozen["protocol"])
    checkpoint = model_payload(frozen["checkpoint"]["path"], frozen["checkpoint"]["sha256"],
                               manifest["scope"]["target_annotation_sha256"], manifest["scope"]["endpoint"])
    if (protocol.get("assignments") != plan["assignments"] or protocol.get("manifest_sha256") != manifest_sha
            or checkpoint.get("training_protocol_sha256") != frozen["protocol"]["sha256"]
            or checkpoint.get("manifest_sha256") != manifest_sha or checkpoint.get("split_plan_sha256") != manifest["split_plan"]["sha256"]):
        raise ValueError("frozen_checkpoint_protocol_binding_mismatch")
    expected = metadata_predictions(frozen["checkpoint"]["path"], frozen["checkpoint"]["sha256"], selected, manifest, plan)
    saved = bound.bound_jsonl(frozen["predictions"])
    indexed = bound.unique_index(saved, "record_id")
    if set(indexed) != {row["record_id"] for row in expected}:
        raise ValueError("frozen_prediction_coverage_mismatch")
    for row in expected:
        actual = indexed[row["record_id"]]
        if set(actual) != set(row):
            raise ValueError("unexpected_frozen_prediction_field")
        for key, value in row.items():
            if key == "predicted" and value is not None:
                if type(actual[key]) not in (int, float) or not np.isclose(actual[key], value, rtol=1e-12, atol=1e-12):
                    raise ValueError("frozen_prediction_checkpoint_mismatch")
            elif actual[key] != value:
                raise ValueError("frozen_prediction_role_or_value_mismatch")
    return frozen, indexed


def fit(*, input_dir, summary_sha256, output_dir):
    output = Path(output_dir)
    if output.exists():
        raise ValueError("output_already_exists")
    wall, cpu = time.perf_counter(), time.process_time()
    before = implementation_hashes()
    summary, loaded, records = intake.load_intake(input_dir, summary_sha256, "fit")
    manifest, plan, scope, metadata, selected_metadata, _, _, _ = loaded
    selected = [row for row in records if row["assigned_role"] == "fit" and row["eligible_for_point_model"]]
    if len(selected) < 5 or len({row["component_id"] for row in selected}) < 2:
        raise ValueError("insufficient_supported_fit_rows_or_components")
    if any(row["native_bindingdb_row"] is not None for row in records if row["assigned_role"] != "fit"):
        raise ValueError("evaluation_outcome_in_fit_input")
    observed = np.asarray([row["observation"]["negative_log10_molar"] for row in selected], dtype=np.float64)
    if not np.isfinite(observed).all():
        raise ValueError("nonfinite_supported_fit_observation")
    protocol = {"schema_version": MODEL_SCHEMA, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_path": summary["manifest_path"], "manifest_sha256": summary["manifest_sha256"],
        "input_summary_sha256": summary_sha256, "split_plan_sha256": manifest["split_plan"]["sha256"],
        "implementation_hashes": before, "assignments": plan["assignments"], "fit_record_ids": [r["record_id"] for r in selected],
        "target_annotation": scope["target_annotation"], "target_annotation_sha256": scope["target_annotation_sha256"],
        "endpoint": scope["endpoint"], "prediction_quantity": "negative_log10_molar_" + scope["endpoint"],
        "features": FEATURES, "ridge_alpha": 10.0, "resplit_after_exclusions": False,
        "fit_replicate_weighting": "inverse_count_per_source_assay_chemical_state_and_reported_conditions",
        "positive_threshold_negative_log10_molar": 6.0, "top_fraction": 0.2, "hyperparameter_search": False,
        "calibration_role_use": "diagnostic only", "physical_target_state_verified": False,
        "scientific_validation": False, "customer_execution": False}
    output.mkdir(parents=True)
    protocol_path = output / "protocol-before-fit.json"
    protocol_path.write_text(common.json_text(protocol) + "\n")
    start = time.perf_counter()
    matrix = existing.features([row["chemical_identity"]["canonical_isomeric_smiles"] for row in selected])
    feature_seconds = time.perf_counter() - start
    keys = [(row["assays"][0]["entry_assay_id"], row["chemical_identity"]["canonical_isomeric_smiles_sha256"],
             common.json_text(row["normalized_native"]["assay_conditions"])) for row in selected]
    repetitions = Counter(keys)
    weights = np.asarray([1.0 / repetitions[key] for key in keys])
    start = time.perf_counter()
    model = Ridge(alpha=10.0, solver="cholesky").fit(matrix, observed, sample_weight=weights)
    fit_seconds = time.perf_counter() - start
    checkpoint = {"schema_version": MODEL_SCHEMA, "implementation_hashes": before, "features": FEATURES,
        "rdkit_version": rdBase.rdkitVersion, "target_annotation_sha256": scope["target_annotation_sha256"],
        "endpoint": scope["endpoint"], "prediction_quantity": "negative_log10_molar_" + scope["endpoint"],
        "coefficients": model.coef_.tolist(), "intercept": float(model.intercept_),
        "mean_baseline": float(np.average(observed, weights=weights)), "training_protocol_sha256": common.file_sha(protocol_path),
        "manifest_sha256": summary["manifest_sha256"], "split_plan_sha256": manifest["split_plan"]["sha256"],
        "uncertainty_calibrated": False, "uncertainty": None, "ood_status": "not_assessed",
        "product_ranking_enabled": False, "customer_execution": False, "physical_energy": False}
    checkpoint_path = output / "selector.json"
    checkpoint_path.write_text(common.json_text(checkpoint) + "\n")
    checkpoint_sha = common.file_sha(checkpoint_path)
    if not np.allclose(predict_checkpoint(checkpoint_path, checkpoint_sha,
                       [r["chemical_identity"]["canonical_isomeric_smiles"] for r in selected],
                       scope["target_annotation_sha256"], scope["endpoint"]), model.predict(matrix), rtol=1e-12, atol=1e-12):
        raise ValueError("serialized_fit_prediction_mismatch")
    start = time.perf_counter()
    predictions = metadata_predictions(checkpoint_path, checkpoint_sha, selected_metadata, manifest, plan)
    prediction_seconds = time.perf_counter() - start
    prediction_path = output / "predictions-before-evaluation-labels.jsonl"
    prediction_path.write_text("".join(common.json_text(row) + "\n" for row in predictions))
    frozen = {"schema_version": FROZEN_SCHEMA, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "training_executed": True, "evaluation_values_read": 0, "manifest_sha256": summary["manifest_sha256"],
        "split_plan_sha256": manifest["split_plan"]["sha256"], "implementation_hashes": before,
        "checkpoint": {"path": str(checkpoint_path.resolve()), "sha256": checkpoint_sha},
        "protocol": {"path": str(protocol_path.resolve()), "sha256": common.file_sha(protocol_path)},
        "predictions": {"path": str(prediction_path.resolve()), "sha256": common.file_sha(prediction_path)}}
    if implementation_hashes() != before:
        raise ValueError("implementation_changed_during_fit")
    frozen_path = output / "frozen-fit.json"
    frozen_path.write_text(common.json_text(frozen) + "\n")
    result = {**protocol, "training_executed": True, "checkpoint_sha256": checkpoint_sha,
        "frozen_fit_sha256": common.file_sha(frozen_path), "fit_requested": plan["counts"]["fit"],
        "fit_used": len(selected), "fit_excluded": plan["counts"]["fit"] - len(selected),
        "fit_components": len({r["component_id"] for r in selected}), "requested_target_rows": len(metadata),
        "metadata_selected_rows": len(records), "evaluation_label_rows_unread": plan["counts"]["calibration"] + plan["counts"]["development_test"],
        "prediction_rows": len(predictions), "prediction_abstentions": sum(r["predicted"] is None for r in predictions),
        "quality_measured": False, "docking_recall_measured": False, "engine_speedup_measured": False,
        "cost": {"wall_seconds": time.perf_counter() - wall, "cpu_seconds": time.process_time() - cpu,
                 "feature_seconds": feature_seconds, "fit_seconds": fit_seconds, "frozen_prediction_seconds": prediction_seconds,
                 "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 "scope": "offline source revalidation, CPU fit and frozen predictions; excludes acquisition and original intake"}}
    (output / "fit-summary.json").write_text(common.json_text(result) + "\n")
    return result


def evaluate(*, input_dir, summary_sha256, output_dir):
    output = Path(output_dir)
    if output.exists():
        raise ValueError("output_already_exists")
    wall, cpu = time.perf_counter(), time.process_time()
    before = implementation_hashes()
    # load_intake reproduces frozen predictions BEFORE it decodes native evaluation labels.
    summary, loaded, records = intake.load_intake(input_dir, summary_sha256, "evaluation")
    manifest, plan, scope, metadata, selected, _, _, _ = loaded
    frozen_ref = summary["frozen_fit"]
    frozen, predictions = validate_frozen(frozen_ref["path"], frozen_ref["sha256"], summary["manifest_sha256"], manifest, plan, selected)
    evaluations, ledger = {}, []
    for role in ("calibration", "development_test"):
        requested = [row for row in records if row["assigned_role"] == role]
        supported = [row for row in requested if row["eligible_for_point_model"]]
        actual = np.asarray([row["observation"]["negative_log10_molar"] for row in supported], dtype=np.float64)
        predicted = np.asarray([np.nan if predictions[row["record_id"]]["predicted"] is None else predictions[row["record_id"]]["predicted"] for row in supported])
        baseline = np.asarray([predictions[row["record_id"]]["mean_baseline"] for row in supported])
        entry = {"requested_preassigned_rows": len(requested), "exact_supported_rows": len(supported),
            "unsupported_or_failed_labels": len(requested) - len(supported),
            "supported_label_coverage": len(supported) / len(requested) if requested else None,
            "observation_status_counts": dict(Counter(r["observation"]["status"] for r in requested)),
            "exclusion_counts": dict(Counter(issue for r in requested for issue in r["admission_issues"])),
            "full_requested_recall": None, "full_requested_recall_reason": "missing_censored_invalid_or_unknown_method_not_assumed_negative"}
        if supported:
            entry.update(mean_baseline=existing.metrics(actual, baseline, 6.0), morgan_ridge=existing.metrics(actual, predicted, 6.0),
                         unique_state_mean_baseline=existing.unique_state_metrics(supported, actual, baseline, 6.0),
                         unique_state_morgan_ridge=existing.unique_state_metrics(supported, actual, predicted, 6.0))
        else:
            entry.update(mean_baseline=None, morgan_ridge=None, unique_state_mean_baseline=None, unique_state_morgan_ridge=None)
        evaluations[role] = entry
        ledger.extend({"record_id": row["record_id"], "role": role, "component_id": row["component_id"],
                       "eligible_for_point_model": row["eligible_for_point_model"], "issues": row["admission_issues"],
                       "observation": row["observation"], "frozen_prediction": predictions[row["record_id"]]} for row in requested)
    if implementation_hashes() != before:
        raise ValueError("implementation_changed_during_evaluation")
    output.mkdir(parents=True)
    (output / "evaluation-ledger.jsonl").write_text("".join(common.json_text(row) + "\n" for row in ledger))
    result = {"schema_version": "public_bindingdb_frozen_evaluation_v1", "manifest_sha256": summary["manifest_sha256"],
        "split_plan_sha256": manifest["split_plan"]["sha256"], "frozen_fit_sha256": frozen_ref["sha256"],
        "implementation_hashes": before, "requested_target_rows": len(metadata), "metadata_selected_rows": len(selected),
        "metadata_not_selected_rows": len(metadata) - len(selected), "evaluations": evaluations,
        "endpoint": scope["endpoint"], "prediction_quantity": "negative_log10_molar_" + scope["endpoint"],
        "full_requested_recall": None, "uncertainty_calibrated": False, "calibration_role_use": "diagnostic only",
        "hyperparameter_search": False, "resplit_after_exclusions": False, "product_ranking_enabled": False,
        "scientific_validation": False, "customer_execution": False, "docking_recall_measured": False, "engine_speedup_measured": False,
        "cost": {"wall_seconds": time.perf_counter() - wall, "cpu_seconds": time.process_time() - cpu,
                 "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 "scope": "offline source revalidation and frozen prediction evaluation; excludes acquisition, intake and fit"}}
    (output / "summary.json").write_text(common.json_text(result) + "\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("fit", "evaluation"), required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--summary-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    function = fit if args.phase == "fit" else evaluate
    result = function(input_dir=args.input_dir, summary_sha256=args.summary_sha256, output_dir=args.output_dir)
    print(json.dumps({key:result[key] for key in ("requested_target_rows", "metadata_selected_rows") if key in result}))


if __name__ == "__main__":
    main()
