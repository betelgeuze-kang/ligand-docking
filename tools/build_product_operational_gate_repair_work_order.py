#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREFLIGHT_JSON = "runs/product_execution_preflight_current.json"
DEFAULT_OUT_JSON = "runs/product_operational_gate_repair_work_order_current.json"
DEFAULT_OUT_CSV = "runs/product_operational_gate_repair_work_order_current.csv"
DEFAULT_OUT_MD = "runs/product_operational_gate_repair_work_order_current.md"

CLAIM_BOUNDARY = (
    "Product operational gate repair work order only; it computes eval-panel feasibility deficits from the local "
    "product execution preflight. It does not run docking, rewrite datasets, delete artifacts, lower product gates, "
    "emit scientific results, assemble bundles, upload, commit, push, or mutate external state."
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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


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


def _first_gate_check(preflight_packet: dict[str, Any]) -> dict[str, Any]:
    checks = preflight_packet.get("operational_gate_feasibility_checks")
    if not isinstance(checks, list):
        return {}
    for check in checks:
        if isinstance(check, dict) and _text(check.get("check")) == "operational_gate_feasibility":
            return check
    return {}


def _blocker_codes(preflight_packet: dict[str, Any]) -> list[str]:
    blockers = preflight_packet.get("blockers")
    if not isinstance(blockers, list):
        return []
    return [
        _text(blocker.get("code"))
        for blocker in blockers
        if isinstance(blocker, dict) and _text(blocker.get("code"))
    ]


def _row(
    *,
    sequence: int,
    repair_item: str,
    status: str,
    source_artifact: str,
    observed: str,
    required: str,
    recommended_action: str,
    reason: str,
    command: str = "",
) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "repair_item": repair_item,
        "status": status,
        "source_artifact": source_artifact,
        "observed": observed,
        "required": required,
        "recommended_action": recommended_action,
        "command": command,
        "reason": reason,
        "approval_token_required": "",
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
    }


def build_product_operational_gate_repair_work_order(
    *,
    preflight_packet: dict[str, Any],
    preflight_path: str = DEFAULT_PREFLIGHT_JSON,
) -> dict[str, Any]:
    preflight = _summary(preflight_packet)
    gate_check = _first_gate_check(preflight_packet)
    blocker_codes = _blocker_codes(preflight_packet)

    target_id = _text(preflight.get("target_id"))
    family = _text(preflight.get("family"))
    source_preflight_status = _text(preflight.get("status")) or "missing"
    gate_status = _text(gate_check.get("status")) or "missing"

    eval_unique = _int(gate_check.get("eval_unique_keys"))
    eval_positive = _int(gate_check.get("eval_positive_keys"))
    eval_negative = max(0, eval_unique - eval_positive)
    gate_min_eval = _int(gate_check.get("gate_min_eval_unique_keys"))
    gate_ef1_min = _float(gate_check.get("gate_ef1_min"))
    ef1_max_possible = gate_check.get("ef1_max_possible")

    additional_eval_needed = max(0, gate_min_eval - eval_unique)
    max_positive_at_gate_min = math.floor(gate_min_eval / gate_ef1_min) if gate_min_eval > 0 and gate_ef1_min > 0 else 0
    required_negative_at_gate_min = max(0, gate_min_eval - max_positive_at_gate_min) if gate_min_eval > 0 else 0
    additional_negative_needed = max(0, required_negative_at_gate_min - eval_negative)
    pure_negative_additions_needed = max(
        additional_eval_needed,
        math.ceil((gate_ef1_min * eval_positive) - eval_unique) if gate_ef1_min > 0 and eval_positive > 0 else 0,
    )
    active_only_additions = additional_eval_needed
    active_only_total = eval_unique + active_only_additions
    active_only_positive = eval_positive + active_only_additions
    active_only_ef1_max = (
        float(active_only_total / active_only_positive) if active_only_positive > 0 else None
    )
    active_only_expansion_can_satisfy_gate = (
        active_only_total >= gate_min_eval
        and (
            gate_ef1_min <= 0.0
            or active_only_ef1_max is None
            or active_only_ef1_max + 1e-12 >= gate_ef1_min
        )
    )

    repair_required = (
        "operational_gate_eval_unique_keys_impossible" in blocker_codes
        or "operational_gate_ef1_threshold_impossible" in blocker_codes
        or gate_status == "fail"
    )
    rows: list[dict[str, Any]] = []

    if not gate_check:
        rows.append(
            _row(
                sequence=1,
                repair_item="operational_gate_feasibility_source",
                status="blocked",
                source_artifact=preflight_path,
                observed="operational_gate_feasibility_check=missing",
                required="present product execution preflight gate feasibility check",
                recommended_action="Regenerate product execution preflight with operational gate enforcement enabled.",
                reason="No gate feasibility row was available to compute repair requirements.",
            )
        )
        status = "blocked_product_operational_gate_repair_work_order"
    elif repair_required:
        rows.extend(
            [
                _row(
                    sequence=1,
                    repair_item="eval_panel_size_deficit",
                    status="repair_required" if additional_eval_needed else "ready",
                    source_artifact=preflight_path,
                    observed=f"eval_unique_keys={eval_unique}",
                    required=f"gate_min_eval_unique_keys={gate_min_eval}",
                    recommended_action=(
                        f"Expand the operational eval split by at least {additional_eval_needed} unique target-ligand keys."
                    ),
                    reason="The product execution gate cannot pass until the eval split reaches the configured minimum size.",
                ),
                _row(
                    sequence=2,
                    repair_item="eval_negative_decoy_deficit",
                    status="repair_required" if additional_negative_needed else "ready",
                    source_artifact=preflight_path,
                    observed=f"eval_negative_keys={eval_negative}; eval_positive_keys={eval_positive}",
                    required=(
                        f"at_least_{required_negative_at_gate_min}_negative_keys_at_{gate_min_eval}_eval_keys; "
                        f"additional_negative_keys_needed={additional_negative_needed}"
                    ),
                    recommended_action=(
                        "Curate inactive or matched decoy ligand rows with SMILES/meta and assign them to the eval roles; "
                        "do not use active-only ChEMBL expansion for this gate."
                    ),
                    reason=(
                        f"At gate_min_eval_unique_keys={gate_min_eval} and gate_ef1_min={gate_ef1_min}, the eval panel "
                        f"needs at least {required_negative_at_gate_min} negative keys; current split has {eval_negative}."
                    ),
                ),
                _row(
                    sequence=3,
                    repair_item="active_only_expansion_guard",
                    status="blocked" if not active_only_expansion_can_satisfy_gate else "ready",
                    source_artifact=preflight_path,
                    observed=(
                        f"active_only_ef1_max_at_min_eval={active_only_ef1_max if active_only_ef1_max is not None else 'unknown'}"
                    ),
                    required=f"gate_ef1_min={gate_ef1_min}",
                    recommended_action=(
                        "Use a balanced validation panel with negatives/decoys, or make an explicit pilot-policy change before "
                        "lowering the operational EF1 gate."
                    ),
                    reason=(
                        "Adding only positive/active ligands drives the perfect-ranking EF1 ceiling toward 1.0 and cannot "
                        "satisfy the current gate."
                    ),
                ),
                _row(
                    sequence=4,
                    repair_item="stale_planned_artifact_guard",
                    status="repair_required" if "planned_artifact_already_present" in blocker_codes else "ready",
                    source_artifact=preflight_path,
                    observed="planned_artifact_already_present"
                    if "planned_artifact_already_present" in blocker_codes
                    else "planned_artifact_clear",
                    required="planned post-execution artifact absent or explicitly archived before rerun",
                    recommended_action=(
                        "Archive or remove the stale planned post-execution artifact after the eval panel repair is complete, then "
                        "rerun product execution preflight and approval gate."
                    ),
                    reason="The preflight is fail-closed against stale post-execution artifacts.",
                ),
            ]
        )
        status = "product_operational_gate_repair_work_order_ready"
    else:
        rows.append(
            _row(
                sequence=1,
                repair_item="operational_gate_feasibility",
                status="ready",
                source_artifact=preflight_path,
                observed=f"operational_gate_feasibility_status={gate_status}",
                required="pass",
                recommended_action="No operational gate repair is required; refresh the approval gate before execution.",
                reason="The configured eval split can satisfy the product operational gate.",
            )
        )
        status = "product_operational_gate_repair_not_required"

    summary = {
        "packet_type": "product_operational_gate_repair_work_order",
        "status": status,
        "target_id": target_id,
        "family": family,
        "source_preflight_status": source_preflight_status,
        "source_preflight_blocker_count": _int(preflight.get("blocker_count")),
        "source_preflight_blockers": blocker_codes,
        "gate_feasibility_status": gate_status,
        "repair_required": repair_required,
        "current_eval_unique_keys": eval_unique,
        "current_eval_positive_keys": eval_positive,
        "current_eval_negative_keys": eval_negative,
        "gate_min_eval_unique_keys": gate_min_eval,
        "gate_ef1_min": gate_ef1_min,
        "current_ef1_max_possible": ef1_max_possible,
        "additional_eval_unique_keys_needed": additional_eval_needed,
        "max_positive_keys_at_gate_min": max_positive_at_gate_min,
        "required_negative_keys_at_gate_min": required_negative_at_gate_min,
        "additional_negative_keys_needed": additional_negative_needed,
        "pure_negative_additions_needed": pure_negative_additions_needed,
        "active_only_expansion_can_satisfy_gate": active_only_expansion_can_satisfy_gate,
        "active_only_ef1_max_at_min_eval": active_only_ef1_max,
        "row_count": len(rows),
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            f"Repair the eval panel to at least {gate_min_eval} unique eval keys with at least "
            f"{required_negative_at_gate_min} negative/decoy keys ({additional_negative_needed} more than current), then "
            "regenerate product execution preflight and approval gate."
            if repair_required
            else "No gate repair is required."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Operational Gate Repair Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- family: `{s['family']}`",
        f"- source_preflight_status: `{s['source_preflight_status']}`",
        f"- gate_feasibility_status: `{s['gate_feasibility_status']}`",
        f"- current_eval_unique_keys: `{s['current_eval_unique_keys']}`",
        f"- current_eval_positive_keys: `{s['current_eval_positive_keys']}`",
        f"- current_eval_negative_keys: `{s['current_eval_negative_keys']}`",
        f"- gate_min_eval_unique_keys: `{s['gate_min_eval_unique_keys']}`",
        f"- gate_ef1_min: `{s['gate_ef1_min']}`",
        f"- current_ef1_max_possible: `{s['current_ef1_max_possible']}`",
        f"- additional_eval_unique_keys_needed: `{s['additional_eval_unique_keys_needed']}`",
        f"- required_negative_keys_at_gate_min: `{s['required_negative_keys_at_gate_min']}`",
        f"- additional_negative_keys_needed: `{s['additional_negative_keys_needed']}`",
        f"- active_only_expansion_can_satisfy_gate: `{s['active_only_expansion_can_satisfy_gate']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- docking_results_emitted: `{s['docking_results_emitted']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Repair Rows",
        "",
        "| sequence | repair_item | status | observed | required |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['sequence']}` | `{row['repair_item']}` | `{row['status']}` | "
            f"`{row['observed']}` | `{row['required']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a product operational gate repair work order from preflight.")
    parser.add_argument("--preflight-json", default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_product_operational_gate_repair_work_order(
        preflight_packet=_read_json_if_present(args.preflight_json),
        preflight_path=args.preflight_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
