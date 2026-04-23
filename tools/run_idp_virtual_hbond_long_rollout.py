#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence


ROOT = "/home/betelgeuze/분자동역학"


def _run(cmd: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "cmd": cmd,
        "rc": int(proc.returncode),
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-20:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-20:]),
    }


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _mean(rows: List[float]) -> float:
    return float(sum(rows) / max(len(rows), 1))


def run_long_rollout(args: argparse.Namespace) -> Dict[str, Any]:
    out_prefix = str(args.out_prefix).strip() or (
        f"/home/betelgeuze/분자동역학/runs/idp_virtual_hbond_long_rollout_{dt.date.today().isoformat()}"
    )
    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    frames = int(args.frames)
    seeds = [int(x.strip()) for x in str(args.seeds).split(",") if str(x).strip()]
    os.makedirs(os.path.dirname(out_prefix) or ".", exist_ok=True)

    runs: List[Dict[str, Any]] = []
    pass_flags: List[bool] = []
    rg_delta: List[float] = []
    sasa_delta: List[float] = []
    helicity_delta: List[float] = []
    contact_delta: List[float] = []

    for seed in seeds:
        eval_json = f"{out_prefix}_seed{seed}_eval.json"
        eval_md = f"{out_prefix}_seed{seed}_eval.md"
        cmd = [
            sys.executable,
            os.path.join(ROOT, "tools", "run_idp_virtual_hbond_rollout_eval.py"),
            "--device",
            str(args.device),
            "--n-res",
            str(args.n_res),
            "--frames",
            str(frames),
            "--seed",
            str(seed),
            "--ionic-strength",
            str(args.ionic_strength),
            "--p-h",
            str(args.p_h),
            "--ptm-count",
            str(args.ptm_count),
            "--hydro-strength",
            str(args.hydro_strength),
            "--out-json",
            eval_json,
            "--out-md",
            eval_md,
        ]
        status = _run(cmd)
        payload = _read_json(eval_json) if os.path.exists(eval_json) else {}
        run_payload = {"seed": seed, "status": status, "payload": payload}
        runs.append(run_payload)
        passed = bool(status["rc"] == 0 and payload.get("pass", False))
        pass_flags.append(passed)
        if payload:
            rg_delta.append(float(payload.get("delta_rg_mean", 0.0) or 0.0))
            sasa_delta.append(float(payload.get("delta_sasa_proxy_mean", 0.0) or 0.0))
            helicity_delta.append(float(payload.get("delta_transient_helicity", 0.0) or 0.0))
            contact_delta.append(float(payload.get("delta_contact_persistence", 0.0) or 0.0))

    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "date_tag": date_tag,
        "device": str(args.device),
        "n_res": int(args.n_res),
        "frames": frames,
        "seeds": seeds,
        "runs": runs,
        "mean_delta_rg": _mean(rg_delta) if rg_delta else 0.0,
        "mean_delta_sasa_proxy": _mean(sasa_delta) if sasa_delta else 0.0,
        "mean_delta_transient_helicity": _mean(helicity_delta) if helicity_delta else 0.0,
        "mean_delta_contact_persistence": _mean(contact_delta) if contact_delta else 0.0,
        "pass_count": int(sum(1 for x in pass_flags if x)),
        "run_count": int(len(pass_flags)),
    }
    summary["pass"] = bool(summary["pass_count"] == summary["run_count"])

    out_json = f"{out_prefix}_summary.json"
    out_md = f"{out_prefix}_summary.md"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    lines = [
        "# IDP Virtual HBond Long Rollout",
        "",
        f"- pass: {summary['pass']}",
        f"- device: {summary['device']}",
        f"- frames: {summary['frames']}",
        f"- seeds: {','.join(str(x) for x in seeds)}",
        f"- pass_count: {summary['pass_count']}/{summary['run_count']}",
        f"- mean_delta_rg: {summary['mean_delta_rg']}",
        f"- mean_delta_sasa_proxy: {summary['mean_delta_sasa_proxy']}",
        f"- mean_delta_transient_helicity: {summary['mean_delta_transient_helicity']}",
        f"- mean_delta_contact_persistence: {summary['mean_delta_contact_persistence']}",
    ]
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(json.dumps({"summary_json": out_json, "summary_md": out_md, "pass": summary["pass"]}, indent=2, ensure_ascii=False))
    if not summary["pass"]:
        raise SystemExit(2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run longer IDP virtual-hbond evaluation over multiple seeds.")
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--out-prefix", type=str, default="")
    p.add_argument("--n-res", type=int, default=64)
    p.add_argument("--frames", type=int, default=512)
    p.add_argument("--seeds", type=str, default="41,42,43")
    p.add_argument("--ionic-strength", type=float, default=0.15)
    p.add_argument("--p-h", dest="p_h", type=float, default=7.2)
    p.add_argument("--ptm-count", type=float, default=1.0)
    p.add_argument("--hydro-strength", type=float, default=1.0)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    run_long_rollout(args)


if __name__ == "__main__":
    main()
