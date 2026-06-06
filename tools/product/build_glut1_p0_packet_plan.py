#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"
CONFIG = ROOT / "config"
TARGET = "GLUT1_TRANSPORT_BLIND"
TARGET_ID = "GLUT1_4PYP"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _rows_by_step(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("packet_step", "")).strip(): dict(row)
        for row in payload.get("workbook_rows", []) or []
        if str(row.get("packet_step", "")).strip()
    }


def build_payload(
    *,
    reference_rows: list[dict[str, str]],
    split_rows: list[dict[str, str]],
    meta_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    target_meta_rows: list[dict[str, str]],
    profile_payload: dict[str, Any],
    workbook_payload: dict[str, Any],
) -> dict[str, Any]:
    ref_rows = [row for row in reference_rows if row.get("target") == TARGET]
    target_ligand_ids = {str(row.get("ligand_id", "")).strip() for row in ref_rows if str(row.get("ligand_id", "")).strip()}
    split_rows = [row for row in split_rows if row.get("target") == TARGET]
    meta_rows = [row for row in meta_rows if str(row.get("ligand_id", "")).strip() in target_ligand_ids]
    target_row = next((row for row in target_rows if row.get("target") == TARGET), {})
    target_meta = next((row for row in target_meta_rows if row.get("target") == TARGET), {})
    workbook_by_step = _rows_by_step(workbook_payload)

    packet_rows: list[dict[str, Any]] = []

    def add(step: str, artifact: str, status: str, blocker: str, next_action: str, repo_path: str, detail: str) -> None:
        packet_rows.append(
            {
                "step_id": step,
                "artifact": artifact,
                "status": status,
                "blocker": blocker,
                "next_action": next_action,
                "repo_path": repo_path,
                "detail": detail,
            }
        )

    pocket_zero = (
        not target_row
        or all(str(target_row.get(key, "")).strip() in {"0", "0.0"} for key in ("pocket_x", "pocket_y", "pocket_z"))
    )
    sequence = str(target_meta.get("sequence", "")).strip()
    sequence_placeholder = not sequence or "TEMPLATE_SEQ" in sequence
    ready_workbook_rows = sum(
        1
        for row in workbook_by_step.values()
        if str(row.get("row_ready_for_apply", "")).strip().lower() == "yes"
    )
    placeholder_ref = sum(1 for row in ref_rows if "placeholder" in row.get("ligand_id", "") or "placeholder" in row.get("source", ""))
    placeholder_split = sum(1 for row in split_rows if "placeholder" in row.get("ligand_id", ""))
    placeholder_meta = sum(1 for row in meta_rows if "template_placeholder" in row.get("scaffold", "") or "placeholder" in row.get("ligand_id", ""))

    add(
        "glut1_target_native",
        "target_native_csv",
        "todo" if pocket_zero else "ready",
        "pocket_centroid_placeholder" if pocket_zero else "",
        "freeze a claim-safe GLUT1 central-cavity pocket centroid before runnable docking promotion",
        "config/real_drug_targets_blind_glut1_4pyp_v1.csv",
        f"pdb_id={target_row.get('pdb_id', '')} native={target_row.get('native_pdb_path', '')}",
    )
    add(
        "glut1_target_meta",
        "target_meta_csv",
        "todo" if sequence_placeholder else "ready",
        "sequence_placeholder" if sequence_placeholder else "",
        "keep 4PYP SEQRES chain A metadata current and preserve state-sensitive pocket fingerprint",
        "config/ligand_target_metadata_blind_glut1_4pyp_v1.csv",
        f"target_family={target_meta.get('target_family', '')} sequence_len={len(sequence)} fingerprint={target_meta.get('pocket_fingerprint', '')}",
    )
    add(
        "glut1_ligand_reference",
        "ligand_reference_csv",
        "todo" if placeholder_ref else "ready",
        "placeholder_ligand_rows" if placeholder_ref else "",
        "promote every synchronized claim-safe GLUT1 ligand reference row before artifact readiness",
        "config/ligand_binding_reference_blind_glut1_4pyp_v1.csv",
        f"row_count={len(ref_rows)} placeholder_rows={placeholder_ref} ready_workbook_rows={ready_workbook_rows}",
    )
    add(
        "glut1_eval_split",
        "eval_split_csv",
        "todo" if placeholder_split else "ready",
        "placeholder_split_roles" if placeholder_split else "",
        "freeze split roles after the full GLUT1 ligand packet is synchronized",
        "config/ligand_eval_splits_blind_glut1_4pyp_v1.csv",
        f"row_count={len(split_rows)} placeholder_rows={placeholder_split} ready_workbook_rows={ready_workbook_rows}",
    )
    add(
        "glut1_ligand_meta",
        "ligand_meta_csv",
        "todo" if placeholder_meta else "ready",
        "placeholder_meta_rows" if placeholder_meta else "",
        "replace placeholder GLUT1 ligand metadata with synchronized curated rows",
        "config/ligand_meta_blind_glut1_4pyp_v1.csv",
        f"row_count={len(meta_rows)} placeholder_rows={placeholder_meta} ready_workbook_rows={ready_workbook_rows}",
    )
    add(
        "glut1_profile_json",
        "profile_json",
        "ready",
        "",
        "keep dry_run until native pocket and ligand packet blockers are closed",
        "config/ligand_htvs_blind_glut1_4pyp_v1.json",
        f"dry_run={profile_payload.get('dry_run')} hard_decoy_fit_targets={profile_payload.get('hard_decoy_fit_targets', '')}",
    )

    p0_artifacts = {"target_native_csv", "target_meta_csv", "ligand_reference_csv", "eval_split_csv", "ligand_meta_csv", "profile_json"}
    summary = {
        "target_id": TARGET_ID,
        "task_id": "glut1_core_full",
        "step_count": len(packet_rows),
        "ready_count": sum(1 for row in packet_rows if row["status"] == "ready"),
        "todo_count": sum(1 for row in packet_rows if row["status"] == "todo"),
        "p0_count": sum(1 for row in packet_rows if row["artifact"] in p0_artifacts),
        "p0_open_count": sum(1 for row in packet_rows if row["artifact"] in p0_artifacts and row["status"] == "todo"),
        "ready_workbook_row_count": ready_workbook_rows,
        "next_priority_steps": [row["step_id"] for row in packet_rows if row["status"] == "todo"][:5],
    }
    return {"summary": summary, "rows": packet_rows}


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GLUT1 P0 Packet Plan",
        "",
        f"- target: `{s['target_id']}`",
        f"- task: `{s['task_id']}`",
        f"- ready: `{s['ready_count']}`",
        f"- todo: `{s['todo_count']}`",
        f"- p0_open_count: `{s['p0_open_count']}`",
        f"- ready_workbook_row_count: `{s['ready_workbook_row_count']}`",
        f"- next_priority_steps: `{', '.join(s['next_priority_steps'])}`",
        "",
        "| step | artifact | status | blocker | detail |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['step_id']}` | `{row['artifact']}` | `{row['status']}` | `{row['blocker'] or '-'}` | {row['detail']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    payload = build_payload(
        reference_rows=_read_csv(CONFIG / "ligand_binding_reference_blind_glut1_4pyp_v1.csv"),
        split_rows=_read_csv(CONFIG / "ligand_eval_splits_blind_glut1_4pyp_v1.csv"),
        meta_rows=_read_csv(CONFIG / "ligand_meta_blind_glut1_4pyp_v1.csv"),
        target_rows=_read_csv(CONFIG / "real_drug_targets_blind_glut1_4pyp_v1.csv"),
        target_meta_rows=_read_csv(CONFIG / "ligand_target_metadata_blind_glut1_4pyp_v1.csv"),
        profile_payload=_load_json(CONFIG / "ligand_htvs_blind_glut1_4pyp_v1.json"),
        workbook_payload=_load_json(RUNS / "glut1_packet_replacement_workbook_current.json"),
    )
    _write_json(RUNS / "glut1_p0_packet_plan_current.json", payload)
    _write_csv(RUNS / "glut1_p0_packet_plan_current.csv", payload["rows"])
    _write_md(RUNS / "glut1_p0_packet_plan_current.md", payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
