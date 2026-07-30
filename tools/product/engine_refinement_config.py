"""Load production engine refinement defaults for HTVS/backmapping/trajectory."""

from __future__ import annotations

import copy
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
        "physics_refinement_base_proxy_col": "binding_energy_mmpbsa_kcal_mol_proxy",
        "physics_refinement_refined_energy_col": "deltaG_mm_gbsa_kcal_mol",
        "physics_refinement_topk_global": 32,
        "physics_refinement_topk_per_target": 8,
        "physics_refinement_selection_mode": "union",
        "physics_refinement_use_refined_scores_downstream": True,
        "physics_refinement_use_refined_proxy_for_calibration": True,
        "pocketmd_eligible_families": "gpcr,kinase,ion_channel",
        "pocketmd_rank_threshold_pct": 0.05,
        "pocketmd_max_per_target": 8,
        "pocketmd_max_per_job": 32,
        "pocketmd_cost_budget": 32.0,
        "pocketmd_unit_cost": 1.0,
        "pocketmd_cost_unit": "normalized_refinement_unit",
        "pocketmd_cost_col": "",
        "pocketmd_family_col": "family",
    },
}


def builtin_engine_refinement_config() -> dict[str, Any]:
    """Return an isolated copy of the deterministic built-in fallback."""

    return copy.deepcopy(_BUILTIN_DEFAULTS)


def load_engine_refinement_config(path: str | Path | None = None) -> dict[str, Any]:
    explicit_path = bool(str(path or "").strip())
    config_path = Path(path) if explicit_path else DEFAULT_CONFIG_PATH
    payload = builtin_engine_refinement_config()
    if not config_path.exists():
        if explicit_path:
            raise FileNotFoundError(
                f"engine refinement config not found: {config_path}"
            )
        return payload
    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(
            f"engine refinement config unreadable: {config_path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"engine refinement config is invalid JSON: {config_path}"
        ) from exc
    if not isinstance(loaded, dict):
        raise ValueError("engine refinement config must be a JSON object")
    for key in ("stage2", "stage3", "stage3b"):
        if key not in loaded:
            continue
        section = loaded[key]
        if not isinstance(section, dict):
            raise ValueError(f"engine refinement config section must be an object: {key}")
        payload[key].update(section)
    for key in ("version", "description", "claim_boundary"):
        if key in loaded:
            payload[key] = loaded[key]
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
