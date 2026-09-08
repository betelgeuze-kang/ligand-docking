"""Fit-only ChEMBL cheap selector; freeze predictions before evaluation labels.

Uses the existing Morgan featurizer and fixed Ridge baseline. This is not an
interaction residual, a potential-energy model, or a customer ranking route.
"""
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
from tools.product import public_chembl_assay_dataset as intake
from tools.product import train_public_assay_selector as existing

MODEL_SCHEMA = "public_chembl_cheap_selector_ridge_v1"
FEATURES = {**existing.FEATURES, "target_encoding": "one_catalogue_target_annotation_per_model_not_physical_state"}


def load_intake(input_dir, summary_sha256, phase):
    """Reproduce every normalized row from the bound native capture, not cache flags."""
    summary = intake.bound_json({"path": str(input_dir / "summary.json"), "sha256": summary_sha256})
    if (summary.get("schema_version") != intake.SCHEMA or summary.get("phase") != phase
            or summary.get("implementation_hashes") != intake.implementation_hashes()):
        raise ValueError("fit_intake_schema_or_implementation_mismatch")
    rows = intake.bound_jsonl({"path": str(input_dir / "records.jsonl"), "sha256": summary["records_sha256"]})
    manifest, plan, scope, indexed, context, graph = intake.load_metadata(
        summary["manifest_path"], summary["manifest_sha256"])
    _, values, origins = intake.read_captures(summary["capture_manifest_path"], summary["capture_manifest_sha256"],
                                            manifest, plan, scope, indexed, phase)
    expected_rows, expected_ledger, expected_context = intake.derive_outputs(plan, scope, indexed, context, graph, values, origins)
    ledger = intake.bound_jsonl({"path": str(input_dir / "ledger.jsonl"), "sha256": summary["ledger_sha256"]})
    saved_context = intake.bound_jsonl({"path": str(input_dir / "identity-context.jsonl"), "sha256": summary["identity_context_sha256"]})
    if ledger != expected_ledger or saved_context != expected_context:
        raise ValueError("intake_ledger_or_role_context_does_not_match_native_source")
    for key, value in {
        "split_plan_sha256": manifest["split_plan"]["sha256"], "intake_scope_sha256": manifest["intake_scope"]["sha256"],
        "requested_metadata_rows": len(indexed), "metadata_selected_rows": len(expected_rows),
        "identity_context_nodes": len(context), "observations_retrieved": len(values),
        "labels_withheld": len(expected_rows) - len(values),
        "point_eligible_rows": sum(row["eligible_for_point_model"] for row in expected_rows),
        "assigned_role_counts": plan["counts"],
        "ledger_counts": dict(Counter(row["status"] for row in expected_ledger)),
        "exclusion_counts": dict(Counter(issue for row in expected_rows for issue in row["admission_issues"])),
        "eligible_role_counts": dict(Counter(row["assigned_role"] for row in expected_rows if row["eligible_for_point_model"])),
    }.items():
        if summary.get(key) != value:
            raise ValueError("intake_summary_does_not_match_native_source:" + key)
    assignments = intake.unique_index(plan["assignments"], "activity_id")
    cached = intake.unique_index(rows, "activity_id")
    if set(cached) != set(assignments):
        raise ValueError("fit_intake_assignment_coverage_mismatch")
    for aid, assignment in assignments.items():
        expected = intake.normalized_record(indexed[aid], assignment, scope,
                                             graph[indexed[aid]["identity_context_node_id"]], values.get(aid), origins.get(aid))
        if cached[aid] != expected:
            raise ValueError("fit_intake_cache_does_not_match_native_source")
        if (assignment["role"] == "fit") != (phase == "fit") and cached[aid]["native_activity"] is not None:
            raise ValueError("wrong_role_outcome_in_phase_input")
    return summary, plan, scope, [cached[aid] for aid in sorted(cached)]


def implementation_hashes():
    return {**intake.implementation_hashes(),
            "trainer": common.file_sha(Path(__file__)),
            "reused_featurizer_and_metrics": common.file_sha(Path(existing.__file__))}


def predict_checkpoint(path, expected_sha, smiles, target_annotation_sha256):
    payload = intake.bound_json({"path": str(path), "sha256": expected_sha})
    if (payload.get("schema_version") != MODEL_SCHEMA or payload.get("features") != FEATURES
            or payload.get("rdkit_version") != rdBase.rdkitVersion
            or payload.get("target_annotation_sha256") != target_annotation_sha256
            or payload.get("implementation_hashes") != implementation_hashes()
            or payload.get("prediction_quantity") != "negative_log10_molar_IC50"
            or payload.get("product_ranking_enabled") is not False
            or payload.get("uncertainty_calibrated") is not False):
        raise ValueError("incompatible_chembl_selector_checkpoint")
    weights = np.asarray(payload["coefficients"], dtype=np.float64)
    intercept = payload["intercept"]
    if (weights.shape != (1024,) or not np.isfinite(weights).all()
            or type(intercept) not in (int, float) or not np.isfinite(intercept)):
        raise ValueError("invalid_chembl_selector_weights")
    return existing.features(smiles) @ weights + intercept


def fit(*, input_dir, summary_sha256, output_dir):
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    if output_dir.exists():
        raise ValueError("output_already_exists")
    wall, cpu = time.perf_counter(), time.process_time()
    source_implementations = implementation_hashes()
    summary, plan, scope, rows = load_intake(input_dir, summary_sha256, "fit")
    selected = [row for row in rows if row["assigned_role"] == "fit" and row["eligible_for_point_model"]]
    if len(selected) < 5 or len({row["component_id"] for row in selected}) < 2:
        raise ValueError("insufficient_supported_fit_rows_or_components")
    target_ids = {row["target_annotation_sha256"] for row in rows}
    if len(target_ids) != 1:
        raise ValueError("mixed_target_annotation_scope")
    target = next(iter(target_ids))
    if scope["positive_threshold_negative_log10_molar"] != 6.0 or scope["top_fraction"] != 0.2:
        raise ValueError("unsupported_predeclared_metric_protocol")
    protocol = {
        "schema_version": MODEL_SCHEMA, "declared_at_utc": datetime.now(timezone.utc).isoformat(),
        "intake_summary_sha256": summary_sha256, "input_dir": str(input_dir),
        "split_plan_sha256": summary["split_plan_sha256"], "intake_scope_sha256": summary["intake_scope_sha256"],
        "implementation_hashes": implementation_hashes(), "target_annotation_sha256": target,
        "target_annotation": rows[0]["target_annotation"], "features": FEATURES,
        "prediction_quantity": "negative_log10_molar_IC50", "ridge_alpha": 10.0,
        "seed": plan["seed"], "hyperparameter_search": False,
        "fit_record_ids": [row["record_id"] for row in selected],
        "assignments": plan["assignments"], "resplit_after_exclusions": False,
        "positive_threshold_negative_log10_molar": 6.0, "top_fraction": 0.2,
        "fit_replicate_weighting": "inverse_count_per_source_assay_and_canonical_isomeric_structure",
        "prediction_scope": "database standardized structures; mixed reported kinase assay conditions; catalogue target admission only",
        "uncertainty_calibration_planned": False,
        "calibration_role_use": "reserved diagnostic evaluation only; no calibrated uncertainty claim",
        "scientific_validation": False, "customer_execution": False,
    }
    output_dir.mkdir(parents=True)
    protocol_path = output_dir / "protocol-before-fit.json"
    protocol_path.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n")
    feature_start = time.perf_counter()
    matrix = existing.features([row["chemical_identity"]["canonical_isomeric_smiles"] for row in selected])
    feature_seconds = time.perf_counter() - feature_start
    observed = np.asarray([row["observation"]["negative_log10_molar"] for row in selected], dtype=np.float64)
    if not np.isfinite(observed).all():
        raise ValueError("nonfinite_supported_fit_label")
    keys = [(row["assay_id"], row["chemical_identity"]["canonical_isomeric_smiles_sha256"]) for row in selected]
    repetitions = Counter(keys)
    weights = np.asarray([1.0 / repetitions[key] for key in keys])
    start = time.perf_counter()
    model = Ridge(alpha=10.0, solver="cholesky").fit(matrix, observed, sample_weight=weights)
    fit_seconds = time.perf_counter() - start
    mean = float(np.average(observed, weights=weights))
    checkpoint = {
        "schema_version": MODEL_SCHEMA, "features": FEATURES, "rdkit_version": rdBase.rdkitVersion,
        "implementation_hashes": implementation_hashes(), "target_annotation_sha256": target,
        "endpoint": "IC50", "endpoint_subtype": "enzyme_inhibition_IC50",
        "prediction_quantity": "negative_log10_molar_IC50", "physical_energy": False,
        "coefficients": model.coef_.tolist(), "intercept": float(model.intercept_),
        "training_protocol_sha256": common.file_sha(protocol_path),
        "split_plan_sha256": summary["split_plan_sha256"], "intake_scope_sha256": summary["intake_scope_sha256"],
        "identity_context_sha256": summary["identity_context_sha256"],
        "mean_baseline": mean, "uncertainty_calibrated": False, "uncertainty": None,
        "ood_status": "not_assessed", "product_ranking_enabled": False, "customer_execution": False,
    }
    checkpoint_path = output_dir / "selector.json"
    checkpoint_path.write_text(common.json_text(checkpoint) + "\n")
    checkpoint_sha = common.file_sha(checkpoint_path)
    predictions = []
    start = time.perf_counter()
    for row in rows:
        # Point-label eligibility is never used to select evaluation predictions.
        chemical_failures = [issue for issue in row["admission_issues"] if issue.startswith("chemical_")]
        prediction = None
        if not chemical_failures:
            smiles = [row["chemical_identity"]["canonical_isomeric_smiles"]]
            value = predict_checkpoint(checkpoint_path, checkpoint_sha, smiles, target)
            expected = model.predict(existing.features(smiles))
            if not np.allclose(value, expected, atol=1e-12, rtol=1e-12):
                raise ValueError("serialized_chembl_prediction_mismatch")
            prediction = float(value[0])
        predictions.append({"record_id": row["record_id"], "activity_id": row["activity_id"],
                            "assigned_role": row["assigned_role"], "component_id": row["component_id"],
                            "predicted": prediction, "mean_baseline": mean,
                            "prediction_quantity": "negative_log10_molar_IC50",
                            "status": "abstained" if chemical_failures else "predicted",
                            "reason": chemical_failures, "observed_label_included": False})
    prediction_seconds = time.perf_counter() - start
    prediction_path = output_dir / "predictions-before-evaluation-labels.jsonl"
    prediction_path.write_text("".join(common.json_text(row) + "\n" for row in predictions))
    frozen = {
        "schema_version": "public_chembl_fit_frozen_before_evaluation_v1",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(), "training_executed": True,
        "split_plan_sha256": summary["split_plan_sha256"], "intake_scope_sha256": summary["intake_scope_sha256"],
        "checkpoint": {"path": str(checkpoint_path), "sha256": checkpoint_sha},
        "protocol": {"path": str(protocol_path), "sha256": common.file_sha(protocol_path)},
        "predictions": {"path": str(prediction_path), "sha256": common.file_sha(prediction_path)},
        "implementation_hashes": implementation_hashes(), "evaluation_values_read": 0,
    }
    if implementation_hashes() != source_implementations:
        raise ValueError("implementation_changed_during_fit")
    freeze_path = output_dir / "frozen-fit.json"
    freeze_path.write_text(json.dumps(frozen, sort_keys=True, indent=2) + "\n")
    report = {
        **protocol, "training_executed": True, "checkpoint_sha256": checkpoint_sha,
        "frozen_fit_sha256": common.file_sha(freeze_path), "fit_requested": plan["counts"]["fit"],
        "fit_used": len(selected), "fit_excluded": plan["counts"]["fit"] - len(selected),
        "fit_components": len({row["component_id"] for row in selected}), "fit_effective_group_weight": float(weights.sum()),
        "requested_metadata_rows": summary["requested_metadata_rows"], "metadata_selected_rows": len(rows),
        "predicted_candidate_rows": sum(row["predicted"] is not None for row in predictions),
        "prediction_abstentions": sum(row["predicted"] is None for row in predictions),
        "evaluation_label_rows_unread": plan["counts"]["calibration"] + plan["counts"]["development_test"],
        "quality_measured": False, "docking_recall_measured": False, "engine_speedup_measured": False,
        "cost": {"feature_seconds": feature_seconds, "fit_seconds": fit_seconds,
                 "serialized_individual_prediction_parity_seconds": prediction_seconds,
                 "wall_seconds": time.perf_counter() - wall, "cpu_seconds": time.process_time() - cpu,
                 "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 "scope": "single CPU fit with complete source verification and individual prediction parity; excludes network/intake"},
    }
    (output_dir / "fit-summary.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return report


def evaluate(*, input_dir, summary_sha256, frozen_fit_path, frozen_fit_sha256, output_dir):
    """Read declared evaluation labels only after an already frozen prediction set."""
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    if output_dir.exists():
        raise ValueError("output_already_exists")
    wall, cpu = time.perf_counter(), time.process_time()
    source_implementations = implementation_hashes()
    summary, plan, scope, rows = load_intake(input_dir, summary_sha256, "evaluation")
    frozen = intake.bound_json({"path": str(frozen_fit_path), "sha256": frozen_fit_sha256})
    capture = intake.bound_json({"path": summary["capture_manifest_path"], "sha256": summary["capture_manifest_sha256"]})
    if (capture["frozen_fit"]["sha256"] != frozen_fit_sha256
            or frozen["implementation_hashes"] != implementation_hashes()
            or frozen["split_plan_sha256"] != summary["split_plan_sha256"]):
        raise ValueError("frozen_fit_evaluation_binding_mismatch")
    predictions = intake.unique_index(intake.bound_jsonl(frozen["predictions"]), "activity_id")
    evaluations, ledger = {}, []
    for role in ("calibration", "development_test"):
        requested = [row for row in rows if row["assigned_role"] == role]
        supported = [row for row in requested if row["eligible_for_point_model"]]
        actual, predicted, baseline = [], [], []
        for row in requested:
            prediction = predictions[row["activity_id"]]
            # Saved checkpoint inference is checked independently of observed labels.
            if prediction["predicted"] is not None:
                recomputed = predict_checkpoint(Path(frozen["checkpoint"]["path"]), frozen["checkpoint"]["sha256"],
                                                [row["chemical_identity"]["canonical_isomeric_smiles"]], row["target_annotation_sha256"])
                if not np.isclose(recomputed[0], prediction["predicted"], rtol=1e-12, atol=1e-12):
                    raise ValueError("frozen_prediction_checkpoint_mismatch")
            ledger.append({"activity_id": row["activity_id"], "record_id": row["record_id"], "role": role,
                           "component_id": row["component_id"], "eligible_exact_observation": row["eligible_for_point_model"],
                           "issues": row["admission_issues"], "observation": row["observation"],
                           "frozen_prediction": prediction})
            if row["eligible_for_point_model"]:
                actual.append(row["observation"]["negative_log10_molar"])
                predicted.append(np.nan if prediction["predicted"] is None else prediction["predicted"])
                baseline.append(prediction["mean_baseline"])
        y, pred, mean = map(lambda values: np.asarray(values, dtype=np.float64), (actual, predicted, baseline))
        result = {
            "requested_preassigned_rows": len(requested), "exact_supported_rows": len(supported),
            "unsupported_or_failed_labels": len(requested) - len(supported),
            "supported_label_coverage": len(supported) / len(requested) if requested else None,
            "requested_components": len({row["component_id"] for row in requested}),
            "supported_components": len({row["component_id"] for row in supported}),
            "exclusion_counts": dict(Counter(issue for row in requested for issue in row["admission_issues"])),
            "full_requested_recall": None,
            "full_requested_recall_reason": "unsupported_missing_censored_labels_not_assumed_negative",
            "observed_metrics_scope": "exact supported reported enzyme IC50; excludes unsupported labels from numeric quality only",
        }
        if supported:
            result.update(mean_baseline=existing.metrics(y, mean, 6.0), morgan_ridge=existing.metrics(y, pred, 6.0),
                          unique_state_mean_baseline=existing.unique_state_metrics(supported, y, mean, 6.0),
                          unique_state_morgan_ridge=existing.unique_state_metrics(supported, y, pred, 6.0))
        else:
            result.update(mean_baseline=None, morgan_ridge=None,
                          unique_state_mean_baseline=None, unique_state_morgan_ridge=None)
        evaluations[role] = result
    if implementation_hashes() != source_implementations:
        raise ValueError("implementation_changed_during_evaluation")
    output_dir.mkdir(parents=True)
    (output_dir / "evaluation-ledger.jsonl").write_text("".join(common.json_text(row) + "\n" for row in ledger))
    report = {
        "schema_version": "public_chembl_frozen_selector_evaluation_v1", "frozen_fit_sha256": frozen_fit_sha256,
        "input_summary_sha256": summary_sha256, "implementation_hashes": implementation_hashes(),
        "requested_metadata_rows": summary["requested_metadata_rows"], "metadata_selected_rows": len(rows),
        "split_plan_sha256": summary["split_plan_sha256"], "intake_scope_sha256": summary["intake_scope_sha256"],
        "evaluations": evaluations, "full_requested_recall": None,
        "hyperparameter_search": False, "resplit_after_exclusions": False,
        "uncertainty_calibrated": False, "product_ranking_enabled": False,
        "docking_recall_measured": False, "engine_speedup_measured": False,
        "scientific_validation": False, "customer_execution": False,
        "cost": {"wall_seconds": time.perf_counter() - wall, "cpu_seconds": time.process_time() - cpu,
                 "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 "scope": "single CPU evaluation including source verification and serialized prediction parity; excludes acquisition/intake/fit"},
    }
    (output_dir / "summary.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--phase", choices=("fit", "evaluation"), default="fit")
    parser.add_argument("--summary-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--frozen-fit", type=Path)
    parser.add_argument("--frozen-fit-sha256")
    args = parser.parse_args(argv)
    if args.phase == "fit":
        if args.frozen_fit is not None or args.frozen_fit_sha256 is not None:
            raise ValueError("frozen_fit_not_an_input_to_fit")
        report = fit(input_dir=args.input_dir, summary_sha256=args.summary_sha256, output_dir=args.output_dir)
    else:
        if args.frozen_fit is None or args.frozen_fit_sha256 is None:
            raise ValueError("frozen_fit_required_for_evaluation")
        report = evaluate(input_dir=args.input_dir, summary_sha256=args.summary_sha256,
                          frozen_fit_path=args.frozen_fit, frozen_fit_sha256=args.frozen_fit_sha256, output_dir=args.output_dir)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
