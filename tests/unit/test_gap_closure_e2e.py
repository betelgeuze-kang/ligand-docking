from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from api.docking_dispatch import (
    build_simulate_request,
    dispatch_docking_job_if_eligible,
    is_dispatch_eligible,
)
from core.score_residual import apply_score_residual
from tools.product.engine_refinement_config import load_engine_refinement_config, stage3_defaults
from tools.product.stage2_skip_router import apply_stage2_skip_router, route_stage2_candidate
from tools.run_ligand_backmapping_scoring import _resolve_ligand_model_for_row


def test_engine_refinement_config_loads_stage3_defaults():
    cfg = load_engine_refinement_config()
    s3 = stage3_defaults(cfg)
    assert s3.get("ligand_model_default") == "auto"
    assert bool(s3.get("onsps_4bead_cascade")) is True
    assert bool(s3.get("two_pass_scoring")) is True


def test_resolve_ligand_model_auto_and_rank_pct():
    polar_family = {"ligand_smiles": "CCO", "family": "gpcr"}
    assert _resolve_ligand_model_for_row(polar_family, "auto", rank_pct=1.0) == "4bead_onsps_hbond"
    generic = {"ligand_smiles": "CCO", "family": ""}
    assert (
        _resolve_ligand_model_for_row(generic, "auto", rank_pct=0.10, onsps_4bead_cascade=True)
        == "2bead"
    )
    assert (
        _resolve_ligand_model_for_row(generic, "auto", rank_pct=0.03, onsps_4bead_cascade=True)
        == "4bead_onsps_hbond"
    )


def test_production_guarded_residual_abstains_on_yellow_band():
    out = apply_score_residual(
        1.0,
        family="gpcr",
        prior_pressure=0.8,
        structural_weakness=0.9,
        mode="production_guarded",
        max_abs_delta=1.5,
    )
    if out["residual_band"] == "yellow":
        assert out["status"] == "production_guarded_abstained"
        assert out["active_score"] == pytest.approx(1.0)


def test_stage2_skip_router_decisions():
    skip = route_stage2_candidate(family="gpcr", affinity_hint=0.0, prior_rank_proxy=0.9)
    assert skip["stage2_route_decision"] == "skip_stage2_inline_score"
    full = route_stage2_candidate(family="gpcr", affinity_hint=0.5, prior_rank_proxy=0.05)
    assert full["stage2_route_decision"] == "full_stage2_trajectory"


def test_stage2_skip_router_batch_summary():
    rows = [
        {"family": "gpcr", "affinity_hint": 0.0, "prior_rank_proxy": 0.95},
        {"family": "gpcr", "affinity_hint": 0.8, "prior_rank_proxy": 0.05},
    ]
    traj_rows, summary = apply_stage2_skip_router(rows, family="gpcr")
    assert summary["row_count"] == 2
    assert summary["stage2_skip_count"] >= 1
    assert len(traj_rows) >= 1


def test_blind_4bead_gate_config_exists():
    path = Path("config/ligand_htvs_blind_gpcr_adrb2_4bead_v1.json")
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    gate = payload.get("gate", {})
    assert gate.get("four_bead_cascade_enabled") is True
    assert float(gate.get("four_bead_delta_backmap_max", 0.0)) > 0.0


def test_enabled_runner_profiles_exist():
    htvs = Path("config/api_validated_runner_profiles/ligand_htvs_pipeline_default.json")
    backmap = Path("config/api_validated_runner_profiles/backmapping_scoring.production.json")
    assert htvs.exists() and backmap.exists()
    htvs_payload = json.loads(htvs.read_text(encoding="utf-8"))
    backmap_payload = json.loads(backmap.read_text(encoding="utf-8"))
    assert htvs_payload.get("enabled") is True
    assert backmap_payload.get("enabled") is True


def test_docking_dispatch_build_request():
    record = {
        "job_id": "dock-1",
        "target_id": "ADRB2",
        "family": "gpcr",
        "request_sha256": "abc",
        "ligand_count": 3,
        "structure_source_kind": "pdb_id",
        "engine_dispatch_manifest": {"runner_profile_id": "ligand_htvs_pipeline_default"},
    }
    req = build_simulate_request(record)
    assert req["runner_profile_id"] == "ligand_htvs_pipeline_default"
    assert req["target_name"] == "ADRB2"


def test_docking_dispatch_eligibility_fail_closed_without_runner_env(monkeypatch: pytest.MonkeyPatch):
    from api.config import settings

    monkeypatch.setattr(settings, "api_validated_runner_enabled", False)
    record = {
        "status": "accepted_fail_closed",
        "queue_status": "queued_fail_closed",
        "validation_status": "pass",
        "engine_dispatch_ready": True,
        "scope_claim_allowed_for_request": True,
        "engine_dispatch_manifest": {"runner_profile_id": "ligand_htvs_pipeline_default"},
    }
    eligible, reason = is_dispatch_eligible(record)
    assert eligible is False
    assert reason == "api_validated_runner_disabled"


def test_docking_dispatch_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from api.config import settings
    from api.job_store import SQLiteJobStore
    from betelgeuze_product.job_orchestration import read_job_record

    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    for name in ("ligand_htvs_pipeline_default", "backmapping_scoring.production"):
        src = Path(f"config/api_validated_runner_profiles/{name}.json")
        (profiles_dir / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        evidence_src = Path(
            f"config/api_validated_runner_profiles/evidence/{name}.evidence.json"
        )
        evidence_dst = profiles_dir / "evidence"
        evidence_dst.mkdir(exist_ok=True)
        (evidence_dst / evidence_src.name).write_text(
            evidence_src.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        profile = json.loads((profiles_dir / src.name).read_text(encoding="utf-8"))
        profile["production_readiness"]["evidence_artifact"] = str(
            evidence_dst / evidence_src.name
        )
        (profiles_dir / src.name).write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8")

    jobs_dir = tmp_path / "docking_jobs"
    jobs_dir.mkdir()
    store_path = tmp_path / "jobs.sqlite3"
    monkeypatch.setattr(settings, "api_validated_runner_enabled", True)
    monkeypatch.setattr(settings, "api_validated_runner_profiles_path", str(profiles_dir))
    monkeypatch.setattr(settings, "api_job_store_path", str(store_path))

    record = {
        "job_id": "dock-dispatch-1",
        "status": "accepted_fail_closed",
        "queue_status": "queued_fail_closed",
        "validation_status": "pass",
        "engine_dispatch_ready": True,
        "scope_claim_allowed_for_request": True,
        "target_id": "ADRB2",
        "family": "gpcr",
        "request_sha256": "sha",
        "ligand_count": 2,
        "structure_source_kind": "pdb_id",
        "engine_dispatch_manifest": {"runner_profile_id": "ligand_htvs_pipeline_default"},
    }
    (jobs_dir / "dock-dispatch-1.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    outcome = dispatch_docking_job_if_eligible(
        record,
        jobs_dir=jobs_dir,
        store=SQLiteJobStore(store_path),
    )
    assert outcome.get("dispatched") is True
    ledger = read_job_record(jobs_dir, "dock-dispatch-1")
    assert ledger.get("worker_dispatch_enqueued") is True
