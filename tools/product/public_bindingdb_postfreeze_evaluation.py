"""Review BindingDB evaluation methods after freezing, without rewriting the fit.

The original manifest/checkpoint/producer remain immutable. This separately
versioned adapter binds method captures and internal review to that original fit.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import time

import numpy as np

from tools.product import public_assay_components as components
from tools.product import public_assay_dataset as common
from tools.product import public_bindingdb_staged_intake as intake
from tools.product import public_chembl_assay_dataset as bound
from tools.product import residual_evidence
from tools.product import train_public_assay_selector as existing
from tools.product import train_public_bindingdb_staged_selector as trainer

CAPTURE_SCHEMA = "public_bindingdb_postfreeze_methods_v1"
REVIEW_SCHEMA = "public_bindingdb_postfreeze_method_review_v1"
EVALUATION_SCHEMA = "public_bindingdb_postfreeze_evaluation_v1"
ROLES = {"calibration", "development_test"}


def implementation_hashes():
    return {**trainer.implementation_hashes(),
            "postfreeze_adapter": common.file_sha(Path(__file__)),
            "source_policy": common.file_sha(Path(residual_evidence.__file__))}


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError
        return parsed
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_postfreeze_timestamp") from exc


def reference(path, sha256):
    return {"path": str(path), "sha256": sha256}


def load_frozen(manifest_ref, frozen_ref):
    loaded = intake.load_metadata(manifest_ref["path"], manifest_ref["sha256"])
    manifest, plan, _, _, selected, _, _, _ = loaded
    frozen, predictions = trainer.validate_frozen(frozen_ref["path"], frozen_ref["sha256"],
                                                  manifest_ref["sha256"], manifest, plan, selected)
    if timestamp(frozen["frozen_at_utc"]) > datetime.now(timezone.utc):
        raise ValueError("future_frozen_fit")
    return loaded, frozen, predictions


def recheck_sources(manifest_ref, frozen_ref, loaded, before):
    manifest = loaded[0]
    for key in ("archive", "normalized_metadata", "identity_context", "split_plan",
                "assay_mapping", "assay_descriptions", "assay_method_ledger"):
        intake.read_entry(manifest[key])
    bound.bound_json(manifest_ref)
    frozen = bound.bound_json(frozen_ref)
    for key in ("checkpoint", "protocol", "predictions"):
        intake.read_entry(frozen[key])
    if implementation_hashes() != before:
        raise ValueError("implementation_changed_during_postfreeze_operation")


def guard_assay_connections(loaded):
    """Verify shared native assay IDs before accessing any evaluation description.

    Metadata-only mapping scans include linked records outside the selected
    target. Unknown, reserved or previously separate components cannot silently
    become evaluation method sources. No new split is assigned here.
    """
    manifest, plan, _, _, _, context, graph, _ = loaded
    assignments = {row["record_id"]: row for row in plan["assignments"]}
    by_record = defaultdict(list)
    for node in context:
        by_record[node["record_id"]].append(graph[node["node_id"]])
    keys = defaultdict(set)
    role_keys = defaultdict(set)
    scans = 0
    for phase in ("selected_keys", "all_linked_records"):
        with intake.binary_table(manifest["assay_mapping"]) as (stream, _):
            header = stream.readline().decode("utf-8-sig").rstrip("\r\n").split("\t")
            if len(header) != len(set(header)) or not all(header):
                raise ValueError("invalid_mapping_header")
            rid_pos, key_pos = header.index("REACTANT_SET_ID"), header.index("ENTRYID_ASSAYID")
            policy_pos = {i for i, key in enumerate(header) if key.strip().casefold() in components.POLICY_FIELDS}
            for raw in stream:
                scans += 1
                tokens = intake.selected_byte_tokens(raw, {rid_pos, key_pos})
                rid, key = "bindingdb:" + tokens.get(rid_pos, "").strip(), tokens.get(key_pos, "")
                if phase == "selected_keys":
                    if rid in assignments:
                        if not key:
                            raise ValueError("missing_selected_assay_key")
                        role_keys[key].add(assignments[rid]["role"])
                        if assignments[rid]["role"] in ROLES:
                            keys[key].add(assignments[rid]["component_id"])
                    continue
                if key not in keys:
                    continue
                policies = intake.selected_byte_tokens(raw, policy_pos)
                if any(components.reservation_status([{header[i]: value for i, value in policies.items()}])):
                    raise ValueError("reserved_or_unknown_assay_mapping_policy")
                states = by_record.get(rid, [])
                if not states or any(state["blocked"] for state in states):
                    raise ValueError("unknown_or_reserved_assay_linked_record")
                if {state["component_id"] for state in states} != keys[key]:
                    raise ValueError("assay_link_changes_frozen_component")
        if phase == "selected_keys" and any(len(keys[key]) != 1 or len(role_keys[key]) != 1 for key in keys):
            raise ValueError("assay_link_crosses_frozen_roles_or_components")
    return {"mapping_metadata_rows_scanned": scans, "evaluation_assay_keys": sorted(keys),
            "shared_assay_component_guard": "verified_against_entire_bound_context"}


def method_sources(loaded):
    guard = guard_assay_connections(loaded)
    plan = loaded[1]
    ids = {row["record_id"] for row in plan["assignments"] if row["role"] in ROLES}
    assays, access = intake.phase_assays(loaded[0], ids, {row["record_id"] for row in plan["assignments"]})
    return {rid: assays.get(rid, []) for rid in sorted(ids)}, access, guard


def capture_methods(*, manifest_path, manifest_sha256, frozen_fit, frozen_fit_sha256, output_dir):
    output = Path(output_dir)
    if output.exists():
        raise ValueError("output_already_exists")
    wall, cpu = time.perf_counter(), time.process_time()
    before = implementation_hashes()
    manifest_ref, frozen_ref = reference(manifest_path, manifest_sha256), reference(frozen_fit, frozen_fit_sha256)
    loaded, frozen, _ = load_frozen(manifest_ref, frozen_ref)
    # Frozen checkpoint, assignments and every prediction validated first.
    assays, access, guard = method_sources(loaded)
    recheck_sources(manifest_ref, frozen_ref, loaded, before)
    output.mkdir(parents=True)
    body_path = output / "method-sources.json"
    body_path.write_text(common.json_text(assays) + "\n")
    result = {"schema_version": CAPTURE_SCHEMA, "manifest": manifest_ref, "frozen_fit": frozen_ref,
              "implementation_hashes": before, "captured_at_utc": datetime.now(timezone.utc).isoformat(),
              "original_frozen_at_utc": frozen["frozen_at_utc"], "methods": reference(body_path, common.file_sha(body_path)),
              "assay_access": access, "assay_connection_guard": guard,
              "evaluation_values_read": 0, "fit_changed": False,
              "cost": {"wall_seconds": time.perf_counter() - wall, "cpu_seconds": time.process_time() - cpu,
                       "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       "scope": "frozen/source verification and evaluation methods only; no numeric evaluation values"}}
    (output / "method-capture.json").write_text(common.json_text(result) + "\n")
    return result


def load_capture(capture_path, capture_sha256):
    # The manifest contains references only; the separate method body is not
    # opened or decoded until the original frozen checkpoint has been validated.
    capture_ref = reference(capture_path, capture_sha256)
    capture = bound.bound_json(capture_ref)
    if (set(capture) != {"schema_version", "manifest", "frozen_fit", "implementation_hashes", "captured_at_utc",
                         "original_frozen_at_utc", "methods", "assay_access", "assay_connection_guard",
                         "evaluation_values_read", "fit_changed", "cost"}
            or capture.get("schema_version") != CAPTURE_SCHEMA or capture.get("evaluation_values_read") != 0
            or capture.get("fit_changed") is not False or capture.get("implementation_hashes") != implementation_hashes()):
        raise ValueError("incompatible_postfreeze_method_capture")
    loaded, frozen, predictions = load_frozen(capture["manifest"], capture["frozen_fit"])
    if not timestamp(frozen["frozen_at_utc"]) <= timestamp(capture["captured_at_utc"]) <= datetime.now(timezone.utc):
        raise ValueError("method_capture_not_after_frozen_fit")
    if capture.get("original_frozen_at_utc") != frozen["frozen_at_utc"]:
        raise ValueError("method_capture_frozen_time_mismatch")
    assays, access, guard = method_sources(loaded)
    if (bound.bound_json(capture["methods"]) != assays or capture.get("assay_access") != access
            or capture.get("assay_connection_guard") != guard):
        raise ValueError("method_capture_does_not_match_native_sources")
    return capture_ref, capture, loaded, predictions, assays


def reviewed_methods(review_ref, capture_ref, capture, loaded, assays):
    review = bound.bound_json(review_ref)
    if (set(review) != {"schema_version", "capture", "reviewed_at_utc", "basis", "methods"}
            or review["schema_version"] != REVIEW_SCHEMA or review["capture"] != capture_ref
            or review["basis"] != "internal_development_method_review"):
        raise ValueError("incompatible_postfreeze_method_review")
    if not timestamp(capture["captured_at_utc"]) <= timestamp(review["reviewed_at_utc"]) <= datetime.now(timezone.utc):
        raise ValueError("method_review_not_after_capture")
    methods = bound.unique_index(review["methods"], "record_id")
    if set(methods) != set(assays):
        raise ValueError("evaluation_method_review_coverage_mismatch")
    for rid, method in methods.items():
        if (set(method) != {"record_id", "status", "reason", "assay_keys", "source_records"}
                or method["status"] not in {"compatible", "incompatible", "unknown", "ambiguous", "missing"}
                or not isinstance(method["reason"], str) or not method["reason"].strip()):
            raise ValueError("invalid_postfreeze_method_decision")
        expected_keys = [assay["entry_assay_id"] for assay in assays[rid]]
        sources = [{k: source[k] for k in ("source_sha256", "source_member", "source_line")}
                   for assay in assays[rid] for source in [assay["mapping_source"], *assay["description_records"]]]
        if (sorted(method["assay_keys"]) != sorted(expected_keys)
                or sorted(method["source_records"], key=common.json_text) != sorted(sources, key=common.json_text)):
            raise ValueError("review_method_native_source_binding_mismatch")
        if method["status"] == "compatible" and (not assays[rid] or any(not a["description_records"] for a in assays[rid])):
            raise ValueError("compatible_method_without_description_source")
    # Original fit decisions are immutable; only evaluation IDs receive overlays.
    return {**deepcopy(loaded[7]), **methods}


def metrics(records, predictions):
    evaluations, ledger = {}, []
    for role in ("calibration", "development_test"):
        requested = [row for row in records if row["assigned_role"] == role]
        supported = [row for row in requested if row["eligible_for_point_model"]]
        actual = np.asarray([row["observation"]["negative_log10_molar"] for row in supported], dtype=np.float64)
        predicted = np.asarray([np.nan if predictions[row["record_id"]]["predicted"] is None
                                else predictions[row["record_id"]]["predicted"] for row in supported])
        baseline = np.asarray([predictions[row["record_id"]]["mean_baseline"] for row in supported])
        entry = {"requested_preassigned_rows": len(requested), "exact_supported_rows": len(supported),
                 "unsupported_or_failed_labels": len(requested) - len(supported),
                 "supported_label_coverage": len(supported) / len(requested) if requested else None,
                 "supported_components": len({row["component_id"] for row in supported}),
                 "observation_status_counts": dict(Counter(row["observation"]["status"] for row in requested)),
                 "exclusion_counts": dict(Counter(issue for row in requested for issue in row["admission_issues"])),
                 "full_requested_recall": None,
                 "full_requested_recall_reason": "missing_censored_invalid_or_unknown_method_not_assumed_negative"}
        for name, scores in (("mean_baseline", baseline), ("morgan_ridge", predicted)):
            entry[name] = existing.metrics(actual, scores, 6.0) if supported else None
            entry["unique_state_" + name] = existing.unique_state_metrics(supported, actual, scores, 6.0) if supported else None
        evaluations[role] = entry
        ledger.extend({"record_id": row["record_id"], "role": role, "component_id": row["component_id"],
                       "eligible_for_point_model": row["eligible_for_point_model"], "issues": row["admission_issues"],
                       "observation": row["observation"], "method_evidence": row["method_evidence"],
                       "frozen_prediction": predictions[row["record_id"]]} for row in requested)
    return evaluations, ledger


def evaluate(*, capture_path, capture_sha256, review_path, review_sha256, output_dir):
    output = Path(output_dir)
    if output.exists():
        raise ValueError("output_already_exists")
    wall, cpu = time.perf_counter(), time.process_time()
    before = implementation_hashes()
    capture_ref, capture, loaded, predictions, assays = load_capture(capture_path, capture_sha256)
    review_ref = reference(review_path, review_sha256)
    methods = reviewed_methods(review_ref, capture_ref, capture, loaded, assays)
    manifest, plan, scope, metadata, selected, context, graph, original_methods = loaded
    # Only after full frozen/source/capture/review verification may values open.
    values, access = intake.native_rows(manifest, metadata, selected, plan, "evaluation", context)
    records, all_target_ledger, updated = intake.derive(manifest, plan, scope, metadata, selected,
                                                       context, graph, methods, assays, values)
    if any(methods[a["record_id"]] != original_methods[a["record_id"]] for a in plan["assignments"] if a["role"] == "fit"):
        raise ValueError("fit_method_changed_during_evaluation")
    evaluations, ledger = metrics(records, predictions)
    recheck_sources(capture["manifest"], capture["frozen_fit"], loaded, before)
    bound.bound_json(capture_ref)
    bound.bound_json(capture["methods"])
    bound.bound_json(review_ref)
    output.mkdir(parents=True)
    for name, rows in (("evaluation-ledger.jsonl", ledger), ("records.jsonl", records),
                       ("all-target-ledger.jsonl", all_target_ledger), ("identity-context.jsonl", updated)):
        (output / name).write_text("".join(common.json_text(row) + "\n" for row in rows))
    result = {"schema_version": EVALUATION_SCHEMA, "manifest": capture["manifest"], "frozen_fit": capture["frozen_fit"],
              "method_capture": capture_ref, "method_review": review_ref, "implementation_hashes": before,
              "requested_target_rows": len(metadata), "metadata_selected_rows": len(selected),
              "metadata_not_selected_rows": len(metadata) - len(selected), "evaluations": evaluations,
              "native_access": access, "endpoint": scope["endpoint"],
              "prediction_quantity": "negative_log10_molar_" + scope["endpoint"],
              "evidence_basis": "database_curated_reported_experiment",
              "primary_values_independently_verified": False, "full_requested_recall": None,
              "fit_changed": False, "training_executed": False, "resplit_after_exclusions": False,
              "hyperparameter_search": False, "uncertainty_calibrated": False, "calibration_role_use": "diagnostic only",
              "product_ranking_enabled": False, "customer_execution": False, "scientific_validation": False,
              "physical_target_state_verified": False, "docking_recall_measured": False, "engine_speedup_measured": False,
              "cost": {"wall_seconds": time.perf_counter() - wall, "cpu_seconds": time.process_time() - cpu,
                       "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       "scope": "source/freeze/method revalidation, evaluation intake and metrics; excludes fit and acquisition"}}
    (output / "summary.json").write_text(common.json_text(result) + "\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="phase", required=True)
    capture = sub.add_parser("capture-methods")
    for name in ("manifest", "manifest-sha256", "frozen-fit", "frozen-fit-sha256"):
        capture.add_argument("--" + name, required=True)
    evaluation = sub.add_parser("evaluate")
    for name in ("capture", "capture-sha256", "review", "review-sha256"):
        evaluation.add_argument("--" + name, required=True)
    for child in (capture, evaluation):
        child.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    if args.phase == "capture-methods":
        result = capture_methods(manifest_path=args.manifest, manifest_sha256=args.manifest_sha256,
            frozen_fit=args.frozen_fit, frozen_fit_sha256=args.frozen_fit_sha256, output_dir=args.output_dir)
    else:
        result = evaluate(capture_path=args.capture, capture_sha256=args.capture_sha256,
            review_path=args.review, review_sha256=args.review_sha256, output_dir=args.output_dir)
    print(json.dumps({key: result[key] for key in ("schema_version", "evaluation_values_read", "evaluations") if key in result}))


if __name__ == "__main__":
    main()
