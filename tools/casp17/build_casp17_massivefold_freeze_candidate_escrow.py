#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_FREEZE_CANDIDATE_PREFLIGHT_JSON = (
    "casp17/casp17_massivefold_freeze_candidate_format_preflight_current.json"
)
DEFAULT_OUT_DIR = "casp17/massivefold_freeze_candidate_escrow"
DEFAULT_OUT_JSON = "casp17/casp17_massivefold_freeze_candidate_escrow_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_massivefold_freeze_candidate_escrow_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_MASSIVEFOLD_FREEZE_CANDIDATE_ESCROW.md"

CLAIM_BOUNDARY = (
    "CASP17 MassiveFold freeze-candidate escrow only. It freezes external-only selected model paths, "
    "SHA256 hashes, top5 manifests, viewers, and native-pending status for later rule-checked review or "
    "future native evaluation. It is not native accuracy, not internal prediction proof, not a CASP portal "
    "submission, and not permission to submit."
)
EXTERNAL_ONLY_POLICY = "external_no_native_freeze_candidate_escrow_only"
INTERNAL_PREDICTION_POLICY = "do_not_mark_as_internal_prediction"
SUBMISSION_POLICY = "do_not_submit_without_rule_check_and_operator_approval"
RULE_ID = "external_freeze_candidate_sha_escrow_v1"

ROW_COLUMNS = [
    "escrow_rank",
    "escrow_status",
    "target_group",
    "target_id",
    "decision_class",
    "final_selector_decision",
    "selected_model_filename",
    "model_path",
    "model_sha256",
    "model_size_bytes",
    "top5_manifest_csv",
    "top5_manifest_sha256",
    "viewer_html",
    "projection_svg",
    "source_decision_md",
    "preflight_md",
    "escrow_folder",
    "escrow_md",
    "model_present",
    "model_sha256_verified",
    "top5_manifest_present",
    "top5_sha256_verified",
    "viewer_present",
    "projection_present",
    "native_status",
    "competitive_proof_eligible",
    "blockers",
    "next_action",
    "external_only_policy",
    "internal_prediction_policy",
    "submission_policy",
    "claim_boundary",
    "rule_id",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like).strip():
        return ""
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return 0


def _is_true(value: Any) -> bool:
    return _text(value).lower() == "true"


def _safe_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_") or "unknown"


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


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _present(path_like: str) -> bool:
    return bool(path_like) and _resolve(path_like).is_file()


def _sha256(path_like: str) -> str:
    path = _resolve(path_like)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _size(path_like: str) -> int:
    if not _present(path_like):
        return 0
    try:
        return _resolve(path_like).stat().st_size
    except OSError:
        return 0


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _escrow_dir_name(row: dict[str, Any]) -> str:
    return f"{int(row['escrow_rank']):02d}_{row['target_group']}_{row['target_id'].lower()}"


def _build_row(rank: int, source: dict[str, Any], escrow_root: Path) -> dict[str, Any]:
    target_id = _text(source.get("target_id")).upper()
    target_group = _text(source.get("target_group"))
    model_path = _text(source.get("model_path"))
    top5_manifest = _text(source.get("top5_manifest_csv"))
    viewer_html = _text(source.get("viewer_html"))
    projection_svg = _text(source.get("projection_svg"))
    blockers: list[str] = []

    preflight_ready = _text(source.get("preflight_status")) == "freeze_candidate_format_preflight_ready_external_only"
    model_present = _present(model_path)
    top5_present = _present(top5_manifest)
    viewer_present = _present(viewer_html)
    projection_present = _present(projection_svg)
    model_sha = _sha256(model_path) if model_present else ""
    top5_sha = _sha256(top5_manifest) if top5_present else ""

    if not preflight_ready:
        blockers.append("freeze_candidate_preflight_not_ready")
    if not target_id:
        blockers.append("target_id_missing")
    if not model_present:
        blockers.append("model_file_missing")
    elif _size(model_path) <= 0:
        blockers.append("model_file_empty")
    if not top5_present:
        blockers.append("top5_manifest_missing")
    if not viewer_present:
        blockers.append("viewer_html_missing")
    if not projection_present:
        blockers.append("projection_svg_missing")

    escrow_folder = escrow_root / _escrow_dir_name(
        {"escrow_rank": rank, "target_group": target_group or "unknown", "target_id": target_id or "unknown"}
    )
    escrow_md = escrow_folder / "FREEZE_ESCROW.md"
    ready = not blockers
    return {
        "escrow_rank": rank,
        "escrow_status": "freeze_candidate_escrow_ready_external_only" if ready else "freeze_candidate_escrow_blocked",
        "target_group": target_group,
        "target_id": target_id,
        "decision_class": _text(source.get("decision_class")),
        "final_selector_decision": _text(source.get("final_selector_decision")),
        "selected_model_filename": _text(source.get("selected_model_filename")),
        "model_path": _artifact(model_path),
        "model_sha256": model_sha,
        "model_size_bytes": _size(model_path),
        "top5_manifest_csv": _artifact(top5_manifest),
        "top5_manifest_sha256": top5_sha,
        "viewer_html": _artifact(viewer_html),
        "projection_svg": _artifact(projection_svg),
        "source_decision_md": _artifact(source.get("source_decision_md", "")),
        "preflight_md": _artifact(source.get("preflight_md", "")),
        "escrow_folder": _artifact(escrow_folder),
        "escrow_md": _artifact(escrow_md),
        "model_present": str(model_present),
        "model_sha256_verified": str(bool(model_sha)),
        "top5_manifest_present": str(top5_present),
        "top5_sha256_verified": str(bool(top5_sha)),
        "viewer_present": str(viewer_present),
        "projection_present": str(projection_present),
        "native_status": "official_native_release_pending",
        "competitive_proof_eligible": "false",
        "blockers": ",".join(blockers),
        "next_action": "keep escrow hashes stable; run CASP rule checks only after operator approval and attach native metrics after release",
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    preflight_payload = _read_json(args.freeze_candidate_preflight_json)
    preflight_summary = _summary(preflight_payload)
    source_rows = _rows(preflight_payload)
    source_rows.sort(key=lambda row: _int(row.get("preflight_rank")) or 9999)
    escrow_root = _resolve(args.out_dir)
    rows = [_build_row(rank, row, escrow_root) for rank, row in enumerate(source_rows, start=1)]
    ready = sum(1 for row in rows if row["escrow_status"] == "freeze_candidate_escrow_ready_external_only")
    blocked = len(rows) - ready
    model_sha_count = sum(1 for row in rows if _is_true(row.get("model_sha256_verified")))
    top5_sha_count = sum(1 for row in rows if _is_true(row.get("top5_sha256_verified")))
    protein_count = sum(1 for row in rows if row["target_group"] == "protein_complex")
    rna_count = sum(1 for row in rows if row["target_group"] == "rna_hybrid")
    manifest_signature = hashlib.sha256(
        json.dumps(
            [
                {
                    "target_id": row["target_id"],
                    "model_path": row["model_path"],
                    "model_sha256": row["model_sha256"],
                    "top5_manifest_sha256": row["top5_manifest_sha256"],
                }
                for row in rows
            ],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    first_blocked = next((row for row in rows if row["escrow_status"] != "freeze_candidate_escrow_ready_external_only"), {})
    summary = {
        "packet_type": "casp17_massivefold_freeze_candidate_escrow",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "massivefold_freeze_candidate_escrow_status": (
            "massivefold_freeze_candidate_escrow_ready_external_only"
            if rows and not blocked
            else (
                "massivefold_freeze_candidate_escrow_partial_external_only"
                if ready
                else "massivefold_freeze_candidate_escrow_blocked"
            )
        ),
        "freeze_candidate_preflight_status": _text(
            preflight_summary.get("massivefold_freeze_candidate_format_preflight_status")
        ),
        "escrow_dir": _artifact(escrow_root),
        "escrow_count": len(rows),
        "ready_escrow_count": ready,
        "blocked_escrow_count": blocked,
        "model_sha256_count": model_sha_count,
        "top5_sha256_count": top5_sha_count,
        "model_present_count": sum(1 for row in rows if _is_true(row.get("model_present"))),
        "viewer_present_count": sum(1 for row in rows if _is_true(row.get("viewer_present"))),
        "projection_present_count": sum(1 for row in rows if _is_true(row.get("projection_present"))),
        "top5_manifest_present_count": sum(1 for row in rows if _is_true(row.get("top5_manifest_present"))),
        "existing_freeze_candidate_count": _int(preflight_summary.get("existing_freeze_candidate_count")),
        "probe_freeze_candidate_count": _int(preflight_summary.get("probe_freeze_candidate_count")),
        "protein_complex_escrow_count": protein_count,
        "rna_hybrid_escrow_count": rna_count,
        "native_pending_count": len(rows),
        "competitive_proof_eligible": False,
        "competitive_proof_eligible_count": 0,
        "author_serialized_count": 0,
        "manifest_signature_sha256": manifest_signature,
        "first_escrow_target_id": _text(rows[0].get("target_id")) if rows else "",
        "first_blocked_target_id": _text(first_blocked.get("target_id")),
        "first_blocker": _text(first_blocked.get("blockers")).split(",")[0] if _text(first_blocked.get("blockers")) else "",
        "external_only_policy": EXTERNAL_ONLY_POLICY,
        "internal_prediction_policy": INTERNAL_PREDICTION_POLICY,
        "submission_policy": SUBMISSION_POLICY,
        "rule_id": RULE_ID,
        "next_action": "hold these external-only hashes for rule-checked formatting review and future native evaluation; keep strict-blind proof separate",
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_target_md(row: dict[str, Any]) -> None:
    path = _resolve(row["escrow_md"])
    lines = [
        f"# {row['target_id']} MassiveFold Freeze-Candidate Escrow",
        "",
        f"- status: `{row['escrow_status']}`",
        f"- decision class: `{row['decision_class']}`",
        f"- final selector decision: `{row['final_selector_decision']}`",
        f"- selected model: `{row['selected_model_filename']}`",
        f"- model path: `{row['model_path']}`",
        f"- model sha256: `{row['model_sha256'] or '-'}`",
        f"- top5 manifest: `{row['top5_manifest_csv']}`",
        f"- top5 sha256: `{row['top5_manifest_sha256'] or '-'}`",
        f"- viewer: `{row['viewer_html'] or '-'}`",
        f"- projection: `{row['projection_svg'] or '-'}`",
        f"- native status: `{row['native_status']}`",
        f"- competitive proof eligible: `{row['competitive_proof_eligible']}`",
        f"- blockers: `{row['blockers'] or '-'}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 MassiveFold Freeze-Candidate Escrow",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['massivefold_freeze_candidate_escrow_status']}`",
        f"- escrow ready/blocked/total: `{summary['ready_escrow_count']}/{summary['blocked_escrow_count']}/{summary['escrow_count']}`",
        f"- SHA model/top5: `{summary['model_sha256_count']}/{summary['top5_sha256_count']}`",
        f"- artifacts model/viewer/projection/top5: `{summary['model_present_count']}/{summary['viewer_present_count']}/{summary['projection_present_count']}/{summary['top5_manifest_present_count']}`",
        f"- existing/probe freeze candidates: `{summary['existing_freeze_candidate_count']}/{summary['probe_freeze_candidate_count']}`",
        f"- RNA/protein-complex: `{summary['rna_hybrid_escrow_count']}/{summary['protein_complex_escrow_count']}`",
        f"- native pending/proof eligible/author serialized: `{summary['native_pending_count']}/{summary['competitive_proof_eligible_count']}/{summary['author_serialized_count']}`",
        f"- first escrow/blocked: `{summary['first_escrow_target_id'] or '-'}`/`{summary['first_blocked_target_id'] or '-'}`",
        f"- manifest_signature_sha256: `{summary['manifest_signature_sha256']}`",
        "",
        "## Escrow Rows",
        "",
        "| target | status | class | model sha | top5 sha | escrow md | blockers |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['escrow_status']}` | `{row['decision_class']}` | "
            f"`{row['model_sha256'][:16] if row['model_sha256'] else '-'}` | "
            f"`{row['top5_manifest_sha256'][:16] if row['top5_manifest_sha256'] else '-'}` | "
            f"`{row['escrow_md']}` | {row['blockers'] or '-'} |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    for row in payload["rows"]:
        _write_target_md(row)
    _write_md(args.out_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build MassiveFold freeze-candidate SHA escrow.")
    parser.add_argument("--freeze-candidate-preflight-json", default=DEFAULT_FREEZE_CANDIDATE_PREFLIGHT_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
