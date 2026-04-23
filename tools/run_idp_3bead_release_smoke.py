#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


ROOT = "/home/betelgeuze/분자동역학"
DEFAULT_SMOKE_HOLDOUTS = [
    "alpha_synuclein_full",
    "fus_lcd",
    "hnrnpa1_lcd",
    "tau_2n4r_fragment",
    "prion_like_polyq_control",
    "ews_lcd",
    "p27_kid",
]


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object: {path}")
    return payload


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _run(cmd: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "cmd": cmd,
        "rc": int(proc.returncode),
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-20:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-20:]),
    }


def _parse_holdouts(raw: str) -> List[str]:
    items = [x.strip() for x in str(raw).split(",")]
    return [x for x in items if x]


def _select_smoke_targets(
    config: Dict[str, Any],
    *,
    holdout_key: str,
    holdouts: Sequence[str],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    requested = [str(x).strip() for x in holdouts if str(x).strip()]
    targets = list(config.get("targets", []) or [])
    selected: List[Dict[str, Any]] = []
    present = set()
    for holdout in requested:
        bucket = [copy.deepcopy(t) for t in targets if str(t.get(holdout_key, t.get("name", ""))).strip() == holdout]
        if bucket:
            present.add(holdout)
            selected.extend(bucket)
    missing = [x for x in requested if x not in present]
    return selected, missing


def _build_smoke_baseline_manifest(
    baseline_manifest_json: str,
    *,
    holdouts: Sequence[str],
    out_json: str,
) -> Dict[str, Any]:
    baseline = _load_json(str(baseline_manifest_json))
    requested = [str(x).strip() for x in holdouts if str(x).strip()]
    artifacts = list(baseline.get("fold_artifacts", []) or [])
    by_holdout = {str(art.get("holdout", "")).strip(): art for art in artifacts}

    filtered: List[Dict[str, Any]] = []
    missing: List[str] = []
    for idx, holdout in enumerate(requested, start=1):
        art = by_holdout.get(holdout)
        if not art:
            missing.append(holdout)
            continue
        row = dict(art)
        row["source_fold_index"] = art.get("fold_index")
        row["fold_index"] = idx
        filtered.append(row)

    if missing:
        raise ValueError(f"baseline manifest missing smoke holdouts: {missing}")

    corrected_pass_folds = sum(int(bool(x.get("corrected_gate_pass", False))) for x in filtered)
    baseline_pass_folds = sum(int(bool(x.get("baseline_gate_pass", False))) for x in filtered)
    fold_count = len(filtered)

    payload = copy.deepcopy(baseline)
    payload["release_kind"] = "idp_3bead_smoke_baseline"
    payload["release_label"] = f"{baseline.get('release_label', 'baseline')}_smoke"
    payload["smoke_holdouts"] = requested
    payload["acceptance"] = {
        "pass": bool(corrected_pass_folds == fold_count),
        "all_fold_pass": bool(corrected_pass_folds == fold_count),
        "combined_gate_pass": bool(baseline.get("acceptance", {}).get("combined_gate_pass", False)),
        "fold_count": fold_count,
        "baseline_pass_folds": baseline_pass_folds,
        "corrected_pass_folds": corrected_pass_folds,
    }
    payload["fold_artifacts"] = filtered
    _write_json(str(out_json), payload)
    return payload


def run_smoke(args: argparse.Namespace) -> Dict[str, Any]:
    holdouts = _parse_holdouts(args.holdouts) or list(DEFAULT_SMOKE_HOLDOUTS)
    config_json = str(args.config_json)
    baseline_manifest_json = str(args.baseline_manifest_json)
    frozen_labels_manifest_json = (
        str(getattr(args, "frozen_labels_manifest_json", "")).strip() or baseline_manifest_json
    )
    out_prefix = str(args.out_prefix).strip() or f"runs/idp_3bead_release_smoke_{dt.date.today().isoformat()}"
    smoke_config_json = str(args.smoke_config_json).strip() or f"{out_prefix}_config.json"
    smoke_baseline_manifest_json = str(args.smoke_baseline_manifest_json).strip() or f"{out_prefix}_baseline_manifest.json"
    smoke_regression_json = str(args.smoke_regression_json).strip() or f"{out_prefix}_release_regression.json"
    smoke_regression_md = str(args.smoke_regression_md).strip() or (
        smoke_regression_json[:-5] + ".md" if smoke_regression_json.endswith(".json") else smoke_regression_json + ".md"
    )
    smoke_candidate_eval_json = str(args.smoke_candidate_eval_json).strip() or f"{out_prefix}_release_candidate_eval.json"
    smoke_candidate_eval_md = str(args.smoke_candidate_eval_md).strip() or (
        smoke_candidate_eval_json[:-5] + ".md"
        if smoke_candidate_eval_json.endswith(".json")
        else smoke_candidate_eval_json + ".md"
    )
    smoke_runner_json = str(args.out_json).strip() or f"{out_prefix}_runner.json"
    smoke_runner_md = str(args.out_md).strip() or (
        smoke_runner_json[:-5] + ".md" if smoke_runner_json.endswith(".json") else smoke_runner_json + ".md"
    )

    base_cfg = _load_json(config_json)
    selected_targets, missing_holdouts = _select_smoke_targets(
        base_cfg,
        holdout_key=str(args.holdout_key),
        holdouts=holdouts,
    )
    if missing_holdouts:
        raise ValueError(f"smoke holdouts not present in config: {missing_holdouts}")

    smoke_cfg = copy.deepcopy(base_cfg)
    smoke_cfg["targets"] = selected_targets
    _write_json(smoke_config_json, smoke_cfg)

    smoke_baseline_manifest = _build_smoke_baseline_manifest(
        baseline_manifest_json,
        holdouts=holdouts,
        out_json=smoke_baseline_manifest_json,
    )

    pipeline_cmd = [
        sys.executable,
        os.path.join(ROOT, "tools", "run_idp_3bead_holdout_pipeline.py"),
        "--config-json",
        smoke_config_json,
        "--device",
        str(args.device),
        "--holdout-key",
        str(args.holdout_key),
        "--out-prefix",
        out_prefix,
        "--resume-existing",
        str(int(args.resume_existing)),
        "--baseline-manifest-json",
        smoke_baseline_manifest_json,
        "--frozen-labels-manifest-json",
        frozen_labels_manifest_json,
        "--release-regression-json",
        smoke_regression_json,
        "--release-regression-md",
        smoke_regression_md,
        "--release-candidate-eval-json",
        smoke_candidate_eval_json,
        "--release-candidate-eval-md",
        smoke_candidate_eval_md,
        "--release-label",
        str(args.release_label).strip() or os.path.basename(out_prefix),
    ]
    pipeline_status = _run(pipeline_cmd)

    summary_json = f"{out_prefix}_summary.json"
    payload: Dict[str, Any] = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "config_json": config_json,
        "baseline_manifest_json": baseline_manifest_json,
        "frozen_labels_manifest_json": frozen_labels_manifest_json,
        "smoke_holdouts": holdouts,
        "smoke_config_json": smoke_config_json,
        "smoke_baseline_manifest_json": smoke_baseline_manifest_json,
        "smoke_baseline_acceptance": smoke_baseline_manifest.get("acceptance", {}),
        "out_prefix": out_prefix,
        "pipeline": pipeline_status,
        "summary_json": summary_json,
        "release_regression_json": smoke_regression_json,
        "release_candidate_eval_json": smoke_candidate_eval_json,
    }
    if os.path.exists(summary_json):
        payload["summary"] = _load_json(summary_json)
    if os.path.exists(smoke_regression_json):
        payload["regression"] = _load_json(smoke_regression_json)
    if os.path.exists(smoke_candidate_eval_json):
        payload["candidate_eval"] = _load_json(smoke_candidate_eval_json)

    payload["pass"] = bool(payload.get("summary", {}).get("pass", False)) and bool(
        payload.get("regression", {}).get("summary", {}).get("pass", False)
    )

    _write_json(smoke_runner_json, payload)
    Path(smoke_runner_md).parent.mkdir(parents=True, exist_ok=True)
    with open(smoke_runner_md, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    "# IDP 3-Bead Release Smoke",
                    "",
                    f"- pass: {payload['pass']}",
                    f"- smoke_holdouts: {', '.join(holdouts)}",
                    f"- config_json: `{config_json}`",
                    f"- baseline_manifest_json: `{baseline_manifest_json}`",
                    f"- smoke_config_json: `{smoke_config_json}`",
                    f"- smoke_baseline_manifest_json: `{smoke_baseline_manifest_json}`",
                    f"- summary_json: `{summary_json}`",
                    f"- release_regression_json: `{smoke_regression_json}`",
                    f"- release_candidate_eval_json: `{smoke_candidate_eval_json}`",
                ]
            )
            + "\n"
        )
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run a short smoke holdout regression against the current IDP release baseline.")
    p.add_argument("--config-json", type=str, default="config/idp_3bead_benchmark_v7.json")
    p.add_argument("--baseline-manifest-json", type=str, default="runs/idp_3bead_release_manifest_current.json")
    p.add_argument("--frozen-labels-manifest-json", type=str, default="")
    p.add_argument("--holdout-key", type=str, default="split_group")
    p.add_argument("--holdouts", type=str, default=",".join(DEFAULT_SMOKE_HOLDOUTS))
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--out-prefix", type=str, default="")
    p.add_argument("--release-label", type=str, default="")
    p.add_argument("--resume-existing", type=int, default=1)
    p.add_argument("--smoke-config-json", type=str, default="")
    p.add_argument("--smoke-baseline-manifest-json", type=str, default="")
    p.add_argument("--smoke-regression-json", type=str, default="")
    p.add_argument("--smoke-regression-md", type=str, default="")
    p.add_argument("--smoke-candidate-eval-json", type=str, default="")
    p.add_argument("--smoke-candidate-eval-md", type=str, default="")
    p.add_argument("--out-json", type=str, default="")
    p.add_argument("--out-md", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_smoke(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not bool(payload.get("pass", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
