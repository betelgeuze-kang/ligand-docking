#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROCM_MANIFEST_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_MEASUREMENT_JSON = "runs/amd_hardware_throughput_measurements_current.json"
DEFAULT_OUT_JSON = "runs/amd_hardware_throughput_scorecard_current.json"
DEFAULT_OUT_CSV = "runs/amd_hardware_throughput_scorecard_current.csv"
DEFAULT_OUT_MD = "runs/amd_hardware_throughput_scorecard_current.md"

CLAIM_BOUNDARY = (
    "AMD hardware throughput scorecard only; evaluates existing local ROCm/HIP measurement evidence. "
    "It does not run benchmarks, docking, model training, package installs, uploads, submissions, email, archive, "
    "externalize, or delete files."
)

REQUIRED_METRICS = (
    ("ligands_per_hour", "ligands/hour", ">0"),
    ("poses_per_sec", "poses/sec", ">0"),
    ("score_evaluations_per_sec", "score evaluations/sec", ">0"),
    ("vram_gb_per_1k_ligands", "VRAM GB per 1k ligands", ">0"),
    ("cpu_vs_rocm_speedup", "CPU vs ROCm speedup", ">0"),
    ("failure_rate", "failure rate", "<=0.05"),
    ("fixed_seed_reproducible", "fixed seed reproducibility", "true"),
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


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric_passed(metric_id: str, value: Any) -> bool:
    if metric_id == "fixed_seed_reproducible":
        return value is True
    numeric = _float_or_none(value)
    if numeric is None:
        return False
    if metric_id == "failure_rate":
        return numeric <= 0.05
    return numeric > 0


def _metric_row(
    *,
    metric_id: str,
    metric_label: str,
    value: Any,
    required: str,
    source_artifact: str,
    reason: str,
) -> dict[str, Any]:
    passed = _metric_passed(metric_id, value)
    return {
        "metric_id": metric_id,
        "metric_label": metric_label,
        "status": "pass" if passed else "fail",
        "observed": "" if value is None else str(value),
        "required": required,
        "source_artifact": source_artifact,
        "reason": reason,
        "release_blocker": not passed,
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
    }


def build_amd_hardware_throughput_scorecard(
    *,
    rocm_manifest_packet: dict[str, Any],
    measurement_packet: dict[str, Any] | None = None,
    rocm_manifest_path: str = DEFAULT_ROCM_MANIFEST_JSON,
    measurement_path: str = DEFAULT_MEASUREMENT_JSON,
) -> dict[str, Any]:
    rocm = _summary(rocm_manifest_packet)
    measurements = _summary(measurement_packet or {})
    rocm_ready = _text(rocm.get("status")) == "rocm_environment_manifest_ready" and rocm.get("manifest_ready") is True
    measurement_present = bool(measurements)

    rows: list[dict[str, Any]] = [
        {
            "metric_id": "rocm_environment_manifest_ready",
            "metric_label": "ROCm environment manifest",
            "status": "pass" if rocm_ready else "fail",
            "observed": _text(rocm.get("status")) or "missing",
            "required": "rocm_environment_manifest_ready",
            "source_artifact": rocm_manifest_path,
            "reason": "AMD hardware throughput claims require a ready ROCm/HIP environment manifest.",
            "release_blocker": not rocm_ready,
            "execution_enabled": False,
            "benchmark_executed": False,
            "external_state_mutated": False,
        }
    ]
    for metric_id, label, required in REQUIRED_METRICS:
        rows.append(
            _metric_row(
                metric_id=metric_id,
                metric_label=label,
                value=measurements.get(metric_id),
                required=required,
                source_artifact=measurement_path,
                reason=f"AMD product packaging needs measured {label} evidence.",
            )
        )

    failed = [row for row in rows if row["status"] != "pass"]
    measurement_metric_pass_count = sum(1 for row in rows[1:] if row["status"] == "pass")
    scorecard_ready = bool(rocm_ready and measurement_present and not failed)
    summary = {
        "packet_type": "amd_hardware_throughput_scorecard",
        "status": "amd_hardware_throughput_scorecard_ready" if scorecard_ready else "blocked_amd_hardware_throughput_scorecard",
        "scorecard_ready": scorecard_ready,
        "rocm_environment_manifest_ready": rocm_ready,
        "measurement_artifact_present": measurement_present,
        "metric_count": len(rows),
        "measurement_metric_count": len(REQUIRED_METRICS),
        "measurement_metric_pass_count": measurement_metric_pass_count,
        "fail_count": len(failed),
        "commercial_compute_default": "rocm_hip",
        "cpu_fallback_available": True,
        "rocm_manifest_status": _text(rocm.get("status")),
        "rocm_torch_ready": bool(rocm.get("torch_rocm_ready") is True),
        "visible_device_count": int(rocm.get("visible_device_count") or 0),
        "device_names": list(rocm.get("device_names") or []),
        "ligands_per_hour": measurements.get("ligands_per_hour"),
        "poses_per_sec": measurements.get("poses_per_sec"),
        "score_evaluations_per_sec": measurements.get("score_evaluations_per_sec"),
        "vram_gb_per_1k_ligands": measurements.get("vram_gb_per_1k_ligands"),
        "cpu_vs_rocm_speedup": measurements.get("cpu_vs_rocm_speedup"),
        "failure_rate": measurements.get("failure_rate"),
        "fixed_seed_reproducible": measurements.get("fixed_seed_reproducible"),
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "AMD hardware throughput scorecard is ready for packaging evidence."
            if scorecard_ready
            else "Run or ingest AMD ROCm smoke benchmark measurements, then rebuild this scorecard."
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
        "# AMD Hardware Throughput Scorecard",
        "",
        f"- status: `{s['status']}`",
        f"- scorecard_ready: `{s['scorecard_ready']}`",
        f"- rocm_environment_manifest_ready: `{s['rocm_environment_manifest_ready']}`",
        f"- measurement_artifact_present: `{s['measurement_artifact_present']}`",
        f"- measurement_metric_pass_count: `{s['measurement_metric_pass_count']}`",
        f"- fail_count: `{s['fail_count']}`",
        f"- commercial_compute_default: `{s['commercial_compute_default']}`",
        f"- cpu_fallback_available: `{s['cpu_fallback_available']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- benchmark_executed: `{s['benchmark_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Metrics",
        "",
        "| metric | status | observed | required | reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['metric_id']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` | {row['reason']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AMD ROCm/HIP hardware throughput scorecard from local artifacts.")
    parser.add_argument("--rocm-manifest-json", default=DEFAULT_ROCM_MANIFEST_JSON)
    parser.add_argument("--measurement-json", default=DEFAULT_MEASUREMENT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_amd_hardware_throughput_scorecard(
        rocm_manifest_packet=_read_json_if_present(args.rocm_manifest_json),
        measurement_packet=_read_json_if_present(args.measurement_json),
        rocm_manifest_path=args.rocm_manifest_json,
        measurement_path=args.measurement_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
