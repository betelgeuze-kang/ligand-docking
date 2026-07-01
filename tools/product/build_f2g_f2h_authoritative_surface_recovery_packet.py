#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PREFLIGHT_JSON = ".betelgeuze/f2g_f2h_surface_preflight.local.json"
DEFAULT_OUT_JSON = ".betelgeuze/f2g_f2h_authoritative_surface_recovery_packet.local.json"
DEFAULT_OUT_CSV = ".betelgeuze/f2g_f2h_authoritative_surface_recovery_packet.local.csv"
DEFAULT_OUT_MD = ".betelgeuze/f2g_f2h_authoritative_surface_recovery_packet.local.md"

PROHIBITED_ACTIONS = (
    "do_not_create_placeholder_json;do_not_pin_dofs;do_not_run_continuation;"
    "do_not_regenerate_0_656_evidence;do_not_promote_g1;do_not_write_protected_runs;"
    "do_not_mutate_external_state"
)

CLAIM_BOUNDARY = (
    "F2g/F2h authoritative surface recovery packet only; it translates the local surface preflight into an "
    "operator work order for restoring the real-MGT, real_per_element tangent, near-null mode, support/elastic-link, "
    "and F2g/F2h prerequisite surfaces from their authoritative implementation branch or protected archive. It does "
    "not create substitute surfaces, run Newton/continuation, pin DOFs, regenerate 0.656 evidence, promote G1, write "
    "protected runs artifacts, upload, submit, delete, commit, push, or mutate external state."
)


SURFACE_REQUIREMENTS: list[dict[str, str]] = [
    {
        "check_id": "implementation_phase1_dir",
        "recovery_item_id": "restore_implementation_phase1_tree",
        "required_surface": "implementation/phase1",
        "authoritative_source_hint": "Original F2/G1 implementation branch or protected source archive that owns the real-MGT diagnostic implementation tree.",
        "acceptance_rule": "Directory exists in the checkout and is the reviewed implementation tree, not a generated placeholder.",
        "operator_action": "Restore or merge the reviewed F2/G1 implementation tree, then rerun the surface preflight.",
    },
    {
        "check_id": "productization_release_evidence_dir",
        "recovery_item_id": "restore_productization_release_evidence_dir",
        "required_surface": "implementation/phase1/release_evidence/productization",
        "authoritative_source_hint": "F2/G1 productization evidence archive or branch that produced the non-promoting G1 diagnostic receipts.",
        "acceptance_rule": "Productization evidence directory exists and remains local/non-promoting until reviewed.",
        "operator_action": "Restore the productization evidence directory from the F2/G1 owner branch/archive, then rerun the surface preflight.",
    },
    {
        "check_id": "real_mgt_input_surface",
        "recovery_item_id": "restore_real_mgt_input_surface",
        "required_surface": "real-MGT model/input packet",
        "authoritative_source_hint": "Reviewed real-MGT model/input packet from the F2/G1 diagnostic implementation source.",
        "acceptance_rule": "A current real-MGT input/model candidate is present under the implementation tree with reviewable provenance.",
        "operator_action": "Restore the reviewed real-MGT model/input packet before mapping near-null DOFs.",
    },
    {
        "check_id": "real_per_element_assembled_tangent_surface",
        "recovery_item_id": "restore_real_per_element_assembled_tangent_surface",
        "required_surface": "real_per_element assembled tangent packet",
        "authoritative_source_hint": "Reviewed real_per_element service tangent output used by the original F2 diagnostic merges.",
        "acceptance_rule": "The assembled tangent candidate is present and matches the real_per_element service contract.",
        "operator_action": "Expose the reviewed real_per_element assembled tangent packet, then rerun the surface preflight.",
    },
    {
        "check_id": "near_null_mode_packet",
        "recovery_item_id": "restore_near_null_mode_packet",
        "required_surface": "near-null or marginally negative mode packet",
        "authoritative_source_hint": "PR #61/F2 diagnostic near-null mode packet or protected equivalent from the original solver diagnostic run.",
        "acceptance_rule": "Near-null packet is present with dominant DOFs that can be mapped to support/free-space context.",
        "operator_action": "Restore the reviewed near-null mode packet so dominant DOFs can be reconciled.",
    },
    {
        "check_id": "support_elastic_link_context",
        "recovery_item_id": "restore_support_elastic_link_context",
        "required_surface": "support membership and elastic-link endpoint/stiffness context",
        "authoritative_source_hint": "Reviewed support/free DOF and elastic-link context from the F2/G1 diagnostic implementation source.",
        "acceptance_rule": "Support membership, constrained/free DOFs, elastic-link endpoints, and stiffness context are present.",
        "operator_action": "Restore support membership, constrained/free DOFs, and elastic-link endpoint/stiffness context.",
    },
    {
        "check_id": "f2g_support_elastic_audit",
        "recovery_item_id": "run_f2g_support_elastic_audit_after_surface_restore",
        "required_surface": "implementation/phase1/release_evidence/productization/g1_support_elastic_link_reconciliation_audit.local.json",
        "authoritative_source_hint": "New local non-promoting audit produced only after the required F2/G1 surfaces are restored.",
        "acceptance_rule": "Audit exists and includes near-null DOFs, support/free state, elastic-link mapping, stiffness stats, and ranked findings.",
        "operator_action": "Run the non-promoting F2g support/elastic-link reconciliation audit after all prerequisite surfaces are present.",
    },
    {
        "check_id": "f2h_continuation_prerequisites",
        "recovery_item_id": "prepare_f2h_continuation_only_after_f2g",
        "required_surface": "F2g audit plus continuation/Newton/load-step candidate",
        "authoritative_source_hint": "Reviewed lightweight continuation driver/input from the F2/G1 implementation source; usable only after F2g audit exists.",
        "acceptance_rule": "F2g audit exists and continuation/Newton prerequisite candidate is present; no G1 promotion is implied.",
        "operator_action": "Keep F2h blocked until the F2g audit exists and continuation code/input surfaces are restored.",
    },
]


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload


def _preflight_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    return {str(row.get("check_id") or ""): dict(row) for row in rows if isinstance(row, dict)}


def _recovery_row(requirement: dict[str, str], preflight_row: dict[str, Any] | None) -> dict[str, Any]:
    status = str((preflight_row or {}).get("status") or "fail")
    present = status == "pass"
    observed = str((preflight_row or {}).get("observed") or "preflight_row_missing")
    blocker = str((preflight_row or {}).get("blocker") or "")
    return {
        "recovery_item_id": requirement["recovery_item_id"],
        "preflight_check_id": requirement["check_id"],
        "status": "pass" if present else "fail",
        "observed": observed,
        "required_surface": requirement["required_surface"],
        "authoritative_source_hint": requirement["authoritative_source_hint"],
        "acceptance_rule": requirement["acceptance_rule"],
        "blocker": "" if present else blocker or f"{requirement['check_id']}_not_ready",
        "operator_action": requirement["operator_action"],
        "prohibited_actions": PROHIBITED_ACTIONS,
        "execution_enabled": False,
        "surface_restore_executed": False,
        "audit_executed": False,
        "continuation_executed": False,
        "claim_promotion_allowed": False,
        "external_state_mutated": False,
    }


def build_f2g_f2h_authoritative_surface_recovery_packet(
    *,
    root: Path = ROOT,
    preflight_json: str | Path = DEFAULT_PREFLIGHT_JSON,
) -> dict[str, Any]:
    root = Path(root)
    preflight_payload, preflight_present = _read_json(preflight_json, root=root)
    preflight_summary = _summary(preflight_payload)
    rows_by_check = _preflight_rows(preflight_payload)

    rows = [_recovery_row(requirement, rows_by_check.get(requirement["check_id"])) for requirement in SURFACE_REQUIREMENTS]
    failing_rows = [row for row in rows if row["status"] != "pass"]
    preflight_status = str(preflight_summary.get("status") or "missing")
    preflight_blockers = (
        preflight_summary.get("blockers")
        if isinstance(preflight_summary.get("blockers"), list)
        else [row["blocker"] for row in failing_rows if row["blocker"]]
    )

    if not preflight_present:
        status = "blocked_f2g_f2h_authoritative_surface_recovery_packet"
        recovery_required = True
        next_required_step = "Run tools/build_f2g_f2h_surface_preflight.py into .betelgeuze before scoping surface recovery."
    elif failing_rows:
        status = "f2g_f2h_authoritative_surface_recovery_packet_ready"
        recovery_required = True
        next_required_step = rows[failing_rows and rows.index(failing_rows[0])]["operator_action"]
    else:
        status = "f2g_f2h_authoritative_surface_recovery_not_required"
        recovery_required = False
        next_required_step = "Surface preflight is ready; proceed to the non-promoting F2g audit under the existing guardrails."

    summary = {
        "packet_type": "f2g_f2h_authoritative_surface_recovery_packet",
        "status": status,
        "preflight_artifact": _display(preflight_json, root=root),
        "preflight_artifact_present": preflight_present,
        "preflight_status": preflight_status,
        "preflight_blocker_count": int(preflight_summary.get("blocker_count") or len(preflight_blockers or [])),
        "preflight_blockers": [str(item) for item in (preflight_blockers or [])],
        "recovery_required": recovery_required,
        "recovery_item_count": len(rows),
        "blocked_recovery_item_count": len(failing_rows),
        "authoritative_source_documented": preflight_present,
        "execution_enabled": False,
        "surface_restore_executed": False,
        "placeholder_surface_creation_allowed": False,
        "f2g_audit_executed": False,
        "f2h_continuation_executed": False,
        "g1_promotion_allowed": False,
        "solver_claim_promotion_allowed": False,
        "protected_runs_artifact_written": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": next_required_step,
    }
    if not preflight_present:
        summary["preflight_blockers"] = ["f2g_f2h_surface_preflight_artifact_missing"]
        summary["preflight_blocker_count"] = 1
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# F2g/F2h Authoritative Surface Recovery Packet",
        "",
        f"- status: `{summary['status']}`",
        f"- preflight_status: `{summary['preflight_status']}`",
        f"- recovery_required: `{summary['recovery_required']}`",
        f"- blocked_recovery_item_count: `{summary['blocked_recovery_item_count']}`",
        f"- placeholder_surface_creation_allowed: `{summary['placeholder_surface_creation_allowed']}`",
        f"- g1_promotion_allowed: `{summary['g1_promotion_allowed']}`",
        "",
        "## Recovery Items",
        "",
        "| item | status | observed | required surface | blocker | operator action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['recovery_item_id']}` | `{row['status']}` | `{row['observed']}` | `{row['required_surface']}` | `{row['blocker'] or '-'}` | {row['operator_action']} |"
        )
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            summary["claim_boundary"],
            "",
            "## Next Step",
            "",
            f"- {summary['next_required_step']}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the F2g/F2h authoritative surface recovery packet.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--preflight-json", default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_f2g_f2h_authoritative_surface_recovery_packet(
        root=root,
        preflight_json=args.preflight_json,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
