#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DISPATCH_BUNDLE_JSON = "runs/residual_force_gpu_worker_dispatch_bundle_current.json"
DEFAULT_OUT_JSON = "runs/residual_force_gpu_worker_execution_runbook_current.json"
DEFAULT_OUT_CSV = "runs/residual_force_gpu_worker_execution_runbook_current.csv"
DEFAULT_OUT_MD = "runs/residual_force_gpu_worker_execution_runbook_current.md"
DEFAULT_OUT_SH = "runs/residual_force_gpu_worker_execution_runbook_current.sh"
DEFAULT_OUT_RETURN_PACKAGER_SH = "runs/residual_force_gpu_worker_return_bundle_packager_current.sh"
DEFAULT_RETURN_BUNDLE_TAR = "runs/residual_force_gpu_worker_return_bundle_current.tar.gz"

ROCM_DIAGNOSTIC_COMMANDS = (
    "python3 tools/build_rocm_environment_manifest.py",
    "rocminfo",
    "rocm-smi --showproductname --showdriverversion --showmeminfo vram",
    "hipcc --version",
    (
        "python3 -c \"import torch; "
        "print('torch_version=' + str(torch.__version__)); "
        "print('torch_hip_version=' + str(getattr(torch.version, 'hip', '') or '')); "
        "print('cuda_available=' + str(torch.cuda.is_available())); "
        "print('visible_device_count=' + str(torch.cuda.device_count())); "
        "print('device_names=' + ','.join(torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())))\""
    ),
)
MANIFEST_NPZ_PATH_COLUMNS = (
    "expected_regenerated_trajectory_npz",
    "trajectory_npz",
    "output_npz",
    "generated_npz",
)
REQUIRED_RETURN_CORE_FILES = (
    "runs/rocm_environment_manifest_current.json",
    "runs/residual_force_trajectory_regeneration_current_summary.json",
    "runs/residual_force_trajectory_regeneration_current_manifest.csv",
    "runs/residual_force_trajectory_regeneration_execution_probe_current.json",
)

CLAIM_BOUNDARY = (
    "Residual force GPU worker execution runbook only; converts an already-built dispatch bundle into an operator "
    "run sequence, return checklist, and worker-side shell script artifact. It does not run GPU jobs, extract bundles, "
    "regenerate trajectories, upload, submit, email, delete files, train models, promote checkpoints, or mutate "
    "external state."
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


def _script_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _row(
    *,
    step_id: str,
    phase: str,
    run_location: str,
    command: str,
    required: str,
    acceptance: str,
    returns_artifact: str = "",
    operator_action_required: bool = True,
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "phase": phase,
        "run_location": run_location,
        "command": command,
        "required": required,
        "acceptance": acceptance,
        "returns_artifact": returns_artifact,
        "operator_action_required": operator_action_required,
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def _build_rows(summary: dict[str, Any], *, out_sh: str, out_return_packager_sh: str) -> list[dict[str, Any]]:
    bundle_tar = _text(summary.get("bundle_tar_path"))
    bundle_sha = _text(summary.get("bundle_tar_sha256"))
    tiny_pilot = _text(summary.get("tiny_pilot_command"))
    full_regeneration = _text(summary.get("full_regeneration_command"))
    post_return = _text(summary.get("acceptance_contract", {}).get("post_return_validation_command"))
    worker_rocm_rule = _text(summary.get("acceptance_contract", {}).get("worker_rocm_manifest_completion_rule"))
    return_summary_rule = _text(summary.get("acceptance_contract", {}).get("return_summary_completion_rule"))
    if not return_summary_rule:
        return_summary_rule = (
            "queue_rows equals expected_queue_rows; processed_rows>=expected_queue_rows; ok_rows>=expected_queue_rows; "
            "failed_rows=0; aborted_early=false; summary paths bind to the returned manifest and summary JSON"
        )
    rows = [
        _row(
            step_id="local_transfer_bundle_to_worker",
            phase="dispatch",
            run_location="local_operator",
            command=f"transfer {bundle_tar} to the GPU worker repository root",
            required="dispatch bundle tarball is available to the GPU worker",
            acceptance=f"bundle sha256 matches {bundle_sha}" if bundle_sha else "bundle tarball exists on worker",
        ),
        _row(
            step_id="worker_extract_dispatch_bundle",
            phase="worker_preflight",
            run_location="gpu_worker",
            command=f"tar -xzf {bundle_tar}",
            required="worker extracts the dispatch bundle at repository root",
            acceptance="queue, tools, templates, and native PDB dependencies are present before execution",
        ),
        _row(
            step_id="worker_rocm_manifest_preflight",
            phase="worker_preflight",
            run_location="gpu_worker",
            command=" && ".join(ROCM_DIAGNOSTIC_COMMANDS),
            required="ROCm/HIP stack and PyTorch-visible AMD GPU are proven before regeneration",
            acceptance=worker_rocm_rule,
            returns_artifact="runs/rocm_environment_manifest_current.json",
        ),
        _row(
            step_id="worker_tiny_pilot",
            phase="worker_execution",
            run_location="gpu_worker",
            command=tiny_pilot,
            required="tiny pilot succeeds before consuming the full regeneration budget",
            acceptance="pilot summary and pilot manifest are written without CPU fallback",
        ),
        _row(
            step_id="worker_full_regeneration",
            phase="worker_execution",
            run_location="gpu_worker",
            command=full_regeneration,
            required="full 768-row residual-force trajectory regeneration runs in production mode on ROCm/HIP",
            acceptance=return_summary_rule,
            returns_artifact="runs/residual_force_trajectory_regeneration_current_summary.json",
        ),
        _row(
            step_id="worker_return_artifacts",
            phase="return_bundle",
            run_location="gpu_worker",
            command=f"bash {out_return_packager_sh}",
            required="summary, manifest, NPZ bundles, execution probe, and ROCm manifest are returned intact",
            acceptance="return bundle tar includes core return files and every NPZ path referenced by the returned manifest",
            returns_artifact="required_return_artifacts",
        ),
        _row(
            step_id="local_post_return_validation",
            phase="local_acceptance",
            run_location="local_operator",
            command=post_return,
            required="local acceptance and promotion ladder are regenerated from returned artifacts",
            acceptance="gpu_worker_return_receipt_ready=true before any downstream production promotion",
        ),
        _row(
            step_id="worker_runbook_script",
            phase="dispatch",
            run_location="gpu_worker",
            command=f"bash {out_sh}",
            required="optional worker-side script mirrors the runbook sequence",
            acceptance="script exits nonzero unless ROCm preflight, tiny pilot, full regeneration, and manifest return checks pass",
        ),
    ]
    return rows


def _write_shell_script(path_like: str | Path, summary: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    bundle_tar = _text(summary.get("bundle_tar_path"))
    bundle_sha = _text(summary.get("bundle_tar_sha256"))
    tiny_pilot = _text(summary.get("tiny_pilot_command"))
    full_regeneration = _text(summary.get("full_regeneration_command"))
    inbound = [
        _text(artifact)
        for artifact in _list(summary.get("acceptance_contract", {}).get("inbound_artifacts"))
        if _text(artifact)
    ]
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Generated worker-side helper. Review before running on the GPU worker.",
        f"BUNDLE_TAR={_script_quote(bundle_tar)}",
        f"BUNDLE_SHA256={_script_quote(bundle_sha)}",
        "",
        "if [[ ! -f \"$BUNDLE_TAR\" ]]; then",
        "  echo \"missing dispatch bundle: $BUNDLE_TAR\" >&2",
        "  exit 2",
        "fi",
        "if [[ -n \"$BUNDLE_SHA256\" ]]; then",
        "  echo \"$BUNDLE_SHA256  $BUNDLE_TAR\" | sha256sum -c -",
        "fi",
        "tar -xzf \"$BUNDLE_TAR\"",
        "",
        "python3 tools/build_rocm_environment_manifest.py",
        "rocminfo",
        "rocm-smi --showproductname --showdriverversion --showmeminfo vram",
        "hipcc --version",
        ROCM_DIAGNOSTIC_COMMANDS[-1],
        "",
        tiny_pilot,
        "",
        full_regeneration,
        "",
        "python3 tools/build_rocm_environment_manifest.py",
        "python3 tools/build_residual_force_trajectory_regeneration_execution_probe.py",
        "",
        "echo 'Required return artifacts:'",
    ]
    for artifact in inbound:
        lines.append(f"echo ' - {artifact}'")
    lines.extend(
        [
            "",
            "test -f runs/rocm_environment_manifest_current.json",
            "test -f runs/residual_force_trajectory_regeneration_current_summary.json",
            "test -f runs/residual_force_trajectory_regeneration_current_manifest.csv",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_return_packager_script(
    path_like: str | Path,
    *,
    return_bundle_tar: str,
) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    npz_columns = ",".join(MANIFEST_NPZ_PATH_COLUMNS)
    core_files = " ".join(_script_quote(file_name) for file_name in REQUIRED_RETURN_CORE_FILES)
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "# Generated GPU-worker return bundle packager. Run after full regeneration finishes.",
        f"RETURN_BUNDLE_TAR={_script_quote(return_bundle_tar)}",
        "SUMMARY_JSON='runs/residual_force_trajectory_regeneration_current_summary.json'",
        "MANIFEST_CSV='runs/residual_force_trajectory_regeneration_current_manifest.csv'",
        "FILE_LIST='runs/residual_force_gpu_worker_return_bundle_file_list_current.txt'",
        "NPZ_FILE_LIST='runs/residual_force_gpu_worker_return_bundle_npz_file_list_current.txt'",
        "",
        "python3 tools/build_rocm_environment_manifest.py",
        "python3 tools/build_residual_force_trajectory_regeneration_execution_probe.py",
        "",
        f"for required in {core_files}; do",
        "  if [[ ! -f \"$required\" ]]; then",
        "    echo \"missing required return file: $required\" >&2",
        "    exit 3",
        "  fi",
        "done",
        "",
        "python3 - <<'PY'",
        "import csv",
        "from pathlib import Path",
        "",
        f"npz_columns = {list(MANIFEST_NPZ_PATH_COLUMNS)!r}",
        "manifest = Path('runs/residual_force_trajectory_regeneration_current_manifest.csv')",
        "paths = []",
        "with manifest.open('r', encoding='utf-8', newline='') as handle:",
        "    reader = csv.DictReader(handle)",
        "    for row in reader:",
        "        for column in npz_columns:",
        "            value = (row.get(column) or '').strip()",
        "            if value:",
        "                paths.append(value)",
        "                break",
        "missing = [path for path in paths if not Path(path).is_file()]",
        "Path('runs/residual_force_gpu_worker_return_bundle_npz_file_list_current.txt').write_text(",
        "    '\\n'.join(dict.fromkeys(paths)) + ('\\n' if paths else ''),",
        "    encoding='utf-8',",
        ")",
        "if missing:",
        "    raise SystemExit('missing NPZ return files: ' + ';'.join(missing[:20]))",
        "if not paths:",
        "    raise SystemExit('manifest has no NPZ paths in columns: ' + ','.join(npz_columns))",
        "PY",
        "",
        "printf '%s\\n' \\",
        "  'runs/rocm_environment_manifest_current.json' \\",
        "  'runs/residual_force_trajectory_regeneration_current_summary.json' \\",
        "  'runs/residual_force_trajectory_regeneration_current_manifest.csv' \\",
        "  'runs/residual_force_trajectory_regeneration_execution_probe_current.json' \\",
        "  'runs/residual_force_gpu_worker_return_bundle_npz_file_list_current.txt' \\",
        "  > \"$FILE_LIST\"",
        "cat \"$NPZ_FILE_LIST\" >> \"$FILE_LIST\"",
        "mkdir -p \"$(dirname \"$RETURN_BUNDLE_TAR\")\"",
        "tar -czf \"$RETURN_BUNDLE_TAR\" -T \"$FILE_LIST\"",
        "sha256sum \"$RETURN_BUNDLE_TAR\" > \"${RETURN_BUNDLE_TAR}.sha256\"",
        "echo \"return_bundle_tar=$RETURN_BUNDLE_TAR\"",
        f"echo \"manifest_npz_path_columns={npz_columns}\"",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def build_payload(
    *,
    dispatch_bundle: dict[str, Any],
    dispatch_bundle_path: str = DEFAULT_DISPATCH_BUNDLE_JSON,
    out_sh: str = DEFAULT_OUT_SH,
    out_return_packager_sh: str = DEFAULT_OUT_RETURN_PACKAGER_SH,
    return_bundle_tar: str = DEFAULT_RETURN_BUNDLE_TAR,
) -> dict[str, Any]:
    bundle = _summary(dispatch_bundle)
    dispatch_bundle_ready = bundle.get("dispatch_bundle_ready") is True
    bundle_tar_exists = bundle.get("bundle_tar_exists") is True
    required_return_artifacts = [
        _text(artifact)
        for artifact in _list(bundle.get("acceptance_contract", {}).get("inbound_artifacts"))
        if _text(artifact)
    ]
    rows = _build_rows(
        bundle,
        out_sh=out_sh,
        out_return_packager_sh=out_return_packager_sh,
    ) if dispatch_bundle_ready else []
    runbook_ready = bool(dispatch_bundle_ready and bundle_tar_exists and rows and required_return_artifacts)
    if runbook_ready:
        _write_shell_script(out_sh, bundle)
        _write_return_packager_script(out_return_packager_sh, return_bundle_tar=return_bundle_tar)
    worker_script_path = _resolve(out_sh)
    worker_script_exists = worker_script_path.is_file()
    return_packager_script_path = _resolve(out_return_packager_sh)
    return_packager_script_exists = return_packager_script_path.is_file()
    summary = {
        "packet_type": "residual_force_gpu_worker_execution_runbook",
        "status": (
            "residual_force_gpu_worker_execution_runbook_ready"
            if runbook_ready
            else "blocked_residual_force_gpu_worker_execution_runbook"
        ),
        "execution_runbook_ready": runbook_ready,
        "dispatch_bundle_ready": dispatch_bundle_ready,
        "dispatch_bundle_artifact": dispatch_bundle_path,
        "bundle_tar_path": _text(bundle.get("bundle_tar_path")),
        "bundle_tar_exists": bundle_tar_exists,
        "bundle_tar_sha256": _text(bundle.get("bundle_tar_sha256")),
        "queue_rows": int(bundle.get("queue_rows") or 0),
        "worker_script_path": out_sh,
        "worker_script_exists": worker_script_exists,
        "worker_script_executable": bool(worker_script_exists and os.access(worker_script_path, os.X_OK)),
        "return_packager_script_path": out_return_packager_sh,
        "return_packager_script_exists": return_packager_script_exists,
        "return_packager_script_executable": bool(
            return_packager_script_exists and os.access(return_packager_script_path, os.X_OK)
        ),
        "return_bundle_tar_path": return_bundle_tar,
        "return_bundle_sha256_path": f"{return_bundle_tar}.sha256",
        "manifest_npz_path_columns": list(MANIFEST_NPZ_PATH_COLUMNS),
        "required_return_core_files": list(REQUIRED_RETURN_CORE_FILES),
        "return_packager_command": f"bash {out_return_packager_sh}",
        "step_count": len(rows),
        "worker_executable_step_count": sum(1 for row in rows if row["run_location"] == "gpu_worker"),
        "local_post_return_step_count": sum(1 for row in rows if row["run_location"] == "local_operator"),
        "rocm_diagnostic_command_count": len(ROCM_DIAGNOSTIC_COMMANDS),
        "required_return_artifact_count": len(required_return_artifacts),
        "required_return_artifacts": required_return_artifacts,
        "acceptance_contract": dict(bundle.get("acceptance_contract") or {}),
        "tiny_pilot_command": _text(bundle.get("tiny_pilot_command")),
        "full_regeneration_command": _text(bundle.get("full_regeneration_command")),
        "post_return_validation_command": _text(
            bundle.get("acceptance_contract", {}).get("post_return_validation_command")
        ),
        "next_required_step": (
            f"Transfer {_text(bundle.get('bundle_tar_path'))} and {out_sh} to the GPU worker, run the script or "
            f"execute the listed steps manually, package returns with {out_return_packager_sh}, return "
            f"{return_bundle_tar}, then run local post-return validation."
            if runbook_ready
            else "Build a ready dispatch bundle before generating the GPU worker execution runbook."
        ),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "full_regeneration_executed": False,
        "force_labels_created": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    blockers = []
    if not dispatch_bundle_ready:
        blockers.append({"code": "dispatch_bundle_not_ready"})
    if dispatch_bundle_ready and not bundle_tar_exists:
        blockers.append({"code": "bundle_tar_missing"})
    if dispatch_bundle_ready and not required_return_artifacts:
        blockers.append({"code": "required_return_artifacts_missing"})
    if runbook_ready and not worker_script_exists:
        blockers.append({"code": "worker_script_missing"})
    if runbook_ready and not return_packager_script_exists:
        blockers.append({"code": "return_packager_script_missing"})
    return {"summary": summary, "rows": rows, "blockers": blockers}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    s = payload["summary"]
    lines = [
        "# Residual Force GPU Worker Execution Runbook",
        "",
        f"- status: `{s['status']}`",
        f"- execution_runbook_ready: `{s['execution_runbook_ready']}`",
        f"- dispatch_bundle_ready: `{s['dispatch_bundle_ready']}`",
        f"- bundle_tar_path: `{s['bundle_tar_path']}`",
        f"- bundle_tar_sha256: `{s['bundle_tar_sha256']}`",
        f"- worker_script_path: `{s['worker_script_path']}`",
        f"- return_packager_script_path: `{s['return_packager_script_path']}`",
        f"- return_bundle_tar_path: `{s['return_bundle_tar_path']}`",
        f"- required_return_artifact_count: `{s['required_return_artifact_count']}`",
        "",
        "## Steps",
        "",
    ]
    for row in payload["rows"]:
        lines.extend(
            [
                f"### {row['step_id']}",
                "",
                f"- phase: `{row['phase']}`",
                f"- run_location: `{row['run_location']}`",
                f"- required: {row['required']}",
                f"- acceptance: {row['acceptance']}",
                "",
                "```bash",
                row["command"],
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Required Return Artifacts",
            "",
            *[f"- `{artifact}`" for artifact in s["required_return_artifacts"]],
            "",
            "## Return Packager",
            "",
            "```bash",
            s["return_packager_command"],
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
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a GPU worker execution runbook from the dispatch bundle.")
    parser.add_argument("--dispatch-bundle-json", default=DEFAULT_DISPATCH_BUNDLE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-sh", default=DEFAULT_OUT_SH)
    parser.add_argument("--out-return-packager-sh", default=DEFAULT_OUT_RETURN_PACKAGER_SH)
    parser.add_argument("--return-bundle-tar", default=DEFAULT_RETURN_BUNDLE_TAR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        dispatch_bundle=_read_json(args.dispatch_bundle_json),
        dispatch_bundle_path=args.dispatch_bundle_json,
        out_sh=args.out_sh,
        out_return_packager_sh=args.out_return_packager_sh,
        return_bundle_tar=args.return_bundle_tar,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
