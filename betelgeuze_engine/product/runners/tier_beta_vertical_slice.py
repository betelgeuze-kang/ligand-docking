from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
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


def _request_json_payload(value: str) -> dict[str, Any] | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.exists() or not path.is_file() or path.suffix.lower() != ".json":
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _request_params(payload: dict[str, Any]) -> dict[str, Any]:
    params = payload.get("runner_profile_params")
    return dict(params) if isinstance(params, dict) else {}


def _resolve_inputs(args: argparse.Namespace) -> tuple[str, str, list[int] | None, int, int, int, int]:
    request_payload = _request_json_payload(str(args.protein_input))
    same_json_request = bool(
        request_payload is not None
        and str(args.protein_input or "").strip() == str(args.ligand_input or "").strip()
    )
    if not same_json_request or request_payload is None:
        return (
            _read_text_or_value(args.protein_input),
            _read_text_or_value(args.ligand_input),
            None,
            int(args.pose_count),
            int(args.top_k),
            int(args.stability_steps),
            int(args.seed),
        )
    params = _request_params(request_payload)
    pocket_indices = params.get("pocket_residue_indices")
    if isinstance(pocket_indices, list) and all(isinstance(item, int) for item in pocket_indices):
        resolved_pocket_indices = pocket_indices
    else:
        resolved_pocket_indices = None
    protein_input = (
        params.get("protein_input")
        or params.get("pdb_content")
        or request_payload.get("pdb_content")
        or params.get("pdb_path")
        or request_payload.get("pdb_path")
        or ""
    )
    ligand_input = (
        params.get("ligand_input")
        or params.get("smiles")
        or params.get("sdf_content")
        or params.get("sdf_path")
        or ""
    )
    return (
        str(protein_input or ""),
        str(ligand_input or ""),
        resolved_pocket_indices,
        int(params.get("pose_count") or args.pose_count),
        int(params.get("top_k") or args.top_k),
        int(params.get("stability_steps") or args.stability_steps),
        int(params.get("seed") or args.seed),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local Tier-beta BioDiscovery vertical-slice service.")
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
    request_json_mode = _request_json_payload(str(args.protein_input)) is not None and (
        str(args.protein_input or "").strip() == str(args.ligand_input or "").strip()
    )
    protein_input, ligand_input, pocket_indices, pose_count, top_k, stability_steps, seed = _resolve_inputs(args)
    service = TierBetaScreening(
        device="cpu",
        pose_count=pose_count,
        top_k=top_k,
        stability_steps=stability_steps,
        seed=seed,
    )
    result = service.screen(
        protein_input=protein_input,
        ligand_input=ligand_input,
        pocket_residue_indices=pocket_indices,
    )
    result_payload: dict[str, Any] = {
        "artifact_type": "tier_beta_vertical_slice_cli_result",
        "result": result,
        "claim_metadata": result.claim_metadata,
        "result_manifest": result.result_manifest,
        "request_mode": "request_json" if request_json_mode else "direct_cli",
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
        "pose_count": pose_count,
        "top_k": top_k,
        "stability_steps": stability_steps,
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
