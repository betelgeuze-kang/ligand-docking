#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
APPROVAL_TOKEN = "APPROVE_PUBLIC_BENCHMARK_NATIVE_STRUCTURE_DOWNLOAD"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, destination: Path, *, timeout_seconds: int, overwrite: bool) -> tuple[bool, str]:
    if destination.exists() and not overwrite:
        return False, "already_present"
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "betelgeuze-public-benchmark-fetch/1.0"})
    with urllib.request.urlopen(request, timeout=int(timeout_seconds)) as response:
        payload = response.read()
    if not payload:
        raise RuntimeError(f"empty payload from {url}")
    fd, tmp_name = tempfile.mkstemp(prefix=".native_", suffix=".tmp", dir=str(destination.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.replace(tmp_path, destination)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return True, "downloaded"


def fetch_native(args: argparse.Namespace) -> dict[str, Any]:
    out_pdb = _resolve(args.out_pdb)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    pdb_id = _text(args.pdb_id).upper()
    source_url = _text(args.source_url) or f"https://files.rcsb.org/download/{pdb_id}.pdb"
    approval_granted = os.environ.get(APPROVAL_TOKEN) == "1"
    blockers: list[str] = []
    if not pdb_id:
        blockers.append("pdb_id_missing")
    if not source_url:
        blockers.append("source_url_missing")
    if not approval_granted:
        blockers.append("approval_token_missing")

    download_executed = False
    fetch_status = "blocked"
    if not blockers:
        download_executed, fetch_status = _download(
            source_url,
            out_pdb,
            timeout_seconds=int(args.timeout_seconds),
            overwrite=bool(args.overwrite),
        )

    present = out_pdb.exists() and out_pdb.is_file()
    size_bytes = out_pdb.stat().st_size if present else 0
    summary = {
        "packet_type": "public_benchmark_native_structure_fetch",
        "suite_id": _text(args.suite_id),
        "target": _text(args.target),
        "pdb_id": pdb_id,
        "status": "public_benchmark_native_structure_ready" if present and not blockers else "blocked_public_benchmark_native_structure_fetch",
        "blocker_count": len(blockers),
        "blockers": blockers,
        "approval_token_required": APPROVAL_TOKEN,
        "approval_granted": approval_granted,
        "source_url": source_url,
        "out_pdb": str(out_pdb),
        "out_pdb_present": present,
        "out_pdb_size_bytes": size_bytes,
        "out_pdb_sha256": _sha256(out_pdb) if present else "",
        "fetch_status": fetch_status,
        "download_executed": download_executed,
        "external_state_mutated": False,
        "claim_boundary": (
            "Approved public benchmark native-structure acquisition only; this writes a local PDB and provenance "
            "artifacts. It does not run docking, submit predictions, register servers, or send email."
        ),
        "next_required_step": (
            "Rebuild the DUD-E-Z product smoke input preflight with this native PDB path."
            if present and not blockers
            else f"Set {APPROVAL_TOKEN}=1 and rerun this fetch command."
        ),
    }
    payload = {"summary": summary}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        "\n".join(
            [
                "# Public Benchmark Native Structure Fetch",
                "",
                f"- status: `{summary['status']}`",
                f"- suite_id: `{summary['suite_id']}`",
                f"- target: `{summary['target']}`",
                f"- pdb_id: `{summary['pdb_id']}`",
                f"- out_pdb_present: `{summary['out_pdb_present']}`",
                f"- out_pdb_size_bytes: `{summary['out_pdb_size_bytes']}`",
                f"- download_executed: `{summary['download_executed']}`",
                f"- approval_granted: `{summary['approval_granted']}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch an approved public benchmark native PDB with provenance.")
    parser.add_argument("--suite-id", default="dude_z_decoy_smoke")
    parser.add_argument("--target", default="AA2AR")
    parser.add_argument("--pdb-id", default="3EML")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--out-pdb", default="data/native/aa2ar.pdb")
    parser.add_argument("--out-json", default="runs/dude_z_decoy_smoke_native_fetch_current.json")
    parser.add_argument("--out-md", default="runs/dude_z_decoy_smoke_native_fetch_current.md")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--overwrite", action=argparse.BooleanOptionalAction, default=False)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    fetch_native(parse_args(argv))


if __name__ == "__main__":
    main()
