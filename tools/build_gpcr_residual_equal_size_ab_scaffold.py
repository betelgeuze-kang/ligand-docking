#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCE_SPEC_JSON = "config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json"
DEFAULT_PROTOTYPE_SPEC_JSON = "runs/gpcr_residual_prototype_spec_current.json"
DEFAULT_GENERATED_ROOT = "runs/gpcr_residual_ab_current"
DEFAULT_OUT_JSON = "runs/gpcr_residual_ab_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_residual_ab_summary_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_residual_ab_summary_current.md"

GPCR_TASK_IDS = ["gpcr_core_full", "gpcr_chembl50_full"]


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


def _selected_rows(source_spec: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for set_row in source_spec.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        for task in set_row.get("tasks", []):
            if str(task.get("kind", "")).strip() != "ligand_stress":
                continue
            task_id = str(task.get("task_id", "")).strip()
            if task_id not in GPCR_TASK_IDS:
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


def _profile_payload(base_profile: dict[str, Any], prototype_spec_json: Path) -> dict[str, Any]:
    out = dict(base_profile)
    out["residual_prototype_enabled"] = True
    out["residual_prototype_mode"] = "shadow_only"
    out["residual_prototype_family"] = "gpcr"
    out["residual_prototype_apply_stage"] = "stage5_ranking"
    out["residual_prototype_status"] = "shadow_runtime_ready"
    out["residual_prototype_spec_json"] = str(prototype_spec_json.resolve())
    out["residual_prototype_runtime_hook_ready"] = True
    out["residual_prototype_notes"] = (
        "Shadow-only GPCR residual prototype scaffold. The runtime hook is available and emits shadow "
        "telemetry, but ranking behavior remains unchanged until apply-mode experiments are explicitly enabled."
    )
    return out


def build_payload(
    *,
    source_spec_json: Path,
    prototype_spec_json: Path,
    generated_root: Path,
) -> dict[str, Any]:
    source_spec = _read_json(source_spec_json)
    prototype_spec = _read_json(prototype_spec_json)
    rows = _selected_rows(source_spec)
    profiles_dir = generated_root / "profiles"
    specs_dir = generated_root / "specs"
    profile_rows: list[dict[str, Any]] = []
    spec_tasks: list[dict[str, Any]] = []

    for row in rows:
        source_profile_path = _resolve(str(row["profile_json"]))
        base_profile = _read_json(source_profile_path)
        out_profile_path = profiles_dir / f"{source_profile_path.stem}_residualab1.json"
        _write_json(out_profile_path, _profile_payload(base_profile, prototype_spec_json))
        task = dict(row["task"])
        task["profile_json"] = str(out_profile_path.resolve())
        suffix = str(task.get("date_tag_suffix", row["task_id"])).strip()
        task["date_tag_suffix"] = f"{suffix}-residualab1"
        spec_tasks.append({"set_id": row["set_id"], "set_meta": dict(row["set_meta"]), "task": task})
        profile_rows.append(
            {
                "set_id": row["set_id"],
                "task_id": row["task_id"],
                "domain": row["domain"],
                "ligand_sizes": row["ligand_sizes"],
                "source_profile_json": row["profile_json"],
                "generated_profile_json": str(out_profile_path.resolve()),
                "residual_prototype_mode": "shadow_only",
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
        "protocol_id": "gpcr_residual_ab_v1",
        "protocol_title": "GPCR Residual Equal-Size A/B Current",
        "protocol_version": "v1",
        "global_governance": {
            "comparison_kind": "equal_size_residual_ab",
            "source_spec_json": str(source_spec_json.resolve()),
            "prototype_spec_json": str(prototype_spec_json.resolve()),
            "prototype_mode": prototype_spec.get("summary", {}).get("prototype_mode", "shadow_only"),
        },
        "sets": [set_map[set_id] for set_id in set_order],
    }
    candidate_spec_path = specs_dir / "gpcr_residual_ab_current_v1.json"
    _write_json(candidate_spec_path, candidate_spec)

    task_rows = [
        {
            "set_id": row["set_id"],
            "task_id": row["task_id"],
            "domain": row["domain"],
            "ligand_sizes": row["ligand_sizes"],
            "profile_json": row["profile_json"],
        }
        for row in rows
    ]
    summary_rows = [
        {
            "artifact": "prototype_spec_json",
            "path": str(prototype_spec_json.resolve()),
            "ready": "yes",
            "notes": "current GPCR residual prototype contract",
        },
        {
            "artifact": "candidate_spec_json",
            "path": str(candidate_spec_path.resolve()),
            "ready": "yes",
            "notes": "equal-size GPCR A/B candidate scaffold",
        },
        {
            "artifact": "runtime_hook_ready",
            "path": "",
            "ready": "yes",
            "notes": "candidate profiles emit shadow residual telemetry without changing ranking behavior",
        },
        {
            "artifact": "claim_ready",
            "path": "",
            "ready": "no",
            "notes": "A/B scaffold is not claim-bearing until baseline/candidate/comparison artifacts exist",
        },
    ]
    scope_summary = {
        "selected_task_count": len(task_rows),
        "selected_set_ids": sorted({row["set_id"] for row in task_rows}),
        "domains_touched": sorted({row["domain"] for row in task_rows if row["domain"]}),
        "ligand_size_surface": sorted({row["ligand_sizes"] for row in task_rows}),
    }
    payload = {
        "comparison_kind": "equal_size_residual_ab",
        "prototype_mode": "shadow_only",
        "runtime_hook_ready": True,
        "claim_ready": False,
        "source_spec_json": str(source_spec_json.resolve()),
        "prototype_spec_json": str(prototype_spec_json.resolve()),
        "candidate_spec_json": str(candidate_spec_path.resolve()),
        "scope_summary": scope_summary,
        "task_rows": task_rows,
        "profile_rows": profile_rows,
        "summary_rows": summary_rows,
        "recommended_next_action": (
            "Run equal-size GPCR baseline/candidate A/B, inspect shadow residual telemetry, and build "
            "comparison artifacts before any 100k router experiment."
        ),
        "baseline_command": (
            f"python3 tools/run_external_validation_blind_sets.py --set-spec-json {source_spec_json} "
            "--set-id-filter set1_core_blind,set2_expanded_ood --task-id-filter gpcr_core_full,gpcr_chembl50_full"
        ),
        "candidate_command": (
            f"python3 tools/run_external_validation_blind_sets.py --set-spec-json {candidate_spec_path.resolve()} "
            "--set-id-filter set1_core_blind,set2_expanded_ood --task-id-filter gpcr_core_full,gpcr_chembl50_full"
        ),
    }
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# GPCR Residual Equal-Size A/B Scaffold",
        "",
        f"- comparison_kind: `{payload['comparison_kind']}`",
        f"- prototype_mode: `{payload['prototype_mode']}`",
        f"- runtime_hook_ready: `{payload['runtime_hook_ready']}`",
        f"- claim_ready: `{payload['claim_ready']}`",
        "",
        "## Scope",
        "",
        f"- selected_task_count: `{payload['scope_summary']['selected_task_count']}`",
        f"- selected_set_ids: `{payload['scope_summary']['selected_set_ids']}`",
        f"- domains_touched: `{payload['scope_summary']['domains_touched']}`",
        f"- ligand_size_surface: `{payload['scope_summary']['ligand_size_surface']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['recommended_next_action']}",
        "",
        "## Task Surface",
        "",
        "| set_id | task_id | domain | ligand_sizes |",
        "| --- | --- | --- | ---: |",
    ]
    for row in payload["task_rows"]:
        lines.append(
            f"| {row['set_id']} | {row['task_id']} | {row['domain']} | {row['ligand_sizes']} |"
        )
    lines.extend(
        [
            "",
            "## Generated Profiles",
            "",
            "| task_id | generated_profile_json | runtime_hook_ready |",
            "| --- | --- | --- |",
        ]
    )
    for row in payload["profile_rows"]:
        lines.append(
            f"| {row['task_id']} | `{row['generated_profile_json']}` | {row['runtime_hook_ready']} |"
        )
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "```bash",
            payload["baseline_command"],
            "```",
            "",
            "```bash",
            payload["candidate_command"],
            "```",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the current GPCR residual equal-size A/B scaffold and generated shadow-only profiles."
    )
    parser.add_argument("--source-spec-json", default=DEFAULT_SOURCE_SPEC_JSON)
    parser.add_argument("--prototype-spec-json", default=DEFAULT_PROTOTYPE_SPEC_JSON)
    parser.add_argument("--generated-root", default=DEFAULT_GENERATED_ROOT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        source_spec_json=_resolve(args.source_spec_json),
        prototype_spec_json=_resolve(args.prototype_spec_json),
        generated_root=_resolve(args.generated_root),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    _write_json(out_json, payload)
    _write_csv(out_csv, payload["profile_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
