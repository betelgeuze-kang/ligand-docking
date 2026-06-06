#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BASE_CONFIG_JSON = "config/idp_3bead_benchmark_v7.json"
DEFAULT_ANCHOR_JSON = "config/idp_observable_anchors_expanded_v5.json"
DEFAULT_OUT_CONFIG_JSON = "config/idp_3bead_benchmark_v7_literature_anchor_subset.json"
DEFAULT_OUT_JSON = "runs/idp_literature_anchor_subset_holdout_current.json"
DEFAULT_OUT_MD = "runs/idp_literature_anchor_subset_holdout_current.md"


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


def build_payload(base_cfg: dict[str, Any], anchor_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    anchors = dict(anchor_payload.get("targets", {}) or {})
    literature_targets = sorted(name for name, meta in anchors.items() if str((meta or {}).get("source", "")) != "branch_family_provisional")
    filtered_targets = [t for t in list(base_cfg.get("targets", [])) if str(t.get("name", "")) in set(literature_targets)]
    out_cfg = dict(base_cfg)
    out_cfg["version"] = f"{base_cfg.get('version', 'idp_3bead_benchmark_v7')}_literature_anchor_subset"
    out_cfg["description"] = "Literature-anchor-only subset scaffold for IDP feature_state_v1 shadow holdout."
    out_cfg["targets"] = filtered_targets
    counts = Counter(str(t.get("name", "")) for t in filtered_targets)
    summary = {
        "base_target_rows": int(len(list(base_cfg.get("targets", [])))),
        "subset_target_rows": int(len(filtered_targets)),
        "literature_anchor_target_count": int(len(literature_targets)),
        "subset_targets": literature_targets,
        "subset_condition_counts": dict(sorted(counts.items())),
        "shadow_mode": "feature_state_v1",
        "coordinate_correction": False,
        "ranking_override": False,
        "gate_override": False,
        "next_required_step": "Run run_idp_3bead_holdout_pipeline.py on this config with --kalman-shadow-enable 1 --kalman-shadow-mode feature_state_v1.",
    }
    payload = {
        "summary": summary,
        "run_command": [
            "python3",
            "tools/run_idp_3bead_holdout_pipeline.py",
            "--config-json",
            str(_resolve(DEFAULT_OUT_CONFIG_JSON)),
            "--device",
            "cuda",
            "--out-prefix",
            "runs/idp_3bead_holdout_v7_literature_anchor_kfshadow_r1",
            "--resume-existing",
            "1",
            "--kalman-shadow-enable",
            "1",
            "--kalman-shadow-mode",
            "feature_state_v1",
            "--kalman-shadow-family-token",
            "idp",
            "--kalman-shadow-obs-noise-scale",
            "0.15",
            "--kalman-shadow-process-noise-scale",
            "0.03",
            "--kalman-shadow-delta-cap-frac",
            "0.25",
        ],
    }
    return out_cfg, payload


def _write_markdown(path: Path, payload: dict[str, Any], out_config_path: Path) -> None:
    summary = payload["summary"]
    lines = [
        "# IDP Literature-Anchor Subset Holdout Scaffold",
        "",
        f"- base_target_rows: `{summary['base_target_rows']}`",
        f"- subset_target_rows: `{summary['subset_target_rows']}`",
        f"- literature_anchor_target_count: `{summary['literature_anchor_target_count']}`",
        f"- shadow_mode: `{summary['shadow_mode']}`",
        f"- coordinate_correction: `{summary['coordinate_correction']}`",
        f"- ranking_override: `{summary['ranking_override']}`",
        f"- gate_override: `{summary['gate_override']}`",
        f"- config_json: `{out_config_path}`",
        "",
        "## Subset Targets",
        "",
    ]
    for target in summary["subset_targets"]:
        lines.append(f"- `{target}` x {summary['subset_condition_counts'][target]}")
    lines.extend([
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Suggested Command",
        "",
        "```bash",
        " ".join(payload["run_command"]),
        "```",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build literature-anchor-only subset scaffold for IDP feature_state holdout.")
    ap.add_argument("--base-config-json", default=DEFAULT_BASE_CONFIG_JSON)
    ap.add_argument("--anchor-json", default=DEFAULT_ANCHOR_JSON)
    ap.add_argument("--out-config-json", default=DEFAULT_OUT_CONFIG_JSON)
    ap.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    out_cfg, payload = build_payload(_read_json(args.base_config_json), _read_json(args.anchor_json))
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
