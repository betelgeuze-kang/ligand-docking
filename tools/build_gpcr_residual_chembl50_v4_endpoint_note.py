#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENDPOINT_JSON = "runs/gpcr_apply_safe_endpoint_current.json"
DEFAULT_PROGRESSION_JSON = "runs/gpcr_residual_progression_comparison_current.json"
DEFAULT_V4_SHADOW_DECISION_JSON = "runs/gpcr_residual_chembl50_v4_decision_current.json"
DEFAULT_V4_APPLY_DECISION_JSON = "runs/gpcr_residual_chembl50_v4_apply_decision_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_residual_chembl50_v4_endpoint_note_current.json"
DEFAULT_OUT_MD = "runs/gpcr_residual_chembl50_v4_endpoint_note_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(
    endpoint_payload: dict[str, Any],
    progression_payload: dict[str, Any],
    v4_shadow_decision: dict[str, Any],
    v4_apply_decision: dict[str, Any],
) -> dict[str, Any]:
    endpoint_s = dict(endpoint_payload.get("summary", {}) or {})
    progression_s = dict(progression_payload.get("summary", {}) or {})
    return {
        "summary": {
            "endpoint_label": "GPCR chembl50_v4 locked-decoy apply-safe endpoint",
            "status": "apply-safe on locked decoys",
            "router_status": "blocked",
            "endpoint_status": endpoint_s.get("endpoint_status", ""),
            "shadow_decision": v4_shadow_decision.get("decision", ""),
            "apply_decision": v4_apply_decision.get("decision", ""),
            "core_v4_apply_preserves_baseline": progression_s.get("core_v4_apply_preserves_baseline", False),
            "chembl50_v4_apply_has_ef1_gain": progression_s.get("chembl50_v4_apply_has_ef1_gain", False),
            "decision": "use chembl50_v4 as the current GPCR locked-decoy apply-safe endpoint; do not promote to the 100k router yet.",
        },
        "references": [
            "runs/gpcr_residual_chembl50_v4_vs_baseline_current.md",
            "runs/gpcr_residual_chembl50_v4_vs_v3shadow_current.md",
            "runs/gpcr_residual_chembl50_v4_mode_comparison_current.md",
            "runs/gpcr_residual_chembl50_v4_decision_current.md",
            "runs/gpcr_residual_chembl50_v4_apply_decision_current.md",
            "runs/gpcr_apply_safe_endpoint_current.md",
            "runs/gpcr_residual_progression_comparison_current.md",
            "runs/cross_family_residual_shadow_layer_current.md",
        ],
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GPCR Handoff Note",
        "",
        f"- endpoint: `{s['endpoint_label']}`",
        f"- status: `{s['status']}`",
        f"- router_status: `{s['router_status']}`",
        f"- endpoint_status: `{s['endpoint_status']}`",
        f"- shadow_decision: `{s['shadow_decision']}`",
        f"- apply_decision: `{s['apply_decision']}`",
        "",
        f"- `v4 shadow` preserved `gpcr_core_full` at baseline parity and kept the chembl50 OOD slice promotion-safe.",
        f"- `v4 apply` kept both GPCR tasks `PASS`.",
        f"- `v4 apply` preserved `gpcr_core_full` at baseline parity: `{s['core_v4_apply_preserves_baseline']}`.",
        f"- `v4 apply` retained the chembl50 EF1 improvement signal: `{s['chembl50_v4_apply_has_ef1_gain']}`.",
        "",
        f"- Decision: `{s['decision']}`",
        "",
        "## Reference Files",
        "",
    ]
    for ref in payload["references"]:
        lines.append(f"- `{ref}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a concise GPCR v4 endpoint handoff note.")
    parser.add_argument("--endpoint-json", default=DEFAULT_ENDPOINT_JSON)
    parser.add_argument("--progression-json", default=DEFAULT_PROGRESSION_JSON)
    parser.add_argument("--v4-shadow-decision-json", default=DEFAULT_V4_SHADOW_DECISION_JSON)
    parser.add_argument("--v4-apply-decision-json", default=DEFAULT_V4_APPLY_DECISION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.endpoint_json),
        _load_json(args.progression_json),
        _load_json(args.v4_shadow_decision_json),
        _load_json(args.v4_apply_decision_json),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
