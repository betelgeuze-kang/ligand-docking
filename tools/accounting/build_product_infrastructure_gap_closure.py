#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/product_infrastructure_gap_closure_current.json"
DEFAULT_OUT_CSV = "runs/product_infrastructure_gap_closure_current.csv"
DEFAULT_OUT_MD = "runs/product_infrastructure_gap_closure_current.md"

CLAIM_BOUNDARY = (
    "Product infrastructure gap closure status only; audits deploy/profile/execution-approval wiring for the five "
    "commercialization infrastructure gaps. It does not run docking, mutate external state, or enable execution."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_text(path_like: str | Path) -> str:
    path = _resolve(path_like)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _row(gap_id: str, gap: str, status: str, evidence: str, observed: str, next_action: str) -> dict[str, Any]:
    return {
        "gap_id": gap_id,
        "gap": gap,
        "status": status,
        "evidence": evidence,
        "observed": observed,
        "next_action": next_action,
        "release_blocker": status != "closed",
        "execution_enabled": False,
        "external_state_mutated": False,
    }


def build_product_infrastructure_gap_closure() -> dict[str, Any]:
    compose = _read_text("deploy/docker-compose.product.yml")
    systemd_unit = _read_text("deploy/systemd/micf-api-docking-dispatch.service")
    systemd_env = _read_text("deploy/systemd/api-docking-dispatch.env.example")
    k8s_dispatch = _read_text("deploy/k8s/dispatch-deployment.yaml")
    kustomization = _read_text("deploy/k8s/kustomization.yaml")
    htvs_profile = _read_text("config/api_validated_runner_profiles/ligand_htvs_pipeline_default.json")
    backmap_profile = _read_text("config/api_validated_runner_profiles/backmapping_scoring.production.json")
    topk_profile = _read_text("config/api_validated_runner_profiles/ligand_topk_delivery.production.json")
    validated_runner = _read_text("api/validated_runner.py")
    docking_request = _read_text("betelgeuze_product/docking_request.py")
    materialize_backmap = _resolve("tools/product/materialize_docking_backmapping_request.py")

    dispatch_deploy_ready = all(
        token in compose
        for token in (
            "api-docking-dispatch:",
            "tools/run_api_docking_dispatch_worker.py",
            "API_DOCKING_DISPATCH_POLL_INTERVAL_SECONDS",
        )
    ) and all(
        token in systemd_unit
        for token in ("api-docking-dispatch.env", "tools/run_api_docking_dispatch_worker.py", "API_DOCKING_DISPATCH_POLL_INTERVAL_SECONDS")
    ) and "API_DOCKING_DISPATCH_POLL_INTERVAL_SECONDS" in systemd_env and "micf-api-docking-dispatch" in k8s_dispatch and "dispatch-deployment.yaml" in kustomization

    htvs_profile_ready = (
        '"enabled": true' in htvs_profile
        and "--pipeline-preset-json" in htvs_profile
        and "--docking-request-json" in htvs_profile
        and (
            "ligand_htvs_api_dispatch_smoke_v1.json" in htvs_profile
            or "ligand_htvs_blind_gpcr_adrb2_4bead_v1.json" in htvs_profile
        )
    )
    backmap_profile_ready = (
        '"enabled": true' in backmap_profile
        and "--docking-request-json" in backmap_profile
        and materialize_backmap.exists()
    )
    topk_profile_ready = (
        '"enabled": true' in topk_profile
        and "tools/run_ligand_topk_delivery.py" in topk_profile
        and "tools/run_ligand_topk_delivery.py" in validated_runner
    )
    execution_gate_ready = all(
        token in docking_request
        for token in (
            "execution_approval_gate_status",
            "execution_enabled_conditional_would_enable",
            "APPROVE_PRODUCT_DOCKING_EXECUTION",
            "_execution_approval_posture",
        )
    )
    topk_profile_enabled = '"enabled": true' in topk_profile
    topk_runner_allowlisted = "tools/run_ligand_topk_delivery.py" in validated_runner
    execution_enabled_hard_false = '"execution_enabled": False' in docking_request

    rows = [
        _row(
            "HW-DEP-02",
            "dispatch worker deploy (compose/systemd/k8s)",
            "closed" if dispatch_deploy_ready else "open",
            "deploy/docker-compose.product.yml; deploy/systemd/micf-api-docking-dispatch.service; deploy/k8s/dispatch-deployment.yaml",
            f"compose_dispatch_service={dispatch_deploy_ready}; systemd_unit={bool(systemd_unit)}; k8s_dispatch={bool(k8s_dispatch)}",
            "Add api-docking-dispatch service to compose/systemd/k8s and wire shared SQLite queue volume.",
        ),
        _row(
            "HW-PROF-01",
            "HTVS profile API dispatch preset + docking request materialize",
            "closed" if htvs_profile_ready else "open",
            "config/api_validated_runner_profiles/ligand_htvs_pipeline_default.json",
            (
                f"pipeline_preset_json={'--pipeline-preset-json' in htvs_profile}; "
                f"api_dispatch_smoke_preset={'ligand_htvs_api_dispatch_smoke_v1.json' in htvs_profile}; "
                f"blind_4bead_preset={'ligand_htvs_blind_gpcr_adrb2_4bead_v1.json' in htvs_profile}; "
                f"docking_request_json={'--docking-request-json' in htvs_profile}"
            ),
            "Enable HTVS profile with API dispatch or blind 4-bead preset and docking request.json consumption.",
        ),
        _row(
            "HW-PROF-02",
            "backmapping ledger materialize + profile",
            "closed" if backmap_profile_ready else "open",
            "config/api_validated_runner_profiles/backmapping_scoring.production.json; tools/product/materialize_docking_backmapping_request.py",
            f"materialize_module_exists={materialize_backmap.exists()}; profile_docking_request={'--docking-request-json' in backmap_profile}",
            "Wire backmapping profile to materialize queue/config from docking request.json.",
        ),
        _row(
            "HW-PROF-04",
            "topk delivery production profile",
            "closed" if topk_profile_ready else "open",
            "config/api_validated_runner_profiles/ligand_topk_delivery.production.json; api/validated_runner.py",
            f"profile_enabled={topk_profile_enabled}; allowlisted={topk_runner_allowlisted}",
            "Add ligand_topk_delivery.production profile and allowlist runner script.",
        ),
        _row(
            "CB-EXEC",
            "execution approval fail-closed wiring",
            "closed" if execution_gate_ready else "open",
            "betelgeuze_product/docking_request.py; runs/product_execution_approval_gate_current.json",
            f"conditional_wiring={execution_gate_ready}; execution_enabled_hard_false={execution_enabled_hard_false}",
            "Wire product execution approval gate into docking ledger while keeping execution_enabled=false.",
        ),
    ]
    closed = [row for row in rows if row["status"] == "closed"]
    open_rows = [row for row in rows if row["status"] != "closed"]
    first_open = open_rows[0] if open_rows else None
    summary = {
        "packet_type": "product_infrastructure_gap_closure",
        "status": "product_infrastructure_gap_closure_complete" if not open_rows else "blocked_product_infrastructure_gap_closure",
        "all_gaps_closed": not open_rows,
        "gap_count": len(rows),
        "closed_gap_count": len(closed),
        "open_gap_count": len(open_rows),
        "closed_gap_ids": [row["gap_id"] for row in closed],
        "open_gap_ids": [row["gap_id"] for row in open_rows],
        "current_primary_open_gap_id": first_open["gap_id"] if first_open else "none",
        "current_next_action": first_open["next_action"] if first_open else "All product infrastructure gaps are closed.",
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Product Infrastructure Gap Closure",
        "",
        f"- status: `{s['status']}`",
        f"- all_gaps_closed: `{s['all_gaps_closed']}`",
        f"- closed_gap_count: `{s['closed_gap_count']}` / `{s['gap_count']}`",
        "",
        "## Gaps",
        "",
        "| gap_id | status | gap | observed |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['gap_id']}` | `{row['status']}` | {row['gap']} | `{row['observed']}` |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build product infrastructure gap closure status.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    args = parser.parse_args(argv)
    payload = build_product_infrastructure_gap_closure()
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
