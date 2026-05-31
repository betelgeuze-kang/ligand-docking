#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ORGANIZER_NOTICE_PACKET_JSON = "casp17/casp17_organizer_notice_packet_current.json"
DEFAULT_OUT_DIR = "casp17/massivefold_external_pool_intake"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_external_pool_intake_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_external_pool_intake_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_EXTERNAL_POOL_INTAKE.md"

MODEL_POOL_POLICY = "external_rerank_accuracy_estimation_pool"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
COMPETITIVE_PROOF_ELIGIBLE = "False"
SUBMISSION_POLICY = "rule_check_required_before_any_human_submission_use"
DOWNLOAD_POLICY = "operator_explicit_download_required_no_automatic_tarball_fetch"
R2345_SEQUENCE_GUARD = "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only"

CLAIM_BOUNDARY = (
    "Local CASP17 MassiveFold external-pool intake only. It records organizer-provided tarball links, "
    "per-target acquisition folders, and rerank/accuracy-estimation guardrails. It does not download large "
    "tarballs, submit CASP models, or convert external MassiveFold structures into internal competitive-proof "
    "predictions."
)

ROW_COLUMNS = [
    "pool_id",
    "model_set_id",
    "primary_target_id",
    "target_category",
    "bundle_format",
    "massivefold_tarball_url",
    "ftp_filename",
    "ftp_size_bytes",
    "ftp_modified_hint",
    "download_path",
    "extract_dir",
    "pool_folder",
    "acquisition_manifest",
    "model_pool_policy",
    "internal_prediction_policy",
    "competitive_proof_eligible",
    "submission_policy",
    "download_policy",
    "sequence_guard",
    "pool_status",
    "next_action",
]


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


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


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


def _massivefold_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("massivefold_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("_").lower()
    return slug[:96] or "massivefold_pool"


def _filename_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def _pool_folder(base_dir: str | Path, model_set_id: str) -> Path:
    return _resolve(base_dir) / _safe_slug(model_set_id)


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


def _build_rows(massivefold_rows: list[dict[str, Any]], out_dir: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, source in enumerate(massivefold_rows, start=1):
        model_set_id = _text(source.get("model_set_id"))
        primary_target_id = _text(source.get("primary_target_id"))
        url = _text(source.get("massivefold_tarball_url"))
        filename = _text(source.get("ftp_filename")) or _filename_from_url(url)
        folder = _pool_folder(out_dir, model_set_id)
        downloads = folder / "downloads"
        extract_dir = folder / "extracted_models"
        manifest = folder / "ACQUISITION_MANIFEST.md"
        rows.append(
            {
                "pool_id": f"massivefold_external_pool_{index:03d}",
                "model_set_id": model_set_id,
                "primary_target_id": primary_target_id,
                "target_category": _text(source.get("target_category")),
                "bundle_format": _text(source.get("bundle_format")),
                "massivefold_tarball_url": url,
                "ftp_filename": filename,
                "ftp_size_bytes": _int(source.get("ftp_size_bytes"), 0),
                "ftp_modified_hint": _text(source.get("ftp_modified_hint")),
                "download_path": _artifact(downloads / filename) if filename else _artifact(downloads),
                "extract_dir": _artifact(extract_dir),
                "pool_folder": _artifact(folder),
                "acquisition_manifest": _artifact(manifest),
                "model_pool_policy": MODEL_POOL_POLICY,
                "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
                "competitive_proof_eligible": COMPETITIVE_PROOF_ELIGIBLE,
                "submission_policy": SUBMISSION_POLICY,
                "download_policy": DOWNLOAD_POLICY,
                "sequence_guard": R2345_SEQUENCE_GUARD if primary_target_id == "R2345" else "",
                "pool_status": "external_pool_ready_for_operator_acquisition" if url else "blocked_missing_tarball_url",
                "next_action": (
                    "optionally download into this external-pool folder, hash the tarball, extract models, "
                    "and use only for rerank/accuracy-estimation rule-checked experiments"
                ),
            }
        )
    return rows


def _status(input_exists: bool, rows: list[dict[str, Any]]) -> str:
    if not input_exists:
        return "blocked_organizer_notice_packet_missing"
    if not rows:
        return "blocked_massivefold_links_missing"
    if any(row["pool_status"].startswith("blocked") for row in rows):
        return "blocked_massivefold_external_pool_incomplete"
    return "massivefold_external_pool_intake_ready"


def _build_summary(
    args: argparse.Namespace,
    organizer_payload: dict[str, Any],
    rows: list[dict[str, Any]],
    input_exists: bool,
) -> dict[str, Any]:
    organizer_summary = _summary(organizer_payload)
    first = rows[0] if rows else {}
    largest = max(rows, key=lambda row: _int(row.get("ftp_size_bytes")), default={})
    ready_rows = [row for row in rows if row["pool_status"] == "external_pool_ready_for_operator_acquisition"]
    return {
        "packet_type": "casp17_massivefold_external_pool_intake",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_external_pool_intake_status": _status(input_exists, rows),
        "organizer_notice_packet_json": _artifact(args.organizer_notice_packet_json),
        "organizer_notice_status": _text(organizer_summary.get("organizer_notice_status")),
        "massivefold_pool_count": len(rows),
        "ready_pool_count": len(ready_rows),
        "blocked_pool_count": len(rows) - len(ready_rows),
        "rna_hybrid_pool_count": sum(1 for row in rows if row["target_category"] == "rna_or_hybrid"),
        "protein_complex_pool_count": sum(1 for row in rows if row["target_category"] == "protein_or_complex"),
        "total_declared_size_bytes": sum(_int(row.get("ftp_size_bytes")) for row in rows),
        "competitive_proof_eligible_count": sum(1 for row in rows if row["competitive_proof_eligible"] == "True"),
        "internal_prediction_blocked_count": sum(
            1 for row in rows if row["internal_prediction_policy"] == INTERNAL_PREDICTION_POLICY
        ),
        "acquisition_manifest_count": len(rows),
        "r2341_pool_present": any(row["primary_target_id"] == "R2341" for row in rows),
        "r2345_pool_present": any(row["primary_target_id"] == "R2345" for row in rows),
        "r2345_sequence_guard": R2345_SEQUENCE_GUARD,
        "model_pool_policy": MODEL_POOL_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "download_policy": DOWNLOAD_POLICY,
        "out_dir": _artifact(args.out_dir),
        "first_pool_id": _text(first.get("pool_id")),
        "first_model_set_id": _text(first.get("model_set_id")),
        "first_primary_target_id": _text(first.get("primary_target_id")),
        "largest_model_set_id": _text(largest.get("model_set_id")),
        "largest_pool_size_bytes": _int(largest.get("ftp_size_bytes")),
        "next_action": (
            "download selected tarballs only into the external-pool lane, record hashes/extraction manifests, "
            "then use them for model ranking and accuracy-estimation calibration without internal proof claims"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    input_path = _resolve(args.organizer_notice_packet_json)
    organizer_payload = _read_json(input_path)
    rows = _build_rows(_massivefold_rows(organizer_payload), args.out_dir)
    summary = _build_summary(args, organizer_payload, rows, input_path.exists())
    return {"summary": summary, "rows": rows}


def _write_manifest(row: dict[str, Any]) -> None:
    lines = [
        f"# {row['model_set_id']} MassiveFold External Pool",
        "",
        f"- pool_id: `{row['pool_id']}`",
        f"- primary_target_id: `{row['primary_target_id']}`",
        f"- target_category: `{row['target_category']}`",
        f"- bundle_format: `{row['bundle_format']}`",
        f"- tarball_url: `{row['massivefold_tarball_url']}`",
        f"- ftp_size_bytes: `{row['ftp_size_bytes']}`",
        f"- model_pool_policy: `{row['model_pool_policy']}`",
        f"- internal_prediction_policy: `{row['internal_prediction_policy']}`",
        f"- competitive_proof_eligible: `{row['competitive_proof_eligible']}`",
        f"- submission_policy: `{row['submission_policy']}`",
        f"- download_policy: `{row['download_policy']}`",
        f"- sequence_guard: `{row['sequence_guard'] or '-'}`",
        "",
        "## Operator Acquisition Commands",
        "",
        "Run only when this external pool is intentionally needed for rerank or accuracy-estimation experiments.",
        "",
        "```bash",
        f"mkdir -p {row['pool_folder']}/downloads {row['pool_folder']}/extracted_models {row['pool_folder']}/hashes",
        f"curl -L -o {row['download_path']} '{row['massivefold_tarball_url']}'",
        f"sha256sum {row['download_path']} > {row['pool_folder']}/hashes/{row['ftp_filename']}.sha256",
        f"tar -tzf {row['download_path']} > {row['pool_folder']}/extracted_models/tarball_listing.txt",
        "```",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
        "",
    ]
    folder = _resolve(row["pool_folder"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ACQUISITION_MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")
    _write_csv(folder / "external_pool_candidate.csv", [row], ROW_COLUMNS)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold External Pool Intake",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_external_pool_intake_status']}`",
        f"- pools ready/blocked/total: `{summary['ready_pool_count']}/{summary['blocked_pool_count']}/{summary['massivefold_pool_count']}`",
        f"- RNA-hybrid/protein-complex: `{summary['rna_hybrid_pool_count']}/{summary['protein_complex_pool_count']}`",
        f"- R2341/R2345 present: `{summary['r2341_pool_present']}`/`{summary['r2345_pool_present']}`",
        f"- competitive proof eligible: `{summary['competitive_proof_eligible_count']}`",
        f"- internal prediction blocked: `{summary['internal_prediction_blocked_count']}`",
        f"- total declared size bytes: `{summary['total_declared_size_bytes']}`",
        f"- largest pool: `{summary['largest_model_set_id'] or '-'}` `{summary['largest_pool_size_bytes']}`",
        f"- policy: `{summary['model_pool_policy']}` / `{summary['internal_prediction_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## External Pools",
        "",
        "| pool | model_set | category | size_bytes | proof | manifest |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['pool_id']}` | `{row['model_set_id']}` | `{row['target_category']}` | "
            f"`{row['ftp_size_bytes']}` | `{row['competitive_proof_eligible']}` | "
            f"`{row['acquisition_manifest']}` |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | - | `False` | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    for row in payload["rows"]:
        _write_manifest(row)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 MassiveFold external model-pool intake manifests.")
    parser.add_argument("--organizer-notice-packet-json", default=DEFAULT_ORGANIZER_NOTICE_PACKET_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
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
