#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INTAKE_CSV = "runs/casp17_target_intake_seed_current.csv"
DEFAULT_OUT_DIR = "runs/casp17_sequences_current"
DEFAULT_OUT_JSON = "runs/casp17_sequence_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_sequence_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_sequence_packet_current.md"
DEFAULT_OUT_INTAKE_CSV = "runs/casp17_target_intake_seed_with_sequences_current.csv"
DEFAULT_SEQUENCE_URL_TEMPLATE = "https://predictioncenter.org/casp17/target.cgi?target={target_id}&view=sequence"


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


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _fetch_sequence(target_id: str, args: argparse.Namespace) -> tuple[str, str]:
    source_dir = _text(args.sequence_source_dir)
    if source_dir:
        path = _resolve(source_dir) / f"{target_id}.fasta"
        return path.read_text(encoding="utf-8"), _artifact(path)
    url = args.sequence_url_template.format(target_id=quote(target_id))
    with urlopen(url, timeout=args.timeout_seconds) as response:
        return response.read().decode("utf-8", errors="replace"), url


def _normalize_fasta(raw_text: str) -> str:
    lines: list[str] = []
    for raw_line in raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            lines.append(line)
        else:
            sequence = re.sub(r"[^A-Za-z*.-]", "", line).upper()
            if sequence:
                for start in range(0, len(sequence), 80):
                    lines.append(sequence[start : start + 80])
    return "\n".join(lines).strip() + "\n" if lines else ""


def _sequence_stats(fasta_text: str) -> dict[str, Any]:
    entry_count = sum(1 for line in fasta_text.splitlines() if line.startswith(">"))
    residue_count = 0
    for line in fasta_text.splitlines():
        if line.startswith(">"):
            continue
        residue_count += len(re.sub(r"[^A-Z*.-]", "", line.upper()))
    return {
        "entry_count": entry_count,
        "residue_count": residue_count,
        "valid_fasta": entry_count > 0 and residue_count > 0 and fasta_text.startswith(">"),
    }


def _target_rows(args: argparse.Namespace) -> list[dict[str, str]]:
    rows = [row for row in _read_csv(args.intake_csv) if _text(row.get("target_id"))]
    if args.target_limit and args.target_limit > 0:
        rows = rows[: args.target_limit]
    return rows


def build_payload(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, str]]]:
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = _target_rows(args)
    manifest_rows: list[dict[str, Any]] = []
    enriched_rows: list[dict[str, str]] = []

    for row in rows:
        target_id = _text(row.get("target_id"))
        enriched = dict(row)
        out_fasta = out_dir / f"{target_id}.fasta"
        status = "failed"
        source = ""
        error = ""
        stats = {"entry_count": 0, "residue_count": 0, "valid_fasta": False}
        try:
            raw_text, source = _fetch_sequence(target_id, args)
            fasta_text = _normalize_fasta(raw_text)
            stats = _sequence_stats(fasta_text)
            if not stats["valid_fasta"]:
                raise ValueError("Fetched sequence is not valid FASTA.")
            out_fasta.write_text(fasta_text, encoding="utf-8")
            status = "ready"
            enriched["sequence_path"] = _artifact(out_fasta)
            enriched["notes"] = (_text(enriched.get("notes")) + " Sequence materialized from CASP17 target page.").strip()
        except Exception as exc:  # noqa: BLE001 - packet records per-target fetch failures without hiding them.
            error = f"{type(exc).__name__}: {exc}"
        enriched_rows.append(enriched)
        manifest_rows.append(
            {
                "target_id": target_id,
                "lane": _text(row.get("lane")),
                "sequence_status": status,
                "sequence_source": source,
                "sequence_path": _artifact(out_fasta) if status == "ready" else "",
                "entry_count": stats["entry_count"],
                "residue_count": stats["residue_count"],
                "valid_fasta": stats["valid_fasta"],
                "error": error,
            }
        )

    ready_count = sum(1 for row in manifest_rows if row["sequence_status"] == "ready")
    summary = {
        "packet_type": "casp17_sequence_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "intake_csv": _artifact(args.intake_csv),
        "out_dir": _artifact(out_dir),
        "target_count": len(manifest_rows),
        "sequence_ready_count": ready_count,
        "sequence_failed_count": len(manifest_rows) - ready_count,
        "target_limit": args.target_limit,
        "claim_boundary": "Sequence materialization only; not a CASP17 prediction or submission.",
    }
    return {"summary": summary, "rows": manifest_rows}, manifest_rows, enriched_rows


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Sequence Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- intake CSV: `{summary['intake_csv']}`",
        f"- output directory: `{summary['out_dir']}`",
        f"- sequence ready/failed: `{summary['sequence_ready_count']}/{summary['sequence_failed_count']}`",
        "",
        "## Targets",
        "",
        "| target | lane | status | entries | residues | sequence path | error |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['lane']}` | `{row['sequence_status']}` | {row['entry_count']} | "
            f"{row['residue_count']} | `{row['sequence_path'] or '-'}` | {row['error'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `no_targets` | 0 | 0 | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize CASP17 target FASTA sequences and enrich intake rows.")
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--sequence-source-dir", default="", help="Optional local directory with <target_id>.fasta files for tests/offline runs.")
    parser.add_argument("--sequence-url-template", default=DEFAULT_SEQUENCE_URL_TEMPLATE)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--target-limit", type=int, default=0, help="Limit targets for a quick first-pass fetch; 0 means all.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-intake-csv", default=DEFAULT_OUT_INTAKE_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload, manifest_rows, enriched_rows = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, manifest_rows)
    fieldnames = list(enriched_rows[0].keys()) if enriched_rows else []
    _write_csv(args.out_intake_csv, enriched_rows, fieldnames=fieldnames)
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
