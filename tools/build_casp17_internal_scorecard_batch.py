#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INTAKE_CSV = "runs/casp17_target_intake_validated_current.csv"
DEFAULT_OUT_DIR = "runs/casp17_internal_scorecards_current"
DEFAULT_OUT_JSON = "runs/casp17_internal_scorecard_batch_current.json"
DEFAULT_OUT_CSV = "runs/casp17_internal_scorecard_batch_current.csv"
DEFAULT_OUT_MD = "runs/casp17_internal_scorecard_batch_current.md"
DEFAULT_OUT_INTAKE_CSV = "runs/casp17_target_intake_scored_current.csv"

DEFAULT_LOCAL_DELIVERY_VERDICT_JSON = "runs/local_delivery_verdict_gate_current.json"
DEFAULT_LOCAL_ENGINE_QUEUE_JSON = "runs/local_engine_commercialization_queue_current.json"
DEFAULT_ACCURACY_SCORECARD_JSON = "runs/accuracy_parity_scorecard_current.json"

PASS_VALUES = {"pass", "passed", "green", "ready", "ok", "true", "1", "complete"}
ALLOWED_LANES = {"organic_ligand_protein_complexes", "difficult_protein_complexes", "accuracy_estimation"}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _status(value: Any) -> str:
    text = _text(value).lower()
    if text in PASS_VALUES:
        return "pass"
    if not text:
        return "missing"
    return text


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _text(value).lower()
    if text in PASS_VALUES:
        return True
    if text in {"false", "0", "no", "n", "fail", "failed", "blocked", "red"}:
        return False
    return None


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _hard_blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _artifact_blockers(path_like: str, *, label: str, required_when_pass: bool = False) -> list[dict[str, str]]:
    if not _text(path_like):
        if required_when_pass:
            return [_hard_blocker(f"{label}_artifact_missing", f"`{label}` artifact path is missing.")]
        return []
    payload = _read_json(path_like)
    if not payload:
        return [_hard_blocker(f"{label}_artifact_invalid", f"`{label}` artifact is missing or invalid JSON.")]
    blockers = payload.get("blockers")
    if not isinstance(blockers, list):
        blockers = _summary(payload).get("blockers")
    if not isinstance(blockers, list):
        blockers = []
    out: list[dict[str, str]] = []
    for blocker in blockers:
        if isinstance(blocker, dict):
            severity = _text(blocker.get("severity")).lower()
            if severity in {"", "hard", "blocker"}:
                code = _text(blocker.get("code") or blocker.get("id") or blocker.get("reason")) or f"{label}_hard_blocker"
                out.append(_hard_blocker(f"{label}:{code}", _text(blocker.get("reason")) or code))
        elif _text(blocker):
            out.append(_hard_blocker(f"{label}:{_text(blocker)}", _text(blocker)))
    return out


def _framework(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, str]]]:
    verdict = _summary(_read_json(args.local_delivery_verdict_json))
    queue = _summary(_read_json(args.local_engine_queue_json))
    accuracy = _summary(_read_json(args.accuracy_scorecard_json))
    blockers: list[dict[str, str]] = []
    if _boolish(verdict.get("delivery_ready")) is not True:
        blockers.append(_hard_blocker("local_delivery_verdict_not_ready", "Local delivery verdict is not ready."))
    if _boolish(queue.get("queue_clear")) is not True and _int(queue.get("blocked_count")) > 0:
        blockers.append(_hard_blocker("local_engine_queue_not_clear", "Local engine commercialization queue is not clear."))
    if _text(accuracy.get("status")).lower() not in {"green", "pass", "ready"}:
        blockers.append(_hard_blocker("accuracy_parity_scorecard_not_green", "Accuracy parity scorecard is not green."))
    return (
        {
            "framework_gate_pass": not blockers,
            "local_delivery_ready": verdict.get("delivery_ready"),
            "local_engine_queue_clear": queue.get("queue_clear"),
            "accuracy_parity_status": accuracy.get("status"),
        },
        blockers,
    )


def _target_scorecard(row: dict[str, str], framework_blockers: list[dict[str, str]]) -> tuple[dict[str, Any], dict[str, str]]:
    target_id = _text(row.get("target_id"))
    lane = _text(row.get("lane"))
    prediction_path = _text(row.get("prediction_file_path"))
    sequence_path = _text(row.get("sequence_path"))
    blockers = list(framework_blockers)

    if not target_id:
        blockers.append(_hard_blocker("missing_target_id", "Target id is missing."))
    if lane not in ALLOWED_LANES:
        blockers.append(_hard_blocker("unsupported_lane", "CASP17 lane is unsupported."))
    if _text(row.get("deadline_class")).lower() != "regular":
        blockers.append(_hard_blocker("deadline_class_not_regular", "Only regular-group target rows can pass the scorecard."))
    if not prediction_path:
        blockers.append(_hard_blocker("missing_prediction_file_path", "Prediction file path is missing."))
    elif not _resolve(prediction_path).exists():
        blockers.append(_hard_blocker("prediction_file_missing", "Prediction file does not exist."))
    if not sequence_path:
        blockers.append(_hard_blocker("missing_sequence_path", "Sequence path is missing."))
    elif not _resolve(sequence_path).exists():
        blockers.append(_hard_blocker("sequence_file_missing", "Sequence file does not exist."))

    for key in ("format_check_status", "geometry_sanity_status", "confidence_calibration_status"):
        if _status(row.get(key)) != "pass":
            blockers.append(_hard_blocker(f"{key}_not_pass", f"`{key}` is not pass."))

    blockers.extend(
        _artifact_blockers(
            _text(row.get("validation_json_path")),
            label="format_validation",
            required_when_pass=_status(row.get("format_check_status")) == "pass",
        )
    )
    blockers.extend(
        _artifact_blockers(
            _text(row.get("geometry_validation_json_path")),
            label="geometry_validation",
            required_when_pass=_status(row.get("geometry_sanity_status")) == "pass",
        )
    )
    blockers.extend(
        _artifact_blockers(
            _text(row.get("confidence_validation_json_path")),
            label="confidence_validation",
            required_when_pass=_status(row.get("confidence_calibration_status")) == "pass",
        )
    )

    if lane == "organic_ligand_protein_complexes":
        for key in ("parameterization_status", "protein_local_minimization_status"):
            if _status(row.get(key)) != "pass":
                blockers.append(_hard_blocker(f"{key}_not_pass", f"`{key}` is not pass for ligand lane."))
        ligand_path = _text(row.get("ligand_info_path"))
        if not ligand_path:
            blockers.append(_hard_blocker("missing_ligand_info_path", "Ligand lane requires ligand info path."))
        elif not _resolve(ligand_path).exists():
            blockers.append(_hard_blocker("ligand_info_file_missing", "Ligand info file does not exist."))

    model_generation_status = "pass"
    if not prediction_path:
        model_generation_status = "missing"
    elif not _resolve(prediction_path).exists() or _status(row.get("format_check_status")) != "pass":
        model_generation_status = "fail"
    if model_generation_status != "pass":
        blockers.append(_hard_blocker("model_generation_status_not_pass", "Generated model is missing or not format-valid."))

    unique_blockers: list[dict[str, str]] = []
    seen: set[str] = set()
    for blocker in blockers:
        code = blocker["code"]
        if code in seen:
            continue
        seen.add(code)
        unique_blockers.append(blocker)

    internal_scorecard_status = "pass" if not unique_blockers else "missing" if not prediction_path else "fail"
    enriched = dict(row)
    enriched["model_generation_status"] = model_generation_status
    enriched["internal_scorecard_status"] = internal_scorecard_status
    payload = {
        "summary": {
            "packet_type": "casp17_target_internal_scorecard",
            "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "target_id": target_id,
            "lane": lane,
            "model_generation_status": model_generation_status,
            "internal_scorecard_status": internal_scorecard_status,
            "blocker_count": len(unique_blockers),
            "claim_boundary": "Internal CASP17 target scorecard only; not accepted submission or performance evidence.",
        },
        "blockers": unique_blockers,
    }
    return payload, enriched


def build_payload(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, str]]]:
    rows = [row for row in _read_csv(args.intake_csv) if any(_text(value) for value in row.values())]
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    framework, framework_blockers = _framework(args)
    batch_rows: list[dict[str, Any]] = []
    enriched_rows: list[dict[str, str]] = []
    for row in rows:
        target_id = _text(row.get("target_id"))
        target_payload, enriched = _target_scorecard(row, framework_blockers)
        target_json = out_dir / f"{target_id}_internal_scorecard.json"
        _write_json(target_json, target_payload)
        enriched["internal_scorecard_json_path"] = _artifact(target_json)
        enriched_rows.append(enriched)
        summary = target_payload["summary"]
        batch_rows.append(
            {
                "target_id": target_id,
                "lane": _text(row.get("lane")),
                "model_generation_status": summary["model_generation_status"],
                "internal_scorecard_status": summary["internal_scorecard_status"],
                "blocker_count": summary["blocker_count"],
                "internal_scorecard_json_path": enriched["internal_scorecard_json_path"],
                "top_blockers": ";".join(blocker["code"] for blocker in target_payload["blockers"][:8]),
            }
        )

    pass_count = sum(1 for row in batch_rows if row["internal_scorecard_status"] == "pass")
    missing_count = sum(1 for row in batch_rows if row["internal_scorecard_status"] == "missing")
    fail_count = sum(1 for row in batch_rows if row["internal_scorecard_status"] == "fail")
    summary = {
        "packet_type": "casp17_internal_scorecard_batch",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "intake_csv": _artifact(args.intake_csv),
        "out_dir": _artifact(out_dir),
        "out_intake_csv": _artifact(args.out_intake_csv),
        "target_row_count": len(batch_rows),
        "internal_scorecard_pass_count": pass_count,
        "internal_scorecard_missing_count": missing_count,
        "internal_scorecard_fail_count": fail_count,
        "framework": framework,
        "claim_boundary": "Internal CASP17 target scorecard batch only; not accepted submission or performance evidence.",
    }
    return {"summary": summary, "rows": batch_rows}, enriched_rows


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Internal Scorecard Batch",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- intake CSV: `{summary['intake_csv']}`",
        f"- target rows: `{summary['target_row_count']}`",
        f"- internal scorecard pass/missing/fail: `{summary['internal_scorecard_pass_count']}/{summary['internal_scorecard_missing_count']}/{summary['internal_scorecard_fail_count']}`",
        f"- enriched intake: `{summary['out_intake_csv']}`",
        "",
        "## Rows",
        "",
        "| target | model | scorecard | blockers | scorecard path | top blockers |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['model_generation_status']}` | `{row['internal_scorecard_status']}` | "
            f"{row['blocker_count']} | `{row['internal_scorecard_json_path']}` | {row['top_blockers'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `no_rows` | 0 | - | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CASP17 target-level internal scorecards and an enriched intake CSV.")
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-intake-csv", default=DEFAULT_OUT_INTAKE_CSV)
    parser.add_argument("--local-delivery-verdict-json", default=DEFAULT_LOCAL_DELIVERY_VERDICT_JSON)
    parser.add_argument("--local-engine-queue-json", default=DEFAULT_LOCAL_ENGINE_QUEUE_JSON)
    parser.add_argument("--accuracy-scorecard-json", default=DEFAULT_ACCURACY_SCORECARD_JSON)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload, enriched_rows = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    fieldnames = list(enriched_rows[0].keys()) if enriched_rows else []
    _write_csv(args.out_intake_csv, enriched_rows, fieldnames=fieldnames)
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
