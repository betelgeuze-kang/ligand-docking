#!/usr/bin/env python3
"""Audit refine-tier physics wiring readiness (WS5 partial, Tier α science)."""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ENGINE_CONFIG = "config/ligand_engine_production.json"
DEFAULT_OUT_JSON = "runs/engine_refinement_tier_readiness_current.json"

CLAIM_BOUNDARY = (
    "Engine refinement tier readiness only; it verifies internal refine-tier modules and HTVS stage3b "
    "policy wiring. It is not an OpenMM/Schrödinger-grade accuracy claim."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _module_importable(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def build_engine_refinement_tier_readiness(*, engine_config: str = DEFAULT_ENGINE_CONFIG) -> dict[str, Any]:
    from tools.product.engine_refinement_config import load_engine_refinement_config

    cfg = load_engine_refinement_config(_resolve(engine_config))
    stage3 = cfg.get("stage3") if isinstance(cfg.get("stage3"), dict) else {}
    stage3b = cfg.get("stage3b") if isinstance(cfg.get("stage3b"), dict) else {}

    checks: list[dict[str, Any]] = []
    checks.append(
        {
            "check_id": "refine_tier_cascade_enabled",
            "status": "pass" if stage3.get("refine_tier_cascade") is True else "blocked",
            "detail": f"refine_tier_cascade={stage3.get('refine_tier_cascade')}",
        }
    )
    checks.append(
        {
            "check_id": "stage3b_physics_refinement_enabled",
            "status": "pass" if stage3b.get("run_physics_refinement") is True else "blocked",
            "detail": f"run_physics_refinement={stage3b.get('run_physics_refinement')}",
        }
    )
    checks.append(
        {
            "check_id": "stage3b_refined_energy_col",
            "status": "pass" if stage3b.get("physics_refinement_refined_energy_col") == "deltaG_mm_gbsa_kcal_mol" else "blocked",
            "detail": str(stage3b.get("physics_refinement_refined_energy_col")),
        }
    )
    for module_name in (
        "core.refine_physics",
        "core.mm_gbsa",
        "core.allatom_forcefield",
        "core.pocket_detection",
        "core.pose_generation",
    ):
        ok = _module_importable(module_name)
        checks.append({"check_id": f"module_{module_name}", "status": "pass" if ok else "blocked", "detail": module_name})

    script_checks = (
        "tools/run_ligand_physics_refinement.py",
        "tools/run_ligand_backmapping_scoring.py",
        "tools/product/engine_refinement_config.py",
    )
    for rel in script_checks:
        ok = _resolve(rel).is_file()
        checks.append({"check_id": f"script_{Path(rel).name}", "status": "pass" if ok else "blocked", "detail": rel})

    blocked = [item for item in checks if item["status"] != "pass"]
    ready = not blocked
    return {
        "summary": {
            "packet_type": "engine_refinement_tier_readiness",
            "status": "engine_refinement_tier_ready" if ready else "blocked_engine_refinement_tier_readiness",
            "engine_refinement_tier_ready": ready,
            "refine_tier": stage3b.get("physics_refinement_mode", "implicit_gb_sa_v1"),
            "refined_energy_col": stage3b.get("physics_refinement_refined_energy_col"),
            "check_count": len(checks),
            "pass_count": len(checks) - len(blocked),
            "blocked_count": len(blocked),
            "claim_boundary": CLAIM_BOUNDARY,
        },
        "checks": checks,
        "engine_config_path": engine_config,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build engine refinement tier readiness gate.")
    parser.add_argument("--engine-config", default=DEFAULT_ENGINE_CONFIG)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    args = parser.parse_args(argv)
    payload = build_engine_refinement_tier_readiness(engine_config=args.engine_config)
    out = _resolve(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
