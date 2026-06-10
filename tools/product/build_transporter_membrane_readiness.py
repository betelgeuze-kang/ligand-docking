#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.product import run_transporter_membrane_scaffold_check as scaffold_check

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GAP_CSV = "config/transporter_membrane_expansion_gap_checklist_v1.csv"
DEFAULT_AQP1_PLAN_JSON = "runs/aqp1_p0_packet_plan_current.json"
DEFAULT_GLUT1_PLAN_JSON = "runs/glut1_p0_packet_plan_current.json"
DEFAULT_DONOR_POLICY_JSON = "runs/transporter_fit_donor_policy_decision_current.json"
DEFAULT_OUT_JSON = "runs/transporter_membrane_readiness_current.json"
DEFAULT_OUT_CSV = "runs/transporter_membrane_readiness_current.csv"
DEFAULT_OUT_MD = "runs/transporter_membrane_readiness_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _aqp1_p0_open_count(aqp1_plan: dict[str, Any] | None) -> int | None:
    if not aqp1_plan:
        return None
    rows = list(aqp1_plan.get("rows", []) or [])
    p0_artifacts = {
        "target_native_csv",
        "ligand_reference_csv",
        "eval_split_csv",
        "ligand_meta_csv",
        "target_meta_csv",
        "profile_json",
    }
    return sum(
        1
        for row in rows
        if str(row.get("artifact", "")).strip() in p0_artifacts
        and str(row.get("status", "")).strip() == "todo"
    )


def _target_plan_p0_open_count(plan: dict[str, Any] | None) -> int | None:
    if not plan:
        return None
    summary = dict(plan.get("summary", {}) or {})
    if "p0_open_count" in summary:
        return int(summary.get("p0_open_count") or 0)
    rows = list(plan.get("rows", []) or [])
    p0_artifacts = {
        "target_native_csv",
        "ligand_reference_csv",
        "eval_split_csv",
        "ligand_meta_csv",
        "target_meta_csv",
        "profile_json",
    }
    return sum(
        1
        for row in rows
        if str(row.get("artifact", "")).strip() in p0_artifacts
        and str(row.get("status", "")).strip() == "todo"
    )


def build_payload(
    scaffold_payload: dict[str, Any],
    gap_rows: list[dict[str, str]],
    aqp1_plan: dict[str, Any] | None = None,
    glut1_plan: dict[str, Any] | None = None,
    donor_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = dict(scaffold_payload.get("summary", {}) or {})
    aqp1_plan_summary = dict((aqp1_plan or {}).get("summary", {}) or {})
    aqp1_plan_open = _aqp1_p0_open_count(aqp1_plan)
    glut1_plan_summary = dict((glut1_plan or {}).get("summary", {}) or {})
    glut1_plan_open = _target_plan_p0_open_count(glut1_plan)
    donor_summary = dict((donor_policy or {}).get("summary", {}) or {})
    scaffold_policy_frozen = (
        donor_summary.get("scaffold_policy_frozen") is True
        and str(donor_summary.get("decision_status", "")).strip() == "scaffold_default_keep_existing_fit_donor_pool"
        and bool(str(donor_summary.get("scaffold_fit_donor_target", "")).strip())
    )
    p0_open = [row for row in gap_rows if str(row.get("priority", "")).strip() == "P0" and str(row.get("status", "")).strip() == "todo"]
    optional_open = [row for row in gap_rows if str(row.get("status", "")).strip() == "optional"]
    if aqp1_plan_open is not None:
        p0_open = [row for row in p0_open if str(row.get("target_id", "")).strip() != "Aquaporin_1"]
    if glut1_plan_open is not None:
        p0_open = [row for row in p0_open if str(row.get("target_id", "")).strip() != "GLUT1_4PYP"]
    if scaffold_policy_frozen:
        p0_open = [
            row
            for row in p0_open
            if str(row.get("required_artifact", "")).strip() != "fit_donor_policy"
        ]
    target_rows: list[dict[str, Any]] = []
    aqp1_core_open = aqp1_plan_open or 0
    glut1_core_open = glut1_plan_open or 0
    family_p0_open_count = len(p0_open)
    total_p0_open_count = family_p0_open_count + aqp1_core_open + glut1_core_open
    for target in ("Aquaporin_1", "GLUT1_4PYP"):
        target_gap_rows = [row for row in gap_rows if str(row.get("target_id", "")).strip() == target]
        target_p0 = [row for row in target_gap_rows if str(row.get("priority", "")).strip() == "P0" and str(row.get("status", "")).strip() == "todo"]
        target_p0_open_count = len(target_p0)
        next_required_step = (
            "curate ligand/reference/meta packets and freeze pocket centroid"
            if target == "Aquaporin_1"
            else "curate ligand/reference/meta packets, freeze pocket centroid, and state annotation"
        )
        if target == "Aquaporin_1" and aqp1_plan_open is not None:
            target_p0_open_count = aqp1_plan_open
            next_required_step = (
                "burn down the remaining AQP1 ligand packet blockers and keep donor policy frozen at the family level"
                if aqp1_plan_summary
                else next_required_step
            )
        if target == "GLUT1_4PYP" and glut1_plan_open is not None:
            target_p0_open_count = glut1_plan_open
            if glut1_plan_summary:
                next_steps = ",".join(str(item) for item in glut1_plan_summary.get("next_priority_steps") or [])
                next_required_step = (
                    "freeze GLUT1 pocket centroid and replace the remaining synchronized ligand packet placeholders"
                    if "glut1_target_native" in next_steps
                    else "replace the remaining synchronized GLUT1 ligand reference/split/meta placeholders"
                )
            else:
                next_required_step = next_required_step
        target_rows.append(
            {
                "target_id": target,
                "gap_row_count": len(target_gap_rows),
                "p0_open_count": target_p0_open_count,
                "scaffold_profile_present": "yes",
                "dry_run_only": "yes",
                "next_required_step": next_required_step,
            }
        )
    return {
        "summary": {
            "validate_only_ok": bool(scaffold_payload.get("ok", False)),
            "artifact_exists_count": int(summary.get("artifact_exists_count", 0)),
            "artifact_count": int(summary.get("artifact_count", 0)),
            "task_count": int(summary.get("task_count", 0)),
            "profile_count": int(summary.get("profile_count", 0)),
            "p0_open_count": total_p0_open_count,
            "family_p0_open_count": family_p0_open_count,
            "aqp1_core_p0_open_count": aqp1_core_open if aqp1_plan_open is not None else len(
                [
                    row
                    for row in gap_rows
                    if str(row.get("target_id", "")).strip() == "Aquaporin_1"
                    and str(row.get("priority", "")).strip() == "P0"
                    and str(row.get("status", "")).strip() == "todo"
                ]
            ),
            "glut1_core_p0_open_count": glut1_core_open if glut1_plan_open is not None else len(
                [
                    row
                    for row in gap_rows
                    if str(row.get("target_id", "")).strip() == "GLUT1_4PYP"
                    and str(row.get("priority", "")).strip() == "P0"
                    and str(row.get("status", "")).strip() == "todo"
                ]
            ),
            "optional_open_count": len(optional_open),
            "scaffold_fit_donor_policy_frozen": scaffold_policy_frozen,
            "scaffold_fit_donor_target": str(donor_summary.get("scaffold_fit_donor_target", "") or ""),
            "next_required_step": (
                "Finish the remaining AQP1 ligand packet blockers, then continue GLUT1 and keep transporter family token unsupported until dry_run scaffolds become runnable."
                if aqp1_plan_open is not None
                else "Finish AQP1/GLUT1 P0 packet blockers and keep transporter family token unsupported until dry_run scaffolds become runnable."
            ),
        },
        "target_rows": target_rows,
        "p0_rows": [
            {
                "target_id": str(row.get("target_id", "")).strip(),
                "required_artifact": str(row.get("required_artifact", "")).strip(),
                "proposed_repo_path": str(row.get("proposed_repo_path", "")).strip(),
                "notes": str(row.get("notes", "")).strip(),
            }
            for row in p0_open
        ],
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Membrane Readiness",
        "",
        f"- validate_only_ok: `{s['validate_only_ok']}`",
        f"- artifact_exists_count: `{s['artifact_exists_count']}/{s['artifact_count']}`",
        f"- task_count: `{s['task_count']}`",
        f"- profile_count: `{s['profile_count']}`",
        f"- p0_open_count: `{s['p0_open_count']}`",
        f"- family_p0_open_count: `{s['family_p0_open_count']}`",
        f"- aqp1_core_p0_open_count: `{s['aqp1_core_p0_open_count']}`",
        f"- glut1_core_p0_open_count: `{s['glut1_core_p0_open_count']}`",
        f"- optional_open_count: `{s['optional_open_count']}`",
        f"- scaffold_fit_donor_policy_frozen: `{s['scaffold_fit_donor_policy_frozen']}`",
        f"- scaffold_fit_donor_target: `{s['scaffold_fit_donor_target']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Target Rows",
        "",
        "| target_id | gap_row_count | p0_open_count | scaffold_profile_present | dry_run_only | next_required_step |",
        "| --- | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["target_rows"]:
        lines.append(
            f"| {row['target_id']} | {row['gap_row_count']} | {row['p0_open_count']} | {row['scaffold_profile_present']} | {row['dry_run_only']} | {row['next_required_step']} |"
        )
    lines.extend(["", "## P0 Open Rows", "", "| target_id | required_artifact | proposed_repo_path | notes |", "| --- | --- | --- | --- |"])
    for row in payload["p0_rows"]:
        lines.append(
            f"| {row['target_id']} | `{row['required_artifact']}` | `{row['proposed_repo_path']}` | {row['notes']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build transporter membrane scaffold readiness from validate-only scaffold checks and gap checklist.")
    p.add_argument("--root", default=".")
    p.add_argument("--gap-csv", default=DEFAULT_GAP_CSV)
    p.add_argument("--aqp1-plan-json", default=DEFAULT_AQP1_PLAN_JSON)
    p.add_argument("--glut1-plan-json", default=DEFAULT_GLUT1_PLAN_JSON)
    p.add_argument("--donor-policy-json", default=DEFAULT_DONOR_POLICY_JSON)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    scaffold_payload = scaffold_check.run_check(root=str(_resolve(args.root)))
    gap_rows = _read_csv(_resolve(args.gap_csv))
    aqp1_plan_path = _resolve(args.aqp1_plan_json)
    aqp1_plan = _load_json(aqp1_plan_path) if aqp1_plan_path.exists() else None
    glut1_plan_path = _resolve(args.glut1_plan_json)
    glut1_plan = _load_json(glut1_plan_path) if glut1_plan_path.exists() else None
    donor_policy_path = _resolve(args.donor_policy_json)
    donor_policy = _load_json(donor_policy_path) if donor_policy_path.exists() else None
    payload = build_payload(scaffold_payload, gap_rows, aqp1_plan, glut1_plan, donor_policy)
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(out_csv, payload["target_rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()
