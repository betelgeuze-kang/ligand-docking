#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BACKEND_READINESS_JSON = "runs/casp17_backend_readiness_packet_current.json"
DEFAULT_ENV_PATH = ".venv-casp17-structure"
DEFAULT_OUT_JSON = "runs/casp17_backend_provisioning_plan_current.json"
DEFAULT_OUT_CSV = "runs/casp17_backend_provisioning_plan_current.csv"
DEFAULT_OUT_MD = "runs/casp17_backend_provisioning_plan_current.md"

ENV_TOOLS = ("python3", "pip", "pip3", "uv", "conda", "mamba", "micromamba")
BACKEND_COMMANDS = ("colabfold_batch", "omegafold", "esm-fold", "esmfold")


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "rank",
        "lane",
        "status",
        "cpu_fallback_allowed",
        "installation_executed",
        "command_template",
        "validation_command",
        "exit_criterion",
        "blockers",
        "rationale",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _sha256_file(path_like: str | Path) -> str:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _source_fingerprint(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {
            "path": _artifact(path_like),
            "present": False,
            "sha256": "",
            "mtime_ns": 0,
            "mtime_local": "",
        }
    stat = path.stat()
    return {
        "path": _artifact(path_like),
        "present": True,
        "sha256": _sha256_file(path),
        "mtime_ns": stat.st_mtime_ns,
        "mtime_local": dt.datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
    }


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _probe(payload: dict[str, Any]) -> dict[str, Any]:
    probe = payload.get("probe")
    return probe if isinstance(probe, dict) else {}


def _commands(probe: dict[str, Any]) -> dict[str, str]:
    commands = probe.get("commands")
    if not isinstance(commands, dict):
        return {}
    return {str(key): _text(value) for key, value in commands.items()}


def _modules(probe: dict[str, Any]) -> dict[str, bool]:
    modules = probe.get("python_modules")
    if not isinstance(modules, dict):
        return {}
    return {str(key): bool(value) for key, value in modules.items()}


def _env_status(env_path: str | Path) -> dict[str, Any]:
    path = _resolve(env_path)
    python_path = path / "bin" / "python"
    pip_path = path / "bin" / "pip"
    if path.exists() and python_path.exists():
        status = "existing_isolated_python_env"
    elif path.exists():
        status = "path_exists_but_python_missing"
    else:
        status = "missing_not_created"
    return {
        "path": _artifact(path),
        "status": status,
        "exists": path.exists(),
        "python_path": _artifact(python_path) if python_path.exists() else "",
        "pip_path": _artifact(pip_path) if pip_path.exists() else "",
    }


def _installed_backend_commands(commands: dict[str, str]) -> list[str]:
    return [name for name in BACKEND_COMMANDS if _text(commands.get(name))]


def _env_tool_summary(commands: dict[str, str]) -> dict[str, str]:
    return {name: _text(commands.get(name)) for name in ENV_TOOLS if _text(commands.get(name))}


def _manual_attach_row() -> dict[str, Any]:
    return {
        "rank": 1,
        "lane": "attach_existing_structure_with_provenance",
        "status": "available_manual_path",
        "cpu_fallback_allowed": False,
        "installation_executed": False,
        "command_template": (
            "python3 tools/build_casp17_existing_structure_intake_builder.py "
            "--structure-dir runs/casp17_existing_structures_current "
            "--provenance-csv runs/casp17_existing_structure_provenance_current.csv "
            "--author-code <CASP_AUTHOR_CODE>"
        ),
        "validation_command": "python3 tools/build_casp17_existing_structure_file_checklist.py --write-provenance-scaffold",
        "exit_criterion": "existing structure is attached or converted, provenance is cleared, then validation/scorecard/submission gate must pass",
        "blockers": "",
        "rationale": "Use a target-specific raw PDB or TS prediction generated elsewhere, but require explicit provenance clearance before import.",
    }


def _detected_backend_row(selected_backend: str) -> dict[str, Any]:
    return {
        "rank": 2,
        "lane": f"use_detected_{selected_backend}",
        "status": "ready_to_refresh_launch_packet",
        "cpu_fallback_allowed": False,
        "installation_executed": False,
        "command_template": "python3 tools/build_casp17_prediction_launch_packet.py",
        "validation_command": "python3 tools/run_casp17_target_attempt_gate.py --target-id <TARGET_ID>",
        "exit_criterion": "launch_status=ready_to_launch with backend contract requiring GPU evidence",
        "blockers": "",
        "rationale": "A supported structure-prediction backend is already visible to the local launch planner.",
    }


def _custom_backend_row() -> dict[str, Any]:
    return {
        "rank": 2,
        "lane": "wire_custom_gpu_backend_command",
        "status": "blocked_until_command_supplied",
        "cpu_fallback_allowed": False,
        "installation_executed": False,
        "command_template": (
            "python3 tools/build_casp17_backend_profile_packet.py --supports-multimer && "
            "python3 tools/build_casp17_prediction_coverage_gate.py"
        ),
        "validation_command": "python3 tools/run_casp17_target_attempt_gate.py --target-id <TARGET_ID> --execute --author-code <CASP_AUTHOR_CODE>",
        "exit_criterion": "backend_runtime.json shows GPU evidence; validate_casp17_backend_contract.py passes",
        "blockers": "missing_structure_prediction_backend",
        "rationale": "The existing GPU can be used as soon as a local predictor is exposed through the repository contract.",
    }


def _rocm_env_row(env_path: str) -> dict[str, Any]:
    return {
        "rank": 3,
        "lane": "provision_isolated_rocm_pytorch_structure_backend",
        "status": "dependency_install_required_not_executed",
        "cpu_fallback_allowed": False,
        "installation_executed": False,
        "command_template": (
            f"python3 -m venv {env_path} && . {env_path}/bin/activate && python -m pip install --upgrade pip && "
            "python -m pip install '<ROCM_COMPATIBLE_STRUCTURE_BACKEND>'"
        ),
        "validation_command": (
            f". {env_path}/bin/activate && python - <<'PY'\n"
            "import torch\n"
            "assert torch.cuda.is_available()\n"
            "print(torch.cuda.get_device_name(0))\n"
            "PY"
        ),
        "exit_criterion": "PyTorch reports the ROCm GPU and launch packet uses a GPU-backed backend command",
        "blockers": "missing_structure_prediction_backend",
        "rationale": "This host exposes an AMD/ROCm GPU; a PyTorch-native structure backend is the lowest-friction local lane.",
    }


def _cuda_env_row(env_path: str) -> dict[str, Any]:
    return {
        "rank": 3,
        "lane": "provision_isolated_cuda_colabfold_backend",
        "status": "dependency_install_required_not_executed",
        "cpu_fallback_allowed": False,
        "installation_executed": False,
        "command_template": (
            f"python3 -m venv {env_path} && . {env_path}/bin/activate && python -m pip install --upgrade pip && "
            "python -m pip install '<CUDA_COMPATIBLE_COLABFOLD_OR_STRUCTURE_BACKEND>'"
        ),
        "validation_command": "colabfold_batch --help && python3 tools/build_casp17_prediction_launch_packet.py",
        "exit_criterion": "colabfold_batch or another supported GPU backend is detected",
        "blockers": "missing_structure_prediction_backend",
        "rationale": "CUDA hosts can use the existing launch planner once a supported backend CLI is isolated and visible.",
    }


def _gpu_enablement_row() -> dict[str, Any]:
    return {
        "rank": 3,
        "lane": "gpu_runtime_enablement_first",
        "status": "blocked_until_gpu_ready",
        "cpu_fallback_allowed": False,
        "installation_executed": False,
        "command_template": "Fix GPU runtime first; do not generate CASP17 predictions through CPU fallback.",
        "validation_command": "python3 tools/build_casp17_backend_readiness_packet.py",
        "exit_criterion": "accelerator_status is rocm_gpu_ready or cuda_gpu_ready",
        "blockers": "gpu_not_ready;cpu_fallback_disallowed",
        "rationale": "CASP17 target generation is too slow and weakly evidenced on CPU fallback for this gate.",
    }


def _colabfold_rocm_caution_row() -> dict[str, Any]:
    return {
        "rank": 4,
        "lane": "colabfold_cuda_lane_on_rocm_host",
        "status": "not_first_choice_on_rocm_host",
        "cpu_fallback_allowed": False,
        "installation_executed": False,
        "command_template": "Use only if a compatible isolated build exists and GPU execution is proven.",
        "validation_command": "python3 tools/validate_casp17_backend_contract.py --target-id <TARGET_ID> --sequence-path <FASTA> --raw-pdb <RAW_PDB> --runtime-json <RUNTIME_JSON> --require-gpu",
        "exit_criterion": "backend contract passes with GPU evidence, not CPU fallback",
        "blockers": "rocm_host_colabfold_cuda_not_first_choice",
        "rationale": "ColabFold packaging is commonly CUDA/JAX-oriented; avoid spending the first local iteration there on ROCm.",
    }


def _plan_rows(summary: dict[str, Any], probe: dict[str, Any], env_path: str) -> list[dict[str, Any]]:
    backend_status = _text(summary.get("backend_status"))
    accelerator_status = _text(summary.get("accelerator_status"))
    selected_backend = _text(summary.get("selected_backend"))
    rows = [_manual_attach_row()]
    if backend_status == "backend_cli_ready" and selected_backend:
        rows.append(_detected_backend_row(selected_backend))
        return rows
    rows.append(_custom_backend_row())
    if accelerator_status == "rocm_gpu_ready":
        rows.append(_rocm_env_row(env_path))
        rows.append(_colabfold_rocm_caution_row())
    elif accelerator_status == "cuda_gpu_ready":
        rows.append(_cuda_env_row(env_path))
    else:
        rows.append(_gpu_enablement_row())
    modules = _modules(probe)
    if backend_status == "python_backend_present_cli_missing":
        rows.append(
            {
                "rank": 5,
                "lane": "wrap_existing_python_backend",
                "status": "blocked_until_cli_or_adapter_written",
                "cpu_fallback_allowed": False,
                "installation_executed": False,
                "command_template": "Expose the existing Python module as a command that writes {raw_pdb}, then pass it as --custom-backend-command.",
                "validation_command": "python3 tools/validate_casp17_backend_contract.py --target-id <TARGET_ID> --sequence-path <FASTA> --raw-pdb <RAW_PDB> --runtime-json <RUNTIME_JSON> --require-gpu",
                "exit_criterion": "launch packet has recommended_backend=custom and target attempt gate reaches contract step",
                "blockers": "missing_backend_cli_wrapper",
                "rationale": f"Detected backend-like Python modules: {','.join(sorted(k for k, v in modules.items() if v)) or 'none'}.",
            }
        )
    return rows


def _plan_status(summary: dict[str, Any], source: dict[str, Any]) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if not source.get("present"):
        blockers.append("backend_readiness_artifact_missing")
        return "blocked_missing_readiness_artifact", blockers
    backend_status = _text(summary.get("backend_status"))
    accelerator_status = _text(summary.get("accelerator_status"))
    existing_blockers = summary.get("blockers")
    if isinstance(existing_blockers, list):
        blockers.extend(_text(item) for item in existing_blockers if _text(item))
    if backend_status == "backend_cli_ready":
        return "backend_ready_no_provisioning_required", []
    if accelerator_status in {"rocm_gpu_ready", "cuda_gpu_ready"}:
        if "missing_structure_prediction_backend" not in blockers:
            blockers.append("missing_structure_prediction_backend")
        return f"blocked_until_{accelerator_status.split('_')[0]}_structure_backend_is_wired", blockers
    if "cpu_fallback_disallowed" not in blockers:
        blockers.append("cpu_fallback_disallowed")
    return "blocked_gpu_or_backend_not_ready", blockers


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    readiness = _read_json(args.backend_readiness_json)
    readiness_summary = _summary(readiness)
    readiness_probe = _probe(readiness)
    commands = _commands(readiness_probe)
    rows = _plan_rows(readiness_summary, readiness_probe, args.env_path)
    source = _source_fingerprint(args.backend_readiness_json)
    plan_status, blockers = _plan_status(readiness_summary, source)
    installed_backends = _installed_backend_commands(commands)
    summary = {
        "packet_type": "casp17_backend_provisioning_plan",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "backend_readiness_json": _artifact(args.backend_readiness_json),
        "backend_readiness_fingerprint": source,
        "backend_readiness_status": _text(readiness_summary.get("backend_status")) or "missing",
        "accelerator_status": _text(readiness_summary.get("accelerator_status")) or "missing",
        "device_names": readiness_summary.get("device_names", []),
        "plan_status": plan_status,
        "ready_to_launch_now": plan_status == "backend_ready_no_provisioning_required",
        "cpu_fallback_allowed": False,
        "installation_executed": False,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "installed_backend_commands": installed_backends,
        "env_tools": _env_tool_summary(commands),
        "isolated_env": _env_status(args.env_path),
        "claim_boundary": "Provisioning guidance only; no dependency installation, prediction execution, registration, or CASP17 submission is performed.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    fingerprint = summary["backend_readiness_fingerprint"]
    env = summary["isolated_env"]
    lines = [
        "# CASP17 Backend Provisioning Plan",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- plan status: `{summary['plan_status']}`",
        f"- accelerator status: `{summary['accelerator_status']}`",
        f"- backend readiness status: `{summary['backend_readiness_status']}`",
        f"- ready to launch now: `{summary['ready_to_launch_now']}`",
        f"- CPU fallback allowed: `{summary['cpu_fallback_allowed']}`",
        f"- installation executed: `{summary['installation_executed']}`",
        f"- blockers: `{';'.join(summary['blockers']) if summary['blockers'] else '-'}`",
        f"- readiness artifact: `{fingerprint['path']}` sha256=`{fingerprint['sha256'] or '-'}` mtime=`{fingerprint['mtime_local'] or '-'}`",
        f"- isolated env: `{env['path']}` status=`{env['status']}`",
        "",
        "## Plan Rows",
        "",
        "| rank | lane | status | CPU fallback | install executed | command template | exit criterion | blockers |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['rank']} | `{row['lane']}` | `{row['status']}` | `{row['cpu_fallback_allowed']}` | "
            f"`{row['installation_executed']}` | `{row['command_template']}` | {row['exit_criterion']} | {row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fail-closed CASP17 backend provisioning plan from the readiness packet.")
    parser.add_argument("--backend-readiness-json", default=DEFAULT_BACKEND_READINESS_JSON)
    parser.add_argument("--env-path", default=DEFAULT_ENV_PATH)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
