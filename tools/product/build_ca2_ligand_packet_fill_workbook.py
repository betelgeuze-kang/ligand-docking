#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
PRIMARY_TARGET = "CARBONIC_ANHYDRASE_2_ZN_BLIND"
DEFAULT_TEMPLATE_JSON = "config/external_validation_biorxiv_non_kinase_enzyme_ca2_v1_template.json"
PACKETS: Dict[str, Dict[str, str]] = {
    "core": {
        "reference": "config/ligand_binding_reference_blind_ca2_zn_v1.csv",
        "split": "config/ligand_eval_splits_blind_ca2_zn_v1.csv",
        "meta": "config/ligand_meta_blind_ca2_zn_v1.csv",
    },
    "ood": {
        "reference": "config/ligand_binding_reference_blind_ca2_zn_chembl50_v1.csv",
        "split": "config/ligand_eval_splits_blind_ca2_zn_chembl50_v1.csv",
        "meta": "config/ligand_meta_blind_ca2_zn_chembl50_v1.csv",
    },
}


def _resolve(path_str: str) -> Path:
    path = Path(str(path_str))
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_csv_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _contains_placeholder(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    upper = text.upper()
    return "PLACEHOLDER" in upper or "TODO" in upper or "TEMPLATE_" in upper


def _row_has_placeholder(row: Dict[str, str]) -> bool:
    return any(_contains_placeholder(value) for value in row.values())


def _bool_text(value: bool) -> str:
    return "yes" if value else "no"


def _load_packet_rows(packet_name: str, table_name: str) -> Tuple[Path, List[Dict[str, str]]]:
    path = _resolve(PACKETS[packet_name][table_name])
    _, rows = _read_csv_rows(path)
    return path, rows


def _select_reference_rows(rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    return [row for row in rows if str(row.get("target", "")).strip() == PRIMARY_TARGET]


def _select_split_rows(rows: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    return [row for row in rows if str(row.get("target", "")).strip() == PRIMARY_TARGET]


def _index_by_ligand_id(rows: Iterable[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    index: Dict[str, Dict[str, str]] = {}
    for row in rows:
        ligand_id = str(row.get("ligand_id", "")).strip()
        if ligand_id:
            index[ligand_id] = row
    return index


def _ligand_ids_for_packet(reference_rows: Dict[str, Dict[str, str]], split_rows: Dict[str, Dict[str, str]], meta_rows: Dict[str, Dict[str, str]]) -> List[str]:
    return sorted(set(reference_rows) | set(split_rows) | set(meta_rows))


def _next_action_for_row(packet_name: str, row: Dict[str, Any]) -> str:
    if row["fit_donor_carryover_candidate"]:
        return f"Decide whether this {packet_name} meta-only ligand belongs to the temporary fit-donor carryover set or should be dropped from the CA2 ledger."
    if not row["in_reference"]:
        return f"Add {packet_name} reference row and provenance for ligand_id."
    if row["reference_placeholder"]:
        return f"Replace {packet_name} placeholder reference values with curated CA2 evidence."
    if not row["in_meta"]:
        return f"Add {packet_name} ligand metadata row keyed by ligand_id."
    if row["meta_placeholder"]:
        return f"Replace {packet_name} placeholder smiles/property values."
    if not row["in_split"]:
        return f"Freeze {packet_name} eval role for ligand_id."
    if row["split_placeholder"]:
        return f"Replace {packet_name} placeholder split role with a frozen governance role."
    if row["target_mismatch"]:
        return f"Remove non-CA2 target leakage from {packet_name} packet rows."
    return f"No immediate blocker for {packet_name} ligand_id ledger row."


def _derive_packet_status(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "header_only"
    if any(row["target_mismatch"] for row in rows):
        return "mixed_target_template"
    if all(row["reference_placeholder"] or row["meta_placeholder"] or row["split_placeholder"] for row in rows):
        return "placeholder_only"
    if any(
        (not row["in_reference"]) or (not row["in_meta"]) or (not row["in_split"])
        for row in rows
    ):
        return "ledger_incomplete"
    if any(row["reference_placeholder"] or row["meta_placeholder"] or row["split_placeholder"] for row in rows):
        return "partially_curated"
    return "ready_for_policy_freeze"


def _build_workbook(template_json_path: Path) -> Dict[str, Any]:
    template_payload = _load_json(template_json_path)
    placeholder_policies = template_payload.get("placeholder_policies", {})
    fit_donor_target = str(placeholder_policies.get("fit_donor_target", "")).strip()
    packet_rows: List[Dict[str, Any]] = []
    packet_summaries: List[Dict[str, Any]] = []

    for packet_name in ("core", "ood"):
        _, ref_all = _load_packet_rows(packet_name, "reference")
        _, split_all = _load_packet_rows(packet_name, "split")
        _, meta_all = _load_packet_rows(packet_name, "meta")

        ref_rows = _index_by_ligand_id(_select_reference_rows(ref_all))
        split_rows = _index_by_ligand_id(_select_split_rows(split_all))
        meta_rows = _index_by_ligand_id(meta_all)
        ligand_ids = _ligand_ids_for_packet(ref_rows, split_rows, meta_rows)

        for ligand_id in ligand_ids:
            ref_row = ref_rows.get(ligand_id, {})
            split_row = split_rows.get(ligand_id, {})
            meta_row = meta_rows.get(ligand_id, {})
            row = {
                "packet": packet_name,
                "ligand_id": ligand_id,
                "in_reference": bool(ref_row),
                "in_split": bool(split_row),
                "in_meta": bool(meta_row),
                "reference_placeholder": _row_has_placeholder(ref_row),
                "split_placeholder": _row_has_placeholder(split_row),
                "meta_placeholder": _row_has_placeholder(meta_row),
                "reference_binding_kcal_mol": str(ref_row.get("reference_binding_kcal_mol", "")).strip(),
                "is_binder": str(ref_row.get("is_binder", "")).strip(),
                "source": str(ref_row.get("source", "")).strip(),
                "role": str(split_row.get("role", "")).strip(),
                "smiles": str(meta_row.get("smiles", "")).strip(),
                "scaffold": str(meta_row.get("scaffold", "")).strip(),
                "fit_donor_target": fit_donor_target,
                "fit_donor_carryover_candidate": bool(meta_row) and not ref_row and not split_row,
                "target_mismatch": any(
                    str(source_row.get("target", "")).strip() not in ("", PRIMARY_TARGET)
                    for source_row in (ref_row, split_row)
                    if source_row
                ),
            }
            row["next_action"] = _next_action_for_row(packet_name, row)
            packet_rows.append(row)

        packet_only_rows = [row for row in packet_rows if row["packet"] == packet_name]
        packet_summaries.append(
            {
                "packet": packet_name,
                "ligand_row_count": len(packet_only_rows),
                "reference_row_count": len(ref_rows),
                "split_row_count": len(split_rows),
                "meta_row_count": len(meta_rows),
                "placeholder_row_count": sum(
                    1
                    for row in packet_only_rows
                    if row["reference_placeholder"] or row["split_placeholder"] or row["meta_placeholder"]
                ),
                "fit_donor_carryover_candidate_count": sum(1 for row in packet_only_rows if row["fit_donor_carryover_candidate"]),
                "target_mismatch_row_count": sum(1 for row in packet_only_rows if row["target_mismatch"]),
                "status": _derive_packet_status(packet_only_rows),
            }
        )

    next_action_counts = Counter(row["next_action"] for row in packet_rows)
    summary = {
        "packet_count": len(packet_summaries),
        "ligand_row_count": len(packet_rows),
        "packets_ready_for_policy_freeze": sum(1 for row in packet_summaries if row["status"] == "ready_for_policy_freeze"),
        "packets_blocked": sum(1 for row in packet_summaries if row["status"] != "ready_for_policy_freeze"),
        "placeholder_row_count": sum(row["placeholder_row_count"] for row in packet_summaries),
        "fit_donor_carryover_candidate_count": sum(row["fit_donor_carryover_candidate_count"] for row in packet_summaries),
        "target_mismatch_row_count": sum(row["target_mismatch_row_count"] for row in packet_summaries),
        "most_common_next_action": next_action_counts.most_common(1)[0][0] if next_action_counts else "",
    }
    return {
        "target": PRIMARY_TARGET,
        "placeholder_policies": placeholder_policies,
        "packet_summaries": packet_summaries,
        "workbook_rows": packet_rows,
        "summary": summary,
    }


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "packet",
        "ligand_id",
        "in_reference",
        "in_split",
        "in_meta",
        "reference_placeholder",
        "split_placeholder",
        "meta_placeholder",
        "fit_donor_carryover_candidate",
        "target_mismatch",
        "reference_binding_kcal_mol",
        "is_binder",
        "source",
        "role",
        "smiles",
        "scaffold",
        "next_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            for key in (
                "in_reference",
                "in_split",
                "in_meta",
                "reference_placeholder",
                "split_placeholder",
                "meta_placeholder",
                "fit_donor_carryover_candidate",
                "target_mismatch",
            ):
                out[key] = _bool_text(bool(out[key]))
            writer.writerow({key: out.get(key, "") for key in fieldnames})


def _write_md(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# CA2 Ligand Packet Fill Workbook",
        "",
        f"- target: `{payload['target']}`",
        f"- packets: `{payload['summary']['packet_count']}`",
        f"- ligand rows: `{payload['summary']['ligand_row_count']}`",
        f"- packets ready for policy freeze: `{payload['summary']['packets_ready_for_policy_freeze']}`",
        f"- packets blocked: `{payload['summary']['packets_blocked']}`",
        f"- placeholder rows: `{payload['summary']['placeholder_row_count']}`",
        f"- fit-donor carryover candidates: `{payload['summary']['fit_donor_carryover_candidate_count']}`",
        f"- target mismatch rows: `{payload['summary']['target_mismatch_row_count']}`",
        "",
        "## Placeholder Policies",
        "",
        f"- `fit_donor_target`: `{payload['placeholder_policies'].get('fit_donor_target', '')}`",
        f"- `fit_donor_policy_state`: `{payload['placeholder_policies'].get('fit_donor_policy_state', '')}`",
        "",
        "## Packet Summary",
        "",
        "| packet | status | ligand rows | placeholders | carryover candidates | target mismatches | next move |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["packet_summaries"]:
        next_move = "Freeze policy" if row["status"] == "ready_for_policy_freeze" else "Curate ligand ledger"
        lines.append(
            f"| {row['packet']} | `{row['status']}` | {row['ligand_row_count']} | {row['placeholder_row_count']} | {row['fit_donor_carryover_candidate_count']} | {row['target_mismatch_row_count']} | {next_move} |"
        )
    lines.extend(
        [
            "",
            "## Most Common Next Action",
            "",
            f"- `{payload['summary']['most_common_next_action']}`",
            "",
            "## Ligand Workbook",
            "",
            "| packet | ligand_id | reference | split | meta | carryover | placeholders | target mismatch | next action |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["workbook_rows"]:
        placeholder_text = "/".join(
            name
            for name, flag in (
                ("ref", row["reference_placeholder"]),
                ("split", row["split_placeholder"]),
                ("meta", row["meta_placeholder"]),
            )
            if flag
        ) or "none"
        lines.append(
            "| {packet} | `{ligand_id}` | {ref} | {split} | {meta} | {carryover} | {placeholders} | {mismatch} | {next_action} |".format(
                packet=row["packet"],
                ligand_id=row["ligand_id"],
                ref=_bool_text(row["in_reference"]),
                split=_bool_text(row["in_split"]),
                meta=_bool_text(row["in_meta"]),
                carryover=_bool_text(row["fit_donor_carryover_candidate"]),
                placeholders=placeholder_text,
                mismatch=_bool_text(row["target_mismatch"]),
                next_action=row["next_action"],
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CA2 ligand packet fill workbook.")
    parser.add_argument(
        "--template-json",
        default=DEFAULT_TEMPLATE_JSON,
        help="CA2 family template JSON used to expose placeholder policy context.",
    )
    parser.add_argument(
        "--out-json",
        default="runs/ca2_ligand_packet_fill_workbook_current.json",
        help="JSON output path.",
    )
    parser.add_argument(
        "--out-csv",
        default="runs/ca2_ligand_packet_fill_workbook_current.csv",
        help="CSV workbook output path.",
    )
    parser.add_argument(
        "--out-md",
        default="runs/ca2_ligand_packet_fill_workbook_current.md",
        help="Markdown report output path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = _build_workbook(_resolve(args.template_json))
    _write_json(_resolve(args.out_json), payload)
    _write_csv(_resolve(args.out_csv), payload["workbook_rows"])
    _write_md(_resolve(args.out_md), payload)


if __name__ == "__main__":
    main()
