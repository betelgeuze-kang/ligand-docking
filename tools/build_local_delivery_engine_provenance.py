#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"

DEFAULT_OUT_JSON = "runs/local_delivery_engine_provenance_current.json"
DEFAULT_OUT_MD = "runs/local_delivery_engine_provenance_current.md"

DEFAULT_PIPELINE_SCRIPT = "tools/run_ligand_htvs_pipeline.py"
DEFAULT_TRAJECTORY_ENGINE_SCRIPT = "tools/generate_ligand_trajectory_engine.py"
DEFAULT_RUST_ENGINE_LIB = "rust_engine/src/lib.rs"

DEFAULT_ENGINE_SURFACE_FILES = [
    DEFAULT_PIPELINE_SCRIPT,
    DEFAULT_TRAJECTORY_ENGINE_SCRIPT,
    "core/integrator.py",
    "core/forcefield.py",
    "core/topology.py",
    DEFAULT_RUST_ENGINE_LIB,
]

ENGINE_SURFACE_ROLES = {
    DEFAULT_PIPELINE_SCRIPT: "top_level_htvs_pipeline_orchestrator",
    DEFAULT_TRAJECTORY_ENGINE_SCRIPT: "trajectory_generation_and_rollout_engine",
    "core/integrator.py": "langevin_integrator",
    "core/forcefield.py": "forcefield_and_backend_selection",
    "core/topology.py": "topology_and_layout_helpers",
    DEFAULT_RUST_ENGINE_LIB: "rust_hip_native_bridge",
}

TRAJECTORY_IMPORT_TARGETS = [
    ("core.config", "core.config"),
    ("ForceField", "ForceField"),
    ("LangevinIntegrator", "LangevinIntegrator"),
    ("TopologyFactory", "TopologyFactory"),
    ("load_native_structure", "load_native_structure"),
]

RUST_ENGINE_TARGETS = [
    ("rust_native_bindings", "extern \"C\""),
    ("rust_kernel_launchers", "launch_"),
    ("rust_python_surface", "pyo3"),
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _read_text(path_like: str | Path) -> str:
    path = _resolve(path_like)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _file_fingerprint(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return {"sha256": "", "size_bytes": 0}
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return {"sha256": h.hexdigest(), "size_bytes": int(path.stat().st_size)}


def _now_local() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _git_value(*args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def collect_git_info() -> dict[str, Any]:
    commit = _git_value("rev-parse", "HEAD")
    branch = _git_value("rev-parse", "--abbrev-ref", "HEAD")
    status = _git_value("status", "--porcelain")
    if not commit and not branch:
        return {"available": False}
    return {
        "available": True,
        "commit": commit,
        "branch": branch,
        "dirty": bool(status),
        "status_porcelain": status.splitlines(),
    }


def _surface_status(paths: Sequence[str | Path]) -> dict[str, Any]:
    required = [_relative(_resolve(path)) for path in paths]
    present = [relpath for relpath in required if _resolve(relpath).exists()]
    missing = [relpath for relpath in required if not _resolve(relpath).exists()]
    details = [
        {
            "path": relpath,
            "role": ENGINE_SURFACE_ROLES.get(relpath, "existing_repository_engine_surface"),
            "present": relpath in present,
            "exists": relpath in present,
            "kind": "existing_repository_engine_surface",
            **_file_fingerprint(relpath),
        }
        for relpath in required
    ]
    return {
        "required": required,
        "present": present,
        "missing": missing,
        "details": details,
    }


def _line_for_token(text: str, token: str) -> int | None:
    for idx, line in enumerate(text.splitlines(), start=1):
        if token in line:
            return idx
    return None


def collect_import_evidence(
    *,
    trajectory_engine_script: str | Path = DEFAULT_TRAJECTORY_ENGINE_SCRIPT,
    rust_engine_lib: str | Path = DEFAULT_RUST_ENGINE_LIB,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    trajectory_text = _read_text(trajectory_engine_script)
    trajectory_path = _relative(_resolve(trajectory_engine_script))
    for label, token in TRAJECTORY_IMPORT_TARGETS:
        line = _line_for_token(trajectory_text, token)
        evidence.append(
            {
                "label": label,
                "source_file": trajectory_path,
                "present": line is not None,
                "line": line,
                "meaning": "trajectory engine references existing repository engine surface",
            }
        )

    rust_text = _read_text(rust_engine_lib)
    rust_path = _relative(_resolve(rust_engine_lib))
    for label, token in RUST_ENGINE_TARGETS:
        line = _line_for_token(rust_text.lower(), token.lower())
        if line is None:
            continue
        evidence.append(
            {
                "label": label,
                "source_file": rust_path,
                "present": True,
                "line": line,
                "meaning": "optional native Rust/HIP engine surface evidence",
            }
        )
    return evidence


def collect_config_evidence(limit: int = 12) -> dict[str, Any]:
    config_dir = ROOT / "config"
    paths = sorted(config_dir.glob("ligand_htvs_*.json")) if config_dir.exists() else []
    selected = paths[: max(0, int(limit))]
    return {
        "pattern": "config/ligand_htvs_*.json",
        "count": len(paths),
        "selected": [
            {
                "path": _relative(path),
                **_file_fingerprint(path),
            }
            for path in selected
        ],
    }


def collect_run_artifact_evidence(limit: int = 12) -> dict[str, Any]:
    paths = sorted(RUNS.glob("ligand_htvs_*")) if RUNS.exists() else []
    selected = [path for path in paths if path.is_file()][: max(0, int(limit))]
    return {
        "pattern": "runs/ligand_htvs_*",
        "count": len([path for path in paths if path.is_file()]),
        "selected": [
            {
                "path": _relative(path),
                **_file_fingerprint(path),
            }
            for path in selected
        ],
    }


def _next_required_step(existing_engine_reused: bool, required_import_evidence_present: bool) -> str:
    if existing_engine_reused and required_import_evidence_present:
        return "Use the existing engine surfaces in the local delivery workflow; do not implement a new engine."
    if not required_import_evidence_present:
        return "restore the expected existing engine import chain before claiming local delivery engine reuse; do not implement a replacement engine."
    return "restore/mount existing engine surface files before claiming local delivery engine reuse; do not implement a replacement engine."


def build_payload(
    *,
    engine_surface_files: Sequence[str | Path] | None = None,
    pipeline_script: str | Path = DEFAULT_PIPELINE_SCRIPT,
    trajectory_engine_script: str | Path = DEFAULT_TRAJECTORY_ENGINE_SCRIPT,
    rust_engine_lib: str | Path = DEFAULT_RUST_ENGINE_LIB,
) -> dict[str, Any]:
    surfaces = list(engine_surface_files or DEFAULT_ENGINE_SURFACE_FILES)
    for path in (pipeline_script, trajectory_engine_script, rust_engine_lib):
        relpath = _relative(_resolve(path))
        if relpath not in [_relative(_resolve(surface)) for surface in surfaces]:
            surfaces.append(path)

    generated_at_local = _now_local()
    git_info = collect_git_info()
    engine_surface_files_payload = _surface_status(surfaces)
    import_evidence = collect_import_evidence(
        trajectory_engine_script=trajectory_engine_script,
        rust_engine_lib=rust_engine_lib,
    )
    present_surface_count = len(engine_surface_files_payload["present"])
    missing_surface_count = len(engine_surface_files_payload["missing"])
    required_surface_count = len(engine_surface_files_payload["required"])
    import_evidence_count = sum(1 for item in import_evidence if item.get("present"))
    existing_engine_reused = missing_surface_count == 0
    required_import_evidence_present = all(
        bool(item.get("present"))
        for item in import_evidence
        if item.get("source_file") == _relative(_resolve(trajectory_engine_script))
    )
    provenance_ok = bool(existing_engine_reused and required_import_evidence_present)
    engine_reuse_statement = (
        "Local delivery reuses existing repository engine surfaces; no new engine is created by this layer."
    )
    status_line = (
        f"provenance_ok={str(provenance_ok).lower()} | "
        f"existing_engine_reused={str(existing_engine_reused).lower()} | "
        f"surfaces={present_surface_count}/{required_surface_count} present | "
        f"import_evidence={import_evidence_count}"
    )
    next_required_step = _next_required_step(existing_engine_reused, required_import_evidence_present)
    return {
        "summary": {
            "provenance_ok": provenance_ok,
            "existing_engine_reused": existing_engine_reused,
            "engine_reuse_statement": engine_reuse_statement,
            "generated_at_local": generated_at_local,
            "source_repo_commit": str(git_info.get("commit", "")),
            "git_dirty": bool(git_info.get("dirty", False)),
            "pipeline_entrypoint": _relative(_resolve(pipeline_script)),
            "trajectory_engine_script": _relative(_resolve(trajectory_engine_script)),
            "required_surface_count": required_surface_count,
            "present_surface_count": present_surface_count,
            "missing_surface_count": missing_surface_count,
            "import_evidence_count": import_evidence_count,
            "required_import_evidence_present": required_import_evidence_present,
            "status_line": status_line,
        },
        "engine_surface_files": engine_surface_files_payload,
        "required_engine_files": engine_surface_files_payload["details"],
        "reuse_chain": [
            _relative(_resolve(pipeline_script)),
            _relative(_resolve(trajectory_engine_script)),
            "core.forcefield.ForceField",
            "core.integrator.LangevinIntegrator",
            "core.topology.TopologyFactory",
            _relative(_resolve(rust_engine_lib)),
        ],
        "import_evidence": import_evidence,
        "import_edge_checks": import_evidence,
        "config_evidence": collect_config_evidence(),
        "run_artifact_evidence": collect_run_artifact_evidence(),
        "negative_claim_guardrail": "No new engine is created by local delivery; this artifact records reuse of existing repository engine surfaces.",
        "generated_at_local": generated_at_local,
        "git": git_info,
        "next_required_step": next_required_step,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = dict(payload.get("summary", {}) or {})
    surfaces = dict(payload.get("engine_surface_files", {}) or {})
    evidence = list(payload.get("import_evidence") or [])
    lines = [
        "# Local Delivery Engine Provenance",
        "",
        "This is provenance for existing engine reuse, not a new engine implementation.",
        "",
        "## Summary",
        "",
        f"- Status: {summary.get('status_line', '')}",
        f"- Engine reuse statement: {summary.get('engine_reuse_statement', '')}",
        f"- Generated local time: {payload.get('generated_at_local', '')}",
        f"- Next required step: {payload.get('next_required_step', '')}",
        "",
        "## Existing Engine Surface Files",
        "",
    ]
    for detail in surfaces.get("details", []):
        marker = "present" if detail.get("present") else "missing"
        lines.append(
            f"- {marker}: {detail.get('path', '')} "
            f"role={detail.get('role', '-')} sha256={detail.get('sha256', '-') or '-'}"
        )
    lines.extend(["", "## Reuse Chain", ""])
    for item in payload.get("reuse_chain", []) or []:
        lines.append(f"- {item}")
    lines.extend(["", "## Import Evidence", ""])
    for item in evidence:
        marker = "present" if item.get("present") else "missing"
        line = item.get("line")
        line_text = f":{line}" if line else ""
        lines.append(f"- {marker}: {item.get('label', '')} in {item.get('source_file', '')}{line_text}")
    lines.extend(["", "## Config Evidence", ""])
    config_evidence = dict(payload.get("config_evidence", {}) or {})
    lines.append(f"- pattern: {config_evidence.get('pattern', '-')}")
    lines.append(f"- count: {config_evidence.get('count', 0)}")
    for item in config_evidence.get("selected", []) or []:
        lines.append(f"- {item.get('path', '')} sha256={item.get('sha256', '-') or '-'}")
    lines.extend(["", "## Guardrails", ""])
    lines.append(f"- {payload.get('negative_claim_guardrail', '')}")
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], out_json: str | Path, out_md: str | Path) -> None:
    json_path = _resolve(out_json)
    md_path = _resolve(out_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build local-delivery provenance showing reuse of existing engine surfaces."
    )
    parser.add_argument(
        "--engine-surface-file",
        action="append",
        default=[],
        help="Additional existing engine surface file to require; may be supplied more than once.",
    )
    parser.add_argument("--pipeline-script", default=DEFAULT_PIPELINE_SCRIPT)
    parser.add_argument("--trajectory-engine-script", default=DEFAULT_TRAJECTORY_ENGINE_SCRIPT)
    parser.add_argument("--rust-engine-lib", default=DEFAULT_RUST_ENGINE_LIB)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    engine_surface_files = [*DEFAULT_ENGINE_SURFACE_FILES, *args.engine_surface_file]
    payload = build_payload(
        engine_surface_files=engine_surface_files,
        pipeline_script=args.pipeline_script,
        trajectory_engine_script=args.trajectory_engine_script,
        rust_engine_lib=args.rust_engine_lib,
    )
    write_outputs(payload, args.out_json, args.out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
