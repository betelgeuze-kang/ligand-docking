#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CANDIDATES_CSV = "config/gpcr_non_adrb2_positive_candidates_v1.csv"
DEFAULT_LEAKAGE_AUDIT_JSON = "runs/gpcr_non_adrb2_positive_candidates_leakage_audit_current.json"
DEFAULT_POSITIVE_COVERAGE_JSON = "runs/gpcr_positive_coverage_expansion_packet_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_positive_coverage_freeze_packet_current.json"
DEFAULT_OUT_MD = "runs/gpcr_positive_coverage_freeze_packet_current.md"

MINIMUM_POSITIVE_COUNT = 9
MINIMUM_NEW_NON_ADRB2_POSITIVES = 3
MINIMUM_DISTINCT_POSITIVE_GPCR_TARGETS = 2


def _resolve(path_like: str | Path | None) -> Path | None:
    if path_like is None or str(path_like).strip() == "":
        return None
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "t", "yes", "y", "pass", "passed", "green", "ready", "curated"}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _is_gpcr_target(row: dict[str, Any]) -> bool:
    family = _text(row.get("target_family")).lower()
    target = _text(row.get("target")).upper()
    return family == "gpcr" or "GPCR" in target


def _is_non_adrb2(row: dict[str, Any]) -> bool:
    return "ADRB2" not in _text(row.get("target")).upper()


def _is_curated(row: dict[str, Any]) -> bool:
    status = _text(row.get("curation_status")).lower()
    return status in {"curated", "ready", "accepted", "reviewed", "freeze_ready"}


def _base_positive_count(coverage_payload: dict[str, Any]) -> int:
    summary = coverage_payload.get("summary") if isinstance(coverage_payload.get("summary"), dict) else {}
    coverage = (
        coverage_payload.get("coverage_requirement")
        if isinstance(coverage_payload.get("coverage_requirement"), dict)
        else {}
    )
    return _as_int(
        summary.get(
            "observed_positive_count",
            coverage.get("observed_positive_count", coverage_payload.get("observed_positive_count")),
        ),
        default=0,
    )


def _base_positive_targets(coverage_payload: dict[str, Any]) -> set[str]:
    context = coverage_payload.get("stage5_context") if isinstance(coverage_payload.get("stage5_context"), dict) else {}
    counts = context.get("positive_target_counts") if isinstance(context.get("positive_target_counts"), dict) else {}
    targets = {_text(target) for target, count in counts.items() if _as_int(count, 0) > 0 and _text(target)}
    if targets:
        return targets
    if _base_positive_count(coverage_payload) > 0:
        return {"ADRB2_GPCR_BLIND"}
    return set()


def _candidate_classification(row: dict[str, str]) -> dict[str, Any]:
    risk_flags: list[str] = []
    target = _text(row.get("target"))
    ligand_id = _text(row.get("ligand_id"))
    role = _text(row.get("role"))
    if not target:
        risk_flags.append("missing_target")
    if not ligand_id:
        risk_flags.append("missing_ligand_id")
    if not _as_bool(row.get("is_binder")):
        risk_flags.append("not_positive_binder")
    if not _is_gpcr_target(row):
        risk_flags.append("not_gpcr_target")
    if not _is_non_adrb2(row):
        risk_flags.append("adrb2_target_not_allowed_for_new_positive")
    if role.lower() in {"fit", "train", "calibration_fit"}:
        risk_flags.append("fit_role_not_allowed")
    if not _is_curated(row):
        risk_flags.append("curation_status_not_freeze_ready")
    if _as_float(row.get("reference_binding_kcal_mol")) is None:
        risk_flags.append("missing_reference_binding_kcal_mol")
    accepted = not risk_flags
    return {
        "target": target,
        "ligand_id": ligand_id,
        "target_family": _text(row.get("target_family")) or ("gpcr" if _is_gpcr_target(row) else ""),
        "is_binder": _as_bool(row.get("is_binder")),
        "reference_binding_kcal_mol": _as_float(row.get("reference_binding_kcal_mol")),
        "source": _text(row.get("source")),
        "source_url": _text(row.get("source_url")),
        "source_release": _text(row.get("source_release")),
        "provenance_date": _text(row.get("provenance_date")),
        "role": role,
        "curation_status": _text(row.get("curation_status")),
        "leakage_audit_id": _text(row.get("leakage_audit_id")),
        "row_classification": "new_non_adrb2_gpcr_positive_candidate",
        "accepted_for_freeze": bool(accepted),
        "risk_flags": risk_flags,
    }


def _leakage_audit_gate(audit_payload: dict[str, Any], audit_path: Path | None) -> dict[str, Any]:
    if not audit_payload:
        return {
            "status": "blocked",
            "pass": False,
            "blockers": ["leakage_audit_missing"],
            "source_artifact": str(audit_path) if audit_path else None,
        }

    failed_rules = audit_payload.get("failed_rules")
    if not isinstance(failed_rules, list):
        failed_rules = []
    blockers: list[str] = []
    if audit_payload.get("pass") is not True:
        blockers.append("leakage_audit_not_pass")
    for metric in (
        "key_overlap_count",
        "target_overlap_count",
        "ligand_overlap_count",
        "family_overlap_count",
        "scaffold_overlap_count",
        "sequence_leak_count",
        "pocket_leak_count",
    ):
        if _as_int(audit_payload.get(metric), 0) > 0:
            blockers.append(metric)
    for metric in ("family_overlap_ratio", "scaffold_overlap_ratio"):
        value = _as_float(audit_payload.get(metric))
        if value is not None and value > 0.0:
            blockers.append(metric)
    if failed_rules:
        blockers.append("failed_rules_present")
    blockers = sorted(set(blockers))
    return {
        "status": "pass" if not blockers else "blocked",
        "pass": not blockers,
        "blockers": blockers,
        "source_artifact": str(audit_path) if audit_path else None,
        "key_overlap_count": _as_int(audit_payload.get("key_overlap_count"), 0),
        "target_overlap_count": _as_int(audit_payload.get("target_overlap_count"), 0),
        "ligand_overlap_count": _as_int(audit_payload.get("ligand_overlap_count"), 0),
        "family_overlap_count": _as_int(audit_payload.get("family_overlap_count"), 0),
        "scaffold_overlap_count": _as_int(audit_payload.get("scaffold_overlap_count"), 0),
        "failed_rules": failed_rules,
    }


def build_packet(
    *,
    candidates_csv: str | Path | None = DEFAULT_CANDIDATES_CSV,
    leakage_audit_json: str | Path | None = DEFAULT_LEAKAGE_AUDIT_JSON,
    positive_coverage_json: str | Path | None = DEFAULT_POSITIVE_COVERAGE_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    candidates_path = _resolve(candidates_csv)
    audit_path = _resolve(leakage_audit_json)
    coverage_path = _resolve(positive_coverage_json)
    candidate_rows_raw = _read_csv(candidates_path)
    audit_payload = _read_json(audit_path)
    coverage_payload = _read_json(coverage_path)

    classified_rows = [_candidate_classification(row) for row in candidate_rows_raw]
    accepted_rows = [row for row in classified_rows if row["accepted_for_freeze"]]
    base_positive_count = _base_positive_count(coverage_payload)
    new_non_adrb2_positive_count = len(accepted_rows)
    total_positive_count = base_positive_count + new_non_adrb2_positive_count
    positive_targets = _base_positive_targets(coverage_payload) | {
        _text(row.get("target")) for row in accepted_rows if _text(row.get("target"))
    }
    leakage_gate = _leakage_audit_gate(audit_payload, audit_path)

    blockers: list[str] = []
    if not candidate_rows_raw:
        blockers.append("candidate_csv_empty")
    if new_non_adrb2_positive_count < MINIMUM_NEW_NON_ADRB2_POSITIVES:
        blockers.append("new_non_adrb2_positive_count_below_3")
    if total_positive_count < MINIMUM_POSITIVE_COUNT:
        blockers.append("positive_count_below_9")
    if len(positive_targets) < MINIMUM_DISTINCT_POSITIVE_GPCR_TARGETS:
        blockers.append("distinct_positive_gpcr_target_count_below_2")
    if leakage_gate["status"] != "pass":
        blockers.append("leakage_audit_not_green")
    if any(not row["accepted_for_freeze"] for row in classified_rows):
        blockers.append("candidate_rows_have_risk_flags")
    blockers = sorted(set(blockers))
    frozen = not blockers

    return {
        "packet_type": "gpcr_positive_coverage_freeze_packet",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_artifacts": {
            "candidates_csv": str(candidates_path) if candidates_path else None,
            "leakage_audit_json": str(audit_path) if audit_path else None,
            "positive_coverage_json": str(coverage_path) if coverage_path else None,
        },
        "summary": {
            "status": "frozen" if frozen else "blocked",
            "frozen": bool(frozen),
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "base_positive_count": int(base_positive_count),
            "new_non_adrb2_positive_count": int(new_non_adrb2_positive_count),
            "positive_count": int(total_positive_count),
            "minimum_positive_count": MINIMUM_POSITIVE_COUNT,
            "minimum_new_non_adrb2_positive_count": MINIMUM_NEW_NON_ADRB2_POSITIVES,
            "distinct_positive_gpcr_target_count": int(len(positive_targets)),
            "minimum_distinct_positive_gpcr_targets": MINIMUM_DISTINCT_POSITIVE_GPCR_TARGETS,
            "leakage_audit_pass": bool(leakage_gate["status"] == "pass"),
            "blocker_count": int(len(blockers)),
            "blockers": blockers,
            "next_required_step": (
                "Run guarded 100k readiness review; freeze packet alone does not promote claims."
                if frozen
                else "Curate at least 3 non-ADRB2 GPCR positives and pass leakage audit before freezing."
            ),
        },
        "claim_boundary": {
            "freeze_packet_is_not_claim_authorization": True,
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
        "acceptance_criteria": {
            "positive_count_gte": MINIMUM_POSITIVE_COUNT,
            "new_non_adrb2_positive_count_gte": MINIMUM_NEW_NON_ADRB2_POSITIVES,
            "distinct_positive_gpcr_target_count_gte": MINIMUM_DISTINCT_POSITIVE_GPCR_TARGETS,
            "leakage_audit_required_pass": True,
        },
        "leakage_audit_gate": leakage_gate,
        "candidate_rows": classified_rows,
        "accepted_candidate_rows": accepted_rows,
        "positive_target_counts": {
            target: sum(1 for row in accepted_rows if row.get("target") == target)
            + (base_positive_count if target in _base_positive_targets(coverage_payload) else 0)
            for target in sorted(positive_targets)
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    leakage = payload["leakage_audit_gate"]
    lines = [
        "# GPCR Positive Coverage Freeze Packet",
        "",
        "## Summary",
        f"- status: `{summary['status']}`",
        f"- frozen: `{str(summary['frozen']).lower()}`",
        f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
        f"- positive_count: `{summary['positive_count']}`",
        f"- new_non_adrb2_positive_count: `{summary['new_non_adrb2_positive_count']}`",
        f"- distinct_positive_gpcr_target_count: `{summary['distinct_positive_gpcr_target_count']}`",
        f"- leakage_audit_pass: `{str(summary['leakage_audit_pass']).lower()}`",
        f"- blockers: `{', '.join(summary['blockers'])}`",
        "",
        "## Leakage Audit",
        f"- status: `{leakage['status']}`",
        f"- blockers: `{', '.join(leakage.get('blockers', []))}`",
        "",
        "## Accepted Candidate Rows",
        "",
        "| target | ligand_id | reference_binding_kcal_mol | source |",
        "| --- | --- | ---: | --- |",
    ]
    accepted = payload.get("accepted_candidate_rows", [])
    if accepted:
        for row in accepted:
            lines.append(
                f"| `{row.get('target')}` | `{row.get('ligand_id')}` | {row.get('reference_binding_kcal_mol')} | {row.get('source')} |"
            )
    else:
        lines.append("|  |  |  | `none` |")
    lines.append("")
    return "\n".join(lines)


def write_outputs(
    *,
    candidates_csv: str | Path | None,
    leakage_audit_json: str | Path | None,
    positive_coverage_json: str | Path | None,
    out_json: str | Path,
    out_md: str | Path,
) -> dict[str, Any]:
    payload = build_packet(
        candidates_csv=candidates_csv,
        leakage_audit_json=leakage_audit_json,
        positive_coverage_json=positive_coverage_json,
    )
    out_json_path = _resolve(out_json)
    out_md_path = _resolve(out_md)
    assert out_json_path is not None
    assert out_md_path is not None
    _write_json(out_json_path, payload)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPCR non-ADRB2 positive coverage freeze packet.")
    parser.add_argument("--candidates-csv", default=DEFAULT_CANDIDATES_CSV)
    parser.add_argument("--leakage-audit-json", default=DEFAULT_LEAKAGE_AUDIT_JSON)
    parser.add_argument("--positive-coverage-json", default=DEFAULT_POSITIVE_COVERAGE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_outputs(
        candidates_csv=args.candidates_csv,
        leakage_audit_json=args.leakage_audit_json,
        positive_coverage_json=args.positive_coverage_json,
        out_json=args.out_json,
        out_md=args.out_md,
    )


if __name__ == "__main__":
    main()
