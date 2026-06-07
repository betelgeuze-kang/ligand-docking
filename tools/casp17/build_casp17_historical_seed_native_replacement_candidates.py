#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_NATIVE_AUTHORITY_AUDIT_JSON = "casp17/casp17_historical_seed_native_authority_audit_current.json"
DEFAULT_PUBLIC_STRUCTURE_DIR = "data/public_structures/2026-02-15"
DEFAULT_CANDIDATE_DIR = "casp17/historical_seed_native_replacement_candidates"
DEFAULT_OUT_JSON = "casp17/casp17_historical_seed_native_replacement_candidates_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_historical_seed_native_replacement_candidates_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_HISTORICAL_SEED_NATIVE_REPLACEMENT_CANDIDATES.md"

CANDIDATE_COLUMNS = [
    "candidate_rank",
    "target_id",
    "benchmark_id",
    "scope",
    "candidate_status",
    "candidate_kind",
    "pdb_id",
    "candidate_label",
    "candidate_confidence",
    "source_public_pdb",
    "candidate_pdb",
    "candidate_exists",
    "candidate_atom_count",
    "candidate_chain_count",
    "candidate_ca_only",
    "candidate_placeholder_marker_count",
    "native_authority_ref",
    "rcsb_entry_url",
    "rcsb_download_url",
    "audit_folder",
    "blockers",
    "next_action",
    "notes",
]

CANDIDATE_MAP: dict[str, list[dict[str, str]]] = {
    "HIST_BBA5": [
        {
            "pdb_id": "1T8J",
            "label": "BBA5",
            "confidence": "direct_local_source_map",
            "notes": "Existing project public-structure source maps BBA5 to RCSB 1T8J.",
        }
    ],
    "HIST_CHIGNOLIN": [
        {
            "pdb_id": "1UAO",
            "label": "Chignolin",
            "confidence": "direct_rcsb_label",
            "notes": "Chignolin representative RCSB entry.",
        }
    ],
    "HIST_CRAMBIN": [
        {
            "pdb_id": "1CRN",
            "label": "Crambin",
            "confidence": "direct_rcsb_label",
            "notes": "Crambin representative RCSB entry.",
        }
    ],
    "HIST_FSD_1": [
        {
            "pdb_id": "1FSD",
            "label": "FSD_1",
            "confidence": "direct_rcsb_label",
            "notes": "FSD-1 NMR ensemble RCSB entry.",
        }
    ],
    "HIST_GB1_MINI": [
        {
            "pdb_id": "2GB1",
            "label": "GB1_Mini",
            "confidence": "direct_local_source_map",
            "notes": "Existing project public-structure source maps GB1_Mini to RCSB 2GB1.",
        }
    ],
    "HIST_PROTEIN_A_BDOMAIN": [
        {
            "pdb_id": "1BDD",
            "label": "Protein_A_Bdomain",
            "confidence": "direct_rcsb_label",
            "notes": "Protein A B-domain minimized average NMR RCSB entry.",
        }
    ],
    "HIST_TRP_CAGE": [
        {
            "pdb_id": "1L2Y",
            "label": "Trp_Cage",
            "confidence": "direct_rcsb_label",
            "notes": "Trp-cage representative RCSB entry.",
        }
    ],
    "HIST_UBIQUITIN_MINI": [
        {
            "pdb_id": "1UBQ",
            "label": "Ubiquitin_Mini",
            "confidence": "direct_local_source_map",
            "notes": "Existing project public-structure source maps Ubiquitin_Mini to RCSB 1UBQ.",
        }
    ],
    "HIST_VILLIN_HP35": [
        {
            "pdb_id": "1YRF",
            "label": "Villin_HP35",
            "confidence": "direct_local_source_map",
            "notes": "Existing project public-structure source maps Villin_HP35 to RCSB 1YRF.",
        }
    ],
    "HIST_WW_DOMAIN_FIP35": [
        {
            "pdb_id": "2F21",
            "label": "WW_Domain_FiP35",
            "confidence": "direct_local_source_map",
            "notes": "Existing project public-structure source maps WW_Domain_FiP35 to RCSB 2F21.",
        }
    ],
}

PLACEHOLDER_MARKERS = (
    "PLACEHOLDER",
    "AUTO-GENERATED SMALL PROTEIN TEST STRUCTURE",
    "MINIMAL TEST STRUCTURE",
    "TEST STRUCTURE FOR VALIDATION",
    "DUMMY",
)
CLAIM_BOUNDARY = (
    "Local CASP17 historical seed native replacement candidate packet only. It copies existing public "
    "RCSB-derived PDB files into per-seed review folders and records authority references for operator "
    "review. It does not replace active native files, mutate operator CSVs, clear no-leak provenance, "
    "score native accuracy, fetch missing structures, run predictors, or submit to CASP."
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


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


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


def _pdb_profile(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    profile = {
        "exists": path.is_file(),
        "atom_count": 0,
        "chain_count": 0,
        "ca_only": False,
        "placeholder_marker_count": 0,
    }
    if not path.is_file():
        return profile
    atom_names: list[str] = []
    chains: set[str] = set()
    first_lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for index, line in enumerate(handle):
            if index < 200:
                first_lines.append(line.rstrip("\n"))
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
    return profile


def _source_public_path(public_dir: str | Path, label: str, pdb_id: str) -> Path:
    return _resolve(public_dir) / f"{_slug(label)}_pdb_{pdb_id.upper()}.pdb"


def _candidate_blockers(profile: dict[str, Any], source_exists: bool) -> list[str]:
    blockers: list[str] = []
    if not source_exists:
        blockers.append("source_public_pdb_missing")
    if not profile["exists"]:
        blockers.append("candidate_pdb_missing")
    if profile["exists"] and _int(profile["atom_count"]) <= 0:
        blockers.append("candidate_atom_count_zero")
    if profile["ca_only"]:
        blockers.append("candidate_ca_only_no_sidechain_atoms")
    if _int(profile["placeholder_marker_count"]):
        blockers.append("candidate_placeholder_marker_present")
    return blockers


def _candidate_status(blockers: list[str]) -> str:
    if not blockers:
        return "operator_review_ready"
    if "source_public_pdb_missing" in blockers:
        return "source_download_required"
    return "candidate_file_blocked"


def _copy_candidate(source: Path, destination: Path) -> bool:
    if not source.is_file():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return True


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    audit_payload = _read_json(args.native_authority_audit_json)
    rows: list[dict[str, Any]] = []
    candidate_rank = 0
    for audit_row in _rows(audit_payload):
        target_id = _text(audit_row.get("target_id"))
        candidates = CANDIDATE_MAP.get(target_id, [])
        if not candidates:
            if _text(audit_row.get("scope")) == "complex":
                candidate_rank += 1
                folder_slot = _int(audit_row.get("batch_slot")) or candidate_rank
                folder = _resolve(args.candidate_dir) / f"{folder_slot:02d}_{_slug(target_id)}"
                rows.append(
                    {
                        "candidate_rank": candidate_rank,
                        "target_id": target_id,
                        "benchmark_id": _text(audit_row.get("benchmark_id")),
                        "scope": _text(audit_row.get("scope")),
                        "candidate_status": "native_authority_ref_required",
                        "candidate_kind": "complex_source_authority_required",
                        "pdb_id": "",
                        "candidate_label": "",
                        "candidate_confidence": "",
                        "source_public_pdb": "",
                        "candidate_pdb": "",
                        "candidate_exists": False,
                        "candidate_atom_count": 0,
                        "candidate_chain_count": 0,
                        "candidate_ca_only": False,
                        "candidate_placeholder_marker_count": 0,
                        "native_authority_ref": "",
                        "rcsb_entry_url": "",
                        "rcsb_download_url": "",
                        "audit_folder": _artifact(folder),
                        "blockers": "external_native_or_source_authority_required",
                        "next_action": "attach external native/source authority for this complex reference or replace the seed row",
                        "notes": "Complex seed currently uses a local generated/minimized reference; no automatic RCSB replacement candidate is assigned.",
                    }
                )
            continue
        for candidate in candidates:
            candidate_rank += 1
            pdb_id = _text(candidate.get("pdb_id")).upper()
            label = _text(candidate.get("label"))
            folder_slot = _int(audit_row.get("batch_slot")) or candidate_rank
            folder = _resolve(args.candidate_dir) / f"{folder_slot:02d}_{_slug(target_id)}"
            source = _source_public_path(args.public_structure_dir, label, pdb_id)
            destination = folder / f"native_candidate_{pdb_id}.pdb"
            _copy_candidate(source, destination)
            profile = _pdb_profile(destination)
            blockers = _candidate_blockers(profile, source.is_file())
            rows.append(
                {
                    "candidate_rank": candidate_rank,
                    "target_id": target_id,
                    "benchmark_id": _text(audit_row.get("benchmark_id")),
                    "scope": _text(audit_row.get("scope")),
                    "candidate_status": _candidate_status(blockers),
                    "candidate_kind": "rcsb_public_native_replacement",
                    "pdb_id": pdb_id,
                    "candidate_label": label,
                    "candidate_confidence": _text(candidate.get("confidence")),
                    "source_public_pdb": _artifact(source),
                    "candidate_pdb": _artifact(destination),
                    "candidate_exists": bool(profile["exists"]),
                    "candidate_atom_count": _int(profile["atom_count"]),
                    "candidate_chain_count": _int(profile["chain_count"]),
                    "candidate_ca_only": bool(profile["ca_only"]),
                    "candidate_placeholder_marker_count": _int(profile["placeholder_marker_count"]),
                    "native_authority_ref": f"rcsb:{pdb_id};doi:10.2210/pdb{pdb_id.lower()}/pdb",
                    "rcsb_entry_url": f"https://www.rcsb.org/structure/{pdb_id}",
                    "rcsb_download_url": f"https://files.rcsb.org/download/{pdb_id}.pdb",
                    "audit_folder": _artifact(folder),
                    "blockers": ",".join(blockers),
                    "next_action": (
                        "operator-review this candidate, then use it to replace the placeholder native path"
                        if not blockers
                        else "download or repair the public PDB candidate before native replacement review"
                    ),
                    "notes": _text(candidate.get("notes")),
                }
            )

    review_ready = sum(1 for row in rows if row["candidate_status"] == "operator_review_ready")
    source_required = sum(1 for row in rows if row["candidate_status"] == "source_download_required")
    complex_authority = sum(1 for row in rows if row["candidate_status"] == "native_authority_ref_required")
    first = next((row for row in rows if row["candidate_status"] != "operator_review_ready"), rows[0] if rows else {})
    if not rows:
        status = "missing_native_authority_audit"
    elif review_ready and source_required == 0:
        status = "partial_native_replacement_candidates_ready"
    elif review_ready:
        status = "native_replacement_candidates_need_download"
    else:
        status = "native_replacement_candidates_blocked"
    summary = {
        "packet_type": "casp17_historical_seed_native_replacement_candidates",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "native_replacement_candidate_status": status,
        "candidate_row_count": len(rows),
        "operator_review_ready_count": review_ready,
        "source_download_required_count": source_required,
        "complex_authority_required_count": complex_authority,
        "candidate_file_blocked_count": sum(1 for row in rows if row["candidate_status"] == "candidate_file_blocked"),
        "monomer_candidate_count": sum(1 for row in rows if row["candidate_kind"] == "rcsb_public_native_replacement"),
        "candidate_dir": _artifact(args.candidate_dir),
        "public_structure_dir": _artifact(args.public_structure_dir),
        "first_blocked_target_id": _text(first.get("target_id")),
        "first_blocked_next_action": _text(first.get("next_action")),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_row_folders(rows: list[dict[str, Any]]) -> None:
    by_folder: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_folder.setdefault(_text(row.get("audit_folder")), []).append(row)
    for folder_name, folder_rows in by_folder.items():
        folder = _resolve(folder_name)
        folder.mkdir(parents=True, exist_ok=True)
        _write_csv(folder / "native_replacement_candidates.csv", folder_rows, CANDIDATE_COLUMNS)
        lines = [
            f"# CASP17 Native Replacement Candidates: {folder_rows[0]['target_id']}",
            "",
            "| rank | status | pdb | candidate | authority | blockers | next action |",
            "| ---: | --- | --- | --- | --- | --- | --- |",
        ]
        for row in folder_rows:
            lines.append(
                f"| {row['candidate_rank']} | `{row['candidate_status']}` | `{row['pdb_id'] or '-'}` | "
                f"`{row['candidate_pdb'] or '-'}` | `{row['native_authority_ref'] or '-'}` | "
                f"`{row['blockers'] or '-'}` | {row['next_action']} |"
            )
        lines.append("")
        (folder / "NATIVE_REPLACEMENT.md").write_text("\n".join(lines), encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Seed Native Replacement Candidates",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['native_replacement_candidate_status']}`",
        f"- review-ready/source-required/file-blocked/complex-authority: `{summary['operator_review_ready_count']}/{summary['source_download_required_count']}/{summary['candidate_file_blocked_count']}/{summary['complex_authority_required_count']}`",
        f"- monomer candidates: `{summary['monomer_candidate_count']}`",
        f"- candidate dir: `{summary['candidate_dir']}`",
        f"- first blocked: `{summary['first_blocked_target_id'] or '-'}`",
        f"- next action: {summary['first_blocked_next_action'] or '-'}",
        "",
        "## Rows",
        "",
        "| rank | target | scope | status | pdb | atoms | candidate | blockers |",
        "| ---: | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['candidate_rank']} | `{row['target_id']}` | `{row['scope']}` | "
            f"`{row['candidate_status']}` | `{row['pdb_id'] or '-'}` | "
            f"{row['candidate_atom_count']} | `{row['candidate_pdb'] or '-'}` | "
            f"`{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `missing_native_authority_audit` | - | 0 | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], CANDIDATE_COLUMNS)
    _write_row_folders(payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 historical seed native replacement candidates.")
    parser.add_argument("--native-authority-audit-json", default=DEFAULT_NATIVE_AUTHORITY_AUDIT_JSON)
    parser.add_argument("--public-structure-dir", default=DEFAULT_PUBLIC_STRUCTURE_DIR)
    parser.add_argument("--candidate-dir", default=DEFAULT_CANDIDATE_DIR)
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
