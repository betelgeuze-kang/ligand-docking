#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.operator_surface_contracts import (
    TRANSPORTER_SAFE_SCOPE_MANUAL_REVIEW_ONLY_DRAFT_PACKETS,
    TRANSPORTER_SAFE_SCOPE_SEED_ROW_BLOCKER_CLOSURE,
)

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PLATFORM_JSON = "runs/platform_operator_quickstart_packet_current.json"
DEFAULT_CATALOG_JSON = "runs/family_packet_catalog_current.json"
DEFAULT_PARTIAL_JSON = "runs/partial_authoritative_reviewer_console_current.json"
DEFAULT_TRANSPORTER_JSON = "runs/transporter_operator_console_current.json"
DEFAULT_RUN_NOW_JSON = "runs/run_now_safe_command_packet_current.json"
DEFAULT_OUT_JSON = "runs/family_operator_quicklink_board_current.json"
DEFAULT_OUT_CSV = "runs/family_operator_quicklink_board_current.csv"
DEFAULT_OUT_MD = "runs/family_operator_quicklink_board_current.md"


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _catalog_lookup(catalog_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    preferred_packet_kind = {
        "ca2": "evidence_closure",
        "pxr": "evidence_closure",
        "transporter": "blocker_closure",
        "idp": "commercial_pretest",
        "aqp1": "seed_row_promotion",
        "glut1": "reviewer_workbench",
    }
    rows_by_family: dict[str, list[dict[str, Any]]] = {}
    for row in catalog_payload.get("rows", []):
        family = str(row.get("family", "")).strip()
        if not family:
            continue
        rows_by_family.setdefault(family, []).append(dict(row))

    lookup: dict[str, dict[str, Any]] = {}
    for family, rows in rows_by_family.items():
        preferred_kind = preferred_packet_kind.get(family, "")
        if preferred_kind:
            preferred_row = next(
                (row for row in rows if str(row.get("packet_kind", "")).strip() == preferred_kind),
                None,
            )
            if preferred_row is not None:
                lookup[family] = preferred_row
                continue
        lookup[family] = rows[-1]
    return lookup


def _run_now_rows(
    platform_payload: dict[str, Any],
    catalog_payload: dict[str, Any],
    run_now_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    catalog = _catalog_lookup(catalog_payload)
    safe_lookup = {
        str(row.get("family", "")).strip(): dict(row)
        for row in run_now_payload.get("rows", [])
        if str(row.get("family", "")).strip()
    }
    rows: list[dict[str, Any]] = []
    for row in platform_payload.get("rows", []):
        if str(row.get("lane", "")).strip() != "run_now":
            continue
        family = str(row.get("family", "")).strip()
        safe = safe_lookup.get(family, {})
        cat = catalog.get("run_now", {})
        family_cat = catalog.get(family, {})
        if family == "idp":
            open_first_artifact = str(family_cat.get("primary_artifact", "")).strip() or str(safe.get("source_artifact", "")).strip()
            guardrail_artifact = str(family_cat.get("secondary_artifact", "")).strip() or str(safe.get("source_artifact", "")).strip()
            open_first_command = f"sed -n '1,220p' {open_first_artifact}" if open_first_artifact else ""
            guardrail_command = f"sed -n '1,220p' {guardrail_artifact}" if guardrail_artifact else ""
        else:
            open_first_artifact = str(safe.get("source_artifact", "")).strip() or str(cat.get("primary_artifact", "")).strip()
            guardrail_artifact = (
                str(safe.get("source_artifact", "")).strip()
                or str(cat.get("secondary_artifact", "")).strip()
                or "runs/platform_operator_quickstart_packet_current.md"
            )
            open_first_command = (
                str(safe.get("artifact_check_command", "")).strip()
                or "sed -n '1,220p' runs/platform_operator_quickstart_packet_current.md"
            )
            guardrail_command = (
                str(safe.get("guardrail_check_command", "")).strip()
                or "sed -n '1,220p' runs/platform_operator_quickstart_packet_current.md"
            )
        rows.append(
            {
                "lane": "run_now",
                "family": family,
                "scope_now": str(row.get("scope_now", "")).strip(),
                "status_signal": str(row.get("current_state", "")).strip(),
                "open_first_artifact": open_first_artifact,
                "open_first_command": open_first_command,
                "guardrail_artifact": guardrail_artifact,
                "guardrail_command": guardrail_command,
                "primary_blocker": str(row.get("primary_blocker", "")).strip(),
                "one_line_note": str(safe.get("primary_handoff_note", "")).strip()
                or str(row.get("operator_action", "")).strip(),
            }
        )
    return rows


def _partial_rows(
    catalog_payload: dict[str, Any],
    partial_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    catalog = _catalog_lookup(catalog_payload)
    rows: list[dict[str, Any]] = []
    for row in partial_payload.get("family_rows", []):
        family = str(row.get("family", "")).strip()
        cat = catalog.get(family, {})
        rows.append(
            {
                "lane": "partial_authoritative",
                "family": family,
                "scope_now": str(row.get("safe_scope_now", "")).strip(),
                "status_signal": f"ready={row.get('ready_rows', 0)} blocked={row.get('blocked_rows', 0)}",
                "open_first_artifact": str(cat.get("primary_artifact", "")).strip(),
                "open_first_command": str(row.get("artifact_check_command", "")).strip(),
                "guardrail_artifact": str(cat.get("secondary_artifact", "")).strip(),
                "guardrail_command": str(row.get("guardrail_check_command", "")).strip(),
                "primary_blocker": str(row.get("review_focus", "")).strip(),
                "one_line_note": str(row.get("reviewer_note", "")).strip(),
            }
        )
    return rows


def _manual_review_rows(
    catalog_payload: dict[str, Any],
    transporter_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    catalog = _catalog_lookup(catalog_payload)
    catalog_summary = dict(catalog_payload.get("summary", {}) or {})
    catalog_rows = [dict(row) for row in catalog_payload.get("rows", []) or []]
    cat = catalog.get("transporter", {})
    transporter_summary = dict(transporter_payload.get("summary", {}) or {})
    transporter_phase = str(transporter_summary.get("current_phase", "") or "").strip()
    rows: list[dict[str, Any]] = []
    for row in transporter_payload.get("target_rows", []):
        family = str(row.get("target", "")).strip()
        family_cat = catalog.get(family, {})
        family_quantitative_cat = next(
            (
                entry
                for entry in catalog_rows
                if str(entry.get("family", "")).strip() == family
                and str(entry.get("packet_kind", "")).strip() == "quantitative_provenance"
            ),
            {},
        )
        pending_manual = int(row.get("pending_manual_verdict_count", 0) or 0)
        open_first_artifact = (
            str(row.get("open_first", "")).strip()
            or str(family_cat.get("primary_artifact", "")).strip()
            or str(cat.get("primary_artifact", "")).strip()
        )
        open_first_command = f"sed -n '1,220p' {open_first_artifact}" if open_first_artifact else ""
        status_signal = (
            f"phase={transporter_phase} wave={row.get('wave', '')}"
            if pending_manual == 0 and transporter_phase
            else f"pending_manual={pending_manual} wave={row.get('wave', '')}"
        )
        one_line_note = str(row.get("operator_instruction", "")).strip()
        if family == "aqp1":
            provenance_artifact = str(family_quantitative_cat.get("primary_artifact", "")).strip() or "runs/aqp1_quantitative_provenance_packet_current.md"
            reviewer_artifact = "runs/aqp1_reviewer_workbench_current.md"
            open_first_command = (
                f"sed -n '1,220p' {open_first_artifact}"
                f" && printf '\\n---\\n' && sed -n '1,220p' {provenance_artifact}"
                f" && printf '\\n---\\n' && sed -n '1,220p' {reviewer_artifact}"
            )
            status_signal += (
                f" exact_human_activity={catalog_summary.get('aqp1_quantitative_provenance_exact_human_activity_count', 0)}"
                f" focus={catalog_summary.get('aqp1_quantitative_provenance_primary_focus_ligand', '')}"
            )
            one_line_note = (
                f"{one_line_note} "
                f"Use the AQP1 provenance lane for `{catalog_summary.get('aqp1_quantitative_provenance_primary_focus_ligand', 'AqB013')}` "
                "and keep replacement_reference_binding_kcal_mol blank."
            ).strip()
        rows.append(
            {
                "lane": "manual_review",
                "family": family,
                "scope_now": (
                    TRANSPORTER_SAFE_SCOPE_SEED_ROW_BLOCKER_CLOSURE
                    if pending_manual == 0 and transporter_phase
                    else TRANSPORTER_SAFE_SCOPE_MANUAL_REVIEW_ONLY_DRAFT_PACKETS
                ),
                "status_signal": status_signal,
                "open_first_artifact": open_first_artifact,
                "open_first_command": open_first_command,
                "guardrail_artifact": str(cat.get("secondary_artifact", "")).strip(),
                "guardrail_command": f"sed -n '1,220p' {str(cat.get('secondary_artifact', '')).strip()}",
                "primary_blocker": (
                    "placeholder_packet_rows_and_donor_policy_blocked"
                    if pending_manual == 0
                    else str(row.get("review_bucket", "")).strip()
                ),
                "one_line_note": one_line_note,
            }
        )
    return rows


def build_payload(
    *,
    platform_payload: dict[str, Any],
    catalog_payload: dict[str, Any],
    partial_payload: dict[str, Any],
    transporter_payload: dict[str, Any],
    run_now_payload: dict[str, Any],
) -> dict[str, Any]:
    rows = (
        _run_now_rows(platform_payload, catalog_payload, run_now_payload)
        + _partial_rows(catalog_payload, partial_payload)
        + _manual_review_rows(catalog_payload, transporter_payload)
    )
    lane_order = {"run_now": 0, "partial_authoritative": 1, "manual_review": 2}
    family_order = {
        "gpcr": 0,
        "ion_channel": 1,
        "kinase": 2,
        "idp": 3,
        "ca2": 4,
        "pxr": 5,
        "aqp1": 6,
        "glut1": 7,
    }
    rows.sort(key=lambda r: (lane_order.get(r["lane"], 9), family_order.get(r["family"], 99)))
    summary = {
        "lane_count": 3,
        "quicklink_row_count": len(rows),
        "run_now_count": sum(1 for r in rows if r["lane"] == "run_now"),
        "partial_authoritative_count": sum(1 for r in rows if r["lane"] == "partial_authoritative"),
        "manual_review_count": sum(1 for r in rows if r["lane"] == "manual_review"),
        "next_required_step": "Open the first artifact for the lane you are operating in, run the paired guardrail command second, and do not cross family scope boundaries from this board alone.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Family Operator Quicklink Board",
        "",
        f"- lane_count: `{summary['lane_count']}`",
        f"- quicklink_row_count: `{summary['quicklink_row_count']}`",
        f"- run_now_count: `{summary['run_now_count']}`",
        f"- partial_authoritative_count: `{summary['partial_authoritative_count']}`",
        f"- manual_review_count: `{summary['manual_review_count']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Quicklinks",
        "",
        "| lane | family | scope_now | open_first_artifact | open_first_command | guardrail_artifact | primary_blocker |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['lane']}` | `{row['family']}` | `{row['scope_now']}` | `{row['open_first_artifact']}` | "
            f"`{row['open_first_command']}` | `{row['guardrail_artifact']}` | `{row['primary_blocker']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a family operator quicklink board for run_now, partial-authoritative, and manual-review lanes.")
    parser.add_argument("--platform-json", default=DEFAULT_PLATFORM_JSON)
    parser.add_argument("--catalog-json", default=DEFAULT_CATALOG_JSON)
    parser.add_argument("--partial-json", default=DEFAULT_PARTIAL_JSON)
    parser.add_argument("--transporter-json", default=DEFAULT_TRANSPORTER_JSON)
    parser.add_argument("--run-now-json", default=DEFAULT_RUN_NOW_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        platform_payload=_load_json(args.platform_json),
        catalog_payload=_load_json(args.catalog_json),
        partial_payload=_load_json(args.partial_json),
        transporter_payload=_load_json(args.transporter_json),
        run_now_payload=_load_json(args.run_now_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()
