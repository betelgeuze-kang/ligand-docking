from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_package_b_competition_bridge as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _rollup_payload(*, claim_allowed: bool = False) -> dict:
    return {
        "summary": {
            "status": "competition_benchmark_rollup_ready",
            "competition_benchmark_rollup_artifact_ready": True,
            "competition_benchmark_rollup_ready": True,
            "competition_credibility_evidence_ready": False,
            "competition_credibility_evidence_blocker_count": 1,
            "competition_credibility_evidence_blockers": [
                "casp16_ligand_competition_credibility_not_ready"
            ],
            "competition_benchmark_blockers": [
                "casp16_ligand_competition_credibility_not_ready",
                "package_b_claim_grade_public_benchmark_not_ready",
            ],
            "competition_evidence_role": "competition_credibility_evidence_only",
            "competition_ligand_commercial_claim_allowed": claim_allowed,
            "package_b_required_for_ligand_commercial_claims": True,
            "package_b_ligand_suite_ids": [
                "pdbbind_casf_pose_affinity",
                "lit_pcba_virtual_screening",
                "dude_z_decoy_smoke",
            ],
            "package_b_ligand_suite_count": 3,
            "package_b_public_benchmark_contract_artifact_path": (
                "runs/product_public_benchmark_contract_current.json"
            ),
            "package_b_public_benchmark_contract_status": (
                "product_public_benchmark_contract_ready"
            ),
            "package_b_ligand_public_benchmark_foundation_ready": True,
            "package_b_refine_tier_public_benchmark_artifact_path": (
                "runs/refine_tier_public_benchmark_readiness_current.json"
            ),
            "package_b_refine_tier_public_benchmark_status": (
                "blocked_refine_tier_public_benchmark_readiness"
            ),
            "package_b_claim_grade_public_benchmark_ready": False,
            "package_b_claim_grade_blocker_count": 1,
            "package_b_claim_grade_blockers": ["insufficient_total_rows"],
            "competition_ligand_claim_package_b_dependency_ready": False,
            "competition_ligand_claim_blocker_count": 2,
            "competition_ligand_claim_blockers": [
                "casp16_ligand_competition_credibility_not_ready",
                "package_b_claim_grade_public_benchmark_not_ready",
            ],
            "github_raw_data_policy_ready": False,
            "github_raw_data_git_tracked_total_count": 2802,
            "github_raw_data_policy_blockers": [
                "bm5_capri_raw_data_committed_in_repo"
            ],
            "package_b_refine_tier_external_state_mutated": False,
            "package_b_refine_tier_apply_external_state_mutated": False,
            "package_b_bridge_next_action": "Fill Package B refine-tier evidence.",
            "claim_boundary": (
                "Competition benchmark rollup only; CASP16, CAPRI/BM5, and CAMEO are "
                "competition credibility evidence only; ligand commercial claims remain locked "
                "unless Package B public ligand benchmark evidence is separately claim-grade ready."
            ),
        }
    }


def test_package_b_competition_bridge_exports_claim_locked_receipt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    rollup_json = tmp_path / "runs/competition_benchmark_rollup_current.json"
    _write_json(rollup_json, _rollup_payload())

    payload = mod.build_package_b_competition_bridge()
    summary = payload["summary"]
    markdown = mod._render_markdown(payload)

    assert summary["status"] == "package_b_competition_bridge_ready"
    assert summary["package_b_competition_bridge_ready"] is True
    assert summary["blocker_count"] == 0
    assert summary["primary_blocker"] == ""
    assert summary["blockers"] == []
    assert summary["bridge_claim_lock_ready"] is True
    assert summary["competition_credibility_only"] is True
    assert summary["competition_rollup_artifact_ready"] is True
    assert summary["competition_credibility_evidence_ready"] is False
    assert summary["competition_credibility_evidence_blockers"] == [
        "casp16_ligand_competition_credibility_not_ready"
    ]
    assert summary["competition_ligand_commercial_claim_allowed"] is False
    assert summary["ligand_commercial_claim_unlock_ready"] is False
    assert summary["ligand_commercial_claim_unlock_prerequisites_ready"] is False
    assert summary["ligand_commercial_claim_unlock_requires_separate_promotion_gate"] is True
    assert summary["ligand_commercial_claim_unlock_blockers"] == [
        "competition_credibility_evidence_not_ready",
        "github_raw_data_policy_not_ready",
        "package_b_claim_grade_public_benchmark_not_ready",
        "casp16_ligand_competition_credibility_not_ready",
    ]
    assert summary["ligand_commercial_claim_unlocked"] is False
    assert summary["commercial_claim_unlocked"] is False
    assert summary["claim_promotion_allowed"] is False
    assert summary["observed_competition_ligand_commercial_claim_allowed"] is False
    assert summary["package_b_required_for_ligand_commercial_claims"] is True
    assert summary["package_b_claim_grade_public_benchmark_ready"] is False
    assert summary["competition_ligand_claim_blockers"] == [
        "casp16_ligand_competition_credibility_not_ready",
        "package_b_claim_grade_public_benchmark_not_ready",
    ]
    assert summary["github_raw_payloads_allowed"] is False
    assert summary["raw_data_stored_in_repo"] is True
    assert summary["raw_data_free"] is False
    assert "source_manifests" in summary["github_safe_allowed_artifact_classes"]
    assert "scorecard_builders" in summary["github_safe_allowed_artifact_classes"]
    assert "claim_boundary_docs" in summary["github_safe_allowed_artifact_classes"]
    assert "raw_benchmark_payloads" not in summary["github_safe_allowed_artifact_classes"]
    assert summary["execution_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert summary["next_required_step"] == "Fill Package B refine-tier evidence."
    assert [row["bridge_check"] for row in payload["rows"]] == [
        "competition_rollup",
        "competition_credibility_evidence",
        "package_b_public_benchmark_contract",
        "package_b_claim_grade_public_benchmark",
        "competition_ligand_claim_gate",
        "github_raw_data_policy",
    ]
    assert "| `raw_benchmark_payloads` | `false` |" in markdown
    assert "Competition credibility evidence ready | `false`" in markdown
    assert "Ligand commercial claim allowed | `false`" in markdown
    assert "Ligand commercial claim unlock ready | `false`" in markdown
    assert "Ligand commercial claim unlock requires separate promotion gate | `true`" in markdown
    assert "competition_credibility_evidence_not_ready" in markdown
    assert "github_raw_data_policy_not_ready" in markdown
    assert "| Raw data stored in repo | `true` |" in markdown
    assert "| Raw-data-free evidence | `false` |" in markdown


def test_package_b_competition_bridge_blocks_unexpected_claim_promotion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "runs/competition_benchmark_rollup_current.json",
        _rollup_payload(claim_allowed=True),
    )

    summary = mod.build_package_b_competition_bridge()["summary"]

    assert summary["status"] == "blocked_package_b_competition_bridge"
    assert summary["package_b_competition_bridge_ready"] is False
    assert summary["blocker_count"] == 1
    assert summary["primary_blocker"] == "competition_ligand_claim_promotion_unexpectedly_allowed"
    assert "competition_ligand_claim_promotion_unexpectedly_allowed" in summary["blockers"]
    assert summary["bridge_claim_lock_ready"] is False
    assert summary["competition_ligand_commercial_claim_allowed"] is False
    assert summary["ligand_commercial_claim_unlock_ready"] is False
    assert summary["observed_competition_ligand_commercial_claim_allowed"] is True
    assert "competition_ligand_claim_promotion_unexpectedly_allowed" in summary[
        "bridge_blockers"
    ]


def test_package_b_competition_bridge_separates_bridge_ready_from_claim_unlock(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    payload = _rollup_payload()
    summary = payload["summary"]
    summary.update(
        {
            "competition_credibility_evidence_ready": True,
            "competition_credibility_evidence_blocker_count": 0,
            "competition_credibility_evidence_blockers": [],
            "competition_benchmark_blockers": [],
            "package_b_claim_grade_public_benchmark_ready": True,
            "package_b_claim_grade_blocker_count": 0,
            "package_b_claim_grade_blockers": [],
            "competition_ligand_claim_package_b_dependency_ready": True,
            "competition_ligand_claim_blocker_count": 0,
            "competition_ligand_claim_blockers": [],
            "github_raw_data_policy_ready": True,
            "github_raw_data_git_tracked_total_count": 0,
            "github_raw_data_policy_blockers": [],
            "package_b_bridge_next_action": "",
        }
    )
    _write_json(tmp_path / "runs/competition_benchmark_rollup_current.json", payload)

    bridge_summary = mod.build_package_b_competition_bridge()["summary"]

    assert bridge_summary["package_b_competition_bridge_ready"] is True
    assert bridge_summary["bridge_claim_lock_ready"] is True
    assert bridge_summary["ligand_commercial_claim_unlock_ready"] is True
    assert bridge_summary["ligand_commercial_claim_unlock_prerequisites_ready"] is True
    assert bridge_summary["ligand_commercial_claim_unlock_requires_separate_promotion_gate"] is True
    assert bridge_summary["ligand_commercial_claim_unlock_blockers"] == []
    assert bridge_summary["competition_ligand_commercial_claim_allowed"] is False
    assert bridge_summary["ligand_commercial_claim_unlocked"] is False
    assert bridge_summary["claim_promotion_allowed"] is False


def test_package_b_competition_bridge_main_writes_json_and_markdown(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    _write_json(
        tmp_path / "runs/competition_benchmark_rollup_current.json",
        _rollup_payload(),
    )

    mod.main([])

    assert (tmp_path / "runs/package_b_competition_bridge_current.json").is_file()
    assert (tmp_path / "docs/package_b_competition_bridge_current.md").is_file()
