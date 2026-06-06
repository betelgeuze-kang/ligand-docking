#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RANKING_CSV = "runs/ligand_blind_trpv1_chembl20_npz_v6_2026-03-11_r1_stage5_ranking_rows.csv"
DEFAULT_DECOY_LABELS_CSV = "runs/ligand_blind_trpv1_chembl20_smoke_2026-03-11_r1_hard_decoy_labels.csv"
DEFAULT_OUT_JSON = "runs/trpv1_ion_channel_matched_negative_panel_current.json"
DEFAULT_OUT_CSV = "runs/trpv1_ion_channel_matched_negative_panel_current.csv"
DEFAULT_OUT_MD = "runs/trpv1_ion_channel_matched_negative_panel_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def build_payload(ranking_frame: pd.DataFrame, decoy_labels_frame: pd.DataFrame) -> dict[str, Any]:
    ranking = ranking_frame.copy()
    labels = decoy_labels_frame.copy()

    target_rows = ranking[ranking["target"].eq("TRPV1_ION_CHANNEL_BLIND")].copy()
    positive_rows = target_rows[target_rows["is_binder"].eq(1)].sort_values("binding_score_composite_v5").head(3)
    positive_top3_mean_distance = float(positive_rows["mean_min_distance_A"].mean())

    negative_rows = target_rows[target_rows["is_binder"].eq(0)].copy()
    negative_rows["distance_gap_to_positive_top3_mean_A"] = (
        negative_rows["mean_min_distance_A"] - positive_top3_mean_distance
    ).abs()
    negative_rows["score_abs"] = negative_rows["binding_score_composite_v5"].abs()
    negative_rows = negative_rows.merge(
        labels[
            [
                "ligand_id",
                "smiles",
                "scaffold",
                "molecular_weight",
                "logp",
                "h_donors",
                "h_acceptors",
                "rot_bonds",
                "decoy_match_distance",
                "decoy_hardness_score",
            ]
        ],
        on="ligand_id",
        how="left",
    )
    negative_rows = negative_rows.sort_values(
        ["distance_gap_to_positive_top3_mean_A", "score_abs", "decoy_match_distance", "molecular_weight"]
    )

    selected: list[dict[str, Any]] = []
    used_scaffolds: set[str] = set()
    for _, row in negative_rows.iterrows():
        scaffold = str(row.get("scaffold", "")).strip()
        if scaffold and scaffold in used_scaffolds:
            continue
        selected.append(dict(row))
        if scaffold:
            used_scaffolds.add(scaffold)
        if len(selected) == 3:
            break
    if len(selected) < 3:
        for _, row in negative_rows.iterrows():
            ligand_id = str(row.get("ligand_id", "")).strip()
            if any(existing["ligand_id"] == ligand_id for existing in selected):
                continue
            selected.append(dict(row))
            if len(selected) == 3:
                break

    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(selected, start=1):
        rows.append(
            {
                "target_id": "TRPV1_ION_CHANNEL_BLIND",
                "panel_slot": f"negative_{idx}",
                "compound_id": row["ligand_id"],
                "compound_name": row["ligand_id"],
                "expected_class": "matched_negative_control_locked_internal",
                "expected_direction": "lower_activity_than_positive_panel",
                "negative_control_locked": True,
                "external_send_ready": False,
                "negative_control_kind": "synthetic_hard_decoy_internal",
                "selection_rule": "geometry_matched_to_top3_positive_mean_distance_with_scaffold_diversity",
                "mean_min_distance_A": row["mean_min_distance_A"],
                "binding_score_composite_v5": row["binding_score_composite_v5"],
                "distance_gap_to_positive_top3_mean_A": row["distance_gap_to_positive_top3_mean_A"],
                "reference_binding_kcal_mol": row["reference_binding_kcal_mol"],
                "smiles": str(row.get("smiles", "")).strip(),
                "scaffold": str(row.get("scaffold", "")).strip(),
                "molecular_weight": row.get("molecular_weight", ""),
                "logp": row.get("logp", ""),
                "h_donors": row.get("h_donors", ""),
                "h_acceptors": row.get("h_acceptors", ""),
                "rot_bonds": row.get("rot_bonds", ""),
                "decoy_match_distance": row.get("decoy_match_distance", ""),
                "decoy_hardness_score": row.get("decoy_hardness_score", ""),
                "repo_source": (
                    f"{DEFAULT_RANKING_CSV};{DEFAULT_DECOY_LABELS_CSV}"
                ),
                "note": (
                    "Internal matched negative selected from TRPV1 synthetic hard decoys. "
                    "Useful for internal contrast control, but not yet vendor-feasible for external CRO send."
                ),
            }
        )

    summary = {
        "status": "trpv1_matched_negative_panel_ready",
        "target_id": "TRPV1_ION_CHANNEL_BLIND",
        "selected_negative_count": len(rows),
        "matched_negative_slot_count_required": 3,
        "matched_negative_slot_count_locked": len(rows),
        "matched_negative_panel_locked": len(rows) == 3,
        "matched_negative_panel_sendable": False,
        "panel_kind": "synthetic_hard_decoy_internal_review_only",
        "positive_top3_mean_distance_A": positive_top3_mean_distance,
        "selection_rule": "geometry closeness to positive top-3 mean distance, then weak-score preference, then scaffold diversity",
        "next_required_step": "Replace or source vendor-feasible matched negatives before treating the TRPV1 six-compound panel as externally sendable.",
    }
    structured = {
        "internal_only_reason": "Selected negatives come from the synthetic hard-decoy scaffold and are not treated as purchasable controls.",
        "panel_lock_semantics": "This panel counts as matched-negative locked for internal review, but not as externally sendable CRO material.",
    }
    return {"summary": summary, "structured": structured, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# TRPV1 Matched Negative Panel",
        "",
        f"- status: `{summary['status']}`",
        f"- target_id: `{summary['target_id']}`",
        f"- selected_negative_count: `{summary['selected_negative_count']}`",
        f"- matched_negative_panel_locked: `{summary['matched_negative_panel_locked']}`",
        f"- matched_negative_panel_sendable: `{summary['matched_negative_panel_sendable']}`",
        f"- panel_kind: `{summary['panel_kind']}`",
        f"- positive_top3_mean_distance_A: `{summary['positive_top3_mean_distance_A']:.6f}`",
        "",
        f"- {summary['selection_rule']}",
        "",
        "| panel_slot | compound_id | scaffold | mean_min_distance_A | distance_gap_to_positive_top3_mean_A | binding_score_composite_v5 | external_send_ready |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['panel_slot']}` | `{row['compound_id']}` | `{row['scaffold']}` | `{row['mean_min_distance_A']}` | `{row['distance_gap_to_positive_top3_mean_A']}` | `{row['binding_score_composite_v5']}` | `{row['external_send_ready']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the internal matched-negative panel for TRPV1 from stage5 ranking and hard-decoy labels.")
    parser.add_argument("--ranking-csv", default=DEFAULT_RANKING_CSV)
    parser.add_argument("--decoy-labels-csv", default=DEFAULT_DECOY_LABELS_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        pd.read_csv(_resolve(args.ranking_csv)),
        pd.read_csv(_resolve(args.decoy_labels_csv)),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
