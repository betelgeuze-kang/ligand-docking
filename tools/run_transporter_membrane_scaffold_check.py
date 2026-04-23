#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_SET_SPEC_JSON = "config/external_validation_transporter_membrane_sets_v1_template.json"

EXPECTED_PRIMARY_CANDIDATES = {
    "core_blind": "AQP1_TRANSPORT_BLIND",
    "expanded_ood": "GLUT1_TRANSPORT_BLIND",
}

EXPECTED_SCAFFOLD_STATUS = {
    "aqp1_profile_present": True,
    "glut1_profile_present": True,
    "aqp1_profile_dry_run_only": True,
    "glut1_profile_dry_run_only": True,
    "ready_for_validate_only": False,
    "claim_ready": False,
}

EXPECTED_REQUIRED_ARTIFACTS = {
    "aqp1_target_csv": "config/real_drug_targets_blind_aqp1_v1.csv",
    "aqp1_target_metadata_csv": "config/ligand_target_metadata_blind_aqp1_v1.csv",
    "aqp1_reference_csv": "config/ligand_binding_reference_blind_aqp1_v1.csv",
    "aqp1_eval_split_csv": "config/ligand_eval_splits_blind_aqp1_v1.csv",
    "aqp1_ligand_meta_csv": "config/ligand_meta_blind_aqp1_v1.csv",
    "aqp1_profile_json": "config/ligand_htvs_blind_aqp1_v1.json",
    "glut1_target_csv": "config/real_drug_targets_blind_glut1_4pyp_v1.csv",
    "glut1_target_metadata_csv": "config/ligand_target_metadata_blind_glut1_4pyp_v1.csv",
    "glut1_reference_csv": "config/ligand_binding_reference_blind_glut1_4pyp_v1.csv",
    "glut1_eval_split_csv": "config/ligand_eval_splits_blind_glut1_4pyp_v1.csv",
    "glut1_ligand_meta_csv": "config/ligand_meta_blind_glut1_4pyp_v1.csv",
    "glut1_profile_json": "config/ligand_htvs_blind_glut1_4pyp_v1.json",
}

EXPECTED_TASKS = {
    "aqp1_core_full": {
        "set_id": "set1_core_blind",
        "profile_json": "config/ligand_htvs_blind_aqp1_v1.json",
        "ligand_sizes": "10000",
    },
    "glut1_4pyp_full": {
        "set_id": "set2_expanded_ood",
        "profile_json": "config/ligand_htvs_blind_glut1_4pyp_v1.json",
        "ligand_sizes": "10000",
    },
    "aqp1_smoke": {
        "set_id": "set3_operational_smoke",
        "profile_json": "config/ligand_htvs_blind_aqp1_v1.json",
        "ligand_sizes": "64",
    },
}

EXPECTED_PROFILES = {
    "config/ligand_htvs_blind_aqp1_v1.json": {
        "target": "AQP1_TRANSPORT_BLIND",
        "target_native_csv": "config/real_drug_targets_blind_aqp1_v1.csv",
        "ligand_csv": "config/ligand_binding_reference_blind_aqp1_v1.csv",
        "eval_split_csv": "config/ligand_eval_splits_blind_aqp1_v1.csv",
        "leakage_ligand_meta_csv": "config/ligand_meta_blind_aqp1_v1.csv",
        "leakage_target_meta_csv": "config/ligand_target_metadata_blind_aqp1_v1.csv",
    },
    "config/ligand_htvs_blind_glut1_4pyp_v1.json": {
        "target": "GLUT1_TRANSPORT_BLIND",
        "target_native_csv": "config/real_drug_targets_blind_glut1_4pyp_v1.csv",
        "ligand_csv": "config/ligand_binding_reference_blind_glut1_4pyp_v1.csv",
        "eval_split_csv": "config/ligand_eval_splits_blind_glut1_4pyp_v1.csv",
        "leakage_ligand_meta_csv": "config/ligand_meta_blind_glut1_4pyp_v1.csv",
        "leakage_target_meta_csv": "config/ligand_target_metadata_blind_glut1_4pyp_v1.csv",
    },
}


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object: {path}")
    return payload


def _record_error(payload: Dict[str, Any], message: str) -> None:
    payload["errors"].append(message)


def _record_warning(payload: Dict[str, Any], message: str) -> None:
    payload["warnings"].append(message)


def _resolve(root: Path, rel_path: str) -> Path:
    return root / rel_path


def run_check(root: str, set_spec_json: str = DEFAULT_SET_SPEC_JSON) -> Dict[str, Any]:
    repo_root = Path(root).resolve()
    payload: Dict[str, Any] = {
        "ok": True,
        "mode": "validate_only_scaffold_check",
        "root": str(repo_root),
        "set_spec_json": str(set_spec_json),
        "errors": [],
        "warnings": [],
        "artifacts": [],
        "tasks": [],
        "profiles": [],
        "summary": {},
    }

    spec_path = _resolve(repo_root, set_spec_json)
    if not spec_path.exists():
        _record_error(payload, f"set spec json missing: {set_spec_json}")
        payload["ok"] = False
        payload["summary"] = {"error_count": 1, "warning_count": 0}
        return payload

    spec = _load_json(spec_path)
    if spec.get("protocol_id") != "external_validation_transporter_membrane_sets_v1_template":
        _record_error(payload, "unexpected transporter scaffold protocol_id")
    if spec.get("status") != "template_not_runnable":
        _record_error(payload, "transporter scaffold set spec must stay template_not_runnable")
    if spec.get("primary_candidates") != EXPECTED_PRIMARY_CANDIDATES:
        _record_error(payload, "transporter scaffold primary_candidates mismatch")
    if spec.get("scaffold_status") != EXPECTED_SCAFFOLD_STATUS:
        _record_error(payload, "transporter scaffold_status drifted from validate-only template expectations")

    required_artifacts = spec.get("required_artifacts", {})
    if not isinstance(required_artifacts, dict):
        required_artifacts = {}
        _record_error(payload, "required_artifacts missing or invalid")
    for key, expected_rel_path in EXPECTED_REQUIRED_ARTIFACTS.items():
        actual_rel_path = str(required_artifacts.get(key, ""))
        resolved = _resolve(repo_root, actual_rel_path) if actual_rel_path else None
        exists = bool(resolved and resolved.exists())
        row = {
            "artifact_key": key,
            "expected_rel_path": expected_rel_path,
            "actual_rel_path": actual_rel_path,
            "exists": exists,
            "matches_expected": actual_rel_path == expected_rel_path,
        }
        payload["artifacts"].append(row)
        if actual_rel_path != expected_rel_path:
            _record_error(payload, f"required_artifacts[{key}] mismatch: expected {expected_rel_path}, found {actual_rel_path or '<missing>'}")
        if not exists:
            _record_error(payload, f"required artifact missing on disk: {actual_rel_path or expected_rel_path}")

    seen_task_ids: List[str] = []
    sets = spec.get("sets", [])
    if not isinstance(sets, list):
        sets = []
        _record_error(payload, "sets missing or invalid")
    for set_payload in sets:
        if not isinstance(set_payload, dict):
            continue
        set_id = str(set_payload.get("set_id", "")).strip()
        for task in set_payload.get("tasks", []) if isinstance(set_payload.get("tasks"), list) else []:
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("task_id", "")).strip()
            profile_json = str(task.get("profile_json", "")).strip()
            ligand_sizes = str(task.get("ligand_sizes", "")).strip()
            expected = EXPECTED_TASKS.get(task_id, {})
            row = {
                "set_id": set_id,
                "task_id": task_id,
                "profile_json": profile_json,
                "ligand_sizes": ligand_sizes,
                "matches_expected_profile": bool(expected and profile_json == expected.get("profile_json")),
            }
            payload["tasks"].append(row)
            seen_task_ids.append(task_id)
            if str(task.get("domain", "")).strip() != "transporter_membrane":
                _record_error(payload, f"task {task_id} must keep domain=transporter_membrane")
            if str(task.get("kind", "")).strip() != "ligand_stress":
                _record_error(payload, f"task {task_id} must keep kind=ligand_stress")
            if not expected:
                _record_error(payload, f"unexpected transporter task id: {task_id}")
                continue
            if set_id != expected["set_id"]:
                _record_error(payload, f"task {task_id} linked to unexpected set_id {set_id}")
            if profile_json != expected["profile_json"]:
                _record_error(payload, f"task {task_id} profile_json mismatch: expected {expected['profile_json']}, found {profile_json}")
            if ligand_sizes != expected["ligand_sizes"]:
                _record_error(payload, f"task {task_id} ligand_sizes mismatch: expected {expected['ligand_sizes']}, found {ligand_sizes}")

    if sorted(seen_task_ids) != sorted(EXPECTED_TASKS.keys()):
        _record_error(payload, "transporter scaffold task set does not match expected validate-only template tasks")

    for profile_rel_path, expected in EXPECTED_PROFILES.items():
        profile_path = _resolve(repo_root, profile_rel_path)
        if not profile_path.exists():
            payload["profiles"].append({"profile_json": profile_rel_path, "exists": False})
            _record_error(payload, f"profile json missing: {profile_rel_path}")
            continue
        profile = _load_json(profile_path)
        description = str(profile.get("description", ""))
        hard_decoy_targets = [part.strip() for part in str(profile.get("hard_decoy_targets", "")).split(",") if part.strip()]
        row = {
            "profile_json": profile_rel_path,
            "exists": True,
            "version": profile.get("version"),
            "target": profile.get("targets"),
            "dry_run": bool(profile.get("dry_run", False)),
            "description_has_dry_run": "dry-run" in description.lower(),
            "description_has_template": "template" in description.lower(),
        }
        payload["profiles"].append(row)
        if profile.get("version") != Path(profile_rel_path).stem:
            _record_error(payload, f"profile version mismatch for {profile_rel_path}")
        if profile.get("targets") != expected["target"]:
            _record_error(payload, f"profile target mismatch for {profile_rel_path}: expected {expected['target']}, found {profile.get('targets')}")
        if profile.get("run_scope") != "full":
            _record_error(payload, f"profile run_scope must stay full for {profile_rel_path}")
        if bool(profile.get("dry_run", False)) is not True:
            _record_error(payload, f"profile dry_run must stay true for {profile_rel_path}")
        if "dry-run" not in description.lower():
            _record_error(payload, f"profile description must mention dry-run for {profile_rel_path}")
        if "template" not in description.lower():
            _record_error(payload, f"profile description must mention template semantics for {profile_rel_path}")
        for field_name, expected_rel_path in expected.items():
            if field_name == "target":
                continue
            actual_rel_path = str(profile.get(field_name, "")).strip()
            if actual_rel_path != expected_rel_path:
                _record_error(payload, f"profile {profile_rel_path} field {field_name} mismatch: expected {expected_rel_path}, found {actual_rel_path or '<missing>'}")
            if actual_rel_path:
                linked_path = _resolve(repo_root, actual_rel_path)
                if not linked_path.exists():
                    _record_error(payload, f"profile {profile_rel_path} references missing file via {field_name}: {actual_rel_path}")
        if profile.get("calibration_reference_csv") != expected["ligand_csv"]:
            _record_error(payload, f"profile calibration_reference_csv mismatch for {profile_rel_path}")
        if profile.get("ranking_labels_csv") != expected["ligand_csv"]:
            _record_error(payload, f"profile ranking_labels_csv mismatch for {profile_rel_path}")
        if profile.get("hard_decoy_fit_targets") != "EGFR_KINASE":
            _record_error(payload, f"profile hard_decoy_fit_targets must stay EGFR_KINASE for {profile_rel_path}")
        if "EGFR_KINASE" not in hard_decoy_targets:
            _record_error(payload, f"profile hard_decoy_targets missing EGFR_KINASE for {profile_rel_path}")
        if expected["target"] not in hard_decoy_targets:
            _record_error(payload, f"profile hard_decoy_targets missing {expected['target']} for {profile_rel_path}")

    explicit_template_markers = 0
    for row in payload["profiles"]:
        profile_rel_path = str(row.get("profile_json", ""))
        if not row.get("exists"):
            continue
        profile = _load_json(_resolve(repo_root, profile_rel_path))
        if bool(profile.get("template_profile", False)):
            explicit_template_markers += 1
        if "claim_ready" in profile and bool(profile.get("claim_ready", False)):
            _record_warning(payload, f"profile claim_ready is true in a scaffold profile: {profile_rel_path}")

    payload["summary"] = {
        "artifact_count": len(payload["artifacts"]),
        "artifact_exists_count": sum(1 for row in payload["artifacts"] if row["exists"]),
        "task_count": len(payload["tasks"]),
        "profile_count": len(payload["profiles"]),
        "dry_run_profile_count": sum(1 for row in payload["profiles"] if row.get("dry_run") is True),
        "explicit_template_profile_count": explicit_template_markers,
        "error_count": len(payload["errors"]),
        "warning_count": len(payload["warnings"]),
        "claim_ready": bool(spec.get("scaffold_status", {}).get("claim_ready", False)) if isinstance(spec.get("scaffold_status"), dict) else False,
        "ready_for_validate_only": bool(spec.get("scaffold_status", {}).get("ready_for_validate_only", False)) if isinstance(spec.get("scaffold_status"), dict) else False,
    }
    payload["ok"] = len(payload["errors"]) == 0
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the transporter/membrane scaffold package without attempting a real blind run."
    )
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="Repo root containing config/ and docs/.")
    parser.add_argument("--set-spec-json", default=DEFAULT_SET_SPEC_JSON, help="Transporter scaffold set spec path, relative to --root.")
    return parser


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_check(root=str(args.root), set_spec_json=str(args.set_spec_json))
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
