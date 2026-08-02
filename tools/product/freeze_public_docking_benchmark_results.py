#!/usr/bin/env python3
"""Freeze completed public docking benchmark subject results immutably.

The execution harness writes convenient ``*_current`` files. Those are useful
for local inspection but are not benchmark evidence until their exact contents
are fixed. This tool validates the completed denominator and case-set identity,
copies each artifact to a content-addressed path, and writes a manifest with the
SHA-256 of every frozen file. Existing content-addressed paths are never
overwritten with different bytes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_EXECUTION_JSON = "runs/frozen_public_docking_benchmark_execution_current.json"
DEFAULT_EXECUTION_CSV = "runs/frozen_public_docking_benchmark_execution_current.csv"
DEFAULT_EXECUTION_MD = "runs/frozen_public_docking_benchmark_execution_current.md"
DEFAULT_METRICS_JSON = "config/frozen_public_docking_benchmark_metrics_current.json"

CLAIM_BOUNDARY = (
    "Immutable subject-result snapshot only. It verifies and content-addresses already completed local "
    "benchmark artifacts. It does not run docking, compute new metrics, run an external baseline, promote "
    "a claim, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _write_immutable(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise RuntimeError(f"immutable_result_snapshot_conflict:{path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)


def freeze_public_docking_benchmark_results(
    *,
    execution_json: str | Path = DEFAULT_EXECUTION_JSON,
    execution_csv: str | Path = DEFAULT_EXECUTION_CSV,
    execution_md: str | Path = DEFAULT_EXECUTION_MD,
    metrics_json: str | Path = DEFAULT_METRICS_JSON,
    output_root: Path = ROOT,
    frozen_at_utc: str | None = None,
) -> dict[str, Any]:
    source_paths = {
        "execution_json": _resolve(execution_json, root=output_root),
        "execution_csv": _resolve(execution_csv, root=output_root),
        "execution_md": _resolve(execution_md, root=output_root),
        "metrics_json": _resolve(metrics_json, root=output_root),
    }
    missing = [name for name, path in source_paths.items() if not path.is_file()]
    if missing:
        raise RuntimeError("result_snapshot_source_missing:" + ",".join(missing))

    contents = {name: path.read_bytes() for name, path in source_paths.items()}
    execution = json.loads(contents["execution_json"].decode("utf-8"))
    metrics = json.loads(contents["metrics_json"].decode("utf-8"))
    summary = execution.get("summary") or {}
    metric_values = metrics.get("metrics") or {}
    if summary.get("suite_complete") is not True:
        raise RuntimeError("result_snapshot_execution_not_complete")
    if summary.get("execution_ready") is not True:
        raise RuntimeError("result_snapshot_execution_not_ready")
    case_set_hash = str(summary.get("case_set_hash") or "")
    if len(case_set_hash) != 64:
        raise RuntimeError("result_snapshot_case_set_hash_invalid")
    if str(metrics.get("case_set_hash") or "") != case_set_hash:
        raise RuntimeError("result_snapshot_metrics_case_set_hash_mismatch")
    case_count = int(summary.get("frozen_case_count") or 0)
    selected_count = int(summary.get("selected_case_count") or 0)
    attempted_count = int(metric_values.get("attempted_case_count") or 0)
    if case_count <= 0 or selected_count != case_count or attempted_count != case_count:
        raise RuntimeError("result_snapshot_failure_denominator_mismatch")
    if len(execution.get("cases") or []) != case_count:
        raise RuntimeError("result_snapshot_execution_case_count_mismatch")

    csv_text = contents["execution_csv"].decode("utf-8")
    csv_rows = list(csv.DictReader(csv_text.splitlines()))
    expected_row_count = case_count * 2
    if len(csv_rows) != expected_row_count:
        raise RuntimeError(
            f"result_snapshot_csv_row_count_mismatch:{len(csv_rows)}!={expected_row_count}"
        )
    row_case_ids = {str(row.get("case_id") or "") for row in csv_rows}
    execution_case_ids = {
        str(item.get("case_id") or "") for item in execution.get("cases") or []
    }
    if row_case_ids != execution_case_ids:
        raise RuntimeError("result_snapshot_csv_case_identity_mismatch")

    execution_sha256 = _sha256_bytes(contents["execution_json"])
    result_snapshot_id = execution_sha256
    frozen_paths = {
        "execution_json": output_root
        / f"runs/frozen_public_docking_benchmark_execution_{result_snapshot_id}.json",
        "execution_csv": output_root
        / f"runs/frozen_public_docking_benchmark_execution_{result_snapshot_id}.csv",
        "execution_md": output_root
        / f"runs/frozen_public_docking_benchmark_execution_{result_snapshot_id}.md",
        "metrics_json": output_root
        / f"config/frozen_public_docking_benchmark_metrics_{result_snapshot_id}.json",
    }
    timestamp = frozen_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    manifest_path = (
        output_root
        / f"runs/frozen_public_docking_benchmark_result_manifest_{result_snapshot_id}.json"
    )

    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name, path in frozen_paths.items():
            if not path.is_file():
                raise RuntimeError(f"frozen_result_artifact_missing:{name}")
            actual = _sha256_bytes(path.read_bytes())
            expected = str((manifest.get("artifacts") or {}).get(name, {}).get("sha256") or "")
            if actual != expected:
                raise RuntimeError(f"frozen_result_artifact_hash_mismatch:{name}")
        return manifest

    for name, path in frozen_paths.items():
        _write_immutable(path, contents[name])
    artifacts = {
        name: {
            "path": _relative(path, output_root),
            "sha256": _sha256_bytes(contents[name]),
            "bytes": len(contents[name]),
        }
        for name, path in frozen_paths.items()
    }
    manifest = {
        "schema_version": "frozen_public_docking_benchmark_result_manifest_v1",
        "status": "frozen_public_docking_benchmark_subject_result_ready",
        "ready": True,
        "result_snapshot_id": result_snapshot_id,
        "frozen_at_utc": timestamp,
        "case_set_hash": case_set_hash,
        "case_count": case_count,
        "primary_engine_surface": summary.get("primary_engine_surface"),
        "candidate_budget": summary.get("candidate_budget"),
        "refinement_max_steps": summary.get("refinement_max_steps"),
        "benchmark_reportable": False,
        "paired_baseline_delta_present": bool(metrics.get("paired_baseline_deltas")),
        "immutable": True,
        "synthetic_metrics_used": bool(metrics.get("synthetic_metrics_used", False)),
        "external_state_mutated": False,
        "artifacts": artifacts,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    _write_immutable(
        manifest_path,
        (
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        ).encode("utf-8"),
    )
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze completed public docking benchmark result artifacts."
    )
    parser.add_argument("--execution-json", default=DEFAULT_EXECUTION_JSON)
    parser.add_argument("--execution-csv", default=DEFAULT_EXECUTION_CSV)
    parser.add_argument("--execution-md", default=DEFAULT_EXECUTION_MD)
    parser.add_argument("--metrics-json", default=DEFAULT_METRICS_JSON)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = freeze_public_docking_benchmark_results(
        execution_json=args.execution_json,
        execution_csv=args.execution_csv,
        execution_md=args.execution_md,
        metrics_json=args.metrics_json,
    )
    if not args.quiet:
        print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
