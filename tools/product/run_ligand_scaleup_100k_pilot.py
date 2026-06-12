#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import shlex
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER_PREFIX = "__REQUIRED__:"


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _resolve_repo_path(raw: str) -> Path:
    path = Path(str(raw))
    if path.is_absolute():
        return path.resolve()
    return (ROOT / path).resolve()


def _slug(text: str) -> str:
    out: List[str] = []
    for ch in str(text):
        if ch.isalnum() or ch in {"-", "_"}:
            out.append(ch)
        else:
            out.append("_")
    return "".join(out).strip("_") or "x"


def _parse_csv_list(spec: str) -> List[str]:
    return [tok.strip() for tok in str(spec or "").split(",") if tok.strip()]


def _is_placeholder(raw: Any) -> bool:
    return str(raw or "").strip().startswith(PLACEHOLDER_PREFIX)


def _count_csv_rows(path: Path) -> Optional[int]:
    if not path.exists() or not path.is_file():
        return None
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            next(reader)
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _safe_float(v: Any) -> Optional[float]:
    if isinstance(v, (int, float)):
        fv = float(v)
        if math.isnan(fv) or math.isinf(fv):
            return None
        return fv
    return None


def _fmt_float(v: Any, digits: int = 3) -> str:
    fv = _safe_float(v)
    if fv is None:
        return ""
    return f"{fv:.{digits}f}"


def _build_task_paths(bundle_root: Path, task_id: str) -> Dict[str, Path]:
    task_slug = _slug(task_id)
    task_root = bundle_root / "tasks" / task_slug
    return {
        "task_root": task_root,
        "regression_profile": task_root / "regression_profile.json",
        "throughput_profile": task_root / "throughput_profile.json",
        "regression_out_prefix": task_root / "regression_run",
        "throughput_out_prefix": task_root / "throughput_run",
    }


def _normalize_task(spec_path: Path, task: Mapping[str, Any]) -> Dict[str, Any]:
    task_id = str(task.get("task_id", "")).strip()
    if not task_id:
        raise ValueError(f"task missing task_id in {spec_path}")
    profile_json = str(task.get("profile_json", "")).strip()
    if not profile_json:
        raise ValueError(f"task missing profile_json: {task_id}")
    return {
        "task_id": task_id,
        "domain": str(task.get("domain", "")).strip(),
        "profile_json": profile_json,
        "targets": str(task.get("targets", "")).strip(),
        "pilot_ligand_csv": str(task.get("pilot_ligand_csv", "")).strip(),
        "pilot_ligand_min_rows": int(task.get("pilot_ligand_min_rows", 0) or 0),
        "notes": str(task.get("notes", "")).strip(),
        "shared_overrides": dict(task.get("shared_overrides", {}) or {}),
        "regression_overrides": dict(task.get("regression_overrides", {}) or {}),
        "throughput_overrides": dict(task.get("throughput_overrides", {}) or {}),
    }


def _load_spec(spec_path: Path) -> Dict[str, Any]:
    spec = _read_json(spec_path)
    if not isinstance(spec.get("tasks"), list) or not spec["tasks"]:
        raise ValueError(f"spec missing tasks: {spec_path}")
    return spec


def _build_runner_cmd(profile_json: Path, out_prefix: Path, dry_run: bool) -> List[str]:
    return [
        "python3",
        "tools/product/run_ligand_htvs_nightly.py",
        "--profile-json",
        str(profile_json),
        "--run-scope",
        "full",
        "--out-prefix",
        str(out_prefix),
        "--dry-run" if dry_run else "--no-dry-run",
    ]


def _build_script(path: Path, title: str, lines: Iterable[str]) -> None:
    body = [ln for ln in lines if ln]
    text = "#!/usr/bin/env bash\nset -euo pipefail\n\n"
    text += f"# {title}\n\n"
    if body:
        text += "\n".join(body).rstrip() + "\n"
    else:
        text += "# No commands emitted.\n"
    _write_text(path, text)
    path.chmod(0o755)


def _throughput_rows_ready(pilot_ligand_csv: str, required_rows: int) -> Tuple[bool, Optional[int], List[str]]:
    missing: List[str] = []
    src = str(pilot_ligand_csv or "").strip()
    if not src:
        missing.append("pilot_ligand_csv")
        return False, None, missing
    if _is_placeholder(src):
        missing.append("pilot_ligand_csv")
        return False, None, missing
    path = _resolve_repo_path(src)
    if not path.exists():
        missing.append("pilot_ligand_csv")
        return False, None, missing
    rows = _count_csv_rows(path)
    if rows is None:
        missing.append("pilot_ligand_csv")
        return False, None, missing
    if required_rows > 0 and rows < required_rows:
        missing.append(f"pilot_ligand_rows<{required_rows}")
    return len(missing) == 0, rows, missing


def _profile_targets(task: Mapping[str, Any], profile: Mapping[str, Any]) -> str:
    explicit = str(task.get("targets", "")).strip()
    if explicit:
        return explicit
    return str(profile.get("targets", "")).strip()


def _derive_throughput_profile(
    *,
    base_profile: Mapping[str, Any],
    spec: Mapping[str, Any],
    task: Mapping[str, Any],
    target_library_size: int,
) -> Dict[str, Any]:
    merged = _deep_merge(base_profile, dict(spec.get("production_speedpack_overrides", {}) or {}))
    merged = _deep_merge(merged, dict(spec.get("throughput_profile_overrides", {}) or {}))
    merged = _deep_merge(merged, dict(task.get("shared_overrides", {}) or {}))
    merged = _deep_merge(merged, dict(task.get("throughput_overrides", {}) or {}))
    merged["run_scope"] = "full"

    full_cfg = dict(merged.get("full", {}) or {})
    targets = _parse_csv_list(_profile_targets(task, merged))
    target_count = max(1, len(targets))
    jobs_per_target = int(full_cfg.get("jobs_per_target", 0) or 0)
    if jobs_per_target <= 0:
        jobs_per_target = int(math.ceil(float(target_library_size) / float(target_count)))
    full_cfg["max_ligands"] = int(target_library_size)
    full_cfg["replicas"] = int(target_library_size)
    full_cfg["jobs_per_target"] = int(jobs_per_target)
    merged["full"] = full_cfg

    merged["build_hard_decoy_benchmark"] = False
    merged["version"] = f"{base_profile.get('version', _slug(task['task_id']))}_pilot100k_throughput"
    merged["description"] = (
        f"{base_profile.get('description', '').strip()} "
        "[100k pilot throughput profile; production speedpack, no ranking/calibration.]"
    ).strip()
    merged["ligand_csv"] = str(task.get("pilot_ligand_csv", "")).strip() or f"{PLACEHOLDER_PREFIX}pilot_ligand_csv"
    merged["targets"] = _profile_targets(task, merged)
    return merged


def _derive_regression_profile(
    *,
    base_profile: Mapping[str, Any],
    spec: Mapping[str, Any],
    task: Mapping[str, Any],
) -> Dict[str, Any]:
    merged = _deep_merge(base_profile, dict(spec.get("production_speedpack_overrides", {}) or {}))
    merged = _deep_merge(merged, dict(spec.get("regression_profile_overrides", {}) or {}))
    merged = _deep_merge(merged, dict(task.get("shared_overrides", {}) or {}))
    merged = _deep_merge(merged, dict(task.get("regression_overrides", {}) or {}))
    merged["run_scope"] = "full"
    merged["version"] = f"{base_profile.get('version', _slug(task['task_id']))}_pilot100k_regression"
    merged["description"] = (
        f"{base_profile.get('description', '').strip()} "
        "[Frozen regression rerun with production speedpack enabled.]"
    ).strip()
    merged["targets"] = _profile_targets(task, merged)
    return merged


def _task_summary_row(
    *,
    task: Mapping[str, Any],
    base_profile_path: Path,
    regression_profile_path: Path,
    throughput_profile_path: Path,
    pilot_row_count: Optional[int],
    throughput_ready: bool,
    throughput_missing: List[str],
) -> Dict[str, Any]:
    return {
        "task_id": str(task.get("task_id", "")),
        "domain": str(task.get("domain", "")),
        "targets": str(task.get("targets", "")),
        "profile_json": str(base_profile_path),
        "regression_profile_json": str(regression_profile_path),
        "throughput_profile_json": str(throughput_profile_path),
        "pilot_ligand_csv": str(task.get("pilot_ligand_csv", "")),
        "pilot_ligand_rows": int(pilot_row_count) if isinstance(pilot_row_count, int) else "",
        "throughput_execute_ready": bool(throughput_ready),
        "throughput_missing_inputs": ",".join(str(x) for x in throughput_missing),
        "notes": str(task.get("notes", "")),
    }


def _build_markdown(summary: Mapping[str, Any], task_rows: List[Mapping[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("# Ligand Scale-Up 100k Pilot")
    lines.append("")
    lines.append(f"- protocol_id: `{summary.get('protocol_id', '')}`")
    lines.append(f"- target_library_size: `{summary.get('target_library_size', 0)}`")
    lines.append(f"- baseline_library_size: `{summary.get('baseline_library_size', 0)}`")
    lines.append(f"- generated_at_local: `{summary.get('generated_at_local', '')}`")
    lines.append(f"- bundle_root: `{summary.get('bundle_root', '')}`")
    lines.append(f"- regression_task_count: `{summary.get('regression_task_count', 0)}`")
    lines.append(f"- throughput_ready_task_count: `{summary.get('throughput_ready_task_count', 0)}`")
    lines.append("")
    lines.append("## Frozen Refs")
    lines.append("")
    for key, value in sorted((summary.get("baseline_refs") or {}).items()):
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## Guardrails")
    lines.append("")
    for key, value in sorted((summary.get("guardrails") or {}).items()):
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## Tasks")
    lines.append("")
    lines.append("| task | domain | regression | throughput ready | pilot csv | pilot rows | notes |")
    lines.append("| --- | --- | ---: | ---: | --- | ---: | --- |")
    for row in task_rows:
        lines.append(
            "| {task_id} | {domain} | yes | {ready} | {pilot_ligand_csv} | {pilot_ligand_rows} | {notes} |".format(
                task_id=row.get("task_id", ""),
                domain=row.get("domain", ""),
                ready="yes" if bool(row.get("throughput_execute_ready", False)) else "no",
                pilot_ligand_csv=row.get("pilot_ligand_csv", ""),
                pilot_ligand_rows=row.get("pilot_ligand_rows", ""),
                notes=row.get("notes", "") or row.get("throughput_missing_inputs", ""),
            )
        )
    lines.append("")
    lines.append("## Commands")
    lines.append("")
    commands = summary.get("command_scripts") or {}
    for key, value in sorted(commands.items()):
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines) + "\n"


def build_bundle(args: argparse.Namespace) -> Dict[str, Any]:
    spec_path = _resolve_repo_path(str(args.spec_json))
    spec = _load_spec(spec_path)
    target_library_size = int(spec.get("target_library_size", 100000))
    baseline_library_size = int(spec.get("baseline_library_size", 10000))
    label = str(args.label).strip() or dt.date.today().isoformat()
    bundle_root = _resolve_repo_path(str(args.out_root)) / f"ligand_scaleup_100k_pilot_{_slug(label)}"
    bundle_root.mkdir(parents=True, exist_ok=True)
    selected = set(_parse_csv_list(str(args.task_filter))) if str(args.task_filter or "").strip() else None

    task_rows: List[Dict[str, Any]] = []
    summary_tasks: List[Dict[str, Any]] = []
    regression_validate_lines: List[str] = []
    regression_run_lines: List[str] = []
    throughput_validate_lines: List[str] = []
    throughput_run_lines: List[str] = []
    all_ready_run_lines: List[str] = []

    for raw_task in spec.get("tasks", []):
        task = _normalize_task(spec_path, raw_task)
        if selected is not None and task["task_id"] not in selected:
            continue
        base_profile_path = _resolve_repo_path(task["profile_json"])
        if not base_profile_path.exists():
            raise FileNotFoundError(f"profile json not found for {task['task_id']}: {base_profile_path}")
        base_profile = _read_json(base_profile_path)
        task["targets"] = _profile_targets(task, base_profile)
        if not task["domain"]:
            task["domain"] = str(base_profile.get("domain", "")).strip()

        paths = _build_task_paths(bundle_root, task["task_id"])
        regression_profile = _derive_regression_profile(base_profile=base_profile, spec=spec, task=task)
        throughput_profile = _derive_throughput_profile(
            base_profile=base_profile,
            spec=spec,
            task=task,
            target_library_size=target_library_size,
        )
        _write_json(paths["regression_profile"], regression_profile)
        _write_json(paths["throughput_profile"], throughput_profile)

        pilot_required_rows = int(task.get("pilot_ligand_min_rows", 0) or target_library_size)
        throughput_ready, pilot_row_count, throughput_missing = _throughput_rows_ready(
            str(task.get("pilot_ligand_csv", "")),
            pilot_required_rows,
        )

        regression_validate_cmd = _build_runner_cmd(paths["regression_profile"], paths["regression_out_prefix"], True)
        regression_run_cmd = _build_runner_cmd(paths["regression_profile"], paths["regression_out_prefix"], False)
        throughput_validate_cmd = _build_runner_cmd(paths["throughput_profile"], paths["throughput_out_prefix"], True)
        throughput_run_cmd = _build_runner_cmd(paths["throughput_profile"], paths["throughput_out_prefix"], False)

        regression_validate_lines.append(shlex.join(regression_validate_cmd))
        regression_run_lines.append(shlex.join(regression_run_cmd))
        throughput_validate_lines.append(shlex.join(throughput_validate_cmd))
        if throughput_ready:
            run_line = shlex.join(throughput_run_cmd)
            throughput_run_lines.append(run_line)
            all_ready_run_lines.append(run_line)
        else:
            throughput_run_lines.append(
                f"# {task['task_id']}: not execute-ready ({', '.join(throughput_missing) or 'missing inputs'})"
            )

        all_ready_run_lines.append(shlex.join(regression_run_cmd))

        task_row = _task_summary_row(
            task=task,
            base_profile_path=base_profile_path,
            regression_profile_path=paths["regression_profile"],
            throughput_profile_path=paths["throughput_profile"],
            pilot_row_count=pilot_row_count,
            throughput_ready=throughput_ready,
            throughput_missing=throughput_missing,
        )
        task_rows.append(task_row)
        summary_tasks.append(
            {
                **task_row,
                "regression_validate_cmd": regression_validate_cmd,
                "regression_run_cmd": regression_run_cmd,
                "throughput_validate_cmd": throughput_validate_cmd,
                "throughput_run_cmd": throughput_run_cmd,
                "pilot_ligand_min_rows": int(pilot_required_rows),
            }
        )

    task_rows.sort(key=lambda row: str(row["task_id"]))
    summary_tasks.sort(key=lambda row: str(row["task_id"]))

    commands_dir = bundle_root / "commands"
    task_csv = bundle_root / "task_matrix.csv"
    summary_json = bundle_root / "summary.json"
    summary_md = bundle_root / "summary.md"
    validate_regression_sh = commands_dir / "validate_regression.sh"
    run_regression_sh = commands_dir / "run_regression.sh"
    validate_throughput_sh = commands_dir / "validate_throughput.sh"
    run_throughput_sh = commands_dir / "run_throughput_ready.sh"
    run_all_ready_sh = commands_dir / "run_all_ready.sh"

    _build_script(validate_regression_sh, "Validate frozen regression reruns.", regression_validate_lines)
    _build_script(run_regression_sh, "Run frozen regression reruns.", regression_run_lines)
    _build_script(validate_throughput_sh, "Validate 100k throughput profiles.", throughput_validate_lines)
    _build_script(run_throughput_sh, "Run throughput-ready 100k pilot tasks.", throughput_run_lines)
    _build_script(run_all_ready_sh, "Run all ready regression and throughput tasks.", all_ready_run_lines)

    task_csv.parent.mkdir(parents=True, exist_ok=True)
    with task_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "task_id",
                "domain",
                "targets",
                "profile_json",
                "regression_profile_json",
                "throughput_profile_json",
                "pilot_ligand_csv",
                "pilot_ligand_rows",
                "throughput_execute_ready",
                "throughput_missing_inputs",
                "notes",
            ],
        )
        writer.writeheader()
        for row in task_rows:
            writer.writerow(row)

    summary = {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "protocol_id": str(spec.get("protocol_id", "")),
        "description": str(spec.get("description", "")),
        "spec_json": str(spec_path),
        "bundle_root": str(bundle_root),
        "baseline_library_size": int(baseline_library_size),
        "target_library_size": int(target_library_size),
        "baseline_refs": dict(spec.get("baseline_refs", {}) or {}),
        "guardrails": dict(spec.get("guardrails", {}) or {}),
        "regression_task_count": int(len(summary_tasks)),
        "throughput_ready_task_count": int(sum(1 for row in summary_tasks if bool(row["throughput_execute_ready"]))),
        "task_matrix_csv": str(task_csv),
        "command_scripts": {
            "validate_regression_sh": str(validate_regression_sh),
            "run_regression_sh": str(run_regression_sh),
            "validate_throughput_sh": str(validate_throughput_sh),
            "run_throughput_ready_sh": str(run_throughput_sh),
            "run_all_ready_sh": str(run_all_ready_sh),
        },
        "tasks": summary_tasks,
    }
    _write_json(summary_json, summary)
    _write_text(summary_md, _build_markdown(summary, task_rows))
    print(
        json.dumps(
            {
                "ok": True,
                "summary_json": str(summary_json),
                "summary_md": str(summary_md),
                "task_count": len(summary_tasks),
                "throughput_ready_task_count": summary["throughput_ready_task_count"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return {
        "summary_json": str(summary_json),
        "summary_md": str(summary_md),
        "task_count": len(summary_tasks),
        "throughput_ready_task_count": summary["throughput_ready_task_count"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a validate-only 100k ligand scale-up pilot bundle with production speedpack profiles."
    )
    parser.add_argument("--spec-json", type=str, default="config/ligand_scaleup_100k_pilot_v1.json")
    parser.add_argument("--out-root", type=str, default="runs")
    parser.add_argument("--label", type=str, default="current")
    parser.add_argument("--task-filter", type=str, default="")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    build_bundle(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
