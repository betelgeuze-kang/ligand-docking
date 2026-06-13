#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.payload_privacy import SENSITIVE_COLLECTION_KEYS, SENSITIVE_SCALAR_KEYS, SENSITIVE_KEY_SUFFIXES
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_ledger_privacy_scan_current.json"
DEFAULT_OUT_CSV = "runs/product_ledger_privacy_scan_current.csv"
DEFAULT_OUT_MD = "runs/product_ledger_privacy_scan_current.md"

DEFAULT_SCAN_GLOBS = [
    "results/product_docking_jobs/*.json",
    "runs/tier_alpha_dispatch_smoke/current/results/product_docking_jobs/*.json",
    "runs/tier_alpha_dispatch_smoke/current/results/*/request.json",
    "runs/api_docking_e2e_smoke_current/product_docking_jobs/*.json",
    "runs/api_docking_e2e_smoke_current/*/request.json",
    "runs/product_operational_quality_contract_current.json",
    "runs/api_docking_dispatch_e2e_evidence_current.json",
    "runs/api_customer_flow_release_evidence_current.json",
    "runs/product_commercial_readiness_operator_packet_current.json",
    "runs/product_commercial_readiness_handoff_bundle_current.json",
    "runs/product_commercial_readiness_operator_packet_freshness_current.json",
    "runs/product_commercial_readiness_execution_ladder_current.json",
    "runs/product_goal_completion_audit_current.json",
    "runs/goal_readiness_rollup_current.json",
    "runs/goal_operator_action_board_current.json",
    "runs/goal_operator_intake_kit_current/manifest.json",
    "runs/goal_release_burndown_work_order_current.json",
    "runs/goal_api_surface_contract_current.json",
    "runs/goal_bottleneck_briefing_current.json",
    "runs/product_full_commercial_blocker_evidence_matrix_current.json",
    "runs/product_scope_breadth_evidence_priority_packet_current.json",
    "runs/engine_refinement_claim_evidence_priority_packet_current.json",
    "runs/production_ai_registry_promotion_operator_receipt_current.json",
    "runs/production_ai_registry_promotion_priority_packet_current.json",
]

CLAIM_BOUNDARY = (
    "Product ledger privacy scan only; it reads local JSON job records, request artifacts, and release audit "
    "artifacts for raw molecular payload leaks. Findings are reported as hash-only evidence. It does not run "
    "docking, mutate ledgers, upload data, email, delete, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash_record(value: Any) -> dict[str, Any]:
    raw = _canonical_text(value)
    return {
        "value_sha256": _sha256_text(raw),
        "byte_length": len(raw.encode("utf-8")),
    }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _is_sensitive_key(key: str) -> bool:
    return key in SENSITIVE_SCALAR_KEYS or key.endswith(SENSITIVE_KEY_SUFFIXES)


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _is_hash_only_redaction(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    sha = str(value.get("sha256", "") or "")
    return (
        value.get("redacted") is True
        and str(value.get("redaction", "") or "") == "sha256"
        and len(sha) == 64
        and all(ch in "0123456789abcdef" for ch in sha.lower())
    )


def _looks_inline_pdb(value: str) -> bool:
    lines = value.splitlines()
    return any(line.startswith("ATOM  ") or line.startswith("HETATM") for line in lines)


def _finding(
    *,
    artifact_path: str,
    json_path: str,
    leak_type: str,
    key: str,
    value: Any,
) -> dict[str, Any]:
    record = _hash_record(value)
    return {
        "artifact_path": artifact_path,
        "json_path": json_path,
        "leak_type": leak_type,
        "key": key,
        "value_sha256": record["value_sha256"],
        "byte_length": record["byte_length"],
    }


def _scan_value(
    value: Any,
    *,
    artifact_path: str,
    json_path: str,
    parent_key: str = "",
    findings: list[dict[str, Any]],
    json_string_depth: int = 0,
) -> None:
    parent_key_l = parent_key.lower()
    if isinstance(value, dict):
        for raw_key, raw_child in value.items():
            key = str(raw_key)
            key_l = key.lower()
            child_path = f"{json_path}.{key}" if json_path else key
            if key_l.endswith("_sha256") or key_l == "request_sha256":
                continue
            if _is_sensitive_key(key_l):
                if not _is_empty(raw_child) and not _is_hash_only_redaction(raw_child):
                    findings.append(
                        _finding(
                            artifact_path=artifact_path,
                            json_path=child_path,
                            leak_type="raw_sensitive_key_value",
                            key=key,
                            value=raw_child,
                        )
                    )
                continue
            _scan_value(
                raw_child,
                artifact_path=artifact_path,
                json_path=child_path,
                parent_key=key,
                findings=findings,
                json_string_depth=json_string_depth,
            )
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _scan_value(
                item,
                artifact_path=artifact_path,
                json_path=f"{json_path}[{index}]",
                parent_key=parent_key,
                findings=findings,
                json_string_depth=json_string_depth,
            )
        return

    if isinstance(value, str):
        if value and parent_key_l in SENSITIVE_COLLECTION_KEYS:
            findings.append(
                _finding(
                    artifact_path=artifact_path,
                    json_path=json_path,
                    leak_type="raw_sensitive_collection_scalar",
                    key=parent_key,
                    value=value,
                )
            )
        if _looks_inline_pdb(value):
            findings.append(
                _finding(
                    artifact_path=artifact_path,
                    json_path=json_path,
                    leak_type="inline_pdb_text",
                    key=parent_key,
                    value=value,
                )
            )
        if json_string_depth < 1:
            stripped = value.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = None
                if parsed is not None:
                    _scan_value(
                        parsed,
                        artifact_path=artifact_path,
                        json_path=f"{json_path}{{json_string}}",
                        parent_key=parent_key,
                        findings=findings,
                        json_string_depth=json_string_depth + 1,
                    )


def _collect_scan_paths(root: Path, scan_globs: list[str]) -> list[Path]:
    paths: dict[str, Path] = {}
    for pattern in scan_globs:
        for path in root.glob(pattern):
            if path.is_file():
                paths[str(path.relative_to(root))] = path
    return [paths[key] for key in sorted(paths)]


def build_product_ledger_privacy_scan(
    *,
    root: str | Path = ROOT,
    scan_globs: list[str] | None = None,
) -> dict[str, Any]:
    root_path = Path(root)
    patterns = list(scan_globs or DEFAULT_SCAN_GLOBS)
    rows: list[dict[str, Any]] = []
    all_findings: list[dict[str, Any]] = []
    invalid_json_paths: list[str] = []

    for path in _collect_scan_paths(root_path, patterns):
        rel_path = str(path.relative_to(root_path))
        findings: list[dict[str, Any]] = []
        invalid_json = False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
            invalid_json = True
            invalid_json_paths.append(rel_path)
        if payload is not None:
            _scan_value(payload, artifact_path=rel_path, json_path="$", findings=findings)
        all_findings.extend(findings)
        passed = not findings and not invalid_json
        rows.append(
            {
                "row_type": "ledger_privacy_artifact_scan",
                "artifact_path": rel_path,
                "status": "pass" if passed else "fail",
                "finding_count": len(findings),
                "invalid_json": invalid_json,
                "finding_types": sorted({finding["leak_type"] for finding in findings}),
                "finding_paths": [finding["json_path"] for finding in findings],
                "observed": f"finding_count={len(findings)};invalid_json={invalid_json}",
                "required": "JSON artifact parses and contains no raw SMILES, inline PDB text, or ligand source values outside hash-only redaction records",
                "release_blocker": not passed,
                "execution_enabled": False,
                "external_state_mutated": False,
            }
        )

    blocker_rows = [row for row in rows if row["release_blocker"]]
    ready = not blocker_rows
    summary = {
        "packet_type": "product_ledger_privacy_scan",
        "status": "product_ledger_privacy_scan_ready" if ready else "blocked_product_ledger_privacy_scan",
        "ledger_privacy_scan_ready": ready,
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "scan_globs": patterns,
        "scan_file_count": len(rows),
        "pass_count": len(rows) - len(blocker_rows),
        "blocker_count": len(blocker_rows),
        "leak_count": len(all_findings),
        "invalid_json_count": len(invalid_json_paths),
        "invalid_json_paths": invalid_json_paths,
        "blocked_artifact_paths": [row["artifact_path"] for row in blocker_rows],
        "finding_count_by_type": {
            leak_type: sum(1 for finding in all_findings if finding["leak_type"] == leak_type)
            for leak_type in sorted({finding["leak_type"] for finding in all_findings})
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "execution_enabled": False,
        "external_state_mutated": False,
        "next_required_step": (
            "Ledger privacy scan is ready; keep this artifact in the release source-of-truth gate."
            if ready
            else "Redact raw molecular payloads to hash-only records, rerun the affected flow, then rebuild this scan."
        ),
    }
    return {"summary": summary, "rows": rows, "findings": all_findings, "blockers": blocker_rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path = ROOT) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Product Ledger Privacy Scan",
        "",
        f"- status: `{s['status']}`",
        f"- ledger_privacy_scan_ready: `{s['ledger_privacy_scan_ready']}`",
        f"- scan_file_count: `{s['scan_file_count']}`",
        f"- leak_count: `{s['leak_count']}`",
        f"- invalid_json_count: `{s['invalid_json_count']}`",
        "",
        "## Scanned Artifacts",
        "",
        "| artifact | status | observed |",
        "| --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['artifact_path']}` | `{row['status']}` | `{row['observed']}` |")
    if payload["findings"]:
        lines.extend(["", "## Hash-Only Findings", "", "| artifact | path | type | sha256 | bytes |", "| --- | --- | --- | --- | --- |"])
        for finding in payload["findings"]:
            lines.append(
                f"| `{finding['artifact_path']}` | `{finding['json_path']}` | `{finding['leak_type']}` | "
                f"`{finding['value_sha256']}` | `{finding['byte_length']}` |"
            )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan product job ledgers and audit artifacts for raw molecular payload leaks.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--scan-glob", action="append", default=None, help="Override default scan globs; may be repeated.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_product_ledger_privacy_scan(root=root, scan_globs=args.scan_glob)
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
