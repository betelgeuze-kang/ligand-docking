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
from tools.product.engine_refinement_config import load_engine_refinement_config, stage3_defaults, stage3b_defaults
from tools.product.stage2_skip_router import apply_stage2_skip_router, route_stage2_candidate
from tools.run_ligand_backmapping_scoring import _resolve_ligand_model_for_row
from tools.run_ligand_htvs_pipeline import _apply_engine_refinement_defaults, build_parser


def test_engine_refinement_config_loads_stage3_defaults():
    cfg = load_engine_refinement_config()
    s3 = stage3_defaults(cfg)
    assert s3.get("ligand_model_default") == "auto"
    assert bool(s3.get("onsps_4bead_cascade")) is True
    assert bool(s3.get("two_pass_scoring")) is True
    assert bool(s3.get("refine_tier_cascade")) is True


def test_engine_refinement_config_loads_stage3b_defaults():
    cfg = load_engine_refinement_config()
    s3b = stage3b_defaults(cfg)
    assert bool(s3b.get("run_physics_refinement")) is True
    assert s3b.get("physics_refinement_backend") == "internal_gb_sa_v1"
    assert s3b.get("physics_refinement_refined_energy_col") == "deltaG_mm_gbsa_kcal_mol"


def test_apply_engine_refinement_defaults_enables_refine_tier_cascade():
    args = build_parser().parse_args([])
    meta = _apply_engine_refinement_defaults(args, load_engine_refinement_config())
    assert meta["applied"] is True
    assert bool(getattr(args, "run_physics_refinement")) is True
    assert getattr(args, "physics_refinement_backend") == "internal_gb_sa_v1"
    assert bool(getattr(args, "traj_cross_docking_pose_seed")) is True
    assert getattr(args, "calibration_proxy_col") == "deltaG_mm_gbsa_kcal_mol"


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


def test_topo_corrector_uses_measured_geometry_not_synthetic_only():
    from core.topo_corrector import summarize_topo_correction

    meta = {
        "site_count": 2,
        "onsps_min_distances": [2.1, 2.4],
        "onsps_angle_scores": [0.82, 0.77],
        "roles": ["donor", "acceptor"],
    }
    out = summarize_topo_correction(meta, score_2bead=-5.0, score_4bead=-5.8)
    assert out["delta_backmap"] == pytest.approx(-0.8)
    assert out["topo_feature_dim"] == 18


def test_stage2_skip_inline_manifest_and_merge(tmp_path: Path):
    from tools.product.merge_stage2_manifests import merge_stage2_manifests
    from tools.product.stage2_skip_inline_scorer import build_skip_inline_manifest

    skipped = [
        {
            "queue_id": "skip-1",
            "target": "ADRB2",
            "ligand_id": "lig-1",
            "ligand_smiles": "CCO",
            "stage2_route_decision": "skip_stage2_inline_score",
            "stage2_skip_applied": True,
        }
    ]
    skip_csv = tmp_path / "skip_manifest.csv"
    skip_meta = build_skip_inline_manifest(skipped, out_csv=str(skip_csv))
    assert skip_meta["skip_row_count"] == 1
    traj_csv = tmp_path / "traj_manifest.csv"
    pd.DataFrame(
        [
            {
                "queue_id": "traj-1",
                "binding_energy_proxy": -4.0,
                "trajectory_frames": 120,
            }
        ]
    ).to_csv(traj_csv, index=False)
    merged_csv = tmp_path / "merged_manifest.csv"
    merged = merge_stage2_manifests(str(traj_csv), str(skip_csv), out_csv=str(merged_csv))
    merged_df = pd.read_csv(merged["merged_manifest_csv"])
    assert set(merged_df["queue_id"].astype(str)) == {"traj-1", "skip-1"}


def test_sync_ledger_from_simulation_result(tmp_path: Path):
    from api.docking_dispatch import sync_ledger_from_simulation_result
    from betelgeuze_product.job_orchestration import read_job_record

    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir()
    record = {"job_id": "dock-sync-1", "status": "accepted_fail_closed"}
    (jobs_dir / "dock-sync-1.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    out = sync_ledger_from_simulation_result(
        jobs_dir,
        "dock-sync-1",
        status="completed",
        result_file="/tmp/result.json",
        worker_id="test-worker",
    )
    assert out.get("synced") is True
    ledger = read_job_record(jobs_dir, "dock-sync-1")
    assert ledger.get("simulation_sync_status") == "completed"
    assert ledger.get("worker_state") == "completed_fail_closed"


def test_materialize_from_docking_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from api.config import settings
    from tools.product.materialize_docking_htvs_request import materialize_from_docking_request

    jobs_dir = tmp_path / "product_docking_jobs"
    jobs_dir.mkdir()
    monkeypatch.setattr(settings, "results_storage_path", str(tmp_path / "results"))
    ledger = {
        "job_id": "dock-mat-1",
        "intake_payload": {
            "family": "gpcr",
            "target_id": "ADRB2",
            "ligands": [{"compound_id": "cmp-1", "smiles": "CCO"}],
        },
    }
    (jobs_dir / "dock-mat-1.json").write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    request = {
        "job_id": "sim-1",
        "target_name": "ADRB2",
        "runner_profile_params": {"docking_job_id": "dock-mat-1"},
    }
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    out = materialize_from_docking_request(str(request_path), out_dir=str(tmp_path / "mat"))
    assert out["ligand_count"] == 1
    queue_df = pd.read_csv(out["queue_csv"])
    assert len(queue_df) == 1
    assert str(queue_df.iloc[0]["target"]) == "ADRB2"


def test_four_bead_gate_evaluator_pass_and_fail():
    from tools.product.four_bead_gate_evaluator import evaluate_four_bead_gate

    ok_df = pd.DataFrame(
        [
            {
                "ligand_model_pass2": "4bead_onsps_hbond",
                "score_2bead": -6.0,
                "score_4bead": -6.5,
                "topo_correction_delta": 0.2,
                "onsps_angle_scores": "[0.8, 0.7]",
            }
        ]
    )
    ok = evaluate_four_bead_gate(ok_df, enabled=True, delta_backmap_max=2.5)
    assert ok["pass"] is True
    bad_df = pd.DataFrame(
        [
            {
                "ligand_model_pass2": "4bead_onsps_hbond",
                "score_2bead": -6.0,
                "score_4bead": -1.0,
                "topo_correction_delta": 2.0,
                "onsps_angle_scores": "[0.8, 0.7]",
            }
        ]
    )
    bad = evaluate_four_bead_gate(bad_df, enabled=True, delta_backmap_max=2.5, no_pass_to_fail_vs_2bead=True)
    assert bad["pass"] is False
    assert bad["pass_to_fail_regression_count"] >= 1


def test_force_residual_shortlist_hook_applies_to_top_fraction():
    from tools.product.force_residual_shortlist_hook import apply_force_residual_shortlist_hook

    rep = np.asarray([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], dtype=np.float32)
    df = pd.DataFrame(
        [
            {"queue_id": "a", "binding_score_composite_v7": 1.0, "representative_ligand_xyz": rep},
            {"queue_id": "b", "binding_score_composite_v7": 5.0, "representative_ligand_xyz": rep},
        ]
    )
    out, meta = apply_force_residual_shortlist_hook(df, top_k_fraction=0.5)
    assert meta["applied"] is True
    assert bool(out.loc[out["queue_id"] == "a", "force_residual_applied"].iloc[0]) is True


def test_stage2_skip_router_exposes_skipped_rows():
    rows = [
        {"family": "gpcr", "affinity_hint": 0.0, "prior_rank_proxy": 0.95},
        {"family": "gpcr", "affinity_hint": 0.8, "prior_rank_proxy": 0.05},
    ]
    traj_rows, summary = apply_stage2_skip_router(rows, family="gpcr")
    assert len(summary.get("skipped_rows", [])) >= 1
    assert len(summary.get("routed_rows", [])) == 2
    assert len(traj_rows) >= 1


def test_materialize_backmapping_from_docking_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from api.config import settings
    from tools.product.materialize_docking_backmapping_request import materialize_from_docking_request

    jobs_dir = tmp_path / "product_docking_jobs"
    jobs_dir.mkdir()
    monkeypatch.setattr(settings, "results_storage_path", str(tmp_path / "results"))
    ledger = {
        "job_id": "dock-bm-1",
        "intake_payload": {
            "family": "gpcr",
            "target_id": "ADRB2",
            "ligands": [{"compound_id": "cmp-1", "smiles": "CCO"}],
        },
    }
    (jobs_dir / "dock-bm-1.json").write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "job_id": "sim-bm-1",
                "target_name": "ADRB2",
                "runner_profile_params": {"docking_job_id": "dock-bm-1"},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    out = materialize_from_docking_request(str(request_path), out_dir=str(tmp_path / "bm"))
    assert out["ligand_count"] == 1
    assert Path(out["queue_csv"]).exists()


def test_docking_request_records_execution_approval_posture():
    from betelgeuze_product.docking_request import build_docking_job_record

    record = build_docking_job_record(
        {
            "request_type": "structure_analysis_ligand_docking",
            "family": "gpcr",
            "target_id": "ADRB2",
            "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
            "ligands": [{"ligand_id": "lig_1", "smiles": "CCO"}],
        },
        job_id="job_exec_gate",
    )
    assert record["execution_enabled"] is False
    assert record["execution_approval_gate_ready"] in {True, False}
    assert record["execution_approval_token_required"] == "APPROVE_PRODUCT_DOCKING_EXECUTION"
    assert record["execution_enabled_conditional_would_enable"] in {True, False}


def test_enabled_topk_runner_profile_exists():
    path = Path("config/api_validated_runner_profiles/ligand_topk_delivery.production.json")
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload.get("enabled") is True
    assert payload.get("runner_script") == "tools/run_ligand_topk_delivery.py"


def test_build_simulate_request_includes_intake_payload():
    record = {
        "job_id": "dock-2",
        "target_id": "ADRB2",
        "family": "gpcr",
        "request_sha256": "abc",
        "ligand_count": 1,
        "structure_source_kind": "pdb_id",
        "intake_payload": {"ligands": [{"compound_id": "x", "smiles": "CCO"}]},
        "engine_dispatch_manifest": {"runner_profile_id": "ligand_htvs_pipeline_default"},
    }
    req = build_simulate_request(record)
    params = req["runner_profile_params"]
    assert params["docking_job_id"] == "dock-2"
    assert len(params.get("ligands", [])) == 1
    assert params.get("intake_payload", {}).get("ligands")
