#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PRETEST_PACKET_JSON = "runs/idp_commercial_pretest_packet_current.json"
DEFAULT_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_ACTIVATION_RESULT_JSON = "runs/tau_k18_full_fold_corrected_calibration_result_current.json"
DEFAULT_OUT_PREFIX = "runs/idp_3bead_holdout_v7_anchor_commercial_pretest_r18validation_r1"
DEFAULT_OUT_JSON = "runs/idp_commercial_pretest_validation_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_commercial_pretest_validation_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_commercial_pretest_validation_packet_current.md"


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


def _exact_command(out_prefix: str, feature_mask: str) -> str:
    return " ".join(
        [
            "IDP_R17_TAU_PH_SPLIT_PATCH=1",
            "IDP_R18_TAU_PH_HELIX_RECOVERY_PATCH=1",
            "python3",
            "tools/run_idp_3bead_holdout_pipeline.py",
            "--config-json",
            str(_resolve("config/idp_3bead_benchmark_v7_literature_anchor_subset.json")),
            "--device",
            "cuda",
            "--out-prefix",
            str(_resolve(out_prefix)),
            "--resume-existing",
            "0",
            "--kalman-shadow-enable",
            "1",
            "--kalman-shadow-mode",
            "feature_state_v1",
            "--kalman-shadow-family-token",
            "idp",
            "--kalman-shadow-feature-mask",
            feature_mask,
            "--kalman-shadow-obs-noise-scale",
            "0.15",
            "--kalman-shadow-process-noise-scale",
            "0.03",
            "--kalman-shadow-delta-cap-frac",
            "0.25",
        ]
    )


def build_payload(
    pretest_packet: dict[str, Any],
    decision_payload: dict[str, Any],
    activation_result: dict[str, Any],
    *,
    out_prefix: str,
) -> dict[str, Any]:
    pretest_s = dict(pretest_packet.get("summary", {}) or {})
    decision_s = dict(decision_payload.get("summary", {}) or {})
    activation_s = dict(activation_result.get("summary", {}) or {})
    feature_mask = str(decision_s.get("default_feature_mask", pretest_s.get("default_feature_mask", "rg_sasa_only"))).strip() or "rg_sasa_only"
    follow_up_rule_name = str(
        activation_s.get("candidate_rule_name", activation_s.get("activation_rule_name", ""))
    ).strip()
    follow_up_status = str(activation_s.get("status", "")).strip()
    follow_up_observation = str(
        activation_s.get(
            "primary_observation",
            "tau_k18_local_full_fold_calibration_passed" if activation_s.get("calibration_corrected_gate_pass", False) else "",
        )
    ).strip()

    rows: list[dict[str, Any]] = []
    for row in pretest_packet.get("rows", []) or []:
        target = str(row.get("target_name", "")).strip()
        lane = str(row.get("lane", "")).strip()
        risk_class = str(row.get("risk_class", "")).strip()
        rows.append(
            {
                "target_name": target,
                "lane": lane,
                "risk_class": risk_class,
                "recommended_mask": str(row.get("recommended_mask", feature_mask)).strip() or feature_mask,
                "validation_priority": "focus_blocker_target" if target == "tau_k18" else ("watchlist_confirm" if "watchlist" in lane else "core_regression_guard"),
                "success_gate": (
                    "corrected_gate_pass must stay true and no corrected-path fragility may reappear"
                    if target == "tau_k18"
                    else "would_have_changed_state and would_have_changed_gate must both stay zero"
                ),
            }
        )

    summary = {
        "status": "operator_validation_packet_ready",
        "validation_scope": "bounded_idp_commercial_pretest_rerun",
        "operator_scope_now": str(decision_s.get("operator_scope_now", "")).strip(),
        "broader_promotion_blocked": bool(decision_s.get("broader_promotion_blocked", True)),
        "shadow_safe_retained": bool(decision_s.get("shadow_safe_retained", False)),
        "default_feature_mask": feature_mask,
        "core_target_count": int(pretest_s.get("core_target_count", 0) or 0),
        "watchlist_target_count": int(pretest_s.get("watchlist_target_count", 0) or 0),
        "row_count": len(rows),
        "focus_validation_target": "tau_k18",
        "activation_rule_name": follow_up_rule_name,
        "activation_status": follow_up_status,
        "activation_observation": follow_up_observation,
        "out_prefix": str(_resolve(out_prefix)),
        "exact_command": _exact_command(out_prefix, feature_mask),
        "next_required_step": (
            "Run this bounded commercial-pretest rerun, confirm tau_k18 keeps the latest short-tau calibration improvement and corrected gate pass, "
            "and keep broader_full_idp_promotion blocked unless the full bounded slice stays clean."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Commercial Pretest Validation Packet",
        "",
        f"- status: `{s['status']}`",
        f"- validation_scope: `{s['validation_scope']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- default_feature_mask: `{s['default_feature_mask']}`",
        f"- core_target_count: `{s['core_target_count']}`",
        f"- watchlist_target_count: `{s['watchlist_target_count']}`",
        f"- row_count: `{s['row_count']}`",
        f"- focus_validation_target: `{s['focus_validation_target']}`",
        f"- activation_rule_name: `{s['activation_rule_name']}`",
        f"- activation_status: `{s['activation_status']}`",
        f"- activation_observation: `{s['activation_observation']}`",
        "",
        "## Exact Command",
        "",
        "```bash",
        s["exact_command"],
        "```",
        "",
        "## Validation Targets",
        "",
        "| target | lane | risk_class | validation_priority | success_gate |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_name']}` | `{row['lane']}` | `{row['risk_class']}` | `{row['validation_priority']}` | {row['success_gate']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a bounded IDP commercial-pretest validation packet.")
    parser.add_argument("--pretest-packet-json", default=DEFAULT_PRETEST_PACKET_JSON)
    parser.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    parser.add_argument("--activation-result-json", default=DEFAULT_ACTIVATION_RESULT_JSON)
    parser.add_argument("--out-prefix", default=DEFAULT_OUT_PREFIX)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.pretest_packet_json),
        _load_json(args.decision_json),
        _load_json(args.activation_result_json),
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
