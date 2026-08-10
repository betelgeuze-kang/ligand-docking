#!/usr/bin/env python3
"""Run the claim-blocked synthetic standalone flow from an installed wheel."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import torch

import betelgeuze_engine_v2 as engine
from betelgeuze_engine_v2.molecular import (
    all_atom_system_from_canonical_json,
    canonical_system_json_bytes,
    canonical_system_sha256,
)


def _provenance(name: str, digest: str) -> engine.StructureProvenance:
    return engine.StructureProvenance(
        source_format="unit",
        source_id=name,
        source_sha256=digest,
        parser_name="standalone-consumer-fixture",
        parser_version="1.0.0",
    )


def _system(*, receptor: bool) -> engine.AllAtomSystem:
    elements = ("O", "N", "H", "C", "H") if receptor else ("C", "N", "H", "O", "H")
    charges = (-0.4, -0.2, 0.2, 0.0, 0.4) if receptor else (0.0, -0.2, 0.2, -0.4, 0.4)
    coordinates = (
        ([2.0, 0.0, 0.0], [3.0, 3.0, 0.0], [2.5, 2.5, 0.0], [-2.0, 3.0, 0.0], [6.0, 6.0, 0.0])
        if receptor
        else ([-2.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [-2.0, 0.0, 0.0], [-3.0, 0.0, 0.0])
    )
    role = "receptor" if receptor else "ligand"
    return engine.AllAtomSystem(
        system_id=f"standalone-consumer-{role}",
        atoms=tuple(
            engine.Atom(
                index=index,
                name=f"{role[0].upper()}{index}",
                element=element,
                atomic_number={"C": 6, "N": 7, "H": 1, "O": 8}[element],
                residue_index=0,
                partial_charge_e=charges[index],
            )
            for index, element in enumerate(elements)
        ),
        bonds=(engine.Bond(index=0, atom_i=1, atom_j=2),)
        if receptor
        else (
            engine.Bond(index=0, atom_i=0, atom_j=1),
            engine.Bond(index=1, atom_i=1, atom_j=2),
            engine.Bond(index=2, atom_i=0, atom_j=3),
            engine.Bond(index=3, atom_i=3, atom_j=4),
        ),
        residues=(
            engine.Residue(
                index=0,
                name="REC" if receptor else "LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=tuple(range(5)),
                entity_type="polymer" if receptor else "non-polymer",
                hetero=not receptor,
            ),
        ),
        chains=(
            engine.Chain(
                index=0,
                chain_id="A" if receptor else "L",
                residue_indices=(0,),
            ),
        ),
        coordinates=torch.tensor([coordinates], dtype=torch.float64),
        provenance=_provenance(role, ("b" if receptor else "a") * 64),
    )


def _load(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        raise RuntimeError(f"{path.name} is not one canonical JSON line")
    document = json.loads(raw[:-1].decode("ascii"))
    canonical = json.dumps(
        document,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    if raw != canonical + b"\n" or not isinstance(document, dict):
        raise RuntimeError(f"{path.name} is not canonical JSON")
    return document


def _run(cli: Path, *arguments: str) -> None:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        (str(cli), *arguments),
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )
    if completed.returncode != 0 or completed.stdout or completed.stderr:
        raise RuntimeError(
            f"betelgeuze-dock {' '.join(arguments[:1])} failed: "
            f"returncode={completed.returncode}; stdout={completed.stdout!r}; "
            f"stderr={completed.stderr!r}"
        )


def run(work_directory: Path, *, forbidden_import_root: Path | None) -> None:
    package_path = Path(engine.__file__).resolve()
    if forbidden_import_root is not None:
        forbidden = forbidden_import_root.resolve()
        if package_path == forbidden or forbidden in package_path.parents:
            raise RuntimeError("Engine v2 imported from the checkout, not the wheel")
    work_directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    cli = Path(sys.executable).with_name("betelgeuze-dock")
    if not cli.is_file():
        raise RuntimeError("installed betelgeuze-dock entry point is missing")

    receptor = _system(receptor=True)
    ligand = _system(receptor=False)
    receptor_input = work_directory / "receptor-input.json"
    ligand_input = work_directory / "ligand-input.json"
    receptor_input.write_bytes(canonical_system_json_bytes(receptor) + b"\n")
    ligand_input.write_bytes(canonical_system_json_bytes(ligand) + b"\n")
    receptor_output = work_directory / "receptor.json"
    ligand_bundle = work_directory / "ligands"
    pocket = work_directory / "pocket.json"
    result = work_directory / "result.json"
    verification = work_directory / "verification.json"
    report = work_directory / "report.json"

    _run(
        cli,
        "prepare-receptor",
        "--input",
        str(receptor_input),
        "--output",
        str(receptor_output),
    )
    _run(
        cli,
        "prepare-ligands",
        "--input",
        str(ligand_input),
        "--output-dir",
        str(ligand_bundle),
    )
    ligand_output = ligand_bundle / f"{canonical_system_sha256(ligand)}.json"
    _run(
        cli,
        "define-pocket",
        "--synthetic-d0-fixture",
        "--coordinate-frame-id",
        "prepared-receptor-frame-v1",
        "--output",
        str(pocket),
    )
    _run(
        cli,
        "dock",
        "--receptor",
        str(receptor_output),
        "--ligand",
        str(ligand_output),
        "--pocket",
        str(pocket),
        "--seed",
        "4301",
        "--test-only-synthetic",
        "--output",
        str(result),
    )
    _run(cli, "verify", "--result", str(result), "--output", str(verification))
    _run(cli, "report", "--result", str(result), "--output", str(report))

    admission = engine.repository_synthetic_d0_fixture_admission()
    prepared_receptor_raw = receptor_output.read_bytes()
    if not prepared_receptor_raw.endswith(b"\n"):
        raise RuntimeError("installed prepared receptor is not newline terminated")
    prepared_receptor = all_atom_system_from_canonical_json(
        prepared_receptor_raw[:-1]
    )
    if canonical_system_sha256(prepared_receptor) != admission.receptor_system_sha256:
        raise RuntimeError("installed prepared receptor lost admitted identity")
    manifest = _load(ligand_bundle / "manifest.json")
    pocket_document = _load(pocket)
    result_document = _load(result)
    verification_document = _load(verification)
    report_document = _load(report)
    if manifest.get("bundle_absent_only") is not True:
        raise RuntimeError("installed ligand bundle lost absent-only semantics")
    if stat.S_IMODE(ligand_bundle.stat().st_mode) != 0o700:
        raise RuntimeError("installed ligand bundle is not private")
    if (
        manifest.get("systems", [{}])[0].get("system_sha256")
        != admission.ligand_system_sha256
    ):
        raise RuntimeError("installed prepared ligand lost admitted identity")
    if (
        pocket_document.get("method_id") != "consumer-reviewed-sphere"
        or pocket_document.get("coordinate_frame_id")
        != "prepared-receptor-frame-v1"
        or pocket_document.get("center_angstrom") != [0.0, 0.0, 0.0]
        or pocket_document.get("radius_angstrom") != 10.0
    ):
        raise RuntimeError("installed synthetic D0 pocket materialization changed")
    scientific = result_document.get("scientific_pipeline_receipt")
    if not isinstance(scientific, dict):
        raise RuntimeError("installed scientific pipeline receipt is missing")
    final_batch = scientific.get("final_scoring_batch")
    if not isinstance(final_batch, dict):
        raise RuntimeError("installed final scoring batch is missing")
    candidates = final_batch.get("records")
    top_indices = result_document.get("top_proposal_indices")
    valid_top_indices = result_document.get("top_valid_proposal_indices")
    profile = result_document.get("pipeline_profile")
    request = result_document.get("request")
    if (
        result_document.get("schema_id")
        != "betelgeuze.engine_v2_standalone_scientific_core_receipt/1.0.0"
        or result_document.get("candidate_denominator") != 64
        or not isinstance(candidates, list)
        or [row.get("slot_index") for row in candidates] != list(range(64))
        or result_document.get("success_count", 0)
        + result_document.get("failure_count", 0)
        != 64
        or result_document.get("success_count") != 32
        or result_document.get("failure_count") != 32
        or result_document.get("score_evidence_complete_count") != 32
        or result_document.get("pose_valid_count") != 32
        or result_document.get("pose_invalid_count") != 0
        or result_document.get("failure_denominator_preserved") is not True
        or not isinstance(profile, dict)
        or profile.get("candidate_count") != 64
        or profile.get("top_k") != 5
        or profile.get("failure_denominator_required") != 64
        or not isinstance(top_indices, list)
        or len(top_indices) != 5
        or top_indices != [45, 47, 23, 63, 9]
        or valid_top_indices != top_indices
        or final_batch.get("candidate_denominator") != 64
        or final_batch.get("score_evidence_complete_count") != 32
        or final_batch.get("pose_valid_count") != 32
        or final_batch.get("denominator_failure_complete") is not True
        or final_batch.get("scorer_v1_terms_fully_preserved") is not True
    ):
        raise RuntimeError(
            "installed scientific synthetic D0 fixed64/Top5 contract changed"
        )
    scored = [row for row in candidates if row.get("rank_eligible") is True]
    if (
        len(scored) != 32
        or any(
            not isinstance(row.get("scorer_evidence"), dict)
            or not isinstance(row["scorer_evidence"].get("terms"), dict)
            or not isinstance(row.get("pose_validity_evidence"), dict)
            or row.get("valid_rank_eligible") is not True
            for row in scored
        )
    ):
        raise RuntimeError(
            "installed scientific receipt lost scorer terms or validity evidence"
        )
    if (
        not isinstance(request, dict)
        or request.get("request_sha256") != admission.request_sha256
        or request.get("receptor_system_sha256")
        != admission.receptor_system_sha256
        or request.get("ligand_system_sha256") != admission.ligand_system_sha256
        or request.get("pocket_fingerprint_sha256")
        != admission.pocket_fingerprint_sha256
        or result_document.get("fixture_manifest_sha256") != admission.manifest_sha256
        or result_document.get("fixture_admission_receipt_sha256")
        != admission.receipt_sha256
        or request.get("synthetic_only_acknowledgment")
        != engine.SYNTHETIC_ONLY_ACKNOWLEDGMENT
    ):
        raise RuntimeError("installed synthetic D0 admission binding changed")
    if (
        result_document.get("component_binding_mode")
        != "sealed_fixed64_scientific_components"
        or result_document.get("canonical_components_sealed") is not True
        or result_document.get("arbitrary_dependency_injection_used") is not False
        or result_document.get("canonical_scientific_core_receipt") is not True
        or result_document.get("complete_scorer_v1_terms_preserved") is not True
        or result_document.get("complete_pose_validity_preserved") is not True
        or result_document.get("primary_and_valid_only_rank_preserved") is not True
        or result_document.get("consumer_activation_scope")
        != "exact_repository_synthetic_d0_only"
    ):
        raise RuntimeError("installed sealed scientific component binding changed")
    for field in (
        "canonical_docking_pipeline_activation_authorized",
        "cli_activation_authorized",
        "api_activation_authorized",
        "benchmark_activation_authorized",
        "product_shadow_activation_authorized",
    ):
        if result_document.get(field) is not True:
            raise RuntimeError(f"installed flow lost synthetic activation {field}")
    for field in (
        "external_reservation_requested",
        "producer_attested",
        "activation_evidence_eligible",
        "reservation_allowed",
        "molecular_cohort_execution_authorized",
        "historical_or_fresh_execution_authorized",
        "stage0_admission_authority",
        "product_execution_authorized",
        "product_mutation_authorized",
        "existing_rank_auto_change_authorized",
        "customer_pose_emission_authorized",
        "public_benchmark_execution_authorized",
        "hip_execution_authorized",
        "public_or_scientific_claim_authorized",
        "claim_safe",
    ):
        if result_document.get(field) is not False:
            raise RuntimeError(f"installed flow asserted forbidden field {field}")
    if "_construction_proof_sha256" in json.dumps(
        result_document,
        sort_keys=True,
    ):
        raise RuntimeError("installed result serialized a private construction proof")
    if (
        verification_document.get("status")
        != "verified_structural_consistency_only"
        or verification_document.get("verification_scope")
        != "available_serialized_structure_only_no_opaque_upstream_content"
        or "valid" in verification_document
        or "cross_bindings_verified" in verification_document
        or "derived_semantics_verified" in verification_document
        or verification_document.get("structural_consistency_valid") is not True
        or verification_document.get(
            "available_structural_cross_bindings_verified"
        )
        is not True
        or verification_document.get("available_derived_semantics_verified")
        is not True
        or verification_document.get(
            "opaque_upstream_receipt_content_verified"
        )
        is not False
        or verification_document.get("content_authenticity_verified") is not False
        or verification_document.get("execution_authority_granted") is not False
    ):
        raise RuntimeError("installed verifier overstated its scope")
    if (
        report_document.get("status") != "structural_report_only"
        or report_document.get("product_execution_authorized") is not False
        or report_document.get("public_or_scientific_claim_authorized") is not False
    ):
        raise RuntimeError("installed report asserted forbidden authority")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--forbid-import-root", type=Path)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    run(
        arguments.work_dir,
        forbidden_import_root=arguments.forbid_import_root,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
