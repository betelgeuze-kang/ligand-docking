#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def write_closeout(
    *,
    summary_json: str,
    out_dir: str = "runs",
    prefix: str = "CLOSEOUT",
    symlink_latest: bool = True,
) -> Dict[str, str]:
    summary_path = Path(str(summary_json).strip())
    if not summary_path.exists():
        raise FileNotFoundError(f"summary json not found: {summary_json}")

    out_root = Path(str(out_dir).strip() or "runs")
    out_root.mkdir(parents=True, exist_ok=True)
    date_tag = dt.date.today().isoformat()
    now_local = dt.datetime.now().isoformat(timespec="seconds")

    payload = _read_json(summary_path)
    stages = payload.get("stages", {}) if isinstance(payload.get("stages"), dict) else {}
    artifacts = payload.get("artifacts", {}) if isinstance(payload.get("artifacts"), dict) else {}
    service_result = payload.get("service_result", {}) if isinstance(payload.get("service_result"), dict) else {}

    artifacts_abs = payload.get("artifacts_abs", {}) if isinstance(payload.get("artifacts_abs"), dict) else {}
    close_payload: Dict[str, Any] = {
        "generated_at_local": now_local,
        "source_summary_json": str(summary_path),
        "source_summary_json_abs": str(summary_path.resolve()),
        "pass": bool(payload.get("pass", False)),
        "failed_stage": payload.get("failed_stage"),
        "run_scope": payload.get("run_scope"),
        "service_result": service_result,
        "stage_count": int(len(stages)),
        "stages_present": list(stages.keys()),
        "artifacts": artifacts,
        "artifacts_abs": artifacts_abs,
    }

    # Preserve core gate block when available for quick external check.
    op_gate = stages.get("stage6_operational_gate")
    if isinstance(op_gate, dict):
        close_payload["stage6_operational_gate"] = op_gate
    strict_gate = stages.get("stage6_strict_gate")
    if isinstance(strict_gate, dict):
        close_payload["stage6_strict_gate"] = strict_gate

    close_json = out_root / f"{prefix}_{date_tag}.json"
    close_md = out_root / f"{prefix}_{date_tag}.md"
    latest_pointer_json = out_root / f"{prefix}_LATEST_POINTER.json"
    latest_pointer_md = out_root / f"{prefix}_LATEST_POINTER.md"
    with close_json.open("w", encoding="utf-8") as f:
        json.dump(close_payload, f, indent=2, ensure_ascii=False)
        f.write("\n")

    lines = [
        f"# {prefix} {date_tag}",
        "",
        f"- generated_at_local: `{now_local}`",
        f"- source_summary_json: `{summary_path}`",
        f"- source_summary_json_abs: `{summary_path.resolve()}`",
        f"- pass: `{close_payload['pass']}`",
        f"- failed_stage: `{close_payload.get('failed_stage')}`",
        f"- run_scope: `{close_payload.get('run_scope')}`",
        f"- stage_count: `{close_payload['stage_count']}`",
        "",
        "## Service",
        f"- service_result: `{service_result}`",
        "",
    ]
    if isinstance(op_gate, dict):
        lines.extend(
            [
                "## Stage6 Operational Gate",
                f"- pass: `{op_gate.get('pass')}`",
                f"- failed_metrics: `{len(op_gate.get('failed_metrics') or [])}`",
            ]
        )
        for m in (op_gate.get("failed_metrics") or []):
            if isinstance(m, dict):
                lines.append(
                    f"- `{m.get('metric')}`: `{m.get('value')}` (threshold `{m.get('threshold')}`)"
                )
        lines.append("")
    lines.extend(
        [
            "## Artifacts",
            f"- closeout_json: `{close_json}`",
            f"- closeout_md: `{close_md}`",
        ]
    )
    with close_md.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    out: Dict[str, str] = {
        "closeout_json": str(close_json),
        "closeout_md": str(close_md),
    }
    if symlink_latest:
        link_json = out_root / f"{prefix}_LATEST.json"
        link_md = out_root / f"{prefix}_LATEST.md"
        for link, target in ((link_json, close_json.name), (link_md, close_md.name)):
            try:
                if link.exists() or link.is_symlink():
                    link.unlink()
                link.symlink_to(target)
            except Exception:
                # Fall back to copy on filesystems that do not support symlink.
                if link.exists():
                    link.unlink()
                src = close_json if link.suffix == ".json" else close_md
                link.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        out["latest_json"] = str(link_json)
        out["latest_md"] = str(link_md)
    latest_pointer_payload = {
        "generated_at_local": now_local,
        "prefix": prefix,
        "closeout_json": str(close_json),
        "closeout_md": str(close_md),
        "closeout_json_abs": str(close_json.resolve()),
        "closeout_md_abs": str(close_md.resolve()),
        "source_summary_json": str(summary_path),
        "source_summary_json_abs": str(summary_path.resolve()),
        "latest_json": str((out_root / f"{prefix}_LATEST.json")),
        "latest_md": str((out_root / f"{prefix}_LATEST.md")),
        "pass": bool(close_payload.get("pass", False)),
        "failed_stage": close_payload.get("failed_stage"),
        "service_result": service_result,
        "artifacts_abs": artifacts_abs,
    }
    latest_pointer_json.write_text(json.dumps(latest_pointer_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    latest_pointer_md.write_text(
        "\n".join(
            [
                f"# {prefix} Latest Pointer",
                "",
                f"- generated_at_local: `{now_local}`",
                f"- closeout_json_abs: `{close_json.resolve()}`",
                f"- closeout_md_abs: `{close_md.resolve()}`",
                f"- source_summary_json_abs: `{summary_path.resolve()}`",
                f"- pass: `{close_payload.get('pass')}`",
                f"- failed_stage: `{close_payload.get('failed_stage')}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out["latest_pointer_json"] = str(latest_pointer_json)
    out["latest_pointer_md"] = str(latest_pointer_md)
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Update CLOSEOUT_LATEST from a summary json file.")
    p.add_argument("--summary-json", type=str, required=True)
    p.add_argument("--out-dir", type=str, default="runs")
    p.add_argument("--prefix", type=str, default="CLOSEOUT")
    p.add_argument("--symlink-latest", action=argparse.BooleanOptionalAction, default=True)
    return p


def main() -> None:
    args = build_parser().parse_args()
    out = write_closeout(
        summary_json=str(args.summary_json),
        out_dir=str(args.out_dir),
        prefix=str(args.prefix),
        symlink_latest=bool(args.symlink_latest),
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
