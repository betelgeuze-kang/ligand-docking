#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _str_or_empty(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() == "nan":
        return ""
    return s


def _build_source_map(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in df.to_dict(orient="records"):
        t = _str_or_empty(row.get("target", ""))
        if not t:
            continue
        out[_normalize_target_key(t)] = row
    return out


def _notes(existing: str, source_manifest: str, tag: str) -> str:
    parts = [p for p in [existing] if p]
    parts.append(f"BOOTSTRAP_SOURCE={source_manifest}")
    parts.append(tag)
    return " | ".join(parts)


def bootstrap_real_md_metadata(
    base_metadata_csv: str,
    source_manifest_csv: str,
    out_csv: str,
    out_json: str,
    md_engine_from: str,
    source_engine_from: str,
    source_path_from: str,
    source_label_from: str,
    note_tag: str,
    overwrite_existing_nonempty: bool,
) -> Dict[str, Any]:
    if not os.path.exists(base_metadata_csv):
        raise FileNotFoundError(f"base metadata csv not found: {base_metadata_csv}")
    if not os.path.exists(source_manifest_csv):
        raise FileNotFoundError(f"source manifest csv not found: {source_manifest_csv}")

    base_df = pd.read_csv(base_metadata_csv)
    src_df = pd.read_csv(source_manifest_csv)
    if "target" not in base_df.columns:
        raise ValueError(f"base metadata csv must include target: {base_metadata_csv}")
    if "target" not in src_df.columns:
        raise ValueError(f"source manifest csv must include target: {source_manifest_csv}")

    for col in [
        "md_engine",
        "source_engine",
        "source_path",
        "source_label",
        "notes",
    ]:
        if col not in base_df.columns:
            base_df[col] = ""

    src_map = _build_source_map(src_df)
    rows: List[Dict[str, Any]] = []
    updated_targets: List[str] = []
    skipped_targets: List[str] = []
    missing_source_targets: List[str] = []

    for row in base_df.to_dict(orient="records"):
        target = _str_or_empty(row.get("target", ""))
        src = src_map.get(_normalize_target_key(target), None)
        if src is None:
            rows.append(row)
            missing_source_targets.append(target)
            continue

        def _set_if_needed(field: str, value: str) -> None:
            current = _str_or_empty(row.get(field, ""))
            if current and (not overwrite_existing_nonempty):
                return
            row[field] = value

        md_engine_val = _str_or_empty(src.get(md_engine_from, ""))
        source_engine_val = _str_or_empty(src.get(source_engine_from, ""))
        source_path_val = _str_or_empty(src.get(source_path_from, ""))
        source_label_val = _str_or_empty(src.get(source_label_from, ""))

        before = {
            "md_engine": _str_or_empty(row.get("md_engine", "")),
            "source_engine": _str_or_empty(row.get("source_engine", "")),
            "source_path": _str_or_empty(row.get("source_path", "")),
            "source_label": _str_or_empty(row.get("source_label", "")),
        }

        _set_if_needed("md_engine", md_engine_val)
        _set_if_needed("source_engine", source_engine_val)
        _set_if_needed("source_path", source_path_val)
        _set_if_needed("source_label", source_label_val)
        row["notes"] = _notes(_str_or_empty(row.get("notes", "")), source_manifest_csv, note_tag)

        after = {
            "md_engine": _str_or_empty(row.get("md_engine", "")),
            "source_engine": _str_or_empty(row.get("source_engine", "")),
            "source_path": _str_or_empty(row.get("source_path", "")),
            "source_label": _str_or_empty(row.get("source_label", "")),
        }
        if before != after:
            updated_targets.append(target)
        else:
            skipped_targets.append(target)
        rows.append(row)

    out_df = pd.DataFrame(rows, columns=list(base_df.columns))
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    out_df.to_csv(out_csv, index=False)

    summary: Dict[str, Any] = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "base_metadata_csv": base_metadata_csv,
        "source_manifest_csv": source_manifest_csv,
        "out_csv": out_csv,
        "rows": int(len(out_df)),
        "updated_targets": sorted([x for x in updated_targets if x]),
        "updated_target_count": int(len([x for x in updated_targets if x])),
        "skipped_targets": sorted([x for x in skipped_targets if x]),
        "missing_source_targets": sorted([x for x in missing_source_targets if x]),
        "policies": {
            "md_engine_from": md_engine_from,
            "source_engine_from": source_engine_from,
            "source_path_from": source_path_from,
            "source_label_from": source_label_from,
            "overwrite_existing_nonempty": bool(overwrite_existing_nonempty),
            "note_tag": note_tag,
        },
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"summary": summary}, f, indent=2, ensure_ascii=False)
    return {"summary": summary}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Bootstrap real_md_metadata.csv fields from an existing manifest "
            "(useful for proxy pipeline dry-run while waiting real MD files)."
        )
    )
    parser.add_argument("--base-metadata-csv", type=str, default="runs/real_md_metadata.csv")
    parser.add_argument("--source-manifest-csv", type=str, default="runs/external_ref_manifest_md_proxy_openmm.csv")
    parser.add_argument("--out-csv", type=str, default="runs/real_md_metadata_bootstrap_proxy.csv")
    parser.add_argument("--out-json", type=str, default="runs/real_md_metadata_bootstrap_proxy_summary.json")
    parser.add_argument("--md-engine-from", type=str, default="engine")
    parser.add_argument("--source-engine-from", type=str, default="engine")
    parser.add_argument("--source-path-from", type=str, default="path")
    parser.add_argument("--source-label-from", type=str, default="label")
    parser.add_argument(
        "--note-tag",
        type=str,
        default="NOT_REAL_MD_UNLESS_SOURCE_VERIFIED",
    )
    parser.add_argument("--overwrite-existing-nonempty", action=argparse.BooleanOptionalAction, default=False)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = bootstrap_real_md_metadata(
            base_metadata_csv=str(args.base_metadata_csv),
            source_manifest_csv=str(args.source_manifest_csv),
            out_csv=str(args.out_csv),
            out_json=str(args.out_json),
            md_engine_from=str(args.md_engine_from),
            source_engine_from=str(args.source_engine_from),
            source_path_from=str(args.source_path_from),
            source_label_from=str(args.source_label_from),
            note_tag=str(args.note_tag),
            overwrite_existing_nonempty=bool(args.overwrite_existing_nonempty),
        )
    except Exception as exc:
        print(f"[FAIL] {exc}")
        sys.exit(2)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
