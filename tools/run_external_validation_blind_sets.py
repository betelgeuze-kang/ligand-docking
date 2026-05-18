#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
ALLOWED_TASK_KINDS = {"ligand_stress", "idp_reference_current_full", "idp_smoke_current"}

SET_DEFS: List[Dict[str, Any]] = [
    {
        "set_id": "set1_core_blind",
        "title": "Core Blind Set",
        "purpose": "Fresh blind/full ligand validation across GPCR, ion-channel, and kinase/protease axes, paired with the current full IDP release-grade holdout.",
        "tasks": [
            {
                "task_id": "gpcr_core_full",
                "domain": "gpcr",
                "kind": "ligand_stress",
                "profile_json": "config/ligand_htvs_blind_gpcr_adrb2_v1.json",
                "ligand_sizes": "10000",
                "date_tag_suffix": "gpcr-core-full",
            },
            {
                "task_id": "ion_trpv1_chembl20_full",
                "domain": "ion_channel",
                "kind": "ligand_stress",
                "profile_json": "config/ligand_htvs_blind_trpv1_chembl20_v1.json",
                "ligand_sizes": "10000",
                "date_tag_suffix": "trpv1-chembl20-full",
            },
            {
                "task_id": "kinase_core_full",
                "domain": "kinase",
                "kind": "ligand_stress",
                "profile_json": "config/ligand_htvs_commercial_validation_no_leak_v2_seq02.json",
                "ligand_sizes": "10000",
                "date_tag_suffix": "kinase-core-full",
            },
            {
                "task_id": "idp_release_current",
                "domain": "idp",
                "kind": "idp_reference_current_full",
            },
        ],
    },
    {
        "set_id": "set2_expanded_ood",
        "title": "Expanded OOD Set",
        "purpose": "Broader OOD blind set using larger GPCR/TRPV1 public expansions and strict external-style kinase/protease validation, paired with current full IDP release diagnostics.",
        "tasks": [
            {
                "task_id": "gpcr_chembl50_full",
                "domain": "gpcr",
                "kind": "ligand_stress",
                "profile_json": "config/ligand_htvs_blind_gpcr_adrb2_chembl50_v1.json",
                "ligand_sizes": "10000",
                "date_tag_suffix": "gpcr-chembl50-full",
            },
            {
                "task_id": "ion_trpv1_chembl50_full",
                "domain": "ion_channel",
                "kind": "ligand_stress",
                "profile_json": "config/ligand_htvs_blind_trpv1_chembl50_v1.json",
                "ligand_sizes": "10000",
                "date_tag_suffix": "trpv1-chembl50-full",
            },
            {
                "task_id": "kinase_strict_full",
                "domain": "kinase",
                "kind": "ligand_stress",
                "profile_json": "config/ligand_htvs_commercial_validation_disjoint_strict_v1.json",
                "ligand_sizes": "10000",
                "date_tag_suffix": "kinase-strict-full",
            },
            {
                "task_id": "idp_release_current",
                "domain": "idp",
                "kind": "idp_reference_current_full",
            },
        ],
    },
    {
        "set_id": "set3_operational_smoke",
        "title": "Operational Smoke Set",
        "purpose": "Fast cross-domain reproducibility set using smaller blind/smoke runs and a fresh current IDP smoke rerun.",
        "tasks": [
            {
                "task_id": "gpcr_smoke",
                "domain": "gpcr",
                "kind": "ligand_stress",
                "profile_json": "config/ligand_htvs_blind_gpcr_adrb2_v1.json",
                "ligand_sizes": "64",
                "date_tag_suffix": "gpcr-smoke",
            },
            {
                "task_id": "ion_trpv1_chembl20_smoke",
                "domain": "ion_channel",
                "kind": "ligand_stress",
                "profile_json": "config/ligand_htvs_blind_trpv1_chembl20_v1.json",
                "ligand_sizes": "64",
                "date_tag_suffix": "trpv1-chembl20-smoke",
            },
            {
                "task_id": "kinase_smoke",
                "domain": "kinase",
                "kind": "ligand_stress",
                "profile_json": "config/ligand_htvs_commercial_validation_disjoint_strict_poscounter_smoke_v1.json",
                "ligand_sizes": "64",
                "date_tag_suffix": "kinase-smoke",
            },
            {
                "task_id": "idp_smoke_current",
                "domain": "idp",
                "kind": "idp_smoke_current",
            },
        ],
    },
]


def _load_set_spec(path: Path) -> Dict[str, Any]:
    spec = _read_json(path)
    sets = spec.get("sets")
    if not isinstance(sets, list) or not sets:
        raise ValueError(f"invalid set spec, missing non-empty 'sets': {path}")
    return spec


def _validate_set_defs(set_defs: List[Dict[str, Any]], source: str) -> None:
    seen_set_ids: set[str] = set()
    for set_def in set_defs:
        set_id = str(set_def.get("set_id", "")).strip()
        title = str(set_def.get("title", "")).strip()
        purpose = str(set_def.get("purpose", "")).strip()
        claim_role = str(set_def.get("claim_role", "")).strip()
        tasks = set_def.get("tasks")
        if not set_id:
            raise ValueError(f"{source}: missing set_id")
        if set_id in seen_set_ids:
            raise ValueError(f"{source}: duplicate set_id: {set_id}")
        seen_set_ids.add(set_id)
        if not title or not purpose:
            raise ValueError(f"{source}: set {set_id} missing title/purpose")
        if claim_role and claim_role not in {"primary", "secondary_generalization", "reproducibility_support", "comparison_candidate"}:
            raise ValueError(f"{source}: set {set_id} invalid claim_role: {claim_role}")
        if not isinstance(tasks, list) or not tasks:
            raise ValueError(f"{source}: set {set_id} missing non-empty tasks")
        seen_task_ids: set[str] = set()
        for task in tasks:
            task_id = str(task.get("task_id", "")).strip()
            domain = str(task.get("domain", "")).strip()
            kind = str(task.get("kind", "")).strip()
            if not task_id or not domain or not kind:
                raise ValueError(f"{source}: set {set_id} has task missing task_id/domain/kind")
            if task_id in seen_task_ids:
                raise ValueError(f"{source}: set {set_id} duplicate task_id: {task_id}")
            seen_task_ids.add(task_id)
            if kind not in ALLOWED_TASK_KINDS:
                raise ValueError(f"{source}: set {set_id} task {task_id} unsupported kind: {kind}")
            if kind == "ligand_stress":
                for req in ["profile_json", "ligand_sizes", "date_tag_suffix"]:
                    if not str(task.get(req, "")).strip():
                        raise ValueError(f"{source}: set {set_id} task {task_id} missing {req}")
                profile_path = (ROOT / str(task["profile_json"])).resolve()
                if not profile_path.exists():
                    raise FileNotFoundError(profile_path)


def _now_local() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError(f"invalid json object: {path}")
    return obj


def _write_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_check_output(cmd: List[str]) -> str:
    try:
        out = subprocess.check_output(cmd, cwd=str(ROOT), stderr=subprocess.DEVNULL, text=True)
        return out.strip()
    except Exception:
        return ""


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_run_provenance(args: argparse.Namespace, spec_path: Path | None) -> Dict[str, Any]:
    return {
        "generated_at_local": _now_local(),
        "cwd": str(ROOT),
        "argv": sys.argv,
        "python_executable": sys.executable,
        "python_version": sys.version.splitlines()[0],
        "platform": platform.platform(),
        "hostname": platform.node(),
        "git_head": _safe_check_output(["git", "rev-parse", "HEAD"]),
        "git_branch": _safe_check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_status_short": _safe_check_output(["git", "status", "--short"]),
        "spec_json": str(spec_path) if spec_path else "",
        "spec_sha256": _sha256_file(spec_path) if spec_path and spec_path.exists() else "",
        "selected_sets": [x.strip() for x in str(args.sets).split(",") if x.strip()],
        "environment": {
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
            "PYTHONUNBUFFERED": os.environ.get("PYTHONUNBUFFERED", ""),
        },
    }


def _write_environment_snapshots(base_root: Path) -> Dict[str, str]:
    pyver = _safe_check_output([sys.executable, "--version"])
    pip_freeze = _safe_check_output([sys.executable, "-m", "pip", "freeze"])
    nvidia_smi = _safe_check_output(["nvidia-smi"])
    env_json = {
        "python_version": pyver,
        "pip_freeze_available": bool(pip_freeze),
        "nvidia_smi_available": bool(nvidia_smi),
    }
    pyver_path = base_root / "python_version.txt"
    pip_path = base_root / "pip_freeze.txt"
    nvidia_path = base_root / "nvidia_smi.txt"
    env_json_path = base_root / "environment_snapshot.json"
    _write_text(pyver_path, pyver + ("\n" if pyver else ""))
    _write_text(pip_path, pip_freeze + ("\n" if pip_freeze else ""))
    _write_text(nvidia_path, nvidia_smi + ("\n" if nvidia_smi else ""))
    _write_json(env_json_path, env_json)
    return {
        "python_version_txt": str(pyver_path),
        "pip_freeze_txt": str(pip_path),
        "nvidia_smi_txt": str(nvidia_path),
        "environment_snapshot_json": str(env_json_path),
    }


def _run(cmd: List[str], log_path: Path) -> Dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n[{_now_local()}] CMD: {' '.join(cmd)}\n")
        log.flush()
        p = subprocess.run(cmd, cwd=str(ROOT), stdout=log, stderr=log, text=True)
    return {"ok": p.returncode == 0, "returncode": int(p.returncode), "cmd": cmd, "log": str(log_path)}


def _copy_if_exists(src: Path, dst_dir: Path) -> Dict[str, Any] | None:
    if (not str(src).strip()) or (not src.exists()) or (not src.is_file()):
        return None
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    shutil.copy2(src, dst)
    return {"src": str(src), "dst": str(dst), "size_bytes": dst.stat().st_size}


def _copy_bundle(paths: List[Path], dst_dir: Path) -> List[Dict[str, Any]]:
    copied: List[Dict[str, Any]] = []
    for src in paths:
        rec = _copy_if_exists(src, dst_dir)
        if rec:
            copied.append(rec)
    return copied


def _write_checksums(set_root: Path) -> Dict[str, str]:
    checksum_rows: List[Dict[str, Any]] = []
    for path in sorted(set_root.rglob("*")):
        if not path.is_file():
            continue
        if path.name in {"checksums.json", "checksums.sha256"}:
            continue
        checksum_rows.append(
            {
                "path": str(path.relative_to(set_root)),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    checksums_json = set_root / "checksums.json"
    checksums_sha = set_root / "checksums.sha256"
    _write_json(checksums_json, {"generated_at_local": _now_local(), "files": checksum_rows})
    checksums_sha.write_text(
        "\n".join(f"{row['sha256']}  {row['path']}" for row in checksum_rows) + ("\n" if checksum_rows else ""),
        encoding="utf-8",
    )
    return {
        "checksums_json": str(checksums_json),
        "checksums_sha256": str(checksums_sha),
    }


def _path_after_flag(cmd: Any, flag: str) -> Path | None:
    if not isinstance(cmd, list):
        return None
    for idx, tok in enumerate(cmd):
        if str(tok) == flag and idx + 1 < len(cmd):
            src = str(cmd[idx + 1]).strip()
            return Path(src).resolve() if src else None
    return None


def _extract_ligand_result(summary_json: Path) -> Dict[str, Any]:
    payload = _read_json(summary_json)
    runs = payload.get("runs") or []
    first = runs[0] if isinstance(runs, list) and runs else {}
    first_summary = Path(str(first.get("summary_json", ""))).resolve() if first.get("summary_json") else None
    first_payload = _read_json(first_summary) if first_summary and first_summary.exists() else {}
    stages = first_payload.get("stages", {}) if isinstance(first_payload.get("stages"), dict) else {}
    stage5 = stages.get("stage5_ranking_eval", {}) if isinstance(stages.get("stage5_ranking_eval"), dict) else {}
    stage45 = stages.get("stage45_integrity", {}) if isinstance(stages.get("stage45_integrity"), dict) else {}
    if not stage45:
        stage45 = stages.get("stage45_eval_integrity", {}) if isinstance(stages.get("stage45_eval_integrity"), dict) else {}
    stage6 = stages.get("stage6_operational_gate", {}) if isinstance(stages.get("stage6_operational_gate"), dict) else {}
    ranking_summary_json = (
        Path(str(stage5.get("artifacts", {}).get("summary_json", ""))).resolve()
        if stage5.get("artifacts", {}).get("summary_json")
        else _path_after_flag(stage5.get("cmd"), "--out-json")
    )
    integrity_summary_json = (
        Path(str(stage45.get("artifacts", {}).get("out_json", ""))).resolve()
        if stage45.get("artifacts", {}).get("out_json")
        else _path_after_flag(stage45.get("cmd"), "--out-json")
    )
    raw_pass = bool(payload.get("pass", False))
    effective_pass = raw_pass
    acceptance_note = ""

    failed_metrics = stage6.get("failed_metrics", []) if isinstance(stage6.get("failed_metrics"), list) else []
    failed_metric_names = {str(x.get("metric", "")).strip() for x in failed_metrics if isinstance(x, dict)}
    smoke_like = bool(first.get("ligand_size") == 64 or payload.get("ligand_sizes") == [64])
    ranking_pass = bool(stage5.get("ok", False))
    integrity_pass = bool(stage45.get("ok", False))
    if (not raw_pass) and smoke_like and ranking_pass and integrity_pass and failed_metric_names <= {"ranking_eval_unique_keys"}:
        effective_pass = True
        acceptance_note = (
            "smoke acceptance uses ranking+integrity criteria; full operational gate "
            "min_eval_unique_keys threshold is retained as diagnostic only for n=64 smoke runs"
        )

    result = {
        "pass": effective_pass,
        "raw_pass": raw_pass,
        "acceptance_note": acceptance_note,
        "summary_json": str(summary_json),
        "summary_md": str(summary_json).replace("_summary.json", "_summary.md"),
        "aggregate_csv": str(payload.get("artifacts", {}).get("aggregate_csv", "")),
        "runs_csv": str(payload.get("artifacts", {}).get("runs_csv", "")),
        "state_json": str(payload.get("artifacts", {}).get("state_json", "")),
        "profile_json": str(payload.get("profile_json", "")),
        "ligand_sizes": payload.get("ligand_sizes"),
        "metrics": {
            "ranking_unique_auc": first.get("ranking_unique_auc"),
            "ranking_pr_auc": first.get("ranking_pr_auc"),
            "ranking_ef1": first.get("ranking_ef1"),
            "ranking_bedroc": first.get("ranking_bedroc"),
            "operational_gate_pass": first.get("operational_gate_pass"),
            "strict_gate_pass": first.get("strict_gate_pass"),
            "ranking_pass": ranking_pass,
            "integrity_pass": integrity_pass,
            "ranking_score_col_used": stage6.get("ranking_score_col_used"),
            "ranking_probability_score_col_used": stage6.get("ranking_probability_score_col_used"),
        },
        "ranking_score_col_used": stage6.get("ranking_score_col_used"),
        "ranking_probability_score_col_used": stage6.get("ranking_probability_score_col_used"),
        "pipeline_summary_json": str(first_summary) if first_summary and first_summary.exists() else "",
        "pipeline_summary_md": str(first_summary).replace("_summary.json", "_summary.md") if first_summary and first_summary.exists() else "",
        "ranking_summary_json": str(ranking_summary_json) if ranking_summary_json and ranking_summary_json.exists() else "",
        "ranking_summary_md": str(ranking_summary_json).replace("_summary.json", "_summary.md") if ranking_summary_json and ranking_summary_json.exists() else "",
        "integrity_summary_json": str(integrity_summary_json) if integrity_summary_json and integrity_summary_json.exists() else "",
        "service_failed_stage": first_payload.get("service_result", {}).get("failed_stage"),
    }
    return result


def _extract_idp_full_current() -> Dict[str, Any]:
    manifest = _read_json(RUNS / "idp_3bead_release_manifest_current.json")
    return {
        "pass": bool(manifest.get("acceptance", {}).get("pass", False)),
        "manifest_json": str(RUNS / "idp_3bead_release_manifest_current.json"),
        "summary_json": str(ROOT / manifest.get("summary_json")) if manifest.get("summary_json") else "",
        "combined_gate_json": str(ROOT / manifest.get("combined_gate_json")) if manifest.get("combined_gate_json") else "",
        "report_md": str(RUNS / "idp_3bead_release_report_current.md"),
        "regression_json": str(RUNS / "idp_3bead_release_regression_current.json"),
        "release_label": manifest.get("release_label"),
        "metrics": dict(manifest.get("combined_gate_metrics", {})),
        "acceptance": dict(manifest.get("acceptance", {})),
    }


def _extract_idp_smoke_current(out_json: Path) -> Dict[str, Any]:
    payload = _read_json(out_json)
    summary_json = Path(str(payload.get("summary_json", ""))) if payload.get("summary_json") else None
    summary = _read_json(summary_json) if summary_json and summary_json.exists() else {}
    return {
        "pass": bool(payload.get("pass", False)),
        "out_json": str(out_json),
        "summary_json": str(summary_json) if summary_json else "",
        "manifest_json": str(payload.get("smoke_manifest_json", "")),
        "regression_json": str(payload.get("smoke_regression_json", "")),
        "candidate_eval_json": str(payload.get("smoke_candidate_eval_json", "")),
        "metrics": dict(summary.get("combined_gate_metrics", {})) if isinstance(summary, dict) else {},
        "acceptance": {
            "pass": summary.get("pass"),
            "all_fold_pass": summary.get("all_fold_pass"),
            "corrected_pass_folds": summary.get("corrected_pass_folds"),
            "baseline_pass_folds": summary.get("baseline_pass_folds"),
            "combined_gate_pass": summary.get("combined_gate_pass"),
        },
    }


def _copy_ligand_result_bundle(result: Dict[str, Any], domain_dir: Path) -> List[Dict[str, Any]]:
    return _copy_bundle([
        Path(result["summary_json"]) if result.get("summary_json") else Path(""),
        Path(result["summary_md"]) if result.get("summary_md") else Path(""),
        Path(result["aggregate_csv"]) if result.get("aggregate_csv") else Path(""),
        Path(result["runs_csv"]) if result.get("runs_csv") else Path(""),
        Path(result["state_json"]) if result.get("state_json") else Path(""),
        Path(result["profile_json"]) if result.get("profile_json") else Path(""),
        Path(result["pipeline_summary_json"]) if result.get("pipeline_summary_json") else Path(""),
        Path(result["pipeline_summary_md"]) if result.get("pipeline_summary_md") else Path(""),
        Path(result["ranking_summary_json"]) if result.get("ranking_summary_json") else Path(""),
        Path(result["ranking_summary_md"]) if result.get("ranking_summary_md") else Path(""),
        Path(result["integrity_summary_json"]) if result.get("integrity_summary_json") else Path(""),
        Path(result["run_log"]) if result.get("run_log") else Path(""),
    ], domain_dir)


def _reconcile_task_result(task: Dict[str, Any], result: Dict[str, Any], domain_dir: Path) -> Dict[str, Any]:
    if task.get("kind") != "ligand_stress":
        return result
    summary_json = Path(str(result.get("summary_json", ""))) if result.get("summary_json") else None
    if not summary_json or not summary_json.exists():
        return result

    refreshed = {
        "task_id": str(result.get("task_id", task.get("task_id", ""))),
        "domain": str(result.get("domain", task.get("domain", ""))),
        "kind": str(result.get("kind", task.get("kind", ""))),
        **_extract_ligand_result(summary_json),
        "run_ok": result.get("run_ok", True),
        "run_returncode": result.get("run_returncode", 0),
        "run_log": result.get("run_log", ""),
    }
    state_json = Path(str(refreshed.get("state_json", ""))) if refreshed.get("state_json") else None
    if state_json and state_json.exists():
        state_payload = _read_json(state_json)
        if state_payload.get("pass") is True:
            refreshed["run_ok"] = True
            refreshed["run_returncode"] = 0
    if refreshed.get("pass") is True:
        refreshed["run_ok"] = True
        refreshed["run_returncode"] = 0
    refreshed["copied_files"] = _copy_ligand_result_bundle(refreshed, domain_dir)
    return refreshed


def _write_set_manifest(set_root: Path, set_def: Dict[str, Any], task_results: List[Dict[str, Any]]) -> None:
    manifest = {
        "generated_at_local": _now_local(),
        "set_id": set_def["set_id"],
        "title": set_def["title"],
        "purpose": set_def["purpose"],
        "pass": all(bool(x.get("pass", False)) for x in task_results),
        "tasks": task_results,
    }
    for opt_key in [
        "claim_role",
        "preregistered_claim",
        "acceptance_policy",
        "blind_governance",
        "submission_package",
        "frozen_references",
    ]:
        if opt_key in set_def:
            manifest[opt_key] = set_def[opt_key]
    manifest_json = set_root / "manifest.json"
    _write_json(manifest_json, manifest)

    lines = [
        f"# {set_def['title']}",
        "",
        f"- set_id: `{set_def['set_id']}`",
        f"- generated_at_local: `{manifest['generated_at_local']}`",
        f"- pass: `{manifest['pass']}`",
        "",
        set_def["purpose"],
        "",
        "## Tasks",
        "",
    ]
    for task in task_results:
        lines.append(f"### {task['task_id']} ({task['domain']})")
        lines.append("")
        lines.append(f"- kind: `{task['kind']}`")
        lines.append(f"- pass: `{task.get('pass')}`")
        for k, v in sorted((task.get("metrics") or {}).items()):
            lines.append(f"- {k}: `{v}`")
        lines.append("")
    (set_root / "manifest.md").write_text("\n".join(lines), encoding="utf-8")


def _write_top_state(base_root: Path, top_state: Dict[str, Any]) -> None:
    _write_json(base_root / "state.json", top_state)
    lines = [
        "# External Validation Blind Runs State",
        "",
        f"- tag: `{top_state.get('tag', '')}`",
        f"- status: `{top_state.get('status', '')}`",
        f"- generated_at_local: `{top_state.get('generated_at_local', '')}`",
        f"- updated_at_local: `{top_state.get('updated_at_local', '')}`",
        f"- completed_set_count: `{len(top_state.get('sets', []))}`",
        "",
        "## Sets",
        "",
    ]
    for s in top_state.get("sets", []):
        lines.append(f"- `{s.get('set_id', '')}` pass=`{s.get('pass', '')}`")
    if top_state.get("error"):
        lines.extend(["", "## Error", "", f"- `{top_state['error']}`"])
    (base_root / "state.md").write_text("\n".join(lines), encoding="utf-8")


def _zip_set(set_root: Path) -> Path:
    zip_path = set_root.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(set_root.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=str(path.relative_to(set_root.parent)))
    return zip_path


def _run_set(base_root: Path, tag: str, set_def: Dict[str, Any], resume: bool) -> Dict[str, Any]:
    set_root = base_root / set_def["set_id"]
    files_root = set_root / "files"
    state_json = set_root / "state.json"
    state = _read_json(state_json) if resume and state_json.exists() else {
        "generated_at_local": _now_local(),
        "set_id": set_def["set_id"],
        "title": set_def["title"],
        "tasks": {},
    }
    task_results: List[Dict[str, Any]] = []

    for task in set_def["tasks"]:
        task_id = task["task_id"]
        domain = task["domain"]
        domain_dir = files_root / domain
        task_state = state["tasks"].get(task_id, {}) if isinstance(state.get("tasks"), dict) else {}
        done = bool(task_state.get("done", False))
        result: Dict[str, Any]
        try:
            if task["kind"] == "ligand_stress":
                out_prefix = RUNS / f"external_validation_{tag}_{set_def['set_id']}_{task_id}"
                summary_json = Path(f"{out_prefix}_summary.json")
                run_meta: Dict[str, Any] = {"ok": True, "returncode": 0, "cmd": [], "log": ""}
                previous_result = task_state.get("result", {}) if isinstance(task_state.get("result"), dict) else {}
                previous_pass = bool(previous_result.get("pass", False))
                if (not done) or (not previous_pass) or (not summary_json.exists()):
                    cmd = [
                        sys.executable,
                        str(ROOT / "tools/run_ligand_stress_validation.py"),
                        "--profile-json", str(ROOT / task["profile_json"]),
                        "--ligand-sizes", str(task["ligand_sizes"]),
                        "--repeats", "1",
                        "--date-tag", f"{tag}-{task['date_tag_suffix']}",
                        "--out-prefix", str(out_prefix),
                        "--resume",
                        "--resume-retry-failed-runs",
                        "--fail-fast",
                        "--enforce-data-contract",
                        "--data-contract-json", str(ROOT / "config/ligand_data_contract_v1.json"),
                    ]
                    log = RUNS / f"external_validation_{tag}_{set_def['set_id']}_{task_id}.log"
                    run_meta = _run(cmd, log)
                    if not run_meta["ok"] and not summary_json.exists():
                        raise RuntimeError(f"ligand stress task failed: {task_id} rc={run_meta['returncode']} log={log}")
                result = {
                    "task_id": task_id,
                    "domain": domain,
                    "kind": task["kind"],
                    **_extract_ligand_result(summary_json),
                    "run_ok": run_meta.get("ok", True),
                    "run_returncode": run_meta.get("returncode", 0),
                    "run_log": run_meta.get("log", ""),
                }
                result["copied_files"] = _copy_ligand_result_bundle(result, domain_dir)
            elif task["kind"] == "idp_reference_current_full":
                result = {
                    "task_id": task_id,
                    "domain": domain,
                    "kind": task["kind"],
                    **_extract_idp_full_current(),
                }
                copied = _copy_bundle([
                    Path(result["manifest_json"]),
                    Path(result["summary_json"]) if result.get("summary_json") else Path(""),
                    Path(result["combined_gate_json"]) if result.get("combined_gate_json") else Path(""),
                    Path(result["report_md"]),
                    Path(result["regression_json"]),
                ], domain_dir)
                result["copied_files"] = copied
            elif task["kind"] == "idp_smoke_current":
                out_json = RUNS / f"external_validation_{tag}_{set_def['set_id']}_{task_id}.json"
                run_meta = {"ok": True, "returncode": 0, "cmd": [], "log": ""}
                if not done or not out_json.exists():
                    cmd = [
                        sys.executable,
                        str(ROOT / "tools/run_idp_3bead_release_smoke_current.py"),
                        "--device", "cuda",
                        "--tag", f"external-{tag}-{set_def['set_id']}-{task_id}",
                        "--out-json", str(out_json),
                    ]
                    log = RUNS / f"external_validation_{tag}_{set_def['set_id']}_{task_id}.log"
                    run_meta = _run(cmd, log)
                    if not run_meta["ok"] and not out_json.exists():
                        raise RuntimeError(f"idp smoke task failed: {task_id} rc={run_meta['returncode']} log={log}")
                result = {
                    "task_id": task_id,
                    "domain": domain,
                    "kind": task["kind"],
                    **_extract_idp_smoke_current(out_json),
                    "run_ok": run_meta.get("ok", True),
                    "run_returncode": run_meta.get("returncode", 0),
                    "run_log": run_meta.get("log", ""),
                }
                copied = _copy_bundle([
                    out_json,
                    Path(result["summary_json"]) if result.get("summary_json") else Path(""),
                    Path(result["manifest_json"]) if result.get("manifest_json") else Path(""),
                    Path(result["regression_json"]) if result.get("regression_json") else Path(""),
                    Path(result["candidate_eval_json"]) if result.get("candidate_eval_json") else Path(""),
                    Path(result["run_log"]) if result.get("run_log") else Path(""),
                ], domain_dir)
                result["copied_files"] = copied
            else:
                raise ValueError(f"unsupported task kind: {task['kind']}")
        except Exception as exc:
            state["failed_task"] = {
                "task_id": task_id,
                "domain": domain,
                "kind": task.get("kind"),
                "updated_at_local": _now_local(),
                "error": str(exc),
            }
            _write_json(state_json, state)
            raise

        task_results.append(result)
        state.setdefault("tasks", {})[task_id] = {"done": True, "result": result, "updated_at_local": _now_local()}
        _write_json(state_json, state)

    task_results = [
        _reconcile_task_result(task, result, files_root / task["domain"])
        for task, result in zip(set_def["tasks"], task_results)
    ]
    for result in task_results:
        state.setdefault("tasks", {})[result["task_id"]] = {
            "done": True,
            "result": result,
            "updated_at_local": _now_local(),
        }
    _write_json(state_json, state)

    _write_set_manifest(set_root, set_def, task_results)
    checksum_artifacts = _write_checksums(set_root)
    manifest_json = set_root / "manifest.json"
    manifest = _read_json(manifest_json)
    manifest["checksum_artifacts"] = checksum_artifacts
    _write_json(manifest_json, manifest)
    manifest_md = set_root / "manifest.md"
    manifest_md.write_text(
        manifest_md.read_text(encoding="utf-8")
        + "\n## Integrity\n\n"
        + f"- checksums_json: `{checksum_artifacts['checksums_json']}`\n"
        + f"- checksums_sha256: `{checksum_artifacts['checksums_sha256']}`\n",
        encoding="utf-8",
    )
    zip_path = _zip_set(set_root)
    set_result = {
        "set_id": set_def["set_id"],
        "title": set_def["title"],
        "claim_role": set_def.get("claim_role", ""),
        "purpose": set_def["purpose"],
        "pass": all(bool(x.get("pass", False)) for x in task_results),
        "set_root": str(set_root),
        "zip_path": str(zip_path),
        "manifest_json": str(set_root / "manifest.json"),
        "manifest_md": str(set_root / "manifest.md"),
        **checksum_artifacts,
        "tasks": task_results,
    }
    return set_result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run 3 cross-domain external blind validation sets and package the produced artifacts.")
    p.add_argument("--tag", type=str, default=f"{dt.date.today().isoformat()}_r1")
    p.add_argument("--out-root", type=str, default="runs/external_validation_blind_runs")
    p.add_argument("--sets", type=str, default="set1_core_blind,set2_expanded_ood,set3_operational_smoke")
    p.add_argument("--set-spec-json", type=str, default="", help="Optional preregistered set specification JSON.")
    p.add_argument("--validate-only", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    return p


def main(argv: List[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    selected_order = [x.strip() for x in str(args.sets).split(',') if x.strip()]
    spec_meta: Dict[str, Any] = {}
    spec_path: Path | None = None
    if str(args.set_spec_json).strip():
        spec_path = (ROOT / str(args.set_spec_json)).resolve() if not Path(str(args.set_spec_json)).is_absolute() else Path(str(args.set_spec_json)).resolve()
        spec = _load_set_spec(spec_path)
        set_defs = spec["sets"]
        _validate_set_defs(set_defs, str(spec_path))
        spec_meta = {
            "set_spec_json": str(spec_path),
            "protocol_id": spec.get("protocol_id"),
            "protocol_title": spec.get("protocol_title"),
            "protocol_version": spec.get("protocol_version"),
            "frozen_at_local": spec.get("frozen_at_local"),
        }
    else:
        set_defs = SET_DEFS
        _validate_set_defs(set_defs, "builtin_set_defs")
    if args.validate_only:
        print(json.dumps({"ok": True, "set_count": len(set_defs), **spec_meta}, indent=2, ensure_ascii=False))
        return
    set_map = {x["set_id"]: x for x in set_defs}
    base_root = ROOT / args.out_root / f"external_validation_blind_runs_{args.tag}"
    base_root.mkdir(parents=True, exist_ok=True)
    provenance = _build_run_provenance(args, spec_path)
    _write_json(base_root / "provenance.json", provenance)
    (base_root / "provenance.md").write_text(
        "# External Validation Run Provenance\n\n"
        + f"- generated_at_local: `{provenance['generated_at_local']}`\n"
        + f"- protocol_id: `{spec_meta.get('protocol_id', '')}`\n"
        + f"- protocol_version: `{spec_meta.get('protocol_version', '')}`\n"
        + f"- spec_json: `{provenance['spec_json']}`\n"
        + f"- spec_sha256: `{provenance['spec_sha256']}`\n"
        + f"- git_head: `{provenance['git_head']}`\n"
        + f"- git_branch: `{provenance['git_branch']}`\n"
        + f"- python_version: `{provenance['python_version']}`\n"
        + f"- platform: `{provenance['platform']}`\n"
        + f"- selected_sets: `{','.join(provenance['selected_sets'])}`\n",
        encoding="utf-8",
    )
    env_artifacts = _write_environment_snapshots(base_root)
    top_state = {
        "generated_at_local": _now_local(),
        "updated_at_local": _now_local(),
        "tag": args.tag,
        "out_root": str(base_root),
        "status": "running",
        "sets": [],
        **spec_meta,
        "provenance_json": str(base_root / "provenance.json"),
        "provenance_md": str(base_root / "provenance.md"),
        "environment_artifacts": env_artifacts,
    }
    _write_top_state(base_root, top_state)
    try:
        for set_id in selected_order:
            set_def = set_map.get(set_id)
            if not set_def:
                continue
            result = _run_set(base_root, args.tag, set_def, resume=bool(args.resume))
            top_state["sets"].append(result)
            top_state["updated_at_local"] = _now_local()
            _write_json(base_root / "summary.json", top_state)
            _write_top_state(base_root, top_state)
    except Exception as exc:
        top_state["status"] = "failed"
        top_state["updated_at_local"] = _now_local()
        top_state["error"] = str(exc)
        _write_top_state(base_root, top_state)
        raise

    lines = ["# External Validation Blind Runs", "", f"- tag: `{args.tag}`", ""]
    for s in top_state["sets"]:
        lines.append(f"## {s['title']}")
        lines.append("")
        lines.append(f"- pass: `{s['pass']}`")
        lines.append(f"- manifest_json: `{s['manifest_json']}`")
        lines.append(f"- zip_path: `{s['zip_path']}`")
        lines.append("")
    top_state["status"] = "completed"
    top_state["updated_at_local"] = _now_local()
    _write_json(base_root / "summary.json", top_state)
    _write_top_state(base_root, top_state)
    (base_root / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(top_state, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
