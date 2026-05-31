#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SEED_INVENTORY_JSON = "runs/casp17_historical_identity_seed_inventory_current.json"
DEFAULT_AUDIT_DIR = "casp17/historical_seed_native_authority_audit"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_native_authority_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_native_authority_audit_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_NATIVE_AUTHORITY_AUDIT.md"

PLACEHOLDER_MARKERS = (
    "PLACEHOLDER",
    "AUTO-GENERATED SMALL PROTEIN TEST STRUCTURE",
    "MINIMAL TEST STRUCTURE",
    "TEST STRUCTURE FOR VALIDATION",
    "DUMMY",
)
LOCAL_GENERATED_SOURCE_KINDS = {
    "paired_protein_ligand_complex_minimized",
}
ROW_COLUMNS = [
    "seed_rank",
    "batch_slot",
    "target_id",
    "benchmark_id",
    "scope",
    "native_authority_status",
    "native_pdb",
    "prediction_pdb",
    "native_exists",
    "prediction_exists",
    "native_atom_count",
    "native_chain_count",
    "native_ca_only",
    "native_placeholder_marker_count",
    "native_authority_ref",
    "source_kind",
    "audit_folder",
    "blockers",
    "next_action",
    "native_header",
    "native_title",
]
CLAIM_BOUNDARY = (
    "Local CASP17 historical seed native-authority audit only. It separates local file presence from "
    "authoritative native/reference suitability before a seed can enter competitive benchmark evidence. "
    "It does not fetch native structures, approve no-leak provenance, mutate operator CSVs, score native "
    "accuracy, run predictors, or submit to CASP."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


def _pdb_profile(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    profile = {
        "exists": path.is_file(),
        "atom_count": 0,
        "chain_count": 0,
        "ca_only": False,
        "placeholder_marker_count": 0,
        "header": "",
        "title": "",
    }
    if not path.is_file():
        return profile
    chains: set[str] = set()
    atom_names: list[str] = []
    first_lines: list[str] = []
    title_lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for index, line in enumerate(handle):
            if index < 200:
                first_lines.append(line.rstrip("\n"))
            if line.startswith("HEADER") and not profile["header"]:
                profile["header"] = line.rstrip("\n")
            if line.startswith("TITLE"):
                title_lines.append(line[10:].strip())
            if line.startswith(("ATOM", "HETATM")):
                profile["atom_count"] += 1
                atom_name = line[12:16].strip()
                if atom_name:
                    atom_names.append(atom_name)
                chain_id = line[21:22].strip()
                if chain_id:
                    chains.add(chain_id)
    profile["chain_count"] = len(chains)
    profile["ca_only"] = bool(atom_names) and all(atom == "CA" for atom in atom_names)
    haystack = "\n".join(first_lines).upper()
    profile["placeholder_marker_count"] = sum(1 for marker in PLACEHOLDER_MARKERS if marker in haystack)
    profile["title"] = " ".join(title_lines)[:240]
    return profile


def _authority_ref(row: dict[str, Any]) -> str:
    for key in ("native_authority_ref", "authority_ref", "native_release_authority_ref", "native_source_ref"):
        value = _text(row.get(key))
        if value:
            return value
    return ""


def _row_blockers(row: dict[str, Any], native_profile: dict[str, Any], prediction_exists: bool) -> list[str]:
    blockers: list[str] = []
    authority_ref = _authority_ref(row)
    source_kind = _text(row.get("source_kind"))
    native_pdb = _text(row.get("native_pdb"))
    prediction_pdb = _text(row.get("prediction_pdb"))
    if not native_profile["exists"]:
        blockers.append("native_pdb_missing")
    if not prediction_exists:
        blockers.append("prediction_pdb_missing")
    if native_pdb and prediction_pdb and _resolve(native_pdb) == _resolve(prediction_pdb):
        blockers.append("native_prediction_paths_identical")
    if native_profile["exists"] and _int(native_profile["atom_count"]) <= 0:
        blockers.append("native_atom_count_zero")
    if native_profile["placeholder_marker_count"]:
        blockers.append("native_placeholder_marker_present")
    if native_profile["ca_only"]:
        blockers.append("native_ca_only_no_sidechain_atoms")
    if source_kind in LOCAL_GENERATED_SOURCE_KINDS and not authority_ref:
        blockers.append("local_generated_native_without_authority")
    if not authority_ref:
        blockers.append("native_authority_ref_missing")
    return blockers


def _next_action(blockers: list[str]) -> str:
    if "native_pdb_missing" in blockers:
        return "place an authoritative native/reference PDB and cite its release authority"
    if "native_placeholder_marker_present" in blockers or "native_ca_only_no_sidechain_atoms" in blockers:
        return "replace the placeholder or CA-only native with an authoritative all-atom native/reference PDB"
    if "local_generated_native_without_authority" in blockers:
        return "attach external native/source authority for the local complex reference or replace the row"
    if "native_authority_ref_missing" in blockers:
        return "add a native authority reference before no-leak promotion"
    if "prediction_pdb_missing" in blockers:
        return "restore the paired internal prediction PDB"
    return "native authority evidence is ready for operator no-leak review"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    seed_payload = _read_json(args.seed_inventory_json)
    rows: list[dict[str, Any]] = []
    for seed in _rows(seed_payload):
        target_id = _text(seed.get("target_id"))
        folder_slot = _int(seed.get("batch_slot")) or _int(seed.get("seed_rank"))
        folder = _resolve(args.audit_dir) / f"{folder_slot:02d}_{_safe_name(target_id)}"
        native_profile = _pdb_profile(seed.get("native_pdb", ""))
        prediction_exists = _resolve(_text(seed.get("prediction_pdb"))).is_file()
        blockers = _row_blockers(seed, native_profile, prediction_exists)
        rows.append(
            {
                "seed_rank": _int(seed.get("seed_rank")),
                "batch_slot": _int(seed.get("batch_slot")),
                "target_id": target_id,
                "benchmark_id": _text(seed.get("benchmark_id")),
                "scope": _text(seed.get("scope")),
                "native_authority_status": "authority_pass" if not blockers else "authority_blocked",
                "native_pdb": _artifact(seed.get("native_pdb", "")),
                "prediction_pdb": _artifact(seed.get("prediction_pdb", "")),
                "native_exists": bool(native_profile["exists"]),
                "prediction_exists": prediction_exists,
                "native_atom_count": _int(native_profile["atom_count"]),
                "native_chain_count": _int(native_profile["chain_count"]),
                "native_ca_only": bool(native_profile["ca_only"]),
                "native_placeholder_marker_count": _int(native_profile["placeholder_marker_count"]),
                "native_authority_ref": _authority_ref(seed),
                "source_kind": _text(seed.get("source_kind")),
                "audit_folder": _artifact(folder),
                "blockers": ",".join(blockers),
                "next_action": _next_action(blockers),
                "native_header": _text(native_profile["header"]),
                "native_title": _text(native_profile["title"]),
            }
        )

    blocked_rows = [row for row in rows if row["native_authority_status"] != "authority_pass"]
    first_blocked = blocked_rows[0] if blocked_rows else {}
    if not rows:
        status = "missing_seed_inventory"
    elif blocked_rows:
        status = "blocked_native_authority"
    else:
        status = "pass"
    summary = {
        "packet_type": "casp17_historical_seed_native_authority_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "native_authority_audit_status": status,
        "seed_row_count": len(rows),
        "native_authority_pass_count": len(rows) - len(blocked_rows),
        "native_authority_blocked_count": len(blocked_rows),
        "placeholder_native_count": sum(1 for row in rows if _int(row.get("native_placeholder_marker_count"))),
        "ca_only_native_count": sum(1 for row in rows if row.get("native_ca_only") is True),
        "local_generated_native_without_authority_count": sum(
            1 for row in rows if "local_generated_native_without_authority" in _text(row.get("blockers"))
        ),
        "authority_ref_missing_count": sum(
            1 for row in rows if "native_authority_ref_missing" in _text(row.get("blockers"))
        ),
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocked_next_action": _text(first_blocked.get("next_action")),
        "seed_inventory_json": _artifact(args.seed_inventory_json),
        "audit_dir": _artifact(args.audit_dir),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_row_folders(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        folder = _resolve(row["audit_folder"])
        folder.mkdir(parents=True, exist_ok=True)
        _write_csv(folder / "native_authority_audit.csv", [row], ROW_COLUMNS)
        lines = [
            f"# CASP17 Native Authority Audit: {row['target_id']}",
            "",
            f"- status: `{row['native_authority_status']}`",
            f"- benchmark: `{row['benchmark_id']}`",
            f"- scope: `{row['scope']}`",
            f"- native: `{row['native_pdb']}`",
            f"- authority ref: `{row['native_authority_ref'] or '-'}`",
            f"- atoms/chains: `{row['native_atom_count']}/{row['native_chain_count']}`",
            f"- placeholder markers: `{row['native_placeholder_marker_count']}`",
            f"- CA-only: `{row['native_ca_only']}`",
            f"- blockers: `{row['blockers'] or '-'}`",
            f"- next action: {row['next_action']}",
            "",
        ]
        (folder / "NATIVE_AUTHORITY.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Native Authority Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['native_authority_audit_status']}`",
        f"- pass/blocked/total: `{summary['native_authority_pass_count']}/{summary['native_authority_blocked_count']}/{summary['seed_row_count']}`",
        f"- placeholder/CA-only/local-generated-without-authority/ref-missing: `{summary['placeholder_native_count']}/{summary['ca_only_native_count']}/{summary['local_generated_native_without_authority_count']}/{summary['authority_ref_missing_count']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}`",
        f"- next action: {summary['first_blocked_next_action'] or '-'}",
        "",
        "## Rows",
        "",
        "| slot | target | scope | status | native | blockers | next action |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['batch_slot']} | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['native_authority_status']}` | `{row['native_pdb']}` | "
            f"`{row['blockers'] or '-'}` | {row['next_action']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `missing_seed_inventory` | - | - | build seed inventory first |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_row_folders(payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed native authority audit.")
    parser.add_argument("--seed-inventory-json", default=DEFAULT_SEED_INVENTORY_JSON)
    parser.add_argument("--audit-dir", default=DEFAULT_AUDIT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
