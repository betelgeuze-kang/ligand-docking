#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENDPOINT_NOTE_JSON = "runs/gpcr_residual_chembl50_v4_endpoint_note_current.json"
DEFAULT_APPLY_DECISION_JSON = "runs/gpcr_residual_chembl50_v4_apply_decision_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_router_pause_note_current.json"
DEFAULT_OUT_MD = "runs/gpcr_router_pause_note_current.md"


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


def build_payload(endpoint_note: dict[str, Any], apply_decision: dict[str, Any]) -> dict[str, Any]:
    endpoint_s = dict(endpoint_note.get("summary", {}) or {})
    return {
        "summary": {
            "router_status": "paused_blocked",
            "endpoint_label": endpoint_s.get("endpoint_label", "GPCR chembl50_v4 locked-decoy apply-safe endpoint"),
            "decision": str(apply_decision.get("decision", "") or ""),
            "pause_reason": str(apply_decision.get("rationale", "") or ""),
            "next_required_step": "Keep GPCR router promotion paused. Use chembl50_v4 as the apply-safe locked-decoy endpoint and revisit router promotion only after a future variant removes the remaining PR regression without losing EF1 gains.",
        }
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GPCR Router Pause Note",
        "",
        f"- router_status: `{s['router_status']}`",
        f"- endpoint_label: `{s['endpoint_label']}`",
        f"- decision: `{s['decision']}`",
        "",
        s["pause_reason"],
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a short GPCR router-pause note from the current v4 apply-safe endpoint.")
    parser.add_argument("--endpoint-note-json", default=DEFAULT_ENDPOINT_NOTE_JSON)
    parser.add_argument("--apply-decision-json", default=DEFAULT_APPLY_DECISION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.endpoint_note_json), _load_json(args.apply_decision_json))
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
