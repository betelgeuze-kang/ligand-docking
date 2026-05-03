import json
from pathlib import Path

import pytest

from tools import build_gpcr_scaleup_intrusion_candidate as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_family_balanced_default_base_profile_uses_frozen_non_adrb2_support() -> None:
    assert (
        mod._default_base_profile_json_for_variant("gpcr_core_family_balanced_rescore_v1")
        == "runs/gpcr_frozen_candidate_profile_support_current/profile.json"
    )
    assert (
        mod._default_base_profile_json_for_variant("gpcr_core_linear_rescore_v1")
        == mod.DEFAULT_BASE_PROFILE_JSON
    )


def test_build_payload_writes_shadow_profile_and_core_only_100k_spec(tmp_path: Path) -> None:
    base_profile = tmp_path / "config" / "base_gpcr.json"
    residual_spec = tmp_path / "runs" / "gpcr_residual_prototype_spec_core_decoy_intrusion_v1_current.json"
    out_dir = tmp_path / "candidate"
    _write_json(
        base_profile,
        {
            "version": "ligand_htvs_blind_gpcr_adrb2_v4_scorefix3",
            "description": "base profile",
            "ranking_score_col": "binding_score_composite_v7",
            "ranking_probability_score_col": "binding_score_composite_v7",
            "full": {"max_ligands": 10000, "replicas": 10000},
        },
    )
    _write_json(
        residual_spec,
        {
            "summary": {
                "family": "gpcr",
                "prototype_variant": "gpcr_core_decoy_intrusion_v1",
            }
        },
    )

    payload = mod.build_payload(
        out_dir=out_dir,
        spec_json=residual_spec,
        base_profile_json=base_profile,
        tag_suffix="intrusiontest",
    )

    profile_path = Path(payload["profile_json"])
    set_spec_path = Path(payload["set_spec_json"])
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    set_spec = json.loads(set_spec_path.read_text(encoding="utf-8"))

    assert profile["residual_prototype_enabled"] is True
    assert profile["residual_prototype_mode"] == "shadow_only"
    assert profile["residual_prototype_family"] == "gpcr"
    assert profile["residual_prototype_runtime_hook_ready"] is True
    assert profile["residual_prototype_spec_json"] == str(residual_spec.resolve())
    assert profile["ranking_score_col"] == "binding_score_composite_v7"
    assert profile["ranking_probability_score_col"] == "binding_score_composite_v7"
    assert profile["router_promotion_allowed"] is False

    assert set_spec["global_governance"]["router_promotion_allowed"] is False
    assert set_spec["global_governance"]["prototype_spec_json"] == str(residual_spec.resolve())
    assert set_spec["global_governance"]["comparison_candidate_role"] == "shadow_candidate"
    assert set_spec["global_governance"]["claim_safe_assertion_allowed"] is False
    assert [row["set_id"] for row in set_spec["sets"]] == ["set1_core_blind"]
    assert set_spec["sets"][0]["claim_role"] == "comparison_candidate"
    assert "not a claim" in set_spec["sets"][0]["preregistered_claim"].lower()
    task = set_spec["sets"][0]["tasks"][0]
    assert task == {
        "task_id": "gpcr_core_full",
        "domain": "gpcr",
        "kind": "ligand_stress",
        "profile_json": str(profile_path.resolve()),
        "ligand_sizes": "100000",
        "date_tag_suffix": "gpcr-core-full-intrusiontest",
    }


def test_build_payload_rejects_non_intrusion_residual_spec(tmp_path: Path) -> None:
    base_profile = tmp_path / "base.json"
    residual_spec = tmp_path / "spec.json"
    _write_json(base_profile, {"ranking_score_col": "binding_score_composite_v7"})
    _write_json(residual_spec, {"summary": {"prototype_variant": "narrow_v2"}})

    with pytest.raises(ValueError, match="gpcr_core_decoy_intrusion_v1"):
        mod.build_payload(
            out_dir=tmp_path / "out",
            spec_json=residual_spec,
            base_profile_json=base_profile,
            tag_suffix="bad",
        )


def test_build_payload_supports_target_specific_pharmacophore_variant(tmp_path: Path) -> None:
    base_profile = tmp_path / "config" / "base_gpcr.json"
    residual_spec = tmp_path / "runs" / "gpcr_residual_prototype_spec_pharmacophore.json"
    out_dir = tmp_path / "candidate"
    _write_json(base_profile, {"ranking_score_col": "binding_score_composite_v7"})
    _write_json(
        residual_spec,
        {
            "summary": {
                "family": "gpcr",
                "prototype_variant": "gpcr_adrb2_beta_blocker_pharmacophore_v1",
            }
        },
    )

    payload = mod.build_payload(
        out_dir=out_dir,
        spec_json=residual_spec,
        base_profile_json=base_profile,
        tag_suffix="pharmacophoretest",
        variant="gpcr_adrb2_beta_blocker_pharmacophore_v1",
    )

    profile = json.loads(Path(payload["profile_json"]).read_text(encoding="utf-8"))
    set_spec = json.loads(Path(payload["set_spec_json"]).read_text(encoding="utf-8"))

    assert payload["candidate_kind"] == "gpcr_adrb2_beta_blocker_pharmacophore_100k"
    assert profile["residual_prototype_candidate"] == "gpcr_adrb2_beta_blocker_pharmacophore_v1"
    assert profile["router_promotion_allowed"] is False
    assert profile["target_specific_candidate"] is True
    assert "target-specific" in profile["residual_prototype_notes"]
    assert set_spec["global_governance"]["prototype_variant"] == "gpcr_adrb2_beta_blocker_pharmacophore_v1"
    assert set_spec["global_governance"]["router_promotion_allowed"] is False


def test_build_payload_can_emit_guarded_apply_profile(tmp_path: Path) -> None:
    base_profile = tmp_path / "config" / "base_gpcr.json"
    residual_spec = tmp_path / "runs" / "gpcr_residual_prototype_spec_pharmacophore.json"
    out_dir = tmp_path / "candidate"
    _write_json(base_profile, {"ranking_score_col": "binding_score_composite_v7"})
    _write_json(
        residual_spec,
        {
            "summary": {
                "family": "gpcr",
                "prototype_variant": "gpcr_adrb2_beta_blocker_pharmacophore_v1",
            }
        },
    )

    payload = mod.build_payload(
        out_dir=out_dir,
        spec_json=residual_spec,
        base_profile_json=base_profile,
        tag_suffix="applytest",
        variant="gpcr_adrb2_beta_blocker_pharmacophore_v1",
        mode="apply",
    )

    profile = json.loads(Path(payload["profile_json"]).read_text(encoding="utf-8"))
    set_spec = json.loads(Path(payload["set_spec_json"]).read_text(encoding="utf-8"))

    assert payload["residual_prototype_mode"] == "apply"
    assert profile["residual_prototype_mode"] == "apply"
    assert profile["ranking_score_col"] == "binding_score_composite_v7_residual_active"
    assert profile["ranking_probability_score_col"] == "binding_score_composite_v7_residual_active"
    assert profile["router_promotion_allowed"] is False
    assert set_spec["global_governance"]["prototype_mode"] == "apply"
    assert set_spec["global_governance"]["apply_mode_claim_allowed"] is False
    assert set_spec["global_governance"]["comparison_candidate_role"] == "guarded_apply_candidate"
    assert set_spec["global_governance"]["claim_safe_assertion_allowed"] is False
    assert set_spec["sets"][0]["claim_role"] == "comparison_candidate"


def test_build_payload_accepts_custom_validation_set_and_task(tmp_path: Path) -> None:
    base_profile = tmp_path / "config" / "chembl50_gpcr.json"
    residual_spec = tmp_path / "runs" / "gpcr_residual_prototype_spec_pharmacophore.json"
    out_dir = tmp_path / "candidate"
    _write_json(base_profile, {"ranking_score_col": "binding_score_composite_v7"})
    _write_json(
        residual_spec,
        {
            "summary": {
                "family": "gpcr",
                "prototype_variant": "gpcr_adrb2_beta_blocker_pharmacophore_v1",
            }
        },
    )

    payload = mod.build_payload(
        out_dir=out_dir,
        spec_json=residual_spec,
        base_profile_json=base_profile,
        tag_suffix="chembl50apply",
        variant="gpcr_adrb2_beta_blocker_pharmacophore_v1",
        mode="apply",
        set_id="set2_expanded_ood",
        set_title="Expanded OOD Set",
        task_id="gpcr_chembl50_full",
    )

    set_spec = json.loads(Path(payload["set_spec_json"]).read_text(encoding="utf-8"))
    assert set_spec["sets"][0]["set_id"] == "set2_expanded_ood"
    assert set_spec["sets"][0]["title"] == "Expanded OOD Set"
    assert set_spec["sets"][0]["tasks"][0]["task_id"] == "gpcr_chembl50_full"
    assert set_spec["sets"][0]["tasks"][0]["date_tag_suffix"] == "gpcr-chembl50-full-chembl50apply"
    assert "--sets set2_expanded_ood" in payload["run_command"]


def test_build_payload_supports_core_linear_rescore_as_guarded_apply_candidate(tmp_path: Path) -> None:
    base_profile = tmp_path / "config" / "base_gpcr.json"
    residual_spec = tmp_path / "runs" / "gpcr_residual_prototype_spec_linear.json"
    out_dir = tmp_path / "candidate"
    _write_json(base_profile, {"ranking_score_col": "binding_score_composite_v7"})
    _write_json(
        residual_spec,
        {
            "summary": {
                "family": "gpcr",
                "prototype_variant": "gpcr_core_linear_rescore_v1",
            },
            "prototype": {
                "tuning": {
                    "variant": "gpcr_core_linear_rescore_v1",
                }
            },
        },
    )

    payload = mod.build_payload(
        out_dir=out_dir,
        spec_json=residual_spec,
        base_profile_json=base_profile,
        tag_suffix="lineartest",
        variant="gpcr_core_linear_rescore_v1",
        mode="apply",
    )

    profile = json.loads(Path(payload["profile_json"]).read_text(encoding="utf-8"))
    set_spec = json.loads(Path(payload["set_spec_json"]).read_text(encoding="utf-8"))

    assert payload["candidate_kind"] == "gpcr_core_linear_rescore_100k"
    assert payload["residual_prototype_mode"] == "apply"
    assert profile["residual_prototype_candidate"] == "gpcr_core_linear_rescore_v1"
    assert profile["ranking_score_col"] == "binding_score_composite_v7_residual_active"
    assert profile["router_promotion_allowed"] is False
    assert "guarded apply" in profile["residual_prototype_notes"].lower()
    assert set_spec["global_governance"]["prototype_variant"] == "gpcr_core_linear_rescore_v1"
    assert set_spec["global_governance"]["comparison_candidate_role"] == "guarded_apply_candidate"
    assert set_spec["global_governance"]["apply_mode_claim_allowed"] is False
    assert set_spec["global_governance"]["claim_safe_assertion_allowed"] is False
    assert set_spec["sets"][0]["claim_role"] == "comparison_candidate"
    assert "not a claim" in set_spec["sets"][0]["preregistered_claim"].lower()


def test_build_payload_supports_family_balanced_rescore_as_claim_locked_candidate(tmp_path: Path) -> None:
    base_profile = tmp_path / "config" / "base_gpcr.json"
    residual_spec = tmp_path / "runs" / "gpcr_residual_prototype_spec_family_balanced.json"
    out_dir = tmp_path / "candidate"
    _write_json(base_profile, {"ranking_score_col": "binding_score_composite_v7"})
    _write_json(
        residual_spec,
        {
            "summary": {
                "family": "gpcr",
                "prototype_variant": "gpcr_core_family_balanced_rescore_v1",
            },
            "prototype": {
                "constraints": {
                    "comparison_only_candidate": True,
                    "claim_locked_candidate": True,
                    "router_promotion_allowed": False,
                    "platform_promotion_allowed": False,
                    "claim_safe_assertion_allowed": False,
                    "broad_gpcr_claim_allowed": False,
                },
                "tuning": {
                    "variant": "gpcr_core_family_balanced_rescore_v1",
                },
            },
        },
    )

    payload = mod.build_payload(
        out_dir=out_dir,
        spec_json=residual_spec,
        base_profile_json=base_profile,
        tag_suffix="familybalanced",
        variant="gpcr_core_family_balanced_rescore_v1",
        mode="apply",
    )

    profile = json.loads(Path(payload["profile_json"]).read_text(encoding="utf-8"))
    set_spec = json.loads(Path(payload["set_spec_json"]).read_text(encoding="utf-8"))
    governance = set_spec["global_governance"]

    assert payload["candidate_kind"] == "gpcr_core_family_balanced_rescore_100k"
    assert profile["residual_prototype_candidate"] == "gpcr_core_family_balanced_rescore_v1"
    assert profile["ranking_score_col"] == "binding_score_composite_v7_residual_active"
    assert profile["router_promotion_allowed"] is False
    assert profile["platform_promotion_allowed"] is False
    assert profile["claim_locked_candidate"] is True
    assert profile["claim_safe_assertion_allowed"] is False
    assert profile["broad_gpcr_claim_allowed"] is False
    assert profile["traj_resume_existing"] is True
    assert "claim-locked" in profile["residual_prototype_notes"].lower()
    assert governance["prototype_variant"] == "gpcr_core_family_balanced_rescore_v1"
    assert governance["comparison_candidate_role"] == "guarded_apply_candidate"
    assert governance["router_promotion_allowed"] is False
    assert governance["platform_promotion_allowed"] is False
    assert governance["claim_locked_candidate"] is True
    assert governance["claim_safe_assertion_allowed"] is False
    assert governance["broad_gpcr_claim_allowed"] is False
    assert set_spec["sets"][0]["claim_role"] == "comparison_candidate"


def test_build_payload_can_override_heavy_artifact_root_for_local_reruns(tmp_path: Path) -> None:
    base_profile = tmp_path / "config" / "base_gpcr.json"
    residual_spec = tmp_path / "runs" / "gpcr_residual_prototype_spec_core_decoy_intrusion_v1_current.json"
    heavy_root = tmp_path / "local_heavy_runs"
    _write_json(
        base_profile,
        {
            "ranking_score_col": "binding_score_composite_v7",
            "heavy_artifacts_root": "/mnt/full/ligand_heavy_runs",
            "auto_heavy_artifacts_root": True,
        },
    )
    _write_json(
        residual_spec,
        {
            "summary": {
                "family": "gpcr",
                "prototype_variant": "gpcr_core_decoy_intrusion_v1",
            }
        },
    )

    payload = mod.build_payload(
        out_dir=tmp_path / "candidate",
        spec_json=residual_spec,
        base_profile_json=base_profile,
        tag_suffix="localheavy",
        variant="gpcr_core_decoy_intrusion_v1",
        mode="apply",
        heavy_artifacts_root=str(heavy_root),
    )

    profile = json.loads(Path(payload["profile_json"]).read_text(encoding="utf-8"))
    assert profile["heavy_artifacts_root"] == str(heavy_root)
    assert profile["auto_heavy_artifacts_root"] is False


def test_build_payload_can_override_stage2_writer_for_local_reruns(tmp_path: Path) -> None:
    base_profile = tmp_path / "config" / "base_gpcr.json"
    residual_spec = tmp_path / "runs" / "gpcr_residual_prototype_spec_core_decoy_intrusion_v1_current.json"
    _write_json(
        base_profile,
        {
            "ranking_score_col": "binding_score_composite_v7",
            "traj_writer_mode": "process",
            "traj_writer_workers": 4,
            "traj_writer_max_pending": 160,
        },
    )
    _write_json(
        residual_spec,
        {
            "summary": {
                "family": "gpcr",
                "prototype_variant": "gpcr_core_decoy_intrusion_v1",
            }
        },
    )

    payload = mod.build_payload(
        out_dir=tmp_path / "candidate",
        spec_json=residual_spec,
        base_profile_json=base_profile,
        tag_suffix="safeio",
        variant="gpcr_core_decoy_intrusion_v1",
        mode="apply",
        traj_writer_mode="thread",
        traj_writer_workers=1,
        traj_writer_max_pending=32,
    )

    profile = json.loads(Path(payload["profile_json"]).read_text(encoding="utf-8"))
    assert profile["traj_writer_mode"] == "thread"
    assert profile["traj_writer_workers"] == 1
    assert profile["traj_writer_max_pending"] == 32


def test_build_payload_can_pin_stage2_batching_for_safe_local_reruns(tmp_path: Path) -> None:
    base_profile = tmp_path / "config" / "base_gpcr.json"
    residual_spec = tmp_path / "runs" / "gpcr_residual_prototype_spec_core_decoy_intrusion_v1_current.json"
    _write_json(
        base_profile,
        {
            "ranking_score_col": "binding_score_composite_v7",
            "traj_job_batch_size": 0,
            "traj_job_batch_autotune_candidates": "2,4,8,16",
        },
    )
    _write_json(
        residual_spec,
        {
            "summary": {
                "family": "gpcr",
                "prototype_variant": "gpcr_core_decoy_intrusion_v1",
            }
        },
    )

    payload = mod.build_payload(
        out_dir=tmp_path / "candidate",
        spec_json=residual_spec,
        base_profile_json=base_profile,
        tag_suffix="safebatch",
        variant="gpcr_core_decoy_intrusion_v1",
        mode="apply",
        traj_job_batch_size=1,
        traj_job_batch_autotune_candidates="1",
        traj_job_batch_autotune_frames=4,
        traj_engine_cache_max_entries=0,
    )

    profile = json.loads(Path(payload["profile_json"]).read_text(encoding="utf-8"))
    assert profile["traj_job_batch_size"] == 1
    assert profile["traj_job_batch_autotune_candidates"] == "1"
    assert profile["traj_job_batch_autotune_frames"] == 4
    assert profile["traj_engine_cache_max_entries"] == 0


def test_build_payload_can_disable_stage2_early_stop_for_rollout_reruns(tmp_path: Path) -> None:
    base_profile = tmp_path / "config" / "base_gpcr.json"
    residual_spec = tmp_path / "runs" / "gpcr_residual_prototype_spec_core_decoy_intrusion_v1_current.json"
    _write_json(
        base_profile,
        {
            "ranking_score_col": "binding_score_composite_v7",
            "traj_prod_early_stop_enabled": True,
        },
    )
    _write_json(
        residual_spec,
        {
            "summary": {
                "family": "gpcr",
                "prototype_variant": "gpcr_core_decoy_intrusion_v1",
            }
        },
    )

    payload = mod.build_payload(
        out_dir=tmp_path / "candidate",
        spec_json=residual_spec,
        base_profile_json=base_profile,
        tag_suffix="rolloutfastpath",
        variant="gpcr_core_decoy_intrusion_v1",
        mode="apply",
        traj_prod_early_stop_enabled=False,
    )

    profile = json.loads(Path(payload["profile_json"]).read_text(encoding="utf-8"))
    assert profile["traj_prod_early_stop_enabled"] is False


def test_build_payload_can_attach_fixed_score_reference_scaling(tmp_path: Path) -> None:
    base_profile = tmp_path / "config" / "base_gpcr.json"
    residual_spec = tmp_path / "runs" / "gpcr_residual_prototype_spec_core_decoy_intrusion_v1_current.json"
    stats_json = tmp_path / "runs" / "gpcr_score_reference_stats_current.json"
    _write_json(base_profile, {"ranking_score_col": "binding_score_composite_v7"})
    _write_json(
        residual_spec,
        {
            "summary": {
                "family": "gpcr",
                "prototype_variant": "gpcr_core_decoy_intrusion_v1",
            }
        },
    )
    _write_json(
        stats_json,
        {
            "summary": {"scope": "gpcr_fit_reference"},
            "features": {"binding_score_composite_v7": {"mean": -1.5, "std": 0.2}},
        },
    )

    payload = mod.build_payload(
        out_dir=tmp_path / "candidate",
        spec_json=residual_spec,
        base_profile_json=base_profile,
        tag_suffix="fixedref",
        variant="gpcr_core_decoy_intrusion_v1",
        mode="apply",
        score_reference_scaling_mode="fixed_family_reference",
        score_reference_stats_json=stats_json,
    )

    profile = json.loads(Path(payload["profile_json"]).read_text(encoding="utf-8"))
    set_spec = json.loads(Path(payload["set_spec_json"]).read_text(encoding="utf-8"))

    assert profile["score_reference_scaling_mode"] == "fixed_family_reference"
    assert profile["score_reference_stats_json"] == str(stats_json.resolve())
    assert profile["score_reference_scaling_claim_allowed"] is False
    governance = set_spec["global_governance"]["score_reference_scaling"]
    assert governance["mode"] == "fixed_family_reference"
    assert governance["stats_json"] == str(stats_json.resolve())
    assert governance["claim_safe_assertion_allowed"] is False


def test_build_payload_supports_mismatch_contact_rescore_as_comparison_only_guarded_candidate(tmp_path: Path) -> None:
    base_profile = tmp_path / "config" / "base_gpcr.json"
    residual_spec = tmp_path / "runs" / "gpcr_residual_prototype_spec_mismatch_contact.json"
    out_dir = tmp_path / "candidate"
    _write_json(base_profile, {"ranking_score_col": "binding_score_composite_v7"})
    _write_json(
        residual_spec,
        {
            "summary": {
                "family": "gpcr",
                "prototype_variant": "gpcr_core_mismatch_contact_rescore_v1",
            },
            "prototype": {
                "constraints": {
                    "comparison_only_candidate": True,
                    "router_promotion_allowed": False,
                    "claim_safe_assertion_allowed": False,
                },
                "tuning": {
                    "variant": "gpcr_core_mismatch_contact_rescore_v1",
                    "failure_tags": [
                        "donor_prior_decoy_intrusion",
                        "weak_contact_prior_mismatch",
                        "affinity_hint_md_support_mismatch",
                        "no_existing_score_column_recovers_gate",
                    ],
                },
            },
        },
    )

    payload = mod.build_payload(
        out_dir=out_dir,
        spec_json=residual_spec,
        base_profile_json=base_profile,
        tag_suffix="mismatchcontact",
        variant="gpcr_core_mismatch_contact_rescore_v1",
        mode="apply",
    )

    profile = json.loads(Path(payload["profile_json"]).read_text(encoding="utf-8"))
    set_spec = json.loads(Path(payload["set_spec_json"]).read_text(encoding="utf-8"))

    assert payload["candidate_kind"] == "gpcr_core_mismatch_contact_rescore_100k"
    assert payload["residual_prototype_mode"] == "apply"
    assert profile["residual_prototype_candidate"] == "gpcr_core_mismatch_contact_rescore_v1"
    assert profile["ranking_score_col"] == "binding_score_composite_v7_residual_active"
    assert profile["router_promotion_allowed"] is False
    assert profile["target_specific_candidate"] is False
    assert profile["claim_safe_assertion_allowed"] is False
    assert "comparison candidate" in profile["residual_prototype_notes"].lower()
    assert "not a claim-safe assertion" in profile["residual_prototype_notes"].lower()
    assert set_spec["global_governance"]["prototype_variant"] == "gpcr_core_mismatch_contact_rescore_v1"
    assert set_spec["global_governance"]["comparison_candidate_role"] == "guarded_apply_candidate"
    assert set_spec["global_governance"]["router_promotion_allowed"] is False
    assert set_spec["global_governance"]["apply_mode_claim_allowed"] is False
    assert set_spec["global_governance"]["claim_safe_assertion_allowed"] is False
    assert set_spec["global_governance"]["broad_gpcr_claim_allowed"] is False
    assert set_spec["sets"][0]["claim_role"] == "comparison_candidate"
    assert "not a claim" in set_spec["sets"][0]["preregistered_claim"].lower()


def test_structure_support_gated_candidate_stays_reject_shadow_until_full_100k_gate_green(tmp_path: Path) -> None:
    base_profile = tmp_path / "config" / "base_gpcr.json"
    residual_spec = tmp_path / "runs" / "gpcr_residual_prototype_spec_structure_support.json"
    out_dir = tmp_path / "candidate"
    _write_json(base_profile, {"ranking_score_col": "binding_score_composite_v7"})
    _write_json(
        residual_spec,
        {
            "summary": {
                "family": "gpcr",
                "prototype_variant": "gpcr_core_mismatch_contact_rescore_v1",
            },
            "prototype": {
                "constraints": {
                    "comparison_only_candidate": True,
                    "structure_support_gate": {
                        "enabled": True,
                        "required_before_claim": True,
                        "full_100k_gate_green": False,
                    },
                    "router_promotion_allowed": False,
                    "claim_safe_assertion_allowed": False,
                },
                "tuning": {
                    "variant": "gpcr_core_mismatch_contact_rescore_v1",
                    "require_no_existing_score_recovery_gate": True,
                },
            },
        },
    )

    payload = mod.build_payload(
        out_dir=out_dir,
        spec_json=residual_spec,
        base_profile_json=base_profile,
        tag_suffix="structureguard",
        variant="gpcr_core_mismatch_contact_rescore_v1",
        mode="apply",
    )

    profile = json.loads(Path(payload["profile_json"]).read_text(encoding="utf-8"))
    set_spec = json.loads(Path(payload["set_spec_json"]).read_text(encoding="utf-8"))
    governance = set_spec["global_governance"]

    assert profile["evidence_role"] == "reject_shadow_evidence"
    assert profile["structure_support_gate"]["enabled"] is True
    assert profile["structure_support_gate"]["full_100k_gate_green"] is False
    assert profile["claim_text_locked_until_full_100k_gate_green"] is True
    assert profile["claim_safe_assertion_allowed"] is False
    assert governance["evidence_role"] == "reject_shadow_evidence"
    assert governance["structure_support_gate"]["required_before_claim"] is True
    assert governance["claim_text_locked_until_full_100k_gate_green"] is True
    assert governance["claim_safe_assertion_allowed"] is False
    assert governance["apply_mode_claim_allowed"] is False
    assert set_spec["sets"][0]["claim_role"] == "comparison_candidate"
    assert set_spec["sets"][0]["preregistered_claim"].startswith("Not a claim:")


def test_build_payload_supports_structure_support_rescore_claim_locked_candidate(tmp_path: Path) -> None:
    base_profile = tmp_path / "config" / "base_gpcr.json"
    residual_spec = tmp_path / "runs" / "gpcr_residual_prototype_spec_structure_support_rescore.json"
    out_dir = tmp_path / "candidate"
    _write_json(base_profile, {"ranking_score_col": "binding_score_composite_v7"})
    _write_json(
        residual_spec,
        {
            "summary": {
                "family": "gpcr",
                "prototype_variant": "gpcr_core_structure_support_rescore_v1",
            },
            "prototype": {
                "constraints": {
                    "comparison_only_candidate": True,
                    "structure_support_gate": {
                        "enabled": True,
                        "required_before_claim": True,
                        "full_100k_gate_green": False,
                    },
                    "router_promotion_allowed": False,
                    "claim_safe_assertion_allowed": False,
                },
                "tuning": {
                    "variant": "gpcr_core_structure_support_rescore_v1",
                },
            },
        },
    )

    payload = mod.build_payload(
        out_dir=out_dir,
        spec_json=residual_spec,
        base_profile_json=base_profile,
        tag_suffix="structuresupport",
        variant="gpcr_core_structure_support_rescore_v1",
        mode="apply",
    )

    profile = json.loads(Path(payload["profile_json"]).read_text(encoding="utf-8"))
    set_spec = json.loads(Path(payload["set_spec_json"]).read_text(encoding="utf-8"))
    governance = set_spec["global_governance"]

    assert payload["candidate_kind"] == "gpcr_core_structure_support_rescore_100k"
    assert profile["residual_prototype_candidate"] == "gpcr_core_structure_support_rescore_v1"
    assert profile["evidence_role"] == "reject_shadow_evidence"
    assert profile["claim_text_locked_until_full_100k_gate_green"] is True
    assert governance["prototype_variant"] == "gpcr_core_structure_support_rescore_v1"
    assert governance["comparison_candidate_role"] == "guarded_apply_candidate"
    assert governance["claim_text_locked_until_full_100k_gate_green"] is True
    assert governance["apply_mode_claim_allowed"] is False
    assert set_spec["sets"][0]["claim_role"] == "comparison_candidate"
