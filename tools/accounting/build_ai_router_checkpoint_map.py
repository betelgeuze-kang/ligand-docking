#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, Optional, Sequence


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def build_ai_router_checkpoint_map(
    curriculum_summary_json: str,
    out_json: str,
    default_target: str = "",
    default_checkpoint: str = "",
    allow_missing_checkpoint: bool = False,
) -> Dict[str, Any]:
    src = str(curriculum_summary_json)
    if not os.path.exists(src):
        raise FileNotFoundError(f"curriculum summary not found: {src}")

    with open(src, "r", encoding="utf-8") as f:
        payload = json.load(f)

    targets = payload.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError(f"invalid curriculum summary format (missing non-empty targets list): {src}")

    target_checkpoints: Dict[str, str] = {}
    for row in targets:
        if not isinstance(row, dict):
            continue
        target = str(row.get("target", "")).strip()
        ckpt = str(row.get("best_checkpoint_path", "")).strip()
        if not target or not ckpt:
            continue
        ckpt_abs = os.path.abspath(ckpt)
        if not allow_missing_checkpoint and not os.path.exists(ckpt_abs):
            raise FileNotFoundError(f"checkpoint file missing for target={target}: {ckpt_abs}")
        target_checkpoints[target] = ckpt_abs

    if not target_checkpoints:
        raise ValueError(f"no usable target->checkpoint mapping found in: {src}")

    default_i = str(default_checkpoint or "").strip()
    if default_i:
        default_abs = os.path.abspath(default_i)
        if not allow_missing_checkpoint and not os.path.exists(default_abs):
            raise FileNotFoundError(f"default checkpoint not found: {default_abs}")
    else:
        target_i = str(default_target or "").strip()
        if target_i and target_i in target_checkpoints:
            default_abs = target_checkpoints[target_i]
        else:
            first_target = next(iter(target_checkpoints.keys()))
            default_abs = target_checkpoints[first_target]

    out = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "source_curriculum_summary": os.path.abspath(src),
        "target_checkpoints": target_checkpoints,
        "default": default_abs,
        "manifest_used": payload.get("distilled_manifest"),
        "schedule": payload.get("schedule"),
        "run_tag": payload.get("run_tag"),
    }
    _ensure_parent(out_json)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build target checkpoint-map JSON from curriculum training summary."
    )
    p.add_argument("--curriculum-summary-json", type=str, required=True)
    p.add_argument("--out-json", type=str, required=True)
    p.add_argument("--default-target", type=str, default="")
    p.add_argument("--default-checkpoint", type=str, default="")
    p.add_argument("--allow-missing-checkpoint", action=argparse.BooleanOptionalAction, default=False)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = build_parser()
    args = p.parse_args(argv)
    out = build_ai_router_checkpoint_map(
        curriculum_summary_json=str(args.curriculum_summary_json),
        out_json=str(args.out_json),
        default_target=str(args.default_target),
        default_checkpoint=str(args.default_checkpoint),
        allow_missing_checkpoint=bool(args.allow_missing_checkpoint),
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
