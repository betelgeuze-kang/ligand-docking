"""Load production engine refinement defaults for HTVS/backmapping/trajectory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "config" / "ligand_engine_production.json"

_BUILTIN_DEFAULTS: dict[str, Any] = {
    "version": "ligand_engine_production_v1",
    "stage2": {
        "multi_start_count": 3,
        "pocket_protein_max_atoms": 256,
        "prod_mode": True,
        "prod_early_stop": True,
        "require_rust_hip": True,
        "cross_docking_pose_seed": True,
    },
    "stage3": {
        "ligand_model_default": "auto",
        "onsps_4bead_cascade": True,
        "residual_assist_mode": "assist",
        "hbond_onsps_weight": 1.0,
        "two_pass_scoring": True,
        "two_pass_topk_pct": 0.05,
        "refine_tier_cascade": True,
    },
    "stage3b": {
        "run_physics_refinement": True,
        "physics_refinement_mode": "implicit_gb_sa_v1",
        "physics_refinement_backend": "internal_gb_sa_v1",
        "physics_refinement_refined_energy_col": "internal_refine_proxy_score",
        "physics_refinement_use_refined_scores_downstream": True,
        "physics_refinement_use_refined_proxy_for_calibration": True,
    },
}


def load_engine_refinement_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    payload: dict[str, Any] = dict(_BUILTIN_DEFAULTS)
    if config_path.exists():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                for key in ("stage2", "stage3", "stage3b"):
                    section = loaded.get(key, {})
                    if isinstance(section, dict):
                        payload.setdefault(key, {})
                        payload[key].update(section)
                for key in ("version", "description", "claim_boundary"):
                    if key in loaded:
                        payload[key] = loaded[key]
        except (OSError, json.JSONDecodeError):
            pass
    return payload


def stage2_defaults(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_engine_refinement_config()
    section = cfg.get("stage2", {})
    return section if isinstance(section, dict) else {}


def stage3_defaults(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_engine_refinement_config()
    section = cfg.get("stage3", {})
    return section if isinstance(section, dict) else {}


def stage3b_defaults(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_engine_refinement_config()
    section = cfg.get("stage3b", {})
    return section if isinstance(section, dict) else {}
