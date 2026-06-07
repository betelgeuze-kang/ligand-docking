#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = "runs/cameo_local_format_smoke_inputs_current"
DEFAULT_TARGET_ID = "CAMEO_DRY_RUN_FORMAT_SMOKE"
DEFAULT_CANDIDATE_ID = "cameo_local_format_smoke_model1"
CLAIM_BOUNDARY = (
    "CAMEO local format smoke inputs only; this synthetic model is not a prediction, not a native structure, "
    "not an official CAMEO result, and is not suitable for accuracy or performance claims."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _relative_or_absolute(path: Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(path, base_dir)
    except ValueError:
        return str(path)


def _pdb_atom(serial: int, atom: str, residue: str, chain: str, resseq: int, x: float, y: float, z: float) -> str:
    return (
        f"ATOM  {serial:5d} {atom:<4}{residue:>3} {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{20.0:6.2f}           C  "
    )


def _synthetic_pdb_text() -> str:
    return "\n".join(
        [
            "MODEL        1",
            _pdb_atom(1, "N", "GLY", "A", 1, 0.000, 0.000, 0.000),
            _pdb_atom(2, "CA", "GLY", "A", 1, 1.458, 0.000, 0.000),
            _pdb_atom(3, "C", "GLY", "A", 1, 2.028, 1.410, 0.000),
            _pdb_atom(4, "O", "GLY", "A", 1, 1.397, 2.460, 0.000),
            _pdb_atom(5, "N", "ALA", "A", 2, 3.377, 1.520, 0.000),
            _pdb_atom(6, "CA", "ALA", "A", 2, 4.040, 2.810, 0.000),
            "END",
            "",
        ]
    )


def build_smoke_inputs(
    *,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    base_dir: str | Path = ROOT,
    target_id: str = DEFAULT_TARGET_ID,
    candidate_id: str = DEFAULT_CANDIDATE_ID,
) -> dict[str, Any]:
    output_dir = _resolve(out_dir)
    base = _resolve(base_dir)
    model_path = output_dir / "model1.pdb"
    model_path_text = _relative_or_absolute(model_path, base)
    candidates_csv = output_dir / "candidates.csv"
    models_csv = output_dir / "models.csv"
    manifest_json = output_dir / "manifest.json"
    manifest_md = output_dir / "manifest.md"

    candidate_rows = [
        {
            "target_id": target_id,
            "candidate_id": candidate_id,
            "source_kind": "cameo_dry_run",
            "validation_status": "pass",
            "model_path": model_path_text,
            "confidence_mean": "0.50",
            "continuity_fraction": "1.0",
            "ca_clash_count": "0",
            "shape_penalty": "0.0",
            "rank_hint": "1",
        }
    ]
    model_rows = [
        {
            "target_id": target_id,
            "candidate_id": candidate_id,
            "cameo_model_rank": "1",
            "model_path": model_path_text,
        }
    ]
    summary = {
        "packet_type": "cameo_local_format_smoke_inputs",
        "status": "cameo_local_format_smoke_inputs_ready",
        "target_id": target_id,
        "candidate_id": candidate_id,
        "source_kind": "cameo_dry_run",
        "model_path": model_path_text,
        "model_file": str(model_path),
        "candidates_csv": str(candidates_csv),
        "models_csv": str(models_csv),
        "official_results_csv": "",
        "candidate_row_count": len(candidate_rows),
        "model_row_count": len(model_rows),
        "official_result_row_count": 0,
        "action_executed": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "native_local_accuracy_used": False,
        "official_cameo_results_used": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run operator input validation, model1 selection, format validation, dry-run handoff, "
            "and readiness refresh against these local smoke inputs."
        ),
    }
    return {
        "summary": summary,
        "candidate_rows": candidate_rows,
        "model_rows": model_rows,
        "paths": {
            "out_dir": str(output_dir),
            "model_file": str(model_path),
            "candidates_csv": str(candidates_csv),
            "models_csv": str(models_csv),
            "manifest_json": str(manifest_json),
            "manifest_md": str(manifest_md),
        },
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# CAMEO Local Format Smoke Inputs",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- candidate_id: `{s['candidate_id']}`",
        f"- source_kind: `{s['source_kind']}`",
        f"- model_path: `{s['model_path']}`",
        f"- candidates_csv: `{s['candidates_csv']}`",
        f"- models_csv: `{s['models_csv']}`",
        f"- official_results_csv: `{s['official_results_csv']}`",
        f"- native_local_accuracy_used: `{s['native_local_accuracy_used']}`",
        f"- official_cameo_results_used: `{s['official_cameo_results_used']}`",
        "",
        "## Claim Boundary",
        "",
        s["claim_boundary"],
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_smoke_inputs(payload: dict[str, Any]) -> None:
    paths = payload["paths"]
    model_path = Path(paths["model_file"])
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text(_synthetic_pdb_text(), encoding="utf-8")
    write_csv_rows(Path(paths["candidates_csv"]), payload["candidate_rows"])
    write_csv_rows(Path(paths["models_csv"]), payload["model_rows"])
    _write_json(paths["manifest_json"], payload)
    _write_markdown(paths["manifest_md"], payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build synthetic CAMEO local format smoke inputs.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--base-dir", default=str(ROOT))
    parser.add_argument("--target-id", default=DEFAULT_TARGET_ID)
    parser.add_argument("--candidate-id", default=DEFAULT_CANDIDATE_ID)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_smoke_inputs(
        out_dir=args.out_dir,
        base_dir=args.base_dir,
        target_id=args.target_id,
        candidate_id=args.candidate_id,
    )
    write_smoke_inputs(payload)


if __name__ == "__main__":
    main()
