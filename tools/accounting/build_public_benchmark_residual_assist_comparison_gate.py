#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_BENCHMARK_JSON = "runs/product_public_benchmark_contract_current.json"
DEFAULT_OUT_JSON = "runs/public_benchmark_residual_assist_comparison_gate_current.json"
DEFAULT_OUT_CSV = "runs/public_benchmark_residual_assist_comparison_gate_current.csv"
DEFAULT_OUT_MD = "runs/public_benchmark_residual_assist_comparison_gate_current.md"

CLAIM_BOUNDARY = (
    "Public benchmark residual assist comparison gate only; audits existing local per-suite raw/shadow/assist "
    "comparison artifacts. It does not run docking, recompute benchmark metrics, train models, promote assist/"
    "production mode, upload, submit, email, archive, externalize, or delete files."
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
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows", [])
    return [dict(row) for row in rows] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _comparison_path_for_suite(suite_id: str) -> str:
    return f"runs/{suite_id}_residual_assist_comparison_current.json"


def _suite_row(suite: dict[str, Any], comparison_packet: dict[str, Any], comparison_path: str) -> dict[str, Any]:
    suite_id = _text(suite.get("suite_id"))
    comparison = _summary(comparison_packet)
    present = bool(comparison_packet)
    baseline_ready = _text(suite.get("status")) == "ready" and suite.get("scorecard_json_present") is True
    assist_ready = comparison.get("assist_comparison_ready") is True or comparison.get("comparison_ready") is True
    pass_to_fail = int(comparison.get("pass_to_fail_regression_count") or 0)
    metric_regression = int(comparison.get("metric_regression_count") or 0)
    throughput_loss = _float(comparison.get("throughput_loss_fraction"))
    status = "pass" if baseline_ready and present and assist_ready and pass_to_fail == 0 and metric_regression == 0 and throughput_loss <= 0.10 else "fail"
    reason = (
        "per-suite assist comparison is present and has no pass-to-fail, metric, or throughput regression"
        if status == "pass"
        else "missing assist comparison artifact or assist comparison has a regression"
    )
    return {
        "suite_id": suite_id,
        "benchmark_family": _text(suite.get("benchmark_family")),
        "baseline_status": _text(suite.get("status")),
        "baseline_scorecard_json": _text(suite.get("scorecard_json")),
        "assist_comparison_json": comparison_path,
        "assist_comparison_present": present,
        "assist_comparison_ready": assist_ready,
        "pass_to_fail_regression_count": pass_to_fail,
        "metric_regression_count": metric_regression,
        "throughput_loss_fraction": throughput_loss,
        "status": status,
        "release_blocker": status != "pass",
        "reason": reason,
        "next_required_step": (
            "No action needed for this suite."
            if status == "pass"
            else f"Generate raw/shadow/assist comparison artifact: {comparison_path}"
        ),
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
    }


def build_public_benchmark_residual_assist_comparison_gate(
    *,
    public_benchmark_packet: dict[str, Any],
    comparison_packets_by_suite: dict[str, dict[str, Any]] | None = None,
    public_benchmark_path: str = DEFAULT_PUBLIC_BENCHMARK_JSON,
) -> dict[str, Any]:
    public = _summary(public_benchmark_packet)
    comparison_packets_by_suite = comparison_packets_by_suite or {}
    suites = [row for row in _rows(public_benchmark_packet) if row.get("required_for_commercial_release") is True or _text(row.get("status")) == "ready"]
    rows = []
    for suite in suites:
        suite_id = _text(suite.get("suite_id"))
        comparison_path = _comparison_path_for_suite(suite_id)
        rows.append(_suite_row(suite, comparison_packets_by_suite.get(suite_id, {}), comparison_path))
    required_suite_count = int(public.get("required_suite_count") or len(suites))
    pass_rows = [row for row in rows if row["status"] == "pass"]
    fail_rows = [row for row in rows if row["status"] != "pass"]
    gate_ready = bool(
        _text(public.get("status")) == "product_public_benchmark_contract_ready"
        and public.get("public_benchmark_validation_ready") is True
        and required_suite_count == 5
        and len(pass_rows) == required_suite_count
        and not fail_rows
    )
    summary = {
        "packet_type": "public_benchmark_residual_assist_comparison_gate",
        "status": "public_benchmark_residual_assist_comparison_gate_ready" if gate_ready else "blocked_public_benchmark_residual_assist_comparison_gate",
        "assist_comparison_gate_ready": gate_ready,
        "assist_promotion_allowed": gate_ready,
        "production_promotion_allowed": False,
        "public_benchmark_artifact": public_benchmark_path,
        "required_suite_count": required_suite_count,
        "suite_count": len(rows),
        "pass_suite_count": len(pass_rows),
        "fail_suite_count": len(fail_rows),
        "missing_assist_comparison_count": sum(1 for row in rows if not row["assist_comparison_present"]),
        "pass_to_fail_regression_count": sum(int(row["pass_to_fail_regression_count"]) for row in rows),
        "metric_regression_count": sum(int(row["metric_regression_count"]) for row in rows),
        "failed_suite_ids": [row["suite_id"] for row in fail_rows],
        "execution_enabled": False,
        "benchmark_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use this gate as public benchmark assist evidence for residual assist promotion."
            if gate_ready
            else "Generate raw/shadow/assist comparison artifacts for all required public benchmark suites."
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
        "# Public Benchmark Residual Assist Comparison Gate",
        "",
        f"- status: `{s['status']}`",
        f"- assist_comparison_gate_ready: `{s['assist_comparison_gate_ready']}`",
        f"- pass_suite_count: `{s['pass_suite_count']}` / `{s['required_suite_count']}`",
        f"- missing_assist_comparison_count: `{s['missing_assist_comparison_count']}`",
        f"- pass_to_fail_regression_count: `{s['pass_to_fail_regression_count']}`",
        f"- metric_regression_count: `{s['metric_regression_count']}`",
        "",
        "## Suites",
        "",
        "| suite | status | comparison present | pass->fail | metric regressions | next step |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['suite_id']}` | `{row['status']}` | `{row['assist_comparison_present']}` | "
            f"`{row['pass_to_fail_regression_count']}` | `{row['metric_regression_count']}` | {row['next_required_step']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build public benchmark residual assist comparison gate from local artifacts.")
    parser.add_argument("--public-benchmark-json", default=DEFAULT_PUBLIC_BENCHMARK_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    public_packet = _read_json_if_present(args.public_benchmark_json)
    comparison_packets: dict[str, dict[str, Any]] = {}
    for suite in _rows(public_packet):
        suite_id = _text(suite.get("suite_id"))
        if suite_id:
            comparison_packets[suite_id] = _read_json_if_present(_comparison_path_for_suite(suite_id))
    payload = build_public_benchmark_residual_assist_comparison_gate(
        public_benchmark_packet=public_packet,
        comparison_packets_by_suite=comparison_packets,
        public_benchmark_path=args.public_benchmark_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
