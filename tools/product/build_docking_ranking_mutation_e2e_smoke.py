#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.docking_request import build_docking_job_record
from betelgeuze_product.residual_mode_policy import customer_ligand_ranking_snapshot

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/docking_ranking_mutation_e2e_smoke_current.json"

CLAIM_BOUNDARY = (
    "Docking ranking-mutation E2E smoke only; validates one fail-closed docking intake record against "
    "synthetic ligand score rows to prove customer ranking order changes only when the runtime guard unlocks. "
    "It does not execute docking engines or mutate production ledgers."
)

DOCKING_PAYLOAD = {
    "request_type": "structure_analysis_ligand_docking",
    "family": "gpcr",
    "target_id": "ADRB2",
    "pdb_content": "ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n",
    "ligands": [
        {"ligand_id": "lig_a", "smiles": "CCO"},
        {"ligand_id": "lig_b", "smiles": "CCN"},
    ],
}

PRODUCTION_GUARDED_REGISTRY = {
    "summary": {
        "default_residual_mode": "production_guarded",
        "production_promotion_allowed": True,
        "customer_facing_auto_correction_allowed": True,
        "customer_facing_score_mutation_allowed": True,
        "customer_facing_ranking_mutation_allowed": True,
        "trained_model_checkpoint_count": 1,
        "selected_sidecar_ready": True,
        "selected_sidecar_missing_output_fields": [],
    }
}

RANKING_SCORE_ROWS = [
    {
        "ligand_id": "lig_a",
        "binding_score_composite_v7": 1.0,
        "binding_score_composite_v7_residual_active": -5.0,
    },
    {
        "ligand_id": "lig_b",
        "binding_score_composite_v7": -5.0,
        "binding_score_composite_v7_residual_active": 1.0,
    },
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def run_smoke() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for shadow_only_active_locked, expected_mutation in (
        (True, False),
        (False, True),
    ):
        record = build_docking_job_record(
            DOCKING_PAYLOAD,
            job_id=f"docking_ranking_e2e_{'locked' if shadow_only_active_locked else 'unlocked'}",
            residual_registry_packet=PRODUCTION_GUARDED_REGISTRY,
            shadow_only_active_locked=shadow_only_active_locked,
        )
        ranking = customer_ligand_ranking_snapshot(
            RANKING_SCORE_ROWS,
            ranking_mutation_allowed=bool(
                record.get("production_ai_customer_facing_ranking_mutation_allowed")
            ),
        )
        row = {
            "scenario": "shadow_locked" if shadow_only_active_locked else "shadow_unlocked",
            "shadow_only_active_locked": shadow_only_active_locked,
            "production_ai_inference_subject_active": record.get("production_ai_inference_subject_active"),
            "production_ai_customer_facing_ranking_mutation_allowed": record.get(
                "production_ai_customer_facing_ranking_mutation_allowed"
            ),
            "customer_score_column": ranking["customer_score_column"],
            "base_ranking_ligand_ids": ranking["base_ranking_ligand_ids"],
            "customer_ranking_ligand_ids": ranking["customer_ranking_ligand_ids"],
            "ranking_mutated": ranking["ranking_mutated"],
            "expected_ranking_mutated": expected_mutation,
            "pass": ranking["ranking_mutated"] is expected_mutation
            and record.get("production_ai_customer_facing_ranking_mutation_allowed")
            is (not shadow_only_active_locked),
        }
        rows.append(row)

    pass_count = sum(1 for row in rows if row["pass"])
    summary = {
        "packet_type": "docking_ranking_mutation_e2e_smoke",
        "status": "docking_ranking_mutation_e2e_smoke_ready"
        if pass_count == len(rows)
        else "blocked_docking_ranking_mutation_e2e_smoke",
        "claim_boundary": CLAIM_BOUNDARY,
        "scenario_count": len(rows),
        "pass_scenario_count": pass_count,
        "fail_scenario_count": len(rows) - pass_count,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "next_required_step": (
            "Docking intake ranking guard preserves base order when locked and reorders on residual-active "
            "scores when production_guarded unlock is active."
            if pass_count == len(rows)
            else "Repair docking-to-ranking guard wiring for locked/unlocked production_guarded scenarios."
        ),
    }
    return {"summary": summary, "rows": rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="E2E smoke for docking intake ranking-mutation guard with synthetic score reorder."
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_smoke()
    path = _resolve(args.out_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
