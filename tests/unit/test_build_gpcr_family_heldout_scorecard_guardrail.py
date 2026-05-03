from __future__ import annotations

import json
from pathlib import Path

from tools import build_gpcr_family_heldout_scorecard_guardrail as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_missing_scorecard_blocks_router_and_platform_claims(tmp_path: Path) -> None:
    payload = mod.build_guardrail(tmp_path / "missing.json")

    summary = payload["summary"]
    assert summary["status"] == "blocked"
    assert summary["scorecard_available"] is False
    assert summary["blockers"] == ["scorecard_missing"]
    assert summary["claim_promotion_allowed"] is False
    assert summary["router_claim_allowed"] is False
    assert summary["platform_claim_allowed"] is False
    assert payload["claim_boundary"]["scorecard_alone_does_not_make_claim_safe"] is True


def test_green_scorecard_still_does_not_promote_claim_by_itself(tmp_path: Path) -> None:
    scorecard = tmp_path / "scorecard.json"
    _write_json(
        scorecard,
        {
            "summary": {"scorecard_level_status": "pass", "acceptance_overall_pass": True},
            "families": {"gpcr": {"row_count": 12, "positive_count": 6}},
            "warnings": [],
        },
    )

    payload = mod.build_guardrail(scorecard)

    summary = payload["summary"]
    assert summary["status"] == "green"
    assert summary["blocker_count"] == 0
    assert summary["claim_promotion_allowed"] is False
    assert summary["router_claim_allowed"] is False
    assert summary["next_required_step"].startswith("Family-held-out scorecard is green")
    assert payload["claim_boundary"]["requires_full_100k_gate_too"] is True


def test_blocking_scorecard_warning_keeps_guardrail_blocked(tmp_path: Path) -> None:
    scorecard = tmp_path / "scorecard.json"
    _write_json(
        scorecard,
        {
            "summary": {"scorecard_level_status": "pass", "acceptance_overall_pass": True},
            "families": {"gpcr": {"row_count": 12, "positive_count": 6}},
            "warnings": [{"family": "gpcr", "metric": "score_coverage", "reason": "missing_or_non_finite_scores"}],
        },
    )

    payload = mod.build_guardrail(scorecard)

    assert payload["summary"]["status"] == "blocked"
    assert payload["summary"]["blockers"] == ["blocking_scorecard_warnings_present"]


def test_render_markdown_keeps_claim_boundary_visible() -> None:
    payload = {
        "summary": {
            "status": "blocked",
            "scorecard_available": False,
            "gpcr_family_present": False,
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "blockers": ["scorecard_missing"],
            "next_required_step": "Build scorecard.",
        }
    }

    markdown = mod.render_markdown(payload)

    assert "GPCR Family-Held-Out Scorecard Guardrail" in markdown
    assert "claim_promotion_allowed" in markdown
    assert "scorecard_missing" in markdown
