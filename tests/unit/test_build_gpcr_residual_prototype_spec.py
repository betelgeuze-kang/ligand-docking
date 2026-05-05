from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_build_gpcr_residual_prototype_spec(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype.json"
    out_csv = tmp_path / "prototype.csv"
    out_md = tmp_path / "prototype.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["prototype_mode"] == "shadow_only"
    assert payload["summary"]["prototype_status"] == "shadow_runtime_ready"
    assert payload["prototype"]["constraints"]["preserve_top2_binders"] is True
    assert any(row["feature_name"] == "mean_min_distance_A" for row in payload["feature_rows"])


def test_build_gpcr_residual_prototype_spec_narrow_v2(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_v2.json"
    out_csv = tmp_path / "prototype_v2.csv"
    out_md = tmp_path / "prototype_v2.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "narrow_v2",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["prototype_variant"] == "narrow_v2"
    assert payload["prototype"]["constraints"]["max_abs_delta_score"] == 0.75
    assert payload["prototype"]["tuning"]["require_distance_above_z"] == 0.35


def test_build_gpcr_residual_prototype_spec_chembl50_v3(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_v3.json"
    out_csv = tmp_path / "prototype_v3.csv"
    out_md = tmp_path / "prototype_v3.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "chembl50_v3",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["prototype_variant"] == "chembl50_v3"
    assert payload["prototype"]["constraints"]["max_abs_delta_score"] == 0.5
    assert payload["prototype"]["tuning"]["chembl50_abstain_on_borderline_support"] is True


def test_build_gpcr_residual_prototype_spec_chembl50_v4(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_v4.json"
    out_csv = tmp_path / "prototype_v4.csv"
    out_md = tmp_path / "prototype_v4.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "chembl50_v4",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["prototype_variant"] == "chembl50_v4"
    assert payload["prototype"]["constraints"]["max_abs_delta_score"] == 0.35
    assert payload["prototype"]["tuning"]["core_guard_abstain_on_small_margin"] is True


def test_build_gpcr_residual_prototype_spec_core_decoy_intrusion_v1(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_intrusion.json"
    out_csv = tmp_path / "prototype_intrusion.csv"
    out_md = tmp_path / "prototype_intrusion.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_core_decoy_intrusion_v1",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    tuning = payload["prototype"]["tuning"]

    assert payload["summary"]["prototype_variant"] == "gpcr_core_decoy_intrusion_v1"
    assert payload["prototype"]["constraints"]["max_abs_delta_score"] == 1.0
    assert tuning["variant"] == "gpcr_core_decoy_intrusion_v1"
    assert tuning["intrusion_weight_low_h_donors"] > 0.0
    assert tuning["min_intrusion_contact_support_for_delta"] == 1.0
    assert any(
        row["feature_name"] == "intrusion_contact_support"
        for row in payload["feature_rows"]
    )
    assert "compact_hydrophobic_low_affinity_decoy_intrusion" in payload["prototype"]["interactions"]


def test_build_gpcr_residual_prototype_spec_core_linear_rescore_v1(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_linear.json"
    out_csv = tmp_path / "prototype_linear.csv"
    out_md = tmp_path / "prototype_linear.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_core_linear_rescore_v1",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    linear = payload["prototype"]["linear_rescore"]

    assert payload["summary"]["prototype_variant"] == "gpcr_core_linear_rescore_v1"
    assert payload["prototype"]["constraints"]["linear_rescore_candidate"] is True
    assert payload["prototype"]["tuning"]["core_replay_pr_auc"] >= 0.55
    assert linear["enabled"] is True
    assert linear["combine_mode"] == "replace"
    assert any(term["feature"] == "z_ligand_logp" for term in linear["terms"])
    assert any(row["feature_name"] == "z_ligand_affinity_hint" for row in payload["feature_rows"])


def test_build_gpcr_residual_prototype_spec_core_family_balanced_rescore_v1_is_claim_locked(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_family_balanced.json"
    out_csv = tmp_path / "prototype_family_balanced.csv"
    out_md = tmp_path / "prototype_family_balanced.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_core_family_balanced_rescore_v1",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    constraints = payload["prototype"]["constraints"]
    linear = payload["prototype"]["linear_rescore"]
    term_features = {term["feature"] for term in linear["terms"]}

    assert payload["summary"]["prototype_variant"] == "gpcr_core_family_balanced_rescore_v1"
    assert constraints["comparison_only_candidate"] is True
    assert constraints["claim_locked_candidate"] is True
    assert constraints["router_promotion_allowed"] is False
    assert constraints["platform_promotion_allowed"] is False
    assert constraints["claim_safe_assertion_allowed"] is False
    assert constraints["broad_gpcr_claim_allowed"] is False
    assert linear["enabled"] is True
    assert linear["combine_mode"] == "replace"
    assert {"z_ligand_h_donors", "z_contact_fraction", "z_mean_min_distance_A"} <= term_features
    assert all("target" not in feature.lower() for feature in term_features)
    assert "no_router_platform_or_claim_promotion" in payload["prototype"]["interactions"]
    assert any(row["feature_name"] == "family_balanced_pose_energy_support" for row in payload["feature_rows"])


def test_build_gpcr_residual_prototype_spec_core_family_anchor_rescore_v2_is_claim_locked(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_family_anchor_v2.json"
    out_csv = tmp_path / "prototype_family_anchor_v2.csv"
    out_md = tmp_path / "prototype_family_anchor_v2.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_core_family_anchor_rescore_v2",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    constraints = payload["prototype"]["constraints"]
    linear = payload["prototype"]["linear_rescore"]
    term_features = {term["feature"] for term in linear["terms"]}
    term_weights = {term["feature"]: term["weight"] for term in linear["terms"]}
    feature_rows = {row["feature_name"]: row for row in payload["feature_rows"]}

    assert payload["summary"]["prototype_variant"] == "gpcr_core_family_anchor_rescore_v2"
    assert constraints["comparison_only_candidate"] is True
    assert constraints["claim_locked_candidate"] is True
    assert constraints["target_identity_feature_allowed"] is False
    assert constraints["scorer_apply_allowed"] is False
    assert constraints["claim_safe_assertion_allowed"] is False
    assert linear["enabled"] is True
    assert linear["combine_mode"] == "replace"
    assert {
        "binding_score_composite_v7_prior_active",
        "gpcr_conserved_anchor_proxy",
        "gpcr_basic_amine_proxy",
        "prior_overreward_without_anchor",
        "gpcr_pose_chemistry_hard_decoy_pressure",
    } <= term_features
    assert term_weights["binding_score_composite_v7_prior_active"] == 1.0
    assert term_weights["gpcr_basic_amine_proxy"] == -4.0
    assert term_weights["gpcr_conserved_anchor_proxy"] == -0.1
    assert term_weights["prior_overreward_without_anchor"] == 0.2
    assert term_weights["gpcr_pose_chemistry_hard_decoy_pressure"] == 3.0
    assert "pose_physics_support" in feature_rows
    assert "gpcr_smiles_present_proxy" in feature_rows
    assert "target_internal_pairwise_pressure" in feature_rows
    assert "target_internal_pairwise_replay_diagnostic" in feature_rows
    assert "gpcr_anchor_chemistry_mismatch_pressure" in feature_rows
    assert all("target" not in feature.lower() or feature == "target_internal_pairwise_pressure" for feature in term_features)
    assert feature_rows["target_internal_pairwise_replay_diagnostic"]["direction"] == "diagnostic_only"
    assert "target_internal_pairwise_replay_diagnostic" not in term_features
    assert "gpcr_anchor_chemistry_mismatch_pressure" in term_features
    assert term_weights["gpcr_anchor_chemistry_mismatch_pressure"] == 1.4
    assert not any(
        blocked in "gpcr_anchor_chemistry_mismatch_pressure"
        for blocked in ["target", "label", "rank", "reference", "binding", "ligand_id", "decoy"]
    )
    assert feature_rows["gpcr_conserved_anchor_proxy"]["role"] == "conserved_anchor_proxy"
    assert feature_rows["gpcr_basic_amine_proxy"]["role"] == "conserved_anchor_chemistry_proxy"
    assert feature_rows["gpcr_smiles_present_proxy"]["role"] == "chemistry_availability_gate"
    assert "no_target_identity_features" in payload["prototype"]["interactions"]


def test_build_gpcr_residual_prototype_spec_core_family_anchor_ci_stability_v3_is_diagnostic_only(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_family_anchor_ci_v3.json"
    out_csv = tmp_path / "prototype_family_anchor_ci_v3.csv"
    out_md = tmp_path / "prototype_family_anchor_ci_v3.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_core_family_anchor_ci_stability_v3",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    constraints = payload["prototype"]["constraints"]
    tuning = payload["prototype"]["tuning"]
    linear = payload["prototype"]["linear_rescore"]
    term_features = {term["feature"] for term in linear.get("terms", [])}
    feature_rows = {row["feature_name"]: row for row in payload["feature_rows"]}

    assert payload["summary"]["prototype_variant"] == "gpcr_core_family_anchor_ci_stability_v3"
    assert constraints["claim_locked_candidate"] is True
    assert constraints["diagnostic_only_candidate"] is True
    assert constraints["scorer_apply_allowed"] is False
    assert constraints["claim_safe_assertion_allowed"] is False
    assert constraints["target_identity_feature_allowed"] is False
    assert constraints["ci_low_threshold"] == 0.45
    assert linear["enabled"] is False
    assert tuning["candidate_source"] == "family_anchor_v2_shadow_ci_low_blocker"
    assert tuning["v2_shadow_pr_auc"] == 0.5767474245351905
    assert tuning["v2_shadow_pr_auc_ci_low"] == 0.21066694653866244
    assert tuning["v2_shadow_pr_auc_ci_low_gap_to_threshold"] == 0.23933305346133758
    assert "bootstrap_ci_low_stability_probe" in feature_rows
    assert "acidic_anchor_overcontact_pressure_probe" in feature_rows
    assert feature_rows["bootstrap_ci_low_stability_probe"]["direction"] == "diagnostic_only"
    assert feature_rows["acidic_anchor_overcontact_pressure_probe"]["direction"] == "diagnostic_only"
    assert "acidic_anchor_overcontact_pressure_probe" not in term_features
    assert "acidic_anchor_overcontact_pressure_probe" in payload["prototype"]["interactions"]
    assert "ci_low_stability_metadata_required" in payload["prototype"]["interactions"]
    assert "family_anchor_v2_score_preserved_as_baseline" in payload["prototype"]["interactions"]


def test_build_gpcr_residual_prototype_spec_acidic_anchor_overcontact_prior_gate_v4_is_claim_locked(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_anchor_overcontact_v4.json"
    out_csv = tmp_path / "prototype_anchor_overcontact_v4.csv"
    out_md = tmp_path / "prototype_anchor_overcontact_v4.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    constraints = payload["prototype"]["constraints"]
    tuning = payload["prototype"]["tuning"]
    linear = payload["prototype"]["linear_rescore"]
    term_features = {term["feature"] for term in linear.get("terms", [])}
    feature_rows = {row["feature_name"]: row for row in payload["feature_rows"]}

    assert payload["summary"]["prototype_variant"] == "gpcr_core_acidic_anchor_overcontact_prior_gate_v4"
    assert constraints["claim_locked_candidate"] is True
    assert constraints["shadow_only_candidate"] is True
    assert constraints["diagnostic_only_candidate"] is True
    assert constraints["scorer_apply_allowed"] is False
    assert constraints["claim_safe_assertion_allowed"] is False
    assert constraints["target_identity_feature_allowed"] is False
    assert constraints["label_feature_allowed"] is False
    assert constraints["rank_feature_allowed"] is False
    assert constraints["ligand_id_feature_allowed"] is False
    assert constraints["reference_binding_value_allowed"] is False
    assert constraints["threshold_relaxation_allowed"] is False
    assert linear["enabled"] is True
    assert tuning["candidate_source"] == "post_v3_acidic_anchor_overcontact_prior_gate"
    assert tuning["threshold_relaxation_allowed"] is False
    assert "gpcr_acidic_anchor_overcontact_prior_gate" in feature_rows
    assert "gpcr_acidic_anchor_overcontact_prior_gate" in term_features
    assert "no_target_identity_labels_ranks_ligand_ids_or_reference_values" in payload["prototype"]["interactions"]
    assert "shadow_only_active_claim_disabled" in payload["prototype"]["interactions"]


def test_build_gpcr_residual_prototype_spec_fixed_reference_live_v5_is_claim_locked_and_records_collapse(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_fixed_reference_live_v5.json"
    out_csv = tmp_path / "prototype_fixed_reference_live_v5.csv"
    out_md = tmp_path / "prototype_fixed_reference_live_v5.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_core_fixed_reference_live_shadow_v5",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    constraints = payload["prototype"]["constraints"]
    tuning = payload["prototype"]["tuning"]
    linear = payload["prototype"]["linear_rescore"]
    term_features = {term["feature"] for term in linear.get("terms", [])}
    feature_rows = {row["feature_name"]: row for row in payload["feature_rows"]}

    assert payload["summary"]["prototype_variant"] == "gpcr_core_fixed_reference_live_shadow_v5"
    assert constraints["claim_locked_candidate"] is True
    assert constraints["shadow_only_candidate"] is True
    assert constraints["diagnostic_only_candidate"] is True
    assert constraints["reference_scaling_mode"] == "fixed_family_reference"
    assert constraints["scorer_apply_allowed"] is False
    assert constraints["threshold_relaxation_allowed"] is False
    assert constraints["fake_pass_allowed"] is False
    assert constraints["target_identity_feature_allowed"] is False
    assert constraints["label_feature_allowed"] is False
    assert constraints["rank_feature_allowed"] is False
    assert constraints["ligand_id_feature_allowed"] is False
    assert constraints["reference_binding_value_allowed"] is False
    assert constraints["fixed_reference_v2_formula_replay_top20_hit_rate"] == 0.0
    assert tuning["rejected_predecessor_variant"] == "gpcr_core_acidic_anchor_overcontact_prior_gate_v4"
    assert tuning["fixed_reference_replay_feature_collapse"]["gpcr_acidic_anchor_overcontact_prior_gate_nonzero"] == 0
    assert tuning["fixed_reference_replay_feature_collapse"]["fixed_reference_prior_weakness_pressure_nonzero"] == 17768
    assert tuning["fixed_reference_v2_formula_replay"]["pr_auc_approx"] == 0.0076
    assert tuning["fixed_reference_v2_formula_replay"]["interpretation"] == "do_not_port_v2_or_v4_weights_under_fixed_reference_scaling"
    assert linear["enabled"] is True
    assert term_features == {
        "binding_score_composite_v7_prior_active",
        "fixed_reference_live_overreward_pressure",
    }
    assert "fixed_reference_feature_collapse_probe" in feature_rows
    assert "fixed_reference_prior_weakness_pressure" in feature_rows
    assert feature_rows["fixed_reference_feature_collapse_probe"]["direction"] == "diagnostic_only"
    assert feature_rows["fixed_reference_prior_weakness_pressure"]["direction"] == "target_agnostic_prior_weakness_alias"
    assert "record_fixed_reference_feature_collapse" in payload["prototype"]["interactions"]
    assert "use_only_fixed_reference_live_pressures" in payload["prototype"]["interactions"]


def test_build_gpcr_residual_prototype_spec_class_a_motif_shadow_v6_is_claim_locked(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_class_a_motif_v6.json"
    out_csv = tmp_path / "prototype_class_a_motif_v6.csv"
    out_md = tmp_path / "prototype_class_a_motif_v6.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_core_class_a_motif_shadow_v6",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    constraints = payload["prototype"]["constraints"]
    tuning = payload["prototype"]["tuning"]
    linear = payload["prototype"]["linear_rescore"]
    term_features = {term["feature"] for term in linear.get("terms", [])}
    feature_rows = {row["feature_name"]: row for row in payload["feature_rows"]}

    assert payload["summary"]["prototype_variant"] == "gpcr_core_class_a_motif_shadow_v6"
    assert tuning["scope"] == "class_a_aminergic_opioid_like_orthosteric_sublane"
    assert constraints["class_a_aminergic_opioid_orthosteric_sublane_candidate"] is True
    assert constraints["broad_gpcr_claim_allowed"] is False
    assert constraints["active_score_locked_to_base"] is True
    assert constraints["scorer_apply_allowed"] is False
    assert constraints["target_identity_feature_allowed"] is False
    assert constraints["label_feature_allowed"] is False
    assert constraints["rank_feature_allowed"] is False
    assert constraints["ligand_id_feature_allowed"] is False
    assert constraints["reference_binding_value_allowed"] is False
    assert constraints["best_baseline_variant"] == "gpcr_core_family_anchor_rescore_v2"
    assert constraints["baseline_role"] == "v2_donor_baseline"
    assert constraints["tombstone_reject_variants"] == [
        "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
        "gpcr_core_fixed_reference_live_shadow_v5",
    ]
    assert constraints["forbidden_live_feature_families"] == [
        "target",
        "is_binder",
        "rank",
        "ligand_id",
        "reference_binding",
    ]
    assert linear["enabled"] is True
    assert term_features == {
        "binding_score_composite_v7_prior_active",
        "class_a_orthosteric_motif_support_proxy",
        "class_a_prior_overreward_invalid_overanchor_pressure",
    }
    assert "class_a_aminergic_opioid_orthosteric_sublane_scope" in feature_rows
    assert "family_anchor_v2_donor_baseline_lock" in feature_rows
    assert "v4_v5_tombstone_reject_preservation" in feature_rows
    assert "active_score_locked_to_base_even_in_apply_mode" in payload["prototype"]["interactions"]
    assert "no_target_is_binder_rank_ligand_id_or_reference_binding_features" in payload["prototype"]["interactions"]


def test_build_gpcr_residual_prototype_spec_class_a_anchor_geometry_shadow_v7_is_claim_locked(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_class_a_anchor_geometry_v7.json"
    out_csv = tmp_path / "prototype_class_a_anchor_geometry_v7.csv"
    out_md = tmp_path / "prototype_class_a_anchor_geometry_v7.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_core_class_a_anchor_geometry_shadow_v7",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    constraints = payload["prototype"]["constraints"]
    tuning = payload["prototype"]["tuning"]
    linear = payload["prototype"]["linear_rescore"]
    term_features = {term["feature"] for term in linear.get("terms", [])}
    feature_rows = {row["feature_name"]: row for row in payload["feature_rows"]}

    assert payload["summary"]["prototype_variant"] == "gpcr_core_class_a_anchor_geometry_shadow_v7"
    assert tuning["scope"] == "class_a_aminergic_opioid_like_orthosteric_sublane"
    assert tuning["candidate_source"] == "post_v6_reject_class_a_anchor_geometry_shadow_design"
    assert constraints["class_a_aminergic_opioid_orthosteric_sublane_candidate"] is True
    assert constraints["score_only_candidate"] is True
    assert constraints["shadow_only_candidate"] is True
    assert constraints["active_score_locked_to_base"] is True
    assert constraints["scorer_apply_allowed"] is False
    assert constraints["broad_gpcr_claim_allowed"] is False
    assert constraints["threshold_relaxation_allowed"] is False
    assert constraints["fake_pass_allowed"] is False
    assert constraints["target_identity_feature_allowed"] is False
    assert constraints["label_feature_allowed"] is False
    assert constraints["rank_feature_allowed"] is False
    assert constraints["ligand_id_feature_allowed"] is False
    assert constraints["reference_binding_value_allowed"] is False
    assert constraints["best_baseline_variant"] == "gpcr_core_family_anchor_rescore_v2"
    assert constraints["baseline_role"] == "v2_donor_baseline"
    assert constraints["rejected_predecessor_variant"] == "gpcr_core_class_a_motif_shadow_v6"
    assert constraints["tombstone_reject_variants"] == [
        "gpcr_core_acidic_anchor_overcontact_prior_gate_v4",
        "gpcr_core_fixed_reference_live_shadow_v5",
        "gpcr_core_class_a_motif_shadow_v6",
    ]
    assert constraints["forbidden_live_feature_families"] == [
        "target",
        "is_binder",
        "rank",
        "ligand_id",
        "reference_binding",
        "threshold_relaxation",
        "fake_pass",
    ]
    assert linear["enabled"] is True
    assert term_features == {
        "binding_score_composite_v7_prior_active",
        "class_a_charge_complemented_anchor_geometry_proxy",
        "class_a_orthosteric_occupancy_proxy",
        "class_a_pose_survival_support_proxy",
        "class_a_invalid_anchor_prior_pressure_v7",
    }
    assert not any(
        blocked in feature.lower()
        for feature in term_features
        for blocked in ["target", "is_binder", "rank", "ligand_id", "reference_binding", "threshold_relaxation", "fake_pass"]
    )
    assert "class_a_charge_complemented_anchor_geometry_proxy" in feature_rows
    assert "class_a_orthosteric_occupancy_proxy" in feature_rows
    assert "class_a_pose_survival_support_proxy" in feature_rows
    assert "class_a_invalid_anchor_prior_pressure_v7" in feature_rows
    assert "family_anchor_v2_donor_baseline_lock" in feature_rows
    assert "v4_v5_v6_reject_preservation" in feature_rows
    assert "active_score_locked_to_base_even_in_apply_mode" in payload["prototype"]["interactions"]
    assert "v6_reject_preserved_not_promoted" in payload["prototype"]["interactions"]


def test_build_gpcr_residual_prototype_spec_adrb2_pharmacophore_v1(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_pharmacophore.json"
    out_csv = tmp_path / "prototype_pharmacophore.csv"
    out_md = tmp_path / "prototype_pharmacophore.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_adrb2_beta_blocker_pharmacophore_v1",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    tuning = payload["prototype"]["tuning"]

    assert payload["summary"]["prototype_variant"] == "gpcr_adrb2_beta_blocker_pharmacophore_v1"
    assert payload["prototype"]["constraints"]["target_specific_pharmacophore_candidate"] is True
    assert tuning["variant"] == "gpcr_adrb2_beta_blocker_pharmacophore_v1"
    assert tuning["pharmacophore_reward_score"] == 8.0
    assert "target_specific_adrb2_beta_blocker_pharmacophore_shadow_only" in payload["prototype"]["interactions"]
    assert any(
        row["feature_name"] == "aryloxypropanolamine_smarts_match"
        for row in payload["feature_rows"]
    )


def test_build_gpcr_residual_prototype_spec_direct_atom_anchor_window_v8_is_claim_locked(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_direct_atom_window_v8.json"
    out_csv = tmp_path / "prototype_direct_atom_window_v8.csv"
    out_md = tmp_path / "prototype_direct_atom_window_v8.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_core_direct_atom_anchor_window_shadow_v8",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    constraints = payload["prototype"]["constraints"]
    tuning = payload["prototype"]["tuning"]
    linear = payload["prototype"]["linear_rescore"]
    term_features = {term["feature"] for term in linear["terms"]}
    feature_rows = {row["feature_name"]: row for row in payload["feature_rows"]}

    assert payload["summary"]["prototype_variant"] == "gpcr_core_direct_atom_anchor_window_shadow_v8"
    assert constraints["claim_locked_candidate"] is True
    assert constraints["shadow_only_candidate"] is True
    assert constraints["score_only_candidate"] is True
    assert constraints["active_score_locked_to_base"] is True
    assert constraints["requires_precomputed_atom_window_features"] is True
    assert constraints["missing_atom_window_features_are_not_negative_evidence"] is True
    assert constraints["scorer_apply_allowed"] is False
    assert constraints["broad_gpcr_claim_allowed"] is False
    assert constraints["target_identity_feature_allowed"] is False
    assert constraints["label_feature_allowed"] is False
    assert constraints["rank_feature_allowed"] is False
    assert constraints["ligand_id_feature_allowed"] is False
    assert constraints["reference_binding_value_allowed"] is False
    assert tuning["variant"] == "gpcr_core_direct_atom_anchor_window_shadow_v8"
    assert tuning["rejected_predecessor_variant"] == "gpcr_core_class_a_anchor_geometry_shadow_v7"
    assert "class_a_direct_atom_window_anchor_geometry_proxy" in term_features
    assert "class_a_hydrophobic_overcontact_pressure_v8" in term_features
    assert feature_rows["class_a_atom_anchor_feature_available_proxy"]["direction"] == (
        "diagnostic_only_no_missing_feature_penalty"
    )
    assert "direct_atom_window_features_not_stage3_proxy_recombination" in payload["prototype"]["interactions"]


def test_build_gpcr_residual_prototype_spec_atom_window_excess_polar_v9_is_claim_locked(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_atom_window_excess_polar_v9.json"
    out_csv = tmp_path / "prototype_atom_window_excess_polar_v9.csv"
    out_md = tmp_path / "prototype_atom_window_excess_polar_v9.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_core_atom_window_excess_polar_shadow_v9",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    constraints = payload["prototype"]["constraints"]
    tuning = payload["prototype"]["tuning"]
    term_features = {term["feature"] for term in payload["prototype"]["linear_rescore"]["terms"]}

    assert payload["summary"]["prototype_variant"] == "gpcr_core_atom_window_excess_polar_shadow_v9"
    assert constraints["claim_locked_candidate"] is True
    assert constraints["score_only_candidate"] is True
    assert constraints["active_score_locked_to_base"] is True
    assert constraints["requires_precomputed_atom_window_features"] is True
    assert constraints["rejected_predecessor_variant"] == "gpcr_core_direct_atom_anchor_window_shadow_v8"
    assert constraints["scorer_apply_allowed"] is False
    assert constraints["broad_gpcr_claim_allowed"] is False
    assert tuning["variant"] == "gpcr_core_atom_window_excess_polar_shadow_v9"
    assert "class_a_excess_polar_anchor_pressure_v9" in term_features
    assert "class_a_compact_amine_window_support_v9" in term_features


def test_build_gpcr_residual_prototype_spec_cationic_pose_distortion_v10_is_claim_locked(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_cationic_pose_distortion_v10.json"
    out_csv = tmp_path / "prototype_cationic_pose_distortion_v10.csv"
    out_md = tmp_path / "prototype_cationic_pose_distortion_v10.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_core_cationic_pose_distortion_shadow_v10",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    constraints = payload["prototype"]["constraints"]
    tuning = payload["prototype"]["tuning"]
    linear = payload["prototype"]["linear_rescore"]
    term_features = {term["feature"] for term in linear["terms"]}
    term_weights = {term["feature"]: term["weight"] for term in linear["terms"]}
    feature_rows = {row["feature_name"]: row for row in payload["feature_rows"]}

    assert payload["summary"]["prototype_variant"] == "gpcr_core_cationic_pose_distortion_shadow_v10"
    assert constraints["claim_locked_candidate"] is True
    assert constraints["shadow_only_candidate"] is True
    assert constraints["score_only_candidate"] is True
    assert constraints["selected_repaired_slice_candidate"] is True
    assert constraints["active_score_locked_to_base"] is True
    assert constraints["requires_precomputed_drd2_repair_slice_features"] is True
    assert constraints["requires_precomputed_cationic_center_features"] is True
    assert constraints["scorer_apply_allowed"] is False
    assert constraints["claim_safe_assertion_allowed"] is False
    assert constraints["broad_gpcr_claim_allowed"] is False
    assert constraints["target_identity_feature_allowed"] is False
    assert constraints["label_feature_allowed"] is False
    assert constraints["rank_feature_allowed"] is False
    assert constraints["ligand_id_feature_allowed"] is False
    assert constraints["reference_binding_value_allowed"] is False
    assert constraints["rejected_predecessor_variant"] == "gpcr_core_atom_window_excess_polar_shadow_v9"
    assert tuning["variant"] == "gpcr_core_cationic_pose_distortion_shadow_v10"
    assert tuning["bounded_envelope_positive_rank"] == 1
    assert tuning["bounded_envelope_decoys_above_positive_count"] == 0
    assert linear["enabled"] is True
    assert linear["combine_mode"] == "replace"
    assert term_features == {"base_score", "label_free_penalty_pressure", "label_free_support_pressure"}
    assert term_weights["base_score"] == 1.0
    assert term_weights["label_free_penalty_pressure"] == 6.0
    assert term_weights["label_free_support_pressure"] == -16.0
    assert "pose_distortion_pressure" in feature_rows
    assert "v8_v9_reject_preservation" in feature_rows
    assert not any(
        blocked in feature.lower()
        for feature in term_features
        for blocked in ["target", "is_binder", "rank", "ligand_id", "reference_binding", "threshold_relaxation", "fake_pass"]
    )
    assert "selected_repaired_drd2_slice_only_not_full_gpcr_claim" in payload["prototype"]["interactions"]
    assert "no_router_platform_or_claim_promotion" in payload["prototype"]["interactions"]


def test_build_gpcr_residual_prototype_spec_cationic_weakbase_rescue_v11_is_claim_locked(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_cationic_weakbase_v11.json"
    out_csv = tmp_path / "prototype_cationic_weakbase_v11.csv"
    out_md = tmp_path / "prototype_cationic_weakbase_v11.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_core_cationic_weakbase_rescue_shadow_v11",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    constraints = payload["prototype"]["constraints"]
    tuning = payload["prototype"]["tuning"]
    linear = payload["prototype"]["linear_rescore"]
    term_features = {term["feature"] for term in linear["terms"]}
    term_weights = {term["feature"]: term["weight"] for term in linear["terms"]}
    feature_rows = {row["feature_name"]: row for row in payload["feature_rows"]}

    assert payload["summary"]["prototype_variant"] == "gpcr_core_cationic_weakbase_rescue_shadow_v11"
    assert constraints["claim_locked_candidate"] is True
    assert constraints["score_only_candidate"] is True
    assert constraints["active_score_locked_to_base"] is True
    assert constraints["requires_weak_base_rescue_gate"] is True
    assert constraints["scorer_apply_allowed"] is False
    assert constraints["target_identity_feature_allowed"] is False
    assert constraints["label_feature_allowed"] is False
    assert constraints["rank_feature_allowed"] is False
    assert constraints["ligand_id_feature_allowed"] is False
    assert constraints["reference_binding_value_allowed"] is False
    assert tuning["variant"] == "gpcr_core_cationic_weakbase_rescue_shadow_v11"
    assert tuning["rejected_predecessor_variant"] == "gpcr_core_cationic_pose_distortion_shadow_v10"
    assert linear["enabled"] is True
    assert term_features == {"base_score", "label_free_penalty_pressure", "weak_base_rescue_support_pressure"}
    assert term_weights["label_free_penalty_pressure"] == 6.0
    assert term_weights["weak_base_rescue_support_pressure"] == -18.0
    assert "weak_base_rescue_support_pressure" in feature_rows
    assert "v10_selected_slice_rework_preservation" in feature_rows
    assert "weak_base_support_rescues_borderline_rows_not_already_strong_decoys" in payload["prototype"]["interactions"]


def test_build_gpcr_residual_prototype_spec_mismatch_contact_rescore_v1_is_guarded(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_mismatch_contact.json"
    out_csv = tmp_path / "prototype_mismatch_contact.csv"
    out_md = tmp_path / "prototype_mismatch_contact.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_core_mismatch_contact_rescore_v1",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    constraints = payload["prototype"]["constraints"]
    tuning = payload["prototype"]["tuning"]

    assert payload["summary"]["prototype_variant"] == "gpcr_core_mismatch_contact_rescore_v1"
    assert constraints["comparison_only_candidate"] is True
    assert constraints["structure_support_gate"] == {
        "enabled": True,
        "required_before_claim": True,
        "full_100k_gate_green": False,
    }
    assert constraints["router_promotion_allowed"] is False
    assert constraints["claim_safe_assertion_allowed"] is False
    assert tuning["variant"] == "gpcr_core_mismatch_contact_rescore_v1"
    assert tuning["failure_tags"] == [
        "donor_prior_decoy_intrusion",
        "weak_contact_prior_mismatch",
        "affinity_hint_md_support_mismatch",
        "no_existing_score_column_recovers_gate",
    ]
    assert tuning["require_no_existing_score_recovery_gate"] is True
    assert tuning["min_contact_mismatch_z_for_delta"] > 0.0
    assert tuning["affinity_md_support_mismatch_weight"] > 0.0
    assert "no_router_or_general_gpcr_family_promotion" in payload["prototype"]["interactions"]
    assert any(row["feature_name"] == "weak_contact_prior_mismatch" for row in payload["feature_rows"])
    assert any(row["feature_name"] == "affinity_hint_md_support_mismatch" for row in payload["feature_rows"])


def test_build_gpcr_residual_prototype_spec_structure_support_rescore_v1_is_claim_locked(tmp_path: Path) -> None:
    out_json = tmp_path / "prototype_structure_support.json"
    out_csv = tmp_path / "prototype_structure_support.csv"
    out_md = tmp_path / "prototype_structure_support.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_residual_prototype_spec.py"),
            "--variant",
            "gpcr_core_structure_support_rescore_v1",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    constraints = payload["prototype"]["constraints"]
    linear = payload["prototype"]["linear_rescore"]

    assert payload["summary"]["prototype_variant"] == "gpcr_core_structure_support_rescore_v1"
    assert constraints["comparison_only_candidate"] is True
    assert constraints["structure_support_gate"] == {
        "enabled": True,
        "required_before_claim": True,
        "full_100k_gate_green": False,
    }
    assert constraints["claim_safe_assertion_allowed"] is False
    assert linear["enabled"] is True
    assert linear["combine_mode"] == "replace"
    assert any(term["feature"] == "z_contact_fraction" for term in linear["terms"])
    assert any(term["feature"] == "z_stability_score" for term in linear["terms"])
    assert "structure_support_replay_only_until_full_100k_gate_green" in payload["prototype"]["interactions"]
