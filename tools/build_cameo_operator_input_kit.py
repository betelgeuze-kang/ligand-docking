#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPAIR_WORK_ORDER_JSON = "runs/cameo_validation_repair_work_order_current.json"
DEFAULT_OUT_DIR = "runs/cameo_operator_input_kit_current"
CLAIM_BOUNDARY = (
    "CAMEO operator input kit only; it creates fill-in templates for local artifact repair. "
    "It does not run predictions, validate models, submit CAMEO targets, send email, use local native accuracy, "
    "or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _blocked_stages(repair_work_order: dict[str, Any]) -> set[str]:
    summary = _summary(repair_work_order)
    stages = summary.get("blocked_stages")
    if isinstance(stages, list):
        return {_text(stage) for stage in stages if _text(stage)}
    return {
        _text(row.get("step"))
        for row in repair_work_order.get("rows", []) or []
        if isinstance(row, dict) and bool(row.get("needed_now", False)) and _text(row.get("step"))
    }


def _template_rows(target_id: str) -> dict[str, list[dict[str, Any]]]:
    target = target_id or "OPERATOR_FILL_CAMEO_TARGET_ID"
    return {
        "candidates_template.csv": [
            {
                "target_id": target,
                "candidate_id": "OPERATOR_FILL_INTERNAL_CANDIDATE_ID",
                "source_kind": "OPERATOR_FILL_internal_prediction_OR_local_pipeline_OR_cameo_dry_run",
                "validation_status": "OPERATOR_FILL_pass_AFTER_LOCAL_QA",
                "model_path": "OPERATOR_FILL_RELATIVE_OR_ABSOLUTE_MODEL_PATH",
                "confidence_mean": "OPERATOR_FILL_0_TO_1_OR_0_TO_100",
                "continuity_fraction": "OPERATOR_FILL_0_TO_1",
                "ca_clash_count": "OPERATOR_FILL_NONNEGATIVE_INTEGER",
                "shape_penalty": "OPERATOR_FILL_0_TO_1",
                "rank_hint": "OPERATOR_FILL_OPTIONAL_POSITIVE_INTEGER",
                "operator_note": "Do not use native/public/template accuracy as selector proof.",
            }
        ],
        "models_template.csv": [
            {
                "target_id": target,
                "candidate_id": "OPERATOR_FILL_SELECTED_CANDIDATE_ID",
                "cameo_model_rank": "OPERATOR_FILL_1_TO_5_MODEL1_IS_1",
                "model_path": "OPERATOR_FILL_RELATIVE_OR_ABSOLUTE_PDB_OR_MMCIF_PATH",
                "selection_status": "OPERATOR_FILL_model1_candidate_OR_top5_candidate",
                "model1_candidate": "OPERATOR_FILL_true_ONLY_FOR_RANK_1",
                "top5_candidate": "OPERATOR_FILL_true_FOR_RANKS_1_TO_5",
                "operator_note": "Model files must be local PDB/mmCIF coordinate files.",
            }
        ],
        "official_results_template.csv": [
            {
                "target_id": target,
                "candidate_id": "OPERATOR_FILL_CAMEO_ASSESSED_CANDIDATE_ID",
                "cameo_model_rank": "OPERATOR_FILL_1_TO_5",
                "result_source_kind": "OPERATOR_FILL_official_cameo_OR_cameo_official_OR_cameo_assessment",
                "result_record_id": "OPERATOR_FILL_OFFICIAL_CAMEO_RESULT_ID_OR_URL",
                "lddt": "OPERATOR_FILL_OFFICIAL_METRIC_OR_BLANK",
                "tm_score": "OPERATOR_FILL_OFFICIAL_METRIC_OR_BLANK",
                "qs_score": "OPERATOR_FILL_OFFICIAL_METRIC_OR_BLANK",
                "rmsd_A": "OPERATOR_FILL_OFFICIAL_METRIC_OR_BLANK",
                "operator_note": "Only official CAMEO assessment metrics are accepted as validation evidence.",
            }
        ],
    }


def _manifest_rows(out_dir: Path, repair_work_order: dict[str, Any], target_id: str) -> list[dict[str, Any]]:
    blocked = _blocked_stages(repair_work_order)
    return [
        {
            "template": "candidates_template.csv",
            "path": str(out_dir / "candidates_template.csv"),
            "blocked_stage": "selection",
            "required_now": "selection" in blocked,
            "repair_command_arg": "--candidates-csv",
            "downstream_tool": "tools/build_cameo_model1_selection_packet.py",
            "purpose": "Internal candidate rows for model1/top5 selection.",
            "accepted_values": "source_kind in internal_prediction,local_pipeline,cameo_dry_run; validation_status=pass",
            "target_id": target_id,
            "action_executed": False,
        },
        {
            "template": "models_template.csv",
            "path": str(out_dir / "models_template.csv"),
            "blocked_stage": "format",
            "required_now": "format" in blocked,
            "repair_command_arg": "--models-csv",
            "downstream_tool": "tools/build_cameo_format_validation_packet.py",
            "purpose": "Selected top5/model1 local PDB/mmCIF model paths for format validation.",
            "accepted_values": "cameo_model_rank 1..5; model_path must point to local PDB/mmCIF",
            "target_id": target_id,
            "action_executed": False,
        },
        {
            "template": "official_results_template.csv",
            "path": str(out_dir / "official_results_template.csv"),
            "blocked_stage": "performance",
            "required_now": "performance" in blocked,
            "repair_command_arg": "--results-csv",
            "downstream_tool": "tools/build_cameo_performance_scorecard.py",
            "purpose": "Official CAMEO result metrics after external assessment is available.",
            "accepted_values": "result_source_kind in official_cameo,cameo_official,cameo_assessment",
            "target_id": target_id,
            "action_executed": False,
        },
    ]


def build_input_kit(
    repair_work_order: dict[str, Any],
    *,
    repair_work_order_json: str = DEFAULT_REPAIR_WORK_ORDER_JSON,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    target_id: str = "",
) -> dict[str, Any]:
    repair_summary = _summary(repair_work_order)
    target = target_id or _text(repair_summary.get("target_id"))
    output_dir = _resolve(out_dir)
    rows = _manifest_rows(output_dir, repair_work_order, target)

    blockers: list[dict[str, str]] = []
    if not repair_work_order:
        blockers.append(
            {
                "code": "repair_work_order_missing",
                "severity": "hard",
                "reason": "CAMEO validation repair work order is required before building operator input templates.",
            }
        )

    status = "cameo_operator_input_kit_ready"
    if blockers:
        status = "blocked_cameo_operator_input_kit"
    elif repair_summary.get("status") == "cameo_validation_repair_not_required":
        status = "cameo_operator_input_kit_not_required"

    required_rows = [row for row in rows if bool(row["required_now"])]
    summary = {
        "packet_type": "cameo_operator_input_kit",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "source_repair_work_order_json": repair_work_order_json,
        "source_repair_status": _text(repair_summary.get("status")),
        "target_id": target,
        "out_dir": str(output_dir),
        "template_count": len(rows),
        "required_template_count": len(required_rows),
        "operator_input_missing_count": int(repair_summary.get("operator_input_missing_count") or 0),
        "operator_input_missing": repair_summary.get("operator_input_missing") if isinstance(repair_summary.get("operator_input_missing"), list) else [],
        "action_executed": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "native_local_accuracy_used": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Fill generated templates, then rebuild the CAMEO repair work order with these template paths."
            if status == "cameo_operator_input_kit_ready"
            else (
                "No operator input kit is required for the current repair state."
                if status == "cameo_operator_input_kit_not_required"
                else "Generate CAMEO validation repair work order first."
            )
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}


def _write_readme(path: Path, payload: dict[str, Any], repair_work_order: dict[str, Any]) -> None:
    s = payload["summary"]
    commands = [
        row.get("command", "")
        for row in repair_work_order.get("rows", []) or []
        if isinstance(row, dict) and _text(row.get("command"))
    ]
    lines = [
        "# CAMEO Operator Input Kit",
        "",
        f"- status: `{s['status']}`",
        f"- source_repair_status: `{s['source_repair_status']}`",
        f"- target_id: `{s['target_id'] or '-'}`",
        f"- action_executed: `{s['action_executed']}`",
        f"- outbound_email_enabled: `{s['outbound_email_enabled']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        f"- native_local_accuracy_used: `{s['native_local_accuracy_used']}`",
        "",
        "## Fill These Files",
        "",
    ]
    for row in payload["rows"]:
        lines.append(
            f"- `{row['template']}`: {row['purpose']} Required now: `{row['required_now']}`. "
            f"Use with `{row['repair_command_arg']}`."
        )
    lines.extend(
        [
            "",
            "## Repair Command Shape",
            "",
            "Replace the `OPERATOR_FILL_*` values before running any command. These commands are recorded from the repair work order and are not executed by this kit.",
            "",
        ]
    )
    if commands:
        lines.extend(f"- `{command}`" for command in commands)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Claim Boundary",
            "",
            s["claim_boundary"],
            "",
            "## Notes",
            "",
            "- Use internal prediction/local pipeline candidates for selector input.",
            "- Use local PDB/mmCIF coordinate files for format validation.",
            "- Use only official CAMEO assessment rows for performance evidence.",
            "- Keep outbound email/submission disabled until an explicit operator approval token is provided.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_input_kit(payload: dict[str, Any], repair_work_order: dict[str, Any]) -> None:
    out_dir = Path(payload["summary"]["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    target_id = _text(payload["summary"].get("target_id"))
    for name, rows in _template_rows(target_id).items():
        write_csv_rows(out_dir / name, rows)
    write_csv_rows(out_dir / "manifest.csv", payload["rows"])
    _write_json(out_dir / "manifest.json", payload)
    _write_readme(out_dir / "README.md", payload, repair_work_order)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build fill-in CAMEO operator input templates for validation repair.")
    parser.add_argument("--repair-work-order-json", default=DEFAULT_REPAIR_WORK_ORDER_JSON)
    parser.add_argument("--target-id", default="")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    repair_work_order = _read_json(args.repair_work_order_json)
    payload = build_input_kit(
        repair_work_order,
        repair_work_order_json=str(args.repair_work_order_json),
        out_dir=args.out_dir,
        target_id=args.target_id,
    )
    write_input_kit(payload, repair_work_order)


if __name__ == "__main__":
    main()
