#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BASE_PROFILE_JSON = "config/ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k.json"
DEFAULT_SPEC_JSON = "runs/gpcr_residual_prototype_spec_core_decoy_intrusion_v1_current.json"
DEFAULT_OUT_DIR = "runs/gpcr_scaleup_100k_core_decoy_intrusion_candidate_current"
DEFAULT_TAG_SUFFIX = "core-decoy-intrusion100k"
INTRUSION_VARIANT = "gpcr_core_decoy_intrusion_v1"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rel_or_abs(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def _default_spec_sidecar(path: Path, suffix: str) -> Path:
    if path.suffix == ".json":
        return path.with_suffix(suffix)
    return path.parent / f"{path.name}{suffix}"


def ensure_intrusion_spec(spec_json: Path) -> None:
    if spec_json.exists():
        return
    cmd = [
        sys.executable,
        str(ROOT / "tools" / "build_gpcr_residual_prototype_spec.py"),
        "--variant",
        INTRUSION_VARIANT,
        "--out-json",
        str(spec_json),
        "--out-csv",
        str(_default_spec_sidecar(spec_json, ".csv")),
        "--out-md",
        str(_default_spec_sidecar(spec_json, ".md")),
    ]
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def _validate_intrusion_spec(spec: dict[str, Any], spec_json: Path) -> None:
    summary = spec.get("summary")
    prototype = spec.get("prototype")
    tuning = prototype.get("tuning") if isinstance(prototype, dict) else {}
    variants = {
        str(summary.get("prototype_variant", "")).strip() if isinstance(summary, dict) else "",
        str(tuning.get("variant", "")).strip() if isinstance(tuning, dict) else "",
    }
    if INTRUSION_VARIANT not in variants:
        raise ValueError(f"{spec_json} is not a {INTRUSION_VARIANT} residual prototype spec")


def _candidate_profile(base_profile: dict[str, Any], *, residual_spec_json: Path) -> dict[str, Any]:
    profile = dict(base_profile)
    profile["residual_prototype_enabled"] = True
    profile["residual_prototype_mode"] = "shadow_only"
    profile["residual_prototype_family"] = "gpcr"
    profile["residual_prototype_apply_stage"] = "stage5_ranking"
    profile["residual_prototype_status"] = "shadow_runtime_ready"
    profile["residual_prototype_runtime_hook_ready"] = True
    profile["residual_prototype_spec_json"] = str(residual_spec_json.resolve())
    profile["residual_prototype_candidate"] = INTRUSION_VARIANT
    profile["ranking_score_col"] = "binding_score_composite_v7"
    profile["ranking_probability_score_col"] = "binding_score_composite_v7"
    profile["router_promotion_allowed"] = False
    profile["residual_prototype_notes"] = (
        "Shadow-only GPCR core-decoy intrusion 100k candidate. v7 remains the active ranking score; "
        "residual telemetry is generated for apply-mode safety review only."
    )
    return profile


def _candidate_set_spec(*, profile_json: Path, residual_spec_json: Path, tag_suffix: str) -> dict[str, Any]:
    return {
        "protocol_id": f"gpcr_scaleup_100k_core_decoy_intrusion_{tag_suffix}",
        "protocol_title": "GPCR Core-Decoy Intrusion 100k Candidate",
        "protocol_version": "v1",
        "global_governance": {
            "comparison_kind": "gpcr_core_decoy_intrusion_100k_candidate",
            "prototype_spec_json": str(residual_spec_json.resolve()),
            "prototype_mode": "shadow_only",
            "family_scope": ["gpcr"],
            "router_promotion_allowed": False,
        },
        "sets": [
            {
                "set_id": "set1_core_blind",
                "title": "Core Blind Set",
                "purpose": "GPCR core full 100k shadow-only residual candidate for core-decoy intrusion review.",
                "claim_role": "primary",
                "preregistered_claim": (
                    "Operational 100k candidate for GPCR core-decoy intrusion analysis; not a router-promotion claim."
                ),
                "tasks": [
                    {
                        "task_id": "gpcr_core_full",
                        "domain": "gpcr",
                        "kind": "ligand_stress",
                        "profile_json": str(profile_json.resolve()),
                        "ligand_sizes": "100000",
                        "date_tag_suffix": f"gpcr-core-full-{tag_suffix}",
                    }
                ],
            }
        ],
    }


def build_payload(
    *,
    out_dir: str | Path,
    spec_json: str | Path,
    base_profile_json: str | Path,
    tag_suffix: str = DEFAULT_TAG_SUFFIX,
    generate_missing_spec: bool = True,
) -> dict[str, Any]:
    out_root = _resolve(out_dir)
    residual_spec_path = _resolve(spec_json)
    base_profile_path = _resolve(base_profile_json)
    if generate_missing_spec:
        ensure_intrusion_spec(residual_spec_path)

    residual_spec = _read_json(residual_spec_path)
    _validate_intrusion_spec(residual_spec, residual_spec_path)
    base_profile = _read_json(base_profile_path)

    profile_path = out_root / "profiles" / f"{base_profile_path.stem}_{tag_suffix}.json"
    set_spec_path = out_root / "specs" / f"gpcr_scaleup_100k_core_decoy_intrusion_{tag_suffix}.json"
    profile = _candidate_profile(base_profile, residual_spec_json=residual_spec_path)
    set_spec = _candidate_set_spec(profile_json=profile_path, residual_spec_json=residual_spec_path, tag_suffix=tag_suffix)
    _write_json(profile_path, profile)
    _write_json(set_spec_path, set_spec)

    return {
        "candidate_kind": "gpcr_core_decoy_intrusion_100k",
        "residual_prototype_mode": "shadow_only",
        "router_promotion_allowed": False,
        "base_profile_json": str(base_profile_path.resolve()),
        "residual_prototype_spec_json": str(residual_spec_path.resolve()),
        "profile_json": str(profile_path.resolve()),
        "set_spec_json": str(set_spec_path.resolve()),
        "run_command": (
            "python3 tools/run_external_validation_blind_sets.py "
            f"--set-spec-json {_rel_or_abs(set_spec_path)} --sets set1_core_blind"
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPCR core-decoy intrusion 100k candidate profile and set-spec JSON.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--spec-json", default=DEFAULT_SPEC_JSON)
    parser.add_argument("--base-profile-json", default=DEFAULT_BASE_PROFILE_JSON)
    parser.add_argument("--tag-suffix", default=DEFAULT_TAG_SUFFIX)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(
        out_dir=args.out_dir,
        spec_json=args.spec_json,
        base_profile_json=args.base_profile_json,
        tag_suffix=args.tag_suffix,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
