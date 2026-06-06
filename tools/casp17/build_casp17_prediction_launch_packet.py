#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import importlib.util
import json
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_WORK_QUEUE_JSON = "runs/casp17_target_work_queue_current.json"
DEFAULT_INTAKE_CSV = "runs/casp17_target_intake_seed_with_sequences_current.csv"
DEFAULT_SEQUENCE_PACKET_JSON = "runs/casp17_sequence_packet_current.json"
DEFAULT_PREDICTION_IMPORT_JSON = "runs/casp17_prediction_import_packet_current.json"
DEFAULT_BACKEND_READINESS_JSON = "runs/casp17_backend_readiness_packet_current.json"
DEFAULT_BACKEND_PROVISIONING_JSON = "runs/casp17_backend_provisioning_plan_current.json"
DEFAULT_PREDICTION_DIR = "runs/casp17_predictions_current"
DEFAULT_JOB_DIR = "runs/casp17_prediction_jobs_current"
DEFAULT_OUT_JSON = "runs/casp17_prediction_launch_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_prediction_launch_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_prediction_launch_packet_current.md"

ELIGIBLE_ACTIONS = {
    "first_internal_attempt",
    "primary_lane_attempt_when_prediction_ready",
}
SECOND_WAVE_ACTIONS = {"second_wave_complex_attempt"}
TARGET_SCOPES = {"eligible", "all_protein", "protein_monomer_homomer", "protein_complex"}
BACKEND_MODES = {"auto", "custom", "internal_physics"}
BACKEND_EXECUTABLES = ("colabfold_batch", "omegafold", "esm-fold", "esmfold")
PYTHON_BACKEND_MODULES = ("esm", "transformers", "colabfold", "openfold", "omegafold", "boltz", "chai_lab", "jax", "haiku")
MONOMER_ONLY_BACKENDS = {"omegafold", "esm-fold", "esmfold"}


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


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "target_kind",
        "recommended_action",
        "work_priority",
        "sequence_path",
        "fasta_entry_count",
        "fasta_residue_count",
        "launch_status",
        "recommended_backend",
        "command",
        "contract_command",
        "conversion_command",
        "expected_prediction_path",
        "blockers",
        "next_required_step",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _run_text_command(command: list[str], timeout_seconds: int = 3) -> tuple[bool, str]:
    try:
        run = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - probe only.
        return False, f"{type(exc).__name__}: {exc}"
    text = (run.stdout or run.stderr or "").strip()
    return run.returncode == 0, text


def _gpu_probe() -> dict[str, Any]:
    torch_cuda = {"torch_present": False, "cuda_available": False, "device_count": 0, "device_names": []}
    try:
        import torch  # type: ignore

        device_count = int(torch.cuda.device_count()) if torch.cuda.is_available() else 0
        torch_cuda = {
            "torch_present": True,
            "cuda_available": bool(torch.cuda.is_available()),
            "device_count": device_count,
            "device_names": [str(torch.cuda.get_device_name(index)) for index in range(device_count)],
        }
    except Exception as exc:  # noqa: BLE001 - optional runtime probe only.
        torch_cuda = {"torch_present": False, "cuda_available": False, "device_count": 0, "device_names": [], "error": str(exc)[:200]}
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return {
            "nvidia_smi_present": False,
            "gpu_detected": bool(torch_cuda["cuda_available"]),
            "gpu_names": list(torch_cuda.get("device_names", [])),
            "torch_cuda": torch_cuda,
        }
    ok, text = _run_text_command([nvidia_smi, "--query-gpu=name", "--format=csv,noheader"], timeout_seconds=4)
    names = [line.strip() for line in text.splitlines() if line.strip()] if ok else []
    return {
        "nvidia_smi_present": True,
        "gpu_detected": bool(names) or bool(torch_cuda["cuda_available"]),
        "gpu_names": names or list(torch_cuda.get("device_names", [])),
        "probe_output": text[:500],
        "torch_cuda": torch_cuda,
    }


def _backend_inventory(
    custom_backend_command: str = "",
    *,
    backend_mode: str = "auto",
    disable_auto_detection: bool = False,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    mode = _text(backend_mode).lower() or "auto"
    if mode == "internal_physics":
        entries.append(
            {
                "backend": "internal_physics",
                "executable": "tools/run_casp17_internal_physics_baseline_predictor.py",
                "path": "tools/run_casp17_internal_physics_baseline_predictor.py",
                "available": True,
                "launch_contract": "repo_internal_torch_coarse_grain_physics",
            }
        )
    for executable in BACKEND_EXECUTABLES:
        path = "" if disable_auto_detection else shutil.which(executable)
        entries.append(
            {
                "backend": executable,
                "executable": executable,
                "path": path or "",
                "available": bool(path),
                "launch_contract": "review_command_before_external_run" if executable != "colabfold_batch" else "known_batch_fasta_outdir",
            }
        )
    if _text(custom_backend_command):
        entries.append(
            {
                "backend": "custom",
                "executable": "custom_template",
                "path": "",
                "available": True,
                "launch_contract": "user_supplied_template",
            }
        )
    priority = (
        ("internal_physics",)
        if mode == "internal_physics"
        else ("custom",) if mode == "custom"
        else ("custom", "colabfold_batch", "omegafold", "esm-fold", "esmfold")
    )
    available = {entry["backend"]: entry for entry in entries if entry["available"]}
    selected = next((name for name in priority if name in available), "")
    return {
        "entries": entries,
        "backend_mode": mode,
        "python_modules": {
            module: False if disable_auto_detection else bool(importlib.util.find_spec(module))
            for module in PYTHON_BACKEND_MODULES
        },
        "selected_backend": selected,
        "selected_backend_available": bool(selected),
        "gpu": _gpu_probe(),
    }


def _sequence_index(sequence_packet: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = sequence_packet.get("rows")
    if not isinstance(rows, list):
        return {}
    return {_text(row.get("target_id")): row for row in rows if isinstance(row, dict)}


def _import_index(prediction_import: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = prediction_import.get("rows")
    if not isinstance(rows, list):
        return {}
    return {_text(row.get("target_id")): row for row in rows if isinstance(row, dict)}


def _work_queue_index(work_queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = work_queue.get("rows")
    if not isinstance(rows, list):
        return {}
    return {_text(row.get("target_id")).upper(): row for row in rows if isinstance(row, dict) and _text(row.get("target_id"))}


def _fasta_stats(path_like: str | Path) -> dict[str, int]:
    path = _resolve(path_like)
    entries = 0
    residues = 0
    if not path.exists():
        return {"entry_count": 0, "residue_count": 0}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            entries += 1
            continue
        residues += sum(1 for char in stripped if char.isalpha() or char in {"*", ".", "-"})
    return {"entry_count": entries, "residue_count": residues}


def _target_kind(target_id: str, sequence_path: str, stoichiometry: str = "") -> str:
    target_id = target_id.upper()
    stats = _fasta_stats(sequence_path) if sequence_path else {"entry_count": 0, "residue_count": 0}
    stoich = _text(stoichiometry).upper()
    if target_id.startswith("H") or (stats["entry_count"] > 1 and target_id.startswith("T")):
        return "protein_complex"
    if target_id.startswith("T"):
        return "protein_monomer_homomer"
    if target_id.startswith("M"):
        return "hybrid_complex"
    return "non_protein_or_unknown"


def _protein_scope_match(target_id: str, target_kind: str, scope: str) -> bool:
    target_id = target_id.upper()
    if scope == "all_protein":
        return target_id.startswith(("T", "H"))
    if scope == "protein_monomer_homomer":
        return target_kind == "protein_monomer_homomer"
    if scope == "protein_complex":
        return target_kind == "protein_complex"
    return False


def _days_until_due(row: dict[str, Any]) -> int:
    due_date = _text(row.get("due_date") or row.get("human_expiration") or row.get("expiration"))
    if not due_date:
        return 999
    try:
        due = dt.date.fromisoformat(due_date[:10])
    except ValueError:
        return 999
    today = dt.datetime.now().astimezone().date()
    return (due - today).days


def _released_protein_rows(work_queue: dict[str, Any], intake_csv: str | Path, *, target_scope: str, target_limit: int) -> list[dict[str, Any]]:
    work_by_target = _work_queue_index(work_queue)
    rows: list[dict[str, Any]] = []
    for intake_row in _read_csv(intake_csv):
        target_id = _text(intake_row.get("target_id")).upper()
        if not target_id:
            continue
        sequence_path = _text(intake_row.get("sequence_path"))
        target_kind = _target_kind(target_id, sequence_path, _text(intake_row.get("stoichiometry")))
        if not _protein_scope_match(target_id, target_kind, target_scope):
            continue
        work_row = work_by_target.get(target_id, {})
        merged = {**intake_row, **work_row}
        merged["target_id"] = target_id
        merged["target_kind"] = target_kind
        merged["sequence_path"] = sequence_path or _text(work_row.get("sequence_path"))
        merged["recommended_action"] = _text(work_row.get("recommended_action")) or "released_protein_prediction"
        merged["work_priority"] = _int(work_row.get("work_priority"), 100)
        merged["days_to_human_expiration"] = _int(work_row.get("days_to_human_expiration"), _days_until_due(merged))
        rows.append(merged)
    rows.sort(key=lambda row: (_text(row.get("due_date")) or "9999-12-31", _text(row.get("target_id"))))
    return rows[:target_limit] if target_limit > 0 else rows


def _shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)


def _command_for_backend(
    *,
    backend: str,
    backend_entries: list[dict[str, Any]],
    target_id: str,
    fasta: str,
    out_dir: str,
    raw_pdb: str,
    runtime_json: str,
    custom_backend_command: str,
    internal_quality_preset: str,
    internal_ensemble_size: int,
    internal_steps: int,
    internal_emit_backbone_atoms: bool,
) -> str:
    if backend == "internal_physics":
        metrics_json = _artifact(_resolve(out_dir) / "internal_physics_metrics.json")
        out_json = _artifact(_resolve(out_dir) / "internal_physics_predictor.json")
        out_csv = _artifact(_resolve(out_dir) / "internal_physics_predictor.csv")
        out_md = _artifact(_resolve(out_dir) / "internal_physics_predictor.md")
        command = [
            "python3",
            "tools/run_casp17_internal_physics_baseline_predictor.py",
            "--target-id",
            target_id,
            "--fasta",
            fasta,
            "--out-dir",
            out_dir,
            "--raw-pdb",
            raw_pdb,
            "--runtime-json",
            runtime_json,
            "--metrics-json",
            metrics_json,
            "--device",
            "auto",
            "--quality-preset",
            internal_quality_preset,
            "--out-json",
            out_json,
            "--out-csv",
            out_csv,
            "--out-md",
            out_md,
        ]
        if int(internal_ensemble_size) > 0:
            command.extend(["--ensemble-size", str(int(internal_ensemble_size))])
        if int(internal_steps) > 0:
            command.extend(["--steps", str(int(internal_steps))])
        if internal_emit_backbone_atoms:
            command.append("--emit-backbone-atoms")
        return _shell_join(command)
    if backend == "custom":
        return _shell_join(
            [
                "python3",
                "tools/run_casp17_custom_backend_job.py",
                "--target-id",
                target_id,
                "--sequence-path",
                fasta,
                "--out-dir",
                out_dir,
                "--raw-pdb",
                raw_pdb,
                "--runtime-json",
                runtime_json,
                "--require-gpu",
                "--command-template",
                custom_backend_command,
            ]
        )
    entry = next((entry for entry in backend_entries if entry.get("backend") == backend), {})
    executable = _text(entry.get("path") or entry.get("executable"))
    if backend == "colabfold_batch":
        return _shell_join([executable, fasta, out_dir])
    if backend in {"omegafold", "esm-fold", "esmfold"}:
        return _shell_join([executable, fasta, out_dir])
    return ""


def _conversion_command(target_id: str, sequence_path: str, expected_raw_pdb: str, expected_prediction_path: str) -> str:
    return _shell_join(
        [
            "python3",
            "tools/convert_casp17_ts_prediction_from_pdb.py",
            "--target-id",
            target_id,
            "--input-pdb",
            expected_raw_pdb,
            "--sequence-path",
            sequence_path,
            "--author-code",
            "<CASP_AUTHOR_CODE>",
            "--out-pdb",
            expected_prediction_path,
        ]
    )


def _contract_command(target_id: str, sequence_path: str, expected_raw_pdb: str, runtime_json: str, backend_kind: str) -> str:
    return _shell_join(
        [
            "python3",
            "tools/validate_casp17_backend_contract.py",
            "--target-id",
            target_id,
            "--sequence-path",
            sequence_path,
            "--raw-pdb",
            expected_raw_pdb,
            "--runtime-json",
            runtime_json,
            "--backend-kind",
            backend_kind,
            "--require-gpu",
        ]
    )


def _eligible_rows(work_queue: dict[str, Any], *, include_second_wave: bool, target_limit: int) -> list[dict[str, Any]]:
    rows = work_queue.get("rows")
    if not isinstance(rows, list):
        return []
    eligible_actions = set(ELIGIBLE_ACTIONS)
    if include_second_wave:
        eligible_actions.update(SECOND_WAVE_ACTIONS)
    selected = [
        row
        for row in rows
        if isinstance(row, dict)
        and _text(row.get("recommended_action")) in eligible_actions
        and _text(row.get("submission_decision")) != "submission_go"
    ]
    selected.sort(key=lambda row: (-_int(row.get("work_priority")), _int(row.get("days_to_human_expiration"), 999), _text(row.get("target_id"))))
    return selected[:target_limit] if target_limit > 0 else selected


def _selected_rows(work_queue: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.target_scope == "eligible":
        return _eligible_rows(work_queue, include_second_wave=args.include_second_wave, target_limit=args.target_limit)
    return _released_protein_rows(
        work_queue,
        args.intake_csv,
        target_scope=args.target_scope,
        target_limit=args.target_limit,
    )


def _launch_row(
    row: dict[str, Any],
    *,
    sequence_by_target: dict[str, dict[str, Any]],
    import_by_target: dict[str, dict[str, Any]],
    inventory: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    target_id = _text(row.get("target_id"))
    sequence_row = sequence_by_target.get(target_id, {})
    import_row = import_by_target.get(target_id, {})
    sequence_path = _text(sequence_row.get("sequence_path") or row.get("sequence_path"))
    expected_prediction_path = _artifact(_resolve(args.prediction_dir) / f"{target_id}TS.pdb")
    job_dir = _artifact(_resolve(args.job_dir) / target_id)
    expected_raw_pdb = _artifact(_resolve(args.job_dir) / target_id / f"{target_id}_model_1.pdb")
    runtime_json = _artifact(_resolve(args.job_dir) / target_id / "backend_runtime.json")
    fasta_stats = _fasta_stats(sequence_path) if sequence_path else {"entry_count": 0, "residue_count": 0}
    target_kind = _text(row.get("target_kind")) or _target_kind(target_id, sequence_path, _text(row.get("stoichiometry")))
    blockers: list[str] = []

    if _text(import_row.get("prediction_import_status")) in {"imported", "existing_ready"}:
        return {
            "target_id": target_id,
            "recommended_action": _text(row.get("recommended_action")),
            "work_priority": _int(row.get("work_priority")),
            "sequence_path": sequence_path,
            "launch_status": "skipped_prediction_already_imported",
            "recommended_backend": "",
            "command": "",
            "contract_command": "",
            "conversion_command": "",
            "expected_prediction_path": expected_prediction_path,
            "blockers": "",
            "next_required_step": "Run validation batch and internal scorecard for the imported prediction.",
        }

    if not sequence_path:
        blockers.append("missing_sequence_path")
    elif not _resolve(sequence_path).exists():
        blockers.append("sequence_file_missing")
    if not args.allow_deadline_close and _int(row.get("days_to_human_expiration"), 999) <= 1:
        blockers.append("deadline_too_close_for_new_public_attempt")

    backend = _text(inventory.get("selected_backend"))
    if not backend:
        blockers.append("no_supported_prediction_backend_detected")
        readiness = _summary(_read_json(args.backend_readiness_json))
        readiness_status = _text(readiness.get("backend_status"))
        if readiness_status:
            blockers.append(f"backend_readiness:{readiness_status}")
        provisioning = _summary(_read_json(args.backend_provisioning_json))
        provisioning_status = _text(provisioning.get("plan_status"))
        if provisioning_status:
            blockers.append(f"backend_provisioning:{provisioning_status}")
    if backend:
        if target_kind == "protein_complex" and backend in MONOMER_ONLY_BACKENDS:
            blockers.append(f"backend_multimer_not_supported:{backend}")
        if target_kind == "protein_complex" and backend == "custom" and not args.backend_supports_multimer:
            blockers.append("backend_multimer_support_not_declared")
        if args.backend_max_chains > 0 and fasta_stats["entry_count"] > args.backend_max_chains:
            blockers.append("backend_max_chains_exceeded")
        if args.backend_max_residues > 0 and fasta_stats["residue_count"] > args.backend_max_residues:
            blockers.append("backend_max_residues_exceeded")

    launch_status = "ready_to_launch" if not blockers else "blocked"
    command = ""
    contract_command = ""
    conversion_command = ""
    if launch_status == "ready_to_launch":
        command = _command_for_backend(
            backend=backend,
            backend_entries=inventory.get("entries", []),
            target_id=target_id,
            fasta=sequence_path,
            out_dir=job_dir,
            raw_pdb=expected_raw_pdb,
            runtime_json=runtime_json,
            custom_backend_command=args.custom_backend_command,
            internal_quality_preset=args.internal_quality_preset,
            internal_ensemble_size=args.internal_ensemble_size,
            internal_steps=args.internal_steps,
            internal_emit_backbone_atoms=bool(args.internal_emit_backbone_atoms),
        )
        contract_command = _contract_command(target_id, sequence_path, expected_raw_pdb, runtime_json, backend)
        conversion_command = _conversion_command(target_id, sequence_path, expected_raw_pdb, expected_prediction_path)

    return {
        "target_id": target_id,
        "target_kind": target_kind,
        "recommended_action": _text(row.get("recommended_action")),
        "work_priority": _int(row.get("work_priority")),
        "sequence_path": sequence_path,
        "fasta_entry_count": fasta_stats["entry_count"],
        "fasta_residue_count": fasta_stats["residue_count"],
        "launch_status": launch_status,
        "recommended_backend": backend,
        "command": command,
        "contract_command": contract_command,
        "conversion_command": conversion_command,
        "expected_prediction_path": expected_prediction_path,
        "blockers": ";".join(blockers),
        "next_required_step": (
            "Run the command, validate backend output contract with GPU evidence, convert the best raw PDB into CASP17 TS format, then run import/validation/scorecard/gate."
            if launch_status == "ready_to_launch"
            else "Review the backend provisioning plan, wire a GPU-backed custom predictor, or attach a target-specific TS prediction file."
        ),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    work_queue = _read_json(args.work_queue_json)
    sequence_packet = _read_json(args.sequence_packet_json)
    prediction_import = _read_json(args.prediction_import_json)
    backend_readiness = _summary(_read_json(args.backend_readiness_json))
    backend_provisioning = _summary(_read_json(args.backend_provisioning_json))
    inventory = _backend_inventory(
        args.custom_backend_command,
        backend_mode=args.backend_mode,
        disable_auto_detection=args.disable_auto_backend_detection,
    )
    rows = [
        _launch_row(
            row,
            sequence_by_target=_sequence_index(sequence_packet),
            import_by_target=_import_index(prediction_import),
            inventory=inventory,
            args=args,
        )
        for row in _selected_rows(work_queue, args)
    ]
    ready_count = sum(1 for row in rows if row["launch_status"] == "ready_to_launch")
    skipped_count = sum(1 for row in rows if row["launch_status"].startswith("skipped"))
    blocked_count = sum(1 for row in rows if row["launch_status"] == "blocked")
    summary = {
        "packet_type": "casp17_prediction_launch_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "work_queue_json": _artifact(args.work_queue_json),
        "intake_csv": _artifact(args.intake_csv),
        "sequence_packet_json": _artifact(args.sequence_packet_json),
        "prediction_import_json": _artifact(args.prediction_import_json),
        "backend_readiness_json": _artifact(args.backend_readiness_json),
        "backend_provisioning_json": _artifact(args.backend_provisioning_json),
        "prediction_dir": _artifact(args.prediction_dir),
        "job_dir": _artifact(args.job_dir),
        "target_count": len(rows),
        "target_scope": args.target_scope,
        "backend_mode": args.backend_mode,
        "allow_deadline_close": bool(args.allow_deadline_close),
        "backend_supports_multimer": bool(args.backend_supports_multimer),
        "backend_max_chains": int(args.backend_max_chains),
        "backend_max_residues": int(args.backend_max_residues),
        "internal_quality_preset": args.internal_quality_preset,
        "internal_ensemble_size": int(args.internal_ensemble_size),
        "internal_steps": int(args.internal_steps),
        "internal_emit_backbone_atoms": bool(args.internal_emit_backbone_atoms),
        "ready_to_launch_count": ready_count,
        "blocked_count": blocked_count,
        "skipped_count": skipped_count,
        "top_launch_target_id": next((row["target_id"] for row in rows if row["launch_status"] == "ready_to_launch"), ""),
        "backend_inventory": inventory,
        "backend_readiness": backend_readiness,
        "backend_provisioning": backend_provisioning,
        "claim_boundary": "Local prediction launch planning only; commands are not executed and this is not CASP17 validation or submission evidence.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    backend = summary["backend_inventory"]
    lines = [
        "# CASP17 Prediction Launch Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target count: `{summary['target_count']}`",
        f"- target scope: `{summary['target_scope']}`",
        f"- ready/blocked/skipped: `{summary['ready_to_launch_count']}/{summary['blocked_count']}/{summary['skipped_count']}`",
        f"- selected backend: `{backend.get('selected_backend') or 'none'}`",
        f"- backend readiness: `{summary.get('backend_readiness', {}).get('backend_status') or 'not_loaded'}`",
        f"- backend provisioning: `{summary.get('backend_provisioning', {}).get('plan_status') or 'not_loaded'}`",
        f"- GPU detected: `{backend.get('gpu', {}).get('gpu_detected')}`",
        f"- top launch target: `{summary['top_launch_target_id'] or '-'}`",
        "",
        "## Rows",
        "",
        "| target | kind | FASTA | status | backend | command | contract | conversion | blockers | next step |",
        "| --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row.get('target_kind') or '-'}` | "
            f"`{row.get('fasta_entry_count', 0)}/{row.get('fasta_residue_count', 0)}` | "
            f"`{row['launch_status']}` | `{row['recommended_backend'] or '-'}` | "
            f"`{row['command'] or '-'}` | `{row.get('contract_command') or '-'}` | `{row['conversion_command'] or '-'}` | "
            f"{row['blockers'] or '-'} | {row['next_required_step']} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | `0/0` | `no_eligible_targets` | - | `-` | `-` | `-` | - | Build watchlist, sequence, import, gate, and work queue first. |")
    lines.extend(["", "## Backend Inventory", ""])
    for entry in backend.get("entries", []):
        lines.append(f"- `{entry['backend']}`: available=`{entry['available']}` path=`{entry.get('path') or '-'}`")
    modules = backend.get("python_modules", {})
    if isinstance(modules, dict):
        available_modules = sorted(name for name, present in modules.items() if present)
        lines.append(f"- python backend modules available: `{','.join(available_modules) if available_modules else 'none'}`")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a fail-closed CASP17 prediction launch packet without executing prediction jobs.")
    parser.add_argument("--work-queue-json", default=DEFAULT_WORK_QUEUE_JSON)
    parser.add_argument("--intake-csv", default=DEFAULT_INTAKE_CSV)
    parser.add_argument("--sequence-packet-json", default=DEFAULT_SEQUENCE_PACKET_JSON)
    parser.add_argument("--prediction-import-json", default=DEFAULT_PREDICTION_IMPORT_JSON)
    parser.add_argument("--backend-readiness-json", default=DEFAULT_BACKEND_READINESS_JSON)
    parser.add_argument("--backend-provisioning-json", default=DEFAULT_BACKEND_PROVISIONING_JSON)
    parser.add_argument("--prediction-dir", default=DEFAULT_PREDICTION_DIR)
    parser.add_argument("--job-dir", default=DEFAULT_JOB_DIR)
    parser.add_argument("--target-limit", type=int, default=3)
    parser.add_argument("--target-scope", choices=sorted(TARGET_SCOPES), default="eligible")
    parser.add_argument("--include-second-wave", action="store_true")
    parser.add_argument("--allow-deadline-close", action="store_true")
    parser.add_argument("--backend-mode", choices=sorted(BACKEND_MODES), default="auto")
    parser.add_argument("--custom-backend-command", default="")
    parser.add_argument("--internal-quality-preset", choices=["casp17_quality", "fast", "smoke"], default="casp17_quality")
    parser.add_argument("--internal-ensemble-size", type=int, default=0)
    parser.add_argument("--internal-steps", type=int, default=0)
    parser.add_argument("--internal-emit-backbone-atoms", action="store_true")
    parser.add_argument("--backend-supports-multimer", action="store_true")
    parser.add_argument("--backend-max-chains", type=int, default=0)
    parser.add_argument("--backend-max-residues", type=int, default=0)
    parser.add_argument("--disable-auto-backend-detection", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
