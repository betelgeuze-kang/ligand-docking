#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional, Sequence

try:
    from tools.run_idp_3bead_release_smoke import DEFAULT_SMOKE_HOLDOUTS, run_smoke
except ModuleNotFoundError:
    from run_idp_3bead_release_smoke import DEFAULT_SMOKE_HOLDOUTS, run_smoke


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"invalid json object: {path}")
    return payload


def _parse_holdouts(raw: str) -> str:
    if not str(raw).strip():
        return ",".join(DEFAULT_SMOKE_HOLDOUTS)
    return ",".join([x.strip() for x in str(raw).split(",") if x.strip()])


def run_current(args: argparse.Namespace) -> Dict[str, Any]:
    smoke_current = _load_json(str(args.smoke_current_json))

    baseline_manifest_json = str(args.baseline_manifest_json).strip() or str(
        smoke_current.get("smoke_baseline_manifest_json", "")
    ).strip()
    if not baseline_manifest_json:
        raise ValueError("unable to resolve smoke baseline manifest json")

    frozen_labels_manifest_json = str(args.frozen_labels_manifest_json).strip() or str(
        args.release_manifest_current_json
    ).strip()
    if not frozen_labels_manifest_json:
        raise ValueError("unable to resolve frozen-labels manifest json")

    out_prefix = str(args.out_prefix).strip() or (
        f"runs/idp_3bead_release_smoke_current_{dt.date.today().isoformat()}_{str(args.tag).strip() or 'rerun'}"
    )
    release_label = str(args.release_label).strip() or os.path.basename(out_prefix)

    smoke_args = SimpleNamespace(
        config_json=str(args.config_json),
        baseline_manifest_json=baseline_manifest_json,
        frozen_labels_manifest_json=frozen_labels_manifest_json,
        holdout_key=str(args.holdout_key),
        holdouts=_parse_holdouts(args.holdouts),
        device=str(args.device),
        out_prefix=out_prefix,
        release_label=release_label,
        resume_existing=int(args.resume_existing),
        smoke_config_json=str(args.smoke_config_json).strip(),
        smoke_baseline_manifest_json=str(args.smoke_baseline_manifest_json).strip(),
        smoke_regression_json=str(args.smoke_regression_json).strip(),
        smoke_regression_md=str(args.smoke_regression_md).strip(),
        smoke_candidate_eval_json=str(args.smoke_candidate_eval_json).strip(),
        smoke_candidate_eval_md=str(args.smoke_candidate_eval_md).strip(),
        out_json=str(args.out_json).strip(),
        out_md=str(args.out_md).strip(),
    )
    return run_smoke(smoke_args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run the canonical current IDP smoke regression using current smoke and release references.")
    p.add_argument("--smoke-current-json", type=str, default="runs/idp_3bead_release_smoke_current.json")
    p.add_argument("--release-manifest-current-json", type=str, default="runs/idp_3bead_release_manifest_current.json")
    p.add_argument("--baseline-manifest-json", type=str, default="")
    p.add_argument("--frozen-labels-manifest-json", type=str, default="")
    p.add_argument("--config-json", type=str, default="config/idp_3bead_benchmark_v7.json")
    p.add_argument("--holdout-key", type=str, default="split_group")
    p.add_argument("--holdouts", type=str, default="")
    p.add_argument("--device", type=str, default="cuda")
    p.add_argument("--out-prefix", type=str, default="")
    p.add_argument("--release-label", type=str, default="")
    p.add_argument("--tag", type=str, default="rerun")
    p.add_argument("--resume-existing", type=int, default=1)
    p.add_argument("--smoke-config-json", type=str, default="")
    p.add_argument("--smoke-baseline-manifest-json", type=str, default="")
    p.add_argument("--smoke-regression-json", type=str, default="")
    p.add_argument("--smoke-regression-md", type=str, default="")
    p.add_argument("--smoke-candidate-eval-json", type=str, default="")
    p.add_argument("--smoke-candidate-eval-md", type=str, default="")
    p.add_argument("--out-json", type=str, default="")
    p.add_argument("--out-md", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_current(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
