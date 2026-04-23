#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path


REPO_ROOT = Path("/home/betelgeuze/분자동역학")
OUT_DIR = REPO_ROOT / "runs" / "viewer_compare_writeback_smoke"
CURRENT_BUNDLE = REPO_ROOT / "runs" / "selected_allatom_visual_bundle_current.json"
OUT_FIXTURE_JSON = OUT_DIR / "writeback_before_smoke_current.json"
OUT_SUMMARY_JSON = OUT_DIR / "writeback_before_smoke_summary_current.json"


def build_before_fixture(payload: dict) -> tuple[dict, dict]:
    rows = list(payload.get("rows") or [])
    before_rows = []
    changed_keys: list[str] = []

    for index, row in enumerate(rows[:3]):
        mutated = dict(row)
        ligand_id = str(mutated.get("ligand_id") or f"row_{index + 1}")
        if index == 0:
            mutated["translation_gate_status"] = "review_only_before"
            mutated["shortlist_tier"] = "review"
            mutated["recommended_next_expensive_lane"] = "pre_writeback_lane"
            mutated["commercial_overall_score_v2"] = round(max(0.0, float(mutated.get("commercial_overall_score_v2") or 0.0) - 7.5), 3)
            mutated["mean_min_distance_A"] = round(float(mutated.get("mean_min_distance_A") or 0.0) + 0.35, 3)
            changed_keys.append(f"{ligand_id}:translation/commercial/distance")
        elif index == 1:
            mutated["commercial_overall_score_v2"] = round(max(0.0, float(mutated.get("commercial_overall_score_v2") or 0.0) - 3.0), 3)
            mutated["binding_energy_proxy"] = round(float(mutated.get("binding_energy_proxy") or 0.0) + 0.015, 3)
            changed_keys.append(f"{ligand_id}:commercial/energy")
        before_rows.append(mutated)

    if rows:
        extra = dict(rows[0])
        extra["packet_rank"] = 99
        extra["ligand_id"] = "writeback_before_only_fixture"
        extra["compound_name"] = "writeback_before_only_fixture"
        extra["translation_gate_status"] = "before_only"
        extra["shortlist_tier"] = "defer"
        extra["recommended_next_expensive_lane"] = "before_only_lane"
        extra["commercial_overall_score_v2"] = 12.3
        before_rows.append(extra)

    fixture = dict(payload)
    fixture["rows"] = before_rows
    summary = dict(payload.get("summary") or {})
    summary["status"] = "selected_allatom_visual_bundle_ready_before_fixture"
    summary["topk_count"] = len(before_rows)
    summary["human_summary"] = "viewer compare/writeback browser smoke before fixture"
    fixture["summary"] = summary

    summary_payload = {
        "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_bundle_json": str(CURRENT_BUNDLE),
        "fixture_json": str(OUT_FIXTURE_JSON),
        "matched_expected_count": min(3, len(rows)),
        "after_only_expected_count": max(0, len(rows) - 3),
        "before_only_expected_count": 1 if rows else 0,
        "changed_keys": changed_keys,
    }
    return fixture, summary_payload


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.loads(CURRENT_BUNDLE.read_text(encoding="utf-8"))
    fixture, summary_payload = build_before_fixture(payload)
    OUT_FIXTURE_JSON.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_SUMMARY_JSON.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
