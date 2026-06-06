from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_FAMILIES: dict[str, dict[str, Any]] = {
    "non_kinase_enzyme_ca2": {
        "label": "Non-kinase enzyme / CA2",
        "template_json": "config/external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template.json",
    },
    "nuclear_receptor_pxr": {
        "label": "Nuclear receptor / PXR",
        "template_json": "config/external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json",
    },
    "transporter_membrane": {
        "label": "Transporter / membrane",
        "template_json": "config/external_validation_transporter_membrane_sets_v1_template.json",
    },
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _collect_profile_rows(
    family_id: str,
    family_label: str,
    template_path: Path,
    template_payload: dict[str, Any],
    repo_root: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_profile_paths: set[str] = set()
    required_artifacts = template_payload.get("required_artifacts", {})
    for key, raw_rel in required_artifacts.items():
        if not str(key).endswith("_profile_json"):
            continue
        rel = str(raw_rel)
        if rel in seen_profile_paths:
            continue
        seen_profile_paths.add(rel)
        profile_path = repo_root / rel
        exists = profile_path.exists()
        payload = _read_json(profile_path) if exists else {}
        rows.append(
            {
                "family_id": family_id,
                "family_label": family_label,
                "template_json": _safe_rel(template_path, repo_root),
                "profile_role": key.replace("_profile_json", ""),
                "profile_json": rel,
                "profile_exists": exists,
                "profile_dry_run": bool(payload.get("dry_run")) if exists else False,
                "profile_targets": str(payload.get("targets", "")) if exists else "",
                "profile_run_scope": str(payload.get("run_scope", "")) if exists else "",
                "profile_description": str(payload.get("description", "")) if exists else "",
            }
        )
    return rows


def _build_payload(repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    for family_id, spec in DEFAULT_FAMILIES.items():
        family_label = str(spec["label"])
        template_path = repo_root / str(spec["template_json"])
        template_exists = template_path.exists()
        template_payload = _read_json(template_path) if template_exists else {}
        template_status = str(template_payload.get("status", "")) if template_exists else ""
        task_count = sum(len(set_payload.get("tasks", [])) for set_payload in template_payload.get("sets", []))
        required_artifacts = template_payload.get("required_artifacts", {}) if template_exists else {}
        artifact_paths = [repo_root / str(value) for value in required_artifacts.values()]
        artifact_exists_count = sum(path.exists() for path in artifact_paths)
        profile_rows = (
            _collect_profile_rows(family_id, family_label, template_path, template_payload, repo_root)
            if template_exists
            else []
        )
        dry_run_profile_count = sum(1 for row in profile_rows if row["profile_dry_run"])
        rows.extend(profile_rows)
        summaries.append(
            {
                "family_id": family_id,
                "family_label": family_label,
                "template_json": _safe_rel(template_path, repo_root),
                "template_exists": template_exists,
                "template_status": template_status,
                "task_count": task_count,
                "required_artifact_count": len(artifact_paths),
                "required_artifact_exists_count": artifact_exists_count,
                "profile_count": len(profile_rows),
                "dry_run_profile_count": dry_run_profile_count,
                "all_profiles_dry_run": bool(profile_rows) and dry_run_profile_count == len(profile_rows),
                "ready_for_validate_only": bool(template_payload.get("scaffold_status", {}).get("ready_for_validate_only", False)),
                "claim_ready": bool(template_payload.get("scaffold_status", {}).get("claim_ready", False)),
            }
        )

    summary = {
        "family_count": len(summaries),
        "template_exists_count": sum(1 for row in summaries if row["template_exists"]),
        "all_profiles_dry_run_count": sum(1 for row in summaries if row["all_profiles_dry_run"]),
        "claim_ready_count": sum(1 for row in summaries if row["claim_ready"]),
        "families": summaries,
    }
    return rows, summary


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Ligand New-Family Readiness",
        "",
        f"- families: `{summary['family_count']}`",
        f"- templates present: `{summary['template_exists_count']}`",
        f"- all profiles dry-run: `{summary['all_profiles_dry_run_count']}`",
        f"- claim-ready families: `{summary['claim_ready_count']}`",
        "",
        "## Family Summary",
        "",
        "| family | template status | tasks | artifacts | profiles | dry-run profiles | validate-only ready | claim-ready |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for family in summary["families"]:
        lines.append(
            "| {family_label} | {template_status} | {task_count} | {required_artifact_exists_count}/{required_artifact_count} | "
            "{profile_count} | {dry_run_profile_count}/{profile_count} | {ready_for_validate_only} | {claim_ready} |".format(**family)
        )
    lines.extend(
        [
            "",
            "## Profile Details",
            "",
            "| family | role | profile | exists | dry_run | targets | scope |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['family_label']} | {row['profile_role']} | `{row['profile_json']}` | {row['profile_exists']} | "
            f"{row['profile_dry_run']} | `{row['profile_targets']}` | `{row['profile_run_scope']}` |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a readiness report for ligand new-family expansion scaffolds.")
    parser.add_argument(
        "--out-json",
        default="runs/ligand_new_family_readiness_current.json",
        help="Output JSON path.",
    )
    parser.add_argument(
        "--out-csv",
        default="runs/ligand_new_family_readiness_current.csv",
        help="Output CSV path.",
    )
    parser.add_argument(
        "--out-md",
        default="runs/ligand_new_family_readiness_current.md",
        help="Output Markdown path.",
    )
    parser.add_argument(
        "--root",
        default=str(ROOT),
        help="Repo root to inspect for scaffold files.",
    )
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    rows, summary = _build_payload(repo_root)
    out_json = Path(args.out_json)
    out_csv = Path(args.out_csv)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    _write_csv(out_csv, rows)
    _write_md(out_md, rows, summary)


if __name__ == "__main__":
    main()
