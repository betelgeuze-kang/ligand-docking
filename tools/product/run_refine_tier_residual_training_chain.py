#!/usr/bin/env python3
"""Build refine-tier supervised dataset and train residual production score model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

from tools.product.build_refine_tier_residual_training_dataset import enrich_refine_tier_labels
from tools.product.build_residual_production_supervised_dataset import (
    build_residual_production_supervised_dataset,
    _write_json,
)
from tools.train_residual_production_score_model import train_residual_production_score_model
from tools.builder_table_utils import write_csv_rows

DEFAULT_STAGE5_GLOB = "runs/*stage5_ranking_rows.csv"
DEFAULT_STAGE3_GLOB = "runs/*stage3_scores.csv"
DEFAULT_DATASET_CSV = "runs/residual_production_supervised_dataset_current.csv"
DEFAULT_ENRICHED_CSV = "runs/residual_production_supervised_dataset_refine_tier_current.csv"
DEFAULT_CHECKPOINT = "models/residual_production_score_model_refine_tier_current.pt"
DEFAULT_SUMMARY_JSON = "runs/refine_tier_residual_training_chain_current.json"
DEFAULT_FORCE_DERIVATION_JSON = "runs/residual_force_derivation_validation_current.json"

CLAIM_BOUNDARY = (
    "Refine-tier residual training chain only; materializes a supervised dataset, enriches refine-tier labels "
    "from stage3 scoring CSVs, and trains a local residual checkpoint. It does not promote production mode, "
    "enable execution, upload, or mutate external state."
)


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _latest_stage3_csv(stage3_glob: str) -> Path | None:
    paths = sorted(_resolve(stage3_glob).parent.glob(Path(stage3_glob).name))
    if not paths:
        for match in sorted(ROOT.glob(stage3_glob)):
            paths.append(match)
    return paths[-1] if paths else None


def run_refine_tier_residual_training_chain(
    *,
    stage5_glob: str = DEFAULT_STAGE5_GLOB,
    stage3_csv: str = "",
    stage3_glob: str = DEFAULT_STAGE3_GLOB,
    stage3_refine_glob: str = "",
    dataset_csv: str = DEFAULT_DATASET_CSV,
    enriched_csv: str = DEFAULT_ENRICHED_CSV,
    out_checkpoint: str = DEFAULT_CHECKPOINT,
    out_summary_json: str = DEFAULT_SUMMARY_JSON,
    min_rows: int = 40,
    min_targets: int = 1,
    epochs: int = 3,
    hidden_dim: int = 16,
    batch_size: int = 16,
    device_name: str = "cpu",
    force_derivation_json: str = DEFAULT_FORCE_DERIVATION_JSON,
) -> dict[str, Any]:
    dataset_payload = build_residual_production_supervised_dataset(
        stage5_glob=stage5_glob,
        min_rows=min_rows,
        min_targets=min_targets,
    )
    base_rows = list(dataset_payload.get("rows") or [])
    dataset_path = _resolve(dataset_csv)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    if base_rows:
        write_csv_rows(dataset_path, base_rows)

    stage3_path = _resolve(stage3_csv) if str(stage3_csv).strip() else _latest_stage3_csv(stage3_glob)
    enriched_path = _resolve(enriched_csv)
    enrich_summary: dict[str, Any] = {"status": "skipped_no_base_dataset"}
    train_input = dataset_path
    if base_rows and str(stage3_refine_glob).strip():
        enrich_summary = enrich_refine_tier_labels(
            input_csv=dataset_path,
            stage3_glob=str(stage3_refine_glob),
            out_csv=enriched_path,
        )
        train_input = enriched_path
    elif base_rows and stage3_path and stage3_path.exists():
        enrich_summary = enrich_refine_tier_labels(
            input_csv=dataset_path,
            stage3_csv=stage3_path,
            out_csv=enriched_path,
        )
        train_input = enriched_path
    elif base_rows:
        enrich_summary = {
            "status": "skipped_missing_stage3_csv",
            "stage3_csv": str(stage3_path) if stage3_path else "",
        }

    train_summary: dict[str, Any] = {"status": "skipped_no_train_rows"}
    if train_input.exists():
        train_summary = train_residual_production_score_model(
            input_csv=str(train_input),
            out_checkpoint=str(_resolve(out_checkpoint)),
            epochs=int(epochs),
            hidden_dim=int(hidden_dim),
            batch_size=int(batch_size),
            device_name=str(device_name),
            force_derivation_json=str(force_derivation_json),
        )

    chain_ready = bool(base_rows) and int(enrich_summary.get("refine_tier_label_rows", 0) or 0) > 0
    training_ready = bool(train_summary.get("train_rows", 0))
    summary = {
        "packet_type": "refine_tier_residual_training_chain",
        "status": "refine_tier_training_chain_ready" if chain_ready and training_ready else "blocked_refine_tier_training_chain",
        "refine_tier_training_chain_ready": chain_ready and training_ready,
        "dataset_rows": len(base_rows),
        "dataset_csv": str(dataset_path),
        "enriched_csv": str(enriched_path),
        "stage3_csv": str(stage3_path) if stage3_path else "",
        "stage3_refine_glob": str(stage3_refine_glob or ""),
        "enrichment": enrich_summary,
        "training": train_summary,
        "out_checkpoint": str(_resolve(out_checkpoint)),
        "execution_enabled": False,
        "model_promoted": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    _write_json(out_summary_json, {"summary": summary})
    md_path = _resolve(str(out_summary_json).replace(".json", ".md"))
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(
        "\n".join(
            [
                "# Refine-Tier Residual Training Chain",
                "",
                f"- status: `{summary['status']}`",
                f"- refine_tier_training_chain_ready: `{summary['refine_tier_training_chain_ready']}`",
                f"- dataset_rows: `{summary['dataset_rows']}`",
                f"- refine_tier_label_rows: `{summary['enrichment'].get('refine_tier_label_rows', 0)}`",
                f"- out_checkpoint: `{summary['out_checkpoint']}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description="Run refine-tier supervised dataset enrichment and residual training chain.")
    p.add_argument("--stage5-glob", type=str, default=DEFAULT_STAGE5_GLOB)
    p.add_argument("--stage3-csv", type=str, default="")
    p.add_argument("--stage3-glob", type=str, default=DEFAULT_STAGE3_GLOB)
    p.add_argument(
        "--stage3-refine-glob",
        type=str,
        default="",
        help="Optional glob of refined stage3 CSVs (deltaG_mm_gbsa_kcal_mol) for multi-source label enrichment.",
    )
    p.add_argument("--dataset-csv", type=str, default=DEFAULT_DATASET_CSV)
    p.add_argument("--enriched-csv", type=str, default=DEFAULT_ENRICHED_CSV)
    p.add_argument("--out-checkpoint", type=str, default=DEFAULT_CHECKPOINT)
    p.add_argument("--out-summary-json", type=str, default=DEFAULT_SUMMARY_JSON)
    p.add_argument("--min-rows", type=int, default=40)
    p.add_argument("--min-targets", type=int, default=1)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--hidden-dim", type=int, default=16)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--force-derivation-json", type=str, default=DEFAULT_FORCE_DERIVATION_JSON)
    args = p.parse_args()
    summary = run_refine_tier_residual_training_chain(
        stage5_glob=args.stage5_glob,
        stage3_csv=args.stage3_csv,
        stage3_glob=args.stage3_glob,
        stage3_refine_glob=args.stage3_refine_glob,
        dataset_csv=args.dataset_csv,
        enriched_csv=args.enriched_csv,
        out_checkpoint=args.out_checkpoint,
        out_summary_json=args.out_summary_json,
        min_rows=int(args.min_rows),
        min_targets=int(args.min_targets),
        epochs=int(args.epochs),
        hidden_dim=int(args.hidden_dim),
        batch_size=int(args.batch_size),
        device_name=str(args.device),
        force_derivation_json=str(args.force_derivation_json),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
