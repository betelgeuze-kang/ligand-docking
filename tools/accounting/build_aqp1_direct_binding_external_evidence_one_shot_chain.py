#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGING_CSV = "runs/aqp1_direct_binding_external_evidence_intake_supplement_current.csv"
DEFAULT_LIVE_SUPPLEMENT_CSV = "runs/aqp1_direct_binding_external_evidence_intake_supplement_current.csv"
DEFAULT_OUT_JSON = "runs/aqp1_direct_binding_external_evidence_one_shot_chain_current.json"
DEFAULT_OUT_MD = "runs/aqp1_direct_binding_external_evidence_one_shot_chain_current.md"

CLAIM_BOUNDARY = (
    "AQP1 direct-binding external evidence one-shot chain only; it validates operator supplement rows, "
    "optionally copies them into the live supplement CSV, rebuilds intake/workbook apply artifacts, and "
    "refreshes transporter scope gates. It does not fabricate claim-safe kcal values or mutate external state."
)


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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


_CHILD_ARTIFACT_HINTS: dict[str, str] = {
    "build_aqp1_direct_binding_external_evidence_supplement_example.py": "runs/aqp1_direct_binding_external_evidence_supplement_example_current.json",
    "build_aqp1_direct_binding_external_evidence_operator_staging_apply.py": "runs/aqp1_direct_binding_external_evidence_operator_staging_apply_current.json",
    "build_aqp1_direct_binding_external_evidence_intake.py": "runs/aqp1_direct_binding_external_evidence_intake_current.json",
    "apply_aqp1_ready_workbook_rows.py": "runs/aqp1_ready_workbook_apply_current.json",
    "build_transporter_aqp1_external_evidence_refresh_chain.py": "runs/transporter_aqp1_external_evidence_refresh_chain_current.json",
}


def _run(cmd: list[str]) -> None:
    script_name = Path(cmd[1]).name if len(cmd) > 1 else ""
    artifact_hint = _CHILD_ARTIFACT_HINTS.get(script_name, "")
    subprocess.run(cmd, cwd=str(ROOT), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if artifact_hint:
        print(f"[aqp1_one_shot] wrote {artifact_hint}", file=sys.stderr)


def _lane(name: str, path_like: str | Path) -> dict[str, Any]:
    payload = _read_json(path_like)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    return {
        "lane": name,
        "status": str(summary.get("status") or "").strip(),
        "artifact": str(_resolve(path_like)),
        "summary": summary,
    }


def build_packet(
    *,
    staging_csv: str = DEFAULT_STAGING_CSV,
    live_supplement_csv: str = DEFAULT_LIVE_SUPPLEMENT_CSV,
    apply_live_copy: bool = True,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    lanes: dict[str, dict[str, Any]] = {}
    blockers: list[str] = []

    _run(
        [
            sys.executable,
            "tools/build_aqp1_direct_binding_external_evidence_supplement_example.py",
        ]
    )
    _run(
        [
            sys.executable,
            "tools/build_aqp1_direct_binding_external_evidence_operator_staging_apply.py",
            "--mode",
            "preview",
            "--staging-csv",
            staging_csv,
            "--live-supplement-csv",
            live_supplement_csv,
        ]
    )
    lanes["staging_preview"] = _lane(
        "staging_preview",
        "runs/aqp1_direct_binding_external_evidence_operator_staging_apply_current.json",
    )

    live_cmd = [
        sys.executable,
        "tools/build_aqp1_direct_binding_external_evidence_operator_staging_apply.py",
        "--mode",
        "live_apply",
        "--staging-csv",
        staging_csv,
        "--live-supplement-csv",
        live_supplement_csv,
    ]
    if apply_live_copy:
        live_cmd.append("--apply-live-copy")
    _run(live_cmd)
    lanes["staging_live_apply"] = _lane(
        "staging_live_apply",
        "runs/aqp1_direct_binding_external_evidence_operator_staging_apply_current.json",
    )
    staging_live = lanes["staging_live_apply"]["summary"]
    if not staging_live.get("live_apply_allowed"):
        blockers.append("aqp1_one_shot:staging_live_apply_not_allowed")

    _run([sys.executable, "tools/build_aqp1_direct_binding_external_evidence_intake.py"])
    lanes["intake"] = _lane(
        "intake",
        "runs/aqp1_direct_binding_external_evidence_intake_current.json",
    )
    intake = lanes["intake"]["summary"]
    if int(intake.get("claim_safe_approved_count") or 0) == 0:
        blockers.append("aqp1_one_shot:claim_safe_approved_rows_missing")

    _run([sys.executable, "tools/apply_aqp1_ready_workbook_rows.py"])
    lanes["workbook_apply"] = _lane("workbook_apply", "runs/aqp1_ready_workbook_apply_current.json")

    _run([sys.executable, "tools/build_transporter_aqp1_external_evidence_refresh_chain.py"])
    lanes["transporter_refresh"] = _lane(
        "transporter_refresh",
        "runs/transporter_aqp1_external_evidence_refresh_chain_current.json",
    )
    transporter = lanes["transporter_refresh"]["summary"]
    blockers.extend(str(item) for item in (transporter.get("blockers") or []))

    status = (
        "aqp1_direct_binding_external_evidence_one_shot_chain_ready"
        if not blockers
        else "aqp1_direct_binding_external_evidence_one_shot_chain_refreshed_with_blockers"
    )
    summary = {
        "packet_type": "aqp1_direct_binding_external_evidence_one_shot_chain",
        "status": status,
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "claim_boundary": CLAIM_BOUNDARY,
        "blockers": blockers,
        "staging_csv": str(_resolve(staging_csv)),
        "live_supplement_csv": str(_resolve(live_supplement_csv)),
        "live_apply_allowed": bool(staging_live.get("live_apply_allowed")),
        "live_copy_executed": bool(staging_live.get("live_copy_executed")),
        "claim_safe_approved_count": int(intake.get("claim_safe_approved_count") or 0),
        "aqp1_core_p0_open_count": int(transporter.get("aqp1_core_p0_open_count") or 0),
        "next_required_step": (
            "AQP1 supplement validated, live copy applied, intake/workbook apply refreshed, and transporter scope gates rebuilt."
            if not blockers
            else "Fill validated direct-binding supplement rows without EXAMPLE markers, then rerun this one-shot chain."
        ),
    }
    return {"summary": summary, "lanes": lanes}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    summary = payload["summary"]
    lines = [
        "# AQP1 Direct Binding External Evidence One-Shot Chain",
        "",
        f"- status: `{summary['status']}`",
        f"- claim_safe_approved_count: `{summary['claim_safe_approved_count']}`",
        f"- live_copy_executed: `{summary['live_copy_executed']}`",
        f"- blockers: `{';'.join(summary.get('blockers') or []) or 'none'}`",
        "",
        "## Claim Boundary",
        "",
        summary["claim_boundary"],
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate AQP1 supplement, apply live copy, and refresh transporter scope.")
    parser.add_argument("--staging-csv", default=DEFAULT_STAGING_CSV)
    parser.add_argument("--live-supplement-csv", default=DEFAULT_LIVE_SUPPLEMENT_CSV)
    parser.add_argument("--no-apply-live-copy", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_packet(
        staging_csv=args.staging_csv,
        live_supplement_csv=args.live_supplement_csv,
        apply_live_copy=not args.no_apply_live_copy,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
