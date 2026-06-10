#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PUBLIC_BENCHMARK_JSON = "runs/product_public_benchmark_contract_current.json"
DEFAULT_GPCR_ASSIST_SELECTION_JSON = "runs/gpcr_residual_assist_candidate_selection_current.json"
DEFAULT_OUT_MANIFEST_JSON = "runs/public_benchmark_residual_assist_comparisons_manifest_current.json"
DEFAULT_OUT_MANIFEST_CSV = "runs/public_benchmark_residual_assist_comparisons_manifest_current.csv"
DEFAULT_OUT_MANIFEST_MD = "runs/public_benchmark_residual_assist_comparisons_manifest_current.md"

CLAIM_BOUNDARY = (
    "Public benchmark residual assist comparisons only; writes local per-suite comparison artifacts from existing "
    "baseline scorecards and the current GPCR assist-selection policy. It does not run docking, recompute benchmark "
    "metrics, train models, change rankings, promote assist/production mode, upload, submit, email, archive, "
    "externalize, or delete files. Current public-suite comparisons are abstain/no-op safety evidence unless a "
    "suite-specific assist replay artifact is supplied separately."
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


def _comparison_path(suite_id: str) -> Path:
    return _resolve(f"runs/{suite_id}_residual_assist_comparison_current.json")


def _comparison_csv_path(suite_id: str) -> Path:
    return _resolve(f"runs/{suite_id}_residual_assist_comparison_current.csv")


def _comparison_md_path(suite_id: str) -> Path:
    return _resolve(f"runs/{suite_id}_residual_assist_comparison_current.md")


def _replay_path(suite_id: str) -> Path:
    return _resolve(f"runs/{suite_id}_residual_assist_replay_current.json")


def _comparison_for_suite(suite: dict[str, Any], assist_selection: dict[str, Any]) -> dict[str, Any]:
    suite_id = _text(suite.get("suite_id"))
    metric = _text(suite.get("primary_metric"))
    baseline_value = _float(suite.get("primary_metric_value"))
    threshold = _float(suite.get("primary_metric_threshold") or suite.get("threshold"))
    baseline_pass = _text(suite.get("status")) == "ready" and baseline_value + 1e-12 >= threshold
    replay_packet = _read_json_if_present(_replay_path(suite_id))
    replay = _summary(replay_packet)
    replay_ready = replay.get("assist_replay_ready") is True
    if replay_ready:
        raw_value = _float(replay.get("raw_primary_metric_value", baseline_value))
        shadow_value = _float(replay.get("shadow_primary_metric_value", raw_value))
        assist_value = _float(replay.get("assist_primary_metric_value", shadow_value))
        route_decision = _text(replay.get("assist_route_decision")) or "shadow_identity_replay"
        abstention_reason = ""
        residual_assist_applied = replay.get("residual_assist_applied") is True
    else:
        route_decision = "abstain_noop"
        abstention_reason = "no_suite_specific_public_benchmark_assist_replay_artifact"
        raw_value = baseline_value
        shadow_value = baseline_value
        assist_value = baseline_value
        residual_assist_applied = False
    shadow_pass = baseline_pass
    assist_pass = baseline_pass and assist_value + 1e-12 >= threshold
    pass_to_fail = bool(baseline_pass and not assist_pass)
    metric_regression = bool(assist_value + 1e-12 < raw_value)
    row = {
        "suite_id": suite_id,
        "benchmark_family": _text(suite.get("benchmark_family")),
        "primary_metric": metric,
        "primary_metric_threshold": threshold,
        "raw_primary_metric_value": raw_value,
        "shadow_primary_metric_value": shadow_value,
        "assist_primary_metric_value": assist_value,
        "delta_shadow_vs_raw": shadow_value - raw_value,
        "delta_assist_vs_raw": assist_value - raw_value,
        "baseline_pass": baseline_pass,
        "shadow_pass": shadow_pass,
        "assist_pass": assist_pass,
        "pass_to_fail_regression": pass_to_fail,
        "metric_regression": metric_regression,
        "residual_assist_applied": residual_assist_applied,
        "assist_route_decision": route_decision,
        "abstention_reason": abstention_reason,
        "throughput_loss_fraction": 0.0,
        "source_scorecard_json": _text(suite.get("scorecard_json")),
        "source_regression_baseline_ref": _text(suite.get("regression_baseline_ref")),
        "status": "pass" if baseline_pass and not pass_to_fail and not metric_regression else "fail",
    }
    summary = {
        "packet_type": "public_benchmark_residual_assist_comparison",
        "status": "public_benchmark_residual_assist_comparison_ready" if row["status"] == "pass" else "blocked_public_benchmark_residual_assist_comparison",
        "assist_comparison_ready": row["status"] == "pass",
        "comparison_ready": row["status"] == "pass",
        "suite_id": suite_id,
        "benchmark_family": row["benchmark_family"],
        "primary_metric": metric,
        "primary_metric_threshold": threshold,
        "raw_primary_metric_value": raw_value,
        "shadow_primary_metric_value": shadow_value,
        "assist_primary_metric_value": assist_value,
        "delta_assist_vs_raw": row["delta_assist_vs_raw"],
        "baseline_pass": baseline_pass,
        "assist_pass": assist_pass,
        "pass_to_fail_regression_count": 1 if pass_to_fail else 0,
        "metric_regression_count": 1 if metric_regression else 0,
        "throughput_loss_fraction": 0.0,
        "residual_assist_applied": residual_assist_applied,
        "assist_route_decision": route_decision,
        "abstention_reason": abstention_reason,
        "assist_replay_ready": replay_ready,
        "gpcr_assist_selection_ready": assist_selection.get("assist_candidate_ready") is True,
        "execution_enabled": False,
        "benchmark_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Keep as public no-regression evidence; run suite-specific assist replay before claiming public-suite metric improvement.",
    }
    return {"summary": summary, "rows": [row]}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    row = payload["rows"][0]
    lines = [
        f"# {s['suite_id']} Residual Assist Comparison",
        "",
        f"- status: `{s['status']}`",
        f"- assist_comparison_ready: `{s['assist_comparison_ready']}`",
        f"- assist_route_decision: `{s['assist_route_decision']}`",
        f"- abstention_reason: `{s['abstention_reason']}`",
        f"- primary_metric: `{s['primary_metric']}`",
        f"- raw_primary_metric_value: `{s['raw_primary_metric_value']}`",
        f"- assist_primary_metric_value: `{s['assist_primary_metric_value']}`",
        f"- delta_assist_vs_raw: `{s['delta_assist_vs_raw']}`",
        f"- pass_to_fail_regression_count: `{s['pass_to_fail_regression_count']}`",
        f"- metric_regression_count: `{s['metric_regression_count']}`",
        "",
        "## Row",
        "",
        "| suite | raw | shadow | assist | pass->fail | metric regression | route |",
        "| --- | ---: | ---: | ---: | --- | --- | --- |",
        f"| `{row['suite_id']}` | `{row['raw_primary_metric_value']}` | `{row['shadow_primary_metric_value']}` | `{row['assist_primary_metric_value']}` | `{row['pass_to_fail_regression']}` | `{row['metric_regression']}` | `{row['assist_route_decision']}` |",
        "",
        "## Claim Boundary",
        "",
        s["claim_boundary"],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_public_benchmark_residual_assist_comparisons(
    *,
    public_benchmark_packet: dict[str, Any],
    gpcr_assist_selection_packet: dict[str, Any],
) -> dict[str, Any]:
    public = _summary(public_benchmark_packet)
    assist_selection = _summary(gpcr_assist_selection_packet)
    rows: list[dict[str, Any]] = []
    for suite in _rows(public_benchmark_packet):
        suite_id = _text(suite.get("suite_id"))
        if not suite_id:
            continue
        payload = _comparison_for_suite(suite, assist_selection)
        json_path = _comparison_path(suite_id)
        csv_path = _comparison_csv_path(suite_id)
        md_path = _comparison_md_path(suite_id)
        _write_json(json_path, payload)
        write_csv_rows(csv_path, payload["rows"])
        _write_md(md_path, payload)
        summary = payload["summary"]
        rows.append(
            {
                "suite_id": suite_id,
                "status": summary["status"],
                "assist_comparison_json": str(json_path.relative_to(ROOT)),
                "assist_comparison_csv": str(csv_path.relative_to(ROOT)),
                "assist_comparison_md": str(md_path.relative_to(ROOT)),
                "assist_route_decision": summary["assist_route_decision"],
                "residual_assist_applied": summary.get("residual_assist_applied") is True,
                "assist_replay_ready": summary.get("assist_replay_ready") is True,
                "delta_assist_vs_raw": summary["delta_assist_vs_raw"],
                "pass_to_fail_regression_count": summary["pass_to_fail_regression_count"],
                "metric_regression_count": summary["metric_regression_count"],
                "release_blocker": summary["status"] != "public_benchmark_residual_assist_comparison_ready",
                "execution_enabled": False,
                "benchmark_executed": False,
                "external_state_mutated": False,
            }
        )
    pass_rows = [row for row in rows if not row["release_blocker"]]
    fail_rows = [row for row in rows if row["release_blocker"]]
    required_suite_count = int(public.get("required_suite_count") or 0)
    manifest_ready = bool(required_suite_count == 5 and len(pass_rows) == required_suite_count and not fail_rows)
    summary = {
        "packet_type": "public_benchmark_residual_assist_comparisons_manifest",
        "status": "public_benchmark_residual_assist_comparisons_manifest_ready" if manifest_ready else "blocked_public_benchmark_residual_assist_comparisons_manifest",
        "manifest_ready": manifest_ready,
        "required_suite_count": required_suite_count,
        "suite_count": len(rows),
        "pass_suite_count": len(pass_rows),
        "fail_suite_count": len(fail_rows),
        "assist_applied_suite_count": len([row for row in rows if row.get("residual_assist_applied") is True]),
        "abstain_noop_suite_count": len([row for row in rows if row["assist_route_decision"] == "abstain_noop"]),
        "claim_public_metric_improvement_allowed": len([row for row in rows if row.get("residual_assist_applied") is True and float(row.get("delta_assist_vs_raw") or 0.0) > 1e-12]) > 0,
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Rebuild public benchmark residual assist comparison gate.",
    }
    return {"summary": summary, "rows": rows}


def _write_manifest_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Public Benchmark Residual Assist Comparisons Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- manifest_ready: `{s['manifest_ready']}`",
        f"- pass_suite_count: `{s['pass_suite_count']}` / `{s['required_suite_count']}`",
        f"- assist_applied_suite_count: `{s['assist_applied_suite_count']}`",
        f"- abstain_noop_suite_count: `{s['abstain_noop_suite_count']}`",
        f"- claim_public_metric_improvement_allowed: `{s['claim_public_metric_improvement_allowed']}`",
        "",
        "## Suites",
        "",
        "| suite | status | route | dAssist | artifact |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['suite_id']}` | `{row['status']}` | `{row['assist_route_decision']}` | `{row['delta_assist_vs_raw']}` | `{row['assist_comparison_json']}` |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build per-suite public benchmark residual assist comparison artifacts.")
    parser.add_argument("--public-benchmark-json", default=DEFAULT_PUBLIC_BENCHMARK_JSON)
    parser.add_argument("--gpcr-assist-selection-json", default=DEFAULT_GPCR_ASSIST_SELECTION_JSON)
    parser.add_argument("--out-manifest-json", default=DEFAULT_OUT_MANIFEST_JSON)
    parser.add_argument("--out-manifest-csv", default=DEFAULT_OUT_MANIFEST_CSV)
    parser.add_argument("--out-manifest-md", default=DEFAULT_OUT_MANIFEST_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_public_benchmark_residual_assist_comparisons(
        public_benchmark_packet=_read_json_if_present(args.public_benchmark_json),
        gpcr_assist_selection_packet=_read_json_if_present(args.gpcr_assist_selection_json),
    )
    _write_json(_resolve(args.out_manifest_json), payload)
    write_csv_rows(_resolve(args.out_manifest_csv), payload["rows"])
    _write_manifest_md(args.out_manifest_md, payload)


if __name__ == "__main__":
    main()
