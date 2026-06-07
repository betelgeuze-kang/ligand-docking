#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SOURCE_SPEC_JSON = "config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json"
DEFAULT_SHADOW_ORIGIN_ARTIFACT = "runs/gpcr_residual_ab_current.json"
DEFAULT_GENERATED_ROOT = "runs/ion_kinase_residual_shadow_current"
DEFAULT_OUT_JSON = "runs/ion_kinase_residual_equal_size_shadow_current.json"
DEFAULT_OUT_CSV = "runs/ion_kinase_residual_equal_size_shadow_summary_current.csv"
DEFAULT_OUT_MD = "runs/ion_kinase_residual_equal_size_shadow_current.md"

TASK_IDS = {
    "ion_trpv1_chembl20_full": "ion_channel",
    "ion_trpv1_chembl50_full": "ion_channel",
    "kinase_core_full": "kinase",
    "kinase_strict_full": "kinase",
}

GUARDRAILS = [
    "shadow_only_no_active_score_change",
    "family_token_must_match_task_domain",
    "keep_current_gates_unchanged",
    "no_pass_to_fail_before_any_family_apply_mode",
    "locked_decoy_followup_required_before_family_promotion",
]


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
            if task_id not in TASK_IDS:
                continue
            out.append(
                {
                    "set_id": set_id,
                    "set_meta": {k: v for k, v in dict(set_row).items() if k != "tasks"},
                    "task_id": task_id,
                    "domain": TASK_IDS[task_id],
                    "ligand_sizes": str(task.get("ligand_sizes", "")).strip(),
                    "profile_json": str(task.get("profile_json", "")).strip(),
                    "task": dict(task),
                }
            )
    return out


def _profile_payload(base_profile: dict[str, Any], *, family: str, shadow_origin_artifact: Path) -> dict[str, Any]:
    out = dict(base_profile)
    out["residual_prototype_enabled"] = True
    out["residual_prototype_mode"] = "shadow_only"
    out["residual_prototype_family"] = family
    out["residual_prototype_apply_stage"] = "stage5_ranking"
    out["residual_prototype_status"] = "shadow_runtime_ready"
    out["residual_prototype_runtime_hook_ready"] = True
    out["residual_prototype_spec_json"] = ""
    out["residual_prototype_guardrail_profile"] = "equal_size_cross_family_shadow"
    out["residual_prototype_shadow_origin_artifact"] = str(shadow_origin_artifact.resolve())
    out["residual_prototype_notes"] = (
        f"Shadow-only {family} residual scaffold cloned from the current GPCR equal-size pattern. "
        "Runtime emits family-tagged shadow telemetry while keeping the active ranking score unchanged."
    )
    return out


def build_payload(*, source_spec_json: Path, shadow_origin_artifact: Path, generated_root: Path) -> dict[str, Any]:
    source_spec = _read_json(source_spec_json)
    rows = _selected_rows(source_spec)
    profiles_dir = generated_root / "profiles"
    specs_dir = generated_root / "specs"
    profile_rows: list[dict[str, Any]] = []
    spec_tasks: list[dict[str, Any]] = []

    for row in rows:
        source_profile_path = _resolve(str(row["profile_json"]))
        base_profile = _read_json(source_profile_path)
        suffix = f"shadow{row['domain']}1"
        out_profile_path = profiles_dir / f"{source_profile_path.stem}_{suffix}.json"
        _write_json(
            out_profile_path,
            _profile_payload(base_profile, family=row["domain"], shadow_origin_artifact=shadow_origin_artifact),
        )
        task = dict(row["task"])
        task["profile_json"] = str(out_profile_path.resolve())
        date_suffix = str(task.get("date_tag_suffix", row["task_id"])).strip()
        task["date_tag_suffix"] = f"{date_suffix}-{suffix}"
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
                "active_score_change_allowed": "no",
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
        "protocol_id": "ion_kinase_residual_equal_size_shadow_v1",
        "protocol_title": "Ion/Kinase Cross-Family Equal-Size Shadow Current",
        "protocol_version": "v1",
        "global_governance": {
            "comparison_kind": "equal_size_cross_family_shadow",
            "source_spec_json": str(source_spec_json.resolve()),
            "shadow_origin_artifact": str(shadow_origin_artifact.resolve()),
            "guardrails": list(GUARDRAILS),
        },
        "sets": [set_map[set_id] for set_id in set_order],
    }
    candidate_spec_path = specs_dir / "ion_kinase_residual_equal_size_shadow_current_v1.json"
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
    payload = {
        "comparison_kind": "equal_size_cross_family_shadow",
        "prototype_mode": "shadow_only",
        "runtime_hook_ready": True,
        "claim_ready": False,
        "source_spec_json": str(source_spec_json.resolve()),
        "shadow_origin_artifact": str(shadow_origin_artifact.resolve()),
        "candidate_spec_json": str(candidate_spec_path.resolve()),
        "scope_summary": {
            "selected_task_count": len(task_rows),
            "selected_set_ids": sorted({row["set_id"] for row in task_rows}),
            "domains_touched": sorted({row["domain"] for row in task_rows if row["domain"]}),
            "ligand_size_surface": sorted({row["ligand_sizes"] for row in task_rows}),
        },
        "task_rows": task_rows,
        "profile_rows": profile_rows,
        "guardrails": list(GUARDRAILS),
        "recommended_next_action": (
            "Run equal-size ion/kinase baseline and candidate shadow A/B, confirm no active-score change, "
            "then decide whether a locked-decoy follow-up is warranted for family-specific apply-mode work."
        ),
        "baseline_command": (
            f"python3 tools/run_external_validation_blind_sets.py --set-spec-json {source_spec_json.resolve()} "
            "--set-id-filter set1_core_blind,set2_expanded_ood "
            "--task-id-filter ion_trpv1_chembl20_full,ion_trpv1_chembl50_full,kinase_core_full,kinase_strict_full"
        ),
        "candidate_command": (
            f"python3 tools/run_external_validation_blind_sets.py --set-spec-json {candidate_spec_path.resolve()} "
            "--set-id-filter set1_core_blind,set2_expanded_ood "
            "--task-id-filter ion_trpv1_chembl20_full,ion_trpv1_chembl50_full,kinase_core_full,kinase_strict_full"
        ),
    }
    return payload


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Ion/Kinase Equal-Size Shadow Scaffold",
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
        "## Guardrails",
        "",
    ]
    for item in payload["guardrails"]:
        lines.append(f"- `{item}`")
    lines.extend([
        "",
        "## Next Step",
        "",
        f"- {payload['recommended_next_action']}",
        "",
        "## Task Surface",
        "",
        "| set_id | task_id | domain | ligand_sizes |",
        "| --- | --- | --- | ---: |",
    ])
    for row in payload["task_rows"]:
        lines.append(f"| {row['set_id']} | {row['task_id']} | {row['domain']} | {row['ligand_sizes']} |")
    lines.extend([
        "",
        "## Generated Profiles",
        "",
        "| task_id | generated_profile_json | runtime_hook_ready | active_score_change_allowed |",
        "| --- | --- | --- | --- |",
    ])
    for row in payload["profile_rows"]:
        lines.append(
            f"| {row['task_id']} | `{row['generated_profile_json']}` | {row['runtime_hook_ready']} | {row['active_score_change_allowed']} |"
        )
    lines.extend([
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
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the next runnable ion/kinase equal-size shadow scaffold from the current GPCR shadow pattern.")
    parser.add_argument("--source-spec-json", default=DEFAULT_SOURCE_SPEC_JSON)
    parser.add_argument("--shadow-origin-artifact", default=DEFAULT_SHADOW_ORIGIN_ARTIFACT)
    parser.add_argument("--generated-root", default=DEFAULT_GENERATED_ROOT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        source_spec_json=_resolve(args.source_spec_json),
        shadow_origin_artifact=_resolve(args.shadow_origin_artifact),
        generated_root=_resolve(args.generated_root),
    )
    _write_json(_resolve(args.out_json), payload)
    _write_csv(_resolve(args.out_csv), payload["profile_rows"])
    _write_markdown(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
