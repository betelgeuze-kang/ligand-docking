#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PUBLIC_BENCHMARK_JSON = "runs/product_public_benchmark_contract_current.json"
DEFAULT_SHADOW_JSON = "runs/residual_shadow_ab_current.json"
DEFAULT_OUT_MANIFEST_JSON = "runs/public_benchmark_residual_assist_replays_manifest_current.json"

CLAIM_BOUNDARY = (
    "Public benchmark residual assist replay materialization only; writes per-suite replay artifacts from "
    "existing scorecard baselines and residual shadow no-mutation evidence. It does not run docking, recompute "
    "benchmark metrics, promote assist/production mode, or mutate external state."
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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _scorecard_primary_metric(scorecard_packet: dict[str, Any], metric: str) -> float:
    summary = _summary(scorecard_packet)
    if summary.get("primary_metric_value") is not None:
        return _float(summary.get("primary_metric_value"))
    evaluator = scorecard_packet.get("evaluator")
    if isinstance(evaluator, dict):
        metrics = evaluator.get("metrics")
        if isinstance(metrics, dict):
            for key in (metric, metric.lower(), metric.upper()):
                if key in metrics:
                    return _float(metrics.get(key))
    return 0.0


def build_public_benchmark_residual_assist_replays(
    *,
    public_benchmark_packet: dict[str, Any],
    residual_shadow_packet: dict[str, Any],
) -> dict[str, Any]:
    shadow = _summary(residual_shadow_packet)
    shadow_ready = shadow.get("no_customer_facing_ranking_change") is True
    rows: list[dict[str, Any]] = []
    for suite in public_benchmark_packet.get("rows", []) or []:
        if not isinstance(suite, dict):
            continue
        suite_id = _text(suite.get("suite_id"))
        if not suite_id:
            continue
        metric = _text(suite.get("primary_metric"))
        scorecard = _read_json_if_present(_text(suite.get("scorecard_json")))
        raw_value = _scorecard_primary_metric(scorecard, metric) or _float(suite.get("primary_metric_value"))
        replay_ready = shadow_ready and _text(suite.get("status")) == "ready" and raw_value > 0.0
        payload = {
            "summary": {
                "packet_type": "public_benchmark_residual_assist_replay",
                "status": "public_benchmark_residual_assist_replay_ready" if replay_ready else "blocked_public_benchmark_residual_assist_replay",
                "assist_replay_ready": replay_ready,
                "suite_id": suite_id,
                "primary_metric": metric,
                "raw_primary_metric_value": raw_value,
                "shadow_primary_metric_value": raw_value,
                "assist_primary_metric_value": raw_value,
                "assist_route_decision": "shadow_identity_replay" if replay_ready else "abstain_noop",
                "residual_assist_applied": replay_ready,
                "customer_facing_ranking_changed": False,
                "replay_source": "scorecard_baseline_shadow_no_mutation",
                "source_scorecard_json": _text(suite.get("scorecard_json")),
                "execution_enabled": False,
                "benchmark_executed": False,
                "external_state_mutated": False,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        }
        out_path = _resolve(f"runs/{suite_id}_residual_assist_replay_current.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        rows.append(
            {
                "suite_id": suite_id,
                "status": payload["summary"]["status"],
                "assist_replay_json": str(out_path.relative_to(ROOT)),
                "assist_replay_ready": replay_ready,
                "primary_metric_value": raw_value,
            }
        )
    ready_rows = [row for row in rows if row["assist_replay_ready"]]
    summary = {
        "packet_type": "public_benchmark_residual_assist_replays_manifest",
        "status": "public_benchmark_residual_assist_replays_manifest_ready" if ready_rows else "blocked_public_benchmark_residual_assist_replays_manifest",
        "manifest_ready": bool(ready_rows),
        "suite_count": len(rows),
        "ready_suite_count": len(ready_rows),
        "shadow_no_ranking_change": shadow_ready,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Materialize public benchmark residual assist replay artifacts.")
    parser.add_argument("--public-benchmark-json", default=DEFAULT_PUBLIC_BENCHMARK_JSON)
    parser.add_argument("--residual-shadow-json", default=DEFAULT_SHADOW_JSON)
    parser.add_argument("--out-manifest-json", default=DEFAULT_OUT_MANIFEST_JSON)
    args = parser.parse_args(argv)
    payload = build_public_benchmark_residual_assist_replays(
        public_benchmark_packet=_read_json_if_present(args.public_benchmark_json),
        residual_shadow_packet=_read_json_if_present(args.residual_shadow_json),
    )
    _resolve(args.out_manifest_json).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
