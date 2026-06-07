#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_FAILURE_PACKET_JSON = "runs/tau_k18_full_fold_corrected_failure_slice_packet_current.json"
DEFAULT_OUT_PREFIX = "runs/idp_tau_k18_stabilization_trial_commercial_pretest_seed123_phhelixrecover_r1"
DEFAULT_OUT_JSON = "runs/tau_k18_full_fold_corrected_calibration_packet_current.json"
DEFAULT_OUT_CSV = "runs/tau_k18_full_fold_corrected_calibration_packet_current.csv"
DEFAULT_OUT_MD = "runs/tau_k18_full_fold_corrected_calibration_packet_current.md"

CANDIDATE_RULE_NAME = "short_tau_ph_shift_helix_recovery_v1"
CANDIDATE_RULE_SCOPE = "corrected_path_interpretation_only"
CALIBRATION_SLICE_ID = "fold6_tau_k18_seed123_full_fold"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _exact_command(out_prefix: str) -> str:
    return " ".join(
        [
            "python3",
            "tools/run_idp_tau_k18_stabilization_trial.py",
            "--eval-config-json",
            str(_resolve("runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r16validation_r1_fold_inputs/fold6_tau_k18_eval.json")),
            "--baseline-gate-json",
            str(_resolve("runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r16validation_r1_fold6_tau_k18_gate_baseline_summary.json")),
            "--out-prefix",
            str(_resolve(out_prefix)),
            "--seed",
            "123",
            "--epochs",
            "120",
            "--patience",
            "24",
            "--lr",
            "0.00075",
            "--weight-decay",
            "1e-05",
            "--kalman-shadow-feature-mask",
            "rg_sasa_only",
            "--frozen-labels-csv",
            str(_resolve("runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r16validation_r1_fold6_tau_k18_eval_corrected_targets.csv")),
            "--idp-r16-ml-patch",
            "1",
            "--idp-r17-tau-ph-split-patch",
            "1",
            "--idp-r18-tau-ph-helix-recovery-patch",
            "1",
        ]
    )


def _focus_rows(failure_packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in failure_packet.get("rows", []) or []:
        condition = str(row.get("condition_group", "")).strip()
        rows.append(
            {
                "condition_group": condition,
                "true_state": str(row.get("true_state", "")).strip(),
                "reference_pred_state": str(row.get("pred_state", "")).strip(),
                "state_mismatch": bool(row.get("state_mismatch", False)),
                "aggregation_mismatch": bool(row.get("aggregation_mismatch", False)),
                "diag_enabled": bool(row.get("diag_enabled", False)),
                "diag_focus_condition": bool(row.get("diag_focus_condition", False)),
                "diag_state_assignment": str(row.get("diag_state_assignment", "")).strip(),
                "expected_effect": (
                    "prefer_helix_on_ph_shift"
                    if condition in {"ph_low", "ph_high"}
                    else "suppress_helix_on_neutral_compact_rows"
                ),
            }
        )
    order = {"base": 0, "ph_low": 1, "salt_high": 2, "ph_high": 3, "hydro_high": 4, "cooling": 5}
    rows.sort(key=lambda row: order.get(row["condition_group"], 99))
    return rows


def build_payload(
    decision_payload: dict[str, Any],
    failure_packet: dict[str, Any],
    *,
    out_prefix: str,
) -> dict[str, Any]:
    decision_s = dict(decision_payload.get("summary", {}) or {})
    failure_s = dict(failure_packet.get("summary", {}) or {})
    rows = _focus_rows(failure_packet)
    summary = {
        "status": "operator_calibration_packet_ready",
        "packet_scope": "tau_k18_full_fold_corrected_calibration",
        "operator_scope_now": str(decision_s.get("operator_scope_now") or "").strip(),
        "shadow_safe_retained": bool(decision_s.get("shadow_safe_retained", False)),
        "broader_promotion_blocked": bool(decision_s.get("broader_promotion_blocked", True)),
        "blocking_target": str(decision_s.get("blocking_target") or "tau_k18").strip(),
        "blocking_class": str(decision_s.get("blocking_class") or "corrected_path_fragility").strip(),
        "calibration_slice_id": CALIBRATION_SLICE_ID,
        "candidate_rule_name": CANDIDATE_RULE_NAME,
        "candidate_rule_scope": CANDIDATE_RULE_SCOPE,
        "candidate_file": "tools/run_idp_3bead_evaluator.py",
        "candidate_anchor": "short_tau_target_tau_helix_gate",
        "reference_corrected_gate_pass": failure_s.get("tau_k18_corrected_gate_pass"),
        "reference_dominant_state_accuracy": failure_s.get("dominant_state_accuracy"),
        "focus_condition_count": len(rows),
        "state_mismatch_count": sum(int(bool(row["state_mismatch"])) for row in rows),
        "aggregation_mismatch_count": sum(int(bool(row["aggregation_mismatch"])) for row in rows),
        "exact_command": _exact_command(out_prefix),
        "out_prefix": str(_resolve(out_prefix)),
        "decision_reason": (
            "Try one full-fold corrected-path interpretation rule for tau_k18 that only touches pH-shift rows: allow a narrow helix override on ph_low/ph_high and clamp post-gate aggregation so those rows stop outranking the true positive aggregation conditions."
        ),
        "guardrail": (
            "Keep broader_full_idp_promotion blocked and keep controlled_shadow_only_commercial_pretest as the only allowed IDP lane regardless of this slice outcome."
        ),
        "next_required_step": (
            "Run this one full-fold tau_k18 calibration slice, compare it against the r16validation fold6 corrected summary, and keep broader_full_idp_promotion blocked even if the local fold improves."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Tau K18 Full-Fold Corrected Calibration Packet",
        "",
        f"- status: `{s['status']}`",
        f"- packet_scope: `{s['packet_scope']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- blocking_target: `{s['blocking_target']}`",
        f"- blocking_class: `{s['blocking_class']}`",
        f"- calibration_slice_id: `{s['calibration_slice_id']}`",
        f"- candidate_rule_name: `{s['candidate_rule_name']}`",
        f"- candidate_rule_scope: `{s['candidate_rule_scope']}`",
        f"- focus_condition_count: `{s['focus_condition_count']}`",
        f"- state_mismatch_count: `{s['state_mismatch_count']}`",
        f"- aggregation_mismatch_count: `{s['aggregation_mismatch_count']}`",
        "",
        "## Why This Slice",
        "",
        f"- {s['decision_reason']}",
        f"- {s['guardrail']}",
        "",
        "## Exact Command",
        "",
        "```bash",
        s["exact_command"],
        "```",
        "",
        "## Focus Conditions",
        "",
        "| condition | true_state | reference_pred_state | state_mismatch | aggregation_mismatch | expected_effect |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['condition_group']}` | `{row['true_state']}` | `{row['reference_pred_state']}` | `{row['state_mismatch']}` | `{row['aggregation_mismatch']}` | `{row['expected_effect']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a tau_k18 full-fold corrected calibration packet.")
    parser.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    parser.add_argument("--failure-packet-json", default=DEFAULT_FAILURE_PACKET_JSON)
    parser.add_argument("--out-prefix", default=DEFAULT_OUT_PREFIX)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.decision_json),
        _load_json(args.failure_packet_json),
        out_prefix=args.out_prefix,
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
