#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_QUEUE_JSON = "runs/transporter_seed_row_promotion_board_current.json"
DEFAULT_OUT_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_OUT_CSV = "runs/glut1_second_wave_source_confirmation_packet_current.csv"
DEFAULT_OUT_MD = "runs/glut1_second_wave_source_confirmation_packet_current.md"

CANONICAL_TARGET_GENE = "SLC2A1"
CANONICAL_TARGET_ALIAS = "GLUT1"
CANONICAL_TARGET_UNIPROT = "P11166"
CANONICAL_TARGET_CHEMBL = "CHEMBL2535"
SECOND_WAVE_STEPS = ("core_binder_01", "core_binder_02", "core_binder_03")
RT_KCAL_MOL_298K = 0.00198720425864083 * 298.15


def _dg_from_uM(value_uM: float) -> str:
    return f"{RT_KCAL_MOL_298K * math.log(value_uM * 1e-6):.4f}"

ROW_OVERRIDES: dict[str, dict[str, Any]] = {
    "core_binder_01": {
        "candidate_name": "cytochalasin B",
        "confirmation_scope": "direct_quantitative_binding_source_confirmation",
        "source_anchor": "PMID 1716731",
        "source_title": (
            "Differentiation of erythrocyte-(GLUT1), liver-(GLUT2), and adipocyte-type (GLUT4) "
            "glucose transporters by binding of the inhibitory ligands cytochalasin B..."
        ),
        "source_anchor_pmid": "1716731",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/1716731/",
        "supportive_pmids": "27078104",
        "evidence_signal": (
            "Confirmed human GLUT1 direct quantitative binding support (Kd 190 nM in human erythrocyte membranes) "
            "plus exact target-pair ChEMBL activity and inhibitor-bound human GLUT1 structural support; no kcal value recovered."
        ),
        "public_provenance_status": "exact_human_glut1_direct_binding_present_no_kcal",
        "public_provenance_signal": "direct_quantitative_binding_present_leave_kcal_blank",
        "assay_type_honesty": "direct_quantitative_binding_plus_structured_activity",
        "chembl_molecule_chembl_id": "CHEMBL411729",
        "chembl_target_chembl_id": CANONICAL_TARGET_CHEMBL,
        "chembl_activity_record_count": 2,
        "chembl_activity_url": (
            "https://www.ebi.ac.uk/chembl/api/data/activity.json?"
            "molecule_chembl_id=CHEMBL411729&target_chembl_id=CHEMBL2535"
        ),
        "representative_activity": "IC50=100 nM; IC50=4.1 uM",
        "direct_binding_measure": "Kd=190 nM",
        "review_bucket": "second_wave_direct_binding_review_only",
        "promotion_blocker": "no_claim_safe_glut1_binding_kcal_curated",
        "next_required_action": "confirm_direct_binding_support_keep_kcal_blank",
        "state_change_potential": "medium",
    },
    "core_binder_02": {
        "candidate_name": "WZB117",
        "confirmation_scope": "exact_target_pair_activity_source_confirmation",
        "source_anchor": "PMID 27836974",
        "source_title": (
            "WZB117 inhibits GLUT1-mediated sugar transport by binding reversibly at the "
            "exofacial sugar binding site."
        ),
        "source_anchor_pmid": "27836974",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/27836974/",
        "supportive_pmids": "22689530,24200808",
        "evidence_signal": (
            "Confirmed human erythrocyte GLUT1 functional inhibitor / transport blocker with apparent Ki(app)=6.2 uM "
            "for 3MG uptake plus exact target-pair ChEMBL activities (IC50 10.9 uM; >10 uM). This is not promoted "
            "as a clean direct binding constant."
        ),
        "public_provenance_status": "exact_human_glut1_activity_present_nonbinding",
        "public_provenance_signal": "apparent_functional_affinity_present_leave_direct_binding_kcal_blank",
        "assay_type_honesty": "human_functional_transport_inhibition_apparent_ki_not_direct_binding",
        "chembl_molecule_chembl_id": "CHEMBL3092944",
        "chembl_target_chembl_id": CANONICAL_TARGET_CHEMBL,
        "chembl_activity_record_count": 3,
        "chembl_activity_url": (
            "https://www.ebi.ac.uk/chembl/api/data/activity.json?"
            "molecule_chembl_id=CHEMBL3092944&target_chembl_id=CHEMBL2535"
        ),
        "representative_activity": "Ki(app)=6.2 uM for 3MG uptake; IC50=10.9 uM; IC50>10 uM",
        "apparent_affinity_measure": "Ki(app)=6.2 uM",
        "apparent_affinity_context": "human erythrocyte 3MG uptake inhibition; functional apparent Ki, not direct binding Kd/Ki",
        "apparent_delta_g_298k_kcal_mol": _dg_from_uM(6.2),
        "apparent_delta_g_method": "RTln(Ki_app_M) at 298.15 K; functional apparent affinity only",
        "direct_binding_measure": "",
        "review_bucket": "second_wave_exact_pair_activity_review_only",
        "promotion_blocker": "no_claim_safe_glut1_binding_kcal_curated",
        "next_required_action": "confirm_exact_target_pair_activity_keep_kcal_blank",
        "state_change_potential": "medium",
    },
    "core_binder_03": {
        "candidate_name": "STF-31",
        "confirmation_scope": "literature_direct_binding_claim_source_confirmation",
        "source_anchor": "PMID 21813754",
        "source_title": "Targeting GLUT1 and the Warburg effect in renal cell carcinoma by chemical synthetic lethality.",
        "source_anchor_pmid": "21813754",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/21813754/",
        "supportive_pmids": "25058389,29949049",
        "evidence_signal": (
            "Review-only human GLUT1/SLC2A1 functional anchor with direct-binding claim from docking/pull-down experiments; "
            "no curated public GLUT1 binding constant or kcal value recovered, and later literature adds NAMPT / dual-action caveats."
        ),
        "public_provenance_status": "human_glut1_functional_anchor_direct_binding_claim_structured_pair_absent",
        "public_provenance_signal": "literature_direct_binding_claim_leave_kcal_blank",
        "assay_type_honesty": "human_functional_anchor_with_direct_binding_claim_not_clean_biophysical_affinity",
        "chembl_molecule_chembl_id": "",
        "chembl_target_chembl_id": CANONICAL_TARGET_CHEMBL,
        "chembl_activity_record_count": 0,
        "chembl_activity_url": "",
        "representative_activity": "No curated public human GLUT1 Kd/Ki/IC50 recovered",
        "direct_binding_measure": "",
        "review_bucket": "second_wave_functional_anchor_review_only",
        "promotion_blocker": "no_structured_glut1_target_pair_activity_curated",
        "next_required_action": "confirm_functional_anchor_keep_review_only",
        "state_change_potential": "low",
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


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _queue_rows_by_step(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("packet_step")): dict(row)
        for row in payload.get("rows", []) or []
        if _text(row.get("target_id")).upper() == CANONICAL_TARGET_ALIAS and _text(row.get("packet_step"))
    }


def _acceptance_gate(packet_step: str, candidate_name: str, status: str, source_anchor: str) -> str:
    if status == "exact_human_glut1_direct_binding_present_no_kcal":
        return (
            f"Accept only if {packet_step} ({candidate_name}; {source_anchor}) stays a human GLUT1 direct quantitative binding row, "
            "while replacement_reference_binding_kcal_mol remains blank."
        )
    if status == "exact_human_glut1_activity_present_nonbinding":
        return (
            f"Accept only if {packet_step} ({candidate_name}; {source_anchor}) stays exact human GLUT1 functional activity / transport inhibition, "
            "without upgrading to direct binding or kcal."
        )
    return (
        f"Accept only if {packet_step} ({candidate_name}; {source_anchor}) remains a review-only human GLUT1 functional anchor, "
        "without claiming a curated public binding constant or kcal."
    )


def _rejection_gate(candidate_name: str, status: str) -> str:
    if status == "exact_human_glut1_direct_binding_present_no_kcal":
        return (
            f"Reject any wording that upgrades {candidate_name} into claim-safe kcal support or authoritative apply before kcal provenance is curated."
        )
    if status == "exact_human_glut1_activity_present_nonbinding":
        return (
            f"Reject unqualified '{candidate_name} binder' language; keep it at exact-target-pair functional inhibition unless direct binding is source-confirmed."
        )
    return (
        f"Reject any claim that {candidate_name} has a curated public human GLUT1 binding constant or kcal value, and keep NAMPT / dual-action caveats visible."
    )


def _review_note(packet_step: str, candidate_name: str, status: str) -> str:
    if status == "exact_human_glut1_direct_binding_present_no_kcal":
        return (
            f"Use {candidate_name} at {packet_step} as the strongest GLUT1 second-wave source-confirmation row, but still leave "
            "replacement_reference_binding_kcal_mol blank."
        )
    if status == "exact_human_glut1_activity_present_nonbinding":
        return (
            f"Use {candidate_name} at {packet_step} as an exact-target-pair functional inhibitor row only after the AQP1 first-wave binders are parked."
        )
    return (
        f"Keep {candidate_name} at {packet_step} review-only as a human GLUT1 functional anchor with direct-binding claim, not a clean biophysical affinity row."
    )


def build_payload(queue_payload: dict[str, Any]) -> dict[str, Any]:
    queue_by_step = _queue_rows_by_step(queue_payload)
    rows: list[dict[str, Any]] = []
    for rank, packet_step in enumerate(SECOND_WAVE_STEPS, start=1):
        queue_row = queue_by_step.get(packet_step, {})
        override = dict(ROW_OVERRIDES.get(packet_step, {}))
        if not (queue_row or override):
            continue

        candidate_name = _text(override.get("candidate_name")) or _text(queue_row.get("candidate_name"))
        status = _text(override.get("public_provenance_status"))
        source_anchor = _text(override.get("source_anchor")) or _text(queue_row.get("source_anchor"))
        source_anchor_pmid = _text(override.get("source_anchor_pmid"))
        source_title = _text(override.get("source_title"))
        source_url = _text(override.get("source_url")) or _text(queue_row.get("source_url"))
        review_bucket = _text(override.get("review_bucket")) or _text(queue_row.get("review_bucket"))
        promotion_blocker = _text(override.get("promotion_blocker")) or _text(queue_row.get("promotion_blocker"))

        rows.append(
            {
                "confirmation_rank": rank,
                "packet_step": packet_step,
                "candidate_name": candidate_name,
                "confirmation_scope": _text(override.get("confirmation_scope")),
                "canonical_target_gene": CANONICAL_TARGET_GENE,
                "canonical_target_alias": CANONICAL_TARGET_ALIAS,
                "canonical_target_uniprot": CANONICAL_TARGET_UNIPROT,
                "canonical_target_chembl_id": CANONICAL_TARGET_CHEMBL,
                "source_anchor": source_anchor,
                "source_anchor_pmid": source_anchor_pmid,
                "source_title": source_title,
                "source_url": source_url,
                "supportive_pmids": _text(override.get("supportive_pmids")),
                "evidence_signal": _text(override.get("evidence_signal")),
                "public_provenance_status": status,
                "public_provenance_signal": _text(override.get("public_provenance_signal")),
                "assay_type_honesty": _text(override.get("assay_type_honesty")),
                "chembl_molecule_chembl_id": _text(override.get("chembl_molecule_chembl_id")),
                "chembl_target_chembl_id": _text(override.get("chembl_target_chembl_id")),
                "chembl_activity_record_count": _int(override.get("chembl_activity_record_count")),
                "chembl_activity_url": _text(override.get("chembl_activity_url")),
                "representative_activity": _text(override.get("representative_activity")),
                "apparent_affinity_measure": _text(override.get("apparent_affinity_measure")),
                "apparent_affinity_context": _text(override.get("apparent_affinity_context")),
                "apparent_delta_g_298k_kcal_mol": _text(override.get("apparent_delta_g_298k_kcal_mol")),
                "apparent_delta_g_method": _text(override.get("apparent_delta_g_method")),
                "direct_binding_measure": _text(override.get("direct_binding_measure")),
                "claim_safe_binding_kcal_ready": "no",
                "review_bucket": review_bucket,
                "promotion_blocker": promotion_blocker,
                "next_required_action": _text(override.get("next_required_action")),
                "state_change_potential": _text(override.get("state_change_potential")),
                "queue_rank": _int(queue_row.get("queue_rank")),
                "acceptance_gate": _acceptance_gate(packet_step, candidate_name, status, source_anchor),
                "rejection_gate": _rejection_gate(candidate_name, status),
                "review_note": _review_note(packet_step, candidate_name, status),
                "supporting_artifacts": "runs/transporter_seed_row_promotion_board_current.md",
            }
        )

    direct_quantitative_binding_count = sum(
        1 for row in rows if row["public_provenance_status"] == "exact_human_glut1_direct_binding_present_no_kcal"
    )
    exact_target_pair_activity_count = sum(
        1
        for row in rows
        if row["public_provenance_status"]
        in {
            "exact_human_glut1_direct_binding_present_no_kcal",
            "exact_human_glut1_activity_present_nonbinding",
        }
    )
    structured_pair_absent_count = sum(
        1
        for row in rows
        if row["public_provenance_status"] == "human_glut1_functional_anchor_direct_binding_claim_structured_pair_absent"
    )
    apparent_functional_affinity_count = sum(1 for row in rows if row["apparent_affinity_measure"])

    summary = {
        "status": "glut1_second_wave_source_confirmation_packet_ready",
        "row_count": len(rows),
        "packet_artifact": "runs/glut1_second_wave_source_confirmation_packet_current.md",
        "primary_focus_ligand": _text(rows[0]["candidate_name"]) if rows else "",
        "primary_confirmation_target": _text(rows[0]["packet_step"]) if rows else "",
        "primary_anchor_pmid": _text(rows[0]["source_anchor_pmid"]) if rows else "",
        "second_wave_targets": ", ".join(row["packet_step"] for row in rows),
        "canonical_target_gene": CANONICAL_TARGET_GENE,
        "canonical_target_alias": CANONICAL_TARGET_ALIAS,
        "canonical_target_uniprot": CANONICAL_TARGET_UNIPROT,
        "canonical_target_chembl_id": CANONICAL_TARGET_CHEMBL,
        "direct_quantitative_binding_count": direct_quantitative_binding_count,
        "exact_target_pair_activity_count": exact_target_pair_activity_count,
        "structured_pair_absent_count": structured_pair_absent_count,
        "apparent_functional_affinity_count": apparent_functional_affinity_count,
        "source_anchor_pmid_count": sum(1 for row in rows if _text(row.get("source_anchor_pmid"))),
        "claim_safe_kcal_ready_count": 0,
        "next_required_step": (
            "Keep GLUT1 as second-wave until AQP1 core_binder_01 through core_binder_03 are parked. "
            "When widened, start with core_binder_01 (cytochalasin B) as the direct quantitative human GLUT1 binding row, "
            "then core_binder_02 (WZB117) as apparent functional affinity only, then core_binder_03 (STF-31) as the review-only "
            "human GLUT1 functional anchor with NAMPT / dual-action caveats. Leave direct-binding replacement_reference_binding_kcal_mol "
            "blank for WZB117/STF-31."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GLUT1 Second-Wave Source Confirmation Packet",
        "",
        f"- status: `{summary['status']}`",
        f"- row_count: `{summary['row_count']}`",
        f"- primary_focus_ligand: `{summary['primary_focus_ligand']}`",
        f"- primary_confirmation_target: `{summary['primary_confirmation_target']}`",
        f"- primary_anchor_pmid: `{summary['primary_anchor_pmid']}`",
        f"- second_wave_targets: `{summary['second_wave_targets']}`",
        f"- canonical_target_gene: `{summary['canonical_target_gene']}`",
        f"- canonical_target_alias: `{summary['canonical_target_alias']}`",
        f"- canonical_target_uniprot: `{summary['canonical_target_uniprot']}`",
        f"- canonical_target_chembl_id: `{summary['canonical_target_chembl_id']}`",
        f"- direct_quantitative_binding_count: `{summary['direct_quantitative_binding_count']}`",
        f"- exact_target_pair_activity_count: `{summary['exact_target_pair_activity_count']}`",
        f"- structured_pair_absent_count: `{summary['structured_pair_absent_count']}`",
        f"- apparent_functional_affinity_count: `{summary['apparent_functional_affinity_count']}`",
        f"- source_anchor_pmid_count: `{summary['source_anchor_pmid_count']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Rows",
        "",
        "| rank | packet_step | candidate_name | source_anchor_pmid | confirmation_scope | public_provenance_status | representative_activity | apparent_delta_g |",
        "| ---: | --- | --- | --- | --- | --- | --- | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['confirmation_rank']} | `{row['packet_step']}` | `{row['candidate_name']}` | "
            f"`{row['source_anchor_pmid']}` | `{row['confirmation_scope']}` | "
            f"`{row['public_provenance_status']}` | `{row['representative_activity'] or '-'}` |"
            f" `{row['apparent_delta_g_298k_kcal_mol'] or '-'}` |"
        )
    lines.extend(["", "## Reviewer Gates", ""])
    for row in payload["rows"]:
        lines.append(f"- `{row['candidate_name']}` accept: {row['acceptance_gate']}")
        lines.append(f"- `{row['candidate_name']}` reject: {row['rejection_gate']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a GLUT1 second-wave source confirmation packet for the current transporter commercialization queue."
    )
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.queue_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
