#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SUBSET_CONFIG_JSON = "config/idp_3bead_benchmark_v7_literature_anchor_subset.json"
DEFAULT_FULL_CONFIG_JSON = "config/idp_3bead_benchmark_v7.json"
DEFAULT_OUT_CONFIG_JSON = "config/idp_3bead_benchmark_v7_anchor_plus_page4.json"
DEFAULT_OUT_JSON = "runs/idp_anchor_plus_page4_config_current.json"
DEFAULT_OUT_MD = "runs/idp_anchor_plus_page4_config_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(subset_cfg: dict[str, Any], full_cfg: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    subset_targets = list(subset_cfg.get("targets", []) or [])
    page4_targets = [dict(row) for row in list(full_cfg.get("targets", []) or []) if str(row.get("name", "")).strip() == "page4"]
    out_cfg = dict(subset_cfg)
    out_cfg["version"] = "idp_3bead_benchmark_v7_anchor_plus_page4"
    out_cfg["description"] = (
        "Controlled 7-target literature-anchor subset plus PAGE4 as the first additional anchor-backed target "
        "for the first true broader IDP shadow-only rerun."
    )
    out_cfg["targets"] = subset_targets + page4_targets

    subset_unique_names: list[str] = []
    for row in subset_targets:
        name = str(row.get("name", "")).strip()
        if name and name not in subset_unique_names:
            subset_unique_names.append(name)

    summary = {
        "status": "anchor_plus_page4_config_ready",
        "validated_subset_target_count": len(subset_unique_names),
        "additional_anchor_target_count": 1 if page4_targets else 0,
        "additional_anchor_target_name": "page4" if page4_targets else "",
        "total_target_row_count": len(out_cfg["targets"]),
        "unique_target_count": len(subset_unique_names) + (1 if page4_targets else 0),
        "config_json": str(_resolve(DEFAULT_OUT_CONFIG_JSON)),
        "next_required_step": (
            "Use this config as the first true broader full-IDP shadow-only rerun scope while keeping broader_full_idp_promotion blocked."
            if page4_targets
            else "PAGE4 rows are missing from the full config, so do not use this config for a broader rerun yet."
        ),
    }
    return out_cfg, {"summary": summary}


def _write_markdown(path: Path, payload: dict[str, Any], out_config_path: Path) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Anchor-Plus-PAGE4 Config",
        "",
        f"- status: `{s['status']}`",
        f"- validated_subset_target_count: `{s['validated_subset_target_count']}`",
        f"- additional_anchor_target_count: `{s['additional_anchor_target_count']}`",
        f"- additional_anchor_target_name: `{s['additional_anchor_target_name']}`",
        f"- total_target_row_count: `{s['total_target_row_count']}`",
        f"- unique_target_count: `{s['unique_target_count']}`",
        f"- config_json: `{out_config_path}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build the first broader anchor-backed IDP config by adding PAGE4 to the validated subset scaffold.")
    ap.add_argument("--subset-config-json", default=DEFAULT_SUBSET_CONFIG_JSON)
    ap.add_argument("--full-config-json", default=DEFAULT_FULL_CONFIG_JSON)
    ap.add_argument("--out-config-json", default=DEFAULT_OUT_CONFIG_JSON)
    ap.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    out_cfg, payload = build_payload(_read_json(args.subset_config_json), _read_json(args.full_config_json))
    out_cfg_path = _resolve(args.out_config_json)
    out_json_path = _resolve(args.out_json)
    out_md_path = _resolve(args.out_md)
    out_cfg_path.parent.mkdir(parents=True, exist_ok=True)
    out_cfg_path.write_text(json.dumps(out_cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md_path, payload, out_cfg_path)


if __name__ == "__main__":
    main()
