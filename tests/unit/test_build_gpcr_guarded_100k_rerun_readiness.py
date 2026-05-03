from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_guarded_100k_rerun_readiness as mod


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _positive_packet(*, observed_positive_count: int, frozen: bool = True) -> dict:
    return {
        "summary": {
            "observed_positive_count": observed_positive_count,
            "minimum_positive_count_for_frozen_packet": 9,
            "full_100k_guarded_rerun_eligible": frozen,
            "full_100k_guarded_rerun_reason": "positive_coverage_frozen" if frozen else "frozen_packet_missing",
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
        }
    }


def _freeze_packet(
    *,
    frozen: bool = True,
    status: str = "frozen",
    positive_count: int = 9,
    new_non_adrb2_positive_count: int = 3,
    distinct_positive_gpcr_target_count: int = 2,
    leakage_audit_pass: bool = True,
) -> dict:
    return {
        "frozen": frozen,
        "status": status,
        "summary": {
            "frozen": frozen,
            "positive_count": positive_count,
            "new_non_adrb2_positive_count": new_non_adrb2_positive_count,
            "distinct_positive_gpcr_target_count": distinct_positive_gpcr_target_count,
            "leakage_audit_pass": leakage_audit_pass,
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
        },
    }


def _family_packet(*, status: str = "green") -> dict:
    return {
        "summary": {
            "status": status,
            "blockers": [] if status == "green" else ["scorecard_missing"],
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
        }
    }


def _scoreability_packet(*, status: str = "pass") -> dict:
    return {
        "summary": {
            "status": status,
            "pass": status == "pass",
            "blockers": [] if status == "pass" else ["missing_native_targets"],
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
        }
    }


def _ci_packet(*, ci_low: float = 0.51, top20_pass: bool = True) -> dict:
    return {
        "summary": {
            "ci_low_blocker": ci_low < 0.45,
            "ranking_pr_auc_ci_low": ci_low,
            "ranking_topk_hit_rate": 0.25 if top20_pass else 0.10,
            "ranking_topk_hit_rate_max_possible": 0.45 if top20_pass else 0.30,
            "threshold": 0.45,
            "ranking_positive_count": 9,
        },
        "claim_coverage_requirement": {
            "ci_low_policy": {
                "status": "meets_threshold" if ci_low >= 0.45 else "blocked",
                "observed": ci_low,
                "threshold": 0.45,
                "claim_promotion_allowed": False,
            },
            "top20_ceiling_observed": 0.45 if top20_pass else 0.30,
            "top20_ceiling_threshold": 0.45,
        },
        "rank_diagnostics": {
            "positive_count": 9,
            "top20_hit_count": 5 if top20_pass else 2,
            "top20_hit_rate_max_possible": 0.45 if top20_pass else 0.30,
        },
        "recovery_interpretation": {"claim_promotion_allowed": False},
    }


def _triage_packet(*, claim_safe: bool = True, top20_guardrail_pass: bool = True) -> dict:
    return {
        "summary": {
            "claim_safe": claim_safe,
            "claim_safe_status": "green" if claim_safe else "regression_guardrail_failed",
            "guardrail_fail_count": 0 if claim_safe and top20_guardrail_pass else 1,
        },
        "guardrail_rows": [
            {
                "guardrail_id": "top20_hit_drop_max_1",
                "metric": "top20_hit_rate_delta",
                "pass": top20_guardrail_pass,
            },
            {
                "guardrail_id": "no_pass_to_fail",
                "metric": "set_pass_transition",
                "pass": claim_safe,
            },
        ],
    }


def _leakage_packet(*, passed: bool = True) -> dict:
    return {
        "pass": passed,
        "failed_rules": [] if passed else ["target_overlap"],
        "key_overlap_count": 0 if passed else 1,
        "target_overlap_count": 0 if passed else 1,
    }


def test_frozen_positive_packet_makes_rerun_eligible_but_do_not_allow_claim_promotion(tmp_path: Path) -> None:
    positive = tmp_path / "positive.json"
    scoreability = tmp_path / "scoreability.json"
    family = tmp_path / "family.json"
    ci = tmp_path / "ci.json"
    triage = tmp_path / "triage.json"
    _write_json(positive, _freeze_packet())
    _write_json(scoreability, _scoreability_packet())
    _write_json(family, _family_packet())
    _write_json(ci, _ci_packet())
    _write_json(triage, _triage_packet())

    payload = mod.build_packet(
        positive_json=positive,
        scoreability_json=scoreability,
        family_heldout_json=family,
        ci_low_json=ci,
        triage_json=triage,
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    assert payload["summary"]["eligible"] is True
    assert payload["summary"]["status"] == "eligible"
    assert payload["summary"]["launch_eligible"] is True
    assert payload["summary"]["launch_status"] == "eligible"
    assert payload["summary"]["launch_blockers"] == []
    assert payload["summary"]["claim_review_eligible"] is True
    assert payload["summary"]["blockers"] == []
    assert payload["gates"]["positive_coverage"]["status"] == "green"
    assert payload["gates"]["frozen_candidate_scoreability"]["status"] == "green"
    assert payload["gates"]["family_heldout"]["status"] == "green"
    assert payload["gates"]["ci_low"]["status"] == "green"
    assert payload["gates"]["top20_stability"]["status"] == "green"
    assert payload["gates"]["leakage_triage"]["status"] == "green"
    assert payload["gates"]["positive_coverage"]["frozen"] is True
    assert payload["gates"]["positive_coverage"]["positive_count"] == 9
    assert payload["gates"]["positive_coverage"]["new_non_adrb2_positive_count"] == 3
    assert payload["gates"]["positive_coverage"]["distinct_positive_gpcr_target_count"] == 2
    assert payload["gates"]["positive_coverage"]["leakage_audit_pass"] is True
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert payload["summary"]["router_claim_allowed"] is False
    assert payload["summary"]["platform_claim_allowed"] is False
    assert payload["claim_boundary"]["readiness_packet_is_not_claim_authorization"] is True


def test_default_positive_input_is_freeze_packet_path_and_blocks_when_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    payload = mod.build_packet(generated_at_local="2026-05-03T00:00:00+09:00")

    assert payload["summary"]["eligible"] is False
    assert payload["summary"]["status"] == "blocked"
    assert payload["summary"]["launch_eligible"] is False
    assert payload["summary"]["launch_status"] == "blocked"
    assert "positive_coverage_packet_missing" in payload["summary"]["launch_blockers"]
    assert payload["input_artifacts"]["positive_json"].endswith(
        "runs/gpcr_positive_coverage_freeze_packet_current.json"
    )
    assert "positive_coverage_packet_missing" in payload["summary"]["blockers"]
    assert "frozen_candidate_scoreability_packet_missing" in payload["summary"]["blockers"]
    assert "frozen_candidate_scoreability_packet_missing" in payload["summary"]["launch_blockers"]
    assert "family_heldout_not_green" in payload["summary"]["blockers"]
    assert "ci_low_below_threshold" in payload["summary"]["blockers"]
    assert "top20_stability_not_green" in payload["summary"]["blockers"]
    assert "leakage_triage_not_green" in payload["summary"]["blockers"]
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert payload["summary"]["router_claim_allowed"] is False
    assert payload["summary"]["platform_claim_allowed"] is False
    assert payload["gates"]["ci_low"]["observed"] is None


def test_positive_expansion_packet_alone_stays_blocked_even_when_count_reaches_9(tmp_path: Path) -> None:
    positive = tmp_path / "positive_expansion.json"
    _write_json(positive, _positive_packet(observed_positive_count=9, frozen=True))

    payload = mod.build_packet(
        positive_json=positive,
        family_heldout_json=tmp_path / "missing_family.json",
        ci_low_json=tmp_path / "missing_ci.json",
        triage_json=tmp_path / "missing_triage.json",
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    gate = payload["gates"]["positive_coverage"]
    assert gate["status"] == "blocked"
    assert gate["positive_count"] is None
    assert "positive_coverage_not_frozen" in gate["blockers"]
    assert "new_non_adrb2_positive_count_below_3" in gate["blockers"]
    assert "distinct_positive_gpcr_target_count_below_2" in gate["blockers"]
    assert "leakage_audit_not_passed" in gate["blockers"]
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert payload["summary"]["router_claim_allowed"] is False
    assert payload["summary"]["platform_claim_allowed"] is False


def test_positive_freeze_packet_blocks_on_each_required_freeze_gate(tmp_path: Path) -> None:
    positive = tmp_path / "positive_freeze.json"
    _write_json(
        positive,
        _freeze_packet(
            frozen=False,
            status="draft",
            positive_count=8,
            new_non_adrb2_positive_count=2,
            distinct_positive_gpcr_target_count=1,
            leakage_audit_pass=False,
        ),
    )

    payload = mod.build_packet(
        positive_json=positive,
        family_heldout_json=tmp_path / "missing_family.json",
        ci_low_json=tmp_path / "missing_ci.json",
        triage_json=tmp_path / "missing_triage.json",
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    gate = payload["gates"]["positive_coverage"]
    assert gate["status"] == "blocked"
    assert gate["frozen"] is False
    assert gate["positive_count"] == 8
    assert gate["new_non_adrb2_positive_count"] == 2
    assert gate["distinct_positive_gpcr_target_count"] == 1
    assert gate["leakage_audit_pass"] is False
    assert gate["blockers"] == [
        "positive_count_below_9",
        "new_non_adrb2_positive_count_below_3",
        "distinct_positive_gpcr_target_count_below_2",
        "leakage_audit_not_passed",
        "positive_coverage_not_frozen",
    ]


def test_missing_or_partial_inputs_block_conservatively(tmp_path: Path) -> None:
    positive = tmp_path / "positive.json"
    scoreability = tmp_path / "scoreability.json"
    _write_json(positive, _freeze_packet())
    _write_json(scoreability, _scoreability_packet())

    payload = mod.build_packet(
        positive_json=positive,
        scoreability_json=scoreability,
        family_heldout_json=tmp_path / "missing_family.json",
        ci_low_json=tmp_path / "missing_ci.json",
        triage_json=tmp_path / "missing_triage.json",
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    assert payload["summary"]["eligible"] is False
    assert payload["gates"]["family_heldout"]["status"] == "blocked"
    assert payload["gates"]["ci_low"]["status"] == "blocked"
    assert payload["gates"]["leakage_triage"]["status"] == "blocked"
    assert payload["summary"]["claim_promotion_allowed"] is False


def test_frozen_positive_packet_opens_launch_but_not_claim_review_when_perf_gates_block(tmp_path: Path) -> None:
    positive = tmp_path / "positive.json"
    scoreability = tmp_path / "scoreability.json"
    _write_json(positive, _freeze_packet())
    _write_json(scoreability, _scoreability_packet())

    payload = mod.build_packet(
        positive_json=positive,
        scoreability_json=scoreability,
        family_heldout_json=tmp_path / "missing_family.json",
        ci_low_json=tmp_path / "missing_ci.json",
        triage_json=tmp_path / "missing_triage.json",
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    assert payload["summary"]["eligible"] is False
    assert payload["summary"]["status"] == "blocked"
    assert payload["summary"]["launch_eligible"] is True
    assert payload["summary"]["launch_status"] == "eligible"
    assert payload["summary"]["launch_blockers"] == []
    assert payload["summary"]["claim_review_eligible"] is False
    assert "family_heldout_not_green" in payload["summary"]["blockers"]
    assert "ci_low_below_threshold" in payload["summary"]["blockers"]
    assert payload["summary"]["claim_promotion_allowed"] is False


def test_top20_gate_uses_actual_hit_rate_from_ci_packet(tmp_path: Path) -> None:
    positive = tmp_path / "positive.json"
    scoreability = tmp_path / "scoreability.json"
    family = tmp_path / "family.json"
    ci = tmp_path / "ci.json"
    triage = tmp_path / "triage.json"
    leakage = tmp_path / "leakage.json"
    _write_json(positive, _freeze_packet())
    _write_json(scoreability, _scoreability_packet())
    _write_json(family, _family_packet())
    _write_json(ci, _ci_packet(ci_low=0.51, top20_pass=False))
    _write_json(triage, _triage_packet(claim_safe=True, top20_guardrail_pass=True))
    _write_json(leakage, _leakage_packet())

    payload = mod.build_packet(
        positive_json=positive,
        scoreability_json=scoreability,
        family_heldout_json=family,
        ci_low_json=ci,
        triage_json=triage,
        leakage_audit_json=leakage,
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    assert payload["gates"]["top20_stability"]["status"] == "blocked"
    assert payload["gates"]["top20_stability"]["top20_hit_rate_observed"] == 0.10
    assert "top20_stability_not_green" in payload["summary"]["blockers"]
    assert payload["gates"]["leakage_triage"]["status"] == "green"


def test_leakage_audit_pass_clears_leakage_gate_even_when_legacy_triage_claim_safe_false(tmp_path: Path) -> None:
    positive = tmp_path / "positive.json"
    scoreability = tmp_path / "scoreability.json"
    family = tmp_path / "family.json"
    ci = tmp_path / "ci.json"
    triage = tmp_path / "triage.json"
    leakage = tmp_path / "leakage.json"
    _write_json(positive, _freeze_packet())
    _write_json(scoreability, _scoreability_packet())
    _write_json(family, _family_packet())
    _write_json(ci, _ci_packet(ci_low=0.001, top20_pass=False))
    _write_json(triage, _triage_packet(claim_safe=False, top20_guardrail_pass=False))
    _write_json(leakage, _leakage_packet())

    payload = mod.build_packet(
        positive_json=positive,
        scoreability_json=scoreability,
        family_heldout_json=family,
        ci_low_json=ci,
        triage_json=triage,
        leakage_audit_json=leakage,
        generated_at_local="2026-05-03T00:00:00+09:00",
    )

    assert payload["gates"]["leakage_triage"]["status"] == "green"
    assert "leakage_triage_not_green" not in payload["summary"]["blockers"]
    assert "ci_low_below_threshold" in payload["summary"]["blockers"]
    assert "top20_stability_not_green" in payload["summary"]["blockers"]


def test_cli_writes_readiness_packet_and_markdown(tmp_path: Path) -> None:
    positive = tmp_path / "positive.json"
    scoreability = tmp_path / "scoreability.json"
    family = tmp_path / "family.json"
    ci = tmp_path / "ci.json"
    triage = tmp_path / "triage.json"
    out_json = tmp_path / "readiness.json"
    out_md = tmp_path / "readiness.md"
    _write_json(positive, _freeze_packet())
    _write_json(scoreability, _scoreability_packet())
    _write_json(family, _family_packet())
    _write_json(ci, _ci_packet())
    _write_json(triage, _triage_packet())

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "build_gpcr_guarded_100k_rerun_readiness.py"),
            "--positive-json",
            str(positive),
            "--scoreability-json",
            str(scoreability),
            "--family-heldout-json",
            str(family),
            "--ci-low-json",
            str(ci),
            "--triage-json",
            str(triage),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    markdown = out_md.read_text(encoding="utf-8")
    assert result.returncode == 0
    assert payload["summary"]["eligible"] is True
    assert "GPCR Guarded 100k Rerun Readiness" in markdown
    assert "claim_promotion_allowed: `false`" in markdown
