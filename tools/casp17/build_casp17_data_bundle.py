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

DEFAULT_RUNS_DIR = "runs"
DEFAULT_DOCS_DIR = "docs"
DEFAULT_CONFIG_DIR = "config"
DEFAULT_OUT_DIR = "casp17"
DEFAULT_OUT_JSON = "casp17/casp17_data_bundle_manifest_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_data_bundle_manifest_current.csv"
DEFAULT_OUT_MD = "casp17/README.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _safe_name(path: Path) -> str:
    return path.name.strip() or "artifact"


def _iter_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.exists():
        return []
    return [child for child in path.rglob("*") if child.is_file()]


def _size_bytes(path: Path) -> int:
    return sum(child.stat().st_size for child in _iter_files(path))


def _file_count(path: Path) -> int:
    return len(_iter_files(path))


def _discover_runs_artifacts(runs_dir: str | Path, prefix: str) -> list[Path]:
    root = _resolve(runs_dir)
    if not root.exists():
        return []
    return sorted(path for path in root.iterdir() if path.name.startswith(prefix))


def _discover_docs_artifacts(docs_dir: str | Path, pattern: str) -> list[Path]:
    root = _resolve(docs_dir)
    if not root.exists():
        return []
    return sorted(path for path in root.glob(pattern))


def _copy_artifact(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(source, destination)


def _row_for(source: Path, destination: Path, group: str, *, copied: bool) -> dict[str, Any]:
    source_exists = source.exists()
    destination_exists = destination.exists()
    return {
        "group": group,
        "name": source.name,
        "kind": "directory" if source.is_dir() else "file",
        "source_path": _artifact(source),
        "bundle_path": _artifact(destination),
        "source_exists": bool(source_exists),
        "bundle_exists": bool(destination_exists),
        "copied_this_run": bool(copied),
        "file_count": _file_count(source) if source_exists else 0,
        "size_bytes": _size_bytes(source) if source_exists else 0,
    }


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
        fieldnames = ["group", "name", "source_path", "bundle_path"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    rows = payload["rows"]
    lines = [
        "# CASP17 Data Bundle",
        "",
        "This folder mirrors the current local CASP17 data artifacts while keeping the original project paths intact.",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- bundle_status: `{summary['bundle_status']}`",
        f"- out_dir: `{summary['out_dir']}`",
        f"- run artifact count: `{summary['runs_artifact_count']}`",
        f"- doc artifact count: `{summary['docs_artifact_count']}`",
        f"- config artifact count: `{summary['config_artifact_count']}`",
        f"- total top-level artifacts: `{summary['artifact_count']}`",
        f"- total files under bundled artifacts: `{summary['file_count']}`",
        f"- total bytes under bundled artifacts: `{summary['size_bytes']}`",
        "",
        "## Layout",
        "",
        "- `runs/`: mirror of top-level `runs/casp17*` artifacts.",
        "- `docs/`: mirror of CASP17 documentation artifacts.",
        "- `config/`: mirror of CASP17 configuration/template artifacts.",
        "- `casp17_data_bundle_manifest_current.json`: machine-readable manifest.",
        "- `casp17_data_bundle_manifest_current.csv`: tabular manifest.",
        "",
        "## Claim Boundary",
        "",
        str(summary["claim_boundary"]),
        "",
        "## Artifacts",
        "",
        "| group | name | kind | files | bytes | source | bundled |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['group']}` | `{row['name']}` | `{row['kind']}` | {row['file_count']} | {row['size_bytes']} | "
            f"`{row['source_path']}` | `{row['bundle_path']}` |"
        )
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = _resolve(args.out_dir)
    runs_out = out_dir / "runs"
    docs_out = out_dir / "docs"
    config_out = out_dir / "config"
    run_sources = _discover_runs_artifacts(args.runs_dir, args.runs_prefix)
    doc_sources = _discover_docs_artifacts(args.docs_dir, args.docs_pattern)
    config_sources = _discover_docs_artifacts(args.config_dir, args.config_pattern)
    rows: list[dict[str, Any]] = []
    for source in run_sources:
        destination = runs_out / _safe_name(source)
        if not args.manifest_only:
            _copy_artifact(source, destination)
        rows.append(_row_for(source, destination, "runs", copied=not args.manifest_only))
    for source in doc_sources:
        destination = docs_out / _safe_name(source)
        if not args.manifest_only:
            _copy_artifact(source, destination)
        rows.append(_row_for(source, destination, "docs", copied=not args.manifest_only))
    for source in config_sources:
        destination = config_out / _safe_name(source)
        if not args.manifest_only:
            _copy_artifact(source, destination)
        rows.append(_row_for(source, destination, "config", copied=not args.manifest_only))
    missing_bundle_count = sum(1 for row in rows if not row["bundle_exists"])
    summary = {
        "packet_type": "casp17_data_bundle_manifest",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "bundle_status": "ready" if rows and missing_bundle_count == 0 else "blocked",
        "out_dir": _artifact(out_dir),
        "runs_dir": _artifact(args.runs_dir),
        "docs_dir": _artifact(args.docs_dir),
        "config_dir": _artifact(args.config_dir),
        "runs_prefix": args.runs_prefix,
        "docs_pattern": args.docs_pattern,
        "config_pattern": args.config_pattern,
        "manifest_only": bool(args.manifest_only),
        "artifact_count": len(rows),
        "runs_artifact_count": sum(1 for row in rows if row["group"] == "runs"),
        "docs_artifact_count": sum(1 for row in rows if row["group"] == "docs"),
        "config_artifact_count": sum(1 for row in rows if row["group"] == "config"),
        "file_count": sum(int(row["file_count"]) for row in rows),
        "size_bytes": sum(int(row["size_bytes"]) for row in rows),
        "missing_bundle_count": missing_bundle_count,
        "manifest_json": _artifact(args.out_json),
        "manifest_csv": _artifact(args.out_csv),
        "readme_md": _artifact(args.out_md),
        "claim_boundary": "Local CASP17 data mirror only; originals remain in place, no external data is fetched, no CASP submission is performed, and no native/current-target accuracy claim is implied.",
    }
    return {"summary": summary, "rows": rows}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mirror current local CASP17 data artifacts into a casp17/ folder.")
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS_DIR)
    parser.add_argument("--docs-dir", default=DEFAULT_DOCS_DIR)
    parser.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--runs-prefix", default="casp17")
    parser.add_argument("--docs-pattern", default="*casp17*")
    parser.add_argument("--config-pattern", default="casp17*")
    parser.add_argument("--manifest-only", action="store_true")
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


if __name__ == "__main__":
    main()
