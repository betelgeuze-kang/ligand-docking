#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from api.validated_runner import ALLOWED_RUNNER_SCRIPTS


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_runner(script: str) -> Path:
    path = Path(script)
    if not path.is_absolute():
        path = _repo_root() / path
    return path


def _evidence_template(profile_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "input_contract_reviewed": False,
        "output_contract_reviewed": False,
        "claim_boundary_reviewed": False,
        "gate_policy_reviewed": False,
        "fake_result_emission_forbidden": False,
        "gate_policy_artifact": "",
        "reviewer": "",
        "reviewed_at_utc": "",
        "notes": "",
        "claim_boundary": str(profile.get("claim_boundary", "") or ""),
        "required_operator_action": (
            "Set every *_reviewed field to true only after reviewing the exact profile inputs, outputs, "
            "claim boundary, and downstream gate policy. Do not enable the profile from this template alone."
        ),
    }


def build_work_order(profiles_dir: Path, *, evidence_dir: Path | None = None, write_templates: bool = False) -> dict[str, Any]:
    profiles = sorted(profiles_dir.glob("*.json"))
    rows: list[dict[str, Any]] = []
    for profile_path in profiles:
        profile = _read_json(profile_path)
        profile_id = str(profile.get("profile_id", profile_path.stem) or profile_path.stem)
        enabled = bool(profile.get("enabled") is True)
        runner_script = str(profile.get("runner_script", "") or "")
        runner_path = _resolve_runner(runner_script) if runner_script else Path("")
        runner_exists = bool(runner_script and runner_path.exists())
        runner_hash = _sha256(runner_path) if runner_exists else ""
        runner_allowlisted = runner_script in ALLOWED_RUNNER_SCRIPTS
        template_rel = ""
        template_path = None
        if evidence_dir is not None:
            template_path = evidence_dir / f"{profile_id}.evidence.template.json"
            template_rel = str(template_path)
            if write_templates:
                template_path.parent.mkdir(parents=True, exist_ok=True)
                template_path.write_text(
                    json.dumps(_evidence_template(profile_id, profile), indent=2, sort_keys=True, ensure_ascii=False)
                    + "\n",
                    encoding="utf-8",
                )

        rows.append(
            {
                "profile_id": profile_id,
                "profile_path": str(profile_path),
                "enabled": enabled,
                "runner_script": runner_script,
                "runner_exists": runner_exists,
                "runner_allowlisted": runner_allowlisted,
                "runner_script_sha256": runner_hash,
                "evidence_template": template_rel,
                "ready_for_operator_review": bool((not enabled) and runner_exists and runner_allowlisted),
                "next_required_step": (
                    "Fill evidence_template, add production_readiness with this runner_script_sha256, then set "
                    "enabled=true only after operator approval."
                    if not enabled
                    else "Already enabled; validate with tools/product/validate_api_runner_profiles.py."
                ),
            }
        )

    return {
        "status": "ready",
        "profiles_dir": str(profiles_dir),
        "profile_count": len(profiles),
        "disabled_profile_count": sum(1 for row in rows if not row["enabled"]),
        "enabled_profile_count": sum(1 for row in rows if row["enabled"]),
        "work_order_only": True,
        "claim_boundary": (
            "Profile enablement work order only. It does not approve, enable, or execute scientific runners."
        ),
        "rows": rows,
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# API Runner Profile Enablement Work Order",
        "",
        f"- profiles_dir: `{payload['profiles_dir']}`",
        f"- profile_count: `{payload['profile_count']}`",
        f"- disabled_profile_count: `{payload['disabled_profile_count']}`",
        f"- enabled_profile_count: `{payload['enabled_profile_count']}`",
        f"- claim_boundary: {payload['claim_boundary']}",
        "",
        "| Profile | Enabled | Runner | Allowlisted | Runner SHA256 | Evidence Template | Next Step |",
        "|---|---:|---|---:|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            "| `{profile_id}` | `{enabled}` | `{runner_script}` | `{runner_allowlisted}` | `{runner_script_sha256}` | `{evidence_template}` | {next_required_step} |".format(
                **row
            )
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build API runner profile enablement work order.")
    parser.add_argument("--profiles-dir", default="config/api_validated_runner_profiles")
    parser.add_argument("--evidence-dir", default="config/api_validated_runner_profiles/evidence")
    parser.add_argument("--write-evidence-templates", action="store_true")
    parser.add_argument("--out-json", default="runs/api_runner_profile_enablement_work_order_current.json")
    parser.add_argument("--out-md", default="runs/api_runner_profile_enablement_work_order_current.md")
    args = parser.parse_args(argv)

    payload = build_work_order(
        Path(args.profiles_dir),
        evidence_dir=Path(args.evidence_dir) if args.evidence_dir else None,
        write_templates=bool(args.write_evidence_templates),
    )
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_markdown(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
