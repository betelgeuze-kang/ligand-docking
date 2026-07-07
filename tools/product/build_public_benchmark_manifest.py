from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

SUPPORTED_DATASETS = {"pdbbind_casf", "astex", "dude", "custom"}
REQUIRED_COLUMNS = ("target", "ligand_id", "receptor_path", "ligand_path", "split")
OPTIONAL_METRIC_COLUMNS = ("pose_rmsd_A", "lddt_pli", "bisyrmsd", "baseline_score", "experimental_value")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _file_present(value: Any) -> bool:
    text = _text(value)
    return bool(text and Path(text).exists())


def _normalize_dataset(value: str) -> str:
    dataset = _text(value).lower().replace("-", "_")
    aliases = {"pdbbind": "pdbbind_casf", "casf": "pdbbind_casf", "dud_e": "dude"}
    dataset = aliases.get(dataset, dataset)
    if dataset not in SUPPORTED_DATASETS:
        raise ValueError(f"unsupported dataset: {value}")
    return dataset


def build_public_benchmark_manifest(
    input_csv: str,
    *,
    dataset: str,
    out_json: str,
    out_csv: str = "",
    out_md: str = "",
    license_receipt: str = "",
    require_local_files: bool = False,
) -> dict[str, Any]:
    normalized_dataset = _normalize_dataset(dataset)
    df = pd.read_csv(input_csv)
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    license_ready = bool(_text(license_receipt))
    for idx, row in enumerate(df.to_dict(orient="records"), start=1):
        row_blockers: list[str] = []
        if missing_cols:
            row_blockers.extend([f"missing_column:{col}" for col in missing_cols])
        else:
            for col in REQUIRED_COLUMNS:
                if not _text(row.get(col)):
                    row_blockers.append(f"{col}_missing")
            if require_local_files:
                if not _file_present(row.get("receptor_path")):
                    row_blockers.append("receptor_path_not_present")
                if not _file_present(row.get("ligand_path")):
                    row_blockers.append("ligand_path_not_present")
        out_row = {
            "row_id": _text(row.get("row_id")) or f"{normalized_dataset}_{idx:05d}",
            "dataset": normalized_dataset,
            "target": _text(row.get("target")),
            "ligand_id": _text(row.get("ligand_id")),
            "receptor_path": _text(row.get("receptor_path")),
            "ligand_path": _text(row.get("ligand_path")),
            "split": _text(row.get("split")),
            "available_metric_columns": [col for col in OPTIONAL_METRIC_COLUMNS if col in df.columns and _text(row.get(col))],
            "blockers": row_blockers,
        }
        rows.append(out_row)
        if row_blockers:
            blockers.append({"row_id": out_row["row_id"], "blockers": row_blockers})
    status = "public_benchmark_manifest_ready"
    if missing_cols or blockers:
        status = "public_benchmark_manifest_incomplete"
    if not license_ready and normalized_dataset != "custom":
        status = "public_benchmark_manifest_license_receipt_required"
    payload = {
        "summary": {
            "status": status,
            "dataset": normalized_dataset,
            "input_csv": str(input_csv),
            "row_count": int(len(rows)),
            "blocked_row_count": int(len(blockers)),
            "missing_required_columns": missing_cols,
            "license_receipt": _text(license_receipt),
            "license_receipt_present": license_ready,
            "require_local_files": bool(require_local_files),
            "claim_boundary": "P2 public benchmark manifest only; dataset files stay local and claims require row-level evidence.",
        },
        "rows": rows,
        "blocked_rows": blockers,
    }
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(out_json).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if out_csv:
        Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out_csv, index=False)
    if out_md:
        Path(out_md).parent.mkdir(parents=True, exist_ok=True)
        Path(out_md).write_text(f"# P2 Public Benchmark Manifest\n\n- status: `{status}`\n- dataset: `{normalized_dataset}`\n- rows: {len(rows)}\n", encoding="utf-8")
    return payload


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--dataset", default="pdbbind_casf")
    parser.add_argument("--license-receipt", default="")
    parser.add_argument("--require-local-files", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--out-json", default="runs/public_benchmark_manifest_current.json")
    parser.add_argument("--out-csv", default="runs/public_benchmark_manifest_current.csv")
    parser.add_argument("--out-md", default="runs/public_benchmark_manifest_current.md")
    args = parser.parse_args(argv)
    payload = build_public_benchmark_manifest(
        args.input_csv,
        dataset=args.dataset,
        license_receipt=args.license_receipt,
        require_local_files=args.require_local_files,
        out_json=args.out_json,
        out_csv=args.out_csv,
        out_md=args.out_md,
    )
    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
