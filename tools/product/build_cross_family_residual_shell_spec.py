#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

LAYER_JSON = ROOT / "runs/cross_family_residual_shadow_layer_current.json"
PLAN_JSON = ROOT / "runs/cross_family_residual_shadow_layer_plan_current.json"
OUT_JSON = ROOT / "runs/cross_family_residual_shell_current.json"
OUT_CSV = ROOT / "runs/cross_family_residual_shell_current.csv"
OUT_MD = ROOT / "runs/cross_family_residual_shell_current.md"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(layer: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    layer_rows = {str(row.get("family", "")).strip(): row for row in layer.get("rows", [])}
    plan_rows = {str(row.get("family", "")).strip(): row for row in plan.get("family_rows", [])}
    families = ["gpcr", "ion_channel", "kinase", "idp", "non_kinase_enzyme_ca2", "nuclear_receptor_pxr", "transporter"]
    rows: list[dict[str, Any]] = []
    for family in families:
        layer_row = layer_rows.get(family, {})
        plan_row = plan_rows.get(family, {})
        token_state = "reserved_blocked_token"
        abstain_default = "yes"
        gpcr_anchor_policy = ""
        idp_kalman_policy = ""
        if family == "gpcr":
            token_state = "active_measured_family"
            abstain_default = "no"
            gpcr_anchor_policy = "locked_decoy_equal_size_anchor_required"
        elif family in {"ion_channel", "kinase"}:
            token_state = "active_conservative_shadow_family"
            abstain_default = "no"
        elif family == "idp":
            token_state = "placeholder_feature_state_family"
            abstain_default = "yes"
            idp_kalman_policy = "feature_state_smoothing_only_identity_shadow_ready"
        elif family == "transporter":
            token_state = "reserved_unsupported_token"
            abstain_default = "yes"

        rows.append(
            {
                "family": family,
                "family_token": family,
                "token_state": token_state,
                "abstain_default": abstain_default,
                "current_state": str(layer_row.get("current_state", "") or plan_row.get("shadow_status", "")).strip(),
                "shadow_policy": str(layer_row.get("shadow_policy", "") or plan_row.get("residual_mode", "")).strip(),
                "routing_policy": str(layer_row.get("routing_policy", "")).strip(),
                "readiness_signal": str(layer_row.get("readiness_signal", "") or plan_row.get("readiness_signal", "")).strip(),
                "next_required_step": str(layer_row.get("next_required_step", "") or plan_row.get("next_runnable_step", "")).strip(),
                "gpcr_anchor_policy": gpcr_anchor_policy,
                "idp_kalman_policy": idp_kalman_policy,
            }
        )

    summary = {
        "shell_mode": "shadow_only_first",
        "family_count": len(rows),
        "base_score_col": "binding_score_composite_v7",
        "shadow_score_col": "binding_score_composite_v7_residual_shadow",
        "active_score_col": "binding_score_composite_v7_residual_active",
        "family_token_col": "residual_shadow_family",
        "abstain_flag_col": "residual_shadow_abstain",
        "abstain_reason_col": "residual_shadow_abstain_reason",
        "router_uncertainty_col": "residual_router_uncertainty",
        "gpcr_anchor_policy_col": "residual_shadow_gpcr_anchor_policy",
        "idp_kalman_policy_col": "residual_idp_kalman_policy",
        "blocked_promotions": [
            "100k_cross_family_apply_mode_router_promotion",
            "ca2_family_token_activation_before_authoritative_rows_exist",
            "pxr_family_token_activation_before_authoritative_rows_exist",
            "transporter_family_token_activation_before_scaffold_matures",
            "idp_coordinate_correction",
            "idp_ranking_override_from_kalman_placeholder",
            "idp_gate_override_from_kalman_shadow",
        ],
        "kalman_placeholder_outputs": [
            "kalman_branch_posterior_smoothed",
            "kalman_state_posterior_smoothed",
            "kalman_contact_fraction_smoothed",
            "kalman_mean_min_distance_smoothed",
            "kf_shadow_identity_telemetry_only",
        ],
        "next_required_step": (
            "Keep GPCR/ion/kinase in shadow-mode family-token routing, extend authoritative CA2/PXR rows, "
            "and keep IDP limited to feature/state smoothing placeholders until the global shadow shell is fixed."
        ),
    }
    return {"summary": summary, "family_rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Cross-Family Residual Shell",
        "",
        f"- shell_mode: `{payload['summary']['shell_mode']}`",
        f"- family_count: `{payload['summary']['family_count']}`",
        f"- base_score_col: `{payload['summary']['base_score_col']}`",
        f"- shadow_score_col: `{payload['summary']['shadow_score_col']}`",
        f"- family_token_col: `{payload['summary']['family_token_col']}`",
        f"- abstain_flag_col: `{payload['summary']['abstain_flag_col']}`",
        f"- abstain_reason_col: `{payload['summary']['abstain_reason_col']}`",
        f"- router_uncertainty_col: `{payload['summary']['router_uncertainty_col']}`",
        f"- gpcr_anchor_policy_col: `{payload['summary']['gpcr_anchor_policy_col']}`",
        f"- idp_kalman_policy_col: `{payload['summary']['idp_kalman_policy_col']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Blocked Promotions",
        "",
    ]
    for item in payload["summary"]["blocked_promotions"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Kalman Placeholder Outputs", ""])
    for item in payload["summary"]["kalman_placeholder_outputs"]:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Family Shell Rows",
            "",
            "| family | token_state | abstain_default | current_state | readiness_signal | gpcr_anchor_policy | idp_kalman_policy |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["family_rows"]:
        lines.append(
            f"| {row['family']} | {row['token_state']} | {row['abstain_default']} | {row['current_state']} | "
            f"`{row['readiness_signal']}` | {row['gpcr_anchor_policy']} | {row['idp_kalman_policy']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    payload = build_payload(_read_json(LAYER_JSON), _read_json(PLAN_JSON))
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_csv(OUT_CSV, payload["family_rows"])
    _write_markdown(OUT_MD, payload)


if __name__ == "__main__":
    main()
