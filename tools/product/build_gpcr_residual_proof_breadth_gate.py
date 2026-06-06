#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GPCR_PROOF_JSON = "runs/gpcr_hard_decoy_residual_proof_current.json"
DEFAULT_GPCR_ASSIST_SELECTION_JSON = "runs/gpcr_residual_assist_candidate_selection_current.json"
DEFAULT_HELDOUT_SCORECARD_JSON = "runs/gpcr_family_heldout_scorecard_coverage_v1_current.json"
DEFAULT_HELDOUT_GUARDRAIL_JSON = "runs/gpcr_family_heldout_scorecard_guardrail_coverage_v1_current.json"
DEFAULT_CI_LOW_RECOVERY_JSON = "runs/gpcr_ci_low_recovery_packet_beta_blocker_rescue_v2_coverage_v1_full_current.json"
DEFAULT_SCALEUP_TRIAGE_JSON = "runs/gpcr_scaleup_regression_triage_beta_blocker_rescue_v2_coverage_v1_full_current.json"
DEFAULT_GUARDED_RERUN_JSON = "runs/gpcr_guarded_100k_rerun_readiness_beta_blocker_rescue_v2_coverage_v1_full_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_residual_proof_breadth_gate_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_residual_proof_breadth_gate_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_residual_proof_breadth_gate_current.md"

CLAIM_BOUNDARY = (
    "GPCR residual proof breadth gate only; audits existing local GPCR proof, assist-selection, heldout, "
    "guardrail, CI-low recovery, scaleup triage, and guarded-rerun readiness artifacts. It does not run docking, "
    "train models, alter ranking defaults, promote assist/production mode, upload, submit, email, archive, "
    "externalize, or delete files."
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
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _row(
    check_id: str,
    status: str,
    observed: str,
    required: str,
    source_artifact: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "observed": observed,
        "required": required,
        "source_artifact": source_artifact,
        "reason": reason,
        "release_blocker": status != "pass",
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
    }


def build_gpcr_residual_proof_breadth_gate(
    *,
    gpcr_proof_packet: dict[str, Any],
    gpcr_assist_selection_packet: dict[str, Any],
    heldout_scorecard_packet: dict[str, Any],
    heldout_guardrail_packet: dict[str, Any],
    ci_low_recovery_packet: dict[str, Any],
    scaleup_triage_packet: dict[str, Any],
    guarded_rerun_packet: dict[str, Any],
    gpcr_proof_path: str = DEFAULT_GPCR_PROOF_JSON,
    gpcr_assist_selection_path: str = DEFAULT_GPCR_ASSIST_SELECTION_JSON,
    heldout_scorecard_path: str = DEFAULT_HELDOUT_SCORECARD_JSON,
    heldout_guardrail_path: str = DEFAULT_HELDOUT_GUARDRAIL_JSON,
    ci_low_recovery_path: str = DEFAULT_CI_LOW_RECOVERY_JSON,
    scaleup_triage_path: str = DEFAULT_SCALEUP_TRIAGE_JSON,
    guarded_rerun_path: str = DEFAULT_GUARDED_RERUN_JSON,
) -> dict[str, Any]:
    gpcr = _summary(gpcr_proof_packet)
    assist = _summary(gpcr_assist_selection_packet)
    heldout = _summary(heldout_scorecard_packet)
    guardrail = _summary(heldout_guardrail_packet)
    ci_low = _summary(ci_low_recovery_packet)
    scaleup = _summary(scaleup_triage_packet)
    guarded = _summary(guarded_rerun_packet)

    proof_ready = (
        _text(gpcr.get("status")) == "gpcr_hard_decoy_residual_proof_ready"
        and gpcr.get("gpcr_hard_decoy_residual_proof_ready") is True
        and _int(gpcr.get("pass_to_fail_regression_count")) == 0
        and _int(gpcr.get("binder_retention_fail_count")) == 0
        and _int(gpcr.get("intrusion_reduction_task_count")) >= 1
    )
    assist_clean = (
        _text(assist.get("status")) == "gpcr_residual_assist_candidate_selection_ready"
        and assist.get("assist_candidate_ready") is True
        and _int(assist.get("pr_auc_regression_warning_count")) == 0
        and _int(assist.get("pass_to_fail_regression_count")) == 0
        and _int(assist.get("residual_applied_task_count")) >= 1
    )
    heldout_ready = (
        heldout.get("acceptance_overall_pass") is True
        and _text(heldout.get("scorecard_level_status")) == "pass"
        and _int(heldout.get("blocker_count")) == 0
        and _int(heldout.get("gpcr_distinct_positive_target_count")) >= 5
        and _int(heldout.get("gpcr_positive_count")) >= 9
    )
    heldout_guardrail_ready = (
        _text(guardrail.get("status")) == "green"
        and guardrail.get("acceptance_overall_pass") is True
        and _int(guardrail.get("blocker_count")) == 0
        and guardrail.get("blocking_warning_present") is False
    )
    ci_low_ready = (
        ci_low.get("pass") is True
        and ci_low.get("ci_low_blocker") is False
        and _float(ci_low.get("ranking_pr_auc_ci_low")) >= _float(ci_low.get("threshold"))
        and _int(ci_low.get("ranking_positive_count")) >= 9
    )
    scaleup_clean = (
        _int(scaleup.get("guardrail_fail_count")) == 0
        and _int(scaleup.get("rejected_candidate_count")) == 0
        and _int(scaleup.get("candidate_count")) >= 1
    )
    guarded_ready = (
        _text(guarded.get("status")) == "eligible"
        and guarded.get("launch_eligible") is True
        and _int(guarded.get("blocker_count")) == 0
        and _int(guarded.get("launch_blocker_count")) == 0
    )

    rows = [
        _row(
            "narrow_hard_decoy_proof_ready",
            "pass" if proof_ready else "fail",
            f"task_count={gpcr.get('task_count')}; intrusion_reduction_task_count={gpcr.get('intrusion_reduction_task_count')}; pass_to_fail={gpcr.get('pass_to_fail_regression_count')}; binder_retention_fail_count={gpcr.get('binder_retention_fail_count')}",
            "hard-decoy proof ready, at least one intrusion-reduction task, zero pass-to-fail and binder-retention failures",
            gpcr_proof_path,
            "Confirms the residual layer targets the measured GPCR hard-decoy failure mode.",
        ),
        _row(
            "clean_per_task_assist_selection",
            "pass" if assist_clean else "fail",
            f"task_count={assist.get('task_count')}; residual_applied_task_count={assist.get('residual_applied_task_count')}; pr_auc_regression_warning_count={assist.get('pr_auc_regression_warning_count')}; pass_to_fail={assist.get('pass_to_fail_regression_count')}",
            "clean per-task assist selection with zero PR-AUC warnings and zero pass-to-fail regressions",
            gpcr_assist_selection_path,
            "Converts a narrow global-apply warning into an auditable abstain/apply routing policy.",
        ),
        _row(
            "family_heldout_target_breadth",
            "pass" if heldout_ready else "fail",
            f"distinct_positive_targets={heldout.get('gpcr_distinct_positive_target_count')}; positive_count={heldout.get('gpcr_positive_count')}; blocker_count={heldout.get('blocker_count')}",
            "at least five distinct GPCR positive targets, at least nine positives, and scorecard pass",
            heldout_scorecard_path,
            "Shows GPCR breadth beyond the two residual proof slices.",
        ),
        _row(
            "family_heldout_guardrail_clean",
            "pass" if heldout_guardrail_ready else "fail",
            f"status={guardrail.get('status')}; blocker_count={guardrail.get('blocker_count')}; blocking_warning_present={guardrail.get('blocking_warning_present')}",
            "green guardrail, zero blockers, and no blocking warnings",
            heldout_guardrail_path,
            "Prevents the breadth claim from leaning on an unguarded scorecard.",
        ),
        _row(
            "ci_low_recovery_green",
            "pass" if ci_low_ready else "fail",
            f"ranking_positive_count={ci_low.get('ranking_positive_count')}; ranking_pr_auc_ci_low={ci_low.get('ranking_pr_auc_ci_low')}; threshold={ci_low.get('threshold')}; ci_low_blocker={ci_low.get('ci_low_blocker')}",
            "CI-low recovery packet passes the operational PR-AUC threshold",
            ci_low_recovery_path,
            "Checks that the recovery signal survives conservative uncertainty accounting.",
        ),
        _row(
            "scaleup_regression_triage_clean",
            "pass" if scaleup_clean else "fail",
            f"candidate_count={scaleup.get('candidate_count')}; guardrail_fail_count={scaleup.get('guardrail_fail_count')}; rejected_candidate_count={scaleup.get('rejected_candidate_count')}; claim_safe={scaleup.get('claim_safe')}",
            "scaleup triage has at least one candidate and zero guardrail/rejection failures",
            scaleup_triage_path,
            "Allows breadth evidence as comparison-only while keeping claim promotion disabled.",
        ),
        _row(
            "guarded_100k_rerun_ready",
            "pass" if guarded_ready else "fail",
            f"status={guarded.get('status')}; launch_eligible={guarded.get('launch_eligible')}; blocker_count={guarded.get('blocker_count')}; launch_blocker_count={guarded.get('launch_blocker_count')}",
            "guarded 100k rerun inputs are eligible with zero blockers",
            guarded_rerun_path,
            "Confirms the next larger GPCR run is unblocked without promoting production claims.",
        ),
    ]
    fail_rows = [row for row in rows if row["status"] != "pass"]
    effective_breadth_count = max(
        _int(gpcr.get("task_count")),
        _int(assist.get("task_count")),
        _int(heldout.get("gpcr_distinct_positive_target_count")),
    )
    pr_auc_warning_count = _int(assist.get("pr_auc_regression_warning_count"))
    pass_to_fail_count = _int(gpcr.get("pass_to_fail_regression_count")) + _int(assist.get("pass_to_fail_regression_count"))
    gate_ready = bool(
        not fail_rows
        and effective_breadth_count >= 5
        and pr_auc_warning_count == 0
        and pass_to_fail_count == 0
        and _int(gpcr.get("intrusion_reduction_task_count")) >= 1
    )
    summary = {
        "packet_type": "gpcr_residual_proof_breadth_gate",
        "status": "gpcr_residual_proof_breadth_gate_ready" if gate_ready else "blocked_gpcr_residual_proof_breadth_gate",
        "gpcr_residual_proof_breadth_gate_ready": gate_ready,
        "assist_promotion_allowed": gate_ready,
        "production_promotion_allowed": False,
        "effective_gpcr_breadth_count": effective_breadth_count,
        "minimum_effective_gpcr_breadth_count": 5,
        "proof_task_count": _int(gpcr.get("task_count")),
        "assist_selection_task_count": _int(assist.get("task_count")),
        "heldout_distinct_positive_target_count": _int(heldout.get("gpcr_distinct_positive_target_count")),
        "pr_auc_regression_warning_count": pr_auc_warning_count,
        "pass_to_fail_regression_count": pass_to_fail_count,
        "intrusion_reduction_task_count": _int(gpcr.get("intrusion_reduction_task_count")),
        "check_count": len(rows),
        "pass_check_count": len(rows) - len(fail_rows),
        "fail_check_count": len(fail_rows),
        "failed_check_ids": [row["check_id"] for row in fail_rows],
        "primary_blocker": fail_rows[0]["check_id"] if fail_rows else "none",
        "execution_enabled": False,
        "benchmark_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use this as GPCR breadth evidence for commercial gap closure item 4; production promotion remains disabled."
            if gate_ready
            else f"Repair `{fail_rows[0]['check_id']}` before GPCR breadth closure."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# GPCR Residual Proof Breadth Gate",
        "",
        f"- status: `{s['status']}`",
        f"- gpcr_residual_proof_breadth_gate_ready: `{s['gpcr_residual_proof_breadth_gate_ready']}`",
        f"- effective_gpcr_breadth_count: `{s['effective_gpcr_breadth_count']}` / `{s['minimum_effective_gpcr_breadth_count']}`",
        f"- pr_auc_regression_warning_count: `{s['pr_auc_regression_warning_count']}`",
        f"- pass_to_fail_regression_count: `{s['pass_to_fail_regression_count']}`",
        f"- pass_check_count: `{s['pass_check_count']}` / `{s['check_count']}`",
        f"- primary_blocker: `{s['primary_blocker']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` | {row['reason']} |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPCR residual proof breadth gate from local artifacts.")
    parser.add_argument("--gpcr-proof-json", default=DEFAULT_GPCR_PROOF_JSON)
    parser.add_argument("--gpcr-assist-selection-json", default=DEFAULT_GPCR_ASSIST_SELECTION_JSON)
    parser.add_argument("--heldout-scorecard-json", default=DEFAULT_HELDOUT_SCORECARD_JSON)
    parser.add_argument("--heldout-guardrail-json", default=DEFAULT_HELDOUT_GUARDRAIL_JSON)
    parser.add_argument("--ci-low-recovery-json", default=DEFAULT_CI_LOW_RECOVERY_JSON)
    parser.add_argument("--scaleup-triage-json", default=DEFAULT_SCALEUP_TRIAGE_JSON)
    parser.add_argument("--guarded-rerun-json", default=DEFAULT_GUARDED_RERUN_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_gpcr_residual_proof_breadth_gate(
        gpcr_proof_packet=_read_json_if_present(args.gpcr_proof_json),
        gpcr_assist_selection_packet=_read_json_if_present(args.gpcr_assist_selection_json),
        heldout_scorecard_packet=_read_json_if_present(args.heldout_scorecard_json),
        heldout_guardrail_packet=_read_json_if_present(args.heldout_guardrail_json),
        ci_low_recovery_packet=_read_json_if_present(args.ci_low_recovery_json),
        scaleup_triage_packet=_read_json_if_present(args.scaleup_triage_json),
        guarded_rerun_packet=_read_json_if_present(args.guarded_rerun_json),
        gpcr_proof_path=args.gpcr_proof_json,
        gpcr_assist_selection_path=args.gpcr_assist_selection_json,
        heldout_scorecard_path=args.heldout_scorecard_json,
        heldout_guardrail_path=args.heldout_guardrail_json,
        ci_low_recovery_path=args.ci_low_recovery_json,
        scaleup_triage_path=args.scaleup_triage_json,
        guarded_rerun_path=args.guarded_rerun_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
