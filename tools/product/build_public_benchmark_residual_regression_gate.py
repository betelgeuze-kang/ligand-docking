#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PUBLIC_BENCHMARK_JSON = "runs/product_public_benchmark_contract_current.json"
DEFAULT_RESIDUAL_SHADOW_AB_JSON = "runs/residual_shadow_ab_current.json"
DEFAULT_OUT_JSON = "runs/public_benchmark_residual_regression_gate_current.json"
DEFAULT_OUT_CSV = "runs/public_benchmark_residual_regression_gate_current.csv"
DEFAULT_OUT_MD = "runs/public_benchmark_residual_regression_gate_current.md"

CLAIM_BOUNDARY = (
    "Public benchmark residual regression gate only; verifies that residual_mode=shadow does not mutate "
    "customer-facing ranking across the ready public benchmark suites. It does not run docking, recompute benchmark "
    "metrics, train models, promote assist/production mode, upload, submit, email, archive, externalize, or delete files. "
    "Assist/production regression still requires explicit per-suite residual comparison evidence."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _suite_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows", [])
    return [dict(row) for row in rows] if isinstance(rows, list) else []


def _gate_row(suite_row: dict[str, Any], *, residual_shadow_ready: bool, no_ranking_change: bool) -> dict[str, Any]:
    suite_ready = _text(suite_row.get("status")) == "ready"
    scorecard_present = bool(suite_row.get("scorecard_json_present") is True)
    residual_mode = "shadow"
    pass_to_fail_regression = False if residual_shadow_ready and no_ranking_change and suite_ready else True
    status = "pass" if not pass_to_fail_regression and scorecard_present else "fail"
    return {
        "suite_id": _text(suite_row.get("suite_id")),
        "benchmark_family": _text(suite_row.get("benchmark_family")),
        "baseline_suite_status": _text(suite_row.get("status")),
        "scorecard_json": _text(suite_row.get("scorecard_json")),
        "scorecard_json_present": scorecard_present,
        "primary_metric": _text(suite_row.get("primary_metric")),
        "primary_metric_value": suite_row.get("primary_metric_value"),
        "primary_metric_threshold": suite_row.get("primary_metric_threshold"),
        "residual_mode": residual_mode,
        "customer_facing_ranking_changed": not no_ranking_change,
        "pass_to_fail_regression": pass_to_fail_regression,
        "status": status,
        "release_blocker": status != "pass",
        "reason": (
            "shadow mode records residual telemetry without mutating customer-facing ranking, so baseline pass/fail is preserved"
            if status == "pass"
            else "baseline suite is not ready, scorecard is missing, or residual shadow no-mutation policy is not proven"
        ),
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
    }


def build_public_benchmark_residual_regression_gate(
    *,
    public_benchmark_packet: dict[str, Any],
    residual_shadow_packet: dict[str, Any],
    public_benchmark_path: str = DEFAULT_PUBLIC_BENCHMARK_JSON,
    residual_shadow_path: str = DEFAULT_RESIDUAL_SHADOW_AB_JSON,
) -> dict[str, Any]:
    public_summary = _summary(public_benchmark_packet)
    residual_summary = _summary(residual_shadow_packet)
    public_ready = (
        _text(public_summary.get("status")) == "product_public_benchmark_contract_ready"
        and public_summary.get("public_benchmark_validation_ready") is True
    )
    residual_shadow_ready = (
        _text(residual_summary.get("status")) == "residual_shadow_ab_scaffold_ready"
        and residual_summary.get("scaffold_ready") is True
    )
    no_ranking_change = bool(residual_summary.get("no_customer_facing_ranking_change") is True)
    rows = [
        _gate_row(row, residual_shadow_ready=residual_shadow_ready, no_ranking_change=no_ranking_change)
        for row in _suite_rows(public_benchmark_packet)
    ]
    required_suite_count = int(public_summary.get("required_suite_count") or 0)
    ready_required_suite_count = int(public_summary.get("ready_required_suite_count") or 0)
    pass_rows = [row for row in rows if row["status"] == "pass"]
    fail_rows = [row for row in rows if row["status"] != "pass"]
    gate_ready = bool(
        public_ready
        and residual_shadow_ready
        and no_ranking_change
        and required_suite_count == 5
        and ready_required_suite_count == required_suite_count
        and len(pass_rows) == required_suite_count
        and not fail_rows
    )
    summary = {
        "packet_type": "public_benchmark_residual_regression_gate",
        "status": "public_benchmark_residual_regression_gate_ready" if gate_ready else "blocked_public_benchmark_residual_regression_gate",
        "public_benchmark_residual_regression_gate_ready": gate_ready,
        "regression_gate_ready": gate_ready,
        "public_benchmark_artifact": public_benchmark_path,
        "residual_shadow_artifact": residual_shadow_path,
        "public_benchmark_ready": public_ready,
        "residual_shadow_ready": residual_shadow_ready,
        "residual_mode": "shadow",
        "no_customer_facing_ranking_change": no_ranking_change,
        "required_suite_count": required_suite_count,
        "ready_required_suite_count": ready_required_suite_count,
        "suite_count": len(rows),
        "pass_suite_count": len(pass_rows),
        "fail_suite_count": len(fail_rows),
        "pass_to_fail_regression_count": sum(1 for row in rows if row["pass_to_fail_regression"]),
        "assist_promotion_allowed": False,
        "production_promotion_allowed": False,
        "execution_enabled": False,
        "benchmark_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Proceed to AMD Workstation/Server packaging."
            if gate_ready
            else "Repair public benchmark contract or residual shadow no-mutation evidence before packaging."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Public Benchmark Residual Regression Gate",
        "",
        f"- status: `{s['status']}`",
        f"- regression_gate_ready: `{s['regression_gate_ready']}`",
        f"- residual_mode: `{s['residual_mode']}`",
        f"- no_customer_facing_ranking_change: `{s['no_customer_facing_ranking_change']}`",
        f"- required_suite_count: `{s['required_suite_count']}`",
        f"- pass_suite_count: `{s['pass_suite_count']}`",
        f"- fail_suite_count: `{s['fail_suite_count']}`",
        f"- pass_to_fail_regression_count: `{s['pass_to_fail_regression_count']}`",
        f"- assist_promotion_allowed: `{s['assist_promotion_allowed']}`",
        f"- production_promotion_allowed: `{s['production_promotion_allowed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Suites",
        "",
        "| suite | status | mode | metric | value | threshold | pass->fail | reason |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['suite_id']}` | `{row['status']}` | `{row['residual_mode']}` | `{row['primary_metric']}` | "
            f"`{row['primary_metric_value']}` | `{row['primary_metric_threshold']}` | `{row['pass_to_fail_regression']}` | {row['reason']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build public benchmark residual regression gate for residual shadow mode.")
    parser.add_argument("--public-benchmark-json", default=DEFAULT_PUBLIC_BENCHMARK_JSON)
    parser.add_argument("--residual-shadow-json", default=DEFAULT_RESIDUAL_SHADOW_AB_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_public_benchmark_residual_regression_gate(
        public_benchmark_packet=_read_json_if_present(args.public_benchmark_json),
        residual_shadow_packet=_read_json_if_present(args.residual_shadow_json),
        public_benchmark_path=args.public_benchmark_json,
        residual_shadow_path=args.residual_shadow_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
