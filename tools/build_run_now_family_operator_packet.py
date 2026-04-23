#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.operator_surface_contracts import (
    IDP_SAFE_SCOPE_CONTROLLED_PRETEST,
    IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE,
    MEASURED_NOOP_SAFE_SCOPE,
)

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HANDOFF_JSON = "runs/pretest_handoff_bundle_current.json"
DEFAULT_CHECKLIST_JSON = "runs/pretest_command_checklist_current.json"
DEFAULT_GPCR_HANDOFF_JSON = "runs/gpcr_handoff_bundle_current.json"
DEFAULT_IDP_COMMERCIAL_PRETEST_JSON = "runs/idp_commercial_pretest_packet_current.json"
DEFAULT_IDP_COMMERCIAL_PRETEST_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_IDP_BROADER_SHADOW_DECISION_JSON = "runs/idp_broader_shadow_decision_current.json"
DEFAULT_IDP_BROADER_SHADOW_RESULT_JSON = "runs/idp_broader_shadow_result_current.json"
DEFAULT_IDP_BROADER_PROMOTION_RESOLUTION_JSON = "runs/idp_broader_promotion_resolution_current.json"
DEFAULT_IDP_ONE_WIDER_REPEATABILITY_PACKET_JSON = "runs/idp_one_wider_shadow_repeatability_packet_current.json"
DEFAULT_IDP_ONE_WIDER_REPEATABILITY_RESULT_JSON = "runs/idp_one_wider_shadow_repeatability_result_current.json"
DEFAULT_IDP_SCOPE_JSON = "runs/idp_pretest_scope_note_current.json"
DEFAULT_IDP_BLOCKER_JSON = "runs/idp_broader_promotion_blocker_note_current.json"
DEFAULT_CROSS_FAMILY_DECISION_JSON = "runs/cross_family_locked_decoy_shadow_decision_current.json"
DEFAULT_OUT_JSON = "runs/run_now_family_operator_packet_current.json"
DEFAULT_OUT_CSV = "runs/run_now_family_operator_packet_current.csv"
DEFAULT_OUT_MD = "runs/run_now_family_operator_packet_current.md"


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


def _maybe_load_json(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _row_map(rows: list[dict[str, Any]], key: str = "family") -> dict[str, dict[str, Any]]:
    return {
        str(row.get(key, "")).strip(): dict(row)
        for row in rows
        if str(row.get(key, "")).strip()
    }


def build_payload(
    handoff_bundle: dict[str, Any],
    checklist_payload: dict[str, Any],
    gpcr_handoff: dict[str, Any],
    idp_commercial_pretest_payload: dict[str, Any],
    idp_broader_shadow_decision_payload: dict[str, Any] | None,
    idp_broader_shadow_result_payload: dict[str, Any] | None,
    idp_scope_payload: dict[str, Any],
    idp_blocker_payload: dict[str, Any],
    cross_family_decision_payload: dict[str, Any],
    idp_commercial_pretest_decision_payload: dict[str, Any] | None = None,
    idp_broader_promotion_resolution_payload: dict[str, Any] | None = None,
    idp_one_wider_repeatability_packet_payload: dict[str, Any] | None = None,
    idp_one_wider_repeatability_result_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    handoff_rows = _row_map(handoff_bundle.get("rows", []) or [])
    checklist_rows = _row_map(checklist_payload.get("rows", []) or [])
    gpcr_summary = dict(gpcr_handoff.get("summary", {}) or {})
    idp_broader_decision = dict((idp_broader_shadow_decision_payload or {}).get("summary", {}) or {})
    idp_broader_result = dict((idp_broader_shadow_result_payload or {}).get("summary", {}) or {})
    idp_scope = dict(idp_scope_payload.get("summary", {}) or {})
    idp_blocker = dict(idp_blocker_payload.get("summary", {}) or {})
    idp_decision = dict((idp_commercial_pretest_decision_payload or {}).get("summary", {}) or {})
    decision_summary = dict(cross_family_decision_payload.get("summary", {}) or {})
    decision_family_rows = _row_map(cross_family_decision_payload.get("family_rows", []) or [])

    gpcr_handoff_row = handoff_rows.get("gpcr", {})
    idp_handoff_row = handoff_rows.get("idp", {})
    gpcr_check = checklist_rows.get("gpcr", {})
    idp_check = checklist_rows.get("idp", {})
    ion_family = decision_family_rows.get("ion_channel", {})
    kinase_family = decision_family_rows.get("kinase", {})
    idp_pretest = dict(idp_commercial_pretest_payload.get("summary", {}) or {})
    idp_promotion_resolution = dict((idp_broader_promotion_resolution_payload or {}).get("summary", {}) or {})
    idp_repeatability_packet = dict((idp_one_wider_repeatability_packet_payload or {}).get("summary", {}) or {})
    idp_repeatability_result = dict((idp_one_wider_repeatability_result_payload or {}).get("summary", {}) or {})
    idp_repeatability = idp_repeatability_result or idp_repeatability_packet

    rows = [
        {
            "sequence_order": 1,
            "family": "gpcr",
            "operator_lane": "run_now_endpoint_only",
            "safe_scope_now": str(gpcr_handoff_row.get("safe_scope_now", "")).strip(),
            "artifact_check_command": str(gpcr_check.get("artifact_check_command", "")).strip(),
            "guardrail_check_command": str(gpcr_check.get("guardrail_check_command", "")).strip(),
            "no_go_rule": str(gpcr_check.get("do_not_do", "")).strip(),
            "operator_handoff": str(gpcr_summary.get("next_required_step", "")).strip(),
            "source_artifact": "runs/gpcr_handoff_bundle_current.md",
        },
        {
            "sequence_order": 2,
            "family": "ion_channel",
            "operator_lane": "measured_noop_shadow_only",
            "safe_scope_now": MEASURED_NOOP_SAFE_SCOPE,
            "artifact_check_command": "sed -n '1,220p' runs/cross_family_locked_decoy_shadow_decision_current.md",
            "guardrail_check_command": "sed -n '1,220p' runs/cross_family_locked_decoy_shadow_decision_current.md",
            "no_go_rule": "Do not add non-noop residual/apply/router logic to ion_channel without a new measured decision.",
            "operator_handoff": (
                f"Keep ion_channel in measured noop-shadow mode. "
                f"completed_tasks={ion_family.get('completed_candidate_tasks', 0)}/{ion_family.get('task_count', 0)}; "
                f"max_abs_delta_pr_auc={ion_family.get('max_abs_delta_pr_auc', 0)}."
            ),
            "source_artifact": "runs/cross_family_locked_decoy_shadow_decision_current.md",
        },
        {
            "sequence_order": 3,
            "family": "kinase",
            "operator_lane": "measured_noop_shadow_only",
            "safe_scope_now": MEASURED_NOOP_SAFE_SCOPE,
            "artifact_check_command": "sed -n '1,220p' runs/cross_family_locked_decoy_shadow_decision_current.md",
            "guardrail_check_command": "sed -n '1,220p' runs/cross_family_locked_decoy_shadow_decision_current.md",
            "no_go_rule": "Do not add non-noop residual/apply/router logic to kinase without a new measured decision.",
            "operator_handoff": (
                f"Keep kinase in measured noop-shadow mode. "
                f"completed_tasks={kinase_family.get('completed_candidate_tasks', 0)}/{kinase_family.get('task_count', 0)}; "
                f"max_abs_delta_pr_auc={kinase_family.get('max_abs_delta_pr_auc', 0)}."
            ),
            "source_artifact": "runs/cross_family_locked_decoy_shadow_decision_current.md",
        },
        {
            "sequence_order": 4,
            "family": "idp",
            "operator_lane": "run_now_one_wider_shadow_safe" if idp_promotion_resolution else "run_now_controlled_shadow_only",
            "safe_scope_now": str(idp_handoff_row.get("safe_scope_now", "")).strip() or (IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE if idp_promotion_resolution else IDP_SAFE_SCOPE_CONTROLLED_PRETEST),
            "artifact_check_command": (
                "sed -n '1,220p' runs/idp_broader_promotion_resolution_current.md && printf '\\n---\\n' && sed -n '1,220p' runs/idp_one_wider_shadow_repeatability_result_current.md"
                if idp_promotion_resolution and idp_repeatability_result
                else
                "sed -n '1,220p' runs/idp_broader_promotion_resolution_current.md && printf '\\n---\\n' && sed -n '1,220p' runs/idp_one_wider_shadow_repeatability_packet_current.md"
                if idp_promotion_resolution and idp_repeatability_packet
                else
                "sed -n '1,220p' runs/idp_broader_promotion_resolution_current.md"
                if idp_promotion_resolution
                else
                "sed -n '1,220p' runs/idp_broader_shadow_decision_current.md"
                if idp_broader_decision
                else
                "sed -n '1,220p' runs/idp_commercial_pretest_decision_current.md"
                if idp_decision
                else "sed -n '1,220p' runs/idp_commercial_pretest_packet_current.md"
            ),
            "guardrail_check_command": str(idp_check.get("guardrail_check_command", "")).strip(),
            "no_go_rule": (
                "Do not broaden beyond the admitted one-wider shadow-safe lane, change the frozen 8-target roster, enable ranking/gate override, or claim commercialization beyond that bounded lane."
                if idp_promotion_resolution
                else "Do not broaden beyond the controlled shadow-only commercial-pretest scope or enable ranking/gate override."
            ),
            "operator_handoff": (
                f"default_mask={idp_broader_decision.get('default_feature_mask', idp_decision.get('default_feature_mask', idp_pretest.get('default_feature_mask', idp_scope.get('default_feature_mask', ''))))}; "
                f"core={idp_pretest.get('core_target_count', 0)}; "
                f"watchlist={idp_pretest.get('watchlist_target_count', 0)}; "
                f"shadow_safe={idp_promotion_resolution.get('shadow_safe_retained', idp_broader_decision.get('shadow_safe_retained', idp_decision.get('shadow_safe_retained', False)))}; "
                f"broader_shadow_passed={idp_broader_decision.get('broader_shadow_passed', False)}; "
                f"broader_pass_folds={idp_broader_decision.get('corrected_pass_folds', 0)}/{idp_broader_decision.get('fold_count', 0)}; "
                f"wider_lane_admitted={idp_promotion_resolution.get('wider_shadow_safe_lane_admitted', False)}; "
                f"frozen_total_targets={idp_promotion_resolution.get('frozen_total_target_count', 0)}; "
                f"page4_fold_pass={idp_promotion_resolution.get('page4_fold_pass', idp_broader_decision.get('page4_fold_pass', False))}; "
                f"tau_k18_fold_pass={idp_promotion_resolution.get('tau_k18_fold_pass', idp_broader_decision.get('tau_k18_fold_pass', False))}; "
                f"repeatability_status={idp_repeatability.get('status', '')}; "
                f"{idp_scope.get('guardrail', '')} "
                f"{idp_repeatability.get('next_required_step', idp_promotion_resolution.get('next_required_step', idp_broader_decision.get('next_required_step', idp_decision.get('next_required_step', idp_blocker.get('next_required_step', '')))))}"
            ).strip(),
            "source_artifact": (
                "runs/idp_one_wider_shadow_repeatability_result_current.md"
                if idp_repeatability_result
                else
                "runs/idp_one_wider_shadow_repeatability_packet_current.md"
                if idp_repeatability_packet
                else
                "runs/idp_broader_promotion_resolution_current.md"
                if idp_promotion_resolution
                else
                "runs/idp_broader_shadow_decision_current.md"
                if idp_broader_decision
                else "runs/idp_commercial_pretest_decision_current.md"
                if idp_decision
                else "runs/idp_commercial_pretest_packet_current.md"
            ),
        },
    ]

    summary = {
        "family_count": len(rows),
        "run_now_packet_count": 2,
        "measured_noop_packet_count": 2,
        "gpcr_blocked_scope": str(gpcr_handoff_row.get("blocked_scope", "")).strip(),
        "idp_blocked_scope": str(idp_handoff_row.get("blocked_scope", "")).strip(),
        "ion_kinase_decision": str(decision_summary.get("decision", "")).strip(),
        "next_required_step": (
            "Use this operator packet before any new run. Execute only the GPCR apply-safe endpoint and the bounded IDP one-wider shadow-safe repeatability slice; keep ion_channel and kinase in measured noop-shadow mode only."
            if idp_promotion_resolution and idp_repeatability
            else
            "Use this operator packet before any new run. Execute only the GPCR apply-safe endpoint and the admitted one-wider shadow-safe IDP lane; keep ion_channel and kinase in measured noop-shadow mode only."
            if idp_promotion_resolution
            else
            "Use this operator packet before any new run. Execute only the GPCR apply-safe endpoint and the "
            "IDP controlled shadow-only commercial-pretest lane; keep ion_channel and kinase in measured noop-shadow mode only."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Run-Now Family Operator Packet",
        "",
        f"- family_count: `{s['family_count']}`",
        f"- run_now_packet_count: `{s['run_now_packet_count']}`",
        f"- measured_noop_packet_count: `{s['measured_noop_packet_count']}`",
        f"- gpcr_blocked_scope: `{s['gpcr_blocked_scope']}`",
        f"- idp_blocked_scope: `{s['idp_blocked_scope']}`",
        f"- ion_kinase_decision: `{s['ion_kinase_decision']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Operator Rows",
        "",
        "| sequence_order | family | operator_lane | safe_scope_now | artifact_check_command | guardrail_check_command | no_go_rule |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['sequence_order']} | `{row['family']}` | `{row['operator_lane']}` | "
            f"`{row['safe_scope_now']}` | `{row['artifact_check_command']}` | "
            f"`{row['guardrail_check_command']}` | {row['no_go_rule']} |"
        )
    lines.extend(["", "## Handoff Notes", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['family']}`: {row['operator_handoff']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a run-now operator packet for GPCR, ion_channel, kinase, and IDP.")
    parser.add_argument("--handoff-json", default=DEFAULT_HANDOFF_JSON)
    parser.add_argument("--checklist-json", default=DEFAULT_CHECKLIST_JSON)
    parser.add_argument("--gpcr-handoff-json", default=DEFAULT_GPCR_HANDOFF_JSON)
    parser.add_argument("--idp-commercial-pretest-json", default=DEFAULT_IDP_COMMERCIAL_PRETEST_JSON)
    parser.add_argument("--idp-commercial-pretest-decision-json", default=DEFAULT_IDP_COMMERCIAL_PRETEST_DECISION_JSON)
    parser.add_argument("--idp-broader-shadow-decision-json", default=DEFAULT_IDP_BROADER_SHADOW_DECISION_JSON)
    parser.add_argument("--idp-broader-shadow-result-json", default=DEFAULT_IDP_BROADER_SHADOW_RESULT_JSON)
    parser.add_argument("--idp-broader-promotion-resolution-json", default=DEFAULT_IDP_BROADER_PROMOTION_RESOLUTION_JSON)
    parser.add_argument("--idp-one-wider-repeatability-packet-json", default=DEFAULT_IDP_ONE_WIDER_REPEATABILITY_PACKET_JSON)
    parser.add_argument("--idp-one-wider-repeatability-result-json", default=DEFAULT_IDP_ONE_WIDER_REPEATABILITY_RESULT_JSON)
    parser.add_argument("--idp-scope-json", default=DEFAULT_IDP_SCOPE_JSON)
    parser.add_argument("--idp-blocker-json", default=DEFAULT_IDP_BLOCKER_JSON)
    parser.add_argument("--cross-family-decision-json", default=DEFAULT_CROSS_FAMILY_DECISION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.handoff_json),
        _load_json(args.checklist_json),
        _load_json(args.gpcr_handoff_json),
        _load_json(args.idp_commercial_pretest_json),
        _maybe_load_json(args.idp_broader_shadow_decision_json),
        _maybe_load_json(args.idp_broader_shadow_result_json),
        _load_json(args.idp_scope_json),
        _load_json(args.idp_blocker_json),
        _load_json(args.cross_family_decision_json),
        _maybe_load_json(args.idp_commercial_pretest_decision_json),
        _maybe_load_json(args.idp_broader_promotion_resolution_json),
        _maybe_load_json(args.idp_one_wider_repeatability_packet_json),
        _maybe_load_json(args.idp_one_wider_repeatability_result_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
