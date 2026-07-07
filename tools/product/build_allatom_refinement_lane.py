from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import pandas as pd


def build_allatom_refinement_lane(scores_csv: str, *, out_json: str) -> dict:
    df = pd.read_csv(scores_csv)
    payload = {
        "summary": {
            "status": "allatom_refinement_work_order_ready",
            "row_count": int(len(df)),
            "claim_boundary": "P2 optional refinement work order only; no broad parity claim.",
        },
        "required_evidence_columns": [
            "allatom_backend",
            "allatom_refined_energy_kcal_mol",
            "allatom_minimized_rmsd_A",
            "allatom_parameterization_status",
        ],
    }
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(out_json).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores-csv", required=True)
    parser.add_argument("--out-json", default="runs/allatom_refinement_lane_current.json")
    args = parser.parse_args(argv)
    print(json.dumps(build_allatom_refinement_lane(args.scores_csv, out_json=args.out_json)["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
