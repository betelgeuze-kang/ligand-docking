from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.public_benchmark import BENCHMARK_SUITES

CLAIM_BOUNDARY = (
    "Public benchmark materialization manifest only; it records whether local benchmark source and result artifacts "
    "exist for a suite. It does not download datasets, extract archives, run docking, compute metrics, register servers, "
    "submit predictions, send email, or mutate external state outside requested output artifacts."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _suite_by_id(suite_id: str) -> dict[str, Any] | None:
    wanted = _text(suite_id)
    return next((suite for suite in BENCHMARK_SUITES if _text(suite.get("suite_id")) == wanted), None)


def _row_count(path: Path) -> int:
    if not path.exists() or path.is_dir():
        return 0
    if path.suffix.lower() != ".csv":
        return 1
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def build_public_benchmark_materialization_manifest(
    *,
    suite_id: str,
    dataset_artifact: str | Path,
    result_artifact: str | Path,
    min_result_rows: int = 1,
) -> dict[str, Any]:
    suite = _suite_by_id(suite_id)
    blockers: list[str] = []
    if suite is None:
        blockers.append("suite_id_unknown")
        family = ""
        source_url = ""
    else:
        family = _text(suite["benchmark_family"])
        source_url = _text(suite["dataset_source_url"])

    dataset = Path(dataset_artifact)
    result = Path(result_artifact)
    dataset_present = dataset.exists()
    result_present = result.exists()
    result_rows = _row_count(result)
    if not dataset_present:
        blockers.append("dataset_artifact_missing")
    if not result_present:
        blockers.append("result_artifact_missing")
    if result_rows < int(min_result_rows):
        blockers.append("result_rows_below_minimum")

    materialized = dataset_present and result_present and result_rows >= int(min_result_rows) and not blockers
    summary = {
        "packet_type": "public_benchmark_materialization_manifest",
        "suite_id": _text(suite_id),
        "status": "public_benchmark_materialization_ready" if materialized else "blocked_public_benchmark_materialization",
        "materialized": materialized,
        "blocker_count": len(sorted(set(blockers))),
        "blockers": sorted(set(blockers)),
        "benchmark_family": family,
        "dataset_source_url": source_url,
        "dataset_artifact": str(dataset),
        "dataset_artifact_present": dataset_present,
        "result_artifact": str(result),
        "result_artifact_present": result_present,
        "result_row_count": result_rows,
        "min_result_rows": int(min_result_rows),
        "external_state_mutated": False,
        "download_executed": False,
        "docking_results_emitted": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Build the suite scorecard from this materialized benchmark evidence."
            if materialized
            else "Place local benchmark source and result artifacts, then rebuild this manifest."
        ),
    }
    rows = [
        {
            "check": "dataset_artifact_present",
            "status": "pass" if dataset_present else "fail",
            "observed": str(dataset),
            "required": source_url,
        },
        {
            "check": "result_artifact_present",
            "status": "pass" if result_present else "fail",
            "observed": str(result),
            "required": "operator-generated benchmark result artifact",
        },
        {
            "check": "result_rows_minimum",
            "status": "pass" if result_rows >= int(min_result_rows) else "fail",
            "observed": str(result_rows),
            "required": str(int(min_result_rows)),
        },
    ]
    return {"summary": summary, "rows": rows}


def write_manifest(path: str | Path, payload: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
