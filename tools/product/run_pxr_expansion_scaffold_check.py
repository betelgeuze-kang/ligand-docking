#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.product import build_pxr_curated_packet_freeze as curated_freeze

EXPECTED_TARGET = "PXR_NR1I2_BLIND"
TEMPLATE_JSON = "config/external_validation_biorxiv_nuclear_receptor_pxr_v1_template.json"
CORE_PROFILE_JSON = "config/ligand_htvs_blind_pxr_nr1i2_v1.json"
OOD_PROFILE_JSON = "config/ligand_htvs_blind_pxr_nr1i2_chembl50_v1.json"

CURRENT_REQUIRED_ARTIFACTS = {
    "target_csv": "config/real_drug_targets_blind_pxr_nr1i2_v1.csv",
    "target_metadata_csv": "config/ligand_target_metadata_blind_pxr_nr1i2_v1.csv",
    "core_reference_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_v1.csv",
    "core_eval_split_csv": "config/ligand_eval_splits_blind_pxr_nr1i2_v1.csv",
    "core_ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_v1.csv",
    "core_profile_json": CORE_PROFILE_JSON,
    "ood_profile_json": OOD_PROFILE_JSON,
    "smoke_profile_json": CORE_PROFILE_JSON,
}

DEFERRED_REQUIRED_ARTIFACTS = {
    "ood_reference_csv": "config/ligand_binding_reference_blind_pxr_nr1i2_chembl50_v1.csv",
    "ood_eval_split_csv": "config/ligand_eval_splits_blind_pxr_nr1i2_chembl50_v1.csv",
    "ood_ligand_meta_csv": "config/ligand_meta_blind_pxr_nr1i2_chembl50_v1.csv",
}

EXPECTED_TEMPLATE_REQUIRED_ARTIFACTS = {
    **CURRENT_REQUIRED_ARTIFACTS,
    **DEFERRED_REQUIRED_ARTIFACTS,
}

EXPECTED_TEMPLATE_TASKS = [
    {
        "set_id": "set1_core_blind",
        "task_id": "nuclear_receptor_pxr_core_full",
        "profile_json": CORE_PROFILE_JSON,
        "ligand_sizes": "10000",
    },
    {
        "set_id": "set2_expanded_ood",
        "task_id": "nuclear_receptor_pxr_chembl50_full",
        "profile_json": OOD_PROFILE_JSON,
        "ligand_sizes": "10000",
    },
    {
        "set_id": "set3_operational_smoke",
        "task_id": "nuclear_receptor_pxr_smoke",
        "profile_json": CORE_PROFILE_JSON,
        "ligand_sizes": "64",
    },
]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_path(repo_root: Path, path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def _load_optional_curated_freeze_payload(
    repo_root: Path,
    workbook_csv: str,
    pending_disposition_json: str,
) -> dict[str, Any]:
    workbook_path = _repo_path(repo_root, workbook_csv)
    if not workbook_path.exists():
        return {}
    workbook_rows = curated_freeze._read_csv(str(workbook_path))  # pyright: ignore[reportPrivateUsage]
    pending_payload: dict[str, Any] = {}
    pending_path = _repo_path(repo_root, pending_disposition_json)
    if pending_path.exists():
        pending_payload = _read_json(pending_path)
    return curated_freeze.build_payload(workbook_rows, pending_payload)


def _safe_rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _add_artifact_row(rows: list[dict[str, Any]], repo_root: Path, key: str, rel_path: str, stage: str, required_now: bool) -> bool:
    path = repo_root / rel_path
    exists = path.exists()
    rows.append(
        {
            "key": key,
            "path": rel_path,
            "stage": stage,
            "required_now": required_now,
            "exists": exists,
        }
    )
    return exists


def _check_profile_contract(
    *,
    name: str,
    rel_path: str,
    repo_root: Path,
    expected_ligand_csv: str,
    expected_eval_split_csv: str,
    expected_ligand_meta_csv: str,
    errors: list[str],
) -> dict[str, Any]:
    path = repo_root / rel_path
    summary: dict[str, Any] = {
        "profile": name,
        "path": rel_path,
        "exists": path.exists(),
        "target": "",
        "dry_run": False,
        "template_profile": False,
        "template_execution_intent": "",
        "claim_ready": None,
    }
    if not path.exists():
        errors.append(f"missing profile JSON: {rel_path}")
        return summary

    payload = _read_json(path)
    summary.update(
        {
            "target": str(payload.get("targets", "")),
            "dry_run": bool(payload.get("dry_run", False)),
            "template_profile": bool(payload.get("template_profile", False)),
            "template_execution_intent": str(payload.get("template_execution_intent", "")),
            "claim_ready": bool(payload.get("claim_ready", False)),
        }
    )

    if payload.get("version") != Path(rel_path).stem:
        errors.append(f"{rel_path}: version must match filename stem")
    if payload.get("targets") != EXPECTED_TARGET:
        errors.append(f"{rel_path}: targets must be {EXPECTED_TARGET}")
    if payload.get("run_scope") != "full":
        errors.append(f"{rel_path}: run_scope must be full")
    if payload.get("dry_run") is not True:
        errors.append(f"{rel_path}: dry_run must be true")
    if payload.get("template_profile") is not True:
        errors.append(f"{rel_path}: template_profile must be true")
    if payload.get("template_execution_intent") != "validate_only":
        errors.append(f"{rel_path}: template_execution_intent must be validate_only")
    if payload.get("claim_ready") is not False:
        errors.append(f"{rel_path}: claim_ready must be false")
    if payload.get("target_native_csv") != CURRENT_REQUIRED_ARTIFACTS["target_csv"]:
        errors.append(f"{rel_path}: target_native_csv must be {CURRENT_REQUIRED_ARTIFACTS['target_csv']}")
    if payload.get("native_path_col") != "native_pdb_path":
        errors.append(f"{rel_path}: native_path_col must be native_pdb_path")
    if payload.get("ligand_csv") != expected_ligand_csv:
        errors.append(f"{rel_path}: ligand_csv must be {expected_ligand_csv}")
    if payload.get("calibration_reference_csv") != expected_ligand_csv:
        errors.append(f"{rel_path}: calibration_reference_csv must match ligand_csv")
    if payload.get("ranking_labels_csv") != expected_ligand_csv:
        errors.append(f"{rel_path}: ranking_labels_csv must match ligand_csv")
    if payload.get("eval_split_csv") != expected_eval_split_csv:
        errors.append(f"{rel_path}: eval_split_csv must be {expected_eval_split_csv}")
    if payload.get("leakage_target_meta_csv") != CURRENT_REQUIRED_ARTIFACTS["target_metadata_csv"]:
        errors.append(f"{rel_path}: leakage_target_meta_csv must be {CURRENT_REQUIRED_ARTIFACTS['target_metadata_csv']}")
    if payload.get("leakage_ligand_meta_csv") != expected_ligand_meta_csv:
        errors.append(f"{rel_path}: leakage_ligand_meta_csv must be {expected_ligand_meta_csv}")
    if payload.get("hard_decoy_reference_csv") != expected_ligand_csv:
        errors.append(f"{rel_path}: hard_decoy_reference_csv must match ligand_csv")
    if payload.get("hard_decoy_ligand_meta_csv") != expected_ligand_meta_csv:
        errors.append(f"{rel_path}: hard_decoy_ligand_meta_csv must match leakage_ligand_meta_csv")
    if payload.get("hard_decoy_target_meta_csv") != CURRENT_REQUIRED_ARTIFACTS["target_metadata_csv"]:
        errors.append(f"{rel_path}: hard_decoy_target_meta_csv must be {CURRENT_REQUIRED_ARTIFACTS['target_metadata_csv']}")
    if payload.get("hard_decoy_targets") != EXPECTED_TARGET:
        errors.append(f"{rel_path}: hard_decoy_targets must be {EXPECTED_TARGET}")
    if payload.get("hard_decoy_fit_targets") != EXPECTED_TARGET:
        errors.append(f"{rel_path}: hard_decoy_fit_targets must be {EXPECTED_TARGET}")
    if payload.get("description", "").find("validate-only") < 0:
        errors.append(f"{rel_path}: description must mention validate-only")
    if payload.get("description", "").find("non-claim") < 0:
        errors.append(f"{rel_path}: description must mention non-claim")
    if payload.get("description", "").find("non-production") < 0:
        errors.append(f"{rel_path}: description must mention non-production")

    return summary


def _build_payload(
    repo_root: Path,
    *,
    template_json: str = TEMPLATE_JSON,
    workbook_csv: str = curated_freeze.DEFAULT_WORKBOOK_CSV,
    pending_disposition_json: str = curated_freeze.DEFAULT_PENDING_DISPOSITION_JSON,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    artifact_rows: list[dict[str, Any]] = []
    profile_rows: list[dict[str, Any]] = []
    curated_freeze_payload = _load_optional_curated_freeze_payload(
        repo_root,
        workbook_csv,
        pending_disposition_json,
    )

    current_exists = int(_add_artifact_row(artifact_rows, repo_root, "template_json", template_json, "current_scaffold", True))
    for key, rel_path in CURRENT_REQUIRED_ARTIFACTS.items():
        current_exists += int(_add_artifact_row(artifact_rows, repo_root, key, rel_path, "current_scaffold", True))

    deferred_exists = 0
    deferred_missing: list[str] = []
    for key, rel_path in DEFERRED_REQUIRED_ARTIFACTS.items():
        exists = _add_artifact_row(artifact_rows, repo_root, key, rel_path, "deferred_ood", False)
        deferred_exists += int(exists)
        if not exists:
            deferred_missing.append(rel_path)

    template_path = _repo_path(repo_root, template_json)
    template_summary: dict[str, Any] = {"path": template_json, "exists": template_path.exists()}
    if not template_path.exists():
        errors.append(f"missing template JSON: {template_json}")
    else:
        template_payload = _read_json(template_path)
        template_summary.update(
            {
                "protocol_id": str(template_payload.get("protocol_id", "")),
                "status": str(template_payload.get("status", "")),
                "primary_target": str(template_payload.get("primary_candidate", {}).get("target", "")),
            }
        )

        if template_payload.get("protocol_id") != "external_validation_biorxiv_nuclear_receptor_pxr_v1_template":
            errors.append(f"{template_json}: protocol_id mismatch")
        if template_payload.get("protocol_version") != "template_v1":
            errors.append(f"{template_json}: protocol_version must be template_v1")
        if template_payload.get("status") != "template_not_runnable":
            errors.append(f"{template_json}: status must be template_not_runnable")
        if template_payload.get("primary_candidate", {}).get("target") != EXPECTED_TARGET:
            errors.append(f"{template_json}: primary_candidate.target must be {EXPECTED_TARGET}")

        required_artifacts = template_payload.get("required_artifacts", {})
        for key, expected in EXPECTED_TEMPLATE_REQUIRED_ARTIFACTS.items():
            if required_artifacts.get(key) != expected:
                errors.append(f"{template_json}: required_artifacts.{key} must be {expected}")

        scaffold_status = template_payload.get("scaffold_status", {})
        expected_scaffold_status = {
            "core_profile_present": True,
            "ood_profile_present": True,
            "core_profile_dry_run_only": True,
            "ood_profile_dry_run_only": True,
            "ready_for_validate_only": False,
            "claim_ready": False,
        }
        for key, expected in expected_scaffold_status.items():
            if scaffold_status.get(key) != expected:
                errors.append(f"{template_json}: scaffold_status.{key} must be {expected}")

        actual_tasks = []
        for set_payload in template_payload.get("sets", []):
            tasks = set_payload.get("tasks", [])
            if not tasks:
                continue
            task = tasks[0]
            actual_tasks.append(
                {
                    "set_id": str(set_payload.get("set_id", "")),
                    "task_id": str(task.get("task_id", "")),
                    "profile_json": str(task.get("profile_json", "")),
                    "ligand_sizes": str(task.get("ligand_sizes", "")),
                }
            )
        if actual_tasks != EXPECTED_TEMPLATE_TASKS:
            errors.append(f"{template_json}: set/task profile links do not match expected PXR scaffold contract")

        if deferred_missing and template_payload.get("status") == "template_not_runnable":
            warnings.append(
                "Deferred chembl50 scaffold artifacts are still missing; this is allowed because the template remains non-runnable."
            )
        elif deferred_missing:
            errors.append(f"{template_json}: deferred OOD artifacts are missing even though the template is not marked template_not_runnable")

    profile_rows.append(
        _check_profile_contract(
            name="core",
            rel_path=CORE_PROFILE_JSON,
            repo_root=repo_root,
            expected_ligand_csv=CURRENT_REQUIRED_ARTIFACTS["core_reference_csv"],
            expected_eval_split_csv=CURRENT_REQUIRED_ARTIFACTS["core_eval_split_csv"],
            expected_ligand_meta_csv=CURRENT_REQUIRED_ARTIFACTS["core_ligand_meta_csv"],
            errors=errors,
        )
    )
    profile_rows.append(
        _check_profile_contract(
            name="ood",
            rel_path=OOD_PROFILE_JSON,
            repo_root=repo_root,
            expected_ligand_csv=DEFERRED_REQUIRED_ARTIFACTS["ood_reference_csv"],
            expected_eval_split_csv=DEFERRED_REQUIRED_ARTIFACTS["ood_eval_split_csv"],
            expected_ligand_meta_csv=DEFERRED_REQUIRED_ARTIFACTS["ood_ligand_meta_csv"],
            errors=errors,
        )
    )

    payload = {
        "inputs": {
            "root": str(repo_root),
            "template_json": template_json,
            "core_profile_json": CORE_PROFILE_JSON,
            "ood_profile_json": OOD_PROFILE_JSON,
            "workbook_csv": workbook_csv,
            "pending_disposition_json": pending_disposition_json,
        },
        "summary": {
            "pass": len(errors) == 0,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "current_required_artifact_count": len(CURRENT_REQUIRED_ARTIFACTS) + 1,
            "current_required_artifact_exists_count": current_exists,
            "deferred_artifact_count": len(DEFERRED_REQUIRED_ARTIFACTS),
            "deferred_artifact_exists_count": deferred_exists,
            "deferred_missing_count": len(deferred_missing),
            "expected_target": EXPECTED_TARGET,
            "curated_freeze_row_count": int(curated_freeze_payload.get("summary", {}).get("ready_row_count", 0) or 0),
            "curated_freeze_blocked_row_count": int(curated_freeze_payload.get("summary", {}).get("blocked_row_count", 0) or 0),
            "partial_curated_packet_count": int(curated_freeze_payload.get("summary", {}).get("partial_packet_count", 0) or 0),
        },
        "template": template_summary,
        "profiles": profile_rows,
        "artifacts": artifact_rows,
        "curated_freeze": curated_freeze_payload,
        "deferred_missing_artifacts": deferred_missing,
        "warnings": warnings,
        "errors": errors,
    }
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the PXR scaffold/template package without attempting a real blind run."
    )
    parser.add_argument(
        "--root",
        default=str(ROOT),
        help="Repo root containing the PXR scaffold files.",
    )
    parser.add_argument(
        "--template-json",
        default=TEMPLATE_JSON,
        help="Template JSON to validate relative to --root.",
    )
    parser.add_argument(
        "--workbook-csv",
        default=curated_freeze.DEFAULT_WORKBOOK_CSV,
        help="Reviewed workbook CSV used to summarize partial curated freeze state when present.",
    )
    parser.add_argument(
        "--pending-disposition-json",
        default=curated_freeze.DEFAULT_PENDING_DISPOSITION_JSON,
        help="Pending disposition JSON used to annotate blocked workbook rows when present.",
    )
    parser.add_argument(
        "--out-json",
        default="runs/pxr_expansion_scaffold_check_current.json",
        help="Output JSON summary path.",
    )
    parser.add_argument(
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Print warnings/errors and curated-freeze summary after writing the JSON output.",
    )
    parser.add_argument(
        "--strict-fail",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Return a non-zero exit code when scaffold checks fail.",
    )
    return parser


def run_check(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.root).resolve()
    payload = _build_payload(
        repo_root,
        template_json=args.template_json,
        workbook_csv=args.workbook_csv,
        pending_disposition_json=args.pending_disposition_json,
    )
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    payload["artifacts_out_json"] = str(out_json)
    return payload


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_check(args)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
    print(f"Wrote summary: {payload['artifacts_out_json']}")
    if bool(args.verbose):
        freeze_summary = dict(payload.get("curated_freeze", {}).get("summary", {}) or {})
        if freeze_summary:
            print(
                "Curated freeze: "
                f"ready_rows={freeze_summary.get('ready_row_count', 0)} "
                f"blocked_rows={freeze_summary.get('blocked_row_count', 0)} "
                f"partial_packets={freeze_summary.get('partial_packet_count', 0)}"
            )
        for warning in payload.get("warnings", []) or []:
            print(f"warning: {warning}")
        for error in payload.get("errors", []) or []:
            print(f"error: {error}")
    if bool(args.strict_fail) and not bool(payload["summary"]["pass"]):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
