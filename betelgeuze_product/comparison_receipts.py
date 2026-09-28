"""Portable, read-only receipts for completed synthetic four-arm comparisons.

This is a new result contract. It exports a *completed* checkout research run
without migrating its checkpoint, and verifies the exported copy without the
checkout, original prepared inputs, engine, selector, or evaluation labels.
Selector predictions are checked against committed rows but are not refitted.
The receipt establishes local integrity, not source authenticity or fitness.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Any

from .prepared_cross_numeric_reference import MAX_BYTES as MAX_POSE_BYTES, check_report

ARMS = ("similarity", "engine", "ai_engine", "similarity_engine")
SCHEMA = "installed_synthetic_prepared_comparison_receipt_v1"
MANIFEST_SCHEMA = "installed_synthetic_prepared_comparison_manifest_v1"
MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_POOL = 10000
HEX = re.compile(r"[0-9a-f]{64}\Z")


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _json(raw: bytes):
    return json.loads(raw, object_pairs_hook=_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")))


def _finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def _sha(value):
    return _digest(_canonical(value))


def _regular_file(path: Path, limit: int) -> bytes:
    """Read only a single-link regular file; reject symlinks and changed files."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                 "receipt_not_single_link_regular_file")
        _require(before.st_size <= limit, "receipt_capacity_exceeded")
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    observed = path.stat(follow_symlinks=False)
    def identity(s):
        return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns
    _require(len(raw) <= limit and len(raw) == before.st_size and
             identity(before) == identity(after) == identity(observed),
             "receipt_changed_during_read")
    return raw


def _load(path: Path, limit: int = MAX_JSON_BYTES):
    return _json(_regular_file(path, limit))


def _write(path: Path, raw: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _entry(path: str, raw: bytes) -> dict:
    return {"path": path, "bytes": len(raw), "sha256": _digest(raw)}


def _ref_is_valid(value):
    return (type(value) is dict and set(value) == {"path", "bytes", "sha256"}
            and type(value["path"]) is str and type(value["bytes"]) is int
            and value["bytes"] >= 0 and type(value["sha256"]) is str
            and HEX.fullmatch(value["sha256"]) is not None)


def _private_dir(path: Path) -> None:
    st = path.lstat()
    _require(stat.S_ISDIR(st.st_mode) and st.st_uid == os.geteuid()
             and not st.st_mode & 0o077, "receipt_directory_not_private")


def _validate_result(result: dict, report_reader) -> list[dict]:
    _require(type(result) is dict and result.get("schema_version") == SCHEMA,
             "unsupported_receipt_schema")
    _require(result.get("source_kind") == "synthetic_constants"
             and result.get("legacy_protocol_version") in {
                 "prepared_candidate_comparison_protocol_v1",
                 "prepared_candidate_comparison_protocol_v2",
             } and type(result.get("legacy_binding")) is str
             and HEX.fullmatch(result["legacy_binding"]) is not None,
             "unsupported_receipt_source")
    _require(result.get("scientifically_validated") is False
             and result.get("source_authenticated") is False
             and result.get("selector_recomputed") is False
             and result.get("evaluation_labels_read") == 0
             and result.get("same_prepared_assay_state_verified") is False
             and result.get("product_ranking_enabled") is False,
             "unsupported_receipt_authority")
    pool = result.get("pool")
    _require(type(pool) is list and 1 <= len(pool) <= MAX_POOL
             and all(type(rid) is str and rid for rid in pool)
             and len(set(pool)) == len(pool), "invalid_receipt_pool")
    _require(type(result.get("arm_order")) is list
             and len(result["arm_order"]) == len(ARMS)
             and set(result["arm_order"]) == set(ARMS), "invalid_receipt_arm_order")
    budget, cap = result.get("budget_seconds_per_arm"), result.get("max_engine_calls_per_arm")
    _require(_finite(budget) and 0 < budget <= 3600
             and type(cap) is int and 1 <= cap <= MAX_POOL, "invalid_receipt_budget")
    arms = result.get("arms")
    _require(type(arms) is dict and set(arms) == set(ARMS), "invalid_receipt_arms")
    references = []
    for arm in ARMS:
        data = arms[arm]
        _require(type(data) is dict and set(data) == {
            "rows", "denominator", "ranked_record_ids", "priority", "worker_complete",
            "completion", "score_quantity", "combined_assay_energy_score",
        }, "invalid_receipt_arm_fields")
        completion, worker, priority = (data[key] for key in (
            "completion", "worker_complete", "priority"))
        binding = result["legacy_binding"]
        _require(type(completion) is dict and completion.get("binding") == binding
                 and completion.get("status") == "complete"
                 and completion.get("budget_seconds") == budget
                 and _finite(completion.get("deadline")) and completion["deadline"] > 0
                 and _finite(completion.get("measured_process_wall_seconds"))
                 and 0 <= completion["measured_process_wall_seconds"] <= budget
                 and _finite(completion.get("termination_overhead_seconds"))
                 and completion["termination_overhead_seconds"] == max(
                     0.0, completion["measured_process_wall_seconds"] - budget),
                 "invalid_completion_receipt")
        _require(type(worker) is dict and worker.get("binding") == binding
                 and worker.get("stop_reason") in {
                     "order_exhausted", "engine_call_cap", "deadline"}
                 and type(worker.get("engine_calls")) is int
                 and 0 <= worker["engine_calls"] <= cap
                 and _finite(worker.get("process_cpu_seconds"))
                 and worker["process_cpu_seconds"] >= 0
                 and type(worker.get("process_peak_rss_kib")) is int
                 and worker["process_peak_rss_kib"] >= 0,
                 "invalid_worker_completion_receipt")
        _require(arm != "similarity" or worker["engine_calls"] == 0,
                 "similarity_claims_engine_calls")
        _require(worker["stop_reason"] != "engine_call_cap"
                 or (arm != "similarity" and worker["engine_calls"] == cap),
                 "invalid_engine_call_cap")
        _require(type(priority) is dict and priority.get("binding") == binding
                 and priority.get("arm") == arm
                 and priority.get("evaluation_labels_read") == 0
                 and type(priority.get("predictions")) is dict
                 and type(priority.get("order")) is list
                 and len(priority["order"]) == len(set(priority["order"]))
                 and set(priority["order"]) <= set(pool),
                 "invalid_priority_receipt")
        if arm == "engine":
            _require(priority["order"] == pool and priority["predictions"] == {},
                     "invalid_engine_priority")
        else:
            _require(set(priority["predictions"]) == set(priority["order"]),
                     "invalid_priority_prediction_coverage")
        _require(all(_finite(v) for v in priority["predictions"].values()),
                 "nonfinite_priority_prediction")
        rows = data["rows"]
        _require(type(rows) is list and len(rows) == len(pool)
                 and [r.get("record_id") if type(r) is dict else None for r in rows] == pool,
                 "invalid_receipt_rows")
        expected_denominator = {"requested": len(pool), **dict(Counter(r.get("status") for r in rows))}
        _require(data["denominator"] == expected_denominator,
                 "receipt_denominator_mismatch")
        processed = {r["record_id"] for r in rows if "completed_monotonic" in r}
        _require(processed <= set(priority["order"]), "row_outside_committed_priority")
        if worker["stop_reason"] == "order_exhausted":
            _require(processed == set(priority["order"]),
                     "completed_worker_missing_ordered_row")
        pose_report_count = 0
        for row in rows:
            rid, status, score = row["record_id"], row.get("status"), row.get("score")
            _require(status in {"evaluated", "failed", "unsupported", "not_processed"}
                     and ((status == "evaluated" and _finite(score))
                          or (status != "evaluated" and score is None)),
                     "invalid_receipt_row_score")
            if "completed_monotonic" in row:
                _require(_finite(row["completed_monotonic"])
                         and row["completed_monotonic"] <= completion["deadline"],
                         "row_after_completion_deadline")
            ref = row.get("pose_report")
            if ref is not None:
                _require(arm != "similarity" and _ref_is_valid(ref)
                         and ref["path"] == f"reports/{arm}/{_sha(rid)}.poses.json",
                         "invalid_pose_report_reference")
                report = report_reader(ref)
                checked = check_report(report)
                _require(row.get("pose_denominator") == report["denominator"]
                         and row.get("numeric_denominator") == checked["denominator"],
                         "pose_report_denominator_mismatch")
                if checked["status"] == "passed":
                    expected = min(item["result"]["quantities"]["cross_total_kcal_per_mol"]
                                   for item in report["rows"])
                    _require(status == "evaluated" and score == expected,
                             "pose_report_score_mismatch")
                else:
                    _require(status == "failed", "pose_report_numeric_status_mismatch")
                references.append(ref)
                pose_report_count += 1
            elif arm != "similarity" and status == "evaluated":
                raise ValueError("evaluated_engine_row_missing_pose_report")
            elif "pose_denominator" in row or "numeric_denominator" in row:
                raise ValueError("unreferenced_pose_denominator")
            if arm == "similarity" and status == "evaluated":
                _require(rid in priority["predictions"] and
                         score == priority["predictions"][rid],
                         "similarity_prediction_score_mismatch")
        _require(worker["engine_calls"] >= pose_report_count,
                 "engine_calls_less_than_saved_reports")
        direction = -1 if arm == "similarity" else 1
        ranked = sorted((r for r in rows if r["status"] == "evaluated"),
                        key=lambda r: (direction * r["score"], r["record_id"]))
        _require(data["ranked_record_ids"] == [r["record_id"] for r in ranked],
                 "receipt_ranking_mismatch")
        _require(data["score_quantity"] == (
            "predicted_negative_log10_molar_endpoint" if arm == "similarity"
            else "existing_cross_only_kcal_per_mol")
            and data["combined_assay_energy_score"] is None,
            "unsupported_score_quantity")
    paths = [ref["path"] for ref in references]
    _require(len(paths) == len(set(paths)), "duplicate_pose_report_reference")
    return sorted(references, key=lambda ref: ref["path"])


def verify_run(run_dir: Path) -> dict:
    """Read-only verification using only the installed package and receipt copy."""
    result = {"schema_version": "installed_synthetic_comparison_verification_v1",
              "status": "invalid", "exit_code": 2, "reason": None,
              "execution_performed": False, "selector_recomputed": False,
              "source_authenticated": False, "scientifically_validated": False,
              "resume_authorized": False, "pose_reports_checked": 0}
    try:
        root = Path(run_dir).absolute()
        _private_dir(root)
        manifest = _load(root / "manifest.json")
        _require(type(manifest) is dict and set(manifest) == {
            "schema_version", "result", "pose_reports"}
            and manifest["schema_version"] == MANIFEST_SCHEMA
            and _ref_is_valid(manifest["result"])
            and manifest["result"]["path"] == "result.json"
            and type(manifest["pose_reports"]) is list,
            "invalid_receipt_manifest")
        raw = _regular_file(root / "result.json", MAX_JSON_BYTES)
        _require(_entry("result.json", raw) == manifest["result"],
                 "receipt_result_hash_mismatch")
        data = _json(raw)

        def report_reader(ref):
            rel = Path(ref["path"])
            _require(len(rel.parts) == 3 and rel.parts[0] == "reports"
                     and rel.parts[1] in ARMS and rel.name.endswith(".poses.json"),
                     "unsafe_pose_report_path")
            _private_dir(root / "reports")
            _private_dir(root / "reports" / rel.parts[1])
            raw_report = _regular_file(root / rel, MAX_POSE_BYTES)
            _require(_entry(ref["path"], raw_report) == ref,
                     "pose_report_hash_mismatch")
            return _json(raw_report)

        references = _validate_result(data, report_reader)
        _require(manifest["pose_reports"] == references,
                 "pose_report_manifest_mismatch")
        _require(set(root.iterdir()) == {root / "manifest.json", root / "result.json", root / "reports"},
                 "unexpected_receipt_root_entry")
        _require(set((root / "reports").iterdir()) == {
            root / "reports" / arm for arm in ARMS},
            "unexpected_pose_report_directory")
        for arm in ARMS:
            expected_files = {root / ref["path"] for ref in references
                              if Path(ref["path"]).parts[1] == arm}
            _require(set((root / "reports" / arm).iterdir()) == expected_files,
                     "unexpected_pose_report_file")
        result.update(status="verified", exit_code=0, reason=None,
                      result_sha256=manifest["result"]["sha256"],
                      pose_reports_checked=len(references),
                      pool_count=len(data["pool"]), arms_verified=list(ARMS))
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        result["reason"] = str(exc) if type(exc) is ValueError else type(exc).__name__
    return result


def export_legacy_synthetic(source_run: Path, output_dir: Path) -> dict:
    """Export a completed v1/v2 synthetic checkout run to the new receipt.

    This copies already committed evidence; it does not execute or resume any
    worker. The export itself is only an integrity transform, not a rerun.
    """
    source = Path(source_run).absolute()
    output = Path(output_dir).absolute()
    _require(not output.is_relative_to(source), "output_inside_source_run")
    envelope = _load(source / "frozen.json")
    _require(type(envelope) is dict and set(envelope) == {"payload", "sha256"}
             and envelope["sha256"] == _sha(envelope["payload"]),
             "legacy_frozen_binding_mismatch")
    frozen, legacy = envelope["payload"], _load(source / "comparison.json")
    protocol = frozen["protocol"]
    _require(protocol.get("source", {}).get("kind") == "synthetic_constants"
             and protocol.get("schema_version") in {
                 "prepared_candidate_comparison_protocol_v1",
                 "prepared_candidate_comparison_protocol_v2",
             } and "reuse_ai_from" not in protocol,
             "only_cold_synthetic_v1_v2_export_supported")
    _require(legacy.get("schema_version") == "prepared_candidate_comparison_result_v1"
             and legacy.get("binding") == envelope["sha256"]
             and legacy.get("pool") == frozen["pool"]
             and set(legacy.get("arms", {})) == set(ARMS)
             and legacy.get("evaluation_labels_read") == 0
             and legacy.get("scientifically_validated") is False
             and legacy.get("product_ranking_enabled") is False,
             "invalid_legacy_comparison")
    arms, reports = {}, {}
    for arm in ARMS:
        src = source / arm
        _require(src.is_dir() and not src.is_symlink(), "missing_legacy_arm")
        old = legacy["arms"][arm]
        completion = _load(src / "completion.json")
        priority = _load(src / "priority.json")
        worker = _load(src / "worker-complete.json")
        _require(old["cost"] == completion
                 and old["worker_observations"]["priority.json"] == priority
                 and old["worker_observations"]["worker-complete.json"] == worker,
                 "legacy_summary_receipt_mismatch")
        rows = []
        for row in old["rows"]:
            rid = row["record_id"]
            path = src / f"{_sha(rid)}.row.json"
            if path.exists():
                wrapped = _load(path)
                _require(type(wrapped) is dict and set(wrapped) == {"payload", "sha256"}
                         and wrapped["sha256"] == _sha(wrapped["payload"]),
                         "legacy_row_hash_mismatch")
                if wrapped["payload"]["completed_monotonic"] <= completion["deadline"]:
                    _require(wrapped["payload"] == row, "legacy_row_summary_mismatch")
            copied = dict(row)
            ref = row.get("pose_report")
            if ref is not None:
                expected = src / f"{_sha(rid)}.poses.json"
                _require(type(ref) is dict and set(ref) == {"path", "sha256"}
                         and Path(ref["path"]).absolute() == expected,
                         "legacy_pose_reference_escaped_run")
                raw = _regular_file(expected, MAX_POSE_BYTES)
                _require(_digest(raw) == ref["sha256"], "legacy_pose_hash_mismatch")
                relative = f"reports/{arm}/{expected.name}"
                reports[relative] = raw
                copied["pose_report"] = _entry(relative, raw)
            rows.append(copied)
        arms[arm] = {
            "rows": rows, "denominator": old["denominator"],
            "ranked_record_ids": old["ranked_record_ids"],
            "priority": priority, "worker_complete": worker,
            "completion": completion, "score_quantity": old["score_quantity"],
            "combined_assay_energy_score": old["combined_assay_energy_score"],
        }
    result = {
        "schema_version": SCHEMA, "source_kind": "synthetic_constants",
        "legacy_protocol_version": protocol["schema_version"],
        "legacy_binding": envelope["sha256"], "pool": frozen["pool"],
        "arm_order": (list(ARMS) if protocol["schema_version"].endswith("_v1")
                      else protocol["arm_order"]),
        "budget_seconds_per_arm": protocol["budget_seconds_per_arm"],
        "max_engine_calls_per_arm": protocol["max_engine_calls_per_arm"],
        "arms": arms, "evaluation_labels_read": 0,
        "scientifically_validated": False, "source_authenticated": False,
        "selector_recomputed": False, "same_prepared_assay_state_verified": False,
        "product_ranking_enabled": False,
    }
    _validate_result(result, lambda ref: _json(reports[ref["path"]]))
    output.mkdir(mode=0o700)
    (output / "reports").mkdir(mode=0o700)
    for arm in ARMS:
        (output / "reports" / arm).mkdir(mode=0o700)
    for name, raw in reports.items():
        _write(output / name, raw)
    result_raw = _canonical(result) + b"\n"
    _require(len(result_raw) <= MAX_JSON_BYTES, "receipt_result_capacity_exceeded")
    _write(output / "result.json", result_raw)
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "result": _entry("result.json", result_raw),
        "pose_reports": [_entry(name, raw) for name, raw in sorted(reports.items())],
    }
    _write(output / "manifest.json", _canonical(manifest) + b"\n")
    verified = verify_run(output)
    _require(verified["status"] == "verified", "exported_receipt_failed_verification")
    return verified


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export-synthetic")
    export.add_argument("--source-run", type=Path, required=True)
    export.add_argument("--output-dir", type=Path, required=True)
    verify = commands.add_parser("verify-run")
    verify.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    outcome = (export_legacy_synthetic(args.source_run, args.output_dir)
               if args.command == "export-synthetic" else verify_run(args.run_dir))
    print(json.dumps(outcome, sort_keys=True, allow_nan=False))
    return outcome["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
