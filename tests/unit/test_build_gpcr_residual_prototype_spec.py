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
