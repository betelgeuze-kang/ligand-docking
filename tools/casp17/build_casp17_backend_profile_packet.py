#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import shlex
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUT_JSON = "runs/casp17_backend_profile_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_backend_profile_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_backend_profile_packet_current.md"
DEFAULT_LAUNCH_JSON = "runs/casp17_all_protein_prediction_launch_custom_ready_current.json"
DEFAULT_BATCH_JSON = "runs/casp17_all_protein_prediction_batch_gate_current.json"
ENV_COMMAND_TEMPLATE = "CASP17_STRUCTURE_PREDICTOR_COMMAND"


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


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else ""


def _shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)


def _adapter_command(args: argparse.Namespace) -> str:
    parts = [
        "python3",
        "tools/casp17/run_casp17_external_structure_predictor_adapter.py",
        "--target-id",
        "{target_id}",
        "--fasta",
        "{fasta}",
        "--out-dir",
        "{out_dir}",
        "--raw-pdb",
        "{raw_pdb}",
    ]
    if args.embed_predictor_template and _text(args.predictor_command_template):
        parts.extend(["--predictor-command-template", _text(args.predictor_command_template)])
    return _shell_join(parts)


def _launch_command(args: argparse.Namespace, custom_backend_command: str) -> str:
    parts = [
        "python3",
        "tools/casp17/build_casp17_prediction_launch_packet.py",
        "--target-scope",
        "all_protein",
        "--target-limit",
        "0",
        "--allow-deadline-close",
        "--custom-backend-command",
        custom_backend_command,
        "--out-json",
        args.launch_json,
        "--out-csv",
        args.launch_csv,
        "--out-md",
        args.launch_md,
    ]
    if args.supports_multimer:
        parts.insert(parts.index("--custom-backend-command"), "--backend-supports-multimer")
    if args.max_chains > 0:
        parts.extend(["--backend-max-chains", str(args.max_chains)])
    if args.max_residues > 0:
        parts.extend(["--backend-max-residues", str(args.max_residues)])
    return _shell_join(parts)


def _batch_plan_command(args: argparse.Namespace) -> str:
    return _shell_join(
        [
            "python3",
            "tools/casp17/run_casp17_prediction_batch_gate.py",
            "--launch-packet-json",
            args.launch_json,
            "--out-json",
            args.batch_json,
            "--out-csv",
            args.batch_csv,
            "--out-md",
            args.batch_md,
        ]
    )


def _batch_execute_command(args: argparse.Namespace) -> str:
    return _shell_join(
        [
            "python3",
            "tools/casp17/run_casp17_prediction_batch_gate.py",
            "--launch-packet-json",
            args.launch_json,
            "--execute",
            "--author-code",
            "<CASP_AUTHOR_CODE>",
        ]
    )


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    template = _text(args.predictor_command_template)
    env_present = bool(_text(os.environ.get(ENV_COMMAND_TEMPLATE)))
    embedded = bool(args.embed_predictor_template and template)
    operator_template_source = "embedded_argument" if embedded else ("environment" if env_present else "missing")
    custom_backend_command = _adapter_command(args)
    blockers: list[str] = []
    if not args.supports_multimer:
        blockers.append("backend_multimer_support_not_declared")
    if operator_template_source == "missing":
        blockers.append("operator_predictor_command_template_missing")
    if not args.require_gpu:
        blockers.append("gpu_requirement_disabled_not_allowed_for_casp17")

    execution_status = "ready" if not blockers else "blocked"
    rows = [
        {
            "name": "custom_backend_command",
            "status": "available",
            "value": custom_backend_command,
        },
        {
            "name": "all_protein_launch_command",
            "status": "available",
            "value": _launch_command(args, custom_backend_command),
        },
        {
            "name": "batch_plan_command",
            "status": "available",
            "value": _batch_plan_command(args),
        },
        {
            "name": "batch_execute_command",
            "status": "blocked_until_author_code_and_predictor_ready" if execution_status == "blocked" else "available",
            "value": _batch_execute_command(args),
        },
    ]
    summary = {
        "packet_type": "casp17_backend_profile_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "profile_name": args.profile_name,
        "custom_backend_command": custom_backend_command,
        "supports_multimer": bool(args.supports_multimer),
        "max_chains": int(args.max_chains),
        "max_residues": int(args.max_residues),
        "require_gpu": bool(args.require_gpu),
        "operator_predictor_template_source": operator_template_source,
        "operator_predictor_template_present": operator_template_source != "missing",
        "operator_predictor_template_sha256": _sha256_text(template) if template else "",
        "execution_status": execution_status,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "env_command_template_name": ENV_COMMAND_TEMPLATE,
        "launch_json": _artifact(args.launch_json),
        "batch_json": _artifact(args.batch_json),
        "claim_boundary": "Backend profile and command wiring only; no dependency installation, prediction execution, validation, or CASP17 submission is performed.",
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["name", "status", "value"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Backend Profile Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- profile: `{summary['profile_name']}`",
        f"- execution status: `{summary['execution_status']}`",
        f"- supports multimer: `{summary['supports_multimer']}`",
        f"- max chains/residues: `{summary['max_chains']}/{summary['max_residues']}`",
        f"- require GPU: `{summary['require_gpu']}`",
        f"- operator predictor template source: `{summary['operator_predictor_template_source']}`",
        f"- blockers: `{';'.join(summary['blockers']) if summary['blockers'] else '-'}`",
        "",
        "## Commands",
        "",
        "| name | status | value |",
        "| --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['name']}` | `{row['status']}` | `{row['value']}` |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 all-protein backend profile and command wiring packet.")
    parser.add_argument("--profile-name", default="external_adapter")
    parser.add_argument("--predictor-command-template", default="")
    parser.add_argument("--embed-predictor-template", action="store_true")
    parser.add_argument("--supports-multimer", action="store_true")
    parser.add_argument("--max-chains", type=int, default=0)
    parser.add_argument("--max-residues", type=int, default=0)
    parser.add_argument("--require-gpu", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--launch-json", default=DEFAULT_LAUNCH_JSON)
    parser.add_argument("--launch-csv", default="runs/casp17_all_protein_prediction_launch_custom_ready_current.csv")
    parser.add_argument("--launch-md", default="runs/casp17_all_protein_prediction_launch_custom_ready_current.md")
    parser.add_argument("--batch-json", default=DEFAULT_BATCH_JSON)
    parser.add_argument("--batch-csv", default="runs/casp17_all_protein_prediction_batch_gate_current.csv")
    parser.add_argument("--batch-md", default="runs/casp17_all_protein_prediction_batch_gate_current.md")
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
