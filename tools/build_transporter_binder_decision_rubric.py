#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AQP1_SHEET_JSON = "runs/aqp1_binder_verdict_update_sheet_current.json"
DEFAULT_GLUT1_SHEET_JSON = "runs/glut1_binder_verdict_update_sheet_current.json"
DEFAULT_GLUT1_SOURCE_CONFIRMATION_JSON = "runs/glut1_second_wave_source_confirmation_packet_current.json"
DEFAULT_OUT_JSON = "runs/transporter_binder_decision_rubric_current.json"
DEFAULT_OUT_CSV = "runs/transporter_binder_decision_rubric_current.csv"
DEFAULT_OUT_MD = "runs/transporter_binder_decision_rubric_current.md"
GLUT1_SOURCE_CONFIRMATION_PACKET_MD = "runs/glut1_second_wave_source_confirmation_packet_current.md"
GLUT1_SOURCE_CONFIRMATION_LEAD = "cytochalasin B"


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


def _aqp1_rubric(candidate_name: str) -> tuple[str, str, str]:
    table = {
        "bacopaside II": (
            "Functional AQP1 water-channel inhibition is reproducible enough to keep as a first-wave review candidate.",
            "No direct human AQP1 target-binding packet row or claim-safe transporter provenance exists yet.",
            "Add transporter-specific packet provenance plus stronger target-specific binding or orthogonal transporter assay evidence.",
        ),
        "AqB013": (
            "Human RPE fluid-flux antagonism gives enough transporter-context signal to keep as first-wave review-only.",
            "Current support is still a tool-compound functional assay, not a direct quantitative target-binding row.",
            "Add a cleaner transporter-specific packet row with direct binding or stronger orthogonal target evidence.",
        ),
        "AqB011": (
            "AQP1 ion-conductance inhibition plus phenotype signal is enough to keep in first-wave review-only status.",
            "Ion-conductance modulation is still weaker than a direct human target-binding packet row.",
            "Add target-specific binding or transporter packet provenance that is stronger than the current conductance-only anchor.",
        ),
    }
    return table.get(
        candidate_name,
        (
            "Keep as review-only until transporter-specific evidence improves.",
            "Current transporter evidence is below authoritative apply standard.",
            "Add stronger transporter-specific packet evidence before any promotion.",
        ),
    )


def _glut1_source_confirmation_context(source_confirmation_packet: dict[str, Any] | None) -> dict[str, Any]:
    summary = dict((source_confirmation_packet or {}).get("summary", {}) or {})
    return {
        "packet_artifact": str(summary.get("packet_artifact", GLUT1_SOURCE_CONFIRMATION_PACKET_MD) or GLUT1_SOURCE_CONFIRMATION_PACKET_MD).strip(),
        "primary_focus_ligand": str(summary.get("primary_focus_ligand", GLUT1_SOURCE_CONFIRMATION_LEAD) or GLUT1_SOURCE_CONFIRMATION_LEAD).strip(),
        "row_count": int(summary.get("row_count", 0) or 0),
        "direct_quantitative_binding_count": int(summary.get("direct_quantitative_binding_count", 0) or 0),
        "exact_target_pair_activity_count": int(summary.get("exact_target_pair_activity_count", 0) or 0),
        "structured_pair_absent_count": int(summary.get("structured_pair_absent_count", 0) or 0),
    }


def _glut1_packet_scope_label(source_confirmation: dict[str, Any]) -> str:
    row_count = int(source_confirmation.get("row_count", 0) or 0)
    return f"{row_count}-row second-wave handoff" if row_count > 0 else "second-wave handoff"


def _glut1_rubric(candidate_name: str, source_confirmation: dict[str, Any]) -> tuple[str, str, str]:
    packet_artifact = str(source_confirmation.get("packet_artifact", GLUT1_SOURCE_CONFIRMATION_PACKET_MD) or GLUT1_SOURCE_CONFIRMATION_PACKET_MD).strip()
    packet_focus = str(source_confirmation.get("primary_focus_ligand", GLUT1_SOURCE_CONFIRMATION_LEAD) or GLUT1_SOURCE_CONFIRMATION_LEAD).strip()
    packet_scope_label = _glut1_packet_scope_label(source_confirmation)
    table = {
        "cytochalasin B": (
            "The GLUT1 second-wave source-confirmation packet keeps cytochalasin B as the lead review-only row because it is the packet's direct quantitative human GLUT1 binding lane.",
            "Even as the packet lead, cytochalasin B remains non-authoritative here because no claim-safe kcal row, donor-policy freeze, or apply-safe curated packet provenance is unlocked by the handoff.",
            f"Keep `{packet_artifact}` open as the {packet_scope_label}, preserve cytochalasin B as the primary focus ligand, and add a claim-safe curated transporter packet row before any promotion.",
        ),
        "WZB117": (
            f"WZB117 stays in `{packet_artifact}` as a review-only exact-target-pair functional lane behind the {packet_focus} packet lead, not as a direct-binding row.",
            "Exact-target-pair functional inhibition is still weaker than a curated human GLUT1 direct-binding row and is not an authoritative binder claim.",
            f"Keep `{packet_artifact}` open as the {packet_scope_label}, preserve {packet_focus} as the packet focus, and do not move WZB117 beyond the exact-target-pair functional lane without direct transporter-specific binding or stronger claim-safe packet provenance.",
        ),
        "STF-31": (
            f"STF-31 stays in `{packet_artifact}` as a review-only structured-pair caveat lane behind the {packet_focus} packet lead.",
            "The structured-pair gap plus NAMPT / dual-action caveats keep STF-31 below authoritative transporter apply and below a clean exact-target-pair row.",
            f"Keep `{packet_artifact}` open as the {packet_scope_label}, preserve {packet_focus} as the packet focus, and require curated human GLUT1 direct binding or exact-target-pair evidence before relaxing the STF-31 structured-pair caveat.",
        ),
    }
    return table.get(
        candidate_name,
        (
            "Keep as review-only until transporter-specific evidence improves.",
            "Current transporter evidence is below authoritative apply standard.",
            "Add stronger transporter-specific packet evidence before any promotion.",
        ),
    )


def _sheet_rows(
    family_label: str,
    sheet_payload: dict[str, Any],
    glut1_source_confirmation: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in sheet_payload.get("sheet_rows", []) or []:
        candidate_name = str(row.get("candidate_name", "")).strip()
        if family_label == "AQP1":
            keep_reason, blocker, next_evidence = _aqp1_rubric(candidate_name)
            packet_artifact = ""
            packet_focus = ""
            packet_row_count = 0
        else:
            keep_reason, blocker, next_evidence = _glut1_rubric(candidate_name, glut1_source_confirmation)
            packet_artifact = str(glut1_source_confirmation.get("packet_artifact", "")).strip()
            packet_focus = str(glut1_source_confirmation.get("primary_focus_ligand", "")).strip()
            packet_row_count = int(glut1_source_confirmation.get("row_count", 0) or 0)
        rows.append(
            {
                "target_id": family_label,
                "packet_step": str(row.get("packet_step", "")).strip(),
                "candidate_name": candidate_name,
                "current_recommended_verdict": str(row.get("current_recommended_verdict", "")).strip(),
                "source_confirmation_packet_artifact": packet_artifact,
                "source_confirmation_packet_primary_focus_ligand": packet_focus,
                "source_confirmation_packet_row_count": packet_row_count,
                "keep_review_only_reason": keep_reason,
                "authoritative_apply_blocker": blocker,
                "minimum_next_evidence": next_evidence,
            }
        )
    return rows


def build_payload(
    aqp1_sheet: dict[str, Any],
    glut1_sheet: dict[str, Any],
    glut1_source_confirmation_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    glut1_source_confirmation = _glut1_source_confirmation_context(glut1_source_confirmation_packet)
    packet_scope_label = _glut1_packet_scope_label(glut1_source_confirmation)
    rows = _sheet_rows("AQP1", aqp1_sheet, glut1_source_confirmation) + _sheet_rows(
        "GLUT1",
        glut1_sheet,
        glut1_source_confirmation,
    )
    summary = {
        "binder_slot_count": len(rows),
        "family_count": 2,
        "policy_status": "reviewer_state_only_blocker_closure",
        "glut1_second_wave_source_confirmation_packet_artifact": glut1_source_confirmation["packet_artifact"],
        "glut1_second_wave_source_confirmation_row_count": glut1_source_confirmation["row_count"],
        "glut1_second_wave_source_confirmation_primary_focus_ligand": glut1_source_confirmation["primary_focus_ligand"],
        "glut1_direct_quantitative_binding_count": glut1_source_confirmation["direct_quantitative_binding_count"],
        "glut1_exact_target_pair_activity_count": glut1_source_confirmation["exact_target_pair_activity_count"],
        "glut1_structured_pair_absent_count": glut1_source_confirmation["structured_pair_absent_count"],
        "next_required_step": (
            "Use this rubric during transporter blocker closure when reviewing binder update sheets. "
            "Keep every slot review-only unless stronger transporter-specific packet evidence exists. "
            f"For GLUT1, treat `{glut1_source_confirmation['packet_artifact']}` as a {packet_scope_label} with "
            f"{glut1_source_confirmation['primary_focus_ligand']} as the lead row, keep WZB117 in the exact-target-pair functional lane, "
            "keep STF-31 under a structured-pair caveat, and do not treat any of it as an authoritative-apply unlock."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Transporter Binder Decision Rubric",
        "",
        f"- binder_slot_count: `{payload['summary']['binder_slot_count']}`",
        f"- family_count: `{payload['summary']['family_count']}`",
        f"- policy_status: `{payload['summary']['policy_status']}`",
        f"- glut1_second_wave_source_confirmation_packet_artifact: `{payload['summary']['glut1_second_wave_source_confirmation_packet_artifact']}`",
        f"- glut1_second_wave_source_confirmation_row_count: `{payload['summary']['glut1_second_wave_source_confirmation_row_count']}`",
        f"- glut1_second_wave_source_confirmation_primary_focus_ligand: `{payload['summary']['glut1_second_wave_source_confirmation_primary_focus_ligand']}`",
        f"- glut1_direct_quantitative_binding_count: `{payload['summary']['glut1_direct_quantitative_binding_count']}`",
        f"- glut1_exact_target_pair_activity_count: `{payload['summary']['glut1_exact_target_pair_activity_count']}`",
        f"- glut1_structured_pair_absent_count: `{payload['summary']['glut1_structured_pair_absent_count']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Binder Rubric",
        "",
        "| target_id | packet_step | candidate_name | current_recommended_verdict | source_confirmation_packet_artifact | source_confirmation_packet_primary_focus_ligand | source_confirmation_packet_row_count | keep_review_only_reason | authoritative_apply_blocker | minimum_next_evidence |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['packet_step']}` | `{row['candidate_name']}` | `{row['current_recommended_verdict']}` | "
            f"`{row['source_confirmation_packet_artifact']}` | `{row['source_confirmation_packet_primary_focus_ligand']}` | {row['source_confirmation_packet_row_count']} | "
            f"{row['keep_review_only_reason']} | {row['authoritative_apply_blocker']} | {row['minimum_next_evidence']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a concise transporter binder decision rubric from current update sheets.")
    parser.add_argument("--aqp1-sheet-json", default=DEFAULT_AQP1_SHEET_JSON)
    parser.add_argument("--glut1-sheet-json", default=DEFAULT_GLUT1_SHEET_JSON)
    parser.add_argument("--glut1-source-confirmation-json", default=DEFAULT_GLUT1_SOURCE_CONFIRMATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.aqp1_sheet_json),
        _load_json(args.glut1_sheet_json),
        _load_json(args.glut1_source_confirmation_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
