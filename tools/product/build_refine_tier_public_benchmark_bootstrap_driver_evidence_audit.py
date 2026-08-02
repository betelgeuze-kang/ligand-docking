#!/usr/bin/env python3
"""Read-only evidence audit for top R9 bootstrap recovery drivers."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECOVERY_QUEUE_JSON = "config/refine_tier_public_benchmark_bootstrap_recovery_queue_current.json"
DEFAULT_CANDIDATE_FILL_JSON = (
    "config/refine_tier_public_benchmark_statistical_support_metric_source_candidate_fill_current.json"
)
DEFAULT_PRIORITY_JSON = "config/refine_tier_public_benchmark_residual_metric_payload_priority_packet_current.json"
DEFAULT_BACKFILL_JSON = (
    "config/refine_tier_public_benchmark_seeded_metric_payload_receipt_backfill_packet_current.json"
)
DEFAULT_DOSSIER_JSON = "config/refine_tier_public_benchmark_residual_review_dossier_current.json"
DEFAULT_OUT_JSON = "config/refine_tier_public_benchmark_bootstrap_driver_evidence_audit_current.json"
DEFAULT_OUT_CSV = "runs/refine_tier_public_benchmark_bootstrap_driver_evidence_audit_current.csv"
DEFAULT_OUT_MD = "docs/refine_tier_public_benchmark_bootstrap_driver_evidence_audit_current.md"

REQUIRED_PAYLOAD_FIELDS = (
    "metric_name",
    "target_id",
    "pose_id",
    "value",
    "method",
    "input_artifacts",
    "input_artifact_sha256s",
    "operator_id",
    "reviewed_at_utc",
    "license_ok",
    "external_engine_calls",
)

CLAIM_BOUNDARY = (
    "R9 bootstrap driver evidence audit only joins existing bootstrap recovery, candidate-fill, residual "
    "priority, seeded-backfill, dossier, and local metric-source payload artifacts for the top bootstrap "
    "drivers. It validates local artifact presence and hashes where those hashes already exist. It does "
    "not compute new metric values, write metric payload JSON, approve receipts, promote canonical intake, "
    "change production scoring, run docking/MD, download, upload, email, delete, commit, push, or mutate "
    "external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path_like: str | Path, *, root: Path = ROOT) -> str:
    path = _resolve(path_like, root=root)
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _read_json(path_like: str | Path, *, root: Path = ROOT) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return payload if isinstance(payload, dict) else {}, True


def _rows(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = payload.get(key)
    return [dict(row) for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y"}


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return (_text(row.get("target_id")), _text(row.get("pose_id")))


def _split_semicolon(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    return [part.strip() for part in _text(value).split(";") if part.strip()]


def _group_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = _key(row)
        if key[0] and key[1]:
            grouped[key].append(row)
    return dict(grouped)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_present(path_text: str, *, root: Path) -> bool:
    if not path_text:
        return False
    if "::" in path_text:
        archive, member = path_text.split("::", 1)
        return bool(member.strip()) and _resolve(archive.strip(), root=root).is_file()
    return _resolve(path_text, root=root).exists()


def _hash_verified(path_text: str, expected_hash: str, *, root: Path) -> bool:
    if not path_text or not expected_hash or "::" in path_text:
        return False
    path = _resolve(path_text, root=root)
    if not path.is_file():
        return False
    return _sha256_file(path) == expected_hash


def _unique_input_hash_summary(rows: list[dict[str, Any]], artifact_key: str, hash_key: str, *, root: Path) -> dict[str, Any]:
    expected: dict[str, str] = {}
    for row in rows:
        artifacts = _split_semicolon(row.get(artifact_key))
        hashes = _split_semicolon(row.get(hash_key))
        for artifact, digest in zip(artifacts, hashes):
            if artifact and artifact not in expected:
                expected[artifact] = digest
    return {
        "input_artifact_count": len(expected),
        "input_artifact_present_count": sum(1 for artifact in expected if _artifact_present(artifact, root=root)),
        "input_artifact_sha256_verified_count": sum(
            1 for artifact, digest in expected.items() if _hash_verified(artifact, digest, root=root)
        ),
        "input_artifacts": ";".join(sorted(expected)),
    }


def _payload_schema_status(payload: dict[str, Any], *, target_id: str, pose_id: str, metric_name: str) -> tuple[bool, str]:
    blockers: list[str] = []
    missing = [field for field in REQUIRED_PAYLOAD_FIELDS if field not in payload]
    if missing:
        blockers.append("missing_required_payload_fields")
    if _text(payload.get("target_id")).lower() != target_id.lower():
        blockers.append("target_id_mismatch")
    if _text(payload.get("pose_id")) != pose_id:
        blockers.append("pose_id_mismatch")
    if _text(payload.get("metric_name")) != metric_name:
        blockers.append("metric_name_mismatch")
    if not _text(payload.get("method")):
        blockers.append("method_missing")
    if not _text(payload.get("operator_id")):
        blockers.append("operator_id_missing")
    if not _text(payload.get("reviewed_at_utc")):
        blockers.append("reviewed_at_utc_missing")
    if _bool(payload.get("license_ok")) is not True:
        blockers.append("license_not_ok")
    if _int(payload.get("external_engine_calls")) != 0:
        blockers.append("external_engine_calls_not_zero")
    if not _split_semicolon(payload.get("input_artifacts")):
        blockers.append("input_artifacts_missing")
    if len(_split_semicolon(payload.get("input_artifacts"))) != len(_split_semicolon(payload.get("input_artifact_sha256s"))):
        blockers.append("input_artifact_sha256_count_mismatch")
    return not blockers, ";".join(sorted(set(blockers)))


def _source_payload_audit(rows: list[dict[str, Any]], *, root: Path) -> dict[str, Any]:
    present_count = 0
    schema_valid_count = 0
    input_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    for row in rows:
        artifact = _text(row.get("metric_source_artifact")) or _text(row.get("expected_metric_source_artifact"))
        metric = _text(row.get("metric_name"))
        target_id = _text(row.get("target_id"))
        pose_id = _text(row.get("pose_id"))
        payload, present = _read_json(artifact, root=root)
        if not present:
            blockers.append(f"{metric}:metric_source_artifact_missing")
            continue
        present_count += 1
        valid, row_blockers = _payload_schema_status(payload, target_id=target_id, pose_id=pose_id, metric_name=metric)
        if valid:
            schema_valid_count += 1
        else:
            blockers.append(f"{metric}:{row_blockers}")
        input_rows.append(
            {
                "input_artifacts": ";".join(_split_semicolon(payload.get("input_artifacts"))),
                "input_artifact_sha256s": ";".join(_split_semicolon(payload.get("input_artifact_sha256s"))),
            }
        )
    input_summary = _unique_input_hash_summary(input_rows, "input_artifacts", "input_artifact_sha256s", root=root)
    return {
        "source_payload_present_count": present_count,
        "source_payload_schema_valid_count": schema_valid_count,
        "source_payload_input_artifact_count": input_summary["input_artifact_count"],
        "source_payload_input_artifact_present_count": input_summary["input_artifact_present_count"],
        "source_payload_input_artifact_sha256_verified_count": input_summary[
            "input_artifact_sha256_verified_count"
        ],
        "source_payload_blockers": ";".join(sorted(set(blockers))),
    }


def _candidate_audit(rows: list[dict[str, Any]], *, root: Path) -> dict[str, Any]:
    input_summary = _unique_input_hash_summary(
        rows,
        "candidate_input_artifacts",
        "candidate_input_artifact_sha256s",
        root=root,
    )
    return {
        "candidate_metric_row_count": len(rows),
        "candidate_metric_pass_count": sum(1 for row in rows if _text(row.get("candidate_status")) == "pass"),
        "candidate_expected_metric_source_artifact_present_count": sum(
            1 for row in rows if _bool(row.get("expected_metric_source_artifact_present"))
        ),
        "candidate_input_artifact_count": input_summary["input_artifact_count"],
        "candidate_input_artifact_present_count": input_summary["input_artifact_present_count"],
        "candidate_input_artifact_sha256_verified_count": input_summary["input_artifact_sha256_verified_count"],
        "candidate_input_artifacts": input_summary["input_artifacts"],
        "candidate_metric_names": ";".join(_text(row.get("metric_name")) for row in rows if _text(row.get("metric_name"))),
        "candidate_metric_values": ";".join(
            f"{_text(row.get('metric_name'))}:{_text(row.get('metric_value_candidate'))}"
            for row in rows
            if _text(row.get("metric_name"))
        ),
        "candidate_methods": ";".join(
            f"{_text(row.get('metric_name'))}:{_text(row.get('method_candidate'))}"
            for row in rows
            if _text(row.get("metric_name"))
        ),
    }


def _audit_class(
    *,
    source_class: str,
    candidate: dict[str, Any],
    source_payload: dict[str, Any],
    backfill_rows: list[dict[str, Any]],
) -> str:
    if source_class == "candidate_fill_preview" and candidate["candidate_expected_metric_source_artifact_present_count"] == 0:
        return "candidate_preview_payload_not_written"
    if source_payload["source_payload_present_count"] and backfill_rows:
        return "existing_payload_receipt_backfill_pending"
    if source_payload["source_payload_present_count"]:
        return "existing_payload_operator_receipt_review"
    return "driver_evidence_missing"


def build_refine_tier_public_benchmark_bootstrap_driver_evidence_audit(
    *,
    recovery_queue_json: str | Path = DEFAULT_RECOVERY_QUEUE_JSON,
    candidate_fill_json: str | Path = DEFAULT_CANDIDATE_FILL_JSON,
    priority_json: str | Path = DEFAULT_PRIORITY_JSON,
    backfill_json: str | Path = DEFAULT_BACKFILL_JSON,
    dossier_json: str | Path = DEFAULT_DOSSIER_JSON,
    root: str | Path = ROOT,
    top_n: int = 2,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    recovery_payload, recovery_present = _read_json(recovery_queue_json, root=root_path)
    candidate_payload, candidate_present = _read_json(candidate_fill_json, root=root_path)
    priority_payload, priority_present = _read_json(priority_json, root=root_path)
    backfill_payload, backfill_present = _read_json(backfill_json, root=root_path)
    dossier_payload, dossier_present = _read_json(dossier_json, root=root_path)

    recovery_rows = sorted(_rows(recovery_payload, "recovery_rows"), key=lambda row: _int(row.get("recovery_priority_rank")))
    driver_rows = [
        row for row in recovery_rows if _text(row.get("review_class")) == "bootstrap_p05_fragility_driver"
    ]
    if top_n > 0:
        driver_rows = driver_rows[:top_n]
    candidate_by_key = _group_rows(_rows(candidate_payload, "rows"))
    priority_by_key = _group_rows(_rows(priority_payload, "priority_rows"))
    backfill_by_key = _group_rows(_rows(backfill_payload, "backfill_template_rows"))
    dossier_by_key = _group_rows(_rows(dossier_payload, "dossier_rows"))

    audit_rows: list[dict[str, Any]] = []
    for rank, recovery in enumerate(driver_rows, start=1):
        key = _key(recovery)
        candidate_rows = sorted(candidate_by_key.get(key, []), key=lambda row: _text(row.get("metric_name")))
        priority_rows = sorted(priority_by_key.get(key, []), key=lambda row: _int(row.get("payload_priority_rank")))
        backfill_rows = sorted(backfill_by_key.get(key, []), key=lambda row: _int(row.get("payload_priority_rank")))
        dossier = dossier_by_key.get(key, [{}])[0]
        candidate = _candidate_audit(candidate_rows, root=root_path)
        source_payload = _source_payload_audit(backfill_rows or priority_rows or candidate_rows, root=root_path)
        audit_class = _audit_class(
            source_class=_text(recovery.get("source_class")),
            candidate=candidate,
            source_payload=source_payload,
            backfill_rows=backfill_rows,
        )
        operator_pending = sum(_int(row.get("operator_manual_pending_field_count")) for row in backfill_rows)
        if not operator_pending:
            operator_pending = sum(_int(row.get("operator_manual_pending_field_count")) for row in priority_rows)
        row = {
            "driver_audit_rank": rank,
            "recovery_priority_rank": _int(recovery.get("recovery_priority_rank")),
            "target_id": key[0],
            "pose_id": key[1],
            "work_order_id": _text(recovery.get("work_order_id")),
            "source_class": _text(recovery.get("source_class")),
            "split": _text(recovery.get("split")),
            "review_class": _text(recovery.get("review_class")),
            "audit_class": audit_class,
            "bootstrap_p05_delta_if_removed": _text(recovery.get("bootstrap_p05_delta_if_removed")),
            "rank_abs_error": _int(recovery.get("rank_abs_error")),
            "refine_proxy_score": _text(recovery.get("refine_proxy_score")),
            "deltaG_experimental_kcal_mol": _text(recovery.get("deltaG_experimental_kcal_mol")),
            "dossier_review_lane": _text(dossier.get("next_review_lane")),
            "dossier_feature_extrapolation_residual_class": _text(
                dossier.get("feature_extrapolation_residual_class")
            ),
            "dossier_feature_diagnostics_brief": _text(dossier.get("feature_diagnostics_brief")),
            "priority_operator_gap_classes": ";".join(
                f"{_text(priority.get('metric_name'))}:{_text(priority.get('operator_gap_class'))}"
                for priority in priority_rows
            ),
            "priority_metric_source_artifacts": ";".join(
                _text(priority.get("metric_source_artifact")) for priority in priority_rows if _text(priority.get("metric_source_artifact"))
            ),
            "backfill_template_row_count": len(backfill_rows),
            "backfill_payload_validation_pass_count": sum(
                1 for row in backfill_rows if _text(row.get("payload_validation_status")) == "pass"
            ),
            "operator_manual_pending_field_count": operator_pending,
            **candidate,
            **source_payload,
            "driver_evidence_audit_ready": True,
            "payload_write_allowed": False,
            "canonical_intake_promotion_allowed": False,
            "claim_promotion_allowed": False,
            "production_score_mutation_allowed": False,
            "external_state_mutated": False,
            "next_required_review": (
                "Review candidate value/method/input hashes and do not write payloads until operator approval."
                if audit_class == "candidate_preview_payload_not_written"
                else "Review existing payload schema/hash evidence and complete the operator backfill receipt."
            ),
        }
        audit_rows.append(row)

    top_row = audit_rows[0] if audit_rows else {}
    summary = {
        "packet_type": "refine_tier_public_benchmark_bootstrap_driver_evidence_audit",
        "status": (
            "refine_tier_public_benchmark_bootstrap_driver_evidence_audit_ready"
            if recovery_present and candidate_present and priority_present and audit_rows
            else "blocked_refine_tier_public_benchmark_bootstrap_driver_evidence_audit"
        ),
        "recovery_queue_json": _display(recovery_queue_json, root=root_path),
        "recovery_queue_json_present": recovery_present,
        "candidate_fill_json": _display(candidate_fill_json, root=root_path),
        "candidate_fill_json_present": candidate_present,
        "priority_json": _display(priority_json, root=root_path),
        "priority_json_present": priority_present,
        "backfill_json": _display(backfill_json, root=root_path),
        "backfill_json_present": backfill_present,
        "dossier_json": _display(dossier_json, root=root_path),
        "dossier_json_present": dossier_present,
        "driver_audit_row_count": len(audit_rows),
        "candidate_preview_payload_not_written_count": sum(
            1 for row in audit_rows if row["audit_class"] == "candidate_preview_payload_not_written"
        ),
        "existing_payload_receipt_backfill_pending_count": sum(
            1 for row in audit_rows if row["audit_class"] == "existing_payload_receipt_backfill_pending"
        ),
        "candidate_input_artifact_count": sum(_int(row.get("candidate_input_artifact_count")) for row in audit_rows),
        "candidate_input_artifact_sha256_verified_count": sum(
            _int(row.get("candidate_input_artifact_sha256_verified_count")) for row in audit_rows
        ),
        "source_payload_present_count": sum(_int(row.get("source_payload_present_count")) for row in audit_rows),
        "source_payload_schema_valid_count": sum(_int(row.get("source_payload_schema_valid_count")) for row in audit_rows),
        "source_payload_input_artifact_sha256_verified_count": sum(
            _int(row.get("source_payload_input_artifact_sha256_verified_count")) for row in audit_rows
        ),
        "operator_manual_pending_field_count": sum(
            _int(row.get("operator_manual_pending_field_count")) for row in audit_rows
        ),
        "top_driver_target_id": top_row.get("target_id", ""),
        "top_driver_pose_id": top_row.get("pose_id", ""),
        "top_driver_audit_class": top_row.get("audit_class", ""),
        "top_driver_bootstrap_p05_delta_if_removed": top_row.get("bootstrap_p05_delta_if_removed", ""),
        "payload_write_allowed": False,
        "canonical_intake_promotion_allowed": False,
        "claim_promotion_allowed": False,
        "production_score_mutation_allowed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Review the top bootstrap drivers at the evidence layer: candidate-preview payload-not-written rows "
            "must be operator-reviewed before payload writes, and existing payload rows need backfill receipt approval."
        ),
    }
    return {"summary": summary, "audit_rows": audit_rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# R9 Bootstrap Driver Evidence Audit",
        "",
        f"- status: `{s['status']}`",
        f"- driver_audit_row_count: `{s['driver_audit_row_count']}`",
        f"- candidate_preview_payload_not_written_count: `{s['candidate_preview_payload_not_written_count']}`",
        f"- existing_payload_receipt_backfill_pending_count: `{s['existing_payload_receipt_backfill_pending_count']}`",
        f"- candidate_input_artifact_sha256_verified_count: `{s['candidate_input_artifact_sha256_verified_count']}`",
        f"- source_payload_schema_valid_count: `{s['source_payload_schema_valid_count']}`",
        f"- source_payload_input_artifact_sha256_verified_count: `{s['source_payload_input_artifact_sha256_verified_count']}`",
        f"- operator_manual_pending_field_count: `{s['operator_manual_pending_field_count']}`",
        f"- top_driver_target_id: `{s['top_driver_target_id']}`",
        f"- top_driver_pose_id: `{s['top_driver_pose_id']}`",
        f"- top_driver_audit_class: `{s['top_driver_audit_class']}`",
        f"- claim_promotion_allowed: `{s['claim_promotion_allowed']}`",
        "",
        "## Driver Audits",
        "",
        "| rank | target | pose | source | audit class | p05 delta | candidate hashes | source payloads | pending fields | next |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["audit_rows"]:
        lines.append(
            f"| `{row['driver_audit_rank']}` | `{row['target_id']}` | `{row['pose_id']}` | "
            f"`{row['source_class']}` | `{row['audit_class']}` | "
            f"`{row['bootstrap_p05_delta_if_removed']}` | "
            f"`{row['candidate_input_artifact_sha256_verified_count']}/{row['candidate_input_artifact_count']}` | "
            f"`{row['source_payload_schema_valid_count']}/{row['source_payload_present_count']}` | "
            f"`{row['operator_manual_pending_field_count']}` | {row['next_required_review']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", s["next_required_step"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only R9 bootstrap driver evidence audit.")
    parser.add_argument("--recovery-queue-json", default=DEFAULT_RECOVERY_QUEUE_JSON)
    parser.add_argument("--candidate-fill-json", default=DEFAULT_CANDIDATE_FILL_JSON)
    parser.add_argument("--priority-json", default=DEFAULT_PRIORITY_JSON)
    parser.add_argument("--backfill-json", default=DEFAULT_BACKFILL_JSON)
    parser.add_argument("--dossier-json", default=DEFAULT_DOSSIER_JSON)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--top-n", type=int, default=2)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_refine_tier_public_benchmark_bootstrap_driver_evidence_audit(
        recovery_queue_json=args.recovery_queue_json,
        candidate_fill_json=args.candidate_fill_json,
        priority_json=args.priority_json,
        backfill_json=args.backfill_json,
        dossier_json=args.dossier_json,
        root=root,
        top_n=args.top_n,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["audit_rows"])
    _write_md(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
