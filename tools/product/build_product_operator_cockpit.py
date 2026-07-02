#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CAPABILITIES_JSON = "runs/product_capability_surface_contract_current.json"
DEFAULT_GOAL_READINESS_JSON = "runs/goal_readiness_rollup_current.json"
DEFAULT_HBOND_JSON = "runs/hbond_backmap_report_current.json"
DEFAULT_GPCR_JSON = "runs/gpcr_hard_decoy_claim_unlock_audit_current.json"
DEFAULT_GPCR_PHASE3_CLOSURE_JSON = "runs/gpcr_hard_decoy_phase3_closure_gap_dossier_current.json"
DEFAULT_POCKETMD_JSON = "runs/pocketmd_lite_topk_refinement_audit_current.json"
DEFAULT_PUBLIC_BENCHMARK_JSON = "runs/public_benchmark_external_receipts_audit_current.json"
DEFAULT_PUBLIC_BENCHMARK_RECEIPT_ATTACH_PACKET_JSON = (
    "runs/public_benchmark_receipt_attach_packet_current.json"
)
DEFAULT_RELEASE_ACTIONS_JSON = "runs/goal_operator_action_board_current.json"
DEFAULT_PM_PRIORITY_QUEUE_JSON = ".betelgeuze/pm_priority_queue_status_current.json"
DEFAULT_EVIDENCE_BUNDLE_JSON = "runs/ai_md_product_evidence_bundle_current.json"
DEFAULT_API_CUSTOMER_FLOW_JSON = "runs/api_customer_flow_release_evidence_current.json"
DEFAULT_CUSTOMER_SHADOW_JSON = "runs/customer_shadow_evidence_status_current.json"
DEFAULT_DEVELOPER_PREVIEW_JSON = "runs/developer_preview_final_gate_audit_current.json"
DEFAULT_F2G_F2H_PREFLIGHT_JSON = ".betelgeuze/f2g_f2h_surface_preflight.local.json"
DEFAULT_F2G_F2H_RECOVERY_JSON = ".betelgeuze/f2g_f2h_authoritative_surface_recovery_packet.local.json"
DEFAULT_ENTERPRISE_ON_PREM_JSON = "runs/enterprise_on_prem_readiness_gate_current.json"
DEFAULT_OUT_JSON = "runs/product_operator_cockpit_current.json"
DEFAULT_OUT_CSV = "runs/product_operator_cockpit_current.csv"
DEFAULT_OUT_MD = "runs/product_operator_cockpit_current.md"
DEFAULT_OUT_HTML = "runs/product_operator_cockpit_current.html"

CLAIM_BOUNDARY = (
    "Product operator cockpit only; reads local current artifacts and renders operator-facing status. "
    "It does not run docking, run MD, mutate artifacts other than its own outputs, approve claims, "
    "upload, email, delete, commit, push, deploy, or mutate external state."
)

REQUIRED_PHASE8_PANEL_IDS = [
    "product_capabilities_dashboard",
    "goal_readiness_dashboard",
    "hbond_backmap_candidate_table",
    "gpcr_hard_decoy_blocker_panel",
    "pocketmd_lite_report_panel",
    "public_benchmark_scorecard",
    "release_blockers_operator_actions",
    "evidence_bundle_export",
    "claim_boundary_matrix",
]

CSV_FIELDS = [
    "panel_id",
    "title",
    "route",
    "artifact",
    "artifact_present",
    "status",
    "surface_ready",
    "source_artifact_ready",
    "operator_action_required",
    "claim_allowed",
    "primary_metric",
    "secondary_metric",
    "next_action",
    "allowed_claim_text",
    "disallowed_claim_text",
    "blockers",
]


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _artifact(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root).resolve()
    try:
        return str(path.relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> dict[str, Any]:
    path = _resolve(path_like, root=root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _bool_true(value: Any) -> bool:
    return value is True


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, tuple):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _first_blocked_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        if row.get("ready") is not True:
            return row
    return {}


def _first_non_pass_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        if _text(row.get("status")).lower() != "pass":
            return row
    return {}


def _metric(label: str, value: Any) -> str:
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif isinstance(value, int):
        rendered = str(value)
    elif isinstance(value, float):
        rendered = f"{value:.4g}"
    else:
        rendered = _text(value)
    return f"{label}={rendered}" if rendered else ""


def _count_metric(label: str, value: Any) -> str:
    return f"{label}={_int(value)}"


def _join_metrics(*metrics: str) -> str:
    return "; ".join(metric for metric in metrics if metric)


def _row_float_values(rows: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        number = _float(row.get(key))
        if number is not None:
            values.append(number)
    return values


def _max_float_or_zero(rows: list[dict[str, Any]], key: str) -> float:
    values = _row_float_values(rows, key)
    return max(values) if values else 0.0


def _min_float_or_zero(rows: list[dict[str, Any]], key: str) -> float:
    values = _row_float_values(rows, key)
    return min(values) if values else 0.0


def _sum_float_or_zero(rows: list[dict[str, Any]], key: str) -> float:
    values = _row_float_values(rows, key)
    return sum(values) if values else 0.0


def _status_is_blocked(status: str) -> bool:
    lowered = status.lower()
    return "blocked" in lowered or "missing" in lowered or "fail" in lowered


def _panel(
    *,
    panel_id: str,
    title: str,
    route: str,
    artifact_path: str | Path,
    artifact_present: bool,
    status: str,
    surface_ready: bool,
    source_artifact_ready: bool,
    operator_action_required: bool,
    claim_allowed: bool,
    primary_metric: str,
    secondary_metric: str,
    next_action: str,
    allowed_claim_text: str,
    disallowed_claim_text: str,
    blockers: list[str] | None = None,
    claim_boundary: str = "",
    root: Path = ROOT,
) -> dict[str, Any]:
    return {
        "panel_id": panel_id,
        "title": title,
        "route": route,
        "artifact": _artifact(artifact_path, root=root),
        "artifact_present": artifact_present,
        "status": status or "missing",
        "surface_ready": surface_ready,
        "source_artifact_ready": source_artifact_ready,
        "operator_action_required": operator_action_required,
        "claim_allowed": claim_allowed,
        "primary_metric": primary_metric,
        "secondary_metric": secondary_metric,
        "next_action": next_action,
        "allowed_claim_text": allowed_claim_text,
        "disallowed_claim_text": disallowed_claim_text,
        "blockers": blockers or [],
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": claim_boundary or CLAIM_BOUNDARY,
    }


def _build_claim_rows(
    *,
    restricted_scope_claim_guard_ready: bool,
    general_platform_claim_allowed: bool,
    gpcr_metric_ready: bool,
    gpcr_broad_claim_allowed: bool,
    pocketmd_refinement_ready: bool,
    pocketmd_claim_allowed: bool,
    public_benchmark_claim_allowed: bool,
    evidence_bundle_export_ready: bool,
    release_allowed: bool,
    customer_shadow_paid_pilot_ready: bool,
    enterprise_on_prem_ready: bool,
) -> list[dict[str, Any]]:
    rows = [
        {
            "claim_id": "operator_cockpit_surface",
            "allowed": True,
            "claim_text": "Local operator cockpit renders current artifact status and claim boundaries.",
            "boundary": "Read-only status surface; not release approval.",
        },
        {
            "claim_id": "restricted_scope_claim_guard",
            "allowed": restricted_scope_claim_guard_ready,
            "claim_text": "Restricted local capability scope is guarded by the current capability artifact.",
            "boundary": "No general protein-ligand platform wording.",
        },
        {
            "claim_id": "gpcr_hard_decoy_metric_review",
            "allowed": gpcr_metric_ready,
            "claim_text": "GPCR hard-decoy metric evidence is ready for operator review.",
            "boundary": "Broad GPCR/router/scorer promotion remains separate.",
        },
        {
            "claim_id": "pocketmd_lite_refinement_evidence",
            "allowed": pocketmd_refinement_ready,
            "claim_text": "PocketMD Lite top-k refinement metric evidence is present for review.",
            "boundary": "PocketMD Lite customer-facing claim needs report-grade evidence and approval.",
        },
        {
            "claim_id": "evidence_bundle_export",
            "allowed": evidence_bundle_export_ready,
            "claim_text": "Local evidence bundle export is available as a handoff artifact.",
            "boundary": "Export-ready is not release-ready.",
        },
        {
            "claim_id": "paid_pilot_wording",
            "allowed": release_allowed and customer_shadow_paid_pilot_ready,
            "claim_text": "Paid pilot wording is allowed.",
            "boundary": "Requires release allowance and reviewed customer-shadow evidence.",
        },
        {
            "claim_id": "general_platform_claim",
            "allowed": general_platform_claim_allowed,
            "claim_text": "General protein-ligand platform claim is allowed.",
            "boundary": "Blocked unless explicitly approved by capability and release gates.",
        },
        {
            "claim_id": "broad_gpcr_claim",
            "allowed": gpcr_broad_claim_allowed,
            "claim_text": "Broad GPCR/router/scorer claim is allowed.",
            "boundary": "Blocked until broad claim review and router promotion gates pass.",
        },
        {
            "claim_id": "pocketmd_lite_customer_claim",
            "allowed": pocketmd_claim_allowed,
            "claim_text": "PocketMD Lite customer-facing claim-grade reporting is allowed.",
            "boundary": "Blocked until claim-grade report evidence and promotion gates pass.",
        },
        {
            "claim_id": "public_benchmark_claim",
            "allowed": public_benchmark_claim_allowed,
            "claim_text": "Public benchmark claim-grade support is allowed.",
            "boundary": "Blocked until benchmark readiness and receipt ledger pass.",
        },
        {
            "claim_id": "enterprise_on_prem_platform_claim",
            "allowed": enterprise_on_prem_ready,
            "claim_text": "Enterprise/on-prem platform claim is allowed.",
            "boundary": "Blocked until OIDC/RBAC, TLS/exposure, object storage, GPU scheduler, tracing, support, and drills pass.",
        },
    ]
    return rows


def _build_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Product Operator Cockpit",
        "",
        f"- status: {summary['status']}",
        f"- phase8_surface_ready: {str(summary['phase8_surface_ready']).lower()}",
        f"- required_phase8_panel_count: {summary['required_phase8_panel_count']}",
        f"- operator_action_required_panel_count: {summary['operator_action_required_panel_count']}",
        f"- paid_pilot_wording_allowed: {str(summary['paid_pilot_wording_allowed']).lower()}",
        f"- general_platform_claim_allowed: {str(summary['general_platform_claim_allowed']).lower()}",
        f"- gpcr_broad_claim_allowed: {str(summary['gpcr_broad_claim_allowed']).lower()}",
        f"- pocketmd_lite_claim_allowed: {str(summary['pocketmd_lite_claim_allowed']).lower()}",
        "",
        "## Panels",
        "",
        "| panel | status | source ready | action | claim | artifact |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _text(row["panel_id"]),
                    _text(row["status"]),
                    str(row["source_artifact_ready"]).lower(),
                    str(row["operator_action_required"]).lower(),
                    str(row["claim_allowed"]).lower(),
                    _text(row["artifact"]),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Claim Boundary", ""])
    for claim in payload["claim_matrix"]:
        prefix = "allowed" if claim["allowed"] else "disallowed"
        lines.append(f"- {prefix}: {claim['claim_id']} - {claim['boundary']}")
    lines.append("")
    lines.append(CLAIM_BOUNDARY)
    lines.append("")
    return "\n".join(lines)


def _build_html(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    rows = payload["rows"]
    claim_rows = payload["claim_matrix"]
    panel_cards = []
    for row in rows:
        state = "ready" if row["source_artifact_ready"] else "blocked"
        action = "Action required" if row["operator_action_required"] else "No action"
        panel_cards.append(
            f"""
      <section class="panel {html.escape(state)}">
        <header>
          <p>{html.escape(row["route"])}</p>
          <h2>{html.escape(row["title"])}</h2>
          <span>{html.escape(row["status"])}</span>
        </header>
        <dl>
          <div><dt>Primary</dt><dd>{html.escape(row["primary_metric"])}</dd></div>
          <div><dt>Secondary</dt><dd>{html.escape(row["secondary_metric"])}</dd></div>
          <div><dt>Artifact</dt><dd>{html.escape(row["artifact"])}</dd></div>
          <div><dt>Action</dt><dd>{html.escape(action)}</dd></div>
        </dl>
        <p class="next">{html.escape(row["next_action"])}</p>
      </section>"""
        )

    claim_table_rows = []
    for claim in claim_rows:
        state = "Allowed" if claim["allowed"] else "Disallowed"
        claim_table_rows.append(
            "<tr>"
            f"<td>{html.escape(claim['claim_id'])}</td>"
            f"<td>{html.escape(state)}</td>"
            f"<td>{html.escape(claim['claim_text'])}</td>"
            f"<td>{html.escape(claim['boundary'])}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Product Operator Cockpit</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --ink: #18202a;
      --muted: #5f6b7a;
      --line: #cfd6df;
      --panel: #ffffff;
      --ready: #176b4d;
      --blocked: #9a3412;
      --accent: #254a7b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      font-weight: 720;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
      margin: 18px 0 20px;
    }}
    .metric {{
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
    }}
    .metric strong {{
      display: block;
      margin-top: 4px;
      font-size: 18px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
      gap: 12px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-left: 5px solid var(--accent);
      border-radius: 6px;
      padding: 14px;
      min-height: 236px;
    }}
    .panel.ready {{ border-left-color: var(--ready); }}
    .panel.blocked {{ border-left-color: var(--blocked); }}
    .panel header {{
      display: grid;
      gap: 5px;
      margin-bottom: 10px;
    }}
    .panel p {{
      margin: 0;
      color: var(--muted);
    }}
    .panel h2 {{
      margin: 0;
      font-size: 17px;
    }}
    .panel span {{
      justify-self: start;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 8px;
      color: var(--muted);
      font-size: 12px;
      max-width: 100%;
      overflow-wrap: anywhere;
    }}
    dl {{
      display: grid;
      gap: 8px;
      margin: 0;
    }}
    dt {{
      color: var(--muted);
      font-size: 12px;
    }}
    dd {{
      margin: 0;
      overflow-wrap: anywhere;
    }}
    .next {{
      margin-top: 12px;
      color: var(--ink);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 18px;
      background: #fff;
      border: 1px solid var(--line);
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 9px;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }}
    th {{
      color: var(--muted);
      font-weight: 640;
    }}
    .boundary {{
      margin-top: 16px;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <main>
    <h1>Product Operator Cockpit</h1>
    <p>{html.escape(CLAIM_BOUNDARY)}</p>
    <section class="summary" aria-label="summary">
      <div class="metric"><span>Status</span><strong>{html.escape(summary["status"])}</strong></div>
      <div class="metric"><span>Phase 8 Panels</span><strong>{summary["required_phase8_panel_count"]}</strong></div>
      <div class="metric"><span>Actions</span><strong>{summary["operator_action_required_panel_count"]}</strong></div>
      <div class="metric"><span>Paid Pilot</span><strong>{str(summary["paid_pilot_wording_allowed"]).lower()}</strong></div>
    </section>
    <section class="grid" aria-label="panels">
      {"".join(panel_cards)}
    </section>
    <table>
      <thead>
        <tr><th>Claim</th><th>Decision</th><th>Text</th><th>Boundary</th></tr>
      </thead>
      <tbody>
        {"".join(claim_table_rows)}
      </tbody>
    </table>
    <p class="boundary">Generated at {html.escape(summary["generated_at_utc"])}. execution_enabled=false; external_state_mutated=false.</p>
  </main>
</body>
</html>
"""


def _csv_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ";".join(_text(item) for item in value if _text(item))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return _text(value)


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in CSV_FIELDS})


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_product_operator_cockpit(
    *,
    capabilities_json: str | Path = DEFAULT_CAPABILITIES_JSON,
    goal_readiness_json: str | Path = DEFAULT_GOAL_READINESS_JSON,
    hbond_json: str | Path = DEFAULT_HBOND_JSON,
    gpcr_json: str | Path = DEFAULT_GPCR_JSON,
    gpcr_phase3_closure_json: str | Path = DEFAULT_GPCR_PHASE3_CLOSURE_JSON,
    pocketmd_json: str | Path = DEFAULT_POCKETMD_JSON,
    public_benchmark_json: str | Path = DEFAULT_PUBLIC_BENCHMARK_JSON,
    public_benchmark_receipt_attach_packet_json: str | Path = (
        DEFAULT_PUBLIC_BENCHMARK_RECEIPT_ATTACH_PACKET_JSON
    ),
    release_actions_json: str | Path = DEFAULT_RELEASE_ACTIONS_JSON,
    pm_priority_queue_json: str | Path = DEFAULT_PM_PRIORITY_QUEUE_JSON,
    evidence_bundle_json: str | Path = DEFAULT_EVIDENCE_BUNDLE_JSON,
    api_customer_flow_json: str | Path = DEFAULT_API_CUSTOMER_FLOW_JSON,
    customer_shadow_json: str | Path = DEFAULT_CUSTOMER_SHADOW_JSON,
    developer_preview_json: str | Path = DEFAULT_DEVELOPER_PREVIEW_JSON,
    f2g_f2h_preflight_json: str | Path = DEFAULT_F2G_F2H_PREFLIGHT_JSON,
    f2g_f2h_recovery_json: str | Path = DEFAULT_F2G_F2H_RECOVERY_JSON,
    enterprise_on_prem_json: str | Path = DEFAULT_ENTERPRISE_ON_PREM_JSON,
    root: Path = ROOT,
) -> dict[str, Any]:
    capabilities = _summary(_read_json(capabilities_json, root=root))
    goal = _summary(_read_json(goal_readiness_json, root=root))
    hbond_payload = _read_json(hbond_json, root=root)
    hbond = _summary(hbond_payload)
    gpcr = _summary(_read_json(gpcr_json, root=root))
    gpcr_phase3_closure = _summary(_read_json(gpcr_phase3_closure_json, root=root))
    pocketmd_payload = _read_json(pocketmd_json, root=root)
    pocketmd = _summary(pocketmd_payload)
    pocketmd_rows = _rows(pocketmd_payload)
    public_benchmark = _summary(_read_json(public_benchmark_json, root=root))
    public_receipt_attach_packet = _summary(
        _read_json(public_benchmark_receipt_attach_packet_json, root=root)
    )
    release_actions = _summary(_read_json(release_actions_json, root=root))
    pm_queue_payload = _read_json(pm_priority_queue_json, root=root)
    pm_queue = _summary(pm_queue_payload)
    pm_queue_rows = _rows(pm_queue_payload)
    evidence_bundle = _summary(_read_json(evidence_bundle_json, root=root))
    api_customer_flow = _summary(_read_json(api_customer_flow_json, root=root))
    customer_shadow = _summary(_read_json(customer_shadow_json, root=root))
    developer_preview = _summary(_read_json(developer_preview_json, root=root))
    f2g_preflight_payload = _read_json(f2g_f2h_preflight_json, root=root)
    f2g_preflight = _summary(f2g_preflight_payload)
    f2g_recovery_payload = _read_json(f2g_f2h_recovery_json, root=root)
    f2g_recovery = _summary(f2g_recovery_payload)
    f2g_recovery_rows = _rows(f2g_recovery_payload)
    enterprise_on_prem = _summary(_read_json(enterprise_on_prem_json, root=root))

    capabilities_present = bool(capabilities)
    restricted_scope_claim_guard_ready = _bool_true(capabilities.get("restricted_scope_claim_guard_ready"))
    general_platform_claim_allowed = _bool_true(capabilities.get("general_platform_claim_allowed"))
    capabilities_source_ready = capabilities_present and _int(capabilities.get("capability_count")) > 0

    goal_present = bool(goal)
    release_allowed = _bool_true(
        release_actions.get("goal_release_allowed")
        or release_actions.get("release_allowed")
        or goal.get("release_allowed")
    )
    goal_operator_pending_count = _int(goal.get("operator_or_external_pending_lane_count"))

    hbond_present = bool(hbond)
    hbond_status = _text(hbond.get("status") or hbond_payload.get("status"))
    hbond_candidate_count = _int(hbond.get("candidate_count") or len(_rows(hbond_payload)))
    hbond_source_ready = hbond_present and hbond_status == "hbond_backmap_report_ready"

    gpcr_present = bool(gpcr)
    gpcr_metric_ready = _bool_true(gpcr.get("hard_decoy_metric_claim_unlock_ready"))
    gpcr_broad_claim_allowed = all(
        [
            _bool_true(gpcr.get("claim_promotion_allowed")),
            _bool_true(gpcr.get("router_claim_allowed")),
            _bool_true(gpcr.get("platform_claim_allowed")),
        ]
    )
    gpcr_promotion_work_order_rows = _int(gpcr.get("promotion_work_order_row_count"))
    gpcr_promotion_work_order_lanes = _int(gpcr.get("promotion_work_order_lane_count"))
    gpcr_promotion_work_order_primary = _first_text(gpcr.get("promotion_work_order_primary_blocker"))
    gpcr_phase3_closure_present = bool(gpcr_phase3_closure)
    gpcr_phase3_closure_ready = _bool_true(gpcr_phase3_closure.get("phase3_closure_evidence_ready"))
    gpcr_phase3_exit_metric_ready = _bool_true(
        gpcr_phase3_closure.get("claim_unlock_phase3_exit_metric_conditions_ready")
    )
    gpcr_phase3_broad_promotion_locked = _bool_true(
        gpcr_phase3_closure.get("claim_unlock_broad_promotion_remains_locked")
    )
    gpcr_phase3_effective_pr_auc_ci_low = gpcr_phase3_closure.get(
        "effective_phase3_ranking_pr_auc_ci_low"
    )
    gpcr_phase3_effective_top20_hit_rate = gpcr_phase3_closure.get("effective_phase3_top20_hit_rate")
    gpcr_phase3_effective_decoys_above_positive = gpcr_phase3_closure.get(
        "effective_phase3_decoys_above_positive_total"
    )
    gpcr_phase3_effective_metric_source = _first_text(
        gpcr_phase3_closure.get("effective_phase3_metric_source")
    )
    gpcr_phase3_promotion_blocker_count = len(
        _string_list(gpcr_phase3_closure.get("claim_unlock_promotion_blockers"))
    )
    gpcr_primary_pr_auc_ci_low = (
        gpcr_phase3_effective_pr_auc_ci_low
        if gpcr_phase3_effective_pr_auc_ci_low is not None
        else gpcr.get("preregistered_ranking_pr_auc_ci_low")
    )
    gpcr_primary_top20_hit_rate = (
        gpcr_phase3_effective_top20_hit_rate
        if gpcr_phase3_effective_top20_hit_rate is not None
        else gpcr.get("preregistered_top20_hit_rate")
    )

    pocketmd_present = bool(pocketmd)
    pocketmd_refinement_ready = _bool_true(pocketmd.get("claim_grade_refinement_evidence_ready"))
    pocketmd_fill_preview_ready = _bool_true(pocketmd.get("claim_grade_fill_preview_evidence_ready"))
    pocketmd_report_ready = _bool_true(pocketmd.get("claim_grade_report_evidence_ready"))
    pocketmd_promotion_allowed = _bool_true(pocketmd.get("claim_promotion_allowed"))
    pocketmd_lite_claim_allowed = (
        pocketmd_refinement_ready
        and pocketmd_report_ready
        and pocketmd_promotion_allowed
    )
    pocketmd_claim_grade_rows = [
        row for row in pocketmd_rows if row.get("claim_grade_metric_ready") is True
    ]
    pocketmd_claim_grade_metric_ready_row_count = (
        len(pocketmd_claim_grade_rows)
        if pocketmd_rows
        else _int(pocketmd.get("claim_grade_metric_ready_count"))
    )
    pocketmd_local_min_ligand_rmsd_a_max = _max_float_or_zero(
        pocketmd_claim_grade_rows,
        "local_min_ligand_rmsd_a",
    )
    pocketmd_hbond_persistence_min = _min_float_or_zero(
        pocketmd_claim_grade_rows,
        "hbond_persistence",
    )
    pocketmd_contact_persistence_min = _min_float_or_zero(
        pocketmd_claim_grade_rows,
        "contact_persistence",
    )
    pocketmd_initial_clash_count_total = _sum_float_or_zero(
        pocketmd_claim_grade_rows,
        "initial_clash_count",
    )
    pocketmd_final_clash_count_total = _sum_float_or_zero(
        pocketmd_claim_grade_rows,
        "clash_count",
    )
    pocketmd_clash_relief_count_total = _sum_float_or_zero(
        pocketmd_claim_grade_rows,
        "clash_relief_count",
    )
    pocketmd_green_band_condition_text = _first_text(
        pocketmd.get("green_band_condition_text"),
        pocketmd.get("green_band_condition"),
    )

    public_present = bool(public_benchmark)
    public_external_receipts_ready = _bool_true(public_benchmark.get("external_benchmark_receipts_ready"))
    public_acceptance_ready = public_external_receipts_ready or _bool_true(
        public_benchmark.get("top_acceptance_artifact_claim_ready")
    )
    public_benchmark_claim_allowed = (
        public_acceptance_ready and _bool_true(public_benchmark.get("claim_promotion_allowed"))
    )
    public_receipt_blocked_rows = _first_text(
        public_benchmark.get("receipt_blocked_row_count"),
        public_benchmark.get(
            "public_benchmark_statistical_support_metric_source_payload_operator_receipt_blocked_row_count"
        ),
    )
    public_blockers = _string_list(public_benchmark.get("blockers"))
    if not public_blockers:
        public_blockers = _string_list(public_benchmark.get("top_acceptance_artifact_missing_true_fields"))
    if not public_blockers:
        public_blockers = _string_list(public_benchmark.get("primary_blocker_id"))
    public_attach_present = bool(public_receipt_attach_packet)
    public_attach_ready = _bool_true(public_receipt_attach_packet.get("receipt_attach_packet_ready"))
    public_attach_blockers = _string_list(public_receipt_attach_packet.get("blockers"))
    if public_attach_blockers:
        public_blockers = public_attach_blockers
    public_vina_pending_scores = _int(
        public_receipt_attach_packet.get("vina_gnina_score_value_pending_count")
    )
    public_vina_pending_fields = _int(public_benchmark.get("vina_gnina_pending_field_count"))
    public_metric_pending_fields = _int(
        public_receipt_attach_packet.get("metric_source_receipt_manual_field_pending_count")
    )
    public_metric_pending_tokens = _int(
        public_receipt_attach_packet.get("metric_source_receipt_approval_token_pending_count")
    )
    public_field_work_order_rows = _int(public_receipt_attach_packet.get("field_work_order_row_count"))
    public_field_work_order_pending_fields = _int(
        public_receipt_attach_packet.get("field_work_order_pending_field_count")
    )
    public_field_work_order_primary_field = _first_text(
        public_receipt_attach_packet.get("field_work_order_primary_field_name")
    )
    public_field_work_order_primary_lane = _first_text(
        public_receipt_attach_packet.get("field_work_order_primary_lane_id")
    )
    public_field_work_order_primary_pending_rows = _int(
        public_receipt_attach_packet.get("field_work_order_primary_pending_row_count")
    )
    public_field_work_order_primary_required_value = _first_text(
        public_receipt_attach_packet.get("field_work_order_primary_required_value")
    )
    public_field_work_order_primary_required_action = _first_text(
        public_receipt_attach_packet.get("field_work_order_primary_required_action")
    )
    public_field_work_order_primary_approval_token = _first_text(
        public_receipt_attach_packet.get("field_work_order_primary_approval_token_required")
    )
    public_field_work_order_primary_operator_csv = _first_text(
        public_receipt_attach_packet.get("field_work_order_primary_operator_csv")
    )
    public_field_work_order_primary_source_artifact = _first_text(
        public_receipt_attach_packet.get("field_work_order_primary_source_artifact")
    )
    public_primary_blocker_id = _first_text(
        public_receipt_attach_packet.get("primary_blocker_id"),
        public_benchmark.get("primary_blocker_id"),
    )
    public_primary_blocker = _first_text(
        public_receipt_attach_packet.get("primary_blocker"),
        public_benchmark.get("primary_blocker"),
    )
    public_primary_next_required_step = _first_text(
        public_receipt_attach_packet.get("next_required_step"),
        public_benchmark.get("primary_blocker_next_required_step"),
        public_benchmark.get("next_required_step"),
    )
    public_vina_score_template_csv = _first_text(
        public_receipt_attach_packet.get("vina_gnina_score_template_csv"),
        public_benchmark.get("vina_gnina_score_template_csv"),
    )
    public_vina_score_template_receipt_json = _first_text(
        public_receipt_attach_packet.get("vina_gnina_score_template_receipt_json"),
        public_benchmark.get("vina_gnina_score_template_receipt_json"),
    )
    public_metric_source_receipt_csv = _first_text(
        public_receipt_attach_packet.get("metric_source_receipt_csv"),
        public_benchmark.get("metric_source_receipt_csv"),
    )
    public_vina_adapter_command_after_fill = _first_text(
        public_benchmark.get("vina_gnina_adapter_command_after_fill"),
        public_receipt_attach_packet.get("vina_gnina_adapter_command_after_fill"),
    )

    release_actions_present = bool(release_actions)
    release_blocker_count = _int(
        release_actions.get("goal_release_blocker_count") or release_actions.get("blocker_count")
    )
    pm_queue_present = bool(pm_queue)
    pm_queue_blocked_count = _int(pm_queue.get("blocked_item_count"))
    pm_queue_ready_count = _int(pm_queue.get("ready_item_count"))
    pm_queue_first_blocked_item_id = _first_text(pm_queue.get("first_blocked_item_id"))
    pm_queue_first_blocked_row = _first_blocked_row(pm_queue_rows)
    pm_queue_first_blocker = _first_text(pm_queue_first_blocked_row.get("blocker"))
    pm_queue_first_action = _first_text(
        pm_queue_first_blocked_row.get("next_action"),
        pm_queue.get("next_required_step"),
    )
    pm_queue_blocked = pm_queue_present and pm_queue_blocked_count > 0
    release_panel_claim_allowed = release_allowed and not pm_queue_blocked

    evidence_bundle_present = bool(evidence_bundle)
    evidence_bundle_export_ready = (
        _bool_true(evidence_bundle.get("bundle_export_ready"))
        and _bool_true(evidence_bundle.get("bundle_tar_exists"))
        and _bool_true(evidence_bundle.get("bundle_validation_pass"))
    )
    api_customer_flow_present = bool(api_customer_flow)
    api_customer_flow_ready = (
        _text(api_customer_flow.get("status")) == "api_customer_flow_release_evidence_ready"
        and _bool_true(api_customer_flow.get("formal_release_evidence_ready"))
        and _bool_true(api_customer_flow.get("clean_install_flow_ready"))
        and _bool_true(api_customer_flow.get("restricted_unattended_runtime_ready"))
        and _bool_true(api_customer_flow.get("result_manifest_signature_verified"))
        and _bool_true(api_customer_flow.get("bundle_validation_ready"))
        and _int(api_customer_flow.get("blocker_count")) == 0
    )

    customer_shadow_paid_pilot_ready = _bool_true(customer_shadow.get("paid_pilot_evidence_ready"))
    customer_shadow_real_row_count = _int(customer_shadow.get("real_customer_shadow_row_count"))
    customer_shadow_completed_case_count = _int(customer_shadow.get("completed_customer_shadow_case_count"))
    customer_shadow_required_case_count = _int(customer_shadow.get("required_completed_customer_shadow_case_count"))
    customer_shadow_missing_case_count = _int(customer_shadow.get("missing_completed_customer_shadow_case_count"))
    customer_shadow_retained_raw_data_count = _int(customer_shadow.get("customer_retained_raw_data_count"))
    customer_shadow_redistribution_false_count = _int(customer_shadow.get("redistribution_allowed_false_count"))
    customer_shadow_anonymized_summary_count = _int(customer_shadow.get("anonymized_result_summary_count"))
    customer_shadow_reviewer_signoff_count = _int(customer_shadow.get("reviewer_signoff_count"))
    customer_shadow_blocker_count = _int(customer_shadow.get("blocker_count"))
    customer_shadow_work_order_ready = _bool_true(customer_shadow.get("customer_shadow_work_order_ready"))
    customer_shadow_work_order_rows = _int(customer_shadow.get("customer_shadow_work_order_row_count"))
    customer_shadow_work_order_primary_slot = _first_text(
        customer_shadow.get("customer_shadow_work_order_primary_case_slot_id")
    )
    customer_shadow_work_order_primary_required_action = _first_text(
        customer_shadow.get("customer_shadow_work_order_primary_required_action")
    )
    customer_shadow_work_order_primary_operator_csv = _first_text(
        customer_shadow.get("customer_shadow_work_order_primary_operator_csv")
    )
    customer_shadow_work_order_primary_required_row_kind = _first_text(
        customer_shadow.get("customer_shadow_work_order_primary_required_row_kind")
    )
    customer_shadow_work_order_primary_required_raw_data_custody = _first_text(
        customer_shadow.get("customer_shadow_work_order_primary_required_raw_data_custody")
    )
    customer_shadow_work_order_primary_required_customer_retained_raw_data = _bool_true(
        customer_shadow.get("customer_shadow_work_order_primary_required_customer_retained_raw_data")
    )
    customer_shadow_work_order_primary_required_redistribution_allowed = _bool_true(
        customer_shadow.get("customer_shadow_work_order_primary_required_redistribution_allowed")
    )
    customer_shadow_work_order_primary_required_raw_data_stored_in_repo = _bool_true(
        customer_shadow.get("customer_shadow_work_order_primary_required_raw_data_stored_in_repo")
    )
    customer_shadow_work_order_primary_required_derived_metadata_fields = _string_list(
        customer_shadow.get("customer_shadow_work_order_primary_required_derived_metadata_fields")
    )
    customer_shadow_work_order_primary_required_reviewer_signoff_status = _first_text(
        customer_shadow.get("customer_shadow_work_order_primary_required_reviewer_signoff_status")
    )
    customer_shadow_work_order_primary_required_source_artifact_fingerprint = _first_text(
        customer_shadow.get("customer_shadow_work_order_primary_required_source_artifact_fingerprint")
    )
    customer_shadow_intake_schema_ready = _bool_true(
        customer_shadow.get("customer_shadow_intake_schema_ready")
    )
    customer_shadow_minimum_met = _bool_true(customer_shadow.get("customer_shadow_minimum_met"))
    customer_shadow_raw_data_stored_in_repo = _bool_true(
        customer_shadow.get("customer_raw_data_stored_in_repo")
    )
    customer_shadow_invalid_row_count = _int(customer_shadow.get("invalid_row_count"))
    customer_shadow_mock_fixture_row_count = _int(customer_shadow.get("mock_fixture_row_count"))
    customer_shadow_required_column_count = _int(customer_shadow.get("required_column_count"))
    customer_shadow_redistribution_required_value = _bool_true(
        customer_shadow.get("redistribution_allowed_required_value")
    )
    paid_pilot_wording_allowed = release_allowed and customer_shadow_paid_pilot_ready

    developer_preview_present = bool(developer_preview)
    developer_preview_clean_baseline_ready = _bool_true(
        developer_preview.get("developer_preview_clean_baseline_ready")
    )
    developer_preview_gate_count = _int(developer_preview.get("gate_count"))
    developer_preview_ready_gate_count = _int(developer_preview.get("ready_gate_count"))
    developer_preview_blocked_gate_count = _int(developer_preview.get("blocked_gate_count"))
    developer_preview_receipt_work_order_rows = _int(
        developer_preview.get("receipt_work_order_row_count")
    )
    developer_preview_primary_blocker_id = _first_text(
        developer_preview.get("primary_blocker_id"),
        developer_preview.get("primary_blocker"),
    )
    developer_preview_primary_receipt_artifact = _first_text(
        developer_preview.get("receipt_work_order_primary_receipt_artifact")
    )
    developer_preview_receipt_work_order_primary_gate = _first_text(
        developer_preview.get("receipt_work_order_primary_gate_id")
    )
    developer_preview_primary_required_receipt_status = _first_text(
        developer_preview.get("receipt_work_order_primary_required_receipt_status")
    )
    developer_preview_primary_required_true_fields = _string_list(
        developer_preview.get("receipt_work_order_primary_required_true_fields")
    )
    developer_preview_primary_required_zero_fields = _string_list(
        developer_preview.get("receipt_work_order_primary_required_zero_fields")
    )
    developer_preview_receipt_blocker_count = _int(developer_preview.get("receipt_blocker_count"))
    f2g_preflight_present = bool(f2g_preflight)
    f2g_recovery_present = bool(f2g_recovery)
    f2g_first_recovery_row = _first_non_pass_row(f2g_recovery_rows)
    f2g_preflight_status = _text(f2g_preflight.get("status"))
    f2g_recovery_status = _text(f2g_recovery.get("status"))
    f2g_recovery_required = _bool_true(f2g_recovery.get("recovery_required"))
    f2g_preflight_blocker_count = _int(f2g_preflight.get("blocker_count"))
    f2g_blocked_recovery_item_count = _int(f2g_recovery.get("blocked_recovery_item_count"))
    f2g_recovery_item_count = _int(f2g_recovery.get("recovery_item_count"))
    f2g_primary_recovery_item = _first_text(f2g_first_recovery_row.get("recovery_item_id"))
    f2g_primary_required_surface = _first_text(f2g_first_recovery_row.get("required_surface"))
    f2g_primary_blocker = _first_text(f2g_first_recovery_row.get("blocker"))
    f2g_primary_operator_action = _first_text(
        f2g_first_recovery_row.get("operator_action"),
        f2g_recovery.get("next_required_step"),
        f2g_preflight.get("next_required_step"),
    )
    f2g_audit_ready = _bool_true(f2g_preflight.get("f2g_audit_ready"))
    f2h_continuation_allowed = _bool_true(f2g_preflight.get("f2h_continuation_allowed"))
    f2g_placeholder_creation_allowed = _bool_true(
        f2g_recovery.get("placeholder_surface_creation_allowed")
    )
    f2g_surface_restore_executed = _bool_true(f2g_recovery.get("surface_restore_executed"))
    enterprise_present = bool(enterprise_on_prem)
    enterprise_ready = _bool_true(enterprise_on_prem.get("enterprise_on_prem_ready"))
    enterprise_control_count = _int(enterprise_on_prem.get("control_count"))
    enterprise_ready_control_count = _int(enterprise_on_prem.get("ready_control_count"))
    enterprise_blocked_control_count = _int(enterprise_on_prem.get("blocked_control_count"))
    enterprise_primary_blocker_id = _first_text(enterprise_on_prem.get("primary_blocker_id"))
    enterprise_primary_blocker = _first_text(enterprise_on_prem.get("primary_blocker"))
    enterprise_next_required_step = _first_text(enterprise_on_prem.get("next_required_step"))
    enterprise_oidc_rbac_ready = _bool_true(enterprise_on_prem.get("oidc_rbac_ready"))
    enterprise_object_storage_ready = _bool_true(enterprise_on_prem.get("object_storage_ready"))
    enterprise_gpu_scheduler_ready = _bool_true(enterprise_on_prem.get("gpu_scheduler_ready"))
    enterprise_audit_provenance_ready = _bool_true(
        enterprise_on_prem.get("audit_provenance_metrics_tracing_ready")
    )
    enterprise_license_control_ready = _bool_true(enterprise_on_prem.get("license_control_ready"))
    enterprise_support_bundle_ready = _bool_true(
        enterprise_on_prem.get("support_bundle_recovery_drill_ready")
    )
    enterprise_rollback_retry_ready = _bool_true(
        enterprise_on_prem.get("rollback_retry_idempotency_ready")
    )

    claim_rows = _build_claim_rows(
        restricted_scope_claim_guard_ready=restricted_scope_claim_guard_ready,
        general_platform_claim_allowed=general_platform_claim_allowed,
        gpcr_metric_ready=gpcr_metric_ready,
        gpcr_broad_claim_allowed=gpcr_broad_claim_allowed,
        pocketmd_refinement_ready=pocketmd_refinement_ready,
        pocketmd_claim_allowed=pocketmd_lite_claim_allowed,
        public_benchmark_claim_allowed=public_benchmark_claim_allowed,
        evidence_bundle_export_ready=evidence_bundle_export_ready,
        release_allowed=release_allowed,
        customer_shadow_paid_pilot_ready=customer_shadow_paid_pilot_ready,
        enterprise_on_prem_ready=enterprise_ready,
    )
    allowed_claim_text = "; ".join(row["claim_id"] for row in claim_rows if row["allowed"])
    disallowed_claim_text = "; ".join(row["claim_id"] for row in claim_rows if not row["allowed"])

    panels = [
        _panel(
            panel_id="product_capabilities_dashboard",
            title="/product/capabilities dashboard",
            route="/product/capabilities",
            artifact_path=capabilities_json,
            artifact_present=capabilities_present,
            status=_text(capabilities.get("status") or "missing_product_capability_surface_contract"),
            surface_ready=True,
            source_artifact_ready=capabilities_source_ready,
            operator_action_required=not capabilities_source_ready,
            claim_allowed=restricted_scope_claim_guard_ready and not general_platform_claim_allowed,
            primary_metric=_join_metrics(
                _metric("ready_capabilities", _int(capabilities.get("ready_capability_count"))),
                _metric("capability_count", _int(capabilities.get("capability_count"))),
            ),
            secondary_metric=_join_metrics(
                _metric("evidence_surfaces", _int(capabilities.get("evidence_surface_count"))),
                _metric("general_platform_claim_allowed", general_platform_claim_allowed),
            ),
            next_action=_first_text(
                capabilities.get("next_required_step"),
                "Keep general platform wording locked until capability and release gates approve it.",
            ),
            allowed_claim_text="Restricted local capability surface may be shown when scoped by family.",
            disallowed_claim_text="General protein-ligand platform wording remains disallowed.",
            blockers=_string_list(capabilities.get("blocked_claim_scopes")),
            claim_boundary=_text(capabilities.get("claim_boundary")) or CLAIM_BOUNDARY,
            root=root,
        ),
        _panel(
            panel_id="goal_readiness_dashboard",
            title="/goal/readiness dashboard",
            route="/goal/readiness",
            artifact_path=goal_readiness_json,
            artifact_present=goal_present,
            status=_text(goal.get("status") or "missing_goal_readiness_rollup"),
            surface_ready=True,
            source_artifact_ready=goal_present,
            operator_action_required=not _bool_true(goal.get("goal_completion_audit_goal_complete")),
            claim_allowed=release_allowed,
            primary_metric=_join_metrics(
                _metric("blocked_lanes", _int(goal.get("blocked_lane_count"))),
                _metric("pending_lanes", goal_operator_pending_count),
            ),
            secondary_metric=_join_metrics(
                _metric("goal_complete", _bool_true(goal.get("goal_completion_audit_goal_complete"))),
                _metric("release_lane_ready", _bool_true(goal.get("release_complete_lane_ready"))),
            ),
            next_action=_first_text(
                goal.get("next_required_step"),
                "Close blocked and operator-pending lanes before release wording.",
            ),
            allowed_claim_text="Goal readiness can be displayed as an operator status dashboard.",
            disallowed_claim_text="Release-complete wording is disallowed until goal completion is true.",
            blockers=[] if goal_present else ["missing_goal_readiness_rollup"],
            claim_boundary=_text(goal.get("claim_boundary")) or CLAIM_BOUNDARY,
            root=root,
        ),
        _panel(
            panel_id="hbond_backmap_candidate_table",
            title="H-Bond BackMap candidate table",
            route="/product/hbond-backmap-report",
            artifact_path=hbond_json,
            artifact_present=hbond_present,
            status=hbond_status or "missing_hbond_backmap_report",
            surface_ready=True,
            source_artifact_ready=hbond_source_ready,
            operator_action_required=not hbond_source_ready,
            claim_allowed=False,
            primary_metric=_join_metrics(
                _metric("candidate_count", hbond_candidate_count),
                _metric("claim_safe_count", _int(hbond.get("claim_safe_count"))),
            ),
            secondary_metric=_join_metrics(
                _metric("donor_sites", _int(hbond.get("total_donor_sites"))),
                _metric("acceptor_sites", _int(hbond.get("total_acceptor_sites"))),
            ),
            next_action=_first_text(
                hbond.get("next_required_step"),
                "Build runs/hbond_backmap_report_current.json from backmapping scores before using the table.",
            ),
            allowed_claim_text="Local interpretability candidates can be inspected when the report exists.",
            disallowed_claim_text="Docking accuracy, affinity, and scientific-result claims are disallowed.",
            blockers=[] if hbond_source_ready else ["hbond_backmap_report_missing_or_blocked"],
            claim_boundary=_text(hbond.get("claim_boundary")) or CLAIM_BOUNDARY,
            root=root,
        ),
        _panel(
            panel_id="gpcr_hard_decoy_blocker_panel",
            title="GPCR hard-decoy blocker panel",
            route="/product/gpcr-hard-decoy-suite-report",
            artifact_path=gpcr_json,
            artifact_present=gpcr_present,
            status=_text(gpcr.get("status") or "missing_gpcr_hard_decoy_claim_unlock_audit"),
            surface_ready=True,
            source_artifact_ready=gpcr_present and gpcr_metric_ready,
            operator_action_required=not gpcr_broad_claim_allowed,
            claim_allowed=gpcr_broad_claim_allowed,
            primary_metric=_join_metrics(
                _metric("pr_auc_ci_low", gpcr_primary_pr_auc_ci_low),
                _metric("top20_hit_rate", gpcr_primary_top20_hit_rate),
            ),
            secondary_metric=_join_metrics(
                _metric(
                    "decoys_above_positive",
                    gpcr_phase3_effective_decoys_above_positive
                    if gpcr_phase3_effective_decoys_above_positive is not None
                    else gpcr.get("preregistered_decoys_above_positive_count"),
                ),
                _metric("phase3_closure_ready", gpcr_phase3_closure_ready),
                _metric("phase3_exit_metric_ready", gpcr_phase3_exit_metric_ready),
                _metric("phase3_metric_source", gpcr_phase3_effective_metric_source),
                _metric("broad_promotion_locked", gpcr_phase3_broad_promotion_locked),
                _metric(
                    "promotion_blockers",
                    gpcr_phase3_promotion_blocker_count or _int(gpcr.get("promotion_blocker_count")),
                ),
                _count_metric("promotion_work_order_rows", gpcr_promotion_work_order_rows),
                _count_metric("promotion_work_order_lanes", gpcr_promotion_work_order_lanes),
                _metric("promotion_work_order_primary", gpcr_promotion_work_order_primary),
            ),
            next_action=_first_text(
                gpcr_phase3_closure.get("next_required_step"),
                gpcr.get("next_required_step"),
                "Complete broad-claim review and scorer/router promotion gates.",
            ),
            allowed_claim_text="Hard-decoy metric evidence may be reviewed.",
            disallowed_claim_text="Broad GPCR/router/scorer claim remains locked.",
            blockers=_string_list(gpcr.get("promotion_blockers")),
            claim_boundary=_text(gpcr.get("claim_boundary")) or CLAIM_BOUNDARY,
            root=root,
        ),
        _panel(
            panel_id="pocketmd_lite_report_panel",
            title="PocketMD Lite report panel",
            route="/product/pocketmd-lite-topk-refinement-audit",
            artifact_path=pocketmd_json,
            artifact_present=pocketmd_present,
            status=_text(pocketmd.get("status") or "missing_pocketmd_lite_topk_refinement_audit"),
            surface_ready=True,
            source_artifact_ready=pocketmd_present and pocketmd_refinement_ready,
            operator_action_required=not pocketmd_lite_claim_allowed,
            claim_allowed=pocketmd_lite_claim_allowed,
            primary_metric=_join_metrics(
                _count_metric("green", pocketmd.get("green_row_count")),
                _count_metric("yellow", pocketmd.get("yellow_row_count")),
                _count_metric("red", pocketmd.get("red_row_count")),
                _count_metric("abstain", pocketmd.get("abstain_row_count")),
                _metric("metric_ready", _int(pocketmd.get("claim_grade_metric_ready_count"))),
                _metric("candidate_count", _int(pocketmd.get("candidate_count"))),
            ),
            secondary_metric=_join_metrics(
                _metric("refinement_ready", pocketmd_refinement_ready),
                _metric("report_ready", pocketmd_report_ready),
                _metric("preview_ready", pocketmd_fill_preview_ready),
                _metric("local_min_rmsd_max", pocketmd_local_min_ligand_rmsd_a_max),
                _metric("hbond_persistence_min", pocketmd_hbond_persistence_min),
                _metric("contact_persistence_min", pocketmd_contact_persistence_min),
                _metric("initial_clashes", pocketmd_initial_clash_count_total),
                _metric("final_clashes", pocketmd_final_clash_count_total),
                _metric("clash_relief", pocketmd_clash_relief_count_total),
                _metric("promotion_allowed", pocketmd_promotion_allowed),
            ),
            next_action=_first_text(
                pocketmd.get("next_required_step"),
                "Finish claim-grade report evidence before PocketMD Lite customer-facing wording.",
            ),
            allowed_claim_text="Top-k refinement metric evidence may be reviewed.",
            disallowed_claim_text="PocketMD Lite claim-grade customer wording remains disallowed.",
            blockers=[]
            if pocketmd_lite_claim_allowed
            else [
                "pocketmd_lite_claim_promotion_missing"
                if pocketmd_refinement_ready and pocketmd_report_ready
                else "pocketmd_lite_preview_not_canonical_report"
                if pocketmd_refinement_ready and pocketmd_fill_preview_ready and not pocketmd_report_ready
                else "pocketmd_lite_claim_grade_report_or_promotion_missing"
            ],
            claim_boundary=_text(pocketmd.get("claim_boundary")) or CLAIM_BOUNDARY,
            root=root,
        ),
        _panel(
            panel_id="public_benchmark_scorecard",
            title="Public benchmark scorecard",
            route="/product/public-benchmark-external-receipts-audit",
            artifact_path=public_benchmark_json,
            artifact_present=public_present,
            status=_text(public_benchmark.get("status") or "missing_public_benchmark_external_receipts_audit"),
            surface_ready=True,
            source_artifact_ready=public_present,
            operator_action_required=not public_benchmark_claim_allowed,
            claim_allowed=public_benchmark_claim_allowed,
            primary_metric=_join_metrics(
                _metric("ready_steps", public_benchmark.get("ready_step_count")),
                _metric("step_count", public_benchmark.get("step_count")),
                _metric("blocked_steps", public_benchmark.get("blocked_step_count")),
                _metric("blocked_receipt_rows", public_receipt_blocked_rows),
                _metric("acceptance_ready", public_acceptance_ready),
            ),
            secondary_metric=_join_metrics(
                _metric(
                    "vina_gnina_score_evidence",
                    _bool_true(public_benchmark.get("vina_gnina_comparison_adapter_score_evidence_ready")),
                ),
                _metric("attach_packet_ready", public_attach_ready),
                _metric("pending_scores", public_vina_pending_scores),
                _metric("pending_score_fields", public_vina_pending_fields),
                _metric("pending_receipt_fields", public_metric_pending_fields),
                _metric("pending_receipt_tokens", public_metric_pending_tokens),
                _count_metric("field_work_order_rows", public_field_work_order_rows),
                _count_metric("field_work_order_pending_fields", public_field_work_order_pending_fields),
                _metric("field_work_order_primary", public_field_work_order_primary_field),
                _metric("field_work_order_lane", public_field_work_order_primary_lane),
                _count_metric("field_work_order_primary_rows", public_field_work_order_primary_pending_rows),
                _metric("field_work_order_required_value", public_field_work_order_primary_required_value),
                _metric("primary_blocker_id", public_primary_blocker_id),
                _metric("primary_blocker", public_primary_blocker),
                _metric("score_template", public_vina_score_template_csv),
                _metric("score_receipt", public_vina_score_template_receipt_json),
                _metric("metric_receipt", public_metric_source_receipt_csv),
                _metric("adapter_after_fill", public_vina_adapter_command_after_fill),
                _metric(
                    "same_input_rows",
                    _bool_true(public_benchmark.get("comparison_adapter_same_input_row_count_match")),
                ),
                _metric("top_artifact_status", public_benchmark.get("top_acceptance_artifact_status")),
                _metric("claim_promotion_allowed", _bool_true(public_benchmark.get("claim_promotion_allowed"))),
            ),
            next_action=_first_text(
                public_field_work_order_primary_required_action,
                public_primary_next_required_step,
                public_benchmark.get("top_required_input"),
                "Attach benchmark receipts and clear Vina/GNINA same-input comparison evidence.",
            ),
            allowed_claim_text="Benchmark receipt status may be displayed.",
            disallowed_claim_text="Public benchmark performance claims remain disallowed.",
            blockers=public_blockers,
            claim_boundary=_text(public_benchmark.get("claim_boundary")) or CLAIM_BOUNDARY,
            root=root,
        ),
        _panel(
            panel_id="developer_preview_final_gates",
            title="Developer Preview final gates",
            route="/goal/developer-preview",
            artifact_path=developer_preview_json,
            artifact_present=developer_preview_present,
            status=_text(developer_preview.get("status") or "missing_developer_preview_final_gate_audit"),
            surface_ready=True,
            source_artifact_ready=developer_preview_present,
            operator_action_required=not developer_preview_clean_baseline_ready,
            claim_allowed=developer_preview_clean_baseline_ready,
            primary_metric=_join_metrics(
                _metric("ready_gates", f"{developer_preview_ready_gate_count}/{developer_preview_gate_count}"),
                _metric("blocked_gates", developer_preview_blocked_gate_count),
                _metric("clean_baseline", developer_preview_clean_baseline_ready),
            ),
            secondary_metric=_join_metrics(
                _count_metric("receipt_work_order_rows", developer_preview_receipt_work_order_rows),
                _count_metric("receipt_blockers", developer_preview_receipt_blocker_count),
                _metric("primary_gate", developer_preview_receipt_work_order_primary_gate),
                _metric("primary_blocker", developer_preview_primary_blocker_id),
                _metric("primary_receipt", developer_preview_primary_receipt_artifact),
                _metric("primary_expected_status", developer_preview_primary_required_receipt_status),
                _count_metric(
                    "primary_required_true_fields",
                    len(developer_preview_primary_required_true_fields),
                ),
                _count_metric(
                    "primary_required_zero_fields",
                    len(developer_preview_primary_required_zero_fields),
                ),
            ),
            next_action=_first_text(
                developer_preview.get("next_required_step"),
                "Attach reviewed clean-checkout, platform, and new-user receipts before Developer Preview wording.",
            ),
            allowed_claim_text="Developer Preview gate status can be displayed for operator review.",
            disallowed_claim_text="Developer demo-ready wording is disallowed until all final gates pass.",
            blockers=_string_list(developer_preview.get("blockers")),
            claim_boundary=_text(developer_preview.get("claim_boundary")) or CLAIM_BOUNDARY,
            root=root,
        ),
        _panel(
            panel_id="f2g_f2h_preflight_work_order",
            title="F2g/F2h preflight / work order",
            route="/goal/priority-queue#f2g-f2h",
            artifact_path=f2g_f2h_recovery_json,
            artifact_present=f2g_recovery_present,
            status=f2g_preflight_status or f2g_recovery_status or "missing_f2g_f2h_surface_preflight",
            surface_ready=True,
            source_artifact_ready=f2g_preflight_present and f2g_recovery_present,
            operator_action_required=f2g_recovery_required or not f2h_continuation_allowed,
            claim_allowed=False,
            primary_metric=_join_metrics(
                _count_metric("preflight_blockers", f2g_preflight_blocker_count),
                _count_metric("blocked_recovery_items", f2g_blocked_recovery_item_count),
                _count_metric("recovery_items", f2g_recovery_item_count),
                _metric("f2g_audit_ready", f2g_audit_ready),
                _metric("f2h_allowed", f2h_continuation_allowed),
            ),
            secondary_metric=_join_metrics(
                _metric("recovery_required", f2g_recovery_required),
                _metric("primary_recovery_item", f2g_primary_recovery_item),
                _metric("primary_required_surface", f2g_primary_required_surface),
                _metric("primary_blocker", f2g_primary_blocker),
                _metric("placeholder_allowed", f2g_placeholder_creation_allowed),
                _metric("surface_restore_executed", f2g_surface_restore_executed),
            ),
            next_action=_first_text(
                f2g_primary_operator_action,
                "Restore the authoritative F2/G1 surfaces, then rerun the local F2g/F2h preflight.",
            ),
            allowed_claim_text="F2g/F2h recovery work order can be shown as non-promoting operator guidance.",
            disallowed_claim_text="F2g audit, F2h continuation, G1 promotion, and solver claims remain disallowed.",
            blockers=_string_list(f2g_preflight.get("blockers")) or _string_list(
                f2g_recovery.get("preflight_blockers")
            ),
            claim_boundary=_text(f2g_recovery.get("claim_boundary"))
            or _text(f2g_preflight.get("claim_boundary"))
            or CLAIM_BOUNDARY,
            root=root,
        ),
        _panel(
            panel_id="enterprise_on_prem_readiness_panel",
            title="Enterprise/on-prem readiness",
            route="/goal/enterprise-on-prem",
            artifact_path=enterprise_on_prem_json,
            artifact_present=enterprise_present,
            status=_text(
                enterprise_on_prem.get("status")
                or "missing_enterprise_on_prem_readiness_gate"
            ),
            surface_ready=True,
            source_artifact_ready=enterprise_present,
            operator_action_required=not enterprise_ready,
            claim_allowed=False,
            primary_metric=_join_metrics(
                _metric("ready_controls", f"{enterprise_ready_control_count}/{enterprise_control_count}"),
                _metric("blocked_controls", enterprise_blocked_control_count),
                _metric("enterprise_ready", enterprise_ready),
            ),
            secondary_metric=_join_metrics(
                _metric("primary_blocker_id", enterprise_primary_blocker_id),
                _metric("oidc_rbac_ready", enterprise_oidc_rbac_ready),
                _metric("object_storage_ready", enterprise_object_storage_ready),
                _metric("gpu_scheduler_ready", enterprise_gpu_scheduler_ready),
                _metric("audit_provenance_tracing_ready", enterprise_audit_provenance_ready),
                _metric("license_control_ready", enterprise_license_control_ready),
                _metric("support_bundle_ready", enterprise_support_bundle_ready),
                _metric("rollback_retry_ready", enterprise_rollback_retry_ready),
            ),
            next_action=_first_text(
                enterprise_next_required_step,
                "Build enterprise/on-prem readiness evidence and keep platform claims blocked.",
            ),
            allowed_claim_text="Enterprise/on-prem readiness blockers can be displayed for operator planning.",
            disallowed_claim_text="Enterprise/on-prem platform wording remains disallowed until all controls pass.",
            blockers=[]
            if enterprise_ready
            else [enterprise_primary_blocker or "enterprise_on_prem_readiness_blocked"],
            claim_boundary=_text(enterprise_on_prem.get("claim_boundary")) or CLAIM_BOUNDARY,
            root=root,
        ),
        _panel(
            panel_id="release_blockers_operator_actions",
            title="Release blockers / operator actions",
            route="/goal/actions",
            artifact_path=pm_priority_queue_json if pm_queue_present else release_actions_json,
            artifact_present=release_actions_present or pm_queue_present,
            status=(
                "pm_priority_queue_blocked"
                if pm_queue_blocked
                else _text(release_actions.get("status") or "missing_goal_operator_action_board")
            ),
            surface_ready=True,
            source_artifact_ready=release_actions_present or pm_queue_present,
            operator_action_required=(not release_allowed) or pm_queue_blocked,
            claim_allowed=release_panel_claim_allowed,
            primary_metric=_join_metrics(
                _metric("release_allowed", release_allowed),
                _metric("release_blockers", release_blocker_count),
                _metric("pm_queue_status", pm_queue.get("status")),
                _count_metric("pm_queue_blocked_items", pm_queue_blocked_count),
            ),
            secondary_metric=_join_metrics(
                _metric("primary_action", release_actions.get("primary_action_id")),
                _metric("decision_gate", release_actions.get("goal_release_decision_gate_status")),
                _metric("pm_first_blocked_item", pm_queue_first_blocked_item_id),
                _metric("pm_first_blocker", pm_queue_first_blocker),
            ),
            next_action=_first_text(
                pm_queue_first_action if pm_queue_blocked else "",
                release_actions.get("primary_action_recommended_action"),
                release_actions.get("next_required_step"),
                "Resolve the primary operator action before release promotion.",
            ),
            allowed_claim_text="Operator actions can be displayed as release blockers.",
            disallowed_claim_text="Release or paid-pilot wording remains disallowed while release_allowed=false.",
            blockers=(
                [pm_queue_first_blocker or "pm_priority_queue_blocked"]
                if pm_queue_blocked
                else ([] if release_allowed else ["goal_release_allowed_false"])
            ),
            claim_boundary=_text(release_actions.get("claim_boundary")) or CLAIM_BOUNDARY,
            root=root,
        ),
        _panel(
            panel_id="evidence_bundle_export",
            title="Evidence bundle export",
            route="/product/evidence-bundle-export",
            artifact_path=evidence_bundle_json,
            artifact_present=evidence_bundle_present,
            status=_text(evidence_bundle.get("status") or "missing_ai_md_product_evidence_bundle"),
            surface_ready=True,
            source_artifact_ready=evidence_bundle_export_ready,
            operator_action_required=not _bool_true(evidence_bundle.get("release_claim_ready")),
            claim_allowed=evidence_bundle_export_ready,
            primary_metric=_join_metrics(
                _metric("bundle_export_ready", evidence_bundle_export_ready),
                _metric("members", _int(evidence_bundle.get("bundle_tar_member_count"))),
            ),
            secondary_metric=_join_metrics(
                _metric("validation_pass", _bool_true(evidence_bundle.get("bundle_validation_pass"))),
                _metric("release_claim_ready", _bool_true(evidence_bundle.get("release_claim_ready"))),
                _metric("api_customer_flow_ready", api_customer_flow_ready),
                _metric("tier_alpha", api_customer_flow.get("tier_alpha_smoke_status")),
                _metric(
                    "signed_manifest",
                    _bool_true(api_customer_flow.get("result_manifest_signature_verified")),
                ),
                _metric(
                    "restricted_runtime",
                    _bool_true(api_customer_flow.get("restricted_unattended_runtime_ready")),
                ),
                _metric(
                    "api_bundle_validation",
                    _bool_true(api_customer_flow.get("bundle_validation_ready")),
                ),
            ),
            next_action=_first_text(
                evidence_bundle.get("next_required_step"),
                "Use the local evidence bundle for handoff, not release promotion.",
            ),
            allowed_claim_text="Local evidence bundle export is available when validation passes.",
            disallowed_claim_text="Release-ready or runtime-green claims remain disallowed.",
            blockers=[] if evidence_bundle_export_ready else ["evidence_bundle_export_not_ready"],
            claim_boundary=_text(evidence_bundle.get("claim_boundary")) or CLAIM_BOUNDARY,
            root=root,
        ),
        _panel(
            panel_id="customer_shadow_evidence_panel",
            title="Customer shadow evidence panel",
            route="/goal/customer-shadow",
            artifact_path=customer_shadow_json,
            artifact_present=bool(customer_shadow),
            status=_text(customer_shadow.get("status") or "missing_customer_shadow_evidence_status"),
            surface_ready=True,
            source_artifact_ready=bool(customer_shadow) and customer_shadow_intake_schema_ready,
            operator_action_required=not customer_shadow_paid_pilot_ready,
            claim_allowed=False,
            primary_metric=_join_metrics(
                _count_metric("completed_cases", customer_shadow_completed_case_count),
                _count_metric("required_cases", customer_shadow_required_case_count),
                _count_metric("missing_cases", customer_shadow_missing_case_count),
                _metric("minimum_met", customer_shadow_minimum_met),
            ),
            secondary_metric=_join_metrics(
                _metric("schema_ready", customer_shadow_intake_schema_ready),
                _count_metric("real_rows", customer_shadow_real_row_count),
                _count_metric("mock_rows", customer_shadow_mock_fixture_row_count),
                _count_metric("invalid_rows", customer_shadow_invalid_row_count),
                _count_metric("retained_raw_data", customer_shadow_retained_raw_data_count),
                _metric("raw_data_in_repo", customer_shadow_raw_data_stored_in_repo),
                _count_metric("redistribution_false", customer_shadow_redistribution_false_count),
                _metric("redistribution_required", customer_shadow_redistribution_required_value),
                _count_metric("anonymized_summaries", customer_shadow_anonymized_summary_count),
                _count_metric("reviewer_signoffs", customer_shadow_reviewer_signoff_count),
                _count_metric("required_columns", customer_shadow_required_column_count),
                _count_metric("work_order_rows", customer_shadow_work_order_rows),
                _metric("work_order_primary", customer_shadow_work_order_primary_slot),
                _metric("required_raw_custody", customer_shadow_work_order_primary_required_raw_data_custody),
                _metric(
                    "required_retained_raw_data",
                    customer_shadow_work_order_primary_required_customer_retained_raw_data,
                ),
                _metric(
                    "required_raw_data_in_repo",
                    customer_shadow_work_order_primary_required_raw_data_stored_in_repo,
                ),
                _count_metric(
                    "required_derived_metadata_fields",
                    len(customer_shadow_work_order_primary_required_derived_metadata_fields),
                ),
                _metric("required_signoff", customer_shadow_work_order_primary_required_reviewer_signoff_status),
            ),
            next_action=_first_text(
                customer_shadow.get("next_required_step"),
                customer_shadow_work_order_primary_required_action,
                "Collect three reviewed customer-shadow metadata rows without storing customer raw data in the repo.",
            ),
            allowed_claim_text="Customer-shadow intake status can be displayed as privacy-preserving operator evidence.",
            disallowed_claim_text="Paid-pilot wording remains disallowed until three reviewed customer-shadow rows pass.",
            blockers=[]
            if customer_shadow_paid_pilot_ready
            else [customer_shadow_work_order_primary_required_action or "customer_shadow_evidence_incomplete"],
            claim_boundary=_text(customer_shadow.get("claim_boundary")) or CLAIM_BOUNDARY,
            root=root,
        ),
        _panel(
            panel_id="claim_boundary_matrix",
            title="Allowed/disallowed claim text",
            route="/product/operator-cockpit#claim-boundary",
            artifact_path=customer_shadow_json,
            artifact_present=bool(customer_shadow),
            status="claim_boundary_matrix_ready",
            surface_ready=True,
            source_artifact_ready=True,
            operator_action_required=not paid_pilot_wording_allowed,
            claim_allowed=False,
            primary_metric=_join_metrics(
                _metric("allowed_claims", sum(1 for row in claim_rows if row["allowed"])),
                _metric("disallowed_claims", sum(1 for row in claim_rows if not row["allowed"])),
                _count_metric("customer_rows", customer_shadow_completed_case_count),
                _count_metric("required_customer_rows", customer_shadow_required_case_count),
            ),
            secondary_metric=_join_metrics(
                _metric("customer_shadow_ready", customer_shadow_paid_pilot_ready),
                _count_metric("real_rows", customer_shadow_real_row_count),
                _count_metric("missing_customer_rows", customer_shadow_missing_case_count),
                _count_metric("retained_raw_data", customer_shadow_retained_raw_data_count),
                _count_metric("redistribution_false", customer_shadow_redistribution_false_count),
                _count_metric("anonymized_summaries", customer_shadow_anonymized_summary_count),
                _count_metric("reviewer_signoffs", customer_shadow_reviewer_signoff_count),
                _count_metric("customer_shadow_blockers", customer_shadow_blocker_count),
                _metric("customer_shadow_work_order_ready", customer_shadow_work_order_ready),
                _count_metric("customer_shadow_work_order_rows", customer_shadow_work_order_rows),
                _metric("customer_shadow_work_order_primary", customer_shadow_work_order_primary_slot),
                _metric(
                    "customer_shadow_work_order_action",
                    customer_shadow_work_order_primary_required_action,
                ),
                _metric("paid_pilot_wording_allowed", paid_pilot_wording_allowed),
            ),
            next_action=(
                "Keep paid-pilot, broad-platform, broad-GPCR, PocketMD claim-grade, and public-benchmark "
                "wording locked until their evidence gates pass."
            ),
            allowed_claim_text=allowed_claim_text,
            disallowed_claim_text=disallowed_claim_text,
            blockers=[] if paid_pilot_wording_allowed else ["paid_pilot_claim_boundary_locked"],
            claim_boundary=CLAIM_BOUNDARY,
            root=root,
        ),
    ]

    missing_required_panel_ids = [
        panel_id for panel_id in REQUIRED_PHASE8_PANEL_IDS if panel_id not in {row["panel_id"] for row in panels}
    ]
    action_panels = [row for row in panels if row["operator_action_required"]]
    source_blocked_panels = [
        row for row in panels if not row["source_artifact_ready"] or _status_is_blocked(_text(row["status"]))
    ]
    phase8_surface_ready = not missing_required_panel_ids and all(row["surface_ready"] for row in panels)
    status = (
        "product_operator_cockpit_ready_claims_blocked"
        if phase8_surface_ready
        else "blocked_product_operator_cockpit"
    )
    if phase8_surface_ready and not action_panels:
        status = "product_operator_cockpit_ready"

    summary = {
        "packet_type": "product_operator_cockpit",
        "schema_version": "product_operator_cockpit_v1",
        "status": status,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "phase8_surface_ready": phase8_surface_ready,
        "required_phase8_panel_count": len(REQUIRED_PHASE8_PANEL_IDS),
        "required_phase8_panel_ids": REQUIRED_PHASE8_PANEL_IDS,
        "observed_phase8_panel_count": len(panels),
        "missing_required_phase8_panel_count": len(missing_required_panel_ids),
        "missing_required_phase8_panel_ids": missing_required_panel_ids,
        "surface_ready_panel_count": sum(1 for row in panels if row["surface_ready"]),
        "source_artifact_ready_panel_count": sum(1 for row in panels if row["source_artifact_ready"]),
        "source_artifact_blocked_panel_count": len(source_blocked_panels),
        "source_artifact_blocked_panel_ids": [row["panel_id"] for row in source_blocked_panels],
        "operator_action_required_panel_count": len(action_panels),
        "operator_action_required_panel_ids": [row["panel_id"] for row in action_panels],
        "allowed_claim_count": sum(1 for row in claim_rows if row["allowed"]),
        "disallowed_claim_count": sum(1 for row in claim_rows if not row["allowed"]),
        "paid_pilot_wording_allowed": paid_pilot_wording_allowed,
        "general_platform_claim_allowed": general_platform_claim_allowed,
        "gpcr_hard_decoy_metric_ready": gpcr_metric_ready,
        "gpcr_broad_claim_allowed": gpcr_broad_claim_allowed,
        "gpcr_phase3_closure_present": gpcr_phase3_closure_present,
        "gpcr_phase3_closure_evidence_ready": gpcr_phase3_closure_ready,
        "gpcr_phase3_exit_metric_conditions_ready": gpcr_phase3_exit_metric_ready,
        "gpcr_phase3_broad_promotion_locked": gpcr_phase3_broad_promotion_locked,
        "gpcr_phase3_effective_ranking_pr_auc_ci_low": gpcr_phase3_effective_pr_auc_ci_low,
        "gpcr_phase3_effective_top20_hit_rate": gpcr_phase3_effective_top20_hit_rate,
        "gpcr_phase3_effective_decoys_above_positive_total": (
            gpcr_phase3_effective_decoys_above_positive
        ),
        "gpcr_phase3_effective_metric_source": gpcr_phase3_effective_metric_source,
        "gpcr_phase3_promotion_blocker_count": gpcr_phase3_promotion_blocker_count,
        "gpcr_promotion_work_order_row_count": gpcr_promotion_work_order_rows,
        "gpcr_promotion_work_order_lane_count": gpcr_promotion_work_order_lanes,
        "gpcr_promotion_work_order_primary_blocker": gpcr_promotion_work_order_primary,
        "pocketmd_lite_refinement_evidence_ready": pocketmd_refinement_ready,
        "pocketmd_lite_report_evidence_ready": pocketmd_report_ready,
        "pocketmd_lite_fill_preview_evidence_ready": pocketmd_fill_preview_ready,
        "pocketmd_lite_preview_requires_canonical_review": (
            pocketmd_fill_preview_ready and not pocketmd_report_ready
        ),
        "pocketmd_lite_claim_grade_metric_ready_row_count": (
            pocketmd_claim_grade_metric_ready_row_count
        ),
        "pocketmd_lite_local_min_ligand_rmsd_a_max": pocketmd_local_min_ligand_rmsd_a_max,
        "pocketmd_lite_hbond_persistence_min": pocketmd_hbond_persistence_min,
        "pocketmd_lite_contact_persistence_min": pocketmd_contact_persistence_min,
        "pocketmd_lite_initial_clash_count_total": pocketmd_initial_clash_count_total,
        "pocketmd_lite_final_clash_count_total": pocketmd_final_clash_count_total,
        "pocketmd_lite_clash_relief_count_total": pocketmd_clash_relief_count_total,
        "pocketmd_lite_green_band_condition_text": pocketmd_green_band_condition_text,
        "pocketmd_lite_claim_allowed": pocketmd_lite_claim_allowed,
        "public_benchmark_claim_allowed": public_benchmark_claim_allowed,
        "public_benchmark_receipt_attach_packet_ready": public_attach_ready,
        "public_benchmark_receipt_attach_packet_present": public_attach_present,
        "public_benchmark_vina_gnina_pending_score_count": public_vina_pending_scores,
        "public_benchmark_vina_gnina_pending_field_count": public_vina_pending_fields,
        "public_benchmark_metric_source_pending_field_count": public_metric_pending_fields,
        "public_benchmark_metric_source_pending_approval_token_count": public_metric_pending_tokens,
        "public_benchmark_field_work_order_row_count": public_field_work_order_rows,
        "public_benchmark_field_work_order_pending_field_count": public_field_work_order_pending_fields,
        "public_benchmark_field_work_order_primary_field_name": public_field_work_order_primary_field,
        "public_benchmark_field_work_order_primary_lane_id": public_field_work_order_primary_lane,
        "public_benchmark_field_work_order_primary_pending_row_count": (
            public_field_work_order_primary_pending_rows
        ),
        "public_benchmark_field_work_order_primary_required_value": (
            public_field_work_order_primary_required_value
        ),
        "public_benchmark_field_work_order_primary_required_action": (
            public_field_work_order_primary_required_action
        ),
        "public_benchmark_field_work_order_primary_approval_token_required": (
            public_field_work_order_primary_approval_token
        ),
        "public_benchmark_field_work_order_primary_operator_csv": (
            public_field_work_order_primary_operator_csv
        ),
        "public_benchmark_field_work_order_primary_source_artifact": (
            public_field_work_order_primary_source_artifact
        ),
        "public_benchmark_primary_blocker_id": public_primary_blocker_id,
        "public_benchmark_primary_blocker": public_primary_blocker,
        "public_benchmark_primary_next_required_step": public_primary_next_required_step,
        "public_benchmark_vina_gnina_score_template_csv": public_vina_score_template_csv,
        "public_benchmark_vina_gnina_score_template_receipt_json": (
            public_vina_score_template_receipt_json
        ),
        "public_benchmark_metric_source_receipt_csv": public_metric_source_receipt_csv,
        "public_benchmark_vina_gnina_adapter_command_after_fill": (
            public_vina_adapter_command_after_fill
        ),
        "evidence_bundle_export_ready": evidence_bundle_export_ready,
        "api_customer_flow_release_evidence_present": api_customer_flow_present,
        "api_customer_flow_release_evidence_ready": api_customer_flow_ready,
        "api_customer_flow_release_evidence_status": _text(api_customer_flow.get("status")),
        "api_customer_flow_release_evidence_pass_count": _int(api_customer_flow.get("pass_count")),
        "api_customer_flow_release_evidence_blocker_count": _int(api_customer_flow.get("blocker_count")),
        "api_customer_flow_tier_alpha_smoke_status": _text(api_customer_flow.get("tier_alpha_smoke_status")),
        "api_customer_flow_tier_alpha_runner_execution_ok": _bool_true(
            api_customer_flow.get("tier_alpha_runner_execution_ok")
        ),
        "api_customer_flow_result_manifest_signature_verified": _bool_true(
            api_customer_flow.get("result_manifest_signature_verified")
        ),
        "api_customer_flow_restricted_runtime_ready": _bool_true(
            api_customer_flow.get("restricted_unattended_runtime_ready")
        ),
        "api_customer_flow_bundle_validation_ready": _bool_true(
            api_customer_flow.get("bundle_validation_ready")
        ),
        "customer_shadow_paid_pilot_evidence_ready": customer_shadow_paid_pilot_ready,
        "customer_shadow_real_row_count": customer_shadow_real_row_count,
        "customer_shadow_completed_case_count": customer_shadow_completed_case_count,
        "customer_shadow_required_case_count": customer_shadow_required_case_count,
        "customer_shadow_missing_case_count": customer_shadow_missing_case_count,
        "customer_shadow_customer_retained_raw_data_count": customer_shadow_retained_raw_data_count,
        "customer_shadow_redistribution_allowed_false_count": customer_shadow_redistribution_false_count,
        "customer_shadow_anonymized_result_summary_count": customer_shadow_anonymized_summary_count,
        "customer_shadow_reviewer_signoff_count": customer_shadow_reviewer_signoff_count,
        "customer_shadow_evidence_blocker_count": customer_shadow_blocker_count,
        "customer_shadow_work_order_ready": customer_shadow_work_order_ready,
        "customer_shadow_work_order_row_count": customer_shadow_work_order_rows,
        "customer_shadow_work_order_primary_case_slot_id": customer_shadow_work_order_primary_slot,
        "customer_shadow_work_order_primary_required_action": (
            customer_shadow_work_order_primary_required_action
        ),
        "customer_shadow_work_order_primary_operator_csv": (
            customer_shadow_work_order_primary_operator_csv
        ),
        "customer_shadow_work_order_primary_required_row_kind": (
            customer_shadow_work_order_primary_required_row_kind
        ),
        "customer_shadow_work_order_primary_required_raw_data_custody": (
            customer_shadow_work_order_primary_required_raw_data_custody
        ),
        "customer_shadow_work_order_primary_required_customer_retained_raw_data": (
            customer_shadow_work_order_primary_required_customer_retained_raw_data
        ),
        "customer_shadow_work_order_primary_required_redistribution_allowed": (
            customer_shadow_work_order_primary_required_redistribution_allowed
        ),
        "customer_shadow_work_order_primary_required_raw_data_stored_in_repo": (
            customer_shadow_work_order_primary_required_raw_data_stored_in_repo
        ),
        "customer_shadow_work_order_primary_required_derived_metadata_fields": (
            customer_shadow_work_order_primary_required_derived_metadata_fields
        ),
        "customer_shadow_work_order_primary_required_reviewer_signoff_status": (
            customer_shadow_work_order_primary_required_reviewer_signoff_status
        ),
        "customer_shadow_work_order_primary_required_source_artifact_fingerprint": (
            customer_shadow_work_order_primary_required_source_artifact_fingerprint
        ),
        "customer_shadow_intake_schema_ready": customer_shadow_intake_schema_ready,
        "customer_shadow_minimum_met": customer_shadow_minimum_met,
        "customer_shadow_raw_data_stored_in_repo": customer_shadow_raw_data_stored_in_repo,
        "customer_shadow_invalid_row_count": customer_shadow_invalid_row_count,
        "customer_shadow_mock_fixture_row_count": customer_shadow_mock_fixture_row_count,
        "customer_shadow_required_column_count": customer_shadow_required_column_count,
        "customer_shadow_redistribution_allowed_required_value": (
            customer_shadow_redistribution_required_value
        ),
        "developer_preview_clean_baseline_ready": developer_preview_clean_baseline_ready,
        "developer_preview_gate_count": developer_preview_gate_count,
        "developer_preview_ready_gate_count": developer_preview_ready_gate_count,
        "developer_preview_blocked_gate_count": developer_preview_blocked_gate_count,
        "developer_preview_receipt_work_order_row_count": developer_preview_receipt_work_order_rows,
        "developer_preview_receipt_blocker_count": developer_preview_receipt_blocker_count,
        "developer_preview_primary_blocker_id": developer_preview_primary_blocker_id,
        "developer_preview_receipt_work_order_primary_gate_id": (
            developer_preview_receipt_work_order_primary_gate
        ),
        "developer_preview_receipt_work_order_primary_receipt_artifact": (
            developer_preview_primary_receipt_artifact
        ),
        "developer_preview_receipt_work_order_primary_required_receipt_status": (
            developer_preview_primary_required_receipt_status
        ),
        "developer_preview_receipt_work_order_primary_required_true_fields": (
            developer_preview_primary_required_true_fields
        ),
        "developer_preview_receipt_work_order_primary_required_zero_fields": (
            developer_preview_primary_required_zero_fields
        ),
        "enterprise_on_prem_readiness_present": enterprise_present,
        "enterprise_on_prem_ready": enterprise_ready,
        "enterprise_on_prem_claim_allowed": False,
        "enterprise_on_prem_control_count": enterprise_control_count,
        "enterprise_on_prem_ready_control_count": enterprise_ready_control_count,
        "enterprise_on_prem_blocked_control_count": enterprise_blocked_control_count,
        "enterprise_on_prem_primary_blocker_id": enterprise_primary_blocker_id,
        "enterprise_on_prem_primary_blocker": enterprise_primary_blocker,
        "enterprise_on_prem_next_required_step": enterprise_next_required_step,
        "enterprise_on_prem_oidc_rbac_ready": enterprise_oidc_rbac_ready,
        "enterprise_on_prem_object_storage_ready": enterprise_object_storage_ready,
        "enterprise_on_prem_gpu_scheduler_ready": enterprise_gpu_scheduler_ready,
        "enterprise_on_prem_audit_provenance_metrics_tracing_ready": (
            enterprise_audit_provenance_ready
        ),
        "enterprise_on_prem_license_control_ready": enterprise_license_control_ready,
        "enterprise_on_prem_support_bundle_recovery_drill_ready": enterprise_support_bundle_ready,
        "enterprise_on_prem_rollback_retry_idempotency_ready": enterprise_rollback_retry_ready,
        "f2g_f2h_preflight_present": f2g_preflight_present,
        "f2g_f2h_recovery_packet_present": f2g_recovery_present,
        "f2g_f2h_preflight_status": f2g_preflight_status,
        "f2g_f2h_recovery_status": f2g_recovery_status,
        "f2g_f2h_recovery_required": f2g_recovery_required,
        "f2g_f2h_preflight_blocker_count": f2g_preflight_blocker_count,
        "f2g_f2h_blocked_recovery_item_count": f2g_blocked_recovery_item_count,
        "f2g_f2h_recovery_item_count": f2g_recovery_item_count,
        "f2g_f2h_primary_recovery_item_id": f2g_primary_recovery_item,
        "f2g_f2h_primary_required_surface": f2g_primary_required_surface,
        "f2g_f2h_primary_blocker": f2g_primary_blocker,
        "f2g_f2h_primary_operator_action": f2g_primary_operator_action,
        "f2g_f2h_audit_ready": f2g_audit_ready,
        "f2h_continuation_allowed": f2h_continuation_allowed,
        "f2g_f2h_placeholder_surface_creation_allowed": f2g_placeholder_creation_allowed,
        "f2g_f2h_surface_restore_executed": f2g_surface_restore_executed,
        "pm_priority_queue_present": pm_queue_present,
        "pm_priority_queue_status": _text(pm_queue.get("status")),
        "pm_priority_queue_ready_item_count": pm_queue_ready_count,
        "pm_priority_queue_blocked_item_count": pm_queue_blocked_count,
        "pm_priority_queue_first_blocked_item_id": pm_queue_first_blocked_item_id,
        "pm_priority_queue_first_blocker": pm_queue_first_blocker,
        "pm_priority_queue_next_required_step": pm_queue_first_action,
        "release_allowed": release_allowed,
        "next_required_step": (
            pm_queue_first_action
            if pm_queue_blocked
            else (action_panels[0]["next_action"] if action_panels else "")
        ),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": panels, "claim_matrix": claim_rows}


def write_product_operator_cockpit_outputs(
    payload: dict[str, Any],
    *,
    out_json: str | Path = DEFAULT_OUT_JSON,
    out_csv: str | Path = DEFAULT_OUT_CSV,
    out_md: str | Path = DEFAULT_OUT_MD,
    out_html: str | Path = DEFAULT_OUT_HTML,
    root: Path = ROOT,
) -> None:
    _write_json(out_json, payload, root=root)
    _write_csv(out_csv, payload["rows"], root=root)
    _write_text(out_md, _build_markdown(payload), root=root)
    _write_text(out_html, _build_html(payload), root=root)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the product operator cockpit current artifacts.")
    parser.add_argument("--capabilities-json", default=DEFAULT_CAPABILITIES_JSON)
    parser.add_argument("--goal-readiness-json", default=DEFAULT_GOAL_READINESS_JSON)
    parser.add_argument("--hbond-json", default=DEFAULT_HBOND_JSON)
    parser.add_argument("--gpcr-json", default=DEFAULT_GPCR_JSON)
    parser.add_argument("--gpcr-phase3-closure-json", default=DEFAULT_GPCR_PHASE3_CLOSURE_JSON)
    parser.add_argument("--pocketmd-json", default=DEFAULT_POCKETMD_JSON)
    parser.add_argument("--public-benchmark-json", default=DEFAULT_PUBLIC_BENCHMARK_JSON)
    parser.add_argument(
        "--public-benchmark-receipt-attach-packet-json",
        default=DEFAULT_PUBLIC_BENCHMARK_RECEIPT_ATTACH_PACKET_JSON,
    )
    parser.add_argument("--release-actions-json", default=DEFAULT_RELEASE_ACTIONS_JSON)
    parser.add_argument("--pm-priority-queue-json", default=DEFAULT_PM_PRIORITY_QUEUE_JSON)
    parser.add_argument("--evidence-bundle-json", default=DEFAULT_EVIDENCE_BUNDLE_JSON)
    parser.add_argument("--api-customer-flow-json", default=DEFAULT_API_CUSTOMER_FLOW_JSON)
    parser.add_argument("--customer-shadow-json", default=DEFAULT_CUSTOMER_SHADOW_JSON)
    parser.add_argument("--developer-preview-json", default=DEFAULT_DEVELOPER_PREVIEW_JSON)
    parser.add_argument("--f2g-f2h-preflight-json", default=DEFAULT_F2G_F2H_PREFLIGHT_JSON)
    parser.add_argument("--f2g-f2h-recovery-json", default=DEFAULT_F2G_F2H_RECOVERY_JSON)
    parser.add_argument("--enterprise-on-prem-json", default=DEFAULT_ENTERPRISE_ON_PREM_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-html", default=DEFAULT_OUT_HTML)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = build_product_operator_cockpit(
        capabilities_json=args.capabilities_json,
        goal_readiness_json=args.goal_readiness_json,
        hbond_json=args.hbond_json,
        gpcr_json=args.gpcr_json,
        gpcr_phase3_closure_json=args.gpcr_phase3_closure_json,
        pocketmd_json=args.pocketmd_json,
        public_benchmark_json=args.public_benchmark_json,
        public_benchmark_receipt_attach_packet_json=args.public_benchmark_receipt_attach_packet_json,
        release_actions_json=args.release_actions_json,
        pm_priority_queue_json=args.pm_priority_queue_json,
        evidence_bundle_json=args.evidence_bundle_json,
        api_customer_flow_json=args.api_customer_flow_json,
        customer_shadow_json=args.customer_shadow_json,
        developer_preview_json=args.developer_preview_json,
        f2g_f2h_preflight_json=args.f2g_f2h_preflight_json,
        f2g_f2h_recovery_json=args.f2g_f2h_recovery_json,
        enterprise_on_prem_json=args.enterprise_on_prem_json,
    )
    write_product_operator_cockpit_outputs(
        payload,
        out_json=args.out_json,
        out_csv=args.out_csv,
        out_md=args.out_md,
        out_html=args.out_html,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
