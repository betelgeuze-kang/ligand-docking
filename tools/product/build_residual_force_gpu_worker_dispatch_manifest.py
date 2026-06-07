#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HANDOFF_JSON = "runs/residual_force_gpu_worker_handoff_package_current.json"
DEFAULT_OUT_JSON = "runs/residual_force_gpu_worker_dispatch_manifest_current.json"
DEFAULT_OUT_CSV = "runs/residual_force_gpu_worker_dispatch_manifest_current.csv"
DEFAULT_OUT_MD = "runs/residual_force_gpu_worker_dispatch_manifest_current.md"

CLAIM_BOUNDARY = (
    "Residual force GPU worker dispatch manifest only; verifies local handoff inputs and describes worker execution "
    "and return expectations. It does not run GPU jobs, regenerate trajectories, create force labels, train models, "
    "promote checkpoints, upload, submit, email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_local_file_artifact(value: str) -> bool:
    if not value or " " in value:
        return False
    return value.startswith(("runs/", "tools/", "data/", "config/")) or Path(value).is_absolute()


def _artifact_row(artifact: str, *, role: str) -> dict[str, Any]:
    is_local = _is_local_file_artifact(artifact)
    path = _resolve(artifact) if is_local else Path(artifact)
    exists = bool(is_local and path.exists())
    is_file = bool(exists and path.is_file())
    return {
        "artifact": artifact,
        "role": role,
        "local_file_reference": is_local,
        "exists_now": exists,
        "is_file": is_file,
        "sha256": _sha256(path) if is_file else "",
        "dispatch_blocker": bool(is_local and not exists),
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _native_pdb_rows(queue_csv: str) -> list[dict[str, Any]]:
    path = _resolve(queue_csv)
    if not path.exists() or not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            native_paths = sorted({_text(row.get("native_pdb_path")) for row in reader if _text(row.get("native_pdb_path"))})
    except OSError:
        return []
    return [_artifact_row(native_path, role="native_pdb_dependency") for native_path in native_paths]


def build_payload(*, handoff_package: dict[str, Any], handoff_path: str = DEFAULT_HANDOFF_JSON) -> dict[str, Any]:
    handoff = _summary(handoff_package)
    handoff_ready = handoff.get("gpu_worker_handoff_ready") is True
    outbound = [_text(item) for item in _list(handoff.get("operator_transfer_outbound_artifacts")) if _text(item)]
    inbound = [_text(item) for item in _list(handoff.get("operator_transfer_inbound_artifacts")) if _text(item)]
    rows = [_artifact_row(handoff_path, role="dispatch_source")]
    rows.extend(_artifact_row(artifact, role="outbound_to_gpu_worker") for artifact in outbound)
    rows.extend(_native_pdb_rows(_text(handoff.get("queue_csv"))))
    local_rows = [row for row in rows if row["local_file_reference"]]
    missing_rows = [row for row in local_rows if not row["exists_now"]]
    native_rows = [row for row in rows if row["role"] == "native_pdb_dependency"]
    native_missing = [row for row in native_rows if not row["exists_now"]]
    dispatch_ready = bool(handoff_ready and local_rows and not missing_rows)
    acceptance = {
        "return_receipt_artifact": _text(handoff.get("operator_transfer_acceptance_artifact")),
        "return_receipt_ready_key": _text(handoff.get("operator_transfer_acceptance_ready_key")),
        "first_return_artifact": _text(handoff.get("operator_transfer_first_return_artifact")),
        "return_manifest_artifact": _text(handoff.get("operator_transfer_return_manifest_artifact")),
        "worker_rocm_manifest_completion_rule": _text(handoff.get("worker_rocm_manifest_completion_rule")),
        "post_return_validation_command": _text(handoff.get("operator_transfer_post_return_validation_command")),
        "inbound_artifacts": inbound,
    }
    summary = {
        "packet_type": "residual_force_gpu_worker_dispatch_manifest",
        "status": (
            "residual_force_gpu_worker_dispatch_manifest_ready"
            if dispatch_ready
            else "blocked_residual_force_gpu_worker_dispatch_manifest"
        ),
        "dispatch_manifest_ready": dispatch_ready,
        "handoff_package_ready": handoff_ready,
        "handoff_package_artifact": handoff_path,
        "queue_rows": int(handoff.get("queue_rows") or 0),
        "queue_csv": _text(handoff.get("queue_csv")),
        "queue_csv_sha256": _text(handoff.get("queue_csv_sha256")),
        "outbound_artifact_count": len(outbound),
        "inbound_artifact_count": len(inbound),
        "local_artifact_reference_count": len(local_rows),
        "local_artifact_present_count": len(local_rows) - len(missing_rows),
        "local_artifact_missing_count": len(missing_rows),
        "local_artifact_missing": [row["artifact"] for row in missing_rows],
        "native_pdb_dependency_count": len(native_rows),
        "native_pdb_missing_count": len(native_missing),
        "native_pdb_missing": [row["artifact"] for row in native_missing],
        "tiny_pilot_command": _text(handoff.get("tiny_pilot_command")),
        "full_regeneration_command": _text(handoff.get("full_regeneration_command")),
        "post_run_validation_commands": _list(handoff.get("post_run_validation_commands")),
        "post_run_validation_command_count": int(handoff.get("post_run_validation_command_count") or 0),
        "acceptance_contract": acceptance,
        "return_summary_completion_rule": _text(handoff.get("return_summary_completion_rule")),
        "return_manifest_required_identity_rule": _text(handoff.get("return_manifest_required_identity_rule")),
        "worker_rocm_manifest_completion_rule": _text(handoff.get("worker_rocm_manifest_completion_rule")),
        "next_required_step": (
            "Send the listed local artifacts plus native PDB dependencies to a GPU-equipped worker, run the tiny pilot, "
            "run the full regeneration command, return the inbound artifacts, then run the post-return validation command."
            if dispatch_ready
            else "Repair missing local dispatch artifacts before sending the GPU worker handoff."
        ),
        "execution_enabled": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows, "blockers": missing_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    s = payload["summary"]
    lines = [
        "# Residual Force GPU Worker Dispatch Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- dispatch_manifest_ready: `{s['dispatch_manifest_ready']}`",
        f"- handoff_package_ready: `{s['handoff_package_ready']}`",
        f"- queue_rows: `{s['queue_rows']}`",
        f"- outbound_artifact_count: `{s['outbound_artifact_count']}`",
        f"- inbound_artifact_count: `{s['inbound_artifact_count']}`",
        f"- local_artifact_missing_count: `{s['local_artifact_missing_count']}`",
        f"- native_pdb_dependency_count: `{s['native_pdb_dependency_count']}`",
        f"- native_pdb_missing_count: `{s['native_pdb_missing_count']}`",
        "",
        "## Tiny Pilot",
        "",
        "```bash",
        s["tiny_pilot_command"],
        "```",
        "",
        "## Full Regeneration",
        "",
        "```bash",
        s["full_regeneration_command"],
        "```",
        "",
        "## Acceptance Contract",
        "",
        f"- return receipt: `{s['acceptance_contract']['return_receipt_artifact']}`",
        f"- ready key: `{s['acceptance_contract']['return_receipt_ready_key']}`",
        f"- worker ROCm rule: `{s['worker_rocm_manifest_completion_rule']}`",
        "",
        "## Claim Boundary",
        "",
        s["claim_boundary"],
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a dispatch manifest for the residual-force GPU worker handoff.")
    parser.add_argument("--handoff-json", default=DEFAULT_HANDOFF_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(handoff_package=_read_json(args.handoff_json), handoff_path=args.handoff_json)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
