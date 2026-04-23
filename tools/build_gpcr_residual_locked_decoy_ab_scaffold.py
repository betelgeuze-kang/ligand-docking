#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BASELINE_RUN_ROOT = "runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v7r1"
DEFAULT_SOURCE_SPEC_JSON = "runs/gpcr_residual_ab_current/specs/gpcr_residual_ab_current_v1.json"
DEFAULT_GENERATED_ROOT = "runs/gpcr_residual_locked_decoy_ab_current"
DEFAULT_OUT_JSON = "runs/gpcr_residual_locked_decoy_ab_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_residual_locked_decoy_ab_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_residual_locked_decoy_ab_summary_current.md"

TASK_IDS = ("gpcr_core_full", "gpcr_chembl50_full")


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _baseline_task_map(run_root: Path) -> dict[str, dict[str, Any]]:
    state = _read_json(run_root / "state.json")
    out: dict[str, dict[str, Any]] = {}
    for set_row in state.get("sets", []):
        for task in set_row.get("tasks", []):
            task_id = str(task.get("task_id", "")).strip()
            if task_id in TASK_IDS:
                out[task_id] = dict(task)
    return out


def _locked_paths(task: dict[str, Any]) -> dict[str, str]:
    summary_json = str(task.get("summary_json", "") or "")
    if not summary_json:
        raise ValueError(f"missing summary_json for task {task.get('task_id')}")
    base = summary_json.removesuffix("_summary.json")
    labels_csv = f"{base}_hard_decoy_labels.csv"
    split_csv = f"{base}_hard_decoy_split.csv"
    for p in [labels_csv, split_csv]:
        if not Path(p).exists():
            raise FileNotFoundError(p)
    return {"labels_csv": labels_csv, "split_csv": split_csv}


def _profile_payload(
    base_profile: dict[str, Any],
    *,
    labels_csv: str,
    split_csv: str,
    residual_mode: str,
    residual_spec_json: str | None,
) -> dict[str, Any]:
    out = dict(base_profile)
    out["build_hard_decoy_benchmark"] = False
    out["ligand_csv"] = labels_csv
    out["calibration_reference_csv"] = labels_csv
    out["ranking_labels_csv"] = labels_csv
    out["eval_split_csv"] = split_csv
    out["residual_prototype_mode"] = residual_mode
    out["residual_prototype_status"] = "apply_runtime_ready" if residual_mode == "apply" else "shadow_runtime_ready"
    out["locked_decoy_ab_enabled"] = True
    out["locked_decoy_labels_csv"] = labels_csv
    out["locked_decoy_split_csv"] = split_csv
    if residual_spec_json:
        out["residual_prototype_spec_json"] = residual_spec_json
    if residual_mode == "apply":
        out["ranking_score_col"] = "binding_score_composite_v7_residual_active"
        out["ranking_probability_score_col"] = "binding_score_composite_v7_residual_active"
        out["locked_decoy_notes"] = (
            "Locked-decoy equal-size A/B scaffold in apply-mode. Reuses baseline hard-decoy labels/split so the "
            "candidate changes only residual-driven ranking behavior."
        )
    else:
        out["locked_decoy_notes"] = (
            "Locked-decoy equal-size A/B scaffold. Reuses baseline hard-decoy labels/split so the shadow residual "
            "candidate sees the same GPCR evaluation packet as the accepted baseline."
        )
    return out


def build_payload(
    *,
    baseline_run_root: Path,
    source_spec_json: Path,
    generated_root: Path,
    residual_mode: str,
    profile_suffix: str,
    residual_spec_json: str | None,
) -> dict[str, Any]:
    baseline_task_map = _baseline_task_map(baseline_run_root)
    source_spec = _read_json(source_spec_json)
    profiles_dir = generated_root / "profiles"
    specs_dir = generated_root / "specs"
    rows: list[dict[str, Any]] = []
    sets: list[dict[str, Any]] = []
    for set_row in source_spec.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        tasks_out: list[dict[str, Any]] = []
        for task in set_row.get("tasks", []):
            task_id = str(task.get("task_id", "")).strip()
            if task_id not in TASK_IDS:
                continue
            base_profile_path = _resolve(str(task.get("profile_json", "")))
            baseline_task = baseline_task_map[task_id]
            locked = _locked_paths(baseline_task)
            out_profile_path = profiles_dir / f"{base_profile_path.stem}_{profile_suffix}.json"
            _write_json(
                out_profile_path,
                _profile_payload(
                    _read_json(base_profile_path),
                    labels_csv=str(Path(locked["labels_csv"]).resolve()),
                    split_csv=str(Path(locked["split_csv"]).resolve()),
                    residual_mode=residual_mode,
                    residual_spec_json=str(Path(residual_spec_json).resolve()) if residual_spec_json else None,
                ),
            )
            new_task = dict(task)
            new_task["profile_json"] = str(out_profile_path.resolve())
            suffix = str(new_task.get("date_tag_suffix", task_id)).strip()
            new_task["date_tag_suffix"] = f"{suffix}-{profile_suffix}"
            tasks_out.append(new_task)
            rows.append(
                {
                    "set_id": set_id,
                    "task_id": task_id,
                    "generated_profile_json": str(out_profile_path.resolve()),
                    "locked_decoy_labels_csv": locked["labels_csv"],
                    "locked_decoy_split_csv": locked["split_csv"],
                    "residual_mode": residual_mode,
                    "residual_spec_json": str(Path(residual_spec_json).resolve()) if residual_spec_json else "",
                }
            )
        if tasks_out:
            new_set = {k: v for k, v in dict(set_row).items() if k != "tasks"}
            new_set["tasks"] = tasks_out
            sets.append(new_set)
    candidate_spec = {
        "protocol_id": f"gpcr_residual_locked_decoy_ab_{residual_mode}_v1",
        "protocol_title": f"GPCR Residual Locked-Decoy A/B Current ({residual_mode})",
        "protocol_version": "v1",
        "global_governance": {
            "comparison_kind": "equal_size_residual_ab_locked_decoy",
            "baseline_run_root": str(baseline_run_root.resolve()),
            "source_spec_json": str(source_spec_json.resolve()),
            "residual_mode": residual_mode,
        },
        "sets": sets,
    }
    candidate_spec_path = specs_dir / f"gpcr_residual_locked_decoy_ab_{residual_mode}_current_v1.json"
    _write_json(candidate_spec_path, candidate_spec)
    next_action = (
        "Use this locked-decoy scaffold for the next GPCR shadow A/B so baseline and candidate share the exact "
        "same hard-decoy labels/split before interpreting any residual telemetry drift."
    )
    if residual_mode == "apply":
        next_action = (
            "Run this locked-decoy apply-mode scaffold and compare against the baseline and shadow runs before "
            "considering any 100k promotion."
        )
    return {
        "comparison_kind": "equal_size_residual_ab_locked_decoy",
        "baseline_run_root": str(baseline_run_root.resolve()),
        "source_spec_json": str(source_spec_json.resolve()),
        "candidate_spec_json": str(candidate_spec_path.resolve()),
        "runtime_hook_ready": True,
        "locked_decoy_ready": True,
        "residual_mode": residual_mode,
        "residual_spec_json": str(Path(residual_spec_json).resolve()) if residual_spec_json else "",
        "rows": rows,
        "recommended_next_action": next_action,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# GPCR Residual Locked-Decoy A/B Scaffold",
        "",
        f"- comparison_kind: `{payload['comparison_kind']}`",
        f"- residual_mode: `{payload['residual_mode']}`",
        f"- residual_spec_json: `{payload.get('residual_spec_json', '')}`",
        f"- runtime_hook_ready: `{payload['runtime_hook_ready']}`",
        f"- locked_decoy_ready: `{payload['locked_decoy_ready']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['recommended_next_action']}",
        "",
        "| task_id | generated_profile_json | locked_decoy_labels_csv | locked_decoy_split_csv |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['task_id']} | `{row['generated_profile_json']}` | `{row['locked_decoy_labels_csv']}` | `{row['locked_decoy_split_csv']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build a GPCR residual equal-size A/B scaffold that reuses baseline hard-decoy labels/split.")
    p.add_argument("--baseline-run-root", default=DEFAULT_BASELINE_RUN_ROOT)
    p.add_argument("--source-spec-json", default=DEFAULT_SOURCE_SPEC_JSON)
    p.add_argument("--generated-root", default=DEFAULT_GENERATED_ROOT)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    p.add_argument("--residual-mode", default="shadow_only", choices=["shadow_only", "apply"])
    p.add_argument("--profile-suffix", default="lockeddecoy1")
    p.add_argument("--residual-spec-json", default="")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        baseline_run_root=_resolve(args.baseline_run_root),
        source_spec_json=_resolve(args.source_spec_json),
        generated_root=_resolve(args.generated_root),
        residual_mode=str(args.residual_mode),
        profile_suffix=str(args.profile_suffix),
        residual_spec_json=str(args.residual_spec_json or "").strip() or None,
    )
    _write_json(_resolve(args.out_json), payload)
    _write_csv(_resolve(args.out_csv), payload["rows"])
    _write_markdown(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
