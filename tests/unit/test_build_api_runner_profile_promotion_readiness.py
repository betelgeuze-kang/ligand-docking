from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_api_runner_profile_promotion_readiness as mod


def _write_profile(root: Path, *, enabled: bool = False) -> None:
    profile = {
        "enabled": enabled,
        "profile_id": "example",
        "runner_script": "tools/run_ligand_backmapping_scoring.py",
        "arguments": [],
        "result_file_template": "{job_results_dir}/runner_result.json",
        "claim_boundary": "reviewed boundary",
    }
    path = root / "profiles" / "example.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile) + "\n", encoding="utf-8")


def _write_runner(root: Path) -> None:
    path = root / "tools" / "run_ligand_backmapping_scoring.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# runner\n", encoding="utf-8")


def _write_evidence(root: Path, *, ready: bool) -> None:
    evidence = {
        "profile_id": "example",
        "input_contract_reviewed": ready,
        "output_contract_reviewed": ready,
        "claim_boundary_reviewed": ready,
        "gate_policy_reviewed": ready,
        "fake_result_emission_forbidden": ready,
        "gate_policy_artifact": "runs/gate.json" if ready else "",
        "reviewer": "operator" if ready else "",
        "reviewed_at_utc": "2026-06-06T00:00:00Z" if ready else "",
    }
    path = root / "evidence" / "example.evidence.template.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence) + "\n", encoding="utf-8")


def test_api_runner_profile_promotion_readiness_blocks_unfilled_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_profile(tmp_path)
    _write_runner(tmp_path)
    _write_evidence(tmp_path, ready=False)

    payload = mod.build_api_runner_profile_promotion_readiness(
        profiles_dir=tmp_path / "profiles",
        evidence_dir=tmp_path / "evidence",
    )
    summary = payload["summary"]
    row = payload["rows"][0]

    assert summary["status"] == "blocked_api_runner_profile_promotion_readiness"
    assert summary["profile_count"] == 1
    assert summary["promotion_ready_count"] == 0
    assert summary["native_evidence_bundle_missing_profile_count"] == 0
    assert row["promotion_ready"] is False
    assert "input_contract_reviewed_not_true" in row["blockers"]
    assert "gate_policy_artifact_missing" in row["blockers"]
    assert summary["profile_enabled_by_this_tool"] is False
    assert summary["runner_executed"] is False
    assert summary["external_state_mutated"] is False


def test_api_runner_profile_promotion_readiness_accepts_enabled_profile_with_production_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    profile = {
        "enabled": True,
        "profile_id": "example",
        "runner_script": "tools/run_ligand_backmapping_scoring.py",
        "arguments": [],
        "result_file_template": "{job_results_dir}/runner_result.json",
        "claim_boundary": "reviewed boundary",
        "evidence_bundle_template": "{job_results_dir}/evidence_bundle.json",
        "production_readiness": {
            "evidence_artifact": "evidence/example.evidence.json",
        },
    }
    (tmp_path / "profiles" / "example.json").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "profiles" / "example.json").write_text(json.dumps(profile) + "\n", encoding="utf-8")
    (tmp_path / "tools" / "run_ligand_backmapping_scoring.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "tools" / "run_ligand_backmapping_scoring.py").write_text("# runner\n", encoding="utf-8")
    _write_evidence(tmp_path, ready=True)
    (tmp_path / "evidence" / "example.evidence.json").write_text(
        (tmp_path / "evidence" / "example.evidence.template.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    payload = mod.build_api_runner_profile_promotion_readiness(
        profiles_dir=tmp_path / "profiles",
        evidence_dir=tmp_path / "evidence",
    )

    summary = payload["summary"]
    assert summary["status"] == "api_runner_profile_promotion_ready"
    assert summary["native_evidence_bundle_required_profile_count"] == 1
    assert summary["native_evidence_bundle_missing_profile_count"] == 0
    assert summary["first_native_evidence_bundle_missing_profile_id"] == ""
    assert payload["rows"][0]["promotion_ready"] is True
    assert payload["rows"][0]["enabled"] is True
    assert payload["rows"][0]["evidence_bundle_template_declared"] is True
    assert payload["rows"][0]["requires_native_evidence_bundle"] is True


def test_api_runner_profile_promotion_readiness_ready_with_filled_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_profile(tmp_path)
    _write_runner(tmp_path)
    _write_evidence(tmp_path, ready=True)

    payload = mod.build_api_runner_profile_promotion_readiness(
        profiles_dir=tmp_path / "profiles",
        evidence_dir=tmp_path / "evidence",
    )

    assert payload["summary"]["status"] == "api_runner_profile_promotion_ready"
    assert payload["summary"]["promotion_ready_count"] == 1
    assert payload["summary"]["native_evidence_bundle_required_profile_count"] == 0
    assert payload["summary"]["native_evidence_bundle_missing_profile_count"] == 0
    assert payload["rows"][0]["promotion_ready"] is True
    assert payload["rows"][0]["profile_enabled_by_this_tool"] is False


def test_api_runner_profile_promotion_readiness_tool_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_profile(tmp_path)
    _write_runner(tmp_path)
    _write_evidence(tmp_path, ready=False)
    out_json = tmp_path / "readiness.json"
    out_csv = tmp_path / "readiness.csv"
    out_md = tmp_path / "readiness.md"
    template_csv = tmp_path / "operator_template.csv"

    mod.main(
        [
            "--profiles-dir",
            str(tmp_path / "profiles"),
            "--evidence-dir",
            str(tmp_path / "evidence"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
            "--operator-template-csv",
            str(template_csv),
        ]
    )

    summary = json.loads(out_json.read_text(encoding="utf-8"))["summary"]
    assert summary["status"] == "blocked_api_runner_profile_promotion_readiness"
    assert summary["operator_template_csv"] == str(template_csv)
    assert out_csv.read_text(encoding="utf-8").startswith("profile_id,profile_path,")
    assert template_csv.read_text(encoding="utf-8").startswith(
        "profile_id,enabled,delivery_oriented,evidence_bundle_template,evidence_bundle_template_declared,"
    )
    assert "example," in template_csv.read_text(encoding="utf-8")
    assert "API Runner Profile Promotion Readiness" in out_md.read_text(encoding="utf-8")


def test_api_runner_profile_promotion_readiness_blocks_enabled_profile_missing_native_template(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    profile = {
        "enabled": True,
        "profile_id": "example",
        "runner_script": "tools/run_ligand_backmapping_scoring.py",
        "arguments": [],
        "result_file_template": "{job_results_dir}/runner_result.json",
        "claim_boundary": "reviewed boundary",
        "production_readiness": {
            "evidence_artifact": "evidence/example.evidence.json",
        },
    }
    (tmp_path / "profiles" / "example.json").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "profiles" / "example.json").write_text(json.dumps(profile) + "\n", encoding="utf-8")
    (tmp_path / "tools" / "run_ligand_backmapping_scoring.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "tools" / "run_ligand_backmapping_scoring.py").write_text("# runner\n", encoding="utf-8")
    _write_evidence(tmp_path, ready=True)
    (tmp_path / "evidence" / "example.evidence.json").write_text(
        (tmp_path / "evidence" / "example.evidence.template.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    payload = mod.build_api_runner_profile_promotion_readiness(
        profiles_dir=tmp_path / "profiles",
        evidence_dir=tmp_path / "evidence",
    )

    row = payload["rows"][0]
    summary = payload["summary"]
    assert summary["status"] == "blocked_api_runner_profile_promotion_readiness"
    assert summary["native_evidence_bundle_required_profile_count"] == 1
    assert summary["native_evidence_bundle_missing_profile_count"] == 1
    assert summary["first_native_evidence_bundle_missing_profile_id"] == "example"
    assert "native evidence_bundle_template" in summary["next_required_step"]
    assert row["promotion_ready"] is False
    assert row["requires_native_evidence_bundle"] is True
    assert row["evidence_bundle_template_declared"] is False
    assert "evidence_bundle_template_missing" in row["blockers"]


def test_api_runner_profile_promotion_readiness_blocks_delivery_oriented_disabled_profile(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    profile = {
        "enabled": False,
        "profile_id": "example",
        "runner_script": "tools/run_ligand_backmapping_scoring.py",
        "arguments": [],
        "result_file_template": "{job_results_dir}/runner_result.json",
        "claim_boundary": "delivery scope only",
        "claim_scope": "restricted_local_delivery_proxy_refinement_only",
    }
    (tmp_path / "profiles" / "example.json").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "profiles" / "example.json").write_text(json.dumps(profile) + "\n", encoding="utf-8")
    (tmp_path / "tools" / "run_ligand_backmapping_scoring.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "tools" / "run_ligand_backmapping_scoring.py").write_text("# runner\n", encoding="utf-8")
    _write_evidence(tmp_path, ready=True)

    payload = mod.build_api_runner_profile_promotion_readiness(
        profiles_dir=tmp_path / "profiles",
        evidence_dir=tmp_path / "evidence",
    )

    row = payload["rows"][0]
    assert payload["summary"]["native_evidence_bundle_required_profile_count"] == 1
    assert payload["summary"]["native_evidence_bundle_missing_profile_count"] == 1
    assert payload["summary"]["first_native_evidence_bundle_missing_profile_id"] == "example"
    assert row["delivery_oriented"] is True
    assert row["requires_native_evidence_bundle"] is True
    assert row["evidence_bundle_template_declared"] is False
    assert "evidence_bundle_template_missing" in row["blockers"]
    assert row["promotion_ready"] is False


def test_api_runner_profile_promotion_readiness_ready_for_delivery_oriented_profile_with_template(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    profile = {
        "enabled": True,
        "profile_id": "example",
        "runner_script": "tools/run_ligand_backmapping_scoring.py",
        "arguments": [],
        "result_file_template": "{job_results_dir}/runner_result.json",
        "claim_boundary": "delivery scope only",
        "claim_scope": "restricted_local_delivery_proxy_refinement_only",
        "evidence_bundle_template": "{job_results_dir}/evidence_bundle.json",
        "production_readiness": {
            "evidence_artifact": "evidence/example.evidence.json",
        },
    }
    (tmp_path / "profiles" / "example.json").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "profiles" / "example.json").write_text(json.dumps(profile) + "\n", encoding="utf-8")
    (tmp_path / "tools" / "run_ligand_backmapping_scoring.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "tools" / "run_ligand_backmapping_scoring.py").write_text("# runner\n", encoding="utf-8")
    _write_evidence(tmp_path, ready=True)
    (tmp_path / "evidence" / "example.evidence.json").write_text(
        (tmp_path / "evidence" / "example.evidence.template.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    payload = mod.build_api_runner_profile_promotion_readiness(
        profiles_dir=tmp_path / "profiles",
        evidence_dir=tmp_path / "evidence",
    )

    row = payload["rows"][0]
    assert payload["summary"]["status"] == "api_runner_profile_promotion_ready"
    assert payload["summary"]["native_evidence_bundle_required_profile_count"] == 1
    assert payload["summary"]["native_evidence_bundle_missing_profile_count"] == 0
    assert row["promotion_ready"] is True
    assert row["delivery_oriented"] is True
    assert row["evidence_bundle_template_declared"] is True
    assert "evidence_bundle_template_missing" not in row["blockers"]


def test_api_runner_profile_promotion_readiness_uses_runtime_runner_allowlist_for_tier_beta(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    profile = {
        "enabled": True,
        "profile_id": "tier_beta_biodiscovery_direct",
        "runner_script": "tools/run_tier_beta_vertical_slice.py",
        "arguments": [],
        "result_file_template": "{job_results_dir}/tier_beta_result.json",
        "claim_boundary": "restricted tier beta scope",
        "evidence_bundle_template": "{job_results_dir}/tier_beta_evidence_bundle.json",
        "production_readiness": {
            "claim_scope": "restricted_local_tier_beta_biodiscovery_vertical_slice",
            "evidence_artifact": "evidence/tier_beta_biodiscovery_direct.evidence.json",
        },
    }
    (tmp_path / "profiles" / "tier_beta_biodiscovery_direct.json").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "profiles" / "tier_beta_biodiscovery_direct.json").write_text(
        json.dumps(profile) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "tools" / "run_tier_beta_vertical_slice.py").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "tools" / "run_tier_beta_vertical_slice.py").write_text("# tier beta runner\n", encoding="utf-8")
    evidence = {
        "profile_id": "tier_beta_biodiscovery_direct",
        "input_contract_reviewed": True,
        "output_contract_reviewed": True,
        "claim_boundary_reviewed": True,
        "gate_policy_reviewed": True,
        "fake_result_emission_forbidden": True,
        "gate_policy_artifact": "runs/tier_beta_gate.json",
        "reviewer": "operator",
        "reviewed_at_utc": "2026-06-23T01:45:00Z",
    }
    evidence_path = tmp_path / "evidence" / "tier_beta_biodiscovery_direct.evidence.json"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text(json.dumps(evidence) + "\n", encoding="utf-8")

    payload = mod.build_api_runner_profile_promotion_readiness(
        profiles_dir=tmp_path / "profiles",
        evidence_dir=tmp_path / "evidence",
    )

    row = payload["rows"][0]
    assert payload["summary"]["status"] == "api_runner_profile_promotion_ready"
    assert row["runner_allowlisted"] is True
    assert row["promotion_ready"] is True
    assert "runner_script_not_allowlisted" not in row["blockers"]
