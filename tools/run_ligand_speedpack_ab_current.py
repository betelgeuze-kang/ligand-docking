#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

_TASK_BUNDLE_MAP: dict[str, list[str]] = {
    "trpv1_full": ["ion_trpv1_chembl20_full", "ion_trpv1_chembl50_full"],
    "trpv1_all": ["ion_trpv1_chembl20_smoke", "ion_trpv1_chembl20_full", "ion_trpv1_chembl50_full"],
    "gpcr_full": ["gpcr_core_full", "gpcr_chembl50_full"],
    "gpcr_all": ["gpcr_smoke", "gpcr_core_full", "gpcr_chembl50_full"],
    "kinase_full": ["kinase_core_full", "kinase_strict_full"],
    "kinase_all": ["kinase_smoke", "kinase_core_full", "kinase_strict_full"],
    "slow_full": ["gpcr_core_full", "gpcr_chembl50_full", "ion_trpv1_chembl20_full", "ion_trpv1_chembl50_full"],
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _parse_csv_list(spec: str) -> list[str]:
    return [tok.strip() for tok in str(spec or "").split(",") if tok.strip()]


def _resolve_baseline_run_root(explicit: str, package_meta_json: str) -> str:
    if str(explicit).strip():
        return str(_resolve_repo_path(explicit))
    meta_path = _resolve_repo_path(package_meta_json)
    if not meta_path.exists():
        return ""
    meta = _read_json(meta_path)
    run_root = str(meta.get("run_root") or "").strip()
    return str(Path(run_root).resolve()) if run_root else ""


def _available_ligand_task_rows(spec: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for set_row in spec.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        for task in set_row.get("tasks", []):
            if str(task.get("kind", "")).strip() != "ligand_stress":
                continue
            rows.append(
                {
                    "set_id": set_id,
                    "task_id": str(task.get("task_id", "")).strip(),
                    "domain": str(task.get("domain", "")).strip(),
                    "ligand_sizes": str(task.get("ligand_sizes", "")).strip(),
                }
            )
    return rows


def _resolve_task_selection(
    spec: dict[str, Any],
    *,
    selected_task_ids: list[str],
    task_bundle: str,
    include_smoke: bool,
) -> dict[str, Any]:
    available_rows = _available_ligand_task_rows(spec)
    available_task_ids = [row["task_id"] for row in available_rows]
    requested_bundle = str(task_bundle or "").strip().lower()
    bundle_task_ids = list(_TASK_BUNDLE_MAP.get(requested_bundle, [])) if requested_bundle else []
    requested_task_ids = [task_id for task_id in selected_task_ids if task_id]

    selected_ids: list[str] = []
    for task_id in [*bundle_task_ids, *requested_task_ids]:
        if task_id not in selected_ids:
            selected_ids.append(task_id)

    warnings: list[str] = []
    errors: list[str] = []
    if requested_bundle and requested_bundle not in _TASK_BUNDLE_MAP:
        errors.append(f"unknown task bundle: {requested_bundle}")
    missing_task_ids = [task_id for task_id in selected_ids if task_id not in available_task_ids]
    if missing_task_ids:
        errors.append(f"selected task ids not present in source spec: {missing_task_ids}")
    if not selected_ids:
        errors.append("no task ids selected; provide --task-ids and/or --task-bundle")

    smoke_ids_in_bundle = [
        row["task_id"]
        for row in available_rows
        if row["task_id"] in bundle_task_ids and row["ligand_sizes"] == "64"
    ]
    if smoke_ids_in_bundle and (not include_smoke):
        warnings.append(
            f"task bundle {requested_bundle} includes smoke tasks {smoke_ids_in_bundle}, but include_smoke=false so they will be dropped."
        )

    selected_rows_preview: list[dict[str, str]] = []
    selected_lookup = set(selected_ids)
    for row in available_rows:
        if row["task_id"] not in selected_lookup:
            continue
        if (not include_smoke) and row["ligand_sizes"] == "64":
            continue
        selected_rows_preview.append(row)
    if selected_ids and (not selected_rows_preview):
        errors.append("task selection produced zero runnable ligand_stress tasks after smoke/full filtering")
    runnable_task_ids = [row["task_id"] for row in selected_rows_preview]

    return {
        "requested_bundle": requested_bundle,
        "bundle_task_ids": bundle_task_ids,
        "requested_task_ids": requested_task_ids,
        "selected_task_ids": selected_ids,
        "runnable_task_ids": runnable_task_ids,
        "selected_rows_preview": selected_rows_preview,
        "available_task_ids": available_task_ids,
        "available_task_bundles": {key: list(value) for key, value in sorted(_TASK_BUNDLE_MAP.items())},
        "warnings": warnings,
        "errors": errors,
    }


def _speedpack_profile_payload(base: dict[str, Any], *, strict_auto: bool) -> dict[str, Any]:
    out = dict(base)
    out["traj_prod_stage2_preset"] = "auto"
    out["traj_prod_stage2_preset_strict"] = bool(strict_auto)
    out["traj_prod_speedpack"] = True
    out["traj_prod_adaptive_frame_budget"] = True
    out["traj_prod_early_stop_enabled"] = True
    out["traj_prod_light_artifacts"] = True
    out["traj_frame_output_format"] = "manifest_only"
    out.setdefault("traj_prod_light_progress_every_jobs", 250)
    return out


def _select_speedpack_tasks(
    spec: dict[str, Any],
    *,
    selected_task_ids: list[str],
    include_smoke: bool,
) -> list[dict[str, Any]]:
    selected = set(selected_task_ids)
    rows: list[dict[str, Any]] = []
    for set_row in spec.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        for task in set_row.get("tasks", []):
            if str(task.get("kind", "")).strip() != "ligand_stress":
                continue
            task_id = str(task.get("task_id", "")).strip()
            ligand_sizes = str(task.get("ligand_sizes", "")).strip()
            if selected and task_id not in selected:
                continue
            if (not include_smoke) and ligand_sizes == "64":
                continue
            rows.append(
                {
                    "set_id": set_id,
                    "task": task,
                    "task_id": task_id,
                    "domain": str(task.get("domain", "")).strip(),
                    "ligand_sizes": ligand_sizes,
                    "profile_json": str(task.get("profile_json", "")).strip(),
                }
            )
    return rows


def _build_speedpack_candidate(
    *,
    source_spec_json: str,
    out_dir: Path,
    selected_task_ids: list[str],
    include_smoke: bool,
    ligand_size_override: str,
    strict_auto: bool,
    task_bundle: str = "",
) -> dict[str, Any]:
    spec_path = _resolve_repo_path(source_spec_json)
    spec = _read_json(spec_path)
    selection = _resolve_task_selection(
        spec,
        selected_task_ids=selected_task_ids,
        task_bundle=task_bundle,
        include_smoke=include_smoke,
    )
    if selection["errors"]:
        raise ValueError("; ".join(str(x) for x in selection["errors"]))
    selected_rows = _select_speedpack_tasks(spec, selected_task_ids=selection["selected_task_ids"], include_smoke=include_smoke)
    profiles_dir = out_dir / "profiles"
    spec_dir = out_dir / "specs"
    profile_rows: list[dict[str, Any]] = []
    profile_map: dict[str, str] = {}
    task_rows: list[dict[str, Any]] = []
    set_map: dict[str, list[dict[str, Any]]] = {}
    source_set_meta: dict[str, dict[str, str]] = {}
    for set_row in spec.get("sets", []):
        set_id = str(set_row.get("set_id", "")).strip()
        if not set_id:
            continue
        meta = {
            "set_id": set_id,
            "title": str(set_row.get("title", "") or set_id).strip(),
            "purpose": str(
                set_row.get("purpose", "")
                or f"Equal-size ligand speedpack A/B slice derived from {set_id}."
            ).strip(),
        }
        claim_role = str(set_row.get("claim_role", "") or "").strip()
        if claim_role:
            meta["claim_role"] = claim_role
        source_set_meta[set_id] = meta

    for row in selected_rows:
        task = dict(row["task"])
        source_profile_json = str(row["profile_json"]).strip()
        source_profile_path = _resolve_repo_path(source_profile_json)
        if source_profile_json not in profile_map:
            base_profile = _read_json(source_profile_path)
            stem = source_profile_path.stem + "_speedpackab1.json"
            out_profile_path = profiles_dir / stem
            _write_json(out_profile_path, _speedpack_profile_payload(base_profile, strict_auto=bool(strict_auto)))
            profile_map[source_profile_json] = str(out_profile_path.resolve())
            profile_rows.append(
                {
                    "source_profile_json": source_profile_json,
                    "generated_profile_json": str(out_profile_path.resolve()),
                    "traj_prod_stage2_preset": "auto",
                    "traj_prod_stage2_preset_strict": bool(strict_auto),
                    "traj_prod_speedpack": True,
                    "traj_prod_early_stop_enabled": True,
                    "traj_prod_light_artifacts": True,
                    "traj_frame_output_format": "manifest_only",
                }
            )
        task["profile_json"] = profile_map[source_profile_json]
        before_sizes = str(task.get("ligand_sizes", "")).strip()
        if str(ligand_size_override).strip() and before_sizes != "64":
            task["ligand_sizes"] = str(ligand_size_override).strip()
        suffix = str(task.get("date_tag_suffix", task["task_id"])).strip()
        task["date_tag_suffix"] = f"{suffix}-speedpackab1"
        set_map.setdefault(str(row["set_id"]), []).append(task)
        task_rows.append(
            {
                "set_id": str(row["set_id"]),
                "task_id": str(task.get("task_id", "")).strip(),
                "domain": str(task.get("domain", "")).strip(),
                "ligand_sizes_before": before_sizes,
                "ligand_sizes_after": str(task.get("ligand_sizes", "")).strip(),
                "is_smoke": bool(before_sizes == "64"),
                "profile_json_before": source_profile_json,
                "profile_json_after": task["profile_json"],
            }
        )

    candidate_spec = {
        "protocol_id": "ligand_speedpack_ab_v1",
        "protocol_title": "Ligand Speedpack A/B Current",
        "protocol_version": "v1",
        "global_governance": {
            "comparison_kind": "equal_size_speedpack_ab",
            "source_spec_json": str(spec_path.resolve()),
        },
        "sets": [
            {**source_set_meta.get(set_id, {"set_id": set_id, "title": set_id, "purpose": "Equal-size A/B slice."}), "tasks": tasks}
            for set_id, tasks in set_map.items()
        ],
    }
    spec_dir.mkdir(parents=True, exist_ok=True)
    candidate_spec_path = spec_dir / "ligand_speedpack_ab_current_v1.json"
    _write_json(candidate_spec_path, candidate_spec)
    return {
        "candidate_spec_json": str(candidate_spec_path.resolve()),
        "selected_rows": selected_rows,
        "selection": selection,
        "task_rows": task_rows,
        "profile_rows": profile_rows,
        "set_ids": list(set_map.keys()),
    }


def _selected_scope_summary(task_rows: list[dict[str, Any]]) -> dict[str, Any]:
    full_rows = [row for row in task_rows if not bool(row["is_smoke"])]
    smoke_rows = [row for row in task_rows if bool(row["is_smoke"])]
    return {
        "selected_task_count": len(task_rows),
        "selected_full_task_count": len(full_rows),
        "selected_smoke_task_count": len(smoke_rows),
        "selected_set_ids": sorted({row["set_id"] for row in task_rows}),
        "domains_touched": sorted({row["domain"] for row in task_rows if str(row["domain"]).strip()}),
        "slow_domain_task_ids": [row["task_id"] for row in task_rows],
    }


def _guardrail_summary() -> list[dict[str, str]]:
    return [
        {"guardrail_id": "no_pass_to_fail", "threshold": "0 pass->fail transitions", "scope": "selected A/B slice"},
        {"guardrail_id": "pr_auc_drop_max_0p02", "threshold": ">= -0.02 absolute", "scope": "selected A/B slice"},
        {"guardrail_id": "top20_hit_drop_max_1", "threshold": ">= -1 hit", "scope": "selected A/B slice"},
        {"guardrail_id": "stage2_speedup_min_1p25x", "threshold": ">= 1.25x on selected slow tasks", "scope": "operational preflight"},
    ]


def _current_artifact_paths() -> dict[str, Path]:
    runs_root = ROOT / "runs"
    return {
        "ab_json": runs_root / "ligand_speedpack_ab_current.json",
        "runtime_json": runs_root / "ligand_speedpack_ab_runtime_current.json",
        "runtime_csv": runs_root / "ligand_speedpack_ab_runtime_current.csv",
        "summary_json": runs_root / "ligand_speedpack_ab_summary_current.json",
        "summary_csv": runs_root / "ligand_speedpack_ab_summary_current.csv",
        "summary_md": runs_root / "ligand_speedpack_ab_summary_current.md",
    }


def _pick_single_task_sla_paths(runtime_json: Path) -> tuple[str, str]:
    if not runtime_json.exists():
        return "", ""
    try:
        payload = _read_json(runtime_json)
    except Exception:
        return "", ""
    rows = payload.get("rows", []) if isinstance(payload.get("rows"), list) else []
    if len(rows) != 1:
        return "", ""
    row = rows[0]
    return (
        str(row.get("baseline_sla_summary_json") or "").strip(),
        str(row.get("candidate_sla_summary_json") or "").strip(),
    )


def _refresh_current_artifacts(
    *,
    payload: dict[str, Any],
    baseline_run_root: str,
    candidate_run_root: str,
    comparison_enabled: bool,
) -> dict[str, Any]:
    artifacts = _current_artifact_paths()
    _write_json(artifacts["ab_json"], payload)

    comparison_json = str(payload.get("comparison_root", "")).strip()
    if comparison_json:
        comparison_json = str((Path(comparison_json) / "summary.json").resolve())
    if (not comparison_enabled) or (not comparison_json):
        comparison_json = ""

    runtime_cmd = [
        sys.executable,
        str(ROOT / "tools/extract_ligand_scaleup_results.py"),
        "--baseline-run-root",
        str(baseline_run_root),
        "--candidate-run-root",
        str(candidate_run_root),
        "--comparison-json",
        str(comparison_json),
        "--out-json",
        str(artifacts["runtime_json"]),
        "--out-csv",
        str(artifacts["runtime_csv"]),
    ]
    runtime_rc = subprocess.run(runtime_cmd, cwd=str(ROOT)).returncode
    if runtime_rc != 0:
        return {
            "enabled": True,
            "ok": False,
            "failed_step": "extract_ligand_scaleup_results",
            "runtime_cmd": runtime_cmd,
            "runtime_returncode": int(runtime_rc),
        }

    baseline_sla_json, candidate_sla_json = _pick_single_task_sla_paths(artifacts["runtime_json"])
    summary_cmd = [
        sys.executable,
        str(ROOT / "tools/build_ligand_speedpack_ab_summary.py"),
        "--ab-json",
        str(artifacts["ab_json"]),
        "--ab-spec-json",
        str(payload.get("candidate_spec_json", "")),
        "--comparison-json",
        str(comparison_json),
        "--baseline-summary-json",
        str((Path(baseline_run_root) / "summary.json").resolve()) if str(baseline_run_root).strip() else "",
        "--candidate-summary-json",
        str((Path(candidate_run_root) / "summary.json").resolve()) if str(candidate_run_root).strip() else "",
        "--baseline-sla-json",
        str(baseline_sla_json),
        "--candidate-sla-json",
        str(candidate_sla_json),
        "--out-json",
        str(artifacts["summary_json"]),
        "--out-csv",
        str(artifacts["summary_csv"]),
        "--out-md",
        str(artifacts["summary_md"]),
    ]
    summary_rc = subprocess.run(summary_cmd, cwd=str(ROOT)).returncode
    if summary_rc != 0:
        return {
            "enabled": True,
            "ok": False,
            "failed_step": "build_ligand_speedpack_ab_summary",
            "runtime_cmd": runtime_cmd,
            "runtime_returncode": int(runtime_rc),
            "summary_cmd": summary_cmd,
            "summary_returncode": int(summary_rc),
        }

    return {
        "enabled": True,
        "ok": True,
        "failed_step": "",
        "runtime_cmd": runtime_cmd,
        "runtime_returncode": int(runtime_rc),
        "summary_cmd": summary_cmd,
        "summary_returncode": int(summary_rc),
        "artifacts": {key: str(path.resolve()) for key, path in artifacts.items()},
        "single_task_sla_refresh": bool(baseline_sla_json and candidate_sla_json),
        "baseline_sla_json": str(baseline_sla_json),
        "candidate_sla_json": str(candidate_sla_json),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Build and optionally run a lightweight equal-size speedpack A/B regression slice for the slowest ligand domains."
    )
    ap.add_argument("--tag", default=f"{dt.date.today().isoformat()}_ligand_speedpack_ab_v1")
    ap.add_argument("--source-spec-json", default="config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json")
    ap.add_argument(
        "--task-ids",
        default="ion_trpv1_chembl20_full,ion_trpv1_chembl50_full",
        help="Comma-separated ligand_stress task ids to include in the speedpack A/B slice.",
    )
    ap.add_argument(
        "--task-bundle",
        default="trpv1_full",
        help="Optional task bundle shortcut. Examples: trpv1_full, trpv1_all, gpcr_full, slow_full.",
    )
    ap.add_argument("--include-smoke", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument(
        "--ligand-size-override",
        default="",
        help="Optional non-smoke ligand_sizes override for the candidate speedpack slice. Leave empty to keep source sizes.",
    )
    ap.add_argument("--strict-auto", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--baseline-run-root", default="")
    ap.add_argument("--current-package-meta-json", default="runs/biorxiv_external_validation_package_current.json")
    ap.add_argument("--out-root", default="runs/external_validation_blind_runs")
    ap.add_argument("--generated-root", default="runs/ligand_speedpack_ab_current")
    ap.add_argument("--comparison-out-root", default="runs")
    ap.add_argument("--compare-label", default="")
    ap.add_argument("--skip-compare", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--refresh-current-artifacts", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    args = ap.parse_args(argv)

    generated_root = _resolve_repo_path(args.generated_root)
    source_spec = _read_json(_resolve_repo_path(args.source_spec_json))
    selection = _resolve_task_selection(
        source_spec,
        selected_task_ids=_parse_csv_list(args.task_ids),
        task_bundle=str(args.task_bundle),
        include_smoke=bool(args.include_smoke),
    )
    if selection["errors"]:
        print(
            json.dumps(
                {
                    "ok": False,
                    "tag": args.tag,
                    "dry_run": bool(args.dry_run),
                    "source_spec_json": str(_resolve_repo_path(args.source_spec_json)),
                    "requested_task_bundle": selection["requested_bundle"],
                    "requested_task_ids": selection["requested_task_ids"],
                    "selected_task_ids": selection["selected_task_ids"],
                    "selection_errors": selection["errors"],
                    "selection_warnings": selection["warnings"],
                    "available_task_ids": selection["available_task_ids"],
                    "available_task_bundles": selection["available_task_bundles"],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 2
    built = _build_speedpack_candidate(
        source_spec_json=str(args.source_spec_json),
        out_dir=generated_root,
        selected_task_ids=selection["selected_task_ids"],
        include_smoke=bool(args.include_smoke),
        ligand_size_override=str(args.ligand_size_override),
        strict_auto=bool(args.strict_auto),
        task_bundle=selection["requested_bundle"],
    )
    task_rows = built["task_rows"]
    scope_summary = _selected_scope_summary(task_rows)
    selected_sets = ",".join(built["set_ids"])
    candidate_run_root = ROOT / args.out_root / f"external_validation_blind_runs_{args.tag}"
    baseline_run_root = _resolve_baseline_run_root(args.baseline_run_root, args.current_package_meta_json)
    compare_label = str(args.compare_label).strip() or f"{args.tag}_vs_current"
    comparison_enabled = bool(baseline_run_root) and (not bool(args.skip_compare))
    comparison_skip_reason = "skip_compare" if bool(args.skip_compare) else ("baseline_run_root_not_found" if not baseline_run_root else "")

    run_cmd = [
        sys.executable,
        str(ROOT / "tools/run_external_validation_blind_sets.py"),
        "--tag",
        str(args.tag),
        "--sets",
        selected_sets,
        "--set-spec-json",
        str(built["candidate_spec_json"]),
        "--out-root",
        str(args.out_root),
    ]
    compare_cmd = [
        sys.executable,
        str(ROOT / "tools/compare_biorxiv_external_validation_runs.py"),
        "--baseline-run-root",
        str(baseline_run_root),
        "--candidate-run-root",
        str(candidate_run_root.resolve()),
        "--out-root",
        str(args.comparison_out_root),
        "--label",
        compare_label,
    ]

    payload = {
        "ok": True,
        "tag": args.tag,
        "dry_run": bool(args.dry_run),
        "source_spec_json": str(_resolve_repo_path(args.source_spec_json)),
        "candidate_spec_json": str(built["candidate_spec_json"]),
        "generated_root": str(generated_root.resolve()),
        "requested_task_bundle": selection["requested_bundle"],
        "bundle_task_ids": selection["bundle_task_ids"],
        "requested_task_ids": selection["requested_task_ids"],
        "selected_task_ids": selection["selected_task_ids"],
        "runnable_task_ids": selection["runnable_task_ids"],
        "selection_warnings": selection["warnings"],
        "available_task_bundles": selection["available_task_bundles"],
        "selected_sets": built["set_ids"],
        "selected_scope_summary": scope_summary,
        "task_rows": task_rows,
        "profile_rows": built["profile_rows"],
        "guardrail_summary": _guardrail_summary(),
        "baseline_run_root": str(baseline_run_root),
        "baseline_run_root_found": bool(baseline_run_root),
        "candidate_run_root": str(candidate_run_root.resolve()),
        "compare_label": compare_label,
        "comparison_root": str((ROOT / args.comparison_out_root / f"biorxiv_run_comparison_{compare_label}").resolve()),
        "comparison_kind": "equal_size_speedpack_ab",
        "comparison_enabled": bool(comparison_enabled),
        "comparison_skip_reason": str(comparison_skip_reason),
        "run_cmd": run_cmd,
        "compare_cmd": compare_cmd if comparison_enabled else [],
        "refresh_current_artifacts": bool(args.refresh_current_artifacts),
        "refresh_result": {"enabled": False, "ok": None},
    }
    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    run_rc = subprocess.run(run_cmd, cwd=str(ROOT)).returncode
    if run_rc != 0:
        return int(run_rc)
    if not comparison_enabled:
        if bool(args.refresh_current_artifacts):
            payload["refresh_result"] = _refresh_current_artifacts(
                payload=payload,
                baseline_run_root=str(baseline_run_root),
                candidate_run_root=str(candidate_run_root.resolve()),
                comparison_enabled=False,
            )
            if not bool(payload["refresh_result"].get("ok", False)):
                return 3
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    compare_rc = subprocess.run(compare_cmd, cwd=str(ROOT)).returncode
    if compare_rc != 0:
        return int(compare_rc)
    if bool(args.refresh_current_artifacts):
        payload["refresh_result"] = _refresh_current_artifacts(
            payload=payload,
            baseline_run_root=str(baseline_run_root),
            candidate_run_root=str(candidate_run_root.resolve()),
            comparison_enabled=True,
        )
        if not bool(payload["refresh_result"].get("ok", False)):
            return 3
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
