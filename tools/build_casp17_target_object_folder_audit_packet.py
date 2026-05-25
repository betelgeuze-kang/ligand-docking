#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TARGET_MODEL_FOLDERS_JSON = "casp17/casp17_target_model_folders_current.json"
DEFAULT_OUT_JSON = "casp17/casp17_target_object_folder_audit_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_target_object_folder_audit_current.csv"
DEFAULT_OUT_MD = "casp17/casp17_target_object_folder_audit_current.md"

HOSTED_TOKENS = ("http://", "https://", "//cdn.", "unpkg.com", "jsdelivr.net")
CLAIM_BOUNDARY = (
    "Local CASP17 object-folder audit only. It verifies per-protein folder placement, "
    "chain/object PDB isolation, manifest/readme/projection/viewer presence, and local-only viewer "
    "dependencies; it does not fetch structures, score native accuracy, use external predictors, "
    "or submit to CASP."
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


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _object_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("object_rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    objects: list[dict[str, Any]] = []
    for target in payload.get("targets", []):
        if not isinstance(target, dict):
            continue
        for row in target.get("objects", []):
            if isinstance(row, dict):
                objects.append(row)
    return objects


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["target_id", "object_id", "folder_audit_status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _ascii_slug(value: str, *, fallback: str, max_len: int = 80) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_text).strip("_")
    slug = re.sub(r"_+", "_", slug)
    if not slug:
        slug = fallback
    return slug[:max_len].rstrip("_") or fallback


def _safe_relative(child: Path, parent: Path) -> str:
    try:
        return str(child.resolve().relative_to(parent.resolve()))
    except (OSError, ValueError):
        return ""


def _file_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _pdb_chain_stats(path: Path) -> dict[str, Any]:
    atoms = 0
    residues: set[tuple[str, str, str]] = set()
    chains: set[str] = set()
    if not path.is_file():
        return {"atom_count": 0, "residue_count": 0, "chain_ids": []}
    for line in _file_text(path).splitlines():
        record = line[:6].strip().upper()
        if record not in {"ATOM", "HETATM"}:
            continue
        atoms += 1
        chain = line[21:22].strip() or "blank"
        resseq = line[22:26].strip()
        icode = line[26:27].strip()
        chains.add(chain)
        residues.add((chain, resseq, icode))
    return {"atom_count": atoms, "residue_count": len(residues), "chain_ids": sorted(chains)}


def _projection_ok(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError):
        return False
    return root.tag.endswith("svg")


def _viewer_blockers(path: Path) -> list[str]:
    if not path.is_file():
        return ["viewer_html_missing"]
    text = _file_text(path)
    blockers: list[str] = []
    if '<canvas id="viewer"' not in text:
        blockers.append("viewer_canvas_missing")
    if "const atoms =" not in text:
        blockers.append("viewer_atom_payload_missing")
    if "requestAnimationFrame" not in text:
        blockers.append("viewer_animation_loop_missing")
    hosted = [token for token in HOSTED_TOKENS if token in text]
    if hosted:
        blockers.append("viewer_hosted_dependency:" + ",".join(hosted))
    return blockers


def _manifest_blockers(path: Path, row: dict[str, Any]) -> list[str]:
    if not path.is_file():
        return ["manifest_missing"]
    payload = _read_json(path)
    summary = _summary(payload)
    blockers: list[str] = []
    for key in ("target_id", "object_id", "chain_id", "model_path", "viewer_html_path"):
        if _text(summary.get(key)) != _text(row.get(key)):
            blockers.append(f"manifest_{key}_mismatch")
    if _text(payload.get("claim_boundary")) != CLAIM_BOUNDARY and "claim_boundary" not in payload:
        blockers.append("manifest_claim_boundary_missing")
    return blockers


def _readme_blockers(path: Path, row: dict[str, Any]) -> list[str]:
    if not path.is_file():
        return ["readme_missing"]
    text = _file_text(path)
    blockers: list[str] = []
    for key in ("target_id", "object_id", "model_path", "viewer_html_path"):
        value = _text(row.get(key))
        if value and value not in text:
            blockers.append(f"readme_{key}_missing")
    return blockers


def _audit_row(row: dict[str, Any]) -> dict[str, Any]:
    target_id = _text(row.get("target_id"))
    protein_name = _text(row.get("protein_name")) or target_id
    object_id = _text(row.get("object_id"))
    chain_id = _text(row.get("chain_id")) or "blank"
    target_folder = _resolve(row.get("target_folder", ""))
    object_folder = _resolve(row.get("object_folder", ""))
    model_path = _resolve(row.get("model_path", ""))
    projection_path = _resolve(row.get("projection_svg_path", ""))
    viewer_path = _resolve(row.get("viewer_html_path", ""))
    manifest_path = _resolve(row.get("manifest_path", ""))
    readme_path = _resolve(row.get("readme_path", ""))

    blockers: list[str] = []
    expected_target_folder_suffix = f"{target_id}_{_ascii_slug(protein_name, fallback='protein_complex')}"
    if not target_folder.is_dir():
        blockers.append("target_folder_missing")
    elif target_folder.name != expected_target_folder_suffix:
        blockers.append("target_folder_not_protein_named")
    if not object_folder.is_dir():
        blockers.append("object_folder_missing")
    else:
        relative_object = _safe_relative(object_folder, target_folder)
        if relative_object != f"objects/{object_id}":
            blockers.append("object_folder_not_under_target_objects")

    if not model_path.is_file():
        blockers.append("object_pdb_missing")
    elif _safe_relative(model_path, object_folder) != f"models/{target_id}_{object_id}.pdb":
        blockers.append("object_pdb_not_in_object_models_folder")

    stats = _pdb_chain_stats(model_path)
    chain_ids = [str(chain) for chain in stats["chain_ids"]]
    if stats["atom_count"] <= 0:
        blockers.append("object_pdb_atom_records_missing")
    if chain_ids != [chain_id]:
        blockers.append("object_pdb_chain_isolation_failed")
    if int(row.get("atom_count") or 0) != int(stats["atom_count"]):
        blockers.append("object_pdb_atom_count_mismatch")
    if int(row.get("residue_count") or 0) != int(stats["residue_count"]):
        blockers.append("object_pdb_residue_count_mismatch")

    if not _projection_ok(projection_path):
        blockers.append("projection_svg_missing_or_invalid")
    blockers.extend(_viewer_blockers(viewer_path))
    blockers.extend(_manifest_blockers(manifest_path, row))
    blockers.extend(_readme_blockers(readme_path, row))

    return {
        "target_id": target_id,
        "protein_name": protein_name,
        "object_id": object_id,
        "chain_id": chain_id,
        "folder_audit_status": "pass" if not blockers else "blocked",
        "target_folder": _artifact(target_folder),
        "object_folder": _artifact(object_folder),
        "model_path": _artifact(model_path),
        "projection_svg_path": _artifact(projection_path),
        "viewer_html_path": _artifact(viewer_path),
        "manifest_path": _artifact(manifest_path),
        "readme_path": _artifact(readme_path),
        "atom_count": stats["atom_count"],
        "residue_count": stats["residue_count"],
        "chain_ids": ",".join(chain_ids),
        "blockers": ",".join(blockers),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    target_payload = _read_json(args.target_model_folders_json)
    target_summary = _summary(target_payload)
    rows = [_audit_row(row) for row in _object_rows(target_payload)]
    pass_rows = [row for row in rows if row["folder_audit_status"] == "pass"]
    blocked_rows = [row for row in rows if row["folder_audit_status"] != "pass"]
    target_ids = sorted({row["target_id"] for row in rows if row["target_id"]})
    summary = {
        "packet_type": "casp17_target_object_folder_audit",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "folder_audit_status": "pass" if rows and not blocked_rows else "blocked",
        "target_model_folders_json": _artifact(args.target_model_folders_json),
        "target_model_folder_status": "ready" if int(target_summary.get("blocked_count") or 0) == 0 else "blocked",
        "target_count": len(target_ids),
        "object_row_count": len(rows),
        "pass_count": len(pass_rows),
        "blocked_count": len(blocked_rows),
        "protein_named_folder_pass_count": sum(
            1 for row in rows if "target_folder_not_protein_named" not in row["blockers"]
        ),
        "chain_isolation_pass_count": sum(
            1 for row in rows if "object_pdb_chain_isolation_failed" not in row["blockers"]
        ),
        "manifest_pass_count": sum(1 for row in rows if "manifest_" not in row["blockers"]),
        "readme_pass_count": sum(1 for row in rows if "readme_" not in row["blockers"]),
        "viewer_local_only_pass_count": sum(1 for row in rows if "viewer_hosted_dependency" not in row["blockers"]),
        "first_blocked_object": blocked_rows[0]["object_id"] if blocked_rows else "",
        "first_blocked_blockers": blocked_rows[0]["blockers"] if blocked_rows else "",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Target Object Folder Audit",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- folder_audit_status: `{summary['folder_audit_status']}`",
        f"- objects pass/blocked/total: `{summary['pass_count']}/{summary['blocked_count']}/{summary['object_row_count']}`",
        f"- protein-named folders: `{summary['protein_named_folder_pass_count']}/{summary['object_row_count']}`",
        f"- chain isolation: `{summary['chain_isolation_pass_count']}/{summary['object_row_count']}`",
        f"- manifest/readme pass: `{summary['manifest_pass_count']}/{summary['readme_pass_count']}`",
        f"- local-only viewers: `{summary['viewer_local_only_pass_count']}/{summary['object_row_count']}`",
        f"- first blocked object: `{summary['first_blocked_object'] or '-'}`",
        f"- first blocked blockers: `{summary['first_blocked_blockers'] or '-'}`",
        "",
        "## Objects",
        "",
        "| target | protein/complex | object | chain | status | atoms | residues | folder | blockers |",
        "| --- | --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | {row['protein_name']} | `{row['object_id']}` | `{row['chain_id']}` | "
            f"`{row['folder_audit_status']}` | {row['atom_count']} | {row['residue_count']} | "
            f"`{row['object_folder']}` | `{row['blockers'] or '-'}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | `blocked` | 0 | 0 | - | no objects |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit CASP17 per-protein object folders for independent local 3D review readiness."
    )
    parser.add_argument("--target-model-folders-json", default=DEFAULT_TARGET_MODEL_FOLDERS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if payload["summary"]["folder_audit_status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
