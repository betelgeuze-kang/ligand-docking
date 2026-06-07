#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path


RUNS = Path("runs")

CORE_PACKET_JSON = RUNS / "commercial_core_preservation_packet_current.json"
EXECUTION_DASHBOARD_JSON = RUNS / "execution_handoff_dashboard_current.json"
GAP_BURNDOWN_JSON = RUNS / "commercialization_gap_burndown_current.json"
HEATMAP_JSON = RUNS / "family_readiness_heatmap_current.json"
FAMILY_PACKET_CATALOG_JSON = RUNS / "family_packet_catalog_current.json"
PLATFORM_QUICKSTART_JSON = RUNS / "platform_operator_quickstart_packet_current.json"
FAMILY_QUICKLINK_BOARD_JSON = RUNS / "family_operator_quicklink_board_current.json"
PARTIAL_COMMIT_LAUNCHBOARD_JSON = RUNS / "partial_authoritative_commit_launchboard_current.json"
TRANSPORTER_QUICKSTART_JSON = RUNS / "transporter_manual_review_quickstart_packet_current.json"
OPERATOR_EVIDENCE_CLOSURE_JSON = RUNS / "operator_evidence_closure_console_current.json"
IDP_COMMERCIAL_PRETEST_JSON = RUNS / "idp_commercial_pretest_packet_current.json"

OUT_JSON = RUNS / "platform_packet_index_current.json"
OUT_CSV = RUNS / "platform_packet_index_current.csv"
OUT_MD = RUNS / "platform_packet_index_current.md"


def load_json(path: Path) -> dict:
    with path.open() as fh:
        return json.load(fh)


def build_rows(
    core_packet: dict,
    execution_dashboard: dict,
    gap_burndown: dict,
    family_heatmap: dict,
    family_packet_catalog: dict,
    platform_quickstart: dict,
    family_quicklink_board: dict,
    partial_commit_launchboard: dict,
    transporter_quickstart: dict,
    operator_evidence_closure: dict,
    idp_commercial_pretest: dict,
) -> list[dict]:
    core_summary = core_packet["summary"]
    exec_summary = execution_dashboard["summary"]
    gap_summary = gap_burndown["summary"]
    heat_summary = family_heatmap["summary"]
    catalog_summary = family_packet_catalog["summary"]
    quickstart_summary = platform_quickstart["summary"]
    quicklink_summary = family_quicklink_board["summary"]
    partial_commit_summary = partial_commit_launchboard["summary"]
    transporter_quickstart_summary = transporter_quickstart["summary"]
    operator_console_summary = operator_evidence_closure["summary"]
    idp_pretest_summary = idp_commercial_pretest["summary"]

    return [
        {
            "packet_key": "platform_operator_quickstart",
            "packet_label": "Platform Operator Quickstart Packet",
            "purpose": "Give the fastest bounded read on run-now, prepare-next, and manual-review lanes before drilling deeper.",
            "artifact_path": str(OUT_MD.parent / "platform_operator_quickstart_packet_current.md"),
            "primary_signal": f"run_now={quickstart_summary['run_now_count']}",
            "secondary_signal": f"prepare_next={quickstart_summary['prepare_next_count']}",
            "open_first_when": "You want the shortest operator-facing summary before opening family-specific packets.",
        },
        {
            "packet_key": "family_packet_catalog",
            "packet_label": "Family Packet Catalog",
            "purpose": "Jump straight from the platform view into the correct packet stack for a specific family.",
            "artifact_path": str(OUT_MD.parent / "family_packet_catalog_current.md"),
            "primary_signal": f"family_packets={catalog_summary['family_packet_count']}",
            "secondary_signal": f"top_level_packets={catalog_summary['top_level_packet_count']}",
            "open_first_when": "You already know which family or lane you need and want the right first packet immediately.",
        },
        {
            "packet_key": "family_operator_quicklink_board",
            "packet_label": "Family Operator Quicklink Board",
            "purpose": "Jump directly to the open-first artifact and guardrail command for each active family lane.",
            "artifact_path": str(OUT_MD.parent / "family_operator_quicklink_board_current.md"),
            "primary_signal": f"quicklinks={quicklink_summary['quicklink_row_count']}",
            "secondary_signal": f"lanes={quicklink_summary['lane_count']}",
            "open_first_when": "You know the family lane and want the fastest open-first artifact plus guardrail command.",
        },
        {
            "packet_key": "partial_authoritative_commit_launchboard",
            "packet_label": "Partial-Authoritative Commit Launchboard",
            "purpose": "Open CA2/PXR commit packets in strict order and stop at the right finish line without broadening scope.",
            "artifact_path": str(OUT_MD.parent / "partial_authoritative_commit_launchboard_current.md"),
            "primary_signal": f"confirm_now={partial_commit_summary['total_confirm_now_count']}",
            "secondary_signal": f"must_defer={partial_commit_summary['total_must_remain_deferred_count']}",
            "open_first_when": "You are working the CA2/PXR partial-authoritative lane and need the exact commit-packet order.",
        },
        {
            "packet_key": "transporter_manual_review_quickstart",
            "packet_label": "Transporter Manual Review Quickstart Packet",
            "purpose": "Open the transporter blocker-closure and seed-row promotion lane at the right wave order before drilling into AQP1 or GLUT1 reviewer packets.",
            "artifact_path": str(OUT_MD.parent / "transporter_manual_review_quickstart_packet_current.md"),
            "primary_signal": f"seed_rows={transporter_quickstart_summary['binder_lane_count']}",
            "secondary_signal": f"donor_reopen_ready={transporter_quickstart_summary['donor_policy_reopen_ready']}",
            "open_first_when": "You are entering the transporter lane from the top level and need the shortest first-wave vs second-wave blocker-closure plan.",
        },
        {
            "packet_key": "idp_commercial_pretest",
            "packet_label": "IDP Commercial Pretest Decision",
            "purpose": "Operate IDP on the current controlled shadow-only commercial-pretest lane and use the decision artifact as the canonical source while broader promotion stays blocked.",
            "artifact_path": str(OUT_MD.parent / "idp_commercial_pretest_decision_current.md"),
            "primary_signal": f"subset_safe_now={'yes' if idp_pretest_summary.get('broader_promotion_blocked', True) else 'no'}",
            "secondary_signal": f"pretest_ready=core:{idp_pretest_summary['core_target_count']} watch:{idp_pretest_summary['watchlist_target_count']}",
            "open_first_when": "You are touching IDP next and need the current commercial-pretest decision first, with broader promotion still explicitly blocked.",
        },
        {
            "packet_key": "operator_evidence_closure_console",
            "packet_label": "Operator Evidence Closure Console",
            "purpose": "Work across CA2, PXR, and transporter in the right daily order without reconstructing the lane sequence manually.",
            "artifact_path": str(OUT_MD.parent / "operator_evidence_closure_console_current.md"),
            "primary_signal": f"console_rows={operator_console_summary['console_row_count']}",
            "secondary_signal": f"transporter_targets={operator_console_summary['transporter_today_target_count']}",
            "open_first_when": "You want the same-day cross-family work queue before dropping into any one family console.",
        },
        {
            "packet_key": "commercial_core_preservation",
            "packet_label": "Commercial Core Preservation Packet",
            "purpose": "Protect the commercial core while expansion families continue evidence closure.",
            "artifact_path": str(OUT_MD.parent / "commercial_core_preservation_packet_current.md"),
            "primary_signal": f"core_lane={core_summary['core_commercial_lane_score']}",
            "secondary_signal": f"gpcr_router={core_summary['gpcr_router_status']}",
            "open_first_when": "You need the non-regression rules for GPCR, ion_channel, kinase, and IDP.",
        },
        {
            "packet_key": "execution_handoff_dashboard",
            "packet_label": "Execution Handoff Dashboard",
            "purpose": "See what can run now, what should be prepared next, and what stays manual-review only.",
            "artifact_path": str(OUT_MD.parent / "execution_handoff_dashboard_current.md"),
            "primary_signal": f"run_now={exec_summary['run_now_count']}",
            "secondary_signal": f"prepare_next={exec_summary['prepare_next_count']}",
            "open_first_when": "You need the current execution lane and next required step by family.",
        },
        {
            "packet_key": "commercialization_gap_burndown",
            "packet_label": "Commercialization Gap Burndown",
            "purpose": "Prioritize the remaining commercialization gaps across core and expansion families.",
            "artifact_path": str(OUT_MD.parent / "commercialization_gap_burndown_current.md"),
            "primary_signal": f"highest_gap={gap_summary['highest_gap_family']}",
            "secondary_signal": f"blocked={gap_summary['blocked_count']}",
            "open_first_when": "You need the next gap-closing order across transporter, CA2/PXR, and IDP broader scope.",
        },
        {
            "packet_key": "family_readiness_heatmap",
            "packet_label": "Family Readiness Heatmap",
            "purpose": "Get a fast visual lane-level view of run-now, prep, and manual-review families.",
            "artifact_path": str(OUT_MD.parent / "family_readiness_heatmap_current.md"),
            "primary_signal": f"run_now={heat_summary['run_now_count']}",
            "secondary_signal": f"manual_review={heat_summary['manual_review_count']}",
            "open_first_when": "You want the quickest family-by-family readiness snapshot before drilling into a packet.",
        },
    ]


def build_summary(
    core_packet: dict,
    execution_dashboard: dict,
    gap_burndown: dict,
    family_heatmap: dict,
    family_packet_catalog: dict,
    platform_quickstart: dict,
    family_quicklink_board: dict,
    partial_commit_launchboard: dict,
    transporter_quickstart: dict,
    operator_evidence_closure: dict,
    idp_commercial_pretest: dict,
    rows: list[dict],
) -> dict:
    core_summary = core_packet["summary"]
    exec_summary = execution_dashboard["summary"]
    gap_summary = gap_burndown["summary"]
    heat_summary = family_heatmap["summary"]
    catalog_summary = family_packet_catalog["summary"]
    quickstart_summary = platform_quickstart["summary"]
    quicklink_summary = family_quicklink_board["summary"]
    partial_commit_summary = partial_commit_launchboard["summary"]
    transporter_quickstart_summary = transporter_quickstart["summary"]
    operator_console_summary = operator_evidence_closure["summary"]
    idp_pretest_summary = idp_commercial_pretest["summary"]

    return {
        "packet_count": len(rows),
        "commercial_core_packet_ready": True,
        "execution_dashboard_ready": True,
        "commercialization_gap_burndown_ready": True,
        "family_heatmap_ready": True,
        "family_packet_catalog_ready": True,
        "platform_operator_quickstart_ready": True,
        "family_operator_quicklink_board_ready": True,
        "idp_commercial_pretest_ready": True,
        "core_commercial_lane_score": core_summary["core_commercial_lane_score"],
        "all_category_expansion_score": core_summary["all_category_expansion_score"],
        "run_now_count": exec_summary["run_now_count"],
        "prepare_next_count": exec_summary["prepare_next_count"],
        "highest_gap_family": gap_summary["highest_gap_family"],
        "manual_review_count": heat_summary["manual_review_count"],
        "manual_review_target_count": quicklink_summary["manual_review_count"],
        "partial_commit_launchboard_ready": True,
        "partial_commit_confirm_now_count": partial_commit_summary["total_confirm_now_count"],
        "transporter_manual_review_quickstart_ready": True,
        "transporter_manual_review_seed_row_count": transporter_quickstart_summary["binder_lane_count"],
        "transporter_manual_review_binder_pending_count": transporter_quickstart_summary["binder_pending_manual_verdict_count"],
        "idp_commercial_pretest_target_count": idp_pretest_summary["row_count"],
        "operator_evidence_closure_ready": True,
        "operator_evidence_closure_console_row_count": operator_console_summary["console_row_count"],
        "family_packet_count": catalog_summary["family_packet_count"],
        "platform_quickstart_run_now_count": quickstart_summary["run_now_count"],
        "family_quicklink_row_count": quicklink_summary["quicklink_row_count"],
        "index_use_rule": (
            "Start with the platform quickstart for the shortest lane summary, use the family packet catalog to jump "
            "to the right family packet, use the family quicklink board for open-first artifacts and guardrails, "
            "use the execution dashboard for current run lanes, use the commercial-core packet for non-regression "
            "rules, and use the burndown board for expansion family priority."
        ),
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, summary: dict, rows: list[dict]) -> None:
    lines = [
        "# Platform Packet Index",
        "",
        f"- packet_count: `{summary['packet_count']}`",
        f"- core_commercial_lane_score: `{summary['core_commercial_lane_score']}`",
        f"- all_category_expansion_score: `{summary['all_category_expansion_score']}`",
        f"- run_now_count: `{summary['run_now_count']}`",
        f"- prepare_next_count: `{summary['prepare_next_count']}`",
        f"- highest_gap_family: `{summary['highest_gap_family']}`",
        f"- manual_review_count: `{summary['manual_review_count']}`",
        f"- manual_review_target_count: `{summary['manual_review_target_count']}`",
        f"- partial_commit_confirm_now_count: `{summary['partial_commit_confirm_now_count']}`",
        f"- transporter_manual_review_seed_row_count: `{summary['transporter_manual_review_seed_row_count']}`",
        f"- idp_commercial_pretest_target_count: `{summary['idp_commercial_pretest_target_count']}`",
        f"- operator_evidence_closure_console_row_count: `{summary['operator_evidence_closure_console_row_count']}`",
        f"- family_packet_count: `{summary['family_packet_count']}`",
        f"- family_quicklink_row_count: `{summary['family_quicklink_row_count']}`",
        "",
        "## How To Use",
        "",
        f"- {summary['index_use_rule']}",
        "",
        "## Navigation",
        "",
        "| packet | purpose | primary signal | secondary signal | open first when | artifact |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| `{packet_label}` | {purpose} | `{primary_signal}` | `{secondary_signal}` | {open_first_when} | `{artifact_path}` |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Suggested Order",
            "",
            "1. `runs/platform_operator_quickstart_packet_current.md`",
            "2. `runs/family_packet_catalog_current.md`",
            "3. `runs/family_operator_quicklink_board_current.md`",
            "4. `runs/operator_evidence_closure_console_current.md`",
            "5. `runs/transporter_manual_review_quickstart_packet_current.md`",
            "6. `runs/idp_commercial_pretest_decision_current.md`",
            "7. `runs/partial_authoritative_commit_launchboard_current.md`",
            "8. `runs/execution_handoff_dashboard_current.md`",
            "9. `runs/commercial_core_preservation_packet_current.md`",
            "10. `runs/commercialization_gap_burndown_current.md`",
            "11. `runs/family_readiness_heatmap_current.md`",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    core_packet = load_json(CORE_PACKET_JSON)
    execution_dashboard = load_json(EXECUTION_DASHBOARD_JSON)
    gap_burndown = load_json(GAP_BURNDOWN_JSON)
    family_heatmap = load_json(HEATMAP_JSON)
    family_packet_catalog = load_json(FAMILY_PACKET_CATALOG_JSON)
    platform_quickstart = load_json(PLATFORM_QUICKSTART_JSON)
    family_quicklink_board = load_json(FAMILY_QUICKLINK_BOARD_JSON)
    partial_commit_launchboard = load_json(PARTIAL_COMMIT_LAUNCHBOARD_JSON)
    transporter_quickstart = load_json(TRANSPORTER_QUICKSTART_JSON)
    operator_evidence_closure = load_json(OPERATOR_EVIDENCE_CLOSURE_JSON)
    idp_commercial_pretest = load_json(IDP_COMMERCIAL_PRETEST_JSON)

    rows = build_rows(
        core_packet,
        execution_dashboard,
        gap_burndown,
        family_heatmap,
        family_packet_catalog,
        platform_quickstart,
        family_quicklink_board,
        partial_commit_launchboard,
        transporter_quickstart,
        operator_evidence_closure,
        idp_commercial_pretest,
    )
    summary = build_summary(
        core_packet,
        execution_dashboard,
        gap_burndown,
        family_heatmap,
        family_packet_catalog,
        platform_quickstart,
        family_quicklink_board,
        partial_commit_launchboard,
        transporter_quickstart,
        operator_evidence_closure,
        idp_commercial_pretest,
        rows,
    )
    payload = {"summary": summary, "rows": rows}

    write_json(OUT_JSON, payload)
    write_csv(OUT_CSV, rows)
    write_md(OUT_MD, summary, rows)


if __name__ == "__main__":
    main()
