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
    assert row["promotion_ready"] is False
    assert "input_contract_reviewed_not_true" in row["blockers"]
    assert "gate_policy_artifact_missing" in row["blockers"]
    assert summary["profile_enabled_by_this_tool"] is False
    assert summary["runner_executed"] is False
    assert summary["external_state_mutated"] is False


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
    assert template_csv.read_text(encoding="utf-8").startswith("profile_id,operator_decision,approval_token,")
    assert "example," in template_csv.read_text(encoding="utf-8")
    assert "API Runner Profile Promotion Readiness" in out_md.read_text(encoding="utf-8")
