#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
from typing import Any, Dict, Optional, Sequence

from core.definitions import ResearchConstants
from tools.export_ai_router_onnx import build_parser as build_export_parser
from tools.export_ai_router_onnx import export_router_onnx


def _extract_json_from_stdout(stdout: str) -> Dict[str, Any]:
    text = str(stdout or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        pass
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for start in range(len(lines)):
        chunk = "\n".join(lines[start:])
        try:
            return json.loads(chunk)
        except Exception:
            continue
    return {"raw_stdout": text}


def run_poc(args: argparse.Namespace) -> Dict[str, Any]:
    target = str(args.target).strip()
    if target not in ResearchConstants.CHALLENGES:
        raise KeyError(f"unknown target: {target}")
    atoms = int(args.atoms)
    if atoms <= 0:
        atoms = int(ResearchConstants.CHALLENGES[target]["n_res"])

    onnx_path = str(args.onnx_path or "").strip()
    export_summary = None
    if not onnx_path:
        export_args = build_export_parser().parse_args([])
        export_args.target = target
        export_args.batch = int(args.batch)
        export_args.atoms = atoms
        export_args.ai_router_checkpoint = str(args.ai_router_checkpoint or "").strip()
        export_args.ai_router_checkpoint_strict = bool(args.ai_router_checkpoint_strict)
        export_args.out_onnx = str(args.out_onnx)
        export_args.out_json = str(args.out_export_json)
        export_summary = export_router_onnx(export_args)
        onnx_path = str(export_summary["out_onnx"])
        atoms = int(export_summary.get("atoms", atoms))
        args.topo_dim = int(export_summary.get("topo_dim", args.topo_dim))
        args.sim_dim = int(export_summary.get("sim_dim", args.sim_dim))

    cmd = [
        "cargo",
        "run",
        "--manifest-path",
        str(args.cargo_manifest),
        "--release",
        "--features",
        "native-inference",
        "--bin",
        "router_onnx_poc",
        "--",
        "--onnx",
        str(onnx_path),
        "--batch",
        str(int(args.batch)),
        "--atoms",
        str(int(atoms)),
        "--topo-dim",
        str(int(args.topo_dim)),
        "--sim-dim",
        str(int(args.sim_dim)),
        "--seed",
        str(int(args.seed)),
    ]
    if str(args.rust_out_json).strip():
        cmd.extend(["--out-json", str(args.rust_out_json)])

    run = subprocess.run(cmd, capture_output=True, text=True, check=False)
    rust_payload = _extract_json_from_stdout(run.stdout)
    payload = {
        "ok": bool(run.returncode == 0),
        "target": target,
        "onnx_path": os.path.abspath(onnx_path),
        "cargo_manifest": os.path.abspath(str(args.cargo_manifest)),
        "returncode": int(run.returncode),
        "command": cmd,
        "rust_stdout_json": rust_payload,
        "rust_stderr_tail": (run.stderr or "")[-2000:],
        "export_summary": export_summary,
    }
    out_json = os.path.abspath(str(args.out_json))
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run Rust-native AIRouter ONNX inference PoC (Python-free inference runtime).",
    )
    p.add_argument("--target", type=str, default="Chignolin")
    p.add_argument("--batch", type=int, default=1)
    p.add_argument("--atoms", type=int, default=0, help="0 means target n_res")
    p.add_argument("--topo-dim", type=int, default=64)
    p.add_argument("--sim-dim", type=int, default=19)
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--onnx-path", type=str, default="")
    p.add_argument("--ai-router-checkpoint", type=str, default="")
    p.add_argument(
        "--ai-router-checkpoint-strict",
        action=argparse.BooleanOptionalAction,
        default=False,
    )
    p.add_argument(
        "--out-onnx",
        type=str,
        default="runtime/cache/ai_router/airouter_router_export_native.onnx",
    )
    p.add_argument(
        "--out-export-json",
        type=str,
        default="runs/airouter_router_onnx_export_native.json",
    )
    p.add_argument(
        "--cargo-manifest",
        type=str,
        default="rust_engine/Cargo.toml",
    )
    p.add_argument(
        "--rust-out-json",
        type=str,
        default="runs/rust_native_inference_raw.json",
    )
    p.add_argument(
        "--out-json",
        type=str,
        default="runs/rust_native_inference_poc_summary.json",
    )
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    out = run_poc(args)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
