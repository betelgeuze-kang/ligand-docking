"""Exact paired admission and denominator-preserving P0/P1 evidence analysis."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import zipfile

from tools.redocking_evidence_support import (
    compare_environments,
    verify_artifact_archive,
)
from tools.run_redocking_development_stages import (
    digest_file,
    digest_json,
    read_json,
    recoveries,
    require,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/redocking_p0_p1_20261104.json"
ENGINES = ("engine_v2", "vina", "gnina")


def exact_numbers(value):
    if isinstance(value, float):
        require(math.isfinite(value), "nonfinite scientific value")
        return {"binary64_hex": value.hex()}
    if isinstance(value, dict):
        return {key: exact_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [exact_numbers(item) for item in value]
    return value


def scientific_projection(row):
    """Exclude only operational timing and run-directory command strings."""
    projection = json.loads(json.dumps(row, allow_nan=False))
    projection.pop("execution_command", None)
    projection.pop("runtime_seconds", None)
    diagnostics = projection.get("engine_v2_diagnostics")
    if diagnostics:
        diagnostics.pop("diagnostic_evaluation_seconds", None)
    return exact_numbers(projection)


def sdf_hashes(path):
    records, pending = [], []
    for line in path.read_bytes().splitlines(keepends=True):
        pending.append(line)
        if line.strip() == b"$$$$":
            records.append(hashlib.sha256(b"".join(pending)).hexdigest())
            pending = []
    require(not b"".join(pending).strip(), "unterminated SDF record")
    return records


def find_receipt(root, case_id, engine):
    paths = list(root.rglob(f"receipts/{engine}/{case_id}.json"))
    isolated = root / "cases" / case_id / "engines" / engine / "receipt.json"
    if isolated.is_file():
        paths.append(isolated)
    require(len(paths) <= 1, "duplicate engine receipt in run root")
    if not paths:
        return None
    payload = read_json(paths[0])
    require(
        payload.get("schema_id")
        == "betelgeuze.engine_v2_public_redocking_case_execution/1.1.0"
        and payload.get("runner_id")
        == "betelgeuze.engine_v2_public_redocking_300_runner/2.13.0",
        "scientific receipt schema/runner differs",
    )
    require(
        payload["receipt_sha256"]
        == digest_json({k: v for k, v in payload.items() if k != "receipt_sha256"}),
        "engine receipt digest differs",
    )
    row = payload["result"]
    require(
        (row["case_id"], row["engine_id"]) == (case_id, engine),
        "receipt identity differs",
    )
    require(
        payload["fresh_execution"] is True and payload["cache_read_allowed"] is False,
        "scientific receipt must represent fresh execution",
    )
    manifest = read_json(MANIFEST)
    if paths[0].name == "receipt.json":
        from tools.run_redocking_isolated_development import observe_science

        destination = paths[0].parent
        request_path = destination / "request.json"
        request = read_json(request_path)
        run_manifest = read_json(root / "run-manifest.json")
        worker_status = read_json(destination / "worker-status.json")
        require(
            request["source"] == run_manifest["source"] == worker_status["source"]
            and request["profile"] == run_manifest["profile"]
            and request["case_id"] == case_id
            and request["task"] == engine,
            "worker request/run/source identity differs",
        )
        require(
            worker_status["request_sha256"] == digest_file(request_path),
            "worker request bytes differ",
        )
        recorded_task_root = Path(request["task_root"])
        require(
            recorded_task_root.is_absolute()
            and ".." not in recorded_task_root.parts
            and recorded_task_root.parts[-4:]
            == ("cases", case_id, "engines", engine)
            and Path(request["materialization_root"])
            == recorded_task_root.parent.parent / "materialization",
            "recorded worker execution directories differ",
        )
        identity = read_json(destination / "journal/identity.json")
        summary = read_json(root / "summary.json")
        cases = [case for case in summary["cases"] if case["case_id"] == case_id]
        require(len(cases) == 1, "worker has no unique controller case")
        controller = cases[0]["engines"][engine]
        require(
            identity["request_sha256"]
            == controller["request_sha256"]
            == worker_status["request_sha256"]
            and controller["task_root"] == request["task_root"]
            and controller["worker_status"] == worker_status
            and worker_status["status"] == "completed"
            and worker_status["receipt_sha256"] == payload["receipt_sha256"]
            and identity["source"] == summary["source"] == request["source"]
            and identity["profile"] == summary["profile"] == request["profile"]
            and identity["case_id"] == case_id
            and identity["task"] == engine
            and cases[0]["global_index"] == manifest["case_ids"].index(case_id)
            and identity["seed"]
            == manifest["seed_base"] + cases[0]["global_index"],
            "worker request journal/controller binding differs",
        )
        verified = observe_science(
            destination,
            root / "cases" / case_id / "materialization",
            case_id,
            manifest["case_ids"].index(case_id),
            engine,
            manifest,
            run_manifest["source"],
            profile=run_manifest["profile"],
            recorded_task_root=recorded_task_root,
        )
        require(
            verified["row"] == row
            and verified["receipt_sha256"] == payload["receipt_sha256"],
            "independent worker input/evaluator/source verification differs",
        )
    require(
        payload["archive_sha256"] == manifest["inputs"]["archive"]["sha256"],
        "archive differs",
    )
    require(
        payload["source_ids_sha256"]
        == manifest["inputs"]["source_identifiers"]["sha256"],
        "source identifier differs",
    )
    if row["status"] == "success":
        for key in (
            "rmsd_angstroms",
            "geometric_valid",
            "chemical_valid",
            "pose_artifact_sha256s",
        ):
            require(
                len(row[key]) == 5, "successful receipt does not contain five poses"
            )
        require(
            all(
                type(value) is bool
                for value in row["geometric_valid"] + row["chemical_valid"]
            ),
            "invalid validity type",
        )
        require(
            all(
                type(value) in (float, int) and math.isfinite(value) and value >= 0
                for value in row["rmsd_angstroms"]
            ),
            "invalid RMSD value",
        )
        poses = list(root.rglob(f"poses/{engine}/{case_id}.sdf"))
        require(len(poses) == 1, "successful receipt lacks a unique SDF")
        require(
            sdf_hashes(poses[0]) == row["pose_artifact_sha256s"],
            "actual pose hashes differ",
        )
    else:
        require(row["status"] == "failure" and row["failure_code"], "untyped failure")
        require(
            all(
                not row[key]
                for key in (
                    "rmsd_angstroms",
                    "geometric_valid",
                    "chemical_valid",
                    "pose_artifact_sha256s",
                )
            ),
            "failed receipt has outcomes",
        )
    if engine == "engine_v2" and row["status"] == "success":
        candidates = row["engine_v2_diagnostics"]["candidates"]
        require(
            len(candidates) == 64
            and sorted(c["proposal_index"] for c in candidates) == list(range(64)),
            "fixed candidate denominator changed",
        )
    return payload


def compare_pair(legacy, observed):
    require(legacy is not None and observed is not None, "paired receipt is missing")
    require(
        legacy["result"]["status"] == observed["result"]["status"] == "success",
        "paired admission requires successful smoke receipts",
    )
    left, right = (
        scientific_projection(legacy["result"]),
        scientific_projection(observed["result"]),
    )
    return {
        "matches": left == right,
        "legacy_projection_sha256": digest_json(left),
        "p1_projection_sha256": digest_json(right),
        "input_hashes_match": legacy["input_sha256s"] == observed["input_sha256s"],
        "evaluator_pipeline_matches": legacy["evaluation_pipeline_sha256"]
        == observed["evaluation_pipeline_sha256"],
        "implementation_matches": legacy["implementation_sha256"]
        == observed["implementation_sha256"],
        "comparison": "all scientific result fields, float binary64 values, 64 candidate slots and five serialized pose hashes; excludes only elapsed time and command path strings",
    }


def journal_observations(root):
    """Verify committed event chains and retain incomplete stages as observations."""
    journals = []
    for directory in sorted({path.parent for path in root.rglob("event-*.json")}):
        identity = read_json(directory / "identity.json")
        identity_hash, previous, events = digest_json(identity), None, []
        for sequence, path in enumerate(sorted(directory.glob("event-*.json")), 1):
            wrapped = read_json(path)
            require(path.name == f"event-{sequence:06d}.json", "journal sequence gap")
            require(
                wrapped["journal_sequence"] == sequence
                and wrapped["identity_sha256"] == identity_hash
                and wrapped["previous_event_sha256"] == previous,
                "journal chain cross-wired",
            )
            require(
                wrapped["event_sha256"]
                == digest_json(
                    {k: v for k, v in wrapped.items() if k != "event_sha256"}
                ),
                "journal event changed",
            )
            previous = wrapped["event_sha256"]
            events.append(wrapped["event"])
        checkpoint_path = directory / "checkpoint.json"
        checkpoint = read_json(checkpoint_path) if checkpoint_path.exists() else None
        if checkpoint:
            index = checkpoint["last_sequence"] - 1
            require(
                0 <= index < len(events) and checkpoint["last_event"] == events[index],
                "checkpoint does not reference a committed event",
            )
            require(
                checkpoint["identity_sha256"] == identity_hash,
                "checkpoint identity differs",
            )
            require(
                checkpoint["event_path"] == f"event-{index + 1:06d}.json",
                "checkpoint path differs",
            )
            pointed = read_json(directory / checkpoint["event_path"])
            require(
                pointed["event_sha256"] == checkpoint["event_sha256"],
                "checkpoint digest differs",
            )
        durations, counts, active = {}, Counter(), {}
        for event in events:
            stage, phase = event.get("stage"), event.get("phase")
            details = event.get("details", {})
            key = (
                stage,
                details.get("proposal_index") if isinstance(details, dict) else None,
            )
            counts[(stage, phase)] += 1
            if phase == "start":
                active[key] = event
            elif phase in {"complete", "error"}:
                active.pop(key, None)
                if phase == "complete":
                    durations[stage] = durations.get(stage, 0.0) + event.get(
                        "elapsed_seconds", 0.0
                    )
        journals.append(
            {
                "path": str(directory.relative_to(root)),
                "identity": identity,
                "event_count": len(events),
                "checkpoint": checkpoint,
                "committed_events_after_checkpoint": len(events)
                - (0 if checkpoint is None else checkpoint["last_sequence"]),
                "completed_stage_seconds": durations,
                "event_counts": [
                    {"stage": key[0], "phase": key[1], "count": value}
                    for key, value in sorted(counts.items())
                ],
                "unfinished_stages": list(active.values()),
                "coordinate_snapshots": sum(
                    bool(e.get("details", {}).get("coordinates_binary64"))
                    for e in events
                    if isinstance(e.get("details", {}), dict)
                ),
                "last_committed_event": events[-1] if events else None,
            }
        )
    return journals


def observation_summary(root, case_id, engine):
    paths = [
        root / "cases" / case_id / "engines" / engine / "observation-summary.json",
        root / "engines" / engine / "observation-summary.json",
    ]
    matches = [read_json(path) for path in paths if path.is_file()]
    require(len(matches) <= 1, "duplicate observation summary")
    require(
        all(value.get("case_id") == case_id for value in matches),
        "observation summary case differs",
    )
    return matches[0] if matches else None


def paired(artifact_root, output_root):
    from tools.redocking_lineage_validation import validate_observation_events

    manifest = read_json(MANIFEST)
    report = {
        "schema_id": "betelgeuze.redocking_p0_p1_paired/1.0.0",
        "analysis_scope": "contaminated_development",
        "claim_safe": False,
        "denominator": 2,
        "cases": [],
        "paired_ready": False,
        "exact_numeric_gate_engines": ["engine_v2"],
        "external_policy": "Both smoke executions must succeed; external numeric comparisons are reported separately and do not gate the P1 Engine V2 change.",
        "interpretation": "Same-node paired equivalence and timings on two fixed cases; no accuracy improvement or general speedup claim.",
    }
    try:
        for index in manifest["smoke_indices"]:
            cid = manifest["case_ids"][index]
            left_root = artifact_root / "paired" / f"{index}-legacy"
            right_root = artifact_root / "paired" / f"{index}-p1"
            left_summary, right_summary = (
                read_json(root / "summary.json") for root in (left_root, right_root)
            )
            for value, profile in (
                (left_summary, "legacy_v7"),
                (right_summary, "development_observation_v1"),
            ):
                require(
                    value["profile"] == profile
                    and value["expected_indices"] == [index],
                    "paired profile/index differs",
                )
                require(
                    value["execution_complete"]
                    and value["scientific_accuracy_complete"],
                    "paired execution incomplete",
                )
                require(
                    len(value["cases"]) == 1 and value["cases"][0]["case_id"] == cid,
                    "paired case cross-wired",
                )
            comparisons, timings = {}, {}
            engine_v2_receipt = None
            for engine in ENGINES:
                left, right = (
                    find_receipt(left_root, cid, engine),
                    find_receipt(right_root, cid, engine),
                )
                if engine == "engine_v2":
                    engine_v2_receipt = right
                for summary, payload in ((left_summary, left), (right_summary, right)):
                    item = summary["cases"][0]["engines"][engine]
                    require(
                        payload
                        and item["observation_status"] == "observed"
                        and item["row"] == payload["result"]
                        and item["receipt_sha256"] == payload["receipt_sha256"],
                        "paired controller/receipt differs",
                    )
                comparisons[engine] = compare_pair(left, right)
                require(
                    comparisons[engine]["input_hashes_match"]
                    and comparisons[engine]["evaluator_pipeline_matches"]
                    and comparisons[engine]["implementation_matches"],
                    "paired input/evaluator/source differs",
                )
                timings[engine] = {
                    "legacy_wall_seconds": left_summary["cases"][0]["engines"][engine][
                        "execution"
                    ]["wall_seconds"],
                    "p1_wall_seconds": right_summary["cases"][0]["engines"][engine][
                        "execution"
                    ]["wall_seconds"],
                    "legacy_reported_runtime_seconds": left["result"][
                        "runtime_seconds"
                    ],
                    "p1_reported_runtime_seconds": right["result"]["runtime_seconds"],
                }
                for prefix, payload in (("legacy", left), ("p1", right)):
                    diag = payload["result"].get("engine_v2_diagnostics")
                    if diag:
                        timings[engine][prefix + "_diagnostic_evaluation_seconds"] = (
                            diag["diagnostic_evaluation_seconds"]
                        )
            journals = journal_observations(right_root)
            engine_journals = [
                j for j in journals if j["identity"].get("task") == "engine_v2"
            ]
            require(len(engine_journals) == 1, "missing unique Engine V2 phase journal")
            event_paths = sorted(
                (right_root / engine_journals[0]["path"]).glob("event-*.json")
            )
            lineage = validate_observation_events(
                [read_json(path)["event"] for path in event_paths],
                case_id=cid,
                canonical_row=engine_v2_receipt["result"],
            )
            require(
                lineage["evaluator_identity"]
                == engine_v2_receipt["evaluation_pipeline_sha256"],
                "lineage evaluator differs from canonical receipt",
            )
            observer = observation_summary(right_root, cid, "engine_v2")
            require(
                observer
                and observer["healthy"]
                and observer["emitted_events"] == lineage["p1_event_count"]
                and observer["evaluation_cache"]["reused_records"] >= 5,
                "Top5 duplicate evaluation was not safely reused",
            )
            report["cases"].append(
                {
                    "case_id": cid,
                    "comparisons": comparisons,
                    "timings": timings,
                    "observation_summary": observer,
                    "engine_v2_phase_journal": engine_journals[0],
                    "lineage_verification": lineage,
                }
            )
            require(
                comparisons["engine_v2"]["matches"],
                "P1 changed an Engine V2 scientific result",
            )
        report["paired_ready"] = True
    except Exception as exc:
        report["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        write_json(output_root / "paired-equivalence.json", report)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            stream.write("paired_ready=true\n")
    return report


def summarize_rows(records, expected_ids):
    """Use the frozen denominator, including engines never started."""
    metrics = {}
    for engine in ENGINES:
        observed = [
            records[cid]["engines"][engine] for cid in expected_ids if cid in records
        ]
        rows = [item["row"] for item in observed if item["row"] is not None]
        counts = {
            key: sum(recoveries(row)[key] for row in rows)
            for key in (
                "top1",
                "top3",
                "top5",
                "valid_top1",
                "valid_top3",
                "valid_top5",
            )
        }
        times = [
            item["execution"]["wall_seconds"]
            for item in observed
            if item.get("execution")
        ]
        metrics[engine] = {
            "denominator": len(expected_ids),
            "observed_rows": len(rows),
            "success_rows": sum(row["status"] == "success" for row in rows),
            "typed_failure_rows": sum(row["status"] == "failure" for row in rows),
            "unobserved_rows": len(expected_ids) - len(rows),
            "counts": counts,
            "rates": {key: value / len(expected_ids) for key, value in counts.items()},
            "worker_wall_seconds_sum": sum(times),
            "worker_wall_seconds_median": statistics.median(times) if times else None,
            "operation_status_counts": dict(
                Counter(item["operation_status"] for item in observed)
            ),
            "failure_codes": dict(
                Counter(
                    row["failure_code"] for row in rows if row["status"] == "failure"
                )
            ),
        }
        if engine == "engine_v2":
            candidate_rows = [
                c
                for row in rows
                for c in row["engine_v2_diagnostics"]["candidates"]
                if c["status"] == "success"
            ]
            counts["oracle"] = sum(
                any(
                    c["status"] == "success" and c["rmsd_angstrom"] <= 2
                    for c in row["engine_v2_diagnostics"]["candidates"]
                )
                for row in rows
            )
            counts["valid_oracle"] = sum(
                any(
                    c["status"] == "success"
                    and c["rmsd_angstrom"] <= 2
                    and c["geometric_valid"]
                    and c["chemical_valid"]
                    for c in row["engine_v2_diagnostics"]["candidates"]
                )
                for row in rows
            )
            metrics[engine]["candidate_success_count"] = len(candidate_rows)
            metrics[engine]["candidate_valid_count"] = sum(
                c["geometric_valid"] and c["chemical_valid"] for c in candidate_rows
            )
            metrics[engine]["candidate_failed_check_counts"] = dict(
                Counter(
                    check
                    for c in candidate_rows
                    for check in c["posebusters_failed_check_ids"]
                )
            )
            metrics[engine]["diagnostic_evaluation_seconds_sum"] = sum(
                row["engine_v2_diagnostics"]["diagnostic_evaluation_seconds"]
                for row in rows
            )
            metrics[engine]["reused_top5_records"] = sum(
                (item.get("observation_summary") or {})
                .get("evaluation_cache", {})
                .get("reused_records", 0)
                for item in observed
            )
            metrics[engine]["rates"].update(
                {
                    key: counts[key] / len(expected_ids)
                    for key in ("oracle", "valid_oracle")
                }
            )
    return metrics


def collect_development(root, records):
    summary = read_json(root / "summary.json")
    require(
        summary["stage"] == "development"
        and summary["profile"] == "development_observation_v1",
        "unexpected development stage/profile",
    )
    require(
        summary["analysis_scope"] == "contaminated_development"
        and summary["claim_safe"] is False,
        "development claim boundary differs",
    )
    manifest = read_json(MANIFEST)
    journals = journal_observations(root)
    for raw in summary["cases"]:
        cid, index = raw["case_id"], raw["global_index"]
        require(
            index in manifest["development_indices"]
            and manifest["case_ids"][index] == cid,
            "development case/index cross-wired",
        )
        require(
            cid not in records,
            "duplicate development attempt requires explicit separate analysis",
        )
        case = {
            "case_id": cid,
            "global_index": index,
            "seed": raw["seed"],
            "materialization": raw["materialization"],
            "engines": {},
        }
        for engine in ENGINES:
            item = raw["engines"][engine]
            receipt = None
            row = None
            if item["observation_status"] == "observed":
                receipt = find_receipt(root, cid, engine)
                require(
                    receipt
                    and receipt["result"] == item["row"]
                    and receipt["receipt_sha256"] == item["receipt_sha256"],
                    "controller/receipt differs",
                )
                row = receipt["result"]
            else:
                require(
                    item["row"] is None,
                    "unobserved controller invented a scientific row",
                )
            phase = [
                j
                for j in journals
                if j["identity"].get("case_id") == cid
                and j["identity"].get("task") == engine
            ]
            require(len(phase) <= 1, "duplicate engine journal")
            case["engines"][engine] = {
                "row": row,
                "receipt_sha256": None
                if receipt is None
                else receipt["receipt_sha256"],
                "raw_receipt_present": (
                    root / "cases" / cid / "engines" / engine / "receipt.json"
                ).is_file(),
                "observation_status": item["observation_status"],
                "operation_status": item["operation_status"],
                "execution": item.get("execution"),
                "errors": item.get("errors", []),
                "observation_summary": observation_summary(
                    root / "cases" / cid, cid, engine
                ),
                "phase_journal": phase[0] if phase else None,
            }
        records[cid] = case
    return {
        "source": summary["source"],
        "expected_indices": summary["expected_indices"],
        "attempted_cases": summary["attempted_cases"],
        "execution_complete": summary["execution_complete"],
        "scientific_accuracy_complete": summary["scientific_accuracy_complete"],
        "fatal_error": summary["fatal_error"],
    }


def environment_report(root, artifact_name):
    env = {
        "artifact": artifact_name,
        "start": None,
        "end": None,
        "reference_comparison": None,
        "end_comparison": None,
        "role": None,
    }
    if (root / "preflight.json").exists():
        env["role"] = read_json(root / "preflight.json").get("environment_role")
    for phase in ("start", "end"):
        path = root / ("environment-" + phase + ".json")
        if path.exists():
            value = read_json(path)
            env[phase] = {
                key: value[key]
                for key in (
                    "content_identity_sha256",
                    "raw_payload_sha256",
                    "report_sha256",
                    "wheel_set_sha256",
                )
            }
    for key, filename in (
        ("reference_comparison", "environment-vs-reference.json"),
        ("end_comparison", "environment-start-vs-end.json"),
    ):
        path = root / filename
        if path.exists():
            value = read_json(path)
            env[key] = {
                "matches": value["matches"],
                "raw_installed_payload_equal": value["raw_installed_payload_equal"],
                "raw_file_difference_count": len(value["raw_file_differences"]),
                "forbidden_file_difference_count": len(
                    value["forbidden_file_differences"]
                ),
                "identity_context_differences": value["identity_context_differences"],
            }
    return env


def revalidate_environments(entries):
    """Bind saved comparisons to the actual snapshots in the sealed upload."""
    references = [root for env, root in entries if env["role"] == "bootstrap_reference"]
    reference = None
    if len(references) == 1 and (references[0] / "environment-start.json").exists():
        reference = read_json(references[0] / "environment-start.json")
    for env, root in entries:
        for key, filename, left in (
            (
                "end_comparison",
                "environment-start-vs-end.json",
                read_json(root / "environment-start.json") if env["start"] else None,
            ),
            ("reference_comparison", "environment-vs-reference.json", reference),
        ):
            right_name = (
                "environment-end.json"
                if key == "end_comparison"
                else "environment-start.json"
            )
            if (
                left is None
                or not (root / right_name).exists()
                or not (root / filename).exists()
            ):
                continue
            actual = compare_environments(left, read_json(root / right_name))
            retained = read_json(root / filename)
            require(
                retained == actual,
                "saved environment comparison differs from actual snapshot comparison",
            )
            env[key]["recomputed_from_actual_snapshots"] = True
        for key, filename in (
            ("native_runtime_identity_sha256", "native-runtime.json"),
            (
                "native_wheel_manifest_identity_sha256",
                "native-wheelhouse-manifest.json",
            ),
        ):
            env[key] = (
                digest_json(read_json(root / filename))
                if (root / filename).exists()
                else None
            )


def aggregate(artifact_root, output_root):
    manifest = read_json(MANIFEST)
    output_root.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_id": "betelgeuze.redocking_p0_p1_aggregate/1.0.0",
        "analysis_scope": "contaminated_development",
        "claim_safe": False,
        "primary_claim_eligible": False,
        "fresh_holdout_executed": False,
        "paired_admission": None,
        "artifacts": [],
        "environments": [],
        "shards": [],
        "resource_policy_changed_from_baseline": True,
        "timing_note": "Worker wall includes imports, hashing and process setup. Completed stage timings can nest and must not be summed as disjoint costs.",
        "baseline_run_id": manifest["baseline_run_id"],
    }
    records, environments = {}, []
    archives = sorted(artifact_root.rglob("sealed-evidence.zip"))
    require(archives, "no sealed evidence artifacts found")
    extraction = artifact_root / "verified-contents"
    require(not extraction.exists(), "use a fresh aggregate extraction directory")
    for number, archive in enumerate(archives):
        verified = verify_artifact_archive(archive)
        report["artifacts"].append(
            {"path": str(archive.relative_to(artifact_root)), **verified}
        )
        destination = extraction / f"{number:02d}"
        destination.mkdir(parents=True)
        # Verification rejects absolute/traversal paths, duplicate members and symlinks.
        with zipfile.ZipFile(archive) as handle:
            handle.extractall(destination)
        comparison = destination / "paired-equivalence.json"
        if comparison.exists():
            require(report["paired_admission"] is None, "multiple admission reports")
            report["paired_admission"] = read_json(comparison)
        env = environment_report(destination, archive.parent.name)
        report["environments"].append(env)
        environments.append((env, destination))
        if (destination / "development/summary.json").exists():
            report["shards"].append(
                collect_development(destination / "development", records)
            )
    revalidate_environments(environments)
    return finalize_aggregate(report, records, manifest, output_root)


def finalize_aggregate(report, records, manifest, output_root):
    expected_ids = [manifest["case_ids"][i] for i in manifest["development_indices"]]
    report["metrics"] = summarize_rows(records, expected_ids)
    report["cases"] = [records[cid] for cid in expected_ids if cid in records]
    report["attempted_development_cases"] = len(records)
    report["missing_development_cases"] = [
        cid for cid in expected_ids if cid not in records
    ]
    content_ids = {
        env["start"]["content_identity_sha256"]
        for env in report["environments"]
        if env["start"]
    }
    report["environment_content_identity_count"] = len(content_ids)
    expected_groups = [
        manifest["development_indices"][offset : offset + 8]
        for offset in range(0, 32, 8)
    ]
    report["fixed_shards_verified"] = (
        sorted(shard["expected_indices"] for shard in report["shards"])
        == expected_groups
    )
    roles = Counter(env["role"] for env in report["environments"])
    native_complete = all(
        len({env.get(key) for env in report["environments"]}) == 1
        and all(env.get(key) for env in report["environments"])
        for key in (
            "native_runtime_identity_sha256",
            "native_wheel_manifest_identity_sha256",
        )
    )
    report["environment_verification_complete"] = (
        roles == {"bootstrap_reference": 1, "worker_comparison": 4}
        and len(content_ids) == 1
        and native_complete
        and all(
            env["start"]
            and env["end"]
            and env["end_comparison"]
            and env["end_comparison"]["matches"]
            and (
                (
                    env["role"] == "bootstrap_reference"
                    and env["reference_comparison"] is None
                )
                or (
                    env["reference_comparison"]
                    and env["reference_comparison"]["matches"]
                )
            )
            for env in report["environments"]
        )
    )
    report["scientific_accuracy_complete"] = bool(
        report["paired_admission"]
        and report["paired_admission"]["paired_ready"]
        and report["environment_verification_complete"]
        and report["fixed_shards_verified"]
        and len(records) == 32
        and all(value["unobserved_rows"] == 0 for value in report["metrics"].values())
        and len(report["shards"]) == 4
        and all(
            shard["scientific_accuracy_complete"] and not shard["fatal_error"]
            for shard in report["shards"]
        )
    )
    report["execution_complete"] = report["fixed_shards_verified"] and all(
        shard["execution_complete"] and not shard["fatal_error"]
        for shard in report["shards"]
    )
    write_json(output_root / "analysis.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("paired", "aggregate"))
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    result = (paired if args.operation == "paired" else aggregate)(
        args.artifact_root, args.output_root
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "paired_ready",
                    "scientific_accuracy_complete",
                    "execution_complete",
                )
                if key in result
            }
        )
    )


if __name__ == "__main__":
    main()
