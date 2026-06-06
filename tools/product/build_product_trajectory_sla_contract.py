#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNS_DIR = "runs"
DEFAULT_ROCM_BENCHMARK_JSON = "runs/product_end_to_end_rocm_benchmark_current.json"
DEFAULT_OUT_JSON = "runs/product_trajectory_sla_contract_current.json"
DEFAULT_OUT_CSV = "runs/product_trajectory_sla_contract_current.csv"
DEFAULT_OUT_MD = "runs/product_trajectory_sla_contract_current.md"

REQUIRED_FAMILIES = ["gpcr", "ion_channel", "kinase"]
MIN_READY_ROWS_PER_FAMILY = 10000

CLAIM_BOUNDARY = (
    "Product trajectory SLA contract only; audits existing local SLA and stage2 trajectory summaries for production "
    "trajectory profile evidence across product families. It does not launch docking, rerun trajectories, train models, "
    "promote production mode, upload, submit, email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _infer_family(path: Path, payload: dict[str, Any]) -> str:
    explicit = _text(payload.get("family")).lower()
    if explicit in {"gpcr", "ion_channel", "kinase"}:
        return explicit
    text = path.as_posix().lower()
    if "ion_trpv" in text or "ion_channel" in text or "trpv1" in text:
        return "ion_channel"
    if "kinase" in text:
        return "kinase"
    if "gpcr" in text:
        return "gpcr"
    return "unknown"


def _prod_flags(payload: dict[str, Any], path: Path) -> tuple[bool, bool, bool]:
    traj_prod = payload.get("traj_prod") if isinstance(payload.get("traj_prod"), dict) else {}
    stage2_summary = (
        payload.get("traj_stage2_engine_summary")
        if isinstance(payload.get("traj_stage2_engine_summary"), dict)
        else {}
    )
    requested_prod = (
        traj_prod.get("enabled") is True
        or payload.get("traj_prod_enabled") is True
    )
    engine_prod = (
        payload.get("prod_mode") is True
        or payload.get("traj_stage2_engine_prod_mode") is True
        or stage2_summary.get("prod_mode") is True
    )
    is_stage2_summary = "stage2_traj_summary" in path.name
    production_profile = bool((requested_prod and engine_prod) or (is_stage2_summary and engine_prod))
    return bool(requested_prod), bool(engine_prod), production_profile


def _processed_rows(payload: dict[str, Any]) -> int:
    return max(
        _int(payload.get("processed_rows")),
        _int(payload.get("queue_rows")),
        _int(payload.get("ok_rows")),
    )


def _failure_rate(payload: dict[str, Any], processed_rows: int) -> float:
    explicit = payload.get("gate_failure_rate_proxy")
    if explicit is not None:
        return _float(explicit)
    failed = _int(payload.get("failed_rows") or payload.get("gate_failed_metric_count"))
    return float(failed / processed_rows) if processed_rows else 1.0


def _throughput_rows_per_sec(payload: dict[str, Any], processed_rows: int) -> float:
    explicit = max(_float(payload.get("queue_rate_stage2_rows_per_sec")), _float(payload.get("rows_per_sec")))
    if explicit > 0:
        return explicit
    latency = _float(payload.get("total_latency_sec"))
    return float(processed_rows / latency) if processed_rows and latency > 0 else 0.0


def _candidate_paths(runs_dir: Path) -> list[Path]:
    if not runs_dir.exists():
        return []
    paths = []
    for path in runs_dir.rglob("*.json"):
        if "_by_name" in path.parts:
            continue
        name = path.name.lower()
        if any(token in name for token in ("sla_summary", "stage2_traj_summary", "full_summary", "smoke_state")):
            paths.append(path)
    return sorted(paths)


def _row_for_path(path: Path) -> dict[str, Any]:
    payload = _read_json_if_present(path)
    requested_prod, engine_prod, production_profile = _prod_flags(payload, path)
    processed_rows = _processed_rows(payload)
    failure_rate = _failure_rate(payload, processed_rows)
    throughput = _throughput_rows_per_sec(payload, processed_rows)
    family = _infer_family(path, payload)
    ready = bool(production_profile and processed_rows > 0 and throughput > 0 and failure_rate <= 0.05 and family != "unknown")
    family_sla_qualified = ready and processed_rows >= MIN_READY_ROWS_PER_FAMILY
    blockers: list[str] = []
    if not production_profile:
        blockers.append("production_trajectory_profile_not_enabled")
    if processed_rows <= 0:
        blockers.append("missing_processed_rows")
    if throughput <= 0:
        blockers.append("missing_positive_throughput")
    if failure_rate > 0.05:
        blockers.append("failure_rate_above_0.05")
    if family == "unknown":
        blockers.append("unknown_family")
    if ready and not family_sla_qualified:
        blockers.append("below_minimum_rows_for_family_sla")
    return {
        "source_artifact": str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path),
        "family": family,
        "production_profile_requested": requested_prod,
        "trajectory_engine_prod_mode": engine_prod,
        "production_trajectory_profile_enabled": production_profile,
        "processed_rows": processed_rows,
        "throughput_rows_per_sec": throughput,
        "failure_rate": failure_rate,
        "ready_for_sla": ready,
        "family_sla_qualified": family_sla_qualified,
        "minimum_rows_for_family_sla": MIN_READY_ROWS_PER_FAMILY,
        "blockers": ";".join(blockers),
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
    }


def build_product_trajectory_sla_contract(
    *,
    runs_dir: str = DEFAULT_RUNS_DIR,
    rocm_benchmark_packet: dict[str, Any] | None = None,
    rocm_benchmark_path: str = DEFAULT_ROCM_BENCHMARK_JSON,
) -> dict[str, Any]:
    root = _resolve(runs_dir)
    rows = [_row_for_path(path) for path in _candidate_paths(root)]
    rocm_baseline = (rocm_benchmark_packet or {}).get("summary")
    if not isinstance(rocm_baseline, dict):
        rocm_baseline = rocm_benchmark_packet or _read_json_if_present(_resolve(rocm_benchmark_path)).get("summary", {})
    if not isinstance(rocm_baseline, dict):
        rocm_baseline = {}
    ready_rows = [row for row in rows if row["ready_for_sla"]]
    qualified_rows = [row for row in ready_rows if row["family_sla_qualified"]]
    ready_families = sorted({str(row["family"]) for row in ready_rows})
    qualified_families = sorted({str(row["family"]) for row in qualified_rows})
    missing_families = [family for family in REQUIRED_FAMILIES if family not in set(ready_families)]
    missing_qualified_families = [family for family in REQUIRED_FAMILIES if family not in set(qualified_families)]
    family_sla_matrix = []
    for family in REQUIRED_FAMILIES:
        family_ready_rows = [row for row in ready_rows if row["family"] == family]
        family_qualified_rows = [row for row in qualified_rows if row["family"] == family]
        family_sla_matrix.append(
            {
                "family": family,
                "ready_run_count": len(family_ready_rows),
                "qualified_ready_run_count": len(family_qualified_rows),
                "max_processed_rows": max([row["processed_rows"] for row in family_ready_rows], default=0),
                "min_qualified_throughput_rows_per_sec": min(
                    [row["throughput_rows_per_sec"] for row in family_qualified_rows],
                    default=0.0,
                ),
                "qualified_for_restricted_family_sla": bool(family_qualified_rows),
            }
        )
    profile_ready = bool(qualified_rows and not missing_qualified_families)
    rocm_baseline_ready = _text(rocm_baseline.get("status")) == "product_end_to_end_rocm_benchmark_ready"
    rocm_baseline_production_profile_enabled = rocm_baseline.get("production_trajectory_profile_enabled") is True
    rocm_baseline_family = _text(rocm_baseline.get("family")) or "unknown"
    rocm_baseline_target_id = _text(rocm_baseline.get("target_id"))
    rocm_baseline_warning_count = 0 if rocm_baseline_production_profile_enabled else int(bool(rocm_baseline_ready))
    allowed_sla_claims = []
    if profile_ready:
        allowed_sla_claims.append("restricted_family_trajectory_profile_sla")
    if rocm_baseline_ready:
        allowed_sla_claims.append("single_target_gpcr_rocm_baseline")
    blocked_sla_claims = [
        "broad_platform_sla",
        "general_protein_ligand_platform_sla",
        "current_rocm_baseline_family_sla",
    ]
    if not rocm_baseline_production_profile_enabled:
        blocked_sla_claims.append("current_rocm_baseline_production_trajectory_profile_claim")
    customer_sla_disclosure_card = {
        "sla_claim_tier": "restricted_family_sla" if profile_ready else "blocked_family_sla",
        "allowed_sla_claims": allowed_sla_claims,
        "blocked_sla_claims": blocked_sla_claims,
        "customer_safe_summary": (
            "Restricted-family trajectory-profile SLA evidence is available for gpcr, ion_channel, and kinase. "
            "The current ROCm benchmark remains a single-target GPCR baseline and must not be described as a broad platform SLA."
            if profile_ready
            else "Trajectory SLA evidence is incomplete; do not make production trajectory SLA claims."
        ),
        "current_rocm_baseline_scope": "single_target_gpcr_baseline" if rocm_baseline_ready else "missing",
        "current_rocm_baseline_profile_gap_acknowledged": bool(
            rocm_baseline_ready and not rocm_baseline_production_profile_enabled
        ),
        "restricted_family_sla_allowed": profile_ready,
        "broad_platform_sla_allowed": False,
        "general_platform_sla_allowed": False,
        "minimum_ready_rows_per_family": MIN_READY_ROWS_PER_FAMILY,
        "qualified_ready_families": qualified_families,
        "missing_qualified_families": missing_qualified_families,
    }
    summary = {
        "packet_type": "product_trajectory_sla_contract",
        "status": "product_trajectory_sla_contract_ready" if profile_ready else "blocked_product_trajectory_sla_contract",
        "production_trajectory_sla_ready": profile_ready,
        "candidate_artifact_count": len(rows),
        "ready_run_count": len(ready_rows),
        "qualified_ready_run_count": len(qualified_rows),
        "required_families": REQUIRED_FAMILIES,
        "ready_families": ready_families,
        "qualified_ready_families": qualified_families,
        "missing_families": missing_families,
        "missing_qualified_families": missing_qualified_families,
        "minimum_ready_run_count": len(REQUIRED_FAMILIES),
        "minimum_ready_rows_per_family": MIN_READY_ROWS_PER_FAMILY,
        "family_sla_matrix": family_sla_matrix,
        "current_rocm_baseline_artifact": rocm_benchmark_path,
        "current_rocm_baseline_ready": rocm_baseline_ready,
        "current_rocm_baseline_family": rocm_baseline_family,
        "current_rocm_baseline_target_id": rocm_baseline_target_id,
        "current_rocm_baseline_production_trajectory_profile_enabled": rocm_baseline_production_profile_enabled,
        "current_rocm_baseline_warning_count": rocm_baseline_warning_count,
        "current_rocm_baseline_claim_scope": "single_target_gpcr_baseline" if rocm_baseline_ready else "missing",
        "current_rocm_baseline_supports_restricted_family_sla": False,
        "current_rocm_baseline_supports_broad_platform_sla": False,
        "allowed_sla_claims": allowed_sla_claims,
        "blocked_sla_claims": blocked_sla_claims,
        "customer_sla_disclosure_card": customer_sla_disclosure_card,
        "customer_sla_disclosure_ready": bool(
            allowed_sla_claims and blocked_sla_claims and customer_sla_disclosure_card
        ),
        "general_platform_sla_allowed": False,
        "restricted_sla_backed_by_historical_profile_artifacts": profile_ready,
        "rocm_baseline_profile_gap_acknowledged": bool(rocm_baseline_ready and not rocm_baseline_production_profile_enabled),
        "max_failure_rate": max([row["failure_rate"] for row in ready_rows], default=1.0),
        "min_throughput_rows_per_sec": min([row["throughput_rows_per_sec"] for row in qualified_rows], default=0.0),
        "sla_claim_tier": "restricted_family_sla" if profile_ready else "blocked_family_sla",
        "restricted_family_sla_allowed": profile_ready,
        "broad_platform_sla_allowed": False,
        "single_baseline_only": False if profile_ready else bool(ready_rows),
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use this as restricted-family trajectory-profile SLA evidence only; broad platform SLA claims remain blocked, "
            "and keep the current ROCm baseline scoped as single-target evidence until production trajectory profile is enabled."
            if profile_ready
            else "Attach production trajectory profile runs for each required family with >=10000 rows, throughput, and failure-rate evidence."
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
        "# Product Trajectory SLA Contract",
        "",
        f"- status: `{s['status']}`",
        f"- production_trajectory_sla_ready: `{s['production_trajectory_sla_ready']}`",
        f"- candidate_artifact_count: `{s['candidate_artifact_count']}`",
        f"- ready_run_count: `{s['ready_run_count']}`",
        f"- qualified_ready_run_count: `{s['qualified_ready_run_count']}`",
        f"- ready_families: `{','.join(s['ready_families'])}`",
        f"- qualified_ready_families: `{','.join(s['qualified_ready_families'])}`",
        f"- missing_families: `{','.join(s['missing_families'])}`",
        f"- missing_qualified_families: `{','.join(s['missing_qualified_families'])}`",
        f"- minimum_ready_rows_per_family: `{s['minimum_ready_rows_per_family']}`",
        f"- sla_claim_tier: `{s['sla_claim_tier']}`",
        f"- current_rocm_baseline_artifact: `{s['current_rocm_baseline_artifact']}`",
        f"- current_rocm_baseline_ready: `{s['current_rocm_baseline_ready']}`",
        f"- current_rocm_baseline_family: `{s['current_rocm_baseline_family']}`",
        f"- current_rocm_baseline_target_id: `{s['current_rocm_baseline_target_id']}`",
        f"- current_rocm_baseline_production_trajectory_profile_enabled: `{s['current_rocm_baseline_production_trajectory_profile_enabled']}`",
        f"- current_rocm_baseline_claim_scope: `{s['current_rocm_baseline_claim_scope']}`",
        f"- current_rocm_baseline_supports_restricted_family_sla: `{s['current_rocm_baseline_supports_restricted_family_sla']}`",
        f"- current_rocm_baseline_supports_broad_platform_sla: `{s['current_rocm_baseline_supports_broad_platform_sla']}`",
        f"- customer_sla_disclosure_ready: `{s['customer_sla_disclosure_ready']}`",
        f"- allowed_sla_claims: `{','.join(s['allowed_sla_claims'])}`",
        f"- blocked_sla_claims: `{','.join(s['blocked_sla_claims'])}`",
        f"- restricted_sla_backed_by_historical_profile_artifacts: `{s['restricted_sla_backed_by_historical_profile_artifacts']}`",
        f"- rocm_baseline_profile_gap_acknowledged: `{s['rocm_baseline_profile_gap_acknowledged']}`",
        f"- broad_platform_sla_allowed: `{s['broad_platform_sla_allowed']}`",
        f"- min_throughput_rows_per_sec: `{s['min_throughput_rows_per_sec']}`",
        f"- max_failure_rate: `{s['max_failure_rate']}`",
        "",
        "## Ready Runs",
        "",
        "| artifact | family | rows | rows/sec | failure_rate |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in [item for item in payload["rows"] if item["family_sla_qualified"]][:80]:
        lines.append(
            f"| `{row['source_artifact']}` | `{row['family']}` | `{row['processed_rows']}` | "
            f"`{row['throughput_rows_per_sec']}` | `{row['failure_rate']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build production trajectory SLA contract from local run artifacts.")
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    parser.add_argument("--rocm-benchmark-json", default=DEFAULT_ROCM_BENCHMARK_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_trajectory_sla_contract(
        runs_dir=args.runs_dir,
        rocm_benchmark_packet=_read_json_if_present(_resolve(args.rocm_benchmark_json)),
        rocm_benchmark_path=args.rocm_benchmark_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
