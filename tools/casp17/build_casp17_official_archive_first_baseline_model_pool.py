#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import tarfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_ACQUISITION_JSON = "casp17/casp17_official_archive_first_baseline_acquisition_audit_current.json"
DEFAULT_OUT_DIR = "casp17/official_archive_first_baseline_model_pool"
DEFAULT_OUT_JSON = "casp17/casp17_official_archive_first_baseline_model_pool_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_official_archive_first_baseline_model_pool_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_OFFICIAL_ARCHIVE_FIRST_BASELINE_MODEL_POOL.md"

CLAIM_BOUNDARY = (
    "Local CASP17 official-archive first baseline model-pool extraction only. It extracts external "
    "CASP archive submissions into a baseline replay folder and builds model1/top5 manifests. It "
    "does not import official archive models as internal predictions, fill strict-blind operator "
    "values, compute native accuracy, push remotes, or submit to CASP."
)
RULE_ID = "official_archive_first_baseline_model_pool_v1"
MODEL_NAME_RE = re.compile(r"^(?P<target>[^/]+)/(?P<model>(?P=target)TS(?P<group>[^_]+)_(?P<num>\d+))$")

ROW_COLUMNS = [
    "model_rank",
    "model_id",
    "target_id",
    "group_id",
    "model_number",
    "pool_role",
    "source_member",
    "extracted_pdb",
    "size_bytes",
    "sha256_16",
    "atom_count",
    "ca_count",
    "residue_count",
    "chain_count",
    "model1_candidate",
    "top5_candidate",
    "extra_model_candidate",
    "model_status",
    "blockers",
    "claim_boundary",
    "rule_id",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like).strip():
        return ""
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
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


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _sha256_16_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _pdb_stats(path: Path) -> dict[str, int]:
    atoms = 0
    ca = 0
    residues: set[tuple[str, str, str]] = set()
    chains: set[str] = set()
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if not line.startswith(("ATOM  ", "HETATM")):
                continue
            atoms += 1
            atom_name = line[12:16].strip()
            if atom_name == "CA":
                ca += 1
            chain = line[21].strip() or "_"
            resseq = line[22:26].strip()
            icode = line[26].strip()
            residues.add((chain, resseq, icode))
            chains.add(chain)
    return {
        "atom_count": atoms,
        "ca_count": ca,
        "residue_count": len(residues),
        "chain_count": len(chains),
    }


def _safe_model_rows(tarball: Path, extract_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with tarfile.open(tarball, "r:gz") as archive:
        members = [member for member in archive.getmembers() if member.isfile()]
        for member in sorted(members, key=lambda item: item.name):
            match = MODEL_NAME_RE.match(member.name)
            if not match:
                rows.append(
                    {
                        "model_rank": 0,
                        "model_id": Path(member.name).name,
                        "target_id": "",
                        "group_id": "",
                        "model_number": 0,
                        "pool_role": "unparsed_member",
                        "source_member": member.name,
                        "extracted_pdb": "",
                        "size_bytes": 0,
                        "sha256_16": "",
                        "atom_count": 0,
                        "ca_count": 0,
                        "residue_count": 0,
                        "chain_count": 0,
                        "model1_candidate": "False",
                        "top5_candidate": "False",
                        "extra_model_candidate": "False",
                        "model_status": "blocked_unparsed_member_name",
                        "blockers": "unparsed_member_name",
                        "claim_boundary": CLAIM_BOUNDARY,
                        "rule_id": RULE_ID,
                    }
                )
                continue
            model_id = match.group("model")
            target_id = match.group("target")
            group_id = match.group("group")
            model_number = _int(match.group("num"))
            data_file = archive.extractfile(member)
            if data_file is None:
                data = b""
            else:
                data = data_file.read()
            target_path = extract_dir / target_id / "all_models" / f"{model_id}.pdb"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(data)
            stats = _pdb_stats(target_path)
            blockers = []
            if not data:
                blockers.append("empty_member")
            if stats["atom_count"] == 0:
                blockers.append("no_atom_records")
            if model_number <= 0:
                blockers.append("invalid_model_number")
            top5 = 1 <= model_number <= 5
            model1 = model_number == 1
            role = "model1" if model1 else ("top5" if top5 else "extra_model")
            rows.append(
                {
                    "model_rank": 0,
                    "model_id": model_id,
                    "target_id": target_id,
                    "group_id": group_id,
                    "model_number": model_number,
                    "pool_role": role,
                    "source_member": member.name,
                    "extracted_pdb": _artifact(target_path),
                    "size_bytes": target_path.stat().st_size,
                    "sha256_16": _sha256_16_bytes(data),
                    "atom_count": stats["atom_count"],
                    "ca_count": stats["ca_count"],
                    "residue_count": stats["residue_count"],
                    "chain_count": stats["chain_count"],
                    "model1_candidate": str(model1),
                    "top5_candidate": str(top5),
                    "extra_model_candidate": str(not top5),
                    "model_status": "model_ready" if not blockers else "blocked_model_file",
                    "blockers": ",".join(blockers),
                    "claim_boundary": CLAIM_BOUNDARY,
                    "rule_id": RULE_ID,
                }
            )
    return sorted(rows, key=lambda row: (row["target_id"], row["group_id"], int(row["model_number"]), row["model_id"]))


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], columns: list[str] = ROW_COLUMNS) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _group_counts(rows: list[dict[str, Any]]) -> tuple[int, int, int]:
    by_group: dict[str, set[int]] = {}
    for row in rows:
        if row["model_status"] != "model_ready":
            continue
        by_group.setdefault(_text(row["group_id"]), set()).add(_int(row["model_number"]))
    group_count = len(by_group)
    groups_with_model1 = sum(1 for nums in by_group.values() if 1 in nums)
    complete_top5_group_count = sum(1 for nums in by_group.values() if {1, 2, 3, 4, 5}.issubset(nums))
    return group_count, groups_with_model1, complete_top5_group_count


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    acquisition_payload = _read_json(args.acquisition_json)
    acquisition_summary = _summary(acquisition_payload)
    tarball = _resolve(_text(acquisition_summary.get("tarball_path")))
    native = _resolve(_text(acquisition_summary.get("native_pdb_path")))
    extract_dir = _resolve(args.out_dir) / "extracted_models"
    rows = _safe_model_rows(tarball, extract_dir) if tarball.exists() else []
    for rank, row in enumerate(rows, start=1):
        row["model_rank"] = rank
    ready_rows = [row for row in rows if row["model_status"] == "model_ready"]
    model1_rows = [row for row in ready_rows if row["model_number"] == 1]
    top5_rows = [row for row in ready_rows if 1 <= row["model_number"] <= 5]
    extra_rows = [row for row in ready_rows if row["model_number"] > 5]
    group_count, groups_with_model1, complete_top5_group_count = _group_counts(rows)
    expected_models = _int(acquisition_summary.get("tarball_model_count"))
    status = (
        "official_archive_first_baseline_model_pool_ready"
        if rows and len(ready_rows) == expected_models and expected_models > 0
        else "official_archive_first_baseline_model_pool_incomplete"
    )
    model1_manifest = _resolve(args.out_dir) / "model1_manifest.csv"
    top5_manifest = _resolve(args.out_dir) / "top5_manifest.csv"
    all_manifest = _resolve(args.out_dir) / "all_models_manifest.csv"
    summary = {
        "packet_type": "casp17_official_archive_first_baseline_model_pool",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_archive_first_baseline_model_pool_status": status,
        "acquisition_json": _artifact(args.acquisition_json),
        "acquisition_status": _text(
            acquisition_summary.get("official_archive_first_baseline_acquisition_audit_status")
        ),
        "first_baseline_candidate_id": _text(acquisition_summary.get("first_baseline_candidate_id")),
        "first_competition": _text(acquisition_summary.get("first_competition")),
        "first_target_id": _text(acquisition_summary.get("first_target_id")),
        "first_native_pdb_code": _text(acquisition_summary.get("first_native_pdb_code")),
        "competitive_proof_eligible": bool(acquisition_summary.get("competitive_proof_eligible")),
        "strict_blind_intake_policy": _text(acquisition_summary.get("strict_blind_intake_policy")),
        "tarball_path": _artifact(tarball),
        "native_pdb_path": _artifact(native),
        "extracted_model_dir": _artifact(extract_dir),
        "expected_model_count": expected_models,
        "model_file_count": len(rows),
        "ready_model_count": len(ready_rows),
        "blocked_model_count": len(rows) - len(ready_rows),
        "group_count": group_count,
        "model1_count": len(model1_rows),
        "groups_with_model1_count": groups_with_model1,
        "top5_model_count": len(top5_rows),
        "complete_top5_group_count": complete_top5_group_count,
        "extra_model_count": len(extra_rows),
        "native_pdb_atom_count": _int(acquisition_summary.get("native_pdb_atom_count")),
        "model1_manifest_csv": _artifact(model1_manifest),
        "top5_manifest_csv": _artifact(top5_manifest),
        "all_models_manifest_csv": _artifact(all_manifest),
        "first_model_id": _text(ready_rows[0].get("model_id")) if ready_rows else "",
        "first_model_path": _text(ready_rows[0].get("extracted_pdb")) if ready_rows else "",
        "first_model_atom_count": _int(ready_rows[0].get("atom_count")) if ready_rows else 0,
        "next_action": (
            "score baseline-only model1 and best-of-5 against the native PDB without importing as internal proof"
            if status == "official_archive_first_baseline_model_pool_ready"
            else "repair baseline acquisition/extraction before scoring"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Official Archive First Baseline Model Pool",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['official_archive_first_baseline_model_pool_status']}`",
        f"- first baseline: `{summary['first_baseline_candidate_id']}` `{summary['first_competition']}` `{summary['first_target_id']}` native `{summary['first_native_pdb_code']}`",
        f"- models ready/blocked/expected: `{summary['ready_model_count']}/{summary['blocked_model_count']}/{summary['expected_model_count']}`",
        f"- groups/model1/top5-complete: `{summary['group_count']}/{summary['model1_count']}/{summary['complete_top5_group_count']}`",
        f"- top5/extra models: `{summary['top5_model_count']}/{summary['extra_model_count']}`",
        f"- proof eligible: `{summary['competitive_proof_eligible']}` policy `{summary['strict_blind_intake_policy']}`",
        f"- manifests: `{summary['model1_manifest_csv']}` `{summary['top5_manifest_csv']}` `{summary['all_models_manifest_csv']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## First Models",
        "",
        "| rank | model | group | number | atoms | path |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"][:20]:
        lines.append(
            f"| `{row['model_rank']}` | `{row['model_id']}` | `{row['group_id']}` | "
            f"`{row['model_number']}` | `{row['atom_count']}` | `{row['extracted_pdb']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    all_manifest = out_dir / "all_models_manifest.csv"
    model1_manifest = out_dir / "model1_manifest.csv"
    top5_manifest = out_dir / "top5_manifest.csv"
    _write_csv(all_manifest, payload["rows"])
    _write_csv(model1_manifest, [row for row in payload["rows"] if row["model_number"] == 1])
    _write_csv(top5_manifest, [row for row in payload["rows"] if 1 <= row["model_number"] <= 5])
    _write_json(out_dir / "model_pool.json", payload)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract first official archive baseline model pool.")
    parser.add_argument("--acquisition-json", default=DEFAULT_ACQUISITION_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    print(
        json.dumps(
            {
                "status": payload["summary"]["official_archive_first_baseline_model_pool_status"],
                "target": payload["summary"]["first_target_id"],
                "models": payload["summary"]["ready_model_count"],
                "model1": payload["summary"]["model1_count"],
                "top5": payload["summary"]["top5_model_count"],
                "groups": payload["summary"]["group_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
