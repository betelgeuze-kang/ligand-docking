from pathlib import Path
import argparse
import copy
import hashlib
import json

import pandas as pd

from betelgeuze_engine.product.selection_score_authority import SelectionScoreAuthority
from betelgeuze_engine.product.implementation_provenance import (
    ImplementationProvenanceError,
    build_implementation_source_manifest,
    validate_implementation_source_manifest,
)
from tools.product.engine_refinement_config import (
    builtin_engine_refinement_config,
    load_engine_refinement_config,
)
from tools import generate_ligand_trajectory_engine as traj_engine
from tools import run_ligand_htvs_pipeline as mod


def _current_engine_config_provenance() -> dict:
    path = Path("config/ligand_engine_production.json").resolve()
    resolved_config = load_engine_refinement_config(path)
    return {
        "schema_version": "ligand_engine_runtime_config_v1",
        "source_kind": "file",
        "requested_path": "config/ligand_engine_production.json",
        "resolved_path": str(path),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "resolved_config": resolved_config,
        "resolved_config_sha256": hashlib.sha256(
            json.dumps(
                resolved_config,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest(),
    }


def _traj_stage2_args_namespace(**overrides):
    base = dict(
        traj_frames_smoke=120,
        traj_frames_full=300,
        traj_job_batch_autotune_candidates="1,2,4,8",
        traj_writer_workers=1,
        traj_writer_max_pending=64,
        traj_dynamic_adress_min_affinity=0.78,
        traj_dynamic_adress_max_protein_residues=200,
        traj_dynamic_adress_fraction=0.15,
        traj_dynamic_adress_base_radius_A=6.0,
        traj_dynamic_adress_affinity_radius_scale=3.0,
        traj_dynamic_adress_mw_radius_scale=2.5,
        traj_dynamic_adress_max_all_atom_radius_A=8.0,
        traj_dynamic_adress_max_atom_ratio=0.10,
        traj_prod_stage2_preset="off",
        traj_prod_stage2_preset_strict=False,
        traj_prod_profile_intent="",
        targets="",
        target_native_csv="",
        leakage_target_meta_csv="",
        out_prefix="runs/demo",
        traj_prod_speedpack=False,
        traj_prod_adaptive_frame_budget=True,
        traj_prod_frame_budget_tiers="0.90:1.00,0.75:0.85,0.60:0.70,0.00:0.55",
        traj_prod_min_frames_smoke=80,
        traj_prod_min_frames_full=160,
        traj_prod_early_stop_enabled=False,
        traj_prod_early_stop_min_frames_smoke=80,
        traj_prod_early_stop_min_frames_full=160,
        traj_prod_early_stop_window=12,
        traj_prod_early_stop_contact_drift=0.015,
        traj_prod_early_stop_min_distance_drift_A=0.12,
        traj_prod_early_stop_max_mean_min_distance_A=6.0,
        traj_prod_light_artifacts=True,
        traj_prod_light_progress_every_jobs=250,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def test_resolve_heavy_artifact_paths_explicit_root(tmp_path: Path):
    root = tmp_path / "heavy"
    resolved = mod._resolve_heavy_artifact_paths(
        out_prefix="runs/demo_run",
        heavy_root=str(root),
        subdir="",
        auto_mount=False,
    )
    assert bool(resolved["enabled"]) is True
    assert str(resolved["root"]) == str(root)
    assert Path(resolved["stage2_trajectory_root"]).exists()
    assert Path(resolved["stage3_delivery_dir"]).exists()


def test_stage3_hbond_evidence_is_embedded_with_child_result_hash(tmp_path: Path):
    stage3_summary_path = tmp_path / "stage3_summary.json"
    stage3_summary = {
        "hbond_evidence_summary": {
            "schema_version": "hbond_evidence_v1",
            "status": "pass",
        },
        "topk": [
            {
                "queue_id": "ADRB2__lig1__rep0001",
                "hbond_evidence": {"schema_version": "hbond_evidence_v1"},
            }
        ],
    }
    stage3_summary_path.write_text(
        json.dumps(stage3_summary, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    fields = mod._stage3_hbond_evidence_fields(
        stage3_summary,
        str(stage3_summary_path),
        hashlib.sha256(stage3_summary_path.read_bytes()).hexdigest(),
    )

    assert fields["hbond_evidence_summary"] == stage3_summary[
        "hbond_evidence_summary"
    ]
    assert fields["hbond_evidence_candidates"] == stage3_summary["topk"]
    assert fields["hbond_evidence_source"]["source_kind"] == (
        "htvs_stage3_backmapping_result"
    )
    assert fields["hbond_evidence_source"]["result_file_sha256"] == hashlib.sha256(
        stage3_summary_path.read_bytes()
    ).hexdigest()


def test_finalize_preserves_runtime_selection_authority_on_post_stage3_failure(
    tmp_path: Path,
    monkeypatch,
):
    authority = SelectionScoreAuthority.create(
        score_column="binding_score_composite_v7",
        score_direction="ascending",
    ).to_dict()
    args = argparse.Namespace(
        _selection_score_authority=authority,
        service_error_codes_json="config/ligand_service_error_codes_v1.json",
        service_retry_after_sec_transient=30,
        service_retry_after_sec_default=0,
        service_schema_version="ligand_htvs_service_v1",
        data_contract_json="",
        evidence_bundle="",
        docking_request_json="",
    )
    monkeypatch.setattr(mod, "_write_closeout_latest", None)

    out = mod._finalize_and_write(
        str(tmp_path / "post_stage3_failure"),
        {"pass": False, "failed_stage": "stage4_calibration", "stages": {}},
        args,
    )

    assert out["selection_score_authority"] == authority
    implementation = validate_implementation_source_manifest(
        out["implementation_source_manifest"]
    )
    assert out["implementation_fingerprint_sha256"] == implementation[
        "manifest_sha256"
    ]


def test_finalize_rejects_mismatched_physics_implementation(tmp_path: Path, monkeypatch):
    args = argparse.Namespace(
        _selection_score_authority={},
        service_error_codes_json="config/ligand_service_error_codes_v1.json",
        service_retry_after_sec_transient=30,
        service_retry_after_sec_default=0,
        service_schema_version="ligand_htvs_service_v1",
        data_contract_json="",
        evidence_bundle="",
        docking_request_json="",
    )
    monkeypatch.setattr(mod, "_write_closeout_latest", None)

    out = mod._finalize_and_write(
        str(tmp_path / "implementation_mismatch"),
        {
            "pass": True,
            "failed_stage": "",
            "physics_refinement": {
                "enabled": True,
                "implementation_fingerprint_sha256": "0" * 64,
            },
        },
        args,
    )

    assert out["pass"] is False
    assert out["failed_stage"] == "stage3b_implementation_provenance"
    assert out["service_result"]["status"] == "error"


def test_finalize_rejects_malformed_child_manifest_with_matching_fingerprint(
    tmp_path: Path,
    monkeypatch,
):
    implementation = build_implementation_source_manifest()
    args = argparse.Namespace(
        _selection_score_authority={},
        service_error_codes_json="config/ligand_service_error_codes_v1.json",
        service_retry_after_sec_transient=30,
        service_retry_after_sec_default=0,
        service_schema_version="ligand_htvs_service_v1",
        data_contract_json="",
        evidence_bundle="",
        docking_request_json="",
    )
    monkeypatch.setattr(mod, "_write_closeout_latest", None)

    out = mod._finalize_and_write(
        str(tmp_path / "malformed_child_manifest"),
        {
            "pass": True,
            "failed_stage": "",
            "physics_refinement": {
                "enabled": True,
                "implementation_source_manifest": {},
                "implementation_fingerprint_sha256": implementation[
                    "manifest_sha256"
                ],
            },
        },
        args,
    )

    assert out["pass"] is False
    assert out["failed_stage"] == "stage3b_implementation_provenance"
    assert "invalid physics refinement implementation manifest" in out[
        "physics_refinement"
    ]["implementation_provenance_error"]


def test_finalize_rejects_source_drift_after_startup_snapshot(
    tmp_path: Path,
    monkeypatch,
):
    implementation = build_implementation_source_manifest()
    drifted = copy.deepcopy(implementation)
    drifted["manifest_sha256"] = "0" * 64
    evidence_bundle = tmp_path / "source_drift_evidence.json"
    args = argparse.Namespace(
        _implementation_source_manifest=implementation,
        _engine_refinement_config_provenance=(
            _current_engine_config_provenance()
        ),
        _selection_score_authority={},
        service_error_codes_json="config/ligand_service_error_codes_v1.json",
        service_retry_after_sec_transient=30,
        service_retry_after_sec_default=0,
        service_schema_version="ligand_htvs_service_v1",
        data_contract_json="",
        evidence_bundle=str(evidence_bundle),
        docking_request_json="",
    )
    monkeypatch.setattr(
        mod,
        "build_implementation_source_manifest",
        lambda: drifted,
    )
    monkeypatch.setattr(mod, "_write_closeout_latest", None)

    out = mod._finalize_and_write(
        str(tmp_path / "source_drift"),
        {"pass": True, "failed_stage": ""},
        args,
    )

    assert out["pass"] is False
    assert out["failed_stage"] == "implementation_source_drift"
    assert "changed after pipeline startup" in out[
        "implementation_provenance_error"
    ]
    assert out["implementation_source_manifest"] == implementation
    assert (tmp_path / "source_drift_summary.json").is_file()
    assert evidence_bundle.is_file()


def test_finalize_emits_drift_artifacts_when_current_manifest_cannot_build(
    tmp_path: Path,
    monkeypatch,
):
    implementation = build_implementation_source_manifest()
    evidence_bundle = tmp_path / "source_missing_evidence.json"
    args = argparse.Namespace(
        _implementation_source_manifest=implementation,
        _engine_refinement_config_provenance=(
            _current_engine_config_provenance()
        ),
        _selection_score_authority={},
        service_error_codes_json="config/ligand_service_error_codes_v1.json",
        service_retry_after_sec_transient=30,
        service_retry_after_sec_default=0,
        service_schema_version="ligand_htvs_service_v1",
        data_contract_json="",
        evidence_bundle=str(evidence_bundle),
        docking_request_json="",
    )

    def missing_source_manifest():
        raise ImplementationProvenanceError(
            "implementation source missing: covered.py"
        )

    monkeypatch.setattr(
        mod,
        "build_implementation_source_manifest",
        missing_source_manifest,
    )
    monkeypatch.setattr(mod, "_write_closeout_latest", None)

    out = mod._finalize_and_write(
        str(tmp_path / "source_missing"),
        {"pass": True, "failed_stage": ""},
        args,
    )

    assert out["pass"] is False
    assert out["failed_stage"] == "implementation_source_drift"
    assert "cannot be revalidated" in out["implementation_provenance_error"]
    assert (tmp_path / "source_missing_summary.json").is_file()
    assert evidence_bundle.is_file()


def test_failed_config_resolution_still_emits_evidence_bundle(
    tmp_path: Path,
    monkeypatch,
):
    evidence_bundle = tmp_path / "failed_evidence.json"
    implementation = build_implementation_source_manifest()
    args = argparse.Namespace(
        _implementation_source_manifest=implementation,
        _selection_score_authority={},
        service_error_codes_json="config/ligand_service_error_codes_v1.json",
        service_retry_after_sec_transient=30,
        service_retry_after_sec_default=0,
        service_schema_version="ligand_htvs_service_v1",
        data_contract_json="",
        evidence_bundle=str(evidence_bundle),
        docking_request_json="",
    )
    monkeypatch.setattr(mod, "_write_closeout_latest", None)

    out = mod._finalize_and_write(
        str(tmp_path / "config_failure"),
        {
            "pass": False,
            "failed_stage": "engine_refinement_config",
            "engine_refinement_config": {
                "schema_version": "ligand_engine_runtime_config_v1",
                "source_kind": "resolution_error",
                "requested_path": str(tmp_path / "missing.json"),
                "error": "engine refinement config not found",
            },
        },
        args,
    )

    assert out["pass"] is False
    assert evidence_bundle.is_file()
    evidence = json.loads(evidence_bundle.read_text(encoding="utf-8"))
    assert evidence["verdict"]["verdict_label"] == "api_job_failed"
    assert evidence["source_hashes"]["config_hash"]


def test_default_config_absence_uses_builtin_provenance(
    tmp_path: Path,
    monkeypatch,
):
    args = mod.build_parser().parse_args(
        [
            "--out-prefix",
            str(tmp_path / "builtin_config"),
        ]
    )
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(
        mod,
        "load_engine_refinement_config",
        lambda _path=None: builtin_engine_refinement_config(),
    )
    monkeypatch.setattr(
        mod,
        "_acquire_instance_lock",
        lambda _path: {
            "ok": False,
            "lock_path": str(tmp_path / "occupied.lock"),
            "owner": "other",
            "fd": None,
        },
    )
    monkeypatch.setattr(mod, "_write_closeout_latest", None)

    out = mod.run_pipeline(args)

    assert out["failed_stage"] == "stage_lock"
    provenance = out["engine_refinement_config"]
    assert provenance["source_kind"] == "builtin_defaults"
    assert provenance["source_sha256"] == ""
    assert provenance["resolved_config"] == builtin_engine_refinement_config()


def test_validate_data_contract_input_detects_missing_column(tmp_path: Path):
    contract = tmp_path / "contract.json"
    ligand_csv = tmp_path / "ligands.csv"
    split_csv = tmp_path / "split.csv"
    labels_csv = tmp_path / "labels.csv"

    contract.write_text(
        """
{
  "input": {
    "ligand_csv_required_cols": ["target", "ligand_id", "is_binder"],
    "eval_split_csv_required_cols": ["target", "ligand_id", "role"],
    "ranking_labels_csv_required_cols": ["target", "ligand_id", "is_binder"]
  }
}
""".strip(),
        encoding="utf-8",
    )
    pd.DataFrame([{"target": "T1", "ligand_id": "L1"}]).to_csv(ligand_csv, index=False)  # is_binder missing
    pd.DataFrame([{"target": "T1", "ligand_id": "L1", "role": "eval"}]).to_csv(split_csv, index=False)
    pd.DataFrame([{"target": "T1", "ligand_id": "L1", "is_binder": 1}]).to_csv(labels_csv, index=False)

    args = argparse.Namespace(
        data_contract_json=str(contract),
        ligand_csv=str(ligand_csv),
        eval_split_csv=str(split_csv),
        ranking_labels_csv=str(labels_csv),
    )
    rep = mod._validate_data_contract_input(args)
    assert bool(rep["ok"]) is False
    assert any("ligand_csv missing columns" in e for e in rep["errors"])


def test_stage1_reuse_diagnostics_rejects_changed_split_and_ligand_inputs():
    args = argparse.Namespace(
        target_native_csv="config/native.csv",
        ligand_csv="config/repaired_reference.csv",
        leakage_ligand_meta_csv="config/repaired_meta.csv",
        eval_split_csv="config/repaired_split.csv",
        csv_smiles_cache_json="runs/repaired_cache.json",
    )
    old_stage1 = {
        "target_native_csv": "config/native.csv",
        "ligand_csv": "config/base_reference.csv",
        "ligand_meta_csv": "config/base_meta.csv",
        "target_ligand_csv": "config/base_split.csv",
        "csv_smiles_cache_json": "runs/base_cache.json",
        "target_ligand_roles": ["fit", "far_ood_eval"],
    }

    diag = mod._stage1_reuse_diagnostics(args, old_stage1, "fit,far_ood_eval")

    assert diag["ok"] is False
    fields = {row["field"] for row in diag["mismatches"]}
    assert {"ligand_csv", "ligand_meta_csv", "target_ligand_csv", "csv_smiles_cache_json"} <= fields


def test_stage1_reuse_diagnostics_accepts_matching_inputs():
    args = argparse.Namespace(
        target_native_csv="config/native.csv",
        ligand_csv="config/repaired_reference.csv",
        leakage_ligand_meta_csv="config/repaired_meta.csv",
        eval_split_csv="config/repaired_split.csv",
        csv_smiles_cache_json="runs/repaired_cache.json",
    )
    stage1 = {
        "target_native_csv": "config/native.csv",
        "ligand_csv": "config/repaired_reference.csv",
        "ligand_meta_csv": "config/repaired_meta.csv",
        "target_ligand_csv": "config/repaired_split.csv",
        "csv_smiles_cache_json": "runs/repaired_cache.json",
        "target_ligand_roles": ["fit", "far_ood_eval"],
    }

    diag = mod._stage1_reuse_diagnostics(args, stage1, "fit,far_ood_eval")

    assert diag["ok"] is True
    assert diag["mismatches"] == []


def test_build_claim_split_contains_both_domains():
    gate = {
        "pass": True,
        "ranking_unique_auc": 0.9,
        "ranking_pr_auc": 0.8,
        "ranking_ef1": 1.5,
        "ranking_bedroc": 0.4,
        "failed_metrics": [],
        "warnings": [],
    }
    rank_payload = {
        "metrics": {"roc_auc_unique_key": 0.9},
        "metrics_unique": {"score_unique_ratio": 0.5},
    }
    out = mod._build_claim_split(gate, rank_payload)
    assert "commercial_claim" in out
    assert "research_claim" in out
    assert bool(out["summary"]["pass"]) is True


def test_build_sla_summary_basic(tmp_path: Path):
    queue_csv = tmp_path / "queue.csv"
    pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "L1"},
            {"target": "T1", "ligand_id": "L2"},
            {"target": "T1", "ligand_id": "L3"},
        ]
    ).to_csv(queue_csv, index=False)
    out = mod._build_sla_summary(
        out_prefix="runs/demo",
        stage0={"duration_sec": 1.0},
        stage1={"duration_sec": 2.0},
        stage2_traj={"duration_sec": 3.0},
        stage2_meta={"duration_sec": 4.0},
        stage3={"duration_sec": 5.0},
        stage3b={"duration_sec": 0.0},
        stage4={"duration_sec": 0.5},
        stage45={"duration_sec": 0.2},
        stage5={"duration_sec": 0.1},
        gate_summary={"pass": True, "failed_metrics": []},
        queue_csv=str(queue_csv),
        trajectory_root="/tmp/traj",
        heavy_enabled=True,
    )
    assert bool(out["pass"]) is True
    assert int(out["queue_rows"]) == 3
    assert float(out["total_latency_sec"]) > 0.0
    assert float(out["queue_rate_stage2_rows_per_sec"]) > 0.0


def test_apply_gate_distance_overrides_replaces_matching_unique_rows() -> None:
    unique_df = pd.DataFrame(
        [
            {"target": "EGFR_KINASE", "ligand_id": "imatinib", "mean_min_distance_A": 2.284},
            {"target": "HIV1_PROTEASE", "ligand_id": "imatinib", "mean_min_distance_A": 2.698},
            {"target": "HIV1_PROTEASE", "ligand_id": "aspirin", "mean_min_distance_A": 2.660},
        ]
    )
    override_report = {
        "requested": True,
        "present": True,
        "path": "runs/nightly_stage6_downstream_rerun_gate_override_current.csv",
        "row_count": 2,
        "valid_row_count": 2,
        "rows": [
            {
                "target": "HIV1_PROTEASE",
                "ligand_id": "imatinib",
                "override_mean_min_distance_A": 2.215,
            },
            {
                "target": "HIV1_PROTEASE",
                "ligand_id": "aspirin",
                "override_mean_min_distance_A": 1.604,
            },
        ],
        "warnings": [],
    }
    out_df, stats = mod._apply_gate_distance_overrides(unique_df, override_report)
    vals = {(row["target"], row["ligand_id"]): row["mean_min_distance_A"] for row in out_df.to_dict(orient="records")}
    assert round(vals[("HIV1_PROTEASE", "imatinib")], 3) == 2.215
    assert round(vals[("HIV1_PROTEASE", "aspirin")], 3) == 1.604
    assert round(vals[("EGFR_KINASE", "imatinib")], 3) == 2.284
    assert stats["applied_count"] == 2
    assert stats["missing_count"] == 0


def test_traj_prod_operational_summary_exposes_resolved_family_and_effective_settings():
    args = _traj_stage2_args_namespace(
        traj_prod_stage2_preset="auto",
        traj_prod_stage2_preset_strict=True,
        traj_prod_speedpack=True,
        traj_prod_early_stop_enabled=True,
        targets="TRPV1_ION_CHANNEL_BLIND",
    )
    diag = mod._traj_prod_stage2_preset_diagnostics(args)
    runtime = mod._traj_prod_runtime_summary(args, diag)
    settings = mod._traj_stage2_runtime_settings(args, mode="full")
    out = mod._traj_prod_operational_summary(
        traj_prod=runtime,
        traj_stage2_settings=settings,
        traj_stage2_diag=diag,
    )
    assert out["requested_preset"] == "auto"
    assert out["resolved_preset"] == "ion_trpv1"
    assert out["strict_enabled"] is True
    assert out["strict_status"] == "ok"
    assert out["light_artifacts"] is True
    assert out["effective_writer_workers"] == 3
    assert out["effective_writer_max_pending"] == 256
    assert out["effective_min_frames"] == 168
    assert out["effective_early_stop_min_frames"] == 184
    assert out["hinted_families"] == ["ion_trpv1"]


def test_traj_prod_markdown_lines_surface_intent_and_effective_runtime():
    args = _traj_stage2_args_namespace(
        traj_prod_stage2_preset="auto",
        traj_prod_stage2_preset_strict=True,
        traj_prod_speedpack=True,
        traj_prod_early_stop_enabled=True,
        traj_prod_profile_intent="scaleup_100k_pilot",
        targets="TRPV1_ION_CHANNEL_BLIND",
    )
    diag = mod._traj_prod_stage2_preset_diagnostics(args)
    runtime = mod._traj_prod_runtime_summary(args, diag)
    settings = mod._traj_stage2_runtime_settings(args, mode="full")
    lines = mod._traj_prod_markdown_lines(
        traj_prod=runtime,
        traj_stage2_settings=settings,
        traj_stage2_diag=diag,
    )
    text = "\n".join(lines)
    assert "## Production Stage2" in text
    assert "- traj_prod_profile_intent: `scaleup_100k_pilot`" in text
    assert "- traj_prod_resolved_preset: `ion_trpv1`" in text
    assert "- effective_writer_workers: 3" in text
    assert "- effective_frame_budget_tiers: `0.92:1.00,0.78:0.88,0.62:0.74,0.00:0.60`" in text


def test_build_sla_summary_includes_top_level_prod_operational_keys(tmp_path: Path):
    queue_csv = tmp_path / "queue.csv"
    pd.DataFrame([{"target": "T1", "ligand_id": "L1"}]).to_csv(queue_csv, index=False)
    args = _traj_stage2_args_namespace(
        traj_prod_stage2_preset="gpcr",
        traj_prod_stage2_preset_strict=True,
        traj_prod_speedpack=True,
        targets="ADRB2_GPCR_BLIND",
    )
    diag = mod._traj_prod_stage2_preset_diagnostics(args)
    runtime = mod._traj_prod_runtime_summary(args, diag)
    settings = mod._traj_stage2_runtime_settings(args, mode="full")
    out = mod._build_sla_summary(
        out_prefix="runs/demo",
        stage0={"duration_sec": 1.0},
        stage1={"duration_sec": 1.0},
        stage2_traj={"duration_sec": 2.0},
        stage2_meta={"duration_sec": 1.0},
        stage3={"duration_sec": 1.0},
        stage3b={"duration_sec": 0.0},
        stage4={"duration_sec": 0.0},
        stage45={"duration_sec": 0.0},
        stage5={"duration_sec": 0.0},
        gate_summary={"pass": True, "failed_metrics": []},
        queue_csv=str(queue_csv),
        trajectory_root="/tmp/traj",
        heavy_enabled=False,
        traj_prod=runtime,
        traj_stage2_settings=settings,
        traj_stage2_diag=diag,
    )
    assert out["traj_prod_requested_preset"] == "gpcr"
    assert out["traj_prod_resolved_preset"] == "gpcr"
    assert out["traj_prod_strict_enabled"] is True
    assert out["traj_prod_strict_status"] == "ok"
    assert out["traj_prod_light_artifacts"] is True
    assert out["traj_prod_effective_writer_workers"] == 2
    assert out["traj_prod_effective_writer_max_pending"] == 160
    assert out["traj_prod_operational_summary"]["effective_frame_budget_tiers"] == "0.90:1.00,0.75:0.82,0.60:0.66,0.00:0.52"


def test_build_sla_summary_reads_stage2_engine_prod_telemetry(tmp_path: Path):
    queue_csv = tmp_path / "queue.csv"
    pd.DataFrame([{"target": "T1", "ligand_id": "L1"}]).to_csv(queue_csv, index=False)
    stage2_summary_json = tmp_path / "stage2_summary.json"
    stage2_summary_json.write_text(
        """
{
  "prod_mode": true,
  "prod_light_artifacts": true,
  "prod_adaptive_frame_budget": true,
  "prod_early_stop": true,
  "prod_frame_budget_applied_count": 9,
  "prod_early_stop_batch_count": 2,
  "prod_early_stop_row_count": 8,
  "mean_sim_frames_count": 141.5,
  "mean_frames_effective_cap": 152.0,
  "job_batch_derate_count": 3,
  "job_batch_size": 0,
  "writer_workers": 3,
  "writer_max_pending": 256,
  "progress_every_jobs": 250,
  "prod_light_effects": {
    "manifest_chunks_disabled": true,
    "target_tail_disabled": true,
    "summary_md_disabled": true,
    "progress_every_jobs_effective": 250
  },
  "artifacts": {
    "manifest_csv": "runs/demo_manifest.csv",
    "manifest_chunks_dir": "",
    "target_tail_csv": "",
    "summary_json": "runs/demo_summary.json",
    "summary_md": "",
    "progress_json": "runs/demo_progress.json"
  }
}
""".strip(),
        encoding="utf-8",
    )
    out = mod._build_sla_summary(
        out_prefix="runs/demo",
        stage0={"duration_sec": 1.0},
        stage1={"duration_sec": 1.0},
        stage2_traj={"duration_sec": 2.0},
        stage2_meta={"duration_sec": 1.0},
        stage3={"duration_sec": 1.0},
        stage3b={"duration_sec": 0.0},
        stage4={"duration_sec": 0.0},
        stage45={"duration_sec": 0.0},
        stage5={"duration_sec": 0.0},
        gate_summary={"pass": True, "failed_metrics": []},
        queue_csv=str(queue_csv),
        trajectory_root="/tmp/traj",
        heavy_enabled=False,
        traj_stage2_summary_json=str(stage2_summary_json),
    )
    assert out["traj_stage2_summary_json_present"] is True
    assert out["traj_stage2_engine_prod_mode"] is True
    assert out["traj_stage2_engine_prod_light_artifacts"] is True
    assert out["traj_stage2_engine_prod_frame_budget_applied_count"] == 9
    assert out["traj_stage2_engine_prod_early_stop_batch_count"] == 2
    assert out["traj_stage2_engine_prod_early_stop_row_count"] == 8
    assert out["traj_stage2_engine_mean_sim_frames_count"] == 141.5
    assert out["traj_stage2_engine_mean_frames_effective_cap"] == 152.0
    assert out["traj_stage2_engine_job_batch_derate_count"] == 3
    assert out["traj_stage2_engine_target_tail_csv_present"] is False
    assert out["traj_stage2_engine_manifest_chunks_dir_present"] is False
    assert out["traj_stage2_engine_summary_md_present"] is False
    assert out["traj_stage2_engine_summary"]["prod_light_effects"]["summary_md_disabled"] is True


def test_traj_prod_stage2_args_disabled_by_default():
    args = argparse.Namespace(
        traj_prod_speedpack=False,
        traj_prod_adaptive_frame_budget=True,
        traj_prod_frame_budget_tiers="0.90:1.00,0.75:0.85,0.60:0.70,0.00:0.55",
        traj_prod_min_frames_smoke=80,
        traj_prod_min_frames_full=160,
        traj_prod_early_stop_enabled=False,
        traj_prod_early_stop_min_frames_smoke=80,
        traj_prod_early_stop_min_frames_full=160,
        traj_prod_early_stop_window=12,
        traj_prod_early_stop_contact_drift=0.015,
        traj_prod_early_stop_min_distance_drift_A=0.12,
        traj_prod_early_stop_max_mean_min_distance_A=6.0,
    )
    assert mod._traj_prod_stage2_args(args, mode="full", traj_frames=300) == []


def test_traj_prod_stage2_args_smoke_and_full_wiring():
    args = argparse.Namespace(
        traj_prod_speedpack=True,
        traj_prod_adaptive_frame_budget=True,
        traj_prod_frame_budget_tiers="0.90:1.00,0.75:0.85,0.60:0.70,0.00:0.55",
        traj_prod_min_frames_smoke=84,
        traj_prod_min_frames_full=180,
        traj_prod_early_stop_enabled=True,
        traj_prod_early_stop_min_frames_smoke=90,
        traj_prod_early_stop_min_frames_full=220,
        traj_prod_early_stop_window=16,
        traj_prod_early_stop_contact_drift=0.03,
        traj_prod_early_stop_min_distance_drift_A=0.15,
        traj_prod_early_stop_max_mean_min_distance_A=5.5,
    )
    smoke = mod._traj_prod_stage2_args(args, mode="smoke", traj_frames=120)
    full = mod._traj_prod_stage2_args(args, mode="full", traj_frames=300)
    assert "--prod-mode" in smoke
    assert "--prod-adaptive-frame-budget" in smoke
    assert smoke[smoke.index("--prod-min-frames") + 1] == "84"
    assert full[full.index("--prod-min-frames") + 1] == "180"
    assert "--prod-early-stop" in smoke
    assert smoke[smoke.index("--prod-early-stop-min-frames") + 1] == "90"
    assert full[full.index("--prod-early-stop-min-frames") + 1] == "220"
    assert full[full.index("--prod-early-stop-window") + 1] == "16"
    assert full[full.index("--prod-early-stop-contact-drift") + 1] == "0.03"
    assert full[full.index("--prod-early-stop-min-distance-drift-A") + 1] == "0.15"
    assert full[full.index("--prod-early-stop-max-mean-min-distance-A") + 1] == "5.5"
    assert "--prod-light-artifacts" in full
    assert full[full.index("--prod-light-progress-every-jobs") + 1] == "250"


def test_traj_prod_early_stop_min_frames_is_clamped():
    args = argparse.Namespace(
        traj_prod_early_stop_min_frames_smoke=999,
        traj_prod_early_stop_min_frames_full=999,
    )
    assert mod._traj_prod_early_stop_min_frames(args, "smoke", 120) == 120
    assert mod._traj_prod_early_stop_min_frames(args, "full", 300) == 300


def test_traj_prod_min_frames_is_clamped():
    args = argparse.Namespace(
        traj_prod_min_frames_smoke=999,
        traj_prod_min_frames_full=999,
    )
    assert mod._traj_prod_min_frames(args, "smoke", 120) == 120
    assert mod._traj_prod_min_frames(args, "full", 300) == 300


def test_traj_prod_stage2_args_parse_in_engine_surface():
    args = argparse.Namespace(
        traj_prod_speedpack=True,
        traj_prod_adaptive_frame_budget=True,
        traj_prod_frame_budget_tiers="0.90:1.00,0.75:0.85,0.60:0.70,0.00:0.55",
        traj_prod_min_frames_smoke=84,
        traj_prod_min_frames_full=180,
        traj_prod_early_stop_enabled=True,
        traj_prod_early_stop_min_frames_smoke=90,
        traj_prod_early_stop_min_frames_full=220,
        traj_prod_early_stop_window=16,
        traj_prod_early_stop_contact_drift=0.03,
        traj_prod_early_stop_min_distance_drift_A=0.15,
        traj_prod_early_stop_max_mean_min_distance_A=5.5,
    )
    cli = mod._traj_prod_stage2_args(args, mode="full", traj_frames=300)
    parsed = traj_engine.build_parser().parse_args(
        [
            "--queue-csv",
            "dummy.csv",
            "--out-root",
            "dummy_out",
            *cli,
        ]
    )
    assert parsed.prod_mode is True
    assert parsed.prod_adaptive_frame_budget is True
    assert parsed.prod_min_frames == 180
    assert parsed.prod_early_stop is True
    assert parsed.prod_early_stop_min_frames == 220
    assert parsed.prod_light_artifacts is True
    assert parsed.prod_light_progress_every_jobs == 250


def test_traj_resume_existing_stage2_arg_defaults_on_and_can_disable():
    default_args = mod.build_parser().parse_args([])
    assert default_args.traj_resume_existing is True
    assert mod._traj_resume_existing_stage2_arg(default_args) == ["--resume-existing"]

    disabled_args = mod.build_parser().parse_args(["--no-traj-resume-existing"])
    assert disabled_args.traj_resume_existing is False
    assert mod._traj_resume_existing_stage2_arg(disabled_args) == ["--no-resume-existing"]


def test_infer_traj_prod_stage2_preset_family_auto_variants():
    assert mod._infer_traj_prod_stage2_preset_family(_traj_stage2_args_namespace(targets="ADRB2_GPCR_BLIND")) == "gpcr"
    assert mod._infer_traj_prod_stage2_preset_family(_traj_stage2_args_namespace(targets="TRPV1_ION_CHANNEL_BLIND")) == "ion_trpv1"
    assert mod._infer_traj_prod_stage2_preset_family(_traj_stage2_args_namespace(targets="EGFR_KINASE,HIV1_PROTEASE")) == "kinase_protease"
    assert mod._infer_traj_prod_stage2_preset_family(_traj_stage2_args_namespace(targets="UNKNOWN_TARGET")) == "default"
    assert (
        mod._infer_traj_prod_stage2_preset_family(
            _traj_stage2_args_namespace(
                targets="UNKNOWN_TARGET",
                target_native_csv="config/native_gpcr_hint.csv",
                leakage_target_meta_csv="config/gpcr_meta.csv",
                out_prefix="runs/gpcr-demo",
            )
        )
        == "gpcr"
    )


def test_traj_stage2_runtime_settings_disabled_preserves_existing_values():
    args = _traj_stage2_args_namespace(
        traj_prod_stage2_preset="off",
        traj_frames_full=333,
        traj_job_batch_autotune_candidates="1,3,5",
        traj_writer_workers=7,
        traj_writer_max_pending=77,
        traj_dynamic_adress_fraction=0.19,
    )
    settings = mod._traj_stage2_runtime_settings(args, mode="full")
    assert settings["traj_frames"] == 333
    assert settings["traj_job_batch_autotune_candidates"] == "1,3,5"
    assert settings["traj_writer_workers"] == 7
    assert settings["traj_writer_max_pending"] == 77
    assert settings["traj_dynamic_adress_fraction"] == 0.19
    assert settings["traj_prod_stage2_preset"]["enabled"] is False
    assert settings["traj_prod_stage2_preset"]["resolved"] == "off"


def test_traj_stage2_runtime_settings_auto_gpcr_applies_family_overrides():
    args = _traj_stage2_args_namespace(
        traj_prod_stage2_preset="auto",
        targets="ADRB2_GPCR_BLIND",
        traj_frames_full=333,
        traj_writer_workers=1,
        traj_writer_max_pending=64,
    )
    settings = mod._traj_stage2_runtime_settings(args, mode="full")
    assert settings["traj_prod_stage2_preset"]["enabled"] is True
    assert settings["traj_prod_stage2_preset"]["requested"] == "auto"
    assert settings["traj_prod_stage2_preset"]["resolved"] == "gpcr"
    assert settings["traj_frames"] == 333
    assert settings["traj_job_batch_autotune_candidates"] == "2,4,8,16"
    assert settings["traj_writer_workers"] == 2
    assert settings["traj_writer_max_pending"] == 160
    assert settings["traj_dynamic_adress_max_protein_residues"] == 170
    assert settings["traj_prod_frame_budget_tiers"] == "0.90:1.00,0.75:0.82,0.60:0.66,0.00:0.52"
    assert settings["traj_prod_min_frames"] == 140
    assert settings["traj_prod_early_stop_min_frames"] == 152


def test_traj_stage2_runtime_settings_explicit_default_overrides_auto_family():
    args = _traj_stage2_args_namespace(
        traj_prod_stage2_preset="default",
        targets="ADRB2_GPCR_BLIND",
    )
    settings = mod._traj_stage2_runtime_settings(args, mode="full")
    assert settings["traj_prod_stage2_preset"]["resolved"] == "default"
    assert settings["traj_writer_max_pending"] == 128
    assert settings["traj_dynamic_adress_max_protein_residues"] == 180
    assert settings["traj_prod_min_frames"] == 144


def test_traj_prod_stage2_args_respect_preset_adjusted_frame_budget():
    args = _traj_stage2_args_namespace(
        traj_prod_stage2_preset="kinase_protease",
        targets="EGFR_KINASE",
        traj_prod_speedpack=True,
        traj_prod_min_frames_full=999,
        traj_prod_early_stop_enabled=True,
        traj_prod_early_stop_min_frames_full=999,
    )
    settings = mod._traj_stage2_runtime_settings(args, mode="full")
    cli = mod._traj_prod_stage2_args(args, mode="full", traj_frames=settings["traj_frames"])
    assert settings["traj_frames"] == 300
    assert settings["traj_prod_frame_budget_tiers"] == "0.90:0.95,0.75:0.76,0.60:0.60,0.00:0.46"
    assert cli[cli.index("--prod-min-frames") + 1] == "128"
    assert cli[cli.index("--prod-early-stop-min-frames") + 1] == "140"


def test_traj_prod_stage2_preset_diagnostics_warn_when_speedpack_off():
    args = _traj_stage2_args_namespace(
        traj_prod_stage2_preset="auto",
        targets="ADRB2_GPCR_BLIND",
        traj_prod_speedpack=False,
    )
    diag = mod._traj_prod_stage2_preset_diagnostics(args)
    assert diag["requested"] == "auto"
    assert diag["resolved"] == "gpcr"
    assert diag["error"] == ""
    assert any("traj_prod_speedpack is off" in warning for warning in diag["warnings"])


def test_traj_prod_stage2_preset_diagnostics_strict_rejects_mixed_auto():
    args = _traj_stage2_args_namespace(
        traj_prod_stage2_preset="auto",
        traj_prod_stage2_preset_strict=True,
        targets="ADRB2_GPCR_BLIND,TRPV1_ION_CHANNEL_BLIND",
    )
    diag = mod._traj_prod_stage2_preset_diagnostics(args)
    assert diag["strict_enabled"] is True
    assert "mixed-family auto inference" in diag["error"]


def test_traj_prod_stage2_preset_diagnostics_strict_rejects_manual_mismatch():
    args = _traj_stage2_args_namespace(
        traj_prod_stage2_preset="gpcr",
        traj_prod_stage2_preset_strict=True,
        targets="EGFR_KINASE",
    )
    diag = mod._traj_prod_stage2_preset_diagnostics(args)
    assert "explicit preset mismatch" in diag["error"]


def test_traj_prod_runtime_summary_warns_when_prod_enabled_without_intent():
    args = _traj_stage2_args_namespace(
        traj_prod_stage2_preset="auto",
        targets="ADRB2_GPCR_BLIND",
        traj_prod_speedpack=True,
        traj_prod_profile_intent="",
    )
    diag = mod._traj_prod_stage2_preset_diagnostics(args)
    summary = mod._traj_prod_runtime_summary(args, diag)
    assert summary["enabled"] is True
    assert summary["resolved_preset"] == "gpcr"
    assert "without traj_prod_profile_intent" in summary["intent_warning"]
    assert any("without traj_prod_profile_intent" in warning for warning in summary["warnings"])


def test_traj_prod_runtime_summary_preserves_explicit_intent():
    args = _traj_stage2_args_namespace(
        traj_prod_stage2_preset="auto",
        targets="TRPV1_ION_CHANNEL_BLIND",
        traj_prod_speedpack=True,
        traj_prod_profile_intent="scaleup_100k_pilot",
    )
    diag = mod._traj_prod_stage2_preset_diagnostics(args)
    summary = mod._traj_prod_runtime_summary(args, diag)
    assert summary["enabled"] is True
    assert summary["profile_intent"] == "scaleup_100k_pilot"
    assert summary["resolved_preset"] == "ion_trpv1"
    assert summary["intent_warning"] == ""


def test_attach_service_result_uses_error_map_and_retry(tmp_path: Path):
    error_profile = tmp_path / "errors.json"
    error_profile.write_text(
        """
{
  "ok_code": "OK",
  "unknown_error_code": "UNKNOWN",
  "map": {
    "stage3_backmapping_scoring": "E_STAGE3"
  },
  "retryable_stages": ["stage3_backmapping_scoring"]
}
""".strip(),
        encoding="utf-8",
    )
    args = argparse.Namespace(
        service_error_codes_json=str(error_profile),
        service_retry_after_sec_transient=45,
        service_retry_after_sec_default=300,
        service_schema_version="service_v1",
        data_contract_json="config/ligand_data_contract_v1.json",
    )
    out = mod._attach_service_result(
        {"pass": False, "failed_stage": "stage3_backmapping_scoring"},
        args,
    )
    assert out["schema_version"] == "service_v1"
    assert out["service_result"]["status"] == "error"
    assert out["service_result"]["error_code"] == "E_STAGE3"
    assert bool(out["service_result"]["retryable"]) is True
    assert int(out["service_result"]["retry_after_sec"]) == 45


def test_finalize_and_write_adds_service_result(tmp_path: Path):
    out_prefix = str(tmp_path / "pipeline")
    error_profile = tmp_path / "errors.json"
    error_profile.write_text("{}", encoding="utf-8")
    args = argparse.Namespace(
        service_error_codes_json=str(error_profile),
        service_retry_after_sec_transient=60,
        service_retry_after_sec_default=300,
        service_schema_version="service_v1",
        data_contract_json="config/ligand_data_contract_v1.json",
    )
    payload = {"pass": True, "failed_stage": None, "artifacts": {"summary_json": f"{out_prefix}_summary.json"}}
    out = mod._finalize_and_write(out_prefix, payload, args)
    assert out["service_result"]["status"] == "ok"
    summary_json = Path(f"{out_prefix}_summary.json")
    assert summary_json.exists()


def test_strict_gate_from_operational_thresholds():
    op_gate = {
        "min_frames_observed": 120,
        "mean_min_distance_A": 2.4,
        "ranking_unique_auc": 0.91,
        "ranking_ood_unique_auc": 0.86,
        "ranking_pr_auc": 0.70,
        "ranking_ef1": 1.30,
        "ranking_bedroc": 0.40,
        "ranking_brier": 0.20,
        "ranking_ece": 0.15,
        "ranking_roc_auc_ci_low": 0.82,
        "ranking_pr_auc_ci_low": 0.62,
        "ranking_ef1_ci_low": 1.02,
        "ranking_topk_hit_rate": 0.82,
        "ranking_positive_count": 30,
        "ranking_ood_positive_count": 20,
        "ranking_expected_score_coverage_ratio": 0.99,
        "ranking_score_unique_ratio": 0.08,
        "ranking_score_tie_ratio": 0.20,
        "ranking_score_mode_ratio": 0.20,
        "ranking_score_orientation_suspect": False,
        "warnings": [],
    }
    args = argparse.Namespace(
        enforce_strict_gate=True,
        strict_gate_min_frames=100,
        strict_gate_max_mean_min_distance_A=2.5,
        strict_gate_ranking_unique_auc_min=0.90,
        strict_gate_ranking_ood_auc_min=0.85,
        strict_gate_pr_auc_min=0.60,
        strict_gate_ef1_min=1.25,
        strict_gate_bedroc_min=0.30,
        strict_gate_brier_max=0.30,
        strict_gate_ece_max=0.30,
        strict_gate_roc_auc_ci_lower_min=0.80,
        strict_gate_pr_auc_ci_lower_min=0.50,
        strict_gate_ef1_ci_lower_min=1.00,
        strict_gate_topk_hit_rate_min=0.80,
        strict_gate_min_positive_count=10,
        strict_gate_min_ood_positive_count=10,
        strict_gate_ranking_min_expected_score_coverage=0.95,
        strict_gate_score_unique_ratio_min=0.05,
        strict_gate_score_tie_ratio_max=0.95,
        strict_gate_score_mode_ratio_max=0.95,
        strict_gate_fail_on_orientation_suspect=True,
    )
    strict = mod._strict_gate_from_operational(op_gate, args)
    assert bool(strict["enabled"]) is True
    assert bool(strict["pass"]) is True

    op_gate_bad = dict(op_gate)
    op_gate_bad["ranking_unique_auc"] = 0.40
    strict_bad = mod._strict_gate_from_operational(op_gate_bad, args)
    assert bool(strict_bad["pass"]) is False
    assert any(m.get("metric") == "ranking_unique_auc" for m in strict_bad["failed_metrics"])


def test_stage1_eval_positive_check_enforces_3d_ready(tmp_path: Path):
    queue_csv = tmp_path / "queue.csv"
    labels_csv = tmp_path / "labels.csv"
    split_csv = tmp_path / "split.csv"
    native_pdb = tmp_path / "native.pdb"
    native_pdb.write_text("ATOM      1  CA  ALA A   1       0.0   0.0   0.0\n", encoding="utf-8")

    pd.DataFrame(
        [
            {
                "target": "T1",
                "ligand_id": "L_POS",
                "ligand_bead_count": 0,  # not 3d-ready
                "ligand_bead0_x": 0.0,
                "ligand_bead0_y": 0.0,
                "ligand_bead0_z": 0.0,
                "native_pdb_path": str(native_pdb),
            },
            {
                "target": "T1",
                "ligand_id": "L_NEG",
                "ligand_bead_count": 2,
                "ligand_bead0_x": 1.0,
                "ligand_bead0_y": 1.0,
                "ligand_bead0_z": 1.0,
                "native_pdb_path": str(native_pdb),
            },
        ]
    ).to_csv(queue_csv, index=False)
    pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "L_POS", "is_binder": 1},
            {"target": "T1", "ligand_id": "L_NEG", "is_binder": 0},
        ]
    ).to_csv(labels_csv, index=False)
    pd.DataFrame(
        [
            {"target": "T1", "ligand_id": "L_POS", "role": "eval"},
            {"target": "T1", "ligand_id": "L_NEG", "role": "eval"},
        ]
    ).to_csv(split_csv, index=False)

    out = mod._stage1_eval_positive_check(
        queue_csv=str(queue_csv),
        labels_csv=str(labels_csv),
        split_csv=str(split_csv),
        eval_roles=["eval"],
        target_col="target",
        ligand_col="ligand_id",
        role_col="role",
        binder_col="is_binder",
        require_3d_ready=True,
        require_native_path_exists=True,
    )
    assert bool(out["ok"]) is True
    assert int(out["rows_eval_positive_total"]) == 1
    assert int(out["rows_eval_positive_in_queue"]) == 1
    assert int(out["rows_eval_positive_3d_ready"]) == 0
    assert int(out["not_ready_eval_positive_count"]) == 1
