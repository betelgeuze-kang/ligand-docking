#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from tools.builder_table_utils import write_csv_rows
from tools.build_trpv1_sourcing_status_sheet import build_payload as build_trpv1_sourcing_payload
from tools.build_trpv1_sourcing_status_sheet import _load_json as load_trpv1_vendor_json

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OUT_DIR = "runs/wetlab_cro_packets"
DEFAULT_OUT_INDEX_JSON = "runs/wetlab_cro_delivery_packet_index_current.json"
DEFAULT_OUT_INDEX_CSV = "runs/wetlab_cro_delivery_packet_index_current.csv"
DEFAULT_OUT_INDEX_MD = "runs/wetlab_cro_delivery_packet_index_current.md"
DEFAULT_OUT_PDF_DIR = "output/pdf/wetlab_cro_packets"
DEFAULT_TRPV1_SHORTLIST_CSV = "docs/wetlab_packets/trpv1_ion_channel_candidate_shortlist.csv"
DEFAULT_TRPV1_SOURCING_REQUEST_CSV = "docs/wetlab_packets/trpv1_ion_channel_sourcing_request.csv"
DEFAULT_TRPV1_VENDOR_WEB_CHECK_JSON = "runs/trpv1_ion_channel_vendor_web_check_current.json"
DEFAULT_TRPV1_VENDOR_WEB_CHECK_MERGED_JSON = "runs/trpv1_ion_channel_vendor_web_check_merged_current.json"
DEFAULT_TRPV1_MATCHED_NEGATIVE_PANEL_JSON = "runs/trpv1_ion_channel_matched_negative_panel_current.json"
DEFAULT_TRPV1_VENDOR_FEASIBLE_NEGATIVE_PANEL_JSON = "runs/trpv1_ion_channel_vendor_feasible_negative_panel_resolved_current.json"
DEFAULT_LIGAND_ADMET_MODULE_JSON = "runs/ligand_admet_module_current.json"
DEFAULT_TMP_PDF_DIR = "tmp/pdfs/wetlab_cro_packets"

RETURN_TEMPLATE_FIELDS = (
    "compound_id",
    "compound_name",
    "expected_class",
    "concentration",
    "raw_signal",
    "normalized_signal",
    "replicate_count",
    "notes",
)

PACKET_SPECS = {
    "EGFR_KINASE": {
        "slug": "egfr_kinase",
        "label": "EGFR kinase pilot",
        "control_csv": "docs/wetlab_packets/egfr_kinase_pilot_controls.csv",
        "assay_mode": "biochemical kinase inhibition assay",
        "success_criterion": "Positives rank above negatives and at least 2 of 3 positives separate clearly from all negatives.",
        "main_risk": "Operational rather than scientific. Assay availability and turnaround time are the main constraints.",
        "repo_support": "config/real_drug_targets_native_v1.csv ; config/ligand_binding_reference_expanded_v2.csv ; config/ligand_eval_splits_v1.csv",
        "external_ask": "Run one kinase inhibition assay for 6 compounds with duplicate or triplicate technical replicates and return percent inhibition or IC50 curve fits.",
    },
    "ADRB2_GPCR_BLIND": {
        "slug": "adrb2_gpcr_blind",
        "label": "ADRB2 GPCR blind pilot",
        "control_csv": "docs/wetlab_packets/adrb2_gpcr_pilot_controls.csv",
        "assay_mode": "antagonist beta-arrestin assay or antagonist cAMP assay",
        "success_criterion": "Known binders outperform negatives and the signal direction matches expected antagonist behavior.",
        "main_risk": "Readout choice matters. Adapt the assay mode to the partner platform instead of forcing a specific GPCR modality.",
        "repo_support": "config/real_drug_targets_blind_gpcr_adrb2_v1.csv ; config/ligand_binding_reference_blind_gpcr_adrb2_v1.csv ; config/ligand_eval_splits_blind_gpcr_adrb2_chembl50_v1.csv",
        "external_ask": "Run one functional assay for 6 compounds total, using concentration-response for the top 3 positives and a compact single-point or short-curve negative panel.",
    },
    "HIV1_PROTEASE": {
        "slug": "hiv1_protease",
        "label": "HIV-1 protease pilot",
        "control_csv": "docs/wetlab_packets/hiv1_protease_pilot_controls.csv",
        "assay_mode": "fluorogenic protease inhibition assay",
        "success_criterion": "Canonical protease inhibitors separate from the three negatives in the expected direction.",
        "main_risk": "Operational rather than conceptual. The main requirement is a partner already running a standard protease assay.",
        "repo_support": "config/real_drug_targets_native_v1.csv ; config/ligand_binding_reference_disjoint_v2.csv ; config/ligand_eval_splits_disjoint_v2.csv",
        "external_ask": "Run one protease inhibition assay for 6 compounds total and return percent inhibition or IC50 values with replicate counts.",
    },
    "TRPV1_ION_CHANNEL_BLIND": {
        "slug": "trpv1_ion_channel_blind",
        "label": "TRPV1 ion-channel pilot",
        "assay_mode": "TRPV1 calcium influx assay or membrane potential assay",
        "success_criterion": "Top computational candidates show activity separation from matched negatives after vendor confirmation and control-lock.",
        "main_risk": "Compound sourcing and channel assay access are the real bottlenecks. This packet must not be sent before vendor confirmation is complete.",
        "repo_support": "config/real_drug_targets_blind_trpv1_v1.csv ; config/ligand_eval_splits_blind_trpv1_chembl20_v1.csv ; docs/wetlab_packets/trpv1_ion_channel_candidate_shortlist.csv ; docs/wetlab_packets/trpv1_ion_channel_sourcing_request.csv",
        "external_ask": "Only after identities and vendors are confirmed, run the same 6-compound pilot structure as the other starter packets.",
    },
}


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _preferred_vendor_json(path_like: str) -> str:
    if path_like == DEFAULT_TRPV1_VENDOR_WEB_CHECK_JSON:
        merged = _resolve(DEFAULT_TRPV1_VENDOR_WEB_CHECK_MERGED_JSON)
        if merged.exists():
            return str(merged)
    return path_like


def _preferred_matched_negative_json(path_like: str) -> str:
    if path_like == DEFAULT_TRPV1_MATCHED_NEGATIVE_PANEL_JSON:
        preferred = _resolve(DEFAULT_TRPV1_VENDOR_FEASIBLE_NEGATIVE_PANEL_JSON)
        if preferred.exists():
            try:
                payload = json.loads(preferred.read_text(encoding="utf-8"))
                if bool(((payload.get("summary", {}) or {}).get("matched_negative_panel_sendable", False))):
                    return str(preferred)
            except Exception:
                pass
    return path_like


def _load_optional_json(path_like: str) -> dict[str, Any] | None:
    path = _resolve(path_like)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _admet_target_summary_lookup(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    rows = (((payload or {}).get("structured", {}) or {}).get("target_summaries", []) or [])
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        target_id = str((row or {}).get("target_id", "")).strip()
        if target_id:
            lookup[target_id] = dict(row)
    return lookup


def _slug(value: str) -> str:
    return value.lower().replace(" ", "_").replace("-", "_").replace("/", "_").replace("(", "").replace(")", "")


def _clean(value: Any) -> str:
    return str(value if value is not None else "").replace("\n", " ").strip()


def _load_control_rows(path_like: str) -> list[dict[str, Any]]:
    return pd.read_csv(_resolve(path_like)).fillna("").to_dict(orient="records")


def _build_trpv1_packet_rows(
    shortlist_csv: str,
    sourcing_request_csv: str,
    vendor_web_check_json: str = DEFAULT_TRPV1_VENDOR_WEB_CHECK_JSON,
    matched_negative_panel_json: str = DEFAULT_TRPV1_MATCHED_NEGATIVE_PANEL_JSON,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sourcing_payload = build_trpv1_sourcing_payload(
        pd.read_csv(_resolve(shortlist_csv)),
        pd.read_csv(_resolve(sourcing_request_csv)),
        load_trpv1_vendor_json(vendor_web_check_json) if _resolve(vendor_web_check_json).exists() else None,
        load_trpv1_vendor_json(_preferred_matched_negative_json(matched_negative_panel_json))
        if _resolve(_preferred_matched_negative_json(matched_negative_panel_json)).exists()
        else None,
    )
    positive_rows = [row for row in sourcing_payload["rows"] if row["priority_rank"] <= 3]
    packet_rows: list[dict[str, Any]] = []
    for row in positive_rows:
        positive_locked = bool(row.get("positive_control_locked", False))
        packet_rows.append(
            {
                "target": "TRPV1_ION_CHANNEL_BLIND",
                "assay_mode": "TRPV1 calcium influx assay",
                "compound_id": row["chembl_id"],
                "compound_name": row["normalized_name"],
                "expected_class": "positive_control_locked" if positive_locked else "positive_candidate_pending_vendor_confirmation",
                "expected_direction": "higher_activity_than_negative_panel",
                "repo_source": "docs/wetlab_packets/trpv1_ion_channel_candidate_shortlist.csv",
                "notes": row["vendor_evidence_note"] if positive_locked else row["blocker_codes"],
                "panel_slot": row["panel_slot"],
                "panel_status": row["panel_lock_status"],
                "send_ready": positive_locked,
            }
        )
    matched_negative_rows = list(sourcing_payload.get("matched_negative_rows", []) or [])
    if matched_negative_rows:
        for row in matched_negative_rows:
            packet_rows.append(
                {
                    "target": "TRPV1_ION_CHANNEL_BLIND",
                    "assay_mode": "TRPV1 calcium influx assay",
                    "compound_id": row["compound_id"],
                    "compound_name": row["compound_name"],
                    "expected_class": row["expected_class"],
                    "expected_direction": row["expected_direction"],
                    "repo_source": row["repo_source"],
                    "notes": row["note"],
                    "panel_slot": row["panel_slot"],
                    "panel_status": "locked_internal_not_sendable" if not row.get("external_send_ready", False) else "locked_sendable",
                    "send_ready": bool(row.get("external_send_ready", False)),
                }
            )
    else:
        for slot_idx in range(1, 4):
            packet_rows.append(
                {
                    "target": "TRPV1_ION_CHANNEL_BLIND",
                    "assay_mode": "TRPV1 calcium influx assay",
                    "compound_id": f"UNLOCKED_NEGATIVE_{slot_idx}",
                    "compound_name": f"matched_negative_control_{slot_idx}",
                    "expected_class": "negative_placeholder",
                    "expected_direction": "lower_activity_than_positive_panel",
                    "repo_source": "pending_vendor_feasible_negative_selection",
                    "notes": "negative control slot still needs a matched purchasable compound",
                    "panel_slot": f"negative_{slot_idx}",
                    "panel_status": "unlocked_missing_negative_selection",
                    "send_ready": False,
                }
            )
    return packet_rows, sourcing_payload["summary"]


def _build_packet_payload(
    *,
    target_id: str,
    rows: list[dict[str, Any]],
    spec: dict[str, str],
    out_dir: Path,
    pdf_dir: Path,
    trpv1_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slug = spec["slug"]
    packet_md = out_dir / f"{slug}_cro_delivery_packet_current.md"
    packet_json = packet_md.with_suffix(".json")
    packet_csv = packet_md.with_suffix(".csv")
    template_csv = out_dir / f"{slug}_cro_data_return_template_current.csv"
    packet_pdf = pdf_dir / f"{slug}_cro_delivery_packet_current.pdf"

    missing_slots = [row for row in rows if not bool(row.get("send_ready", True))]
    ready_for_send = not missing_slots
    summary = {
        "status": "cro_delivery_packet_ready" if ready_for_send else "cro_delivery_packet_blocked",
        "target_id": target_id,
        "packet_label": spec["label"],
        "assay_mode": spec["assay_mode"],
        "compound_count": len(rows),
        "ready_for_send": ready_for_send,
        "missing_slot_count": len(missing_slots),
        "success_criterion": spec["success_criterion"],
        "main_risk": spec["main_risk"],
        "repo_support": spec["repo_support"],
        "external_ask": spec["external_ask"],
        "packet_md": str(packet_md),
        "packet_pdf": str(packet_pdf),
        "data_return_template_csv": str(template_csv),
        "next_required_step": (
            "Send this packet to the CRO or collaborator with the data-return template attached."
            if ready_for_send
            else "Resolve the missing compound slots before sending this packet externally."
        ),
    }
    if trpv1_summary:
        summary["sourcing_blocking_reason"] = trpv1_summary["blocking_reason"]
        summary["sourcing_vendor_confirmed_positive_count"] = trpv1_summary["vendor_confirmed_positive_count"]
        summary["matched_negative_slot_count_locked"] = trpv1_summary["matched_negative_slot_count_locked"]
        summary["matched_negative_panel_locked_internal"] = trpv1_summary["matched_negative_panel_locked_internal"]
        summary["matched_negative_panel_sendable"] = trpv1_summary["matched_negative_panel_sendable"]
        summary["vendor_evidence_mode"] = trpv1_summary.get("vendor_evidence_mode", "")
        summary["vendor_quote_response_received_count"] = trpv1_summary.get("vendor_quote_response_received_count", 0)
        summary["control_panel_locked"] = trpv1_summary.get("control_panel_locked", False)

    structured = {
        "data_return_template_fields": " ; ".join(RETURN_TEMPLATE_FIELDS),
        "packet_shape": "6-compound pilot",
        "control_panel_state": "complete" if ready_for_send else "incomplete",
    }
    payload = {"summary": summary, "structured": structured, "rows": rows}

    packet_json.parent.mkdir(parents=True, exist_ok=True)
    packet_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(packet_csv, rows)
    _write_packet_markdown(packet_md, payload)
    write_csv_rows(template_csv, _build_data_return_template_rows(rows))
    _write_packet_pdf(packet_pdf, payload)
    _render_pdf_preview(packet_pdf)
    return {
        "target_id": target_id,
        "packet_status": summary["status"],
        "ready_for_send": ready_for_send,
        "compound_count": len(rows),
        "missing_slot_count": len(missing_slots),
        "packet_md": str(packet_md),
        "packet_pdf": str(packet_pdf),
        "data_return_template_csv": str(template_csv),
        "success_criterion": spec["success_criterion"],
        "matched_negative_slot_count_locked": summary.get("matched_negative_slot_count_locked", 0),
        "matched_negative_panel_locked_internal": summary.get("matched_negative_panel_locked_internal", False),
        "matched_negative_panel_sendable": summary.get("matched_negative_panel_sendable", False),
        "vendor_evidence_mode": summary.get("vendor_evidence_mode", ""),
        "vendor_quote_response_received_count": summary.get("vendor_quote_response_received_count", 0),
        "control_panel_locked": summary.get("control_panel_locked", False),
    }


def _build_data_return_template_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    template_rows: list[dict[str, Any]] = []
    for row in rows:
        template_rows.append(
            {
                "compound_id": row.get("compound_id", ""),
                "compound_name": row.get("compound_name", ""),
                "expected_class": row.get("expected_class", ""),
                "concentration": "",
                "raw_signal": "",
                "normalized_signal": "",
                "replicate_count": "",
                "notes": "",
            }
        )
    return template_rows


def _write_packet_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        f"# {summary['packet_label']}",
        "",
        f"- status: `{summary['status']}`",
        f"- target_id: `{summary['target_id']}`",
        f"- assay_mode: `{summary['assay_mode']}`",
        f"- compound_count: `{summary['compound_count']}`",
        f"- ready_for_send: `{summary['ready_for_send']}`",
        f"- missing_slot_count: `{summary['missing_slot_count']}`",
        "",
        "## Success Criterion",
        "",
        f"- {summary['success_criterion']}",
        "",
        "## External Ask",
        "",
        f"- {summary['external_ask']}",
        "",
        "## Compound Panel",
        "",
        "| compound_id | compound_name | expected_class | expected_direction | notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row.get('compound_id', '')}` | {row.get('compound_name', '')} | `{row.get('expected_class', '')}` | `{row.get('expected_direction', '')}` | {row.get('notes', '')} |"
        )
    lines.extend(
        [
            "",
            "## Data Return Template Fields",
            "",
            "- compound_id",
            "- compound_name",
            "- expected_class",
            "- concentration",
            "- raw_signal",
            "- normalized_signal",
            "- replicate_count",
            "- notes",
            "",
            "## Main Risk",
            "",
            f"- {summary['main_risk']}",
            "",
            "## Repo Support",
            "",
            f"- {summary['repo_support']}",
            "",
            "## Next Step",
            "",
            f"- {summary['next_required_step']}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_packet_pdf(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    section_style = styles["Heading2"]
    body_style = styles["BodyText"]
    small_style = ParagraphStyle("SmallBody", parent=body_style, fontSize=9, leading=11)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    summary = payload["summary"]
    story: list[Any] = [
        Paragraph(summary["packet_label"], title_style),
        Spacer(1, 4 * mm),
        Paragraph(f"Target: {summary['target_id']}", body_style),
        Paragraph(f"Assay mode: {summary['assay_mode']}", body_style),
        Paragraph(f"Status: {summary['status']}", body_style),
        Paragraph(f"Ready for send: {summary['ready_for_send']}", body_style),
        Spacer(1, 4 * mm),
        Paragraph("Success Criterion", section_style),
        Paragraph(summary["success_criterion"], body_style),
        Spacer(1, 3 * mm),
        Paragraph("External Ask", section_style),
        Paragraph(summary["external_ask"], body_style),
        Spacer(1, 3 * mm),
        Paragraph("Compound Panel", section_style),
    ]

    table_data = [["Compound ID", "Compound Name", "Class", "Expected Direction"]]
    for row in payload["rows"]:
        table_data.append(
            [
                str(row.get("compound_id", "")),
                str(row.get("compound_name", "")),
                str(row.get("expected_class", "")),
                str(row.get("expected_direction", "")),
            ]
        )
    table = Table(table_data, repeatRows=1, colWidths=[40 * mm, 62 * mm, 42 * mm, 38 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    story.extend(
        [
            Spacer(1, 3 * mm),
            Paragraph("Data Return Template", section_style),
            Paragraph(", ".join(RETURN_TEMPLATE_FIELDS), small_style),
            Spacer(1, 3 * mm),
            Paragraph("Main Risk", section_style),
            Paragraph(summary["main_risk"], body_style),
            Spacer(1, 3 * mm),
            Paragraph("Repo Support", section_style),
            Paragraph(summary["repo_support"], small_style),
        ]
    )
    doc.build(story)


def _render_pdf_preview(pdf_path: Path) -> None:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        return
    tmp_dir = _resolve(DEFAULT_TMP_PDF_DIR)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    prefix = tmp_dir / pdf_path.stem
    subprocess.run(
        [pdftoppm, "-png", str(pdf_path), str(prefix)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for png_path in tmp_dir.glob(f"{pdf_path.stem}-*.png"):
        png_path.unlink()


def build_payload(
    *,
    out_dir: Path,
    pdf_dir: Path,
    trpv1_shortlist_csv: str,
    trpv1_sourcing_request_csv: str,
    trpv1_vendor_web_check_json: str,
    trpv1_matched_negative_panel_json: str,
    ligand_admet_module_json: str,
) -> dict[str, Any]:
    admet_payload = _load_optional_json(ligand_admet_module_json)
    admet_summary = dict((admet_payload or {}).get("summary", {}) or {})
    admet_by_target = _admet_target_summary_lookup(admet_payload)
    rows: list[dict[str, Any]] = []
    for target_id, spec in PACKET_SPECS.items():
        if target_id == "TRPV1_ION_CHANNEL_BLIND":
            packet_rows, trpv1_summary = _build_trpv1_packet_rows(
                trpv1_shortlist_csv,
                trpv1_sourcing_request_csv,
                trpv1_vendor_web_check_json,
                trpv1_matched_negative_panel_json,
            )
            index_row = _build_packet_payload(
                target_id=target_id,
                rows=packet_rows,
                spec=spec,
                out_dir=out_dir,
                pdf_dir=pdf_dir,
                trpv1_summary=trpv1_summary,
            )
        else:
            packet_rows = _load_control_rows(spec["control_csv"])
            index_row = _build_packet_payload(
                target_id=target_id,
                rows=packet_rows,
                spec=spec,
                out_dir=out_dir,
                pdf_dir=pdf_dir,
            )
        admet_target = admet_by_target.get(target_id, {})
        index_row.update(
            {
                "admet_module_status": _clean(admet_summary.get("status", "")),
                "admet_compound_count": int(admet_target.get("compound_count", 0) or 0),
                "admet_green_count": int(admet_target.get("green_count", 0) or 0),
                "admet_yellow_count": int(admet_target.get("yellow_count", 0) or 0),
                "admet_red_count": int(admet_target.get("red_count", 0) or 0),
            }
        )
        index_row["admet_bucket_summary"] = (
            f"{index_row['admet_green_count']}g/{index_row['admet_yellow_count']}y/{index_row['admet_red_count']}r"
        )
        index_row["admet_triage_signal"] = (
            "red_present"
            if index_row["admet_red_count"] > 0
            else "yellow_present"
            if index_row["admet_yellow_count"] > 0
            else "green_only"
            if index_row["admet_compound_count"] > 0
            else "not_reported"
        )
        rows.append(index_row)

    summary = {
        "status": "wetlab_cro_delivery_packet_index_ready",
        "target_count": len(rows),
        "ready_for_send_count": sum(1 for row in rows if row["ready_for_send"]),
        "blocked_count": sum(1 for row in rows if not row["ready_for_send"]),
        "admet_module_status": _clean(admet_summary.get("status", "")),
        "admet_target_count": int(admet_summary.get("target_count", 0) or 0),
        "admet_compound_count": int(admet_summary.get("compound_count", 0) or 0),
        "admet_green_count": int(admet_summary.get("green_count", 0) or 0),
        "admet_yellow_count": int(admet_summary.get("yellow_count", 0) or 0),
        "admet_red_count": int(admet_summary.get("red_count", 0) or 0),
        "admet_module_scope": _clean(admet_summary.get("module_scope", "")),
        "admet_next_required_step": _clean(admet_summary.get("next_required_step", "")),
        "next_required_step": "Use the ready packets for CRO outreach now, and keep TRPV1 blocked until vendor confirmation and matched negatives are locked.",
    }
    return {"summary": summary, "rows": rows}


def _write_index_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Wet-Lab CRO Delivery Packet Index",
        "",
        f"- status: `{summary['status']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- ready_for_send_count: `{summary['ready_for_send_count']}`",
        f"- blocked_count: `{summary['blocked_count']}`",
        f"- admet_module_status: `{summary.get('admet_module_status', '')}`",
        f"- admet_target_count: `{summary.get('admet_target_count', 0)}`",
        f"- admet_compound_count: `{summary.get('admet_compound_count', 0)}`",
        f"- admet_bucket_summary: `{summary.get('admet_green_count', 0)}g/{summary.get('admet_yellow_count', 0)}y/{summary.get('admet_red_count', 0)}r`",
        "",
        "| target_id | packet_status | ready_for_send | compound_count | missing_slot_count | admet_bucket_summary | admet_triage_signal | packet_md | packet_pdf |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['packet_status']}` | `{row['ready_for_send']}` | `{row['compound_count']}` | `{row['missing_slot_count']}` | `{row.get('admet_bucket_summary', '')}` | `{row.get('admet_triage_signal', '')}` | `{row['packet_md']}` | `{row['packet_pdf']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CRO delivery packets and PDFs for the external wet-lab starter set.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-pdf-dir", default=DEFAULT_OUT_PDF_DIR)
    parser.add_argument("--out-index-json", default=DEFAULT_OUT_INDEX_JSON)
    parser.add_argument("--out-index-csv", default=DEFAULT_OUT_INDEX_CSV)
    parser.add_argument("--out-index-md", default=DEFAULT_OUT_INDEX_MD)
    parser.add_argument("--trpv1-shortlist-csv", default=DEFAULT_TRPV1_SHORTLIST_CSV)
    parser.add_argument("--trpv1-sourcing-request-csv", default=DEFAULT_TRPV1_SOURCING_REQUEST_CSV)
    parser.add_argument("--trpv1-vendor-web-check-json", default=DEFAULT_TRPV1_VENDOR_WEB_CHECK_JSON)
    parser.add_argument("--trpv1-matched-negative-panel-json", default=DEFAULT_TRPV1_MATCHED_NEGATIVE_PANEL_JSON)
    parser.add_argument("--ligand-admet-module-json", default=DEFAULT_LIGAND_ADMET_MODULE_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = _resolve(args.out_dir)
    pdf_dir = _resolve(args.out_pdf_dir)
    trpv1_vendor_web_check_json = _preferred_vendor_json(args.trpv1_vendor_web_check_json)
    payload = build_payload(
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        trpv1_shortlist_csv=args.trpv1_shortlist_csv,
        trpv1_sourcing_request_csv=args.trpv1_sourcing_request_csv,
        trpv1_vendor_web_check_json=trpv1_vendor_web_check_json,
        trpv1_matched_negative_panel_json=args.trpv1_matched_negative_panel_json,
        ligand_admet_module_json=args.ligand_admet_module_json,
    )
    out_json = _resolve(args.out_index_json)
    out_csv = _resolve(args.out_index_csv)
    out_md = _resolve(args.out_index_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_index_markdown(out_md, payload)


if __name__ == "__main__":
    main()
