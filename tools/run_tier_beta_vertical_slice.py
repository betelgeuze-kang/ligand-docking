#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.result_manifest import write_result_manifest  # noqa: E402
from betelgeuze_ai_md.contracts.api_adapter import write_api_evidence_bundle  # noqa: E402
from betelgeuze_engine.biodiscovery import TierBetaScreening  # noqa: E402


def _read_text_or_value(value: str) -> str:
    text = str(value or "").strip()
    if text and Path(text).exists() and Path(text).is_file():
        return Path(text).read_text(encoding="utf-8", errors="ignore")
    return text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the local Tier-beta BioDiscovery vertical-slice service."
    )
    parser.add_argument("--protein-input", required=True, help="PDB/mmCIF path or inline PDB text.")
    parser.add_argument("--ligand-input", required=True, help="SMILES/SDF path or ligand text.")
    parser.add_argument("--result-json", required=True)
    parser.add_argument("--manifest-json", default="")
    parser.add_argument("--evidence-bundle-json", default="")
    parser.add_argument("--pose-count", type=int, default=8)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--stability-steps", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--signing-key", default="local-dev-result-manifest-signing-key-change-me")
    parser.add_argument("--key-id", default="local-dev")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.evidence_bundle_json and not args.manifest_json:
        raise SystemExit("--evidence-bundle-json requires --manifest-json")
    service = TierBetaScreening(
        device="cpu",
        pose_count=int(args.pose_count),
        top_k=int(args.top_k),
        stability_steps=int(args.stability_steps),
        seed=int(args.seed),
    )
    result = service.screen(
        protein_input=_read_text_or_value(args.protein_input),
        ligand_input=_read_text_or_value(args.ligand_input),
    )
    result_payload: dict[str, Any] = {
        "artifact_type": "tier_beta_vertical_slice_cli_result",
        "result": result,
        "claim_metadata": result.claim_metadata,
        "result_manifest": result.result_manifest,
        "external_state_mutated": False,
    }
    result_path = Path(args.result_json)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(
            result_payload,
            default=lambda item: item.__dict__ if hasattr(item, "__dict__") else str(item),
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    api_manifest: dict[str, Any] = {}
    manifest_request = {
        "protein_input_sha256": result.result_manifest.get("content_hash", ""),
        "ligand_input": "<redacted>",
        "pose_count": int(args.pose_count),
        "top_k": int(args.top_k),
        "stability_steps": int(args.stability_steps),
    }
    status = "completed" if result.ok else "failed"
    if args.manifest_json:
        api_manifest = write_result_manifest(
            args.manifest_json,
            job_id="tier_beta_cli",
            request=manifest_request,
            status=status,
            result_file=str(result_path),
            error=str(result.blocked_reason or ""),
            signing_key=str(args.signing_key),
            key_id=str(args.key_id),
            claim_scope=str(result.claim_scope),
            topology_fidelity=str(result.claim_metadata.get("topology_fidelity") or "sequence_mapped"),
            accuracy_claim_grade="restricted-local-tier-beta",
            result_claim_metadata=result.claim_metadata,
        )
    if args.evidence_bundle_json:
        result_payload = json.loads(result_path.read_text(encoding="utf-8"))
        bundle = write_api_evidence_bundle(
            args.evidence_bundle_json,
            job_id="tier_beta_cli",
            request=manifest_request,
            result_manifest=api_manifest,
            result_payload=result_payload,
            status_payload={
                "job_id": "tier_beta_cli",
                "status": status,
                "result_file": str(result_path),
                "result_manifest": str(args.manifest_json),
            },
        )
        api_manifest["evidence_bundle"] = str(args.evidence_bundle_json)
        api_manifest["evidence_bundle_sha256"] = bundle.fingerprint()
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
