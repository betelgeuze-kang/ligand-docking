#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NEGLECTED_OUTREACH_JSON = "runs/wetlab_neglected_outreach_packet_current.json"
DEFAULT_ONCOLOGY_FIRST_CONTACT_JSON = "runs/wetlab_oncology_first_contact_packet_current.json"
DEFAULT_ANTIVIRAL_FIRST_CONTACT_JSON = "runs/wetlab_antiviral_first_contact_packets_current.json"
DEFAULT_KINASE_OUTREACH_JSON = "runs/wetlab_kinase_outreach_packet_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_partner_first_contact_export_bundle_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_partner_first_contact_export_bundle_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_partner_first_contact_export_bundle_current.md"
DEFAULT_SENDER_NAME = "강지훈"
DEFAULT_SENDER_AFFILIATION: str | None = None


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


def _ready_targets(payload: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    for row in payload.get("rows", []) or []:
        if str(row.get("status", "")) == "ready_for_outbound_send":
            target_id = str(row.get("target_id", "")).strip()
            if target_id:
                targets.append(target_id)
    return targets


def _rows_by_track(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in payload.get("rows", []) or []:
        track_id = str(row.get("partner_track_id", "")).strip()
        if track_id:
            rows[track_id] = dict(row)
    return rows


def _render_email_signoff(
    sender_name: str = DEFAULT_SENDER_NAME,
    sender_affiliation: str | None = DEFAULT_SENDER_AFFILIATION,
) -> str:
    normalized_name = sender_name.strip() or DEFAULT_SENDER_NAME
    normalized_affiliation = (sender_affiliation or "").strip()
    if normalized_affiliation:
        return f"Best,\n{normalized_name}\n{normalized_affiliation}"
    return f"Best,\n{normalized_name}"


def _render_email_body(
    message: str,
    sender_name: str = DEFAULT_SENDER_NAME,
    sender_affiliation: str | None = DEFAULT_SENDER_AFFILIATION,
) -> str:
    return f"{message.rstrip()}\n\n{_render_email_signoff(sender_name, sender_affiliation)}"


def build_payload(
    neglected_outreach: dict[str, Any],
    oncology_first_contact: dict[str, Any],
    antiviral_first_contact: dict[str, Any],
    kinase_outreach: dict[str, Any] | None = None,
    sender_name: str = DEFAULT_SENDER_NAME,
    sender_affiliation: str | None = DEFAULT_SENDER_AFFILIATION,
) -> dict[str, Any]:
    sender_name = sender_name.strip() or DEFAULT_SENDER_NAME
    sender_affiliation = (sender_affiliation or "").strip() or None
    neglected_ready = _ready_targets(neglected_outreach)
    antiviral_ready = _ready_targets(antiviral_first_contact)
    oncology_ready = bool(oncology_first_contact.get("summary", {}).get("export_ready", False))
    kinase_rows = _rows_by_track(kinase_outreach or {})
    m4k = kinase_rows.get("M4K_open_science", {})
    sgc = kinase_rows.get("SGC_dark_kinase", {})

    rows = [
        {
            "track_id": "DNDi_IPK",
            "track_label": "DNDi / Institut Pasteur Korea",
            "status": "ready_to_send" if len(neglected_ready) >= 2 else "awaiting_fill",
            "lead_targets": "; ".join(neglected_ready) if neglected_ready else "T. cruzi PDE ; Cruzain",
            "email_subject": "Chagas micro-validation packet: parasite PDE selectivity plus Cruzain artifact filtering",
            "email_body": _render_email_body(
                "Hello DNDi/IPK team,\n\n"
                "I’m reaching out with a compact Chagas micro-validation idea centered on two low-friction targets: T. cruzi PDE and Cruzain. "
                "The ask is intentionally small. For PDE, the first experiment is framed around parasite-versus-human PDE separation from day one. For Cruzain, the shortlist is already filtered around host cysteine-protease counterscreens and artifact control so the wet-lab is not handed a noisy protease hit list.\n\n"
                "If this looks rail-fit for DNDi/IPK, I can send a one-page brief for each target, the top-3 low-friction and top-3 novelty compounds, and the paired anti-target plan in a single attachment set. "
                "We also have Leishmania braziliensis DHODH ready as a follow-on neglected-enzyme expansion once the first Chagas packet is scoped.",
                sender_name=sender_name,
                sender_affiliation=sender_affiliation,
            ),
            "proposal_title": "DNDi/IPK neglected-disease micro-validation: T. cruzi PDE plus Cruzain",
            "proposal_summary": (
                "A two-target Chagas first-contact packet that combines a parasite-vs-human selectivity story for T. cruzi PDE with a false-positive-controlled Cruzain protease story, keeping the wet-lab ask limited to cheap recombinant assays and day-one counterscreens."
            ),
            "attachment_artifacts": "runs/wetlab_neglected_outreach_packet_current.md; runs/wetlab_neglected_first_contact_packets_current.md; runs/wetlab_target_brief_tcruzi_pde_current.md; runs/wetlab_target_brief_cruzain_current.md",
        },
        {
            "track_id": "M4K_open_science",
            "track_label": "M4K / rare-disease open-science kinase",
            "status": "ready_to_send" if str(m4k.get("status", "")) == "ready_for_partner_specific_export" else "awaiting_fill",
            "lead_targets": str(m4k.get("target_id", "ALK2")),
            "email_subject": "ALK2: bound repurposing + novelty packet for a fast mutant-aware validation pass",
            "email_body": _render_email_body(
                "Hello M4K team,\n\n"
                "I’m reaching out with a compact ALK2 validation idea that is already bound on both low-friction and novelty lanes. The first ask is intentionally narrow: a biochemical or DSF validation pass with mutant-versus-wild-type comparison and a close-kinase mini-panel, so the output is decision-grade rather than just positive or negative. We have kept the first readout cheap and interpretable, with deeper cell-engagement follow-up held back until the benchmark stack stays clean.\n\n"
                "The packet also carries a CNS-aware liability note and an ALK-family selectivity frame so it can be reviewed as an open-science co-development starting point rather than a broad kinase campaign. If useful, I can send the one-page brief, the bound shortlist, and the first-pass assay logic immediately.\n\n",
                sender_name=sender_name,
                sender_affiliation=sender_affiliation,
            ),
            "proposal_title": "Open-science ALK2 mutant-aware micro-validation packet",
            "proposal_summary": (
                "A rare-disease ALK2 first-contact packet with bound repurposing and novelty lanes, framed around mutant-aware biochemical or DSF validation, an ALK-family mini-panel, and a publication-friendly open-science co-development path."
            ),
            "attachment_artifacts": "runs/wetlab_kinase_outreach_packet_current.md; runs/wetlab_wave1_kinase_first_contact_packets_current.md; runs/wetlab_target_brief_alk2_current.md",
        },
        {
            "track_id": "SGC_dark_kinase",
            "track_label": "SGC / dark kinase structural-biology labs",
            "status": "ready_to_send" if str(sgc.get("status", "")) == "ready_for_partner_specific_export" else "awaiting_fill",
            "lead_targets": str(sgc.get("target_id", "STK17B (DRAK2)")),
            "email_subject": "STK17B: open-set benchmark packet for a P-loop-first validation pass",
            "email_body": _render_email_body(
                "Hello,\n\n"
                "I’m sharing a STK17B validation idea built around benchmark-first validation rather than generic dark-kinase exploration. The framing is simple: start from a published PKIS benchmark trio and the 11-series open probe frame, then test a compact novelty set against that open set with DSF or a straightforward biochemical assay and a neighborhood kinase mini-panel. The point is to ask whether the P-loop and conformational-dynamics ranking is adding signal inside a known benchmark frame.\n\n"
                "If that benchmark-first stack is of interest, I can send the one-page brief, the compact shortlist, and the benchmark/control logic immediately. The packet is already shaped for structural-biology or cell-engagement follow-up if the first pass stays clean.\n\n",
                sender_name=sender_name,
                sender_affiliation=sender_affiliation,
            ),
            "proposal_title": "Open-set benchmark STK17B P-loop validation packet",
            "proposal_summary": (
                "A dark-kinase STK17B first-contact packet that uses a published PKIS benchmark trio plus the 11-series open-probe frame, then asks for a low-friction DSF or biochemical validation pass against a compact novelty shortlist and neighborhood kinase mini-panel."
            ),
            "attachment_artifacts": "runs/wetlab_kinase_outreach_packet_current.md; runs/wetlab_wave1_kinase_first_contact_packets_current.md; runs/wetlab_target_brief_stk17b_current.md; runs/wetlab_stk17b_novelty_fill_map_current.md",
        },
        {
            "track_id": "oncology_condition_aware",
            "track_label": "Condition-aware oncology labs",
            "status": "ready_to_send" if oncology_ready else "awaiting_fill",
            "lead_targets": "CA IX",
            "email_subject": "CA IX acidic-buffer validation packet with built-in CA II / CA XII deselection",
            "email_body": _render_email_body(
                "Hello,\n\n"
                "I’m reaching out with a small condition-aware oncology packet built around CA IX under tumor-like acidic buffer. The core question is not generic carbonic-anhydrase inhibition. It is whether an assay-conditioned screen at acidic pH improves CA IX-biased triage while CA II and CA XII counterscreens run in the same first packet.\n\n"
                "The packet already includes three low-friction approved benchmark compounds, three literature-anchored novelty references, and an explicit acidic-arm versus neutral-arm buffer program with immediate deselection gates. If useful, I can send the one-page brief, the companion-panel logic, and the concise go/no-go criteria as the first attachment set.\n\n",
                sender_name=sender_name,
                sender_affiliation=sender_affiliation,
            ),
            "proposal_title": "Condition-aware CA IX validation under tumor-like acidic buffer",
            "proposal_summary": (
                "A pH-conditioned CA IX first-contact packet that couples acidic-buffer ranking with same-packet CA II and CA XII deselection, so the wet-lab can answer a sharper yes/no question than a flat carbonic-anhydrase screen."
            ),
            "attachment_artifacts": "runs/wetlab_oncology_first_contact_packet_current.md; runs/wetlab_target_brief_caix_current.md; runs/ca_ix_one_page_brief_current.md",
        },
        {
            "track_id": "READDI_Korea",
            "track_label": "READDI / Korea antiviral rail",
            "status": "ready_to_send" if len(antiviral_ready) >= 2 else "awaiting_fill",
            "lead_targets": "; ".join(antiviral_ready) if antiviral_ready else "SARS-CoV-2 Mpro ; SARS-CoV-2 PLpro",
            "email_subject": "Rapid antiviral micro-validation packet: paired Mpro and PLpro with host-liability counterscreens",
            "email_body": _render_email_body(
                "Hello READDI/Korea collaborators,\n\n"
                "I’m reaching out with a paired coronavirus protease validation idea built for fast micro-validation. Mpro is the low-friction proof rail with vendor-checked controls and a fast biochemical path. PLpro is the higher-selectivity companion rail, with host DUB counterscreens built in from the first pass instead of being deferred until after a shallow-pocket hit list appears.\n\n"
                "The intent is a small, high-clarity validation step: top-3 low-friction candidates, top-3 novelty candidates, explicit host-liability filters, and a quick yes/no decision on whether the dynamics-first triage is adding value. If helpful, I can send the paired first-contact packet, the one-page target briefs, and the current Mpro procurement sheet immediately.\n\n",
                sender_name=sender_name,
                sender_affiliation=sender_affiliation,
            ),
            "proposal_title": "READDI paired coronavirus protease micro-validation: Mpro plus PLpro",
            "proposal_summary": (
                "A paired antiviral first-contact packet that uses Mpro as the cheapest proof rail and PLpro as the shallow-pocket selectivity rail, with explicit host-protease and human-DUB counterscreens from the first experiment."
            ),
            "attachment_artifacts": "runs/wetlab_antiviral_first_contact_packets_current.md; runs/wetlab_target_brief_sarscov2_mpro_current.md; runs/wetlab_target_brief_sarscov2_plpro_current.md; runs/wetlab_mpro_vendor_cost_check_current.md",
        },
    ]

    summary = {
        "status": "wetlab_partner_first_contact_export_bundle_ready",
        "track_count": len(rows),
        "ready_to_send_count": sum(1 for row in rows if row["status"] == "ready_to_send"),
        "sender_name": sender_name,
        "sender_affiliation": sender_affiliation or "",
        "next_required_step": "Use these exported subject lines, email bodies, proposal titles, and attachment bundles for DNDi/IPK, M4K, SGC, oncology, and READDI first-contact outreach.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Partner First Contact Export Bundle",
        "",
        f"- status: `{s['status']}`",
        f"- track_count: `{s['track_count']}`",
        f"- ready_to_send_count: `{s['ready_to_send_count']}`",
        f"- sender_name: `{s['sender_name']}`",
        f"- sender_affiliation: `{s['sender_affiliation']}`",
        "",
    ]
    for row in payload["rows"]:
        lines.extend(
            [
                f"## {row['track_label']}",
                "",
                f"- track_id: `{row['track_id']}`",
                f"- status: `{row['status']}`",
                f"- lead_targets: `{row['lead_targets']}`",
                f"- email_subject: {row['email_subject']}",
                "",
                "### Email Body",
                "",
                "```text",
                row["email_body"],
                "```",
                "",
                f"- proposal_title: {row['proposal_title']}",
                f"- proposal_summary: {row['proposal_summary']}",
                f"- attachment_artifacts: `{row['attachment_artifacts']}`",
                "",
            ]
        )
    lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the outbound first-contact email and proposal text bundle.")
    parser.add_argument("--neglected-outreach-json", default=DEFAULT_NEGLECTED_OUTREACH_JSON)
    parser.add_argument("--oncology-first-contact-json", default=DEFAULT_ONCOLOGY_FIRST_CONTACT_JSON)
    parser.add_argument("--antiviral-first-contact-json", default=DEFAULT_ANTIVIRAL_FIRST_CONTACT_JSON)
    parser.add_argument("--kinase-outreach-json", default=DEFAULT_KINASE_OUTREACH_JSON)
    parser.add_argument("--sender-name", default=DEFAULT_SENDER_NAME)
    parser.add_argument("--sender-affiliation", default=DEFAULT_SENDER_AFFILIATION)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.neglected_outreach_json),
        _load_json(args.oncology_first_contact_json),
        _load_json(args.antiviral_first_contact_json),
        _load_json(args.kinase_outreach_json),
        args.sender_name,
        args.sender_affiliation,
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
