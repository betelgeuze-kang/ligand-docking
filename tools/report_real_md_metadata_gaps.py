#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from core.definitions import ResearchConstants


REQUIRED_FIELDS = ["md_engine", "source_engine", "source_path"]
RECOMMENDED_FIELDS = [
    "md_forcefield",
    "md_water_model",
    "md_temperature_k",
    "md_timestep_fs",
    "md_steps",
    "md_software_version",
]


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _str_or_empty(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() == "nan":
        return ""
    return s


def _match_engine(v: str, pattern: str) -> bool:
    if not v:
        return False
    return re.search(pattern, v, flags=re.IGNORECASE) is not None


def _load_metadata_csv(
    metadata_csv: str,
    template_csv: str,
    init_metadata_if_missing: bool,
) -> pd.DataFrame:
    if os.path.exists(metadata_csv):
        return pd.read_csv(metadata_csv)
    if init_metadata_if_missing and os.path.exists(template_csv):
        os.makedirs(os.path.dirname(metadata_csv) or ".", exist_ok=True)
        shutil.copy2(template_csv, metadata_csv)
        return pd.read_csv(metadata_csv)
    return pd.DataFrame()


def _targets(manifest_csv: Optional[str]) -> List[str]:
    if manifest_csv and os.path.exists(manifest_csv):
        df = pd.read_csv(manifest_csv)
        if "target" in df.columns:
            seen: Dict[str, str] = {}
            for t in df["target"].tolist():
                ts = _str_or_empty(t)
                if not ts:
                    continue
                k = _normalize_target_key(ts)
                if k not in seen:
                    seen[k] = ts
            return list(seen.values())
    return list(ResearchConstants.CHALLENGES.keys())


def report_real_md_metadata_gaps(
    metadata_csv: str,
    template_csv: str,
    manifest_csv: Optional[str],
    out_csv: str,
    out_json: str,
    out_md: str,
    md_engine_regex: str,
    init_metadata_if_missing: bool,
    strict: bool,
) -> Dict[str, Any]:
    meta_df = _load_metadata_csv(
        metadata_csv=metadata_csv,
        template_csv=template_csv,
        init_metadata_if_missing=init_metadata_if_missing,
    )
    if (not meta_df.empty) and ("target" not in meta_df.columns):
        raise ValueError(f"metadata csv missing required column: target ({metadata_csv})")

    meta_by_target: Dict[str, Dict[str, Any]] = {}
    if not meta_df.empty:
        for row in meta_df.to_dict(orient="records"):
            t = _str_or_empty(row.get("target", ""))
            if not t:
                continue
            meta_by_target[_normalize_target_key(t)] = row

    targets = _targets(manifest_csv)
    rows: List[Dict[str, Any]] = []
    for t in targets:
        row = meta_by_target.get(_normalize_target_key(t), {})
        missing_required: List[str] = []
        missing_recommended: List[str] = []
        for f in REQUIRED_FIELDS:
            if not _str_or_empty(row.get(f, "")):
                missing_required.append(f)
        for f in RECOMMENDED_FIELDS:
            if not _str_or_empty(row.get(f, "")):
                missing_recommended.append(f)

        md_engine = _str_or_empty(row.get("md_engine", ""))
        source_engine = _str_or_empty(row.get("source_engine", ""))
        source_path = _str_or_empty(row.get("source_path", ""))
        source_path_exists = bool(source_path) and os.path.exists(source_path)
        md_engine_ok = _match_engine(md_engine, md_engine_regex)
        source_engine_ok = _match_engine(source_engine, md_engine_regex)

        strict_ok = (
            len(missing_required) == 0
            and md_engine_ok
            and source_engine_ok
            and source_path_exists
        )
        if len(missing_required) == 0 and (not md_engine_ok):
            missing_required.append("md_engine(regex)")
        if len(missing_required) == 0 and (not source_engine_ok):
            missing_required.append("source_engine(regex)")
        if len(missing_required) == 0 and (not source_path_exists):
            missing_required.append("source_path(exists)")

        rows.append(
            {
                "target": t,
                "metadata_row_present": bool(len(row) > 0),
                "md_engine": md_engine,
                "source_engine": source_engine,
                "source_path": source_path,
                "source_path_exists": bool(source_path_exists),
                "md_engine_ok": bool(md_engine_ok),
                "source_engine_ok": bool(source_engine_ok),
                "strict_ok": bool(strict_ok),
                "missing_required_fields": ",".join(missing_required),
                "missing_recommended_fields": ",".join(missing_recommended),
            }
        )

    out_df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)
    out_df.to_csv(out_csv, index=False)

    strict_ready_targets = int(out_df["strict_ok"].sum()) if not out_df.empty else 0
    total_targets = int(len(out_df))
    failed_targets = (
        sorted(out_df.loc[out_df["strict_ok"] == False, "target"].astype(str).tolist()) if not out_df.empty else []
    )
    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "metadata_csv": metadata_csv,
        "template_csv": template_csv,
        "manifest_csv": manifest_csv,
        "md_engine_regex": md_engine_regex,
        "total_targets": total_targets,
        "strict_ready_targets": strict_ready_targets,
        "strict_not_ready_targets": int(total_targets - strict_ready_targets),
        "failed_targets": failed_targets,
        "strict_ready": bool(strict_ready_targets == total_targets and total_targets > 0),
    }
    payload = {"summary": summary, "rows": rows}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    md_lines: List[str] = []
    md_lines.append("# Real MD Metadata Gap Report")
    md_lines.append("")
    md_lines.append(f"- metadata_csv: `{metadata_csv}`")
    md_lines.append(f"- template_csv: `{template_csv}`")
    md_lines.append(f"- manifest_csv: `{manifest_csv}`")
    md_lines.append(f"- strict_ready_targets: `{strict_ready_targets}/{total_targets}`")
    md_lines.append("")
    md_lines.append("## Failed Targets")
    md_lines.append("")
    if len(failed_targets) == 0:
        md_lines.append("- none")
    else:
        for t in failed_targets:
            r = out_df[out_df["target"] == t].iloc[0]
            md_lines.append(
                f"- `{t}`: required=`{r['missing_required_fields']}` recommended=`{r['missing_recommended_fields']}`"
            )
    md_lines.append("")
    md_lines.append("## Required Fields")
    md_lines.append("")
    for f in REQUIRED_FIELDS:
        md_lines.append(f"- `{f}`")
    md_lines.append("- `md_engine` and `source_engine` must match regex and `source_path` must exist.")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines).strip() + "\n")

    if strict and not bool(summary["strict_ready"]):
        raise RuntimeError(
            f"real md metadata gaps remain: strict_ready_targets={strict_ready_targets}/{total_targets}"
        )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report target-wise gaps in real MD metadata required for strict provenance gate."
    )
    parser.add_argument("--metadata-csv", type=str, default="runs/real_md_metadata.csv")
    parser.add_argument("--template-csv", type=str, default="runs/real_md_metadata_template_2026-02-14.csv")
    parser.add_argument("--manifest-csv", type=str, default="runs/external_ref_manifest_real_filled_2026-02-14.csv")
    parser.add_argument("--md-engine-regex", type=str, default=r"(openmm|amber|gromacs)")
    parser.add_argument("--init-metadata-if-missing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-csv", type=str, default="runs/real_md_metadata_gap_report.csv")
    parser.add_argument("--out-json", type=str, default="runs/real_md_metadata_gap_report.json")
    parser.add_argument("--out-md", type=str, default="runs/real_md_metadata_gap_report.md")
    parser.add_argument("--strict", action=argparse.BooleanOptionalAction, default=False)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = report_real_md_metadata_gaps(
            metadata_csv=str(args.metadata_csv),
            template_csv=str(args.template_csv),
            manifest_csv=str(args.manifest_csv) if args.manifest_csv else None,
            out_csv=str(args.out_csv),
            out_json=str(args.out_json),
            out_md=str(args.out_md),
            md_engine_regex=str(args.md_engine_regex),
            init_metadata_if_missing=bool(args.init_metadata_if_missing),
            strict=bool(args.strict),
        )
    except Exception as exc:
        print(f"[FAIL] {exc}")
        sys.exit(2)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
