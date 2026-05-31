#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_MASSIVEFOLD_FTP_ROOT = "ftp://files.plbs.fr:21211/CASP17-CAPRI/"
DEFAULT_MASSIVEFOLD_LINKS_URL = DEFAULT_MASSIVEFOLD_FTP_ROOT + "CASP17-CAPRI_MF_links.csv"
DEFAULT_OUT_DIR = "casp17/organizer_notice_packet"
DEFAULT_OUT_JSON = "casp17/casp17_organizer_notice_packet_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_organizer_notice_packet_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_ORGANIZER_NOTICE_PACKET.md"

NOTICE_SOURCE_REF = "operator_email_excerpt_casp17_organizer"
R2345_INVALID_REQUEST_STATUS = "ignored_invalid_dna_t_in_rna_sequence"
R2345_REPLACEMENT_REQUEST_STATUS = "accepted_second_request_only"
MASSIVEFOLD_MODEL_POOL_POLICY = "external_rerank_accuracy_estimation_pool"
MASSIVEFOLD_INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
MASSIVEFOLD_SUBMISSION_POLICY = "rule_check_required_before_any_human_submission_use"
LARGE_DOWNLOAD_POLICY = "tarballs_not_downloaded_by_notice_packet"


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


def _read_text(path_like: str | Path) -> str:
    return _resolve(path_like).read_text(encoding="utf-8")


def _fetch_text(url: str, timeout_seconds: int) -> str:
    with urlopen(url, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="replace")


def _read_source(
    *,
    file_path: str,
    source_url: str,
    timeout_seconds: int,
    allow_network: bool,
) -> tuple[str, str, str]:
    if file_path:
        path = _resolve(file_path)
        return path.read_text(encoding="utf-8"), _artifact(path), "file_loaded"
    if not allow_network or not source_url:
        return "", "", "not_loaded"
    try:
        return _fetch_text(source_url, timeout_seconds), source_url, "url_loaded"
    except OSError:
        return "", source_url, "url_error"


def _target_category(model_set_id: str) -> str:
    if model_set_id.startswith(("R", "M")):
        return "rna_or_hybrid"
    if model_set_id.startswith(("H", "T")):
        return "protein_or_complex"
    return "other"


def _primary_target_id(model_set_id: str) -> str:
    return model_set_id.split("_", 1)[0].strip()


def _bundle_format(url: str) -> str:
    if "_all_cifs_" in url:
        return "cif_bundle"
    if "_all_pdbs_" in url:
        return "pdb_cif_bundle"
    return "unknown_bundle"


def _parse_massivefold_links(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in csv.reader(text.splitlines()):
        if len(raw) < 2:
            continue
        model_set_id = _text(raw[0])
        url = _text(raw[1])
        if not model_set_id or not url or model_set_id.lower() in {"target", "model_set_id"}:
            continue
        rows.append(
            {
                "model_set_id": model_set_id,
                "primary_target_id": _primary_target_id(model_set_id),
                "target_category": _target_category(model_set_id),
                "massivefold_tarball_url": url,
                "bundle_format": _bundle_format(url),
                "model_pool_policy": MASSIVEFOLD_MODEL_POOL_POLICY,
                "internal_prediction_policy": MASSIVEFOLD_INTERNAL_PREDICTION_POLICY,
                "submission_policy": MASSIVEFOLD_SUBMISSION_POLICY,
                "large_download_policy": LARGE_DOWNLOAD_POLICY,
            }
        )
    return rows


def _parse_ftp_listing(text: str) -> dict[str, dict[str, Any]]:
    listing: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        parts = line.split(maxsplit=8)
        if len(parts) < 9:
            continue
        filename = parts[8].strip()
        if not filename or filename in {".", ".."}:
            continue
        size = parts[4] if re.fullmatch(r"\d+", parts[4]) else ""
        listing[filename] = {
            "ftp_permissions": parts[0],
            "ftp_size_bytes": int(size) if size else "",
            "ftp_modified_hint": " ".join(parts[5:8]),
            "ftp_filename": filename,
        }
    return listing


def _filename_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def _enrich_with_listing(rows: list[dict[str, Any]], listing: dict[str, dict[str, Any]]) -> None:
    for row in rows:
        filename = _filename_from_url(_text(row.get("massivefold_tarball_url")))
        row["ftp_filename"] = filename
        meta = listing.get(filename, {})
        row["ftp_size_bytes"] = meta.get("ftp_size_bytes", "")
        row["ftp_modified_hint"] = meta.get("ftp_modified_hint", "")


def _notice_rows(massivefold_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_primary = {row["primary_target_id"]: row for row in massivefold_rows}
    r2341 = by_primary.get("R2341", {})
    r2345 = by_primary.get("R2345", {})
    return [
        {
            "notice_id": "organizer_notice_001",
            "target_id": "R2345",
            "notice_type": "sequence_request_quarantine",
            "source_ref": NOTICE_SOURCE_REF,
            "request_time_pacific": "09:30",
            "request_status": R2345_INVALID_REQUEST_STATUS,
            "sequence_gate": "rna_sequence_requires_acgu_no_t",
            "action": "do_not_use_first_request_for_modeling_or_scoring",
            "competitive_proof_policy": "quarantine_invalid_input",
            "notes": "First R2345 request used a DNA T where RNA U was intended.",
        },
        {
            "notice_id": "organizer_notice_002",
            "target_id": "R2345",
            "notice_type": "sequence_request_replacement",
            "source_ref": NOTICE_SOURCE_REF,
            "request_time_pacific": "11:30",
            "request_status": R2345_REPLACEMENT_REQUEST_STATUS,
            "sequence_gate": "rna_sequence_requires_acgu_no_t",
            "action": "treat_second_request_as_r2345_active_modeling_request",
            "competitive_proof_policy": "use_only_after_sequence_validation",
            "notes": "Second R2345 request supersedes the invalid first request.",
        },
        {
            "notice_id": "organizer_notice_003",
            "target_id": "R2341",
            "notice_type": "massivefold_first_rna_set_available",
            "source_ref": NOTICE_SOURCE_REF,
            "request_time_pacific": "",
            "request_status": "massivefold_external_model_set_available",
            "sequence_gate": "",
            "action": "track_as_external_candidate_pool_for_rerank_and_accuracy_estimation",
            "competitive_proof_policy": MASSIVEFOLD_INTERNAL_PREDICTION_POLICY,
            "notes": _text(r2341.get("massivefold_tarball_url")),
        },
        {
            "notice_id": "organizer_notice_004",
            "target_id": "R2345",
            "notice_type": "massivefold_r2345_set_observed",
            "source_ref": DEFAULT_MASSIVEFOLD_LINKS_URL if r2345 else NOTICE_SOURCE_REF,
            "request_time_pacific": "",
            "request_status": "massivefold_external_model_set_available" if r2345 else "not_seen_in_links",
            "sequence_gate": "keep_invalid_0930_request_quarantined",
            "action": "track_external_set_separately_from_internal_prediction_lane",
            "competitive_proof_policy": MASSIVEFOLD_INTERNAL_PREDICTION_POLICY,
            "notes": _text(r2345.get("massivefold_tarball_url")),
        },
    ]


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
        fieldnames = ["row_type", "target_id", "status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _target_folder_name(target_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", target_id.strip()).strip("_")
    return safe or "target"


def _target_markdown(target_id: str, notice_rows: list[dict[str, Any]], model_rows: list[dict[str, Any]]) -> str:
    lines = [
        f"# {target_id} Organizer Notice",
        "",
        "## Guardrails",
        "",
        f"- model_pool_policy: `{MASSIVEFOLD_MODEL_POOL_POLICY}`",
        f"- internal_prediction_policy: `{MASSIVEFOLD_INTERNAL_PREDICTION_POLICY}`",
        f"- submission_policy: `{MASSIVEFOLD_SUBMISSION_POLICY}`",
        f"- large_download_policy: `{LARGE_DOWNLOAD_POLICY}`",
        "",
        "## Notices",
        "",
        "| notice_id | type | status | action |",
        "| - | - | - | - |",
    ]
    for row in notice_rows:
        lines.append(
            f"| `{row['notice_id']}` | `{row['notice_type']}` | `{row['request_status']}` | `{row['action']}` |"
        )
    if not notice_rows:
        lines.append("| - | - | - | - |")
    lines.extend(["", "## MassiveFold Model Sets", "", "| model_set | bundle | size_bytes | url |", "| - | - | - | - |"])
    for row in model_rows:
        lines.append(
            f"| `{row['model_set_id']}` | `{row['bundle_format']}` | `{row.get('ftp_size_bytes') or ''}` | `{row['massivefold_tarball_url']}` |"
        )
    if not model_rows:
        lines.append("| - | - | - | - |")
    lines.append("")
    return "\n".join(lines)


def _write_target_packets(out_dir: str | Path, notice_rows: list[dict[str, Any]], model_rows: list[dict[str, Any]]) -> int:
    grouped_notice: dict[str, list[dict[str, Any]]] = {}
    grouped_models: dict[str, list[dict[str, Any]]] = {}
    for row in notice_rows:
        grouped_notice.setdefault(_text(row.get("target_id")), []).append(row)
    for row in model_rows:
        grouped_models.setdefault(_text(row.get("primary_target_id")), []).append(row)

    target_ids = sorted({target for target in [*grouped_notice, *grouped_models] if target})
    root = _resolve(out_dir)
    for target_id in target_ids:
        folder = root / _target_folder_name(target_id)
        folder.mkdir(parents=True, exist_ok=True)
        notices = grouped_notice.get(target_id, [])
        models = grouped_models.get(target_id, [])
        (folder / "NOTICE.md").write_text(_target_markdown(target_id, notices, models), encoding="utf-8")
        _write_csv(folder / "notice_rows.csv", notices)
        _write_csv(folder / "massivefold_model_sets.csv", models)
    return len(target_ids)


def _first_model_url(rows: list[dict[str, Any]], target_id: str) -> str:
    for row in rows:
        if row.get("primary_target_id") == target_id:
            return _text(row.get("massivefold_tarball_url"))
    return ""


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    notices = payload["notice_rows"]
    models = payload["massivefold_rows"]
    lines = [
        "# CASP17 Organizer Notice Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- organizer_notice_status: `{summary['organizer_notice_status']}`",
        f"- source_notice_ref: `{summary['source_notice_ref']}`",
        f"- R2345 first request: `{summary['r2345_first_request_status']}`",
        f"- R2345 replacement request: `{summary['r2345_replacement_request_status']}`",
        f"- MassiveFold links: `{summary['massivefold_link_count']}` RNA/hybrid `{summary['massivefold_rna_hybrid_link_count']}` protein/complex `{summary['massivefold_protein_complex_link_count']}`",
        f"- R2341 available: `{summary['massivefold_r2341_link_present']}` `{summary['massivefold_r2341_tarball_url']}`",
        f"- R2345 available: `{summary['massivefold_r2345_link_present']}` `{summary['massivefold_r2345_tarball_url']}`",
        f"- model_pool_policy: `{summary['massivefold_model_pool_policy']}`",
        f"- internal_prediction_policy: `{summary['massivefold_internal_prediction_policy']}`",
        f"- submission_policy: `{summary['massivefold_submission_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Notice Rows",
        "",
        "| notice | target | type | status | action |",
        "| - | - | - | - | - |",
    ]
    for row in notices:
        lines.append(
            f"| `{row['notice_id']}` | `{row['target_id']}` | `{row['notice_type']}` | `{row['request_status']}` | `{row['action']}` |"
        )
    lines.extend(["", "## MassiveFold Links", "", "| model_set | category | bundle | size_bytes | url |", "| - | - | - | - | - |"])
    for row in models:
        lines.append(
            f"| `{row['model_set_id']}` | `{row['target_category']}` | `{row['bundle_format']}` | `{row.get('ftp_size_bytes') or ''}` | `{row['massivefold_tarball_url']}` |"
        )
    if not models:
        lines.append("| - | - | - | - | - |")
    lines.append("")
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    generated_at = dt.datetime.now().astimezone().replace(microsecond=0).isoformat()
    links_text, links_ref, links_status = _read_source(
        file_path=args.massivefold_links_csv,
        source_url=args.massivefold_links_url,
        timeout_seconds=args.timeout_seconds,
        allow_network=not args.no_network,
    )
    listing_text, listing_ref, listing_status = _read_source(
        file_path=args.ftp_listing_file,
        source_url=args.ftp_listing_url,
        timeout_seconds=args.timeout_seconds,
        allow_network=not args.no_network,
    )
    massivefold_rows = _parse_massivefold_links(links_text)
    _enrich_with_listing(massivefold_rows, _parse_ftp_listing(listing_text))
    notice_rows = _notice_rows(massivefold_rows)
    packet_folder_count = _write_target_packets(args.out_dir, notice_rows, massivefold_rows)

    rna_rows = [row for row in massivefold_rows if row["target_category"] == "rna_or_hybrid"]
    protein_rows = [row for row in massivefold_rows if row["target_category"] == "protein_or_complex"]
    r2341_url = _first_model_url(massivefold_rows, "R2341")
    r2345_url = _first_model_url(massivefold_rows, "R2345")
    status = "organizer_notice_intake_ready" if notice_rows else "blocked_no_notice_rows"
    if not massivefold_rows:
        status = "organizer_notice_ready_massivefold_links_missing"

    summary = {
        "packet_type": "casp17_organizer_notice_packet",
        "generated_at_local": generated_at,
        "organizer_notice_status": status,
        "source_notice_ref": NOTICE_SOURCE_REF,
        "massivefold_links_source_ref": links_ref,
        "massivefold_links_load_status": links_status,
        "massivefold_ftp_listing_source_ref": listing_ref,
        "massivefold_ftp_listing_load_status": listing_status,
        "r2345_first_request_status": R2345_INVALID_REQUEST_STATUS,
        "r2345_replacement_request_status": R2345_REPLACEMENT_REQUEST_STATUS,
        "r2345_sequence_validation_gate": "rna_sequence_requires_acgu_no_t",
        "massivefold_ftp_root": DEFAULT_MASSIVEFOLD_FTP_ROOT,
        "massivefold_link_count": len(massivefold_rows),
        "massivefold_rna_hybrid_link_count": len(rna_rows),
        "massivefold_protein_complex_link_count": len(protein_rows),
        "massivefold_r2341_link_present": bool(r2341_url),
        "massivefold_r2341_tarball_url": r2341_url,
        "massivefold_r2345_link_present": bool(r2345_url),
        "massivefold_r2345_tarball_url": r2345_url,
        "massivefold_model_pool_policy": MASSIVEFOLD_MODEL_POOL_POLICY,
        "massivefold_internal_prediction_policy": MASSIVEFOLD_INTERNAL_PREDICTION_POLICY,
        "massivefold_submission_policy": MASSIVEFOLD_SUBMISSION_POLICY,
        "large_download_policy": LARGE_DOWNLOAD_POLICY,
        "target_packet_folder_count": packet_folder_count,
        "out_dir": _artifact(args.out_dir),
        "next_action": (
            "keep R2345 09:30 Pacific request quarantined, validate the 11:30 Pacific RNA sequence, "
            "and treat MassiveFold tarballs as external rerank/accuracy-estimation pools until CASP rule use is checked"
        ),
        "claim_boundary": (
            "Organizer notice intake only; this does not download large MassiveFold tarballs, run predictors, "
            "submit CASP models, or convert external MassiveFold models into internal competitive-proof evidence."
        ),
    }
    return {"summary": summary, "notice_rows": notice_rows, "massivefold_rows": massivefold_rows, "rows": notice_rows}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the CASP17 organizer notice and MassiveFold external-pool packet.")
    parser.add_argument("--massivefold-links-csv", default="")
    parser.add_argument("--massivefold-links-url", default=DEFAULT_MASSIVEFOLD_LINKS_URL)
    parser.add_argument("--ftp-listing-file", default="")
    parser.add_argument("--ftp-listing-url", default=DEFAULT_MASSIVEFOLD_FTP_ROOT)
    parser.add_argument("--timeout-seconds", type=int, default=20)
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    rows: list[dict[str, Any]] = []
    for row in payload["notice_rows"]:
        rows.append({"row_type": "organizer_notice", **row})
    for row in payload["massivefold_rows"]:
        rows.append({"row_type": "massivefold_model_set", **row})
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, rows)
    _write_markdown(args.out_md, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
