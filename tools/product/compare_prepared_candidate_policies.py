"""Offline, budgeted policy comparison on one frozen pool of supplied poses.

Four arms: fit-only Morgan/Tanimoto, source-order V2, Ridge-prioritized V2,
and similarity-prioritized V2. No new engine, assay/energy score addition, source
admission, docking search, or product model registration is performed here.
Evaluation labels have a separate post-freeze entry point.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import uuid

ARMS = ("similarity", "engine", "ai_engine", "similarity_engine")
SCHEMA = "prepared_candidate_comparison_protocol_v1"
ORDERED_SCHEMA = "prepared_candidate_comparison_protocol_v2"
D3_SCHEMA = "prepared_candidate_comparison_protocol_v3"
MAX_BYTES = 32 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read(path):
    from tools.product.public_assay_components import loads

    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("comparison_capacity_exceeded")
    return loads(raw.decode())


def bound(ref):
    if type(ref) is not dict or set(ref) != {"path", "sha256"}:
        raise ValueError("expected_bound_file")
    with Path(ref["path"]).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise ValueError("comparison_source_hash_mismatch")
    from tools.product.public_assay_components import loads

    return loads(raw.decode())


def file_ref(path):
    return {
        "path": str(path),
        "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
    }


def publish(path, value, *, deadline=None):
    """Publish a complete immutable JSON file; interrupted temporary files aren't rows."""
    path = Path(path)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex)
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(canonical(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        if deadline is not None and time.monotonic() >= deadline:
            return False
        os.link(temporary, path)  # exclusive, no replacement of prior evidence
        return True
    finally:
        temporary.unlink(missing_ok=True)


def _number(value, *, positive=False):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or (positive and value <= 0)
    ):
        raise ValueError("invalid_comparison_number")
    return float(value)


def _stop_child(child):
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # it exited between the timeout and termination
    child.wait()


def _validate_rows(rows):
    if type(rows) is not list or not 1 <= len(rows) <= 10000:
        raise ValueError("invalid_comparison_metadata_count")
    ids, groups = set(), {}
    for row in rows:
        if set(row) != {
            "record_id",
            "role",
            "component_id",
            "smiles",
            "fit_value",
            "assay_id",
        }:
            raise ValueError("unexpected_comparison_metadata_field")
        if any(
            type(row[k]) is not str or not row[k]
            for k in ("record_id", "component_id", "assay_id")
        ):
            raise ValueError("invalid_comparison_identity")
        if row["record_id"] in ids or row["role"] not in {
            "fit",
            "calibration",
            "development_test",
        }:
            raise ValueError("duplicate_identity_or_invalid_role")
        ids.add(row["record_id"])
        if row["component_id"] in groups and groups[row["component_id"]] != row["role"]:
            raise ValueError("cross_role_component_leakage")
        groups[row["component_id"]] = row["role"]
        if row["smiles"] is not None and (
            type(row["smiles"]) is not str or not row["smiles"]
        ):
            raise ValueError("invalid_comparison_smiles")
        if row["fit_value"] is not None:
            if row["role"] != "fit":
                raise ValueError("evaluation_label_before_freeze")
            _number(row["fit_value"])
    fit = [
        r
        for r in rows
        if r["role"] == "fit" and r["fit_value"] is not None and r["smiles"]
    ]
    if not fit or not any(r["role"] == "development_test" for r in rows):
        raise ValueError("missing_fit_or_candidate_pool")
    # Duplicate chemical identity cannot cross roles even in synthetic fixtures.
    from tools.product.public_assay_dataset import chemical_identity

    identity_roles = {}
    for row in rows:
        if row["smiles"]:
            identity = chemical_identity(row["smiles"])
            key = identity["canonical_isomeric_smiles"]
            if key in identity_roles and identity_roles[key] != row["role"]:
                raise ValueError("cross_role_chemical_identity_leakage")
            identity_roles[key] = row["role"]
            row["smiles"] = key
    return rows


def load_rows(source):
    """Native route reuses source-bound metadata preassignment before labels."""
    if source.get("kind") == "synthetic_constants":
        if set(source) != {"kind", "rows"}:
            raise ValueError("unexpected_synthetic_source_field")
        return _validate_rows(copy.deepcopy(source["rows"])), {
            "evidence_kind": "synthetic_constants"
        }
    if source.get("kind") != "chembl_fit_intake" or set(source) != {
        "kind",
        "input_dir",
        "summary_sha256",
    }:
        raise ValueError("unsupported_comparison_source")
    from tools.product.train_public_chembl_selector import load_intake

    summary, plan, scope, original = load_intake(
        Path(source["input_dir"]), source["summary_sha256"], "fit"
    )
    rows = []
    for row in original:
        if row["assigned_role"] != "fit" and (
            row["observation"] is not None or row["native_activity"] is not None
        ):
            raise ValueError("evaluation_label_before_freeze")
        identity = row["chemical_identity"]
        issues = row.get(
            "prediction_issues",
            [x for x in row["admission_issues"] if x.startswith("chemical_")],
        )
        rows.append(
            {
                "record_id": row["record_id"],
                "role": row["assigned_role"],
                "component_id": row["component_id"],
                "assay_id": row["assay_id"],
                "smiles": identity["canonical_isomeric_smiles"]
                if identity and not issues
                else None,
                "fit_value": row["observation"]["negative_log10_molar"]
                if row["assigned_role"] == "fit" and row["eligible_for_point_model"]
                else None,
            }
        )
    return _validate_rows(rows), {
        "evidence_kind": "source_bound_catalogue_development",
        "split_plan_sha256": summary["split_plan_sha256"],
        "intake_scope_sha256": summary["intake_scope_sha256"],
        "endpoint": scope["endpoint"],
        "primary_prepared_state_link_verified": False,
    }


def _execution_order(protocol):
    """Validate explicit v2 order; never infer an order from observed outcomes."""
    if protocol["schema_version"] == SCHEMA:
        return ARMS
    order = protocol.get("arm_order")
    if (type(order) is not list or len(order) != len(ARMS)
            or any(type(name) is not str for name in order) or set(order) != set(ARMS)
            or protocol.get("tie_policy") != "seeded_pool_order"
            or type(protocol.get("selection_seed")) is not int
            or not 0 <= protocol["selection_seed"] < 2**32):
        raise ValueError("invalid_prespecified_comparison_order")
    return tuple(order)


def _prediction_order(frozen, predictions):
    if frozen["protocol"]["schema_version"] == SCHEMA:
        return sorted(predictions, key=lambda rid: (-predictions[rid], rid))
    seed = frozen["protocol"]["selection_seed"]
    ordinal = {rid: index for index, rid in enumerate(frozen["pool"])}
    # Stable seeded permutation of ORIGINAL pool positions, not record IDs.
    # The pool, seed and arm order are all bound before labels are read.
    tie = {rid: sha({"seed": seed, "pool_index": index}) for rid, index in ordinal.items()}
    return sorted(predictions, key=lambda rid: (-predictions[rid], tie[rid], ordinal[rid]))


def freeze(protocol):
    started = time.perf_counter()
    fields = {
        "schema_version",
        "source",
        "requests",
        "budget_seconds_per_arm",
        "max_engine_calls_per_arm",
        "top_k",
    }
    if type(protocol) is not dict:
        raise ValueError("unsupported_comparison_protocol")
    version = protocol.get("schema_version")
    if version in {ORDERED_SCHEMA, D3_SCHEMA}:
        fields |= {"selection_seed", "tie_policy", "arm_order"}
    if version == D3_SCHEMA:
        fields.add("calculation")
        if protocol.get("calculation") != {"backend": "fixed_receptor_d3_v1", "score_quantity": "uncalibrated_scorer_v1_dimensionless_minimize"}:
            raise ValueError("explicit_D3_backend_and_score_quantity_required")
    if (version not in {SCHEMA, ORDERED_SCHEMA, D3_SCHEMA}
            or not fields <= set(protocol) <= fields | {"reuse_ai_from"}):
        raise ValueError("unsupported_comparison_protocol")
    _execution_order(protocol)
    budget = _number(protocol["budget_seconds_per_arm"], positive=True)
    if budget > 3600:
        raise ValueError("comparison_budget_exceeds_capacity")
    for key in ("max_engine_calls_per_arm", "top_k"):
        if type(protocol[key]) is not int or not 1 <= protocol[key] <= 10000:
            raise ValueError("invalid_comparison_count_budget")
    rows, provenance = load_rows(protocol["source"])
    pool = [r["record_id"] for r in rows if r["role"] == "development_test"]
    if type(protocol["requests"]) is not dict or set(protocol["requests"]) != set(pool):
        raise ValueError("candidate_request_denominator_mismatch")
    from betelgeuze_engine.product.prepared_pose_journal import (
        _input_binding,
        _runtime_binding,
    )
    import torch

    torch.set_num_threads(1)
    inputs, requests = {}, {}
    for rid, ref in protocol["requests"].items():
        request = None if ref is None else bound(ref)
        requests[rid] = request
        if version == D3_SCHEMA:
            from betelgeuze_product.cpu_refinement_v1_2 import policy_adapter
            inputs[rid] = None if request is None else policy_adapter.input_binding(request)
        else:
            if request is not None and request.get("schema_version") != "prepared_rigid_pose_cross_request_v1":
                raise ValueError("requires_existing_rigid_pose_request")
            inputs[rid] = None if request is None else _input_binding(request)
    runtime = _runtime_binding()
    root = Path(__file__).resolve().parents[2]
    runtime["comparison_tools"] = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((root / "tools/product").glob("*.py"))
    }
    result = {
        "protocol": copy.deepcopy(protocol),
        "rows": rows,
        "pool": pool,
        "requests": requests,
        "source_inputs": inputs,
        "runtime": runtime,
        "provenance": provenance,
        "scope": ("online_imports_features_fit_inference_matched_baseline_D3_refinement_rescoring_and_worker_io"
                  if version == D3_SCHEMA else "online_imports_validation_features_fit_inference_provided_pose_scoring_and_worker_io"),
        "upstream_acquisition_preparation_and_pose_generation_measured": False,
        "scientifically_validated": False,
        "product_ranking_enabled": False,
        "reused_ai_model": None,
    }
    if "reuse_ai_from" in protocol:
        prior = bound(protocol["reuse_ai_from"])
        prior_root = Path(protocol["reuse_ai_from"]["path"]).parent
        prior_envelope = read(prior_root / "frozen.json")
        previous = prior_envelope["payload"]
        if (
            sha(previous) != prior_envelope["sha256"]
            or prior["binding"] != prior_envelope["sha256"]
            or previous["protocol"]
            != {k: v for k, v in protocol.items() if k != "reuse_ai_from"}
            or any(
                previous[k] != result[k]
                for k in (
                    "rows",
                    "pool",
                    "requests",
                    "source_inputs",
                    "runtime",
                    "provenance",
                )
            )
        ):
            raise ValueError("reused_model_source_or_protocol_changed")
        complete = read(prior_root / "ai_engine/completion.json")
        if (
            complete["binding"] != prior["binding"]
            or complete["status"] != "complete"
            or _arm_summary(
                prior_root / "ai_engine", previous, prior["binding"], complete
            )
            != prior["arms"]["ai_engine"]
        ):
            raise ValueError("reused_model_completed_cold_arm_required")
        setup = prior["arms"]["ai_engine"]["worker_observations"]["priority.json"][
            "setup_cost"
        ]
        model = setup["model_reference"]
        payload = bound(model)
        if protocol["source"]["kind"] == "chembl_fit_intake":
            for key in ("checkpoint", "protocol"):
                bound(payload[key])
            if any(
                payload[key] != provenance[key]
                for key in ("split_plan_sha256", "intake_scope_sha256")
            ):
                raise ValueError("reused_native_model_scope_changed")
        elif payload.get("source_rows_sha256") != sha(rows):
            raise ValueError("reused_synthetic_model_fit_changed")
        result["reused_ai_model"] = {
            "reference": model,
            "cold_result": protocol["reuse_ai_from"],
            "cold_arm_cost": prior["arms"]["ai_engine"]["cost"],
            "cold_feature_fit_prediction_seconds": setup[
                "feature_fit_prediction_seconds"
            ],
        }
    if len(canonical(result).encode()) > MAX_BYTES:
        raise ValueError("frozen_comparison_capacity_exceeded")
    return result, time.perf_counter() - started


def _priority(frozen, arm, directory):
    rows, pool = frozen["rows"], frozen["pool"]
    candidates = {r["record_id"]: r for r in rows if r["record_id"] in pool}
    if arm == "engine":
        return pool, {}, {}
    tick = time.perf_counter()
    from tools.product.train_public_assay_selector import features
    import numpy as np

    selected = [
        r
        for r in rows
        if r["role"] == "fit" and r["fit_value"] is not None and r["smiles"]
    ]
    valid = [rid for rid in pool if candidates[rid]["smiles"]]
    predictions = {}
    model_reference = None
    reused = frozen["reused_ai_model"] if arm == "ai_engine" else None
    if reused:
        model_reference = reused["reference"]
        payload = bound(model_reference)
        if frozen["protocol"]["source"]["kind"] == "chembl_fit_intake":
            from tools.product.train_public_chembl_selector import predict_checkpoint

            training = bound(payload["protocol"])
            values = predict_checkpoint(
                payload["checkpoint"]["path"],
                payload["checkpoint"]["sha256"],
                [candidates[rid]["smiles"] for rid in valid],
                training["target_annotation_sha256"],
                endpoint=frozen["provenance"]["endpoint"],
            )
        else:
            weights = np.asarray(payload["coefficients"], dtype=np.float64)
            if (
                weights.shape != (1024,)
                or not np.isfinite(weights).all()
                or payload["source_rows_sha256"] != sha(rows)
            ):
                raise ValueError("invalid_reused_synthetic_model")
            values = features(
                [candidates[rid]["smiles"] for rid in valid]
            ) @ weights + _number(payload["intercept"])
        predictions = {rid: _number(float(v)) for rid, v in zip(valid, values)}
    elif (
        arm == "ai_engine"
        and frozen["protocol"]["source"]["kind"] == "chembl_fit_intake"
    ):
        from tools.product.train_public_chembl_selector import fit

        source = frozen["protocol"]["source"]
        fit(
            input_dir=source["input_dir"],
            summary_sha256=source["summary_sha256"],
            output_dir=directory / "model",
        )
        model_reference = file_ref(directory / "model/frozen-fit.json")
        for line in (
            (directory / "model/predictions-before-evaluation-labels.jsonl")
            .read_text()
            .splitlines()
        ):
            item = json.loads(line)
            if item["record_id"] in pool and item["predicted"] is not None:
                predictions[item["record_id"]] = _number(item["predicted"])
    else:
        x = features([r["smiles"] for r in selected])
        z = features([candidates[rid]["smiles"] for rid in valid])
        y = np.asarray([r["fit_value"] for r in selected])
        if arm == "ai_engine":
            from sklearn.linear_model import Ridge

            # Same feature and fixed Ridge primitives; this fixture model is synthetic only.
            model = Ridge(alpha=10.0, solver="cholesky").fit(x, y)
            values = model.predict(z) if len(z) else []
            publish(
                directory / "synthetic-model.json",
                {
                    "coefficients": model.coef_.tolist(),
                    "intercept": float(model.intercept_),
                    "evidence_kind": "synthetic_constants",
                    "fit_record_ids": [r["record_id"] for r in selected],
                    "source_rows_sha256": sha(rows),
                },
            )
            model_reference = file_ref(directory / "synthetic-model.json")
        else:
            # Nearest-neighbor Tanimoto, equal weighting for tied nearest fit compounds.
            # Replicate rows first collapse by canonical SMILES, preventing replicate voting.
            unique = {}
            for index, row in enumerate(selected):
                unique.setdefault(row["smiles"], []).append(index)
            indices = [v[0] for v in unique.values()]
            fx, fy = x[indices], np.asarray([y[v].mean() for v in unique.values()])
            values = []
            for query in z:
                intersection = fx @ query
                union = fx.sum(axis=1) + query.sum() - intersection
                similarity = np.divide(
                    intersection, union, out=np.ones_like(union), where=union != 0
                )
                values.append(float(fy[similarity == similarity.max()].mean()))
        predictions = {rid: _number(float(value)) for rid, value in zip(valid, values)}
    order = _prediction_order(frozen, predictions)
    return (
        order,
        predictions,
        {
            "feature_fit_prediction_seconds": time.perf_counter() - tick,
            "mode": "model_reuse" if reused else "cold_fit_included",
            "reused_model_run_measured": bool(reused),
            "model_reference": model_reference,
            "historical_cold_run": reused,
        },
    )


def worker(run_dir, arm, deadline):
    directory = run_dir / arm
    envelope = read(run_dir / "frozen.json")
    frozen, binding = envelope["payload"], envelope["sha256"]
    if sha(frozen) != binding:
        raise ValueError("frozen_comparison_binding_mismatch")
    if arm != "similarity":
        import torch

        torch.set_num_threads(1)
    order, predictions, setup = _priority(frozen, arm, directory)
    publish(
        directory / "priority.json",
        {
            "binding": binding,
            "arm": arm,
            "order": order,
            "predictions": predictions,
            "setup_cost": setup,
            "evaluation_labels_read": 0,
        },
    )
    if arm != "similarity":
        from betelgeuze_engine.product.prepared_rigid_poses import (
            evaluate_rigid_pose_request,
        )
        from tools.product.verify_prepared_cross_numerics import check_report

    called = 0
    for rid in order:
        if time.monotonic() >= deadline:
            break
        if (
            arm != "similarity"
            and called >= frozen["protocol"]["max_engine_calls_per_arm"]
        ):
            break
        tick, cpu = time.perf_counter(), time.process_time()
        result = {
            "record_id": rid,
            "arm": arm,
            "binding": binding,
            "score": None,
            "status": "unsupported",
            "reason": "prepared_input_missing",
            "prediction": predictions.get(rid),
        }
        try:
            if arm == "similarity":
                result.update(status="evaluated", score=predictions[rid], reason=None)
            elif frozen["requests"][rid] is not None and frozen["protocol"]["schema_version"] == D3_SCHEMA:
                from betelgeuze_product.cpu_refinement_v1_2 import policy_adapter
                called += 1
                report = policy_adapter.evaluate(frozen["requests"][rid])
                summary = policy_adapter.summarize(report, request=frozen["requests"][rid])
                file = directory / (sha(rid) + ".d3.json")
                publish(file, report)
                result.update(status=summary["status"], score=summary["score"], reason=summary["reason"],
                              d3_summary=summary, d3_report=file_ref(file))
            elif frozen["requests"][rid] is not None:
                called += 1
                report = json.loads(
                    canonical(evaluate_rigid_pose_request(frozen["requests"][rid]))
                )
                checked = check_report(report)
                file = directory / (sha(rid) + ".poses.json")
                publish(file, report)
                result.update(
                    status="failed",
                    reason="incomplete_or_failed_numeric_pose",
                    pose_denominator=report["denominator"],
                    numeric_denominator=checked["denominator"],
                    pose_report={
                        "path": str(file),
                        "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                    },
                )
                if checked["status"] == "passed":
                    result.update(
                        status="evaluated",
                        reason=None,
                        score=min(
                            row["result"]["quantities"]["cross_total_kcal_per_mol"]
                            for row in report["rows"]
                        ),
                    )
        except Exception as exc:
            result.update(status="failed", reason=type(exc).__name__ + ":" + str(exc))
        result.update(
            cost={
                "wall_seconds": time.perf_counter() - tick,
                "cpu_seconds": time.process_time() - cpu,
            },
            completed_monotonic=time.monotonic(),
        )
        if not publish(
            directory / (sha(rid) + ".row.json"),
            {"payload": result, "sha256": sha(result)},
            deadline=deadline,
        ):
            break
    publish(
        directory / "worker-complete.json",
        {
            "binding": binding,
            "engine_calls": called,
            "process_cpu_seconds": time.process_time(),
            "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
    )


def _arm_summary(directory, frozen, binding, completion):
    rows = []
    for rid in frozen["pool"]:
        path = directory / (sha(rid) + ".row.json")
        value = {
            "record_id": rid,
            "status": "not_processed",
            "score": None,
            "reason": completion["status"],
        }
        if path.exists():
            wrapped = read(path)
            item = wrapped["payload"]
            if (
                sha(item) != wrapped["sha256"]
                or item["binding"] != binding
                or item["record_id"] != rid
                or item["arm"] != directory.name
            ):
                raise ValueError("committed_comparison_row_mismatch")
            if item["completed_monotonic"] <= completion["deadline"]:
                value = item
            else:
                value["reason"] = "completed_after_budget"
        elif (directory / "priority.json").exists():
            priority = read(directory / "priority.json")
            if priority["binding"] != binding or priority["arm"] != directory.name:
                raise ValueError("priority_binding_mismatch")
            if directory.name != "engine" and rid not in priority["order"]:
                value.update(status="unsupported", reason="predictor_abstained")
        if value.get("pose_report"):
            from betelgeuze_engine.product.prepared_pose_journal import _file_hash

            if (
                _file_hash(Path(value["pose_report"]["path"]))
                != value["pose_report"]["sha256"]
            ):
                raise ValueError("pose_report_hash_mismatch")
        if value.get("d3_report"):
            from betelgeuze_product.cpu_refinement_v1_2 import policy_adapter
            summary = policy_adapter.summarize(bound(value["d3_report"]), request=frozen["requests"][rid])
            if (summary != value["d3_summary"] or summary["score"] != value["score"]
                    or summary["status"] != value["status"]):
                raise ValueError("D3_committed_summary_mismatch")
        elif (frozen["protocol"]["schema_version"] == D3_SCHEMA and directory.name != "similarity"
              and value["status"] == "evaluated"):
            raise ValueError("D3_evaluated_row_missing_report")
        rows.append(value)
    direction = -1 if directory.name == "similarity" else 1
    ranked = sorted(
        (r for r in rows if r["status"] == "evaluated"),
        key=lambda r: (direction * r["score"], r["record_id"]),
    )
    observations = {}
    for name in ("priority.json", "worker-complete.json"):
        if (directory / name).exists():
            value = read(directory / name)
            if value["binding"] != binding:
                raise ValueError("worker_observation_binding_mismatch")
            if name == "priority.json" and value["setup_cost"].get("model_reference"):
                payload = bound(value["setup_cost"]["model_reference"])
                if frozen["protocol"]["source"]["kind"] == "chembl_fit_intake":
                    for key in ("checkpoint", "protocol"):
                        bound(payload[key])
            observations[name] = value
    return {
        "worker_observations": observations,
        "rows": rows,
        "denominator": {
            "requested": len(rows),
            **dict(Counter(r["status"] for r in rows)),
        },
        "ranked_record_ids": [r["record_id"] for r in ranked],
        "cost": completion,
        "score_quantity": "predicted_negative_log10_molar_endpoint"
        if directory.name == "similarity"
        else ("uncalibrated_scorer_v1_dimensionless_minimize" if frozen["protocol"]["schema_version"] == D3_SCHEMA
              else "existing_cross_only_kcal_per_mol"),
        "combined_assay_energy_score": None,
    }


def run(protocol, output_dir, *, resume=False):
    started = time.perf_counter()
    frozen, setup_seconds = freeze(protocol)
    binding = sha(frozen)
    output_dir = Path(output_dir).resolve()
    if not resume:
        output_dir.mkdir()
    elif not output_dir.is_dir():
        raise ValueError("resume_directory_missing")
    with (output_dir / "run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        envelope = {"payload": frozen, "sha256": binding}
        if resume:
            if read(output_dir / "frozen.json") != envelope:
                raise ValueError("resume_input_or_runtime_changed")
            if (output_dir / "comparison.json").exists():
                result = read(output_dir / "comparison.json")
                if result["binding"] != binding:
                    raise ValueError("comparison_binding_mismatch")
                for arm in ARMS:
                    actual = _arm_summary(
                        output_dir / arm,
                        frozen,
                        binding,
                        read(output_dir / arm / "completion.json"),
                    )
                    if actual != result["arms"][arm]:
                        raise ValueError("resume_committed_summary_mismatch")
                return result
        else:
            publish(output_dir / "frozen.json", envelope)
        arms = {}
        for arm in _execution_order(protocol):
            directory = output_dir / arm
            directory.mkdir(exist_ok=resume)
            attempt = directory / "attempt.json"
            if not attempt.exists():
                tick = time.monotonic()
                deadline = tick + protocol["budget_seconds_per_arm"]
                publish(
                    attempt,
                    {
                        "binding": binding,
                        "started_monotonic": tick,
                        "deadline": deadline,
                    },
                )
                command = [
                    sys.executable,
                    "-B",
                    "-m",
                    "tools.product.compare_prepared_candidate_policies",
                    "worker",
                    "--run-dir",
                    str(output_dir),
                    "--arm",
                    arm,
                    "--deadline",
                    str(deadline),
                ]
                environment = dict(
                    os.environ,
                    OMP_NUM_THREADS="1",
                    MKL_NUM_THREADS="1",
                    PYTHONDONTWRITEBYTECODE="1",
                )
                root = str(Path(__file__).resolve().parents[2])
                with (
                    (directory / "worker.log").open("x") as log,
                    (directory / "worker.lock").open("a") as lease,
                ):
                    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    child = subprocess.Popen(
                        command,
                        cwd=root,
                        env=environment,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                        pass_fds=(lease.fileno(),),
                    )
                    status = "complete"
                    try:
                        code = child.wait(
                            timeout=max(0.001, deadline - time.monotonic())
                        )
                        if code != 0:
                            status = "worker_failed"
                    except subprocess.TimeoutExpired:
                        _stop_child(child)
                        status = "budget_exhausted"
                    except BaseException:
                        _stop_child(child)
                        raise
                elapsed = time.monotonic() - tick
                if elapsed > protocol["budget_seconds_per_arm"]:
                    status = "budget_exhausted"
                complete = {
                    "binding": binding,
                    "status": status,
                    "deadline": deadline,
                    "measured_process_wall_seconds": elapsed,
                    "budget_seconds": protocol["budget_seconds_per_arm"],
                    "termination_overhead_seconds": max(
                        0.0, elapsed - protocol["budget_seconds_per_arm"]
                    ),
                }
                publish(directory / "completion.json", complete)
            elif not (directory / "completion.json").exists():
                with (directory / "worker.lock").open("a") as lease:
                    try:
                        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError as exc:
                        raise ValueError("comparison_worker_still_running") from exc
                prior = read(attempt)
                if prior["binding"] != binding:
                    raise ValueError("attempt_binding_mismatch")
                # A lost parent leaves uncertain work/cost: do not obtain a free retry.
                publish(
                    directory / "completion.json",
                    {
                        "binding": binding,
                        "status": "interrupted_budget_forfeited",
                        "deadline": prior["deadline"],
                        "measured_process_wall_seconds": None,
                        "budget_seconds": protocol["budget_seconds_per_arm"],
                        "termination_overhead_seconds": None,
                    },
                )
            completion = read(directory / "completion.json")
            if completion["binding"] != binding:
                raise ValueError("completion_binding_mismatch")
            arms[arm] = _arm_summary(directory, frozen, binding, completion)
        # Recheck every bound input and all code before publishing completed comparison.
        refreshed, _ = freeze(protocol)
        if refreshed != frozen:
            raise ValueError("inputs_changed_during_comparison")
        result = {
            "schema_version": "prepared_candidate_comparison_result_v1",
            "binding": binding,
            "pool": frozen["pool"],
            "arms": arms,
            "provenance": frozen["provenance"],
            "evaluation_labels_read": 0,
            "scientifically_validated": False,
            "product_ranking_enabled": False,
            "same_prepared_assay_state_verified": False,
            "end_to_end_cost_measured": False,
            "common_validation_seconds": setup_seconds,
            "orchestrator_wall_seconds": time.perf_counter() - started,
            "cost_scope": frozen["scope"],
            "upstream_cost": None,
        }
        publish(output_dir / "comparison.json", result)
        return result


def _label_metrics(result, frozen, labels):
    metrics = {}
    k = frozen["protocol"]["top_k"]
    for arm, data in result["arms"].items():
        rows = {r["record_id"]: r for r in data["rows"]}
        remaining, hits, known, unknown = k, 0.0, 0.0, 0.0
        scores = [rows[rid]["score"] for rid in data["ranked_record_ids"]]
        for score in dict.fromkeys(scores):
            tied = [
                rid for rid in data["ranked_record_ids"] if rows[rid]["score"] == score
            ]
            take = min(remaining, len(tied))
            weight = take / len(tied)
            hits += weight * sum(labels[rid] is True for rid in tied)
            known += weight * sum(labels[rid] is not None for rid in tied)
            unknown += weight * sum(labels[rid] is None for rid in tied)
            remaining -= take
            if not remaining:
                break
        metrics[arm] = {
            "requested": len(result["pool"]),
            "ranked": len(scores),
            "top_k": k,
            "tie_expected_known_active_hits": hits,
            "tie_expected_known_labels": known,
            "tie_expected_unknown_labels": unknown,
            "unfilled_top_k_slots": remaining,
            "full_pool_coverage": len(scores) / len(result["pool"]),
            "known_positive_recall": hits / sum(v is True for v in labels.values())
            if any(v is True for v in labels.values())
            else None,
        }
    return metrics


def evaluate_synthetic(result_ref, frozen_ref, labels_ref, output):
    """Post-freeze metrics for the synthetic contract; never accepts native labels."""
    result, envelope = bound(result_ref), bound(frozen_ref)
    frozen = envelope["payload"]
    if (
        sha(frozen) != envelope["sha256"]
        or result["binding"] != envelope["sha256"]
        or frozen["protocol"]["source"]["kind"] != "synthetic_constants"
    ):
        raise ValueError("synthetic_evaluation_freeze_mismatch")
    labels = bound(labels_ref)  # only after frozen protocol/result checks
    if set(labels) != set(result["pool"]) or any(
        v not in (True, False, None) or type(v) not in (bool, type(None))
        for v in labels.values()
    ):
        raise ValueError("synthetic_label_denominator_mismatch")
    metrics = _label_metrics(result, frozen, labels)
    report = {
        "evidence_kind": "synthetic_contract_test",
        "binding": result["binding"],
        "metrics": metrics,
        "labels_read_after_result_binding": True,
        "scientifically_validated": False,
        "ai_advantage_claimed": False,
    }
    publish(output, report)
    return report


def evaluate_native(result_ref, frozen_ref, evaluation_dir, summary_sha256, output):
    """Decode native outcomes only after validating the saved comparison and inputs.

    This measures a catalogue-development experiment, not a scientifically
    admitted assay/prepared-state join or an independent blind qualification.
    """
    started = time.perf_counter()
    result, envelope = bound(result_ref), bound(frozen_ref)
    frozen = envelope["payload"]
    if (
        sha(frozen) != envelope["sha256"]
        or result["binding"] != envelope["sha256"]
        or frozen["protocol"]["source"]["kind"] != "chembl_fit_intake"
        or result["pool"] != frozen["pool"]
        or set(result["arms"]) != set(ARMS)
    ):
        raise ValueError("native_evaluation_freeze_mismatch")
    current, _ = freeze(frozen["protocol"])
    if current != frozen:
        raise ValueError("native_evaluation_inputs_changed")
    root = Path(result_ref["path"]).parent
    for arm in ARMS:
        completion = read(root / arm / "completion.json")
        if (
            completion["binding"] != result["binding"]
            or _arm_summary(root / arm, frozen, result["binding"], completion)
            != result["arms"][arm]
        ):
            raise ValueError("native_evaluation_committed_results_changed")
    evaluation_summary = bound(
        {"path": str(Path(evaluation_dir) / "summary.json"), "sha256": summary_sha256}
    )
    for key in ("split_plan_sha256", "intake_scope_sha256"):
        if evaluation_summary.get(key) != frozen["provenance"][key]:
            raise ValueError("native_evaluation_role_scope_mismatch")
    from tools.product.train_public_chembl_selector import load_intake

    summary, _, scope, records = load_intake(
        Path(evaluation_dir), summary_sha256, "evaluation"
    )
    selected = {
        r["record_id"]: r for r in records if r["assigned_role"] == "development_test"
    }
    if set(selected) != set(result["pool"]):
        raise ValueError("native_evaluation_denominator_mismatch")
    identities = {r["record_id"]: r for r in frozen["rows"]}
    threshold = _number(scope["positive_threshold_negative_log10_molar"])
    labels = {}
    for rid, row in selected.items():
        if (
            row["component_id"] != identities[rid]["component_id"]
            or row["assay_id"] != identities[rid]["assay_id"]
        ):
            raise ValueError("native_evaluation_identity_changed")
        labels[rid] = (
            row["observation"]["negative_log10_molar"] >= threshold
            if row["eligible_for_point_model"]
            else None
        )
    by_assay = {}
    for assay in sorted({r["assay_id"] for r in selected.values()}):
        pool = [rid for rid in result["pool"] if selected[rid]["assay_id"] == assay]
        restricted = {"pool": pool, "arms": {}}
        for arm, data in result["arms"].items():
            restricted["arms"][arm] = {
                "rows": [r for r in data["rows"] if r["record_id"] in pool],
                "ranked_record_ids": [
                    rid for rid in data["ranked_record_ids"] if rid in pool
                ],
            }
        by_assay[assay] = _label_metrics(
            restricted, frozen, {rid: labels[rid] for rid in pool}
        )
    report = {
        "evidence_kind": "source_bound_catalogue_development",
        "binding": result["binding"],
        "evaluation_intake_summary_sha256": summary_sha256,
        "metrics_by_assay": by_assay,
        "requested": len(labels),
        "known": sum(v is not None for v in labels.values()),
        "unknown": sum(v is None for v in labels.values()),
        "endpoint": scope["endpoint"],
        "positive_threshold_negative_log10_molar": threshold,
        "same_prepared_assay_state_verified": False,
        "heldout_blindness_verified": False,
        "labels_read_after_result_binding": True,
        "scientifically_validated": False,
        "ai_advantage_claimed": False,
        "wall_seconds": time.perf_counter() - started,
    }
    publish(output, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    launch = subs.add_parser("run")
    launch.add_argument("--protocol", type=Path, required=True)
    launch.add_argument("--output-dir", type=Path, required=True)
    launch.add_argument("--resume", action="store_true")
    child = subs.add_parser("worker")
    child.add_argument("--run-dir", type=Path, required=True)
    child.add_argument("--arm", choices=ARMS, required=True)
    child.add_argument("--deadline", type=float, required=True)
    evaluation = subs.add_parser("evaluate")
    evaluation.add_argument("--comparison", type=Path, required=True)
    evaluation.add_argument("--comparison-sha256", required=True)
    evaluation.add_argument("--frozen", type=Path, required=True)
    evaluation.add_argument("--frozen-sha256", required=True)
    evaluation.add_argument("--evaluation-dir", type=Path, required=True)
    evaluation.add_argument("--summary-sha256", required=True)
    evaluation.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "worker":
        worker(args.run_dir, args.arm, args.deadline)
    elif args.command == "evaluate":
        evaluate_native(
            {"path": str(args.comparison), "sha256": args.comparison_sha256},
            {"path": str(args.frozen), "sha256": args.frozen_sha256},
            args.evaluation_dir,
            args.summary_sha256,
            args.output,
        )
    else:
        result = run(read(args.protocol), args.output_dir, resume=args.resume)
        print(
            canonical(
                {arm: data["denominator"] for arm, data in result["arms"].items()}
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
