#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


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


def run_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    out_prefix = str(args.out_prefix).strip() or f"runs/idp_virtual_hbond_pipeline_{date_tag}"
    smoke_json = f"{out_prefix}_smoke.json"
    smoke_md = f"{out_prefix}_smoke.md"
    eval_json = f"{out_prefix}_eval.json"
    eval_md = f"{out_prefix}_eval.md"
    summary_json = f"{out_prefix}_summary.json"
    summary_md = f"{out_prefix}_summary.md"

    os.makedirs(os.path.dirname(summary_json) or ".", exist_ok=True)
    device = str(args.device)
    smoke_cmd = [
        sys.executable,
        os.path.join(ROOT, "tools", "run_idp_virtual_hbond_smoke.py"),
        "--device",
        device,
        "--n-res",
        str(args.n_res),
        "--frames",
        str(args.smoke_frames),
        "--seed",
        str(args.seed),
        "--out-json",
        smoke_json,
        "--out-md",
        smoke_md,
    ]
    eval_cmd = [
        sys.executable,
        os.path.join(ROOT, "tools", "run_idp_virtual_hbond_eval.py"),
        "--device",
        device,
        "--n-res",
        str(args.n_res),
        "--frames",
        str(args.eval_frames),
        "--seed",
        str(args.seed + 1),
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

    smoke_status = _run(smoke_cmd)
    smoke_payload = _read_json(smoke_json) if os.path.exists(smoke_json) else {}
    eval_status = {"rc": None}
    eval_payload: Dict[str, Any] = {}
    if int(smoke_status["rc"]) == 0:
        eval_status = _run(eval_cmd)
        if os.path.exists(eval_json):
            eval_payload = _read_json(eval_json)

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "device": device,
        "date_tag": date_tag,
        "out_prefix": out_prefix,
        "smoke": {"status": smoke_status, "payload": smoke_payload},
        "eval": {"status": eval_status, "payload": eval_payload},
    }
    payload["pass"] = bool(
        int(smoke_status.get("rc", 1)) == 0
        and int(eval_status.get("rc", 1)) == 0
        and bool(smoke_payload.get("pass", False))
        and bool(eval_payload.get("pass", False))
    )

    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    lines = [
        "# IDP Virtual HBond Pipeline",
        "",
        f"- pass: {payload['pass']}",
        f"- device: {device}",
        f"- smoke_rc: {smoke_status.get('rc')}",
        f"- eval_rc: {eval_status.get('rc')}",
        f"- smoke_json: {smoke_json}",
        f"- eval_json: {eval_json}",
    ]
    with open(summary_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    payload["summary_json"] = summary_json
    payload["summary_md"] = summary_md
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run isolated smoke+eval pipeline for experimental IDP virtual-hbond branch.")
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--out-prefix", type=str, default="")
    p.add_argument("--n-res", type=int, default=64)
    p.add_argument("--seed", type=int, default=31)
    p.add_argument("--smoke-frames", type=int, default=24)
    p.add_argument("--eval-frames", type=int, default=64)
    p.add_argument("--ionic-strength", type=float, default=0.15)
    p.add_argument("--p-h", dest="p_h", type=float, default=7.2)
    p.add_argument("--ptm-count", type=float, default=1.0)
    p.add_argument("--hydro-strength", type=float, default=1.0)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_pipeline(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not bool(payload.get("pass", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
