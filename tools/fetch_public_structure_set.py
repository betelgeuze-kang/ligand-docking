#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tempfile
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from core.definitions import ResearchConstants


DEFAULT_PDB_IDS: Dict[str, str] = {
    "Chignolin": "1UAO",
    "Trp_Cage": "1L2Y",
    "Villin_HP35": "1YRF",
    "BBA5": "1T8J",
    "FSD_1": "1FSD",
    "WW_Domain_FiP35": "2F21",
    "Crambin": "1CRN",
    "Protein_A_Bdomain": "1BDD",
    "GB1_Mini": "2GB1",
    "Ubiquitin_Mini": "1UBQ",
}


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _slug_target(name: str) -> str:
    out: List[str] = []
    prev_us = False
    for ch in str(name).lower():
        if ch.isalnum():
            out.append(ch)
            prev_us = False
            continue
        if not prev_us:
            out.append("_")
            prev_us = True
    return ("".join(out).strip("_") or "target")


def _str_or_empty(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() == "nan":
        return ""
    return s


def _parse_targets(spec: str) -> List[str]:
    if str(spec).strip().lower() == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    return [x.strip() for x in str(spec).split(",") if x.strip()]


def _parse_afdb_model_versions(raw: str) -> List[str]:
    vals = [x.strip().lower() for x in str(raw).split(",") if x.strip()]
    out: List[str] = []
    for v in vals:
        if v.startswith("v") and len(v) > 1 and v[1:].isdigit():
            tag = v
        elif v.isdigit():
            tag = f"v{v}"
        else:
            continue
        if tag not in out:
            out.append(tag)
    if len(out) == 0:
        out = ["v6", "v5", "v4"]
    return out


def _write_template_sources_csv(path: str, targets: Sequence[str]) -> str:
    rows: List[Dict[str, Any]] = []
    for target in targets:
        rows.append(
            {
                "target": target,
                "pdb_id": DEFAULT_PDB_IDS.get(target, ""),
                "uniprot_id": "",
                "notes": "fill uniprot_id for AFDB download if available",
            }
        )
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _load_source_rows(sources_csv: str, targets: Sequence[str]) -> List[Dict[str, Any]]:
    if not os.path.exists(sources_csv):
        raise FileNotFoundError(f"sources csv not found: {sources_csv}")
    df = pd.read_csv(sources_csv)
    if "target" not in df.columns:
        raise ValueError(f"sources csv missing required column 'target': {sources_csv}")

    row_map: Dict[str, Dict[str, Any]] = {}
    for row in df.to_dict(orient="records"):
        target = _str_or_empty(row.get("target", ""))
        if not target:
            continue
        row_map[_normalize_target_key(target)] = row

    resolved: List[Dict[str, Any]] = []
    for target in targets:
        key = _normalize_target_key(target)
        row = dict(row_map.get(key, {}))
        row["target"] = target
        row.setdefault("pdb_id", "")
        row.setdefault("uniprot_id", "")
        resolved.append(row)
    return resolved


def _download_binary(url: str, out_path: str, timeout_sec: float) -> Tuple[int, str]:
    tmp_dir = os.path.dirname(out_path) or "."
    os.makedirs(tmp_dir, exist_ok=True)
    with urllib.request.urlopen(url, timeout=float(timeout_sec)) as resp:
        payload = resp.read()
    if len(payload) == 0:
        raise RuntimeError(f"empty payload: {url}")
    fd, tmp_path = tempfile.mkstemp(prefix=".dl_", suffix=".tmp", dir=tmp_dir)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
        os.replace(tmp_path, out_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return int(len(payload)), out_path


def _fetch_one(
    target: str,
    source_kind: str,
    source_id: str,
    url: str,
    out_path: str,
    timeout_sec: float,
    overwrite: bool,
    dry_run: bool,
) -> Dict[str, Any]:
    if os.path.exists(out_path) and (not overwrite):
        return {
            "target": target,
            "path": os.path.abspath(out_path),
            "source_kind": source_kind,
            "source_id": source_id,
            "url": url,
            "status": "exists",
            "error": "",
            "bytes": int(os.path.getsize(out_path)),
            "downloaded_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        }
    if dry_run:
        return {
            "target": target,
            "path": os.path.abspath(out_path),
            "source_kind": source_kind,
            "source_id": source_id,
            "url": url,
            "status": "dry_run",
            "error": "",
            "bytes": 0,
            "downloaded_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        }
    try:
        n_bytes, _ = _download_binary(url=url, out_path=out_path, timeout_sec=timeout_sec)
        return {
            "target": target,
            "path": os.path.abspath(out_path),
            "source_kind": source_kind,
            "source_id": source_id,
            "url": url,
            "status": "downloaded",
            "error": "",
            "bytes": int(n_bytes),
            "downloaded_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        }
    except urllib.error.HTTPError as exc:
        return {
            "target": target,
            "path": os.path.abspath(out_path),
            "source_kind": source_kind,
            "source_id": source_id,
            "url": url,
            "status": "failed",
            "error": f"http_{int(exc.code)}",
            "bytes": 0,
            "downloaded_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        }
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        return {
            "target": target,
            "path": os.path.abspath(out_path),
            "source_kind": source_kind,
            "source_id": source_id,
            "url": url,
            "status": "failed",
            "error": str(exc),
            "bytes": 0,
            "downloaded_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        }


def _fetch_one_with_fallback_urls(
    target: str,
    source_kind: str,
    source_id: str,
    urls: Sequence[str],
    out_path: str,
    timeout_sec: float,
    overwrite: bool,
    dry_run: bool,
) -> Dict[str, Any]:
    last_error = ""
    for idx, url in enumerate(urls):
        result = _fetch_one(
            target=target,
            source_kind=source_kind,
            source_id=source_id,
            url=str(url),
            out_path=out_path,
            timeout_sec=timeout_sec,
            overwrite=overwrite if idx == 0 else True,
            dry_run=dry_run,
        )
        if result.get("status") in {"downloaded", "exists", "dry_run"}:
            result["fallback_attempts"] = int(idx + 1)
            return result
        last_error = str(result.get("error", ""))
    return {
        "target": target,
        "path": os.path.abspath(out_path),
        "source_kind": source_kind,
        "source_id": source_id,
        "url": str(urls[-1]) if len(urls) > 0 else "",
        "status": "failed",
        "error": last_error or "all_fallback_urls_failed",
        "bytes": 0,
        "downloaded_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "fallback_attempts": int(len(urls)),
    }


def fetch_public_structure_set(
    sources_csv: str,
    targets_spec: str,
    out_dir: str,
    out_manifest_csv: str,
    out_summary_json: str,
    download_pdb: bool = True,
    download_afdb: bool = True,
    timeout_sec: float = 30.0,
    afdb_model_versions: str = "v6,v5,v4",
    overwrite: bool = False,
    dry_run: bool = False,
    strict: bool = False,
    write_template_if_missing: bool = True,
) -> Dict[str, Any]:
    targets = _parse_targets(targets_spec)
    if write_template_if_missing and (not os.path.exists(sources_csv)):
        _write_template_sources_csv(path=sources_csv, targets=targets)
    rows = _load_source_rows(sources_csv=sources_csv, targets=targets)
    afdb_versions = _parse_afdb_model_versions(afdb_model_versions)

    manifest_rows: List[Dict[str, Any]] = []
    requested = 0

    for row in rows:
        target = _str_or_empty(row.get("target", ""))
        slug = _slug_target(target)
        pdb_id = _str_or_empty(row.get("pdb_id", "")).upper()
        uniprot_id = _str_or_empty(row.get("uniprot_id", "")).upper()

        if bool(download_pdb) and pdb_id:
            requested += 1
            pdb_url = _str_or_empty(row.get("pdb_url", "")) or f"https://files.rcsb.org/download/{pdb_id}.pdb"
            pdb_path = os.path.join(out_dir, f"{slug}_pdb_{pdb_id}.pdb")
            result = _fetch_one(
                target=target,
                source_kind="pdb_or_other",
                source_id=pdb_id,
                url=pdb_url,
                out_path=pdb_path,
                timeout_sec=float(timeout_sec),
                overwrite=bool(overwrite),
                dry_run=bool(dry_run),
            )
            result["pdb_id"] = pdb_id
            result["uniprot_id"] = uniprot_id
            manifest_rows.append(result)

        if bool(download_afdb) and uniprot_id:
            requested += 1
            afdb_url_raw = _str_or_empty(row.get("afdb_url", ""))
            afdb_urls = [afdb_url_raw] if afdb_url_raw else [
                f"https://alphafold.ebi.ac.uk/files/AF-{uniprot_id}-F1-model_{v}.pdb"
                for v in afdb_versions
            ]
            afdb_path = os.path.join(out_dir, f"{slug}_afdb_{uniprot_id}.pdb")
            result = _fetch_one_with_fallback_urls(
                target=target,
                source_kind="afdb",
                source_id=uniprot_id,
                urls=afdb_urls,
                out_path=afdb_path,
                timeout_sec=float(timeout_sec),
                overwrite=bool(overwrite),
                dry_run=bool(dry_run),
            )
            result["pdb_id"] = pdb_id
            result["uniprot_id"] = uniprot_id
            manifest_rows.append(result)

    os.makedirs(os.path.dirname(out_manifest_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_summary_json) or ".", exist_ok=True)
    if len(manifest_rows) > 0:
        pd.DataFrame(manifest_rows).to_csv(out_manifest_csv, index=False)
    else:
        pd.DataFrame(
            columns=[
                "target",
                "path",
                "source_kind",
                "source_id",
                "url",
                "status",
                "error",
                "bytes",
                "downloaded_at_local",
                "pdb_id",
                "uniprot_id",
            ]
        ).to_csv(out_manifest_csv, index=False)

    downloaded_count = int(sum(1 for r in manifest_rows if r["status"] == "downloaded"))
    exists_count = int(sum(1 for r in manifest_rows if r["status"] == "exists"))
    dry_run_count = int(sum(1 for r in manifest_rows if r["status"] == "dry_run"))
    failed_rows = [r for r in manifest_rows if r["status"] == "failed"]
    summary: Dict[str, Any] = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "sources_csv": os.path.abspath(sources_csv),
        "targets": targets,
        "target_count": int(len(targets)),
        "requested_sources": int(requested),
        "rows_emitted": int(len(manifest_rows)),
        "downloaded_count": downloaded_count,
        "exists_count": exists_count,
        "dry_run_count": dry_run_count,
        "failed_count": int(len(failed_rows)),
        "failed_targets": sorted({str(r["target"]) for r in failed_rows}),
        "out_manifest_csv": out_manifest_csv,
        "out_summary_json": out_summary_json,
        "out_dir": os.path.abspath(out_dir),
        "policies": {
            "download_pdb": bool(download_pdb),
            "download_afdb": bool(download_afdb),
            "afdb_model_versions": afdb_versions,
            "timeout_sec": float(timeout_sec),
            "overwrite": bool(overwrite),
            "dry_run": bool(dry_run),
            "strict": bool(strict),
            "write_template_if_missing": bool(write_template_if_missing),
        },
    }
    with open(out_summary_json, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": manifest_rows}, f, indent=2, ensure_ascii=False)

    if strict and len(failed_rows) > 0:
        ex = failed_rows[0]
        raise RuntimeError(
            "public structure fetch strict failure: "
            f"target={ex['target']} kind={ex['source_kind']} status={ex['status']} error={ex['error']}"
        )
    return {"summary": summary, "rows": manifest_rows}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch public structure files (RCSB PDB and optional AFDB) and build a curation-ready manifest."
        )
    )
    parser.add_argument("--sources-csv", type=str, default="config/structure_sources_10targets.csv")
    parser.add_argument("--targets", type=str, default="all")
    parser.add_argument("--out-dir", type=str, default="data/public_structures")
    parser.add_argument("--out-manifest-csv", type=str, default="runs/structure_sources_public_manifest.csv")
    parser.add_argument("--out-summary-json", type=str, default="runs/structure_sources_public_summary.json")
    parser.add_argument("--download-pdb", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--download-afdb", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--afdb-model-versions",
        type=str,
        default="v6,v5,v4",
        help="Fallback AFDB model versions, comma-separated (e.g. v6,v5,v4).",
    )
    parser.add_argument("--timeout-sec", type=float, default=30.0)
    parser.add_argument("--overwrite", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--strict", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--write-template-if-missing", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = fetch_public_structure_set(
        sources_csv=str(args.sources_csv),
        targets_spec=str(args.targets),
        out_dir=str(args.out_dir),
        out_manifest_csv=str(args.out_manifest_csv),
        out_summary_json=str(args.out_summary_json),
        download_pdb=bool(args.download_pdb),
        download_afdb=bool(args.download_afdb),
        afdb_model_versions=str(args.afdb_model_versions),
        timeout_sec=float(args.timeout_sec),
        overwrite=bool(args.overwrite),
        dry_run=bool(args.dry_run),
        strict=bool(args.strict),
        write_template_if_missing=bool(args.write_template_if_missing),
    )
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
