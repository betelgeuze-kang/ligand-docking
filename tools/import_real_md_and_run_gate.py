#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from types import SimpleNamespace
from typing import Any, Dict, Optional, Sequence

import pandas as pd

from core.definitions import ResearchConstants
from tools.bootstrap_real_md_metadata import bootstrap_real_md_metadata
from tools.prepare_real_md_manifest import prepare_real_md_manifest
from tools.report_real_md_metadata_gaps import report_real_md_metadata_gaps
from tools.run_strict_md_eval import run_strict_md_eval


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", str(text).strip().lower()).strip("_")
    return s or "run"


def _has_proxy_engine(path: str) -> bool:
    if not os.path.exists(path):
        raise FileNotFoundError(f"source manifest not found: {path}")
    df = pd.read_csv(path)
    if "engine" not in df.columns:
        return False
    vals = [str(x).strip().lower() for x in df["engine"].tolist()]
    return any("proxy" in v for v in vals if v)


def _paths(out_dir: str, label: str, stamp: str) -> Dict[str, str]:
    l = _slug(label)
    base = os.path.abspath(out_dir)
    return {
        "metadata_csv": os.path.join(base, f"real_md_metadata_imported_{l}_{stamp}.csv"),
        "metadata_summary_json": os.path.join(base, f"real_md_metadata_imported_{l}_{stamp}_summary.json"),
        "gap_csv": os.path.join(base, f"real_md_metadata_gap_report_imported_{l}_{stamp}.csv"),
        "gap_json": os.path.join(base, f"real_md_metadata_gap_report_imported_{l}_{stamp}.json"),
        "gap_md": os.path.join(base, f"real_md_metadata_gap_report_imported_{l}_{stamp}.md"),
        "candidate_manifest_csv": os.path.join(base, f"external_ref_manifest_real_md_candidate_imported_{l}_{stamp}.csv"),
        "candidate_manifest_json": os.path.join(base, f"external_ref_manifest_real_md_candidate_imported_{l}_{stamp}_summary.json"),
        "strict_summary_json": os.path.join(base, f"strict_md_eval_imported_{l}_{stamp}.json"),
    }


def import_real_md_and_run_gate(args: argparse.Namespace) -> Dict[str, Any]:
    stamp = str(args.date_stamp) if args.date_stamp else dt.date.today().isoformat()
    out = _paths(out_dir=str(args.out_dir), label=str(args.label), stamp=stamp)
    os.makedirs(str(args.out_dir), exist_ok=True)

    if bool(args.forbid_proxy_engines) and _has_proxy_engine(str(args.source_manifest_csv)):
        raise RuntimeError(
            "source manifest contains proxy engine values; "
            "use a real MD source manifest or set --no-forbid-proxy-engines"
        )

    boot = bootstrap_real_md_metadata(
        base_metadata_csv=str(args.base_metadata_csv),
        source_manifest_csv=str(args.source_manifest_csv),
        out_csv=out["metadata_csv"],
        out_json=out["metadata_summary_json"],
        md_engine_from=str(args.md_engine_from),
        source_engine_from=str(args.source_engine_from),
        source_path_from=str(args.source_path_from),
        source_label_from=str(args.source_label_from),
        note_tag=str(args.note_tag),
        overwrite_existing_nonempty=bool(args.overwrite_existing_nonempty),
    )

    gaps = report_real_md_metadata_gaps(
        metadata_csv=out["metadata_csv"],
        template_csv=str(args.template_csv),
        manifest_csv=str(args.input_manifest),
        out_csv=out["gap_csv"],
        out_json=out["gap_json"],
        out_md=out["gap_md"],
        md_engine_regex=str(args.md_engine_regex),
        init_metadata_if_missing=False,
        strict=True,
    )

    cand = prepare_real_md_manifest(
        input_manifest=str(args.input_manifest),
        metadata_csv=out["metadata_csv"],
        template_csv=str(args.template_csv),
        out_manifest=out["candidate_manifest_csv"],
        out_json=out["candidate_manifest_json"],
        engine_regex=str(args.md_engine_regex),
        write_template=False,
        require_existing_source_path=True,
        expected_target_count=int(args.expected_target_count),
        strict=True,
    )

    strict_args = SimpleNamespace(
        manifest_csv=out["candidate_manifest_csv"],
        label=f"imported_{args.label}_{stamp}",
        out_dir=str(args.out_dir),
        date_stamp=stamp,
        targets=str(args.targets),
        steps=int(args.steps),
        runs=int(args.runs),
        noise=float(args.noise),
        seed_base=int(args.seed_base),
        md_engine_regex=str(args.md_engine_regex),
        expected_target_count=int(args.expected_target_count),
        strict_validation=True,
        require_gap_ready=True,
        run_provenance_validation=True,
        provenance_source_engine_regex=str(args.md_engine_regex),
        provenance_require_source_engine=True,
        provenance_require_source_path=True,
        provenance_strict=True,
        enforce_provenance_gate=True,
    )
    strict_payload = run_strict_md_eval(strict_args)

    payload: Dict[str, Any] = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "label": str(args.label),
        "source_manifest_csv": str(args.source_manifest_csv),
        "outputs": out,
        "bootstrap_summary": boot.get("summary", {}),
        "gap_summary": gaps.get("summary", {}),
        "candidate_summary": cand.get("summary", {}),
        "strict_checks": strict_payload.get("checks", {}),
        "strict_accuracy_summary": strict_payload.get("accuracy_summary", {}),
    }
    with open(out["strict_summary_json"], "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Import real-MD source manifest into metadata and run strict gate end-to-end. "
            "Fails early if proxy engines are detected (default)."
        )
    )
    parser.add_argument("--label", type=str, default="real_md_import")
    parser.add_argument("--date-stamp", type=str, default=None)
    parser.add_argument("--out-dir", type=str, default="runs")
    parser.add_argument("--base-metadata-csv", type=str, default="runs/real_md_metadata.csv")
    parser.add_argument("--template-csv", type=str, default="runs/real_md_metadata_template_2026-02-14.csv")
    parser.add_argument("--source-manifest-csv", type=str, required=True)
    parser.add_argument("--input-manifest", type=str, default="runs/external_ref_manifest_real_filled_2026-02-14.csv")
    parser.add_argument("--md-engine-regex", type=str, default=r"(openmm|amber|gromacs)")
    parser.add_argument("--md-engine-from", type=str, default="engine")
    parser.add_argument("--source-engine-from", type=str, default="engine")
    parser.add_argument("--source-path-from", type=str, default="path")
    parser.add_argument("--source-label-from", type=str, default="label")
    parser.add_argument("--note-tag", type=str, default="REAL_MD_IMPORTED")
    parser.add_argument("--overwrite-existing-nonempty", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--forbid-proxy-engines", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--targets", type=str, default="all")
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--noise", type=float, default=0.02)
    parser.add_argument("--seed-base", type=int, default=42)
    parser.add_argument("--expected-target-count", type=int, default=len(ResearchConstants.CHALLENGES))
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = import_real_md_and_run_gate(args)
    except Exception as exc:
        print(f"[FAIL] {exc}")
        sys.exit(2)
    print(json.dumps(payload["strict_checks"], indent=2, ensure_ascii=False))
    print(json.dumps(payload["strict_accuracy_summary"], indent=2, ensure_ascii=False))
    print(f"Wrote: {payload['outputs']['strict_summary_json']}")


if __name__ == "__main__":
    main()
