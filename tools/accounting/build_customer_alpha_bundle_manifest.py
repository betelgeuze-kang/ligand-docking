#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGING_JSON = "runs/amd_workstation_server_packaging_profile_current.json"
DEFAULT_ROCM_MANIFEST_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_THROUGHPUT_SCORECARD_JSON = "runs/amd_hardware_throughput_scorecard_current.json"
DEFAULT_RESIDUAL_SHADOW_JSON = "runs/residual_shadow_ab_current.json"
DEFAULT_GPCR_PROOF_JSON = "runs/gpcr_hard_decoy_residual_proof_current.json"
DEFAULT_PUBLIC_REGRESSION_JSON = "runs/public_benchmark_residual_regression_gate_current.json"
DEFAULT_PRODUCT_BUNDLE_JSON = "runs/product_bundle_contract_current.json"
DEFAULT_COMMERCIAL_INDEPENDENCE_JSON = "runs/product_commercial_independence_gate_current.json"
DEFAULT_PRODUCT_READINESS_JSON = "runs/product_readiness_gate_current.json"
DEFAULT_LOCAL_ENV_JSON = "runs/local_delivery_environment_manifest_current.json"
DEFAULT_OUT_JSON = "runs/customer_alpha_bundle_manifest_current.json"
DEFAULT_OUT_CSV = "runs/customer_alpha_bundle_manifest_current.csv"
DEFAULT_OUT_MD = "runs/customer_alpha_bundle_manifest_current.md"

CLAIM_BOUNDARY = (
    "Customer alpha bundle manifest only; consolidates existing local delivery, ROCm, residual, benchmark, packaging, "
    "and commercial-independence evidence into a customer-facing alpha handoff surface. It does not assemble a new zip, "
    "run docking, run benchmarks, train models, install dependencies, upload, submit to external services, email, "
    "archive, externalize, or delete files."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _external_state_mutated(*packets: dict[str, Any]) -> bool:
    for packet in packets:
        if packet.get("external_state_mutated") is True:
            return True
        if _summary(packet).get("external_state_mutated") is True:
            return True
        for row in packet.get("rows") or []:
            if isinstance(row, dict) and row.get("external_state_mutated") is True:
                return True
    return False


def _row(
    component: str,
    status: str,
    evidence: str,
    required: str,
    reason: str,
    customer_visible_surface: str,
) -> dict[str, Any]:
    return {
        "component": component,
        "status": status,
        "evidence": evidence,
        "required": required,
        "reason": reason,
        "customer_visible_surface": customer_visible_surface,
        "release_blocker": status != "pass",
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
    }


def build_customer_alpha_bundle_manifest(
    *,
    packaging_packet: dict[str, Any],
    rocm_manifest_packet: dict[str, Any],
    throughput_scorecard_packet: dict[str, Any],
    residual_shadow_packet: dict[str, Any],
    gpcr_proof_packet: dict[str, Any],
    public_regression_packet: dict[str, Any],
    product_bundle_packet: dict[str, Any],
    commercial_independence_packet: dict[str, Any],
    product_readiness_packet: dict[str, Any],
    local_env_packet: dict[str, Any],
    packaging_path: str = DEFAULT_PACKAGING_JSON,
    rocm_manifest_path: str = DEFAULT_ROCM_MANIFEST_JSON,
    throughput_scorecard_path: str = DEFAULT_THROUGHPUT_SCORECARD_JSON,
    residual_shadow_path: str = DEFAULT_RESIDUAL_SHADOW_JSON,
    gpcr_proof_path: str = DEFAULT_GPCR_PROOF_JSON,
    public_regression_path: str = DEFAULT_PUBLIC_REGRESSION_JSON,
    product_bundle_path: str = DEFAULT_PRODUCT_BUNDLE_JSON,
    commercial_independence_path: str = DEFAULT_COMMERCIAL_INDEPENDENCE_JSON,
    product_readiness_path: str = DEFAULT_PRODUCT_READINESS_JSON,
    local_env_path: str = DEFAULT_LOCAL_ENV_JSON,
) -> dict[str, Any]:
    packaging = _summary(packaging_packet)
    rocm = _summary(rocm_manifest_packet)
    throughput = _summary(throughput_scorecard_packet)
    residual = _summary(residual_shadow_packet)
    gpcr = _summary(gpcr_proof_packet)
    public_regression = _summary(public_regression_packet)
    product_bundle = _summary(product_bundle_packet)
    commercial = _summary(commercial_independence_packet)
    readiness = _summary(product_readiness_packet)
    local_env = _summary(local_env_packet)

    packaging_ready = (
        _text(packaging.get("status")) == "amd_workstation_server_packaging_profile_ready"
        and packaging.get("packaging_ready") is True
    )
    rocm_ready = _text(rocm.get("status")) == "rocm_environment_manifest_ready" and rocm.get("manifest_ready") is True
    throughput_ready = (
        _text(throughput.get("status")) == "amd_hardware_throughput_scorecard_ready"
        and throughput.get("scorecard_ready") is True
    )
    residual_ready = (
        _text(residual.get("status")) in {"residual_shadow_ab_ready", "residual_shadow_ab_scaffold_ready"}
        and (residual.get("residual_shadow_ab_ready") is True or residual.get("shadow_ab_ready") is True or residual.get("scaffold_ready") is True)
    )
    gpcr_ready = _text(gpcr.get("status")) == "gpcr_hard_decoy_residual_proof_ready" and gpcr.get("proof_ready") is True
    public_regression_ready = (
        _text(public_regression.get("status")) == "public_benchmark_residual_regression_gate_ready"
        and public_regression.get("regression_gate_ready") is True
    )
    product_bundle_ready = (
        _text(product_bundle.get("status")) == "product_bundle_contract_ready"
        and product_bundle.get("bundle_assembled") is True
        and product_bundle.get("bundle_validation_passed") is True
    )
    commercial_ready = (
        _text(commercial.get("status")) == "product_commercial_independence_gate_ready"
        and commercial.get("commercial_independent_product_claim_allowed") is True
        and int(commercial.get("external_saas_runtime_dependency_count") or 0) == 0
    )
    product_readiness_ready = (
        _text(readiness.get("status")) == "product_handoff_ready"
        and readiness.get("local_delivery_delivery_ready") is True
        and readiness.get("source_artifacts_all_fingerprinted") is True
    )
    local_install_ready = (
        local_env.get("requirements_lock_complete") is True
        and int(local_env.get("missing_requirement_count") or 0) == 0
        and (commercial.get("reproducible_install_manifest_ready") is True or packaging.get("install_guide_ready") is True)
    )
    no_external_state_mutation = not _external_state_mutated(
        packaging_packet,
        rocm_manifest_packet,
        throughput_scorecard_packet,
        residual_shadow_packet,
        gpcr_proof_packet,
        public_regression_packet,
        product_bundle_packet,
        commercial_independence_packet,
        product_readiness_packet,
        local_env_packet,
    )

    local_delivery_bundle_dir = _text(product_bundle.get("expected_bundle_dir"))
    rows = [
        _row(
            "local_install",
            "pass" if local_install_ready else "fail",
            f"{local_env_path}; {commercial_independence_path}; {packaging_path}",
            "requirements lock complete, zero missing requirements, reproducible install evidence ready",
            "Customer alpha can point operators at separated ROCm/CPU/dev dependency profiles and local install evidence.",
            "install guide + dependency profiles",
        ),
        _row(
            "rocm_smoke_benchmark",
            "pass" if rocm_ready and throughput_ready else "fail",
            f"{rocm_manifest_path}; {throughput_scorecard_path}",
            "ROCm manifest ready and AMD hardware throughput scorecard ready",
            "Customer alpha has AMD-native runtime status plus hardware smoke throughput evidence.",
            "ROCm environment status + hardware throughput scorecard",
        ),
        _row(
            "docking_job_evidence",
            "pass" if product_bundle_ready and product_readiness_ready else "fail",
            f"{product_bundle_path}; {product_readiness_path}",
            "validated local delivery bundle and product handoff evidence",
            "Customer alpha references validated docking-job delivery evidence without executing a new docking run.",
            "validated local delivery bundle",
        ),
        _row(
            "report_bundle_generated",
            "pass" if product_bundle_ready and bool(local_delivery_bundle_dir) else "fail",
            product_bundle_path,
            "result bundle contract points to an expected local delivery bundle directory",
            "Customer alpha has a report-bundle handoff surface rooted in existing validated local evidence.",
            local_delivery_bundle_dir or "missing local delivery bundle path",
        ),
        _row(
            "benchmark_evidence",
            "pass" if residual_ready and gpcr_ready and public_regression_ready else "fail",
            f"{residual_shadow_path}; {gpcr_proof_path}; {public_regression_path}",
            "residual shadow A/B, GPCR hard-decoy proof, and public benchmark residual regression gate ready",
            "Customer alpha includes benchmark-driven residual evidence while keeping residual_mode=shadow.",
            "residual A/B report + public benchmark regression status",
        ),
        _row(
            "commercial_independence",
            "pass" if commercial_ready else "fail",
            commercial_independence_path,
            "commercial independence gate ready and external SaaS runtime dependency count is zero",
            "Customer alpha can be positioned as a local/private product surface.",
            "commercial independence status",
        ),
        _row(
            "approval_safety",
            "pass" if no_external_state_mutation else "fail",
            "all alpha manifest source packets",
            "no external mutation, upload, email, submission, archive, externalization, or deletion",
            "Customer alpha preserves approval-token safety and records that no external state was changed.",
            "approval safety status",
        ),
        _row(
            "amd_packaging_profile",
            "pass" if packaging_ready else "fail",
            packaging_path,
            "AMD Workstation Profile and AMD Server Profile packaging evidence ready",
            "Customer alpha includes the AMD workstation/server delivery profile.",
            "AMD packaging profile",
        ),
    ]
    fail_rows = [row for row in rows if row["status"] != "pass"]
    alpha_ready = not fail_rows
    artifacts = {
        "packaging_profile": packaging_path,
        "rocm_manifest": rocm_manifest_path,
        "hardware_throughput_scorecard": throughput_scorecard_path,
        "residual_ab_report": residual_shadow_path,
        "gpcr_hard_decoy_residual_proof": gpcr_proof_path,
        "public_benchmark_residual_regression_gate": public_regression_path,
        "validated_local_delivery_bundle_contract": product_bundle_path,
        "commercial_independence_gate": commercial_independence_path,
        "product_readiness_gate": product_readiness_path,
        "local_delivery_environment_manifest": local_env_path,
        "local_delivery_bundle_dir": local_delivery_bundle_dir,
    }
    summary = {
        "packet_type": "customer_alpha_bundle_manifest",
        "status": "customer_alpha_bundle_manifest_ready" if alpha_ready else "blocked_customer_alpha_bundle_manifest",
        "customer_alpha_bundle_ready": alpha_ready,
        "alpha_bundle_ready": alpha_ready,
        "local_install_evidence_ready": local_install_ready,
        "rocm_smoke_benchmark_succeeds": bool(rocm_ready and throughput_ready),
        "docking_job_evidence_ready": bool(product_bundle_ready and product_readiness_ready),
        "report_bundle_generated": bool(product_bundle_ready and bool(local_delivery_bundle_dir)),
        "benchmark_evidence_ready": bool(residual_ready and gpcr_ready and public_regression_ready),
        "commercial_independence_ready": commercial_ready,
        "approval_safety_ready": no_external_state_mutation,
        "amd_packaging_profile_ready": packaging_ready,
        "residual_mode_default": "shadow",
        "commercial_compute_default": "rocm_hip",
        "cli_surface": ["benchmark rocm", "residual shadow", "residual compare", "report bundle"],
        "api_surface": ["ROCm environment status", "residual mode status", "benchmark regression status"],
        "artifact_surface": ["ROCm manifest", "residual A/B report", "hardware throughput scorecard"],
        "artifact_paths": artifacts,
        "component_count": len(rows),
        "pass_component_count": len(rows) - len(fail_rows),
        "fail_component_count": len(fail_rows),
        "approval_tokens_required": [],
        "execution_enabled": False,
        "benchmark_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Roadmap complete." if alpha_ready else "Repair failed alpha manifest components before customer handoff.",
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    s = payload["summary"]
    lines = [
        "# Customer Alpha Bundle Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- customer_alpha_bundle_ready: `{s['customer_alpha_bundle_ready']}`",
        f"- residual_mode_default: `{s['residual_mode_default']}`",
        f"- commercial_compute_default: `{s['commercial_compute_default']}`",
        f"- pass_component_count: `{s['pass_component_count']}` / `{s['component_count']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Customer Surfaces",
        "",
        f"- CLI: `{', '.join(s['cli_surface'])}`",
        f"- API: `{', '.join(s['api_surface'])}`",
        f"- Artifacts: `{', '.join(s['artifact_surface'])}`",
        "",
        "## Components",
        "",
        "| component | status | evidence | customer surface | reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['component']}` | `{row['status']}` | `{row['evidence']}` | `{row['customer_visible_surface']}` | {row['reason']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build customer alpha bundle manifest from local productization evidence.")
    parser.add_argument("--packaging-json", default=DEFAULT_PACKAGING_JSON)
    parser.add_argument("--rocm-manifest-json", default=DEFAULT_ROCM_MANIFEST_JSON)
    parser.add_argument("--throughput-scorecard-json", default=DEFAULT_THROUGHPUT_SCORECARD_JSON)
    parser.add_argument("--residual-shadow-json", default=DEFAULT_RESIDUAL_SHADOW_JSON)
    parser.add_argument("--gpcr-proof-json", default=DEFAULT_GPCR_PROOF_JSON)
    parser.add_argument("--public-regression-json", default=DEFAULT_PUBLIC_REGRESSION_JSON)
    parser.add_argument("--product-bundle-json", default=DEFAULT_PRODUCT_BUNDLE_JSON)
    parser.add_argument("--commercial-independence-json", default=DEFAULT_COMMERCIAL_INDEPENDENCE_JSON)
    parser.add_argument("--product-readiness-json", default=DEFAULT_PRODUCT_READINESS_JSON)
    parser.add_argument("--local-env-json", default=DEFAULT_LOCAL_ENV_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_customer_alpha_bundle_manifest(
        packaging_packet=_read_json_if_present(args.packaging_json),
        rocm_manifest_packet=_read_json_if_present(args.rocm_manifest_json),
        throughput_scorecard_packet=_read_json_if_present(args.throughput_scorecard_json),
        residual_shadow_packet=_read_json_if_present(args.residual_shadow_json),
        gpcr_proof_packet=_read_json_if_present(args.gpcr_proof_json),
        public_regression_packet=_read_json_if_present(args.public_regression_json),
        product_bundle_packet=_read_json_if_present(args.product_bundle_json),
        commercial_independence_packet=_read_json_if_present(args.commercial_independence_json),
        product_readiness_packet=_read_json_if_present(args.product_readiness_json),
        local_env_packet=_read_json_if_present(args.local_env_json),
        packaging_path=args.packaging_json,
        rocm_manifest_path=args.rocm_manifest_json,
        throughput_scorecard_path=args.throughput_scorecard_json,
        residual_shadow_path=args.residual_shadow_json,
        gpcr_proof_path=args.gpcr_proof_json,
        public_regression_path=args.public_regression_json,
        product_bundle_path=args.product_bundle_json,
        commercial_independence_path=args.commercial_independence_json,
        product_readiness_path=args.product_readiness_json,
        local_env_path=args.local_env_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
