#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.build_residual_production_checkpoint_preflight import REQUIRED_OUTPUT_FIELDS
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TRAINING_DATA_JSON = "runs/residual_production_training_data_contract_current.json"
DEFAULT_SCORE_MODEL_JSON = "runs/residual_production_score_model_current.json"
DEFAULT_SIDECAR_JSON = "runs/residual_production_checkpoint_sidecar_current.json"
DEFAULT_PREFLIGHT_JSON = "runs/residual_production_checkpoint_preflight_current.json"
DEFAULT_REGISTRY_JSON = "runs/residual_model_registry_current.json"
DEFAULT_WORK_ORDER_JSON = "runs/residual_production_checkpoint_work_order_current.json"
DEFAULT_OUT_JSON = "runs/residual_production_output_head_gap_contract_current.json"
DEFAULT_OUT_CSV = "runs/residual_production_output_head_gap_contract_current.csv"
DEFAULT_OUT_MD = "runs/residual_production_output_head_gap_contract_current.md"

CLAIM_BOUNDARY = (
    "Residual production output-head gap contract only; reconciles required production output heads across training "
    "data, score-model payload, checkpoint sidecar, preflight, registry, and work-order evidence. It does not train "
    "models, run inference, promote production mode, mutate rankings, run docking, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else packet if isinstance(packet, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[str]:
    return [str(item) for item in (value if isinstance(value, list) else [])]


def _bool(value: Any) -> bool:
    return value is True


def _field_row(
    field: str,
    *,
    training: dict[str, Any],
    score: dict[str, Any],
    sidecar: dict[str, Any],
    preflight: dict[str, Any],
    registry: dict[str, Any],
    work_order: dict[str, Any],
) -> dict[str, Any]:
    dataset_labels = set(_list(training.get("dataset_label_fields")))
    training_missing = set(_list(training.get("production_missing_output_fields"))) | set(
        _list(training.get("missing_energy_force_label_fields"))
    )
    score_outputs = set(_list(score.get("learned_output_fields"))) | set(_list(score.get("policy_output_fields")))
    sidecar_payload_outputs = set(_list(sidecar.get("payload_output_fields")))
    sidecar_adapter = sidecar.get("adapter_output_policy") if isinstance(sidecar.get("adapter_output_policy"), dict) else {}
    preflight_required = set(_list(preflight.get("required_output_fields")))
    registry_missing_outputs = set(_list(registry.get("checkpoint_missing_output_fields")))
    registry_missing_adapter = set(_list(registry.get("checkpoint_missing_adapter_output_policy_fields")))
    work_order_blockers = _list(work_order.get("checkpoint_closure_blockers"))

    energy_force_evidence_ready = (
        (field == "delta_energy" and _bool(training.get("delta_energy_label_evidence_ready")))
        or (field == "delta_force" and _bool(training.get("delta_force_label_evidence_ready")))
    )
    uncertainty_policy_evidence_ready = field in {
        "uncertainty",
        "abstention_reason",
        "stage2_route_decision",
    } and _bool(training.get("uncertainty_policy_evidence_ready"))
    training_label_ready = (
        field not in training_missing or energy_force_evidence_ready or uncertainty_policy_evidence_ready
    ) and (
        field in dataset_labels
        or energy_force_evidence_ready
        or (field == "uncertainty" and _bool(training.get("uncertainty_learned_output_ready")))
        or (
            field in {"abstention_reason", "stage2_route_decision"}
            and _bool(training.get("policy_output_fields_ready"))
        )
        or uncertainty_policy_evidence_ready
    )
    score_output_ready = field in score_outputs
    sidecar_payload_ready = field in sidecar_payload_outputs
    adapter_policy_ready = bool(_text(sidecar_adapter.get(field)))
    preflight_requires_field = field in preflight_required
    registry_output_ready = field not in registry_missing_outputs
    upstream_ready = bool(
        training_label_ready
        and score_output_ready
        and sidecar_payload_ready
        and adapter_policy_ready
        and preflight_requires_field
    )
    blockers: list[str] = []
    if not training_label_ready:
        blockers.append("training_label_missing_or_not_ready")
    if not score_output_ready:
        blockers.append("score_model_output_missing")
    if not sidecar_payload_ready:
        blockers.append("sidecar_payload_output_missing")
    if not adapter_policy_ready:
        blockers.append("adapter_policy_missing_or_registry_blocked")
    if not preflight_requires_field:
        blockers.append("preflight_required_field_missing")
    return {
        "output_field": field,
        "status": "ready" if upstream_ready else "blocked",
        "training_label_ready": training_label_ready,
        "score_model_output_ready": score_output_ready,
        "sidecar_payload_output_ready": sidecar_payload_ready,
        "adapter_policy_ready": adapter_policy_ready,
        "preflight_requires_field": preflight_requires_field,
        "registry_output_ready": registry_output_ready,
        "registry_publication_pending": not registry_output_ready,
        "registry_adapter_policy_publication_pending": field in registry_missing_adapter,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "work_order_blockers_for_field": [
            item for item in work_order_blockers if field in item or "sidecar:" in item
        ],
        "next_action": (
            "Ready across production output-head contract."
            if upstream_ready
            else (
                "Return GPU-derived labels and retrain/sidecar the production model with this output head, then "
                "rerun checkpoint preflight and registry."
            )
        ),
        "execution_enabled": False,
        "training_executed": False,
        "model_promoted": False,
        "external_state_mutated": False,
    }


def build_payload(
    *,
    training_data_packet: dict[str, Any],
    score_model_packet: dict[str, Any],
    sidecar_packet: dict[str, Any],
    preflight_packet: dict[str, Any],
    registry_packet: dict[str, Any],
    work_order_packet: dict[str, Any],
) -> dict[str, Any]:
    training = _summary(training_data_packet)
    score = _summary(score_model_packet)
    sidecar = _summary(sidecar_packet)
    preflight = _summary(preflight_packet)
    registry = _summary(registry_packet)
    work_order = _summary(work_order_packet)
    rows = [
        _field_row(
            field,
            training=training,
            score=score,
            sidecar=sidecar,
            preflight=preflight,
            registry=registry,
            work_order=work_order,
        )
        for field in REQUIRED_OUTPUT_FIELDS
    ]
    blocked_rows = [row for row in rows if row["status"] != "ready"]
    registry_pending_rows = [row for row in rows if row["registry_publication_pending"] is True]
    first_blocker = blocked_rows[0] if blocked_rows else {}
    ready = bool(rows and not blocked_rows)
    summary = {
        "packet_type": "residual_production_output_head_gap_contract",
        "status": (
            "residual_production_output_head_gap_contract_ready"
            if ready
            else "blocked_residual_production_output_head_gap_contract"
        ),
        "output_head_gap_contract_ready": True,
        "production_output_heads_complete": ready,
        "required_output_field_count": len(REQUIRED_OUTPUT_FIELDS),
        "ready_output_field_count": len(rows) - len(blocked_rows),
        "blocked_output_field_count": len(blocked_rows),
        "blocked_output_fields": [row["output_field"] for row in blocked_rows],
        "registry_output_published_field_count": len(rows) - len(registry_pending_rows),
        "registry_output_publication_pending_field_count": len(registry_pending_rows),
        "registry_output_publication_pending_fields": [
            row["output_field"] for row in registry_pending_rows
        ],
        "first_blocked_output_field": _text(first_blocker.get("output_field")),
        "first_blocked_output_field_blockers": _list(first_blocker.get("blockers")),
        "training_data_ready": _bool(training.get("production_training_data_ready")),
        "score_model_status": _text(score.get("status")),
        "score_model_production_checkpoint_ready": _bool(score.get("production_checkpoint_ready")),
        "sidecar_ready": _bool(sidecar.get("sidecar_ready")),
        "preflight_ready": _bool(preflight.get("checkpoint_preflight_ready")),
        "registry_production_promotion_allowed": _bool(registry.get("production_promotion_allowed")),
        "next_required_step": (
            "Production output heads are complete; continue checkpoint preflight and guarded registry promotion."
            if ready
            else (
                "Close the first blocked output head by returning GPU-derived label evidence, regenerating the "
                "training-data contract, retraining the score model, rebuilding the checkpoint sidecar, and rerunning "
                "preflight/registry gates."
            )
        ),
        "execution_enabled": False,
        "training_executed": False,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Residual Production Output-Head Gap Contract",
        "",
        f"- status: `{s['status']}`",
        f"- production_output_heads_complete: `{s['production_output_heads_complete']}`",
        f"- ready_output_field_count: `{s['ready_output_field_count']}` / `{s['required_output_field_count']}`",
        f"- blocked_output_fields: `{','.join(s['blocked_output_fields'])}`",
        f"- first_blocked_output_field: `{s['first_blocked_output_field']}`",
        "",
        "## Output Fields",
        "",
        "| field | status | training label | score output | sidecar payload | adapter policy | registry output | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['output_field']}` | `{row['status']}` | `{row['training_label_ready']}` | "
            f"`{row['score_model_output_ready']}` | `{row['sidecar_payload_output_ready']}` | "
            f"`{row['adapter_policy_ready']}` | `{row['registry_output_ready']}` | "
            f"`{','.join(row['blockers'])}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build residual production output-head gap contract.")
    parser.add_argument("--training-data-json", default=DEFAULT_TRAINING_DATA_JSON)
    parser.add_argument("--score-model-json", default=DEFAULT_SCORE_MODEL_JSON)
    parser.add_argument("--sidecar-json", default=DEFAULT_SIDECAR_JSON)
    parser.add_argument("--preflight-json", default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--registry-json", default=DEFAULT_REGISTRY_JSON)
    parser.add_argument("--work-order-json", default=DEFAULT_WORK_ORDER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(
        training_data_packet=_read_json(args.training_data_json),
        score_model_packet=_read_json(args.score_model_json),
        sidecar_packet=_read_json(args.sidecar_json),
        preflight_packet=_read_json(args.preflight_json),
        registry_packet=_read_json(args.registry_json),
        work_order_packet=_read_json(args.work_order_json),
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
