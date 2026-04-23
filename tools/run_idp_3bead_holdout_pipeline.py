#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence

ROOT = "/home/betelgeuze/분자동역학"
DEFAULT_PATCH_ENV = {
    "IDP_R11_ML_PATCH": "0",
    "IDP_R11_PHYS_PATCH": "0",
    "IDP_R12_ML_PATCH": "0",
    "IDP_R12_PHYS_PATCH": "0",
    "IDP_R13_ML_PATCH": "0",
    "IDP_R13_PHYS_PATCH": "0",
    "IDP_R14_ML_PATCH": "0",
    "IDP_R14_PHYS_PATCH": "1",
    "IDP_R15_ML_PATCH": "0",
    "IDP_R16_ML_PATCH": "1",
    "IDP_R17_PHYS_PATCH": "0",
    "IDP_R17_TAU_PH_SPLIT_PATCH": "0",
    "IDP_R18_TAU_PH_HELIX_RECOVERY_PATCH": "0",
}


def _run(cmd: List[str]) -> Dict[str, Any]:
    env = os.environ.copy()
    for key, value in DEFAULT_PATCH_ENV.items():
        env.setdefault(key, value)
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)
    return {
        "cmd": cmd,
        "rc": int(proc.returncode),
        "stdout_tail": "\n".join((proc.stdout or "").splitlines()[-20:]),
        "stderr_tail": "\n".join((proc.stderr or "").splitlines()[-20:]),
    }


def _is_retryable_gpu_fault(status: Dict[str, Any]) -> bool:
    if int(status.get("rc", 0) or 0) == 0:
        return False
    text = "\n".join(
        [
            str(status.get("stderr_tail", "") or ""),
            str(status.get("stdout_tail", "") or ""),
        ]
    ).lower()
    patterns = (
        "memory access fault by gpu",
        "hsa_status_error_memory_fault",
        "hiperrorillegaladdress",
        "hiperrorlaunchfailure",
        "launch failure",
        "page not present or supervisor privilege",
    )
    return any(pat in text for pat in patterns)


def _run_with_retry(
    cmd: List[str],
    *,
    stage_name: str,
    retry_gpu_faults: int = 0,
) -> Dict[str, Any]:
    status = _run(cmd)
    attempts: List[Dict[str, Any]] = [dict(status)]
    retries = 0
    while retries < retry_gpu_faults and _is_retryable_gpu_fault(status):
        retries += 1
        status = _run(cmd)
        attempts.append(dict(status))
    if retries:
        status["retry_count"] = retries
        status["attempts"] = attempts
        status["retry_stage_name"] = stage_name
    return status


def _with_patch_env(cmd: List[str]) -> List[str]:
    return cmd


def _append_kalman_shadow_args(cmd: List[str], args: argparse.Namespace) -> List[str]:
    if int(getattr(args, "kalman_shadow_enable", 0) or 0) <= 0:
        return cmd
    cmd.extend(
        [
            "--kalman-shadow-enable",
            str(int(getattr(args, "kalman_shadow_enable", 0) or 0)),
            "--kalman-shadow-mode",
            str(getattr(args, "kalman_shadow_mode", "identity") or "identity"),
            "--kalman-shadow-family-token",
            str(getattr(args, "kalman_shadow_family_token", "idp") or "idp"),
            "--kalman-shadow-obs-noise-scale",
            str(float(getattr(args, "kalman_shadow_obs_noise_scale", 0.0) or 0.0)),
            "--kalman-shadow-process-noise-scale",
            str(float(getattr(args, "kalman_shadow_process_noise_scale", 0.0) or 0.0)),
            "--kalman-shadow-delta-cap-frac",
            str(float(getattr(args, "kalman_shadow_delta_cap_frac", 0.25) or 0.25)),
            "--kalman-shadow-feature-mask",
            str(getattr(args, "kalman_shadow_feature_mask", "all") or "all"),
        ]
    )
    return cmd


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _require_outputs(
    status: Dict[str, Any],
    required_paths: Sequence[str],
    *,
    stage_name: str,
) -> bool:
    missing = [str(path) for path in required_paths if not os.path.exists(path)]
    if status.get("rc", 0) != 0 or missing:
        status["missing_outputs"] = missing
        status["stage_name"] = stage_name
        return False
    return True


def _subset_config(base: Dict[str, Any], targets: List[Dict[str, Any]], path: str) -> str:
    cfg = copy.deepcopy(base)
    cfg["targets"] = targets
    _write_json(path, cfg)
    return path


def _derive_targets_csv(eval_corrected_json: str) -> str:
    if eval_corrected_json.endswith("_summary.json"):
        return eval_corrected_json[: -len("_summary.json")] + "_targets.csv"
    return os.path.splitext(eval_corrected_json)[0] + "_targets.csv"


def _resolve_frozen_labels_csv(
    baseline_manifest_json: str,
    fold_idx: int,
    holdout: str,
) -> str:
    baseline_manifest_json = str(baseline_manifest_json).strip()
    if not baseline_manifest_json or not os.path.exists(baseline_manifest_json):
        return ""
    manifest = _read_json(baseline_manifest_json)
    artifacts = list(manifest.get("fold_artifacts", []))
    holdout = str(holdout).strip()

    def _artifact_csv(artifact: Dict[str, Any]) -> str:
        csv_path = str(artifact.get("eval_corrected_csv", "")).strip()
        if not csv_path:
            csv_path = _derive_targets_csv(str(artifact.get("eval_corrected_json", "")).strip())
        return csv_path if csv_path and os.path.exists(csv_path) else ""

    # Sentinel / subset runs reindex folds, so holdout-name matching must win.
    for artifact in artifacts:
        art_holdout = str(artifact.get("holdout", "")).strip()
        if art_holdout != holdout:
            continue
        csv_path = _artifact_csv(artifact)
        if csv_path:
            return csv_path

    # Fallback for older manifests that may not have a reliable holdout name.
    for artifact in artifacts:
        art_idx = int(artifact.get("fold_index", 0) or 0)
        if art_idx != int(fold_idx):
            continue
        csv_path = _artifact_csv(artifact)
        if csv_path:
            return csv_path
    return ""


def run_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    base_cfg = _read_json(str(args.config_json))
    targets = list(base_cfg.get("targets", []))
    groups = []
    seen = set()
    for t in targets:
        g = str(t.get(args.holdout_key, t.get("name", "")))
        if g not in seen:
            seen.add(g)
            groups.append(g)

    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    out_prefix = str(args.out_prefix).strip() or f"{ROOT}/runs/idp_3bead_holdout_{date_tag}"
    work_dir = f"{out_prefix}_fold_inputs"
    os.makedirs(work_dir, exist_ok=True)
    baseline_manifest_json = str(getattr(args, "baseline_manifest_json", "")).strip()
    frozen_labels_manifest_json = str(getattr(args, "frozen_labels_manifest_json", "")).strip() or baseline_manifest_json

    folds: List[Dict[str, Any]] = []
    combined_baseline_rows: List[Dict[str, Any]] = []
    combined_corrected_rows: List[Dict[str, Any]] = []
    baseline_template: Dict[str, Any] = {}
    corrected_template: Dict[str, Any] = {}

    for fold_idx, holdout in enumerate(groups, start=1):
        train_targets = [dict(t) for t in targets if str(t.get(args.holdout_key, t.get("name", ""))) != holdout]
        eval_targets = [dict(t) for t in targets if str(t.get(args.holdout_key, t.get("name", ""))) == holdout]
        fold_prefix = f"{out_prefix}_fold{fold_idx}_{holdout}"
        train_cfg = _subset_config(base_cfg, train_targets, os.path.join(work_dir, f"fold{fold_idx}_{holdout}_train.json"))
        eval_cfg = _subset_config(base_cfg, eval_targets, os.path.join(work_dir, f"fold{fold_idx}_{holdout}_eval.json"))
        train_eval_json = f"{fold_prefix}_train_eval_summary.json"
        train_dataset_prefix = f"{fold_prefix}_train_branch_dataset"
        ckpt = f"{ROOT}/models/idp_branch_holdout_{date_tag}_fold{fold_idx}_{holdout}.pt"
        eval_base_json = f"{fold_prefix}_eval_baseline_summary.json"
        eval_corr_json = f"{fold_prefix}_eval_corrected_summary.json"
        gate_base_json = f"{fold_prefix}_gate_baseline_summary.json"
        gate_corr_json = f"{fold_prefix}_gate_corrected_summary.json"
        frozen_labels_csv = _resolve_frozen_labels_csv(
            frozen_labels_manifest_json,
            fold_idx=fold_idx,
            holdout=str(holdout),
        )

        status: Dict[str, Any] = {}
        if bool(int(getattr(args, "resume_existing", 1))):
            completed_paths = [
                train_eval_json,
                f"{fold_prefix}_train_branch_summary.json",
                eval_base_json,
                eval_corr_json,
                gate_base_json,
                gate_corr_json,
            ]
            if all(os.path.exists(p) for p in completed_paths):
                eval_base_payload = _read_json(eval_base_json)
                eval_corr_payload = _read_json(eval_corr_json)
                gate_base_payload = _read_json(gate_base_json)
                gate_corr_payload = _read_json(gate_corr_json)
                status["resumed_existing"] = True
                for row in list(eval_base_payload.get("targets", [])):
                    row["holdout_fold"] = holdout
                    combined_baseline_rows.append(row)
                for row in list(eval_corr_payload.get("targets", [])):
                    row["holdout_fold"] = holdout
                    combined_corrected_rows.append(row)
                baseline_template = {k: v for k, v in eval_base_payload.items() if k not in {"targets", "target_count", "pass_count", "pass_fraction", "summary_json", "summary_md", "targets_csv"}}
                corrected_template = {k: v for k, v in eval_corr_payload.items() if k not in {"targets", "target_count", "pass_count", "pass_fraction", "summary_json", "summary_md", "targets_csv"}}
                folds.append(
                    {
                        "holdout": holdout,
                        "train_target_count": len(train_targets),
                        "eval_target_count": len(eval_targets),
                        "status": status,
                        "frozen_labels_csv": frozen_labels_csv,
                        "baseline_gate": gate_base_payload,
                        "corrected_gate": gate_corr_payload,
                        "pass": bool(gate_corr_payload.get("pass", False)),
                    }
                )
                continue
        train_branch_summary_json = f"{fold_prefix}_train_branch_summary.json"
        train_branch_summary_md = f"{fold_prefix}_train_branch_summary.md"
        train_dataset_npz = f"{train_dataset_prefix}.npz"
        train_dataset_rows = f"{train_dataset_prefix}_rows.csv"
        train_dataset_summary_json = f"{train_dataset_prefix}_summary.json"

        if os.path.exists(train_eval_json):
            status["train_eval"] = {"skipped_existing": True, "summary_json": train_eval_json}
        else:
            train_eval_cmd = [
                sys.executable, os.path.join(ROOT, "tools", "run_idp_3bead_evaluator.py"),
                "--config-json", train_cfg,
                "--device", str(args.device),
                "--date-tag", f"{date_tag}-fold{fold_idx}-train",
                "--out-prefix", f"{fold_prefix}_train_eval",
            ]
            _append_kalman_shadow_args(train_eval_cmd, args)
            status["train_eval"] = _run_with_retry(
                train_eval_cmd,
                stage_name="train_eval",
                retry_gpu_faults=1,
            )
            if not _require_outputs(status["train_eval"], [train_eval_json], stage_name="train_eval"):
                folds.append({"holdout": holdout, "status": status, "pass": False})
                continue

        if all(os.path.exists(p) for p in [train_dataset_npz, train_dataset_rows, train_dataset_summary_json]):
            status["dataset"] = {"skipped_existing": True, "npz": train_dataset_npz}
        else:
            dataset_cmd = [
                sys.executable, os.path.join(ROOT, "tools", "build_idp_branch_dataset.py"),
                "--eval-json", train_eval_json,
                "--taxonomy-json", str(base_cfg.get("runtime", {}).get("idp_branch_taxonomy_json", os.path.join(ROOT, "config", "idp_branch_taxonomy_v1.json"))),
                "--out-prefix", train_dataset_prefix,
            ]
            status["dataset"] = _run(dataset_cmd)
            if not _require_outputs(
                status["dataset"],
                [train_dataset_npz, train_dataset_rows, train_dataset_summary_json],
                stage_name="dataset",
            ):
                folds.append({"holdout": holdout, "status": status, "pass": False})
                continue

        if all(os.path.exists(p) for p in [ckpt, train_branch_summary_json, train_branch_summary_md]):
            status["train"] = {"skipped_existing": True, "checkpoint": ckpt}
        else:
            train_cmd = [
                sys.executable, os.path.join(ROOT, "tools", "train_idp_branch_model.py"),
                "--input-npz", train_dataset_npz,
                "--device", str(args.device),
                "--seed", "42",
                "--out-checkpoint", ckpt,
                "--out-json", train_branch_summary_json,
                "--out-md", train_branch_summary_md,
            ]
            status["train"] = _run(train_cmd)
            if not _require_outputs(
                status["train"],
                [ckpt, train_branch_summary_json, train_branch_summary_md],
                stage_name="train",
            ):
                folds.append({"holdout": holdout, "status": status, "pass": False})
                continue

        if os.path.exists(eval_base_json):
            status["eval_baseline"] = {"skipped_existing": True, "summary_json": eval_base_json}
        else:
            eval_base_cmd = [
                sys.executable, os.path.join(ROOT, "tools", "run_idp_3bead_evaluator.py"),
                "--config-json", eval_cfg,
                "--device", str(args.device),
                "--date-tag", f"{date_tag}-fold{fold_idx}-eval-base",
                "--out-prefix", f"{fold_prefix}_eval_baseline",
            ]
            _append_kalman_shadow_args(eval_base_cmd, args)
            if frozen_labels_csv:
                eval_base_cmd.extend(["--frozen-labels-csv", frozen_labels_csv])
            status["eval_baseline"] = _run_with_retry(
                eval_base_cmd,
                stage_name="eval_baseline",
                retry_gpu_faults=1,
            )
            if not _require_outputs(status["eval_baseline"], [eval_base_json], stage_name="eval_baseline"):
                folds.append({"holdout": holdout, "status": status, "pass": False})
                continue

        if os.path.exists(gate_base_json):
            status["gate_baseline"] = {"skipped_existing": True, "summary_json": gate_base_json}
        else:
            gate_base_cmd = [
                sys.executable, os.path.join(ROOT, "tools", "run_idp_3bead_benchmark_gate.py"),
                "--config-json", eval_cfg,
                "--eval-json", eval_base_json,
                "--out-json", gate_base_json,
                "--out-md", f"{fold_prefix}_gate_baseline_summary.md",
            ]
            status["gate_baseline"] = _run(gate_base_cmd)
            if not _require_outputs(status["gate_baseline"], [gate_base_json], stage_name="gate_baseline"):
                folds.append({"holdout": holdout, "status": status, "pass": False})
                continue

        if os.path.exists(eval_corr_json):
            status["eval_corrected"] = {"skipped_existing": True, "summary_json": eval_corr_json}
        else:
            eval_corr_cmd = [
                sys.executable, os.path.join(ROOT, "tools", "run_idp_3bead_evaluator.py"),
                "--config-json", eval_cfg,
                "--device", str(args.device),
                "--residual-checkpoint", ckpt,
                "--residual-device", str(args.device),
                "--date-tag", f"{date_tag}-fold{fold_idx}-eval-corrected",
                "--out-prefix", f"{fold_prefix}_eval_corrected",
            ]
            _append_kalman_shadow_args(eval_corr_cmd, args)
            if frozen_labels_csv:
                eval_corr_cmd.extend(["--frozen-labels-csv", frozen_labels_csv])
            status["eval_corrected"] = _run_with_retry(
                eval_corr_cmd,
                stage_name="eval_corrected",
                retry_gpu_faults=1,
            )
            if not _require_outputs(status["eval_corrected"], [eval_corr_json], stage_name="eval_corrected"):
                folds.append({"holdout": holdout, "status": status, "pass": False})
                continue

        if os.path.exists(gate_corr_json):
            status["gate_corrected"] = {"skipped_existing": True, "summary_json": gate_corr_json}
        else:
            gate_corr_cmd = [
                sys.executable, os.path.join(ROOT, "tools", "run_idp_3bead_benchmark_gate.py"),
                "--config-json", eval_cfg,
                "--eval-json", eval_corr_json,
                "--out-json", gate_corr_json,
                "--out-md", f"{fold_prefix}_gate_corrected_summary.md",
            ]
            status["gate_corrected"] = _run(gate_corr_cmd)
            if not _require_outputs(status["gate_corrected"], [gate_corr_json], stage_name="gate_corrected"):
                folds.append({"holdout": holdout, "status": status, "pass": False})
                continue

        eval_base_payload = _read_json(eval_base_json)
        eval_corr_payload = _read_json(eval_corr_json)
        gate_base_payload = _read_json(gate_base_json)
        gate_corr_payload = _read_json(gate_corr_json)
        for row in list(eval_base_payload.get("targets", [])):
            row["holdout_fold"] = holdout
            combined_baseline_rows.append(row)
        for row in list(eval_corr_payload.get("targets", [])):
            row["holdout_fold"] = holdout
            combined_corrected_rows.append(row)
        baseline_template = {k: v for k, v in eval_base_payload.items() if k not in {"targets", "target_count", "pass_count", "pass_fraction", "summary_json", "summary_md", "targets_csv"}}
        corrected_template = {k: v for k, v in eval_corr_payload.items() if k not in {"targets", "target_count", "pass_count", "pass_fraction", "summary_json", "summary_md", "targets_csv"}}
        folds.append(
            {
                "holdout": holdout,
                "train_target_count": len(train_targets),
                "eval_target_count": len(eval_targets),
                "status": status,
                "frozen_labels_csv": frozen_labels_csv,
                "baseline_gate": gate_base_payload,
                "corrected_gate": gate_corr_payload,
                "pass": bool(gate_corr_payload.get("pass", False)),
            }
        )

    combined_baseline_json = f"{out_prefix}_baseline_eval_summary.json"
    combined_corrected_json = f"{out_prefix}_corrected_eval_summary.json"
    combined_branch_prefix = f"{out_prefix}_branch_summary"
    baseline_payload = dict(baseline_template)
    baseline_payload["targets"] = combined_baseline_rows
    baseline_payload["target_count"] = len(combined_baseline_rows)
    baseline_payload["pass_count"] = sum(int(bool(r.get("target_pass", False))) for r in combined_baseline_rows)
    baseline_payload["pass_fraction"] = float(baseline_payload["pass_count"] / max(len(combined_baseline_rows), 1))
    _write_json(combined_baseline_json, baseline_payload)
    corrected_payload = dict(corrected_template)
    corrected_payload["targets"] = combined_corrected_rows
    corrected_payload["target_count"] = len(combined_corrected_rows)
    corrected_payload["pass_count"] = sum(int(bool(r.get("target_pass", False))) for r in combined_corrected_rows)
    corrected_payload["pass_fraction"] = float(corrected_payload["pass_count"] / max(len(combined_corrected_rows), 1))
    corrected_payload["residual"] = {"applied": True, "holdout_mode": True}
    _write_json(combined_corrected_json, corrected_payload)

    combined_gate_json = f"{out_prefix}_combined_gate_summary.json"
    combined_gate_md = f"{out_prefix}_combined_gate_summary.md"
    gate_status = _run([
        sys.executable, os.path.join(ROOT, "tools", "run_idp_3bead_benchmark_gate.py"),
        "--config-json", str(args.config_json),
        "--eval-json", combined_corrected_json,
        "--out-json", combined_gate_json,
        "--out-md", combined_gate_md,
    ])
    branch_status = _run([
        sys.executable, os.path.join(ROOT, "tools", "build_idp_branch_feature_report.py"),
        "--config-json", str(args.config_json),
        "--eval-json", combined_corrected_json,
        "--out-prefix", combined_branch_prefix,
    ])
    combined_gate_payload = _read_json(combined_gate_json) if os.path.exists(combined_gate_json) else {}
    branch_payload = _read_json(f"{combined_branch_prefix}.json") if os.path.exists(f"{combined_branch_prefix}.json") else {}

    final = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "config_json": str(args.config_json),
        "device": str(args.device),
        "holdout_key": str(args.holdout_key),
        "fold_count": len(groups),
        "folds": folds,
        "combined_baseline_eval_json": combined_baseline_json,
        "combined_corrected_eval_json": combined_corrected_json,
        "combined_gate": {"status": gate_status, "payload": combined_gate_payload},
        "branch_summary": {"status": branch_status, "payload": branch_payload},
    }
    final["baseline_pass_folds"] = sum(int(bool(f.get("baseline_gate", {}).get("pass", False))) for f in folds)
    final["corrected_pass_folds"] = sum(int(bool(f.get("corrected_gate", {}).get("pass", False))) for f in folds)
    final["all_fold_pass"] = bool(final["corrected_pass_folds"] == len(groups))
    final["combined_gate_pass"] = bool(combined_gate_payload.get("pass", False))
    # Fold-level corrected pass is the release criterion. The combined gate
    # stays as a global diagnostic and should not veto a clean fold sweep.
    final["pass"] = bool(final["all_fold_pass"])
    out_json = f"{out_prefix}_summary.json"
    out_md = f"{out_prefix}_summary.md"
    _write_json(out_json, final)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    "# IDP 3-Bead Holdout Pipeline",
                    "",
                    f"- pass: {final['pass']}",
                    f"- fold_count: {final['fold_count']}",
                    f"- baseline_pass_folds: {final['baseline_pass_folds']}",
                    f"- corrected_pass_folds: {final['corrected_pass_folds']}",
                    f"- all_fold_pass: {final['all_fold_pass']}",
                    f"- combined_gate_pass: {final['combined_gate_pass']}",
                    f"- combined_gate_json: `{combined_gate_json}`",
                    f"- branch_summary_json: `{combined_branch_prefix}.json`",
                ]
            ) + "\n"
        )

    release_post: Dict[str, Any] = {}
    if bool(int(getattr(args, "emit_release_manifest", 1))):
        release_manifest_json = str(args.release_manifest_json).strip() or f"{out_prefix}_release_manifest.json"
        release_manifest_md = str(args.release_manifest_md).strip() or (
            release_manifest_json[:-5] + ".md" if release_manifest_json.endswith(".json") else release_manifest_json + ".md"
        )
        release_global_agg_json = (
            str(getattr(args, "release_global_agg_calibrator_json", "")).strip()
            or (
                release_manifest_json.replace("release_manifest", "global_aggregation_calibrator")
                if "release_manifest" in os.path.basename(release_manifest_json)
                else f"{out_prefix}_global_aggregation_calibrator.json"
            )
        )
        release_global_agg_md = str(getattr(args, "release_global_agg_calibrator_md", "")).strip() or (
            release_global_agg_json[:-5] + ".md"
            if release_global_agg_json.endswith(".json")
            else release_global_agg_json + ".md"
        )
        release_global_agg_predictions_csv = str(
            getattr(args, "release_global_agg_calibrator_predictions_csv", "")
        ).strip() or (
            release_global_agg_json[:-5] + "_predictions.csv"
            if release_global_agg_json.endswith(".json")
            else release_global_agg_json + "_predictions.csv"
        )
        release_global_agg_dashboard_html = str(
            getattr(args, "release_global_agg_dashboard_html", "")
        ).strip() or f"{out_prefix}_global_aggregation_dashboard.html"
        release_global_agg_dashboard_json = str(
            getattr(args, "release_global_agg_dashboard_json", "")
        ).strip() or f"{out_prefix}_global_aggregation_dashboard.json"
        historical_compare_json = str(getattr(args, "historical_global_agg_compare_json", "")).strip()
        release_label = str(args.release_label).strip() or os.path.basename(out_prefix)
        manifest_cmd = [
            sys.executable,
            os.path.join(ROOT, "tools", "build_idp_release_manifest.py"),
            "--summary-json",
            out_json,
            "--out-json",
            release_manifest_json,
            "--out-md",
            release_manifest_md,
            "--release-label",
            release_label,
        ]
        release_post["manifest"] = _run(manifest_cmd)
        release_post["manifest_json"] = release_manifest_json
        release_post["manifest_md"] = release_manifest_md

        global_agg_cmd = [
            sys.executable,
            os.path.join(ROOT, "tools", "evaluate_idp_global_aggregation_calibrator.py"),
            "--manifest-json",
            release_manifest_json,
            "--out-json",
            release_global_agg_json,
            "--out-md",
            release_global_agg_md,
            "--out-predictions-csv",
            release_global_agg_predictions_csv,
        ]
        release_post["global_aggregation_diagnostic"] = _run(global_agg_cmd)
        release_post["global_aggregation_diagnostic_json"] = release_global_agg_json
        release_post["global_aggregation_diagnostic_md"] = release_global_agg_md
        release_post["global_aggregation_diagnostic_predictions_csv"] = release_global_agg_predictions_csv

        # Rebuild the manifest after diagnostic artifacts exist so the manifest records
        # the diagnostic json/md/predictions paths before any downstream consumers
        # such as the dashboard try to resolve them.
        release_post["manifest_refresh"] = _run(manifest_cmd)

        dashboard_cmd = [
            sys.executable,
            os.path.join(ROOT, "tools", "build_idp_global_aggregation_dashboard.py"),
            "--manifest-json",
            release_manifest_json,
            "--out-html",
            release_global_agg_dashboard_html,
            "--out-json",
            release_global_agg_dashboard_json,
        ]
        if historical_compare_json:
            dashboard_cmd.extend(["--compare-json", historical_compare_json])
        release_post["global_aggregation_dashboard"] = _run(dashboard_cmd)
        release_post["global_aggregation_dashboard_html"] = release_global_agg_dashboard_html
        release_post["global_aggregation_dashboard_json"] = release_global_agg_dashboard_json
        # Refresh once more after the dashboard exists so html/json dashboard paths are
        # also captured as stable diagnostic artifacts.
        release_post["manifest_refresh_dashboard"] = _run(manifest_cmd)

        baseline_manifest_json = str(getattr(args, "baseline_manifest_json", "")).strip()
        if baseline_manifest_json:
            release_regression_json = str(args.release_regression_json).strip() or f"{out_prefix}_release_regression.json"
            release_regression_md = str(args.release_regression_md).strip() or (
                release_regression_json[:-5] + ".md"
                if release_regression_json.endswith(".json")
                else release_regression_json + ".md"
            )
            regression_cmd = [
                sys.executable,
                os.path.join(ROOT, "tools", "check_idp_holdout_regression.py"),
                "--baseline-manifest-json",
                baseline_manifest_json,
                "--candidate-summary-json",
                out_json,
                "--out-json",
                release_regression_json,
                "--out-md",
                release_regression_md,
                "--require-candidate-pass",
                "1",
                "--require-all-fold-pass",
                "1",
                "--max-corrected-fold-drop",
                "0",
            ]
            release_post["regression"] = _run(regression_cmd)
            release_post["regression_json"] = release_regression_json
            release_post["regression_md"] = release_regression_md
            release_post["baseline_manifest_json"] = baseline_manifest_json

            release_candidate_eval_json = str(args.release_candidate_eval_json).strip() or (
                f"{out_prefix}_release_candidate_eval.json"
            )
            release_candidate_eval_md = str(args.release_candidate_eval_md).strip() or (
                release_candidate_eval_json[:-5] + ".md"
                if release_candidate_eval_json.endswith(".json")
                else release_candidate_eval_json + ".md"
            )
            candidate_eval_cmd = [
                sys.executable,
                os.path.join(ROOT, "tools", "evaluate_idp_release_candidate.py"),
                "--baseline-manifest-json",
                baseline_manifest_json,
                "--candidate-summary-json",
                out_json,
                "--candidate-manifest-json",
                release_manifest_json,
                "--candidate-global-agg-calibrator-json",
                release_global_agg_json,
                "--out-json",
                release_candidate_eval_json,
                "--out-md",
                release_candidate_eval_md,
                "--regression-json",
                release_regression_json,
                "--regression-md",
                release_regression_md,
                "--require-candidate-pass",
                "1",
                "--require-all-fold-pass",
                "1",
                "--max-corrected-fold-drop",
                "0",
            ]
            release_post["candidate_eval"] = _run(candidate_eval_cmd)
            release_post["candidate_eval_json"] = release_candidate_eval_json
            release_post["candidate_eval_md"] = release_candidate_eval_md

            if bool(int(getattr(args, "auto_promote_if_candidate_approved", 0))):
                promote_out_json = str(args.release_promotion_json).strip() or (
                    f"{out_prefix}_release_promotion.json"
                )
                promote_cmd = [
                    sys.executable,
                    os.path.join(ROOT, "tools", "promote_idp_release_candidate.py"),
                    "--candidate-eval-json",
                    release_candidate_eval_json,
                    "--out-json",
                    promote_out_json,
                    "--candidate-manifest-json",
                    release_manifest_json,
                    "--candidate-manifest-md",
                    release_manifest_md,
                    "--candidate-regression-json",
                    release_regression_json,
                    "--candidate-regression-md",
                    release_regression_md,
                ]
                release_post["promotion"] = _run(promote_cmd)
                release_post["promotion_json"] = promote_out_json

    final["release_post"] = release_post
    _write_json(out_json, final)
    return final


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run strict hold-out residual validation for IDP 3-bead pipeline.")
    p.add_argument("--config-json", type=str, required=True)
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--holdout-key", type=str, default="split_group")
    p.add_argument("--anchor-loss-weight", type=float, default=0.5)
    p.add_argument("--observable-loss-weight", type=float, default=0.5)
    p.add_argument("--date-tag", type=str, default="")
    p.add_argument("--out-prefix", type=str, default="")
    p.add_argument("--resume-existing", type=int, default=1)
    p.add_argument("--emit-release-manifest", type=int, default=1)
    p.add_argument("--release-label", type=str, default="")
    p.add_argument("--release-manifest-json", type=str, default="")
    p.add_argument("--release-manifest-md", type=str, default="")
    p.add_argument("--release-global-agg-calibrator-json", type=str, default="")
    p.add_argument("--release-global-agg-calibrator-md", type=str, default="")
    p.add_argument("--release-global-agg-calibrator-predictions-csv", type=str, default="")
    p.add_argument("--baseline-manifest-json", type=str, default="")
    p.add_argument("--frozen-labels-manifest-json", type=str, default="")
    p.add_argument("--release-regression-json", type=str, default="")
    p.add_argument("--release-regression-md", type=str, default="")
    p.add_argument("--release-candidate-eval-json", type=str, default="")
    p.add_argument("--release-candidate-eval-md", type=str, default="")
    p.add_argument("--auto-promote-if-candidate-approved", type=int, default=0)
    p.add_argument("--release-promotion-json", type=str, default="")
    p.add_argument("--kalman-shadow-enable", type=int, default=0)
    p.add_argument("--kalman-shadow-mode", type=str, default="identity")
    p.add_argument("--kalman-shadow-family-token", type=str, default="idp")
    p.add_argument("--kalman-shadow-obs-noise-scale", type=float, default=0.0)
    p.add_argument("--kalman-shadow-process-noise-scale", type=float, default=0.0)
    p.add_argument("--kalman-shadow-delta-cap-frac", type=float, default=0.25)
    p.add_argument("--kalman-shadow-feature-mask", type=str, default="all")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_pipeline(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not bool(payload.get("pass", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
