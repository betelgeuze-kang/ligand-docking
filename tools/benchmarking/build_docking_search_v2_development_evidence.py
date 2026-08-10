#!/usr/bin/env python3
"""Build a canonical Docking Search v2 retrospective-development receipt."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from benchmarks.docking_search_v2 import (
    ProtocolError,
    canonical_json_bytes,
    evaluate_development_result,
    verify_evidence_receipt,
)


MAX_RESULT_BYTES = 16 * 1024 * 1024


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("duplicate_json_key", f"duplicate key {key!r}")
        result[key] = value
    return result


def _load_result(path: Path) -> object:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_file() or resolved.stat().st_size > MAX_RESULT_BYTES:
        raise ProtocolError(
            "invalid_result_file", "result must be a regular file no larger than 16 MiB"
        )
    try:
        return json.loads(
            resolved.read_bytes(),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ProtocolError("nonfinite_json_number", value)
            ),
        )
    except UnicodeDecodeError as exc:
        raise ProtocolError("invalid_result_encoding", "result must be UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ProtocolError("invalid_result_json", str(exc)) from exc


def _write_exclusive(path: Path, payload: bytes) -> None:
    destination = path.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            destination.unlink()
        except FileNotFoundError:
            pass
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-json", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = _load_result(args.result_json)
        receipt = evaluate_development_result(result)
        verify_evidence_receipt(receipt, result)
        _write_exclusive(args.output_json, canonical_json_bytes(receipt))
    except (OSError, ProtocolError) as exc:
        print(f"docking_search_v2_development_evidence=blocked:{exc}")
        return 1
    print(
        "docking_search_v2_development_evidence="
        f"{receipt['decision']}:{receipt['receipt_sha256']}"
    )
    return 0 if receipt["decision"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
