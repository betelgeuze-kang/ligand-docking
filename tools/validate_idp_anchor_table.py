#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Sequence


REQUIRED_METRICS = [
    "rg_mean_range",
    "sasa_proxy_mean_range",
    "contact_persistence_range",
    "transient_helicity_range",
    "ensemble_diversity_range",
]


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _check_range(raw: Any) -> bool:
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        return False
    try:
        lo = float(raw[0])
        hi = float(raw[1])
    except Exception:
        return False
    return hi >= lo


def validate(payload: Dict[str, Any]) -> Dict[str, Any]:
    targets = dict(payload.get("targets", {}) or {})
    errors: List[Dict[str, Any]] = []
    for target, spec in sorted(targets.items()):
        row_errors: List[str] = []
        if not str(spec.get("source", "")).strip():
            row_errors.append("missing_source")
        provenance = dict(spec.get("provenance", {}) or {})
        if not str(provenance.get("kind", "")).strip():
            row_errors.append("missing_provenance_kind")
        for metric in REQUIRED_METRICS:
            if not _check_range(spec.get(metric)):
                row_errors.append(f"invalid_{metric}")
        if row_errors:
            errors.append({"target": target, "errors": row_errors})
    return {
        "target_count": len(targets),
        "error_count": len(errors),
        "errors": errors,
        "pass": len(errors) == 0,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Validate IDP observable anchor table schema.")
    p.add_argument("--anchor-json", type=str, required=True)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = _read_json(str(args.anchor_json))
    report = validate(payload)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if report["pass"] else 2)


if __name__ == "__main__":
    main()
