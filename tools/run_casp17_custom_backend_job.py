#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_JSON = "runs/casp17_custom_backend_job_current.json"
DEFAULT_OUT_CSV = "runs/casp17_custom_backend_job_current.csv"
DEFAULT_OUT_MD = "runs/casp17_custom_backend_job_current.md"


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


def _torch_gpu_probe() -> dict[str, Any]:
    try:
        import torch  # type: ignore

        available = bool(torch.cuda.is_available())
        device_count = int(torch.cuda.device_count()) if available else 0
        return {
            "torch_present": True,
            "cuda_available": available,
            "device_count": device_count,
            "device_names": [str(torch.cuda.get_device_name(index)) for index in range(device_count)],
            "torch_version": _text(getattr(torch, "__version__", "")),
        }
    except Exception as exc:  # noqa: BLE001 - runtime probe must never hide command contract state.
        return {
            "torch_present": False,
            "cuda_available": False,
            "device_count": 0,
            "device_names": [],
            "error": str(exc)[:300],
        }


def _gpu_probe(args: argparse.Namespace) -> dict[str, Any]:
    if _text(args.gpu_probe_json):
        payload = _read_json(args.gpu_probe_json)
        return payload.get("gpu", payload) if isinstance(payload.get("gpu", payload), dict) else {}
    torch_cuda = _torch_gpu_probe()
    rocm_smi = shutil.which("rocm-smi")
    nvidia_smi = shutil.which("nvidia-smi")
    return {
        "gpu_detected": bool(torch_cuda.get("cuda_available")),
        "gpu_names": list(torch_cuda.get("device_names", [])),
        "torch_cuda": torch_cuda,
        "rocm_smi_present": bool(rocm_smi),
        "nvidia_smi_present": bool(nvidia_smi),
    }


def _gpu_detected(gpu: dict[str, Any]) -> bool:
    if gpu.get("gpu_detected") is True or gpu.get("cuda_available") is True:
        return True
    torch_cuda = gpu.get("torch_cuda")
    return isinstance(torch_cuda, dict) and torch_cuda.get("cuda_available") is True


def _render_command(args: argparse.Namespace, *, out_dir: Path, raw_pdb: Path, runtime_json: Path) -> str:
    values = {
        "target_id": _text(args.target_id).upper(),
        "fasta": _artifact(args.sequence_path),
        "sequence_path": _artifact(args.sequence_path),
        "out_dir": _artifact(out_dir),
        "raw_pdb": _artifact(raw_pdb),
        "runtime_json": _artifact(runtime_json),
        "prediction_dir": _artifact(args.prediction_dir),
    }
    return args.command_template.format(**values)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Custom Backend Job",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target: `{summary['target_id']}`",
        f"- job status: `{summary['job_status']}`",
        f"- GPU detected: `{summary['gpu_detected']}`",
        f"- command return code: `{summary['returncode']}`",
        f"- raw PDB exists: `{summary['raw_pdb_exists']}`",
        f"- raw PDB: `{summary['raw_pdb']}`",
        f"- runtime JSON: `{summary['runtime_json']}`",
        f"- stdout/stderr: `{summary['stdout_file']}` / `{summary['stderr_file']}`",
        "",
        "## Command",
        "",
        f"`{summary['rendered_command'] or '-'}`",
        "",
        "## Claim Boundary",
        "",
        str(summary["claim_boundary"]),
        "",
    ]
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_job(args: argparse.Namespace) -> dict[str, Any]:
    target_id = _text(args.target_id).upper()
    out_dir = _resolve(args.out_dir or f"runs/casp17_prediction_jobs_current/{target_id}")
    raw_pdb = _resolve(args.raw_pdb or out_dir / f"{target_id}_model_1.pdb")
    runtime_json = _resolve(args.runtime_json or out_dir / "backend_runtime.json")
    stdout_file = _resolve(args.stdout_file or out_dir / "backend_stdout.txt")
    stderr_file = _resolve(args.stderr_file or out_dir / "backend_stderr.txt")
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_pdb.parent.mkdir(parents=True, exist_ok=True)
    runtime_json.parent.mkdir(parents=True, exist_ok=True)
    stdout_file.parent.mkdir(parents=True, exist_ok=True)
    stderr_file.parent.mkdir(parents=True, exist_ok=True)

    gpu = _gpu_probe(args)
    gpu_ok = _gpu_detected(gpu)
    rendered_command = _render_command(args, out_dir=out_dir, raw_pdb=raw_pdb, runtime_json=runtime_json)

    returncode = -1
    job_status = "blocked_no_gpu" if args.require_gpu and not gpu_ok else "not_started"
    stdout_text = ""
    stderr_text = ""
    started_at = ""
    finished_at = ""
    if job_status != "blocked_no_gpu":
        started_at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            run = subprocess.run(
                shlex.split(rendered_command),
                check=False,
                capture_output=True,
                text=True,
                timeout=int(args.timeout_seconds),
                cwd=str(ROOT),
            )
            returncode = int(run.returncode)
            stdout_text = run.stdout or ""
            stderr_text = run.stderr or ""
            job_status = "completed" if returncode == 0 else "failed"
            if job_status == "completed" and args.require_raw_pdb and not raw_pdb.exists():
                returncode = 2
                job_status = "failed_missing_raw_pdb"
                stderr_text = (stderr_text + "\n" if stderr_text else "") + "Backend command completed but did not create the required raw PDB."
        except subprocess.TimeoutExpired as exc:
            returncode = 124
            stdout_text = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else str(exc.stdout or "")
            stderr_text = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else str(exc.stderr or "")
            job_status = "timeout"
        except Exception as exc:  # noqa: BLE001 - preserve runtime failure in packet.
            returncode = 125
            stderr_text = f"{type(exc).__name__}: {exc}"
            job_status = "failed"
        finished_at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        stdout_file.write_text(stdout_text, encoding="utf-8")
        stderr_file.write_text(stderr_text, encoding="utf-8")
    else:
        stderr_text = "GPU execution evidence is required; command was not started."
        stderr_file.write_text(stderr_text, encoding="utf-8")
        stdout_file.write_text("", encoding="utf-8")

    runtime_payload = {
        "summary": {
            "packet_type": "casp17_custom_backend_runtime",
            "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "target_id": target_id,
            "job_status": job_status,
            "returncode": returncode,
            "started_at_local": started_at,
            "finished_at_local": finished_at,
            "gpu_detected": gpu_ok,
            "gpu_names": gpu.get("gpu_names") or gpu.get("device_names") or [],
            "raw_pdb": _artifact(raw_pdb),
            "raw_pdb_exists": raw_pdb.exists(),
            "rendered_command": rendered_command,
            "stdout_file": _artifact(stdout_file),
            "stderr_file": _artifact(stderr_file),
            "claim_boundary": "Custom backend runtime evidence only; not CASP17 validation or submission evidence.",
        },
        "runtime": {
            "gpu_detected": gpu_ok,
            "gpu_names": gpu.get("gpu_names") or gpu.get("device_names") or [],
            "torch_cuda": gpu.get("torch_cuda", {}),
        },
    }
    _write_json(runtime_json, runtime_payload)
    summary = {
        **runtime_payload["summary"],
        "sequence_path": _artifact(args.sequence_path),
        "out_dir": _artifact(out_dir),
        "runtime_json": _artifact(runtime_json),
    }
    return {"summary": summary, "runtime": runtime_payload["runtime"]}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a custom CASP17 structure prediction backend and write standard runtime evidence.")
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--sequence-path", required=True)
    parser.add_argument("--command-template", required=True)
    parser.add_argument("--prediction-dir", default="runs/casp17_predictions_current")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--raw-pdb", default="")
    parser.add_argument("--runtime-json", default="")
    parser.add_argument("--stdout-file", default="")
    parser.add_argument("--stderr-file", default="")
    parser.add_argument("--timeout-seconds", type=int, default=21600)
    parser.add_argument("--require-gpu", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--require-raw-pdb", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--gpu-probe-json", default="", help="Optional deterministic GPU probe JSON for tests/offline review.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = run_job(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, [payload["summary"]])
    _write_md(args.out_md, payload)
    if payload["summary"]["job_status"] != "completed":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
