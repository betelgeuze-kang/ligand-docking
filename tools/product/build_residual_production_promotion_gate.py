#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_json_utils import read_json, read_summary
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSIST_GATE_JSON = "runs/residual_assist_promotion_gate_current.json"
DEFAULT_SIDECAR_JSON = "runs/residual_production_checkpoint_sidecar_current.json"
DEFAULT_PREFLIGHT_JSON = "runs/residual_production_checkpoint_preflight_current.json"
DEFAULT_TRAINING_CONTRACT_JSON = "runs/residual_production_training_data_contract_current.json"
DEFAULT_SCORE_MODEL_JSON = "runs/residual_production_score_model_current.json"
DEFAULT_FORCE_RECEIPT_JSON = "runs/residual_force_gpu_worker_return_receipt_current.json"
DEFAULT_OUT_JSON = "runs/residual_production_promotion_gate_current.json"
DEFAULT_OUT_CSV = "runs/residual_production_promotion_gate_current.csv"
DEFAULT_OUT_MD = "runs/residual_production_promotion_gate_current.md"

CLAIM_BOUNDARY = (
    "Residual production promotion gate only; audits assist, checkpoint sidecar, preflight, training contract, "
    "score-model output-head, and GPU force-return receipt evidence before guarded production mode. It does not "
    "train models, alter rankings, promote production mode in runtime, run docking, upload, submit, email, archive, "
    "externalize, or delete files."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    return read_json(path_like, root=ROOT)


def _row(check_id: str, status: str, observed: str, required: str, reason: str, source_artifact: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "observed": observed,
        "required": required,
        "reason": reason,
        "source_artifact": source_artifact,
        "release_blocker": status != "pass",
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
    }


def build_residual_production_promotion_gate(
    *,
    assist_gate_packet: dict[str, Any],
    sidecar_packet: dict[str, Any],
    preflight_packet: dict[str, Any],
    training_contract_packet: dict[str, Any],
    score_model_packet: dict[str, Any],
    force_receipt_packet: dict[str, Any],
    assist_gate_path: str = DEFAULT_ASSIST_GATE_JSON,
    sidecar_path: str = DEFAULT_SIDECAR_JSON,
    preflight_path: str = DEFAULT_PREFLIGHT_JSON,
    training_contract_path: str = DEFAULT_TRAINING_CONTRACT_JSON,
    score_model_path: str = DEFAULT_SCORE_MODEL_JSON,
    force_receipt_path: str = DEFAULT_FORCE_RECEIPT_JSON,
) -> dict[str, Any]:
    assist = read_summary(assist_gate_packet)
    sidecar = read_summary(sidecar_packet)
    preflight = read_summary(preflight_packet)
    training = read_summary(training_contract_packet)
    score = read_summary(score_model_packet)
    receipt = read_summary(force_receipt_packet)

    assist_ready = assist.get("assist_promotion_allowed") is True
    sidecar_ready = sidecar.get("sidecar_ready") is True
    preflight_ready = preflight.get("checkpoint_preflight_ready") is True and int(preflight.get("ready_checkpoint_count") or 0) > 0
    training_ready = training.get("production_training_data_ready") is True
    score_ready = score.get("production_checkpoint_ready") is True and not (score.get("missing_production_output_fields") or [])
    receipt_ready = receipt.get("gpu_worker_return_receipt_ready") is True

    rows = [
        _row(
            "assist_promotion_prerequisite",
            "pass" if assist_ready else "fail",
            f"assist_promotion_allowed={assist.get('assist_promotion_allowed')}",
            "assist promotion gate green before production promotion",
            "Production mode must not bypass assist evidence.",
            assist_gate_path,
        ),
        _row(
            "production_checkpoint_sidecar_ready",
            "pass" if sidecar_ready else "fail",
            f"sidecar_ready={sidecar.get('sidecar_ready')}; sidecar_written={sidecar.get('sidecar_written')}",
            "checkpoint sidecar metadata ready with receipt binding",
            "Production promotion requires a fail-closed sidecar with bound force receipt.",
            sidecar_path,
        ),
        _row(
            "production_checkpoint_preflight_ready",
            "pass" if preflight_ready else "fail",
            f"checkpoint_preflight_ready={preflight.get('checkpoint_preflight_ready')}; ready_checkpoint_count={preflight.get('ready_checkpoint_count')}",
            "checkpoint preflight ready with at least one guarded checkpoint",
            "Preflight validates sidecar metadata, adapter policy, and benchmark gate artifacts.",
            preflight_path,
        ),
        _row(
            "production_training_data_contract_ready",
            "pass" if training_ready else "fail",
            f"production_training_data_ready={training.get('production_training_data_ready')}; primary_blocker={training.get('primary_blocker')}",
            "training-data contract ready with energy/force and uncertainty evidence",
            "Production promotion requires a closed training-data contract.",
            training_contract_path,
        ),
        _row(
            "score_model_production_output_heads_ready",
            "pass" if score_ready else "fail",
            f"production_checkpoint_ready={score.get('production_checkpoint_ready')}; missing_output_fields={','.join(str(item) for item in score.get('missing_production_output_fields') or [])}",
            "score checkpoint exposes all required production output heads",
            "Missing delta_energy/delta_force heads must remain fail-closed.",
            score_model_path,
        ),
        _row(
            "force_gpu_worker_return_receipt_ready",
            "pass" if receipt_ready else "fail",
            f"gpu_worker_return_receipt_ready={receipt.get('gpu_worker_return_receipt_ready')}; manifest_ok_row_count={receipt.get('manifest_ok_row_count')}",
            "GPU worker return receipt ready with operator-verified NPZ coverage",
            "Force head promotion requires bound GPU return receipt evidence.",
            force_receipt_path,
        ),
    ]
    fail_rows = [row for row in rows if row["status"] != "pass"]
    production_allowed = not fail_rows
    summary = {
        "packet_type": "residual_production_promotion_gate",
        "status": "residual_production_promotion_gate_ready" if production_allowed else "blocked_residual_production_promotion_gate",
        "assist_promotion_allowed": assist_ready,
        "production_promotion_allowed": production_allowed,
        "residual_mode_from": "assist",
        "residual_mode_to": "production_guarded",
        "check_count": len(rows),
        "pass_check_count": len(rows) - len(fail_rows),
        "fail_check_count": len(fail_rows),
        "failed_check_ids": [row["check_id"] for row in fail_rows],
        "primary_blocker": fail_rows[0]["check_id"] if fail_rows else "none",
        "execution_enabled": False,
        "benchmark_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Production promotion is evidence-ready; wire guarded production mode behind explicit policy change."
            if production_allowed
            else f"Repair `{fail_rows[0]['check_id']}` before production promotion."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Production Promotion Gate",
        "",
        f"- status: `{s['status']}`",
        f"- production_promotion_allowed: `{s['production_promotion_allowed']}`",
        f"- residual_mode_from: `{s['residual_mode_from']}`",
        f"- residual_mode_to: `{s['residual_mode_to']}`",
        f"- pass_check_count: `{s['pass_check_count']}` / `{s['check_count']}`",
        f"- primary_blocker: `{s['primary_blocker']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | {row['observed']} | {row['required']} | {row['reason']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit production promotion evidence for guarded residual mode.")
    parser.add_argument("--assist-gate-json", default=DEFAULT_ASSIST_GATE_JSON)
    parser.add_argument("--sidecar-json", default=DEFAULT_SIDECAR_JSON)
    parser.add_argument("--preflight-json", default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--training-contract-json", default=DEFAULT_TRAINING_CONTRACT_JSON)
    parser.add_argument("--score-model-json", default=DEFAULT_SCORE_MODEL_JSON)
    parser.add_argument("--force-receipt-json", default=DEFAULT_FORCE_RECEIPT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int | None:
    args = parse_args(argv)
    payload = build_residual_production_promotion_gate(
        assist_gate_packet=_read_json_if_present(args.assist_gate_json),
        sidecar_packet=_read_json_if_present(args.sidecar_json),
        preflight_packet=_read_json_if_present(args.preflight_json),
        training_contract_packet=_read_json_if_present(args.training_contract_json),
        score_model_packet=_read_json_if_present(args.score_model_json),
        force_receipt_packet=_read_json_if_present(args.force_receipt_json),
        assist_gate_path=args.assist_gate_json,
        sidecar_path=args.sidecar_json,
        preflight_path=args.preflight_json,
        training_contract_path=args.training_contract_json,
        score_model_path=args.score_model_json,
        force_receipt_path=args.force_receipt_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main() or 0)
