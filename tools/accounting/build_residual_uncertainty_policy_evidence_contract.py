#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCORE_MODEL_JSON = "runs/residual_production_score_model_current.json"
DEFAULT_RESIDUAL_SHADOW_JSON = "runs/residual_shadow_ab_current.json"
DEFAULT_ASSIST_GATE_JSON = "runs/residual_assist_promotion_gate_current.json"
DEFAULT_PUBLIC_ASSIST_GATE_JSON = "runs/public_benchmark_residual_assist_comparison_gate_current.json"
DEFAULT_OUT_JSON = "runs/residual_uncertainty_policy_evidence_contract_current.json"
DEFAULT_OUT_CSV = "runs/residual_uncertainty_policy_evidence_contract_current.csv"
DEFAULT_OUT_MD = "runs/residual_uncertainty_policy_evidence_contract_current.md"

REQUIRED_POLICY_OUTPUT_FIELDS = ("abstention_reason", "stage2_route_decision")
REQUIRED_ABSTENTION_FIELDS = ("uncertainty", "abstention_reason", "stage2_route_decision")

CLAIM_BOUNDARY = (
    "Residual uncertainty/policy evidence contract only; audits local score-model uncertainty output, abstention/route "
    "adapter evidence, shadow fail-closed schema, and assist benchmark gates before production promotion. It does not "
    "train models, create checkpoints, write sidecars, run inference, run docking, change rankings, promote production "
    "mode, upload, submit, email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    return packet if isinstance(packet, dict) else {}


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any) -> bool:
    return value is True


def _row(
    check_id: str,
    status: str,
    observed: str,
    required: str,
    source_artifact: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "observed": observed,
        "required": required,
        "source_artifact": source_artifact,
        "next_action": next_action,
        "release_blocker": status != "pass",
        "execution_enabled": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }


def build_residual_uncertainty_policy_evidence_contract(
    *,
    score_model_packet: dict[str, Any],
    residual_shadow_packet: dict[str, Any],
    assist_gate_packet: dict[str, Any],
    public_assist_gate_packet: dict[str, Any],
    score_model_path: str = DEFAULT_SCORE_MODEL_JSON,
    residual_shadow_path: str = DEFAULT_RESIDUAL_SHADOW_JSON,
    assist_gate_path: str = DEFAULT_ASSIST_GATE_JSON,
    public_assist_gate_path: str = DEFAULT_PUBLIC_ASSIST_GATE_JSON,
    min_val_rows: int = 100,
    min_pr_auc: float = 0.50,
) -> dict[str, Any]:
    score = _summary(score_model_packet)
    residual = _summary(residual_shadow_packet)
    assist = _summary(assist_gate_packet)
    public_assist = _summary(public_assist_gate_packet)
    best = score.get("best") if isinstance(score.get("best"), dict) else {}
    checkpoint = str(score.get("checkpoint") or "")
    checkpoint_exists = bool(checkpoint and _resolve(checkpoint).exists())
    learned_output_fields = [str(field) for field in score.get("learned_output_fields") or []]
    policy_output_fields = [str(field) for field in score.get("policy_output_fields") or []]
    residual_fields = [str(field) for field in residual.get("residual_output_fields") or []]
    missing_policy_fields = [field for field in REQUIRED_POLICY_OUTPUT_FIELDS if field not in policy_output_fields]
    missing_abstention_schema_fields = [field for field in REQUIRED_ABSTENTION_FIELDS if field not in residual_fields]

    score_model_quality_ready = bool(
        str(score.get("status") or "") == "residual_production_score_model_trained"
        and checkpoint_exists
        and _int(score.get("val_rows")) >= min_val_rows
        and _float(best.get("pr_auc")) >= min_pr_auc
    )
    uncertainty_head_ready = "uncertainty" in learned_output_fields
    policy_output_adapter_ready = _bool(score.get("policy_output_adapter_ready")) and not missing_policy_fields
    fail_closed_shadow_schema_ready = bool(
        _bool(residual.get("residual_shadow_ab_ready"))
        and _bool(residual.get("raw_baseline_preserved"))
        and _bool(residual.get("no_customer_facing_ranking_change"))
        and (_bool(residual.get("abstention_fields_present")) or not missing_abstention_schema_fields)
    )
    assist_benchmark_ready = _bool(assist.get("assist_promotion_allowed")) and _bool(
        public_assist.get("assist_comparison_gate_ready")
    )
    production_mode_locked = (
        residual.get("production_promotion_allowed") is False
        and score.get("production_checkpoint_ready") is not True
    )

    rows = [
        _row(
            "score_model_uncertainty_quality",
            "pass" if score_model_quality_ready and uncertainty_head_ready else "fail",
            (
                f"status={score.get('status')};checkpoint_exists={checkpoint_exists};"
                f"val_rows={_int(score.get('val_rows'))};pr_auc={_float(best.get('pr_auc'))};"
                f"learned_output_fields={','.join(learned_output_fields)}"
            ),
            f"trained score model has checkpoint, >={min_val_rows} validation rows, PR-AUC>={min_pr_auc}, and learned uncertainty output",
            score_model_path,
            "Train or refresh the score model until uncertainty output and validation quality evidence are present.",
        ),
        _row(
            "policy_output_adapter_contract",
            "pass" if policy_output_adapter_ready else "fail",
            (
                f"policy_output_adapter_ready={score.get('policy_output_adapter_ready')};"
                f"policy_output_fields={','.join(policy_output_fields)};"
                f"missing_policy_output_fields={','.join(missing_policy_fields)}"
            ),
            "policy adapter emits abstention_reason and stage2_route_decision",
            score_model_path,
            "Bind abstention_reason and stage2_route_decision outputs in the score-model policy adapter.",
        ),
        _row(
            "fail_closed_shadow_schema",
            "pass" if fail_closed_shadow_schema_ready else "fail",
            (
                f"residual_shadow_ab_ready={residual.get('residual_shadow_ab_ready')};"
                f"raw_baseline_preserved={residual.get('raw_baseline_preserved')};"
                f"no_customer_facing_ranking_change={residual.get('no_customer_facing_ranking_change')};"
                f"abstention_fields_present={residual.get('abstention_fields_present')};"
                f"missing_abstention_schema_fields={','.join(missing_abstention_schema_fields)}"
            ),
            "shadow layer preserves raw ranking and exposes uncertainty/abstention/route fields",
            residual_shadow_path,
            "Repair residual shadow schema before using policy evidence for production checkpoint sidecars.",
        ),
        _row(
            "assist_benchmark_policy_guard",
            "pass" if assist_benchmark_ready else "fail",
            (
                f"assist_promotion_allowed={assist.get('assist_promotion_allowed')};"
                f"public_assist_gate_ready={public_assist.get('assist_comparison_gate_ready')}"
            ),
            "assist and public assist benchmark gates are green before production policy evidence is accepted",
            f"{assist_gate_path};{public_assist_gate_path}",
            "Keep assist/public assist benchmark gates green while production checkpoint work proceeds.",
        ),
        _row(
            "production_mode_lock",
            "pass" if production_mode_locked else "fail",
            (
                f"residual_production_promotion_allowed={residual.get('production_promotion_allowed')};"
                f"score_model_production_checkpoint_ready={score.get('production_checkpoint_ready')}"
            ),
            "policy evidence does not itself promote production mode or alter customer rankings",
            f"{score_model_path};{residual_shadow_path}",
            "Keep production promotion locked until checkpoint preflight, force provenance, and benchmark gates are ready.",
        ),
    ]

    fail_rows = [row for row in rows if row["status"] != "pass"]
    ready = not fail_rows
    summary = {
        "packet_type": "residual_uncertainty_policy_evidence_contract",
        "status": (
            "residual_uncertainty_policy_evidence_contract_ready"
            if ready
            else "blocked_residual_uncertainty_policy_evidence_contract"
        ),
        "uncertainty_policy_evidence_ready": ready,
        "check_count": len(rows),
        "pass_check_count": len(rows) - len(fail_rows),
        "fail_check_count": len(fail_rows),
        "failed_check_ids": [row["check_id"] for row in fail_rows],
        "primary_blocker": fail_rows[0]["check_id"] if fail_rows else "none",
        "learned_output_fields": learned_output_fields,
        "policy_output_fields": policy_output_fields,
        "required_policy_output_fields": list(REQUIRED_POLICY_OUTPUT_FIELDS),
        "required_abstention_fields": list(REQUIRED_ABSTENTION_FIELDS),
        "missing_policy_output_fields": missing_policy_fields,
        "missing_abstention_schema_fields": missing_abstention_schema_fields,
        "score_model_quality_ready": score_model_quality_ready,
        "uncertainty_head_ready": uncertainty_head_ready,
        "policy_output_adapter_ready": policy_output_adapter_ready,
        "fail_closed_shadow_schema_ready": fail_closed_shadow_schema_ready,
        "assist_benchmark_ready": assist_benchmark_ready,
        "production_mode_locked": production_mode_locked,
        "source_artifacts": [score_model_path, residual_shadow_path, assist_gate_path, public_assist_gate_path],
        "execution_enabled": False,
        "training_executed": False,
        "checkpoint_created": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use this policy evidence as input to the production training-data contract; production promotion remains gated by checkpoint preflight."
            if ready
            else fail_rows[0]["next_action"]
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Uncertainty Policy Evidence Contract",
        "",
        f"- status: `{s['status']}`",
        f"- uncertainty_policy_evidence_ready: `{s['uncertainty_policy_evidence_ready']}`",
        f"- pass_check_count: `{s['pass_check_count']}` / `{s['check_count']}`",
        f"- primary_blocker: `{s['primary_blocker']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build residual uncertainty/policy evidence contract.")
    parser.add_argument("--score-model-json", default=DEFAULT_SCORE_MODEL_JSON)
    parser.add_argument("--residual-shadow-json", default=DEFAULT_RESIDUAL_SHADOW_JSON)
    parser.add_argument("--assist-gate-json", default=DEFAULT_ASSIST_GATE_JSON)
    parser.add_argument("--public-assist-gate-json", default=DEFAULT_PUBLIC_ASSIST_GATE_JSON)
    parser.add_argument("--min-val-rows", type=int, default=100)
    parser.add_argument("--min-pr-auc", type=float, default=0.50)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_uncertainty_policy_evidence_contract(
        score_model_packet=_read_json_if_present(args.score_model_json),
        residual_shadow_packet=_read_json_if_present(args.residual_shadow_json),
        assist_gate_packet=_read_json_if_present(args.assist_gate_json),
        public_assist_gate_packet=_read_json_if_present(args.public_assist_gate_json),
        score_model_path=args.score_model_json,
        residual_shadow_path=args.residual_shadow_json,
        assist_gate_path=args.assist_gate_json,
        public_assist_gate_path=args.public_assist_gate_json,
        min_val_rows=args.min_val_rows,
        min_pr_auc=args.min_pr_auc,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
