#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/architecture_validation_speedpack_ab_retrospective_current.json"

BASELINE_SUMMARIES = {
    "set1_core_blind_ion_trpv1_chembl20_full": "runs/external_validation_2026-05-11_ligand_speedpack_ab_v3_set1_core_blind_ion_trpv1_chembl20_full_p0_n10000_r1_stage5_ranking_summary.json",
    "set2_expanded_ood_ion_trpv1_chembl50_full": "runs/external_validation_2026-05-11_ligand_speedpack_ab_v3_set2_expanded_ood_ion_trpv1_chembl50_full_p0_n10000_r1_stage5_ranking_summary.json",
}
CANDIDATE_SUMMARIES = {
    "set1_core_blind_ion_trpv1_chembl20_full": "runs/external_validation_2026-05-11_ligand_speedpack_ab_v4_set1_core_blind_ion_trpv1_chembl20_full_p0_n10000_r1_stage5_ranking_summary.json",
    "set2_expanded_ood_ion_trpv1_chembl50_full": "runs/external_validation_2026-05-11_ligand_speedpack_ab_v4_set2_expanded_ood_ion_trpv1_chembl50_full_p0_n10000_r1_stage5_ranking_summary.json",
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _metric(packet: dict[str, Any], key: str) -> float | None:
    metrics = packet.get("metrics")
    if isinstance(metrics, dict) and metrics.get(key) is not None:
        return float(metrics[key])
    return None


def build_architecture_validation_speedpack_ab_retrospective() -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    claim_safe = True
    for task_id, baseline_path in BASELINE_SUMMARIES.items():
        candidate_path = CANDIDATE_SUMMARIES[task_id]
        baseline = _read_json(baseline_path)
        candidate = _read_json(candidate_path)
        if not baseline or not candidate:
            claim_safe = False
            comparisons.append({"task_id": task_id, "status": "missing_artifact"})
            continue
        baseline_pass = bool(baseline.get("pass"))
        candidate_pass = bool(candidate.get("pass"))
        pass_to_fail = bool(baseline_pass and not candidate_pass)
        pr_delta = (_metric(candidate, "pr_auc") or 0.0) - (_metric(baseline, "pr_auc") or 0.0)
        top20_delta = (_metric(candidate, "topk_hit_rate") or 0.0) - (_metric(baseline, "topk_hit_rate") or 0.0)
        task_claim_safe = not pass_to_fail and pr_delta >= -0.01 and top20_delta >= -0.05
        claim_safe = claim_safe and task_claim_safe and baseline_pass and candidate_pass
        comparisons.append(
            {
                "task_id": task_id,
                "baseline_artifact": baseline_path,
                "candidate_artifact": candidate_path,
                "baseline_pass": baseline_pass,
                "candidate_pass": candidate_pass,
                "pass_to_fail": pass_to_fail,
                "pr_auc_delta": pr_delta,
                "top20_delta": top20_delta,
                "claim_safe": task_claim_safe,
            }
        )

    summary = {
        "packet_type": "architecture_validation_speedpack_ab_retrospective",
        "status": "architecture_validation_speedpack_ab_retrospective_ready" if comparisons else "blocked_architecture_validation_speedpack_ab_retrospective",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "comparison_kind": "equal_size_retrospective_v3_baseline_vs_v4_candidate",
        "baseline_tag": "2026-05-11_ligand_speedpack_ab_v3",
        "candidate_tag": "2026-05-11_ligand_speedpack_ab_v4",
        "claim_safe": claim_safe,
        "task_count": len(comparisons),
        "claim_boundary": "Retrospective equal-size A/B from completed TRPV1 speedpack runs; stage2 speed SLA not re-measured here.",
    }
    return {"summary": summary, "comparisons": comparisons}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build retrospective speedpack A/B evidence for Package B.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    args = parser.parse_args(argv)
    payload = build_architecture_validation_speedpack_ab_retrospective()
    _resolve(args.out_json).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
