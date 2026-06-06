#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENDPOINT_JSON = "runs/gpcr_apply_safe_endpoint_current.json"
DEFAULT_ROUTER_PAUSE_JSON = "runs/gpcr_router_pause_note_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_pretest_handoff_packet_current.json"
DEFAULT_OUT_MD = "runs/gpcr_pretest_handoff_packet_current.md"


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


def build_payload(endpoint_payload: dict[str, Any], router_pause_payload: dict[str, Any]) -> dict[str, Any]:
    endpoint = dict(endpoint_payload.get("summary", {}) or {})
    router = dict(router_pause_payload.get("summary", {}) or {})
    return {
        "summary": {
            "safe_now": "chembl50_v4_locked_decoy_apply_safe_endpoint",
            "blocked_now": "100k_router_promotion",
            "endpoint_status": endpoint.get("endpoint_status", ""),
            "router_status": router.get("router_status", ""),
            "next_safe_experiment": "Only another locked-decoy GPCR variant that targets the remaining chembl50 PR regression while preserving core parity.",
            "do_not_do": "Do not promote GPCR to the 100k router path yet.",
        }
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GPCR Pretest Handoff Packet",
        "",
        f"- safe_now: `{s['safe_now']}`",
        f"- blocked_now: `{s['blocked_now']}`",
        f"- endpoint_status: `{s['endpoint_status']}`",
        f"- router_status: `{s['router_status']}`",
        "",
        "## Next Safe Experiment",
        "",
        f"- {s['next_safe_experiment']}",
        "",
        "## Do Not Do",
        "",
        f"- {s['do_not_do']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a concise GPCR pretest handoff packet.")
    parser.add_argument("--endpoint-json", default=DEFAULT_ENDPOINT_JSON)
    parser.add_argument("--router-pause-json", default=DEFAULT_ROUTER_PAUSE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.endpoint_json), _load_json(args.router_pause_json))
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
