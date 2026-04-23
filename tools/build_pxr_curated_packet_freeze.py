#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TARGET = "PXR_NR1I2_BLIND"
DEFAULT_WORKBOOK_CSV = "runs/pxr_packet_replacement_workbook_current.csv"
DEFAULT_PENDING_DISPOSITION_JSON = "runs/pxr_pending_row_disposition_current.json"
DEFAULT_OUT_JSON = "runs/pxr_curated_packet_freeze_current.json"
DEFAULT_OUT_CSV = "runs/pxr_curated_packet_freeze_current.csv"
DEFAULT_OUT_MD = "runs/pxr_curated_packet_freeze_current.md"

FREEZE_ARTIFACTS = {
    "core": {
        "reference_csv": "runs/pxr_core_reference_freeze_current.csv",
        "eval_split_csv": "runs/pxr_core_eval_splits_freeze_current.csv",
        "ligand_meta_csv": "runs/pxr_core_ligand_meta_freeze_current.csv",
    },
    "ood": {
        "reference_csv": "runs/pxr_ood_reference_freeze_current.csv",
        "eval_split_csv": "runs/pxr_ood_eval_splits_freeze_current.csv",
        "ligand_meta_csv": "runs/pxr_ood_ligand_meta_freeze_current.csv",
    },
}

REFERENCE_HEADERS = ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"]
SPLIT_HEADERS = ["target", "ligand_id", "role"]
META_HEADERS = ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"]


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


def _read_csv(path_like: str) -> list[dict[str, str]]:
    with _resolve(path_like).open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _contains_placeholder(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    return "todo" in text or "placeholder" in text or "_pending" in text


def _source_evidence_kind(source: str) -> str:
    text = str(source or "").strip()
    if not text:
        return "missing"
    if text.startswith("chembl_direct_binding::"):
        return "direct_binding"
    if text.startswith("chembl_activity_proxy::") or text.startswith("chembl_activity::"):
        return "activity_proxy"
    if text.startswith("pubchem_name_resolve_pending::"):
        return "pending_resolution"
    return "other"


def _role_bucket(role: str) -> str:
    text = str(role or "").strip()
    if text == "fit":
        return "fit"
    if text.endswith("_eval"):
        return "eval"
    return "other"


def _keyed_pending_disposition(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    return {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }


def _row_is_freezeable(row: dict[str, str]) -> bool:
    if str(row.get("row_ready_for_apply", "")).strip().lower() != "yes":
        return False
    if str(row.get("required_missing_fields", "")).strip():
        return False
    required_fields = [
        "replacement_ligand_id",
        "replacement_reference_binding_kcal_mol",
        "replacement_source",
        "replacement_role",
        "replacement_smiles",
        "replacement_scaffold",
    ]
    for field in required_fields:
        if not str(row.get(field, "")).strip():
            return False
        if _contains_placeholder(row.get(field, "")):
            return False
    return True


def _reference_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "target": TARGET,
        "ligand_id": str(row.get("replacement_ligand_id", "")).strip(),
        "reference_binding_kcal_mol": str(row.get("replacement_reference_binding_kcal_mol", "")).strip(),
        "is_binder": str(row.get("replacement_is_binder", "")).strip(),
        "source": str(row.get("replacement_source", "")).strip(),
    }


def _split_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "target": TARGET,
        "ligand_id": str(row.get("replacement_ligand_id", "")).strip(),
        "role": str(row.get("replacement_role", "")).strip(),
    }


def _meta_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "ligand_id": str(row.get("replacement_ligand_id", "")).strip(),
        "smiles": str(row.get("replacement_smiles", "")).strip(),
        "molecular_weight": str(row.get("replacement_molecular_weight", "")).strip(),
        "logp": str(row.get("replacement_logp", "")).strip(),
        "h_donors": str(row.get("replacement_h_donors", "")).strip(),
        "h_acceptors": str(row.get("replacement_h_acceptors", "")).strip(),
        "rot_bonds": str(row.get("replacement_rot_bonds", "")).strip(),
        "scaffold": str(row.get("replacement_scaffold", "")).strip(),
    }


def build_payload(
    workbook_rows: list[dict[str, str]],
    pending_disposition_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    disposition_by_step = _keyed_pending_disposition(pending_disposition_payload)
    packet_summaries: list[dict[str, Any]] = []
    freeze_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []

    for packet in ("core", "ood"):
        packet_rows = [dict(row) for row in workbook_rows if str(row.get("packet", "")).strip() == packet]
        ready_rows = [row for row in packet_rows if _row_is_freezeable(row)]
        blocked_packet_rows = [row for row in packet_rows if row not in ready_rows]

        ready_binder_count = sum(1 for row in ready_rows if str(row.get("replacement_is_binder", "")).strip() == "1")
        ready_non_binder_count = sum(1 for row in ready_rows if str(row.get("replacement_is_binder", "")).strip() == "0")
        ready_fit_count = sum(1 for row in ready_rows if _role_bucket(row.get("replacement_role", "")) == "fit")
        ready_eval_count = sum(1 for row in ready_rows if _role_bucket(row.get("replacement_role", "")) == "eval")
        evidence_counter = Counter(_source_evidence_kind(str(row.get("replacement_source", "")).strip()) for row in ready_rows)

        packet_summary = {
            "packet": packet,
            "workbook_row_count": len(packet_rows),
            "ready_row_count": len(ready_rows),
            "blocked_row_count": len(blocked_packet_rows),
            "ready_binder_count": ready_binder_count,
            "ready_non_binder_count": ready_non_binder_count,
            "ready_fit_row_count": ready_fit_count,
            "ready_eval_row_count": ready_eval_count,
            "direct_binding_ready_row_count": int(evidence_counter.get("direct_binding", 0)),
            "activity_proxy_ready_row_count": int(evidence_counter.get("activity_proxy", 0)),
            "partial_curated_freeze": bool(ready_rows) and len(ready_rows) < len(packet_rows),
            "full_packet_frozen": bool(packet_rows) and len(ready_rows) == len(packet_rows),
            "claim_ready": bool(packet_rows)
            and len(ready_rows) == len(packet_rows)
            and ready_fit_count > 0
            and ready_eval_count > 0
            and ready_non_binder_count > 0,
            "reference_csv": FREEZE_ARTIFACTS[packet]["reference_csv"],
            "eval_split_csv": FREEZE_ARTIFACTS[packet]["eval_split_csv"],
            "ligand_meta_csv": FREEZE_ARTIFACTS[packet]["ligand_meta_csv"],
            "next_required_step": (
                "Packet is fully frozen from the reviewed workbook."
                if packet_rows and len(ready_rows) == len(packet_rows)
                else (
                    f"Keep the frozen {len(ready_rows)} reviewed rows, then resolve the remaining {len(blocked_packet_rows)} {packet} workbook rows honestly."
                    if ready_rows
                    else f"Freeze the first reviewed {packet} workbook row before treating the packet as partially curated."
                )
            ),
        }
        packet_summaries.append(packet_summary)

        for row in ready_rows:
            source = str(row.get("replacement_source", "")).strip()
            evidence_kind = _source_evidence_kind(source)
            freeze_rows.append(
                {
                    "packet": packet,
                    "packet_step": str(row.get("packet_step", "")).strip(),
                    "replacement_ligand_id": str(row.get("replacement_ligand_id", "")).strip(),
                    "replacement_role": str(row.get("replacement_role", "")).strip(),
                    "replacement_is_binder": str(row.get("replacement_is_binder", "")).strip(),
                    "replacement_reference_binding_kcal_mol": str(row.get("replacement_reference_binding_kcal_mol", "")).strip(),
                    "replacement_source": source,
                    "source_evidence_kind": evidence_kind,
                    "freeze_status": "frozen_ready_row",
                    "provenance_honesty_note": (
                        "direct human PXR binding provenance"
                        if evidence_kind == "direct_binding"
                        else "human PXR activity-derived proxy kept explicit in source"
                        if evidence_kind == "activity_proxy"
                        else "non-standard provenance string"
                    ),
                }
            )

        for row in blocked_packet_rows:
            step = str(row.get("packet_step", "")).strip()
            disposition = disposition_by_step.get(step, {})
            blocked_rows.append(
                {
                    "packet": packet,
                    "packet_step": step,
                    "replacement_ligand_id": str(row.get("replacement_ligand_id", "")).strip(),
                    "replacement_role": str(row.get("replacement_role", "")).strip(),
                    "replacement_is_binder": str(row.get("replacement_is_binder", "")).strip(),
                    "required_missing_fields": str(row.get("required_missing_fields", "")).strip(),
                    "policy_bucket": str(disposition.get("disposition", "")).strip(),
                    "promotion_blocker": str(disposition.get("promotion_blocker", "")).strip(),
                    "next_required_action": str(
                        disposition.get("next_required_action", "") or row.get("notes", "")
                    ).strip(),
                }
            )

    ready_counter = Counter(row["packet"] for row in freeze_rows)
    blocked_counter = Counter(row["packet"] for row in blocked_rows)
    evidence_counter = Counter(row["source_evidence_kind"] for row in freeze_rows)

    summary = {
        "family": "pxr",
        "target": TARGET,
        "workbook_row_count": len(workbook_rows),
        "ready_row_count": len(freeze_rows),
        "blocked_row_count": len(blocked_rows),
        "packet_count": len(packet_summaries),
        "partial_packet_count": sum(1 for row in packet_summaries if row["partial_curated_freeze"]),
        "full_packet_count": sum(1 for row in packet_summaries if row["full_packet_frozen"]),
        "claim_ready_packet_count": sum(1 for row in packet_summaries if row["claim_ready"]),
        "core_ready_row_count": int(ready_counter.get("core", 0)),
        "core_blocked_row_count": int(blocked_counter.get("core", 0)),
        "ood_ready_row_count": int(ready_counter.get("ood", 0)),
        "ood_blocked_row_count": int(blocked_counter.get("ood", 0)),
        "direct_binding_ready_row_count": int(evidence_counter.get("direct_binding", 0)),
        "activity_proxy_ready_row_count": int(evidence_counter.get("activity_proxy", 0)),
        "partial_claim_support_ready": bool(freeze_rows),
        "claim_ready": all(bool(row["claim_ready"]) for row in packet_summaries) if packet_summaries else False,
        "next_required_step": (
            "Use the frozen reviewed subset as an honest partial-authoritative packet input, but keep PXR non-runnable until the remaining blocked rows are either frozen or explicitly left out of scope."
            if freeze_rows and blocked_rows
            else "Freeze the first reviewed workbook rows before treating the PXR packet as partially authoritative."
            if not freeze_rows
            else "Both PXR packets are fully frozen from the reviewed workbook."
        ),
    }
    return {
        "summary": summary,
        "packet_summaries": packet_summaries,
        "freeze_rows": freeze_rows,
        "blocked_rows": blocked_rows,
        "freeze_artifacts": FREEZE_ARTIFACTS,
    }


def _write_csv_with_headers(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})


def _write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "packet",
        "packet_step",
        "replacement_ligand_id",
        "replacement_role",
        "replacement_is_binder",
        "replacement_reference_binding_kcal_mol",
        "replacement_source",
        "source_evidence_kind",
        "freeze_status",
        "provenance_honesty_note",
    ]
    _write_csv_with_headers(path, headers, rows)


def _write_freeze_artifacts(payload: dict[str, Any]) -> None:
    rows_by_packet = {
        packet: [row for row in payload.get("freeze_rows", []) if row.get("packet") == packet]
        for packet in ("core", "ood")
    }
    for packet, rows in rows_by_packet.items():
        _write_csv_with_headers(
            _resolve(FREEZE_ARTIFACTS[packet]["reference_csv"]),
            REFERENCE_HEADERS,
            [
                _reference_row(
                    {
                        "replacement_ligand_id": row.get("replacement_ligand_id", ""),
                        "replacement_reference_binding_kcal_mol": row.get("replacement_reference_binding_kcal_mol", ""),
                        "replacement_is_binder": row.get("replacement_is_binder", ""),
                        "replacement_source": row.get("replacement_source", ""),
                    }
                )
                for row in rows
            ],
        )
        _write_csv_with_headers(
            _resolve(FREEZE_ARTIFACTS[packet]["eval_split_csv"]),
            SPLIT_HEADERS,
            [
                _split_row(
                    {
                        "replacement_ligand_id": row.get("replacement_ligand_id", ""),
                        "replacement_role": row.get("replacement_role", ""),
                    }
                )
                for row in rows
            ],
        )
        workbook_meta_rows = {
            str(row.get("packet_step", "")).strip(): row
            for row in payload.get("freeze_rows", [])
            if str(row.get("packet", "")).strip() == packet
        }
        _write_csv_with_headers(
            _resolve(FREEZE_ARTIFACTS[packet]["ligand_meta_csv"]),
            META_HEADERS,
            [
                _meta_row(
                    {
                        "replacement_ligand_id": step_row.get("replacement_ligand_id", ""),
                        "replacement_smiles": original_row.get("replacement_smiles", ""),
                        "replacement_molecular_weight": original_row.get("replacement_molecular_weight", ""),
                        "replacement_logp": original_row.get("replacement_logp", ""),
                        "replacement_h_donors": original_row.get("replacement_h_donors", ""),
                        "replacement_h_acceptors": original_row.get("replacement_h_acceptors", ""),
                        "replacement_rot_bonds": original_row.get("replacement_rot_bonds", ""),
                        "replacement_scaffold": original_row.get("replacement_scaffold", ""),
                    }
                )
                for step_row, original_row in (
                    (
                        row,
                        workbook_meta_rows.get(str(row.get("packet_step", "")).strip(), {}),
                    )
                    for row in payload.get("freeze_rows", [])
                    if str(row.get("packet", "")).strip() == packet
                )
            ],
        )


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# PXR Curated Packet Freeze",
        "",
        f"- family: `{s['family']}`",
        f"- target: `{s['target']}`",
        f"- workbook_row_count: `{s['workbook_row_count']}`",
        f"- ready_row_count: `{s['ready_row_count']}`",
        f"- blocked_row_count: `{s['blocked_row_count']}`",
        f"- partial_packet_count: `{s['partial_packet_count']}`",
        f"- full_packet_count: `{s['full_packet_count']}`",
        f"- direct_binding_ready_row_count: `{s['direct_binding_ready_row_count']}`",
        f"- activity_proxy_ready_row_count: `{s['activity_proxy_ready_row_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Packet Summary",
        "",
        "| packet | workbook_rows | ready_rows | blocked_rows | fit_ready | eval_ready | non_binder_ready | claim_ready |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["packet_summaries"]:
        lines.append(
            f"| {row['packet']} | {row['workbook_row_count']} | {row['ready_row_count']} | {row['blocked_row_count']} | "
            f"{row['ready_fit_row_count']} | {row['ready_eval_row_count']} | {row['ready_non_binder_count']} | `{row['claim_ready']}` |"
        )
    lines.extend(
        [
            "",
            "## Frozen Rows",
            "",
            "| packet_step | ligand | role | binder | source_evidence_kind | reference_binding_kcal_mol |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["freeze_rows"]:
        lines.append(
            f"| `{row['packet_step']}` | `{row['replacement_ligand_id']}` | `{row['replacement_role']}` | "
            f"`{row['replacement_is_binder']}` | `{row['source_evidence_kind']}` | `{row['replacement_reference_binding_kcal_mol']}` |"
        )
    lines.extend(
        [
            "",
            "## Blocked Rows",
            "",
            "| packet_step | ligand | required_missing_fields | policy_bucket | promotion_blocker |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["blocked_rows"]:
        lines.append(
            f"| `{row['packet_step']}` | `{row['replacement_ligand_id']}` | `{row['required_missing_fields']}` | "
            f"`{row['policy_bucket']}` | `{row['promotion_blocker']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze the reviewed PXR workbook rows that are already structurally/provenance complete.")
    parser.add_argument("--workbook-csv", default=DEFAULT_WORKBOOK_CSV)
    parser.add_argument("--pending-disposition-json", default=DEFAULT_PENDING_DISPOSITION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workbook_rows = _read_csv(args.workbook_csv)
    pending_disposition_payload = (
        _load_json(args.pending_disposition_json)
        if str(args.pending_disposition_json).strip() and _resolve(args.pending_disposition_json).exists()
        else {}
    )
    workbook_index = {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in workbook_rows
        if str(row.get("packet_step", "")).strip()
    }
    payload = build_payload(workbook_rows, pending_disposition_payload)
    # Copy the full workbook meta fields into the payload rows before writing the packet CSVs.
    payload["freeze_rows"] = [
        {**workbook_index.get(str(row.get("packet_step", "")).strip(), {}), **row}
        for row in payload.get("freeze_rows", [])
    ]

    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_summary_csv(out_csv, payload["freeze_rows"])
    _write_freeze_artifacts(payload)
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
