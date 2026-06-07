#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BASELINE_RUN_ROOT = "runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v7r1"
DEFAULT_SOURCE_SPEC_JSON = "config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json"
DEFAULT_GENERATED_ROOT = "runs/cross_family_locked_decoy_shadow_current"
DEFAULT_OUT_JSON = "runs/cross_family_locked_decoy_shadow_current.json"
DEFAULT_OUT_CSV = "runs/cross_family_locked_decoy_shadow_current.csv"
DEFAULT_OUT_MD = "runs/cross_family_locked_decoy_shadow_summary_current.md"
DEFAULT_RESIDUAL_SPEC_JSON = "runs/gpcr_residual_prototype_spec_narrow_v2_current.json"

TASK_IDS = (
    "ion_trpv1_chembl20_full",
    "ion_trpv1_chembl50_full",
    "kinase_core_full",
    "kinase_strict_full",
)

TASK_TO_FAMILY = {
    "ion_trpv1_chembl20_full": "ion_channel",
    "ion_trpv1_chembl50_full": "ion_channel",
    "kinase_core_full": "kinase",
    "kinase_strict_full": "kinase",
}


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


def _selected_rows(source_spec: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for set_row in source_spec.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        for task in set_row.get("tasks", []):
            if str(task.get("kind", "")).strip() != "ligand_stress":
                continue
            task_id = str(task.get("task_id", "")).strip()
            if task_id not in TASK_IDS:
                continue
            out.append(
                {
                    "set_id": set_id,
                    "set_meta": {k: v for k, v in dict(set_row).items() if k != "tasks"},
                    "task_id": task_id,
                    "domain": str(task.get("domain", "")).strip(),
                    "ligand_sizes": str(task.get("ligand_sizes", "")).strip(),
                    "profile_json": str(task.get("profile_json", "")).strip(),
                    "task": dict(task),
                }
            )
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
    family: str,
    residual_spec_json: str,
) -> dict[str, Any]:
    out = dict(base_profile)
    out["build_hard_decoy_benchmark"] = False
    out["ligand_csv"] = labels_csv
    out["calibration_reference_csv"] = labels_csv
    out["ranking_labels_csv"] = labels_csv
    out["eval_split_csv"] = split_csv
    out["residual_prototype_enabled"] = True
    out["residual_prototype_mode"] = "shadow_only"
    out["residual_prototype_family"] = family
    out["residual_prototype_apply_stage"] = "stage5_ranking"
    out["residual_prototype_status"] = "shadow_runtime_ready"
    out["residual_prototype_runtime_hook_ready"] = True
    out["residual_prototype_spec_json"] = residual_spec_json
    out["locked_decoy_ab_enabled"] = True
    out["locked_decoy_labels_csv"] = labels_csv
    out["locked_decoy_split_csv"] = split_csv
    out["locked_decoy_notes"] = (
        "Locked-decoy cross-family shadow scaffold. Reuses accepted baseline hard-decoy labels/split so the "
        "candidate measures family-token routing and shadow telemetry without changing the evaluation packet."
    )
    return out


def build_payload(
    *,
    baseline_run_root: Path,
    source_spec_json: Path,
    generated_root: Path,
    residual_spec_json: Path,
) -> dict[str, Any]:
    baseline_task_map = _baseline_task_map(baseline_run_root)
    source_spec = _read_json(source_spec_json)
    rows = _selected_rows(source_spec)
    profiles_dir = generated_root / "profiles"
    specs_dir = generated_root / "specs"
    profile_rows: list[dict[str, Any]] = []
    spec_tasks: list[dict[str, Any]] = []

    for row in rows:
        task_id = str(row["task_id"])
        source_profile_path = _resolve(str(row["profile_json"]))
        base_profile = _read_json(source_profile_path)
        baseline_task = baseline_task_map[task_id]
        locked = _locked_paths(baseline_task)
        family = TASK_TO_FAMILY[task_id]
        out_profile_path = profiles_dir / f"{source_profile_path.stem}_crossfamshadow1.json"
        _write_json(
            out_profile_path,
            _profile_payload(
                base_profile,
                labels_csv=str(Path(locked["labels_csv"]).resolve()),
                split_csv=str(Path(locked["split_csv"]).resolve()),
                family=family,
                residual_spec_json=str(residual_spec_json.resolve()),
            ),
        )
        task = dict(row["task"])
        task["profile_json"] = str(out_profile_path.resolve())
        suffix = str(task.get("date_tag_suffix", task_id)).strip()
        task["date_tag_suffix"] = f"{suffix}-crossfamshadow1"
        spec_tasks.append({"set_id": row["set_id"], "set_meta": dict(row["set_meta"]), "task": task})
        profile_rows.append(
            {
                "set_id": row["set_id"],
                "task_id": task_id,
                "family": family,
                "domain": row["domain"],
                "ligand_sizes": row["ligand_sizes"],
                "source_profile_json": row["profile_json"],
                "generated_profile_json": str(out_profile_path.resolve()),
                "locked_decoy_labels_csv": locked["labels_csv"],
                "locked_decoy_split_csv": locked["split_csv"],
                "runtime_hook_ready": "yes",
            }
        )

    set_order: list[str] = []
    set_map: dict[str, dict[str, Any]] = {}
    for row in spec_tasks:
        set_id = str(row["set_id"])
        if set_id not in set_map:
            set_meta = dict(row.get("set_meta", {}))
            set_map[set_id] = {k: v for k, v in set_meta.items() if k != "tasks"}
            set_map[set_id]["tasks"] = []
            set_order.append(set_id)
        set_map[set_id]["tasks"].append(dict(row["task"]))

    candidate_spec = {
        "protocol_id": "cross_family_locked_decoy_shadow_v1",
        "protocol_title": "Cross-Family Locked-Decoy Shadow Current",
        "protocol_version": "v1",
        "global_governance": {
            "comparison_kind": "cross_family_locked_decoy_shadow",
            "baseline_run_root": str(baseline_run_root.resolve()),
            "source_spec_json": str(source_spec_json.resolve()),
            "prototype_spec_json": str(residual_spec_json.resolve()),
            "prototype_mode": "shadow_only",
            "family_scope": ["ion_channel", "kinase"],
        },
        "sets": [set_map[set_id] for set_id in set_order],
    }
    candidate_spec_path = specs_dir / "cross_family_locked_decoy_shadow_current_v1.json"
    _write_json(candidate_spec_path, candidate_spec)
    payload = {
        "comparison_kind": "cross_family_locked_decoy_shadow",
        "prototype_mode": "shadow_only",
        "runtime_hook_ready": True,
        "claim_ready": False,
        "locked_decoy_ready": True,
        "baseline_run_root": str(baseline_run_root.resolve()),
        "source_spec_json": str(source_spec_json.resolve()),
        "prototype_spec_json": str(residual_spec_json.resolve()),
        "candidate_spec_json": str(candidate_spec_path.resolve()),
        "family_scope": ["ion_channel", "kinase"],
        "profile_rows": profile_rows,
        "recommended_next_action": (
            "Run the locked-decoy ion/kinase equal-size shadow candidate, verify pass stability, and only then "
            "promote the global cross-family shadow shell from plan to runnable status."
        ),
    }
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Cross-Family Locked-Decoy Shadow Scaffold",
        "",
        f"- comparison_kind: `{payload['comparison_kind']}`",
        f"- prototype_mode: `{payload['prototype_mode']}`",
        f"- runtime_hook_ready: `{payload['runtime_hook_ready']}`",
        f"- claim_ready: `{payload['claim_ready']}`",
        f"- locked_decoy_ready: `{payload['locked_decoy_ready']}`",
        f"- family_scope: `{payload['family_scope']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['recommended_next_action']}",
        "",
        "## Generated Profiles",
        "",
        "| set_id | task_id | family | generated_profile_json | locked_decoy_labels_csv | locked_decoy_split_csv |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["profile_rows"]:
        lines.append(
            f"| {row['set_id']} | {row['task_id']} | {row['family']} | `{row['generated_profile_json']}` | "
            f"`{row['locked_decoy_labels_csv']}` | `{row['locked_decoy_split_csv']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build a locked-decoy equal-size cross-family shadow scaffold for ion/kinase.")
    p.add_argument("--baseline-run-root", default=DEFAULT_BASELINE_RUN_ROOT)
    p.add_argument("--source-spec-json", default=DEFAULT_SOURCE_SPEC_JSON)
    p.add_argument("--generated-root", default=DEFAULT_GENERATED_ROOT)
    p.add_argument("--residual-spec-json", default=DEFAULT_RESIDUAL_SPEC_JSON)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        baseline_run_root=_resolve(args.baseline_run_root),
        source_spec_json=_resolve(args.source_spec_json),
        generated_root=_resolve(args.generated_root),
        residual_spec_json=_resolve(args.residual_spec_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    _write_json(out_json, payload)
    _write_csv(out_csv, payload["profile_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
