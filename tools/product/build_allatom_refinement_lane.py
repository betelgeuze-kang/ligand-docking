from __future__ import annotations

import argparse
import importlib.util
import json
import math
import shutil
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

SCORE_COLS = (
    "proxy_binding_energy_score",
    "binding_score_stronger_physics_v1",
    "binding_energy_explicit_water_recheck_kcal_mol_proxy",
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "binding_energy_proxy",
)
EVIDENCE_COLS = (
    "allatom_backend",
    "allatom_refined_energy_kcal_mol",
    "allatom_minimized_rmsd_A",
    "allatom_parameterization_status",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    try:
        v = float(value)
        return None if math.isnan(v) else float(v)
    except Exception:
        return None


def _score_col(df: pd.DataFrame, requested: str = "") -> str:
    if requested and requested in df.columns:
        return requested
    for col in SCORE_COLS:
        if col in df.columns:
            return col
    return ""


def _environment() -> dict[str, Any]:
    modules = {name: importlib.util.find_spec(name) is not None for name in ("openmm", "pdbfixer")}
    executables = {name: bool(shutil.which(name)) for name in ("antechamber", "parmchk2", "obabel")}
    return {
        "modules": modules,
        "executables": executables,
        "runtime_ready": bool(modules.get("openmm") and (executables.get("antechamber") or executables.get("obabel"))),
    }


def _row_id(row: dict[str, Any], idx: int) -> str:
    target = _text(row.get("target") or row.get("target_id") or row.get("pdb_id"))
    ligand = _text(row.get("ligand_id") or row.get("compound_id") or row.get("pose_id"))
    if target and ligand:
        return f"{target}::{ligand}"
    return _text(row.get("queue_id") or row.get("row_id")) or f"row_{idx:05d}"


def _selected_rows(df: pd.DataFrame, score_col: str, topk: int, lower_better: bool) -> pd.DataFrame:
    work = df.copy()
    if score_col:
        work["_sort_score"] = pd.to_numeric(work[score_col], errors="coerce")
        work = work.sort_values("_sort_score", ascending=bool(lower_better), na_position="last")
    if int(topk) > 0:
        work = work.head(int(topk))
    return work.drop(columns=["_sort_score"], errors="ignore").reset_index(drop=True)


def _evidence(selected: pd.DataFrame) -> dict[str, Any]:
    missing = [col for col in EVIDENCE_COLS if col not in selected.columns]
    if missing:
        return {"complete": False, "missing_columns": missing, "complete_rows": 0, "failed_rows": []}
    complete_rows = 0
    failed_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(selected.to_dict(orient="records"), start=1):
        blockers: list[str] = []
        if not _text(row.get("allatom_backend")):
            blockers.append("backend_missing")
        if _text(row.get("allatom_parameterization_status")) not in {"pass", "ready", "parameterized"}:
            blockers.append("parameterization_not_ready")
        if _num(row.get("allatom_refined_energy_kcal_mol")) is None:
            blockers.append("energy_missing")
        rmsd = _num(row.get("allatom_minimized_rmsd_A"))
        if rmsd is None:
            blockers.append("rmsd_missing")
        elif rmsd > 3.0:
            blockers.append("rmsd_above_review_threshold")
        if blockers:
            failed_rows.append({"row_id": _row_id(row, idx), "blockers": blockers})
        else:
            complete_rows += 1
    return {
        "complete": bool(complete_rows == len(selected) and len(selected) > 0),
        "missing_columns": [],
        "complete_rows": int(complete_rows),
        "failed_rows": failed_rows,
    }


def build_allatom_refinement_lane(
    scores_csv: str,
    *,
    out_json: str,
    out_csv: str = "",
    out_md: str = "",
    score_col: str = "",
    topk: int = 25,
    lower_better: bool = True,
) -> dict[str, Any]:
    df = pd.read_csv(scores_csv)
    used_score_col = _score_col(df, score_col)
    selected = _selected_rows(df, used_score_col, topk, lower_better)
    env = _environment()
    evidence = _evidence(selected)
    rows = [
        {
            "row_id": _row_id(row, idx),
            "target": _text(row.get("target") or row.get("target_id") or row.get("pdb_id")),
            "ligand_id": _text(row.get("ligand_id") or row.get("compound_id") or row.get("pose_id")),
            "score_col": used_score_col,
            "score_value": row.get(used_score_col) if used_score_col else None,
            "required_evidence_columns": list(EVIDENCE_COLS),
        }
        for idx, row in enumerate(selected.to_dict(orient="records"), start=1)
    ]
    status = "allatom_refinement_evidence_ready" if evidence["complete"] else "allatom_refinement_work_order_ready"
    payload = {
        "summary": {
            "status": status,
            "row_count": int(len(selected)),
            "score_col_used": used_score_col,
            "runtime_ready": bool(env["runtime_ready"]),
            "evidence_complete": bool(evidence["complete"]),
            "claim_boundary": "P2 optional refinement work order/evidence surface only; no broad parity claim.",
        },
        "environment": env,
        "evidence": evidence,
        "work_order_rows": rows,
    }
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(out_json).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if out_csv:
        Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out_csv, index=False)
    if out_md:
        Path(out_md).parent.mkdir(parents=True, exist_ok=True)
        Path(out_md).write_text(f"# P2 All-Atom Refinement Lane\n\n- status: `{status}`\n- rows: {len(rows)}\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores-csv", required=True)
    parser.add_argument("--score-col", default="")
    parser.add_argument("--topk", type=int, default=25)
    parser.add_argument("--lower-better", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-json", default="runs/allatom_refinement_lane_current.json")
    parser.add_argument("--out-csv", default="runs/allatom_refinement_lane_work_order_current.csv")
    parser.add_argument("--out-md", default="runs/allatom_refinement_lane_current.md")
    args = parser.parse_args(argv)
    payload = build_allatom_refinement_lane(
        args.scores_csv,
        out_json=args.out_json,
        out_csv=args.out_csv,
        out_md=args.out_md,
        score_col=args.score_col,
        topk=args.topk,
        lower_better=args.lower_better,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
