#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import shlex
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"

DEFAULT_OUT_JSON = "runs/nightly_stage6_tuning_sweep_packet_current.json"
DEFAULT_OUT_CSV = "runs/nightly_stage6_tuning_sweep_packet_current.csv"
DEFAULT_OUT_MD = "runs/nightly_stage6_tuning_sweep_packet_current.md"
DEFAULT_TUNING_JSON = "runs/nightly_stage6_tuning_packet_current.json"
DEFAULT_FOLLOWUP_JSON = "runs/nightly_stage6_followup_retry_packet_current.json"

_TOP_NIGHTLY_RE = re.compile(r"ligand_htvs_nightly_(\d{4}-\d{2}-\d{2})_summary\.json$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _fmt_float(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def _slug(value: str) -> str:
    lowered = value.strip().lower().replace("::", "__")
    return _SLUG_RE.sub("_", lowered).strip("_") or "row"


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_csv_rows(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _extract_stage_payload(latest_nightly_payload: dict[str, Any], stage_name: str) -> dict[str, Any]:
    stages = dict(latest_nightly_payload.get("stages", {}) or {})
    direct = dict(stages.get(stage_name, {}) or {})
    if direct:
        return direct
    for scope_name in ("smoke", "full"):
        scoped = dict(stages.get(scope_name, {}) or {})
        nested = dict(scoped.get("stages", {}) or {}).get(stage_name, {})
        nested_dict = dict(nested or {})
        if nested_dict:
            return nested_dict
    return {}


def _discover_latest_top_nightly() -> Path | None:
    candidates: list[tuple[str, Path]] = []
    for path in RUNS.glob("ligand_htvs_nightly_*_summary.json"):
        match = _TOP_NIGHTLY_RE.fullmatch(path.name)
        if match:
            candidates.append((match.group(1), path))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0])[-1][1]


def _cmd_tokens(stage2_payload: dict[str, Any]) -> list[str]:
    cmd = list(stage2_payload.get("cmd") or [])
    if cmd:
        return [_text(token) for token in cmd]
    cmd_str = _text(stage2_payload.get("cmd_str"))
    if not cmd_str:
        return []
    return list(shlex.split(cmd_str))


def _option_value(cmd: list[str], option: str) -> str:
    for idx, token in enumerate(cmd):
        if token == option and idx + 1 < len(cmd):
            return _text(cmd[idx + 1])
    return ""


def _extract_scalar_baseline(cmd: list[str]) -> dict[str, Any]:
    return {
        "queue_csv": _option_value(cmd, "--queue-csv"),
        "frames": _int(_option_value(cmd, "--frames")),
        "noise_scale": _float(_option_value(cmd, "--noise-scale")),
        "pocket_attract_base": _float(_option_value(cmd, "--pocket-attract-base")),
        "protein_repulse": _float(_option_value(cmd, "--protein-repulse")),
        "step_size": _float(_option_value(cmd, "--step-size")),
        "seed": _int(_option_value(cmd, "--seed")),
        "out_root": _option_value(cmd, "--out-root"),
    }


def _retuned_cmd(
    baseline_cmd: list[str],
    *,
    subset_queue_csv_artifact: str,
    out_root: str,
    out_manifest_csv: str,
    out_summary_json: str,
    out_summary_md: str,
    out_progress_json: str,
    frames: int,
    noise_scale: float,
    pocket_attract_base: float,
    protein_repulse: float,
    extra_scalar_args: dict[str, str] | None = None,
    extra_bool_flags: list[str] | None = None,
    remove_flags: list[str] | None = None,
) -> list[str]:
    scalar_overrides = {
        "--queue-csv": subset_queue_csv_artifact,
        "--out-root": out_root,
        "--out-manifest-csv": out_manifest_csv,
        "--out-summary-json": out_summary_json,
        "--out-summary-md": out_summary_md,
        "--out-progress-json": out_progress_json,
        "--frames": str(frames),
        "--noise-scale": f"{noise_scale:.3f}",
        "--pocket-attract-base": f"{pocket_attract_base:.3f}",
        "--protein-repulse": f"{protein_repulse:.3f}",
    }
    scalar_overrides.update({k: _text(v) for k, v in dict(extra_scalar_args or {}).items() if _text(k)})
    bool_overrides = {"--resume-existing", "--no-resume-existing"}
    remove_flag_set = {_text(flag) for flag in (remove_flags or []) if _text(flag)}
    rebuilt: list[str] = []
    idx = 0
    while idx < len(baseline_cmd):
        token = _text(baseline_cmd[idx])
        if token in scalar_overrides:
            idx += 2
            continue
        if token in bool_overrides or token in remove_flag_set:
            idx += 1
            continue
        rebuilt.append(token)
        if token.startswith("--") and idx + 1 < len(baseline_cmd) and not str(baseline_cmd[idx + 1]).startswith("--"):
            rebuilt.append(_text(baseline_cmd[idx + 1]))
            idx += 2
            continue
        idx += 1
    rebuilt.append("--no-resume-existing")
    for flag in extra_bool_flags or []:
        if _text(flag):
            rebuilt.append(_text(flag))
    for option, value in scalar_overrides.items():
        rebuilt.extend([option, value])
    return rebuilt


def _preset_specs(
    *,
    target: str,
    culprit_kind: str,
    base_frames: int,
    base_noise_scale: float,
    base_pocket_attract_base: float,
    base_protein_repulse: float,
) -> list[dict[str, Any]]:
    replay = {
        "preset_id": "anchor_replay_baseline",
        "preset_rank": 1,
        "frames": base_frames,
        "noise_scale": base_noise_scale,
        "pocket_attract_base": base_pocket_attract_base,
        "protein_repulse": base_protein_repulse,
        "expected_effect": "Reproduce the current anchor row in isolation before spending more retry budget.",
        "extra_scalar_args": {},
        "extra_bool_flags": [],
        "remove_flags": [],
    }
    target_force_args = {
        "--dynamic-adress-force-targets": target,
        "--dynamic-adress-min-affinity": "0.70",
        "--dynamic-adress-max-protein-residues": "260",
    }
    uncapped_force_args = {
        **target_force_args,
        "--dynamic-adress-max-all-atom-radius-A": "12.0",
        "--dynamic-adress-max-atom-ratio": "0.2",
    }
    if culprit_kind == "binder_recovery":
        return [
            replay,
            {
                "preset_id": "target_forced_adress_uncapped_probe",
                "preset_rank": 2,
                "frames": base_frames,
                "noise_scale": base_noise_scale,
                "pocket_attract_base": base_pocket_attract_base,
                "protein_repulse": base_protein_repulse,
                "expected_effect": f"Replay the successful uncapped ADReSS route for `{target}` without the current core-on-radius cap.",
                "extra_scalar_args": uncapped_force_args,
                "extra_bool_flags": [],
                "remove_flags": ["--dynamic-adress-cap-force-core-on-radius"],
            },
            {
                "preset_id": "target_forced_adress_replay",
                "preset_rank": 3,
                "frames": base_frames,
                "noise_scale": base_noise_scale,
                "pocket_attract_base": base_pocket_attract_base,
                "protein_repulse": base_protein_repulse,
                "expected_effect": f"Force `{target}` through the ADReSS route instead of the current `affinity_low` / fallback lane.",
                "extra_scalar_args": target_force_args,
                "extra_bool_flags": [],
                "remove_flags": [],
            },
            {
                "preset_id": "target_forced_adress_geometry_bias",
                "preset_rank": 4,
                "frames": base_frames + 20,
                "noise_scale": base_noise_scale,
                "pocket_attract_base": base_pocket_attract_base + 0.03,
                "protein_repulse": max(base_protein_repulse - 0.03, 0.05),
                "expected_effect": f"Force `{target}` into ADReSS and add a light geometry bias if the pure route replay still misses the gate.",
                "extra_scalar_args": {
                    **target_force_args,
                    "--dynamic-adress-max-all-atom-radius-A": "9.0",
                },
                "extra_bool_flags": [],
                "remove_flags": [],
            },
        ]
    return [
        replay,
        {
            "preset_id": "target_forced_adress_uncapped_probe",
            "preset_rank": 2,
            "frames": base_frames,
            "noise_scale": base_noise_scale,
            "pocket_attract_base": base_pocket_attract_base,
            "protein_repulse": base_protein_repulse,
            "expected_effect": f"Replay the successful uncapped ADReSS route for `{target}` before falling back to cleanup-only probes.",
            "extra_scalar_args": uncapped_force_args,
            "extra_bool_flags": [],
            "remove_flags": ["--dynamic-adress-cap-force-core-on-radius"],
        },
        {
            "preset_id": "target_forced_adress_consistency_probe",
            "preset_rank": 3,
            "frames": base_frames,
            "noise_scale": base_noise_scale,
            "pocket_attract_base": base_pocket_attract_base,
            "protein_repulse": base_protein_repulse,
            "expected_effect": f"Force `{target}` into ADReSS once to check whether the cleanup row is only being blocked by the current routing gate.",
            "extra_scalar_args": target_force_args,
            "extra_bool_flags": [],
            "remove_flags": [],
        },
        {
            "preset_id": "adress_only_boundary_probe",
            "preset_rank": 4,
            "frames": base_frames + 20,
            "noise_scale": base_noise_scale,
            "pocket_attract_base": base_pocket_attract_base + 0.01,
            "protein_repulse": base_protein_repulse + 0.01,
            "expected_effect": f"Run an `adress_only` boundary probe for `{target}` before promoting the decoy lane to closeout or parking it as unresolved noise.",
            "extra_scalar_args": {
                **target_force_args,
                "--strategy-mode": "adress_only",
            },
            "extra_bool_flags": [],
            "remove_flags": [],
        },
    ]


def _parameter_delta_line(
    *,
    frames: int,
    noise_scale: float,
    pocket_attract_base: float,
    protein_repulse: float,
    base_frames: int,
    base_noise_scale: float,
    base_pocket_attract_base: float,
    base_protein_repulse: float,
) -> str:
    return (
        f"frames {frames} ({frames - base_frames:+d}), "
        f"noise_scale {_fmt_float(noise_scale)} ({noise_scale - base_noise_scale:+.3f}), "
        f"pocket_attract_base {_fmt_float(pocket_attract_base)} ({pocket_attract_base - base_pocket_attract_base:+.3f}), "
        f"protein_repulse {_fmt_float(protein_repulse)} ({protein_repulse - base_protein_repulse:+.3f})"
    )


def build_payload(
    latest_nightly_payload: dict[str, Any],
    latest_nightly_artifact: str,
    tuning_payload: dict[str, Any],
    tuning_artifact: str,
    followup_payload: dict[str, Any],
    followup_artifact: str,
    stage1_queue_rows: list[dict[str, Any]],
    stage1_queue_artifact: str,
) -> dict[str, Any]:
    tuning_summary = dict(tuning_payload.get("summary", {}) or {})
    followup_summary = dict(followup_payload.get("summary", {}) or {})
    followup_rows = list(followup_payload.get("rows", []) or [])
    stage2_payload = _extract_stage_payload(latest_nightly_payload, "stage2_trajectory_generation")
    baseline_cmd = _cmd_tokens(stage2_payload)
    baseline = _extract_scalar_baseline(baseline_cmd)
    base_frames = _int(baseline.get("frames")) or 100
    base_noise_scale = _float(baseline.get("noise_scale"))
    base_pocket_attract_base = _float(baseline.get("pocket_attract_base")) or 0.16
    base_protein_repulse = _float(baseline.get("protein_repulse")) or 0.22
    stage1_by_queue = {
        _text(row.get("queue_id")): dict(row)
        for row in stage1_queue_rows
        if _text(row.get("queue_id"))
    }
    retry_rows = [dict(row) for row in followup_rows if _text(row.get("action_bucket")) == "retry"]
    closure_rows = [dict(row) for row in followup_rows if _text(row.get("action_bucket")) == "closure"]

    rows: list[dict[str, Any]] = []
    retry_subset_artifacts: list[str] = []
    retry_anchor_present_count = 0
    for followup_row in retry_rows:
        row_key = _text(followup_row.get("row_key"))
        row_slug = _slug(row_key)
        culprit_kind = _text(followup_row.get("culprit_kind")) or "retry"
        target = row_key.split("::", 1)[0] if "::" in row_key else _text(followup_row.get("target"))
        retry_anchor_queue_id = _text(followup_row.get("retry_anchor_queue_id"))
        retry_anchor_seed = _text(followup_row.get("retry_anchor_seed"))
        retry_anchor_npz = _text(followup_row.get("retry_anchor_trajectory_npz"))
        subset_queue_csv_artifact = f"runs/nightly_stage6_retry_subset_{row_slug}.csv"
        retry_subset_artifacts.append(subset_queue_csv_artifact)
        retry_anchor_present = retry_anchor_queue_id in stage1_by_queue
        retry_anchor_present_count += int(retry_anchor_present)
        for preset in _preset_specs(
            target=target,
            culprit_kind=culprit_kind,
            base_frames=base_frames,
            base_noise_scale=base_noise_scale,
            base_pocket_attract_base=base_pocket_attract_base,
            base_protein_repulse=base_protein_repulse,
        ):
            preset_id = _text(preset.get("preset_id"))
            out_root = f"runs/nightly_stage6_retry_runs/{row_slug}/{preset_id}"
            out_manifest_csv = f"{out_root}_manifest.csv"
            out_summary_json = f"{out_root}_summary.json"
            out_summary_md = f"{out_root}_summary.md"
            out_progress_json = f"{out_root}_progress.json"
            cmd = _retuned_cmd(
                baseline_cmd,
                subset_queue_csv_artifact=subset_queue_csv_artifact,
                out_root=out_root,
                out_manifest_csv=out_manifest_csv,
                out_summary_json=out_summary_json,
                out_summary_md=out_summary_md,
                out_progress_json=out_progress_json,
                frames=_int(preset.get("frames")),
                noise_scale=_float(preset.get("noise_scale")),
                pocket_attract_base=_float(preset.get("pocket_attract_base")),
                protein_repulse=_float(preset.get("protein_repulse")),
                extra_scalar_args=dict(preset.get("extra_scalar_args") or {}),
                extra_bool_flags=list(preset.get("extra_bool_flags") or []),
                remove_flags=list(preset.get("remove_flags") or []),
            )
            rows.append(
                {
                    "execution_priority_rank": len(rows) + 1,
                    "row_key": row_key,
                    "culprit_kind": culprit_kind,
                    "recommended_action": _text(followup_row.get("recommended_action")),
                    "retry_anchor_queue_id": retry_anchor_queue_id,
                    "retry_anchor_seed": retry_anchor_seed,
                    "retry_anchor_trajectory_npz": retry_anchor_npz,
                    "retry_anchor_present_in_stage1_queue": retry_anchor_present,
                    "subset_queue_csv_artifact": subset_queue_csv_artifact,
                    "preset_id": preset_id,
                    "preset_rank": _int(preset.get("preset_rank")),
                    "frames": _int(preset.get("frames")),
                    "noise_scale": _float(preset.get("noise_scale")),
                    "pocket_attract_base": _float(preset.get("pocket_attract_base")),
                    "protein_repulse": _float(preset.get("protein_repulse")),
                    "parameter_delta_line": _parameter_delta_line(
                        frames=_int(preset.get("frames")),
                        noise_scale=_float(preset.get("noise_scale")),
                        pocket_attract_base=_float(preset.get("pocket_attract_base")),
                        protein_repulse=_float(preset.get("protein_repulse")),
                        base_frames=base_frames,
                        base_noise_scale=base_noise_scale,
                        base_pocket_attract_base=base_pocket_attract_base,
                        base_protein_repulse=base_protein_repulse,
                    ),
                    "expected_effect": _text(preset.get("expected_effect")),
                    "retry_command_str": shlex.join(cmd),
                    "retry_out_root": out_root,
                    "retry_summary_json_artifact": out_summary_json,
                    "retry_summary_md_artifact": out_summary_md,
                    "distance_over_threshold": _float(followup_row.get("distance_over_threshold")),
                }
            )

    unique_subset_artifacts = list(dict.fromkeys(retry_subset_artifacts))
    primary_focus_row_key = _text(rows[0].get("row_key")) if rows else _text(followup_summary.get("primary_retry_row_key"))
    primary_preset_id = _text(rows[0].get("preset_id")) if rows else ""
    primary_subset_queue_csv_artifact = _text(rows[0].get("subset_queue_csv_artifact")) if rows else ""
    closure_line = ", ".join(
        f"{_text(row.get('row_key'))} [{_text(row.get('recommended_action'))}]"
        for row in closure_rows
        if _text(row.get("row_key"))
    )
    status = "nightly_stage6_tuning_sweep_packet_ready" if rows else "nightly_stage6_tuning_sweep_packet_missing"
    status_line = (
        f"built `{len(rows)}` executable retry presets across `{len(retry_rows)}` retry rows; "
        f"`{len(closure_rows)}` closure rows stay out of the rerun band."
        if rows
        else "no retry rows were available to translate into a stage6 tuning sweep."
    )
    next_required_step = (
        f"Write the subset queue csvs from `{stage1_queue_artifact or baseline.get('queue_csv') or '-'}`, "
        f"start with `{primary_preset_id}` for `{primary_focus_row_key}`, and keep `{followup_artifact or DEFAULT_FOLLOWUP_JSON.replace('.json', '.md')}` open "
        "so closure rows stay parked while the retry band is rerun in isolation."
        if rows
        else "Build the nightly followup retry packet first so the tuning sweep has concrete retry rows."
    )
    summary = {
        "packet_ready": bool(rows),
        "packet_artifact": DEFAULT_OUT_MD,
        "status": status,
        "status_line": status_line,
        "nightly_summary_artifact": latest_nightly_artifact,
        "tuning_packet_artifact": tuning_artifact or DEFAULT_TUNING_JSON.replace(".json", ".md"),
        "followup_packet_artifact": followup_artifact or DEFAULT_FOLLOWUP_JSON.replace(".json", ".md"),
        "baseline_queue_csv_artifact": stage1_queue_artifact or _text(baseline.get("queue_csv")),
        "baseline_frames": base_frames,
        "baseline_noise_scale": base_noise_scale,
        "baseline_pocket_attract_base": base_pocket_attract_base,
        "baseline_protein_repulse": base_protein_repulse,
        "baseline_step_size": _float(baseline.get("step_size")),
        "retry_row_count": len(retry_rows),
        "closure_row_count": len(closure_rows),
        "sweep_preset_row_count": len(rows),
        "retry_subset_queue_count": len(unique_subset_artifacts),
        "retry_anchor_present_count": retry_anchor_present_count,
        "primary_focus_row_key": primary_focus_row_key,
        "primary_preset_id": primary_preset_id,
        "primary_subset_queue_csv_artifact": primary_subset_queue_csv_artifact,
        "closure_line": closure_line,
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _write_subset_queue_csvs(
    *,
    stage1_queue_rows: list[dict[str, Any]],
    payload: dict[str, Any],
) -> tuple[int, int]:
    stage1_by_queue = {
        _text(row.get("queue_id")): dict(row)
        for row in stage1_queue_rows
        if _text(row.get("queue_id"))
    }
    grouped: dict[str, dict[str, Any]] = {}
    for row in payload.get("rows", []) or []:
        subset_artifact = _text(row.get("subset_queue_csv_artifact"))
        queue_id = _text(row.get("retry_anchor_queue_id"))
        if subset_artifact and queue_id and subset_artifact not in grouped:
            grouped[subset_artifact] = stage1_by_queue.get(queue_id, {})
    written = 0
    missing = 0
    for artifact, source_row in grouped.items():
        if not source_row:
            missing += 1
            continue
        out_path = _resolve(artifact)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(source_row.keys())
        with out_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(source_row)
        written += 1
    return written, missing


def _markdown(payload: dict[str, Any]) -> str:
    summary = dict(payload.get("summary", {}) or {})
    rows = list(payload.get("rows", []) or [])
    lines = [
        "# Nightly Stage6 Tuning Sweep Packet",
        "",
        f"- packet_ready: `{summary.get('packet_ready', False)}`",
        f"- status: `{summary.get('status') or '-'}`",
        f"- status_line: `{summary.get('status_line') or '-'}`",
        f"- nightly_summary_artifact: `{summary.get('nightly_summary_artifact') or '-'}`",
        f"- tuning_packet_artifact: `{summary.get('tuning_packet_artifact') or '-'}`",
        f"- followup_packet_artifact: `{summary.get('followup_packet_artifact') or '-'}`",
        f"- baseline_queue_csv_artifact: `{summary.get('baseline_queue_csv_artifact') or '-'}`",
        f"- baseline_frames: `{summary.get('baseline_frames')}`",
        f"- baseline_noise_scale: `{_fmt_float(summary.get('baseline_noise_scale'))}`",
        f"- baseline_pocket_attract_base: `{_fmt_float(summary.get('baseline_pocket_attract_base'))}`",
        f"- baseline_protein_repulse: `{_fmt_float(summary.get('baseline_protein_repulse'))}`",
        f"- retry_row_count: `{summary.get('retry_row_count')}`",
        f"- closure_row_count: `{summary.get('closure_row_count')}`",
        f"- sweep_preset_row_count: `{summary.get('sweep_preset_row_count')}`",
        f"- retry_subset_queue_count: `{summary.get('retry_subset_queue_count')}`",
        f"- retry_anchor_present_count: `{summary.get('retry_anchor_present_count')}`",
        f"- primary_focus_row_key: `{summary.get('primary_focus_row_key') or '-'}`",
        f"- primary_preset_id: `{summary.get('primary_preset_id') or '-'}`",
        f"- primary_subset_queue_csv_artifact: `{summary.get('primary_subset_queue_csv_artifact') or '-'}`",
        "",
        "## Next Step",
        "",
        f"- {summary.get('next_required_step') or '-'}",
        "",
        "## Closure Lanes",
        "",
        f"- `{summary.get('closure_line') or '-'}`",
        "",
        "## Retry Sweep",
        "",
        "| order | row_key | preset_id | subset_queue_csv | frames | noise_scale | pocket_attract_base | protein_repulse | anchor_queue_id | expected_effect |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['execution_priority_rank']} | `{row['row_key']}` | `{row['preset_id']}` | "
            f"`{row['subset_queue_csv_artifact']}` | {row['frames']} | {_fmt_float(row['noise_scale'])} | "
            f"{_fmt_float(row['pocket_attract_base'])} | {_fmt_float(row['protein_repulse'])} | "
            f"`{row['retry_anchor_queue_id']}` | {row['expected_effect']} |"
        )
        lines.append(
            f"|  |  |  |  |  |  |  |  |  | `{row['parameter_delta_line']}` |"
        )
        lines.append(
            f"|  |  |  |  |  |  |  |  |  | `{row['retry_command_str']}` |"
        )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the nightly stage6 tuning sweep packet.")
    parser.add_argument("--nightly-summary-json", default="")
    parser.add_argument("--tuning-json", default=DEFAULT_TUNING_JSON)
    parser.add_argument("--followup-json", default=DEFAULT_FOLLOWUP_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    latest_nightly_path = _resolve(args.nightly_summary_json) if args.nightly_summary_json else _discover_latest_top_nightly()
    latest_nightly_payload = _load_json(latest_nightly_path) if latest_nightly_path else {}
    latest_nightly_artifact = (
        str(latest_nightly_path.relative_to(ROOT))
        if latest_nightly_path is not None
        else "runs/ligand_htvs_nightly_latest_summary.json"
    )
    tuning_payload = _load_json(args.tuning_json)
    followup_payload = _load_json(args.followup_json)
    stage2_payload = _extract_stage_payload(latest_nightly_payload, "stage2_trajectory_generation")
    stage1_queue_artifact = _option_value(_cmd_tokens(stage2_payload), "--queue-csv")
    stage1_queue_rows = _load_csv_rows(stage1_queue_artifact) if stage1_queue_artifact else []
    payload = build_payload(
        latest_nightly_payload=latest_nightly_payload,
        latest_nightly_artifact=latest_nightly_artifact,
        tuning_payload=tuning_payload,
        tuning_artifact=_text(dict(tuning_payload.get("summary", {}) or {}).get("packet_artifact")),
        followup_payload=followup_payload,
        followup_artifact=_text(dict(followup_payload.get("summary", {}) or {}).get("packet_artifact")),
        stage1_queue_rows=stage1_queue_rows,
        stage1_queue_artifact=stage1_queue_artifact,
    )
    written_subset_count, missing_subset_count = _write_subset_queue_csvs(
        stage1_queue_rows=stage1_queue_rows,
        payload=payload,
    )
    payload["summary"]["retry_subset_queue_written_count"] = written_subset_count
    payload["summary"]["retry_subset_queue_missing_count"] = missing_subset_count
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    out_md.write_text(_markdown(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
