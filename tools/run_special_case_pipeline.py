#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd


DOMAIN_ORDER = ["metal", "dna", "membrane"]
DOMAIN_SOURCE_DEFAULTS = {
    "metal": "config/structure_sources_special_metal.csv",
    "dna": "config/structure_sources_special_dna.csv",
    "membrane": "config/structure_sources_special_membrane.csv",
}


def _now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _read_json_if_exists(path: str) -> Dict[str, Any]:
    src = str(path).strip()
    if not src or (not os.path.exists(src)):
        return {}
    try:
        with open(src, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _run_cmd(cmd: List[str], env: Dict[str, str]) -> Dict[str, Any]:
    started = time.time()
    proc = subprocess.run(cmd, env=env, text=True, capture_output=True)
    ended = time.time()
    return {
        "cmd": list(cmd),
        "cmd_str": " ".join(cmd),
        "returncode": int(proc.returncode),
        "ok": bool(proc.returncode == 0),
        "duration_sec": float(max(0.0, ended - started)),
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-80:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-80:]),
    }


def _append_step(
    records: List[Dict[str, Any]],
    *,
    stage: str,
    scope: str,
    name: str,
    run_result: Dict[str, Any],
    outputs: Dict[str, Any],
    pass_flag: bool,
    reason: str = "",
) -> None:
    rec = dict(run_result)
    rec["index"] = int(len(records) + 1)
    rec["stage"] = str(stage)
    rec["scope"] = str(scope)
    rec["name"] = str(name)
    rec["outputs"] = dict(outputs or {})
    rec["pass"] = bool(pass_flag)
    rec["reason"] = str(reason or "")
    records.append(rec)


def _parse_domains(spec: str) -> List[str]:
    s = str(spec).strip().lower()
    if (not s) or (s == "all"):
        return list(DOMAIN_ORDER)
    requested = [x.strip().lower() for x in s.split(",") if x.strip()]
    out: List[str] = []
    for domain in DOMAIN_ORDER:
        if domain in requested:
            out.append(domain)
    for domain in requested:
        if domain not in out and domain in DOMAIN_ORDER:
            out.append(domain)
    if not out:
        raise ValueError(f"no valid domains in --domains={spec}; allowed: {DOMAIN_ORDER}")
    return out


def _run_scope_list(run_scope: str) -> List[str]:
    s = str(run_scope).strip().lower()
    if s == "smoke_only":
        return ["smoke"]
    if s == "full_only":
        return ["full"]
    return ["smoke", "full"]


def _targets_for_scope(source_csv: str, scope: str) -> str:
    if not os.path.exists(source_csv):
        return "all"
    try:
        df = pd.read_csv(source_csv)
    except Exception:
        return "all"
    if "target" not in df.columns:
        return "all"
    values = [str(x).strip() for x in df["target"].astype(str).tolist() if str(x).strip()]
    if not values:
        return "all"
    if scope == "smoke":
        return values[0]
    return ",".join(values)


def _copy_latest_domain_artifacts(
    *,
    date_tag: str,
    domain: str,
    preferred_gate_prefix: str,
) -> Dict[str, str]:
    out_json = f"runs/special_case_{domain}_{date_tag}_summary.json"
    out_csv = f"runs/special_case_{domain}_{date_tag}_summary.csv"
    out_md = f"runs/special_case_{domain}_{date_tag}_summary.md"
    copied = {"summary_json": out_json, "summary_csv": out_csv, "summary_md": out_md}
    src_json = f"{preferred_gate_prefix}.json"
    src_csv = f"{preferred_gate_prefix}.csv"
    src_md = f"{preferred_gate_prefix}.md"
    for src, dst in [(src_json, out_json), (src_csv, out_csv), (src_md, out_md)]:
        if os.path.exists(src):
            _ensure_parent(dst)
            shutil.copyfile(src, dst)
    return copied


def run_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    out_prefix = str(args.out_prefix).strip() or f"runs/special_case_pipeline_{date_tag}"
    summary_json = f"{out_prefix}_summary.json"
    summary_md = f"{out_prefix}_summary.md"
    steps_csv = f"{out_prefix}_steps.csv"
    policy_json = str(args.policy_json).strip()
    if not policy_json:
        raise ValueError("--policy-json is required")

    domains = _parse_domains(str(args.domains))
    scopes = _run_scope_list(str(args.run_scope))
    env = os.environ.copy()
    env["FORCE_RUST_HIP"] = "1"
    env["RUST_HIP_USE_GPU_NBLIST_BUILDER"] = "1"
    env.setdefault("NBLIST_AUTOGROW", "1")
    env.setdefault("RUST_HIP_NBLIST_AUTOGROW", "1")

    records: List[Dict[str, Any]] = []
    failed_stage = ""
    failed_reason = ""
    exit_code = 0

    core_gate_json = str(args.core_gate_json).strip() or f"{out_prefix}_core_gate.json"
    core_gate_csv = str(args.core_gate_csv).strip() or f"{out_prefix}_core_gate.csv"

    if not bool(args.skip_core_gate):
        parity_prefix = f"{out_prefix}_core_gate_parity"
        stage2_prefix = f"{out_prefix}_core_gate_stage2"
        bench_csv = f"{out_prefix}_core_gate_bench.csv"
        core_cmd = [
            sys.executable,
            "tools/validate_accuracy_gate.py",
            "--targets",
            str(args.gate_targets),
            "--samples",
            str(int(args.gate_samples)),
            "--noise",
            str(float(args.gate_noise)),
            "--steps",
            str(int(args.gate_steps)),
            "--runs",
            str(int(args.gate_runs)),
            "--warmup-steps",
            str(int(args.gate_warmup_steps)),
            "--strict-mode",
            "--enforce-speed-gate",
            "--jaccard-threshold",
            str(float(args.gate_jaccard_threshold)),
            "--e2e-rmse-threshold",
            str(float(args.gate_e2e_rmse_threshold)),
            "--rel-rmse-threshold",
            str(float(args.gate_rel_rmse_threshold)),
            "--speedup-threshold",
            str(float(args.gate_speedup_threshold)),
            "--out-json",
            core_gate_json,
            "--out-csv",
            core_gate_csv,
            "--parity-prefix",
            parity_prefix,
            "--stage2-prefix",
            stage2_prefix,
            "--benchmark-csv",
            bench_csv,
        ]
        core_run = _run_cmd(core_cmd, env=env)
        core_payload = _read_json_if_exists(core_gate_json)
        core_pass = bool(core_payload.get("summary", {}).get("pass", False))
        _append_step(
            records,
            stage="stage1_core_gate",
            scope="core",
            name="validate_accuracy_gate",
            run_result=core_run,
            outputs={
                "core_gate_json": core_gate_json,
                "core_gate_csv": core_gate_csv,
                "parity_prefix": parity_prefix,
                "stage2_prefix": stage2_prefix,
            },
            pass_flag=core_pass,
            reason="" if core_pass else "core_gate_pass=false",
        )
        if not core_pass:
            failed_stage = "stage1_core_gate"
            failed_reason = "core_gate_failed"
            exit_code = 2

    strict_summary_json = str(args.strict_summary_json).strip()
    if exit_code == 0 and bool(args.skip_core_gate):
        gate_ok = True
        if core_gate_json and os.path.exists(core_gate_json):
            core_payload = _read_json_if_exists(core_gate_json)
            gate_ok = bool(core_payload.get("summary", {}).get("pass", False))
        if strict_summary_json and os.path.exists(strict_summary_json):
            strict_payload = _read_json_if_exists(strict_summary_json)
            gate_ok = bool(gate_ok and strict_payload.get("summary", {}).get("pass", False))
        _append_step(
            records,
            stage="stage1_core_gate",
            scope="core",
            name="skip_core_gate",
            run_result={
                "cmd": [],
                "cmd_str": "skip_core_gate",
                "returncode": 0 if gate_ok else 2,
                "ok": gate_ok,
                "duration_sec": 0.0,
                "stdout_tail": "",
                "stderr_tail": "",
            },
            outputs={
                "core_gate_json": core_gate_json if core_gate_json else None,
                "strict_summary_json": strict_summary_json if strict_summary_json else None,
            },
            pass_flag=gate_ok,
            reason="" if gate_ok else "provided_core_or_strict_summary_failed",
        )
        if not gate_ok:
            failed_stage = "stage1_core_gate"
            failed_reason = "provided_core_or_strict_summary_failed"
            exit_code = 2

    stage_results: Dict[str, Dict[str, Any]] = {}

    def _domain_source(domain: str) -> str:
        val = str(getattr(args, f"{domain}_sources_csv")).strip()
        return val or DOMAIN_SOURCE_DEFAULTS[domain]

    if exit_code == 0:
        for domain in domains:
            stage_key = f"stage_{domain}"
            stage_results[stage_key] = {"smoke": {}, "full": {}, "pass": False}
            domain_source_csv = _domain_source(domain)

            for scope in scopes:
                targets_spec = _targets_for_scope(domain_source_csv, scope=scope)
                stage_prefix = f"{out_prefix}_{domain}_{scope}"
                manifest_csv = f"{stage_prefix}_manifest.csv"
                manifest_json = f"{stage_prefix}_manifest.json"
                labels_csv = f"{stage_prefix}_labels.csv"
                labels_json = f"{stage_prefix}_labels.json"
                gate_json = f"{stage_prefix}_gate.json"
                gate_csv = f"{stage_prefix}_gate.csv"
                gate_md = f"{stage_prefix}_gate.md"

                # 1) Build manifest
                cmd_manifest = [
                    sys.executable,
                    "tools/build_special_case_manifest.py",
                    "--domain",
                    domain,
                    "--targets",
                    targets_spec,
                    "--source-csv",
                    domain_source_csv,
                    "--out-manifest",
                    manifest_csv,
                    "--out-json",
                    manifest_json,
                ]
                run_manifest = _run_cmd(cmd_manifest, env=env)
                ok_manifest = bool(run_manifest.get("ok", False))
                _append_step(
                    records,
                    stage=stage_key,
                    scope=scope,
                    name=f"{domain}_{scope}_build_manifest",
                    run_result=run_manifest,
                    outputs={"manifest_csv": manifest_csv, "manifest_json": manifest_json},
                    pass_flag=ok_manifest,
                    reason="" if ok_manifest else "build_manifest_failed",
                )
                if not ok_manifest:
                    failed_stage = f"{stage_key}_{scope}"
                    failed_reason = "build_manifest_failed"
                    exit_code = 3
                    break

                # 2) Extract labels
                cmd_labels = [
                    sys.executable,
                    "tools/extract_special_case_labels.py",
                    "--domain",
                    domain,
                    "--manifest-csv",
                    manifest_csv,
                    "--out-csv",
                    labels_csv,
                    "--out-json",
                    labels_json,
                ]
                run_labels = _run_cmd(cmd_labels, env=env)
                ok_labels = bool(run_labels.get("ok", False))
                _append_step(
                    records,
                    stage=stage_key,
                    scope=scope,
                    name=f"{domain}_{scope}_extract_labels",
                    run_result=run_labels,
                    outputs={"labels_csv": labels_csv, "labels_json": labels_json},
                    pass_flag=ok_labels,
                    reason="" if ok_labels else "extract_labels_failed",
                )
                if not ok_labels:
                    failed_stage = f"{stage_key}_{scope}"
                    failed_reason = "extract_labels_failed"
                    exit_code = 3
                    break

                # 3) Validate gate
                cmd_gate = [
                    sys.executable,
                    "tools/validate_special_case_gate.py",
                    "--domain",
                    domain,
                    "--manifest-csv",
                    manifest_csv,
                    "--labels-json",
                    labels_json,
                    "--policy-json",
                    policy_json,
                    "--out-json",
                    gate_json,
                    "--out-csv",
                    gate_csv,
                    "--out-md",
                    gate_md,
                ]
                if core_gate_json and os.path.exists(core_gate_json):
                    cmd_gate.extend(["--core-gate-json", core_gate_json])
                if strict_summary_json and os.path.exists(strict_summary_json):
                    cmd_gate.extend(["--strict-summary-json", strict_summary_json])
                run_gate = _run_cmd(cmd_gate, env=env)
                gate_payload = _read_json_if_exists(gate_json)
                gate_pass = bool(gate_payload.get("summary", {}).get("pass", False))
                stage_results[stage_key][scope] = {
                    "pass": gate_pass,
                    "manifest_csv": manifest_csv,
                    "labels_json": labels_json,
                    "gate_json": gate_json,
                    "gate_csv": gate_csv,
                    "gate_md": gate_md,
                }
                _append_step(
                    records,
                    stage=stage_key,
                    scope=scope,
                    name=f"{domain}_{scope}_validate_gate",
                    run_result=run_gate,
                    outputs={"gate_json": gate_json, "gate_csv": gate_csv, "gate_md": gate_md},
                    pass_flag=gate_pass,
                    reason="" if gate_pass else "special_case_gate_failed",
                )
                if not gate_pass:
                    failed_stage = f"{stage_key}_{scope}"
                    failed_reason = "special_case_gate_failed"
                    exit_code = 3
                    break

                if (scope == "smoke") and (not gate_pass):
                    # Explicit smoke->full rule.
                    failed_stage = f"{stage_key}_smoke"
                    failed_reason = "smoke_failed"
                    exit_code = 3
                    break

            # Per-domain pass.
            smoke_pass = bool(stage_results[stage_key].get("smoke", {}).get("pass", False))
            smoke_required = "smoke" in scopes
            full_required = "full" in scopes
            full_pass = bool(stage_results[stage_key].get("full", {}).get("pass", False)) if full_required else True
            stage_results[stage_key]["pass"] = bool(
                ((not smoke_required) or smoke_pass) and ((not full_required) or full_pass)
            )

            # Canonical artifacts per domain.
            preferred_scope = "full" if ("full" in scopes and full_pass) else "smoke"
            preferred_gate_json = stage_results[stage_key].get(preferred_scope, {}).get("gate_json", "")
            preferred_gate_prefix = str(preferred_gate_json).rsplit(".json", 1)[0] if preferred_gate_json else ""
            if preferred_gate_prefix:
                copied = _copy_latest_domain_artifacts(
                    date_tag=date_tag,
                    domain=domain,
                    preferred_gate_prefix=preferred_gate_prefix,
                )
                stage_results[stage_key]["published"] = copied

            if exit_code != 0 and bool(args.strict_fail_fast):
                break

    pass_all = bool(exit_code == 0)
    payload = {
        "generated_at_local": _now_iso(),
        "date_tag": date_tag,
        "domains": domains,
        "run_scope": str(args.run_scope),
        "pass": pass_all,
        "exit_code": int(exit_code),
        "failed_stage": failed_stage or None,
        "failed_reason": failed_reason or None,
        "core": {
            "skip_core_gate": bool(args.skip_core_gate),
            "core_gate_json": core_gate_json,
            "core_gate_csv": core_gate_csv,
            "strict_summary_json": strict_summary_json or None,
        },
        "stages": stage_results,
        "steps": records,
        "artifacts": {
            "summary_json": summary_json,
            "summary_md": summary_md,
            "steps_csv": steps_csv,
        },
    }

    _ensure_parent(summary_json)
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    pd.DataFrame(records).to_csv(steps_csv, index=False)

    _ensure_parent(summary_md)
    lines = [
        "# Special Case Pipeline Summary",
        "",
        f"- generated_at_local: `{payload['generated_at_local']}`",
        f"- date_tag: `{payload['date_tag']}`",
        f"- run_scope: `{payload['run_scope']}`",
        f"- pass: `{payload['pass']}`",
        f"- exit_code: `{payload['exit_code']}`",
        f"- failed_stage: `{payload['failed_stage']}`",
        "",
        "## Domains",
    ]
    for domain in domains:
        key = f"stage_{domain}"
        info = stage_results.get(key, {})
        lines.append(f"- {domain}: `{info.get('pass')}`")
        if "smoke" in scopes:
            lines.append(f"  smoke: `{info.get('smoke', {}).get('pass')}`")
        if "full" in scopes:
            lines.append(f"  full: `{info.get('full', {}).get('pass')}`")
    lines.extend(
        [
            "",
            "## Artifacts",
            f"- summary_json: `{summary_json}`",
            f"- summary_md: `{summary_md}`",
            f"- steps_csv: `{steps_csv}`",
        ]
    )
    with open(summary_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run special-case domain coverage pipeline (metal -> dna -> membrane)."
    )
    p.add_argument("--date-tag", type=str, default=dt.date.today().isoformat())
    p.add_argument("--domains", type=str, default="metal,dna,membrane")
    p.add_argument(
        "--run-scope",
        type=str,
        default="smoke_then_full",
        choices=["smoke_then_full", "smoke_only", "full_only"],
    )
    p.add_argument("--strict-fail-fast", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--out-prefix", type=str, default="")

    p.add_argument(
        "--policy-json",
        type=str,
        default="config/special_case_gate_policy_v1_2026-02-18.json",
    )
    p.add_argument("--metal-sources-csv", type=str, default=DOMAIN_SOURCE_DEFAULTS["metal"])
    p.add_argument("--dna-sources-csv", type=str, default=DOMAIN_SOURCE_DEFAULTS["dna"])
    p.add_argument("--membrane-sources-csv", type=str, default=DOMAIN_SOURCE_DEFAULTS["membrane"])

    p.add_argument("--skip-core-gate", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--core-gate-json", type=str, default="")
    p.add_argument("--core-gate-csv", type=str, default="")
    p.add_argument("--strict-summary-json", type=str, default="")

    p.add_argument("--gate-targets", type=str, default="all")
    p.add_argument("--gate-samples", type=int, default=8)
    p.add_argument("--gate-noise", type=float, default=0.08)
    p.add_argument("--gate-steps", type=int, default=60)
    p.add_argument("--gate-runs", type=int, default=1)
    p.add_argument("--gate-warmup-steps", type=int, default=40)
    p.add_argument("--gate-jaccard-threshold", type=float, default=1.0)
    p.add_argument("--gate-e2e-rmse-threshold", type=float, default=0.35)
    p.add_argument("--gate-rel-rmse-threshold", type=float, default=1e-5)
    p.add_argument("--gate-speedup-threshold", type=float, default=12.0)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_pipeline(args)
    out = {
        "pass": bool(payload.get("pass", False)),
        "exit_code": int(payload.get("exit_code", 1)),
        "failed_stage": payload.get("failed_stage"),
        "summary_json": payload.get("artifacts", {}).get("summary_json"),
        "summary_md": payload.get("artifacts", {}).get("summary_md"),
        "steps_csv": payload.get("artifacts", {}).get("steps_csv"),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    if int(out["exit_code"]) != 0:
        sys.exit(int(out["exit_code"]))


if __name__ == "__main__":
    main()
