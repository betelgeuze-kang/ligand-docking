#!/usr/bin/env python3
"""Operator intake for the frozen public docking benchmark suite (P1-8).

``betelgeuze_product.frozen_benchmark_suite`` defines what a reportable suite
must contain. This tool is the only way real cases enter it: an operator fills a
CSV of frozen cases plus a metrics JSON, and this builder turns them into the
suite packet and a fail-closed receipt.

Two things it deliberately does NOT do:

- it does not download datasets or fetch structures (the operator supplies
  provenance ids for cases they already hold under an acceptable licence);
- it does not invent, interpolate, or default any metric. A missing metric, a
  missing stratification label, or a baseline delta computed over a subset is
  reported as a blocker, because a partially filled suite reads downstream as a
  complete one.

The receipt is the artifact a reviewer reads: it names every blocker and the
exact next operator action, so "the benchmark is not ready" is always a
specific, actionable statement rather than a status word.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from betelgeuze_product.frozen_benchmark_suite import (  # noqa: E402
    ALLOWED_BASELINE_ENGINES,
    MAX_FROZEN_CASE_COUNT,
    MIN_FROZEN_CASE_COUNT,
    REQUIRED_METRICS,
    REQUIRED_STRATIFICATION_AXES,
    build_frozen_benchmark_suite,
)

DEFAULT_CASES_CSV = "config/frozen_public_docking_benchmark_cases_current.csv"
DEFAULT_METRICS_JSON = "config/frozen_public_docking_benchmark_metrics_current.json"
DEFAULT_OUT_JSON = "runs/frozen_public_docking_benchmark_suite_current.json"
DEFAULT_OUT_CSV = "runs/frozen_public_docking_benchmark_suite_current.csv"
DEFAULT_OUT_MD = "runs/frozen_public_docking_benchmark_suite_current.md"

#: Columns the operator CSV must provide. The stratification axes are required
#: per case, which is what stops an all-easy suite from passing.
CASE_IDENTITY_COLUMNS = ("case_id", "target_id", "ligand_id", "provenance_id")
REQUIRED_CASE_COLUMNS = CASE_IDENTITY_COLUMNS + REQUIRED_STRATIFICATION_AXES

STATUS_READY = "frozen_public_docking_benchmark_suite_intake_ready"
STATUS_BLOCKED = "blocked_frozen_public_docking_benchmark_suite_intake"

CLAIM_BOUNDARY = (
    "Operator intake for the frozen public docking benchmark suite. It validates operator-supplied case rows and "
    "metrics against the frozen-suite contract and emits a fail-closed receipt. It does not download datasets, "
    "fetch structures, run docking, compute metrics, run baselines, or promote a claim."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path)


def _read_cases(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Read the operator case CSV into suite case mappings."""

    blockers: list[str] = []
    if not path.is_file():
        return [], [f"cases_csv_missing:{path.name}"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    missing_columns = [name for name in REQUIRED_CASE_COLUMNS if name not in fieldnames]
    if missing_columns:
        blockers.append("cases_csv_missing_columns:" + ",".join(missing_columns))
    cases: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        blank_identity = [
            name
            for name in CASE_IDENTITY_COLUMNS
            if not str(row.get(name) or "").strip()
        ]
        if blank_identity:
            blockers.append(
                f"case_row_missing_identity:row={index}:" + ",".join(blank_identity)
            )
        cases.append(
            {
                "case_id": str(row.get("case_id") or "").strip(),
                "target_id": str(row.get("target_id") or "").strip(),
                "ligand_id": str(row.get("ligand_id") or "").strip(),
                "provenance_id": str(row.get("provenance_id") or "").strip(),
                "strata": {
                    axis: str(row.get(axis) or "").strip()
                    for axis in REQUIRED_STRATIFICATION_AXES
                    if str(row.get(axis) or "").strip()
                },
            }
        )
    return cases, blockers


def _read_metrics(
    path: Path,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    str,
    str,
    list[str],
]:
    """Read the operator metrics JSON: metrics, intervals, deltas, freeze time."""

    if not path.is_file():
        return {}, [], [], "", "", [f"metrics_json_missing:{path.name}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [], [], "", "", [f"metrics_json_unparseable:{exc.msg}"]
    if not isinstance(payload, dict):
        return {}, [], [], "", "", ["metrics_json_not_an_object"]
    metrics = payload.get("metrics")
    intervals = payload.get("bootstrap_intervals")
    deltas = payload.get("paired_baseline_deltas")
    blockers: list[str] = []
    if not isinstance(metrics, dict):
        metrics = {}
        blockers.append("metrics_json_missing_metrics_object")
    if not isinstance(intervals, list):
        intervals = []
    if not isinstance(deltas, list):
        deltas = []
    # The freeze timestamp is suite identity, not a metric, so it may sit at the
    # payload top level; accept it from either place.
    frozen_at_utc = str(payload.get("frozen_at_utc") or metrics.get("frozen_at_utc") or "").strip()
    case_set_hash = str(payload.get("case_set_hash") or "").strip()
    if metrics and not case_set_hash:
        blockers.append("metrics_case_set_hash_missing")
    return (
        dict(metrics),
        [row for row in intervals if isinstance(row, dict)],
        [row for row in deltas if isinstance(row, dict)],
        frozen_at_utc,
        case_set_hash,
        blockers,
    )


def _next_operator_step(blockers: list[str], case_count: int) -> str:
    """Name the single most useful next action, not a generic status."""

    if not blockers:
        return (
            "Frozen suite intake is complete and internally consistent. It may now be used as the "
            "denominator for a scoped public-benchmark report."
        )
    if any(b.startswith("cases_csv_missing") for b in blockers):
        return (
            f"Create the operator case CSV with columns "
            f"{','.join(REQUIRED_CASE_COLUMNS)} and {MIN_FROZEN_CASE_COUNT}-{MAX_FROZEN_CASE_COUNT} rows."
        )
    if any(b.startswith("case_count_below_minimum") for b in blockers):
        return (
            f"Add frozen cases: {case_count} present, {MIN_FROZEN_CASE_COUNT} required. "
            "Pick cases you already hold under an acceptable licence and record their provenance ids."
        )
    if any(b.startswith("stratification_axis_single_bucket") for b in blockers):
        return (
            "Diversify stratification: at least one axis has a single bucket, so the suite cannot show "
            "whether a result generalizes along that axis."
        )
    if any(b.startswith("required_metric_missing") for b in blockers):
        missing = sorted(
            b.split(":", 1)[1] for b in blockers if b.startswith("required_metric_missing")
        )
        return "Fill the missing required metrics in the metrics JSON: " + ",".join(missing)
    if any(b == "paired_baseline_delta_missing" for b in blockers):
        return (
            "Run an offline baseline ("
            + "/".join(ALLOWED_BASELINE_ENGINES)
            + ") over the same frozen cases and record the paired delta."
        )
    if any(b == "bootstrap_ci_missing" for b in blockers):
        return "Record a bootstrap confidence interval for the reported success rate."
    return "Resolve the reported intake blockers: " + ",".join(blockers[:3])


def build_frozen_benchmark_suite_intake(
    *,
    cases_csv: str | Path = DEFAULT_CASES_CSV,
    metrics_json: str | Path = DEFAULT_METRICS_JSON,
    suite_id: str = "frozen_public_docking_benchmark_v1",
    frozen_at_utc: str = "",
) -> dict[str, Any]:
    """Validate operator intake and emit the suite packet plus receipt."""

    cases_path = _resolve(cases_csv)
    metrics_path = _resolve(metrics_json)
    cases, case_blockers = _read_cases(cases_path)
    (
        metrics,
        intervals,
        deltas,
        metrics_frozen_at,
        metrics_case_set_hash,
        metric_blockers,
    ) = _read_metrics(metrics_path)

    resolved_frozen_at = str(frozen_at_utc or metrics_frozen_at or "").strip()
    suite = build_frozen_benchmark_suite(
        suite_id=str(suite_id),
        frozen_at_utc=resolved_frozen_at,
        cases=cases,
        metrics=metrics,
        bootstrap_intervals=intervals,
        paired_baseline_deltas=deltas,
    )
    suite_payload = suite.to_dict()
    identity_blockers: list[str] = []
    if metrics_case_set_hash and metrics_case_set_hash != suite.case_set_hash:
        identity_blockers.append("metrics_case_set_hash_mismatch")
    if (
        str(frozen_at_utc or "").strip()
        and metrics_frozen_at
        and str(frozen_at_utc).strip() != metrics_frozen_at
    ):
        identity_blockers.append("metrics_frozen_at_utc_mismatch")

    blockers = list(
        dict.fromkeys(
            [
                *case_blockers,
                *metric_blockers,
                *identity_blockers,
                *suite_payload.get("blockers", []),
            ]
        )
    )
    ready = not blockers
    summary: dict[str, Any] = {
        "packet_type": "frozen_public_docking_benchmark_suite_intake",
        "status": STATUS_READY if ready else STATUS_BLOCKED,
        "ready": ready,
        "suite_id": str(suite_id),
        "frozen_at_utc": resolved_frozen_at,
        "cases_csv": str(cases_csv),
        "metrics_json": str(metrics_json),
        "case_count": suite.case_count,
        "case_count_required_min": MIN_FROZEN_CASE_COUNT,
        "case_count_required_max": MAX_FROZEN_CASE_COUNT,
        "case_set_hash": suite.case_set_hash,
        "metrics_case_set_hash": metrics_case_set_hash,
        "metrics_case_set_hash_matches": bool(
            metrics_case_set_hash and metrics_case_set_hash == suite.case_set_hash
        ),
        "required_case_columns": list(REQUIRED_CASE_COLUMNS),
        "required_metrics": list(REQUIRED_METRICS),
        "present_metric_count": sum(1 for m in REQUIRED_METRICS if m in metrics),
        "missing_metric_ids": [m for m in REQUIRED_METRICS if m not in metrics],
        "stratification_coverage": suite_payload["stratification_coverage"],
        "bootstrap_interval_count": len(intervals),
        "paired_baseline_delta_count": len(deltas),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "next_required_step": _next_operator_step(blockers, suite.case_count),
        "datasets_downloaded": False,
        "docking_executed": False,
        "baseline_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    rows = [
        {
            "case_id": case["case_id"],
            "target_id": case["target_id"],
            "ligand_id": case["ligand_id"],
            "provenance_id": case["provenance_id"],
            "missing_stratification_axes": ",".join(
                axis for axis in REQUIRED_STRATIFICATION_AXES if axis not in case["strata"]
            ),
            **{axis: case["strata"].get(axis, "") for axis in REQUIRED_STRATIFICATION_AXES},
        }
        for case in cases
    ]
    return {"summary": summary, "rows": rows, "suite": suite_payload}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary", {})
    lines = [
        "# Frozen Public Docking Benchmark Suite Intake (current)",
        "",
        "Generated packet. Edit the operator CSV/JSON inputs and regenerate; do not hand-edit here.",
        "",
        f"- status: `{summary.get('status')}`",
        f"- suite_id: `{summary.get('suite_id')}`",
        f"- frozen_at_utc: `{summary.get('frozen_at_utc')}`",
        f"- case_count: `{summary.get('case_count')}` "
        f"(required `{summary.get('case_count_required_min')}`-`{summary.get('case_count_required_max')}`)",
        f"- case_set_hash: `{summary.get('case_set_hash')}`",
        f"- present_metric_count: `{summary.get('present_metric_count')}`/"
        f"`{len(summary.get('required_metrics') or [])}`",
        f"- bootstrap_interval_count: `{summary.get('bootstrap_interval_count')}`",
        f"- paired_baseline_delta_count: `{summary.get('paired_baseline_delta_count')}`",
        f"- blocker_count: `{summary.get('blocker_count')}`",
        "",
        "## Stratification Coverage",
        "",
    ]
    coverage = summary.get("stratification_coverage") or {}
    for axis in REQUIRED_STRATIFICATION_AXES:
        buckets = coverage.get(axis) or []
        lines.append(f"- {axis}: `{len(buckets)}` bucket(s) `{','.join(buckets) or 'none'}`")
    lines.extend(["", "## Blockers", ""])
    blockers = summary.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker}`" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Next Required Step",
            "",
            f"{summary.get('next_required_step', '')}",
            "",
            "## Claim Boundary",
            "",
            f"{summary.get('claim_boundary', '')}",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate operator-supplied frozen public docking benchmark intake."
    )
    parser.add_argument("--cases-csv", default=DEFAULT_CASES_CSV)
    parser.add_argument("--metrics-json", default=DEFAULT_METRICS_JSON)
    parser.add_argument("--suite-id", default="frozen_public_docking_benchmark_v1")
    parser.add_argument("--frozen-at-utc", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_frozen_benchmark_suite_intake(
        cases_csv=args.cases_csv,
        metrics_json=args.metrics_json,
        suite_id=args.suite_id,
        frozen_at_utc=args.frozen_at_utc,
    )
    out_json = _resolve(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.out_csv:
        from tools.product.builder_table_utils import write_csv_rows

        write_csv_rows(_resolve(args.out_csv), packet["rows"])
    if args.out_md:
        out_md = _resolve(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(packet), encoding="utf-8")
    summary = packet["summary"]
    if not args.quiet:
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
