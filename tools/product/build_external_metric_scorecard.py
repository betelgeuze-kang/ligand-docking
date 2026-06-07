#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmark.external_metric_scorecard import build_external_metric_scorecard

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = "config/p2_external_metric_inputs.example.json"
DEFAULT_OUT = "runs/external_metric_scorecard_current.json"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd = (Path.cwd() / path).resolve()
    return cwd if cwd.exists() else (ROOT / path).resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build external metric scorecard (P2).")
    parser.add_argument("--input-json", default=DEFAULT_INPUT)
    parser.add_argument("--out-json", default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    input_path = _resolve(args.input_json)
    inputs: list[dict[str, Any]] = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(inputs, list):
        raise SystemExit("input-json must be a JSON array of row objects")
    payload = build_external_metric_scorecard(inputs=inputs)
    out = _resolve(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
