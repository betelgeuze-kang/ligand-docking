#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILES_DIR = "config/api_validated_runner_profiles"
DEFAULT_EVIDENCE_DIR = "config/api_validated_runner_profiles/evidence"
DEFAULT_OUT_JSON = "runs/api_runner_profile_promotion_readiness_current.json"
DEFAULT_OUT_CSV = "runs/api_runner_profile_promotion_readiness_current.csv"
DEFAULT_OUT_MD = "runs/api_runner_profile_promotion_readiness_current.md"
DEFAULT_OPERATOR_TEMPLATE_CSV = "runs/api_runner_profile_promotion_operator_template_current.csv"

APPROVAL_TOKEN = "APPROVE_API_RUNNER_PROFILE_PROMOTION"
ALLOWED_RUNNER_SCRIPTS = {
    "tools/run_ligand_htvs_pipeline.py",
    "tools/run_ligand_backmapping_scoring.py",
    "tools/run_ligand_topk_delivery.py",
}
REQUIRED_TRUE_EVIDENCE = (
    "input_contract_reviewed",
    "output_contract_reviewed",
    "claim_boundary_reviewed",
    "gate_policy_reviewed",
    "fake_result_emission_forbidden",
)
DELIVERY_PROXY_REFINEMENT_SCOPES = (
    "restricted_local_delivery_proxy_refinement_only",
)
CLAIM_BOUNDARY = (
    "API runner profile promotion readiness only; it validates disabled profile metadata and operator evidence "
    "before a separate approval/edit step. It does not enable profiles, edit JSON, run scientific runners, submit jobs, "
    "or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_operator_template(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "profile_id",
        "enabled",
        "delivery_oriented",
        "evidence_bundle_template",
        "evidence_bundle_template_declared",
        "operator_decision",
        "approval_token",
        "input_contract_reviewed",
        "output_contract_reviewed",
        "claim_boundary_reviewed",
        "gate_policy_reviewed",
        "fake_result_emission_forbidden",
        "gate_policy_artifact",
        "reviewer",
        "reviewed_at_utc",
        "operator_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        if not rows:
            writer.writerow(
                {
                    "profile_id": "OPERATOR_FILL_PROFILE_ID",
                    "enabled": "",
                    "delivery_oriented": "",
                    "evidence_bundle_template": "",
                    "evidence_bundle_template_declared": "",
                    "operator_decision": "",
                    "approval_token": "",
                    "input_contract_reviewed": "",
                    "output_contract_reviewed": "",
                    "claim_boundary_reviewed": "",
                    "gate_policy_reviewed": "",
                    "fake_result_emission_forbidden": "",
                    "gate_policy_artifact": "",
                    "reviewer": "",
                    "reviewed_at_utc": "",
                    "operator_note": "",
                }
            )
            return
        for row in rows:
            writer.writerow(
                {
                    "profile_id": row["profile_id"],
                    "enabled": row["enabled"],
                    "delivery_oriented": row["delivery_oriented"],
                    "evidence_bundle_template": row["evidence_bundle_template"],
                    "evidence_bundle_template_declared": row["evidence_bundle_template_declared"],
                    "operator_decision": "",
                    "approval_token": "",
                    "input_contract_reviewed": "",
                    "output_contract_reviewed": "",
                    "claim_boundary_reviewed": "",
                    "gate_policy_reviewed": "",
                    "fake_result_emission_forbidden": "",
                    "gate_policy_artifact": "",
                    "reviewer": "",
                    "reviewed_at_utc": "",
                    "operator_note": "",
                }
            )


def _sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool(value: Any) -> bool:
    return value is True


def _profile_paths(profiles_dir: Path) -> list[Path]:
    return sorted(path for path in profiles_dir.glob("*.json") if path.is_file())


def _evidence_paths(evidence_dir: Path, profile_id: str) -> list[Path]:
    return [
        evidence_dir / f"{profile_id}.evidence.template.json",
        evidence_dir / f"{profile_id}.evidence.json",
    ]


def _read_profile_evidence(evidence_dir: Path, profile_id: str) -> tuple[Path, dict[str, Any]]:
    for path in _evidence_paths(evidence_dir, profile_id):
        if path.is_file():
            return path, _read_json_if_present(path)
    return _evidence_paths(evidence_dir, profile_id)[0], {}


def _evidence_status(evidence: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    for key in REQUIRED_TRUE_EVIDENCE:
        if evidence.get(key) is not True:
            blockers.append(f"{key}_not_true")
    for key in ("gate_policy_artifact", "reviewer", "reviewed_at_utc"):
        if not _text(evidence.get(key)):
            blockers.append(f"{key}_missing")
    return not blockers, blockers


def _claim_scope(profile: dict[str, Any]) -> str:
    production_readiness = profile.get("production_readiness")
    if isinstance(production_readiness, dict):
        scope = _text(production_readiness.get("claim_scope"))
        if scope:
            return scope
    return _text(profile.get("claim_scope"))


def _is_delivery_oriented(profile: dict[str, Any]) -> bool:
    scope = _claim_scope(profile)
    return any(marker in scope for marker in DELIVERY_PROXY_REFINEMENT_SCOPES)


def _requires_native_bundle(profile: dict[str, Any]) -> bool:
    return _bool(profile.get("enabled")) or _is_delivery_oriented(profile)


def build_api_runner_profile_promotion_readiness(
    *,
    profiles_dir: str | Path = DEFAULT_PROFILES_DIR,
    evidence_dir: str | Path = DEFAULT_EVIDENCE_DIR,
    operator_template_csv: str | Path = DEFAULT_OPERATOR_TEMPLATE_CSV,
) -> dict[str, Any]:
    profiles_root = _resolve(profiles_dir)
    evidence_root = _resolve(evidence_dir)
    rows: list[dict[str, Any]] = []
    for profile_path in _profile_paths(profiles_root):
        profile = _read_json_if_present(profile_path)
        profile_id = _text(profile.get("profile_id") or profile_path.stem)
        enabled = _bool(profile.get("enabled"))
        runner_script = _text(profile.get("runner_script"))
        runner_path = _resolve(runner_script) if runner_script else Path("")
        runner_exists = bool(runner_script and runner_path.is_file())
        runner_hash = _sha256(runner_path)
        runner_allowlisted = runner_script in ALLOWED_RUNNER_SCRIPTS
        evidence_path, evidence = _read_profile_evidence(evidence_root, profile_id)
        evidence_ready, evidence_blockers = _evidence_status(evidence)
        production_readiness = profile.get("production_readiness")
        production_readiness = production_readiness if isinstance(production_readiness, dict) else {}
        production_evidence_path = _text(production_readiness.get("evidence_artifact"))
        production_evidence = _read_json_if_present(production_evidence_path) if production_evidence_path else {}
        production_evidence_ready, _ = _evidence_status(production_evidence) if production_evidence else (False, [])
        already_promoted = enabled and production_evidence_ready
        delivery_oriented = _is_delivery_oriented(profile)
        claim_scope_value = _claim_scope(profile)
        evidence_bundle_template = _text(profile.get("evidence_bundle_template"))
        evidence_bundle_template_declared = bool(evidence_bundle_template)
        requires_native_bundle = _requires_native_bundle(profile)
        profile_blockers: list[str] = []
        if enabled and not already_promoted:
            profile_blockers.append("profile_already_enabled")
        if not runner_script:
            profile_blockers.append("runner_script_missing")
        if runner_script and not runner_allowlisted:
            profile_blockers.append("runner_script_not_allowlisted")
        if runner_script and not runner_exists:
            profile_blockers.append("runner_script_file_missing")
        if not _text(profile.get("result_file_template")):
            profile_blockers.append("result_file_template_missing")
        if not _text(profile.get("claim_boundary")):
            profile_blockers.append("claim_boundary_missing")
        if not evidence_path.is_file() and not production_evidence_path:
            profile_blockers.append("evidence_file_missing")
        if requires_native_bundle and not evidence_bundle_template_declared:
            profile_blockers.append("evidence_bundle_template_missing")
        if not already_promoted:
            profile_blockers.extend(evidence_blockers)
        ready = not profile_blockers
        rows.append(
            {
                "profile_id": profile_id,
                "profile_path": str(profile_path.relative_to(ROOT) if profile_path.is_relative_to(ROOT) else profile_path),
                "enabled": enabled,
                "already_promoted": already_promoted,
                "delivery_oriented": delivery_oriented,
                "claim_scope": claim_scope_value,
                "runner_script": runner_script,
                "runner_exists": runner_exists,
                "runner_allowlisted": runner_allowlisted,
                "runner_script_sha256": runner_hash,
                "evidence_artifact": str(evidence_path.relative_to(ROOT) if evidence_path.is_relative_to(ROOT) else evidence_path),
                "evidence_ready": evidence_ready,
                "evidence_bundle_template": evidence_bundle_template,
                "evidence_bundle_template_declared": evidence_bundle_template_declared,
                "requires_native_evidence_bundle": requires_native_bundle,
                "promotion_ready": ready,
                "blocker_count": len(profile_blockers),
                "blockers": ",".join(profile_blockers),
                "approval_token_required": APPROVAL_TOKEN,
                "profile_enabled_by_this_tool": False,
                "runner_executed": False,
                "external_state_mutated": False,
            }
        )
    ready_count = sum(1 for row in rows if row["promotion_ready"])
    blocked_count = len(rows) - ready_count
    native_bundle_missing_rows = [
        row
        for row in rows
        if row["requires_native_evidence_bundle"] and not row["evidence_bundle_template_declared"]
    ]
    summary = {
        "packet_type": "api_runner_profile_promotion_readiness",
        "status": "api_runner_profile_promotion_ready" if rows and blocked_count == 0 else "blocked_api_runner_profile_promotion_readiness",
        "profiles_dir": str(profiles_root.relative_to(ROOT) if profiles_root.is_relative_to(ROOT) else profiles_root),
        "evidence_dir": str(evidence_root.relative_to(ROOT) if evidence_root.is_relative_to(ROOT) else evidence_root),
        "profile_count": len(rows),
        "promotion_ready_count": ready_count,
        "blocked_profile_count": blocked_count,
        "enabled_profile_count": sum(1 for row in rows if row["enabled"]),
        "native_evidence_bundle_required_profile_count": sum(
            1 for row in rows if row["requires_native_evidence_bundle"]
        ),
        "native_evidence_bundle_missing_profile_count": len(native_bundle_missing_rows),
        "first_native_evidence_bundle_missing_profile_id": (
            native_bundle_missing_rows[0]["profile_id"] if native_bundle_missing_rows else ""
        ),
        "approval_token_required": APPROVAL_TOKEN,
        "operator_template_csv": str(operator_template_csv),
        "profile_enabled_by_this_tool": False,
        "runner_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Apply a separate operator-approved profile edit only after reviewing this readiness packet."
            if rows and blocked_count == 0
            else (
                "Add native evidence_bundle_template to each delivery/proxy-refinement profile and confirm "
                "runner-native EvidenceBundle emission before any delivery profile can be promoted."
                if native_bundle_missing_rows
                else "Fill profile evidence artifacts and required review fields before any profile can be promoted."
            )
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# API Runner Profile Promotion Readiness",
        "",
        f"- status: `{s['status']}`",
        f"- profile_count: `{s['profile_count']}`",
        f"- promotion_ready_count: `{s['promotion_ready_count']}`",
        f"- blocked_profile_count: `{s['blocked_profile_count']}`",
        f"- enabled_profile_count: `{s['enabled_profile_count']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- operator_template_csv: `{s['operator_template_csv']}`",
        f"- profile_enabled_by_this_tool: `{s['profile_enabled_by_this_tool']}`",
        f"- runner_executed: `{s['runner_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Profiles",
        "",
        "| profile | enabled | delivery_oriented | runner | evidence | native_bundle_template | ready | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['profile_id']}` | `{row['enabled']}` | `{row['delivery_oriented']}` | "
            f"`{row['runner_script']}` | `{row['evidence_artifact']}` | "
            f"`{row['evidence_bundle_template']}` | `{row['promotion_ready']}` | `{row['blockers']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build API runner profile promotion readiness gate.")
    parser.add_argument("--profiles-dir", default=DEFAULT_PROFILES_DIR)
    parser.add_argument("--evidence-dir", default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--operator-template-csv", default=DEFAULT_OPERATOR_TEMPLATE_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_api_runner_profile_promotion_readiness(
        profiles_dir=args.profiles_dir,
        evidence_dir=args.evidence_dir,
        operator_template_csv=args.operator_template_csv,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_operator_template(args.operator_template_csv, payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
