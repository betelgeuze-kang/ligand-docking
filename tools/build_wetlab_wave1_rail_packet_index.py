#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NEGLECTED_ROWS_JSON = "runs/wetlab_neglected_wave1_rows_current.json"
DEFAULT_NEGLECTED_FIRST_CONTACT_JSON = "runs/wetlab_neglected_first_contact_packets_current.json"
DEFAULT_KINASE_RAIL_JSON = "runs/wetlab_wave1_kinase_rail_packets_current.json"
DEFAULT_KINASE_FIRST_CONTACT_JSON = "runs/wetlab_wave1_kinase_first_contact_packets_current.json"
DEFAULT_ANTIVIRAL_RAIL_JSON = "runs/wetlab_antiviral_wave1_rail_current.json"
DEFAULT_ANTIVIRAL_FIRST_CONTACT_JSON = "runs/wetlab_antiviral_first_contact_packets_current.json"
DEFAULT_ONCOLOGY_FIRST_CONTACT_JSON = "runs/wetlab_oncology_first_contact_packet_current.json"
DEFAULT_PRIORITY3_FILL_JSON = "runs/wetlab_priority3_repurposing_fill_map_current.json"
DEFAULT_PRIORITY3_NOVELTY_FILL_JSON = "runs/wetlab_priority3_novelty_fill_map_current.json"
DEFAULT_NEXT3_FILL_JSON = "runs/wetlab_next3_repurposing_fill_map_current.json"
DEFAULT_NEXT3_NOVELTY_FILL_JSON = "runs/wetlab_next3_novelty_fill_map_current.json"
DEFAULT_STK17B_FILL_JSON = "runs/wetlab_stk17b_repurposing_fill_map_current.json"
DEFAULT_STK17B_NOVELTY_FILL_JSON = "runs/wetlab_stk17b_novelty_fill_map_current.json"
DEFAULT_MPRO_VENDOR_COST_JSON = "runs/wetlab_mpro_vendor_cost_check_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_wave1_rail_packet_index_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_wave1_rail_packet_index_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_wave1_rail_packet_index_current.md"

TRACK_LABELS = {
    "DNDi_IPK": "DNDi / Institut Pasteur Korea",
    "M4K_open_science": "M4K / rare-disease open-science kinase",
    "SGC_dark_kinase": "SGC / dark kinase structural-biology labs",
    "READDI_Korea": "READDI / Korea antiviral rail",
    "oncology_condition_aware": "Condition-aware oncology labs",
}

TRACK_FAMILIES = {
    "DNDi_IPK": "neglected_disease",
    "M4K_open_science": "kinase",
    "SGC_dark_kinase": "kinase",
    "READDI_Korea": "antiviral",
    "oncology_condition_aware": "condition_aware_oncology",
}


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


def _maybe_load_json(path_like: str) -> dict[str, Any] | None:
    path = _resolve(path_like)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _track_id(row: dict[str, Any]) -> str:
    return str(row.get("partner_track_id") or row.get("partner_track") or "").strip()


def _rows_by_track(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in payload.get("rows", []) or []:
        track_id = _track_id(row)
        if not track_id:
            continue
        grouped.setdefault(track_id, []).append(dict(row))
    return grouped


def _target_ids(rows: list[dict[str, Any]]) -> str:
    ids: list[str] = []
    for row in rows:
        target_id = str(row.get("target_id", "")).strip()
        if target_id and target_id not in ids:
            ids.append(target_id)
    return ", ".join(ids)


def _make_row(
    track_id: str,
    rail_artifact_status: str,
    first_contact_status: str,
    outbound_status: str,
    target_ids: str,
    target_count: int,
    source_artifacts: str,
    next_required_step: str,
    lead_export_target: str,
    lead_gate_status: str,
) -> dict[str, Any]:
    return {
        "rail_id": track_id,
        "rail_label": TRACK_LABELS[track_id],
        "rail_family": TRACK_FAMILIES[track_id],
        "target_ids": target_ids,
        "target_count": target_count,
        "rail_artifact_status": rail_artifact_status,
        "first_contact_status": first_contact_status,
        "outbound_status": outbound_status,
        "lead_export_target": lead_export_target,
        "lead_gate_status": lead_gate_status,
        "source_artifacts": source_artifacts,
        "next_required_step": next_required_step,
    }


def build_payload(
    neglected_rows: dict[str, Any],
    neglected_first_contact: dict[str, Any],
    kinase_rail: dict[str, Any],
    kinase_first_contact: dict[str, Any],
    antiviral_rail: dict[str, Any],
    antiviral_first_contact: dict[str, Any],
    oncology_first_contact: dict[str, Any],
    priority3_fill: dict[str, Any] | None = None,
    priority3_novelty_fill: dict[str, Any] | None = None,
    next3_fill: dict[str, Any] | None = None,
    next3_novelty_fill: dict[str, Any] | None = None,
    stk17b_fill: dict[str, Any] | None = None,
    stk17b_novelty_fill: dict[str, Any] | None = None,
    mpro_vendor_cost: dict[str, Any] | None = None,
) -> dict[str, Any]:
    neglected_rows_by_track = _rows_by_track(neglected_rows)
    kinase_rows_by_track = _rows_by_track(kinase_rail)
    antiviral_rows_by_track = _rows_by_track(antiviral_rail)
    antiviral_first_contact_status = str(antiviral_first_contact.get("summary", {}).get("status", "pending_first_contact_packet"))
    oncology_first_contact_status = str(oncology_first_contact.get("summary", {}).get("status", "pending_high_lane"))

    priority3_fill_targets = {
        str(row.get("target_id", "")).strip()
        for row in (priority3_fill or {}).get("rows", []) or []
        if str(row.get("target_id", "")).strip()
    }
    novelty_fill_targets = {
        str(row.get("target_id", "")).strip()
        for row in (priority3_novelty_fill or {}).get("rows", []) or []
        if str(row.get("target_id", "")).strip()
    }
    next3_fill_targets = {
        str(row.get("target_id", "")).strip()
        for row in (next3_fill or {}).get("rows", []) or []
        if str(row.get("target_id", "")).strip()
    }
    next3_novelty_targets = {
        str(row.get("target_id", "")).strip()
        for row in (next3_novelty_fill or {}).get("rows", []) or []
        if str(row.get("target_id", "")).strip()
    }
    stk17b_fill_targets = {
        str(row.get("target_id", "")).strip()
        for row in (stk17b_fill or {}).get("rows", []) or []
        if str(row.get("target_id", "")).strip()
    }
    stk17b_novelty_targets = {
        str(row.get("target_id", "")).strip()
        for row in (stk17b_novelty_fill or {}).get("rows", []) or []
        if str(row.get("target_id", "")).strip()
    }
    mpro_vendor_ready = str((mpro_vendor_cost or {}).get("summary", {}).get("status", "")) == "wetlab_mpro_vendor_cost_check_ready"

    rows = [
        _make_row(
            "DNDi_IPK",
            str(neglected_rows.get("summary", {}).get("status", "pending_high_lane")),
            str(neglected_first_contact.get("summary", {}).get("status", "pending_high_lane")),
            "first_contact_exported" if "T. cruzi PDE" in priority3_fill_targets and "T. cruzi PDE" in novelty_fill_targets else "ready_for_compound_fill",
            _target_ids(neglected_rows_by_track.get("DNDi_IPK", [])),
            len(neglected_rows_by_track.get("DNDi_IPK", [])),
            "runs/wetlab_neglected_wave1_rows_current.md; runs/wetlab_neglected_first_contact_packets_current.md",
            "Export the T. cruzi PDE-enriched DNDi/IPK first-contact packet now, then keep Cruzain and LbDHODH on generic rows until their compound lanes are filled." if "T. cruzi PDE" in priority3_fill_targets and "T. cruzi PDE" in novelty_fill_targets else "Fill the neglected-disease repurposing and novelty compounds, then route the DNDi/IPK first-contact packets.",
            "T. cruzi PDE",
            "lead_packet_export_ready" if "T. cruzi PDE" in priority3_fill_targets and "T. cruzi PDE" in novelty_fill_targets else "novelty_fill_pending",
        ),
        _make_row(
            "M4K_open_science",
            str(kinase_rail.get("summary", {}).get("status", "pending_high_lane")),
            str(kinase_first_contact.get("summary", {}).get("status", "pending_high_lane")),
            "first_contact_exported" if "ALK2" in next3_fill_targets and "ALK2" in next3_novelty_targets else "ready_for_compound_fill",
            _target_ids(kinase_rows_by_track.get("M4K_open_science", [])),
            len(kinase_rows_by_track.get("M4K_open_science", [])),
            "runs/wetlab_wave1_kinase_rail_packets_current.md; runs/wetlab_wave1_kinase_first_contact_packets_current.md",
            "Export the ALK2-enriched M4K first-contact packet now." if "ALK2" in next3_fill_targets and "ALK2" in next3_novelty_targets else "Fill the ALK2 repurposing and novelty compounds, then export the M4K first-contact packet.",
            "ALK2",
            "lead_packet_export_ready" if "ALK2" in next3_fill_targets and "ALK2" in next3_novelty_targets else "pending_compound_fill",
        ),
        _make_row(
            "SGC_dark_kinase",
            str(kinase_rail.get("summary", {}).get("status", "pending_high_lane")),
            str(kinase_first_contact.get("summary", {}).get("status", "pending_high_lane")),
            "first_contact_exported" if "STK17B (DRAK2)" in stk17b_fill_targets and "STK17B (DRAK2)" in stk17b_novelty_targets else "ready_for_compound_fill",
            _target_ids(kinase_rows_by_track.get("SGC_dark_kinase", [])),
            len(kinase_rows_by_track.get("SGC_dark_kinase", [])),
            "runs/wetlab_wave1_kinase_rail_packets_current.md; runs/wetlab_wave1_kinase_first_contact_packets_current.md",
            "Export the STK17B-enriched SGC first-contact packet now." if "STK17B (DRAK2)" in stk17b_fill_targets and "STK17B (DRAK2)" in stk17b_novelty_targets else "Fill the STK17B repurposing and novelty compounds, then export the SGC first-contact packet.",
            "STK17B (DRAK2)",
            "lead_packet_export_ready" if "STK17B (DRAK2)" in stk17b_fill_targets and "STK17B (DRAK2)" in stk17b_novelty_targets else "pending_compound_fill",
        ),
        _make_row(
            "READDI_Korea",
            str(antiviral_rail.get("summary", {}).get("status", "pending_high_lane")),
            antiviral_first_contact_status,
            (
                "first_contact_exported"
                if antiviral_first_contact_status == "wetlab_antiviral_first_contact_packets_ready"
                and "SARS-CoV-2 Mpro" in priority3_fill_targets
                and "SARS-CoV-2 Mpro" in novelty_fill_targets
                and mpro_vendor_ready
                and "SARS-CoV-2 PLpro" in next3_fill_targets
                and "SARS-CoV-2 PLpro" in next3_novelty_targets
                else "ready_for_compound_fill" if antiviral_first_contact_status == "wetlab_antiviral_first_contact_packets_ready" else "rail_ready_pending_first_contact_build"
            ),
            _target_ids(antiviral_rows_by_track.get("READDI_Korea", [])),
            len(antiviral_rows_by_track.get("READDI_Korea", [])),
            "runs/wetlab_antiviral_wave1_rail_current.md; runs/wetlab_antiviral_first_contact_packets_current.md",
            "Export the paired Mpro plus PLpro READDI packet now with the vendor/cost sheet attached."
            if antiviral_first_contact_status == "wetlab_antiviral_first_contact_packets_ready"
            and "SARS-CoV-2 Mpro" in priority3_fill_targets
            and "SARS-CoV-2 Mpro" in novelty_fill_targets
            and mpro_vendor_ready
            and "SARS-CoV-2 PLpro" in next3_fill_targets
            and "SARS-CoV-2 PLpro" in next3_novelty_targets
            else "Fill the PLpro/Mpro repurposing and novelty compounds, then route the paired READDI first-contact packets.",
            "SARS-CoV-2 Mpro",
            "mpro_vendor_cost_ready" if antiviral_first_contact_status == "wetlab_antiviral_first_contact_packets_ready"
            and "SARS-CoV-2 Mpro" in priority3_fill_targets
            and "SARS-CoV-2 Mpro" in novelty_fill_targets
            and mpro_vendor_ready
            and "SARS-CoV-2 PLpro" in next3_fill_targets
            and "SARS-CoV-2 PLpro" in next3_novelty_targets else "novelty_fill_or_vendor_pending",
        ),
        _make_row(
            "oncology_condition_aware",
            oncology_first_contact_status,
            oncology_first_contact_status,
            (
                "first_contact_exported"
                if oncology_first_contact_status == "wetlab_oncology_first_contact_packet_ready"
                and "CA IX" in priority3_fill_targets
                and "CA IX" in novelty_fill_targets
                else "ready_for_compound_fill" if oncology_first_contact_status == "wetlab_oncology_first_contact_packet_ready" else "pending_high_lane"
            ),
            "CA IX",
            1,
            "runs/ca_ix_one_page_brief_current.md; runs/wetlab_oncology_first_contact_packet_current.md",
            "Export the CA IX-enriched oncology condition-aware first-contact packet now."
            if oncology_first_contact_status == "wetlab_oncology_first_contact_packet_ready"
            and "CA IX" in priority3_fill_targets
            and "CA IX" in novelty_fill_targets
            else "Fill the CA IX repurposing and novelty compounds, then route the oncology condition-aware first-contact packet.",
            "CA IX",
            "lead_packet_export_ready" if oncology_first_contact_status == "wetlab_oncology_first_contact_packet_ready"
            and "CA IX" in priority3_fill_targets
            and "CA IX" in novelty_fill_targets else "novelty_fill_pending",
        ),
    ]

    if mpro_vendor_ready:
        for row in rows:
            if row["rail_id"] == "READDI_Korea":
                row["mpro_vendor_cost_check_artifact"] = "runs/wetlab_mpro_vendor_cost_check_current.md"
                break

    all_exported = all(row["outbound_status"] == "first_contact_exported" for row in rows)
    summary = {
        "status": "wetlab_wave1_rail_packet_index_ready",
        "rail_count": len(rows),
        "compound_fill_ready_count": sum(1 for row in rows if row["outbound_status"] == "ready_for_compound_fill"),
        "first_contact_exported_count": sum(1 for row in rows if row["outbound_status"] == "first_contact_exported"),
        "rail_ready_pending_first_contact_build_count": sum(1 for row in rows if row["outbound_status"] == "rail_ready_pending_first_contact_build"),
        "pending_high_lane_count": sum(1 for row in rows if row["outbound_status"] == "pending_high_lane"),
        "priority3_repurposing_fill_target_count": len(priority3_fill_targets),
        "priority3_novelty_fill_target_count": len(novelty_fill_targets),
        "priority3_repurposing_fill_artifact": "runs/wetlab_priority3_repurposing_fill_map_current.md" if priority3_fill_targets else "",
        "priority3_novelty_fill_artifact": "runs/wetlab_priority3_novelty_fill_map_current.md" if novelty_fill_targets else "",
        "next3_repurposing_fill_target_count": len(next3_fill_targets),
        "next3_novelty_fill_target_count": len(next3_novelty_targets),
        "next3_repurposing_fill_artifact": "runs/wetlab_next3_repurposing_fill_map_current.md" if next3_fill_targets else "",
        "next3_novelty_fill_artifact": "runs/wetlab_next3_novelty_fill_map_current.md" if next3_novelty_targets else "",
        "stk17b_repurposing_fill_target_count": len(stk17b_fill_targets),
        "stk17b_novelty_fill_target_count": len(stk17b_novelty_targets),
        "stk17b_repurposing_fill_artifact": "runs/wetlab_stk17b_repurposing_fill_map_current.md" if stk17b_fill_targets else "",
        "stk17b_novelty_fill_artifact": "runs/wetlab_stk17b_novelty_fill_map_current.md" if stk17b_novelty_targets else "",
        "mpro_vendor_cost_check_ready": mpro_vendor_ready,
        "mpro_vendor_cost_check_artifact": "runs/wetlab_mpro_vendor_cost_check_current.md" if mpro_vendor_ready else "",
        "domain_generation_schema_artifact": "runs/wetlab_domain_generation_schema_current.md",
        "partner_export_schema_artifact": "runs/wetlab_partner_export_schema_current.md",
        "priority3_target_render_split_artifact": "runs/wetlab_priority3_target_render_split_current.md",
        "priority3_protein_run_queue_artifact": "runs/wetlab_priority3_protein_run_queue_current.md",
        "prep_artifact_lane_artifact": "runs/wetlab_prep_artifact_lane_current.md",
        "condition_aware_oncology_status": oncology_first_contact_status,
        "next_required_step": "Use the five exported rail packets as the outbound set, then launch the priority-three execution queue in serialized order while keeping prep/artifact work parallel and exports frozen." if all_exported else "Keep the priority-three rails exported, open the ALK2, Cruzain, PLpro, and STK17B next-rail packets with their bound fills, then export partner-ready email packets before any broader Wave 1 expansion.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Wave 1 Rail Packet Index",
        "",
        f"- status: `{s['status']}`",
        f"- rail_count: `{s['rail_count']}`",
        f"- compound_fill_ready_count: `{s['compound_fill_ready_count']}`",
        f"- first_contact_exported_count: `{s['first_contact_exported_count']}`",
        f"- rail_ready_pending_first_contact_build_count: `{s['rail_ready_pending_first_contact_build_count']}`",
        f"- pending_high_lane_count: `{s['pending_high_lane_count']}`",
        f"- priority3_repurposing_fill_target_count: `{s['priority3_repurposing_fill_target_count']}`",
        f"- priority3_novelty_fill_target_count: `{s['priority3_novelty_fill_target_count']}`",
        f"- stk17b_repurposing_fill_target_count: `{s['stk17b_repurposing_fill_target_count']}`",
        f"- stk17b_novelty_fill_target_count: `{s['stk17b_novelty_fill_target_count']}`",
        f"- condition_aware_oncology_status: `{s['condition_aware_oncology_status']}`",
        "",
        "| rail_id | rail_label | outbound_status | lead_export_target | lead_gate_status | target_count | target_ids |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    if s["priority3_repurposing_fill_artifact"]:
        lines.insert(7, f"- priority3_repurposing_fill_artifact: `{s['priority3_repurposing_fill_artifact']}`")
    if s["priority3_novelty_fill_artifact"]:
        lines.insert(8, f"- priority3_novelty_fill_artifact: `{s['priority3_novelty_fill_artifact']}`")
    if s["stk17b_repurposing_fill_artifact"]:
        lines.insert(9, f"- stk17b_repurposing_fill_artifact: `{s['stk17b_repurposing_fill_artifact']}`")
    if s["stk17b_novelty_fill_artifact"]:
        lines.insert(10, f"- stk17b_novelty_fill_artifact: `{s['stk17b_novelty_fill_artifact']}`")
    if s["mpro_vendor_cost_check_artifact"]:
        lines.insert(11, f"- mpro_vendor_cost_check_artifact: `{s['mpro_vendor_cost_check_artifact']}`")
    lines.insert(12, f"- domain_generation_schema_artifact: `{s['domain_generation_schema_artifact']}`")
    lines.insert(13, f"- partner_export_schema_artifact: `{s['partner_export_schema_artifact']}`")
    lines.insert(14, f"- priority3_target_render_split_artifact: `{s['priority3_target_render_split_artifact']}`")
    lines.insert(15, f"- priority3_protein_run_queue_artifact: `{s['priority3_protein_run_queue_artifact']}`")
    lines.insert(16, f"- prep_artifact_lane_artifact: `{s['prep_artifact_lane_artifact']}`")
    for row in payload["rows"]:
        lines.append(
            f"| `{row['rail_id']}` | `{row['rail_label']}` | `{row['outbound_status']}` | `{row['lead_export_target']}` | `{row['lead_gate_status']}` | `{row['target_count']}` | {row['target_ids']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Wave 1 rail packet outbound status index.")
    parser.add_argument("--neglected-rows-json", default=DEFAULT_NEGLECTED_ROWS_JSON)
    parser.add_argument("--neglected-first-contact-json", default=DEFAULT_NEGLECTED_FIRST_CONTACT_JSON)
    parser.add_argument("--kinase-rail-json", default=DEFAULT_KINASE_RAIL_JSON)
    parser.add_argument("--kinase-first-contact-json", default=DEFAULT_KINASE_FIRST_CONTACT_JSON)
    parser.add_argument("--antiviral-rail-json", default=DEFAULT_ANTIVIRAL_RAIL_JSON)
    parser.add_argument("--antiviral-first-contact-json", default=DEFAULT_ANTIVIRAL_FIRST_CONTACT_JSON)
    parser.add_argument("--oncology-first-contact-json", default=DEFAULT_ONCOLOGY_FIRST_CONTACT_JSON)
    parser.add_argument("--priority3-fill-json", default=DEFAULT_PRIORITY3_FILL_JSON)
    parser.add_argument("--priority3-novelty-fill-json", default=DEFAULT_PRIORITY3_NOVELTY_FILL_JSON)
    parser.add_argument("--next3-fill-json", default=DEFAULT_NEXT3_FILL_JSON)
    parser.add_argument("--next3-novelty-fill-json", default=DEFAULT_NEXT3_NOVELTY_FILL_JSON)
    parser.add_argument("--stk17b-fill-json", default=DEFAULT_STK17B_FILL_JSON)
    parser.add_argument("--stk17b-novelty-fill-json", default=DEFAULT_STK17B_NOVELTY_FILL_JSON)
    parser.add_argument("--mpro-vendor-cost-json", default=DEFAULT_MPRO_VENDOR_COST_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.neglected_rows_json),
        _load_json(args.neglected_first_contact_json),
        _load_json(args.kinase_rail_json),
        _load_json(args.kinase_first_contact_json),
        _load_json(args.antiviral_rail_json),
        _load_json(args.antiviral_first_contact_json),
        _load_json(args.oncology_first_contact_json),
        _maybe_load_json(args.priority3_fill_json),
        _maybe_load_json(args.priority3_novelty_fill_json),
        _maybe_load_json(args.next3_fill_json),
        _maybe_load_json(args.next3_novelty_fill_json),
        _maybe_load_json(args.stk17b_fill_json),
        _maybe_load_json(args.stk17b_novelty_fill_json),
        _maybe_load_json(args.mpro_vendor_cost_json),
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
