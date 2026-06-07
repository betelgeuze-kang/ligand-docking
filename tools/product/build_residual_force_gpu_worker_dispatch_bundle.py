#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DISPATCH_JSON = "runs/residual_force_gpu_worker_dispatch_manifest_current.json"
DEFAULT_OUT_TAR = "runs/residual_force_gpu_worker_dispatch_bundle_current.tar.gz"
DEFAULT_OUT_JSON = "runs/residual_force_gpu_worker_dispatch_bundle_current.json"
DEFAULT_OUT_CSV = "runs/residual_force_gpu_worker_dispatch_bundle_current.csv"
DEFAULT_OUT_MD = "runs/residual_force_gpu_worker_dispatch_bundle_current.md"

CLAIM_BOUNDARY = (
    "Residual force GPU worker dispatch bundle only; creates a local tar.gz from already-prepared handoff artifacts "
    "for operator transfer. It does not run GPU jobs, regenerate trajectories, upload, submit, email, delete files, "
    "train models, promote checkpoints, or mutate external state."
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


def _rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows")
    return [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _sha256_file(path: Path) -> str:
    import hashlib

    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _arcname(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return f"external_inputs/{_sha256_file(path)[:12]}_{path.name}"


def _bundle_rows(dispatch_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in dispatch_rows:
        if row.get("local_file_reference") is not True or row.get("exists_now") is not True:
            continue
        artifact = _text(row.get("artifact"))
        path = _resolve(artifact)
        if not path.is_file():
            continue
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "artifact": artifact,
                "bundle_arcname": _arcname(path),
                "role": _text(row.get("role")),
                "source_sha256": _sha256_file(path),
                "source_size_bytes": path.stat().st_size,
                "included_in_bundle": True,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )
    return rows


def _write_tar(path_like: str | Path, rows: list[dict[str, Any]]) -> tuple[bool, int, int, str]:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        for row in rows:
            source = _resolve(_text(row.get("artifact")))
            tar.add(source, arcname=_text(row.get("bundle_arcname")), recursive=False)
    return (path.exists(), path.stat().st_size if path.exists() else 0, len(rows), _sha256_file(path))


def build_payload(
    *,
    dispatch_manifest: dict[str, Any],
    dispatch_path: str = DEFAULT_DISPATCH_JSON,
    out_tar: str = DEFAULT_OUT_TAR,
) -> dict[str, Any]:
    dispatch = _summary(dispatch_manifest)
    rows = _bundle_rows(_rows(dispatch_manifest))
    dispatch_ready = dispatch.get("dispatch_manifest_ready") is True
    missing_count = int(dispatch.get("local_artifact_missing_count") or 0)
    bundle_input_ready = bool(dispatch_ready and missing_count == 0 and rows)
    tar_exists = False
    tar_size = 0
    tar_member_count = 0
    tar_sha = ""
    if bundle_input_ready:
        tar_exists, tar_size, tar_member_count, tar_sha = _write_tar(out_tar, rows)
    bundle_ready = bool(bundle_input_ready and tar_exists and tar_member_count == len(rows) and tar_sha)
    summary = {
        "packet_type": "residual_force_gpu_worker_dispatch_bundle",
        "status": (
            "residual_force_gpu_worker_dispatch_bundle_ready"
            if bundle_ready
            else "blocked_residual_force_gpu_worker_dispatch_bundle"
        ),
        "dispatch_bundle_ready": bundle_ready,
        "dispatch_manifest_ready": dispatch_ready,
        "dispatch_manifest_artifact": dispatch_path,
        "bundle_tar_path": out_tar,
        "bundle_tar_exists": tar_exists,
        "bundle_tar_size_bytes": tar_size,
        "bundle_tar_sha256": tar_sha,
        "bundle_member_count": tar_member_count,
        "source_artifact_count": len(rows),
        "local_artifact_missing_count": missing_count,
        "native_pdb_dependency_count": int(dispatch.get("native_pdb_dependency_count") or 0),
        "native_pdb_missing_count": int(dispatch.get("native_pdb_missing_count") or 0),
        "queue_rows": int(dispatch.get("queue_rows") or 0),
        "outbound_artifact_count": int(dispatch.get("outbound_artifact_count") or 0),
        "inbound_artifact_count": int(dispatch.get("inbound_artifact_count") or 0),
        "acceptance_contract": dict(dispatch.get("acceptance_contract") or {}),
        "tiny_pilot_command": _text(dispatch.get("tiny_pilot_command")),
        "full_regeneration_command": _text(dispatch.get("full_regeneration_command")),
        "post_run_validation_commands": list(dispatch.get("post_run_validation_commands") or []),
        "post_run_validation_command_count": int(dispatch.get("post_run_validation_command_count") or 0),
        "next_required_step": (
            f"Transfer {out_tar} to the GPU worker, extract it at the repository root, run the tiny pilot, run the full "
            "regeneration command, return the inbound artifacts, then run post-return validation locally."
            if bundle_ready
            else "Repair dispatch manifest inputs before creating the GPU worker dispatch bundle."
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
    blockers = []
    if not dispatch_ready:
        blockers.append({"code": "dispatch_manifest_not_ready"})
    if missing_count:
        blockers.append({"code": "local_artifact_missing", "count": missing_count})
    if bundle_input_ready and not tar_exists:
        blockers.append({"code": "bundle_tar_not_created"})
    return {"summary": summary, "rows": rows, "blockers": blockers}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    s = payload["summary"]
    lines = [
        "# Residual Force GPU Worker Dispatch Bundle",
        "",
        f"- status: `{s['status']}`",
        f"- dispatch_bundle_ready: `{s['dispatch_bundle_ready']}`",
        f"- bundle_tar_path: `{s['bundle_tar_path']}`",
        f"- bundle_tar_size_bytes: `{s['bundle_tar_size_bytes']}`",
        f"- bundle_tar_sha256: `{s['bundle_tar_sha256']}`",
        f"- bundle_member_count: `{s['bundle_member_count']}`",
        f"- source_artifact_count: `{s['source_artifact_count']}`",
        f"- local_artifact_missing_count: `{s['local_artifact_missing_count']}`",
        "",
        "## Operator Commands",
        "",
        "### Tiny Pilot",
        "",
        "```bash",
        s["tiny_pilot_command"],
        "```",
        "",
        "### Full Regeneration",
        "",
        "```bash",
        s["full_regeneration_command"],
        "```",
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
    parser = argparse.ArgumentParser(description="Create a local tar.gz dispatch bundle for the residual-force GPU worker.")
    parser.add_argument("--dispatch-json", default=DEFAULT_DISPATCH_JSON)
    parser.add_argument("--out-tar", default=DEFAULT_OUT_TAR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        dispatch_manifest=_read_json(args.dispatch_json),
        dispatch_path=args.dispatch_json,
        out_tar=args.out_tar,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
