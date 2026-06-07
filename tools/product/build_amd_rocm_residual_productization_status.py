#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MASTER_DOC = "docs/amd_rocm_residual_intelligence_productization_master_plan.md"
DEFAULT_ROCM_MANIFEST_JSON = "runs/rocm_environment_manifest_current.json"
DEFAULT_THROUGHPUT_SCORECARD_JSON = "runs/amd_hardware_throughput_scorecard_current.json"
DEFAULT_RESIDUAL_SHADOW_AB_JSON = "runs/residual_shadow_ab_current.json"
DEFAULT_GPCR_PROOF_JSON = "runs/gpcr_hard_decoy_residual_proof_current.json"
DEFAULT_PUBLIC_BENCHMARK_JSON = "runs/product_public_benchmark_contract_current.json"
DEFAULT_PUBLIC_REGRESSION_JSON = "runs/public_benchmark_residual_regression_gate_current.json"
DEFAULT_AMD_PACKAGING_JSON = "runs/amd_workstation_server_packaging_profile_current.json"
DEFAULT_ALPHA_BUNDLE_JSON = "runs/customer_alpha_bundle_manifest_current.json"
DEFAULT_OUT_JSON = "runs/amd_rocm_residual_productization_status_current.json"
DEFAULT_OUT_CSV = "runs/amd_rocm_residual_productization_status_current.csv"
DEFAULT_OUT_MD = "runs/amd_rocm_residual_productization_status_current.md"

REQUIRED_MASTER_DOC_TERMS = (
    "residual_mode=shadow",
    "ROCm/HIP",
    "E(3)/SE(3)",
    "PINN",
    "AMD Workstation Profile",
    "public benchmark",
)

CLAIM_BOUNDARY = (
    "AMD ROCm residual productization status only; inspects existing local documentation and evidence artifacts. "
    "It does not run benchmarks, docking, model training, package installs, uploads, submissions, email, archive, "
    "externalize, or delete files."
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


def _read_text_if_present(path_like: str | Path) -> str:
    path = _resolve(path_like)
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _packet_ready(packet: dict[str, Any], *, ready_keys: Iterable[str], ready_statuses: Iterable[str]) -> bool:
    summary = _summary(packet)
    status = _text(summary.get("status"))
    return status in set(ready_statuses) or any(summary.get(key) is True for key in ready_keys)


def _phase_row(
    *,
    phase_id: str,
    phase_name: str,
    status: str,
    evidence_artifact: str,
    observed: str,
    required: str,
    reason: str,
    next_required_step: str,
    next_command: str,
) -> dict[str, Any]:
    return {
        "phase_id": phase_id,
        "phase_name": phase_name,
        "status": status,
        "evidence_artifact": evidence_artifact,
        "observed": observed,
        "required": required,
        "reason": reason,
        "next_required_step": next_required_step,
        "next_command": next_command,
        "release_blocker": status != "complete",
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
    }


def build_amd_rocm_residual_productization_status(
    *,
    master_doc_text: str,
    rocm_manifest_packet: dict[str, Any],
    throughput_scorecard_packet: dict[str, Any],
    residual_shadow_ab_packet: dict[str, Any] | None = None,
    gpcr_proof_packet: dict[str, Any] | None = None,
    public_benchmark_packet: dict[str, Any] | None = None,
    public_regression_packet: dict[str, Any] | None = None,
    amd_packaging_packet: dict[str, Any] | None = None,
    alpha_bundle_packet: dict[str, Any] | None = None,
    master_doc_path: str = DEFAULT_MASTER_DOC,
    rocm_manifest_path: str = DEFAULT_ROCM_MANIFEST_JSON,
    throughput_scorecard_path: str = DEFAULT_THROUGHPUT_SCORECARD_JSON,
    residual_shadow_ab_path: str = DEFAULT_RESIDUAL_SHADOW_AB_JSON,
    gpcr_proof_path: str = DEFAULT_GPCR_PROOF_JSON,
    public_benchmark_path: str = DEFAULT_PUBLIC_BENCHMARK_JSON,
    public_regression_path: str = DEFAULT_PUBLIC_REGRESSION_JSON,
    amd_packaging_path: str = DEFAULT_AMD_PACKAGING_JSON,
    alpha_bundle_path: str = DEFAULT_ALPHA_BUNDLE_JSON,
) -> dict[str, Any]:
    residual_shadow_ab_packet = residual_shadow_ab_packet or {}
    gpcr_proof_packet = gpcr_proof_packet or {}
    public_benchmark_packet = public_benchmark_packet or {}
    public_regression_packet = public_regression_packet or {}
    amd_packaging_packet = amd_packaging_packet or {}
    alpha_bundle_packet = alpha_bundle_packet or {}

    missing_doc_terms = [term for term in REQUIRED_MASTER_DOC_TERMS if term not in master_doc_text]
    doc_ready = bool(master_doc_text) and not missing_doc_terms
    rocm_summary = _summary(rocm_manifest_packet)
    throughput_summary = _summary(throughput_scorecard_packet)
    residual_summary = _summary(residual_shadow_ab_packet)
    gpcr_summary = _summary(gpcr_proof_packet)
    public_summary = _summary(public_benchmark_packet)
    regression_summary = _summary(public_regression_packet)
    packaging_summary = _summary(amd_packaging_packet)
    alpha_summary = _summary(alpha_bundle_packet)

    rocm_ready = _text(rocm_summary.get("status")) == "rocm_environment_manifest_ready" and rocm_summary.get("manifest_ready") is True
    throughput_ready = (
        _text(throughput_summary.get("status")) == "amd_hardware_throughput_scorecard_ready"
        and throughput_summary.get("scorecard_ready") is True
    )
    residual_ab_ready = _packet_ready(
        residual_shadow_ab_packet,
        ready_keys=("residual_shadow_ab_ready", "shadow_ab_ready", "scaffold_ready"),
        ready_statuses=("residual_shadow_ab_ready", "residual_shadow_ab_scaffold_ready", "gpcr_residual_locked_decoy_ab_scaffold_ready"),
    )
    gpcr_proof_ready = _packet_ready(
        gpcr_proof_packet,
        ready_keys=("gpcr_hard_decoy_residual_proof_ready", "proof_ready", "regression_gate_ready"),
        ready_statuses=("gpcr_hard_decoy_residual_proof_ready", "gpcr_residual_shadow_proof_ready"),
    )
    public_benchmark_ready = _packet_ready(
        public_benchmark_packet,
        ready_keys=("public_benchmark_validation_ready", "public_benchmark_evidence_ready"),
        ready_statuses=("product_public_benchmark_contract_ready",),
    )
    public_regression_ready = _packet_ready(
        public_regression_packet,
        ready_keys=("public_benchmark_residual_regression_gate_ready", "regression_gate_ready"),
        ready_statuses=("public_benchmark_residual_regression_gate_ready",),
    )
    packaging_ready = _packet_ready(
        amd_packaging_packet,
        ready_keys=("amd_workstation_server_packaging_profile_ready", "packaging_ready"),
        ready_statuses=("amd_workstation_server_packaging_profile_ready",),
    )
    alpha_ready = _packet_ready(
        alpha_bundle_packet,
        ready_keys=("customer_alpha_bundle_ready", "alpha_bundle_ready"),
        ready_statuses=("customer_alpha_bundle_manifest_ready",),
    )

    phase1_ready = bool(rocm_ready and throughput_ready)
    rows = [
        _phase_row(
            phase_id="phase_0",
            phase_name="Document/contract consolidation",
            status="complete" if doc_ready else "blocked",
            evidence_artifact=master_doc_path,
            observed="ready" if doc_ready else f"missing_terms={','.join(missing_doc_terms) or 'document_missing'}",
            required="master plan exists and contains required ROCm/residual/productization terms",
            reason="Phase 0 fixes residual_mode=shadow and product architecture decision language.",
            next_required_step="Proceed to ROCm/HIP platform proof." if doc_ready else "Restore required master plan terms.",
            next_command="test -f docs/amd_rocm_residual_intelligence_productization_master_plan.md",
        ),
        _phase_row(
            phase_id="phase_1",
            phase_name="ROCm manifest + hardware smoke benchmark",
            status="complete" if phase1_ready else "blocked",
            evidence_artifact=f"{rocm_manifest_path}; {throughput_scorecard_path}",
            observed=f"rocm_status={_text(rocm_summary.get('status')) or 'missing'}; throughput_status={_text(throughput_summary.get('status')) or 'missing'}",
            required="rocm_environment_manifest_ready and amd_hardware_throughput_scorecard_ready",
            reason="AMD packaging needs runtime detection plus measured throughput metrics before ROCm/HIP performance claims.",
            next_required_step=(
                "Proceed to residual shadow A/B scaffold."
                if phase1_ready
                else "Expose/record ROCm runtime and ingest AMD hardware smoke benchmark measurements."
            ),
            next_command="python3 tools/build_rocm_environment_manifest.py && python3 tools/build_amd_hardware_throughput_scorecard.py",
        ),
        _phase_row(
            phase_id="phase_2",
            phase_name="Residual shadow A/B scaffold",
            status="complete" if residual_ab_ready else "pending",
            evidence_artifact=residual_shadow_ab_path,
            observed=_text(residual_summary.get("status")) or "missing",
            required="residual shadow A/B report with residual_mode=shadow and raw ranking preserved",
            reason="Residual corrections must be observed in shadow mode before assist or production promotion.",
            next_required_step="Proceed to GPCR hard-decoy slice proof." if residual_ab_ready else "Emit residual shadow A/B artifact without changing ranking.",
            next_command="betelgeuze-product residual shadow",
        ),
        _phase_row(
            phase_id="phase_3",
            phase_name="GPCR hard-decoy slice residual proof",
            status="complete" if gpcr_proof_ready else "pending",
            evidence_artifact=gpcr_proof_path,
            observed=_text(gpcr_summary.get("status")) or "missing",
            required="GPCR hard-decoy intrusion reduction proof without pass-to-fail regression",
            reason="First residual proof should target the known hard-decoy failure mode.",
            next_required_step="Proceed to public benchmark residual regression gate." if gpcr_proof_ready else "Run GPCR hard-decoy residual proof after Phase 2 scaffold readiness.",
            next_command="betelgeuze-product residual compare",
        ),
        _phase_row(
            phase_id="phase_4",
            phase_name="Public benchmark residual regression gate",
            status="complete" if public_benchmark_ready and public_regression_ready else "pending",
            evidence_artifact=f"{public_benchmark_path}; {public_regression_path}",
            observed=f"public_benchmark_status={_text(public_summary.get('status')) or 'missing'}; residual_regression_status={_text(regression_summary.get('status')) or 'missing'}",
            required="public benchmark contract ready plus residual regression gate ready",
            reason="LIT-PCBA/DUDE-Z/PDBbind-CASF/BM5/CASP archive checks prevent residual overfitting.",
            next_required_step="Proceed to AMD workstation/server packaging." if public_benchmark_ready and public_regression_ready else "Materialize residual comparison gates across public benchmark suites.",
            next_command="betelgeuze-product residual compare && betelgeuze-product report bundle",
        ),
        _phase_row(
            phase_id="phase_5",
            phase_name="AMD Workstation/Server packaging",
            status="complete" if packaging_ready else "pending",
            evidence_artifact=amd_packaging_path,
            observed=_text(packaging_summary.get("status")) or "missing",
            required="AMD Workstation Profile and AMD Server Profile package evidence",
            reason="Commercial delivery needs reproducible hardware profiles, dependency lockfiles, and fallback policy.",
            next_required_step="Proceed to customer-facing alpha bundle." if packaging_ready else "Define/package AMD workstation and server profiles after benchmark gates are green.",
            next_command="betelgeuze-product benchmark rocm",
        ),
        _phase_row(
            phase_id="phase_6",
            phase_name="Customer-facing alpha bundle",
            status="complete" if alpha_ready else "pending",
            evidence_artifact=alpha_bundle_path,
            observed=_text(alpha_summary.get("status")) or "missing",
            required="customer alpha bundle manifest with CLI/API/report artifacts",
            reason="The alpha bundle is the customer-visible handoff surface for the independent product.",
            next_required_step="Productization roadmap complete." if alpha_ready else "Build alpha bundle once hardware, residual, benchmark, and packaging gates pass.",
            next_command="betelgeuze-product report bundle",
        ),
    ]
    complete_rows = [row for row in rows if row["status"] == "complete"]
    blocked_rows = [row for row in rows if row["status"] == "blocked"]
    pending_rows = [row for row in rows if row["status"] == "pending"]
    all_complete = len(complete_rows) == len(rows)
    first_open = next((row for row in rows if row["status"] != "complete"), None)
    primary_bottleneck_phase = "none" if all_complete or first_open is None else first_open["phase_id"]
    primary_bottleneck = "none" if all_complete or first_open is None else first_open["phase_name"]
    primary_bottleneck_status = "complete" if all_complete or first_open is None else first_open["status"]
    primary_bottleneck_reason = "Productization roadmap complete." if all_complete or first_open is None else first_open["reason"]
    next_required_step = "Productization roadmap complete." if all_complete or first_open is None else first_open["next_required_step"]
    next_command = "none" if all_complete or first_open is None else first_open["next_command"]
    return {
        "summary": {
            "packet_type": "amd_rocm_residual_productization_status",
            "status": "amd_rocm_residual_productization_complete" if all_complete else "blocked_amd_rocm_residual_productization",
            "roadmap_complete": all_complete,
            "phase_count": len(rows),
            "complete_phase_count": len(complete_rows),
            "blocked_phase_count": len(blocked_rows),
            "pending_phase_count": len(pending_rows),
            "completion_percent": round((len(complete_rows) / len(rows)) * 100.0, 3),
            "phase0_document_contract_ready": doc_ready,
            "phase1_rocm_manifest_ready": rocm_ready,
            "phase1_hardware_throughput_scorecard_ready": throughput_ready,
            "phase2_residual_shadow_ab_ready": residual_ab_ready,
            "phase3_gpcr_hard_decoy_proof_ready": gpcr_proof_ready,
            "phase4_public_benchmark_ready": public_benchmark_ready,
            "phase4_public_residual_regression_ready": public_regression_ready,
            "phase5_amd_packaging_ready": packaging_ready,
            "phase6_alpha_bundle_ready": alpha_ready,
            "residual_mode_default": "shadow",
            "commercial_compute_default": "rocm_hip",
            "cpu_fallback_available": True,
            "approval_tokens_required": [],
            "primary_bottleneck_phase": primary_bottleneck_phase,
            "primary_bottleneck": primary_bottleneck,
            "primary_bottleneck_status": primary_bottleneck_status,
            "primary_bottleneck_reason": primary_bottleneck_reason,
            "next_required_step": next_required_step,
            "next_command": next_command,
            "execution_enabled": False,
            "benchmark_executed": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        },
        "rows": rows,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# AMD ROCm Residual Productization Status",
        "",
        f"- status: `{s['status']}`",
        f"- roadmap_complete: `{s['roadmap_complete']}`",
        f"- complete_phase_count: `{s['complete_phase_count']}` / `{s['phase_count']}`",
        f"- completion_percent: `{s['completion_percent']}`",
        f"- residual_mode_default: `{s['residual_mode_default']}`",
        f"- commercial_compute_default: `{s['commercial_compute_default']}`",
        f"- primary_bottleneck_phase: `{s['primary_bottleneck_phase']}`",
        f"- primary_bottleneck: `{s['primary_bottleneck']}`",
        f"- primary_bottleneck_status: `{s['primary_bottleneck_status']}`",
        f"- execution_enabled: `{s['execution_enabled']}`",
        f"- benchmark_executed: `{s['benchmark_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Roadmap",
        "",
        "| phase | status | evidence | observed | next step |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['phase_id']}` {row['phase_name']} | `{row['status']}` | `{row['evidence_artifact']}` | `{row['observed']}` | {row['next_required_step']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Command", "", f"`{s['next_command']}`", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AMD ROCm residual productization roadmap status.")
    parser.add_argument("--master-doc", default=DEFAULT_MASTER_DOC)
    parser.add_argument("--rocm-manifest-json", default=DEFAULT_ROCM_MANIFEST_JSON)
    parser.add_argument("--throughput-scorecard-json", default=DEFAULT_THROUGHPUT_SCORECARD_JSON)
    parser.add_argument("--residual-shadow-ab-json", default=DEFAULT_RESIDUAL_SHADOW_AB_JSON)
    parser.add_argument("--gpcr-proof-json", default=DEFAULT_GPCR_PROOF_JSON)
    parser.add_argument("--public-benchmark-json", default=DEFAULT_PUBLIC_BENCHMARK_JSON)
    parser.add_argument("--public-regression-json", default=DEFAULT_PUBLIC_REGRESSION_JSON)
    parser.add_argument("--amd-packaging-json", default=DEFAULT_AMD_PACKAGING_JSON)
    parser.add_argument("--alpha-bundle-json", default=DEFAULT_ALPHA_BUNDLE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_amd_rocm_residual_productization_status(
        master_doc_text=_read_text_if_present(args.master_doc),
        rocm_manifest_packet=_read_json_if_present(args.rocm_manifest_json),
        throughput_scorecard_packet=_read_json_if_present(args.throughput_scorecard_json),
        residual_shadow_ab_packet=_read_json_if_present(args.residual_shadow_ab_json),
        gpcr_proof_packet=_read_json_if_present(args.gpcr_proof_json),
        public_benchmark_packet=_read_json_if_present(args.public_benchmark_json),
        public_regression_packet=_read_json_if_present(args.public_regression_json),
        amd_packaging_packet=_read_json_if_present(args.amd_packaging_json),
        alpha_bundle_packet=_read_json_if_present(args.alpha_bundle_json),
        master_doc_path=args.master_doc,
        rocm_manifest_path=args.rocm_manifest_json,
        throughput_scorecard_path=args.throughput_scorecard_json,
        residual_shadow_ab_path=args.residual_shadow_ab_json,
        gpcr_proof_path=args.gpcr_proof_json,
        public_benchmark_path=args.public_benchmark_json,
        public_regression_path=args.public_regression_json,
        amd_packaging_path=args.amd_packaging_json,
        alpha_bundle_path=args.alpha_bundle_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
