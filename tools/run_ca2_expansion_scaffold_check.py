#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TEMPLATE_JSON = "config/external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template.json"
EXPECTED_PRIMARY_TARGET = "CARBONIC_ANHYDRASE_2_ZN_BLIND"
EXPECTED_FIT_DONOR_TARGET = "EGFR_KINASE"
EXPECTED_TEMPLATE_STATUS = "template_not_runnable"
EXPECTED_REQUIRED_ARTIFACT_KEYS = {
    "target_csv",
    "target_metadata_csv",
    "core_reference_csv",
    "core_eval_split_csv",
    "core_ligand_meta_csv",
    "ood_reference_csv",
    "ood_eval_split_csv",
    "ood_ligand_meta_csv",
    "core_profile_json",
    "ood_profile_json",
    "smoke_profile_json",
}
EXPECTED_TASKS = {
    "set1_core_blind": {
        "task_id": "non_kinase_enzyme_ca2_core_full",
        "profile_key": "core_profile_json",
        "ligand_sizes": "10000",
        "date_tag_suffix": "ca2-core-full",
    },
    "set2_expanded_ood": {
        "task_id": "non_kinase_enzyme_ca2_chembl50_full",
        "profile_key": "ood_profile_json",
        "ligand_sizes": "10000",
        "date_tag_suffix": "ca2-chembl50-full",
    },
    "set3_operational_smoke": {
        "task_id": "non_kinase_enzyme_ca2_smoke",
        "profile_key": "smoke_profile_json",
        "ligand_sizes": "64",
        "date_tag_suffix": "ca2-smoke",
    },
}


def _resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else (ROOT / path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _norm_csv_tokens(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _add_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    ok: bool,
    detail: str,
    path: str | None = None,
) -> None:
    row: dict[str, Any] = {
        "check_id": check_id,
        "ok": bool(ok),
        "detail": detail,
    }
    if path:
        row["path"] = path
    checks.append(row)


def _validate_profile(
    *,
    checks: list[dict[str, Any]],
    profile_key: str,
    profile_relpath: str,
    target_csv_relpath: str,
    target_metadata_csv_relpath: str,
    reference_csv_relpath: str,
    eval_split_csv_relpath: str,
    ligand_meta_csv_relpath: str,
) -> None:
    profile_path = _resolve_repo_path(profile_relpath)
    if not profile_path.exists():
        _add_check(
            checks,
            check_id=f"profile_exists:{profile_key}",
            ok=False,
            detail="profile JSON missing",
            path=profile_relpath,
        )
        return
    payload = _read_json(profile_path)
    _add_check(
        checks,
        check_id=f"profile_target:{profile_key}",
        ok=str(payload.get("targets", "")).strip() == EXPECTED_PRIMARY_TARGET,
        detail=f"targets={payload.get('targets', '')}",
        path=profile_relpath,
    )
    for field, expected in (
        ("dry_run", True),
        ("template_profile", True),
        ("template_execution_intent", "validate_only"),
        ("claim_ready", False),
    ):
        _add_check(
            checks,
            check_id=f"profile_flag:{profile_key}:{field}",
            ok=payload.get(field) == expected,
            detail=f"{field}={payload.get(field)!r}",
            path=profile_relpath,
        )
    for field, expected in (
        ("target_native_csv", target_csv_relpath),
        ("ligand_csv", reference_csv_relpath),
        ("calibration_reference_csv", reference_csv_relpath),
        ("ranking_labels_csv", reference_csv_relpath),
        ("eval_split_csv", eval_split_csv_relpath),
        ("leakage_target_meta_csv", target_metadata_csv_relpath),
        ("leakage_ligand_meta_csv", ligand_meta_csv_relpath),
        ("hard_decoy_reference_csv", reference_csv_relpath),
        ("hard_decoy_ligand_meta_csv", ligand_meta_csv_relpath),
        ("hard_decoy_target_meta_csv", target_metadata_csv_relpath),
    ):
        value = str(payload.get(field, "")).strip()
        _add_check(
            checks,
            check_id=f"profile_link:{profile_key}:{field}",
            ok=value == expected,
            detail=f"{field}={value}",
            path=profile_relpath,
        )
    hard_decoy_targets = set(_norm_csv_tokens(payload.get("hard_decoy_targets")))
    _add_check(
        checks,
        check_id=f"profile_link:{profile_key}:hard_decoy_targets",
        ok={EXPECTED_PRIMARY_TARGET, EXPECTED_FIT_DONOR_TARGET}.issubset(hard_decoy_targets),
        detail=f"hard_decoy_targets={sorted(hard_decoy_targets)}",
        path=profile_relpath,
    )
    _add_check(
        checks,
        check_id=f"profile_link:{profile_key}:hard_decoy_fit_targets",
        ok=str(payload.get("hard_decoy_fit_targets", "")).strip() == EXPECTED_FIT_DONOR_TARGET,
        detail=f"hard_decoy_fit_targets={payload.get('hard_decoy_fit_targets', '')}",
        path=profile_relpath,
    )


def _validate_target_packet(
    *,
    checks: list[dict[str, Any]],
    target_csv_relpath: str,
    target_metadata_csv_relpath: str,
    expected_native_pdb_relpath: str,
) -> None:
    target_csv_path = _resolve_repo_path(target_csv_relpath)
    target_meta_path = _resolve_repo_path(target_metadata_csv_relpath)
    if target_csv_path.exists():
        rows = _read_csv_rows(target_csv_path)
        by_target = {str(row.get("target", "")).strip(): row for row in rows}
        _add_check(
            checks,
            check_id="target_packet:targets_present",
            ok={EXPECTED_PRIMARY_TARGET, EXPECTED_FIT_DONOR_TARGET}.issubset(set(by_target)),
            detail=f"targets={sorted(by_target)}",
            path=target_csv_relpath,
        )
        ca2_row = by_target.get(EXPECTED_PRIMARY_TARGET, {})
        native_value = str(ca2_row.get("native_pdb_path", "")).strip()
        _add_check(
            checks,
            check_id="target_packet:ca2_native_path",
            ok=native_value == expected_native_pdb_relpath,
            detail=f"native_pdb_path={native_value}",
            path=target_csv_relpath,
        )
        _add_check(
            checks,
            check_id="target_packet:ca2_pdb_id",
            ok=str(ca2_row.get("pdb_id", "")).strip() == "1CA2",
            detail=f"pdb_id={ca2_row.get('pdb_id', '')}",
            path=target_csv_relpath,
        )
    if target_meta_path.exists():
        rows = _read_csv_rows(target_meta_path)
        by_target = {str(row.get("target", "")).strip(): row for row in rows}
        ca2_row = by_target.get(EXPECTED_PRIMARY_TARGET, {})
        _add_check(
            checks,
            check_id="target_metadata:targets_present",
            ok={EXPECTED_PRIMARY_TARGET, EXPECTED_FIT_DONOR_TARGET}.issubset(set(by_target)),
            detail=f"targets={sorted(by_target)}",
            path=target_metadata_csv_relpath,
        )
        _add_check(
            checks,
            check_id="target_metadata:ca2_family",
            ok=str(ca2_row.get("target_family", "")).strip() == "METALLOENZYME",
            detail=f"target_family={ca2_row.get('target_family', '')}",
            path=target_metadata_csv_relpath,
        )
    native_path = _resolve_repo_path(expected_native_pdb_relpath)
    _add_check(
        checks,
        check_id="target_packet:native_structure_exists",
        ok=native_path.exists(),
        detail="native structure file exists" if native_path.exists() else "native structure file missing",
        path=expected_native_pdb_relpath,
    )


def _validate_reference_bundle(
    *,
    checks: list[dict[str, Any]],
    bundle_name: str,
    reference_csv_relpath: str,
    eval_split_csv_relpath: str,
    ligand_meta_csv_relpath: str,
) -> None:
    reference_path = _resolve_repo_path(reference_csv_relpath)
    split_path = _resolve_repo_path(eval_split_csv_relpath)
    meta_path = _resolve_repo_path(ligand_meta_csv_relpath)
    if not (reference_path.exists() and split_path.exists() and meta_path.exists()):
        return
    ref_rows = _read_csv_rows(reference_path)
    split_rows = _read_csv_rows(split_path)
    meta_rows = _read_csv_rows(meta_path)
    ref_targets = {str(row.get("target", "")).strip() for row in ref_rows}
    split_targets = {str(row.get("target", "")).strip() for row in split_rows}
    meta_ligands = {str(row.get("ligand_id", "")).strip() for row in meta_rows}
    ref_ligands = {str(row.get("ligand_id", "")).strip() for row in ref_rows}
    split_ligands = {str(row.get("ligand_id", "")).strip() for row in split_rows}
    ca2_ref_rows = [row for row in ref_rows if str(row.get("target", "")).strip() == EXPECTED_PRIMARY_TARGET]
    ca2_split_rows = [row for row in split_rows if str(row.get("target", "")).strip() == EXPECTED_PRIMARY_TARGET]
    _add_check(
        checks,
        check_id=f"bundle:{bundle_name}:targets_present",
        ok=EXPECTED_PRIMARY_TARGET in ref_targets and EXPECTED_PRIMARY_TARGET in split_targets,
        detail=f"reference_targets={sorted(ref_targets)} split_targets={sorted(split_targets)}",
        path=reference_csv_relpath,
    )
    _add_check(
        checks,
        check_id=f"bundle:{bundle_name}:ca2_rows_present",
        ok=bool(ca2_ref_rows) and bool(ca2_split_rows),
        detail=f"ca2_reference_rows={len(ca2_ref_rows)} ca2_split_rows={len(ca2_split_rows)}",
        path=reference_csv_relpath,
    )
    _add_check(
        checks,
        check_id=f"bundle:{bundle_name}:ligand_meta_covers_reference",
        ok=ref_ligands.issubset(meta_ligands),
        detail=f"missing_meta={sorted(ref_ligands - meta_ligands)}",
        path=ligand_meta_csv_relpath,
    )
    _add_check(
        checks,
        check_id=f"bundle:{bundle_name}:eval_split_matches_reference",
        ok=split_ligands == ref_ligands,
        detail=f"missing_in_split={sorted(ref_ligands - split_ligands)} extra_in_split={sorted(split_ligands - ref_ligands)}",
        path=eval_split_csv_relpath,
    )


def validate_ca2_scaffold(template_json: str = DEFAULT_TEMPLATE_JSON) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    template_path = _resolve_repo_path(template_json)
    _add_check(
        checks,
        check_id="template_exists",
        ok=template_path.exists(),
        detail="template JSON exists" if template_path.exists() else "template JSON missing",
        path=str(template_json),
    )
    if not template_path.exists():
        return {
            "mode": "validate_only",
            "template_json": str(template_json),
            "pass": False,
            "checks": checks,
            "summary": {
                "total_checks": len(checks),
                "passed_checks": 0,
                "failed_checks": len(checks),
            },
        }

    template = _read_json(template_path)
    required_artifacts = template.get("required_artifacts") or {}
    _add_check(
        checks,
        check_id="template_status",
        ok=str(template.get("status", "")).strip() == EXPECTED_TEMPLATE_STATUS,
        detail=f"status={template.get('status', '')}",
        path=str(template_json),
    )
    _add_check(
        checks,
        check_id="template_primary_target",
        ok=str(((template.get("primary_candidate") or {}).get("target", ""))).strip() == EXPECTED_PRIMARY_TARGET,
        detail=f"primary_target={(template.get('primary_candidate') or {}).get('target', '')}",
        path=str(template_json),
    )
    _add_check(
        checks,
        check_id="template_required_artifact_keys",
        ok=set(required_artifacts) == EXPECTED_REQUIRED_ARTIFACT_KEYS,
        detail=f"required_artifact_keys={sorted(required_artifacts)}",
        path=str(template_json),
    )

    for key in sorted(EXPECTED_REQUIRED_ARTIFACT_KEYS):
        relpath = str(required_artifacts.get(key, "")).strip()
        exists = bool(relpath) and _resolve_repo_path(relpath).exists()
        _add_check(
            checks,
            check_id=f"artifact_exists:{key}",
            ok=exists,
            detail=f"{key}={relpath}",
            path=relpath or str(template_json),
        )

    primary_candidate = template.get("primary_candidate") or {}
    expected_native_pdb_relpath = str(primary_candidate.get("native_pdb_path", "")).strip()
    _validate_target_packet(
        checks=checks,
        target_csv_relpath=str(required_artifacts.get("target_csv", "")).strip(),
        target_metadata_csv_relpath=str(required_artifacts.get("target_metadata_csv", "")).strip(),
        expected_native_pdb_relpath=expected_native_pdb_relpath,
    )
    _validate_reference_bundle(
        checks=checks,
        bundle_name="core",
        reference_csv_relpath=str(required_artifacts.get("core_reference_csv", "")).strip(),
        eval_split_csv_relpath=str(required_artifacts.get("core_eval_split_csv", "")).strip(),
        ligand_meta_csv_relpath=str(required_artifacts.get("core_ligand_meta_csv", "")).strip(),
    )
    _validate_reference_bundle(
        checks=checks,
        bundle_name="ood",
        reference_csv_relpath=str(required_artifacts.get("ood_reference_csv", "")).strip(),
        eval_split_csv_relpath=str(required_artifacts.get("ood_eval_split_csv", "")).strip(),
        ligand_meta_csv_relpath=str(required_artifacts.get("ood_ligand_meta_csv", "")).strip(),
    )

    _validate_profile(
        checks=checks,
        profile_key="core_profile_json",
        profile_relpath=str(required_artifacts.get("core_profile_json", "")).strip(),
        target_csv_relpath=str(required_artifacts.get("target_csv", "")).strip(),
        target_metadata_csv_relpath=str(required_artifacts.get("target_metadata_csv", "")).strip(),
        reference_csv_relpath=str(required_artifacts.get("core_reference_csv", "")).strip(),
        eval_split_csv_relpath=str(required_artifacts.get("core_eval_split_csv", "")).strip(),
        ligand_meta_csv_relpath=str(required_artifacts.get("core_ligand_meta_csv", "")).strip(),
    )
    _validate_profile(
        checks=checks,
        profile_key="ood_profile_json",
        profile_relpath=str(required_artifacts.get("ood_profile_json", "")).strip(),
        target_csv_relpath=str(required_artifacts.get("target_csv", "")).strip(),
        target_metadata_csv_relpath=str(required_artifacts.get("target_metadata_csv", "")).strip(),
        reference_csv_relpath=str(required_artifacts.get("ood_reference_csv", "")).strip(),
        eval_split_csv_relpath=str(required_artifacts.get("ood_eval_split_csv", "")).strip(),
        ligand_meta_csv_relpath=str(required_artifacts.get("ood_ligand_meta_csv", "")).strip(),
    )

    smoke_profile = str(required_artifacts.get("smoke_profile_json", "")).strip()
    core_profile = str(required_artifacts.get("core_profile_json", "")).strip()
    _add_check(
        checks,
        check_id="template_smoke_profile_link",
        ok=smoke_profile == core_profile,
        detail=f"smoke_profile_json={smoke_profile}",
        path=str(template_json),
    )

    sets = template.get("sets") or []
    set_map = {str(row.get("set_id", "")).strip(): row for row in sets}
    _add_check(
        checks,
        check_id="template_set_ids",
        ok=set(set_map) == set(EXPECTED_TASKS),
        detail=f"set_ids={sorted(set_map)}",
        path=str(template_json),
    )
    for set_id, expected_task in EXPECTED_TASKS.items():
        set_row = set_map.get(set_id) or {}
        tasks = set_row.get("tasks") or []
        task = tasks[0] if tasks else {}
        expected_profile = str(required_artifacts.get(expected_task["profile_key"], "")).strip()
        _add_check(
            checks,
            check_id=f"task_link:{set_id}:single_task",
            ok=len(tasks) == 1,
            detail=f"task_count={len(tasks)}",
            path=str(template_json),
        )
        _add_check(
            checks,
            check_id=f"task_link:{set_id}:task_id",
            ok=str(task.get("task_id", "")).strip() == expected_task["task_id"],
            detail=f"task_id={task.get('task_id', '')}",
            path=str(template_json),
        )
        _add_check(
            checks,
            check_id=f"task_link:{set_id}:domain_kind",
            ok=str(task.get("domain", "")).strip() == "non_kinase_enzyme"
            and str(task.get("kind", "")).strip() == "ligand_stress",
            detail=f"domain={task.get('domain', '')} kind={task.get('kind', '')}",
            path=str(template_json),
        )
        _add_check(
            checks,
            check_id=f"task_link:{set_id}:profile_json",
            ok=str(task.get("profile_json", "")).strip() == expected_profile,
            detail=f"profile_json={task.get('profile_json', '')}",
            path=str(template_json),
        )
        _add_check(
            checks,
            check_id=f"task_link:{set_id}:ligand_sizes",
            ok=str(task.get("ligand_sizes", "")).strip() == expected_task["ligand_sizes"],
            detail=f"ligand_sizes={task.get('ligand_sizes', '')}",
            path=str(template_json),
        )
        _add_check(
            checks,
            check_id=f"task_link:{set_id}:date_tag_suffix",
            ok=str(task.get("date_tag_suffix", "")).strip() == expected_task["date_tag_suffix"],
            detail=f"date_tag_suffix={task.get('date_tag_suffix', '')}",
            path=str(template_json),
        )

    passed_checks = sum(1 for row in checks if row["ok"])
    failed_checks = len(checks) - passed_checks
    return {
        "mode": "validate_only",
        "template_json": str(template_json),
        "pass": failed_checks == 0,
        "checks": checks,
        "summary": {
            "total_checks": len(checks),
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
        },
    }


def _render_text(payload: dict[str, Any], *, verbose: bool = False) -> str:
    summary = payload.get("summary") or {}
    lines = [
        f"CA2 scaffold check: {'PASS' if payload.get('pass') else 'FAIL'}",
        f"mode: {payload.get('mode', 'validate_only')}",
        f"template_json: {payload.get('template_json', '')}",
        (
            f"checks: {summary.get('passed_checks', 0)}/{summary.get('total_checks', 0)} passed"
            f"  failed={summary.get('failed_checks', 0)}"
        ),
    ]
    checks = payload.get("checks") or []
    rows = checks if verbose else [row for row in checks if not row.get("ok")]
    if rows:
        lines.append("")
        for row in rows:
            status = "PASS" if row.get("ok") else "FAIL"
            detail = str(row.get("detail", "")).strip()
            path = str(row.get("path", "")).strip()
            suffix = f"  path={path}" if path else ""
            lines.append(f"- {status}  {row.get('check_id', 'unknown')}  {detail}{suffix}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Validate-only internal consistency check for the CA2 scaffold/template package. No blind run is launched."
    )
    ap.add_argument("--template-json", default=DEFAULT_TEMPLATE_JSON)
    ap.add_argument("--json", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--verbose", action=argparse.BooleanOptionalAction, default=False)
    args = ap.parse_args(argv)

    payload = validate_ca2_scaffold(template_json=str(args.template_json))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_text(payload, verbose=bool(args.verbose)))
    return 0 if payload.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
