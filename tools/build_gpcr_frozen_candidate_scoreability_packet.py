#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_FREEZE_JSON = "runs/gpcr_positive_coverage_freeze_packet_current.json"
DEFAULT_PROFILE_JSON = "config/ligand_htvs_blind_gpcr_adrb2_v4_scorefix3_prod100k.json"
DEFAULT_OUT_JSON = "runs/gpcr_frozen_candidate_scoreability_current.json"
DEFAULT_OUT_MD = "runs/gpcr_frozen_candidate_scoreability_current.md"


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
    return _text(value).lower() in {"1", "true", "yes", "y", "pass", "passed", "green", "frozen"}


def _as_int(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _split_list(value: Any) -> set[str]:
    return {part.strip() for part in str(value or "").split(",") if part.strip()}


def _key_set(rows: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(_text(row.get("target")), _text(row.get("ligand_id"))) for row in rows}


def _target_set(rows: list[dict[str, str]]) -> set[str]:
    return {_text(row.get("target")) for row in rows if _text(row.get("target"))}


def _ligand_set(rows: list[dict[str, str]]) -> set[str]:
    return {_text(row.get("ligand_id")) for row in rows if _text(row.get("ligand_id"))}


def _native_targets(rows: list[dict[str, str]]) -> tuple[set[str], list[str]]:
    targets: set[str] = set()
    missing_paths: list[str] = []
    for row in rows:
        target = _text(row.get("target"))
        native = _text(row.get("native_pdb_path"))
        if not target:
            continue
        targets.add(target)
        native_path = _resolve(native)
        if native and native_path is not None and not native_path.exists():
            missing_paths.append(target)
    return targets, sorted(set(missing_paths))


def _candidate_rows(freeze_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = freeze_payload.get("accepted_candidate_rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _freeze_positive_count(payload: dict[str, Any], summary: dict[str, Any]) -> int | None:
    count = _as_int(payload.get("positive_count"))
    if count is not None:
        return count
    return _as_int(summary.get("positive_count"))


def _profile_positive_count(rows: list[dict[str, str]], profile_targets: set[str]) -> int:
    count = 0
    for row in rows:
        target = _text(row.get("target"))
        if target not in profile_targets:
            continue
        if _as_bool(row.get("is_binder")):
            count += 1
    return count


def build_packet(
    *,
    freeze_json: str | Path | None = DEFAULT_FREEZE_JSON,
    profile_json: str | Path | None = DEFAULT_PROFILE_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    freeze_path = _resolve(freeze_json)
    profile_path = _resolve(profile_json)
    freeze_payload = _read_json(freeze_path)
    profile_payload = _read_json(profile_path)
    freeze_summary = freeze_payload.get("summary") if isinstance(freeze_payload.get("summary"), dict) else {}
    freeze_positive_count = _freeze_positive_count(freeze_payload, freeze_summary)
    candidates = _candidate_rows(freeze_payload)
    candidate_targets = {_text(row.get("target")) for row in candidates if _text(row.get("target"))}
    candidate_ligands = {_text(row.get("ligand_id")) for row in candidates if _text(row.get("ligand_id"))}
    candidate_keys = {(_text(row.get("target")), _text(row.get("ligand_id"))) for row in candidates}

    profile_targets = _split_list(profile_payload.get("targets"))
    hard_decoy_targets = _split_list(profile_payload.get("hard_decoy_targets"))
    ranking_labels = _read_csv(_resolve(profile_payload.get("ranking_labels_csv")))
    eval_splits = _read_csv(_resolve(profile_payload.get("eval_split_csv")))
    target_meta = _read_csv(_resolve(profile_payload.get("leakage_target_meta_csv")))
    ligand_meta = _read_csv(_resolve(profile_payload.get("leakage_ligand_meta_csv")))
    native_rows = _read_csv(_resolve(profile_payload.get("target_native_csv")))
    native_targets, native_missing_paths = _native_targets(native_rows)

    label_keys = _key_set(ranking_labels)
    split_keys = _key_set(eval_splits)
    target_meta_targets = _target_set(target_meta)
    ligand_meta_ligands = _ligand_set(ligand_meta)
    profile_positive_count = _profile_positive_count(ranking_labels, profile_targets)

    missing = {
        "profile_targets": sorted(candidate_targets - profile_targets),
        "hard_decoy_targets": sorted(candidate_targets - hard_decoy_targets),
        "native_targets": sorted(candidate_targets - native_targets),
        "native_paths": native_missing_paths,
        "ranking_label_keys": sorted(f"{target}:{ligand}" for target, ligand in (candidate_keys - label_keys)),
        "eval_split_keys": sorted(f"{target}:{ligand}" for target, ligand in (candidate_keys - split_keys)),
        "target_meta_targets": sorted(candidate_targets - target_meta_targets),
        "ligand_meta_ligands": sorted(candidate_ligands - ligand_meta_ligands),
    }

    blockers: list[str] = []
    if not freeze_payload:
        blockers.append("freeze_packet_missing")
    if not _as_bool(freeze_summary.get("frozen")):
        blockers.append("freeze_packet_not_frozen")
    if not candidates:
        blockers.append("accepted_candidate_rows_missing")
    if not profile_payload:
        blockers.append("profile_missing")
    for key, values in missing.items():
        if values:
            blockers.append(f"missing_{key}")
    if freeze_positive_count is not None and profile_positive_count < freeze_positive_count:
        blockers.append("profile_positive_count_below_freeze_packet")
    blockers = sorted(set(blockers))
    passed = not blockers

    return {
        "packet_type": "gpcr_frozen_candidate_scoreability",
        "source_artifacts": {
            "freeze_json": str(freeze_path) if freeze_path else None,
            "profile_json": str(profile_path) if profile_path else None,
            "target_native_csv": profile_payload.get("target_native_csv"),
            "ranking_labels_csv": profile_payload.get("ranking_labels_csv"),
            "eval_split_csv": profile_payload.get("eval_split_csv"),
            "target_meta_csv": profile_payload.get("leakage_target_meta_csv"),
            "ligand_meta_csv": profile_payload.get("leakage_ligand_meta_csv"),
        },
        "summary": {
            "status": "pass" if passed else "blocked",
            "pass": bool(passed),
            "candidate_count": len(candidates),
            "freeze_positive_count": freeze_positive_count,
            "profile_positive_count": profile_positive_count,
            "candidate_targets": sorted(candidate_targets),
            "candidate_ligands": sorted(candidate_ligands),
            "blocker_count": len(blockers),
            "blockers": blockers,
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "next_required_step": (
                "Candidate scoreability is wired; guarded 100k launch can proceed, but claim promotion remains false."
                if passed
                else "Build a frozen-candidate profile with native, reference, split, target-meta, and ligand-meta coverage before 100k launch."
            ),
        },
        "missing_coverage": missing,
        "claim_boundary": {
            "scoreability_packet_is_not_claim_authorization": True,
            "claim_promotion_allowed": False,
            "router_claim_allowed": False,
            "platform_claim_allowed": False,
            "fake_pass_allowed": False,
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    return "\n".join(
        [
            "# GPCR Frozen Candidate Scoreability",
            "",
            f"- status: `{summary['status']}`",
            f"- pass: `{str(summary['pass']).lower()}`",
            f"- candidate_count: `{summary['candidate_count']}`",
            f"- blockers: `{', '.join(summary['blockers'])}`",
            f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
            "",
            "## Next Step",
            "",
            f"- {summary['next_required_step']}",
            "",
        ]
    )


def write_outputs(
    *,
    freeze_json: str | Path | None,
    profile_json: str | Path | None,
    out_json: str | Path,
    out_md: str | Path,
) -> dict[str, Any]:
    payload = build_packet(freeze_json=freeze_json, profile_json=profile_json)
    out_json_path = _resolve(out_json)
    out_md_path = _resolve(out_md)
    assert out_json_path is not None
    assert out_md_path is not None
    _write_json(out_json_path, payload)
    out_md_path.parent.mkdir(parents=True, exist_ok=True)
    out_md_path.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPCR frozen candidate scoreability packet.")
    parser.add_argument("--freeze-json", default=DEFAULT_FREEZE_JSON)
    parser.add_argument("--profile-json", default=DEFAULT_PROFILE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_outputs(
        freeze_json=args.freeze_json,
        profile_json=args.profile_json,
        out_json=args.out_json,
        out_md=args.out_md,
    )


if __name__ == "__main__":
    main()
