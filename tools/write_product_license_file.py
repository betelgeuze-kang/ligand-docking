#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from betelgeuze_product.license_decision import APPROVAL_TOKEN

DEFAULT_WORK_ORDER_JSON = "runs/product_license_file_creation_work_order_current.json"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else Path.cwd() / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"blocked_license_file_write: unreadable_work_order: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("blocked_license_file_write: work_order_not_object")
    return payload


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _approval_present() -> bool:
    return os.environ.get(APPROVAL_TOKEN) == "1"


def _license_text(args: argparse.Namespace) -> str:
    source = args.license_text_file or args.license_template
    if source:
        source_path = _resolve(source)
        if not source_path.is_file():
            raise SystemExit(f"blocked_license_file_write: license_text_file_missing: {source_path}")
        text = source_path.read_text(encoding="utf-8")
    else:
        text = args.literal_license_text or ""
    if not text.strip():
        raise SystemExit("blocked_license_file_write: empty_license_text")
    return text if text.endswith("\n") else text + "\n"


def write_license_file(
    *,
    work_order_json: str | Path,
    out: str | Path,
    license_text: str,
    force: bool = False,
) -> dict[str, Any]:
    packet = _read_json(work_order_json)
    summary = _summary(packet)
    if not _approval_present():
        raise SystemExit(f"blocked_license_file_write: missing_env_approval_token:{APPROVAL_TOKEN}=1")
    if _text(summary.get("status")) != "product_license_file_creation_work_order_ready":
        raise SystemExit("blocked_license_file_write: work_order_not_ready")
    if summary.get("license_file_creation_review_ready") is not True:
        raise SystemExit("blocked_license_file_write: review_not_ready")
    target_from_work_order = _text(summary.get("target_license_path")) or "LICENSE"
    if Path(out).as_posix() != Path(target_from_work_order).as_posix():
        raise SystemExit(
            "blocked_license_file_write: output_path_mismatch:"
            f"out={Path(out).as_posix()};target={Path(target_from_work_order).as_posix()}"
        )
    out_path = _resolve(out)
    if out_path.exists() and not force:
        raise SystemExit(f"blocked_license_file_write: target_exists:{out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(license_text, encoding="utf-8")
    return {
        "status": "product_license_file_written",
        "license_file_written": True,
        "target_license_path": Path(out).as_posix(),
        "work_order_json": str(work_order_json),
        "approval_token_required": APPROVAL_TOKEN,
        "external_state_mutated": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write an operator-approved LICENSE file from a ready work order.")
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--out", default="LICENSE")
    parser.add_argument("--license-text-file")
    parser.add_argument("--license-template")
    parser.add_argument("--literal-license-text")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    result = write_license_file(
        work_order_json=args.work_order_json,
        out=args.out,
        license_text=_license_text(args),
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
