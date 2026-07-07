from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

SUPPORTED_ENGINES = {"vina", "gnina", "smina"}
REQUIRED_RESULT_COLUMNS = ("target", "ligand_id", "baseline_engine", "baseline_score", "pose_path")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_csv(path: str) -> pd.DataFrame:
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(f"csv not found: {path}")
    return pd.read_csv(src)


def _target_rows(path: str) -> list[dict[str, Any]]:
    df = _read_csv(path)
    if "target" not in df.columns and "target_id" in df.columns:
        df = df.rename(columns={"target_id": "target"})
    if "target" not in df.columns:
        raise ValueError("targets csv must include target or target_id")
    return df.to_dict(orient="records")


def _ligand_rows(path: str) -> list[dict[str, Any]]:
    df = _read_csv(path)
    if "ligand_id" not in df.columns:
        raise ValueError("ligands csv must include ligand_id")
    return df.to_dict(orient="records")


def _work_rows(targets_csv: str, ligands_csv: str, engine: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for target in _target_rows(targets_csv):
        for ligand in _ligand_rows(ligands_csv):
            tid = _text(target.get("target") or target.get("target_id"))
            lid = _text(ligand.get("ligand_id"))
            rows.append(
                {
                    "target": tid,
                    "ligand_id": lid,
                    "baseline_engine": engine,
                    "receptor_path": _text(target.get("receptor_path") or target.get("native_pdb_path") or target.get("pdb_path")),
                    "ligand_path": _text(ligand.get("ligand_path") or ligand.get("sdf_path") or ligand.get("pdbqt_path")),
                    "smiles": _text(ligand.get("smiles")),
                    "operator_result_required_columns": list(REQUIRED_RESULT_COLUMNS),
                    "claim_boundary": "External baseline comparison work order only; product runtime remains independent.",
                }
            )
    return rows


def _validate_results(results_csv: str) -> dict[str, Any]:
    if not results_csv:
        return {"provided": False, "complete": False, "missing_columns": list(REQUIRED_RESULT_COLUMNS), "row_count": 0}
    df = _read_csv(results_csv)
    missing = [col for col in REQUIRED_RESULT_COLUMNS if col not in df.columns]
    complete_rows = 0
    failed_rows: list[dict[str, Any]] = []
    if not missing:
        for idx, row in enumerate(df.to_dict(orient="records"), start=1):
            blockers: list[str] = []
            for col in REQUIRED_RESULT_COLUMNS:
                if not _text(row.get(col)):
                    blockers.append(f"{col}_missing")
            if blockers:
                failed_rows.append({"row_index": idx, "blockers": blockers})
            else:
                complete_rows += 1
    return {
        "provided": True,
        "complete": bool((not missing) and complete_rows == len(df) and len(df) > 0),
        "missing_columns": missing,
        "row_count": int(len(df)),
        "complete_rows": int(complete_rows),
        "failed_rows": failed_rows,
    }


def build_external_docking_baseline_adapter(
    *,
    targets_csv: str,
    ligands_csv: str,
    engine: str,
    out_json: str,
    out_csv: str = "",
    out_md: str = "",
    results_csv: str = "",
) -> dict[str, Any]:
    normalized_engine = _text(engine).lower()
    if normalized_engine not in SUPPORTED_ENGINES:
        raise ValueError(f"unsupported engine: {engine}")
    rows = _work_rows(targets_csv, ligands_csv, normalized_engine)
    result_report = _validate_results(results_csv)
    engine_executable = shutil.which(normalized_engine) or ""
    status = "external_baseline_results_ready" if result_report["complete"] else "external_baseline_work_order_ready"
    payload = {
        "summary": {
            "status": status,
            "engine": normalized_engine,
            "engine_executable_present": bool(engine_executable),
            "engine_executable_path": engine_executable,
            "work_order_row_count": int(len(rows)),
            "results_complete": bool(result_report["complete"]),
            "claim_boundary": "P2 baseline adapter creates comparison work orders or validates operator results; it does not run external engines in product runtime.",
        },
        "result_validation": result_report,
        "work_order_rows": rows,
    }
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(out_json).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if out_csv:
        Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out_csv, index=False)
    if out_md:
        Path(out_md).parent.mkdir(parents=True, exist_ok=True)
        Path(out_md).write_text(f"# P2 External Baseline Adapter\n\n- status: `{status}`\n- engine: `{normalized_engine}`\n- rows: {len(rows)}\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-csv", required=True)
    parser.add_argument("--ligands-csv", required=True)
    parser.add_argument("--engine", default="vina")
    parser.add_argument("--results-csv", default="")
    parser.add_argument("--out-json", default="runs/external_docking_baseline_adapter_current.json")
    parser.add_argument("--out-csv", default="runs/external_docking_baseline_work_order_current.csv")
    parser.add_argument("--out-md", default="runs/external_docking_baseline_adapter_current.md")
    args = parser.parse_args(argv)
    payload = build_external_docking_baseline_adapter(
        targets_csv=args.targets_csv,
        ligands_csv=args.ligands_csv,
        engine=args.engine,
        results_csv=args.results_csv,
        out_json=args.out_json,
        out_csv=args.out_csv,
        out_md=args.out_md,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
