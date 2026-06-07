#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{str(k): _text(v) for k, v in row.items()} for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _read_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def build_scores(args: argparse.Namespace) -> dict[str, Any]:
    source = _resolve(args.htvs_scores_csv)
    out_scores = _resolve(args.out_scores_csv)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    rows = _read_csv(source)
    score_col = _text(args.score_col)
    grouped: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        target = _text(row.get("target"))
        ligand = _text(row.get("ligand_id"))
        raw_score = _text(row.get(score_col))
        if not target or not ligand or raw_score == "":
            continue
        grouped.setdefault((target, ligand), []).append(_float(raw_score))

    out_rows = []
    for (target, ligand), values in sorted(grouped.items()):
        if not values:
            continue
        out_rows.append(
            {
                "target": target,
                "ligand_id": ligand,
                "binding_score": sum(values) / len(values),
                "replicate_count": len(values),
                "source_score_col": score_col,
            }
        )
    out_rows.sort(key=lambda row: _float(row["binding_score"]))
    _write_csv(out_scores, out_rows, ["target", "ligand_id", "binding_score", "replicate_count", "source_score_col"])

    execution_summary = _read_summary(_resolve(args.execution_summary_json)) if _text(args.execution_summary_json) else {}
    summary = {
        "packet_type": "lit_pcba_product_scores_from_htvs",
        "status": "lit_pcba_product_scores_ready" if out_rows else "blocked_lit_pcba_product_scores",
        "source_engine": "betelgeuze_ligand_htvs",
        "htvs_scores_csv": str(source),
        "execution_summary_json": str(_resolve(args.execution_summary_json)) if _text(args.execution_summary_json) else "",
        "execution_summary_pass": execution_summary.get("pass") is True if execution_summary else False,
        "score_col": score_col,
        "input_rows": len(rows),
        "output_rows": len(out_rows),
        "out_scores_csv": str(out_scores),
        "external_state_mutated": False,
        "docking_results_emitted": False,
        "next_required_step": "Build product benchmark provenance and run the LIT-PCBA scorecard.",
    }
    payload = {"summary": summary, "rows": out_rows[:20]}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        "\n".join(
            [
                "# LIT-PCBA Product Scores From HTVS",
                "",
                f"- status: `{summary['status']}`",
                f"- input_rows: `{summary['input_rows']}`",
                f"- output_rows: `{summary['output_rows']}`",
                f"- score_col: `{score_col}`",
                f"- out_scores_csv: `{out_scores}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export product HTVS scores into LIT-PCBA scorecard CSV format.")
    parser.add_argument("--htvs-scores-csv", default="runs/lit_pcba_adrb2_product_stage3_scores.csv")
    parser.add_argument("--execution-summary-json", default="runs/lit_pcba_adrb2_product_summary.json")
    parser.add_argument("--score-col", default="binding_score_composite_v7")
    parser.add_argument("--out-scores-csv", default="runs/lit_pcba_scores_current.csv")
    parser.add_argument("--out-json", default="runs/lit_pcba_product_scores_from_htvs_current.json")
    parser.add_argument("--out-md", default="runs/lit_pcba_product_scores_from_htvs_current.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    build_scores(parse_args(argv))


if __name__ == "__main__":
    main()
