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


def run_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    out_prefix = str(args.out_prefix).strip() or f"/home/betelgeuze/분자동역학/runs/idp_3bead_pipeline_{date_tag}"
    eval_json = f"{out_prefix}_eval_summary.json"
    gate_json = f"{out_prefix}_gate_summary.json"
    dataset_prefix = f"{out_prefix}_residual_dataset"
    train_json = f"{out_prefix}_residual_train_summary.json"
    train_md = f"{out_prefix}_residual_train_summary.md"
    train_ckpt = f"/home/betelgeuze/분자동역학/models/idp_residual_{date_tag}.pt"
    eval_residual_json = f"{out_prefix}_eval_residual_summary.json"
    gate_residual_json = f"{out_prefix}_gate_residual_summary.json"
    branch_report_json = f"{out_prefix}_branch_report.json"
    final_json = f"{out_prefix}_summary.json"
    final_md = f"{out_prefix}_summary.md"

    os.makedirs(os.path.dirname(final_json) or ".", exist_ok=True)

    eval_cmd = [
        sys.executable,
        os.path.join(ROOT, "tools", "run_idp_3bead_evaluator.py"),
        "--config-json",
        str(args.config_json),
        "--device",
        str(args.device),
        "--date-tag",
        date_tag,
        "--out-prefix",
        f"{out_prefix}_eval",
    ]
    eval_status = _run(eval_cmd)
    eval_payload = _read_json(eval_json) if os.path.exists(eval_json) else {}

    gate_status = {"rc": None}
    gate_payload: Dict[str, Any] = {}
    dataset_status = {"rc": None}
    dataset_payload: Dict[str, Any] = {}
    train_status = {"rc": None}
    train_payload: Dict[str, Any] = {}
    eval_residual_status = {"rc": None}
    eval_residual_payload: Dict[str, Any] = {}
    gate_residual_status = {"rc": None}
    gate_residual_payload: Dict[str, Any] = {}
    branch_status = {"rc": None}
    branch_payload: Dict[str, Any] = {}

    if int(eval_status["rc"]) == 0:
        gate_cmd = [
            sys.executable,
            os.path.join(ROOT, "tools", "run_idp_3bead_benchmark_gate.py"),
            "--config-json",
            str(args.config_json),
            "--eval-json",
            eval_json,
            "--out-json",
            gate_json,
            "--out-md",
            f"{out_prefix}_gate_summary.md",
        ]
        gate_status = _run(gate_cmd)
        if os.path.exists(gate_json):
            gate_payload = _read_json(gate_json)

        dataset_cmd = [
            sys.executable,
            os.path.join(ROOT, "tools", "build_idp_residual_dataset.py"),
            "--eval-json",
            eval_json,
            "--out-prefix",
            dataset_prefix,
        ]
        dataset_status = _run(dataset_cmd)
        dataset_json = f"{dataset_prefix}_summary.json"
        if os.path.exists(dataset_json):
            dataset_payload = _read_json(dataset_json)

        dataset_npz = f"{dataset_prefix}.npz"
        train_cmd = [
            sys.executable,
            os.path.join(ROOT, "tools", "train_idp_residual_model.py"),
            "--input-npz",
            dataset_npz,
            "--device",
            str(args.device),
            "--out-checkpoint",
            train_ckpt,
            "--out-json",
            train_json,
            "--out-md",
            train_md,
        ]
        train_status = _run(train_cmd)
        if os.path.exists(train_json):
            train_payload = _read_json(train_json)

        if int(train_status.get("rc", 1)) == 0 and os.path.exists(train_ckpt):
            eval_residual_cmd = [
                sys.executable,
                os.path.join(ROOT, "tools", "run_idp_3bead_evaluator.py"),
                "--config-json",
                str(args.config_json),
                "--device",
                str(args.device),
                "--residual-checkpoint",
                train_ckpt,
                "--residual-device",
                str(args.device),
                "--date-tag",
                date_tag,
                "--out-prefix",
                f"{out_prefix}_eval_residual",
            ]
            eval_residual_status = _run(eval_residual_cmd)
            if os.path.exists(eval_residual_json):
                eval_residual_payload = _read_json(eval_residual_json)

            gate_residual_cmd = [
                sys.executable,
                os.path.join(ROOT, "tools", "run_idp_3bead_benchmark_gate.py"),
                "--config-json",
                str(args.config_json),
                "--eval-json",
                eval_residual_json,
                "--out-json",
                gate_residual_json,
                "--out-md",
                f"{out_prefix}_gate_residual_summary.md",
            ]
            gate_residual_status = _run(gate_residual_cmd)
            if os.path.exists(gate_residual_json):
                gate_residual_payload = _read_json(gate_residual_json)

        branch_cmd = [
            sys.executable,
            os.path.join(ROOT, "tools", "build_idp_branch_feature_report.py"),
            "--config-json",
            str(args.config_json),
            "--eval-json",
            eval_residual_json if os.path.exists(eval_residual_json) else eval_json,
            "--out-prefix",
            f"{out_prefix}_branch_report",
        ]
        branch_status = _run(branch_cmd)
        if os.path.exists(branch_report_json):
            branch_payload = _read_json(branch_report_json)

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "config_json": str(args.config_json),
        "device": str(args.device),
        "date_tag": date_tag,
        "eval": {"status": eval_status, "payload": eval_payload},
        "gate": {"status": gate_status, "payload": gate_payload},
        "dataset": {"status": dataset_status, "payload": dataset_payload},
        "residual_train": {"status": train_status, "payload": train_payload},
        "eval_residual": {"status": eval_residual_status, "payload": eval_residual_payload},
        "gate_residual": {"status": gate_residual_status, "payload": gate_residual_payload},
        "branch_report": {"status": branch_status, "payload": branch_payload},
    }
    baseline_ok = bool(
        int(eval_status.get("rc", 1)) == 0
        and int(gate_status.get("rc", 1)) == 0
        and int(dataset_status.get("rc", 1)) == 0
        and int(train_status.get("rc", 1)) == 0
    )
    def _rc_ok(status: dict[str, object]) -> bool:
        try:
            return int(status.get("rc", 1) or 1) == 0
        except (TypeError, ValueError):
            return False

    corrected_available = _rc_ok(eval_residual_status) and _rc_ok(gate_residual_status)
    payload["pass"] = bool(
        (corrected_available and bool(gate_residual_payload.get("pass", False)))
        or (not corrected_available and baseline_ok)
    )
    payload["baseline_pass"] = bool(gate_payload.get("pass", False))
    payload["residual_pass"] = bool(gate_residual_payload.get("pass", False)) if corrected_available else None

    with open(final_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    with open(final_md, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    "# IDP 3-Bead Pipeline",
                    "",
                    f"- pass: {payload['pass']}",
                    f"- config_json: `{args.config_json}`",
                    f"- eval_json: `{eval_json}`",
                    f"- gate_json: `{gate_json}`",
                    f"- dataset_npz: `{dataset_prefix}.npz`",
                    f"- residual_checkpoint: `{train_ckpt}`",
                    f"- eval_residual_json: `{eval_residual_json}`",
                    f"- gate_residual_json: `{gate_residual_json}`",
                    f"- branch_report_json: `{branch_report_json}`",
                    f"- baseline_pass: `{payload['baseline_pass']}`",
                    f"- residual_pass: `{payload['residual_pass']}`",
                ]
            )
            + "\n"
        )
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run IDP 3-bead evaluator -> gate -> residual learning pipeline.")
    p.add_argument("--config-json", type=str, required=True)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--out-prefix", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_pipeline(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not bool(payload.get("pass", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
