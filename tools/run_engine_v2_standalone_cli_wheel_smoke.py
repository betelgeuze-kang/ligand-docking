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
    canonical_system_json_bytes,
    canonical_system_sha256,
)


def _provenance(name: str, digest: str) -> engine.StructureProvenance:
    return engine.StructureProvenance(
        source_format="installed-wheel-toy",
        source_id=name,
        source_sha256=digest,
        parser_name="installed-wheel-toy-fixture",
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
        system_id=f"installed-wheel-toy-{role}",
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
        "--center",
        "0",
        "0",
        "0",
        "--radius",
        "10",
        "--source-artifact",
        str(receptor_output),
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
        "--synthetic-test-candidates",
        "2",
        "--synthetic-test-top-k",
        "1",
        "--test-only-synthetic",
        "--output",
        str(result),
    )
    _run(cli, "verify", "--result", str(result), "--output", str(verification))
    _run(cli, "report", "--result", str(result), "--output", str(report))

    manifest = _load(ligand_bundle / "manifest.json")
    result_document = _load(result)
    verification_document = _load(verification)
    report_document = _load(report)
    if manifest.get("bundle_absent_only") is not True:
        raise RuntimeError("installed ligand bundle lost absent-only semantics")
    if stat.S_IMODE(ligand_bundle.stat().st_mode) != 0o700:
        raise RuntimeError("installed ligand bundle is not private")
    if result_document.get("candidate_count") != 2:
        raise RuntimeError("installed synthetic denominator changed")
    for field in (
        "external_reservation_requested",
        "historical_execution_authorized",
        "fresh_holdout_execution_authorized",
        "stage0_admission_authority",
        "product_execution_authorized",
        "customer_pose_emission_authorized",
        "public_or_scientific_claim_authorized",
        "claim_safe",
    ):
        if result_document.get(field) is not False:
            raise RuntimeError(f"installed flow asserted forbidden field {field}")
    if (
        verification_document.get("status")
        != "verified_structural_consistency_only"
        or "valid" in verification_document
        or verification_document.get("structural_consistency_valid") is not True
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
