#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_MANIFEST_CSV = "data/competition_benchmarks/casp16_ligand/source_manifest.csv"
DEFAULT_CHECKSUM_MANIFEST = "data/competition_benchmarks/casp16_ligand/checksums.sha256"
DEFAULT_OUT_JSON = "runs/casp16_ligand_materialization_manifest_current.json"
DEFAULT_OUT_CSV = "runs/casp16_ligand_materialization_manifest_current.csv"
DEFAULT_OUT_MD = "runs/casp16_ligand_materialization_manifest_current.md"

PACKET_TYPE = "casp16_ligand_materialization_manifest"
SCHEMA_VERSION = "casp16_ligand_materialization_manifest_v1"
REQUIRED_SOURCE_COLUMNS = ("target_id", "source_url", "sha256")
RAW_DATA_SUFFIXES = {
    ".pdb",
    ".cif",
    ".mmcif",
    ".sdf",
    ".mol",
    ".mol2",
    ".pdbqt",
    ".mae",
    ".maegz",
    ".xtc",
    ".trr",
    ".dcd",
    ".nc",
    ".tar",
    ".gz",
    ".tgz",
    ".zip",
    ".xz",
}
ALLOWED_COMMITTED_FILENAMES = {
    "source_manifest.csv",
    "checksums.sha256",
    "materialization_manifest.json",
    "materialization_manifest.md",
}

CLAIM_BOUNDARY = (
    "CASP16 ligand materialization manifest only; it validates operator-provided source and checksum "
    "manifests and confirms raw-data custody stays outside committed repository files. It does not "
    "download CASP data, read target structures, run docking, compute metrics, submit predictions, "
    "promote ligand commercial claims, or mutate external state outside requested receipt outputs."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = Path(path_like)
    if path.is_absolute():
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
    return str(path_like)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_source_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.is_file():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{str(k): _text(v) for k, v in row.items()} for row in reader]
        return rows, list(reader.fieldnames or [])


def _checksum_values(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    values: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        values.add(text.split()[0])
    return values


def _nearest_existing_path(path: Path) -> Path:
    current = path if path.exists() else path.parent
    while not current.exists() and current != current.parent:
        current = current.parent
    return current if current.exists() else Path.cwd()


def _git_root(path: Path) -> Path | None:
    probe = _nearest_existing_path(path)
    try:
        result = subprocess.run(
            ["git", "-C", str(probe), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()) if result.stdout.strip() else None


def _git_tracked_raw_files(path: Path) -> list[str]:
    root = _git_root(path)
    if root is None:
        return []
    try:
        relative = path.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return []
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--", str(relative)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    tracked: list[str] = []
    for line in result.stdout.splitlines():
        tracked_path = Path(line.strip())
        if not str(tracked_path):
            continue
        if tracked_path.name in ALLOWED_COMMITTED_FILENAMES:
            continue
        if tracked_path.suffix.lower() in RAW_DATA_SUFFIXES:
            tracked.append(str(tracked_path))
    return sorted(tracked)


def build_casp16_ligand_materialization_manifest(
    *,
    source_manifest_csv: str | Path = DEFAULT_SOURCE_MANIFEST_CSV,
    checksum_manifest: str | Path = DEFAULT_CHECKSUM_MANIFEST,
    min_source_rows: int = 1,
    root: Path = ROOT,
) -> dict[str, Any]:
    source_manifest = _resolve(source_manifest_csv, root=root)
    checksums = _resolve(checksum_manifest, root=root)
    source_rows, source_columns = _read_source_rows(source_manifest)
    checksum_values = _checksum_values(checksums)
    missing_required_columns = [
        column for column in REQUIRED_SOURCE_COLUMNS if column not in source_columns
    ]
    row_missing_value_count = sum(
        1
        for row in source_rows
        for column in REQUIRED_SOURCE_COLUMNS
        if not _text(row.get(column))
    )
    source_sha_values = {_text(row.get("sha256")) for row in source_rows if _text(row.get("sha256"))}
    checksum_missing_sha256 = sorted(value for value in source_sha_values if value not in checksum_values)
    tracked_raw_files = _git_tracked_raw_files(source_manifest.parent)

    blockers: list[str] = []
    if not source_manifest.is_file():
        blockers.append("source_manifest_csv_missing")
    if missing_required_columns:
        blockers.append("source_manifest_required_columns_missing")
    if len(source_rows) < int(min_source_rows):
        blockers.append("source_manifest_rows_below_minimum")
    if row_missing_value_count:
        blockers.append("source_manifest_required_values_missing")
    if not checksums.is_file():
        blockers.append("checksum_manifest_missing")
    if checksums.is_file() and not checksum_values:
        blockers.append("checksum_manifest_empty")
    if checksum_missing_sha256:
        blockers.append("checksum_manifest_missing_source_sha256")
    if tracked_raw_files:
        blockers.append("raw_data_committed_in_repo")
    blockers = sorted(set(blockers))

    materialization_ready = not blockers
    rows = [
        {
            "check": "source_manifest_csv_present",
            "status": "pass" if source_manifest.is_file() else "fail",
            "observed": _display(source_manifest, root=root),
            "required": "operator-reviewed CSV manifest",
        },
        {
            "check": "source_manifest_required_columns",
            "status": "pass" if not missing_required_columns else "fail",
            "observed": ";".join(source_columns),
            "required": ";".join(REQUIRED_SOURCE_COLUMNS),
        },
        {
            "check": "source_manifest_min_rows",
            "status": "pass" if len(source_rows) >= int(min_source_rows) else "fail",
            "observed": str(len(source_rows)),
            "required": str(int(min_source_rows)),
        },
        {
            "check": "checksum_manifest_covers_source_sha256",
            "status": "pass" if not checksum_missing_sha256 and bool(checksum_values) else "fail",
            "observed": str(len(checksum_values)),
            "required": "all source_manifest sha256 values",
        },
        {
            "check": "raw_data_custody",
            "status": "pass" if not tracked_raw_files else "fail",
            "observed": str(len(tracked_raw_files)),
            "required": "0 git-tracked raw CASP data files",
        },
    ]
    summary = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "casp16_ligand_materialization_ready"
        if materialization_ready
        else "blocked_casp16_ligand_materialization",
        "materialization_ready": materialization_ready,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "source_manifest_csv": _display(source_manifest, root=root),
        "source_manifest_csv_present": source_manifest.is_file(),
        "source_manifest_row_count": len(source_rows),
        "source_manifest_columns": source_columns,
        "missing_required_columns": missing_required_columns,
        "source_manifest_required_value_missing_count": row_missing_value_count,
        "checksum_manifest": _display(checksums, root=root),
        "checksum_manifest_present": checksums.is_file(),
        "checksum_manifest_line_count": len(checksum_values),
        "checksum_missing_sha256_count": len(checksum_missing_sha256),
        "checksum_missing_sha256_sample": checksum_missing_sha256[:10],
        "raw_data_committed": bool(tracked_raw_files),
        "raw_data_git_tracked_file_count": len(tracked_raw_files),
        "raw_data_git_tracked_sample_paths": tracked_raw_files[:10],
        "download_executed": False,
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "claim_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "scorecard_run_command_template": (
            "python3 tools/build_casp16_ligand_scorecard.py "
            f"--materialization-json {_display(DEFAULT_OUT_JSON, root=root)} "
            "--scorecard-rows-csv OPERATOR_REVIEWED_SCORECARD_ROWS_CSV "
            "--out-json runs/casp16_ligand_scorecard_current.json"
        ),
        "next_required_step": (
            "Build the reviewed CASP16 ligand scorecard receipt."
            if materialization_ready
            else "Fill source/checksum manifests with reviewed operator metadata, keep raw data out of git, and rebuild this receipt."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["check", "status", "observed", "required"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# CASP16 Ligand Materialization Manifest",
        "",
        f"- status: `{summary['status']}`",
        f"- materialization_ready: `{summary['materialization_ready']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- source_manifest_row_count: `{summary['source_manifest_row_count']}`",
        f"- checksum_manifest_line_count: `{summary['checksum_manifest_line_count']}`",
        f"- raw_data_git_tracked_file_count: `{summary['raw_data_git_tracked_file_count']}`",
        "",
        "| check | status | observed | required |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` |"
        )
    lines.extend(["", "## Blockers", ""])
    blockers = summary.get("blockers") or []
    lines.extend(f"- `{blocker}`" for blocker in blockers) if blockers else lines.append("- none")
    lines.extend(["", CLAIM_BOUNDARY, ""])
    return "\n".join(lines)


def _write_text(path_like: str | Path, text: str, *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a CASP16 ligand materialization receipt without downloads.")
    parser.add_argument("--source-manifest-csv", default=DEFAULT_SOURCE_MANIFEST_CSV)
    parser.add_argument("--checksum-manifest", default=DEFAULT_CHECKSUM_MANIFEST)
    parser.add_argument("--min-source-rows", default=1, type=int)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_casp16_ligand_materialization_manifest(
        source_manifest_csv=args.source_manifest_csv,
        checksum_manifest=args.checksum_manifest,
        min_source_rows=args.min_source_rows,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_text(args.out_md, _render_md(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
