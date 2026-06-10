#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SLICE_ROWS_CSV = "runs/gpcr_drd2_hard_decoy_slice_packet_rows_current.csv"
DEFAULT_PENALTY_ENVELOPE_JSON = "runs/gpcr_drd2_hard_decoy_penalty_envelope_current.json"
DEFAULT_SLICE_SCORES_CSV = "runs/gpcr_drd2_repaired_slice_shadow_input_scores_current.csv"
DEFAULT_SPEC_JSON = "runs/gpcr_residual_prototype_spec_cationic_pose_distortion_shadow_v10_current.json"
DEFAULT_REPLAY_SCORES_CSV = "runs/gpcr_cationic_pose_distortion_v10_shadow_replay_scores_current.csv"
DEFAULT_REPLAY_SUMMARY_JSON = "runs/gpcr_cationic_pose_distortion_v10_shadow_replay_summary_current.json"
DEFAULT_REPLAY_SUMMARY_MD = "runs/gpcr_cationic_pose_distortion_v10_shadow_replay_summary_current.md"
DEFAULT_REVIEW_JSON = "runs/gpcr_cationic_pose_distortion_v10_shadow_replay_review_current.json"
DEFAULT_REVIEW_MD = "runs/gpcr_cationic_pose_distortion_v10_shadow_replay_review_current.md"
DEFAULT_OUT_JSON = "runs/gpcr_drd2_repaired_slice_shadow_replay_packet_current.json"
DEFAULT_OUT_MD = "runs/gpcr_drd2_repaired_slice_shadow_replay_packet_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or str(value).strip() == "":
            return default
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if out == out else default


def _truthy(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "t", "yes", "y"}


def build_slice_input_scores(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        base_score = _float(row.get("base_score"))
        out.append(
            {
                "target": _text(row.get("target")),
                "ligand_id": _text(row.get("ligand_id")),
                "is_positive": _truthy(row.get("is_positive")),
                "is_binder": _truthy(row.get("is_positive")),
                "base_score": base_score,
                "binding_score_composite_v7": base_score,
                "label_free_penalty_pressure": _float(row.get("label_free_penalty_pressure")),
                "label_free_support_pressure": _float(row.get("label_free_support_pressure")),
                "window_like_nonbasic_pressure": _float(row.get("window_like_nonbasic_pressure")),
                "invalid_close_overanchor_pressure": _float(row.get("invalid_close_overanchor_pressure")),
                "hydrophobic_overcontact_pressure": _float(row.get("hydrophobic_overcontact_pressure")),
                "multipolar_basic_pressure": _float(row.get("multipolar_basic_pressure")),
                "cationic_mismatch_pressure": _float(row.get("cationic_mismatch_pressure")),
                "pose_distortion_pressure": _float(row.get("pose_distortion_pressure")),
                "pose_preservation_support": _float(row.get("pose_preservation_support")),
                "valid_anchor_support": _float(row.get("valid_anchor_support")),
                "compact_anchor_support": _float(row.get("compact_anchor_support")),
                "slice_label_text": _text(row.get("slice_label_text")),
                "binding_energy_mmpbsa_kcal_mol_proxy": 0.0,
                "mean_min_distance_A": _float(row.get("atom_anchor_mean_distance_A")),
                "stability_score": 0.0,
                "contact_fraction": _float(row.get("atom_contact_fraction_2p8_4p2A")),
                "ligand_h_donors": _float(row.get("ligand_h_donors")),
                "ligand_h_acceptors": _float(row.get("ligand_h_acceptors")),
                "ligand_rot_bonds": _float(row.get("ligand_rot_bonds")),
                "ligand_logp": _float(row.get("ligand_logp")),
                "basic_amine_count": _float(row.get("basic_amine_count")),
            }
        )
    return out


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def build_packet(
    *,
    slice_rows_csv: str | Path = DEFAULT_SLICE_ROWS_CSV,
    penalty_envelope_json: str | Path = DEFAULT_PENALTY_ENVELOPE_JSON,
    slice_scores_csv: str | Path = DEFAULT_SLICE_SCORES_CSV,
    spec_json: str | Path = DEFAULT_SPEC_JSON,
    replay_scores_csv: str | Path = DEFAULT_REPLAY_SCORES_CSV,
    replay_summary_json: str | Path = DEFAULT_REPLAY_SUMMARY_JSON,
    review_json: str | Path = DEFAULT_REVIEW_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    slice_rows = _read_csv(slice_rows_csv)
    if not slice_rows:
        raise FileNotFoundError(f"hard decoy slice rows missing: {_resolve(slice_rows_csv)}")

    _run([sys.executable, "tools/gpcr_replay/build_gpcr_drd2_hard_decoy_penalty_envelope.py", "--rows-csv", str(slice_rows_csv)])
    envelope = _read_json(penalty_envelope_json)
    envelope_summary = envelope.get("summary") if isinstance(envelope.get("summary"), dict) else {}

    input_scores = build_slice_input_scores(slice_rows)
    _write_csv(slice_scores_csv, input_scores)

    from tools.accounting.build_gpcr_residual_prototype_spec import build_payload as build_spec_payload, _write_csv as write_spec_csv, _write_markdown as write_spec_markdown

    spec_payload = build_spec_payload(variant="gpcr_core_cationic_pose_distortion_shadow_v10")
    spec_path = _resolve(spec_json)
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(spec_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_spec_csv(_resolve(spec_json).with_suffix(".csv"), spec_payload["feature_rows"])
    write_spec_markdown(_resolve(spec_json).with_suffix(".md"), spec_payload)

    _run(
        [
            sys.executable,
            "tools/product/replay_gpcr_residual_shadow_scores.py",
            "--input-scores-csv",
            str(slice_scores_csv),
            "--residual-prototype-spec-json",
            str(spec_json),
            "--out-scores-csv",
            str(replay_scores_csv),
            "--out-summary-json",
            str(replay_summary_json),
            "--out-summary-md",
            str(DEFAULT_REPLAY_SUMMARY_MD),
        ]
    )

    _run(
        [
            sys.executable,
            "tools/gpcr_replay/build_gpcr_cationic_pose_distortion_shadow_replay_review.py",
            "--input-scores-csv",
            str(replay_scores_csv),
            "--input-summary-json",
            str(replay_summary_json),
            "--out-json",
            str(review_json),
            "--out-md",
            str(DEFAULT_REVIEW_MD),
        ]
    )

    replay_summary = _read_json(replay_summary_json).get("summary", {})
    review_summary = _read_json(review_json).get("summary", {})
    positive_rank = review_summary.get("selected_slice_positive_rank")
    status = _text(review_summary.get("status"))
    blockers = list(review_summary.get("blockers") or [])
    summary = {
        "packet_type": "gpcr_drd2_repaired_slice_shadow_replay_packet",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status if status else "blocked_internal_review",
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "full_100k_claim_review_allowed": False,
        "slice_row_count": len(slice_rows),
        "penalty_envelope_status": _text(envelope_summary.get("status")),
        "penalty_envelope_next_action": _text(envelope_summary.get("next_action")),
        "bounded_best_positive_rank": envelope_summary.get("bounded_best_positive_rank"),
        "bounded_best_penalty_weight": envelope_summary.get("bounded_best_penalty_weight"),
        "bounded_best_support_weight": envelope_summary.get("bounded_best_support_weight"),
        "replay_status": _text(replay_summary.get("status")),
        "selected_slice_positive_rank": positive_rank,
        "selected_slice_decoys_above_positive_count": review_summary.get("selected_slice_decoys_above_positive_count"),
        "active_score_locked_to_base": review_summary.get("active_score_locked_to_base"),
        "blockers": blockers,
        "artifacts": {
            "slice_rows_csv": str(_resolve(slice_rows_csv)),
            "penalty_envelope_json": str(_resolve(penalty_envelope_json)),
            "slice_scores_csv": str(_resolve(slice_scores_csv)),
            "spec_json": str(_resolve(spec_json)),
            "replay_scores_csv": str(_resolve(replay_scores_csv)),
            "replay_summary_json": str(_resolve(replay_summary_json)),
            "review_json": str(_resolve(review_json)),
        },
        "next_required_step": (
            "Selected-slice v10 shadow replay is green under claim lock. Materialize equivalent label-free "
            "cationic-center/pose-distortion features for frozen non-ADRB2 rows, then resume mount stage2 "
            "regeneration before any full guarded 100k claim review."
            if status == "selected_slice_shadow_green_claim_locked"
            else "Run build_gpcr_drd2_valid_anchor_discriminator_slice_replay_packet.py after refining "
            "false-valid-anchor pressure, then resume mount stage2 regeneration if slice replay greens."
        ),
    }
    return {
        "summary": summary,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "full_100k_claim_review_allowed": False,
            "selected_slice_green_is_not_claim_evidence": True,
        },
        "penalty_envelope_summary": envelope_summary,
        "replay_summary": replay_summary,
        "review_summary": review_summary,
    }


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR DRD2 Repaired Slice Shadow Replay Packet",
        "",
        f"- status: `{summary['status']}`",
        f"- slice_row_count: `{summary['slice_row_count']}`",
        f"- penalty_envelope_status: `{summary['penalty_envelope_status']}`",
        f"- replay_status: `{summary['replay_status']}`",
        f"- selected_slice_positive_rank: `{summary['selected_slice_positive_rank']}`",
        f"- selected_slice_decoys_above_positive_count: `{summary['selected_slice_decoys_above_positive_count']}`",
        f"- active_score_locked_to_base: `{summary['active_score_locked_to_base']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
    ]
    if summary.get("blockers"):
        lines.extend(["## Blockers", ""])
        for blocker in summary["blockers"]:
            lines.append(f"- `{blocker}`")
        lines.append("")
    _resolve(path_like).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run v10 label-free penalty envelope and repaired-slice shadow replay chain.")
    parser.add_argument("--slice-rows-csv", default=DEFAULT_SLICE_ROWS_CSV)
    parser.add_argument("--penalty-envelope-json", default=DEFAULT_PENALTY_ENVELOPE_JSON)
    parser.add_argument("--slice-scores-csv", default=DEFAULT_SLICE_SCORES_CSV)
    parser.add_argument("--spec-json", default=DEFAULT_SPEC_JSON)
    parser.add_argument("--replay-scores-csv", default=DEFAULT_REPLAY_SCORES_CSV)
    parser.add_argument("--replay-summary-json", default=DEFAULT_REPLAY_SUMMARY_JSON)
    parser.add_argument("--review-json", default=DEFAULT_REVIEW_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_packet(
        slice_rows_csv=args.slice_rows_csv,
        penalty_envelope_json=args.penalty_envelope_json,
        slice_scores_csv=args.slice_scores_csv,
        spec_json=args.spec_json,
        replay_scores_csv=args.replay_scores_csv,
        replay_summary_json=args.replay_summary_json,
        review_json=args.review_json,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
