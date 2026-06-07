from __future__ import annotations

import json
from pathlib import Path

from tools import build_residual_uncertainty_policy_evidence_contract as mod


def _packet(summary: dict[str, object]) -> dict[str, object]:
    return {"summary": summary}


def test_uncertainty_policy_evidence_contract_ready(tmp_path: Path) -> None:
    checkpoint = tmp_path / "score.pt"
    checkpoint.write_bytes(b"checkpoint")
    payload = mod.build_residual_uncertainty_policy_evidence_contract(
        score_model_packet=_packet(
            {
                "status": "residual_production_score_model_trained",
                "checkpoint": str(checkpoint),
                "val_rows": 200,
                "best": {"pr_auc": 0.7},
                "learned_output_fields": ["delta_score", "corrected_score", "uncertainty"],
                "policy_output_fields": ["abstention_reason", "stage2_route_decision"],
                "policy_output_adapter_ready": True,
                "production_checkpoint_ready": False,
            }
        ),
        residual_shadow_packet=_packet(
            {
                "residual_shadow_ab_ready": True,
                "raw_baseline_preserved": True,
                "no_customer_facing_ranking_change": True,
                "abstention_fields_present": True,
                "production_promotion_allowed": False,
                "residual_output_fields": ["uncertainty", "abstention_reason", "stage2_route_decision"],
            }
        ),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
    )

    summary = payload["summary"]
    assert summary["status"] == "residual_uncertainty_policy_evidence_contract_ready"
    assert summary["uncertainty_policy_evidence_ready"] is True
    assert summary["policy_output_adapter_ready"] is True
    assert summary["fail_closed_shadow_schema_ready"] is True
    assert summary["production_mode_locked"] is True


def test_uncertainty_policy_evidence_contract_blocks_missing_policy_adapter(tmp_path: Path) -> None:
    checkpoint = tmp_path / "score.pt"
    checkpoint.write_bytes(b"checkpoint")
    payload = mod.build_residual_uncertainty_policy_evidence_contract(
        score_model_packet=_packet(
            {
                "status": "residual_production_score_model_trained",
                "checkpoint": str(checkpoint),
                "val_rows": 200,
                "best": {"pr_auc": 0.7},
                "learned_output_fields": ["uncertainty"],
                "policy_output_fields": ["abstention_reason"],
                "policy_output_adapter_ready": True,
                "production_checkpoint_ready": False,
            }
        ),
        residual_shadow_packet=_packet(
            {
                "residual_shadow_ab_ready": True,
                "raw_baseline_preserved": True,
                "no_customer_facing_ranking_change": True,
                "abstention_fields_present": True,
                "production_promotion_allowed": False,
                "residual_output_fields": ["uncertainty", "abstention_reason", "stage2_route_decision"],
            }
        ),
        assist_gate_packet=_packet({"assist_promotion_allowed": True}),
        public_assist_gate_packet=_packet({"assist_comparison_gate_ready": True}),
    )

    assert payload["summary"]["uncertainty_policy_evidence_ready"] is False
    assert payload["summary"]["primary_blocker"] == "policy_output_adapter_contract"
    assert "stage2_route_decision" in payload["summary"]["missing_policy_output_fields"]


def test_uncertainty_policy_evidence_contract_cli_writes_outputs(tmp_path: Path) -> None:
    checkpoint = tmp_path / "score.pt"
    checkpoint.write_bytes(b"checkpoint")
    score = tmp_path / "score.json"
    residual = tmp_path / "residual.json"
    assist = tmp_path / "assist.json"
    public = tmp_path / "public.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    score.write_text(
        json.dumps(
            _packet(
                {
                    "status": "residual_production_score_model_trained",
                    "checkpoint": str(checkpoint),
                    "val_rows": 200,
                    "best": {"pr_auc": 0.7},
                    "learned_output_fields": ["uncertainty"],
                    "policy_output_fields": ["abstention_reason", "stage2_route_decision"],
                    "policy_output_adapter_ready": True,
                    "production_checkpoint_ready": False,
                }
            )
        )
        + "\n",
        encoding="utf-8",
    )
    residual.write_text(
        json.dumps(
            _packet(
                {
                    "residual_shadow_ab_ready": True,
                    "raw_baseline_preserved": True,
                    "no_customer_facing_ranking_change": True,
                    "abstention_fields_present": True,
                    "production_promotion_allowed": False,
                    "residual_output_fields": ["uncertainty", "abstention_reason", "stage2_route_decision"],
                }
            )
        )
        + "\n",
        encoding="utf-8",
    )
    assist.write_text(json.dumps(_packet({"assist_promotion_allowed": True})) + "\n", encoding="utf-8")
    public.write_text(json.dumps(_packet({"assist_comparison_gate_ready": True})) + "\n", encoding="utf-8")

    mod.main(
        [
            "--score-model-json",
            str(score),
            "--residual-shadow-json",
            str(residual),
            "--assist-gate-json",
            str(assist),
            "--public-assist-gate-json",
            str(public),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["uncertainty_policy_evidence_ready"] is True
    assert "policy_output_adapter_contract" in out_csv.read_text(encoding="utf-8")
    assert "Residual Uncertainty Policy Evidence Contract" in out_md.read_text(encoding="utf-8")
