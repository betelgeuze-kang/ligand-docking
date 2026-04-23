#!/usr/bin/env python3
from __future__ import annotations

import copy
import csv
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRIMARY_TARGET = "CARBONIC_ANHYDRASE_2_ZN_BLIND"

PACKET_TABLE_PATHS: dict[str, dict[str, str]] = {
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

REFERENCE_FIELDS = ["target", "ligand_id", "reference_binding_kcal_mol", "is_binder", "source"]
SPLIT_FIELDS = ["target", "ligand_id", "role"]
META_FIELDS = ["ligand_id", "smiles", "molecular_weight", "logp", "h_donors", "h_acceptors", "rot_bonds", "scaffold"]
REQUIRED_WORKBOOK_FIELDS = [
    "replacement_ligand_id",
    "replacement_reference_binding_kcal_mol",
    "replacement_source",
    "replacement_smiles",
    "replacement_scaffold",
]
TABLE_APPLY_FLAGS = {
    "reference": "apply_reference_row",
    "split": "apply_split_row",
    "meta": "apply_meta_row",
}


def resolve_path(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def read_csv_rows(path_like: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    path = resolve_path(path_like)
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return fieldnames, rows


def write_csv_rows(path_like: str | Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path = resolve_path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _is_yes(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes", "y"}


def contains_placeholder(value: Any) -> bool:
    text = _text(value).lower()
    if not text:
        return False
    return "placeholder" in text or "todo" in text or "template_" in text


def row_has_placeholder(row: dict[str, Any]) -> bool:
    return any(contains_placeholder(value) for value in row.values())


def workbook_missing_fields(row: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_WORKBOOK_FIELDS if not _text(row.get(field, ""))]


def expected_rows_from_workbook(row: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {
        "reference": {
            "target": _text(row.get("target")) or PRIMARY_TARGET,
            "ligand_id": _text(row.get("replacement_ligand_id")),
            "reference_binding_kcal_mol": _text(row.get("replacement_reference_binding_kcal_mol")),
            "is_binder": _text(row.get("replacement_is_binder")),
            "source": _text(row.get("replacement_source")),
        },
        "split": {
            "target": _text(row.get("target")) or PRIMARY_TARGET,
            "ligand_id": _text(row.get("replacement_ligand_id")),
            "role": _text(row.get("replacement_role")),
        },
        "meta": {
            "ligand_id": _text(row.get("replacement_ligand_id")),
            "smiles": _text(row.get("replacement_smiles")),
            "molecular_weight": _text(row.get("replacement_molecular_weight")),
            "logp": _text(row.get("replacement_logp")),
            "h_donors": _text(row.get("replacement_h_donors")),
            "h_acceptors": _text(row.get("replacement_h_acceptors")),
            "rot_bonds": _text(row.get("replacement_rot_bonds")),
            "scaffold": _text(row.get("replacement_scaffold")),
        },
    }


def load_packet_tables(packet_paths: dict[str, dict[str, str]] | None = None) -> dict[str, dict[str, Any]]:
    packet_paths = packet_paths or PACKET_TABLE_PATHS
    tables: dict[str, dict[str, Any]] = {}
    for packet, table_map in packet_paths.items():
        tables[packet] = {}
        for table_name, relpath in table_map.items():
            fieldnames, rows = read_csv_rows(relpath)
            tables[packet][table_name] = {
                "path": str(relpath),
                "fieldnames": fieldnames,
                "rows": rows,
            }
    return tables


def _match_row(row: dict[str, str], ligand_id: str, *, target_required: str | None) -> bool:
    if target_required is not None and _text(row.get("target")) != target_required:
        return False
    return _text(row.get("ligand_id")) == ligand_id


def _find_row(rows: list[dict[str, str]], ligand_id: str, *, target_required: str | None) -> tuple[int | None, dict[str, str] | None]:
    for idx, row in enumerate(rows):
        if _match_row(row, ligand_id, target_required=target_required):
            return idx, row
    return None, None


def _row_matches_expected(actual: dict[str, str] | None, expected: dict[str, str], fields: list[str]) -> bool:
    if not actual:
        return False
    return all(_text(actual.get(field)) == _text(expected.get(field)) for field in fields)


def _classify_slot(
    rows: list[dict[str, str]],
    *,
    current_ligand_id: str,
    replacement_ligand_id: str,
    expected: dict[str, str],
    fields: list[str],
    target_required: str | None,
) -> dict[str, Any]:
    current_idx, current_row = _find_row(rows, current_ligand_id, target_required=target_required)
    replacement_idx, replacement_row = _find_row(rows, replacement_ligand_id, target_required=target_required)
    applied = _row_matches_expected(replacement_row, expected, fields)
    if applied:
        slot_action = "applied"
    elif replacement_row:
        slot_action = "update_existing_replacement"
    elif current_row:
        slot_action = "replace_current"
    else:
        slot_action = "append_missing"
    return {
        "current_index": current_idx,
        "current_exists": current_row is not None,
        "replacement_index": replacement_idx,
        "replacement_exists": replacement_row is not None,
        "applied": applied,
        "slot_action": slot_action,
        "current_row_has_placeholder": row_has_placeholder(current_row or {}),
        "replacement_row_has_placeholder": row_has_placeholder(replacement_row or {}),
    }


def classify_workbook_row(row: dict[str, Any], packet_tables: dict[str, dict[str, Any]]) -> dict[str, Any]:
    packet = _text(row.get("packet"))
    current_ligand_id = _text(row.get("current_ligand_id"))
    replacement_ligand_id = _text(row.get("replacement_ligand_id"))
    missing_fields = workbook_missing_fields(row)
    row_ready = not missing_fields
    packet_bundle = packet_tables.get(packet, {})
    expected_rows = expected_rows_from_workbook(row)

    reference_state = _classify_slot(
        packet_bundle.get("reference", {}).get("rows", []),
        current_ligand_id=current_ligand_id,
        replacement_ligand_id=replacement_ligand_id,
        expected=expected_rows["reference"],
        fields=REFERENCE_FIELDS,
        target_required=PRIMARY_TARGET,
    )
    split_state = _classify_slot(
        packet_bundle.get("split", {}).get("rows", []),
        current_ligand_id=current_ligand_id,
        replacement_ligand_id=replacement_ligand_id,
        expected=expected_rows["split"],
        fields=SPLIT_FIELDS,
        target_required=PRIMARY_TARGET,
    )
    meta_state = _classify_slot(
        packet_bundle.get("meta", {}).get("rows", []),
        current_ligand_id=current_ligand_id,
        replacement_ligand_id=replacement_ligand_id,
        expected=expected_rows["meta"],
        fields=META_FIELDS,
        target_required=None,
    )
    requested_states = {
        "reference": reference_state,
        "split": split_state,
        "meta": meta_state,
    }
    requested_tables = [table for table, flag in TABLE_APPLY_FLAGS.items() if _is_yes(row.get(flag, "yes"))]
    row_applied = row_ready and all(requested_states[table]["applied"] for table in requested_tables)
    freeze_pending = row_ready and not row_applied
    return {
        **dict(row),
        "missing_field_count": len(missing_fields),
        "missing_fields": ",".join(missing_fields),
        "row_ready_for_apply": "yes" if row_ready else "no",
        "row_applied_in_config": "yes" if row_applied else "no",
        "row_freeze_pending": "yes" if freeze_pending else "no",
        "reference_slot_action": reference_state["slot_action"],
        "split_slot_action": split_state["slot_action"],
        "meta_slot_action": meta_state["slot_action"],
        "reference_applied": "yes" if reference_state["applied"] else "no",
        "split_applied": "yes" if split_state["applied"] else "no",
        "meta_applied": "yes" if meta_state["applied"] else "no",
    }


def _upsert_row(
    rows: list[dict[str, str]],
    *,
    current_ligand_id: str,
    replacement_ligand_id: str,
    expected: dict[str, str],
    fields: list[str],
    target_required: str | None,
) -> str:
    replacement_idx, replacement_row = _find_row(rows, replacement_ligand_id, target_required=target_required)
    if replacement_row:
        if not _row_matches_expected(replacement_row, expected, fields):
            rows[replacement_idx] = {**replacement_row, **expected}
            return "updated_existing_replacement"
        return "already_applied"

    current_idx, current_row = _find_row(rows, current_ligand_id, target_required=target_required)
    if current_row:
        rows[current_idx] = {**current_row, **expected}
        return "replaced_current"

    rows.append(dict(expected))
    return "appended"


def materialize_ready_workbook_rows(
    workbook_rows: list[dict[str, Any]],
    packet_tables: dict[str, dict[str, Any]] | None = None,
    *,
    apply_changes: bool = False,
) -> dict[str, Any]:
    packet_tables = copy.deepcopy(packet_tables or load_packet_tables())
    materialized_rows: list[dict[str, Any]] = []
    slot_action_counter: Counter[str] = Counter()

    for workbook_row in workbook_rows:
        classified = classify_workbook_row(workbook_row, packet_tables)
        if classified["row_ready_for_apply"] != "yes":
            continue
        packet = _text(classified.get("packet"))
        bundle = packet_tables.get(packet)
        if not bundle:
            continue
        expected = expected_rows_from_workbook(classified)
        current_ligand_id = _text(classified.get("current_ligand_id"))
        replacement_ligand_id = _text(classified.get("replacement_ligand_id"))
        row_actions: dict[str, str] = {}
        for table_name, fields in (
            ("reference", REFERENCE_FIELDS),
            ("split", SPLIT_FIELDS),
            ("meta", META_FIELDS),
        ):
            if not _is_yes(classified.get(TABLE_APPLY_FLAGS[table_name], "yes")):
                continue
            action = _upsert_row(
                bundle[table_name]["rows"],
                current_ligand_id=current_ligand_id,
                replacement_ligand_id=replacement_ligand_id,
                expected=expected[table_name],
                fields=fields,
                target_required=PRIMARY_TARGET if table_name != "meta" else None,
            )
            row_actions[table_name] = action
            slot_action_counter[f"{table_name}:{action}"] += 1
        materialized_rows.append(
            {
                "packet": packet,
                "packet_step": _text(classified.get("packet_step")),
                "current_ligand_id": current_ligand_id,
                "replacement_ligand_id": replacement_ligand_id,
                "materialized_tables": ",".join(sorted(row_actions)),
                "reference_action": row_actions.get("reference", ""),
                "split_action": row_actions.get("split", ""),
                "meta_action": row_actions.get("meta", ""),
            }
        )

    if apply_changes:
        for bundle in packet_tables.values():
            for table in bundle.values():
                write_csv_rows(table["path"], table["fieldnames"], table["rows"])

    return {
        "packet_tables": packet_tables,
        "materialized_rows": materialized_rows,
        "summary": {
            "materialized_row_count": len(materialized_rows),
            "slot_action_counts": dict(sorted(slot_action_counter.items())),
            "apply_changes": apply_changes,
        },
    }


def _packet_rows(packet_bundle: dict[str, Any], table_name: str) -> list[dict[str, str]]:
    rows = list(packet_bundle.get(table_name, {}).get("rows", []))
    if table_name in {"reference", "split"}:
        return [row for row in rows if _text(row.get("target")) == PRIMARY_TARGET]
    return rows


def summarize_packet_bundle(packet: str, packet_bundle: dict[str, Any]) -> dict[str, Any]:
    reference_rows = _packet_rows(packet_bundle, "reference")
    split_rows = _packet_rows(packet_bundle, "split")
    meta_rows = _packet_rows(packet_bundle, "meta")
    ref_by_id = {_text(row.get("ligand_id")): row for row in reference_rows if _text(row.get("ligand_id"))}
    split_by_id = {_text(row.get("ligand_id")): row for row in split_rows if _text(row.get("ligand_id"))}
    meta_by_id = {_text(row.get("ligand_id")): row for row in meta_rows if _text(row.get("ligand_id"))}
    ligand_ids = sorted(set(ref_by_id) | set(split_by_id) | set(meta_by_id))
    complete_ligand_count = 0
    placeholder_ligand_count = 0
    missing_reference_value_count = 0
    binder_count = 0
    non_binder_count = 0
    for ligand_id in ligand_ids:
        ref_row = ref_by_id.get(ligand_id, {})
        split_row = split_by_id.get(ligand_id, {})
        meta_row = meta_by_id.get(ligand_id, {})
        is_complete = (
            bool(ref_row)
            and bool(split_row)
            and bool(meta_row)
            and not contains_placeholder(ligand_id)
            and not contains_placeholder(ref_row.get("source"))
            and not contains_placeholder(split_row.get("role"))
            and not contains_placeholder(meta_row.get("smiles"))
            and not contains_placeholder(meta_row.get("scaffold"))
            and bool(_text(ref_row.get("reference_binding_kcal_mol")))
            and bool(_text(split_row.get("role")))
            and bool(_text(meta_row.get("smiles")))
            and bool(_text(meta_row.get("scaffold")))
        )
        if is_complete:
            complete_ligand_count += 1
        if contains_placeholder(ligand_id) or row_has_placeholder(ref_row) or row_has_placeholder(split_row) or row_has_placeholder(meta_row):
            placeholder_ligand_count += 1
        if ref_row and not _text(ref_row.get("reference_binding_kcal_mol")):
            missing_reference_value_count += 1
        if _text(ref_row.get("is_binder")) == "1":
            binder_count += 1
        elif _text(ref_row.get("is_binder")) == "0":
            non_binder_count += 1

    packet_ready = bool(ligand_ids) and complete_ligand_count == len(ligand_ids)
    if not ligand_ids:
        status = "header_only"
    elif packet_ready:
        status = "ready_for_packet"
    elif complete_ligand_count > 0:
        status = "partially_curated"
    else:
        status = "placeholder_only"

    return {
        "packet": packet,
        "ligand_row_count": len(ligand_ids),
        "complete_ligand_count": complete_ligand_count,
        "blocked_ligand_count": len(ligand_ids) - complete_ligand_count,
        "placeholder_ligand_count": placeholder_ligand_count,
        "missing_reference_value_count": missing_reference_value_count,
        "binder_count": binder_count,
        "non_binder_count": non_binder_count,
        "packet_ready": packet_ready,
        "status": status,
    }


def summarize_packet_tables(packet_tables: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {packet: summarize_packet_bundle(packet, bundle) for packet, bundle in packet_tables.items()}
