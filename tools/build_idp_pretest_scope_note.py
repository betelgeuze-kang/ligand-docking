#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.operator_surface_contracts import (
    IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION,
    IDP_SAFE_SCOPE_LEGACY_SUBSET_ONLY,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUBSET_DECISION_JSON = "runs/idp_feature_state_subset_decision_current.json"
DEFAULT_OUT_JSON = "runs/idp_pretest_scope_note_current.json"
DEFAULT_OUT_MD = "runs/idp_pretest_scope_note_current.md"


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


def build_payload(subset_decision: dict[str, Any]) -> dict[str, Any]:
    s = dict(subset_decision.get("summary", {}) or {})
    return {
        "summary": {
            "allowed_now": IDP_SAFE_SCOPE_LEGACY_SUBSET_ONLY,
            "default_feature_mask": str(s.get("default_feature_mask", "") or "rg_sasa_only"),
            "blocked_now": IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION,
            "subset_safe": bool(s.get("literature_anchor_default_promotion", False)),
            "next_safe_experiment": (
                "Expand only within the current controlled commercial-pretest lane, starting with the next controlled anchor-backed shadow-only slice while keeping no coordinate correction, no ranking override, and no gate override."
            ),
            "guardrail": "Require would_have_changed_state = 0, would_have_changed_gate = 0, and no corrected-pass regression on the expanded slice.",
        }
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Pretest Scope Note",
        "",
        f"- allowed_now: `{s['allowed_now']}`",
        f"- default_feature_mask: `{s['default_feature_mask']}`",
        f"- blocked_now: `{s['blocked_now']}`",
        f"- subset_safe: `{s['subset_safe']}`",
        "",
        "This note records the legacy validated literature-anchor subset basis only; it is explanatory context for, not the current operator scope of, the controlled commercial-pretest lane. Keep broader full-IDP promotion blocked and do not introduce coordinate, ranking, or gate overrides yet.",
        "",
        "## Next Safe Experiment",
        "",
        f"- {s['next_safe_experiment']}",
        f"- {s['guardrail']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a concise operator-facing IDP pretest scope note.")
    parser.add_argument("--subset-decision-json", default=DEFAULT_SUBSET_DECISION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.subset_decision_json))
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
