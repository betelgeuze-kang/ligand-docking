#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = ".betelgeuze/f2g_f2h_surface_preflight.local.json"
DEFAULT_OUT_CSV = ".betelgeuze/f2g_f2h_surface_preflight.local.csv"
DEFAULT_OUT_MD = ".betelgeuze/f2g_f2h_surface_preflight.local.md"
DEFAULT_PRODUCTIZATION_DIR = "implementation/phase1/release_evidence/productization"
DEFAULT_F2G_AUDIT_JSON = (
    "implementation/phase1/release_evidence/productization/"
    "g1_support_elastic_link_reconciliation_audit.local.json"
)

EXCLUDED_DIRS = {
    ".git",
    ".betelgeuze",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "archives",
    "data",
    "logs",
    "models",
    "node_modules",
    "output",
    "results",
    "runtime",
    "target",
    "tmp",
    "venv",
    "viewer",
}

CLAIM_BOUNDARY = (
    "F2g/F2h surface preflight only; it checks whether the current checkout exposes the real-MGT, "
    "real_per_element assembled tangent, near-null mode, support/elastic-link, and continuation prerequisite "
    "surfaces needed for the PM-requested non-promoting audit. It does not assemble a solver, run Newton, "
    "pin DOFs, regenerate 0.656 evidence, promote G1, update protected runs artifacts, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def _candidate_paths(root: Path) -> list[str]:
    paths: list[str] = []
    for path in root.rglob("*"):
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if _is_excluded(rel) or not path.is_file():
            continue
        paths.append(rel.as_posix())
    return sorted(paths)


def _matches(paths: list[str], *tokens: str) -> list[str]:
    lower_tokens = tuple(token.lower() for token in tokens if token)
    return [path for path in paths if all(token in path.lower() for token in lower_tokens)]


def _any_matches(paths: list[str], groups: list[tuple[str, ...]]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for group in groups:
        for path in _matches(paths, *group):
            if path not in seen:
                seen.add(path)
                out.append(path)
    return out


def _row(check_id: str, passed: bool, observed: str, required: str, blocker: str, next_action: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "blocker": "" if passed else blocker,
        "next_action": next_action,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
    }


def build_f2g_f2h_surface_preflight(
    *,
    root: Path = ROOT,
    productization_dir: str = DEFAULT_PRODUCTIZATION_DIR,
    f2g_audit_json: str = DEFAULT_F2G_AUDIT_JSON,
) -> dict[str, Any]:
    root = Path(root)
    candidate_paths = _candidate_paths(root)
    implementation_phase1_dir = _resolve("implementation/phase1", root=root)
    productization_path = _resolve(productization_dir, root=root)
    f2g_audit_path = _resolve(f2g_audit_json, root=root)

    real_mgt_candidates = _any_matches(candidate_paths, [("real", "mgt"), ("real-mgt",), ("real_mgt",)])
    real_per_element_candidates = _any_matches(
        candidate_paths,
        [("real_per_element",), ("real-per-element",), ("per_element", "tangent")],
    )
    assembled_tangent_candidates = _any_matches(
        candidate_paths,
        [("assembled", "tangent"), ("service", "tangent"), ("real_per_element",)],
    )
    near_null_mode_candidates = _any_matches(
        candidate_paths,
        [("near_null",), ("near-null",), ("near_rigid",), ("marginally", "negative")],
    )
    support_elastic_candidates = _any_matches(
        candidate_paths,
        [("support", "elastic"), ("elastic", "link"), ("supported", "dof"), ("free", "dof", "support")],
    )
    continuation_candidates = _any_matches(
        candidate_paths,
        [("continuation", "newton"), ("load", "continuation"), ("relative_diagonal_shift",), ("diagonal", "shift")],
    )

    rows = [
        _row(
            "implementation_phase1_dir",
            implementation_phase1_dir.is_dir(),
            str(implementation_phase1_dir.relative_to(root)) if implementation_phase1_dir.exists() else "missing",
            "implementation/phase1 directory present",
            "implementation_phase1_dir_missing",
            "Restore or add the F2/G1 implementation tree before running the support/elastic-link audit.",
        ),
        _row(
            "productization_release_evidence_dir",
            productization_path.is_dir(),
            str(productization_path.relative_to(root)) if productization_path.exists() else "missing",
            "implementation/phase1/release_evidence/productization directory present",
            "productization_release_evidence_dir_missing",
            "Create the non-promoting productization evidence directory or restore it from the branch that owns F2/G1.",
        ),
        _row(
            "real_mgt_input_surface",
            bool(real_mgt_candidates),
            ";".join(real_mgt_candidates[:8]) or "none",
            "at least one current real-MGT input/model surface candidate",
            "real_mgt_input_surface_missing",
            "Restore the real-MGT model/input packet before mapping near-null DOFs.",
        ),
        _row(
            "real_per_element_assembled_tangent_surface",
            bool(real_per_element_candidates and assembled_tangent_candidates),
            ";".join((real_per_element_candidates + assembled_tangent_candidates)[:8]) or "none",
            "real_per_element assembled tangent candidate surface present",
            "real_per_element_tangent_surface_missing",
            "Expose the real_per_element service tangent packet used by the F2 diagnostic merges.",
        ),
        _row(
            "near_null_mode_packet",
            bool(near_null_mode_candidates),
            ";".join(near_null_mode_candidates[:8]) or "none",
            "near-null or marginally negative mode packet present",
            "near_null_modes_packet_missing",
            "Restore the PR #61 near-null mode packet so dominant DOFs can be reconciled.",
        ),
        _row(
            "support_elastic_link_context",
            bool(support_elastic_candidates),
            ";".join(support_elastic_candidates[:8]) or "none",
            "support and elastic-link context surface present",
            "support_elastic_link_context_missing",
            "Expose support membership, constrained/free DOFs, and elastic-link endpoint/stiffness context.",
        ),
        _row(
            "f2g_support_elastic_audit",
            f2g_audit_path.is_file(),
            str(f2g_audit_path.relative_to(root)) if f2g_audit_path.exists() else "missing",
            "g1_support_elastic_link_reconciliation_audit.local.json exists",
            "f2g_audit_not_available",
            "Run the F2g support/elastic-link reconciliation only after the required real-MGT surfaces are present.",
        ),
        _row(
            "f2h_continuation_prerequisites",
            f2g_audit_path.is_file() and bool(continuation_candidates),
            ";".join(continuation_candidates[:8]) or "none",
            "F2g audit plus continuation/Newton surface candidates present",
            "f2h_blocked_until_f2g_audit",
            "Do not start F2h continuation until the F2g local audit exists and continuation code/input surfaces are restored.",
        ),
    ]
    blockers = [row["blocker"] for row in rows if row["status"] != "pass"]
    ready = not blockers
    summary = {
        "packet_type": "f2g_f2h_surface_preflight",
        "status": "f2g_f2h_surface_preflight_ready" if ready else "blocked_f2g_f2h_surface_preflight",
        "root": str(root),
        "candidate_file_count": len(candidate_paths),
        "real_mgt_candidate_count": len(real_mgt_candidates),
        "real_per_element_candidate_count": len(real_per_element_candidates),
        "assembled_tangent_candidate_count": len(assembled_tangent_candidates),
        "near_null_mode_candidate_count": len(near_null_mode_candidates),
        "support_elastic_link_candidate_count": len(support_elastic_candidates),
        "continuation_candidate_count": len(continuation_candidates),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "f2g_audit_ready": f2g_audit_path.is_file(),
        "f2h_continuation_allowed": False,
        "g1_promotion_allowed": False,
        "solver_claim_promotion_allowed": False,
        "protected_runs_artifact_written": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run the non-promoting F2g support/elastic-link reconciliation audit."
            if ready
            else "Restore the missing F2/G1 real-MGT implementation and diagnostic input surfaces; keep F2h blocked until F2g local audit exists."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    summary = payload["summary"]
    lines = [
        "# F2g/F2h Surface Preflight",
        "",
        f"- status: `{summary['status']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- f2g_audit_ready: `{summary['f2g_audit_ready']}`",
        f"- f2h_continuation_allowed: `{summary['f2h_continuation_allowed']}`",
        f"- g1_promotion_allowed: `{summary['g1_promotion_allowed']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | blocker | next action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | `{row['blocker'] or '-'}` | {row['next_action']} |"
        )
    lines.extend(["", "## Claim Boundary", "", summary["claim_boundary"], "", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the F2g/F2h surface availability preflight.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--productization-dir", default=DEFAULT_PRODUCTIZATION_DIR)
    parser.add_argument("--f2g-audit-json", default=DEFAULT_F2G_AUDIT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_f2g_f2h_surface_preflight(
        root=Path(args.root),
        productization_dir=args.productization_dir,
        f2g_audit_json=args.f2g_audit_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
