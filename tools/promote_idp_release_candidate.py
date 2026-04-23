#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from build_idp_release_report import build_report


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object: {path}")
    return payload


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def _replace_symlink(link_path: str, target_path: str) -> None:
    link = Path(link_path)
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        link.unlink()
    rel_target = os.path.relpath(target_path, start=str(link.parent))
    link.symlink_to(rel_target)


def _infer_candidate_prefix(candidate_summary_json: str) -> str:
    if candidate_summary_json.endswith("_summary.json"):
        return candidate_summary_json[: -len("_summary.json")]
    return os.path.splitext(candidate_summary_json)[0]


def promote(args: argparse.Namespace) -> Dict[str, Any]:
    candidate_eval = _load_json(str(args.candidate_eval_json))
    decision = str((candidate_eval.get("recommendation") or {}).get("decision", "")).strip()
    promote_flag = bool((candidate_eval.get("recommendation") or {}).get("promote", False))

    candidate_summary_json = str((candidate_eval.get("inputs") or {}).get("candidate_summary_json", "")).strip()
    if not candidate_summary_json:
        raise ValueError("candidate_eval missing inputs.candidate_summary_json")
    prefix = _infer_candidate_prefix(candidate_summary_json)

    candidate_manifest_json = str(args.candidate_manifest_json).strip() or f"{prefix}_release_manifest.json"
    candidate_manifest_md = str(args.candidate_manifest_md).strip() or f"{prefix}_release_manifest.md"
    candidate_regression_json = str(args.candidate_regression_json).strip() or f"{prefix}_release_regression.json"
    candidate_regression_md = str(args.candidate_regression_md).strip() or f"{prefix}_release_regression.md"

    payload: Dict[str, Any] = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "candidate_eval_json": str(args.candidate_eval_json),
        "candidate_summary_json": candidate_summary_json,
        "candidate_manifest_json": candidate_manifest_json,
        "candidate_regression_json": candidate_regression_json,
        "decision": decision,
        "promote": promote_flag,
        "updated": False,
        "reason": "",
    }

    if not promote_flag:
        payload["reason"] = "candidate_eval did not approve promotion"
        _write_json(str(args.out_json), payload)
        return payload

    baseline_current_json = str(args.baseline_current_json)
    manifest_current_json = str(args.manifest_current_json)
    manifest_current_md = str(args.manifest_current_md)
    regression_current_json = str(args.regression_current_json)
    regression_current_md = str(args.regression_current_md)
    report_current_md = str(args.report_current_md)

    baseline_payload = {
        "release_label": Path(prefix).name,
        "summary_json": candidate_summary_json,
        "manifest_json": candidate_manifest_json,
        "manifest_md": candidate_manifest_md,
        "regression_json": candidate_regression_json,
        "regression_md": candidate_regression_md,
        "promoted_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "notes": "Canonical current IDP release baseline. Use manifest_json as --baseline-manifest-json for future holdout regressions.",
    }
    _write_json(baseline_current_json, baseline_payload)
    _replace_symlink(manifest_current_json, candidate_manifest_json)
    _replace_symlink(manifest_current_md, candidate_manifest_md)
    _replace_symlink(regression_current_json, candidate_regression_json)
    _replace_symlink(regression_current_md, candidate_regression_md)

    report_text = build_report(
        baseline_json=baseline_current_json,
        manifest_json=candidate_manifest_json,
        regression_json=candidate_regression_json,
        historical_compare_json=str(getattr(args, "historical_compare_json", "")).strip(),
    )
    Path(report_current_md).parent.mkdir(parents=True, exist_ok=True)
    Path(report_current_md).write_text(report_text, encoding="utf-8")

    payload["updated"] = True
    payload["reason"] = "current baseline updated from approved candidate"
    payload["baseline_current_json"] = baseline_current_json
    payload["manifest_current_json"] = manifest_current_json
    payload["regression_current_json"] = regression_current_json
    payload["report_current_md"] = report_current_md
    _write_json(str(args.out_json), payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Promote an approved IDP release candidate to the current baseline.")
    p.add_argument("--candidate-eval-json", required=True, type=str)
    p.add_argument("--out-json", required=True, type=str)
    p.add_argument("--candidate-manifest-json", default="", type=str)
    p.add_argument("--candidate-manifest-md", default="", type=str)
    p.add_argument("--candidate-regression-json", default="", type=str)
    p.add_argument("--candidate-regression-md", default="", type=str)
    p.add_argument("--baseline-current-json", default="runs/idp_3bead_release_baseline_current.json", type=str)
    p.add_argument("--manifest-current-json", default="runs/idp_3bead_release_manifest_current.json", type=str)
    p.add_argument("--manifest-current-md", default="runs/idp_3bead_release_manifest_current.md", type=str)
    p.add_argument("--regression-current-json", default="runs/idp_3bead_release_regression_current.json", type=str)
    p.add_argument("--regression-current-md", default="runs/idp_3bead_release_regression_current.md", type=str)
    p.add_argument("--report-current-md", default="runs/idp_3bead_release_report_current.md", type=str)
    p.add_argument("--historical-compare-json", default="", type=str)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = promote(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
